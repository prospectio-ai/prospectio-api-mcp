"""
Unit tests for EnrichChain.

Tests the LLM-based enrichment chain methods with mocked LLM responses.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from infrastructure.services.enrich_leads_agent.chains.enrich_chain import EnrichChain
from infrastructure.services.enrich_leads_agent.models.company_info import CompanyInfo
from infrastructure.services.enrich_leads_agent.models.contact_info import (
    ContactInfo,
    ContactsList,
)
from infrastructure.services.enrich_leads_agent.models.contact_bio import ContactBio
from infrastructure.services.enrich_leads_agent.models.job_titles import JobTitles
from infrastructure.services.enrich_leads_agent.models.search_results_model import SearchResultModel
from domain.entities.profile import Profile


def _create_chain() -> EnrichChain:
    """Create an EnrichChain with a mock LLM client."""
    mock_llm = MagicMock()
    return EnrichChain(mock_llm)


class TestEnrichChainGetCompanyDescription:
    """Tests for get_company_description method."""

    @pytest.fixture
    def chain(self) -> EnrichChain:
        return _create_chain()

    @pytest.mark.asyncio
    async def test_get_company_description_success(self, chain: EnrichChain):
        """Should return a description string on success."""
        # The method creates self.chain internally as prompt_template | llm_client | StrOutputParser()
        # We need to mock the final chain.ainvoke
        mock_runnable = AsyncMock()
        mock_runnable.ainvoke.return_value = "  Acme Corp is a leading technology company.  "

        with patch("infrastructure.services.enrich_leads_agent.chains.enrich_chain.ChatPromptTemplate") as mock_pt, \
             patch("infrastructure.services.enrich_leads_agent.chains.enrich_chain.StrOutputParser") as mock_parser:
            # Make the pipe chain return our mock
            mock_pt.from_messages.return_value.__or__ = MagicMock(
                return_value=MagicMock(__or__=MagicMock(return_value=mock_runnable))
            )
            result = await chain.get_company_description("Acme Corp", ["Web page content"])

        assert result == "Acme Corp is a leading technology company."

    @pytest.mark.asyncio
    async def test_get_company_description_empty_web_content(self, chain: EnrichChain):
        """Should handle empty web content list."""
        mock_runnable = AsyncMock()
        mock_runnable.ainvoke.return_value = "No info found"

        with patch("infrastructure.services.enrich_leads_agent.chains.enrich_chain.ChatPromptTemplate") as mock_pt, \
             patch("infrastructure.services.enrich_leads_agent.chains.enrich_chain.StrOutputParser"):
            mock_pt.from_messages.return_value.__or__ = MagicMock(
                return_value=MagicMock(__or__=MagicMock(return_value=mock_runnable))
            )
            result = await chain.get_company_description("Unknown Corp", [])

        assert result == "No info found"

    @pytest.mark.asyncio
    async def test_get_company_description_error_returns_empty(self, chain: EnrichChain):
        """Should return empty string on error."""
        mock_runnable = AsyncMock()
        mock_runnable.ainvoke.side_effect = Exception("LLM error")

        with patch("infrastructure.services.enrich_leads_agent.chains.enrich_chain.ChatPromptTemplate") as mock_pt, \
             patch("infrastructure.services.enrich_leads_agent.chains.enrich_chain.StrOutputParser"):
            mock_pt.from_messages.return_value.__or__ = MagicMock(
                return_value=MagicMock(__or__=MagicMock(return_value=mock_runnable))
            )
            result = await chain.get_company_description("Acme", ["content"])

        assert result == ""


class TestEnrichChainExtractOtherInfo:
    """Tests for extract_other_info_from_description method."""

    @pytest.fixture
    def chain(self) -> EnrichChain:
        return _create_chain()

    @pytest.mark.asyncio
    async def test_extract_other_info_success(self, chain: EnrichChain):
        """Should return CompanyInfo on success."""
        expected = CompanyInfo(
            industry=["Technology", "AI"],
            compatibility="80",
            location=["Paris", "London"],
            size="200-500",
            revenue="50M",
        )
        mock_structured = AsyncMock()
        mock_structured.ainvoke.return_value = expected.model_dump()

        chain.llm_client.with_structured_output.return_value = mock_structured

        with patch("infrastructure.services.enrich_leads_agent.chains.enrich_chain.ChatPromptTemplate") as mock_pt:
            mock_pt.from_messages.return_value.__or__ = MagicMock(return_value=mock_structured)
            result = await chain.extract_other_info_from_description(["web content"])

        assert isinstance(result, CompanyInfo)
        assert result.industry == ["Technology", "AI"]

    @pytest.mark.asyncio
    async def test_extract_other_info_error_returns_defaults(self, chain: EnrichChain):
        """Should return default CompanyInfo on error."""
        mock_structured = AsyncMock()
        mock_structured.ainvoke.side_effect = Exception("Parse error")
        chain.llm_client.with_structured_output.return_value = mock_structured

        with patch("infrastructure.services.enrich_leads_agent.chains.enrich_chain.ChatPromptTemplate") as mock_pt:
            mock_pt.from_messages.return_value.__or__ = MagicMock(return_value=mock_structured)
            result = await chain.extract_other_info_from_description(["web content"])

        assert isinstance(result, CompanyInfo)
        assert result.industry == []
        assert result.compatibility == "0"


class TestEnrichChainExtractContacts:
    """Tests for extract_contacts_from_answer method."""

    @pytest.fixture
    def chain(self) -> EnrichChain:
        return _create_chain()

    @pytest.mark.asyncio
    async def test_extract_contacts_empty_answer_returns_empty(self, chain: EnrichChain):
        """Should return empty list for empty answer."""
        result = await chain.extract_contacts_from_answer("Acme", "")
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_contacts_whitespace_answer_returns_empty(self, chain: EnrichChain):
        """Should return empty list for whitespace-only answer."""
        result = await chain.extract_contacts_from_answer("Acme", "   ")
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_contacts_success(self, chain: EnrichChain):
        """Should return list of ContactInfo on success."""
        contacts_list = ContactsList(
            contacts=[
                ContactInfo(
                    name="Marie Dupont",
                    email=["marie@acme.com"],
                    title="CTO",
                    phone="+33612345678",
                    profile_url=["https://linkedin.com/in/marie"],
                ),
            ]
        )
        mock_structured = AsyncMock()
        mock_structured.ainvoke.return_value = contacts_list.model_dump()
        chain.llm_client.with_structured_output.return_value = mock_structured

        with patch("infrastructure.services.enrich_leads_agent.chains.enrich_chain.ChatPromptTemplate") as mock_pt:
            mock_pt.from_messages.return_value.__or__ = MagicMock(return_value=mock_structured)
            result = await chain.extract_contacts_from_answer("Acme", "Marie Dupont is the CTO...")

        assert len(result) == 1
        assert result[0].name == "Marie Dupont"

    @pytest.mark.asyncio
    async def test_extract_contacts_error_returns_empty(self, chain: EnrichChain):
        """Should return empty list on error."""
        mock_structured = AsyncMock()
        mock_structured.ainvoke.side_effect = Exception("LLM error")
        chain.llm_client.with_structured_output.return_value = mock_structured

        with patch("infrastructure.services.enrich_leads_agent.chains.enrich_chain.ChatPromptTemplate") as mock_pt:
            mock_pt.from_messages.return_value.__or__ = MagicMock(return_value=mock_structured)
            result = await chain.extract_contacts_from_answer("Acme", "Some answer text")

        assert result == []


class TestEnrichChainExtractJobTitles:
    """Tests for extract_interesting_job_titles_from_profile method."""

    @pytest.fixture
    def chain(self) -> EnrichChain:
        return _create_chain()

    @pytest.fixture
    def profile(self) -> Profile:
        """Create a test profile."""
        return Profile(
            job_title="AI Developer",
            location="Paris",
            bio="Expert in machine learning",
            work_experience=[],
        )

    @pytest.mark.asyncio
    async def test_extract_job_titles_success(self, chain: EnrichChain, profile: Profile):
        """Should return list of job titles on success."""
        job_titles = JobTitles(job_titles=["CTO", "VP Engineering", "Head of AI"])
        mock_structured = AsyncMock()
        mock_structured.ainvoke.return_value = job_titles.model_dump()
        chain.llm_client.with_structured_output.return_value = mock_structured

        with patch("infrastructure.services.enrich_leads_agent.chains.enrich_chain.ChatPromptTemplate") as mock_pt:
            mock_pt.from_messages.return_value.__or__ = MagicMock(return_value=mock_structured)
            result = await chain.extract_interesting_job_titles_from_profile(profile)

        assert result == ["CTO", "VP Engineering", "Head of AI"]

    @pytest.mark.asyncio
    async def test_extract_job_titles_error_returns_empty(self, chain: EnrichChain, profile: Profile):
        """Should return empty list on error."""
        mock_structured = AsyncMock()
        mock_structured.ainvoke.side_effect = Exception("LLM error")
        chain.llm_client.with_structured_output.return_value = mock_structured

        with patch("infrastructure.services.enrich_leads_agent.chains.enrich_chain.ChatPromptTemplate") as mock_pt:
            mock_pt.from_messages.return_value.__or__ = MagicMock(return_value=mock_structured)
            result = await chain.extract_interesting_job_titles_from_profile(profile)

        assert result == []


class TestEnrichChainExtractContactBio:
    """Tests for extract_contact_bio method."""

    @pytest.fixture
    def chain(self) -> EnrichChain:
        return _create_chain()

    @pytest.mark.asyncio
    async def test_extract_contact_bio_empty_search_results(self, chain: EnrichChain):
        """Should return None for empty search results."""
        result = await chain.extract_contact_bio("Marie", "CTO", "Acme", "")
        assert result is None

    @pytest.mark.asyncio
    async def test_extract_contact_bio_whitespace_search_results(self, chain: EnrichChain):
        """Should return None for whitespace-only search results."""
        result = await chain.extract_contact_bio("Marie", "CTO", "Acme", "   ")
        assert result is None

    @pytest.mark.asyncio
    async def test_extract_contact_bio_success(self, chain: EnrichChain):
        """Should return ContactBio on success."""
        bio = ContactBio(
            short_description="Experienced tech leader",
            full_bio="Marie Dupont has 15 years of experience in technology leadership...",
        )
        mock_structured = AsyncMock()
        mock_structured.ainvoke.return_value = bio.model_dump()
        chain.llm_client.with_structured_output.return_value = mock_structured

        with patch("infrastructure.services.enrich_leads_agent.chains.enrich_chain.ChatPromptTemplate") as mock_pt:
            mock_pt.from_messages.return_value.__or__ = MagicMock(return_value=mock_structured)
            result = await chain.extract_contact_bio(
                "Marie Dupont", "CTO", "Acme Corp", "Search results about Marie..."
            )

        assert isinstance(result, ContactBio)
        assert result.short_description == "Experienced tech leader"

    @pytest.mark.asyncio
    async def test_extract_contact_bio_error_returns_none(self, chain: EnrichChain):
        """Should return None on error."""
        mock_structured = AsyncMock()
        mock_structured.ainvoke.side_effect = Exception("LLM error")
        chain.llm_client.with_structured_output.return_value = mock_structured

        with patch("infrastructure.services.enrich_leads_agent.chains.enrich_chain.ChatPromptTemplate") as mock_pt:
            mock_pt.from_messages.return_value.__or__ = MagicMock(return_value=mock_structured)
            result = await chain.extract_contact_bio(
                "Marie", "CTO", "Acme", "Some search results"
            )

        assert result is None


class TestEnrichChainExtractContactFromWebSearch:
    """Tests for extract_contact_from_web_search method."""

    @pytest.fixture
    def chain(self) -> EnrichChain:
        return _create_chain()

    @pytest.mark.asyncio
    async def test_extract_contact_from_web_search_success(self, chain: EnrichChain):
        """Should return ContactInfo on success."""
        contact = ContactInfo(
            name="Jean Martin",
            email=["jean@acme.com"],
            title="VP Engineering",
            phone="+33612345678",
            profile_url=["https://linkedin.com/in/jean-martin"],
        )
        mock_structured = AsyncMock()
        mock_structured.ainvoke.return_value = contact.model_dump()
        chain.llm_client.with_structured_output.return_value = mock_structured

        web_search = SearchResultModel(
            title="Acme team page",
            url="https://acme.com/team",
            snippet="Jean Martin, VP Engineering at Acme",
        )

        with patch("infrastructure.services.enrich_leads_agent.chains.enrich_chain.ChatPromptTemplate") as mock_pt:
            mock_pt.from_messages.return_value.__or__ = MagicMock(return_value=mock_structured)
            result = await chain.extract_contact_from_web_search("Acme", web_search)

        assert isinstance(result, ContactInfo)
        assert result.name == "Jean Martin"

    @pytest.mark.asyncio
    async def test_extract_contact_from_web_search_error_returns_none(self, chain: EnrichChain):
        """Should return None on error."""
        mock_structured = AsyncMock()
        mock_structured.ainvoke.side_effect = Exception("LLM error")
        chain.llm_client.with_structured_output.return_value = mock_structured

        web_search = SearchResultModel(title="Page", url="https://x.com", snippet="snippet")

        with patch("infrastructure.services.enrich_leads_agent.chains.enrich_chain.ChatPromptTemplate") as mock_pt:
            mock_pt.from_messages.return_value.__or__ = MagicMock(return_value=mock_structured)
            result = await chain.extract_contact_from_web_search("Acme", web_search)

        assert result is None
