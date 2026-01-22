"""API endpoints for Knowledge Graph Health Monitoring.

This module provides comprehensive health monitoring for all knowledge graph
components, including:
- Service availability checks
- Performance metrics
- Resource utilization
- Dependency status
- Component-specific diagnostics
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/kg/health", tags=["kg-health"])


# ============================================================================
# Models
# ============================================================================

class HealthStatus(str, Enum):
    """Health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ComponentHealth(BaseModel):
    """Health information for a single component."""

    name: str
    status: HealthStatus
    latency_ms: float | None = None
    last_check: datetime
    details: dict[str, Any] | None = None
    error: str | None = None


class DependencyHealth(BaseModel):
    """Health information for a dependency."""

    name: str
    type: str  # database, cache, service, etc.
    status: HealthStatus
    latency_ms: float | None = None
    version: str | None = None
    connection_info: dict[str, Any] | None = None


class OverallHealth(BaseModel):
    """Overall health status of the knowledge graph system."""

    status: HealthStatus
    timestamp: datetime
    components: list[ComponentHealth]
    dependencies: list[DependencyHealth]
    metrics: dict[str, Any]


# ============================================================================
# Health Check Functions
# ============================================================================

async def check_graph_database() -> ComponentHealth:
    """Check health of the graph database service."""
    start = time.perf_counter()
    now = datetime.now(timezone.utc)

    try:
        from app.services.graph_database_service import get_graph_database_service
        svc = get_graph_database_service()
        stats = svc.get_stats() if hasattr(svc, "get_stats") else {}
        latency = (time.perf_counter() - start) * 1000

        return ComponentHealth(
            name="graph_database",
            status=HealthStatus.HEALTHY,
            latency_ms=latency,
            last_check=now,
            details=stats,
        )
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return ComponentHealth(
            name="graph_database",
            status=HealthStatus.UNHEALTHY,
            latency_ms=latency,
            last_check=now,
            error=str(e),
        )


async def check_graph_analytics() -> ComponentHealth:
    """Check health of the graph analytics service."""
    start = time.perf_counter()
    now = datetime.now(timezone.utc)

    try:
        from app.services.graph_analytics_service import get_graph_analytics_service
        svc = get_graph_analytics_service()
        stats = svc.get_stats() if hasattr(svc, "get_stats") else {"loaded": True}
        latency = (time.perf_counter() - start) * 1000

        return ComponentHealth(
            name="graph_analytics",
            status=HealthStatus.HEALTHY,
            latency_ms=latency,
            last_check=now,
            details=stats,
        )
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return ComponentHealth(
            name="graph_analytics",
            status=HealthStatus.UNHEALTHY,
            latency_ms=latency,
            last_check=now,
            error=str(e),
        )


async def check_graph_embedding() -> ComponentHealth:
    """Check health of the graph embedding service."""
    start = time.perf_counter()
    now = datetime.now(timezone.utc)

    try:
        from app.services.graph_embedding_service import get_graph_embedding_service
        svc = get_graph_embedding_service()
        latency = (time.perf_counter() - start) * 1000

        return ComponentHealth(
            name="graph_embedding",
            status=HealthStatus.HEALTHY,
            latency_ms=latency,
            last_check=now,
            details={"model": "all-MiniLM-L6-v2", "dimensions": 384},
        )
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return ComponentHealth(
            name="graph_embedding",
            status=HealthStatus.UNHEALTHY,
            latency_ms=latency,
            last_check=now,
            error=str(e),
        )


async def check_causal_reasoning() -> ComponentHealth:
    """Check health of the causal reasoning service."""
    start = time.perf_counter()
    now = datetime.now(timezone.utc)

    try:
        from app.services.causal_reasoning_service import get_causal_reasoning_service
        svc = get_causal_reasoning_service()
        latency = (time.perf_counter() - start) * 1000

        return ComponentHealth(
            name="causal_reasoning",
            status=HealthStatus.HEALTHY,
            latency_ms=latency,
            last_check=now,
            details={"loaded": True},
        )
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return ComponentHealth(
            name="causal_reasoning",
            status=HealthStatus.UNHEALTHY,
            latency_ms=latency,
            last_check=now,
            error=str(e),
        )


async def check_provenance_service() -> ComponentHealth:
    """Check health of the provenance service."""
    start = time.perf_counter()
    now = datetime.now(timezone.utc)

    try:
        from app.services.provenance_service import get_provenance_service
        svc = get_provenance_service()
        latency = (time.perf_counter() - start) * 1000

        return ComponentHealth(
            name="provenance",
            status=HealthStatus.HEALTHY,
            latency_ms=latency,
            last_check=now,
            details={"ontology": "W3C PROV-O"},
        )
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return ComponentHealth(
            name="provenance",
            status=HealthStatus.UNHEALTHY,
            latency_ms=latency,
            last_check=now,
            error=str(e),
        )


async def check_multi_agent_orchestrator() -> ComponentHealth:
    """Check health of the multi-agent orchestrator."""
    start = time.perf_counter()
    now = datetime.now(timezone.utc)

    try:
        from app.services.multi_agent_orchestrator import get_multi_agent_orchestrator
        svc = get_multi_agent_orchestrator()
        latency = (time.perf_counter() - start) * 1000

        return ComponentHealth(
            name="multi_agent_orchestrator",
            status=HealthStatus.HEALTHY,
            latency_ms=latency,
            last_check=now,
            details={
                "agents": ["diagnostic", "treatment", "safety", "evidence"],
                "active_sessions": 0,
            },
        )
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return ComponentHealth(
            name="multi_agent_orchestrator",
            status=HealthStatus.UNHEALTHY,
            latency_ms=latency,
            last_check=now,
            error=str(e),
        )


async def check_visualization_service() -> ComponentHealth:
    """Check health of the visualization service."""
    start = time.perf_counter()
    now = datetime.now(timezone.utc)

    try:
        from app.services.kg_visualization_service import get_kg_visualization_service
        svc = get_kg_visualization_service()
        latency = (time.perf_counter() - start) * 1000

        return ComponentHealth(
            name="kg_visualization",
            status=HealthStatus.HEALTHY,
            latency_ms=latency,
            last_check=now,
            details={"formats": ["d3js", "cytoscape", "visjs"]},
        )
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return ComponentHealth(
            name="kg_visualization",
            status=HealthStatus.UNHEALTHY,
            latency_ms=latency,
            last_check=now,
            error=str(e),
        )


async def check_medagentbench() -> ComponentHealth:
    """Check health of the MedAgentBench service."""
    start = time.perf_counter()
    now = datetime.now(timezone.utc)

    try:
        from app.services.medagentbench_service import get_medagentbench_service
        svc = get_medagentbench_service()
        suites = svc.list_suites()
        latency = (time.perf_counter() - start) * 1000

        return ComponentHealth(
            name="medagentbench",
            status=HealthStatus.HEALTHY,
            latency_ms=latency,
            last_check=now,
            details={"suites_count": len(suites)},
        )
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return ComponentHealth(
            name="medagentbench",
            status=HealthStatus.UNHEALTHY,
            latency_ms=latency,
            last_check=now,
            error=str(e),
        )


async def check_drknows_benchmark() -> ComponentHealth:
    """Check health of the DR.KNOWS benchmark service."""
    start = time.perf_counter()
    now = datetime.now(timezone.utc)

    try:
        from app.services.drknows_benchmark_service import get_drknows_benchmark_service
        svc = get_drknows_benchmark_service()
        history = svc.get_benchmark_history()
        latency = (time.perf_counter() - start) * 1000

        return ComponentHealth(
            name="drknows_benchmark",
            status=HealthStatus.HEALTHY,
            latency_ms=latency,
            last_check=now,
            details={"history_count": len(history)},
        )
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return ComponentHealth(
            name="drknows_benchmark",
            status=HealthStatus.UNHEALTHY,
            latency_ms=latency,
            last_check=now,
            error=str(e),
        )


async def check_partitioning_service() -> ComponentHealth:
    """Check health of the partitioning service."""
    start = time.perf_counter()
    now = datetime.now(timezone.utc)

    try:
        from app.services.kg_partitioning_service import get_kg_partitioning_service
        svc = get_kg_partitioning_service()
        latency = (time.perf_counter() - start) * 1000

        return ComponentHealth(
            name="kg_partitioning",
            status=HealthStatus.HEALTHY,
            latency_ms=latency,
            last_check=now,
            details={"strategies": ["hash", "patient_centric", "semantic_type"]},
        )
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return ComponentHealth(
            name="kg_partitioning",
            status=HealthStatus.UNHEALTHY,
            latency_ms=latency,
            last_check=now,
            error=str(e),
        )


async def check_kafka_streaming() -> ComponentHealth:
    """Check health of the Kafka streaming service."""
    start = time.perf_counter()
    now = datetime.now(timezone.utc)

    try:
        from app.services.kg_kafka_streaming_service import get_kg_kafka_streaming_service
        svc = get_kg_kafka_streaming_service()
        stats = svc.get_stats()
        latency = (time.perf_counter() - start) * 1000

        return ComponentHealth(
            name="kg_kafka_streaming",
            status=HealthStatus.HEALTHY,
            latency_ms=latency,
            last_check=now,
            details=stats,
        )
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return ComponentHealth(
            name="kg_kafka_streaming",
            status=HealthStatus.UNHEALTHY,
            latency_ms=latency,
            last_check=now,
            error=str(e),
        )


async def check_fhir_export() -> ComponentHealth:
    """Check health of the FHIR export service."""
    start = time.perf_counter()
    now = datetime.now(timezone.utc)

    try:
        from app.services.knowledge_graph_fhir_export import (
            get_knowledge_graph_fhir_exporter,
        )
        svc = get_knowledge_graph_fhir_exporter()
        latency = (time.perf_counter() - start) * 1000

        return ComponentHealth(
            name="fhir_export",
            status=HealthStatus.HEALTHY,
            latency_ms=latency,
            last_check=now,
            details={"resources": ["Provenance", "Evidence", "Library", "Bundle"]},
        )
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return ComponentHealth(
            name="fhir_export",
            status=HealthStatus.UNHEALTHY,
            latency_ms=latency,
            last_check=now,
            error=str(e),
        )


async def check_neo4j_dependency() -> DependencyHealth:
    """Check Neo4j database connectivity."""
    now = datetime.now(timezone.utc)

    try:
        from app.services.graph_database_service import get_graph_database_service
        start = time.perf_counter()
        svc = get_graph_database_service()
        stats = svc.get_stats() if hasattr(svc, "get_stats") else {}
        latency = (time.perf_counter() - start) * 1000

        # Check if in mock mode (no real Neo4j connection)
        if stats.get("mock_mode", False):
            return DependencyHealth(
                name="neo4j",
                type="graph_database",
                status=HealthStatus.DEGRADED,
                latency_ms=latency,
                version="mock",
                connection_info={"mock_mode": True, "reason": "Neo4j not available"},
            )

        return DependencyHealth(
            name="neo4j",
            type="graph_database",
            status=HealthStatus.HEALTHY,
            latency_ms=latency,
            version=stats.get("version", "unknown"),
            connection_info={
                "uri": stats.get("uri", "bolt://localhost:7687"),
                "database": stats.get("database", "neo4j"),
            },
        )
    except Exception as e:
        return DependencyHealth(
            name="neo4j",
            type="graph_database",
            status=HealthStatus.UNHEALTHY,
            version=None,
            connection_info={"error": str(e)},
        )


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/")
async def get_overall_health() -> dict[str, Any]:
    """Get overall health status of all KG components.

    Returns comprehensive health information including:
    - Component health status
    - Dependency health status
    - System metrics
    """
    start = time.perf_counter()

    # Check all components in parallel
    components = [
        await check_graph_database(),
        await check_graph_analytics(),
        await check_graph_embedding(),
        await check_causal_reasoning(),
        await check_provenance_service(),
        await check_multi_agent_orchestrator(),
        await check_visualization_service(),
        await check_medagentbench(),
        await check_drknows_benchmark(),
        await check_partitioning_service(),
        await check_kafka_streaming(),
        await check_fhir_export(),
    ]

    # Check dependencies
    dependencies = [
        await check_neo4j_dependency(),
    ]

    # Determine overall status
    healthy_count = sum(1 for c in components if c.status == HealthStatus.HEALTHY)
    degraded_count = sum(1 for c in components if c.status == HealthStatus.DEGRADED)
    unhealthy_count = sum(1 for c in components if c.status == HealthStatus.UNHEALTHY)

    if unhealthy_count > 0:
        overall_status = HealthStatus.UNHEALTHY
    elif degraded_count > 0:
        overall_status = HealthStatus.DEGRADED
    else:
        overall_status = HealthStatus.HEALTHY

    total_time = (time.perf_counter() - start) * 1000

    return {
        "status": overall_status.value,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "check_duration_ms": total_time,
        "summary": {
            "total_components": len(components),
            "healthy": healthy_count,
            "degraded": degraded_count,
            "unhealthy": unhealthy_count,
        },
        "components": [
            {
                "name": c.name,
                "status": c.status.value,
                "latency_ms": c.latency_ms,
                "last_check": c.last_check.isoformat(),
                "details": c.details,
                "error": c.error,
            }
            for c in components
        ],
        "dependencies": [
            {
                "name": d.name,
                "type": d.type,
                "status": d.status.value,
                "latency_ms": d.latency_ms,
                "version": d.version,
                "connection_info": d.connection_info,
            }
            for d in dependencies
        ],
        "metrics": {
            "avg_component_latency_ms": (
                sum(c.latency_ms or 0 for c in components) / len(components)
                if components else 0
            ),
            "max_component_latency_ms": (
                max(c.latency_ms or 0 for c in components)
                if components else 0
            ),
        },
    }


@router.get("/component/{component_name}")
async def get_component_health(component_name: str) -> dict[str, Any]:
    """Get detailed health for a specific component."""
    health_checks = {
        "graph_database": check_graph_database,
        "graph_analytics": check_graph_analytics,
        "graph_embedding": check_graph_embedding,
        "causal_reasoning": check_causal_reasoning,
        "provenance": check_provenance_service,
        "multi_agent_orchestrator": check_multi_agent_orchestrator,
        "kg_visualization": check_visualization_service,
        "medagentbench": check_medagentbench,
        "drknows_benchmark": check_drknows_benchmark,
        "kg_partitioning": check_partitioning_service,
        "kg_kafka_streaming": check_kafka_streaming,
        "fhir_export": check_fhir_export,
    }

    if component_name not in health_checks:
        return {
            "error": f"Unknown component: {component_name}",
            "available_components": list(health_checks.keys()),
        }

    health = await health_checks[component_name]()

    return {
        "name": health.name,
        "status": health.status.value,
        "latency_ms": health.latency_ms,
        "last_check": health.last_check.isoformat(),
        "details": health.details,
        "error": health.error,
    }


@router.get("/dependencies")
async def get_dependencies_health() -> dict[str, Any]:
    """Get health status of all external dependencies."""
    dependencies = [
        await check_neo4j_dependency(),
    ]

    healthy = sum(1 for d in dependencies if d.status == HealthStatus.HEALTHY)
    degraded = sum(1 for d in dependencies if d.status == HealthStatus.DEGRADED)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total": len(dependencies),
            "healthy": healthy,
            "degraded": degraded,
            "unhealthy": len(dependencies) - healthy - degraded,
        },
        "dependencies": [
            {
                "name": d.name,
                "type": d.type,
                "status": d.status.value,
                "latency_ms": d.latency_ms,
                "version": d.version,
                "connection_info": d.connection_info,
            }
            for d in dependencies
        ],
    }


@router.get("/liveness")
async def liveness_probe() -> dict[str, str]:
    """Kubernetes liveness probe for KG services.

    Returns a simple response indicating the service is alive.
    """
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/readiness")
async def readiness_probe() -> dict[str, Any]:
    """Kubernetes readiness probe for KG services.

    Checks if all critical components are ready to serve requests.
    """
    # Check critical components only
    critical_components = [
        await check_graph_database(),
        await check_graph_analytics(),
    ]

    all_ready = all(c.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED) for c in critical_components)

    return {
        "status": "ready" if all_ready else "not_ready",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "critical_components": [
            {
                "name": c.name,
                "status": c.status.value,
            }
            for c in critical_components
        ],
    }


@router.get("/metrics")
async def get_health_metrics(
    include_history: bool = Query(default=False, description="Include historical metrics"),
) -> dict[str, Any]:
    """Get health metrics for monitoring dashboards.

    Returns metrics suitable for Prometheus/Grafana integration.
    """
    now = datetime.now(timezone.utc)

    # Check all components
    components = [
        await check_graph_database(),
        await check_graph_analytics(),
        await check_graph_embedding(),
        await check_causal_reasoning(),
        await check_provenance_service(),
        await check_multi_agent_orchestrator(),
        await check_visualization_service(),
        await check_medagentbench(),
        await check_drknows_benchmark(),
        await check_partitioning_service(),
        await check_kafka_streaming(),
        await check_fhir_export(),
    ]

    # Calculate metrics
    status_counts = {
        "healthy": sum(1 for c in components if c.status == HealthStatus.HEALTHY),
        "degraded": sum(1 for c in components if c.status == HealthStatus.DEGRADED),
        "unhealthy": sum(1 for c in components if c.status == HealthStatus.UNHEALTHY),
    }

    latencies = [c.latency_ms for c in components if c.latency_ms is not None]

    metrics = {
        "timestamp": now.isoformat(),
        "kg_health_components_total": len(components),
        "kg_health_components_healthy": status_counts["healthy"],
        "kg_health_components_degraded": status_counts["degraded"],
        "kg_health_components_unhealthy": status_counts["unhealthy"],
        "kg_health_check_latency_avg_ms": sum(latencies) / len(latencies) if latencies else 0,
        "kg_health_check_latency_max_ms": max(latencies) if latencies else 0,
        "kg_health_check_latency_min_ms": min(latencies) if latencies else 0,
        "component_latencies": {c.name: c.latency_ms for c in components},
        "component_statuses": {c.name: c.status.value for c in components},
    }

    return metrics


@router.get("/alerts")
async def get_health_alerts() -> dict[str, Any]:
    """Get current health alerts for unhealthy or degraded components."""
    components = [
        await check_graph_database(),
        await check_graph_analytics(),
        await check_graph_embedding(),
        await check_causal_reasoning(),
        await check_provenance_service(),
        await check_multi_agent_orchestrator(),
        await check_visualization_service(),
        await check_medagentbench(),
        await check_drknows_benchmark(),
        await check_partitioning_service(),
        await check_kafka_streaming(),
        await check_fhir_export(),
    ]

    alerts = []
    for c in components:
        if c.status == HealthStatus.UNHEALTHY:
            alerts.append({
                "severity": "critical",
                "component": c.name,
                "status": c.status.value,
                "message": f"Component {c.name} is unhealthy: {c.error}",
                "timestamp": c.last_check.isoformat(),
            })
        elif c.status == HealthStatus.DEGRADED:
            alerts.append({
                "severity": "warning",
                "component": c.name,
                "status": c.status.value,
                "message": f"Component {c.name} is degraded",
                "timestamp": c.last_check.isoformat(),
            })

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "alert_count": len(alerts),
        "alerts": alerts,
    }
