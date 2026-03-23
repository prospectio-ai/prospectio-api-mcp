"""
DEPRECATED: These tests exercise a FakeRepository, not the real implementation.
They should be replaced with real repository integration tests using PostgreSQL
test containers (testcontainers-python) when available. See PROS-12.

Unit tests for the CampaignRepository functionality.

Tests cover:
- create_campaign - verify campaign is created
- get_campaign_by_id - verify campaign is retrieved
- save_message - verify message is saved
- get_contacts_without_messages - verify only contacts without messages are returned
- contact_has_message - verify returns True/False correctly

Uses an in-memory fake repository for testing the expected behavior
without requiring a real database.
"""

import pytest
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from domain.entities.campaign import Campaign, CampaignEntity, CampaignStatus
from domain.entities.campaign_result import CampaignMessage
from domain.entities.contact import Contact
from domain.entities.company import Company
from domain.ports.campaign_repository import CampaignRepositoryPort


class FakeCampaignRepository(CampaignRepositoryPort):
    """
    In-memory fake implementation of CampaignRepositoryPort for testing.
    Simulates database behavior without requiring actual database connection.
    """

    def __init__(self):
        self._campaigns: Dict[str, Campaign] = {}
        self._messages: Dict[str, CampaignMessage] = {}
        self._contacts: Dict[str, Contact] = {}
        self._companies: Dict[str, Company] = {}
        # Track which contacts have messages (by contact_id)
        self._contact_messages: Dict[str, List[str]] = {}  # contact_id -> [message_ids]

    async def create_campaign(self, campaign: Campaign) -> Campaign:
        """Create a new campaign in the fake store."""
        campaign_id = campaign.id or str(uuid4())
        now = datetime.now(timezone.utc)
        created_campaign = Campaign(
            id=campaign_id,
            name=campaign.name,
            description=campaign.description,
            status=campaign.status,
            created_at=campaign.created_at or now,
            updated_at=campaign.updated_at or now,
            completed_at=campaign.completed_at,
            total_contacts=campaign.total_contacts,
            successful=campaign.successful,
            failed=campaign.failed,
        )
        self._campaigns[campaign_id] = created_campaign
        return created_campaign

    async def get_campaign_by_id(self, campaign_id: str) -> Optional[Campaign]:
        """Retrieve a campaign by its ID."""
        return self._campaigns.get(campaign_id)

    async def get_campaigns(self, offset: int, limit: int) -> CampaignEntity:
        """Retrieve campaigns with pagination."""
        all_campaigns = list(self._campaigns.values())
        # Sort by created_at descending
        all_campaigns.sort(key=lambda c: c.created_at or datetime.min, reverse=True)
        paginated = all_campaigns[offset:offset + limit]
        total_pages = (len(all_campaigns) + limit - 1) // limit if limit > 0 else 1
        return CampaignEntity(campaigns=paginated, pages=total_pages)

    async def update_campaign(self, campaign: Campaign) -> Campaign:
        """Update an existing campaign."""
        if campaign.id not in self._campaigns:
            raise ValueError(f"Campaign not found with id: {campaign.id}")
        updated = Campaign(
            id=campaign.id,
            name=campaign.name,
            description=campaign.description,
            status=campaign.status,
            created_at=self._campaigns[campaign.id].created_at,
            updated_at=datetime.now(timezone.utc),
            completed_at=campaign.completed_at,
            total_contacts=campaign.total_contacts,
            successful=campaign.successful,
            failed=campaign.failed,
        )
        self._campaigns[campaign.id] = updated
        return updated

    async def save_message(self, message: CampaignMessage) -> CampaignMessage:
        """Save a campaign message."""
        message_id = message.id or str(uuid4())
        saved_message = CampaignMessage(
            id=message_id,
            campaign_id=message.campaign_id,
            contact_id=message.contact_id,
            contact_name=message.contact_name,
            contact_email=message.contact_email,
            company_name=message.company_name,
            subject=message.subject,
            message=message.message,
            status=message.status,
            error=message.error,
            created_at=message.created_at or datetime.now(timezone.utc),
        )
        self._messages[message_id] = saved_message

        # Track contact -> message relationship
        if message.contact_id not in self._contact_messages:
            self._contact_messages[message.contact_id] = []
        self._contact_messages[message.contact_id].append(message_id)

        return saved_message

    async def get_campaign_messages(
        self, campaign_id: str, offset: int, limit: int
    ) -> List[CampaignMessage]:
        """Retrieve messages for a specific campaign with pagination."""
        campaign_messages = [
            msg for msg in self._messages.values()
            if msg.campaign_id == campaign_id
        ]
        campaign_messages.sort(key=lambda m: m.created_at or datetime.min, reverse=True)
        return campaign_messages[offset:offset + limit]

    async def get_contacts_without_messages(self) -> List[Tuple[Contact, Company]]:
        """Retrieve all contacts that don't have any messages generated yet."""
        result: List[Tuple[Contact, Company]] = []
        for contact_id, contact in self._contacts.items():
            # Only include contacts without messages
            if contact_id not in self._contact_messages:
                company = self._companies.get(contact.company_id)
                if company:
                    result.append((contact, company))
        return result

    async def contact_has_message(self, contact_id: str) -> bool:
        """Check if a contact already has a message generated."""
        return contact_id in self._contact_messages

    async def get_failed_messages_with_contacts(
        self, campaign_id: str
    ) -> List[Tuple[CampaignMessage, Contact, Company]]:
        """Return failed messages with their associated contact and company."""
        result: List[Tuple[CampaignMessage, Contact, Company]] = []
        for msg in self._messages.values():
            if msg.campaign_id == campaign_id and msg.status == "failed":
                contact = self._contacts.get(msg.contact_id)
                if contact and contact.company_id:
                    company = self._companies.get(contact.company_id)
                    if company:
                        result.append((msg, contact, company))
        return result

    async def delete_message(self, message_id: str) -> None:
        """Delete a message record by ID."""
        if message_id in self._messages:
            msg = self._messages[message_id]
            # Clean up contact_messages tracking
            if msg.contact_id in self._contact_messages:
                self._contact_messages[msg.contact_id] = [
                    mid for mid in self._contact_messages[msg.contact_id]
                    if mid != message_id
                ]
                if not self._contact_messages[msg.contact_id]:
                    del self._contact_messages[msg.contact_id]
            del self._messages[message_id]

    # Helper methods for test setup (not in interface)
    def add_contact(self, contact: Contact) -> None:
        """Add a contact to the fake store."""
        self._contacts[contact.id] = contact

    def add_company(self, company: Company) -> None:
        """Add a company to the fake store."""
        self._companies[company.id] = company

    def clear(self) -> None:
        """Reset all data in the fake store."""
        self._campaigns.clear()
        self._messages.clear()
        self._contacts.clear()
        self._companies.clear()
        self._contact_messages.clear()


class TestFakeCampaignRepository:
    """Tests for the CampaignRepository using a fake implementation."""

    @pytest.fixture
    def repository(self) -> FakeCampaignRepository:
        """Create a fresh fake repository for each test."""
        return FakeCampaignRepository()

    @pytest.fixture
    def sample_campaign(self) -> Campaign:
        """Create a sample campaign for testing."""
        return Campaign(
            name="Test Campaign",
            description="Test campaign description",
            status=CampaignStatus.DRAFT,
            total_contacts=10,
            successful=0,
            failed=0,
        )

    @pytest.fixture
    def sample_contact(self) -> Contact:
        """Create a sample contact for testing."""
        return Contact(
            id=str(uuid4()),
            company_id=str(uuid4()),
            company_name="Test Company",
            name="John Doe",
            email=["john.doe@example.com"],
            title="Software Engineer",
        )

    @pytest.fixture
    def sample_company(self, sample_contact: Contact) -> Company:
        """Create a sample company for testing."""
        return Company(
            id=sample_contact.company_id,
            name="Test Company",
            industry="Technology",
            location="Paris",
        )

    @pytest.fixture
    def sample_message(self, sample_contact: Contact) -> CampaignMessage:
        """Create a sample campaign message for testing."""
        return CampaignMessage(
            campaign_id=str(uuid4()),
            contact_id=sample_contact.id,
            contact_name=sample_contact.name,
            contact_email=sample_contact.email,
            company_name=sample_contact.company_name,
            subject="Test Subject",
            message="Test message body",
            status="success",
        )

    # --- create_campaign tests ---

    @pytest.mark.asyncio
    async def test_create_campaign_returns_campaign_with_id(
        self,
        repository: FakeCampaignRepository,
        sample_campaign: Campaign
    ):
        """Should create campaign and assign an ID."""
        result = await repository.create_campaign(sample_campaign)

        assert result.id is not None
        assert len(result.id) > 0

    @pytest.mark.asyncio
    async def test_create_campaign_preserves_name(
        self,
        repository: FakeCampaignRepository,
        sample_campaign: Campaign
    ):
        """Should preserve campaign name."""
        result = await repository.create_campaign(sample_campaign)

        assert result.name == sample_campaign.name

    @pytest.mark.asyncio
    async def test_create_campaign_preserves_description(
        self,
        repository: FakeCampaignRepository,
        sample_campaign: Campaign
    ):
        """Should preserve campaign description."""
        result = await repository.create_campaign(sample_campaign)

        assert result.description == sample_campaign.description

    @pytest.mark.asyncio
    async def test_create_campaign_preserves_status(
        self,
        repository: FakeCampaignRepository,
        sample_campaign: Campaign
    ):
        """Should preserve campaign status."""
        result = await repository.create_campaign(sample_campaign)

        assert result.status == sample_campaign.status

    @pytest.mark.asyncio
    async def test_create_campaign_sets_created_at(
        self,
        repository: FakeCampaignRepository,
        sample_campaign: Campaign
    ):
        """Should set created_at timestamp."""
        result = await repository.create_campaign(sample_campaign)

        assert result.created_at is not None
        assert isinstance(result.created_at, datetime)

    @pytest.mark.asyncio
    async def test_create_campaign_persists_to_store(
        self,
        repository: FakeCampaignRepository,
        sample_campaign: Campaign
    ):
        """Should persist campaign to internal store."""
        result = await repository.create_campaign(sample_campaign)

        assert result.id in repository._campaigns
        stored = repository._campaigns[result.id]
        assert stored.name == sample_campaign.name

    @pytest.mark.asyncio
    async def test_create_campaign_uses_provided_id(
        self,
        repository: FakeCampaignRepository
    ):
        """Should use provided ID if given."""
        custom_id = "custom-campaign-id"
        campaign = Campaign(id=custom_id, name="Custom ID Campaign")

        result = await repository.create_campaign(campaign)

        assert result.id == custom_id

    # --- get_campaign_by_id tests ---

    @pytest.mark.asyncio
    async def test_get_campaign_by_id_returns_existing_campaign(
        self,
        repository: FakeCampaignRepository,
        sample_campaign: Campaign
    ):
        """Should return campaign when it exists."""
        created = await repository.create_campaign(sample_campaign)

        result = await repository.get_campaign_by_id(created.id)

        assert result is not None
        assert result.id == created.id
        assert result.name == created.name

    @pytest.mark.asyncio
    async def test_get_campaign_by_id_returns_none_for_nonexistent(
        self,
        repository: FakeCampaignRepository
    ):
        """Should return None when campaign does not exist."""
        result = await repository.get_campaign_by_id("nonexistent-id")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_campaign_by_id_returns_correct_campaign(
        self,
        repository: FakeCampaignRepository
    ):
        """Should return the correct campaign among multiple."""
        campaign1 = Campaign(name="Campaign 1")
        campaign2 = Campaign(name="Campaign 2")
        campaign3 = Campaign(name="Campaign 3")

        created1 = await repository.create_campaign(campaign1)
        created2 = await repository.create_campaign(campaign2)
        await repository.create_campaign(campaign3)

        result = await repository.get_campaign_by_id(created2.id)

        assert result is not None
        assert result.name == "Campaign 2"
        assert result.id == created2.id

    # --- save_message tests ---

    @pytest.mark.asyncio
    async def test_save_message_returns_message_with_id(
        self,
        repository: FakeCampaignRepository,
        sample_message: CampaignMessage
    ):
        """Should save message and assign an ID."""
        result = await repository.save_message(sample_message)

        assert result.id is not None
        assert len(result.id) > 0

    @pytest.mark.asyncio
    async def test_save_message_preserves_subject(
        self,
        repository: FakeCampaignRepository,
        sample_message: CampaignMessage
    ):
        """Should preserve message subject."""
        result = await repository.save_message(sample_message)

        assert result.subject == sample_message.subject

    @pytest.mark.asyncio
    async def test_save_message_preserves_message_body(
        self,
        repository: FakeCampaignRepository,
        sample_message: CampaignMessage
    ):
        """Should preserve message body."""
        result = await repository.save_message(sample_message)

        assert result.message == sample_message.message

    @pytest.mark.asyncio
    async def test_save_message_preserves_contact_id(
        self,
        repository: FakeCampaignRepository,
        sample_message: CampaignMessage
    ):
        """Should preserve contact_id."""
        result = await repository.save_message(sample_message)

        assert result.contact_id == sample_message.contact_id

    @pytest.mark.asyncio
    async def test_save_message_preserves_campaign_id(
        self,
        repository: FakeCampaignRepository,
        sample_message: CampaignMessage
    ):
        """Should preserve campaign_id."""
        result = await repository.save_message(sample_message)

        assert result.campaign_id == sample_message.campaign_id

    @pytest.mark.asyncio
    async def test_save_message_sets_created_at(
        self,
        repository: FakeCampaignRepository,
        sample_message: CampaignMessage
    ):
        """Should set created_at timestamp."""
        result = await repository.save_message(sample_message)

        assert result.created_at is not None
        assert isinstance(result.created_at, datetime)

    @pytest.mark.asyncio
    async def test_save_message_persists_to_store(
        self,
        repository: FakeCampaignRepository,
        sample_message: CampaignMessage
    ):
        """Should persist message to internal store."""
        result = await repository.save_message(sample_message)

        assert result.id in repository._messages
        stored = repository._messages[result.id]
        assert stored.subject == sample_message.subject

    @pytest.mark.asyncio
    async def test_save_message_tracks_contact_message_relationship(
        self,
        repository: FakeCampaignRepository,
        sample_message: CampaignMessage
    ):
        """Should track that contact now has a message."""
        result = await repository.save_message(sample_message)

        assert sample_message.contact_id in repository._contact_messages
        assert result.id in repository._contact_messages[sample_message.contact_id]

    # --- get_contacts_without_messages tests ---

    @pytest.mark.asyncio
    async def test_get_contacts_without_messages_returns_contacts_without_messages(
        self,
        repository: FakeCampaignRepository,
        sample_contact: Contact,
        sample_company: Company
    ):
        """Should return contacts that have no messages."""
        repository.add_contact(sample_contact)
        repository.add_company(sample_company)

        result = await repository.get_contacts_without_messages()

        assert len(result) == 1
        contact, company = result[0]
        assert contact.id == sample_contact.id
        assert company.id == sample_company.id

    @pytest.mark.asyncio
    async def test_get_contacts_without_messages_excludes_contacts_with_messages(
        self,
        repository: FakeCampaignRepository,
        sample_contact: Contact,
        sample_company: Company,
        sample_message: CampaignMessage
    ):
        """Should exclude contacts that already have messages."""
        repository.add_contact(sample_contact)
        repository.add_company(sample_company)

        # Save a message for the contact
        await repository.save_message(sample_message)

        result = await repository.get_contacts_without_messages()

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_contacts_without_messages_returns_only_contacts_without_messages(
        self,
        repository: FakeCampaignRepository
    ):
        """Should return only contacts without messages in mixed scenario."""
        # Create contacts and companies
        company1_id = str(uuid4())
        company2_id = str(uuid4())
        contact1 = Contact(id=str(uuid4()), company_id=company1_id, name="Contact 1")
        contact2 = Contact(id=str(uuid4()), company_id=company2_id, name="Contact 2")
        company1 = Company(id=company1_id, name="Company 1")
        company2 = Company(id=company2_id, name="Company 2")

        repository.add_contact(contact1)
        repository.add_contact(contact2)
        repository.add_company(company1)
        repository.add_company(company2)

        # Save message only for contact1
        message = CampaignMessage(
            contact_id=contact1.id,
            subject="Subject",
            message="Body"
        )
        await repository.save_message(message)

        result = await repository.get_contacts_without_messages()

        assert len(result) == 1
        contact, company = result[0]
        assert contact.id == contact2.id
        assert company.id == company2_id

    @pytest.mark.asyncio
    async def test_get_contacts_without_messages_returns_empty_when_all_have_messages(
        self,
        repository: FakeCampaignRepository
    ):
        """Should return empty list when all contacts have messages."""
        company_id = str(uuid4())
        contact = Contact(id=str(uuid4()), company_id=company_id, name="Contact")
        company = Company(id=company_id, name="Company")

        repository.add_contact(contact)
        repository.add_company(company)

        message = CampaignMessage(
            contact_id=contact.id,
            subject="Subject",
            message="Body"
        )
        await repository.save_message(message)

        result = await repository.get_contacts_without_messages()

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_contacts_without_messages_returns_empty_when_no_contacts(
        self,
        repository: FakeCampaignRepository
    ):
        """Should return empty list when no contacts exist."""
        result = await repository.get_contacts_without_messages()

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_contacts_without_messages_excludes_contacts_without_companies(
        self,
        repository: FakeCampaignRepository
    ):
        """Should exclude contacts that don't have associated companies."""
        contact = Contact(id=str(uuid4()), company_id=str(uuid4()), name="Contact")
        repository.add_contact(contact)
        # Don't add the company

        result = await repository.get_contacts_without_messages()

        assert len(result) == 0

    # --- contact_has_message tests ---

    @pytest.mark.asyncio
    async def test_contact_has_message_returns_false_when_no_message(
        self,
        repository: FakeCampaignRepository,
        sample_contact: Contact
    ):
        """Should return False when contact has no messages."""
        repository.add_contact(sample_contact)

        result = await repository.contact_has_message(sample_contact.id)

        assert result is False

    @pytest.mark.asyncio
    async def test_contact_has_message_returns_true_when_message_exists(
        self,
        repository: FakeCampaignRepository,
        sample_contact: Contact,
        sample_message: CampaignMessage
    ):
        """Should return True when contact has a message."""
        repository.add_contact(sample_contact)
        await repository.save_message(sample_message)

        result = await repository.contact_has_message(sample_contact.id)

        assert result is True

    @pytest.mark.asyncio
    async def test_contact_has_message_returns_false_for_nonexistent_contact(
        self,
        repository: FakeCampaignRepository
    ):
        """Should return False for non-existent contact ID."""
        result = await repository.contact_has_message("nonexistent-id")

        assert result is False

    @pytest.mark.asyncio
    async def test_contact_has_message_returns_true_after_multiple_messages(
        self,
        repository: FakeCampaignRepository,
        sample_contact: Contact
    ):
        """Should return True when contact has multiple messages."""
        repository.add_contact(sample_contact)

        # Save multiple messages for the same contact
        message1 = CampaignMessage(
            campaign_id=str(uuid4()),
            contact_id=sample_contact.id,
            subject="Subject 1",
            message="Body 1"
        )
        message2 = CampaignMessage(
            campaign_id=str(uuid4()),
            contact_id=sample_contact.id,
            subject="Subject 2",
            message="Body 2"
        )
        await repository.save_message(message1)
        await repository.save_message(message2)

        result = await repository.contact_has_message(sample_contact.id)

        assert result is True

    @pytest.mark.asyncio
    async def test_contact_has_message_independent_per_contact(
        self,
        repository: FakeCampaignRepository
    ):
        """Should track messages independently per contact."""
        contact1 = Contact(id=str(uuid4()), name="Contact 1")
        contact2 = Contact(id=str(uuid4()), name="Contact 2")
        repository.add_contact(contact1)
        repository.add_contact(contact2)

        # Only save message for contact1
        message = CampaignMessage(
            contact_id=contact1.id,
            subject="Subject",
            message="Body"
        )
        await repository.save_message(message)

        assert await repository.contact_has_message(contact1.id) is True
        assert await repository.contact_has_message(contact2.id) is False

    # --- Integration tests ---

    @pytest.mark.asyncio
    async def test_full_campaign_workflow(
        self,
        repository: FakeCampaignRepository
    ):
        """Should handle a complete campaign workflow correctly."""
        # Create campaign
        campaign = Campaign(
            name="Integration Test Campaign",
            description="Testing full workflow",
            status=CampaignStatus.DRAFT
        )
        created_campaign = await repository.create_campaign(campaign)
        assert created_campaign.id is not None

        # Add contacts and companies
        company_id = str(uuid4())
        contact1 = Contact(id=str(uuid4()), company_id=company_id, name="Contact 1")
        contact2 = Contact(id=str(uuid4()), company_id=company_id, name="Contact 2")
        company = Company(id=company_id, name="Test Company")

        repository.add_contact(contact1)
        repository.add_contact(contact2)
        repository.add_company(company)

        # Initially both contacts should be without messages
        contacts_without_messages = await repository.get_contacts_without_messages()
        assert len(contacts_without_messages) == 2

        # Save message for contact1
        message1 = CampaignMessage(
            campaign_id=created_campaign.id,
            contact_id=contact1.id,
            contact_name=contact1.name,
            subject="Hello",
            message="Test message"
        )
        saved_message = await repository.save_message(message1)
        assert saved_message.id is not None

        # Now only contact2 should be without messages
        contacts_without_messages = await repository.get_contacts_without_messages()
        assert len(contacts_without_messages) == 1
        assert contacts_without_messages[0][0].id == contact2.id

        # Verify contact_has_message
        assert await repository.contact_has_message(contact1.id) is True
        assert await repository.contact_has_message(contact2.id) is False

        # Retrieve campaign
        retrieved = await repository.get_campaign_by_id(created_campaign.id)
        assert retrieved is not None
        assert retrieved.name == "Integration Test Campaign"
