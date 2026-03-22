"""
Tests for infrastructure/services/generate_message.py - GenerateMessageLLM service.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from domain.entities.contact import Contact
from domain.entities.company import Company
from domain.entities.profile import Profile
from domain.entities.prospect_message import ProspectMessage
from domain.ports.generate_message import GenerateMessagePort


class TestGenerateMessageLLM:
    """Test suite for GenerateMessageLLM service."""

    @pytest.fixture
    def mock_llm_chain(self):
        """Create a mock LLM chain."""
        chain = AsyncMock()
        chain.ainvoke.return_value = ProspectMessage(
            subject="Collaboration Opportunity",
            message="Hello, I'd like to discuss a potential collaboration.",
        )
        return chain

    @pytest.fixture
    def sample_profile(self):
        return Profile(job_title="Dev", location="Paris", bio="Bio")

    @pytest.fixture
    def sample_contact(self):
        return Contact(id="c1", name="Alice", email=["alice@co.com"])

    @pytest.fixture
    def sample_company(self):
        return Company(id="co1", name="TechCorp")

    @pytest.mark.asyncio
    async def test_get_message_returns_prospect_message(
        self,
        mock_llm_chain,
        sample_profile,
        sample_contact,
        sample_company,
    ):
        """Should return a ProspectMessage from LLM chain output."""
        with patch("infrastructure.services.generate_message.LLMConfig") as mock_config_cls, \
             patch("infrastructure.services.generate_message.LLMClientFactory") as mock_factory_cls, \
             patch("infrastructure.services.generate_message.PromptLoader") as mock_loader_cls:

            mock_config = MagicMock()
            mock_config.PROSPECTING_MODEL = "Ollama/llama3"
            mock_config_cls.return_value = mock_config

            mock_client = MagicMock()
            mock_client.with_structured_output.return_value = MagicMock()
            mock_factory_cls.return_value.create_client.return_value = mock_client

            mock_loader_cls.return_value.load_prompt.return_value = "Generate a message for {profile} {contact} {company}"

            from infrastructure.services.generate_message import GenerateMessageLLM

            # Patch the chain pipeline operator result
            mock_chain = AsyncMock()
            mock_chain.ainvoke.return_value = ProspectMessage(
                subject="Collaboration Opportunity",
                message="Hello, I'd like to discuss.",
            )
            with patch("infrastructure.services.generate_message.PromptTemplate") as mock_template_cls:
                mock_template_instance = MagicMock()
                mock_template_instance.__or__ = MagicMock(return_value=mock_chain)
                mock_template_cls.return_value = mock_template_instance

                service = GenerateMessageLLM()
                result = await service.get_message(sample_profile, sample_contact, sample_company)

            assert isinstance(result, ProspectMessage)
            assert result.subject == "Collaboration Opportunity"

    def test_implements_generate_message_port(self):
        """GenerateMessageLLM should implement GenerateMessagePort."""
        with patch("infrastructure.services.generate_message.LLMConfig") as mock_config_cls, \
             patch("infrastructure.services.generate_message.LLMClientFactory") as mock_factory_cls:

            mock_config = MagicMock()
            mock_config.PROSPECTING_MODEL = "Ollama/llama3"
            mock_config_cls.return_value = mock_config
            mock_factory_cls.return_value.create_client.return_value = MagicMock()

            from infrastructure.services.generate_message import GenerateMessageLLM

            service = GenerateMessageLLM()
            assert isinstance(service, GenerateMessagePort)
