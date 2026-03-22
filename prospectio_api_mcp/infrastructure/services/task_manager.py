import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from domain.ports.task_manager import TaskManagerPort
from domain.entities.task import Task, TaskProgress


class InMemoryTaskManager(TaskManagerPort):
    """
    In-memory implementation of TaskManagerPort using asyncio.
    Thread-safe implementation with TTL-based cleanup for expired tasks.
    """

    def __init__(self, task_ttl_seconds: int = 3600):
        """
        Initialize the InMemoryTaskManager.

        Args:
            task_ttl_seconds (int): Time-to-live for completed/failed tasks in seconds.
                                    Default is 3600 (1 hour).
        """
        self.tasks: Dict[str, Task] = {}
        self.results: Dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._task_ttl_seconds = task_ttl_seconds

    async def submit_task(self, task_id: str, task_type: Optional[str] = None) -> Task:
        """
        Submit a coroutine as a background task.

        Args:
            task_id (str): Unique task identifier.
            task_type (Optional[str]): Type of task (e.g., 'insert_leads', 'generate_campaign').

        Returns:
            Task: The created task entity.
        """
        now = datetime.now(timezone.utc)
        task = Task(
            task_id=task_id,
            message="Task submitted",
            status="pending",
            task_type=task_type,
            created_at=now,
            updated_at=now
        )
        async with self._lock:
            self.tasks[task_id] = task
        return task

    async def update_task(
        self,
        task_id: str,
        message: str,
        status: str,
        progress: Optional[TaskProgress] = None,
        error_details: Optional[str] = None
    ) -> Task:
        """
        Update the status of a background task.

        Args:
            task_id (str): Unique task identifier.
            message (str): Status message.
            status (str): Task status (e.g., 'pending', 'in_progress', 'completed', 'failed').
            progress (Optional[TaskProgress]): Progress information for the task.
            error_details (Optional[str]): Detailed error message if task failed.

        Returns:
            Task: The updated task entity.
        """
        async with self._lock:
            if task_id not in self.tasks:
                raise ValueError(f"Task with ID {task_id} not found.")

            task = self.tasks[task_id]
            now = datetime.now(timezone.utc)

            # Handle timestamp updates based on status transitions
            started_at = task.started_at
            completed_at = task.completed_at

            # Set started_at when task transitions to in_progress for the first time
            if status == "in_progress" and task.started_at is None:
                started_at = now

            # Set completed_at when task transitions to completed or failed
            if status in ("completed", "failed") and task.completed_at is None:
                completed_at = now

            # Create updated task
            updated_task = Task(
                task_id=task_id,
                message=message,
                status=status,
                task_type=task.task_type,
                progress=progress,
                error_details=error_details,
                result=task.result,
                created_at=task.created_at,
                updated_at=now,
                started_at=started_at,
                completed_at=completed_at
            )
            self.tasks[task_id] = updated_task
            return updated_task

    async def get_task_status(self, task_id: str) -> Task:
        """
        Get the status of a task.

        Args:
            task_id (str): The task ID.

        Returns:
            Task: The task entity with status.
        """
        async with self._lock:
            return self.tasks.get(
                task_id,
                Task(task_id=task_id, message="Task not found", status="unknown")
            )

    async def remove_task(self, task_id: str) -> bool:
        """
        Remove a completed or failed task from the manager.

        Args:
            task_id (str): The task ID to remove.

        Returns:
            bool: True if task was removed, False if not found.
        """
        async with self._lock:
            if task_id in self.tasks:
                del self.tasks[task_id]
                # Also remove associated result if exists
                if task_id in self.results:
                    del self.results[task_id]
                return True
            return False

    async def store_result(self, task_id: str, result: Any) -> None:
        """
        Store the result of a completed task.

        Args:
            task_id (str): The task ID.
            result (Any): The result data to store.

        Returns:
            None
        """
        async with self._lock:
            self.results[task_id] = result

    async def get_result(self, task_id: str) -> Optional[Any]:
        """
        Get the stored result of a task.

        Args:
            task_id (str): The task ID.

        Returns:
            Optional[Any]: The stored result, or None if not found.
        """
        async with self._lock:
            return self.results.get(task_id)

    async def cleanup_expired_tasks(self) -> int:
        """
        Remove tasks where completed_at is older than TTL.

        Returns:
            int: Number of tasks removed.
        """
        now = datetime.now(timezone.utc)
        removed_count = 0

        async with self._lock:
            expired_task_ids = []
            for task_id, task in self.tasks.items():
                if task.completed_at is not None:
                    # Calculate age of completed task
                    age_seconds = (now - task.completed_at).total_seconds()
                    if age_seconds > self._task_ttl_seconds:
                        expired_task_ids.append(task_id)

            # Remove expired tasks and their results
            for task_id in expired_task_ids:
                del self.tasks[task_id]
                if task_id in self.results:
                    del self.results[task_id]
                removed_count += 1

        return removed_count

    async def get_running_tasks(self, task_type: Optional[str] = None) -> List[Task]:
        """
        Get all running tasks (status in pending, processing, in_progress).

        Args:
            task_type (Optional[str]): If provided, filter tasks by this type.

        Returns:
            List[Task]: List of running tasks.
        """
        running_statuses = {"pending", "processing", "in_progress"}

        async with self._lock:
            running_tasks = [
                task for task in self.tasks.values()
                if task.status in running_statuses
                and (task_type is None or task.task_type == task_type)
            ]

        return running_tasks


task_manager = InMemoryTaskManager()
