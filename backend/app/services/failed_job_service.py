"""Failed Job Service.

Service for managing failed jobs in Dead Letter Queue.
"""

import traceback
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.logging import get_logger
from ..models.failed_job import FailedJob

logger = get_logger(__name__)


class FailedJobService:
    """Service for managing failed jobs."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_failed_job(
        self,
        job_id: str,
        task_name: str,
        job_args: list[Any] | None = None,
        job_kwargs: dict[str, Any] | None = None,
        error: Exception | None = None,
        retry_count: int = 0,
        max_retries: int = 3,
        metadata: dict[str, Any] | None = None
    ) -> FailedJob:
        """Create a failed job record in Dead Letter Queue.

        Args:
            job_id: ARQ job ID
            task_name: Task function name
            job_args: Job arguments
            job_kwargs: Job keyword arguments
            error: Exception that caused the failure
            retry_count: Number of retries attempted
            max_retries: Maximum retries configured
            metadata: Additional metadata (trace context, etc.)

        Returns:
            Created FailedJob record
        """
        error_type = type(error).__name__ if error else "UnknownError"
        error_message = str(error) if error else "Unknown error"
        error_traceback_str = None
        if error:
            error_traceback_str = ''.join(traceback.format_exception(type(error), error, error.__traceback__))

        failed_job = FailedJob(
            job_id=job_id,
            task_name=task_name,
            job_args=job_args or [],
            job_kwargs=job_kwargs or {},
            error_type=error_type,
            error_message=error_message,
            error_traceback=error_traceback_str,
            retry_count=str(retry_count),
            max_retries=str(max_retries),
            status="pending",
            job_metadata=metadata or {}
        )

        self.db.add(failed_job)
        await self.db.flush()

        logger.warning(
            "Job moved to Dead Letter Queue",
            extra={
                'job_id': job_id,
                'task_name': task_name,
                'retry_count': retry_count,
                'max_retries': max_retries,
                'error_type': error_type
            }
        )

        return failed_job
