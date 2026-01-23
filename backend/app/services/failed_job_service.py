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
        metadata: dict[str, Any] | None = None,
        is_retryable: bool | None = None,
        pending_job_id: Any | None = None
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
            is_retryable: Override for retryable detection (auto-detected if None)
            pending_job_id: Reference to original pending_job (if available)

        Returns:
            Created FailedJob record
        """
        from ..core.exceptions import ProviderUnavailableError
        
        error_type = type(error).__name__ if error else "UnknownError"
        error_message = str(error) if error else "Unknown error"
        error_traceback_str = None
        if error:
            error_traceback_str = ''.join(traceback.format_exception(type(error), error, error.__traceback__))

        if is_retryable is None:
            is_retryable = isinstance(error, ProviderUnavailableError)

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
            is_retryable=is_retryable,
            job_metadata=metadata or {},
            pending_job_id=pending_job_id
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
                'error_type': error_type,
                'is_retryable': is_retryable,
                'will_auto_retry': is_retryable
            }
        )

        return failed_job

    async def get_retryable_jobs(self, limit: int = 100) -> list[FailedJob]:
        """Get failed jobs that are retryable.
        
        Returns jobs that:
        - Have is_retryable=True (typically ProviderUnavailableError)
        - Have status='pending' (not already retried or reviewed)
        
        Args:
            limit: Maximum number of jobs to retrieve
            
        Returns:
            List of retryable FailedJob records, ordered by creation time (oldest first)
        """
        from sqlalchemy import select
        
        stmt = (
            select(FailedJob)
            .where(FailedJob.is_retryable == True)  # noqa: E712
            .where(FailedJob.status == "pending")
            .order_by(FailedJob.created_at.asc())
            .limit(limit)
        )
        
        result = await self.db.execute(stmt)
        jobs = list(result.scalars().all())
        
        logger.debug(
            f"Retrieved {len(jobs)} retryable jobs from DLQ",
            extra={'job_count': len(jobs), 'limit': limit}
        )
        
        return jobs
