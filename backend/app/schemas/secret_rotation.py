"""Pydantic schemas for Secret Rotation framework (DEVOPS-4).

Provides request/response models for the secret rotation API including:
- SecretMetadata: masked secret information for API responses
- SecretComplianceReport: rotation compliance status per secret
- RotationAuditEntry: audit trail for rotation events
- Response wrappers for list, compliance, and audit endpoints
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class SecretType(str, Enum):
    """Types of managed secrets."""

    DB_CREDENTIAL = "DB_CREDENTIAL"
    API_KEY = "API_KEY"
    JWT_SECRET = "JWT_SECRET"
    ENCRYPTION_KEY = "ENCRYPTION_KEY"
    WEBHOOK_SECRET = "WEBHOOK_SECRET"


class RotationStatus(str, Enum):
    """Status of a secret's rotation compliance."""

    CURRENT = "CURRENT"
    DUE_SOON = "DUE_SOON"
    OVERDUE = "OVERDUE"
    NEVER_ROTATED = "NEVER_ROTATED"


class SecretMetadata(BaseModel):
    """Masked secret metadata for API responses.

    Raw values are NEVER exposed -- only first/last 4 chars are shown.
    """

    name: str = Field(..., description="Unique secret name")
    secret_type: SecretType = Field(..., description="Type of secret")
    masked_value: str = Field(..., description="Masked current value (e.g., 'abcd...wxyz')")
    has_previous: bool = Field(False, description="Whether a previous value exists (grace period)")
    created_at: datetime = Field(..., description="When the secret was first created")
    rotated_at: datetime | None = Field(None, description="When the secret was last rotated")
    expires_at: datetime | None = Field(None, description="When the current value expires")
    rotation_interval_days: int = Field(..., description="Rotation interval in days")
    grace_period_minutes: int = Field(..., description="Dual-read grace period in minutes")


class SecretComplianceReport(BaseModel):
    """Compliance status for a single secret."""

    name: str = Field(..., description="Secret name")
    secret_type: SecretType = Field(..., description="Type of secret")
    status: RotationStatus = Field(..., description="Current rotation compliance status")
    last_rotated: datetime | None = Field(None, description="Last rotation timestamp")
    next_rotation_due: datetime | None = Field(None, description="When rotation is next due")
    days_until_rotation: int | None = Field(None, description="Days until rotation is due (negative if overdue)")
    rotation_interval_days: int = Field(..., description="Configured rotation interval")


class RotationAuditEntry(BaseModel):
    """Audit trail entry for a rotation event."""

    id: str = Field(..., description="Unique audit entry ID")
    secret_name: str = Field(..., description="Name of the rotated secret")
    secret_type: SecretType = Field(..., description="Type of the rotated secret")
    action: str = Field(..., description="Action performed (e.g., 'rotated', 'created', 'previous_cleared')")
    initiated_by: str = Field(..., description="Who or what triggered the rotation")
    reason: str = Field("", description="Reason for the rotation")
    timestamp: datetime = Field(..., description="When the action occurred")
    metadata: dict = Field(default_factory=dict, description="Additional event metadata")


class RotateSecretRequest(BaseModel):
    """Request body for manual secret rotation."""

    reason: str = Field("manual_rotation", description="Reason for rotation")
    initiated_by: str = Field("admin", description="Who initiated the rotation")


class SecretListResponse(BaseModel):
    """Response for listing all managed secrets."""

    secrets: list[SecretMetadata] = Field(default_factory=list)
    total: int = Field(0, description="Total number of managed secrets")


class ComplianceResponse(BaseModel):
    """Response for compliance report."""

    reports: list[SecretComplianceReport] = Field(default_factory=list)
    total: int = Field(0)
    overdue_count: int = Field(0, description="Number of overdue secrets")
    due_soon_count: int = Field(0, description="Number of secrets due for rotation within 30 days")
    compliant_count: int = Field(0, description="Number of compliant secrets")


class AuditLogResponse(BaseModel):
    """Response for audit log."""

    entries: list[RotationAuditEntry] = Field(default_factory=list)
    total: int = Field(0)


class AutoRotationResult(BaseModel):
    """Result of running auto-rotation check."""

    checked: int = Field(0, description="Number of secrets checked")
    rotated: list[str] = Field(default_factory=list, description="Names of secrets that were rotated")
    errors: list[str] = Field(default_factory=list, description="Any errors during rotation")
    timestamp: datetime = Field(..., description="When the check was run")
