"""P3-009: Selective tracing middleware with sampling controls.

Traces expensive endpoints at a configurable higher sample rate while
keeping a lower base rate for all other traffic. Trace data is emitted
via structured logging and can be forwarded to any tracing backend.

Configuration via environment variables:
    TRACING_ENABLED          - Enable/disable tracing (default: true)
    TRACING_SAMPLE_RATE      - Base sample rate 0.0-1.0 (default: 0.1)
    TRACING_EXPENSIVE_RATE   - Sample rate for expensive endpoints (default: 0.5)
"""

from __future__ import annotations

import logging
import os
import random
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default expensive endpoints (high-latency or high-compute)
# ---------------------------------------------------------------------------

DEFAULT_EXPENSIVE_ENDPOINTS: list[str] = [
    "/api/v1/clinical-agent/query",
    "/api/v1/nlp/extract",
    "/api/v1/kg/build",
    "/api/v1/graph-rag/query",
    "/api/v1/guideline-rag/query",
    "/api/v1/pipelines/execute",
]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class TracingConfig:
    """Runtime configuration for the tracing middleware."""

    enabled: bool = True
    sample_rate: float = 0.1  # base rate for all endpoints
    expensive_endpoints: list[str] = field(
        default_factory=lambda: list(DEFAULT_EXPENSIVE_ENDPOINTS)
    )
    expensive_sample_rate: float = 0.5  # higher rate for expensive endpoints

    def __post_init__(self) -> None:
        self.sample_rate = max(0.0, min(1.0, self.sample_rate))
        self.expensive_sample_rate = max(0.0, min(1.0, self.expensive_sample_rate))


def _config_from_env() -> TracingConfig:
    """Build TracingConfig from environment variables."""
    enabled_raw = os.environ.get("TRACING_ENABLED", "true").lower()
    enabled = enabled_raw in ("true", "1", "yes")

    sample_rate = float(os.environ.get("TRACING_SAMPLE_RATE", "0.1"))
    expensive_rate = float(os.environ.get("TRACING_EXPENSIVE_RATE", "0.5"))

    return TracingConfig(
        enabled=enabled,
        sample_rate=sample_rate,
        expensive_sample_rate=expensive_rate,
    )


# ---------------------------------------------------------------------------
# Trace data
# ---------------------------------------------------------------------------


@dataclass
class TraceRecord:
    """A single request trace record."""

    request_id: str
    path: str
    method: str
    start_time: float
    end_time: float = 0.0
    duration_ms: float = 0.0
    status_code: int = 0
    is_expensive: bool = False
    sampled: bool = True

    def finalize(self, status_code: int) -> None:
        """Set end time, duration, and status code."""
        self.end_time = time.time()
        self.duration_ms = round((self.end_time - self.start_time) * 1000, 2)
        self.status_code = status_code

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for structured logging / export."""
        return {
            "request_id": self.request_id,
            "path": self.path,
            "method": self.method,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "status_code": self.status_code,
            "is_expensive": self.is_expensive,
        }


# ---------------------------------------------------------------------------
# Sampling logic
# ---------------------------------------------------------------------------


def _is_expensive(path: str, expensive_endpoints: list[str]) -> bool:
    """Check whether *path* matches any expensive endpoint prefix."""
    for ep in expensive_endpoints:
        if path.startswith(ep):
            return True
    return False


def should_trace(path: str, config: TracingConfig) -> bool:
    """Decide whether to trace this request based on config and sampling.

    Expensive endpoints use *expensive_sample_rate*; all others use
    the base *sample_rate*. A random float is compared to the rate.
    """
    if not config.enabled:
        return False

    rate = (
        config.expensive_sample_rate
        if _is_expensive(path, config.expensive_endpoints)
        else config.sample_rate
    )

    if rate >= 1.0:
        return True
    if rate <= 0.0:
        return False

    return random.random() < rate


# ---------------------------------------------------------------------------
# In-memory trace store (bounded)
# ---------------------------------------------------------------------------

_MAX_STORED_TRACES = 1000


class TraceStore:
    """Bounded in-memory trace store for recent request traces."""

    def __init__(self, max_traces: int = _MAX_STORED_TRACES) -> None:
        self._traces: list[TraceRecord] = []
        self._max = max_traces

    def add(self, trace: TraceRecord) -> None:
        if len(self._traces) >= self._max:
            # Drop oldest quarter
            self._traces = self._traces[self._max // 4 :]
        self._traces.append(trace)

    def recent(self, limit: int = 50) -> list[TraceRecord]:
        return list(reversed(self._traces[-limit:]))

    def clear(self) -> None:
        self._traces.clear()

    @property
    def size(self) -> int:
        return len(self._traces)


# Module-level singleton
_default_store = TraceStore()


def get_trace_store() -> TraceStore:
    return _default_store


def reset_trace_store() -> None:
    global _default_store
    _default_store = TraceStore()


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class TracingMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that selectively traces requests.

    Emits structured log entries for sampled requests and stores trace
    records in an in-memory buffer for dashboard retrieval.
    """

    def __init__(
        self,
        app: Any,
        config: TracingConfig | None = None,
        store: TraceStore | None = None,
    ) -> None:
        super().__init__(app)
        self.config = config or _config_from_env()
        self.store = store or get_trace_store()

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path
        method = request.method

        if not should_trace(path, self.config):
            return await call_next(request)

        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        trace = TraceRecord(
            request_id=request_id,
            path=path,
            method=method,
            start_time=time.time(),
            is_expensive=_is_expensive(path, self.config.expensive_endpoints),
        )

        response = await call_next(request)

        trace.finalize(response.status_code)
        self.store.add(trace)

        # Structured log
        logger.info(
            "trace: %s %s %dms status=%d request_id=%s expensive=%s",
            method,
            path,
            trace.duration_ms,
            trace.status_code,
            request_id,
            trace.is_expensive,
        )

        # Add trace headers to response
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Trace-Duration-Ms"] = str(trace.duration_ms)

        return response
