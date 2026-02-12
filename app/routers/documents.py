import os
import uuid

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Document
from app.schemas import DocumentResponse
from app.services.ingestion import ingest_document, UPLOAD_DIR

router = APIRouter(prefix="/documents", tags=["documents"])

# Hardcoded for now — replace with auth later
DEFAULT_USER_ID = "user_01"


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a PDF document for ingestion."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    # Save file locally
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}.pdf")
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Run ingestion pipeline
    try:
        doc = await ingest_document(db, file_path, file.filename, DEFAULT_USER_ID)
    except Exception as e:
        # Clean up file on failure
        os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

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