"""Refine KGEdge temporal fields for bi-temporal model.

Revision ID: 028
Revises: 027
Create Date: 2026-01-28

Restructures temporal fields to properly capture bi-temporal model:

1. Valid Time (Event Time): When the clinical event happened
   - event_date: Point in time (e.g., "diagnosed on 2023-03-15")
   - valid_from/valid_to: Validity period (renamed from temporal_valid_from/to)

2. Transaction Time (Record Time): Provenance - when we learned about it
   - recorded_at: When recorded in source system
   - source_document_date: Date of source document

3. Temporal Assertion: From NLP extraction
   - temporality: current, past, future
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Rename and add temporal columns for bi-temporal model."""

    # Rename existing columns to simpler names
    op.alter_column("kg_edges", "temporal_valid_from", new_column_name="valid_from")
    op.alter_column("kg_edges", "temporal_valid_to", new_column_name="valid_to")

    # Add new columns for complete bi-temporal model
    op.add_column(
        "kg_edges",
        sa.Column(
            "event_date",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When this clinical event occurred (point in time)",
        ),
    )
    op.add_column(
        "kg_edges",
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When this was recorded in the source system",
        ),
    )
    op.add_column(
        "kg_edges",
        sa.Column(
            "source_document_date",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Date of the source document (note date, lab date)",
        ),
    )
    op.add_column(
        "kg_edges",
        sa.Column(
            "temporality",
            sa.String(20),
            nullable=True,
            comment="Temporal assertion: current, past, future",
        ),
    )

    # Update indexes - drop old, create new
    op.drop_index("ix_kg_edges_temporal_range", table_name="kg_edges")
    op.drop_index("ix_kg_edges_patient_temporal", table_name="kg_edges")
    op.drop_index("ix_kg_edges_temporal_valid_from", table_name="kg_edges")
    op.drop_index("ix_kg_edges_temporal_valid_to", table_name="kg_edges")

    # Create new indexes
    op.create_index("ix_kg_edges_valid_range", "kg_edges", ["valid_from", "valid_to"])
    op.create_index("ix_kg_edges_patient_valid", "kg_edges", ["patient_id", "valid_from"])
    op.create_index("ix_kg_edges_event_date", "kg_edges", ["event_date"])


def downgrade() -> None:
    """Revert to original column names."""

    # Drop new indexes
    op.drop_index("ix_kg_edges_event_date", table_name="kg_edges")
    op.drop_index("ix_kg_edges_patient_valid", table_name="kg_edges")
    op.drop_index("ix_kg_edges_valid_range", table_name="kg_edges")

    # Drop new columns
    op.drop_column("kg_edges", "temporality")
    op.drop_column("kg_edges", "source_document_date")
    op.drop_column("kg_edges", "recorded_at")
    op.drop_column("kg_edges", "event_date")

    # Rename columns back
    op.alter_column("kg_edges", "valid_from", new_column_name="temporal_valid_from")
    op.alter_column("kg_edges", "valid_to", new_column_name="temporal_valid_to")

    # Recreate old indexes
    op.create_index(
        "ix_kg_edges_temporal_valid_from", "kg_edges", ["temporal_valid_from"]
    )
    op.create_index(
        "ix_kg_edges_temporal_valid_to", "kg_edges", ["temporal_valid_to"]
    )
    op.create_index(
        "ix_kg_edges_temporal_range",
        "kg_edges",
        ["temporal_valid_from", "temporal_valid_to"],
    )
    op.create_index(
        "ix_kg_edges_patient_temporal",
        "kg_edges",
        ["patient_id", "temporal_valid_from"],
    )
