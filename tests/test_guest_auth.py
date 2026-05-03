"""Tests for guest authentication: token creation, verification, and expiry."""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest

from app.services.guest_auth import create_guest_user, verify_guest_token

_SECRET = "test-secret-for-unit-tests-exactly-32b"
_ALGORITHM = "HS256"


@pytest.fixture(autouse=True)
def patch_secret(monkeypatch):
    monkeypatch.setattr("app.services.guest_auth.settings.guest_jwt_secret", _SECRET)
    monkeypatch.setattr("app.services.guest_auth.settings.guest_session_duration_hours", 24)
    monkeypatch.setattr("app.services.guest_auth.settings.guest_max_messages_per_session", 20)


# --- verify_guest_token ---

def test_verify_guest_token_accepts_valid_token():
    payload = {
        "sub": "guest_abc123",
        "is_guest": True,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
    }
    token = jwt.encode(payload, _SECRET, algorithm=_ALGORITHM)
    claims = verify_guest_token(token)
    assert claims["sub"] == "guest_abc123"
    assert claims["is_guest"] is True


def test_verify_guest_token_rejects_expired_token():
    payload = {
        "sub": "guest_abc123",
        "is_guest": True,
        "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
    }
    token = jwt.encode(payload, _SECRET, algorithm=_ALGORITHM)
    with pytest.raises(jwt.ExpiredSignatureError):
        verify_guest_token(token)


def test_verify_guest_token_rejects_wrong_secret():
    payload = {
        "sub": "guest_abc123",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    wrong_secret = "wrong-secret-that-is-long-enough-32b"
    token = jwt.encode(payload, wrong_secret, algorithm=_ALGORITHM)
    with pytest.raises(jwt.InvalidSignatureError):
        verify_guest_token(token)


def test_verify_guest_token_rejects_garbage():
    with pytest.raises(jwt.DecodeError):
        verify_guest_token("not.a.jwt")


# --- create_guest_user ---

def _mock_db():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_create_guest_user_returns_user_and_token():
    mock_db = _mock_db()
    user, token = await create_guest_user(mock_db)

    assert user.is_guest is True
    assert user.clerk_id.startswith("guest_")
    mock_db.add.assert_called_once_with(user)
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_guest_user_token_is_valid_jwt():
    user, token = await create_guest_user(_mock_db())
    claims = verify_guest_token(token)
    assert claims["sub"] == user.clerk_id
    assert claims["is_guest"] is True


@pytest.mark.asyncio
async def test_create_guest_user_token_expires_in_24h():
    before = time.time()
    _, token = await create_guest_user(_mock_db())
    after = time.time()

    claims = jwt.decode(token, _SECRET, algorithms=[_ALGORITHM])
    expected_duration = 24 * 3600
    actual_duration = claims["exp"] - claims["iat"]
    assert abs(actual_duration - expected_duration) < 5


# --- 503 when secret is missing ---

def test_verify_guest_token_raises_503_when_secret_missing(monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setattr("app.services.guest_auth.settings.guest_jwt_secret", "")
    with pytest.raises(HTTPException) as exc_info:
        verify_guest_token("any.token.value")
    assert exc_info.value.status_code == 503
