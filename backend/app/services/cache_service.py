"""Cache Service.

Redis-based caching layer for improving response times (Requirement 4.7).
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import redis.asyncio as aioredis
from redis.exceptions import (
    ConnectionError as RedisConnectionError,
    TimeoutError as RedisTimeoutError,
)

from ..core.config import settings
from ..core.constants import Cache, Pagination
from ..core.logging import get_logger
from ..core.metrics import (
    cache_connection_status,
    cache_errors_total,
    cache_operations_total,
)
from ..utils import generate_cache_key, safe_json_dumps, safe_json_loads

logger = get_logger(__name__)


class CacheService:
    """Redis cache service for application data.

    Caching strategy:
    - Application reads: Cache individual applications (5 min TTL)
    - List queries: Cache paginated results (2 min TTL)
    - Statistics: Cache country stats (10 min TTL)
    - Invalidation: On create/update/delete operations
    
    Error handling:
    - Tracks connection errors separately from other errors
    - Records metrics for monitoring and alerting
    - Gracefully degrades when Redis is unavailable
    """

    def __init__(self):
        self.redis: aioredis.Redis | None = None
        self._connected = False
        self._consecutive_failures = 0
        self._max_consecutive_failures = 5

    async def connect(self):
        """Establish Redis connection."""
        if not self._connected:
            try:
                self.redis = await aioredis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True
                )
                await self.redis.ping()
                self._connected = True
                self._consecutive_failures = 0
                cache_connection_status.set(1)
                logger.info("Cache service connected to Redis")
            except Exception as e:
                self._connected = False
                cache_connection_status.set(0)
                error_type = self._classify_error(e)
                cache_errors_total.labels(
                    operation='connect',
                    error_type=error_type
                ).inc()
                logger.warning(
                    "Failed to connect to Redis",
                    extra={'error': str(e), 'error_type': error_type},
                    exc_info=True
                )
                raise

    async def disconnect(self):
        """Close Redis connection."""
        if self.redis and self._connected:
            try:
                await self.redis.close()
                self._connected = False
                cache_connection_status.set(0)
                logger.debug("Cache service disconnected from Redis")
            except Exception as e:
                logger.warning(
                    "Error disconnecting from Redis",
                    extra={'error': str(e)},
                    exc_info=True
                )
                self._connected = False
                cache_connection_status.set(0)

    def _classify_error(self, error: Exception) -> str:
        """Classify error type for metrics and alerting.
        
        Args:
            error: Exception to classify
            
        Returns:
            Error type: 'connection', 'timeout', or 'other'
        """
        if isinstance(error, (RedisConnectionError, ConnectionError)):
            return 'connection'
        elif isinstance(error, (RedisTimeoutError, TimeoutError, asyncio.TimeoutError)):
            return 'timeout'
        else:
            return 'other'
    
    def _handle_cache_error(
        self,
        operation: str,
        error: Exception,
        key: str | None = None,
        pattern: str | None = None
    ) -> None:
        """Handle cache errors with metrics and logging.
        
        Args:
            operation: Operation name (get, set, delete, delete_pattern)
            error: Exception that occurred
            key: Cache key (if applicable)
            pattern: Cache pattern (if applicable)
        """
        error_type = self._classify_error(error)
        self._consecutive_failures += 1
        
        cache_errors_total.labels(
            operation=operation,
            error_type=error_type
        ).inc()
        cache_operations_total.labels(
            operation=operation,
            status='failure'
        ).inc()
        
        if error_type == 'connection':
            self._connected = False
            cache_connection_status.set(0)
        
        extra = {
            'error': str(error),
            'error_type': error_type,
            'operation': operation,
            'consecutive_failures': self._consecutive_failures
        }
        if key:
            extra['key'] = key
        if pattern:
            extra['pattern'] = pattern
        
        if error_type in ('connection', 'timeout'):
            log_level = logger.warning
            if self._consecutive_failures >= self._max_consecutive_failures:
                log_level = logger.error
        else:
            log_level = logger.error
        
        log_level(
            f"Cache {operation} error",
            extra=extra,
            exc_info=True
        )
        
        if self._consecutive_failures >= self._max_consecutive_failures:
            logger.error(
                f"Cache service has exceeded failure threshold ({self._max_consecutive_failures} consecutive failures). "
                "Redis may be unavailable. System will continue without cache.",
                extra={
                    'consecutive_failures': self._consecutive_failures,
                    'error_type': error_type
                }
            )

    async def get(self, key: str) -> Any | None:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found or on error
        """
        if not self._connected:
            try:
                await self.connect()
            except Exception:
                return None

        try:
            value = await self.redis.get(key)
            self._consecutive_failures = 0
            cache_operations_total.labels(operation='get', status='success').inc()

            if value:
                logger.debug(
                    "Cache hit",
                    extra={'key': key}
                )
                return safe_json_loads(value)

            logger.debug(
                "Cache miss",
                extra={'key': key}
            )
            return None

        except Exception as e:
            self._handle_cache_error('get', e, key=key)
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None
    ):
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time to live in seconds (default 5 minutes)
        """
        if ttl is None:
            ttl = Cache.DEFAULT_TTL_SECONDS
            
        if not self._connected:
            try:
                await self.connect()
            except Exception:
                return

        try:
            serialized = safe_json_dumps(value)
            await self.redis.setex(
                key,
                ttl,
                serialized
            )
            self._consecutive_failures = 0
            cache_operations_total.labels(operation='set', status='success').inc()

            logger.debug(
                "Cache set",
                extra={'key': key, 'ttl': ttl}
            )

        except Exception as e:
            self._handle_cache_error('set', e, key=key)

    async def delete(self, key: str):
        """Delete value from cache.

        Args:
            key: Cache key
        """
        if not self._connected:
            try:
                await self.connect()
            except Exception:
                return

        try:
            await self.redis.delete(key)
            self._consecutive_failures = 0
            cache_operations_total.labels(operation='delete', status='success').inc()

            logger.debug(
                "Cache deleted",
                extra={'key': key}
            )

        except Exception as e:
            self._handle_cache_error('delete', e, key=key)

    async def delete_pattern(self, pattern: str):
        """Delete all keys matching a pattern.

        Args:
            pattern: Redis key pattern (e.g., "application:*")
        """
        if not self._connected:
            try:
                await self.connect()
            except Exception:
                return

        try:
            keys = []
            async for key in self.redis.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                await self.redis.delete(*keys)

            self._consecutive_failures = 0
            cache_operations_total.labels(operation='delete_pattern', status='success').inc()

            logger.info(
                "Cache pattern deleted",
                extra={'pattern': pattern, 'count': len(keys)}
            )

        except Exception as e:
            self._handle_cache_error('delete_pattern', e, pattern=pattern)

    async def invalidate_application(self, application_id: str):
        """Invalidate all cache entries related to an application.

        This is called when an application is created/updated/deleted.

        Args:
            application_id: Application UUID
        """
        await self.delete(application_key(application_id))

        await self.delete_pattern("applications:list:*")

        await self.delete_pattern("stats:*")

        logger.info(
            "Application cache invalidated",
            extra={'application_id': application_id}
        )

    async def get_country_stats_cached(
        self,
        country: str,
        fetch_fn: Callable[[], Awaitable[dict[str, Any]]]
    ) -> dict[str, Any]:
        """Get country statistics with caching.

        First checks cache, if not found, calls fetch_fn to get data,
        stores it in cache with 5 minute TTL, and returns it.

        Args:
            country: Country code
            fetch_fn: Async function that returns country statistics dict

        Returns:
            Dictionary with country statistics
        """
        cache_key = country_stats_key(country)

        cached_stats = await self.get(cache_key)
        if cached_stats is not None:
            logger.debug(
                "Country stats cache hit",
                extra={'country': country, 'key': cache_key}
            )
            return cached_stats

        logger.debug(
            "Country stats cache miss, fetching from database",
            extra={'country': country, 'key': cache_key}
        )
        stats = await fetch_fn()

        await self.set(cache_key, stats, ttl=300)

        return stats


cache = CacheService()


def application_key(application_id: str) -> str:
    """Generate cache key for an application."""
    return generate_cache_key("application", application_id)


def applications_list_key(
    country: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = Pagination.DEFAULT_PAGE_SIZE
) -> str:
    """Generate cache key for application list."""
    return generate_cache_key(
        "applications",
        "list",
        country=country or "all",
        status=status or "all",
        page=page,
        page_size=page_size
    )


def country_stats_key(country: str) -> str:
    """Generate cache key for country statistics."""
    return generate_cache_key("stats", "country", country)
