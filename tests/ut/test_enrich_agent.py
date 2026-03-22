"""
Unit tests for EnrichLeadsAgent.

Tests the agent's helper methods and orchestration logic
with mocked dependencies.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from domain.entities.company import Company, CompanyEntity
from domain.entities.contact import Contact, ContactEntity
from domain.entities.job import JobEntity
from domain.entities.leads import Leads
from domain.entities.profile import Profile
from infrastructure.services.enrich_leads_agent.agent import EnrichLeadsAgent
from infrastructure.services.task_manager import InMemoryTaskManager
from tests.ut.fakes.fake_leads_repository import FakeLeadsRepository


class TestBuildProgressMessage:
    """Tests for _build_progress_message method."""

    @pytest.fixture
    def agent(self) -> EnrichLeadsAgent:
        """Create an EnrichLeadsAgent with fakes."""
        task_manager = InMemoryTaskManager()
        leads_repo = FakeLeadsRepository()
        with patch("infrastructure.services.enrich_leads_agent.agent.EnrichLeadsNodes"):
            return EnrichLeadsAgent(task_manager, leads_repo)

    def test_build_progress_message_format(self, agent: EnrichLeadsAgent):
        """Should build a formatted progress message with all counts."""
        result = agent._build_progress_message(
            current_action="Processing: Acme Corp",
            companies_processed=2,
            companies_total=5,
            companies_saved=1,
            companies_skipped=1,
            contacts_saved=3,
            contacts_skipped=2,
        )

        assert "Processing: Acme Corp" in result
        assert "2/5" in result
        assert "1 saved" in result
        assert "1 skipped" in result
        assert "3 saved" in result
        assert "2 skipped" in result

    def test_build_progress_message_initial_state(self, agent: EnrichLeadsAgent):
        """Should handle zero counts."""
        result = agent._build_progress_message(
            current_action="Starting...",
            companies_processed=0,
            companies_total=10,
            companies_saved=0,
            companies_skipped=0,
            contacts_saved=0,
            contacts_skipped=0,
        )

        assert "Starting..." in result
        assert "0/10" in result


class TestCreateProgressCallback:
    """Tests for _create_progress_callback method."""

    @pytest.fixture
    def agent(self) -> EnrichLeadsAgent:
        """Create an EnrichLeadsAgent with fakes."""
        task_manager = InMemoryTaskManager()
        leads_repo = FakeLeadsRepository()
        with patch("infrastructure.services.enrich_leads_agent.agent.EnrichLeadsNodes"):
            return EnrichLeadsAgent(task_manager, leads_repo)

    @pytest.mark.asyncio
    async def test_callback_updates_task(self, agent: EnrichLeadsAgent):
        """Should create a callback that updates task progress."""
        task_id = "test-task-123"
        await agent.task_manager.submit_task(task_id)

        callback = agent._create_progress_callback(task_id)
        await callback("Step 1 complete")

        task = await agent.task_manager.get_task_status(task_id)
        assert task.message == "Step 1 complete"
        assert task.status == "in_progress"


class TestSaveCompanyIfNew:
    """Tests for _save_company_if_new method."""

    @pytest.fixture
    def leads_repo(self) -> FakeLeadsRepository:
        """Create a FakeLeadsRepository."""
        return FakeLeadsRepository()

    @pytest.fixture
    def agent(self, leads_repo: FakeLeadsRepository) -> EnrichLeadsAgent:
        """Create an EnrichLeadsAgent with a fake repository."""
        task_manager = InMemoryTaskManager()
        with patch("infrastructure.services.enrich_leads_agent.agent.EnrichLeadsNodes"):
            agent = EnrichLeadsAgent(task_manager, leads_repo)
            return agent

    @pytest.mark.asyncio
    async def test_save_new_company(self, agent: EnrichLeadsAgent):
        """Should save and return (True, company) for new companies."""
        company = Company(name="Acme Corp", industry="Technology")

        was_saved, saved_company = await agent._save_company_if_new(company)

        assert was_saved is True
        assert saved_company is not None
        assert saved_company.name == "Acme Corp"
        assert saved_company.id is not None

    @pytest.mark.asyncio
    async def test_skip_existing_company(self, agent: EnrichLeadsAgent, leads_repo: FakeLeadsRepository):
        """Should return (False, existing_company) for existing companies."""
        existing = await leads_repo.save_company(Company(name="Acme Corp"))

        was_saved, returned_company = await agent._save_company_if_new(
            Company(name="Acme Corp", industry="Tech")
        )

        assert was_saved is False
        assert returned_company is not None
        assert returned_company.name == "Acme Corp"

    @pytest.mark.asyncio
    async def test_company_without_name(self, agent: EnrichLeadsAgent):
        """Should return (False, None) for company without name."""
        company = Company(name=None)

        was_saved, saved_company = await agent._save_company_if_new(company)

        assert was_saved is False
        assert saved_company is None


class TestSaveContactIfNew:
    """Tests for _save_contact_if_new method."""

    @pytest.fixture
    def leads_repo(self) -> FakeLeadsRepository:
        """Create a FakeLeadsRepository."""
        return FakeLeadsRepository()

    @pytest.fixture
    def agent(self, leads_repo: FakeLeadsRepository) -> EnrichLeadsAgent:
        """Create an EnrichLeadsAgent with a fake repository."""
        task_manager = InMemoryTaskManager()
        with patch("infrastructure.services.enrich_leads_agent.agent.EnrichLeadsNodes"):
            return EnrichLeadsAgent(task_manager, leads_repo)

    @pytest.mark.asyncio
    async def test_save_new_contact_with_email(self, agent: EnrichLeadsAgent):
        """Should save contact when email is new."""
        contact = Contact(name="Marie Dupont", email=["marie@acme.com"])

        result = await agent._save_contact_if_new(contact)

        assert result is True

    @pytest.mark.asyncio
    async def test_skip_existing_contact_by_email(self, agent: EnrichLeadsAgent, leads_repo: FakeLeadsRepository):
        """Should skip contact when email already exists."""
        await leads_repo.save_contact(Contact(name="Marie Dupont", email=["marie@acme.com"]))

        result = await agent._save_contact_if_new(
            Contact(name="Marie Dupont", email=["marie@acme.com"])
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_save_contact_without_email_new(self, agent: EnrichLeadsAgent):
        """Should save contact by name+company when no email and new."""
        contact = Contact(name="Jean Martin", company_id="comp-1", email=None)

        result = await agent._save_contact_if_new(contact)

        assert result is True

    @pytest.mark.asyncio
    async def test_skip_existing_contact_by_name_and_company(
        self, agent: EnrichLeadsAgent, leads_repo: FakeLeadsRepository
    ):
        """Should skip contact when name+company already exists."""
        await leads_repo.save_contact(
            Contact(name="Jean Martin", company_id="comp-1", email=None)
        )

        result = await agent._save_contact_if_new(
            Contact(name="Jean Martin", company_id="comp-1", email=None)
        )

        assert result is False
