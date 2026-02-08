"""Performance Benchmarks & SLA Management API endpoints (CTO-9).

Provides endpoints for:
- Recording and querying benchmark results
- SLA definition CRUD and compliance monitoring
- Performance trend analysis and regression detection
- Benchmark suite management and execution
- Version-to-version performance comparison
- Aggregate performance metrics
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas.performance_benchmarks import (
    BenchmarkCategory,
    BenchmarkListResponse,
    BenchmarkResult,
    BenchmarkResultCreate,
    BenchmarkSuite,
    BenchmarkSuiteCreate,
    BenchmarkSuiteListResponse,
    BenchmarkSuiteRunResult,
    PerformanceMetrics,
    PerformanceTrend,
    RegressionReport,
    SLAComplianceSummary,
    SLADefinition,
    SLADefinitionCreate,
    SLADefinitionUpdate,
    SLAListResponse,
    SLAStatus,
    SLATier,
    VersionComparison,
)
from app.services.performance_benchmark_service import get_performance_benchmark_service

router = APIRouter(prefix="/performance-benchmarks", tags=["Performance Benchmarks"])


# ============================================================================
# Benchmark CRUD
# ============================================================================


@router.post(
    "/benchmarks",
    response_model=BenchmarkResult,
    summary="Record a benchmark result",
    description="Record a new performance benchmark measurement.",
)
async def record_benchmark(request: BenchmarkResultCreate) -> BenchmarkResult:
    """Record a new benchmark measurement."""
    service = get_performance_benchmark_service()
    return service.record_benchmark(
        category=request.category,
        operation_name=request.operation_name,
        results_dict=request.model_dump(exclude={"category", "operation_name"}),
    )


@router.get(
    "/benchmarks",
    response_model=BenchmarkListResponse,
    summary="List benchmark results",
    description="Query benchmark results with optional category/operation filters.",
)
async def list_benchmarks(
    category: BenchmarkCategory | None = Query(None, description="Filter by category"),
    operation: str | None = Query(None, description="Filter by operation name"),
    limit: int = Query(50, ge=1, le=500, description="Maximum results"),
) -> BenchmarkListResponse:
    """List benchmark results."""
    service = get_performance_benchmark_service()
    results = service.get_benchmarks(category=category, operation_name=operation, limit=limit)
    return BenchmarkListResponse(total=len(results), results=results)


@router.get(
    "/benchmarks/{benchmark_id}",
    response_model=BenchmarkResult,
    summary="Get benchmark result",
    description="Get a specific benchmark result by ID.",
)
async def get_benchmark(benchmark_id: str) -> BenchmarkResult:
    """Get a single benchmark result."""
    service = get_performance_benchmark_service()
    result = service.get_benchmark(benchmark_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Benchmark '{benchmark_id}' not found")
    return result


# ============================================================================
# SLA CRUD
# ============================================================================


@router.post(
    "/slas",
    response_model=SLADefinition,
    summary="Create SLA definition",
    description="Create a new SLA definition for an operation.",
)
async def create_sla(request: SLADefinitionCreate) -> SLADefinition:
    """Create a new SLA definition."""
    service = get_performance_benchmark_service()
    return service.create_sla(
        category=request.category,
        operation_name=request.operation_name,
        tier=request.tier,
        target_p50_ms=request.target_p50_ms,
        target_p95_ms=request.target_p95_ms,
        target_p99_ms=request.target_p99_ms,
        target_throughput_rps=request.target_throughput_rps,
        measurement_window_hours=request.measurement_window_hours,
        breach_threshold_pct=request.breach_threshold_pct,
    )


@router.get(
    "/slas",
    response_model=SLAListResponse,
    summary="List SLA definitions",
    description="List all SLA definitions, optionally filtered by category.",
)
async def list_slas(
    category: BenchmarkCategory | None = Query(None, description="Filter by category"),
) -> SLAListResponse:
    """List SLA definitions."""
    service = get_performance_benchmark_service()
    slas = service.list_slas(category=category)
    return SLAListResponse(total=len(slas), slas=slas)


@router.get(
    "/slas/{sla_id}",
    response_model=SLADefinition,
    summary="Get SLA definition",
    description="Get a specific SLA definition by ID.",
)
async def get_sla(sla_id: str) -> SLADefinition:
    """Get a single SLA definition."""
    service = get_performance_benchmark_service()
    sla = service.get_sla(sla_id)
    if sla is None:
        raise HTTPException(status_code=404, detail=f"SLA '{sla_id}' not found")
    return sla


@router.put(
    "/slas/{sla_id}",
    response_model=SLADefinition,
    summary="Update SLA definition",
    description="Update an existing SLA definition.",
)
async def update_sla(sla_id: str, request: SLADefinitionUpdate) -> SLADefinition:
    """Update an SLA definition."""
    service = get_performance_benchmark_service()
    updated = service.update_sla(sla_id, request.model_dump(exclude_none=True))
    if updated is None:
        raise HTTPException(status_code=404, detail=f"SLA '{sla_id}' not found")
    return updated


@router.delete(
    "/slas/{sla_id}",
    summary="Delete SLA definition",
    description="Delete an SLA definition.",
)
async def delete_sla(sla_id: str) -> dict[str, str]:
    """Delete an SLA definition."""
    service = get_performance_benchmark_service()
    deleted = service.delete_sla(sla_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"SLA '{sla_id}' not found")
    return {"status": "deleted", "sla_id": sla_id}


# ============================================================================
# SLA Compliance
# ============================================================================


@router.get(
    "/slas/{sla_id}/compliance",
    response_model=SLAStatus,
    summary="Check SLA compliance",
    description="Check current compliance status for a specific SLA.",
)
async def check_sla_compliance(sla_id: str) -> SLAStatus:
    """Check compliance for a single SLA."""
    service = get_performance_benchmark_service()
    status = service.check_sla_compliance(sla_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"SLA '{sla_id}' not found")
    return status


@router.get(
    "/compliance",
    response_model=SLAComplianceSummary,
    summary="Check all SLA compliance",
    description="Batch check compliance for all SLA definitions.",
)
async def check_all_compliance() -> SLAComplianceSummary:
    """Batch compliance check for all SLAs."""
    service = get_performance_benchmark_service()
    return service.check_all_sla_compliance()


# ============================================================================
# Trend analysis & regression detection
# ============================================================================


@router.get(
    "/trends",
    response_model=PerformanceTrend,
    summary="Get performance trends",
    description="Analyze performance trends for a specific operation over time.",
)
async def get_trends(
    category: BenchmarkCategory = Query(..., description="Benchmark category"),
    operation: str = Query(..., description="Operation name"),
    days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
) -> PerformanceTrend:
    """Get performance trend analysis."""
    service = get_performance_benchmark_service()
    return service.get_performance_trends(category, operation, days)


@router.get(
    "/regressions",
    response_model=RegressionReport,
    summary="Detect regressions",
    description="Scan all operations for performance regressions (p99 increase >20%).",
)
async def detect_regressions() -> RegressionReport:
    """Detect performance regressions across all operations."""
    service = get_performance_benchmark_service()
    return service.detect_regressions()


# ============================================================================
# Benchmark suites
# ============================================================================


@router.post(
    "/suites",
    response_model=BenchmarkSuite,
    summary="Create benchmark suite",
    description="Create a new benchmark suite grouping multiple benchmarks.",
)
async def create_suite(request: BenchmarkSuiteCreate) -> BenchmarkSuite:
    """Create a new benchmark suite."""
    service = get_performance_benchmark_service()
    benchmarks = [b.model_dump() for b in request.benchmarks]
    return service.create_suite(
        name=request.name,
        description=request.description,
        benchmarks=benchmarks,
        schedule_cron=request.schedule_cron,
    )


@router.get(
    "/suites",
    response_model=BenchmarkSuiteListResponse,
    summary="List benchmark suites",
    description="List all benchmark suites.",
)
async def list_suites() -> BenchmarkSuiteListResponse:
    """List all benchmark suites."""
    service = get_performance_benchmark_service()
    suites = service.list_suites()
    return BenchmarkSuiteListResponse(total=len(suites), suites=suites)


@router.get(
    "/suites/{suite_id}",
    response_model=BenchmarkSuite,
    summary="Get benchmark suite",
    description="Get a specific benchmark suite by ID.",
)
async def get_suite(suite_id: str) -> BenchmarkSuite:
    """Get a benchmark suite."""
    service = get_performance_benchmark_service()
    suite = service.get_suite(suite_id)
    if suite is None:
        raise HTTPException(status_code=404, detail=f"Suite '{suite_id}' not found")
    return suite


@router.post(
    "/suites/{suite_id}/run",
    response_model=BenchmarkSuiteRunResult,
    summary="Run benchmark suite",
    description="Execute a benchmark suite, generating results for each entry.",
)
async def run_suite(suite_id: str) -> BenchmarkSuiteRunResult:
    """Run a benchmark suite."""
    service = get_performance_benchmark_service()
    result = service.run_suite(suite_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Suite '{suite_id}' not found")
    return result


# ============================================================================
# Version comparison
# ============================================================================


@router.get(
    "/compare",
    response_model=VersionComparison,
    summary="Compare versions",
    description="Compare performance metrics between two application versions.",
)
async def compare_versions(
    version_a: str = Query(..., description="First version (baseline)"),
    version_b: str = Query(..., description="Second version (candidate)"),
) -> VersionComparison:
    """Compare performance between two versions."""
    service = get_performance_benchmark_service()
    return service.compare_versions(version_a, version_b)


# ============================================================================
# Aggregate metrics
# ============================================================================


@router.get(
    "/metrics",
    response_model=PerformanceMetrics,
    summary="Get performance metrics",
    description="Get aggregate performance metrics across all operations and SLAs.",
)
async def get_metrics() -> PerformanceMetrics:
    """Get program-wide performance metrics."""
    service = get_performance_benchmark_service()
    return service.get_metrics()
