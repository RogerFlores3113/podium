"""Tests for SSE delimiter, keepalive ping, and finally-commit behavior (WIRE-01, WIRE-02, WIRE-04)."""

import os
import pytest


def _read_chat_source() -> str:
    """Read app/routers/chat.py source directly to avoid triggering settings validation."""
    here = os.path.dirname(__file__)
    chat_path = os.path.join(here, "..", "app", "routers", "chat.py")
    with open(os.path.normpath(chat_path)) as f:
        return f.read()


def test_event_source_response_uses_lf_separator():
    """EventSourceResponse must be constructed with sep='\\n' (WIRE-01)."""
    source = _read_chat_source()
    assert 'sep="\\n"' in source or "sep='\\n'" in source, (
        "EventSourceResponse must pass sep='\\n' to override sse-starlette's default '\\r\\n'"
    )


def test_event_source_response_includes_ping_15():
    """EventSourceResponse must be constructed with ping=15 (WIRE-04)."""
    source = _read_chat_source()
    assert "ping=15" in source, (
        "EventSourceResponse must pass ping=15 to prevent AWS ALB 60s idle timeout from killing long tool calls"
    )


def test_event_generator_has_finally_db_commit():
    """event_generator() must call db.commit() in a finally block (WIRE-02)."""
    source = _read_chat_source()
    # Assert that "finally" appears in source and that db.commit is called inside it
    assert "finally:" in source, (
        "event_generator must have a finally block for disconnect safety (WIRE-02)"
    )
    # Verify commit follows finally (within reasonable proximity in source)
    finally_idx = source.index("finally:")
    post_finally = source[finally_idx:finally_idx + 100]
    assert "db.commit()" in post_finally, (
        "db.commit() must appear in the finally block body (WIRE-02)"
    )
