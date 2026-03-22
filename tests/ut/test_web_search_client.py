"""
Unit tests for WebSearchClient.

Tests the web search client including helper methods and search functionality
with mocked external API calls.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from infrastructure.services.enrich_leads_agent.tools.web_search_client import (
    WebSearchClient,
)
from infrastructure.services.enrich_leads_agent.models.web_search_models import (
    WebSearchResult,
    WebSearchSource,
)
from config import LLMConfig, WebSearchConfig


def _create_client() -> WebSearchClient:
    """Create a WebSearchClient with mocked ChatOpenAI so no real API is needed."""
    WebSearchClient._semaphore = None
    with patch("infrastructure.services.enrich_leads_agent.tools.web_search_client.ChatOpenAI"):
        return WebSearchClient(LLMConfig(), WebSearchConfig())


class TestWebSearchClientExtractSources:
    """Tests for _extract_sources_from_response method."""

    @pytest.fixture
    def client(self) -> WebSearchClient:
        return _create_client()

    def test_no_response_metadata(self, client: WebSearchClient):
        """Should return empty list when response has no response_metadata."""
        response = MagicMock(spec=[])  # No attributes at all
        result = client._extract_sources_from_response(response)
        assert result == []

    def test_empty_metadata(self, client: WebSearchClient):
        """Should return empty list when metadata has no citations or annotations."""
        response = MagicMock()
        response.response_metadata = {}
        result = client._extract_sources_from_response(response)
        assert result == []

    def test_perplexity_citations_format(self, client: WebSearchClient):
        """Should extract sources from Perplexity citations format (list of URLs)."""
        response = MagicMock()
        response.response_metadata = {
            "citations": [
                "https://example.com/page1",
                "https://example.com/page2",
            ]
        }
        result = client._extract_sources_from_response(response)

        assert len(result) == 2
        assert isinstance(result[0], WebSearchSource)
        assert result[0].title == "Source 1"
        assert result[0].url == "https://example.com/page1"
        assert result[1].title == "Source 2"
        assert result[1].url == "https://example.com/page2"

    def test_perplexity_citations_skips_non_string(self, client: WebSearchClient):
        """Should skip non-string entries in citations."""
        response = MagicMock()
        response.response_metadata = {
            "citations": ["https://valid.com", 42, None, "https://also-valid.com"]
        }
        result = client._extract_sources_from_response(response)

        assert len(result) == 2
        assert result[0].url == "https://valid.com"
        assert result[1].url == "https://also-valid.com"

    def test_openrouter_annotations_format(self, client: WebSearchClient):
        """Should extract sources from OpenRouter annotations format."""
        response = MagicMock()
        response.response_metadata = {
            "annotations": [
                {
                    "type": "url_citation",
                    "url_citation": {
                        "title": "Company Page",
                        "url": "https://company.com",
                        "content": "Company details here",
                    },
                },
                {
                    "type": "other_type",
                    "data": "should be ignored",
                },
            ]
        }
        result = client._extract_sources_from_response(response)

        assert len(result) == 1
        assert result[0].title == "Company Page"
        assert result[0].url == "https://company.com"
        assert result[0].content == "Company details here"


class TestWebSearchClientSearch:
    """Tests for search method with mocked LLM calls."""

    @pytest.fixture
    def client(self) -> WebSearchClient:
        return _create_client()

    @pytest.mark.asyncio
    async def test_search_success(self, client: WebSearchClient):
        """Should return WebSearchResult on successful search."""
        mock_response = MagicMock()
        mock_response.content = "Acme Corp is a technology company based in Paris."
        mock_response.response_metadata = {}

        client.client.ainvoke = AsyncMock(return_value=mock_response)
        result = await client.search("What is Acme Corp?")

        assert isinstance(result, WebSearchResult)
        assert result.answer == "Acme Corp is a technology company based in Paris."
        assert result.sources == []

    @pytest.mark.asyncio
    async def test_search_with_non_string_content(self, client: WebSearchClient):
        """Should handle non-string response content gracefully."""
        mock_response = MagicMock()
        mock_response.content = ["not", "a", "string"]
        mock_response.response_metadata = {}

        client.client.ainvoke = AsyncMock(return_value=mock_response)
        result = await client.search("test query")

        assert result.answer == ""

    @pytest.mark.asyncio
    async def test_search_generic_error_returns_empty_result(self, client: WebSearchClient):
        """Should return empty WebSearchResult on generic errors."""
        client.client.ainvoke = AsyncMock(side_effect=Exception("Connection timeout"))
        result = await client.search("test query")

        assert isinstance(result, WebSearchResult)
        assert result.answer == ""
        assert result.sources == []

    @pytest.mark.asyncio
    async def test_search_rate_limit_retry_then_success(self, client: WebSearchClient):
        """Should retry on rate limit errors and succeed."""
        mock_response = MagicMock()
        mock_response.content = "Success after retry"
        mock_response.response_metadata = {}

        call_count = 0
        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("429 Too Many Requests")
            return mock_response

        client.client.ainvoke = AsyncMock(side_effect=side_effect)
        result = await client.search("test query")

        assert result.answer == "Success after retry"
        assert client._retry_count == 0

    @pytest.mark.asyncio
    async def test_search_rate_limit_max_retries_exceeded(self, client: WebSearchClient):
        """Should return empty result when rate limit retries are exhausted."""
        client._max_retries = 1

        client.client.ainvoke = AsyncMock(side_effect=Exception("rate limit exceeded"))
        result = await client.search("test query")

        assert isinstance(result, WebSearchResult)
        assert result.answer == ""


class TestWebSearchClientConvenienceMethods:
    """Tests for convenience search methods."""

    @pytest.fixture
    def client(self) -> WebSearchClient:
        return _create_client()

    @pytest.mark.asyncio
    async def test_search_with_site_filter(self, client: WebSearchClient):
        """Should append site filter to query."""
        expected_result = WebSearchResult(answer="Filtered result")

        with patch.object(client, "search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = expected_result
            result = await client.search_with_site_filter(
                query="company info",
                site="pappers.fr",
            )

        mock_search.assert_called_once()
        call_args = mock_search.call_args
        assert "site:pappers.fr" in call_args.kwargs["query"]
        assert result == expected_result

    @pytest.mark.asyncio
    async def test_search_company_contacts(self, client: WebSearchClient):
        """Should build a contact-focused query and call search."""
        expected_result = WebSearchResult(answer="Found 2 contacts")

        with patch.object(client, "search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = expected_result
            result = await client.search_company_contacts(
                company_name="Acme Corp",
                job_title="CTO",
            )

        mock_search.assert_called_once()
        call_args = mock_search.call_args
        assert "Acme Corp" in call_args.kwargs["query"]
        assert "CTO" in call_args.kwargs["query"]
        assert result == expected_result

    @pytest.mark.asyncio
    async def test_search_company_info(self, client: WebSearchClient):
        """Should build a company info query and call search."""
        expected_result = WebSearchResult(answer="Company details")

        with patch.object(client, "search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = expected_result
            result = await client.search_company_info(company_name="Acme Corp")

        mock_search.assert_called_once()
        call_args = mock_search.call_args
        assert "Acme Corp" in call_args.kwargs["query"]
        assert result == expected_result

    @pytest.mark.asyncio
    async def test_search_contact_bio(self, client: WebSearchClient):
        """Should build a bio-focused query and call search."""
        expected_result = WebSearchResult(answer="Bio info")

        with patch.object(client, "search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = expected_result
            result = await client.search_contact_bio(
                first_name="Marie",
                last_name="Dupont",
                position="CTO",
                company="Acme Corp",
            )

        mock_search.assert_called_once()
        call_args = mock_search.call_args
        assert "Marie" in call_args.kwargs["query"]
        assert "Dupont" in call_args.kwargs["query"]
        assert result == expected_result
