from datetime import datetime
from typing import Any

from pydantic import BaseModel


class TaskProgress(BaseModel):
    """Progress information for a running task."""
    current: int = 0
    total: int = 0
    percentage: float = 0.0


class Task(BaseModel):
    """Domain entity representing a background task."""
    task_id: str
    message: str
    status: str
    task_type: str | None = None
    progress: TaskProgress | None = None
    error_details: str | None = None
    result: Any | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None