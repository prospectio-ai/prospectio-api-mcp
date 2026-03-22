"""Result model for resume extraction."""

from pydantic import BaseModel, Field

from domain.entities.profile import Profile


class ResumeExtractionResult(BaseModel):
    """Result of resume extraction containing extracted profile and raw text."""

    extracted_profile: Profile = Field(
        description="Extracted profile data from resume"
    )
    raw_text: str = Field(description="Raw text extracted from PDF")
