"""Transaction Helper Utilities.

Provides safe transaction management with automatic rollback on errors.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def safe_transaction(
    db: AsyncSession
) -> AsyncGenerator[AsyncSession, None]:
    """Context manager for safe database transactions.

    Automatically commits on success, rolls back on any exception.

    Args:
        db: AsyncSession to manage

    Yields:
        The same AsyncSession for use within the context

    Raises:
        Any exception that occurs during the transaction will be re-raised
        after rolling back the transaction.

    Usage:
        ```python
        async with AsyncSessionLocal() as db:
            async with safe_transaction(db):
                # Do database operations
                application.status = ApplicationStatus.APPROVED
                # Auto-commits on success, auto-rollbacks on error
        ```

    Note:
        This context manager ensures that:
        - On success: transaction is committed automatically
        - On exception: transaction is rolled back and exception is re-raised
        - No manual commit/rollback calls are needed
    """
    try:
        yield db
        await db.commit()
        logger.debug("Transaction committed successfully")
    except Exception as e:
        await db.rollback()
        logger.error(
            "Transaction rolled back due to error",
            extra={
                'error': str(e),
                'error_type': type(e).__name__
            },
            exc_info=True
        )
        raise


async def safe_rollback(
    db: AsyncSession,
    error: Exception,
    context: str = ""
) -> None:
    """Safely rollback database transaction.

    Handles cases where transaction may already be closed or in invalid state.

    Args:
        db: Database session
        error: Exception that triggered rollback
        context: Context string for logging (e.g., "application creation")

    Note:
        This function is designed to be safe to call even if the transaction
        is already rolled back or closed. It will log warnings but not raise
        exceptions if rollback fails.
    """
    try:
        await db.rollback()
        logger.debug(
            "Transaction rolled back successfully",
            extra={
                'error': str(error),
                'error_type': type(error).__name__,
                'context': context
            }
        )
    except Exception as rollback_error:
        logger.warning(
            f"Rollback failed (transaction may already be closed): {context}",
            extra={
                'rollback_error': str(rollback_error),
                'rollback_error_type': type(rollback_error).__name__,
                'original_error': str(error),
                'original_error_type': type(error).__name__,
                'context': context
            }
        )
