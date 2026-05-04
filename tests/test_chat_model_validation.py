"""Tests for model validation gate on the chat stream endpoint (MODEL-03 / T-05-04)."""
import os
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_stream_rejects_disabled_ollama_model():
    """MODEL-03: Stream endpoint must 422 when Ollama model submitted but OLLAMA_BASE_URL unset."""
    with patch("app.routers.chat.settings") as mock_settings:
        mock_settings.ollama_base_url = ""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/chat/stream",
                json={"message": "hello", "model": "ollama/llama3.2"},
                headers={"Authorization": "Bearer test-token"},
            )
    assert response.status_code == 422, (
        f"Expected 422 for disabled Ollama model, got {response.status_code}"
    )
