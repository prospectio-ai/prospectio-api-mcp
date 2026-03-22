"""
Tests for application/api/profile_routes.py - Profile route handlers via FastAPI TestClient.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from application.api.profile_routes import profile_router
from domain.entities.profile import Profile


@pytest.fixture
def mock_profile_repository():
    """Create a mock profile repository."""
    return AsyncMock()


@pytest.fixture
def mock_leads_repository():
    """Create a mock leads repository."""
    return AsyncMock()


@pytest.fixture
def app(mock_profile_repository, mock_leads_repository):
    """Create a FastAPI app with profile routes."""
    app = FastAPI()
    router = profile_router(
        repository=mock_profile_repository,
        leads_repository=mock_leads_repository,
    )
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create a TestClient."""
    return TestClient(app)


class TestGetProfileEndpoint:
    """Test GET /profile endpoint."""

    def test_get_profile_success(self, client, mock_profile_repository):
        """Should return profile data on success."""
        profile = Profile(
            job_title="Senior Developer",
            location="Paris",
            bio="A developer",
        )
        mock_profile_repository.get_profile.return_value = profile

        with patch("application.api.profile_routes.ProfileUseCase") as mock_uc_cls:
            mock_uc = AsyncMock()
            mock_uc.get_profile.return_value = profile
            mock_uc_cls.return_value = mock_uc

            response = client.get("/profile")

        assert response.status_code == 200
        data = response.json()
        assert data["job_title"] == "Senior Developer"

    def test_get_profile_handles_error(self, client, mock_profile_repository):
        """Should return 500 on error."""
        with patch("application.api.profile_routes.ProfileUseCase") as mock_uc_cls:
            mock_uc = AsyncMock()
            mock_uc.get_profile.side_effect = RuntimeError("DB down")
            mock_uc_cls.return_value = mock_uc

            response = client.get("/profile")

        assert response.status_code == 500


class TestUpsertProfileEndpoint:
    """Test POST /profile/upsert endpoint."""

    def test_upsert_profile_success(self, client, mock_profile_repository):
        """Should upsert profile and return result."""
        with patch("application.api.profile_routes.ProfileUseCase") as mock_uc_cls:
            mock_uc = AsyncMock()
            mock_uc.upsert_profile.return_value = {"result": "success"}
            mock_uc_cls.return_value = mock_uc

            response = client.post(
                "/profile/upsert",
                json={
                    "job_title": "Developer",
                    "location": "Paris",
                    "bio": "A developer",
                },
            )

        assert response.status_code == 200

    def test_upsert_profile_handles_error(self, client, mock_profile_repository):
        """Should return 500 on error."""
        with patch("application.api.profile_routes.ProfileUseCase") as mock_uc_cls:
            mock_uc = AsyncMock()
            mock_uc.upsert_profile.side_effect = RuntimeError("DB down")
            mock_uc_cls.return_value = mock_uc

            response = client.post(
                "/profile/upsert",
                json={
                    "job_title": "Developer",
                    "location": "Paris",
                    "bio": "A developer",
                },
            )

        assert response.status_code == 500


class TestResetDataEndpoint:
    """Test DELETE /profile/reset endpoint."""

    def test_reset_data_success(self, client, mock_profile_repository, mock_leads_repository):
        """Should reset data and return result."""
        with patch("application.api.profile_routes.ResetDataUseCase") as mock_uc_cls:
            mock_uc = AsyncMock()
            mock_uc.execute.return_value = {"message": "Data reset successfully"}
            mock_uc_cls.return_value = mock_uc

            response = client.delete("/profile/reset")

        assert response.status_code == 200
        assert "Data reset" in response.json()["message"]

    def test_reset_data_handles_error(self, client, mock_profile_repository, mock_leads_repository):
        """Should return 500 on error."""
        with patch("application.api.profile_routes.ResetDataUseCase") as mock_uc_cls:
            mock_uc = AsyncMock()
            mock_uc.execute.side_effect = RuntimeError("DB down")
            mock_uc_cls.return_value = mock_uc

            response = client.delete("/profile/reset")

        assert response.status_code == 500


class TestUploadResumeEndpoint:
    """Test POST /profile/upload-resume endpoint."""

    def test_upload_resume_rejects_non_pdf(self, client):
        """Should reject non-PDF file with 400."""
        with patch("application.api.profile_routes.ResumeExtractor") as mock_extractor_cls:
            mock_extractor = MagicMock()
            mock_extractor.validate_file.return_value = (False, "Invalid file type")
            mock_extractor_cls.return_value = mock_extractor

            response = client.post(
                "/profile/upload-resume",
                files={"file": ("resume.txt", b"fake content", "text/plain")},
            )

        assert response.status_code == 400

    def test_upload_resume_success(self, client):
        """Should accept PDF and return extraction result."""
        from domain.entities.profile import Profile
        from infrastructure.dto.llm import ResumeExtractionResult

        profile = Profile(job_title="Dev", location="Paris", bio="Bio")
        result = ResumeExtractionResult(extracted_profile=profile, raw_text="raw text")

        with patch("application.api.profile_routes.ResumeExtractor") as mock_extractor_cls:
            mock_extractor = MagicMock()
            mock_extractor.validate_file.return_value = (True, "")
            mock_extractor.extract_from_pdf = AsyncMock(return_value=result)
            mock_extractor_cls.return_value = mock_extractor

            response = client.post(
                "/profile/upload-resume",
                files={"file": ("resume.pdf", b"fake pdf", "application/pdf")},
            )

        assert response.status_code == 200
        data = response.json()
        assert "extracted_profile" in data
        assert data["raw_text"] == "raw text"

    def test_upload_resume_handles_value_error(self, client):
        """Should return 422 on ValueError."""
        with patch("application.api.profile_routes.ResumeExtractor") as mock_extractor_cls:
            mock_extractor = MagicMock()
            mock_extractor.validate_file.return_value = (True, "")
            mock_extractor.extract_from_pdf = AsyncMock(
                side_effect=ValueError("Bad PDF")
            )
            mock_extractor_cls.return_value = mock_extractor

            response = client.post(
                "/profile/upload-resume",
                files={"file": ("resume.pdf", b"bad pdf", "application/pdf")},
            )

        assert response.status_code == 422

    def test_upload_resume_handles_generic_error(self, client):
        """Should return 500 on generic error."""
        with patch("application.api.profile_routes.ResumeExtractor") as mock_extractor_cls:
            mock_extractor = MagicMock()
            mock_extractor.validate_file.return_value = (True, "")
            mock_extractor.extract_from_pdf = AsyncMock(
                side_effect=RuntimeError("Unexpected error")
            )
            mock_extractor_cls.return_value = mock_extractor

            response = client.post(
                "/profile/upload-resume",
                files={"file": ("resume.pdf", b"bad pdf", "application/pdf")},
            )

        assert response.status_code == 500
