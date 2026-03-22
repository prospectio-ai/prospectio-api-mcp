"""
Tests for application/use_cases/generate_campaign.py - GenerateCampaignUseCase.
"""
import pytest
from unittest.mock import AsyncMock

from application.use_cases.generate_campaign import GenerateCampaignUseCase
from domain.entities.campaign import CampaignStatus
from domain.entities.contact import Contact
from domain.entities.company import Company
from domain.entities.profile import Profile
from domain.entities.prospect_message import ProspectMessage
from tests.doubles.repositories import FakeCampaignRepository, FakeProfileRepository
from tests.doubles.ports import FakeGenerateMessagePort


class TestGenerateCampaignUseCase:
    """Test suite for GenerateCampaignUseCase."""

    @pytest.fixture
    def fake_profile_repository(self):
        return FakeProfileRepository()

    @pytest.fixture
    def fake_campaign_repository(self):
        return FakeCampaignRepository()

    @pytest.fixture
    def fake_message_port(self):
        return FakeGenerateMessagePort()

    @pytest.fixture
    def mock_task_manager(self):
        manager = AsyncMock()
        return manager

    @pytest.fixture
    def sample_profile(self):
        return Profile(
            job_title="Senior Dev",
            location="Paris",
            bio="Experienced developer",
        )

    @pytest.fixture
    def sample_contacts_with_companies(self):
        return [
            (
                Contact(id="c1", company_id="co1", name="Alice", email=["alice@co.com"]),
                Company(id="co1", name="CompanyA", industry="Tech"),
            ),
            (
                Contact(id="c2", company_id="co2", name="Bob", email=["bob@co.com"]),
                Company(id="co2", name="CompanyB", industry="Fintech"),
            ),
        ]

    def _create_use_case(
        self,
        task_uuid,
        campaign_name,
        profile_repo,
        campaign_repo,
        message_port,
        task_manager,
    ):
        return GenerateCampaignUseCase(
            task_uuid=task_uuid,
            campaign_name=campaign_name,
            profile_repository=profile_repo,
            campaign_repository=campaign_repo,
            message_port=message_port,
            task_manager=task_manager,
        )

    @pytest.mark.asyncio
    async def test_raises_when_profile_not_found(
        self,
        fake_profile_repository,
        fake_campaign_repository,
        fake_message_port,
        mock_task_manager,
    ):
        """Should raise ValueError and mark task as failed when profile is missing."""
        uc = self._create_use_case(
            "task-1", "Test Campaign",
            fake_profile_repository, fake_campaign_repository,
            fake_message_port, mock_task_manager,
        )

        with pytest.raises(ValueError, match="Profile not found"):
            await uc.generate_campaign()

        mock_task_manager.update_task.assert_called()
        call_args = mock_task_manager.update_task.call_args
        assert call_args[1].get("status") == "failed" or call_args[0][2] == "failed"

    @pytest.mark.asyncio
    async def test_returns_empty_result_when_no_contacts(
        self,
        fake_profile_repository,
        fake_campaign_repository,
        fake_message_port,
        mock_task_manager,
        sample_profile,
    ):
        """Should return result with 0 contacts when no contacts available."""
        fake_profile_repository.set_profile(sample_profile)

        uc = self._create_use_case(
            "task-2", "Empty Campaign",
            fake_profile_repository, fake_campaign_repository,
            fake_message_port, mock_task_manager,
        )

        result = await uc.generate_campaign()

        assert result.total_contacts == 0
        assert result.successful == 0
        assert result.failed == 0
        assert result.messages == []

    @pytest.mark.asyncio
    async def test_generates_messages_for_all_contacts(
        self,
        fake_profile_repository,
        fake_campaign_repository,
        fake_message_port,
        mock_task_manager,
        sample_profile,
        sample_contacts_with_companies,
    ):
        """Should generate messages for every contact."""
        fake_profile_repository.set_profile(sample_profile)
        fake_campaign_repository.add_contacts_with_companies(sample_contacts_with_companies)

        uc = self._create_use_case(
            "task-3", "Full Campaign",
            fake_profile_repository, fake_campaign_repository,
            fake_message_port, mock_task_manager,
        )

        result = await uc.generate_campaign()

        assert result.total_contacts == 2
        assert result.successful == 2
        assert result.failed == 0
        assert len(result.messages) == 2

    @pytest.mark.asyncio
    async def test_campaign_marked_completed(
        self,
        fake_profile_repository,
        fake_campaign_repository,
        fake_message_port,
        mock_task_manager,
        sample_profile,
        sample_contacts_with_companies,
    ):
        """Should mark campaign as COMPLETED when at least one message succeeds."""
        fake_profile_repository.set_profile(sample_profile)
        fake_campaign_repository.add_contacts_with_companies(sample_contacts_with_companies)

        uc = self._create_use_case(
            "task-4", "Completed Campaign",
            fake_profile_repository, fake_campaign_repository,
            fake_message_port, mock_task_manager,
        )

        await uc.generate_campaign()

        campaigns = fake_campaign_repository.get_all_campaigns()
        assert len(campaigns) == 1
        assert campaigns[0].status == CampaignStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_campaign_marked_failed_when_all_fail(
        self,
        fake_profile_repository,
        fake_campaign_repository,
        fake_message_port,
        mock_task_manager,
        sample_profile,
        sample_contacts_with_companies,
    ):
        """Should mark campaign as FAILED when all messages fail."""
        fake_profile_repository.set_profile(sample_profile)
        fake_campaign_repository.add_contacts_with_companies(sample_contacts_with_companies)

        for contact, _ in sample_contacts_with_companies:
            fake_message_port.set_should_fail_for(contact.id or "")

        uc = self._create_use_case(
            "task-5", "Failed Campaign",
            fake_profile_repository, fake_campaign_repository,
            fake_message_port, mock_task_manager,
        )

        result = await uc.generate_campaign()

        assert result.failed == 2
        assert result.successful == 0
        campaigns = fake_campaign_repository.get_all_campaigns()
        assert campaigns[0].status == CampaignStatus.FAILED

    @pytest.mark.asyncio
    async def test_stores_result_in_task_manager(
        self,
        fake_profile_repository,
        fake_campaign_repository,
        fake_message_port,
        mock_task_manager,
        sample_profile,
        sample_contacts_with_companies,
    ):
        """Should store the result via task_manager.store_result."""
        fake_profile_repository.set_profile(sample_profile)
        fake_campaign_repository.add_contacts_with_companies(sample_contacts_with_companies)

        uc = self._create_use_case(
            "task-6", "Store Result Campaign",
            fake_profile_repository, fake_campaign_repository,
            fake_message_port, mock_task_manager,
        )

        result = await uc.generate_campaign()

        mock_task_manager.store_result.assert_called_once_with("task-6", result)

    @pytest.mark.asyncio
    async def test_handles_partial_failures(
        self,
        fake_profile_repository,
        fake_campaign_repository,
        fake_message_port,
        mock_task_manager,
        sample_profile,
        sample_contacts_with_companies,
    ):
        """Should handle mix of successes and failures."""
        fake_profile_repository.set_profile(sample_profile)
        fake_campaign_repository.add_contacts_with_companies(sample_contacts_with_companies)
        fake_message_port.set_should_fail_for("c1")

        uc = self._create_use_case(
            "task-7", "Partial Campaign",
            fake_profile_repository, fake_campaign_repository,
            fake_message_port, mock_task_manager,
        )

        result = await uc.generate_campaign()

        assert result.successful == 1
        assert result.failed == 1
        assert result.total_contacts == 2

        campaigns = fake_campaign_repository.get_all_campaigns()
        assert campaigns[0].status == CampaignStatus.COMPLETED
