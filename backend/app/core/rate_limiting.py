"""Rate Limiting Utilities.

Provides custom key functions for rate limiting that combine IP address
and user_id from JWT tokens for better control and security.
"""

from fastapi import Request
from jose import JWTError, jwt
from slowapi.util import get_remote_address

from .config import settings
from .logging import get_logger

logger = get_logger(__name__)


def get_rate_limit_key(request: Request) -> str:
    """Get rate limiting key combining IP address and user_id from JWT token.

    This function provides better rate limiting control by:
    1. Extracting user_id from JWT token if available
    2. Combining IP address + user_id for authenticated requests
    3. Falling back to IP address only for unauthenticated requests

    This prevents users from bypassing rate limits by using different IPs,
    as the rate limit is applied per user_id regardless of IP address.

    Args:
        request: FastAPI Request object

    Returns:
        Rate limiting key string in format:
        - "ip:<ip_address>:user:<user_id>" for authenticated requests
        - "ip:<ip_address>" for unauthenticated requests
    """
    ip_address = get_remote_address(request)
    user_id = _extract_user_id_from_request(request)

    if user_id:
        key = f"ip:{ip_address}:user:{user_id}"
        logger.debug(
            "Rate limit key with user_id",
            extra={"ip": ip_address, "user_id": user_id}
        )
        return key

    key = f"ip:{ip_address}"
    logger.debug(
        "Rate limit key (IP only)",
        extra={"ip": ip_address}
    )
    return key


def _extract_user_id_from_request(request: Request) -> str | None:
    """Extract user_id from JWT token in Authorization header.

    This function attempts to extract and validate the JWT token from
    the Authorization header without raising exceptions, as rate limiting
    should work even if token validation fails (we just won't use user_id).

    Args:
        request: FastAPI Request object

    Returns:
        user_id string if token is valid and contains 'sub' field, None otherwise
    """
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None

        token = parts[1]

        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_signature": True}
            )
        except JWTError:
            return None

        user_id = payload.get("sub")
        return user_id if user_id else None

    except Exception as e:
        logger.debug(
            "Failed to extract user_id for rate limiting",
            extra={"error": str(e)}
        )
        return None
