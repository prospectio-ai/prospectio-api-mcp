from abc import ABC, abstractmethod
from typing import Any, List, Optional
from domain.entities.task import Task, TaskProgress


class TaskManagerPort(ABC):
    """
    Port for managing background tasks.
    """

    @abstractmethod
    async def submit_task(self, task_id: str, task_type: Optional[str] = None) -> Task:
        """
        Submit a coroutine as a background task.

        Args:
            task_id (str): Unique task identifier.
            task_type (Optional[str]): Type of task (e.g., 'insert_leads', 'generate_campaign').

        Returns:
            Task: The created task entity.
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    async def get_task_status(self, task_id: str) -> Task:
        """
        Get the status of a task.

        Args:
            task_id (str): The task ID.

        Returns:
            Task: The task entity with status.
        """
        pass

    @abstractmethod
    async def remove_task(self, task_id: str) -> bool:
        """
        Remove a completed or failed task from the manager.

        Args:
            task_id (str): The task ID to remove.

        Returns:
            bool: True if task was removed, False if not found.
        """
        pass

    @abstractmethod
    async def store_result(self, task_id: str, result: Any) -> None:
        """
        Store the result of a completed task.

        Args:
            task_id (str): The task ID.
            result (Any): The result data to store.

        Returns:
            None
        """
        pass

    @abstractmethod
    async def get_result(self, task_id: str) -> Optional[Any]:
        """
        Get the stored result of a task.

        Args:
            task_id (str): The task ID.

        Returns:
            Optional[Any]: The stored result, or None if not found.
        """
        pass

    @abstractmethod
    async def get_running_tasks(self, task_type: Optional[str] = None) -> List[Task]:
        """
        Get all running tasks (status in pending, processing, in_progress).

        Args:
            task_type (Optional[str]): If provided, filter tasks by this type.

        Returns:
            List[Task]: List of running tasks.
        """
        pass
