"""Global Credit Core - Main Application.

Multi-country credit application system with async processing,
real-time updates, and extensible architecture.
"""

import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .api.v1.endpoints import metrics as metrics_endpoint
from .api.v1.router import api_router
from .core.config import settings
from .core.constants import (
    ApiEndpoints,
    ErrorMessages,
    HttpHeaders,
)
from .core.logging import get_logger, set_request_id, setup_logging
from .core.metrics import set_app_info
from .core.tracing import setup_tracing
from .core.rate_limiting import get_rate_limit_key
from .middleware.payload_size import PayloadSizeMiddleware
from .middleware.prometheus import PrometheusMiddleware
from .services.websocket_service import redis_subscriber

# Setup logging
setup_logging()
logger = get_logger(__name__)

# Setup rate limiting (protection against abuse)
# Uses IP + user_id combination for better control (prevents bypassing limits with different IPs)
limiter = Limiter(key_func=get_rate_limit_key)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    logger.info(
        "Application starting",
        extra={
            'environment': settings.ENVIRONMENT,
            'version': settings.APP_VERSION
        }
    )

    # Initialize Prometheus metrics
    set_app_info(
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT
    )
    logger.debug("Prometheus metrics initialized")

    # Initialize distributed tracing
    setup_tracing()
    logger.debug("Distributed tracing initialized")

    # Start Redis subscriber for WebSocket broadcasts (cross-process communication)
    subscriber_task = asyncio.create_task(redis_subscriber())
    logger.debug("Redis subscriber started for WebSocket cross-process communication")

    yield

    # Shutdown
    logger.info("Application shutting down")

    # Cancel Redis subscriber task
    subscriber_task.cancel()
    try:
        await subscriber_task
    except asyncio.CancelledError:
        logger.debug("Redis subscriber task cancelled")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Multi-country credit application system with async processing",
    lifespan=lifespan,
    docs_url=ApiEndpoints.DOCS,
    redoc_url=ApiEndpoints.REDOC,
    openapi_url=ApiEndpoints.OPENAPI
)

# Override OpenAPI schema to add security configuration
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = app.openapi()
    openapi_schema["info"]["description"] = """
Multi-country credit application system with async processing.

## Authentication

This API uses JWT (JSON Web Tokens) for authentication. To use protected endpoints:

1. Obtain a JWT token (see `/docs` for authentication endpoint or check `docs/authentication.md`)
2. Click the **"Authorize"** button above
3. Enter your token in the format: `Bearer <your-token>`
4. All authenticated requests will include the token in the Authorization header

## Security

- **JWT Tokens**: Required for most endpoints (except health check and docs)
- **Admin Role**: Required for PATCH and DELETE operations on applications
- **Webhook Signatures**: Required for webhook endpoints (HMAC-SHA256)

For more details, see `docs/authentication.md`
    """
    openapi_schema["components"] = {
        "securitySchemes": {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "Enter your JWT token. Format: Bearer <token>"
            }
        }
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Add rate limiter to app state (SECURITY: Protection against API abuse)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "X-Request-ID",
        "X-Webhook-Signature",
        "Content-Length",
    ],
)

# Payload size validation middleware (SECURITY: Prevent DoS attacks with large payloads)
# Must be added before Prometheus middleware to reject oversized requests early
app.add_middleware(PayloadSizeMiddleware)

# Prometheus metrics middleware
app.add_middleware(PrometheusMiddleware)


# Request ID middleware (for observability - Requirement 4.3)
@app.middleware("http")
async def add_request_id_middleware(request: Request, call_next):
    """Middleware to add request_id to all requests for traceability.

    The request_id is:
    1. Generated for each request
    2. Stored in context var (accessible in all logs)
    3. Returned in response headers
    """
    # Generate and set request ID
    request_id = set_request_id()

    # Log request
    logger.info(
        "Request started",
        extra={
            'method': request.method,
            'path': request.url.path,
            'client': request.client.host if request.client else 'unknown'
        }
    )

    # Process request
    start_time = time.time()

    try:
        response = await call_next(request)

        # Calculate processing time
        process_time = time.time() - start_time

        # Add custom headers
        response.headers[HttpHeaders.REQUEST_ID] = request_id
        response.headers[HttpHeaders.PROCESS_TIME] = str(process_time)

        # Log response
        logger.info(
            "Request completed",
            extra={
                'status_code': response.status_code,
                'process_time': process_time
            }
        )

        return response

    except Exception as e:
        process_time = time.time() - start_time

        logger.error(
            "Request failed",
            extra={
                'error': str(e),
                'process_time': process_time
            },
            exc_info=True
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": ErrorMessages.INTERNAL_SERVER_ERROR,
                "request_id": request_id
            },
            headers={HttpHeaders.REQUEST_ID: request_id}
        )


# Include API routes
app.include_router(
    api_router,
    prefix=settings.API_V1_PREFIX
)

# Prometheus metrics endpoint
app.include_router(metrics_endpoint.router, tags=["Metrics"])


# Health check endpoint
@app.get(ApiEndpoints.HEALTH, tags=["Health"])
async def health_check():
    """Health check endpoint for Kubernetes readiness/liveness probes."""
    return {
        "status": "healthy",
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }


# Root endpoint
@app.get(ApiEndpoints.ROOT, tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": ApiEndpoints.DOCS,
        "health": ApiEndpoints.HEALTH,
        "api": settings.API_V1_PREFIX
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
