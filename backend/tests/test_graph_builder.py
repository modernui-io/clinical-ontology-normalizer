"""Tests for Knowledge Graph builder service.

Tests task 7.x: Validates graph construction, node/edge creation,
and patient graph structure.
"""

from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.clinical_fact import ClinicalFact
from app.models.knowledge_graph import KGEdge, KGNode
from app.schemas.base import Assertion, Domain, Experiencer, Temporality
from app.schemas.knowledge_graph import EdgeType, NodeType
from app.services.graph_builder import (
    BaseGraphBuilderService,
    EdgeInput,
    GraphResult,
    NodeInput,
)
from app.services.graph_builder_db import DatabaseGraphBuilderService

_graph_test_engine = create_engine(
    "sqlite:///:memory:",
    echo=False,
    future=True,
)
_GraphTestSession = sessionmaker(
    bind=_graph_test_engine,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="function")
def graph_session() -> Session:
    """Create a database session with graph and fact tables."""
    KGNode.__table__.create(bind=_graph_test_engine, checkfirst=True)
    KGEdge.__table__.create(bind=_graph_test_engine, checkfirst=True)
    ClinicalFact.__table__.create(bind=_graph_test_engine, checkfirst=True)

    session = _GraphTestSession()
    try:
        yield session
    finally:
        session.close()
        KGEdge.__table__.drop(bind=_graph_test_engine, checkfirst=True)
        KGNode.__table__.drop(bind=_graph_test_engine, checkfirst=True)
        ClinicalFact.__table__.drop(bind=_graph_test_engine, checkfirst=True)


class TestNodeInput:
    """Tests for NodeInput dataclass."""

    def test_create_node_input(self) -> None:
        """Test creating a NodeInput."""
        node_input = NodeInput(
            patient_id="P001",
            node_type=NodeType.CONDITION,
            label="Fever",
            omop_concept_id=437663,
        )
        assert node_input.patient_id == "P001"
        assert node_input.node_type == NodeType.CONDITION
        assert node_input.label == "Fever"

    def test_node_input_default_properties(self) -> None:
        """Test NodeInput default properties."""
        node_input = NodeInput(
            patient_id="P001",
            node_type=NodeType.PATIENT,
            label="Patient P001",
        )
        assert node_input.properties == {}
        assert node_input.omop_concept_id is None


class TestEdgeInput:
    """Tests for EdgeInput dataclass."""

    def test_create_edge_input(self) -> None:
        """Test creating an EdgeInput."""
        source_id = uuid4()
        target_id = uuid4()
        edge_input = EdgeInput(
            patient_id="P001",
            source_node_id=source_id,
            target_node_id=target_id,
            edge_type=EdgeType.HAS_CONDITION,
        )
        assert edge_input.source_node_id == source_id
        assert edge_input.target_node_id == target_id
        assert edge_input.edge_type == EdgeType.HAS_CONDITION


class TestGraphResult:
    """Tests for GraphResult dataclass."""

    def test_create_graph_result(self) -> None:
        """Test creating a GraphResult."""
        result = GraphResult(
            patient_id="P001",
            node_count=5,
            edge_count=4,
            nodes_created=3,
            edges_created=2,
        )
        assert result.patient_id == "P001"
        assert result.node_count == 5


class TestBaseGraphBuilderService:
    """Tests for BaseGraphBuilderService utilities."""

    def test_domain_to_node_type_condition(self) -> None:
        """Test domain to node type mapping for conditions."""
        builder = BaseGraphBuilderService()
        assert builder.domain_to_node_type(Domain.CONDITION) == NodeType.CONDITION

    def test_domain_to_node_type_drug(self) -> None:
        """Test domain to node type mapping for drugs."""
        builder = BaseGraphBuilderService()
        assert builder.domain_to_node_type(Domain.DRUG) == NodeType.DRUG

    def test_domain_to_node_type_measurement(self) -> None:
        """Test domain to node type mapping for measurements."""
        builder = BaseGraphBuilderService()
        assert builder.domain_to_node_type(Domain.MEASUREMENT) == NodeType.MEASUREMENT

    def test_domain_to_node_type_procedure(self) -> None:
        """Test domain to node type mapping for procedures."""
        builder = BaseGraphBuilderService()
        assert builder.domain_to_node_type(Domain.PROCEDURE) == NodeType.PROCEDURE

    def test_domain_to_edge_type_condition(self) -> None:
        """Test domain to edge type mapping for conditions."""
        builder = BaseGraphBuilderService()
        assert builder.domain_to_edge_type(Domain.CONDITION) == EdgeType.HAS_CONDITION

    def test_domain_to_edge_type_drug(self) -> None:
        """Test domain to edge type mapping for drugs."""
        builder = BaseGraphBuilderService()
        assert builder.domain_to_edge_type(Domain.DRUG) == EdgeType.TAKES_DRUG

    def test_calculate_node_dedup_key(self) -> None:
        """Test node deduplication key calculation."""
        builder = BaseGraphBuilderService()
        key = builder.calculate_node_dedup_key(
            patient_id="P001",
            node_type=NodeType.CONDITION,
            omop_concept_id=437663,
        )
        assert key == "P001:condition:437663"

    def test_calculate_node_dedup_key_patient(self) -> None:
        """Test dedup key for patient node."""
        builder = BaseGraphBuilderService()
        key = builder.calculate_node_dedup_key(
            patient_id="P001",
            node_type=NodeType.PATIENT,
            omop_concept_id=None,
        )
        assert key == "P001:patient:patient"


class TestDatabaseGraphBuilderService:
    """Tests for DatabaseGraphBuilderService with database."""

    @pytest.fixture
    def service(self, graph_session: Session) -> DatabaseGraphBuilderService:
        """Create a graph builder service."""
        return DatabaseGraphBuilderService(graph_session)

    def test_create_patient_node(
        self, service: DatabaseGraphBuilderService, graph_session: Session
    ) -> None:
        """Test creating a patient node (task 7.2)."""
        node_id = service.create_patient_node("P001")

        assert node_id is not None

        # Verify node in database
        node = graph_session.execute(select(KGNode).where(KGNode.id == str(node_id))).scalar_one()
        assert node.patient_id == "P001"
        assert node.node_type == NodeType.PATIENT
        assert node.label == "Patient P001"

    def test_create_patient_node_idempotent(
        self, service: DatabaseGraphBuilderService, graph_session: Session
    ) -> None:
        """Test that creating patient node twice returns same ID."""
        node_id_1 = service.create_patient_node("P001")
        node_id_2 = service.create_patient_node("P001")

        assert node_id_1 == node_id_2

        # Verify only one node in database
        nodes = (
            graph_session.execute(
                select(KGNode)
                .where(KGNode.patient_id == "P001")
                .where(KGNode.node_type == NodeType.PATIENT)
            )
            .scalars()
            .all()
        )
        assert len(nodes) == 1

    def test_get_patient_node(
        self, service: DatabaseGraphBuilderService, graph_session: Session
    ) -> None:
        """Test getting a patient node."""
        # Patient node doesn't exist yet
        assert service.get_patient_node("P001") is None

        # Create patient node
        created_id = service.create_patient_node("P001")

        # Now it should be found
        found_id = service.get_patient_node("P001")
        assert found_id == created_id

    def test_create_node(
        self, service: DatabaseGraphBuilderService, graph_session: Session
    ) -> None:
        """Test creating a concept node."""
        node_input = NodeInput(
            patient_id="P001",
            node_type=NodeType.CONDITION,
            label="Fever",
            omop_concept_id=437663,
            properties={"assertion": "present"},
        )
        node_id = service.create_node(node_input)

        assert node_id is not None

        # Verify node in database
        node = graph_session.execute(select(KGNode).where(KGNode.id == str(node_id))).scalar_one()
        assert node.label == "Fever"
        assert node.omop_concept_id == 437663
        assert node.properties["assertion"] == "present"

    def test_create_node_deduplication(
        self, service: DatabaseGraphBuilderService, graph_session: Session
    ) -> None:
        """Test that duplicate nodes return same ID."""
        node_input = NodeInput(
            patient_id="P001",
            node_type=NodeType.CONDITION,
            label="Fever",
            omop_concept_id=437663,
        )
        node_id_1 = service.create_node(node_input)
        node_id_2 = service.create_node(node_input)

        assert node_id_1 == node_id_2

        # Verify only one shared concept node in database (patient_id=NULL)
        nodes = (
            graph_session.execute(
                select(KGNode)
                .where(KGNode.patient_id.is_(None))
                .where(KGNode.omop_concept_id == 437663)
            )
            .scalars()
            .all()
        )
        assert len(nodes) == 1

    def test_create_edge(
        self, service: DatabaseGraphBuilderService, graph_session: Session
    ) -> None:
        """Test creating an edge (task 7.4)."""
        # Create source and target nodes
        patient_id = service.create_patient_node("P001")
        condition_input = NodeInput(
            patient_id="P001",
            node_type=NodeType.CONDITION,
            label="Fever",
            omop_concept_id=437663,
        )
        condition_id = service.create_node(condition_input)

        # Create edge
        edge_input = EdgeInput(
            patient_id="P001",
            source_node_id=patient_id,
            target_node_id=condition_id,
            edge_type=EdgeType.HAS_CONDITION,
        )
        edge_id = service.create_edge(edge_input)

        assert edge_id is not None

        # Verify edge in database
        edge = graph_session.execute(select(KGEdge).where(KGEdge.id == str(edge_id))).scalar_one()
        assert edge.source_node_id == str(patient_id)
        assert edge.target_node_id == str(condition_id)
        assert edge.edge_type == EdgeType.HAS_CONDITION

    def test_create_edge_deduplication(
        self, service: DatabaseGraphBuilderService, graph_session: Session
    ) -> None:
        """Test that duplicate edges return same ID."""
        patient_id = service.create_patient_node("P001")
        condition_input = NodeInput(
            patient_id="P001",
            node_type=NodeType.CONDITION,
            label="Fever",
            omop_concept_id=437663,
        )
        condition_id = service.create_node(condition_input)

        edge_input = EdgeInput(
            patient_id="P001",
            source_node_id=patient_id,
            target_node_id=condition_id,
            edge_type=EdgeType.HAS_CONDITION,
        )
        edge_id_1 = service.create_edge(edge_input)
        edge_id_2 = service.create_edge(edge_input)

        assert edge_id_1 == edge_id_2

    def test_project_fact_to_graph(
        self, service: DatabaseGraphBuilderService, graph_session: Session
    ) -> None:
        """Test projecting a fact to graph node (task 7.3)."""
        # Create patient node first
        service.create_patient_node("P001")

        fact_id = uuid4()
        node_id = service.project_fact_to_graph(
            fact_id=fact_id,
            patient_id="P001",
            domain=Domain.CONDITION,
            omop_concept_id=437663,
            concept_name="Fever",
            assertion="present",
            temporality="current",
            experiencer="patient",
        )

        assert node_id is not None

        # Verify shared concept node created (patient_id=NULL)
        node = graph_session.execute(select(KGNode).where(KGNode.id == str(node_id))).scalar_one()
        assert node.label == "Fever"
        assert node.node_type == NodeType.CONDITION
        assert node.patient_id is None  # Shared concept node

        # Verify edge created with patient-specific metadata
        edges = (
            graph_session.execute(select(KGEdge).where(KGEdge.patient_id == "P001")).scalars().all()
        )
        assert len(edges) == 1
        assert edges[0].edge_type == EdgeType.HAS_CONDITION
        assert edges[0].properties.get("fact_id") == str(fact_id)

    def test_project_negated_fact_to_graph(
        self, service: DatabaseGraphBuilderService, graph_session: Session
    ) -> None:
        """Test that negated facts are properly marked on the edge."""
        service.create_patient_node("P001")

        service.project_fact_to_graph(
            fact_id=uuid4(),
            patient_id="P001",
            domain=Domain.CONDITION,
            omop_concept_id=255848,
            concept_name="Pneumonia",
            assertion="absent",
            temporality="current",
            experiencer="patient",
        )

        # Negation metadata lives on edge (patient-specific), not on node (shared concept)
        edges = (
            graph_session.execute(select(KGEdge).where(KGEdge.patient_id == "P001")).scalars().all()
        )
        assert len(edges) == 1
        assert edges[0].properties.get("is_negated") is True
        assert edges[0].properties.get("assertion") == "absent"

    def test_project_uncertain_fact_to_graph(
        self, service: DatabaseGraphBuilderService, graph_session: Session
    ) -> None:
        """Test that uncertain facts are properly marked on the edge."""
        service.create_patient_node("P001")

        service.project_fact_to_graph(
            fact_id=uuid4(),
            patient_id="P001",
            domain=Domain.CONDITION,
            omop_concept_id=437663,
            concept_name="Fever",
            assertion="possible",
            temporality="current",
            experiencer="patient",
        )

        # Uncertainty metadata lives on edge, not on node
        edges = (
            graph_session.execute(select(KGEdge).where(KGEdge.patient_id == "P001")).scalars().all()
        )
        assert len(edges) == 1
        assert edges[0].properties.get("is_uncertain") is True
        assert edges[0].properties.get("assertion") == "possible"

    def test_build_graph_for_patient(
        self, service: DatabaseGraphBuilderService, graph_session: Session
    ) -> None:
        """Test building complete graph for a patient."""
        # Create some facts first
        fact1 = ClinicalFact(
            patient_id="P001",
            domain=Domain.CONDITION,
            omop_concept_id=437663,
            concept_name="Fever",
            assertion=Assertion.PRESENT,
            temporality=Temporality.CURRENT,
            experiencer=Experiencer.PATIENT,
            confidence=0.9,
        )
        fact2 = ClinicalFact(
            patient_id="P001",
            domain=Domain.DRUG,
            omop_concept_id=1503297,
            concept_name="Metformin",
            assertion=Assertion.PRESENT,
            temporality=Temporality.CURRENT,
            experiencer=Experiencer.PATIENT,
            confidence=0.9,
        )
        graph_session.add(fact1)
        graph_session.add(fact2)
        graph_session.flush()

        # Build graph
        result = service.build_graph_for_patient("P001")

        assert result.patient_id == "P001"
        assert result.node_count == 3  # Patient + 2 facts
        assert result.edge_count == 2  # 2 edges from patient to facts

    def test_build_graph_for_patient_with_negated_fact(
        self, service: DatabaseGraphBuilderService, graph_session: Session
    ) -> None:
        """Test building graph includes negated facts."""
        fact = ClinicalFact(
            patient_id="P001",
            domain=Domain.CONDITION,
            omop_concept_id=255848,
            concept_name="Pneumonia",
            assertion=Assertion.ABSENT,  # Negated
            temporality=Temporality.CURRENT,
            experiencer=Experiencer.PATIENT,
            confidence=0.9,
        )
        graph_session.add(fact)
        graph_session.flush()

        result = service.build_graph_for_patient("P001")

        # Verify negated fact is in graph
        assert result.node_count == 2  # Patient + negated condition
        assert result.edge_count == 1

        # Check node properties
        negated_nodes = service.get_negated_nodes("P001")
        assert len(negated_nodes) == 1
        assert negated_nodes[0].label == "Pneumonia"

    def test_get_nodes_for_patient(
        self, service: DatabaseGraphBuilderService, graph_session: Session
    ) -> None:
        """Test getting all nodes for a patient via edge-join."""
        patient_node_id = service.create_patient_node("P001")
        condition_id = service.create_node(
            NodeInput(
                patient_id="P001",
                node_type=NodeType.CONDITION,
                label="Fever",
                omop_concept_id=437663,
            )
        )
        drug_id = service.create_node(
            NodeInput(
                patient_id="P001",
                node_type=NodeType.DRUG,
                label="Metformin",
                omop_concept_id=1503297,
            )
        )

        # Create edges so edge-join can find shared concept nodes
        service.create_edge(EdgeInput(
            patient_id="P001", source_node_id=patient_node_id,
            target_node_id=condition_id, edge_type=EdgeType.HAS_CONDITION,
        ))
        service.create_edge(EdgeInput(
            patient_id="P001", source_node_id=patient_node_id,
            target_node_id=drug_id, edge_type=EdgeType.TAKES_DRUG,
        ))

        # Get all nodes
        all_nodes = service.get_nodes_for_patient("P001")
        assert len(all_nodes) == 3

        # Filter by type
        conditions = service.get_nodes_for_patient("P001", node_type=NodeType.CONDITION)
        assert len(conditions) == 1
        assert conditions[0].label == "Fever"

    def test_get_edges_for_patient(
        self, service: DatabaseGraphBuilderService, graph_session: Session
    ) -> None:
        """Test getting all edges for a patient."""
        patient_id = service.create_patient_node("P001")
        condition_id = service.create_node(
            NodeInput(
                patient_id="P001",
                node_type=NodeType.CONDITION,
                label="Fever",
                omop_concept_id=437663,
            )
        )
        drug_id = service.create_node(
            NodeInput(
                patient_id="P001",
                node_type=NodeType.DRUG,
                label="Metformin",
                omop_concept_id=1503297,
            )
        )

        # Create edges
        service.create_edge(
            EdgeInput(
                patient_id="P001",
                source_node_id=patient_id,
                target_node_id=condition_id,
                edge_type=EdgeType.HAS_CONDITION,
            )
        )
        service.create_edge(
            EdgeInput(
                patient_id="P001",
                source_node_id=patient_id,
                target_node_id=drug_id,
                edge_type=EdgeType.TAKES_DRUG,
            )
        )

        # Get all edges
        all_edges = service.get_edges_for_patient("P001")
        assert len(all_edges) == 2

        # Filter by type
        condition_edges = service.get_edges_for_patient("P001", edge_type=EdgeType.HAS_CONDITION)
        assert len(condition_edges) == 1

    def test_get_node_by_id(
        self, service: DatabaseGraphBuilderService, graph_session: Session
    ) -> None:
        """Test getting a node by ID."""
        node_id = service.create_node(
            NodeInput(
                patient_id="P001",
                node_type=NodeType.CONDITION,
                label="Fever",
                omop_concept_id=437663,
            )
        )

        node = service.get_node_by_id(node_id)
        assert node is not None
        assert node.label == "Fever"

        # Non-existent node
        assert service.get_node_by_id(uuid4()) is None

    def test_get_patient_graph(
        self, service: DatabaseGraphBuilderService, graph_session: Session
    ) -> None:
        """Test getting complete patient graph via edge-join."""
        # Create some facts
        fact = ClinicalFact(
            patient_id="P001",
            domain=Domain.CONDITION,
            omop_concept_id=437663,
            concept_name="Fever",
            assertion=Assertion.PRESENT,
            temporality=Temporality.CURRENT,
            experiencer=Experiencer.PATIENT,
            confidence=0.9,
        )
        graph_session.add(fact)
        graph_session.flush()

        # Build graph first (creates patient node, concept node, edge)
        service.build_graph_for_patient("P001")

        # Get patient graph — uses edge-join to find shared concept nodes
        patient_graph = service.get_patient_graph("P001")

        assert patient_graph.patient_id == "P001"
        assert len(patient_graph.nodes) >= 2  # Patient + condition (at least)
        assert len(patient_graph.edges) >= 1

        # Verify node structure
        node_types = {n.node_type for n in patient_graph.nodes}
        assert NodeType.PATIENT in node_types
        assert NodeType.CONDITION in node_types

    def test_get_negated_nodes(
        self, service: DatabaseGraphBuilderService, graph_session: Session
    ) -> None:
        """Test getting negated nodes via edge properties."""
        patient_node_id = service.create_patient_node("P001")

        # Create normal concept node
        fever_id = service.create_node(
            NodeInput(
                patient_id="P001",
                node_type=NodeType.CONDITION,
                label="Fever",
                omop_concept_id=437663,
            )
        )

        # Create negated concept node
        pneumonia_id = service.create_node(
            NodeInput(
                patient_id="P001",
                node_type=NodeType.CONDITION,
                label="Pneumonia",
                omop_concept_id=255848,
            )
        )

        # Create edges — negation lives on the edge, not the node
        service.create_edge(EdgeInput(
            patient_id="P001", source_node_id=patient_node_id,
            target_node_id=fever_id, edge_type=EdgeType.HAS_CONDITION,
            properties={"is_negated": False},
        ))
        service.create_edge(EdgeInput(
            patient_id="P001", source_node_id=patient_node_id,
            target_node_id=pneumonia_id, edge_type=EdgeType.HAS_CONDITION,
            properties={"is_negated": True},
        ))

        negated = service.get_negated_nodes("P001")
        assert len(negated) == 1
        assert negated[0].label == "Pneumonia"

    def test_different_patients_have_separate_graphs(
        self, service: DatabaseGraphBuilderService, graph_session: Session
    ) -> None:
        """Test that different patients see only their own concepts via edges."""
        p001_node_id = service.create_patient_node("P001")
        p002_node_id = service.create_patient_node("P002")

        fever_id = service.create_node(
            NodeInput(
                patient_id="P001",
                node_type=NodeType.CONDITION,
                label="Fever",
                omop_concept_id=437663,
            )
        )
        cough_id = service.create_node(
            NodeInput(
                patient_id="P002",
                node_type=NodeType.CONDITION,
                label="Cough",
                omop_concept_id=254761,
            )
        )

        # Create edges to scope concepts to patients
        service.create_edge(EdgeInput(
            patient_id="P001", source_node_id=p001_node_id,
            target_node_id=fever_id, edge_type=EdgeType.HAS_CONDITION,
        ))
        service.create_edge(EdgeInput(
            patient_id="P002", source_node_id=p002_node_id,
            target_node_id=cough_id, edge_type=EdgeType.HAS_CONDITION,
        ))

        p001_nodes = service.get_nodes_for_patient("P001")
        p002_nodes = service.get_nodes_for_patient("P002")

        assert len(p001_nodes) == 2  # Patient + condition
        assert len(p002_nodes) == 2
        assert {n.label for n in p001_nodes if n.node_type == NodeType.CONDITION} == {"Fever"}
        assert {n.label for n in p002_nodes if n.node_type == NodeType.CONDITION} == {"Cough"}

    def test_multiple_domains_in_graph(
        self, service: DatabaseGraphBuilderService, graph_session: Session
    ) -> None:
        """Test graph with multiple domain types."""
        # Create facts for multiple domains
        fact1 = ClinicalFact(
            patient_id="P001",
            domain=Domain.CONDITION,
            omop_concept_id=437663,
            concept_name="Fever",
            assertion=Assertion.PRESENT,
            temporality=Temporality.CURRENT,
            experiencer=Experiencer.PATIENT,
            confidence=0.9,
        )
        fact2 = ClinicalFact(
            patient_id="P001",
            domain=Domain.DRUG,
            omop_concept_id=1503297,
            concept_name="Metformin",
            assertion=Assertion.PRESENT,
            temporality=Temporality.CURRENT,
            experiencer=Experiencer.PATIENT,
            confidence=0.9,
        )
        fact3 = ClinicalFact(
            patient_id="P001",
            domain=Domain.MEASUREMENT,
            omop_concept_id=3004249,
            concept_name="Blood pressure",
            assertion=Assertion.PRESENT,
            temporality=Temporality.CURRENT,
            experiencer=Experiencer.PATIENT,
            confidence=0.9,
        )
        graph_session.add(fact1)
        graph_session.add(fact2)
        graph_session.add(fact3)
        graph_session.flush()

        result = service.build_graph_for_patient("P001")

        # 1 patient + 3 fact nodes
        assert result.node_count == 4
        # 3 edges (one for each fact)
        assert result.edge_count == 3

        # Verify edge types
        edges = service.get_edges_for_patient("P001")
        edge_types = {e.edge_type for e in edges}
        assert EdgeType.HAS_CONDITION in edge_types
        assert EdgeType.TAKES_DRUG in edge_types
        assert EdgeType.HAS_MEASUREMENT in edge_types
