"""Add temporal fields to kg_edges table.

Revision ID: 026
Revises: 025
Create Date: 2026-01-28

Adds bi-temporal support to knowledge graph edges:
- temporal_valid_from: When relationship became valid
- temporal_valid_to: When relationship ceased to be valid
- temporal_order: Allen's interval algebra relationship
- temporal_confidence: Confidence in temporal assertions

Also adds indexes for efficient temporal range queries.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add temporal columns and indexes to kg_edges."""
    # Add temporal columns
    op.add_column(
        "kg_edges",
        sa.Column(
            "temporal_valid_from",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When this relationship became valid in real world",
        ),
    )
    op.add_column(
        "kg_edges",
        sa.Column(
            "temporal_valid_to",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When this relationship ceased to be valid (null = ongoing)",
        ),
    )
    op.add_column(
        "kg_edges",
        sa.Column(
            "temporal_order",
            sa.String(20),
            nullable=True,
            comment="Temporal ordering: before, after, during, concurrent, etc.",
        ),
    )
    op.add_column(
        "kg_edges",
        sa.Column(
            "temporal_confidence",
            sa.Float(),
            nullable=True,
            comment="Confidence in temporal assertions (0-1)",
        ),
    )

    # Add indexes for temporal queries
    op.create_index(
        "ix_kg_edges_temporal_valid_from",
        "kg_edges",
        ["temporal_valid_from"],
        unique=False,
    )
    op.create_index(
        "ix_kg_edges_temporal_valid_to",
        "kg_edges",
        ["temporal_valid_to"],
        unique=False,
    )
    op.create_index(
        "ix_kg_edges_temporal_range",
        "kg_edges",
        ["temporal_valid_from", "temporal_valid_to"],
        unique=False,
    )
    op.create_index(
        "ix_kg_edges_patient_temporal",
        "kg_edges",
        ["patient_id", "temporal_valid_from"],
        unique=False,
    )


def downgrade() -> None:
    """Remove temporal columns and indexes from kg_edges."""
    # Drop indexes
    op.drop_index("ix_kg_edges_patient_temporal", table_name="kg_edges")
    op.drop_index("ix_kg_edges_temporal_range", table_name="kg_edges")
    op.drop_index("ix_kg_edges_temporal_valid_to", table_name="kg_edges")
    op.drop_index("ix_kg_edges_temporal_valid_from", table_name="kg_edges")

    # Drop columns
    op.drop_column("kg_edges", "temporal_confidence")
    op.drop_column("kg_edges", "temporal_order")
    op.drop_column("kg_edges", "temporal_valid_to")
    op.drop_column("kg_edges", "temporal_valid_from")
