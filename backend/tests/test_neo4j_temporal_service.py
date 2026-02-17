"""Tests for Neo4j Temporal Knowledge Graph Service."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

try:
    from app.services.neo4j_temporal_service import (
        Neo4jTemporalService,
        SemanticGroup,
        SEMANTIC_TYPE_TO_GROUP,
        TemporalNode,
        TemporalEdge,
        ReasoningPath,
        TemporalQuery,
    )
except ImportError:
    pytest.skip("neo4j driver not installed", allow_module_level=True)


class TestSemanticGroups:
    """Test UMLS semantic group mappings."""

    def test_disorders_mapping(self) -> None:
        """Test disorder semantic types map correctly."""
        assert SEMANTIC_TYPE_TO_GROUP["T047"] == SemanticGroup.DISO
        assert SEMANTIC_TYPE_TO_GROUP["T048"] == SemanticGroup.DISO
        assert SEMANTIC_TYPE_TO_GROUP["T191"] == SemanticGroup.DISO

    def test_chemicals_mapping(self) -> None:
        """Test chemical/drug semantic types map correctly."""
        assert SEMANTIC_TYPE_TO_GROUP["T121"] == SemanticGroup.CHEM
        assert SEMANTIC_TYPE_TO_GROUP["T200"] == SemanticGroup.CHEM
        assert SEMANTIC_TYPE_TO_GROUP["T103"] == SemanticGroup.CHEM

    def test_procedures_mapping(self) -> None:
        """Test procedure semantic types map correctly."""
        assert SEMANTIC_TYPE_TO_GROUP["T059"] == SemanticGroup.PROC
        assert SEMANTIC_TYPE_TO_GROUP["T060"] == SemanticGroup.PROC
        assert SEMANTIC_TYPE_TO_GROUP["T061"] == SemanticGroup.PROC

    def test_anatomy_mapping(self) -> None:
        """Test anatomy semantic types map correctly."""
        assert SEMANTIC_TYPE_TO_GROUP["T023"] == SemanticGroup.ANAT
        assert SEMANTIC_TYPE_TO_GROUP["T029"] == SemanticGroup.ANAT

    def test_physiology_mapping(self) -> None:
        """Test physiology semantic types map correctly."""
        assert SEMANTIC_TYPE_TO_GROUP["T033"] == SemanticGroup.PHYS
        assert SEMANTIC_TYPE_TO_GROUP["T034"] == SemanticGroup.PHYS

    def test_semantic_group_values(self) -> None:
        """Test semantic group enum values."""
        assert SemanticGroup.DISO.value == "Disorders"
        assert SemanticGroup.CHEM.value == "Chemicals & Drugs"
        assert SemanticGroup.PROC.value == "Procedures"
        assert SemanticGroup.ANAT.value == "Anatomy"


class TestTemporalNode:
    """Test TemporalNode dataclass."""

    def test_create_basic_node(self) -> None:
        """Test creating a basic temporal node."""
        node = TemporalNode(
            id="node_1",
            label="Concept",
            cui="C0001234",
        )
        assert node.id == "node_1"
        assert node.label == "Concept"
        assert node.cui == "C0001234"
        assert node.valid_from is None
        assert node.valid_to is None

    def test_create_node_with_temporal_fields(self) -> None:
        """Test creating a node with temporal fields."""
        valid_from = datetime(2024, 1, 1, tzinfo=timezone.utc)
        valid_to = datetime(2024, 12, 31, tzinfo=timezone.utc)

        node = TemporalNode(
            id="node_2",
            label="ClinicalFact",
            cui="C0005678",
            valid_from=valid_from,
            valid_to=valid_to,
        )
        assert node.valid_from == valid_from
        assert node.valid_to == valid_to

    def test_create_node_with_semantic_type(self) -> None:
        """Test creating a node with semantic type."""
        node = TemporalNode(
            id="node_3",
            label="Concept",
            cui="C0011849",
            semantic_type="T047",
            semantic_group=SemanticGroup.DISO,
        )
        assert node.semantic_type == "T047"
        assert node.semantic_group == SemanticGroup.DISO


class TestTemporalEdge:
    """Test TemporalEdge dataclass."""

    def test_create_basic_edge(self) -> None:
        """Test creating a basic temporal edge."""
        edge = TemporalEdge(
            source_id="node_1",
            target_id="node_2",
            relationship_type="TREATS",
        )
        assert edge.source_id == "node_1"
        assert edge.target_id == "node_2"
        assert edge.relationship_type == "TREATS"
        assert edge.confidence == 1.0

    def test_create_edge_with_provenance(self) -> None:
        """Test creating an edge with provenance."""
        edge = TemporalEdge(
            source_id="drug_1",
            target_id="condition_1",
            relationship_type="MAY_TREAT",
            source_document="Note_12345",
            confidence=0.85,
        )
        assert edge.source_document == "Note_12345"
        assert edge.confidence == 0.85


class TestReasoningPath:
    """Test ReasoningPath dataclass."""

    def test_create_reasoning_path(self) -> None:
        """Test creating a reasoning path."""
        nodes = [
            TemporalNode(id="n1", label="Concept", cui="C001"),
            TemporalNode(id="n2", label="Concept", cui="C002"),
        ]
        edges = [
            TemporalEdge(source_id="n1", target_id="n2", relationship_type="RELATED"),
        ]

        path = ReasoningPath(
            nodes=nodes,
            edges=edges,
            score=0.9,
            hops=1,
        )
        assert len(path.nodes) == 2
        assert len(path.edges) == 1
        assert path.score == 0.9
        assert path.hops == 1


class TestTemporalQuery:
    """Test TemporalQuery dataclass."""

    def test_create_point_in_time_query(self) -> None:
        """Test creating a point-in-time query."""
        as_of = datetime(2024, 6, 15, tzinfo=timezone.utc)

        query = TemporalQuery(
            patient_id="P12345",
            as_of_time=as_of,
        )
        assert query.patient_id == "P12345"
        assert query.as_of_time == as_of
        assert query.max_hops == 3  # default

    def test_create_range_query(self) -> None:
        """Test creating a range query."""
        from_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        to_time = datetime(2024, 12, 31, tzinfo=timezone.utc)

        query = TemporalQuery(
            patient_id="P12345",
            from_time=from_time,
            to_time=to_time,
            max_hops=5,
        )
        assert query.from_time == from_time
        assert query.to_time == to_time
        assert query.max_hops == 5

    def test_create_query_with_semantic_filter(self) -> None:
        """Test creating a query with semantic filtering."""
        query = TemporalQuery(
            patient_id="P12345",
            semantic_groups=[SemanticGroup.DISO, SemanticGroup.CHEM],
            semantic_types=["T047", "T121"],
        )
        assert len(query.semantic_groups) == 2
        assert len(query.semantic_types) == 2


class TestNeo4jTemporalService:
    """Test Neo4jTemporalService class."""

    def test_service_initialization(self) -> None:
        """Test service initializes with correct defaults."""
        service = Neo4jTemporalService()
        assert service.uri == "bolt://localhost:7687"
        assert service.user == "neo4j"
        assert service.password == ""  # must be provided via settings/env
        assert service._driver is None

    def test_service_custom_config(self) -> None:
        """Test service with custom configuration."""
        service = Neo4jTemporalService(
            uri="bolt://custom:7688",
            user="admin",
            password="secret",
        )
        assert service.uri == "bolt://custom:7688"
        assert service.user == "admin"
        assert service.password == "secret"

    @pytest.mark.asyncio
    async def test_close_without_connection(self) -> None:
        """Test closing service without active connection."""
        service = Neo4jTemporalService()
        await service.close()  # Should not raise
        assert service._driver is None

    @pytest.mark.asyncio
    async def test_aggregate_evidence_empty(self) -> None:
        """Test evidence aggregation with empty paths."""
        service = Neo4jTemporalService()
        result = await service.aggregate_evidence([])
        assert result["evidence"] == []
        assert result["confidence"] == 0.0
        assert result["sources"] == []

    @pytest.mark.asyncio
    async def test_aggregate_evidence_with_paths(self) -> None:
        """Test evidence aggregation with multiple paths."""
        service = Neo4jTemporalService()

        # Create test paths
        nodes = [
            TemporalNode(id="n1", label="Concept", cui="C001", properties={"name": "Drug A"}),
            TemporalNode(id="n2", label="Concept", cui="C002", properties={"name": "Condition B"}),
        ]
        edges = [
            TemporalEdge(
                source_id="n1",
                target_id="n2",
                relationship_type="TREATS",
                source_document="Note_1",
            ),
        ]

        paths = [
            ReasoningPath(nodes=nodes, edges=edges, score=0.9, hops=1),
            ReasoningPath(nodes=nodes, edges=edges, score=0.8, hops=1),
        ]

        result = await service.aggregate_evidence(paths)
        assert result["total_paths"] == 2
        assert result["unique_conclusions"] == 1
        assert len(result["evidence"]) == 1
        assert result["evidence"][0]["supporting_paths"] == 2


class TestSchemaInitialization:
    """Test schema initialization queries."""

    @pytest.mark.asyncio
    async def test_initialize_schema_without_connection(self) -> None:
        """Test schema initialization logs warning when not connected."""
        service = Neo4jTemporalService()

        # Should not raise, just log warning
        await service.initialize_schema()
