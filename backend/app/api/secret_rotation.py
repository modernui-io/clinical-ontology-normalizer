"""Secret Rotation API endpoints (DEVOPS-4).

Admin-only endpoints for managing secret lifecycle, triggering rotations,
checking compliance, and viewing audit trails.

Endpoints:
    GET  /api/v1/admin/secrets               - List all managed secrets (masked)
    GET  /api/v1/admin/secrets/compliance     - Compliance report
    GET  /api/v1/admin/secrets/audit-log      - Rotation audit trail
    POST /api/v1/admin/secrets/check-schedule - Run auto-rotation check
    GET  /api/v1/admin/secrets/{name}         - Secret metadata (no raw value)
    POST /api/v1/admin/secrets/{name}/rotate  - Trigger manual rotation
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.schemas.secret_rotation import (
    AuditLogResponse,
    AutoRotationResult,
    ComplianceResponse,
    RotateSecretRequest,
    RotationAuditEntry as AuditEntrySchema,
    SecretComplianceReport,
    SecretListResponse,
    SecretMetadata,
    SecretType as SchemaSecretType,
    RotationStatus,
)
from app.services.secret_rotation_service import (
    SecretRotationService,
    get_secret_rotation_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/secrets", tags=["Secret Rotation"])


def _get_service() -> SecretRotationService:
    """Retrieve the singleton service."""
    return get_secret_rotation_service()


# ---------------------------------------------------------------------------
# GET /admin/secrets
# ---------------------------------------------------------------------------


@router.get("", response_model=SecretListResponse)
async def list_secrets() -> SecretListResponse:
    """List all managed secrets with masked values."""
    service = _get_service()
    secrets = service.list_secrets()
    items = [
        SecretMetadata(
            name=s["name"],
            secret_type=SchemaSecretType(s["secret_type"]),
            masked_value=s["masked_value"],
            has_previous=s["has_previous"],
            created_at=s["created_at"],
            rotated_at=s.get("rotated_at"),
            expires_at=s.get("expires_at"),
            rotation_interval_days=s["rotation_interval_days"],
            grace_period_minutes=s["grace_period_minutes"],
        )
        for s in secrets
    ]
    return SecretListResponse(secrets=items, total=len(items))


# ---------------------------------------------------------------------------
# GET /admin/secrets/compliance
# ---------------------------------------------------------------------------


@router.get("/compliance", response_model=ComplianceResponse)
async def get_compliance() -> ComplianceResponse:
    """Get compliance report for all managed secrets."""
    service = _get_service()
    report = service.get_compliance_report()
    items = [
        SecretComplianceReport(
            name=r["name"],
            secret_type=SchemaSecretType(r["secret_type"]),
            status=RotationStatus(r["status"]),
            last_rotated=r.get("last_rotated"),
            next_rotation_due=r.get("next_rotation_due"),
            days_until_rotation=r.get("days_until_rotation"),
            rotation_interval_days=r["rotation_interval_days"],
        )
        for r in report["reports"]
    ]
    return ComplianceResponse(
        reports=items,
        total=report["total"],
        overdue_count=report["overdue_count"],
        due_soon_count=report["due_soon_count"],
        compliant_count=report["compliant_count"],
    )


# ---------------------------------------------------------------------------
# GET /admin/secrets/audit-log
# ---------------------------------------------------------------------------


@router.get("/audit-log", response_model=AuditLogResponse)
async def get_audit_log(
    secret_name: str | None = None,
    limit: int = 100,
) -> AuditLogResponse:
    """Get rotation audit trail, optionally filtered by secret name."""
    service = _get_service()
    entries = service.get_audit_log(secret_name=secret_name, limit=limit)
    items = [
        AuditEntrySchema(
            id=e["id"],
            secret_name=e["secret_name"],
            secret_type=SchemaSecretType(e["secret_type"]),
            action=e["action"],
            initiated_by=e["initiated_by"],
            reason=e["reason"],
            timestamp=e["timestamp"],
            metadata=e.get("metadata", {}),
        )
        for e in entries
    ]
    return AuditLogResponse(entries=items, total=len(items))


# ---------------------------------------------------------------------------
# POST /admin/secrets/check-schedule
# ---------------------------------------------------------------------------


@router.post("/check-schedule", response_model=AutoRotationResult)
async def check_schedule() -> AutoRotationResult:
    """Run auto-rotation check across all managed secrets."""
    service = _get_service()
    result = service.check_and_rotate(initiated_by="admin_scheduled")
    return AutoRotationResult(
        checked=result["checked"],
        rotated=result["rotated"],
        errors=result["errors"],
        timestamp=result["timestamp"],
    )


# ---------------------------------------------------------------------------
# GET /admin/secrets/{name}
# ---------------------------------------------------------------------------


@router.get("/{name}", response_model=SecretMetadata)
async def get_secret(name: str) -> SecretMetadata:
    """Get metadata for a single secret (no raw value exposed)."""
    service = _get_service()
    meta = service.get_secret_metadata(name)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"Secret '{name}' not found")
    return SecretMetadata(
        name=meta["name"],
        secret_type=SchemaSecretType(meta["secret_type"]),
        masked_value=meta["masked_value"],
        has_previous=meta["has_previous"],
        created_at=meta["created_at"],
        rotated_at=meta.get("rotated_at"),
        expires_at=meta.get("expires_at"),
        rotation_interval_days=meta["rotation_interval_days"],
        grace_period_minutes=meta["grace_period_minutes"],
    )


# ---------------------------------------------------------------------------
# POST /admin/secrets/{name}/rotate
# ---------------------------------------------------------------------------


@router.post("/{name}/rotate", response_model=SecretMetadata)
async def rotate_secret(name: str, body: RotateSecretRequest | None = None) -> SecretMetadata:
    """Trigger manual rotation for a secret."""
    service = _get_service()
    req = body or RotateSecretRequest()
    record = service.rotate_secret(
        name,
        initiated_by=req.initiated_by,
        reason=req.reason,
    )
    if record is None:
        raise HTTPException(status_code=404, detail=f"Secret '{name}' not found")

    meta = service.get_secret_metadata(name)
    assert meta is not None
    return SecretMetadata(
        name=meta["name"],
        secret_type=SchemaSecretType(meta["secret_type"]),
        masked_value=meta["masked_value"],
        has_previous=meta["has_previous"],
        created_at=meta["created_at"],
        rotated_at=meta.get("rotated_at"),
        expires_at=meta.get("expires_at"),
        rotation_interval_days=meta["rotation_interval_days"],
        grace_period_minutes=meta["grace_period_minutes"],
    )
