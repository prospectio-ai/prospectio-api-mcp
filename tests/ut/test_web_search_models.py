"""
Unit tests for WebSearchResult and WebSearchSource models.

Tests the conversion methods to_search_results() and get_combined_content().
"""

import pytest

from infrastructure.services.enrich_leads_agent.models.web_search_models import (
    WebSearchResult,
    WebSearchSource,
)


class TestWebSearchSource:
    """Tests for WebSearchSource model."""

    def test_default_values(self):
        """Should have empty string defaults."""
        source = WebSearchSource()

        assert source.title == ""
        assert source.url == ""
        assert source.content == ""

    def test_with_data(self):
        """Should accept title, url, and content."""
        source = WebSearchSource(
            title="Company Page",
            url="https://acme.com",
            content="Acme is a technology company...",
        )

        assert source.title == "Company Page"
        assert source.url == "https://acme.com"
        assert source.content == "Acme is a technology company..."


class TestWebSearchResultToSearchResults:
    """Tests for WebSearchResult.to_search_results() method."""

    def test_empty_sources(self):
        """Should return empty list when no sources."""
        result = WebSearchResult(answer="Some answer")
        search_results = result.to_search_results()

        assert search_results == []

    def test_converts_sources_to_search_result_models(self):
        """Should convert WebSearchSource objects to SearchResultModel format."""
        result = WebSearchResult(
            answer="Answer text",
            sources=[
                WebSearchSource(
                    title="Source 1",
                    url="https://source1.com",
                    content="Content for source 1 that is quite detailed.",
                ),
                WebSearchSource(
                    title="Source 2",
                    url="https://source2.com",
                    content="",
                ),
            ],
        )
        search_results = result.to_search_results()

        assert len(search_results) == 2
        assert search_results[0].title == "Source 1"
        assert search_results[0].url == "https://source1.com"
        assert search_results[0].snippet == "Content for source 1 that is quite detailed."
        assert search_results[1].title == "Source 2"
        assert search_results[1].snippet == ""

    def test_truncates_long_content_to_500_chars(self):
        """Should truncate content to 500 characters for the snippet."""
        long_content = "A" * 1000
        result = WebSearchResult(
            sources=[
                WebSearchSource(
                    title="Long",
                    url="https://long.com",
                    content=long_content,
                ),
            ],
        )
        search_results = result.to_search_results()

        assert len(search_results[0].snippet) == 500


class TestWebSearchResultGetCombinedContent:
    """Tests for WebSearchResult.get_combined_content() method."""

    def test_empty_result(self):
        """Should return empty string when no answer and no sources."""
        result = WebSearchResult()
        content = result.get_combined_content()

        assert content == ""

    def test_answer_only(self):
        """Should return just the answer when no sources have content."""
        result = WebSearchResult(answer="This is the main answer.")
        content = result.get_combined_content()

        assert content == "This is the main answer."

    def test_answer_with_source_content(self):
        """Should combine answer and source content with separators."""
        result = WebSearchResult(
            answer="Main answer text",
            sources=[
                WebSearchSource(
                    title="Page Title",
                    url="https://example.com",
                    content="Source content here.",
                ),
            ],
        )
        content = result.get_combined_content()

        assert "Main answer text" in content
        assert "## Page Title" in content
        assert "Source: https://example.com" in content
        assert "Source content here." in content
        assert "---" in content

    def test_sources_without_content_are_skipped(self):
        """Should skip sources that have no content."""
        result = WebSearchResult(
            answer="Answer",
            sources=[
                WebSearchSource(title="No Content", url="https://empty.com", content=""),
                WebSearchSource(title="Has Content", url="https://full.com", content="Actual content"),
            ],
        )
        content = result.get_combined_content()

        assert "No Content" not in content
        assert "Has Content" in content
        assert "Actual content" in content

    def test_source_without_title_or_url(self):
        """Should handle sources with empty title or url."""
        result = WebSearchResult(
            sources=[
                WebSearchSource(title="", url="", content="Just content, no metadata"),
            ],
        )
        content = result.get_combined_content()

        assert "Just content, no metadata" in content
        # No header or source line since they're empty
        assert "##" not in content
        assert "Source:" not in content

    def test_multiple_sources_with_content(self):
        """Should combine multiple sources with separator."""
        result = WebSearchResult(
            answer="Intro",
            sources=[
                WebSearchSource(title="S1", url="https://s1.com", content="Content 1"),
                WebSearchSource(title="S2", url="https://s2.com", content="Content 2"),
            ],
        )
        content = result.get_combined_content()

        assert content.count("---") == 2  # Two separators: answer|s1, s1|s2
        assert "Content 1" in content
        assert "Content 2" in content
