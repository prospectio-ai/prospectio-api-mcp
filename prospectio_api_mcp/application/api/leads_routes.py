import asyncio
import logging
import traceback
from fastapi import APIRouter, HTTPException, Path
from application.requests.insert_leads import InsertLeadsRequest
from application.use_cases.generate_message import GenerateMessageUseCase
from application.use_cases.get_leads import GetLeadsUseCase
from domain.entities.company import CompanyEntity
from domain.entities.contact import ContactEntity
from domain.entities.job import JobEntity
from domain.entities.leads import Leads
from domain.entities.prospect_message import ProspectMessage
from domain.ports.compatibility_score import CompatibilityScorePort
from domain.ports.enrich_leads import EnrichLeadsPort
from domain.ports.generate_message import GenerateMessagePort
from domain.ports.profile_respository import ProfileRepositoryPort
from domain.ports.task_manager import TaskManagerPort
from domain.services.leads.leads_processor import LeadsProcessor
from prospectio_api_mcp.application.use_cases.insert_leads import (
    InsertLeadsUseCase,
)
from collections.abc import Callable
from domain.services.leads.strategy import LeadsStrategy
from domain.ports.leads_repository import LeadsRepositoryPort
from application.api.mcp_routes import mcp_prospectio
from uuid import uuid4
from domain.entities.task import Task


logger = logging.getLogger(__name__)

_background_tasks: set[asyncio.Task] = set()


def leads_router(
    jobs_strategy: dict[str, Callable[[str, list[str]], LeadsStrategy]],
    repository: LeadsRepositoryPort,
    compatibility: CompatibilityScorePort,
    profile_repository: ProfileRepositoryPort,
    enrich_port: EnrichLeadsPort,
    message_port: GenerateMessagePort,
    task_manager: TaskManagerPort,
) -> APIRouter:
    """
    Create an APIRouter for company jobs endpoints with injected strategy.

    Args:
        jobs_strategy (dict[str, callable]): Mapping of source to strategy factory.
        repository (LeadsRepositoryPort): Repository for data persistence.
    Returns:
        APIRouter: Configured router with endpoints.
    """
    leads_router = APIRouter()

    @leads_router.get("/leads/{type}/{offset}/{limit}")
    @mcp_prospectio.tool(
        description="ALWAYS USE THIS FIRST to retrieve existing data from the database before searching for new opportunities. "
        "Returns companies, jobs, contacts or leads that are already stored in the database. "
        "This endpoint is paginated: use the 'offset' parameter to paginate through results. Offset begins at 0. "
        "Pagination size: 5 for companies, 10 for contacts, 3 for jobs. "
        "Use this tool when the user wants to see existing leads, companies, jobs, or contacts. "
        "Only use the insert/leads endpoint when the user specifically asks for new opportunities or when no relevant data is found in the database. "
        "The parameter 'type' can be: 'companies', 'jobs', 'contacts', or 'leads'. "
        "Example: GET /get/leads/companies/0 to get the first 5 companies, /get/leads/companies/5 for the next 5, /get/leads/contacts/0 for the first 10 contacts, /get/leads/jobs/0 for the first 3 jobs, etc."
    )
    async def get_leads(
        type: str = Path(..., description="Lead source"),
        offset: int = Path(..., description="Offset for pagination"),
        limit: int = Path(..., description="Limit for pagination"),
    ) -> Leads | CompanyEntity | JobEntity | ContactEntity:
        try:
            leads = await GetLeadsUseCase(type, repository).get_leads(offset, limit)
            return leads
        except Exception as e:
            logger.error(f"Error in get leads: {e}\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=str(e))

    @leads_router.post("/insert/leads")
    @mcp_prospectio.tool(
        description="Use this ONLY when the user asks for NEW opportunities/leads or when get/leads returns insufficient data. "
        "This tool searches external sources and inserts NEW leads into the database. "
        "Sources available: 'jsearch', 'active_jobs_db'."
        "If a source does not work or returns no data, try another one. "
        "Requires location (country code) and job titles as technologies or job titles (e.g., 'Python', 'AI', 'RAG', 'LLM', 'Tech lead', 'Software Engineer'). Focus on technologies found on profile."
        "IMPORTANT: Before using this, check the user profile or ask to update it if missing. "
        'Example JSON: {"source": "jsearch", "location": "FR", "job_params": ["Python", "AI", "RAG", "LLM", "Tech lead", "Software Engineer"]}'
    )
    async def insert_leads(
        request: InsertLeadsRequest
    ) -> Task:
        """
        Retrieve leads with contacts from the specified source.

        Args:
            source (str): The source from which to get leads with contacts.
            location (str): The country code for the location.
            job_title (list[str]): List of job titles to filter leads.

        Returns:
            dict: A dictionary containing the leads data.
        """
        try:
            if request.source not in jobs_strategy:
                raise ValueError(f"Unknown source: {request.source}")
            job_params = [title.strip().lower() for title in request.job_params]
            location = request.location.strip().lower()
            strategy = request.source.strip().lower()
            task_uuid = str(uuid4())
            strategy = jobs_strategy[request.source](location, job_params)
            processor = LeadsProcessor(compatibility)

            task = asyncio.create_task(
                InsertLeadsUseCase(
                    task_uuid, strategy, repository, processor, profile_repository, enrich_port, task_manager
                ).insert_leads()
            )
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)

            return Task(
                task_id=task_uuid,
                message=f"Lead insertion started for source '{request.source}' in location '{location}'",
                status="processing"
            )
        except Exception as e:
            await task_manager.remove_task(task_uuid)
            logger.error(f"Error in insert leads: {e}\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=str(e))
        
    @leads_router.get("/task/{task_id}")
    @mcp_prospectio.tool(
        description="Check the status and progress of a background task by its unique ID. "
        "Essential for monitoring long-running operations like lead insertion, enrichment, or data processing. "
        "Returns current status ('processing', 'completed', 'failed'), progress information, and any error details. "
        "Use the task_id returned from operations like '/insert/leads' to track their execution. "
        "Completed or failed tasks are automatically cleaned up after status retrieval. "
        "Example: After starting lead insertion, use this to monitor when new leads are ready in the database."
    )
    async def get_task_status(task_id: str) -> Task:
        """
        Get the status of a task by its ID.

        Args:
            task_id (str): The ID of the task to retrieve.

        Returns:
            Task: The task with its current status.
        """
        try:
            task = await task_manager.get_task_status(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            if task.status == "completed" or task.status == "failed":
                await task_manager.remove_task(task_id)
            return task
        except Exception as e:
            logger.error(f"Error in get task status: {e}\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=str(e))
        
    @leads_router.get("/generate/message/{contact_id}")
    async def generate_prospecting_message(contact_id: str) -> ProspectMessage:
        """
        Generate a prospecting message for a contact by its ID.

        Args:
            id (str): The ID of the contact to generate a message for.

        Returns:
            str: The generated prospecting message.
        """
        try:
            message = await GenerateMessageUseCase(repository, profile_repository, message_port).generate_message(contact_id)
            return message
        except Exception as e:
            logger.error(f"Error in generate prospecting message: {e}\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=str(e))

    return leads_router
