import logging
from functools import lru_cache

import httpx
import jwt
from jwt import PyJWKClient
from fastapi import Request, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import User

logger = logging.getLogger(__name__)

# Cache the JWKS client — it fetches and caches Clerk's public keys
_jwks_client = None


def get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(settings.clerk_jwks_url)
    return _jwks_client


def verify_token(token: str) -> dict:
    """
    Verify a Clerk JWT and return its claims.

    Raises HTTPException if the token is invalid.
    """
    try:
        client = get_jwks_client()
        signing_key = client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={
                "verify_exp": True,
                "verify_aud": False,  # Clerk doesn't always set audience
            },
        )
        return claims
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user_id(request: Request) -> str:
    """
    FastAPI dependency that extracts and verifies the user ID from the JWT.

    Use this as a dependency in any route that needs authentication:
        @router.get("/")
        async def my_route(user_id: str = Depends(get_current_user_id)):
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header",
        )

    token = auth_header.split(" ", 1)[1]
    claims = verify_token(token)

    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing user ID")

    return user_id


async def get_or_create_user(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI dependency that returns the User object, creating it on first access.

    This is the "just-in-time provisioning" pattern — we don't require
    a separate registration step. The first time a Clerk user hits our API,
    we create their local record.
    """
    result = await db.execute(
        select(User).where(User.clerk_id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        user = User(clerk_id=user_id)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info(f"Created new user: {user_id}")

    return user