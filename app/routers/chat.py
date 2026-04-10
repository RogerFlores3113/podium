import uuid
import json
import logging
from sse_starlette.sse import EventSourceResponse

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Conversation, Message
from app.schemas import ChatRequest, ChatResponse, ConversationResponse
from app.services.retrieval import retrieve_relevant_chunks
from app.services.llm import (
    generate_response,
    generate_response_stream,
    build_conversation_history,
    get_user_api_key,
)
from app.services.agent import run_agent

from app.config import settings
from app.limiter import limiter

from app.auth import get_current_user_id 

router = APIRouter(prefix="/chat", tags=["chat"])

logger = logging.getLogger(__name__)


@limiter.limit("30/minute")
async def chat(
    request: Request, # slowapi needs the raw Request
    body: ChatRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Send a message and get a RAG-augmented response.

    If conversation_id is provided, continues that conversation.
    Otherwise, creates a new one.
    """
    # Get or create conversation
    if body.conversation_id:
        result = await db.execute(
            select(Conversation).where(Conversation.id == body.conversation_id)
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = Conversation(
            user_id=user_id,
            title=body.message[:100],  # Use first 100 chars as title
        )
        db.add(conversation)
        await db.flush()

    # Store user message
    user_message = Message(
        conversation_id=conversation.id,
        user_id=user_id,
        role="user",
        content=body.message,
    )
    db.add(user_message)
    await db.flush()

    # Retrieve relevant chunks
    chunks = await retrieve_relevant_chunks(db, body.message, user_id)

    # Build conversation history (skip for brand new conversations)
    history = []
    if body.conversation_id:
        history = await build_conversation_history(
            db, conversation.id, settings.memory_max_tokens
        )

    # get user api key
    user_api_key = await get_user_api_key(db, user_id, "openai")

    # Generate response
    response_text = await generate_response(
        body.message, chunks, history, api_key=user_api_key
    )

    # Store assistant message
    assistant_message = Message(
        conversation_id=conversation.id,
        user_id=user_id,
        role="assistant",
        content=response_text,
    )
    db.add(assistant_message)

    await db.commit()

    return ChatResponse(
        conversation_id=conversation.id,
        response=response_text,
        sources=[c["content"] for c in chunks],
    )


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a conversation with all messages."""
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
            )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.post("/stream")
async def chat_stream(
    request_obj: Request,
    request: ChatRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Send a message and get a streaming response from the agent.

    The agent may call tools (web search, document search, python executor)
    and stream its thinking, tool calls, and results back to the client
    via SSE events.

    Event types:
      - token: streaming LLM text
      - tool_call_start: agent is invoking a tool
      - tool_call_result: tool returned successfully
      - tool_call_error: tool failed
      - done: agent finished
      - error: unrecoverable failure
    """
    # Get or create conversation
    if request.conversation_id:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == request.conversation_id,
                Conversation.user_id == user_id,
            )
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = Conversation(
            user_id=user_id,
            title=request.message[:100],
        )
        db.add(conversation)
        await db.flush()

    # Store user message immediately
    user_message = Message(
        conversation_id=conversation.id,
        user_id=user_id,
        role="user",
        content=request.message,
    )
    db.add(user_message)
    await db.flush()

    # Build history (including prior tool calls if any)
    history = []
    if request.conversation_id:
        history = await build_conversation_history(
            db, conversation.id, settings.memory_max_tokens
        )

    # Resolve user's API key (BYOK)
    user_api_key = await get_user_api_key(db, user_id, "openai")

    async def event_generator():
        # Send conversation ID early so the frontend can track it
        yield {
            "event": "conversation",
            "data": json.dumps({"conversation_id": str(conversation.id)}),
        }

        try:
            async for agent_event in run_agent(
                db=db,
                user_id=user_id,
                user_message=request.message,
                conversation_history=history,
                api_key=user_api_key,
            ):
                event_type = agent_event["type"]

                if event_type == "token":
                    yield {
                        "event": "token",
                        "data": json.dumps({"token": agent_event["content"]}),
                    }
                elif event_type == "tool_call_start":
                    yield {
                        "event": "tool_call_start",
                        "data": json.dumps({
                            "id": agent_event["id"],
                            "name": agent_event["name"],
                            "arguments": agent_event["arguments"],
                        }),
                    }
                elif event_type == "tool_call_result":
                    yield {
                        "event": "tool_call_result",
                        "data": json.dumps({
                            "id": agent_event["id"],
                            "name": agent_event["name"],
                            "result": agent_event["result"],
                        }),
                    }
                elif event_type == "tool_call_error":
                    yield {
                        "event": "tool_call_error",
                        "data": json.dumps({
                            "id": agent_event["id"],
                            "name": agent_event["name"],
                            "error": agent_event["error"],
                        }),
                    }
                elif event_type == "assistant_message":
                    # Persist the assistant message to the database
                    assistant_msg = Message(
                        conversation_id=conversation.id,
                        user_id=user_id,
                        role="assistant",
                        content=agent_event["content"] or "",
                        tool_calls=agent_event["tool_calls"],
                    )
                    db.add(assistant_msg)
                    await db.flush()
                elif event_type == "tool_message":
                    # Persist the tool result message
                    tool_msg = Message(
                        conversation_id=conversation.id,
                        user_id=user_id,
                        role="tool",
                        content=agent_event["content"],
                        tool_call_id=agent_event["tool_call_id"],
                    )
                    db.add(tool_msg)
                    await db.flush()
                elif event_type == "done":
                    await db.commit()
                    yield {
                        "event": "done",
                        "data": json.dumps({
                            "conversation_id": str(conversation.id),
                        }),
                    }
                elif event_type == "error":
                    await db.commit()  # Still save any partial work
                    yield {
                        "event": "error",
                        "data": json.dumps({"detail": agent_event["detail"]}),
                    }
        except Exception as e:
            logger.error(f"Chat stream failed: {e}", exc_info=True)
            yield {
                "event": "error",
                "data": json.dumps({"detail": str(e)}),
            }

    return EventSourceResponse(event_generator())