"""Fake implementation of LeadsRepositoryPort for unit testing."""

from typing import List, Optional, Tuple
import uuid

from domain.ports.leads_repository import LeadsRepositoryPort
from domain.entities.leads import Leads
from domain.entities.company import Company, CompanyEntity
from domain.entities.job import Job, JobEntity
from domain.entities.contact import Contact, ContactEntity


class FakeLeadsRepository(LeadsRepositoryPort):
    """
    In-memory fake implementation of LeadsRepositoryPort for testing.

    This test double stores data in memory and provides predictable behavior
    for unit tests without requiring a real database connection.
    """

    def __init__(self) -> None:
        """Initialize empty in-memory storage."""
        self._companies: dict[str, Company] = {}
        self._jobs: dict[str, Job] = {}
        self._contacts: dict[str, Contact] = {}

    def reset(self) -> None:
        """Clear all stored data. Useful between tests."""
        self._companies.clear()
        self._jobs.clear()
        self._contacts.clear()

    async def save_leads(self, leads: Leads) -> None:
        """
        Insert leads into in-memory storage.

        Args:
            leads: The leads data to insert.
        """
        if leads.companies:
            for company in leads.companies.companies:
                company_id = company.id or str(uuid.uuid4())
                company.id = company_id
                self._companies[company_id] = company

        if leads.jobs:
            for job in leads.jobs.jobs:
                job_id = job.id or str(uuid.uuid4())
                job.id = job_id
                self._jobs[job_id] = job

        if leads.contacts:
            for contact in leads.contacts.contacts:
                contact_id = contact.id or str(uuid.uuid4())
                contact.id = contact_id
                self._contacts[contact_id] = contact

    async def get_jobs(self, offset: int, limit: int) -> JobEntity:
        """
        Retrieve jobs from in-memory storage with pagination.

        Args:
            offset: Number of jobs to skip.
            limit: Maximum number of jobs to return.

        Returns:
            JobEntity: Domain entity containing list of jobs.
        """
        jobs_list = list(self._jobs.values())
        paginated = jobs_list[offset:offset + limit]
        return JobEntity(jobs=paginated)

    async def get_jobs_by_title_and_location(
        self, title: list[str], location: list[str]
    ) -> JobEntity:
        """
        Retrieve jobs by title and location from in-memory storage.

        Args:
            title: The titles to search for.
            location: The locations to search for.

        Returns:
            JobEntity: Domain entity containing matching jobs.
        """
        matching_jobs = [
            job for job in self._jobs.values()
            if (not title or job.job_title in title) and
               (not location or job.location in location)
        ]
        return JobEntity(jobs=matching_jobs)

    async def get_companies(self, offset: int, limit: int) -> CompanyEntity:
        """
        Retrieve companies from in-memory storage with pagination.

        Args:
            offset: Number of companies to skip.
            limit: Maximum number of companies to return.

        Returns:
            CompanyEntity: Domain entity containing list of companies.
        """
        companies_list = list(self._companies.values())
        paginated = companies_list[offset:offset + limit]
        total_pages = (len(companies_list) + limit - 1) // limit if limit > 0 else 1
        return CompanyEntity(companies=paginated, pages=total_pages)

    async def get_companies_by_names(self, company_names: List[str]) -> CompanyEntity:
        """
        Retrieve companies by their names from in-memory storage.

        Args:
            company_names: List of company names to search for.

        Returns:
            CompanyEntity: Domain entity containing matching companies.
        """
        matching = [
            company for company in self._companies.values()
            if company.name in company_names
        ]
        return CompanyEntity(companies=matching)

    async def get_contacts(self, offset: int, limit: int) -> ContactEntity:
        """
        Retrieve contacts from in-memory storage with pagination.

        Args:
            offset: Number of contacts to skip.
            limit: Maximum number of contacts to return.

        Returns:
            ContactEntity: Domain entity containing list of contacts.
        """
        contacts_list = list(self._contacts.values())
        paginated = contacts_list[offset:offset + limit]
        total_pages = (len(contacts_list) + limit - 1) // limit if limit > 0 else 1
        return ContactEntity(contacts=paginated, pages=total_pages)

    async def get_contacts_by_name_and_title(
        self, names: list[str], titles: list[str]
    ) -> ContactEntity:
        """
        Retrieve contacts by name and title from in-memory storage.

        Args:
            names: The names to search for.
            titles: The titles to search for.

        Returns:
            ContactEntity: Domain entity containing matching contacts.
        """
        matching = [
            contact for contact in self._contacts.values()
            if (not names or contact.name in names) and
               (not titles or contact.title in titles)
        ]
        return ContactEntity(contacts=matching)

    async def get_contact_by_id(self, id: str) -> Optional[Contact]:
        """
        Retrieve a contact by ID from in-memory storage.

        Args:
            id: The ID of the contact to search for.

        Returns:
            Optional[Contact]: The contact if found, else None.
        """
        return self._contacts.get(id)

    async def get_company_by_id(self, id: str) -> Optional[Company]:
        """
        Retrieve a company by ID from in-memory storage.

        Args:
            id: The ID of the company to search for.

        Returns:
            Optional[Company]: The company if found, else None.
        """
        return self._companies.get(id)

    async def get_leads(self, offset: int, limit: int) -> Leads:
        """
        Retrieve all leads data from in-memory storage.

        Args:
            offset: Number of items to skip.
            limit: Maximum number of items to return.

        Returns:
            Leads: Domain entity containing all companies, jobs, and contacts.
        """
        companies = await self.get_companies(offset, limit)
        jobs = await self.get_jobs(offset, limit)
        contacts = await self.get_contacts(offset, limit)

        return Leads(
            companies=companies,
            jobs=jobs,
            contacts=contacts,
            pages=max(companies.pages or 1, contacts.pages or 1)
        )

    async def get_all_contacts_with_companies(self) -> List[Tuple[Contact, Company]]:
        """
        Retrieve all contacts with their associated companies.

        Returns:
            List[Tuple[Contact, Company]]: List of contact-company pairs.
        """
        result: List[Tuple[Contact, Company]] = []
        for contact in self._contacts.values():
            if contact.company_id and contact.company_id in self._companies:
                company = self._companies[contact.company_id]
                result.append((contact, company))
        return result

    async def delete_all_data(self) -> None:
        """Delete all leads data from in-memory storage."""
        self.reset()

    async def company_exists_by_name(self, name: str) -> bool:
        """
        Check if a company with the given name exists in storage.

        Args:
            name: The name of the company to check.

        Returns:
            bool: True if a company with this name exists, False otherwise.
        """
        return any(
            company.name == name
            for company in self._companies.values()
        )

    async def get_company_by_name(self, name: str) -> Optional[Company]:
        """
        Retrieve a company by its name from in-memory storage.

        Args:
            name: The name of the company to search for.

        Returns:
            Optional[Company]: The company if found, None otherwise.
        """
        for company in self._companies.values():
            if company.name == name:
                return company
        return None

    async def contact_exists_by_email(self, emails: list[str]) -> bool:
        """
        Check if a contact with any of the given emails exists in storage.

        Args:
            emails: List of email addresses to check.

        Returns:
            bool: True if a contact with any of these emails exists, False otherwise.
        """
        emails_set = set(emails)
        for contact in self._contacts.values():
            if contact.email:
                if emails_set.intersection(contact.email):
                    return True
        return False

    async def contact_exists_by_name_and_company(
        self, name: str, company_id: Optional[str]
    ) -> bool:
        """
        Check if a contact with the given name and company exists in storage.

        Used for deduplication when a contact has no email address.

        Args:
            name: The name of the contact to check.
            company_id: The company ID to check (can be None).

        Returns:
            bool: True if a contact with this name and company exists, False otherwise.
        """
        name_lower = name.lower()
        for contact in self._contacts.values():
            if contact.name and contact.name.lower() == name_lower:
                if company_id is None and contact.company_id is None:
                    return True
                if company_id and contact.company_id == company_id:
                    return True
        return False

    async def save_company(self, company: Company) -> Company:
        """
        Save a single company to in-memory storage.

        Args:
            company: The company entity to save.

        Returns:
            Company: The saved company with its generated ID.
        """
        company_id = company.id or str(uuid.uuid4())
        saved_company = Company(**{**company.model_dump(), "id": company_id})
        self._companies[company_id] = saved_company
        return saved_company

    async def save_contact(self, contact: Contact) -> Contact:
        """
        Save a single contact to in-memory storage.

        Args:
            contact: The contact entity to save.

        Returns:
            Contact: The saved contact with its generated ID.
        """
        contact_id = contact.id or str(uuid.uuid4())
        saved_contact = Contact(**{**contact.model_dump(), "id": contact_id})
        self._contacts[contact_id] = saved_contact
        return saved_contact

    async def job_exists(self, job_title: str, company_name: str) -> bool:
        """
        Check if a job with the given title and company name exists in storage.

        Args:
            job_title: The title of the job.
            company_name: The name of the company.

        Returns:
            bool: True if a job with this title and company exists, False otherwise.
        """
        for job in self._jobs.values():
            if job.job_title == job_title and job.company_name == company_name:
                return True
        return False

    async def save_job(self, job: Job) -> Job:
        """
        Save a single job to in-memory storage.

        Args:
            job: The job entity to save.

        Returns:
            Job: The saved job with its generated ID.
        """
        job_id = job.id or str(uuid.uuid4())
        saved_job = Job(**{**job.model_dump(), "id": job_id})
        self._jobs[job_id] = saved_job
        return saved_job

    async def get_or_create_company_stub(self, name: str) -> Company:
        """
        Get an existing company by name or create a minimal stub company.

        Args:
            name: The name of the company.

        Returns:
            Company: The existing or newly created stub company with its ID.
        """
        # Check if company already exists
        for company in self._companies.values():
            if company.name == name:
                return company

        # Create stub company
        company_id = str(uuid.uuid4())
        stub_company = Company(id=company_id, name=name)
        self._companies[company_id] = stub_company
        return stub_company
