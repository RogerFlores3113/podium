"""Tests for agent helper functions."""

import pytest
from app.services.agent import (
    GUEST_ALLOWED_TOOLS,
    RESPONSES_API_MODELS,
    _to_responses_input,
    _to_responses_tools,
)
from app.tools import get_tool_schemas


def test_responses_api_models_contains_gpt5_nano():
    assert "gpt-5-nano" in RESPONSES_API_MODELS


def test_responses_api_models_contains_gpt_5_4_nano():
    """MODEL-02: gpt-5.4-nano must be in the Responses API dispatch set."""
    assert "gpt-5.4-nano" in RESPONSES_API_MODELS


def test_guest_model_lock_is_gpt5_nano():
    """MODEL-05: Guest model is always gpt-5-nano (locked in agent.py)."""
    assert "gpt-5-nano" in RESPONSES_API_MODELS


def test_to_responses_input_system_becomes_developer():
    messages = [{"role": "system", "content": "You are helpful."}]
    result = _to_responses_input(messages)
    assert result[0]["role"] == "developer"
    assert result[0]["content"][0]["type"] == "input_text"
    assert result[0]["content"][0]["text"] == "You are helpful."


def test_to_responses_input_user_message():
    messages = [{"role": "user", "content": "Hello!"}]
    result = _to_responses_input(messages)
    assert result[0]["role"] == "user"
    assert result[0]["content"][0]["type"] == "input_text"


def test_to_responses_input_assistant_text():
    messages = [{"role": "assistant", "content": "Hi there!"}]
    result = _to_responses_input(messages)
    assert result[0]["role"] == "assistant"
    assert result[0]["content"][0]["type"] == "output_text"


def test_to_responses_input_tool_call_and_result():
    messages = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "call_1", "type": "function", "function": {"name": "web_search", "arguments": '{"query":"test"}'}}
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "Search results here"},
    ]
    result = _to_responses_input(messages)
    assert result[0]["type"] == "function_call"
    assert result[0]["call_id"] == "call_1"
    assert result[0]["name"] == "web_search"
    assert result[1]["type"] == "function_call_output"
    assert result[1]["call_id"] == "call_1"
    assert result[1]["output"] == "Search results here"


# ---------------------------------------------------------------------------
# D-02: GUEST_ALLOWED_TOOLS and guest system prompt
# ---------------------------------------------------------------------------

def test_guest_allowed_tools_includes_python_executor():
    """D-02: Guest tool set must include python_executor (sandbox is available to guests)."""
    assert "python_executor" in GUEST_ALLOWED_TOOLS


def test_guest_allowed_tools_excludes_memory_save():
    """D-02: memory_save must remain excluded from guest sessions."""
    assert "memory_save" not in GUEST_ALLOWED_TOOLS


def test_guest_tool_schemas_include_python_executor():
    """D-02: The filtered tool schemas for guests must contain python_executor."""
    all_schemas = get_tool_schemas()
    guest_schemas = [t for t in all_schemas if t["function"]["name"] in GUEST_ALLOWED_TOOLS]
    guest_tool_names = {t["function"]["name"] for t in guest_schemas}
    assert "python_executor" in guest_tool_names, (
        f"python_executor not in guest schemas: {guest_tool_names}"
    )


def test_guest_tool_schemas_exclude_memory_save():
    """D-02: The filtered tool schemas for guests must not contain memory_save."""
    all_schemas = get_tool_schemas()
    guest_schemas = [t for t in all_schemas if t["function"]["name"] in GUEST_ALLOWED_TOOLS]
    guest_tool_names = {t["function"]["name"] for t in guest_schemas}
    assert "memory_save" not in guest_tool_names


def test_to_responses_tools_format():
    chat_schemas = [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web",
                "parameters": {"type": "object", "properties": {"query": {"type": "string"}}},
            },
        }
    ]
    result = _to_responses_tools(chat_schemas)
    assert len(result) == 1
    assert result[0]["type"] == "function"
    assert result[0]["name"] == "web_search"
    assert result[0]["description"] == "Search the web"
    assert "parameters" in result[0]
    # No "function" wrapper — flat structure
    assert "function" not in result[0]
