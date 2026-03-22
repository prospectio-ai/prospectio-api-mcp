"""
Unit tests for ProfileDatabase conversion methods.

Tests the _convert_dto_to_entity method that converts ProfileDTO
to Profile domain entity without requiring a real database.
"""

import pytest
from unittest.mock import MagicMock

from domain.entities.profile import Profile
from domain.entities.work_experience import WorkExperience
from domain.entities.education import Education
from domain.entities.certification import Certification
from domain.entities.language import Language
from infrastructure.services.profile_database import ProfileDatabase


class TestProfileDatabaseConversion:
    """Test suite for ProfileDatabase entity conversion methods."""

    @pytest.fixture
    def profile_db(self) -> ProfileDatabase:
        """Create a ProfileDatabase instance with a dummy URL."""
        return ProfileDatabase("sqlite+aiosqlite:///:memory:")

    def _make_dto(self, **overrides) -> MagicMock:
        """Helper to create a mock ProfileDTO with defaults."""
        dto = MagicMock()
        dto.full_name = overrides.get("full_name", "Jean Dupont")
        dto.email = overrides.get("email", "jean@example.com")
        dto.phone = overrides.get("phone", "+33612345678")
        dto.job_title = overrides.get("job_title", "Software Engineer")
        dto.location = overrides.get("location", "Paris, France")
        dto.bio = overrides.get("bio", "Experienced developer")
        dto.years_of_experience = overrides.get("years_of_experience", 10)
        dto.work_experience = overrides.get("work_experience", None)
        dto.education = overrides.get("education", None)
        dto.certifications = overrides.get("certifications", None)
        dto.languages = overrides.get("languages", None)
        dto.technos = overrides.get("technos", ["Python", "FastAPI"])
        return dto

    def test_convert_dto_to_entity_basic_fields(self, profile_db: ProfileDatabase):
        """Should convert basic scalar fields from DTO to Profile entity."""
        dto = self._make_dto()
        result = profile_db._convert_dto_to_entity(dto)

        assert isinstance(result, Profile)
        assert result.full_name == "Jean Dupont"
        assert result.email == "jean@example.com"
        assert result.phone == "+33612345678"
        assert result.job_title == "Software Engineer"
        assert result.location == "Paris, France"
        assert result.bio == "Experienced developer"
        assert result.years_of_experience == 10
        assert result.technos == ["Python", "FastAPI"]

    def test_convert_dto_to_entity_with_work_experience(self, profile_db: ProfileDatabase):
        """Should convert work_experience list from DTO dicts to WorkExperience entities."""
        dto = self._make_dto(
            work_experience=[
                {
                    "company": "Acme Corp",
                    "position": "Senior Developer",
                    "start_date": "2020-01",
                    "end_date": "2024-01",
                    "description": "Led a team of 5 developers",
                },
                {
                    "company": "Startup Inc",
                    "position": "Junior Developer",
                    "start_date": "2018-06",
                    "end_date": "2020-01",
                    "description": "Full-stack development",
                },
            ]
        )
        result = profile_db._convert_dto_to_entity(dto)

        assert len(result.work_experience) == 2
        assert isinstance(result.work_experience[0], WorkExperience)
        assert result.work_experience[0].company == "Acme Corp"
        assert result.work_experience[0].position == "Senior Developer"
        assert result.work_experience[1].company == "Startup Inc"

    def test_convert_dto_to_entity_with_education(self, profile_db: ProfileDatabase):
        """Should convert education list from DTO dicts to Education entities."""
        dto = self._make_dto(
            education=[
                {
                    "institution": "University of Paris",
                    "degree": "Master's in Computer Science",
                    "start_date": "2015-09",
                    "end_date": "2017-06",
                }
            ]
        )
        result = profile_db._convert_dto_to_entity(dto)

        assert len(result.education) == 1
        assert isinstance(result.education[0], Education)
        assert result.education[0].institution == "University of Paris"

    def test_convert_dto_to_entity_with_certifications(self, profile_db: ProfileDatabase):
        """Should convert certifications list from DTO dicts to Certification entities."""
        dto = self._make_dto(
            certifications=[
                {
                    "name": "AWS Solutions Architect",
                    "issuer": "Amazon",
                    "date": "2023-06",
                }
            ]
        )
        result = profile_db._convert_dto_to_entity(dto)

        assert len(result.certifications) == 1
        assert isinstance(result.certifications[0], Certification)
        assert result.certifications[0].name == "AWS Solutions Architect"

    def test_convert_dto_to_entity_with_languages(self, profile_db: ProfileDatabase):
        """Should convert languages list from DTO dicts to Language entities."""
        dto = self._make_dto(
            languages=[
                {"name": "French", "level": "native"},
                {"name": "English", "level": "fluent"},
            ]
        )
        result = profile_db._convert_dto_to_entity(dto)

        assert len(result.languages) == 2
        assert isinstance(result.languages[0], Language)
        assert result.languages[0].name == "French"
        assert result.languages[1].name == "English"

    def test_convert_dto_to_entity_with_empty_nested_lists(self, profile_db: ProfileDatabase):
        """Should handle empty nested lists gracefully."""
        dto = self._make_dto(
            work_experience=[],
            education=[],
            certifications=[],
            languages=[],
        )
        result = profile_db._convert_dto_to_entity(dto)

        assert result.work_experience == []
        assert result.education == []
        assert result.certifications == []
        assert result.languages == []

    def test_convert_dto_to_entity_with_none_nested_lists(self, profile_db: ProfileDatabase):
        """Should handle None nested lists by returning empty lists."""
        dto = self._make_dto(
            work_experience=None,
            education=None,
            certifications=None,
            languages=None,
        )
        result = profile_db._convert_dto_to_entity(dto)

        assert result.work_experience == []
        assert result.education == []
        assert result.certifications == []
        assert result.languages == []

    def test_convert_dto_to_entity_with_none_technos(self, profile_db: ProfileDatabase):
        """Should handle None technos by returning empty list."""
        dto = self._make_dto(technos=None)
        result = profile_db._convert_dto_to_entity(dto)

        assert result.technos == []
