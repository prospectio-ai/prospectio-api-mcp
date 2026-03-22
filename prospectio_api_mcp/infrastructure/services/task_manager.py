from datetime import datetime, timezone
from typing import Any, Dict

from domain.entities.task import Task, TaskProgress
from domain.ports.task_manager import TaskManagerPort


class InMemoryTaskManager(TaskManagerPort):
    """
    In-memory implementation of TaskManagerPort using asyncio.
    """

    RUNNING_STATUSES = {"pending", "in_progress", "processing"}

    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.results: Dict[str, Any] = {}

    async def submit_task(self, task_id: str, task_type: str | None = None) -> Task:
        """
        Submit a new background task.

        Args:
            task_id: Unique task identifier.
            task_type: Optional type classification for the task.

        Returns:
            The created Task entity.
        """
        now = datetime.now(timezone.utc)
        task = Task(
            task_id=task_id,
            message="Task submitted",
            status="pending",
            task_type=task_type,
            created_at=now,
            updated_at=now,
        )
        self.tasks[task_id] = task
        return task

    async def update_task(
        self,
        task_id: str,
        message: str,
        status: str,
        progress: TaskProgress | None = None,
        error_details: str | None = None,
    ) -> Task:
        """
        Update the status of a background task.

        Args:
            task_id: Unique task identifier.
            message: Status message.
            status: New status string.
            progress: Optional progress information.
            error_details: Optional error details for failed tasks.

        Returns:
            The updated Task entity.
        """
        if task_id not in self.tasks:
            raise ValueError(f"Task with ID {task_id} not found.")

        task = self.tasks[task_id]
        now = datetime.now(timezone.utc)

        task.message = message
        task.status = status
        task.updated_at = now

        if progress is not None:
            task.progress = progress

        if error_details is not None:
            task.error_details = error_details

        # Set started_at on first transition to in_progress
        if status == "in_progress" and task.started_at is None:
            task.started_at = now

        # Set completed_at on first transition to completed or failed
        if status in ("completed", "failed") and task.completed_at is None:
            task.completed_at = now

        return task

    async def get_task_status(self, task_id: str) -> Task:
        """
        Get the status of a task.

        Args:
            task_id: The task ID.

        Returns:
            The task entity with status.
        """
        return self.tasks.get(
            task_id,
            Task(task_id=task_id, message="Task not found", status="unknown"),
        )

    async def remove_task(self, task_id: str) -> bool:
        """
        Remove a completed or failed task from the manager.

        Args:
            task_id: The task ID to remove.

        Returns:
            True if the task was removed, False if not found.
        """
        if task_id in self.tasks:
            del self.tasks[task_id]
            self.results.pop(task_id, None)
            return True
        return False

    async def store_result(self, task_id: str, result: Any) -> None:
        """
        Store a result for a task.

        Args:
            task_id: The task ID.
            result: The result data to store.
        """
        self.results[task_id] = result

    async def get_result(self, task_id: str) -> Any | None:
        """
        Get the stored result for a task.

        Args:
            task_id: The task ID.

        Returns:
            The stored result, or None if not found.
        """
        return self.results.get(task_id)

    async def get_running_tasks(self, task_type: str | None = None) -> list[Task]:
        """
        Get all tasks that are currently running.

        Args:
            task_type: Optional filter by task type.

        Returns:
            List of running tasks.
        """
        running = [
            task
            for task in self.tasks.values()
            if task.status in self.RUNNING_STATUSES
        ]

        if task_type is not None:
            running = [task for task in running if task.task_type == task_type]

        return running


task_manager = InMemoryTaskManager()
