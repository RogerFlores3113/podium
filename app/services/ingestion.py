import os
import uuid

import pymupdf
from litellm import aembedding
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Document, Chunk


UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def extract_text_from_pdf(file_path: str) -> tuple[str, int]:
    """Extract all text from a PDF. Returns (text, page_count)."""
    doc = pymupdf.open(file_path)
    text = ""
    for page in doc:
        text += page.get_text() + "\n"
    page_count = len(doc)
    doc.close()
    return text.strip(), page_count


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """
    Split text into overlapping chunks by character count.

    This is a naive implementation — it splits on character boundaries.
    A better approach (deferred) would split on token count or semantic
    boundaries (paragraphs, sentences). Good enough for v0.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():  # Skip empty chunks
            chunks.append(chunk.strip())
        start = end - overlap
    return chunks


async def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for a list of texts using litellm.

    litellm abstracts the provider — if you switch to Claude or a local
    model later, you change the model string and nothing else.
    """
    response = await aembedding(
        model=settings.embedding_model,
        input=texts,
        api_key=settings.openai_api_key,
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

    # 4. Embed (in batches to avoid API limits)
    batch_size = 100  # OpenAI allows up to 2048, but be conservative
    all_embeddings = []
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        embeddings = await generate_embeddings(batch)
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