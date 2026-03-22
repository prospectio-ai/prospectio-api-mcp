"""
Extended unit tests for LeadsProcessor.

Covers the methods not yet tested: calculate_statistics,
calculate_compatibility_scores, and additional edge cases
for deduplication methods.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from domain.entities.company import Company, CompanyEntity
from domain.entities.contact import Contact, ContactEntity
from domain.entities.job import Job, JobEntity
from domain.entities.leads import Leads
from domain.entities.leads_result import LeadsResult
from domain.entities.profile import Profile
from domain.entities.compatibility_score import CompatibilityScore
from domain.services.leads.leads_processor import LeadsProcessor


def _create_processor(score_port=None) -> LeadsProcessor:
    """Create a LeadsProcessor with mocked LLMConfig."""
    if score_port is None:
        score_port = MagicMock()
    with patch("domain.services.leads.leads_processor.LLMConfig") as mock_config:
        mock_config.return_value.CONCURRENT_CALLS = 5
        return LeadsProcessor(compatibility_score_port=score_port)


class TestCalculateStatistics:
    """Tests for calculate_statistics method."""

    @pytest.fixture
    def processor(self) -> LeadsProcessor:
        return _create_processor()

    def test_calculate_statistics_with_data(self, processor: LeadsProcessor):
        """Should return correct counts for companies, jobs, and contacts."""
        leads = Leads(
            companies=CompanyEntity(
                companies=[
                    Company(name="A"),
                    Company(name="B"),
                ]
            ),
            jobs=JobEntity(
                jobs=[
                    Job(job_title="Dev1"),
                    Job(job_title="Dev2"),
                    Job(job_title="Dev3"),
                ]
            ),
            contacts=ContactEntity(
                contacts=[
                    Contact(name="C1"),
                ]
            ),
        )

        result = processor.calculate_statistics(leads)

        assert isinstance(result, LeadsResult)
        assert result.companies == "Insert of 2 companies"
        assert result.jobs == "insert of 3 jobs"
        assert result.contacts == "insert of 1 contacts"

    def test_calculate_statistics_empty_leads(self, processor: LeadsProcessor):
        """Should handle None entities gracefully."""
        leads = Leads(companies=None, jobs=None, contacts=None)

        result = processor.calculate_statistics(leads)

        assert result.companies == "Insert of 0 companies"
        assert result.jobs == "insert of 0 jobs"
        assert result.contacts == "insert of 0 contacts"


class TestCalculateCompatibilityScores:
    """Tests for calculate_compatibility_scores method."""

    @pytest.fixture
    def mock_score_port(self) -> AsyncMock:
        """Create a mock compatibility score port."""
        mock = AsyncMock()
        mock.get_compatibility_score.return_value = CompatibilityScore(score=85)
        return mock

    @pytest.fixture
    def processor(self, mock_score_port: AsyncMock) -> LeadsProcessor:
        return _create_processor(score_port=mock_score_port)

    @pytest.fixture
    def profile(self) -> Profile:
        """Create a test profile."""
        return Profile(
            job_title="AI Developer",
            location="Paris",
            bio="Machine learning expert",
            work_experience=[],
        )

    @pytest.mark.asyncio
    async def test_calculate_scores_for_jobs_with_descriptions(
        self, processor: LeadsProcessor, profile: Profile, mock_score_port: AsyncMock
    ):
        """Should calculate scores for jobs that have descriptions."""
        jobs = JobEntity(
            jobs=[
                Job(id="j1", job_title="Python Dev", description="Python developer position"),
                Job(id="j2", job_title="ML Engineer", description="Machine learning role"),
            ]
        )

        result = await processor.calculate_compatibility_scores(profile, jobs)

        assert result.jobs[0].compatibility_score == 85
        assert result.jobs[1].compatibility_score == 85
        assert mock_score_port.get_compatibility_score.await_count == 2

    @pytest.mark.asyncio
    async def test_calculate_scores_skips_jobs_without_description(
        self, processor: LeadsProcessor, profile: Profile, mock_score_port: AsyncMock
    ):
        """Should return 0 score for jobs without descriptions."""
        jobs = JobEntity(
            jobs=[
                Job(id="j1", job_title="No Description Job", description=None),
                Job(id="j2", job_title="Empty Description Job", description=""),
            ]
        )

        result = await processor.calculate_compatibility_scores(profile, jobs)

        assert result.jobs[0].compatibility_score == 0
        assert result.jobs[1].compatibility_score == 0
        # LLM should not be called for jobs without descriptions
        mock_score_port.get_compatibility_score.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_calculate_scores_empty_jobs(
        self, processor: LeadsProcessor, profile: Profile
    ):
        """Should handle empty jobs list."""
        jobs = JobEntity(jobs=[])

        result = await processor.calculate_compatibility_scores(profile, jobs)

        assert result.jobs == []


class TestDeduplicateCompanies:
    """Tests for deduplicate_companies method."""

    @pytest.fixture
    def processor(self) -> LeadsProcessor:
        return _create_processor()

    def test_deduplicate_companies_removes_duplicates(self, processor: LeadsProcessor):
        """Should remove duplicate companies by normalized name."""
        companies = CompanyEntity(
            companies=[
                Company(id="c1", name="Acme Corp"),
                Company(id="c2", name="acme corp"),
                Company(id="c3", name="Beta Inc"),
            ]
        )
        jobs = JobEntity(
            jobs=[
                Job(id="j1", company_id="c2", job_title="Dev"),
            ]
        )

        result = processor.deduplicate_companies(companies, jobs)

        assert len(result.companies) == 2
        names = [c.name for c in result.companies]
        assert "acme corp" in names
        assert "beta inc" in names

    def test_deduplicate_companies_updates_job_references(self, processor: LeadsProcessor):
        """Should update job company_id to reference the surviving deduplicated company."""
        companies = CompanyEntity(
            companies=[
                Company(id="c1", name="Acme Corp"),
                Company(id="c2", name="Acme Corp"),
            ]
        )
        jobs = JobEntity(
            jobs=[
                Job(id="j1", company_id="c2", job_title="Dev"),
            ]
        )

        processor.deduplicate_companies(companies, jobs)

        # Job should now reference c1 (first unique company)
        assert jobs.jobs[0].company_id == "c1"


class TestNewCompanies:
    """Tests for new_companies method."""

    @pytest.fixture
    def processor(self) -> LeadsProcessor:
        return _create_processor()

    def test_filters_existing_companies(self, processor: LeadsProcessor):
        """Should filter out companies that already exist in DB."""
        companies = CompanyEntity(
            companies=[
                Company(name="Acme Corp"),
                Company(name="New Corp"),
            ]
        )
        db_companies = CompanyEntity(
            companies=[
                Company(name="acme corp"),  # case-insensitive match
            ]
        )

        result = processor.new_companies(companies, db_companies)

        assert len(result.companies) == 1
        assert result.companies[0].name == "New Corp"


class TestNewJobs:
    """Tests for new_jobs method."""

    @pytest.fixture
    def processor(self) -> LeadsProcessor:
        return _create_processor()

    def test_filters_existing_jobs(self, processor: LeadsProcessor):
        """Should filter out jobs that already exist in DB."""
        jobs = JobEntity(
            jobs=[
                Job(job_title="Python Dev", location="Paris", job_type="fulltime", company_id="c1", description="desc1"),
                Job(job_title="New Role", location="London", job_type="contract", company_id="c2", description="desc2"),
            ]
        )
        db_jobs = JobEntity(
            jobs=[
                Job(job_title="python dev", location="paris", job_type="fulltime", company_id="c1", description="desc1"),
            ]
        )

        result = processor.new_jobs(jobs, db_jobs)

        assert len(result.jobs) == 1
        assert result.jobs[0].job_title.strip().lower() == "new role"


class TestChangeJobsCompanyId:
    """Tests for change_jobs_company_id method."""

    @pytest.fixture
    def processor(self) -> LeadsProcessor:
        return _create_processor()

    def test_updates_job_company_ids_from_db(self, processor: LeadsProcessor):
        """Should update job company_id to DB company_id."""
        jobs = JobEntity(
            jobs=[
                Job(id="j1", company_id="temp-c1", job_title="Dev"),
            ]
        )
        companies = CompanyEntity(
            companies=[
                Company(id="temp-c1", name="Acme Corp"),
            ]
        )
        db_companies = CompanyEntity(
            companies=[
                Company(id="real-c1", name="Acme Corp"),
            ]
        )

        result = processor.change_jobs_company_id(jobs, companies, db_companies)

        assert result.jobs[0].company_id == "real-c1"


class TestDeduplicateContacts:
    """Tests for deduplicate_contacts method."""

    @pytest.fixture
    def processor(self) -> LeadsProcessor:
        return _create_processor()

    def test_removes_duplicate_contacts(self, processor: LeadsProcessor):
        """Should remove duplicate contacts based on normalized name+title."""
        contacts = ContactEntity(
            contacts=[
                Contact(name="Marie Dupont", title="CTO", email=["m@a.com"]),
                Contact(name="marie dupont", title="cto", email=["m@a.com"]),
                Contact(name="Jean Martin", title="VP", email=["j@a.com"]),
            ]
        )

        result = processor.deduplicate_contacts(contacts)

        assert len(result.contacts) == 2

    def test_excludes_contacts_without_email(self, processor: LeadsProcessor):
        """Should exclude contacts without email addresses."""
        contacts = ContactEntity(
            contacts=[
                Contact(name="NoEmail", title="Manager", email=None),
                Contact(name="HasEmail", title="Director", email=["x@y.com"]),
            ]
        )

        result = processor.deduplicate_contacts(contacts)

        assert len(result.contacts) == 1
        assert result.contacts[0].name == "hasemail"

    def test_excludes_contacts_without_title(self, processor: LeadsProcessor):
        """Should exclude contacts without title."""
        contacts = ContactEntity(
            contacts=[
                Contact(name="NoTitle", title=None, email=["a@b.com"]),
                Contact(name="HasTitle", title="CTO", email=["b@c.com"]),
            ]
        )

        result = processor.deduplicate_contacts(contacts)

        assert len(result.contacts) == 1


class TestNewContacts:
    """Tests for new_contacts method."""

    @pytest.fixture
    def processor(self) -> LeadsProcessor:
        return _create_processor()

    def test_filters_existing_contacts(self, processor: LeadsProcessor):
        """Should filter out contacts that already exist in DB."""
        contacts = ContactEntity(
            contacts=[
                Contact(name="Marie Dupont", title="CTO"),
                Contact(name="Jean Martin", title="VP Engineering"),
            ]
        )
        db_contacts = ContactEntity(
            contacts=[
                Contact(name="marie dupont", title="cto"),
            ]
        )

        result = processor.new_contacts(contacts, db_contacts)

        assert len(result.contacts) == 1
        assert result.contacts[0].name == "Jean Martin"

    def test_all_contacts_are_new(self, processor: LeadsProcessor):
        """Should return all contacts when none exist in DB."""
        contacts = ContactEntity(
            contacts=[
                Contact(name="Marie", title="CTO"),
            ]
        )
        db_contacts = ContactEntity(contacts=[])

        result = processor.new_contacts(contacts, db_contacts)

        assert len(result.contacts) == 1


class TestChangeContactsJobAndCompanyId:
    """Tests for change_contacts_job_and_company_id method."""

    @pytest.fixture
    def processor(self) -> LeadsProcessor:
        return _create_processor()

    def test_updates_company_id_from_lookup(self, processor: LeadsProcessor):
        """Should update contact company_id from company lookup."""
        contacts = ContactEntity(
            contacts=[
                Contact(name="Marie", title="cto", company_id="Acme Corp"),
            ]
        )
        jobs = JobEntity(jobs=[])
        companies = CompanyEntity(
            companies=[
                Company(id="real-c1", name="Acme Corp"),
            ]
        )

        result = processor.change_contacts_job_and_company_id(contacts, jobs, companies)

        assert result.contacts[0].company_id == "real-c1"

    def test_updates_job_id_from_lookup(self, processor: LeadsProcessor):
        """Should update contact job_id when title+company matches a job."""
        contacts = ContactEntity(
            contacts=[
                Contact(name="Marie", title="Python Developer", company_id="paris, france"),
            ]
        )
        jobs = JobEntity(
            jobs=[
                Job(id="j1", job_title="Python Developer", location="Paris, France"),
            ]
        )
        companies = CompanyEntity(companies=[])

        result = processor.change_contacts_job_and_company_id(contacts, jobs, companies)

        assert result.contacts[0].job_id == "j1"


class TestDeduplicateJobs:
    """Tests for deduplicate_jobs method."""

    @pytest.fixture
    def processor(self) -> LeadsProcessor:
        return _create_processor()

    def test_removes_duplicate_jobs(self, processor: LeadsProcessor):
        """Should remove duplicate jobs by normalized title+location+type+company."""
        jobs = JobEntity(
            jobs=[
                Job(id="j1", job_title="Python Dev", location="Paris", job_type="fulltime", company_id="c1"),
                Job(id="j2", job_title="python dev", location="paris", job_type="fulltime", company_id="c1"),
                Job(id="j3", job_title="Java Dev", location="London", job_type="contract", company_id="c2"),
            ]
        )

        result = processor.deduplicate_jobs(jobs)

        assert len(result.jobs) == 2


class TestEnrichLeads:
    """Tests for enrich_leads method."""

    @pytest.fixture
    def processor(self) -> LeadsProcessor:
        return _create_processor()

    @pytest.mark.asyncio
    async def test_enrich_leads_delegates_to_port(self, processor: LeadsProcessor):
        """Should delegate enrichment to the enrich_leads port."""
        profile = Profile(job_title="Dev", location="Paris", bio="Test", work_experience=[])
        leads = Leads(
            companies=CompanyEntity(companies=[]),
            jobs=JobEntity(jobs=[]),
            contacts=ContactEntity(contacts=[]),
        )
        enriched_leads = Leads(
            companies=CompanyEntity(companies=[Company(name="Enriched")]),
            jobs=JobEntity(jobs=[]),
            contacts=ContactEntity(contacts=[]),
        )
        mock_enrich_port = AsyncMock()
        mock_enrich_port.execute.return_value = enriched_leads

        result = await processor.enrich_leads(mock_enrich_port, leads, profile, "task-123")

        assert result == enriched_leads
        mock_enrich_port.execute.assert_awaited_once_with(leads, profile, "task-123")
