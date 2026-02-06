"""Add narrative node and edge types for clinical course tracking.

Adds new enum values for clinical narrative tracking:

node_type additions:
- admission: Admission event node
- clinical_event: Key event during hospitalization
- hospital_course: Hospital course summary node
- discharge: Discharge event node
- episode: Episode of care container

edge_type additions:
- admitted_for: Admission -> Condition (reason for admission)
- has_episode: Patient -> Episode (hospitalization episode)
- part_of_episode: Event -> Episode (belongs to episode)
- precedes: Event -> Event (temporal ordering)
- follows: Event -> Event (temporal ordering)
- caused_by: Event -> Event/Condition (causal relationship)
- resulted_in: Event -> Event/Condition (causal outcome)
- discharged_with: Discharge -> Condition/Plan (discharge outcome)

Revision ID: 036
Revises: 035
Create Date: 2026-02-05

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "036"
down_revision = "035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add new enum values for narrative tracking."""
    # Add new node_type enum values for narrative nodes
    op.execute("ALTER TYPE node_type ADD VALUE IF NOT EXISTS 'admission'")
    op.execute("ALTER TYPE node_type ADD VALUE IF NOT EXISTS 'clinical_event'")
    op.execute("ALTER TYPE node_type ADD VALUE IF NOT EXISTS 'hospital_course'")
    op.execute("ALTER TYPE node_type ADD VALUE IF NOT EXISTS 'discharge'")
    op.execute("ALTER TYPE node_type ADD VALUE IF NOT EXISTS 'episode'")

    # Add new edge_type enum values for narrative relationships
    op.execute("ALTER TYPE edge_type ADD VALUE IF NOT EXISTS 'admitted_for'")
    op.execute("ALTER TYPE edge_type ADD VALUE IF NOT EXISTS 'has_episode'")
    op.execute("ALTER TYPE edge_type ADD VALUE IF NOT EXISTS 'part_of_episode'")
    op.execute("ALTER TYPE edge_type ADD VALUE IF NOT EXISTS 'precedes'")
    op.execute("ALTER TYPE edge_type ADD VALUE IF NOT EXISTS 'follows'")
    op.execute("ALTER TYPE edge_type ADD VALUE IF NOT EXISTS 'caused_by'")
    op.execute("ALTER TYPE edge_type ADD VALUE IF NOT EXISTS 'resulted_in'")
    op.execute("ALTER TYPE edge_type ADD VALUE IF NOT EXISTS 'discharged_with'")


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
