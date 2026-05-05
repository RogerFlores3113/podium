import uuid
import json
import logging
from sse_starlette.sse import EventSourceResponse

import httpx
import litellm
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Conversation, Message, User
from app.schemas import ChatRequest, ConversationResponse, ConversationListItemResponse, ConversationUpdate
from app.services.llm import build_conversation_history, get_user_api_key, normalize_ollama_url, resolve_api_key
from app.services.agent import run_agent
from app.services.memory import retrieve_core_memories, format_core_memories_for_prompt

from app.config import settings, AVAILABLE_MODELS, provider_for_model
from app.limiter import limiter
from app.auth import get_or_create_user

router = APIRouter(prefix="/chat", tags=["chat"])

logger = logging.getLogger(__name__)


@router.get("/models")
async def list_models():
    """Return non-Ollama models available for selection. Ollama models are fetched separately."""
    return AVAILABLE_MODELS


@router.get("/ollama-models")
async def list_ollama_models(
    user: User = Depends(get_or_create_user),
    db: AsyncSession = Depends(get_db),
):
    """Return models available on the user's configured Ollama server."""
    user_ollama_url = await get_user_api_key(db, user.clerk_id, "ollama")
    base_url = normalize_ollama_url(user_ollama_url or settings.ollama_base_url)
    if not base_url:
        return []
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{base_url.rstrip('/')}/api/tags")
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []
    models = [
        {
            "id": f"ollama/{m['name']}",
            "label": f"{m['name']} (local)",
            "provider": "ollama",
        }
        for m in data.get("models", [])
    ]
    return models


@router.get("/", response_model=list[ConversationListItemResponse])
async def list_conversations(
    user: User = Depends(get_or_create_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
):
    """Return the most recent conversations for the current user."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user.clerk_id)
        .order_by(Conversation.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    user: User = Depends(get_or_create_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a conversation with all messages."""
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.clerk_id,
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: uuid.UUID,
    user: User = Depends(get_or_create_user),
    db: AsyncSession = Depends(get_db),
):
    """Hard-delete a conversation. Cascades to messages via FK ondelete=CASCADE.

    Memory.source_conversation_id is set to NULL (FK ondelete=SET NULL),
    preserving extracted memories with provenance link severed.
    """
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.clerk_id,
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await db.delete(conversation)
    await db.commit()
    return {"detail": "Conversation deleted"}


@router.patch("/{conversation_id}", response_model=ConversationListItemResponse)
async def update_conversation(
    conversation_id: uuid.UUID,
    body: ConversationUpdate,
    user: User = Depends(get_or_create_user),
    db: AsyncSession = Depends(get_db),
):
    """Rename a conversation. Only the owning user can rename their own conversations."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.clerk_id,
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conversation.title = body.title
    await db.commit()
    await db.refresh(conversation)
    return conversation


@router.post("/stream")
@limiter.limit("5/minute")
async def chat_stream(
    request: Request,
    body: ChatRequest,
    user: User = Depends(get_or_create_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Send a message and get a streaming response from the agent.

    Event types:
      - conversation: sent first with the conversation_id
      - token: streaming LLM text
      - tool_call_start: agent is invoking a tool
      - tool_call_result: tool returned successfully
      - tool_call_error: tool failed
      - done: agent finished
      - error: unrecoverable failure
    """
    user_id = user.clerk_id

    # Validate model before any DB work (MODEL-03: fail fast on disabled Ollama models).
    # Skip validation for Ollama models — list_models() only returns non-Ollama models.
    if body.model and not body.model.startswith("ollama/"):
        active_model_ids = {m["id"] for m in await list_models()}
        if body.model not in active_model_ids:
            raise HTTPException(status_code=422, detail="Model not available")

    # Enforce guest message cap before doing any DB work
    if user.is_guest:
        count_result = await db.execute(
            select(func.count(Message.id)).where(
                Message.user_id == user_id,
                Message.role == "user",
            )
        )
        msg_count = count_result.scalar_one()
        if msg_count >= settings.guest_max_messages_per_session:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "guest_limit_reached",
                    "message": f"Guest sessions are limited to {settings.guest_max_messages_per_session} messages. Sign up to keep chatting.",
                },
            )

    if body.conversation_id:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == body.conversation_id,
                Conversation.user_id == user_id,
            )
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = Conversation(
            user_id=user_id,
            title=body.message[:100],
        )
        db.add(conversation)
        await db.flush()

    history = []
    if body.conversation_id:
        history = await build_conversation_history(
            db, conversation.id, settings.memory_max_tokens
        )

    user_message = Message(
        conversation_id=conversation.id,
        user_id=user_id,
        role="user",
        content=body.message,
    )
    db.add(user_message)
    await db.flush()

    provider = provider_for_model(body.model or settings.chat_model)
    user_api_key = await get_user_api_key(db, user_id, provider)
    resolved_api_key = resolve_api_key(user, user_api_key, provider=provider)

    # Load core memories for prompt injection
    core_memories = await retrieve_core_memories(db, user_id)
    core_memories_text = format_core_memories_for_prompt(core_memories)
    if core_memories_text:
        logger.info(f"Injecting {len(core_memories)} core memories into prompt")

    async def event_generator():
        yield {
            "event": "conversation",
            "data": json.dumps({"conversation_id": str(conversation.id)}),
        }

        try:
            async for agent_event in run_agent(
                db=db,
                user_id=user_id,
                user_message=body.message,
                conversation_history=history,
                api_key=resolved_api_key,
                core_memories_text=core_memories_text,
                model=body.model or settings.chat_model,
                is_guest=user.is_guest,
                effort=body.effort,
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

                    # Schedule memory extraction (debounced — later jobs supersede this one)
                    try:
                        redis_pool = request.app.state.redis_pool
                        await redis_pool.enqueue_job(
                            "extract_memories_job",
                            str(conversation.id),
                            user_id,
                            _job_id=f"extract:{conversation.id}",
                            _defer_by=settings.memory_extraction_delay,
                        )
                    except Exception as e:
                        logger.warning(f"Failed to schedule memory extraction: {e}")

                    yield {
                        "event": "done",
                        "data": json.dumps({
                            "conversation_id": str(conversation.id),
                        }),
                    }
                elif event_type == "error":
                    await db.commit()
                    yield {
                        "event": "error",
                        "data": json.dumps({"detail": agent_event["detail"]}),
                    }
        except litellm.AuthenticationError:
            provider = provider_for_model(body.model or "").title() or "provider"
            logger.warning(f"BYOK authentication failed for model {body.model}")
            await db.rollback()
            yield {
                "event": "error",
                "data": json.dumps({"detail": f"Invalid API key for {provider}. Update your key in Settings."}),
            }
        except Exception as e:
            logger.error(f"Chat stream failed: {e}", exc_info=True)
            await db.rollback()
            yield {
                "event": "error",
                "data": json.dumps({"detail": "An unexpected error occurred. Please try again."}),
            }
        finally:
            await db.commit()

    return EventSourceResponse(event_generator(), sep="\n", ping=15)
