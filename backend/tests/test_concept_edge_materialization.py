"""Tests for concept→concept edge materialization (Phase 1).

Validates that OMOP lateral relationships between shared concept nodes
are correctly materialized as KGEdges in the patient's knowledge graph.
"""

from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.clinical_fact import ClinicalFact
from app.models.knowledge_graph import KGEdge, KGNode
from app.schemas.base import Assertion, Domain, Experiencer, Temporality
from app.schemas.knowledge_graph import EdgeType, NodeType
from app.services.graph_builder import EdgeInput, NodeInput
from app.services.graph_builder_db import DatabaseGraphBuilderService

# In-memory SQLite test engine
_test_engine = create_engine("sqlite:///:memory:", echo=False, future=True)
_TestSession = sessionmaker(bind=_test_engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="function")
def db_session() -> Session:
    """Create a database session with KG tables."""
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


def _seed_patient_with_drug_and_condition(
    graph_service: DatabaseGraphBuilderService,
    patient_id: str = "P001",
    drug_concept_id: int = 1503297,
    condition_concept_id: int = 201826,
) -> tuple[UUID, UUID, UUID]:
    """Helper: Create patient node with drug and condition concept nodes.

    Returns:
        (patient_node_id, drug_node_id, condition_node_id)
    """
    patient_node_id = graph_service.create_patient_node(patient_id)

    drug_node_id = graph_service.create_node(NodeInput(
        patient_id=None,
        node_type=NodeType.DRUG,
        label="Metformin",
        omop_concept_id=drug_concept_id,
        properties={"domain": "Drug"},
    ))

    condition_node_id = graph_service.create_node(NodeInput(
        patient_id=None,
        node_type=NodeType.CONDITION,
        label="Type 2 diabetes mellitus",
        omop_concept_id=condition_concept_id,
        properties={"domain": "Condition"},
    ))

    # Create patient→drug and patient→condition edges
    graph_service.create_edge(EdgeInput(
        patient_id=patient_id,
        source_node_id=patient_node_id,
        target_node_id=drug_node_id,
        edge_type=EdgeType.TAKES_DRUG,
    ))
    graph_service.create_edge(EdgeInput(
        patient_id=patient_id,
        source_node_id=patient_node_id,
        target_node_id=condition_node_id,
        edge_type=EdgeType.HAS_CONDITION,
    ))

    return patient_node_id, drug_node_id, condition_node_id


class TestConceptEdgeMaterialization:
    """Tests for _materialize_concept_edges method."""

    def test_drug_treats_condition_edge_created(
        self, graph_service: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        """Seed Drug + Condition with OMOP 'May treat', verify DRUG_TREATS edge."""
        patient_id = "P001"
        drug_concept = 1503297
        condition_concept = 201826

        _seed_patient_with_drug_and_condition(
            graph_service, patient_id, drug_concept, condition_concept
        )

        # Mock the OMOP relationship query to return "May treat"
        mock_rows = [
            (drug_concept, condition_concept, "May treat"),
        ]
        with patch.object(
            db_session, "execute",
            side_effect=_make_execute_interceptor(db_session, mock_rows, drug_concept, condition_concept),
        ):
            count = graph_service._materialize_concept_edges(patient_id)

        assert count == 1

        # Verify the edge exists
        edges = db_session.query(KGEdge).filter(
            KGEdge.edge_type == EdgeType.DRUG_TREATS,
            KGEdge.patient_id == patient_id,
        ).all()
        assert len(edges) == 1
        assert edges[0].properties.get("source") == "omop_concept_relationship"

    def test_no_duplicate_concept_edges_on_rebuild(
        self, graph_service: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        """Run materialization twice, verify no duplication."""
        patient_id = "P001"
        drug_concept = 1503297
        condition_concept = 201826

        _seed_patient_with_drug_and_condition(
            graph_service, patient_id, drug_concept, condition_concept
        )

        mock_rows = [(drug_concept, condition_concept, "May treat")]

        with patch.object(
            db_session, "execute",
            side_effect=_make_execute_interceptor(db_session, mock_rows, drug_concept, condition_concept),
        ):
            count1 = graph_service._materialize_concept_edges(patient_id)
            count2 = graph_service._materialize_concept_edges(patient_id)

        # First call creates 1, second creates 0 (dedup)
        assert count1 == 1
        assert count2 == 1  # _batch_create_edges returns existing IDs too

        # But only 1 actual edge exists
        edges = db_session.query(KGEdge).filter(
            KGEdge.edge_type == EdgeType.DRUG_TREATS,
            KGEdge.patient_id == patient_id,
        ).all()
        assert len(edges) == 1

    def test_concept_edges_shared_across_patients(
        self, graph_service: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        """Two patients, same concepts, verify shared concept→concept edge.

        Concept→concept edges between shared nodes are deduplicated by
        (source_node_id, target_node_id, edge_type). The first patient to
        trigger materialization creates the edge; subsequent patients reuse it.
        """
        drug_concept = 1503297
        condition_concept = 201826

        _seed_patient_with_drug_and_condition(
            graph_service, "P001", drug_concept, condition_concept
        )

        # Create second patient with same concepts
        p2_node = graph_service.create_patient_node("P002")
        # The shared concept nodes are reused (dedup)
        drug_node = graph_service._node_dedup_cache.get(
            f"__shared__:drug:{drug_concept}"
        )
        condition_node = graph_service._node_dedup_cache.get(
            f"__shared__:condition:{condition_concept}"
        )
        assert drug_node is not None
        assert condition_node is not None

        graph_service.create_edge(EdgeInput(
            patient_id="P002",
            source_node_id=p2_node,
            target_node_id=drug_node,
            edge_type=EdgeType.TAKES_DRUG,
        ))
        graph_service.create_edge(EdgeInput(
            patient_id="P002",
            source_node_id=p2_node,
            target_node_id=condition_node,
            edge_type=EdgeType.HAS_CONDITION,
        ))

        mock_rows = [(drug_concept, condition_concept, "May treat")]

        with patch.object(
            db_session, "execute",
            side_effect=_make_execute_interceptor(db_session, mock_rows, drug_concept, condition_concept),
        ):
            graph_service._materialize_concept_edges("P001")
            graph_service._materialize_concept_edges("P002")

        # Concept→concept edge is shared (dedup by source/target/type)
        all_drug_treats = db_session.query(KGEdge).filter(
            KGEdge.edge_type == EdgeType.DRUG_TREATS,
        ).all()
        # Only one edge exists between the shared concept nodes
        assert len(all_drug_treats) == 1
        # First materializer's patient_id is stored
        assert all_drug_treats[0].patient_id == "P001"

    def test_empty_concept_relationship_handled(
        self, graph_service: DatabaseGraphBuilderService, db_session: Session
    ) -> None:
        """Graceful zero-edge result when no OMOP relationships exist."""
        patient_id = "P001"
        _seed_patient_with_drug_and_condition(graph_service, patient_id)

        # Mock empty result
        with patch.object(
            db_session, "execute",
            side_effect=_make_execute_interceptor(db_session, [], 0, 0),
        ):
            count = graph_service._materialize_concept_edges(patient_id)

        assert count == 0

    def test_single_concept_returns_zero(
        self, graph_service: DatabaseGraphBuilderService
    ) -> None:
        """When patient has only one concept, return 0 edges (need >= 2)."""
        patient_id = "P_SINGLE"
        graph_service.create_patient_node(patient_id)
        graph_service.create_node(NodeInput(
            patient_id=None,
            node_type=NodeType.DRUG,
            label="Aspirin",
            omop_concept_id=1112807,
        ))
        # Patient node is not a concept, so only 1 concept node
        count = graph_service._materialize_concept_edges(patient_id)
        assert count == 0


def _make_execute_interceptor(real_session, mock_rows, *concept_ids):
    """Create a session.execute interceptor that returns mock rows for OMOP queries."""
    real_execute = real_session.__class__.execute

    def interceptor(self, statement, *args, **kwargs):
        # Check if this is our OMOP lateral rel query
        stmt_str = str(statement)
        if "concept_relationships" in stmt_str:
            mock_result = MagicMock()
            mock_result.fetchall.return_value = mock_rows
            return mock_result
        # Fall through to real execute for all other queries
        return real_execute(self, statement, *args, **kwargs)

    return lambda stmt, *a, **kw: interceptor(real_session, stmt, *a, **kw)
