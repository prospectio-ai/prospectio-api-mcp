from enum import StrEnum
from typing import Optional
from pydantic import BaseModel, Field


class ValidationStatus(StrEnum):
    """
    Validation status for contacts based on confidence score thresholds.

    VERIFIED (70-100): High confidence - contact is likely correct
    LIKELY_VALID (40-69): Medium confidence - may need review
    NEEDS_REVIEW (0-39): Low confidence - requires manual verification
    """

    VERIFIED = "verified"
    LIKELY_VALID = "likely_valid"
    NEEDS_REVIEW = "needs_review"


class ValidationResult(BaseModel):
    """
    Result of contact validation containing confidence score and validation details.
    """

    confidence_score: int = Field(
        ...,
        ge=0,
        le=100,
        description="Confidence score from 0 to 100"
    )
    validation_status: ValidationStatus = Field(
        ...,
        description="Validation status based on confidence score thresholds"
    )
    validation_reasons: list[str] = Field(
        default_factory=list,
        description="List of reasons explaining the confidence score"
    )
    email_domain_valid: bool = Field(
        default=False,
        description="Whether the email domain matches the company domain"
    )
    linkedin_valid: bool = Field(
        default=False,
        description="Whether a valid LinkedIn URL was found"
    )
    name_found_in_search: bool = Field(
        default=False,
        description="Whether the contact name was found in the original search results"
    )
    title_matches_search: bool = Field(
        default=False,
        description="Whether the contact title matches the searched job title"
    )

    @classmethod
    def from_score(
        cls,
        confidence_score: int,
        validation_reasons: list[str],
        email_domain_valid: bool = False,
        linkedin_valid: bool = False,
        name_found_in_search: bool = False,
        title_matches_search: bool = False,
    ) -> "ValidationResult":
        """
        Create a ValidationResult from a confidence score, automatically determining the status.

        Args:
            confidence_score: The calculated confidence score (0-100).
            validation_reasons: List of reasons for the score.
            email_domain_valid: Whether email domain matched company.
            linkedin_valid: Whether LinkedIn URL was valid.
            name_found_in_search: Whether name was in search results.
            title_matches_search: Whether title matched search.

        Returns:
            ValidationResult: The validation result with appropriate status.
        """
        if confidence_score >= 70:
            status = ValidationStatus.VERIFIED
        elif confidence_score >= 40:
            status = ValidationStatus.LIKELY_VALID
        else:
            status = ValidationStatus.NEEDS_REVIEW

        return cls(
            confidence_score=min(max(confidence_score, 0), 100),
            validation_status=status,
            validation_reasons=validation_reasons,
            email_domain_valid=email_domain_valid,
            linkedin_valid=linkedin_valid,
            name_found_in_search=name_found_in_search,
            title_matches_search=title_matches_search,
        )
