"""Asynchronous Tasks.

Background tasks processed by ARQ workers.
These handle credit evaluation, risk assessment, and external integrations.
"""

import asyncio
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID

import redis.asyncio as aioredis
from arq import create_pool
from arq.connections import RedisSettings
from redis.asyncio.lock import Lock
from sqlalchemy import delete, select
from sqlalchemy.exc import DatabaseError, OperationalError, TimeoutError as SQLTimeoutError

try:
    from opentelemetry import context as otel_context
except ImportError:
    otel_context = None

from ..core.config import settings
from ..core.constants import (
    ApprovalRecommendation,
    ErrorMessages,
    Security,
    Timeout,
    WebhookEventsTTL,
)
from ..core.encryption import decrypt_value
from ..core.exceptions import (
    ApplicationNotFoundError,
    DatabaseConnectionError,
    ExternalServiceError,
    InvalidApplicationIdError,
    NetworkTimeoutError,
    PermanentError,
    RecoverableError,
    StateTransitionError,
    ValidationError,
)
from ..core.logging import get_logger, set_request_id
from ..core.metrics import (
    worker_task_duration_seconds,
    worker_tasks_in_progress,
    worker_tasks_total,
)
from ..core.state_machine import validate_transition

try:
    from ..core.tracing import (
        extract_trace_context,
        get_tracer,
        inject_trace_context,
    )
except ImportError:

    def get_tracer(name: str):
        """No-op tracer when tracing is not available."""
        class NoOpTracer:
            def start_as_current_span(self, *args, **kwargs):
                from contextlib import nullcontext
                return nullcontext()
        return NoOpTracer()

    def extract_trace_context(carrier: dict):
        """No-op trace context extraction."""
        return None

    def inject_trace_context(carrier: dict):
        """No-op trace context injection."""
        pass

    if otel_context is None:
        class NullContext:
            def attach(self, context):
                from contextlib import nullcontext
                return nullcontext()
        otel_context = NullContext()

from ..db.database import AsyncSessionLocal
from ..models.application import Application, ApplicationStatus
from ..models.webhook_event import WebhookEvent
from ..services.partitioning_service import monitor_and_partition_tables
from ..services.websocket_service import broadcast_application_update
from ..strategies.factory import get_country_strategy
from ..utils import decimal_to_string, generate_request_id
from ..utils.helpers import (
    validate_banking_data_precision,
    validate_risk_score_precision,
)
from ..utils.transaction_helpers import safe_transaction

logger = get_logger(__name__)


@worker_tasks_in_progress.track_inprogress()
async def process_credit_application(ctx, application_id: str, trace_context: dict | None = None):
    """Main task: Process a credit application.

    This task:
    1. Fetches banking data from provider (mock)
    2. Applies country-specific business rules
    3. Updates application status and risk score
    4. Sends WebSocket notification (for real-time updates)

    Args:
        ctx: ARQ context
        application_id: UUID of the application to process
        trace_context: Optional trace context dictionary for distributed tracing

    Raises:
        PermanentError: For errors that won't resolve on retry (invalid data, not found, etc.)
        RecoverableError: For transient errors that may resolve on retry (network, DB connection)
        Exception: Any other unexpected error (will be retried by ARQ)
    """
    start_time = time.time()

    # Extract trace context if provided
    tracer = get_tracer(__name__)
    if trace_context:
        otel_context_obj = extract_trace_context(trace_context)
        if otel_context_obj:
            # Create span as child of propagated context
            with otel_context.attach(otel_context_obj):
                with tracer.start_as_current_span("process_credit_application") as span:
                    span.set_attribute("application.id", application_id)
                    return await _process_credit_application_impl(
                        ctx, application_id, start_time, tracer, span
                    )
    
    # No trace context, create new trace
    with tracer.start_as_current_span("process_credit_application") as span:
        span.set_attribute("application.id", application_id)
        return await _process_credit_application_impl(
            ctx, application_id, start_time, tracer, span
        )


async def _process_credit_application_impl(
    ctx, application_id: str, start_time: float, tracer, span
):
    """Internal implementation of credit application processing."""
    set_request_id(
        generate_request_id(Security.REQUEST_ID_PREFIX_WORKER)
    )

    logger.info(
        "Processing credit application",
        extra={'application_id': application_id}
    )

    redis_client = await aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=False
    )

    lock_key = f"process:{application_id}"
    lock_timeout = 300

    try:
        lock = Lock(redis_client, lock_key, timeout=lock_timeout, sleep=0.1)
        async with lock:
            logger.debug(
                "Acquired distributed lock for application processing",
                extra={'application_id': application_id, 'lock_key': lock_key}
            )

            async with AsyncSessionLocal() as db:
                try:
                    async with safe_transaction(db):
                        try:
                            uuid_obj = UUID(application_id)
                        except ValueError as e:
                            logger.error(
                                "Invalid UUID format",
                                extra={'application_id': application_id}
                            )
                            worker_tasks_total.labels(
                                task_name='process_credit_application',
                                status='failure'
                            ).inc()
                            duration = time.time() - start_time
                            worker_task_duration_seconds.labels(
                                task_name='process_credit_application'
                            ).observe(duration)
                            raise InvalidApplicationIdError(
                                f"Invalid UUID format: {application_id}"
                            ) from e

                        result = await db.execute(
                            select(Application).where(Application.id == uuid_obj)
                        )
                        application = result.scalar_one_or_none()

                        if not application:
                            logger.error(
                                "Application not found",
                                extra={'application_id': application_id}
                            )
                            worker_tasks_total.labels(
                                task_name='process_credit_application',
                                status='failure'
                            ).inc()
                            duration = time.time() - start_time
                            worker_task_duration_seconds.labels(
                                task_name='process_credit_application'
                            ).observe(duration)
                            raise ApplicationNotFoundError(
                                ErrorMessages.APPLICATION_NOT_FOUND.format(application_id=application_id)
                            )

                        if application.identity_document:
                            application.identity_document = await decrypt_value(db, application.identity_document)
                        if application.full_name:
                            application.full_name = await decrypt_value(db, application.full_name)

                        logger.debug("Validating application...")
                        await asyncio.sleep(Timeout.VALIDATION_STAGE_DELAY)

                        old_status = application.status
                        new_status = ApplicationStatus.VALIDATING
                        try:
                            validate_transition(old_status, new_status)
                        except ValueError as e:
                            raise StateTransitionError(str(e)) from e
                        application.status = new_status

                        await db.refresh(application)

                        try:
                            await broadcast_application_update(application)
                            logger.debug(
                                "Broadcasted VALIDATING status",
                                extra={'application_id': application_id}
                            )
                        except Exception as e:
                            logger.warning(
                                "Failed to broadcast VALIDATING status",
                                extra={'application_id': application_id, 'error': str(e)},
                                exc_info=True
                            )

                        try:
                            strategy = get_country_strategy(application.country)
                        except ValueError as e:
                            raise ValidationError(f"Unsupported country: {application.country}") from e

                        logger.info(
                            "Fetching banking data",
                            extra={
                                'application_id': application_id,
                                'country': application.country
                            }
                        )

                        with tracer.start_as_current_span("fetch_banking_data") as provider_span:
                            provider_span.set_attribute("provider.country", application.country)
                            provider_span.set_attribute("application.id", application_id)
                            
                            try:
                                banking_data = await strategy.get_banking_data(
                                    application.identity_document,
                                    application.full_name
                                )
                                provider_span.set_attribute("provider.success", True)
                            except (TimeoutError, asyncio.TimeoutError) as e:
                                provider_span.set_attribute("provider.success", False)
                                provider_span.record_exception(e)
                                raise NetworkTimeoutError(
                                    f"Timeout fetching banking data: {str(e)}"
                                ) from e
                            except Exception as e:
                                provider_span.set_attribute("provider.success", False)
                                provider_span.record_exception(e)
                                raise ExternalServiceError(
                                    f"Error fetching banking data: {str(e)}"
                                ) from e

                        await asyncio.sleep(Timeout.BANKING_DATA_DELAY)

                        logger.info(
                            "Applying business rules",
                            extra={'application_id': application_id}
                        )

                        with tracer.start_as_current_span("apply_business_rules") as rules_span:
                            rules_span.set_attribute("application.id", application_id)
                            rules_span.set_attribute("application.country", application.country)
                            rules_span.set_attribute("application.requested_amount", str(application.requested_amount))
                            
                            risk_assessment = strategy.apply_business_rules(
                                application.requested_amount,
                                application.monthly_income,
                                banking_data,
                                application.country_specific_data
                            )
                            
                            rules_span.set_attribute("risk.score", str(risk_assessment.risk_score))
                            rules_span.set_attribute("risk.level", risk_assessment.risk_level)
                            rules_span.set_attribute("approval.recommendation", risk_assessment.approval_recommendation)

                        await asyncio.sleep(Timeout.BUSINESS_RULES_DELAY)

                        banking_data_dict = banking_data.dict()
                        banking_data_dict = decimal_to_string(banking_data_dict)
                        banking_data_dict = validate_banking_data_precision(banking_data_dict)

                        application.banking_data = banking_data_dict
                        application.risk_score = validate_risk_score_precision(risk_assessment.risk_score)

                        if not application.country_specific_data:
                            application.country_specific_data = {}
                        application.country_specific_data['risk_level'] = risk_assessment.risk_level

                        old_status = application.status
                        if risk_assessment.approval_recommendation == ApprovalRecommendation.APPROVE:
                            new_status = ApplicationStatus.APPROVED
                        elif risk_assessment.approval_recommendation == ApprovalRecommendation.REJECT:
                            new_status = ApplicationStatus.REJECTED
                        elif risk_assessment.approval_recommendation == ApprovalRecommendation.REVIEW:
                            new_status = ApplicationStatus.UNDER_REVIEW
                        else:
                            new_status = ApplicationStatus.UNDER_REVIEW

                        try:
                            validate_transition(old_status, new_status)
                        except ValueError as e:
                            raise StateTransitionError(str(e)) from e
                        application.status = new_status

                        application.validation_errors = risk_assessment.reasons

                        await db.refresh(application)

                    logger.info(
                        "Application processing completed",
                        extra={
                            'application_id': application_id,
                            'final_status': application.status,
                            'risk_score': str(risk_assessment.risk_score)
                        }
                    )

                    try:
                        await broadcast_application_update(application)
                        # Extract status value safely for logging
                        status_value = application.status.value if hasattr(application.status, 'value') else str(application.status)
                        logger.debug(
                            "Broadcasted final status",
                            extra={
                                'application_id': application_id,
                                'status': status_value
                            }
                        )
                    except Exception as e:
                        logger.warning(
                            "Failed to broadcast final status",
                            extra={'application_id': application_id, 'error': str(e)},
                            exc_info=True
                        )

                    worker_tasks_total.labels(
                        task_name='process_credit_application',
                        status='success'
                    ).inc()
                    duration = time.time() - start_time
                    worker_task_duration_seconds.labels(
                        task_name='process_credit_application'
                    ).observe(duration)

                    return f"Application {application_id} processed: {application.status}"

                except (PermanentError, InvalidApplicationIdError, ApplicationNotFoundError,
                        ValidationError, StateTransitionError) as e:
                    error_type = type(e).__name__
                    error_message = str(e)

                    logger.error(
                        "Permanent error processing application (will not retry)",
                        extra={
                            'application_id': application_id,
                            'error': error_message,
                            'error_type': error_type,
                            'stage': 'processing',
                            'retryable': False
                        },
                        exc_info=True
                    )

                    worker_tasks_total.labels(
                        task_name='process_credit_application',
                        status='failure'
                    ).inc()
                    duration = time.time() - start_time
                    worker_task_duration_seconds.labels(
                        task_name='process_credit_application'
                    ).observe(duration)

                    raise

                except (RecoverableError, DatabaseConnectionError, ExternalServiceError,
                        NetworkTimeoutError) as e:
                    error_type = type(e).__name__
                    error_message = str(e)

                    logger.warning(
                        "Recoverable error processing application (will retry)",
                        extra={
                            'application_id': application_id,
                            'error': error_message,
                            'error_type': error_type,
                            'stage': 'processing',
                            'retryable': True
                        },
                        exc_info=True
                    )

                    worker_tasks_total.labels(
                        task_name='process_credit_application',
                        status='failure'
                    ).inc()
                    duration = time.time() - start_time
                    worker_task_duration_seconds.labels(
                        task_name='process_credit_application'
                    ).observe(duration)

                    raise

                except (OperationalError, DatabaseError, SQLTimeoutError) as e:
                    error_type = type(e).__name__
                    error_message = str(e)

                    logger.warning(
                        "Database error processing application (will retry)",
                        extra={
                            'application_id': application_id,
                            'error': error_message,
                            'error_type': error_type,
                            'stage': 'processing',
                            'retryable': True
                        },
                        exc_info=True
                    )

                    worker_tasks_total.labels(
                        task_name='process_credit_application',
                        status='failure'
                    ).inc()
                    duration = time.time() - start_time
                    worker_task_duration_seconds.labels(
                        task_name='process_credit_application'
                    ).observe(duration)

                    raise DatabaseConnectionError(
                        f"Database error: {error_message}"
                    ) from e

                except (TimeoutError, asyncio.TimeoutError) as e:
                    error_type = type(e).__name__
                    error_message = str(e)

                    logger.warning(
                        "Timeout error processing application (will retry)",
                        extra={
                            'application_id': application_id,
                            'error': error_message,
                            'error_type': error_type,
                            'stage': 'processing',
                            'retryable': True
                        },
                        exc_info=True
                    )

                    worker_tasks_total.labels(
                        task_name='process_credit_application',
                        status='failure'
                    ).inc()
                    duration = time.time() - start_time
                    worker_task_duration_seconds.labels(
                        task_name='process_credit_application'
                    ).observe(duration)

                    raise NetworkTimeoutError(
                        f"Timeout error: {error_message}"
                    ) from e

                except Exception as e:
                    error_type = type(e).__name__
                    error_message = str(e)

                    logger.error(
                        "Unexpected error processing application",
                        extra={
                            'application_id': application_id,
                            'error': error_message,
                            'error_type': error_type,
                            'stage': 'processing',
                            'retryable': 'unknown'
                        },
                        exc_info=True
                    )

                    worker_tasks_total.labels(
                        task_name='process_credit_application',
                        status='failure'
                    ).inc()
                    duration = time.time() - start_time
                    worker_task_duration_seconds.labels(
                        task_name='process_credit_application'
                    ).observe(duration)

                    raise
    finally:
        await redis_client.close()


async def send_webhook_notification(ctx, application_id: str, webhook_url: str):
    """Task: Send webhook notification to external system.

    Args:
        ctx: ARQ context
        application_id: Application UUID
        webhook_url: URL to send notification to
    """
    set_request_id(
        f"{Security.REQUEST_ID_PREFIX_WEBHOOK}{application_id[:Security.REQUEST_ID_UUID_LENGTH]}"
    )

    logger.info(
        "Sending webhook notification",
        extra={
            'application_id': application_id,
            'webhook_url': webhook_url
        }
    )

    await asyncio.sleep(Timeout.WEBHOOK_SIMULATION)

    logger.info(
        "Webhook sent successfully",
        extra={'application_id': application_id}
    )

    return f"Webhook sent for {application_id}"


async def cleanup_old_applications(ctx):
    """Periodic task: Clean up old applications.

    Archives or deletes old applications based on retention policy.
    """
    set_request_id(Security.REQUEST_ID_PREFIX_CLEANUP)

    logger.info("Running cleanup task")

    return "Cleanup completed"


async def cleanup_old_webhook_events(ctx):
    """Periodic task: Clean up old webhook events (TTL: 30 days).

    This task deletes webhook events older than 30 days to prevent
    unbounded growth of the webhook_events table.

    Runs daily to maintain database performance and storage efficiency.
    """
    set_request_id(Security.REQUEST_ID_PREFIX_CLEANUP)

    logger.info(
        "Running webhook events cleanup task",
        extra={'ttl_days': WebhookEventsTTL.TTL_DAYS}
    )

    # Calculate cutoff date (30 days ago)
    cutoff_date = datetime.now(UTC) - timedelta(days=WebhookEventsTTL.TTL_DAYS)

    async with AsyncSessionLocal() as db:
        try:
            delete_stmt = delete(WebhookEvent).where(
                WebhookEvent.created_at < cutoff_date
            )

            result = await db.execute(delete_stmt)
            deleted_count = result.rowcount

            await db.commit()

            logger.info(
                "Webhook events cleanup completed",
                extra={
                    'deleted_count': deleted_count,
                    'cutoff_date': cutoff_date.isoformat(),
                    'ttl_days': WebhookEventsTTL.TTL_DAYS
                }
            )

            return f"Deleted {deleted_count} webhook events older than {WebhookEventsTTL.TTL_DAYS} days"

        except (OperationalError, DatabaseError, SQLTimeoutError) as e:
            await db.rollback()
            logger.warning(
                "Database error during webhook cleanup (will retry)",
                extra={
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'retryable': True
                },
                exc_info=True
            )
            raise DatabaseConnectionError(
                f"Database error during cleanup: {str(e)}"
            ) from e
        except Exception as e:
            await db.rollback()
            logger.error(
                "Unexpected error during webhook cleanup",
                extra={
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'retryable': 'unknown'
                },
                exc_info=True
            )
            raise


async def monitor_table_partitioning(ctx):
    """Periodic task: Monitor tables and partition when they exceed 1M records.

    This task:
    1. Checks row counts for partitionable tables (applications, audit_logs, webhook_events)
    2. Automatically converts tables to partitioned tables when threshold (1M) is exceeded
    3. Ensures future partitions exist for already-partitioned tables
    4. Uses PostgreSQL native range partitioning by created_at (monthly partitions)

    Runs periodically to maintain optimal database performance as data grows.
    """
    set_request_id("partitioning-task")

    logger.info("Running table partitioning monitoring task")

    async with AsyncSessionLocal() as db:
        try:
            results = await monitor_and_partition_tables(db)

            logger.info(
                "Table partitioning check completed",
                extra={
                    'tables_checked': results.get('tables_checked', 0),
                    'tables_partitioned': results.get('tables_partitioned', 0),
                    'tables_already_partitioned': results.get('tables_already_partitioned', 0),
                    'tables_below_threshold': results.get('tables_below_threshold', 0),
                    'errors_count': len(results.get('errors', [])),
                }
            )

            if results.get('errors'):
                for error in results['errors']:
                    logger.warning(f"Partitioning error: {error}")

            return {
                'status': 'completed',
                'summary': {
                    'tables_checked': results.get('tables_checked', 0),
                    'tables_partitioned': results.get('tables_partitioned', 0),
                    'tables_already_partitioned': results.get('tables_already_partitioned', 0),
                    'tables_below_threshold': results.get('tables_below_threshold', 0),
                    'errors': results.get('errors', []),
                },
                'details': results.get('details', {}),
            }

        except (OperationalError, DatabaseError, SQLTimeoutError) as e:
            await db.rollback()
            logger.warning(
                "Database error during partitioning check (will retry)",
                extra={
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'retryable': True
                },
                exc_info=True
            )
            raise DatabaseConnectionError(
                f"Database error during partitioning: {str(e)}"
            ) from e
        except Exception as e:
            await db.rollback()
            logger.error(
                "Unexpected error during partitioning check",
                extra={
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'retryable': 'unknown'
                },
                exc_info=True
            )
            raise


async def enqueue_application_processing(application_id: str):
    """Enqueue an application for processing.

    This is called from the API endpoint to queue work.
    Propagates trace context to the worker for distributed tracing.

    Args:
        application_id: Application UUID
    """
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)

    redis = await create_pool(redis_settings)

    try:
        trace_context = {}
        inject_trace_context(trace_context)

        job = await redis.enqueue_job(
            'process_credit_application',
            application_id,
            trace_context if trace_context else None
        )

        logger.info(
            "Application queued for processing",
            extra={
                'application_id': application_id,
                'job_id': job.job_id if job else 'unknown'
            }
        )

        return job

    finally:
        await redis.close()
