"""SQLAlchemy models for HIPAA-compliant audit trail logging.

Provides comprehensive audit logging for all PHI access and data operations,
supporting HIPAA compliance requirements for healthcare data handling.

Models:
- AuditLog: Individual audit trail entries for all data access/modification
- AuditExport: Records of audit log exports for compliance reporting
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import Boolean, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditAction(str, Enum):
    """Types of auditable actions."""

    # Data access actions
    READ = "read"
    SEARCH = "search"
    EXPORT = "export"
    DOWNLOAD = "download"

    # Data modification actions
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"

    # Authentication/authorization actions
    LOGIN = "login"
    LOGOUT = "logout"
    AUTH_FAILURE = "auth_failure"

    # System actions
    SYSTEM_ACCESS = "system_access"
    CONFIG_CHANGE = "config_change"


class AuditResourceType(str, Enum):
    """Types of resources that can be audited."""

    DOCUMENT = "document"
    PATIENT = "patient"
    CLINICAL_FACT = "clinical_fact"
    MENTION = "mention"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    VOCABULARY = "vocabulary"
    FHIR_RESOURCE = "fhir_resource"
    STRUCTURED_RESOURCE = "structured_resource"
    USER = "user"
    SYSTEM = "system"
    AUDIT_LOG = "audit_log"
    REPORT = "report"


class AuditExportStatus(str, Enum):
    """Status of audit export jobs."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AuditExportFormat(str, Enum):
    """Supported audit export formats."""

    JSON = "json"
    CSV = "csv"
    HIPAA = "hipaa"  # HIPAA-required format with specific fields


class AuditLog(Base):
    """Audit trail entry for tracking all data access and modifications.

    HIPAA requires tracking of:
    - Who accessed the data (user_id)
    - When the access occurred (timestamp)
    - What data was accessed (resource_type, resource_id)
    - What action was performed (action)
    - From where (ip_address)
    - Whether PHI was involved (phi_accessed)

    This model captures all required information plus additional context
    for security monitoring and compliance reporting.
    """

    __tablename__ = "audit_logs"

    # Timestamp of the action (overrides Base.created_at for explicit naming)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    # User identification
    user_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,  # May be null for unauthenticated requests
        index=True,
    )

    # Action performed
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    # Resource information
    resource_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    resource_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,  # May be null for collection-level access
        index=True,
    )

    # Request context
    ip_address: Mapped[str | None] = mapped_column(
        String(45),  # IPv6 max length
        nullable=True,
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    request_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    # Request/response details
    request_method: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )
    request_path: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )
    response_status: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    # Additional context (JSON)
    details: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
    )

    # PHI tracking - critical for HIPAA
    phi_accessed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )

    # Patient ID if applicable (for PHI correlation)
    patient_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    # Session tracking
    session_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    # Outcome/status
    success: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Composite indexes for common query patterns
    __table_args__ = (
        Index("ix_audit_logs_user_timestamp", "user_id", "timestamp"),
        Index("ix_audit_logs_resource_timestamp", "resource_type", "resource_id", "timestamp"),
        Index("ix_audit_logs_phi_timestamp", "phi_accessed", "timestamp"),
        Index("ix_audit_logs_patient_timestamp", "patient_id", "timestamp"),
        Index("ix_audit_logs_action_timestamp", "action", "timestamp"),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id}, timestamp={self.timestamp}, "
            f"user_id={self.user_id}, action={self.action}, "
            f"resource_type={self.resource_type}, phi_accessed={self.phi_accessed})>"
        )


class AuditExport(Base):
    """Record of audit log exports for compliance reporting.

    Tracks when audit logs were exported, by whom, and for what date range.
    This provides an audit trail of the audit trail itself, which may be
    required for compliance verification.
    """

    __tablename__ = "audit_exports"

    # Export date range
    export_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    end_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Export file information
    file_path: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )
    file_size_bytes: Mapped[int | None] = mapped_column(
        nullable=True,
    )
    record_count: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    # Export format
    format: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="json",
    )

    # Status tracking
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Who requested the export
    requested_by: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    # Export filters (JSON)
    filters: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
    )

    # Checksum for integrity verification
    checksum: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    # Processing timestamps
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"<AuditExport(id={self.id}, export_date={self.export_date}, "
            f"start_date={self.start_date}, end_date={self.end_date}, "
            f"status={self.status}, requested_by={self.requested_by})>"
        )
