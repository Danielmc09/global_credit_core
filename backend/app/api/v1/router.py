"""API v1 Router.

Aggregates all v1 endpoints.
"""

from fastapi import APIRouter

from .endpoints import applications, auth, webhooks, websocket

api_router = APIRouter()

# Include application endpoints
api_router.include_router(
    applications.router,
    prefix="/applications",
    tags=["Applications"]
)

# Include webhook endpoints
api_router.include_router(
    webhooks.router,
    prefix="/webhooks",
    tags=["Webhooks"]
)

# Include WebSocket endpoints
api_router.include_router(
    websocket.router,
    tags=["WebSocket"]
)

# Include authentication endpoints
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"]
)
