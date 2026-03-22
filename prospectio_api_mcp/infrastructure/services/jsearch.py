from uuid import uuid4
import httpx
import logging
from typing import Optional
from prospectio_api_mcp.domain.ports.fetch_leads import FetchLeadsPort
from prospectio_api_mcp.domain.ports.leads_repository import LeadsRepositoryPort
from infrastructure.dto.rapidapi.jsearch import JSearchResponseDTO
from config import JsearchConfig
from infrastructure.api.client import BaseApiClient
from domain.entities.company import Company, CompanyEntity
from domain.entities.job import Job, JobEntity
from prospectio_api_mcp.domain.entities.leads import Leads
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


class JsearchAPI(FetchLeadsPort):
    """
    Adapter for the JSearch API to fetch job data.
    Supports streaming jobs to database as they are fetched.
    """

    def __init__(
        self,
        config: JsearchConfig,
        leads_repository: Optional[LeadsRepositoryPort] = None,
    ) -> None:
        """
        Initialize JSearchAPI with configuration.

        Args:
            config (JSearchConfig): JSearch API configuration object.
            leads_repository (Optional[LeadsRepositoryPort]): Repository for streaming jobs to database.
        """
        self.api_base = config.JSEARCH_API_URL
        self.api_keys = config.RAPIDAPI_API_KEY
        self.search_endpoint = "/search"
        self.leads_repository = leads_repository
        self._jobs_saved = 0
        self._jobs_skipped = 0

    def _get_headers(self, api_key: str) -> dict[str, str]:
        """
        Get headers for API requests with the specified API key.

        Args:
            api_key (str): The RapidAPI key to use.

        Returns:
            dict[str, str]: Headers for the API request.
        """
        return {
            "accept": "application/json",
            "x-rapidapi-host": self.api_base.split("//")[-1].split("/")[0],
            "x-rapidapi-key": api_key,
        }
    
    async def _make_request_with_retry(self, endpoint: str, params: dict, key_index: int = 0) -> JSearchResponseDTO:
        """
        Make API request with recursive retry logic for different API keys on 429 errors.

        Args:
            endpoint (str): The API endpoint to call.
            params (dict): Request parameters.
            key_index (int): Current key index to try.

        Returns:
            JSearchResponseDTO: The parsed response data.

        Raises:
            RuntimeError: If all API keys are exhausted or other errors occur.
        """
        if key_index >= len(self.api_keys):
            raise RuntimeError("All API keys exhausted due to rate limiting")

        headers = self._get_headers(self.api_keys[key_index])
        client = BaseApiClient(self.api_base, headers)
        result = await client.get(endpoint, params)
        
        if result.status_code == 429:
            await client.close()
            return await self._make_request_with_retry(endpoint, params, key_index + 1)
        
        return await self._check_error(client, result, JSearchResponseDTO)

    async def _check_error[T](
        self, client: BaseApiClient, result: httpx.Response, dto_type: type[T]
    ) -> T:
        """
        Check the HTTP response for errors and parse the response into the given DTO type.
        Closes the client after processing.

        Args:
            client (BaseApiClient): The API client instance to close.
            result (httpx.Response): The HTTP response from the API call.
            dto_type (type[T]): The DTO class to parse the response into.

        Raises:
            RuntimeError: If the response status code is not 200.

        Returns:
            T: An instance of the DTO type with the response data.
        """
        if result.status_code != 200:
            await client.close()
            raise RuntimeError(f"Failed to fetch leads: {result.text}")
        dto = dto_type(**result.json())
        await client.close()
        return dto

    async def to_company_entity(
        self, dto: JSearchResponseDTO
    ) -> tuple[CompanyEntity, list[str], list[str]]:
        """
        Convert JSearch response DTO to CompanyEntity.

        Args:
            dto (JSearchResponseDTO): The JSearch API response data.

        Returns:
            tuple[CompanyEntity, list[str], list[str]]: Entity containing companies,
                their IDs, and their names.
        """
        companies: list[Company] = []
        ids: list[str] = []
        names: list[str] = []
        for jsearch_company in dto.data if dto.data else []:
            company = Company(  # type: ignore
                id=str(uuid4()), name=jsearch_company.employer_name, source="jsearch"
            )
            ids.append(company.id or str(uuid4()))
            names.append(jsearch_company.employer_name or "")
            companies.append(company)
        return CompanyEntity(companies=companies), ids, names # type: ignore

    async def _save_job_if_new(self, job: Job, company_name: str) -> tuple[bool, Job]:
        """
        Save a job to the database if it does not already exist.

        Args:
            job: The job entity to save.
            company_name: The name of the company for deduplication.

        Returns:
            tuple[bool, Job]: (was_saved, job_with_id)
        """
        if not self.leads_repository:
            return False, job

        if not job.job_title or not company_name:
            logger.warning("Job missing title or company name, skipping save")
            return False, job

        # Check if job already exists
        exists = await self.leads_repository.job_exists(job.job_title, company_name)
        if exists:
            logger.info(f"Job '{job.job_title}' at '{company_name}' already exists, skipping")
            self._jobs_skipped += 1
            return False, job

        # Get or create company stub to satisfy FK constraint
        company = await self.leads_repository.get_or_create_company_stub(company_name)
        job.company_id = company.id

        # Save the job
        saved_job = await self.leads_repository.save_job(job)
        logger.info(f"Saved job '{job.job_title}' at '{company_name}' with ID: {saved_job.id}")
        self._jobs_saved += 1
        return True, saved_job

    async def to_job_entity(
        self, dto: JSearchResponseDTO, ids: list[str], company_names: list[str]
    ) -> JobEntity:
        """
        Convert JSearch response DTO to JobEntity.
        If leads_repository is set, streams jobs to database as they are created.

        Args:
            dto (JSearchResponseDTO): The JSearch API response data.
            ids (list[str]): List of company IDs.
            company_names (list[str]): List of company names for deduplication.

        Returns:
            JobEntity: Entity containing jobs from JSearch data.
        """
        jobs: list[Job] = []
        for index, job in enumerate(dto.data) if dto.data else []:
            job.job_id = str(uuid4())
            company_name = company_names[index] if index < len(company_names) else ""
            job_entity = Job(  # type: ignore
                id=job.job_id,
                company_id=ids[index] if index < len(ids) else None,
                company_name=company_name,
                date_creation=(
                    job.job_posted_at_datetime_utc.rstrip("Z")
                    if job.job_posted_at_datetime_utc
                    else datetime.now().isoformat()
                ),
                description=job.job_description,
                job_title=job.job_title,
                location=job.job_location,
                salary=f"{job.job_min_salary or ''} - {job.job_max_salary or ''}",
                job_type=job.job_employment_type,
                apply_url=[job.job_apply_link or "", job.job_google_link or ""],
            )

            # Stream to database if repository is set
            if self.leads_repository:
                _, job_entity = await self._save_job_if_new(job_entity, company_name)

            jobs.append(job_entity)
        return JobEntity(jobs=jobs) # type: ignore

    async def process_results(
        self, company_result: CompanyEntity, job_result: JobEntity, params: dict
    ) -> None:
        await asyncio.sleep(1)  # Rate limiting to avoid hitting API limits
        jsearch = await self._make_request_with_retry(self.search_endpoint, params)
        company_entity, ids, names = await self.to_company_entity(jsearch)
        job_entity = await self.to_job_entity(jsearch, ids, names)
        company_result.companies.extend(company_entity.companies)
        job_result.jobs.extend(job_entity.jobs)

    async def fetch_leads(self, location: str, job_title: list[str]) -> Leads:
        """
        Fetch jobs from the JSearch API based on search parameters.
        If leads_repository is set, streams jobs to database as they are fetched.

        Args:
            location (str): The location to search jobs in.
            job_title (list[str]): List of job titles to search for.

        Returns:
            Leads: The leads containing companies and jobs data.
        """
        # Reset streaming counters
        self._jobs_saved = 0
        self._jobs_skipped = 0

        params_list = []
        company_result: CompanyEntity = CompanyEntity(companies=[]) # type: ignore
        job_result: JobEntity = JobEntity(jobs=[]) # type: ignore

        for title in job_title[:2]:
            params = {
                "query": f"{title} in {location}",
                "page": 1,
                "num_pages": 1,
                "date_posted": "month",
                "country": location[0:2].lower(),
            }
            params_list.append(params)

        await asyncio.gather(
            *[
                self.process_results(company_result, job_result, params)
                for params in params_list
            ]
        )

        # Log streaming stats if repository was used
        if self.leads_repository:
            logger.info(
                f"JSearch streaming complete: {self._jobs_saved} jobs saved, "
                f"{self._jobs_skipped} jobs skipped (duplicates)"
            )

        # Combine results into a Leads object
        leads = Leads(
            companies=company_result,
            jobs=job_result,
            contacts=None,
        ) # type: ignore
        return leads
