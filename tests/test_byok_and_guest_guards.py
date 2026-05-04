"""Tests for BYOK enforcement, guest tool filtering, and guest model forcing."""

import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException

from app.services.llm import resolve_api_key
from app.services.agent import GUEST_ALLOWED_TOOLS, get_tool_schemas


def _make_user(is_guest: bool) -> MagicMock:
    u = MagicMock()
    u.is_guest = is_guest
    u.clerk_id = "guest_abc" if is_guest else "user_clerk_123"
    return u


# --- resolve_api_key ---

def test_guest_always_uses_system_key(monkeypatch):
    monkeypatch.setattr("app.services.llm.settings.openai_api_key", "sk-system-key")
    guest = _make_user(is_guest=True)
    result = resolve_api_key(guest, user_key=None)
    assert result == "sk-system-key"


def test_guest_ignores_any_byok_key(monkeypatch):
    monkeypatch.setattr("app.services.llm.settings.openai_api_key", "sk-system-key")
    guest = _make_user(is_guest=True)
    result = resolve_api_key(guest, user_key="sk-user-key")
    assert result == "sk-system-key"


def test_authenticated_user_with_byok_uses_their_key(monkeypatch):
    monkeypatch.setattr("app.services.llm.settings.openai_api_key", "sk-system-key")
    user = _make_user(is_guest=False)
    result = resolve_api_key(user, user_key="sk-user-byok-key")
    assert result == "sk-user-byok-key"


def test_authenticated_user_without_byok_raises_402():
    user = _make_user(is_guest=False)
    with pytest.raises(HTTPException) as exc_info:
        resolve_api_key(user, user_key=None)
    assert exc_info.value.status_code == 402
    assert exc_info.value.detail["error"] == "byok_required"


def test_ollama_provider_bypasses_byok_check():
    """MODEL-03: Ollama uses local endpoint, not an API key — no BYOK required."""
    user = _make_user(is_guest=False)
    result = resolve_api_key(user, user_key=None, provider="ollama")
    assert result == ""


# --- guest tool filtering ---

def test_guest_allowed_tools_excludes_python_executor():
    assert "python_executor" not in GUEST_ALLOWED_TOOLS


def test_guest_allowed_tools_includes_expected_tools():
    assert GUEST_ALLOWED_TOOLS == {"document_search", "memory_search", "web_search", "url_reader"}


def test_tool_filter_for_guest_removes_python_executor():
    all_schemas = get_tool_schemas()
    all_names = {t["function"]["name"] for t in all_schemas}
    assert "python_executor" in all_names

    guest_schemas = [t for t in all_schemas if t["function"]["name"] in GUEST_ALLOWED_TOOLS]
    guest_names = {t["function"]["name"] for t in guest_schemas}
    assert "python_executor" not in guest_names
    assert guest_names == GUEST_ALLOWED_TOOLS


# --- CR-04: provider-aware BYOK 402 message ---

def test_byok_402_message_uses_anthropic_label_for_anthropic_provider():
    user = _make_user(is_guest=False)
    with pytest.raises(HTTPException) as exc_info:
        resolve_api_key(user, user_key=None, provider="anthropic")
    assert exc_info.value.status_code == 402
    assert exc_info.value.detail["error"] == "byok_required"
    assert "Anthropic" in exc_info.value.detail["message"]
    assert "OpenAI" not in exc_info.value.detail["message"]


def test_byok_402_message_uses_openai_label_for_openai_provider():
    user = _make_user(is_guest=False)
    with pytest.raises(HTTPException) as exc_info:
        resolve_api_key(user, user_key=None, provider="openai")
    assert exc_info.value.status_code == 402
    assert exc_info.value.detail["error"] == "byok_required"
    assert "OpenAI" in exc_info.value.detail["message"]


# --- CR-02: WebSearchTool BadRequestError must not echo user query ---

@pytest.mark.asyncio
async def test_web_search_bad_request_does_not_echo_query(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.tools.web_search import WebSearchTool

    tool = WebSearchTool()
    ctx = MagicMock()

    from tavily.errors import BadRequestError

    with patch("app.tools.web_search.AsyncTavilyClient") as mock_client_cls, \
         patch("app.tools.web_search.settings") as mock_settings:
        mock_settings.tavily_api_key = "test-key"
        instance = MagicMock()
        instance.search = AsyncMock(side_effect=BadRequestError("bad"))
        mock_client_cls.return_value = instance

        result = await tool.execute(ctx, {"query": "SENSITIVE_QUERY_TEXT_xyz"})

    assert "SENSITIVE_QUERY_TEXT_xyz" not in result
    assert "rephrasing" in result
