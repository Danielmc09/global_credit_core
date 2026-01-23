from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.application import Application, ApplicationStatus, AuditLog
from ..models.pending_job import PendingJob
from ..schemas.application import ApplicationCreate, ApplicationUpdate
from .application_command_service import ApplicationCommandService
from .application_query_service import ApplicationQueryService


class ApplicationService:
    """Facade service for managing credit applications.
    
    This service delegates to specialized Query and Command services (CQRS pattern)
    while maintaining backward compatibility with existing code.
    
    Benefits:
    - Separation of Concerns: Queries vs Commands
    - Easier to test (mock query/command services separately)
    - Better scalability (can optimize read/write paths independently)
    - Cleaner code organization
    """

    def __init__(
        self,
        db: AsyncSession,
        query_service: ApplicationQueryService | None = None,
        command_service: ApplicationCommandService | None = None,
        redis=None,
        cache_service=None
    ):
        """Initialize the facade service.
        
        Args:
            db: Database session
            query_service: Optional query service (for DI/testing)
            command_service: Optional command service (for DI/testing)
            redis: Optional Redis connection for real-time enqueuing
            cache_service: Optional cache service for cache invalidation
        """
        self.db = db
        self.redis = redis
        self.cache_service = cache_service
        self.query_service = query_service or ApplicationQueryService(db)
        self.command_service = command_service or ApplicationCommandService(
            db,
            redis=redis,
            cache_service=cache_service
        )


    async def create_application(
        self,
        application_data: ApplicationCreate
    ) -> Application:
        """Create a new credit application."""
        return await self.command_service.create_application(application_data)


    async def update_application(
        self,
        application_id: UUID,
        update_data: ApplicationUpdate
    ) -> Application:
        """Update an existing application."""
        return await self.command_service.update_application(application_id, update_data)


    async def delete_application(self, application_id: UUID) -> bool:
        """Soft delete an application."""
        return await self.command_service.delete_application(application_id)


    async def get_application(self, application_id: UUID) -> Application | None:
        """Get an application by ID."""
        return await self.query_service.get_application(application_id)


    async def list_applications(
        self,
        country: str | None = None,
        status: ApplicationStatus | None = None,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[list[Application], int]:
        """List applications with optional filtering and pagination."""
        return await self.query_service.list_applications(country, status, page, page_size)


    async def get_audit_logs(
        self,
        application_id: UUID,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[list[AuditLog], int]:
        """Get audit logs for an application."""
        return await self.query_service.get_audit_logs(application_id, page, page_size)


    async def get_pending_jobs(self, application_id: UUID) -> list[PendingJob]:
        """Get pending jobs for an application."""
        return await self.query_service.get_pending_jobs(application_id)


    async def get_statistics_by_country(self, country: str) -> dict[str, Any]:
        """Get application statistics for a country."""
        return await self.query_service.get_statistics_by_country(country)


    async def create_and_enqueue(
        self,
        application_data: ApplicationCreate
    ) -> Application:
        """Create application and enqueue it immediately for processing.
        
        This method orchestrates the complete application creation flow with
        real-time enqueuing to Redis and cache invalidation.
        
        Args:
            application_data: Application creation data
            
        Returns:
            Created application with all DB-generated values
            
        Raises:
            ValueError: If validation fails
        """
        return await self.command_service.create_and_enqueue(application_data)
