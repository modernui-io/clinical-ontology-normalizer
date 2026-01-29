"""VP-Platform: Redis connection management with async support.

Provides both sync and async Redis clients:
- get_redis(): Sync client for background workers and RQ jobs
- get_async_redis(): Async client for FastAPI endpoints

Usage:
    # Sync (for workers)
    from app.core.redis import get_redis
    redis = get_redis()
    redis.set("key", "value")

    # Async (for API endpoints)
    from app.core.redis import get_async_redis
    redis = await get_async_redis()
    await redis.set("key", "value")
"""

import asyncio
import logging
from typing import Any

from redis import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)

# Sync Redis connection instance (lazy initialized)
_redis_client: Redis | None = None

# Async Redis connection instance (lazy initialized)
_async_redis_client: Any = None


def get_redis() -> Redis:
    """Get or create sync Redis connection.

    Returns a Redis client configured from settings.
    Connection is lazily created on first call.

    Use for background workers and RQ jobs.

    Returns:
        Redis client instance.
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
    return _redis_client


async def get_async_redis() -> Any:
    """Get or create async Redis connection.

    VP-Platform: Added async Redis support for FastAPI endpoints.
    Returns an async Redis client for use in async contexts.

    Usage:
        redis = await get_async_redis()
        await redis.set("key", "value")
        value = await redis.get("key")

    Returns:
        Async Redis client instance.

    Raises:
        ImportError: If redis[asyncio] is not installed.
    """
    global _async_redis_client

    if _async_redis_client is None:
        try:
            from redis.asyncio import Redis as AsyncRedis

            _async_redis_client = AsyncRedis.from_url(
                settings.redis_url,
                decode_responses=True,
            )
            logger.info("Async Redis client initialized")
        except ImportError:
            raise ImportError(
                "redis[asyncio] not installed. Install with: pip install redis[asyncio]"
            )

    return _async_redis_client


def close_redis() -> None:
    """Close sync Redis connection.

    Should be called during application shutdown.
    """
    global _redis_client
    if _redis_client is not None:
        _redis_client.close()
        _redis_client = None
        logger.debug("Sync Redis connection closed")


async def close_async_redis() -> None:
    """Close async Redis connection.

    VP-Platform: Should be called during application shutdown.
    """
    global _async_redis_client
    if _async_redis_client is not None:
        await _async_redis_client.close()
        _async_redis_client = None
        logger.debug("Async Redis connection closed")


def ping_redis() -> bool:
    """Check if sync Redis connection is healthy.

    VP-DevOps-4: Added logging for connection failures.

    Returns:
        True if Redis responds to ping, False otherwise.
    """
    try:
        result = get_redis().ping()
        if result:
            logger.debug("Sync Redis health check passed")
        return bool(result)
    except Exception as e:
        logger.warning(
            "Sync Redis health check failed",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "redis_url": _mask_redis_url(settings.redis_url),
            },
        )
        return False


async def ping_async_redis() -> bool:
    """Check if async Redis connection is healthy.

    VP-Platform: Async version of ping_redis.
    VP-DevOps-4: Added logging for connection failures.

    Returns:
        True if Redis responds to ping, False otherwise.
    """
    try:
        redis = await get_async_redis()
        result = await redis.ping()
        if result:
            logger.debug("Async Redis health check passed")
        return bool(result)
    except Exception as e:
        logger.warning(
            "Async Redis health check failed",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "redis_url": _mask_redis_url(settings.redis_url),
            },
        )
        return False


def _mask_redis_url(url: str) -> str:
    """Mask password in Redis URL for safe logging."""
    # Parse and mask password if present
    if "@" in url:
        # redis://user:password@host:port/db -> redis://user:***@host:port/db
        import re
        return re.sub(r":([^:@]+)@", r":***@", url)
    return url


class AsyncRedisCache:
    """VP-Platform: Async Redis cache helper for common patterns.

    Provides convenient methods for caching with expiration.

    Usage:
        cache = AsyncRedisCache(prefix="myapp")
        await cache.set("user:123", {"name": "John"}, ttl=3600)
        user = await cache.get("user:123")
    """

    def __init__(self, prefix: str = "", default_ttl: int = 3600):
        """Initialize cache helper.

        Args:
            prefix: Key prefix for namespacing.
            default_ttl: Default TTL in seconds.
        """
        self.prefix = prefix
        self.default_ttl = default_ttl
        self._redis: Any = None

    async def _get_redis(self) -> Any:
        """Get or cache Redis connection."""
        if self._redis is None:
            self._redis = await get_async_redis()
        return self._redis

    def _make_key(self, key: str) -> str:
        """Create prefixed key."""
        if self.prefix:
            return f"{self.prefix}:{key}"
        return key

    async def get(self, key: str) -> str | None:
        """Get a value from cache.

        Args:
            key: Cache key.

        Returns:
            Cached value or None if not found.
        """
        redis = await self._get_redis()
        return await redis.get(self._make_key(key))

    async def set(
        self,
        key: str,
        value: str,
        ttl: int | None = None,
    ) -> bool:
        """Set a value in cache.

        Args:
            key: Cache key.
            value: Value to cache.
            ttl: Time-to-live in seconds (uses default if not specified).

        Returns:
            True if set successfully.
        """
        redis = await self._get_redis()
        ttl = ttl or self.default_ttl
        result = await redis.setex(self._make_key(key), ttl, value)
        return bool(result)

    async def delete(self, key: str) -> bool:
        """Delete a value from cache.

        Args:
            key: Cache key.

        Returns:
            True if deleted successfully.
        """
        redis = await self._get_redis()
        result = await redis.delete(self._make_key(key))
        return bool(result)

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache.

        Args:
            key: Cache key.

        Returns:
            True if key exists.
        """
        redis = await self._get_redis()
        return bool(await redis.exists(self._make_key(key)))

    async def get_json(self, key: str) -> dict | list | None:
        """Get a JSON value from cache.

        Args:
            key: Cache key.

        Returns:
            Parsed JSON value or None if not found.
        """
        import json

        value = await self.get(key)
        if value:
            return json.loads(value)
        return None

    async def set_json(
        self,
        key: str,
        value: dict | list,
        ttl: int | None = None,
    ) -> bool:
        """Set a JSON value in cache.

        Args:
            key: Cache key.
            value: Value to cache (will be serialized to JSON).
            ttl: Time-to-live in seconds.

        Returns:
            True if set successfully.
        """
        import json

        return await self.set(key, json.dumps(value), ttl)
