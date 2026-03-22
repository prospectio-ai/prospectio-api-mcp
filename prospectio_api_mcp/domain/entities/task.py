from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime


class TaskProgress(BaseModel):
    """Progress information for a task."""
    current: int = Field(default=0, description="Current item being processed")
    total: int = Field(default=0, description="Total items to process")
    percentage: float = Field(default=0.0, description="Completion percentage (0-100)")


class Task(BaseModel):
    """Domain entity representing a background task."""
    task_id: str
    message: str
    status: str
    task_type: Optional[str] = Field(default=None, description="Type of task")
    progress: Optional[TaskProgress] = Field(default=None, description="Progress information")
    error_details: Optional[str] = Field(default=None, description="Detailed error message")
    result: Optional[Any] = Field(default=None, description="Task result data")
    created_at: Optional[datetime] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
