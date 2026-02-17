import os
import uuid

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Document
from app.schemas import DocumentResponse
from app.services.ingestion import UPLOAD_DIR

router = APIRouter(prefix="/documents", tags=["documents"])

DEFAULT_USER_ID = "user_01"


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a PDF document for background ingestion."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    # Save file locally
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}.pdf")
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Create document record immediately
    doc = Document(
        user_id=DEFAULT_USER_ID,
        filename=file.filename,
        storage_path=file_path,
        status="processing",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Enqueue background processing
    redis_pool = await create_pool(
        RedisSettings.from_dsn(settings.redis_url)
    )
    await redis_pool.enqueue_job(
        "process_document",
        str(doc.id),
        file_path,
        file.filename,
        DEFAULT_USER_ID,
    )
    await redis_pool.close()

    return doc


@router.get("/", response_model=list[DocumentResponse])
async def list_documents(db: AsyncSession = Depends(get_db)):
    """List all uploaded documents."""
    result = await db.execute(
        select(Document)
        .where(Document.user_id == DEFAULT_USER_ID)
        .order_by(Document.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single document's status. Useful for polling after upload."""
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc