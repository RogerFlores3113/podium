"""Tests for agent helper functions."""

import pytest
from app.services.agent import (
    RESPONSES_API_MODELS,
    _to_responses_input,
    _to_responses_tools,
)


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
