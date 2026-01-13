"""Utility Functions Module.

Common utility functions used across the application.
"""

from .helpers import (
    calculate_age,
    decimal_to_string,
    format_currency,
    format_datetime,
    generate_cache_key,
    generate_request_id,
    mask_document,
    normalize_path,
    parse_datetime,
    safe_json_dumps,
    safe_json_loads,
    sanitize_log_data,
    sanitize_string,
    truncate_string,
    validate_uuid,
)

__all__ = [
    "mask_document",
    "generate_request_id",
    "format_datetime",
    "parse_datetime",
    "calculate_age",
    "sanitize_string",
    "sanitize_log_data",
    "validate_uuid",
    "truncate_string",
    "format_currency",
    "generate_cache_key",
    "normalize_path",
    "decimal_to_string",
    "safe_json_loads",
    "safe_json_dumps",
]
