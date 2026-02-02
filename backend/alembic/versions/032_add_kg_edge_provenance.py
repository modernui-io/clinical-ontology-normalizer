"""Add provenance fields to kg_edges table.

Adds source tracking for knowledge graph edges:
- source_document_id: FK to documents table (where relationship was extracted from)
- extraction_method: How the relationship was extracted (nlp, manual, imported)
- extraction_confidence: Confidence in the extraction (0-1)

Revision ID: 032
Revises: 031
Create Date: 2026-02-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add provenance columns to kg_edges table."""
    # Add source_document_id with FK to documents table
    op.add_column(
        "kg_edges",
        sa.Column(
            "source_document_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # Add extraction_method column
    op.add_column(
        "kg_edges",
        sa.Column(
            "extraction_method",
            sa.String(50),
            nullable=True,
        ),
    )

    # Add extraction_confidence column
    op.add_column(
        "kg_edges",
        sa.Column(
            "extraction_confidence",
            sa.Float,
            nullable=True,
        ),
    )

    # Create index on source_document_id for efficient document -> edge lookups
    op.create_index(
        "ix_kg_edges_source_document_id",
        "kg_edges",
        ["source_document_id"],
    )


def downgrade() -> None:
    """Remove provenance columns from kg_edges table."""
    op.drop_index("ix_kg_edges_source_document_id", "kg_edges")
    op.drop_column("kg_edges", "extraction_confidence")
    op.drop_column("kg_edges", "extraction_method")
    op.drop_column("kg_edges", "source_document_id")
