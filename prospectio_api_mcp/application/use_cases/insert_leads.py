from domain.ports.enrich_leads import EnrichLeadsPort
from domain.ports.profile_respository import ProfileRepositoryPort
from domain.ports.task_manager import TaskManagerPort
from domain.services.leads.strategy import LeadsStrategy
from domain.entities.leads_result import LeadsResult
from domain.entities.task import TaskProgress
from domain.ports.leads_repository import LeadsRepositoryPort
from domain.services.leads.leads_processor import LeadsProcessor


class InsertLeadsUseCase:
    """
    Use case for retrieving leads with contacts from a specified source using the strategy pattern.
    This class selects the appropriate strategy based on the source and delegates the lead retrieval logic.
    """

    def __init__(
        self,
        task_uuid: str,
        strategy: LeadsStrategy,
        repository: LeadsRepositoryPort,
        leads_processor: LeadsProcessor,
        profile_repository: ProfileRepositoryPort,
        enrich_leads: EnrichLeadsPort,
        task_manager: TaskManagerPort
    ):
        """
        Initialize the GetLeadsUseCase with the required parameters and available strategies.

        Args:
            source (str): The lead source identifier (e.g., 'mantiks', 'clearbit').
            location (str): The location to search for leads.
            job_title (list[str]): List of job titles to filter leads.
            port (ProspectAPIPort): The port interface to the external prospect API.
        """
        self.strategy = strategy
        self.repository = repository
        self.leads_processor = leads_processor
        self.profile_repository = profile_repository
        self.enrich_leads = enrich_leads
        self.task_uuid = task_uuid
        self.task_manager = task_manager

    async def insert_leads(self) -> LeadsResult:
        """
        Retrieve leads using the selected strategy for the given source.

        Returns:
            str: The leads data as a string (JSON or similar).
        Raises:
            KeyError: If the specified source is not supported.
        """
        # Define processing steps for progress tracking
        total_steps = 7
        current_step = 0

        def make_progress(step: int) -> TaskProgress:
            return TaskProgress(
                current=step,
                total=total_steps,
                percentage=round((step / total_steps) * 100, 1)
            )

        self.task = await self.task_manager.submit_task(self.task_uuid, task_type="insert_leads")

        # Step 1: Get profile
        current_step = 1
        await self.task_manager.update_task(
            self.task_uuid,
            "Fetching user profile",
            "in_progress",
            progress=make_progress(current_step)
        )
        profile = await self.profile_repository.get_profile()
        if not profile:
            await self.task_manager.update_task(
                self.task_uuid,
                "Profile not found. Please create a profile before inserting leads.",
                "failed",
                progress=make_progress(current_step),
                error_details="Profile not found. Please create a profile before inserting leads."
            )
            raise ValueError(
                "Profile not found. Please create a profile before inserting leads."
            )

        # Step 2: Execute strategy to fetch leads
        current_step = 2
        await self.task_manager.update_task(
            self.task_uuid,
            "Fetching leads from source",
            "in_progress",
            progress=make_progress(current_step)
        )
        leads = await self.strategy.execute()
        if not leads.jobs:
            await self.task_manager.update_task(
                self.task_uuid,
                "No jobs found in the leads data.",
                "failed",
                progress=make_progress(current_step),
                error_details="No jobs found in the leads data."
            )
            raise ValueError("No jobs found in the leads data.")
        if not leads.companies:
            await self.task_manager.update_task(
                self.task_uuid,
                "No companies found in the leads data.",
                "failed",
                progress=make_progress(current_step),
                error_details="No companies found in the leads data."
            )
            raise ValueError("No companies found in the leads data.")

        # Step 3: Process and deduplicate leads
        current_step = 3
        await self.task_manager.update_task(
            self.task_uuid,
            "Processing and deduplicating leads",
            "in_progress",
            progress=make_progress(current_step)
        )
        leads.companies = await self.leads_processor.deduplicate_companies(
            leads.companies, leads.jobs
        )
        leads.jobs = await self.leads_processor.deduplicate_jobs(leads.jobs)
        if leads.contacts:
            names = [
                contact.name
                for contact in leads.contacts.contacts
                if contact.name is not None
            ]
            titles = [
                contact.title
                for contact in leads.contacts.contacts
                if contact.title is not None
            ]
            db_contacts = await self.repository.get_contacts_by_name_and_title(
                names, titles
            )

        # Step 4: Match with existing data
        current_step = 4
        await self.task_manager.update_task(
            self.task_uuid,
            "Matching with existing database records",
            "in_progress",
            progress=make_progress(current_step)
        )
        company_names = [
            company.name for company in leads.companies.companies if company.name is not None
        ]
        db_companies = await self.repository.get_companies_by_names(company_names)
        leads.jobs = await self.leads_processor.change_jobs_company_id(
            leads.jobs, leads.companies, db_companies
        )
        leads.companies = await self.leads_processor.new_companies(
            leads.companies, db_companies
        )
        job_titles = [job.job_title for job in leads.jobs.jobs if job.job_title]
        locations = [job.location for job in leads.jobs.jobs if job.location]
        db_jobs = await self.repository.get_jobs_by_title_and_location(
            job_titles, locations
        )
        leads.jobs = await self.leads_processor.new_jobs(leads.jobs, db_jobs)
        if leads.contacts and db_contacts:
            leads.contacts = await self.leads_processor.new_contacts(
                leads.contacts, db_contacts
            )
            leads.contacts = (
                await self.leads_processor.change_contacts_job_and_company_id(
                    leads.contacts, leads.jobs, leads.companies
                )
            )

        # Step 5: Calculate compatibility scores
        current_step = 5
        await self.task_manager.update_task(
            self.task_uuid,
            "Calculating compatibility scores",
            "in_progress",
            progress=make_progress(current_step)
        )
        await self.leads_processor.calculate_compatibility_scores(profile, leads.jobs)

        # Step 6: Enrich leads
        current_step = 6
        await self.task_manager.update_task(
            self.task_uuid,
            "Enriching leads with additional data",
            "in_progress",
            progress=make_progress(current_step)
        )
        await self.leads_processor.enrich_leads(self.enrich_leads, leads, profile, self.task_uuid)
        if leads.contacts:
            leads.contacts = await self.leads_processor.deduplicate_contacts(
                leads.contacts
            )

        # Step 7: Save and complete
        current_step = 7
        await self.task_manager.update_task(
            self.task_uuid,
            "Saving leads to database",
            "in_progress",
            progress=make_progress(current_step)
        )
        leads_result = await self.leads_processor.calculate_statistics(leads)
        await self.repository.save_leads(leads)

        # Store result and mark as completed
        await self.task_manager.store_result(self.task_uuid, leads_result)
        await self.task_manager.update_task(
            self.task_uuid,
            f"Lead insertion completed with companies: {leads_result.companies}, jobs: {leads_result.jobs}, and contacts: {leads_result.contacts} saved",
            "completed",
            progress=make_progress(current_step)
        )
        return leads_result
