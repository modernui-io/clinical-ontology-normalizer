"""Add temporal pipeline fields to documents and mentions.

Adds note_date to documents (for anchoring relative temporal expressions)
and date_precision + temporal_relationship to mentions (enriched by
temporal extractor during NLP extraction).

Note: mentions.event_date was already added in migration 033.

Revision ID: 049
Revises: 048
Create Date: 2026-02-19
"""

from alembic import op
import sqlalchemy as sa

revision = "049"
down_revision = "048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add temporal pipeline columns."""
    # Add note_date to documents
    op.add_column(
        "documents",
        sa.Column(
            "note_date",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # Add date_precision and temporal_relationship to mentions
    op.add_column(
        "mentions",
        sa.Column(
            "date_precision",
            sa.String(20),
            nullable=True,
        ),
    )
    op.add_column(
        "mentions",
        sa.Column(
            "temporal_relationship",
            sa.String(30),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Remove temporal pipeline columns."""
    op.drop_column("mentions", "temporal_relationship")
    op.drop_column("mentions", "date_precision")
    op.drop_column("documents", "note_date")
