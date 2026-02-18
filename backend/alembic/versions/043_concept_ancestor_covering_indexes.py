"""Add covering indexes for omop_concept_ancestor and trigram index for concept name.

Revision ID: 043
Revises: 042
Create Date: 2026-02-18

The existing single-column indexes (from migration 018) require table lookups
for every row. These composite covering indexes enable index-only scans for
the two dominant access patterns: ancestor lookup (given descendant) and
descendant lookup (given ancestor). The trigram index supports fast ILIKE
searches on concept_name.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "043"
down_revision: str | None = "042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Covering index: given descendant, find ancestors (index-only scan)
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_omop_ancestor_desc_covering
        ON omop_concept_ancestor (descendant_concept_id)
        INCLUDE (ancestor_concept_id, min_levels_of_separation, max_levels_of_separation)
        """
    )

    # Covering index: given ancestor, find descendants (index-only scan)
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_omop_ancestor_anc_covering
        ON omop_concept_ancestor (ancestor_concept_id)
        INCLUDE (descendant_concept_id, min_levels_of_separation, max_levels_of_separation)
        """
    )

    # Trigram index for fast ILIKE searches on concept name
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_omop_concept_name_trgm
        ON omop_concept USING gin (concept_name gin_trgm_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_omop_concept_name_trgm")
    op.execute("DROP INDEX IF EXISTS ix_omop_ancestor_anc_covering")
    op.execute("DROP INDEX IF EXISTS ix_omop_ancestor_desc_covering")
