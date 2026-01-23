import asyncio
from datetime import UTC, datetime
from typing import Any

from ..core.config import settings
from ..core.logging import get_logger
from ..db.database import AsyncSessionLocal
from ..services.failed_job_service import FailedJobService
from ..models.failed_job import FailedJob

logger = get_logger(__name__)


async def retry_failed_jobs(ctx: dict[str, Any]) -> dict[str, int]:
    """Retry failed jobs that are marked as retryable.
    
    This cron task runs periodically to check for retryable jobs in the
    failed_jobs table and re-enqueues them if the external provider is available.
    
    Args:
        ctx: ARQ worker context containing Redis connection
        
    Returns:
        Dictionary with retry statistics
    """
    logger.info("Starting retry job check")
    
    stats = {
        'checked': 0,
        'retried': 0,
        'skipped': 0,
        'failed': 0
    }
    
    try:
        async with AsyncSessionLocal() as db:
            service = FailedJobService(db)
            
            # Get retryable jobs (limit to avoid overwhelming the system)
            retryable_jobs = await service.get_retryable_jobs(limit=100)
            stats['checked'] = len(retryable_jobs)
            
            if not retryable_jobs:
                logger.info("No retryable jobs found")
                return stats
            
            logger.info(
                f"Found {len(retryable_jobs)} retryable jobs",
                extra={'job_count': len(retryable_jobs)}
            )
            
            for failed_job in retryable_jobs:
                try:
                    if await _should_retry_job(failed_job):
                        await _retry_job(ctx, failed_job, db)
                        stats['retried'] += 1
                    else:
                        stats['skipped'] += 1
                        logger.debug(
                            "Skipping job retry - conditions not met",
                            extra={
                                'job_id': failed_job.job_id,
                                'task_name': failed_job.task_name
                            }
                        )
                        
                except Exception as e:
                    stats['failed'] += 1
                    logger.error(
                        f"Error retrying job {failed_job.job_id}",
                        extra={
                            'job_id': failed_job.job_id,
                            'error': str(e),
                            'exception_type': type(e).__name__
                        },
                        exc_info=True
                    )
            
            # Commit all status updates
            await db.commit()
        
        logger.info(
            "Retry job check completed",
            extra=stats
        )
        
        return stats
        
    except Exception as e:
        logger.error(
            "Critical error in retry job worker",
            extra={
                'error': str(e),
                'exception_type': type(e).__name__
            },
            exc_info=True
        )
        return stats


async def _should_retry_job(failed_job: FailedJob) -> bool:
    """Check if a job should be retried.
    
    For transient errors (NetworkTimeoutError, ProviderUnavailableError, 
    ExternalServiceError), we retry the job. For ProviderUnavailableError 
    specifically, the circuit breaker will determine if the provider is available.
    
    Strategy: We attempt retry and let the circuit breaker decide.
    If the circuit is still open, the job will fail again and be re-queued.
    
    Args:
        failed_job: FailedJob database record
        
    Returns:
        True if job should be retried, False otherwise
    """
    RETRYABLE_ERRORS = {
        'ProviderUnavailableError',
        'NetworkTimeoutError',
        'ExternalServiceError'
    }
    
    if failed_job.error_type not in RETRYABLE_ERRORS:
        logger.debug(
            f"Job {failed_job.job_id} error type is not retryable, skipping",
            extra={
                'job_id': failed_job.job_id,
                'error_type': failed_job.error_type,
                'retryable_errors': list(RETRYABLE_ERRORS)
            }
        )
        return False
    
    return True


async def _retry_job(ctx: dict[str, Any], failed_job: FailedJob, db: Any) -> None:
    """Re-enqueue a failed job for processing.
    
    Args:
        ctx: ARQ worker context
        failed_job: FailedJob database record
        db: Database session
    """
    logger.info(
        f"Retrying job {failed_job.job_id}",
        extra={
            'job_id': failed_job.job_id,
            'task_name': failed_job.task_name,
            'original_error': failed_job.error_type,
            'failed_at': str(failed_job.created_at)
        }
    )
    
    redis = ctx['redis']
    
    job_args = failed_job.job_args or []
    job_kwargs = failed_job.job_kwargs or {}
    
    try:
        new_job_id = f"{failed_job.job_id}_retry_{int(datetime.now(UTC).timestamp())}"
        
        await redis.enqueue_job(
            failed_job.task_name,
            *job_args,
            **job_kwargs,
            _job_id=new_job_id
        )
        
        failed_job.status = "retried"
        failed_job.reprocessed_job_id = new_job_id
        failed_job.reprocessed_at = datetime.now(UTC)
        
        await db.flush()
        
        logger.info(
            f"Successfully retried job {failed_job.job_id}",
            extra={
                'original_job_id': failed_job.job_id,
                'new_job_id': new_job_id,
                'task_name': failed_job.task_name
            }
        )
        
    except Exception as e:
        logger.error(
            f"Failed to re-enqueue job {failed_job.job_id}",
            extra={
                'job_id': failed_job.job_id,
                'task_name': failed_job.task_name,
                'error': str(e),
                'exception_type': type(e).__name__
            },
            exc_info=True
        )
        raise
