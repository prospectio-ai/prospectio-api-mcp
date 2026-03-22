"""
DuckDuckGo search client for LinkedIn profile URL discovery.

This client uses the ddgs library to find LinkedIn profile URLs.
It provides rate limiting and fallback strategies for reliable searches.
"""

import asyncio
import logging
import re
import time
from dataclasses import dataclass

from ddgs import DDGS

from config import DuckDuckGoConfig

logger = logging.getLogger(__name__)


@dataclass
class LinkedInSearchResult:
    """
    Result from a LinkedIn profile search.

    Attributes:
        urls: List of LinkedIn profile URLs found.
        query: The search query used.
        success: Whether the search completed successfully.
        error: Error message if search failed.
    """

    urls: list[str]
    query: str
    success: bool = True
    error: str | None = None


class DuckDuckGoClient:
    """
    Client for searching LinkedIn profile URLs via DuckDuckGo.

    Uses the duckduckgo-search library to perform searches and extract
    LinkedIn profile URLs from results. Implements rate limiting to
    avoid being blocked.
    """

    LINKEDIN_URL_PATTERN = re.compile(
        r"https?://(?:[\w-]+\.)?linkedin\.com/in/([\w\-]+)",
        re.IGNORECASE,
    )

    # Class-level lock for rate limiting across all instances
    _rate_limit_lock: asyncio.Lock | None = None
    _last_request_time: float = 0

    @classmethod
    def _get_rate_limit_lock(cls) -> asyncio.Lock:
        """Get or create the class-level rate limit lock."""
        if cls._rate_limit_lock is None:
            cls._rate_limit_lock = asyncio.Lock()
        return cls._rate_limit_lock

    def __init__(self, config: DuckDuckGoConfig | None = None):
        """
        Initialize the DuckDuckGo client.

        Args:
            config: Optional DuckDuckGoConfig for search settings.
        """
        self.config = config or DuckDuckGoConfig()
        self.ddgs = DDGS()
        self._retry_count = 0

    async def _wait_for_rate_limit(self) -> None:
        """
        Wait for the required delay between requests.

        Ensures requests are spaced out to avoid rate limiting.
        """
        lock = self._get_rate_limit_lock()
        async with lock:
            current_time = time.monotonic()
            time_since_last = current_time - DuckDuckGoClient._last_request_time
            delay_needed = self.config.DUCKDUCKGO_DELAY_BETWEEN_REQUESTS - time_since_last

            if delay_needed > 0:
                logger.debug(f"Rate limiting: waiting {delay_needed:.2f}s before request")
                await asyncio.sleep(delay_needed)

            DuckDuckGoClient._last_request_time = time.monotonic()

    def _extract_linkedin_urls(self, results: list[dict]) -> list[str]:
        """
        Extract unique LinkedIn profile URLs from search results.

        Args:
            results: List of search result dictionaries from DDGS.

        Returns:
            List of unique LinkedIn profile URLs found.
        """
        unique_urls: list[str] = []
        seen_usernames: set[str] = set()

        for result in results:
            href = result.get("href", "") or result.get("link", "")

            # Check if it's a LinkedIn profile URL
            match = self.LINKEDIN_URL_PATTERN.search(href)
            if match:
                username = match.group(1).lower()
                if username not in seen_usernames:
                    seen_usernames.add(username)
                    unique_urls.append(f"https://www.linkedin.com/in/{username}")

        return unique_urls[: self.config.DUCKDUCKGO_MAX_RESULTS]

    def _sanitize_search_term(self, term: str) -> str:
        """
        Sanitize a search term to prevent query issues.

        Args:
            term: The raw search term to sanitize.

        Returns:
            Sanitized search term safe for use in queries.
        """
        if not term:
            return ""
        # Remove problematic characters
        sanitized = re.sub(r'["\'\\\n\r\t]', " ", term)
        # Remove excessive whitespace
        sanitized = re.sub(r"\s+", " ", sanitized).strip()
        # Limit length
        return sanitized[:200]

    async def _execute_search(self, query: str) -> list[dict]:
        """
        Execute a DuckDuckGo search with retry logic for rate limits.

        Args:
            query: The search query string.

        Returns:
            List of search result dictionaries.
        """
        await self._wait_for_rate_limit()

        try:
            logger.info(f"DuckDuckGo search: {query}")

            # Run synchronous DDGS in thread to not block async loop
            results = await asyncio.to_thread(
                self.ddgs.text,
                query,
                max_results=self.config.DUCKDUCKGO_MAX_RESULTS,
            )

            # Reset retry count on success
            self._retry_count = 0
            logger.debug(f"DuckDuckGo returned {len(results)} results")
            return list(results)

        except Exception as e:
            # Handle rate limit with exponential backoff
            if "202 Ratelimit" in str(e):
                if self._retry_count < 5:
                    self._retry_count += 1
                    delay = 2 ** self._retry_count
                    logger.warning(
                        f"Rate limit hit. Retrying {self._retry_count}/5 after {delay}s..."
                    )
                    await asyncio.sleep(delay)
                    return await self._execute_search(query)
                else:
                    logger.error("Rate limit exceeded. No more retries.")
                    self._retry_count = 0
                    return []

            logger.error(f"DuckDuckGo search failed for '{query}': {e}")
            return []

    async def _search_linkedin(
        self,
        search_term: str,
        company_name: str,
        search_type: str = "name",
    ) -> LinkedInSearchResult:
        """
        Core LinkedIn search method.

        Args:
            search_term: The name or job title to search for.
            company_name: Name of the company (used only for title searches).
            search_type: Type of search for logging ("name" or "title").

        Returns:
            LinkedInSearchResult containing found LinkedIn URLs.
        """
        safe_term = self._sanitize_search_term(search_term)

        # For name searches, just use name + site: (simpler = better results)
        # For title searches, include company to narrow down
        if search_type == "name":
            query = f'{safe_term} site:linkedin.com/in'
        else:
            safe_company = self._sanitize_search_term(company_name)
            query = f'{safe_term} {safe_company} site:linkedin.com/in'

        logger.info(f"DuckDuckGo LinkedIn {search_type} search: {query}")

        results = await self._execute_search(query)

        if not results:
            return LinkedInSearchResult(
                urls=[],
                query=query,
                success=True,  # Search succeeded but no results
                error=None,
            )

        urls = self._extract_linkedin_urls(results)
        logger.info(f"Found {len(urls)} LinkedIn URLs for '{search_term}' at '{company_name}'")

        return LinkedInSearchResult(urls=urls, query=query)

    async def search_linkedin_profile(
        self,
        person_name: str,
        company_name: str,
    ) -> LinkedInSearchResult:
        """
        Search for a person's LinkedIn profile by name and company.

        Args:
            person_name: Full name of the person to search for.
            company_name: Name of the company the person works at.

        Returns:
            LinkedInSearchResult containing found LinkedIn URLs.
        """
        return await self._search_linkedin(person_name, company_name, "name")

    async def search_linkedin_by_title(
        self,
        job_title: str,
        company_name: str,
    ) -> LinkedInSearchResult:
        """
        Search for LinkedIn profiles by job title and company.

        Args:
            job_title: The job title to search for.
            company_name: Name of the company.

        Returns:
            LinkedInSearchResult containing found LinkedIn URLs.
        """
        return await self._search_linkedin(job_title, company_name, "title")

    async def search_with_fallback(
        self,
        person_name: str | None,
        job_title: str,
        company_name: str,
    ) -> LinkedInSearchResult:
        """
        Search for LinkedIn profile with fallback strategy.

        First tries to search by person name if provided. If no results
        are found or name is not available, falls back to searching by
        job title.

        Args:
            person_name: Optional full name of the person.
            job_title: The job title to use as fallback.
            company_name: Name of the company.

        Returns:
            LinkedInSearchResult containing found LinkedIn URLs.
        """
        # Try name search first if name is provided
        if person_name and person_name.strip():
            result = await self.search_linkedin_profile(person_name, company_name)

            if result.success and result.urls:
                return result

            logger.info(
                f"No results by name for '{person_name}', "
                f"falling back to title search '{job_title}'"
            )

        # Fallback to title search
        return await self.search_linkedin_by_title(job_title, company_name)

    async def batch_search_linkedin_urls(
        self,
        contacts: list[dict],
        company_name: str,
    ) -> dict[str, list[str]]:
        """
        Search for LinkedIn URLs for multiple contacts.

        Args:
            contacts: List of contact dictionaries with 'name' and 'title' keys.
            company_name: Name of the company.

        Returns:
            Dictionary mapping contact names to lists of LinkedIn URLs.
        """
        results: dict[str, list[str]] = {}

        for contact in contacts:
            name = contact.get("name", "")
            title = contact.get("title", "")

            if not name and not title:
                continue

            result = await self.search_with_fallback(
                person_name=name,
                job_title=title,
                company_name=company_name,
            )

            key = name or title
            results[key] = result.urls

        return results
