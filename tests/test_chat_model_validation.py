"""Tests for model validation gate on the chat stream endpoint (MODEL-03 / T-05-04)."""
import os
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.auth import get_or_create_user


def _mock_user():
    user = MagicMock()
    user.clerk_id = "test-user"
    user.is_guest = False
    return user


@pytest.mark.asyncio
async def test_stream_rejects_disabled_ollama_model():
    """MODEL-03: Stream endpoint must 422 when Ollama model submitted but OLLAMA_BASE_URL unset."""
    app.dependency_overrides[get_or_create_user] = lambda: _mock_user()
    try:
        with patch("app.routers.chat.settings") as mock_settings:
            mock_settings.ollama_base_url = ""
            mock_settings.guest_max_messages_per_session = 10
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/chat/stream",
                    json={"message": "hello", "model": "ollama/llama3.2"},
                )
    finally:
        app.dependency_overrides.pop(get_or_create_user, None)
    assert response.status_code == 422, (
        f"Expected 422 for disabled Ollama model, got {response.status_code}"
    )
