"""Observability Tracing Service (DEVOPS-2).

Pure-Python distributed tracing inspired by OpenTelemetry.  Provides span
creation, W3C TraceContext propagation, a ``@trace_operation`` decorator for
instrumenting service methods, and in-memory span storage with configurable
eviction.

Usage:
    from app.services.observability_service import (
        get_tracing_service,
        trace_operation,
    )

    tracing = get_tracing_service()
    span = tracing.start_span("fhir_import", attributes={"resource_type": "Patient"})
    # ... do work ...
    tracing.end_span(span.span_id)

    # Or use the decorator:
    @trace_operation("screen_patient")
    def screen(patient_id: str) -> dict: ...
"""

from __future__ import annotations

import functools
import logging
import os
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

from app.schemas.observability import (
    AlertCondition,
    AlertRuleSchema,
    AlertSeverity,
    AlertStateSchema,
    AlertStatus,
    SpanSchema,
    SpanStatus,
    TraceSchema,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# W3C TraceContext helpers
# ---------------------------------------------------------------------------


def generate_trace_id() -> str:
    """Generate a 32-hex-char trace ID (128-bit)."""
    return uuid4().hex


def generate_span_id() -> str:
    """Generate a 16-hex-char span ID (64-bit)."""
    return uuid4().hex[:16]


def format_traceparent(trace_id: str, span_id: str, sampled: bool = True) -> str:
    """Format a W3C traceparent header value.

    Format: ``{version}-{trace_id}-{parent_id}-{trace_flags}``
    """
    flags = "01" if sampled else "00"
    return f"00-{trace_id}-{span_id}-{flags}"


def parse_traceparent(header: str) -> dict[str, Any] | None:
    """Parse a W3C traceparent header.

    Returns dict with ``trace_id``, ``parent_id``, ``sampled`` or ``None``
    if the header is invalid.
    """
    parts = header.strip().split("-")
    if len(parts) != 4:
        return None
    version, trace_id, parent_id, flags = parts
    if version != "00":
        return None
    if len(trace_id) != 32 or len(parent_id) != 16:
        return None
    return {
        "trace_id": trace_id,
        "parent_id": parent_id,
        "sampled": flags == "01",
    }


# ---------------------------------------------------------------------------
# TracingService
# ---------------------------------------------------------------------------


class TracingService:
    """In-memory distributed tracing service.

    Thread-safe: all mutations guarded by ``_lock``.
    """

    DEFAULT_MAX_SPANS = 10_000

    def __init__(self, max_spans: int | None = None) -> None:
        self._max_spans = max_spans or self.DEFAULT_MAX_SPANS
        self._spans: list[SpanSchema] = []
        self._active_spans: dict[str, SpanSchema] = {}
        self._lock = threading.Lock()
        self._service_name = os.environ.get("OTEL_SERVICE_NAME", "clinical-ontology")

    # ------------------------------------------------------------------
    # Span lifecycle
    # ------------------------------------------------------------------

    def start_span(
        self,
        operation_name: str,
        *,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        attributes: dict[str, Any] | None = None,
        service_name: str | None = None,
    ) -> SpanSchema:
        """Create and start a new span."""
        span = SpanSchema(
            trace_id=trace_id or generate_trace_id(),
            span_id=generate_span_id(),
            parent_span_id=parent_span_id,
            operation_name=operation_name,
            service_name=service_name or self._service_name,
            start_time=datetime.now(timezone.utc),
            status=SpanStatus.UNSET,
            attributes=attributes or {},
        )
        with self._lock:
            self._active_spans[span.span_id] = span
        return span

    def end_span(
        self,
        span_id: str,
        *,
        status: SpanStatus = SpanStatus.OK,
        attributes: dict[str, Any] | None = None,
    ) -> SpanSchema | None:
        """End an active span and move it to completed storage."""
        with self._lock:
            span = self._active_spans.pop(span_id, None)
            if span is None:
                return None

            now = datetime.now(timezone.utc)
            span.end_time = now
            span.duration_ms = (now - span.start_time).total_seconds() * 1000
            span.status = status
            if attributes:
                span.attributes.update(attributes)

            self._spans.append(span)
            self._evict_if_needed()
            return span

    def add_span_event(
        self,
        span_id: str,
        name: str,
        attributes: dict[str, Any] | None = None,
    ) -> bool:
        """Add a timestamped event to an active span."""
        with self._lock:
            span = self._active_spans.get(span_id)
            if span is None:
                return False
            span.events.append(
                {
                    "name": name,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "attributes": attributes or {},
                }
            )
            return True

    def set_span_attributes(
        self,
        span_id: str,
        attributes: dict[str, Any],
    ) -> bool:
        """Set attributes on an active span."""
        with self._lock:
            span = self._active_spans.get(span_id)
            if span is None:
                return False
            span.attributes.update(attributes)
            return True

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def get_traces(
        self,
        service_name: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TraceSchema]:
        """Return completed traces, optionally filtered by service."""
        with self._lock:
            traces_map: dict[str, list[SpanSchema]] = defaultdict(list)
            for span in self._spans:
                if service_name and span.service_name != service_name:
                    continue
                traces_map[span.trace_id].append(span)

            result: list[TraceSchema] = []
            for trace_id, spans in traces_map.items():
                root = None
                for s in spans:
                    if s.parent_span_id is None:
                        root = s
                        break
                total_dur = root.duration_ms if root else None
                overall_status = SpanStatus.OK
                for s in spans:
                    if s.status == SpanStatus.ERROR:
                        overall_status = SpanStatus.ERROR
                        break

                result.append(
                    TraceSchema(
                        trace_id=trace_id,
                        root_span=root,
                        spans=list(spans),
                        service_name=spans[0].service_name if spans else self._service_name,
                        duration_ms=total_dur,
                        span_count=len(spans),
                        status=overall_status,
                    )
                )

            # Sort by most recent first
            result.sort(
                key=lambda t: t.root_span.start_time if t.root_span else datetime.min.replace(tzinfo=timezone.utc),
                reverse=True,
            )
            return result[offset : offset + limit]

    def get_trace_by_id(self, trace_id: str) -> TraceSchema | None:
        """Return a single trace by its trace_id."""
        with self._lock:
            spans = [s for s in self._spans if s.trace_id == trace_id]
            if not spans:
                return None
            root = None
            for s in spans:
                if s.parent_span_id is None:
                    root = s
                    break
            overall_status = SpanStatus.OK
            for s in spans:
                if s.status == SpanStatus.ERROR:
                    overall_status = SpanStatus.ERROR
                    break
            return TraceSchema(
                trace_id=trace_id,
                root_span=root,
                spans=list(spans),
                service_name=spans[0].service_name,
                duration_ms=root.duration_ms if root else None,
                span_count=len(spans),
                status=overall_status,
            )

    def get_span_count(self) -> int:
        """Return number of completed spans."""
        with self._lock:
            return len(self._spans)

    def get_active_span_count(self) -> int:
        """Return number of in-flight spans."""
        with self._lock:
            return len(self._active_spans)

    # ------------------------------------------------------------------
    # TraceContext propagation
    # ------------------------------------------------------------------

    def inject_context(self, span: SpanSchema) -> dict[str, str]:
        """Produce W3C traceparent headers for outgoing requests."""
        return {"traceparent": format_traceparent(span.trace_id, span.span_id)}

    def extract_context(self, headers: dict[str, str]) -> dict[str, Any] | None:
        """Parse incoming W3C traceparent header."""
        tp = headers.get("traceparent")
        if not tp:
            return None
        return parse_traceparent(tp)

    # ------------------------------------------------------------------
    # Eviction
    # ------------------------------------------------------------------

    def _evict_if_needed(self) -> None:
        """Drop oldest spans when storage exceeds max_spans (caller holds lock)."""
        if len(self._spans) > self._max_spans:
            excess = len(self._spans) - self._max_spans
            self._spans = self._spans[excess:]

    # ------------------------------------------------------------------
    # Management
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Clear all stored spans."""
        with self._lock:
            self._spans.clear()
            self._active_spans.clear()


# ---------------------------------------------------------------------------
# AlertEngine
# ---------------------------------------------------------------------------


class AlertEngine:
    """Evaluates alert rules against current metric values.

    Manages the alert state machine:  OK -> PENDING -> FIRING -> RESOLVED
    """

    def __init__(self) -> None:
        self._rules: list[AlertRuleSchema] = []
        self._states: dict[str, AlertStateSchema] = {}
        self._lock = threading.Lock()
        self._history: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Rule management
    # ------------------------------------------------------------------

    def add_rule(self, rule: AlertRuleSchema) -> None:
        """Register a new alert rule."""
        with self._lock:
            self._rules.append(rule)
            self._states[rule.name] = AlertStateSchema(
                rule_name=rule.name,
                status=AlertStatus.OK,
                severity=rule.severity,
                threshold=rule.threshold,
                condition=rule.condition,
                description=rule.description,
            )

    def get_rules(self) -> list[AlertRuleSchema]:
        """Return all registered rules."""
        with self._lock:
            return list(self._rules)

    def get_states(self) -> list[AlertStateSchema]:
        """Return current alert states."""
        with self._lock:
            return list(self._states.values())

    def get_firing_alerts(self) -> list[AlertStateSchema]:
        """Return only FIRING and PENDING alerts."""
        with self._lock:
            return [
                s
                for s in self._states.values()
                if s.status in (AlertStatus.FIRING, AlertStatus.PENDING)
            ]

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(self, metric_values: dict[str, float]) -> list[AlertStateSchema]:
        """Evaluate all rules against provided metric values.

        Returns list of states that changed.
        """
        now = datetime.now(timezone.utc)
        changed: list[AlertStateSchema] = []

        with self._lock:
            for rule in self._rules:
                value = metric_values.get(rule.metric_name)
                state = self._states[rule.name]
                state.current_value = value

                if value is None:
                    # No data - can't evaluate, leave as is
                    continue

                condition_met = self._check_condition(value, rule.condition, rule.threshold)

                old_status = state.status
                if condition_met:
                    if state.status == AlertStatus.OK or state.status == AlertStatus.RESOLVED:
                        state.status = AlertStatus.PENDING
                        state.pending_since = now
                        state.resolved_at = None
                    elif state.status == AlertStatus.PENDING:
                        # Check if duration threshold exceeded
                        if state.pending_since and rule.duration_seconds > 0:
                            elapsed = (now - state.pending_since).total_seconds()
                            if elapsed >= rule.duration_seconds:
                                state.status = AlertStatus.FIRING
                                state.firing_since = now
                        elif rule.duration_seconds == 0:
                            state.status = AlertStatus.FIRING
                            state.firing_since = now
                    # FIRING stays FIRING while condition is met
                else:
                    if state.status in (AlertStatus.PENDING, AlertStatus.FIRING):
                        state.status = AlertStatus.RESOLVED
                        state.resolved_at = now
                        state.pending_since = None
                        state.firing_since = None

                if state.status != old_status:
                    transition = {
                        "rule_name": rule.name,
                        "from": old_status.value,
                        "to": state.status.value,
                        "value": value,
                        "timestamp": now.isoformat(),
                    }
                    state.history.append(transition)
                    self._history.append(transition)
                    changed.append(state)

        return changed

    @staticmethod
    def _check_condition(value: float, condition: AlertCondition, threshold: float) -> bool:
        """Check if value meets the alert condition."""
        if condition == AlertCondition.GT:
            return value > threshold
        elif condition == AlertCondition.LT:
            return value < threshold
        elif condition == AlertCondition.EQ:
            return value == threshold
        return False

    def get_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return recent alert state transitions."""
        with self._lock:
            return list(reversed(self._history[-limit:]))

    def clear(self) -> None:
        """Reset all alert state."""
        with self._lock:
            self._rules.clear()
            self._states.clear()
            self._history.clear()


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------


def trace_operation(
    name: str,
    *,
    service_name: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> Callable:
    """Decorator to instrument a function with tracing.

    Works with both sync and async functions.
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracing = get_tracing_service()
            span = tracing.start_span(
                name,
                service_name=service_name,
                attributes=attributes or {},
            )
            try:
                result = fn(*args, **kwargs)
                tracing.end_span(span.span_id, status=SpanStatus.OK)
                return result
            except Exception as exc:
                tracing.end_span(
                    span.span_id,
                    status=SpanStatus.ERROR,
                    attributes={"error.type": type(exc).__name__, "error.message": str(exc)},
                )
                raise

        @functools.wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracing = get_tracing_service()
            span = tracing.start_span(
                name,
                service_name=service_name,
                attributes=attributes or {},
            )
            try:
                result = await fn(*args, **kwargs)
                tracing.end_span(span.span_id, status=SpanStatus.OK)
                return result
            except Exception as exc:
                tracing.end_span(
                    span.span_id,
                    status=SpanStatus.ERROR,
                    attributes={"error.type": type(exc).__name__, "error.message": str(exc)},
                )
                raise

        import asyncio

        if asyncio.iscoroutinefunction(fn):
            return async_wrapper
        return sync_wrapper

    return decorator


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_tracing_service: TracingService | None = None
_alert_engine: AlertEngine | None = None
_singleton_lock = threading.Lock()


def get_tracing_service(max_spans: int | None = None) -> TracingService:
    """Return the global TracingService singleton."""
    global _tracing_service
    if _tracing_service is None:
        with _singleton_lock:
            if _tracing_service is None:
                _tracing_service = TracingService(max_spans=max_spans)
    return _tracing_service


def get_alert_engine() -> AlertEngine:
    """Return the global AlertEngine singleton."""
    global _alert_engine
    if _alert_engine is None:
        with _singleton_lock:
            if _alert_engine is None:
                _alert_engine = AlertEngine()
                _register_default_alerts(_alert_engine)
    return _alert_engine


def _register_default_alerts(engine: AlertEngine) -> None:
    """Register pre-configured clinical trial alert rules."""
    engine.add_rule(
        AlertRuleSchema(
            name="screening_p99_latency_high",
            metric_name="screening_duration_seconds_p99",
            condition=AlertCondition.GT,
            threshold=5.0,
            duration_seconds=60,
            severity=AlertSeverity.WARNING,
            description="Screening p99 latency > 5s",
        )
    )
    engine.add_rule(
        AlertRuleSchema(
            name="fhir_import_error_rate_high",
            metric_name="fhir_import_error_rate",
            condition=AlertCondition.GT,
            threshold=0.10,
            duration_seconds=0,
            severity=AlertSeverity.CRITICAL,
            description="FHIR import error rate > 10%",
        )
    )
    engine.add_rule(
        AlertRuleSchema(
            name="api_error_rate_high",
            metric_name="api_error_rate",
            condition=AlertCondition.GT,
            threshold=0.05,
            duration_seconds=0,
            severity=AlertSeverity.WARNING,
            description="API error rate > 5%",
        )
    )
    engine.add_rule(
        AlertRuleSchema(
            name="active_patient_count_drop",
            metric_name="active_patient_count_change_rate",
            condition=AlertCondition.LT,
            threshold=-0.20,
            duration_seconds=0,
            severity=AlertSeverity.CRITICAL,
            description="Active patient count drops > 20% in 1 hour",
        )
    )


def reset_singletons() -> None:
    """Reset singletons for testing."""
    global _tracing_service, _alert_engine
    with _singleton_lock:
        _tracing_service = None
        _alert_engine = None
