from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..core.constants import Pagination
from ..models.application import Application, ApplicationStatus, AuditLog
from ..models.pending_job import PendingJob
from ..repositories.application_repository import ApplicationRepository


class ApplicationQueryService:
    """Query service for read-only application operations (CQRS pattern)."""

    def __init__(
        self,
        db: AsyncSession,
        repository: ApplicationRepository | None = None
    ):
        self.db = db
        self.repository = repository or ApplicationRepository(db)


    async def get_application(self, application_id: UUID) -> Application | None:
        """Get an application by ID.

        Args:
            application_id: Application UUID

        Returns:
            Application if found, None otherwise
        """
        return await self.repository.find_by_id(application_id, decrypt=True)


    async def list_applications(
        self,
        country: str | None = None,
        status: ApplicationStatus | None = None,
        page: int = Pagination.DEFAULT_PAGE,
        page_size: int = Pagination.DEFAULT_PAGE_SIZE
    ) -> tuple[list[Application], int]:
        """List applications with optional filtering and pagination.

        Args:
            country: Filter by country code
            status: Filter by status
            page: Page number (1-indexed)
            page_size: Number of items per page

        Returns:
            Tuple of (list of applications, total count)
        """
        return await self.repository.list(
            country=country,
            status=status,
            page=page,
            page_size=page_size
        )


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
        return await self.repository.get_audit_logs(
            application_id,
            page,
            page_size
        )


    async def get_pending_jobs(self, application_id: UUID) -> list[PendingJob]:
        """Get pending jobs for an application.

        Args:
            application_id: Application UUID

        Returns:
            List of pending jobs
        """

        query = select(PendingJob).where(
            PendingJob.application_id == application_id
        ).order_by(PendingJob.created_at.desc())

        result = await self.db.execute(query)
        return list(result.scalars().all())


    async def get_statistics_by_country(self, country: str) -> dict[str, Any]:
        """Get application statistics for a country.

        Args:
            country: Country code

        Returns:
            Dictionary with statistics
        """
        return await self.repository.get_statistics_by_country(country)
