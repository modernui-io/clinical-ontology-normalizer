"""P2-015: Redis topology for separating cache, queue, and session connections.

In production, different Redis roles can point at different instances for
isolation (cache eviction policy vs. persistent queue data).  Falls back
to a single REDIS_URL when per-role URLs are not configured.
"""

from __future__ import annotations

import enum
import logging
import os
import re
import threading
from dataclasses import dataclass
from typing import Any

from redis import Redis

logger = logging.getLogger(__name__)


class RedisRole(enum.Enum):
    """Logical role for a Redis connection."""
    CACHE = "cache"
    QUEUE = "queue"
    SESSION = "session"


# Env-var mapping per role.  Falls back to REDIS_URL.
_ROLE_ENV_MAP: dict[RedisRole, str] = {
    RedisRole.CACHE: "REDIS_CACHE_URL",
    RedisRole.QUEUE: "REDIS_QUEUE_URL",
    RedisRole.SESSION: "REDIS_SESSION_URL",
}

_DEFAULT_REDIS_URL = "redis://localhost:6379/0"


def _mask_url(url: str) -> str:
    """Mask password in Redis URL for safe logging."""
    if "@" in url:
        return re.sub(r":([^:@]+)@", r":***@", url)
    return url


@dataclass(frozen=True)
class TopologyStatus:
    """Describes which roles share or have separate Redis instances."""
    role_urls: dict[str, str]  # role name -> masked URL
    shared: bool  # True if all roles point at the same instance


class RedisTopology:
    """Manages separate Redis connections per logical role.

    Usage:
        topology = RedisTopology()
        cache_conn = topology.get_redis(RedisRole.CACHE)
        queue_conn = topology.get_redis(RedisRole.QUEUE)
    """

    def __init__(self) -> None:
        self._connections: dict[RedisRole, Redis] = {}
        self._lock = threading.Lock()
        self._urls: dict[RedisRole, str] = {}
        self._resolve_urls()

    def _resolve_urls(self) -> None:
        """Resolve the URL each role should connect to."""
        fallback = os.environ.get("REDIS_URL", _DEFAULT_REDIS_URL)
        for role, env_var in _ROLE_ENV_MAP.items():
            self._urls[role] = os.environ.get(env_var, fallback)

    def _url_for(self, role: RedisRole) -> str:
        return self._urls[role]

    def get_redis(self, role: RedisRole) -> Redis:
        """Get a Redis client for the given role.

        Connections are lazily created and cached per role.
        If two roles resolve to the same URL, they still get separate
        client objects (safe for independent option tuning later).
        """
        if role not in self._connections:
            with self._lock:
                if role not in self._connections:
                    url = self._url_for(role)
                    logger.info(
                        "Creating Redis connection for role=%s url=%s",
                        role.value,
                        _mask_url(url),
                    )
                    self._connections[role] = Redis.from_url(url, decode_responses=True)
        return self._connections[role]

    def get_topology_status(self) -> TopologyStatus:
        """Return a summary of which roles share instances."""
        role_urls = {role.value: _mask_url(self._url_for(role)) for role in RedisRole}
        raw_urls = set(self._urls.values())
        return TopologyStatus(role_urls=role_urls, shared=len(raw_urls) == 1)

    def ping(self, role: RedisRole) -> bool:
        """Health-check a specific role's connection."""
        try:
            return bool(self.get_redis(role).ping())
        except Exception as e:
            logger.warning(
                "Redis ping failed for role=%s: %s",
                role.value,
                str(e),
            )
            return False

    def ping_all(self) -> dict[str, bool]:
        """Health-check all roles."""
        return {role.value: self.ping(role) for role in RedisRole}

    def close(self, role: RedisRole | None = None) -> None:
        """Close connection(s).

        If role is None, close all.
        """
        with self._lock:
            if role is not None:
                conn = self._connections.pop(role, None)
                if conn:
                    conn.close()
            else:
                for conn in self._connections.values():
                    conn.close()
                self._connections.clear()


# Module-level singleton (lazy)
_topology: RedisTopology | None = None
_topology_lock = threading.Lock()


def get_topology() -> RedisTopology:
    """Get the module-level RedisTopology singleton."""
    global _topology
    if _topology is None:
        with _topology_lock:
            if _topology is None:
                _topology = RedisTopology()
    return _topology


def get_redis_for_role(role: RedisRole) -> Redis:
    """Convenience: get a Redis client for a role via the singleton."""
    return get_topology().get_redis(role)
