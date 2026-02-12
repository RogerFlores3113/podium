import logging
from litellm import acompletion

from app.config import settings


SYSTEM_PROMPT = """You are a helpful AI assistant with access to the user's personal knowledge base.
Use the provided context to answer the user's question accurately.
If the context doesn't contain relevant information, say so honestly — don't make things up.
When referencing information from the context, be specific about what you found."""
logger = logging.getLogger(__name__)


async def generate_response(
    query: str,
    context_chunks: list[dict],
    conversation_history: list[dict] | None = None,
) -> str:
    """
    Build a prompt with retrieved context and send to the LLM.

    conversation_history is a list of {"role": "user"|"assistant", "content": "..."}
    dicts. Deferred for now — we'll just use the current query.
    """
    # Build context string
    context = "\n\n---\n\n".join(
        [f"[Relevance: {c['similarity']:.2f}]\n{c['content']}" for c in context_chunks]
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Context from your knowledge base:\n\n{context}\n\n---\n\nQuestion: {query}",
        },
    ]

    response = await acompletion(
        model=settings.chat_model,
        messages=messages,
        api_key=settings.openai_api_key,
        max_tokens=1000,
    )

    return response.choices[0].message.content