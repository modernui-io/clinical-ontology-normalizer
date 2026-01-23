"""Health check endpoints for Clinical Ontology Normalizer.

Provides comprehensive health checks for all system dependencies including:
- Database connectivity
- Redis availability
- Neo4j graph database
- Kafka message broker

Health status follows a simple model:
- "healthy": All checks pass
- "degraded": Some non-critical services unavailable
- "unhealthy": Critical services unavailable

Usage:
    GET /api/v1/health - Comprehensive health check
    GET /api/v1/health/live - Simple liveness probe
    GET /api/v1/health/ready - Readiness probe
"""

import asyncio
import logging
import time
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.terminology_cache import get_all_cache_stats, clear_all_caches

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


# =============================================================================
# Health Check Functions
# =============================================================================


async def check_database() -> ComponentHealth:
    """Check database connectivity.

    Executes a simple SELECT query to verify the database is responding.

    Returns:
        ComponentHealth with database status.
    """
    start_time = time.perf_counter()

    try:
        from sqlalchemy import text

        from app.core.database import async_session_maker

        async with async_session_maker() as session:
            # Execute a simple query with timeout
            result = await asyncio.wait_for(
                session.execute(text("SELECT 1")),
                timeout=HEALTH_CHECK_TIMEOUT,
            )
            result.scalar()

            latency = (time.perf_counter() - start_time) * 1000

            return ComponentHealth(
                status=ComponentStatus.UP,
                latency_ms=round(latency, 2),
                details={"database_url": _mask_connection_string(settings.database_url)},
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
        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(None, redis_client.ping),
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
        loop = asyncio.get_event_loop()
        health_result = await asyncio.wait_for(
            loop.run_in_executor(None, graph_service.health_check),
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


def set_app_start_time(start_time: float) -> None:
    """Set the application start time for uptime calculation.

    Args:
        start_time: Unix timestamp when the app started.
    """
    global _app_start_time
    _app_start_time = start_time


def get_uptime_seconds() -> float | None:
    """Get the application uptime in seconds.

    Returns:
        Uptime in seconds, or None if start time not set.
    """
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
    # Run all health checks in parallel
    database_check, redis_check, neo4j_check, kafka_check = await asyncio.gather(
        check_database(),
        check_redis(),
        check_neo4j(),
        check_kafka(),
        return_exceptions=False,
    )

    checks = {
        "database": database_check,
        "redis": redis_check,
        "neo4j": neo4j_check,
        "kafka": kafka_check,
    }

    overall_status = _determine_overall_status(checks)

    # Set HTTP status code based on health
    if overall_status == HealthStatus.UNHEALTHY:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status=overall_status,
        timestamp=datetime.now(UTC).isoformat(),
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
        timestamp=datetime.now(UTC).isoformat(),
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
        timestamp=datetime.now(UTC).isoformat(),
        services_ready=services_ready,
        services_total=services_total,
    )


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
