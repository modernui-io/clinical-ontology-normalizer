"""Database-backed Knowledge Graph builder service.

Implements graph construction with database persistence.
Supports bi-temporal model for temporal reasoning.
Syncs graphs to Neo4j for graph queries and visualization.
"""
# MODULE: graph_storage
# MATURITY: production

from __future__ import annotations

import json
import logging
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import or_, select, text, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.clinical_fact import ClinicalFact
from app.models.knowledge_graph import KGEdge, KGNode
from app.schemas.base import Domain
from app.schemas.knowledge_graph import EdgeType, NodeType, PatientGraph, TemporalOrder
from app.services.graph_builder import (
    BaseGraphBuilderService,
    EdgeInput,
    GraphResult,
    NodeInput,
)
from app.core.degradation_context import DegradationContext
from app.services.graph_database_service import get_graph_database_service

logger = logging.getLogger(__name__)


class DatabaseGraphBuilderService(BaseGraphBuilderService):
    """Database-backed graph builder service.

    Creates and manages KGNode and KGEdge records in the database.

    Usage:
        service = DatabaseGraphBuilderService(session)
        result = service.build_graph_for_patient("P001")
    """

    def __init__(self, session: Session) -> None:
        """Initialize the database graph builder.

        Args:
            session: SQLAlchemy database session.
        """
        super().__init__()
        self._session = session
        self._patient_node_cache: dict[str, UUID] = {}
        self._node_dedup_cache: dict[str, UUID] = {}
        # Reverse map: UUID -> NodeInput for O(1) edge lookups
        self._uuid_to_node: dict[UUID, NodeInput] = {}
        self._pending_flush = False

    def create_patient_node(self, patient_id: str) -> UUID:
        """Create or get the central patient node."""
        # Check cache
        if patient_id in self._patient_node_cache:
            return self._patient_node_cache[patient_id]

        # Check database
        stmt = (
            select(KGNode)
            .where(KGNode.patient_id == patient_id)
            .where(KGNode.node_type == NodeType.PATIENT)
        )
        result = self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            node_id = UUID(existing.id)
            self._patient_node_cache[patient_id] = node_id
            self._uuid_to_node[node_id] = NodeInput(
                patient_id=patient_id,
                node_type=NodeType.PATIENT,
                label=existing.label,
                omop_concept_id=None,
                properties=existing.properties,
            )
            return node_id

        # Create new patient node
        node = KGNode(
            patient_id=patient_id,
            node_type=NodeType.PATIENT,
            omop_concept_id=None,
            label=f"Patient {patient_id}",
            properties={"type": "patient"},
        )
        self._session.add(node)
        self._session.flush()

        node_id = UUID(node.id)
        self._patient_node_cache[patient_id] = node_id
        self._uuid_to_node[node_id] = NodeInput(
            patient_id=patient_id,
            node_type=NodeType.PATIENT,
            label=f"Patient {patient_id}",
            omop_concept_id=None,
            properties={"type": "patient"},
        )
        return node_id

    def get_patient_node(self, patient_id: str) -> UUID | None:
        """Get the patient node ID for a patient."""
        if patient_id in self._patient_node_cache:
            return self._patient_node_cache[patient_id]

        stmt = (
            select(KGNode)
            .where(KGNode.patient_id == patient_id)
            .where(KGNode.node_type == NodeType.PATIENT)
        )
        result = self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            node_id = UUID(existing.id)
            self._patient_node_cache[patient_id] = node_id
            return node_id

        return None

    def create_node(self, node_input: NodeInput) -> UUID:
        """Create a node in the knowledge graph.

        For concept nodes (non-PATIENT with omop_concept_id), creates shared
        nodes with patient_id=None that are deduplicated across patients.
        Patient nodes always retain their patient_id.
        """
        # Determine if this should be a shared concept node
        is_concept = (
            node_input.node_type != NodeType.PATIENT
            and node_input.omop_concept_id is not None
        )
        if is_concept:
            node_input = NodeInput(
                patient_id=None,
                node_type=node_input.node_type,
                label=node_input.label,
                omop_concept_id=node_input.omop_concept_id,
                properties=node_input.properties,
            )

        # Calculate dedup key
        dedup_key = self.calculate_node_dedup_key(
            node_input.patient_id,
            node_input.node_type,
            node_input.omop_concept_id,
        )

        # Check cache (covers both primed DB results and in-session creates)
        if dedup_key in self._node_dedup_cache:
            return self._node_dedup_cache[dedup_key]

        # Check database only if cache wasn't primed.
        # Always check DB for shared concepts even when cache is primed,
        # since _prime_caches only loads concepts connected to THIS patient.
        if not self._pending_flush or is_concept:
            if is_concept:
                # Shared concept lookup: patient_id IS NULL + concept identity
                stmt = (
                    select(KGNode)
                    .where(KGNode.patient_id.is_(None))
                    .where(KGNode.omop_concept_id == node_input.omop_concept_id)
                    .where(KGNode.node_type == node_input.node_type)
                )
            else:
                stmt = select(KGNode).where(KGNode.patient_id == node_input.patient_id)
                if node_input.omop_concept_id:
                    stmt = stmt.where(KGNode.omop_concept_id == node_input.omop_concept_id)
                stmt = stmt.where(KGNode.node_type == node_input.node_type)

            result = self._session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                node_id = UUID(existing.id)
                self._node_dedup_cache[dedup_key] = node_id
                self._uuid_to_node[node_id] = node_input
                return node_id

        # Create new node
        node = KGNode(
            patient_id=node_input.patient_id,
            node_type=node_input.node_type,
            omop_concept_id=node_input.omop_concept_id,
            label=node_input.label,
            properties=node_input.properties,
        )
        self._session.add(node)
        self._session.flush()

        node_id = UUID(node.id)
        self._node_dedup_cache[dedup_key] = node_id
        self._uuid_to_node[node_id] = node_input
        return node_id

    def create_edge(self, edge_input: EdgeInput) -> UUID:
        """Create an edge in the knowledge graph.

        Populates bi-temporal fields from EdgeInput:
        - Valid Time: event_date, valid_from, valid_to
        - Transaction Time: recorded_at, source_document_date
        - Temporal Assertion: temporality, temporal_order, temporal_confidence
        """
        # Check for existing edge
        stmt = (
            select(KGEdge)
            .where(KGEdge.source_node_id == str(edge_input.source_node_id))
            .where(KGEdge.target_node_id == str(edge_input.target_node_id))
            .where(KGEdge.edge_type == edge_input.edge_type)
        )
        result = self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            return UUID(existing.id)

        # Create new edge with bi-temporal fields
        # Auto-compute temporal_order via Allen's interval algebra if intervals exist
        computed_temporal_order = edge_input.temporal_order
        if computed_temporal_order is None and edge_input.valid_from and edge_input.valid_to:
            computed_temporal_order = self._compute_temporal_order(edge_input)

        edge = KGEdge(
            patient_id=edge_input.patient_id,
            source_node_id=str(edge_input.source_node_id),
            target_node_id=str(edge_input.target_node_id),
            edge_type=edge_input.edge_type,
            fact_id=str(edge_input.fact_id) if edge_input.fact_id else None,
            properties=edge_input.properties,
            # Valid Time: When the clinical event happened
            event_date=edge_input.event_date,
            valid_from=edge_input.valid_from,
            valid_to=edge_input.valid_to,
            # Transaction Time: Provenance
            recorded_at=edge_input.recorded_at,
            source_document_date=edge_input.source_document_date,
            # Temporal Assertion
            temporality=edge_input.temporality,
            temporal_order=computed_temporal_order.value if computed_temporal_order else None,
            temporal_confidence=edge_input.temporal_confidence,
        )
        self._session.add(edge)
        self._session.flush()

        return UUID(edge.id)

    def _compute_temporal_order(self, edge_input: EdgeInput) -> TemporalOrder | None:
        """Compute temporal_order via Allen's interval algebra.

        Finds the most recent existing edge for the same patient + target concept
        and computes the Allen relation between the new edge and the existing one.
        Returns None if no suitable reference edge exists.
        """
        try:
            from app.services.temporal_query_service import (
                TemporalInterval,
                temporal_order_from_intervals,
            )

            # Find related edges for same patient + target concept
            related_stmt = (
                select(KGEdge)
                .where(KGEdge.patient_id == edge_input.patient_id)
                .where(KGEdge.target_node_id == str(edge_input.target_node_id))
                .where(KGEdge.valid_from.isnot(None))
                .where(KGEdge.valid_to.isnot(None))
                .order_by(KGEdge.valid_from.desc())
                .limit(1)
            )
            related = self._session.execute(related_stmt).scalar_one_or_none()

            if related and related.valid_from and related.valid_to:
                new_interval = TemporalInterval(
                    start=edge_input.valid_from, end=edge_input.valid_to
                )
                existing_interval = TemporalInterval(
                    start=related.valid_from, end=related.valid_to
                )
                return temporal_order_from_intervals(new_interval, existing_interval)
        except Exception as exc:
            logger.debug("Allen's interval computation skipped: %s", exc)

        return None

    def project_fact_to_graph(
        self,
        fact_id: UUID,
        patient_id: str,
        domain: Domain,
        omop_concept_id: int,
        concept_name: str,
        assertion: str,
        temporality: str,
        experiencer: str,
        # Bi-temporal fields
        event_date: "datetime | None" = None,
        valid_from: "datetime | None" = None,
        valid_to: "datetime | None" = None,
        recorded_at: "datetime | None" = None,
        source_document_date: "datetime | None" = None,
        temporal_confidence: float | None = None,
    ) -> UUID:
        """Project a ClinicalFact to a node in the graph.

        Creates a shared concept node (patient_id=None) and an edge from the
        patient node to it. Patient-specific metadata (assertion, experiencer,
        etc.) lives on the edge, keeping the node concept-level only.
        """
        # Create the shared concept node (patient_id=None via create_node)
        node_type = self.domain_to_node_type(domain)
        node_input = NodeInput(
            patient_id=None,
            node_type=node_type,
            label=concept_name,
            omop_concept_id=omop_concept_id,
            properties={
                "concept_name": concept_name,
                "domain": domain.value,
            },
        )
        node_id = self.create_node(node_input)

        # Create edge from patient to concept node with patient-specific metadata
        patient_node_id = self.get_patient_node(patient_id)
        if patient_node_id is None:
            patient_node_id = self.create_patient_node(patient_id)

        edge_type = self.domain_to_edge_type(domain)
        edge_input = EdgeInput(
            patient_id=patient_id,
            source_node_id=patient_node_id,
            target_node_id=node_id,
            edge_type=edge_type,
            fact_id=fact_id,
            properties={
                "assertion": assertion,
                "experiencer": experiencer,
                "is_negated": assertion == "absent",
                "is_uncertain": assertion == "possible",
                "fact_id": str(fact_id),
            },
            # Bi-temporal fields
            event_date=event_date,
            valid_from=valid_from,
            valid_to=valid_to,
            recorded_at=recorded_at,
            source_document_date=source_document_date,
            temporality=temporality,
            temporal_confidence=temporal_confidence,
        )
        self.create_edge(edge_input)

        return node_id

    def get_node_by_id(self, node_id: UUID) -> NodeInput | None:
        """Get a node by ID."""
        stmt = select(KGNode).where(KGNode.id == str(node_id))
        result = self._session.execute(stmt)
        node = result.scalar_one_or_none()

        if node is None:
            return None

        return NodeInput(
            patient_id=node.patient_id,
            node_type=node.node_type,
            label=node.label,
            omop_concept_id=node.omop_concept_id,
            properties=node.properties,
        )

    def get_nodes_for_patient(
        self,
        patient_id: str,
        node_type: NodeType | None = None,
    ) -> list[NodeInput]:
        """Get all nodes for a patient.

        Returns both patient-owned nodes (patient_id set) and shared concept
        nodes (patient_id=NULL) that are connected via edges for this patient.
        """
        # Patient-owned nodes (patient node itself, plus any non-concept nodes)
        patient_stmt = select(KGNode).where(KGNode.patient_id == patient_id)
        if node_type is not None:
            patient_stmt = patient_stmt.where(KGNode.node_type == node_type)
        patient_nodes = self._session.execute(patient_stmt).scalars().all()

        # Shared concept nodes connected to this patient via edges
        concept_stmt = (
            select(KGNode)
            .join(
                KGEdge,
                or_(
                    KGEdge.target_node_id == KGNode.id,
                    KGEdge.source_node_id == KGNode.id,
                ),
            )
            .where(KGEdge.patient_id == patient_id)
            .where(KGNode.patient_id.is_(None))
        )
        if node_type is not None:
            concept_stmt = concept_stmt.where(KGNode.node_type == node_type)
        concept_nodes = self._session.execute(concept_stmt).scalars().all()

        # Combine and deduplicate
        seen_ids: set[str] = set()
        nodes: list[KGNode] = []
        for n in list(patient_nodes) + list(concept_nodes):
            if n.id not in seen_ids:
                seen_ids.add(n.id)
                nodes.append(n)

        return [
            NodeInput(
                patient_id=n.patient_id,
                node_type=n.node_type,
                label=n.label,
                omop_concept_id=n.omop_concept_id,
                properties=n.properties,
            )
            for n in nodes
        ]

    def get_edges_for_patient(
        self,
        patient_id: str,
        edge_type: EdgeType | None = None,
    ) -> list[EdgeInput]:
        """Get all edges for a patient."""
        stmt = select(KGEdge).where(KGEdge.patient_id == patient_id)
        if edge_type is not None:
            stmt = stmt.where(KGEdge.edge_type == edge_type)

        result = self._session.execute(stmt)
        edges = result.scalars().all()

        return [
            EdgeInput(
                patient_id=e.patient_id,
                source_node_id=UUID(e.source_node_id),
                target_node_id=UUID(e.target_node_id),
                edge_type=e.edge_type,
                fact_id=UUID(e.fact_id) if e.fact_id else None,
                properties=e.properties,
            )
            for e in edges
        ]

    def _prime_caches(self, patient_id: str) -> None:
        """Pre-load all existing nodes/edges into caches to avoid per-item DB lookups.

        Loads both patient-owned nodes and shared concept nodes that are
        connected to this patient via edges.
        """
        # Load patient-owned nodes
        stmt = select(KGNode).where(KGNode.patient_id == patient_id)
        result = self._session.execute(stmt)
        patient_nodes = result.scalars().all()

        # Also load shared concept nodes connected by this patient's edges
        shared_stmt = (
            select(KGNode)
            .join(
                KGEdge,
                or_(
                    KGEdge.target_node_id == KGNode.id,
                    KGEdge.source_node_id == KGNode.id,
                ),
            )
            .where(KGEdge.patient_id == patient_id)
            .where(KGNode.patient_id.is_(None))
        )
        shared_result = self._session.execute(shared_stmt)
        shared_nodes = shared_result.scalars().all()

        # If no shared nodes found via edges (first build for this patient),
        # preload recent shared concept nodes to avoid per-item SELECTs
        if not shared_nodes:
            recent_shared_stmt = (
                select(KGNode)
                .where(KGNode.patient_id.is_(None))
                .where(KGNode.omop_concept_id.isnot(None))
                .order_by(KGNode.created_at.desc())
                .limit(500)
            )
            recent_shared_result = self._session.execute(recent_shared_stmt)
            shared_nodes = list(recent_shared_result.scalars().all())
            logger.debug(
                f"Primed {len(shared_nodes)} recent shared concept nodes for first-patient build"
            )

        all_nodes = list(patient_nodes) + list(shared_nodes)

        for node in all_nodes:
            node_id = UUID(node.id)
            if node.node_type == NodeType.PATIENT:
                self._patient_node_cache[patient_id] = node_id
            else:
                dedup_key = self.calculate_node_dedup_key(
                    node.patient_id, node.node_type, node.omop_concept_id
                )
                self._node_dedup_cache[dedup_key] = node_id

            node_input = NodeInput(
                patient_id=node.patient_id,
                node_type=node.node_type,
                label=node.label,
                omop_concept_id=node.omop_concept_id,
                properties=node.properties,
            )
            self._uuid_to_node[node_id] = node_input

        self._pending_flush = True
        logger.debug(
            f"Primed caches for patient {patient_id}: "
            f"{len(patient_nodes)} patient nodes, {len(shared_nodes)} shared concept nodes"
        )

    def _batch_create_nodes(self, node_inputs: list[NodeInput]) -> dict[str, UUID]:
        """Batch create nodes, returning dedup_key -> node_id map.

        1. Compute dedup keys, filter out cached
        2. Batch SELECT for existing shared concepts
        3. Bulk INSERT ... ON CONFLICT DO NOTHING for new nodes
        4. Re-query for conflicted rows to get IDs
        5. Update caches
        """
        result_map: dict[str, UUID] = {}
        if not node_inputs:
            return result_map

        # Normalize concept nodes to shared (patient_id=None)
        normalized: list[tuple[NodeInput, str]] = []  # (node_input, dedup_key)
        for ni in node_inputs:
            is_concept = (
                ni.node_type != NodeType.PATIENT
                and ni.omop_concept_id is not None
            )
            if is_concept:
                ni = NodeInput(
                    patient_id=None,
                    node_type=ni.node_type,
                    label=ni.label,
                    omop_concept_id=ni.omop_concept_id,
                    properties=ni.properties,
                )
            dedup_key = self.calculate_node_dedup_key(
                ni.patient_id, ni.node_type, ni.omop_concept_id
            )
            # Skip if already in cache
            if dedup_key in self._node_dedup_cache:
                result_map[dedup_key] = self._node_dedup_cache[dedup_key]
            else:
                normalized.append((ni, dedup_key))

        if not normalized:
            return result_map

        # Separate shared concepts from non-concept nodes
        concept_nodes: list[tuple[NodeInput, str]] = []
        other_nodes: list[tuple[NodeInput, str]] = []
        for ni, dk in normalized:
            if ni.patient_id is None and ni.omop_concept_id is not None:
                concept_nodes.append((ni, dk))
            else:
                other_nodes.append((ni, dk))

        # --- Batch handle shared concept nodes ---
        if concept_nodes:
            # Deduplicate by (node_type, omop_concept_id) within the batch
            seen_concepts: dict[tuple[str, int], tuple[NodeInput, str]] = {}
            for ni, dk in concept_nodes:
                key = (ni.node_type.value if hasattr(ni.node_type, 'value') else ni.node_type, ni.omop_concept_id)
                if key not in seen_concepts:
                    seen_concepts[key] = (ni, dk)

            unique_concepts = list(seen_concepts.values())

            # Batch SELECT existing
            type_concept_pairs = [
                (ni.node_type, ni.omop_concept_id)
                for ni, _ in unique_concepts
            ]
            existing_stmt = (
                select(KGNode)
                .where(KGNode.patient_id.is_(None))
                .where(
                    tuple_(KGNode.node_type, KGNode.omop_concept_id).in_(
                        type_concept_pairs
                    )
                )
            )
            existing_rows = self._session.execute(existing_stmt).scalars().all()

            # Map existing by (node_type, omop_concept_id)
            existing_map: dict[tuple, KGNode] = {}
            for row in existing_rows:
                existing_map[(row.node_type, row.omop_concept_id)] = row

            # Separate found vs. new
            to_insert: list[tuple[NodeInput, str, str]] = []  # (ni, dk, pre-generated id)
            for ni, dk in unique_concepts:
                existing = existing_map.get((ni.node_type, ni.omop_concept_id))
                if existing:
                    node_id = UUID(existing.id)
                    result_map[dk] = node_id
                    self._node_dedup_cache[dk] = node_id
                    self._uuid_to_node[node_id] = ni
                else:
                    new_id = str(uuid4())
                    to_insert.append((ni, dk, new_id))

            # Bulk INSERT ... ON CONFLICT DO NOTHING
            if to_insert:
                insert_values = [
                    {
                        "id": new_id,
                        "patient_id": None,
                        "node_type": ni.node_type,
                        "omop_concept_id": ni.omop_concept_id,
                        "label": ni.label,
                        "properties": ni.properties,
                    }
                    for ni, _, new_id in to_insert
                ]

                stmt = pg_insert(KGNode).values(insert_values)
                stmt = stmt.on_conflict_do_nothing(
                    index_elements=["node_type", "omop_concept_id"],
                    index_where=KGNode.__table__.c.patient_id.is_(None)
                    & KGNode.__table__.c.omop_concept_id.is_not(None)
                    & KGNode.__table__.c.deleted_at.is_(None),
                )
                self._session.execute(stmt)
                self._session.flush()

                # Re-query to get IDs for any that conflicted (concurrent insert)
                requery_pairs = [
                    (ni.node_type, ni.omop_concept_id)
                    for ni, _, _ in to_insert
                ]
                requery_stmt = (
                    select(KGNode)
                    .where(KGNode.patient_id.is_(None))
                    .where(
                        tuple_(KGNode.node_type, KGNode.omop_concept_id).in_(
                            requery_pairs
                        )
                    )
                )
                requeried = self._session.execute(requery_stmt).scalars().all()
                requery_map: dict[tuple, str] = {}
                for row in requeried:
                    requery_map[(row.node_type, row.omop_concept_id)] = row.id

                for ni, dk, pre_id in to_insert:
                    actual_id_str = requery_map.get(
                        (ni.node_type, ni.omop_concept_id), pre_id
                    )
                    node_id = UUID(actual_id_str)
                    result_map[dk] = node_id
                    self._node_dedup_cache[dk] = node_id
                    self._uuid_to_node[node_id] = ni

            # Map duplicate concept_nodes entries to the same IDs
            for ni, dk in concept_nodes:
                if dk not in result_map:
                    key = (ni.node_type.value if hasattr(ni.node_type, 'value') else ni.node_type, ni.omop_concept_id)
                    canonical_ni, canonical_dk = seen_concepts[key]
                    if canonical_dk in result_map:
                        result_map[dk] = result_map[canonical_dk]
                        self._node_dedup_cache[dk] = result_map[canonical_dk]

        # --- Batch handle non-concept nodes ---
        if other_nodes:
            insert_values = []
            id_map: list[tuple[str, str, NodeInput]] = []  # (dk, new_id, ni)
            for ni, dk in other_nodes:
                new_id = str(uuid4())
                insert_values.append({
                    "id": new_id,
                    "patient_id": ni.patient_id,
                    "node_type": ni.node_type,
                    "omop_concept_id": ni.omop_concept_id,
                    "label": ni.label,
                    "properties": ni.properties,
                })
                id_map.append((dk, new_id, ni))

            self._session.execute(pg_insert(KGNode).values(insert_values))
            self._session.flush()

            for dk, new_id, ni in id_map:
                node_id = UUID(new_id)
                result_map[dk] = node_id
                self._node_dedup_cache[dk] = node_id
                self._uuid_to_node[node_id] = ni

        return result_map

    def _batch_create_edges(self, edge_inputs: list[EdgeInput]) -> list[UUID]:
        """Batch create edges.

        1. Batch SELECT existing: WHERE (source_node_id, target_node_id, edge_type) IN (...)
        2. Filter out existing
        3. Bulk insert new edges preserving all temporal fields
        """
        if not edge_inputs:
            return []

        result_ids: list[UUID] = []

        # Batch SELECT existing edges
        edge_keys = [
            (str(ei.source_node_id), str(ei.target_node_id), ei.edge_type)
            for ei in edge_inputs
        ]
        existing_stmt = (
            select(KGEdge)
            .where(
                tuple_(
                    KGEdge.source_node_id,
                    KGEdge.target_node_id,
                    KGEdge.edge_type,
                ).in_(edge_keys)
            )
        )
        existing_rows = self._session.execute(existing_stmt).scalars().all()

        # Build set of existing edge keys
        existing_set: set[tuple[str, str, str]] = set()
        existing_id_map: dict[tuple[str, str, str], str] = {}
        for row in existing_rows:
            edge_type_val = row.edge_type.value if hasattr(row.edge_type, 'value') else row.edge_type
            key = (row.source_node_id, row.target_node_id, edge_type_val)
            existing_set.add(key)
            existing_id_map[key] = row.id

        # Separate new vs existing
        to_insert: list[tuple[EdgeInput, str]] = []  # (edge_input, new_id)
        for ei in edge_inputs:
            edge_type_val = ei.edge_type.value if hasattr(ei.edge_type, 'value') else ei.edge_type
            key = (str(ei.source_node_id), str(ei.target_node_id), edge_type_val)
            if key in existing_set:
                result_ids.append(UUID(existing_id_map[key]))
            else:
                new_id = str(uuid4())
                to_insert.append((ei, new_id))
                existing_set.add(key)  # Prevent duplicates within the batch
                existing_id_map[key] = new_id  # Allow subsequent dupes to find the ID

        # Bulk insert new edges
        if to_insert:
            insert_values = [
                {
                    "id": new_id,
                    "patient_id": ei.patient_id,
                    "source_node_id": str(ei.source_node_id),
                    "target_node_id": str(ei.target_node_id),
                    "edge_type": ei.edge_type,
                    "fact_id": str(ei.fact_id) if ei.fact_id else None,
                    "properties": ei.properties,
                    "event_date": ei.event_date,
                    "valid_from": ei.valid_from,
                    "valid_to": ei.valid_to,
                    "recorded_at": ei.recorded_at,
                    "source_document_date": ei.source_document_date,
                    "temporality": ei.temporality,
                    "temporal_order": ei.temporal_order.value if ei.temporal_order else None,
                    "temporal_confidence": ei.temporal_confidence,
                }
                for ei, new_id in to_insert
            ]

            self._session.execute(pg_insert(KGEdge).values(insert_values))
            self._session.flush()

            for ei, new_id in to_insert:
                result_ids.append(UUID(new_id))

        return result_ids

    def build_graph_for_patient(self, patient_id: str) -> GraphResult:
        """Build the complete knowledge graph for a patient.

        Uses batch operations to minimize DB roundtrips (~8 instead of ~404):
        1. Prime caches (1 query for patient nodes + 1 for shared concepts)
        2. Ensure patient node (0-1 queries)
        3. Query all facts (1 query)
        4. Collect all NodeInput objects from facts
        5. Batch create nodes (2-3 queries: SELECT + INSERT + re-query)
        6. Collect all EdgeInput objects using node IDs
        7. Batch create edges (1-2 queries: SELECT + INSERT)
        8. Sync to Neo4j

        Extracts temporal data from ClinicalFact and populates bi-temporal
        fields on the resulting KGEdge.

        After building the PostgreSQL graph, syncs to Neo4j for graph queries.
        """
        # Prime caches: load all existing nodes in one query
        self._prime_caches(patient_id)

        # Create patient node
        existing_patient = self.get_patient_node(patient_id)
        if existing_patient is None:
            self.create_patient_node(patient_id)

        patient_node_id = self._patient_node_cache[patient_id]

        # Get all facts for patient
        stmt = select(ClinicalFact).where(ClinicalFact.patient_id == patient_id)
        result = self._session.execute(stmt)
        facts = result.scalars().all()

        if not facts:
            all_nodes = list(self._uuid_to_node.values())
            all_edges = self.get_edges_for_patient(patient_id)
            self._sync_to_neo4j(patient_id, all_nodes, all_edges)
            return GraphResult(
                patient_id=patient_id,
                node_count=len(all_nodes),
                edge_count=len(all_edges),
                nodes_created=0,
                edges_created=0,
            )

        # Step 4: Collect all NodeInput objects from facts
        node_inputs: list[NodeInput] = []
        fact_to_node_type: list[tuple[object, NodeType, str]] = []  # (fact, node_type, dedup_key)
        for fact in facts:
            node_type = self.domain_to_node_type(fact.domain)
            node_input = NodeInput(
                patient_id=None,  # Shared concept
                node_type=node_type,
                label=fact.concept_name,
                omop_concept_id=fact.omop_concept_id,
                properties={
                    "concept_name": fact.concept_name,
                    "domain": fact.domain.value,
                },
            )
            pid_for_dedup = None if fact.omop_concept_id is not None else patient_id
            dedup_key = self.calculate_node_dedup_key(
                pid_for_dedup, node_type, fact.omop_concept_id
            )
            node_inputs.append(node_input)
            fact_to_node_type.append((fact, node_type, dedup_key))

        # Step 5: Batch create all nodes
        pre_batch_cache_size = len(self._node_dedup_cache)
        dedup_to_id = self._batch_create_nodes(node_inputs)

        # Merge batch results with existing cache
        nodes_created = len(self._node_dedup_cache) - pre_batch_cache_size

        # Step 6: Collect all EdgeInput objects
        edge_inputs: list[EdgeInput] = []
        for i, (fact, node_type, dedup_key) in enumerate(fact_to_node_type):
            target_node_id = dedup_to_id.get(dedup_key) or self._node_dedup_cache.get(dedup_key)
            if target_node_id is None:
                logger.warning(
                    f"No node found for dedup_key={dedup_key}, skipping edge for fact {fact.id}"
                )
                continue

            edge_type = self.domain_to_edge_type(fact.domain)
            edge_input = EdgeInput(
                patient_id=patient_id,
                source_node_id=patient_node_id,
                target_node_id=target_node_id,
                edge_type=edge_type,
                fact_id=UUID(fact.id),
                properties={
                    "assertion": fact.assertion.value,
                    "experiencer": fact.experiencer.value,
                    "is_negated": fact.assertion.value == "absent",
                    "is_uncertain": fact.assertion.value == "possible",
                    "fact_id": str(fact.id),
                },
                event_date=fact.start_date,
                valid_from=fact.start_date,
                valid_to=fact.end_date,
                recorded_at=None,
                source_document_date=fact.created_at,
                temporality=fact.temporality.value,
                temporal_confidence=fact.confidence,
            )
            edge_inputs.append(edge_input)

        # Step 7: Batch create all edges
        pre_edge_count = len(self.get_edges_for_patient(patient_id))
        self._batch_create_edges(edge_inputs)

        # Step 7b: Materialize concept→concept edges from OMOP lateral relationships
        concept_edges_created = self._materialize_concept_edges(patient_id)

        # Use cached node/edge data instead of re-querying for totals
        all_nodes = list(self._uuid_to_node.values())
        all_edges = self.get_edges_for_patient(patient_id)
        edges_created = len(all_edges) - pre_edge_count

        # Sync to Neo4j using batched operations
        self._sync_to_neo4j(patient_id, all_nodes, all_edges)

        # Invalidate traversal cache after graph rebuild
        try:
            from app.services.kg_cache_service import invalidate_traversal_cache
            invalidate_traversal_cache(patient_id)
        except Exception:
            pass

        return GraphResult(
            patient_id=patient_id,
            node_count=len(all_nodes),
            edge_count=len(all_edges),
            nodes_created=nodes_created,
            edges_created=edges_created,
        )

    # Map OMOP relationship_id values to KG EdgeType for concept→concept edges.
    # Only lateral (non-hierarchical) relationships that add clinical value.
    OMOP_REL_TO_EDGE_TYPE: dict[str, EdgeType] = {
        "May treat": EdgeType.DRUG_TREATS,
        "May be treated by": EdgeType.CONDITION_TREATED_BY,
        "May cause": EdgeType.MAY_CAUSE,
        "Has finding site": EdgeType.HAS_FINDING_SITE,
        "Has causative agent": EdgeType.CAUSED_BY,
        "Has asso morph": EdgeType.HAS_MORPHOLOGY,
    }

    def _materialize_concept_edges(self, patient_id: str) -> int:
        """Create concept→concept edges from OMOP lateral relationships.

        Queries omop_concept_relationship for lateral relationships between
        concepts already in this patient's graph, then creates KGEdges.

        Returns:
            Number of concept→concept edges created.
        """
        # 1. Collect omop_concept_ids from shared concept nodes in patient graph
        concept_nodes = {
            node_id: node_input
            for node_id, node_input in self._uuid_to_node.items()
            if node_input.omop_concept_id and node_input.patient_id is None
        }
        concept_ids = [n.omop_concept_id for n in concept_nodes.values()]
        if len(concept_ids) < 2:
            return 0

        # Build reverse lookup: omop_concept_id -> node UUID
        omop_to_uuid: dict[int, UUID] = {}
        for node_id, node_input in concept_nodes.items():
            # First match wins (shared concepts are deduplicated)
            if node_input.omop_concept_id not in omop_to_uuid:
                omop_to_uuid[node_input.omop_concept_id] = node_id

        # 2. Query concept_relationships for lateral rels between patient's concepts
        # Note: ORM uses 'concept_relationships', Alembic/OMOP uses 'omop_concept_relationship'
        # We try concept_relationships first (ORM tables), fall back to omop_concept_relationship
        rel_names = list(self.OMOP_REL_TO_EDGE_TYPE.keys())
        sql = text("""
            SELECT cr.concept_id_1, cr.concept_id_2, cr.relationship_id
            FROM concept_relationships cr
            WHERE cr.concept_id_1 = ANY(:ids)
              AND cr.concept_id_2 = ANY(:ids)
              AND cr.relationship_id = ANY(:rels)
              AND cr.invalid_reason IS NULL
        """)
        try:
            rows = self._session.execute(
                sql, {"ids": concept_ids, "rels": rel_names}
            ).fetchall()
        except Exception as e:
            logger.warning(
                "Failed to query omop_concept_relationship for concept edges: %s", e
            )
            return 0

        if not rows:
            return 0

        # 3. Map to EdgeInput, skipping self-loops
        edge_inputs: list[EdgeInput] = []
        for row in rows:
            concept_id_1, concept_id_2, relationship_id = row[0], row[1], row[2]
            if concept_id_1 == concept_id_2:
                continue

            edge_type = self.OMOP_REL_TO_EDGE_TYPE.get(relationship_id)
            if edge_type is None:
                continue

            source_uuid = omop_to_uuid.get(concept_id_1)
            target_uuid = omop_to_uuid.get(concept_id_2)
            if source_uuid is None or target_uuid is None:
                continue

            edge_inputs.append(EdgeInput(
                patient_id=patient_id,
                source_node_id=source_uuid,
                target_node_id=target_uuid,
                edge_type=edge_type,
                properties={
                    "source": "omop_concept_relationship",
                    "relationship_id": relationship_id,
                },
            ))

        if not edge_inputs:
            return 0

        # 4. Batch create (dedup handled by _batch_create_edges)
        created = self._batch_create_edges(edge_inputs)
        logger.info(
            "Materialized %d concept→concept edges for patient %s from %d OMOP relationships",
            len(created), patient_id, len(rows),
        )
        return len(created)

    def _sync_to_neo4j(
        self,
        patient_id: str,
        nodes: list[NodeInput],
        edges: list[EdgeInput],
    ) -> None:
        """Sync patient graph to Neo4j using batched operations.

        Uses UNWIND for bulk node/edge creation instead of per-item MERGE.
        Gracefully handles Neo4j being unavailable.
        """
        graph_db = get_graph_database_service()

        # Check if Neo4j is available
        if not graph_db.is_connected:
            if graph_db.is_mock_mode:
                logger.debug(
                    f"Neo4j in mock mode, skipping sync for patient {patient_id}"
                )
            else:
                logger.warning(
                    f"Neo4j not available, skipping sync for patient {patient_id}"
                )
            return

        try:
            # Create or update patient node in Neo4j
            patient_cypher = """
            MERGE (p:Patient {patient_id: $patient_id})
            SET p.label = $label,
                p.updated_at = datetime()
            RETURN p
            """
            graph_db.execute_write(
                patient_cypher,
                {"patient_id": patient_id, "label": f"Patient {patient_id}"},
            )

            # Batch create/update all clinical fact nodes with UNWIND
            # Shared concept nodes use {node_type}_{omop_concept_id} as ID
            # so Neo4j naturally merges the same concept across patients.
            non_patient_nodes = [n for n in nodes if n.node_type != NodeType.PATIENT]
            if non_patient_nodes:
                node_batch = []
                for n in non_patient_nodes:
                    if n.patient_id is None and n.omop_concept_id is not None:
                        # Shared concept node - global ID without patient prefix
                        neo4j_id = f"{n.node_type.value}_{n.omop_concept_id}"
                    else:
                        # Non-concept node with patient_id (edge case)
                        neo4j_id = f"{patient_id}_{n.node_type.value}_{n.omop_concept_id or n.label}"
                    node_batch.append({
                        "node_id": neo4j_id,
                        "label": n.label,
                        "node_type": n.node_type.value,
                        "omop_concept_id": n.omop_concept_id,
                        "properties": json.dumps(n.properties),
                    })
                batch_node_cypher = """
                UNWIND $nodes AS row
                MERGE (n:ClinicalFact {node_id: row.node_id})
                SET n.label = row.label,
                    n.node_type = row.node_type,
                    n.omop_concept_id = row.omop_concept_id,
                    n.properties = row.properties,
                    n.updated_at = datetime()
                """
                graph_db.execute_write(batch_node_cypher, {"nodes": node_batch})

            # Batch create edges - group by edge type for efficiency
            edge_batches: dict[str, list[dict]] = {}
            for edge in edges:
                source_node = self._find_node_by_uuid(edge.source_node_id)
                target_node = self._find_node_by_uuid(edge.target_node_id)

                if source_node is None or target_node is None:
                    continue

                if source_node.node_type == NodeType.PATIENT:
                    source_id = patient_id
                    source_label = "Patient"
                elif source_node.patient_id is None and source_node.omop_concept_id is not None:
                    source_id = f"{source_node.node_type.value}_{source_node.omop_concept_id}"
                    source_label = "ClinicalFact"
                else:
                    source_id = f"{patient_id}_{source_node.node_type.value}_{source_node.omop_concept_id or source_node.label}"
                    source_label = "ClinicalFact"

                if target_node.node_type == NodeType.PATIENT:
                    target_id = patient_id
                    target_label = "Patient"
                elif target_node.patient_id is None and target_node.omop_concept_id is not None:
                    target_id = f"{target_node.node_type.value}_{target_node.omop_concept_id}"
                    target_label = "ClinicalFact"
                else:
                    target_id = f"{patient_id}_{target_node.node_type.value}_{target_node.omop_concept_id or target_node.label}"
                    target_label = "ClinicalFact"

                rel_type = edge.edge_type.value.upper().replace(' ', '_')
                batch_key = f"{source_label}|{target_label}|{rel_type}"

                if batch_key not in edge_batches:
                    edge_batches[batch_key] = []
                edge_batches[batch_key].append({
                    "source_id": source_id,
                    "target_id": target_id,
                    "edge_type": edge.edge_type.value,
                    "properties": json.dumps(edge.properties),
                    "temporality": edge.temporality,
                    "event_date": edge.event_date.isoformat() if edge.event_date else None,
                    "valid_from": edge.valid_from.isoformat() if edge.valid_from else None,
                    "valid_to": edge.valid_to.isoformat() if edge.valid_to else None,
                    "temporal_confidence": edge.temporal_confidence,
                    "temporal_order": edge.temporal_order.value if edge.temporal_order else None,
                })

            # Execute one UNWIND query per edge-type group
            for batch_key, batch_data in edge_batches.items():
                source_label, target_label, rel_type = batch_key.split("|")
                source_key = 'patient_id' if source_label == 'Patient' else 'node_id'
                target_key = 'patient_id' if target_label == 'Patient' else 'node_id'
                edge_cypher = f"""
                UNWIND $edges AS row
                MATCH (s:{source_label} {{{source_key}: row.source_id}})
                MATCH (t:{target_label} {{{target_key}: row.target_id}})
                MERGE (s)-[r:{rel_type}]->(t)
                SET r.edge_type = row.edge_type,
                    r.properties = row.properties,
                    r.temporality = row.temporality,
                    r.event_date = row.event_date,
                    r.valid_from = row.valid_from,
                    r.valid_to = row.valid_to,
                    r.temporal_confidence = row.temporal_confidence,
                    r.temporal_order = row.temporal_order,
                    r.updated_at = datetime()
                """
                graph_db.execute_write(edge_cypher, {"edges": batch_data})

            logger.info(
                f"Synced {len(nodes)} nodes and {len(edges)} edges to Neo4j "
                f"for patient {patient_id} (batched)"
            )

        except Exception as e:
            # Log error but don't fail - PostgreSQL graph is still valid
            DegradationContext.record_stage_failure("neo4j_sync", e, None)
            logger.error(
                f"Failed to sync graph to Neo4j for patient {patient_id}: {e}"
            )

    def _find_node_by_uuid(
        self,
        node_uuid: UUID,
    ) -> NodeInput | None:
        """Find a node by UUID using O(1) reverse map lookup."""
        return self._uuid_to_node.get(node_uuid)

    def get_patient_graph(self, patient_id: str) -> PatientGraph:
        """Get the complete graph for a patient.

        Returns a PatientGraph schema with all nodes and edges,
        including bi-temporal fields on edges. Includes both patient-owned
        nodes and shared concept nodes connected via edges.
        """
        # Patient-owned nodes
        patient_node_stmt = select(KGNode).where(KGNode.patient_id == patient_id)
        patient_nodes = self._session.execute(patient_node_stmt).scalars().all()

        # Shared concept nodes connected via edges
        concept_node_stmt = (
            select(KGNode)
            .join(
                KGEdge,
                or_(
                    KGEdge.target_node_id == KGNode.id,
                    KGEdge.source_node_id == KGNode.id,
                ),
            )
            .where(KGEdge.patient_id == patient_id)
            .where(KGNode.patient_id.is_(None))
        )
        concept_nodes = self._session.execute(concept_node_stmt).scalars().all()

        # Combine and deduplicate
        seen_ids: set[str] = set()
        nodes: list[KGNode] = []
        for n in list(patient_nodes) + list(concept_nodes):
            if n.id not in seen_ids:
                seen_ids.add(n.id)
                nodes.append(n)

        # Get all edges for this patient
        edge_stmt = select(KGEdge).where(KGEdge.patient_id == patient_id)
        edge_result = self._session.execute(edge_stmt)
        edges = edge_result.scalars().all()

        return PatientGraph(
            patient_id=patient_id,
            nodes=[
                {
                    "id": UUID(n.id),
                    "patient_id": n.patient_id,
                    "node_type": n.node_type,
                    "omop_concept_id": n.omop_concept_id,
                    "label": n.label,
                    "properties": n.properties,
                    "created_at": n.created_at,
                }
                for n in nodes
            ],
            edges=[
                {
                    "id": UUID(e.id),
                    "patient_id": e.patient_id,
                    "source_node_id": UUID(e.source_node_id),
                    "target_node_id": UUID(e.target_node_id),
                    "edge_type": e.edge_type,
                    "fact_id": UUID(e.fact_id) if e.fact_id else None,
                    "properties": e.properties,
                    # Valid Time
                    "event_date": e.event_date,
                    "valid_from": e.valid_from,
                    "valid_to": e.valid_to,
                    # Transaction Time
                    "recorded_at": e.recorded_at,
                    "source_document_date": e.source_document_date,
                    # Temporal Assertion
                    "temporality": e.temporality,
                    "temporal_order": e.temporal_order,
                    "temporal_confidence": e.temporal_confidence,
                    "created_at": e.created_at,
                }
                for e in edges
            ],
        )

    def get_negated_nodes(self, patient_id: str) -> list[NodeInput]:
        """Get all negated finding nodes for a patient.

        With shared concept nodes, negation is stored on the edge (per-patient
        assertion), not on the node itself.
        """
        edges = self.get_edges_for_patient(patient_id)
        negated_node_ids: set[UUID] = set()
        for edge in edges:
            if edge.properties.get("is_negated", False):
                negated_node_ids.add(edge.target_node_id)

        if not negated_node_ids:
            return []

        # Fetch the actual nodes
        results = []
        for nid in negated_node_ids:
            node = self.get_node_by_id(nid)
            if node is not None:
                results.append(node)
        return results
