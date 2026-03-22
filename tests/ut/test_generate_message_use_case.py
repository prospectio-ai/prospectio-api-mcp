"""
Tests for application/use_cases/generate_message.py - GenerateMessageUseCase.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from application.use_cases.generate_message import GenerateMessageUseCase
from domain.entities.contact import Contact
from domain.entities.company import Company
from domain.entities.profile import Profile
from domain.entities.prospect_message import ProspectMessage


class TestGenerateMessageUseCase:
    """Test suite for GenerateMessageUseCase."""

    @pytest.fixture
    def mock_repository(self):
        """Create a mock leads repository."""
        repo = AsyncMock()
        return repo

    @pytest.fixture
    def mock_profile_repository(self):
        """Create a mock profile repository."""
        repo = AsyncMock()
        return repo

    @pytest.fixture
    def mock_message_port(self):
        """Create a mock message generation port."""
        port = AsyncMock()
        return port

    @pytest.fixture
    def sample_profile(self):
        """Sample user profile."""
        return Profile(
            job_title="Senior Python Developer",
            location="Paris",
            bio="Experienced dev",
        )

    @pytest.fixture
    def sample_contact(self):
        """Sample contact."""
        return Contact(
            id="contact-123",
            company_id="company-456",
            name="Alice",
            email=["alice@example.com"],
        )

    @pytest.fixture
    def sample_company(self):
        """Sample company."""
        return Company(
            id="company-456",
            name="TechCorp",
            industry="Technology",
        )

    @pytest.fixture
    def use_case(self, mock_repository, mock_profile_repository, mock_message_port):
        """Create a GenerateMessageUseCase with mock dependencies."""
        return GenerateMessageUseCase(
            repository=mock_repository,
            profile_repository=mock_profile_repository,
            message_port=mock_message_port,
        )

    @pytest.mark.asyncio
    async def test_generate_message_success(
        self,
        use_case,
        mock_repository,
        mock_profile_repository,
        mock_message_port,
        sample_profile,
        sample_contact,
        sample_company,
    ):
        """Should generate a message when profile, contact, and company all exist."""
        mock_profile_repository.get_profile.return_value = sample_profile
        mock_repository.get_contact_by_id.return_value = sample_contact
        mock_repository.get_company_by_id.return_value = sample_company
        expected_message = ProspectMessage(subject="Hi", message="Hello Alice")
        mock_message_port.get_message.return_value = expected_message

        result = await use_case.generate_message("contact-123")

        assert result == expected_message
        mock_profile_repository.get_profile.assert_called_once()
        mock_repository.get_contact_by_id.assert_called_once_with("contact-123")
        mock_repository.get_company_by_id.assert_called_once_with("company-456")
        mock_message_port.get_message.assert_called_once_with(
            sample_profile, sample_contact, sample_company
        )

    @pytest.mark.asyncio
    async def test_raises_when_profile_not_found(
        self,
        use_case,
        mock_profile_repository,
    ):
        """Should raise ValueError when profile is not found."""
        mock_profile_repository.get_profile.return_value = None

        with pytest.raises(ValueError, match="Profile not found"):
            await use_case.generate_message("contact-123")

    @pytest.mark.asyncio
    async def test_raises_when_contact_not_found(
        self,
        use_case,
        mock_repository,
        mock_profile_repository,
        sample_profile,
    ):
        """Should raise ValueError when contact is not found."""
        mock_profile_repository.get_profile.return_value = sample_profile
        mock_repository.get_contact_by_id.return_value = None

        with pytest.raises(ValueError, match="Contact with id contact-123 not found"):
            await use_case.generate_message("contact-123")

    @pytest.mark.asyncio
    async def test_raises_when_company_not_found(
        self,
        use_case,
        mock_repository,
        mock_profile_repository,
        sample_profile,
        sample_contact,
    ):
        """Should raise ValueError when company is not found."""
        mock_profile_repository.get_profile.return_value = sample_profile
        mock_repository.get_contact_by_id.return_value = sample_contact
        mock_repository.get_company_by_id.return_value = None

        with pytest.raises(ValueError, match="Company with id company-456 not found"):
            await use_case.generate_message("contact-123")
