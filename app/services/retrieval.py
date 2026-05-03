import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.ingestion import generate_embeddings

logger = logging.getLogger(__name__)


async def retrieve_relevant_chunks(
    db: AsyncSession,
    query: str,
    user_id: str,
    top_k: int | None = None,
    include_seed: bool = False,
) -> list[dict]:
    """
    Embed the query and find the most similar chunks via cosine similarity.

    Returns a list of dicts with 'content' and 'similarity' keys.
    When include_seed=True (guest users), also searches the shared demo corpus.
    """
    top_k = top_k or settings.retrieval_top_k

    embeddings = await generate_embeddings([query])
    query_embedding = embeddings[0]

    if include_seed:
        sql = text("""
            SELECT content, 1 - (embedding <=> :embedding) AS similarity
            FROM chunks
            WHERE user_id = :user_id OR user_id = :seed_user_id
            ORDER BY embedding <=> :embedding
            LIMIT :top_k
        """)
        params = {
            "embedding": str(query_embedding),
            "user_id": user_id,
            "seed_user_id": settings.seed_user_id,
            "top_k": top_k,
        }
    else:
        sql = text("""
            SELECT content, 1 - (embedding <=> :embedding) AS similarity
            FROM chunks
            WHERE user_id = :user_id
            ORDER BY embedding <=> :embedding
            LIMIT :top_k
        """)
        params = {
            "embedding": str(query_embedding),
            "user_id": user_id,
            "top_k": top_k,
        }

    result = await db.execute(sql, params)
    rows = result.fetchall()

    if rows:
        logger.info(f"Retrieved {len(rows)} chunks for query (top similarity: {rows[0].similarity:.3f})")
    else:
        logger.info("No chunks retrieved for query")

    return [{"content": row.content, "similarity": row.similarity} for row in rows]
