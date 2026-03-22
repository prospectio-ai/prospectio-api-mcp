import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from application.use_cases.insert_leads import InsertLeadsUseCase
from domain.entities.company import Company, CompanyEntity
from domain.entities.compatibility_score import CompatibilityScore
from domain.entities.contact import ContactEntity
from domain.entities.job import Job, JobEntity
from domain.entities.leads import Leads
from domain.entities.profile import Profile
from domain.entities.work_experience import WorkExperience
from domain.ports.profile_respository import ProfileRepositoryPort
from domain.ports.task_manager import TaskManagerPort
from domain.services.leads.leads_processor import LeadsProcessor
from domain.services.leads.strategies.active_jobs_db import ActiveJobsDBStrategy
from infrastructure.dto.database.profile import ProfileDTO
from infrastructure.services.active_jobs_db import ActiveJobsDBAPI
from infrastructure.services.compatibility_score import CompatibilityScoreLLM
from infrastructure.services.enrich_leads_agent.agent import EnrichLeadsAgent
from infrastructure.services.enrich_leads_agent.chains.decision_chain import DecisionChain
from infrastructure.services.enrich_leads_agent.chains.enrich_chain import EnrichChain
from infrastructure.services.enrich_leads_agent.models.company_info import CompanyInfo
from infrastructure.services.enrich_leads_agent.models.contact_info import ContactInfo
from infrastructure.services.enrich_leads_agent.models.make_decision import MakeDecisionResult
from infrastructure.services.enrich_leads_agent.models.search_results_model import SearchResultModel
from infrastructure.services.enrich_leads_agent.tools.duck_duck_go_client import DuckDuckGoClient
from infrastructure.services.leads_database import LeadsDatabase
from domain.entities.leads_result import LeadsResult
from infrastructure.services.profile_database import ProfileDatabase
from config import DatabaseConfig, ActiveJobsDBConfig
from domain.ports.enrich_leads import EnrichLeadsPort
from infrastructure.services.task_manager import InMemoryTaskManager

@pytest.fixture(autouse=True)
def patch_database_constructors():
    """
    Patch constructors of LeadsDatabase and ProfileDatabase to avoid DB connection during tests.
    """
    with patch("infrastructure.services.leads_database.LeadsDatabase.__init__", return_value=None), \
         patch("infrastructure.services.profile_database.ProfileDatabase.__init__", return_value=None):
        yield

class TestActiveJobsDBUseCase:
    """Test suite for the Active Jobs DB use case implementation."""

    @pytest.fixture
    def sample_profile_data(self) -> Profile:
        """
        Sample Profile data for testing.
        
        Returns:
            Profile: Mock profile data.
        """
        return Profile(
            job_title="Senior Python Developer",
            location="Paris, France",
            bio="Experienced Python developer with expertise in FastAPI and Clean Architecture",
            work_experience=[
                WorkExperience(
                    company="Tech Solutions",
                    position="Senior Python Developer",
                    start_date="2022-01-01",
                    end_date="2025-01-01",
                    description="Developed and maintained Python applications using FastAPI"
                ),
                WorkExperience(
                    company="StartupCorp",
                    position="Python Developer",
                    start_date="2020-06-01",
                    end_date="2021-12-31",
                    description="Built microservices and REST APIs"
                )
            ],
            technos=["Python", "TensorFlow", "PyTorch"]
        )

    @pytest.fixture
    def sample_profile_dto(self) -> ProfileDTO:
        """
        Sample ProfileDTO data for testing.
        
        Returns:
            ProfileDTO: Mock profile DTO data.
        """
        profile_dto = ProfileDTO()
        profile_dto.id = 1
        profile_dto.job_title = "Senior Python Developer"
        profile_dto.location = "Paris, France"
        profile_dto.bio = "Experienced Python developer with expertise in FastAPI and Clean Architecture"
        profile_dto.work_experience = [
            {
                "company": "Tech Solutions",
                "position": "Senior Python Developer",
                "start_date": "2022-01-01",
                "end_date": "2025-01-01",
                "description": "Developed and maintained Python applications using FastAPI"
            },
            {
                "company": "StartupCorp",
                "position": "Python Developer",
                "start_date": "2020-06-01",
                "end_date": "2021-12-31",
                "description": "Built microservices and REST APIs"
            }
        ]
        return profile_dto

    @pytest.fixture
    def repo_profile_database(self, database_config: DatabaseConfig) -> ProfileDatabase:
        """
        Create a ProfileDatabase instance for testing.
        
        Args:
            database_config: The test configuration.
            
        Returns:
            ProfileDatabase: Configured profile database repository.
        """
        return ProfileDatabase(database_config.DATABASE_URL)

    @pytest.fixture
    def active_jobs_db_config(self) -> ActiveJobsDBConfig:
        """
        Create a test configuration for Active Jobs DB API.
        
        Returns:
            ActiveJobsDBConfig: Test configuration object.
        """
        return ActiveJobsDBConfig(
            ACTIVE_JOBS_DB_URL="https://active-jobs-db.p.rapidapi.com",
            RAPIDAPI_API_KEY=["test-rapidapi-key"]
        )

    @pytest.fixture
    def sample_active_jobs_response(self) -> list:
        """
        Sample Active Jobs DB response from Active Jobs DB API.
        
        Returns:
            list: Mock Active Jobs DB response data.
        """
        return [
            {
                "id": "active_job_1",
                "date_posted": "2025-01-01",
                "date_created": "2025-01-01T10:00:00Z",
                "title": "Senior Python Developer",
                "organization": "Innovation Labs",
                "organization_url": "https://innovationlabs.com",
                "date_validthrough": "2025-02-01",
                "locations_raw": [
                    {
                        "@type": "Place",
                        "address": {
                            "@type": "PostalAddress",
                            "addressCountry": "FR",
                            "addressLocality": "Paris",
                            "addressRegion": "Île-de-France"
                        }
                    }
                ],
                "locations_alt_raw": ["Paris, France"],
                "location_type": "onsite",
                "location_requirements_raw": [
                    {
                        "@type": "LocationRequirement",
                        "name": "Paris"
                    }
                ],
                "salary_raw": {
                    "min": 85000,
                    "max": 125000,
                    "currency": "EUR"
                },
                "employment_type": ["FULL_TIME"],
                "url": "https://innovationlabs.com/careers/python-dev",
                "source_type": "company_website",
                "source": "innovationlabs.com",
                "source_domain": "innovationlabs.com",
                "organization_logo": "https://logo.clearbit.com/innovationlabs.com",
                "cities_derived": ["Paris"],
                "regions_derived": ["Île-de-France"],
                "countries_derived": ["France"],
                "locations_derived": ["Paris, France"],
                "timezones_derived": ["Europe/Paris"],
                "lats_derived": [48.8566],
                "lngs_derived": [2.3522],
                "remote_derived": False,
                "domain_derived": "innovationlabs.com",
                "description_text": "We are seeking a Senior Python Developer to join our innovative team..."
            },
            {
                "id": "active_job_2",
                "date_posted": "2025-01-02",
                "date_created": "2025-01-02T14:30:00Z",
                "title": "Python Backend Engineer",
                "organization": "DataTech Solutions",
                "organization_url": "https://datatech.fr",
                "date_validthrough": "2025-02-15",
                "locations_raw": [
                    {
                        "@type": "Place",
                        "address": {
                            "@type": "PostalAddress",
                            "addressCountry": "FR",
                            "addressLocality": "Lyon",
                            "addressRegion": "Auvergne-Rhône-Alpes"
                        }
                    }
                ],
                "locations_alt_raw": ["Lyon, France"],
                "location_type": "hybrid",
                "location_requirements_raw": [
                    {
                        "@type": "LocationRequirement",
                        "name": "Lyon"
                    }
                ],
                "salary_raw": {
                    "min": 70000,
                    "max": 95000,
                    "currency": "EUR"
                },
                "employment_type": ["FULL_TIME", "CONTRACT"],
                "url": "https://datatech.fr/jobs/backend-python",
                "source_type": "job_board",
                "source": "datatech.fr",
                "source_domain": "datatech.fr",
                "organization_logo": "https://logo.clearbit.com/datatech.fr",
                "cities_derived": ["Lyon"],
                "regions_derived": ["Auvergne-Rhône-Alpes"],
                "countries_derived": ["France"],
                "locations_derived": ["Lyon, France"],
                "timezones_derived": ["Europe/Paris"],
                "lats_derived": [45.7640],
                "lngs_derived": [4.8357],
                "remote_derived": False,
                "domain_derived": "datatech.fr",
                "description_text": "Join our data engineering team as a Python Backend Engineer..."
            }
        ]

    @pytest.fixture
    def active_jobs_db_api(self, active_jobs_db_config: ActiveJobsDBConfig) -> ActiveJobsDBAPI:
        """
        Create an ActiveJobsDBAPI instance for testing.
        
        Args:
            active_jobs_db_config: The test configuration.
            
        Returns:
            ActiveJobsDBAPI: Configured Active Jobs DB API adapter.
        """
        return ActiveJobsDBAPI(active_jobs_db_config)

    @pytest.fixture
    def active_jobs_db_strategy(self, active_jobs_db_api: ActiveJobsDBAPI) -> ActiveJobsDBStrategy:
        """
        Create an ActiveJobsDBStrategy instance for testing.
        
        Args:
            active_jobs_db_api: The Active Jobs DB API adapter.
            
        Returns:
            ActiveJobsDBStrategy: Configured Active Jobs DB strategy.
        """
        return ActiveJobsDBStrategy(
            location="France",
            job_title=["Python Developer", "Backend Engineer"],
            port=active_jobs_db_api
        )

    @pytest.fixture
    def active_jobs_db_repository(self) -> LeadsDatabase:
        """
        Create an ActiveJobsDBStrategy instance for testing.
        
        Args:
            active_jobs_db_api: The Active Jobs DB API adapter.
            
        Returns:
            ActiveJobsDBStrategy: Configured Active Jobs DB strategy.
        """
        return LeadsDatabase(DatabaseConfig().DATABASE_URL) # type: ignore
    
    @pytest.fixture
    def compatibility_score_llm(self) -> CompatibilityScore:
        """
        Create a mock CompatibilityScoreLLM for testing.
        
        Returns:
            CompatibilityScore: Mocked compatibility score.
        """
        return CompatibilityScore(score=85)
    
    @pytest.fixture
    def profile_repository(self) -> ProfileRepositoryPort:
        """
        Create a mock ProfileRepositoryPort for testing.
        
        Returns:
            ProfileRepositoryPort: Mocked profile repository.
        """
        return ProfileDatabase(DatabaseConfig().DATABASE_URL) # type: ignore
    
    @pytest.fixture
    def leads_processor(self) -> LeadsProcessor:
        """
        Create a LeadsProcessor instance for testing.
        
        Returns:
            LeadsProcessor: Configured leads processor.
        """
        return LeadsProcessor(
            compatibility_score_port=CompatibilityScoreLLM()
        )
    
    @pytest.fixture
    def task_manager(self) -> TaskManagerPort:
        """
        Create a InMemoryTaskManager for testing.

        Returns:
            InMemoryTaskManager: Configured task manager.
        """
        return InMemoryTaskManager()

    @pytest.fixture
    def enrich_leads(self, task_manager: TaskManagerPort) -> EnrichLeadsPort:
        """
        Create a  EnrichLeadsPort for testing.

        Returns:
            EnrichLeadsPort: Configured enrich leads agent.
        """
        return EnrichLeadsAgent(task_manager)

    @pytest.fixture
    def decide_enrichment(self) -> MakeDecisionResult:
        """
        Create a mock MakeDecisionResult for testing.
        
        Returns:
            MakeDecisionResult: Mocked decision result.
        """
        return MakeDecisionResult(result=True)

    @pytest.fixture
    def company_info(self) -> CompanyInfo:
        """
        Create a mock CompanyInfo for testing.

        Returns:
            CompanyInfo: Mocked company info.
        """
        return CompanyInfo(
            industry=["Technology"], 
            compatibility="20", 
            location=["Paris"], 
            size="51-200", 
            revenue="10M-50M"
        )
    
    @pytest.fixture
    def contact_info(self) -> ContactInfo:
        """
        Create a mock ContactInfo for testing.

        Returns:
            ContactInfo: Mocked contact info.
        """
        return ContactInfo(
            name="John Doe",
            email=["john.doe@example.com"],
            title="Software Engineer",
            phone="123-456-7890",
            profile_url=["https://linkedin.com/in/johndoe"]
        )
    
    @pytest.fixture
    def job_titles(self) -> list[str]:
        """
        Create a mock list of job titles for testing.

        Returns:
            list[str]: Mocked job titles.
        """
        return ["Senior Python Developer", "Backend Engineer"]
    
    @pytest.fixture
    def crawl_page(self) -> str:
        """
        Create a mock crawled page content for testing.

        Returns:
            str: Mocked crawled page content.
        """
        return "<p>This is a mock crawled page content with company information.</p>"
    
    @pytest.fixture
    def search(self) -> list[SearchResultModel]:
        """
        Create a mock list of search results for testing.

        Returns:
            list[SearchResultModel]: Mocked search results.
        """
        return [
            SearchResultModel(
                title="John Doe - Software Engineer - LinkedIn",
                url="https://linkedin.com/in/johndoe",
                snippet="Experienced Software Engineer with expertise in Python and FastAPI."
            ),
            SearchResultModel(
                title="Jane Smith - Backend Developer - LinkedIn",
                url="https://linkedin.com/in/janesmith",
                snippet="Skilled Backend Developer specializing in microservices and REST APIs."
            )
        ]
    
    @pytest.fixture
    def database_config(self) -> DatabaseConfig:
        """
        Create a test configuration for Database.
        
        Returns:
            DatabaseConfig: Test configuration object.
        """
        return DatabaseConfig() # type: ignore
    
    @pytest.fixture
    def mock_profile_database(self) -> Profile:
        """
        Create a ProfileDatabase instance for testing.
        
        Args:
            database_config: The test configuration.
            
        Returns:
            ProfileDatabase: Configured profile database repository.
        """
        return Profile(
            job_title="AI Developper",
            location="Remote",
            bio="Experienced AI developer with expertise in machine learning and data science",
            work_experience=[],
            technos=["Python", "TensorFlow", "PyTorch"]
        )
    
    @pytest.fixture
    def companies_database(self) -> CompanyEntity:
        """
        Build a CompanyEntity object simulating companies already present in DB, matching the API response.

        Args:
            active_jobs_response (list): The mock response from Active Jobs DB API.

        Returns:
            Leads: The Leads entity as it would be present in DB.
        """
        companies = CompanyEntity(companies=[
            Company(
                id="38aeceee-254d-44c8-92b5-33a1d32e8d82",
                name="Innovation Labs",
                industry=None,
                compatibility=None,
                source="active_jobs_db",
                location=None,
                size=None,
                revenue=None,
                website="https://innovationlabs.com",
                description=None,
                opportunities=None
            ),
            Company(
                id="6e88cd46-e213-4170-b9ae-aa5380867563",
                name="DataTech Solutions",
                industry=None,
                compatibility=None,
                source="active_jobs_db",
                location=None,
                size=None,
                revenue=None,
                website="https://datatech.fr",
                description=None,
                opportunities=None
            )
        ], pages=1)
        return companies
    
    @pytest.fixture
    def jobs_database(self) -> JobEntity:
        """
        Create a mock JobEntity for testing.
        """
        jobs = JobEntity(jobs=[
                Job(
                    id="6b38fd8d-3f82-42d6-ae90-247c3f3320b0",
                    company_id="38aeceee-254d-44c8-92b5-33a1d32e8d82",
                    date_creation="2025-01-01",
                    description="We are seeking a Senior Python Developer to join our innovative team...",
                    job_title="Senior Python Developer",
                    location="Paris, France",
                    salary="{'min': 85000, 'max': 125000, 'currency': 'EUR'}",
                    job_seniority=None,
                    job_type="FULL_TIME",
                    sectors=None,
                    apply_url=["https://innovationlabs.com/careers/python-dev"],
                    compatibility_score=None
                ), # type: ignore
                Job(
                    id="bcffd4b0-8318-49f9-8cb3-d999027d03ea",
                    company_id="6e88cd46-e213-4170-b9ae-aa5380867563",
                    date_creation="2025-01-02",
                    description="Join our data engineering team as a Python Backend Engineer...",
                    job_title="Python Backend Engineer",
                    location="Lyon, France",
                    salary="{'min': 70000, 'max': 95000, 'currency': 'EUR'}",
                    job_seniority=None,
                    job_type="FULL_TIME, CONTRACT",
                    sectors=None,
                    apply_url=["https://datatech.fr/jobs/backend-python"],
                    compatibility_score=None
                ) # type: ignore
            ]
        ) # type: ignore
        return jobs

    @pytest.fixture
    def use_case(self, 
                 active_jobs_db_strategy: ActiveJobsDBStrategy, 
                 active_jobs_db_repository: LeadsDatabase, 
                 leads_processor: LeadsProcessor,
                 profile_repository: ProfileRepositoryPort,
                 enrich_leads: EnrichLeadsPort,
                 task_manager: TaskManagerPort
    ) -> InsertLeadsUseCase:
        """
        Create a GetCompanyJobsUseCase instance for testing.
        
        Args:
            active_jobs_db_strategy: The Active Jobs DB strategy.
            
        Returns:
            GetCompanyJobsUseCase: Configured use case.
        """
        return InsertLeadsUseCase(
            task_uuid="test-task-uuid",
            strategy=active_jobs_db_strategy, 
            repository=active_jobs_db_repository, 
            leads_processor=leads_processor, 
            profile_repository=profile_repository,
            enrich_leads=enrich_leads,
            task_manager=task_manager
        )

    @pytest.mark.asyncio
    async def test_get_leads_success(
        self,
        use_case: InsertLeadsUseCase,
        sample_active_jobs_response: list,
        compatibility_score_llm: CompatibilityScore,
        decide_enrichment: MakeDecisionResult,
        company_info: CompanyInfo,
        contact_info: ContactInfo,
        job_titles: list[str],
        crawl_page: str,
        search: list[SearchResultModel],
        mock_profile_database: Profile
    ) -> None:
        """
        Test successful lead retrieval from Active Jobs DB API.
        
        Args:
            use_case: The configured use case.
            sample_active_jobs_response: Mock Active Jobs DB response.
        """
        # Mock the HTTP response
        active_jobs_response_mock = MagicMock()
        active_jobs_response_mock.status_code = 200
        active_jobs_response_mock.json.return_value = sample_active_jobs_response

        with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get, \
            patch.object(CompatibilityScoreLLM, 'get_compatibility_score', new_callable=AsyncMock) as mock_score, \
            patch.object(EnrichChain, 'get_company_description', new_callable=AsyncMock) as mock_description, \
            patch.object(DecisionChain, 'decide_enrichment', new_callable=AsyncMock) as mock_decide, \
            patch.object(EnrichChain, 'extract_other_info_from_description', new_callable=AsyncMock) as mock_company_info, \
            patch.object(EnrichChain, 'extract_contact_from_web_search', new_callable=AsyncMock) as mock_contact_info, \
            patch.object(EnrichChain, 'extract_interesting_job_titles_from_profile', new_callable=AsyncMock) as mock_job_titles, \
            patch.object(DuckDuckGoClient, 'search', new_callable=AsyncMock) as mock_search, \
            patch.object(use_case, 'profile_repository', autospec=True) as mock_profile_repo, \
            patch.object(use_case, 'repository', autospec=True) as mock_repo:

            mock_profile_repo.get_profile = AsyncMock(return_value=mock_profile_database)

            mock_get.return_value = active_jobs_response_mock
            mock_score.return_value = compatibility_score_llm
            mock_description.return_value = "Mock company description"
            mock_decide.return_value = decide_enrichment
            mock_company_info.return_value = company_info
            mock_contact_info.return_value = contact_info
            mock_job_titles.return_value = job_titles
            mock_search.return_value = search

            mock_repo.save_leads = AsyncMock(return_value=None)
            mock_repo.get_jobs = AsyncMock(return_value=JobEntity(jobs=[])) # type: ignore
            mock_repo.get_companies = AsyncMock(return_value=CompanyEntity(companies=[], pages=1))
            mock_repo.get_contacts = AsyncMock(return_value=ContactEntity(contacts=[], pages=1)) # type: ignore
            mock_repo.get_jobs_by_title_and_location = AsyncMock(return_value=JobEntity(jobs=[])) # type: ignore
            mock_repo.get_companies_by_names = AsyncMock(return_value=CompanyEntity(companies=[])) # type: ignore
            mock_repo.get_contacts_by_name_and_title = AsyncMock(return_value=ContactEntity(contacts=[])) # type: ignore
            mock_repo.get_leads = AsyncMock(return_value=None)

            result = await use_case.insert_leads()
            task = await use_case.task_manager.get_task_status("test-task-uuid")

            assert isinstance(result, LeadsResult)
            assert result.companies == "Insert of 2 companies"
            assert result.jobs == "insert of 2 jobs"
            assert result.contacts == "insert of 0 contacts"
            assert task.status == "completed"

    @pytest.mark.asyncio
    async def test_get_leads_success_no_insert(
        self,
        use_case: InsertLeadsUseCase,
        sample_active_jobs_response: list,
        compatibility_score_llm: CompatibilityScore,
        decide_enrichment: MakeDecisionResult,
        company_info: CompanyInfo,
        contact_info: ContactInfo,
        job_titles: list[str],
        crawl_page: str,
        search: list[SearchResultModel],
        mock_profile_database: Profile,
        companies_database: CompanyEntity,
        jobs_database: JobEntity
    ) -> None:
        """
        Test successful lead retrieval from Active Jobs DB API.
        
        Args:
            use_case: The configured use case.
            sample_active_jobs_response: Mock Active Jobs DB response.
        """
        # Mock the HTTP response
        active_jobs_response_mock = MagicMock()
        active_jobs_response_mock.status_code = 200
        active_jobs_response_mock.json.return_value = sample_active_jobs_response

        with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get, \
            patch.object(CompatibilityScoreLLM, 'get_compatibility_score', new_callable=AsyncMock) as mock_score, \
            patch.object(EnrichChain, 'get_company_description', new_callable=AsyncMock) as mock_description, \
            patch.object(DecisionChain, 'decide_enrichment', new_callable=AsyncMock) as mock_decide, \
            patch.object(EnrichChain, 'extract_other_info_from_description', new_callable=AsyncMock) as mock_company_info, \
            patch.object(EnrichChain, 'extract_contact_from_web_search', new_callable=AsyncMock) as mock_contact_info, \
            patch.object(EnrichChain, 'extract_interesting_job_titles_from_profile', new_callable=AsyncMock) as mock_job_titles, \
            patch.object(DuckDuckGoClient, 'search', new_callable=AsyncMock) as mock_search, \
            patch.object(use_case, 'repository', autospec=True) as mock_repo, \
            patch.object(use_case, 'profile_repository', autospec=True) as mock_profile_repo:

            mock_profile_repo.get_profile = AsyncMock(return_value=mock_profile_database)

            mock_get.return_value = active_jobs_response_mock
            mock_score.return_value = compatibility_score_llm
            mock_description.return_value = "Mock company description"
            mock_decide.return_value = decide_enrichment
            mock_company_info.return_value = company_info
            mock_contact_info.return_value = contact_info
            mock_job_titles.return_value = job_titles
            mock_search.return_value = search
            
            mock_repo.save_leads = AsyncMock(return_value=None)
            mock_repo.get_jobs = AsyncMock(return_value=JobEntity(jobs=[])) # type: ignore
            mock_repo.get_companies = AsyncMock(return_value=CompanyEntity(companies=[], pages=1))
            mock_repo.get_contacts = AsyncMock(return_value=ContactEntity(contacts=[], pages=1))
            mock_repo.get_jobs_by_title_and_location = AsyncMock(return_value=jobs_database)
            mock_repo.get_companies_by_names = AsyncMock(return_value=companies_database)
            mock_repo.get_contacts_by_name_and_title = AsyncMock(return_value=ContactEntity(contacts=[])) # type: ignore
            mock_repo.get_leads = AsyncMock(return_value=None)

            mock_get.return_value = active_jobs_response_mock

            result = await use_case.insert_leads()
            task = await use_case.task_manager.get_task_status("test-task-uuid")

            assert isinstance(result, LeadsResult)
            assert result.companies == "Insert of 0 companies"
            assert result.jobs == "insert of 0 jobs"
            assert result.contacts == "insert of 0 contacts"
            assert task.status == "completed"
