from sqlalchemy.ext.asyncio import AsyncSession

from ...infrastructure.security import encrypt_for_query
from ...core.logging import get_logger
from ...core.constants import ApplicationStatus
from ...repositories.application_repository import ApplicationRepository
from ...utils import sanitize_log_data

logger = get_logger(__name__)


async def check_duplicate_by_document(
    db: AsyncSession,
    document: str,
    country: str
) -> None:
    """Check for duplicate applications by document and country.
    
    Business rule: Only one active application per document+country combination.
    
    Args:
        db: Database session
        document: Document to check
        country: Country to check
        
    Raises:
        ValueError: If an active application already exists for this document and country
    """
    active_statuses = ApplicationStatus.ACTIVE_STATUSES
    
    repository = ApplicationRepository(db)
    encrypted_document = await encrypt_for_query(db, document)
    existing = await repository.find_active_by_document_and_country(
        country,
        encrypted_document,
        active_statuses,
        for_update=True
    )
    
    if existing:
        logger.warning(
            "Duplicate application attempt",
            extra=sanitize_log_data({
                'country': country,
                'document': document,
                'existing_status': existing.status,
                'existing_id': str(existing.id)
            })
        )
        raise ValueError(
            f"An active application with document '{document}' "
            f"already exists for country '{country}'. "
            f"Current status: {existing.status}. "
            f"Only one active application per document and country is allowed. "
            f"You can create a new application once the current one is REJECTED, CANCELLED, or COMPLETED."
        )
