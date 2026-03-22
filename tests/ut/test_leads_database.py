"""
Unit tests for LeadsDatabase conversion methods.

Tests the private conversion methods between domain entities and database models
without requiring a real database connection.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock

from domain.entities.company import Company
from domain.entities.contact import Contact
from domain.entities.job import Job
from infrastructure.services.leads_database import LeadsDatabase


class TestLeadsDatabaseConversions:
    """Test suite for LeadsDatabase entity conversion methods."""

    @pytest.fixture
    def leads_db(self) -> LeadsDatabase:
        """Create a LeadsDatabase instance with a dummy URL (no real connection needed)."""
        return LeadsDatabase("sqlite+aiosqlite:///:memory:")

    # --- _convert_company_to_db ---

    def test_convert_company_to_db_full_data(self, leads_db: LeadsDatabase):
        """Should convert a fully populated Company to CompanyDB."""
        company = Company(
            id="comp-123",
            name="Acme Corp",
            industry="Technology",
            compatibility="85",
            source="jsearch",
            location="Paris, France",
            size="50-200",
            revenue="10M-50M",
            website="https://acme.com",
            description="Leading tech company",
            opportunities=["AI", "Cloud"],
        )
        result = leads_db._convert_company_to_db(company)

        assert result.id == "comp-123"
        assert result.name == "Acme Corp"
        assert result.industry == "Technology"
        assert result.compatibility == "85"
        assert result.source == "jsearch"
        assert result.location == "Paris, France"
        assert result.size == "50-200"
        assert result.revenue == "10M-50M"
        assert result.website == "https://acme.com"
        assert result.description == "Leading tech company"
        assert result.opportunities == ["AI", "Cloud"]

    def test_convert_company_to_db_minimal_data(self, leads_db: LeadsDatabase):
        """Should convert a Company with only required fields."""
        company = Company(name="Minimal Corp")
        result = leads_db._convert_company_to_db(company)

        assert result.name == "Minimal Corp"
        assert result.id is None
        assert result.industry is None
        assert result.website is None

    # --- _convert_job_to_db ---

    def test_convert_job_to_db_full_data(self, leads_db: LeadsDatabase):
        """Should convert a fully populated Job to JobDB."""
        job = Job(
            id="job-456",
            company_id="comp-123",
            date_creation="2025-01-15T10:30:00",
            description="Senior Python Developer position",
            job_title="Senior Python Developer",
            location="Paris, France",
            salary="80K-120K EUR",
            job_seniority="senior",
            job_type="fulltime",
            sectors="Technology",
            apply_url=["https://acme.com/apply"],
            compatibility_score=85,
        )
        result = leads_db._convert_job_to_db(job)

        assert result.id == "job-456"
        assert result.company_id == "comp-123"
        assert result.description == "Senior Python Developer position"
        assert result.job_title == "Senior Python Developer"
        assert result.location == "Paris, France"
        assert result.salary == "80K-120K EUR"
        assert result.job_seniority == "senior"
        assert result.job_type == "fulltime"
        assert result.sectors == "Technology"
        assert result.apply_url == ["https://acme.com/apply"]
        assert result.compatibility_score == 85
        assert isinstance(result.date_creation, datetime)

    def test_convert_job_to_db_no_date_creation(self, leads_db: LeadsDatabase):
        """Should handle missing date_creation by using current time."""
        job = Job(
            id="job-789",
            job_title="Developer",
            date_creation=None,
        )
        result = leads_db._convert_job_to_db(job)

        assert result.id == "job-789"
        assert isinstance(result.date_creation, datetime)

    # --- _convert_contact_to_db ---

    def test_convert_contact_to_db_full_data(self, leads_db: LeadsDatabase):
        """Should convert a fully populated Contact to ContactDB."""
        contact = Contact(
            company_id="comp-123",
            job_id="job-456",
            name="Marie Dupont",
            email=["marie@acme.com", "marie.dupont@gmail.com"],
            title="CTO",
            phone="+33612345678",
            profile_url="https://linkedin.com/in/marie-dupont",
            short_description="Tech leader with 15 years experience",
            full_bio="Marie Dupont is a seasoned technology executive...",
            confidence_score=85,
            validation_status="verified",
            validation_reasons=["Email matches company domain", "LinkedIn profile found"],
        )
        result = leads_db._convert_contact_to_db(contact)

        assert result.company_id == "comp-123"
        assert result.job_id == "job-456"
        assert result.name == "Marie Dupont"
        assert result.email == ["marie@acme.com", "marie.dupont@gmail.com"]
        assert result.title == "CTO"
        assert result.phone == "+33612345678"
        assert result.profile_url == "https://linkedin.com/in/marie-dupont"
        assert result.short_description == "Tech leader with 15 years experience"
        assert result.full_bio == "Marie Dupont is a seasoned technology executive..."
        assert result.confidence_score == 85
        assert result.validation_status == "verified"
        assert result.validation_reasons == ["Email matches company domain", "LinkedIn profile found"]

    def test_convert_contact_to_db_minimal_data(self, leads_db: LeadsDatabase):
        """Should convert a Contact with only minimal fields."""
        contact = Contact(name="John Doe")
        result = leads_db._convert_contact_to_db(contact)

        assert result.name == "John Doe"
        assert result.email is None
        assert result.company_id is None

    # --- _convert_db_to_job ---

    def test_convert_db_to_job_full_data(self, leads_db: LeadsDatabase):
        """Should convert a JobDB to domain Job entity."""
        job_db = MagicMock()
        job_db.id = "job-456"
        job_db.company_id = "comp-123"
        job_db.date_creation = datetime(2025, 1, 15, 10, 30)
        job_db.description = "Python Developer role"
        job_db.job_title = "Python Developer"
        job_db.location = "Paris"
        job_db.salary = "80K-120K"
        job_db.job_seniority = "senior"
        job_db.job_type = "fulltime"
        job_db.sectors = "Tech"
        job_db.apply_url = ["https://apply.com"]
        job_db.compatibility_score = 90

        result = leads_db._convert_db_to_job(job_db, "Acme Corp")

        assert result.id == "job-456"
        assert result.company_id == "comp-123"
        assert result.company_name == "Acme Corp"
        assert result.description == "Python Developer role"
        assert result.job_title == "Python Developer"
        assert result.location == "Paris"
        assert result.salary == "80K-120K"
        assert result.job_seniority == "senior"
        assert result.job_type == "fulltime"
        assert result.sectors == "Tech"
        assert result.apply_url == ["https://apply.com"]
        assert result.compatibility_score == 90
        assert "2025-01-15" in result.date_creation

    def test_convert_db_to_job_no_date_creation(self, leads_db: LeadsDatabase):
        """Should handle None date_creation in JobDB."""
        job_db = MagicMock()
        job_db.id = "job-123"
        job_db.company_id = None
        job_db.date_creation = None
        job_db.description = None
        job_db.job_title = "Dev"
        job_db.location = None
        job_db.salary = None
        job_db.job_seniority = None
        job_db.job_type = None
        job_db.sectors = None
        job_db.apply_url = None
        job_db.compatibility_score = None

        result = leads_db._convert_db_to_job(job_db)

        assert result.id == "job-123"
        assert result.date_creation is None
        assert result.company_name is None

    # --- _convert_db_to_company ---

    def test_convert_db_to_company_full_data(self, leads_db: LeadsDatabase):
        """Should convert a CompanyDB to domain Company entity."""
        company_db = MagicMock()
        company_db.id = "comp-123"
        company_db.name = "Acme Corp"
        company_db.industry = "Technology"
        company_db.compatibility = "85"
        company_db.source = "jsearch"
        company_db.location = "Paris"
        company_db.size = "50-200"
        company_db.revenue = "10M"
        company_db.website = "https://acme.com"
        company_db.description = "Tech company"
        company_db.opportunities = ["AI"]

        result = leads_db._convert_db_to_company(company_db)

        assert isinstance(result, Company)
        assert result.id == "comp-123"
        assert result.name == "Acme Corp"
        assert result.industry == "Technology"
        assert result.compatibility == "85"
        assert result.source == "jsearch"
        assert result.location == "Paris"
        assert result.size == "50-200"
        assert result.revenue == "10M"
        assert result.website == "https://acme.com"
        assert result.description == "Tech company"
        assert result.opportunities == ["AI"]

    # --- _convert_db_to_contact ---

    def test_convert_db_to_contact_full_data(self, leads_db: LeadsDatabase):
        """Should convert a ContactDB to domain Contact entity."""
        contact_db = MagicMock()
        contact_db.id = "contact-789"
        contact_db.company_id = "comp-123"
        contact_db.job_id = "job-456"
        contact_db.name = "Jean Martin"
        contact_db.email = ["jean@acme.com"]
        contact_db.title = "VP Engineering"
        contact_db.phone = "+33698765432"
        contact_db.profile_url = "https://linkedin.com/in/jean"
        contact_db.short_description = "Engineering leader"
        contact_db.full_bio = "Jean Martin is an engineering leader..."
        contact_db.confidence_score = 75
        contact_db.validation_status = "verified"
        contact_db.validation_reasons = ["Email matches domain"]

        result = leads_db._convert_db_to_contact(contact_db, "Acme Corp", "VP Engineering")

        assert isinstance(result, Contact)
        assert result.id == "contact-789"
        assert result.company_id == "comp-123"
        assert result.company_name == "Acme Corp"
        assert result.job_id == "job-456"
        assert result.job_title == "VP Engineering"
        assert result.name == "Jean Martin"
        assert result.email == ["jean@acme.com"]
        assert result.title == "VP Engineering"
        assert result.phone == "+33698765432"
        assert result.profile_url == "https://linkedin.com/in/jean"
        assert result.confidence_score == 75

    def test_convert_db_to_contact_with_none_names(self, leads_db: LeadsDatabase):
        """Should handle None company_name and job_title gracefully."""
        contact_db = MagicMock()
        contact_db.id = "contact-001"
        contact_db.company_id = None
        contact_db.job_id = None
        contact_db.name = "Unknown Person"
        contact_db.email = None
        contact_db.title = None
        contact_db.phone = None
        contact_db.profile_url = None
        contact_db.short_description = None
        contact_db.full_bio = None
        contact_db.confidence_score = None
        contact_db.validation_status = None
        contact_db.validation_reasons = None

        result = leads_db._convert_db_to_contact(contact_db, None, None)

        assert result.company_name is None
        assert result.job_title is None
        assert result.name == "Unknown Person"
