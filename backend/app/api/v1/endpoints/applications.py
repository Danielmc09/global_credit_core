from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ....domain.transformers import (
    application_to_response,
    convert_applications_to_responses,
)
from ..helpers.rate_limit_helpers import apply_rate_limit_if_needed
from ....core.constants import (
    ErrorMessages,
    Pagination,
    SuccessMessages,
)
from ...dependencies import require_admin, require_auth
from ....core.logging import get_logger, get_request_id
from ....domain.validators import is_duplicate_constraint_error
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
    PendingJobListResponse,
    PendingJobResponse,
    SuccessResponse,
)
from ....services.application_service import ApplicationService
from ....services.cache_service import cache
from ....strategies.factory import CountryStrategyFactory
from ....utils import sanitize_log_data
from ....utils.transaction_helpers import safe_rollback, safe_transaction

logger = get_logger(__name__)

router = APIRouter()


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
    service = ApplicationService(
        db,
        redis=request.app.state.arq_pool,  # ARQ pool for job enqueuing
        cache_service=cache
    )

    try:
        app = await service.create_and_enqueue(application)
        return await application_to_response(db, app)

    except ValueError as e:
        await safe_rollback(db, e, "application creation - validation error")
        logger.error(
            "Application creation failed - validation error",
            extra={'error': str(e), 'request_id': get_request_id()}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
        
    except IntegrityError as e:
        await safe_rollback(db, e, "application creation - integrity error")
        error_str = str(e.orig) if hasattr(e, 'orig') else str(e)

        if is_duplicate_constraint_error(error_str):
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
        
        logger.error(
            "Database integrity error",
            extra={'error': error_str, 'request_id': get_request_id()},
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
            extra={'error': str(e), 'request_id': get_request_id()},
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

        # Fetch applications from database
        applications, total = await service.list_applications(
            country=country,
            status=status_filter,
            page=page,
            page_size=page_size
        )

        # Convert to response format (with error handling for decryption failures)
        application_responses = await convert_applications_to_responses(db, applications, logger)

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


async def _update_application_in_transaction(
    service: ApplicationService,
    application_id: UUID,
    update_data: ApplicationUpdate,
    db: AsyncSession
):
    """Update application within transaction.
    
    Args:
        service: Application service instance
        application_id: Application ID to update
        update_data: Update data
        db: Database session
        
    Returns:
        Updated application
        
    Raises:
        HTTPException: If application not found
    """
    async with safe_transaction(db):
        application = await service.update_application(application_id, update_data)
        
        if not application:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.APPLICATION_NOT_FOUND.format(application_id=application_id)
            )
        
        await db.refresh(application)
    
    return application


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
        application = await _update_application_in_transaction(
            service, application_id, update_data, db
        )
        
        try:
            await cache.invalidate_application(str(application_id))
        except Exception as e:
            logger.warning(
                "Failed to invalidate cache after application update",
                extra={'error': str(e), 'application_id': str(application_id), 'request_id': get_request_id()}
            )
        
        logger.info(
            "Application updated",
            extra={'application_id': str(application_id), 'request_id': get_request_id()}
        )

        return await application_to_response(db, application)
        
    except HTTPException:
        raise
        
    except ValueError as e:
        await safe_rollback(db, e, f"application update - validation error (id: {application_id})")
        logger.warning(
            "Validation error updating application",
            extra={'application_id': str(application_id), 'error': str(e), 'request_id': get_request_id()}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
        
    except Exception as e:
        await safe_rollback(db, e, f"application update - unexpected error (id: {application_id})")
        logger.error(
            "Error updating application",
            extra={'application_id': str(application_id), 'error': str(e), 'request_id': get_request_id()},
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
    "/{application_id}/pending-jobs",
    response_model=PendingJobListResponse,
    summary="Get pending jobs for an application (DB Trigger -> Queue flow)",
    responses={
        200: {"description": "List of pending jobs"},
        401: {"description": "Unauthorized - Invalid or missing JWT token"},
        403: {"description": "Forbidden - Authentication required"},
        404: {"model": ErrorResponse, "description": "Application not found"}
    },
    openapi_extra={
        "security": [{"BearerAuth": []}]
    }
)
async def get_pending_jobs(
    application_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_auth)
):
    """Get pending jobs for an application (DB Trigger -> Queue flow).

    CRITICAL: This endpoint shows the "DB Trigger -> Job Queue" flow (Requirement 3.7).
    When a new application is INSERTED, a database trigger automatically creates a pending_job.
    This endpoint returns those jobs, making the flow visible.

    Returns:
        List of pending jobs for the application, ordered by creation date (newest first).
    """
    service = ApplicationService(db)

    application = await service.get_application(application_id)
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.APPLICATION_NOT_FOUND.format(application_id=application_id)
        )

    pending_jobs = await service.get_pending_jobs(application_id)

    pending_job_responses = [PendingJobResponse.model_validate(job) for job in pending_jobs]

    return PendingJobListResponse(
        pending_jobs=pending_job_responses
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
