"""Add vocabulary versioning columns.

Revision ID: 023
Revises: 022
Create Date: 2026-01-27

Adds version tracking columns to concepts and concept_relationships tables.
Creates ConceptStatus enum; defaults existing rows to 'active'.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "023"
down_revision: str | None = "022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create enum type
    concept_status = sa.Enum(
        "active", "deprecated", "retired", "merged",
        name="concept_status",
    )
    concept_status.create(op.get_bind(), checkfirst=True)

    # Add version columns to concepts
    op.add_column(
        "concepts",
        sa.Column("vocabulary_version", sa.String(50), nullable=True),
    )
    op.add_column(
        "concepts",
        sa.Column("version_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "concepts",
        sa.Column("previous_concept_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "concepts",
        sa.Column(
            "status",
            concept_status,
            nullable=False,
            server_default="active",
        ),
    )
    op.add_column(
        "concepts",
        sa.Column("status_changed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("ix_concepts_vocabulary_version", "concepts", ["vocabulary_version"])
    op.create_index("ix_concepts_status", "concepts", ["status"])

    # Add relationship_version to concept_relationships
    op.add_column(
        "concept_relationships",
        sa.Column("relationship_version", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("concept_relationships", "relationship_version")
    op.drop_index("ix_concepts_status")
    op.drop_index("ix_concepts_vocabulary_version")
    op.drop_column("concepts", "status_changed_at")
    op.drop_column("concepts", "status")
    op.drop_column("concepts", "previous_concept_id")
    op.drop_column("concepts", "version_date")
    op.drop_column("concepts", "vocabulary_version")

    sa.Enum(name="concept_status").drop(op.get_bind(), checkfirst=True)
