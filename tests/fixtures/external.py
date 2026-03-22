"""Centralized fixtures for external dependencies (the only things we mock)."""
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_jsearch_api():
    """Mock JSearch RapidAPI calls."""
    mock = AsyncMock()
    mock.search_jobs.return_value = []
    return mock


@pytest.fixture
def mock_active_jobs_db_api():
    """Mock ActiveJobsDB RapidAPI calls."""
    mock = AsyncMock()
    mock.search_jobs.return_value = []
    return mock


@pytest.fixture
def mock_llm_chain():
    """Mock LangChain LLM chain invocations."""
    mock = AsyncMock()
    mock.ainvoke.return_value = MagicMock(content="mocked response")
    return mock


@pytest.fixture
def mock_generate_message_port():
    """Mock the message generation port (external LLM dependency)."""
    mock = AsyncMock()
    mock.generate_message.return_value = MagicMock(
        subject="Test Subject",
        message="Test Message",
    )
    return mock
