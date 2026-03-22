import datetime
from domain.entities.campaign import Campaign, CampaignStatus
from domain.entities.campaign_result import CampaignResult, CampaignMessage
from domain.entities.task import TaskProgress
from domain.ports.generate_message import GenerateMessagePort
from domain.ports.profile_respository import ProfileRepositoryPort
from domain.ports.campaign_repository import CampaignRepositoryPort
from domain.ports.task_manager import TaskManagerPort

ERR_PROFILE_NOT_FOUND = "Profile not found. Please create a profile before generating campaign."


class GenerateCampaignUseCase:
    """
    Use case for generating prospecting messages for all contacts in the database.
    This creates a campaign by iterating through all contacts and generating personalized messages.
    Only contacts without existing messages will be processed (each contact gets one message ever).
    """

    def __init__(
        self,
        task_uuid: str,
        campaign_name: str,
        profile_repository: ProfileRepositoryPort,
        campaign_repository: CampaignRepositoryPort,
        message_port: GenerateMessagePort,
        task_manager: TaskManagerPort,
    ):
        """
        Initialize the GenerateCampaignUseCase with required dependencies.

        Args:
            task_uuid (str): Unique identifier for the background task.
            campaign_name (str): Name for the campaign to create.
            profile_repository (ProfileRepositoryPort): Repository for accessing user profile.
            campaign_repository (CampaignRepositoryPort): Repository for campaign and message persistence.
            message_port (GenerateMessagePort): Port for generating prospecting messages.
            task_manager (TaskManagerPort): Port for managing task status updates.
        """
        self.task_uuid = task_uuid
        self.campaign_name = campaign_name
        self.profile_repository = profile_repository
        self.campaign_repository = campaign_repository
        self.message_port = message_port
        self.task_manager = task_manager

    async def generate_campaign(self) -> CampaignResult:
        """
        Generate prospecting messages for contacts without existing messages.
        Each contact can only receive one message ever (enforced by campaign_repository).

        Returns:
            CampaignResult: Result containing all generated messages and statistics.

        Raises:
            ValueError: If profile is not found or no contacts are available.
        """
        await self.task_manager.submit_task(self.task_uuid, task_type="generate_campaign")

        # Get user profile
        profile = await self.profile_repository.get_profile()
        if not profile:
            await self.task_manager.update_task(
                self.task_uuid,
                ERR_PROFILE_NOT_FOUND,
                "failed",
                progress=TaskProgress(current=0, total=1, percentage=0.0),
                error_details=ERR_PROFILE_NOT_FOUND
            )
            raise ValueError(ERR_PROFILE_NOT_FOUND)

        # Create campaign record at start
        campaign = Campaign(
            name=self.campaign_name,
            status=CampaignStatus.IN_PROGRESS,
            created_at=datetime.datetime.now(datetime.UTC),
            updated_at=datetime.datetime.now(datetime.UTC),
        )
        campaign = await self.campaign_repository.create_campaign(campaign)

        # Get contacts without existing messages (each contact gets one message ever)
        await self.task_manager.update_task(
            self.task_uuid,
            "Fetching contacts without messages",
            "in_progress",
            progress=TaskProgress(current=0, total=1, percentage=0.0)
        )
        contacts_with_companies = await self.campaign_repository.get_contacts_without_messages()

        if not contacts_with_companies:
            # Update campaign as completed with zero contacts
            campaign.status = CampaignStatus.COMPLETED
            campaign.completed_at = datetime.datetime.now(datetime.UTC)
            await self.campaign_repository.update_campaign(campaign)

            await self.task_manager.update_task(
                self.task_uuid,
                "No new contacts found. All contacts already have messages.",
                "completed",
                progress=TaskProgress(current=0, total=0, percentage=100.0)
            )

            result = CampaignResult(
                total_contacts=0,
                successful=0,
                failed=0,
                messages=[]
            )
            await self.task_manager.store_result(self.task_uuid, result)
            return result

        total_contacts = len(contacts_with_companies)
        messages: list[CampaignMessage] = []
        successful = 0
        failed = 0

        # Update campaign with total contacts
        campaign.total_contacts = total_contacts
        await self.campaign_repository.update_campaign(campaign)

        # Generate messages for each contact
        for index, (contact, company) in enumerate(contacts_with_companies):
            current = index + 1
            percentage = round((current / total_contacts) * 100, 1)

            await self.task_manager.update_task(
                self.task_uuid,
                f"Generating message {current}/{total_contacts} for {contact.name or 'Unknown'}",
                "in_progress",
                progress=TaskProgress(current=current, total=total_contacts, percentage=percentage)
            )

            try:
                prospect_message = await self.message_port.get_message(profile, contact, company)
                campaign_message = CampaignMessage(
                    campaign_id=campaign.id,
                    contact_id=contact.id or "",
                    contact_name=contact.name,
                    contact_email=contact.email,
                    company_name=company.name,
                    subject=prospect_message.subject,
                    message=prospect_message.message,
                    status="success",
                    error=None,
                    created_at=datetime.datetime.now(datetime.UTC)
                )
                # Save message to DB immediately (not at end)
                saved_message = await self.campaign_repository.save_message(campaign_message)
                messages.append(saved_message)
                successful += 1
            except Exception as e:
                campaign_message = CampaignMessage(
                    campaign_id=campaign.id,
                    contact_id=contact.id or "",
                    contact_name=contact.name,
                    contact_email=contact.email,
                    company_name=company.name,
                    subject="",
                    message="",
                    status="failed",
                    error=str(e),
                    created_at=datetime.datetime.now(datetime.UTC)
                )
                # Save failed message to DB as well
                saved_message = await self.campaign_repository.save_message(campaign_message)
                messages.append(saved_message)
                failed += 1

            # Update campaign stats after each message
            campaign.successful = successful
            campaign.failed = failed
            await self.campaign_repository.update_campaign(campaign)

        # Mark campaign as completed or failed based on results
        if failed == total_contacts:
            campaign.status = CampaignStatus.FAILED
        else:
            campaign.status = CampaignStatus.COMPLETED
        campaign.completed_at = datetime.datetime.now(datetime.UTC)
        await self.campaign_repository.update_campaign(campaign)

        result = CampaignResult(
            total_contacts=total_contacts,
            successful=successful,
            failed=failed,
            messages=messages
        )

        # Store result for later retrieval
        await self.task_manager.store_result(self.task_uuid, result)

        await self.task_manager.update_task(
            self.task_uuid,
            f"Campaign generation completed: {successful} successful, {failed} failed out of {total_contacts} contacts",
            "completed",
            progress=TaskProgress(current=total_contacts, total=total_contacts, percentage=100.0)
        )

        return result
