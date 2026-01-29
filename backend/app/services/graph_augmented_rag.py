"""Graph-Augmented RAG Service.

Enhances retrieval-augmented generation with knowledge graph traversal.
Combines document retrieval with graph paths for richer LLM context.

Architecture:
1. Extract concepts from query
2. Traverse patient KG to find relevant paths (2-3 hops)
3. Query temporal context for time-aware evidence
4. Serialize graph paths as structured context
5. Combine with document retrieval for comprehensive context
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.knowledge_graph import KGEdge, KGNode
from app.schemas.knowledge_graph import EdgeType, NodeType

logger = logging.getLogger(__name__)


@dataclass
class GraphPath:
    """A traversal path through the knowledge graph."""

    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    path_type: str  # "condition_treatment", "temporal_sequence", "comorbidity"
    confidence: float = 1.0

    def to_prompt_format(self) -> str:
        """Format path for LLM prompt."""
        if not self.nodes or len(self.nodes) < 2:
            return ""

        parts = []
        for i, node in enumerate(self.nodes):
            node_str = node.get("label", "?")
            parts.append(node_str)

            if i < len(self.edges):
                edge = self.edges[i]
                edge_type = edge.get("edge_type", "relates_to")
                confidence = edge.get("confidence", 1.0)
                temporal = ""
                if edge.get("temporality"):
                    temporal = f", {edge['temporality']}"
                parts.append(f" --[{edge_type} (conf: {confidence:.2f}{temporal})]--> ")

        return "".join(parts)


@dataclass
class TemporalContext:
    """Temporal context extracted from the graph."""

    event_timeline: list[dict[str, Any]]  # Events in chronological order
    temporal_conflicts: list[str]  # Any detected conflicts
    current_state: dict[str, Any]  # What's true now
    historical_state: dict[str, Any]  # What was true in the past


@dataclass
class GraphAugmentedContext:
    """Context combining graph traversal with documents."""

    query: str
    patient_id: str
    graph_paths: list[GraphPath]
    temporal_context: TemporalContext | None
    retrieved_documents: list[dict[str, Any]]
    policy_constraints: list[dict[str, Any]]
    total_evidence_pieces: int = 0

    def to_llm_prompt(self) -> str:
        """Format all context for LLM consumption."""
        sections = []

        # Graph Evidence Section
        if self.graph_paths:
            sections.append("=== Graph Evidence ===")
            for i, path in enumerate(self.graph_paths, 1):
                path_str = path.to_prompt_format()
                if path_str:
                    sections.append(f"Path {i} ({path.path_type}): {path_str}")
            sections.append("")

        # Temporal Context Section
        if self.temporal_context:
            sections.append("=== Temporal Context ===")
            if self.temporal_context.current_state:
                sections.append("Current State:")
                for key, value in self.temporal_context.current_state.items():
                    sections.append(f"  - {key}: {value}")

            if self.temporal_context.event_timeline:
                sections.append("Timeline:")
                for event in self.temporal_context.event_timeline[:10]:
                    date_str = event.get("date", "unknown")
                    desc = event.get("description", "")
                    sections.append(f"  - {date_str}: {desc}")

            if self.temporal_context.temporal_conflicts:
                sections.append("Temporal Concerns:")
                for conflict in self.temporal_context.temporal_conflicts:
                    sections.append(f"  - {conflict}")
            sections.append("")

        # Policy Constraints Section
        if self.policy_constraints:
            sections.append("=== Applicable Policy Rules ===")
            for policy in self.policy_constraints[:5]:
                rule_id = policy.get("rule_id", "")
                description = policy.get("description", "")
                strength = policy.get("strength", "")
                sections.append(f"Rule {rule_id} ({strength}): {description}")
            sections.append("")

        # Retrieved Documents Section
        if self.retrieved_documents:
            sections.append("=== Retrieved Document Context ===")
            for doc in self.retrieved_documents[:5]:
                source = doc.get("source", "document")
                content = doc.get("content", "")[:500]
                sections.append(f"[{source}]: {content}")
            sections.append("")

        return "\n".join(sections)


class GraphAugmentedRAGService:
    """Service for graph-augmented retrieval-augmented generation.

    Enhances LLM context with knowledge graph traversal paths
    and temporal reasoning for richer, more accurate responses.

    Usage:
        service = GraphAugmentedRAGService(session)
        context = service.retrieve_context(
            query="What medications is this patient on for diabetes?",
            patient_id="P001",
        )
        llm_prompt = context.to_llm_prompt()
    """

    def __init__(self, session: Session) -> None:
        """Initialize the service.

        Args:
            session: SQLAlchemy database session.
        """
        self._session = session

    def retrieve_context(
        self,
        query: str,
        patient_id: str,
        max_hops: int = 3,
        max_paths: int = 10,
        include_temporal: bool = True,
        include_policies: bool = True,
        time_point: datetime | None = None,
    ) -> GraphAugmentedContext:
        """Retrieve graph-augmented context for a query.

        Args:
            query: The user's question or query.
            patient_id: Patient to query graph for.
            max_hops: Maximum hops in graph traversal.
            max_paths: Maximum paths to return.
            include_temporal: Include temporal context.
            include_policies: Include policy constraints.
            time_point: Optional time point for temporal queries.

        Returns:
            GraphAugmentedContext with paths, temporal info, and documents.
        """
        # Extract concepts from query
        query_concepts = self._extract_query_concepts(query)

        # Find relevant starting nodes in patient's graph
        start_nodes = self._find_matching_nodes(patient_id, query_concepts)

        # Traverse graph from starting nodes
        graph_paths = self._traverse_graph(
            patient_id=patient_id,
            start_nodes=start_nodes,
            max_hops=max_hops,
            max_paths=max_paths,
        )

        # Get temporal context if requested
        temporal_context = None
        if include_temporal:
            temporal_context = self._get_temporal_context(
                patient_id=patient_id,
                time_point=time_point,
            )

        # Get applicable policy constraints if requested
        policy_constraints = []
        if include_policies:
            policy_constraints = self._get_policy_constraints(
                patient_id=patient_id,
                query_concepts=query_concepts,
            )

        # Retrieve relevant documents (placeholder - would integrate with SemanticQA)
        retrieved_documents = self._retrieve_documents(
            query=query,
            patient_id=patient_id,
        )

        return GraphAugmentedContext(
            query=query,
            patient_id=patient_id,
            graph_paths=graph_paths,
            temporal_context=temporal_context,
            retrieved_documents=retrieved_documents,
            policy_constraints=policy_constraints,
            total_evidence_pieces=(
                len(graph_paths)
                + len(retrieved_documents)
                + len(policy_constraints)
            ),
        )

    def _extract_query_concepts(self, query: str) -> list[str]:
        """Extract clinical concepts from query text.

        This is a simplified implementation. In production, use NLP
        entity extraction with SNOMED/RxNorm mapping.
        """
        # Common clinical terms to look for
        clinical_terms = [
            "diabetes", "hypertension", "heart failure", "copd", "asthma",
            "metformin", "lisinopril", "aspirin", "insulin", "atorvastatin",
            "a1c", "glucose", "creatinine", "blood pressure", "hemoglobin",
            "medication", "condition", "diagnosis", "treatment", "lab",
        ]

        query_lower = query.lower()
        found_concepts = []

        for term in clinical_terms:
            if term in query_lower:
                found_concepts.append(term)

        # Extract any quoted terms
        import re
        quoted = re.findall(r'"([^"]+)"', query)
        found_concepts.extend(quoted)

        return found_concepts

    def _find_matching_nodes(
        self,
        patient_id: str,
        concepts: list[str],
    ) -> list[KGNode]:
        """Find nodes in patient's graph matching query concepts."""
        if not concepts:
            # Return patient node as starting point
            stmt = (
                select(KGNode)
                .where(KGNode.patient_id == patient_id)
                .where(KGNode.node_type == NodeType.PATIENT)
            )
            result = self._session.execute(stmt)
            patient_node = result.scalar_one_or_none()
            return [patient_node] if patient_node else []

        # Search for nodes matching any concept
        stmt = select(KGNode).where(KGNode.patient_id == patient_id)
        result = self._session.execute(stmt)
        nodes = result.scalars().all()

        matching = []
        for node in nodes:
            label_lower = node.label.lower()
            for concept in concepts:
                if concept.lower() in label_lower:
                    matching.append(node)
                    break

        return matching[:20]  # Limit starting nodes

    def _traverse_graph(
        self,
        patient_id: str,
        start_nodes: list[KGNode],
        max_hops: int,
        max_paths: int,
    ) -> list[GraphPath]:
        """Traverse graph from starting nodes to find relevant paths."""
        paths = []

        for start_node in start_nodes[:5]:  # Limit starting points
            # BFS traversal from this node
            node_paths = self._bfs_traverse(
                patient_id=patient_id,
                start_node=start_node,
                max_hops=max_hops,
            )
            paths.extend(node_paths)

            if len(paths) >= max_paths:
                break

        return paths[:max_paths]

    def _bfs_traverse(
        self,
        patient_id: str,
        start_node: KGNode,
        max_hops: int,
    ) -> list[GraphPath]:
        """BFS traversal from a starting node."""
        paths = []

        # Get outgoing edges from start node
        stmt = (
            select(KGEdge)
            .where(KGEdge.source_node_id == start_node.id)
            .where(KGEdge.patient_id == patient_id)
        )
        result = self._session.execute(stmt)
        edges = result.scalars().all()

        for edge in edges[:10]:
            # Get target node
            target_stmt = select(KGNode).where(KGNode.id == edge.target_node_id)
            target_result = self._session.execute(target_stmt)
            target_node = target_result.scalar_one_or_none()

            if target_node:
                # Build 1-hop path
                path = GraphPath(
                    nodes=[
                        {"id": start_node.id, "label": start_node.label, "type": start_node.node_type.value},
                        {"id": target_node.id, "label": target_node.label, "type": target_node.node_type.value},
                    ],
                    edges=[
                        {
                            "edge_type": edge.edge_type.value,
                            "confidence": edge.temporal_confidence or 1.0,
                            "temporality": edge.temporality,
                            "event_date": edge.event_date.isoformat() if edge.event_date else None,
                        }
                    ],
                    path_type=self._classify_path_type(start_node, edge, target_node),
                    confidence=edge.temporal_confidence or 1.0,
                )
                paths.append(path)

                # Continue traversal if more hops allowed
                if max_hops > 1:
                    deeper_paths = self._bfs_traverse(
                        patient_id=patient_id,
                        start_node=target_node,
                        max_hops=max_hops - 1,
                    )
                    for deeper_path in deeper_paths[:3]:
                        # Combine paths
                        combined = GraphPath(
                            nodes=path.nodes + deeper_path.nodes[1:],
                            edges=path.edges + deeper_path.edges,
                            path_type=path.path_type,
                            confidence=min(path.confidence, deeper_path.confidence),
                        )
                        paths.append(combined)

        return paths

    def _classify_path_type(
        self,
        source: KGNode,
        edge: KGEdge,
        target: KGNode,
    ) -> str:
        """Classify the type of path for better context."""
        if source.node_type == NodeType.PATIENT:
            if target.node_type == NodeType.CONDITION:
                return "patient_condition"
            elif target.node_type == NodeType.DRUG:
                return "patient_medication"
            elif target.node_type == NodeType.MEASUREMENT:
                return "patient_measurement"

        if source.node_type == NodeType.CONDITION:
            if target.node_type == NodeType.DRUG:
                return "condition_treatment"
            elif target.node_type == NodeType.CONDITION:
                return "comorbidity"

        if edge.edge_type == EdgeType.DRUG_TREATS:
            return "treatment_relationship"

        return "general_relationship"

    def _get_temporal_context(
        self,
        patient_id: str,
        time_point: datetime | None,
    ) -> TemporalContext:
        """Get temporal context from patient's graph."""
        # Get all edges with temporal data
        stmt = (
            select(KGEdge)
            .where(KGEdge.patient_id == patient_id)
            .where(KGEdge.event_date.isnot(None))
            .order_by(KGEdge.event_date.desc())
        )
        result = self._session.execute(stmt)
        edges = result.scalars().all()

        # Build timeline
        timeline = []
        current_state = {}
        historical_state = {}

        for edge in edges[:50]:
            # Get target node for description
            target_stmt = select(KGNode).where(KGNode.id == edge.target_node_id)
            target = self._session.execute(target_stmt).scalar_one_or_none()

            if target:
                event = {
                    "date": edge.event_date.isoformat() if edge.event_date else None,
                    "description": f"{edge.edge_type.value}: {target.label}",
                    "temporality": edge.temporality,
                    "is_current": edge.temporality == "current",
                }
                timeline.append(event)

                # Track current vs historical
                if edge.temporality == "current":
                    current_state[target.label] = "active"
                elif edge.temporality == "past":
                    historical_state[target.label] = "resolved"

        # Detect temporal conflicts (simplified)
        conflicts = []
        # In a real implementation, use temporal_query_service

        return TemporalContext(
            event_timeline=timeline,
            temporal_conflicts=conflicts,
            current_state=current_state,
            historical_state=historical_state,
        )

    def _get_policy_constraints(
        self,
        patient_id: str,
        query_concepts: list[str],
    ) -> list[dict[str, Any]]:
        """Get applicable policy constraints.

        In production, this would query the PolicyKG and match
        against patient conditions/medications.
        """
        # Placeholder - would integrate with PolicyComplianceAgent
        return []

    def _retrieve_documents(
        self,
        query: str,
        patient_id: str,
    ) -> list[dict[str, Any]]:
        """Retrieve relevant documents for the query.

        In production, this would integrate with SemanticQAService.
        """
        # Placeholder - would integrate with document retrieval
        return []


def get_graph_augmented_rag_service(session: Session) -> GraphAugmentedRAGService:
    """Factory function to create GraphAugmentedRAGService."""
    return GraphAugmentedRAGService(session)
