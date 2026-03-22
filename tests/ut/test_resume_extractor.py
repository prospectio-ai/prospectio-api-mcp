"""
Tests for infrastructure/services/resume_extractor.py - ResumeExtractor service.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from infrastructure.services.resume_extractor import (
    ResumeExtractor,
    MAX_FILE_SIZE,
    ALLOWED_CONTENT_TYPES,
)


class TestResumeExtractorValidation:
    """Test suite for ResumeExtractor.validate_file."""

    @pytest.fixture
    def extractor(self):
        """Create a ResumeExtractor with mocked dependencies."""
        with patch("infrastructure.services.resume_extractor.LLMConfig") as mock_config_cls, \
             patch("infrastructure.services.resume_extractor.LLMClientFactory") as mock_factory_cls, \
             patch("infrastructure.services.resume_extractor.MarkItDown"):
            mock_config = MagicMock()
            mock_config.MODEL = "Ollama/llama3"
            mock_config_cls.return_value = mock_config
            mock_factory_cls.return_value.create_client.return_value = MagicMock()
            yield ResumeExtractor()

    def test_valid_pdf_file(self, extractor):
        """Should accept a valid PDF file."""
        is_valid, error = extractor.validate_file("application/pdf", 1024)
        assert is_valid is True
        assert error == ""

    def test_rejects_non_pdf_content_type(self, extractor):
        """Should reject non-PDF content types."""
        is_valid, error = extractor.validate_file("text/plain", 1024)
        assert is_valid is False
        assert "Invalid file type" in error

    def test_rejects_image_content_type(self, extractor):
        """Should reject image content types."""
        is_valid, error = extractor.validate_file("image/png", 1024)
        assert is_valid is False
        assert "Invalid file type" in error

    def test_rejects_oversized_file(self, extractor):
        """Should reject files exceeding MAX_FILE_SIZE."""
        is_valid, error = extractor.validate_file("application/pdf", MAX_FILE_SIZE + 1)
        assert is_valid is False
        assert "File too large" in error

    def test_accepts_max_size_file(self, extractor):
        """Should accept files at exactly MAX_FILE_SIZE."""
        is_valid, error = extractor.validate_file("application/pdf", MAX_FILE_SIZE)
        assert is_valid is True
        assert error == ""

    def test_allowed_content_types_contains_pdf(self):
        """ALLOWED_CONTENT_TYPES should include application/pdf."""
        assert "application/pdf" in ALLOWED_CONTENT_TYPES

    def test_max_file_size_is_10mb(self):
        """MAX_FILE_SIZE should be 10MB."""
        assert MAX_FILE_SIZE == 10 * 1024 * 1024


class TestResumeExtractorPdfToText:
    """Test suite for ResumeExtractor._pdf_to_text."""

    @pytest.fixture
    def extractor(self):
        with patch("infrastructure.services.resume_extractor.LLMConfig") as mock_config_cls, \
             patch("infrastructure.services.resume_extractor.LLMClientFactory") as mock_factory_cls, \
             patch("infrastructure.services.resume_extractor.MarkItDown") as mock_markitdown_cls:
            mock_config = MagicMock()
            mock_config.MODEL = "Ollama/llama3"
            mock_config_cls.return_value = mock_config
            mock_factory_cls.return_value.create_client.return_value = MagicMock()

            mock_markitdown = MagicMock()
            mock_markitdown_cls.return_value = mock_markitdown

            ext = ResumeExtractor()
            ext._mock_markitdown = mock_markitdown
            yield ext

    def test_converts_pdf_bytes_to_text(self, extractor):
        """Should return text content from PDF bytes."""
        mock_result = MagicMock()
        mock_result.text_content = "John Doe\nSenior Developer"
        extractor._mock_markitdown.convert_stream.return_value = mock_result

        result = extractor._pdf_to_text(b"fake-pdf-bytes")

        assert result == "John Doe\nSenior Developer"
        extractor._mock_markitdown.convert_stream.assert_called_once()

    def test_returns_empty_string_when_no_content(self, extractor):
        """Should return empty string when text_content is None."""
        mock_result = MagicMock()
        mock_result.text_content = None
        extractor._mock_markitdown.convert_stream.return_value = mock_result

        result = extractor._pdf_to_text(b"fake-pdf-bytes")
        assert result == ""

    def test_raises_value_error_on_conversion_failure(self, extractor):
        """Should raise ValueError when conversion fails."""
        extractor._mock_markitdown.convert_stream.side_effect = Exception("Parse error")

        with pytest.raises(ValueError, match="Failed to process PDF"):
            extractor._pdf_to_text(b"corrupt-pdf")


class TestResumeExtractorExtractFromPdf:
    """Test suite for ResumeExtractor.extract_from_pdf."""

    @pytest.fixture
    def extractor(self):
        with patch("infrastructure.services.resume_extractor.LLMConfig") as mock_config_cls, \
             patch("infrastructure.services.resume_extractor.LLMClientFactory") as mock_factory_cls, \
             patch("infrastructure.services.resume_extractor.MarkItDown"):
            mock_config = MagicMock()
            mock_config.MODEL = "Ollama/llama3"
            mock_config_cls.return_value = mock_config
            mock_factory_cls.return_value.create_client.return_value = MagicMock()
            yield ResumeExtractor()

    @pytest.mark.asyncio
    async def test_raises_when_pdf_yields_empty_text(self, extractor):
        """Should raise ValueError when PDF yields empty text."""
        with patch.object(extractor, "_pdf_to_text", return_value=""):
            with pytest.raises(ValueError, match="Could not extract text from PDF"):
                await extractor.extract_from_pdf(b"fake-pdf")

    @pytest.mark.asyncio
    async def test_raises_when_pdf_yields_whitespace_only(self, extractor):
        """Should raise ValueError when PDF yields only whitespace."""
        with patch.object(extractor, "_pdf_to_text", return_value="   \n\t  "):
            with pytest.raises(ValueError, match="Could not extract text from PDF"):
                await extractor.extract_from_pdf(b"fake-pdf")

    @pytest.mark.asyncio
    async def test_returns_extraction_result_on_success(self, extractor):
        """Should return ResumeExtractionResult with profile and raw text."""
        from domain.entities.profile import Profile
        from infrastructure.dto.llm import ResumeExtractionResult

        mock_profile = Profile(job_title="Dev", location="Paris", bio="Bio")

        with patch.object(extractor, "_pdf_to_text", return_value="John Doe resume text"), \
             patch.object(extractor, "_extract_profile", new_callable=AsyncMock, return_value=mock_profile):

            result = await extractor.extract_from_pdf(b"fake-pdf")

            assert isinstance(result, ResumeExtractionResult)
            assert result.extracted_profile.job_title == "Dev"
            assert result.raw_text == "John Doe resume text"
