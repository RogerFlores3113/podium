"""Tests for model capability flags and provider detection."""

import pytest
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
    assert provider_for_model("gpt-4o-nano") == "openai"
    assert provider_for_model("gpt-4o-mini") == "openai"
    assert provider_for_model("gpt-4o") == "openai"
    assert provider_for_model("claude-3-5-haiku-20241022") == "anthropic"
    assert provider_for_model("claude-3-5-sonnet-20241022") == "anthropic"


def test_provider_for_unknown_openai_prefix():
    assert provider_for_model("gpt-3.5-turbo") == "openai"


def test_provider_for_unknown_anthropic_prefix():
    assert provider_for_model("claude-4-opus") == "anthropic"


def test_provider_for_ollama_prefix():
    assert provider_for_model("ollama/llama3.2") == "ollama"
    assert provider_for_model("ollama/mistral") == "ollama"


def test_model_supports_tools_defaults_true():
    assert model_supports_tools("gpt-4o-mini") is True
    assert model_supports_tools("gpt-4o") is True
    assert model_supports_tools("claude-3-5-sonnet-20241022") is True


def test_model_supports_tools_ollama_disabled():
    assert model_supports_tools("ollama/llama3.2") is False
    assert model_supports_tools("ollama/mistral") is False


def test_model_supports_tools_unknown_model():
    # Unknown models default to supporting tools
    assert model_supports_tools("some-future-model") is True
