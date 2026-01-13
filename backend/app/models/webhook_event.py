"""WebhookEvent Model.

Tracks webhook events for idempotency and audit trail.
Prevents duplicate webhook processing by storing idempotency keys.
"""

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from ..db.database import Base


class WebhookEventStatus(str, enum.Enum):
    """Status of webhook event processing."""
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class WebhookEvent(Base):
    """Model for tracking webhook events for idempotency.

    This table stores all incoming webhook events with their idempotency key
    to prevent duplicate processing. Each webhook from external banking systems
    should have a unique provider_reference which serves as the idempotency key.

    Attributes:
        id: Unique identifier for the webhook event
        idempotency_key: Unique key from provider (e.g., provider_reference)
        application_id: Reference to the application being updated
        payload: Complete webhook payload for audit trail
        status: Current processing status (processing, processed, failed)
        error_message: Error details if processing failed
        processed_at: Timestamp when processing completed successfully
        created_at: When the webhook was first received
        updated_at: Last update timestamp
    """
    __tablename__ = "webhook_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    idempotency_key = Column(String(255), nullable=False, unique=True, index=True)
    application_id = Column(
        UUID(as_uuid=True),
        ForeignKey('applications.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    payload = Column(JSONB, nullable=False)
    status = Column(
        String(20),
        nullable=False,
        default=WebhookEventStatus.PROCESSING.value,
        index=True
    )
    error_message = Column(Text, nullable=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        index=True
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=lambda: datetime.now(UTC)
    )
    application = relationship("Application", back_populates="webhook_events")

    def __repr__(self):
        return f"<WebhookEvent(id={self.id}, idempotency_key={self.idempotency_key}, status={self.status})>"

    def is_already_processed(self) -> bool:
        """Check if this webhook event was already successfully processed."""
        return self.status == WebhookEventStatus.PROCESSED

    def mark_as_processed(self):
        """Mark webhook event as successfully processed."""
        self.status = WebhookEventStatus.PROCESSED
        self.processed_at = datetime.now(UTC)

    def mark_as_failed(self, error_message: str):
        """Mark webhook event as failed with error message."""
        self.status = WebhookEventStatus.FAILED
        self.error_message = error_message
