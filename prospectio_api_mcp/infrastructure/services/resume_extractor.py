"""Resume extraction service for extracting profile data from PDF resumes."""

import io
import logging
from typing import List

from markitdown import MarkItDown
from langchain.prompts import PromptTemplate

from config import LLMConfig
from domain.entities.profile import Profile
from domain.entities.work_experience import WorkExperience
from domain.entities.education import Education
from domain.entities.certification import Certification
from domain.entities.language import Language
from domain.services.prompt_loader import PromptLoader
from infrastructure.api.llm_client_factory import LLMClientFactory
from infrastructure.dto.llm import ExtractedProfileLLM, ResumeExtractionResult


logger = logging.getLogger(__name__)


# Maximum file size: 10MB
MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_CONTENT_TYPES = ["application/pdf"]


class ResumeExtractor:
    """Service for extracting profile information from PDF resumes.

    Uses MarkItDown for PDF to text conversion and LLM for structured
    profile extraction.
    """

    def __init__(self) -> None:
        """Initialize the ResumeExtractor with LLM client."""
        model = LLMConfig().MODEL  # type: ignore
        self.llm_client = LLMClientFactory(
            model=model,
            config=LLMConfig(),  # type: ignore
        ).create_client()
        self.markitdown = MarkItDown()

    def validate_file(self, content_type: str, file_size: int) -> tuple[bool, str]:
        """Validate uploaded file for content type and size.

        Args:
            content_type: MIME type of the uploaded file.
            file_size: Size of the file in bytes.

        Returns:
            Tuple of (is_valid, error_message). If valid, error_message is empty.
        """
        if content_type not in ALLOWED_CONTENT_TYPES:
            return False, f"Invalid file type. Allowed types: {', '.join(ALLOWED_CONTENT_TYPES)}"

        if file_size > MAX_FILE_SIZE:
            max_mb = MAX_FILE_SIZE / (1024 * 1024)
            return False, f"File too large. Maximum size is {max_mb}MB"

        return True, ""

    async def extract_from_pdf(self, file_content: bytes) -> ResumeExtractionResult:
        """Extract profile information from PDF resume content.

        Args:
            file_content: Raw bytes of the PDF file.

        Returns:
            ResumeExtractionResult containing extracted profile and raw text.

        Raises:
            ValueError: If PDF cannot be processed.
        """
        # Convert PDF to text
        raw_text = self._pdf_to_text(file_content)

        if not raw_text or not raw_text.strip():
            raise ValueError("Could not extract text from PDF. File may be corrupted or image-based.")

        # Extract structured profile using LLM
        profile = await self._extract_profile(raw_text)

        return ResumeExtractionResult(
            extracted_profile=profile,
            raw_text=raw_text
        )

    def _pdf_to_text(self, file_content: bytes) -> str:
        """Convert PDF bytes to text using MarkItDown.

        Args:
            file_content: Raw bytes of the PDF file.

        Returns:
            Extracted text from PDF.

        Raises:
            ValueError: If PDF conversion fails.
        """
        try:
            # MarkItDown expects a file-like object or path
            # Create a BytesIO object for in-memory processing
            file_stream = io.BytesIO(file_content)

            # Use convert method with stream
            result = self.markitdown.convert_stream(file_stream, file_extension=".pdf")

            return result.text_content if result.text_content else ""
        except Exception as e:
            logger.error(f"Error converting PDF to text: {e}")
            raise ValueError(f"Failed to process PDF: {str(e)}")

    async def _extract_profile(self, resume_text: str) -> Profile:
        """Extract structured profile from resume text using LLM.

        Args:
            resume_text: Plain text extracted from resume.

        Returns:
            Profile entity with extracted information.
        """
        prompt = PromptLoader().load_prompt("resume_extraction")
        template = PromptTemplate(
            input_variables=["resume_text"],
            template=prompt,
        )

        chain = template | self.llm_client.with_structured_output(ExtractedProfileLLM)

        result = await chain.ainvoke({"resume_text": resume_text})

        # Convert LLM result to Profile entity
        extracted = ExtractedProfileLLM.model_validate(result)

        # Convert LLM DTOs to domain entities
        work_experiences: List[WorkExperience] = [
            WorkExperience(**exp.model_dump()) for exp in extracted.work_experience
        ]

        education_list: List[Education] = [
            Education(**edu.model_dump()) for edu in extracted.education
        ]

        certifications_list: List[Certification] = [
            Certification(**cert.model_dump()) for cert in extracted.certifications
        ]

        languages_list: List[Language] = [
            Language(**lang.model_dump()) for lang in extracted.languages
        ]

        return Profile(
            full_name=extracted.full_name,
            email=extracted.email,
            phone=extracted.phone,
            job_title=extracted.job_title,
            location=extracted.location,
            bio=extracted.bio,
            years_of_experience=extracted.years_of_experience,
            work_experience=work_experiences,
            education=education_list,
            certifications=certifications_list,
            languages=languages_list,
            technos=extracted.technos,
        )
