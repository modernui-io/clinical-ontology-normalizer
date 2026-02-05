"""Add provenance and temporal enum values.

Adds new enum values for provenance tracking and temporal edges:

node_type additions:
- clinical_note: Source note for entity extraction
- date: Date node for temporal relationships

edge_type additions:
- extracted_from: Entity -> Clinical Note provenance
- occurred_on: Entity -> Date temporal relationship
- drug_interaction: Drug -> Drug interaction (OMOP relationship)

Revision ID: 035
Revises: 034
Create Date: 2026-02-05

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add new enum values for provenance and temporal tracking."""
    # Add new node_type enum values
    op.execute("ALTER TYPE node_type ADD VALUE IF NOT EXISTS 'clinical_note'")
    op.execute("ALTER TYPE node_type ADD VALUE IF NOT EXISTS 'date'")

    # Add new edge_type enum values
    op.execute("ALTER TYPE edge_type ADD VALUE IF NOT EXISTS 'extracted_from'")
    op.execute("ALTER TYPE edge_type ADD VALUE IF NOT EXISTS 'occurred_on'")
    op.execute("ALTER TYPE edge_type ADD VALUE IF NOT EXISTS 'drug_interaction'")


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
