"""Add data_lineage table for CDO-1 lineage tracking.

CDO-1: Data Lineage Tracking (P2 - foundational for compliance and trust).

Creates an append-only table to track WHERE each ClinicalFact came from
and HOW it was derived, enabling regulatory compliance audits and debugging.

Revision ID: 039
Revises: 038
Create Date: 2026-02-08

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "039"
down_revision: str | None = "038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "data_lineage",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "clinical_fact_id",
            UUID(as_uuid=False),
            sa.ForeignKey("clinical_facts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column(
            "source_document_id",
            UUID(as_uuid=False),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_resource_type", sa.String(100), nullable=True),
        sa.Column("source_resource_id", sa.String(255), nullable=True),
        sa.Column("extraction_method", sa.String(100), nullable=True),
        sa.Column("extraction_confidence", sa.Float, nullable=True),
        sa.Column("transformation_chain", JSON, nullable=True),
    )

    # Indexes for common query patterns
    op.create_index(
        "ix_data_lineage_clinical_fact_id",
        "data_lineage",
        ["clinical_fact_id"],
    )
    op.create_index(
        "ix_data_lineage_source_type",
        "data_lineage",
        ["source_type"],
    )
    op.create_index(
        "ix_data_lineage_fact_source",
        "data_lineage",
        ["clinical_fact_id", "source_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_data_lineage_fact_source", table_name="data_lineage")
    op.drop_index("ix_data_lineage_source_type", table_name="data_lineage")
    op.drop_index("ix_data_lineage_clinical_fact_id", table_name="data_lineage")
    op.drop_table("data_lineage")
