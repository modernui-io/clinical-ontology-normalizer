"""Tests for IdempotencyMiddleware (P2-020).

Validates retry safety for POST/PUT endpoints by checking:
- Cache hit returns replayed response with X-Idempotency-Replayed header
- GET/DELETE requests are unaffected
- Missing header passes through
- Key length validation
- Concurrent duplicate detection (409)
- TTL expiration
- Different methods/paths produce different cache entries
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.middleware.idempotency_middleware import (
    IDEMPOTENCY_HEADER,
    CachedResponse,
    IdempotencyMiddleware,
    IdempotencyStore,
)


# ---------------------------------------------------------------------------
# Test app
# ---------------------------------------------------------------------------

async def _echo_handler(request: Request) -> JSONResponse:
    """Simple handler that echoes the method and path."""
    body = await request.body()
    return JSONResponse(
        {"method": request.method, "path": request.url.path, "body": body.decode()},
        status_code=201,
    )


async def _get_handler(request: Request) -> JSONResponse:
    return JSONResponse({"method": "GET"})


def _build_test_app(store: IdempotencyStore | None = None) -> Starlette:
    """Build a minimal Starlette app with the idempotency middleware."""
    app = Starlette(
        routes=[
            Route("/api/v1/documents", _echo_handler, methods=["POST", "PUT"]),
            Route("/api/v1/documents", _get_handler, methods=["GET"]),
            Route("/api/v1/other", _echo_handler, methods=["POST"]),
        ],
    )
    s = store or IdempotencyStore()
    app.add_middleware(IdempotencyMiddleware, store=s)
    return app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def store() -> IdempotencyStore:
    return IdempotencyStore(ttl_seconds=60)


@pytest.fixture
def test_app(store: IdempotencyStore) -> Starlette:
    return _build_test_app(store)


@pytest.fixture
async def client(test_app: Starlette) -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# Unit tests for IdempotencyStore
# ---------------------------------------------------------------------------

class TestIdempotencyStore:
    """Unit tests for the in-memory TTL store."""

    def test_get_returns_none_for_missing_key(self, store: IdempotencyStore) -> None:
        assert store.get("missing", "POST", "/path") is None

    def test_set_and_get_returns_cached(self, store: IdempotencyStore) -> None:
        cached = CachedResponse(
            status_code=201,
            body=b'{"ok":true}',
            headers={"content-type": "application/json"},
            created_at=time.monotonic(),
        )
        store.set("key1", "POST", "/path", cached)
        result = store.get("key1", "POST", "/path")
        assert result is not None
        assert result.status_code == 201
        assert result.body == b'{"ok":true}'

    def test_different_methods_are_separate(self, store: IdempotencyStore) -> None:
        cached = CachedResponse(
            status_code=200, body=b"x", headers={}, created_at=time.monotonic()
        )
        store.set("key1", "POST", "/path", cached)
        assert store.get("key1", "PUT", "/path") is None

    def test_different_paths_are_separate(self, store: IdempotencyStore) -> None:
        cached = CachedResponse(
            status_code=200, body=b"x", headers={}, created_at=time.monotonic()
        )
        store.set("key1", "POST", "/a", cached)
        assert store.get("key1", "POST", "/b") is None

    def test_expired_entry_returns_none(self) -> None:
        store = IdempotencyStore(ttl_seconds=0)
        cached = CachedResponse(
            status_code=200,
            body=b"x",
            headers={},
            created_at=time.monotonic() - 1,
        )
        store.set("key1", "POST", "/path", cached)
        assert store.get("key1", "POST", "/path") is None

    def test_mark_in_flight(self, store: IdempotencyStore) -> None:
        assert store.mark_in_flight("k", "POST", "/p") is True
        assert store.mark_in_flight("k", "POST", "/p") is False  # already in flight

    def test_clear_in_flight(self, store: IdempotencyStore) -> None:
        store.mark_in_flight("k", "POST", "/p")
        store.clear_in_flight("k", "POST", "/p")
        assert store.mark_in_flight("k", "POST", "/p") is True  # can re-mark

    def test_size_property(self, store: IdempotencyStore) -> None:
        assert store.size == 0
        cached = CachedResponse(
            status_code=200, body=b"", headers={}, created_at=time.monotonic()
        )
        store.set("k1", "POST", "/a", cached)
        store.set("k2", "POST", "/b", cached)
        assert store.size == 2


# ---------------------------------------------------------------------------
# Integration tests with the middleware
# ---------------------------------------------------------------------------

class TestIdempotencyMiddleware:
    """Integration tests for the full middleware stack."""

    @pytest.mark.asyncio
    async def test_post_without_header_passes_through(self, client: AsyncClient) -> None:
        """POST without Idempotency-Key should execute normally."""
        r = await client.post("/api/v1/documents", content=b"hello")
        assert r.status_code == 201
        assert "X-Idempotency-Replayed" not in r.headers

    @pytest.mark.asyncio
    async def test_get_ignores_idempotency_header(self, client: AsyncClient) -> None:
        """GET requests should never use idempotency logic."""
        r = await client.get(
            "/api/v1/documents",
            headers={IDEMPOTENCY_HEADER: "get-key-1"},
        )
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_first_post_with_key_returns_original(self, client: AsyncClient) -> None:
        """First POST with a key should execute the handler and return 201."""
        r = await client.post(
            "/api/v1/documents",
            content=b"data",
            headers={IDEMPOTENCY_HEADER: "unique-key-1"},
        )
        assert r.status_code == 201
        assert "X-Idempotency-Replayed" not in r.headers

    @pytest.mark.asyncio
    async def test_second_post_with_same_key_returns_cached(
        self, client: AsyncClient
    ) -> None:
        """Second POST with the same key should return cached response."""
        headers = {IDEMPOTENCY_HEADER: "dup-key-1"}
        r1 = await client.post("/api/v1/documents", content=b"data", headers=headers)
        assert r1.status_code == 201

        r2 = await client.post("/api/v1/documents", content=b"data", headers=headers)
        assert r2.status_code == 201
        assert r2.headers.get("X-Idempotency-Replayed") == "true"
        assert r1.json() == r2.json()

    @pytest.mark.asyncio
    async def test_same_key_different_path_not_cached(
        self, client: AsyncClient
    ) -> None:
        """Same key on different path should be treated as separate requests."""
        key = "cross-path-key"
        r1 = await client.post(
            "/api/v1/documents",
            content=b"a",
            headers={IDEMPOTENCY_HEADER: key},
        )
        r2 = await client.post(
            "/api/v1/other",
            content=b"b",
            headers={IDEMPOTENCY_HEADER: key},
        )
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert "X-Idempotency-Replayed" not in r2.headers

    @pytest.mark.asyncio
    async def test_key_too_long_returns_400(self, client: AsyncClient) -> None:
        """Idempotency key exceeding max length should return 400."""
        long_key = "x" * 300
        r = await client.post(
            "/api/v1/documents",
            content=b"data",
            headers={IDEMPOTENCY_HEADER: long_key},
        )
        assert r.status_code == 400
        assert "maximum length" in r.json()["detail"]

    @pytest.mark.asyncio
    async def test_put_also_uses_idempotency(self, client: AsyncClient) -> None:
        """PUT requests should also support idempotency."""
        headers = {IDEMPOTENCY_HEADER: "put-key-1"}
        r1 = await client.put("/api/v1/documents", content=b"update", headers=headers)
        assert r1.status_code == 201

        r2 = await client.put("/api/v1/documents", content=b"update", headers=headers)
        assert r2.status_code == 201
        assert r2.headers.get("X-Idempotency-Replayed") == "true"
