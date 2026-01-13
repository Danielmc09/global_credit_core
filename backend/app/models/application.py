"""SQLAlchemy Models for Credit Applications.

These models mirror the database schema created in init.sql
"""

import enum
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, Index, Numeric, String, text
from sqlalchemy.dialects.postgresql import (
    BYTEA,
    ENUM as PostgresEnum,
    JSONB,
    UUID as PGUUID,
)
from sqlalchemy.orm import relationship

from ..core.constants import (
    ApplicationStatus as AppStatusConstants,
    CountryCode as CountryCodeConstants,
    DatabaseLimits,
    SystemValues,
)
from ..db.database import Base


class CountryCode(str, enum.Enum):
    """Supported country codes."""
    ES = CountryCodeConstants.SPAIN
    PT = CountryCodeConstants.PORTUGAL
    IT = CountryCodeConstants.ITALY
    MX = CountryCodeConstants.MEXICO
    CO = CountryCodeConstants.COLOMBIA
    BR = CountryCodeConstants.BRAZIL


class ApplicationStatus(str, enum.Enum):
    """Application status enum."""
    PENDING = AppStatusConstants.PENDING
    VALIDATING = AppStatusConstants.VALIDATING
    APPROVED = AppStatusConstants.APPROVED
    REJECTED = AppStatusConstants.REJECTED
    UNDER_REVIEW = AppStatusConstants.UNDER_REVIEW
    COMPLETED = AppStatusConstants.COMPLETED
    CANCELLED = AppStatusConstants.CANCELLED


class Application(Base):
    """Credit application model."""

    __tablename__ = "applications"

    __table_args__ = (
        Index(
            'unique_document_per_country',
            'country',
            'identity_document',
            unique=True,
            postgresql_where=text("status NOT IN ('CANCELLED', 'REJECTED', 'COMPLETED') AND deleted_at IS NULL")
        ),
        Index(
            'unique_idempotency_key',
            'idempotency_key',
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL")
        ),
        Index('idx_applications_country_status', 'country', 'status'),
        Index('idx_applications_created_at', 'created_at'),
        Index('idx_applications_deleted_at', 'deleted_at'),
    )

    id = Column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("uuid_generate_v4()")
    )
    country = Column(
        PostgresEnum(
            CountryCode,
            name='country_code',
            create_type=True
        ),
        nullable=False
    )
    full_name = Column(BYTEA, nullable=False, comment="Encrypted full name using pgcrypto")
    identity_document = Column(BYTEA, nullable=False, comment="Encrypted identity document using pgcrypto")
    requested_amount = Column(
        Numeric(DatabaseLimits.AMOUNT_PRECISION, DatabaseLimits.AMOUNT_SCALE),
        nullable=False
    )
    monthly_income = Column(
        Numeric(DatabaseLimits.AMOUNT_PRECISION, DatabaseLimits.AMOUNT_SCALE),
        nullable=False
    )
    currency = Column(
        String(3),
        nullable=False
    )
    idempotency_key = Column(
        String(255),
        nullable=True,
        unique=True
    )
    status = Column(
        PostgresEnum(
            ApplicationStatus,
            name='application_status',
            create_type=True
        ),
        nullable=False,
        default=ApplicationStatus.PENDING
    )
    country_specific_data = Column(JSONB, default={})
    banking_data = Column(JSONB, default={})
    validation_errors = Column(JSONB, default=[])
    risk_score = Column(
        Numeric(DatabaseLimits.RISK_SCORE_PRECISION, DatabaseLimits.RISK_SCORE_SCALE),
        nullable=True
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=lambda: datetime.now(UTC)
    )
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    webhook_events = relationship("WebhookEvent", back_populates="application", cascade="all, delete-orphan")
    pending_jobs = relationship("PendingJob", back_populates="application", cascade="all, delete-orphan")

    def __repr__(self):
        return (
            f"<Application(id={self.id}, country={self.country}, "
            f"currency={self.currency}, status={self.status}, amount={self.requested_amount})>"
        )


class AuditLog(Base):
    """Audit log model for tracking status changes."""

    __tablename__ = "audit_logs"

    id = Column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("uuid_generate_v4()")
    )
    application_id = Column(
        PGUUID(as_uuid=True),
        nullable=False
    )
    old_status = Column(
        PostgresEnum(
            ApplicationStatus,
            name='application_status',
            create_type=True
        ),
        nullable=True
    )
    new_status = Column(
        PostgresEnum(
            ApplicationStatus,
            name='application_status',
            create_type=True
        ),
        nullable=False
    )
    changed_by = Column(String(DatabaseLimits.CHANGED_BY_MAX_LENGTH), default=SystemValues.DEFAULT_CHANGED_BY)
    change_reason = Column(String(DatabaseLimits.CHANGE_REASON_MAX_LENGTH), nullable=True)
    change_metadata = Column(JSONB, name='metadata', default={})
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP")
    )

    def __repr__(self):
        return (
            f"<AuditLog(id={self.id}, application={self.application_id}, "
            f"{self.old_status} -> {self.new_status})>"
        )
