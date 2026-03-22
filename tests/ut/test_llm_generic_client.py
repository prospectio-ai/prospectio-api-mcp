"""
Tests for infrastructure/api/llm_generic_client.py - LLMGenericClient.
"""
from infrastructure.api.llm_generic_client import LLMGenericClient
from langchain_core.language_models.chat_models import BaseChatModel


class TestLLMGenericClient:
    """Test suite for LLMGenericClient."""

    def test_inherits_base_chat_model(self):
        """Should inherit from BaseChatModel."""
        assert issubclass(LLMGenericClient, BaseChatModel)

    def test_defines_init_with_model_and_temperature(self):
        """Should have __init__ that accepts model and temperature."""
        import inspect
        sig = inspect.signature(LLMGenericClient.__init__)
        params = list(sig.parameters.keys())
        assert "model" in params
        assert "temperature" in params

    def test_is_abstract_class(self):
        """Should be abstract (cannot be instantiated directly due to BaseChatModel ABCs)."""
        import pytest
        with pytest.raises(TypeError, match="abstract"):
            LLMGenericClient(model="test", temperature=0.5)
