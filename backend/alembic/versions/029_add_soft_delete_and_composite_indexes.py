"""Add soft delete columns and composite indexes.

VP-Compliance: Add deleted_at/deleted_by columns for soft delete pattern.
VP-Performance: Add composite indexes for common query patterns.

Revision ID: 029
Revises: 028_refine_kg_edge_temporal_fields
Create Date: 2026-01-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add soft delete columns and composite indexes."""
    # ==========================================================================
    # VP-Compliance: Soft Delete Columns
    # ==========================================================================

    # clinical_facts
    op.add_column(
        "clinical_facts",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "clinical_facts",
        sa.Column("deleted_by", postgresql.UUID(as_uuid=False), nullable=True),
    )
    op.create_index("ix_clinical_facts_deleted_at", "clinical_facts", ["deleted_at"])

    # documents
    op.add_column(
        "documents",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("deleted_by", postgresql.UUID(as_uuid=False), nullable=True),
    )
    op.create_index("ix_documents_deleted_at", "documents", ["deleted_at"])

    # structured_resources
    op.add_column(
        "structured_resources",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "structured_resources",
        sa.Column("deleted_by", postgresql.UUID(as_uuid=False), nullable=True),
    )
    op.create_index("ix_structured_resources_deleted_at", "structured_resources", ["deleted_at"])

    # kg_nodes
    op.add_column(
        "kg_nodes",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "kg_nodes",
        sa.Column("deleted_by", postgresql.UUID(as_uuid=False), nullable=True),
    )
    op.create_index("ix_kg_nodes_deleted_at", "kg_nodes", ["deleted_at"])

    # kg_edges
    op.add_column(
        "kg_edges",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "kg_edges",
        sa.Column("deleted_by", postgresql.UUID(as_uuid=False), nullable=True),
    )
    op.create_index("ix_kg_edges_deleted_at", "kg_edges", ["deleted_at"])

    # ==========================================================================
    # VP-Performance: Composite Indexes for clinical_facts
    # ==========================================================================

    # Patient + domain: "Get all conditions/drugs/measurements for patient"
    op.create_index(
        "ix_clinical_facts_patient_domain",
        "clinical_facts",
        ["patient_id", "domain"],
    )

    # Patient + assertion: "Get all negated findings for patient"
    op.create_index(
        "ix_clinical_facts_patient_assertion",
        "clinical_facts",
        ["patient_id", "assertion"],
    )

    # Patient + domain + assertion: "Get all positive conditions for patient"
    op.create_index(
        "ix_clinical_facts_patient_domain_assertion",
        "clinical_facts",
        ["patient_id", "domain", "assertion"],
    )

    # Patient + concept: "Get all instances of specific diagnosis for patient"
    op.create_index(
        "ix_clinical_facts_patient_concept",
        "clinical_facts",
        ["patient_id", "omop_concept_id"],
    )


def downgrade() -> None:
    """Remove soft delete columns and composite indexes."""
    # Remove composite indexes
    op.drop_index("ix_clinical_facts_patient_concept", "clinical_facts")
    op.drop_index("ix_clinical_facts_patient_domain_assertion", "clinical_facts")
    op.drop_index("ix_clinical_facts_patient_assertion", "clinical_facts")
    op.drop_index("ix_clinical_facts_patient_domain", "clinical_facts")

    # Remove soft delete from kg_edges
    op.drop_index("ix_kg_edges_deleted_at", "kg_edges")
    op.drop_column("kg_edges", "deleted_by")
    op.drop_column("kg_edges", "deleted_at")

    # Remove soft delete from kg_nodes
    op.drop_index("ix_kg_nodes_deleted_at", "kg_nodes")
    op.drop_column("kg_nodes", "deleted_by")
    op.drop_column("kg_nodes", "deleted_at")

    # Remove soft delete from structured_resources
    op.drop_index("ix_structured_resources_deleted_at", "structured_resources")
    op.drop_column("structured_resources", "deleted_by")
    op.drop_column("structured_resources", "deleted_at")

    # Remove soft delete from documents
    op.drop_index("ix_documents_deleted_at", "documents")
    op.drop_column("documents", "deleted_by")
    op.drop_column("documents", "deleted_at")

    # Remove soft delete from clinical_facts
    op.drop_index("ix_clinical_facts_deleted_at", "clinical_facts")
    op.drop_column("clinical_facts", "deleted_by")
    op.drop_column("clinical_facts", "deleted_at")
