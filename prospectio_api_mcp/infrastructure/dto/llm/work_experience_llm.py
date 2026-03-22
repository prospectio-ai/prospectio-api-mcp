"""LLM DTO for work experience extraction."""

from pydantic import BaseModel, Field


class WorkExperienceLLM(BaseModel):
    """Schema for LLM structured output of work experience."""

    position: str = Field(description="Job position or title")
    company: str = Field(description="Company name")
    start_date: str = Field(description="Start date in YYYY-MM format")
    end_date: str = Field(description="End date in YYYY-MM format or 'Present'")
    description: str = Field(description="Description of the role and responsibilities")
