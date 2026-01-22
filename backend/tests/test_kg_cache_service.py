"""Tests for Knowledge Graph Cache Service."""

from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest

from app.services.kg_cache_service import (
    CacheConfig,
    CacheEntry,
    CacheStats,
    CacheType,
    KGCacheService,
    LRUCache,
    get_kg_cache_service,
    reset_kg_cache_service,
)


class TestCacheEntry:
    """Test CacheEntry dataclass."""

    def test_cache_entry_creation(self) -> None:
        """Test creating a cache entry."""
        now = datetime.now(timezone.utc)
        future = datetime.fromtimestamp(now.timestamp() + 300, tz=timezone.utc)

        entry = CacheEntry(
            key="test:key",
            value={"data": "test"},
            cache_type=CacheType.CONCEPT,
            created_at=now,
            expires_at=future,
        )

        assert entry.key == "test:key"
        assert entry.value == {"data": "test"}
        assert entry.access_count == 0
        assert not entry.is_expired()

    def test_cache_entry_expired(self) -> None:
        """Test expired cache entry detection."""
        now = datetime.now(timezone.utc)
        past = datetime.fromtimestamp(now.timestamp() - 300, tz=timezone.utc)

        entry = CacheEntry(
            key="test:key",
            value={"data": "test"},
            cache_type=CacheType.CONCEPT,
            created_at=past,
            expires_at=past,
        )

        assert entry.is_expired()

    def test_cache_entry_touch(self) -> None:
        """Test updating access metadata."""
        now = datetime.now(timezone.utc)
        future = datetime.fromtimestamp(now.timestamp() + 300, tz=timezone.utc)

        entry = CacheEntry(
            key="test:key",
            value={"data": "test"},
            cache_type=CacheType.CONCEPT,
            created_at=now,
            expires_at=future,
        )

        assert entry.access_count == 0
        entry.touch()
        assert entry.access_count == 1
        assert entry.last_accessed is not None

        entry.touch()
        assert entry.access_count == 2


class TestCacheStats:
    """Test CacheStats dataclass."""

    def test_cache_stats_defaults(self) -> None:
        """Test default cache stats."""
        stats = CacheStats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.hit_rate == 0.0

    def test_cache_stats_hit_rate(self) -> None:
        """Test hit rate calculation."""
        stats = CacheStats(hits=80, misses=20)
        assert stats.hit_rate == 0.8

    def test_cache_stats_to_dict(self) -> None:
        """Test converting stats to dict."""
        stats = CacheStats(hits=100, misses=50, evictions=10)
        data = stats.to_dict()

        assert data["hits"] == 100
        assert data["misses"] == 50
        assert data["evictions"] == 10
        assert "hit_rate" in data


class TestLRUCache:
    """Test LRU cache implementation."""

    def test_lru_cache_put_get(self) -> None:
        """Test basic put and get operations."""
        cache = LRUCache(max_size=100)

        cache.put("key1", {"value": 1}, CacheType.CONCEPT, 300)
        entry = cache.get("key1")

        assert entry is not None
        assert entry.value == {"value": 1}

    def test_lru_cache_miss(self) -> None:
        """Test cache miss."""
        cache = LRUCache(max_size=100)
        entry = cache.get("nonexistent")
        assert entry is None

    def test_lru_cache_eviction(self) -> None:
        """Test LRU eviction when at capacity."""
        cache = LRUCache(max_size=3)

        cache.put("key1", {"value": 1}, CacheType.CONCEPT, 300)
        cache.put("key2", {"value": 2}, CacheType.CONCEPT, 300)
        cache.put("key3", {"value": 3}, CacheType.CONCEPT, 300)

        # Access key1 to make it recently used
        cache.get("key1")

        # Add key4, should evict key2 (least recently used)
        cache.put("key4", {"value": 4}, CacheType.CONCEPT, 300)

        assert cache.get("key1") is not None
        assert cache.get("key2") is None  # Evicted
        assert cache.get("key3") is not None
        assert cache.get("key4") is not None

    def test_lru_cache_expired_entry(self) -> None:
        """Test that expired entries are not returned."""
        cache = LRUCache(max_size=100)

        # Put with 0 TTL (immediately expired)
        cache.put("key1", {"value": 1}, CacheType.CONCEPT, 0)
        time.sleep(0.1)

        entry = cache.get("key1")
        assert entry is None

    def test_lru_cache_delete(self) -> None:
        """Test deleting an entry."""
        cache = LRUCache(max_size=100)

        cache.put("key1", {"value": 1}, CacheType.CONCEPT, 300)
        assert cache.delete("key1")
        assert cache.get("key1") is None
        assert not cache.delete("key1")  # Already deleted

    def test_lru_cache_clear(self) -> None:
        """Test clearing the cache."""
        cache = LRUCache(max_size=100)

        cache.put("key1", {"value": 1}, CacheType.CONCEPT, 300)
        cache.put("key2", {"value": 2}, CacheType.CONCEPT, 300)

        count = cache.clear()
        assert count == 2
        assert cache.size == 0

    def test_lru_cache_clear_by_type(self) -> None:
        """Test clearing entries by type."""
        cache = LRUCache(max_size=100)

        cache.put("concept1", {"value": 1}, CacheType.CONCEPT, 300)
        cache.put("concept2", {"value": 2}, CacheType.CONCEPT, 300)
        cache.put("path1", {"value": 3}, CacheType.PATH, 300)

        count = cache.clear_by_type(CacheType.CONCEPT)
        assert count == 2
        assert cache.size == 1  # path1 remains

    def test_lru_cache_cleanup_expired(self) -> None:
        """Test cleaning up expired entries."""
        cache = LRUCache(max_size=100)

        cache.put("key1", {"value": 1}, CacheType.CONCEPT, 0)  # Expired
        cache.put("key2", {"value": 2}, CacheType.CONCEPT, 300)  # Not expired

        time.sleep(0.1)
        count = cache.cleanup_expired()

        assert count == 1
        assert cache.get("key1") is None
        assert cache.get("key2") is not None


class TestKGCacheService:
    """Test KG cache service."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self) -> None:
        """Reset singleton before each test."""
        reset_kg_cache_service()

    def test_service_creation(self) -> None:
        """Test creating the cache service."""
        config = CacheConfig(l1_max_size=100)
        service = KGCacheService(config)
        assert service is not None

    def test_put_and_get(self) -> None:
        """Test basic put and get operations."""
        service = KGCacheService()

        service.put(CacheType.CONCEPT, "C0004096", {"name": "Asthma"})
        result = service.get(CacheType.CONCEPT, "C0004096")

        assert result is not None
        assert result["name"] == "Asthma"

    def test_cache_miss(self) -> None:
        """Test cache miss."""
        service = KGCacheService()
        result = service.get(CacheType.CONCEPT, "nonexistent")
        assert result is None

    def test_get_with_params(self) -> None:
        """Test get with additional parameters."""
        service = KGCacheService()

        params = {"max_hops": 3, "include_provenance": True}
        service.put(CacheType.PATH, "C1->C2", {"paths": []}, params)

        result = service.get(CacheType.PATH, "C1->C2", params)
        assert result is not None

        # Different params should miss
        other_params = {"max_hops": 5}
        result = service.get(CacheType.PATH, "C1->C2", other_params)
        assert result is None

    def test_delete(self) -> None:
        """Test deleting a cached entry."""
        service = KGCacheService()

        service.put(CacheType.CONCEPT, "C0004096", {"name": "Asthma"})
        assert service.delete(CacheType.CONCEPT, "C0004096")
        assert service.get(CacheType.CONCEPT, "C0004096") is None

    def test_invalidate_by_type(self) -> None:
        """Test invalidating all entries of a type."""
        service = KGCacheService()

        service.put(CacheType.CONCEPT, "C1", {"name": "Concept 1"})
        service.put(CacheType.CONCEPT, "C2", {"name": "Concept 2"})
        service.put(CacheType.PATH, "P1", {"path": []})

        count = service.invalidate_by_type(CacheType.CONCEPT)
        assert count == 2

        assert service.get(CacheType.CONCEPT, "C1") is None
        assert service.get(CacheType.PATH, "P1") is not None

    def test_clear(self) -> None:
        """Test clearing all cache entries."""
        service = KGCacheService()

        service.put(CacheType.CONCEPT, "C1", {"name": "Concept 1"})
        service.put(CacheType.PATH, "P1", {"path": []})

        count = service.clear()
        assert count == 2

    def test_stats(self) -> None:
        """Test cache statistics."""
        service = KGCacheService()

        service.put(CacheType.CONCEPT, "C1", {"name": "Concept 1"})

        # Hit
        service.get(CacheType.CONCEPT, "C1")
        # Miss
        service.get(CacheType.CONCEPT, "C2")

        stats = service.get_stats()
        assert stats.hits == 1
        assert stats.misses == 1
        assert stats.l1_size == 1

    def test_convenience_methods_concept(self) -> None:
        """Test concept convenience methods."""
        service = KGCacheService()

        concept = {"cui": "C0004096", "name": "Asthma"}
        service.put_concept("C0004096", concept)

        result = service.get_concept("C0004096")
        assert result is not None
        assert result["name"] == "Asthma"

    def test_convenience_methods_patient_graph(self) -> None:
        """Test patient graph convenience methods."""
        service = KGCacheService()

        graph = {"nodes": [], "edges": []}
        params = {"depth": 2}
        service.put_patient_graph("P12345", graph, params)

        result = service.get_patient_graph("P12345", params)
        assert result is not None
        assert "nodes" in result

    def test_convenience_methods_embedding(self) -> None:
        """Test embedding convenience methods."""
        service = KGCacheService()

        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        service.put_embedding("text_hash_123", embedding)

        result = service.get_embedding("text_hash_123")
        assert result is not None
        assert len(result) == 5

    def test_convenience_methods_path(self) -> None:
        """Test path convenience methods."""
        service = KGCacheService()

        paths = [{"path_id": "p1", "hops": 2}]
        service.put_path("C1", "C2", paths)

        result = service.get_path("C1", "C2")
        assert result is not None
        assert len(result) == 1


class TestSingleton:
    """Test singleton pattern."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self) -> None:
        """Reset singleton before each test."""
        reset_kg_cache_service()

    def test_singleton_returns_same_instance(self) -> None:
        """Test that singleton returns the same instance."""
        service1 = get_kg_cache_service()
        service2 = get_kg_cache_service()
        assert service1 is service2

    def test_reset_singleton(self) -> None:
        """Test resetting the singleton."""
        service1 = get_kg_cache_service()
        reset_kg_cache_service()
        service2 = get_kg_cache_service()
        assert service1 is not service2


class TestCacheConfig:
    """Test cache configuration."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = CacheConfig()

        assert config.l1_max_size == 10000
        assert config.l1_default_ttl_seconds == 300
        assert config.l2_enabled is False

    def test_ttl_by_type(self) -> None:
        """Test TTL configuration by type."""
        config = CacheConfig()

        assert config.ttl_by_type[CacheType.CONCEPT] == 3600
        assert config.ttl_by_type[CacheType.PATIENT_GRAPH] == 300
        assert config.ttl_by_type[CacheType.EMBEDDING] == 7200

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = CacheConfig(
            l1_max_size=5000,
            l1_default_ttl_seconds=600,
            l2_enabled=True,
        )

        assert config.l1_max_size == 5000
        assert config.l1_default_ttl_seconds == 600
        assert config.l2_enabled is True


class TestCacheKeyGeneration:
    """Test cache key generation."""

    def test_simple_key(self) -> None:
        """Test simple key generation."""
        service = KGCacheService()
        key = service._generate_key(CacheType.CONCEPT, "C0004096")
        assert key == "concept:C0004096"

    def test_key_with_params(self) -> None:
        """Test key generation with parameters."""
        service = KGCacheService()

        params = {"max_hops": 3, "include_provenance": True}
        key = service._generate_key(CacheType.PATH, "C1->C2", params)

        assert key.startswith("path:C1->C2:")
        assert len(key) > len("path:C1->C2:")  # Has hash suffix

    def test_consistent_key_generation(self) -> None:
        """Test that keys are consistently generated."""
        service = KGCacheService()

        params = {"a": 1, "b": 2}
        key1 = service._generate_key(CacheType.QUERY_RESULT, "query1", params)

        # Same params in different order should produce same key
        params2 = {"b": 2, "a": 1}
        key2 = service._generate_key(CacheType.QUERY_RESULT, "query1", params2)

        assert key1 == key2
