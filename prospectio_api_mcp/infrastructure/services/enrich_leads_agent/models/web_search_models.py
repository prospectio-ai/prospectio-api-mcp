"""
Pydantic models for web search responses (Perplexity/OpenRouter).
"""

from pydantic import BaseModel, Field

from infrastructure.services.enrich_leads_agent.models.search_results_model import (
    SearchResultModel,
)


class WebSearchSource(BaseModel):
    """
    Represents a source/citation from web search responses.
    """

    title: str = ""
    url: str = ""
    content: str = ""


class WebSearchResult(BaseModel):
    """
    Processed result from web search containing the answer
    and converted search results for compatibility with existing code.
    """

    answer: str = ""
    sources: list[WebSearchSource] = Field(default_factory=list)

    def to_search_results(self) -> list[SearchResultModel]:
        """
        Convert web search sources to SearchResultModel format for compatibility
        with existing code that expects search-style results.

        Returns:
            list[SearchResultModel]: List of search results in the standard format.
        """
        return [
            SearchResultModel(
                title=source.title,
                url=source.url,
                snippet=source.content[:500] if source.content else "",
            )
            for source in self.sources
        ]

    def get_combined_content(self) -> str:
        """
        Get the answer and source content combined into a single string.

        For Perplexity models, the answer contains the main synthesized content.
        For OpenRouter :online models, sources may also contain crawled content.

        Returns:
            str: Combined content from answer and sources.
        """
        contents = []

        # Include the main answer (primary content from Perplexity)
        if self.answer:
            contents.append(self.answer)

        # Include source content if available (OpenRouter annotations format)
        for source in self.sources:
            if source.content:
                header = f"## {source.title}\n" if source.title else ""
                url_ref = f"Source: {source.url}\n" if source.url else ""
                contents.append(f"{header}{url_ref}\n{source.content}")

        return "\n\n---\n\n".join(contents)
