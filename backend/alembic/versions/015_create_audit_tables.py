"""Create audit_logs and audit_exports tables for HIPAA compliance.

Revision ID: 015
Revises: 014
Create Date: 2026-01-18

This migration creates tables for HIPAA-compliant audit trail logging:
- audit_logs: Tracks all data access and modifications
- audit_exports: Tracks audit log export requests

HIPAA requires:
- Date and time of access
- User identification
- Type of action
- Patient identification (when applicable)
- Description of information accessed
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "015"
down_revision: str | None = "014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create audit_logs table
    op.create_table(
        "audit_logs",
        # Primary key (inherited from Base)
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # Timestamp of the action
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        # User identification
        sa.Column("user_id", sa.String(255), nullable=True),
        # Action performed
        sa.Column("action", sa.String(50), nullable=False),
        # Resource information
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.String(255), nullable=True),
        # Request context
        sa.Column("ip_address", sa.String(45), nullable=True),  # IPv6 max length
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("request_id", sa.String(100), nullable=True),
        sa.Column("request_method", sa.String(10), nullable=True),
        sa.Column("request_path", sa.String(1000), nullable=True),
        sa.Column("response_status", sa.Integer(), nullable=True),
        # Additional details (JSON)
        sa.Column("details", postgresql.JSONB(), nullable=True),
        # PHI tracking - critical for HIPAA
        sa.Column("phi_accessed", sa.Boolean(), nullable=False, default=False),
        # Patient ID if applicable
        sa.Column("patient_id", sa.String(255), nullable=True),
        # Session tracking
        sa.Column("session_id", sa.String(255), nullable=True),
        # Outcome/status
        sa.Column("success", sa.Boolean(), nullable=False, default=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )

    # Create indexes for audit_logs
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_resource_type", "audit_logs", ["resource_type"])
    op.create_index("ix_audit_logs_resource_id", "audit_logs", ["resource_id"])
    op.create_index("ix_audit_logs_request_id", "audit_logs", ["request_id"])
    op.create_index("ix_audit_logs_phi_accessed", "audit_logs", ["phi_accessed"])
    op.create_index("ix_audit_logs_patient_id", "audit_logs", ["patient_id"])
    op.create_index("ix_audit_logs_session_id", "audit_logs", ["session_id"])

    # Create composite indexes for common query patterns
    op.create_index(
        "ix_audit_logs_user_timestamp",
        "audit_logs",
        ["user_id", "timestamp"],
    )
    op.create_index(
        "ix_audit_logs_resource_timestamp",
        "audit_logs",
        ["resource_type", "resource_id", "timestamp"],
    )
    op.create_index(
        "ix_audit_logs_phi_timestamp",
        "audit_logs",
        ["phi_accessed", "timestamp"],
    )
    op.create_index(
        "ix_audit_logs_patient_timestamp",
        "audit_logs",
        ["patient_id", "timestamp"],
    )
    op.create_index(
        "ix_audit_logs_action_timestamp",
        "audit_logs",
        ["action", "timestamp"],
    )

    # Create audit_exports table
    op.create_table(
        "audit_exports",
        # Primary key (inherited from Base)
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # Export date range
        sa.Column("export_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=False),
        # Export file information
        sa.Column("file_path", sa.String(1000), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("record_count", sa.Integer(), nullable=True),
        # Export format
        sa.Column("format", sa.String(20), nullable=False, default="json"),
        # Status tracking
        sa.Column("status", sa.String(20), nullable=False, default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        # Who requested the export
        sa.Column("requested_by", sa.String(255), nullable=True),
        # Export filters (JSON)
        sa.Column("filters", postgresql.JSONB(), nullable=True),
        # Checksum for integrity verification
        sa.Column("checksum", sa.String(128), nullable=True),
        # Processing timestamps
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Create indexes for audit_exports
    op.create_index("ix_audit_exports_export_date", "audit_exports", ["export_date"])
    op.create_index("ix_audit_exports_status", "audit_exports", ["status"])
    op.create_index("ix_audit_exports_requested_by", "audit_exports", ["requested_by"])


def downgrade() -> None:
    # Drop audit_exports indexes
    op.drop_index("ix_audit_exports_requested_by")
    op.drop_index("ix_audit_exports_status")
    op.drop_index("ix_audit_exports_export_date")

    # Drop audit_exports table
    op.drop_table("audit_exports")

    # Drop audit_logs composite indexes
    op.drop_index("ix_audit_logs_action_timestamp")
    op.drop_index("ix_audit_logs_patient_timestamp")
    op.drop_index("ix_audit_logs_phi_timestamp")
    op.drop_index("ix_audit_logs_resource_timestamp")
    op.drop_index("ix_audit_logs_user_timestamp")

    # Drop audit_logs single-column indexes
    op.drop_index("ix_audit_logs_session_id")
    op.drop_index("ix_audit_logs_patient_id")
    op.drop_index("ix_audit_logs_phi_accessed")
    op.drop_index("ix_audit_logs_request_id")
    op.drop_index("ix_audit_logs_resource_id")
    op.drop_index("ix_audit_logs_resource_type")
    op.drop_index("ix_audit_logs_action")
    op.drop_index("ix_audit_logs_user_id")
    op.drop_index("ix_audit_logs_timestamp")

    # Drop audit_logs table
    op.drop_table("audit_logs")
