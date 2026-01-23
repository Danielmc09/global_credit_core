"""FastAPI Dependencies for Authentication and Authorization.

Provides reusable dependencies for protecting endpoints with authentication
and role-based access control.
"""

from fastapi import Depends, HTTPException, status

from ..infrastructure.security import get_current_user
from ..core.logging import get_logger

logger = get_logger(__name__)


async def require_auth(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """Dependency that requires authentication for an endpoint.

    This dependency ensures that the request includes a valid JWT token.
    It extracts the user information from the token and makes it available
    to the endpoint handler.

    Usage:
        @router.get("/protected")
        async def protected_endpoint(
            user: dict = Depends(require_auth)
        ):
            return {"message": f"Hello {user.get('sub')}"}

    Args:
        current_user: User data from JWT token (injected by get_current_user)

    Returns:
        User data dictionary from token payload

    Raises:
        HTTPException: 401 if authentication fails
    """
    return current_user


async def require_admin(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """Dependency that requires admin role for an endpoint.

    This dependency ensures that:
    1. The request includes a valid JWT token (authentication)
    2. The user has the "admin" role (authorization)

    Usage:
        @router.delete("/applications/{id}")
        async def delete_application(
            id: UUID,
            admin_user: dict = Depends(require_admin)
        ):
            # Only admins can delete applications
            ...

    Args:
        current_user: User data from JWT token (injected by get_current_user)

    Returns:
        User data dictionary from token payload

    Raises:
        HTTPException: 401 if authentication fails
        HTTPException: 403 if user is not an admin
    """
    user_role = current_user.get("role")

    if user_role != "admin":
        logger.warning(
            "Unauthorized access attempt - admin required",
            extra={
                "user_id": current_user.get("sub"),
                "user_role": user_role,
                "required_role": "admin"
            }
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required. This operation is restricted to administrators.",
        )

    logger.info(
        "Admin access granted",
        extra={"user_id": current_user.get("sub")}
    )

    return current_user
