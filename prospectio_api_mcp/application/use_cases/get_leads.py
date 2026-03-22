from domain.entities.company import CompanyEntity
from domain.entities.contact import ContactEntity
from domain.entities.job import JobEntity
from domain.entities.leads import Leads
from domain.ports.leads_repository import LeadsRepositoryPort


class GetLeadsUseCase:
    """
    Use case for retrieving different types of data (companies, jobs, contacts, leads) from the repository.
    This class acts as a dispatcher to fetch specific data types based on the requested type.
    """

    def __init__(self, type: str, repository: LeadsRepositoryPort):
        """
        Initialize the InsertCompanyJobsUseCase with the data type and repository.

        Args:
            type (str): The data type to retrieve ('companies', 'jobs', 'contacts', or 'leads').
            repository (LeadsRepositoryPort): The repository interface for data access.
        """
        self.type = type
        self.repository = repository

    async def get_leads(
        self, offset: int, limit: int
    ) -> Leads | CompanyEntity | JobEntity | ContactEntity:
        """
        Retrieve data based on the specified type from the repository.

        Returns:
            Union[Leads, CompanyEntity, JobEntity, ContactEntity]: The retrieved data object
            corresponding to the requested type.

        Raises:
            KeyError: If the specified type is not supported ('companies', 'jobs', 'contacts', 'leads').
        """
        if self.type == "companies":
            return await self.repository.get_companies(offset, limit)
        elif self.type == "jobs":
            return await self.repository.get_jobs(offset, limit)
        elif self.type == "contacts":
            return await self.repository.get_contacts(offset, limit)
        elif self.type == "leads":
            return await self.repository.get_leads(offset, limit)
        else:
            raise KeyError(f"Unsupported type: {self.type}")
