"""Add concept-to-concept edge types for OMOP lateral relationships.

Revision ID: 044
Revises: 043
Create Date: 2026-02-18

Adds has_finding_site and has_morphology edge types to support
concept→concept edges materialized from OMOP lateral relationships
(e.g., Pneumonia -[HAS_FINDING_SITE]-> Lung).
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "044"
down_revision: str | None = "043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE edge_type ADD VALUE IF NOT EXISTS 'has_finding_site'")
    op.execute("ALTER TYPE edge_type ADD VALUE IF NOT EXISTS 'has_morphology'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values.
    # The values will remain but are harmless if unused.
    pass
