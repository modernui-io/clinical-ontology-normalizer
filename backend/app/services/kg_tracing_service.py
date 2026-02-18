"""Distributed tracing service for Knowledge Graph operations.

This module provides OpenTelemetry-compatible tracing for KG operations:
- Span creation and management
- Trace context propagation
- Performance metrics
- Error tracking and reporting
"""
# MODULE: graph_support
# MATURITY: pilot

from __future__ import annotations

import functools
import logging
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Generator, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class SpanStatus(str, Enum):
    """Status of a tracing span."""

    OK = "ok"
    ERROR = "error"
    UNSET = "unset"


class SpanKind(str, Enum):
    """Kind of span (OpenTelemetry compatible)."""

    INTERNAL = "internal"
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"


@dataclass
class SpanContext:
    """Context for trace propagation."""

    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    trace_flags: int = 1  # 1 = sampled
    trace_state: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "trace_flags": self.trace_flags,
            "trace_state": self.trace_state,
        }


@dataclass
class Span:
    """A tracing span representing a unit of work."""

    name: str
    context: SpanContext
    kind: SpanKind = SpanKind.INTERNAL
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: datetime | None = None
    status: SpanStatus = SpanStatus.UNSET
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    links: list[SpanContext] = field(default_factory=list)
    error: str | None = None

    @property
    def duration_ms(self) -> float | None:
        """Get span duration in milliseconds."""
        if self.end_time is None:
            return None
        delta = self.end_time - self.start_time
        return delta.total_seconds() * 1000

    def set_attribute(self, key: str, value: Any) -> None:
        """Set an attribute on the span."""
        self.attributes[key] = value

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        """Add an event to the span."""
        self.events.append({
            "name": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attributes": attributes or {},
        })

    def set_status(self, status: SpanStatus, description: str | None = None) -> None:
        """Set the span status."""
        self.status = status
        if description and status == SpanStatus.ERROR:
            self.error = description

    def record_exception(self, exception: Exception) -> None:
        """Record an exception on the span."""
        self.status = SpanStatus.ERROR
        self.error = str(exception)
        self.add_event("exception", {
            "exception.type": type(exception).__name__,
            "exception.message": str(exception),
        })

    def end(self) -> None:
        """End the span."""
        if self.end_time is None:
            self.end_time = datetime.now(timezone.utc)
        if self.status == SpanStatus.UNSET:
            self.status = SpanStatus.OK

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "context": self.context.to_dict(),
            "kind": self.kind.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "status": self.status.value,
            "attributes": self.attributes,
            "events": self.events,
            "error": self.error,
        }


@dataclass
class TraceMetrics:
    """Metrics about traces."""

    total_spans: int = 0
    completed_spans: int = 0
    error_spans: int = 0
    avg_duration_ms: float = 0.0
    max_duration_ms: float = 0.0
    min_duration_ms: float = float("inf")
    spans_by_name: dict[str, int] = field(default_factory=dict)
    errors_by_name: dict[str, int] = field(default_factory=dict)

    def update(self, span: Span) -> None:
        """Update metrics with a completed span."""
        self.total_spans += 1

        if span.end_time is not None:
            self.completed_spans += 1
            duration = span.duration_ms or 0.0

            # Update duration stats
            self.max_duration_ms = max(self.max_duration_ms, duration)
            self.min_duration_ms = min(self.min_duration_ms, duration)

            # Update average
            total_duration = self.avg_duration_ms * (self.completed_spans - 1)
            self.avg_duration_ms = (total_duration + duration) / self.completed_spans

        # Track by name
        self.spans_by_name[span.name] = self.spans_by_name.get(span.name, 0) + 1

        if span.status == SpanStatus.ERROR:
            self.error_spans += 1
            self.errors_by_name[span.name] = self.errors_by_name.get(span.name, 0) + 1

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_spans": self.total_spans,
            "completed_spans": self.completed_spans,
            "error_spans": self.error_spans,
            "error_rate": self.error_spans / self.total_spans if self.total_spans > 0 else 0.0,
            "avg_duration_ms": round(self.avg_duration_ms, 2),
            "max_duration_ms": round(self.max_duration_ms, 2),
            "min_duration_ms": round(self.min_duration_ms, 2) if self.min_duration_ms != float("inf") else 0.0,
            "spans_by_name": self.spans_by_name,
            "errors_by_name": self.errors_by_name,
        }


class KGTracingService:
    """Distributed tracing service for Knowledge Graph operations.

    Provides OpenTelemetry-compatible tracing with:
    - Automatic span creation and management
    - Trace context propagation
    - Performance metrics collection
    - Error tracking and reporting
    """

    def __init__(self, service_name: str = "kg-service") -> None:
        """Initialize the tracing service."""
        self._service_name = service_name
        self._active_spans: dict[str, Span] = {}
        self._completed_spans: list[Span] = []
        self._metrics = TraceMetrics()
        self._lock = threading.RLock()
        self._max_completed_spans = 1000

        # Thread-local storage for current trace context
        self._thread_local = threading.local()

    def _generate_id(self) -> str:
        """Generate a unique ID for spans and traces."""
        return uuid.uuid4().hex[:16]

    def _get_current_context(self) -> SpanContext | None:
        """Get the current trace context from thread-local storage."""
        return getattr(self._thread_local, "current_context", None)

    def _set_current_context(self, context: SpanContext | None) -> None:
        """Set the current trace context in thread-local storage."""
        self._thread_local.current_context = context

    def start_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: dict[str, Any] | None = None,
        parent_context: SpanContext | None = None,
    ) -> Span:
        """Start a new span.

        Args:
            name: Name of the span (operation being traced)
            kind: Kind of span (internal, server, client, etc.)
            attributes: Initial attributes for the span
            parent_context: Optional parent context for linking spans

        Returns:
            The created Span
        """
        # Use provided parent or get from thread-local
        parent = parent_context or self._get_current_context()

        # Create context
        if parent:
            context = SpanContext(
                trace_id=parent.trace_id,
                span_id=self._generate_id(),
                parent_span_id=parent.span_id,
            )
        else:
            context = SpanContext(
                trace_id=self._generate_id(),
                span_id=self._generate_id(),
            )

        # Create span
        span = Span(
            name=name,
            context=context,
            kind=kind,
            attributes=attributes or {},
        )

        # Add standard attributes
        span.set_attribute("service.name", self._service_name)
        span.set_attribute("kg.operation", name)

        with self._lock:
            self._active_spans[context.span_id] = span

        # Set as current context
        self._set_current_context(context)

        return span

    def end_span(self, span: Span) -> None:
        """End a span and record metrics.

        Args:
            span: The span to end
        """
        span.end()

        with self._lock:
            # Remove from active spans
            self._active_spans.pop(span.context.span_id, None)

            # Add to completed spans (with limit)
            self._completed_spans.append(span)
            if len(self._completed_spans) > self._max_completed_spans:
                self._completed_spans = self._completed_spans[-self._max_completed_spans:]

            # Update metrics
            self._metrics.update(span)

        # Restore parent context
        if span.context.parent_span_id:
            parent = self._active_spans.get(span.context.parent_span_id)
            if parent:
                self._set_current_context(parent.context)
            else:
                self._set_current_context(None)
        else:
            self._set_current_context(None)

    @contextmanager
    def span(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: dict[str, Any] | None = None,
    ) -> Generator[Span, None, None]:
        """Context manager for creating and managing spans.

        Args:
            name: Name of the span
            kind: Kind of span
            attributes: Initial attributes

        Yields:
            The span being traced

        Example:
            with tracer.span("process_query") as span:
                span.set_attribute("query.type", "concept_lookup")
                result = process_query(...)
        """
        span = self.start_span(name, kind, attributes)
        try:
            yield span
        except Exception as e:
            span.record_exception(e)
            raise
        finally:
            self.end_span(span)

    def trace(
        self,
        name: str | None = None,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: dict[str, Any] | None = None,
    ) -> Callable[[Callable[..., T]], Callable[..., T]]:
        """Decorator for tracing functions.

        Args:
            name: Span name (defaults to function name)
            kind: Kind of span
            attributes: Initial attributes

        Returns:
            Decorated function

        Example:
            @tracer.trace("query_concepts")
            def query_concepts(cui: str) -> dict:
                ...
        """
        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            span_name = name or func.__name__

            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> T:
                with self.span(span_name, kind, attributes) as span:
                    # Add function info as attributes
                    span.set_attribute("code.function", func.__name__)
                    span.set_attribute("code.namespace", func.__module__)
                    return func(*args, **kwargs)

            return wrapper
        return decorator

    def trace_async(
        self,
        name: str | None = None,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: dict[str, Any] | None = None,
    ) -> Callable[[Callable[..., T]], Callable[..., T]]:
        """Decorator for tracing async functions.

        Args:
            name: Span name (defaults to function name)
            kind: Kind of span
            attributes: Initial attributes

        Returns:
            Decorated async function
        """
        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            span_name = name or func.__name__

            @functools.wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> T:
                span = self.start_span(span_name, kind, attributes)
                span.set_attribute("code.function", func.__name__)
                span.set_attribute("code.namespace", func.__module__)
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    span.record_exception(e)
                    raise
                finally:
                    self.end_span(span)

            return wrapper  # type: ignore
        return decorator

    def get_active_spans(self) -> list[Span]:
        """Get all active (in-progress) spans."""
        with self._lock:
            return list(self._active_spans.values())

    def get_recent_spans(self, limit: int = 100) -> list[Span]:
        """Get recent completed spans."""
        with self._lock:
            return self._completed_spans[-limit:]

    def get_spans_by_trace(self, trace_id: str) -> list[Span]:
        """Get all spans for a specific trace."""
        with self._lock:
            return [
                s for s in self._completed_spans
                if s.context.trace_id == trace_id
            ]

    def get_metrics(self) -> TraceMetrics:
        """Get tracing metrics."""
        return self._metrics

    def get_operation_stats(self, operation_name: str) -> dict[str, Any]:
        """Get statistics for a specific operation."""
        with self._lock:
            spans = [s for s in self._completed_spans if s.name == operation_name]

        if not spans:
            return {"operation": operation_name, "count": 0}

        durations = [s.duration_ms or 0.0 for s in spans]
        errors = [s for s in spans if s.status == SpanStatus.ERROR]

        return {
            "operation": operation_name,
            "count": len(spans),
            "error_count": len(errors),
            "error_rate": len(errors) / len(spans),
            "avg_duration_ms": sum(durations) / len(durations),
            "max_duration_ms": max(durations),
            "min_duration_ms": min(durations),
            "p50_duration_ms": sorted(durations)[len(durations) // 2],
            "p95_duration_ms": sorted(durations)[int(len(durations) * 0.95)] if len(durations) > 1 else durations[0],
        }

    def clear_spans(self) -> int:
        """Clear all completed spans."""
        with self._lock:
            count = len(self._completed_spans)
            self._completed_spans.clear()
            return count


# Singleton instance
_tracing_service: KGTracingService | None = None
_tracing_lock = threading.Lock()


def get_kg_tracing_service(service_name: str = "kg-service") -> KGTracingService:
    """Get the singleton tracing service instance.

    Args:
        service_name: Name of the service (only used on first call)

    Returns:
        KGTracingService instance
    """
    global _tracing_service
    if _tracing_service is None:
        with _tracing_lock:
            if _tracing_service is None:
                _tracing_service = KGTracingService(service_name)
    return _tracing_service


def reset_kg_tracing_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _tracing_service
    with _tracing_lock:
        if _tracing_service is not None:
            _tracing_service.clear_spans()
        _tracing_service = None
