"""
Unit tests for the ResetDataUseCase.

Tests cover:
- Successful reset of all data (calls delete_all_data and delete_profile)
- Proper ordering of operations (leads deleted before profile)
- Return value verification
"""

import pytest
from unittest.mock import AsyncMock

from application.use_cases.reset_data import ResetDataUseCase
from domain.ports.profile_respository import ProfileRepositoryPort
from domain.ports.leads_repository import LeadsRepositoryPort


class FakeProfileRepository(ProfileRepositoryPort):
    """Fake implementation of ProfileRepositoryPort for testing."""

    def __init__(self):
        self.delete_profile_called = False
        self.delete_profile_call_order = None

    async def upsert_profile(self, profile):
        pass

    async def get_profile(self):
        return None

    async def delete_profile(self):
        self.delete_profile_called = True


class FakeLeadsRepository(LeadsRepositoryPort):
    """Fake implementation of LeadsRepositoryPort for testing."""

    def __init__(self):
        self.delete_all_data_called = False

    async def save_leads(self, leads):
        pass

    async def get_jobs(self, offset, limit):
        pass

    async def get_jobs_by_title_and_location(self, title, location):
        pass

    async def get_companies(self, offset, limit):
        pass

    async def get_companies_by_names(self, company_names):
        pass

    async def get_contacts(self, offset, limit):
        pass

    async def get_contacts_by_name_and_title(self, names, titles):
        pass

    async def get_contact_by_id(self, id):
        return None

    async def get_company_by_id(self, id):
        return None

    async def get_leads(self, offset, limit):
        pass

    async def get_all_contacts_with_companies(self):
        return []

    async def delete_all_data(self):
        self.delete_all_data_called = True

    async def company_exists_by_name(self, name: str) -> bool:
        return False

    async def get_company_by_name(self, name: str):
        return None

    async def contact_exists_by_email(self, emails: list[str]) -> bool:
        return False

    async def contact_exists_by_name_and_company(self, name: str, company_id) -> bool:
        return False

    async def save_company(self, company):
        return company

    async def save_contact(self, contact):
        return contact

    async def job_exists(self, job_title: str, company_name: str) -> bool:
        return False

    async def save_job(self, job):
        return job

    async def get_or_create_company_stub(self, name: str):
        from domain.entities.company import Company
        return Company(id="stub-id", name=name)


class TestResetDataUseCase:
    """Tests for ResetDataUseCase implementation."""

    @pytest.fixture
    def fake_profile_repository(self) -> FakeProfileRepository:
        """Create a fresh fake profile repository for each test."""
        return FakeProfileRepository()

    @pytest.fixture
    def fake_leads_repository(self) -> FakeLeadsRepository:
        """Create a fresh fake leads repository for each test."""
        return FakeLeadsRepository()

    @pytest.fixture
    def use_case(
        self,
        fake_profile_repository: FakeProfileRepository,
        fake_leads_repository: FakeLeadsRepository
    ) -> ResetDataUseCase:
        """Create a ResetDataUseCase instance with fake repositories."""
        return ResetDataUseCase(
            profile_repository=fake_profile_repository,
            leads_repository=fake_leads_repository
        )

    # --- execute tests ---

    @pytest.mark.asyncio
    async def test_execute_calls_delete_all_data(
        self,
        use_case: ResetDataUseCase,
        fake_leads_repository: FakeLeadsRepository
    ):
        """Should call delete_all_data on leads repository."""
        await use_case.execute()

        assert fake_leads_repository.delete_all_data_called is True

    @pytest.mark.asyncio
    async def test_execute_calls_delete_profile(
        self,
        use_case: ResetDataUseCase,
        fake_profile_repository: FakeProfileRepository
    ):
        """Should call delete_profile on profile repository."""
        await use_case.execute()

        assert fake_profile_repository.delete_profile_called is True

    @pytest.mark.asyncio
    async def test_execute_returns_success_message(
        self,
        use_case: ResetDataUseCase
    ):
        """Should return a success message after reset."""
        result = await use_case.execute()

        assert result == {"result": "All data has been reset successfully"}

    @pytest.mark.asyncio
    async def test_execute_deletes_leads_before_profile(
        self,
        fake_profile_repository: FakeProfileRepository,
        fake_leads_repository: FakeLeadsRepository
    ):
        """Should delete leads data before deleting profile (correct order)."""
        call_order = []

        # Track call order
        original_delete_all = fake_leads_repository.delete_all_data
        original_delete_profile = fake_profile_repository.delete_profile

        async def tracked_delete_all():
            call_order.append("delete_all_data")
            return await original_delete_all()

        async def tracked_delete_profile():
            call_order.append("delete_profile")
            return await original_delete_profile()

        fake_leads_repository.delete_all_data = tracked_delete_all
        fake_profile_repository.delete_profile = tracked_delete_profile

        use_case = ResetDataUseCase(
            profile_repository=fake_profile_repository,
            leads_repository=fake_leads_repository
        )

        await use_case.execute()

        assert call_order == ["delete_all_data", "delete_profile"]

    @pytest.mark.asyncio
    async def test_execute_with_mock_verifies_calls(self):
        """Should verify repository methods are called using mocks."""
        mock_profile_repo = AsyncMock(spec=ProfileRepositoryPort)
        mock_leads_repo = AsyncMock(spec=LeadsRepositoryPort)

        use_case = ResetDataUseCase(
            profile_repository=mock_profile_repo,
            leads_repository=mock_leads_repo
        )

        await use_case.execute()

        mock_leads_repo.delete_all_data.assert_called_once()
        mock_profile_repo.delete_profile.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_propagates_leads_repository_exception(self):
        """Should propagate exception from leads repository."""
        mock_profile_repo = AsyncMock(spec=ProfileRepositoryPort)
        mock_leads_repo = AsyncMock(spec=LeadsRepositoryPort)
        mock_leads_repo.delete_all_data.side_effect = Exception("Database error")

        use_case = ResetDataUseCase(
            profile_repository=mock_profile_repo,
            leads_repository=mock_leads_repo
        )

        with pytest.raises(Exception, match="Database error"):
            await use_case.execute()

        # Profile deletion should NOT be called if leads deletion fails
        mock_profile_repo.delete_profile.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_propagates_profile_repository_exception(self):
        """Should propagate exception from profile repository."""
        mock_profile_repo = AsyncMock(spec=ProfileRepositoryPort)
        mock_leads_repo = AsyncMock(spec=LeadsRepositoryPort)
        mock_profile_repo.delete_profile.side_effect = Exception("Profile deletion error")

        use_case = ResetDataUseCase(
            profile_repository=mock_profile_repo,
            leads_repository=mock_leads_repo
        )

        with pytest.raises(Exception, match="Profile deletion error"):
            await use_case.execute()

        # Leads deletion should have been called before profile
        mock_leads_repo.delete_all_data.assert_called_once()
