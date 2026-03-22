"""Unit tests for job streaming functionality in API adapters."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from domain.entities.company import Company
from domain.entities.job import Job
from config import JsearchConfig, ActiveJobsDBConfig
from infrastructure.services.jsearch import JsearchAPI
from infrastructure.services.active_jobs_db import ActiveJobsDBAPI
from tests.ut.fakes.fake_leads_repository import FakeLeadsRepository


class TestJsearchAPIJobStreaming:
    """Test suite for JsearchAPI job streaming functionality."""

    @pytest.fixture
    def jsearch_config(self) -> JsearchConfig:
        """Create a test configuration for JSearch API."""
        return JsearchConfig(
            JSEARCH_API_URL="https://jsearch.p.rapidapi.com",
            RAPIDAPI_API_KEY=["test-rapidapi-key"]
        )

    @pytest.fixture
    def fake_repository(self) -> FakeLeadsRepository:
        """Create a FakeLeadsRepository for testing job streaming."""
        return FakeLeadsRepository()

    @pytest.fixture
    def jsearch_api_with_repository(
        self, jsearch_config: JsearchConfig, fake_repository: FakeLeadsRepository
    ) -> JsearchAPI:
        """Create a JsearchAPI instance with a repository for streaming."""
        return JsearchAPI(jsearch_config, leads_repository=fake_repository)

    @pytest.fixture
    def jsearch_api_without_repository(
        self, jsearch_config: JsearchConfig
    ) -> JsearchAPI:
        """Create a JsearchAPI instance without a repository."""
        return JsearchAPI(jsearch_config, leads_repository=None)

    @pytest.fixture
    def sample_job(self) -> Job:
        """Create a sample job for testing."""
        return Job(
            job_title="Senior Python Developer",
            company_name="Tech Solutions",
            description="We are looking for a senior Python developer...",
            location="Paris, France",
        )

    # --- Tests for _save_job_if_new ---

    @pytest.mark.asyncio
    async def test_save_job_if_new_without_repository(
        self, jsearch_api_without_repository: JsearchAPI, sample_job: Job
    ):
        """Should return False and original job when no repository is set."""
        was_saved, returned_job = await jsearch_api_without_repository._save_job_if_new(
            sample_job, "Tech Solutions"
        )

        assert was_saved is False
        assert returned_job == sample_job

    @pytest.mark.asyncio
    async def test_save_job_if_new_with_missing_job_title(
        self, jsearch_api_with_repository: JsearchAPI
    ):
        """Should return False when job has no title."""
        job_without_title = Job(company_name="Some Company")

        was_saved, returned_job = await jsearch_api_with_repository._save_job_if_new(
            job_without_title, "Some Company"
        )

        assert was_saved is False
        assert returned_job == job_without_title

    @pytest.mark.asyncio
    async def test_save_job_if_new_with_missing_company_name(
        self, jsearch_api_with_repository: JsearchAPI
    ):
        """Should return False when company name is empty."""
        job = Job(job_title="Developer")

        was_saved, returned_job = await jsearch_api_with_repository._save_job_if_new(
            job, ""
        )

        assert was_saved is False
        assert returned_job == job

    @pytest.mark.asyncio
    async def test_save_job_if_new_saves_new_job(
        self,
        jsearch_api_with_repository: JsearchAPI,
        fake_repository: FakeLeadsRepository,
        sample_job: Job,
    ):
        """Should save a new job and return True."""
        was_saved, saved_job = await jsearch_api_with_repository._save_job_if_new(
            sample_job, "Tech Solutions"
        )

        assert was_saved is True
        assert saved_job.id is not None
        assert saved_job.company_id is not None
        assert jsearch_api_with_repository._jobs_saved == 1
        assert jsearch_api_with_repository._jobs_skipped == 0

        # Verify job was persisted
        exists = await fake_repository.job_exists("Senior Python Developer", "Tech Solutions")
        assert exists is True

    @pytest.mark.asyncio
    async def test_save_job_if_new_skips_existing_job(
        self,
        jsearch_api_with_repository: JsearchAPI,
        fake_repository: FakeLeadsRepository,
        sample_job: Job,
    ):
        """Should skip saving when job already exists."""
        # First save the job
        await jsearch_api_with_repository._save_job_if_new(sample_job, "Tech Solutions")

        # Reset counters
        jsearch_api_with_repository._jobs_saved = 0
        jsearch_api_with_repository._jobs_skipped = 0

        # Try to save the same job again
        duplicate_job = Job(
            job_title="Senior Python Developer",
            company_name="Tech Solutions",
            description="Different description",
        )
        was_saved, returned_job = await jsearch_api_with_repository._save_job_if_new(
            duplicate_job, "Tech Solutions"
        )

        assert was_saved is False
        assert jsearch_api_with_repository._jobs_saved == 0
        assert jsearch_api_with_repository._jobs_skipped == 1

    @pytest.mark.asyncio
    async def test_save_job_if_new_creates_company_stub(
        self,
        jsearch_api_with_repository: JsearchAPI,
        fake_repository: FakeLeadsRepository,
        sample_job: Job,
    ):
        """Should create company stub when saving a new job."""
        # Verify company does not exist
        exists = await fake_repository.company_exists_by_name("Tech Solutions")
        assert exists is False

        # Save job
        await jsearch_api_with_repository._save_job_if_new(sample_job, "Tech Solutions")

        # Verify company stub was created
        exists = await fake_repository.company_exists_by_name("Tech Solutions")
        assert exists is True

    @pytest.mark.asyncio
    async def test_save_job_if_new_uses_existing_company(
        self,
        jsearch_api_with_repository: JsearchAPI,
        fake_repository: FakeLeadsRepository,
        sample_job: Job,
    ):
        """Should use existing company when saving a job."""
        # Pre-create company with full data
        existing_company = Company(
            name="Tech Solutions",
            industry="Technology",
            location="Paris",
            website="https://techsolutions.com",
        )
        saved_company = await fake_repository.save_company(existing_company)

        # Save job
        was_saved, saved_job = await jsearch_api_with_repository._save_job_if_new(
            sample_job, "Tech Solutions"
        )

        # Verify job uses existing company's ID
        assert was_saved is True
        assert saved_job.company_id == saved_company.id


class TestActiveJobsDBAPIJobStreaming:
    """Test suite for ActiveJobsDBAPI job streaming functionality."""

    @pytest.fixture
    def active_jobs_config(self) -> ActiveJobsDBConfig:
        """Create a test configuration for Active Jobs DB API."""
        return ActiveJobsDBConfig(
            ACTIVE_JOBS_DB_URL="https://active-jobs-db.p.rapidapi.com",
            RAPIDAPI_API_KEY=["test-rapidapi-key"]
        )

    @pytest.fixture
    def fake_repository(self) -> FakeLeadsRepository:
        """Create a FakeLeadsRepository for testing job streaming."""
        return FakeLeadsRepository()

    @pytest.fixture
    def active_jobs_api_with_repository(
        self, active_jobs_config: ActiveJobsDBConfig, fake_repository: FakeLeadsRepository
    ) -> ActiveJobsDBAPI:
        """Create an ActiveJobsDBAPI instance with a repository for streaming."""
        return ActiveJobsDBAPI(active_jobs_config, leads_repository=fake_repository)

    @pytest.fixture
    def active_jobs_api_without_repository(
        self, active_jobs_config: ActiveJobsDBConfig
    ) -> ActiveJobsDBAPI:
        """Create an ActiveJobsDBAPI instance without a repository."""
        return ActiveJobsDBAPI(active_jobs_config, leads_repository=None)

    @pytest.fixture
    def sample_job(self) -> Job:
        """Create a sample job for testing."""
        return Job(
            job_title="Backend Engineer",
            company_name="Innovation Labs",
            description="Join our data engineering team...",
            location="Lyon, France",
        )

    # --- Tests for _save_job_if_new ---

    @pytest.mark.asyncio
    async def test_save_job_if_new_without_repository(
        self, active_jobs_api_without_repository: ActiveJobsDBAPI, sample_job: Job
    ):
        """Should return False and original job when no repository is set."""
        was_saved, returned_job = await active_jobs_api_without_repository._save_job_if_new(
            sample_job, "Innovation Labs"
        )

        assert was_saved is False
        assert returned_job == sample_job

    @pytest.mark.asyncio
    async def test_save_job_if_new_with_missing_job_title(
        self, active_jobs_api_with_repository: ActiveJobsDBAPI
    ):
        """Should return False when job has no title."""
        job_without_title = Job(company_name="Some Company")

        was_saved, returned_job = await active_jobs_api_with_repository._save_job_if_new(
            job_without_title, "Some Company"
        )

        assert was_saved is False
        assert returned_job == job_without_title

    @pytest.mark.asyncio
    async def test_save_job_if_new_with_missing_company_name(
        self, active_jobs_api_with_repository: ActiveJobsDBAPI
    ):
        """Should return False when company name is empty."""
        job = Job(job_title="Developer")

        was_saved, returned_job = await active_jobs_api_with_repository._save_job_if_new(
            job, ""
        )

        assert was_saved is False
        assert returned_job == job

    @pytest.mark.asyncio
    async def test_save_job_if_new_saves_new_job(
        self,
        active_jobs_api_with_repository: ActiveJobsDBAPI,
        fake_repository: FakeLeadsRepository,
        sample_job: Job,
    ):
        """Should save a new job and return True."""
        was_saved, saved_job = await active_jobs_api_with_repository._save_job_if_new(
            sample_job, "Innovation Labs"
        )

        assert was_saved is True
        assert saved_job.id is not None
        assert saved_job.company_id is not None
        assert active_jobs_api_with_repository._jobs_saved == 1
        assert active_jobs_api_with_repository._jobs_skipped == 0

        # Verify job was persisted
        exists = await fake_repository.job_exists("Backend Engineer", "Innovation Labs")
        assert exists is True

    @pytest.mark.asyncio
    async def test_save_job_if_new_skips_existing_job(
        self,
        active_jobs_api_with_repository: ActiveJobsDBAPI,
        fake_repository: FakeLeadsRepository,
        sample_job: Job,
    ):
        """Should skip saving when job already exists."""
        # First save the job
        await active_jobs_api_with_repository._save_job_if_new(sample_job, "Innovation Labs")

        # Reset counters
        active_jobs_api_with_repository._jobs_saved = 0
        active_jobs_api_with_repository._jobs_skipped = 0

        # Try to save the same job again
        duplicate_job = Job(
            job_title="Backend Engineer",
            company_name="Innovation Labs",
            description="Different description",
        )
        was_saved, returned_job = await active_jobs_api_with_repository._save_job_if_new(
            duplicate_job, "Innovation Labs"
        )

        assert was_saved is False
        assert active_jobs_api_with_repository._jobs_saved == 0
        assert active_jobs_api_with_repository._jobs_skipped == 1

    @pytest.mark.asyncio
    async def test_save_job_if_new_creates_company_stub(
        self,
        active_jobs_api_with_repository: ActiveJobsDBAPI,
        fake_repository: FakeLeadsRepository,
        sample_job: Job,
    ):
        """Should create company stub when saving a new job."""
        # Verify company does not exist
        exists = await fake_repository.company_exists_by_name("Innovation Labs")
        assert exists is False

        # Save job
        await active_jobs_api_with_repository._save_job_if_new(sample_job, "Innovation Labs")

        # Verify company stub was created
        exists = await fake_repository.company_exists_by_name("Innovation Labs")
        assert exists is True


class TestJobStreamingIntegration:
    """Integration tests for job streaming across multiple API adapters."""

    @pytest.fixture
    def fake_repository(self) -> FakeLeadsRepository:
        """Create a shared FakeLeadsRepository for integration testing."""
        return FakeLeadsRepository()

    @pytest.fixture
    def jsearch_api(
        self, fake_repository: FakeLeadsRepository
    ) -> JsearchAPI:
        """Create a JsearchAPI with shared repository."""
        config = JsearchConfig(
            JSEARCH_API_URL="https://jsearch.p.rapidapi.com",
            RAPIDAPI_API_KEY=["test-key"]
        )
        return JsearchAPI(config, leads_repository=fake_repository)

    @pytest.fixture
    def active_jobs_api(
        self, fake_repository: FakeLeadsRepository
    ) -> ActiveJobsDBAPI:
        """Create an ActiveJobsDBAPI with shared repository."""
        config = ActiveJobsDBConfig(
            ACTIVE_JOBS_DB_URL="https://active-jobs-db.p.rapidapi.com",
            RAPIDAPI_API_KEY=["test-key"]
        )
        return ActiveJobsDBAPI(config, leads_repository=fake_repository)

    @pytest.mark.asyncio
    async def test_deduplication_across_adapters(
        self,
        fake_repository: FakeLeadsRepository,
        jsearch_api: JsearchAPI,
        active_jobs_api: ActiveJobsDBAPI,
    ):
        """Should deduplicate jobs across different API adapters sharing the same repository."""
        job = Job(
            job_title="Full Stack Developer",
            company_name="Shared Company",
            description="Full stack role",
        )

        # Save via JSearch API
        was_saved_jsearch, _ = await jsearch_api._save_job_if_new(job, "Shared Company")
        assert was_saved_jsearch is True
        assert jsearch_api._jobs_saved == 1

        # Try to save same job via Active Jobs DB API - should be detected as duplicate
        was_saved_active, _ = await active_jobs_api._save_job_if_new(job, "Shared Company")
        assert was_saved_active is False
        assert active_jobs_api._jobs_skipped == 1

    @pytest.mark.asyncio
    async def test_company_stub_reuse_across_adapters(
        self,
        fake_repository: FakeLeadsRepository,
        jsearch_api: JsearchAPI,
        active_jobs_api: ActiveJobsDBAPI,
    ):
        """Should reuse company stubs created by one adapter in another."""
        # Create job via JSearch - this creates company stub
        job1 = Job(
            job_title="Frontend Developer",
            company_name="Multi-Source Corp",
        )
        _, saved_job1 = await jsearch_api._save_job_if_new(job1, "Multi-Source Corp")

        # Create different job via Active Jobs DB - should reuse same company
        job2 = Job(
            job_title="Backend Developer",
            company_name="Multi-Source Corp",
        )
        _, saved_job2 = await active_jobs_api._save_job_if_new(job2, "Multi-Source Corp")

        # Both jobs should have the same company_id
        assert saved_job1.company_id == saved_job2.company_id

        # Only one company should exist
        companies = await fake_repository.get_companies(0, 100)
        matching = [c for c in companies.companies if c.name == "Multi-Source Corp"]
        assert len(matching) == 1

    @pytest.mark.asyncio
    async def test_streaming_counters_are_per_adapter(
        self,
        fake_repository: FakeLeadsRepository,
        jsearch_api: JsearchAPI,
        active_jobs_api: ActiveJobsDBAPI,
    ):
        """Should maintain separate streaming counters per adapter."""
        job1 = Job(job_title="DevOps Engineer", company_name="Ops Inc")
        job2 = Job(job_title="SRE Engineer", company_name="Ops Inc")

        await jsearch_api._save_job_if_new(job1, "Ops Inc")
        await active_jobs_api._save_job_if_new(job2, "Ops Inc")

        # Each adapter should have its own counter
        assert jsearch_api._jobs_saved == 1
        assert jsearch_api._jobs_skipped == 0
        assert active_jobs_api._jobs_saved == 1
        assert active_jobs_api._jobs_skipped == 0

    @pytest.mark.asyncio
    async def test_different_jobs_same_company_are_both_saved(
        self,
        fake_repository: FakeLeadsRepository,
        jsearch_api: JsearchAPI,
    ):
        """Should save multiple different jobs for the same company."""
        job1 = Job(job_title="Software Engineer", company_name="Growing Startup")
        job2 = Job(job_title="Product Manager", company_name="Growing Startup")
        job3 = Job(job_title="Data Scientist", company_name="Growing Startup")

        was_saved1, _ = await jsearch_api._save_job_if_new(job1, "Growing Startup")
        was_saved2, _ = await jsearch_api._save_job_if_new(job2, "Growing Startup")
        was_saved3, _ = await jsearch_api._save_job_if_new(job3, "Growing Startup")

        assert was_saved1 is True
        assert was_saved2 is True
        assert was_saved3 is True
        assert jsearch_api._jobs_saved == 3

        # All jobs should exist
        assert await fake_repository.job_exists("Software Engineer", "Growing Startup")
        assert await fake_repository.job_exists("Product Manager", "Growing Startup")
        assert await fake_repository.job_exists("Data Scientist", "Growing Startup")
