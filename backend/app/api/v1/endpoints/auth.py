"""Authentication Endpoints.

Provides endpoints for JWT token generation for development and testing.
In production, this would typically integrate with a user management system.
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ....core.config import settings
from ....core.logging import get_logger
from ....infrastructure.security import create_access_token

logger = get_logger(__name__)

router = APIRouter()


class TokenRequest(BaseModel):
    """Request model for token generation."""
    
    user_id: str = Field(..., description="User identifier")
    email: str = Field(default="demo@example.com", description="User email")
    role: str = Field(default="user", description="User role (user or admin)")


class TokenResponse(BaseModel):
    """Response model for token generation."""
    
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in minutes")
    user_id: str = Field(..., description="User identifier")
    role: str = Field(..., description="User role")


@router.post(
    "/demo-token",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate Demo JWT Token",
    description="""
    Generate a JWT token for development and testing purposes.
    
    **Note:** This endpoint is for development/testing only. In production,
    tokens should be generated through a proper authentication flow (e.g., login).
    
    **Usage:**
    1. Call this endpoint to get a token
    2. Use the token in the Authorization header: `Bearer <token>`
    3. Token expires after the configured time (default: 60 minutes)
    """,
    tags=["Authentication"],
    responses={
        200: {"description": "Token generated successfully"},
        400: {"description": "Invalid request data"},
    }
)
async def generate_demo_token(request: TokenRequest) -> TokenResponse:
    """Generate a demo JWT token for testing.
    
    This endpoint allows generating JWT tokens for development and testing.
    In a production environment, tokens would be generated through a proper
    authentication flow (e.g., login with username/password).
    
    Args:
        request: Token request with user information
        
    Returns:
        Token response with access token and metadata
        
    Raises:
        HTTPException: If role is invalid
    """
    # Validate role
    if request.role not in ["user", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role: {request.role}. Must be 'user' or 'admin'"
        )
    
    # Generate token
    token_data = {
        "sub": request.user_id,
        "email": request.email,
        "role": request.role
    }
    
    token = create_access_token(
        data=token_data,
        expires_delta=timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)
    )
    
    logger.info(
        "Demo token generated",
        extra={
            "user_id": request.user_id,
            "role": request.role,
            "environment": settings.ENVIRONMENT
        }
    )
    
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRATION_MINUTES,
        user_id=request.user_id,
        role=request.role
    )


@router.get(
    "/demo-token/quick",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Quick Demo Token (User)",
    description="""
    Generate a quick demo token with default user credentials.
    Convenience endpoint for testing with a regular user role.
    """,
    tags=["Authentication"],
    responses={
        200: {"description": "Token generated successfully"},
    }
)
async def generate_quick_demo_token() -> TokenResponse:
    """Generate a quick demo token with default user credentials.
    
    Returns:
        Token response with access token for a default user
    """
    token_data = {
        "sub": "demo-user",
        "email": "demo@example.com",
        "role": "user"
    }
    
    token = create_access_token(
        data=token_data,
        expires_delta=timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)
    )
    
    logger.info(
        "Quick demo token generated",
        extra={"user_id": "demo-user", "role": "user"}
    )
    
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRATION_MINUTES,
        user_id="demo-user",
        role="user"
    )


@router.get(
    "/demo-token/admin",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Quick Demo Token (Admin)",
    description="""
    Generate a quick demo token with admin credentials.
    Convenience endpoint for testing with admin role.
    """,
    tags=["Authentication"],
    responses={
        200: {"description": "Token generated successfully"},
    }
)
async def generate_admin_demo_token() -> TokenResponse:
    """Generate a quick demo token with admin credentials.
    
    Returns:
        Token response with access token for an admin user
    """
    token_data = {
        "sub": "demo-admin",
        "email": "admin@example.com",
        "role": "admin"
    }
    
    token = create_access_token(
        data=token_data,
        expires_delta=timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)
    )
    
    logger.info(
        "Admin demo token generated",
        extra={"user_id": "demo-admin", "role": "admin"}
    )
    
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRATION_MINUTES,
        user_id="demo-admin",
        role="admin"
    )
