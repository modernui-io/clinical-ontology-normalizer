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
import logging
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = "043"
down_revision: str | None = "042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT 1 FROM pg_tables WHERE tablename = :t"),
        {"t": table_name},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    # Covering indexes on omop_concept_ancestor (only if table exists — loaded by ETL)
    if _table_exists("omop_concept_ancestor"):
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_omop_ancestor_desc_covering
            ON omop_concept_ancestor (descendant_concept_id)
            INCLUDE (ancestor_concept_id, min_levels_of_separation, max_levels_of_separation)
            """
        )
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_omop_ancestor_anc_covering
            ON omop_concept_ancestor (ancestor_concept_id)
            INCLUDE (descendant_concept_id, min_levels_of_separation, max_levels_of_separation)
            """
        )
    else:
        logger.info("omop_concept_ancestor table not found — skipping covering indexes (run OMOP ETL first)")

    # Trigram index for fast ILIKE searches on concept name
    if _table_exists("omop_concept"):
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_omop_concept_name_trgm
            ON omop_concept USING gin (concept_name gin_trgm_ops)
            """
        )
    else:
        logger.info("omop_concept table not found — skipping trigram index (run OMOP ETL first)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_omop_concept_name_trgm")
    op.execute("DROP INDEX IF EXISTS ix_omop_ancestor_anc_covering")
    op.execute("DROP INDEX IF EXISTS ix_omop_ancestor_desc_covering")
