"""Tests for Knowledge Graph Visualization Service."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.kg_visualization_service import (
    CATEGORY_COLORS,
    ClusterInfo,
    ClusteredGraph,
    KGVisualizationService,
    NodeCategory,
    ReasoningPathVis,
    TemporalAnimation,
    TemporalFrame,
    VisEdge,
    VisGraph,
    VisNode,
    VisualizationType,
    get_kg_visualization_service,
)


class TestVisNode:
    """Test VisNode dataclass."""

    def test_create_basic_node(self) -> None:
        """Test creating a basic visualization node."""
        node = VisNode(
            id="node_1",
            label="Diabetes Mellitus",
            category=NodeCategory.CONDITION,
        )
        assert node.id == "node_1"
        assert node.label == "Diabetes Mellitus"
        assert node.category == NodeCategory.CONDITION
        assert node.size == 1.0
        assert node.confidence == 1.0

    def test_create_node_with_position(self) -> None:
        """Test creating a node with position."""
        node = VisNode(
            id="node_2",
            label="Metformin",
            category=NodeCategory.DRUG,
            x=100.0,
            y=200.0,
            fixed=True,
        )
        assert node.x == 100.0
        assert node.y == 200.0
        assert node.fixed is True


class TestVisEdge:
    """Test VisEdge dataclass."""

    def test_create_basic_edge(self) -> None:
        """Test creating a basic visualization edge."""
        edge = VisEdge(
            id="edge_1",
            source="drug_1",
            target="condition_1",
            label="TREATS",
        )
        assert edge.source == "drug_1"
        assert edge.target == "condition_1"
        assert edge.label == "TREATS"
        assert edge.directed is True
        assert edge.weight == 1.0

    def test_create_styled_edge(self) -> None:
        """Test creating a styled edge."""
        edge = VisEdge(
            id="edge_2",
            source="a",
            target="b",
            label="RELATED",
            style="dashed",
            color="#FF0000",
            weight=0.5,
        )
        assert edge.style == "dashed"
        assert edge.color == "#FF0000"
        assert edge.weight == 0.5


class TestVisGraph:
    """Test VisGraph dataclass."""

    def test_create_graph(self) -> None:
        """Test creating a visualization graph."""
        nodes = [
            VisNode(id="n1", label="Node 1", category=NodeCategory.CONCEPT),
            VisNode(id="n2", label="Node 2", category=NodeCategory.CONCEPT),
        ]
        edges = [
            VisEdge(id="e1", source="n1", target="n2", label="RELATED"),
        ]

        graph = VisGraph(
            nodes=nodes,
            edges=edges,
            title="Test Graph",
            layout=VisualizationType.FORCE_DIRECTED,
        )
        assert len(graph.nodes) == 2
        assert len(graph.edges) == 1
        assert graph.title == "Test Graph"


class TestKGVisualizationService:
    """Test KGVisualizationService class."""

    def test_service_initialization(self) -> None:
        """Test service initializes correctly."""
        service = KGVisualizationService()
        assert service._layout_cache == {}

    def test_create_vis_node(self) -> None:
        """Test creating a visualization node."""
        service = KGVisualizationService()
        node = service.create_vis_node(
            node_id="test_1",
            label="Test Node",
            category=NodeCategory.CONDITION,
            confidence=0.9,
        )
        assert node.id == "test_1"
        assert node.label == "Test Node"
        assert node.category == NodeCategory.CONDITION
        assert node.color == CATEGORY_COLORS[NodeCategory.CONDITION]
        assert node.confidence == 0.9

    def test_create_vis_edge(self) -> None:
        """Test creating a visualization edge."""
        service = KGVisualizationService()
        edge = service.create_vis_edge(
            source="a",
            target="b",
            label="CONNECTS",
            weight=0.8,
        )
        assert edge.source == "a"
        assert edge.target == "b"
        assert edge.label == "CONNECTS"
        assert edge.weight == 0.8

    def test_build_patient_graph(self) -> None:
        """Test building a patient graph."""
        service = KGVisualizationService()

        conditions = [
            {"id": "cond_1", "name": "Type 2 Diabetes", "confidence": 0.95},
            {"id": "cond_2", "name": "Hypertension", "confidence": 0.9},
        ]
        medications = [
            {"id": "med_1", "name": "Metformin 500mg", "treats_conditions": ["cond_1"]},
            {"id": "med_2", "name": "Lisinopril 10mg", "treats_conditions": ["cond_2"]},
        ]

        graph = service.build_patient_graph(
            patient_id="P12345",
            conditions=conditions,
            medications=medications,
        )

        # Patient + 2 conditions + 2 medications
        assert len(graph.nodes) == 5
        # Patient->conditions (2) + Patient->meds (2) + meds->conditions (2)
        assert len(graph.edges) == 6
        assert graph.title == "Patient P12345 Clinical Graph"

    def test_build_patient_graph_with_all_resources(self) -> None:
        """Test building a patient graph with all resource types."""
        service = KGVisualizationService()

        conditions = [{"id": "c1", "name": "Diabetes"}]
        medications = [{"id": "m1", "name": "Metformin"}]
        procedures = [{"id": "p1", "name": "Blood glucose monitoring"}]
        labs = [{"id": "l1", "name": "HbA1c", "value": "7.2%"}]

        graph = service.build_patient_graph(
            patient_id="P001",
            conditions=conditions,
            medications=medications,
            procedures=procedures,
            labs=labs,
        )

        # Patient + condition + medication + procedure + lab
        assert len(graph.nodes) == 5
        # Verify all node categories are present
        categories = {n.category for n in graph.nodes}
        assert NodeCategory.PATIENT in categories
        assert NodeCategory.CONDITION in categories
        assert NodeCategory.DRUG in categories
        assert NodeCategory.PROCEDURE in categories
        assert NodeCategory.LAB in categories

    def test_build_reasoning_path_vis(self) -> None:
        """Test building reasoning path visualization."""
        service = KGVisualizationService()

        nodes = [
            {"id": "n1", "name": "Diabetes", "semantic_type": "T047"},
            {"id": "n2", "name": "Metformin", "semantic_type": "T121"},
        ]
        edges = [
            {"source": "n1", "target": "n2", "type": "MAY_TREAT"},
        ]

        path_vis = service.build_reasoning_path_vis(
            path_id="path_1",
            nodes=nodes,
            edges=edges,
            score=0.9,
            explanation="Metformin treats diabetes",
        )

        assert path_vis.path_id == "path_1"
        assert len(path_vis.nodes) == 2
        assert len(path_vis.edges) == 1
        assert path_vis.score == 0.9
        assert path_vis.hops == 1
        assert path_vis.start_node == "n1"
        assert path_vis.end_node == "n2"

    def test_infer_category_from_semantic_type(self) -> None:
        """Test category inference from semantic type."""
        service = KGVisualizationService()

        # Condition
        node_condition = {"semantic_type": "T047", "name": "Test"}
        assert service._infer_category(node_condition) == NodeCategory.CONDITION

        # Drug
        node_drug = {"semantic_type": "T121", "name": "Test"}
        assert service._infer_category(node_drug) == NodeCategory.DRUG

        # Procedure
        node_proc = {"semantic_type": "T061", "name": "Test"}
        assert service._infer_category(node_proc) == NodeCategory.PROCEDURE

        # Lab
        node_lab = {"semantic_type": "T034", "name": "Test"}
        assert service._infer_category(node_lab) == NodeCategory.LAB

    def test_infer_category_from_label(self) -> None:
        """Test category inference from label keywords."""
        service = KGVisualizationService()

        node_disease = {"name": "Heart disease"}
        assert service._infer_category(node_disease) == NodeCategory.CONDITION

        node_drug = {"name": "Aspirin 100mg"}
        assert service._infer_category(node_drug) == NodeCategory.DRUG

        node_proc = {"name": "Cardiac surgery"}
        assert service._infer_category(node_proc) == NodeCategory.PROCEDURE

    def test_build_temporal_animation(self) -> None:
        """Test building temporal animation."""
        service = KGVisualizationService()

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 6, 1, tzinfo=timezone.utc)

        nodes = [
            {"id": "n1", "name": "Condition A", "valid_from": start},
            {"id": "n2", "name": "Condition B", "valid_from": start + timedelta(days=60)},
        ]
        edges = [
            {"source": "n1", "target": "n2", "type": "RELATED"},
        ]

        animation = service.build_temporal_animation(
            nodes=nodes,
            edges=edges,
            start_time=start,
            end_time=end,
            frame_interval_days=30,
        )

        assert len(animation.frames) > 0
        assert animation.start_time == start
        assert animation.end_time == end
        assert animation.frame_duration_ms == 1000

        # First frame should have only n1
        first_frame = animation.frames[0]
        assert any(n.id == "n1" for n in first_frame.nodes)

    def test_build_semantic_clusters(self) -> None:
        """Test building semantic clusters."""
        service = KGVisualizationService()

        nodes = [
            {"id": "c1", "name": "Diabetes", "semantic_type": "T047"},
            {"id": "c2", "name": "Hypertension", "semantic_type": "T047"},
            {"id": "d1", "name": "Metformin", "semantic_type": "T121"},
            {"id": "d2", "name": "Lisinopril", "semantic_type": "T121"},
        ]
        edges = [
            {"source": "d1", "target": "c1", "type": "TREATS"},
            {"source": "d2", "target": "c2", "type": "TREATS"},
        ]

        clustered = service.build_semantic_clusters(nodes, edges)

        assert len(clustered.graph.nodes) == 4
        assert len(clustered.clusters) == 2  # conditions and drugs

        # Verify cluster assignments
        condition_cluster = next(
            (c for c in clustered.clusters if c.semantic_group == "condition"), None
        )
        drug_cluster = next(
            (c for c in clustered.clusters if c.semantic_group == "drug"), None
        )

        assert condition_cluster is not None
        assert len(condition_cluster.node_ids) == 2

        assert drug_cluster is not None
        assert len(drug_cluster.node_ids) == 2

    def test_to_d3_format(self) -> None:
        """Test D3.js format conversion."""
        service = KGVisualizationService()

        graph = VisGraph(
            nodes=[
                VisNode(id="n1", label="Node 1", category=NodeCategory.CONCEPT),
            ],
            edges=[],
        )

        d3_data = service.to_d3_format(graph)

        assert "nodes" in d3_data
        assert "links" in d3_data
        assert len(d3_data["nodes"]) == 1
        assert d3_data["nodes"][0]["id"] == "n1"

    def test_to_cytoscape_format(self) -> None:
        """Test Cytoscape.js format conversion."""
        service = KGVisualizationService()

        graph = VisGraph(
            nodes=[
                VisNode(id="n1", label="Node 1", category=NodeCategory.CONCEPT, x=100, y=200),
            ],
            edges=[
                VisEdge(id="e1", source="n1", target="n1", label="SELF"),
            ],
        )

        cyto_data = service.to_cytoscape_format(graph)

        assert "elements" in cyto_data
        assert len(cyto_data["elements"]) == 2  # 1 node + 1 edge

        node_element = cyto_data["elements"][0]
        assert node_element["data"]["id"] == "n1"
        assert node_element["position"]["x"] == 100

    def test_to_vis_network_format(self) -> None:
        """Test vis.js Network format conversion."""
        service = KGVisualizationService()

        graph = VisGraph(
            nodes=[
                VisNode(
                    id="n1", label="Node 1", category=NodeCategory.CONCEPT,
                    confidence=0.85
                ),
            ],
            edges=[
                VisEdge(id="e1", source="n1", target="n1", label="SELF", directed=True),
            ],
        )

        vis_data = service.to_vis_network_format(graph)

        assert "nodes" in vis_data
        assert "edges" in vis_data

        node = vis_data["nodes"][0]
        assert node["id"] == "n1"
        assert "Confidence: 0.85" in node["title"]

        edge = vis_data["edges"][0]
        assert edge["from"] == "n1"
        assert edge["arrows"] == "to"


class TestCategoryColors:
    """Test category color mappings."""

    def test_all_categories_have_colors(self) -> None:
        """Test that all node categories have assigned colors."""
        for category in NodeCategory:
            assert category in CATEGORY_COLORS
            assert CATEGORY_COLORS[category].startswith("#")


class TestSingletonPattern:
    """Test singleton visualization service pattern."""

    def test_get_singleton_instance(self) -> None:
        """Test getting singleton service instance."""
        service1 = get_kg_visualization_service()
        service2 = get_kg_visualization_service()
        assert service1 is service2


class TestNodeSizeCalculation:
    """Test node size calculations."""

    def test_patient_nodes_are_largest(self) -> None:
        """Test that patient nodes are the largest."""
        service = KGVisualizationService()

        patient_size = service._calculate_node_size(NodeCategory.PATIENT, 1.0)
        condition_size = service._calculate_node_size(NodeCategory.CONDITION, 1.0)

        assert patient_size > condition_size

    def test_confidence_affects_size(self) -> None:
        """Test that lower confidence reduces node size."""
        service = KGVisualizationService()

        high_conf_size = service._calculate_node_size(NodeCategory.CONCEPT, 1.0)
        low_conf_size = service._calculate_node_size(NodeCategory.CONCEPT, 0.5)

        assert high_conf_size > low_conf_size


class TestTemporalAnimation:
    """Test temporal animation features."""

    def test_animation_frame_structure(self) -> None:
        """Test temporal frame structure."""
        frame = TemporalFrame(
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            nodes=[],
            edges=[],
            changes={"added": ["n1"], "removed": []},
        )

        assert frame.timestamp.year == 2024
        assert "added" in frame.changes

    def test_animation_structure(self) -> None:
        """Test temporal animation structure."""
        frames = [
            TemporalFrame(
                timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
                nodes=[],
                edges=[],
            ),
        ]

        animation = TemporalAnimation(
            frames=frames,
            start_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_time=datetime(2024, 12, 31, tzinfo=timezone.utc),
            frame_duration_ms=500,
        )

        assert len(animation.frames) == 1
        assert animation.frame_duration_ms == 500
