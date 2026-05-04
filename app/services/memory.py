import json
import logging
import uuid
from datetime import datetime

from litellm import acompletion
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Memory, Message
from app.services.ingestion import generate_embeddings

logger = logging.getLogger(__name__)


EXTRACTION_PROMPT = """You are a memory extraction system. Given a conversation between \
a user and an AI assistant, extract durable, useful facts about the user that would help \
in future conversations.

Output ONLY a JSON array of memory objects. Each object has:
- category: "fact" (something objectively true about the user), "preference" (something \
they like/dislike/prefer), or "context" (ongoing situations, projects, or plans)
- content: A concise first-person statement about the user, starting with "User ". \
Be specific. Avoid duplicating information that is already generic knowledge.

Rules:
- ONLY extract information explicitly stated by the user. Do not infer.
- Skip ephemeral information (what they asked about today, specific questions).
- Skip things the assistant said — only facts about the user.
- If nothing memorable was said, output an empty array [].
- Keep each memory to ONE sentence, under 150 characters.
- Prefer specificity: "User uses PostgreSQL 16 with pgvector" over "User uses a database".

Examples of GOOD memories:
- {"category": "fact", "content": "User works as a software engineer at a startup"}
- {"category": "preference", "content": "User prefers Python over JavaScript for backend work"}
- {"category": "context", "content": "User is building a personal AI assistant platform"}

Examples of BAD memories (DO NOT extract these):
- {"category": "fact", "content": "User asked about Python"}  (too ephemeral)
- {"category": "preference", "content": "User likes helpful answers"}  (generic/obvious)
- {"category": "context", "content": "The assistant searched the web"}  (about assistant, not user)

Output the JSON array and nothing else."""


async def extract_memories_from_conversation(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    user_id: str,
) -> list[dict]:
    """
    Extract memories from a conversation using an LLM.
    Returns the list of extracted memory dicts (before persistence).
    """
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    messages = result.scalars().all()

    if not messages:
        return []

    # Only include user/assistant text — tool calls are noisy and rarely
    # contain durable facts about the user
    formatted = []
    for msg in messages:
        if msg.role == "user":
            formatted.append(f"User: {msg.content}")
        elif msg.role == "assistant" and msg.content:
            formatted.append(f"Assistant: {msg.content}")

    if not formatted:
        return []

    conversation_text = "\n\n".join(formatted)

    try:
        response = await acompletion(
            model=settings.memory_extraction_model,
            messages=[
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": f"Conversation:\n\n{conversation_text}"},
            ],
            api_key=settings.openai_api_key,
            max_tokens=1000,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        # response_format="json_object" requires specific prompt wording on some models
        logger.warning(f"JSON mode failed, retrying without: {e}")
        response = await acompletion(
            model=settings.memory_extraction_model,
            messages=[
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": f"Conversation:\n\n{conversation_text}"},
            ],
            api_key=settings.openai_api_key,
            max_tokens=1000,
        )

    content = response.choices[0].message.content.strip()
    logger.info(f"Memory extraction response ({len(content)} chars): {content[:200]}")

    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            for key in ("memories", "items", "results"):
                if key in parsed and isinstance(parsed[key], list):
                    parsed = parsed[key]
                    break
            else:
                if not isinstance(parsed, list):
                    logger.warning(f"Unexpected extraction format: {parsed}")
                    return []

        if not isinstance(parsed, list):
            return []
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse extraction response: {e}")
        return []

    valid_memories = []
    for mem in parsed:
        if not isinstance(mem, dict):
            continue
        if "category" not in mem or "content" not in mem:
            continue
        if mem["category"] not in ("fact", "preference", "context"):
            continue
        if not isinstance(mem["content"], str) or not mem["content"].strip():
            continue
        valid_memories.append(mem)

    logger.info(
        f"Extracted {len(valid_memories)} valid memories from conversation {conversation_id}"
    )
    return valid_memories


async def persist_memories(
    db: AsyncSession,
    user_id: str,
    conversation_id: uuid.UUID | None,
    memories: list[dict],
) -> int:
    """
    Store extracted memories with embeddings.
    Returns the number of memories actually saved.
    """
    if not memories:
        return 0

    contents = [m["content"] for m in memories]
    embeddings = await generate_embeddings(contents)

    count = 0
    for mem_data, embedding in zip(memories, embeddings):
        memory = Memory(
            user_id=user_id,
            category=mem_data["category"],
            content=mem_data["content"],
            embedding=embedding,
            source_conversation_id=conversation_id,
        )
        db.add(memory)
        count += 1

    await db.commit()
    logger.info(f"Persisted {count} memories for user {user_id}")
    return count


async def retrieve_core_memories(
    db: AsyncSession,
    user_id: str,
    limit: int | None = None,
) -> list[Memory]:
    """
    Get facts and preferences for always-inject into the system prompt.
    Context memories are retrieved on-demand via the memory_search tool.
    """
    limit = limit or settings.memory_core_always_inject

    result = await db.execute(
        select(Memory)
        .where(
            Memory.user_id == user_id,
            Memory.is_active == True,
            Memory.category.in_(["fact", "preference"]),
        )
        .order_by(Memory.updated_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def search_memories(
    db: AsyncSession,
    user_id: str,
    query: str,
    top_k: int | None = None,
) -> list[dict]:
    """Semantic search over a user's memories. Used by the memory_search tool."""
    from sqlalchemy import text

    top_k = top_k or settings.memory_retrieval_top_k

    embeddings = await generate_embeddings([query])
    query_embedding = embeddings[0]

    result = await db.execute(
        text("""
            SELECT id, category, content, 1 - (embedding <=> :embedding) AS similarity
            FROM memories
            WHERE user_id = :user_id
              AND is_active = true
            ORDER BY embedding <=> :embedding
            LIMIT :top_k
        """),
        {
            "embedding": str(query_embedding),
            "user_id": user_id,
            "top_k": top_k,
        },
    )

    rows = result.fetchall()
    return [
        {
            "id": str(row.id),
            "category": row.category,
            "content": row.content,
            "similarity": float(row.similarity),
        }
        for row in rows
    ]


def format_core_memories_for_prompt(memories: list[Memory]) -> str:
    """Format core memories for injection into the system prompt."""
    if not memories:
        return ""

    by_category: dict[str, list[str]] = {"fact": [], "preference": []}
    for m in memories:
        if m.category in by_category:
            by_category[m.category].append(m.content)

    parts = []
    if by_category["fact"]:
        parts.append("Facts:\n" + "\n".join(f"- {c}" for c in by_category["fact"]))
    if by_category["preference"]:
        parts.append(
            "Preferences:\n" + "\n".join(f"- {c}" for c in by_category["preference"])
        )

    if not parts:
        return ""

    return "What you know about this user:\n\n" + "\n\n".join(parts)
