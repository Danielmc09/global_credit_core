from sqlalchemy.ext.asyncio import AsyncSession

from ...infrastructure.security import decrypt_pii_fields
from ...schemas.application import ApplicationResponse


def _build_application_dict(app, decrypted_name: str, decrypted_doc: str) -> dict:
    """Build application dictionary from ORM object.
    
    Args:
        app: Application ORM object
        decrypted_name: Decrypted full name
        decrypted_doc: Decrypted identity document
        
    Returns:
        Dictionary representation of application
    """
    return {
        "id": app.id,
        "country": app.country,
        "full_name": decrypted_name,
        "identity_document": decrypted_doc,
        "requested_amount": app.requested_amount,
        "monthly_income": app.monthly_income,
        "currency": app.currency,
        "status": app.status,
        "risk_score": app.risk_score,
        "idempotency_key": app.idempotency_key,
        "country_specific_data": app.country_specific_data or {},
        "banking_data": app.banking_data or {},
        "validation_errors": app.validation_errors or [],
        "created_at": app.created_at,
        "updated_at": app.updated_at,
    }


async def application_to_response(
    db: AsyncSession, 
    app,
    decrypted_full_name: str | None = None,
    decrypted_identity_document: str | None = None
) -> ApplicationResponse:
    """Convert Application ORM object to ApplicationResponse, decrypting PII fields.

    Args:
        db: Database session for decryption (used if values not pre-decrypted)
        app: Application ORM object
        decrypted_full_name: Optional pre-decrypted full name (if None, will decrypt)
        decrypted_identity_document: Optional pre-decrypted identity document (if None, will decrypt)

    Returns:
        ApplicationResponse with decrypted fields
    """
    decrypted_name, decrypted_doc = await decrypt_pii_fields(
        db,
        encrypted_full_name=app.full_name,
        encrypted_identity_document=app.identity_document,
        decrypted_full_name=decrypted_full_name,
        decrypted_identity_document=decrypted_identity_document
    )
    
    app_dict = _build_application_dict(app, decrypted_name, decrypted_doc)
    
    return ApplicationResponse.model_validate(app_dict)


async def convert_applications_to_responses(
    db: AsyncSession,
    applications: list,
    logger
) -> list[ApplicationResponse]:
    """Convert multiple applications to response format with error handling.
    
    Args:
        db: Database session
        applications: List of application ORM objects
        logger: Logger instance
        
    Returns:
        List of ApplicationResponse objects (failures are logged and skipped)
    """
    responses = []
    
    for app in applications:
        try:
            responses.append(await application_to_response(db, app))
        except Exception as decrypt_error:
            logger.warning(
                "Failed to decrypt application during list",
                extra={
                    'application_id': str(app.id) if app else None,
                    'error': str(decrypt_error),
                    'error_type': type(decrypt_error).__name__
                }
            )
            continue
    
    return responses
