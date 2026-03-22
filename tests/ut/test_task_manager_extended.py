"""
Extended unit tests for InMemoryTaskManager.

Covers cleanup_expired_tasks and timestamp behavior.
"""

import pytest
from datetime import datetime, timezone, timedelta

from infrastructure.services.task_manager import InMemoryTaskManager


class TestCleanupExpiredTasks:
    """Tests for cleanup_expired_tasks method."""

    @pytest.fixture
    def manager(self) -> InMemoryTaskManager:
        """Create a task manager with short TTL for testing."""
        return InMemoryTaskManager(task_ttl_seconds=60)

    @pytest.mark.asyncio
    async def test_cleanup_removes_expired_completed_tasks(self, manager: InMemoryTaskManager):
        """Should remove completed tasks older than TTL."""
        task = await manager.submit_task("task-1")
        await manager.update_task("task-1", "Done", "completed")

        # Manually age the task beyond TTL
        aged_task = manager.tasks["task-1"]
        manager.tasks["task-1"] = aged_task.model_copy(
            update={"completed_at": datetime.now(timezone.utc) - timedelta(seconds=120)}
        )

        removed_count = await manager.cleanup_expired_tasks()

        assert removed_count == 1
        task_status = await manager.get_task_status("task-1")
        assert task_status.status == "unknown"

    @pytest.mark.asyncio
    async def test_cleanup_keeps_non_expired_tasks(self, manager: InMemoryTaskManager):
        """Should keep tasks that have not expired yet."""
        await manager.submit_task("task-1")
        await manager.update_task("task-1", "Done", "completed")

        # Task was just completed, should not be expired
        removed_count = await manager.cleanup_expired_tasks()

        assert removed_count == 0
        task = await manager.get_task_status("task-1")
        assert task.status == "completed"

    @pytest.mark.asyncio
    async def test_cleanup_keeps_running_tasks(self, manager: InMemoryTaskManager):
        """Should not remove tasks that are still running."""
        await manager.submit_task("task-1")
        await manager.update_task("task-1", "Processing", "in_progress")

        removed_count = await manager.cleanup_expired_tasks()

        assert removed_count == 0
        task = await manager.get_task_status("task-1")
        assert task.status == "in_progress"

    @pytest.mark.asyncio
    async def test_cleanup_removes_results_for_expired_tasks(self, manager: InMemoryTaskManager):
        """Should also remove stored results for expired tasks."""
        await manager.submit_task("task-1")
        await manager.update_task("task-1", "Done", "completed")
        await manager.store_result("task-1", {"data": "test result"})

        # Age the task beyond TTL
        aged_task = manager.tasks["task-1"]
        manager.tasks["task-1"] = aged_task.model_copy(
            update={"completed_at": datetime.now(timezone.utc) - timedelta(seconds=120)}
        )

        await manager.cleanup_expired_tasks()

        result = await manager.get_result("task-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_cleanup_multiple_mixed_tasks(self, manager: InMemoryTaskManager):
        """Should only remove expired tasks, keep others."""
        # Create tasks with different states
        await manager.submit_task("expired-1")
        await manager.update_task("expired-1", "Done", "completed")
        await manager.submit_task("expired-2")
        await manager.update_task("expired-2", "Failed", "failed")
        await manager.submit_task("fresh-1")
        await manager.update_task("fresh-1", "Done", "completed")
        await manager.submit_task("running-1")
        await manager.update_task("running-1", "Working", "in_progress")

        # Age only the expired tasks
        old_time = datetime.now(timezone.utc) - timedelta(seconds=120)
        for task_id in ["expired-1", "expired-2"]:
            task = manager.tasks[task_id]
            manager.tasks[task_id] = task.model_copy(
                update={"completed_at": old_time}
            )

        removed_count = await manager.cleanup_expired_tasks()

        assert removed_count == 2
        # Verify the right tasks were removed
        assert (await manager.get_task_status("expired-1")).status == "unknown"
        assert (await manager.get_task_status("expired-2")).status == "unknown"
        assert (await manager.get_task_status("fresh-1")).status == "completed"
        assert (await manager.get_task_status("running-1")).status == "in_progress"

    @pytest.mark.asyncio
    async def test_cleanup_no_tasks_returns_zero(self, manager: InMemoryTaskManager):
        """Should return 0 when no tasks exist."""
        removed_count = await manager.cleanup_expired_tasks()
        assert removed_count == 0


class TestTimestampBehavior:
    """Tests for timestamp transitions in task lifecycle."""

    @pytest.fixture
    def manager(self) -> InMemoryTaskManager:
        """Create a task manager."""
        return InMemoryTaskManager()

    @pytest.mark.asyncio
    async def test_started_at_set_on_first_in_progress(self, manager: InMemoryTaskManager):
        """Should set started_at when task first moves to in_progress."""
        await manager.submit_task("task-1")
        task = await manager.get_task_status("task-1")
        assert task.started_at is None

        await manager.update_task("task-1", "Working", "in_progress")
        task = await manager.get_task_status("task-1")
        assert task.started_at is not None

    @pytest.mark.asyncio
    async def test_started_at_not_changed_on_second_in_progress(self, manager: InMemoryTaskManager):
        """Should not change started_at on subsequent in_progress updates."""
        await manager.submit_task("task-1")
        await manager.update_task("task-1", "Step 1", "in_progress")
        task = await manager.get_task_status("task-1")
        first_started_at = task.started_at

        await manager.update_task("task-1", "Step 2", "in_progress")
        task = await manager.get_task_status("task-1")
        assert task.started_at == first_started_at

    @pytest.mark.asyncio
    async def test_completed_at_set_on_completion(self, manager: InMemoryTaskManager):
        """Should set completed_at when task moves to completed."""
        await manager.submit_task("task-1")
        await manager.update_task("task-1", "Working", "in_progress")
        await manager.update_task("task-1", "Done", "completed")

        task = await manager.get_task_status("task-1")
        assert task.completed_at is not None

    @pytest.mark.asyncio
    async def test_completed_at_set_on_failure(self, manager: InMemoryTaskManager):
        """Should set completed_at when task moves to failed."""
        await manager.submit_task("task-1")
        await manager.update_task("task-1", "Error", "failed", error_details="Something broke")

        task = await manager.get_task_status("task-1")
        assert task.completed_at is not None
        assert task.error_details == "Something broke"

    @pytest.mark.asyncio
    async def test_update_nonexistent_task_raises_error(self, manager: InMemoryTaskManager):
        """Should raise ValueError when updating a non-existent task."""
        with pytest.raises(ValueError, match="not found"):
            await manager.update_task("nonexistent", "msg", "in_progress")
