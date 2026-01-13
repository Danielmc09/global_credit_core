"""Failed Job Model for Dead Letter Queue.

Stores jobs that have failed after maximum retries for manual review and reprocessing.
"""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID

from ..db.database import Base


class FailedJob(Base):
    """Model for storing failed jobs in Dead Letter Queue."""

    __tablename__ = "failed_jobs"

    id = Column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("uuid_generate_v4()")
    )
    job_id = Column(String(255), nullable=False, unique=True, comment="ARQ job ID")
    task_name = Column(String(255), nullable=False, comment="Task function name")
    job_args = Column(JSONB, default={}, comment="Job arguments")
    job_kwargs = Column(JSONB, default={}, comment="Job keyword arguments")
    error_type = Column(String(255), nullable=False, comment="Exception type name")
    error_message = Column(Text, nullable=False, comment="Exception message")
    error_traceback = Column(Text, nullable=True, comment="Full traceback")
    retry_count = Column(String(10), nullable=False, comment="Number of retries attempted")
    max_retries = Column(String(10), nullable=False, comment="Maximum retries configured")
    status = Column(
        String(50),
        nullable=False,
        default="pending",
        comment="Status: pending, reviewed, reprocessed, ignored"
    )
    reviewed_by = Column(String(255), nullable=True, comment="User who reviewed the job")
    reviewed_at = Column(DateTime(timezone=True), nullable=True, comment="When job was reviewed")
    review_notes = Column(Text, nullable=True, comment="Review notes or resolution")
    reprocessed_at = Column(DateTime(timezone=True), nullable=True, comment="When job was reprocessed")
    reprocessed_job_id = Column(String(255), nullable=True, comment="New job ID if reprocessed")
    job_metadata = Column(JSONB, default={}, comment="Additional metadata (trace context, etc.)")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="When job first failed after max retries"
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=lambda: datetime.now(UTC),
        comment="Last update timestamp"
    )

    def __repr__(self):
        return (
            f"<FailedJob(id={self.id}, job_id={self.job_id}, "
            f"task_name={self.task_name}, status={self.status})>"
        )
