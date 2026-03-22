from typing import List, Optional
from enum import StrEnum
from datetime import datetime
from pydantic import BaseModel, Field


class CampaignStatus(StrEnum):
    """Enum for campaign status values."""
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Campaign(BaseModel):
    """
    Represents a prospecting campaign containing generated messages for contacts.
    """
    id: Optional[str] = Field(None, description="Unique identifier for the campaign")
    name: str = Field(..., description="Name of the campaign")
    description: Optional[str] = Field(None, description="Description of the campaign")
    status: CampaignStatus = Field(
        default=CampaignStatus.DRAFT,
        description="Current status of the campaign"
    )
    created_at: Optional[datetime] = Field(None, description="Timestamp when campaign was created")
    updated_at: Optional[datetime] = Field(None, description="Timestamp when campaign was last updated")
    completed_at: Optional[datetime] = Field(None, description="Timestamp when campaign was completed")
    total_contacts: int = Field(default=0, description="Total number of contacts in the campaign")
    successful: int = Field(default=0, description="Number of successfully generated messages")
    failed: int = Field(default=0, description="Number of failed message generations")


class CampaignEntity(BaseModel):
    """
    DTO for a list of campaigns with pagination.
    """
    campaigns: List[Campaign] = Field(..., description="List of campaigns")
    pages: Optional[int] = Field(None, description="Total number of pages available")
