"""Education entity for representing educational background."""

from typing import Optional
from pydantic import BaseModel, Field


class Education(BaseModel):
    """Represents an education entry in a profile."""

    institution: Optional[str] = Field(
        None, description="Name of the educational institution"
    )
    degree: Optional[str] = Field(
        None, description="Degree obtained (e.g., Bachelor, Master, PhD)"
    )
    field_of_study: Optional[str] = Field(
        None, description="Field of study or major"
    )
    start_date: Optional[str] = Field(
        None, description="Start date in YYYY-MM format"
    )
    end_date: Optional[str] = Field(
        None, description="End date in YYYY-MM format or 'Present'"
    )
