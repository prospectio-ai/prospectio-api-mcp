"""Fake repository implementations for testing."""

from typing import List, Optional, Tuple
from uuid import uuid4

from domain.entities.campaign import Campaign, CampaignEntity
from domain.entities.campaign_result import CampaignMessage
from domain.entities.contact import Contact
from domain.entities.company import Company
from domain.entities.profile import Profile
from domain.entities.leads import Leads
from domain.ports.campaign_repository import CampaignRepositoryPort
from domain.ports.profile_respository import ProfileRepositoryPort


class FakeCampaignRepository(CampaignRepositoryPort):
    """In-memory fake implementation of CampaignRepositoryPort for testing."""

    def __init__(self):
        self._campaigns: dict[str, Campaign] = {}
        self._messages: dict[str, CampaignMessage] = {}
        self._contacts_with_companies: List[Tuple[Contact, Company]] = []
        self._failed_messages_with_contacts: dict[str, List[Tuple[CampaignMessage, Contact, Company]]] = {}

    async def create_campaign(self, campaign: Campaign) -> Campaign:
        """Create a new campaign with auto-generated ID."""
        if campaign.id is None:
            campaign.id = str(uuid4())
        self._campaigns[campaign.id] = campaign
        return campaign

    async def get_campaign_by_id(self, campaign_id: str) -> Optional[Campaign]:
        """Retrieve a campaign by its ID."""
        return self._campaigns.get(campaign_id)

    async def get_campaigns(self, offset: int, limit: int) -> CampaignEntity:
        """Retrieve campaigns with pagination."""
        campaigns = list(self._campaigns.values())
        paginated = campaigns[offset : offset + limit]
        pages = (len(campaigns) + limit - 1) // limit if limit > 0 else 1
        return CampaignEntity(campaigns=paginated, pages=pages)

    async def update_campaign(self, campaign: Campaign) -> Campaign:
        """Update an existing campaign."""
        if campaign.id:
            self._campaigns[campaign.id] = campaign
        return campaign

    async def save_message(self, message: CampaignMessage) -> CampaignMessage:
        """Save a campaign message with auto-generated ID."""
        if message.id is None:
            message.id = str(uuid4())
        self._messages[message.id] = message
        return message

    async def get_campaign_messages(
        self, campaign_id: str, offset: int, limit: int
    ) -> List[CampaignMessage]:
        """Retrieve messages for a specific campaign with pagination."""
        campaign_messages = [
            m for m in self._messages.values() if m.campaign_id == campaign_id
        ]
        return campaign_messages[offset : offset + limit]

    async def get_contacts_without_messages(self) -> List[Tuple[Contact, Company]]:
        """Return pre-configured contacts without messages."""
        return self._contacts_with_companies

    async def contact_has_message(self, contact_id: str) -> bool:
        """Check if a contact already has a message generated."""
        return any(m.contact_id == contact_id for m in self._messages.values())

    async def get_failed_messages_with_contacts(
        self, campaign_id: str
    ) -> List[Tuple[CampaignMessage, Contact, Company]]:
        """Return failed messages with their associated contact and company."""
        return self._failed_messages_with_contacts.get(campaign_id, [])

    async def delete_message(self, message_id: str) -> None:
        """Delete a message record by ID."""
        self._messages.pop(message_id, None)

    # Helper methods for test setup (not in interface)
    def add_contacts_with_companies(
        self, contacts_with_companies: List[Tuple[Contact, Company]]
    ) -> None:
        """Configure contacts that will be returned by get_contacts_without_messages."""
        self._contacts_with_companies = contacts_with_companies

    def get_all_messages(self) -> List[CampaignMessage]:
        """Return all saved messages."""
        return list(self._messages.values())

    def get_all_campaigns(self) -> List[Campaign]:
        """Return all campaigns."""
        return list(self._campaigns.values())

    def add_failed_messages_with_contacts(
        self,
        campaign_id: str,
        failed_messages: List[Tuple[CampaignMessage, Contact, Company]],
    ) -> None:
        """Configure failed messages that will be returned by get_failed_messages_with_contacts."""
        self._failed_messages_with_contacts[campaign_id] = failed_messages

    def clear(self) -> None:
        """Reset the fake repository."""
        self._campaigns.clear()
        self._messages.clear()
        self._contacts_with_companies.clear()
        self._failed_messages_with_contacts.clear()


class FakeProfileRepository(ProfileRepositoryPort):
    """In-memory fake implementation of ProfileRepositoryPort for testing."""

    def __init__(self):
        self._profile: Optional[Profile] = None

    async def upsert_profile(self, profile: Profile) -> Leads:
        """Store the profile."""
        self._profile = profile
        # Return empty Leads as this is not the primary use case
        return Leads(companies=None, jobs=None, contacts=None, pages=0)  # type: ignore

    async def get_profile(self) -> Optional[Profile]:
        """Retrieve the stored profile."""
        return self._profile

    async def delete_profile(self) -> None:
        """Delete the stored profile."""
        self._profile = None

    # Helper methods for test setup
    def set_profile(self, profile: Profile) -> None:
        """Configure the profile to be returned."""
        self._profile = profile

    def clear(self) -> None:
        """Reset the fake repository."""
        self._profile = None
