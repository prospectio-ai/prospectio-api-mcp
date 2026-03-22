from abc import ABC, abstractmethod
from domain.entities.leads import Leads
from domain.entities.profile import Profile


class ProfileRepositoryPort(ABC):
    """
    Abstract port interface for fetching leads from an external provider.
    """

    @abstractmethod
    async def upsert_profile(self, profile: Profile) -> Leads:
        """
        Fetch leads from the provider.

        Args:
            location (str): The location to search for leads.
            job_title (list[str]): List of job titles to filter leads.
        Returns:
            dict: The leads data retrieved from the provider.
        """
        pass

    @abstractmethod
    async def get_profile(self) -> Profile:
        """
        Retrieve a profile from the database.

        Returns:
            Profile: The profile entity if found, None otherwise.
        """
        pass

    @abstractmethod
    async def delete_profile(self) -> None:
        """
        Delete the profile from the database.

        Returns:
            None
        """
        pass
