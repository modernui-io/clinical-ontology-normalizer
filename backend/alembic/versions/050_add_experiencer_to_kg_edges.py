"""Add experiencer column to kg_edges.

Promotes experiencer from unstructured JSON properties dict to a
proper queryable column on kg_edges, reusing the existing
experiencer_type PostgreSQL enum (already created by ClinicalFact).

Backfills existing rows from properties->>'experiencer'.

Revision ID: 050
Revises: 049
Create Date: 2026-02-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "050"
down_revision = "049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add experiencer column and backfill from properties JSON."""
    # Add the column using the existing experiencer_type enum
    op.add_column(
        "kg_edges",
        sa.Column(
            "experiencer",
            sa.Enum(
                "patient", "family", "other",
                name="experiencer_type",
                create_type=False,
            ),
            nullable=True,
        ),
    )
    op.create_index("ix_kg_edges_experiencer", "kg_edges", ["experiencer"])

    # Backfill from properties->>'experiencer' for existing rows
    op.execute(
        """
        UPDATE kg_edges
        SET experiencer = (properties->>'experiencer')::experiencer_type
        WHERE properties->>'experiencer' IS NOT NULL
          AND experiencer IS NULL
        """
    )


def downgrade() -> None:
    """Remove experiencer column."""
    op.drop_index("ix_kg_edges_experiencer", table_name="kg_edges")
    op.drop_column("kg_edges", "experiencer")
