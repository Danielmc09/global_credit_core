"""Helper Utility Functions.

Common helper functions used throughout the application.
"""

import json
import re
import uuid
from datetime import date, datetime
from decimal import Decimal
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


def generate_request_id(prefix: str | None = None) -> str:
    """Generate a unique request ID.

    Args:
        prefix: Optional prefix for the request ID (e.g., "API", "WORKER")

    Returns:
        Request ID string (UUID)

    Examples:
        >>> generate_request_id()
        "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        >>> generate_request_id("API")
        "API-a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    """
    request_id = str(uuid.uuid4())
    if prefix:
        return f"{prefix}-{request_id}"
    return request_id


def format_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format datetime to string.

    Args:
        dt: Datetime object to format
        format_str: Format string (default: ISO-like format)

    Returns:
        Formatted datetime string

    Examples:
        >>> format_datetime(datetime(2024, 1, 15, 10, 30, 0))
        "2024-01-15 10:30:00"
        >>> format_datetime(datetime(2024, 1, 15), "%Y-%m-%d")
        "2024-01-15"
    """
    if not dt:
        return ""
    return dt.strftime(format_str)


def parse_datetime(date_string: str, format_str: str = "%Y-%m-%d") -> datetime | None:
    """Parse datetime string to datetime object.

    Args:
        date_string: Date string to parse
        format_str: Format string to use for parsing

    Returns:
        Datetime object or None if parsing fails

    Examples:
        >>> parse_datetime("2024-01-15")
        datetime(2024, 1, 15, 0, 0)
    """
    if not date_string:
        return None
    try:
        return datetime.strptime(date_string, format_str)
    except (ValueError, TypeError):
        return None


def calculate_age(birth_date: date) -> int:
    """Calculate age from birth date.

    Args:
        birth_date: Date of birth

    Returns:
        Age in years

    Examples:
        >>> from datetime import date
        >>> calculate_age(date(1990, 1, 1))
        34  # (assuming current year is 2024)
    """
    if not birth_date:
        return 0

    today = date.today()
    age = today.year - birth_date.year

    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1

    return age


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


def validate_uuid(uuid_string: str) -> bool:
    """Validate if a string is a valid UUID.

    Args:
        uuid_string: String to validate

    Returns:
        True if valid UUID, False otherwise

    Examples:
        >>> validate_uuid("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
        True
        >>> validate_uuid("invalid")
        False
    """
    if not uuid_string:
        return False

    if not isinstance(uuid_string, str):
        try:
            uuid_string = str(uuid_string)
        except (TypeError, ValueError):
            return False

    try:
        uuid.UUID(uuid_string)
        return True
    except (ValueError, TypeError):
        return False


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


def format_currency(amount: Decimal, currency_symbol: str = "$", decimals: int = 2) -> str:
    """Format decimal amount as currency string.

    Args:
        amount: Decimal amount to format
        currency_symbol: Currency symbol (default: "$")
        decimals: Number of decimal places (default: 2)

    Returns:
        Formatted currency string

    Examples:
        >>> format_currency(Decimal("1234.56"))
        "$1,234.56"
        >>> format_currency(Decimal("1000"), "€", 0)
        "€1,000"
    """
    if amount is None:
        return f"{currency_symbol}0.00"

    formatted = f"{amount:,.{decimals}f}"
    return f"{currency_symbol}{formatted}"


def generate_cache_key(
    prefix: str,
    *args,
    separator: str = ":",
    **kwargs
) -> str:
    """Generate a cache key from prefix and arguments.

    Args:
        prefix: Key prefix (e.g., "application", "list")
        *args: Positional arguments to include in key
        separator: Separator between key parts (default: ":")
        **kwargs: Keyword arguments to include in key (sorted by key name)

    Returns:
        Cache key string

    Examples:
        >>> generate_cache_key("application", "abc123")
        "application:abc123"
        >>> generate_cache_key("list", country="ES", status="PENDING", page=1)
        "list:country=ES:page=1:status=PENDING"
        >>> generate_cache_key("stats", "country", "ES")
        "stats:country:ES"
    """
    parts = [prefix]

    for arg in args:
        if arg is not None:
            parts.append(str(arg))

    if kwargs:
        sorted_kwargs = sorted(kwargs.items())
        for key, value in sorted_kwargs:
            if value is not None:
                parts.append(f"{key}={value}")

    return separator.join(parts)


def safe_json_loads(json_string: str, default: Any = None) -> Any:
    """Safely parse JSON string, returning default on error.

    Args:
        json_string: JSON string to parse
        default: Default value to return on error

    Returns:
        Parsed JSON object or default value
    """
    try:
        return json.loads(json_string)
    except (json.JSONDecodeError, TypeError):
        return default


def decimal_to_string(value: Any) -> Any:
    """Convert Decimal to string preserving precision for JSON serialization.

    This is critical in fintech to avoid precision loss from Decimal → float conversion.

    Args:
        value: Value to convert (typically Decimal, but handles other types)

    Returns:
        String if Decimal, otherwise original value

    Examples:
        >>> decimal_to_string(Decimal("1234.5678"))
        "1234.5678"
        >>> decimal_to_string({"amount": Decimal("100.00")})
        {"amount": "100.00"}
    """
    if isinstance(value, Decimal):
        return str(value)
    elif isinstance(value, dict):
        return {k: decimal_to_string(v) for k, v in value.items()}
    elif isinstance(value, list | tuple):
        return [decimal_to_string(item) for item in value]
    return value


def safe_json_dumps(obj: Any, default: str = "{}") -> str:
    """Safely serialize object to JSON string.

    Preserves Decimal precision by converting to string (critical for fintech).

    Args:
        obj: Object to serialize
        default: Default string to return on error

    Returns:
        JSON string or default value
    """
    try:
        obj_converted = decimal_to_string(obj)
        return json.dumps(obj_converted, default=str)
    except (TypeError, ValueError):
        return default


def normalize_path(path: str) -> str:
    """Normalize API path by replacing UUIDs and IDs with placeholders.

    Useful for metrics and logging to avoid high cardinality.

    Args:
        path: API path to normalize

    Returns:
        Normalized path with IDs replaced

    Examples:
        >>> normalize_path("/api/v1/applications/a1b2c3d4-e5f6-7890-abcd-ef1234567890")
        "/api/v1/applications/{id}"
        >>> normalize_path("/api/v1/applications/123/audit")
        "/api/v1/applications/{id}/audit"
    """
    if not path:
        return path

    uuid_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
    path = re.sub(uuid_pattern, '{id}', path, flags=re.IGNORECASE)

    return re.sub(r'/\d+(?=/|$)', '/{id}', path)


def validate_amount_precision(amount: Decimal | None) -> Decimal | None:
    """Validate and round amount to database precision (2 decimal places).

    This function ensures amounts are rounded to the correct precision
    before being stored in the database to prevent precision errors.

    Args:
        amount: Decimal amount to validate and round

    Returns:
        Decimal rounded to 2 decimal places, or None if input is None

    Examples:
        >>> validate_amount_precision(Decimal("1234.5678"))
        Decimal("1234.57")
        >>> validate_amount_precision(Decimal("100.00"))
        Decimal("100.00")
        >>> validate_amount_precision(None)
        None
    """
    if amount is None:
        return None

    return amount.quantize(Decimal("0.01"))


def validate_risk_score_precision(risk_score: Decimal | None) -> Decimal | None:
    """Validate and round risk score to database precision (2 decimal places).

    This function ensures risk scores are rounded to the correct precision
    before being stored in the database to prevent precision errors.

    Args:
        risk_score: Decimal risk score to validate and round

    Returns:
        Decimal rounded to 2 decimal places, or None if input is None

    Examples:
        >>> validate_risk_score_precision(Decimal("45.6789"))
        Decimal("45.68")
        >>> validate_risk_score_precision(Decimal("50.00"))
        Decimal("50.00")
        >>> validate_risk_score_precision(None)
        None
    """
    if risk_score is None:
        return None

    return risk_score.quantize(Decimal("0.01"))


def validate_banking_data_precision(banking_data: dict[str, Any]) -> dict[str, Any]:
    """Validate and round numeric fields in banking_data to database precision.

    This function ensures all Decimal fields in banking_data are rounded to
    the correct precision before being stored in the database to prevent precision errors.
    Validates total_debt and monthly_obligations to 2 decimal places.

    Args:
        banking_data: Dictionary containing banking data with potential Decimal fields

    Returns:
        Dictionary with Decimal fields rounded to correct precision

    Examples:
        >>> validate_banking_data_precision({"total_debt": Decimal("1234.5678"), "credit_score": 700})
        {"total_debt": Decimal("1234.57"), "credit_score": 700}
    """
    if not banking_data or not isinstance(banking_data, dict):
        return banking_data

    validated = banking_data.copy()

    if 'total_debt' in validated and validated['total_debt'] is not None:
        if isinstance(validated['total_debt'], Decimal):
            validated['total_debt'] = validate_amount_precision(validated['total_debt'])
        elif isinstance(validated['total_debt'], str):
            try:
                debt_decimal = Decimal(validated['total_debt'])
                validated['total_debt'] = str(validate_amount_precision(debt_decimal))
            except (ValueError, TypeError, Exception):
                pass

    if 'monthly_obligations' in validated and validated['monthly_obligations'] is not None:
        if isinstance(validated['monthly_obligations'], Decimal):
            validated['monthly_obligations'] = validate_amount_precision(validated['monthly_obligations'])
        elif isinstance(validated['monthly_obligations'], str):
            try:
                obligations_decimal = Decimal(validated['monthly_obligations'])
                validated['monthly_obligations'] = str(validate_amount_precision(obligations_decimal))
            except (ValueError, TypeError, Exception):
                pass

    return validated


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
