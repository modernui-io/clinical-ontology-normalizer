"""Terminology Operation Caching.

Provides an in-memory TTL cache for terminology operations
(ICD-10 lookups, CPT searches, drug safety queries, etc.)
to reduce repeated computation on common queries.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class CacheEntry:
    """A cached value with TTL tracking."""

    value: Any
    created_at: float
    ttl_seconds: float
    hits: int = 0

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl_seconds


class TerminologyCache:
    """Thread-safe TTL cache for terminology operations.

    Features:
    - Configurable max size with LRU eviction
    - Per-entry TTL with automatic expiration
    - Thread-safe operations
    - Cache statistics for monitoring
    """

    def __init__(self, max_size: int = 1000, default_ttl: float = 300.0):
        """Initialize the cache.

        Args:
            max_size: Maximum number of entries before LRU eviction.
            default_ttl: Default time-to-live in seconds (5 minutes).
        """
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._hits = 0
        self._misses = 0

    def _make_key(self, namespace: str, *args: Any, **kwargs: Any) -> str:
        """Generate a deterministic cache key from arguments."""
        key_data = json.dumps(
            {"ns": namespace, "args": args, "kwargs": sorted(kwargs.items())},
            sort_keys=True,
            default=str,
        )
        return hashlib.md5(key_data.encode()).hexdigest()

    def get(self, key: str) -> Any | None:
        """Get a value from cache, or None if expired/missing."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None
            if entry.is_expired:
                del self._cache[key]
                self._misses += 1
                return None
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.hits += 1
            self._hits += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Store a value in the cache."""
        with self._lock:
            # Evict if at max size
            while len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
            self._cache[key] = CacheEntry(
                value=value,
                created_at=time.time(),
                ttl_seconds=ttl if ttl is not None else self._default_ttl,
            )

    def invalidate(self, key: str) -> None:
        """Remove a specific entry."""
        with self._lock:
            self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(self._hits / total, 3) if total > 0 else 0.0,
                "default_ttl_seconds": self._default_ttl,
            }


def cached_operation(
    cache: "TerminologyCache",
    operation: str,
    ttl: float | None = None,
) -> Callable:
    """Decorator that caches the result of a terminology operation.

    Usage:
        @cached_operation(get_icd10_cache(), "lookup", ttl=3600)
        def lookup_code(system: str, code: str) -> dict:
            ...

    Args:
        cache: The TerminologyCache instance to use.
        operation: Operation name for key generation.
        ttl: Optional TTL override in seconds.

    Returns:
        Decorator function.
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        import functools

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            key = cache._make_key(operation, *args, **kwargs)
            cached = cache.get(key)
            if cached is not None:
                return cached
            result = func(*args, **kwargs)
            if result is not None:
                cache.set(key, result, ttl=ttl)
            return result

        # Expose cache invalidation
        wrapper.invalidate_cache = lambda: cache.clear()  # type: ignore[attr-defined]
        wrapper.cache = cache  # type: ignore[attr-defined]
        return wrapper

    return decorator


# Global cache instances for each terminology service
_icd10_cache = TerminologyCache(max_size=2000, default_ttl=600.0)  # 10 min TTL
_cpt_cache = TerminologyCache(max_size=1000, default_ttl=600.0)
_drug_cache = TerminologyCache(max_size=500, default_ttl=600.0)
_hcc_cache = TerminologyCache(max_size=500, default_ttl=600.0)
_differential_cache = TerminologyCache(max_size=200, default_ttl=300.0)  # 5 min TTL
_fhir_operation_cache = TerminologyCache(max_size=2000, default_ttl=3600.0)  # 1 hour TTL


def get_icd10_cache() -> TerminologyCache:
    """Get the ICD-10 terminology cache."""
    return _icd10_cache


def get_cpt_cache() -> TerminologyCache:
    """Get the CPT terminology cache."""
    return _cpt_cache


def get_drug_cache() -> TerminologyCache:
    """Get the drug safety cache."""
    return _drug_cache


def get_hcc_cache() -> TerminologyCache:
    """Get the HCC analysis cache."""
    return _hcc_cache


def get_differential_cache() -> TerminologyCache:
    """Get the differential diagnosis cache."""
    return _differential_cache


def get_fhir_operation_cache() -> TerminologyCache:
    """Get the FHIR terminology operation cache."""
    return _fhir_operation_cache


def get_all_cache_stats() -> dict[str, Any]:
    """Get statistics for all terminology caches."""
    return {
        "icd10": _icd10_cache.get_stats(),
        "cpt": _cpt_cache.get_stats(),
        "drug_safety": _drug_cache.get_stats(),
        "hcc": _hcc_cache.get_stats(),
        "differential": _differential_cache.get_stats(),
        "fhir_operations": _fhir_operation_cache.get_stats(),
    }


def clear_all_caches() -> None:
    """Clear all terminology caches (also used for vocabulary reload invalidation)."""
    _icd10_cache.clear()
    _cpt_cache.clear()
    _drug_cache.clear()
    _hcc_cache.clear()
    _differential_cache.clear()
    _fhir_operation_cache.clear()


# =============================================================================
# Redis-based Terminology Cache for FHIR Operations
# =============================================================================

# Default TTL per operation type (seconds)
OPERATION_TTL = {
    "lookup": 3600,        # 1 hour
    "validate-code": 3600, # 1 hour
    "expand": 1800,        # 30 minutes
    "translate": 3600,     # 1 hour
}


class RedisTerminologyCache:
    """Redis-backed cache for FHIR terminology operations.

    Features:
    - Configurable TTL per operation type
    - Cache key generation from operation + parameters
    - Cache invalidation API
    - Fallback to in-memory cache when Redis is unavailable
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0", prefix: str = "term"):
        self._redis_url = redis_url
        self._prefix = prefix
        self._redis = None
        self._fallback = TerminologyCache(max_size=2000, default_ttl=1800.0)
        self._connected = False

    def _get_redis(self):
        """Lazily connect to Redis."""
        if self._redis is None:
            try:
                import redis
                self._redis = redis.from_url(self._redis_url, decode_responses=True)
                self._redis.ping()
                self._connected = True
            except Exception as e:
                logger.warning(f"Redis unavailable, using in-memory fallback: {e}")
                self._connected = False
                self._redis = None
        return self._redis

    def make_key(self, operation: str, **params) -> str:
        """Generate a deterministic cache key from operation and parameters."""
        key_data = json.dumps(
            {"op": operation, "params": sorted(params.items())},
            sort_keys=True,
            default=str,
        )
        key_hash = hashlib.md5(key_data.encode()).hexdigest()
        return f"{self._prefix}:{operation}:{key_hash}"

    def get(self, operation: str, **params) -> Any | None:
        """Get a cached result for an operation."""
        key = self.make_key(operation, **params)
        redis_client = self._get_redis()

        if redis_client and self._connected:
            try:
                cached = redis_client.get(key)
                if cached:
                    return json.loads(cached)
                return None
            except Exception as e:
                logger.warning(f"Redis get error: {e}")

        # Fallback to in-memory
        return self._fallback.get(key)

    def set(self, operation: str, value: Any, **params) -> None:
        """Cache a result for an operation with appropriate TTL."""
        key = self.make_key(operation, **params)
        ttl = OPERATION_TTL.get(operation, 1800)
        redis_client = self._get_redis()

        if redis_client and self._connected:
            try:
                redis_client.setex(key, ttl, json.dumps(value, default=str))
                return
            except Exception as e:
                logger.warning(f"Redis set error: {e}")

        # Fallback to in-memory
        self._fallback.set(key, value, ttl=float(ttl))

    def invalidate(self, operation: str, **params) -> None:
        """Invalidate a specific cached operation result."""
        key = self.make_key(operation, **params)
        redis_client = self._get_redis()

        if redis_client and self._connected:
            try:
                redis_client.delete(key)
            except Exception as e:
                logger.warning(f"Redis invalidate error: {e}")

        self._fallback.invalidate(key)

    def invalidate_operation(self, operation: str) -> int:
        """Invalidate all cached results for a specific operation type.

        Returns the number of keys invalidated.
        """
        pattern = f"{self._prefix}:{operation}:*"
        redis_client = self._get_redis()
        count = 0

        if redis_client and self._connected:
            try:
                cursor = 0
                while True:
                    cursor, keys = redis_client.scan(cursor, match=pattern, count=100)
                    if keys:
                        count += redis_client.delete(*keys)
                    if cursor == 0:
                        break
            except Exception as e:
                logger.warning(f"Redis invalidate_operation error: {e}")

        self._fallback.clear()
        return count

    def clear(self) -> None:
        """Clear all terminology cache entries."""
        pattern = f"{self._prefix}:*"
        redis_client = self._get_redis()

        if redis_client and self._connected:
            try:
                cursor = 0
                while True:
                    cursor, keys = redis_client.scan(cursor, match=pattern, count=100)
                    if keys:
                        redis_client.delete(*keys)
                    if cursor == 0:
                        break
            except Exception as e:
                logger.warning(f"Redis clear error: {e}")

        self._fallback.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        redis_client = self._get_redis()
        stats = {
            "connected": self._connected,
            "backend": "redis" if self._connected else "in-memory",
            "operation_ttls": OPERATION_TTL,
        }

        if redis_client and self._connected:
            try:
                info = redis_client.info("memory")
                stats["redis_memory_used"] = info.get("used_memory_human", "unknown")
            except Exception:
                pass
        else:
            stats.update(self._fallback.get_stats())

        return stats


# Global Redis cache instance
_redis_terminology_cache: RedisTerminologyCache | None = None


def get_redis_terminology_cache() -> RedisTerminologyCache:
    """Get the Redis terminology cache singleton."""
    global _redis_terminology_cache
    if _redis_terminology_cache is None:
        import os
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        _redis_terminology_cache = RedisTerminologyCache(redis_url=redis_url)
    return _redis_terminology_cache


def reset_redis_terminology_cache() -> None:
    """Reset the Redis terminology cache singleton (for testing)."""
    global _redis_terminology_cache
    _redis_terminology_cache = None
