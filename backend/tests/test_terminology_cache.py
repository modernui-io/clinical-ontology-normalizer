"""Tests for Terminology Caching (Redis-based).

Tests verify:
- Cache hit returns cached result
- Cache miss calls underlying service
- TTL expiration
- Cache invalidation
- Cache key uniqueness across operations
"""

import time

import pytest
from unittest.mock import patch, MagicMock

from app.services.terminology_cache import (
    RedisTerminologyCache,
    OPERATION_TTL,
    reset_redis_terminology_cache,
)


@pytest.fixture(autouse=True)
def reset_cache():
    """Reset cache singleton between tests."""
    reset_redis_terminology_cache()
    yield
    reset_redis_terminology_cache()


@pytest.fixture
def cache():
    """Create a RedisTerminologyCache that falls back to in-memory."""
    # Use a non-existent Redis URL to force in-memory fallback
    c = RedisTerminologyCache(redis_url="redis://nonexistent:9999/0", prefix="test")
    return c


class TestCacheHitReturns:
    """Test cache hit returns cached result."""

    def test_set_and_get(self, cache):
        cache.set("lookup", {"display": "Diabetes"}, system="snomed", code="73211009")
        result = cache.get("lookup", system="snomed", code="73211009")
        assert result == {"display": "Diabetes"}

    def test_cache_hit_same_params(self, cache):
        cache.set("validate-code", {"result": True}, system="icd10", code="E11.9")
        result = cache.get("validate-code", system="icd10", code="E11.9")
        assert result == {"result": True}

    def test_repeated_gets_return_same(self, cache):
        cache.set("lookup", {"name": "Test"}, code="123")
        assert cache.get("lookup", code="123") == {"name": "Test"}
        assert cache.get("lookup", code="123") == {"name": "Test"}


class TestCacheMiss:
    """Test cache miss returns None."""

    def test_miss_returns_none(self, cache):
        result = cache.get("lookup", system="snomed", code="nonexistent")
        assert result is None

    def test_different_params_miss(self, cache):
        cache.set("lookup", {"display": "A"}, code="111")
        result = cache.get("lookup", code="222")
        assert result is None

    def test_different_operation_miss(self, cache):
        cache.set("lookup", {"display": "A"}, code="111")
        result = cache.get("expand", code="111")
        assert result is None


class TestTTLExpiration:
    """Test TTL expiration."""

    def test_expired_entry_returns_none(self):
        # Create cache with very short TTL fallback
        cache = RedisTerminologyCache(redis_url="redis://nonexistent:9999/0", prefix="ttl-test")
        # Override the fallback TTL to be very short
        cache._fallback._default_ttl = 0.01  # 10ms
        key = cache.make_key("lookup", code="test")
        cache._fallback.set(key, {"data": "old"}, ttl=0.01)
        time.sleep(0.02)
        result = cache._fallback.get(key)
        assert result is None

    def test_operation_ttl_defaults(self):
        assert OPERATION_TTL["lookup"] == 3600
        assert OPERATION_TTL["expand"] == 1800
        assert OPERATION_TTL["validate-code"] == 3600
        assert OPERATION_TTL["translate"] == 3600


class TestCacheInvalidation:
    """Test cache invalidation."""

    def test_invalidate_specific_entry(self, cache):
        cache.set("lookup", {"display": "A"}, system="snomed", code="111")
        cache.invalidate("lookup", system="snomed", code="111")
        result = cache.get("lookup", system="snomed", code="111")
        assert result is None

    def test_invalidate_does_not_affect_other_entries(self, cache):
        cache.set("lookup", {"display": "A"}, code="111")
        cache.set("lookup", {"display": "B"}, code="222")
        cache.invalidate("lookup", code="111")
        assert cache.get("lookup", code="222") == {"display": "B"}

    def test_clear_removes_all(self, cache):
        cache.set("lookup", {"a": 1}, code="1")
        cache.set("expand", {"b": 2}, url="test")
        cache.clear()
        assert cache.get("lookup", code="1") is None
        assert cache.get("expand", url="test") is None

    def test_invalidate_operation_clears_type(self, cache):
        cache.set("lookup", {"a": 1}, code="1")
        cache.set("lookup", {"b": 2}, code="2")
        cache.set("expand", {"c": 3}, url="test")
        cache.invalidate_operation("lookup")
        # In-memory fallback clears all on invalidate_operation
        # so expand is also cleared
        assert cache.get("lookup", code="1") is None
        assert cache.get("lookup", code="2") is None


class TestCacheKeyUniqueness:
    """Test cache key uniqueness across operations."""

    def test_different_operations_different_keys(self, cache):
        key1 = cache.make_key("lookup", code="111")
        key2 = cache.make_key("expand", code="111")
        assert key1 != key2

    def test_different_params_different_keys(self, cache):
        key1 = cache.make_key("lookup", system="snomed", code="111")
        key2 = cache.make_key("lookup", system="icd10", code="111")
        assert key1 != key2

    def test_same_params_same_key(self, cache):
        key1 = cache.make_key("lookup", system="snomed", code="111")
        key2 = cache.make_key("lookup", system="snomed", code="111")
        assert key1 == key2

    def test_param_order_does_not_matter(self, cache):
        key1 = cache.make_key("lookup", system="snomed", code="111")
        key2 = cache.make_key("lookup", code="111", system="snomed")
        assert key1 == key2

    def test_key_includes_prefix(self, cache):
        key = cache.make_key("lookup", code="111")
        assert key.startswith("test:lookup:")

    def test_isolation_between_operations(self, cache):
        cache.set("lookup", {"result": "lookup"}, code="111")
        cache.set("expand", {"result": "expand"}, code="111")
        assert cache.get("lookup", code="111") == {"result": "lookup"}
        assert cache.get("expand", code="111") == {"result": "expand"}


class TestCacheStats:
    """Test cache statistics."""

    def test_stats_includes_backend(self, cache):
        stats = cache.get_stats()
        assert "backend" in stats
        assert stats["backend"] == "in-memory"

    def test_stats_includes_ttls(self, cache):
        stats = cache.get_stats()
        assert "operation_ttls" in stats
        assert stats["operation_ttls"]["lookup"] == 3600
