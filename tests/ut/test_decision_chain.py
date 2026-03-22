"""
Unit tests for DecisionChain.

Tests the company enrichment decision logic with mocked LLM responses.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from infrastructure.services.enrich_leads_agent.chains.decision_chain import DecisionChain
from infrastructure.services.enrich_leads_agent.models.make_decision import MakeDecisionResult
from domain.entities.company import Company


class TestDecisionChain:
    """Test suite for DecisionChain."""

    @pytest.fixture
    def llm_client(self) -> MagicMock:
        """Create a mock LLM client."""
        return MagicMock()

    @pytest.fixture
    def chain(self, llm_client: MagicMock) -> DecisionChain:
        """Create a DecisionChain with a mock LLM client."""
        return DecisionChain(llm_client)

    @pytest.fixture
    def sample_company(self) -> Company:
        """Create a sample company for testing."""
        return Company(
            id="comp-123",
            name="Acme Corp",
            industry="Technology",
            location="Paris, France",
        )

    @pytest.mark.asyncio
    async def test_decide_enrichment_approved(
        self, chain: DecisionChain, llm_client: MagicMock, sample_company: Company
    ):
        """Should return True when LLM decides enrichment is needed."""
        decision = MakeDecisionResult(result=True)
        mock_structured = AsyncMock()
        mock_structured.ainvoke.return_value = decision.model_dump()
        llm_client.with_structured_output.return_value = mock_structured

        with patch("infrastructure.services.enrich_leads_agent.chains.decision_chain.ChatPromptTemplate") as mock_prompt:
            mock_prompt.from_messages.return_value.__or__ = MagicMock(return_value=mock_structured)
            result = await chain.decide_enrichment(sample_company)

        assert isinstance(result, MakeDecisionResult)
        assert result.result is True

    @pytest.mark.asyncio
    async def test_decide_enrichment_rejected(
        self, chain: DecisionChain, llm_client: MagicMock, sample_company: Company
    ):
        """Should return False when LLM decides no enrichment needed."""
        decision = MakeDecisionResult(result=False)
        mock_structured = AsyncMock()
        mock_structured.ainvoke.return_value = decision.model_dump()
        llm_client.with_structured_output.return_value = mock_structured

        with patch("infrastructure.services.enrich_leads_agent.chains.decision_chain.ChatPromptTemplate") as mock_prompt:
            mock_prompt.from_messages.return_value.__or__ = MagicMock(return_value=mock_structured)
            result = await chain.decide_enrichment(sample_company)

        assert isinstance(result, MakeDecisionResult)
        assert result.result is False

    @pytest.mark.asyncio
    async def test_decide_enrichment_error_defaults_to_true(
        self, chain: DecisionChain, llm_client: MagicMock, sample_company: Company
    ):
        """Should default to True (enrich) when LLM fails."""
        mock_structured = AsyncMock()
        mock_structured.ainvoke.side_effect = Exception("LLM unavailable")
        llm_client.with_structured_output.return_value = mock_structured

        with patch("infrastructure.services.enrich_leads_agent.chains.decision_chain.ChatPromptTemplate") as mock_prompt:
            mock_prompt.from_messages.return_value.__or__ = MagicMock(return_value=mock_structured)
            result = await chain.decide_enrichment(sample_company)

        assert isinstance(result, MakeDecisionResult)
        assert result.result is True
