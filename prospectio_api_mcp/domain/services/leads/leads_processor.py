from config import LLMConfig
from domain.entities.company import CompanyEntity
from domain.entities.job import Job, JobEntity
from domain.entities.leads import Leads
from domain.entities.leads_result import LeadsResult
from domain.entities.profile import Profile
from domain.ports.compatibility_score import CompatibilityScorePort
from domain.entities.contact import ContactEntity
from domain.ports.enrich_leads import EnrichLeadsPort
import asyncio

from domain.ports.task_manager import TaskManagerPort


class LeadsProcessor:

    def __init__(self, compatibility_score_port: CompatibilityScorePort):
        config = LLMConfig() # type: ignore
        concurrency_limit = config.CONCURRENT_CALLS
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.compatibility_score_port = compatibility_score_port

    def deduplicate_contacts(self, contacts: ContactEntity) -> ContactEntity:
        """
        Remove duplicate contacts based on normalized name and title.

        Args:
            contacts (ContactEntity): Contacts to deduplicate.

        Returns:
            ContactEntity: Entity containing only unique contacts.
        """
        seen = set()
        unique_contacts = []
        for contact in contacts.contacts:
            contact.name = contact.name.strip().lower() if contact.name else ""
            contact.title = contact.title.strip().lower() if contact.title else ""
            identifier = (contact.name, contact.title)
            if identifier not in seen and contact.email and contact.title:
                seen.add(identifier)
                unique_contacts.append(contact)
        return ContactEntity(contacts=unique_contacts) # type: ignore

    def new_contacts(
        self, contacts: ContactEntity, db_contacts: ContactEntity
    ) -> ContactEntity:
        """
        Filter out contacts that already exist in the database, based on normalized name and title.

        Args:
            contacts (ContactEntity): Contacts to check for uniqueness.
            db_contacts (ContactEntity): Contacts already present in the database.

        Returns:
            ContactEntity: Entity containing only new contacts not present in the database.
        """
        existing_contacts = {
            (
                contact.name.strip().lower() if contact.name else "",
                contact.title.strip().lower() if contact.title else "",
            )
            for contact in db_contacts.contacts
        }
        new_contacts = [
            contact
            for contact in contacts.contacts
            if (
                contact.name.strip().lower() if contact.name else "",
                contact.title.strip().lower() if contact.title else "",
            )
            not in existing_contacts
        ]
        return ContactEntity(contacts=new_contacts) # type: ignore

    def change_contacts_job_and_company_id(
        self, contacts: ContactEntity, jobs: JobEntity, companies: CompanyEntity
    ) -> ContactEntity:
        """
        Update the job_id and company_id of each contact to match the corresponding job and company in the provided entities, using normalized name/title for jobs and companies.

        Args:
            contacts (ContactEntity): Contacts to update.
            jobs (JobEntity): Jobs to match for job_id.
            companies (CompanyEntity): Companies to match for company_id.

        Returns:
            ContactEntity: Contacts with updated job_id and company_id if a match is found.
        """
        job_lookup = {
            (
                job.job_title.strip().lower() if job.job_title else "",
                job.location.strip().lower() if job.location else "",
            ): job.id
            for job in jobs.jobs
            if job.id is not None
            and job.job_title is not None
            and job.location is not None
        }
        company_lookup = {
            company.name.strip().lower(): company.id
            for company in companies.companies
            if company.id is not None and company.name is not None
        }
        for contact in contacts.contacts:
            if contact.company_id:
                name = contact.company_id.strip().lower()
                contact.company_id = company_lookup.get(name, contact.company_id)
            if contact.title and contact.company_id:
                key = (
                    contact.title.strip().lower(),
                    contact.company_id.strip().lower(),
                )
                contact.job_id = job_lookup.get(key, contact.job_id)
        return contacts

    def change_jobs_company_id(
        self, jobs: JobEntity, companies: CompanyEntity, db_companies: CompanyEntity
    ) -> JobEntity:
        """
        Update the company_id of each job to match the corresponding company in the database, using normalized company names.

        Args:
            jobs (JobEntity): Jobs to update.
            companies (CompanyEntity): Companies from the current batch.
            db_companies (CompanyEntity): Companies from the database.

        Returns:
            JobEntity: Jobs with updated company_id if a match is found in the database.
        """
        company_db_mapping = {
            company.name.strip().lower(): company.id
            for company in db_companies.companies
            if company.name is not None
        }
        company_ids = {
            company.id: company.name.strip().lower()
            for company in companies.companies
            if company.id is not None and company.name is not None
        }
        for job in jobs.jobs:
            if job.company_id and job.company_id in company_ids:
                company_name = company_ids[job.company_id]
                company_id = company_db_mapping.get(company_name)
                if company_id is not None:
                    job.company_id = company_id
        return jobs

    def new_jobs(self, jobs: JobEntity, db_jobs: JobEntity) -> JobEntity:
        """
        Filter out jobs that already exist in the database, based on normalized job title, location, type, and company_id.

        Args:
            jobs (JobEntity): Jobs to check for uniqueness.
            db_jobs (JobEntity): Jobs already present in the database.

        Returns:
            JobEntity: Entity containing only new jobs not present in the database.
        """
        existing_jobs = {
            (
                job.job_title.strip().lower() if job.job_title else "",
                job.location.strip().lower() if job.location else "",
                job.company_id.strip().lower() if job.company_id else "",
                job.job_type.strip().lower() if job.job_type else "",
                job.description.strip().lower() if job.description else "",
            )
            for job in db_jobs.jobs
        }

        new_jobs = [
            job
            for job in jobs.jobs
            if (
                job.job_title.strip().lower() if job.job_title else "",
                job.location.strip().lower() if job.location else "",
                job.company_id.strip().lower() if job.company_id else "",
                job.job_type.strip().lower() if job.job_type else "",
                job.description.strip().lower() if job.description else "",
            )
            not in existing_jobs
        ]
        return JobEntity(jobs=new_jobs) # type: ignore

    def new_companies(
        self, companies: CompanyEntity, db_companies: CompanyEntity
    ) -> CompanyEntity:
        """
        Filter out companies that already exist in the database, based on normalized company names.

        Args:
            companies (CompanyEntity): Companies to check for uniqueness.
            db_companies (CompanyEntity): Companies already present in the database.

        Returns:
            CompanyEntity: Entity containing only new companies not present in the database.
        """
        existing_companies = {
            company.name.strip().lower()
            for company in db_companies.companies
            if company.name is not None
        }
        new_companies = [
            company
            for company in companies.companies
            if company.name and company.name.strip().lower() not in existing_companies
        ]
        return CompanyEntity(companies=new_companies) # type: ignore

    def deduplicate_jobs(self, jobs: JobEntity) -> JobEntity:
        """
        Remove duplicate jobs based on normalized title, location, type, and company_id.

        Args:
            jobs (JobEntity): Jobs to deduplicate.

        Returns:
            JobEntity: Entity containing only unique jobs.
        """
        seen = set()
        unique_jobs = []
        for job in jobs.jobs:
            job.job_title = job.job_title.strip().lower() if job.job_title else ""
            job.location = job.location.strip().lower() if job.location else ""
            job.job_type = job.job_type.strip().lower() if job.job_type else ""
            job.company_id = job.company_id.strip().lower() if job.company_id else ""

            identifier = (job.job_title, job.location, job.job_type, job.company_id)
            if identifier not in seen:
                seen.add(identifier)
                unique_jobs.append(job)

        return JobEntity(jobs=unique_jobs) # type: ignore

    def deduplicate_companies(
        self, companies: CompanyEntity, jobs: JobEntity
    ) -> CompanyEntity:
        """
        Remove duplicate companies based on normalized company names and update jobs to reference the deduplicated companies.

        Args:
            companies (CompanyEntity): Companies to deduplicate.
            jobs (JobEntity): Jobs referencing companies.

        Returns:
            CompanyEntity: Entity containing only unique companies.
        """
        seen = set()
        unique_companies = []
        companies_mapping = {
            company.id: company.name.strip().lower()
            for company in companies.companies
            if company.name is not None
        }
        unique_companies_mapping = {}

        for company in companies.companies:
            company.name = company.name.strip().lower() if company.name else ""
            if company.name not in seen:
                seen.add(company.name)
                unique_companies.append(company)
                unique_companies_mapping[company.name] = company.id

        for job in jobs.jobs:
            if job.company_id in companies_mapping:
                company_name = companies_mapping[job.company_id]
                job.company_id = unique_companies_mapping.get(company_name)

        return CompanyEntity(companies=unique_companies) # type: ignore

    def calculate_statistics(self, leads: Leads) -> LeadsResult:
        """
        Calculate and return statistics about the inserted leads (companies, jobs, contacts).

        Args:
            leads (Leads): The leads entity containing companies, jobs, and contacts.

        Returns:
            LeadsResult: Statistics about the number of inserted companies, jobs, and contacts.
        """
        nb_of_companies = len(leads.companies.companies) if leads.companies else 0
        nb_of_jobs = len(leads.jobs.jobs) if leads.jobs else 0
        nb_of_contacts = len(leads.contacts.contacts) if leads.contacts else 0

        return LeadsResult(
            companies=f"Insert of {nb_of_companies} companies",
            jobs=f"insert of {nb_of_jobs} jobs",
            contacts=f"insert of {nb_of_contacts} contacts",
        )

    async def calculate_compatibility_scores(
        self, profile: Profile, jobs: JobEntity
    ) -> JobEntity:
        """
        Calculate compatibility scores for each job using the provided profile and update the jobs in place.

        Args:
            profile (Profile): The user profile to use for scoring.
            jobs (JobEntity): Jobs to score and update.

        Returns:
            JobEntity: Jobs with updated compatibility_score fields.
        """

        async def calculate_single_score(job: Job):
            async with self.semaphore:
                if not job.description:
                    return job, 0
                result = await self.compatibility_score_port.get_compatibility_score(
                    profile=profile,
                    job_description=job.description,
                    job_location=job.location or "",
                )
                return job, result.score

        tasks = [calculate_single_score(job) for job in jobs.jobs]
        results = await asyncio.gather(*tasks)

        for job, score in results:
            job.compatibility_score = score

        return jobs

    async def enrich_leads(self, enrich_leads: EnrichLeadsPort, leads: Leads, profile: Profile, task_uuid: str) -> Leads:
        """
        Enrich leads with deduplication and compatibility scoring.

        This method is a placeholder for future enrichment logic.
        """
        return await enrich_leads.execute(leads, profile, task_uuid)
