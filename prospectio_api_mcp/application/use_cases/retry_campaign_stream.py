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


class RetryCampaignStreamUseCase:
    """
    Use case for retrying failed campaign messages with real-time SSE streaming.
    Deletes old failed messages, re-generates them, and yields events as they are processed.
    """

    def __init__(
        self,
        campaign_id: str,
        profile_repository: ProfileRepositoryPort,
        campaign_repository: CampaignRepositoryPort,
        message_port: GenerateMessagePort,
    ):
        """
        Initialize the retry streaming use case.

        Args:
            campaign_id: ID of the campaign to retry failed messages for.
            profile_repository: Repository for accessing user profile.
            campaign_repository: Repository for campaign and message persistence.
            message_port: Port for generating prospecting messages.
        """
        self.campaign_id = campaign_id
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
                error=saved_message.error,
                created_at=saved_message.created_at or _utc_now(),
            ).model_dump(),
        ).to_sse_format()

    async def retry_campaign_stream(self) -> AsyncGenerator[str, None]:
        """
        Retry failed campaign messages with SSE streaming.

        Yields:
            str: SSE-formatted event strings.
        """
        campaign: Optional[Campaign] = None
        successful = 0
        failed = 0
        total_to_retry = 0

        try:
            # Fetch campaign by ID
            campaign = await self.campaign_repository.get_campaign_by_id(self.campaign_id)
            if not campaign:
                yield SSEEvent(
                    event=SSEEventType.CAMPAIGN_FAILED,
                    data={"error": f"Campaign not found with id: {self.campaign_id}"},
                ).to_sse_format()
                return

            # Validate campaign status
            if campaign.status not in (CampaignStatus.COMPLETED, CampaignStatus.FAILED):
                yield SSEEvent(
                    event=SSEEventType.CAMPAIGN_FAILED,
                    data={"error": f"Cannot retry campaign with status '{campaign.status.value}'. Only COMPLETED or FAILED campaigns can be retried."},
                ).to_sse_format()
                return

            # Fetch user profile
            profile = await self.profile_repository.get_profile()
            if not profile:
                yield SSEEvent(
                    event=SSEEventType.CAMPAIGN_FAILED,
                    data={"error": "Profile not found. Please create a profile first."},
                ).to_sse_format()
                return

            # Fetch failed messages with contacts
            failed_messages_with_contacts = (
                await self.campaign_repository.get_failed_messages_with_contacts(self.campaign_id)
            )

            # If no failed messages, emit completion and return
            if not failed_messages_with_contacts:
                yield SSEEvent(
                    event=SSEEventType.CAMPAIGN_COMPLETED,
                    data={
                        "campaign_id": campaign.id,
                        "total_contacts": 0,
                        "successful": campaign.successful,
                        "failed": 0,
                        "message": "No failed messages to retry.",
                    },
                ).to_sse_format()
                return

            total_to_retry = len(failed_messages_with_contacts)
            previous_successful = campaign.successful

            # Set campaign to IN_PROGRESS
            campaign.status = CampaignStatus.IN_PROGRESS
            campaign.completed_at = None
            await self.campaign_repository.update_campaign(campaign)

            # Emit campaign started event
            yield SSEEvent(
                event=SSEEventType.CAMPAIGN_STARTED,
                data={"campaign_id": campaign.id, "campaign_name": campaign.name},
            ).to_sse_format()

            # Process each failed message
            for index, (old_message, contact, company) in enumerate(failed_messages_with_contacts):
                current = index + 1
                percentage = round((current / total_to_retry) * 100, 1)

                # Emit progress update
                yield SSEEvent(
                    event=SSEEventType.PROGRESS_UPDATE,
                    data=CampaignProgressData(
                        campaign_id=campaign.id or "",
                        current=current,
                        total=total_to_retry,
                        percentage=percentage,
                        current_contact_name=contact.name,
                    ).model_dump(),
                ).to_sse_format()

                # Delete old failed message
                await self.campaign_repository.delete_message(old_message.id or "")

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
                campaign.successful = previous_successful + successful
                campaign.failed = failed
                await self.campaign_repository.update_campaign(campaign)

            # Mark campaign as completed or failed
            campaign.status = (
                CampaignStatus.FAILED if failed == total_to_retry else CampaignStatus.COMPLETED
            )
            campaign.completed_at = _utc_now()
            await self.campaign_repository.update_campaign(campaign)

            # Emit completion event
            yield SSEEvent(
                event=SSEEventType.CAMPAIGN_COMPLETED,
                data={
                    "campaign_id": campaign.id,
                    "total_contacts": total_to_retry,
                    "successful": successful,
                    "failed": failed,
                    "message": f"Retry completed: {successful} successful, {failed} failed",
                },
            ).to_sse_format()

        except Exception as e:
            logger.error(f"Unexpected error in campaign retry stream: {e}")
            if campaign and campaign.id:
                try:
                    campaign.status = CampaignStatus.FAILED
                    campaign.completed_at = _utc_now()
                    await self.campaign_repository.update_campaign(campaign)
                except Exception as update_error:
                    logger.error(f"Failed to update campaign status on error: {update_error}")

            yield SSEEvent(
                event=SSEEventType.CAMPAIGN_FAILED,
                data={
                    "campaign_id": campaign.id if campaign else None,
                    "error": f"Unexpected error: {str(e)}",
                    "total_contacts": total_to_retry,
                    "successful": successful,
                    "failed": failed,
                },
            ).to_sse_format()
