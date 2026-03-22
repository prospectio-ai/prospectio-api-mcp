from typing import List, Optional, Tuple
import datetime
from math import ceil
import uuid
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import select, exists, or_
from domain.ports.campaign_repository import CampaignRepositoryPort
from domain.entities.campaign import Campaign, CampaignEntity, CampaignStatus
from domain.entities.campaign_result import CampaignMessage
from domain.entities.contact import Contact
from domain.entities.company import Company
from domain.entities.validation_result import ValidationStatus
from infrastructure.dto.database.campaign import Campaign as CampaignDB
from infrastructure.dto.database.message import Message as MessageDB
from infrastructure.dto.database.contact import Contact as ContactDB
from infrastructure.dto.database.company import Company as CompanyDB

# Minimum confidence score required for campaign message generation
MIN_CONFIDENCE_SCORE_FOR_CAMPAIGN = 70


class CampaignDatabase(CampaignRepositoryPort):
    """
    SQLAlchemy implementation of the campaign repository port.
    Handles campaign and message persistence operations using async operations.
    """

    def __init__(self, database_url: str):
        """
        Initialize the campaign database repository.

        Args:
            database_url (str): Async database connection URL (should start with postgresql+asyncpg://).
        """
        self.database_url = database_url
        self.engine = create_async_engine(database_url)

    async def create_campaign(self, campaign: Campaign) -> Campaign:
        """
        Create a new campaign in the database.

        Args:
            campaign (Campaign): The campaign entity to create.

        Returns:
            Campaign: The created campaign with assigned ID.
        """
        async with AsyncSession(self.engine) as session:
            try:
                campaign_db = CampaignDB(
                    id=campaign.id or str(uuid.uuid4()),
                    name=campaign.name,
                    description=campaign.description,
                    status=campaign.status.value,
                    created_at=campaign.created_at or datetime.datetime.now(datetime.UTC),
                    updated_at=campaign.updated_at or datetime.datetime.now(datetime.UTC),
                    completed_at=campaign.completed_at,
                    total_contacts=campaign.total_contacts,
                    successful=campaign.successful,
                    failed=campaign.failed,
                )
                session.add(campaign_db)
                await session.commit()
                await session.refresh(campaign_db)
                return self._convert_db_to_campaign(campaign_db)
            except Exception as e:
                await session.rollback()
                raise e

    async def get_campaign_by_id(self, campaign_id: str) -> Optional[Campaign]:
        """
        Retrieve a campaign by its ID.

        Args:
            campaign_id (str): The unique identifier of the campaign.

        Returns:
            Optional[Campaign]: The campaign entity if found, otherwise None.
        """
        async with AsyncSession(self.engine) as session:
            result = await session.execute(
                select(CampaignDB).where(CampaignDB.id == campaign_id)
            )
            campaign_db = result.scalars().first()
            if campaign_db:
                return self._convert_db_to_campaign(campaign_db)
            return None

    async def get_campaigns(self, offset: int, limit: int) -> CampaignEntity:
        """
        Retrieve campaigns with pagination.

        Args:
            offset (int): Number of campaigns to skip.
            limit (int): Maximum number of campaigns to return.

        Returns:
            CampaignEntity: Entity containing list of campaigns and pagination info.
        """
        async with AsyncSession(self.engine) as session:
            total_result = await session.execute(select(CampaignDB.id))
            total_campaigns = total_result.scalars().all()
            total_pages = ceil(len(total_campaigns) / limit) if limit > 0 else 1

            result = await session.execute(
                select(CampaignDB)
                .order_by(CampaignDB.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            campaign_dbs = result.scalars().all()
            campaigns = [
                self._convert_db_to_campaign(campaign_db)
                for campaign_db in campaign_dbs
            ]
            return CampaignEntity(campaigns=campaigns, pages=total_pages)

    async def update_campaign(self, campaign: Campaign) -> Campaign:
        """
        Update an existing campaign.

        Args:
            campaign (Campaign): The campaign entity with updated fields.

        Returns:
            Campaign: The updated campaign entity.
        """
        async with AsyncSession(self.engine) as session:
            try:
                result = await session.execute(
                    select(CampaignDB).where(CampaignDB.id == campaign.id)
                )
                campaign_db = result.scalars().first()
                if not campaign_db:
                    raise ValueError(f"Campaign not found with id: {campaign.id}")

                campaign_db.name = campaign.name
                campaign_db.description = campaign.description
                campaign_db.status = campaign.status.value
                campaign_db.updated_at = datetime.datetime.now(datetime.UTC)
                campaign_db.completed_at = campaign.completed_at
                campaign_db.total_contacts = campaign.total_contacts
                campaign_db.successful = campaign.successful
                campaign_db.failed = campaign.failed

                await session.commit()
                await session.refresh(campaign_db)
                return self._convert_db_to_campaign(campaign_db)
            except Exception as e:
                await session.rollback()
                raise e

    async def save_message(self, message: CampaignMessage) -> CampaignMessage:
        """
        Save a campaign message to the database.

        Args:
            message (CampaignMessage): The message entity to save.

        Returns:
            CampaignMessage: The saved message with assigned ID.
        """
        async with AsyncSession(self.engine) as session:
            try:
                message_db = MessageDB(
                    id=message.id or str(uuid.uuid4()),
                    campaign_id=message.campaign_id,
                    contact_id=message.contact_id,
                    contact_name=message.contact_name,
                    contact_email=message.contact_email,
                    company_name=message.company_name,
                    subject=message.subject,
                    message=message.message,
                    status=message.status,
                    error=message.error,
                    created_at=message.created_at or datetime.datetime.now(datetime.UTC),
                )
                session.add(message_db)
                await session.commit()
                await session.refresh(message_db)
                return self._convert_db_to_message(message_db)
            except Exception as e:
                await session.rollback()
                raise e

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
        async with AsyncSession(self.engine) as session:
            result = await session.execute(
                select(MessageDB)
                .where(MessageDB.campaign_id == campaign_id)
                .order_by(MessageDB.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            message_dbs = result.scalars().all()
            return [
                self._convert_db_to_message(message_db)
                for message_db in message_dbs
            ]

    async def get_contacts_without_messages(self) -> List[Tuple[Contact, Company]]:
        """
        Retrieve all high-confidence contacts that don't have any messages generated yet.
        This ensures each contact only receives one message ever.

        Only contacts with validation_status='verified' OR confidence_score >= 70
        are returned. This filters out low-confidence contacts that need review.

        Returns:
            List[Tuple[Contact, Company]]: List of contact and company pairs
                for high-confidence contacts without existing messages.
        """
        async with AsyncSession(self.engine) as session:
            # Subquery to get contact_ids that already have messages
            message_contact_ids = select(MessageDB.contact_id).distinct()

            # Get high-confidence contacts that don't have messages
            # Filter: validation_status='verified' OR confidence_score >= 70
            # Also include contacts with NULL validation (legacy data)
            contacts_result = await session.execute(
                select(ContactDB).where(
                    ~ContactDB.id.in_(message_contact_ids),
                    or_(
                        ContactDB.validation_status == ValidationStatus.VERIFIED.value,
                        ContactDB.confidence_score >= MIN_CONFIDENCE_SCORE_FOR_CAMPAIGN,
                        # Include legacy contacts without validation data
                        ContactDB.validation_status.is_(None),
                    )
                )
            )
            contact_dbs = contacts_result.scalars().all()

            if not contact_dbs:
                return []

            # Get all unique company IDs
            company_ids = list({
                contact_db.company_id
                for contact_db in contact_dbs
                if contact_db.company_id is not None
            })

            # Fetch all companies in one query
            companies_map: dict[str, CompanyDB] = {}
            if company_ids:
                companies_result = await session.execute(
                    select(CompanyDB).where(CompanyDB.id.in_(company_ids))
                )
                company_dbs = companies_result.scalars().all()
                companies_map = {company_db.id: company_db for company_db in company_dbs}

            # Build result list of tuples
            result: List[Tuple[Contact, Company]] = []
            for contact_db in contact_dbs:
                company_db = companies_map.get(contact_db.company_id) if contact_db.company_id else None
                if company_db:
                    contact = self._convert_db_to_contact(
                        contact_db,
                        company_db.name,
                        None
                    )
                    company = self._convert_db_to_company(company_db)
                    result.append((contact, company))

            return result

    async def contact_has_message(self, contact_id: str) -> bool:
        """
        Check if a contact already has a message generated.

        Args:
            contact_id (str): The contact ID to check.

        Returns:
            bool: True if contact has a message, False otherwise.
        """
        async with AsyncSession(self.engine) as session:
            result = await session.execute(
                select(exists().where(MessageDB.contact_id == contact_id))
            )
            return result.scalar() or False

    def _convert_db_to_campaign(self, campaign_db: CampaignDB) -> Campaign:
        """
        Convert database campaign model to domain campaign entity.

        Args:
            campaign_db: Database campaign model.

        Returns:
            Campaign: Domain campaign entity.
        """
        return Campaign(
            id=campaign_db.id,
            name=campaign_db.name,
            description=campaign_db.description,
            status=CampaignStatus(campaign_db.status),
            created_at=campaign_db.created_at,
            updated_at=campaign_db.updated_at,
            completed_at=campaign_db.completed_at,
            total_contacts=campaign_db.total_contacts,
            successful=campaign_db.successful,
            failed=campaign_db.failed,
        )

    def _convert_db_to_message(self, message_db: MessageDB) -> CampaignMessage:
        """
        Convert database message model to domain campaign message entity.

        Args:
            message_db: Database message model.

        Returns:
            CampaignMessage: Domain campaign message entity.
        """
        return CampaignMessage(
            id=message_db.id,
            campaign_id=message_db.campaign_id,
            contact_id=message_db.contact_id,
            contact_name=message_db.contact_name,
            contact_email=message_db.contact_email,
            company_name=message_db.company_name,
            subject=message_db.subject,
            message=message_db.message,
            status=message_db.status,
            error=message_db.error,
            created_at=message_db.created_at,
        )

    def _convert_db_to_contact(
        self,
        contact_db: ContactDB,
        company_name: Optional[str],
        job_title: Optional[str]
    ) -> Contact:
        """
        Convert database contact model to domain contact entity.

        Args:
            contact_db: Database contact model.
            company_name: Name of the company.
            job_title: Title of the job.

        Returns:
            Contact: Domain contact entity.
        """
        return Contact(
            id=contact_db.id,
            company_id=contact_db.company_id,
            company_name=company_name,
            job_id=contact_db.job_id,
            job_title=job_title,
            name=contact_db.name,
            email=contact_db.email,
            title=contact_db.title,
            phone=contact_db.phone,
            profile_url=contact_db.profile_url,
            short_description=contact_db.short_description,
            full_bio=contact_db.full_bio,
            confidence_score=contact_db.confidence_score,
            validation_status=contact_db.validation_status,
            validation_reasons=contact_db.validation_reasons,
        )

    def _convert_db_to_company(self, company_db: CompanyDB) -> Company:
        """
        Convert database company model to domain company entity.

        Args:
            company_db: Database company model.

        Returns:
            Company: Domain company entity.
        """
        return Company(
            id=company_db.id,
            name=company_db.name,
            industry=company_db.industry,
            compatibility=company_db.compatibility,
            source=company_db.source,
            location=company_db.location,
            size=company_db.size,
            revenue=company_db.revenue,
            website=company_db.website,
            description=company_db.description,
            opportunities=company_db.opportunities,
        )
