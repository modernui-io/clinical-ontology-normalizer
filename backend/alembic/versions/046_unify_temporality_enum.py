"""Unify temporality enum: change kg_edges.temporality from VARCHAR(20) to temporality_type enum.

Phase 4 Workstream 1: The temporality_type enum already exists in PostgreSQL
(used by mentions and clinical_facts tables). This migration converts the
kg_edges.temporality column to use the same enum for type safety and consistency.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "046"
down_revision: str | None = "045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE kg_edges "
        "ALTER COLUMN temporality TYPE temporality_type "
        "USING temporality::temporality_type"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE kg_edges "
        "ALTER COLUMN temporality TYPE VARCHAR(20) "
        "USING temporality::text"
    )
