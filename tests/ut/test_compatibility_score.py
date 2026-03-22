"""
Unit tests for CompatibilityScoreLLM.

Tests the compatibility scoring service with mocked LLM.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from domain.entities.compatibility_score import CompatibilityScore
from domain.entities.profile import Profile
from infrastructure.services.compatibility_score import CompatibilityScoreLLM


class TestCompatibilityScoreLLM:
    """Test suite for CompatibilityScoreLLM."""

    @pytest.fixture
    def profile(self) -> Profile:
        """Create a sample profile for testing."""
        return Profile(
            job_title="AI Developer",
            location="Paris, France",
            bio="Expert in machine learning and Python",
            work_experience=[],
        )

    @pytest.mark.asyncio
    async def test_get_compatibility_score_success(self, profile: Profile):
        """Should return a CompatibilityScore from the LLM chain."""
        expected_score = CompatibilityScore(score=85)

        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = expected_score.model_dump()

        with patch.object(CompatibilityScoreLLM, "__init__", lambda self: None):
            scorer = CompatibilityScoreLLM()
            scorer.llm_client = MagicMock()
            scorer.llm_client.with_structured_output.return_value = MagicMock()

        # Patch the whole chain creation
        with patch("infrastructure.services.compatibility_score.PromptLoader") as mock_loader, \
             patch("infrastructure.services.compatibility_score.PromptTemplate") as mock_template:
            mock_loader.return_value.load_prompt.return_value = "Test prompt"
            mock_template.return_value.__or__ = MagicMock(return_value=mock_chain)

            result = await scorer.get_compatibility_score(
                profile=profile,
                job_description="Python developer position at a tech company",
                job_location="Paris",
            )

        assert isinstance(result, CompatibilityScore)
        assert result.score == 85

    @pytest.mark.asyncio
    async def test_get_compatibility_score_invokes_chain_with_profile_data(self, profile: Profile):
        """Should pass profile and job data to the LLM chain."""
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = {"score": 70}

        with patch.object(CompatibilityScoreLLM, "__init__", lambda self: None):
            scorer = CompatibilityScoreLLM()
            scorer.llm_client = MagicMock()
            scorer.llm_client.with_structured_output.return_value = MagicMock()

        with patch("infrastructure.services.compatibility_score.PromptLoader") as mock_loader, \
             patch("infrastructure.services.compatibility_score.PromptTemplate") as mock_template:
            mock_loader.return_value.load_prompt.return_value = "Test prompt"
            mock_template.return_value.__or__ = MagicMock(return_value=mock_chain)

            result = await scorer.get_compatibility_score(
                profile=profile,
                job_description="Backend developer role",
                job_location="Remote",
            )

        # Verify chain was invoked with correct arguments
        call_args = mock_chain.ainvoke.call_args[0][0]
        assert call_args["job_title"] == "AI Developer"
        assert call_args["profile_location"] == "Paris, France"
        assert call_args["bio"] == "Expert in machine learning and Python"
        assert call_args["job_description"] == "Backend developer role"
        assert call_args["job_location"] == "Remote"
