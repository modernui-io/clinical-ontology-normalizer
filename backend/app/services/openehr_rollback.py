"""OpenEHR Batch Rollback Service — tested code path for import rollback.

P0-019: Replaces the manual SQL from the ops runbook with a callable service
that soft-deletes ClinicalFacts and removes KG nodes/edges for a given
patient + time range batch.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinical_fact import ClinicalFact
from app.models.data_lineage import DataLineageRecord, SourceType
from app.models.knowledge_graph import KGEdge, KGNode

logger = logging.getLogger(__name__)


@dataclass
class RollbackReport:
    """Result of a batch rollback operation."""

    patient_id: str
    success: bool
    facts_deleted: int = 0
    nodes_deleted: int = 0
    edges_deleted: int = 0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "patient_id": self.patient_id,
            "success": self.success,
            "facts_deleted": self.facts_deleted,
            "nodes_deleted": self.nodes_deleted,
            "edges_deleted": self.edges_deleted,
            "error": self.error,
        }


@dataclass
class RollbackVerification:
    """Result of a rollback verification check."""

    patient_id: str
    passed: bool
    residual_facts: int = 0
    residual_nodes: int = 0
    residual_edges: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "patient_id": self.patient_id,
            "passed": self.passed,
            "residual_facts": self.residual_facts,
            "residual_nodes": self.residual_nodes,
            "residual_edges": self.residual_edges,
        }


class OpenEHRRollbackService:
    """Batch rollback of OpenEHR imports by patient + time range."""

    async def rollback_import_batch(
        self,
        session: AsyncSession,
        patient_id: str,
        batch_start: datetime,
        batch_end: datetime,
    ) -> RollbackReport:
        """Identify affected ClinicalFacts via lineage, soft-delete facts,
        and remove KG nodes/edges for the batch.

        Args:
            session: Database session.
            patient_id: Patient whose imports to roll back.
            batch_start: Start of the time window (created_at >= batch_start).
            batch_end: End of the time window (created_at <= batch_end).

        Returns:
            RollbackReport with counts of affected entities.
        """
        try:
            # Step 1: Find fact IDs from OpenEHR imports in the time range via lineage
            lineage_result = await session.execute(
                select(DataLineageRecord.clinical_fact_id).where(
                    DataLineageRecord.source_type == SourceType.OPENEHR_IMPORT,
                    DataLineageRecord.created_at >= batch_start,
                    DataLineageRecord.created_at <= batch_end,
                )
            )
            batch_fact_ids = set(lineage_result.scalars().all())

            if not batch_fact_ids:
                # Fallback: find facts directly by patient + time range
                fact_result = await session.execute(
                    select(ClinicalFact.id).where(
                        ClinicalFact.patient_id == patient_id,
                        ClinicalFact.deleted_at.is_(None),
                        ClinicalFact.created_at >= batch_start,
                        ClinicalFact.created_at <= batch_end,
                    )
                )
                batch_fact_ids = set(fact_result.scalars().all())

            if not batch_fact_ids:
                return RollbackReport(
                    patient_id=patient_id,
                    success=True,
                    error="No matching facts found in batch window",
                )

            # Step 2: Filter to only this patient's facts
            facts_result = await session.execute(
                select(ClinicalFact).where(
                    ClinicalFact.id.in_(batch_fact_ids),
                    ClinicalFact.patient_id == patient_id,
                    ClinicalFact.deleted_at.is_(None),
                )
            )
            facts = list(facts_result.scalars().all())
            fact_ids = {f.id for f in facts}

            # Step 3: Soft-delete the facts
            for fact in facts:
                fact.soft_delete()

            # Step 4: Soft-delete KG edges referencing these facts
            edges_result = await session.execute(
                select(KGEdge).where(
                    KGEdge.patient_id == patient_id,
                    KGEdge.fact_id.in_(fact_ids),
                    KGEdge.deleted_at.is_(None),
                )
            )
            edges = list(edges_result.scalars().all())
            for edge in edges:
                edge.soft_delete()

            # Step 5: Soft-delete KG nodes that are targets of the deleted edges
            # (but NOT the patient node — preserve it)
            target_node_ids = {e.target_node_id for e in edges}
            if target_node_ids:
                nodes_result = await session.execute(
                    select(KGNode).where(
                        KGNode.id.in_(target_node_ids),
                        KGNode.patient_id == patient_id,
                        KGNode.deleted_at.is_(None),
                    )
                )
                nodes = list(nodes_result.scalars().all())
                for node in nodes:
                    node.soft_delete()
                nodes_deleted = len(nodes)
            else:
                nodes_deleted = 0

            await session.flush()

            return RollbackReport(
                patient_id=patient_id,
                success=True,
                facts_deleted=len(facts),
                nodes_deleted=nodes_deleted,
                edges_deleted=len(edges),
            )

        except Exception as e:
            logger.error(f"Rollback failed for patient {patient_id}: {e}")
            return RollbackReport(
                patient_id=patient_id,
                success=False,
                error=str(e),
            )

    async def verify_rollback(
        self,
        session: AsyncSession,
        patient_id: str,
        batch_start: datetime,
        batch_end: datetime,
    ) -> RollbackVerification:
        """Confirm zero remaining active facts/nodes/edges from the batch.

        Returns pass/fail with residual counts.
        """
        # Check for active facts from OpenEHR import in the time range
        lineage_result = await session.execute(
            select(DataLineageRecord.clinical_fact_id).where(
                DataLineageRecord.source_type == SourceType.OPENEHR_IMPORT,
                DataLineageRecord.created_at >= batch_start,
                DataLineageRecord.created_at <= batch_end,
            )
        )
        batch_fact_ids = set(lineage_result.scalars().all())

        residual_facts = 0
        residual_edges = 0
        residual_nodes = 0

        if batch_fact_ids:
            # Count active (non-deleted) facts
            facts_result = await session.execute(
                select(ClinicalFact).where(
                    ClinicalFact.id.in_(batch_fact_ids),
                    ClinicalFact.patient_id == patient_id,
                    ClinicalFact.deleted_at.is_(None),
                )
            )
            residual_facts = len(list(facts_result.scalars().all()))

            # Count active edges referencing these facts
            edges_result = await session.execute(
                select(KGEdge).where(
                    KGEdge.patient_id == patient_id,
                    KGEdge.fact_id.in_(batch_fact_ids),
                    KGEdge.deleted_at.is_(None),
                )
            )
            residual_edges = len(list(edges_result.scalars().all()))

        # Count active non-patient nodes in the time range
        nodes_result = await session.execute(
            select(KGNode).where(
                KGNode.patient_id == patient_id,
                KGNode.deleted_at.is_(None),
                KGNode.created_at >= batch_start,
                KGNode.created_at <= batch_end,
                KGNode.node_type != "patient",
            )
        )
        residual_nodes = len(list(nodes_result.scalars().all()))

        passed = residual_facts == 0 and residual_edges == 0 and residual_nodes == 0

        return RollbackVerification(
            patient_id=patient_id,
            passed=passed,
            residual_facts=residual_facts,
            residual_nodes=residual_nodes,
            residual_edges=residual_edges,
        )
