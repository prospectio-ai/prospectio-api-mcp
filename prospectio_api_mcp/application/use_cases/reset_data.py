from domain.ports.profile_respository import ProfileRepositoryPort
from domain.ports.leads_repository import LeadsRepositoryPort


class ResetDataUseCase:
    """
    Use case for resetting all user data.
    Deletes profile and all leads data (contacts, jobs, companies).
    """

    def __init__(
        self,
        profile_repository: ProfileRepositoryPort,
        leads_repository: LeadsRepositoryPort,
    ):
        """
        Initialize the reset data use case.

        Args:
            profile_repository (ProfileRepositoryPort): Repository for profile operations.
            leads_repository (LeadsRepositoryPort): Repository for leads operations.
        """
        self.profile_repository = profile_repository
        self.leads_repository = leads_repository

    async def execute(self) -> dict:
        """
        Execute the reset operation.
        Deletes all leads data first, then the profile.

        Returns:
            dict: Result message indicating successful reset.
        """
        await self.leads_repository.delete_all_data()
        await self.profile_repository.delete_profile()
        return {"result": "All data has been reset successfully"}
