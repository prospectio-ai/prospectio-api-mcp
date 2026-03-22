"""
Unit tests for EnrichLeadsNodes.

Tests the node methods used in the enrichment graph,
including parsing, task creation, aggregation, and enrichment helpers.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from domain.entities.company import Company, CompanyEntity
from domain.entities.contact import Contact, ContactEntity
from domain.entities.job import JobEntity
from domain.entities.leads import Leads
from domain.entities.profile import Profile
from infrastructure.services.enrich_leads_agent.models.contact_info import ContactInfo
from infrastructure.services.enrich_leads_agent.models.contact_bio import ContactBio
from infrastructure.services.enrich_leads_agent.models.make_decision import MakeDecisionResult
from infrastructure.services.enrich_leads_agent.models.web_search_models import WebSearchResult
from infrastructure.services.enrich_leads_agent.tools.duckduckgo_client import LinkedInSearchResult


def _create_nodes():
    """Create an EnrichLeadsNodes instance with fully mocked init dependencies."""
    with patch("infrastructure.services.enrich_leads_agent.nodes.caching_resolver"), \
         patch("infrastructure.services.enrich_leads_agent.nodes.LLMClientFactory") as mock_factory, \
         patch("infrastructure.services.enrich_leads_agent.nodes.WebSearchClient") as mock_ws, \
         patch("infrastructure.services.enrich_leads_agent.nodes.DuckDuckGoClient") as mock_ddg, \
         patch("infrastructure.services.enrich_leads_agent.nodes.DecisionChain") as mock_dc, \
         patch("infrastructure.services.enrich_leads_agent.nodes.EnrichChain") as mock_ec, \
         patch("infrastructure.services.enrich_leads_agent.nodes.ContactValidator") as mock_cv, \
         patch("infrastructure.services.enrich_leads_agent.nodes.LLMConfig"), \
         patch("infrastructure.services.enrich_leads_agent.nodes.WebSearchConfig"), \
         patch("infrastructure.services.enrich_leads_agent.nodes.DuckDuckGoConfig"):
        mock_factory.return_value.create_client.return_value = MagicMock()
        from infrastructure.services.enrich_leads_agent.nodes import EnrichLeadsNodes
        return EnrichLeadsNodes()


class TestParseNameMethod:
    """Tests for _parse_name method."""

    @pytest.fixture
    def nodes(self):
        return _create_nodes()

    def test_empty_name(self, nodes):
        """Should return empty strings for empty name."""
        first, last = nodes._parse_name("")
        assert first == ""
        assert last == ""

    def test_single_name(self, nodes):
        """Should return single name as first name, empty last name."""
        first, last = nodes._parse_name("Marie")
        assert first == "Marie"
        assert last == ""

    def test_two_part_name(self, nodes):
        """Should split into first and last name."""
        first, last = nodes._parse_name("Marie Dupont")
        assert first == "Marie"
        assert last == "Dupont"

    def test_three_part_name(self, nodes):
        """Should take first part as first name, rest as last name."""
        first, last = nodes._parse_name("Jean Pierre Dupont")
        assert first == "Jean"
        assert last == "Pierre Dupont"

    def test_name_with_extra_spaces(self, nodes):
        """Should handle names with extra whitespace."""
        first, last = nodes._parse_name("  Marie   Dupont  ")
        assert first == "Marie"
        assert last == "Dupont"


class TestFirstStep:
    """Tests for first_step method."""

    @pytest.fixture
    def nodes(self):
        return _create_nodes()

    def test_first_step_initializes_state(self, nodes):
        """Should initialize state with analysis step and store profile/leads."""
        profile = Profile(job_title="Dev", location="Paris", bio="Test", work_experience=[])
        leads = Leads(
            companies=CompanyEntity(companies=[]),
            contacts=ContactEntity(contacts=[]),
            jobs=JobEntity(jobs=[]),
        )
        state = {"profile": profile, "leads": leads, "step": []}

        result = nodes.first_step(state)

        assert result["step"] == ["Analysis of the lead's data."]
        assert nodes.profile == profile
        assert nodes.leads == leads


class TestCreateEnrichCompaniesTasks:
    """Tests for create_enrich_companies_tasks method."""

    @pytest.fixture
    def nodes(self):
        return _create_nodes()

    def test_creates_tasks_for_companies(self, nodes):
        """Should create one Send task per company."""
        companies = [
            Company(id="c1", name="Acme"),
            Company(id="c2", name="Beta Corp"),
        ]
        leads = Leads(
            companies=CompanyEntity(companies=companies),
            contacts=ContactEntity(contacts=[]),
            jobs=JobEntity(jobs=[]),
        )
        state = {"leads": leads, "step": []}

        result = nodes.create_enrich_companies_tasks(state)

        assert len(result["companies_tasks"]) == 2

    def test_empty_companies_returns_empty_list(self, nodes):
        """Should return empty list when no companies."""
        leads = Leads(
            companies=CompanyEntity(companies=[]),
            contacts=ContactEntity(contacts=[]),
            jobs=JobEntity(jobs=[]),
        )
        state = {"leads": leads, "step": []}

        result = nodes.create_enrich_companies_tasks(state)

        assert result["companies_tasks"] == []

    def test_none_companies_returns_empty_list(self, nodes):
        """Should return empty list when companies is None."""
        leads = Leads(
            companies=None,
            contacts=ContactEntity(contacts=[]),
            jobs=JobEntity(jobs=[]),
        )
        state = {"leads": leads, "step": []}

        result = nodes.create_enrich_companies_tasks(state)

        assert result["companies_tasks"] == []


class TestCreateEnrichContactsTasks:
    """Tests for create_enrich_contacts_tasks method."""

    @pytest.fixture
    def nodes(self):
        return _create_nodes()

    def test_creates_contact_tasks_for_companies(self, nodes):
        """Should create one Send task per company for contact enrichment."""
        companies = [Company(id="c1", name="Acme")]
        leads = Leads(
            companies=CompanyEntity(companies=companies),
            contacts=ContactEntity(contacts=[]),
            jobs=JobEntity(jobs=[]),
        )
        state = {"leads": leads, "step": []}

        result = nodes.create_enrich_contacts_tasks(state)

        assert len(result["contacts_tasks"]) == 1

    def test_empty_companies_returns_empty_contacts_tasks(self, nodes):
        """Should return empty list when no companies exist."""
        leads = Leads(
            companies=None,
            contacts=ContactEntity(contacts=[]),
            jobs=JobEntity(jobs=[]),
        )
        state = {"leads": leads, "step": []}

        result = nodes.create_enrich_contacts_tasks(state)

        assert result["contacts_tasks"] == []


class TestReportProgress:
    """Tests for _report_progress method."""

    @pytest.fixture
    def nodes(self):
        return _create_nodes()

    @pytest.mark.asyncio
    async def test_report_progress_with_callback(self, nodes):
        """Should call progress callback when set."""
        callback = AsyncMock()
        nodes.progress_callback = callback

        await nodes._report_progress("Processing step 1")

        callback.assert_awaited_once_with("Processing step 1")

    @pytest.mark.asyncio
    async def test_report_progress_without_callback(self, nodes):
        """Should do nothing when no callback is set."""
        nodes.progress_callback = None
        # Should not raise
        await nodes._report_progress("Processing step 1")


class TestSaveContactImmediately:
    """Tests for _save_contact_immediately method."""

    @pytest.fixture
    def nodes(self):
        return _create_nodes()

    @pytest.mark.asyncio
    async def test_no_repository_returns_false(self, nodes):
        """Should return False when no leads_repository is set."""
        nodes.leads_repository = None
        contact = Contact(name="Marie Dupont", email=["marie@acme.com"])

        result = await nodes._save_contact_immediately(contact)

        assert result is False

    @pytest.mark.asyncio
    async def test_save_new_contact_with_email(self, nodes):
        """Should save contact and return True when email is new."""
        mock_repo = AsyncMock()
        mock_repo.contact_exists_by_email.return_value = False
        mock_repo.save_contact.return_value = Contact(
            id="saved-123", name="Marie Dupont", email=["marie@acme.com"]
        )
        nodes.leads_repository = mock_repo
        contact = Contact(name="Marie Dupont", email=["marie@acme.com"])

        result = await nodes._save_contact_immediately(contact)

        assert result is True
        mock_repo.save_contact.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skip_duplicate_by_email(self, nodes):
        """Should return False when contact email already exists."""
        mock_repo = AsyncMock()
        mock_repo.contact_exists_by_email.return_value = True
        nodes.leads_repository = mock_repo
        contact = Contact(name="Marie Dupont", email=["marie@acme.com"])

        result = await nodes._save_contact_immediately(contact)

        assert result is False
        mock_repo.save_contact.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_save_contact_without_email_checks_name(self, nodes):
        """Should check by name and company when no email."""
        mock_repo = AsyncMock()
        mock_repo.contact_exists_by_name_and_company.return_value = False
        mock_repo.save_contact.return_value = Contact(
            id="saved-456", name="Jean Martin", company_id="comp-1"
        )
        nodes.leads_repository = mock_repo
        contact = Contact(name="Jean Martin", company_id="comp-1", email=None)

        result = await nodes._save_contact_immediately(contact)

        assert result is True
        mock_repo.contact_exists_by_name_and_company.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skip_duplicate_by_name_and_company(self, nodes):
        """Should return False when contact name+company already exists."""
        mock_repo = AsyncMock()
        mock_repo.contact_exists_by_name_and_company.return_value = True
        nodes.leads_repository = mock_repo
        contact = Contact(name="Jean Martin", company_id="comp-1", email=None)

        result = await nodes._save_contact_immediately(contact)

        assert result is False

    @pytest.mark.asyncio
    async def test_save_error_returns_false(self, nodes):
        """Should return False when save raises an exception."""
        mock_repo = AsyncMock()
        mock_repo.contact_exists_by_email.return_value = False
        mock_repo.save_contact.side_effect = Exception("DB error")
        nodes.leads_repository = mock_repo
        contact = Contact(name="Error Case", email=["error@test.com"])

        result = await nodes._save_contact_immediately(contact)

        assert result is False


class TestGetLinkedInUrlsFromDuckDuckGo:
    """Tests for _get_linkedin_urls_from_duckduckgo method."""

    @pytest.fixture
    def nodes(self):
        return _create_nodes()

    @pytest.mark.asyncio
    async def test_successful_search_returns_urls(self, nodes):
        """Should return URLs when DuckDuckGo finds LinkedIn profiles."""
        nodes.duckduckgo_client = AsyncMock()
        nodes.duckduckgo_client.search_with_fallback.return_value = LinkedInSearchResult(
            urls=["https://linkedin.com/in/marie-dupont"],
            query="Marie Dupont CTO Acme",
            success=True,
        )
        contact_info = ContactInfo(
            name="Marie Dupont", title="CTO", email=[], phone="", profile_url=[]
        )

        result = await nodes._get_linkedin_urls_from_duckduckgo(contact_info, "Acme Corp")

        assert result == ["https://linkedin.com/in/marie-dupont"]

    @pytest.mark.asyncio
    async def test_no_results_returns_empty_list(self, nodes):
        """Should return empty list when no URLs found."""
        nodes.duckduckgo_client = AsyncMock()
        nodes.duckduckgo_client.search_with_fallback.return_value = LinkedInSearchResult(
            urls=[],
            query="Unknown Person",
            success=True,
        )
        contact_info = ContactInfo(
            name="Unknown Person", title="Unknown", email=[], phone="", profile_url=[]
        )

        result = await nodes._get_linkedin_urls_from_duckduckgo(contact_info, "Unknown Corp")

        assert result == []

    @pytest.mark.asyncio
    async def test_error_returns_empty_list(self, nodes):
        """Should return empty list when DuckDuckGo raises an exception."""
        nodes.duckduckgo_client = AsyncMock()
        nodes.duckduckgo_client.search_with_fallback.side_effect = Exception("Network error")
        contact_info = ContactInfo(
            name="Marie", title="CTO", email=[], phone="", profile_url=[]
        )

        result = await nodes._get_linkedin_urls_from_duckduckgo(contact_info, "Acme")

        assert result == []


class TestEnrichContactBio:
    """Tests for _enrich_contact_bio method."""

    @pytest.fixture
    def nodes(self):
        return _create_nodes()

    @pytest.mark.asyncio
    async def test_empty_name_returns_none(self, nodes):
        """Should return None when contact has empty name."""
        nodes.progress_callback = None
        contact_info = ContactInfo(
            name="", title="CTO", email=[], phone="", profile_url=[]
        )

        short, full = await nodes._enrich_contact_bio(contact_info, "Acme")

        assert short is None
        assert full is None

    @pytest.mark.asyncio
    async def test_no_bio_search_results_returns_none(self, nodes):
        """Should return None when web search returns no answer."""
        nodes.progress_callback = None
        nodes.web_search_client = AsyncMock()
        nodes.web_search_client.search_contact_bio.return_value = WebSearchResult(answer="")
        contact_info = ContactInfo(
            name="Marie Dupont", title="CTO", email=[], phone="", profile_url=[]
        )

        short, full = await nodes._enrich_contact_bio(contact_info, "Acme")

        assert short is None
        assert full is None

    @pytest.mark.asyncio
    async def test_no_bio_extracted_returns_none(self, nodes):
        """Should return None when enrich_chain returns no bio."""
        nodes.progress_callback = None
        nodes.web_search_client = AsyncMock()
        nodes.web_search_client.search_contact_bio.return_value = WebSearchResult(
            answer="Some search results"
        )
        nodes.enrich_chain = AsyncMock()
        nodes.enrich_chain.extract_contact_bio.return_value = None
        contact_info = ContactInfo(
            name="Marie Dupont", title="CTO", email=[], phone="", profile_url=[]
        )

        short, full = await nodes._enrich_contact_bio(contact_info, "Acme")

        assert short is None
        assert full is None

    @pytest.mark.asyncio
    async def test_successful_bio_extraction(self, nodes):
        """Should return short_description and full_bio on success."""
        nodes.progress_callback = None
        nodes.web_search_client = AsyncMock()
        nodes.web_search_client.search_contact_bio.return_value = WebSearchResult(
            answer="Marie Dupont is a tech leader..."
        )
        nodes.enrich_chain = AsyncMock()
        nodes.enrich_chain.extract_contact_bio.return_value = ContactBio(
            short_description="Experienced tech leader",
            full_bio="Marie Dupont has over 15 years of experience...",
        )
        contact_info = ContactInfo(
            name="Marie Dupont", title="CTO", email=[], phone="", profile_url=[]
        )

        short, full = await nodes._enrich_contact_bio(contact_info, "Acme")

        assert short == "Experienced tech leader"
        assert full == "Marie Dupont has over 15 years of experience..."

    @pytest.mark.asyncio
    async def test_truncates_long_short_description(self, nodes):
        """Should truncate short_description to 255 chars when bio is returned with a long description."""
        nodes.progress_callback = None
        nodes.web_search_client = AsyncMock()
        nodes.web_search_client.search_contact_bio.return_value = WebSearchResult(
            answer="Some results"
        )
        # Use a MagicMock to bypass pydantic validation for the ContactBio
        # (in reality, the LLM might return a longer string before validation)
        mock_bio = MagicMock()
        mock_bio.short_description = "A" * 300
        mock_bio.full_bio = "Full bio"
        nodes.enrich_chain = AsyncMock()
        nodes.enrich_chain.extract_contact_bio.return_value = mock_bio
        contact_info = ContactInfo(
            name="Marie Dupont", title="CTO", email=[], phone="", profile_url=[]
        )

        short, full = await nodes._enrich_contact_bio(contact_info, "Acme")

        assert len(short) == 255


class TestAggregate:
    """Tests for aggregate method."""

    @pytest.fixture
    def nodes(self):
        return _create_nodes()

    def test_aggregate_with_contacts(self, nodes):
        """Should aggregate enriched contacts into leads."""
        contacts = [Contact(name="Marie"), Contact(name="Jean")]
        state = {
            "enriched_contacts": contacts,
            "step": [],
        }

        result = nodes.aggregate(state)

        assert result["step"] == ["Aggregated enriched data into leads."]
        assert nodes.leads.contacts.contacts == contacts

    def test_aggregate_with_companies(self, nodes):
        """Should aggregate enriched companies into leads."""
        companies = [Company(name="Acme"), Company(name="Beta")]
        state = {
            "enriched_company": companies,
            "step": [],
        }

        result = nodes.aggregate(state)

        assert result["step"] == ["Aggregated enriched data into leads."]
        assert nodes.leads.companies.companies == companies

    def test_aggregate_empty_companies_with_contacts(self, nodes):
        """Should handle empty enriched_company list when contacts are also present."""
        contacts = [Contact(name="Marie")]
        state = {
            "enriched_contacts": contacts,
            "enriched_company": [],
            "step": [],
        }

        result = nodes.aggregate(state)

        assert result["step"] == ["Aggregated enriched data into leads."]

    def test_aggregate_with_contacts_and_companies(self, nodes):
        """Should aggregate both enriched contacts and companies."""
        contacts = [Contact(name="Marie")]
        companies = [Company(name="Acme")]
        state = {
            "enriched_contacts": contacts,
            "enriched_company": companies,
            "step": [],
        }

        result = nodes.aggregate(state)

        assert result["step"] == ["Aggregated enriched data into leads."]
        assert nodes.leads.contacts.contacts == contacts
        assert nodes.leads.companies.companies == companies


class TestMakeCompanyDecision:
    """Tests for make_company_decision method."""

    @pytest.fixture
    def nodes(self):
        return _create_nodes()

    @pytest.mark.asyncio
    async def test_approved_company(self, nodes):
        """Should keep company in state when decision is True."""
        nodes.progress_callback = None
        nodes.decision_chain = AsyncMock()
        nodes.decision_chain.decide_enrichment.return_value = MakeDecisionResult(result=True)
        company = Company(id="c1", name="Acme Corp")
        state = {"company": company, "step": []}

        result = await nodes.make_company_decision(state)

        assert result["company"] == [company]

    @pytest.mark.asyncio
    async def test_rejected_company(self, nodes):
        """Should empty company list when decision is False."""
        nodes.progress_callback = None
        nodes.decision_chain = AsyncMock()
        nodes.decision_chain.decide_enrichment.return_value = MakeDecisionResult(result=False)
        company = Company(id="c1", name="Irrelevant Corp")
        state = {"company": company, "step": []}

        result = await nodes.make_company_decision(state)

        assert result["company"] == []


class TestEnrichContacts:
    """Tests for enrich_contacts method."""

    @pytest.fixture
    def nodes(self):
        return _create_nodes()

    @pytest.mark.asyncio
    async def test_enrich_contacts_no_job_titles(self, nodes):
        """Should return empty contacts when no job titles are extracted."""
        nodes.progress_callback = None
        nodes.enrich_chain = AsyncMock()
        nodes.enrich_chain.extract_interesting_job_titles_from_profile.return_value = []

        company = Company(id="c1", name="Acme Corp")
        state = {"company": company, "step": []}

        result = await nodes.enrich_contacts(state)

        assert result["enriched_contacts"] == []
        assert result["contacts_saved"] == 0
        assert result["contacts_skipped"] == 0

    @pytest.mark.asyncio
    async def test_enrich_contacts_no_search_results(self, nodes):
        """Should handle case where web search returns no answer."""
        nodes.progress_callback = None
        nodes.enrich_chain = AsyncMock()
        nodes.enrich_chain.extract_interesting_job_titles_from_profile.return_value = ["CTO"]
        nodes.web_search_client = AsyncMock()
        nodes.web_search_client.search_company_contacts.return_value = WebSearchResult(answer="")

        company = Company(id="c1", name="Acme Corp")
        state = {"company": company, "step": []}

        result = await nodes.enrich_contacts(state)

        assert result["enriched_contacts"] == []
        assert result["contacts_saved"] == 0

    @pytest.mark.asyncio
    async def test_enrich_contacts_with_contact_found(self, nodes):
        """Should process contacts when found in search results."""
        nodes.progress_callback = None
        nodes.leads_repository = None  # batch mode

        nodes.enrich_chain = AsyncMock()
        nodes.enrich_chain.extract_interesting_job_titles_from_profile.return_value = ["CTO"]
        nodes.enrich_chain.extract_contacts_from_answer.return_value = [
            ContactInfo(
                name="Marie Dupont",
                email=["marie@acme.com"],
                title="CTO",
                phone="+33612345678",
                profile_url=[],
            )
        ]
        nodes.enrich_chain.extract_contact_bio.return_value = ContactBio(
            short_description="Tech leader",
            full_bio="Marie is a tech leader with 15 years of experience.",
        )

        nodes.web_search_client = AsyncMock()
        nodes.web_search_client.search_company_contacts.return_value = WebSearchResult(
            answer="Marie Dupont is the CTO at Acme Corp."
        )
        nodes.web_search_client.search_contact_bio.return_value = WebSearchResult(
            answer="Marie Dupont bio info."
        )

        nodes.duckduckgo_client = AsyncMock()
        nodes.duckduckgo_client.search_with_fallback.return_value = LinkedInSearchResult(
            urls=["https://linkedin.com/in/marie-dupont"],
            query="Marie Dupont CTO Acme Corp",
            success=True,
        )

        from infrastructure.services.enrich_leads_agent.validators.contact_validator import ContactValidator
        from unittest.mock import MagicMock as MM
        mock_validation = MM()
        mock_validation.confidence_score = 80
        mock_validation.validation_status.value = "verified"
        mock_validation.validation_reasons = ["Email matches domain"]
        nodes.contact_validator = MM()
        nodes.contact_validator.validate_contact.return_value = mock_validation

        # Mock the email validator to avoid DNS lookups
        with patch("infrastructure.services.enrich_leads_agent.nodes.validate_email") as mock_validate:
            mock_validate.return_value.email = "marie@acme.com"

            company = Company(id="c1", name="Acme Corp")
            state = {"company": company, "step": []}

            result = await nodes.enrich_contacts(state)

        assert len(result["enriched_contacts"]) == 1
        assert result["enriched_contacts"][0].name == "Marie Dupont"
        assert result["enriched_contacts"][0].email == ["marie@acme.com"]
        assert result["enriched_contacts"][0].profile_url == "https://linkedin.com/in/marie-dupont"

    @pytest.mark.asyncio
    async def test_enrich_contacts_dedup_in_memory(self, nodes):
        """Should skip duplicate contacts within the same run."""
        nodes.progress_callback = None
        nodes.leads_repository = None

        nodes.enrich_chain = AsyncMock()
        nodes.enrich_chain.extract_interesting_job_titles_from_profile.return_value = ["CTO", "VP"]
        # Return the same contact for both job titles
        nodes.enrich_chain.extract_contacts_from_answer.return_value = [
            ContactInfo(
                name="Marie Dupont",
                email=["marie@acme.com"],
                title="CTO",
                phone="+33612345678",
                profile_url=[],
            )
        ]
        nodes.enrich_chain.extract_contact_bio.return_value = ContactBio(
            short_description="Leader",
            full_bio="Full bio",
        )
        nodes.web_search_client = AsyncMock()
        nodes.web_search_client.search_company_contacts.return_value = WebSearchResult(
            answer="Marie Dupont is the CTO"
        )
        nodes.web_search_client.search_contact_bio.return_value = WebSearchResult(
            answer="Bio info"
        )
        nodes.duckduckgo_client = AsyncMock()
        nodes.duckduckgo_client.search_with_fallback.return_value = LinkedInSearchResult(
            urls=[], query="", success=True
        )

        mock_validation = MagicMock()
        mock_validation.confidence_score = 80
        mock_validation.validation_status.value = "verified"
        mock_validation.validation_reasons = []
        nodes.contact_validator = MagicMock()
        nodes.contact_validator.validate_contact.return_value = mock_validation

        with patch("infrastructure.services.enrich_leads_agent.nodes.validate_email") as mock_validate:
            mock_validate.return_value.email = "marie@acme.com"

            company = Company(id="c1", name="Acme Corp")
            state = {"company": company, "step": []}

            result = await nodes.enrich_contacts(state)

        # Should only process one contact due to deduplication
        assert len(result["enriched_contacts"]) == 1
        assert result["contacts_skipped"] == 1

    @pytest.mark.asyncio
    async def test_enrich_contacts_streaming_mode(self, nodes):
        """Should save contacts immediately in streaming mode."""
        nodes.progress_callback = None

        mock_repo = AsyncMock()
        mock_repo.contact_exists_by_email.return_value = False
        mock_repo.save_contact.return_value = Contact(
            id="saved-1", name="Marie Dupont", email=["marie@acme.com"]
        )
        nodes.leads_repository = mock_repo

        nodes.enrich_chain = AsyncMock()
        nodes.enrich_chain.extract_interesting_job_titles_from_profile.return_value = ["CTO"]
        nodes.enrich_chain.extract_contacts_from_answer.return_value = [
            ContactInfo(
                name="Marie Dupont",
                email=["marie@acme.com"],
                title="CTO",
                phone="",
                profile_url=[],
            )
        ]
        nodes.enrich_chain.extract_contact_bio.return_value = None
        nodes.web_search_client = AsyncMock()
        nodes.web_search_client.search_company_contacts.return_value = WebSearchResult(
            answer="Marie Dupont CTO"
        )
        nodes.web_search_client.search_contact_bio.return_value = WebSearchResult(answer="")
        nodes.duckduckgo_client = AsyncMock()
        nodes.duckduckgo_client.search_with_fallback.return_value = LinkedInSearchResult(
            urls=[], query="", success=True
        )

        mock_validation = MagicMock()
        mock_validation.confidence_score = 50
        mock_validation.validation_status.value = "likely_valid"
        mock_validation.validation_reasons = []
        nodes.contact_validator = MagicMock()
        nodes.contact_validator.validate_contact.return_value = mock_validation

        with patch("infrastructure.services.enrich_leads_agent.nodes.validate_email") as mock_validate:
            mock_validate.return_value.email = "marie@acme.com"

            company = Company(id="c1", name="Acme Corp")
            state = {"company": company, "step": []}

            result = await nodes.enrich_contacts(state)

        assert result["contacts_saved"] == 1
        assert len(result["enriched_contacts"]) == 1

    @pytest.mark.asyncio
    async def test_enrich_contacts_invalid_email_skipped(self, nodes):
        """Should skip invalid emails during validation."""
        from email_validator import EmailNotValidError
        nodes.progress_callback = None
        nodes.leads_repository = None

        nodes.enrich_chain = AsyncMock()
        nodes.enrich_chain.extract_interesting_job_titles_from_profile.return_value = ["CTO"]
        nodes.enrich_chain.extract_contacts_from_answer.return_value = [
            ContactInfo(
                name="Marie Dupont",
                email=["invalid-email", "valid@acme.com"],
                title="CTO",
                phone="",
                profile_url=[],
            )
        ]
        nodes.enrich_chain.extract_contact_bio.return_value = None
        nodes.web_search_client = AsyncMock()
        nodes.web_search_client.search_company_contacts.return_value = WebSearchResult(
            answer="Marie Dupont CTO"
        )
        nodes.web_search_client.search_contact_bio.return_value = WebSearchResult(answer="")
        nodes.duckduckgo_client = AsyncMock()
        nodes.duckduckgo_client.search_with_fallback.return_value = LinkedInSearchResult(
            urls=[], query="", success=True
        )

        mock_validation = MagicMock()
        mock_validation.confidence_score = 50
        mock_validation.validation_status.value = "likely_valid"
        mock_validation.validation_reasons = []
        nodes.contact_validator = MagicMock()
        nodes.contact_validator.validate_contact.return_value = mock_validation

        call_count = 0
        def validate_side_effect(email, **kwargs):
            nonlocal call_count
            call_count += 1
            if "invalid" in email:
                raise EmailNotValidError("Invalid email")
            mock_result = MagicMock()
            mock_result.email = email
            return mock_result

        with patch("infrastructure.services.enrich_leads_agent.nodes.validate_email", side_effect=validate_side_effect):
            company = Company(id="c1", name="Acme Corp")
            state = {"company": company, "step": []}

            result = await nodes.enrich_contacts(state)

        assert len(result["enriched_contacts"]) == 1
        # Only the valid email should be kept
        assert result["enriched_contacts"][0].email == ["valid@acme.com"]


class TestEnrichCompany:
    """Tests for enrich_company method."""

    @pytest.fixture
    def nodes(self):
        return _create_nodes()

    @pytest.mark.asyncio
    async def test_enrich_company_success(self, nodes):
        """Should enrich company with description, industry, location, size, revenue."""
        from infrastructure.services.enrich_leads_agent.models.company_info import CompanyInfo

        nodes.progress_callback = None
        nodes.web_search_client = AsyncMock()
        nodes.web_search_client.search_company_info.return_value = WebSearchResult(
            answer="Acme Corp is a leading tech company based in Paris with 200 employees."
        )
        nodes.enrich_chain = AsyncMock()
        nodes.enrich_chain.get_company_description.return_value = "Acme Corp provides cloud solutions."
        nodes.enrich_chain.extract_other_info_from_description.return_value = CompanyInfo(
            industry=["Technology", "Cloud"],
            compatibility="75",
            location=["Paris", "London"],
            size="200-500",
            revenue="50M",
        )

        company = Company(id="c1", name="Acme Corp")
        state = {"company": company, "step": []}

        result = await nodes.enrich_company(state)

        assert result["enriched_company"] == [company]
        assert result["company"] == []
        assert company.description == "Acme Corp provides cloud solutions."
        assert company.industry == "Technology, Cloud"
        assert company.location == "Paris, London"
        assert company.size == "200-500"
        assert company.revenue == "50M"
        assert company.compatibility == "75"

    @pytest.mark.asyncio
    async def test_enrich_company_strips_think_tags(self, nodes):
        """Should remove <think>...</think> tags from company description."""
        from infrastructure.services.enrich_leads_agent.models.company_info import CompanyInfo

        nodes.progress_callback = None
        nodes.web_search_client = AsyncMock()
        nodes.web_search_client.search_company_info.return_value = WebSearchResult(answer="Info")
        nodes.enrich_chain = AsyncMock()
        nodes.enrich_chain.get_company_description.return_value = (
            "<think>reasoning here</think>Acme Corp is a tech company."
        )
        nodes.enrich_chain.extract_other_info_from_description.return_value = CompanyInfo(
            industry=[], compatibility="0", location=[], size="", revenue=""
        )

        company = Company(id="c1", name="Acme Corp")
        state = {"company": company, "step": []}

        result = await nodes.enrich_company(state)

        assert "<think>" not in company.description
        assert company.description == "Acme Corp is a tech company."


class TestCreateEnrichCompanyTasks:
    """Tests for create_enrich_company_tasks method."""

    @pytest.fixture
    def nodes(self):
        return _create_nodes()

    def test_creates_tasks_for_approved_companies(self, nodes):
        """Should create Send tasks for approved companies."""
        companies = [Company(id="c1", name="Acme"), Company(id="c2", name="Beta")]
        state = {"company": companies, "step": []}

        result = nodes.create_enrich_company_tasks(state)

        assert len(result["enrich_companies_tasks"]) == 2

    def test_empty_companies_returns_empty_tasks(self, nodes):
        """Should return empty tasks when no approved companies."""
        state = {"company": [], "step": []}

        result = nodes.create_enrich_company_tasks(state)

        assert result["enrich_companies_tasks"] == []
