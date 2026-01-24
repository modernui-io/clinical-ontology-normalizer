"""Data Quality API endpoints.

Provides:
- GET /data-quality/completeness - Overall completeness report
- GET /data-quality/completeness/{table} - Table-specific completeness
- GET /data-quality/completeness/trends - Historical completeness trends
- GET /data-quality/consistency - Consistency validation results
- POST /data-quality/consistency/run - Trigger consistency checks
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.services.data_completeness_service import get_data_completeness_service
from app.services.data_consistency_service import get_data_consistency_service
from app.services.data_quality_service import get_data_quality_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data-quality", tags=["data-quality"])


@router.get("/completeness")
async def get_completeness() -> dict[str, Any]:
    """Get overall data completeness report across all OMOP tables."""
    service = get_data_completeness_service()
    report = service.get_completeness()

    return {
        "id": report.id,
        "timestamp": report.timestamp,
        "overall_completeness_pct": report.overall_completeness_pct,
        "tables": [
            {
                "table_name": t.table_name,
                "total_records": t.total_records,
                "required_completeness_pct": t.required_completeness_pct,
                "optional_completeness_pct": t.optional_completeness_pct,
                "overall_completeness_pct": t.overall_completeness_pct,
                "fields": [
                    {
                        "field_name": f.field_name,
                        "total_records": f.total_records,
                        "non_null_count": f.non_null_count,
                        "null_count": f.null_count,
                        "completeness_pct": f.completeness_pct,
                        "is_required": f.is_required,
                    }
                    for f in t.fields
                ],
            }
            for t in report.tables
        ],
        "sources": [
            {
                "source_name": s.source_name,
                "record_count": s.record_count,
                "completeness_pct": s.completeness_pct,
                "tables": s.tables,
            }
            for s in report.sources
        ],
    }


@router.get("/completeness/trends")
async def get_completeness_trends(
    limit: int = Query(30, ge=1, le=100, description="Number of history entries"),
) -> dict[str, Any]:
    """Get historical completeness trends."""
    service = get_data_completeness_service()
    trends = service.get_trends(limit=limit)

    return {
        "total_entries": len(trends),
        "trends": [
            {
                "id": s.id,
                "timestamp": s.timestamp,
                "overall_completeness_pct": s.overall_completeness_pct,
                "table_scores": s.table_scores,
            }
            for s in trends
        ],
    }


@router.get("/completeness/{table_name}")
async def get_table_completeness(table_name: str) -> dict[str, Any]:
    """Get completeness scorecard for a specific OMOP table."""
    service = get_data_completeness_service()
    result = service.get_table_completeness(table_name)

    if result is None:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

    return {
        "table_name": result.table_name,
        "total_records": result.total_records,
        "required_completeness_pct": result.required_completeness_pct,
        "optional_completeness_pct": result.optional_completeness_pct,
        "overall_completeness_pct": result.overall_completeness_pct,
        "fields": [
            {
                "field_name": f.field_name,
                "total_records": f.total_records,
                "non_null_count": f.non_null_count,
                "null_count": f.null_count,
                "completeness_pct": f.completeness_pct,
                "is_required": f.is_required,
            }
            for f in result.fields
        ],
    }


@router.get("/consistency")
async def get_consistency() -> dict[str, Any]:
    """Get the last consistency validation results."""
    service = get_data_consistency_service()
    report = service.get_results()

    if report is None:
        return {
            "message": "No consistency checks have been run yet",
            "results": [],
        }

    return _format_consistency_report(report)


@router.post("/consistency/run")
async def run_consistency_checks() -> dict[str, Any]:
    """Trigger consistency validation checks."""
    service = get_data_consistency_service()
    report = service.run_checks()
    return _format_consistency_report(report)


def _format_consistency_report(report) -> dict[str, Any]:
    """Format a ConsistencyReport for API response."""
    return {
        "id": report.id,
        "timestamp": report.timestamp,
        "total_checks": report.total_checks,
        "checks_passed": report.checks_passed,
        "checks_failed": report.checks_failed,
        "checks_warning": report.checks_warning,
        "total_issues": report.total_issues,
        "critical_issues": report.critical_issues,
        "high_issues": report.high_issues,
        "medium_issues": report.medium_issues,
        "low_issues": report.low_issues,
        "results": [
            {
                "check_id": r.check_id,
                "check_name": r.check_name,
                "check_type": r.check_type.value,
                "status": r.status.value,
                "records_checked": r.records_checked,
                "issues_found": r.issues_found,
                "issues": [
                    {
                        "issue_id": i.issue_id,
                        "check_type": i.check_type.value,
                        "severity": i.severity.value,
                        "table": i.table,
                        "field": i.field,
                        "record_id": i.record_id,
                        "description": i.description,
                        "current_value": i.current_value,
                        "expected_value": i.expected_value,
                    }
                    for i in r.issues
                ],
            }
            for r in report.results
        ],
    }


# =============================================================================
# OHDSI DQD Endpoints
# =============================================================================


@router.post("/dqd/run")
async def run_dqd_checks() -> dict[str, Any]:
    """Trigger OHDSI Data Quality Dashboard checks.

    Runs completeness, conformance, and plausibility checks
    across OMOP CDM tables. Returns the full run result with
    pass/fail counts and individual check details.
    """
    service = get_data_quality_service()
    result = service.run_checks()

    pass_rate = (
        round(result.summary.checks_passed / result.summary.total_checks * 100, 1)
        if result.summary.total_checks > 0
        else 0.0
    )

    return {
        "run_id": result.run_id,
        "started_at": result.started_at,
        "completed_at": result.completed_at,
        "duration_ms": result.duration_ms,
        "total_checks": result.summary.total_checks,
        "checks_passed": result.summary.checks_passed,
        "checks_failed": result.summary.checks_failed,
        "pass_rate": pass_rate,
        "overall_score": result.summary.overall_score,
        "results": [
            {
                "check_id": r.check_id,
                "check_name": r.check_name,
                "category": r.category.value,
                "subcategory": r.subcategory.value,
                "table": r.table.value,
                "field": r.field,
                "status": r.status.value,
                "score": r.score,
                "records_total": r.records_total,
                "records_passed": r.records_passed,
                "records_failed": r.records_failed,
                "percent_passed": r.percent_passed,
                "message": r.message,
            }
            for r in result.check_results
        ],
    }


@router.get("/dqd/results")
async def get_dqd_results() -> dict[str, Any]:
    """Get latest DQD results summary.

    Returns the most recent quality check summary with
    category-level and table-level breakdowns.
    """
    service = get_data_quality_service()
    summary = service.get_summary()

    return {
        "overall_score": summary.overall_score,
        "executed_at": summary.executed_at,
        "total_checks": summary.total_checks,
        "checks_passed": summary.checks_passed,
        "checks_failed": summary.checks_failed,
        "completeness_score": summary.completeness_score,
        "conformance_score": summary.conformance_score,
        "plausibility_score": summary.plausibility_score,
        "total_issues": summary.total_issues,
        "categories": [
            {
                "category": cat.category.value,
                "score": cat.score,
                "checks_total": cat.checks_total,
                "checks_passed": cat.checks_passed,
                "checks_failed": cat.checks_failed,
            }
            for cat in summary.category_summaries
        ],
        "tables": [
            {
                "table": tbl.table.value,
                "record_count": tbl.record_count,
                "score": tbl.score,
                "completeness_score": tbl.completeness_score,
                "conformance_score": tbl.conformance_score,
                "plausibility_score": tbl.plausibility_score,
                "issues_count": tbl.issues_count,
            }
            for tbl in summary.table_summaries
        ],
    }


@router.get("/dqd/history")
async def get_dqd_history(
    limit: int = Query(10, ge=1, le=100, description="Number of history entries"),
) -> dict[str, Any]:
    """Get DQD run history."""
    service = get_data_quality_service()
    history = service.get_history(limit=limit)

    return {
        "total": len(history),
        "entries": [
            {
                "run_id": entry.run_id,
                "timestamp": entry.timestamp,
                "overall_score": entry.overall_score,
                "completeness_score": entry.completeness_score,
                "conformance_score": entry.conformance_score,
                "plausibility_score": entry.plausibility_score,
                "total_checks": entry.total_checks,
                "checks_passed": entry.checks_passed,
                "total_issues": entry.total_issues,
            }
            for entry in history
        ],
    }


@router.get("/dqd/issues")
async def get_dqd_issues(
    severity: str | None = Query(None, description="Filter by severity: critical, high, medium, low"),
    limit: int = Query(50, ge=1, le=500, description="Maximum issues to return"),
) -> dict[str, Any]:
    """Get DQD issues from the latest run."""
    from app.services.data_quality_service import DQDSeverity

    service = get_data_quality_service()
    sev = DQDSeverity(severity) if severity else None
    issues = service.get_issues(severity=sev, limit=limit)

    return {
        "total": len(issues),
        "issues": [
            {
                "issue_id": issue.issue_id,
                "check_id": issue.check_id,
                "category": issue.category.value,
                "severity": issue.severity.value,
                "table": issue.table.value,
                "field": issue.field,
                "description": issue.description,
                "current_value": issue.current_value,
                "expected_value": issue.expected_value,
                "recommendation": issue.recommendation,
            }
            for issue in issues
        ],
    }
