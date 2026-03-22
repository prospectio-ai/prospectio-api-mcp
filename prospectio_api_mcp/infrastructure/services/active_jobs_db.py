import httpx
from uuid import uuid4
from prospectio_api_mcp.domain.ports.fetch_leads import FetchLeadsPort
from infrastructure.dto.rapidapi.active_jobs_db import ActiveJobsResponseDTO
from config import ActiveJobsDBConfig
from infrastructure.api.client import BaseApiClient
from domain.entities.company import Company, CompanyEntity
from domain.entities.job import Job, JobEntity
from domain.entities.leads import Leads
from datetime import datetime


class ActiveJobsDBAPI(FetchLeadsPort):
    """
    Adapter for the Active Jobs DB API to fetch job data.
    """

    def __init__(self, config: ActiveJobsDBConfig) -> None:
        """
        Initialize ActiveJobsDBAPI with configuration.

        Args:
            config (ActiveJobsDBConfig): Active Jobs DB API configuration object.
        """
        self.api_base = config.ACTIVE_JOBS_DB_URL
        self.api_keys = config.RAPIDAPI_API_KEY
        self.endpoint = "/active-ats-7d"

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
            Exception: If the response status code is not 200.

        Returns:
            T: An instance of the DTO type with the response data.
        """
        if result.status_code != 200:
            await client.close()
            raise RuntimeError(f"Failed to fetch jobs: {result.text}")
        dto = dto_type(**{"active_jobs": result.json()})
        await client.close()
        return dto
    
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
    
    async def _make_request_with_retry(self, endpoint: str, params: dict, key_index: int = 0) -> ActiveJobsResponseDTO:
        """
        Make API request with recursive retry logic for different API keys on 429 errors.

        Args:
            endpoint (str): The API endpoint to call.
            params (dict): Request parameters.
            key_index (int): Current key index to try.

        Returns:
            ActiveJobsResponseDTO: The parsed response data.

        Raises:
            Exception: If all API keys are exhausted or other errors occur.
        """
        if key_index >= len(self.api_keys):
            raise RuntimeError("All API keys exhausted due to rate limiting")

        headers = self._get_headers(self.api_keys[key_index])
        client = BaseApiClient(self.api_base, headers)
        result = await client.get(endpoint, params)
        
        if result.status_code == 429:
            await client.close()
            return await self._make_request_with_retry(endpoint, params, key_index + 1)
        
        return await self._check_error(client, result, ActiveJobsResponseDTO)

    async def to_company_entity(
        self, dto: ActiveJobsResponseDTO
    ) -> tuple[CompanyEntity, list[str]]:
        """
        Convert Active Jobs DB response DTO to CompanyEntity.

        Args:
            dto (ActiveJobsResponseDTO): The Active Jobs DB API response data.

        Returns:
            tuple[CompanyEntity, list[str]]: Entity containing companies and their IDs.
        """
        companies: list[Company] = []
        ids: list[str] = []

        for active_job in dto.active_jobs if dto.active_jobs else []:
            company_id = str(uuid4())
            company = Company(  # type: ignore
                id=company_id,
                name=active_job.organization,
                source="active_jobs_db",
                website=active_job.organization_url,
            )
            ids.append(company_id)
            companies.append(company)

        return CompanyEntity(companies=companies), ids # type: ignore

    async def to_job_entity(
        self, dto: ActiveJobsResponseDTO, ids: list[str]
    ) -> JobEntity:
        """
        Convert Active Jobs DB response DTO to JobEntity.

        Args:
            dto (ActiveJobsResponseDTO): The Active Jobs DB API response data.
            ids (list[str]): List of company IDs to associate with jobs.

        Returns:
            JobEntity: Entity containing jobs from Active Jobs DB data.
        """
        jobs: list[Job] = []

        for index, active_job in enumerate(dto.active_jobs) if dto.active_jobs else []:
            active_job.id = str(uuid4())
            job_entity = Job(  # type: ignore
                id=active_job.id,
                company_id=ids[index] if index < len(ids) else str(uuid4()),
                date_creation=active_job.date_posted or datetime.now().isoformat(),
                description=active_job.description_text,
                job_title=active_job.title,
                location=(
                    ", ".join(active_job.locations_derived)
                    if active_job.locations_derived
                    else None
                ),
                salary=str(active_job.salary_raw) if active_job.salary_raw else None,
                job_type=(
                    ", ".join(active_job.employment_type)
                    if active_job.employment_type
                    else None
                ),
                apply_url=[active_job.url or ""],
            )
            jobs.append(job_entity)

        return JobEntity(jobs=jobs) # type: ignore

    async def fetch_leads(self, location: str, job_title: list[str]) -> Leads:
        """
        Fetch jobs from the Active Jobs DB API based on search parameters.

        Args:
            location (str): The location to search jobs in.
            job_title (list[str]): List of job titles to search for.

        Returns:
            Leads: The leads containing companies and jobs data.
        """
        params = {
            "limit": 10,
            "offset": 0,
            "advanced_title_filter": f"{' | '.join(job_title)}",
            "location_filter": location,
            "description_type": "text",
        }
        active_jobs = await self._make_request_with_retry(self.endpoint, params)

        company_entity, ids = await self.to_company_entity(active_jobs)
        job_entity = await self.to_job_entity(active_jobs, ids)

        return Leads(companies=company_entity, jobs=job_entity, contacts=None) # type: ignore
