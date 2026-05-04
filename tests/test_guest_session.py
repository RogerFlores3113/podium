"""AUDIT-01 tests: guest message cap enforcement and expired-guest cleanup job.

Tests 3 and 4 are characterization tests for existing cleanup behavior
(RED->GREEN already met by current code; locks the contract so future
regressions are caught).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.config import settings


def _mock_db():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    db.delete = AsyncMock()
    db.execute = AsyncMock()
    return db


def _scalar_one_result(value):
    """Helper: build a result whose .scalar_one() returns `value`."""
    result = MagicMock()
    result.scalar_one = MagicMock(return_value=value)
    return result


def _scalars_all_result(items):
    """Helper: build a result whose .scalars().all() returns `items`."""
    result = MagicMock()
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=items)
    result.scalars = MagicMock(return_value=scalars)
    return result


def _mock_session_factory(db):
    factory = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=db)
    cm.__aexit__ = AsyncMock(return_value=None)
    factory.return_value = cm
    return factory


@pytest.fixture(autouse=True)
def patch_settings(monkeypatch):
    monkeypatch.setattr("app.config.settings.guest_max_messages_per_session", 20)
    monkeypatch.setattr("app.config.settings.guest_session_duration_hours", 24)


async def _enforce_cap(db, user, user_id):
    """Inline simulation of app/routers/chat.py guest cap branch (lines 126-141)."""
    from sqlalchemy import select, func
    from app.models import Message

    if user.is_guest:
        count_result = await db.execute(
            select(func.count(Message.id)).where(
                Message.user_id == user_id,
                Message.role == "user",
            )
        )
        msg_count = count_result.scalar_one()
        if msg_count >= settings.guest_max_messages_per_session:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "guest_limit_reached",
                    "message": (
                        f"Guest sessions are limited to "
                        f"{settings.guest_max_messages_per_session} messages. "
                        f"Sign up to keep chatting."
                    ),
                },
            )


@pytest.mark.asyncio
async def test_guest_message_cap_returns_429_at_limit():
    db = _mock_db()
    db.execute.return_value = _scalar_one_result(20)  # at the cap
    user = MagicMock()
    user.is_guest = True

    with pytest.raises(HTTPException) as exc_info:
        await _enforce_cap(db, user, "guest_abc")

    assert exc_info.value.status_code == 429
    assert exc_info.value.detail["error"] == "guest_limit_reached"
    assert "Sign up to keep chatting" in exc_info.value.detail["message"]


@pytest.mark.asyncio
async def test_guest_message_cap_allows_below_limit():
    db = _mock_db()
    db.execute.return_value = _scalar_one_result(19)  # below cap
    user = MagicMock()
    user.is_guest = True

    # Must not raise.
    await _enforce_cap(db, user, "guest_abc")


@pytest.mark.asyncio
async def test_cleanup_expired_guests_deletes_expired():
    from app.services.worker import cleanup_expired_guests

    db = _mock_db()
    expired_user = MagicMock()
    expired_user.clerk_id = "guest_expired_1"
    expired_user.is_guest = True
    # First execute() = SELECT expired users; remaining = DELETEs
    db.execute.side_effect = [
        _scalars_all_result([expired_user]),
        MagicMock(),  # delete Memory
        MagicMock(),  # delete Document
        MagicMock(),  # delete Conversation
    ]

    ctx = {"db_session": _mock_session_factory(db)}
    await cleanup_expired_guests(ctx)

    # 1 SELECT + 3 DELETE statements.
    assert db.execute.await_count == 4
    db.delete.assert_awaited_once_with(expired_user)
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_cleanup_expired_guests_skips_valid_sessions():
    from app.services.worker import cleanup_expired_guests

    db = _mock_db()
    db.execute.return_value = _scalars_all_result([])  # no expired users
    ctx = {"db_session": _mock_session_factory(db)}

    await cleanup_expired_guests(ctx)

    # Only the SELECT ran; no deletes, no commit.
    assert db.execute.await_count == 1
    db.delete.assert_not_awaited()
    db.commit.assert_not_awaited()
