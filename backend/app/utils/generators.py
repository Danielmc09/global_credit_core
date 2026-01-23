"""ID and key generation utilities."""

import uuid
from typing import Any


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
