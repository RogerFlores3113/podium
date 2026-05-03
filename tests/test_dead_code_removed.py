"""Tests for dead code removal from app/services/llm.py (QUAL-01)."""

import os


def _read_llm_source() -> str:
    """Read app/services/llm.py source directly to avoid triggering settings validation."""
    here = os.path.dirname(__file__)
    llm_path = os.path.join(here, "..", "app", "services", "llm.py")
    with open(os.path.normpath(llm_path)) as f:
        return f.read()


def test_generate_response_is_removed():
    """generate_response must not exist in llm.py — it is dead code with no callers (QUAL-01)."""
    source = _read_llm_source()
    # Look for the function definition, not just any reference
    assert "async def generate_response(" not in source, (
        "generate_response is dead code (no callers outside llm.py) and must be deleted"
    )


def test_generate_response_stream_is_removed():
    """generate_response_stream must not exist in llm.py — it is dead code with no callers (QUAL-01)."""
    source = _read_llm_source()
    # Look for the function definition, not just any reference
    assert "async def generate_response_stream(" not in source, (
        "generate_response_stream is dead code (no callers outside llm.py) and must be deleted"
    )
