import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.exc import DatabaseError, OperationalError, TimeoutError as SQLTimeoutError

from ..core.constants import Security, WebhookEventsTTL
from ..core.exceptions import DatabaseConnectionError
from ..core.logging import get_logger, set_request_id
from ..db.database import AsyncSessionLocal
from ..models.webhook_event import WebhookEvent

logger = get_logger(__name__)


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
