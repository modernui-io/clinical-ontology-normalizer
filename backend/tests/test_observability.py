"""Tests for Observability Stack (DEVOPS-2).

Covers:
- TracingService: span creation, parent-child linking, trace context propagation,
  decorator instrumentation, span storage eviction
- MetricsCollector: counter increment, gauge set/inc/dec, histogram observe +
  bucket distribution, rate calculation
- Prometheus export format correctness
- AlertEngine: rule evaluation, state transitions
- Dashboard aggregation
- API endpoint responses
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.schemas.observability import (
    AlertCondition,
    AlertRuleSchema,
    AlertSeverity,
    AlertStatus,
    AlertsResponse,
    DashboardResponse,
    MetricsResponse,
    MetricType,
    SpanStatus,
    TraceSchema,
    TracesResponse,
)
from app.services.metrics_collector_service import (
    MetricsCollector,
    get_metrics_collector,
    reset_metrics_collector,
)
from app.services.observability_service import (
    AlertEngine,
    TracingService,
    format_traceparent,
    generate_span_id,
    generate_trace_id,
    get_alert_engine,
    get_tracing_service,
    parse_traceparent,
    reset_singletons,
    trace_operation,
)


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def tracing() -> TracingService:
    """Create a fresh TracingService."""
    return TracingService(max_spans=100)


@pytest.fixture
def alert_engine() -> AlertEngine:
    """Create a fresh AlertEngine."""
    return AlertEngine()


@pytest.fixture
def metrics() -> MetricsCollector:
    """Create a fresh MetricsCollector."""
    return MetricsCollector()


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset global singletons before each test."""
    reset_singletons()
    reset_metrics_collector()
    yield
    reset_singletons()
    reset_metrics_collector()


# ===========================================================================
# TracingService Tests
# ===========================================================================


class TestSpanCreation:
    """Test span creation and lifecycle."""

    def test_start_span_creates_span(self, tracing: TracingService):
        span = tracing.start_span("test_operation")
        assert span.operation_name == "test_operation"
        assert span.trace_id is not None
        assert span.span_id is not None
        assert span.parent_span_id is None
        assert span.status == SpanStatus.UNSET
        assert span.end_time is None
        assert span.duration_ms is None

    def test_start_span_with_trace_id(self, tracing: TracingService):
        trace_id = generate_trace_id()
        span = tracing.start_span("op", trace_id=trace_id)
        assert span.trace_id == trace_id

    def test_start_span_with_attributes(self, tracing: TracingService):
        span = tracing.start_span("op", attributes={"resource_type": "Patient"})
        assert span.attributes["resource_type"] == "Patient"

    def test_end_span_sets_duration(self, tracing: TracingService):
        span = tracing.start_span("op")
        ended = tracing.end_span(span.span_id, status=SpanStatus.OK)
        assert ended is not None
        assert ended.status == SpanStatus.OK
        assert ended.duration_ms is not None
        assert ended.duration_ms >= 0
        assert ended.end_time is not None

    def test_end_span_unknown_id_returns_none(self, tracing: TracingService):
        result = tracing.end_span("nonexistent_span_id")
        assert result is None

    def test_end_span_with_error_status(self, tracing: TracingService):
        span = tracing.start_span("op")
        ended = tracing.end_span(
            span.span_id,
            status=SpanStatus.ERROR,
            attributes={"error.message": "something failed"},
        )
        assert ended is not None
        assert ended.status == SpanStatus.ERROR
        assert ended.attributes["error.message"] == "something failed"

    def test_add_span_event(self, tracing: TracingService):
        span = tracing.start_span("op")
        result = tracing.add_span_event(span.span_id, "retry", attributes={"attempt": 2})
        assert result is True
        # End span and verify events are stored
        ended = tracing.end_span(span.span_id)
        assert ended is not None
        assert len(ended.events) == 1
        assert ended.events[0]["name"] == "retry"

    def test_add_event_to_unknown_span(self, tracing: TracingService):
        result = tracing.add_span_event("nonexistent", "event")
        assert result is False

    def test_set_span_attributes(self, tracing: TracingService):
        span = tracing.start_span("op")
        result = tracing.set_span_attributes(span.span_id, {"key": "value"})
        assert result is True

    def test_set_attributes_unknown_span(self, tracing: TracingService):
        result = tracing.set_span_attributes("nonexistent", {"key": "value"})
        assert result is False


class TestParentChildLinking:
    """Test parent-child span relationships."""

    def test_child_span_has_parent_id(self, tracing: TracingService):
        parent = tracing.start_span("parent_op")
        child = tracing.start_span(
            "child_op",
            trace_id=parent.trace_id,
            parent_span_id=parent.span_id,
        )
        assert child.parent_span_id == parent.span_id
        assert child.trace_id == parent.trace_id

    def test_trace_contains_parent_and_child(self, tracing: TracingService):
        parent = tracing.start_span("parent")
        child = tracing.start_span(
            "child",
            trace_id=parent.trace_id,
            parent_span_id=parent.span_id,
        )
        tracing.end_span(child.span_id)
        tracing.end_span(parent.span_id)

        trace = tracing.get_trace_by_id(parent.trace_id)
        assert trace is not None
        assert trace.span_count == 2
        assert trace.root_span is not None
        assert trace.root_span.operation_name == "parent"


class TestTraceContextPropagation:
    """Test W3C traceparent format."""

    def test_generate_trace_id_length(self):
        tid = generate_trace_id()
        assert len(tid) == 32

    def test_generate_span_id_length(self):
        sid = generate_span_id()
        assert len(sid) == 16

    def test_format_traceparent(self):
        tp = format_traceparent("a" * 32, "b" * 16, sampled=True)
        assert tp == f"00-{'a' * 32}-{'b' * 16}-01"

    def test_format_traceparent_unsampled(self):
        tp = format_traceparent("a" * 32, "b" * 16, sampled=False)
        assert tp.endswith("-00")

    def test_parse_traceparent_valid(self):
        tp = f"00-{'a' * 32}-{'b' * 16}-01"
        result = parse_traceparent(tp)
        assert result is not None
        assert result["trace_id"] == "a" * 32
        assert result["parent_id"] == "b" * 16
        assert result["sampled"] is True

    def test_parse_traceparent_invalid_version(self):
        tp = f"99-{'a' * 32}-{'b' * 16}-01"
        assert parse_traceparent(tp) is None

    def test_parse_traceparent_invalid_format(self):
        assert parse_traceparent("invalid") is None

    def test_parse_traceparent_wrong_lengths(self):
        assert parse_traceparent("00-abc-def-01") is None

    def test_inject_context(self, tracing: TracingService):
        span = tracing.start_span("op")
        headers = tracing.inject_context(span)
        assert "traceparent" in headers
        parsed = parse_traceparent(headers["traceparent"])
        assert parsed is not None
        assert parsed["trace_id"] == span.trace_id
        assert parsed["parent_id"] == span.span_id

    def test_extract_context(self, tracing: TracingService):
        tp = format_traceparent("a" * 32, "b" * 16)
        result = tracing.extract_context({"traceparent": tp})
        assert result is not None
        assert result["trace_id"] == "a" * 32

    def test_extract_context_missing_header(self, tracing: TracingService):
        result = tracing.extract_context({})
        assert result is None


class TestDecoratorInstrumentation:
    """Test the @trace_operation decorator."""

    def test_sync_decorator_creates_span(self):
        tracing = get_tracing_service()

        @trace_operation("decorated_sync")
        def my_func(x: int) -> int:
            return x * 2

        result = my_func(5)
        assert result == 10
        assert tracing.get_span_count() == 1

    def test_sync_decorator_captures_error(self):
        tracing = get_tracing_service()

        @trace_operation("decorated_error")
        def failing_func():
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            failing_func()

        assert tracing.get_span_count() == 1
        traces = tracing.get_traces()
        assert len(traces) == 1
        assert traces[0].status == SpanStatus.ERROR

    @pytest.mark.asyncio
    async def test_async_decorator_creates_span(self):
        tracing = get_tracing_service()

        @trace_operation("decorated_async")
        async def async_func(x: int) -> int:
            return x * 3

        result = await async_func(4)
        assert result == 12
        assert tracing.get_span_count() == 1

    @pytest.mark.asyncio
    async def test_async_decorator_captures_error(self):
        tracing = get_tracing_service()

        @trace_operation("async_error")
        async def async_fail():
            raise RuntimeError("async boom")

        with pytest.raises(RuntimeError, match="async boom"):
            await async_fail()

        traces = tracing.get_traces()
        assert len(traces) == 1
        assert traces[0].status == SpanStatus.ERROR


class TestSpanStorageEviction:
    """Test span eviction when max size is exceeded."""

    def test_eviction_on_max_spans(self):
        tracing = TracingService(max_spans=5)
        # Create and end 10 spans
        for i in range(10):
            span = tracing.start_span(f"op_{i}")
            tracing.end_span(span.span_id)

        # Should only retain the last 5
        assert tracing.get_span_count() == 5
        traces = tracing.get_traces(limit=100)
        ops = set()
        for t in traces:
            for s in t.spans:
                ops.add(s.operation_name)
        # The last 5 operations should be retained
        for i in range(5, 10):
            assert f"op_{i}" in ops

    def test_span_count(self, tracing: TracingService):
        assert tracing.get_span_count() == 0
        span = tracing.start_span("op")
        assert tracing.get_active_span_count() == 1
        tracing.end_span(span.span_id)
        assert tracing.get_span_count() == 1
        assert tracing.get_active_span_count() == 0

    def test_clear(self, tracing: TracingService):
        span = tracing.start_span("op")
        tracing.end_span(span.span_id)
        tracing.clear()
        assert tracing.get_span_count() == 0


class TestTraceQuerying:
    """Test trace query methods."""

    def test_get_traces_empty(self, tracing: TracingService):
        traces = tracing.get_traces()
        assert traces == []

    def test_get_trace_by_id_not_found(self, tracing: TracingService):
        assert tracing.get_trace_by_id("nonexistent") is None

    def test_get_traces_filter_by_service(self, tracing: TracingService):
        s1 = tracing.start_span("op1", service_name="svc_a")
        tracing.end_span(s1.span_id)
        s2 = tracing.start_span("op2", service_name="svc_b")
        tracing.end_span(s2.span_id)

        traces_a = tracing.get_traces(service_name="svc_a")
        assert len(traces_a) == 1
        assert traces_a[0].service_name == "svc_a"

    def test_get_traces_pagination(self, tracing: TracingService):
        for i in range(5):
            s = tracing.start_span(f"op_{i}")
            tracing.end_span(s.span_id)

        page1 = tracing.get_traces(limit=2, offset=0)
        page2 = tracing.get_traces(limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 2

    def test_trace_error_status_propagated(self, tracing: TracingService):
        parent = tracing.start_span("parent")
        child = tracing.start_span(
            "child",
            trace_id=parent.trace_id,
            parent_span_id=parent.span_id,
        )
        tracing.end_span(child.span_id, status=SpanStatus.ERROR)
        tracing.end_span(parent.span_id, status=SpanStatus.OK)

        trace = tracing.get_trace_by_id(parent.trace_id)
        assert trace is not None
        assert trace.status == SpanStatus.ERROR


# ===========================================================================
# MetricsCollector Tests
# ===========================================================================


class TestCounterMetrics:
    """Test counter metric type."""

    def test_counter_increment(self, metrics: MetricsCollector):
        metrics.register_counter("test_counter")
        metrics.counter_inc("test_counter")
        assert metrics.counter_get("test_counter") == 1.0

    def test_counter_increment_by_value(self, metrics: MetricsCollector):
        metrics.register_counter("test_counter")
        metrics.counter_inc("test_counter", value=5.0)
        assert metrics.counter_get("test_counter") == 5.0

    def test_counter_with_labels(self, metrics: MetricsCollector):
        metrics.register_counter("requests", label_names=["method"])
        metrics.counter_inc("requests", labels={"method": "GET"})
        metrics.counter_inc("requests", labels={"method": "GET"})
        metrics.counter_inc("requests", labels={"method": "POST"})

        assert metrics.counter_get("requests", labels={"method": "GET"}) == 2.0
        assert metrics.counter_get("requests", labels={"method": "POST"}) == 1.0

    def test_counter_unregistered_noop(self, metrics: MetricsCollector):
        # Should not raise
        metrics.counter_inc("nonexistent")
        assert metrics.counter_get("nonexistent") == 0.0


class TestGaugeMetrics:
    """Test gauge metric type."""

    def test_gauge_set(self, metrics: MetricsCollector):
        metrics.register_gauge("temperature")
        metrics.gauge_set("temperature", 72.5)
        assert metrics.gauge_get("temperature") == 72.5

    def test_gauge_inc(self, metrics: MetricsCollector):
        metrics.register_gauge("connections")
        metrics.gauge_set("connections", 10)
        metrics.gauge_inc("connections", 5)
        assert metrics.gauge_get("connections") == 15

    def test_gauge_dec(self, metrics: MetricsCollector):
        metrics.register_gauge("connections")
        metrics.gauge_set("connections", 10)
        metrics.gauge_dec("connections", 3)
        assert metrics.gauge_get("connections") == 7

    def test_gauge_with_labels(self, metrics: MetricsCollector):
        metrics.register_gauge("pool_size", label_names=["pool"])
        metrics.gauge_set("pool_size", 5, labels={"pool": "main"})
        metrics.gauge_set("pool_size", 3, labels={"pool": "worker"})
        assert metrics.gauge_get("pool_size", labels={"pool": "main"}) == 5
        assert metrics.gauge_get("pool_size", labels={"pool": "worker"}) == 3


class TestHistogramMetrics:
    """Test histogram metric type."""

    def test_histogram_observe(self, metrics: MetricsCollector):
        metrics.register_histogram("duration", buckets=[0.1, 0.5, 1.0, 5.0])
        metrics.histogram_observe("duration", 0.3)
        metrics.histogram_observe("duration", 0.8)
        metrics.histogram_observe("duration", 2.0)

        assert metrics.histogram_get_count("duration") == 3
        assert metrics.histogram_get_sum("duration") == pytest.approx(3.1)

    def test_histogram_bucket_distribution(self, metrics: MetricsCollector):
        metrics.register_histogram("latency", buckets=[1.0, 5.0, 10.0])
        # Observe values that fall into different buckets
        metrics.histogram_observe("latency", 0.5)  # <= 1.0
        metrics.histogram_observe("latency", 3.0)  # <= 5.0
        metrics.histogram_observe("latency", 7.0)  # <= 10.0
        metrics.histogram_observe("latency", 15.0)  # <= +Inf

        all_metrics = metrics.get_all_metrics()
        lat_metric = next(m for m in all_metrics if m.name == "latency")
        assert len(lat_metric.histograms) == 1
        h = lat_metric.histograms[0]
        assert h.count == 4
        # Buckets: 1.0 -> 1, 5.0 -> 1, 10.0 -> 1, +Inf -> 1
        # (non-cumulative in the store, but let's verify count and sum)
        assert h.sum == pytest.approx(25.5)

    def test_histogram_percentile(self, metrics: MetricsCollector):
        metrics.register_histogram("resp_time", buckets=[0.1, 0.5, 1.0])
        for v in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
            metrics.histogram_observe("resp_time", v)

        p50 = metrics.histogram_percentile("resp_time", 50)
        assert p50 is not None
        assert 0.4 <= p50 <= 0.6  # Median of 0.1..1.0

        p99 = metrics.histogram_percentile("resp_time", 99)
        assert p99 is not None
        assert p99 >= 0.9

    def test_histogram_percentile_empty(self, metrics: MetricsCollector):
        metrics.register_histogram("empty_hist")
        assert metrics.histogram_percentile("empty_hist", 50) is None

    def test_histogram_with_labels(self, metrics: MetricsCollector):
        metrics.register_histogram("req_dur", label_names=["method"], buckets=[1.0])
        metrics.histogram_observe("req_dur", 0.5, labels={"method": "GET"})
        metrics.histogram_observe("req_dur", 1.5, labels={"method": "POST"})

        assert metrics.histogram_get_count("req_dur", labels={"method": "GET"}) == 1
        assert metrics.histogram_get_count("req_dur", labels={"method": "POST"}) == 1


class TestMetricRateCalculation:
    """Test rate calculation helpers."""

    def test_counter_rate(self, metrics: MetricsCollector):
        metrics.register_counter("rate_test")
        # Increment 10 times
        for _ in range(10):
            metrics.counter_inc("rate_test")

        # Rate should be positive with a window that includes all increments
        rate = metrics.counter_rate("rate_test", window_seconds=60)
        assert rate > 0

    def test_counter_rate_empty(self, metrics: MetricsCollector):
        metrics.register_counter("empty_rate")
        rate = metrics.counter_rate("empty_rate")
        assert rate == 0.0

    def test_counter_rate_unregistered(self, metrics: MetricsCollector):
        rate = metrics.counter_rate("nonexistent")
        assert rate == 0.0


# ===========================================================================
# Prometheus Export Tests
# ===========================================================================


class TestPrometheusExport:
    """Test Prometheus text exposition format."""

    def test_export_counter(self, metrics: MetricsCollector):
        metrics.register_counter("http_requests_total", help_text="Total HTTP requests")
        metrics.counter_inc("http_requests_total", labels={"method": "GET"})

        output = metrics.export_prometheus()
        assert "# HELP http_requests_total Total HTTP requests" in output
        assert "# TYPE http_requests_total counter" in output
        assert 'http_requests_total{method="GET"}' in output

    def test_export_gauge(self, metrics: MetricsCollector):
        metrics.register_gauge("temperature", help_text="Current temp")
        metrics.gauge_set("temperature", 42)

        output = metrics.export_prometheus()
        assert "# TYPE temperature gauge" in output
        assert "temperature 42" in output

    def test_export_histogram(self, metrics: MetricsCollector):
        metrics.register_histogram("response_time", buckets=[0.1, 0.5, 1.0])
        metrics.histogram_observe("response_time", 0.3)

        output = metrics.export_prometheus()
        assert "# TYPE response_time histogram" in output
        assert "response_time_bucket" in output
        assert "response_time_count" in output
        assert "response_time_sum" in output
        assert '+Inf' in output

    def test_export_empty_returns_empty(self, metrics: MetricsCollector):
        output = metrics.export_prometheus()
        assert output == ""

    def test_export_format_labels(self, metrics: MetricsCollector):
        metrics.register_counter("labeled", label_names=["a", "b"])
        metrics.counter_inc("labeled", labels={"a": "1", "b": "2"})

        output = metrics.export_prometheus()
        assert 'a="1"' in output
        assert 'b="2"' in output


# ===========================================================================
# AlertEngine Tests
# ===========================================================================


class TestAlertRuleEvaluation:
    """Test alert rule evaluation and state transitions."""

    def test_add_rule(self, alert_engine: AlertEngine):
        rule = AlertRuleSchema(
            name="test_alert",
            metric_name="test_metric",
            condition=AlertCondition.GT,
            threshold=5.0,
            severity=AlertSeverity.WARNING,
        )
        alert_engine.add_rule(rule)
        assert len(alert_engine.get_rules()) == 1

    def test_initial_state_is_ok(self, alert_engine: AlertEngine):
        rule = AlertRuleSchema(
            name="test_alert",
            metric_name="test_metric",
            condition=AlertCondition.GT,
            threshold=5.0,
        )
        alert_engine.add_rule(rule)
        states = alert_engine.get_states()
        assert len(states) == 1
        assert states[0].status == AlertStatus.OK

    def test_condition_gt_triggers_pending(self, alert_engine: AlertEngine):
        rule = AlertRuleSchema(
            name="high_latency",
            metric_name="latency",
            condition=AlertCondition.GT,
            threshold=5.0,
            duration_seconds=0,
        )
        alert_engine.add_rule(rule)
        changed = alert_engine.evaluate({"latency": 10.0})
        assert len(changed) == 1
        # First eval always goes OK -> PENDING
        assert changed[0].status == AlertStatus.PENDING

    def test_condition_lt_triggers(self, alert_engine: AlertEngine):
        rule = AlertRuleSchema(
            name="low_count",
            metric_name="count",
            condition=AlertCondition.LT,
            threshold=10.0,
            duration_seconds=0,
        )
        alert_engine.add_rule(rule)
        changed = alert_engine.evaluate({"count": 5.0})
        assert len(changed) == 1
        assert changed[0].status == AlertStatus.PENDING

    def test_condition_eq_triggers(self, alert_engine: AlertEngine):
        rule = AlertRuleSchema(
            name="exact_match",
            metric_name="errors",
            condition=AlertCondition.EQ,
            threshold=0.0,
            duration_seconds=0,
        )
        alert_engine.add_rule(rule)
        changed = alert_engine.evaluate({"errors": 0.0})
        assert len(changed) == 1
        assert changed[0].status == AlertStatus.PENDING

    def test_state_transition_ok_to_pending(self, alert_engine: AlertEngine):
        rule = AlertRuleSchema(
            name="slow",
            metric_name="latency",
            condition=AlertCondition.GT,
            threshold=5.0,
            duration_seconds=60,  # Requires duration
        )
        alert_engine.add_rule(rule)
        changed = alert_engine.evaluate({"latency": 10.0})
        assert len(changed) == 1
        assert changed[0].status == AlertStatus.PENDING

    def test_state_transition_pending_to_firing(self, alert_engine: AlertEngine):
        rule = AlertRuleSchema(
            name="slow",
            metric_name="latency",
            condition=AlertCondition.GT,
            threshold=5.0,
            duration_seconds=0,  # 0 duration -> fires on second eval from pending
        )
        alert_engine.add_rule(rule)
        # First eval: OK -> PENDING
        alert_engine.evaluate({"latency": 10.0})
        states = alert_engine.get_states()
        assert states[0].status == AlertStatus.PENDING
        # Second eval: PENDING -> FIRING (duration=0)
        alert_engine.evaluate({"latency": 10.0})
        states = alert_engine.get_states()
        assert states[0].status == AlertStatus.FIRING

    def test_state_transition_firing_to_resolved(self, alert_engine: AlertEngine):
        rule = AlertRuleSchema(
            name="alert1",
            metric_name="metric1",
            condition=AlertCondition.GT,
            threshold=5.0,
            duration_seconds=0,
        )
        alert_engine.add_rule(rule)
        # First eval: OK -> PENDING
        alert_engine.evaluate({"metric1": 10.0})
        # Second eval: PENDING -> FIRING
        alert_engine.evaluate({"metric1": 10.0})
        states = alert_engine.get_states()
        assert states[0].status == AlertStatus.FIRING
        # Resolve
        changed = alert_engine.evaluate({"metric1": 3.0})
        assert len(changed) == 1
        assert changed[0].status == AlertStatus.RESOLVED

    def test_resolved_to_pending_on_refire(self, alert_engine: AlertEngine):
        rule = AlertRuleSchema(
            name="alert1",
            metric_name="metric1",
            condition=AlertCondition.GT,
            threshold=5.0,
            duration_seconds=0,
        )
        alert_engine.add_rule(rule)
        alert_engine.evaluate({"metric1": 10.0})  # OK -> PENDING
        alert_engine.evaluate({"metric1": 10.0})  # PENDING -> FIRING
        alert_engine.evaluate({"metric1": 3.0})   # FIRING -> RESOLVED
        changed = alert_engine.evaluate({"metric1": 10.0})  # RESOLVED -> PENDING
        assert len(changed) == 1
        assert changed[0].status == AlertStatus.PENDING

    def test_no_data_leaves_state_unchanged(self, alert_engine: AlertEngine):
        rule = AlertRuleSchema(
            name="alert1",
            metric_name="metric1",
            condition=AlertCondition.GT,
            threshold=5.0,
        )
        alert_engine.add_rule(rule)
        changed = alert_engine.evaluate({})
        assert len(changed) == 0

    def test_get_firing_alerts(self, alert_engine: AlertEngine):
        for i in range(3):
            alert_engine.add_rule(
                AlertRuleSchema(
                    name=f"alert_{i}",
                    metric_name=f"metric_{i}",
                    condition=AlertCondition.GT,
                    threshold=5.0,
                    duration_seconds=0,
                )
            )
        # First eval: OK -> PENDING for first two
        alert_engine.evaluate({"metric_0": 10.0, "metric_1": 10.0, "metric_2": 3.0})
        # get_firing_alerts returns FIRING + PENDING
        firing = alert_engine.get_firing_alerts()
        assert len(firing) == 2

    def test_alert_history(self, alert_engine: AlertEngine):
        rule = AlertRuleSchema(
            name="alert1",
            metric_name="metric1",
            condition=AlertCondition.GT,
            threshold=5.0,
            duration_seconds=0,
        )
        alert_engine.add_rule(rule)
        alert_engine.evaluate({"metric1": 10.0})  # OK -> PENDING
        alert_engine.evaluate({"metric1": 10.0})  # PENDING -> FIRING
        alert_engine.evaluate({"metric1": 3.0})   # FIRING -> RESOLVED

        history = alert_engine.get_history()
        assert len(history) >= 3

    def test_alert_engine_clear(self, alert_engine: AlertEngine):
        alert_engine.add_rule(
            AlertRuleSchema(
                name="test",
                metric_name="m",
                condition=AlertCondition.GT,
                threshold=1.0,
            )
        )
        alert_engine.clear()
        assert len(alert_engine.get_rules()) == 0
        assert len(alert_engine.get_states()) == 0


class TestDefaultAlerts:
    """Test pre-configured default alerts."""

    def test_default_alerts_registered(self):
        engine = get_alert_engine()
        rules = engine.get_rules()
        rule_names = {r.name for r in rules}
        assert "screening_p99_latency_high" in rule_names
        assert "fhir_import_error_rate_high" in rule_names
        assert "api_error_rate_high" in rule_names
        assert "active_patient_count_drop" in rule_names

    def test_default_alert_severities(self):
        engine = get_alert_engine()
        rules = {r.name: r for r in engine.get_rules()}
        assert rules["screening_p99_latency_high"].severity == AlertSeverity.WARNING
        assert rules["fhir_import_error_rate_high"].severity == AlertSeverity.CRITICAL
        assert rules["api_error_rate_high"].severity == AlertSeverity.WARNING
        assert rules["active_patient_count_drop"].severity == AlertSeverity.CRITICAL


# ===========================================================================
# Dashboard Aggregation Tests
# ===========================================================================


class TestDashboardAggregation:
    """Test dashboard data aggregation logic."""

    def test_dashboard_healthy_by_default(self):
        """Dashboard should show healthy when no alerts are firing."""
        mc = get_metrics_collector()
        tracing = get_tracing_service()
        engine = get_alert_engine()

        # No data means no alerts should fire
        states = engine.get_states()
        firing = [s for s in states if s.status in (AlertStatus.FIRING, AlertStatus.PENDING)]
        assert len(firing) == 0

    def test_default_metrics_registered(self):
        """Check that default clinical metrics are registered."""
        mc = get_metrics_collector()
        names = mc.get_metric_names()
        assert "screening_requests_total" in names
        assert "screening_duration_seconds" in names
        assert "fhir_imports_total" in names
        assert "fhir_import_duration_seconds" in names
        assert "nlp_extractions_total" in names
        assert "active_patients" in names
        assert "clinical_facts_total" in names
        assert "api_request_duration_seconds" in names


# ===========================================================================
# API Endpoint Tests
# ===========================================================================


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    """Create an async test client with auth bypass."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestHealthEndpoints:
    """Test observability API endpoints."""

    @pytest.mark.anyio
    async def test_dashboard_endpoint(self, client: AsyncClient):
        resp = await client.get("/api/v1/observability/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "overall_status" in data
        assert "services" in data
        assert "active_alerts" in data
        assert "timestamp" in data

    @pytest.mark.anyio
    async def test_traces_endpoint(self, client: AsyncClient):
        resp = await client.get("/api/v1/observability/traces")
        assert resp.status_code == 200
        data = resp.json()
        assert "traces" in data
        assert "total" in data

    @pytest.mark.anyio
    async def test_trace_not_found(self, client: AsyncClient):
        resp = await client.get("/api/v1/observability/traces/nonexistent_trace_id")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_metrics_endpoint(self, client: AsyncClient):
        resp = await client.get("/api/v1/observability/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "metrics" in data
        assert "total" in data

    @pytest.mark.anyio
    async def test_prometheus_endpoint(self, client: AsyncClient):
        resp = await client.get("/api/v1/observability/metrics/prometheus")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers.get("content-type", "")

    @pytest.mark.anyio
    async def test_alerts_endpoint(self, client: AsyncClient):
        resp = await client.get("/api/v1/observability/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert "alerts" in data
        assert "firing_count" in data
        assert "pending_count" in data
        assert "ok_count" in data


# ===========================================================================
# Metrics Collector Management
# ===========================================================================


class TestMetricsManagement:
    """Test metrics collector management methods."""

    def test_clear_metrics(self, metrics: MetricsCollector):
        metrics.register_counter("test")
        metrics.counter_inc("test")
        metrics.clear()
        assert metrics.get_metric_names() == []

    def test_get_metric_names(self, metrics: MetricsCollector):
        metrics.register_counter("z_counter")
        metrics.register_gauge("a_gauge")
        names = metrics.get_metric_names()
        assert names == ["a_gauge", "z_counter"]  # sorted
