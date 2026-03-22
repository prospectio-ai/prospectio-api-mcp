"""LLM DTO for extracted profile from resume."""

from typing import List, Optional
from pydantic import BaseModel, Field

from .work_experience_llm import WorkExperienceLLM
from .education_llm import EducationLLM
from .certification_llm import CertificationLLM
from .language_llm import LanguageLLM


class ExtractedProfileLLM(BaseModel):
    """Schema for LLM structured output of extracted profile."""

    full_name: Optional[str] = Field(
        None, description="Full name of the candidate"
    )
    email: Optional[str] = Field(
        None, description="Email address of the candidate"
    )
    phone: Optional[str] = Field(
        None, description="Phone number of the candidate"
    )
    job_title: str = Field(description="Current job title")
    location: str = Field(description="Current location")
    bio: str = Field(description="Professional biography")
    years_of_experience: Optional[int] = Field(
        None, description="Total years of professional experience"
    )
    work_experience: List[WorkExperienceLLM] = Field(
        default_factory=list, description="List of work experiences"
    )
    education: List[EducationLLM] = Field(
        default_factory=list, description="List of education entries"
    )
    certifications: List[CertificationLLM] = Field(
        default_factory=list, description="List of certifications"
    )
    languages: List[LanguageLLM] = Field(
        default_factory=list, description="List of languages"
    )
    technos: List[str] = Field(
        default_factory=list, description="List of technologies"
    )
