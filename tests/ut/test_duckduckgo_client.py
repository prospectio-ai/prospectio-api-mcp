"""
Unit tests for DuckDuckGoClient.

Tests the LinkedIn profile URL discovery functionality using the
ddgs library with mocked responses.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from infrastructure.services.enrich_leads_agent.tools.duckduckgo_client import (
    DuckDuckGoClient,
    LinkedInSearchResult,
)
from config import DuckDuckGoConfig


class TestLinkedInSearchResult:
    """Tests for LinkedInSearchResult dataclass."""

    def test_default_values(self):
        """Test default values for success and error."""
        result = LinkedInSearchResult(urls=[], query="test")
        assert result.success is True
        assert result.error is None

    def test_error_state(self):
        """Test error state representation."""
        result = LinkedInSearchResult(
            urls=[],
            query="test",
            success=False,
            error="Connection failed",
        )
        assert result.success is False
        assert result.error == "Connection failed"


class TestDuckDuckGoClientExtractLinkedInUrls:
    """Tests for _extract_linkedin_urls method."""

    @pytest.fixture
    def client(self) -> DuckDuckGoClient:
        """Create client instance for testing."""
        config = DuckDuckGoConfig(
            DUCKDUCKGO_TIMEOUT=10.0,
            DUCKDUCKGO_MAX_RESULTS=5,
            DUCKDUCKGO_DELAY_BETWEEN_REQUESTS=0.1,
        )
        return DuckDuckGoClient(config=config)

    def test_extracts_single_linkedin_url(self, client: DuckDuckGoClient):
        """Test extraction of a single LinkedIn URL from results."""
        results = [
            {"href": "https://www.linkedin.com/in/john-doe", "title": "John Doe"}
        ]
        urls = client._extract_linkedin_urls(results)
        assert len(urls) == 1
        assert urls[0] == "https://www.linkedin.com/in/john-doe"

    def test_extracts_multiple_linkedin_urls(self, client: DuckDuckGoClient):
        """Test extraction of multiple LinkedIn URLs."""
        results = [
            {"href": "https://www.linkedin.com/in/john-doe", "title": "John Doe"},
            {"href": "https://linkedin.com/in/jane-smith", "title": "Jane Smith"},
            {"href": "https://fr.linkedin.com/in/pierre-dupont", "title": "Pierre"},
        ]
        urls = client._extract_linkedin_urls(results)
        assert len(urls) == 3
        assert "https://www.linkedin.com/in/john-doe" in urls
        assert "https://www.linkedin.com/in/jane-smith" in urls
        assert "https://www.linkedin.com/in/pierre-dupont" in urls

    def test_handles_duplicate_urls(self, client: DuckDuckGoClient):
        """Test deduplication of LinkedIn URLs by username."""
        results = [
            {"href": "https://www.linkedin.com/in/john-doe", "title": "John"},
            {"href": "https://linkedin.com/in/john-doe", "title": "John Doe"},
            {"href": "https://www.linkedin.com/in/JOHN-DOE", "title": "JOHN"},
        ]
        urls = client._extract_linkedin_urls(results)
        assert len(urls) == 1
        assert urls[0] == "https://www.linkedin.com/in/john-doe"

    def test_respects_max_results_limit(self, client: DuckDuckGoClient):
        """Test that extraction respects max results limit."""
        results = [
            {"href": f"https://linkedin.com/in/user-{i}", "title": f"User {i}"}
            for i in range(20)
        ]
        urls = client._extract_linkedin_urls(results)
        assert len(urls) == client.config.DUCKDUCKGO_MAX_RESULTS

    def test_returns_empty_list_when_no_linkedin_urls(self, client: DuckDuckGoClient):
        """Test returns empty list when no LinkedIn URLs in results."""
        results = [
            {"href": "https://example.com/profile", "title": "Profile"},
            {"href": "https://twitter.com/johndoe", "title": "Twitter"},
        ]
        urls = client._extract_linkedin_urls(results)
        assert urls == []

    def test_ignores_company_linkedin_urls(self, client: DuckDuckGoClient):
        """Test that company URLs are ignored, only /in/ profiles extracted."""
        results = [
            {"href": "https://linkedin.com/company/acme-corp", "title": "ACME"},
            {"href": "https://linkedin.com/in/john-doe", "title": "John"},
        ]
        urls = client._extract_linkedin_urls(results)
        assert len(urls) == 1
        assert urls[0] == "https://www.linkedin.com/in/john-doe"

    def test_handles_empty_results(self, client: DuckDuckGoClient):
        """Test graceful handling of empty results."""
        urls = client._extract_linkedin_urls([])
        assert urls == []

    def test_handles_missing_href(self, client: DuckDuckGoClient):
        """Test handling of results without href field."""
        results = [
            {"title": "No href"},
            {"href": "https://linkedin.com/in/valid-user", "title": "Valid"},
        ]
        urls = client._extract_linkedin_urls(results)
        assert len(urls) == 1
        assert urls[0] == "https://www.linkedin.com/in/valid-user"

    def test_uses_link_field_as_fallback(self, client: DuckDuckGoClient):
        """Test that 'link' field is used when 'href' is missing."""
        results = [
            {"link": "https://linkedin.com/in/from-link", "title": "From Link"},
        ]
        urls = client._extract_linkedin_urls(results)
        assert urls == ["https://www.linkedin.com/in/from-link"]


class TestDuckDuckGoClientSanitizeSearchTerm:
    """Tests for _sanitize_search_term method."""

    @pytest.fixture
    def client(self) -> DuckDuckGoClient:
        """Create client instance for testing."""
        return DuckDuckGoClient()

    def test_removes_quotes(self, client: DuckDuckGoClient):
        """Test removal of quote characters."""
        result = client._sanitize_search_term('John "The Best" Doe')
        assert '"' not in result

    def test_removes_newlines(self, client: DuckDuckGoClient):
        """Test removal of newline characters."""
        assert "John Doe" == client._sanitize_search_term("John\nDoe")

    def test_collapses_whitespace(self, client: DuckDuckGoClient):
        """Test collapsing of multiple whitespace."""
        assert client._sanitize_search_term("John    Doe") == "John Doe"

    def test_truncates_long_terms(self, client: DuckDuckGoClient):
        """Test truncation of overly long terms."""
        long_term = "x" * 300
        result = client._sanitize_search_term(long_term)
        assert len(result) == 200

    def test_handles_empty_string(self, client: DuckDuckGoClient):
        """Test handling of empty string."""
        assert client._sanitize_search_term("") == ""


class TestDuckDuckGoClientSearchLinkedInProfile:
    """Tests for search_linkedin_profile method."""

    @pytest.fixture
    def client(self) -> DuckDuckGoClient:
        """Create client instance for testing."""
        config = DuckDuckGoConfig(
            DUCKDUCKGO_TIMEOUT=10.0,
            DUCKDUCKGO_MAX_RESULTS=5,
            DUCKDUCKGO_DELAY_BETWEEN_REQUESTS=0.0,
        )
        return DuckDuckGoClient(config=config)

    @pytest.mark.asyncio
    async def test_successful_search_returns_urls(self, client: DuckDuckGoClient):
        """Test successful search returns LinkedIn URLs."""
        mock_results = [
            {"href": "https://linkedin.com/in/john-doe", "title": "John Doe"},
            {"href": "https://linkedin.com/in/johnny-doe", "title": "Johnny"},
        ]

        with patch.object(client, "_execute_search", return_value=mock_results):
            result = await client.search_linkedin_profile("John Doe", "ACME Corp")

        assert result.success is True
        assert len(result.urls) == 2
        # Name search uses only name + site: (no company)
        assert "john doe site:linkedin.com/in" in result.query.lower()

    @pytest.mark.asyncio
    async def test_returns_empty_urls_when_no_results(self, client: DuckDuckGoClient):
        """Test returns empty list when search yields no results."""
        with patch.object(client, "_execute_search", return_value=[]):
            result = await client.search_linkedin_profile("Unknown Person", "Unknown Co")

        assert result.success is True
        assert result.urls == []


class TestDuckDuckGoClientSearchLinkedInByTitle:
    """Tests for search_linkedin_by_title method."""

    @pytest.fixture
    def client(self) -> DuckDuckGoClient:
        """Create client instance for testing."""
        config = DuckDuckGoConfig(
            DUCKDUCKGO_DELAY_BETWEEN_REQUESTS=0.0,
        )
        return DuckDuckGoClient(config=config)

    @pytest.mark.asyncio
    async def test_successful_title_search(self, client: DuckDuckGoClient):
        """Test successful search by job title."""
        mock_results = [
            {"href": "https://linkedin.com/in/cto-person", "title": "CTO"},
        ]

        with patch.object(client, "_execute_search", return_value=mock_results):
            result = await client.search_linkedin_by_title("CTO", "TechCorp")

        assert result.success is True
        assert len(result.urls) == 1
        # Title search includes company name
        assert "cto techcorp site:linkedin.com/in" in result.query.lower()


class TestDuckDuckGoClientSearchWithFallback:
    """Tests for search_with_fallback method."""

    @pytest.fixture
    def client(self) -> DuckDuckGoClient:
        """Create client instance for testing."""
        config = DuckDuckGoConfig(
            DUCKDUCKGO_DELAY_BETWEEN_REQUESTS=0.0,
        )
        return DuckDuckGoClient(config=config)

    @pytest.mark.asyncio
    async def test_returns_name_search_results_when_found(
        self, client: DuckDuckGoClient
    ):
        """Test returns results from name search when successful."""
        name_result = LinkedInSearchResult(
            urls=["https://www.linkedin.com/in/john-doe"],
            query="john doe site:linkedin.com/in",
        )

        with patch.object(
            client, "search_linkedin_profile", return_value=name_result
        ) as mock_name:
            with patch.object(client, "search_linkedin_by_title") as mock_title:
                result = await client.search_with_fallback(
                    person_name="John Doe",
                    job_title="Engineer",
                    company_name="ACME",
                )

        mock_name.assert_called_once_with("John Doe", "ACME")
        mock_title.assert_not_called()
        assert result.urls == ["https://www.linkedin.com/in/john-doe"]

    @pytest.mark.asyncio
    async def test_falls_back_to_title_when_name_returns_no_urls(
        self, client: DuckDuckGoClient
    ):
        """Test falls back to title search when name search returns empty."""
        name_result = LinkedInSearchResult(urls=[], query="name query")
        title_result = LinkedInSearchResult(
            urls=["https://www.linkedin.com/in/engineer-person"],
            query="title query",
        )

        with patch.object(
            client, "search_linkedin_profile", return_value=name_result
        ):
            with patch.object(
                client, "search_linkedin_by_title", return_value=title_result
            ):
                result = await client.search_with_fallback(
                    person_name="Unknown Person",
                    job_title="Engineer",
                    company_name="ACME",
                )

        assert result.urls == ["https://www.linkedin.com/in/engineer-person"]

    @pytest.mark.asyncio
    async def test_uses_title_search_when_no_name_provided(
        self, client: DuckDuckGoClient
    ):
        """Test uses title search directly when name is None."""
        title_result = LinkedInSearchResult(
            urls=["https://www.linkedin.com/in/cto"],
            query="title query",
        )

        with patch.object(client, "search_linkedin_profile") as mock_name:
            with patch.object(
                client, "search_linkedin_by_title", return_value=title_result
            ):
                result = await client.search_with_fallback(
                    person_name=None,
                    job_title="CTO",
                    company_name="ACME",
                )

        mock_name.assert_not_called()
        assert result.urls == ["https://www.linkedin.com/in/cto"]

    @pytest.mark.asyncio
    async def test_uses_title_search_when_name_is_empty_string(
        self, client: DuckDuckGoClient
    ):
        """Test uses title search when name is empty string."""
        title_result = LinkedInSearchResult(urls=[], query="title query")

        with patch.object(client, "search_linkedin_profile") as mock_name:
            with patch.object(
                client, "search_linkedin_by_title", return_value=title_result
            ):
                await client.search_with_fallback(
                    person_name="",
                    job_title="CTO",
                    company_name="ACME",
                )

        mock_name.assert_not_called()

    @pytest.mark.asyncio
    async def test_uses_title_search_when_name_is_whitespace(
        self, client: DuckDuckGoClient
    ):
        """Test uses title search when name is only whitespace."""
        title_result = LinkedInSearchResult(urls=[], query="title query")

        with patch.object(client, "search_linkedin_profile") as mock_name:
            with patch.object(
                client, "search_linkedin_by_title", return_value=title_result
            ):
                await client.search_with_fallback(
                    person_name="   ",
                    job_title="CTO",
                    company_name="ACME",
                )

        mock_name.assert_not_called()


class TestDuckDuckGoClientExecuteSearch:
    """Tests for _execute_search method."""

    @pytest.fixture
    def client(self) -> DuckDuckGoClient:
        """Create client instance for testing."""
        config = DuckDuckGoConfig(
            DUCKDUCKGO_DELAY_BETWEEN_REQUESTS=0.0,
            DUCKDUCKGO_MAX_RESULTS=5,
        )
        return DuckDuckGoClient(config=config)

    @pytest.mark.asyncio
    async def test_returns_results_on_success(self, client: DuckDuckGoClient):
        """Test returns search results on successful query."""
        mock_results = [
            {"href": "https://linkedin.com/in/user", "title": "User"},
        ]

        with patch.object(client.ddgs, "text", return_value=mock_results):
            results = await client._execute_search("test query")

        assert len(results) == 1
        assert results[0]["href"] == "https://linkedin.com/in/user"

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_exception(self, client: DuckDuckGoClient):
        """Test returns empty list when DDGS raises exception."""
        with patch.object(client.ddgs, "text", side_effect=Exception("Network error")):
            results = await client._execute_search("test query")

        assert results == []

    @pytest.mark.asyncio
    async def test_retries_on_rate_limit(self, client: DuckDuckGoClient):
        """Test retries with exponential backoff on rate limit error."""
        mock_results = [{"href": "https://linkedin.com/in/user", "title": "User"}]

        # First call raises rate limit, second succeeds
        call_count = 0

        def rate_limit_then_success(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("202 Ratelimit")
            return mock_results

        with patch.object(client.ddgs, "text", side_effect=rate_limit_then_success):
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                results = await client._execute_search("test query")

        assert len(results) == 1
        assert client._retry_count == 0  # Reset after success
        mock_sleep.assert_called_once_with(2)  # 2^1 = 2 seconds

    @pytest.mark.asyncio
    async def test_gives_up_after_max_retries(self, client: DuckDuckGoClient):
        """Test returns empty list after max retries on rate limit."""
        with patch.object(
            client.ddgs, "text", side_effect=Exception("202 Ratelimit")
        ):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                results = await client._execute_search("test query")

        assert results == []
        assert client._retry_count == 0  # Reset after giving up


class TestDuckDuckGoClientRateLimiting:
    """Tests for rate limiting behavior."""

    def test_rate_limit_lock_is_shared_across_instances(self):
        """Test that rate limit lock is class-level (shared)."""
        # Reset class-level state
        DuckDuckGoClient._rate_limit_lock = None

        client1 = DuckDuckGoClient()
        client2 = DuckDuckGoClient()

        lock1 = client1._get_rate_limit_lock()
        lock2 = client2._get_rate_limit_lock()

        assert lock1 is lock2


class TestDuckDuckGoClientBatchSearch:
    """Tests for batch_search_linkedin_urls method."""

    @pytest.fixture
    def client(self) -> DuckDuckGoClient:
        """Create client instance for testing."""
        config = DuckDuckGoConfig(
            DUCKDUCKGO_DELAY_BETWEEN_REQUESTS=0.0,
        )
        return DuckDuckGoClient(config=config)

    @pytest.mark.asyncio
    async def test_searches_for_multiple_contacts(self, client: DuckDuckGoClient):
        """Test batch search for multiple contacts."""
        contacts = [
            {"name": "John Doe", "title": "CEO"},
            {"name": "Jane Smith", "title": "CTO"},
        ]

        async def mock_search(person_name, job_title, company_name):
            if person_name == "John Doe":
                return LinkedInSearchResult(
                    urls=["https://www.linkedin.com/in/john-doe"],
                    query="query",
                )
            return LinkedInSearchResult(
                urls=["https://www.linkedin.com/in/jane-smith"],
                query="query",
            )

        with patch.object(client, "search_with_fallback", side_effect=mock_search):
            results = await client.batch_search_linkedin_urls(contacts, "ACME")

        assert "John Doe" in results
        assert "Jane Smith" in results
        assert results["John Doe"] == ["https://www.linkedin.com/in/john-doe"]
        assert results["Jane Smith"] == ["https://www.linkedin.com/in/jane-smith"]

    @pytest.mark.asyncio
    async def test_skips_contacts_without_name_or_title(
        self, client: DuckDuckGoClient
    ):
        """Test that contacts without name and title are skipped."""
        contacts = [
            {"name": "", "title": ""},
            {"name": "Valid", "title": "CEO"},
        ]

        with patch.object(
            client,
            "search_with_fallback",
            return_value=LinkedInSearchResult(urls=[], query="q"),
        ) as mock_search:
            await client.batch_search_linkedin_urls(contacts, "ACME")

        assert mock_search.call_count == 1


class TestDuckDuckGoClientIntegration:
    """Integration-style tests with realistic scenarios."""

    @pytest.fixture
    def client(self) -> DuckDuckGoClient:
        """Create client instance for testing."""
        config = DuckDuckGoConfig(
            DUCKDUCKGO_DELAY_BETWEEN_REQUESTS=0.0,
            DUCKDUCKGO_MAX_RESULTS=10,
        )
        return DuckDuckGoClient(config=config)

    def test_extracts_urls_from_typical_ddgs_response(self, client: DuckDuckGoClient):
        """Test extraction from typical DDGS response format."""
        results = [
            {
                "title": "John Doe - CEO - ACME Corp | LinkedIn",
                "href": "https://www.linkedin.com/in/john-doe-12345",
                "body": "View John Doe's profile on LinkedIn...",
            },
            {
                "title": "ACME Corp | LinkedIn",
                "href": "https://www.linkedin.com/company/acme-corp",
                "body": "ACME Corp is a technology company...",
            },
            {
                "title": "Jane Smith - CTO - ACME Corp | LinkedIn",
                "href": "https://fr.linkedin.com/in/jane-smith",
                "body": "View Jane Smith's profile...",
            },
        ]

        urls = client._extract_linkedin_urls(results)

        assert len(urls) == 2  # Company URL should be excluded
        assert "https://www.linkedin.com/in/john-doe-12345" in urls
        assert "https://www.linkedin.com/in/jane-smith" in urls

    def test_handles_complex_linkedin_usernames(self, client: DuckDuckGoClient):
        """Test extraction of various LinkedIn username formats."""
        results = [
            {"href": "https://linkedin.com/in/simple"},
            {"href": "https://linkedin.com/in/with-hyphens"},
            {"href": "https://linkedin.com/in/with_underscores"},
            {"href": "https://linkedin.com/in/MixedCase123"},
        ]

        urls = client._extract_linkedin_urls(results)

        assert len(urls) == 4
        assert "https://www.linkedin.com/in/simple" in urls
        assert "https://www.linkedin.com/in/with-hyphens" in urls
        assert "https://www.linkedin.com/in/with_underscores" in urls
        assert "https://www.linkedin.com/in/mixedcase123" in urls


