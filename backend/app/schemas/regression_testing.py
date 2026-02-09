"""Pydantic schemas for Regression Test Orchestration.

QA-4: Comprehensive regression test management with test case tracking,
suite orchestration, flaky test detection, coverage analysis, trend
reporting, impact analysis, and test health dashboards.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class TestSuiteType(str, Enum):
    """Classification of test suite purpose."""

    SMOKE = "SMOKE"
    REGRESSION = "REGRESSION"
    INTEGRATION = "INTEGRATION"
    E2E = "E2E"
    PERFORMANCE = "PERFORMANCE"
    SECURITY = "SECURITY"
    COMPLIANCE = "COMPLIANCE"
    ACCESSIBILITY = "ACCESSIBILITY"


class TestStatus(str, Enum):
    """Status of an individual test case execution."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    FLAKY = "FLAKY"
    BLOCKED = "BLOCKED"
    TIMED_OUT = "TIMED_OUT"


class TestPriority(str, Enum):
    """Priority level for test cases."""

    P0_CRITICAL = "P0_CRITICAL"
    P1_HIGH = "P1_HIGH"
    P2_MEDIUM = "P2_MEDIUM"
    P3_LOW = "P3_LOW"


class TriggerType(str, Enum):
    """What event triggers a test run."""

    ON_COMMIT = "ON_COMMIT"
    ON_PR = "ON_PR"
    ON_MERGE = "ON_MERGE"
    SCHEDULED = "SCHEDULED"
    MANUAL = "MANUAL"
    ON_DEPLOY = "ON_DEPLOY"


class TestRunStatus(str, Enum):
    """Status of a full test run (suite execution)."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"


class FlakyRootCause(str, Enum):
    """Root cause category for flaky tests."""

    TIMING = "TIMING"
    RACE_CONDITION = "RACE_CONDITION"
    EXTERNAL_DEPENDENCY = "EXTERNAL_DEPENDENCY"
    DATA_DEPENDENCY = "DATA_DEPENDENCY"
    RESOURCE_CONTENTION = "RESOURCE_CONTENTION"
    ENVIRONMENT = "ENVIRONMENT"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Core Models
# ---------------------------------------------------------------------------


class TestCase(BaseModel):
    """A single test case definition."""

    id: str = Field(..., description="Unique test case identifier")
    name: str = Field(..., description="Human-readable test name")
    description: str = Field(default="", description="What this test validates")
    suite_type: TestSuiteType = Field(..., description="Suite category")
    priority: TestPriority = Field(default=TestPriority.P2_MEDIUM, description="Execution priority")
    module: str = Field(..., description="Module/component under test")
    tags: list[str] = Field(default_factory=list, description="Searchable tags")
    expected_duration_ms: int = Field(default=1000, description="Expected run time in ms")
    flaky_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Historical flaky rate 0-1")
    last_run_status: TestStatus | None = Field(default=None, description="Most recent status")
    last_run_at: datetime | None = Field(default=None, description="Most recent execution time")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    owner: str = Field(default="", description="Team or person responsible")
    automated: bool = Field(default=True, description="Whether the test is automated")
    preconditions: list[str] = Field(default_factory=list, description="Setup requirements")
    steps: list[str] = Field(default_factory=list, description="Execution steps")


class TestSuite(BaseModel):
    """A collection of test cases executed together."""

    id: str = Field(..., description="Unique suite identifier")
    name: str = Field(..., description="Human-readable suite name")
    suite_type: TestSuiteType = Field(..., description="Suite category")
    description: str = Field(default="", description="Suite purpose")
    test_case_ids: list[str] = Field(default_factory=list, description="Ordered test IDs")
    trigger_types: list[TriggerType] = Field(default_factory=list, description="Activation triggers")
    schedule_cron: str | None = Field(default=None, description="Cron expression for scheduled runs")
    estimated_duration_minutes: int = Field(default=10, description="Estimated total run time")
    parallelizable: bool = Field(default=True, description="Can tests run in parallel")
    max_parallel: int = Field(default=4, ge=1, description="Max parallel workers")
    environment_requirements: list[str] = Field(default_factory=list, description="Required env vars/services")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    enabled: bool = Field(default=True, description="Whether suite is active")


class TestCaseResult(BaseModel):
    """Result of a single test case within a test run."""

    test_case_id: str = Field(..., description="Test case that was executed")
    test_case_name: str = Field(default="", description="Name for display")
    status: TestStatus = Field(..., description="Outcome")
    duration_ms: int = Field(default=0, ge=0, description="Actual execution time")
    error_message: str | None = Field(default=None, description="Failure message")
    stack_trace: str | None = Field(default=None, description="Failure stack trace")
    retry_count: int = Field(default=0, ge=0, description="Retries performed")
    screenshots: list[str] = Field(default_factory=list, description="Screenshot URLs")


class TestRun(BaseModel):
    """A full execution of a test suite."""

    id: str = Field(..., description="Unique run identifier")
    suite_id: str = Field(..., description="Suite that was executed")
    suite_name: str = Field(default="", description="Suite name for display")
    status: TestRunStatus = Field(default=TestRunStatus.QUEUED, description="Run status")
    trigger_type: TriggerType = Field(default=TriggerType.MANUAL, description="How it was triggered")
    triggered_by: str = Field(default="system", description="User or system that triggered")
    build_version: str = Field(default="", description="Build/commit being tested")
    environment: str = Field(default="development", description="Target environment")
    started_at: datetime | None = Field(default=None, description="When execution began")
    completed_at: datetime | None = Field(default=None, description="When execution ended")
    duration_seconds: float | None = Field(default=None, description="Total wall-clock time")
    total_tests: int = Field(default=0, ge=0, description="Total tests in run")
    passed: int = Field(default=0, ge=0, description="Passed count")
    failed: int = Field(default=0, ge=0, description="Failed count")
    skipped: int = Field(default=0, ge=0, description="Skipped count")
    flaky: int = Field(default=0, ge=0, description="Flaky count")
    blocked: int = Field(default=0, ge=0, description="Blocked count")
    pass_rate: float = Field(default=0.0, ge=0.0, le=100.0, description="Pass percentage")
    results: list[TestCaseResult] = Field(default_factory=list, description="Per-test results")
    artifacts_url: str | None = Field(default=None, description="Link to build artifacts")


class TestCoverage(BaseModel):
    """Code coverage metrics for a module."""

    module: str = Field(..., description="Module/package name")
    total_lines: int = Field(default=0, ge=0, description="Total source lines")
    covered_lines: int = Field(default=0, ge=0, description="Lines covered by tests")
    coverage_percent: float = Field(default=0.0, ge=0.0, le=100.0, description="Line coverage %")
    branch_coverage_percent: float = Field(default=0.0, ge=0.0, le=100.0, description="Branch coverage %")
    uncovered_functions: list[str] = Field(default_factory=list, description="Functions without coverage")


class FlakyTestReport(BaseModel):
    """Report on a flaky test case."""

    test_case_id: str = Field(..., description="Flaky test identifier")
    test_case_name: str = Field(default="", description="Test name for display")
    flaky_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Flaky rate 0-1")
    total_runs_30d: int = Field(default=0, ge=0, description="Total runs in last 30 days")
    failures_30d: int = Field(default=0, ge=0, description="Failures in last 30 days")
    last_flaky_run: datetime | None = Field(default=None, description="Last flaky occurrence")
    root_cause_category: FlakyRootCause = Field(default=FlakyRootCause.UNKNOWN, description="Root cause")
    triaged: bool = Field(default=False, description="Whether root cause has been investigated")


class RegressionTrend(BaseModel):
    """Daily regression trend data point."""

    date: str = Field(..., description="Date in YYYY-MM-DD format")
    total_tests: int = Field(default=0, ge=0)
    pass_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    avg_duration_seconds: float = Field(default=0.0, ge=0.0)
    new_failures: int = Field(default=0, ge=0)
    resolved_failures: int = Field(default=0, ge=0)


# ---------------------------------------------------------------------------
# Aggregate / Dashboard Models
# ---------------------------------------------------------------------------


class TestMetrics(BaseModel):
    """Aggregate test execution metrics."""

    total_test_cases: int = Field(default=0, ge=0)
    total_automated: int = Field(default=0, ge=0)
    total_manual: int = Field(default=0, ge=0)
    automation_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    overall_pass_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    avg_duration_seconds: float = Field(default=0.0, ge=0.0)
    total_runs_30d: int = Field(default=0, ge=0)
    flaky_test_count: int = Field(default=0, ge=0)
    avg_flaky_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    p0_pass_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    p1_pass_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    coverage_by_module: list[TestCoverage] = Field(default_factory=list)


class TestHealthDashboard(BaseModel):
    """Top-level dashboard aggregating test health."""

    metrics: TestMetrics = Field(default_factory=TestMetrics)
    recent_runs: list[TestRun] = Field(default_factory=list)
    flaky_reports: list[FlakyTestReport] = Field(default_factory=list)
    trends: list[RegressionTrend] = Field(default_factory=list)
    suites_enabled: int = Field(default=0, ge=0)
    suites_disabled: int = Field(default=0, ge=0)
    next_scheduled_run: datetime | None = Field(default=None)
    health_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Overall 0-100 score")


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------


class TestCaseCreate(BaseModel):
    """Payload to create a test case."""

    name: str = Field(..., min_length=1, max_length=300)
    description: str = Field(default="")
    suite_type: TestSuiteType = Field(...)
    priority: TestPriority = Field(default=TestPriority.P2_MEDIUM)
    module: str = Field(..., min_length=1, max_length=200)
    tags: list[str] = Field(default_factory=list)
    expected_duration_ms: int = Field(default=1000, ge=1)
    owner: str = Field(default="")
    automated: bool = Field(default=True)
    preconditions: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)


class TestCaseUpdate(BaseModel):
    """Payload to update a test case."""

    name: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None)
    suite_type: TestSuiteType | None = Field(default=None)
    priority: TestPriority | None = Field(default=None)
    module: str | None = Field(default=None, min_length=1, max_length=200)
    tags: list[str] | None = Field(default=None)
    expected_duration_ms: int | None = Field(default=None, ge=1)
    owner: str | None = Field(default=None)
    automated: bool | None = Field(default=None)
    preconditions: list[str] | None = Field(default=None)
    steps: list[str] | None = Field(default=None)


class TestCaseListResponse(BaseModel):
    """Paginated list of test cases."""

    items: list[TestCase] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)
    limit: int = Field(default=50)
    offset: int = Field(default=0)


class TestSuiteCreate(BaseModel):
    """Payload to create a test suite."""

    name: str = Field(..., min_length=1, max_length=300)
    suite_type: TestSuiteType = Field(...)
    description: str = Field(default="")
    test_case_ids: list[str] = Field(default_factory=list)
    trigger_types: list[TriggerType] = Field(default_factory=list)
    schedule_cron: str | None = Field(default=None)
    estimated_duration_minutes: int = Field(default=10, ge=1)
    parallelizable: bool = Field(default=True)
    max_parallel: int = Field(default=4, ge=1)
    environment_requirements: list[str] = Field(default_factory=list)
    enabled: bool = Field(default=True)


class TestSuiteUpdate(BaseModel):
    """Payload to update a test suite."""

    name: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None)
    test_case_ids: list[str] | None = Field(default=None)
    trigger_types: list[TriggerType] | None = Field(default=None)
    schedule_cron: str | None = Field(default=None)
    estimated_duration_minutes: int | None = Field(default=None, ge=1)
    parallelizable: bool | None = Field(default=None)
    max_parallel: int | None = Field(default=None, ge=1)
    environment_requirements: list[str] | None = Field(default=None)
    enabled: bool | None = Field(default=None)


class TestSuiteListResponse(BaseModel):
    """Paginated list of test suites."""

    items: list[TestSuite] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)
    limit: int = Field(default=50)
    offset: int = Field(default=0)


class TriggerTestRunRequest(BaseModel):
    """Request to trigger a test run for a suite."""

    suite_id: str = Field(..., min_length=1)
    trigger_type: TriggerType = Field(default=TriggerType.MANUAL)
    triggered_by: str = Field(default="system")
    build_version: str = Field(default="latest")
    environment: str = Field(default="development")


class TestRunListResponse(BaseModel):
    """Paginated list of test runs."""

    items: list[TestRun] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)
    limit: int = Field(default=50)
    offset: int = Field(default=0)


class CoverageListResponse(BaseModel):
    """Coverage data for all modules."""

    items: list[TestCoverage] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)
    overall_coverage: float = Field(default=0.0, ge=0.0, le=100.0)


class FlakyTestListResponse(BaseModel):
    """List of flaky test reports."""

    items: list[FlakyTestReport] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)


class TriageFlakyRequest(BaseModel):
    """Request to triage a flaky test."""

    root_cause_category: FlakyRootCause = Field(...)
    triaged: bool = Field(default=True)


class TrendResponse(BaseModel):
    """Regression trend over time."""

    items: list[RegressionTrend] = Field(default_factory=list)
    total_days: int = Field(default=0, ge=0)


class ImpactAnalysisRequest(BaseModel):
    """Request to analyze which tests should run for changed modules."""

    changed_modules: list[str] = Field(..., min_length=1)
    include_dependent: bool = Field(default=True, description="Include transitive dependencies")


class ImpactAnalysisResponse(BaseModel):
    """Result of test impact analysis."""

    changed_modules: list[str] = Field(default_factory=list)
    affected_test_ids: list[str] = Field(default_factory=list)
    affected_test_count: int = Field(default=0, ge=0)
    estimated_duration_minutes: float = Field(default=0.0, ge=0.0)
    recommended_suite_type: TestSuiteType = Field(default=TestSuiteType.REGRESSION)


class PrioritizedTestList(BaseModel):
    """Tests ordered by execution priority."""

    items: list[TestCase] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)
    estimated_duration_minutes: float = Field(default=0.0, ge=0.0)


class EstimatedRunTime(BaseModel):
    """Estimated time to run a suite or set of tests."""

    suite_id: str | None = Field(default=None)
    test_count: int = Field(default=0, ge=0)
    sequential_minutes: float = Field(default=0.0, ge=0.0)
    parallel_minutes: float = Field(default=0.0, ge=0.0)
    max_parallel: int = Field(default=4, ge=1)
