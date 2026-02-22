"""Add concept_relationships columns for cross-vocabulary mapping.

Table already created in migration 011. This migration adds extra columns
(valid_start_date, valid_end_date, invalid_reason, updated_at) and additional
indexes that were not part of the original schema.

Revision ID: 014
Revises: 013
Create Date: 2026-01-18

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "014"
down_revision: str | None = "013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table: str, column: str) -> bool:
    """Check if a column already exists on a table."""
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
        sa.text(
            "SELECT 1 FROM pg_indexes WHERE indexname = :name"
        ),
        {"name": index_name},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    # Table already exists from migration 011 — add missing columns only
    new_columns = [
        ("valid_start_date", sa.String(8)),
        ("valid_end_date", sa.String(8)),
        ("invalid_reason", sa.String(1)),
        ("updated_at", sa.DateTime(timezone=True)),
    ]
    for col_name, col_type in new_columns:
        if not _column_exists("concept_relationships", col_name):
            op.add_column(
                "concept_relationships",
                sa.Column(col_name, col_type, nullable=True),
            )

    # Add indexes that don't already exist
    new_indexes = [
        ("ix_concept_relationships_source", ["concept_id_1"]),
        ("ix_concept_relationships_target", ["concept_id_2"]),
        ("ix_concept_relationships_type", ["relationship_id"]),
        ("ix_concept_relationships_mapping", ["concept_id_1", "relationship_id"]),
    ]
    for idx_name, idx_cols in new_indexes:
        if not _index_exists(idx_name):
            op.create_index(idx_name, "concept_relationships", idx_cols)


def downgrade() -> None:
    for idx_name in [
        "ix_concept_relationships_mapping",
        "ix_concept_relationships_type",
        "ix_concept_relationships_target",
        "ix_concept_relationships_source",
    ]:
        if _index_exists(idx_name):
            op.drop_index(idx_name)

    for col_name in ["updated_at", "invalid_reason", "valid_end_date", "valid_start_date"]:
        if _column_exists("concept_relationships", col_name):
            op.drop_column("concept_relationships", col_name)
