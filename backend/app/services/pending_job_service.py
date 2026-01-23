from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.logging import get_logger
from ..models.pending_job import PendingJob, PendingJobStatus

logger = get_logger(__name__)


class PendingJobService:
    """Service for managing pending job status updates."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_by_arq_job_id(self, arq_job_id: str) -> PendingJob | None:
        """Find pending job by ARQ job ID.
        
        Args:
            arq_job_id: ARQ job ID (format: rt_{application_id})
            
        Returns:
            PendingJob if found, None otherwise
        """
        stmt = select(PendingJob).where(PendingJob.arq_job_id == arq_job_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_as_completed(self, arq_job_id: str) -> bool:
        """Mark a pending job as completed.
        
        Args:
            arq_job_id: ARQ job ID (format: rt_{application_id})
            
        Returns:
            True if updated, False if not found
        """
        stmt = (
            update(PendingJob)
            .where(PendingJob.arq_job_id == arq_job_id)
            .where(PendingJob.status == PendingJobStatus.ENQUEUED.value)
            .values(
                status=PendingJobStatus.COMPLETED.value,
                processed_at=datetime.now(UTC),
                updated_at=datetime.now(UTC)
            )
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        
        updated = result.rowcount > 0
        
        if updated:
            logger.info(
                "Pending job marked as completed",
                extra={'arq_job_id': arq_job_id}
            )
        else:
            logger.warning(
                "Pending job not found or already processed",
                extra={'arq_job_id': arq_job_id}
            )
        
        return updated

    async def mark_as_failed(self, arq_job_id: str, error_message: str | None = None) -> bool:
        """Mark a pending job as failed.
        
        Args:
            arq_job_id: ARQ job ID (format: rt_{application_id})
            error_message: Optional error message
            
        Returns:
            True if updated, False if not found
        """
        values = {
            'status': PendingJobStatus.FAILED.value,
            'processed_at': datetime.now(UTC),
            'updated_at': datetime.now(UTC)
        }
        
        if error_message:
            values['error_message'] = error_message
        
        stmt = (
            update(PendingJob)
            .where(PendingJob.arq_job_id == arq_job_id)
            .where(PendingJob.status == PendingJobStatus.ENQUEUED.value)
            .values(**values)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        
        updated = result.rowcount > 0
        
        if updated:
            logger.info(
                "Pending job marked as failed",
                extra={'arq_job_id': arq_job_id, 'error': error_message}
            )
        else:
            logger.warning(
                "Pending job not found or already processed",
                extra={'arq_job_id': arq_job_id}
            )
        
        return updated
