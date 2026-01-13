"""Pending Job Model for DB Trigger -> Queue Flow.

CRITICAL: This model makes the "DB Trigger -> Job Queue" flow visible (Requirement 3.7).
When a new application is INSERTED, a database trigger automatically creates a pending_job.
A worker then consumes from this table and enqueues to ARQ (Redis).
"""

import enum
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import relationship

from ..db.database import Base


class PendingJobStatus(str, enum.Enum):
    """Status of a pending job."""

    PENDING = "pending"  # Created by trigger, waiting to be processed
    ENQUEUED = "enqueued"  # Picked up by worker and enqueued to ARQ
    PROCESSING = "processing"  # Being processed by ARQ worker
    COMPLETED = "completed"  # Completed successfully
    FAILED = "failed"  # Failed (moved to failed_jobs)


class PendingJob(Base):
    """Model for pending jobs created by DB triggers.

    CRITICAL: This table makes the "DB Trigger -> Job Queue" flow visible.
    When a new application is INSERTED, trigger_enqueue_application_processing
    automatically creates a pending_job here. A worker then consumes from this
    table and enqueues to ARQ (Redis).

    This demonstrates Requirement 3.7: "una operación en la base de datos genere
    trabajo a ser procesado de forma asíncrona (por ejemplo: en una cola de trabajos)."
    """

    __tablename__ = "pending_jobs"

    id = Column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("uuid_generate_v4()"),
        comment="Pending job UUID"
    )
    application_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        comment="Application that triggered this job via DB trigger"
    )
    task_name = Column(
        String(255),
        nullable=False,
        default="process_credit_application",
        comment="Task name to execute"
    )
    job_args = Column(
        JSONB,
        default={},
        comment="Job arguments (application_id, country, etc.)"
    )
    job_kwargs = Column(
        JSONB,
        default={},
        comment="Job keyword arguments"
    )
    status = Column(
        String(50),
        nullable=False,
        default=PendingJobStatus.PENDING.value,
        comment="Job status: pending, enqueued, processing, completed, failed"
    )
    arq_job_id = Column(
        String(255),
        nullable=True,
        comment="ARQ job ID after enqueuing to Redis"
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="When job was created by DB trigger"
    )
    enqueued_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When job was enqueued to ARQ"
    )
    processed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When job processing completed"
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=lambda: datetime.now(UTC),
        comment="Last update timestamp"
    )
    error_message = Column(
        Text,
        nullable=True,
        comment="Error message if job failed"
    )
    retry_count = Column(
        Integer,
        default=0,
        comment="Number of retry attempts"
    )

    # Relationship to application
    application = relationship("Application", back_populates="pending_jobs")

    def __repr__(self):
        return (
            f"<PendingJob(id={self.id}, application_id={self.application_id}, "
            f"status={self.status}, arq_job_id={self.arq_job_id})>"
        )
