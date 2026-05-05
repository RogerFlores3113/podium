"""Tests for conversation management endpoints (DELETE and PATCH).

Requirements: CONV-01, POLISH-05
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.routers.chat import delete_conversation, update_conversation
from app.models import Conversation, User
from app.schemas import ConversationUpdate


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


# ---------------------------------------------------------------------------
# PATCH /{conversation_id} tests (POLISH-05)
# ---------------------------------------------------------------------------

def _mock_db_for_patch(conversation_value):
    """Return a mocked AsyncSession for PATCH tests.

    scalar_one_or_none returns the given conversation (or None).
    commit and refresh are async no-ops.
    """
    db = MagicMock()
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = conversation_value
    db.execute = AsyncMock(return_value=scalar_result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


def _conversation(conv_id=None, user_id="user_clerk_123"):
    """Return a MagicMock shaped like a Conversation."""
    conv = MagicMock(spec=Conversation)
    conv.id = conv_id or uuid.uuid4()
    conv.user_id = user_id
    conv.title = "Original title"
    return conv


@pytest.mark.asyncio
async def test_update_conversation_happy_path():
    """PATCH with a valid title updates the conversation title and returns the record."""
    conv_id = uuid.uuid4()
    user = _user()
    conv = _conversation(conv_id=conv_id, user_id=user.clerk_id)

    db = _mock_db_for_patch(conv)
    body = ConversationUpdate(title="New name")

    result = await update_conversation(conv_id, body, user, db)

    # Title should be mutated on the model
    assert conv.title == "New name"
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(conv)
    # The endpoint returns the conversation object (response_model serialises it)
    assert result is conv


@pytest.mark.asyncio
async def test_update_conversation_not_found_raises_404():
    """PATCH on a nonexistent conversation_id returns 404."""
    conv_id = uuid.uuid4()
    user = _user()

    db = _mock_db_for_patch(None)
    body = ConversationUpdate(title="New name")

    with pytest.raises(HTTPException) as exc_info:
        await update_conversation(conv_id, body, user, db)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Conversation not found"
    db.commit.assert_not_awaited()
    db.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_conversation_other_user_returns_404():
    """PATCH on a conversation owned by a different user returns 404.

    The WHERE clause includes user_id == clerk_id; the DB returns None,
    so the endpoint raises 404 — preventing IDOR (T-13-03).
    """
    conv_id = uuid.uuid4()
    requester = _user(clerk_id="different_clerk_456")

    # DB returns None because ownership filter excludes the row
    db = _mock_db_for_patch(None)
    body = ConversationUpdate(title="Stolen title")

    with pytest.raises(HTTPException) as exc_info:
        await update_conversation(conv_id, body, requester, db)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Conversation not found"
    db.commit.assert_not_awaited()
    db.refresh.assert_not_awaited()
