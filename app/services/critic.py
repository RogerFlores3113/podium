"""
Actor-critic self-critique pass (AGT-02, D-09-03).

Stateless module: takes a draft answer and returns a revised answer.
Called by agent.py; has no dependency on the agent loop.
"""
import logging

from litellm import acompletion

from app.config import settings

# Models that use the OpenAI Responses API instead of Chat Completions.
# Defined here because _actor_critic always falls back to memory_extraction_model
# for these models (acompletion does not support Responses API format).
# agent.py imports this constant back to avoid duplication.
RESPONSES_API_MODELS: frozenset[str] = frozenset({"gpt-5-nano", "gpt-5.4-nano"})

logger = logging.getLogger(__name__)


async def _actor_critic(
    initial_answer: str,
    messages: list[dict],
    model: str | None,
) -> str:
    """
    Single self-critique pass (AGT-02, D-09-03).

    Returns revised text if the model identifies improvements, or returns the
    original text if the critique response starts with 'LGTM' (case-insensitive).

    Always uses litellm acompletion regardless of the primary model path.
    Always uses settings.openai_api_key (system key) — critique is a system-side
    quality operation, not billed to the user's BYOK key (see RESEARCH.md Pitfall 5).
    Falls back to settings.memory_extraction_model when the primary model is a
    Responses API model (acompletion does not support Responses API format).
    """
    critique_model = model or settings.memory_extraction_model
    if critique_model in RESPONSES_API_MODELS:
        critique_model = settings.memory_extraction_model
    critique_api_key = settings.openai_api_key  # always system key

    critique_messages = list(messages) + [
        {"role": "assistant", "content": initial_answer},
        {
            "role": "user",
            "content": (
                "Please review your answer above. Is it complete, accurate, "
                "and directly useful to a recruiter? If yes, reply LGTM. "
                "If not, give a revised and improved answer."
            ),
        },
    ]
    response = await acompletion(
        model=critique_model,
        messages=critique_messages,
        api_key=critique_api_key,
        max_tokens=1500,
        stream=False,
    )
    revised = response.choices[0].message.content or ""
    if revised.strip().upper().startswith("LGTM"):
        return initial_answer
    return revised.strip() or initial_answer
