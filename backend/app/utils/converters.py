"""Type conversion utilities."""

import json
import re
from decimal import Decimal
from typing import Any


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
