"""
DEPRECATED: These tests exercise a FakeRepository, not the real implementation.
They should be replaced with real repository integration tests using PostgreSQL
test containers (testcontainers-python) when available. See PROS-12.

Unit tests for FakeLeadsRepository test double.
"""

import pytest

from domain.entities.company import Company
from domain.entities.contact import Contact
from domain.entities.job import Job
from tests.ut.fakes.fake_leads_repository import FakeLeadsRepository


class TestFakeLeadsRepository:
    """Test suite for FakeLeadsRepository test double."""

    @pytest.fixture
    def repository(self) -> FakeLeadsRepository:
        """Create a fresh FakeLeadsRepository for each test."""
        return FakeLeadsRepository()

    @pytest.fixture
    def sample_company(self) -> Company:
        """Create a sample company for testing."""
        return Company(
            name="Tech Solutions Inc",
            industry="Technology",
            location="Paris, France",
            size="50-200 employees",
            revenue="5-10M",
            website="https://techsolutions.com",
            description="Leading technology solutions provider",
        )

    @pytest.fixture
    def sample_contact(self) -> Contact:
        """Create a sample contact for testing."""
        return Contact(
            name="Marie Dubois",
            email=["marie.dubois@techsolutions.com", "marie@personal.com"],
            title="HR Manager",
            phone="+33 1 23 45 67 89",
            profile_url="https://linkedin.com/in/marie-dubois",
        )

    # --- Tests for company_exists_by_name ---

    @pytest.mark.asyncio
    async def test_company_exists_by_name_returns_false_when_no_companies(
        self, repository: FakeLeadsRepository
    ):
        """Should return False when repository has no companies."""
        result = await repository.company_exists_by_name("Nonexistent Company")
        assert result is False

    @pytest.mark.asyncio
    async def test_company_exists_by_name_returns_false_when_company_not_found(
        self, repository: FakeLeadsRepository, sample_company: Company
    ):
        """Should return False when company name does not match."""
        await repository.save_company(sample_company)

        result = await repository.company_exists_by_name("Different Company")
        assert result is False

    @pytest.mark.asyncio
    async def test_company_exists_by_name_returns_true_when_company_exists(
        self, repository: FakeLeadsRepository, sample_company: Company
    ):
        """Should return True when a company with the given name exists."""
        await repository.save_company(sample_company)

        result = await repository.company_exists_by_name("Tech Solutions Inc")
        assert result is True

    @pytest.mark.asyncio
    async def test_company_exists_by_name_is_exact_match(
        self, repository: FakeLeadsRepository, sample_company: Company
    ):
        """Should only match exact company names, not partial matches."""
        await repository.save_company(sample_company)

        # Partial match should return False
        result = await repository.company_exists_by_name("Tech Solutions")
        assert result is False

        # Exact match should return True
        result = await repository.company_exists_by_name("Tech Solutions Inc")
        assert result is True

    # --- Tests for contact_exists_by_email ---

    @pytest.mark.asyncio
    async def test_contact_exists_by_email_returns_false_when_no_contacts(
        self, repository: FakeLeadsRepository
    ):
        """Should return False when repository has no contacts."""
        result = await repository.contact_exists_by_email(["test@example.com"])
        assert result is False

    @pytest.mark.asyncio
    async def test_contact_exists_by_email_returns_false_when_no_email_overlap(
        self, repository: FakeLeadsRepository, sample_contact: Contact
    ):
        """Should return False when none of the provided emails match."""
        await repository.save_contact(sample_contact)

        result = await repository.contact_exists_by_email(
            ["different@example.com", "other@test.com"]
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_contact_exists_by_email_returns_true_when_single_email_matches(
        self, repository: FakeLeadsRepository, sample_contact: Contact
    ):
        """Should return True when one of the provided emails matches."""
        await repository.save_contact(sample_contact)

        # Match the primary email
        result = await repository.contact_exists_by_email(
            ["marie.dubois@techsolutions.com"]
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_contact_exists_by_email_returns_true_when_secondary_email_matches(
        self, repository: FakeLeadsRepository, sample_contact: Contact
    ):
        """Should return True when a secondary email in the contact matches."""
        await repository.save_contact(sample_contact)

        # Match the secondary email
        result = await repository.contact_exists_by_email(["marie@personal.com"])
        assert result is True

    @pytest.mark.asyncio
    async def test_contact_exists_by_email_returns_true_with_partial_overlap(
        self, repository: FakeLeadsRepository, sample_contact: Contact
    ):
        """Should return True when at least one email overlaps."""
        await repository.save_contact(sample_contact)

        # One matching email among non-matching ones
        result = await repository.contact_exists_by_email(
            ["nonexistent@example.com", "marie@personal.com", "other@test.com"]
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_contact_exists_by_email_with_empty_email_list(
        self, repository: FakeLeadsRepository, sample_contact: Contact
    ):
        """Should return False when provided with an empty email list."""
        await repository.save_contact(sample_contact)

        result = await repository.contact_exists_by_email([])
        assert result is False

    @pytest.mark.asyncio
    async def test_contact_exists_by_email_handles_contact_with_no_emails(
        self, repository: FakeLeadsRepository
    ):
        """Should handle contacts that have no email addresses."""
        contact_without_email = Contact(
            name="John Doe",
            email=None,
            title="Developer",
        )
        await repository.save_contact(contact_without_email)

        result = await repository.contact_exists_by_email(["any@example.com"])
        assert result is False

    # --- Tests for save_company ---

    @pytest.mark.asyncio
    async def test_save_company_returns_company_with_id(
        self, repository: FakeLeadsRepository, sample_company: Company
    ):
        """Should return the saved company with a generated ID."""
        saved_company = await repository.save_company(sample_company)

        assert saved_company.id is not None
        assert saved_company.name == sample_company.name
        assert saved_company.industry == sample_company.industry

    @pytest.mark.asyncio
    async def test_save_company_preserves_existing_id(
        self, repository: FakeLeadsRepository
    ):
        """Should preserve the ID if company already has one."""
        company_with_id = Company(
            id="existing-id-123",
            name="Existing Company",
            industry="Finance",
        )

        saved_company = await repository.save_company(company_with_id)

        assert saved_company.id == "existing-id-123"

    @pytest.mark.asyncio
    async def test_save_company_persists_to_storage(
        self, repository: FakeLeadsRepository, sample_company: Company
    ):
        """Should persist the company so it can be retrieved later."""
        saved_company = await repository.save_company(sample_company)

        retrieved = await repository.get_company_by_id(saved_company.id)
        assert retrieved is not None
        assert retrieved.name == sample_company.name

    @pytest.mark.asyncio
    async def test_save_company_generates_unique_ids(
        self, repository: FakeLeadsRepository
    ):
        """Should generate unique IDs for different companies."""
        company1 = Company(name="Company One")
        company2 = Company(name="Company Two")

        saved1 = await repository.save_company(company1)
        saved2 = await repository.save_company(company2)

        assert saved1.id != saved2.id

    # --- Tests for save_contact ---

    @pytest.mark.asyncio
    async def test_save_contact_returns_contact_with_id(
        self, repository: FakeLeadsRepository, sample_contact: Contact
    ):
        """Should return the saved contact with a generated ID."""
        saved_contact = await repository.save_contact(sample_contact)

        assert saved_contact.id is not None
        assert saved_contact.name == sample_contact.name
        assert saved_contact.email == sample_contact.email

    @pytest.mark.asyncio
    async def test_save_contact_preserves_existing_id(
        self, repository: FakeLeadsRepository
    ):
        """Should preserve the ID if contact already has one."""
        contact_with_id = Contact(
            id="contact-id-456",
            name="Existing Contact",
            email=["existing@example.com"],
        )

        saved_contact = await repository.save_contact(contact_with_id)

        assert saved_contact.id == "contact-id-456"

    @pytest.mark.asyncio
    async def test_save_contact_persists_to_storage(
        self, repository: FakeLeadsRepository, sample_contact: Contact
    ):
        """Should persist the contact so it can be retrieved later."""
        saved_contact = await repository.save_contact(sample_contact)

        retrieved = await repository.get_contact_by_id(saved_contact.id)
        assert retrieved is not None
        assert retrieved.name == sample_contact.name
        assert retrieved.email == sample_contact.email

    @pytest.mark.asyncio
    async def test_save_contact_generates_unique_ids(
        self, repository: FakeLeadsRepository
    ):
        """Should generate unique IDs for different contacts."""
        contact1 = Contact(name="Contact One", email=["one@example.com"])
        contact2 = Contact(name="Contact Two", email=["two@example.com"])

        saved1 = await repository.save_contact(contact1)
        saved2 = await repository.save_contact(contact2)

        assert saved1.id != saved2.id

    # --- Integration tests ---

    @pytest.mark.asyncio
    async def test_reset_clears_all_data(
        self, repository: FakeLeadsRepository, sample_company: Company, sample_contact: Contact
    ):
        """Should clear all stored data when reset is called."""
        await repository.save_company(sample_company)
        await repository.save_contact(sample_contact)

        repository.reset()

        assert await repository.company_exists_by_name(sample_company.name) is False
        assert await repository.contact_exists_by_email(sample_contact.email) is False


class TestFakeLeadsRepositoryJobStreaming:
    """Test suite for FakeLeadsRepository job streaming methods."""

    @pytest.fixture
    def repository(self) -> FakeLeadsRepository:
        """Create a fresh FakeLeadsRepository for each test."""
        return FakeLeadsRepository()

    @pytest.fixture
    def sample_job(self) -> Job:
        """Create a sample job for testing."""
        return Job(
            job_title="Senior Python Developer",
            company_name="Tech Solutions Inc",
            description="We are looking for a senior Python developer...",
            location="Paris, France",
            salary="80000 - 120000 EUR",
            job_type="FULL_TIME",
            apply_url=["https://techsolutions.com/careers/apply"],
        )

    @pytest.fixture
    def sample_company(self) -> Company:
        """Create a sample company for testing."""
        return Company(
            name="Tech Solutions Inc",
            industry="Technology",
            location="Paris, France",
            website="https://techsolutions.com",
        )

    # --- Tests for job_exists ---

    @pytest.mark.asyncio
    async def test_job_exists_returns_false_when_no_jobs(
        self, repository: FakeLeadsRepository
    ):
        """Should return False when repository has no jobs."""
        result = await repository.job_exists("Senior Developer", "Any Company")
        assert result is False

    @pytest.mark.asyncio
    async def test_job_exists_returns_false_when_job_not_found(
        self, repository: FakeLeadsRepository, sample_job: Job
    ):
        """Should return False when job title and company combination does not exist."""
        await repository.save_job(sample_job)

        # Different job title
        result = await repository.job_exists("Junior Developer", "Tech Solutions Inc")
        assert result is False

    @pytest.mark.asyncio
    async def test_job_exists_returns_false_when_company_not_found(
        self, repository: FakeLeadsRepository, sample_job: Job
    ):
        """Should return False when company name does not match."""
        await repository.save_job(sample_job)

        # Different company
        result = await repository.job_exists("Senior Python Developer", "Other Company")
        assert result is False

    @pytest.mark.asyncio
    async def test_job_exists_returns_true_when_job_exists(
        self, repository: FakeLeadsRepository, sample_job: Job
    ):
        """Should return True when a job with the given title and company exists."""
        await repository.save_job(sample_job)

        result = await repository.job_exists("Senior Python Developer", "Tech Solutions Inc")
        assert result is True

    @pytest.mark.asyncio
    async def test_job_exists_is_exact_match(
        self, repository: FakeLeadsRepository, sample_job: Job
    ):
        """Should only match exact job title and company name, not partial matches."""
        await repository.save_job(sample_job)

        # Partial match on job title should return False
        result = await repository.job_exists("Senior Python", "Tech Solutions Inc")
        assert result is False

        # Partial match on company name should return False
        result = await repository.job_exists("Senior Python Developer", "Tech Solutions")
        assert result is False

        # Exact match should return True
        result = await repository.job_exists("Senior Python Developer", "Tech Solutions Inc")
        assert result is True

    # --- Tests for save_job ---

    @pytest.mark.asyncio
    async def test_save_job_returns_job_with_id(
        self, repository: FakeLeadsRepository, sample_job: Job
    ):
        """Should return the saved job with a generated ID."""
        saved_job = await repository.save_job(sample_job)

        assert saved_job.id is not None
        assert saved_job.job_title == sample_job.job_title
        assert saved_job.company_name == sample_job.company_name

    @pytest.mark.asyncio
    async def test_save_job_preserves_existing_id(
        self, repository: FakeLeadsRepository
    ):
        """Should preserve the ID if job already has one."""
        job_with_id = Job(
            id="existing-job-id-789",
            job_title="Backend Developer",
            company_name="Startup Corp",
        )

        saved_job = await repository.save_job(job_with_id)

        assert saved_job.id == "existing-job-id-789"

    @pytest.mark.asyncio
    async def test_save_job_persists_to_storage(
        self, repository: FakeLeadsRepository, sample_job: Job
    ):
        """Should persist the job so it can be found via job_exists."""
        saved_job = await repository.save_job(sample_job)

        exists = await repository.job_exists(
            saved_job.job_title, saved_job.company_name  # type: ignore
        )
        assert exists is True

    @pytest.mark.asyncio
    async def test_save_job_generates_unique_ids(
        self, repository: FakeLeadsRepository
    ):
        """Should generate unique IDs for different jobs."""
        job1 = Job(job_title="Developer 1", company_name="Company A")
        job2 = Job(job_title="Developer 2", company_name="Company B")

        saved1 = await repository.save_job(job1)
        saved2 = await repository.save_job(job2)

        assert saved1.id != saved2.id

    @pytest.mark.asyncio
    async def test_save_job_preserves_all_fields(
        self, repository: FakeLeadsRepository, sample_job: Job
    ):
        """Should preserve all job fields when saving."""
        saved_job = await repository.save_job(sample_job)

        assert saved_job.job_title == sample_job.job_title
        assert saved_job.company_name == sample_job.company_name
        assert saved_job.description == sample_job.description
        assert saved_job.location == sample_job.location
        assert saved_job.salary == sample_job.salary
        assert saved_job.job_type == sample_job.job_type
        assert saved_job.apply_url == sample_job.apply_url

    # --- Tests for get_or_create_company_stub ---

    @pytest.mark.asyncio
    async def test_get_or_create_company_stub_returns_existing_company(
        self, repository: FakeLeadsRepository, sample_company: Company
    ):
        """Should return existing company if it already exists."""
        # First save a company
        saved_company = await repository.save_company(sample_company)

        # Then call get_or_create_company_stub with the same name
        result = await repository.get_or_create_company_stub("Tech Solutions Inc")

        assert result.id == saved_company.id
        assert result.name == saved_company.name
        # Should preserve original company data
        assert result.industry == saved_company.industry
        assert result.location == saved_company.location

    @pytest.mark.asyncio
    async def test_get_or_create_company_stub_creates_new_stub(
        self, repository: FakeLeadsRepository
    ):
        """Should create a new stub company if it does not exist."""
        result = await repository.get_or_create_company_stub("New Company LLC")

        assert result.id is not None
        assert result.name == "New Company LLC"
        # Stub company should have only the name, other fields should be None/default
        assert result.industry is None
        assert result.location is None

    @pytest.mark.asyncio
    async def test_get_or_create_company_stub_persists_new_stub(
        self, repository: FakeLeadsRepository
    ):
        """Should persist the new stub company so it can be retrieved later."""
        result = await repository.get_or_create_company_stub("New Company LLC")

        # Verify company exists
        exists = await repository.company_exists_by_name("New Company LLC")
        assert exists is True

        # Verify can be retrieved by ID
        retrieved = await repository.get_company_by_id(result.id)  # type: ignore
        assert retrieved is not None
        assert retrieved.name == "New Company LLC"

    @pytest.mark.asyncio
    async def test_get_or_create_company_stub_returns_same_stub_on_second_call(
        self, repository: FakeLeadsRepository
    ):
        """Should return the same stub company on subsequent calls with the same name."""
        first_call = await repository.get_or_create_company_stub("Stub Company")
        second_call = await repository.get_or_create_company_stub("Stub Company")

        assert first_call.id == second_call.id
        assert first_call.name == second_call.name

    @pytest.mark.asyncio
    async def test_get_or_create_company_stub_creates_different_stubs_for_different_names(
        self, repository: FakeLeadsRepository
    ):
        """Should create different stub companies for different names."""
        stub1 = await repository.get_or_create_company_stub("Company A")
        stub2 = await repository.get_or_create_company_stub("Company B")

        assert stub1.id != stub2.id
        assert stub1.name == "Company A"
        assert stub2.name == "Company B"

    # --- Integration tests for job streaming workflow ---

    @pytest.mark.asyncio
    async def test_job_streaming_workflow(
        self, repository: FakeLeadsRepository
    ):
        """Should support the full job streaming workflow."""
        company_name = "Streaming Test Corp"
        job_title = "Data Engineer"

        # Step 1: Check if job exists (should be False)
        exists = await repository.job_exists(job_title, company_name)
        assert exists is False

        # Step 2: Get or create company stub
        company = await repository.get_or_create_company_stub(company_name)
        assert company.id is not None

        # Step 3: Save the job with company_id
        job = Job(
            job_title=job_title,
            company_name=company_name,
            company_id=company.id,
            description="Build data pipelines",
        )
        saved_job = await repository.save_job(job)

        # Step 4: Verify job now exists
        exists = await repository.job_exists(job_title, company_name)
        assert exists is True

        # Step 5: Second call should detect duplicate
        exists = await repository.job_exists(job_title, company_name)
        assert exists is True

    @pytest.mark.asyncio
    async def test_reset_clears_jobs(
        self, repository: FakeLeadsRepository, sample_job: Job
    ):
        """Should clear all jobs when reset is called."""
        await repository.save_job(sample_job)

        repository.reset()

        exists = await repository.job_exists(
            sample_job.job_title, sample_job.company_name  # type: ignore
        )
        assert exists is False
