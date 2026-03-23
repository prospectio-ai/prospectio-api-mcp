"""Unit tests for RetryCampaignStreamUseCase."""

import json
import pytest
from typing import List

from domain.entities.campaign import Campaign, CampaignStatus
from domain.entities.campaign_result import CampaignMessage
from domain.entities.company import Company
from domain.entities.contact import Contact
from domain.entities.profile import Profile
from domain.entities.prospect_message import ProspectMessage
from application.use_cases.retry_campaign_stream import RetryCampaignStreamUseCase
from tests.doubles.repositories import FakeCampaignRepository, FakeProfileRepository
from tests.doubles.ports import FakeGenerateMessagePort


class TestRetryCampaignStreamUseCase:
    """Tests for RetryCampaignStreamUseCase."""

    CAMPAIGN_ID = "campaign-retry-001"

    @pytest.fixture
    def fake_profile_repository(self) -> FakeProfileRepository:
        """Fresh fake profile repository."""
        return FakeProfileRepository()

    @pytest.fixture
    def fake_campaign_repository(self) -> FakeCampaignRepository:
        """Fresh fake campaign repository."""
        return FakeCampaignRepository()

    @pytest.fixture
    def fake_message_port(self) -> FakeGenerateMessagePort:
        """Fresh fake message port."""
        return FakeGenerateMessagePort()

    @pytest.fixture
    def sample_profile(self) -> Profile:
        """Sample user profile for testing."""
        return Profile(
            job_title="Senior Python Developer",
            location="Paris, France",
            bio="Experienced developer specializing in FastAPI and clean architecture.",
            work_experience=[],
            technos=["Python", "FastAPI", "PostgreSQL"],
        )

    @pytest.fixture
    def completed_campaign(self, fake_campaign_repository: FakeCampaignRepository) -> Campaign:
        """A completed campaign with some successful and failed messages."""
        campaign = Campaign(
            id=self.CAMPAIGN_ID,
            name="Test Campaign",
            status=CampaignStatus.COMPLETED,
            total_contacts=3,
            successful=1,
            failed=2,
        )
        # Manually insert into fake repo
        fake_campaign_repository._campaigns[campaign.id] = campaign
        return campaign

    @pytest.fixture
    def failed_messages_with_contacts(self) -> List[tuple[CampaignMessage, Contact, Company]]:
        """Failed messages with their contacts and companies for retry."""
        return [
            (
                CampaignMessage(
                    id="msg-fail-001",
                    campaign_id="campaign-retry-001",
                    contact_id="contact-001",
                    contact_name="Alice Johnson",
                    contact_email=["alice@techcorp.com"],
                    company_name="TechCorp",
                    subject="",
                    message="",
                    status="failed",
                    error="LLM timeout",
                ),
                Contact(
                    id="contact-001",
                    company_id="company-001",
                    name="Alice Johnson",
                    email=["alice@techcorp.com"],
                    title="CTO",
                ),
                Company(
                    id="company-001",
                    name="TechCorp",
                    industry="Technology",
                    location="Paris, France",
                ),
            ),
            (
                CampaignMessage(
                    id="msg-fail-002",
                    campaign_id="campaign-retry-001",
                    contact_id="contact-002",
                    contact_name="Bob Smith",
                    contact_email=["bob@innovate.io"],
                    company_name="Innovate.io",
                    subject="",
                    message="",
                    status="failed",
                    error="Parsing failure",
                ),
                Contact(
                    id="contact-002",
                    company_id="company-002",
                    name="Bob Smith",
                    email=["bob@innovate.io"],
                    title="Engineering Manager",
                ),
                Company(
                    id="company-002",
                    name="Innovate.io",
                    industry="Software",
                    location="Lyon, France",
                ),
            ),
        ]

    @staticmethod
    def parse_sse_event(sse_string: str) -> tuple[str, dict]:
        """Parse an SSE string into event type and data."""
        lines = sse_string.strip().split("\n")
        event_type = ""
        data = {}

        for line in lines:
            if line.startswith("event: "):
                event_type = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
                if "event" in data:
                    event_type = data["event"]

        return event_type, data

    @staticmethod
    async def collect_events(
        use_case: RetryCampaignStreamUseCase,
    ) -> List[tuple[str, dict]]:
        """Collect all SSE events from the retry stream."""
        events = []
        async for sse_string in use_case.retry_campaign_stream():
            event_type, data = TestRetryCampaignStreamUseCase.parse_sse_event(
                sse_string
            )
            events.append((event_type, data))
        return events

    def _make_use_case(
        self,
        fake_profile_repository: FakeProfileRepository,
        fake_campaign_repository: FakeCampaignRepository,
        fake_message_port: FakeGenerateMessagePort,
        campaign_id: str = CAMPAIGN_ID,
    ) -> RetryCampaignStreamUseCase:
        """Create a RetryCampaignStreamUseCase with dependencies."""
        return RetryCampaignStreamUseCase(
            campaign_id=campaign_id,
            profile_repository=fake_profile_repository,
            campaign_repository=fake_campaign_repository,
            message_port=fake_message_port,
        )

    async def test_happy_path_retries_failed_messages(
        self,
        fake_profile_repository: FakeProfileRepository,
        fake_campaign_repository: FakeCampaignRepository,
        fake_message_port: FakeGenerateMessagePort,
        sample_profile: Profile,
        completed_campaign: Campaign,
        failed_messages_with_contacts: List[tuple[CampaignMessage, Contact, Company]],
    ):
        """Should retry all failed messages and emit correct events."""
        fake_profile_repository.set_profile(sample_profile)
        fake_campaign_repository.add_failed_messages_with_contacts(
            self.CAMPAIGN_ID, failed_messages_with_contacts
        )

        use_case = self._make_use_case(
            fake_profile_repository, fake_campaign_repository, fake_message_port
        )
        events = await self.collect_events(use_case)

        event_types = [t for t, _ in events]

        # Expected: started, (progress, message) * 2, completed
        assert event_types == [
            "campaign_started",
            "progress_update",
            "message_generated",
            "progress_update",
            "message_generated",
            "campaign_completed",
        ]

        # Verify message events are successful
        message_events = [(t, d) for t, d in events if t == "message_generated"]
        assert len(message_events) == 2
        for _, msg_data in message_events:
            assert msg_data["data"]["status"] == "success"

        # Verify completion counters
        completed_events = [(t, d) for t, d in events if t == "campaign_completed"]
        assert len(completed_events) == 1
        _, completed_data = completed_events[0]
        assert completed_data["data"]["successful"] == 2
        assert completed_data["data"]["failed"] == 0

    async def test_no_failed_messages_emits_completion_immediately(
        self,
        fake_profile_repository: FakeProfileRepository,
        fake_campaign_repository: FakeCampaignRepository,
        fake_message_port: FakeGenerateMessagePort,
        sample_profile: Profile,
        completed_campaign: Campaign,
    ):
        """Should emit completion event with zero retried when no failed messages exist."""
        fake_profile_repository.set_profile(sample_profile)
        # No failed messages configured

        use_case = self._make_use_case(
            fake_profile_repository, fake_campaign_repository, fake_message_port
        )
        events = await self.collect_events(use_case)

        assert len(events) == 1
        event_type, data = events[0]
        assert event_type == "campaign_completed"
        assert data["data"]["total_contacts"] == 0
        assert "No failed messages to retry" in data["data"]["message"]

    async def test_campaign_not_found_emits_error(
        self,
        fake_profile_repository: FakeProfileRepository,
        fake_campaign_repository: FakeCampaignRepository,
        fake_message_port: FakeGenerateMessagePort,
        sample_profile: Profile,
    ):
        """Should emit campaign_failed event when campaign does not exist."""
        fake_profile_repository.set_profile(sample_profile)

        use_case = self._make_use_case(
            fake_profile_repository,
            fake_campaign_repository,
            fake_message_port,
            campaign_id="nonexistent-id",
        )
        events = await self.collect_events(use_case)

        assert len(events) == 1
        event_type, data = events[0]
        assert event_type == "campaign_failed"
        assert "Campaign not found" in data["data"]["error"]

    async def test_campaign_in_progress_emits_error(
        self,
        fake_profile_repository: FakeProfileRepository,
        fake_campaign_repository: FakeCampaignRepository,
        fake_message_port: FakeGenerateMessagePort,
        sample_profile: Profile,
    ):
        """Should emit campaign_failed event when campaign is IN_PROGRESS."""
        fake_profile_repository.set_profile(sample_profile)
        in_progress_campaign = Campaign(
            id="campaign-in-progress",
            name="Active Campaign",
            status=CampaignStatus.IN_PROGRESS,
            total_contacts=5,
        )
        fake_campaign_repository._campaigns[in_progress_campaign.id] = in_progress_campaign

        use_case = self._make_use_case(
            fake_profile_repository,
            fake_campaign_repository,
            fake_message_port,
            campaign_id="campaign-in-progress",
        )
        events = await self.collect_events(use_case)

        assert len(events) == 1
        event_type, data = events[0]
        assert event_type == "campaign_failed"
        assert "Cannot retry campaign with status" in data["data"]["error"]

    async def test_partial_failures_updates_counters_correctly(
        self,
        fake_profile_repository: FakeProfileRepository,
        fake_campaign_repository: FakeCampaignRepository,
        fake_message_port: FakeGenerateMessagePort,
        sample_profile: Profile,
        completed_campaign: Campaign,
        failed_messages_with_contacts: List[tuple[CampaignMessage, Contact, Company]],
    ):
        """Should correctly update counters when some retries fail again."""
        fake_profile_repository.set_profile(sample_profile)
        fake_campaign_repository.add_failed_messages_with_contacts(
            self.CAMPAIGN_ID, failed_messages_with_contacts
        )
        # Make second contact fail again
        fake_message_port.set_should_fail_for("contact-002")

        use_case = self._make_use_case(
            fake_profile_repository, fake_campaign_repository, fake_message_port
        )
        events = await self.collect_events(use_case)

        # Verify message statuses
        message_events = [(t, d) for t, d in events if t == "message_generated"]
        assert len(message_events) == 2
        _, first_msg = message_events[0]
        assert first_msg["data"]["status"] == "success"
        _, second_msg = message_events[1]
        assert second_msg["data"]["status"] == "failed"

        # Verify completion counters
        completed_events = [(t, d) for t, d in events if t == "campaign_completed"]
        _, completed_data = completed_events[0]
        assert completed_data["data"]["successful"] == 1
        assert completed_data["data"]["failed"] == 1

        # Verify campaign state: previous_successful (1) + new_successful (1) = 2
        campaign = fake_campaign_repository._campaigns[self.CAMPAIGN_ID]
        assert campaign.status == CampaignStatus.COMPLETED
        assert campaign.successful == 2  # 1 previous + 1 new
        assert campaign.failed == 1
        assert campaign.completed_at is not None

    async def test_no_profile_emits_error(
        self,
        fake_profile_repository: FakeProfileRepository,
        fake_campaign_repository: FakeCampaignRepository,
        fake_message_port: FakeGenerateMessagePort,
        completed_campaign: Campaign,
    ):
        """Should emit campaign_failed event when profile does not exist."""
        # Profile repository is empty by default

        use_case = self._make_use_case(
            fake_profile_repository, fake_campaign_repository, fake_message_port
        )
        events = await self.collect_events(use_case)

        assert len(events) == 1
        event_type, data = events[0]
        assert event_type == "campaign_failed"
        assert "Profile not found" in data["data"]["error"]

    async def test_old_messages_are_deleted_before_regeneration(
        self,
        fake_profile_repository: FakeProfileRepository,
        fake_campaign_repository: FakeCampaignRepository,
        fake_message_port: FakeGenerateMessagePort,
        sample_profile: Profile,
        completed_campaign: Campaign,
        failed_messages_with_contacts: List[tuple[CampaignMessage, Contact, Company]],
    ):
        """Should delete old failed messages before generating new ones."""
        fake_profile_repository.set_profile(sample_profile)
        fake_campaign_repository.add_failed_messages_with_contacts(
            self.CAMPAIGN_ID, failed_messages_with_contacts
        )
        # Pre-populate messages in the repository
        for msg, _, _ in failed_messages_with_contacts:
            fake_campaign_repository._messages[msg.id] = msg

        use_case = self._make_use_case(
            fake_profile_repository, fake_campaign_repository, fake_message_port
        )
        await self.collect_events(use_case)

        # Old message IDs should no longer exist
        assert "msg-fail-001" not in fake_campaign_repository._messages
        assert "msg-fail-002" not in fake_campaign_repository._messages

        # New messages should exist (2 new ones)
        all_messages = fake_campaign_repository.get_all_messages()
        assert len(all_messages) == 2
        assert all(m.status == "success" for m in all_messages)

    async def test_all_retries_fail_marks_campaign_failed(
        self,
        fake_profile_repository: FakeProfileRepository,
        fake_campaign_repository: FakeCampaignRepository,
        fake_message_port: FakeGenerateMessagePort,
        sample_profile: Profile,
        completed_campaign: Campaign,
        failed_messages_with_contacts: List[tuple[CampaignMessage, Contact, Company]],
    ):
        """Should mark campaign as FAILED when all retries fail again."""
        fake_profile_repository.set_profile(sample_profile)
        fake_campaign_repository.add_failed_messages_with_contacts(
            self.CAMPAIGN_ID, failed_messages_with_contacts
        )
        # Make all contacts fail
        fake_message_port.set_should_fail_for("contact-001")
        fake_message_port.set_should_fail_for("contact-002")

        use_case = self._make_use_case(
            fake_profile_repository, fake_campaign_repository, fake_message_port
        )
        await self.collect_events(use_case)

        campaign = fake_campaign_repository._campaigns[self.CAMPAIGN_ID]
        assert campaign.status == CampaignStatus.FAILED
        assert campaign.failed == 2
        # Previous successful stays
        assert campaign.successful == 1

    async def test_retry_on_failed_campaign_status(
        self,
        fake_profile_repository: FakeProfileRepository,
        fake_campaign_repository: FakeCampaignRepository,
        fake_message_port: FakeGenerateMessagePort,
        sample_profile: Profile,
        failed_messages_with_contacts: List[tuple[CampaignMessage, Contact, Company]],
    ):
        """Should allow retry on campaigns with FAILED status."""
        fake_profile_repository.set_profile(sample_profile)
        failed_campaign = Campaign(
            id="campaign-failed-001",
            name="Failed Campaign",
            status=CampaignStatus.FAILED,
            total_contacts=2,
            successful=0,
            failed=2,
        )
        fake_campaign_repository._campaigns[failed_campaign.id] = failed_campaign
        fake_campaign_repository.add_failed_messages_with_contacts(
            "campaign-failed-001", failed_messages_with_contacts
        )

        use_case = self._make_use_case(
            fake_profile_repository,
            fake_campaign_repository,
            fake_message_port,
            campaign_id="campaign-failed-001",
        )
        events = await self.collect_events(use_case)

        event_types = [t for t, _ in events]
        assert "campaign_started" in event_types
        assert "campaign_completed" in event_types
