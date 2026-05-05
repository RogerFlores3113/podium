"""Tests for model capability flags and provider detection."""

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


def test_provider_for_unknown_openai_prefix():
    assert provider_for_model("gpt-3.5-turbo") == "openai"


def test_provider_for_unknown_anthropic_prefix():
    assert provider_for_model("claude-4-opus") == "anthropic"


def test_provider_for_ollama_prefix():
    assert provider_for_model("ollama/llama3.2") == "ollama"
    assert provider_for_model("ollama/mistral") == "ollama"


def test_model_supports_tools_ollama_disabled():
    assert model_supports_tools("ollama/llama3.2") is False
    assert model_supports_tools("ollama/mistral") is False


def test_model_supports_tools_unknown_model():
    # Unknown models default to supporting tools
    assert model_supports_tools("some-future-model") is True


# MODEL-01 / MODEL-02: Roster correctness (Plan 05-01 RED → Plan 05-02 GREEN)

def test_roster_contains_only_approved_openai_models():
    """MODEL-01/02: Only gpt-5-nano and gpt-5.4-nano; no legacy gpt-4o* entries."""
    openai_ids = [m["id"] for m in AVAILABLE_MODELS if m["provider"] == "openai"]
    assert "gpt-5-nano" in openai_ids
    assert "gpt-5.4-nano" in openai_ids
    assert "gpt-4o-mini" not in openai_ids
    assert "gpt-4o" not in openai_ids


def test_roster_contains_approved_anthropic_models():
    """MODEL-01: claude-sonnet-4-6 and claude-haiku-4-5 present; no claude-3-5-* entries."""
    anthropic_ids = [m["id"] for m in AVAILABLE_MODELS if m["provider"] == "anthropic"]
    assert "claude-sonnet-4-6" in anthropic_ids
    assert "claude-haiku-4-5" in anthropic_ids
    assert "claude-3-5-haiku-20241022" not in anthropic_ids
    assert "claude-3-5-sonnet-20241022" not in anthropic_ids


def test_all_roster_entries_have_friendly_labels():
    """MODEL-01: All non-Ollama labels contain middle-dot (·) separator."""
    for m in AVAILABLE_MODELS:
        if m["provider"] != "ollama":
            assert "·" in m["label"], (
                f"Model {m['id']} label '{m['label']}' missing middle-dot separator"
            )


def test_settings_has_ollama_base_url():
    """MODEL-04: Settings exposes ollama_base_url defaulting to empty string."""
    from app.config import settings
    assert hasattr(settings, "ollama_base_url")
    assert settings.ollama_base_url == ""


@pytest.mark.asyncio
async def test_list_models_returns_only_non_ollama_models():
    """MODEL-04: list_models() returns only non-Ollama entries (Ollama roster lives at /ollama-models)."""
    from app.routers.chat import list_models
    result = await list_models()
    assert all(m["provider"] != "ollama" for m in result)
    assert len(result) > 0
