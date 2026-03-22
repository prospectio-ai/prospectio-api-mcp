import contextlib
from typing import Callable
from fastapi import FastAPI, BackgroundTasks
from application.api.leads_routes import leads_router
from application.api.profile_routes import profile_router
from domain.ports import task_manager
from infrastructure.services.compatibility_score import CompatibilityScoreLLM
from infrastructure.services.enrich_leads_agent.agent import EnrichLeadsAgent
from infrastructure.services.generate_message import GenerateMessageLLM
from infrastructure.services.profile_database import ProfileDatabase
from infrastructure.services.campaign_database import CampaignDatabase
from application.api.mcp_routes import mcp_prospectio
from config import ActiveJobsDBConfig, JsearchConfig
from domain.services.leads.strategies.active_jobs_db import ActiveJobsDBStrategy
from domain.services.leads.strategies.jsearch import JsearchStrategy
from infrastructure.services.active_jobs_db import ActiveJobsDBAPI
from infrastructure.services.jsearch import JsearchAPI
from config import AppConfig
from infrastructure.services.leads_database import LeadsDatabase
from config import DatabaseConfig
from config import AppConfig
from fastapi.middleware.cors import CORSMiddleware
from infrastructure.services.task_manager import InMemoryTaskManager


def _create_leads_strategies(leads_database) -> dict[str, Callable]:
    """Create leads strategies with shared database instance for job streaming."""
    return {
        "jsearch": lambda location, job_title: JsearchStrategy(
            port=JsearchAPI(JsearchConfig(), leads_repository=leads_database),  # type: ignore
            location=location,
            job_title=job_title,
        ),
        "active_jobs_db": lambda location, job_title: ActiveJobsDBStrategy(
            port=ActiveJobsDBAPI(ActiveJobsDBConfig(), leads_repository=leads_database),  # type: ignore
            location=location,
            job_title=job_title,
        ),
    }

in_memory_task_manager = InMemoryTaskManager()
campaign_database = CampaignDatabase(DatabaseConfig().DATABASE_URL)  # type: ignore
leads_database = LeadsDatabase(DatabaseConfig().DATABASE_URL)  # type: ignore
profile_database = ProfileDatabase(DatabaseConfig().DATABASE_URL)  # type: ignore

# Create strategies with leads_database for job streaming
leads_strategies = _create_leads_strategies(leads_database)

leads_routes = leads_router(
    leads_strategies,
    leads_database,
    CompatibilityScoreLLM(),
    profile_database,
    EnrichLeadsAgent(in_memory_task_manager, leads_database),
    GenerateMessageLLM(),
    in_memory_task_manager,
    campaign_database
)

profile_routes = profile_router(
    profile_database,
    leads_database,
)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the lifespan of both HTTP and stdio MCP servers."""
    async with contextlib.AsyncExitStack() as stack:
        if AppConfig().EXPOSE == "streamable": # type: ignore
            await stack.enter_async_context(mcp_prospectio.session_manager.run())
        yield


app = FastAPI(title="Prospectio API", lifespan=lifespan)

app_config = AppConfig() # type: ignore

app.add_middleware(
    CORSMiddleware,
    allow_origins=app_config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REST_PATH = "/prospectio/rest/v1"
MCP_PATH = "/prospectio/"

app.include_router(leads_routes, prefix=REST_PATH, tags=["Prospects"])
app.include_router(profile_routes, prefix=REST_PATH, tags=["Profile"])

if AppConfig().EXPOSE == "streamable": # type: ignore
    app.mount(MCP_PATH, mcp_prospectio.streamable_http_app())
if AppConfig().EXPOSE == "sse": # type: ignore
    app.mount(MCP_PATH, mcp_prospectio.sse_app())

if __name__ == "__main__":
    mcp_prospectio.run(transport="stdio")
