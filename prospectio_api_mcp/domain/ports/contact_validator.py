from abc import ABC, abstractmethod
from domain.entities.validation_result import ValidationResult
from domain.entities.contact import Contact
from domain.entities.company import Company


class ContactValidatorPort(ABC):
    """
    Port interface for contact validation.

    Implementations should validate extracted contacts against various criteria
    and return a confidence score with validation details.
    """

    @abstractmethod
    def validate_contact(
        self,
        contact: Contact,
        company: Company,
        search_answer: str,
        searched_job_title: str,
    ) -> ValidationResult:
        """
        Validate an extracted contact and return a confidence score.

        Args:
            contact: The contact entity to validate.
            company: The company the contact is associated with.
            search_answer: The original search results text used for extraction.
            searched_job_title: The job title that was searched for.

        Returns:
            ValidationResult: The validation result with confidence score and details.
        """
        pass
