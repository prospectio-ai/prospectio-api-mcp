"""Certification entity for representing professional certifications."""

from typing import Optional
from pydantic import BaseModel, Field


class Certification(BaseModel):
    """Represents a certification entry in a profile."""

    name: Optional[str] = Field(
        None, description="Name of the certification"
    )
    issuing_organization: Optional[str] = Field(
        None, description="Organization that issued the certification"
    )
    issue_date: Optional[str] = Field(
        None, description="Issue date in YYYY-MM format"
    )
    expiration_date: Optional[str] = Field(
        None, description="Expiration date in YYYY-MM format or None if no expiration"
    )
