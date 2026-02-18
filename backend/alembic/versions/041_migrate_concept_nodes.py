"""Migrate per-patient concept nodes to shared global concept nodes.

For each (node_type, omop_concept_id) group:
1. Create one canonical shared node (patient_id=NULL)
2. Copy assertion/temporality from old node.properties to edge.properties
3. Repoint edges to the canonical node
4. Soft-delete old per-patient concept nodes

Revision ID: 041
Revises: 040
Create Date: 2026-02-17

"""

import json
from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "041"
down_revision: str | None = "040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # Step 1: Find all (node_type, omop_concept_id) groups that have per-patient nodes
    groups = conn.execute(text("""
        SELECT DISTINCT node_type, omop_concept_id
        FROM kg_nodes
        WHERE patient_id IS NOT NULL
          AND node_type != 'patient'
          AND omop_concept_id IS NOT NULL
          AND deleted_at IS NULL
    """)).fetchall()

    for node_type, omop_concept_id in groups:
        # Step 2: Check if a canonical shared node already exists (idempotent)
        existing = conn.execute(text("""
            SELECT id FROM kg_nodes
            WHERE patient_id IS NULL
              AND node_type = :node_type
              AND omop_concept_id = :omop_concept_id
              AND deleted_at IS NULL
            LIMIT 1
        """), {"node_type": node_type, "omop_concept_id": omop_concept_id}).fetchone()

        if existing:
            canonical_id = existing[0]
        else:
            # Get a representative node's concept-level properties
            representative = conn.execute(text("""
                SELECT id, label, properties
                FROM kg_nodes
                WHERE patient_id IS NOT NULL
                  AND node_type = :node_type
                  AND omop_concept_id = :omop_concept_id
                  AND deleted_at IS NULL
                ORDER BY created_at ASC
                LIMIT 1
            """), {"node_type": node_type, "omop_concept_id": omop_concept_id}).fetchone()

            if not representative:
                continue

            # Create canonical shared node with concept-level properties only
            # Strip patient-specific fields (assertion, temporality, experiencer) from properties
            old_props = representative[2] if isinstance(representative[2], dict) else json.loads(representative[2] or "{}")
            concept_props = {k: v for k, v in old_props.items()
                            if k not in ("assertion", "temporality", "experiencer", "is_negated", "is_uncertain", "fact_id")}

            conn.execute(text("""
                INSERT INTO kg_nodes (id, patient_id, node_type, omop_concept_id, label, properties, created_at)
                VALUES (gen_random_uuid(), NULL, :node_type, :omop_concept_id, :label, :properties::jsonb, now())
            """), {
                "node_type": node_type,
                "omop_concept_id": omop_concept_id,
                "label": representative[1],
                "properties": json.dumps(concept_props),
            })

            # Get the newly created canonical node ID
            row = conn.execute(text("""
                SELECT id FROM kg_nodes
                WHERE patient_id IS NULL
                  AND node_type = :node_type
                  AND omop_concept_id = :omop_concept_id
                  AND deleted_at IS NULL
                LIMIT 1
            """), {"node_type": node_type, "omop_concept_id": omop_concept_id}).fetchone()
            canonical_id = row[0]

        # Step 3: For each old per-patient node, repoint edges and copy metadata
        old_nodes = conn.execute(text("""
            SELECT id, patient_id, properties
            FROM kg_nodes
            WHERE patient_id IS NOT NULL
              AND node_type = :node_type
              AND omop_concept_id = :omop_concept_id
              AND deleted_at IS NULL
        """), {"node_type": node_type, "omop_concept_id": omop_concept_id}).fetchall()

        for old_id, old_patient_id, old_props_raw in old_nodes:
            old_props = old_props_raw if isinstance(old_props_raw, dict) else json.loads(old_props_raw or "{}")

            # Extract assertion metadata from node.properties to merge into edge.properties
            assertion_data = {}
            for key in ("assertion", "temporality", "experiencer", "is_negated", "is_uncertain", "fact_id"):
                if key in old_props:
                    assertion_data[key] = old_props[key]

            if assertion_data:
                assertion_json = json.dumps(assertion_data)

                # Update edges pointing TO this old node
                conn.execute(text("""
                    UPDATE kg_edges
                    SET properties = COALESCE(properties, '{}'::jsonb) || :assertion_data::jsonb,
                        target_node_id = :canonical_id
                    WHERE target_node_id = :old_id
                """), {
                    "assertion_data": assertion_json,
                    "canonical_id": str(canonical_id),
                    "old_id": str(old_id),
                })

                # Update edges pointing FROM this old node
                conn.execute(text("""
                    UPDATE kg_edges
                    SET properties = COALESCE(properties, '{}'::jsonb) || :assertion_data::jsonb,
                        source_node_id = :canonical_id
                    WHERE source_node_id = :old_id
                """), {
                    "assertion_data": assertion_json,
                    "canonical_id": str(canonical_id),
                    "old_id": str(old_id),
                })
            else:
                # Just repoint edges without modifying properties
                conn.execute(text("""
                    UPDATE kg_edges SET target_node_id = :canonical_id WHERE target_node_id = :old_id
                """), {"canonical_id": str(canonical_id), "old_id": str(old_id)})

                conn.execute(text("""
                    UPDATE kg_edges SET source_node_id = :canonical_id WHERE source_node_id = :old_id
                """), {"canonical_id": str(canonical_id), "old_id": str(old_id)})

            # Step 4: Soft-delete old per-patient node
            conn.execute(text("""
                UPDATE kg_nodes SET deleted_at = now() WHERE id = :old_id
            """), {"old_id": str(old_id)})


def downgrade() -> None:
    # Restore soft-deleted per-patient concept nodes
    op.execute(text("""
        UPDATE kg_nodes SET deleted_at = NULL
        WHERE deleted_at IS NOT NULL
          AND patient_id IS NOT NULL
          AND node_type != 'patient'
          AND omop_concept_id IS NOT NULL
    """))
    # Delete the shared canonical nodes created by this migration.
    # Note: Edge repointing is not automatically reversed.
    # A full rollback requires restoring from backup or running a reverse migration.
    op.execute(text("""
        DELETE FROM kg_nodes
        WHERE patient_id IS NULL
          AND node_type != 'patient'
          AND omop_concept_id IS NOT NULL
    """))
