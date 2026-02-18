"""Neo4j Query Router for multi-hop graph traversal.

Routes graph traversal queries to the optimal backend:
- 1-hop queries always use PostgreSQL (fast, no overhead)
- 2+ hop queries use Neo4j when available (variable-length path matching)
- Falls back to PostgreSQL BFS when Neo4j is unavailable or errors

Neo4j's genuine advantage: variable-length multi-relational path matching
in a single Cypher query vs. N*M per-hop queries in PostgreSQL.
"""
# MODULE: graph_rag
# MATURITY: pilot

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.knowledge_graph import KGEdge, KGNode
from app.schemas.knowledge_graph import EdgeType, NodeType
from app.services.graph_database_service import GraphDatabaseService, get_graph_database_service

logger = logging.getLogger(__name__)


@dataclass
class MultiHopQuery:
    """Query parameters for multi-hop graph traversal."""

    patient_id: str
    start_concept_ids: list[int]
    edge_type_filter: list[str] | None = None
    max_hops: int = 3
    min_confidence: float = 0.3
    max_paths: int = 20


@dataclass
class PathNode:
    """A node in a traversal path."""

    node_id: str
    label: str
    node_type: str
    omop_concept_id: int | None = None


@dataclass
class PathEdge:
    """An edge in a traversal path."""

    edge_type: str
    confidence: float = 1.0
    temporality: str | None = None
    event_date: str | None = None


@dataclass
class GraphPath:
    """A traversal path through the knowledge graph."""

    nodes: list[PathNode]
    edges: list[PathEdge]
    hops: int
    path_confidence: float = 1.0
    source: str = "pg"  # "pg" or "neo4j"


class Neo4jQueryRouter:
    """Routes multi-hop queries to Neo4j or PostgreSQL.

    Decision logic:
    - max_hops <= 1: Always PG (single JOIN, no overhead)
    - max_hops >= 2 and Neo4j available: Neo4j (variable-length Cypher)
    - max_hops >= 2 and Neo4j unavailable: PG BFS fallback

    Usage:
        router = Neo4jQueryRouter(session)
        paths = router.execute_multi_hop(query)
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self._graph_db: GraphDatabaseService | None = None

    @property
    def neo4j_available(self) -> bool:
        """Check if Neo4j is available for queries."""
        try:
            if self._graph_db is None:
                self._graph_db = get_graph_database_service()
            return self._graph_db.is_connected
        except Exception:
            return False

    def execute_multi_hop(self, query: MultiHopQuery) -> list[GraphPath]:
        """Execute a multi-hop traversal query.

        Routes to optimal backend based on hop count and Neo4j availability.
        """
        if query.max_hops <= 1 or not self.neo4j_available:
            return self._pg_bfs(query)

        try:
            return self._neo4j_multi_hop(query)
        except Exception as e:
            logger.warning(
                "Neo4j multi-hop query failed, falling back to PG BFS: %s", e
            )
            return self._pg_bfs(query)

    def _neo4j_multi_hop(self, query: MultiHopQuery) -> list[GraphPath]:
        """Execute multi-hop traversal via Neo4j Cypher.

        Uses variable-length path matching — Neo4j's genuine advantage
        over PostgreSQL for this pattern.
        """
        assert self._graph_db is not None

        # Build edge type filter for Cypher
        if query.edge_type_filter:
            edge_types = query.edge_type_filter
        else:
            # All defined edge types
            edge_types = [e.value.upper().replace(" ", "_") for e in EdgeType]

        # Neo4j doesn't support parameters in variable-length patterns,
        # so we interpolate max_hops directly (safe integer, not user input)
        safe_max_hops = int(query.max_hops)
        safe_max_paths = int(query.max_paths)

        cypher = f"""
        MATCH (p:Patient {{patient_id: $patient_id}})-[]->(start:ClinicalFact)
        WHERE start.omop_concept_id IN $start_concept_ids
        MATCH path = (start)-[*1..{safe_max_hops}]-(end:ClinicalFact)
        WHERE ALL(r IN relationships(path) WHERE type(r) IN $edge_types)
          AND start <> end
        WITH path, nodes(path) AS path_nodes, relationships(path) AS path_rels,
             length(path) AS hops,
             reduce(c = 1.0, r IN relationships(path) |
               c * COALESCE(toFloat(r.temporal_confidence), 1.0)) AS path_confidence
        WHERE path_confidence >= $min_confidence
        RETURN path_nodes, path_rels, hops, path_confidence
        ORDER BY path_confidence DESC, hops ASC
        LIMIT {safe_max_paths}
        """

        params = {
            "patient_id": query.patient_id,
            "start_concept_ids": query.start_concept_ids,
            "edge_types": edge_types,
            "min_confidence": query.min_confidence,
        }

        result = self._graph_db.execute_read(cypher, params)

        paths: list[GraphPath] = []
        for record in result.records:
            path_nodes = record.get("path_nodes", [])
            path_rels = record.get("path_rels", [])
            hops = record.get("hops", 0)
            confidence = record.get("path_confidence", 1.0)

            nodes = []
            for n in path_nodes:
                nodes.append(PathNode(
                    node_id=n.get("node_id", ""),
                    label=n.get("label", ""),
                    node_type=n.get("node_type", ""),
                    omop_concept_id=n.get("omop_concept_id"),
                ))

            edges = []
            for r in path_rels:
                edges.append(PathEdge(
                    edge_type=r.get("edge_type", "related_to"),
                    confidence=r.get("temporal_confidence") or 1.0,
                    temporality=r.get("temporality"),
                    event_date=r.get("event_date"),
                ))

            paths.append(GraphPath(
                nodes=nodes,
                edges=edges,
                hops=hops,
                path_confidence=confidence,
                source="neo4j",
            ))

        return paths

    def _pg_bfs(self, query: MultiHopQuery) -> list[GraphPath]:
        """Breadth-first traversal in PostgreSQL.

        Fallback for when Neo4j is unavailable. Executes per-hop queries.
        """
        # Find starting nodes by OMOP concept ID
        start_stmt = (
            select(KGNode)
            .join(
                KGEdge,
                or_(
                    KGEdge.target_node_id == KGNode.id,
                    KGEdge.source_node_id == KGNode.id,
                ),
            )
            .where(KGEdge.patient_id == query.patient_id)
            .where(KGNode.omop_concept_id.in_(query.start_concept_ids))
            .distinct()
        )
        result = self._session.execute(start_stmt)
        start_nodes = list(result.scalars().all())

        if not start_nodes:
            return []

        all_paths: list[GraphPath] = []
        visited: set[str] = set()

        for start_node in start_nodes[:5]:
            node_paths = self._pg_bfs_from_node(
                patient_id=query.patient_id,
                start_node=start_node,
                max_hops=query.max_hops,
                min_confidence=query.min_confidence,
                edge_type_filter=query.edge_type_filter,
                visited=visited,
            )
            all_paths.extend(node_paths)
            if len(all_paths) >= query.max_paths:
                break

        return all_paths[:query.max_paths]

    def _pg_bfs_from_node(
        self,
        patient_id: str,
        start_node: KGNode,
        max_hops: int,
        min_confidence: float,
        edge_type_filter: list[str] | None,
        visited: set[str],
    ) -> list[GraphPath]:
        """BFS from a single node in PostgreSQL."""
        paths: list[GraphPath] = []
        frontier: list[tuple[KGNode, list[PathNode], list[PathEdge], float]] = [
            (
                start_node,
                [PathNode(
                    node_id=str(start_node.id),
                    label=start_node.label,
                    node_type=start_node.node_type.value,
                    omop_concept_id=start_node.omop_concept_id,
                )],
                [],
                1.0,
            )
        ]

        for hop in range(max_hops):
            next_frontier: list[tuple[KGNode, list[PathNode], list[PathEdge], float]] = []

            # Batch fetch edges for all frontier nodes
            frontier_ids = [str(node.id) for node, _, _, _ in frontier]
            if not frontier_ids:
                break

            edge_stmt = (
                select(KGEdge)
                .where(KGEdge.patient_id == patient_id)
                .where(
                    or_(
                        KGEdge.source_node_id.in_(frontier_ids),
                        KGEdge.target_node_id.in_(frontier_ids),
                    )
                )
            )
            if edge_type_filter:
                edge_stmt = edge_stmt.where(KGEdge.edge_type.in_(edge_type_filter))

            edges = list(self._session.execute(edge_stmt).scalars().all())

            # Batch fetch neighbor nodes
            neighbor_ids: set[str] = set()
            for edge in edges:
                neighbor_ids.add(edge.source_node_id)
                neighbor_ids.add(edge.target_node_id)
            neighbor_ids -= set(frontier_ids)

            neighbor_map: dict[str, KGNode] = {}
            if neighbor_ids:
                neighbor_stmt = select(KGNode).where(KGNode.id.in_(list(neighbor_ids)))
                neighbor_map = {
                    n.id: n
                    for n in self._session.execute(neighbor_stmt).scalars().all()
                }

            for current_node, path_nodes, path_edges, path_conf in frontier:
                current_id = str(current_node.id)
                for edge in edges:
                    if edge.source_node_id == current_id:
                        neighbor = neighbor_map.get(edge.target_node_id)
                    elif edge.target_node_id == current_id:
                        neighbor = neighbor_map.get(edge.source_node_id)
                    else:
                        continue

                    if neighbor is None or neighbor.id in visited:
                        continue

                    edge_conf = edge.temporal_confidence or 1.0
                    new_conf = path_conf * edge_conf
                    if new_conf < min_confidence:
                        continue

                    new_node = PathNode(
                        node_id=str(neighbor.id),
                        label=neighbor.label,
                        node_type=neighbor.node_type.value,
                        omop_concept_id=neighbor.omop_concept_id,
                    )
                    new_edge = PathEdge(
                        edge_type=edge.edge_type.value,
                        confidence=edge_conf,
                        temporality=edge.temporality,
                        event_date=edge.event_date.isoformat() if edge.event_date else None,
                    )

                    new_path_nodes = path_nodes + [new_node]
                    new_path_edges = path_edges + [new_edge]

                    paths.append(GraphPath(
                        nodes=new_path_nodes,
                        edges=new_path_edges,
                        hops=hop + 1,
                        path_confidence=new_conf,
                        source="pg",
                    ))

                    visited.add(neighbor.id)
                    next_frontier.append((neighbor, new_path_nodes, new_path_edges, new_conf))

            frontier = next_frontier

        return paths
