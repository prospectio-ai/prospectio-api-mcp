[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/kaiohz-prospectio-api-mcp-badge.png)](https://mseep.ai/app/kaiohz-prospectio-api-mcp)

[![Verified on MseeP](https://mseep.ai/badge.svg)](https://mseep.ai/app/ca42713a-0e73-4a6d-ad28-4df8042547fd)

# Prospectio MCP API

A FastAPI-based application that implements the Model Context Protocol (MCP) for lead prospecting. The project follows Clean Architecture principles with a clear separation of concerns across domain, application, and infrastructure layers.

The application now includes persistent storage capabilities with PostgreSQL and pgvector integration, allowing leads data to be stored and managed efficiently.

## 🏗️ Project Architecture

This project implements **Clean Architecture** (also known as Hexagonal Architecture) with the following layers:

- **Domain Layer**: Core business entities and logic
- **Application Layer**: Use cases and API routes
- **Infrastructure Layer**: External services, APIs, and framework implementations

## Three-Phase Contact Enrichment

The application uses a sophisticated three-phase approach for contact enrichment that separates professional information discovery, LinkedIn profile URL discovery, and biographical information gathering:

### Phase 1: Perplexity Web Search (Contact Information)

Uses Perplexity's sonar model via OpenRouter for finding professional contact information:
- **Names**: Full names of professionals at target companies
- **Email addresses**: Professional and work emails
- **Phone numbers**: Direct contact numbers
- **Job titles**: Current positions and roles
- **Professional background**: Career information

The Perplexity search deliberately excludes LinkedIn keywords to avoid low-quality LinkedIn-focused results and instead focuses on finding verified contact details from various professional sources.

### Phase 2: DuckDuckGo HTML Search (LinkedIn URLs)

After contact information is gathered, the `DuckDuckGoClient` performs targeted LinkedIn profile URL discovery:

**Dual Search Strategy:**
1. **Primary Search (Name + Company)**: Searches for `site:linkedin.com/in "Person Name" "Company Name"`
2. **Fallback Search (Title + Company)**: If the name search yields no results, falls back to `site:linkedin.com/in "Job Title" "Company Name"`

**Key Features:**
- Rate limiting to avoid being blocked (configurable delay between requests)
- URL deduplication and normalization
- Regex-based extraction of LinkedIn profile URLs from HTML
- Query sanitization to prevent injection

### Phase 3: Perplexity Web Search (Contact Biography)

After LinkedIn URLs are discovered, a secondary Perplexity search gathers biographical information for each contact:
- **Short Description**: A concise one-line summary of the contact's professional profile
- **Full Bio**: A comprehensive biography including career history, achievements, and professional background

This phase enriches the Contact entity with two additional fields:
- `short_description`: Brief professional summary (displayed in contacts list)
- `full_bio`: Detailed biographical information (displayed in contact detail view)

### Configuration Options

Add these environment variables to your `.env` file to customize the enrichment behavior:

```bash
# Perplexity Web Search (Phase 1 & Phase 3)
WEB_SEARCH_MODEL=perplexity/sonar      # Model for web search
WEB_SEARCH_TIMEOUT=60.0                 # Request timeout in seconds
WEB_SEARCH_CONCURRENT_REQUESTS=5        # Max concurrent search requests

# DuckDuckGo LinkedIn Search (Phase 2)
DUCKDUCKGO_TIMEOUT=30.0                 # Request timeout in seconds
DUCKDUCKGO_MAX_RESULTS=10               # Max LinkedIn URLs per search
DUCKDUCKGO_DELAY_BETWEEN_REQUESTS=2.0   # Rate limiting delay in seconds
```

### Database Migration

If you have an existing database, run the following migration to add the bio columns:

```bash
psql -d your_database -f /database/migrations/add_contact_bio_columns.sql
```

Or execute the SQL directly:
```sql
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS short_description TEXT;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS full_bio TEXT;
```

### Enrichment Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `WebSearchClient` | `infrastructure/services/enrich_leads_agent/tools/web_search_client.py` | Perplexity-based contact info and bio search |
| `DuckDuckGoClient` | `infrastructure/services/enrich_leads_agent/tools/duckduckgo_client.py` | LinkedIn URL discovery via HTML search |
| `DuckDuckGoConfig` | `config.py` | Configuration for DuckDuckGo settings |
| `WebSearchConfig` | `config.py` | Configuration for Perplexity settings |
| `EnrichLeadsNodes` | `infrastructure/services/enrich_leads_agent/nodes.py` | Orchestrates the three-phase enrichment |

## 📁 Project Structure
```
prospectio-api-mcp/
├── Dockerfile
├── README.md
├── curls/
│   └── list.http
├── database/
│   └── init.sql
├── docker-compose.yml
├── glama.json
├── poetry.lock
├── prospectio_api_mcp/
│   ├── __pycache__/
│   ├── application/
│   │   ├── api/
│   │   │   ├── leads_routes.py
│   │   │   ├── mcp_routes.py
│   │   │   ├── profile_routes.py
│   │   │   └── __pycache__/
│   │   └── use_cases/
│   │       ├── get_leads.py
│   │       ├── insert_leads.py
│   │       ├── profile.py
│   │       └── __pycache__/
│   ├── config.py
│   ├── domain/
│   │   ├── entities/
│   │   │   ├── company.py
│   │   │   ├── compatibility_score.py
│   │   │   ├── contact.py
│   │   │   ├── job.py
│   │   │   ├── leads.py
│   │   │   ├── leads_result.py
│   │   │   ├── profile.py
│   │   │   ├── work_experience.py
│   │   │   └── __pycache__/
│   │   ├── ports/
│   │   │   ├── compatibility_score.py
│   │   │   ├── fetch_leads.py
│   │   │   ├── leads_repository.py
│   │   │   ├── profile_respository.py
│   │   │   └── __pycache__/
│   │   ├── prompts/
│   │   │   └── compatibility_score.md
│   │   └── services/
│   │       ├── prompt_loader.py
│   │       ├── __pycache__/
│   │       └── leads/
│   │           ├── active_jobs_db.py
│   │           ├── jsearch.py
│   │           ├── mantiks.py
│   │           └── strategy.py
│   ├── infrastructure/
│   │   ├── api/
│   │   │   ├── client.py
│   │   │   ├── llm_client_factory.py
│   │   │   ├── llm_generic_client.py
│   │   │   └── __pycache__/
│   │   ├── dto/
│   │   │   ├── database/
│   │   │   ├── llm/
│   │   │   ├── mantiks/
│   │   │   └── rapidapi/
│   │   └── services/
│   │       ├── active_jobs_db.py
│   │       ├── compatibility_score.py
│   │       ├── jsearch.py
│   │       ├── leads_database.py
│   │       ├── mantiks.py
│   │       └── profile_database.py
│   ├── main.py
│   ├── mcp.py
│   ├── mcp_routes.py
│   └── __pycache__/
├── pyproject.toml
├── pyrightconfig.json
├── tests/
│   └── ut/
│       ├── test_1_profile_use_case.py
│       ├── test_active_jobs_db_use_case.py
│       ├── test_get_leads_use_case.py
│       ├── test_jsearch_use_case.py
│       ├── test_mantiks_use_case.py
│       └── __pycache__/
├── uv.lock
```

## 🔧 Core Components

### Domain Layer (`prospectio_api_mcp/domain/`)

#### Entities
- **`Contact`** (`contact.py`): Represents a business contact (name, email, phone, title, linkedin_url, short_description, full_bio)
- **`Company`** (`company.py`): Represents a company (name, industry, size, location, description)
- **`Job`** (`job.py`): Represents a job posting (title, description, location, salary, requirements)
- **`Leads`** (`leads.py`): Aggregates companies, jobs, and contacts for lead data
- **`LeadsResult`** (`leads_result.py`): Represents the result of a lead insertion operation
- **`Profile`** (`profile.py`): Represents a user profile with personal and professional information
- **`WorkExperience`** (`work_experience.py`): Represents work experience entries for a profile

#### Ports
- **`CompanyJobsPort`** (`fetch_leads.py`): Abstract interface for fetching company jobs from any data source
  - `fetch_company_jobs(location: str, job_title: list[str]) -> Leads`: Abstract method for job search
- **`LeadsRepositoryPort`** (`leads_repository.py`): Abstract interface for persisting leads data
  - `save_leads(leads: Leads) -> None`: Abstract method for saving leads to storage
- **`ProfileRepositoryPort`** (`profile_respository.py`): Abstract interface for profile data management
  - Profile-related repository operations

#### Strategies (`prospectio_api_mcp/domain/services/leads/`)
- **`CompanyJobsStrategy`** (`strategy.py`): Abstract base class for job retrieval strategies
- **Concrete Strategies**: Implementations for each data source:
  - `ActiveJobsDBStrategy`, `JsearchStrategy`, `MantiksStrategy`

### Application Layer (`prospectio_api_mcp/application/`)

#### API (`prospectio_api_mcp/application/api/`)
- **`leads_routes.py`**: Defines FastAPI endpoints for leads management
- **`profile_routes.py`**: Defines FastAPI endpoints for profile management

#### Use Cases (`prospectio_api_mcp/application/use_cases/`)
- **`InsertCompanyJobsUseCase`** (`insert_leads.py`): Orchestrates the process of retrieving and inserting company jobs from different sources
  - Accepts a strategy and repository, retrieves leads and persists them to the database
- **`GetLeadsUseCase`** (`get_leads.py`): Handles retrieval of leads data
- **`ProfileUseCase`** (`profile.py`): Manages profile-related operations

### Infrastructure Layer (`prospectio_api_mcp/infrastructure/`)

#### API Client (`prospectio_api_mcp/infrastructure/api/client.py`)
- **`BaseApiClient`**: Async HTTP client for external API calls

#### DTOs (`prospectio_api_mcp/infrastructure/dto/`)
- **Database DTOs**: `base.py`, `company.py`, `job.py`, `contact.py`, `profile.py`, `work_experience.py` - SQLAlchemy models for persistence
- **Mantiks DTOs**: `company.py`, `company_response.py`, `job.py`, `location.py`, `salary.py` - Data transfer objects for Mantiks API
- **RapidAPI DTOs**: `active_jobs_db.py`, `jsearch.py` - Data transfer objects for RapidAPI services

#### Services (`prospectio_api_mcp/infrastructure/services/`)
- **`ActiveJobsDBAPI`**: Adapter for Active Jobs DB API
- **`JsearchAPI`**: Adapter for Jsearch API
- **`MantiksAPI`**: Adapter for Mantiks API
- **`LeadsDatabase`**: PostgreSQL repository implementation for leads persistence
- **`ProfileDatabase`**: PostgreSQL repository implementation for profile management

All API services implement the `CompanyJobsPort` interface, and the database service implements the `LeadsRepositoryPort` interface, allowing for easy swapping and extension.

## 🚀 Application Entry Point (`prospectio_api_mcp/main.py`)

The FastAPI application is configured to:
- **Manage Application Lifespan**: Handles startup and shutdown events, including MCP session lifecycle.
- **Expose Multiple Protocols**:
  - REST API available at `/rest/v1/`
  - MCP protocol available at `/prospectio/` (implemented in `mcp_routes.py`)
- **Integrate Routers**: Includes leads insertion routes and profile routes for comprehensive lead and profile management via FastAPI's APIRouter.
- **Load Configuration**: Loads environment-based settings from `config.py` using Pydantic.
- **Dependency Injection**: Injects service implementations, strategies, and repository into endpoints for clean separation.
- **Database Integration**: Configures PostgreSQL connection for persistent storage of leads data and profiles.

## ⚙️ Configuration

To run the application, you need to configure your environment variables. This is done using a `.env` file at the root of the project.

1.  **Create the `.env` file**:
    Copy the example file `.env.example` to a new file named `.env`.
    ```bash
    cp .env.example .env
    cp .env .env.docker
    ```

2.  **Edit the `.env` file**:
    Open the `.env` file and fill in the required values for the following variables:
    - `EXPOSE`: `stdio` or `http`
    - `MASTER_KEY`: Your master key.
    - `ALLOWED_ORIGINS`: Comma-separated list of allowed origins.
    - `MANTIKS_API_URL`: The base URL for the Mantiks API.
    - `MANTIKS_API_KEY`: Your API key for Mantiks.
    - `RAPIDAPI_API_KEY`: Your API key for RapidAPI.
    - `JSEARCH_API_URL`: The base URL for the Jsearch API.
    - `ACTIVE_JOBS_DB_URL`: The base URL for the Active Jobs DB API.
    - `DATABASE_URL`: PostgreSQL connection string (e.g., `postgresql+asyncpg://user:password@host:port/database`)

The application uses Pydantic Settings to load these variables from the `.env` file (see `prospectio_api_mcp/config.py`).

## 📦 Dependencies (`pyproject.toml`)

### Core Dependencies
- **FastAPI (0.115.14)**: Modern web framework with automatic API documentation
- **MCP (1.10.1)**: Model Context Protocol implementation
- **Pydantic (2.10.3)**: Data validation and serialization
- **HTTPX (0.28.1)**: HTTP client for external API calls
- **SQLAlchemy (2.0.41)**: Database ORM for PostgreSQL integration
- **asyncpg (0.30.0)**: Async PostgreSQL driver
- **psycopg (3.2.4)**: PostgreSQL adapter

### Development Dependencies
- **Pytest**: Testing framework

## 🔄 Data Flow

1. **HTTP Request**: Client makes a POST request to `/rest/v1/insert/leads/{source}` with JSON body containing location and job_title parameters.
2. **Route Handler**: The FastAPI route in `application/api/routes.py` receives the request and extracts parameters.
3. **Strategy Mapping**: The handler selects the appropriate strategy (e.g., `ActiveJobsDBStrategy`, `JsearchStrategy`, etc.) based on the source.
4. **Use Case Execution**: `InsertCompanyJobsUseCase` is instantiated with the selected strategy and repository.
5. **Strategy Execution**: The use case delegates to the strategy's `execute()` method to fetch leads data.
6. **Port Execution**: The strategy calls the port's `fetch_company_jobs(location, job_title)` method, which is implemented by the infrastructure adapter (e.g., `ActiveJobsDBAPI`).

## 🧪 Testing

The project includes comprehensive unit tests following pytest best practices and Clean Architecture principles. Tests are located in the `tests/` directory and use dependency injection for mocking external services.

### Test Structure

```
tests/
└── ut/                                    # Unit tests
    ├── test_mantiks_use_case.py          # Mantiks strategy tests
    ├── test_jsearch_use_case.py          # JSearch strategy tests
    ├── test_active_jobs_db_use_case.py   # Active Jobs DB strategy tests
    ├── test_get_leads.py                 # Get leads use case tests
    └── test_profile.py                   # Profile use case tests
```

### Running Tests

#### **Install Dependencies:**
```bash
poetry install
```

#### **Run All Tests:**
```bash
# Run all tests
poetry run pytest

# Run with verbose output
poetry run pytest -v
```

#### **Run Specific Test Files:**

```bash
# Run Mantiks tests only
poetry run pytest tests/ut/test_mantiks_use_case.py -v

# Run JSearch tests only
poetry run pytest tests/ut/test_jsearch_use_case.py -v

# Run Active Jobs DB tests only
poetry run pytest tests/ut/test_active_jobs_db_use_case.py -v

# Run Get Leads tests only
poetry run pytest tests/ut/test_get_leads.py -v

# Run Profile tests only
poetry run pytest tests/ut/test_profile.py -v
```

#### **Run Specific Test Methods:**
```bash
# Run a specific test method
poetry run pytest tests/ut/test_mantiks_use_case.py::TestMantiksUseCase::test_get_leads_success -v
```

### **Environment Variables for Testing**

Tests require a `.env` file for configuration. Copy the example file:
```bash
cp .env.example .env
```

The CI pipeline automatically handles environment setup and database initialization.

## 🏃‍♂️ Running the Application

Before running the application, make sure you have set up your environment variables as described in the [**Configuration**](#️-configuration) section.

### Option 1: Local Development

1. **Install Dependencies**:
   ```bash
   poetry install
   ```

2. **Run the Application**:
   ```bash
   poetry run fastapi run prospectio_api_mcp/main.py --reload --port <YOUR_PORT>
   ```

### Option 2: Docker Compose (Recommended)

The Docker Compose setup includes both the application and PostgreSQL database with pgvector extension.

First build a network for prospectio :
```bash
docker network create prospectio
```

1. **Build and Run with Docker Compose**:
   ```bash
   # Build and start the container
   docker-compose up --build
   
   # Or run in background (detached mode)
   docker-compose up -d --build
   ```

3. **Stop the Application**:
   ```bash
   # Stop the container
   docker-compose down
   
   # Stop and remove volumes (if needed)
   docker-compose down -v
   ```

4. **View Logs**:
   ```bash
   # View real-time logs
   docker-compose logs -f
   
   # View logs for specific service
   docker-compose logs -f prospectio-api-mcp
  ```

### Accessing the APIs

Once the application is running (locally or via Docker), you can access:
- **REST API**: `http://localhost:<YOUR_PORT>/rest/v1/insert/leads/{source}`
  - `source` can be: mantiks, active_jobs_db, jsearch
  - Method: POST with JSON body containing `location` and `job_title` array
  - Example: `http://localhost:<YOUR_PORT>/rest/v1/insert/leads/mantiks`
- **API Documentation**: `http://localhost:<YOUR_PORT>/docs`
- **MCP Endpoint**: `http://localhost:<YOUR_PORT>/prospectio/mcp/sse`

# Add to claude

change settings json to match your environment

```json
{
  "mcpServers": {
    "Prospectio-stdio": {
      "command": "<ABSOLUTE_PATH>/uv",
      "args": [
        "--directory",
        "<PROJECT_ABSOLUTE_PATH>",
        "run",
        "prospectio_api_mcp/main.py"
      ]
    }
  }
}
```

# Add to Gemini cli

change settings json to match your environment

```json
{
  "mcpServers": {
    "prospectio-http": {
      "httpUrl": "http://localhost:<YOUR_PORT>/prospectio/mcp/sse",
      "timeout": 30000
    },
    "Prospectio-stdio": {
      "command": "<ABSOLUTE_PATH>/uv",
      "args": [
        "--directory",
        "<PROJECT_ABSOLUTE_PATH>",
        "run",
        "prospectio_api_mcp/main.py"
      ]
    }
  }
}
```

**Built with ❤️ by the Prospectio Team**