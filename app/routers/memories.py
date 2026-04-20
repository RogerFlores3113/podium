import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import get_current_user_id
from app.models import Memory
from app.schemas import MemoryResponse, MemoryCreate, MemoryUpdate
from app.services.ingestion import generate_embeddings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memories", tags=["memories"])

VALID_CATEGORIES = {"fact", "preference", "context"}


@router.get("/", response_model=list[MemoryResponse])
async def list_memories(
    user_id: str = Depends(get_current_user_id),
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List all active memories for the current user, optionally filtered by category."""
    query = (
        select(Memory)
        .where(Memory.user_id == user_id, Memory.is_active == True)
        .order_by(Memory.updated_at.desc())
    )
    if category:
        if category not in VALID_CATEGORIES:
            raise HTTPException(status_code=400, detail="Invalid category")
        query = query.where(Memory.category == category)

    result = await db.execute(query)
    return result.scalars().all()


@router.post("/", response_model=MemoryResponse)
async def create_memory(
    request: MemoryCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Manually add a memory."""
    if request.category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid category")
    if not request.content.strip():
        raise HTTPException(status_code=400, detail="Content cannot be empty")

    embeddings = await generate_embeddings([request.content])
    memory = Memory(
        user_id=user_id,
        category=request.category,
        content=request.content.strip(),
        embedding=embeddings[0],
        edited_by_user=True,
    )
    db.add(memory)
    await db.commit()
    await db.refresh(memory)
    return memory


@router.put("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: uuid.UUID,
    request: MemoryUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Edit a memory's content. Re-embeds for updated semantic search."""
    result = await db.execute(
        select(Memory).where(
            Memory.id == memory_id,
            Memory.user_id == user_id,
        )
    )
    memory = result.scalar_one_or_none()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    if not request.content.strip():
        raise HTTPException(status_code=400, detail="Content cannot be empty")

    embeddings = await generate_embeddings([request.content])
    memory.content = request.content.strip()
    memory.embedding = embeddings[0]
    memory.edited_by_user = True
    await db.commit()
    await db.refresh(memory)
    return memory


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a memory (sets is_active = false)."""
    result = await db.execute(
        select(Memory).where(
            Memory.id == memory_id,
            Memory.user_id == user_id,
        )
    )
    memory = result.scalar_one_or_none()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    memory.is_active = False
    await db.commit()
    return {"detail": "Memory deactivated"}


@router.delete("/")
async def delete_all_memories(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Hard delete ALL of the user's memories. Irreversible."""
    result = await db.execute(
        sql_delete(Memory).where(Memory.user_id == user_id)
    )
    await db.commit()
    deleted = result.rowcount
    logger.warning(f"User {user_id} hard-deleted {deleted} memories")
    return {"detail": f"Deleted {deleted} memories"}
