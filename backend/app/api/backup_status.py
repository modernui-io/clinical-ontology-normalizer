"""Backup status and RPO compliance API endpoints (COO-1).

Provides operational endpoints for monitoring backup health and
RPO compliance across all critical systems.

Endpoints:
    GET /api/v1/ops/backup-status   - Full backup verification report
    GET /api/v1/ops/rpo-compliance  - RPO compliance check per system
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.backup_verification_service import (
    BackupStatus,
    BackupType,
    ComplianceStatus,
    get_backup_verification_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ops", tags=["Operations"])


# ============================================================================
# Response Models
# ============================================================================


class RPOComplianceResponse(BaseModel):
    """RPO compliance entry for a single backup type."""

    backup_type: str = Field(description="Type of backup")
    status: str = Field(description="Compliance status: compliant, warning, violation, unknown")
    rpo_window_hours: float = Field(description="Configured RPO window in hours")
    last_backup_age_hours: float | None = Field(
        description="Hours since last backup, or null if no backup exists"
    )
    last_backup_timestamp: datetime | None = Field(
        description="Timestamp of last backup, or null"
    )
    next_required_by: datetime | None = Field(
        description="When next backup is required to maintain RPO compliance"
    )
    message: str = Field(description="Human-readable compliance message")


class BackupStatusResponse(BaseModel):
    """Full backup verification report."""

    generated_at: datetime = Field(description="When this report was generated")
    overall_status: str = Field(description="Overall status: healthy, degraded, critical")
    total_backups_tracked: int = Field(description="Total number of backups in registry")
    compliance_entries: list[RPOComplianceResponse] = Field(
        description="RPO compliance status per backup type"
    )
    recent_backups: list[dict[str, Any]] = Field(
        description="Most recent backups across all types"
    )
    alerts: list[str] = Field(description="Active alerts and warnings")
    summary: str = Field(description="Human-readable summary")


class RPOComplianceReport(BaseModel):
    """RPO compliance report across all systems."""

    generated_at: datetime
    overall_compliant: bool = Field(description="True if all systems are compliant")
    violation_count: int = Field(description="Number of RPO violations")
    warning_count: int = Field(description="Number of RPO warnings")
    entries: list[RPOComplianceResponse]


# ============================================================================
# Endpoints
# ============================================================================


@router.get(
    "/backup-status",
    response_model=BackupStatusResponse,
    summary="Get backup verification report",
    description=(
        "Returns a comprehensive backup verification report including "
        "RPO compliance status, recent backup history, and active alerts. "
        "Use this endpoint for operational monitoring dashboards."
    ),
)
async def get_backup_status() -> BackupStatusResponse:
    """Get current backup verification report."""
    service = get_backup_verification_service()
    report = service.verify_backup_status()

    return BackupStatusResponse(
        generated_at=report.generated_at,
        overall_status=report.overall_status.value,
        total_backups_tracked=report.total_backups_tracked,
        compliance_entries=[
            RPOComplianceResponse(
                backup_type=e.backup_type.value,
                status=e.status.value,
                rpo_window_hours=e.rpo_window_hours,
                last_backup_age_hours=e.last_backup_age_hours,
                last_backup_timestamp=e.last_backup_timestamp,
                next_required_by=e.next_required_by,
                message=e.message,
            )
            for e in report.compliance_entries
        ],
        recent_backups=report.recent_backups,
        alerts=report.alerts,
        summary=report.summary,
    )


@router.get(
    "/rpo-compliance",
    response_model=RPOComplianceReport,
    summary="Check RPO compliance",
    description=(
        "Returns RPO compliance status for each backup type. "
        "Shows whether each system's backups are within the configured "
        "Recovery Point Objective window."
    ),
)
async def get_rpo_compliance() -> RPOComplianceReport:
    """Check RPO compliance across all systems."""
    service = get_backup_verification_service()
    entries = service.check_rpo_compliance()

    violation_count = sum(1 for e in entries if e.status == ComplianceStatus.VIOLATION)
    warning_count = sum(1 for e in entries if e.status == ComplianceStatus.WARNING)
    # Overall compliant only if no violations and no unknowns
    overall_compliant = all(
        e.status in (ComplianceStatus.COMPLIANT, ComplianceStatus.WARNING)
        for e in entries
    )

    now = datetime.now(timezone.utc)

    return RPOComplianceReport(
        generated_at=now,
        overall_compliant=overall_compliant,
        violation_count=violation_count,
        warning_count=warning_count,
        entries=[
            RPOComplianceResponse(
                backup_type=e.backup_type.value,
                status=e.status.value,
                rpo_window_hours=e.rpo_window_hours,
                last_backup_age_hours=e.last_backup_age_hours,
                last_backup_timestamp=e.last_backup_timestamp,
                next_required_by=e.next_required_by,
                message=e.message,
            )
            for e in entries
        ],
    )
