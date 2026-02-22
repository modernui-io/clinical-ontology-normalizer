"""Tests for shared concept knowledge graph feature.

Shared concept nodes (conditions, drugs, etc.) have patient_id=NULL and are
deduplicated across patients. Patient nodes always retain patient_id. Edges
always carry patient_id and hold patient-specific metadata (assertion,
experiencer, etc.).

NOTE: get_nodes_for_patient and get_patient_graph use UNION queries that work
correctly with PostgreSQL but fail with SQLite in-memory due to ORM mapping
differences. Tests that verify edge-join retrieval behavior query the DB
directly to validate the data model invariants.
"""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, or_
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.knowledge_graph import KGEdge, KGNode
from app.models.clinical_fact import ClinicalFact
from app.schemas.base import Assertion, Domain, Experiencer, Temporality
from app.schemas.knowledge_graph import EdgeType, NodeType
from app.services.graph_builder import BaseGraphBuilderService, EdgeInput, NodeInput
from app.services.graph_builder_db import DatabaseGraphBuilderService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_test_engine = create_engine(
    "sqlite:///:memory:",
    echo=False,
    future=True,
    poolclass=StaticPool,
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
def svc(db_session: Session) -> DatabaseGraphBuilderService:
    """Create a DatabaseGraphBuilderService."""
    return DatabaseGraphBuilderService(db_session)


# Concept IDs used across tests
DIABETES_CONCEPT = 201826
HYPERTENSION_CONCEPT = 316866
ASPIRIN_CONCEPT = 1112807


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _project_condition(
    svc: DatabaseGraphBuilderService,
    patient_id: str,
    concept_id: int,
    concept_name: str,
    assertion: str = "present",
):
    """Helper to project a condition fact to the graph."""
    return svc.project_fact_to_graph(
        fact_id=uuid4(),
        patient_id=patient_id,
        domain=Domain.CONDITION,
        omop_concept_id=concept_id,
        concept_name=concept_name,
        assertion=assertion,
        temporality="current",
        experiencer="patient",
    )


def _project_drug(
    svc: DatabaseGraphBuilderService,
    patient_id: str,
    concept_id: int,
    concept_name: str,
    assertion: str = "present",
):
    """Helper to project a drug fact to the graph."""
    return svc.project_fact_to_graph(
        fact_id=uuid4(),
        patient_id=patient_id,
        domain=Domain.DRUG,
        omop_concept_id=concept_id,
        concept_name=concept_name,
        assertion=assertion,
        temporality="current",
        experiencer="patient",
    )


def _get_concept_nodes_for_patient(session: Session, patient_id: str) -> list[KGNode]:
    """Get shared concept nodes connected to a patient via edges (direct query).

    Avoids the SQLite UNION limitation in get_nodes_for_patient.
    """
    return (
        session.query(KGNode)
        .join(
            KGEdge,
            or_(
                KGEdge.target_node_id == KGNode.id,
                KGEdge.source_node_id == KGNode.id,
            ),
        )
        .filter(KGEdge.patient_id == patient_id)
        .filter(KGNode.patient_id.is_(None))
        .all()
    )


def _get_all_nodes_for_patient(session: Session, patient_id: str) -> list[KGNode]:
    """Get all nodes for a patient: patient-owned + shared concepts (direct query)."""
    patient_nodes = (
        session.query(KGNode)
        .filter(KGNode.patient_id == patient_id)
        .all()
    )
    concept_nodes = _get_concept_nodes_for_patient(session, patient_id)
    # Deduplicate by id
    seen = {n.id for n in patient_nodes}
    for cn in concept_nodes:
        if cn.id not in seen:
            patient_nodes.append(cn)
            seen.add(cn.id)
    return patient_nodes


# ===========================================================================
# 1. Shared concept node deduplication
# ===========================================================================


class TestSharedConceptDedup:
    """Creating the same concept for two patients should produce one shared node."""

    def test_same_concept_two_patients_produces_one_node(
        self, svc: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        """The same OMOP concept projected for two patients yields a single KGNode."""
        _project_condition(svc, "PA", DIABETES_CONCEPT, "Diabetes")
        _project_condition(svc, "PB", DIABETES_CONCEPT, "Diabetes")

        nodes = (
            db_session.query(KGNode)
            .filter(
                KGNode.omop_concept_id == DIABETES_CONCEPT,
                KGNode.node_type == NodeType.CONDITION,
            )
            .all()
        )
        # Only one shared concept node
        assert len(nodes) == 1
        assert nodes[0].patient_id is None

    def test_same_concept_two_patients_two_edges(
        self, svc: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        """Each patient gets its own edge to the shared concept node."""
        _project_condition(svc, "PA", DIABETES_CONCEPT, "Diabetes")
        _project_condition(svc, "PB", DIABETES_CONCEPT, "Diabetes")

        edges = db_session.query(KGEdge).all()
        patient_ids_on_edges = {e.patient_id for e in edges}
        assert patient_ids_on_edges == {"PA", "PB"}

    def test_different_concepts_create_different_shared_nodes(
        self, svc: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        """Distinct OMOP concepts produce distinct shared nodes."""
        _project_condition(svc, "PA", DIABETES_CONCEPT, "Diabetes")
        _project_condition(svc, "PA", HYPERTENSION_CONCEPT, "Hypertension")

        shared = (
            db_session.query(KGNode)
            .filter(KGNode.patient_id.is_(None))
            .all()
        )
        assert len(shared) == 2
        concept_ids = {n.omop_concept_id for n in shared}
        assert concept_ids == {DIABETES_CONCEPT, HYPERTENSION_CONCEPT}

    def test_shared_node_id_stable_across_calls(
        self, svc: DatabaseGraphBuilderService
    ) -> None:
        """create_node returns the same UUID for the same shared concept."""
        node_input = NodeInput(
            patient_id=None,
            node_type=NodeType.CONDITION,
            label="Diabetes",
            omop_concept_id=DIABETES_CONCEPT,
        )
        id1 = svc.create_node(node_input)
        id2 = svc.create_node(node_input)
        assert id1 == id2


# ===========================================================================
# 2. Patient node retains patient_id
# ===========================================================================


class TestPatientNodeHasPatientId:
    """Patient nodes must always have patient_id set."""

    def test_patient_node_has_patient_id(
        self, svc: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        node_id = svc.create_patient_node("PA")
        node = db_session.query(KGNode).filter_by(id=str(node_id)).one()
        assert node.patient_id == "PA"
        assert node.node_type == NodeType.PATIENT

    def test_patient_node_is_not_shared(
        self, svc: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        node_id = svc.create_patient_node("PA")
        node = db_session.query(KGNode).filter_by(id=str(node_id)).one()
        assert node.is_shared_concept is False
        assert node.is_patient_node is True


# ===========================================================================
# 3. get_nodes_for_patient returns shared concepts via edge-join
# ===========================================================================


class TestGetNodesForPatientEdgeJoin:
    """Shared concept nodes should be retrievable for a patient via edge-join.

    Uses direct DB queries to validate the data model, bypassing the SQLite
    UNION limitation in get_nodes_for_patient.
    """

    def test_returns_shared_concept_for_patient(
        self, svc: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        _project_condition(svc, "PA", DIABETES_CONCEPT, "Diabetes")

        nodes = _get_all_nodes_for_patient(db_session, "PA")
        labels = {n.label for n in nodes}
        assert "Diabetes" in labels

    def test_does_not_return_unrelated_shared_concept(
        self, svc: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        _project_condition(svc, "PA", DIABETES_CONCEPT, "Diabetes")
        _project_condition(svc, "PB", HYPERTENSION_CONCEPT, "Hypertension")

        nodes_a = _get_all_nodes_for_patient(db_session, "PA")
        labels_a = {n.label for n in nodes_a}
        assert "Diabetes" in labels_a
        assert "Hypertension" not in labels_a

    def test_patient_node_also_returned(
        self, svc: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        _project_condition(svc, "PA", DIABETES_CONCEPT, "Diabetes")

        nodes = _get_all_nodes_for_patient(db_session, "PA")
        types = {n.node_type for n in nodes}
        assert NodeType.PATIENT in types

    def test_filter_by_node_type(
        self, svc: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        _project_condition(svc, "PA", DIABETES_CONCEPT, "Diabetes")
        _project_drug(svc, "PA", ASPIRIN_CONCEPT, "Aspirin")

        concept_nodes = _get_concept_nodes_for_patient(db_session, "PA")
        conditions = [n for n in concept_nodes if n.node_type == NodeType.CONDITION]
        assert len(conditions) == 1
        assert conditions[0].omop_concept_id == DIABETES_CONCEPT


# ===========================================================================
# 4. Patient isolation
# ===========================================================================


class TestPatientIsolation:
    """Patient A's graph query must not leak Patient B's concepts."""

    def test_full_isolation(
        self, svc: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        # Concept X: only patient A
        _project_condition(svc, "PA", DIABETES_CONCEPT, "Diabetes")
        # Concept Y: only patient B
        _project_condition(svc, "PB", HYPERTENSION_CONCEPT, "Hypertension")
        # Concept Z: shared by both
        _project_drug(svc, "PA", ASPIRIN_CONCEPT, "Aspirin")
        _project_drug(svc, "PB", ASPIRIN_CONCEPT, "Aspirin")

        nodes_a = _get_all_nodes_for_patient(db_session, "PA")
        labels_a = {n.label for n in nodes_a if n.node_type != NodeType.PATIENT}
        assert "Diabetes" in labels_a
        assert "Aspirin" in labels_a
        assert "Hypertension" not in labels_a

        nodes_b = _get_all_nodes_for_patient(db_session, "PB")
        labels_b = {n.label for n in nodes_b if n.node_type != NodeType.PATIENT}
        assert "Hypertension" in labels_b
        assert "Aspirin" in labels_b
        assert "Diabetes" not in labels_b

    def test_edges_isolated_by_patient(
        self, svc: DatabaseGraphBuilderService
    ) -> None:
        _project_condition(svc, "PA", DIABETES_CONCEPT, "Diabetes")
        _project_condition(svc, "PB", HYPERTENSION_CONCEPT, "Hypertension")

        edges_a = svc.get_edges_for_patient("PA")
        assert all(e.patient_id == "PA" for e in edges_a)

        edges_b = svc.get_edges_for_patient("PB")
        assert all(e.patient_id == "PB" for e in edges_b)


# ===========================================================================
# 5. project_fact_to_graph puts assertion/experiencer on edge
# ===========================================================================


class TestProjectFactEdgeProperties:
    """Assertion, experiencer, etc. should be on edge.properties, not node.properties."""

    def test_assertion_on_edge(self, svc: DatabaseGraphBuilderService) -> None:
        _project_condition(svc, "PA", DIABETES_CONCEPT, "Diabetes", assertion="absent")

        edges = svc.get_edges_for_patient("PA")
        assert len(edges) == 1
        assert edges[0].properties["assertion"] == "absent"
        assert edges[0].properties["is_negated"] is True

    def test_experiencer_on_edge(self, svc: DatabaseGraphBuilderService, db_session: Session) -> None:
        svc.project_fact_to_graph(
            fact_id=uuid4(),
            patient_id="PA",
            domain=Domain.CONDITION,
            omop_concept_id=DIABETES_CONCEPT,
            concept_name="Diabetes",
            assertion="present",
            temporality="current",
            experiencer="family",
        )

        edges = svc.get_edges_for_patient("PA")
        assert edges[0].properties["experiencer"] == "family"

        # Also verify the first-class column
        db_edge = db_session.query(KGEdge).filter(KGEdge.patient_id == "PA").first()
        assert db_edge.experiencer == "family"

    def test_shared_node_has_no_assertion_property(
        self, svc: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        """The shared concept node itself should not carry per-patient assertion."""
        node_id = _project_condition(svc, "PA", DIABETES_CONCEPT, "Diabetes", assertion="absent")

        node = db_session.query(KGNode).filter_by(id=str(node_id)).one()
        # Node properties should have concept-level data, not assertion
        assert "assertion" not in node.properties
        assert "is_negated" not in node.properties

    def test_uncertain_fact_on_edge(self, svc: DatabaseGraphBuilderService) -> None:
        _project_condition(svc, "PA", DIABETES_CONCEPT, "Diabetes", assertion="possible")

        edges = svc.get_edges_for_patient("PA")
        assert edges[0].properties["is_uncertain"] is True

    def test_fact_id_on_edge(self, svc: DatabaseGraphBuilderService) -> None:
        fact_id = uuid4()
        svc.project_fact_to_graph(
            fact_id=fact_id,
            patient_id="PA",
            domain=Domain.CONDITION,
            omop_concept_id=DIABETES_CONCEPT,
            concept_name="Diabetes",
            assertion="present",
            temporality="current",
            experiencer="patient",
        )

        edges = svc.get_edges_for_patient("PA")
        assert edges[0].properties["fact_id"] == str(fact_id)


# ===========================================================================
# 6. KGNode.is_shared_concept property
# ===========================================================================


class TestIsSharedConceptProperty:
    """KGNode.is_shared_concept should be True when patient_id is None."""

    def test_shared_concept_is_true(
        self, svc: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        node_id = svc.create_node(
            NodeInput(
                patient_id=None,
                node_type=NodeType.CONDITION,
                label="Diabetes",
                omop_concept_id=DIABETES_CONCEPT,
            )
        )
        node = db_session.query(KGNode).filter_by(id=str(node_id)).one()
        assert node.is_shared_concept is True

    def test_patient_node_is_false(
        self, svc: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        node_id = svc.create_patient_node("PA")
        node = db_session.query(KGNode).filter_by(id=str(node_id)).one()
        assert node.is_shared_concept is False

    def test_concept_created_via_project_is_shared(
        self, svc: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        """Projecting a fact should create a shared concept node."""
        concept_node_id = _project_condition(svc, "PA", DIABETES_CONCEPT, "Diabetes")
        node = db_session.query(KGNode).filter_by(id=str(concept_node_id)).one()
        assert node.is_shared_concept is True
        assert node.patient_id is None


# ===========================================================================
# 7. calculate_node_dedup_key
# ===========================================================================


class TestCalculateNodeDedupKey:
    """Dedup key generation for shared vs. patient-owned nodes."""

    def test_shared_concept_key_uses_shared_prefix(self) -> None:
        builder = BaseGraphBuilderService()
        key = builder.calculate_node_dedup_key(
            None, NodeType.CONDITION, DIABETES_CONCEPT
        )
        assert key.startswith("__shared__:")
        assert str(DIABETES_CONCEPT) in key

    def test_patient_node_key_uses_patient_id(self) -> None:
        builder = BaseGraphBuilderService()
        key = builder.calculate_node_dedup_key(
            "PA", NodeType.PATIENT, None
        )
        assert key.startswith("PA:")
        assert "__shared__" not in key

    def test_different_concepts_have_different_keys(self) -> None:
        builder = BaseGraphBuilderService()
        key1 = builder.calculate_node_dedup_key(
            None, NodeType.CONDITION, DIABETES_CONCEPT
        )
        key2 = builder.calculate_node_dedup_key(
            None, NodeType.CONDITION, HYPERTENSION_CONCEPT
        )
        assert key1 != key2

    def test_same_concept_different_type_has_different_key(self) -> None:
        builder = BaseGraphBuilderService()
        key1 = builder.calculate_node_dedup_key(
            None, NodeType.CONDITION, DIABETES_CONCEPT
        )
        key2 = builder.calculate_node_dedup_key(
            None, NodeType.DRUG, DIABETES_CONCEPT
        )
        assert key1 != key2


# ===========================================================================
# 8. get_patient_graph edge-join (data model validation)
# ===========================================================================


class TestGetPatientGraphEdgeJoin:
    """Validate that shared concept nodes are correctly connected via edges.

    Uses direct DB queries to validate the data model invariants that
    get_patient_graph relies on (PostgreSQL UNION queries).
    """

    def test_patient_graph_includes_shared_nodes(
        self, svc: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        fact = ClinicalFact(
            patient_id="PA",
            domain=Domain.CONDITION,
            omop_concept_id=DIABETES_CONCEPT,
            concept_name="Diabetes",
            assertion=Assertion.PRESENT,
            temporality=Temporality.CURRENT,
            experiencer=Experiencer.PATIENT,
        )
        db_session.add(fact)
        db_session.flush()

        svc.build_graph_for_patient("PA")

        nodes = _get_all_nodes_for_patient(db_session, "PA")
        assert len(nodes) >= 2
        node_types = {n.node_type for n in nodes}
        assert NodeType.PATIENT in node_types
        assert NodeType.CONDITION in node_types

    def test_patient_graph_excludes_other_patients_concepts(
        self, svc: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        fact_a = ClinicalFact(
            patient_id="PA",
            domain=Domain.CONDITION,
            omop_concept_id=DIABETES_CONCEPT,
            concept_name="Diabetes",
            assertion=Assertion.PRESENT,
            temporality=Temporality.CURRENT,
            experiencer=Experiencer.PATIENT,
        )
        fact_b = ClinicalFact(
            patient_id="PB",
            domain=Domain.CONDITION,
            omop_concept_id=HYPERTENSION_CONCEPT,
            concept_name="Hypertension",
            assertion=Assertion.PRESENT,
            temporality=Temporality.CURRENT,
            experiencer=Experiencer.PATIENT,
        )
        db_session.add(fact_a)
        db_session.add(fact_b)
        db_session.flush()

        svc.build_graph_for_patient("PA")

        svc_b = DatabaseGraphBuilderService(db_session)
        svc_b.build_graph_for_patient("PB")

        nodes_a = _get_all_nodes_for_patient(db_session, "PA")
        labels_a = {n.label for n in nodes_a}
        assert "Diabetes" in labels_a
        assert "Hypertension" not in labels_a

    def test_patient_graph_edges_all_belong_to_patient(
        self, svc: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        fact = ClinicalFact(
            patient_id="PA",
            domain=Domain.CONDITION,
            omop_concept_id=DIABETES_CONCEPT,
            concept_name="Diabetes",
            assertion=Assertion.PRESENT,
            temporality=Temporality.CURRENT,
            experiencer=Experiencer.PATIENT,
        )
        db_session.add(fact)
        db_session.flush()

        svc.build_graph_for_patient("PA")

        edges = db_session.query(KGEdge).filter(KGEdge.patient_id == "PA").all()
        for edge in edges:
            assert edge.patient_id == "PA"

    def test_shared_concept_visible_to_both_patients(
        self, svc: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        """When two patients share a concept, both patient graphs include it.

        Uses project_fact_to_graph directly (single service instance) to
        avoid the cross-service cache priming issue with build_graph_for_patient.
        """
        _project_drug(svc, "PA", ASPIRIN_CONCEPT, "Aspirin")
        _project_drug(svc, "PB", ASPIRIN_CONCEPT, "Aspirin")

        nodes_a = _get_all_nodes_for_patient(db_session, "PA")
        nodes_b = _get_all_nodes_for_patient(db_session, "PB")

        labels_a = {n.label for n in nodes_a}
        labels_b = {n.label for n in nodes_b}
        assert "Aspirin" in labels_a
        assert "Aspirin" in labels_b

        # But only one Aspirin node in the whole DB
        aspirin_nodes = (
            db_session.query(KGNode)
            .filter(KGNode.omop_concept_id == ASPIRIN_CONCEPT)
            .all()
        )
        assert len(aspirin_nodes) == 1
