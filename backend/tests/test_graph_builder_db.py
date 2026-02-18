"""Tests for DatabaseGraphBuilderService.

Tests graph construction, patient nodes, fact-to-node projection,
edge creation, and graph structure validation (tasks 7.2-7.4, 7.6).
"""

from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.clinical_fact import ClinicalFact
from app.models.knowledge_graph import KGEdge, KGNode
from app.schemas.base import Assertion, Domain, Experiencer, Temporality
from app.schemas.knowledge_graph import EdgeType, NodeType
from app.services.graph_builder import EdgeInput, NodeInput
from app.services.graph_builder_db import DatabaseGraphBuilderService

# Create test database engine
_test_engine = create_engine(
    "sqlite:///:memory:",
    echo=False,
    future=True,
)
_TestSession = sessionmaker(
    bind=_test_engine,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="function")
def db_session() -> Session:
    """Create a database session with knowledge graph tables."""
    KGNode.__table__.create(bind=_test_engine, checkfirst=True)
    KGEdge.__table__.create(bind=_test_engine, checkfirst=True)
    ClinicalFact.__table__.create(bind=_test_engine, checkfirst=True)

    session = _TestSession()
    try:
        yield session
    finally:
        session.close()
        ClinicalFact.__table__.drop(bind=_test_engine, checkfirst=True)
        KGEdge.__table__.drop(bind=_test_engine, checkfirst=True)
        KGNode.__table__.drop(bind=_test_engine, checkfirst=True)


@pytest.fixture
def graph_service(db_session: Session) -> DatabaseGraphBuilderService:
    """Create a DatabaseGraphBuilderService."""
    return DatabaseGraphBuilderService(db_session)


class TestPatientNodeCreation:
    """Tests for patient node creation (task 7.2)."""

    def test_create_patient_node_returns_uuid(
        self, graph_service: DatabaseGraphBuilderService
    ) -> None:
        """Test that create_patient_node returns a UUID."""
        node_id = graph_service.create_patient_node("P001")
        assert node_id is not None

    def test_create_patient_node_persists_to_database(
        self, graph_service: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        """Test that patient node is persisted to database."""
        node_id = graph_service.create_patient_node("P001")

        node = db_session.query(KGNode).filter_by(id=str(node_id)).first()
        assert node is not None
        assert node.patient_id == "P001"
        assert node.node_type == NodeType.PATIENT

    def test_create_patient_node_is_idempotent(
        self, graph_service: DatabaseGraphBuilderService
    ) -> None:
        """Test that creating the same patient node twice returns same ID."""
        node_id1 = graph_service.create_patient_node("P001")
        node_id2 = graph_service.create_patient_node("P001")
        assert node_id1 == node_id2

    def test_get_patient_node_returns_existing(
        self, graph_service: DatabaseGraphBuilderService
    ) -> None:
        """Test get_patient_node returns existing node."""
        created_id = graph_service.create_patient_node("P001")
        retrieved_id = graph_service.get_patient_node("P001")
        assert retrieved_id == created_id

    def test_get_patient_node_returns_none_if_not_exists(
        self, graph_service: DatabaseGraphBuilderService
    ) -> None:
        """Test get_patient_node returns None if not found."""
        result = graph_service.get_patient_node("P999")
        assert result is None

    def test_patient_node_has_correct_label(
        self, graph_service: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        """Test that patient node has descriptive label."""
        node_id = graph_service.create_patient_node("P001")

        node = db_session.query(KGNode).filter_by(id=str(node_id)).first()
        assert "P001" in node.label


class TestNodeCreation:
    """Tests for generic node creation."""

    def test_create_node_returns_uuid(self, graph_service: DatabaseGraphBuilderService) -> None:
        """Test that create_node returns a UUID."""
        node_input = NodeInput(
            patient_id="P001",
            node_type=NodeType.CONDITION,
            label="Fever",
            omop_concept_id=437663,
        )
        node_id = graph_service.create_node(node_input)
        assert node_id is not None

    def test_create_node_persists_to_database(
        self, graph_service: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        """Test that node is persisted to database."""
        node_input = NodeInput(
            patient_id="P001",
            node_type=NodeType.CONDITION,
            label="Fever",
            omop_concept_id=437663,
        )
        node_id = graph_service.create_node(node_input)

        node = db_session.query(KGNode).filter_by(id=str(node_id)).first()
        assert node is not None
        assert node.label == "Fever"
        assert node.omop_concept_id == 437663

    def test_create_node_deduplicates(self, graph_service: DatabaseGraphBuilderService) -> None:
        """Test that duplicate nodes return the same ID."""
        node_input = NodeInput(
            patient_id="P001",
            node_type=NodeType.CONDITION,
            label="Fever",
            omop_concept_id=437663,
        )
        node_id1 = graph_service.create_node(node_input)
        node_id2 = graph_service.create_node(node_input)
        assert node_id1 == node_id2

    def test_different_concepts_create_different_nodes(
        self, graph_service: DatabaseGraphBuilderService
    ) -> None:
        """Test that different concepts create different nodes."""
        node1 = NodeInput(
            patient_id="P001",
            node_type=NodeType.CONDITION,
            label="Fever",
            omop_concept_id=437663,
        )
        node2 = NodeInput(
            patient_id="P001",
            node_type=NodeType.CONDITION,
            label="Pneumonia",
            omop_concept_id=255848,
        )
        node_id1 = graph_service.create_node(node1)
        node_id2 = graph_service.create_node(node2)
        assert node_id1 != node_id2

    def test_create_node_with_properties(
        self, graph_service: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        """Test that node properties are persisted."""
        node_input = NodeInput(
            patient_id="P001",
            node_type=NodeType.CONDITION,
            label="Fever",
            omop_concept_id=437663,
            properties={"severity": "high"},
        )
        node_id = graph_service.create_node(node_input)

        node = db_session.query(KGNode).filter_by(id=str(node_id)).first()
        assert node.properties.get("severity") == "high"


class TestEdgeCreation:
    """Tests for edge creation (task 7.4)."""

    def test_create_edge_returns_uuid(self, graph_service: DatabaseGraphBuilderService) -> None:
        """Test that create_edge returns a UUID."""
        patient_id = graph_service.create_patient_node("P001")
        condition_node = graph_service.create_node(
            NodeInput(
                patient_id="P001",
                node_type=NodeType.CONDITION,
                label="Fever",
                omop_concept_id=437663,
            )
        )

        edge_input = EdgeInput(
            patient_id="P001",
            source_node_id=patient_id,
            target_node_id=condition_node,
            edge_type=EdgeType.HAS_CONDITION,
        )
        edge_id = graph_service.create_edge(edge_input)
        assert edge_id is not None

    def test_create_edge_persists_to_database(
        self, graph_service: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        """Test that edge is persisted to database."""
        patient_id = graph_service.create_patient_node("P001")
        condition_node = graph_service.create_node(
            NodeInput(
                patient_id="P001",
                node_type=NodeType.CONDITION,
                label="Fever",
                omop_concept_id=437663,
            )
        )

        edge_input = EdgeInput(
            patient_id="P001",
            source_node_id=patient_id,
            target_node_id=condition_node,
            edge_type=EdgeType.HAS_CONDITION,
        )
        edge_id = graph_service.create_edge(edge_input)

        edge = db_session.query(KGEdge).filter_by(id=str(edge_id)).first()
        assert edge is not None
        assert edge.edge_type == EdgeType.HAS_CONDITION

    def test_create_edge_deduplicates(self, graph_service: DatabaseGraphBuilderService) -> None:
        """Test that duplicate edges return the same ID."""
        patient_id = graph_service.create_patient_node("P001")
        condition_node = graph_service.create_node(
            NodeInput(
                patient_id="P001",
                node_type=NodeType.CONDITION,
                label="Fever",
                omop_concept_id=437663,
            )
        )

        edge_input = EdgeInput(
            patient_id="P001",
            source_node_id=patient_id,
            target_node_id=condition_node,
            edge_type=EdgeType.HAS_CONDITION,
        )
        edge_id1 = graph_service.create_edge(edge_input)
        edge_id2 = graph_service.create_edge(edge_input)
        assert edge_id1 == edge_id2

    def test_create_edge_with_fact_id(
        self, graph_service: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        """Test that edge can store fact_id."""
        patient_id = graph_service.create_patient_node("P001")
        condition_node = graph_service.create_node(
            NodeInput(
                patient_id="P001",
                node_type=NodeType.CONDITION,
                label="Fever",
                omop_concept_id=437663,
            )
        )
        fact_id = uuid4()

        edge_input = EdgeInput(
            patient_id="P001",
            source_node_id=patient_id,
            target_node_id=condition_node,
            edge_type=EdgeType.HAS_CONDITION,
            fact_id=fact_id,
        )
        edge_id = graph_service.create_edge(edge_input)

        edge = db_session.query(KGEdge).filter_by(id=str(edge_id)).first()
        assert edge.fact_id == str(fact_id)


class TestFactToNodeProjection:
    """Tests for fact-to-node projection (task 7.3)."""

    def test_project_fact_creates_node(self, graph_service: DatabaseGraphBuilderService) -> None:
        """Test that projecting a fact creates a node."""
        fact_id = uuid4()
        node_id = graph_service.project_fact_to_graph(
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

    def test_project_fact_creates_edge(self, graph_service: DatabaseGraphBuilderService) -> None:
        """Test that projecting a fact creates an edge to patient."""
        fact_id = uuid4()
        graph_service.project_fact_to_graph(
            fact_id=fact_id,
            patient_id="P001",
            domain=Domain.CONDITION,
            omop_concept_id=437663,
            concept_name="Fever",
            assertion="present",
            temporality="current",
            experiencer="patient",
        )

        edges = graph_service.get_edges_for_patient("P001")
        assert len(edges) == 1
        assert edges[0].edge_type == EdgeType.HAS_CONDITION

    def test_project_fact_creates_patient_node_if_missing(
        self, graph_service: DatabaseGraphBuilderService
    ) -> None:
        """Test that projecting creates patient node if needed."""
        fact_id = uuid4()
        graph_service.project_fact_to_graph(
            fact_id=fact_id,
            patient_id="P001",
            domain=Domain.CONDITION,
            omop_concept_id=437663,
            concept_name="Fever",
            assertion="present",
            temporality="current",
            experiencer="patient",
        )

        patient_node = graph_service.get_patient_node("P001")
        assert patient_node is not None

    def test_project_negated_fact_sets_properties(
        self, graph_service: DatabaseGraphBuilderService
    ) -> None:
        """Test that negated facts have correct properties on the edge."""
        fact_id = uuid4()
        graph_service.project_fact_to_graph(
            fact_id=fact_id,
            patient_id="P001",
            domain=Domain.CONDITION,
            omop_concept_id=255848,
            concept_name="Pneumonia",
            assertion="absent",
            temporality="current",
            experiencer="patient",
        )

        # Negation metadata lives on edge (patient-specific), not on shared concept node
        edges = graph_service.get_edges_for_patient("P001")
        assert len(edges) == 1
        assert edges[0].properties.get("is_negated") is True
        assert edges[0].properties.get("assertion") == "absent"

    def test_project_uncertain_fact_sets_properties(
        self, graph_service: DatabaseGraphBuilderService
    ) -> None:
        """Test that uncertain facts have correct properties on the edge."""
        fact_id = uuid4()
        graph_service.project_fact_to_graph(
            fact_id=fact_id,
            patient_id="P001",
            domain=Domain.CONDITION,
            omop_concept_id=437663,
            concept_name="Fever",
            assertion="possible",
            temporality="current",
            experiencer="patient",
        )

        # Uncertainty metadata lives on edge, not on shared concept node
        edges = graph_service.get_edges_for_patient("P001")
        assert len(edges) == 1
        assert edges[0].properties.get("is_uncertain") is True

    def test_project_drug_creates_takes_drug_edge(
        self, graph_service: DatabaseGraphBuilderService
    ) -> None:
        """Test that drug facts create TAKES_DRUG edges."""
        fact_id = uuid4()
        graph_service.project_fact_to_graph(
            fact_id=fact_id,
            patient_id="P001",
            domain=Domain.DRUG,
            omop_concept_id=1000000,
            concept_name="Aspirin",
            assertion="present",
            temporality="current",
            experiencer="patient",
        )

        edges = graph_service.get_edges_for_patient("P001")
        assert len(edges) == 1
        assert edges[0].edge_type == EdgeType.TAKES_DRUG


class TestGetNodesAndEdges:
    """Tests for node and edge retrieval."""

    def test_get_node_by_id(self, graph_service: DatabaseGraphBuilderService) -> None:
        """Test retrieving a node by ID."""
        node_input = NodeInput(
            patient_id="P001",
            node_type=NodeType.CONDITION,
            label="Fever",
            omop_concept_id=437663,
        )
        node_id = graph_service.create_node(node_input)

        retrieved = graph_service.get_node_by_id(node_id)
        assert retrieved is not None
        assert retrieved.label == "Fever"

    def test_get_node_by_id_not_found(self, graph_service: DatabaseGraphBuilderService) -> None:
        """Test that get_node_by_id returns None for unknown ID."""
        result = graph_service.get_node_by_id(uuid4())
        assert result is None

    def test_get_nodes_for_patient(self, graph_service: DatabaseGraphBuilderService) -> None:
        """Test getting all nodes for a patient via edge-join."""
        patient_node_id = graph_service.create_patient_node("P001")
        condition_id = graph_service.create_node(
            NodeInput(
                patient_id="P001",
                node_type=NodeType.CONDITION,
                label="Fever",
                omop_concept_id=437663,
            )
        )
        drug_id = graph_service.create_node(
            NodeInput(
                patient_id="P001",
                node_type=NodeType.DRUG,
                label="Aspirin",
                omop_concept_id=1000000,
            )
        )

        # Create edges so edge-join can find shared concept nodes
        graph_service.create_edge(EdgeInput(
            patient_id="P001", source_node_id=patient_node_id,
            target_node_id=condition_id, edge_type=EdgeType.HAS_CONDITION,
        ))
        graph_service.create_edge(EdgeInput(
            patient_id="P001", source_node_id=patient_node_id,
            target_node_id=drug_id, edge_type=EdgeType.TAKES_DRUG,
        ))

        nodes = graph_service.get_nodes_for_patient("P001")
        assert len(nodes) == 3  # Patient + 2 concepts

    def test_get_nodes_by_type(self, graph_service: DatabaseGraphBuilderService) -> None:
        """Test filtering nodes by type."""
        patient_node_id = graph_service.create_patient_node("P001")
        condition_id = graph_service.create_node(
            NodeInput(
                patient_id="P001",
                node_type=NodeType.CONDITION,
                label="Fever",
                omop_concept_id=437663,
            )
        )
        drug_id = graph_service.create_node(
            NodeInput(
                patient_id="P001",
                node_type=NodeType.DRUG,
                label="Aspirin",
                omop_concept_id=1000000,
            )
        )

        # Create edges for edge-join
        graph_service.create_edge(EdgeInput(
            patient_id="P001", source_node_id=patient_node_id,
            target_node_id=condition_id, edge_type=EdgeType.HAS_CONDITION,
        ))
        graph_service.create_edge(EdgeInput(
            patient_id="P001", source_node_id=patient_node_id,
            target_node_id=drug_id, edge_type=EdgeType.TAKES_DRUG,
        ))

        conditions = graph_service.get_nodes_for_patient("P001", node_type=NodeType.CONDITION)
        assert len(conditions) == 1
        assert conditions[0].node_type == NodeType.CONDITION

    def test_get_edges_for_patient(self, graph_service: DatabaseGraphBuilderService) -> None:
        """Test getting all edges for a patient."""
        patient_id = graph_service.create_patient_node("P001")
        condition_id = graph_service.create_node(
            NodeInput(
                patient_id="P001",
                node_type=NodeType.CONDITION,
                label="Fever",
                omop_concept_id=437663,
            )
        )
        drug_id = graph_service.create_node(
            NodeInput(
                patient_id="P001",
                node_type=NodeType.DRUG,
                label="Aspirin",
                omop_concept_id=1000000,
            )
        )

        graph_service.create_edge(
            EdgeInput(
                patient_id="P001",
                source_node_id=patient_id,
                target_node_id=condition_id,
                edge_type=EdgeType.HAS_CONDITION,
            )
        )
        graph_service.create_edge(
            EdgeInput(
                patient_id="P001",
                source_node_id=patient_id,
                target_node_id=drug_id,
                edge_type=EdgeType.TAKES_DRUG,
            )
        )

        edges = graph_service.get_edges_for_patient("P001")
        assert len(edges) == 2

    def test_get_edges_by_type(self, graph_service: DatabaseGraphBuilderService) -> None:
        """Test filtering edges by type."""
        patient_id = graph_service.create_patient_node("P001")
        condition_id = graph_service.create_node(
            NodeInput(
                patient_id="P001",
                node_type=NodeType.CONDITION,
                label="Fever",
                omop_concept_id=437663,
            )
        )
        drug_id = graph_service.create_node(
            NodeInput(
                patient_id="P001",
                node_type=NodeType.DRUG,
                label="Aspirin",
                omop_concept_id=1000000,
            )
        )

        graph_service.create_edge(
            EdgeInput(
                patient_id="P001",
                source_node_id=patient_id,
                target_node_id=condition_id,
                edge_type=EdgeType.HAS_CONDITION,
            )
        )
        graph_service.create_edge(
            EdgeInput(
                patient_id="P001",
                source_node_id=patient_id,
                target_node_id=drug_id,
                edge_type=EdgeType.TAKES_DRUG,
            )
        )

        condition_edges = graph_service.get_edges_for_patient(
            "P001", edge_type=EdgeType.HAS_CONDITION
        )
        assert len(condition_edges) == 1


class TestBuildGraphForPatient:
    """Tests for complete graph building (task 7.6)."""

    def test_build_graph_creates_patient_node(
        self, graph_service: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        """Test that build_graph_for_patient creates patient node."""
        result = graph_service.build_graph_for_patient("P001")

        assert result.patient_id == "P001"
        patient_node = graph_service.get_patient_node("P001")
        assert patient_node is not None

    def test_build_graph_processes_all_facts(
        self, graph_service: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        """Test that all facts are projected to the graph."""
        # Create facts directly in DB
        fact1 = ClinicalFact(
            patient_id="P001",
            domain=Domain.CONDITION,
            omop_concept_id=437663,
            concept_name="Fever",
            assertion=Assertion.PRESENT,
            temporality=Temporality.CURRENT,
            experiencer=Experiencer.PATIENT,
        )
        fact2 = ClinicalFact(
            patient_id="P001",
            domain=Domain.DRUG,
            omop_concept_id=1000000,
            concept_name="Aspirin",
            assertion=Assertion.PRESENT,
            temporality=Temporality.CURRENT,
            experiencer=Experiencer.PATIENT,
        )
        db_session.add(fact1)
        db_session.add(fact2)
        db_session.flush()

        result = graph_service.build_graph_for_patient("P001")

        # Should have patient + 2 concept nodes
        assert result.node_count == 3
        # Should have 2 edges (patient -> condition, patient -> drug)
        assert result.edge_count == 2

    def test_build_graph_returns_correct_counts(
        self, graph_service: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        """Test that build_graph returns correct creation counts."""
        fact = ClinicalFact(
            patient_id="P001",
            domain=Domain.CONDITION,
            omop_concept_id=437663,
            concept_name="Fever",
            assertion=Assertion.PRESENT,
            temporality=Temporality.CURRENT,
            experiencer=Experiencer.PATIENT,
        )
        db_session.add(fact)
        db_session.flush()

        result = graph_service.build_graph_for_patient("P001")

        assert result.nodes_created >= 1
        assert result.edges_created >= 1

    def test_build_graph_preserves_negated_facts(
        self, graph_service: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        """Test that negated facts are correctly included in graph via edges."""
        fact = ClinicalFact(
            patient_id="P001",
            domain=Domain.CONDITION,
            omop_concept_id=255848,
            concept_name="Pneumonia",
            assertion=Assertion.ABSENT,
            temporality=Temporality.CURRENT,
            experiencer=Experiencer.PATIENT,
        )
        db_session.add(fact)
        db_session.flush()

        graph_service.build_graph_for_patient("P001")

        # get_negated_nodes checks edge.properties for is_negated
        negated = graph_service.get_negated_nodes("P001")
        assert len(negated) == 1
        assert negated[0].label == "Pneumonia"


class TestGetPatientGraph:
    """Tests for complete graph retrieval."""

    def test_get_patient_graph_returns_schema(
        self, graph_service: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        """Test that get_patient_graph returns a PatientGraph via edge-join."""
        fact = ClinicalFact(
            patient_id="P001",
            domain=Domain.CONDITION,
            omop_concept_id=437663,
            concept_name="Fever",
            assertion=Assertion.PRESENT,
            temporality=Temporality.CURRENT,
            experiencer=Experiencer.PATIENT,
        )
        db_session.add(fact)
        db_session.flush()

        graph_service.build_graph_for_patient("P001")
        patient_graph = graph_service.get_patient_graph("P001")

        assert patient_graph.patient_id == "P001"
        assert len(patient_graph.nodes) >= 2  # Patient + condition (at least)
        assert len(patient_graph.edges) >= 1


class TestGraphStructureValidation:
    """Tests validating graph structure (task 7.6)."""

    def test_graph_is_star_topology(
        self, graph_service: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        """Test that graph has star topology with patient at center."""
        # Create multiple facts
        fact1 = ClinicalFact(
            patient_id="P001",
            domain=Domain.CONDITION,
            omop_concept_id=437663,
            concept_name="Fever",
            assertion=Assertion.PRESENT,
            temporality=Temporality.CURRENT,
            experiencer=Experiencer.PATIENT,
        )
        fact2 = ClinicalFact(
            patient_id="P001",
            domain=Domain.DRUG,
            omop_concept_id=1000000,
            concept_name="Aspirin",
            assertion=Assertion.PRESENT,
            temporality=Temporality.CURRENT,
            experiencer=Experiencer.PATIENT,
        )
        db_session.add(fact1)
        db_session.add(fact2)
        db_session.flush()

        graph_service.build_graph_for_patient("P001")

        # All edges should have patient as source
        patient_node = graph_service.get_patient_node("P001")
        edges = graph_service.get_edges_for_patient("P001")

        for edge in edges:
            assert edge.source_node_id == patient_node

    def test_edge_types_match_node_types(
        self, graph_service: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        """Test that edge types correctly correspond to target node types."""
        fact = ClinicalFact(
            patient_id="P001",
            domain=Domain.CONDITION,
            omop_concept_id=437663,
            concept_name="Fever",
            assertion=Assertion.PRESENT,
            temporality=Temporality.CURRENT,
            experiencer=Experiencer.PATIENT,
        )
        db_session.add(fact)
        db_session.flush()

        graph_service.build_graph_for_patient("P001")

        edges = graph_service.get_edges_for_patient("P001", edge_type=EdgeType.HAS_CONDITION)
        assert len(edges) == 1

        # Verify target node is a condition
        target_node = graph_service.get_node_by_id(edges[0].target_node_id)
        assert target_node.node_type == NodeType.CONDITION


class TestDatabaseGraphBuilderExports:
    """Tests for module exports."""

    def test_database_graph_builder_exported(self) -> None:
        """Test that DatabaseGraphBuilderService is exported."""
        from app.services import DatabaseGraphBuilderService

        assert DatabaseGraphBuilderService is not None
