import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.limiter import limiter
from app.services.guest_auth import create_guest_user

router = APIRouter(prefix="/guest", tags=["guest"])
logger = logging.getLogger(__name__)


@router.post("/session")
@limiter.limit("5/hour")
async def create_guest_session(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Create an ephemeral guest session. No auth required.

    Returns a short-lived JWT the client stores in sessionStorage.
    Rate-limited to 5/hour per IP to prevent drive-by spam.
    """
    _, token = await create_guest_user(db)

    expires_at = datetime.now(timezone.utc) + timedelta(
        hours=settings.guest_session_duration_hours
    )
    return {
        "token": token,
        "expires_at": expires_at.isoformat(),
    }
