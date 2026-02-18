"""Add audit log immutability and tamper-evident hash chain.

CISO-8: Comprehensive Audit Logging Hardening
CLO-2.5: 21 CFR Part 11 Audit Trail Compliance

Changes:
1. Add actor_role column for RBAC audit correlation
2. Add record_hash and previous_hash columns for tamper-evident chain
3. Create PostgreSQL trigger to prevent UPDATE/DELETE on audit_logs
4. Add index on record_hash for chain verification queries

The immutability trigger ensures that once an audit record is written,
it cannot be modified or deleted through the application database user.
This satisfies:
- HIPAA Security Rule 164.312(b) - audit controls
- 21 CFR Part 11.10(e) - audit trails cannot be modified
- SOC 2 CC7.2 - system monitoring

Revision ID: 037
Revises: 036
Create Date: 2026-02-08

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "037"
down_revision: str | None = "036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table: str, column: str) -> bool:
    """Check if a column already exists (handles create_all schema drift)."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column"
        ),
        {"table": table, "column": column},
    )
    return result.fetchone() is not None


def _index_exists(index_name: str) -> bool:
    """Check if an index already exists."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT 1 FROM pg_indexes WHERE indexname = :name"),
        {"name": index_name},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    # --- Step 1: Add new columns to audit_logs (idempotent) ---

    # Actor role for RBAC correlation
    if not _column_exists("audit_logs", "actor_role"):
        op.add_column(
            "audit_logs",
            sa.Column("actor_role", sa.String(100), nullable=True),
        )
    if not _index_exists("ix_audit_logs_actor_role"):
        op.create_index("ix_audit_logs_actor_role", "audit_logs", ["actor_role"])

    # Tamper-evident hash chain columns
    if not _column_exists("audit_logs", "record_hash"):
        op.add_column(
            "audit_logs",
            sa.Column("record_hash", sa.String(64), nullable=True),
        )
    if not _column_exists("audit_logs", "previous_hash"):
        op.add_column(
            "audit_logs",
            sa.Column("previous_hash", sa.String(64), nullable=True),
        )
    if not _index_exists("ix_audit_logs_record_hash"):
        op.create_index("ix_audit_logs_record_hash", "audit_logs", ["record_hash"])

    # --- Step 2: Create immutability trigger ---
    # This trigger prevents any UPDATE or DELETE on the audit_logs table.
    # It fires BEFORE the operation and raises an exception, blocking the change.
    # To bypass in an emergency (e.g., data retention archival by a DBA),
    # the trigger must be explicitly disabled by a superuser:
    #   ALTER TABLE audit_logs DISABLE TRIGGER audit_log_immutable;

    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'IMMUTABLE: audit_logs records cannot be modified or deleted (HIPAA/21 CFR Part 11)';
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER audit_log_immutable
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_modification();
    """)


def downgrade() -> None:
    # Drop trigger and function
    op.execute("DROP TRIGGER IF EXISTS audit_log_immutable ON audit_logs;")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_modification();")

    # Drop indexes
    op.drop_index("ix_audit_logs_record_hash", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_role", table_name="audit_logs")

    # Drop columns
    op.drop_column("audit_logs", "previous_hash")
    op.drop_column("audit_logs", "record_hash")
    op.drop_column("audit_logs", "actor_role")
