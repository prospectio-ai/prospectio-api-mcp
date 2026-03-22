import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from application.use_cases.insert_leads import InsertLeadsUseCase
from domain.entities.company import Company, CompanyEntity
from domain.entities.compatibility_score import CompatibilityScore
from domain.entities.contact import ContactEntity
from domain.entities.job import Job, JobEntity
from domain.entities.profile import Profile
from domain.ports.enrich_leads import EnrichLeadsPort
from domain.ports.profile_respository import ProfileRepositoryPort
from domain.ports.task_manager import TaskManagerPort
from domain.services.leads.leads_processor import LeadsProcessor
from domain.services.leads.strategies.jsearch import JsearchStrategy
from infrastructure.services.compatibility_score import CompatibilityScoreLLM
from infrastructure.services.enrich_leads_agent.agent import EnrichLeadsAgent
from infrastructure.services.enrich_leads_agent.chains.decision_chain import DecisionChain
from infrastructure.services.enrich_leads_agent.chains.enrich_chain import EnrichChain
from infrastructure.services.enrich_leads_agent.models.company_info import CompanyInfo
from infrastructure.services.enrich_leads_agent.models.contact_info import ContactInfo
from infrastructure.services.enrich_leads_agent.models.make_decision import MakeDecisionResult
from infrastructure.services.enrich_leads_agent.models.search_results_model import SearchResultModel
from infrastructure.services.enrich_leads_agent.tools.duck_duck_go_client import DuckDuckGoClient
from infrastructure.services.jsearch import JsearchAPI
from config import DatabaseConfig, JsearchConfig
from infrastructure.services.leads_database import LeadsDatabase
from domain.entities.leads_result import LeadsResult
from infrastructure.services.profile_database import ProfileDatabase
from infrastructure.services.task_manager import InMemoryTaskManager

class TestJsearchUseCase:
    """Test suite for the JSearch use case implementation."""

    @pytest.fixture
    def jsearch_config(self) -> JsearchConfig:
        """
        Create a test configuration for JSearch API.
        
        Returns:
            JsearchConfig: Test configuration object.
        """
        return JsearchConfig(
            JSEARCH_API_URL="https://jsearch.p.rapidapi.com",
            RAPIDAPI_API_KEY=["test-rapidapi-key"]
        )

    @pytest.fixture
    def sample_jsearch_response(self) -> dict:
        """
        Sample JSearch response from JSearch API.
        
        Returns:
            dict: Mock JSearch response data.
        """
        return {
            "status": "OK",
            "request_id": "test-request-123",
            "parameters": {
                "query": "Python Developer in France",
                "page": 1,
                "num_pages": 1,
                "date_posted": "month",
                "country": "fr",
                "language": "en"
            },
            "data": [
                {
                    "job_id": "jsearch_job_1",
                    "job_title": "Senior Python Developer",
                    "employer_name": "Tech Solutions",
                    "employer_logo": "https://logo.clearbit.com/techsolutions.com",
                    "employer_website": "https://techsolutions.com",
                    "employer_company_type": "Technology",
                    "employer_linkedin": "https://linkedin.com/company/techsolutions",
                    "job_publisher": "LinkedIn",
                    "job_employment_type": "FULLTIME",
                    "job_employment_types": ["FULLTIME"],
                    "job_employment_type_text": "Full-time",
                    "job_apply_link": "https://jobs.techsolutions.com/apply/python-dev",
                    "job_apply_is_direct": True,
                    "job_apply_quality_score": 0.95,
                    "job_description": "We are looking for a Senior Python Developer to join our team...",
                    "job_is_remote": False,
                    "job_posted_human_readable": "2 days ago",
                    "job_posted_at_timestamp": 1735689600,
                    "job_posted_at_datetime_utc": "2025-01-01T00:00:00Z",
                    "job_location": "Paris, France",
                    "job_city": "Paris",
                    "job_state": "Île-de-France",
                    "job_country": "FR",
                    "job_latitude": 48.8566,
                    "job_longitude": 2.3522,
                    "job_benefits": "Health insurance, 401k, Remote work",
                    "job_google_link": "https://www.google.com/search?q=python+developer+paris",
                    "job_offer_expiration_datetime_utc": "2025-02-01T00:00:00Z",
                    "job_offer_expiration_timestamp": 1738368000,
                    "job_required_experience": {
                        "no_experience_required": False,
                        "required_experience_in_months": 60,
                        "experience_mentioned": True,
                        "experience_preferred": True
                    },
                    "job_salary": "€80,000 - €120,000",
                    "job_min_salary": 80000.0,
                    "job_max_salary": 120000.0,
                    "job_salary_currency": "EUR",
                    "job_salary_period": "YEAR",
                    "job_highlights": {
                        "qualifications": [
                            "5+ years of Python experience",
                            "Experience with FastAPI",
                            "Knowledge of Clean Architecture"
                        ],
                        "responsibilities": [
                            "Develop and maintain Python applications",
                            "Work with cross-functional teams",
                            "Mentor junior developers"
                        ]
                    },
                    "job_job_title": "Senior Python Developer",
                    "job_posting_language": "en",
                    "job_onet_soc": "15113200",
                    "job_onet_job_zone": "4",
                    "job_occupational_categories": ["Technology", "Software Development"],
                    "job_naics_code": "541511",
                    "job_naics_name": "Custom Computer Programming Services"
                }
            ]
        }

    @pytest.fixture
    def jsearch_api(self, jsearch_config: JsearchConfig) -> JsearchAPI:
        """
        Create a JsearchAPI instance for testing.
        
        Args:
            jsearch_config: The test configuration.
            
        Returns:
            JsearchAPI: Configured JSearch API adapter.
        """
        return JsearchAPI(jsearch_config)

    @pytest.fixture
    def jsearch_strategy(self, jsearch_api: JsearchAPI) -> JsearchStrategy:
        """
        Create a JsearchStrategy instance for testing.
        
        Args:
            jsearch_api: The JSearch API adapter.
            
        Returns:
            JsearchStrategy: Configured JSearch strategy.
        """
        return JsearchStrategy(
            location="france",
            job_title=["python developer", "senior developer"],
            port=jsearch_api
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
            technos=[]
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
                name="Tech Solutions",
                industry=None,
                compatibility=None,
                source="jsearch",
                location=None,
                size=None,
                revenue=None,
                website="https://techsolutions.com",
                description=None,
                opportunities=None
            )
        ], pages=1)
        return companies
    
    @pytest.fixture
    def jobs_database(self) -> JobEntity:
        """
        Create a mock JobEntity for testing, with a job that matches the JSearch API mock response so it is detected as 'already present'.
        """
        jobs = JobEntity(jobs=[
            Job(
                id="jsearch_job_1",
                company_id="38aeceee-254d-44c8-92b5-33a1d32e8d82",  # lowercased
                date_creation="2025-01-01T00:00:00Z",
                description="we are looking for a senior python developer to join our team...",  # lowercased
                job_title="senior python developer",  # lowercased
                location="paris, france",  # lowercased
                salary="{'min': 80000, 'max': 120000, 'currency': 'EUR'}",
                job_seniority=None,
                job_type="fulltime",  # lowercased
                sectors="Technology, Software Development",
                apply_url=["https://jobs.techsolutions.com/apply/python-dev"],
                compatibility_score=None
            ) # type: ignore
        ], pages=1)
        return jobs

    @pytest.fixture
    def use_case(self, 
                 jsearch_strategy: JsearchStrategy, 
                 active_jobs_db_repository: LeadsDatabase, 
                 leads_processor: LeadsProcessor,
                 profile_repository: ProfileRepositoryPort,
                 enrich_leads: EnrichLeadsPort,
                task_manager: TaskManagerPort
    ) -> InsertLeadsUseCase:
        """
        Create a GetCompanyJobsUseCase instance for testing.
        
        Args:
            jsearch_strategy: The JSearch strategy.
            
        Returns:
            GetCompanyJobsUseCase: Configured use case.
        """
        return InsertLeadsUseCase(
            task_uuid="test-task-uuid",
            strategy=jsearch_strategy, 
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
        sample_jsearch_response: dict,
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
        Test successful lead retrieval from JSearch API.
        
        Args:
            use_case: The configured use case.
            sample_jsearch_response: Mock JSearch response.
        """
        # Mock the HTTP response
        jsearch_response_mock = MagicMock()
        jsearch_response_mock.status_code = 200
        jsearch_response_mock.json.return_value = sample_jsearch_response

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

            mock_get.return_value = jsearch_response_mock
            mock_score.return_value = compatibility_score_llm
            mock_description.return_value = "Mock company description"
            mock_decide.return_value = decide_enrichment
            mock_company_info.return_value = company_info
            mock_contact_info.return_value = contact_info
            mock_job_titles.return_value = job_titles
            mock_crawl.return_value = crawl_page
            mock_search.return_value = search

            mock_repo.save_leads = AsyncMock(return_value=None)
            mock_repo.get_jobs = AsyncMock(return_value=JobEntity(jobs=[], pages=1))
            mock_repo.get_companies = AsyncMock(return_value=CompanyEntity(companies=[], pages=1))
            mock_repo.get_contacts = AsyncMock(return_value=ContactEntity(contacts=[], pages=1)) # type: ignore
            mock_repo.get_jobs_by_title_and_location = AsyncMock(return_value=JobEntity(jobs=[])) # type: ignore
            mock_repo.get_companies_by_names = AsyncMock(return_value=CompanyEntity(companies=[])) # type: ignore
            mock_repo.get_contacts_by_name_and_title = AsyncMock(return_value=ContactEntity(contacts=[])) # type: ignore
            mock_repo.get_leads = AsyncMock(return_value=None)
            # Execute the use case
            result = await use_case.insert_leads()
            task = await use_case.task_manager.get_task_status("test-task-uuid")
            
            # Verify result type
            assert isinstance(result, LeadsResult)

            # Verify result content
            assert result.companies == "Insert of 1 companies"
            assert result.jobs == "insert of 1 jobs"
            assert result.contacts == "insert of 0 contacts"
            assert task.status == "completed"

    @pytest.mark.asyncio
    async def test_get_leads_success_no_insert(
        self,
        use_case: InsertLeadsUseCase,
        sample_jsearch_response: dict,
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
        Test successful lead retrieval from JSearch API.
        
        Args:
            use_case: The configured use case.
            sample_jsearch_response: Mock JSearch response.
        """
        # Mock the HTTP response
        jsearch_response_mock = MagicMock()
        jsearch_response_mock.status_code = 200
        jsearch_response_mock.json.return_value = sample_jsearch_response

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

            mock_get.return_value = jsearch_response_mock
            mock_score.return_value = compatibility_score_llm
            mock_description.return_value = "Mock company description"
            mock_decide.return_value = decide_enrichment
            mock_company_info.return_value = company_info
            mock_contact_info.return_value = contact_info
            mock_job_titles.return_value = job_titles
            mock_crawl.return_value = crawl_page
            mock_search.return_value = search
            
            mock_repo.save_leads = AsyncMock(return_value=None)
            mock_repo.get_jobs = AsyncMock(return_value=JobEntity(jobs=[], pages=1))
            mock_repo.get_companies = AsyncMock(return_value=CompanyEntity(companies=[], pages=1))
            mock_repo.get_contacts = AsyncMock(return_value=ContactEntity(contacts=[], pages=1))
            mock_repo.get_jobs_by_title_and_location = AsyncMock(return_value=jobs_database)
            mock_repo.get_companies_by_names = AsyncMock(return_value=companies_database)
            mock_repo.get_contacts_by_name_and_title = AsyncMock(return_value=ContactEntity(contacts=[])) # type: ignore
            mock_repo.get_leads = AsyncMock(return_value=None)
            
            # Execute the use case
            result = await use_case.insert_leads()
            task = await use_case.task_manager.get_task_status("test-task-uuid")
            
            # Verify result type
            assert isinstance(result, LeadsResult)

            # Verify result content
            assert result.companies == "Insert of 0 companies"
            assert result.jobs == "insert of 0 jobs"
            assert result.contacts == "insert of 0 contacts"
            assert task.status == "completed"
