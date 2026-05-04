"""RED tests for DELETE /chat/{conversation_id} endpoint.

These tests WILL FAIL until Plan 03-02 adds `delete_conversation` to
app/routers/chat.py. The import error itself is the RED signal.

Requirements: CONV-01
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.routers.chat import delete_conversation  # ImportError/AttributeError until 03-02
from app.models import Conversation, User


def _mock_db_returning(value):
    """Return a mocked AsyncSession whose scalar_one_or_none() returns `value`."""
    db = MagicMock()
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = value
    db.execute = AsyncMock(return_value=scalar_result)
    db.delete = AsyncMock()
    db.commit = AsyncMock()
    return db


def _user(clerk_id="user_clerk_123"):
    """Return a MagicMock shaped like a User with the given clerk_id."""
    u = MagicMock(spec=User)
    u.clerk_id = clerk_id
    return u


@pytest.mark.asyncio
async def test_delete_conversation_happy_path():
    """Given a conversation owned by the requesting user, the endpoint
    deletes the row and returns {'detail': 'Conversation deleted'}."""
    conv_id = uuid.uuid4()
    user = _user()

    conv = MagicMock(spec=Conversation)
    conv.id = conv_id
    conv.user_id = user.clerk_id

    db = _mock_db_returning(conv)

    result = await delete_conversation(conv_id, user, db)

    db.delete.assert_awaited_once_with(conv)
    db.commit.assert_awaited_once()
    assert result == {"detail": "Conversation deleted"}


@pytest.mark.asyncio
async def test_delete_conversation_not_found_raises_404():
    """When the conversation does not exist, the endpoint raises HTTP 404.
    db.delete and db.commit must NOT be called."""
    conv_id = uuid.uuid4()
    user = _user()

    db = _mock_db_returning(None)  # SELECT returns nothing

    with pytest.raises(HTTPException) as exc_info:
        await delete_conversation(conv_id, user, db)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Conversation not found"
    db.delete.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_conversation_other_user_returns_404():
    """When the conversation belongs to a different user, the WHERE
    user_id == clerk_id filter in the SQL query means scalar_one_or_none()
    returns None — the handler raises 404 and does NOT call delete or commit.

    Using a different clerk_id on the user fixture makes the intent explicit:
    the ownership guard is enforced at the SQL layer, not in application code."""
    conv_id = uuid.uuid4()
    # This user is NOT the owner of the conversation
    requester = _user(clerk_id="different_clerk_456")

    # Simulate the DB returning None because the ownership filter excluded the row
    db = _mock_db_returning(None)

    with pytest.raises(HTTPException) as exc_info:
        await delete_conversation(conv_id, requester, db)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Conversation not found"
    db.delete.assert_not_awaited()
    db.commit.assert_not_awaited()
