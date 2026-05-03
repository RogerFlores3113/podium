"""Tests for Redis pool reuse in document upload endpoint (WIRE-03)."""

import os
import pytest


def _read_documents_source() -> str:
    """Read app/routers/documents.py source directly to avoid triggering settings validation."""
    here = os.path.dirname(__file__)
    docs_path = os.path.join(here, "..", "app", "routers", "documents.py")
    with open(os.path.normpath(docs_path)) as f:
        return f.read()


def test_upload_document_does_not_call_create_pool():
    """upload_document must not call create_pool — pool must come from app.state (WIRE-03)."""
    source = _read_documents_source()
    assert "create_pool" not in source, (
        "upload_document must not call create_pool; use request.app.state.redis_pool instead"
    )


def test_upload_document_reads_pool_from_app_state():
    """upload_document must read redis_pool from request.app.state (WIRE-03)."""
    source = _read_documents_source()
    assert "request.app.state.redis_pool" in source, (
        "upload_document must use request.app.state.redis_pool, not create its own pool"
    )
