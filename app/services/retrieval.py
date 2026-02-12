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
) -> list[dict]:
    """
    Embed the query and find the most similar chunks via cosine similarity.

    Returns a list of dicts with 'content' and 'similarity' keys.
    """
    top_k = top_k or settings.retrieval_top_k

    # Embed the query
    embeddings = await generate_embeddings([query])
    query_embedding = embeddings[0]


    # pgvector cosine distance: <=> operator
    # Similarity = 1 - distance
    result = await db.execute(
        text("""
            SELECT content, 1 - (embedding <=> :embedding) AS similarity
            FROM chunks
            WHERE user_id = :user_id
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

    # log
    logger.info(f"Retrieved {len(rows)} chunks for query (top similarity: {rows[0].similarity:.3f})")

    return [{"content": row.content, "similarity": row.similarity} for row in rows]