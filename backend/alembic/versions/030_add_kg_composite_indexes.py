"""Add composite indexes to knowledge graph tables.

VP-Performance-1: Add composite indexes for common KG query patterns.

These indexes optimize:
- Node lookups by patient + type (most common query)
- Node lookups by patient + concept ID
- Edge lookups by patient + edge type
- Edge lookups by source/target node + type

Revision ID: 030
Revises: 029
Create Date: 2026-01-29
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add composite indexes to kg_nodes and kg_edges."""
    # ==========================================================================
    # VP-Performance-1: KGNode Composite Indexes
    # ==========================================================================

    # Patient + node_type: "Get all conditions/drugs/measurements for patient"
    op.create_index(
        "ix_kg_nodes_patient_type",
        "kg_nodes",
        ["patient_id", "node_type"],
    )

    # Patient + concept: "Get nodes by patient and OMOP concept"
    op.create_index(
        "ix_kg_nodes_patient_concept",
        "kg_nodes",
        ["patient_id", "omop_concept_id"],
    )

    # Node type + concept: "Find all diabetes (concept) nodes across patients"
    op.create_index(
        "ix_kg_nodes_type_concept",
        "kg_nodes",
        ["node_type", "omop_concept_id"],
    )

    # ==========================================================================
    # VP-Performance-1: KGEdge Composite Indexes
    # ==========================================================================

    # Patient + edge_type: "Get all 'takes_drug' edges for patient"
    op.create_index(
        "ix_kg_edges_patient_type",
        "kg_edges",
        ["patient_id", "edge_type"],
    )

    # Source node + edge_type: "Get all outgoing edges of type X from node"
    op.create_index(
        "ix_kg_edges_source_type",
        "kg_edges",
        ["source_node_id", "edge_type"],
    )

    # Target node + edge_type: "Get all incoming edges of type X to node"
    op.create_index(
        "ix_kg_edges_target_type",
        "kg_edges",
        ["target_node_id", "edge_type"],
    )


def downgrade() -> None:
    """Remove composite indexes from kg_nodes and kg_edges."""
    # Remove KGEdge indexes
    op.drop_index("ix_kg_edges_target_type", "kg_edges")
    op.drop_index("ix_kg_edges_source_type", "kg_edges")
    op.drop_index("ix_kg_edges_patient_type", "kg_edges")

    # Remove KGNode indexes
    op.drop_index("ix_kg_nodes_type_concept", "kg_nodes")
    op.drop_index("ix_kg_nodes_patient_concept", "kg_nodes")
    op.drop_index("ix_kg_nodes_patient_type", "kg_nodes")
