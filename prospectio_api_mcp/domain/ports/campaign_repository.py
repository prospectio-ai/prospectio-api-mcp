from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from domain.entities.campaign import Campaign, CampaignEntity
from domain.entities.campaign_result import CampaignMessage
from domain.entities.contact import Contact
from domain.entities.company import Company


class CampaignRepositoryPort(ABC):
    """
    Abstract port interface for campaign persistence operations.
    """

    @abstractmethod
    async def create_campaign(self, campaign: Campaign) -> Campaign:
        """
        Create a new campaign in the database.

        Args:
            campaign (Campaign): The campaign entity to create.

        Returns:
            Campaign: The created campaign with assigned ID.
        """
        pass

    @abstractmethod
    async def get_campaign_by_id(self, campaign_id: str) -> Optional[Campaign]:
        """
        Retrieve a campaign by its ID.

        Args:
            campaign_id (str): The unique identifier of the campaign.

        Returns:
            Optional[Campaign]: The campaign entity if found, otherwise None.
        """
        pass

    @abstractmethod
    async def get_campaigns(self, offset: int, limit: int) -> CampaignEntity:
        """
        Retrieve campaigns with pagination.

        Args:
            offset (int): Number of campaigns to skip.
            limit (int): Maximum number of campaigns to return.

        Returns:
            CampaignEntity: Entity containing list of campaigns and pagination info.
        """
        pass

    @abstractmethod
    async def update_campaign(self, campaign: Campaign) -> Campaign:
        """
        Update an existing campaign.

        Args:
            campaign (Campaign): The campaign entity with updated fields.

        Returns:
            Campaign: The updated campaign entity.
        """
        pass

    @abstractmethod
    async def save_message(self, message: CampaignMessage) -> CampaignMessage:
        """
        Save a campaign message to the database.

        Args:
            message (CampaignMessage): The message entity to save.

        Returns:
            CampaignMessage: The saved message with assigned ID.
        """
        pass

    @abstractmethod
    async def get_campaign_messages(
        self, campaign_id: str, offset: int, limit: int
    ) -> List[CampaignMessage]:
        """
        Retrieve messages for a specific campaign with pagination.

        Args:
            campaign_id (str): The campaign ID to get messages for.
            offset (int): Number of messages to skip.
            limit (int): Maximum number of messages to return.

        Returns:
            List[CampaignMessage]: List of campaign messages.
        """
        pass

    @abstractmethod
    async def get_contacts_without_messages(self) -> List[Tuple[Contact, Company]]:
        """
        Retrieve all contacts that don't have any messages generated yet.
        This ensures each contact only receives one message ever.

        Returns:
            List[Tuple[Contact, Company]]: List of contact and company pairs
                for contacts without existing messages.
        """
        pass

    @abstractmethod
    async def contact_has_message(self, contact_id: str) -> bool:
        """
        Check if a contact already has a message generated.

        Args:
            contact_id (str): The contact ID to check.

        Returns:
            bool: True if contact has a message, False otherwise.
        """
        pass

    @abstractmethod
    async def get_failed_messages_with_contacts(
        self, campaign_id: str
    ) -> List[Tuple[CampaignMessage, Contact, Company]]:
        """
        Return failed messages with their associated contact and company.

        Args:
            campaign_id (str): The campaign ID to get failed messages for.

        Returns:
            List[Tuple[CampaignMessage, Contact, Company]]: List of failed message,
                contact, and company triples.
        """
        pass

    @abstractmethod
    async def delete_message(self, message_id: str) -> None:
        """
        Delete a message record by ID.

        Args:
            message_id (str): The unique identifier of the message to delete.
        """
        pass
