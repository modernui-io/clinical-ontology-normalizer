"""Create Policy Knowledge Graph tables.

Revision ID: 027
Revises: 026
Create Date: 2026-01-28

Creates the Policy Knowledge Graph schema:
- policy_kg_nodes: Nodes representing rules, conditions, actions, etc.
- policy_kg_edges: Relationships between policy nodes
- policy_rules: Structured IF-THEN-ELSE rules extracted from policies

This graph is separate from the patient KG and encodes clinical
decision rules for machine reasoning.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

# revision identifiers, used by Alembic.
revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create policy knowledge graph tables."""

    # Create policy_kg_nodes table
    op.create_table(
        "policy_kg_nodes",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        # Source linkage
        sa.Column(
            "policy_section_id",
            UUID(as_uuid=False),
            sa.ForeignKey("policy_sections.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        # Node identity
        sa.Column("node_type", sa.String(50), nullable=False, index=True),
        sa.Column("label", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        # Medical concept linkage
        sa.Column("omop_concept_ids", ARRAY(sa.Integer), nullable=True),
        sa.Column("snomed_codes", ARRAY(sa.String), nullable=True),
        sa.Column("icd10_codes", ARRAY(sa.String), nullable=True),
        # Evidence grading
        sa.Column("evidence_grade", sa.String(20), nullable=True),
        sa.Column("recommendation_strength", sa.String(20), nullable=True),
        # Structured rule components
        sa.Column("rule_logic", JSONB, nullable=True),
        # Temporal validity
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        # Semantic search
        sa.Column("embedding", ARRAY(sa.Float), nullable=True),
        # Confidence and provenance
        sa.Column("extraction_confidence", sa.Float, nullable=True),
        sa.Column("source_text", sa.Text, nullable=True),
    )

    # Create indexes for policy_kg_nodes
    op.create_index(
        "ix_policy_kg_nodes_type_label",
        "policy_kg_nodes",
        ["node_type", "label"],
    )
    op.create_index(
        "ix_policy_kg_nodes_effective",
        "policy_kg_nodes",
        ["effective_from", "effective_to"],
    )

    # Create policy_kg_edges table
    op.create_table(
        "policy_kg_edges",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        # Node references
        sa.Column(
            "source_node_id",
            UUID(as_uuid=False),
            sa.ForeignKey("policy_kg_nodes.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "target_node_id",
            UUID(as_uuid=False),
            sa.ForeignKey("policy_kg_nodes.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # Edge type
        sa.Column("edge_type", sa.String(50), nullable=False, index=True),
        # Properties
        sa.Column("properties", JSONB, nullable=True),
        sa.Column("conditions", JSONB, nullable=True),
        # Temporal validity
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        # Confidence
        sa.Column("confidence", sa.Float, nullable=True),
    )

    # Create indexes for policy_kg_edges
    op.create_index(
        "ix_policy_kg_edges_source_target",
        "policy_kg_edges",
        ["source_node_id", "target_node_id"],
    )
    op.create_index(
        "ix_policy_kg_edges_effective",
        "policy_kg_edges",
        ["effective_from", "effective_to"],
    )

    # Create policy_rules table (higher-level abstraction)
    op.create_table(
        "policy_rules",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        # Rule identification
        sa.Column("rule_id", sa.String(100), nullable=False, unique=True, index=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        # Source linkage
        sa.Column(
            "policy_section_id",
            UUID(as_uuid=False),
            sa.ForeignKey("policy_sections.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "policy_kg_node_id",
            UUID(as_uuid=False),
            sa.ForeignKey("policy_kg_nodes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Structured rule components
        sa.Column("if_conditions", JSONB, nullable=False),
        sa.Column("then_actions", JSONB, nullable=False),
        sa.Column("unless_exceptions", JSONB, nullable=True),
        # Medical concept applicability
        sa.Column("applies_to_conditions", ARRAY(sa.String), nullable=True),
        sa.Column("applies_to_medications", ARRAY(sa.String), nullable=True),
        sa.Column("applies_to_measurements", ARRAY(sa.String), nullable=True),
        # Evidence grading
        sa.Column("evidence_grade", sa.String(20), nullable=True),
        sa.Column("recommendation_strength", sa.String(20), nullable=True),
        # Lifecycle
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, default=True),
        # Semantic search
        sa.Column("embedding", ARRAY(sa.Float), nullable=True),
    )

    # Create indexes for policy_rules
    op.create_index(
        "ix_policy_rules_active",
        "policy_rules",
        ["is_active"],
    )
    op.create_index(
        "ix_policy_rules_effective",
        "policy_rules",
        ["effective_from", "effective_to"],
    )


def downgrade() -> None:
    """Drop policy knowledge graph tables."""
    op.drop_table("policy_rules")
    op.drop_table("policy_kg_edges")
    op.drop_table("policy_kg_nodes")
