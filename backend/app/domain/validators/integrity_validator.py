from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ...infrastructure.security import decrypt_pii_fields
from ...core.logging import get_logger
from ...models.application import Application
from ...repositories.application_repository import ApplicationRepository
from ...schemas.application import ApplicationCreate
from ...utils import sanitize_log_data

logger = get_logger(__name__)

# Database constraint error patterns
DUPLICATE_ERROR_PATTERNS = (
    'unique_document_per_country',
    'duplicate key',
    'unique constraint failed',
    'applications.country',
    'applications.identity_document',
)


def is_duplicate_constraint_error(error_str: str) -> bool:
    """Check if error is a duplicate constraint violation.
    
    This is used to identify database constraint errors related to
    duplicate applications (by document or idempotency key).
    
    Args:
        error_str: Error string from database exception
        
    Returns:
        True if it's a duplicate constraint error, False otherwise
    """
    error_str_lower = error_str.lower()
    return any(pattern in error_str_lower for pattern in DUPLICATE_ERROR_PATTERNS)


async def handle_integrity_error(
    db: AsyncSession,
    error: IntegrityError,
    application_data: ApplicationCreate
) -> Application:
    """Handle database integrity errors during application creation.
    
    This handles race conditions where duplicate checks pass but
    database constraints are violated.
    
    Args:
        db: Database session
        error: The integrity error from database
        application_data: Application creation data
        
    Returns:
        Existing application if idempotency key duplicate
        
    Raises:
        ValueError: If duplicate document or other integrity error
    """
    
    error_str = str(error.orig) if hasattr(error, 'orig') else str(error)
    error_str_lower = error_str.lower()
    
    # Handle duplicate document constraint
    if ('unique_document_per_country' in error_str or
        'applications.country' in error_str or
        'applications.identity_document' in error_str):
        logger.warning(
            "Duplicate application attempt (database constraint - document)",
            extra=sanitize_log_data({
                'country': application_data.country,
                'document': application_data.identity_document,
                'error': error_str
            })
        )
        raise ValueError(
            f"An active application with document '{application_data.identity_document}' "
            f"already exists for country '{application_data.country}'. "
            f"Only one active application per document and country is allowed."
        )
    
    # Handle duplicate idempotency key constraint
    if 'unique_idempotency_key' in error_str or 'idempotency_key' in error_str_lower:
        logger.warning(
            "Duplicate idempotency key detected (database constraint)",
            extra={'idempotency_key': application_data.idempotency_key, 'error': error_str}
        )
        repository = ApplicationRepository(db)
        existing_app = await repository.find_by_idempotency_key(
            application_data.idempotency_key
        )
        if existing_app:
            logger.info(
                "Returning existing application from idempotency key constraint",
                extra={
                    'idempotency_key': application_data.idempotency_key,
                    'existing_application_id': str(existing_app.id)
                }
            )
            # Decrypt PII fields in-place
            decrypted_name, decrypted_doc = await decrypt_pii_fields(
                db,
                encrypted_full_name=existing_app.full_name,
                encrypted_identity_document=existing_app.identity_document
            )
            existing_app.full_name = decrypted_name
            existing_app.identity_document = decrypted_doc
            return existing_app
        else:
            raise ValueError(
                f"An application with idempotency_key '{application_data.idempotency_key}' "
                f"already exists, but could not be retrieved."
            )
    
    # Handle other integrity errors
    logger.error(
        "Database integrity error during application creation",
        extra=sanitize_log_data({
            'error': error_str,
            'country': application_data.country,
            'document': application_data.identity_document
        }),
        exc_info=True
    )
    raise
