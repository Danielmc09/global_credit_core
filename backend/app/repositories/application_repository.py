"""Application Repository.

Data access layer for Application entities.
Separates data access logic from business logic (Repository Pattern).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.constants import Pagination
from ..infrastructure.security import decrypt_value
from ..models.application import Application, ApplicationStatus, AuditLog


class ApplicationRepository:
    """Repository for Application data access operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_by_id(
        self, 
        application_id: UUID | str, 
        include_deleted: bool = False,
        decrypt: bool = False
    ) -> Application | None:
        """Find application by ID.

        Args:
            application_id: Application UUID
            include_deleted: If True, include soft-deleted applications
            decrypt: If True, decrypt PII fields before returning.
                    WARNING: Do not use decrypt=True if you plan to update the application,
                    as decrypted strings cannot be saved to BYTEA columns.

        Returns:
            Application if found, None otherwise
        """
        application_id_str = str(application_id) if isinstance(application_id, UUID) else application_id

        query = select(Application).where(Application.id == application_id_str)

        if not include_deleted:
            query = query.where(Application.deleted_at.is_(None))

        result = await self.db.execute(query)
        application = result.scalar_one_or_none()

        # Decrypt PII fields only if explicitly requested
        # NOTE: Do NOT decrypt if the application will be updated, as SQLAlchemy
        # will try to save strings to BYTEA columns, causing errors
        if application and decrypt:
            if application.identity_document:
                application.identity_document = await decrypt_value(self.db, application.identity_document)
            if application.full_name:
                application.full_name = await decrypt_value(self.db, application.full_name)

        return application


    async def find_by_idempotency_key(
        self,
        idempotency_key: str,
        include_deleted: bool = False,
        for_update: bool = False
    ) -> Application | None:
        """Find application by idempotency key.

        Args:
            idempotency_key: Idempotency key
            include_deleted: If True, include soft-deleted applications
            for_update: If True, use SELECT FOR UPDATE

        Returns:
            Application if found, None otherwise
        """
        query = select(Application).where(
            and_(
                Application.idempotency_key == idempotency_key,
                Application.deleted_at.is_(None) if not include_deleted else True
            )
        )

        if for_update:
            query = query.with_for_update()

        result = await self.db.execute(query)
        return result.scalar_one_or_none()


    async def find_active_by_document_and_country(
        self,
        country: str,
        encrypted_document: bytes,
        active_statuses: list[ApplicationStatus],
        for_update: bool = False
    ) -> Application | None:
        """Find active application by document and country.

        Args:
            country: Country code
            encrypted_document: Encrypted identity document
            active_statuses: List of active statuses to filter
            for_update: If True, use SELECT FOR UPDATE

        Returns:
            Application if found, None otherwise
        """
        query = select(Application).where(
            and_(
                Application.country == country,
                Application.identity_document == encrypted_document,
                Application.deleted_at.is_(None),
                Application.status.in_(active_statuses)
            )
        )

        if for_update:
            query = query.with_for_update()

        result = await self.db.execute(query)
        return result.scalar_one_or_none()


    async def create(self, application: Application) -> Application:
        """Create a new application.

        Args:
            application: Application entity to create

        Returns:
            Created application
        """
        self.db.add(application)
        await self.db.flush()
        return application


    async def update(self, application: Application) -> Application:
        """Update an existing application.

        Args:
            application: Application entity to update

        Returns:
            Updated application
        """
        await self.db.flush()
        await self.db.refresh(application)
        return application


    async def soft_delete(self, application: Application) -> None:
        """Soft delete an application.

        Args:
            application: Application entity to soft delete
        """
        from datetime import UTC, datetime
        application.deleted_at = datetime.now(UTC)
        await self.db.flush()


    async def list(
        self,
        country: str | None = None,
        status: ApplicationStatus | None = None,
        page: int = Pagination.DEFAULT_PAGE,
        page_size: int = Pagination.DEFAULT_PAGE_SIZE,
        include_deleted: bool = False
    ) -> tuple[list[Application], int]:
        """List applications with optional filtering and pagination.

        Args:
            country: Filter by country code
            status: Filter by status
            page: Page number (1-indexed)
            page_size: Number of items per page
            include_deleted: If True, include soft-deleted applications

        Returns:
            Tuple of (list of applications, total count)
        """
        # Build query
        query = select(Application)

        if not include_deleted:
            query = query.where(Application.deleted_at.is_(None))

        if country:
            query = query.where(Application.country == country)

        if status:
            query = query.where(Application.status == status)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Add pagination
        offset = (page - 1) * page_size
        query = query.order_by(Application.created_at.desc()).offset(offset).limit(page_size)

        # Execute query
        result = await self.db.execute(query)
        applications = result.scalars().all()

        # Decrypt PII fields for all applications
        for app in applications:
            if app.identity_document:
                app.identity_document = await decrypt_value(self.db, app.identity_document)
            if app.full_name:
                app.full_name = await decrypt_value(self.db, app.full_name)

        return list(applications), total


    async def get_statistics_by_country(self, country: str) -> dict[str, Any]:
        """Get application statistics for a country.

        Args:
            country: Country code

        Returns:
            Dictionary with statistics
        """
        result = await self.db.execute(
            select(
                func.count(Application.id).label('total'),
                func.sum(Application.requested_amount).label('total_amount'),
                func.avg(Application.requested_amount).label('avg_amount'),
                func.count(Application.id).filter(
                    Application.status == ApplicationStatus.PENDING
                ).label('pending'),
                func.count(Application.id).filter(
                    Application.status == ApplicationStatus.APPROVED
                ).label('approved'),
                func.count(Application.id).filter(
                    Application.status == ApplicationStatus.REJECTED
                ).label('rejected')
            ).where(
                and_(
                    Application.country == country,
                    Application.deleted_at.is_(None)
                )
            )
        )

        row = result.first()

        return {
            'country': country,
            'total_applications': row.total or 0,
            'total_amount': str(row.total_amount or 0),   # Decimal preserved as string
            'average_amount': str(row.avg_amount or 0),   # Decimal preserved as string
            'pending_count': row.pending or 0,
            'approved_count': row.approved or 0,
            'rejected_count': row.rejected or 0
        }


    async def get_audit_logs(
        self,
        application_id: UUID,
        page: int = Pagination.DEFAULT_PAGE,
        page_size: int = Pagination.DEFAULT_PAGE_SIZE
    ) -> tuple[list[AuditLog], int]:
        """Get audit logs for an application with pagination.

        Args:
            application_id: Application UUID
            page: Page number (1-indexed)
            page_size: Number of items per page

        Returns:
            Tuple of (list of audit logs, total count)
        """
        # Build query
        query = select(AuditLog).where(AuditLog.application_id == application_id)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Add pagination
        offset = (page - 1) * page_size
        query = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(page_size)

        # Execute query
        result = await self.db.execute(query)
        audit_logs = result.scalars().all()

        return list(audit_logs), total
