"""Terminology Operation Caching.

Provides an in-memory TTL cache for terminology operations
(ICD-10 lookups, CPT searches, drug safety queries, etc.)
to reduce repeated computation on common queries.
"""

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


# Global cache instances for each terminology service
_icd10_cache = TerminologyCache(max_size=2000, default_ttl=600.0)  # 10 min TTL
_cpt_cache = TerminologyCache(max_size=1000, default_ttl=600.0)
_drug_cache = TerminologyCache(max_size=500, default_ttl=600.0)
_hcc_cache = TerminologyCache(max_size=500, default_ttl=600.0)
_differential_cache = TerminologyCache(max_size=200, default_ttl=300.0)  # 5 min TTL


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


def get_all_cache_stats() -> dict[str, Any]:
    """Get statistics for all terminology caches."""
    return {
        "icd10": _icd10_cache.get_stats(),
        "cpt": _cpt_cache.get_stats(),
        "drug_safety": _drug_cache.get_stats(),
        "hcc": _hcc_cache.get_stats(),
        "differential": _differential_cache.get_stats(),
    }


def clear_all_caches() -> None:
    """Clear all terminology caches."""
    _icd10_cache.clear()
    _cpt_cache.clear()
    _drug_cache.clear()
    _hcc_cache.clear()
    _differential_cache.clear()
