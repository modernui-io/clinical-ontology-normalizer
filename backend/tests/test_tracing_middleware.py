"""Tests for P3-009: Selective tracing middleware with sampling controls."""

from __future__ import annotations

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.middleware.tracing_middleware import (
    DEFAULT_EXPENSIVE_ENDPOINTS,
    TraceRecord,
    TraceStore,
    TracingConfig,
    TracingMiddleware,
    _is_expensive,
    reset_trace_store,
    should_trace,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_app(config: TracingConfig | None = None) -> Starlette:
    """Build a tiny Starlette app with the tracing middleware."""
    store = TraceStore()

    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    async def nlp_extract(request: Request) -> JSONResponse:
        return JSONResponse({"mentions": []})

    async def clinical_agent(request: Request) -> JSONResponse:
        return JSONResponse({"answer": "test"})

    app = Starlette(
        routes=[
            Route("/api/v1/health", health),
            Route("/api/v1/nlp/extract", nlp_extract, methods=["POST"]),
            Route("/api/v1/clinical-agent/query", clinical_agent, methods=["POST"]),
        ],
    )
    cfg = config or TracingConfig(enabled=True, sample_rate=1.0, expensive_sample_rate=1.0)
    app.add_middleware(TracingMiddleware, config=cfg, store=store)
    return app


@pytest.fixture()
def traced_app() -> Starlette:
    """App with 100% tracing for deterministic tests."""
    return _make_app()


@pytest.fixture()
def client(traced_app: Starlette) -> TestClient:
    return TestClient(traced_app)


# ---------------------------------------------------------------------------
# TracingConfig tests
# ---------------------------------------------------------------------------


class TestTracingConfig:
    def test_defaults(self) -> None:
        cfg = TracingConfig()
        assert cfg.enabled is True
        assert cfg.sample_rate == 0.1
        assert cfg.expensive_sample_rate == 0.5
        assert len(cfg.expensive_endpoints) > 0

    def test_clamps_sample_rate(self) -> None:
        cfg = TracingConfig(sample_rate=2.0, expensive_sample_rate=-0.5)
        assert cfg.sample_rate == 1.0
        assert cfg.expensive_sample_rate == 0.0

    def test_custom_expensive_endpoints(self) -> None:
        cfg = TracingConfig(expensive_endpoints=["/custom/endpoint"])
        assert cfg.expensive_endpoints == ["/custom/endpoint"]


# ---------------------------------------------------------------------------
# Sampling logic tests
# ---------------------------------------------------------------------------


class TestShouldTrace:
    def test_disabled_returns_false(self) -> None:
        cfg = TracingConfig(enabled=False, sample_rate=1.0)
        assert should_trace("/api/v1/health", cfg) is False

    def test_rate_zero_returns_false(self) -> None:
        cfg = TracingConfig(enabled=True, sample_rate=0.0, expensive_sample_rate=0.0)
        assert should_trace("/api/v1/health", cfg) is False

    def test_rate_one_returns_true(self) -> None:
        cfg = TracingConfig(enabled=True, sample_rate=1.0)
        assert should_trace("/api/v1/health", cfg) is True

    def test_expensive_endpoint_uses_expensive_rate(self) -> None:
        cfg = TracingConfig(
            enabled=True,
            sample_rate=0.0,
            expensive_sample_rate=1.0,
        )
        assert should_trace("/api/v1/nlp/extract", cfg) is True
        assert should_trace("/api/v1/health", cfg) is False

    def test_is_expensive_function(self) -> None:
        assert _is_expensive("/api/v1/nlp/extract", DEFAULT_EXPENSIVE_ENDPOINTS) is True
        assert _is_expensive("/api/v1/health", DEFAULT_EXPENSIVE_ENDPOINTS) is False
        assert _is_expensive("/api/v1/clinical-agent/query", DEFAULT_EXPENSIVE_ENDPOINTS) is True
        assert _is_expensive("/api/v1/kg/build", DEFAULT_EXPENSIVE_ENDPOINTS) is True


# ---------------------------------------------------------------------------
# TraceRecord tests
# ---------------------------------------------------------------------------


class TestTraceRecord:
    def test_finalize(self) -> None:
        import time

        trace = TraceRecord(
            request_id="test-123",
            path="/api/v1/health",
            method="GET",
            start_time=time.time(),
        )
        time.sleep(0.01)
        trace.finalize(200)
        assert trace.status_code == 200
        assert trace.duration_ms > 0
        assert trace.end_time > trace.start_time

    def test_to_dict(self) -> None:
        trace = TraceRecord(
            request_id="abc",
            path="/test",
            method="GET",
            start_time=1000.0,
            end_time=1001.0,
            duration_ms=1000.0,
            status_code=200,
            is_expensive=True,
        )
        d = trace.to_dict()
        assert d["request_id"] == "abc"
        assert d["path"] == "/test"
        assert d["duration_ms"] == 1000.0
        assert d["is_expensive"] is True


# ---------------------------------------------------------------------------
# TraceStore tests
# ---------------------------------------------------------------------------


class TestTraceStore:
    def test_add_and_recent(self) -> None:
        store = TraceStore(max_traces=100)
        for i in range(5):
            store.add(
                TraceRecord(
                    request_id=f"req-{i}",
                    path="/test",
                    method="GET",
                    start_time=1000.0 + i,
                )
            )
        recent = store.recent(3)
        assert len(recent) == 3
        # Most recent first
        assert recent[0].request_id == "req-4"

    def test_bounded_size(self) -> None:
        store = TraceStore(max_traces=10)
        for i in range(20):
            store.add(
                TraceRecord(
                    request_id=f"req-{i}",
                    path="/test",
                    method="GET",
                    start_time=1000.0 + i,
                )
            )
        assert store.size <= 10

    def test_clear(self) -> None:
        store = TraceStore()
        store.add(
            TraceRecord(
                request_id="req-1",
                path="/test",
                method="GET",
                start_time=1000.0,
            )
        )
        store.clear()
        assert store.size == 0


# ---------------------------------------------------------------------------
# Middleware integration tests
# ---------------------------------------------------------------------------


class TestTracingMiddleware:
    def test_health_endpoint_traced(self, client: TestClient) -> None:
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert "X-Request-ID" in resp.headers
        assert "X-Trace-Duration-Ms" in resp.headers

    def test_duration_header_is_numeric(self, client: TestClient) -> None:
        resp = client.get("/api/v1/health")
        duration = float(resp.headers["X-Trace-Duration-Ms"])
        assert duration >= 0

    def test_custom_request_id_preserved(self, client: TestClient) -> None:
        resp = client.get(
            "/api/v1/health",
            headers={"X-Request-ID": "my-custom-id"},
        )
        assert resp.headers["X-Request-ID"] == "my-custom-id"

    def test_disabled_tracing_no_headers(self) -> None:
        app = _make_app(TracingConfig(enabled=False))
        c = TestClient(app)
        resp = c.get("/api/v1/health")
        assert resp.status_code == 200
        assert "X-Trace-Duration-Ms" not in resp.headers

    def test_zero_rate_no_tracing(self) -> None:
        app = _make_app(
            TracingConfig(enabled=True, sample_rate=0.0, expensive_sample_rate=0.0)
        )
        c = TestClient(app)
        resp = c.get("/api/v1/health")
        assert resp.status_code == 200
        assert "X-Trace-Duration-Ms" not in resp.headers

    def test_expensive_endpoint_traced(self, client: TestClient) -> None:
        resp = client.post("/api/v1/nlp/extract")
        assert resp.status_code == 200
        assert "X-Trace-Duration-Ms" in resp.headers
