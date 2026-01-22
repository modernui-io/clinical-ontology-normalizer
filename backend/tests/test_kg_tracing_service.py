"""Tests for Knowledge Graph Tracing Service."""

from __future__ import annotations

import asyncio
import time

import pytest

from app.services.kg_tracing_service import (
    KGTracingService,
    Span,
    SpanContext,
    SpanKind,
    SpanStatus,
    TraceMetrics,
    get_kg_tracing_service,
    reset_kg_tracing_service,
)


class TestSpanContext:
    """Test SpanContext dataclass."""

    def test_context_creation(self) -> None:
        """Test creating a span context."""
        context = SpanContext(
            trace_id="abc123",
            span_id="def456",
            parent_span_id="parent123",
        )
        assert context.trace_id == "abc123"
        assert context.span_id == "def456"
        assert context.parent_span_id == "parent123"

    def test_context_to_dict(self) -> None:
        """Test converting context to dictionary."""
        context = SpanContext(
            trace_id="abc123",
            span_id="def456",
        )
        data = context.to_dict()
        assert data["trace_id"] == "abc123"
        assert data["span_id"] == "def456"


class TestSpan:
    """Test Span dataclass."""

    def test_span_creation(self) -> None:
        """Test creating a span."""
        context = SpanContext(trace_id="t1", span_id="s1")
        span = Span(name="test_operation", context=context)

        assert span.name == "test_operation"
        assert span.status == SpanStatus.UNSET
        assert span.end_time is None

    def test_span_set_attribute(self) -> None:
        """Test setting span attributes."""
        context = SpanContext(trace_id="t1", span_id="s1")
        span = Span(name="test", context=context)

        span.set_attribute("key1", "value1")
        span.set_attribute("key2", 42)

        assert span.attributes["key1"] == "value1"
        assert span.attributes["key2"] == 42

    def test_span_add_event(self) -> None:
        """Test adding events to span."""
        context = SpanContext(trace_id="t1", span_id="s1")
        span = Span(name="test", context=context)

        span.add_event("processing_started", {"step": 1})
        span.add_event("processing_completed")

        assert len(span.events) == 2
        assert span.events[0]["name"] == "processing_started"
        assert span.events[0]["attributes"]["step"] == 1

    def test_span_set_status(self) -> None:
        """Test setting span status."""
        context = SpanContext(trace_id="t1", span_id="s1")
        span = Span(name="test", context=context)

        span.set_status(SpanStatus.OK)
        assert span.status == SpanStatus.OK

        span.set_status(SpanStatus.ERROR, "Something went wrong")
        assert span.status == SpanStatus.ERROR
        assert span.error == "Something went wrong"

    def test_span_record_exception(self) -> None:
        """Test recording exception on span."""
        context = SpanContext(trace_id="t1", span_id="s1")
        span = Span(name="test", context=context)

        try:
            raise ValueError("Test error")
        except ValueError as e:
            span.record_exception(e)

        assert span.status == SpanStatus.ERROR
        assert "Test error" in span.error
        assert len(span.events) == 1
        assert span.events[0]["name"] == "exception"

    def test_span_end(self) -> None:
        """Test ending a span."""
        context = SpanContext(trace_id="t1", span_id="s1")
        span = Span(name="test", context=context)

        assert span.end_time is None
        span.end()

        assert span.end_time is not None
        assert span.status == SpanStatus.OK

    def test_span_duration(self) -> None:
        """Test span duration calculation."""
        context = SpanContext(trace_id="t1", span_id="s1")
        span = Span(name="test", context=context)

        time.sleep(0.01)  # 10ms
        span.end()

        assert span.duration_ms is not None
        assert span.duration_ms >= 10

    def test_span_to_dict(self) -> None:
        """Test converting span to dictionary."""
        context = SpanContext(trace_id="t1", span_id="s1")
        span = Span(name="test", context=context)
        span.set_attribute("key", "value")
        span.end()

        data = span.to_dict()
        assert data["name"] == "test"
        assert data["context"]["trace_id"] == "t1"
        assert data["attributes"]["key"] == "value"
        assert data["duration_ms"] is not None


class TestTraceMetrics:
    """Test TraceMetrics dataclass."""

    def test_metrics_defaults(self) -> None:
        """Test default metrics."""
        metrics = TraceMetrics()
        assert metrics.total_spans == 0
        assert metrics.error_spans == 0

    def test_metrics_update(self) -> None:
        """Test updating metrics with spans."""
        metrics = TraceMetrics()

        context = SpanContext(trace_id="t1", span_id="s1")
        span = Span(name="operation1", context=context)
        span.end()

        metrics.update(span)

        assert metrics.total_spans == 1
        assert metrics.completed_spans == 1
        assert "operation1" in metrics.spans_by_name

    def test_metrics_error_tracking(self) -> None:
        """Test error tracking in metrics."""
        metrics = TraceMetrics()

        context = SpanContext(trace_id="t1", span_id="s1")
        span = Span(name="failed_op", context=context)
        span.set_status(SpanStatus.ERROR, "Failed")
        span.end()

        metrics.update(span)

        assert metrics.error_spans == 1
        assert "failed_op" in metrics.errors_by_name

    def test_metrics_to_dict(self) -> None:
        """Test converting metrics to dictionary."""
        metrics = TraceMetrics(
            total_spans=100,
            completed_spans=95,
            error_spans=5,
        )
        data = metrics.to_dict()

        assert data["total_spans"] == 100
        assert data["error_rate"] == 0.05


class TestKGTracingService:
    """Test KG tracing service."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self) -> None:
        """Reset singleton before each test."""
        reset_kg_tracing_service()

    def test_service_creation(self) -> None:
        """Test creating the tracing service."""
        service = KGTracingService("test-service")
        assert service is not None

    def test_start_end_span(self) -> None:
        """Test starting and ending a span."""
        service = KGTracingService()

        span = service.start_span("test_operation")
        assert span.name == "test_operation"
        assert span.context.trace_id is not None

        service.end_span(span)
        assert span.end_time is not None

    def test_span_hierarchy(self) -> None:
        """Test parent-child span relationships."""
        service = KGTracingService()

        parent = service.start_span("parent_op")
        child = service.start_span("child_op")

        assert child.context.parent_span_id == parent.context.span_id
        assert child.context.trace_id == parent.context.trace_id

        service.end_span(child)
        service.end_span(parent)

    def test_span_context_manager(self) -> None:
        """Test span context manager."""
        service = KGTracingService()

        with service.span("operation") as span:
            span.set_attribute("key", "value")

        assert span.end_time is not None
        assert span.attributes["key"] == "value"

    def test_span_context_manager_exception(self) -> None:
        """Test span context manager with exception."""
        service = KGTracingService()

        with pytest.raises(ValueError):
            with service.span("failing_operation") as span:
                raise ValueError("Test error")

        assert span.status == SpanStatus.ERROR
        assert span.error is not None

    def test_trace_decorator(self) -> None:
        """Test trace decorator."""
        service = KGTracingService()

        @service.trace("decorated_operation")
        def my_function(x: int) -> int:
            return x * 2

        result = my_function(5)
        assert result == 10

        recent = service.get_recent_spans(1)
        assert len(recent) == 1
        assert recent[0].name == "decorated_operation"

    def test_trace_decorator_with_exception(self) -> None:
        """Test trace decorator with exception."""
        service = KGTracingService()

        @service.trace("failing_function")
        def failing_function() -> None:
            raise RuntimeError("Test error")

        with pytest.raises(RuntimeError):
            failing_function()

        recent = service.get_recent_spans(1)
        assert len(recent) == 1
        assert recent[0].status == SpanStatus.ERROR

    def test_get_active_spans(self) -> None:
        """Test getting active spans."""
        service = KGTracingService()

        span1 = service.start_span("active1")
        span2 = service.start_span("active2")

        active = service.get_active_spans()
        assert len(active) == 2

        service.end_span(span2)
        service.end_span(span1)

        active = service.get_active_spans()
        assert len(active) == 0

    def test_get_recent_spans(self) -> None:
        """Test getting recent completed spans."""
        service = KGTracingService()

        for i in range(5):
            with service.span(f"operation_{i}"):
                pass

        recent = service.get_recent_spans(3)
        assert len(recent) == 3

    def test_get_spans_by_trace(self) -> None:
        """Test getting spans by trace ID."""
        service = KGTracingService()

        with service.span("parent") as parent:
            trace_id = parent.context.trace_id
            with service.span("child1"):
                pass
            with service.span("child2"):
                pass

        spans = service.get_spans_by_trace(trace_id)
        assert len(spans) == 3

    def test_get_metrics(self) -> None:
        """Test getting tracing metrics."""
        service = KGTracingService()

        with service.span("op1"):
            pass
        with service.span("op2"):
            pass

        try:
            with service.span("failing_op"):
                raise ValueError("Error")
        except ValueError:
            pass

        metrics = service.get_metrics()
        assert metrics.total_spans == 3
        assert metrics.error_spans == 1

    def test_get_operation_stats(self) -> None:
        """Test getting stats for specific operation."""
        service = KGTracingService()

        for _ in range(10):
            with service.span("repeated_op"):
                time.sleep(0.001)

        stats = service.get_operation_stats("repeated_op")
        assert stats["operation"] == "repeated_op"
        assert stats["count"] == 10
        assert stats["avg_duration_ms"] > 0

    def test_clear_spans(self) -> None:
        """Test clearing completed spans."""
        service = KGTracingService()

        for i in range(5):
            with service.span(f"op_{i}"):
                pass

        count = service.clear_spans()
        assert count == 5

        recent = service.get_recent_spans()
        assert len(recent) == 0


class TestSingleton:
    """Test singleton pattern."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self) -> None:
        """Reset singleton before each test."""
        reset_kg_tracing_service()

    def test_singleton_returns_same_instance(self) -> None:
        """Test that singleton returns same instance."""
        service1 = get_kg_tracing_service()
        service2 = get_kg_tracing_service()
        assert service1 is service2

    def test_reset_singleton(self) -> None:
        """Test resetting singleton."""
        service1 = get_kg_tracing_service()
        reset_kg_tracing_service()
        service2 = get_kg_tracing_service()
        assert service1 is not service2


class TestAsyncTracing:
    """Test async tracing functionality."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self) -> None:
        """Reset singleton before each test."""
        reset_kg_tracing_service()

    @pytest.mark.asyncio
    async def test_trace_async_decorator(self) -> None:
        """Test trace_async decorator."""
        service = KGTracingService()

        @service.trace_async("async_operation")
        async def async_function(x: int) -> int:
            await asyncio.sleep(0.001)
            return x * 2

        result = await async_function(5)
        assert result == 10

        recent = service.get_recent_spans(1)
        assert len(recent) == 1
        assert recent[0].name == "async_operation"

    @pytest.mark.asyncio
    async def test_trace_async_with_exception(self) -> None:
        """Test trace_async with exception."""
        service = KGTracingService()

        @service.trace_async("failing_async")
        async def failing_async() -> None:
            await asyncio.sleep(0.001)
            raise RuntimeError("Async error")

        with pytest.raises(RuntimeError):
            await failing_async()

        recent = service.get_recent_spans(1)
        assert len(recent) == 1
        assert recent[0].status == SpanStatus.ERROR
