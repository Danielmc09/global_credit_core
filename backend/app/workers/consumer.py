from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.logging import get_logger, set_request_id
from ..db.database import AsyncSessionLocal
from ..models.pending_job import PendingJob, PendingJobStatus
from ..infrastructure.monitoring import inject_trace_context

logger = get_logger(__name__)


async def _fetch_pending_jobs(db: AsyncSessionLocal, limit: int = 50):
    """Fetch pending jobs from the database."""
    pending_jobs_query = select(PendingJob).where(
        PendingJob.status == PendingJobStatus.PENDING.value
    ).order_by(PendingJob.created_at.asc()).limit(limit)
    
    result = await db.execute(pending_jobs_query)
    return result.scalars().all()


async def _enqueue_job_to_arq(redis, pending_job: PendingJob):
    """Enqueue a single job to ARQ.
    
    Uses the same job_id format as realtime enqueue (rt_{application_id})
    to enable ARQ duplicate detection. If the same application is already
    enqueued via realtime, ARQ will reject this duplicate job.
    """
    application_id = pending_job.job_args.get('application_id') if pending_job.job_args else None
    if not application_id:
        # Fallback to direct attribute if not in args
        application_id = str(pending_job.application_id)
    
    trace_context = {}
    inject_trace_context(trace_context)
    
    arq_job = await redis.enqueue_job(
        pending_job.task_name or 'process_credit_application',
        application_id,
        trace_context if trace_context else None,
        _job_id=f"rt_{application_id}",  # Use application_id, not pending_job.id
    )
    return arq_job, application_id


async def _handle_job_success(db: AsyncSession, pending_job: PendingJob, arq_job, application_id: str):
    """Update job status on successful enqueue."""
    pending_job.status = PendingJobStatus.ENQUEUED.value
    pending_job.arq_job_id = arq_job.job_id if arq_job else None
    pending_job.enqueued_at = datetime.now(UTC)
    
    await db.commit()
    
    logger.info(
        "Pending job enqueued to ARQ (DB Trigger -> Queue flow)",
        extra={
            'pending_job_id': str(pending_job.id),
            'application_id': application_id,
            'arq_job_id': arq_job.job_id if arq_job else None,
            'triggered_by': 'database_trigger'
        }
    )


async def _handle_job_failure(db: AsyncSession, pending_job: PendingJob, error: Exception):
    """Update job status and log on failure."""
    try:
        pending_job.status = PendingJobStatus.FAILED.value
        pending_job.error_message = str(error)
        pending_job.updated_at = datetime.now(UTC)
        await db.commit()
        
        logger.error(
            "Failed to enqueue pending job",
            extra={
                'pending_job_id': str(pending_job.id),
                'error': str(error)
            },
            exc_info=True
        )
    except Exception as inner_e:
        logger.error(
            "CRITICAL: Failed to update pending job status after failure",
            extra={'error': str(inner_e)},
            exc_info=True
        )


async def consume_pending_jobs_from_db(ctx):
    """CRITICAL: Consume pending jobs created by DB triggers and enqueue to ARQ.
    
    This task implements Requirement 3.7: "una operación en la base de datos genere
    trabajo a ser procesado de forma asíncrona (por ejemplo: en una cola de trabajos)."
    
    Flow:
    1. DB Trigger (trigger_enqueue_application_processing) creates pending_job when application is INSERTED
    2. This worker consumes from pending_jobs table (visible in DB)
    3. Enqueues to ARQ (Redis) for actual processing
    4. Updates pending_job status to 'enqueued'
    
    This makes the "DB Trigger -> Job Queue" flow visible and demonstrable.
    
    Args:
        ctx: ARQ worker context
        
    Returns:
        dict: Summary of processed jobs
    """
    set_request_id("consume-pending-jobs")
    
    logger.info("Starting consumption of pending jobs from database (DB Trigger -> Queue flow)")
    
    redis = ctx['redis']
    
    try:
        async with AsyncSessionLocal() as db:
            pending_jobs = await _fetch_pending_jobs(db)
            
            if not pending_jobs:
                logger.debug("No pending jobs found in database")
                return {
                    'status': 'completed',
                    'jobs_processed': 0,
                    'jobs_enqueued': 0,
                    'jobs_failed': 0
                }
            
            logger.info(
                f"Found {len(pending_jobs)} pending jobs to process",
                extra={'pending_count': len(pending_jobs)}
            )
            
            enqueued_count = 0
            failed_count = 0
            
            for pending_job in pending_jobs:
                try:
                    arq_job, application_id = await _enqueue_job_to_arq(redis, pending_job)
                    await _handle_job_success(db, pending_job, arq_job, application_id)
                    enqueued_count += 1
                    
                except Exception as e:
                    await db.rollback()
                    failed_count += 1
                    await _handle_job_failure(db, pending_job, e)
            
            return {
                'status': 'completed',
                'jobs_processed': len(pending_jobs),
                'jobs_enqueued': enqueued_count,
                'jobs_failed': failed_count
            }
            
    except Exception as e:
        logger.error(
            "Unexpected error consuming pending jobs",
            extra={
                'error': str(e),
                'error_type': type(e).__name__
            },
            exc_info=True
        )
        raise

