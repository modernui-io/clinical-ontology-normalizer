"""Data Consistency API endpoints.

Provides endpoints for running OMOP CDM data consistency checks:
- Referential integrity validation
- Temporal plausibility checks
- Cross-table consistency
- Orphan record detection
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.data_consistency_service import (
    CheckStatus,
    CheckType,
    Severity,
    get_data_consistency_service,
)

router = APIRouter(prefix="/data-consistency", tags=["Data Quality"])


# ============================================================================
# Request/Response Models
# ============================================================================


class ConsistencyIssueResponse(BaseModel):
    """A single consistency issue found."""

    issue_id: str = Field(..., description="Issue ID")
    check_type: str = Field(..., description="Type of check that found the issue")
    severity: str = Field(..., description="Issue severity")
    table: str = Field(..., description="Table where issue was found")
    field: str | None = Field(None, description="Field with the issue")
    record_id: str | None = Field(None, description="Record ID with the issue")
    description: str = Field(..., description="Issue description")
    current_value: str | None = Field(None, description="Current value")
    expected_value: str | None = Field(None, description="Expected value")


class CheckResultResponse(BaseModel):
    """Result of a single consistency check."""

    check_id: str = Field(..., description="Check ID")
    check_name: str = Field(..., description="Check name")
    check_type: str = Field(..., description="Check type")
    status: str = Field(..., description="Check status")
    records_checked: int = Field(..., description="Records checked")
    issues_found: int = Field(..., description="Issues found")
    issues: list[ConsistencyIssueResponse] = Field(..., description="List of issues")


class ConsistencyReportResponse(BaseModel):
    """Full consistency validation report."""

    id: str = Field(..., description="Report ID")
    timestamp: float = Field(..., description="Report timestamp")
    total_checks: int = Field(..., description="Total checks run")
    checks_passed: int = Field(..., description="Checks passed")
    checks_failed: int = Field(..., description="Checks failed")
    checks_warning: int = Field(..., description="Checks with warnings")
    total_issues: int = Field(..., description="Total issues found")
    critical_issues: int = Field(..., description="Critical severity issues")
    high_issues: int = Field(..., description="High severity issues")
    medium_issues: int = Field(..., description="Medium severity issues")
    low_issues: int = Field(..., description="Low severity issues")
    results: list[CheckResultResponse] = Field(..., description="Check results")


class CheckTypesResponse(BaseModel):
    """Available check types."""

    check_types: list[dict[str, str]] = Field(..., description="Available check types")


class SeveritiesResponse(BaseModel):
    """Available severity levels."""

    severities: list[dict[str, str]] = Field(..., description="Available severity levels")


class StatusesResponse(BaseModel):
    """Available check statuses."""

    statuses: list[dict[str, str]] = Field(..., description="Available check statuses")


class SummaryResponse(BaseModel):
    """Summary of last consistency check."""

    has_results: bool = Field(..., description="Whether results exist")
    report_id: str | None = Field(None, description="Report ID")
    timestamp: float | None = Field(None, description="Report timestamp")
    total_checks: int = Field(0, description="Total checks")
    checks_passed: int = Field(0, description="Checks passed")
    checks_failed: int = Field(0, description="Checks failed")
    total_issues: int = Field(0, description="Total issues")
    critical_issues: int = Field(0, description="Critical issues")


# ============================================================================
# Helper Functions
# ============================================================================


def _issue_to_response(issue) -> ConsistencyIssueResponse:
    """Convert ConsistencyIssue to response model."""
    return ConsistencyIssueResponse(
        issue_id=issue.issue_id,
        check_type=issue.check_type.value,
        severity=issue.severity.value,
        table=issue.table,
        field=issue.field,
        record_id=issue.record_id,
        description=issue.description,
        current_value=issue.current_value,
        expected_value=issue.expected_value,
    )


def _check_result_to_response(result) -> CheckResultResponse:
    """Convert ConsistencyCheckResult to response model."""
    return CheckResultResponse(
        check_id=result.check_id,
        check_name=result.check_name,
        check_type=result.check_type.value,
        status=result.status.value,
        records_checked=result.records_checked,
        issues_found=result.issues_found,
        issues=[_issue_to_response(i) for i in result.issues],
    )


def _report_to_response(report) -> ConsistencyReportResponse:
    """Convert ConsistencyReport to response model."""
    return ConsistencyReportResponse(
        id=report.id,
        timestamp=report.timestamp,
        total_checks=report.total_checks,
        checks_passed=report.checks_passed,
        checks_failed=report.checks_failed,
        checks_warning=report.checks_warning,
        total_issues=report.total_issues,
        critical_issues=report.critical_issues,
        high_issues=report.high_issues,
        medium_issues=report.medium_issues,
        low_issues=report.low_issues,
        results=[_check_result_to_response(r) for r in report.results],
    )


# ============================================================================
# Endpoints - Static routes first
# ============================================================================


@router.post(
    "/run",
    response_model=ConsistencyReportResponse,
    summary="Run consistency checks",
    description="Run all data consistency checks and return results.",
)
async def run_checks() -> ConsistencyReportResponse:
    """Run all consistency checks."""
    service = get_data_consistency_service()
    report = service.run_checks()
    return _report_to_response(report)


@router.get(
    "/results",
    response_model=ConsistencyReportResponse | None,
    summary="Get last results",
    description="Get results from the last consistency check run.",
)
async def get_results() -> ConsistencyReportResponse | None:
    """Get last consistency check results."""
    service = get_data_consistency_service()
    report = service.get_results()

    if not report:
        raise HTTPException(
            status_code=404,
            detail="No consistency check results available. Run /run first.",
        )

    return _report_to_response(report)


@router.get(
    "/summary",
    response_model=SummaryResponse,
    summary="Get results summary",
    description="Get a summary of the last consistency check.",
)
async def get_summary() -> SummaryResponse:
    """Get summary of last consistency check."""
    service = get_data_consistency_service()
    report = service.get_results()

    if not report:
        return SummaryResponse(has_results=False)

    return SummaryResponse(
        has_results=True,
        report_id=report.id,
        timestamp=report.timestamp,
        total_checks=report.total_checks,
        checks_passed=report.checks_passed,
        checks_failed=report.checks_failed,
        total_issues=report.total_issues,
        critical_issues=report.critical_issues,
    )


@router.get(
    "/check-types",
    response_model=CheckTypesResponse,
    summary="List check types",
    description="Get available consistency check types.",
)
async def list_check_types() -> CheckTypesResponse:
    """List available check types."""
    check_types = [
        {"value": ct.value, "name": ct.name.replace("_", " ").title()}
        for ct in CheckType
    ]
    return CheckTypesResponse(check_types=check_types)


@router.get(
    "/severities",
    response_model=SeveritiesResponse,
    summary="List severities",
    description="Get available issue severity levels.",
)
async def list_severities() -> SeveritiesResponse:
    """List available severity levels."""
    severities = [
        {"value": s.value, "name": s.name.replace("_", " ").title()}
        for s in Severity
    ]
    return SeveritiesResponse(severities=severities)


@router.get(
    "/statuses",
    response_model=StatusesResponse,
    summary="List statuses",
    description="Get available check statuses.",
)
async def list_statuses() -> StatusesResponse:
    """List available check statuses."""
    statuses = [
        {"value": s.value, "name": s.name.replace("_", " ").title()}
        for s in CheckStatus
    ]
    return StatusesResponse(statuses=statuses)


# ============================================================================
# Endpoints - Parameterized routes (filtered results)
# ============================================================================


@router.get(
    "/issues",
    response_model=list[ConsistencyIssueResponse],
    summary="Get filtered issues",
    description="Get issues from the last check run with optional filters.",
)
async def get_issues(
    severity: str | None = Query(None, description="Filter by severity"),
    check_type: str | None = Query(None, description="Filter by check type"),
    table: str | None = Query(None, description="Filter by table"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum issues to return"),
) -> list[ConsistencyIssueResponse]:
    """Get filtered issues from last check run."""
    service = get_data_consistency_service()
    report = service.get_results()

    if not report:
        return []

    # Collect all issues
    all_issues = []
    for result in report.results:
        all_issues.extend(result.issues)

    # Apply filters
    if severity:
        try:
            sev_enum = Severity(severity)
            all_issues = [i for i in all_issues if i.severity == sev_enum]
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid severity: {severity}")

    if check_type:
        try:
            ct_enum = CheckType(check_type)
            all_issues = [i for i in all_issues if i.check_type == ct_enum]
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid check_type: {check_type}")

    if table:
        all_issues = [i for i in all_issues if i.table == table]

    return [_issue_to_response(i) for i in all_issues[:limit]]
