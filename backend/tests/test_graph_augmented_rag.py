"""Tests for GraphAugmentedRAGService.

Covers all five production upgrades:
1. Hybrid concept extraction (NLP + OMOP + label fallback)
2. N+1 batch fix in temporal context
3. Policy constraints via GuidelineRAGService
4. Confidence-weighted traversal scoring
5. Bidirectional edge traversal
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.document import Document
from app.models.knowledge_graph import KGEdge, KGNode
from app.schemas.knowledge_graph import EdgeType, NodeType
from app.services.graph_augmented_rag import (
    MIN_TRAVERSAL_CONFIDENCE,
    GraphAugmentedRAGService,
    QueryConcept,
    _score_and_filter_edges,
)

# ---------------------------------------------------------------------------
# Test database setup
# ---------------------------------------------------------------------------

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
    """Create a database session with KG + Document tables."""
    KGNode.__table__.create(bind=_test_engine, checkfirst=True)
    KGEdge.__table__.create(bind=_test_engine, checkfirst=True)
    Document.__table__.create(bind=_test_engine, checkfirst=True)

    session = _TestSession()
    try:
        yield session
    finally:
        session.close()
        Document.__table__.drop(bind=_test_engine, checkfirst=True)
        KGEdge.__table__.drop(bind=_test_engine, checkfirst=True)
        KGNode.__table__.drop(bind=_test_engine, checkfirst=True)


@pytest.fixture
def rag_service(db_session: Session) -> GraphAugmentedRAGService:
    """Create a GraphAugmentedRAGService backed by the test session."""
    return GraphAugmentedRAGService(db_session)


# ---------------------------------------------------------------------------
# Helpers: seed graph data
# ---------------------------------------------------------------------------

def _make_patient_node(session: Session, patient_id: str = "P001") -> KGNode:
    node = KGNode(
        id=str(uuid4()),
        patient_id=patient_id,
        node_type=NodeType.PATIENT,
        label=f"Patient {patient_id}",
    )
    session.add(node)
    session.flush()
    return node


def _make_concept_node(
    session: Session,
    label: str,
    node_type: NodeType,
    omop_concept_id: int | None = None,
    patient_id: str | None = None,
) -> KGNode:
    node = KGNode(
        id=str(uuid4()),
        patient_id=patient_id,
        node_type=node_type,
        label=label,
        omop_concept_id=omop_concept_id,
    )
    session.add(node)
    session.flush()
    return node


def _make_edge(
    session: Session,
    source: KGNode,
    target: KGNode,
    patient_id: str,
    edge_type: EdgeType,
    temporality: str | None = "current",
    temporal_confidence: float = 0.9,
    event_date: datetime | None = None,
) -> KGEdge:
    edge = KGEdge(
        id=str(uuid4()),
        patient_id=patient_id,
        source_node_id=source.id,
        target_node_id=target.id,
        edge_type=edge_type,
        temporality=temporality,
        temporal_confidence=temporal_confidence,
        event_date=event_date,
    )
    session.add(edge)
    session.flush()
    return edge


# ===========================================================================
# Step 1: Concept Extraction Tests
# ===========================================================================

class TestConceptExtraction:
    """Test hybrid NLP + label fallback concept extraction."""

    def test_quoted_terms_extracted(self, rag_service: GraphAugmentedRAGService) -> None:
        """Quoted terms in query are always extracted."""
        concepts = rag_service._extract_query_concepts('What about "diabetes mellitus"?')
        texts = [c.text for c in concepts]
        assert "diabetes mellitus" in texts

    def test_multiple_quoted_terms(self, rag_service: GraphAugmentedRAGService) -> None:
        concepts = rag_service._extract_query_concepts('"metformin" and "diabetes"')
        texts = [c.text.lower() for c in concepts]
        assert "metformin" in texts
        assert "diabetes" in texts

    def test_quoted_terms_have_confidence(self, rag_service: GraphAugmentedRAGService) -> None:
        concepts = rag_service._extract_query_concepts('"aspirin"')
        assert concepts[0].confidence == pytest.approx(0.9)

    @patch("app.services.nlp_entity.get_nlp_entity_service")
    def test_nlp_entities_extracted(self, mock_get_nlp: MagicMock, rag_service: GraphAugmentedRAGService) -> None:
        """NLP entity extraction is used when available."""
        mock_entity = MagicMock()
        mock_entity.text = "diabetes"
        mock_entity.entity_type = MagicMock(value="diagnosis")
        mock_entity.confidence = 0.95

        mock_result = MagicMock()
        mock_result.entities = [mock_entity]

        mock_service = MagicMock()
        mock_service.extract_entities.return_value = mock_result
        mock_get_nlp.return_value = mock_service

        concepts = rag_service._extract_query_concepts("Patient has diabetes")
        entity_concepts = [c for c in concepts if c.entity_type == "diagnosis"]
        assert len(entity_concepts) >= 1
        assert entity_concepts[0].text == "diabetes"
        assert entity_concepts[0].confidence == 0.95

    @patch("app.services.nlp_entity.get_nlp_entity_service", side_effect=ImportError("no nlp"))
    def test_nlp_fallback_graceful(self, mock_get_nlp: MagicMock, rag_service: GraphAugmentedRAGService) -> None:
        """If NLP service is unavailable, extraction still works via quoted terms."""
        concepts = rag_service._extract_query_concepts('"heart failure"')
        assert len(concepts) >= 1
        assert any(c.text == "heart failure" for c in concepts)

    def test_deduplication(self, rag_service: GraphAugmentedRAGService) -> None:
        """Same term from NLP and quotes should not duplicate."""
        with patch("app.services.nlp_entity.get_nlp_entity_service") as mock_get_nlp:
            mock_entity = MagicMock()
            mock_entity.text = "diabetes"
            mock_entity.entity_type = MagicMock(value="diagnosis")
            mock_entity.confidence = 0.95

            mock_result = MagicMock()
            mock_result.entities = [mock_entity]
            mock_service = MagicMock()
            mock_service.extract_entities.return_value = mock_result
            mock_get_nlp.return_value = mock_service

            concepts = rag_service._extract_query_concepts('patient has "diabetes"')
            diabetes_concepts = [c for c in concepts if c.text.lower() == "diabetes"]
            assert len(diabetes_concepts) == 1

    def test_returns_query_concept_type(self, rag_service: GraphAugmentedRAGService) -> None:
        """_extract_query_concepts returns list[QueryConcept]."""
        concepts = rag_service._extract_query_concepts('"test"')
        assert all(isinstance(c, QueryConcept) for c in concepts)


# ===========================================================================
# Step 1 continued: Node matching with OMOP IDs
# ===========================================================================

class TestNodeMatching:
    """Test that node matching prefers OMOP ID over label substring."""

    def test_empty_concepts_returns_patient_node(
        self, db_session: Session, rag_service: GraphAugmentedRAGService
    ) -> None:
        patient = _make_patient_node(db_session, "P001")
        nodes = rag_service._find_matching_nodes("P001", [])
        assert len(nodes) == 1
        assert nodes[0].id == patient.id

    def test_label_match_finds_nodes(
        self, db_session: Session, rag_service: GraphAugmentedRAGService
    ) -> None:
        patient = _make_patient_node(db_session, "P001")
        condition = _make_concept_node(db_session, "Diabetes Mellitus", NodeType.CONDITION)
        _make_edge(db_session, patient, condition, "P001", EdgeType.HAS_CONDITION)

        concepts = [QueryConcept(text="diabetes")]
        nodes = rag_service._find_matching_nodes("P001", concepts)
        assert any(n.id == condition.id for n in nodes)

    def test_omop_id_match_preferred(
        self, db_session: Session, rag_service: GraphAugmentedRAGService
    ) -> None:
        patient = _make_patient_node(db_session, "P001")
        condition = _make_concept_node(
            db_session, "Type 2 DM", NodeType.CONDITION, omop_concept_id=201826
        )
        _make_edge(db_session, patient, condition, "P001", EdgeType.HAS_CONDITION)

        # OMOP ID match — even though label doesn't contain "diabetes"
        concepts = [QueryConcept(text="diabetes", omop_concept_id=201826)]
        nodes = rag_service._find_matching_nodes("P001", concepts)
        assert any(n.id == condition.id for n in nodes)


# ===========================================================================
# Step 2: N+1 Fix Tests
# ===========================================================================

class TestTemporalContextBatch:
    """Test that temporal context uses batch queries instead of N+1."""

    def test_temporal_context_returns_timeline(
        self, db_session: Session, rag_service: GraphAugmentedRAGService
    ) -> None:
        patient = _make_patient_node(db_session, "P001")
        drug = _make_concept_node(db_session, "Metformin", NodeType.DRUG)
        _make_edge(
            db_session, patient, drug, "P001", EdgeType.TAKES_DRUG,
            temporality="current",
            event_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
        )

        ctx = rag_service._get_temporal_context("P001", time_point=None)
        assert len(ctx.event_timeline) == 1
        assert ctx.current_state.get("Metformin") == "active"

    def test_temporal_context_batch_handles_many_edges(
        self, db_session: Session, rag_service: GraphAugmentedRAGService
    ) -> None:
        """Batch fetch handles multiple edges without N+1."""
        patient = _make_patient_node(db_session, "P001")
        for i in range(10):
            node = _make_concept_node(db_session, f"Condition_{i}", NodeType.CONDITION)
            _make_edge(
                db_session, patient, node, "P001", EdgeType.HAS_CONDITION,
                temporality="current",
                event_date=datetime(2024, 1, i + 1, tzinfo=timezone.utc),
            )

        ctx = rag_service._get_temporal_context("P001", time_point=None)
        assert len(ctx.event_timeline) == 10
        assert len(ctx.current_state) == 10

    def test_historical_state_tracked(
        self, db_session: Session, rag_service: GraphAugmentedRAGService
    ) -> None:
        patient = _make_patient_node(db_session, "P001")
        old_drug = _make_concept_node(db_session, "Aspirin", NodeType.DRUG)
        _make_edge(
            db_session, patient, old_drug, "P001", EdgeType.TAKES_DRUG,
            temporality="past",
            event_date=datetime(2023, 6, 1, tzinfo=timezone.utc),
        )

        ctx = rag_service._get_temporal_context("P001", time_point=None)
        assert ctx.historical_state.get("Aspirin") == "resolved"


# ===========================================================================
# Step 3: Policy Constraints Tests
# ===========================================================================

class TestPolicyConstraints:
    """Test GuidelineRAGService integration for policy constraints."""

    @patch("app.services.guideline_rag_service.get_guideline_rag_service")
    def test_returns_guideline_citations(
        self, mock_get_guideline: MagicMock, rag_service: GraphAugmentedRAGService
    ) -> None:
        mock_section = MagicMock()
        mock_section.section_id = "ADA-2024-A1C"
        mock_section.guideline = "ADA Standards of Care"
        mock_section.recommendation_text = "Target A1C <7% for most adults"
        mock_section.recommendation_level = "A"
        mock_section.evidence_grade = "High"

        mock_citation = MagicMock()
        mock_citation.section = mock_section
        mock_citation.score = 0.85

        mock_service = MagicMock()
        mock_service.is_loaded = True
        mock_service.search.return_value = [mock_citation]
        mock_get_guideline.return_value = mock_service

        concepts = [QueryConcept(text="diabetes", entity_type="diagnosis")]
        constraints = rag_service._get_policy_constraints("P001", concepts)

        assert len(constraints) == 1
        assert constraints[0]["rule_id"] == "ADA-2024-A1C"
        assert "ADA Standards of Care" in constraints[0]["description"]
        assert constraints[0]["strength"] == "A"

    @patch("app.services.guideline_rag_service.get_guideline_rag_service")
    def test_empty_when_no_match(
        self, mock_get_guideline: MagicMock, rag_service: GraphAugmentedRAGService
    ) -> None:
        mock_service = MagicMock()
        mock_service.is_loaded = True
        mock_service.search.return_value = []
        mock_get_guideline.return_value = mock_service

        concepts = [QueryConcept(text="obscure thing")]
        constraints = rag_service._get_policy_constraints("P001", concepts)
        assert constraints == []

    def test_empty_concepts_returns_empty(
        self, rag_service: GraphAugmentedRAGService
    ) -> None:
        constraints = rag_service._get_policy_constraints("P001", [])
        assert constraints == []

    @patch(
        "app.services.guideline_rag_service.get_guideline_rag_service",
        side_effect=ImportError("no guideline service"),
    )
    def test_graceful_failure(
        self, mock_get_guideline: MagicMock, rag_service: GraphAugmentedRAGService
    ) -> None:
        concepts = [QueryConcept(text="diabetes")]
        constraints = rag_service._get_policy_constraints("P001", concepts)
        assert constraints == []


# ===========================================================================
# Step 4: Confidence-Weighted Traversal Tests
# ===========================================================================

class TestConfidenceScoring:
    """Test edge scoring and filtering logic."""

    def _make_mock_edge(
        self,
        edge_type: EdgeType,
        confidence: float,
        temporality: str = "current",
    ) -> MagicMock:
        edge = MagicMock(spec=KGEdge)
        edge.edge_type = edge_type
        edge.temporal_confidence = confidence
        edge.temporality = temporality
        return edge

    def test_low_confidence_edges_pruned(self) -> None:
        edges = [
            self._make_mock_edge(EdgeType.HAS_CONDITION, 0.1),
            self._make_mock_edge(EdgeType.HAS_CONDITION, 0.8),
        ]
        filtered = _score_and_filter_edges(edges, [])
        assert len(filtered) == 1
        assert filtered[0].temporal_confidence == 0.8

    def test_query_relevant_edges_boosted(self) -> None:
        """Medication query should prefer TAKES_DRUG over HAS_CONDITION."""
        drug_edge = self._make_mock_edge(EdgeType.TAKES_DRUG, 0.7)
        cond_edge = self._make_mock_edge(EdgeType.HAS_CONDITION, 0.7)
        edges = [cond_edge, drug_edge]

        concepts = [QueryConcept(text="metformin", entity_type="medication")]
        filtered = _score_and_filter_edges(edges, concepts)

        # Drug edge should be first (boosted by query relevance)
        assert filtered[0] is drug_edge

    def test_current_preferred_over_historical(self) -> None:
        current = self._make_mock_edge(EdgeType.HAS_CONDITION, 0.7, temporality="current")
        past = self._make_mock_edge(EdgeType.HAS_CONDITION, 0.7, temporality="past")
        filtered = _score_and_filter_edges([past, current], [])

        # Current should be ranked higher
        assert filtered[0] is current

    def test_all_low_confidence_returns_empty(self) -> None:
        edges = [
            self._make_mock_edge(EdgeType.HAS_CONDITION, 0.1),
            self._make_mock_edge(EdgeType.TAKES_DRUG, 0.2),
        ]
        filtered = _score_and_filter_edges(edges, [])
        assert len(filtered) == 0

    def test_high_confidence_sorted_first(self) -> None:
        low = self._make_mock_edge(EdgeType.HAS_CONDITION, 0.5)
        high = self._make_mock_edge(EdgeType.HAS_CONDITION, 0.95)
        filtered = _score_and_filter_edges([low, high], [])
        assert filtered[0] is high


# ===========================================================================
# Step 5: Bidirectional Traversal Tests
# ===========================================================================

class TestBidirectionalTraversal:
    """Test that BFS follows both outgoing and incoming edges."""

    def test_outgoing_edges_followed(
        self, db_session: Session, rag_service: GraphAugmentedRAGService
    ) -> None:
        patient = _make_patient_node(db_session, "P001")
        condition = _make_concept_node(db_session, "Diabetes", NodeType.CONDITION)
        _make_edge(db_session, patient, condition, "P001", EdgeType.HAS_CONDITION)

        paths = rag_service._bfs_traverse(
            patient_id="P001",
            start_node=patient,
            query_concepts=[],
            max_hops=1,
        )
        assert len(paths) >= 1
        assert any("Diabetes" in str(p.nodes) for p in paths)

    def test_incoming_edges_followed(
        self, db_session: Session, rag_service: GraphAugmentedRAGService
    ) -> None:
        """Starting from a condition, incoming edges from patient are followed."""
        patient = _make_patient_node(db_session, "P001")
        condition = _make_concept_node(db_session, "Diabetes", NodeType.CONDITION)
        # Edge goes patient -> condition, so from condition's perspective it's incoming
        _make_edge(db_session, patient, condition, "P001", EdgeType.HAS_CONDITION)

        paths = rag_service._bfs_traverse(
            patient_id="P001",
            start_node=condition,
            query_concepts=[],
            max_hops=1,
        )
        # Should find the patient via the incoming edge
        assert len(paths) >= 1
        labels = [n.get("label", "") for p in paths for n in p.nodes]
        assert any("Patient" in lbl for lbl in labels)

    def test_drug_treats_condition_bidirectional(
        self, db_session: Session, rag_service: GraphAugmentedRAGService
    ) -> None:
        """From a condition node, can find treating drug via incoming DRUG_TREATS edge."""
        condition = _make_concept_node(db_session, "Diabetes", NodeType.CONDITION)
        drug = _make_concept_node(db_session, "Metformin", NodeType.DRUG)
        # drug -> condition edge (DRUG_TREATS)
        _make_edge(db_session, drug, condition, "P001", EdgeType.DRUG_TREATS)

        paths = rag_service._bfs_traverse(
            patient_id="P001",
            start_node=condition,
            query_concepts=[],
            max_hops=1,
        )
        labels = [n.get("label", "") for p in paths for n in p.nodes]
        assert "Metformin" in labels


# ===========================================================================
# Integration: End-to-end retrieve_context
# ===========================================================================

class TestRetrieveContextIntegration:
    """Test the full sync retrieve_context pipeline."""

    @patch("app.services.nlp_entity.get_nlp_entity_service")
    @patch("app.services.guideline_rag_service.get_guideline_rag_service")
    def test_full_pipeline_sync(
        self,
        mock_guideline: MagicMock,
        mock_nlp: MagicMock,
        db_session: Session,
        rag_service: GraphAugmentedRAGService,
    ) -> None:
        # Setup NLP mock
        mock_entity = MagicMock()
        mock_entity.text = "diabetes"
        mock_entity.entity_type = MagicMock(value="diagnosis")
        mock_entity.confidence = 0.95

        mock_result = MagicMock()
        mock_result.entities = [mock_entity]
        mock_nlp_svc = MagicMock()
        mock_nlp_svc.extract_entities.return_value = mock_result
        mock_nlp.return_value = mock_nlp_svc

        # Setup guideline mock
        mock_guideline_svc = MagicMock()
        mock_guideline_svc.is_loaded = True
        mock_guideline_svc.search.return_value = []
        mock_guideline.return_value = mock_guideline_svc

        # Seed graph
        patient = _make_patient_node(db_session, "P001")
        condition = _make_concept_node(db_session, "Diabetes Mellitus", NodeType.CONDITION)
        drug = _make_concept_node(db_session, "Metformin", NodeType.DRUG)
        _make_edge(
            db_session, patient, condition, "P001", EdgeType.HAS_CONDITION,
            event_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        _make_edge(
            db_session, condition, drug, "P001", EdgeType.CONDITION_TREATED_BY,
            event_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
        )

        context = rag_service.retrieve_context(
            query="What medications is this patient on for diabetes?",
            patient_id="P001",
            max_hops=2,
        )

        assert context.patient_id == "P001"
        assert len(context.graph_paths) >= 1

    def test_empty_graph_returns_context(
        self, db_session: Session, rag_service: GraphAugmentedRAGService
    ) -> None:
        """Service handles empty graph without crashing."""
        context = rag_service.retrieve_context(
            query="anything",
            patient_id="P999",
            include_temporal=False,
            include_policies=False,
        )
        assert context.graph_paths == []
        assert context.total_evidence_pieces == 0


# ===========================================================================
# QueryConcept dataclass tests
# ===========================================================================

class TestQueryConcept:
    """Test the QueryConcept dataclass."""

    def test_defaults(self) -> None:
        qc = QueryConcept(text="test")
        assert qc.entity_type is None
        assert qc.omop_concept_id is None
        assert qc.confidence == 1.0

    def test_full_construction(self) -> None:
        qc = QueryConcept(
            text="metformin",
            entity_type="medication",
            omop_concept_id=1503297,
            confidence=0.95,
        )
        assert qc.text == "metformin"
        assert qc.omop_concept_id == 1503297
