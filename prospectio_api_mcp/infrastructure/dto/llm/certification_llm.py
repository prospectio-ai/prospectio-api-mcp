"""LLM DTO for certification extraction."""

from typing import Optional
from pydantic import BaseModel, Field


class CertificationLLM(BaseModel):
    """Schema for LLM structured output of certification."""

    name: str = Field(description="Name of the certification")
    issuing_organization: Optional[str] = Field(
        None, description="Organization that issued the certification"
    )
    issue_date: Optional[str] = Field(
        None, description="Issue date in YYYY-MM format"
    )
    expiration_date: Optional[str] = Field(
        None, description="Expiration date in YYYY-MM format or None if no expiration"
    )
