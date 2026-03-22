"""
Unit tests for LLMClientFactory.

Tests client creation for different model providers.
"""

import pytest
from unittest.mock import MagicMock, patch

from infrastructure.api.llm_client_factory import LLMClientFactory
from config import LLMConfig


class TestLLMClientFactory:
    """Test suite for LLMClientFactory."""

    @pytest.fixture
    def config(self) -> LLMConfig:
        """Create a test LLM config."""
        return LLMConfig()

    def test_create_ollama_client(self, config: LLMConfig):
        """Should create a ChatOllama client for Ollama models."""
        mock_ollama = MagicMock()
        with patch.dict(
            "infrastructure.api.llm_client_factory.LLMClientFactory.__init__.__globals__",
            {},
        ):
            pass

        factory = LLMClientFactory(model="Ollama/llama3.1", config=config)
        # Replace the mapping entry with a mock
        factory.model_mapping["Ollama"] = mock_ollama

        factory.create_client()

        mock_ollama.assert_called_once()
        call_kwargs = mock_ollama.call_args.kwargs
        assert call_kwargs["model"] == "llama3.1"
        assert "base_url" in call_kwargs

    def test_create_google_client(self, config: LLMConfig):
        """Should create a ChatGoogleGenerativeAI client for Google models."""
        mock_google = MagicMock()
        factory = LLMClientFactory(model="Google/gemini-pro", config=config)
        factory.model_mapping["Google"] = mock_google

        factory.create_client()

        mock_google.assert_called_once()
        call_kwargs = mock_google.call_args.kwargs
        assert call_kwargs["model"] == "gemini-pro"

    def test_create_mistral_client(self, config: LLMConfig):
        """Should create a ChatMistralAI client for Mistral models."""
        mock_mistral = MagicMock()
        factory = LLMClientFactory(model="Mistral/mistral-large", config=config)
        factory.model_mapping["Mistral"] = mock_mistral

        factory.create_client()

        mock_mistral.assert_called_once()
        call_kwargs = mock_mistral.call_args.kwargs
        assert call_kwargs["model"] == "mistral-large"

    def test_create_openrouter_client(self, config: LLMConfig):
        """Should create a ChatOpenAI client for OpenRouter models."""
        mock_openai = MagicMock()
        factory = LLMClientFactory(model="OpenRouter/gpt-4", config=config)
        factory.model_mapping["OpenRouter"] = mock_openai

        factory.create_client()

        mock_openai.assert_called_once()
        call_kwargs = mock_openai.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4"
        assert "api_key" in call_kwargs
        assert "base_url" in call_kwargs

    def test_invalid_model_raises_error(self, config: LLMConfig):
        """Should raise ValueError for unknown model category."""
        factory = LLMClientFactory(model="Unknown/some-model", config=config)

        with pytest.raises(ValueError, match="Invalid model name"):
            factory.create_client()

    def test_model_with_slashes_in_name(self, config: LLMConfig):
        """Should correctly parse model names with multiple slashes."""
        mock_openai = MagicMock()
        factory = LLMClientFactory(model="OpenRouter/org/model-name", config=config)
        factory.model_mapping["OpenRouter"] = mock_openai

        factory.create_client()

        call_kwargs = mock_openai.call_args.kwargs
        # Should split only on first slash
        assert call_kwargs["model"] == "org/model-name"
