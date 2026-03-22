from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field
import datetime
import json


class SSEEventType(str, Enum):
    """Event types for Server-Sent Events stream."""

    CAMPAIGN_STARTED = "campaign_started"
    MESSAGE_GENERATED = "message_generated"
    PROGRESS_UPDATE = "progress_update"
    CAMPAIGN_COMPLETED = "campaign_completed"
    CAMPAIGN_FAILED = "campaign_failed"
    HEARTBEAT = "heartbeat"


class SSEEvent(BaseModel):
    """Base model for SSE events."""

    event: SSEEventType
    data: Any
    timestamp: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.UTC))

    def to_sse_format(self) -> str:
        """Format event for SSE protocol."""
        data_json = json.dumps(self.model_dump(), default=str)
        return f"event: {self.event.value}\ndata: {data_json}\n\n"


class CampaignProgressData(BaseModel):
    """Progress data for campaign generation."""

    campaign_id: str
    current: int
    total: int
    percentage: float
    current_contact_name: Optional[str] = None


class MessageGeneratedData(BaseModel):
    """Data for a newly generated message."""

    campaign_id: str
    message_id: str
    contact_id: str
    contact_name: Optional[str]
    contact_email: Optional[list[str]]
    company_name: Optional[str]
    subject: str
    message: str
    status: str
    error: Optional[str] = None
    created_at: datetime.datetime
