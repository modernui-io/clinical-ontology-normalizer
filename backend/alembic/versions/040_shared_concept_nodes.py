"""Make kg_nodes.patient_id nullable for shared concept nodes.

Shared concept nodes (conditions, drugs, measurements, procedures, observations)
have patient_id=NULL and are shared across patients. Patient nodes still require
patient_id. Edges carry patient_id to scope relationships.

Revision ID: 040
Revises: 039
Create Date: 2026-02-17

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "040"
down_revision: str | None = "039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Make patient_id nullable on kg_nodes
    op.alter_column("kg_nodes", "patient_id", nullable=True)

    # 2. Add CHECK constraint: patient nodes must have patient_id
    op.execute(
        """
        ALTER TABLE kg_nodes
        ADD CONSTRAINT ck_patient_node_has_pid
        CHECK (
            (node_type = 'patient' AND patient_id IS NOT NULL)
            OR (node_type != 'patient')
        )
        """
    )

    # 3. Unique index for global concept dedup: one shared node per (node_type, omop_concept_id)
    op.execute(
        """
        CREATE UNIQUE INDEX ix_kg_nodes_global_concept
        ON kg_nodes (node_type, omop_concept_id)
        WHERE patient_id IS NULL
          AND omop_concept_id IS NOT NULL
          AND deleted_at IS NULL
        """
    )

    # 4. Index for querying shared nodes by type
    op.execute(
        """
        CREATE INDEX ix_kg_nodes_shared
        ON kg_nodes (node_type)
        WHERE patient_id IS NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_kg_nodes_shared")
    op.execute("DROP INDEX IF EXISTS ix_kg_nodes_global_concept")
    op.execute("ALTER TABLE kg_nodes DROP CONSTRAINT IF EXISTS ck_patient_node_has_pid")
    op.alter_column("kg_nodes", "patient_id", nullable=False)
