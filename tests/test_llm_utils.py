"""Unit tests for app.services.llm functions.

Patch target rule: always patch `app.services.llm.os.path.exists`,
NOT the global `os.path.exists` — the module-level reference is what
the function under test reads.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.llm import normalize_ollama_url, build_conversation_history


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(messages):
    """Return a mock AsyncSession whose execute returns the given message list."""
    db = MagicMock()
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=messages)
    execute_result = MagicMock()
    execute_result.scalars = MagicMock(return_value=scalars)
    db.execute = AsyncMock(return_value=execute_result)
    return db


def _msg(role, content="", tool_calls=None, tool_call_id=None):
    """Return a MagicMock mimicking a Message ORM object."""
    m = MagicMock()
    m.role = role
    m.content = content
    m.tool_calls = tool_calls  # list[dict] or None
    m.tool_call_id = tool_call_id
    return m


# ---------------------------------------------------------------------------
# CR-01: Second orphan pass — assistant messages with unmatched tool_calls
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_assistant_tool_call_without_tool_result_is_dropped():
    """CR-01: Assistant message whose tool_call_id has no matching tool result is dropped."""
    # Messages come back newest-first from the DB query
    messages = [
        _msg("assistant", "", tool_calls=[{"id": "call_orphan", "type": "function",
                                           "function": {"name": "web_search", "arguments": "{}"}}]),
        _msg("user", "search something"),
    ]
    db = _make_db(messages)
    history = await build_conversation_history(db, "conv-1", max_tokens=100_000)
    roles = [h["role"] for h in history]
    # The assistant tool_call message has no matching tool result — must be dropped
    assert "assistant" not in roles or all(
        not h.get("tool_calls") for h in history if h["role"] == "assistant"
    ), "Orphan assistant tool_call message must be dropped"


@pytest.mark.asyncio
async def test_assistant_tool_call_with_matching_tool_result_is_kept():
    """CR-01: Assistant message whose tool_call_id IS matched by a tool result is retained."""
    messages = [
        _msg("tool", "result text", tool_call_id="call_matched"),
        _msg("assistant", "", tool_calls=[{"id": "call_matched", "type": "function",
                                           "function": {"name": "web_search", "arguments": "{}"}}]),
        _msg("user", "search something"),
    ]
    db = _make_db(messages)
    history = await build_conversation_history(db, "conv-1", max_tokens=100_000)
    # The assistant message should be kept because its tool_call_id appears in tool results
    assistant_msgs = [h for h in history if h.get("role") == "assistant" and h.get("tool_calls")]
    assert len(assistant_msgs) == 1, "Matched assistant tool_call message must be kept"


@pytest.mark.asyncio
async def test_orphan_tool_message_is_still_dropped_by_first_pass():
    """Regression: tool message with no matching assistant is still dropped by the first pass."""
    messages = [
        _msg("tool", "orphan tool result", tool_call_id="call_gone"),
        _msg("user", "hello"),
    ]
    db = _make_db(messages)
    history = await build_conversation_history(db, "conv-1", max_tokens=100_000)
    tool_msgs = [h for h in history if h.get("role") == "tool"]
    assert len(tool_msgs) == 0, "Orphan tool message must be dropped by first pass"


@pytest.mark.asyncio
async def test_normal_messages_without_tool_calls_are_unaffected():
    """CR-01: Regular user/assistant messages without tool_calls pass through unchanged."""
    messages = [
        _msg("assistant", "Here is my answer."),
        _msg("user", "What is the capital?"),
    ]
    db = _make_db(messages)
    history = await build_conversation_history(db, "conv-1", max_tokens=100_000)
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"


def test_localhost_rewritten_to_host_docker_internal_in_docker():
    with patch("app.services.llm.os.path.exists", return_value=True):
        result = normalize_ollama_url("http://localhost:11434")
    assert result == "http://host.docker.internal:11434"


def test_127_0_0_1_rewritten_in_docker():
    with patch("app.services.llm.os.path.exists", return_value=True):
        result = normalize_ollama_url("http://127.0.0.1:11434")
    assert result == "http://host.docker.internal:11434"


def test_non_localhost_url_passes_through_unchanged():
    with patch("app.services.llm.os.path.exists", return_value=True):
        result = normalize_ollama_url("http://192.168.1.10:11434")
    assert result == "http://192.168.1.10:11434"


def test_url_unchanged_when_not_in_docker():
    with patch("app.services.llm.os.path.exists", return_value=False):
        result = normalize_ollama_url("http://localhost:11434")
    assert result == "http://localhost:11434"


def test_empty_string_returns_empty_string():
    # No patch needed — guard clause short-circuits before any os call.
    assert normalize_ollama_url("") == ""


def test_localhost_without_port_rewritten_in_docker():
    with patch("app.services.llm.os.path.exists", return_value=True):
        result = normalize_ollama_url("http://localhost")
    assert result == "http://host.docker.internal"
