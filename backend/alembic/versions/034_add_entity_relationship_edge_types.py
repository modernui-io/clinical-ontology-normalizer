"""Add entity-to-entity relationship edge types.

Adds new edge_type enum values to support entity-to-entity relationships:
- symptom_of: Symptom -> Condition relationship
- monitors: Measurement -> Condition relationship
- related_to: Generic entity relationship
- may_cause: Drug -> Side effect relationship
- contraindicated_with: Drug -> Drug/Condition contraindication

Revision ID: 034
Revises: 033
Create Date: 2026-02-04

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "034"
down_revision = "033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add new edge_type enum values for entity-to-entity relationships."""
    # Add new enum values for entity relationships
    # Using IF NOT EXISTS to be idempotent
    op.execute("ALTER TYPE edge_type ADD VALUE IF NOT EXISTS 'symptom_of'")
    op.execute("ALTER TYPE edge_type ADD VALUE IF NOT EXISTS 'monitors'")
    op.execute("ALTER TYPE edge_type ADD VALUE IF NOT EXISTS 'related_to'")
    op.execute("ALTER TYPE edge_type ADD VALUE IF NOT EXISTS 'may_cause'")
    op.execute("ALTER TYPE edge_type ADD VALUE IF NOT EXISTS 'contraindicated_with'")


def downgrade() -> None:
    """Downgrade not supported for enum value removal.

    PostgreSQL does not support removing enum values directly.
    To downgrade, you would need to:
    1. Create a new enum type without these values
    2. Update all rows to not use these values
    3. Drop and recreate the column with the new type
    4. Drop the old enum type

    This is left as a manual operation if needed.
    """
    pass
