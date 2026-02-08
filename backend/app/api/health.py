"""Health check endpoints for Clinical Ontology Normalizer.

VP-DevOps: Enhanced health checks with system metrics.

Provides comprehensive health checks for all system dependencies including:
- Database connectivity
- Redis availability
- Neo4j graph database
- Kafka message broker
- System metrics (CPU, memory, disk)

Health status follows a simple model:
- "healthy": All checks pass
- "degraded": Some non-critical services unavailable
- "unhealthy": Critical services unavailable

Usage:
    GET /api/v1/health - Comprehensive health check
    GET /api/v1/health/live - Simple liveness probe
    GET /api/v1/health/ready - Readiness probe
    GET /api/v1/health/deep - Deep health check with system metrics
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import platform
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.terminology_cache import clear_all_caches, get_all_cache_stats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/health", tags=["Health"])


# =============================================================================
# Constants
# =============================================================================

# Health check timeout in seconds
HEALTH_CHECK_TIMEOUT = 5.0

# Service criticality levels
CRITICAL_SERVICES = {"database"}
NON_CRITICAL_SERVICES = {"redis", "neo4j", "kafka"}


# =============================================================================
# Models
# =============================================================================


class HealthStatus(str, Enum):
    """Overall health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ComponentStatus(str, Enum):
    """Individual component status."""

    UP = "up"
    DOWN = "down"


class ComponentHealth(BaseModel):
    """Health status of a single component."""

    status: ComponentStatus = Field(description="Component status (up/down)")
    latency_ms: float | None = Field(
        default=None, description="Response latency in milliseconds"
    )
    error: str | None = Field(default=None, description="Error message if status is down")
    details: dict[str, Any] | None = Field(
        default=None, description="Additional component-specific details"
    )


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""

    status: HealthStatus = Field(description="Overall health status")
    timestamp: str = Field(description="ISO8601 timestamp of the check")
    version: str = Field(description="Application version")
    checks: dict[str, ComponentHealth] = Field(
        description="Individual component health checks"
    )
    uptime_seconds: float | None = Field(
        default=None, description="Application uptime in seconds"
    )


class LivenessResponse(BaseModel):
    """Response model for liveness probe."""

    status: str = Field(default="ok", description="Liveness status")
    timestamp: str = Field(description="ISO8601 timestamp")


class ReadinessResponse(BaseModel):
    """Response model for readiness probe."""

    status: str = Field(description="Readiness status (ready/not_ready)")
    timestamp: str = Field(description="ISO8601 timestamp")
    services_ready: int = Field(description="Number of services ready")
    services_total: int = Field(description="Total number of services checked")


# VP-DevOps: Enhanced system metrics models
class MemoryInfo(BaseModel):
    """Memory usage information."""

    total_mb: float = Field(description="Total memory in MB")
    available_mb: float = Field(description="Available memory in MB")
    used_mb: float = Field(description="Used memory in MB")
    percent_used: float = Field(description="Percentage of memory used")


class DiskInfo(BaseModel):
    """Disk usage information."""

    total_gb: float = Field(description="Total disk space in GB")
    free_gb: float = Field(description="Free disk space in GB")
    used_gb: float = Field(description="Used disk space in GB")
    percent_used: float = Field(description="Percentage of disk used")


class SystemInfo(BaseModel):
    """System information."""

    hostname: str = Field(description="Server hostname")
    os: str = Field(description="Operating system")
    os_version: str = Field(description="OS version")
    python_version: str = Field(description="Python version")
    cpu_count: int = Field(description="Number of CPU cores")
    process_id: int = Field(description="Current process ID")


class SystemMetrics(BaseModel):
    """System resource metrics."""

    memory: MemoryInfo | None = Field(default=None, description="Memory usage")
    disk: DiskInfo | None = Field(default=None, description="Disk usage")
    system: SystemInfo = Field(description="System information")
    load_average: list[float] | None = Field(default=None, description="System load averages (1, 5, 15 min)")


class DeepHealthResponse(BaseModel):
    """Response model for deep health check with system metrics."""

    status: HealthStatus = Field(description="Overall health status")
    timestamp: str = Field(description="ISO8601 timestamp of the check")
    version: str = Field(description="Application version")
    environment: str = Field(description="Environment (development/production)")
    checks: dict[str, ComponentHealth] = Field(description="Individual component health checks")
    system_metrics: SystemMetrics = Field(description="System resource metrics")
    uptime_seconds: float | None = Field(default=None, description="Application uptime in seconds")


# =============================================================================
# Health Check Functions
# =============================================================================


async def check_database() -> ComponentHealth:
    """Check database connectivity and pool status.

    VP-Observability-1: Enhanced to include connection pool metrics.

    Executes a simple SELECT query to verify the database is responding
    and reports connection pool health.

    Returns:
        ComponentHealth with database and pool status.
    """
    start_time = time.perf_counter()

    try:
        from sqlalchemy import text

        from app.core.database import async_session_maker, engine

        async with async_session_maker() as session:
            # Execute a simple query with timeout
            result = await asyncio.wait_for(
                session.execute(text("SELECT 1")),
                timeout=HEALTH_CHECK_TIMEOUT,
            )
            result.scalar()

            latency = (time.perf_counter() - start_time) * 1000

            # VP-Observability-1: Get connection pool metrics
            pool = engine.pool
            pool_status = "healthy"
            pool_metrics = {}

            try:
                # Get pool statistics
                pool_size = pool.size()
                checked_in = pool.checkedin()
                checked_out = pool.checkedout()
                overflow = pool.overflow()

                pool_metrics = {
                    "pool_size": pool_size,
                    "connections_checked_in": checked_in,
                    "connections_checked_out": checked_out,
                    "connections_overflow": overflow,
                    "connections_available": checked_in,
                    "connections_in_use": checked_out,
                }

                # Check pool health thresholds
                if checked_in < 2:
                    pool_status = "warning"
                    pool_metrics["warning"] = "Low available connections"
                if checked_in == 0 and checked_out >= pool_size:
                    pool_status = "critical"
                    pool_metrics["warning"] = "Pool exhausted"

            except Exception as pool_err:
                pool_metrics["pool_error"] = str(pool_err)
                pool_status = "unknown"

            # Determine overall status
            status = ComponentStatus.UP
            if pool_status == "critical":
                status = ComponentStatus.DEGRADED

            return ComponentHealth(
                status=status,
                latency_ms=round(latency, 2),
                details={
                    "database_url": _mask_connection_string(settings.database_url),
                    "pool_status": pool_status,
                    **pool_metrics,
                },
            )

    except asyncio.TimeoutError:
        return ComponentHealth(
            status=ComponentStatus.DOWN,
            latency_ms=HEALTH_CHECK_TIMEOUT * 1000,
            error="Database query timed out",
        )
    except Exception as e:
        latency = (time.perf_counter() - start_time) * 1000
        return ComponentHealth(
            status=ComponentStatus.DOWN,
            latency_ms=round(latency, 2),
            error=str(e),
        )


async def check_redis() -> ComponentHealth:
    """Check Redis connectivity.

    Executes a PING command to verify Redis is responding.

    Returns:
        ComponentHealth with Redis status.
    """
    start_time = time.perf_counter()

    try:
        from app.core.redis import get_redis

        redis_client = get_redis()

        # Execute ping with timeout
        # VP-Deprecation-4: Use asyncio.to_thread() instead of deprecated get_event_loop()
        result = await asyncio.wait_for(
            asyncio.to_thread(redis_client.ping),
            timeout=HEALTH_CHECK_TIMEOUT,
        )

        latency = (time.perf_counter() - start_time) * 1000

        if result:
            return ComponentHealth(
                status=ComponentStatus.UP,
                latency_ms=round(latency, 2),
                details={"redis_url": _mask_connection_string(settings.redis_url)},
            )
        else:
            return ComponentHealth(
                status=ComponentStatus.DOWN,
                latency_ms=round(latency, 2),
                error="Redis ping returned False",
            )

    except asyncio.TimeoutError:
        return ComponentHealth(
            status=ComponentStatus.DOWN,
            latency_ms=HEALTH_CHECK_TIMEOUT * 1000,
            error="Redis ping timed out",
        )
    except Exception as e:
        latency = (time.perf_counter() - start_time) * 1000
        return ComponentHealth(
            status=ComponentStatus.DOWN,
            latency_ms=round(latency, 2),
            error=str(e),
        )


async def check_neo4j() -> ComponentHealth:
    """Check Neo4j graph database connectivity.

    Uses the GraphDatabaseService health check.

    Returns:
        ComponentHealth with Neo4j status.
    """
    start_time = time.perf_counter()

    try:
        from app.services.graph_database_service import get_graph_database_service

        graph_service = get_graph_database_service()

        # Execute health check with timeout
        # VP-Deprecation-4: Use asyncio.to_thread() instead of deprecated get_event_loop()
        health_result = await asyncio.wait_for(
            asyncio.to_thread(graph_service.health_check),
            timeout=HEALTH_CHECK_TIMEOUT,
        )

        latency = (time.perf_counter() - start_time) * 1000

        if health_result.status.value in ("connected", "mock_mode"):
            return ComponentHealth(
                status=ComponentStatus.UP,
                latency_ms=health_result.latency_ms or round(latency, 2),
                details={
                    "mode": health_result.status.value,
                    "server_version": health_result.server_version,
                    "database": health_result.database,
                },
            )
        else:
            return ComponentHealth(
                status=ComponentStatus.DOWN,
                latency_ms=health_result.latency_ms or round(latency, 2),
                error=health_result.error_message,
            )

    except asyncio.TimeoutError:
        return ComponentHealth(
            status=ComponentStatus.DOWN,
            latency_ms=HEALTH_CHECK_TIMEOUT * 1000,
            error="Neo4j health check timed out",
        )
    except Exception as e:
        latency = (time.perf_counter() - start_time) * 1000
        return ComponentHealth(
            status=ComponentStatus.DOWN,
            latency_ms=round(latency, 2),
            error=str(e),
        )


async def check_kafka() -> ComponentHealth:
    """Check Kafka connectivity.

    Uses the KafkaService health check.

    Returns:
        ComponentHealth with Kafka status.
    """
    start_time = time.perf_counter()

    try:
        from app.services.kafka_service import get_kafka_service

        kafka_service = get_kafka_service()

        # Get health status
        health = kafka_service.get_health()

        latency = (time.perf_counter() - start_time) * 1000

        if health.connected:
            return ComponentHealth(
                status=ComponentStatus.UP,
                latency_ms=health.latency_ms or round(latency, 2),
                details={
                    "broker_count": health.broker_count,
                    "topic_count": health.topic_count,
                    "mock_mode": kafka_service.is_mock_mode(),
                },
            )
        else:
            return ComponentHealth(
                status=ComponentStatus.DOWN,
                latency_ms=round(latency, 2),
                error=health.error_message or "Kafka not connected",
            )

    except asyncio.TimeoutError:
        return ComponentHealth(
            status=ComponentStatus.DOWN,
            latency_ms=HEALTH_CHECK_TIMEOUT * 1000,
            error="Kafka health check timed out",
        )
    except Exception as e:
        latency = (time.perf_counter() - start_time) * 1000
        return ComponentHealth(
            status=ComponentStatus.DOWN,
            latency_ms=round(latency, 2),
            error=str(e),
        )


def _mask_connection_string(conn_str: str) -> str:
    """Mask sensitive parts of a connection string.

    Args:
        conn_str: Connection string that may contain passwords.

    Returns:
        Connection string with password masked.
    """
    import re

    # Mask password in URLs like postgresql://user:password@host
    return re.sub(r":([^:@]+)@", r":***@", conn_str)


def _determine_overall_status(checks: dict[str, ComponentHealth]) -> HealthStatus:
    """Determine overall health status from component checks.

    Args:
        checks: Dictionary of component health checks.

    Returns:
        Overall health status.
    """
    critical_down = any(
        checks.get(service, ComponentHealth(status=ComponentStatus.DOWN)).status
        == ComponentStatus.DOWN
        for service in CRITICAL_SERVICES
    )

    if critical_down:
        return HealthStatus.UNHEALTHY

    non_critical_down = any(
        checks.get(service, ComponentHealth(status=ComponentStatus.DOWN)).status
        == ComponentStatus.DOWN
        for service in NON_CRITICAL_SERVICES
        if service in checks
    )

    if non_critical_down:
        return HealthStatus.DEGRADED

    return HealthStatus.HEALTHY


# =============================================================================
# Application Uptime Tracking
# =============================================================================

_app_start_time: float | None = None
_app_start_lock = threading.Lock()


def set_app_start_time(start_time: float) -> None:
    """Set the application start time for uptime calculation.

    Args:
        start_time: Unix timestamp when the app started.
    """
    global _app_start_time
    # VP-ThreadSafety: Lock for thread-safe write
    with _app_start_lock:
        _app_start_time = start_time


def get_uptime_seconds() -> float | None:
    """Get the application uptime in seconds.

    Returns:
        Uptime in seconds, or None if start time not set.
    """
    # VP-ThreadSafety: Read is atomic for float, no lock needed
    if _app_start_time is None:
        return None
    return time.time() - _app_start_time


# =============================================================================
# Endpoints
# =============================================================================


@router.get(
    "",
    response_model=HealthResponse,
    responses={
        200: {"description": "System is healthy"},
        503: {"description": "System is unhealthy"},
    },
    summary="Comprehensive health check",
    description="Performs health checks on all system dependencies and returns overall status.",
)
async def health_check(response: Response) -> HealthResponse:
    """Comprehensive health check endpoint.

    Checks all system dependencies in parallel:
    - Database connectivity
    - Redis availability
    - Neo4j graph database
    - Kafka message broker

    Returns 200 if healthy or degraded, 503 if unhealthy.
    """
    # VP-Reliability-1: Run all health checks in parallel with exception handling
    # return_exceptions=True ensures one failing check doesn't crash the entire endpoint
    results = await asyncio.gather(
        check_database(),
        check_redis(),
        check_neo4j(),
        check_kafka(),
        return_exceptions=True,
    )

    def _safe_result(result: ComponentHealth | Exception, name: str) -> ComponentHealth:
        """Convert exceptions to DOWN status instead of failing the endpoint."""
        if isinstance(result, Exception):
            logger.warning(f"Health check for {name} raised exception: {result}")
            return ComponentHealth(
                status=ComponentStatus.DOWN,
                error=f"Health check failed: {type(result).__name__}",
            )
        return result

    checks = {
        "database": _safe_result(results[0], "database"),
        "redis": _safe_result(results[1], "redis"),
        "neo4j": _safe_result(results[2], "neo4j"),
        "kafka": _safe_result(results[3], "kafka"),
    }

    overall_status = _determine_overall_status(checks)

    # Set HTTP status code based on health
    if overall_status == HealthStatus.UNHEALTHY:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status=overall_status,
        timestamp=datetime.now(timezone.utc).isoformat(),
        version="1.0.0",
        checks=checks,
        uptime_seconds=get_uptime_seconds(),
    )


@router.get(
    "/live",
    response_model=LivenessResponse,
    summary="Liveness probe",
    description="Simple liveness check for container orchestration. Always returns 200 if the process is running.",
)
async def liveness_probe() -> LivenessResponse:
    """Liveness probe endpoint.

    Simple check that the application is running.
    Use for Kubernetes liveness probes.

    Always returns 200 if the process is alive.
    """
    return LivenessResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={
        200: {"description": "System is ready to receive traffic"},
        503: {"description": "System is not ready"},
    },
    summary="Readiness probe",
    description="Checks if the system is ready to handle requests. Returns 200 if ready, 503 if not.",
)
async def readiness_probe(response: Response) -> ReadinessResponse:
    """Readiness probe endpoint.

    Checks if critical services are available.
    Use for Kubernetes readiness probes.

    Returns 200 if the database is available, 503 otherwise.
    """
    # Check only critical services for readiness
    database_check = await check_database()

    services_ready = 1 if database_check.status == ComponentStatus.UP else 0
    services_total = 1

    is_ready = database_check.status == ComponentStatus.UP

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(
        status="ready" if is_ready else "not_ready",
        timestamp=datetime.now(timezone.utc).isoformat(),
        services_ready=services_ready,
        services_total=services_total,
    )


def _get_system_metrics() -> SystemMetrics:
    """Collect system resource metrics.

    VP-DevOps: Enhanced health check with system information.

    Returns:
        SystemMetrics with memory, disk, and system info.
    """
    import sys

    # System info (always available)
    system_info = SystemInfo(
        hostname=platform.node(),
        os=platform.system(),
        os_version=platform.release(),
        python_version=sys.version.split()[0],
        cpu_count=os.cpu_count() or 1,
        process_id=os.getpid(),
    )

    # Memory info (requires psutil, gracefully handle if not available)
    memory_info = None
    disk_info = None
    load_average = None

    try:
        import psutil

        # Memory
        mem = psutil.virtual_memory()
        memory_info = MemoryInfo(
            total_mb=round(mem.total / (1024 * 1024), 2),
            available_mb=round(mem.available / (1024 * 1024), 2),
            used_mb=round(mem.used / (1024 * 1024), 2),
            percent_used=mem.percent,
        )

        # Disk
        disk = psutil.disk_usage("/")
        disk_info = DiskInfo(
            total_gb=round(disk.total / (1024 * 1024 * 1024), 2),
            free_gb=round(disk.free / (1024 * 1024 * 1024), 2),
            used_gb=round(disk.used / (1024 * 1024 * 1024), 2),
            percent_used=disk.percent,
        )
    except ImportError:
        logger.debug("psutil not available, skipping memory/disk metrics")
    except Exception as e:
        logger.warning(f"Failed to collect memory/disk metrics: {e}")

    # Load average (Unix only)
    try:
        load_average = list(os.getloadavg())
    except (AttributeError, OSError):
        pass  # Not available on Windows

    return SystemMetrics(
        memory=memory_info,
        disk=disk_info,
        system=system_info,
        load_average=load_average,
    )


@router.get(
    "/deep",
    response_model=DeepHealthResponse,
    responses={
        200: {"description": "System is healthy"},
        503: {"description": "System is unhealthy"},
    },
    summary="Deep health check with system metrics",
    description="Comprehensive health check including system resource metrics. Use for debugging and monitoring.",
)
async def deep_health_check(response: Response) -> DeepHealthResponse:
    """Deep health check endpoint with system metrics.

    VP-DevOps: Enhanced health check that includes:
    - All standard service health checks
    - System metrics (CPU, memory, disk)
    - Environment information

    Use for detailed system monitoring and debugging.
    """
    # VP-Reliability-1: Run all health checks in parallel with exception handling
    results = await asyncio.gather(
        check_database(),
        check_redis(),
        check_neo4j(),
        check_kafka(),
        return_exceptions=True,
    )

    def _safe_result(result: ComponentHealth | Exception, name: str) -> ComponentHealth:
        """Convert exceptions to DOWN status instead of failing the endpoint."""
        if isinstance(result, Exception):
            logger.warning(f"Health check for {name} raised exception: {result}")
            return ComponentHealth(
                status=ComponentStatus.DOWN,
                error=f"Health check failed: {type(result).__name__}",
            )
        return result

    checks = {
        "database": _safe_result(results[0], "database"),
        "redis": _safe_result(results[1], "redis"),
        "neo4j": _safe_result(results[2], "neo4j"),
        "kafka": _safe_result(results[3], "kafka"),
    }

    overall_status = _determine_overall_status(checks)

    # Collect system metrics
    system_metrics = _get_system_metrics()

    # Set HTTP status code based on health
    if overall_status == HealthStatus.UNHEALTHY:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return DeepHealthResponse(
        status=overall_status,
        timestamp=datetime.now(timezone.utc).isoformat(),
        version="1.0.0",
        environment="development" if settings.debug else "production",
        checks=checks,
        system_metrics=system_metrics,
        uptime_seconds=get_uptime_seconds(),
    )


@router.get(
    "/detailed",
    summary="Detailed health check with per-component SLI data",
    description=(
        "Returns detailed health status for every infrastructure component "
        "including PostgreSQL, Redis, Neo4j, NLP service, disk space, and memory usage. "
        "Designed for SLA monitoring dashboards."
    ),
    responses={
        200: {"description": "System is healthy or degraded"},
        503: {"description": "System is unhealthy"},
    },
)
async def detailed_health_check(response: Response) -> dict[str, Any]:
    """Detailed health check endpoint for SLA monitoring.

    VPE-4: Enhanced health check that returns per-component status with
    latency measurements, suitable for SLI collection and SLA verification.

    Components checked:
    - PostgreSQL: connection + query latency
    - Redis: ping + latency
    - Neo4j: connection check (if configured)
    - NLP service: availability check
    - Disk space: threshold check
    - Memory usage: threshold check

    Returns structured JSON for SLA dashboards.
    """
    overall_start = time.perf_counter()
    components: dict[str, Any] = {}

    # --- PostgreSQL ---
    db_start = time.perf_counter()
    try:
        from sqlalchemy import text
        from app.core.database import async_session_maker

        async with async_session_maker() as session:
            await asyncio.wait_for(
                session.execute(text("SELECT 1")),
                timeout=HEALTH_CHECK_TIMEOUT,
            )
        db_latency = (time.perf_counter() - db_start) * 1000
        components["postgresql"] = {
            "status": "up",
            "latency_ms": round(db_latency, 2),
        }
    except Exception as e:
        db_latency = (time.perf_counter() - db_start) * 1000
        components["postgresql"] = {
            "status": "down",
            "latency_ms": round(db_latency, 2),
            "error": str(e),
        }

    # --- Redis ---
    redis_start = time.perf_counter()
    try:
        from app.core.redis import get_redis

        redis_client = get_redis()
        result = await asyncio.wait_for(
            asyncio.to_thread(redis_client.ping),
            timeout=HEALTH_CHECK_TIMEOUT,
        )
        redis_latency = (time.perf_counter() - redis_start) * 1000
        components["redis"] = {
            "status": "up" if result else "down",
            "latency_ms": round(redis_latency, 2),
        }
    except Exception as e:
        redis_latency = (time.perf_counter() - redis_start) * 1000
        components["redis"] = {
            "status": "down",
            "latency_ms": round(redis_latency, 2),
            "error": str(e),
        }

    # --- Neo4j (optional) ---
    neo4j_start = time.perf_counter()
    try:
        from app.services.graph_database_service import get_graph_database_service

        graph_service = get_graph_database_service()
        health_result = await asyncio.wait_for(
            asyncio.to_thread(graph_service.health_check),
            timeout=HEALTH_CHECK_TIMEOUT,
        )
        neo4j_latency = (time.perf_counter() - neo4j_start) * 1000
        is_up = health_result.status.value in ("connected", "mock_mode")
        components["neo4j"] = {
            "status": "up" if is_up else "down",
            "latency_ms": round(neo4j_latency, 2),
            "mode": health_result.status.value,
        }
        if not is_up and health_result.error_message:
            components["neo4j"]["error"] = health_result.error_message
    except Exception as e:
        neo4j_latency = (time.perf_counter() - neo4j_start) * 1000
        components["neo4j"] = {
            "status": "down",
            "latency_ms": round(neo4j_latency, 2),
            "error": str(e),
        }

    # --- NLP Service ---
    nlp_start = time.perf_counter()
    try:
        from app.services.vocabulary import get_vocabulary_service

        vocab = get_vocabulary_service()
        stats = vocab.get_stats()
        nlp_latency = (time.perf_counter() - nlp_start) * 1000
        is_loaded = stats.get("concept_count", 0) > 0
        components["nlp_service"] = {
            "status": "up" if is_loaded else "degraded",
            "latency_ms": round(nlp_latency, 2),
            "concept_count": stats.get("concept_count", 0),
            "term_count": stats.get("term_count", 0),
        }
    except Exception as e:
        nlp_latency = (time.perf_counter() - nlp_start) * 1000
        components["nlp_service"] = {
            "status": "down",
            "latency_ms": round(nlp_latency, 2),
            "error": str(e),
        }

    # --- Disk Space ---
    try:
        import shutil

        usage = shutil.disk_usage("/")
        total_gb = usage.total / (1024 ** 3)
        free_gb = usage.free / (1024 ** 3)
        used_pct = ((usage.total - usage.free) / usage.total) * 100
        disk_status = "up"
        if used_pct > 90:
            disk_status = "critical"
        elif used_pct > 80:
            disk_status = "warning"
        components["disk_space"] = {
            "status": disk_status,
            "total_gb": round(total_gb, 2),
            "free_gb": round(free_gb, 2),
            "used_percent": round(used_pct, 1),
        }
    except Exception as e:
        components["disk_space"] = {
            "status": "unknown",
            "error": str(e),
        }

    # --- Memory Usage ---
    try:
        import psutil

        mem = psutil.virtual_memory()
        mem_status = "up"
        if mem.percent > 95:
            mem_status = "critical"
        elif mem.percent > 85:
            mem_status = "warning"
        components["memory"] = {
            "status": mem_status,
            "total_mb": round(mem.total / (1024 * 1024), 2),
            "available_mb": round(mem.available / (1024 * 1024), 2),
            "used_percent": round(mem.percent, 1),
        }
    except ImportError:
        components["memory"] = {
            "status": "unknown",
            "error": "psutil not installed",
        }
    except Exception as e:
        components["memory"] = {
            "status": "unknown",
            "error": str(e),
        }

    # --- Determine overall status ---
    statuses = [c.get("status", "unknown") for c in components.values()]
    if components.get("postgresql", {}).get("status") == "down":
        overall = "unhealthy"
    elif "down" in statuses or "critical" in statuses:
        overall = "degraded"
    elif "warning" in statuses:
        overall = "degraded"
    else:
        overall = "healthy"

    total_latency = (time.perf_counter() - overall_start) * 1000

    if overall == "unhealthy":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": overall,
        "components": components,
        "latency_ms": round(total_latency, 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": get_uptime_seconds(),
    }


@router.get(
    "/cache",
    summary="Get terminology cache statistics",
    description="Returns hit/miss rates and sizes for all terminology caches.",
)
async def get_cache_stats() -> dict[str, Any]:
    return get_all_cache_stats()


@router.post(
    "/cache/clear",
    summary="Clear all terminology caches",
    description="Invalidates all cached terminology results.",
)
async def clear_caches() -> dict[str, str]:
    clear_all_caches()
    return {"status": "cleared"}
