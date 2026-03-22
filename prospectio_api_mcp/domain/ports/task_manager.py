from abc import ABC, abstractmethod
from typing import Any

from domain.entities.task import Task, TaskProgress


class TaskManagerPort(ABC):
    """
    Port for managing background tasks.
    """

    @abstractmethod
    async def submit_task(self, task_id: str, task_type: str | None = None) -> Task:
        """
        Submit a new background task.

        Args:
            task_id: Unique task identifier.
            task_type: Optional type classification for the task.

        Returns:
            The created Task entity.
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    async def get_task_status(self, task_id: str) -> Task:
        """
        Get the status of a task.

        Args:
            task_id: The task ID.

        Returns:
            The task entity with status.
        """
        pass

    @abstractmethod
    async def remove_task(self, task_id: str) -> bool:
        """
        Remove a completed or failed task from the manager.

        Args:
            task_id: The task ID to remove.

        Returns:
            True if the task was removed, False if not found.
        """
        pass

    @abstractmethod
    async def store_result(self, task_id: str, result: Any) -> None:
        """
        Store a result for a task.

        Args:
            task_id: The task ID.
            result: The result data to store.
        """
        pass

    @abstractmethod
    async def get_result(self, task_id: str) -> Any | None:
        """
        Get the stored result for a task.

        Args:
            task_id: The task ID.

        Returns:
            The stored result, or None if not found.
        """
        pass

    @abstractmethod
    async def get_running_tasks(self, task_type: str | None = None) -> list[Task]:
        """
        Get all tasks that are currently running.

        Args:
            task_type: Optional filter by task type.

        Returns:
            List of running tasks.
        """
        pass
