"""Webhook Endpoints.

Receive notifications from external banking systems (Requirement 3.8).
"""

import json
from functools import wraps
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import ValidationError
from slowapi import Limiter
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.config import settings
from ....core.constants import ErrorMessages, SuccessMessages, WebhookPayloadLimits
from ....core.logging import get_logger
from ....infrastructure.security import get_rate_limit_key, verify_webhook_signature
from ....db.database import get_db
from ....models.application import ApplicationStatus
from ....models.webhook_event import WebhookEvent, WebhookEventStatus
from ....schemas.application import SuccessResponse, WebhookBankConfirmation
from ....services.application_service import ApplicationService
from ....infrastructure.messaging import publish_application_update
from ....utils import format_datetime
from ....utils import validate_banking_data_precision

logger = get_logger(__name__)

router = APIRouter()

# Rate limiter instance
# Uses IP + user_id combination for better control (prevents bypassing limits with different IPs)
limiter = Limiter(key_func=get_rate_limit_key)

# Helper function to conditionally apply rate limiting
def apply_rate_limit_if_needed(func):
    """Apply rate limiting only if not in test environment.
    
    Uses settings.ENVIRONMENT to check the current environment.
    Since conftest.py sets ENVIRONMENT="test" in os.environ before
    importing application code, settings will correctly capture this value.
    """
    # Use settings.ENVIRONMENT for consistent configuration access
    # conftest.py sets ENVIRONMENT="test" before importing, so settings will have the correct value
    if settings.ENVIRONMENT == "test":
        # In test environment, return function unchanged (no rate limiting)
        return func
    
    # In production/development, apply rate limiting
    return limiter.limit("100/minute")(func)


@router.post(
    "/bank-confirmation",
    response_model=SuccessResponse,
    summary="Receive bank confirmation webhook",
    responses={
        200: {"description": "Webhook processed successfully"},
        401: {"description": "Invalid signature"},
        404: {"description": "Application not found"}
    }
)
@apply_rate_limit_if_needed
async def bank_confirmation_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_webhook_signature: str | None = Header(None)
):
    """Webhook endpoint to receive banking data confirmation from external providers.

    **Security:**
    - Requires valid signature in X-Webhook-Signature header
    - Signature is HMAC-SHA256 of raw payload with shared secret

    **Idempotency:**
    - Uses provider_reference as idempotency key
    - Duplicate webhooks are detected and return success without reprocessing
    - Failed webhooks can be retried

    **Process:**
    1. Read raw request body
    2. Verify webhook signature
    3. Parse and validate payload
    4. **Check idempotency (NEW)** - if already processed, return early
    5. Find application
    6. Update with banking data
    7. Update status if needed
    8. Mark webhook as processed

    This demonstrates integration with external systems (Requirement 3.8).
    """
    if not x_webhook_signature:
        logger.warning("Webhook received without signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing webhook signature (X-Webhook-Signature header required)"
        )

    # Validate payload size to prevent DoS attacks
    # Check Content-Length header first if available
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            content_length_int = int(content_length)
            if content_length_int > WebhookPayloadLimits.MAX_PAYLOAD_SIZE_BYTES:
                logger.warning(
                    "Webhook payload too large (Content-Length check)",
                    extra={'content_length': content_length_int, 'max_size': WebhookPayloadLimits.MAX_PAYLOAD_SIZE_BYTES}
                )
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Webhook payload exceeds maximum size of {WebhookPayloadLimits.MAX_PAYLOAD_SIZE_MB}MB"
                )
        except ValueError:
            # Invalid Content-Length header, continue to check actual body size
            logger.debug("Invalid Content-Length header, will check actual body size")

    body_bytes = await request.body()
    
    # Validate actual body size (in case Content-Length was missing or incorrect)
    if len(body_bytes) > WebhookPayloadLimits.MAX_PAYLOAD_SIZE_BYTES:
        logger.warning(
            "Webhook payload too large (body size check)",
            extra={'body_size': len(body_bytes), 'max_size': WebhookPayloadLimits.MAX_PAYLOAD_SIZE_BYTES}
        )
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Webhook payload exceeds maximum size of {WebhookPayloadLimits.MAX_PAYLOAD_SIZE_MB}MB"
        )
    
    payload_json = body_bytes.decode('utf-8')

    if not verify_webhook_signature(
        payload_json,
        x_webhook_signature
    ):
        logger.warning("Invalid webhook signature received")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )

    try:
        payload_dict = json.loads(payload_json)

        if 'application_id' in payload_dict and isinstance(payload_dict['application_id'], str):
            try:
                uuid_value = UUID(payload_dict['application_id'])
                payload_dict['application_id'] = uuid_value
            except (ValueError, TypeError) as uuid_error:
                logger.error(
                    "Invalid application_id format in webhook payload",
                    extra={'application_id': payload_dict.get('application_id'), 'error': str(uuid_error)}
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid application_id format: {uuid_error!s}"
                )
        webhook_data = WebhookBankConfirmation(**payload_dict)

        payload_for_storage = json.loads(payload_json)
    except HTTPException:
        raise
    except ValidationError as e:
        error_details = "; ".join([f"{err['loc']}: {err['msg']}" for err in e.errors()])
        logger.error(
            "Invalid webhook payload (Pydantic validation)",
            extra={'error': error_details, 'payload_preview': payload_json[:200]}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid webhook payload: {error_details}"
        )
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.error(
            "Invalid webhook payload",
            extra={'error': str(e), 'payload_preview': payload_json[:200]}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid webhook payload: {e!s}"
        )

    idempotency_key = webhook_data.provider_reference

    if not idempotency_key:
        logger.warning(
            "Webhook received without provider_reference",
            extra={'application_id': str(webhook_data.application_id)}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing provider_reference in webhook payload (required for idempotency)"
        )

    existing_event_query = select(WebhookEvent).where(
        WebhookEvent.idempotency_key == idempotency_key
    )
    result = await db.execute(existing_event_query)
    existing_event = result.scalar_one_or_none()

    if existing_event:
        if existing_event.is_already_processed():
            logger.info(
                "Webhook already processed (idempotent response)",
                extra={
                    'idempotency_key': idempotency_key,
                    'application_id': str(webhook_data.application_id),
                    'original_processed_at': str(existing_event.processed_at)
                }
            )
            return SuccessResponse(
                message="Webhook already processed",
                data={
                    'application_id': str(existing_event.application_id),
                    'already_processed': True,
                    'processed_at': existing_event.processed_at.isoformat() if existing_event.processed_at else None
                }
            )
        else:
            logger.info(
                "Retrying previously failed webhook",
                extra={
                    'idempotency_key': idempotency_key,
                    'previous_status': existing_event.status,
                    'previous_error': existing_event.error_message
                }
            )
            existing_event.status = WebhookEventStatus.PROCESSING
            existing_event.error_message = None
            webhook_event = existing_event
    else:
        # Check if application exists WITHOUT decrypting
        # Decrypting would modify the Application object in the session,
        # causing SQLAlchemy to try to save decrypted strings to BYTEA columns on commit
        try:
            service = ApplicationService(db)
            application = await service.repository.find_by_id(webhook_data.application_id, decrypt=False)
        except Exception as find_error:
            # Error occurred before webhook_event creation - return HTTPException
            logger.error(
                "Failed to find application for webhook",
                extra={
                    'error': str(find_error),
                    'error_type': type(find_error).__name__,
                    'application_id': str(webhook_data.application_id),
                    'idempotency_key': idempotency_key
                },
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error processing webhook: {find_error!s}"
            )

        if not application:
            logger.warning(
                "Application not found for webhook",
                extra={
                    'application_id': str(webhook_data.application_id),
                    'idempotency_key': idempotency_key
                }
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.APPLICATION_NOT_FOUND.format(application_id=webhook_data.application_id)
            )

        # Application exists - create event record
        # webhook_data.application_id is already a UUID object from Pydantic validation
        try:
            webhook_event = WebhookEvent(
                idempotency_key=idempotency_key,
                application_id=webhook_data.application_id,
                payload=payload_for_storage,  # Use the copy with string values for JSONB
                status=WebhookEventStatus.PROCESSING
            )
            db.add(webhook_event)
            logger.debug(
                "Created new webhook event",
                extra={
                    'idempotency_key': idempotency_key,
                    'application_id': str(webhook_data.application_id)
                }
            )
        except Exception as create_error:
            logger.error(
                "Failed to create webhook event",
                extra={
                    'error': str(create_error),
                    'error_type': type(create_error).__name__,
                    'idempotency_key': idempotency_key,
                    'application_id': str(webhook_data.application_id)
                },
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save webhook event: {create_error!s}"
            )

    # Commit the webhook event record before processing
    # This ensures idempotency even if processing fails
    try:
        await db.commit()
        logger.debug("Webhook event committed to database")
    except IntegrityError as integrity_error:
        # Handle unique constraint violations (shouldn't happen if logic is correct, but handle gracefully)
        await db.rollback()
        error_str = str(integrity_error.orig) if hasattr(integrity_error, 'orig') else str(integrity_error)
        if 'unique' in error_str.lower() or 'duplicate' in error_str.lower():
            logger.warning(
                "Webhook event already exists (race condition?)",
                extra={
                    'idempotency_key': idempotency_key,
                    'error': error_str
                }
            )
            # Try to fetch the existing event
            result = await db.execute(
                select(WebhookEvent).where(WebhookEvent.idempotency_key == idempotency_key)
            )
            existing_event = result.scalar_one_or_none()
            if existing_event:
                webhook_event = existing_event
                if existing_event.is_already_processed():
                    # Already processed - return success
                    return SuccessResponse(
                        message="Webhook already processed",
                        data={
                            'application_id': str(existing_event.application_id),
                            'already_processed': True,
                            'processed_at': existing_event.processed_at.isoformat() if existing_event.processed_at else None
                        }
                    )
                # Update for retry
                existing_event.status = WebhookEventStatus.PROCESSING
                existing_event.error_message = None
                await db.commit()
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to save webhook event: duplicate key violation"
                )
        else:
            logger.error(
                "Database integrity error committing webhook event",
                extra={
                    'error': error_str,
                    'idempotency_key': idempotency_key
                },
                exc_info=True
            )
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save webhook event: {error_str}"
            )
    except Exception as commit_error:
        logger.error(
            "Failed to commit webhook event",
            extra={
                'error': str(commit_error),
                'error_type': type(commit_error).__name__,
                'idempotency_key': idempotency_key
            },
            exc_info=True
        )
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save webhook event: {commit_error!s}"
        )

    logger.info(
        "Received bank confirmation webhook",
        extra={
            'application_id': str(webhook_data.application_id),
            'document_verified': webhook_data.document_verified,
            'idempotency_key': idempotency_key
        }
    )

    # Application already verified to exist above, so we can proceed with processing
    # Get the application again WITHOUT decrypting, as we need to update it
    # Decrypting would modify the Application object in the session,
    # causing SQLAlchemy to try to save decrypted strings to BYTEA columns on commit
    service = ApplicationService(db)

    try:
        # Find application WITHOUT decrypting (should exist since we verified it above)
        application = await service.repository.find_by_id(webhook_data.application_id, decrypt=False)

        if not application:
            # This should not happen since we verified above, but handle it gracefully
            webhook_event.mark_as_failed(f"Application not found: {webhook_data.application_id}")
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.APPLICATION_NOT_FOUND.format(application_id=webhook_data.application_id)
            )

        # Update banking data
        banking_data = application.banking_data or {}
        banking_data.update({
            'document_verified': webhook_data.document_verified,
            'credit_score': webhook_data.credit_score,
            'total_debt': str(webhook_data.total_debt) if webhook_data.total_debt else None,               # Decimal preserved as string
            'monthly_obligations': str(webhook_data.monthly_obligations) if webhook_data.monthly_obligations else None,  # Decimal preserved as string
            'has_defaults': webhook_data.has_defaults,
            'provider_reference': webhook_data.provider_reference,
            'verified_at': format_datetime(webhook_data.verified_at, "%Y-%m-%dT%H:%M:%S"),
            'webhook_received': True
        })

        # Validate precision before updating to prevent database errors
        application.banking_data = validate_banking_data_precision(banking_data)

        # If document not verified, reject application
        if not webhook_data.document_verified:
            application.status = ApplicationStatus.REJECTED
            application.validation_errors = ['Document verification failed by banking provider']

        # Mark webhook as successfully processed
        webhook_event.mark_as_processed()

        await db.commit()

        logger.info(
            "Bank confirmation processed",
            extra={
                'application_id': str(webhook_data.application_id),
                'status': application.status,
                'idempotency_key': idempotency_key
            }
        )

        # Publish update to Redis (will be broadcast to WebSocket clients)
        try:
            status_value = application.status.value if hasattr(application.status, 'value') else str(application.status)
            updated_at_str = (
                format_datetime(application.updated_at, "%Y-%m-%dT%H:%M:%S")
                if application.updated_at 
                else None
            )
            
            await publish_application_update(
                application_id=str(application.id),
                status=status_value,
                risk_score=application.risk_score,
                updated_at=updated_at_str
            )
        except Exception as broadcast_error:
            # Don't fail the webhook if publish fails
            logger.warning(
                "Failed to publish application update to Redis",
                extra={
                    'error': str(broadcast_error),
                    'application_id': str(application.id)
                }
            )

        return SuccessResponse(
            message=SuccessMessages.WEBHOOK_SENT,
            data={
                'application_id': str(application.id),
                'status': application.status,
                'already_processed': False
            }
        )

    except HTTPException:
        # Re-raise HTTP exceptions without modification
        raise
    except Exception as e:
        # Mark webhook as failed for unexpected errors
        error_message = f"Unexpected error processing webhook: {e!s}"

        # Only mark webhook as failed if webhook_event exists
        # (it might not exist if error occurred before creation)
        if 'webhook_event' in locals() and webhook_event is not None:
            try:
                webhook_event.mark_as_failed(error_message)
                await db.commit()
            except Exception as commit_error:
                logger.error(
                    "Failed to mark webhook as failed",
                    extra={'error': str(commit_error), 'original_error': str(e)}
                )
                # Continue to raise original error even if commit fails

        # Log error with available context
        log_extra = {
            'error': str(e),
            'error_type': type(e).__name__
        }
        if 'idempotency_key' in locals():
            log_extra['idempotency_key'] = idempotency_key
        if 'webhook_data' in locals():
            log_extra['application_id'] = str(webhook_data.application_id)

        logger.error(
            "Failed to process webhook",
            extra=log_extra,
            exc_info=True
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_message
        )
