import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from litellm import acompletion
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings, model_supports_tools
from app.services.llm import normalize_ollama_url
from app.tools import get_tool, get_tool_schemas
from app.tools.base import ToolContext

# Models that use the OpenAI Responses API instead of Chat Completions.
RESPONSES_API_MODELS: frozenset[str] = frozenset({"gpt-5-nano", "gpt-5.4-nano"})

logger = logging.getLogger(__name__)


AGENT_SYSTEM_PROMPT = """You are a skilled AI assistant for recruiters and talent acquisition professionals. You help with candidate research, job market analysis, sourcing strategies, and managing recruiter knowledge.

You have the following tools available:
- document_search: Search the user's uploaded documents (resumes, job descriptions, offer letters, sourcing notes).
- web_search: Search the web for company intelligence, salary benchmarks, job market trends, and candidate background.
- url_reader: Fetch and read the full content of any public URL the user shares or that appears in search results.
- python_executor: Execute Python code for data analysis, candidate scoring, or parsing structured data like CSV exports.
- memory_search: Search what the user has told you in past sessions — their preferences, candidate notes, company context.
- memory_save: Save a personal fact, preference, or ongoing context about the user to long-term memory.

Guidelines:
- Use document_search when the user asks about a specific candidate, role, or document they have uploaded.
- Use web_search when you need current company information, salary data, industry news, or anything that may have changed recently.
- Use url_reader when the user shares a link or when a web search result needs deeper reading before you can answer.
- Use memory_search when the user references something they told you before, or when past context might improve your answer.
- Use memory_save when the user shares a personal fact, preference, or ongoing context that would be useful in future sessions (e.g., their name, company, preferred answer format, open requisitions). Do NOT save temporary task context — things they just asked about or one-time lookups.
- Multiple sequential tool calls are fine when gathering information from different sources.

IMPORTANT — Tool synthesis rule:
After EVERY tool call, you MUST write a complete response to the user that:
1. Summarizes what the tool found (or explains if it found nothing useful).
2. Directly answers the user's original question using that information.
3. Cites URLs when web_search results are used.
Never end your turn with only tool calls and no text — always follow tool results with a user-facing answer.
"""

GUEST_ALLOWED_TOOLS: frozenset[str] = frozenset(
    {"document_search", "memory_search", "web_search", "url_reader"}
    # python_executor and memory_save are absent — guests cannot execute code or save memories
)


def _to_responses_input(messages: list[dict]) -> list[dict]:
    """Convert standard chat-completion messages to Responses API input format."""
    result: list[dict] = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content") or ""
        if role == "system":
            result.append({"role": "developer", "content": [{"type": "input_text", "text": content}]})
        elif role == "user":
            result.append({"role": "user", "content": [{"type": "input_text", "text": content}]})
        elif role == "assistant":
            if msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    result.append({
                        "type": "function_call",
                        "call_id": tc["id"],
                        "name": tc["function"]["name"],
                        "arguments": tc["function"]["arguments"],
                    })
            if content:
                result.append({"role": "assistant", "content": [{"type": "output_text", "text": content}]})
        elif role == "tool":
            result.append({
                "type": "function_call_output",
                "call_id": msg.get("tool_call_id", ""),
                "output": content,
            })
    return result


def _to_responses_tools(tool_schemas: list[dict]) -> list[dict]:
    """Convert chat-completion tool schemas to Responses API format."""
    return [
        {
            "type": "function",
            "name": s["function"]["name"],
            "description": s["function"]["description"],
            "parameters": s["function"]["parameters"],
        }
        for s in tool_schemas
        if s.get("type") == "function"
    ]


async def _run_responses_agent(
    db: AsyncSession,
    user_id: str,
    input_messages: list[dict],
    responses_tools: list[dict],
    api_key: str,
    model: str,
    is_guest: bool = False,
) -> AsyncGenerator[dict, None]:
    """Agent loop using the OpenAI Responses API (for gpt-5-nano and similar)."""
    client = AsyncOpenAI(api_key=api_key)
    ctx = ToolContext(user_id=user_id, db=db, is_guest=is_guest)

    for iteration in range(settings.agent_max_iterations):
        logger.info(f"Responses API iteration {iteration + 1}/{settings.agent_max_iterations}")

        try:
            stream = await client.responses.create(
                model=model,
                input=input_messages,
                tools=responses_tools,
                reasoning={"effort": "medium", "summary": "auto"},
                include=["reasoning.encrypted_content"],
                store=True,
                stream=True,
            )
        except Exception as e:
            logger.error(f"Responses API call failed: {e}", exc_info=True)
            yield {"type": "error", "detail": f"LLM error: {str(e)}"}
            return

        accumulated_text = ""
        # call_id -> {name, arguments}
        pending_calls: dict[str, dict] = {}
        # Reasoning items with encrypted_content to pass on the next turn
        reasoning_items: list[dict] = []

        async for event in stream:
            etype = event.type

            if etype == "response.output_text.delta":
                token = event.delta
                accumulated_text += token
                yield {"type": "token", "content": token}

            elif etype == "response.output_item.added":
                item = event.item
                if getattr(item, "type", None) == "function_call":
                    pending_calls[item.call_id] = {"name": item.name, "arguments": ""}

            elif etype == "response.function_call_arguments.delta":
                call_id = getattr(event, "call_id", None)
                if call_id and call_id in pending_calls:
                    pending_calls[call_id]["arguments"] += event.delta

            elif etype == "response.output_item.done":
                item = event.item
                item_type = getattr(item, "type", None)
                if item_type == "function_call":
                    # Use the final complete arguments from the done event
                    if item.call_id in pending_calls:
                        pending_calls[item.call_id]["arguments"] = item.arguments
                elif item_type == "reasoning":
                    enc = getattr(item, "encrypted_content", None)
                    if enc:
                        reasoning_item: dict = {
                            "type": "reasoning",
                            "id": item.id,
                            "encrypted_content": enc,
                        }
                        summary = getattr(item, "summary", None)
                        if summary is not None:
                            reasoning_item["summary"] = summary
                        reasoning_items.append(reasoning_item)

        # Emit the full assistant message for DB persistence
        tool_calls_list = (
            [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["arguments"]},
                }
                for call_id, tc in pending_calls.items()
            ]
            if pending_calls
            else None
        )
        yield {"type": "assistant_message", "content": accumulated_text, "tool_calls": tool_calls_list}

        if not pending_calls:
            if not accumulated_text.strip():
                if iteration == 0:
                    input_messages.append({
                        "role": "user",
                        "content": [{"type": "input_text", "text": "Please summarize your findings and answer my question."}],
                    })
                    logger.warning(
                        "Empty completion (Responses API) on iteration %d — retrying", iteration
                    )
                    continue
                else:
                    yield {
                        "type": "assistant_message",
                        "content": "I wasn't able to generate a response. Please try again.",
                        "tool_calls": None,
                    }
            yield {"type": "done"}
            return

        # Build next-turn input: assistant text, reasoning items, then function_call items
        if accumulated_text:
            input_messages.append({
                "role": "assistant",
                "content": [{"type": "output_text", "text": accumulated_text}],
            })
        input_messages.extend(reasoning_items)
        for call_id, tc in pending_calls.items():
            input_messages.append({
                "type": "function_call",
                "call_id": call_id,
                "name": tc["name"],
                "arguments": tc["arguments"],
            })

        # Execute tools and add results
        for call_id, tc in pending_calls.items():
            tc_name = tc["name"]
            tc_args_raw = tc["arguments"]

            yield {"type": "tool_call_start", "id": call_id, "name": tc_name, "arguments": tc_args_raw}

            try:
                tc_args = json.loads(tc_args_raw) if tc_args_raw else {}
            except json.JSONDecodeError as e:
                tool_result = f"Invalid tool arguments: {e}"
                yield {"type": "tool_call_error", "id": call_id, "name": tc_name, "error": tool_result}
                input_messages.append({"type": "function_call_output", "call_id": call_id, "output": tool_result})
                yield {"type": "tool_message", "tool_call_id": call_id, "content": tool_result}
                continue

            try:
                tool = get_tool(tc_name)
                tool_result = await tool.execute(ctx, tc_args)
                yield {"type": "tool_call_result", "id": call_id, "name": tc_name, "result": tool_result}
            except KeyError:
                tool_result = f"Error: Unknown tool '{tc_name}'"
                yield {"type": "tool_call_error", "id": call_id, "name": tc_name, "error": tool_result}
            except Exception as e:
                logger.error(f"Tool {tc_name} failed: {e}", exc_info=True)
                tool_result = f"Error: {str(e)}"
                yield {"type": "tool_call_error", "id": call_id, "name": tc_name, "error": tool_result}

            input_messages.append({"type": "function_call_output", "call_id": call_id, "output": tool_result})
            yield {"type": "tool_message", "tool_call_id": call_id, "content": tool_result}

    logger.warning(f"Responses API agent hit max iterations ({settings.agent_max_iterations})")
    yield {
        "type": "error",
        "detail": f"Agent exceeded {settings.agent_max_iterations} iterations.",
    }


async def run_agent(
    db: AsyncSession,
    user_id: str,
    user_message: str,
    conversation_history: list[dict],
    api_key: str | None = None,
    core_memories_text: str | None = None,
    model: str | None = None,
    is_guest: bool = False,
) -> AsyncGenerator[dict, None]:
    """
    Run the agent loop for a single user message.

    This is an async generator that yields events as they happen. The caller
    (the chat endpoint) consumes these events and forwards them to the frontend
    via SSE.

    Event types yielded:
      - {"type": "token", "content": str}          — a streaming text token
      - {"type": "tool_call_start", "id": str, "name": str, "arguments": str}
      - {"type": "tool_call_result", "id": str, "name": str, "result": str}
      - {"type": "tool_call_error", "id": str, "name": str, "error": str}
      - {"type": "assistant_message", "content": str, "tool_calls": list | None}
            — full assistant message to persist to DB (emitted before each iteration ends)
      - {"type": "tool_message", "tool_call_id": str, "content": str}
            — full tool result message to persist
      - {"type": "done"}                            — agent finished
      - {"type": "error", "detail": str}            — unrecoverable error

    The caller is responsible for persisting messages to the database.

    Args:
        db: Database session (passed to tools that need it)
        user_id: Current user (for tenant isolation in tools)
        user_message: The user's new message
        conversation_history: Prior messages in OpenAI format
        api_key: User's API key (from BYOK), None to use system default
    """
    # Build the initial message list. System prompt (+ injected memories) first,
    # then history, then the new user message.
    system_prompt = AGENT_SYSTEM_PROMPT
    if core_memories_text:
        system_prompt = f"{AGENT_SYSTEM_PROMPT}\n\n---\n\n{core_memories_text}"

    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    all_schemas = get_tool_schemas()
    tool_schemas = (
        [t for t in all_schemas if t["function"]["name"] in GUEST_ALLOWED_TOOLS]
        if is_guest
        else all_schemas
    )
    resolved_model = "gpt-5-nano" if is_guest else (model or settings.chat_model)
    resolved_api_key = api_key or settings.openai_api_key

    # Dispatch to the Responses API loop for models that require it
    if resolved_model in RESPONSES_API_MODELS:
        input_messages = _to_responses_input(messages)
        responses_tools = _to_responses_tools(tool_schemas) if model_supports_tools(resolved_model) else []
        async for event in _run_responses_agent(
            db, user_id, input_messages, responses_tools, resolved_api_key, resolved_model, is_guest
        ):
            yield event
        return

    # Build tool context — passed to every tool execution
    ctx = ToolContext(user_id=user_id, db=db, is_guest=is_guest)

    for iteration in range(settings.agent_max_iterations):
        logger.info(f"Agent iteration {iteration + 1}/{settings.agent_max_iterations}")

        try:
            is_ollama = resolved_model.startswith("ollama/")
            response = await acompletion(
                model=resolved_model,
                messages=messages,
                tools=tool_schemas if model_supports_tools(resolved_model) else None,
                api_key="" if is_ollama else resolved_api_key,
                api_base=normalize_ollama_url(resolved_api_key) if is_ollama else None,
                max_tokens=1500,
                stream=True,
            )
        except Exception as e:
            logger.error(f"LLM call failed: {e}", exc_info=True)
            yield {"type": "error", "detail": f"LLM error: {str(e)}"}
            return

        # Accumulators for this iteration
        accumulated_text = ""
        accumulated_tool_calls: dict[int, dict] = {}
        # Keyed by index because tool calls arrive as deltas with an index field.

        async for chunk in response:
            if chunk is None:
                break
            delta = chunk.choices[0].delta

            # Handle text content — stream it to the frontend as it arrives
            if delta.content:
                accumulated_text += delta.content
                yield {"type": "token", "content": delta.content}

            # Handle tool call deltas — accumulate them
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index

                    # First chunk for this tool call — initialize the accumulator
                    if idx not in accumulated_tool_calls:
                        accumulated_tool_calls[idx] = {
                            "id": tc_delta.id or "",
                            "type": "function",
                            "function": {
                                "name": (tc_delta.function.name
                                         if tc_delta.function else "") or "",
                                "arguments": "",
                            },
                        }

                    # Subsequent chunks may carry the ID, name, or arguments.
                    # The SSE protocol splits JSON arguments across multiple chunks,
                    # so we concatenate them.
                    if tc_delta.id:
                        accumulated_tool_calls[idx]["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            accumulated_tool_calls[idx]["function"]["name"] = (
                                tc_delta.function.name
                            )
                        if tc_delta.function.arguments:
                            accumulated_tool_calls[idx]["function"]["arguments"] += (
                                tc_delta.function.arguments
                            )

        # Stream is done for this iteration. Now decide: is the agent finished,
        # or does it need to execute tools and loop again?

        # Empty-completion guard: no text and no tool calls = silent done
        if not accumulated_tool_calls and not accumulated_text.strip():
            if iteration == 0:
                # Retry once with a nudge message
                messages.append({
                    "role": "user",
                    "content": "Please summarize your findings and answer my question.",
                })
                logger.warning("Empty completion on iteration %d — retrying with nudge", iteration)
                continue
            else:
                # Already retried — yield graceful fallback
                yield {
                    "type": "assistant_message",
                    "content": "I wasn't able to generate a response. Please try again.",
                    "tool_calls": None,
                }
                yield {"type": "done"}
                return

        if not accumulated_tool_calls:
            # No tool calls → this is the final response. Persist and return.
            yield {
                "type": "assistant_message",
                "content": accumulated_text,
                "tool_calls": None,
            }
            yield {"type": "done"}
            return

        # Otherwise, we have tool calls to execute.
        # First, persist the assistant message (with tool calls) so the chat
        # endpoint can save it to the DB.
        tool_calls_list = [accumulated_tool_calls[i] for i in sorted(accumulated_tool_calls)]

        yield {
            "type": "assistant_message",
            "content": accumulated_text,
            "tool_calls": tool_calls_list,
        }

        # Also append to the in-memory message list so the LLM sees it
        # on the next iteration.
        messages.append({
            "role": "assistant",
            "content": accumulated_text,
            "tool_calls": tool_calls_list,
        })

        # Execute each tool call and collect results
        for tc in tool_calls_list:
            tc_id = tc["id"]
            tc_name = tc["function"]["name"]
            tc_args_raw = tc["function"]["arguments"]

            # Signal tool call start to the frontend
            yield {
                "type": "tool_call_start",
                "id": tc_id,
                "name": tc_name,
                "arguments": tc_args_raw,
            }

            # Parse arguments (they come as a JSON string)
            try:
                tc_args = json.loads(tc_args_raw) if tc_args_raw else {}
            except json.JSONDecodeError as e:
                error_msg = f"Invalid tool arguments: {e}"
                logger.error(f"{tc_name}: {error_msg}")
                yield {
                    "type": "tool_call_error",
                    "id": tc_id,
                    "name": tc_name,
                    "error": error_msg,
                }
                # Append error as the tool result so the LLM can react
                tool_result = error_msg
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": tool_result,
                })
                yield {
                    "type": "tool_message",
                    "tool_call_id": tc_id,
                    "content": tool_result,
                }
                continue

            # Look up and execute the tool
            try:
                tool = get_tool(tc_name)
                tool_result = await tool.execute(ctx, tc_args)
                yield {
                    "type": "tool_call_result",
                    "id": tc_id,
                    "name": tc_name,
                    "result": tool_result,
                }
            except KeyError:
                tool_result = f"Error: Unknown tool '{tc_name}'"
                yield {
                    "type": "tool_call_error",
                    "id": tc_id,
                    "name": tc_name,
                    "error": tool_result,
                }
            except Exception as e:
                logger.error(f"Tool {tc_name} failed: {e}", exc_info=True)
                tool_result = f"Error: {str(e)}"
                yield {
                    "type": "tool_call_error",
                    "id": tc_id,
                    "name": tc_name,
                    "error": tool_result,
                }

            # Append tool result to messages for the next LLM iteration
            messages.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": tool_result,
            })

            # Signal the tool result to persist
            yield {
                "type": "tool_message",
                "tool_call_id": tc_id,
                "content": tool_result,
            }

    # If we hit max iterations, the agent is stuck in a loop
    logger.warning(f"Agent hit max iterations ({settings.agent_max_iterations})")
    yield {
        "type": "error",
        "detail": f"Agent exceeded {settings.agent_max_iterations} iterations. "
                  "This usually means the task is too complex or the model is confused.",
    }