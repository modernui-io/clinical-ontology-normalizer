"""Data Completeness API endpoints.

Provides endpoints for calculating and tracking OMOP CDM data completeness:
- Per-table and per-field completeness metrics
- Source-level breakdowns
- Historical trends
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.data_completeness_service import (
    OMOPTable,
    get_data_completeness_service,
)

router = APIRouter(prefix="/data-completeness", tags=["Data Quality"])


# ============================================================================
# Request/Response Models
# ============================================================================


class FieldCompletenessResponse(BaseModel):
    """Completeness data for a single field."""

    field_name: str = Field(..., description="Field name")
    total_records: int = Field(..., description="Total records in table")
    non_null_count: int = Field(..., description="Non-null count")
    null_count: int = Field(..., description="Null count")
    completeness_pct: float = Field(..., description="Completeness percentage")
    is_required: bool = Field(..., description="Whether field is required")


class TableCompletenessResponse(BaseModel):
    """Completeness scorecard for a table."""

    table_name: str = Field(..., description="Table name")
    total_records: int = Field(..., description="Total records")
    required_completeness_pct: float = Field(..., description="Required fields completeness")
    optional_completeness_pct: float = Field(..., description="Optional fields completeness")
    overall_completeness_pct: float = Field(..., description="Overall completeness")
    fields: list[FieldCompletenessResponse] = Field(..., description="Field-level completeness")


class SourceCompletenessResponse(BaseModel):
    """Completeness breakdown by source."""

    source_name: str = Field(..., description="Source name")
    record_count: int = Field(..., description="Total records from source")
    completeness_pct: float = Field(..., description="Overall completeness")
    tables: dict[str, float] = Field(..., description="Per-table completeness")


class CompletenessReportResponse(BaseModel):
    """Full completeness report response."""

    id: str = Field(..., description="Report ID")
    timestamp: float = Field(..., description="Report timestamp")
    overall_completeness_pct: float = Field(..., description="Overall completeness")
    tables: list[TableCompletenessResponse] = Field(..., description="Table-level completeness")
    sources: list[SourceCompletenessResponse] = Field(..., description="Source-level completeness")


class SnapshotResponse(BaseModel):
    """A point-in-time completeness measurement."""

    id: str = Field(..., description="Snapshot ID")
    timestamp: float = Field(..., description="Snapshot timestamp")
    overall_completeness_pct: float = Field(..., description="Overall completeness")
    table_scores: dict[str, float] = Field(..., description="Per-table completeness scores")


class TrendsResponse(BaseModel):
    """Historical completeness trends."""

    total: int = Field(..., description="Total snapshots returned")
    snapshots: list[SnapshotResponse] = Field(..., description="Historical snapshots")


class TablesResponse(BaseModel):
    """Available OMOP tables."""

    tables: list[dict[str, str]] = Field(..., description="Available tables")


# ============================================================================
# Helper Functions
# ============================================================================


def _field_to_response(fc) -> FieldCompletenessResponse:
    """Convert FieldCompleteness to response model."""
    return FieldCompletenessResponse(
        field_name=fc.field_name,
        total_records=fc.total_records,
        non_null_count=fc.non_null_count,
        null_count=fc.null_count,
        completeness_pct=fc.completeness_pct,
        is_required=fc.is_required,
    )


def _table_to_response(tc) -> TableCompletenessResponse:
    """Convert TableCompleteness to response model."""
    return TableCompletenessResponse(
        table_name=tc.table_name,
        total_records=tc.total_records,
        required_completeness_pct=tc.required_completeness_pct,
        optional_completeness_pct=tc.optional_completeness_pct,
        overall_completeness_pct=tc.overall_completeness_pct,
        fields=[_field_to_response(f) for f in tc.fields],
    )


def _source_to_response(sc) -> SourceCompletenessResponse:
    """Convert SourceCompleteness to response model."""
    return SourceCompletenessResponse(
        source_name=sc.source_name,
        record_count=sc.record_count,
        completeness_pct=sc.completeness_pct,
        tables=sc.tables,
    )


def _report_to_response(report) -> CompletenessReportResponse:
    """Convert CompletenessReport to response model."""
    return CompletenessReportResponse(
        id=report.id,
        timestamp=report.timestamp,
        overall_completeness_pct=report.overall_completeness_pct,
        tables=[_table_to_response(t) for t in report.tables],
        sources=[_source_to_response(s) for s in report.sources],
    )


# ============================================================================
# Endpoints - Static routes first
# ============================================================================


@router.get(
    "",
    response_model=CompletenessReportResponse,
    summary="Get completeness report",
    description="Get completeness metrics for all OMOP tables.",
)
async def get_completeness() -> CompletenessReportResponse:
    """Get overall completeness report."""
    service = get_data_completeness_service()
    report = service.get_completeness()
    return _report_to_response(report)


@router.get(
    "/tables",
    response_model=TablesResponse,
    summary="List available tables",
    description="Get list of OMOP tables that can be analyzed.",
)
async def list_tables() -> TablesResponse:
    """List available OMOP tables."""
    tables = [
        {"value": t.value, "name": t.name.replace("_", " ").title()}
        for t in OMOPTable
    ]
    return TablesResponse(tables=tables)


@router.get(
    "/trends",
    response_model=TrendsResponse,
    summary="Get completeness trends",
    description="Get historical completeness snapshots for trend analysis.",
)
async def get_trends(
    limit: int = Query(30, ge=1, le=100, description="Maximum snapshots to return"),
) -> TrendsResponse:
    """Get historical completeness trends."""
    service = get_data_completeness_service()
    snapshots = service.get_trends(limit=limit)
    return TrendsResponse(
        total=len(snapshots),
        snapshots=[
            SnapshotResponse(
                id=s.id,
                timestamp=s.timestamp,
                overall_completeness_pct=s.overall_completeness_pct,
                table_scores=s.table_scores,
            )
            for s in snapshots
        ],
    )


# ============================================================================
# Endpoints - Parameterized routes
# ============================================================================


@router.get(
    "/{table_name}",
    response_model=TableCompletenessResponse,
    summary="Get table completeness",
    description="Get completeness metrics for a specific OMOP table.",
)
async def get_table_completeness(table_name: str) -> TableCompletenessResponse:
    """Get completeness for a specific table."""
    service = get_data_completeness_service()
    table_completeness = service.get_table_completeness(table_name)

    if not table_completeness:
        raise HTTPException(
            status_code=404,
            detail=f"Table not found: {table_name}",
        )

    return _table_to_response(table_completeness)
