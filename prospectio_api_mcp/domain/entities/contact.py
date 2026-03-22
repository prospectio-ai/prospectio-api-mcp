from typing import Optional, List
from pydantic import BaseModel, Field

class Contact(BaseModel):
    """
    Represents a business contact with optional fields: name, email, phone, and company name.
    """
    id: Optional[str] = Field(None, description="Unique identifier for the contact")
    company_id: Optional[str] = Field(
        None, description="Name of the company associated with the contact"
    )
    company_name: Optional[str] = Field(
        None, description="Name of the company associated with the contact"
    )
    job_id: Optional[str] = Field(
        None, description="ID of the job associated with the contact"
    )
    job_title: Optional[str] = Field(
        None, description="Title of the job associated with the contact"
    )
    name: Optional[str] = Field(None, description="Name of the contact")
    email: Optional[list[str]] = Field(None, description="Email address of the contact")
    title: Optional[str] = Field(None, description="Title of the contact")
    phone: Optional[str] = Field(None, description="Phone number of the contact")
    profile_url: Optional[str] = Field(
        None, description="URL to the contact's profile (e.g., LinkedIn)"
    )
    short_description: Optional[str] = Field(
        None, description="Short bio of the contact (~100 chars)"
    )
    full_bio: Optional[str] = Field(
        None, description="Full biography of the contact (500-1500 chars)"
    )
    confidence_score: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Validation confidence score (0-100). Scores >= 70 are verified."
    )
    validation_status: Optional[str] = Field(
        None,
        description="Validation status: 'verified' (70-100), 'likely_valid' (40-69), 'needs_review' (0-39)"
    )
    validation_reasons: Optional[list[str]] = Field(
        None,
        description="List of reasons explaining the confidence score"
    )


class ContactEntity(BaseModel):
    """
    DTO for a list of contacts.
    """
    contacts: List[Contact] = Field(..., description="List of contacts")
    pages: Optional[int] = Field(None, description="Total number of pages available")
