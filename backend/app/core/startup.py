import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import settings
from .logging import get_logger
from ..infrastructure.monitoring.metrics import set_app_info
from ..infrastructure.monitoring import setup_tracing
from ..infrastructure.messaging import start_notification_bridge, get_redis_client
from ..infrastructure.messaging.arq_pool import get_arq_pool, close_arq_pool

logger = get_logger(__name__)


def create_lifespan():
    """Create lifespan context manager for FastAPI application.
    
    This function returns a lifespan context manager that handles:
    - Startup: Initialize services (Prometheus, tracing, Redis, notification bridge)
    - Shutdown: Clean up resources (close Redis, cancel tasks)
    
    Returns:
        Lifespan context manager for FastAPI
    """
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Lifespan context manager for startup and shutdown events."""
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

        # Initialize Redis client for Pub/Sub and store in app state
        app.state.redis = await get_redis_client()
        logger.debug("Redis Pub/Sub client initialized and stored in app state")
        
        # Initialize ARQ pool for job enqueuing
        app.state.arq_pool = await get_arq_pool()
        logger.debug("ARQ pool initialized for job enqueuing")

        # Start notification bridge (Redis Pub/Sub → WebSocket)
        subscriber_task = asyncio.create_task(start_notification_bridge())
        logger.debug("Notification bridge started (Redis Pub/Sub → WebSocket)")

        yield

        logger.info("Application shutting down")
        
        # Close ARQ pool
        if hasattr(app.state, 'arq_pool') and app.state.arq_pool:
            try:
                await close_arq_pool()
                logger.debug("ARQ pool closed")
            except Exception as e:
                logger.warning(f"Error closing ARQ pool: {e}")

        # Close Redis Pub/Sub connection
        if hasattr(app.state, 'redis') and app.state.redis:
            try:
                await app.state.redis.close()
                logger.debug("Redis Pub/Sub connection closed")
            except Exception as e:
                logger.warning(f"Error closing Redis connection: {e}")

        # Cancel notification bridge task
        subscriber_task.cancel()
        try:
            await subscriber_task
            logger.debug("Notification bridge task completed")
        except asyncio.CancelledError:
            logger.debug("Notification bridge task cancelled successfully")
        except Exception as e:
            logger.warning(f"Error during notification bridge shutdown: {e}")
    
    return lifespan
