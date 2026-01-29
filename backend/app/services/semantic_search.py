"""Semantic search service for clinical data.

Provides semantic similarity search over clinical facts, mentions,
and OMOP concepts using vector embeddings.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Sequence
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinical_fact import ClinicalFact
from app.models.knowledge_graph import KGNode
from app.services.embedding_service import EmbeddingService, get_embedding_service

logger = logging.getLogger(__name__)


@dataclass
class SemanticSearchResult:
    """Result from semantic search."""

    id: str
    text: str
    score: float
    domain: str | None = None
    omop_concept_id: int | None = None
    patient_id: str | None = None
    metadata: dict | None = None


class SemanticSearchService:
    """Service for semantic similarity search.

    Enables finding clinically similar facts and concepts using
    vector embeddings instead of exact text matching.

    Example queries:
        - "heart problems" → finds CHF, heart failure, cardiac arrest
        - "blood pressure medication" → finds ACE inhibitors, beta blockers
        - "difficulty breathing" → finds dyspnea, shortness of breath, respiratory distress
    """

    def __init__(self, embedding_service: EmbeddingService | None = None) -> None:
        """Initialize the semantic search service.

        Args:
            embedding_service: Optional embedding service instance.
        """
        self._embedding_service = embedding_service or get_embedding_service()

    async def search_clinical_facts(
        self,
        session: AsyncSession,
        query: str,
        patient_id: str | None = None,
        domain: str | None = None,
        top_k: int = 10,
        threshold: float = 0.5,
    ) -> list[SemanticSearchResult]:
        """Search clinical facts by semantic similarity.

        Args:
            session: Database session.
            query: Natural language search query.
            patient_id: Optional patient ID to filter results.
            domain: Optional domain to filter (condition, drug, measurement, etc.).
            top_k: Maximum number of results.
            threshold: Minimum similarity score (0-1).

        Returns:
            List of SemanticSearchResult ordered by similarity.
        """
        # Generate query embedding
        query_embedding = self._embedding_service.encode(query)

        # Build query for facts with embeddings
        stmt = select(ClinicalFact).where(ClinicalFact.embedding.isnot(None))

        if patient_id:
            stmt = stmt.where(ClinicalFact.patient_id == patient_id)
        if domain:
            stmt = stmt.where(ClinicalFact.domain == domain)

        result = await session.execute(stmt)
        facts = result.scalars().all()

        if not facts:
            return []

        # Compute similarities
        fact_embeddings = [f.embedding for f in facts]
        similar_indices = self._embedding_service.find_similar(
            query_embedding,
            fact_embeddings,
            top_k=top_k,
            threshold=threshold,
        )

        # Build results
        results = []
        for idx, score in similar_indices:
            fact = facts[idx]
            results.append(SemanticSearchResult(
                id=str(fact.id),
                text=fact.concept_name,
                score=score,
                domain=fact.domain.value if fact.domain else None,
                omop_concept_id=fact.omop_concept_id,
                patient_id=fact.patient_id,
                metadata={
                    "assertion": fact.assertion.value if fact.assertion else None,
                    "temporality": fact.temporality.value if fact.temporality else None,
                    "confidence": fact.confidence,
                },
            ))

        return results

    async def search_kg_nodes(
        self,
        session: AsyncSession,
        query: str,
        patient_id: str | None = None,
        node_type: str | None = None,
        top_k: int = 10,
        threshold: float = 0.5,
    ) -> list[SemanticSearchResult]:
        """Search knowledge graph nodes by semantic similarity.

        Args:
            session: Database session.
            query: Natural language search query.
            patient_id: Optional patient ID to filter results.
            node_type: Optional node type to filter.
            top_k: Maximum number of results.
            threshold: Minimum similarity score (0-1).

        Returns:
            List of SemanticSearchResult ordered by similarity.
        """
        # Generate query embedding
        query_embedding = self._embedding_service.encode(query)

        # Build query for nodes with embeddings
        stmt = select(KGNode).where(KGNode.embedding.isnot(None))

        if patient_id:
            stmt = stmt.where(KGNode.patient_id == patient_id)
        if node_type:
            stmt = stmt.where(KGNode.node_type == node_type)

        result = await session.execute(stmt)
        nodes = result.scalars().all()

        if not nodes:
            return []

        # Compute similarities
        node_embeddings = [n.embedding for n in nodes]
        similar_indices = self._embedding_service.find_similar(
            query_embedding,
            node_embeddings,
            top_k=top_k,
            threshold=threshold,
        )

        # Build results
        results = []
        for idx, score in similar_indices:
            node = nodes[idx]
            results.append(SemanticSearchResult(
                id=str(node.id),
                text=node.label,
                score=score,
                domain=node.node_type.value if node.node_type else None,
                omop_concept_id=node.omop_concept_id,
                patient_id=node.patient_id,
                metadata=node.properties,
            ))

        return results

    async def search_omop_concepts(
        self,
        session: AsyncSession,
        query: str,
        domain_id: str | None = None,
        vocabulary_id: str | None = None,
        top_k: int = 20,
        threshold: float = 0.5,
    ) -> list[SemanticSearchResult]:
        """Search OMOP concepts by semantic similarity.

        Uses pre-computed embeddings for OMOP concepts if available,
        otherwise falls back to text-based search.

        Args:
            session: Database session.
            query: Natural language search query.
            domain_id: Optional domain to filter (Condition, Drug, etc.).
            vocabulary_id: Optional vocabulary to filter (SNOMED, RxNorm, etc.).
            top_k: Maximum number of results.
            threshold: Minimum similarity score (0-1).

        Returns:
            List of SemanticSearchResult ordered by similarity.
        """
        # Generate query embedding
        query_embedding = self._embedding_service.encode(query)

        # Check if concept embeddings table exists and has data
        # For now, fall back to text-based search with semantic reranking
        sql = """
            SELECT concept_id, concept_name, domain_id, vocabulary_id
            FROM omop_concepts
            WHERE standard_concept = 'S'
        """
        params = {}

        if domain_id:
            sql += " AND domain_id = :domain_id"
            params["domain_id"] = domain_id

        if vocabulary_id:
            sql += " AND vocabulary_id = :vocabulary_id"
            params["vocabulary_id"] = vocabulary_id

        # First, do text-based filtering to get candidates
        # This is more efficient than embedding all concepts
        query_terms = query.lower().split()
        like_conditions = " OR ".join([
            f"LOWER(concept_name) LIKE :term{i}"
            for i in range(len(query_terms))
        ])
        if like_conditions:
            sql += f" AND ({like_conditions})"
            for i, term in enumerate(query_terms):
                params[f"term{i}"] = f"%{term}%"

        sql += " LIMIT 1000"  # Get candidates for reranking

        result = await session.execute(text(sql), params)
        rows = result.fetchall()

        if not rows:
            return []

        # Generate embeddings for candidates and rerank
        candidate_texts = [row[1] for row in rows]  # concept_name
        candidate_embeddings = self._embedding_service.encode_batch(candidate_texts)

        similar_indices = self._embedding_service.find_similar(
            query_embedding,
            candidate_embeddings,
            top_k=top_k,
            threshold=threshold,
        )

        # Build results
        results = []
        for idx, score in similar_indices:
            row = rows[idx]
            results.append(SemanticSearchResult(
                id=str(row[0]),  # concept_id
                text=row[1],     # concept_name
                score=score,
                domain=row[2],   # domain_id
                omop_concept_id=row[0],
                metadata={
                    "vocabulary_id": row[3],
                },
            ))

        return results

    async def generate_fact_embeddings(
        self,
        session: AsyncSession,
        patient_id: str | None = None,
        batch_size: int = 100,
    ) -> int:
        """Generate embeddings for clinical facts that don't have them.

        Args:
            session: Database session.
            patient_id: Optional patient ID to limit scope.
            batch_size: Number of facts to process at once.

        Returns:
            Number of facts updated.
        """
        # Get facts without embeddings
        stmt = select(ClinicalFact).where(ClinicalFact.embedding.is_(None))
        if patient_id:
            stmt = stmt.where(ClinicalFact.patient_id == patient_id)

        result = await session.execute(stmt)
        facts = result.scalars().all()

        if not facts:
            logger.info("No facts without embeddings found")
            return 0

        logger.info(f"Generating embeddings for {len(facts)} clinical facts")

        # Process in batches
        updated = 0
        for i in range(0, len(facts), batch_size):
            batch = facts[i:i + batch_size]
            texts = [f.concept_name for f in batch]
            embeddings = self._embedding_service.encode_batch(texts)

            for fact, embedding in zip(batch, embeddings):
                fact.embedding = embedding
                updated += 1

            await session.flush()
            logger.info(f"Processed {updated}/{len(facts)} facts")

        await session.commit()
        logger.info(f"Generated embeddings for {updated} clinical facts")
        return updated

    async def generate_node_embeddings(
        self,
        session: AsyncSession,
        patient_id: str | None = None,
        batch_size: int = 100,
    ) -> int:
        """Generate embeddings for KG nodes that don't have them.

        Args:
            session: Database session.
            patient_id: Optional patient ID to limit scope.
            batch_size: Number of nodes to process at once.

        Returns:
            Number of nodes updated.
        """
        # Get nodes without embeddings
        stmt = select(KGNode).where(KGNode.embedding.is_(None))
        if patient_id:
            stmt = stmt.where(KGNode.patient_id == patient_id)

        result = await session.execute(stmt)
        nodes = result.scalars().all()

        if not nodes:
            logger.info("No nodes without embeddings found")
            return 0

        logger.info(f"Generating embeddings for {len(nodes)} KG nodes")

        # Process in batches
        updated = 0
        for i in range(0, len(nodes), batch_size):
            batch = nodes[i:i + batch_size]
            texts = [n.label for n in batch]
            embeddings = self._embedding_service.encode_batch(texts)

            for node, embedding in zip(batch, embeddings):
                node.embedding = embedding
                updated += 1

            await session.flush()
            logger.info(f"Processed {updated}/{len(nodes)} nodes")

        await session.commit()
        logger.info(f"Generated embeddings for {updated} KG nodes")
        return updated


def get_semantic_search_service() -> SemanticSearchService:
    """Get the semantic search service instance.

    Returns:
        The semantic search service instance.
    """
    return SemanticSearchService()
