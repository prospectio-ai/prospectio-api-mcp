import datetime
from typing import AsyncGenerator, Optional
import logging
from domain.entities.campaign import Campaign, CampaignStatus
from domain.entities.campaign_result import CampaignMessage
from domain.entities.contact import Contact
from domain.entities.company import Company
from domain.entities.sse_events import (
    SSEEvent,
    SSEEventType,
    CampaignProgressData,
    MessageGeneratedData,
)
from domain.ports.generate_message import GenerateMessagePort
from domain.ports.profile_respository import ProfileRepositoryPort
from domain.ports.campaign_repository import CampaignRepositoryPort


logger = logging.getLogger(__name__)


def _utc_now() -> datetime.datetime:
    """Return current UTC datetime."""
    return datetime.datetime.now(datetime.UTC)


class GenerateCampaignStreamUseCase:
    """
    Use case for generating prospecting messages with real-time SSE streaming.
    Yields events as messages are generated for immediate client display.
    """

    def __init__(
        self,
        campaign_name: str,
        profile_repository: ProfileRepositoryPort,
        campaign_repository: CampaignRepositoryPort,
        message_port: GenerateMessagePort,
    ):
        """
        Initialize the streaming use case.

        Args:
            campaign_name: Name for the campaign to create.
            profile_repository: Repository for accessing user profile.
            campaign_repository: Repository for campaign and message persistence.
            message_port: Port for generating prospecting messages.
        """
        self.campaign_name = campaign_name
        self.profile_repository = profile_repository
        self.campaign_repository = campaign_repository
        self.message_port = message_port

    def _create_campaign_message(
        self,
        campaign_id: Optional[str],
        contact: Contact,
        company: Company,
        subject: str,
        message: str,
        status: str,
        error: Optional[str] = None,
    ) -> CampaignMessage:
        """Create a CampaignMessage with common fields populated."""
        return CampaignMessage(
            campaign_id=campaign_id,
            contact_id=contact.id or "",
            contact_name=contact.name,
            contact_email=contact.email,
            company_name=company.name,
            subject=subject,
            message=message,
            status=status,
            error=error,
            created_at=_utc_now(),
        )

    def _create_message_event(self, saved_message: CampaignMessage) -> str:
        """Create SSE event for a generated message."""
        return SSEEvent(
            event=SSEEventType.MESSAGE_GENERATED,
            data=MessageGeneratedData(
                campaign_id=saved_message.campaign_id or "",
                message_id=saved_message.id or "",
                contact_id=saved_message.contact_id,
                contact_name=saved_message.contact_name,
                contact_email=saved_message.contact_email,
                company_name=saved_message.company_name,
                subject=saved_message.subject,
                message=saved_message.message,
                status=saved_message.status,
                created_at=saved_message.created_at or _utc_now(),
            ).model_dump(),
        ).to_sse_format()

    async def generate_campaign_stream(self) -> AsyncGenerator[str, None]:
        """
        Generate campaign messages with SSE streaming.

        Yields:
            str: SSE-formatted event strings.
        """
        campaign = None
        successful = 0
        failed = 0
        total_contacts = 0

        try:
            # Get user profile
            profile = await self.profile_repository.get_profile()
            if not profile:
                yield SSEEvent(
                    event=SSEEventType.CAMPAIGN_FAILED,
                    data={"error": "Profile not found. Please create a profile first."},
                ).to_sse_format()
                return

            # Create campaign record
            try:
                now = _utc_now()
                campaign = Campaign(
                    name=self.campaign_name,
                    status=CampaignStatus.IN_PROGRESS,
                    created_at=now,
                    updated_at=now,
                )
                campaign = await self.campaign_repository.create_campaign(campaign)
            except Exception as e:
                logger.error(f"Failed to create campaign: {e}")
                yield SSEEvent(
                    event=SSEEventType.CAMPAIGN_FAILED,
                    data={"error": f"Failed to create campaign: {str(e)}"},
                ).to_sse_format()
                return

            # Emit campaign started event
            yield SSEEvent(
                event=SSEEventType.CAMPAIGN_STARTED,
                data={"campaign_id": campaign.id, "campaign_name": campaign.name},
            ).to_sse_format()

            # Get contacts without existing messages
            contacts_with_companies = (
                await self.campaign_repository.get_contacts_without_messages()
            )

            if not contacts_with_companies:
                campaign.status = CampaignStatus.COMPLETED
                campaign.completed_at = _utc_now()
                await self.campaign_repository.update_campaign(campaign)

                yield SSEEvent(
                    event=SSEEventType.CAMPAIGN_COMPLETED,
                    data={
                        "campaign_id": campaign.id,
                        "total_contacts": 0,
                        "successful": 0,
                        "failed": 0,
                        "message": "No new contacts found.",
                    },
                ).to_sse_format()
                return

            total_contacts = len(contacts_with_companies)

            # Update campaign with total contacts
            campaign.total_contacts = total_contacts
            await self.campaign_repository.update_campaign(campaign)

            # Generate messages with streaming
            for index, (contact, company) in enumerate(contacts_with_companies):
                current = index + 1
                percentage = round((current / total_contacts) * 100, 1)

                # Emit progress update
                yield SSEEvent(
                    event=SSEEventType.PROGRESS_UPDATE,
                    data=CampaignProgressData(
                        campaign_id=campaign.id or "",
                        current=current,
                        total=total_contacts,
                        percentage=percentage,
                        current_contact_name=contact.name,
                    ).model_dump(),
                ).to_sse_format()

                try:
                    prospect_message = await self.message_port.get_message(
                        profile, contact, company
                    )
                    campaign_message = self._create_campaign_message(
                        campaign.id,
                        contact,
                        company,
                        subject=prospect_message.subject,
                        message=prospect_message.message,
                        status="success",
                    )
                    saved_message = await self.campaign_repository.save_message(
                        campaign_message
                    )
                    successful += 1
                    yield self._create_message_event(saved_message)

                except Exception as e:
                    logger.warning(f"Failed to generate message for contact {contact.id}: {e}")
                    campaign_message = self._create_campaign_message(
                        campaign.id,
                        contact,
                        company,
                        subject="",
                        message="",
                        status="failed",
                        error=str(e),
                    )
                    saved_message = await self.campaign_repository.save_message(
                        campaign_message
                    )
                    failed += 1
                    yield self._create_message_event(saved_message)

                # Update campaign stats after each message
                campaign.successful = successful
                campaign.failed = failed
                await self.campaign_repository.update_campaign(campaign)

            # Mark campaign as completed or failed
            campaign.status = (
                CampaignStatus.FAILED if failed == total_contacts else CampaignStatus.COMPLETED
            )
            campaign.completed_at = _utc_now()
            await self.campaign_repository.update_campaign(campaign)

            # Emit completion event
            yield SSEEvent(
                event=SSEEventType.CAMPAIGN_COMPLETED,
                data={
                    "campaign_id": campaign.id,
                    "total_contacts": total_contacts,
                    "successful": successful,
                    "failed": failed,
                    "message": f"Campaign completed: {successful} successful, {failed} failed",
                },
            ).to_sse_format()

        except Exception as e:
            # Handle unexpected errors and ensure campaign is marked as failed
            logger.error(f"Unexpected error in campaign stream: {e}")
            if campaign and campaign.id:
                try:
                    campaign.status = CampaignStatus.FAILED
                    campaign.completed_at = _utc_now()
                    campaign.successful = successful
                    campaign.failed = failed
                    await self.campaign_repository.update_campaign(campaign)
                except Exception as update_error:
                    logger.error(f"Failed to update campaign status on error: {update_error}")

            yield SSEEvent(
                event=SSEEventType.CAMPAIGN_FAILED,
                data={
                    "campaign_id": campaign.id if campaign else None,
                    "error": f"Unexpected error: {str(e)}",
                    "total_contacts": total_contacts,
                    "successful": successful,
                    "failed": failed,
                },
            ).to_sse_format()
