"""
Tests for application/api/leads_routes.py - Leads router and helper functions.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import APIRouter

from application.api.leads_routes import run_task_with_error_handling, leads_router


class TestRunTaskWithErrorHandling:
    """Test suite for the run_task_with_error_handling helper."""

    @pytest.mark.asyncio
    async def test_successful_coroutine_runs_without_update(self):
        """Should run the coroutine without calling task_manager on success."""
        mock_task_manager = AsyncMock()

        async def success_coro():
            return "done"

        await run_task_with_error_handling(success_coro(), mock_task_manager, "task-1")

        mock_task_manager.update_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_failed_coroutine_updates_task_to_failed(self):
        """Should update task status to 'failed' when coroutine raises."""
        mock_task_manager = AsyncMock()

        async def fail_coro():
            raise RuntimeError("Something went wrong")

        await run_task_with_error_handling(fail_coro(), mock_task_manager, "task-2")

        mock_task_manager.update_task.assert_called_once()
        call_kwargs = mock_task_manager.update_task.call_args
        assert call_kwargs[1]["task_id"] == "task-2"
        assert call_kwargs[1]["status"] == "failed"
        assert "RuntimeError" in call_kwargs[1]["error_details"]

    @pytest.mark.asyncio
    async def test_failed_task_update_does_not_propagate(self):
        """Should not raise even if task_manager.update_task fails."""
        mock_task_manager = AsyncMock()
        mock_task_manager.update_task.side_effect = RuntimeError("Update failed")

        async def fail_coro():
            raise ValueError("Original error")

        # Should not raise
        await run_task_with_error_handling(fail_coro(), mock_task_manager, "task-3")


class TestLeadsRouterFactory:
    """Test suite for the leads_router factory function."""

    def test_returns_api_router(self):
        """leads_router() should return an APIRouter instance."""
        router = leads_router(
            jobs_strategy={},
            repository=AsyncMock(),
            compatibility=AsyncMock(),
            profile_repository=AsyncMock(),
            enrich_port=AsyncMock(),
            message_port=AsyncMock(),
            task_manager=AsyncMock(),
            campaign_repository=AsyncMock(),
        )
        assert isinstance(router, APIRouter)

    def test_router_has_leads_endpoints(self):
        """Router should have registered GET /leads/* and POST /insert/leads endpoints."""
        router = leads_router(
            jobs_strategy={},
            repository=AsyncMock(),
            compatibility=AsyncMock(),
            profile_repository=AsyncMock(),
            enrich_port=AsyncMock(),
            message_port=AsyncMock(),
            task_manager=AsyncMock(),
            campaign_repository=AsyncMock(),
        )
        route_paths = [r.path for r in router.routes]
        assert "/leads/{type}/{offset}/{limit}" in route_paths
        assert "/insert/leads" in route_paths
        assert "/task/{task_id}" in route_paths
        assert "/tasks/running" in route_paths

    def test_router_has_campaign_endpoints(self):
        """Router should have campaign-related endpoints."""
        router = leads_router(
            jobs_strategy={},
            repository=AsyncMock(),
            compatibility=AsyncMock(),
            profile_repository=AsyncMock(),
            enrich_port=AsyncMock(),
            message_port=AsyncMock(),
            task_manager=AsyncMock(),
            campaign_repository=AsyncMock(),
        )
        route_paths = [r.path for r in router.routes]
        assert "/generate/campaign" in route_paths
        assert "/generate/campaign/stream" in route_paths
        assert "/contacts/new/{offset}/{limit}" in route_paths
