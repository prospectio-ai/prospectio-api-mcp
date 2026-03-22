from pydantic import Field
from pydantic_settings import BaseSettings


class AppConfig(BaseSettings):
    EXPOSE: str = Field(..., json_schema_extra={"env": "EXPOSE"})
    MASTER_KEY: str = Field(..., json_schema_extra={"env": "MASTER_KEY"})
    ALLOWED_ORIGINS: list[str] = Field(..., json_schema_extra={"env": "ALLOWED_ORIGINS"})


class MantiksConfig(BaseSettings):
    MANTIKS_API_URL: str = Field(..., json_schema_extra={"env": "MANTIKS_API_URL"})
    MANTIKS_API_KEY: str = Field(..., json_schema_extra={"env": "MANTIKS_API_KEY"})


class RapidApiConfig(BaseSettings):
    RAPIDAPI_API_KEY: list[str] = Field(..., json_schema_extra={"env": "RAPIDAPI_API_KEY"})


class JsearchConfig(RapidApiConfig):
    JSEARCH_API_URL: str = Field(..., json_schema_extra={"env": "JSEARCH_API_URL"})


class ActiveJobsDBConfig(RapidApiConfig):
    ACTIVE_JOBS_DB_URL: str = Field(
        ..., json_schema_extra={"env": "ACTIVE_JOBS_DB_URL"}
    )


class DatabaseConfig(BaseSettings):
    """
    PostgreSQL database configuration.
    """

    DATABASE_URL: str = Field(..., json_schema_extra={"env": "DATABASE_URL"})


class LLMConfig(BaseSettings):
    """
    Configuration for the LLM client.
    """

    MODEL: str = Field(..., json_schema_extra={"env": "MODEL"})
    DECISION_MODEL: str = Field(..., json_schema_extra={"env": "DECISION_MODEL"})
    ENRICH_MODEL: str = Field(..., json_schema_extra={"env": "ENRICH_MODEL"})
    PROSPECTING_MODEL: str = Field(..., json_schema_extra={"env": "PROSPECTING_MODEL"})
    TEMPERATURE: float = Field(..., json_schema_extra={"env": "TEMPERATURE"})
    OLLAMA_BASE_URL: str = Field(..., json_schema_extra={"env": "OLLAMA_BASE_URL"})
    GOOGLE_API_KEY: str = Field(..., json_schema_extra={"env": "GOOGLE_API_KEY"})
    MISTRAL_API_KEY: str = Field(..., json_schema_extra={"env": "MISTRAL_API_KEY"})
    CONCURRENT_CALLS: int = Field(..., json_schema_extra={"env": "CONCURRENT_CALLS"})
    OPEN_ROUTER_API_URL: str = Field(..., json_schema_extra={"env": "OPEN_ROUTER_API_URL"})
    OPEN_ROUTER_API_KEY: str = Field(..., json_schema_extra={"env": "OPEN_ROUTER_API_KEY"})


class DuckDuckGoConfig(BaseSettings):
    """Configuration for the DuckDuckGo search client."""
    DUCKDUCKGO_TIMEOUT: float = Field(10.0, json_schema_extra={"env": "DUCKDUCKGO_TIMEOUT"})
    DUCKDUCKGO_MAX_RESULTS: int = Field(5, json_schema_extra={"env": "DUCKDUCKGO_MAX_RESULTS"})
    DUCKDUCKGO_DELAY_BETWEEN_REQUESTS: float = Field(
        1.0, json_schema_extra={"env": "DUCKDUCKGO_DELAY_BETWEEN_REQUESTS"}
    )


class CrawlConfig(BaseSettings):
    CRAWL_VERBOSE: bool = Field(False, json_schema_extra={"env": "CRAWL_VERBOSE"})
    CRAWL_SCAN_FULL_PAGE: bool = Field(
        False, json_schema_extra={"env": "CRAWL_SCAN_FULL_PAGE"}
    )