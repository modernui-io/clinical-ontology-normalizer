"""Caching service for Knowledge Graph queries.

This module provides a multi-tier caching system for KG operations:
- L1 Cache: In-memory LRU cache for hot data (millisecond access)
- L2 Cache: Redis-backed cache for distributed caching (optional)
- Automatic TTL management and cache invalidation
- Query fingerprinting for cache key generation
"""
# MODULE: graph_support
# MATURITY: pilot

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CacheType(str, Enum):
    """Types of cached data."""

    CONCEPT = "concept"
    RELATIONSHIP = "relationship"
    PATH = "path"
    PATIENT_GRAPH = "patient_graph"
    QUERY_RESULT = "query_result"
    EMBEDDING = "embedding"
    BENCHMARK = "benchmark"


@dataclass
class CacheEntry(Generic[T]):
    """A cached entry with metadata."""

    key: str
    value: T
    cache_type: CacheType
    created_at: datetime
    expires_at: datetime
    access_count: int = 0
    last_accessed: datetime | None = None
    size_bytes: int = 0

    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        return datetime.now(timezone.utc) > self.expires_at

    def touch(self) -> None:
        """Update access metadata."""
        self.access_count += 1
        self.last_accessed = datetime.now(timezone.utc)


@dataclass
class CacheConfig:
    """Configuration for the cache service."""

    # L1 (in-memory) cache settings
    l1_max_size: int = 10000  # Max entries
    l1_max_memory_mb: int = 512  # Max memory in MB
    l1_default_ttl_seconds: int = 300  # 5 minutes

    # L2 (Redis) cache settings
    l2_enabled: bool = False
    l2_redis_url: str = "redis://localhost:6379"
    l2_default_ttl_seconds: int = 3600  # 1 hour

    # TTL by cache type (seconds)
    ttl_by_type: dict[CacheType, int] = field(default_factory=lambda: {
        CacheType.CONCEPT: 3600,  # 1 hour (concepts rarely change)
        CacheType.RELATIONSHIP: 1800,  # 30 minutes
        CacheType.PATH: 600,  # 10 minutes (paths can change)
        CacheType.PATIENT_GRAPH: 300,  # 5 minutes (patient data changes)
        CacheType.QUERY_RESULT: 120,  # 2 minutes
        CacheType.EMBEDDING: 7200,  # 2 hours (embeddings are expensive)
        CacheType.BENCHMARK: 86400,  # 24 hours
    })


@dataclass
class CacheStats:
    """Statistics about cache performance."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0
    l1_size: int = 0
    l1_memory_bytes: int = 0
    l2_enabled: bool = False
    l2_hits: int = 0
    l2_misses: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "expirations": self.expirations,
            "hit_rate": round(self.hit_rate, 4),
            "l1_size": self.l1_size,
            "l1_memory_bytes": self.l1_memory_bytes,
            "l2_enabled": self.l2_enabled,
            "l2_hits": self.l2_hits,
            "l2_misses": self.l2_misses,
        }


class LRUCache:
    """Thread-safe LRU cache implementation."""

    def __init__(self, max_size: int = 10000) -> None:
        """Initialize LRU cache."""
        self._cache: OrderedDict[str, CacheEntry[Any]] = OrderedDict()
        self._max_size = max_size
        self._lock = threading.RLock()
        self._memory_bytes = 0

    def get(self, key: str) -> CacheEntry[Any] | None:
        """Get an entry from the cache."""
        with self._lock:
            if key not in self._cache:
                return None

            entry = self._cache[key]
            if entry.is_expired():
                del self._cache[key]
                self._memory_bytes -= entry.size_bytes
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.touch()
            return entry

    def put(
        self,
        key: str,
        value: Any,
        cache_type: CacheType,
        ttl_seconds: int,
    ) -> None:
        """Put an entry in the cache."""
        now = datetime.now(timezone.utc)

        # Estimate size
        size_bytes = len(json.dumps(value, default=str).encode("utf-8"))

        entry = CacheEntry(
            key=key,
            value=value,
            cache_type=cache_type,
            created_at=now,
            expires_at=datetime.fromtimestamp(
                now.timestamp() + ttl_seconds, tz=timezone.utc
            ),
            size_bytes=size_bytes,
        )

        with self._lock:
            # Remove existing entry if present
            if key in self._cache:
                old_entry = self._cache.pop(key)
                self._memory_bytes -= old_entry.size_bytes

            # Evict if at capacity
            while len(self._cache) >= self._max_size:
                _, evicted = self._cache.popitem(last=False)
                self._memory_bytes -= evicted.size_bytes

            self._cache[key] = entry
            self._memory_bytes += size_bytes

    def delete(self, key: str) -> bool:
        """Delete an entry from the cache."""
        with self._lock:
            if key in self._cache:
                entry = self._cache.pop(key)
                self._memory_bytes -= entry.size_bytes
                return True
            return False

    def clear(self) -> int:
        """Clear all entries from the cache."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._memory_bytes = 0
            return count

    def clear_by_type(self, cache_type: CacheType) -> int:
        """Clear all entries of a specific type."""
        with self._lock:
            keys_to_delete = [
                k for k, v in self._cache.items()
                if v.cache_type == cache_type
            ]
            for key in keys_to_delete:
                entry = self._cache.pop(key)
                self._memory_bytes -= entry.size_bytes
            return len(keys_to_delete)

    def cleanup_expired(self) -> int:
        """Remove all expired entries."""
        with self._lock:
            expired_keys = [
                k for k, v in self._cache.items()
                if v.is_expired()
            ]
            for key in expired_keys:
                entry = self._cache.pop(key)
                self._memory_bytes -= entry.size_bytes
            return len(expired_keys)

    @property
    def size(self) -> int:
        """Get current cache size."""
        return len(self._cache)

    @property
    def memory_bytes(self) -> int:
        """Get current memory usage."""
        return self._memory_bytes


class KGCacheService:
    """Knowledge Graph caching service.

    Provides multi-tier caching for KG queries with automatic TTL management,
    cache invalidation, and statistics tracking.
    """

    def __init__(self, config: CacheConfig | None = None) -> None:
        """Initialize the cache service."""
        self._config = config or CacheConfig()
        self._l1_cache = LRUCache(max_size=self._config.l1_max_size)
        self._stats = CacheStats()
        self._redis_client: Any = None

        # Try to connect to Redis if enabled
        if self._config.l2_enabled:
            try:
                import redis
                self._redis_client = redis.from_url(self._config.l2_redis_url)
                self._redis_client.ping()
                self._stats.l2_enabled = True
                logger.info("Redis cache connected")
            except Exception as e:
                logger.warning(f"Redis connection failed, L2 cache disabled: {e}")
                self._stats.l2_enabled = False

    def _generate_key(
        self,
        cache_type: CacheType,
        identifier: str,
        params: dict[str, Any] | None = None,
    ) -> str:
        """Generate a cache key from type, identifier, and parameters."""
        key_parts = [cache_type.value, identifier]
        if params:
            # Sort params for consistent key generation
            param_str = json.dumps(params, sort_keys=True, default=str)
            param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]
            key_parts.append(param_hash)
        return ":".join(key_parts)

    def get(
        self,
        cache_type: CacheType,
        identifier: str,
        params: dict[str, Any] | None = None,
    ) -> Any | None:
        """Get a value from the cache.

        Args:
            cache_type: Type of cached data
            identifier: Primary identifier (e.g., CUI, patient_id)
            params: Additional parameters for the query

        Returns:
            Cached value or None if not found/expired
        """
        key = self._generate_key(cache_type, identifier, params)

        # Try L1 cache first
        entry = self._l1_cache.get(key)
        if entry is not None:
            self._stats.hits += 1
            return entry.value

        # Try L2 cache if enabled
        if self._stats.l2_enabled and self._redis_client:
            try:
                redis_key = f"kg:{key}"
                value = self._redis_client.get(redis_key)
                if value:
                    self._stats.l2_hits += 1
                    self._stats.hits += 1
                    # Deserialize and promote to L1
                    result = json.loads(value)
                    ttl = self._get_ttl(cache_type)
                    self._l1_cache.put(key, result, cache_type, ttl)
                    return result
                self._stats.l2_misses += 1
            except Exception as e:
                logger.warning(f"Redis get failed: {e}")

        self._stats.misses += 1
        return None

    def put(
        self,
        cache_type: CacheType,
        identifier: str,
        value: Any,
        params: dict[str, Any] | None = None,
        ttl_seconds: int | None = None,
    ) -> None:
        """Put a value in the cache.

        Args:
            cache_type: Type of cached data
            identifier: Primary identifier
            value: Value to cache
            params: Additional parameters used in the query
            ttl_seconds: Optional TTL override
        """
        key = self._generate_key(cache_type, identifier, params)
        ttl = ttl_seconds or self._get_ttl(cache_type)

        # Store in L1
        self._l1_cache.put(key, value, cache_type, ttl)

        # Store in L2 if enabled
        if self._stats.l2_enabled and self._redis_client:
            try:
                redis_key = f"kg:{key}"
                self._redis_client.setex(
                    redis_key,
                    ttl,
                    json.dumps(value, default=str),
                )
            except Exception as e:
                logger.warning(f"Redis set failed: {e}")

    def delete(
        self,
        cache_type: CacheType,
        identifier: str,
        params: dict[str, Any] | None = None,
    ) -> bool:
        """Delete a value from the cache.

        Args:
            cache_type: Type of cached data
            identifier: Primary identifier
            params: Additional parameters

        Returns:
            True if deleted, False if not found
        """
        key = self._generate_key(cache_type, identifier, params)

        l1_deleted = self._l1_cache.delete(key)

        l2_deleted = False
        if self._stats.l2_enabled and self._redis_client:
            try:
                redis_key = f"kg:{key}"
                l2_deleted = bool(self._redis_client.delete(redis_key))
            except Exception as e:
                logger.warning(f"Redis delete failed: {e}")

        return l1_deleted or l2_deleted

    def invalidate_patient(self, patient_id: str) -> int:
        """Invalidate all cache entries for a patient.

        Args:
            patient_id: Patient identifier

        Returns:
            Number of entries invalidated
        """
        count = 0

        # Invalidate L1 entries
        count += self._l1_cache.clear_by_type(CacheType.PATIENT_GRAPH)

        # Invalidate L2 entries if enabled
        if self._stats.l2_enabled and self._redis_client:
            try:
                pattern = f"kg:patient_graph:{patient_id}:*"
                keys = list(self._redis_client.scan_iter(match=pattern))
                if keys:
                    count += self._redis_client.delete(*keys)
            except Exception as e:
                logger.warning(f"Redis invalidation failed: {e}")

        logger.info(f"Invalidated {count} cache entries for patient {patient_id}")
        return count

    def invalidate_by_type(self, cache_type: CacheType) -> int:
        """Invalidate all cache entries of a specific type.

        Args:
            cache_type: Type to invalidate

        Returns:
            Number of entries invalidated
        """
        count = self._l1_cache.clear_by_type(cache_type)
        self._stats.evictions += count

        if self._stats.l2_enabled and self._redis_client:
            try:
                pattern = f"kg:{cache_type.value}:*"
                keys = list(self._redis_client.scan_iter(match=pattern))
                if keys:
                    count += self._redis_client.delete(*keys)
            except Exception as e:
                logger.warning(f"Redis invalidation failed: {e}")

        return count

    def clear(self) -> int:
        """Clear all cache entries.

        Returns:
            Number of entries cleared
        """
        count = self._l1_cache.clear()
        self._stats.evictions += count

        if self._stats.l2_enabled and self._redis_client:
            try:
                pattern = "kg:*"
                keys = list(self._redis_client.scan_iter(match=pattern))
                if keys:
                    count += self._redis_client.delete(*keys)
            except Exception as e:
                logger.warning(f"Redis clear failed: {e}")

        return count

    def cleanup(self) -> int:
        """Cleanup expired entries.

        Returns:
            Number of entries cleaned up
        """
        count = self._l1_cache.cleanup_expired()
        self._stats.expirations += count
        return count

    def _get_ttl(self, cache_type: CacheType) -> int:
        """Get TTL for a cache type."""
        return self._config.ttl_by_type.get(
            cache_type,
            self._config.l1_default_ttl_seconds,
        )

    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        self._stats.l1_size = self._l1_cache.size
        self._stats.l1_memory_bytes = self._l1_cache.memory_bytes
        return self._stats

    # Convenience methods for common cache operations

    def get_concept(self, cui: str) -> dict[str, Any] | None:
        """Get a cached concept by CUI."""
        return self.get(CacheType.CONCEPT, cui)

    def put_concept(self, cui: str, concept: dict[str, Any]) -> None:
        """Cache a concept."""
        self.put(CacheType.CONCEPT, cui, concept)

    def get_patient_graph(
        self,
        patient_id: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Get a cached patient graph."""
        return self.get(CacheType.PATIENT_GRAPH, patient_id, params)

    def put_patient_graph(
        self,
        patient_id: str,
        graph: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> None:
        """Cache a patient graph."""
        self.put(CacheType.PATIENT_GRAPH, patient_id, graph, params)

    def get_embedding(self, text_hash: str) -> list[float] | None:
        """Get a cached embedding."""
        return self.get(CacheType.EMBEDDING, text_hash)

    def put_embedding(self, text_hash: str, embedding: list[float]) -> None:
        """Cache an embedding."""
        self.put(CacheType.EMBEDDING, text_hash, embedding)

    def get_path(
        self,
        source_cui: str,
        target_cui: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]] | None:
        """Get cached reasoning paths."""
        identifier = f"{source_cui}->{target_cui}"
        return self.get(CacheType.PATH, identifier, params)

    def put_path(
        self,
        source_cui: str,
        target_cui: str,
        paths: list[dict[str, Any]],
        params: dict[str, Any] | None = None,
    ) -> None:
        """Cache reasoning paths."""
        identifier = f"{source_cui}->{target_cui}"
        self.put(CacheType.PATH, identifier, paths, params)


# Singleton instance
_cache_service: KGCacheService | None = None
_cache_lock = threading.Lock()


def get_kg_cache_service(config: CacheConfig | None = None) -> KGCacheService:
    """Get the singleton KG cache service instance.

    Args:
        config: Optional configuration (only used on first call)

    Returns:
        KGCacheService instance
    """
    global _cache_service
    if _cache_service is None:
        with _cache_lock:
            if _cache_service is None:
                _cache_service = KGCacheService(config)
    return _cache_service


def reset_kg_cache_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _cache_service
    with _cache_lock:
        if _cache_service is not None:
            _cache_service.clear()
        _cache_service = None


# ------------------------------------------------------------------
# Traversal result cache (module-level, TTL-based LRU)
#
# Stored here (graph_support) so that both graph_storage (graph_builder_db)
# and graph_rag (graph_augmented_rag) can import without violating
# module boundary rules.
# ------------------------------------------------------------------
_TRAVERSAL_CACHE: dict[str, tuple[float, list]] = {}  # key -> (expiry_ts, paths)
_TRAVERSAL_CACHE_TTL = 300  # 5 minutes
_TRAVERSAL_CACHE_MAX = 100


def traversal_cache_key(
    patient_id: str,
    start_node_ids: list,
    query_concept_ids: list,
    max_hops: int,
    assertion_mode: str = "full",
    temporal_mode: str = "full_bitemporal",
) -> str:
    """Generate a hash key for traversal cache lookups."""
    raw = f"{patient_id}:{sorted(str(x) for x in start_node_ids)}:{sorted(str(x) for x in query_concept_ids)}:{max_hops}:{assertion_mode}:{temporal_mode}"
    return hashlib.sha256(raw.encode()).hexdigest()


def traversal_cache_get(key: str) -> list | None:
    """Get cached traversal paths by key, returning None on miss or expiry."""
    entry = _TRAVERSAL_CACHE.get(key)
    if entry is None:
        return None
    expiry, paths = entry
    if time.monotonic() > expiry:
        _TRAVERSAL_CACHE.pop(key, None)
        return None
    return paths


def traversal_cache_put(key: str, paths: list) -> None:
    """Store traversal paths in cache with LRU eviction."""
    if len(_TRAVERSAL_CACHE) >= _TRAVERSAL_CACHE_MAX:
        oldest_key = min(_TRAVERSAL_CACHE, key=lambda k: _TRAVERSAL_CACHE[k][0])
        _TRAVERSAL_CACHE.pop(oldest_key, None)
    _TRAVERSAL_CACHE[key] = (time.monotonic() + _TRAVERSAL_CACHE_TTL, paths)


def invalidate_traversal_cache(patient_id: str | None = None) -> int:
    """Invalidate traversal cache entries.

    If patient_id given, ideally only that patient's entries would be cleared,
    but since keys are hashed we clear all (safe; worst case is a few extra misses).
    """
    count = len(_TRAVERSAL_CACHE)
    _TRAVERSAL_CACHE.clear()
    return count
