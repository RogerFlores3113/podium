import uuid
import logging
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import User

logger = logging.getLogger(__name__)

_ALGORITHM = "HS256"


def _guest_secret() -> str:
    if not settings.guest_jwt_secret:
        raise HTTPException(
            status_code=503,
            detail="Guest sessions are not available — server misconfiguration.",
        )
    return settings.guest_jwt_secret


async def create_guest_user(db: AsyncSession) -> tuple[User, str]:
    """
    Create a new guest User and return it together with a signed JWT.

    The JWT is HS256, expires in guest_session_duration_hours, and contains
    {"sub": "guest_<uuid>", "is_guest": true}.
    """
    guest_clerk_id = f"guest_{uuid.uuid4()}"
    user = User(clerk_id=guest_clerk_id, is_guest=True)
    db.add(user)
    await db.commit()
    await db.refresh(user)

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=settings.guest_session_duration_hours)
    payload = {
        "sub": guest_clerk_id,
        "is_guest": True,
        "iat": now,
        "exp": expires_at,
    }
    token = jwt.encode(payload, _guest_secret(), algorithm=_ALGORITHM)
    logger.info(f"Created guest user: {guest_clerk_id}")
    return user, token


def verify_guest_token(token: str) -> dict:
    """
    Validate a guest HS256 JWT and return its claims.

    Raises jwt.InvalidTokenError on failure.
    """
    return jwt.decode(token, _guest_secret(), algorithms=[_ALGORITHM])
