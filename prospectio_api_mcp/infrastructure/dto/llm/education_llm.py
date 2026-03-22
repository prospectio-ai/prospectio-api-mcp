"""LLM DTO for education extraction."""

from typing import Optional
from pydantic import BaseModel, Field


class EducationLLM(BaseModel):
    """Schema for LLM structured output of education."""

    institution: str = Field(description="Name of the educational institution")
    degree: str = Field(description="Degree obtained (e.g., Bachelor, Master, PhD)")
    field_of_study: Optional[str] = Field(
        None, description="Field of study or major"
    )
    start_date: Optional[str] = Field(
        None, description="Start date in YYYY-MM format"
    )
    end_date: Optional[str] = Field(
        None, description="End date in YYYY-MM format or 'Present'"
    )
