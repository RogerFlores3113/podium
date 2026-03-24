import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import get_or_create_user
from app.models import User, ApiKey
from app.schemas import ApiKeyCreate, ApiKeyResponse
from app.services.encryption import encrypt_api_key, clear_cached_key

router = APIRouter(prefix="/keys", tags=["api-keys"])

SUPPORTED_PROVIDERS = {"openai", "anthropic", "ollama"}


@router.post("/", response_model=ApiKeyResponse)
async def add_api_key(
    request: ApiKeyCreate,
    user: User = Depends(get_or_create_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Store an encrypted API key for a provider.

    If a key already exists for this provider, it's replaced.
    """
    if request.provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported provider. Must be one of: {SUPPORTED_PROVIDERS}",
        )

    # Deactivate existing key for this provider
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.user_id == user.id,
            ApiKey.provider == request.provider,
            ApiKey.is_active == True,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.is_active = False
        clear_cached_key(f"{user.clerk_id}:{request.provider}")

    # Encrypt and store new key
    encrypted = encrypt_api_key(request.api_key)
    key_hint = "..." + request.api_key[-4:]

    api_key = ApiKey(
        user_id=user.id,
        provider=request.provider,
        encrypted_key=encrypted,
        key_hint=key_hint,
        is_active=True,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    return ApiKeyResponse(
        id=api_key.id,
        provider=api_key.provider,
        key_hint=api_key.key_hint,
        is_active=api_key.is_active,
        created_at=api_key.created_at,
    )


@router.get("/", response_model=list[ApiKeyResponse])
async def list_api_keys(
    user: User = Depends(get_or_create_user),
    db: AsyncSession = Depends(get_db),
):
    """List all API keys for the current user (hints only, not actual keys)."""
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.user_id == user.id,
            ApiKey.is_active == True,
        )
    )
    return result.scalars().all()


@router.delete("/{key_id}")
async def delete_api_key(
    key_id: uuid.UUID,
    user: User = Depends(get_or_create_user),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate an API key."""
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.id == key_id,
            ApiKey.user_id == user.id,
        )
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    api_key.is_active = False
    clear_cached_key(f"{user.clerk_id}:{api_key.provider}")
    await db.commit()

    return {"detail": "API key deactivated"}