"""Database-backed Knowledge Graph builder service.

Implements graph construction with database persistence.
Supports bi-temporal model for temporal reasoning.
Syncs graphs to Neo4j for graph queries and visualization.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.clinical_fact import ClinicalFact
from app.models.knowledge_graph import KGEdge, KGNode
from app.schemas.base import Domain
from app.schemas.knowledge_graph import EdgeType, NodeType, PatientGraph
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
        """Create a node in the knowledge graph."""
        # Calculate dedup key
        dedup_key = self.calculate_node_dedup_key(
            node_input.patient_id,
            node_input.node_type,
            node_input.omop_concept_id,
        )

        # Check cache
        if dedup_key in self._node_dedup_cache:
            return self._node_dedup_cache[dedup_key]

        # Check database
        stmt = select(KGNode).where(KGNode.patient_id == node_input.patient_id)
        if node_input.omop_concept_id:
            stmt = stmt.where(KGNode.omop_concept_id == node_input.omop_concept_id)
        stmt = stmt.where(KGNode.node_type == node_input.node_type)

        result = self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            node_id = UUID(existing.id)
            self._node_dedup_cache[dedup_key] = node_id
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
            temporal_order=edge_input.temporal_order.value if edge_input.temporal_order else None,
            temporal_confidence=edge_input.temporal_confidence,
        )
        self._session.add(edge)
        self._session.flush()

        return UUID(edge.id)

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

        Creates a node for the fact and an edge connecting it to the patient node.
        Populates bi-temporal fields for temporal reasoning.
        """
        # Create the fact node
        node_type = self.domain_to_node_type(domain)
        node_input = NodeInput(
            patient_id=patient_id,
            node_type=node_type,
            label=concept_name,
            omop_concept_id=omop_concept_id,
            properties={
                "assertion": assertion,
                "temporality": temporality,
                "experiencer": experiencer,
                "fact_id": str(fact_id),
                "is_negated": assertion == "absent",
                "is_uncertain": assertion == "possible",
            },
        )
        node_id = self.create_node(node_input)

        # Create edge from patient to fact node
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
            properties={"assertion": assertion},
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
        """Get all nodes for a patient."""
        stmt = select(KGNode).where(KGNode.patient_id == patient_id)
        if node_type is not None:
            stmt = stmt.where(KGNode.node_type == node_type)

        result = self._session.execute(stmt)
        nodes = result.scalars().all()

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

    def build_graph_for_patient(self, patient_id: str) -> GraphResult:
        """Build the complete knowledge graph for a patient.

        Extracts temporal data from ClinicalFact and populates bi-temporal
        fields on the resulting KGEdge:
        - start_date → valid_from (start of validity period)
        - end_date → valid_to (end of validity period)
        - start_date → event_date (when event occurred, if no explicit event_date)
        - created_at → source_document_date (when recorded)
        - temporality → temporality (current/past/future from NLP)
        - confidence → temporal_confidence

        After building the PostgreSQL graph, syncs to Neo4j for graph queries.
        """
        nodes_created = 0
        edges_created = 0

        # Create patient node
        existing_patient = self.get_patient_node(patient_id)
        if existing_patient is None:
            self.create_patient_node(patient_id)
            nodes_created += 1

        # Get all facts for patient
        stmt = select(ClinicalFact).where(ClinicalFact.patient_id == patient_id)
        result = self._session.execute(stmt)
        facts = result.scalars().all()

        # Project each fact to graph
        for fact in facts:
            # Check if node already exists
            node_type = self.domain_to_node_type(fact.domain)
            dedup_key = self.calculate_node_dedup_key(patient_id, node_type, fact.omop_concept_id)
            node_exists = dedup_key in self._node_dedup_cache

            # Extract temporal data from ClinicalFact
            # - start_date is when the clinical event began (valid_from)
            # - end_date is when the clinical event ended (valid_to)
            # - For point-in-time events, start_date is the event_date
            # - created_at is when the record was created (source_document_date)
            event_date = fact.start_date  # Point in time event
            valid_from = fact.start_date  # Start of validity
            valid_to = fact.end_date  # End of validity (None = ongoing)
            source_document_date = fact.created_at  # When record was created

            self.project_fact_to_graph(
                fact_id=UUID(fact.id),
                patient_id=patient_id,
                domain=fact.domain,
                omop_concept_id=fact.omop_concept_id,
                concept_name=fact.concept_name,
                assertion=fact.assertion.value,
                temporality=fact.temporality.value,
                experiencer=fact.experiencer.value,
                # Bi-temporal fields
                event_date=event_date,
                valid_from=valid_from,
                valid_to=valid_to,
                recorded_at=None,  # Could be populated from FactEvidence source
                source_document_date=source_document_date,
                temporal_confidence=fact.confidence,
            )

            if not node_exists:
                nodes_created += 1
                edges_created += 1

        # Get final counts and data for Neo4j sync
        all_nodes = self.get_nodes_for_patient(patient_id)
        all_edges = self.get_edges_for_patient(patient_id)

        # Sync to Neo4j for graph queries and visualization
        self._sync_to_neo4j(patient_id, all_nodes, all_edges)

        return GraphResult(
            patient_id=patient_id,
            node_count=len(all_nodes),
            edge_count=len(all_edges),
            nodes_created=nodes_created,
            edges_created=edges_created,
        )

    def _sync_to_neo4j(
        self,
        patient_id: str,
        nodes: list[NodeInput],
        edges: list[EdgeInput],
    ) -> None:
        """Sync patient graph to Neo4j for graph queries and visualization.

        This method gracefully handles Neo4j being unavailable:
        - If Neo4j is not connected, logs a warning and returns
        - PostgreSQL graph remains valid for local queries
        - System degrades gracefully without failing

        Args:
            patient_id: The patient ID to sync
            nodes: List of nodes to sync
            edges: List of edges to sync
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

            # Create or update clinical fact nodes
            for node in nodes:
                # Skip patient nodes (already created above)
                if node.node_type == NodeType.PATIENT:
                    continue

                # Generate a unique node ID based on patient + concept
                node_id = f"{patient_id}_{node.node_type.value}_{node.omop_concept_id or node.label}"

                node_cypher = """
                MERGE (n:ClinicalFact {node_id: $node_id})
                SET n.patient_id = $patient_id,
                    n.label = $label,
                    n.node_type = $node_type,
                    n.omop_concept_id = $omop_concept_id,
                    n.properties = $properties,
                    n.updated_at = datetime()
                """
                graph_db.execute_write(
                    node_cypher,
                    {
                        "node_id": node_id,
                        "patient_id": patient_id,
                        "label": node.label,
                        "node_type": node.node_type.value,
                        "omop_concept_id": node.omop_concept_id,
                        "properties": json.dumps(node.properties),
                    },
                )

            # Create edges between patient and clinical facts
            for edge in edges:
                # Generate node IDs for source and target
                source_node = self._find_node_by_uuid(nodes, edge.source_node_id)
                target_node = self._find_node_by_uuid(nodes, edge.target_node_id)

                if source_node is None or target_node is None:
                    logger.warning(
                        f"Could not find nodes for edge {edge.source_node_id} -> {edge.target_node_id}"
                    )
                    continue

                # Build source and target IDs
                if source_node.node_type == NodeType.PATIENT:
                    source_id = patient_id
                    source_label = "Patient"
                else:
                    source_id = f"{patient_id}_{source_node.node_type.value}_{source_node.omop_concept_id or source_node.label}"
                    source_label = "ClinicalFact"

                if target_node.node_type == NodeType.PATIENT:
                    target_id = patient_id
                    target_label = "Patient"
                else:
                    target_id = f"{patient_id}_{target_node.node_type.value}_{target_node.omop_concept_id or target_node.label}"
                    target_label = "ClinicalFact"

                # Create relationship with edge type
                # Use dynamic relationship type based on edge_type
                edge_cypher = f"""
                MATCH (s:{source_label} {{{('patient_id' if source_label == 'Patient' else 'node_id')}: $source_id}})
                MATCH (t:{target_label} {{{('patient_id' if target_label == 'Patient' else 'node_id')}: $target_id}})
                MERGE (s)-[r:{edge.edge_type.value.upper().replace(' ', '_')}]->(t)
                SET r.edge_type = $edge_type,
                    r.properties = $properties,
                    r.temporality = $temporality,
                    r.updated_at = datetime()
                RETURN r
                """
                graph_db.execute_write(
                    edge_cypher,
                    {
                        "source_id": source_id,
                        "target_id": target_id,
                        "edge_type": edge.edge_type.value,
                        "properties": json.dumps(edge.properties),
                        "temporality": edge.temporality,
                    },
                )

            logger.info(
                f"Synced {len(nodes)} nodes and {len(edges)} edges to Neo4j "
                f"for patient {patient_id}"
            )

        except Exception as e:
            # Log error but don't fail - PostgreSQL graph is still valid
            DegradationContext.record_stage_failure("neo4j_sync", e, None)
            logger.error(
                f"Failed to sync graph to Neo4j for patient {patient_id}: {e}"
            )

    def _find_node_by_uuid(
        self,
        nodes: list[NodeInput],
        node_uuid: UUID,
    ) -> NodeInput | None:
        """Find a node in the list by checking the dedup cache.

        Since NodeInput doesn't have a UUID, we need to look up the node
        based on the dedup key that maps to this UUID.

        Args:
            nodes: List of nodes to search
            node_uuid: UUID to find

        Returns:
            The matching NodeInput or None
        """
        # Reverse lookup in dedup cache
        for dedup_key, cached_uuid in self._node_dedup_cache.items():
            if cached_uuid == node_uuid:
                # Parse dedup key to find matching node
                # Key format: "patient_id:node_type:omop_concept_id"
                parts = dedup_key.split(":")
                if len(parts) >= 2:
                    patient_id = parts[0]
                    node_type_str = parts[1]
                    omop_id = int(parts[2]) if len(parts) > 2 and parts[2] else None

                    for node in nodes:
                        if (
                            node.patient_id == patient_id
                            and node.node_type.value == node_type_str
                            and node.omop_concept_id == omop_id
                        ):
                            return node

        # Check patient node cache
        for patient_id, cached_uuid in self._patient_node_cache.items():
            if cached_uuid == node_uuid:
                for node in nodes:
                    if node.node_type == NodeType.PATIENT and node.patient_id == patient_id:
                        return node

        return None

    def get_patient_graph(self, patient_id: str) -> PatientGraph:
        """Get the complete graph for a patient.

        Returns a PatientGraph schema with all nodes and edges,
        including bi-temporal fields on edges.
        """
        # Get all nodes
        node_stmt = select(KGNode).where(KGNode.patient_id == patient_id)
        node_result = self._session.execute(node_stmt)
        nodes = node_result.scalars().all()

        # Get all edges
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
        """Get all negated finding nodes for a patient."""
        nodes = self.get_nodes_for_patient(patient_id)
        return [n for n in nodes if n.properties.get("is_negated", False)]
