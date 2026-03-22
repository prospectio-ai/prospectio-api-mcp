import asyncio
import logging
import traceback
from typing import List, Union, Optional
from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import StreamingResponse
from application.requests.insert_leads import InsertLeadsRequest
from application.requests.campaign import CreateCampaignRequest
from application.use_cases.generate_message import GenerateMessageUseCase
from application.use_cases.generate_campaign import GenerateCampaignUseCase
from application.use_cases.generate_campaign_stream import GenerateCampaignStreamUseCase
from application.use_cases.get_leads import GetLeadsUseCase
from domain.entities.company import CompanyEntity
from domain.entities.contact import ContactEntity
from domain.entities.job import JobEntity
from domain.entities.leads import Leads
from domain.entities.prospect_message import ProspectMessage
from domain.entities.campaign import Campaign, CampaignEntity
from domain.entities.campaign_result import CampaignResult, CampaignMessage
from domain.ports.compatibility_score import CompatibilityScorePort
from domain.ports.enrich_leads import EnrichLeadsPort
from domain.ports.generate_message import GenerateMessagePort
from domain.ports.profile_respository import ProfileRepositoryPort
from domain.ports.task_manager import TaskManagerPort
from domain.ports.campaign_repository import CampaignRepositoryPort
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


async def run_task_with_error_handling(
    coro,
    task_manager: "TaskManagerPort",
    task_id: str
) -> None:
    """
    Wrapper to run a coroutine with error handling for background tasks.

    Wraps the coroutine in try/except to ensure that any exceptions are
    caught, logged, and the task is updated to 'failed' status with error details.

    Args:
        coro: The coroutine to execute.
        task_manager (TaskManagerPort): The task manager to update task status.
        task_id (str): The unique task identifier.

    Returns:
        None
    """
    try:
        await coro
    except Exception as e:
        error_message = f"{type(e).__name__}: {str(e)}"
        logger.error(f"Background task {task_id} failed: {error_message}\n{traceback.format_exc()}")
        try:
            await task_manager.update_task(
                task_id=task_id,
                message="Task failed due to an unexpected error",
                status="failed",
                error_details=error_message
            )
        except Exception as update_error:
            logger.error(f"Failed to update task {task_id} status: {update_error}")


def leads_router(
    jobs_strategy: dict[str, Callable[[str, list[str]], LeadsStrategy]],
    repository: LeadsRepositoryPort,
    compatibility: CompatibilityScorePort,
    profile_repository: ProfileRepositoryPort,
    enrich_port: EnrichLeadsPort,
    message_port: GenerateMessagePort,
    task_manager: TaskManagerPort,
    campaign_repository: CampaignRepositoryPort,
) -> APIRouter:
    """
    Create an APIRouter for company jobs endpoints with injected strategy.

    Args:
        jobs_strategy (dict[str, callable]): Mapping of source to strategy factory.
        repository (LeadsRepositoryPort): Repository for data persistence.
        campaign_repository (CampaignRepositoryPort): Repository for campaign operations.
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
    ) -> Union[Leads, CompanyEntity, JobEntity, ContactEntity]:
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
        task_uuid = str(uuid4())
        try:
            if request.source not in jobs_strategy:
                raise ValueError(f"Unknown source: {request.source}")
            job_params = [title.strip().lower() for title in request.job_params]
            location = request.location.strip().lower()
            strategy = jobs_strategy[request.source](location, job_params)
            processor = LeadsProcessor(compatibility)

            asyncio.create_task(
                run_task_with_error_handling(
                    InsertLeadsUseCase(
                        task_uuid, strategy, repository, processor, profile_repository, enrich_port, task_manager
                    ).insert_leads(),
                    task_manager,
                    task_uuid
                )
            )

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

    @leads_router.get("/tasks/running")
    @mcp_prospectio.tool(
        description="Get all currently running tasks. "
        "Returns tasks with status 'pending', 'processing', or 'in_progress'. "
        "Optionally filter by task_type (e.g., 'insert_leads', 'generate_campaign'). "
        "Use this to check if there are any background operations in progress before starting new ones."
    )
    async def get_running_tasks(
        task_type: Optional[str] = Query(
            default=None,
            description="Filter tasks by type (e.g., 'insert_leads', 'generate_campaign')"
        )
    ) -> List[Task]:
        """
        Get all running tasks, optionally filtered by task type.

        Args:
            task_type (Optional[str]): If provided, filter tasks by this type.

        Returns:
            List[Task]: List of running tasks.
        """
        try:
            tasks = await task_manager.get_running_tasks(task_type)
            return tasks
        except Exception as e:
            logger.error(f"Error in get running tasks: {e}\n{traceback.format_exc()}")
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

    @leads_router.post("/generate/campaign")
    @mcp_prospectio.tool(
        description="Generate prospecting messages for contacts WITHOUT existing messages as a campaign. "
        "This creates personalized messages for each contact based on the user profile and company information. "
        "IMPORTANT: Each contact can only receive ONE message ever - contacts with existing messages are skipped. "
        "Returns a Task with task_id for polling status via '/task/{task_id}'. "
        "Use this when the user wants to create a bulk prospecting campaign. "
        "IMPORTANT: Ensure the user profile is set up before running this operation. "
        'Example JSON: {"name": "Q1 2024 Outreach Campaign", "description": "Target Python developers"}'
    )
    async def generate_campaign(request: CreateCampaignRequest) -> Task:
        """
        Generate prospecting messages for contacts without existing messages.

        Args:
            request (CreateCampaignRequest): Campaign creation request with name and optional description.

        Returns:
            Task: A task object with task_id for status polling.
        """
        task_uuid = str(uuid4())
        try:
            asyncio.create_task(
                run_task_with_error_handling(
                    GenerateCampaignUseCase(
                        task_uuid,
                        request.name,
                        profile_repository,
                        campaign_repository,
                        message_port,
                        task_manager
                    ).generate_campaign(),
                    task_manager,
                    task_uuid
                )
            )

            return Task(
                task_id=task_uuid,
                message=f"Campaign '{request.name}' generation started for contacts without messages",
                status="processing"
            )
        except Exception as e:
            await task_manager.remove_task(task_uuid)
            logger.error(f"Error in generate campaign: {e}\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=str(e))

    @leads_router.post("/generate/campaign/stream")
    async def generate_campaign_stream(request: CreateCampaignRequest) -> StreamingResponse:
        """
        Generate prospecting messages with SSE streaming.

        Returns a stream of Server-Sent Events as messages are generated.

        Event types:
        - campaign_started: Campaign creation confirmed with campaign_id
        - progress_update: Current progress (X/Y contacts)
        - message_generated: Each message as it's created
        - campaign_completed: Final summary
        - campaign_failed: Error occurred

        Args:
            request (CreateCampaignRequest): Campaign creation request with name.

        Returns:
            StreamingResponse: SSE stream of campaign events.
        """
        try:
            use_case = GenerateCampaignStreamUseCase(
                campaign_name=request.name,
                profile_repository=profile_repository,
                campaign_repository=campaign_repository,
                message_port=message_port,
            )

            return StreamingResponse(
                use_case.generate_campaign_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        except Exception as e:
            logger.error(f"Error in generate campaign stream: {e}\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=str(e))

    @leads_router.get("/campaign/result/{task_id}")
    @mcp_prospectio.tool(
        description="Retrieve the full result of a completed campaign generation task. "
        "Returns the CampaignResult containing all generated messages, statistics, and details. "
        "Use this after the '/task/{task_id}' endpoint shows status 'completed' to get the campaign data. "
        "The result includes: total_contacts, successful count, failed count, and all generated messages. "
        "Note: Results are stored temporarily and may be cleaned up after retrieval."
    )
    async def get_campaign_result(task_id: str) -> Optional[CampaignResult]:
        """
        Get the stored result of a campaign generation task.

        Args:
            task_id (str): The ID of the campaign task.

        Returns:
            CampaignResult: The campaign result with all generated messages, or None if not found.
        """
        try:
            result = await task_manager.get_result(task_id)
            if result is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Campaign result not found for task_id: {task_id}. "
                           "The task may not have completed yet or the result has been cleaned up."
                )
            if not isinstance(result, CampaignResult):
                raise HTTPException(
                    status_code=400,
                    detail=f"Task {task_id} is not a campaign generation task."
                )
            return result
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in get campaign result: {e}\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=str(e))

    @leads_router.get("/campaigns/{offset}/{limit}")
    @mcp_prospectio.tool(
        description="Retrieve all campaigns with pagination. "
        "Returns a list of campaigns ordered by creation date (newest first). "
        "Use this to view campaign history and their statistics. "
        "Each campaign includes: id, name, status, total_contacts, successful, failed counts, and timestamps."
    )
    async def get_campaigns(
        offset: int = Path(..., ge=0, description="Number of campaigns to skip"),
        limit: int = Path(..., ge=1, le=100, description="Maximum number of campaigns to return")
    ) -> CampaignEntity:
        """
        Retrieve campaigns with pagination.

        Args:
            offset (int): Number of campaigns to skip.
            limit (int): Maximum number of campaigns to return.

        Returns:
            CampaignEntity: List of campaigns with pagination info.
        """
        try:
            campaigns = await campaign_repository.get_campaigns(offset, limit)
            return campaigns
        except Exception as e:
            logger.error(f"Error in get campaigns: {e}\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=str(e))

    @leads_router.get("/campaigns/{campaign_id}")
    @mcp_prospectio.tool(
        description="Retrieve a specific campaign by its ID. "
        "Returns detailed campaign information including status and statistics."
    )
    async def get_campaign_by_id(
        campaign_id: str = Path(..., description="The campaign ID")
    ) -> Campaign:
        """
        Retrieve a campaign by its ID.

        Args:
            campaign_id (str): The unique identifier of the campaign.

        Returns:
            Campaign: The campaign entity.
        """
        try:
            campaign = await campaign_repository.get_campaign_by_id(campaign_id)
            if not campaign:
                raise HTTPException(
                    status_code=404,
                    detail=f"Campaign not found with id: {campaign_id}"
                )
            return campaign
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in get campaign by id: {e}\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=str(e))

    @leads_router.get("/campaigns/{campaign_id}/messages/{offset}/{limit}")
    @mcp_prospectio.tool(
        description="Retrieve messages for a specific campaign with pagination. "
        "Returns all generated messages for the campaign including contact info, subject, and message body."
    )
    async def get_campaign_messages(
        campaign_id: str = Path(..., description="The campaign ID"),
        offset: int = Path(..., ge=0, description="Number of messages to skip"),
        limit: int = Path(..., ge=1, le=100, description="Maximum number of messages to return")
    ) -> List[CampaignMessage]:
        """
        Retrieve messages for a specific campaign with pagination.

        Args:
            campaign_id (str): The campaign ID.
            offset (int): Number of messages to skip.
            limit (int): Maximum number of messages to return.

        Returns:
            List[CampaignMessage]: List of campaign messages.
        """
        try:
            # Verify campaign exists
            campaign = await campaign_repository.get_campaign_by_id(campaign_id)
            if not campaign:
                raise HTTPException(
                    status_code=404,
                    detail=f"Campaign not found with id: {campaign_id}"
                )
            messages = await campaign_repository.get_campaign_messages(campaign_id, offset, limit)
            return messages
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in get campaign messages: {e}\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=str(e))

    @leads_router.get("/contacts/new/{offset}/{limit}")
    @mcp_prospectio.tool(
        description="Retrieve contacts that have NOT received any messages yet. "
        "Use this to see which contacts are available for the next campaign. "
        "Each contact can only receive ONE message ever, so this shows contacts eligible for messaging."
    )
    async def get_new_contacts(
        offset: int = Path(..., ge=0, description="Number of contacts to skip"),
        limit: int = Path(..., ge=1, le=100, description="Maximum number of contacts to return")
    ) -> ContactEntity:
        """
        Retrieve contacts without existing messages.

        Args:
            offset (int): Number of contacts to skip.
            limit (int): Maximum number of contacts to return.

        Returns:
            ContactEntity: List of contacts without messages.
        """
        try:
            contacts_with_companies = await campaign_repository.get_contacts_without_messages()
            # Apply pagination manually since we get all contacts first
            paginated_contacts = contacts_with_companies[offset:offset + limit]
            contacts = [contact for contact, _ in paginated_contacts]
            total_pages = (len(contacts_with_companies) + limit - 1) // limit if limit > 0 else 1
            return ContactEntity(contacts=contacts, pages=total_pages)
        except Exception as e:
            logger.error(f"Error in get new contacts: {e}\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=str(e))

    return leads_router
