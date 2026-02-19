"""Add PHI encrypted columns for HIPAA compliance.

Revision ID: 042
Revises: 041
Create Date: 2026-02-18

Adds encrypted columns alongside existing plaintext for safe migration:
- documents.text_encrypted (Fernet-encrypted document text)
- kg_nodes.patient_id_encrypted (AES-SIV deterministic for queryability)
- kg_edges.patient_id_encrypted (AES-SIV deterministic for queryability)
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "042"
down_revision: str | None = "041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add encrypted columns (nullable for gradual migration)
    op.add_column("documents", sa.Column("text_encrypted", sa.Text(), nullable=True))
    op.add_column("kg_nodes", sa.Column("patient_id_encrypted", sa.String(500), nullable=True))
    op.add_column("kg_edges", sa.Column("patient_id_encrypted", sa.String(500), nullable=True))

    # Add index on encrypted patient_id for queryability
    op.create_index(
        "ix_kg_nodes_patient_id_encrypted",
        "kg_nodes",
        ["patient_id_encrypted"],
    )
    op.create_index(
        "ix_kg_edges_patient_id_encrypted",
        "kg_edges",
        ["patient_id_encrypted"],
    )


def downgrade() -> None:
    op.drop_index("ix_kg_edges_patient_id_encrypted", table_name="kg_edges")
    op.drop_index("ix_kg_nodes_patient_id_encrypted", table_name="kg_nodes")
    op.drop_column("kg_edges", "patient_id_encrypted")
    op.drop_column("kg_nodes", "patient_id_encrypted")
    op.drop_column("documents", "text_encrypted")
