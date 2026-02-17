import logging

from arq import create_pool
from arq.connections import RedisSettings, ArqRedis
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)


async def process_document(
    ctx: dict,
    document_id: str,
    file_path: str,
    filename: str,
    user_id: str,
):
    """
    Background job: run the full ingestion pipeline for a document.

    This is the same logic that was in the upload endpoint,
    but now runs in a separate worker process.
    """
    # Import here to avoid circular imports
    from app.services.ingestion import ingest_document_background

    db_session = ctx["db_session"]

    try:
        async with db_session() as db:
            await ingest_document_background(
                db, document_id, file_path, filename, user_id
            )
        logger.info(f"Document processed successfully: {filename} ({document_id})")
    except Exception as e:
        logger.error(f"Document processing failed: {document_id} — {e}", exc_info=True)
        # Mark document as failed
        async with db_session() as db:
            from app.models import Document
            from sqlalchemy import select

            result = await db.execute(
                select(Document).where(Document.id == document_id)
            )
            doc = result.scalar_one_or_none()
            if doc:
                doc.status = "failed"
                await db.commit()


async def startup(ctx: dict):
    """Called when the worker starts. Set up shared resources."""
    engine = create_async_engine(settings.database_url, echo=False)
    ctx["db_session"] = async_sessionmaker(engine, expire_on_commit=False)
    logger.info("Worker started")


async def shutdown(ctx: dict):
    """Called when the worker stops. Clean up."""
    logger.info("Worker shutting down")


class WorkerSettings:
    """arq worker configuration."""

    functions = [process_document]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 5
    job_timeout = 300  # 5 minutes max per document