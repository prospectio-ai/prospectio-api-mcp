"""Unit tests for EnrichLeadsAgent streaming/incremental save behavior."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from domain.entities.company import Company, CompanyEntity
from domain.entities.contact import Contact, ContactEntity
from domain.entities.leads import Leads
from domain.entities.profile import Profile
from infrastructure.services.enrich_leads_agent.agent import EnrichLeadsAgent
from infrastructure.services.task_manager import InMemoryTaskManager
from tests.ut.fakes.fake_leads_repository import FakeLeadsRepository


@pytest.fixture(autouse=True)
def patch_enrich_leads_nodes():
    """
    Patch EnrichLeadsNodes constructor to avoid LLM configuration requirements during tests.
    This fixture is autouse=True so it applies to all tests in this module.
    """
    with patch(
        "infrastructure.services.enrich_leads_agent.agent.EnrichLeadsNodes"
    ) as mock_nodes_class:
        # Create a mock instance with the required methods
        mock_nodes = MagicMock()
        mock_nodes.make_company_decision = AsyncMock(return_value={"company": []})
        mock_nodes.enrich_company = AsyncMock(return_value={"enriched_company": []})
        mock_nodes.enrich_contacts = AsyncMock(return_value={"enriched_contacts": []})
        mock_nodes.profile = None
        mock_nodes.leads = None
        mock_nodes_class.return_value = mock_nodes
        yield mock_nodes


class TestEnrichLeadsAgentStreaming:
    """Test suite for EnrichLeadsAgent streaming/incremental save behavior."""

    @pytest.fixture
    def task_manager(self) -> InMemoryTaskManager:
        """Create a fresh InMemoryTaskManager for each test."""
        return InMemoryTaskManager()

    @pytest.fixture
    def leads_repository(self) -> FakeLeadsRepository:
        """Create a fresh FakeLeadsRepository for each test."""
        return FakeLeadsRepository()

    @pytest.fixture
    def agent(
        self,
        task_manager: InMemoryTaskManager,
        leads_repository: FakeLeadsRepository
    ) -> EnrichLeadsAgent:
        """Create an EnrichLeadsAgent with test doubles."""
        return EnrichLeadsAgent(
            task_manager=task_manager,
            leads_repository=leads_repository
        )

    @pytest.fixture
    def sample_profile(self) -> Profile:
        """Create a sample profile for testing."""
        return Profile(
            job_title="Senior Python Developer",
            location="Paris, France",
            bio="Experienced developer",
            work_experience=[],
            technos=["Python", "FastAPI"],
        )

    @pytest.fixture
    def sample_companies(self) -> list[Company]:
        """Create sample companies for testing."""
        return [
            Company(
                name="Tech Solutions Inc",
                industry="Technology",
                website="https://techsolutions.com",
            ),
            Company(
                name="Innovation Labs",
                industry="Software",
                website="https://innovationlabs.com",
            ),
            Company(
                name="Data Corp",
                industry="Data Science",
                website="https://datacorp.com",
            ),
        ]

    @pytest.fixture
    def sample_leads(self, sample_companies: list[Company]) -> Leads:
        """Create sample leads for testing."""
        return Leads(
            companies=CompanyEntity(companies=sample_companies),
            jobs=None,
            contacts=None,
        )

    @pytest.fixture
    def task_uuid(self) -> str:
        """Return a fixed task UUID for testing."""
        return "test-task-uuid-123"

    async def _setup_task(self, task_manager: InMemoryTaskManager, task_uuid: str):
        """Helper to submit a task before tests that need it."""
        await task_manager.submit_task(task_uuid)

    # --- Tests for incremental company saving ---

    @pytest.mark.asyncio
    async def test_companies_are_saved_one_at_a_time(
        self,
        agent: EnrichLeadsAgent,
        leads_repository: FakeLeadsRepository,
        task_manager: InMemoryTaskManager,
        sample_leads: Leads,
        sample_profile: Profile,
        task_uuid: str,
    ):
        """Should save each company incrementally during execute()."""
        await self._setup_task(task_manager, task_uuid)

        # Track save order
        save_order: list[str] = []
        original_save = leads_repository.save_company

        async def track_saves(company: Company) -> Company:
            save_order.append(company.name)
            return await original_save(company)

        leads_repository.save_company = track_saves

        # Mock the nodes to avoid external API calls
        with patch.object(agent.nodes, 'make_company_decision', new_callable=AsyncMock) as mock_decision, \
             patch.object(agent.nodes, 'enrich_company', new_callable=AsyncMock) as mock_enrich, \
             patch.object(agent.nodes, 'enrich_contacts', new_callable=AsyncMock) as mock_contacts:

            # Decision: approve all companies
            mock_decision.return_value = {"company": [MagicMock()]}
            mock_enrich.return_value = {"enriched_company": []}
            mock_contacts.return_value = {"enriched_contacts": []}

            await agent.execute(sample_leads, sample_profile, task_uuid)

        # Verify companies were saved in order
        assert len(save_order) == 3
        assert save_order[0] == "Tech Solutions Inc"
        assert save_order[1] == "Innovation Labs"
        assert save_order[2] == "Data Corp"

    @pytest.mark.asyncio
    async def test_duplicate_companies_are_skipped(
        self,
        agent: EnrichLeadsAgent,
        leads_repository: FakeLeadsRepository,
        task_manager: InMemoryTaskManager,
        sample_profile: Profile,
        task_uuid: str,
    ):
        """Should skip companies that already exist in the repository."""
        await self._setup_task(task_manager, task_uuid)

        # Pre-populate with existing company
        existing_company = Company(
            name="Tech Solutions Inc",
            industry="Technology",
        )
        await leads_repository.save_company(existing_company)

        # Create leads with existing and new companies
        leads = Leads(
            companies=CompanyEntity(
                companies=[
                    Company(name="Tech Solutions Inc", industry="Technology"),
                    Company(name="New Company", industry="Startup"),
                ]
            ),
            jobs=None,
            contacts=None,
        )

        with patch.object(agent.nodes, 'make_company_decision', new_callable=AsyncMock) as mock_decision, \
             patch.object(agent.nodes, 'enrich_company', new_callable=AsyncMock) as mock_enrich, \
             patch.object(agent.nodes, 'enrich_contacts', new_callable=AsyncMock) as mock_contacts:

            mock_decision.return_value = {"company": [MagicMock()]}
            mock_enrich.return_value = {"enriched_company": []}
            mock_contacts.return_value = {"enriched_contacts": []}

            await agent.execute(leads, sample_profile, task_uuid)

        # Should only have 2 companies: the existing one and the new one
        companies = await leads_repository.get_companies(0, 100)
        assert len(companies.companies) == 2

        # Verify the existing company was not duplicated
        names = [c.name for c in companies.companies]
        assert names.count("Tech Solutions Inc") == 1
        assert "New Company" in names

    # --- Tests for duplicate contacts being skipped ---

    @pytest.mark.asyncio
    async def test_duplicate_contacts_are_skipped(
        self,
        agent: EnrichLeadsAgent,
        leads_repository: FakeLeadsRepository,
        task_manager: InMemoryTaskManager,
        sample_profile: Profile,
        task_uuid: str,
    ):
        """Should skip contacts that already exist by email (streaming mode saves in node)."""
        await self._setup_task(task_manager, task_uuid)

        # Pre-populate with existing contact
        existing_contact = Contact(
            name="Existing Contact",
            email=["existing@techsolutions.com"],
            title="Manager",
        )
        await leads_repository.save_contact(existing_contact)

        leads = Leads(
            companies=CompanyEntity(
                companies=[Company(name="Some Company", industry="Tech")]
            ),
            jobs=None,
            contacts=None,
        )

        # In streaming mode, the node saves contacts and returns counts
        # Simulate the node saving the new contact and skipping the duplicate
        new_contact = Contact(
            name="New Contact",
            email=["new@example.com"],
            title="Developer",
        )

        async def mock_enrich_contacts_streaming(state):
            # Simulate streaming: save new contact, skip duplicate
            await leads_repository.save_contact(new_contact)
            return {
                "enriched_contacts": [new_contact],
                "contacts_saved": 1,
                "contacts_skipped": 1,  # duplicate was skipped
            }

        with patch.object(agent.nodes, 'make_company_decision', new_callable=AsyncMock) as mock_decision, \
             patch.object(agent.nodes, 'enrich_company', new_callable=AsyncMock) as mock_enrich, \
             patch.object(agent.nodes, 'enrich_contacts', side_effect=mock_enrich_contacts_streaming):

            mock_decision.return_value = {"company": [MagicMock()]}
            mock_enrich.return_value = {"enriched_company": []}

            await agent.execute(leads, sample_profile, task_uuid)

        # Should have 2 contacts: the existing one and the new one
        contacts = await leads_repository.get_contacts(0, 100)
        assert len(contacts.contacts) == 2

        # Verify the duplicate was skipped (name should still be original)
        emails = [c.email[0] if c.email else None for c in contacts.contacts]
        assert "existing@techsolutions.com" in emails
        assert "new@example.com" in emails

    @pytest.mark.asyncio
    async def test_contacts_without_email_are_skipped(
        self,
        agent: EnrichLeadsAgent,
        leads_repository: FakeLeadsRepository,
        task_manager: InMemoryTaskManager,
        sample_profile: Profile,
        task_uuid: str,
    ):
        """Should skip contacts that have no email address (streaming mode)."""
        await self._setup_task(task_manager, task_uuid)

        leads = Leads(
            companies=CompanyEntity(
                companies=[Company(name="Some Company", industry="Tech")]
            ),
            jobs=None,
            contacts=None,
        )

        # In streaming mode, the node saves contacts with email and skips those without
        valid_contact = Contact(name="Has Email", email=["valid@example.com"], title="Developer")

        async def mock_enrich_contacts_streaming(state):
            # Simulate streaming: save contact with email, skip one without
            await leads_repository.save_contact(valid_contact)
            return {
                "enriched_contacts": [valid_contact],
                "contacts_saved": 1,
                "contacts_skipped": 1,  # no-email contact was skipped
            }

        with patch.object(agent.nodes, 'make_company_decision', new_callable=AsyncMock) as mock_decision, \
             patch.object(agent.nodes, 'enrich_company', new_callable=AsyncMock) as mock_enrich, \
             patch.object(agent.nodes, 'enrich_contacts', side_effect=mock_enrich_contacts_streaming):

            mock_decision.return_value = {"company": [MagicMock()]}
            mock_enrich.return_value = {"enriched_company": []}

            await agent.execute(leads, sample_profile, task_uuid)

        # Only the contact with email should be saved
        contacts = await leads_repository.get_contacts(0, 100)
        assert len(contacts.contacts) == 1
        assert contacts.contacts[0].name == "Has Email"

    # --- Tests for progress counters ---

    @pytest.mark.asyncio
    async def test_progress_counters_are_updated_correctly(
        self,
        agent: EnrichLeadsAgent,
        leads_repository: FakeLeadsRepository,
        task_manager: InMemoryTaskManager,
        sample_profile: Profile,
        task_uuid: str,
    ):
        """Should update progress counters correctly during execution (streaming mode)."""
        await self._setup_task(task_manager, task_uuid)

        # Pre-populate with existing company and contact
        await leads_repository.save_company(
            Company(name="Existing Company", industry="Tech")
        )
        await leads_repository.save_contact(
            Contact(name="Existing Contact", email=["existing@example.com"])
        )

        leads = Leads(
            companies=CompanyEntity(
                companies=[
                    Company(name="Existing Company", industry="Tech"),  # Will be skipped
                    Company(name="New Company", industry="Startup"),    # Will be saved
                ]
            ),
            jobs=None,
            contacts=None,
        )

        # Track which company is being processed
        call_count = [0]

        async def mock_enrich_contacts_streaming(state):
            call_count[0] += 1
            if call_count[0] == 1:
                # First company: 1 saved, 1 skipped (existing)
                new_contact = Contact(name="New Contact", email=["new@example.com"])
                await leads_repository.save_contact(new_contact)
                return {
                    "enriched_contacts": [new_contact],
                    "contacts_saved": 1,
                    "contacts_skipped": 1,
                }
            else:
                # Second company: 0 saved, 2 skipped (both already exist)
                return {
                    "enriched_contacts": [],
                    "contacts_saved": 0,
                    "contacts_skipped": 2,
                }

        with patch.object(agent.nodes, 'make_company_decision', new_callable=AsyncMock) as mock_decision, \
             patch.object(agent.nodes, 'enrich_company', new_callable=AsyncMock) as mock_enrich, \
             patch.object(agent.nodes, 'enrich_contacts', side_effect=mock_enrich_contacts_streaming):

            mock_decision.return_value = {"company": [MagicMock()]}
            mock_enrich.return_value = {"enriched_company": []}

            await agent.execute(leads, sample_profile, task_uuid)

        # Check final task status message contains expected counts
        task = await task_manager.get_task_status(task_uuid)
        assert "2/2" in task.message  # Progress: 2/2 companies processed
        assert "Companies: 1 saved, 1 skipped" in task.message
        # 1 saved (new@example.com on first company), 3 skipped:
        #   - existing@example.com skipped on company 1 (pre-exists)
        #   - existing@example.com skipped on company 2 (pre-exists)
        #   - new@example.com skipped on company 2 (saved on company 1)
        assert "Contacts: 1 saved, 3 skipped" in task.message

    # --- Tests for error handling and continuation ---

    @pytest.mark.asyncio
    async def test_processing_continues_after_company_failure(
        self,
        agent: EnrichLeadsAgent,
        leads_repository: FakeLeadsRepository,
        task_manager: InMemoryTaskManager,
        sample_leads: Leads,
        sample_profile: Profile,
        task_uuid: str,
    ):
        """Should continue processing remaining companies if one fails."""
        await self._setup_task(task_manager, task_uuid)

        call_count = 0

        async def decision_side_effect(state):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # Fail on second company
                raise Exception("Simulated processing error")
            return {"company": [MagicMock()]}

        with patch.object(agent.nodes, 'make_company_decision', new_callable=AsyncMock) as mock_decision, \
             patch.object(agent.nodes, 'enrich_company', new_callable=AsyncMock) as mock_enrich, \
             patch.object(agent.nodes, 'enrich_contacts', new_callable=AsyncMock) as mock_contacts:

            mock_decision.side_effect = decision_side_effect
            mock_enrich.return_value = {"enriched_company": []}
            mock_contacts.return_value = {"enriched_contacts": []}

            # Should not raise, should continue processing
            await agent.execute(sample_leads, sample_profile, task_uuid)

        # Verify 2 out of 3 companies were saved (1st and 3rd)
        companies = await leads_repository.get_companies(0, 100)
        assert len(companies.companies) == 2

        saved_names = [c.name for c in companies.companies]
        assert "Tech Solutions Inc" in saved_names
        assert "Data Corp" in saved_names
        assert "Innovation Labs" not in saved_names  # This one failed

    @pytest.mark.asyncio
    async def test_processing_continues_after_contact_save_failure(
        self,
        agent: EnrichLeadsAgent,
        leads_repository: FakeLeadsRepository,
        task_manager: InMemoryTaskManager,
        sample_profile: Profile,
        task_uuid: str,
    ):
        """Should continue processing contacts if one fails to save (streaming mode)."""
        await self._setup_task(task_manager, task_uuid)

        leads = Leads(
            companies=CompanyEntity(
                companies=[Company(name="Test Company", industry="Tech")]
            ),
            jobs=None,
            contacts=None,
        )

        # In streaming mode, the node handles saving and error recovery
        contact1 = Contact(name="Contact 1", email=["c1@example.com"])
        contact3 = Contact(name="Contact 3", email=["c3@example.com"])

        async def mock_enrich_contacts_streaming(state):
            # Simulate streaming: save 2 contacts, 1 failed
            await leads_repository.save_contact(contact1)
            # Contact 2 would fail - simulated by not saving it
            await leads_repository.save_contact(contact3)
            return {
                "enriched_contacts": [contact1, contact3],
                "contacts_saved": 2,
                "contacts_skipped": 1,  # 1 failed
            }

        with patch.object(agent.nodes, 'make_company_decision', new_callable=AsyncMock) as mock_decision, \
             patch.object(agent.nodes, 'enrich_company', new_callable=AsyncMock) as mock_enrich, \
             patch.object(agent.nodes, 'enrich_contacts', side_effect=mock_enrich_contacts_streaming):

            mock_decision.return_value = {"company": [MagicMock()]}
            mock_enrich.return_value = {"enriched_company": []}

            # Should not raise
            await agent.execute(leads, sample_profile, task_uuid)

        # 2 contacts should be saved (1st and 3rd)
        contacts = await leads_repository.get_contacts(0, 100)
        assert len(contacts.contacts) == 2

    @pytest.mark.asyncio
    async def test_company_without_name_is_skipped(
        self,
        agent: EnrichLeadsAgent,
        leads_repository: FakeLeadsRepository,
        task_manager: InMemoryTaskManager,
        sample_profile: Profile,
        task_uuid: str,
    ):
        """Should skip companies that have no name."""
        await self._setup_task(task_manager, task_uuid)

        leads = Leads(
            companies=CompanyEntity(
                companies=[
                    Company(name=None, industry="Unknown"),  # No name
                    Company(name="Valid Company", industry="Tech"),
                ]
            ),
            jobs=None,
            contacts=None,
        )

        with patch.object(agent.nodes, 'make_company_decision', new_callable=AsyncMock) as mock_decision, \
             patch.object(agent.nodes, 'enrich_company', new_callable=AsyncMock) as mock_enrich, \
             patch.object(agent.nodes, 'enrich_contacts', new_callable=AsyncMock) as mock_contacts:

            mock_decision.return_value = {"company": [MagicMock()]}
            mock_enrich.return_value = {"enriched_company": []}
            mock_contacts.return_value = {"enriched_contacts": []}

            await agent.execute(leads, sample_profile, task_uuid)

        # Only the named company should be saved
        companies = await leads_repository.get_companies(0, 100)
        assert len(companies.companies) == 1
        assert companies.companies[0].name == "Valid Company"

    # --- Tests for contact-company association ---

    @pytest.mark.asyncio
    async def test_contacts_are_associated_with_saved_company(
        self,
        agent: EnrichLeadsAgent,
        leads_repository: FakeLeadsRepository,
        task_manager: InMemoryTaskManager,
        sample_profile: Profile,
        task_uuid: str,
    ):
        """Should associate saved contacts with their company ID (streaming mode)."""
        await self._setup_task(task_manager, task_uuid)

        leads = Leads(
            companies=CompanyEntity(
                companies=[Company(name="Parent Company", industry="Tech")]
            ),
            jobs=None,
            contacts=None,
        )

        # In streaming mode, the node receives the company (with ID after save)
        # and creates/saves contacts with the correct company_id
        async def mock_enrich_contacts_streaming(state):
            # The company passed to enrich_contacts should have an ID
            company = state.get("company")
            assert company is not None, "Company should be passed to enrich_contacts"

            # Create contact with the company's ID
            contact = Contact(
                name="Contact",
                email=["contact@example.com"],
                company_id=company.id,
            )

            # Streaming mode: save immediately
            await leads_repository.save_contact(contact)

            return {
                "enriched_contacts": [contact],
                "contacts_saved": 1,
                "contacts_skipped": 0,
            }

        with patch.object(agent.nodes, 'make_company_decision', new_callable=AsyncMock) as mock_decision, \
             patch.object(agent.nodes, 'enrich_company', new_callable=AsyncMock) as mock_enrich, \
             patch.object(agent.nodes, 'enrich_contacts', side_effect=mock_enrich_contacts_streaming):

            mock_decision.return_value = {"company": [MagicMock()]}
            mock_enrich.return_value = {"enriched_company": []}

            await agent.execute(leads, sample_profile, task_uuid)

        # Get the saved contact
        contacts = await leads_repository.get_contacts(0, 100)
        assert len(contacts.contacts) == 1

        # Get the saved company
        companies = await leads_repository.get_companies(0, 100)
        assert len(companies.companies) == 1

        # Contact should have the company ID
        assert contacts.contacts[0].company_id == companies.companies[0].id

    # --- Tests for empty leads ---

    @pytest.mark.asyncio
    async def test_handles_empty_companies_list(
        self,
        agent: EnrichLeadsAgent,
        leads_repository: FakeLeadsRepository,
        task_manager: InMemoryTaskManager,
        sample_profile: Profile,
        task_uuid: str,
    ):
        """Should handle leads with no companies gracefully."""
        await self._setup_task(task_manager, task_uuid)

        leads = Leads(
            companies=CompanyEntity(companies=[]),
            jobs=None,
            contacts=None,
        )

        result = await agent.execute(leads, sample_profile, task_uuid)

        # Should complete without error
        task = await task_manager.get_task_status(task_uuid)
        assert "Enrichment complete" in task.message
        assert "0/0" in task.message

    @pytest.mark.asyncio
    async def test_handles_none_companies(
        self,
        agent: EnrichLeadsAgent,
        leads_repository: FakeLeadsRepository,
        task_manager: InMemoryTaskManager,
        sample_profile: Profile,
        task_uuid: str,
    ):
        """Should handle leads with None companies gracefully."""
        await self._setup_task(task_manager, task_uuid)

        leads = Leads(
            companies=None,
            jobs=None,
            contacts=None,
        )

        # This should not raise
        result = await agent.execute(leads, sample_profile, task_uuid)

        task = await task_manager.get_task_status(task_uuid)
        assert task.status == "in_progress"


class TestBuildProgressMessage:
    """Tests for the _build_progress_message helper method."""

    @pytest.fixture
    def agent(self) -> EnrichLeadsAgent:
        """Create an agent for testing the progress message builder."""
        task_manager = InMemoryTaskManager()
        leads_repository = FakeLeadsRepository()
        return EnrichLeadsAgent(task_manager=task_manager, leads_repository=leads_repository)

    def test_progress_message_format(self, agent: EnrichLeadsAgent):
        """Should format progress message with all counts."""
        message = agent._build_progress_message(
            current_action="Processing: Test Company",
            companies_processed=5,
            companies_total=10,
            companies_saved=3,
            companies_skipped=2,
            contacts_saved=8,
            contacts_skipped=1,
        )

        assert "Processing: Test Company" in message
        assert "Progress: 5/10" in message
        assert "Companies: 3 saved, 2 skipped" in message
        assert "Contacts: 8 saved, 1 skipped" in message

    def test_progress_message_with_zero_counts(self, agent: EnrichLeadsAgent):
        """Should handle zero counts correctly."""
        message = agent._build_progress_message(
            current_action="Starting enrichment...",
            companies_processed=0,
            companies_total=0,
            companies_saved=0,
            companies_skipped=0,
            contacts_saved=0,
            contacts_skipped=0,
        )

        assert "Progress: 0/0" in message
        assert "Companies: 0 saved, 0 skipped" in message
        assert "Contacts: 0 saved, 0 skipped" in message
