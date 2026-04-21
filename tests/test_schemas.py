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
