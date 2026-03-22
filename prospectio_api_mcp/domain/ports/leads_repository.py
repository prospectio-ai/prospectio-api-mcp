from abc import ABC, abstractmethod
from typing import List, Optional
from domain.entities.leads import Leads
from domain.entities.company import CompanyEntity, Company
from domain.entities.job import JobEntity
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
    async def get_all_contacts_with_companies(self) -> list:
        """
        Retrieve all contacts with their associated companies.

        Returns:
            list: List of contacts with company information.
        """
        pass

    @abstractmethod
    async def delete_all_data(self) -> None:
        """
        Delete all leads data (companies, jobs, and contacts) from the database.
        """
        pass

    @abstractmethod
    async def company_exists_by_name(self, name: str) -> bool:
        """
        Check if a company exists by name.

        Args:
            name: The company name to check.

        Returns:
            True if the company exists.
        """
        pass

    @abstractmethod
    async def get_company_by_name(self, name: str) -> Optional[Company]:
        """
        Retrieve a company by its name.

        Args:
            name: The company name.

        Returns:
            The company if found, else None.
        """
        pass

    @abstractmethod
    async def contact_exists_by_email(self, emails: list[str]) -> bool:
        """
        Check if a contact exists by email.

        Args:
            emails: List of email addresses to check.

        Returns:
            True if a contact with any of the emails exists.
        """
        pass

    @abstractmethod
    async def contact_exists_by_name_and_company(self, name: str, company_id) -> bool:
        """
        Check if a contact exists by name and company.

        Args:
            name: The contact name.
            company_id: The company ID.

        Returns:
            True if the contact exists.
        """
        pass

    @abstractmethod
    async def save_company(self, company: Company) -> Company:
        """
        Save a company to the database.

        Args:
            company: The company entity to save.

        Returns:
            The saved company entity.
        """
        pass

    @abstractmethod
    async def save_contact(self, contact: Contact) -> Contact:
        """
        Save a contact to the database.

        Args:
            contact: The contact entity to save.

        Returns:
            The saved contact entity.
        """
        pass

    @abstractmethod
    async def job_exists(self, job_title: str, company_name: str) -> bool:
        """
        Check if a job exists by title and company name.

        Args:
            job_title: The job title.
            company_name: The company name.

        Returns:
            True if the job exists.
        """
        pass

    @abstractmethod
    async def save_job(self, job) -> None:
        """
        Save a job to the database.

        Args:
            job: The job entity to save.
        """
        pass

    @abstractmethod
    async def get_or_create_company_stub(self, name: str) -> Company:
        """
        Get an existing company or create a stub company by name.

        Args:
            name: The company name.

        Returns:
            The existing or newly created company.
        """
        pass
