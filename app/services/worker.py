import logging
from datetime import datetime

from arq.connections import RedisSettings
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


async def extract_memories_job(
    ctx: dict,
    conversation_id: str,
    user_id: str,
):
    """
    Background job: extract memories from a completed conversation.

    Runs after a delay so if the user keeps chatting, later jobs supersede this one.
    The debounce check ensures only the most recent job actually does work.
    """
    from app.services.memory import extract_memories_from_conversation, persist_memories
    from app.models import Message
    from sqlalchemy import select, func
    from datetime import timedelta
    import uuid as _uuid

    db_session = ctx["db_session"]
    conv_uuid = _uuid.UUID(conversation_id)

    try:
        async with db_session() as db:
            # Debounce: if a newer message arrived, skip — another job will handle it
            cutoff = datetime.utcnow() - timedelta(seconds=settings.memory_extraction_delay)
            result = await db.execute(
                select(func.max(Message.created_at))
                .where(Message.conversation_id == conv_uuid)
            )
            last_message_at = result.scalar_one_or_none()

            if last_message_at is None:
                logger.info(f"No messages in conversation {conversation_id}, skipping")
                return

            if last_message_at > cutoff:
                logger.info(
                    f"Conversation {conversation_id} still active "
                    f"(last message {last_message_at}), skipping extraction"
                )
                return

            memories = await extract_memories_from_conversation(db, conv_uuid, user_id)
            saved = await persist_memories(db, user_id, conv_uuid, memories)
            logger.info(
                f"Memory extraction complete for {conversation_id}: {saved} memories saved"
            )
    except Exception as e:
        logger.error(
            f"Memory extraction failed for {conversation_id}: {e}", exc_info=True
        )


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

    functions = [process_document, extract_memories_job]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 5
    job_timeout = 300