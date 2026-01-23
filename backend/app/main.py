from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from .api.v1.endpoints import metrics as metrics_endpoint
from .api.v1.router import api_router
from .core.config import settings
from .core.constants import ApiEndpoints, HttpHeaders
from .core.logging import get_logger, setup_logging
from .core.openapi import get_custom_openapi
from .core.startup import create_lifespan
from .infrastructure.security import get_rate_limit_key
from .middleware.payload_size import PayloadSizeMiddleware
from .middleware.prometheus import PrometheusMiddleware
from .middleware.request_id import RequestIDMiddleware

setup_logging()
logger = get_logger(__name__)

limiter = Limiter(key_func=get_rate_limit_key)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Multi-country credit application system with async processing",
    lifespan=create_lifespan(),
    docs_url=ApiEndpoints.DOCS,
    redoc_url=ApiEndpoints.REDOC,
    openapi_url=ApiEndpoints.OPENAPI
)

app.openapi = get_custom_openapi(app)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        HttpHeaders.AUTHORIZATION,
        HttpHeaders.CONTENT_TYPE,
        HttpHeaders.ACCEPT,
        HttpHeaders.REQUEST_ID,
        HttpHeaders.WEBHOOK_SIGNATURE,
        HttpHeaders.CONTENT_LENGTH,
    ],
)

app.add_middleware(PayloadSizeMiddleware)

app.add_middleware(PrometheusMiddleware)

app.add_middleware(RequestIDMiddleware)
# Include API routes
app.include_router(
    api_router,
    prefix=settings.API_V1_PREFIX
)

app.include_router(metrics_endpoint.router, tags=["Metrics"])


@app.get(ApiEndpoints.HEALTH, tags=["Health"])
async def health_check():
    """Health check endpoint for Kubernetes readiness/liveness probes."""
    return {
        "status": "healthy",
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }


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
