"""Unit tests for SSE event entities and formatting."""

import json
import pytest
from datetime import datetime

from domain.entities.sse_events import (
    SSEEvent,
    SSEEventType,
    CampaignProgressData,
    MessageGeneratedData,
)


class TestSSEEventType:
    """Tests for SSEEventType enum."""

    def test_event_types_have_correct_values(self):
        """Should have all expected event types with correct string values."""
        assert SSEEventType.CAMPAIGN_STARTED == "campaign_started"
        assert SSEEventType.MESSAGE_GENERATED == "message_generated"
        assert SSEEventType.PROGRESS_UPDATE == "progress_update"
        assert SSEEventType.CAMPAIGN_COMPLETED == "campaign_completed"
        assert SSEEventType.CAMPAIGN_FAILED == "campaign_failed"
        assert SSEEventType.HEARTBEAT == "heartbeat"

    def test_event_types_count(self):
        """Should have exactly 6 event types."""
        assert len(SSEEventType) == 6


class TestSSEEvent:
    """Tests for SSEEvent model and formatting."""

    @pytest.fixture
    def sample_timestamp(self) -> datetime:
        """Fixed timestamp for testing."""
        return datetime(2025, 1, 10, 12, 0, 0)

    def test_creates_event_with_required_fields(self, sample_timestamp: datetime):
        """Should create SSE event with event type and data."""
        event = SSEEvent(
            event=SSEEventType.CAMPAIGN_STARTED,
            data={"campaign_id": "camp-123", "campaign_name": "Test Campaign"},
            timestamp=sample_timestamp,
        )

        assert event.event == SSEEventType.CAMPAIGN_STARTED
        assert event.data["campaign_id"] == "camp-123"
        assert event.data["campaign_name"] == "Test Campaign"
        assert event.timestamp == sample_timestamp

    def test_creates_event_with_default_timestamp(self):
        """Should auto-generate timestamp if not provided."""
        event = SSEEvent(
            event=SSEEventType.HEARTBEAT,
            data={},
        )

        assert event.timestamp is not None
        assert isinstance(event.timestamp, datetime)

    def test_to_sse_format_produces_valid_sse_string(self, sample_timestamp: datetime):
        """Should format event correctly for SSE protocol."""
        event = SSEEvent(
            event=SSEEventType.CAMPAIGN_STARTED,
            data={"campaign_id": "camp-123"},
            timestamp=sample_timestamp,
        )

        sse_output = event.to_sse_format()

        # Check SSE format structure - event type appears in output
        assert "event: " in sse_output
        assert "CAMPAIGN_STARTED" in sse_output or "campaign_started" in sse_output
        assert "data: " in sse_output
        assert sse_output.endswith("\n\n")

    def test_to_sse_format_contains_valid_json_data(self, sample_timestamp: datetime):
        """Should include valid JSON in the data field."""
        event = SSEEvent(
            event=SSEEventType.MESSAGE_GENERATED,
            data={"message_id": "msg-456", "status": "success"},
            timestamp=sample_timestamp,
        )

        sse_output = event.to_sse_format()

        # Extract the data line
        lines = sse_output.strip().split("\n")
        data_line = next(line for line in lines if line.startswith("data: "))
        json_str = data_line[6:]  # Remove "data: " prefix

        # Verify it's valid JSON
        parsed = json.loads(json_str)
        assert parsed["event"] == "message_generated"
        assert parsed["data"]["message_id"] == "msg-456"
        assert parsed["data"]["status"] == "success"

    def test_to_sse_format_handles_nested_data(self, sample_timestamp: datetime):
        """Should handle complex nested data structures."""
        event = SSEEvent(
            event=SSEEventType.PROGRESS_UPDATE,
            data={
                "campaign_id": "camp-123",
                "current": 5,
                "total": 10,
                "percentage": 50.0,
                "nested": {"key": "value"},
            },
            timestamp=sample_timestamp,
        )

        sse_output = event.to_sse_format()
        lines = sse_output.strip().split("\n")
        data_line = next(line for line in lines if line.startswith("data: "))
        json_str = data_line[6:]

        parsed = json.loads(json_str)
        assert parsed["data"]["nested"]["key"] == "value"


class TestCampaignProgressData:
    """Tests for CampaignProgressData model."""

    def test_creates_progress_data_with_all_fields(self):
        """Should create progress data with all required and optional fields."""
        progress = CampaignProgressData(
            campaign_id="camp-123",
            current=5,
            total=10,
            percentage=50.0,
            current_contact_name="John Doe",
        )

        assert progress.campaign_id == "camp-123"
        assert progress.current == 5
        assert progress.total == 10
        assert progress.percentage == 50.0
        assert progress.current_contact_name == "John Doe"

    def test_creates_progress_data_without_optional_fields(self):
        """Should create progress data without optional contact name."""
        progress = CampaignProgressData(
            campaign_id="camp-123",
            current=1,
            total=5,
            percentage=20.0,
        )

        assert progress.current_contact_name is None

    def test_model_dump_produces_dict(self):
        """Should convert to dict for JSON serialization."""
        progress = CampaignProgressData(
            campaign_id="camp-123",
            current=3,
            total=10,
            percentage=30.0,
            current_contact_name="Jane Smith",
        )

        data = progress.model_dump()

        assert isinstance(data, dict)
        assert data["campaign_id"] == "camp-123"
        assert data["current"] == 3
        assert data["total"] == 10


class TestMessageGeneratedData:
    """Tests for MessageGeneratedData model."""

    @pytest.fixture
    def sample_created_at(self) -> datetime:
        """Fixed timestamp for testing."""
        return datetime(2025, 1, 10, 14, 30, 0)

    def test_creates_message_data_with_all_fields(self, sample_created_at: datetime):
        """Should create message data with all fields."""
        message_data = MessageGeneratedData(
            campaign_id="camp-123",
            message_id="msg-456",
            contact_id="contact-789",
            contact_name="John Doe",
            contact_email=["john@example.com", "john.doe@company.com"],
            company_name="Acme Corp",
            subject="Exciting Opportunity",
            message="Hello John, I wanted to reach out...",
            status="success",
            created_at=sample_created_at,
        )

        assert message_data.campaign_id == "camp-123"
        assert message_data.message_id == "msg-456"
        assert message_data.contact_id == "contact-789"
        assert message_data.contact_name == "John Doe"
        assert message_data.contact_email == ["john@example.com", "john.doe@company.com"]
        assert message_data.company_name == "Acme Corp"
        assert message_data.subject == "Exciting Opportunity"
        assert message_data.status == "success"

    def test_creates_message_data_with_optional_fields_none(
        self, sample_created_at: datetime
    ):
        """Should create message data with optional fields as None."""
        message_data = MessageGeneratedData(
            campaign_id="camp-123",
            message_id="msg-456",
            contact_id="contact-789",
            contact_name=None,
            contact_email=None,
            company_name=None,
            subject="Hello",
            message="Message body",
            status="success",
            created_at=sample_created_at,
        )

        assert message_data.contact_name is None
        assert message_data.contact_email is None
        assert message_data.company_name is None

    def test_model_dump_serializes_datetime(self, sample_created_at: datetime):
        """Should properly serialize datetime in model_dump."""
        message_data = MessageGeneratedData(
            campaign_id="camp-123",
            message_id="msg-456",
            contact_id="contact-789",
            contact_name="Test",
            contact_email=["test@test.com"],
            company_name="Test Co",
            subject="Subject",
            message="Message",
            status="success",
            created_at=sample_created_at,
        )

        data = message_data.model_dump()

        assert isinstance(data, dict)
        assert data["created_at"] == sample_created_at


class TestSSEEventIntegration:
    """Integration tests for SSE event creation with real data models."""

    def test_progress_event_with_progress_data(self):
        """Should create a complete progress event using CampaignProgressData."""
        progress_data = CampaignProgressData(
            campaign_id="camp-123",
            current=3,
            total=10,
            percentage=30.0,
            current_contact_name="Alice Johnson",
        )

        event = SSEEvent(
            event=SSEEventType.PROGRESS_UPDATE,
            data=progress_data.model_dump(),
        )

        sse_output = event.to_sse_format()

        assert "PROGRESS_UPDATE" in sse_output or "progress_update" in sse_output
        assert "camp-123" in sse_output
        assert "Alice Johnson" in sse_output

    def test_message_generated_event_with_message_data(self):
        """Should create a complete message generated event."""
        from datetime import timezone
        message_data = MessageGeneratedData(
            campaign_id="camp-123",
            message_id="msg-001",
            contact_id="contact-001",
            contact_name="Bob Smith",
            contact_email=["bob@company.com"],
            company_name="Smith Industries",
            subject="Partnership Opportunity",
            message="Dear Bob, I noticed your work...",
            status="success",
            created_at=datetime.now(timezone.utc),
        )

        event = SSEEvent(
            event=SSEEventType.MESSAGE_GENERATED,
            data=message_data.model_dump(),
        )

        sse_output = event.to_sse_format()

        assert "MESSAGE_GENERATED" in sse_output or "message_generated" in sse_output
        assert "Bob Smith" in sse_output
        assert "Partnership Opportunity" in sse_output

    def test_campaign_completed_event(self):
        """Should create a campaign completed event with summary data."""
        event = SSEEvent(
            event=SSEEventType.CAMPAIGN_COMPLETED,
            data={
                "campaign_id": "camp-123",
                "total_contacts": 50,
                "successful": 45,
                "failed": 5,
                "message": "Campaign completed: 45 successful, 5 failed",
            },
        )

        sse_output = event.to_sse_format()

        assert "CAMPAIGN_COMPLETED" in sse_output or "campaign_completed" in sse_output

        # Parse and verify the JSON data
        lines = sse_output.strip().split("\n")
        data_line = next(line for line in lines if line.startswith("data: "))
        parsed = json.loads(data_line[6:])

        assert parsed["data"]["total_contacts"] == 50
        assert parsed["data"]["successful"] == 45
        assert parsed["data"]["failed"] == 5

    def test_campaign_failed_event(self):
        """Should create a campaign failed event with error message."""
        event = SSEEvent(
            event=SSEEventType.CAMPAIGN_FAILED,
            data={"error": "Profile not found. Please create a profile first."},
        )

        sse_output = event.to_sse_format()

        assert "CAMPAIGN_FAILED" in sse_output or "campaign_failed" in sse_output
        assert "Profile not found" in sse_output
