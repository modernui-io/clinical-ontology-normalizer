"""Add pipeline_version column to clinical_facts.

CSO-1: Pipeline Reproducibility / Version Pinning.
Every ClinicalFact now records which pipeline version produced it,
enabling "show me all facts produced by pipeline v1.0 vs v1.1"
queries and full reproducibility audits.

The column is nullable for backward compatibility with existing rows.

Revision ID: 038
Revises: 037
Create Date: 2026-02-08

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "038"
down_revision: str | None = "037"
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
    # Add pipeline_version column (nullable for backward compat, idempotent)
    if not _column_exists("clinical_facts", "pipeline_version"):
        op.add_column(
            "clinical_facts",
            sa.Column("pipeline_version", sa.String(100), nullable=True),
        )
    # Index for querying facts by pipeline version
    if not _index_exists("ix_clinical_facts_pipeline_version"):
        op.create_index(
            "ix_clinical_facts_pipeline_version",
            "clinical_facts",
            ["pipeline_version"],
        )


def downgrade() -> None:
    op.drop_index("ix_clinical_facts_pipeline_version", table_name="clinical_facts")
    op.drop_column("clinical_facts", "pipeline_version")
