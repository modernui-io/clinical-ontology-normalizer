"""Tests for terminology operation caching.

Tests verify:
- Cache decorator stores and retrieves results
- TTL expiration works correctly
- Cache invalidation on vocabulary reload
- Cache statistics tracking
- Per-operation TTL configuration
"""

import time
import pytest

from app.services.terminology_cache import (
    TerminologyCache,
    CacheEntry,
    cached_operation,
    get_fhir_operation_cache,
    get_all_cache_stats,
    clear_all_caches,
    OPERATION_TTL,
)


class TestCacheEntry:
    """Test CacheEntry dataclass."""

    def test_entry_not_expired_immediately(self):
        entry = CacheEntry(value="test", created_at=time.time(), ttl_seconds=60)
        assert not entry.is_expired

    def test_entry_expired_after_ttl(self):
        entry = CacheEntry(value="test", created_at=time.time() - 100, ttl_seconds=60)
        assert entry.is_expired

    def test_entry_just_before_expiry(self):
        # 59 seconds ago with 60 second TTL - should NOT be expired
        entry = CacheEntry(value="test", created_at=time.time() - 59, ttl_seconds=60)
        assert not entry.is_expired

    def test_entry_past_boundary(self):
        # 61 seconds ago with 60 second TTL - should be expired
        entry = CacheEntry(value="test", created_at=time.time() - 61, ttl_seconds=60)
        assert entry.is_expired


class TestTerminologyCache:
    """Test TerminologyCache core operations."""

    def setup_method(self):
        self.cache = TerminologyCache(max_size=10, default_ttl=60.0)

    def test_set_and_get(self):
        self.cache.set("key1", {"result": "value1"})
        assert self.cache.get("key1") == {"result": "value1"}

    def test_get_missing_key_returns_none(self):
        assert self.cache.get("nonexistent") is None

    def test_expired_entry_returns_none(self):
        self.cache.set("key1", "value1", ttl=0.01)
        time.sleep(0.02)
        assert self.cache.get("key1") is None

    def test_lru_eviction(self):
        cache = TerminologyCache(max_size=3, default_ttl=60.0)
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        cache.set("k3", "v3")
        cache.set("k4", "v4")  # Should evict k1
        assert cache.get("k1") is None
        assert cache.get("k2") == "v2"

    def test_access_updates_lru_order(self):
        cache = TerminologyCache(max_size=3, default_ttl=60.0)
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        cache.set("k3", "v3")
        # Access k1 to make it recently used
        cache.get("k1")
        cache.set("k4", "v4")  # Should evict k2 (least recently used)
        assert cache.get("k1") == "v1"
        assert cache.get("k2") is None

    def test_invalidate_key(self):
        self.cache.set("key1", "value1")
        self.cache.invalidate("key1")
        assert self.cache.get("key1") is None

    def test_clear_removes_all(self):
        self.cache.set("k1", "v1")
        self.cache.set("k2", "v2")
        self.cache.clear()
        assert self.cache.get("k1") is None
        assert self.cache.get("k2") is None

    def test_make_key_deterministic(self):
        key1 = self.cache._make_key("lookup", "system1", "code1")
        key2 = self.cache._make_key("lookup", "system1", "code1")
        assert key1 == key2

    def test_make_key_different_for_different_args(self):
        key1 = self.cache._make_key("lookup", "system1", "code1")
        key2 = self.cache._make_key("lookup", "system1", "code2")
        assert key1 != key2

    def test_make_key_different_for_different_namespaces(self):
        key1 = self.cache._make_key("lookup", "system1", "code1")
        key2 = self.cache._make_key("validate", "system1", "code1")
        assert key1 != key2


class TestCacheStats:
    """Test cache statistics tracking."""

    def setup_method(self):
        self.cache = TerminologyCache(max_size=100, default_ttl=60.0)

    def test_initial_stats(self):
        stats = self.cache.get_stats()
        assert stats["size"] == 0
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == 0.0

    def test_hit_increments(self):
        self.cache.set("key1", "value1")
        self.cache.get("key1")
        stats = self.cache.get_stats()
        assert stats["hits"] == 1

    def test_miss_increments(self):
        self.cache.get("nonexistent")
        stats = self.cache.get_stats()
        assert stats["misses"] == 1

    def test_hit_rate_calculation(self):
        self.cache.set("key1", "value1")
        self.cache.get("key1")  # hit
        self.cache.get("key1")  # hit
        self.cache.get("miss")  # miss
        stats = self.cache.get_stats()
        assert stats["hit_rate"] == pytest.approx(0.667, abs=0.01)

    def test_clear_resets_stats(self):
        self.cache.set("key1", "value1")
        self.cache.get("key1")
        self.cache.clear()
        stats = self.cache.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0


class TestCachedOperationDecorator:
    """Test the cached_operation decorator."""

    def setup_method(self):
        self.cache = TerminologyCache(max_size=100, default_ttl=60.0)
        self.call_count = 0

    def test_first_call_executes_function(self):
        @cached_operation(self.cache, "test_op")
        def expensive_op(x: int) -> int:
            self.call_count += 1
            return x * 2

        result = expensive_op(5)
        assert result == 10
        assert self.call_count == 1

    def test_second_call_uses_cache(self):
        @cached_operation(self.cache, "test_op")
        def expensive_op(x: int) -> int:
            self.call_count += 1
            return x * 2

        expensive_op(5)
        result = expensive_op(5)
        assert result == 10
        assert self.call_count == 1  # Not called again

    def test_different_args_call_function(self):
        @cached_operation(self.cache, "test_op")
        def expensive_op(x: int) -> int:
            self.call_count += 1
            return x * 2

        expensive_op(5)
        expensive_op(10)
        assert self.call_count == 2

    def test_none_result_not_cached(self):
        @cached_operation(self.cache, "test_op")
        def may_return_none(x: int):
            self.call_count += 1
            return None if x < 0 else x

        may_return_none(-1)
        may_return_none(-1)
        assert self.call_count == 2  # Called twice because None wasn't cached

    def test_custom_ttl(self):
        @cached_operation(self.cache, "test_op", ttl=0.01)
        def fast_expiry(x: int) -> int:
            self.call_count += 1
            return x

        fast_expiry(5)
        time.sleep(0.02)
        fast_expiry(5)
        assert self.call_count == 2  # Called again after TTL

    def test_invalidate_cache_method(self):
        @cached_operation(self.cache, "test_op")
        def cached_fn(x: int) -> int:
            self.call_count += 1
            return x

        cached_fn(5)
        cached_fn.invalidate_cache()
        cached_fn(5)
        assert self.call_count == 2

    def test_kwargs_cached_correctly(self):
        @cached_operation(self.cache, "test_op")
        def with_kwargs(system: str, code: str) -> str:
            self.call_count += 1
            return f"{system}:{code}"

        with_kwargs(system="snomed", code="123")
        result = with_kwargs(system="snomed", code="123")
        assert result == "snomed:123"
        assert self.call_count == 1


class TestFHIROperationCache:
    """Test the FHIR operation cache instance."""

    def test_fhir_cache_exists(self):
        cache = get_fhir_operation_cache()
        assert cache is not None
        assert cache._default_ttl == 3600.0  # 1 hour

    def test_fhir_cache_in_all_stats(self):
        stats = get_all_cache_stats()
        assert "fhir_operations" in stats


class TestCacheInvalidationOnReload:
    """Test that clear_all_caches clears everything (vocabulary reload scenario)."""

    def test_clear_all_caches_clears_fhir(self):
        cache = get_fhir_operation_cache()
        cache.set("test_key", "test_value")
        clear_all_caches()
        assert cache.get("test_key") is None

    def test_clear_all_resets_stats(self):
        cache = get_fhir_operation_cache()
        cache.set("test_key", "test_value")
        cache.get("test_key")
        clear_all_caches()
        stats = cache.get_stats()
        assert stats["hits"] == 0


class TestOperationTTLConfig:
    """Test per-operation TTL configuration."""

    def test_lookup_ttl(self):
        assert OPERATION_TTL["lookup"] == 3600

    def test_validate_code_ttl(self):
        assert OPERATION_TTL["validate-code"] == 3600

    def test_expand_ttl(self):
        assert OPERATION_TTL["expand"] == 1800

    def test_translate_ttl(self):
        assert OPERATION_TTL["translate"] == 3600
