"""HIPAA-compliant audit trail API endpoints.

Provides endpoints for:
- Querying audit logs with filters
- Exporting audit logs to various formats
- Managing audit export records
- Downloading export files

All endpoints require admin authorization in production.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.audit import (
    AuditAction,
    AuditExport,
    AuditExportFormat,
    AuditExportStatus,
    AuditLog,
    AuditResourceType,
)
from app.services.audit_service import get_audit_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audit", tags=["Audit"])

# Type alias for database session dependency
DbSession = Annotated[AsyncSession, Depends(get_db)]


# ============================================================================
# Request/Response Models
# ============================================================================


class AuditLogResponse(BaseModel):
    """Response model for a single audit log entry."""

    id: str
    timestamp: datetime
    user_id: str | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    request_id: str | None = None
    request_method: str | None = None
    request_path: str | None = None
    response_status: int | None = None
    details: dict[str, Any] | None = None
    phi_accessed: bool
    patient_id: str | None = None
    session_id: str | None = None
    success: bool
    error_message: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    """Response model for paginated audit log list."""

    logs: list[AuditLogResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class AuditExportRequest(BaseModel):
    """Request model for creating an audit export."""

    start_date: datetime = Field(..., description="Start date for export range")
    end_date: datetime = Field(..., description="End date for export range")
    format: str = Field(
        default="json",
        description="Export format: json, csv, or hipaa",
    )
    filters: dict[str, Any] | None = Field(
        default=None,
        description="Additional filters for the export",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "start_date": "2024-01-01T00:00:00Z",
                "end_date": "2024-01-31T23:59:59Z",
                "format": "hipaa",
                "filters": {
                    "phi_only": True,
                    "user_id": "admin@example.com",
                },
            }
        }


class AuditExportResponse(BaseModel):
    """Response model for audit export record."""

    id: str
    export_date: datetime
    start_date: datetime
    end_date: datetime
    file_path: str | None = None
    file_size_bytes: int | None = None
    record_count: int | None = None
    format: str
    status: str
    error_message: str | None = None
    requested_by: str | None = None
    filters: dict[str, Any] | None = None
    checksum: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class AuditExportListResponse(BaseModel):
    """Response model for list of audit exports."""

    exports: list[AuditExportResponse]
    total: int


class AuditStatsResponse(BaseModel):
    """Response model for audit statistics."""

    total_logs: int
    phi_access_count: int
    unique_users: int
    action_counts: dict[str, int]
    resource_type_counts: dict[str, int]
    period_start: datetime | None = None
    period_end: datetime | None = None


# ============================================================================
# API Endpoints
# ============================================================================


@router.get(
    "/logs",
    response_model=AuditLogListResponse,
    summary="Query audit logs",
    description="Query audit logs with filters. Requires admin authorization.",
)
async def get_audit_logs(
    db: DbSession,
    start_date: datetime | None = Query(
        None,
        description="Filter by start timestamp (ISO format)",
    ),
    end_date: datetime | None = Query(
        None,
        description="Filter by end timestamp (ISO format)",
    ),
    user_id: str | None = Query(
        None,
        description="Filter by user ID",
    ),
    action: str | None = Query(
        None,
        description="Filter by action type",
    ),
    resource_type: str | None = Query(
        None,
        description="Filter by resource type",
    ),
    resource_id: str | None = Query(
        None,
        description="Filter by resource ID",
    ),
    patient_id: str | None = Query(
        None,
        description="Filter by patient ID",
    ),
    phi_only: bool = Query(
        False,
        description="Only return PHI access events",
    ),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
        description="Maximum number of results",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Pagination offset",
    ),
) -> AuditLogListResponse:
    """Query audit logs with filters.

    This endpoint provides access to the audit trail for compliance
    monitoring and security analysis. Results are paginated and can
    be filtered by various criteria.

    **Access Control**: This endpoint should be restricted to admin users.
    In production, implement proper authorization checks.

    **HIPAA Compliance**: Access to this endpoint should itself be logged.
    """
    audit_service = get_audit_service()

    logs, total = await audit_service.query_logs(
        db=db,
        start_date=start_date,
        end_date=end_date,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        patient_id=patient_id,
        phi_only=phi_only,
        limit=limit,
        offset=offset,
    )

    # Convert to response models
    log_responses = [
        AuditLogResponse(
            id=log.id,
            timestamp=log.timestamp,
            user_id=log.user_id,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            ip_address=log.ip_address,
            user_agent=log.user_agent,
            request_id=log.request_id,
            request_method=log.request_method,
            request_path=log.request_path,
            response_status=log.response_status,
            details=log.details,
            phi_accessed=log.phi_accessed,
            patient_id=log.patient_id,
            session_id=log.session_id,
            success=log.success,
            error_message=log.error_message,
            created_at=log.created_at,
        )
        for log in logs
    ]

    return AuditLogListResponse(
        logs=log_responses,
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + len(logs)) < total,
    )


@router.get(
    "/logs/{log_id}",
    response_model=AuditLogResponse,
    summary="Get single audit log",
    description="Get a specific audit log entry by ID.",
)
async def get_audit_log(
    log_id: str,
    db: DbSession,
) -> AuditLogResponse:
    """Get a specific audit log entry.

    Args:
        log_id: The audit log ID
        db: Database session

    Returns:
        The audit log entry

    Raises:
        HTTPException: If audit log not found
    """
    stmt = select(AuditLog).where(AuditLog.id == log_id)
    result = await db.execute(stmt)
    log = result.scalar_one_or_none()

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit log not found: {log_id}",
        )

    return AuditLogResponse(
        id=log.id,
        timestamp=log.timestamp,
        user_id=log.user_id,
        action=log.action,
        resource_type=log.resource_type,
        resource_id=log.resource_id,
        ip_address=log.ip_address,
        user_agent=log.user_agent,
        request_id=log.request_id,
        request_method=log.request_method,
        request_path=log.request_path,
        response_status=log.response_status,
        details=log.details,
        phi_accessed=log.phi_accessed,
        patient_id=log.patient_id,
        session_id=log.session_id,
        success=log.success,
        error_message=log.error_message,
        created_at=log.created_at,
    )


@router.get(
    "/stats",
    response_model=AuditStatsResponse,
    summary="Get audit statistics",
    description="Get aggregate statistics for audit logs.",
)
async def get_audit_stats(
    db: DbSession,
    start_date: datetime | None = Query(
        None,
        description="Filter by start timestamp",
    ),
    end_date: datetime | None = Query(
        None,
        description="Filter by end timestamp",
    ),
) -> AuditStatsResponse:
    """Get aggregate statistics for audit logs.

    Provides summary statistics including:
    - Total log count
    - PHI access count
    - Unique users
    - Action type distribution
    - Resource type distribution
    """
    from sqlalchemy import distinct, func

    # Build base query with date filters
    conditions = []
    if start_date:
        conditions.append(AuditLog.timestamp >= start_date)
    if end_date:
        conditions.append(AuditLog.timestamp <= end_date)

    # Total logs
    total_query = select(func.count(AuditLog.id))
    if conditions:
        total_query = total_query.where(*conditions)
    total_result = await db.execute(total_query)
    total_logs = total_result.scalar() or 0

    # PHI access count
    phi_query = select(func.count(AuditLog.id)).where(
        AuditLog.phi_accessed == True  # noqa: E712
    )
    if conditions:
        phi_query = phi_query.where(*conditions)
    phi_result = await db.execute(phi_query)
    phi_count = phi_result.scalar() or 0

    # Unique users
    users_query = select(func.count(distinct(AuditLog.user_id)))
    if conditions:
        users_query = users_query.where(*conditions)
    users_result = await db.execute(users_query)
    unique_users = users_result.scalar() or 0

    # Action counts
    action_query = select(AuditLog.action, func.count(AuditLog.id)).group_by(
        AuditLog.action
    )
    if conditions:
        action_query = action_query.where(*conditions)
    action_result = await db.execute(action_query)
    action_counts = {row[0]: row[1] for row in action_result.all()}

    # Resource type counts
    resource_query = select(
        AuditLog.resource_type, func.count(AuditLog.id)
    ).group_by(AuditLog.resource_type)
    if conditions:
        resource_query = resource_query.where(*conditions)
    resource_result = await db.execute(resource_query)
    resource_counts = {row[0]: row[1] for row in resource_result.all()}

    return AuditStatsResponse(
        total_logs=total_logs,
        phi_access_count=phi_count,
        unique_users=unique_users,
        action_counts=action_counts,
        resource_type_counts=resource_counts,
        period_start=start_date,
        period_end=end_date,
    )


@router.post(
    "/export",
    response_model=AuditExportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create audit export",
    description="Create a new audit log export job.",
)
async def create_audit_export(
    request: AuditExportRequest,
    db: DbSession,
    requested_by: str | None = Query(
        None,
        description="User requesting the export",
    ),
) -> AuditExportResponse:
    """Create a new audit log export.

    This endpoint creates an export job that will generate a file
    containing audit logs for the specified date range. The export
    can be downloaded once processing is complete.

    **Supported Formats**:
    - `json`: Standard JSON format with all fields
    - `csv`: CSV format for spreadsheet import
    - `hipaa`: HIPAA-compliant format with required fields

    **HIPAA Note**: The HIPAA format includes all fields required by
    HIPAA regulations for audit trail documentation.
    """
    # Validate format
    valid_formats = [f.value for f in AuditExportFormat]
    if request.format not in valid_formats:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid format. Must be one of: {valid_formats}",
        )

    # Validate date range
    if request.start_date >= request.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before end_date",
        )

    audit_service = get_audit_service()

    # Create export record
    export_record = await audit_service.create_export(
        db=db,
        start_date=request.start_date,
        end_date=request.end_date,
        requested_by=requested_by,
        export_format=request.format,
        filters=request.filters,
    )

    # Process the export immediately (could be async in production)
    export_record = await audit_service.process_export(
        db=db,
        export_id=export_record.id,
    )

    await db.commit()

    return AuditExportResponse(
        id=export_record.id,
        export_date=export_record.export_date,
        start_date=export_record.start_date,
        end_date=export_record.end_date,
        file_path=export_record.file_path,
        file_size_bytes=export_record.file_size_bytes,
        record_count=export_record.record_count,
        format=export_record.format,
        status=export_record.status,
        error_message=export_record.error_message,
        requested_by=export_record.requested_by,
        filters=export_record.filters,
        checksum=export_record.checksum,
        started_at=export_record.started_at,
        completed_at=export_record.completed_at,
        created_at=export_record.created_at,
    )


@router.get(
    "/exports",
    response_model=AuditExportListResponse,
    summary="List audit exports",
    description="List all past audit export records.",
)
async def list_audit_exports(
    db: DbSession,
    limit: int = Query(
        50,
        ge=1,
        le=100,
        description="Maximum number of results",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Pagination offset",
    ),
) -> AuditExportListResponse:
    """List all audit export records.

    Returns a paginated list of audit export records, ordered by
    export date (most recent first).
    """
    from sqlalchemy import func

    # Get total count
    count_stmt = select(func.count(AuditExport.id))
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    # Get exports
    stmt = (
        select(AuditExport)
        .order_by(AuditExport.export_date.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    exports = result.scalars().all()

    return AuditExportListResponse(
        exports=[
            AuditExportResponse(
                id=export.id,
                export_date=export.export_date,
                start_date=export.start_date,
                end_date=export.end_date,
                file_path=export.file_path,
                file_size_bytes=export.file_size_bytes,
                record_count=export.record_count,
                format=export.format,
                status=export.status,
                error_message=export.error_message,
                requested_by=export.requested_by,
                filters=export.filters,
                checksum=export.checksum,
                started_at=export.started_at,
                completed_at=export.completed_at,
                created_at=export.created_at,
            )
            for export in exports
        ],
        total=total,
    )


@router.get(
    "/exports/{export_id}",
    response_model=AuditExportResponse,
    summary="Get audit export",
    description="Get details of a specific audit export.",
)
async def get_audit_export(
    export_id: str,
    db: DbSession,
) -> AuditExportResponse:
    """Get details of a specific audit export.

    Args:
        export_id: The export ID
        db: Database session

    Returns:
        The export record

    Raises:
        HTTPException: If export not found
    """
    stmt = select(AuditExport).where(AuditExport.id == export_id)
    result = await db.execute(stmt)
    export = result.scalar_one_or_none()

    if not export:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export not found: {export_id}",
        )

    return AuditExportResponse(
        id=export.id,
        export_date=export.export_date,
        start_date=export.start_date,
        end_date=export.end_date,
        file_path=export.file_path,
        file_size_bytes=export.file_size_bytes,
        record_count=export.record_count,
        format=export.format,
        status=export.status,
        error_message=export.error_message,
        requested_by=export.requested_by,
        filters=export.filters,
        checksum=export.checksum,
        started_at=export.started_at,
        completed_at=export.completed_at,
        created_at=export.created_at,
    )


@router.get(
    "/exports/{export_id}/download",
    summary="Download audit export",
    description="Download the export file for a completed export.",
)
async def download_audit_export(
    export_id: str,
    db: DbSession,
) -> FileResponse:
    """Download the export file for a completed export.

    Args:
        export_id: The export ID
        db: Database session

    Returns:
        The export file as a download

    Raises:
        HTTPException: If export not found or not completed
    """
    stmt = select(AuditExport).where(AuditExport.id == export_id)
    result = await db.execute(stmt)
    export = result.scalar_one_or_none()

    if not export:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export not found: {export_id}",
        )

    if export.status != AuditExportStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Export is not ready. Status: {export.status}",
        )

    if not export.file_path or not Path(export.file_path).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export file not found on disk",
        )

    # Determine media type
    media_type_map = {
        "json": "application/json",
        "csv": "text/csv",
        "hipaa": "application/json",
    }
    media_type = media_type_map.get(export.format, "application/octet-stream")

    # Get filename from path
    filename = Path(export.file_path).name

    return FileResponse(
        path=export.file_path,
        media_type=media_type,
        filename=filename,
        headers={
            "X-Checksum-SHA256": export.checksum or "",
        },
    )


@router.get(
    "/actions",
    summary="List valid action types",
    description="Get list of valid audit action types.",
)
async def list_audit_actions() -> dict[str, list[str]]:
    """List all valid audit action types.

    Returns:
        Dictionary with list of valid actions
    """
    return {"actions": [action.value for action in AuditAction]}


@router.get(
    "/resource-types",
    summary="List valid resource types",
    description="Get list of valid audit resource types.",
)
async def list_audit_resource_types() -> dict[str, list[str]]:
    """List all valid audit resource types.

    Returns:
        Dictionary with list of valid resource types
    """
    return {"resource_types": [rt.value for rt in AuditResourceType]}


@router.get(
    "/export-formats",
    summary="List valid export formats",
    description="Get list of valid audit export formats.",
)
async def list_export_formats() -> dict[str, list[dict[str, str]]]:
    """List all valid export formats with descriptions.

    Returns:
        Dictionary with list of formats and their descriptions
    """
    formats = [
        {
            "format": AuditExportFormat.JSON.value,
            "description": "Standard JSON format with all fields",
            "media_type": "application/json",
        },
        {
            "format": AuditExportFormat.CSV.value,
            "description": "CSV format for spreadsheet import",
            "media_type": "text/csv",
        },
        {
            "format": AuditExportFormat.HIPAA.value,
            "description": "HIPAA-compliant format with required audit fields",
            "media_type": "application/json",
        },
    ]
    return {"formats": formats}
