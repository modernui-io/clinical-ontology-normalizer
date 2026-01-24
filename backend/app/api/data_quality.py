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
