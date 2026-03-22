"""LLM DTO for language extraction."""

from typing import Optional
from pydantic import BaseModel, Field


class LanguageLLM(BaseModel):
    """Schema for LLM structured output of language proficiency."""

    name: str = Field(description="Name of the language")
    proficiency: Optional[str] = Field(
        None,
        description="Proficiency level (e.g., Native, Fluent, Professional, Intermediate, Basic)"
    )
