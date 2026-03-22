"""
Tests for infrastructure/dto/llm/ - LLM DTO Pydantic models.
Covers: CertificationLLM, EducationLLM, LanguageLLM, WorkExperienceLLM,
        ExtractedProfileLLM, ResumeExtractionResult, and __init__ re-exports.
"""
import pytest
from pydantic import ValidationError

from infrastructure.dto.llm import (
    CertificationLLM,
    EducationLLM,
    LanguageLLM,
    WorkExperienceLLM,
    ExtractedProfileLLM,
    ResumeExtractionResult,
)
from domain.entities.profile import Profile


class TestWorkExperienceLLM:
    """Test suite for WorkExperienceLLM model."""

    def test_valid_work_experience(self):
        """Should accept all required fields."""
        exp = WorkExperienceLLM(
            position="Senior Developer",
            company="TechCorp",
            start_date="2020-01",
            end_date="2024-12",
            description="Built APIs",
        )
        assert exp.position == "Senior Developer"
        assert exp.company == "TechCorp"

    def test_rejects_missing_position(self):
        """Should reject missing position."""
        with pytest.raises(ValidationError):
            WorkExperienceLLM(
                company="TechCorp",
                start_date="2020-01",
                end_date="Present",
                description="Built APIs",
            )  # type: ignore

    def test_rejects_missing_company(self):
        """Should reject missing company."""
        with pytest.raises(ValidationError):
            WorkExperienceLLM(
                position="Developer",
                start_date="2020-01",
                end_date="Present",
                description="Built APIs",
            )  # type: ignore

    def test_end_date_can_be_present(self):
        """Should accept 'Present' as end_date."""
        exp = WorkExperienceLLM(
            position="Dev",
            company="Co",
            start_date="2020-01",
            end_date="Present",
            description="Work",
        )
        assert exp.end_date == "Present"


class TestEducationLLM:
    """Test suite for EducationLLM model."""

    def test_valid_education(self):
        """Should accept required fields."""
        edu = EducationLLM(institution="MIT", degree="Master")
        assert edu.institution == "MIT"
        assert edu.degree == "Master"

    def test_optional_fields_default_to_none(self):
        """Optional fields should default to None."""
        edu = EducationLLM(institution="MIT", degree="Master")
        assert edu.field_of_study is None
        assert edu.start_date is None
        assert edu.end_date is None

    def test_all_fields_populated(self):
        """Should accept all fields populated."""
        edu = EducationLLM(
            institution="MIT",
            degree="PhD",
            field_of_study="Computer Science",
            start_date="2015-09",
            end_date="2020-06",
        )
        assert edu.field_of_study == "Computer Science"

    def test_rejects_missing_institution(self):
        """Should reject missing institution."""
        with pytest.raises(ValidationError):
            EducationLLM(degree="Master")  # type: ignore


class TestCertificationLLM:
    """Test suite for CertificationLLM model."""

    def test_valid_certification(self):
        """Should accept required name field."""
        cert = CertificationLLM(name="AWS Solutions Architect")
        assert cert.name == "AWS Solutions Architect"

    def test_optional_fields_default_to_none(self):
        """Optional fields should default to None."""
        cert = CertificationLLM(name="CKA")
        assert cert.issuing_organization is None
        assert cert.issue_date is None
        assert cert.expiration_date is None

    def test_all_fields_populated(self):
        """Should accept all fields populated."""
        cert = CertificationLLM(
            name="AWS Solutions Architect",
            issuing_organization="Amazon",
            issue_date="2023-01",
            expiration_date="2026-01",
        )
        assert cert.issuing_organization == "Amazon"

    def test_rejects_missing_name(self):
        """Should reject missing name."""
        with pytest.raises(ValidationError):
            CertificationLLM()  # type: ignore


class TestLanguageLLM:
    """Test suite for LanguageLLM model."""

    def test_valid_language(self):
        """Should accept required name field."""
        lang = LanguageLLM(name="French")
        assert lang.name == "French"

    def test_optional_proficiency(self):
        """Proficiency should default to None."""
        lang = LanguageLLM(name="English")
        assert lang.proficiency is None

    def test_with_proficiency(self):
        """Should accept proficiency field."""
        lang = LanguageLLM(name="English", proficiency="Native")
        assert lang.proficiency == "Native"

    def test_rejects_missing_name(self):
        """Should reject missing name."""
        with pytest.raises(ValidationError):
            LanguageLLM()  # type: ignore


class TestExtractedProfileLLM:
    """Test suite for ExtractedProfileLLM model."""

    def test_minimal_valid_profile(self):
        """Should accept with only required fields."""
        profile = ExtractedProfileLLM(
            job_title="Developer",
            location="Paris",
            bio="A developer",
        )
        assert profile.job_title == "Developer"
        assert profile.location == "Paris"
        assert profile.bio == "A developer"

    def test_optional_fields_default_properly(self):
        """Optional fields should default to None/empty list."""
        profile = ExtractedProfileLLM(
            job_title="Dev",
            location="Paris",
            bio="Bio",
        )
        assert profile.full_name is None
        assert profile.email is None
        assert profile.phone is None
        assert profile.years_of_experience is None
        assert profile.work_experience == []
        assert profile.education == []
        assert profile.certifications == []
        assert profile.languages == []
        assert profile.technos == []

    def test_full_profile_with_nested_objects(self):
        """Should accept nested work_experience, education, certifications, languages."""
        profile = ExtractedProfileLLM(
            full_name="John Doe",
            email="john@example.com",
            phone="+33612345678",
            job_title="Senior Dev",
            location="Paris",
            bio="Experienced developer",
            years_of_experience=10,
            work_experience=[
                WorkExperienceLLM(
                    position="Dev",
                    company="Co",
                    start_date="2020-01",
                    end_date="Present",
                    description="Work",
                )
            ],
            education=[EducationLLM(institution="MIT", degree="Master")],
            certifications=[CertificationLLM(name="CKA")],
            languages=[LanguageLLM(name="English", proficiency="Native")],
            technos=["Python", "FastAPI"],
        )
        assert len(profile.work_experience) == 1
        assert len(profile.education) == 1
        assert len(profile.certifications) == 1
        assert len(profile.languages) == 1
        assert profile.technos == ["Python", "FastAPI"]

    def test_rejects_missing_required_fields(self):
        """Should reject missing required fields."""
        with pytest.raises(ValidationError):
            ExtractedProfileLLM()  # type: ignore


class TestResumeExtractionResult:
    """Test suite for ResumeExtractionResult model."""

    def test_valid_result(self):
        """Should accept extracted_profile and raw_text."""
        profile = Profile(job_title="Dev", location="Paris", bio="Bio")
        result = ResumeExtractionResult(
            extracted_profile=profile,
            raw_text="John Doe\nSenior Developer\nParis",
        )
        assert result.extracted_profile.job_title == "Dev"
        assert "John Doe" in result.raw_text

    def test_rejects_missing_profile(self):
        """Should reject missing extracted_profile."""
        with pytest.raises(ValidationError):
            ResumeExtractionResult(raw_text="some text")  # type: ignore

    def test_rejects_missing_raw_text(self):
        """Should reject missing raw_text."""
        profile = Profile(job_title="Dev", location="Paris", bio="Bio")
        with pytest.raises(ValidationError):
            ResumeExtractionResult(extracted_profile=profile)  # type: ignore


class TestLLMDtoInit:
    """Test that __init__.py re-exports all expected classes."""

    def test_exports_all_classes(self):
        """All DTOs should be importable from the package."""
        from infrastructure.dto.llm import (
            WorkExperienceLLM,
            EducationLLM,
            CertificationLLM,
            LanguageLLM,
            ExtractedProfileLLM,
            ResumeExtractionResult,
        )
        assert WorkExperienceLLM is not None
        assert EducationLLM is not None
        assert CertificationLLM is not None
        assert LanguageLLM is not None
        assert ExtractedProfileLLM is not None
        assert ResumeExtractionResult is not None
