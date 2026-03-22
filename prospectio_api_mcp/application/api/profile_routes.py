from application.use_cases.profile import ProfileUseCase
from application.use_cases.reset_data import ResetDataUseCase
from domain.entities.profile import Profile
from fastapi import APIRouter, Body, HTTPException, UploadFile, File, status
import logging
import traceback
from domain.ports.profile_respository import ProfileRepositoryPort
from domain.ports.leads_repository import LeadsRepositoryPort
from application.api.mcp_routes import mcp_prospectio
from infrastructure.services.resume_extractor import ResumeExtractor
from infrastructure.dto.llm import ResumeExtractionResult


logger = logging.getLogger(__name__)


def profile_router(
    repository: ProfileRepositoryPort,
    leads_repository: LeadsRepositoryPort,
) -> APIRouter:
    """
    Create an APIRouter for profile endpoints with injected repository.

    Args:
        repository (ProfileRepositoryPort): Profile repository for data persistence.
        leads_repository (LeadsRepositoryPort): Leads repository for reset operations.

    Returns:
        APIRouter: Configured router with profile endpoints.
    """
    profile_router = APIRouter()

    @profile_router.post("/profile/upsert")
    @mcp_prospectio.tool(
        description="Insert or update the user profile into the database. "
        "Use this AFTER calling get/profile when the profile doesn't exist or needs updates. "
        "You can ask for missing fields if the user hasn't provided them, or save partial data if user prefers. "
        'Example JSON: {"job_title": "Software Developer", "location": "FR", "bio": "Passionate developer", "work_experience": [{"company": "TechCorp", "position": "Developer", "start_date": "2020-01", "end_date": "2023-12", "description": "Full-stack development"}], "technos": ["Python", "FastAPI"]}'
    )
    async def upsert_profile(
        profile: Profile = Body(
            ..., description="User profile data to insert or update"
        )
    ) -> dict:
        """
        Insert or update a user profile in the database.

        Args:
            profile (Profile): The profile data to insert or update in the database.

        Returns:
            dict: Empty dictionary indicating successful operation.
        """
        try:
            return await ProfileUseCase(repository).upsert_profile(profile)
        except Exception as e:
            logger.error(f"Error in get company jobs: {e}\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=str(e))

    @profile_router.get("/profile")
    @mcp_prospectio.tool(
        description="ALWAYS USE THIS FIRST to get the user profile from the database. "
        "This must be called before using any other endpoints (upsert profile, get leads, insert leads) "
        "to understand the user's context, job preferences, and location. "
        "If no profile exists or profile is incomplete, then use upsert to create/update it."
    )
    async def get_profile() -> Profile:
        """Retourne le profil utilisateur complet avec toutes les informations."""
        try:
            return await ProfileUseCase(repository).get_profile()
        except Exception as e:
            logger.error(f"Error in get profile: {e}\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=str(e))

    @profile_router.post(
        "/profile/upload-resume",
        response_model=ResumeExtractionResult,
        status_code=status.HTTP_200_OK,
        summary="Upload resume PDF for profile extraction",
        description="Upload a PDF resume to extract profile information automatically. "
        "Returns extracted profile data and raw text from the resume.",
    )
    async def upload_resume(
        file: UploadFile = File(..., description="PDF resume file to extract profile from")
    ) -> ResumeExtractionResult:
        """Extract profile information from an uploaded PDF resume.

        Args:
            file: The uploaded PDF file containing the resume.

        Returns:
            ResumeExtractionResult with extracted_profile and raw_text.

        Raises:
            HTTPException: If file validation fails or extraction errors occur.
        """
        try:
            resume_extractor = ResumeExtractor()

            # Validate file type and size
            content_type = file.content_type or ""
            file_content = await file.read()
            file_size = len(file_content)

            is_valid, error_message = resume_extractor.validate_file(
                content_type, file_size
            )
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_message
                )

            # Extract profile from PDF
            result = await resume_extractor.extract_from_pdf(file_content)
            return result

        except HTTPException:
            raise
        except ValueError as e:
            logger.error(f"Error extracting resume: {e}\n{traceback.format_exc()}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"Error in upload resume: {e}\n{traceback.format_exc()}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process resume"
            )

    @profile_router.delete(
        "/profile/reset",
        status_code=status.HTTP_200_OK,
        summary="Reset all user data",
        description="Delete all user data including profile, contacts, jobs, and companies. "
        "This action is irreversible.",
    )
    async def reset_data() -> dict:
        """Reset all user data by deleting profile and leads.

        Returns:
            dict: Result message indicating successful reset.

        Raises:
            HTTPException: If reset operation fails.
        """
        try:
            return await ResetDataUseCase(repository, leads_repository).execute()
        except Exception as e:
            logger.error(f"Error in reset data: {e}\n{traceback.format_exc()}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to reset data"
            )

    return profile_router
