"""API endpoints for Knowledge Graph Benchmarking.

This module provides REST API endpoints for running and managing
MedAgentBench and DR.KNOWS benchmarks against the knowledge graph.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import log_and_raise_internal_error
from app.core.database import get_db

from app.services.drknows_benchmark_service import (
    DRKNOWSBenchmarkService,
    get_drknows_benchmark_service,
)
from app.services.medagentbench_service import (
    BenchmarkCategory,
    DifficultyLevel,
    MedAgentBenchService,
    get_medagentbench_service,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/kg/benchmark", tags=["kg-benchmark"])


# Request/Response Models

class RunSuiteRequest(BaseModel):
    """Request to run a benchmark suite."""

    suite_id: str = Field(..., description="ID of the benchmark suite to run")


class CustomCaseRequest(BaseModel):
    """Request to create a custom benchmark case."""

    case_id: str = Field(..., description="Unique case ID")
    category: str = Field(..., description="Benchmark category")
    difficulty: str = Field(..., description="Difficulty level")
    question: str = Field(..., description="The question to answer")
    expected_answer: str | list[str] = Field(..., description="Expected answer(s)")
    context: dict[str, Any] | None = Field(default=None, description="Additional context")
    expected_entities: list[str] | None = Field(default=None, description="Expected entities")
    reasoning_steps: list[str] | None = Field(default=None, description="Expected reasoning steps")


class BenchmarkComparisonRequest(BaseModel):
    """Request to compare benchmark results to baseline."""

    baseline_name: str = Field(default="DR.KNOWS", description="Baseline system to compare against")


class SuiteResponse(BaseModel):
    """Response containing suite information."""

    suite_id: str
    name: str
    description: str
    case_count: int
    version: str


class BenchmarkResultSummary(BaseModel):
    """Summary of benchmark results."""

    suite_id: str
    suite_name: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    overall_accuracy: float
    category_scores: dict[str, float]
    difficulty_scores: dict[str, float]
    avg_execution_time_ms: float


# MedAgentBench Endpoints

@router.get("/medagentbench/suites", response_model=list[SuiteResponse])
async def list_benchmark_suites() -> list[dict[str, Any]]:
    """List all available MedAgentBench benchmark suites."""
    service = get_medagentbench_service()
    return service.list_suites()


@router.get("/medagentbench/suites/{suite_id}")
async def get_benchmark_suite(suite_id: str) -> dict[str, Any]:
    """Get details of a specific benchmark suite."""
    service = get_medagentbench_service()
    suite = service.get_suite(suite_id)

    if not suite:
        raise HTTPException(status_code=404, detail=f"Suite not found: {suite_id}")

    return {
        "suite_id": suite.suite_id,
        "name": suite.name,
        "description": suite.description,
        "version": suite.version,
        "case_count": len(suite.cases),
        "cases": [
            {
                "case_id": case.case_id,
                "category": case.category.value,
                "difficulty": case.difficulty.value,
                "question": case.question,
            }
            for case in suite.cases
        ],
    }


@router.post("/medagentbench/run/{suite_id}")
async def run_benchmark_suite(suite_id: str) -> dict[str, Any]:
    """Run a MedAgentBench benchmark suite.

    Note: This runs with a mock agent for testing purposes.
    In production, connect to the actual KG reasoning service.
    """
    service = get_medagentbench_service()

    if not service.get_suite(suite_id):
        raise HTTPException(status_code=404, detail=f"Suite not found: {suite_id}")

    # Mock agent for demonstration
    async def mock_agent(case: Any) -> dict[str, Any]:
        # In production, this would call the actual KG reasoning service
        return {
            "answer": "Metformin",  # Default answer for testing
            "reasoning_trace": ["Analyzed clinical context", "Found relevant concepts"],
        }

    try:
        report = await service.run_suite(suite_id, mock_agent)

        return {
            "suite_id": report.suite_id,
            "suite_name": report.suite_name,
            "total_cases": report.total_cases,
            "passed_cases": report.passed_cases,
            "failed_cases": report.failed_cases,
            "overall_accuracy": report.overall_accuracy,
            "category_scores": report.category_scores,
            "difficulty_scores": report.difficulty_scores,
            "avg_execution_time_ms": report.avg_execution_time_ms,
            "metrics": report.metrics,
            "run_at": report.run_at.isoformat(),
        }
    except Exception as e:
        raise log_and_raise_internal_error(
            exception=e,
            endpoint="/kg/benchmark/medagentbench/run",
            user_message="Failed to run benchmark suite",
        )


@router.post("/medagentbench/compare")
async def compare_to_baseline(request: BenchmarkComparisonRequest) -> dict[str, Any]:
    """Compare the most recent benchmark results to a baseline system."""
    service = get_medagentbench_service()

    # For demonstration, create a sample report
    # In production, retrieve the actual last run
    from app.services.medagentbench_service import BenchmarkReport
    from datetime import datetime, timezone

    sample_report = BenchmarkReport(
        suite_id="qa_basic",
        suite_name="Medical Question Answering",
        total_cases=10,
        passed_cases=8,
        failed_cases=2,
        overall_accuracy=0.80,
        category_scores={"question_answering": 0.80},
        difficulty_scores={"easy": 0.90, "medium": 0.75},
        avg_execution_time_ms=50.0,
        results=[],
    )

    comparison = service.compare_to_baseline(sample_report, request.baseline_name)
    return comparison


@router.get("/medagentbench/categories")
async def list_benchmark_categories() -> list[dict[str, str]]:
    """List all benchmark categories."""
    return [
        {"value": cat.value, "name": cat.name}
        for cat in BenchmarkCategory
    ]


@router.get("/medagentbench/difficulties")
async def list_difficulty_levels() -> list[dict[str, str]]:
    """List all difficulty levels."""
    return [
        {"value": level.value, "name": level.name}
        for level in DifficultyLevel
    ]


# DR.KNOWS Benchmark Endpoints

@router.post("/drknows/run")
async def run_drknows_benchmark(
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Run a complete DR.KNOWS-style benchmark.

    This runs the full benchmark suite including:
    - Path discovery metrics (real KG traversal)
    - Reasoning accuracy (real KG path matching)
    - Semantic coverage (real node_type distribution)
    - Knowledge coverage (real node/edge counts)
    - Multi-hop accuracy
    - Temporal reasoning
    - Explanation quality
    """
    service = get_drknows_benchmark_service(db_session=session)

    try:
        result = await service.run_full_benchmark(None)

        return service.export_benchmark_report(result)
    except Exception as e:
        raise log_and_raise_internal_error(
            exception=e,
            endpoint="/kg/benchmark/drknows/run",
            user_message="Failed to run DR.KNOWS benchmark",
        )


@router.get("/drknows/history")
async def get_drknows_history(
    limit: int = Query(default=10, ge=1, le=100, description="Number of results to return"),
) -> list[dict[str, Any]]:
    """Get history of DR.KNOWS benchmark runs."""
    service = get_drknows_benchmark_service()

    history = service.get_benchmark_history()[-limit:]

    return [
        {
            "benchmark_id": result.benchmark_id,
            "run_at": result.run_at.isoformat(),
            "overall_score": result.overall_score,
            "status": result.comparison_to_baseline.get("status", "unknown"),
        }
        for result in history
    ]


@router.get("/drknows/latest")
async def get_latest_drknows_result() -> dict[str, Any]:
    """Get the most recent DR.KNOWS benchmark result."""
    service = get_drknows_benchmark_service()

    result = service.get_latest_benchmark()
    if not result:
        raise HTTPException(status_code=404, detail="No benchmark results available")

    return service.export_benchmark_report(result)


@router.get("/drknows/trend")
async def get_drknows_trend() -> dict[str, Any]:
    """Get trend analysis across DR.KNOWS benchmark runs."""
    service = get_drknows_benchmark_service()
    return service.get_trend_analysis()


@router.get("/drknows/baseline")
async def get_drknows_baseline() -> dict[str, Any]:
    """Get the DR.KNOWS baseline metrics for comparison."""
    from app.services.drknows_benchmark_service import DRKNOWS_BASELINE

    return {
        "baseline_name": "DR.KNOWS",
        "source": "Published paper metrics",
        "metrics": DRKNOWS_BASELINE,
    }


@router.get("/drknows/semantic-groups")
async def get_umls_semantic_groups() -> dict[str, str]:
    """Get UMLS semantic groups used in benchmarking."""
    from app.services.drknows_benchmark_service import UMLS_SEMANTIC_GROUPS

    return UMLS_SEMANTIC_GROUPS


# Health Check

@router.get("/health")
async def benchmark_health() -> dict[str, Any]:
    """Health check for benchmarking services."""
    medagent_service = get_medagentbench_service()
    drknows_service = get_drknows_benchmark_service()

    return {
        "status": "healthy",
        "services": {
            "medagentbench": {
                "available": True,
                "suites_count": len(medagent_service.list_suites()),
            },
            "drknows": {
                "available": True,
                "history_count": len(drknows_service.get_benchmark_history()),
            },
        },
    }
