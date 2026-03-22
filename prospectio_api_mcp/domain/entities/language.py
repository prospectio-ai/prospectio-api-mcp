"""Language entity for representing language proficiency."""

from typing import Optional
from pydantic import BaseModel, Field


class Language(BaseModel):
    """Represents a language proficiency entry in a profile."""

    name: Optional[str] = Field(
        None, description="Name of the language"
    )
    proficiency: Optional[str] = Field(
        None,
        description="Proficiency level (e.g., Native, Fluent, Professional, Intermediate, Basic)"
    )
