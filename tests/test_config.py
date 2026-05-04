"""Tests for model capability flags and provider detection."""

import os
import pytest
from unittest.mock import patch
from app.config import (
    AVAILABLE_MODELS,
    MODEL_CAPABILITIES,
    provider_for_model,
    model_supports_tools,
)


def test_available_models_have_required_fields():
    for model in AVAILABLE_MODELS:
        assert "id" in model
        assert "label" in model
        assert "provider" in model
        assert model["provider"] in ("openai", "anthropic", "ollama")


def test_provider_for_known_models():
    assert provider_for_model("gpt-5-nano") == "openai"
    assert provider_for_model("claude-sonnet-4-6") == "anthropic"
    assert provider_for_model("ollama/llama3.2") == "ollama"


def test_provider_for_unknown_openai_prefix():
    assert provider_for_model("gpt-3.5-turbo") == "openai"


def test_provider_for_unknown_anthropic_prefix():
    assert provider_for_model("claude-4-opus") == "anthropic"


def test_provider_for_ollama_prefix():
    assert provider_for_model("ollama/llama3.2") == "ollama"
    assert provider_for_model("ollama/mistral") == "ollama"


def test_model_supports_tools_defaults_true():
    assert model_supports_tools("gpt-5-nano") is True
    assert model_supports_tools("claude-sonnet-4-6") is True


def test_model_supports_tools_ollama_disabled():
    assert model_supports_tools("ollama/llama3.2") is False
    assert model_supports_tools("ollama/mistral") is False


def test_model_supports_tools_unknown_model():
    # Unknown models default to supporting tools
    assert model_supports_tools("some-future-model") is True


# MODEL-01: OpenAI roster
def test_roster_contains_only_approved_openai_models():
    ids = [m["id"] for m in AVAILABLE_MODELS]
    assert "gpt-5-nano" in ids
    assert "gpt-5.4-nano" in ids
    assert "gpt-4o" not in ids
    assert "gpt-4o-mini" not in ids


# MODEL-01/02: Anthropic roster
def test_roster_contains_approved_anthropic_models():
    ids = [m["id"] for m in AVAILABLE_MODELS]
    assert "claude-sonnet-4-6" in ids
    assert "claude-haiku-4-5" in ids
    assert "claude-3-5-haiku-20241022" not in ids
    assert "claude-3-5-sonnet-20241022" not in ids


# MODEL-04: Friendly labels with middle-dot separator
def test_all_roster_entries_have_friendly_labels():
    for m in AVAILABLE_MODELS:
        if m["provider"] != "ollama":
            assert "·" in m["label"], (
                f"Model {m['id']} label '{m['label']}' missing middle-dot separator"
            )


# MODEL-03: Ollama gating — exclude when URL unset
@pytest.mark.asyncio
async def test_list_models_excludes_ollama_when_url_unset():
    with patch("app.routers.chat.settings") as mock_settings:
        mock_settings.ollama_base_url = ""
        # Lazy import to avoid module-level DB engine creation at collection time
        from app.routers.chat import list_models
        result = await list_models()
    assert all(m["provider"] != "ollama" for m in result)


# MODEL-03: Ollama gating — include when URL set
@pytest.mark.asyncio
async def test_list_models_includes_ollama_when_url_set():
    with patch("app.routers.chat.settings") as mock_settings:
        mock_settings.ollama_base_url = "http://localhost:11434"
        from app.routers.chat import list_models
        result = await list_models()
    assert any(m["provider"] == "ollama" for m in result)
