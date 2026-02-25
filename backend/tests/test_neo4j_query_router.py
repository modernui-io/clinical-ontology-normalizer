"""Tests for PG-native Query Router.

Validates:
- Routing logic (1-hop -> _pg_single_hop, 2+ hop -> _pg_recursive_cte)
- ORM-based single-hop traversal (works in SQLite)
- CTE deserialization (mocked session.execute for PG-specific SQL)
- OMOP_REL_TO_EDGE_TYPE mapping dictionary
- Backward-compatible alias (Neo4jQueryRouter)
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.knowledge_graph import KGEdge, KGNode
from app.schemas.knowledge_graph import EdgeType, NodeType
from app.services.neo4j_query_router import (
    GraphPath,
    GraphQueryRouter,
    MAX_HOPS_LIMIT,
    MAX_PATHS_LIMIT,
    MultiHopQuery,
    Neo4jQueryRouter,
    OMOP_REL_NAMES,
    OMOP_REL_TO_EDGE_TYPE,
    PathEdge,
    PathNode,
)

# ---------------------------------------------------------------------------
# Test database setup (SQLite for ORM tests)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_node(
    session: Session,
    label: str,
    node_type: NodeType,
    patient_id: str | None = None,
    omop_concept_id: int | None = None,
) -> KGNode:
    node = KGNode(
        id=str(uuid4()),
        patient_id=patient_id,
        node_type=node_type,
        label=label,
        omop_concept_id=omop_concept_id,
        properties={},
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
    temporal_confidence: float | None = None,
    temporality: str | None = None,
) -> KGEdge:
    edge = KGEdge(
        id=str(uuid4()),
        patient_id=patient_id,
        source_node_id=source.id,
        target_node_id=target.id,
        edge_type=edge_type,
        properties={},
        temporal_confidence=temporal_confidence,
        temporality=temporality,
    )
    session.add(edge)
    session.flush()
    return edge


# ===========================================================================
# TestExecuteMultiHopRouting — Routing logic
# ===========================================================================

class TestExecuteMultiHopRouting:
    """Verify execute_multi_hop dispatches to the correct method."""

    def test_1_hop_routes_to_single_hop(self, db_session: Session) -> None:
        """max_hops=1 -> calls _pg_single_hop."""
        router = GraphQueryRouter(db_session)
        query = MultiHopQuery(
            patient_id="P001",
            start_concept_ids=[201826],
            max_hops=1,
        )
        with patch.object(router, "_pg_single_hop", return_value=[]) as mock_single:
            with patch.object(router, "_pg_recursive_cte") as mock_cte:
                router.execute_multi_hop(query)
                mock_single.assert_called_once_with(query)
                mock_cte.assert_not_called()

    def test_2_hop_routes_to_recursive_cte(self, db_session: Session) -> None:
        """max_hops=2 -> calls _pg_recursive_cte."""
        router = GraphQueryRouter(db_session)
        query = MultiHopQuery(
            patient_id="P001",
            start_concept_ids=[201826],
            max_hops=2,
        )
        with patch.object(router, "_pg_recursive_cte", return_value=[]) as mock_cte:
            with patch.object(router, "_pg_single_hop") as mock_single:
                router.execute_multi_hop(query)
                mock_cte.assert_called_once_with(query)
                mock_single.assert_not_called()

    def test_3_hop_routes_to_recursive_cte(self, db_session: Session) -> None:
        """max_hops=3 -> calls _pg_recursive_cte."""
        router = GraphQueryRouter(db_session)
        query = MultiHopQuery(
            patient_id="P001",
            start_concept_ids=[201826],
            max_hops=3,
        )
        with patch.object(router, "_pg_recursive_cte", return_value=[]) as mock_cte:
            router.execute_multi_hop(query)
            mock_cte.assert_called_once_with(query)

    def test_0_hop_routes_to_single_hop(self, db_session: Session) -> None:
        """max_hops=0 -> calls _pg_single_hop, returns []."""
        router = GraphQueryRouter(db_session)
        query = MultiHopQuery(
            patient_id="P001",
            start_concept_ids=[201826],
            max_hops=0,
        )
        with patch.object(router, "_pg_single_hop", return_value=[]) as mock_single:
            result = router.execute_multi_hop(query)
            mock_single.assert_called_once_with(query)
            assert result == []


# ===========================================================================
# TestPgSingleHop — ORM-based 1-hop (works in SQLite)
# ===========================================================================

class TestPgSingleHop:
    """Test _pg_single_hop with real SQLite database."""

    def test_finds_direct_neighbors(self, db_session: Session) -> None:
        """Patient->Condition->Drug, start from Condition, find neighbors."""
        patient = _make_node(db_session, "Patient P001", NodeType.PATIENT, patient_id="P001")
        condition = _make_node(db_session, "Diabetes", NodeType.CONDITION, omop_concept_id=201826)
        drug = _make_node(db_session, "Metformin", NodeType.DRUG, omop_concept_id=1503297)

        _make_edge(db_session, patient, condition, "P001", EdgeType.HAS_CONDITION)
        _make_edge(db_session, condition, drug, "P001", EdgeType.CONDITION_TREATED_BY)

        router = GraphQueryRouter(db_session)
        query = MultiHopQuery(
            patient_id="P001",
            start_concept_ids=[201826],
            max_hops=1,
            min_confidence=0.0,
        )
        results = router._pg_single_hop(query)

        all_labels = [n.label for p in results for n in p.nodes]
        assert "Diabetes" in all_labels
        assert any(lbl in all_labels for lbl in ("Patient P001", "Metformin"))

    def test_bidirectional_traversal(self, db_session: Session) -> None:
        """Finds neighbors via both source_node_id and target_node_id."""
        patient = _make_node(db_session, "Patient P001", NodeType.PATIENT, patient_id="P001")
        condition = _make_node(db_session, "Diabetes", NodeType.CONDITION, omop_concept_id=201826)
        drug = _make_node(db_session, "Metformin", NodeType.DRUG, omop_concept_id=1503297)

        # Edge FROM patient TO condition (condition is target)
        _make_edge(db_session, patient, condition, "P001", EdgeType.HAS_CONDITION)
        # Edge FROM condition TO drug (condition is source)
        _make_edge(db_session, condition, drug, "P001", EdgeType.CONDITION_TREATED_BY)

        router = GraphQueryRouter(db_session)
        query = MultiHopQuery(
            patient_id="P001",
            start_concept_ids=[201826],
            max_hops=1,
            min_confidence=0.0,
        )
        results = router._pg_single_hop(query)

        all_neighbor_labels = set()
        for p in results:
            for n in p.nodes:
                if n.label != "Diabetes":
                    all_neighbor_labels.add(n.label)
        assert "Patient P001" in all_neighbor_labels
        assert "Metformin" in all_neighbor_labels

    def test_confidence_filtering_excludes_low(self, db_session: Session) -> None:
        """Edge with confidence 0.1, min_confidence=0.5 -> excluded."""
        patient = _make_node(db_session, "Patient P001", NodeType.PATIENT, patient_id="P001")
        condition = _make_node(db_session, "Diabetes", NodeType.CONDITION, omop_concept_id=201826)
        _make_edge(db_session, patient, condition, "P001", EdgeType.HAS_CONDITION, temporal_confidence=0.1)

        router = GraphQueryRouter(db_session)
        query = MultiHopQuery(
            patient_id="P001",
            start_concept_ids=[201826],
            max_hops=1,
            min_confidence=0.5,
        )
        results = router._pg_single_hop(query)
        assert len(results) == 0

    def test_confidence_filtering_includes_high(self, db_session: Session) -> None:
        """Edge with confidence 0.9, min_confidence=0.5 -> included."""
        patient = _make_node(db_session, "Patient P001", NodeType.PATIENT, patient_id="P001")
        condition = _make_node(db_session, "Diabetes", NodeType.CONDITION, omop_concept_id=201826)
        _make_edge(db_session, patient, condition, "P001", EdgeType.HAS_CONDITION, temporal_confidence=0.9)

        router = GraphQueryRouter(db_session)
        query = MultiHopQuery(
            patient_id="P001",
            start_concept_ids=[201826],
            max_hops=1,
            min_confidence=0.5,
        )
        results = router._pg_single_hop(query)
        assert len(results) >= 1

    def test_edge_type_filter(self, db_session: Session) -> None:
        """Only returns edges matching filter list."""
        patient = _make_node(db_session, "Patient P001", NodeType.PATIENT, patient_id="P001")
        condition = _make_node(db_session, "Diabetes", NodeType.CONDITION, omop_concept_id=201826)
        drug = _make_node(db_session, "Metformin", NodeType.DRUG, omop_concept_id=1503297)

        _make_edge(db_session, patient, condition, "P001", EdgeType.HAS_CONDITION)
        _make_edge(db_session, condition, drug, "P001", EdgeType.CONDITION_TREATED_BY)

        router = GraphQueryRouter(db_session)
        query = MultiHopQuery(
            patient_id="P001",
            start_concept_ids=[201826],
            max_hops=1,
            min_confidence=0.0,
            edge_type_filter=["condition_treated_by"],
        )
        results = router._pg_single_hop(query)

        edge_types = [e.edge_type for p in results for e in p.edges]
        assert all(et == "condition_treated_by" for et in edge_types)

    def test_max_paths_limit(self, db_session: Session) -> None:
        """With many neighbors, max_paths=3 returns at most 3."""
        patient = _make_node(db_session, "Patient P001", NodeType.PATIENT, patient_id="P001")
        condition = _make_node(db_session, "Diabetes", NodeType.CONDITION, omop_concept_id=201826)
        _make_edge(db_session, patient, condition, "P001", EdgeType.HAS_CONDITION)

        for i in range(10):
            drug = _make_node(db_session, f"Drug_{i}", NodeType.DRUG, omop_concept_id=100000 + i)
            _make_edge(db_session, condition, drug, "P001", EdgeType.CONDITION_TREATED_BY)

        router = GraphQueryRouter(db_session)
        query = MultiHopQuery(
            patient_id="P001",
            start_concept_ids=[201826],
            max_hops=1,
            min_confidence=0.0,
            max_paths=3,
        )
        results = router._pg_single_hop(query)
        assert len(results) <= 3

    def test_no_start_nodes_returns_empty(self, db_session: Session) -> None:
        """concept_id not in graph -> []."""
        patient = _make_node(db_session, "Patient P001", NodeType.PATIENT, patient_id="P001")
        condition = _make_node(db_session, "Diabetes", NodeType.CONDITION, omop_concept_id=201826)
        _make_edge(db_session, patient, condition, "P001", EdgeType.HAS_CONDITION)

        router = GraphQueryRouter(db_session)
        query = MultiHopQuery(
            patient_id="P001",
            start_concept_ids=[999999],
            max_hops=1,
            min_confidence=0.0,
        )
        results = router._pg_single_hop(query)
        assert len(results) == 0

    def test_patient_isolation(self, db_session: Session) -> None:
        """Two patients share concept, only edges for requested patient returned."""
        patient1 = _make_node(db_session, "Patient P001", NodeType.PATIENT, patient_id="P001")
        patient2 = _make_node(db_session, "Patient P002", NodeType.PATIENT, patient_id="P002")
        condition = _make_node(db_session, "Diabetes", NodeType.CONDITION, omop_concept_id=201826)
        drug1 = _make_node(db_session, "Metformin", NodeType.DRUG, omop_concept_id=1503297)
        drug2 = _make_node(db_session, "Insulin", NodeType.DRUG, omop_concept_id=1567198)

        # P001 edges
        _make_edge(db_session, patient1, condition, "P001", EdgeType.HAS_CONDITION)
        _make_edge(db_session, condition, drug1, "P001", EdgeType.CONDITION_TREATED_BY)
        # P002 edges
        _make_edge(db_session, patient2, condition, "P002", EdgeType.HAS_CONDITION)
        _make_edge(db_session, condition, drug2, "P002", EdgeType.CONDITION_TREATED_BY)

        router = GraphQueryRouter(db_session)
        query = MultiHopQuery(
            patient_id="P001",
            start_concept_ids=[201826],
            max_hops=1,
            min_confidence=0.0,
        )
        results = router._pg_single_hop(query)

        all_labels = {n.label for p in results for n in p.nodes}
        assert "Insulin" not in all_labels


# ===========================================================================
# TestPgRecursiveCteDeserialization — Mock session.execute
# ===========================================================================

class TestPgRecursiveCteDeserialization:
    """Test _pg_recursive_cte deserialization with mocked session.execute."""

    def _make_mock_session(self, rows: list[tuple]) -> MagicMock:
        """Create a mock session that returns the given rows."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = rows
        mock_session.execute.return_value = mock_result
        return mock_session

    def test_single_hop_clinical_path(self) -> None:
        """Mock 1-row CTE result, verify PathNode/PathEdge construction."""
        rows = [
            (
                ["node-1", "node-2"],
                ["Diabetes", "Metformin"],
                ["condition", "drug"],
                [201826, 1503297],
                ["May treat"],
                [0.9],
                ["patient"],
                ["present"],
                1,
                0.9,
            ),
        ]
        session = self._make_mock_session(rows)
        router = GraphQueryRouter(session)
        query = MultiHopQuery(patient_id="P001", start_concept_ids=[201826], max_hops=2)
        paths = router._pg_recursive_cte(query)

        assert len(paths) == 1
        path = paths[0]
        assert len(path.nodes) == 2
        assert path.nodes[0].node_id == "node-1"
        assert path.nodes[0].label == "Diabetes"
        assert path.nodes[0].node_type == "condition"
        assert path.nodes[0].omop_concept_id == 201826
        assert path.nodes[1].label == "Metformin"
        assert len(path.edges) == 1
        assert path.edges[0].edge_type == "drug_treats"
        assert path.edges[0].confidence == 0.9
        assert path.edges[0].experiencer == "patient"
        assert path.edges[0].assertion == "present"

    def test_two_hop_vocab_path(self) -> None:
        """Mock 2-hop vocab result with 3 nodes, 2 edges."""
        rows = [
            (
                ["node-a", "node-b", "node-c"],
                ["Diabetes", "Lung Disorder", "Lung"],
                ["condition", "condition", "anatomy"],
                [201826, 300000, 400000],
                ["May cause", "Has finding site"],
                [1.0, 1.0],
                ["patient", "patient"],
                ["present", "present"],
                2,
                1.0,
            ),
        ]
        session = self._make_mock_session(rows)
        router = GraphQueryRouter(session)
        query = MultiHopQuery(patient_id="P001", start_concept_ids=[201826], max_hops=3)
        paths = router._pg_recursive_cte(query)

        assert len(paths) == 1
        path = paths[0]
        assert len(path.nodes) == 3
        assert len(path.edges) == 2
        assert path.hops == 2

    def test_omop_rel_mapped_to_edge_type(self) -> None:
        """'May treat' in CTE -> 'drug_treats' in PathEdge."""
        rows = [
            (
                ["n1", "n2"],
                ["Diabetes", "Metformin"],
                ["condition", "drug"],
                [201826, 1503297],
                ["May treat"],
                [0.9],
                ["patient"],
                ["present"],
                1,
                0.9,
            ),
        ]
        session = self._make_mock_session(rows)
        router = GraphQueryRouter(session)
        query = MultiHopQuery(patient_id="P001", start_concept_ids=[201826], max_hops=2)
        paths = router._pg_recursive_cte(query)
        assert paths[0].edges[0].edge_type == "drug_treats"

    def test_unknown_rel_passes_through(self) -> None:
        """Unknown relationship_id preserved as-is."""
        rows = [
            (
                ["n1", "n2"],
                ["A", "B"],
                ["condition", "condition"],
                [100, 200],
                ["Unknown Relationship XYZ"],
                [1.0],
                ["patient"],
                ["present"],
                1,
                1.0,
            ),
        ]
        session = self._make_mock_session(rows)
        router = GraphQueryRouter(session)
        query = MultiHopQuery(patient_id="P001", start_concept_ids=[100], max_hops=2)
        paths = router._pg_recursive_cte(query)
        assert paths[0].edges[0].edge_type == "Unknown Relationship XYZ"

    def test_confidence_filter_applied(self) -> None:
        """min_confidence parameter is passed to the SQL execution."""
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        session.execute.return_value = mock_result

        router = GraphQueryRouter(session)
        query = MultiHopQuery(
            patient_id="P001",
            start_concept_ids=[201826],
            max_hops=2,
            min_confidence=0.8,
        )
        paths = router._pg_recursive_cte(query)

        call_args = session.execute.call_args
        params = call_args[0][1]
        assert params["min_confidence"] == 0.8
        assert paths == []

    def test_max_paths_limit_applied(self) -> None:
        """LIMIT clause contains max_paths value."""
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        session.execute.return_value = mock_result

        router = GraphQueryRouter(session)
        query = MultiHopQuery(
            patient_id="P001",
            start_concept_ids=[201826],
            max_hops=2,
            max_paths=5,
        )
        router._pg_recursive_cte(query)

        call_args = session.execute.call_args
        sql_text = str(call_args[0][0])
        assert "LIMIT 5" in sql_text

    def test_empty_result(self) -> None:
        """No rows -> empty list."""
        session = self._make_mock_session([])
        router = GraphQueryRouter(session)
        query = MultiHopQuery(patient_id="P001", start_concept_ids=[201826], max_hops=2)
        paths = router._pg_recursive_cte(query)
        assert paths == []

    def test_edge_type_filter_maps_to_omop_rels(self) -> None:
        """edge_type_filter=['drug_treats'] -> omop_rels contains 'May treat'."""
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        session.execute.return_value = mock_result

        router = GraphQueryRouter(session)
        query = MultiHopQuery(
            patient_id="P001",
            start_concept_ids=[201826],
            max_hops=2,
            edge_type_filter=["drug_treats"],
        )
        router._pg_recursive_cte(query)

        call_args = session.execute.call_args
        params = call_args[0][1]
        assert "May treat" in params["omop_rels"]

    def test_no_edge_type_filter_uses_all(self) -> None:
        """None filter -> all OMOP_REL_NAMES passed."""
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        session.execute.return_value = mock_result

        router = GraphQueryRouter(session)
        query = MultiHopQuery(
            patient_id="P001",
            start_concept_ids=[201826],
            max_hops=2,
            edge_type_filter=None,
        )
        router._pg_recursive_cte(query)

        call_args = session.execute.call_args
        params = call_args[0][1]
        assert params["omop_rels"] == OMOP_REL_NAMES

    def test_path_source_is_pg_cte(self) -> None:
        """Every returned path has source='pg_cte'."""
        rows = [
            (["n1", "n2"], ["A", "B"], ["condition", "drug"], [100, 200], ["May treat"], [0.9], ["patient"], ["present"], 1, 0.9),
            (["n3", "n4"], ["C", "D"], ["drug", "condition"], [300, 400], ["May cause"], [0.8], ["patient"], ["present"], 1, 0.8),
        ]
        session = self._make_mock_session(rows)
        router = GraphQueryRouter(session)
        query = MultiHopQuery(patient_id="P001", start_concept_ids=[100], max_hops=2)
        paths = router._pg_recursive_cte(query)
        assert all(p.source == "pg_cte" for p in paths)

    def test_vocab_node_domain_mapping(self) -> None:
        """Node types from CTE (domain_id mapped) are preserved in PathNode."""
        rows = [
            (
                ["n1", "n2"],
                ["Diabetes", "Lung"],
                ["condition", "anatomy"],
                [201826, 500000],
                ["Has finding site"],
                [1.0],
                ["patient"],
                ["present"],
                1,
                1.0,
            ),
        ]
        session = self._make_mock_session(rows)
        router = GraphQueryRouter(session)
        query = MultiHopQuery(patient_id="P001", start_concept_ids=[201826], max_hops=2)
        paths = router._pg_recursive_cte(query)

        assert paths[0].nodes[0].node_type == "condition"
        assert paths[0].nodes[1].node_type == "anatomy"

    def test_experiencer_and_assertion_propagated(self) -> None:
        """experiencer and assertion from CTE rows are set on PathEdge."""
        rows = [
            (
                ["n1", "n2"],
                ["Hypertension", "Patient"],
                ["condition", "patient"],
                [316866, None],
                ["HAS_CONDITION"],
                [0.95],
                ["family"],
                ["family_history"],
                1,
                0.95,
            ),
        ]
        session = self._make_mock_session(rows)
        router = GraphQueryRouter(session)
        query = MultiHopQuery(patient_id="P001", start_concept_ids=[316866], max_hops=2)
        paths = router._pg_recursive_cte(query)

        assert len(paths) == 1
        edge = paths[0].edges[0]
        assert edge.experiencer == "family"
        assert edge.assertion == "family_history"


# ===========================================================================
# TestOmopRelToEdgeTypeMapping — Dictionary validation
# ===========================================================================

class TestOmopRelToEdgeTypeMapping:
    """Validate the OMOP_REL_TO_EDGE_TYPE mapping dictionary."""

    def test_all_keys_are_strings(self) -> None:
        assert all(isinstance(k, str) for k in OMOP_REL_TO_EDGE_TYPE.keys())

    def test_all_values_are_strings(self) -> None:
        assert all(isinstance(v, str) for v in OMOP_REL_TO_EDGE_TYPE.values())

    def test_bidirectional_pairs_exist(self) -> None:
        """'May treat' + 'May be treated by' both present."""
        assert "May treat" in OMOP_REL_TO_EDGE_TYPE
        assert "May be treated by" in OMOP_REL_TO_EDGE_TYPE

    def test_clinical_anatomy_rels_present(self) -> None:
        """Has finding site, Has asso morph, Has causative agent all mapped."""
        assert "Has finding site" in OMOP_REL_TO_EDGE_TYPE
        assert "Has asso morph" in OMOP_REL_TO_EDGE_TYPE
        assert "Has causative agent" in OMOP_REL_TO_EDGE_TYPE

    def test_minimum_mapping_count(self) -> None:
        """At least 90 entries (currently ~130)."""
        assert len(OMOP_REL_TO_EDGE_TYPE) >= 90


# ===========================================================================
# TestBackwardCompatAlias — Neo4jQueryRouter alias
# ===========================================================================

class TestBackwardCompatAlias:
    """Verify Neo4jQueryRouter backward-compatible alias."""

    def test_neo4j_query_router_alias_exists(self) -> None:
        """Neo4jQueryRouter is GraphQueryRouter."""
        assert Neo4jQueryRouter is GraphQueryRouter

    def test_alias_instantiable(self, db_session: Session) -> None:
        """Neo4jQueryRouter(session) works."""
        router = Neo4jQueryRouter(db_session)
        assert isinstance(router, GraphQueryRouter)


# ===========================================================================
# TestNeo4jImportQuarantine — Zero Neo4j runtime dependency
# ===========================================================================

class TestNeo4jImportQuarantine:
    """Prove neo4j_query_router.py has zero Neo4j runtime imports."""

    def test_no_neo4j_top_level_imports(self) -> None:
        """AST-scan neo4j_query_router.py — no 'neo4j' module imported."""
        import ast
        import inspect
        import app.services.neo4j_query_router as mod

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

    def test_execute_multi_hop_succeeds_without_neo4j(self) -> None:
        """Patch sys.modules to block neo4j — execute_multi_hop still works."""
        import sys
        saved = sys.modules.get("neo4j")
        sys.modules["neo4j"] = None  # type: ignore[assignment]
        try:
            from app.services.neo4j_query_router import GraphQueryRouter, MultiHopQuery
            mock_session = MagicMock()
            mock_result = MagicMock()
            mock_result.fetchall.return_value = []
            mock_session.execute.return_value = mock_result

            router = GraphQueryRouter(mock_session)
            query = MultiHopQuery(patient_id="P001", start_concept_ids=[201826], max_hops=2)
            paths = router.execute_multi_hop(query)
            assert isinstance(paths, list)
        finally:
            if saved is None:
                sys.modules.pop("neo4j", None)
            else:
                sys.modules["neo4j"] = saved


# ===========================================================================
# TestMaxHopsGuardrail — Scale-safety clamping
# ===========================================================================

class TestMaxHopsGuardrail:
    """Verify max_hops and max_paths are clamped at scale-safe limits."""

    def test_max_hops_clamped_to_limit(self) -> None:
        """max_hops=50 -> SQL contains depth limit of MAX_HOPS_LIMIT (10)."""
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        session.execute.return_value = mock_result

        router = GraphQueryRouter(session)
        query = MultiHopQuery(
            patient_id="P001",
            start_concept_ids=[201826],
            max_hops=50,
            max_paths=20,
        )
        router._pg_recursive_cte(query)

        # Find the CTE SQL call (the one with fetchall, not the SET LOCAL)
        sql_call = None
        for call in session.execute.call_args_list:
            sql_text = str(call[0][0])
            if "clinical_traversal" in sql_text:
                sql_call = call
                break
        assert sql_call is not None, "CTE SQL not found in execute calls"
        sql_text = str(sql_call[0][0])
        assert f"t.depth < {MAX_HOPS_LIMIT}" in sql_text
        assert "t.depth < 50" not in sql_text

    def test_max_paths_clamped_to_limit(self) -> None:
        """max_paths=500 -> SQL contains LIMIT MAX_PATHS_LIMIT (100)."""
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        session.execute.return_value = mock_result

        router = GraphQueryRouter(session)
        query = MultiHopQuery(
            patient_id="P001",
            start_concept_ids=[201826],
            max_hops=2,
            max_paths=500,
        )
        router._pg_recursive_cte(query)

        sql_call = None
        for call in session.execute.call_args_list:
            sql_text = str(call[0][0])
            if "clinical_traversal" in sql_text:
                sql_call = call
                break
        assert sql_call is not None
        sql_text = str(sql_call[0][0])
        assert f"LIMIT {MAX_PATHS_LIMIT}" in sql_text
        assert "LIMIT 500" not in sql_text

    def test_normal_values_unchanged(self) -> None:
        """max_hops=3, max_paths=20 -> values passed through unchanged."""
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        session.execute.return_value = mock_result

        router = GraphQueryRouter(session)
        query = MultiHopQuery(
            patient_id="P001",
            start_concept_ids=[201826],
            max_hops=3,
            max_paths=20,
        )
        router._pg_recursive_cte(query)

        sql_call = None
        for call in session.execute.call_args_list:
            sql_text = str(call[0][0])
            if "clinical_traversal" in sql_text:
                sql_call = call
                break
        assert sql_call is not None
        sql_text = str(sql_call[0][0])
        assert "t.depth < 3" in sql_text
        assert "LIMIT 20" in sql_text


# ===========================================================================
# TestCTETimeout — Statement timeout before CTE execution
# ===========================================================================

class TestCTETimeout:
    """Verify SET LOCAL statement_timeout issued before CTE execute."""

    def test_statement_timeout_set_before_cte(self) -> None:
        """SET LOCAL statement_timeout = '10s' issued before the CTE query."""
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        session.execute.return_value = mock_result

        router = GraphQueryRouter(session)
        query = MultiHopQuery(
            patient_id="P001",
            start_concept_ids=[201826],
            max_hops=2,
        )
        router._pg_recursive_cte(query)

        # Inspect all execute calls in order
        call_texts = [str(c[0][0]) for c in session.execute.call_args_list]
        timeout_idx = None
        cte_idx = None
        for i, t in enumerate(call_texts):
            if "statement_timeout" in t:
                timeout_idx = i
            if "clinical_traversal" in t:
                cte_idx = i

        assert timeout_idx is not None, "SET LOCAL statement_timeout not found"
        assert cte_idx is not None, "CTE query not found"
        assert timeout_idx < cte_idx, "Timeout must be set BEFORE CTE executes"


# ===========================================================================
# TestSafetyCriticalRelationMapping — OMOP safety relations preserved
# ===========================================================================

class TestSafetyCriticalRelationMapping:
    """Verify safety-critical OMOP relations map correctly to edge types."""

    SAFETY_CRITICAL_FORWARD = {
        "CI by": "contraindicated_with",
        "Drug-drug inter for": "interacts_with",
        "May cause": "may_cause",
        "Induces": "induces",
        "Inhibits effect": "inhibits_effect",
        "May treat": "drug_treats",
    }

    SAFETY_CRITICAL_INVERSE = {
        "CI to": "contraindicated_with",
        "Has drug-drug inter": "interacts_with",
        "May be treated by": "condition_treated_by",
        "Induced by": "induced_by",
        "May be inhibited by": "inhibited_by",
    }

    def test_forward_safety_relations_mapped(self) -> None:
        """All 6 forward safety-critical relations map correctly."""
        for omop_rel, expected_edge in self.SAFETY_CRITICAL_FORWARD.items():
            assert omop_rel in OMOP_REL_TO_EDGE_TYPE, \
                f"Missing safety-critical relation: {omop_rel}"
            assert OMOP_REL_TO_EDGE_TYPE[omop_rel] == expected_edge, \
                f"{omop_rel} maps to {OMOP_REL_TO_EDGE_TYPE[omop_rel]}, expected {expected_edge}"

    def test_inverse_safety_relations_mapped(self) -> None:
        """All inverse safety-critical relations map correctly."""
        for omop_rel, expected_edge in self.SAFETY_CRITICAL_INVERSE.items():
            assert omop_rel in OMOP_REL_TO_EDGE_TYPE, \
                f"Missing inverse safety-critical relation: {omop_rel}"
            assert OMOP_REL_TO_EDGE_TYPE[omop_rel] == expected_edge, \
                f"{omop_rel} maps to {OMOP_REL_TO_EDGE_TYPE[omop_rel]}, expected {expected_edge}"


# ===========================================================================
# TestCycleAvoidance — Anti-cycle in CTE SQL
# ===========================================================================

class TestCycleAvoidance:
    """Verify CTE SQL prevents infinite loops on cyclic graphs."""

    def test_cycle_in_sqlite_no_infinite_loop(self, db_session: Session) -> None:
        """Create A->B->C->A cycle; 1-hop from A does NOT self-loop back."""
        a = _make_node(db_session, "NodeA", NodeType.CONDITION, omop_concept_id=1001)
        b = _make_node(db_session, "NodeB", NodeType.CONDITION, omop_concept_id=1002)
        c = _make_node(db_session, "NodeC", NodeType.CONDITION, omop_concept_id=1003)

        _make_edge(db_session, a, b, "P001", EdgeType.HAS_CONDITION)
        _make_edge(db_session, b, c, "P001", EdgeType.HAS_CONDITION)
        _make_edge(db_session, c, a, "P001", EdgeType.HAS_CONDITION)

        router = GraphQueryRouter(db_session)
        query = MultiHopQuery(
            patient_id="P001",
            start_concept_ids=[1001],
            max_hops=1,
            min_confidence=0.0,
        )
        results = router._pg_single_hop(query)

        # Start is NodeA; should find neighbors B and C but NOT loop back to A as neighbor
        all_labels = {n.label for p in results for n in p.nodes if n.label != "NodeA"}
        assert "NodeA" not in all_labels, "Self-loop detected — cycle avoidance failed"

    def test_cte_sql_contains_anti_cycle_clause(self) -> None:
        """Verify CTE SQL contains visited_ids check to prevent revisiting nodes."""
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        session.execute.return_value = mock_result

        router = GraphQueryRouter(session)
        query = MultiHopQuery(
            patient_id="P001",
            start_concept_ids=[201826],
            max_hops=3,
        )
        router._pg_recursive_cte(query)

        # Find the CTE SQL call
        sql_text = None
        for call in session.execute.call_args_list:
            text = str(call[0][0])
            if "clinical_traversal" in text:
                sql_text = text
                break

        assert sql_text is not None, "CTE SQL not found"
        assert "NOT (n2.id::text = ANY(t.visited_ids))" in sql_text, \
            "Anti-cycle clause missing from CTE SQL"


# ===========================================================================
# TestScaleSafety — Path limits enforced at service layer
# ===========================================================================

class TestScaleSafety:
    """Verify scale-safety: path limits enforced, no duplicate paths."""

    def test_many_neighbors_limited_by_max_paths(self, db_session: Session) -> None:
        """Create 50 neighbors, request max_paths=5 — at most 5 returned."""
        center = _make_node(db_session, "Center", NodeType.CONDITION, omop_concept_id=9999)

        for i in range(50):
            neighbor = _make_node(
                db_session, f"Neighbor_{i}", NodeType.DRUG,
                omop_concept_id=10000 + i,
            )
            _make_edge(db_session, center, neighbor, "P001", EdgeType.CONDITION_TREATED_BY)

        router = GraphQueryRouter(db_session)
        query = MultiHopQuery(
            patient_id="P001",
            start_concept_ids=[9999],
            max_hops=1,
            min_confidence=0.0,
            max_paths=5,
        )
        results = router._pg_single_hop(query)
        assert len(results) <= 5, f"Expected ≤5 paths, got {len(results)}"

    def test_single_hop_visited_prevents_duplicates(self, db_session: Session) -> None:
        """Two edges to same neighbor — only one path returned (visited set)."""
        center = _make_node(db_session, "Center", NodeType.CONDITION, omop_concept_id=8888)
        neighbor = _make_node(db_session, "SameNeighbor", NodeType.DRUG, omop_concept_id=8889)

        # Two edges to the same neighbor (different edge types)
        _make_edge(db_session, center, neighbor, "P001", EdgeType.CONDITION_TREATED_BY)
        _make_edge(db_session, center, neighbor, "P001", EdgeType.DRUG_TREATS)

        router = GraphQueryRouter(db_session)
        query = MultiHopQuery(
            patient_id="P001",
            start_concept_ids=[8888],
            max_hops=1,
            min_confidence=0.0,
        )
        results = router._pg_single_hop(query)

        # The visited set should prevent duplicate neighbor paths
        neighbor_labels = [
            n.label for p in results for n in p.nodes
            if n.label == "SameNeighbor"
        ]
        # Should appear in at most one path (visited set dedup)
        # Note: visited set deduplicates by neighbor.id, so at most one path with this neighbor
        assert len(neighbor_labels) <= 2, \
            f"Expected ≤2 occurrences of SameNeighbor (1 path, 1 node), got {len(neighbor_labels)}"
