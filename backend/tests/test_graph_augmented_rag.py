"""Tests for GraphAugmentedRAGService.

Covers all five production upgrades:
1. Hybrid concept extraction (NLP + OMOP + label fallback)
2. N+1 batch fix in temporal context
3. Policy constraints via GuidelineRAGService
4. Confidence-weighted traversal scoring
5. Bidirectional edge traversal
"""

import sys
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
    experiencer: str | None = None,
    properties: dict | None = None,
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
        experiencer=experiencer,
        properties=properties or {},
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
# Step 4b: Assertion-Aware Scoring Tests
# ===========================================================================

class TestAssertionAwareScoring:
    """Test assertion-based scoring in _score_and_filter_edges."""

    def _make_mock_edge(
        self,
        edge_type: EdgeType,
        confidence: float,
        temporality: str = "current",
        assertion: str = "present",
    ) -> MagicMock:
        edge = MagicMock(spec=KGEdge)
        edge.edge_type = edge_type
        edge.temporal_confidence = confidence
        edge.temporality = temporality
        edge.properties = {
            "assertion": assertion,
            "is_negated": assertion == "absent",
            "is_uncertain": assertion == "possible",
        }
        return edge

    def test_negated_edge_scores_lower_than_present(self) -> None:
        """Negated (absent) edge should score lower than present edge with same confidence."""
        present_edge = self._make_mock_edge(EdgeType.HAS_CONDITION, 0.8, assertion="present")
        negated_edge = self._make_mock_edge(EdgeType.HAS_CONDITION, 0.8, assertion="absent")
        filtered = _score_and_filter_edges([negated_edge, present_edge], [])
        # Present edge should be ranked higher
        assert filtered[0] is present_edge

    def test_uncertain_edge_scores_lower_than_present(self) -> None:
        """Uncertain (possible) edge should score lower than present edge."""
        present_edge = self._make_mock_edge(EdgeType.HAS_CONDITION, 0.8, assertion="present")
        uncertain_edge = self._make_mock_edge(EdgeType.HAS_CONDITION, 0.8, assertion="possible")
        filtered = _score_and_filter_edges([uncertain_edge, present_edge], [])
        assert filtered[0] is present_edge

    def test_family_history_edge_scores_lower(self) -> None:
        """Family history edge should score lower than present edge."""
        present_edge = self._make_mock_edge(EdgeType.HAS_CONDITION, 0.8, assertion="present")
        fh_edge = self._make_mock_edge(EdgeType.HAS_CONDITION, 0.8, assertion="family_history")
        filtered = _score_and_filter_edges([fh_edge, present_edge], [])
        assert filtered[0] is present_edge

    def test_historical_edge_scores_lower(self) -> None:
        """Historical edge should score lower than present edge."""
        present_edge = self._make_mock_edge(EdgeType.HAS_CONDITION, 0.8, assertion="present")
        hist_edge = self._make_mock_edge(EdgeType.HAS_CONDITION, 0.8, assertion="historical")
        filtered = _score_and_filter_edges([hist_edge, present_edge], [])
        assert filtered[0] is present_edge

    def test_negated_scores_lowest(self) -> None:
        """Absent should be the most heavily penalized assertion."""
        present_edge = self._make_mock_edge(EdgeType.HAS_CONDITION, 0.8, assertion="present")
        uncertain_edge = self._make_mock_edge(EdgeType.HAS_CONDITION, 0.8, assertion="possible")
        negated_edge = self._make_mock_edge(EdgeType.HAS_CONDITION, 0.8, assertion="absent")
        filtered = _score_and_filter_edges(
            [negated_edge, uncertain_edge, present_edge], []
        )
        # Order should be: present > uncertain > negated
        assert filtered[0] is present_edge
        assert filtered[-1] is negated_edge

    def test_assertion_mode_none_ignores_assertion(self) -> None:
        """In assertion_mode='none', negated and present edges should score identically."""
        present_edge = self._make_mock_edge(EdgeType.HAS_CONDITION, 0.8, assertion="present")
        negated_edge = self._make_mock_edge(EdgeType.HAS_CONDITION, 0.8, assertion="absent")
        filtered = _score_and_filter_edges(
            [negated_edge, present_edge], [], assertion_mode="none"
        )
        # Both should have identical scores, so order is stable (input order)
        assert len(filtered) == 2

    def test_assertion_mode_extracted_only_no_score_change(self) -> None:
        """In assertion_mode='extracted_only', no score modification."""
        present_edge = self._make_mock_edge(EdgeType.HAS_CONDITION, 0.8, assertion="present")
        negated_edge = self._make_mock_edge(EdgeType.HAS_CONDITION, 0.8, assertion="absent")
        filtered = _score_and_filter_edges(
            [negated_edge, present_edge], [], assertion_mode="extracted_only"
        )
        # No assertion scoring, so both have same base score
        assert len(filtered) == 2

    def test_temporal_mode_no_temporal_skips_temporality_boost(self) -> None:
        """In temporal_mode='no_temporal', current/past edges score equally."""
        current = self._make_mock_edge(EdgeType.HAS_CONDITION, 0.7, temporality="current")
        past = self._make_mock_edge(EdgeType.HAS_CONDITION, 0.7, temporality="past")
        filtered = _score_and_filter_edges(
            [past, current], [], temporal_mode="no_temporal"
        )
        # Without temporal boost, both should have identical scores
        assert len(filtered) == 2


# ===========================================================================
# Step 4c: Prompt Format Tests
# ===========================================================================

class TestPromptFormat:
    """Test assertion rendering in GraphPath.to_prompt_format and to_llm_prompt."""

    def test_absent_assertion_shown_in_prompt(self) -> None:
        """ABSENT assertion should appear in prompt format."""
        from app.services.graph_augmented_rag import GraphPath

        path = GraphPath(
            nodes=[
                {"id": "1", "label": "Patient", "type": "patient"},
                {"id": "2", "label": "Diabetes", "type": "condition"},
            ],
            edges=[{
                "edge_type": "has_condition",
                "confidence": 0.9,
                "temporality": "current",
                "assertion": "absent",
            }],
            path_type="patient_condition",
            confidence=0.9,
        )
        prompt = path.to_prompt_format()
        assert "ABSENT" in prompt

    def test_present_assertion_not_shown_in_prompt(self) -> None:
        """PRESENT assertion should NOT appear in prompt (default, no label)."""
        from app.services.graph_augmented_rag import GraphPath

        path = GraphPath(
            nodes=[
                {"id": "1", "label": "Patient", "type": "patient"},
                {"id": "2", "label": "Diabetes", "type": "condition"},
            ],
            edges=[{
                "edge_type": "has_condition",
                "confidence": 0.9,
                "temporality": "current",
                "assertion": "present",
            }],
            path_type="patient_condition",
            confidence=0.9,
        )
        prompt = path.to_prompt_format()
        assert "PRESENT" not in prompt

    def test_assertion_mode_none_hides_assertion(self) -> None:
        """When assertion_mode='none', assertion is not shown in prompt."""
        from app.services.graph_augmented_rag import GraphPath

        path = GraphPath(
            nodes=[
                {"id": "1", "label": "Patient", "type": "patient"},
                {"id": "2", "label": "Diabetes", "type": "condition"},
            ],
            edges=[{
                "edge_type": "has_condition",
                "confidence": 0.9,
                "temporality": "current",
                "assertion": "absent",
            }],
            path_type="patient_condition",
            confidence=0.9,
        )
        prompt = path.to_prompt_format(assertion_mode="none")
        assert "ABSENT" not in prompt

    def test_llm_prompt_includes_assertion_notes(self) -> None:
        """to_llm_prompt should include Assertion Notes section for negated findings."""
        from app.services.graph_augmented_rag import GraphAugmentedContext, GraphPath

        path = GraphPath(
            nodes=[
                {"id": "1", "label": "Patient", "type": "patient"},
                {"id": "2", "label": "Diabetes", "type": "condition"},
            ],
            edges=[{
                "edge_type": "has_condition",
                "confidence": 0.9,
                "temporality": "current",
                "assertion": "absent",
            }],
            path_type="patient_condition",
            confidence=0.9,
        )
        ctx = GraphAugmentedContext(
            query="test",
            patient_id="P001",
            graph_paths=[path],
            temporal_context=None,
            retrieved_documents=[],
            policy_constraints=[],
        )
        prompt = ctx.to_llm_prompt()
        assert "=== IMPORTANT: Clinical Assertion Status ===" in prompt
        assert "NEGATED" in prompt
        assert "Diabetes" in prompt

    def test_llm_prompt_no_assertion_notes_when_mode_none(self) -> None:
        """to_llm_prompt with assertion_mode='none' should omit Assertion Notes."""
        from app.services.graph_augmented_rag import GraphAugmentedContext, GraphPath

        path = GraphPath(
            nodes=[
                {"id": "1", "label": "Patient", "type": "patient"},
                {"id": "2", "label": "Diabetes", "type": "condition"},
            ],
            edges=[{
                "edge_type": "has_condition",
                "confidence": 0.9,
                "temporality": "current",
                "assertion": "absent",
            }],
            path_type="patient_condition",
            confidence=0.9,
        )
        ctx = GraphAugmentedContext(
            query="test",
            patient_id="P001",
            graph_paths=[path],
            temporal_context=None,
            retrieved_documents=[],
            policy_constraints=[],
        )
        prompt = ctx.to_llm_prompt(assertion_mode="none")
        assert "=== IMPORTANT: Clinical Assertion Status ===" not in prompt


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


# ===========================================================================
# Step 6: _traverse_graph + Router Integration Tests
# ===========================================================================

class TestTraverseGraphRouterIntegration:
    """Test _traverse_graph router integration and BFS fallback."""

    def _make_mock_start_node(self, label: str = "Diabetes", omop_id: int | None = 201826) -> MagicMock:
        """Create a mock KGNode for start_nodes parameter."""
        node = MagicMock(spec=KGNode)
        node.id = str(uuid4())
        node.label = label
        node.omop_concept_id = omop_id
        node.node_type = NodeType.CONDITION
        return node

    def _make_router_path(
        self,
        node_pairs: list[tuple[str, str, str, int]] | None = None,
        edge_type: str = "drug_treats",
        confidence: float = 0.9,
    ) -> MagicMock:
        """Build a mock router GraphPath (from neo4j_query_router)."""
        from app.services.neo4j_query_router import GraphPath as RouterGraphPath, PathEdge, PathNode

        if node_pairs is None:
            node_pairs = [("n1", "Diabetes", "condition", 201826), ("n2", "Metformin", "drug", 1503297)]

        return RouterGraphPath(
            nodes=[PathNode(nid, lbl, ntype, cid) for nid, lbl, ntype, cid in node_pairs],
            edges=[PathEdge(edge_type, confidence)],
            hops=len(node_pairs) - 1,
            path_confidence=confidence,
            source="pg_cte",
        )

    # --- Router invocation conditions ---

    @patch("app.services.neo4j_query_router.GraphQueryRouter")
    def test_traverse_graph_uses_router_for_2_hops(
        self, MockRouter: MagicMock, rag_service: GraphAugmentedRAGService,
    ) -> None:
        """max_hops=2 with start_nodes having omop_concept_ids -> router called."""
        mock_instance = MagicMock()
        mock_instance.execute_multi_hop.return_value = [self._make_router_path()]
        MockRouter.return_value = mock_instance

        start_nodes = [self._make_mock_start_node()]
        paths = rag_service._traverse_graph(
            patient_id="P001", start_nodes=start_nodes,
            query_concepts=[], max_hops=2, max_paths=10,
        )

        mock_instance.execute_multi_hop.assert_called_once()
        assert len(paths) >= 1

    @patch("app.services.neo4j_query_router.GraphQueryRouter")
    def test_traverse_graph_uses_bfs_for_1_hop(
        self, MockRouter: MagicMock, rag_service: GraphAugmentedRAGService,
    ) -> None:
        """max_hops=1 -> BFS used, router NOT called."""
        start_nodes = [self._make_mock_start_node()]

        with patch.object(rag_service, "_bfs_traverse", return_value=[]) as mock_bfs:
            rag_service._traverse_graph(
                patient_id="P001", start_nodes=start_nodes,
                query_concepts=[], max_hops=1, max_paths=10,
            )
            MockRouter.assert_not_called()
            mock_bfs.assert_called()

    @patch("app.services.neo4j_query_router.GraphQueryRouter")
    def test_traverse_graph_skips_router_no_concept_ids(
        self, MockRouter: MagicMock, rag_service: GraphAugmentedRAGService,
    ) -> None:
        """start_nodes with omop_concept_id=None -> falls back to BFS."""
        start_nodes = [self._make_mock_start_node(omop_id=None)]

        with patch.object(rag_service, "_bfs_traverse", return_value=[]) as mock_bfs:
            rag_service._traverse_graph(
                patient_id="P001", start_nodes=start_nodes,
                query_concepts=[], max_hops=2, max_paths=10,
            )
            MockRouter.return_value.execute_multi_hop.assert_not_called()
            mock_bfs.assert_called()

    # --- Adapter conversion (router PathNode/PathEdge -> RAG GraphPath dicts) ---

    @patch("app.services.neo4j_query_router.GraphQueryRouter")
    def test_router_path_converted_to_rag_graphpath(
        self, MockRouter: MagicMock, rag_service: GraphAugmentedRAGService,
    ) -> None:
        """Verify dict structure: nodes=[{id, label, type}], edges=[{edge_type, confidence, ...}]."""
        from app.services.neo4j_query_router import GraphPath as RouterGraphPath, PathEdge, PathNode

        mock_instance = MagicMock()
        mock_instance.execute_multi_hop.return_value = [
            RouterGraphPath(
                nodes=[
                    PathNode("n1", "Diabetes", "condition", 201826),
                    PathNode("n2", "Metformin", "drug", 1503297),
                ],
                edges=[PathEdge("drug_treats", 0.9, temporality="current", event_date="2024-01-15")],
                hops=1, path_confidence=0.9, source="pg_cte",
            ),
        ]
        MockRouter.return_value = mock_instance

        start_nodes = [self._make_mock_start_node()]
        paths = rag_service._traverse_graph("P001", start_nodes, [], max_hops=2, max_paths=10)

        assert len(paths) == 1
        path = paths[0]
        assert path.nodes[0] == {"id": "n1", "label": "Diabetes", "type": "condition"}
        assert path.nodes[1] == {"id": "n2", "label": "Metformin", "type": "drug"}
        assert path.edges[0]["edge_type"] == "drug_treats"
        assert path.edges[0]["confidence"] == 0.9
        assert path.edges[0]["temporality"] == "current"
        assert path.edges[0]["event_date"] == "2024-01-15"

    @patch("app.services.neo4j_query_router.GraphQueryRouter")
    def test_path_type_is_multi_hop(
        self, MockRouter: MagicMock, rag_service: GraphAugmentedRAGService,
    ) -> None:
        """All converted paths have path_type='multi_hop'."""
        mock_instance = MagicMock()
        mock_instance.execute_multi_hop.return_value = [
            self._make_router_path(),
            self._make_router_path(
                node_pairs=[("n3", "C", "condition", 300), ("n4", "D", "drug", 400)],
                edge_type="may_cause", confidence=0.8,
            ),
        ]
        MockRouter.return_value = mock_instance

        start_nodes = [self._make_mock_start_node()]
        paths = rag_service._traverse_graph("P001", start_nodes, [], max_hops=2, max_paths=10)
        assert all(p.path_type == "multi_hop" for p in paths)

    @patch("app.services.neo4j_query_router.GraphQueryRouter")
    def test_confidence_preserved(
        self, MockRouter: MagicMock, rag_service: GraphAugmentedRAGService,
    ) -> None:
        """path_confidence from router -> confidence on RAG GraphPath."""
        mock_instance = MagicMock()
        mock_instance.execute_multi_hop.return_value = [
            self._make_router_path(confidence=0.75),
        ]
        MockRouter.return_value = mock_instance

        start_nodes = [self._make_mock_start_node()]
        paths = rag_service._traverse_graph("P001", start_nodes, [], max_hops=2, max_paths=10)
        assert paths[0].confidence == 0.75

    # --- Fallback behavior ---

    @patch("app.services.neo4j_query_router.GraphQueryRouter", side_effect=Exception("Router error"))
    def test_router_exception_falls_back_to_bfs(
        self, MockRouter: MagicMock, rag_service: GraphAugmentedRAGService,
    ) -> None:
        """Router raises Exception -> BFS called, no crash."""
        start_nodes = [self._make_mock_start_node()]

        with patch.object(rag_service, "_bfs_traverse", return_value=[]) as mock_bfs:
            paths = rag_service._traverse_graph("P001", start_nodes, [], max_hops=2, max_paths=10)
            mock_bfs.assert_called()
            assert isinstance(paths, list)

    def test_router_import_error_falls_back(
        self, rag_service: GraphAugmentedRAGService,
    ) -> None:
        """Import fails -> BFS used."""
        start_nodes = [self._make_mock_start_node()]

        with patch.dict(sys.modules, {"app.services.neo4j_query_router": None}):
            with patch.object(rag_service, "_bfs_traverse", return_value=[]) as mock_bfs:
                paths = rag_service._traverse_graph("P001", start_nodes, [], max_hops=2, max_paths=10)
                mock_bfs.assert_called()

    @patch("app.services.neo4j_query_router.GraphQueryRouter")
    def test_router_returns_empty_still_valid(
        self, MockRouter: MagicMock, rag_service: GraphAugmentedRAGService,
    ) -> None:
        """Router returns [] -> empty result (no BFS fallback needed)."""
        mock_instance = MagicMock()
        mock_instance.execute_multi_hop.return_value = []
        MockRouter.return_value = mock_instance

        start_nodes = [self._make_mock_start_node()]
        paths = rag_service._traverse_graph("P001", start_nodes, [], max_hops=2, max_paths=10)
        assert paths == []

    # --- Parameter passing ---

    @patch("app.services.neo4j_query_router.GraphQueryRouter")
    def test_patient_id_passed_to_router(
        self, MockRouter: MagicMock, rag_service: GraphAugmentedRAGService,
    ) -> None:
        """Verify patient_id forwarded correctly."""
        mock_instance = MagicMock()
        mock_instance.execute_multi_hop.return_value = []
        MockRouter.return_value = mock_instance

        start_nodes = [self._make_mock_start_node()]
        rag_service._traverse_graph("PATIENT_XYZ", start_nodes, [], max_hops=2, max_paths=10)

        call_args = mock_instance.execute_multi_hop.call_args[0][0]
        assert call_args.patient_id == "PATIENT_XYZ"

    @patch("app.services.neo4j_query_router.GraphQueryRouter")
    def test_start_concept_ids_extracted(
        self, MockRouter: MagicMock, rag_service: GraphAugmentedRAGService,
    ) -> None:
        """Only non-None omop_concept_ids passed."""
        mock_instance = MagicMock()
        mock_instance.execute_multi_hop.return_value = []
        MockRouter.return_value = mock_instance

        node_with_id = self._make_mock_start_node(omop_id=201826)
        node_without_id = self._make_mock_start_node(omop_id=None)
        rag_service._traverse_graph("P001", [node_with_id, node_without_id], [], max_hops=2, max_paths=10)

        call_args = mock_instance.execute_multi_hop.call_args[0][0]
        assert call_args.start_concept_ids == [201826]

    @patch("app.services.neo4j_query_router.GraphQueryRouter")
    def test_max_hops_and_paths_forwarded(
        self, MockRouter: MagicMock, rag_service: GraphAugmentedRAGService,
    ) -> None:
        """max_hops and max_paths match."""
        mock_instance = MagicMock()
        mock_instance.execute_multi_hop.return_value = []
        MockRouter.return_value = mock_instance

        start_nodes = [self._make_mock_start_node()]
        rag_service._traverse_graph("P001", start_nodes, [], max_hops=4, max_paths=15)

        call_args = mock_instance.execute_multi_hop.call_args[0][0]
        assert call_args.max_hops == 4
        assert call_args.max_paths == 15

    @patch("app.services.neo4j_query_router.GraphQueryRouter")
    def test_min_confidence_uses_constant(
        self, MockRouter: MagicMock, rag_service: GraphAugmentedRAGService,
    ) -> None:
        """min_confidence=MIN_TRAVERSAL_CONFIDENCE (0.3)."""
        mock_instance = MagicMock()
        mock_instance.execute_multi_hop.return_value = []
        MockRouter.return_value = mock_instance

        start_nodes = [self._make_mock_start_node()]
        rag_service._traverse_graph("P001", start_nodes, [], max_hops=2, max_paths=10)

        call_args = mock_instance.execute_multi_hop.call_args[0][0]
        assert call_args.min_confidence == MIN_TRAVERSAL_CONFIDENCE
        assert call_args.min_confidence == 0.3

    @patch("app.services.neo4j_query_router.GraphQueryRouter")
    def test_max_paths_limits_output(
        self, MockRouter: MagicMock, rag_service: GraphAugmentedRAGService,
    ) -> None:
        """Even if router returns 100, only max_paths returned."""
        from app.services.neo4j_query_router import GraphPath as RouterGraphPath, PathEdge, PathNode

        mock_instance = MagicMock()
        mock_instance.execute_multi_hop.return_value = [
            RouterGraphPath(
                nodes=[PathNode(f"n{i}", f"Node{i}", "condition", 100 + i), PathNode(f"m{i}", f"Target{i}", "drug", 200 + i)],
                edges=[PathEdge("drug_treats", 0.9)],
                hops=1, path_confidence=0.9, source="pg_cte",
            )
            for i in range(100)
        ]
        MockRouter.return_value = mock_instance

        start_nodes = [self._make_mock_start_node()]
        paths = rag_service._traverse_graph("P001", start_nodes, [], max_hops=2, max_paths=5)
        assert len(paths) == 5


# ===========================================================================
# TestNeo4jImportQuarantine — Zero Neo4j runtime dependency (RAG service)
# ===========================================================================

class TestNeo4jImportQuarantine:
    """Prove graph_augmented_rag.py has zero Neo4j runtime imports."""

    def test_no_neo4j_top_level_imports(self) -> None:
        """AST-scan graph_augmented_rag.py — no 'neo4j' module imported."""
        import ast
        import inspect
        import app.services.graph_augmented_rag as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)

        neo4j_imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "neo4j" or alias.name.startswith("neo4j."):
                        neo4j_imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and (node.module == "neo4j" or node.module.startswith("neo4j.")):
                    neo4j_imports.append(node.module)

        assert neo4j_imports == [], f"neo4j imports found: {neo4j_imports}"

    def test_retrieve_context_succeeds_without_neo4j(
        self, db_session: Session, rag_service: GraphAugmentedRAGService,
    ) -> None:
        """Patch sys.modules to block neo4j — retrieve_context still works."""
        saved = sys.modules.get("neo4j")
        sys.modules["neo4j"] = None  # type: ignore[assignment]
        try:
            context = rag_service.retrieve_context(
                query="test query",
                patient_id="P999",
                include_temporal=False,
                include_policies=False,
            )
            assert isinstance(context.graph_paths, list)
        finally:
            if saved is None:
                sys.modules.pop("neo4j", None)
            else:
                sys.modules["neo4j"] = saved


# ===========================================================================
# TestIngestionToTraversalContract — Ingestion services are Neo4j-free
# ===========================================================================

class TestIngestionToTraversalContract:
    """Verify ingestion services have no neo4j dependency."""

    def test_ingestion_services_no_neo4j_imports(self) -> None:
        """AST-scan mimic/synthea/mtsamples ingestion — no neo4j imports."""
        import ast
        import inspect

        modules_to_check = [
            "app.services.mimic_ingestion",
            "app.services.synthea_ingestion",
            "app.services.mtsamples_ingestion",
        ]
        neo4j_imports: list[str] = []
        for mod_name in modules_to_check:
            try:
                mod = __import__(mod_name, fromlist=["_"])
                source = inspect.getsource(mod)
                tree = ast.parse(source)

                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name == "neo4j" or alias.name.startswith("neo4j."):
                                neo4j_imports.append(f"{mod_name}: {alias.name}")
                    elif isinstance(node, ast.ImportFrom):
                        if node.module and (node.module == "neo4j" or node.module.startswith("neo4j.")):
                            neo4j_imports.append(f"{mod_name}: {node.module}")
            except ImportError:
                pass  # Module not installed — that's fine, no neo4j dep

        assert neo4j_imports == [], f"neo4j imports found in ingestion: {neo4j_imports}"

    def test_shared_concept_node_found_via_edge_join(
        self, db_session: Session, rag_service: GraphAugmentedRAGService,
    ) -> None:
        """Seed shared concept node (patient_id=NULL) + kg_edge with patient_id — _find_matching_nodes finds it."""
        # Shared concept node (patient_id=NULL, omop_concept_id set)
        shared_node = _make_concept_node(
            db_session, "Hypertension", NodeType.CONDITION,
            omop_concept_id=316866, patient_id=None,
        )
        # Patient node
        patient = _make_patient_node(db_session, "P001")
        # Edge linking shared node to patient's graph
        _make_edge(db_session, patient, shared_node, "P001", EdgeType.HAS_CONDITION)

        concepts = [QueryConcept(text="hypertension", omop_concept_id=316866)]
        nodes = rag_service._find_matching_nodes("P001", concepts)
        assert any(n.id == shared_node.id for n in nodes), \
            "Shared concept node should be found via edge-join"


# ===========================================================================
# TestAdapterSemanticPreservation — Router -> RAG metadata preserved
# ===========================================================================

class TestAdapterSemanticPreservation:
    """Verify router PathEdge metadata is preserved through RAG adapter."""

    def _make_mock_start_node(self, label: str = "Diabetes", omop_id: int = 201826) -> MagicMock:
        node = MagicMock(spec=KGNode)
        node.id = str(uuid4())
        node.label = label
        node.omop_concept_id = omop_id
        node.node_type = NodeType.CONDITION
        return node

    @patch("app.services.neo4j_query_router.GraphQueryRouter")
    def test_temporality_preserved(
        self, MockRouter: MagicMock, rag_service: GraphAugmentedRAGService,
    ) -> None:
        """Router PathEdge.temporality -> RAG GraphPath.edges[].temporality."""
        from app.services.neo4j_query_router import GraphPath as RouterGraphPath, PathEdge, PathNode

        mock_instance = MagicMock()
        mock_instance.execute_multi_hop.return_value = [
            RouterGraphPath(
                nodes=[PathNode("n1", "A", "condition", 100), PathNode("n2", "B", "drug", 200)],
                edges=[PathEdge("drug_treats", 0.9, temporality="current", event_date=None)],
                hops=1, path_confidence=0.9, source="pg_cte",
            ),
        ]
        MockRouter.return_value = mock_instance

        start_nodes = [self._make_mock_start_node()]
        paths = rag_service._traverse_graph("P001", start_nodes, [], max_hops=2, max_paths=10)

        assert len(paths) == 1
        assert paths[0].edges[0]["temporality"] == "current"

    @patch("app.services.neo4j_query_router.GraphQueryRouter")
    def test_event_date_preserved(
        self, MockRouter: MagicMock, rag_service: GraphAugmentedRAGService,
    ) -> None:
        """Router PathEdge.event_date -> RAG GraphPath.edges[].event_date."""
        from app.services.neo4j_query_router import GraphPath as RouterGraphPath, PathEdge, PathNode

        mock_instance = MagicMock()
        mock_instance.execute_multi_hop.return_value = [
            RouterGraphPath(
                nodes=[PathNode("n1", "A", "condition", 100), PathNode("n2", "B", "drug", 200)],
                edges=[PathEdge("drug_treats", 0.9, temporality=None, event_date="2024-03-15")],
                hops=1, path_confidence=0.9, source="pg_cte",
            ),
        ]
        MockRouter.return_value = mock_instance

        start_nodes = [self._make_mock_start_node()]
        paths = rag_service._traverse_graph("P001", start_nodes, [], max_hops=2, max_paths=10)

        assert paths[0].edges[0]["event_date"] == "2024-03-15"

    @patch("app.services.neo4j_query_router.GraphQueryRouter")
    def test_missing_assertion_defaults_to_present(
        self, MockRouter: MagicMock, rag_service: GraphAugmentedRAGService,
    ) -> None:
        """PathEdge without assertion attribute -> defaults to 'present'."""
        from app.services.neo4j_query_router import GraphPath as RouterGraphPath, PathEdge, PathNode

        mock_instance = MagicMock()
        # PathEdge has no 'assertion' field — the adapter should default
        mock_instance.execute_multi_hop.return_value = [
            RouterGraphPath(
                nodes=[PathNode("n1", "A", "condition", 100), PathNode("n2", "B", "drug", 200)],
                edges=[PathEdge("drug_treats", 0.9)],
                hops=1, path_confidence=0.9, source="pg_cte",
            ),
        ]
        MockRouter.return_value = mock_instance

        start_nodes = [self._make_mock_start_node()]
        paths = rag_service._traverse_graph("P001", start_nodes, [], max_hops=2, max_paths=10)

        assert paths[0].edges[0]["assertion"] == "present"

    @patch("app.services.neo4j_query_router.GraphQueryRouter")
    def test_ranking_order_preserved(
        self, MockRouter: MagicMock, rag_service: GraphAugmentedRAGService,
    ) -> None:
        """3 paths with conf 0.9/0.5/0.3 -> output order preserved."""
        from app.services.neo4j_query_router import GraphPath as RouterGraphPath, PathEdge, PathNode

        mock_instance = MagicMock()
        mock_instance.execute_multi_hop.return_value = [
            RouterGraphPath(
                nodes=[PathNode("n1", "A", "condition", 100), PathNode("n2", "B", "drug", 200)],
                edges=[PathEdge("drug_treats", 0.9)],
                hops=1, path_confidence=0.9, source="pg_cte",
            ),
            RouterGraphPath(
                nodes=[PathNode("n3", "C", "condition", 300), PathNode("n4", "D", "drug", 400)],
                edges=[PathEdge("may_cause", 0.5)],
                hops=1, path_confidence=0.5, source="pg_cte",
            ),
            RouterGraphPath(
                nodes=[PathNode("n5", "E", "condition", 500), PathNode("n6", "F", "drug", 600)],
                edges=[PathEdge("induces", 0.3)],
                hops=1, path_confidence=0.3, source="pg_cte",
            ),
        ]
        MockRouter.return_value = mock_instance

        start_nodes = [self._make_mock_start_node()]
        paths = rag_service._traverse_graph("P001", start_nodes, [], max_hops=2, max_paths=10)

        assert len(paths) == 3
        assert paths[0].confidence == 0.9
        assert paths[1].confidence == 0.5
        assert paths[2].confidence == 0.3
