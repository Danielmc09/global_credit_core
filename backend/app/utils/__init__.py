"""Utility functions organized by domain.

For backward compatibility, all functions are re-exported here.
However, prefer importing from specific modules for better clarity:
    from app.utils.formatting import format_datetime
    from app.utils.strings import mask_document
    from app.utils.generators import generate_request_id
"""

# Converters
from .converters import (
    decimal_to_string,
    normalize_path,
    safe_json_dumps,
    safe_json_loads,
)

# Formatting
from .formatting import calculate_age, format_currency, format_datetime, parse_datetime

# Generators
from .generators import generate_cache_key, generate_request_id

# Strings
from .strings import mask_document, sanitize_log_data, sanitize_string, truncate_string

# Validators
from .validators import (
    validate_amount_precision,
    validate_banking_data_precision,
    validate_risk_score_precision,
    validate_uuid,
)

__all__ = [
    # Converters
    "decimal_to_string",
    "safe_json_loads",
    "safe_json_dumps",
    "normalize_path",
    # Formatting
    "format_datetime",
    "parse_datetime",
    "calculate_age",
    "format_currency",
    # Generators
    "generate_request_id",
    "generate_cache_key",
    # Strings
    "mask_document",
    "sanitize_string",
    "truncate_string",
    "sanitize_log_data",
    # Validators
    "validate_uuid",
    "validate_amount_precision",
    "validate_risk_score_precision",
    "validate_banking_data_precision",
]
