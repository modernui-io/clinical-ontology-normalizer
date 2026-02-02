"""Add provenance fields to kg_nodes table.

Adds source tracking for knowledge graph nodes:
- source_document_id: FK to documents table (where entity was extracted from)
- extraction_method: How the entity was extracted (nlp, manual, imported)
- extraction_confidence: Confidence in the extraction (0-1)

Revision ID: 031
Revises: 030
Create Date: 2026-02-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add provenance columns to kg_nodes table."""
    # Add source_document_id with FK to documents table
    op.add_column(
        "kg_nodes",
        sa.Column(
            "source_document_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # Add extraction_method column
    op.add_column(
        "kg_nodes",
        sa.Column(
            "extraction_method",
            sa.String(50),
            nullable=True,
        ),
    )

    # Add extraction_confidence column
    op.add_column(
        "kg_nodes",
        sa.Column(
            "extraction_confidence",
            sa.Float,
            nullable=True,
        ),
    )

    # Create index on source_document_id for efficient document -> node lookups
    op.create_index(
        "ix_kg_nodes_source_document_id",
        "kg_nodes",
        ["source_document_id"],
    )


def downgrade() -> None:
    """Remove provenance columns from kg_nodes table."""
    op.drop_index("ix_kg_nodes_source_document_id", "kg_nodes")
    op.drop_column("kg_nodes", "extraction_confidence")
    op.drop_column("kg_nodes", "extraction_method")
    op.drop_column("kg_nodes", "source_document_id")
