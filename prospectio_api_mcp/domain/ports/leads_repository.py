from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from domain.entities.leads import Leads
from domain.entities.company import CompanyEntity, Company
from domain.entities.job import Job, JobEntity
from domain.entities.contact import Contact, ContactEntity


class LeadsRepositoryPort(ABC):
    """
    Abstract port interface for inserting leads into a database.
    """

    @abstractmethod
    async def save_leads(self, leads: Leads) -> None:
        """
        Insert leads into the database.

        Args:
            leads (Leads): The leads data to insert.
        """
        pass

    @abstractmethod
    async def get_jobs(self, offset: int, limit: int) -> JobEntity:
        """
        Retrieve jobs from the database with pagination.

        Args:
            offset (int): Number of jobs to skip.
            limit (int): Maximum number of jobs to return.

        Returns:
            JobEntity: Domain entity containing list of jobs.
        """
        pass

    @abstractmethod
    async def get_jobs_by_title_and_location(
        self, title: list[str], location: list[str]
    ) -> JobEntity:
        """
        Retrieve a job by its title and location from the database.

        Args:
            title (str): The title of the job to search for.
            location (str): The location of the job to search for.

        Returns:
            JobEntity: Domain entity containing the job details.
        """
        pass

    @abstractmethod
    async def get_companies(self, offset: int, limit: int) -> CompanyEntity:
        """
        Retrieve companies from the database.

        Returns:
            CompanyEntity: Domain entity containing list of companies.
        """
        pass

    @abstractmethod
    async def get_companies_by_names(self, company_names: List[str]) -> CompanyEntity:
        """
        Retrieve companies by their names from the database.

        Args:
            company_names (List[str]): List of company names to search for.

        Returns:
            CompanyEntity: Domain entity containing list of companies matching the names.
        """
        pass

    @abstractmethod
    async def get_contacts(self, offset: int, limit: int) -> ContactEntity:
        """
        Retrieve contacts from the database.

        Returns:
            ContactEntity: Domain entity containing list of contacts.
        """
        pass

    @abstractmethod
    async def get_contacts_by_name_and_title(
        self, names: list[str], titles: list[str]
    ) -> ContactEntity:
        """
        Retrieve contacts by their name and title from the database.
        Args:
            name (str): The name of the contact to search for.
            title (str): The title of the contact to search for.

        Returns:
            ContactEntity: Domain entity containing list of contacts matching the name and title.
        """
        pass

    @abstractmethod
    async def get_contact_by_id(self, id: str) -> Optional[Contact]:
        """
        Retrieve a contact by its ID from the database.

        Args:
            id (str): The ID of the contact to search for.

        Returns:
            Optional[ContactEntity]: Domain entity containing the contact details if found, else None.
        """
        pass

    @abstractmethod
    async def get_company_by_id(self, id: str) -> Optional[Company]:
        """
        Retrieve a company by its ID from the database.

        Args:
            id (str): The ID of the company to search for.

        Returns:
            Optional[CompanyEntity]: Domain entity containing the company details if found, else None.
        """
        pass

    @abstractmethod
    async def get_leads(self, offset: int, limit: int) -> Leads:
        """
        Retrieve all leads data (companies, jobs, and contacts) from the database.

        Returns:
            Leads: Domain entity containing all companies, jobs, and contacts.
        """
        pass

    @abstractmethod
    async def get_all_contacts_with_companies(self) -> List[Tuple[Contact, Company]]:
        """
        Retrieve all contacts with their associated companies from the database.

        Returns:
            List[Tuple[Contact, Company]]: List of tuples containing contact and company pairs.
        """
        pass

    @abstractmethod
    async def delete_all_data(self) -> None:
        """
        Delete all leads data (contacts, jobs, companies) from the database.
        Deletes in correct order to respect foreign key constraints:
        1. Contacts (references jobs and companies)
        2. Jobs (references companies)
        3. Companies

        Returns:
            None
        """
        pass

    @abstractmethod
    async def company_exists_by_name(self, name: str) -> bool:
        """
        Check if a company with the given name already exists in the database.

        Args:
            name: The name of the company to check.

        Returns:
            bool: True if a company with this name exists, False otherwise.
        """
        pass

    @abstractmethod
    async def get_company_by_name(self, name: str) -> Optional[Company]:
        """
        Retrieve a company by its name from the database.

        Args:
            name: The name of the company to search for.

        Returns:
            Optional[Company]: The company if found, None otherwise.
        """
        pass

    @abstractmethod
    async def contact_exists_by_email(self, emails: list[str]) -> bool:
        """
        Check if a contact with any of the given emails already exists in the database.

        Args:
            emails: List of email addresses to check.

        Returns:
            bool: True if a contact with any of these emails exists, False otherwise.
        """
        pass

    @abstractmethod
    async def contact_exists_by_name_and_company(
        self, name: str, company_id: Optional[str]
    ) -> bool:
        """
        Check if a contact with the given name and company already exists in the database.

        Used for deduplication when a contact has no email address.

        Args:
            name: The name of the contact to check.
            company_id: The company ID to check (can be None).

        Returns:
            bool: True if a contact with this name and company exists, False otherwise.
        """
        pass

    @abstractmethod
    async def save_company(self, company: Company) -> Company:
        """
        Save a single company to the database.

        Args:
            company: The company entity to save.

        Returns:
            Company: The saved company with its generated ID.
        """
        pass

    @abstractmethod
    async def save_contact(self, contact: Contact) -> Contact:
        """
        Save a single contact to the database.

        Args:
            contact: The contact entity to save.

        Returns:
            Contact: The saved contact with its generated ID.
        """
        pass

    @abstractmethod
    async def job_exists(self, job_title: str, company_name: str) -> bool:
        """
        Check if a job with the given title and company name already exists in the database.

        Args:
            job_title: The title of the job.
            company_name: The name of the company.

        Returns:
            bool: True if a job with this title and company exists, False otherwise.
        """
        pass

    @abstractmethod
    async def save_job(self, job: Job) -> Job:
        """
        Save a single job to the database.

        Args:
            job: The job entity to save.

        Returns:
            Job: The saved job with its generated ID.
        """
        pass

    @abstractmethod
    async def get_or_create_company_stub(self, name: str) -> Company:
        """
        Get an existing company by name or create a minimal stub company.

        This is used when saving jobs to ensure the company_id foreign key
        constraint is satisfied. Creates a stub company with only the name
        if the company does not exist yet.

        Args:
            name: The name of the company.

        Returns:
            Company: The existing or newly created stub company with its ID.
        """
        pass
