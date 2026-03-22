from typing import Optional, List, Any
from pydantic import BaseModel, Field, RootModel

JSON_LD_TYPE_ALIAS = "@type"


class AddressDTO(BaseModel):
    """
    DTO for postal address information.
    """

    type: Optional[str] = Field(None, alias=JSON_LD_TYPE_ALIAS)
    addressCountry: Optional[str] = None
    addressLocality: Optional[str] = None
    addressRegion: Optional[str] = None


class PlaceDTO(BaseModel):
    """
    DTO for place/location information.
    """

    type: Optional[str] = Field(None, alias=JSON_LD_TYPE_ALIAS)
    address: Optional[AddressDTO] = None


class LocationRequirementDTO(BaseModel):
    """
    DTO for location requirements.
    """

    type: Optional[str] = Field(None, alias=JSON_LD_TYPE_ALIAS)
    name: Optional[str] = None


class ActiveJobDTO(BaseModel):
    """
    DTO representing a single active job entry.
    """

    id: str
    date_posted: Optional[str] = None
    date_created: Optional[str] = None
    title: Optional[str] = None
    organization: Optional[str] = None
    organization_url: Optional[str] = None
    date_validthrough: Optional[str] = None
    locations_raw: Optional[List[PlaceDTO]] = None
    locations_alt_raw: Optional[List[str]] = None
    location_type: Optional[str] = None
    location_requirements_raw: Optional[List[LocationRequirementDTO]] = None
    salary_raw: Optional[Any] = None
    employment_type: Optional[List[str]] = None
    url: Optional[str] = None
    source_type: Optional[str] = None
    source: Optional[str] = None
    source_domain: Optional[str] = None
    organization_logo: Optional[str] = None
    cities_derived: Optional[List[str]] = None
    regions_derived: Optional[List[str]] = None
    countries_derived: Optional[List[str]] = None
    locations_derived: Optional[List[str]] = None
    timezones_derived: Optional[List[str]] = None
    lats_derived: Optional[List[float]] = None
    lngs_derived: Optional[List[float]] = None
    remote_derived: Optional[bool] = None
    domain_derived: Optional[str] = None
    description_text: Optional[str] = None


class ActiveJobsResponseDTO(BaseModel):
    """
    DTO for a list of active jobs.
    """

    active_jobs: List[ActiveJobDTO] = Field(
        ..., description="List of active job entries"
    )
