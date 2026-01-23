import arq
from arq.connections import ArqRedis, RedisSettings

from ...core.config import settings
from ...core.logging import get_logger

logger = get_logger(__name__)

# Global ARQ pool for job enqueuing
_arq_pool: ArqRedis | None = None


async def get_arq_pool() -> ArqRedis:
    """Get or create ARQ Redis pool for job enqueuing.
    
    This pool is used by the API to enqueue jobs to the worker queue.
    It's separate from the redis-py client used for Pub/Sub.
    
    Returns:
        ARQ Redis pool with enqueue_job() method
    """
    global _arq_pool
    
    if _arq_pool is None:
        redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
        _arq_pool = await arq.create_pool(redis_settings)
        logger.info("ARQ pool initialized for job enqueuing")
    
    return _arq_pool


async def close_arq_pool():
    """Close the ARQ pool gracefully."""
    global _arq_pool
    
    if _arq_pool is not None:
        await _arq_pool.close()
        _arq_pool = None
        logger.info("ARQ pool closed")
