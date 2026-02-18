"""Tests for Neo4j Query Router (Phase 2).

Validates routing logic:
- 1-hop always uses PG
- 2+ hop routes to Neo4j when available
- Neo4j unavailable falls back to PG
- Neo4j failure falls back to PG
- Confidence filtering works
"""

from unittest.mock import MagicMock, PropertyMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.knowledge_graph import KGEdge, KGNode
from app.schemas.knowledge_graph import EdgeType, NodeType
from app.services.neo4j_query_router import (
    GraphPath,
    MultiHopQuery,
    Neo4jQueryRouter,
    PathEdge,
    PathNode,
)

# In-memory SQLite test engine
_test_engine = create_engine("sqlite:///:memory:", echo=False, future=True)
_TestSession = sessionmaker(bind=_test_engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="function")
def db_session() -> Session:
    """Create a database session with KG tables."""
    KGNode.__table__.create(bind=_test_engine, checkfirst=True)
    KGEdge.__table__.create(bind=_test_engine, checkfirst=True)

    session = _TestSession()
    try:
        yield session
    finally:
        session.close()
        KGEdge.__table__.drop(bind=_test_engine, checkfirst=True)
        KGNode.__table__.drop(bind=_test_engine, checkfirst=True)


class TestQueryRouting:
    """Tests for query routing logic."""

    def test_1_hop_always_uses_pg(self, db_session: Session) -> None:
        """1-hop queries should always use PG, even if Neo4j is available."""
        router = Neo4jQueryRouter(db_session)

        query = MultiHopQuery(
            patient_id="P001",
            start_concept_ids=[201826],
            max_hops=1,
        )

        with patch.object(router, "_pg_bfs", return_value=[]) as mock_pg:
            with patch.object(router, "_neo4j_multi_hop") as mock_neo4j:
                # Even with Neo4j available, 1-hop should use PG
                type(router).neo4j_available = PropertyMock(return_value=True)
                router.execute_multi_hop(query)

                mock_pg.assert_called_once()
                mock_neo4j.assert_not_called()

    def test_2_hop_routes_to_neo4j(self, db_session: Session) -> None:
        """2+ hop queries should route to Neo4j when available."""
        router = Neo4jQueryRouter(db_session)

        query = MultiHopQuery(
            patient_id="P001",
            start_concept_ids=[201826],
            max_hops=3,
        )

        mock_paths = [
            GraphPath(
                nodes=[
                    PathNode("n1", "Diabetes", "condition", 201826),
                    PathNode("n2", "Metformin", "drug", 1503297),
                ],
                edges=[PathEdge("drug_treats", 0.9)],
                hops=1,
                path_confidence=0.9,
                source="neo4j",
            )
        ]

        with patch.object(router, "_neo4j_multi_hop", return_value=mock_paths) as mock_neo4j:
            with patch.object(router, "_pg_bfs") as mock_pg:
                type(router).neo4j_available = PropertyMock(return_value=True)
                result = router.execute_multi_hop(query)

                mock_neo4j.assert_called_once()
                mock_pg.assert_not_called()
                assert len(result) == 1
                assert result[0].source == "neo4j"

    def test_neo4j_unavailable_falls_back(self, db_session: Session) -> None:
        """When Neo4j unavailable, 2+ hop queries fall back to PG BFS."""
        router = Neo4jQueryRouter(db_session)

        query = MultiHopQuery(
            patient_id="P001",
            start_concept_ids=[201826],
            max_hops=3,
        )

        with patch.object(router, "_pg_bfs", return_value=[]) as mock_pg:
            type(router).neo4j_available = PropertyMock(return_value=False)
            router.execute_multi_hop(query)

            mock_pg.assert_called_once()

    def test_neo4j_failure_falls_back(self, db_session: Session) -> None:
        """When Neo4j query fails, fall back to PG BFS."""
        router = Neo4jQueryRouter(db_session)

        query = MultiHopQuery(
            patient_id="P001",
            start_concept_ids=[201826],
            max_hops=3,
        )

        with patch.object(
            router, "_neo4j_multi_hop", side_effect=Exception("Neo4j timeout")
        ):
            with patch.object(router, "_pg_bfs", return_value=[]) as mock_pg:
                type(router).neo4j_available = PropertyMock(return_value=True)
                router.execute_multi_hop(query)

                mock_pg.assert_called_once()

    def test_confidence_filtering(self, db_session: Session) -> None:
        """Paths below min_confidence should be excluded."""
        router = Neo4jQueryRouter(db_session)

        # Seed a simple graph: Patient -> Condition with low confidence
        patient_node = KGNode(
            patient_id="P001",
            node_type=NodeType.PATIENT,
            label="Patient P001",
            properties={},
        )
        condition_node = KGNode(
            patient_id=None,
            node_type=NodeType.CONDITION,
            label="Diabetes",
            omop_concept_id=201826,
            properties={},
        )
        db_session.add_all([patient_node, condition_node])
        db_session.flush()

        edge = KGEdge(
            patient_id="P001",
            source_node_id=str(patient_node.id),
            target_node_id=str(condition_node.id),
            edge_type=EdgeType.HAS_CONDITION,
            properties={},
            temporal_confidence=0.1,  # Below typical threshold
        )
        db_session.add(edge)
        db_session.flush()

        query = MultiHopQuery(
            patient_id="P001",
            start_concept_ids=[201826],
            max_hops=1,
            min_confidence=0.5,  # Higher than edge confidence
        )

        type(router).neo4j_available = PropertyMock(return_value=False)
        results = router.execute_multi_hop(query)

        # Low-confidence edge should be filtered out
        assert len(results) == 0


class TestPgBfs:
    """Tests for PostgreSQL BFS traversal."""

    def test_pg_bfs_finds_1_hop_paths(self, db_session: Session) -> None:
        """PG BFS should find direct neighbors."""
        router = Neo4jQueryRouter(db_session)

        patient_node = KGNode(
            patient_id="P001",
            node_type=NodeType.PATIENT,
            label="Patient P001",
            properties={},
        )
        condition_node = KGNode(
            patient_id=None,
            node_type=NodeType.CONDITION,
            label="Diabetes",
            omop_concept_id=201826,
            properties={},
        )
        drug_node = KGNode(
            patient_id=None,
            node_type=NodeType.DRUG,
            label="Metformin",
            omop_concept_id=1503297,
            properties={},
        )
        db_session.add_all([patient_node, condition_node, drug_node])
        db_session.flush()

        # Patient -> Condition, Patient -> Drug
        db_session.add(KGEdge(
            patient_id="P001",
            source_node_id=str(patient_node.id),
            target_node_id=str(condition_node.id),
            edge_type=EdgeType.HAS_CONDITION,
            properties={},
        ))
        db_session.add(KGEdge(
            patient_id="P001",
            source_node_id=str(patient_node.id),
            target_node_id=str(drug_node.id),
            edge_type=EdgeType.TAKES_DRUG,
            properties={},
        ))
        db_session.flush()

        query = MultiHopQuery(
            patient_id="P001",
            start_concept_ids=[201826],
            max_hops=1,
            min_confidence=0.0,
        )

        type(router).neo4j_available = PropertyMock(return_value=False)
        results = router.execute_multi_hop(query)

        # Should find at least the patient→condition path
        assert len(results) >= 1
        assert all(r.source == "pg" for r in results)
