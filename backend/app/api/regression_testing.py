"""API endpoints for Regression Test Orchestration.

QA-4: 22+ endpoints for test case management, suite orchestration,
run triggering, coverage, flaky test detection, trend analysis,
impact analysis, and test health dashboards.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas.regression_testing import (
    CoverageListResponse,
    EstimatedRunTime,
    FlakyTestListResponse,
    FlakyTestReport,
    ImpactAnalysisRequest,
    ImpactAnalysisResponse,
    PrioritizedTestList,
    TestCase,
    TestCaseCreate,
    TestCaseListResponse,
    TestCaseResult,
    TestCaseUpdate,
    TestCoverage,
    TestHealthDashboard,
    TestPriority,
    TestRun,
    TestRunListResponse,
    TestRunStatus,
    TestSuite,
    TestSuiteCreate,
    TestSuiteListResponse,
    TestSuiteType,
    TestSuiteUpdate,
    TriageFlakyRequest,
    TrendResponse,
    TriggerTestRunRequest,
)
from app.services.regression_testing_service import get_regression_testing_service

router = APIRouter(prefix="/regression-testing", tags=["Regression Testing"])


# ============================================================================
# Test Case endpoints
# ============================================================================


@router.get("/test-cases", response_model=TestCaseListResponse)
async def list_test_cases(
    suite_type: TestSuiteType | None = Query(default=None),
    priority: TestPriority | None = Query(default=None),
    module: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    automated: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> TestCaseListResponse:
    """List test cases with optional filtering."""
    svc = get_regression_testing_service()
    return svc.list_test_cases(
        suite_type=suite_type,
        priority=priority,
        module=module,
        tag=tag,
        automated=automated,
        limit=limit,
        offset=offset,
    )


@router.get("/test-cases/{test_case_id}", response_model=TestCase)
async def get_test_case(test_case_id: str) -> TestCase:
    """Get a single test case by ID."""
    svc = get_regression_testing_service()
    tc = svc.get_test_case(test_case_id)
    if not tc:
        raise HTTPException(status_code=404, detail=f"Test case {test_case_id} not found")
    return tc


@router.post("/test-cases", response_model=TestCase, status_code=201)
async def create_test_case(payload: TestCaseCreate) -> TestCase:
    """Create a new test case."""
    svc = get_regression_testing_service()
    return svc.create_test_case(payload)


@router.patch("/test-cases/{test_case_id}", response_model=TestCase)
async def update_test_case(test_case_id: str, payload: TestCaseUpdate) -> TestCase:
    """Update an existing test case."""
    svc = get_regression_testing_service()
    tc = svc.update_test_case(test_case_id, payload)
    if not tc:
        raise HTTPException(status_code=404, detail=f"Test case {test_case_id} not found")
    return tc


@router.delete("/test-cases/{test_case_id}", status_code=204)
async def delete_test_case(test_case_id: str) -> None:
    """Delete a test case."""
    svc = get_regression_testing_service()
    if not svc.delete_test_case(test_case_id):
        raise HTTPException(status_code=404, detail=f"Test case {test_case_id} not found")


# ============================================================================
# Test Suite endpoints
# ============================================================================


@router.get("/test-suites", response_model=TestSuiteListResponse)
async def list_test_suites(
    suite_type: TestSuiteType | None = Query(default=None),
    enabled: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> TestSuiteListResponse:
    """List test suites with optional filtering."""
    svc = get_regression_testing_service()
    return svc.list_test_suites(suite_type=suite_type, enabled=enabled, limit=limit, offset=offset)


@router.get("/test-suites/{suite_id}", response_model=TestSuite)
async def get_test_suite(suite_id: str) -> TestSuite:
    """Get a single test suite by ID."""
    svc = get_regression_testing_service()
    suite = svc.get_test_suite(suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail=f"Test suite {suite_id} not found")
    return suite


@router.post("/test-suites", response_model=TestSuite, status_code=201)
async def create_test_suite(payload: TestSuiteCreate) -> TestSuite:
    """Create a new test suite."""
    svc = get_regression_testing_service()
    return svc.create_test_suite(payload)


@router.patch("/test-suites/{suite_id}", response_model=TestSuite)
async def update_test_suite(suite_id: str, payload: TestSuiteUpdate) -> TestSuite:
    """Update an existing test suite."""
    svc = get_regression_testing_service()
    suite = svc.update_test_suite(suite_id, payload)
    if not suite:
        raise HTTPException(status_code=404, detail=f"Test suite {suite_id} not found")
    return suite


@router.delete("/test-suites/{suite_id}", status_code=204)
async def delete_test_suite(suite_id: str) -> None:
    """Delete a test suite."""
    svc = get_regression_testing_service()
    if not svc.delete_test_suite(suite_id):
        raise HTTPException(status_code=404, detail=f"Test suite {suite_id} not found")


@router.post("/test-suites/{suite_id}/enable", response_model=TestSuite)
async def enable_test_suite(suite_id: str) -> TestSuite:
    """Enable a disabled test suite."""
    svc = get_regression_testing_service()
    suite = svc.enable_suite(suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail=f"Test suite {suite_id} not found")
    return suite


@router.post("/test-suites/{suite_id}/disable", response_model=TestSuite)
async def disable_test_suite(suite_id: str) -> TestSuite:
    """Disable a test suite."""
    svc = get_regression_testing_service()
    suite = svc.disable_suite(suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail=f"Test suite {suite_id} not found")
    return suite


# ============================================================================
# Test Run endpoints
# ============================================================================


@router.post("/runs/trigger", response_model=TestRun, status_code=201)
async def trigger_test_run(payload: TriggerTestRunRequest) -> TestRun:
    """Trigger a new test run for a suite (simulated execution)."""
    svc = get_regression_testing_service()
    run = svc.trigger_test_run(payload)
    if not run:
        raise HTTPException(status_code=404, detail=f"Suite {payload.suite_id} not found")
    return run


@router.get("/runs", response_model=TestRunListResponse)
async def list_test_runs(
    suite_id: str | None = Query(default=None),
    status: TestRunStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> TestRunListResponse:
    """List test runs with optional filtering."""
    svc = get_regression_testing_service()
    return svc.list_test_runs(suite_id=suite_id, status=status, limit=limit, offset=offset)


@router.get("/runs/{run_id}", response_model=TestRun)
async def get_test_run(run_id: str) -> TestRun:
    """Get a single test run by ID."""
    svc = get_regression_testing_service()
    run = svc.get_test_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Test run {run_id} not found")
    return run


@router.get("/runs/{run_id}/results", response_model=list[TestCaseResult])
async def get_run_results(run_id: str) -> list[TestCaseResult]:
    """Get individual test case results for a run."""
    svc = get_regression_testing_service()
    run = svc.get_test_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Test run {run_id} not found")
    return svc.get_run_results(run_id)


# ============================================================================
# Coverage endpoints
# ============================================================================


@router.get("/coverage", response_model=CoverageListResponse)
async def list_coverage() -> CoverageListResponse:
    """Get code coverage for all modules."""
    svc = get_regression_testing_service()
    return svc.list_coverage()


@router.get("/coverage/{module}", response_model=TestCoverage)
async def get_module_coverage(module: str) -> TestCoverage:
    """Get code coverage for a specific module."""
    svc = get_regression_testing_service()
    cov = svc.get_module_coverage(module)
    if not cov:
        raise HTTPException(status_code=404, detail=f"Coverage for module {module} not found")
    return cov


# ============================================================================
# Flaky Test endpoints
# ============================================================================


@router.get("/flaky-tests", response_model=FlakyTestListResponse)
async def list_flaky_tests(
    triaged: bool | None = Query(default=None),
) -> FlakyTestListResponse:
    """List flaky test reports."""
    svc = get_regression_testing_service()
    return svc.list_flaky_tests(triaged=triaged)


@router.get("/flaky-tests/{test_case_id}", response_model=FlakyTestReport)
async def get_flaky_report(test_case_id: str) -> FlakyTestReport:
    """Get flaky test report for a specific test case."""
    svc = get_regression_testing_service()
    report = svc.get_flaky_report(test_case_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Flaky report for {test_case_id} not found")
    return report


@router.post("/flaky-tests/{test_case_id}/triage", response_model=FlakyTestReport)
async def triage_flaky_test(test_case_id: str, payload: TriageFlakyRequest) -> FlakyTestReport:
    """Triage a flaky test (set root cause and mark as triaged)."""
    svc = get_regression_testing_service()
    report = svc.triage_flaky_test(test_case_id, payload.root_cause_category, payload.triaged)
    if not report:
        raise HTTPException(status_code=404, detail=f"Flaky report for {test_case_id} not found")
    return report


# ============================================================================
# Trends endpoint
# ============================================================================


@router.get("/trends", response_model=TrendResponse)
async def get_regression_trends(
    days: int = Query(default=14, ge=1, le=90),
) -> TrendResponse:
    """Get regression trend data over time."""
    svc = get_regression_testing_service()
    return svc.get_regression_trends(days=days)


# ============================================================================
# Dashboard endpoint
# ============================================================================


@router.get("/dashboard", response_model=TestHealthDashboard)
async def get_test_health_dashboard() -> TestHealthDashboard:
    """Get the aggregate test health dashboard."""
    svc = get_regression_testing_service()
    return svc.get_test_health_dashboard()


# ============================================================================
# Impact Analysis endpoint
# ============================================================================


@router.post("/impact-analysis", response_model=ImpactAnalysisResponse)
async def analyze_impact(payload: ImpactAnalysisRequest) -> ImpactAnalysisResponse:
    """Determine which tests should run based on changed modules."""
    svc = get_regression_testing_service()
    return svc.analyze_impact(payload)


# ============================================================================
# Estimated Run Time endpoint
# ============================================================================


@router.get("/suites/{suite_id}/estimated-time", response_model=EstimatedRunTime)
async def get_estimated_run_time(suite_id: str) -> EstimatedRunTime:
    """Get estimated run time for a suite."""
    svc = get_regression_testing_service()
    est = svc.estimate_run_time(suite_id)
    if not est:
        raise HTTPException(status_code=404, detail=f"Suite {suite_id} not found")
    return est


# ============================================================================
# Prioritization endpoint
# ============================================================================


@router.get("/prioritized-tests", response_model=PrioritizedTestList)
async def get_prioritized_tests(
    suite_type: TestSuiteType | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> PrioritizedTestList:
    """Get tests ordered by execution priority (P0 first, then by flaky rate)."""
    svc = get_regression_testing_service()
    return svc.get_prioritized_tests(suite_type=suite_type, limit=limit)
