"""Tests for CausalReasoningService integration with GraphAugmentedRAG (Phase 5).

Validates:
- Causal chains returned for causal queries
- No causal invocation for simple queries
- Causal service failure doesn't break RAG
"""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.document import Document
from app.models.knowledge_graph import KGEdge, KGNode
from app.schemas.knowledge_graph import EdgeType, NodeType
from app.services.graph_augmented_rag import (
    GraphAugmentedRAGService,
    _CAUSAL_PATTERNS,
)

# In-memory SQLite test engine
_test_engine = create_engine("sqlite:///:memory:", echo=False, future=True)
_TestSession = sessionmaker(bind=_test_engine, autocommit=False, autoflush=False)


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
    """Create a GraphAugmentedRAGService."""
    return GraphAugmentedRAGService(db_session)


class TestCausalPatternDetection:
    """Tests for causal language pattern detection."""

    def test_causal_pattern_matches_caused_by(self) -> None:
        assert _CAUSAL_PATTERNS.search("What is caused by diabetes?")

    def test_causal_pattern_matches_treatment_for(self) -> None:
        assert _CAUSAL_PATTERNS.search("What is the treatment for hypertension?")

    def test_causal_pattern_matches_side_effect(self) -> None:
        assert _CAUSAL_PATTERNS.search("What are the side effects of metformin?")

    def test_causal_pattern_matches_leads_to(self) -> None:
        assert _CAUSAL_PATTERNS.search("Diabetes leads to retinopathy")

    def test_causal_pattern_no_match_simple_query(self) -> None:
        assert not _CAUSAL_PATTERNS.search("What medications does this patient take?")

    def test_causal_pattern_no_match_general(self) -> None:
        assert not _CAUSAL_PATTERNS.search("Show patient vitals")


class TestCausalIntegration:
    """Tests for causal context integration in GraphAugmentedRAG."""

    @patch("app.services.graph_augmented_rag.GraphAugmentedRAGService._extract_query_concepts")
    def test_causal_chains_returned_for_causal_queries(
        self, mock_extract, rag_service: GraphAugmentedRAGService, db_session: Session
    ) -> None:
        """Causal queries should include causal chain paths in response."""
        from app.services.graph_augmented_rag import QueryConcept

        mock_extract.return_value = [
            QueryConcept(text="metformin", entity_type="medication"),
            QueryConcept(text="diabetes", entity_type="diagnosis"),
        ]

        # Seed a patient node so the graph traversal doesn't error
        patient_node = KGNode(
            patient_id="P001",
            node_type=NodeType.PATIENT,
            label="Patient P001",
            properties={},
        )
        db_session.add(patient_node)
        db_session.flush()

        context = rag_service.retrieve_context(
            query="What are the side effects of metformin for diabetes?",
            patient_id="P001",
            max_hops=1,
            include_temporal=False,
            include_policies=False,
        )

        # Should have causal paths in the result
        causal_paths = [p for p in context.graph_paths if p.path_type == "causal_chain"]
        assert len(causal_paths) > 0

    @patch("app.services.graph_augmented_rag.GraphAugmentedRAGService._extract_query_concepts")
    def test_no_causal_invocation_for_simple_queries(
        self, mock_extract, rag_service: GraphAugmentedRAGService, db_session: Session
    ) -> None:
        """Simple queries should not invoke causal reasoning."""
        from app.services.graph_augmented_rag import QueryConcept

        mock_extract.return_value = [
            QueryConcept(text="blood pressure", entity_type="vital_sign"),
        ]

        patient_node = KGNode(
            patient_id="P001",
            node_type=NodeType.PATIENT,
            label="Patient P001",
            properties={},
        )
        db_session.add(patient_node)
        db_session.flush()

        context = rag_service.retrieve_context(
            query="What is the patient's blood pressure?",
            patient_id="P001",
            max_hops=1,
            include_temporal=False,
            include_policies=False,
        )

        causal_paths = [p for p in context.graph_paths if p.path_type == "causal_chain"]
        assert len(causal_paths) == 0

    @patch("app.services.graph_augmented_rag.GraphAugmentedRAGService._extract_query_concepts")
    def test_causal_service_failure_doesnt_break_rag(
        self, mock_extract, rag_service: GraphAugmentedRAGService, db_session: Session
    ) -> None:
        """If causal service fails, RAG should still return other paths."""
        from app.services.graph_augmented_rag import QueryConcept

        mock_extract.return_value = [
            QueryConcept(text="metformin", entity_type="medication"),
        ]

        patient_node = KGNode(
            patient_id="P001",
            node_type=NodeType.PATIENT,
            label="Patient P001",
            properties={},
        )
        db_session.add(patient_node)
        db_session.flush()

        # Mock causal service to raise
        with patch(
            "app.services.causal_reasoning_service.get_causal_reasoning_service",
            side_effect=Exception("Causal service unavailable"),
        ):
            context = rag_service.retrieve_context(
                query="What is caused by metformin?",
                patient_id="P001",
                max_hops=1,
                include_temporal=False,
                include_policies=False,
            )

        # Should still return a valid context (no crash)
        assert context.patient_id == "P001"
        assert context.query == "What is caused by metformin?"
