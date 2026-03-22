"""
Unit tests for PromptLoader service.

Tests the prompt loading functionality from markdown files.
"""

import pytest
import os
from domain.services.prompt_loader import PromptLoader


class TestPromptLoader:
    """Test suite for PromptLoader."""

    @pytest.fixture
    def loader(self) -> PromptLoader:
        """Create a PromptLoader instance."""
        return PromptLoader()

    def test_load_existing_prompt(self, loader: PromptLoader):
        """Should load an existing prompt file and return its content."""
        result = loader.load_prompt("company_description")

        assert isinstance(result, str)
        assert len(result) > 0
        # Should not be the default fallback
        assert result != "You are a helpful AI assistant."

    def test_load_all_known_prompts(self, loader: PromptLoader):
        """Should successfully load all prompts defined in the mapping."""
        for prompt_name in PromptLoader.prompt_mapping:
            result = loader.load_prompt(prompt_name)
            assert isinstance(result, str)
            assert len(result) > 0, f"Prompt '{prompt_name}' is empty"

    def test_load_nonexistent_prompt_returns_fallback(self, loader: PromptLoader):
        """Should return fallback message for a prompt not in the mapping."""
        result = loader.load_prompt("nonexistent_prompt_that_does_not_exist")

        assert result == "You are a helpful AI assistant."

    def test_prompt_mapping_has_expected_keys(self):
        """Should have the expected prompt names in the mapping."""
        expected_keys = [
            "compatibility_score",
            "company_decision",
            "company_description",
            "company_info",
            "contact_bio",
            "contact_info",
            "contacts_from_answer",
            "job_titles",
            "prospecting_message",
            "resume_extraction",
        ]
        for key in expected_keys:
            assert key in PromptLoader.prompt_mapping, f"Missing prompt key: {key}"

    def test_loaded_prompt_is_stripped(self, loader: PromptLoader):
        """Loaded prompts should be stripped of leading/trailing whitespace."""
        result = loader.load_prompt("company_description")

        # The result should not start or end with whitespace
        assert result == result.strip()
