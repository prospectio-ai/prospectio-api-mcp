from typing import Optional
from pydantic import BaseModel, Field


class CreateCampaignRequest(BaseModel):
    """
    Request model for creating a campaign.

    Attributes:
        name (str): Name for the campaign.
        description (Optional[str]): Optional description for the campaign.
    """
    name: str = Field(..., min_length=1, max_length=255, description="Name of the campaign")
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Optional description of the campaign"
    )
