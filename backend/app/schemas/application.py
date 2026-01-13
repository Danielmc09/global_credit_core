"""Pydantic Schemas for API Request/Response Validation.

These schemas handle validation and serialization for the API.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, condecimal, root_validator, validator

from ..core.constants import (
    COUNTRY_CURRENCY,
    CountryCode as CountryCodeConstants,
    CreditScore,
    Currency,
    ErrorMessages,
    RiskScore,
    ValidationLimits,
)
from ..core.country_limits import get_max_loan_amount, get_min_monthly_income
from ..models.application import ApplicationStatus, CountryCode
from ..utils import mask_document, sanitize_string


class ApplicationBase(BaseModel):
    """Base schema with common fields."""
    country: CountryCode
    full_name: str = Field(
        ...,
        min_length=ValidationLimits.MIN_NAME_LENGTH,
        max_length=ValidationLimits.MAX_NAME_LENGTH
    )
    requested_amount: condecimal(
        gt=0, decimal_places=ValidationLimits.MAX_AMOUNT_DECIMAL_PLACES
    ) = Field(...)
    monthly_income: condecimal(
        gt=0, decimal_places=ValidationLimits.MAX_AMOUNT_DECIMAL_PLACES
    ) = Field(...)
    currency: str | None = None


class ApplicationCreate(ApplicationBase):
    """Schema for creating a new application.

    Note: identity_document is treated as PII (Personally Identifiable Information).
    In production, this would be encrypted at rest.

    **Idempotency:**
    - If idempotency_key is provided, duplicate requests with the same key will return
      the existing application instead of creating a duplicate.
    - Clients should generate a unique key (e.g., UUID) for each request to ensure
      idempotency in case of network timeouts or retries.
    """
    identity_document: str = Field(
        ...,
        min_length=ValidationLimits.MIN_DOCUMENT_LENGTH,
        max_length=ValidationLimits.MAX_DOCUMENT_LENGTH
    )
    country_specific_data: dict[str, Any] | None = {}
    idempotency_key: str | None = Field(
        None,
        max_length=255,
        description="Optional idempotency key to prevent duplicate applications. "
                    "If provided and an application with this key exists, the existing application will be returned."
    )

    @validator('identity_document')
    def validate_document_not_empty(cls, v):
        """Validate and sanitize identity document."""
        sanitized = sanitize_string(v)
        if not sanitized:
            raise ValueError(ErrorMessages.DOCUMENT_EMPTY)
        return sanitized

    @validator('full_name')
    def validate_name(cls, v):
        """Validate that full name contains at least first and last name."""
        sanitized = sanitize_string(v)
        if not sanitized:
            raise ValueError(ErrorMessages.NAME_EMPTY)
        parts = sanitized.split()
        if len(parts) < ValidationLimits.MIN_NAME_PARTS:
            raise ValueError(ErrorMessages.NAME_INVALID)
        return sanitized

    @root_validator(skip_on_failure=True)
    def validate_all_country_specific_rules(cls, values):
        """Validate currency, amount limits, and income limits.

        This root_validator runs after all field validators to ensure:
        1. Currency is set or validated against country
        2. Requested amount is within country limits
        3. Monthly income meets country minimum requirements
        """
        country = values.get('country')
        if not country:
            return values

        country_code = country if isinstance(country, str) else country.value
        currency = values.get('currency')
        expected_currency = COUNTRY_CURRENCY.get(country_code)

        if currency is not None:
            currency_upper = currency.upper()

            if expected_currency:
                if currency_upper != expected_currency.upper():
                    country_name = CountryCodeConstants.COUNTRY_NAMES.get(
                        country_code, country_code
                    )
                    raise ValueError(
                        f"Currency '{currency}' does not match country "
                        f"'{country_name}' ({country_code}). "
                        f"Expected currency: {expected_currency}"
                    )
                values['currency'] = expected_currency
            else:
                if currency_upper not in Currency.SUPPORTED_CURRENCIES:
                    raise ValueError(
                        f"Currency '{currency}' is not supported. "
                        f"Supported currencies: {', '.join(Currency.SUPPORTED_CURRENCIES)}"
                    )
        elif expected_currency:
            values['currency'] = expected_currency
        else:
            raise ValueError(
                f"Currency is required for country '{country_code}'. "
                f"Please specify a currency code (e.g., EUR, BRL, MXN, COP)."
            )

        requested_amount = values.get('requested_amount')
        if requested_amount is not None:
            amount_to_check = (
                requested_amount
                if isinstance(requested_amount, Decimal)
                else Decimal(str(requested_amount))
            )

            max_amount = get_max_loan_amount(country_code)
            if max_amount is not None and amount_to_check > max_amount:
                raise ValueError(
                    f"Requested amount exceeds maximum limit for {country_code}: "
                    f"${max_amount:,.2f}. Your request: ${amount_to_check:,.2f}"
                )

        monthly_income = values.get('monthly_income')
        if monthly_income is not None:
            income_to_check = (
                monthly_income
                if isinstance(monthly_income, Decimal)
                else Decimal(str(monthly_income))
            )

            min_income = get_min_monthly_income(country_code)
            if min_income is not None and income_to_check < min_income:
                raise ValueError(
                    f"Monthly income below minimum requirement for {country_code}: "
                    f"${min_income:,.2f}. Your income: ${income_to_check:,.2f}"
                )

        return values


class ApplicationUpdate(BaseModel):
    """Schema for updating an application."""
    status: ApplicationStatus | None = None
    risk_score: (
        condecimal(
            ge=RiskScore.MIN_SCORE,
            le=RiskScore.MAX_SCORE,
            decimal_places=ValidationLimits.RISK_SCORE_DECIMAL_PLACES,
        )
        | None
    ) = None
    banking_data: dict[str, Any] | None = None
    validation_errors: list[str] | None = None
    country_specific_data: dict[str, Any] | None = None


class ApplicationResponse(ApplicationBase):
    """Schema for application responses.

    Note: identity_document is masked in the actual response for security.
    """
    id: UUID
    identity_document: str
    status: ApplicationStatus
    risk_score: Decimal | None = None
    currency: str
    idempotency_key: str | None = None

    country_specific_data: dict[str, Any] = {}
    banking_data: dict[str, Any] = {}
    validation_errors: list[str] = []

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @validator('identity_document', pre=False)
    def mask_document_field(cls, v):
        """Mask identity document for security (PII protection).
        Shows only last 4 characters.
        """
        return mask_document(v)


class ApplicationListResponse(BaseModel):
    """Schema for paginated list response."""
    total: int
    page: int
    page_size: int
    applications: list[ApplicationResponse]


class AuditLogResponse(BaseModel):
    """Schema for audit log responses."""
    id: UUID
    application_id: UUID
    old_status: ApplicationStatus | None
    new_status: ApplicationStatus
    changed_by: str
    change_reason: str | None
    metadata: dict[str, Any] = Field(default={}, alias='change_metadata')

    class Config:
        from_attributes = True
        populate_by_name = True


class AuditLogListResponse(BaseModel):
    """Schema for paginated audit log list response."""
    total: int
    page: int
    page_size: int
    audit_logs: list[AuditLogResponse]


class PendingJobResponse(BaseModel):
    """Schema for pending job response (DB Trigger -> Queue flow)."""
    id: UUID
    application_id: UUID
    task_name: str
    status: str
    arq_job_id: str | None
    created_at: datetime
    enqueued_at: datetime | None
    processed_at: datetime | None
    error_message: str | None
    retry_count: int

    class Config:
        from_attributes = True


class PendingJobListResponse(BaseModel):
    """Schema for pending jobs list response."""
    pending_jobs: list[PendingJobResponse]


class WebhookBankConfirmation(BaseModel):
    """Schema for webhook payload from banking provider.

    This represents data received from external banking systems.
    """
    application_id: UUID
    document_verified: bool
    credit_score: int | None = Field(
        None,
        ge=CreditScore.MIN_INTERNATIONAL,
        le=CreditScore.MAX_INTERNATIONAL
    )
    total_debt: Decimal | None = Field(None, ge=0)
    monthly_obligations: Decimal | None = Field(None, ge=0)
    has_defaults: bool = False
    provider_reference: str | None = None
    verified_at: datetime
    webhook_signature: str | None = None


class ErrorResponse(BaseModel):
    """Standard error response schema."""
    error: str
    detail: str | None = None
    request_id: str | None = None


class SuccessResponse(BaseModel):
    """Standard success response schema."""
    message: str
    data: dict[str, Any] | None = None
