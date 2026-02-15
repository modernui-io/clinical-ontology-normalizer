"""P2-015: Tests for Redis topology (cache vs queue vs session separation)."""

from __future__ import annotations

import os
from unittest import mock

import pytest

from app.core.redis_topology import (
    RedisRole,
    RedisTopology,
    TopologyStatus,
    _mask_url,
)


# ---------------------------------------------------------------------------
# URL masking
# ---------------------------------------------------------------------------

class TestMaskUrl:
    def test_mask_password(self) -> None:
        assert _mask_url("redis://:secret@host:6379/0") == "redis://:***@host:6379/0"

    def test_no_password(self) -> None:
        assert _mask_url("redis://host:6379/0") == "redis://host:6379/0"

    def test_user_password(self) -> None:
        masked = _mask_url("redis://user:pass@host:6379/0")
        assert "pass" not in masked
        assert "***" in masked


# ---------------------------------------------------------------------------
# Topology construction
# ---------------------------------------------------------------------------

class TestRedisTopologyConstruction:
    def test_default_urls_fallback_to_redis_url(self) -> None:
        with mock.patch.dict(os.environ, {"REDIS_URL": "redis://default:6379/0"}, clear=False):
            topo = RedisTopology()
            status = topo.get_topology_status()
            assert status.shared is True
            assert len(status.role_urls) == 3

    def test_separate_urls(self) -> None:
        env = {
            "REDIS_URL": "redis://fallback:6379/0",
            "REDIS_CACHE_URL": "redis://cache:6379/0",
            "REDIS_QUEUE_URL": "redis://queue:6379/1",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            topo = RedisTopology()
            status = topo.get_topology_status()
            # session falls back, but cache and queue are different -> not shared
            assert status.shared is False
            assert "cache" in status.role_urls["cache"]

    def test_all_same_still_shared(self) -> None:
        same_url = "redis://shared:6379/0"
        env = {
            "REDIS_URL": same_url,
            "REDIS_CACHE_URL": same_url,
            "REDIS_QUEUE_URL": same_url,
            "REDIS_SESSION_URL": same_url,
        }
        with mock.patch.dict(os.environ, env, clear=False):
            topo = RedisTopology()
            assert topo.get_topology_status().shared is True


# ---------------------------------------------------------------------------
# TopologyStatus model
# ---------------------------------------------------------------------------

class TestTopologyStatus:
    def test_fields(self) -> None:
        ts = TopologyStatus(role_urls={"cache": "redis://x", "queue": "redis://y", "session": "redis://x"}, shared=False)
        assert ts.shared is False
        assert "cache" in ts.role_urls


# ---------------------------------------------------------------------------
# get_redis per role
# ---------------------------------------------------------------------------

class TestGetRedis:
    def test_returns_redis_client(self) -> None:
        with mock.patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379/0"}, clear=False):
            topo = RedisTopology()
            client = topo.get_redis(RedisRole.CACHE)
            assert client is not None
            # Calling again returns the same cached instance
            assert topo.get_redis(RedisRole.CACHE) is client

    def test_different_roles_different_clients(self) -> None:
        with mock.patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379/0"}, clear=False):
            topo = RedisTopology()
            cache = topo.get_redis(RedisRole.CACHE)
            queue = topo.get_redis(RedisRole.QUEUE)
            assert cache is not queue


# ---------------------------------------------------------------------------
# Close
# ---------------------------------------------------------------------------

class TestClose:
    def test_close_single_role(self) -> None:
        with mock.patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379/0"}, clear=False):
            topo = RedisTopology()
            _ = topo.get_redis(RedisRole.CACHE)
            topo.close(RedisRole.CACHE)
            # After close, a new client is created on next access
            client = topo.get_redis(RedisRole.CACHE)
            assert client is not None

    def test_close_all(self) -> None:
        with mock.patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379/0"}, clear=False):
            topo = RedisTopology()
            _ = topo.get_redis(RedisRole.CACHE)
            _ = topo.get_redis(RedisRole.QUEUE)
            topo.close()
            # All cleared, new clients on next access
            assert topo.get_redis(RedisRole.CACHE) is not None


# ---------------------------------------------------------------------------
# Enum coverage
# ---------------------------------------------------------------------------

class TestRedisRole:
    def test_enum_values(self) -> None:
        assert RedisRole.CACHE.value == "cache"
        assert RedisRole.QUEUE.value == "queue"
        assert RedisRole.SESSION.value == "session"

    def test_all_roles_represented(self) -> None:
        assert len(RedisRole) == 3
