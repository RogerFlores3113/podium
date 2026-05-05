"""Unit tests for app.services.llm.normalize_ollama_url (OLL-02).

Patch target rule: always patch `app.services.llm.os.path.exists`,
NOT the global `os.path.exists` — the module-level reference is what
the function under test reads.
"""
from unittest.mock import patch

from app.services.llm import normalize_ollama_url


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
