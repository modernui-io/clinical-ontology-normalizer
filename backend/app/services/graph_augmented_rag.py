"""Graph-Augmented RAG Service.

Enhances retrieval-augmented generation with knowledge graph traversal.
Combines document retrieval with graph paths for richer LLM context.

Architecture:
1. Extract concepts from query via NLP + OMOP lookup + label fallback
2. Traverse patient KG to find relevant paths (2-3 hops, bidirectional)
3. Query temporal context for time-aware evidence (batch-optimized)
4. Retrieve applicable clinical guidelines via GuidelineRAGService
5. Serialize graph paths as structured context
6. Combine with document retrieval for comprehensive context

Supports both sync and async SQLAlchemy sessions.
"""
# MODULE: graph_rag
# MATURITY: pilot

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Union
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.knowledge_graph import KGEdge, KGNode
from app.schemas.knowledge_graph import EdgeType, NodeType

from app.services.kg_cache_service import (
    invalidate_traversal_cache,
    traversal_cache_get as _traversal_cache_get,
    traversal_cache_key as _traversal_cache_key,
    traversal_cache_put as _traversal_cache_put,
)

logger = logging.getLogger(__name__)

# Minimum edge confidence for traversal inclusion (Step 4)
MIN_TRAVERSAL_CONFIDENCE = 0.3

# Causal language patterns that trigger causal reasoning integration
_CAUSAL_PATTERNS = re.compile(
    r"\b(caused?\s+by|leads?\s+to|side\s+effects?|adverse\s+effects?|"
    r"treatment\s+for|treats?|exacerbat|complicat|progression|"
    r"contraindic|result(?:s|ed|ing)?\s+in)\b",
    re.IGNORECASE,
)

# Map NLP EntityType values to OMOP domain hints for concept lookup
_ENTITY_TYPE_TO_DOMAIN: dict[str, str] = {
    "diagnosis": "Condition",
    "medication": "Drug",
    "procedure": "Procedure",
    "lab_result": "Measurement",
    "vital_sign": "Measurement",
    "symptom": "Condition",
    "allergy": "Observation",
}

# Map NLP EntityType values to preferred KGEdge types for traversal scoring
_ENTITY_TYPE_TO_PREFERRED_EDGES: dict[str, set[str]] = {
    "diagnosis": {EdgeType.HAS_CONDITION.value, EdgeType.CONDITION_TREATED_BY.value, EdgeType.SYMPTOM_OF.value},
    "medication": {EdgeType.TAKES_DRUG.value, EdgeType.DRUG_TREATS.value, EdgeType.DRUG_INTERACTION.value},
    "lab_result": {EdgeType.HAS_MEASUREMENT.value, EdgeType.MONITORS.value},
    "vital_sign": {EdgeType.HAS_MEASUREMENT.value, EdgeType.MONITORS.value},
    "procedure": {EdgeType.HAS_PROCEDURE.value},
    "symptom": {EdgeType.HAS_CONDITION.value, EdgeType.SYMPTOM_OF.value},
}


@dataclass
class QueryConcept:
    """A concept extracted from a user query with optional OMOP resolution."""

    text: str
    entity_type: str | None = None  # e.g. "diagnosis", "medication"
    omop_concept_id: int | None = None
    confidence: float = 1.0


@dataclass
class GraphPath:
    """A traversal path through the knowledge graph."""

    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    path_type: str  # "condition_treatment", "temporal_sequence", "comorbidity"
    confidence: float = 1.0

    def to_prompt_format(self, assertion_mode: str = "full") -> str:
        """Format path for LLM prompt.

        Args:
            assertion_mode: "full" | "extracted_only" | "none".
                When "none", assertion labels are omitted from the prompt.
        """
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
                assertion_str = ""
                if assertion_mode != "none":
                    assertion = edge.get("assertion", "present")
                    if assertion != "present":
                        assertion_str = f", {assertion.upper()}"
                parts.append(f" --[{edge_type} (conf: {confidence:.2f}{temporal}{assertion_str})]--> ")

        return "".join(parts)


@dataclass
class TemporalContext:
    """Temporal context extracted from the graph."""

    event_timeline: list[dict[str, Any]]  # Events in chronological order
    temporal_conflicts: list[str]  # Any detected conflicts
    current_state: dict[str, Any]  # What's true now
    historical_state: dict[str, Any]  # What was true in the past


class SourceRetrievalStatus:
    """Status constants for document source retrieval (P1-011)."""

    FULL = "full"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


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
    source_retrieval_status: str = field(default=SourceRetrievalStatus.UNAVAILABLE)

    def to_llm_prompt(self, assertion_mode: str = "full") -> str:
        """Format all context for LLM consumption.

        Args:
            assertion_mode: "full" | "extracted_only" | "none".
                Controls whether assertion labels appear in graph evidence
                and whether the Assertion Notes section is included.
        """
        sections = []

        # Assertion Notes Section FIRST (only in full or extracted_only mode)
        # Placed at the top so the model sees critical assertion status before evidence
        if assertion_mode != "none" and self.graph_paths:
            negated_findings = []
            uncertain_findings = []
            family_findings = []
            historical_findings = []
            for path in self.graph_paths:
                for idx, edge in enumerate(path.edges):
                    assertion = edge.get("assertion", "present")
                    # Use the target node (idx+1) for this edge, not just the last node
                    target_label = (
                        path.nodes[idx + 1].get("label", "?")
                        if idx + 1 < len(path.nodes)
                        else path.nodes[-1].get("label", "?") if path.nodes else "?"
                    )
                    if assertion == "absent":
                        negated_findings.append(target_label)
                    elif assertion == "possible":
                        uncertain_findings.append(target_label)
                    elif assertion == "family_history":
                        family_findings.append(target_label)
                    elif assertion == "historical":
                        historical_findings.append(target_label)

            if negated_findings or uncertain_findings or family_findings or historical_findings:
                sections.append("=== IMPORTANT: Clinical Assertion Status ===")
                sections.append("The following findings have NON-PRESENT assertion status.")
                sections.append("You MUST use this information when answering.")
                if negated_findings:
                    sections.append(
                        f">>> NEGATED (patient does NOT have): {', '.join(set(negated_findings))}"
                    )
                if uncertain_findings:
                    sections.append(
                        f">>> UNCERTAIN (suspected, NOT confirmed): {', '.join(set(uncertain_findings))}"
                    )
                if family_findings:
                    sections.append(
                        f">>> FAMILY HISTORY ONLY (relative's condition, NOT patient's): "
                        f"{', '.join(set(family_findings))}"
                    )
                if historical_findings:
                    sections.append(
                        f">>> HISTORICAL (past/resolved, NOT current): {', '.join(set(historical_findings))}"
                    )
                sections.append("")

        # Graph Evidence Section
        if self.graph_paths:
            sections.append("=== Graph Evidence ===")
            for i, path in enumerate(self.graph_paths, 1):
                path_str = path.to_prompt_format(assertion_mode=assertion_mode)
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

    Supports both sync and async SQLAlchemy sessions.

    Usage (sync):
        service = GraphAugmentedRAGService(session)
        context = service.retrieve_context(
            query="What medications is this patient on for diabetes?",
            patient_id="P001",
        )
        llm_prompt = context.to_llm_prompt()

    Usage (async):
        service = GraphAugmentedRAGService(async_session)
        context = await service.retrieve_context_async(
            query="What medications is this patient on for diabetes?",
            patient_id="P001",
        )
        llm_prompt = context.to_llm_prompt()
    """

    def __init__(self, session: Union[Session, AsyncSession]) -> None:
        """Initialize the service.

        Args:
            session: SQLAlchemy database session (sync or async).
        """
        self._session = session
        self._is_async = isinstance(session, AsyncSession)

    async def retrieve_context_async(
        self,
        query: str,
        patient_id: str,
        max_hops: int = 3,
        max_paths: int = 10,
        include_temporal: bool = True,
        include_policies: bool = True,
        time_point: datetime | None = None,
    ) -> GraphAugmentedContext:
        """Retrieve graph-augmented context for a query (async version).

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
        # Scale-safety: clamp unbounded parameters
        max_hops = min(max_hops, 10)
        max_paths = min(max_paths, 100)

        # Step 1: Extract concepts from query (NLP + quoted terms)
        query_concepts = self._extract_query_concepts(query)

        # Step 1 Tier 2: Enrich with OMOP concept IDs (async only)
        query_concepts = await self._enrich_concepts_with_omop_async(query_concepts)

        # Find relevant starting nodes in patient's graph
        start_nodes = await self._find_matching_nodes_async(patient_id, query_concepts)

        # Traverse graph from starting nodes
        graph_paths = await self._traverse_graph_async(
            patient_id=patient_id,
            start_nodes=start_nodes,
            query_concepts=query_concepts,
            max_hops=max_hops,
            max_paths=max_paths,
        )

        # Get temporal context if requested
        temporal_context = None
        if include_temporal:
            temporal_context = await self._get_temporal_context_async(
                patient_id=patient_id,
                time_point=time_point,
            )

        # Get applicable policy constraints if requested
        policy_constraints: list[dict[str, Any]] = []
        if include_policies:
            policy_constraints = await self._get_policy_constraints_async(
                patient_id=patient_id,
                query_concepts=query_concepts,
            )

        # P1-011: Real document retrieval with status tracking
        retrieved_documents, source_status = await self._retrieve_documents_async(
            query=query,
            patient_id=patient_id,
            query_concepts=query_concepts,
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
            source_retrieval_status=source_status,
        )

    def retrieve_context(
        self,
        query: str,
        patient_id: str,
        max_hops: int = 3,
        max_paths: int = 10,
        include_temporal: bool = True,
        include_policies: bool = True,
        time_point: datetime | None = None,
        assertion_mode: str = "full",
        temporal_mode: str = "full_bitemporal",
        retrieval_mode: str = "graph_plus_doc",
    ) -> GraphAugmentedContext:
        """Retrieve graph-augmented context for a query (sync version).

        Args:
            query: The user's question or query.
            patient_id: Patient to query graph for.
            max_hops: Maximum hops in graph traversal.
            max_paths: Maximum paths to return.
            include_temporal: Include temporal context.
            include_policies: Include policy constraints.
            time_point: Optional time point for temporal queries.
            assertion_mode: "full" | "extracted_only" | "none".
            temporal_mode: "full_bitemporal" | "timestamps_only" | "no_temporal".
            retrieval_mode: "doc_only" | "graph_only" | "graph_plus_doc" | "graph_plus_doc_plus_guidelines".

        Returns:
            GraphAugmentedContext with paths, temporal info, and documents.
        """
        # Scale-safety: clamp unbounded parameters
        max_hops = min(max_hops, 10)
        max_paths = min(max_paths, 100)

        # Step 1: Extract concepts from query (NLP + quoted terms)
        # Note: OMOP enrichment skipped in sync path (requires async DB)
        query_concepts = self._extract_query_concepts(query)

        # Find relevant starting nodes in patient's graph
        start_nodes = self._find_matching_nodes(patient_id, query_concepts)

        # Traverse graph from starting nodes (skip if doc_only mode)
        graph_paths: list[GraphPath] = []
        if retrieval_mode != "doc_only":
            graph_paths = self._traverse_graph(
                patient_id=patient_id,
                start_nodes=start_nodes,
                query_concepts=query_concepts,
                max_hops=max_hops,
                max_paths=max_paths,
                assertion_mode=assertion_mode,
                temporal_mode=temporal_mode,
            )

        # Causal reasoning: augment paths for causal queries
        if retrieval_mode != "doc_only":
            causal_paths = self._get_causal_context(query, query_concepts)
            if causal_paths:
                graph_paths = graph_paths + causal_paths

        # Get temporal context if requested (skip if no_temporal mode)
        temporal_context = None
        if include_temporal and temporal_mode != "no_temporal":
            temporal_context = self._get_temporal_context(
                patient_id=patient_id,
                time_point=time_point,
            )

        # Get applicable policy constraints if requested
        policy_constraints: list[dict[str, Any]] = []
        if include_policies and retrieval_mode == "graph_plus_doc_plus_guidelines":
            policy_constraints = self._get_policy_constraints(
                patient_id=patient_id,
                query_concepts=query_concepts,
            )

        # P1-011: Real document retrieval with status tracking (skip if graph_only mode)
        retrieved_documents: list[dict[str, Any]] = []
        source_status = SourceRetrievalStatus.UNAVAILABLE
        if retrieval_mode != "graph_only":
            retrieved_documents, source_status = self._retrieve_documents_sync(
                query=query,
                patient_id=patient_id,
                query_concepts=query_concepts,
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
            source_retrieval_status=source_status,
        )

    # ------------------------------------------------------------------
    # Step 1: Hybrid concept extraction (NLP + OMOP + label fallback)
    # ------------------------------------------------------------------

    def _extract_query_concepts(self, query: str) -> list[QueryConcept]:
        """Extract clinical concepts from query text via hybrid pipeline.

        Tier 1: NLP entity extraction using ClinicalNLPEntityService
        Tier 3: Quoted-term extraction (always applied)
        Note: Tier 2 (OMOP lookup) is applied asynchronously via
              _enrich_concepts_with_omop_async in the async path.
        """
        concepts: list[QueryConcept] = []
        seen_texts: set[str] = set()

        # Tier 1: NLP entity extraction
        try:
            from app.services.nlp_entity import get_nlp_entity_service

            nlp_service = get_nlp_entity_service()
            result = nlp_service.extract_entities(query)
            for entity in result.entities:
                text_lower = entity.text.lower()
                if text_lower not in seen_texts:
                    seen_texts.add(text_lower)
                    concepts.append(QueryConcept(
                        text=entity.text,
                        entity_type=entity.entity_type.value,
                        confidence=entity.confidence,
                    ))
        except Exception as exc:
            logger.debug("NLP entity extraction unavailable, falling back: %s", exc)

        # Tier 3: Quoted-term extraction
        quoted = re.findall(r'"([^"]+)"', query)
        for term in quoted:
            term_lower = term.lower()
            if term_lower not in seen_texts:
                seen_texts.add(term_lower)
                concepts.append(QueryConcept(text=term, confidence=0.9))

        return concepts

    async def _enrich_concepts_with_omop_async(
        self,
        concepts: list[QueryConcept],
    ) -> list[QueryConcept]:
        """Tier 2: Enrich QueryConcepts with OMOP concept IDs via async DB lookup."""
        if not concepts:
            return concepts

        try:
            from app.services.concept_lookup import lookup_concept_cached

            for concept in concepts:
                if concept.omop_concept_id is not None:
                    continue
                domain = _ENTITY_TYPE_TO_DOMAIN.get(concept.entity_type or "")
                match = await lookup_concept_cached(
                    self._session, concept.text, domain
                )
                if match:
                    concept.omop_concept_id = match.concept_id
        except Exception as exc:
            logger.debug("OMOP concept enrichment failed: %s", exc)

        return concepts

    # ------------------------------------------------------------------
    # Node matching (updated for QueryConcept)
    # ------------------------------------------------------------------

    def _find_matching_nodes(
        self,
        patient_id: str,
        concepts: list[QueryConcept],
    ) -> list[KGNode]:
        """Find nodes in patient's graph matching query concepts.

        Patient nodes still have patient_id set, so we query directly.
        Shared concept nodes (patient_id=NULL) are found via edge-join
        since edges always carry patient_id.

        When a QueryConcept has omop_concept_id, match directly on
        KGNode.omop_concept_id for exact hits.
        """
        if not concepts:
            # Return patient node as starting point (patient nodes still have patient_id)
            stmt = (
                select(KGNode)
                .where(KGNode.patient_id == patient_id)
                .where(KGNode.node_type == NodeType.PATIENT)
            )
            result = self._session.execute(stmt)
            patient_node = result.scalar_one_or_none()
            return [patient_node] if patient_node else []

        # Try OMOP ID exact matching first
        omop_ids = [c.omop_concept_id for c in concepts if c.omop_concept_id]
        omop_matched_nodes: list[KGNode] = []
        omop_matched_ids: set = set()
        if omop_ids:
            stmt = (
                select(KGNode)
                .join(KGEdge, or_(KGEdge.target_node_id == KGNode.id, KGEdge.source_node_id == KGNode.id))
                .where(KGEdge.patient_id == patient_id)
                .where(KGNode.omop_concept_id.in_(omop_ids))
                .distinct()
            )
            result = self._session.execute(stmt)
            omop_matched_nodes = list(result.scalars().all())
            omop_matched_ids = {n.id for n in omop_matched_nodes}

        # Fall back to label matching for concepts without OMOP IDs
        label_concepts = [c for c in concepts if not c.omop_concept_id]
        label_matched_nodes: list[KGNode] = []
        if label_concepts:
            stmt = (
                select(KGNode)
                .join(KGEdge, or_(KGEdge.target_node_id == KGNode.id, KGEdge.source_node_id == KGNode.id))
                .where(KGEdge.patient_id == patient_id)
                .distinct()
            )
            result = self._session.execute(stmt)
            nodes = result.scalars().all()

            for node in nodes:
                if node.id in omop_matched_ids:
                    continue
                label_lower = node.label.lower()
                for concept in label_concepts:
                    if concept.text.lower() in label_lower:
                        label_matched_nodes.append(node)
                        break

        # OMOP matches first (higher precision), then label matches
        return (omop_matched_nodes + label_matched_nodes)[:20]

    async def _find_matching_nodes_async(
        self,
        patient_id: str,
        concepts: list[QueryConcept],
    ) -> list[KGNode]:
        """Find nodes in patient's graph matching query concepts (async version).

        Patient nodes still have patient_id set, so we query directly.
        Shared concept nodes (patient_id=NULL) are found via edge-join
        since edges always carry patient_id.

        When a QueryConcept has omop_concept_id, match directly on
        KGNode.omop_concept_id for exact hits.
        """
        if not concepts:
            # Return patient node as starting point (patient nodes still have patient_id)
            stmt = (
                select(KGNode)
                .where(KGNode.patient_id == patient_id)
                .where(KGNode.node_type == NodeType.PATIENT)
            )
            result = await self._session.execute(stmt)
            patient_node = result.scalar_one_or_none()
            return [patient_node] if patient_node else []

        # Try OMOP ID exact matching first
        omop_ids = [c.omop_concept_id for c in concepts if c.omop_concept_id]
        omop_matched_nodes: list[KGNode] = []
        omop_matched_ids: set = set()
        if omop_ids:
            stmt = (
                select(KGNode)
                .join(KGEdge, or_(KGEdge.target_node_id == KGNode.id, KGEdge.source_node_id == KGNode.id))
                .where(KGEdge.patient_id == patient_id)
                .where(KGNode.omop_concept_id.in_(omop_ids))
                .distinct()
            )
            result = await self._session.execute(stmt)
            omop_matched_nodes = list(result.scalars().all())
            omop_matched_ids = {n.id for n in omop_matched_nodes}

        # Fall back to label matching for concepts without OMOP IDs
        label_concepts = [c for c in concepts if not c.omop_concept_id]
        label_matched_nodes: list[KGNode] = []
        if label_concepts:
            stmt = (
                select(KGNode)
                .join(KGEdge, or_(KGEdge.target_node_id == KGNode.id, KGEdge.source_node_id == KGNode.id))
                .where(KGEdge.patient_id == patient_id)
                .distinct()
            )
            result = await self._session.execute(stmt)
            nodes = result.scalars().all()

            for node in nodes:
                if node.id in omop_matched_ids:
                    continue
                label_lower = node.label.lower()
                for concept in label_concepts:
                    if concept.text.lower() in label_lower:
                        label_matched_nodes.append(node)
                        break

        # OMOP matches first (higher precision), then label matches
        return (omop_matched_nodes + label_matched_nodes)[:20]

    # ------------------------------------------------------------------
    # Graph traversal (Steps 4+5: confidence scoring + bidirectional)
    # ------------------------------------------------------------------

    async def _traverse_graph_async(
        self,
        patient_id: str,
        start_nodes: list[KGNode],
        query_concepts: list[QueryConcept],
        max_hops: int,
        max_paths: int,
        assertion_mode: str = "full",
        temporal_mode: str = "full_bitemporal",
    ) -> list[GraphPath]:
        """Traverse graph from starting nodes to find relevant paths (async version)."""
        # Check traversal cache
        start_node_ids = [str(n.id) for n in start_nodes]
        concept_ids = [c.omop_concept_id for c in query_concepts if c.omop_concept_id]
        cache_key = _traversal_cache_key(
            patient_id, start_node_ids, concept_ids, max_hops, assertion_mode, temporal_mode,
        )
        cached = _traversal_cache_get(cache_key)
        if cached is not None:
            return cached[:max_paths]

        paths = []

        for start_node in start_nodes[:5]:  # Limit starting points
            node_paths = await self._bfs_traverse_async(
                patient_id=patient_id,
                start_node=start_node,
                query_concepts=query_concepts,
                max_hops=max_hops,
                assertion_mode=assertion_mode,
                temporal_mode=temporal_mode,
            )
            paths.extend(node_paths)

            if len(paths) >= max_paths:
                break

        _traversal_cache_put(cache_key, paths[:max_paths])
        return paths[:max_paths]

    async def _bfs_traverse_async(
        self,
        patient_id: str,
        start_node: KGNode,
        query_concepts: list[QueryConcept],
        max_hops: int,
        assertion_mode: str = "full",
        temporal_mode: str = "full_bitemporal",
    ) -> list[GraphPath]:
        """BFS traversal from a starting node (async, bidirectional, confidence-weighted)."""
        paths = []

        # Step 5: Get both outgoing and incoming edges
        outgoing_stmt = (
            select(KGEdge)
            .where(KGEdge.source_node_id == start_node.id)
            .where(KGEdge.patient_id == patient_id)
        )
        incoming_stmt = (
            select(KGEdge)
            .where(KGEdge.target_node_id == start_node.id)
            .where(KGEdge.patient_id == patient_id)
        )
        out_result = await self._session.execute(outgoing_stmt)
        in_result = await self._session.execute(incoming_stmt)

        outgoing_edges = list(out_result.scalars().all())
        incoming_edges = list(in_result.scalars().all())

        # Step 4: Filter and score edges (with mode parameters for ablation)
        all_edges = _score_and_filter_edges(
            outgoing_edges + incoming_edges, query_concepts,
            assertion_mode=assertion_mode, temporal_mode=temporal_mode,
        )
        all_edges = all_edges[:10]

        # Batch-fetch all neighbor nodes in one query (avoids N+1)
        neighbor_ids = set()
        for edge in all_edges:
            if edge.source_node_id != start_node.id:
                neighbor_ids.add(edge.source_node_id)
            if edge.target_node_id != start_node.id:
                neighbor_ids.add(edge.target_node_id)

        neighbor_map: dict = {}
        if neighbor_ids:
            neighbor_stmt = select(KGNode).where(KGNode.id.in_(list(neighbor_ids)))
            neighbor_result = await self._session.execute(neighbor_stmt)
            neighbor_map = {n.id: n for n in neighbor_result.scalars().all()}

        for edge in all_edges:
            # Determine the "other" node (neighbor)
            if edge.source_node_id == start_node.id:
                neighbor_node = neighbor_map.get(edge.target_node_id)
            else:
                neighbor_node = neighbor_map.get(edge.source_node_id)

            if neighbor_node:
                edge_props = edge.properties or {}
                path = GraphPath(
                    nodes=[
                        {"id": str(start_node.id), "label": start_node.label, "type": start_node.node_type.value},
                        {"id": str(neighbor_node.id), "label": neighbor_node.label, "type": neighbor_node.node_type.value},
                    ],
                    edges=[
                        {
                            "edge_type": edge.edge_type.value,
                            "confidence": edge.temporal_confidence or 1.0,
                            "temporality": edge.temporality,
                            "assertion": edge_props.get("assertion", "present"),
                            "is_negated": edge_props.get("is_negated", False),
                            "is_uncertain": edge_props.get("is_uncertain", False),
                            "event_date": edge.event_date.isoformat() if edge.event_date else None,
                        }
                    ],
                    path_type=self._classify_path_type(start_node, edge, neighbor_node),
                    confidence=edge.temporal_confidence or 1.0,
                )
                paths.append(path)

                # Continue traversal if more hops allowed
                if max_hops > 1:
                    deeper_paths = await self._bfs_traverse_async(
                        patient_id=patient_id,
                        start_node=neighbor_node,
                        query_concepts=query_concepts,
                        max_hops=max_hops - 1,
                        assertion_mode=assertion_mode,
                        temporal_mode=temporal_mode,
                    )
                    for deeper_path in deeper_paths[:3]:
                        combined = GraphPath(
                            nodes=path.nodes + deeper_path.nodes[1:],
                            edges=path.edges + deeper_path.edges,
                            path_type=path.path_type,
                            confidence=min(path.confidence, deeper_path.confidence),
                        )
                        paths.append(combined)

        return paths

    def _traverse_graph(
        self,
        patient_id: str,
        start_nodes: list[KGNode],
        query_concepts: list[QueryConcept],
        max_hops: int,
        max_paths: int,
        assertion_mode: str = "full",
        temporal_mode: str = "full_bitemporal",
    ) -> list[GraphPath]:
        """Traverse graph from starting nodes to find relevant paths.

        For 2+ hop queries, uses the PG-native query router which traverses
        both kg_edges and concept_relationships (20M+ vocabulary relationships)
        in a single CTE. Falls back to PG BFS on failure.
        """
        # Check traversal cache
        start_node_ids = [str(n.id) for n in start_nodes]
        concept_ids = [c.omop_concept_id for c in query_concepts if c.omop_concept_id]
        cache_key = _traversal_cache_key(
            patient_id, start_node_ids, concept_ids, max_hops, assertion_mode, temporal_mode,
        )
        cached = _traversal_cache_get(cache_key)
        if cached is not None:
            return cached[:max_paths]

        if max_hops >= 2:
            try:
                from app.services.neo4j_query_router import GraphQueryRouter, MultiHopQuery

                start_concept_ids = [
                    n.omop_concept_id for n in start_nodes
                    if n.omop_concept_id
                ]
                if start_concept_ids:
                    router = GraphQueryRouter(self._session)
                    query = MultiHopQuery(
                        patient_id=patient_id,
                        start_concept_ids=start_concept_ids,
                        max_hops=max_hops,
                        max_paths=max_paths,
                        min_confidence=MIN_TRAVERSAL_CONFIDENCE,
                    )
                    router_paths = router.execute_multi_hop(query)
                    result = [
                        GraphPath(
                            nodes=[
                                {"id": n.node_id, "label": n.label, "type": n.node_type}
                                for n in rp.nodes
                            ],
                            edges=[
                                {
                                    "edge_type": e.edge_type,
                                    "confidence": e.confidence,
                                    "temporality": e.temporality,
                                    "assertion": getattr(e, "assertion", "present") or "present",
                                    "is_negated": getattr(e, "is_negated", False),
                                    "is_uncertain": getattr(e, "is_uncertain", False),
                                    "event_date": e.event_date,
                                }
                                for e in rp.edges
                            ],
                            path_type="multi_hop",
                            confidence=rp.path_confidence,
                        )
                        for rp in router_paths
                    ][:max_paths]
                    _traversal_cache_put(cache_key, result)
                    return result
            except Exception as e:
                logger.debug("Query router failed, using PG BFS: %s", e)

        paths = []

        for start_node in start_nodes[:5]:  # Limit starting points
            node_paths = self._bfs_traverse(
                patient_id=patient_id,
                start_node=start_node,
                query_concepts=query_concepts,
                max_hops=max_hops,
                assertion_mode=assertion_mode,
                temporal_mode=temporal_mode,
            )
            paths.extend(node_paths)

            if len(paths) >= max_paths:
                break

        _traversal_cache_put(cache_key, paths[:max_paths])
        return paths[:max_paths]

    def _bfs_traverse(
        self,
        patient_id: str,
        start_node: KGNode,
        query_concepts: list[QueryConcept],
        max_hops: int,
        assertion_mode: str = "full",
        temporal_mode: str = "full_bitemporal",
    ) -> list[GraphPath]:
        """BFS traversal from a starting node (sync, bidirectional, confidence-weighted)."""
        paths = []

        # Step 5: Get both outgoing and incoming edges
        outgoing_stmt = (
            select(KGEdge)
            .where(KGEdge.source_node_id == start_node.id)
            .where(KGEdge.patient_id == patient_id)
        )
        incoming_stmt = (
            select(KGEdge)
            .where(KGEdge.target_node_id == start_node.id)
            .where(KGEdge.patient_id == patient_id)
        )
        out_result = self._session.execute(outgoing_stmt)
        in_result = self._session.execute(incoming_stmt)

        outgoing_edges = list(out_result.scalars().all())
        incoming_edges = list(in_result.scalars().all())

        # Step 4: Filter and score edges (with mode parameters for ablation)
        all_edges = _score_and_filter_edges(
            outgoing_edges + incoming_edges, query_concepts,
            assertion_mode=assertion_mode, temporal_mode=temporal_mode,
        )
        all_edges = all_edges[:10]

        # Batch-fetch all neighbor nodes in one query (avoids N+1)
        neighbor_ids = set()
        for edge in all_edges:
            if edge.source_node_id != start_node.id:
                neighbor_ids.add(edge.source_node_id)
            if edge.target_node_id != start_node.id:
                neighbor_ids.add(edge.target_node_id)

        neighbor_map: dict = {}
        if neighbor_ids:
            neighbor_stmt = select(KGNode).where(KGNode.id.in_(list(neighbor_ids)))
            neighbor_result = self._session.execute(neighbor_stmt)
            neighbor_map = {n.id: n for n in neighbor_result.scalars().all()}

        for edge in all_edges:
            # Determine the "other" node (neighbor)
            if edge.source_node_id == start_node.id:
                neighbor_node = neighbor_map.get(edge.target_node_id)
            else:
                neighbor_node = neighbor_map.get(edge.source_node_id)

            if neighbor_node:
                edge_props = edge.properties or {}
                path = GraphPath(
                    nodes=[
                        {"id": str(start_node.id), "label": start_node.label, "type": start_node.node_type.value},
                        {"id": str(neighbor_node.id), "label": neighbor_node.label, "type": neighbor_node.node_type.value},
                    ],
                    edges=[
                        {
                            "edge_type": edge.edge_type.value,
                            "confidence": edge.temporal_confidence or 1.0,
                            "temporality": edge.temporality,
                            "assertion": edge_props.get("assertion", "present"),
                            "is_negated": edge_props.get("is_negated", False),
                            "is_uncertain": edge_props.get("is_uncertain", False),
                            "event_date": edge.event_date.isoformat() if edge.event_date else None,
                        }
                    ],
                    path_type=self._classify_path_type(start_node, edge, neighbor_node),
                    confidence=edge.temporal_confidence or 1.0,
                )
                paths.append(path)

                # Continue traversal if more hops allowed
                if max_hops > 1:
                    deeper_paths = self._bfs_traverse(
                        patient_id=patient_id,
                        start_node=neighbor_node,
                        query_concepts=query_concepts,
                        max_hops=max_hops - 1,
                        assertion_mode=assertion_mode,
                        temporal_mode=temporal_mode,
                    )
                    for deeper_path in deeper_paths[:3]:
                        combined = GraphPath(
                            nodes=path.nodes + deeper_path.nodes[1:],
                            edges=path.edges + deeper_path.edges,
                            path_type=path.path_type,
                            confidence=min(path.confidence, deeper_path.confidence),
                        )
                        paths.append(combined)

        return paths

    def _get_causal_context(
        self,
        query: str,
        query_concepts: list[QueryConcept],
    ) -> list[GraphPath]:
        """Get causal reasoning context when query contains causal language.

        Only invoked when query contains causal language (e.g., "caused by",
        "side effect", "treatment for"). Results are converted to GraphPath
        for uniform context assembly.
        """
        if not _CAUSAL_PATTERNS.search(query):
            return []

        try:
            from app.services.causal_reasoning_service import (
                CausalQuery,
                get_causal_reasoning_service,
            )

            causal_service = get_causal_reasoning_service()

            # Use first concept as start, second as end (if available)
            concept_texts = [c.text for c in query_concepts if c.text]
            if not concept_texts:
                return []

            causal_query = CausalQuery(
                start_concept=concept_texts[0],
                end_concept=concept_texts[1] if len(concept_texts) > 1 else None,
                max_chain_length=4,
                min_confidence=MIN_TRAVERSAL_CONFIDENCE,
            )

            # CausalReasoningService is async; use mock data path synchronously
            chains = causal_service._mock_causal_chains(causal_query)

            # Convert CausalChain -> GraphPath
            causal_paths: list[GraphPath] = []
            for chain in chains:
                if not chain.links:
                    continue
                nodes = [
                    {"id": chain.links[0].source_cui, "label": chain.links[0].source_name, "type": "concept"}
                ]
                edges_list = []
                for link in chain.links:
                    nodes.append({"id": link.target_cui, "label": link.target_name, "type": "concept"})
                    edges_list.append({
                        "edge_type": link.relation_type.value,
                        "confidence": link.confidence,
                        "temporality": None,
                        "event_date": None,
                    })

                causal_paths.append(GraphPath(
                    nodes=nodes,
                    edges=edges_list,
                    path_type="causal_chain",
                    confidence=chain.total_confidence,
                ))

            return causal_paths

        except Exception as e:
            logger.debug("Causal reasoning integration failed: %s", e)
            return []

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

    # ------------------------------------------------------------------
    # Step 2: Temporal context (N+1 fix — batch node fetch)
    # ------------------------------------------------------------------

    async def _get_temporal_context_async(
        self,
        patient_id: str,
        time_point: datetime | None,
    ) -> TemporalContext:
        """Get temporal context from patient's graph (async, batch-optimized)."""
        # Get all edges with temporal data
        stmt = (
            select(KGEdge)
            .where(KGEdge.patient_id == patient_id)
            .where(KGEdge.event_date.isnot(None))
            .order_by(KGEdge.event_date.desc())
        )
        result = await self._session.execute(stmt)
        edges = result.scalars().all()
        edges = edges[:50]

        # Batch-fetch all target nodes in one query (fixes N+1)
        target_ids = [e.target_node_id for e in edges]
        if target_ids:
            target_stmt = select(KGNode).where(KGNode.id.in_(target_ids))
            target_result = await self._session.execute(target_stmt)
            target_map = {n.id: n for n in target_result.scalars().all()}
        else:
            target_map = {}

        # Build timeline
        timeline = []
        current_state = {}
        historical_state = {}

        for edge in edges:
            target = target_map.get(edge.target_node_id)

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
        conflicts: list[str] = []

        return TemporalContext(
            event_timeline=timeline,
            temporal_conflicts=conflicts,
            current_state=current_state,
            historical_state=historical_state,
        )

    def _get_temporal_context(
        self,
        patient_id: str,
        time_point: datetime | None,
    ) -> TemporalContext:
        """Get temporal context from patient's graph (sync, batch-optimized)."""
        # Get all edges with temporal data
        stmt = (
            select(KGEdge)
            .where(KGEdge.patient_id == patient_id)
            .where(KGEdge.event_date.isnot(None))
            .order_by(KGEdge.event_date.desc())
        )
        result = self._session.execute(stmt)
        edges = result.scalars().all()
        edges = edges[:50]

        # Batch-fetch all target nodes in one query (fixes N+1)
        target_ids = [e.target_node_id for e in edges]
        if target_ids:
            target_stmt = select(KGNode).where(KGNode.id.in_(target_ids))
            target_result = self._session.execute(target_stmt)
            target_map = {n.id: n for n in target_result.scalars().all()}
        else:
            target_map = {}

        # Build timeline
        timeline = []
        current_state = {}
        historical_state = {}

        for edge in edges:
            target = target_map.get(edge.target_node_id)

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
        conflicts: list[str] = []

        return TemporalContext(
            event_timeline=timeline,
            temporal_conflicts=conflicts,
            current_state=current_state,
            historical_state=historical_state,
        )

    # ------------------------------------------------------------------
    # Step 3: Policy constraints via GuidelineRAGService
    # ------------------------------------------------------------------

    def _get_policy_constraints(
        self,
        patient_id: str,
        query_concepts: list[QueryConcept],
    ) -> list[dict[str, Any]]:
        """Get applicable policy constraints from clinical guidelines (sync)."""
        return self._build_policy_constraints(patient_id, query_concepts)

    async def _get_policy_constraints_async(
        self,
        patient_id: str,
        query_concepts: list[QueryConcept],
    ) -> list[dict[str, Any]]:
        """Get applicable policy constraints from clinical guidelines (async)."""
        return self._build_policy_constraints(patient_id, query_concepts)

    def _build_policy_constraints(
        self,
        patient_id: str,
        query_concepts: list[QueryConcept],
    ) -> list[dict[str, Any]]:
        """Core policy constraint logic shared by sync/async paths.

        Uses GuidelineRAGService (which is synchronous) to retrieve
        applicable clinical guidelines based on query concepts.
        """
        if not query_concepts:
            return []

        try:
            from app.services.guideline_rag_service import get_guideline_rag_service

            guideline_service = get_guideline_rag_service()
            if not guideline_service.is_loaded:
                return []

            # Separate concepts by type for patient context
            patient_conditions = [
                c.text for c in query_concepts
                if c.entity_type in ("diagnosis", "symptom")
            ]
            patient_medications = [
                c.text for c in query_concepts
                if c.entity_type == "medication"
            ]

            query_text = " ".join(c.text for c in query_concepts)
            citations = guideline_service.search(
                query=query_text,
                patient_conditions=patient_conditions or None,
                patient_medications=patient_medications or None,
                top_k=2,
                min_score=0.5,
            )

            constraints: list[dict[str, Any]] = []
            for citation in citations:
                section = citation.section
                constraints.append({
                    "rule_id": section.section_id,
                    "description": (
                        f"[{section.guideline}] {section.recommendation_text}"
                    ),
                    "strength": (
                        section.recommendation_level or section.evidence_grade
                    ),
                    "relevance_score": citation.score,
                })

            return constraints

        except Exception as exc:
            logger.debug("Guideline RAG lookup failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Document retrieval (unchanged logic, updated type hints)
    # ------------------------------------------------------------------

    async def _retrieve_documents_async(
        self,
        query: str,
        patient_id: str,
        query_concepts: list[QueryConcept] | None = None,
    ) -> tuple[list[dict[str, Any]], str]:
        """Retrieve real patient documents using FTS with Python fallback (async)."""
        try:
            # Build search terms from query + concepts
            search_terms = query
            if query_concepts:
                concept_texts = [
                    c.text if isinstance(c, QueryConcept) else str(c)
                    for c in query_concepts
                ]
                search_terms = " ".join([query] + [t for t in concept_texts if t])

            # Try FTS query first
            try:
                from sqlalchemy import func as sa_func, text as sa_text
                fts_query = sa_func.plainto_tsquery("english", search_terms)
                stmt = (
                    select(
                        Document,
                        sa_func.ts_rank(Document.search_vector, fts_query).label("rank"),
                    )
                    .where(Document.patient_id == patient_id)
                    .where(Document.search_vector.op("@@")(fts_query))
                    .order_by(sa_text("rank DESC"))
                    .limit(5)
                )
                result = await self._session.execute(stmt)
                rows = result.all()
                if rows:
                    formatted = []
                    for doc, rank in rows:
                        content = doc.text[:500] if doc.text else ""
                        formatted.append({
                            "source": f"document:{doc.id}",
                            "source_available": True,
                            "note_type": doc.note_type,
                            "patient_id": doc.patient_id,
                            "content": content,
                            "relevance_score": round(float(rank), 4),
                        })
                    return formatted, SourceRetrievalStatus.FULL
            except Exception as fts_exc:
                logger.debug("FTS query failed, falling back to Python scoring: %s", fts_exc)

            # Fallback: load all docs and score in Python
            stmt = select(Document).where(Document.patient_id == patient_id)
            result = await self._session.execute(stmt)
            docs = list(result.scalars().all())

            if not docs:
                return [], SourceRetrievalStatus.UNAVAILABLE

            return self._score_and_format_docs(docs, query, query_concepts)

        except Exception as exc:
            logger.warning("Document retrieval failed for patient %s: %s", patient_id, exc)
            return [], SourceRetrievalStatus.UNAVAILABLE

    def _retrieve_documents_sync(
        self,
        query: str,
        patient_id: str,
        query_concepts: list[QueryConcept] | None = None,
    ) -> tuple[list[dict[str, Any]], str]:
        """Retrieve real patient documents using FTS with Python fallback (sync)."""
        try:
            # Build search terms from query + concepts
            search_terms = query
            if query_concepts:
                concept_texts = [
                    c.text if isinstance(c, QueryConcept) else str(c)
                    for c in query_concepts
                ]
                search_terms = " ".join([query] + [t for t in concept_texts if t])

            # Try FTS query first
            try:
                from sqlalchemy import func as sa_func, text as sa_text
                fts_query = sa_func.plainto_tsquery("english", search_terms)
                stmt = (
                    select(
                        Document,
                        sa_func.ts_rank(Document.search_vector, fts_query).label("rank"),
                    )
                    .where(Document.patient_id == patient_id)
                    .where(Document.search_vector.op("@@")(fts_query))
                    .order_by(sa_text("rank DESC"))
                    .limit(5)
                )
                result = self._session.execute(stmt)
                rows = result.all()
                if rows:
                    formatted = []
                    for doc, rank in rows:
                        content = doc.text[:500] if doc.text else ""
                        formatted.append({
                            "source": f"document:{doc.id}",
                            "source_available": True,
                            "note_type": doc.note_type,
                            "patient_id": doc.patient_id,
                            "content": content,
                            "relevance_score": round(float(rank), 4),
                        })
                    return formatted, SourceRetrievalStatus.FULL
            except Exception as fts_exc:
                logger.debug("FTS query failed, falling back to Python scoring: %s", fts_exc)

            # Fallback: load all docs and score in Python
            stmt = select(Document).where(Document.patient_id == patient_id)
            result = self._session.execute(stmt)
            docs = list(result.scalars().all())

            if not docs:
                return [], SourceRetrievalStatus.UNAVAILABLE

            return self._score_and_format_docs(docs, query, query_concepts)

        except Exception as exc:
            logger.warning("Document retrieval failed for patient %s: %s", patient_id, exc)
            return [], SourceRetrievalStatus.UNAVAILABLE

    def _score_and_format_docs(
        self,
        docs: list[Any],
        query: str,
        query_concepts: list[QueryConcept] | None = None,
    ) -> tuple[list[dict[str, Any]], str]:
        """Score documents by relevance and return with retrieval status.

        Returns:
            Tuple of (formatted docs, source_retrieval_status).
        """
        concept_texts: list[str] = []
        if query_concepts:
            for c in query_concepts:
                concept_texts.append(c.text if isinstance(c, QueryConcept) else str(c))
        query_lower = query.lower()
        scored: list[tuple[float, Any]] = []

        for doc in docs:
            try:
                text_lower = doc.text.lower() if doc.text else ""
                # Score: keyword overlap + concept overlap
                score = 0.0
                query_words = set(query_lower.split())
                for word in query_words:
                    if len(word) > 2 and word in text_lower:
                        score += 1.0
                for concept in concept_texts:
                    if concept.lower() in text_lower:
                        score += 2.0
                scored.append((score, doc))
            except Exception:
                # Individual doc scoring failure doesn't invalidate batch
                continue

        if not scored:
            return [], SourceRetrievalStatus.UNAVAILABLE

        # Sort by score descending, take top 5
        scored.sort(key=lambda x: x[0], reverse=True)
        top_docs = scored[:5]

        formatted: list[dict[str, Any]] = []
        any_failed = False
        for score, doc in top_docs:
            if score <= 0:
                continue
            try:
                content = doc.text[:500] if doc.text else ""
                formatted.append({
                    "source": f"document:{doc.id}",
                    "source_available": True,
                    "note_type": doc.note_type,
                    "patient_id": doc.patient_id,
                    "content": content,
                    "relevance_score": round(score, 2),
                })
            except Exception as exc:
                try:
                    doc_id = doc.id
                except Exception:
                    doc_id = "unknown"
                logger.warning("P1-011: Failed to format doc %s: %s", doc_id, exc)
                formatted.append({
                    "source": f"document:{doc_id}",
                    "source_available": False,
                    "content": "",
                    "relevance_score": 0.0,
                })
                any_failed = True

        if not formatted:
            return [], SourceRetrievalStatus.UNAVAILABLE

        if any_failed:
            return formatted, SourceRetrievalStatus.PARTIAL

        return formatted, SourceRetrievalStatus.FULL


# ------------------------------------------------------------------
# Step 4: Edge scoring and filtering (module-level helper)
# ------------------------------------------------------------------

def _score_and_filter_edges(
    edges: list[KGEdge],
    query_concepts: list[QueryConcept],
    assertion_mode: str = "full",
    temporal_mode: str = "full_bitemporal",
) -> list[KGEdge]:
    """Score edges by confidence and query relevance, filter low-confidence.

    Scoring criteria:
    1. Base confidence (temporal_confidence)
    2. Query-relevant edge types get a boost
    3. Current temporality preferred over historical (unless temporal_mode="no_temporal")
    4. Assertion-based scoring (unless assertion_mode="none")
    5. Edges below MIN_TRAVERSAL_CONFIDENCE are pruned

    Args:
        edges: Edges to score.
        query_concepts: Query concepts for relevance boosting.
        assertion_mode: "full" | "extracted_only" | "none".
            - "full": Apply assertion-based score modifiers.
            - "extracted_only": Include assertion in metadata but don't modify scores.
            - "none": Ignore assertion entirely.
        temporal_mode: "full_bitemporal" | "timestamps_only" | "no_temporal".
            - "full_bitemporal": Full temporal scoring including temporality boost.
            - "timestamps_only": Use event_date but skip temporality enum boost.
            - "no_temporal": No temporal scoring at all.
    """
    # Collect preferred edge types from all query concepts
    preferred_types: set[str] = set()
    for concept in query_concepts:
        if concept.entity_type:
            preferred_types.update(
                _ENTITY_TYPE_TO_PREFERRED_EDGES.get(concept.entity_type, set())
            )

    scored: list[tuple[float, KGEdge]] = []
    for edge in edges:
        confidence = edge.temporal_confidence or 1.0

        # Prune low-confidence edges
        if confidence < MIN_TRAVERSAL_CONFIDENCE:
            continue

        score = confidence

        # Boost query-relevant edge types
        if preferred_types and edge.edge_type.value in preferred_types:
            score += 0.2

        # Temporal scoring (skip if no_temporal mode)
        if temporal_mode != "no_temporal":
            if edge.temporality == "current":
                score += 0.1

        # Assertion-based scoring (only in "full" mode)
        if assertion_mode == "full":
            edge_props = edge.properties or {}
            assertion = edge_props.get("assertion", "present")
            if assertion == "absent":
                score *= 0.5  # Negated conditions significantly less relevant
            elif assertion == "possible":
                score *= 0.75  # Uncertain conditions moderately less relevant
            elif assertion in ("hypothetical", "conditional"):
                score *= 0.6  # Hypothetical/conditional
            elif assertion == "family_history":
                score *= 0.7  # Family history, not patient's own
            elif assertion == "historical":
                score *= 0.8  # Historical, less current relevance
            # "present" gets no penalty (default)

        scored.append((score, edge))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)
    return [edge for _, edge in scored]


def get_graph_augmented_rag_service(
    session: Union[Session, AsyncSession]
) -> GraphAugmentedRAGService:
    """Factory function to create GraphAugmentedRAGService.

    Args:
        session: SQLAlchemy database session (sync or async).

    Returns:
        GraphAugmentedRAGService instance configured for the session type.
    """
    return GraphAugmentedRAGService(session)
