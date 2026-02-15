"""Idempotency middleware for safe retries on POST/PUT ingestion endpoints.

P2-020: Prevents duplicate processing when clients retry requests due to
network timeouts or ambiguous failures. Keyed by (Idempotency-Key header,
HTTP method, path). Cached responses are replayed within a configurable TTL.

Usage:
    Add to FastAPI app middleware stack:
        app.add_middleware(IdempotencyMiddleware)

    Clients send: Idempotency-Key: <unique-uuid>
    If the same key+method+path is seen within the TTL window, the original
    response is returned without re-executing the handler.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# Header name for idempotency key
IDEMPOTENCY_HEADER = "Idempotency-Key"

# TTL from env var (seconds), default 1 hour
IDEMPOTENCY_TTL_SECONDS = int(os.environ.get("IDEMPOTENCY_TTL_SECONDS", "3600"))

# Maximum key length to prevent abuse
MAX_KEY_LENGTH = 256

# Methods that support idempotency (mutating operations)
IDEMPOTENT_METHODS = {"POST", "PUT"}


@dataclass
class CachedResponse:
    """Stored response for an idempotency key."""

    status_code: int
    body: bytes
    headers: dict[str, str]
    created_at: float


class IdempotencyStore:
    """In-memory TTL store for idempotency keys.

    Thread-safe for asyncio (single-threaded event loop). Uses lazy eviction
    on reads plus periodic sweeps to bound memory growth.
    """

    def __init__(self, ttl_seconds: int = IDEMPOTENCY_TTL_SECONDS) -> None:
        self._store: dict[str, CachedResponse] = {}
        self._in_flight: set[str] = set()
        self.ttl_seconds = ttl_seconds
        self._last_sweep: float = time.monotonic()
        self._sweep_interval: float = 300.0  # sweep every 5 minutes

    def _composite_key(self, idempotency_key: str, method: str, path: str) -> str:
        """Build a composite cache key from (idempotency_key, method, path)."""
        raw = f"{idempotency_key}:{method}:{path}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _maybe_sweep(self) -> None:
        """Remove expired entries if enough time has passed since last sweep."""
        now = time.monotonic()
        if now - self._last_sweep < self._sweep_interval:
            return
        self._last_sweep = now
        expired = [
            k for k, v in self._store.items()
            if now - v.created_at > self.ttl_seconds
        ]
        for k in expired:
            del self._store[k]
        if expired:
            logger.debug("Idempotency sweep removed %d expired entries", len(expired))

    def get(self, idempotency_key: str, method: str, path: str) -> CachedResponse | None:
        """Look up a cached response. Returns None if not found or expired."""
        self._maybe_sweep()
        key = self._composite_key(idempotency_key, method, path)
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.monotonic() - entry.created_at > self.ttl_seconds:
            del self._store[key]
            return None
        return entry

    def set(
        self, idempotency_key: str, method: str, path: str, response: CachedResponse
    ) -> None:
        """Store a response for replay."""
        key = self._composite_key(idempotency_key, method, path)
        self._store[key] = response

    def mark_in_flight(self, idempotency_key: str, method: str, path: str) -> bool:
        """Mark a key as in-flight. Returns False if already in-flight (concurrent duplicate)."""
        key = self._composite_key(idempotency_key, method, path)
        if key in self._in_flight:
            return False
        self._in_flight.add(key)
        return True

    def clear_in_flight(self, idempotency_key: str, method: str, path: str) -> None:
        """Remove in-flight marker after response is stored."""
        key = self._composite_key(idempotency_key, method, path)
        self._in_flight.discard(key)

    @property
    def size(self) -> int:
        """Current number of cached entries (for monitoring)."""
        return len(self._store)


# Module-level singleton so tests can inject/reset
_default_store = IdempotencyStore()


def get_idempotency_store() -> IdempotencyStore:
    """Return the module-level idempotency store."""
    return _default_store


def reset_idempotency_store() -> None:
    """Reset the store (for testing)."""
    global _default_store
    _default_store = IdempotencyStore()


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that enforces idempotent POST/PUT requests.

    When a request includes an ``Idempotency-Key`` header and uses POST or PUT,
    the middleware:
    1. Checks if a cached response exists for (key, method, path).
    2. If yes, returns the cached response immediately.
    3. If no, executes the handler, caches the response, and returns it.
    4. Requests without the header or using GET/DELETE pass through unchanged.
    """

    def __init__(self, app: Any, store: IdempotencyStore | None = None) -> None:
        super().__init__(app)
        self.store = store or get_idempotency_store()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Only apply to POST/PUT
        if request.method not in IDEMPOTENT_METHODS:
            return await call_next(request)

        # Check for Idempotency-Key header
        idempotency_key = request.headers.get(IDEMPOTENCY_HEADER)
        if not idempotency_key:
            return await call_next(request)

        # Validate key length
        if len(idempotency_key) > MAX_KEY_LENGTH:
            return JSONResponse(
                status_code=400,
                content={"detail": f"Idempotency-Key exceeds maximum length of {MAX_KEY_LENGTH}"},
            )

        method = request.method
        path = request.url.path

        # Check cache
        cached = self.store.get(idempotency_key, method, path)
        if cached is not None:
            logger.info(
                "Idempotency cache hit: key=%s method=%s path=%s",
                idempotency_key[:16],
                method,
                path,
            )
            return Response(
                content=cached.body,
                status_code=cached.status_code,
                headers={
                    **cached.headers,
                    "X-Idempotency-Replayed": "true",
                },
            )

        # Guard against concurrent duplicates
        if not self.store.mark_in_flight(idempotency_key, method, path):
            return JSONResponse(
                status_code=409,
                content={"detail": "A request with this Idempotency-Key is already being processed"},
            )

        try:
            # Execute the actual handler
            response = await call_next(request)

            # Read the response body so we can cache it
            body = b""
            async for chunk in response.body_iterator:
                if isinstance(chunk, str):
                    body += chunk.encode("utf-8")
                else:
                    body += chunk

            # Extract headers we want to cache
            cached_headers = {}
            for key, value in response.headers.items():
                if key.lower() not in ("transfer-encoding", "content-length"):
                    cached_headers[key] = value

            # Store in cache
            self.store.set(
                idempotency_key,
                method,
                path,
                CachedResponse(
                    status_code=response.status_code,
                    body=body,
                    headers=cached_headers,
                    created_at=time.monotonic(),
                ),
            )

            # Return reconstructed response
            return Response(
                content=body,
                status_code=response.status_code,
                headers=cached_headers,
            )
        finally:
            self.store.clear_in_flight(idempotency_key, method, path)
