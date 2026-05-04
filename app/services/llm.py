import json
import logging

from litellm import acompletion
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import HTTPException
from app.config import settings
from app.models import Message, User, ApiKey
from app.services.tokens import count_tokens
from app.services.encryption import (
    decrypt_api_key,
    get_cached_key, 
    set_cached_key,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a helpful AI assistant with access to the user's personal knowledge base.
Use the provided context to answer the user's question accurately.
If the context doesn't contain relevant information, say so honestly — don't make things up.
When referencing information from the context, be specific about what you found."""


async def build_conversation_history(
    db: AsyncSession,
    conversation_id,
    max_tokens: int,
) -> list[dict]:
    """
    Fetch recent messages for a conversation, fitting within a token budget.

    Handles user, assistant (with or without tool calls), and tool messages.
    Returns messages in OpenAI format, oldest first.
    """
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
    )
    messages = result.scalars().all()

    history: list[dict] = []
    token_count = 0

    for msg in messages:
        # Rough token estimate — include tool_calls JSON if present
        content_for_count = msg.content or ""
        if msg.tool_calls:
            content_for_count += json.dumps(msg.tool_calls)
        msg_tokens = count_tokens(content_for_count)

        if token_count + msg_tokens > max_tokens:
            break

        # Reconstruct the message in OpenAI format
        if msg.role == "tool":
            history.append({
                "role": "tool",
                "tool_call_id": msg.tool_call_id or "",
                "content": msg.content,
            })
        elif msg.role == "assistant" and msg.tool_calls:
            history.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": msg.tool_calls,
            })
        else:
            history.append({
                "role": msg.role,
                "content": msg.content,
            })

        token_count += msg_tokens

    history.reverse()

    logger.info(
        f"Conversation history: {len(history)} messages, ~{token_count} tokens"
    )
    return history


def build_context_string(chunks: list[dict], max_tokens: int) -> str:
    """
    Build a context string from retrieved chunks, fitting within a token budget.

    Chunks are assumed to be pre-sorted by relevance (most relevant first).
    """
    parts = []
    token_count = 0

    for chunk in chunks:
        chunk_str = f"[Relevance: {chunk['similarity']:.2f}]\n{chunk['content']}"
        chunk_tokens = count_tokens(chunk_str)
        if token_count + chunk_tokens > max_tokens:
            break
        parts.append(chunk_str)
        token_count += chunk_tokens

    logger.info(f"Context: {len(parts)}/{len(chunks)} chunks, ~{token_count} tokens")
    return "\n\n---\n\n".join(parts)


async def get_user_api_key(
    db: AsyncSession,
    clerk_id: str,
    provider: str,
) -> str | None:
    """
    Get the decrypted API key for a user and provider.

    Uses an in-memory cache to avoid calling KMS on every request.
    Falls back to the system key if the user hasn't provided one.
    """
    cache_key = f"{clerk_id}:{provider}"

    # Check cache first
    cached = get_cached_key(cache_key)
    if cached:
        return cached

    # Fetch from DB
    result = await db.execute(
        select(ApiKey)
        .join(User)
        .where(
            User.clerk_id == clerk_id,
            ApiKey.provider == provider,
            ApiKey.is_active == True,
        )
    )
    api_key_record = result.scalar_one_or_none()

    if not api_key_record:
        return None  # No user key — caller should fall back to system key

    # Decrypt and cache
    decrypted = decrypt_api_key(api_key_record.encrypted_key)
    set_cached_key(cache_key, decrypted)

    return decrypted


def resolve_api_key(user: User, user_key: str | None, provider: str = "") -> str:
    """
    Return the API key to use for a request.

    Guests always use the system key (cost-controlled via model + rate limits).
    Ollama uses a local endpoint — no API key required.
    Authenticated users must have a BYOK key; 402 if they don't.
    """
    if user.is_guest:
        return settings.openai_api_key
    if provider == "ollama":
        # For Ollama, the "key" stored in BYOK is the user's base URL.
        # Fall back to the server-wide OLLAMA_BASE_URL if no user URL is saved.
        return user_key or settings.ollama_base_url or ""
    if not user_key:
        provider_label = {
            "anthropic": "Anthropic API key",
            "openai": "OpenAI API key",
        }.get(provider, "API key")
        raise HTTPException(
            status_code=402,
            detail={
                "error": "byok_required",
                "message": f"Add your {provider_label} in Settings to chat. Or sign out and try Podium as a guest.",
            },
        )
    return user_key
