"""Application Endpoints.

RESTful API endpoints for credit applications.
"""

from functools import wraps
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from slowapi import Limiter
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.config import settings
from ....core.constants import (
    ErrorMessages,
    Pagination,
    SuccessMessages,
)
from ....core.dependencies import require_admin, require_auth
from ....core.encryption import decrypt_value
from ....core.logging import get_logger, get_request_id
from ....core.rate_limiting import get_rate_limit_key
from ....db.database import get_db
from ....models.application import ApplicationStatus
from ....schemas.application import (
    ApplicationCreate,
    ApplicationListResponse,
    ApplicationResponse,
    ApplicationUpdate,
    AuditLogListResponse,
    AuditLogResponse,
    ErrorResponse,
    SuccessResponse,
)
from ....services.application_service import ApplicationService
from ....services.cache_service import cache
from ....services.websocket_service import broadcast_application_update
from ....strategies.factory import CountryStrategyFactory
from ....utils.helpers import sanitize_log_data
from ....utils.transaction_helpers import safe_rollback, safe_transaction
from ....workers.tasks import enqueue_application_processing

logger = get_logger(__name__)

router = APIRouter()

limiter = Limiter(key_func=get_rate_limit_key)


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
    if decrypted_full_name is not None:
        decrypted_name = decrypted_full_name
    elif app.full_name:
        if isinstance(app.full_name, str):
            decrypted_name = app.full_name
        else:
            try:
                if not db.in_transaction():
                    await db.begin()
                decrypted_name = await decrypt_value(db, app.full_name)
            except Exception as e:
                logger.warning(
                    "Decryption failed, attempting with new transaction",
                    extra={'error': str(e), 'error_type': type(e).__name__}
                )
                try:
                    if not db.in_transaction():
                        await db.begin()
                    decrypted_name = await decrypt_value(db, app.full_name)
                except Exception as retry_error:
                    logger.error(
                        "Decryption failed after retry",
                        extra={'error': str(retry_error), 'error_type': type(retry_error).__name__}
                    )
                    raise ValueError(f"Decryption failed: {str(retry_error)}") from retry_error
    else:
        decrypted_name = ""
    
    if decrypted_identity_document is not None:
        decrypted_doc = decrypted_identity_document
    elif app.identity_document:
        if isinstance(app.identity_document, str):
            decrypted_doc = app.identity_document
        else:
            try:
                if not db.in_transaction():
                    await db.begin()
                decrypted_doc = await decrypt_value(db, app.identity_document)
            except Exception as e:
                logger.warning(
                    "Decryption failed, attempting with new transaction",
                    extra={'error': str(e), 'error_type': type(e).__name__}
                )
                try:
                    if not db.in_transaction():
                        await db.begin()
                    decrypted_doc = await decrypt_value(db, app.identity_document)
                except Exception as retry_error:
                    logger.error(
                        "Decryption failed after retry",
                        extra={'error': str(retry_error), 'error_type': type(retry_error).__name__}
                    )
                    raise ValueError(f"Decryption failed: {str(retry_error)}") from retry_error
    else:
        decrypted_doc = ""

    app_dict = {
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

    return ApplicationResponse.model_validate(app_dict)

def apply_rate_limit_if_needed(func):
    """Apply rate limiting only if not in test environment.
    
    Uses settings.ENVIRONMENT to check the current environment.
    Since conftest.py sets ENVIRONMENT="test" in os.environ before
    importing application code, settings will correctly capture this value.
    """
    if settings.ENVIRONMENT == "test":
        return func
    
    return limiter.limit("10/minute")(func)


@router.post(
    "",
    response_model=ApplicationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new credit application",
    responses={
        201: {"description": "Application created successfully"},
        400: {"model": ErrorResponse, "description": "Validation error"},
        401: {"description": "Unauthorized - Invalid or missing JWT token"},
        403: {"description": "Forbidden - Authentication required"},
        422: {"model": ErrorResponse, "description": "Invalid data"},
        429: {"description": "Too many requests - rate limit exceeded"}
    },
    openapi_extra={
        "security": [{"BearerAuth": []}],
        "examples": {
            "spain_application": {
                "summary": "Spanish application example",
                "description": "Example of creating a credit application for Spain",
                "value": {
                    "country": "ES",
                    "full_name": "Juan Pérez García",
                    "identity_document": "12345678Z",
                    "requested_amount": 10000.00,
                    "monthly_income": 3000.00,
                    "country_specific_data": {}
                }
            },
            "mexico_application": {
                "summary": "Mexico application example",
                "description": "Example of creating a credit application for Mexico",
                "value": {
                    "country": "MX",
                    "full_name": "María González López",
                    "identity_document": "ABCD123456EFGH78",
                    "requested_amount": 50000.00,
                    "monthly_income": 15000.00,
                    "country_specific_data": {
                        "curp": "GOLE800101HDFNRL01"
                    }
                }
            },
            "application_with_idempotency": {
                "summary": "Application with idempotency key",
                "description": "Example showing how to use idempotency_key to prevent duplicate applications",
                "value": {
                    "country": "ES",
                    "full_name": "Carlos Martínez Sánchez",
                    "identity_document": "87654321A",
                    "requested_amount": 15000.00,
                    "monthly_income": 4000.00,
                    "idempotency_key": "550e8400-e29b-41d4-a716-446655440000",
                    "country_specific_data": {}
                }
            }
        }
    }
)
@apply_rate_limit_if_needed
async def create_application(
    request: Request,
    application: ApplicationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_auth)
):
    """Create a new credit application.

    The application is created in PENDING status and queued for asynchronous processing.
    A worker will:
    1. Fetch banking data from the country's provider
    2. Apply business rules
    3. Update the status accordingly

    **Required fields:**
    - country: Country code (ES, MX, BR, etc.)
    - full_name: Full legal name
    - identity_document: Country-specific ID (DNI, CURP, CPF, etc.)
    - requested_amount: Amount requested (must be positive)
    - monthly_income: Monthly income (must be positive)

    **Idempotency:**
    - Optional `idempotency_key` field can be provided to prevent duplicate applications
    - If the same `idempotency_key` is sent twice, the existing application will be returned
    - Clients should generate a unique key (e.g., UUID) for each request to ensure idempotency
    """
    service = ApplicationService(db)

    try:
        request_idempotency_key = application.idempotency_key
        
        decrypted_name = None
        decrypted_doc = None
        
        async with safe_transaction(db):
            app = await service.create_application(application)
            await db.refresh(app)
            
            if app.full_name:
                if isinstance(app.full_name, str):
                    decrypted_name = app.full_name
                else:
                    decrypted_name = await decrypt_value(db, app.full_name)
            else:
                decrypted_name = ""
            
            if app.identity_document:
                if isinstance(app.identity_document, str):
                    decrypted_doc = app.identity_document
                else:
                    decrypted_doc = await decrypt_value(db, app.identity_document)
            else:
                decrypted_doc = ""

        from datetime import UTC, datetime, timedelta
        is_new_application = True
        if request_idempotency_key and app.idempotency_key == request_idempotency_key:
            now = datetime.now(UTC)
            created_at = app.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=UTC)
            time_since_creation = now - created_at
            if time_since_creation > timedelta(seconds=5):
                is_new_application = False
                logger.info(
                    "Idempotent request detected - returning existing application",
                    extra={
                        'application_id': str(app.id),
                        'idempotency_key': request_idempotency_key,
                        'created_at': app.created_at.isoformat(),
                        'request_id': get_request_id()
                    }
                )

        if is_new_application:
            await enqueue_application_processing(str(app.id))
            logger.info(
                "Application created and queued",
                extra={
                    'application_id': str(app.id),
                    'idempotency_key': request_idempotency_key,
                    'request_id': get_request_id()
                }
            )
        else:
            logger.info(
                "Idempotent request - existing application returned (not queued)",
                extra={
                    'application_id': str(app.id),
                    'idempotency_key': request_idempotency_key,
                    'request_id': get_request_id()
                }
            )

        try:
            await cache.invalidate_application(str(app.id))
        except Exception as e:
            logger.warning(
                "Failed to invalidate cache after application creation",
                extra={'error': str(e), 'application_id': str(app.id)}
            )

        return await application_to_response(
            db, 
            app, 
            decrypted_full_name=decrypted_name,
            decrypted_identity_document=decrypted_doc
        )

    except ValueError as e:
        await safe_rollback(db, e, "application creation - validation error")
        logger.error(
            "Application creation failed",
            extra={
                'error': str(e),
                'request_id': get_request_id()
            }
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except IntegrityError as e:
        await safe_rollback(db, e, "application creation - integrity error")
        error_str = str(e.orig) if hasattr(e, 'orig') else str(e)

        error_str_lower = error_str.lower()
        if ('unique_document_per_country' in error_str or
            'duplicate key' in error_str_lower or
            'unique constraint failed' in error_str_lower or
            'applications.country' in error_str or
            'applications.identity_document' in error_str):
            logger.warning(
                "Duplicate application attempt (database constraint)",
                extra=sanitize_log_data({
                    'country': application.country,
                    'document': application.identity_document,
                    'request_id': get_request_id()
                })
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An active application with document '{application.identity_document}' already exists for country '{application.country}'. Only one active application per document and country is allowed. Cancelled applications can be replaced with a new one."
            )
        else:
            logger.error(
                "Database integrity error",
                extra={
                    'error': error_str,
                    'request_id': get_request_id()
                },
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Database constraint violation. Please check your input data."
            )
    except Exception as e:
        await safe_rollback(db, e, "application creation - unexpected error")
        logger.error(
            "Unexpected error creating application",
            extra={
                'error': str(e),
                'request_id': get_request_id()
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorMessages.INTERNAL_SERVER_ERROR
        )


@router.get(
    "",
    response_model=ApplicationListResponse,
    summary="List credit applications",
    responses={
        401: {"description": "Unauthorized - Invalid or missing JWT token"},
        403: {"description": "Forbidden - Authentication required"},
        200: {"description": "List of applications"}
    }
)
async def list_applications(
    country: str | None = Query(None, description="Filter by country code"),
    status_filter: ApplicationStatus | None = Query(None, alias="status", description="Filter by status"),
    page: int = Query(
        Pagination.DEFAULT_PAGE,
        ge=1,
        description="Page number"
    ),
    page_size: int = Query(
        Pagination.DEFAULT_PAGE_SIZE,
        ge=Pagination.MIN_PAGE_SIZE,
        le=Pagination.MAX_PAGE_SIZE,
        description="Items per page"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_auth)
):
    """List all credit applications with optional filtering.

    Supports pagination and filtering by:
    - **country**: Country code (ES, MX, BR, etc.)
    - **status**: Application status (PENDING, APPROVED, etc.)

    Results are ordered by creation date (newest first).
    """
    try:
        service = ApplicationService(db)

        applications, total = await service.list_applications(
            country=country,
            status=status_filter,
            page=page,
            page_size=page_size
        )

        application_responses = []
        for app in applications:
            try:
                application_responses.append(await application_to_response(db, app))
            except Exception as decrypt_error:
                logger.warning(
                    "Failed to decrypt application during list",
                    extra={
                        'application_id': str(app.id) if app else None,
                        'error': str(decrypt_error),
                        'error_type': type(decrypt_error).__name__,
                        'request_id': get_request_id()
                    }
                )
                continue
        

        return ApplicationListResponse(
            total=total,
            page=page,
            page_size=page_size,
            applications=application_responses
        )
    except Exception as e:
        logger.error(
            "Error listing applications",
            extra={
                'error': str(e),
                'error_type': type(e).__name__,
                'country': country,
                'status': status_filter,
                'page': page,
                'request_id': get_request_id()
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorMessages.INTERNAL_SERVER_ERROR
        )


@router.get(
    "/{application_id}",
    response_model=ApplicationResponse,
    summary="Get application details",
    responses={
        200: {"description": "Application details"},
        401: {"description": "Unauthorized - Invalid or missing JWT token"},
        403: {"description": "Forbidden - Authentication required"},
        404: {"model": ErrorResponse, "description": "Application not found"}
    }
)
async def get_application(
    application_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_auth)
):
    """Get detailed information about a specific credit application.

    Returns full application details including:
    - Basic information
    - Status and risk assessment
    - Banking data (if available)
    - Country-specific data
    """
    service = ApplicationService(db)

    application = await service.get_application(application_id)

    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.APPLICATION_NOT_FOUND.format(application_id=application_id)
        )

    return await application_to_response(db, application)


@router.patch(
    "/{application_id}",
    response_model=ApplicationResponse,
    summary="Update application (Admin only)",
    responses={
        401: {"description": "Unauthorized - Invalid or missing JWT token"},
        403: {"description": "Forbidden - Admin role required"},
        200: {"description": "Application updated successfully"},
        404: {"model": ErrorResponse, "description": "Application not found"}
    }
)
async def update_application(
    application_id: UUID,
    update_data: ApplicationUpdate,
    db: AsyncSession = Depends(get_db),
    admin_user: dict = Depends(require_admin)
):
    """Update an existing application.

    Can update:
    - Status (will trigger audit log automatically via DB trigger)
    - Risk score
    - Banking data
    - Validation errors

    **Note:** Status changes are audited automatically.
    """
    service = ApplicationService(db)

    try:
        decrypted_name = None
        decrypted_doc = None
        
        async with safe_transaction(db):
            application = await service.update_application(application_id, update_data)

            if not application:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=ErrorMessages.APPLICATION_NOT_FOUND.format(application_id=application_id)
                )

            if application.full_name:
                if isinstance(application.full_name, str):
                    decrypted_name = application.full_name
                else:
                    decrypted_name = await decrypt_value(db, application.full_name)
            else:
                decrypted_name = ""
            
            if application.identity_document:
                if isinstance(application.identity_document, str):
                    decrypted_doc = application.identity_document
                else:
                    decrypted_doc = await decrypt_value(db, application.identity_document)
            else:
                decrypted_doc = ""

        await db.refresh(application)

        try:
            await cache.invalidate_application(str(application_id))
        except Exception as e:
            logger.warning(
                "Failed to invalidate cache after application update",
                extra={'error': str(e), 'application_id': str(application_id)}
            )

        logger.info(
            "Application updated",
            extra={
                'application_id': str(application_id),
                'request_id': get_request_id()
            }
        )

        return await application_to_response(
            db,
            application,
            decrypted_full_name=decrypted_name,
            decrypted_identity_document=decrypted_doc
        )
    except HTTPException:
        raise
    except ValueError as e:
        await safe_rollback(db, e, f"application update - validation error (id: {application_id})")
        logger.warning(
            "Validation error updating application",
            extra={
                'application_id': str(application_id),
                'error': str(e),
                'request_id': get_request_id()
            }
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        await safe_rollback(db, e, f"application update - unexpected error (id: {application_id})")
        logger.error(
            "Error updating application",
            extra={
                'application_id': str(application_id),
                'error': str(e),
                'request_id': get_request_id()
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorMessages.INTERNAL_SERVER_ERROR
        )


@router.delete(
    "/{application_id}",
    response_model=SuccessResponse,
    summary="Delete application (Admin only)",
    responses={
        401: {"description": "Unauthorized - Invalid or missing JWT token"},
        403: {"description": "Forbidden - Admin role required"},
        200: {"description": "Application deleted successfully"},
        404: {"model": ErrorResponse, "description": "Application not found"}
    }
)
async def delete_application(
    application_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin_user: dict = Depends(require_admin)
):
    """Soft delete an application.

    The application is not actually removed from the database,
    but marked as deleted and will not appear in normal queries.
    """
    service = ApplicationService(db)

    try:
        async with safe_transaction(db):
            deleted = await service.delete_application(application_id)

            if not deleted:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=ErrorMessages.APPLICATION_NOT_FOUND.format(application_id=application_id)
                )

        return SuccessResponse(
            message=SuccessMessages.APPLICATION_DELETED,
            data={"application_id": str(application_id)}
        )
    except HTTPException:
        raise
    except Exception as e:
        await safe_rollback(db, e, f"application deletion - unexpected error (id: {application_id})")
        logger.error(
            "Error deleting application",
            extra={
                'application_id': str(application_id),
                'error': str(e),
                'request_id': get_request_id()
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorMessages.INTERNAL_SERVER_ERROR
        )


@router.get(
    "/{application_id}/audit",
    response_model=AuditLogListResponse,
    summary="Get application audit logs",
    responses={
        200: {"description": "Paginated list of audit logs"},
        401: {"description": "Unauthorized - Invalid or missing JWT token"},
        403: {"description": "Forbidden - Authentication required"},
        404: {"model": ErrorResponse, "description": "Application not found"}
    },
    openapi_extra={
        "security": [{"BearerAuth": []}]
    }
)
async def get_audit_logs(
    application_id: UUID,
    page: int = Query(
        Pagination.DEFAULT_PAGE,
        ge=1,
        description="Page number"
    ),
    page_size: int = Query(
        Pagination.DEFAULT_PAGE_SIZE,
        ge=Pagination.MIN_PAGE_SIZE,
        le=Pagination.MAX_PAGE_SIZE,
        description="Items per page"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_auth)
):
    """Get audit trail for an application with pagination.

    Returns paginated status changes and who/what triggered them.
    Audit logs are created automatically via database triggers.
    Results are ordered by creation date (newest first).

    Supports pagination with:
    - **page**: Page number (1-indexed)
    - **page_size**: Number of items per page
    """
    service = ApplicationService(db)

    application = await service.get_application(application_id)
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.APPLICATION_NOT_FOUND.format(application_id=application_id)
        )

    audit_logs, total = await service.get_audit_logs(
        application_id,
        page=page,
        page_size=page_size
    )

    audit_log_responses = [AuditLogResponse.model_validate(log) for log in audit_logs]

    return AuditLogListResponse(
        total=total,
        page=page,
        page_size=page_size,
        audit_logs=audit_log_responses
    )


@router.get(
    "/stats/country/{country_code}",
    summary="Get country statistics",
    responses={
        200: {"description": "Country statistics"},
        400: {"model": ErrorResponse, "description": "Invalid country code"},
        401: {"description": "Unauthorized - Invalid or missing JWT token"},
        403: {"description": "Forbidden - Authentication required"}
    },
    openapi_extra={
        "security": [{"BearerAuth": []}]
    }
)
async def get_country_statistics(
    country_code: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_auth)
):
    """Get application statistics for a specific country.

    Returns:
    - Total applications
    - Total and average amounts
    - Count by status (pending, approved, rejected)
    """
    # Validate country code
    if not CountryStrategyFactory.is_country_supported(country_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorMessages.COUNTRY_NOT_SUPPORTED.format(country_code=country_code)
        )

    service = ApplicationService(db)

    async def fetch_stats():
        return await service.get_statistics_by_country(country_code)

    return await cache.get_country_stats_cached(country_code, fetch_stats)



@router.get(
    "/meta/supported-countries",
    summary="Get supported countries",
    responses={
        200: {"description": "List of supported country codes"}
    }
)
async def get_supported_countries():
    """Get list of supported country codes.

    Returns all countries that have implemented strategies.
    """
    countries = CountryStrategyFactory.get_supported_countries()

    return {
        "supported_countries": countries,
        "total": len(countries)
    }
