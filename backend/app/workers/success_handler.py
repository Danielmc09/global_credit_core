from typing import Any

from ..core.logging import get_logger
from ..db.database import AsyncSessionLocal
from ..services.pending_job_service import PendingJobService

logger = get_logger(__name__)


async def handle_job_success(ctx: dict[str, Any], job: Any, result: Any) -> None:
    """Handle a job that has completed successfully.

    This function is called by ARQ when a job completes without errors.
    It updates the pending_job status to 'completed' and sets processed_at.

    Args:
        ctx: ARQ worker context
        job: ARQ job object containing job information
        result: The result returned by the job function
    """
    try:
        # Extract job_id (format: rt_{application_id})
        job_id = getattr(job, 'job_id', None) or getattr(job, 'id', None) or 'unknown'
        if job_id != 'unknown':
            job_id = str(job_id)

        task_name = getattr(job, 'function', None) or getattr(job, 'task_name', None) or 'unknown'

        logger.info(
            "Job completed successfully - updating pending_job status",
            extra={
                'job_id': job_id,
                'task_name': task_name
            }
        )

        # Update pending_job status to completed
        async with AsyncSessionLocal() as db:
            try:
                pending_job_service = PendingJobService(db)
                updated = await pending_job_service.mark_as_completed(job_id)

                if updated:
                    logger.info(
                        "Pending job status updated to completed",
                        extra={
                            'job_id': job_id,
                            'task_name': task_name
                        }
                    )
                else:
                    logger.warning(
                        "Could not update pending_job (may not exist or already processed)",
                        extra={
                            'job_id': job_id,
                            'task_name': task_name
                        }
                    )

            except Exception as db_error:
                await db.rollback()
                logger.error(
                    "Failed to update pending_job status after success",
                    extra={
                        'job_id': job_id,
                        'task_name': task_name,
                        'db_error': str(db_error)
                    },
                    exc_info=True
                )

    except Exception as handler_error:
        # Don't let handler errors affect the job completion
        logger.error(
            "Error in success handler (job still completed successfully)",
            extra={
                'job_id': getattr(job, 'job_id', 'unknown'),
                'handler_error': str(handler_error)
            },
            exc_info=True
        )
