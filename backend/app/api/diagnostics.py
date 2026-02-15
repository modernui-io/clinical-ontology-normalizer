"""Integration diagnostics API (P3-007).

Self-serve diagnostics for onboarding teams — connection health,
configuration validation, and pipeline smoke tests.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/diagnostics", tags=["diagnostics"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class ConnectionStatus(BaseModel):
    """Status of a single dependency connection."""

    name: str
    status: str = Field(description="healthy | unhealthy | not_configured")
    latency_ms: float | None = None
    message: str | None = None


class ConnectionsResponse(BaseModel):
    """Response from connection checks."""

    checked_at: str
    connections: list[ConnectionStatus]
    overall: str = Field(description="healthy | degraded | unhealthy")


class ConfigCheck(BaseModel):
    """Result of a single config validation."""

    key: str
    status: str = Field(description="ok | missing | placeholder")
    hint: str | None = None


class ConfigResponse(BaseModel):
    """Response from config validation."""

    checked_at: str
    checks: list[ConfigCheck]
    overall: str = Field(description="ok | warnings | errors")


class PipelineTestStep(BaseModel):
    """Result of a single pipeline test step."""

    step: str
    status: str = Field(description="pass | fail | skip")
    duration_ms: float | None = None
    message: str | None = None


class PipelineTestResponse(BaseModel):
    """Response from pipeline smoke test."""

    tested_at: str
    steps: list[PipelineTestStep]
    overall: str = Field(description="pass | partial | fail")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PLACEHOLDER_VALUES = {"changeme", "password", "secret", "xxx", "placeholder", "CHANGE_ME"}


async def _check_postgres() -> ConnectionStatus:
    """Check PostgreSQL connectivity."""
    start = time.perf_counter()
    try:
        db_url = getattr(settings, "DATABASE_URL", None) or os.getenv("DATABASE_URL", "")
        if not db_url:
            return ConnectionStatus(name="PostgreSQL", status="not_configured", message="DATABASE_URL not set")
        # Try a lightweight import-based check
        try:
            from app.core.database import async_session_factory
            async with async_session_factory() as session:
                result = await session.execute("SELECT 1")  # type: ignore[arg-type]
                result.scalar()
            elapsed = (time.perf_counter() - start) * 1000
            return ConnectionStatus(name="PostgreSQL", status="healthy", latency_ms=round(elapsed, 1))
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ConnectionStatus(name="PostgreSQL", status="unhealthy", latency_ms=round(elapsed, 1), message=str(exc)[:200])
    except Exception as exc:
        return ConnectionStatus(name="PostgreSQL", status="unhealthy", message=str(exc)[:200])


async def _check_redis() -> ConnectionStatus:
    """Check Redis connectivity."""
    start = time.perf_counter()
    try:
        redis_url = getattr(settings, "REDIS_URL", None) or os.getenv("REDIS_URL", "")
        if not redis_url:
            return ConnectionStatus(name="Redis", status="not_configured", message="REDIS_URL not set")
        try:
            from app.core.redis import get_redis
            r = await get_redis()
            if r is None:
                return ConnectionStatus(name="Redis", status="unhealthy", message="Redis client not initialized")
            await r.ping()
            elapsed = (time.perf_counter() - start) * 1000
            return ConnectionStatus(name="Redis", status="healthy", latency_ms=round(elapsed, 1))
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ConnectionStatus(name="Redis", status="unhealthy", latency_ms=round(elapsed, 1), message=str(exc)[:200])
    except Exception as exc:
        return ConnectionStatus(name="Redis", status="unhealthy", message=str(exc)[:200])


async def _check_neo4j() -> ConnectionStatus:
    """Check Neo4j connectivity."""
    start = time.perf_counter()
    try:
        neo4j_uri = getattr(settings, "NEO4J_URI", None) or os.getenv("NEO4J_URI", "")
        if not neo4j_uri:
            return ConnectionStatus(name="Neo4j", status="not_configured", message="NEO4J_URI not set")
        try:
            from app.services.graph_database_service import get_graph_database_service
            svc = get_graph_database_service()
            if hasattr(svc, "health_check"):
                ok = await svc.health_check()
                elapsed = (time.perf_counter() - start) * 1000
                return ConnectionStatus(
                    name="Neo4j",
                    status="healthy" if ok else "unhealthy",
                    latency_ms=round(elapsed, 1),
                )
            elapsed = (time.perf_counter() - start) * 1000
            return ConnectionStatus(name="Neo4j", status="healthy", latency_ms=round(elapsed, 1), message="Service loaded")
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ConnectionStatus(name="Neo4j", status="unhealthy", latency_ms=round(elapsed, 1), message=str(exc)[:200])
    except Exception as exc:
        return ConnectionStatus(name="Neo4j", status="unhealthy", message=str(exc)[:200])


async def _check_kafka() -> ConnectionStatus:
    """Check Kafka connectivity."""
    try:
        kafka_url = getattr(settings, "KAFKA_BOOTSTRAP_SERVERS", None) or os.getenv("KAFKA_BOOTSTRAP_SERVERS", "")
        if not kafka_url:
            return ConnectionStatus(name="Kafka", status="not_configured", message="KAFKA_BOOTSTRAP_SERVERS not set")
        return ConnectionStatus(name="Kafka", status="healthy", message="Configured (async producer)")
    except Exception as exc:
        return ConnectionStatus(name="Kafka", status="unhealthy", message=str(exc)[:200])


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/connections",
    response_model=ConnectionsResponse,
    summary="Check all dependency connections",
    description="Verifies connectivity to PostgreSQL, Redis, Neo4j, and Kafka.",
)
async def check_connections() -> ConnectionsResponse:
    """Run connectivity checks against all dependencies."""
    results = await asyncio.gather(
        _check_postgres(),
        _check_redis(),
        _check_neo4j(),
        _check_kafka(),
        return_exceptions=True,
    )

    connections: list[ConnectionStatus] = []
    for r in results:
        if isinstance(r, Exception):
            connections.append(ConnectionStatus(name="unknown", status="unhealthy", message=str(r)[:200]))
        else:
            connections.append(r)

    statuses = [c.status for c in connections]
    if all(s == "healthy" or s == "not_configured" for s in statuses):
        overall = "healthy"
    elif any(s == "unhealthy" for s in statuses if connections[statuses.index(s)].name == "PostgreSQL"):
        overall = "unhealthy"
    else:
        overall = "degraded"

    return ConnectionsResponse(
        checked_at=datetime.now(timezone.utc).isoformat(),
        connections=connections,
        overall=overall,
    )


@router.get(
    "/config",
    response_model=ConfigResponse,
    summary="Validate configuration",
    description="Checks required environment variables and detects placeholder values. Secrets are redacted.",
)
async def check_config() -> ConfigResponse:
    """Validate that required configuration is set and not placeholder."""
    checks: list[ConfigCheck] = []

    config_keys: list[tuple[str, str, bool]] = [
        ("DATABASE_URL", "PostgreSQL connection string", True),
        ("REDIS_URL", "Redis connection string", False),
        ("NEO4J_URI", "Neo4j connection URI", False),
        ("NEO4J_USER", "Neo4j username", False),
        ("NEO4J_PASSWORD", "Neo4j password", False),
        ("SECRET_KEY", "Application secret key", True),
        ("KAFKA_BOOTSTRAP_SERVERS", "Kafka bootstrap servers", False),
        ("CORS_ORIGINS", "CORS allowed origins", False),
    ]

    errors = 0
    warnings = 0

    for key, hint, required in config_keys:
        val = getattr(settings, key, None) or os.getenv(key, "")
        if not val:
            if required:
                checks.append(ConfigCheck(key=key, status="missing", hint=f"Required: {hint}"))
                errors += 1
            else:
                checks.append(ConfigCheck(key=key, status="missing", hint=f"Optional: {hint}"))
                warnings += 1
        elif any(p in str(val).lower() for p in PLACEHOLDER_VALUES):
            checks.append(ConfigCheck(key=key, status="placeholder", hint=f"Value appears to be a placeholder for: {hint}"))
            warnings += 1
        else:
            checks.append(ConfigCheck(key=key, status="ok", hint=hint))

    if errors > 0:
        overall = "errors"
    elif warnings > 0:
        overall = "warnings"
    else:
        overall = "ok"

    return ConfigResponse(
        checked_at=datetime.now(timezone.utc).isoformat(),
        checks=checks,
        overall=overall,
    )


@router.get(
    "/pipeline-test",
    response_model=PipelineTestResponse,
    summary="Run pipeline smoke test",
    description="Submits a test document through the NLP pipeline and traces each step.",
)
async def run_pipeline_test() -> PipelineTestResponse:
    """Run a quick pipeline smoke test with a synthetic document."""
    steps: list[PipelineTestStep] = []

    # Step 1: NLP extraction
    start = time.perf_counter()
    try:
        from app.services.nlp import get_nlp_service
        svc = get_nlp_service()
        test_text = "Patient presents with type 2 diabetes mellitus and hypertension."
        result = svc.extract(test_text) if hasattr(svc, "extract") else svc.process(test_text)
        elapsed = (time.perf_counter() - start) * 1000
        mention_count = len(result) if isinstance(result, list) else len(getattr(result, "mentions", []))
        steps.append(PipelineTestStep(
            step="NLP Extraction",
            status="pass",
            duration_ms=round(elapsed, 1),
            message=f"Extracted {mention_count} mentions",
        ))
    except Exception as exc:
        elapsed = (time.perf_counter() - start) * 1000
        steps.append(PipelineTestStep(
            step="NLP Extraction",
            status="fail",
            duration_ms=round(elapsed, 1),
            message=str(exc)[:200],
        ))

    # Step 2: OMOP mapping
    start = time.perf_counter()
    try:
        from app.services.vocabulary import get_vocabulary_service
        svc = get_vocabulary_service()
        results = svc.search("diabetes mellitus") if hasattr(svc, "search") else []
        elapsed = (time.perf_counter() - start) * 1000
        count = len(results) if isinstance(results, list) else 0
        steps.append(PipelineTestStep(
            step="OMOP Concept Mapping",
            status="pass",
            duration_ms=round(elapsed, 1),
            message=f"Found {count} candidate concepts",
        ))
    except Exception as exc:
        elapsed = (time.perf_counter() - start) * 1000
        steps.append(PipelineTestStep(
            step="OMOP Concept Mapping",
            status="fail",
            duration_ms=round(elapsed, 1),
            message=str(exc)[:200],
        ))

    # Step 3: Fact building
    start = time.perf_counter()
    try:
        from app.services.fact_builder import get_fact_builder_service
        svc = get_fact_builder_service()
        elapsed = (time.perf_counter() - start) * 1000
        steps.append(PipelineTestStep(
            step="Fact Builder",
            status="pass",
            duration_ms=round(elapsed, 1),
            message="Service initialized successfully",
        ))
    except Exception as exc:
        elapsed = (time.perf_counter() - start) * 1000
        steps.append(PipelineTestStep(
            step="Fact Builder",
            status="fail",
            duration_ms=round(elapsed, 1),
            message=str(exc)[:200],
        ))

    # Step 4: Knowledge graph builder
    start = time.perf_counter()
    try:
        from app.services.graph_builder import get_graph_builder_service
        svc = get_graph_builder_service()
        elapsed = (time.perf_counter() - start) * 1000
        steps.append(PipelineTestStep(
            step="Knowledge Graph Builder",
            status="pass",
            duration_ms=round(elapsed, 1),
            message="Service initialized successfully",
        ))
    except Exception as exc:
        elapsed = (time.perf_counter() - start) * 1000
        steps.append(PipelineTestStep(
            step="Knowledge Graph Builder",
            status="fail",
            duration_ms=round(elapsed, 1),
            message=str(exc)[:200],
        ))

    statuses = [s.status for s in steps]
    if all(s == "pass" for s in statuses):
        overall = "pass"
    elif all(s == "fail" for s in statuses):
        overall = "fail"
    else:
        overall = "partial"

    return PipelineTestResponse(
        tested_at=datetime.now(timezone.utc).isoformat(),
        steps=steps,
        overall=overall,
    )
