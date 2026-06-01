import os
import re
import uuid
import logging

import pymupdf
from litellm import aembedding
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Document, Chunk
from app.services.llm import get_user_api_key
from app.services.storage import get_local_path


UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_path: str) -> tuple[str, int]:
    """Extract all text from a PDF. Returns (text, page_count)."""
    doc = pymupdf.open(file_path)
    text = ""
    for page in doc:
        text += page.get_text() + "\n"
    page_count = len(doc)
    doc.close()
    return text.strip(), page_count


# Split a paragraph into sentences, keeping the terminator attached to each
# sentence. Trailing text without a terminator is captured as a final sentence.
_SENTENCE_RE = re.compile(r"\S.*?[.!?](?=\s|$)|\S.*?$", re.DOTALL)


def _split_sentences(paragraph: str) -> list[str]:
    """Split a paragraph into sentences (terminator kept on the sentence)."""
    return [m.group().strip() for m in _SENTENCE_RE.finditer(paragraph) if m.group().strip()]


def _hard_split(sentence: str, chunk_size: int) -> list[str]:
    """Hard-split an oversize sentence on character count so chunking terminates."""
    return [sentence[i : i + chunk_size] for i in range(0, len(sentence), chunk_size)]


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """
    Split text into overlapping chunks on sentence/paragraph boundaries.

    Text is split into paragraphs (blank lines), then sentences. Sentences are
    greedily packed into chunks up to chunk_size characters; each new chunk is
    seeded with whole trailing sentences from the previous chunk totalling about
    `overlap` characters, so chunks overlap without cutting mid-sentence. A
    single sentence longer than chunk_size is hard-split on character count
    (the only case where a chunk is cut mid-sentence), guaranteeing termination.
    """
    # Flatten paragraphs into an ordered list of sentences.
    sentences: list[str] = []
    for paragraph in re.split(r"\n\s*\n", text):
        sentences.extend(_split_sentences(paragraph))

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0  # length of " ".join(current)

    def flush() -> list[str]:
        """Emit the current chunk and return the whole-sentence overlap seed."""
        if not current:
            return []
        chunks.append(" ".join(current))
        # Carry whole trailing sentences totalling ~overlap chars into next chunk.
        seed: list[str] = []
        seed_len = 0
        for sentence in reversed(current):
            added = len(sentence) + (1 if seed else 0)
            if seed and seed_len + added > overlap:
                break
            seed.insert(0, sentence)
            seed_len += added
        return seed

    for sentence in sentences:
        if len(sentence) > chunk_size:
            # Oversize sentence: flush what we have, then hard-split it. No
            # overlap is carried across a hard-split boundary.
            flush()
            chunks.extend(_hard_split(sentence, chunk_size))
            current, current_len = [], 0
            continue

        addition = len(sentence) + (1 if current else 0)
        if current and current_len + addition > chunk_size:
            current = flush()
            current_len = len(" ".join(current))
            addition = len(sentence) + (1 if current else 0)

        current.append(sentence)
        current_len += addition

    if current:
        chunks.append(" ".join(current))

    return [c.strip() for c in chunks if c.strip()]


async def generate_embeddings(
    texts: list[str], api_key: str | None = None
) -> list[list[float]]:
    """
    Generate embeddings for a list of texts using litellm.

    litellm abstracts the provider — if you switch to Claude or a local
    model later, you change the model string and nothing else.

    api_key: the user's OpenAI BYOK key when available; when None, the
    system key (settings.openai_api_key) is used.
    """
    response = await aembedding(
        model=settings.embedding_model,
        input=texts,
        api_key=api_key or settings.openai_api_key,
    )
    return [item["embedding"] for item in response.data]


async def ingest_document(
    db: AsyncSession,
    file_path: str,
    filename: str,
    user_id: str,
) -> Document:
    """
    Full ingestion pipeline: extract → chunk → embed → store.

    This is synchronous within the request for now. For large documents,
    you'd want to make this a background job (deferred to later).
    """
    # 1. Create document record
    doc = Document(
        user_id=user_id,
        filename=filename,
        storage_path=file_path,
        status="processing",
    )
    db.add(doc)
    await db.flush()  # Get the ID without committing

    # 2. Extract text
    text, page_count = extract_text_from_pdf(file_path)
    doc.page_count = page_count

    if not text:
        doc.status = "empty"
        await db.commit()
        return doc

    # 3. Chunk
    chunks = chunk_text(text, settings.chunk_size, settings.chunk_overlap)

    # Log
    logger.info(f"Ingesting document: {filename} ({page_count} pages, {len(chunks)} chunks)")

    # 4. Embed (in batches to avoid API limits)
    api_key = await get_user_api_key(db, user_id, "openai")
    batch_size = 100  # OpenAI allows up to 2048, but be conservative
    all_embeddings = []
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        embeddings = await generate_embeddings(batch, api_key=api_key)
        all_embeddings.extend(embeddings)

    # 5. Store chunks with embeddings
    for idx, (chunk_text_content, embedding) in enumerate(
        zip(chunks, all_embeddings)
    ):
        chunk = Chunk(
            document_id=doc.id,
            user_id=user_id,
            content=chunk_text_content,
            chunk_index=idx,
            embedding=embedding,
        )
        db.add(chunk)

    doc.status = "ready"
    await db.commit()
    await db.refresh(doc)
    return doc


async def ingest_document_background(
    db: AsyncSession,
    document_id: str,
    file_path: str,
    filename: str,
    user_id: str,
) -> None:
    """
    Background version of ingestion. The Document row already exists
    with status='processing'. This function does the heavy lifting.
    """
    from app.models import Document
    from sqlalchemy import select

    # Fetch the existing document record
    result = await db.execute(
        select(Document).where(Document.id == uuid.UUID(document_id))
    )
    doc = result.scalar_one()


    # Extract text — need a local file for pymupdf
    local_path = get_local_path(file_path)
    try:
        text, page_count = extract_text_from_pdf(local_path)
    finally:
        # Clean up temp file if it was downloaded from S3
        import os
        if local_path != file_path and os.path.exists(local_path):
            os.remove(local_path)

    doc.page_count = page_count

    # Chunk
    chunks = chunk_text(text, settings.chunk_size, settings.chunk_overlap)
    logger.info(
        f"Ingesting document: {filename} ({page_count} pages, {len(chunks)} chunks)"
    )

    # Embed in batches
    api_key = await get_user_api_key(db, user_id, "openai")
    batch_size = 100
    all_embeddings = []
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        embeddings = await generate_embeddings(batch, api_key=api_key)
        all_embeddings.extend(embeddings)

    # Store chunks
    for idx, (chunk_text_content, embedding) in enumerate(
        zip(chunks, all_embeddings)
    ):
        chunk = Chunk(
            document_id=doc.id,
            user_id=user_id,
            content=chunk_text_content,
            chunk_index=idx,
            embedding=embedding,
        )
        db.add(chunk)

    doc.status = "ready"
    await db.commit()
