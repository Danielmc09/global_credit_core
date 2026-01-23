from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.logging import get_logger
from ..domain.state_machine import validate_transition
from ..domain.validators import check_duplicate_by_document
from ..domain.factories import ApplicationFactory
from ..domain.validators import validate_and_normalize_currency
from ..models.application import Application
from ..repositories.application_repository import ApplicationRepository
from ..schemas.application import ApplicationCreate, ApplicationUpdate
from ..strategies.factory import get_country_strategy
from ..utils import validate_banking_data_precision, validate_risk_score_precision
from ..utils.transaction_helpers import safe_transaction
from ..infrastructure.monitoring import inject_trace_context

logger = get_logger(__name__)


class ApplicationCommandService:
    """Command service for write operations on applications (CQRS pattern)."""

    def __init__(
        self,
        db: AsyncSession,
        repository: ApplicationRepository | None = None,
        factory: ApplicationFactory | None = None,
        redis=None,
        cache_service=None
    ):
        self.db = db
        self.repository = repository or ApplicationRepository(db)
        self.factory = factory or ApplicationFactory(db)
        self.redis = redis
        self.cache_service = cache_service


    async def create_application(
        self,
        application_data: ApplicationCreate
    ) -> Application:
        """Create a new credit application.

        This method orchestrates the application creation process following
        the "Fail Fast, Fail Cheap" principle:
        
        1. Fast validations (no DB, <5ms):
           - Validates country exists
           - Validates currency matches country
           - Validates identity document format
           - Validates amount ranges
        
        2. DB validations (10-50ms):
           - Checks for idempotency
           - Checks for duplicate applications
        
        3. Creation (10-100ms):
           - Creates the application in PENDING status

        The actual credit evaluation happens asynchronously in a worker.

        Args:
            application_data: Application creation data

        Returns:
            Created application with decrypted PII fields

        Raises:
            ValueError: If validation fails (invalid country, currency mismatch, 
                       invalid document format, duplicates, etc.)
        """
        logger.info(
            "Creating application",
            extra={
                'country': application_data.country,
                'amount': str(application_data.requested_amount)
            }
        )

        strategy = get_country_strategy(application_data.country)

        currency = validate_and_normalize_currency(
            application_data.country,
            application_data.currency,
            strategy.country_name
        )

        validation_result = strategy.validate_identity_document(
            application_data.identity_document
        )
        
        if not validation_result.is_valid:
            logger.warning(
                "Document validation failed",
                extra={
                    'errors': validation_result.errors,
                    'country': application_data.country
                }
            )
            raise ValueError(
                f"Invalid identity document: {', '.join(validation_result.errors)}"
            )

        if application_data.requested_amount <= 0:
            raise ValueError("Requested amount must be positive")
        
        if application_data.monthly_income < 0:
            raise ValueError("Monthly income cannot be negative")

        existing_app = await self.factory.find_by_idempotency_key_decrypted(
            application_data.idempotency_key
        )
        if existing_app:
            return existing_app

        await check_duplicate_by_document(  
            self.db, 
            application_data.identity_document, 
            application_data.country
        )

        application = await self.factory.create_from_request(
            application_data,
            currency,
            validation_result
        )

        return application


    async def update_application(
        self,
        application_id: UUID,
        update_data: ApplicationUpdate
    ) -> Application:
        """Update an existing application.

        Args:
            application_id: Application UUID
            update_data: Application update data

        Returns:
            Updated application

        Raises:
            ValueError: If application not found or update is invalid
        """
        application = await self.repository.find_by_id(
            application_id,
            decrypt=False
        )

        if not application:
            raise ValueError(f"Application {application_id} not found")

        if application.deleted_at:
            raise ValueError(f"Cannot update deleted application {application_id}")

        if update_data.status:
            validate_transition(application.status, update_data.status)
            application.status = update_data.status

        if update_data.risk_score is not None:
            application.risk_score = validate_risk_score_precision(update_data.risk_score)

        if update_data.banking_data:
            application.banking_data = {
                **application.banking_data,
                **{
                    k: validate_banking_data_precision(v) if isinstance(v, (int, float)) else v
                    for k, v in update_data.banking_data.items()
                }
            }

        if update_data.rejection_reason:
            application.rejection_reason = update_data.rejection_reason

        if update_data.validation_errors is not None:
            application.validation_errors = update_data.validation_errors

        logger.info(
            "Application updated",
            extra={
                'application_id': str(application_id),
                'status': application.status,
                'risk_score': str(application.risk_score) if application.risk_score else None
            }
        )

        return await self.repository.update(application)


    async def delete_application(self, application_id: UUID) -> bool:
        """Soft delete an application.

        Args:
            application_id: Application UUID

        Returns:
            True if deleted, False if not found

        Raises:
            ValueError: If application is already deleted
        """
        application = await self.repository.find_by_id(
            application_id,
            include_deleted=False
        )

        if not application:
            return False

        if application.deleted_at:
            raise ValueError(f"Application {application_id} is already deleted")

        logger.info(
            "Soft deleting application",
            extra={'application_id': str(application_id)}
        )

        await self.repository.soft_delete(application)
        return True


    async def _update_pending_job_with_arq_id(self, app: Application, arq_job_id: str) -> None:
        """Update pending_job with ARQ job ID after successful enqueue.
        
        Args:
            app: Application that was enqueued
            arq_job_id: ARQ job ID returned from Redis
        """
        from datetime import UTC, datetime
        from sqlalchemy import select, update
        from ..models.pending_job import PendingJob
        
        try:
            # Update the pending_job with arq_job_id
            stmt = (
                update(PendingJob)
                .where(PendingJob.application_id == app.id)
                .where(PendingJob.arq_job_id.is_(None))  # Only update if not yet set
                .values(
                    arq_job_id=arq_job_id,
                    enqueued_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC)
                )
            )
            await self.db.execute(stmt)
            await self.db.commit()
            
            logger.debug(
                "Updated pending_job with arq_job_id",
                extra={
                    'application_id': str(app.id),
                    'arq_job_id': arq_job_id
                }
            )
        except Exception as e:
            logger.warning(
                "Failed to update pending_job with arq_job_id",
                extra={
                    'application_id': str(app.id),
                    'arq_job_id': arq_job_id,
                    'error': str(e)
                }
            )

    async def _enqueue_realtime(self, app: Application) -> str | None:
        """Enqueue application to Redis for immediate processing.
        
        This method attempts to enqueue the application immediately after creation.
        If Redis fails, it logs a warning and relies on the fallback cron job.
        
        Args:
            app: Application to enqueue
            
        Returns:
            ARQ job ID if successful, None otherwise
        """
        trace_context = {}

        inject_trace_context(trace_context)
        
        try:
            job = await self.redis.enqueue_job(
                'process_credit_application',
                str(app.id),
                trace_context if trace_context else None,
                _job_id=f"rt_{app.id}",
            )
            arq_job_id = job.job_id if job else None
            
            logger.info(
                "Real-time job enqueued successfully",
                extra={
                    'application_id': str(app.id),
                    'arq_job_id': arq_job_id,
                    'enqueue_method': 'realtime'
                }
            )
            return arq_job_id
        except Exception as e:
            logger.warning(
                "Real-time enqueue failed, relying on fallback cron",
                extra={
                    'application_id': str(app.id),
                    'error': str(e),
                    'fallback': 'cron_consumer'
                }
            )
            return None


    async def _invalidate_cache(self, application_id: UUID) -> None:
        """Invalidate cache for the application.
        
        Args:
            application_id: Application UUID
        """
        try:
            await self.cache_service.invalidate_application(str(application_id))
            logger.debug(
                "Cache invalidated successfully",
                extra={'application_id': str(application_id)}
            )
        except Exception as e:
            logger.warning(
                "Failed to invalidate cache after application creation",
                extra={
                    'application_id': str(application_id),
                    'error': str(e)
                }
            )


    async def create_and_enqueue(
        self,
        application_data: ApplicationCreate
    ) -> Application:
        """Create application and enqueue it immediately for processing.
        
        This method orchestrates the complete application creation flow:
        1. Creates the application in a transaction
        2. Refreshes to get DB-generated values (id, timestamps, triggers)
        3. Enqueues immediately to Redis (outside transaction)
        4. Invalidates cache
        
        For high-concurrency scenarios (1M+ requests), this approach:
        - Keeps DB transactions short (commit before Redis enqueue)
        - Enqueues immediately (no 60-second wait)
        - Has fallback to cron if Redis fails
        
        Args:
            application_data: Application creation data
            
        Returns:
            Created application with all DB-generated values
            
        Raises:
            ValueError: If validation fails
        """
        
        async with safe_transaction(self.db):
            app = await self.create_application(application_data)
            await self.db.refresh(app)
        
        # Debug logging to track ARQ pool availability
        logger.info(
            "Attempting real-time enqueue",
            extra={
                'application_id': str(app.id),
                'arq_pool_available': self.redis is not None,
                'arq_pool_type': type(self.redis).__name__ if self.redis else None
            }
        )
        
        if self.redis:
            arq_job_id = await self._enqueue_realtime(app)
            if arq_job_id:
                # Save the arq_job_id to the pending_jobs table
                await self._update_pending_job_with_arq_id(app, arq_job_id)
        else:
            logger.warning(
                "ARQ pool not available, application will be picked up by cron consumer",
                extra={
                    'application_id': str(app.id),
                    'fallback': 'cron_consumer',
                    'delay_expected': '~60 seconds'
                }
            )
        
        if self.cache_service:
            await self._invalidate_cache(app.id)
        
        return app
