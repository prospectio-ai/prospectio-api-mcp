from typing import List, Optional
from pydantic import BaseModel, Field


class Company(BaseModel):
    """
    Represents a company with optional fields to match frontend requirements.
    """

    id: Optional[str] = Field(None, description="Unique identifier for the company")
    name: Optional[str] = Field(None, description="Name of the company")
    industry: Optional[str] = Field(None, description="Industry sector of the company")
    compatibility: Optional[str] = Field(
        None,
        description="Compatibility rate with the prospect (e.g., '95% compatibility')",
    )
    source: Optional[str] = Field(
        None, description="Source of the information (e.g., 'LinkedIn Sales Navigator')"
    )
    location: Optional[str] = Field(None, description="Location of the company")
    size: Optional[str] = Field(
        None, description="Company size (e.g., '50-200 employees')"
    )
    revenue: Optional[str] = Field(None, description="Company revenue (e.g., '5-10M€')")
    website: Optional[str] = Field(None, description="Company website")
    description: Optional[str] = Field(
        None, description="Description of the company ('About')"
    )
    opportunities: Optional[list[str]] = Field(
        None,
        description="List of opportunities or keywords associated with the company",
    )


class CompanyEntity(BaseModel):
    """
    DTO for a list of active jobs.
    """
    companies: List[Company] = Field(..., description="List of companies")
    pages: Optional[int] = Field(None, description="Total number of pages available")
