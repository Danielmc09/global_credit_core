"""Custom Exceptions for Worker Error Handling.

This module defines specific exception classes to differentiate between
recoverable and permanent errors in worker tasks. This allows ARQ to make
intelligent decisions about retries.

Recoverable errors are transient issues that may resolve on retry:
- Network timeouts
- Temporary database connection issues
- External service unavailability

Permanent errors are issues that won't resolve on retry:
- Invalid data (e.g., invalid UUID, application not found)
- Validation errors
- Business logic violations
"""


class WorkerError(Exception):
    """Base exception for all worker-related errors."""
    pass


class RecoverableError(WorkerError):
    """Error that may be resolved on retry.

    These errors are typically transient:
    - Network issues
    - Temporary database connection problems
    - External service timeouts
    - Rate limiting (temporary)

    ARQ should retry these errors.
    """
    pass


class PermanentError(WorkerError):
    """Error that won't be resolved on retry.

    These errors indicate permanent issues:
    - Invalid input data
    - Resource not found
    - Validation failures
    - Business rule violations

    ARQ should NOT retry these errors.
    """
    pass


# Specific recoverable errors
class DatabaseConnectionError(RecoverableError):
    """Database connection or transaction error that may be temporary."""
    pass


class ExternalServiceError(RecoverableError):
    """Error from external service that may be temporary."""
    pass


class NetworkTimeoutError(RecoverableError):
    """Network timeout that may resolve on retry."""
    pass


class RateLimitError(RecoverableError):
    """Rate limit error that may resolve after delay."""
    pass


# Specific permanent errors
class InvalidApplicationIdError(PermanentError):
    """Invalid application ID format or value."""
    pass


class ApplicationNotFoundError(PermanentError):
    """Application not found in database."""
    pass


class ValidationError(PermanentError):
    """Data validation error that won't resolve on retry."""
    pass


class BusinessRuleViolationError(PermanentError):
    """Business rule violation that won't resolve on retry."""
    pass


class StateTransitionError(PermanentError):
    """Invalid state transition that won't resolve on retry."""
    pass
