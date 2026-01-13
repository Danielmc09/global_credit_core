"""Application Service Layer.

Handles business logic for credit applications.
Separates business logic from API controllers (clean architecture).
Uses Repository Pattern for data access.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.constants import (
    COUNTRY_CURRENCY,
    Currency,
    ErrorMessages,
    Pagination,
)
from ..core.encryption import decrypt_value, encrypt_for_query, encrypt_value
from ..core.logging import get_logger
from ..core.state_machine import validate_transition
from ..models.application import Application, ApplicationStatus, AuditLog
from ..repositories.application_repository import ApplicationRepository
from ..schemas.application import ApplicationCreate, ApplicationUpdate
from ..strategies.factory import get_country_strategy
from ..utils.helpers import sanitize_log_data, validate_amount_precision, validate_banking_data_precision, validate_risk_score_precision

logger = get_logger(__name__)


class ApplicationService:
    """Service for managing credit applications."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = ApplicationRepository(db)

    async def _decrypt_application_fields(self, application: Application) -> Application:
        """Decrypt PII fields in an application object.
        
        Args:
            application: Application object with encrypted fields
            
        Returns:
            Application with decrypted fields
        """
        if application:
            if application.identity_document:
                application.identity_document = await decrypt_value(self.db, application.identity_document)
            if application.full_name:
                application.full_name = await decrypt_value(self.db, application.full_name)
        return application

    async def create_application(
        self,
        application_data: ApplicationCreate
    ) -> Application:
        """Create a new credit application.

        This method:
        1. Validates currency matches country (defense in depth)
        2. Validates the identity document using country strategy
        3. Creates the application in PENDING status
        4. The actual evaluation happens asynchronously in a worker

        Args:
            application_data: Application creation data

        Returns:
            Created application

        Raises:
            ValueError: If validation fails (currency mismatch, invalid document, etc.)
        """
        logger.info(
            "Creating application",
            extra={
                'country': application_data.country,
                'amount': str(application_data.requested_amount)  # Decimal preserved as string
            }
        )

        # Get country strategy
        strategy = get_country_strategy(application_data.country)

        # Validate currency matches country
        country_code = application_data.country
        expected_currency = COUNTRY_CURRENCY.get(country_code)
        
        if application_data.currency is not None:
            # Currency provided - validate it matches the country
            currency_upper = application_data.currency.upper()
            
            if expected_currency:
                # Country has a defined currency - validate it matches
                if currency_upper != expected_currency.upper():
                    country_name = strategy.country_name
                    logger.warning(
                        "Currency mismatch detected",
                        extra={
                            'country': country_code,
                            'provided_currency': application_data.currency,
                            'expected_currency': expected_currency
                        }
                    )
                    raise ValueError(
                        f"Currency '{application_data.currency}' does not match country '{country_name}' ({country_code}). "
                        f"Expected currency: {expected_currency}"
                    )
                # Currency matches, normalize to expected format
                application_data.currency = expected_currency
            else:
                # Country not in mapping - validate it's a supported currency
                if currency_upper not in Currency.SUPPORTED_CURRENCIES:
                    logger.warning(
                        "Unsupported currency provided",
                        extra={
                            'country': country_code,
                            'currency': application_data.currency
                        }
                    )
                    raise ValueError(
                        f"Currency '{application_data.currency}' is not supported. "
                        f"Supported currencies: {', '.join(Currency.SUPPORTED_CURRENCIES)}"
                    )
        elif expected_currency:
            # Currency not provided but country has a default - infer it
            application_data.currency = expected_currency
            logger.debug(
                "Currency inferred from country",
                extra={
                    'country': country_code,
                    'inferred_currency': expected_currency
                }
            )
        else:
            # Currency not provided and country has no default
            logger.error(
                "Currency required but not provided and no default available",
                extra={'country': country_code}
            )
            raise ValueError(
                f"Currency is required for country '{country_code}'. "
                f"Please specify a currency code (e.g., EUR, BRL, MXN, COP)."
            )

        # Validate identity document
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
                ErrorMessages.DOCUMENT_VALIDATION_FAILED.format(
                    errors=', '.join(validation_result.errors)
                )
            )

        # Check for idempotency first (if idempotency_key is provided)
        if application_data.idempotency_key:
            existing_app_by_key = await self.repository.find_by_idempotency_key(
                application_data.idempotency_key,
                for_update=True
            )

            if existing_app_by_key:
                logger.info(
                    "Idempotent request detected - returning existing application",
                    extra={
                        'idempotency_key': application_data.idempotency_key,
                        'existing_application_id': str(existing_app_by_key.id),
                        'existing_status': existing_app_by_key.status
                    }
                )
                # Decrypt PII fields before returning
                await self._decrypt_application_fields(existing_app_by_key)
                return existing_app_by_key

        active_statuses = [
            ApplicationStatus.PENDING,
            ApplicationStatus.VALIDATING,
            ApplicationStatus.APPROVED,
            ApplicationStatus.UNDER_REVIEW
        ]

        # Encrypt identity_document for query (must match encrypted value in DB)
        encrypted_document = await encrypt_for_query(self.db, application_data.identity_document)
        
        existing = await self.repository.find_active_by_document_and_country(
            application_data.country,
            encrypted_document,
            active_statuses,
            for_update=True
        )

        if existing:
            logger.warning(
                "Duplicate application attempt",
                extra=sanitize_log_data({
                    'country': application_data.country,
                    'document': application_data.identity_document,
                    'existing_status': existing.status,
                    'existing_id': str(existing.id)
                })
            )
            raise ValueError(
                f"An active application with document '{application_data.identity_document}' "
                f"already exists for country '{application_data.country}'. "
                f"Current status: {existing.status}. "
                f"Only one active application per document and country is allowed. "
                f"You can create a new application once the current one is REJECTED, CANCELLED, or COMPLETED."
            )

        # Validate precision before inserting to prevent database errors
        validated_amount = validate_amount_precision(application_data.requested_amount)
        validated_income = validate_amount_precision(application_data.monthly_income)

        # Encrypt PII fields before storing
        encrypted_document = await encrypt_value(self.db, application_data.identity_document)
        encrypted_name = await encrypt_value(self.db, application_data.full_name)

        application = Application(
            country=application_data.country,
            full_name=encrypted_name,
            identity_document=encrypted_document,
            requested_amount=validated_amount,
            monthly_income=validated_income,
            currency=application_data.currency,
            status=ApplicationStatus.PENDING,
            country_specific_data=application_data.country_specific_data or {},
            validation_errors=validation_result.warnings,
            idempotency_key=application_data.idempotency_key
        )

        try:
            # Use repository to create application
            # Use flush() instead of commit() to:
            # 1. Get the application ID immediately (needed for response)
            # 2. Catch IntegrityError early (before commit)
            # 3. Allow the endpoint layer to handle commit via safe_transaction
            application = await self.repository.create(application)
        except IntegrityError as e:
            error_str = str(e.orig) if hasattr(e, 'orig') else str(e)
            error_str_lower = error_str.lower()

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
            elif ('unique_idempotency_key' in error_str or
                  'idempotency_key' in error_str_lower):
                # This should rarely happen since we check before insert, but handle race condition
                logger.warning(
                    "Duplicate idempotency key detected (database constraint)",
                    extra={
                        'idempotency_key': application_data.idempotency_key,
                        'error': error_str
                    }
                )
                # Fetch the existing application by idempotency_key
                existing_app_by_key = await self.repository.find_by_idempotency_key(
                    application_data.idempotency_key
                )
                if existing_app_by_key:
                    logger.info(
                        "Returning existing application from idempotency key constraint",
                        extra={
                            'idempotency_key': application_data.idempotency_key,
                            'existing_application_id': str(existing_app_by_key.id)
                        }
                    )
                    # Decrypt PII fields before returning
                    await self._decrypt_application_fields(existing_app_by_key)
                    return existing_app_by_key
                else:
                    # This shouldn't happen, but handle gracefully
                    raise ValueError(
                        f"An application with idempotency_key '{application_data.idempotency_key}' "
                        f"already exists, but could not be retrieved."
                    )
            elif ('duplicate key' in error_str_lower or
                  'unique constraint failed' in error_str_lower):
                # Generic unique constraint violation
                logger.error(
                    "Database unique constraint violation",
                    extra=sanitize_log_data({
                        'error': error_str,
                        'country': application_data.country,
                        'document': application_data.identity_document,
                        'idempotency_key': application_data.idempotency_key
                    }),
                    exc_info=True
                )
                raise
            else:
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
        except Exception as e:
            logger.error(
                "Unexpected error during application creation",
                extra=sanitize_log_data({
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'country': application_data.country,
                    'document': application_data.identity_document
                }),
                exc_info=True
            )
            raise

        logger.info(
            "Application created",
            extra={
                'application_id': str(application.id),
                'status': application.status
            }
        )

        # Decrypt PII fields before returning
        await self._decrypt_application_fields(application)
        return application

    async def get_application(self, application_id: UUID) -> Application | None:
        """Get an application by ID.

        Args:
            application_id: Application UUID

        Returns:
            Application if found, None otherwise
        """
        # Decrypt fields when getting for display/response
        return await self.repository.find_by_id(application_id, decrypt=True)

    async def list_applications(
        self,
        country: str | None = None,
        status: ApplicationStatus | None = None,
        page: int = Pagination.DEFAULT_PAGE,
        page_size: int = Pagination.DEFAULT_PAGE_SIZE
    ) -> tuple[list[Application], int]:
        """List applications with optional filtering and pagination.

        Args:
            country: Filter by country code
            status: Filter by status
            page: Page number (1-indexed)
            page_size: Number of items per page

        Returns:
            Tuple of (list of applications, total count)
        """
        applications, total = await self.repository.list(
            country=country,
            status=status,
            page=page,
            page_size=page_size
        )

        logger.info(
            "Listed applications",
            extra={
                'country': country,
                'status': status,
                'page': page,
                'total': total
            }
        )

        return applications, total

    async def update_application(
        self,
        application_id: UUID,
        update_data: ApplicationUpdate
    ) -> Application | None:
        """Update an application.

        Note: Status changes will automatically trigger the audit log via database trigger.

        Args:
            application_id: Application UUID
            update_data: Update data

        Returns:
            Updated application if found, None otherwise

        Raises:
            ValueError: If trying to change status of an application in a final state
        """
        # Get application WITHOUT decrypting, as we need to update it
        # Decrypted strings cannot be saved to BYTEA columns
        application = await self.repository.find_by_id(application_id, decrypt=False)

        if not application:
            return None

        if update_data.status is not None:
            old_status = application.status
            new_status = update_data.status

            validate_transition(old_status, new_status)

            if old_status != new_status:
                # Set session variable to indicate manual change (for trigger)
                # The trigger will use this to set changed_by and change_reason
                try:
                    await self.db.execute(
                        text("SET LOCAL app.changed_by = 'user'")
                    )
                    await self.db.execute(
                        text("SET LOCAL app.change_reason = 'Status changed manually'")
                    )
                except Exception as e:
                    # If SET LOCAL is not supported (e.g., SQLite), continue anyway
                    # The trigger will use default values ('system', 'Status changed automatically')
                    error_str = str(e).lower()
                    if 'syntax error' in error_str or 'not supported' in error_str or 'sqlite' in error_str:
                        logger.debug(
                            "SET LOCAL not supported (likely SQLite), trigger will use defaults",
                            extra={'error': str(e)}
                        )
                    else:
                        logger.warning(
                            "Could not set session variables for trigger, continuing anyway",
                            extra={'error': str(e)}
                        )

            # Update status (trigger will automatically create audit log)
            application.status = new_status
            logger.info(
                "Application status changed",
                extra={
                    'application_id': str(application_id),
                    'old_status': old_status,
                    'new_status': new_status,
                    'manual_change': True
                }
            )

        if update_data.risk_score is not None:
            # Validate precision before updating to prevent database errors
            application.risk_score = validate_risk_score_precision(update_data.risk_score)

        if update_data.banking_data is not None:
            # Validate precision before updating to prevent database errors
            application.banking_data = validate_banking_data_precision(update_data.banking_data)

        if update_data.validation_errors is not None:
            application.validation_errors = update_data.validation_errors

        if update_data.country_specific_data is not None:
            application.country_specific_data = update_data.country_specific_data

        # Use repository to update application
        # flush() is called inside repository.update()
        return await self.repository.update(application)

    async def delete_application(self, application_id: UUID) -> bool:
        """Soft delete an application.

        Args:
            application_id: Application UUID

        Returns:
            True if deleted, False if not found
        """
        application = await self.repository.find_by_id(application_id)

        if not application:
            return False

        await self.repository.soft_delete(application)

        logger.info(
            "Application deleted",
            extra={'application_id': str(application_id)}
        )

        return True

    async def get_audit_logs(
        self,
        application_id: UUID,
        page: int = Pagination.DEFAULT_PAGE,
        page_size: int = Pagination.DEFAULT_PAGE_SIZE
    ) -> tuple[list[AuditLog], int]:
        """Get audit logs for an application with pagination.

        Args:
            application_id: Application UUID
            page: Page number (1-indexed)
            page_size: Number of items per page

        Returns:
            Tuple of (list of audit logs, total count)
        """
        audit_logs, total = await self.repository.get_audit_logs(
            application_id,
            page=page,
            page_size=page_size
        )

        logger.info(
            "Listed audit logs",
            extra={
                'application_id': str(application_id),
                'page': page,
                'total': total
            }
        )

        return audit_logs, total

    async def get_statistics_by_country(self, country: str) -> dict[str, Any]:
        """Get application statistics for a country.

        Args:
            country: Country code

        Returns:
            Dictionary with statistics
        """
        return await self.repository.get_statistics_by_country(country)
