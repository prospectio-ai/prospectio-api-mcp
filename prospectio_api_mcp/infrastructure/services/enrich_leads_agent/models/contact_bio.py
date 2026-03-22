from pydantic import BaseModel, Field


class ContactBio(BaseModel):
    """
    Represents a contact's biography information extracted from search results.
    """
    short_description: str = Field(
        ...,
        description="Short bio of the contact (~100 chars)",
        max_length=255
    )
    full_bio: str = Field(
        ...,
        description="Full biography of the contact (500-1500 chars)"
    )
