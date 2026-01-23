"""String manipulation utilities."""

from typing import Any

from ..core.constants import Security


def mask_document(document: str, visible_chars: int | None = None) -> str:
    """Mask identity document for security (PII protection).

    Shows only the last N characters, masking the rest with asterisks.

    Args:
        document: The document string to mask
        visible_chars: Number of characters to show at the end (default from Security constants)

    Returns:
        Masked document string

    Examples:
        >>> mask_document("12345678Z")
        "****5678Z"
        >>> mask_document("ABC123")
        "****"
    """
    if not document:
        return Security.DOCUMENT_MASK_FULL

    visible = visible_chars or Security.DOCUMENT_VISIBLE_CHARS

    if len(document) <= visible:
        return Security.DOCUMENT_MASK_FULL

    masked_length = len(document) - visible
    return Security.DOCUMENT_MASK_CHAR * masked_length + document[-visible:]


def sanitize_string(value: str, max_length: int | None = None) -> str:
    """Sanitize string by trimming whitespace and optionally truncating.

    Args:
        value: String to sanitize
        max_length: Optional maximum length

    Returns:
        Sanitized string

    Examples:
        >>> sanitize_string("  hello world  ")
        "hello world"
        >>> sanitize_string("hello world", max_length=5)
        "hello"
    """
    if not value:
        return ""

    sanitized = value.strip()

    if max_length and len(sanitized) > max_length:
        return sanitized[:max_length]

    return sanitized


def truncate_string(value: str, max_length: int, suffix: str = "...") -> str:
    """Truncate string to maximum length with suffix.

    Args:
        value: String to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated (default: "...")

    Returns:
        Truncated string

    Examples:
        >>> truncate_string("Hello world", 5)
        "Hello..."
        >>> truncate_string("Hi", 5)
        "Hi"
    """
    if not value or len(value) <= max_length:
        return value or ""

    return value[:max_length - len(suffix)] + suffix


def sanitize_log_data(data: dict[str, Any]) -> dict[str, Any]:
    """Sanitize log data by masking PII (Personally Identifiable Information).

    This function masks sensitive fields in log data to prevent PII leakage
    in logs. Fields that are considered PII:
    - identity_document: Masked using mask_document()
    - document: Alias for identity_document, also masked
    - full_name: Partially masked (shows first name only)
    - monthly_income: Masked (shows only range or masked value)
    - banking_data: Entire field is masked

    Args:
        data: Dictionary containing log data that may include PII

    Returns:
        Dictionary with PII fields masked

    Examples:
        >>> sanitize_log_data({'document': '12345678Z', 'country': 'ES'})
        {'document': '****5678Z', 'country': 'ES'}
        >>> sanitize_log_data({'full_name': 'Juan Pérez García', 'amount': 1000})
        {'full_name': 'Juan ****', 'amount': 1000}
    """
    if not data or not isinstance(data, dict):
        return data

    sanitized = data.copy()

    for key in ['document', 'identity_document']:
        if key in sanitized and sanitized[key]:
            sanitized[key] = mask_document(str(sanitized[key]))

    if 'full_name' in sanitized and sanitized['full_name']:
        name = str(sanitized['full_name']).strip()
        if name:
            name_parts = name.split()
            if len(name_parts) > 1:
                sanitized['full_name'] = f"{name_parts[0]} ****"
            else:
                if len(name) > 3:
                    sanitized['full_name'] = f"{name[:3]}****"
                else:
                    sanitized['full_name'] = "****"

    if 'monthly_income' in sanitized and sanitized['monthly_income'] is not None:
        income_str = str(sanitized['monthly_income'])
        sanitized['monthly_income'] = f"***{income_str[-2:]}" if len(income_str) > 2 else "****"

    if 'banking_data' in sanitized:
        sanitized['banking_data'] = "[REDACTED]"

    for key, value in sanitized.items():
        if isinstance(value, dict):
            sanitized[key] = sanitize_log_data(value)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_log_data(item) if isinstance(item, dict) else item
                for item in value
            ]

    return sanitized
