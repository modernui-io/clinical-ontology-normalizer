"""
Knowledge Graph Visualization Service.

Provides data preparation for interactive knowledge graph visualizations:
- Force-directed graph layouts
- Hierarchical tree views
- Reasoning path visualizations
- Temporal evolution animations
- Semantic cluster views

Compatible with:
- D3.js force-directed graphs
- Cytoscape.js network visualization
- vis.js timeline and network
- Neo4j Bloom-style visualizations
"""

from __future__ import annotations

import logging
import math
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class VisualizationType(str, Enum):
    """Types of knowledge graph visualizations."""

    FORCE_DIRECTED = "force_directed"  # D3.js force layout
    HIERARCHICAL = "hierarchical"  # Tree/hierarchy view
    RADIAL = "radial"  # Radial tree
    TIMELINE = "timeline"  # Temporal view
    CLUSTER = "cluster"  # Semantic clustering
    PATH = "path"  # Reasoning path
    SANKEY = "sankey"  # Flow diagram


class NodeCategory(str, Enum):
    """Categories for node styling."""

    CONDITION = "condition"
    DRUG = "drug"
    PROCEDURE = "procedure"
    LAB = "lab"
    PATIENT = "patient"
    CONCEPT = "concept"
    INFERENCE = "inference"


# Color palettes for different categories
CATEGORY_COLORS = {
    NodeCategory.CONDITION: "#E74C3C",  # Red
    NodeCategory.DRUG: "#3498DB",  # Blue
    NodeCategory.PROCEDURE: "#2ECC71",  # Green
    NodeCategory.LAB: "#F39C12",  # Orange
    NodeCategory.PATIENT: "#9B59B6",  # Purple
    NodeCategory.CONCEPT: "#1ABC9C",  # Teal
    NodeCategory.INFERENCE: "#95A5A6",  # Gray
}


@dataclass
class VisNode:
    """Node for visualization."""

    id: str
    label: str
    category: NodeCategory
    group: str | None = None
    size: float = 1.0
    color: str | None = None
    x: float | None = None
    y: float | None = None
    fixed: bool = False
    properties: dict[str, Any] = field(default_factory=dict)
    # Temporal
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    # Provenance
    confidence: float = 1.0
    source: str | None = None


@dataclass
class VisEdge:
    """Edge for visualization."""

    id: str
    source: str
    target: str
    label: str
    weight: float = 1.0
    directed: bool = True
    color: str | None = None
    style: str = "solid"  # solid, dashed, dotted
    properties: dict[str, Any] = field(default_factory=dict)
    # Temporal
    valid_from: datetime | None = None
    valid_to: datetime | None = None


@dataclass
class VisGraph:
    """Complete graph for visualization."""

    nodes: list[VisNode]
    edges: list[VisEdge]
    layout: VisualizationType = VisualizationType.FORCE_DIRECTED
    title: str = ""
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReasoningPathVis:
    """Visualization for a reasoning path."""

    path_id: str
    nodes: list[VisNode]
    edges: list[VisEdge]
    start_node: str
    end_node: str
    hops: int
    score: float
    explanation: str = ""


@dataclass
class TemporalFrame:
    """A single frame in temporal animation."""

    timestamp: datetime
    nodes: list[VisNode]
    edges: list[VisEdge]
    changes: dict[str, Any] = field(default_factory=dict)


@dataclass
class TemporalAnimation:
    """Temporal evolution animation data."""

    frames: list[TemporalFrame]
    start_time: datetime
    end_time: datetime
    frame_duration_ms: int = 1000


@dataclass
class ClusterInfo:
    """Information about a semantic cluster."""

    cluster_id: str
    label: str
    semantic_group: str
    node_ids: list[str]
    centroid_x: float = 0.0
    centroid_y: float = 0.0
    radius: float = 100.0
    color: str | None = None


@dataclass
class ClusteredGraph:
    """Graph with semantic clustering."""

    graph: VisGraph
    clusters: list[ClusterInfo]
    inter_cluster_edges: list[VisEdge]


class KGVisualizationService:
    """
    Service for preparing knowledge graph data for visualization.

    Supports multiple visualization libraries and formats.
    """

    def __init__(self):
        self._layout_cache: dict[str, VisGraph] = {}

    def create_vis_node(
        self,
        node_id: str,
        label: str,
        category: NodeCategory,
        properties: dict[str, Any] | None = None,
        confidence: float = 1.0,
    ) -> VisNode:
        """Create a visualization node."""
        return VisNode(
            id=node_id,
            label=label,
            category=category,
            color=CATEGORY_COLORS.get(category),
            properties=properties or {},
            confidence=confidence,
            size=self._calculate_node_size(category, confidence),
        )

    def _calculate_node_size(
        self,
        category: NodeCategory,
        confidence: float,
    ) -> float:
        """Calculate node size based on category and confidence."""
        base_size = {
            NodeCategory.PATIENT: 2.0,
            NodeCategory.CONDITION: 1.5,
            NodeCategory.DRUG: 1.5,
            NodeCategory.PROCEDURE: 1.3,
            NodeCategory.LAB: 1.0,
            NodeCategory.CONCEPT: 1.0,
            NodeCategory.INFERENCE: 0.8,
        }.get(category, 1.0)

        return base_size * (0.5 + 0.5 * confidence)

    def create_vis_edge(
        self,
        source: str,
        target: str,
        label: str,
        weight: float = 1.0,
        directed: bool = True,
    ) -> VisEdge:
        """Create a visualization edge."""
        return VisEdge(
            id=f"{source}-{label}-{target}",
            source=source,
            target=target,
            label=label,
            weight=weight,
            directed=directed,
        )

    def build_patient_graph(
        self,
        patient_id: str,
        conditions: list[dict[str, Any]],
        medications: list[dict[str, Any]],
        procedures: list[dict[str, Any]] | None = None,
        labs: list[dict[str, Any]] | None = None,
    ) -> VisGraph:
        """
        Build a visualization graph for a patient.

        Args:
            patient_id: Patient identifier
            conditions: List of patient conditions
            medications: List of patient medications
            procedures: Optional list of procedures
            labs: Optional list of lab results

        Returns:
            VisGraph ready for visualization
        """
        nodes: list[VisNode] = []
        edges: list[VisEdge] = []

        # Patient node
        patient_node = self.create_vis_node(
            node_id=patient_id,
            label=f"Patient {patient_id}",
            category=NodeCategory.PATIENT,
        )
        patient_node.fixed = True  # Center the patient
        nodes.append(patient_node)

        # Condition nodes
        for i, condition in enumerate(conditions):
            cond_id = condition.get("id", f"cond_{i}")
            cond_node = self.create_vis_node(
                node_id=cond_id,
                label=condition.get("name", "Unknown Condition"),
                category=NodeCategory.CONDITION,
                properties=condition,
                confidence=condition.get("confidence", 1.0),
            )
            nodes.append(cond_node)
            edges.append(
                self.create_vis_edge(
                    source=patient_id,
                    target=cond_id,
                    label="HAS_CONDITION",
                )
            )

        # Medication nodes
        for i, med in enumerate(medications):
            med_id = med.get("id", f"med_{i}")
            med_node = self.create_vis_node(
                node_id=med_id,
                label=med.get("name", "Unknown Medication"),
                category=NodeCategory.DRUG,
                properties=med,
            )
            nodes.append(med_node)
            edges.append(
                self.create_vis_edge(
                    source=patient_id,
                    target=med_id,
                    label="TAKES",
                )
            )

            # Link medications to conditions they treat
            treats = med.get("treats_conditions", [])
            for cond_id in treats:
                edges.append(
                    self.create_vis_edge(
                        source=med_id,
                        target=cond_id,
                        label="TREATS",
                    )
                )

        # Procedure nodes
        if procedures:
            for i, proc in enumerate(procedures):
                proc_id = proc.get("id", f"proc_{i}")
                proc_node = self.create_vis_node(
                    node_id=proc_id,
                    label=proc.get("name", "Unknown Procedure"),
                    category=NodeCategory.PROCEDURE,
                    properties=proc,
                )
                nodes.append(proc_node)
                edges.append(
                    self.create_vis_edge(
                        source=patient_id,
                        target=proc_id,
                        label="HAD_PROCEDURE",
                    )
                )

        # Lab nodes
        if labs:
            for i, lab in enumerate(labs):
                lab_id = lab.get("id", f"lab_{i}")
                lab_node = self.create_vis_node(
                    node_id=lab_id,
                    label=f"{lab.get('name', 'Lab')}: {lab.get('value', '')}",
                    category=NodeCategory.LAB,
                    properties=lab,
                )
                nodes.append(lab_node)
                edges.append(
                    self.create_vis_edge(
                        source=patient_id,
                        target=lab_id,
                        label="HAS_RESULT",
                    )
                )

        return VisGraph(
            nodes=nodes,
            edges=edges,
            title=f"Patient {patient_id} Clinical Graph",
            layout=VisualizationType.FORCE_DIRECTED,
        )

    def build_reasoning_path_vis(
        self,
        path_id: str,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        score: float,
        explanation: str = "",
    ) -> ReasoningPathVis:
        """
        Build visualization for a reasoning path.

        Args:
            path_id: Path identifier
            nodes: Nodes in the path
            edges: Edges in the path
            score: Path confidence score
            explanation: Human-readable explanation

        Returns:
            ReasoningPathVis for display
        """
        vis_nodes: list[VisNode] = []
        vis_edges: list[VisEdge] = []

        for i, node in enumerate(nodes):
            category = self._infer_category(node)
            vis_node = self.create_vis_node(
                node_id=node.get("id", f"n{i}"),
                label=node.get("name", node.get("label", f"Node {i}")),
                category=category,
                properties=node,
                confidence=node.get("confidence", 1.0),
            )
            # Position nodes in a line for path visualization
            vis_node.x = i * 150
            vis_node.y = 0
            vis_node.fixed = True
            vis_nodes.append(vis_node)

        for i, edge in enumerate(edges):
            vis_edge = self.create_vis_edge(
                source=edge.get("source", vis_nodes[i].id if i < len(vis_nodes) else ""),
                target=edge.get("target", vis_nodes[i + 1].id if i + 1 < len(vis_nodes) else ""),
                label=edge.get("type", edge.get("label", "RELATED")),
                weight=edge.get("confidence", 1.0),
            )
            vis_edges.append(vis_edge)

        return ReasoningPathVis(
            path_id=path_id,
            nodes=vis_nodes,
            edges=vis_edges,
            start_node=vis_nodes[0].id if vis_nodes else "",
            end_node=vis_nodes[-1].id if vis_nodes else "",
            hops=len(vis_edges),
            score=score,
            explanation=explanation,
        )

    def _infer_category(self, node: dict[str, Any]) -> NodeCategory:
        """Infer node category from properties."""
        semantic_type = node.get("semantic_type", "")
        label = node.get("label", node.get("name", "")).lower()

        # Check semantic type
        if semantic_type in ["T047", "T048", "T191", "T046"]:
            return NodeCategory.CONDITION
        if semantic_type in ["T121", "T200", "T103"]:
            return NodeCategory.DRUG
        if semantic_type in ["T059", "T060", "T061"]:
            return NodeCategory.PROCEDURE
        if semantic_type in ["T034"]:
            return NodeCategory.LAB

        # Check label keywords
        if any(kw in label for kw in ["disease", "syndrome", "disorder"]):
            return NodeCategory.CONDITION
        if any(kw in label for kw in ["drug", "medication", "mg", "ml"]):
            return NodeCategory.DRUG
        if any(kw in label for kw in ["procedure", "surgery", "biopsy"]):
            return NodeCategory.PROCEDURE
        if any(kw in label for kw in ["lab", "test", "level"]):
            return NodeCategory.LAB

        return NodeCategory.CONCEPT

    def build_temporal_animation(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        start_time: datetime,
        end_time: datetime,
        frame_interval_days: int = 30,
    ) -> TemporalAnimation:
        """
        Build temporal animation showing graph evolution.

        Args:
            nodes: All nodes with valid_from/valid_to
            edges: All edges with valid_from/valid_to
            start_time: Animation start
            end_time: Animation end
            frame_interval_days: Days between frames

        Returns:
            TemporalAnimation with frames
        """
        from datetime import timedelta

        frames: list[TemporalFrame] = []
        current_time = start_time

        while current_time <= end_time:
            # Filter nodes valid at current time
            frame_nodes = []
            for node in nodes:
                valid_from = node.get("valid_from")
                valid_to = node.get("valid_to")

                # Parse dates if strings
                if isinstance(valid_from, str):
                    valid_from = datetime.fromisoformat(valid_from.replace("Z", "+00:00"))
                if isinstance(valid_to, str):
                    valid_to = datetime.fromisoformat(valid_to.replace("Z", "+00:00"))

                is_valid = (valid_from is None or valid_from <= current_time) and \
                           (valid_to is None or valid_to > current_time)

                if is_valid:
                    category = self._infer_category(node)
                    vis_node = self.create_vis_node(
                        node_id=node.get("id", ""),
                        label=node.get("name", node.get("label", "")),
                        category=category,
                        properties=node,
                    )
                    vis_node.valid_from = valid_from
                    vis_node.valid_to = valid_to
                    frame_nodes.append(vis_node)

            # Filter edges
            frame_edges = []
            node_ids = {n.id for n in frame_nodes}
            for edge in edges:
                if edge.get("source") in node_ids and edge.get("target") in node_ids:
                    vis_edge = self.create_vis_edge(
                        source=edge.get("source", ""),
                        target=edge.get("target", ""),
                        label=edge.get("type", "RELATED"),
                    )
                    frame_edges.append(vis_edge)

            frames.append(
                TemporalFrame(
                    timestamp=current_time,
                    nodes=frame_nodes,
                    edges=frame_edges,
                )
            )

            current_time += timedelta(days=frame_interval_days)

        return TemporalAnimation(
            frames=frames,
            start_time=start_time,
            end_time=end_time,
            frame_duration_ms=1000,
        )

    def build_semantic_clusters(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> ClusteredGraph:
        """
        Build graph with semantic clustering.

        Groups nodes by semantic type/category for cleaner visualization.

        Args:
            nodes: All graph nodes
            edges: All graph edges

        Returns:
            ClusteredGraph with cluster information
        """
        # Group nodes by category
        clusters: dict[NodeCategory, list[VisNode]] = {}

        vis_nodes = []
        for node in nodes:
            category = self._infer_category(node)
            vis_node = self.create_vis_node(
                node_id=node.get("id", ""),
                label=node.get("name", node.get("label", "")),
                category=category,
                properties=node,
            )

            if category not in clusters:
                clusters[category] = []
            clusters[category].append(vis_node)
            vis_nodes.append(vis_node)

        # Position clusters in a circle
        cluster_infos = []
        num_clusters = len(clusters)
        cluster_radius = 300
        center_x, center_y = 400, 400

        for i, (category, cluster_nodes) in enumerate(clusters.items()):
            angle = (2 * math.pi * i) / max(num_clusters, 1)
            cx = center_x + cluster_radius * math.cos(angle)
            cy = center_y + cluster_radius * math.sin(angle)

            # Position nodes within cluster
            node_radius = 50
            for j, node in enumerate(cluster_nodes):
                node_angle = (2 * math.pi * j) / max(len(cluster_nodes), 1)
                node.x = cx + node_radius * math.cos(node_angle)
                node.y = cy + node_radius * math.sin(node_angle)
                node.group = category.value

            cluster_infos.append(
                ClusterInfo(
                    cluster_id=category.value,
                    label=category.value.title(),
                    semantic_group=category.value,
                    node_ids=[n.id for n in cluster_nodes],
                    centroid_x=cx,
                    centroid_y=cy,
                    radius=node_radius * 1.5,
                    color=CATEGORY_COLORS.get(category),
                )
            )

        # Build edges
        vis_edges = []
        node_ids = {n.id for n in vis_nodes}
        for edge in edges:
            if edge.get("source") in node_ids and edge.get("target") in node_ids:
                vis_edge = self.create_vis_edge(
                    source=edge.get("source", ""),
                    target=edge.get("target", ""),
                    label=edge.get("type", "RELATED"),
                )
                vis_edges.append(vis_edge)

        graph = VisGraph(
            nodes=vis_nodes,
            edges=vis_edges,
            layout=VisualizationType.CLUSTER,
        )

        return ClusteredGraph(
            graph=graph,
            clusters=cluster_infos,
            inter_cluster_edges=[],  # Could be computed if needed
        )

    def to_d3_format(self, graph: VisGraph) -> dict[str, Any]:
        """
        Convert to D3.js format.

        Returns:
            Dictionary compatible with D3.js force layout
        """
        return {
            "nodes": [
                {
                    "id": n.id,
                    "label": n.label,
                    "group": n.category.value,
                    "size": n.size,
                    "color": n.color,
                    "x": n.x,
                    "y": n.y,
                    "fx": n.x if n.fixed else None,
                    "fy": n.y if n.fixed else None,
                    **n.properties,
                }
                for n in graph.nodes
            ],
            "links": [
                {
                    "source": e.source,
                    "target": e.target,
                    "label": e.label,
                    "weight": e.weight,
                    "color": e.color,
                }
                for e in graph.edges
            ],
            "metadata": graph.metadata,
        }

    def to_cytoscape_format(self, graph: VisGraph) -> dict[str, Any]:
        """
        Convert to Cytoscape.js format.

        Returns:
            Dictionary compatible with Cytoscape.js
        """
        elements = []

        for node in graph.nodes:
            elements.append({
                "data": {
                    "id": node.id,
                    "label": node.label,
                    "category": node.category.value,
                    **node.properties,
                },
                "position": {"x": node.x or 0, "y": node.y or 0},
                "style": {
                    "background-color": node.color,
                    "width": node.size * 30,
                    "height": node.size * 30,
                },
            })

        for edge in graph.edges:
            elements.append({
                "data": {
                    "id": edge.id,
                    "source": edge.source,
                    "target": edge.target,
                    "label": edge.label,
                    **edge.properties,
                },
                "style": {
                    "line-color": edge.color,
                    "line-style": edge.style,
                    "width": edge.weight * 2,
                },
            })

        return {"elements": elements}

    def to_vis_network_format(self, graph: VisGraph) -> dict[str, Any]:
        """
        Convert to vis.js Network format.

        Returns:
            Dictionary compatible with vis.js Network
        """
        return {
            "nodes": [
                {
                    "id": n.id,
                    "label": n.label,
                    "group": n.category.value,
                    "size": n.size * 20,
                    "color": {"background": n.color, "border": n.color},
                    "x": n.x,
                    "y": n.y,
                    "fixed": n.fixed,
                    "title": f"{n.label}\nConfidence: {n.confidence:.2f}",
                }
                for n in graph.nodes
            ],
            "edges": [
                {
                    "from": e.source,
                    "to": e.target,
                    "label": e.label,
                    "arrows": "to" if e.directed else None,
                    "width": e.weight * 2,
                    "color": e.color,
                    "dashes": e.style == "dashed",
                }
                for e in graph.edges
            ],
        }


# Singleton instance
_kg_vis_service: KGVisualizationService | None = None
_kg_vis_lock = threading.Lock()


def get_kg_visualization_service() -> KGVisualizationService:
    """Get the singleton knowledge graph visualization service."""
    global _kg_vis_service
    # VP-ThreadSafety: Double-checked locking for thread safety
    if _kg_vis_service is None:
        with _kg_vis_lock:
            if _kg_vis_service is None:
                _kg_vis_service = KGVisualizationService()
    return _kg_vis_service
