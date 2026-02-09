"""Pydantic schemas for Deployment Verification & API Contract Testing.

VPE-9: Deployment verification with smoke tests, health checks, schema
validation, performance checks, data integrity verification, and rollback
readiness.  API contract testing with schema diffing, backward compatibility
analysis, and breaking-change detection.  Error budgets with SLI definitions,
burn-rate calculation, and deployment gate evaluation.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class VerificationType(str, Enum):
    """Type of deployment verification check."""

    SMOKE_TEST = "SMOKE_TEST"
    HEALTH_CHECK = "HEALTH_CHECK"
    SCHEMA_VALIDATION = "SCHEMA_VALIDATION"
    PERFORMANCE_CHECK = "PERFORMANCE_CHECK"
    DATA_INTEGRITY = "DATA_INTEGRITY"
    ROLLBACK_READINESS = "ROLLBACK_READINESS"


class VerificationStatus(str, Enum):
    """Status of a verification check."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    TIMED_OUT = "TIMED_OUT"


class ContractTestType(str, Enum):
    """Type of API contract test."""

    REQUEST_SCHEMA = "REQUEST_SCHEMA"
    RESPONSE_SCHEMA = "RESPONSE_SCHEMA"
    BACKWARD_COMPATIBILITY = "BACKWARD_COMPATIBILITY"
    BREAKING_CHANGE = "BREAKING_CHANGE"
    DEPRECATION = "DEPRECATION"


class EnvironmentName(str, Enum):
    """Deployment target environment."""

    DEVELOPMENT = "DEVELOPMENT"
    STAGING = "STAGING"
    QA = "QA"
    UAT = "UAT"
    PRODUCTION = "PRODUCTION"


class ErrorBudgetStatus(str, Enum):
    """Error budget health status."""

    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    EXHAUSTED = "EXHAUSTED"


class DeploymentGateResult(str, Enum):
    """Aggregate deployment gate evaluation result."""

    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"


# ---------------------------------------------------------------------------
# Verification Check
# ---------------------------------------------------------------------------


class VerificationCheck(BaseModel):
    """A single verification check within a deployment verification suite."""

    id: str = Field(description="Unique check identifier")
    name: str = Field(description="Human-readable check name")
    verification_type: VerificationType = Field(description="Category of this check")
    description: str | None = Field(default=None, description="Detailed check description")
    expected_result: str | None = Field(default=None, description="Expected outcome")
    actual_result: str | None = Field(default=None, description="Actual observed outcome")
    status: VerificationStatus = Field(description="Check execution status")
    duration_ms: float | None = Field(default=None, description="Execution time in milliseconds")
    error_message: str | None = Field(default=None, description="Error details on failure")
    endpoint_url: str | None = Field(default=None, description="Endpoint URL being verified")
    created_at: datetime = Field(description="When the check was created")


# ---------------------------------------------------------------------------
# Deployment Verification
# ---------------------------------------------------------------------------


class DeploymentVerification(BaseModel):
    """A complete deployment verification run containing multiple checks."""

    id: str = Field(description="Unique verification run identifier")
    deployment_id: str = Field(description="Associated deployment identifier")
    environment: EnvironmentName = Field(description="Target deployment environment")
    version: str = Field(description="Application version being verified")
    checks: list[VerificationCheck] = Field(
        default_factory=list, description="Individual verification checks"
    )
    overall_status: VerificationStatus = Field(description="Aggregate verification status")
    started_at: datetime = Field(description="When the verification started")
    completed_at: datetime | None = Field(default=None, description="When verification finished")
    triggered_by: str = Field(description="Who or what triggered the verification")
    rollback_recommended: bool = Field(
        default=False, description="Whether rollback is recommended based on results"
    )


# ---------------------------------------------------------------------------
# API Contract
# ---------------------------------------------------------------------------


class APIContract(BaseModel):
    """An API contract defining endpoint schema expectations."""

    id: str = Field(description="Unique contract identifier")
    endpoint_path: str = Field(description="API endpoint path (e.g. /api/v1/patients)")
    method: str = Field(description="HTTP method (GET, POST, PUT, DELETE)")
    version: str = Field(description="API version for this contract")
    request_schema: dict | None = Field(default=None, description="Expected request JSON schema")
    response_schema: dict | None = Field(default=None, description="Expected response JSON schema")
    required_headers: list[str] = Field(
        default_factory=list, description="Required HTTP headers"
    )
    deprecated: bool = Field(default=False, description="Whether this endpoint is deprecated")
    deprecated_date: datetime | None = Field(
        default=None, description="Date endpoint was deprecated"
    )
    replacement_endpoint: str | None = Field(
        default=None, description="Replacement endpoint if deprecated"
    )
    created_at: datetime = Field(description="When the contract was created")
    updated_at: datetime = Field(description="When the contract was last updated")


# ---------------------------------------------------------------------------
# Breaking Change
# ---------------------------------------------------------------------------


class BreakingChange(BaseModel):
    """A detected breaking change in an API contract."""

    field_path: str = Field(description="JSON path of the changed field")
    change_type: str = Field(description="Type of change (removed, type_changed, required_added)")
    old_value: str | None = Field(default=None, description="Previous value or type")
    new_value: str | None = Field(default=None, description="New value or type")
    severity: str = Field(description="Severity: HIGH, MEDIUM, LOW")


# ---------------------------------------------------------------------------
# Contract Test Result
# ---------------------------------------------------------------------------


class ContractTestResult(BaseModel):
    """Result of testing an API contract."""

    id: str = Field(description="Unique test result identifier")
    contract_id: str = Field(description="Associated contract identifier")
    test_type: ContractTestType = Field(description="Type of contract test performed")
    status: VerificationStatus = Field(description="Test result status")
    details: str | None = Field(default=None, description="Detailed test outcome")
    breaking_changes: list[BreakingChange] = Field(
        default_factory=list, description="Detected breaking changes"
    )
    created_at: datetime = Field(description="When the test was run")


# ---------------------------------------------------------------------------
# Error Budget Violation
# ---------------------------------------------------------------------------


class ErrorBudgetViolation(BaseModel):
    """A recorded violation of an error budget."""

    timestamp: datetime = Field(description="When the violation occurred")
    duration_minutes: float = Field(description="Duration of the violation in minutes")
    error_rate_percent: float = Field(description="Error rate during violation")
    cause: str = Field(description="Root cause or description of the violation")


# ---------------------------------------------------------------------------
# Error Budget
# ---------------------------------------------------------------------------


class ErrorBudget(BaseModel):
    """Error budget tracking for a service SLI."""

    id: str = Field(description="Unique error budget identifier")
    service_name: str = Field(description="Service being monitored")
    sli_name: str = Field(description="Service level indicator name")
    target_percent: float = Field(description="SLO target percentage (e.g. 99.9)")
    current_percent: float = Field(description="Current measured percentage")
    remaining_budget_percent: float = Field(
        description="Remaining error budget as a percentage"
    )
    status: ErrorBudgetStatus = Field(description="Current error budget health status")
    burn_rate_per_hour: float = Field(
        description="Rate at which budget is being consumed per hour"
    )
    time_to_exhaustion_hours: float | None = Field(
        default=None, description="Estimated hours until budget exhaustion"
    )
    window_start: datetime = Field(description="Start of the measurement window")
    window_end: datetime = Field(description="End of the measurement window")
    violations: list[ErrorBudgetViolation] = Field(
        default_factory=list, description="Budget violations within the window"
    )


# ---------------------------------------------------------------------------
# SLI Definition
# ---------------------------------------------------------------------------


class SLIDefinition(BaseModel):
    """A service level indicator definition."""

    id: str = Field(description="Unique SLI identifier")
    service_name: str = Field(description="Service this SLI monitors")
    sli_name: str = Field(description="SLI name (e.g. availability, latency_p99)")
    description: str | None = Field(default=None, description="Human-readable description")
    target_percent: float = Field(description="Target percentage for this SLI")
    measurement_query: str | None = Field(
        default=None, description="Query or expression used to measure the SLI"
    )
    window_hours: int = Field(default=720, description="Measurement window in hours (default 30d)")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class DeploymentVerificationCreate(BaseModel):
    """Request to create a new deployment verification."""

    deployment_id: str = Field(description="Deployment to verify")
    environment: EnvironmentName = Field(description="Target environment")
    version: str = Field(description="Application version")
    triggered_by: str = Field(default="system", description="Who triggered the verification")


class RunSmokeTestRequest(BaseModel):
    """Request to run smoke tests against a deployment."""

    deployment_id: str = Field(description="Deployment to test")
    environment: EnvironmentName = Field(description="Target environment")
    version: str = Field(description="Application version")
    endpoints: list[str] | None = Field(
        default=None, description="Specific endpoints to test (None = all)"
    )
    triggered_by: str = Field(default="system", description="Who triggered the tests")


class APIContractCreate(BaseModel):
    """Request to create a new API contract."""

    endpoint_path: str = Field(description="API endpoint path")
    method: str = Field(description="HTTP method")
    version: str = Field(default="v1", description="API version")
    request_schema: dict | None = Field(default=None, description="Request JSON schema")
    response_schema: dict | None = Field(default=None, description="Response JSON schema")
    required_headers: list[str] = Field(default_factory=list, description="Required headers")


class APIContractUpdate(BaseModel):
    """Request to update an API contract."""

    endpoint_path: str | None = Field(default=None, description="Updated endpoint path")
    method: str | None = Field(default=None, description="Updated HTTP method")
    version: str | None = Field(default=None, description="Updated API version")
    request_schema: dict | None = Field(default=None, description="Updated request schema")
    response_schema: dict | None = Field(default=None, description="Updated response schema")
    required_headers: list[str] | None = Field(default=None, description="Updated headers")
    deprecated: bool | None = Field(default=None, description="Mark as deprecated")
    replacement_endpoint: str | None = Field(default=None, description="Replacement endpoint")


class SLIDefinitionCreate(BaseModel):
    """Request to create a new SLI definition."""

    service_name: str = Field(description="Service name")
    sli_name: str = Field(description="SLI name")
    description: str | None = Field(default=None, description="Description")
    target_percent: float = Field(description="Target percentage")
    measurement_query: str | None = Field(default=None, description="Measurement query")
    window_hours: int = Field(default=720, description="Measurement window in hours")


class ErrorBudgetCreate(BaseModel):
    """Request to create a new error budget."""

    service_name: str = Field(description="Service name")
    sli_name: str = Field(description="SLI name being budgeted")
    target_percent: float = Field(description="SLO target percentage")
    window_hours: int = Field(default=720, description="Budget window in hours")


class DeploymentGateEvaluation(BaseModel):
    """Result of evaluating all deployment gates."""

    result: DeploymentGateResult = Field(description="Aggregate gate result")
    verification_status: VerificationStatus = Field(description="Latest verification status")
    contract_pass_rate: float = Field(description="Percentage of contract tests passing")
    error_budgets_healthy: bool = Field(description="Whether all error budgets are healthy")
    failing_checks: list[str] = Field(
        default_factory=list, description="Names of failing checks"
    )
    warnings: list[str] = Field(default_factory=list, description="Warning messages")
    evaluated_at: datetime = Field(description="When the evaluation was performed")


class VerificationTrend(BaseModel):
    """Historical verification trending data point."""

    date: str = Field(description="Date string (YYYY-MM-DD)")
    total_verifications: int = Field(description="Total verification runs")
    passed: int = Field(description="Number that passed")
    failed: int = Field(description="Number that failed")
    pass_rate: float = Field(description="Pass rate percentage")


class DeploymentVerificationMetrics(BaseModel):
    """Aggregate metrics for deployment verification."""

    total_verifications: int = Field(description="Total verification runs")
    pass_rate: float = Field(description="Overall pass rate percentage")
    avg_verification_time_ms: float = Field(description="Average verification duration")
    total_contracts: int = Field(description="Total API contracts tracked")
    contract_test_pass_rate: float = Field(description="Contract test pass rate")
    breaking_changes_detected: int = Field(description="Total breaking changes found")
    error_budgets_healthy: int = Field(description="Number of healthy error budgets")
    error_budgets_total: int = Field(description="Total error budgets")
    recent_trends: list[VerificationTrend] = Field(
        default_factory=list, description="Recent verification trends"
    )


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class DeploymentVerificationListResponse(BaseModel):
    """Paginated list of deployment verifications."""

    verifications: list[DeploymentVerification] = Field(default_factory=list)
    total: int = Field(description="Total number of verifications")
    limit: int = Field(description="Page size")
    offset: int = Field(description="Page offset")


class APIContractListResponse(BaseModel):
    """Paginated list of API contracts."""

    contracts: list[APIContract] = Field(default_factory=list)
    total: int = Field(description="Total number of contracts")
    limit: int = Field(description="Page size")
    offset: int = Field(description="Page offset")


class ContractTestResultListResponse(BaseModel):
    """Paginated list of contract test results."""

    results: list[ContractTestResult] = Field(default_factory=list)
    total: int = Field(description="Total number of results")
    limit: int = Field(description="Page size")
    offset: int = Field(description="Page offset")


class ErrorBudgetListResponse(BaseModel):
    """Paginated list of error budgets."""

    budgets: list[ErrorBudget] = Field(default_factory=list)
    total: int = Field(description="Total number of budgets")
    limit: int = Field(description="Page size")
    offset: int = Field(description="Page offset")


class SLIDefinitionListResponse(BaseModel):
    """Paginated list of SLI definitions."""

    definitions: list[SLIDefinition] = Field(default_factory=list)
    total: int = Field(description="Total number of definitions")
    limit: int = Field(description="Page size")
    offset: int = Field(description="Page offset")
