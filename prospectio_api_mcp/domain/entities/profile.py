"""Profile entity for representing user profile information."""

from typing import List, Optional
from pydantic import BaseModel, Field

from .work_experience import WorkExperience
from .education import Education
from .certification import Certification
from .language import Language


class Profile(BaseModel):
    """Represents a user profile with personal and professional information."""

    full_name: Optional[str] = Field(None, description="Full name of the candidate")
    email: Optional[str] = Field(None, description="Email address of the candidate")
    phone: Optional[str] = Field(None, description="Phone number of the candidate")
    job_title: Optional[str] = Field(None, description="Current job title")
    location: Optional[str] = Field(None, description="Current location")
    bio: Optional[str] = Field(None, description="Professional biography")
    years_of_experience: Optional[int] = Field(
        None, description="Total years of professional experience"
    )
    work_experience: List[WorkExperience] = Field(
        default_factory=list, description="List of work experiences"
    )
    education: List[Education] = Field(
        default_factory=list, description="List of education entries"
    )
    certifications: List[Certification] = Field(
        default_factory=list, description="List of certifications"
    )
    languages: List[Language] = Field(
        default_factory=list, description="List of languages"
    )
    technos: List[str] = Field(
        default_factory=list, description="List of technologies"
    )
