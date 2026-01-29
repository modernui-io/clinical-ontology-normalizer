"""Audit logging for data access and operations.

Provides comprehensive logging for:
- Data access events (read, write, export)
- Authentication events
- Sensitive operations

This audit log should be persisted to a secure, append-only store
in production for compliance and security purposes.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional
from enum import Enum

from pydantic import BaseModel, Field

# Separate audit logger for security-critical events
audit_logger = logging.getLogger("audit")


class AuditAction(str, Enum):
    """Types of auditable actions."""

    # Data access
    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    EXPORT = "export"

    # Authentication
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"

    # System
    ERROR = "error"


class AuditEvent(BaseModel):
    """Audit event record.

    Contains all relevant context for an auditable action.
    """

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    action: AuditAction = Field(..., description="Type of action performed")
    resource_type: str = Field(..., description="Type of resource accessed")
    resource_id: str | None = Field(None, description="ID of specific resource")
    patient_id: str | None = Field(None, description="Patient ID if applicable")
    user_id: str | None = Field(None, description="User who performed action")
    ip_address: str | None = Field(None, description="Client IP address")
    details: dict[str, Any | None] = Field(None, description="Additional context")
    success: bool = Field(True, description="Whether action succeeded")


def log_audit(
    action: AuditAction,
    resource_type: str,
    resource_id: str | None = None,
    patient_id: str | None = None,
    user_id: str | None = None,
    ip_address: str | None = None,
    details: dict[str, Any | None] = None,
    success: bool = True,
) -> AuditEvent:
    """Log an audit event.

    This function should be called for all security-relevant operations.

    Args:
        action: Type of action being audited
        resource_type: The type of resource being accessed
        resource_id: Specific resource identifier
        patient_id: Patient ID if this is patient data
        user_id: User performing the action
        ip_address: Client IP address
        details: Additional context
        success: Whether the action succeeded

    Returns:
        The created AuditEvent
    """
    event = AuditEvent(
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        patient_id=patient_id,
        user_id=user_id,
        ip_address=ip_address,
        details=details,
        success=success,
    )

    # Log to audit logger
    log_level = logging.INFO if success else logging.WARNING
    audit_logger.log(
        log_level,
        f"AUDIT: {action.value} {resource_type}"
        f"{f'/{resource_id}' if resource_id else ''}"
        f"{f' patient={patient_id}' if patient_id else ''}"
        f" success={success}",
        extra={"audit_event": event.model_dump()},
    )

    return event


def log_data_access(
    resource_type: str,
    resource_id: str | None = None,
    patient_id: str | None = None,
    user_id: str | None = None,
    action: AuditAction = AuditAction.READ,
) -> AuditEvent:
    """Log a data access event.

    Convenience function for common data access auditing.

    Args:
        resource_type: Type of data being accessed
        resource_id: Specific resource ID
        patient_id: Patient the data belongs to
        user_id: User accessing the data
        action: Type of access (default: READ)

    Returns:
        The created AuditEvent
    """
    return log_audit(
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        patient_id=patient_id,
        user_id=user_id,
    )


def log_export(
    patient_id: str,
    export_type: str,
    user_id: str | None = None,
    record_count: int = 0,
) -> AuditEvent:
    """Log a data export event.

    Export events are particularly important for compliance.

    Args:
        patient_id: Patient whose data is being exported
        export_type: Type of export (e.g., "omop")
        user_id: User performing the export
        record_count: Number of records exported

    Returns:
        The created AuditEvent
    """
    return log_audit(
        action=AuditAction.EXPORT,
        resource_type="export",
        patient_id=patient_id,
        user_id=user_id,
        details={"export_type": export_type, "record_count": record_count},
    )


def log_auth_event(
    success: bool,
    user_id: str | None = None,
    ip_address: str | None = None,
    reason: str | None = None,
) -> AuditEvent:
    """Log an authentication event.

    Args:
        success: Whether authentication succeeded
        user_id: User attempting to authenticate
        ip_address: Client IP address
        reason: Reason for failure if applicable

    Returns:
        The created AuditEvent
    """
    action = AuditAction.AUTH_SUCCESS if success else AuditAction.AUTH_FAILURE
    details = {"reason": reason} if reason else None

    return log_audit(
        action=action,
        resource_type="auth",
        user_id=user_id,
        ip_address=ip_address,
        details=details,
        success=success,
    )
