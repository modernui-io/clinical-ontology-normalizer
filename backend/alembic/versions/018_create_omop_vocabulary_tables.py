"""Create OMOP Vocabulary reference tables.

Revision ID: 018
Revises: 017
Create Date: 2026-01-24

This migration creates the OMOP CDM v5.4 Vocabulary reference tables.
These tables provide standardized terminology and concept definitions
for the clinical data stored in the OMOP CDM tables.

Reference: https://ohdsi.github.io/CommonDataModel/cdm54.html#Vocabulary_Tables

Tables Created (8 total):
    - concept: Standard concepts across all vocabularies
    - vocabulary: Registered vocabularies (SNOMED, ICD-10, RxNorm, etc.)
    - domain: Concept domain assignments (Condition, Drug, Procedure, etc.)
    - concept_class: Concept classification within vocabularies
    - concept_relationship: Relationships between concepts
    - relationship: Relationship type definitions
    - concept_synonym: Multilingual concept synonyms
    - concept_ancestor: Hierarchical ancestor/descendant relationships
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "018"
down_revision: str | None = "017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ==========================================================================
    # Vocabulary Reference Tables
    # ==========================================================================

    # Create vocabulary table (must be created before concept for FK)
    op.create_table(
        "omop_vocabulary",
        sa.Column("vocabulary_id", sa.String(20), primary_key=True),
        sa.Column("vocabulary_name", sa.String(255), nullable=False),
        sa.Column("vocabulary_reference", sa.String(255), nullable=True),
        sa.Column("vocabulary_version", sa.String(255), nullable=True),
        sa.Column("vocabulary_concept_id", sa.Integer(), nullable=False),
    )

    # Create domain table
    op.create_table(
        "omop_domain",
        sa.Column("domain_id", sa.String(20), primary_key=True),
        sa.Column("domain_name", sa.String(255), nullable=False),
        sa.Column("domain_concept_id", sa.Integer(), nullable=False),
    )

    # Create concept_class table
    op.create_table(
        "omop_concept_class",
        sa.Column("concept_class_id", sa.String(20), primary_key=True),
        sa.Column("concept_class_name", sa.String(255), nullable=False),
        sa.Column("concept_class_concept_id", sa.Integer(), nullable=False),
    )

    # Create relationship table (must be created before concept_relationship for FK)
    op.create_table(
        "omop_relationship",
        sa.Column("relationship_id", sa.String(20), primary_key=True),
        sa.Column("relationship_name", sa.String(255), nullable=False),
        sa.Column("is_hierarchical", sa.String(1), nullable=False),
        sa.Column("defines_ancestry", sa.String(1), nullable=False),
        sa.Column("reverse_relationship_id", sa.String(20), nullable=False),
        sa.Column("relationship_concept_id", sa.Integer(), nullable=False),
    )

    # Create concept table (central vocabulary table)
    op.create_table(
        "omop_concept",
        sa.Column("concept_id", sa.Integer(), primary_key=True),
        sa.Column("concept_name", sa.String(255), nullable=False),
        sa.Column("domain_id", sa.String(20), nullable=False),
        sa.Column("vocabulary_id", sa.String(20), nullable=False),
        sa.Column("concept_class_id", sa.String(20), nullable=False),
        sa.Column("standard_concept", sa.String(1), nullable=True),
        sa.Column("concept_code", sa.String(50), nullable=False),
        sa.Column("valid_start_date", sa.Date(), nullable=False),
        sa.Column("valid_end_date", sa.Date(), nullable=False),
        sa.Column("invalid_reason", sa.String(1), nullable=True),
        sa.ForeignKeyConstraint(
            ["vocabulary_id"], ["omop_vocabulary.vocabulary_id"],
            name="fk_concept_vocabulary"
        ),
        sa.ForeignKeyConstraint(
            ["domain_id"], ["omop_domain.domain_id"],
            name="fk_concept_domain"
        ),
        sa.ForeignKeyConstraint(
            ["concept_class_id"], ["omop_concept_class.concept_class_id"],
            name="fk_concept_class"
        ),
    )
    op.create_index("idx_omop_concept_code", "omop_concept", ["concept_code"])
    op.create_index("idx_omop_concept_vocabulary_id", "omop_concept", ["vocabulary_id"])
    op.create_index("idx_omop_concept_domain_id", "omop_concept", ["domain_id"])
    op.create_index("idx_omop_concept_class_id", "omop_concept", ["concept_class_id"])
    op.create_index("idx_omop_concept_standard", "omop_concept", ["standard_concept"])

    # Create concept_relationship table
    op.create_table(
        "omop_concept_relationship",
        sa.Column("concept_id_1", sa.Integer(), nullable=False),
        sa.Column("concept_id_2", sa.Integer(), nullable=False),
        sa.Column("relationship_id", sa.String(20), nullable=False),
        sa.Column("valid_start_date", sa.Date(), nullable=False),
        sa.Column("valid_end_date", sa.Date(), nullable=False),
        sa.Column("invalid_reason", sa.String(1), nullable=True),
        sa.PrimaryKeyConstraint("concept_id_1", "concept_id_2", "relationship_id"),
        sa.ForeignKeyConstraint(
            ["concept_id_1"], ["omop_concept.concept_id"],
            name="fk_concept_rel_concept_1"
        ),
        sa.ForeignKeyConstraint(
            ["concept_id_2"], ["omop_concept.concept_id"],
            name="fk_concept_rel_concept_2"
        ),
        sa.ForeignKeyConstraint(
            ["relationship_id"], ["omop_relationship.relationship_id"],
            name="fk_concept_rel_relationship"
        ),
    )
    op.create_index(
        "idx_omop_concept_rel_id_1", "omop_concept_relationship", ["concept_id_1"]
    )
    op.create_index(
        "idx_omop_concept_rel_id_2", "omop_concept_relationship", ["concept_id_2"]
    )
    op.create_index(
        "idx_omop_concept_rel_rel_id", "omop_concept_relationship", ["relationship_id"]
    )

    # Create concept_synonym table
    op.create_table(
        "omop_concept_synonym",
        sa.Column("concept_id", sa.Integer(), nullable=False),
        sa.Column("concept_synonym_name", sa.String(1000), nullable=False),
        sa.Column("language_concept_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["concept_id"], ["omop_concept.concept_id"],
            name="fk_concept_synonym_concept"
        ),
    )
    op.create_index(
        "idx_omop_concept_synonym_id", "omop_concept_synonym", ["concept_id"]
    )

    # Create concept_ancestor table
    op.create_table(
        "omop_concept_ancestor",
        sa.Column("ancestor_concept_id", sa.Integer(), nullable=False),
        sa.Column("descendant_concept_id", sa.Integer(), nullable=False),
        sa.Column("min_levels_of_separation", sa.Integer(), nullable=False),
        sa.Column("max_levels_of_separation", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("ancestor_concept_id", "descendant_concept_id"),
        sa.ForeignKeyConstraint(
            ["ancestor_concept_id"], ["omop_concept.concept_id"],
            name="fk_concept_ancestor_ancestor"
        ),
        sa.ForeignKeyConstraint(
            ["descendant_concept_id"], ["omop_concept.concept_id"],
            name="fk_concept_ancestor_descendant"
        ),
    )
    op.create_index(
        "idx_omop_ancestor_ancestor_id", "omop_concept_ancestor", ["ancestor_concept_id"]
    )
    op.create_index(
        "idx_omop_ancestor_descendant_id", "omop_concept_ancestor", ["descendant_concept_id"]
    )


def downgrade() -> None:
    op.drop_table("omop_concept_ancestor")
    op.drop_table("omop_concept_synonym")
    op.drop_table("omop_concept_relationship")
    op.drop_table("omop_concept")
    op.drop_table("omop_relationship")
    op.drop_table("omop_concept_class")
    op.drop_table("omop_domain")
    op.drop_table("omop_vocabulary")
