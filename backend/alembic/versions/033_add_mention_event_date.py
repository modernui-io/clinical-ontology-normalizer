"""Add event_date field to mentions table.

Captures the specific date when a clinical event occurred,
extracted from text like "diagnosed on 3/15/2023" or "started March 2022".

Revision ID: 033
Revises: 032
Create Date: 2026-02-02
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add event_date column to mentions table."""
    op.add_column(
        "mentions",
        sa.Column(
            "event_date",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # Create index for temporal queries
    op.create_index(
        "ix_mentions_event_date",
        "mentions",
        ["event_date"],
    )


def downgrade() -> None:
    """Remove event_date column from mentions table."""
    op.drop_index("ix_mentions_event_date", "mentions")
    op.drop_column("mentions", "event_date")
