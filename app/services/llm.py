import logging

from litellm import acompletion
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Message
from app.services.tokens import count_tokens

from collections.abc import AsyncGenerator

from litellm import acompletion

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

    Works backward from newest to oldest, stopping when we'd exceed the budget.
    This ensures the most recent context is always included.
    """
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
    )
    messages = result.scalars().all()

    history = []
    token_count = 0

    for msg in messages:
        msg_tokens = count_tokens(msg.content)
        if token_count + msg_tokens > max_tokens:
            break
        history.append({"role": msg.role, "content": msg.content})
        token_count += msg_tokens

    # Reverse so oldest is first (we built the list newest-first)
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


async def generate_response(
    query: str,
    context_chunks: list[dict],
    conversation_history: list[dict] | None = None,
) -> str:
    """Build a prompt with context + history and send to the LLM."""

    context = build_context_string(context_chunks, settings.context_max_tokens)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Add conversation history if present
    if conversation_history:
        messages.extend(conversation_history)

    # The current user message includes the retrieved context
    messages.append({
        "role": "user",
        "content": f"Context from your knowledge base:\n\n{context}\n\n---\n\nQuestion: {query}",
    })

    response = await acompletion(
        model=settings.chat_model,
        messages=messages,
        api_key=settings.openai_api_key,
        max_tokens=1000,
    )

    return response.choices[0].message.content

async def generate_response_stream(
    query: str,
    context_chunks: list[dict],
    conversation_history: list[dict] | None = None,
) -> AsyncGenerator[str, None]:
    """
    Same as generate_response, but yields tokens as they arrive.

    The caller is responsible for collecting the full text if needed
    (e.g., to save to the database).
    """
    context = build_context_string(context_chunks, settings.context_max_tokens)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if conversation_history:
        messages.extend(conversation_history)

    messages.append({
        "role": "user",
        "content": f"Context from your knowledge base:\n\n{context}\n\n---\n\nQuestion: {query}",
    })

    response = await acompletion(
        model=settings.chat_model,
        messages=messages,
        api_key=settings.openai_api_key,
        max_tokens=1000,
        stream=True,  # This is the only difference
    )

    async for chunk in response:
        content = chunk.choices[0].delta.content
        if content:
            yield content
