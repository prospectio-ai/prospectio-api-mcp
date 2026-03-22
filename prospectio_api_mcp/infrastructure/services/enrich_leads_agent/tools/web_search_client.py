"""
Web Search client using Perplexity's sonar model.

This client uses Perplexity's native web search capabilities through OpenRouter.
Perplexity sonar models have built-in web search and return citations inline.
"""

import asyncio
import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from config import LLMConfig, WebSearchConfig
from infrastructure.services.enrich_leads_agent.models.web_search_models import (
    WebSearchResult,
    WebSearchSource,
)

logger = logging.getLogger(__name__)


class WebSearchClient:
    """
    Client for performing web searches using Perplexity's sonar model.

    Perplexity models have native web search capabilities and return
    citations inline in the response text (e.g., [1], [2]).
    Supports configurable concurrent requests via WEB_SEARCH_CONCURRENT_REQUESTS.
    """

    # Class-level semaphore to limit concurrent requests across ALL instances
    _semaphore: asyncio.Semaphore | None = None

    @classmethod
    def _get_semaphore(cls, limit: int) -> asyncio.Semaphore:
        """Get or create the class-level semaphore with the specified limit."""
        if cls._semaphore is None:
            cls._semaphore = asyncio.Semaphore(limit)
        return cls._semaphore

    def __init__(
        self,
        llm_config: LLMConfig | None = None,
        web_search_config: WebSearchConfig | None = None,
    ):
        """
        Initialize the Perplexity web search client.

        Args:
            llm_config: Optional LLMConfig for OpenRouter credentials.
            web_search_config: Optional WebSearchConfig for search settings.
        """
        self.llm_config = llm_config or LLMConfig()
        self.web_search_config = web_search_config or WebSearchConfig()
        self._retry_count = 0
        self._max_retries = 3

        # Initialize ChatOpenAI with OpenRouter settings for Perplexity
        # Perplexity sonar models have native web search - no plugins needed
        self.client = ChatOpenAI(
            model=self.web_search_config.WEB_SEARCH_MODEL,
            api_key=self.llm_config.OPEN_ROUTER_API_KEY,
            base_url=self.llm_config.OPEN_ROUTER_API_URL,
            timeout=self.web_search_config.WEB_SEARCH_TIMEOUT,
        )

    def _extract_sources_from_response(self, response) -> list[WebSearchSource]:
        """
        Extract sources from Perplexity response if available.

        Note: Perplexity via OpenRouter typically doesn't return structured citations
        in the metadata. The citations are embedded inline in the response text.
        The main content is in the `answer` field which is used by get_combined_content().

        Args:
            response: The LangChain response object.

        Returns:
            list[WebSearchSource]: Extracted sources (may be empty for Perplexity).
        """
        if not hasattr(response, "response_metadata"):
            return []

        metadata = response.response_metadata

        # Try Perplexity format: citations as list of URLs
        citations = metadata.get("citations", [])
        if citations:
            return [
                WebSearchSource(title=f"Source {i + 1}", url=url, content="")
                for i, url in enumerate(citations)
                if isinstance(url, str)
            ]

        # Try OpenRouter annotations format
        annotations = metadata.get("annotations", [])
        if annotations:
            return [
                WebSearchSource(
                    title=annotation.get("url_citation", {}).get("title", ""),
                    url=annotation.get("url_citation", {}).get("url", ""),
                    content=annotation.get("url_citation", {}).get("content", ""),
                )
                for annotation in annotations
                if annotation.get("type") == "url_citation"
            ]

        # No structured citations - this is expected for Perplexity via OpenRouter
        # The content is in the answer field instead
        return []

    async def search(
        self,
        query: str,
        system_instructions: str = "Focus on providing all details about user's request",
    ) -> WebSearchResult:
        """
        Search using Perplexity web search and return results with content.

        Args:
            query: The search query string.
            system_instructions: Custom instructions for the search.

        Returns:
            WebSearchResult: Search result containing answer and sources.
        """
        try:
            semaphore = self._get_semaphore(
                self.web_search_config.WEB_SEARCH_CONCURRENT_REQUESTS
            )
            async with semaphore:
                logger.info(f"Perplexity web search starting: query='{query}'")

                messages = [
                    SystemMessage(content=system_instructions),
                    HumanMessage(content=query),
                ]

                response = await self.client.ainvoke(messages)

                sources = self._extract_sources_from_response(response)

                result = WebSearchResult(
                    answer=response.content if isinstance(response.content, str) else "",
                    sources=sources,
                )

                logger.info(
                    f"Perplexity web search completed:\n"
                    f"  Query: {query}\n"
                    f"  Answer ({len(result.answer)} chars):\n{result.answer}\n"
                    f"  Sources count: {len(result.sources)}"
                )

                self._retry_count = 0
                return result

        except Exception as e:
            error_str = str(e).lower()

            # Handle rate limiting
            if "429" in error_str or "rate" in error_str:
                if self._retry_count < self._max_retries:
                    self._retry_count += 1
                    logger.warning(
                        f"Perplexity rate limit hit. Retry {self._retry_count}/{self._max_retries}"
                    )
                    await asyncio.sleep(2**self._retry_count)
                    return await self.search(query, system_instructions)
                else:
                    logger.error("Perplexity rate limit exceeded. No more retries.")
                    self._retry_count = 0
                    return WebSearchResult()

            logger.error(f"Perplexity web search error for query '{query}': {e}")
            return WebSearchResult()

    async def search_with_site_filter(
        self,
        query: str,
        site: str,
        system_instructions: str = "Focus on providing all details about user's request",
    ) -> WebSearchResult:
        """
        Search with a site filter (e.g., site:pappers.fr).

        Args:
            query: The base search query.
            site: The site to filter results to (e.g., pappers.fr).
            system_instructions: Custom instructions for the search.

        Returns:
            WebSearchResult: Search result containing answer and sources with content.
        """
        filtered_query = f"{query} site:{site}"
        return await self.search(
            query=filtered_query,
            system_instructions=system_instructions,
        )

    async def search_company_contacts(
        self,
        company_name: str,
        job_title: str,
    ) -> WebSearchResult:
        """
        Search for contact information at a company with a specific job title.

        This method focuses on finding general contact information (names, emails,
        phone numbers) without specifically targeting LinkedIn. LinkedIn URL
        discovery is handled separately by DuckDuckGoClient.

        Args:
            company_name: Name of the company.
            job_title: Job title to search for.

        Returns:
            WebSearchResult: Search result containing contact information.
        """
        query = (
            f"Find professionals working at {company_name} with position similar to: {job_title}. "
            f"I need their contact information including full names, email addresses, and phone numbers. "
            f"Return as much information as possible about each person."
        )
        return await self.search(
            query=query,
            system_instructions=(
                "Search for professionals at this company. For each person found, you MUST provide:\n"
                "- Full name\n"
                "- Current job title\n"
                "- Professional background\n"
                "- Email address if available\n"
                "- Phone number if available\n"
                "Focus on finding contact information for decision-makers and professionals."
            ),
        )

    async def search_company_info(
        self,
        company_name: str,
    ) -> WebSearchResult:
        """
        Search for company information.

        Args:
            company_name: Name of the company to search for.

        Returns:
            WebSearchResult: Search results with company information.
        """
        query = (
            f"I want detailed information about the company {company_name}. "
            f"Return as much information as you can about this company."
        )
        return await self.search(
            query=query,
            system_instructions=(
                "Provide comprehensive company information including:\n"
                "- Company description and what they do\n"
                "- Products and services offered\n"
                "- Industry and market sectors\n"
                "- Headquarters location and offices\n"
                "- Company size (number of employees)\n"
                "- Revenue and financial information if available\n"
                "- Year founded\n"
                "- Key executives and leadership\n"
                "- Website and social media\n"
                "- Any registration numbers (SIRET, SIREN, etc.)\n"
                "Return all available details about this company."
            ),
        )

    async def search_contact_bio(
        self,
        first_name: str,
        last_name: str,
        position: str,
        company: str,
    ) -> WebSearchResult:
        """
        Search for contact biography information.

        Args:
            first_name: First name of the contact.
            last_name: Last name of the contact.
            position: Job title/position of the contact.
            company: Company where the contact works.

        Returns:
            WebSearchResult: Search results containing biography information.
        """
        query = (
            f'"{first_name} {last_name}" "{position}" "{company}" '
            f"professional background biography"
        )
        return await self.search(
            query=query,
            system_instructions=(
                "Search for professional information about this person. Provide:\n"
                "- Professional background and career history\n"
                "- Current role and responsibilities\n"
                "- Key achievements and expertise areas\n"
                "- Education and qualifications\n"
                "- Notable projects or contributions\n"
                "- Industry recognition or awards\n"
                "- Any public speaking, publications, or thought leadership\n"
                "Return all available professional details about this person."
            ),
        )
