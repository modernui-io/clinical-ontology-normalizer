"""Data Quality Dashboard (DQD) Reporting API Endpoints.

Provides endpoints for OHDSI-style Data Quality Dashboard:
- Overall quality scores (Completeness, Conformance, Plausibility)
- Individual check results
- Issue tracking with severity levels
- Historical quality trends
"""

from enum import Enum
from uuid import uuid4

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.api.errors import ErrorCode, InternalError


router = APIRouter(prefix="/quality", tags=["Data Quality Dashboard"])


# ============================================================================
# Data Quality Dashboard (DQD) Enums
# ============================================================================


class DQDCategoryAPI(str, Enum):
    """Data quality check categories."""

    COMPLETENESS = "completeness"
    CONFORMANCE = "conformance"
    PLAUSIBILITY = "plausibility"


class DQDSubcategoryAPI(str, Enum):
    """Data quality check subcategories."""

    COMPLETENESS_REQUIRED = "required_fields"
    COMPLETENESS_OPTIONAL = "optional_fields"
    CONFORMANCE_VALUE = "value_conformance"
    CONFORMANCE_RELATIONAL = "relational_conformance"
    CONFORMANCE_COMPUTATIONAL = "computational_conformance"
    PLAUSIBILITY_TEMPORAL = "temporal_plausibility"
    PLAUSIBILITY_ATEMPORAL = "atemporal_plausibility"
    PLAUSIBILITY_UNIQUENESS = "uniqueness_plausibility"


class DQDSeverityAPI(str, Enum):
    """Severity levels for data quality issues."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DQDStatusAPI(str, Enum):
    """Status of a quality check."""

    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    ERROR = "error"
    NOT_APPLICABLE = "not_applicable"


class OMOPTableAPI(str, Enum):
    """OMOP CDM tables."""

    PERSON = "person"
    VISIT_OCCURRENCE = "visit_occurrence"
    CONDITION_OCCURRENCE = "condition_occurrence"
    DRUG_EXPOSURE = "drug_exposure"
    PROCEDURE_OCCURRENCE = "procedure_occurrence"
    MEASUREMENT = "measurement"
    OBSERVATION = "observation"
    NOTE = "note"
    NOTE_NLP = "note_nlp"
    DEATH = "death"


# ============================================================================
# DQD Response Models
# ============================================================================


class DQDCheckResultResponse(BaseModel):
    """Result of a single data quality check."""

    check_id: str = Field(..., description="Unique check identifier")
    check_name: str = Field(..., description="Human-readable check name")
    category: DQDCategoryAPI = Field(..., description="Check category")
    subcategory: DQDSubcategoryAPI = Field(..., description="Check subcategory")
    table: OMOPTableAPI = Field(..., description="OMOP table being checked")
    field: str | None = Field(None, description="Field being checked")

    status: DQDStatusAPI = Field(..., description="Check status")
    severity: DQDSeverityAPI = Field(..., description="Issue severity if failed")
    score: float = Field(..., ge=0, le=100, description="Check score (0-100)")

    records_total: int = Field(0, description="Total records checked")
    records_passed: int = Field(0, description="Records that passed")
    records_failed: int = Field(0, description="Records that failed")
    percent_passed: float = Field(0, description="Percentage of records passed")

    threshold_value: float = Field(0, description="Pass threshold")
    message: str = Field("", description="Result message")
    failed_examples: list[dict] = Field(default_factory=list, description="Sample failed records")
    execution_time_ms: float = Field(0, description="Check execution time")
    executed_at: str = Field(..., description="Execution timestamp")


class DQDIssueResponse(BaseModel):
    """A data quality issue."""

    issue_id: str = Field(..., description="Unique issue identifier")
    check_id: str = Field(..., description="Check that found this issue")
    table: OMOPTableAPI = Field(..., description="Affected table")
    field: str | None = Field(None, description="Affected field")
    record_id: str | None = Field(None, description="Specific record ID if applicable")
    severity: DQDSeverityAPI = Field(..., description="Issue severity")
    category: DQDCategoryAPI = Field(..., description="Issue category")

    description: str = Field(..., description="Issue description")
    current_value: str | None = Field(None, description="Current value")
    expected_value: str | None = Field(None, description="Expected value")
    recommendation: str = Field("", description="Remediation recommendation")

    detected_at: str = Field(..., description="When issue was detected")
    resolved: bool = Field(False, description="Whether issue is resolved")


class DQDCategorySummaryResponse(BaseModel):
    """Summary for a quality category."""

    category: DQDCategoryAPI = Field(..., description="Category")
    score: float = Field(..., ge=0, le=100, description="Category score")
    checks_total: int = Field(..., description="Total checks in category")
    checks_passed: int = Field(..., description="Passed checks")
    checks_failed: int = Field(..., description="Failed checks")
    checks_warning: int = Field(..., description="Warning checks")
    critical_issues: int = Field(0, description="Critical issues count")
    high_issues: int = Field(0, description="High priority issues count")

    previous_score: float | None = Field(None, description="Previous score for trend")
    score_change: float | None = Field(None, description="Score change from previous")


class DQDTableSummaryResponse(BaseModel):
    """Summary for an OMOP table."""

    table: OMOPTableAPI = Field(..., description="Table name")
    record_count: int = Field(..., description="Total records in table")
    score: float = Field(..., ge=0, le=100, description="Table quality score")
    completeness_score: float = Field(..., description="Completeness score")
    conformance_score: float = Field(..., description="Conformance score")
    plausibility_score: float = Field(..., description="Plausibility score")
    issues_count: int = Field(0, description="Total issues for table")
    critical_issues: int = Field(0, description="Critical issues for table")


class DQDSummaryResponse(BaseModel):
    """Overall data quality summary."""

    overall_score: float = Field(..., ge=0, le=100, description="Overall quality score")
    executed_at: str = Field(..., description="Last execution timestamp")
    execution_time_ms: float = Field(..., description="Execution time")

    completeness_score: float = Field(..., description="Completeness score")
    conformance_score: float = Field(..., description="Conformance score")
    plausibility_score: float = Field(..., description="Plausibility score")

    total_checks: int = Field(..., description="Total checks executed")
    checks_passed: int = Field(..., description="Checks passed")
    checks_failed: int = Field(..., description="Checks failed")
    checks_warning: int = Field(..., description="Checks with warnings")
    checks_error: int = Field(0, description="Checks that errored")

    total_issues: int = Field(0, description="Total issues found")
    critical_issues: int = Field(0, description="Critical issues")
    high_issues: int = Field(0, description="High priority issues")
    medium_issues: int = Field(0, description="Medium priority issues")
    low_issues: int = Field(0, description="Low priority issues")

    category_summaries: list[DQDCategorySummaryResponse] = Field(
        default_factory=list,
        description="Summaries by category"
    )
    table_summaries: list[DQDTableSummaryResponse] = Field(
        default_factory=list,
        description="Summaries by table"
    )


class DQDHistoryEntryResponse(BaseModel):
    """Historical quality score entry."""

    run_id: str = Field(..., description="Run identifier")
    timestamp: str = Field(..., description="Run timestamp")
    overall_score: float = Field(..., description="Overall score")
    completeness_score: float = Field(..., description="Completeness score")
    conformance_score: float = Field(..., description="Conformance score")
    plausibility_score: float = Field(..., description="Plausibility score")
    total_checks: int = Field(..., description="Total checks")
    checks_passed: int = Field(..., description="Checks passed")
    total_issues: int = Field(..., description="Total issues")


class DQDCheckListResponse(BaseModel):
    """Response for list of check results."""

    request_id: str = Field(..., description="Request identifier")
    total_checks: int = Field(..., description="Total checks returned")
    category_filter: str | None = Field(None, description="Category filter applied")
    checks: list[DQDCheckResultResponse] = Field(..., description="Check results")


class DQDHistoryResponse(BaseModel):
    """Response for quality history."""

    request_id: str = Field(..., description="Request identifier")
    entries: list[DQDHistoryEntryResponse] = Field(..., description="History entries")
    total_entries: int = Field(..., description="Total entries returned")


class DQDRunResponse(BaseModel):
    """Response for a quality check run."""

    request_id: str = Field(..., description="Request identifier")
    run_id: str = Field(..., description="Run identifier")
    summary: DQDSummaryResponse = Field(..., description="Run summary")
    total_checks: int = Field(..., description="Total checks executed")
    total_issues: int = Field(..., description="Total issues found")
    duration_ms: float = Field(..., description="Run duration")
    started_at: str = Field(..., description="Run start time")
    completed_at: str = Field(..., description="Run completion time")


class DQDIssueListResponse(BaseModel):
    """Response for list of issues."""

    request_id: str = Field(..., description="Request identifier")
    total_issues: int = Field(..., description="Total issues")
    severity_filter: str | None = Field(None, description="Severity filter applied")
    issues: list[DQDIssueResponse] = Field(..., description="Issues list")


# ============================================================================
# DQD API Endpoints
# ============================================================================


@router.get(
    "/dqd/summary",
    response_model=DQDSummaryResponse,
    summary="Get overall data quality summary",
    description="Returns aggregate quality scores for Completeness, Conformance, and Plausibility.",
)
async def get_dqd_summary() -> DQDSummaryResponse:
    """Get overall data quality summary.

    Returns aggregate quality scores across all OMOP CDM tables,
    broken down by the three OHDSI DQD categories:
    - Completeness: Required fields populated
    - Conformance: Values within expected ranges
    - Plausibility: Temporal consistency and reasonable values

    Returns:
        DQDSummaryResponse with overall and category scores.
    """
    try:
        from app.services.data_quality_service import get_data_quality_service

        service = get_data_quality_service()
        summary = service.get_summary()

        return DQDSummaryResponse(
            overall_score=summary.overall_score,
            executed_at=summary.executed_at,
            execution_time_ms=summary.execution_time_ms,
            completeness_score=summary.completeness_score,
            conformance_score=summary.conformance_score,
            plausibility_score=summary.plausibility_score,
            total_checks=summary.total_checks,
            checks_passed=summary.checks_passed,
            checks_failed=summary.checks_failed,
            checks_warning=summary.checks_warning,
            checks_error=summary.checks_error,
            total_issues=summary.total_issues,
            critical_issues=summary.critical_issues,
            high_issues=summary.high_issues,
            medium_issues=summary.medium_issues,
            low_issues=summary.low_issues,
            category_summaries=[
                DQDCategorySummaryResponse(
                    category=DQDCategoryAPI(cs.category.value),
                    score=cs.score,
                    checks_total=cs.checks_total,
                    checks_passed=cs.checks_passed,
                    checks_failed=cs.checks_failed,
                    checks_warning=cs.checks_warning,
                    critical_issues=cs.critical_issues,
                    high_issues=cs.high_issues,
                    previous_score=cs.previous_score,
                    score_change=cs.score_change,
                )
                for cs in summary.category_summaries
            ],
            table_summaries=[
                DQDTableSummaryResponse(
                    table=OMOPTableAPI(ts.table.value),
                    record_count=ts.record_count,
                    score=ts.score,
                    completeness_score=ts.completeness_score,
                    conformance_score=ts.conformance_score,
                    plausibility_score=ts.plausibility_score,
                    issues_count=ts.issues_count,
                    critical_issues=ts.critical_issues,
                )
                for ts in summary.table_summaries
            ],
        )

    except Exception as e:
        raise InternalError(
            message=f"Failed to get DQD summary: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )


@router.get(
    "/dqd/checks",
    response_model=DQDCheckListResponse,
    summary="List all data quality check results",
    description="Returns results of all executed quality checks.",
)
async def list_dqd_checks(
    category: DQDCategoryAPI | None = Query(None, description="Filter by category"),
) -> DQDCheckListResponse:
    """List all data quality check results.

    Args:
        category: Optional category filter (completeness, conformance, plausibility)

    Returns:
        DQDCheckListResponse with check results.
    """
    request_id = str(uuid4())

    try:
        from app.services.data_quality_service import (
            get_data_quality_service,
            DQDCategory,
        )

        service = get_data_quality_service()

        cat_filter = None
        if category:
            cat_filter = DQDCategory(category.value)

        checks = service.get_checks(category=cat_filter)

        return DQDCheckListResponse(
            request_id=request_id,
            total_checks=len(checks),
            category_filter=category.value if category else None,
            checks=[
                DQDCheckResultResponse(
                    check_id=c.check_id,
                    check_name=c.check_name,
                    category=DQDCategoryAPI(c.category.value),
                    subcategory=DQDSubcategoryAPI(c.subcategory.value),
                    table=OMOPTableAPI(c.table.value),
                    field=c.field,
                    status=DQDStatusAPI(c.status.value),
                    severity=DQDSeverityAPI(c.severity.value),
                    score=c.score,
                    records_total=c.records_total,
                    records_passed=c.records_passed,
                    records_failed=c.records_failed,
                    percent_passed=c.percent_passed,
                    threshold_value=c.threshold_value,
                    message=c.message,
                    failed_examples=c.failed_examples,
                    execution_time_ms=c.execution_time_ms,
                    executed_at=c.executed_at,
                )
                for c in checks
            ],
        )

    except Exception as e:
        raise InternalError(
            message=f"Failed to list DQD checks: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )


@router.get(
    "/dqd/checks/{category}",
    response_model=DQDCheckListResponse,
    summary="Get checks by category",
    description="Returns check results for a specific quality category.",
)
async def get_dqd_checks_by_category(
    category: DQDCategoryAPI,
) -> DQDCheckListResponse:
    """Get check results for a specific category.

    Args:
        category: Quality category (completeness, conformance, plausibility)

    Returns:
        DQDCheckListResponse with filtered check results.
    """
    request_id = str(uuid4())

    try:
        from app.services.data_quality_service import (
            get_data_quality_service,
            DQDCategory,
        )

        service = get_data_quality_service()
        cat_enum = DQDCategory(category.value)
        checks = service.get_checks_by_category(cat_enum)

        return DQDCheckListResponse(
            request_id=request_id,
            total_checks=len(checks),
            category_filter=category.value,
            checks=[
                DQDCheckResultResponse(
                    check_id=c.check_id,
                    check_name=c.check_name,
                    category=DQDCategoryAPI(c.category.value),
                    subcategory=DQDSubcategoryAPI(c.subcategory.value),
                    table=OMOPTableAPI(c.table.value),
                    field=c.field,
                    status=DQDStatusAPI(c.status.value),
                    severity=DQDSeverityAPI(c.severity.value),
                    score=c.score,
                    records_total=c.records_total,
                    records_passed=c.records_passed,
                    records_failed=c.records_failed,
                    percent_passed=c.percent_passed,
                    threshold_value=c.threshold_value,
                    message=c.message,
                    failed_examples=c.failed_examples,
                    execution_time_ms=c.execution_time_ms,
                    executed_at=c.executed_at,
                )
                for c in checks
            ],
        )

    except Exception as e:
        raise InternalError(
            message=f"Failed to get DQD checks by category: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )


@router.post(
    "/dqd/run",
    response_model=DQDRunResponse,
    summary="Trigger data quality check run",
    description="Executes all data quality checks and returns results.",
)
async def run_dqd_checks() -> DQDRunResponse:
    """Trigger a fresh data quality check run.

    Executes all configured quality checks against the OMOP CDM tables
    and returns comprehensive results.

    Returns:
        DQDRunResponse with run results and summary.
    """
    request_id = str(uuid4())

    try:
        from app.services.data_quality_service import get_data_quality_service

        service = get_data_quality_service()
        run_result = service.run_checks()

        summary = run_result.summary
        return DQDRunResponse(
            request_id=request_id,
            run_id=run_result.run_id,
            summary=DQDSummaryResponse(
                overall_score=summary.overall_score,
                executed_at=summary.executed_at,
                execution_time_ms=summary.execution_time_ms,
                completeness_score=summary.completeness_score,
                conformance_score=summary.conformance_score,
                plausibility_score=summary.plausibility_score,
                total_checks=summary.total_checks,
                checks_passed=summary.checks_passed,
                checks_failed=summary.checks_failed,
                checks_warning=summary.checks_warning,
                checks_error=summary.checks_error,
                total_issues=summary.total_issues,
                critical_issues=summary.critical_issues,
                high_issues=summary.high_issues,
                medium_issues=summary.medium_issues,
                low_issues=summary.low_issues,
                category_summaries=[
                    DQDCategorySummaryResponse(
                        category=DQDCategoryAPI(cs.category.value),
                        score=cs.score,
                        checks_total=cs.checks_total,
                        checks_passed=cs.checks_passed,
                        checks_failed=cs.checks_failed,
                        checks_warning=cs.checks_warning,
                        critical_issues=cs.critical_issues,
                        high_issues=cs.high_issues,
                    )
                    for cs in summary.category_summaries
                ],
                table_summaries=[
                    DQDTableSummaryResponse(
                        table=OMOPTableAPI(ts.table.value),
                        record_count=ts.record_count,
                        score=ts.score,
                        completeness_score=ts.completeness_score,
                        conformance_score=ts.conformance_score,
                        plausibility_score=ts.plausibility_score,
                        issues_count=ts.issues_count,
                        critical_issues=ts.critical_issues,
                    )
                    for ts in summary.table_summaries
                ],
            ),
            total_checks=len(run_result.check_results),
            total_issues=len(run_result.issues),
            duration_ms=run_result.duration_ms,
            started_at=run_result.started_at,
            completed_at=run_result.completed_at,
        )

    except Exception as e:
        raise InternalError(
            message=f"Failed to run DQD checks: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )


@router.get(
    "/dqd/history",
    response_model=DQDHistoryResponse,
    summary="Get historical quality scores",
    description="Returns historical quality scores for trend analysis.",
)
async def get_dqd_history(
    limit: int = Query(30, ge=1, le=100, description="Number of entries to return"),
) -> DQDHistoryResponse:
    """Get historical quality scores.

    Args:
        limit: Maximum number of history entries to return (default 30, max 100)

    Returns:
        DQDHistoryResponse with historical entries.
    """
    request_id = str(uuid4())

    try:
        from app.services.data_quality_service import get_data_quality_service

        service = get_data_quality_service()
        history = service.get_history(limit=limit)

        return DQDHistoryResponse(
            request_id=request_id,
            entries=[
                DQDHistoryEntryResponse(
                    run_id=h.run_id,
                    timestamp=h.timestamp,
                    overall_score=h.overall_score,
                    completeness_score=h.completeness_score,
                    conformance_score=h.conformance_score,
                    plausibility_score=h.plausibility_score,
                    total_checks=h.total_checks,
                    checks_passed=h.checks_passed,
                    total_issues=h.total_issues,
                )
                for h in history
            ],
            total_entries=len(history),
        )

    except Exception as e:
        raise InternalError(
            message=f"Failed to get DQD history: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )


@router.get(
    "/dqd/issues",
    response_model=DQDIssueListResponse,
    summary="Get data quality issues",
    description="Returns list of identified data quality issues.",
)
async def get_dqd_issues(
    severity: DQDSeverityAPI | None = Query(None, description="Filter by severity"),
    limit: int = Query(100, ge=1, le=500, description="Maximum issues to return"),
) -> DQDIssueListResponse:
    """Get data quality issues.

    Args:
        severity: Optional severity filter
        limit: Maximum number of issues to return

    Returns:
        DQDIssueListResponse with issues list.
    """
    request_id = str(uuid4())

    try:
        from app.services.data_quality_service import (
            get_data_quality_service,
            DQDSeverity,
        )

        service = get_data_quality_service()

        sev_filter = None
        if severity:
            sev_filter = DQDSeverity(severity.value)

        issues = service.get_issues(severity=sev_filter, limit=limit)

        return DQDIssueListResponse(
            request_id=request_id,
            total_issues=len(issues),
            severity_filter=severity.value if severity else None,
            issues=[
                DQDIssueResponse(
                    issue_id=i.issue_id,
                    check_id=i.check_id,
                    table=OMOPTableAPI(i.table.value),
                    field=i.field,
                    record_id=i.record_id,
                    severity=DQDSeverityAPI(i.severity.value),
                    category=DQDCategoryAPI(i.category.value),
                    description=i.description,
                    current_value=str(i.current_value) if i.current_value else None,
                    expected_value=str(i.expected_value) if i.expected_value else None,
                    recommendation=i.recommendation,
                    detected_at=i.detected_at,
                    resolved=i.resolved,
                )
                for i in issues
            ],
        )

    except Exception as e:
        raise InternalError(
            message=f"Failed to get DQD issues: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )


@router.get(
    "/dqd/stats",
    summary="Get DQD service statistics",
    description="Get statistics about the Data Quality Dashboard service.",
)
async def get_dqd_stats() -> dict:
    """Get DQD service statistics.

    Returns information about configured checks and service state.
    """
    try:
        from app.services.data_quality_service import get_data_quality_service

        service = get_data_quality_service()
        return service.get_stats()

    except Exception as e:
        raise InternalError(
            message=f"Failed to get DQD stats: {str(e)}",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
        )
