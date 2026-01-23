"""Application Constants.

Centralized constants used throughout the application.
This file contains all hardcoded values that should be maintained in one place.
"""

from decimal import Decimal

# ============================================================================
# APPLICATION STATUS CONSTANTS
# ============================================================================

class ApplicationStatus:
    """Application status values."""
    PENDING = "PENDING"
    VALIDATING = "VALIDATING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

    # List of all statuses
    ALL_STATUSES = [
        PENDING,
        VALIDATING,
        APPROVED,
        REJECTED,
        UNDER_REVIEW,
        COMPLETED,
        CANCELLED,
    ]

    # List of active statuses (applications that are still in progress)
    # Used for duplicate detection - only one active application per document/country
    ACTIVE_STATUSES = [
        PENDING,
        VALIDATING,
        APPROVED,
        UNDER_REVIEW,
    ]

    # Default status for new applications
    DEFAULT_STATUS = PENDING



# ============================================================================
# COUNTRY CODE CONSTANTS
# ============================================================================

class CountryCode:
    """Supported country codes (ISO 3166-1 alpha-2)."""
    SPAIN = "ES"
    PORTUGAL = "PT"
    ITALY = "IT"
    MEXICO = "MX"
    COLOMBIA = "CO"
    BRAZIL = "BR"
    ARGENTINA = "AR"

    # List of all supported countries
    SUPPORTED_COUNTRIES = [
        SPAIN,
        PORTUGAL,
        ITALY,
        MEXICO,
        COLOMBIA,
        BRAZIL,
    ]

    # Country names mapping
    COUNTRY_NAMES: dict[str, str] = {
        SPAIN: "España",
        PORTUGAL: "Portugal",
        ITALY: "Italia",
        MEXICO: "México",
        COLOMBIA: "Colombia",
        BRAZIL: "Brasil",
    }

    # Document types by country
    DOCUMENT_TYPES: dict[str, str] = {
        SPAIN: "DNI",
        PORTUGAL: "NIF",
        ITALY: "Codice Fiscale",
        MEXICO: "CURP",
        COLOMBIA: "Cédula",
        BRAZIL: "CPF",
    }


# ============================================================================
# CURRENCY CONSTANTS
# ============================================================================

class Currency:
    """Supported currency codes (ISO 4217)."""
    EUR = "EUR"  # Euro (Spain, Portugal, Italy)
    BRL = "BRL"  # Brazilian Real (Brazil)
    MXN = "MXN"  # Mexican Peso (Mexico)
    COP = "COP"  # Colombian Peso (Colombia)
    ARG = "ARS"

    # List of all supported currencies
    SUPPORTED_CURRENCIES = [
        EUR,
        BRL,
        MXN,
        COP,
        ARG
    ]


# Mapping of country codes to their default currency
# This is used for validation and auto-inference when currency is not provided
COUNTRY_CURRENCY: dict[str, str] = {
    CountryCode.SPAIN: Currency.EUR,
    CountryCode.PORTUGAL: Currency.EUR,
    CountryCode.ITALY: Currency.EUR,
    CountryCode.BRAZIL: Currency.BRL,
    CountryCode.MEXICO: Currency.MXN,
    CountryCode.COLOMBIA: Currency.COP,
    CountryCode.ARGENTINA: Currency.ARG

}


# ============================================================================
# RISK ASSESSMENT CONSTANTS
# ============================================================================

class RiskLevel:
    """Risk level classifications."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ApprovalRecommendation:
    """Approval recommendation values."""
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REVIEW = "REVIEW"


class RiskScore:
    """Risk score constants."""
    MIN_SCORE = Decimal("0")
    MAX_SCORE = Decimal("100")
    DEFAULT_MIN = Decimal("10")

    # Payment ratio thresholds (percentage of income)
    MAX_PAYMENT_RATIO_PERCENT = Decimal("35.0")  # 35% of monthly income

    # Risk level thresholds (used for determining risk level from score)
    CRITICAL_THRESHOLD = Decimal("70")  # >= 70: CRITICAL
    HIGH_THRESHOLD = Decimal("50")  # >= 50: HIGH
    MEDIUM_THRESHOLD = Decimal("30")  # >= 30: MEDIUM, < 30: LOW


# ============================================================================
# CREDIT SCORE CONSTANTS
# ============================================================================

class CreditScore:
    """Credit score ranges and thresholds."""
    # International scale (FICO-like)
    MIN_INTERNATIONAL = 300
    MAX_INTERNATIONAL = 850
    DEFAULT_MIN_INTERNATIONAL = 500

    # Brazilian scale (Serasa)
    MIN_BRAZIL = 0
    MAX_BRAZIL = 1000

    # High credit score thresholds
    HIGH_SCORE_THRESHOLD = 750  # Excellent credit score
    GOOD_SCORE_THRESHOLD = 700  # Good credit score


# ============================================================================
# VALIDATION CONSTANTS
# ============================================================================

class ValidationLimits:
    """Validation limits for fields."""
    # Name validation
    MIN_NAME_LENGTH = 3
    MAX_NAME_LENGTH = 255
    MIN_NAME_PARTS = 2  # At least first and last name

    # Document validation
    MIN_DOCUMENT_LENGTH = 5
    MAX_DOCUMENT_LENGTH = 50

    # Amount validation
    MIN_AMOUNT = Decimal("0.01")
    MAX_AMOUNT_DECIMAL_PLACES = 2

    # Risk score validation
    MIN_RISK_SCORE = Decimal("0")
    MAX_RISK_SCORE = Decimal("100")
    RISK_SCORE_DECIMAL_PLACES = 2


# ============================================================================
# PAGINATION CONSTANTS
# ============================================================================

class Pagination:
    """Pagination defaults and limits."""
    DEFAULT_PAGE = 1
    DEFAULT_PAGE_SIZE = 10
    MIN_PAGE_SIZE = 1
    MAX_PAGE_SIZE = 100


# ============================================================================
# DATABASE CONSTANTS
# ============================================================================

class DatabaseLimits:
    """Database field length limits."""
    FULL_NAME_MAX_LENGTH = 255
    IDENTITY_DOCUMENT_MAX_LENGTH = 50
    CHANGED_BY_MAX_LENGTH = 100
    CHANGE_REASON_MAX_LENGTH = 500

    # Numeric precision
    AMOUNT_PRECISION = 12
    AMOUNT_SCALE = 2
    RISK_SCORE_PRECISION = 5
    RISK_SCORE_SCALE = 2

    # Connection pool settings
    POOL_SIZE = 10
    MAX_OVERFLOW = 20

    # Partitioning threshold
    PARTITION_THRESHOLD = 1_000_000  # 1 million records


# ============================================================================
# SECURITY & MASKING CONSTANTS
# ============================================================================

class Security:
    """Security-related constants."""
    # Document masking
    DOCUMENT_MASK_CHAR = "*"
    DOCUMENT_VISIBLE_CHARS = 4  # Show last 4 characters
    DOCUMENT_MASK_FULL = "****"  # When document is too short

    # Request ID
    REQUEST_ID_PREFIX_WORKER = "worker-"
    REQUEST_ID_PREFIX_WEBHOOK = "webhook-"
    REQUEST_ID_PREFIX_CLEANUP = "cleanup-task"
    REQUEST_ID_UUID_LENGTH = 8  # First 8 chars of UUID


# ============================================================================
# WEBHOOK EVENTS TTL CONSTANTS
# ============================================================================

class WebhookEventsTTL:
    """Webhook events TTL constants for cleanup."""
    TTL_DAYS = 30  # Delete events older than 30 days
    TTL_SECONDS = TTL_DAYS * 24 * 60 * 60  # 30 days in seconds


# ============================================================================
# PAYLOAD SIZE CONSTANTS
# ============================================================================

class PayloadLimits:
    """General payload size limits to prevent DoS attacks."""
    # Default limit for all API endpoints (except webhooks which have their own limit)
    MAX_PAYLOAD_SIZE_BYTES = 2 * 1024 * 1024  # 2MB (2,097,152 bytes)
    MAX_PAYLOAD_SIZE_MB = 2  # For error messages


class WebhookPayloadLimits:
    """Webhook payload size limits to prevent DoS attacks."""
    MAX_PAYLOAD_SIZE_BYTES = 1 * 1024 * 1024  # 1MB (1,048,576 bytes)
    MAX_PAYLOAD_SIZE_MB = 1  # For error messages


# ============================================================================
# CACHE CONSTANTS
# ============================================================================

class Cache:
    """Cache-related constants."""
    DEFAULT_TTL_SECONDS = 300  # 5 minutes
    DEFAULT_PAGE_SIZE = 10


# ============================================================================
# TIMEOUT CONSTANTS
# ============================================================================

class Timeout:
    """Timeout values in seconds."""
    JOB_TIMEOUT = 300  # 5 minutes per job
    PROVIDER_TIMEOUT = 30  # 30 seconds for provider calls (prevents blocking workers)
    WEBHOOK_SIMULATION = 0.5  # Simulated webhook delay
    # Processing delays for visibility (demo purposes)
    VALIDATION_STAGE_DELAY = 5.0  # Delay after status change to VALIDATING (5 seconds)
    BANKING_DATA_DELAY = 5.0  # Delay after fetching banking data (5 seconds)
    BUSINESS_RULES_DELAY = 5.0  # Delay after applying business rules (5 seconds)


# ============================================================================
# ERROR MESSAGES
# ============================================================================

class ErrorMessages:
    """Standard error messages."""
    INTERNAL_SERVER_ERROR = "Internal server error"
    APPLICATION_NOT_FOUND = "Application {application_id} not found"
    COUNTRY_NOT_SUPPORTED = "Country '{country_code}' is not supported"
    DOCUMENT_VALIDATION_FAILED = "Document validation failed: {errors}"
    DOCUMENT_EMPTY = "Identity document cannot be empty"
    NAME_EMPTY = "Full name cannot be empty"
    NAME_INVALID = "Full name should include at least first and last name"
    PROCESSING_ERROR = "Processing error: {error}"


# ============================================================================
# SUCCESS MESSAGES
# ============================================================================

class SuccessMessages:
    """Standard success messages."""
    APPLICATION_DELETED = "Application deleted successfully"
    APPLICATION_CREATED = "Application created successfully"
    APPLICATION_UPDATED = "Application updated successfully"
    WEBHOOK_SENT = "Webhook sent successfully"
    CLEANUP_COMPLETED = "Cleanup completed"


# ============================================================================
# HTTP HEADERS
# ============================================================================

class HttpHeaders:
    """HTTP header names."""
    REQUEST_ID = "X-Request-ID"
    PROCESS_TIME = "X-Process-Time"
    WEBHOOK_SIGNATURE = "X-Webhook-Signature"
    AUTHORIZATION = "Authorization"
    CONTENT_TYPE = "Content-Type"
    ACCEPT = "Accept"
    CONTENT_LENGTH = "Content-Length"


# ============================================================================
# API ENDPOINTS
# ============================================================================

class ApiEndpoints:
    """API endpoint paths."""
    DOCS = "/docs"
    REDOC = "/redoc"
    OPENAPI = "/openapi.json"
    HEALTH = "/health"
    ROOT = "/"


# ============================================================================
# BUSINESS RULES CONSTANTS
# ============================================================================

class BusinessRules:
    """Common business rule constants."""
    # Common calculation values
    MONTHS_PER_YEAR = 12
    MONTHS_PER_YEAR_DECIMAL = Decimal('12')  # Decimal version for calculations
    PERCENTAGE_MULTIPLIER = Decimal('100')  # For converting ratios to percentages
    YEARS_FOR_STABILITY_CHECK = 2
    YEARS_FOR_STABILITY_CHECK_DECIMAL = Decimal('2')  # Decimal version

    # Loan term defaults
    DEFAULT_LOAN_TERM_MONTHS = 36
    DEFAULT_LOAN_TERM_MONTHS_DECIMAL = Decimal('36')  # Decimal version for calculations
    DEFAULT_LOAN_TERM_MONTHS_COLOMBIA = 12

    # Debt-to-income thresholds
    MAX_DEBT_TO_INCOME_MONTHS = 6  # 6 months of income

    # Account age thresholds (months)
    MIN_ACCOUNT_AGE_MONTHS = 36
    MIN_ACCOUNT_AGE_MONTHS_BRAZIL = 24  # Brazil uses 24 months threshold

    # Risk score adjustments (positive - reduce risk)
    RISK_SCORE_ADJUSTMENT_HIGH_CREDIT = Decimal("15")
    RISK_SCORE_ADJUSTMENT_GOOD_CREDIT = Decimal("10")
    RISK_SCORE_ADJUSTMENT_GOOD_ACCOUNT_AGE = Decimal("10")
    RISK_SCORE_ADJUSTMENT_LOW_PAYMENT_RATIO = Decimal("5")
    RISK_SCORE_ADJUSTMENT_ACCOUNT_AGE_BRAZIL = Decimal("5")

    # Risk score penalties (negative - increase risk)
    RISK_SCORE_PENALTY_DEFAULT = Decimal("35")
    RISK_SCORE_PENALTY_LOW_INCOME = Decimal("30")
    RISK_SCORE_PENALTY_LOW_CREDIT = Decimal("30")
    RISK_SCORE_PENALTY_HIGH_AMOUNT = Decimal("25")
    RISK_SCORE_PENALTY_HIGH_RATIO = Decimal("25")
    RISK_SCORE_PENALTY_HIGH_DEBT = Decimal("20")
    RISK_SCORE_PENALTY_HIGH_DEBT_BRAZIL = Decimal("20")

    # Spain-specific risk score penalties
    RISK_SCORE_PENALTY_HIGH_AMOUNT_THRESHOLD = Decimal("15")  # For amounts exceeding high threshold
    RISK_SCORE_PENALTY_HIGH_DTI_SPAIN = Decimal("30")  # For high debt-to-income ratio in Spain
    RISK_SCORE_PENALTY_LOW_CREDIT_SPAIN = Decimal("25")  # For low credit score in Spain
    RISK_SCORE_PENALTY_DEFAULTS_SPAIN = Decimal("40")  # For active defaults in Spain

    # Mexico-specific risk score penalties
    RISK_SCORE_PENALTY_LOW_INCOME_MEXICO = Decimal("40")  # For low income in Mexico
    RISK_SCORE_PENALTY_LOAN_TO_INCOME_MEXICO = Decimal("35")  # For exceeding loan-to-income multiple
    RISK_SCORE_PENALTY_HIGH_PAYMENT_RATIO_MEXICO = Decimal("25")  # For high payment-to-income ratio
    RISK_SCORE_PENALTY_HIGH_DTI_MEXICO = Decimal("30")  # For high debt-to-income ratio in Mexico
    RISK_SCORE_PENALTY_LOW_CREDIT_MEXICO = Decimal("30")  # For low credit score in Mexico
    RISK_SCORE_PENALTY_DEFAULTS_MEXICO = Decimal("35")  # For active defaults in Mexico

    # Italy-specific risk score penalties
    RISK_SCORE_PENALTY_FINANCIAL_STABILITY_ITALY = Decimal("15")  # For exceeding 2 years of income

    # Payment ratio thresholds (percentage)
    LOW_PAYMENT_RATIO_THRESHOLD = Decimal("15.0")  # Below this is considered low/comfortable
    HIGH_DTI_THRESHOLD_MEXICO = Decimal("45.0")  # Mexico-specific DTI threshold
    HIGH_PAYMENT_RATIO_THRESHOLD_ITALY = Decimal("30.0")  # Italy-specific payment ratio threshold


# ============================================================================
# COUNTRY-SPECIFIC BUSINESS RULES
# ============================================================================

class CountryBusinessRules:
    """Country-specific business rule constants."""

    # Spain (ES)
    SPAIN_MIN_INCOME = Decimal("1500.00")  # EUR
    SPAIN_MAX_LOAN_AMOUNT = Decimal("50000.00")  # EUR
    SPAIN_HIGH_AMOUNT_THRESHOLD = Decimal("20000.00")  # EUR
    SPAIN_MAX_DEBT_TO_INCOME = Decimal("40.0")  # 40%
    SPAIN_MIN_CREDIT_SCORE = 600

    # Portugal (PT)
    PORTUGAL_MIN_INCOME = Decimal("800.00")  # EUR
    PORTUGAL_MAX_LOAN_AMOUNT = Decimal("30000.00")  # EUR
    PORTUGAL_MAX_DEBT_TO_INCOME = Decimal("35.0")  # 35%
    PORTUGAL_MIN_CREDIT_SCORE = 550

    # Italy (IT)
    ITALY_MIN_INCOME = Decimal("1200.00")  # EUR
    ITALY_MAX_LOAN_AMOUNT = Decimal("40000.00")  # EUR
    ITALY_MAX_DEBT_TO_INCOME = Decimal("35.0")  # 35%
    ITALY_MIN_CREDIT_SCORE = 550

    # Mexico (MX)
    MEXICO_MIN_INCOME = Decimal("5000.00")  # MXN
    MEXICO_MAX_LOAN_AMOUNT = Decimal("200000.00")  # MXN
    MEXICO_MAX_DEBT_TO_INCOME = Decimal("40.0")  # 40%
    MEXICO_MIN_CREDIT_SCORE = 500

    # Colombia (CO)
    COLOMBIA_MIN_INCOME = Decimal("1500000.00")  # COP
    COLOMBIA_MAX_LOAN_AMOUNT = Decimal("50000000.00")  # COP
    COLOMBIA_MAX_PAYMENT_TO_INCOME = Decimal("40.0")  # 40%
    COLOMBIA_MIN_CREDIT_SCORE = 600

    # Brazil (BR)
    BRAZIL_MIN_INCOME = Decimal("2000.00")  # BRL
    BRAZIL_MAX_LOAN_AMOUNT = Decimal("100000.00")  # BRL
    BRAZIL_MAX_LOAN_TO_INCOME_RATIO = Decimal("5.0")  # 5x annual income
    BRAZIL_MAX_DEBT_TO_INCOME = Decimal("35.0")  # 35%
    BRAZIL_MIN_CREDIT_SCORE = 550


# ============================================================================
# PROVIDER NAMES
# ============================================================================

class ProviderNames:
    """Banking provider names by country."""
    SPAIN = "Spanish Banking Provider"
    PORTUGAL = "Portuguese Banking Provider"
    ITALY = "Italian Banking Provider"
    MEXICO = "Mexican Banking Provider (Buró de Crédito)"
    COLOMBIA = "Colombian Banking Provider (DataCrédito)"
    BRAZIL = "Brazilian Banking Provider (Serasa)"


# ============================================================================
# SYSTEM VALUES
# ============================================================================

class SystemValues:
    """System default values."""
    DEFAULT_CHANGED_BY = "system"
    DEFAULT_ACCOUNT_STATUS = "active"
    DEFAULT_LOAN_TERM_MONTHS = 36


# ============================================================================
# CIRCUIT BREAKER CONSTANTS
# ============================================================================

class CircuitBreaker:
    """Circuit breaker configuration constants."""
    DEFAULT_FAILURE_THRESHOLD = 5
    DEFAULT_RECOVERY_TIMEOUT = 60  # seconds

    # Circuit breaker states
    STATE_CLOSED = 0
    STATE_OPEN = 1
    STATE_HALF_OPEN = 2

    # Fallback credit score when circuit is open (default for unknown countries)
    FALLBACK_CREDIT_SCORE = 600
    
    # Safety margin to subtract from country minimum for conservative fallback
    # This ensures applications are flagged for review rather than auto-approved
    FALLBACK_SCORE_MARGIN = 50


# ============================================================================
# WEBSOCKET CONSTANTS
# ============================================================================

class WebSocketMessageTypes:
    """WebSocket message type constants."""
    CONNECTION = "connection"
    SUBSCRIBED = "subscribed"
    APPLICATION_UPDATE = "application_update"
    PING = "ping"
    PONG = "pong"


class WebSocketActions:
    """WebSocket action constants."""
    SUBSCRIBE = "subscribe"
    PING = "ping"


class WebSocket:
    """WebSocket connection and retry constants."""
    # Redis subscriber retry configuration
    MAX_RETRIES = 10
    INITIAL_BACKOFF_SECONDS = 5 
    MAX_BACKOFF_SECONDS = 300  # 5 minutes


# ============================================================================
# HTTP CONSTANTS
# ============================================================================

class HttpStatusCodes:
    """HTTP status code constants."""
    INTERNAL_SERVER_ERROR = 500
    NOT_FOUND = 404
    UNAUTHORIZED = 401
    BAD_REQUEST = 400
    OK = 200
    CREATED = 201


# ============================================================================
# PATH NORMALIZATION CONSTANTS
# ============================================================================

class PathNormalization:
    """Constants for path normalization in metrics."""
    UUID_LENGTH = 36
    UUID_DASH_COUNT = 4
    MIN_ID_LENGTH = 20
    ID_PLACEHOLDER = "{id}"


# ============================================================================
# METRICS CONSTANTS
# ============================================================================

class Metrics:
    """Metrics-related constants."""
    ENDPOINT_PATH = "/metrics"
