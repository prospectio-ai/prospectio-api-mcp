"""
Tests for application/requests/campaign.py and application/requests/insert_leads.py
Pydantic request model validation.
"""
import pytest
from pydantic import ValidationError

from application.requests.campaign import CreateCampaignRequest
from application.requests.insert_leads import InsertLeadsRequest


class TestCreateCampaignRequest:
    """Test suite for CreateCampaignRequest validation."""

    def test_valid_campaign_with_name_only(self):
        """Should accept a request with just name."""
        req = CreateCampaignRequest(name="Q1 Outreach")
        assert req.name == "Q1 Outreach"
        assert req.description is None

    def test_valid_campaign_with_description(self):
        """Should accept a request with name and description."""
        req = CreateCampaignRequest(name="Q1 Outreach", description="Target Python devs")
        assert req.name == "Q1 Outreach"
        assert req.description == "Target Python devs"

    def test_rejects_empty_name(self):
        """Should reject an empty name."""
        with pytest.raises(ValidationError):
            CreateCampaignRequest(name="")

    def test_rejects_name_over_255_chars(self):
        """Should reject name exceeding 255 characters."""
        with pytest.raises(ValidationError):
            CreateCampaignRequest(name="x" * 256)

    def test_rejects_description_over_1000_chars(self):
        """Should reject description exceeding 1000 characters."""
        with pytest.raises(ValidationError):
            CreateCampaignRequest(name="Test", description="x" * 1001)

    def test_rejects_missing_name(self):
        """Should reject request without name."""
        with pytest.raises(ValidationError):
            CreateCampaignRequest()  # type: ignore

    def test_accepts_max_length_name(self):
        """Should accept name at exactly 255 characters."""
        req = CreateCampaignRequest(name="x" * 255)
        assert len(req.name) == 255

    def test_accepts_max_length_description(self):
        """Should accept description at exactly 1000 characters."""
        req = CreateCampaignRequest(name="Test", description="x" * 1000)
        assert len(req.description) == 1000


class TestInsertLeadsRequest:
    """Test suite for InsertLeadsRequest validation."""

    def test_valid_request(self):
        """Should accept a valid request with all fields."""
        req = InsertLeadsRequest(
            source="jsearch",
            location="FR",
            job_params=["Python", "AI"]
        )
        assert req.source == "jsearch"
        assert req.location == "FR"
        assert req.job_params == ["Python", "AI"]

    def test_rejects_missing_source(self):
        """Should reject request without source."""
        with pytest.raises(ValidationError):
            InsertLeadsRequest(location="FR", job_params=["Python"])  # type: ignore

    def test_rejects_missing_location(self):
        """Should reject request without location."""
        with pytest.raises(ValidationError):
            InsertLeadsRequest(source="jsearch", job_params=["Python"])  # type: ignore

    def test_rejects_missing_job_params(self):
        """Should reject request without job_params."""
        with pytest.raises(ValidationError):
            InsertLeadsRequest(source="jsearch", location="FR")  # type: ignore

    def test_accepts_empty_job_params_list(self):
        """Should accept empty job_params list."""
        req = InsertLeadsRequest(source="jsearch", location="FR", job_params=[])
        assert req.job_params == []

    def test_job_params_preserves_order(self):
        """Should preserve order of job_params."""
        req = InsertLeadsRequest(
            source="jsearch",
            location="US",
            job_params=["Python", "AI", "LLM"]
        )
        assert req.job_params == ["Python", "AI", "LLM"]
