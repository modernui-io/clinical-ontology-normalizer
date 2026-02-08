"""Observability API endpoints (DEVOPS-2).

Provides health dashboard, distributed tracing, Prometheus-compatible metrics,
and alert management endpoints for the clinical trial platform.

Endpoints:
    GET /observability/dashboard              - Aggregated system health view
    GET /observability/traces                 - Recent traces with filtering
    GET /observability/traces/{trace_id}      - Single trace detail
    GET /observability/metrics                - Current metric values
    GET /observability/metrics/prometheus     - Prometheus text format
    GET /observability/alerts                 - Active alerts based on thresholds
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse

from app.core.permissions import Permission, PermissionChecker
from app.schemas.observability import (
    AlertsResponse,
    AlertStatus,
    DashboardResponse,
    MetricsResponse,
    ServiceHealth,
    SpanStatus,
    TraceSchema,
    TracesResponse,
)
from app.services.metrics_collector_service import get_metrics_collector
from app.services.observability_service import (
    get_alert_engine,
    get_tracing_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/observability",
    tags=["Observability"],
)

# ---------------------------------------------------------------------------
# Permission dependency
# ---------------------------------------------------------------------------

_analytics_perm_checker = PermissionChecker([Permission.READ_ANALYTICS])


async def _require_analytics_perm(request: Request) -> None:
    return await _analytics_perm_checker(request)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Aggregated system health dashboard",
    description="Returns an aggregated view of system health including service status, active alerts, and key metrics.",
    dependencies=[Depends(_require_analytics_perm)],
)
async def get_dashboard() -> DashboardResponse:
    """Build an aggregated system health dashboard."""
    tracing = get_tracing_service()
    metrics = get_metrics_collector()
    alerts = get_alert_engine()

    now = datetime.now(timezone.utc)

    # Collect service health summaries
    services: list[ServiceHealth] = []

    # Screening service health
    screening_p50 = metrics.histogram_percentile("screening_duration_seconds", 50)
    screening_p99 = metrics.histogram_percentile("screening_duration_seconds", 99)
    screening_rate = metrics.counter_rate("screening_requests_total")
    services.append(
        ServiceHealth(
            name="screening",
            status="healthy",
            latency_p50_ms=(screening_p50 * 1000) if screening_p50 is not None else None,
            latency_p99_ms=(screening_p99 * 1000) if screening_p99 is not None else None,
            request_rate=screening_rate if screening_rate > 0 else None,
        )
    )

    # FHIR import service health
    fhir_p50 = metrics.histogram_percentile("fhir_import_duration_seconds", 50)
    fhir_p99 = metrics.histogram_percentile("fhir_import_duration_seconds", 99)
    fhir_rate = metrics.counter_rate("fhir_imports_total")
    services.append(
        ServiceHealth(
            name="fhir_import",
            status="healthy",
            latency_p50_ms=(fhir_p50 * 1000) if fhir_p50 is not None else None,
            latency_p99_ms=(fhir_p99 * 1000) if fhir_p99 is not None else None,
            request_rate=fhir_rate if fhir_rate > 0 else None,
        )
    )

    # NLP extraction service health
    nlp_rate = metrics.counter_rate("nlp_extractions_total")
    services.append(
        ServiceHealth(
            name="nlp_extraction",
            status="healthy",
            request_rate=nlp_rate if nlp_rate > 0 else None,
        )
    )

    # Determine overall status from alerts
    firing_alerts = alerts.get_firing_alerts()
    firing_count = sum(1 for a in firing_alerts if a.status == AlertStatus.FIRING)
    pending_count = sum(1 for a in firing_alerts if a.status == AlertStatus.PENDING)

    if firing_count > 0:
        overall_status = "unhealthy"
    elif pending_count > 0:
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    # Trace summary
    traces = tracing.get_traces(limit=10000)
    total_traces = len(traces)
    error_traces = sum(1 for t in traces if t.status == SpanStatus.ERROR)
    error_rate = error_traces / total_traces if total_traces > 0 else None

    # Key metrics
    active_patients = metrics.gauge_get("active_patients")
    clinical_facts = metrics.gauge_get("clinical_facts_total")

    return DashboardResponse(
        timestamp=now,
        overall_status=overall_status,
        services=services,
        active_alerts=firing_count + pending_count,
        total_traces_24h=total_traces,
        error_rate_24h=error_rate,
        key_metrics={
            "active_patients": active_patients,
            "clinical_facts_total": clinical_facts,
            "screening_p99_ms": (screening_p99 * 1000) if screening_p99 is not None else None,
        },
    )


# ---------------------------------------------------------------------------
# Traces
# ---------------------------------------------------------------------------


@router.get(
    "/traces",
    response_model=TracesResponse,
    summary="Recent traces",
    description="Return recent distributed traces with optional filtering by service name.",
    dependencies=[Depends(_require_analytics_perm)],
)
async def get_traces(
    service_name: Optional[str] = Query(None, description="Filter by service name"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum traces to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> TracesResponse:
    """Return recent traces."""
    tracing = get_tracing_service()
    traces = tracing.get_traces(service_name=service_name, limit=limit, offset=offset)
    return TracesResponse(
        traces=traces,
        total=len(traces),
        limit=limit,
        offset=offset,
    )


@router.get(
    "/traces/{trace_id}",
    response_model=TraceSchema,
    summary="Single trace detail",
    description="Return a complete trace by its trace ID, including all spans.",
    dependencies=[Depends(_require_analytics_perm)],
)
async def get_trace_detail(trace_id: str) -> TraceSchema:
    """Return a single trace by ID."""
    tracing = get_tracing_service()
    trace = tracing.get_trace_by_id(trace_id)
    if trace is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"Trace {trace_id} not found")
    return trace


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=MetricsResponse,
    summary="Current metric values",
    description="Return all registered metrics and their current values.",
    dependencies=[Depends(_require_analytics_perm)],
)
async def get_metrics() -> MetricsResponse:
    """Return all metrics."""
    mc = get_metrics_collector()
    all_metrics = mc.get_all_metrics()
    return MetricsResponse(
        timestamp=datetime.now(timezone.utc),
        metrics=all_metrics,
        total=len(all_metrics),
    )


@router.get(
    "/metrics/prometheus",
    summary="Prometheus text format",
    description="Export all metrics in Prometheus text exposition format.",
    response_class=PlainTextResponse,
    dependencies=[Depends(_require_analytics_perm)],
)
async def get_metrics_prometheus() -> PlainTextResponse:
    """Return metrics in Prometheus text exposition format."""
    mc = get_metrics_collector()
    text = mc.export_prometheus()
    return PlainTextResponse(
        content=text,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------


@router.get(
    "/alerts",
    response_model=AlertsResponse,
    summary="Active alerts",
    description="Return current alert states including firing, pending, and resolved alerts.",
    dependencies=[Depends(_require_analytics_perm)],
)
async def get_alerts() -> AlertsResponse:
    """Return current alert states."""
    engine = get_alert_engine()
    states = engine.get_states()

    firing = sum(1 for s in states if s.status == AlertStatus.FIRING)
    pending = sum(1 for s in states if s.status == AlertStatus.PENDING)
    ok = sum(1 for s in states if s.status == AlertStatus.OK)

    return AlertsResponse(
        timestamp=datetime.now(timezone.utc),
        alerts=states,
        firing_count=firing,
        pending_count=pending,
        ok_count=ok,
    )
