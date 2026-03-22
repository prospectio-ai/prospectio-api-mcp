"""
Tests for application/api/leads_routes.py - Leads route handlers via FastAPI TestClient.
"""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from application.api.leads_routes import leads_router
from domain.entities.contact import Contact, ContactEntity
from domain.entities.company import Company, CompanyEntity
from domain.entities.task import Task
from domain.entities.campaign import Campaign, CampaignEntity, CampaignStatus
from domain.entities.campaign_result import CampaignResult, CampaignMessage
from domain.entities.leads import Leads


@pytest.fixture
def mock_deps():
    """Create all mock dependencies for leads_router."""
    return {
        "jobs_strategy": {"jsearch": lambda loc, params: AsyncMock()},
        "repository": AsyncMock(),
        "compatibility": AsyncMock(),
        "profile_repository": AsyncMock(),
        "enrich_port": AsyncMock(),
        "message_port": AsyncMock(),
        "task_manager": AsyncMock(),
        "campaign_repository": AsyncMock(),
    }


@pytest.fixture
def app(mock_deps):
    """Create a FastAPI app with leads routes."""
    app = FastAPI()
    router = leads_router(**mock_deps)
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestGetLeadsEndpoint:
    """Test GET /leads/{type}/{offset}/{limit} endpoint."""

    def test_get_leads_success(self, client, mock_deps):
        """Should return leads data on success."""
        leads = Leads(
            companies=None, jobs=None, contacts=None, pages=0
        )

        with patch("application.api.leads_routes.GetLeadsUseCase") as mock_uc_cls:
            mock_uc = AsyncMock()
            mock_uc.get_leads.return_value = leads
            mock_uc_cls.return_value = mock_uc

            response = client.get("/leads/companies/0/5")

        assert response.status_code == 200

    def test_get_leads_error(self, client, mock_deps):
        """Should return 500 on error."""
        with patch("application.api.leads_routes.GetLeadsUseCase") as mock_uc_cls:
            mock_uc = AsyncMock()
            mock_uc.get_leads.side_effect = RuntimeError("DB error")
            mock_uc_cls.return_value = mock_uc

            response = client.get("/leads/companies/0/5")

        assert response.status_code == 500


class TestGetTaskStatusEndpoint:
    """Test GET /task/{task_id} endpoint."""

    def test_get_task_status_found(self, client, mock_deps):
        """Should return task when found."""
        task = Task(task_id="t1", message="Processing", status="processing")
        mock_deps["task_manager"].get_task_status.return_value = task

        response = client.get("/task/t1")
        assert response.status_code == 200
        assert response.json()["task_id"] == "t1"

    def test_get_task_status_not_found(self, client, mock_deps):
        """Should return 500 (wrapping 404) when task not found."""
        mock_deps["task_manager"].get_task_status.return_value = None

        response = client.get("/task/nonexistent")
        assert response.status_code == 500

    def test_get_task_status_completed_removes_task(self, client, mock_deps):
        """Should remove task when status is completed."""
        task = Task(task_id="t2", message="Done", status="completed")
        mock_deps["task_manager"].get_task_status.return_value = task

        response = client.get("/task/t2")
        assert response.status_code == 200
        mock_deps["task_manager"].remove_task.assert_called_once_with("t2")


class TestGetRunningTasksEndpoint:
    """Test GET /tasks/running endpoint."""

    def test_get_running_tasks(self, client, mock_deps):
        """Should return list of running tasks."""
        tasks = [
            Task(task_id="t1", message="Processing", status="processing"),
        ]
        mock_deps["task_manager"].get_running_tasks.return_value = tasks

        response = client.get("/tasks/running")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    def test_get_running_tasks_error(self, client, mock_deps):
        """Should return 500 on error."""
        mock_deps["task_manager"].get_running_tasks.side_effect = RuntimeError("Error")

        response = client.get("/tasks/running")
        assert response.status_code == 500


class TestGenerateMessageEndpoint:
    """Test GET /generate/message/{contact_id} endpoint."""

    def test_generate_message_success(self, client, mock_deps):
        """Should return prospect message on success."""
        from domain.entities.prospect_message import ProspectMessage

        with patch("application.api.leads_routes.GenerateMessageUseCase") as mock_uc_cls:
            mock_uc = AsyncMock()
            mock_uc.generate_message.return_value = ProspectMessage(
                subject="Hi", message="Hello"
            )
            mock_uc_cls.return_value = mock_uc

            response = client.get("/generate/message/contact-123")

        assert response.status_code == 200
        assert response.json()["subject"] == "Hi"

    def test_generate_message_error(self, client, mock_deps):
        """Should return 500 on error."""
        with patch("application.api.leads_routes.GenerateMessageUseCase") as mock_uc_cls:
            mock_uc = AsyncMock()
            mock_uc.generate_message.side_effect = RuntimeError("LLM error")
            mock_uc_cls.return_value = mock_uc

            response = client.get("/generate/message/contact-123")

        assert response.status_code == 500


class TestInsertLeadsEndpoint:
    """Test POST /insert/leads endpoint."""

    def test_insert_leads_unknown_source(self, client, mock_deps):
        """Should return 500 for unknown source."""
        response = client.post(
            "/insert/leads",
            json={"source": "unknown_source", "location": "FR", "job_params": ["Python"]},
        )
        assert response.status_code == 500

    def test_insert_leads_success(self, client, mock_deps):
        """Should return task for valid request."""
        response = client.post(
            "/insert/leads",
            json={"source": "jsearch", "location": "FR", "job_params": ["Python"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processing"
        assert "task_id" in data


class TestGetCampaignResultEndpoint:
    """Test GET /campaign/result/{task_id} endpoint."""

    def test_get_campaign_result_found(self, client, mock_deps):
        """Should return campaign result when found."""
        result = CampaignResult(
            total_contacts=5, successful=4, failed=1, messages=[]
        )
        mock_deps["task_manager"].get_result.return_value = result

        response = client.get("/campaign/result/t1")
        assert response.status_code == 200
        assert response.json()["total_contacts"] == 5

    def test_get_campaign_result_not_found(self, client, mock_deps):
        """Should return 404 when result not found."""
        mock_deps["task_manager"].get_result.return_value = None

        response = client.get("/campaign/result/t1")
        assert response.status_code == 404

    def test_get_campaign_result_wrong_type(self, client, mock_deps):
        """Should return 400 when result is not CampaignResult."""
        mock_deps["task_manager"].get_result.return_value = "not a campaign result"

        response = client.get("/campaign/result/t1")
        assert response.status_code == 400


class TestGetCampaignsEndpoint:
    """Test GET /campaigns/{offset}/{limit} endpoint."""

    def test_get_campaigns_success(self, client, mock_deps):
        """Should return campaigns list."""
        entity = CampaignEntity(
            campaigns=[Campaign(name="C1", status=CampaignStatus.COMPLETED)],
            pages=1,
        )
        mock_deps["campaign_repository"].get_campaigns.return_value = entity

        response = client.get("/campaigns/0/10")
        assert response.status_code == 200


class TestGetCampaignByIdEndpoint:
    """Test GET /campaigns/{campaign_id} endpoint."""

    def test_get_campaign_found(self, client, mock_deps):
        """Should return campaign when found."""
        campaign = Campaign(id="camp-1", name="C1", status=CampaignStatus.COMPLETED)
        mock_deps["campaign_repository"].get_campaign_by_id.return_value = campaign

        response = client.get("/campaigns/camp-1")
        assert response.status_code == 200

    def test_get_campaign_not_found(self, client, mock_deps):
        """Should return 404 when campaign not found."""
        mock_deps["campaign_repository"].get_campaign_by_id.return_value = None

        response = client.get("/campaigns/nonexistent")
        assert response.status_code == 404


class TestGetCampaignMessagesEndpoint:
    """Test GET /campaigns/{campaign_id}/messages/{offset}/{limit} endpoint."""

    def test_get_campaign_messages_success(self, client, mock_deps):
        """Should return messages list."""
        campaign = Campaign(id="camp-1", name="C1", status=CampaignStatus.COMPLETED)
        mock_deps["campaign_repository"].get_campaign_by_id.return_value = campaign
        mock_deps["campaign_repository"].get_campaign_messages.return_value = [
            CampaignMessage(
                contact_id="c1",
                subject="Hi",
                message="Hello",
            )
        ]

        response = client.get("/campaigns/camp-1/messages/0/10")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_get_campaign_messages_campaign_not_found(self, client, mock_deps):
        """Should return 404 when campaign not found."""
        mock_deps["campaign_repository"].get_campaign_by_id.return_value = None

        response = client.get("/campaigns/nonexistent/messages/0/10")
        assert response.status_code == 404


class TestGetNewContactsEndpoint:
    """Test GET /contacts/new/{offset}/{limit} endpoint."""

    def test_get_new_contacts_success(self, client, mock_deps):
        """Should return paginated contacts without messages."""
        contacts_companies = [
            (Contact(id="c1", name="Alice"), Company(id="co1", name="TechCo")),
            (Contact(id="c2", name="Bob"), Company(id="co2", name="FinCo")),
        ]
        mock_deps["campaign_repository"].get_contacts_without_messages.return_value = contacts_companies

        response = client.get("/contacts/new/0/10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["contacts"]) == 2
        assert data["pages"] == 1

    def test_get_new_contacts_error(self, client, mock_deps):
        """Should return 500 on error."""
        mock_deps["campaign_repository"].get_contacts_without_messages.side_effect = RuntimeError("DB down")

        response = client.get("/contacts/new/0/10")
        assert response.status_code == 500
