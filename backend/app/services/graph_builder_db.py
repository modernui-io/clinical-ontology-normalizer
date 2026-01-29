"""Database-backed Knowledge Graph builder service.

Implements graph construction with database persistence.
Supports bi-temporal model for temporal reasoning.
"""

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

        # Get final counts
        all_nodes = self.get_nodes_for_patient(patient_id)
        all_edges = self.get_edges_for_patient(patient_id)

        return GraphResult(
            patient_id=patient_id,
            node_count=len(all_nodes),
            edge_count=len(all_edges),
            nodes_created=nodes_created,
            edges_created=edges_created,
        )

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
