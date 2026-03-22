"""
Unit tests for the task management system.

Tests cover:
- TaskProgress model creation and serialization
- Task entity with all fields
- InMemoryTaskManager operations (submit, update, get, remove, store/get result)
- Automatic timestamp management
"""

import pytest
from datetime import datetime, timezone

from domain.entities.task import Task, TaskProgress
from infrastructure.services.task_manager import InMemoryTaskManager


class TestTaskProgress:
    """Tests for TaskProgress model."""

    def test_create_progress_with_all_fields(self):
        """Should create TaskProgress with all fields specified."""
        progress = TaskProgress(current=5, total=10, percentage=50.0)

        assert progress.current == 5
        assert progress.total == 10
        assert progress.percentage == 50.0

    def test_create_progress_with_defaults(self):
        """Should create TaskProgress with default values."""
        progress = TaskProgress()

        assert progress.current == 0
        assert progress.total == 0
        assert progress.percentage == 0.0

    def test_create_progress_partial_fields(self):
        """Should create TaskProgress with partial fields."""
        progress = TaskProgress(current=3, total=20)

        assert progress.current == 3
        assert progress.total == 20
        assert progress.percentage == 0.0

    def test_progress_serialization(self):
        """Should serialize TaskProgress to dict correctly."""
        progress = TaskProgress(current=7, total=14, percentage=50.0)
        data = progress.model_dump()

        assert data == {"current": 7, "total": 14, "percentage": 50.0}

    def test_progress_from_dict(self):
        """Should create TaskProgress from dict."""
        data = {"current": 25, "total": 100, "percentage": 25.0}
        progress = TaskProgress(**data)

        assert progress.current == 25
        assert progress.total == 100
        assert progress.percentage == 25.0


class TestTask:
    """Tests for Task entity model."""

    def test_create_task_minimal(self):
        """Should create Task with only required fields."""
        task = Task(task_id="test-123", message="Test task", status="pending")

        assert task.task_id == "test-123"
        assert task.message == "Test task"
        assert task.status == "pending"
        assert task.task_type is None
        assert task.progress is None
        assert task.error_details is None
        assert task.result is None
        assert task.created_at is None
        assert task.updated_at is None
        assert task.started_at is None
        assert task.completed_at is None

    def test_create_task_with_all_fields(self):
        """Should create Task with all fields specified."""
        now = datetime.now(timezone.utc)
        progress = TaskProgress(current=5, total=10, percentage=50.0)

        task = Task(
            task_id="task-456",
            message="Processing leads",
            status="in_progress",
            task_type="insert_leads",
            progress=progress,
            error_details=None,
            result={"processed": 5},
            created_at=now,
            updated_at=now,
            started_at=now,
            completed_at=None
        )

        assert task.task_id == "task-456"
        assert task.message == "Processing leads"
        assert task.status == "in_progress"
        assert task.task_type == "insert_leads"
        assert task.progress.current == 5
        assert task.progress.total == 10
        assert task.result == {"processed": 5}
        assert task.created_at == now
        assert task.updated_at == now
        assert task.started_at == now
        assert task.completed_at is None

    def test_create_task_with_error_details(self):
        """Should create failed Task with error details."""
        task = Task(
            task_id="task-error",
            message="Task failed",
            status="failed",
            error_details="Connection timeout after 30 seconds"
        )

        assert task.status == "failed"
        assert task.error_details == "Connection timeout after 30 seconds"

    def test_task_serialization(self):
        """Should serialize Task to dict correctly."""
        progress = TaskProgress(current=3, total=10, percentage=30.0)
        now = datetime(2025, 1, 9, 12, 0, 0)

        task = Task(
            task_id="task-serial",
            message="Serialization test",
            status="in_progress",
            task_type="test_type",
            progress=progress,
            created_at=now,
            updated_at=now
        )

        data = task.model_dump()

        assert data["task_id"] == "task-serial"
        assert data["message"] == "Serialization test"
        assert data["status"] == "in_progress"
        assert data["task_type"] == "test_type"
        assert data["progress"]["current"] == 3
        assert data["progress"]["total"] == 10
        assert data["progress"]["percentage"] == 30.0

    def test_task_from_dict(self):
        """Should create Task from dict."""
        data = {
            "task_id": "from-dict",
            "message": "Created from dict",
            "status": "completed",
            "task_type": "generate_campaign",
            "progress": {"current": 100, "total": 100, "percentage": 100.0}
        }

        task = Task(**data)

        assert task.task_id == "from-dict"
        assert task.status == "completed"
        assert task.task_type == "generate_campaign"
        assert task.progress.percentage == 100.0


class TestInMemoryTaskManager:
    """Tests for InMemoryTaskManager implementation."""

    @pytest.fixture
    def task_manager(self) -> InMemoryTaskManager:
        """Create a fresh task manager for each test."""
        return InMemoryTaskManager()

    # --- submit_task tests ---

    @pytest.mark.asyncio
    async def test_submit_task_without_type(self, task_manager: InMemoryTaskManager):
        """Should create task without task_type specified."""
        task = await task_manager.submit_task("task-001")

        assert task.task_id == "task-001"
        assert task.message == "Task submitted"
        assert task.status == "pending"
        assert task.task_type is None

    @pytest.mark.asyncio
    async def test_submit_task_with_type(self, task_manager: InMemoryTaskManager):
        """Should create task with task_type specified."""
        task = await task_manager.submit_task("task-002", task_type="insert_leads")

        assert task.task_id == "task-002"
        assert task.status == "pending"
        assert task.task_type == "insert_leads"

    @pytest.mark.asyncio
    async def test_submit_task_sets_created_at(self, task_manager: InMemoryTaskManager):
        """Should set created_at timestamp on task submission."""
        task = await task_manager.submit_task("task-003")

        assert task.created_at is not None
        assert isinstance(task.created_at, datetime)

    @pytest.mark.asyncio
    async def test_submit_task_sets_updated_at(self, task_manager: InMemoryTaskManager):
        """Should set updated_at timestamp on task submission."""
        task = await task_manager.submit_task("task-004")

        assert task.updated_at is not None
        assert task.updated_at == task.created_at

    @pytest.mark.asyncio
    async def test_submit_task_started_at_is_none(self, task_manager: InMemoryTaskManager):
        """Should not set started_at timestamp on task submission."""
        task = await task_manager.submit_task("task-005")

        assert task.started_at is None

    @pytest.mark.asyncio
    async def test_submit_task_completed_at_is_none(self, task_manager: InMemoryTaskManager):
        """Should not set completed_at timestamp on task submission."""
        task = await task_manager.submit_task("task-006")

        assert task.completed_at is None

    @pytest.mark.asyncio
    async def test_submit_task_persists_task(self, task_manager: InMemoryTaskManager):
        """Should persist task in internal storage."""
        await task_manager.submit_task("task-007", task_type="test")

        assert "task-007" in task_manager.tasks
        assert task_manager.tasks["task-007"].task_type == "test"

    # --- update_task tests ---

    @pytest.mark.asyncio
    async def test_update_task_changes_message_and_status(self, task_manager: InMemoryTaskManager):
        """Should update task message and status."""
        await task_manager.submit_task("task-010")

        updated = await task_manager.update_task(
            "task-010",
            message="Processing",
            status="in_progress"
        )

        assert updated.message == "Processing"
        assert updated.status == "in_progress"

    @pytest.mark.asyncio
    async def test_update_task_raises_for_unknown_task(self, task_manager: InMemoryTaskManager):
        """Should raise ValueError for non-existent task."""
        with pytest.raises(ValueError, match="Task with ID unknown-task not found"):
            await task_manager.update_task(
                "unknown-task",
                message="Update",
                status="in_progress"
            )

    @pytest.mark.asyncio
    async def test_update_task_with_progress(self, task_manager: InMemoryTaskManager):
        """Should update task with progress information."""
        await task_manager.submit_task("task-011")
        progress = TaskProgress(current=25, total=100, percentage=25.0)

        updated = await task_manager.update_task(
            "task-011",
            message="Processing 25/100",
            status="in_progress",
            progress=progress
        )

        assert updated.progress is not None
        assert updated.progress.current == 25
        assert updated.progress.total == 100
        assert updated.progress.percentage == 25.0

    @pytest.mark.asyncio
    async def test_update_task_with_error_details(self, task_manager: InMemoryTaskManager):
        """Should update task with error details on failure."""
        await task_manager.submit_task("task-012")

        updated = await task_manager.update_task(
            "task-012",
            message="Task failed",
            status="failed",
            error_details="Database connection refused"
        )

        assert updated.status == "failed"
        assert updated.error_details == "Database connection refused"

    @pytest.mark.asyncio
    async def test_update_task_preserves_task_type(self, task_manager: InMemoryTaskManager):
        """Should preserve task_type when updating."""
        await task_manager.submit_task("task-013", task_type="generate_campaign")

        updated = await task_manager.update_task(
            "task-013",
            message="Started",
            status="in_progress"
        )

        assert updated.task_type == "generate_campaign"

    @pytest.mark.asyncio
    async def test_update_task_preserves_created_at(self, task_manager: InMemoryTaskManager):
        """Should preserve created_at when updating."""
        task = await task_manager.submit_task("task-014")
        original_created_at = task.created_at

        updated = await task_manager.update_task(
            "task-014",
            message="Updated",
            status="in_progress"
        )

        assert updated.created_at == original_created_at

    @pytest.mark.asyncio
    async def test_update_task_changes_updated_at(self, task_manager: InMemoryTaskManager):
        """Should update updated_at timestamp on each update."""
        task = await task_manager.submit_task("task-015")
        original_updated_at = task.updated_at

        # Small delay to ensure different timestamp
        import asyncio
        await asyncio.sleep(0.01)

        updated = await task_manager.update_task(
            "task-015",
            message="Updated",
            status="in_progress"
        )

        assert updated.updated_at is not None
        assert updated.updated_at >= original_updated_at

    # --- Timestamp behavior tests ---

    @pytest.mark.asyncio
    async def test_started_at_set_when_status_becomes_in_progress(
        self, task_manager: InMemoryTaskManager
    ):
        """Should set started_at when task transitions to in_progress."""
        task = await task_manager.submit_task("task-020")
        assert task.started_at is None

        updated = await task_manager.update_task(
            "task-020",
            message="Processing",
            status="in_progress"
        )

        assert updated.started_at is not None
        assert isinstance(updated.started_at, datetime)

    @pytest.mark.asyncio
    async def test_started_at_not_overwritten_on_subsequent_updates(
        self, task_manager: InMemoryTaskManager
    ):
        """Should not overwrite started_at on subsequent in_progress updates."""
        await task_manager.submit_task("task-021")

        # First transition to in_progress
        first_update = await task_manager.update_task(
            "task-021",
            message="Processing",
            status="in_progress"
        )
        original_started_at = first_update.started_at

        # Second update while still in_progress
        import asyncio
        await asyncio.sleep(0.01)

        second_update = await task_manager.update_task(
            "task-021",
            message="Still processing",
            status="in_progress"
        )

        assert second_update.started_at == original_started_at

    @pytest.mark.asyncio
    async def test_completed_at_set_when_status_becomes_completed(
        self, task_manager: InMemoryTaskManager
    ):
        """Should set completed_at when task transitions to completed."""
        await task_manager.submit_task("task-022")
        await task_manager.update_task("task-022", message="Processing", status="in_progress")

        completed = await task_manager.update_task(
            "task-022",
            message="Done",
            status="completed"
        )

        assert completed.completed_at is not None
        assert isinstance(completed.completed_at, datetime)

    @pytest.mark.asyncio
    async def test_completed_at_set_when_status_becomes_failed(
        self, task_manager: InMemoryTaskManager
    ):
        """Should set completed_at when task transitions to failed."""
        await task_manager.submit_task("task-023")
        await task_manager.update_task("task-023", message="Processing", status="in_progress")

        failed = await task_manager.update_task(
            "task-023",
            message="Failed",
            status="failed",
            error_details="Error occurred"
        )

        assert failed.completed_at is not None
        assert isinstance(failed.completed_at, datetime)

    @pytest.mark.asyncio
    async def test_completed_at_not_overwritten_on_subsequent_updates(
        self, task_manager: InMemoryTaskManager
    ):
        """Should not overwrite completed_at on subsequent updates."""
        await task_manager.submit_task("task-024")

        completed = await task_manager.update_task(
            "task-024",
            message="Done",
            status="completed"
        )
        original_completed_at = completed.completed_at

        import asyncio
        await asyncio.sleep(0.01)

        # Update again (though this is unusual)
        updated_again = await task_manager.update_task(
            "task-024",
            message="Still done",
            status="completed"
        )

        assert updated_again.completed_at == original_completed_at

    # --- get_task_status tests ---

    @pytest.mark.asyncio
    async def test_get_task_status_returns_existing_task(
        self, task_manager: InMemoryTaskManager
    ):
        """Should return task status for existing task."""
        await task_manager.submit_task("task-030", task_type="test")

        task = await task_manager.get_task_status("task-030")

        assert task.task_id == "task-030"
        assert task.status == "pending"
        assert task.task_type == "test"

    @pytest.mark.asyncio
    async def test_get_task_status_returns_unknown_for_nonexistent(
        self, task_manager: InMemoryTaskManager
    ):
        """Should return unknown status for non-existent task."""
        task = await task_manager.get_task_status("nonexistent-task")

        assert task.task_id == "nonexistent-task"
        assert task.status == "unknown"
        assert task.message == "Task not found"

    # --- remove_task tests ---

    @pytest.mark.asyncio
    async def test_remove_task_returns_true_for_existing(
        self, task_manager: InMemoryTaskManager
    ):
        """Should return True when removing existing task."""
        await task_manager.submit_task("task-040")

        result = await task_manager.remove_task("task-040")

        assert result is True
        assert "task-040" not in task_manager.tasks

    @pytest.mark.asyncio
    async def test_remove_task_returns_false_for_nonexistent(
        self, task_manager: InMemoryTaskManager
    ):
        """Should return False when task does not exist."""
        result = await task_manager.remove_task("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_remove_task_cleans_up_associated_result(
        self, task_manager: InMemoryTaskManager
    ):
        """Should remove associated result when task is removed."""
        await task_manager.submit_task("task-041")
        await task_manager.store_result("task-041", {"data": "test"})

        # Verify result exists
        assert await task_manager.get_result("task-041") is not None

        # Remove task
        await task_manager.remove_task("task-041")

        # Verify result is also removed
        assert await task_manager.get_result("task-041") is None

    # --- store_result and get_result tests ---

    @pytest.mark.asyncio
    async def test_store_result_stores_data(self, task_manager: InMemoryTaskManager):
        """Should store result data."""
        await task_manager.submit_task("task-050")
        result_data = {"leads_inserted": 100, "errors": []}

        await task_manager.store_result("task-050", result_data)

        assert task_manager.results["task-050"] == result_data

    @pytest.mark.asyncio
    async def test_get_result_returns_stored_data(self, task_manager: InMemoryTaskManager):
        """Should return stored result data."""
        await task_manager.submit_task("task-051")
        result_data = {"campaign_id": "abc123", "status": "created"}
        await task_manager.store_result("task-051", result_data)

        result = await task_manager.get_result("task-051")

        assert result == result_data

    @pytest.mark.asyncio
    async def test_get_result_returns_none_for_no_result(
        self, task_manager: InMemoryTaskManager
    ):
        """Should return None when no result stored."""
        await task_manager.submit_task("task-052")

        result = await task_manager.get_result("task-052")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_result_returns_none_for_nonexistent_task(
        self, task_manager: InMemoryTaskManager
    ):
        """Should return None for non-existent task."""
        result = await task_manager.get_result("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_store_result_can_store_various_types(
        self, task_manager: InMemoryTaskManager
    ):
        """Should store various data types as results."""
        await task_manager.submit_task("task-053")

        # Store dict
        await task_manager.store_result("task-053", {"key": "value"})
        assert await task_manager.get_result("task-053") == {"key": "value"}

        # Store list
        await task_manager.store_result("task-053", [1, 2, 3])
        assert await task_manager.get_result("task-053") == [1, 2, 3]

        # Store string
        await task_manager.store_result("task-053", "simple result")
        assert await task_manager.get_result("task-053") == "simple result"

        # Store None explicitly
        await task_manager.store_result("task-053", None)
        assert await task_manager.get_result("task-053") is None

    # --- Integration/workflow tests ---

    @pytest.mark.asyncio
    async def test_full_task_lifecycle(self, task_manager: InMemoryTaskManager):
        """Should handle complete task lifecycle from submission to completion."""
        # Submit task
        task = await task_manager.submit_task("lifecycle-task", task_type="insert_leads")
        assert task.status == "pending"
        assert task.started_at is None
        assert task.completed_at is None

        # Start processing
        task = await task_manager.update_task(
            "lifecycle-task",
            message="Starting",
            status="in_progress"
        )
        assert task.status == "in_progress"
        assert task.started_at is not None
        assert task.completed_at is None

        # Progress update
        task = await task_manager.update_task(
            "lifecycle-task",
            message="Processing 50/100",
            status="in_progress",
            progress=TaskProgress(current=50, total=100, percentage=50.0)
        )
        assert task.progress.percentage == 50.0

        # Complete
        task = await task_manager.update_task(
            "lifecycle-task",
            message="Completed",
            status="completed"
        )
        assert task.status == "completed"
        assert task.completed_at is not None

        # Store result
        await task_manager.store_result("lifecycle-task", {"inserted": 100})

        # Verify result
        result = await task_manager.get_result("lifecycle-task")
        assert result == {"inserted": 100}

        # Cleanup
        removed = await task_manager.remove_task("lifecycle-task")
        assert removed is True
        assert await task_manager.get_result("lifecycle-task") is None

    @pytest.mark.asyncio
    async def test_multiple_concurrent_tasks(self, task_manager: InMemoryTaskManager):
        """Should handle multiple tasks concurrently."""
        # Submit multiple tasks
        await task_manager.submit_task("task-a", task_type="type_a")
        await task_manager.submit_task("task-b", task_type="type_b")
        await task_manager.submit_task("task-c", task_type="type_c")

        # Update different tasks
        await task_manager.update_task("task-a", message="A processing", status="in_progress")
        await task_manager.update_task("task-b", message="B done", status="completed")
        await task_manager.update_task("task-c", message="C failed", status="failed")

        # Verify each task has correct state
        task_a = await task_manager.get_task_status("task-a")
        task_b = await task_manager.get_task_status("task-b")
        task_c = await task_manager.get_task_status("task-c")

        assert task_a.status == "in_progress"
        assert task_a.task_type == "type_a"

        assert task_b.status == "completed"
        assert task_b.task_type == "type_b"

        assert task_c.status == "failed"
        assert task_c.task_type == "type_c"

        # Verify correct count
        assert len(task_manager.tasks) == 3

    # --- get_running_tasks tests ---

    @pytest.mark.asyncio
    async def test_get_running_tasks_returns_pending_tasks(
        self, task_manager: InMemoryTaskManager
    ):
        """Should return tasks with pending status."""
        await task_manager.submit_task("task-pending", task_type="test")

        running_tasks = await task_manager.get_running_tasks()

        assert len(running_tasks) == 1
        assert running_tasks[0].task_id == "task-pending"
        assert running_tasks[0].status == "pending"

    @pytest.mark.asyncio
    async def test_get_running_tasks_returns_processing_tasks(
        self, task_manager: InMemoryTaskManager
    ):
        """Should return tasks with processing status."""
        await task_manager.submit_task("task-processing", task_type="test")
        await task_manager.update_task(
            "task-processing",
            message="Processing",
            status="processing"
        )

        running_tasks = await task_manager.get_running_tasks()

        assert len(running_tasks) == 1
        assert running_tasks[0].task_id == "task-processing"
        assert running_tasks[0].status == "processing"

    @pytest.mark.asyncio
    async def test_get_running_tasks_returns_in_progress_tasks(
        self, task_manager: InMemoryTaskManager
    ):
        """Should return tasks with in_progress status."""
        await task_manager.submit_task("task-in-progress", task_type="test")
        await task_manager.update_task(
            "task-in-progress",
            message="In progress",
            status="in_progress"
        )

        running_tasks = await task_manager.get_running_tasks()

        assert len(running_tasks) == 1
        assert running_tasks[0].task_id == "task-in-progress"
        assert running_tasks[0].status == "in_progress"

    @pytest.mark.asyncio
    async def test_get_running_tasks_excludes_completed_tasks(
        self, task_manager: InMemoryTaskManager
    ):
        """Should not return tasks with completed status."""
        await task_manager.submit_task("task-completed", task_type="test")
        await task_manager.update_task(
            "task-completed",
            message="Completed",
            status="completed"
        )

        running_tasks = await task_manager.get_running_tasks()

        assert len(running_tasks) == 0

    @pytest.mark.asyncio
    async def test_get_running_tasks_excludes_failed_tasks(
        self, task_manager: InMemoryTaskManager
    ):
        """Should not return tasks with failed status."""
        await task_manager.submit_task("task-failed", task_type="test")
        await task_manager.update_task(
            "task-failed",
            message="Failed",
            status="failed"
        )

        running_tasks = await task_manager.get_running_tasks()

        assert len(running_tasks) == 0

    @pytest.mark.asyncio
    async def test_get_running_tasks_returns_multiple_running_tasks(
        self, task_manager: InMemoryTaskManager
    ):
        """Should return all tasks with running statuses."""
        await task_manager.submit_task("task-1", task_type="type_a")
        await task_manager.submit_task("task-2", task_type="type_b")
        await task_manager.update_task("task-2", message="Processing", status="in_progress")
        await task_manager.submit_task("task-3", task_type="type_a")
        await task_manager.update_task("task-3", message="Processing", status="processing")

        running_tasks = await task_manager.get_running_tasks()

        assert len(running_tasks) == 3
        task_ids = {task.task_id for task in running_tasks}
        assert task_ids == {"task-1", "task-2", "task-3"}

    @pytest.mark.asyncio
    async def test_get_running_tasks_filters_by_task_type(
        self, task_manager: InMemoryTaskManager
    ):
        """Should filter running tasks by task_type when provided."""
        await task_manager.submit_task("task-a1", task_type="insert_leads")
        await task_manager.submit_task("task-a2", task_type="insert_leads")
        await task_manager.submit_task("task-b1", task_type="generate_campaign")
        await task_manager.update_task("task-a1", message="Processing", status="in_progress")
        await task_manager.update_task("task-b1", message="Processing", status="in_progress")

        running_tasks = await task_manager.get_running_tasks(task_type="insert_leads")

        assert len(running_tasks) == 2
        for task in running_tasks:
            assert task.task_type == "insert_leads"

    @pytest.mark.asyncio
    async def test_get_running_tasks_filter_returns_empty_for_no_matches(
        self, task_manager: InMemoryTaskManager
    ):
        """Should return empty list when no tasks match the filter."""
        await task_manager.submit_task("task-1", task_type="insert_leads")
        await task_manager.submit_task("task-2", task_type="insert_leads")

        running_tasks = await task_manager.get_running_tasks(task_type="generate_campaign")

        assert len(running_tasks) == 0

    @pytest.mark.asyncio
    async def test_get_running_tasks_filter_excludes_completed_of_same_type(
        self, task_manager: InMemoryTaskManager
    ):
        """Should exclude completed tasks even when filtering by type."""
        await task_manager.submit_task("task-1", task_type="insert_leads")
        await task_manager.submit_task("task-2", task_type="insert_leads")
        await task_manager.update_task("task-2", message="Done", status="completed")

        running_tasks = await task_manager.get_running_tasks(task_type="insert_leads")

        assert len(running_tasks) == 1
        assert running_tasks[0].task_id == "task-1"

    @pytest.mark.asyncio
    async def test_get_running_tasks_returns_empty_when_no_tasks(
        self, task_manager: InMemoryTaskManager
    ):
        """Should return empty list when no tasks exist."""
        running_tasks = await task_manager.get_running_tasks()

        assert running_tasks == []

    @pytest.mark.asyncio
    async def test_get_running_tasks_mixed_statuses_scenario(
        self, task_manager: InMemoryTaskManager
    ):
        """Should correctly filter in a mixed scenario with all statuses."""
        # Create tasks with various statuses
        await task_manager.submit_task("pending-1", task_type="type_a")  # pending
        await task_manager.submit_task("in-progress-1", task_type="type_a")
        await task_manager.update_task("in-progress-1", message="Working", status="in_progress")
        await task_manager.submit_task("processing-1", task_type="type_b")
        await task_manager.update_task("processing-1", message="Processing", status="processing")
        await task_manager.submit_task("completed-1", task_type="type_a")
        await task_manager.update_task("completed-1", message="Done", status="completed")
        await task_manager.submit_task("failed-1", task_type="type_b")
        await task_manager.update_task("failed-1", message="Error", status="failed")

        # Get all running tasks
        all_running = await task_manager.get_running_tasks()
        assert len(all_running) == 3
        running_ids = {task.task_id for task in all_running}
        assert running_ids == {"pending-1", "in-progress-1", "processing-1"}

        # Get running tasks filtered by type_a
        type_a_running = await task_manager.get_running_tasks(task_type="type_a")
        assert len(type_a_running) == 2
        type_a_ids = {task.task_id for task in type_a_running}
        assert type_a_ids == {"pending-1", "in-progress-1"}

        # Get running tasks filtered by type_b
        type_b_running = await task_manager.get_running_tasks(task_type="type_b")
        assert len(type_b_running) == 1
        assert type_b_running[0].task_id == "processing-1"
