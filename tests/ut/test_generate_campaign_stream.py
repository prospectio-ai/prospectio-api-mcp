"""Unit tests for GenerateCampaignStreamUseCase."""

import json
import pytest
from datetime import datetime
from typing import List

from domain.entities.campaign import CampaignStatus
from domain.entities.company import Company
from domain.entities.contact import Contact
from domain.entities.profile import Profile
from domain.entities.prospect_message import ProspectMessage
from domain.entities.sse_events import SSEEventType
from application.use_cases.generate_campaign_stream import GenerateCampaignStreamUseCase
from tests.doubles.repositories import FakeCampaignRepository, FakeProfileRepository
from tests.doubles.ports import FakeGenerateMessagePort


class TestGenerateCampaignStreamUseCase:
    """Tests for GenerateCampaignStreamUseCase."""

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
    def sample_contacts_with_companies(self) -> List[tuple[Contact, Company]]:
        """Sample contacts with their companies for testing."""
        return [
            (
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
            (
                Contact(
                    id="contact-003",
                    company_id="company-003",
                    name="Carol Williams",
                    email=["carol@startup.com"],
                    title="VP Engineering",
                ),
                Company(
                    id="company-003",
                    name="StartupCo",
                    industry="Fintech",
                    location="Bordeaux, France",
                ),
            ),
        ]

    @pytest.fixture
    def use_case(
        self,
        fake_profile_repository: FakeProfileRepository,
        fake_campaign_repository: FakeCampaignRepository,
        fake_message_port: FakeGenerateMessagePort,
    ) -> GenerateCampaignStreamUseCase:
        """Create use case with fake dependencies."""
        return GenerateCampaignStreamUseCase(
            campaign_name="Test Campaign",
            profile_repository=fake_profile_repository,
            campaign_repository=fake_campaign_repository,
            message_port=fake_message_port,
        )

    @staticmethod
    def parse_sse_event(sse_string: str) -> tuple[str, dict]:
        """Parse an SSE string into event type and data.

        The event type is extracted from the JSON data's 'event' field
        since the SSE event line may contain the enum string representation.
        """
        lines = sse_string.strip().split("\n")
        event_type = ""
        data = {}

        for line in lines:
            if line.startswith("event: "):
                # The event line may contain SSEEventType.X or just the value
                event_type = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
                # The actual event value is in the JSON data
                if "event" in data:
                    event_type = data["event"]

        return event_type, data

    @staticmethod
    async def collect_events(
        use_case: GenerateCampaignStreamUseCase,
    ) -> List[tuple[str, dict]]:
        """Collect all SSE events from the stream."""
        events = []
        async for sse_string in use_case.generate_campaign_stream():
            event_type, data = TestGenerateCampaignStreamUseCase.parse_sse_event(
                sse_string
            )
            events.append((event_type, data))
        return events

    async def test_emits_failed_event_when_profile_not_found(
        self,
        use_case: GenerateCampaignStreamUseCase,
        fake_profile_repository: FakeProfileRepository,
    ):
        """Should emit campaign_failed event when profile does not exist."""
        # Profile repository is empty by default

        events = await self.collect_events(use_case)

        # Should have exactly one event: campaign_failed
        assert len(events) == 1
        event_type, data = events[0]
        assert event_type == "campaign_failed"
        assert "Profile not found" in data["data"]["error"]

    async def test_emits_started_event_when_campaign_begins(
        self,
        use_case: GenerateCampaignStreamUseCase,
        fake_profile_repository: FakeProfileRepository,
        fake_campaign_repository: FakeCampaignRepository,
        sample_profile: Profile,
    ):
        """Should emit campaign_started event with campaign info."""
        fake_profile_repository.set_profile(sample_profile)
        # No contacts - campaign will complete immediately

        events = await self.collect_events(use_case)

        # First event should be campaign_started
        event_type, data = events[0]
        assert event_type == "campaign_started"
        assert "campaign_id" in data["data"]
        assert data["data"]["campaign_name"] == "Test Campaign"

    async def test_emits_completed_event_when_no_contacts(
        self,
        use_case: GenerateCampaignStreamUseCase,
        fake_profile_repository: FakeProfileRepository,
        sample_profile: Profile,
    ):
        """Should emit completed event with zero contacts when none available."""
        fake_profile_repository.set_profile(sample_profile)
        # Campaign repository has no contacts by default

        events = await self.collect_events(use_case)

        # Should have started and completed events
        assert len(events) == 2

        started_type, _ = events[0]
        assert started_type == "campaign_started"

        completed_type, completed_data = events[1]
        assert completed_type == "campaign_completed"
        assert completed_data["data"]["total_contacts"] == 0
        assert completed_data["data"]["successful"] == 0
        assert completed_data["data"]["failed"] == 0
        assert "No new contacts found" in completed_data["data"]["message"]

    async def test_emits_progress_events_for_each_contact(
        self,
        use_case: GenerateCampaignStreamUseCase,
        fake_profile_repository: FakeProfileRepository,
        fake_campaign_repository: FakeCampaignRepository,
        sample_profile: Profile,
        sample_contacts_with_companies: List[tuple[Contact, Company]],
    ):
        """Should emit progress_update event before processing each contact."""
        fake_profile_repository.set_profile(sample_profile)
        fake_campaign_repository.add_contacts_with_companies(
            sample_contacts_with_companies
        )

        events = await self.collect_events(use_case)

        # Filter progress events
        progress_events = [
            (t, d) for t, d in events if t == "progress_update"
        ]

        # Should have 3 progress events (one per contact)
        assert len(progress_events) == 3

        # Verify first progress event
        _, first_progress = progress_events[0]
        assert first_progress["data"]["current"] == 1
        assert first_progress["data"]["total"] == 3
        assert first_progress["data"]["percentage"] == pytest.approx(33.3, rel=0.1)
        assert first_progress["data"]["current_contact_name"] == "Alice Johnson"

        # Verify last progress event
        _, last_progress = progress_events[2]
        assert last_progress["data"]["current"] == 3
        assert last_progress["data"]["percentage"] == 100.0
        assert last_progress["data"]["current_contact_name"] == "Carol Williams"

    async def test_emits_message_generated_for_successful_messages(
        self,
        use_case: GenerateCampaignStreamUseCase,
        fake_profile_repository: FakeProfileRepository,
        fake_campaign_repository: FakeCampaignRepository,
        fake_message_port: FakeGenerateMessagePort,
        sample_profile: Profile,
        sample_contacts_with_companies: List[tuple[Contact, Company]],
    ):
        """Should emit message_generated event for each successfully generated message."""
        fake_profile_repository.set_profile(sample_profile)
        fake_campaign_repository.add_contacts_with_companies(
            sample_contacts_with_companies
        )
        fake_message_port.set_default_message(
            ProspectMessage(
                subject="Custom Subject",
                message="Custom message body",
            )
        )

        events = await self.collect_events(use_case)

        # Filter message_generated events
        message_events = [
            (t, d) for t, d in events if t == "message_generated"
        ]

        # Should have 3 message events (one per contact)
        assert len(message_events) == 3

        # Verify first message event
        _, first_msg = message_events[0]
        assert first_msg["data"]["contact_name"] == "Alice Johnson"
        assert first_msg["data"]["company_name"] == "TechCorp"
        assert first_msg["data"]["subject"] == "Custom Subject"
        assert first_msg["data"]["status"] == "success"

    async def test_handles_message_generation_failures(
        self,
        use_case: GenerateCampaignStreamUseCase,
        fake_profile_repository: FakeProfileRepository,
        fake_campaign_repository: FakeCampaignRepository,
        fake_message_port: FakeGenerateMessagePort,
        sample_profile: Profile,
        sample_contacts_with_companies: List[tuple[Contact, Company]],
    ):
        """Should emit message_generated with failed status on generation error."""
        fake_profile_repository.set_profile(sample_profile)
        fake_campaign_repository.add_contacts_with_companies(
            sample_contacts_with_companies
        )
        # Make second contact fail
        fake_message_port.set_should_fail_for("contact-002")

        events = await self.collect_events(use_case)

        # Filter message_generated events
        message_events = [
            (t, d) for t, d in events if t == "message_generated"
        ]

        assert len(message_events) == 3

        # Check the failed message (second contact)
        _, failed_msg = message_events[1]
        assert failed_msg["data"]["contact_name"] == "Bob Smith"
        assert failed_msg["data"]["status"] == "failed"
        assert "error" in failed_msg["data"]

        # Verify final stats
        completed_events = [
            (t, d) for t, d in events if t == "campaign_completed"
        ]
        assert len(completed_events) == 1
        _, completed = completed_events[0]
        assert completed["data"]["successful"] == 2
        assert completed["data"]["failed"] == 1

    async def test_persists_campaign_and_messages(
        self,
        use_case: GenerateCampaignStreamUseCase,
        fake_profile_repository: FakeProfileRepository,
        fake_campaign_repository: FakeCampaignRepository,
        sample_profile: Profile,
        sample_contacts_with_companies: List[tuple[Contact, Company]],
    ):
        """Should persist campaign and all generated messages."""
        fake_profile_repository.set_profile(sample_profile)
        fake_campaign_repository.add_contacts_with_companies(
            sample_contacts_with_companies
        )

        await self.collect_events(use_case)

        # Verify campaign was created and updated
        campaigns = fake_campaign_repository.get_all_campaigns()
        assert len(campaigns) == 1
        campaign = campaigns[0]
        assert campaign.name == "Test Campaign"
        assert campaign.status == CampaignStatus.COMPLETED
        assert campaign.total_contacts == 3
        assert campaign.successful == 3
        assert campaign.failed == 0
        assert campaign.completed_at is not None

        # Verify messages were saved
        messages = fake_campaign_repository.get_all_messages()
        assert len(messages) == 3
        assert all(m.campaign_id == campaign.id for m in messages)

    async def test_marks_campaign_failed_when_all_messages_fail(
        self,
        use_case: GenerateCampaignStreamUseCase,
        fake_profile_repository: FakeProfileRepository,
        fake_campaign_repository: FakeCampaignRepository,
        fake_message_port: FakeGenerateMessagePort,
        sample_profile: Profile,
        sample_contacts_with_companies: List[tuple[Contact, Company]],
    ):
        """Should mark campaign as FAILED when all message generations fail."""
        fake_profile_repository.set_profile(sample_profile)
        fake_campaign_repository.add_contacts_with_companies(
            sample_contacts_with_companies
        )
        # Make all contacts fail
        for contact, _ in sample_contacts_with_companies:
            fake_message_port.set_should_fail_for(contact.id or "")

        await self.collect_events(use_case)

        # Verify campaign status is FAILED
        campaigns = fake_campaign_repository.get_all_campaigns()
        assert len(campaigns) == 1
        assert campaigns[0].status == CampaignStatus.FAILED
        assert campaigns[0].failed == 3
        assert campaigns[0].successful == 0

    async def test_message_port_called_for_each_contact(
        self,
        use_case: GenerateCampaignStreamUseCase,
        fake_profile_repository: FakeProfileRepository,
        fake_campaign_repository: FakeCampaignRepository,
        fake_message_port: FakeGenerateMessagePort,
        sample_profile: Profile,
        sample_contacts_with_companies: List[tuple[Contact, Company]],
    ):
        """Should call message port exactly once per contact."""
        fake_profile_repository.set_profile(sample_profile)
        fake_campaign_repository.add_contacts_with_companies(
            sample_contacts_with_companies
        )

        await self.collect_events(use_case)

        assert fake_message_port.get_call_count() == 3

    async def test_event_order_is_correct(
        self,
        use_case: GenerateCampaignStreamUseCase,
        fake_profile_repository: FakeProfileRepository,
        fake_campaign_repository: FakeCampaignRepository,
        sample_profile: Profile,
        sample_contacts_with_companies: List[tuple[Contact, Company]],
    ):
        """Should emit events in correct order: started, (progress, message)*, completed."""
        fake_profile_repository.set_profile(sample_profile)
        fake_campaign_repository.add_contacts_with_companies(
            sample_contacts_with_companies[:1]  # Use only one contact
        )

        events = await self.collect_events(use_case)
        event_types = [t for t, _ in events]

        # Expected order for 1 contact
        assert event_types == [
            "campaign_started",
            "progress_update",
            "message_generated",
            "campaign_completed",
        ]

    async def test_includes_contact_emails_in_message_events(
        self,
        use_case: GenerateCampaignStreamUseCase,
        fake_profile_repository: FakeProfileRepository,
        fake_campaign_repository: FakeCampaignRepository,
        sample_profile: Profile,
    ):
        """Should include contact email addresses in message_generated events."""
        fake_profile_repository.set_profile(sample_profile)
        fake_campaign_repository.add_contacts_with_companies(
            [
                (
                    Contact(
                        id="contact-multi-email",
                        name="Multi Email Contact",
                        email=["primary@example.com", "secondary@example.com"],
                    ),
                    Company(id="company-001", name="Test Co"),
                ),
            ]
        )

        events = await self.collect_events(use_case)

        message_events = [
            (t, d) for t, d in events if t == "message_generated"
        ]
        assert len(message_events) == 1

        _, msg_data = message_events[0]
        assert msg_data["data"]["contact_email"] == [
            "primary@example.com",
            "secondary@example.com",
        ]


class TestGenerateCampaignStreamUseCaseWithCustomMessages:
    """Tests for use case with custom message configurations."""

    @pytest.fixture
    def fake_profile_repository(self) -> FakeProfileRepository:
        return FakeProfileRepository()

    @pytest.fixture
    def fake_campaign_repository(self) -> FakeCampaignRepository:
        return FakeCampaignRepository()

    @pytest.fixture
    def fake_message_port(self) -> FakeGenerateMessagePort:
        return FakeGenerateMessagePort()

    @pytest.fixture
    def sample_profile(self) -> Profile:
        return Profile(
            job_title="Tech Consultant",
            location="Remote",
            bio="Helping companies scale.",
        )

    async def test_uses_contact_specific_messages(
        self,
        fake_profile_repository: FakeProfileRepository,
        fake_campaign_repository: FakeCampaignRepository,
        fake_message_port: FakeGenerateMessagePort,
        sample_profile: Profile,
    ):
        """Should use contact-specific messages when configured."""
        fake_profile_repository.set_profile(sample_profile)

        # Configure specific messages for each contact
        fake_message_port.set_message_for_contact(
            "contact-vip",
            ProspectMessage(
                subject="VIP Subject Line",
                message="VIP personalized message",
            ),
        )

        fake_campaign_repository.add_contacts_with_companies(
            [
                (
                    Contact(id="contact-vip", name="VIP Contact"),
                    Company(id="company-001", name="VIP Company"),
                ),
            ]
        )

        use_case = GenerateCampaignStreamUseCase(
            campaign_name="VIP Campaign",
            profile_repository=fake_profile_repository,
            campaign_repository=fake_campaign_repository,
            message_port=fake_message_port,
        )

        events = []
        async for sse_string in use_case.generate_campaign_stream():
            event_type, data = TestGenerateCampaignStreamUseCase.parse_sse_event(
                sse_string
            )
            events.append((event_type, data))

        message_events = [
            (t, d) for t, d in events if t == "message_generated"
        ]
        assert len(message_events) == 1

        _, msg_data = message_events[0]
        assert msg_data["data"]["subject"] == "VIP Subject Line"
        assert msg_data["data"]["message"] == "VIP personalized message"
