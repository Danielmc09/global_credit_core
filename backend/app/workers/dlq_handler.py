"""Dead Letter Queue Handler.

Handles failed jobs after maximum retries and stores them in the DLQ.

ARQ calls this handler when a job fails after max_tries.
The handler stores the failed job in the database for manual review.
"""

from typing import Any

from ..core.logging import get_logger
from ..db.database import AsyncSessionLocal
from ..services.failed_job_service import FailedJobService

logger = get_logger(__name__)


async def handle_failed_job(ctx: dict[str, Any], job: Any, exc: Exception) -> None:
    """Handle a job that has failed after maximum retries.

    This function is called by ARQ when a job fails after max_tries.
    It stores the failed job in the Dead Letter Queue for manual review.

    Args:
        ctx: ARQ worker context
        job: ARQ job object containing job information
        exc: Exception that caused the final failure
    """
    try:
        job_id = getattr(job, 'job_id', None) or getattr(job, 'id', None) or 'unknown'
        if job_id != 'unknown':
            job_id = str(job_id)

        task_name = getattr(job, 'function', None) or getattr(job, 'task_name', None) or 'unknown'
        job_args = getattr(job, 'args', []) or []
        job_kwargs = getattr(job, 'kwargs', {}) or {}

        retry_count = getattr(job, 'retry_count', None) or ctx.get('retry_count', 0)
        max_retries = getattr(job, 'max_retries', None) or ctx.get('max_tries', 3)

        metadata = {}
        if hasattr(job, 'metadata') and job.metadata:
            metadata = job.metadata
        elif 'trace_context' in job_kwargs:
            metadata = {'trace_context': job_kwargs.get('trace_context')}
        elif 'trace_context' in ctx:
            metadata = {'trace_context': ctx.get('trace_context')}

        logger.error(
            "Job failed after maximum retries - moving to DLQ",
            extra={
                'job_id': job_id,
                'task_name': task_name,
                'retry_count': retry_count,
                'max_retries': max_retries,
                'error_type': type(exc).__name__,
                'error_message': str(exc)
            },
            exc_info=True
        )

        async with AsyncSessionLocal() as db:
            try:
                failed_job_service = FailedJobService(db)
                await failed_job_service.create_failed_job(
                    job_id=job_id,
                    task_name=task_name,
                    job_args=list(job_args) if job_args else None,
                    job_kwargs=dict(job_kwargs) if job_kwargs else None,
                    error=exc,
                    retry_count=retry_count,
                    max_retries=max_retries,
                    metadata=metadata
                )
                await db.commit()

                logger.info(
                    "Failed job stored in Dead Letter Queue",
                    extra={
                        'job_id': job_id,
                        'task_name': task_name
                    }
                )
            except Exception as db_error:
                await db.rollback()
                logger.error(
                    "Failed to store job in Dead Letter Queue",
                    extra={
                        'job_id': job_id,
                        'task_name': task_name,
                        'db_error': str(db_error)
                    },
                    exc_info=True
                )

    except Exception as handler_error:
        logger.critical(
            "Critical error in DLQ handler",
            extra={
                'job_id': getattr(job, 'job_id', 'unknown'),
                'handler_error': str(handler_error)
            },
            exc_info=True
        )
