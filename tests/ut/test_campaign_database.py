"""
Tests for infrastructure/services/campaign_database.py - CampaignDatabase service.
Tests cover the conversion methods (pure logic) and the constructor.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from infrastructure.services.campaign_database import CampaignDatabase, MIN_CONFIDENCE_SCORE_FOR_CAMPAIGN
from domain.entities.campaign import Campaign, CampaignStatus
from domain.entities.campaign_result import CampaignMessage
from domain.entities.contact import Contact
from domain.entities.company import Company
from domain.ports.campaign_repository import CampaignRepositoryPort


class TestCampaignDatabaseInit:
    """Test suite for CampaignDatabase initialization."""

    def test_stores_database_url(self):
        """Should store the database URL."""
        db = CampaignDatabase("postgresql+asyncpg://user:pass@localhost/test")
        assert db.database_url == "postgresql+asyncpg://user:pass@localhost/test"

    def test_creates_engine(self):
        """Should create an async engine."""
        db = CampaignDatabase("postgresql+asyncpg://user:pass@localhost/test")
        assert db.engine is not None

    def test_implements_campaign_repository_port(self):
        """CampaignDatabase should implement CampaignRepositoryPort."""
        db = CampaignDatabase("postgresql+asyncpg://user:pass@localhost/test")
        assert isinstance(db, CampaignRepositoryPort)


class TestCampaignDatabaseConversions:
    """Test suite for CampaignDatabase private conversion methods."""

    @pytest.fixture
    def db(self):
        """Create a CampaignDatabase instance."""
        return CampaignDatabase("postgresql+asyncpg://user:pass@localhost/test")

    def test_convert_db_to_campaign(self, db):
        """Should convert CampaignDB to Campaign domain entity."""
        now = datetime.now(timezone.utc)
        campaign_db = MagicMock()
        campaign_db.id = "camp-123"
        campaign_db.name = "Test Campaign"
        campaign_db.description = "A test"
        campaign_db.status = "in_progress"
        campaign_db.created_at = now
        campaign_db.updated_at = now
        campaign_db.completed_at = None
        campaign_db.total_contacts = 10
        campaign_db.successful = 5
        campaign_db.failed = 2

        result = db._convert_db_to_campaign(campaign_db)

        assert isinstance(result, Campaign)
        assert result.id == "camp-123"
        assert result.name == "Test Campaign"
        assert result.description == "A test"
        assert result.status == CampaignStatus.IN_PROGRESS
        assert result.total_contacts == 10
        assert result.successful == 5
        assert result.failed == 2
        assert result.completed_at is None

    def test_convert_db_to_message(self, db):
        """Should convert MessageDB to CampaignMessage domain entity."""
        now = datetime.now(timezone.utc)
        message_db = MagicMock()
        message_db.id = "msg-456"
        message_db.campaign_id = "camp-123"
        message_db.contact_id = "contact-789"
        message_db.contact_name = "Alice"
        message_db.contact_email = ["alice@example.com"]
        message_db.company_name = "TechCorp"
        message_db.subject = "Opportunity"
        message_db.message = "Hello Alice"
        message_db.status = "success"
        message_db.error = None
        message_db.created_at = now

        result = db._convert_db_to_message(message_db)

        assert isinstance(result, CampaignMessage)
        assert result.id == "msg-456"
        assert result.campaign_id == "camp-123"
        assert result.contact_id == "contact-789"
        assert result.contact_name == "Alice"
        assert result.subject == "Opportunity"
        assert result.message == "Hello Alice"
        assert result.status == "success"

    def test_convert_db_to_contact(self, db):
        """Should convert ContactDB to Contact domain entity."""
        contact_db = MagicMock()
        contact_db.id = "contact-1"
        contact_db.company_id = "company-1"
        contact_db.job_id = "job-1"
        contact_db.name = "Bob"
        contact_db.email = ["bob@co.com"]
        contact_db.title = "CTO"
        contact_db.phone = "+33123456789"
        contact_db.profile_url = "https://linkedin.com/in/bob"
        contact_db.short_description = "Tech leader"
        contact_db.full_bio = "Full bio text"
        contact_db.confidence_score = 85
        contact_db.validation_status = "verified"
        contact_db.validation_reasons = ["High confidence"]

        result = db._convert_db_to_contact(contact_db, "TechCorp", "Dev Lead")

        assert isinstance(result, Contact)
        assert result.id == "contact-1"
        assert result.company_name == "TechCorp"
        assert result.job_title == "Dev Lead"
        assert result.name == "Bob"
        assert result.confidence_score == 85
        assert result.validation_status == "verified"

    def test_convert_db_to_company(self, db):
        """Should convert CompanyDB to Company domain entity."""
        company_db = MagicMock()
        company_db.id = "company-1"
        company_db.name = "TechCorp"
        company_db.industry = "Technology"
        company_db.compatibility = "95%"
        company_db.source = "jsearch"
        company_db.location = "Paris"
        company_db.size = "50-200"
        company_db.revenue = "5-10M"
        company_db.website = "https://techcorp.com"
        company_db.description = "A tech company"
        company_db.opportunities = ["Python dev", "AI engineer"]

        result = db._convert_db_to_company(company_db)

        assert isinstance(result, Company)
        assert result.id == "company-1"
        assert result.name == "TechCorp"
        assert result.industry == "Technology"
        assert result.location == "Paris"
        assert result.opportunities == ["Python dev", "AI engineer"]


class TestMinConfidenceScore:
    """Test constants."""

    def test_min_confidence_score_is_70(self):
        """MIN_CONFIDENCE_SCORE_FOR_CAMPAIGN should be 70."""
        assert MIN_CONFIDENCE_SCORE_FOR_CAMPAIGN == 70
