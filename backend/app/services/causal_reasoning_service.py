"""
Causal Reasoning Service for Clinical Knowledge Graph.

Implements causal inference patterns for clinical decision support:
- Causal chain discovery (A causes B causes C)
- Treatment-outcome reasoning
- Adverse event pathway analysis
- Counterfactual reasoning support

Based on:
- Clinical causal inference literature
- Drug-disease-outcome pathways from UMLS
- Temporal causality patterns
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CausalRelationType(str, Enum):
    """Types of causal relationships in clinical domain."""

    CAUSES = "CAUSES"  # Direct causation
    MAY_CAUSE = "MAY_CAUSE"  # Probabilistic causation
    PREVENTS = "PREVENTS"  # Preventive effect
    TREATS = "TREATS"  # Therapeutic effect
    EXACERBATES = "EXACERBATES"  # Worsening effect
    LEADS_TO = "LEADS_TO"  # Temporal progression
    ASSOCIATED_WITH = "ASSOCIATED_WITH"  # Correlation (not causal)
    COMPLICATION_OF = "COMPLICATION_OF"  # Complication relationship
    ADVERSE_EFFECT_OF = "ADVERSE_EFFECT_OF"  # Drug adverse effect
    CONTRAINDICATED_BY = "CONTRAINDICATED_BY"  # Contraindication


class TemporalOrder(str, Enum):
    """Temporal ordering for causal inference."""

    BEFORE = "before"
    DURING = "during"
    AFTER = "after"
    CONCURRENT = "concurrent"
    UNKNOWN = "unknown"


@dataclass
class CausalLink:
    """A single causal link between two concepts."""

    source_cui: str
    source_name: str
    target_cui: str
    target_name: str
    relation_type: CausalRelationType
    confidence: float = 1.0
    evidence_count: int = 1
    temporal_order: TemporalOrder = TemporalOrder.BEFORE
    mechanism: str | None = None  # Biological/clinical mechanism
    sources: list[str] = field(default_factory=list)


@dataclass
class CausalChain:
    """A chain of causal relationships."""

    chain_id: str
    links: list[CausalLink]
    start_concept: str
    end_concept: str
    total_confidence: float
    chain_length: int
    pathway_type: str  # treatment, adverse_event, progression, etc.
    mechanisms: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        """Generate human-readable summary of the chain."""
        if not self.links:
            return "Empty chain"

        parts = [self.links[0].source_name]
        for link in self.links:
            parts.append(f"-[{link.relation_type.value}]->")
            parts.append(link.target_name)

        return " ".join(parts)


@dataclass
class CausalQuery:
    """Query parameters for causal reasoning."""

    start_concept: str  # CUI or name
    end_concept: str | None = None  # Target (None = explore all)
    relation_types: list[CausalRelationType] | None = None
    max_chain_length: int = 5
    min_confidence: float = 0.5
    require_mechanism: bool = False
    temporal_constraint: TemporalOrder | None = None


@dataclass
class CounterfactualQuery:
    """Query for counterfactual reasoning."""

    patient_id: str
    intervention: str  # What if this happened?
    outcome: str  # What would be the effect on this?
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class CounterfactualResult:
    """Result of counterfactual analysis."""

    query: CounterfactualQuery
    predicted_outcome: str
    confidence: float
    supporting_chains: list[CausalChain]
    contradicting_chains: list[CausalChain]
    explanation: str


class CausalReasoningService:
    """Service for causal inference in clinical knowledge graphs.

    Features:
    - Find causal chains between concepts
    - Treatment-outcome pathway analysis
    - Adverse event causality assessment
    - Counterfactual reasoning support
    """

    # Relation types that represent causal relationships
    CAUSAL_RELATIONS = {
        CausalRelationType.CAUSES,
        CausalRelationType.MAY_CAUSE,
        CausalRelationType.LEADS_TO,
        CausalRelationType.ADVERSE_EFFECT_OF,
        CausalRelationType.COMPLICATION_OF,
    }

    # Relation types that represent therapeutic relationships
    THERAPEUTIC_RELATIONS = {
        CausalRelationType.TREATS,
        CausalRelationType.PREVENTS,
    }

    # Confidence decay per hop
    HOP_DECAY = 0.85

    def __init__(
        self,
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_user: str = "neo4j",
        neo4j_password: str = "clinical123",
    ):
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self._driver = None

    async def connect(self) -> None:
        """Connect to Neo4j database."""
        try:
            from neo4j import AsyncGraphDatabase

            self._driver = AsyncGraphDatabase.driver(
                self.neo4j_uri,
                auth=(self.neo4j_user, self.neo4j_password),
            )
            logger.info(f"Connected to Neo4j at {self.neo4j_uri}")
        except Exception as e:
            logger.warning(f"Neo4j connection failed: {e}")
            self._driver = None

    async def close(self) -> None:
        """Close Neo4j connection."""
        if self._driver:
            await self._driver.close()
            self._driver = None

    async def find_causal_chains(
        self,
        query: CausalQuery,
    ) -> list[CausalChain]:
        """Find causal chains between concepts.

        Args:
            query: CausalQuery with search parameters

        Returns:
            List of CausalChain objects
        """
        if not self._driver:
            logger.warning("Neo4j not connected, using mock data")
            return self._mock_causal_chains(query)

        # Build relationship type filter
        rel_types = query.relation_types or list(CausalRelationType)
        rel_type_list = [r.value for r in rel_types]

        # Build Cypher query
        if query.end_concept:
            # Find paths between specific concepts
            cypher = """
            MATCH (start:Concept)
            WHERE start.cui = $start_cui OR start.name CONTAINS $start_name
            MATCH (end:Concept)
            WHERE end.cui = $end_cui OR end.name CONTAINS $end_name
            MATCH path = shortestPath((start)-[*1..$max_length]-(end))
            WHERE ALL(r IN relationships(path) WHERE type(r) IN $rel_types)
            WITH path, nodes(path) as path_nodes, relationships(path) as path_rels
            RETURN path_nodes, path_rels, length(path) as chain_length
            ORDER BY chain_length
            LIMIT 10
            """
            params = {
                "start_cui": query.start_concept,
                "start_name": query.start_concept,
                "end_cui": query.end_concept,
                "end_name": query.end_concept,
                "max_length": query.max_chain_length,
                "rel_types": rel_type_list,
            }
        else:
            # Explore all causal chains from start concept
            cypher = """
            MATCH (start:Concept)
            WHERE start.cui = $start_cui OR start.name CONTAINS $start_name
            MATCH path = (start)-[*1..$max_length]->(end:Concept)
            WHERE ALL(r IN relationships(path) WHERE type(r) IN $rel_types)
            WITH path, nodes(path) as path_nodes, relationships(path) as path_rels,
                 end, length(path) as chain_length
            RETURN path_nodes, path_rels, chain_length, end.cui as end_cui
            ORDER BY chain_length
            LIMIT 20
            """
            params = {
                "start_cui": query.start_concept,
                "start_name": query.start_concept,
                "max_length": query.max_chain_length,
                "rel_types": rel_type_list,
            }

        chains = []
        try:
            async with self._driver.session() as session:
                result = await session.run(cypher, **params)
                async for record in result:
                    chain = self._build_chain_from_record(record, query)
                    if chain and chain.total_confidence >= query.min_confidence:
                        chains.append(chain)
        except Exception as e:
            logger.error(f"Error finding causal chains: {e}")
            return self._mock_causal_chains(query)

        return chains

    def _build_chain_from_record(
        self,
        record: Any,
        query: CausalQuery,
    ) -> CausalChain | None:
        """Build a CausalChain from a Neo4j query result."""
        try:
            path_nodes = record["path_nodes"]
            path_rels = record["path_rels"]
            chain_length = record["chain_length"]

            if not path_nodes or len(path_nodes) < 2:
                return None

            links = []
            confidence = 1.0

            for i, rel in enumerate(path_rels):
                source_node = path_nodes[i]
                target_node = path_nodes[i + 1]

                rel_type = CausalRelationType(rel.type) if hasattr(rel, 'type') else CausalRelationType.ASSOCIATED_WITH
                link_confidence = float(rel.get("confidence", 0.8)) if hasattr(rel, 'get') else 0.8

                link = CausalLink(
                    source_cui=source_node.get("cui", ""),
                    source_name=source_node.get("name", "Unknown"),
                    target_cui=target_node.get("cui", ""),
                    target_name=target_node.get("name", "Unknown"),
                    relation_type=rel_type,
                    confidence=link_confidence,
                    mechanism=rel.get("mechanism") if hasattr(rel, 'get') else None,
                )
                links.append(link)

                # Apply hop decay
                confidence *= link_confidence * (self.HOP_DECAY ** i)

            # Determine pathway type based on relations
            pathway_type = self._infer_pathway_type(links)

            return CausalChain(
                chain_id=f"chain_{hash(str(links))}",
                links=links,
                start_concept=links[0].source_cui,
                end_concept=links[-1].target_cui,
                total_confidence=confidence,
                chain_length=chain_length,
                pathway_type=pathway_type,
                mechanisms=[l.mechanism for l in links if l.mechanism],
            )

        except Exception as e:
            logger.debug(f"Error building chain: {e}")
            return None

    def _infer_pathway_type(self, links: list[CausalLink]) -> str:
        """Infer the type of pathway from the links."""
        rel_types = {link.relation_type for link in links}

        if CausalRelationType.ADVERSE_EFFECT_OF in rel_types:
            return "adverse_event"
        elif CausalRelationType.TREATS in rel_types or CausalRelationType.PREVENTS in rel_types:
            return "treatment"
        elif CausalRelationType.COMPLICATION_OF in rel_types:
            return "complication"
        elif CausalRelationType.LEADS_TO in rel_types:
            return "progression"
        else:
            return "causal"

    def _mock_causal_chains(self, query: CausalQuery) -> list[CausalChain]:
        """Generate mock causal chains for testing without Neo4j."""
        # Example: Diabetes -> Nephropathy -> ESRD
        mock_links = [
            CausalLink(
                source_cui="C0011849",
                source_name="Diabetes Mellitus",
                target_cui="C0011881",
                target_name="Diabetic Nephropathy",
                relation_type=CausalRelationType.CAUSES,
                confidence=0.85,
            ),
            CausalLink(
                source_cui="C0011881",
                source_name="Diabetic Nephropathy",
                target_cui="C0022661",
                target_name="End-Stage Renal Disease",
                relation_type=CausalRelationType.LEADS_TO,
                confidence=0.75,
            ),
        ]

        return [
            CausalChain(
                chain_id="mock_chain_1",
                links=mock_links,
                start_concept="C0011849",
                end_concept="C0022661",
                total_confidence=0.64,  # 0.85 * 0.75
                chain_length=2,
                pathway_type="progression",
            )
        ]

    async def find_treatment_pathways(
        self,
        condition_cui: str,
        include_mechanisms: bool = True,
    ) -> list[CausalChain]:
        """Find treatment pathways for a condition.

        Args:
            condition_cui: CUI of the condition
            include_mechanisms: Whether to include mechanism information

        Returns:
            List of treatment pathway chains
        """
        query = CausalQuery(
            start_concept=condition_cui,
            relation_types=[
                CausalRelationType.TREATS,
                CausalRelationType.PREVENTS,
            ],
            max_chain_length=3,
            require_mechanism=include_mechanisms,
        )
        return await self.find_causal_chains(query)

    async def find_adverse_event_pathways(
        self,
        drug_cui: str,
    ) -> list[CausalChain]:
        """Find adverse event pathways for a drug.

        Args:
            drug_cui: CUI of the drug

        Returns:
            List of adverse event chains
        """
        query = CausalQuery(
            start_concept=drug_cui,
            relation_types=[
                CausalRelationType.ADVERSE_EFFECT_OF,
                CausalRelationType.MAY_CAUSE,
                CausalRelationType.CAUSES,
            ],
            max_chain_length=3,
        )
        return await self.find_causal_chains(query)

    async def analyze_progression(
        self,
        condition_cui: str,
        max_stages: int = 5,
    ) -> list[CausalChain]:
        """Analyze disease progression pathways.

        Args:
            condition_cui: CUI of the starting condition
            max_stages: Maximum progression stages

        Returns:
            List of progression chains
        """
        query = CausalQuery(
            start_concept=condition_cui,
            relation_types=[
                CausalRelationType.LEADS_TO,
                CausalRelationType.COMPLICATION_OF,
                CausalRelationType.EXACERBATES,
            ],
            max_chain_length=max_stages,
        )
        return await self.find_causal_chains(query)

    async def counterfactual_analysis(
        self,
        query: CounterfactualQuery,
    ) -> CounterfactualResult:
        """Perform counterfactual analysis.

        "What would have happened if the patient received treatment X?"

        Args:
            query: CounterfactualQuery with intervention and outcome

        Returns:
            CounterfactualResult with prediction and explanation
        """
        # Find causal chains from intervention to outcome
        causal_query = CausalQuery(
            start_concept=query.intervention,
            end_concept=query.outcome,
            max_chain_length=5,
        )

        supporting = await self.find_causal_chains(causal_query)

        # Find chains that might contradict (through blocking mechanisms)
        contradicting: list[CausalChain] = []  # Would need more complex analysis

        # Calculate overall confidence
        if supporting:
            avg_confidence = sum(c.total_confidence for c in supporting) / len(supporting)
        else:
            avg_confidence = 0.0

        # Generate explanation
        if supporting:
            explanation = f"Found {len(supporting)} causal pathway(s) from {query.intervention} to {query.outcome}. "
            explanation += f"Average confidence: {avg_confidence:.2%}. "
            explanation += f"Primary pathway: {supporting[0].summary}"
        else:
            explanation = f"No causal pathways found from {query.intervention} to {query.outcome}."

        # Predict outcome
        if avg_confidence > 0.7:
            predicted = "likely"
        elif avg_confidence > 0.4:
            predicted = "possible"
        else:
            predicted = "unlikely"

        return CounterfactualResult(
            query=query,
            predicted_outcome=predicted,
            confidence=avg_confidence,
            supporting_chains=supporting,
            contradicting_chains=contradicting,
            explanation=explanation,
        )

    async def explain_causality(
        self,
        chain: CausalChain,
    ) -> str:
        """Generate a human-readable explanation of a causal chain.

        Args:
            chain: CausalChain to explain

        Returns:
            Natural language explanation
        """
        parts = []
        parts.append(f"Causal Pathway ({chain.pathway_type.title()}):\n")

        for i, link in enumerate(chain.links, 1):
            rel_desc = self._describe_relation(link.relation_type)
            parts.append(f"  {i}. {link.source_name} {rel_desc} {link.target_name}")

            if link.mechanism:
                parts.append(f"      Mechanism: {link.mechanism}")

            parts.append(f"      Confidence: {link.confidence:.0%}\n")

        parts.append(f"\nOverall pathway confidence: {chain.total_confidence:.0%}")

        if chain.mechanisms:
            parts.append(f"Key mechanisms: {', '.join(chain.mechanisms)}")

        return "\n".join(parts)

    def _describe_relation(self, rel_type: CausalRelationType) -> str:
        """Get human-readable description of relation type."""
        descriptions = {
            CausalRelationType.CAUSES: "causes",
            CausalRelationType.MAY_CAUSE: "may cause",
            CausalRelationType.PREVENTS: "prevents",
            CausalRelationType.TREATS: "treats",
            CausalRelationType.EXACERBATES: "worsens",
            CausalRelationType.LEADS_TO: "leads to",
            CausalRelationType.ASSOCIATED_WITH: "is associated with",
            CausalRelationType.COMPLICATION_OF: "is a complication of",
            CausalRelationType.ADVERSE_EFFECT_OF: "is an adverse effect of",
            CausalRelationType.CONTRAINDICATED_BY: "is contraindicated by",
        }
        return descriptions.get(rel_type, "relates to")


# Singleton instance
_causal_service: CausalReasoningService | None = None
_causal_lock = threading.Lock()


def get_causal_reasoning_service() -> CausalReasoningService:
    """Get the singleton causal reasoning service."""
    global _causal_service
    # VP-ThreadSafety: Double-checked locking for thread safety
    if _causal_service is None:
        with _causal_lock:
            if _causal_service is None:
                from app.core.config import settings

                _causal_service = CausalReasoningService(
                    neo4j_uri=getattr(settings, "neo4j_uri", "bolt://localhost:7687"),
                    neo4j_user=getattr(settings, "neo4j_user", "neo4j"),
                    neo4j_password=getattr(settings, "neo4j_password", "clinical123"),
                )
    return _causal_service
