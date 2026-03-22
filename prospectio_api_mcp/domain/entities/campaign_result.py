from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class CampaignMessage(BaseModel):
    """
    Represents a generated message for a single contact in a campaign.
    """
    id: Optional[str] = Field(None, description="Unique identifier for the message")
    campaign_id: Optional[str] = Field(None, description="ID of the campaign this message belongs to")
    contact_id: str = Field(..., description="ID of the contact")
    contact_name: Optional[str] = Field(None, description="Name of the contact")
    contact_email: Optional[List[str]] = Field(None, description="Email addresses")
    company_name: Optional[str] = Field(None, description="Company name")
    subject: str = Field(..., description="Generated subject line")
    message: str = Field(..., description="Generated message body")
    status: str = Field(default="success", description="Message generation status")
    error: Optional[str] = Field(None, description="Error message if failed")
    created_at: Optional[datetime] = Field(None, description="Timestamp when message was created")


class CampaignResult(BaseModel):
    """
    Represents the result of a campaign generation containing all generated messages.
    """
    total_contacts: int = Field(..., description="Total number of contacts processed")
    successful: int = Field(..., description="Number of successfully generated messages")
    failed: int = Field(..., description="Number of failed message generations")
    messages: List[CampaignMessage] = Field(default_factory=list, description="List of generated campaign messages")
