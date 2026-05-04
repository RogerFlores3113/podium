"""Tests for Pydantic request/response schemas."""

import uuid
import pytest
from app.schemas import ChatRequest


def test_chat_request_minimal():
    req = ChatRequest(message="hello")
    assert req.message == "hello"
    assert req.conversation_id is None
    assert req.model is None


def test_chat_request_with_model():
    req = ChatRequest(message="hello", model="gpt-4o")
    assert req.model == "gpt-4o"


def test_chat_request_with_conversation_id():
    cid = uuid.uuid4()
    req = ChatRequest(message="hello", conversation_id=cid)
    assert req.conversation_id == cid


def test_chat_request_model_defaults_none():
    req = ChatRequest(message="test")
    assert req.model is None


def test_chat_request_effort_defaults_to_balanced():
    """ChatRequest.effort must default to 'balanced' when not provided (AGT-04, D-09-04)."""
    req = ChatRequest(message="hello")
    assert req.effort == "balanced", "effort must default to 'balanced' for backward compatibility"


def test_chat_request_effort_accepts_valid_values():
    """ChatRequest.effort must accept 'fast', 'balanced', 'thorough' (AGT-04, D-09-04)."""
    for value in ("fast", "balanced", "thorough"):
        req = ChatRequest(message="hello", effort=value)
        assert req.effort == value


def test_chat_request_effort_rejects_invalid_values():
    """ChatRequest.effort must reject values outside the Literal enum (AGT-04, D-09-04)."""
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        ChatRequest(message="hello", effort="turbo")
