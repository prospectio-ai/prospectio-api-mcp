import logging

from domain.entities.company import Company
from domain.entities.contact import Contact, ContactEntity
from domain.entities.leads import Leads
from domain.entities.profile import Profile
from domain.ports.enrich_leads import EnrichLeadsPort
from domain.ports.leads_repository import LeadsRepositoryPort
from domain.ports.task_manager import TaskManagerPort
from infrastructure.services.enrich_leads_agent.nodes import EnrichLeadsNodes

logger = logging.getLogger(__name__)


class EnrichLeadsAgent(EnrichLeadsPort):
    """
    An agent that enriches leads using various data sources.

    This agent processes companies SEQUENTIALLY to avoid flooding
    external APIs like OpenRouter with too many concurrent requests.
    Data is saved incrementally after each company is processed.
    """

    def __init__(
        self,
        task_manager: TaskManagerPort,
        leads_repository: LeadsRepositoryPort,
    ):
        """
        Initialize the EnrichLeadsAgent.

        Args:
            task_manager: Task manager for tracking progress.
            leads_repository: Repository for saving leads data incrementally.
        """
        self.task_manager = task_manager
        self.leads_repository = leads_repository
        self._task_uuid: str | None = None
        self.nodes = EnrichLeadsNodes(leads_repository=leads_repository)

    def _create_progress_callback(self, task_uuid: str):
        """Create a progress callback function for nodes."""
        async def progress_callback(message: str) -> None:
            await self.task_manager.update_task(task_uuid, message, "in_progress")
        return progress_callback

    def _build_progress_message(
        self,
        current_action: str,
        companies_processed: int,
        companies_total: int,
        companies_saved: int,
        companies_skipped: int,
        contacts_saved: int,
        contacts_skipped: int,
    ) -> str:
        """
        Build a detailed progress message with counts.

        Args:
            current_action: The current action being performed.
            companies_processed: Number of companies processed so far.
            companies_total: Total number of companies to process.
            companies_saved: Number of companies saved to database.
            companies_skipped: Number of companies skipped (already exist).
            contacts_saved: Number of contacts saved to database.
            contacts_skipped: Number of contacts skipped (already exist).

        Returns:
            str: Formatted progress message.
        """
        return (
            f"{current_action} | "
            f"Progress: {companies_processed}/{companies_total} | "
            f"Companies: {companies_saved} saved, {companies_skipped} skipped | "
            f"Contacts: {contacts_saved} saved, {contacts_skipped} skipped"
        )

    async def _save_company_if_new(self, company: Company) -> tuple[bool, Company | None]:
        """
        Save a company to the database if it does not already exist.
        If company already exists, returns the existing company to get its ID.

        Args:
            company: The company to potentially save.

        Returns:
            tuple[bool, Company | None]: (was_saved, company_with_id)
                - was_saved: True if company was saved, False if already existed.
                - company_with_id: The saved or existing company with ID.
        """
        if not company.name:
            logger.warning("Company has no name, skipping save")
            return False, None

        # Check if company already exists and retrieve it
        existing_company = await self.leads_repository.get_company_by_name(company.name)
        if existing_company:
            logger.info(f"Company '{company.name}' already exists with ID: {existing_company.id}")
            return False, existing_company

        saved_company = await self.leads_repository.save_company(company)
        logger.info(f"Saved company '{company.name}' with ID: {saved_company.id}")
        return True, saved_company

    async def _save_contact_if_new(self, contact: Contact) -> bool:
        """
        Save a contact to the database if it does not already exist.

        Deduplication strategy:
        - If contact has email: check by email
        - If contact has no email: check by name + company_id

        Args:
            contact: The contact to potentially save.

        Returns:
            bool: True if contact was saved, False if skipped.
        """
        # Check for duplicates based on available data
        if contact.email:
            exists = await self.leads_repository.contact_exists_by_email(contact.email)
            if exists:
                logger.info(
                    f"Contact '{contact.name}' with email(s) {contact.email} already exists, skipping"
                )
                return False
        else:
            # No email - check by name and company to avoid duplicates
            exists = await self.leads_repository.contact_exists_by_name_and_company(
                contact.name, contact.company_id
            )
            if exists:
                logger.info(
                    f"Contact '{contact.name}' at company {contact.company_id} already exists, skipping"
                )
                return False

        saved_contact = await self.leads_repository.save_contact(contact)
        logger.info(f"Saved contact '{contact.name}' with ID: {saved_contact.id}")
        return True

    async def execute(self, leads: Leads, profile: Profile, task_uuid: str) -> Leads:
        """
        Execute the enrichment pipeline sequentially with incremental saves.

        Processes each company one at a time to avoid overwhelming
        external APIs with concurrent requests. Data is saved to the database
        immediately after each company and its contacts are enriched.

        Args:
            leads: The leads to enrich.
            profile: The user profile for context.
            task_uuid: The task UUID for progress tracking.

        Returns:
            Leads: The enriched leads (also saved incrementally to database).
        """
        # Set progress callback for this task
        self._task_uuid = task_uuid
        self.nodes.progress_callback = self._create_progress_callback(task_uuid)

        # Initialize nodes with profile and leads
        self.nodes.profile = profile
        self.nodes.leads = leads

        # Initialize progress counters
        companies_processed = 0
        companies_total = len(leads.companies.companies) if leads.companies else 0
        companies_saved = 0
        companies_skipped = 0
        contacts_saved = 0
        contacts_skipped = 0

        await self.task_manager.update_task(
            task_uuid,
            self._build_progress_message(
                "Starting enrichment...",
                companies_processed,
                companies_total,
                companies_saved,
                companies_skipped,
                contacts_saved,
                contacts_skipped,
            ),
            "in_progress",
        )

        companies = leads.companies.companies if leads.companies else []
        enriched_companies = []
        all_contacts = []

        # Process each company SEQUENTIALLY
        for i, company in enumerate(companies):
            try:
                logger.info(f"Processing company {i+1}/{len(companies)}: {company.name}")

                await self.task_manager.update_task(
                    task_uuid,
                    self._build_progress_message(
                        f"Processing: {company.name}",
                        companies_processed,
                        companies_total,
                        companies_saved,
                        companies_skipped,
                        contacts_saved,
                        contacts_skipped,
                    ),
                    "in_progress",
                )

                enriched_company = None

                # Step 1: Make decision if company should be enriched
                state = {"company": company, "step": []}
                decision_state = await self.nodes.make_company_decision(state)

                approved_companies = decision_state.get("company", [])

                if approved_companies:
                    # Step 2: Enrich company info
                    await self.task_manager.update_task(
                        task_uuid,
                        self._build_progress_message(
                            f"Enriching: {company.name}",
                            companies_processed,
                            companies_total,
                            companies_saved,
                            companies_skipped,
                            contacts_saved,
                            contacts_skipped,
                        ),
                        "in_progress",
                    )

                    enrich_state = {"company": company, "step": []}
                    enriched_state = await self.nodes.enrich_company(enrich_state)

                    enriched_company_list = enriched_state.get("enriched_company", [])
                    if enriched_company_list:
                        enriched_company = enriched_company_list[0]
                        enriched_companies.append(enriched_company)

                # Step 3: Save enriched company (or original if not enriched)
                company_to_save = enriched_company if enriched_company else company
                was_saved, saved_company = await self._save_company_if_new(company_to_save)

                if was_saved:
                    companies_saved += 1
                else:
                    companies_skipped += 1

                # Step 4: Enrich contacts for this company
                await self.task_manager.update_task(
                    task_uuid,
                    self._build_progress_message(
                        f"Finding contacts for: {company.name}",
                        companies_processed,
                        companies_total,
                        companies_saved,
                        companies_skipped,
                        contacts_saved,
                        contacts_skipped,
                    ),
                    "in_progress",
                )

                # Use saved_company to ensure correct company_id for contacts
                company_for_contacts = saved_company if saved_company else company
                contacts_state = {"company": company_for_contacts, "step": []}
                contacts_result = await self.nodes.enrich_contacts(contacts_state)

                # In streaming mode, contacts are saved immediately in the node
                # Aggregate the counts from the node
                node_contacts_saved = contacts_result.get("contacts_saved", 0)
                node_contacts_skipped = contacts_result.get("contacts_skipped", 0)
                contacts_saved += node_contacts_saved
                contacts_skipped += node_contacts_skipped

                # Get contacts list for return value
                contacts = contacts_result.get("enriched_contacts", [])
                if contacts:
                    logger.info(
                        f"Found {len(contacts)} contacts for {company.name} "
                        f"({node_contacts_saved} saved, {node_contacts_skipped} skipped)"
                    )
                    all_contacts.extend(contacts)

                companies_processed += 1

                # Update progress after company is fully processed
                await self.task_manager.update_task(
                    task_uuid,
                    self._build_progress_message(
                        f"Completed: {company.name}",
                        companies_processed,
                        companies_total,
                        companies_saved,
                        companies_skipped,
                        contacts_saved,
                        contacts_skipped,
                    ),
                    "in_progress",
                )

            except Exception as company_error:
                logger.error(
                    f"Error processing company '{company.name}': {company_error}",
                    exc_info=True,
                )
                companies_processed += 1
                companies_skipped += 1
                # Continue processing remaining companies

        # Update leads with enriched data for return value
        if enriched_companies:
            leads.companies.companies = enriched_companies

        if all_contacts:
            if not leads.contacts:
                leads.contacts = ContactEntity(contacts=[])
            leads.contacts.contacts = all_contacts

        await self.task_manager.update_task(
            task_uuid,
            self._build_progress_message(
                "Enrichment complete",
                companies_processed,
                companies_total,
                companies_saved,
                companies_skipped,
                contacts_saved,
                contacts_skipped,
            ),
            "in_progress",
        )

        return leads
