"""Add provenance_records and reasoning_traces tables.

Revision ID: 020
Revises: 019
Create Date: 2026-01-27

Adds tables for tracking:
- provenance_records: Origin and extraction details of clinical entities
- reasoning_traces: Steps of the hybrid query reasoning pipeline
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "020"
down_revision: str | None = "019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create provenance_records table
    op.create_table(
        "provenance_records",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", sa.String(255), nullable=False),
        sa.Column("patient_id", sa.String(255), nullable=True),
        sa.Column("extraction_method", sa.String(50), nullable=False),
        sa.Column("confidence_level", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("source_section", sa.String(500), nullable=True),
        sa.Column("source_span_start", sa.Integer(), nullable=True),
        sa.Column("source_span_end", sa.Integer(), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("extraction_model", sa.String(200), nullable=True),
        sa.Column("extraction_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by", sa.String(255), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
    )

    # Provenance indexes
    op.create_index("ix_provenance_records_entity_type", "provenance_records", ["entity_type"])
    op.create_index("ix_provenance_records_entity_id", "provenance_records", ["entity_id"])
    op.create_index("ix_provenance_records_patient_id", "provenance_records", ["patient_id"])
    op.create_index("ix_provenance_entity", "provenance_records", ["entity_type", "entity_id"])
    op.create_index("ix_provenance_patient_entity", "provenance_records", ["patient_id", "entity_type"])
    op.create_index("ix_provenance_source_doc", "provenance_records", ["source_document_id"])

    # Create reasoning_traces table
    op.create_table(
        "reasoning_traces",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("query_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("patient_id", sa.String(255), nullable=True),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("step_type", sa.String(50), nullable=False),
        sa.Column("input_summary", sa.Text(), nullable=True),
        sa.Column("output_summary", sa.Text(), nullable=True),
        sa.Column("confidence_contribution", sa.Float(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
    )

    # Reasoning trace indexes
    op.create_index("ix_reasoning_traces_query_id", "reasoning_traces", ["query_id"])
    op.create_index("ix_reasoning_traces_patient_id", "reasoning_traces", ["patient_id"])
    op.create_index("ix_reasoning_query_step", "reasoning_traces", ["query_id", "step_order"])
    op.create_index("ix_reasoning_patient", "reasoning_traces", ["patient_id"])


def downgrade() -> None:
    # Drop reasoning_traces indexes
    op.drop_index("ix_reasoning_patient")
    op.drop_index("ix_reasoning_query_step")
    op.drop_index("ix_reasoning_traces_patient_id")
    op.drop_index("ix_reasoning_traces_query_id")

    # Drop reasoning_traces table
    op.drop_table("reasoning_traces")

    # Drop provenance_records indexes
    op.drop_index("ix_provenance_source_doc")
    op.drop_index("ix_provenance_patient_entity")
    op.drop_index("ix_provenance_entity")
    op.drop_index("ix_provenance_records_patient_id")
    op.drop_index("ix_provenance_records_entity_id")
    op.drop_index("ix_provenance_records_entity_type")

    # Drop provenance_records table
    op.drop_table("provenance_records")
