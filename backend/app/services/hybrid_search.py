"""Hybrid search service combining exact and semantic matching.

This service provides intelligent clinical term lookup by combining:
1. Exact match: Fast dictionary lookup for known terms
2. Semantic search: Vector similarity for fuzzy/unknown terms

The hybrid approach ensures:
- Known terms are matched instantly with high confidence
- Unknown/misspelled terms can still be mapped semantically
- Performance remains fast for the common case (exact match)
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.database import get_sync_engine
from app.models.vocabulary import Concept, ConceptSynonym
from app.services.embedding_service import EmbeddingService, get_embedding_service

logger = logging.getLogger(__name__)

# Scoring constants
EXACT_MATCH_SCORE = 1.0
SYNONYM_MATCH_SCORE = 0.95
SEMANTIC_SCORE_MULTIPLIER = 0.85  # Semantic matches get slightly lower confidence


@dataclass
class SearchResult:
    """Result from hybrid search."""

    concept_id: int
    concept_name: str
    domain_id: str
    vocabulary_id: str
    score: float
    match_type: str  # "exact", "synonym", "semantic"
    matched_term: str | None = None  # The term that matched (for synonym/semantic)


@dataclass
class HybridSearchService:
    """Service for hybrid exact + semantic concept search.

    Provides fast, intelligent clinical term lookup by combining
    dictionary-based exact matching with embedding-based semantic search.

    Usage:
        service = HybridSearchService()
        await service.initialize()  # Preload embeddings

        # Search for a term
        results = await service.search("heart failure", top_k=5)

        # Search with domain filter
        results = await service.search("metformin", domain_id="Drug")
    """

    _embedding_service: EmbeddingService = field(default_factory=get_embedding_service)
    _concept_embeddings: dict[int, list[float]] = field(default_factory=dict)
    _concept_cache: dict[int, tuple[str, str, str]] = field(default_factory=dict)  # id -> (name, domain, vocab)
    _synonym_index: dict[str, list[int]] = field(default_factory=dict)  # term -> concept_ids
    _initialized: bool = False

    async def initialize(
        self,
        session: AsyncSession,
        domains: Sequence[str] | None = None,
        max_concepts: int = 50_000,
    ) -> None:
        """Initialize the service by loading concept embeddings.

        Args:
            session: Database session.
            domains: Optional list of domains to load.
            max_concepts: Maximum concepts to load into memory.
        """
        if self._initialized:
            return

        logger.info("Initializing hybrid search service...")

        # Build query for concepts with embeddings
        stmt = (
            select(Concept)
            .where(Concept.embedding.isnot(None))
        )

        if domains:
            stmt = stmt.where(Concept.domain_id.in_(domains))

        stmt = stmt.limit(max_concepts)

        result = await session.execute(stmt)
        concepts = result.scalars().all()

        logger.info(f"Loading {len(concepts)} concepts with embeddings...")

        # Load embeddings and build cache
        for concept in concepts:
            self._concept_embeddings[concept.concept_id] = concept.embedding
            self._concept_cache[concept.concept_id] = (
                concept.concept_name,
                concept.domain_id,
                concept.vocabulary_id,
            )

            # Index by concept name for exact matching
            name_lower = concept.concept_name.lower()
            if name_lower not in self._synonym_index:
                self._synonym_index[name_lower] = []
            self._synonym_index[name_lower].append(concept.concept_id)

        # Load synonyms for exact matching
        concept_ids = list(self._concept_cache.keys())
        if concept_ids:
            # Batch load synonyms
            synonym_stmt = select(ConceptSynonym).where(
                ConceptSynonym.concept_id.in_(concept_ids)
            )
            synonym_result = await session.execute(synonym_stmt)
            synonyms = synonym_result.scalars().all()

            for syn in synonyms:
                term = syn.concept_synonym_name.lower()
                if term not in self._synonym_index:
                    self._synonym_index[term] = []
                if syn.concept_id not in self._synonym_index[term]:
                    self._synonym_index[term].append(syn.concept_id)

            logger.info(f"Indexed {len(synonyms)} synonyms")

        self._initialized = True
        logger.info(
            f"Hybrid search initialized: {len(self._concept_cache)} concepts, "
            f"{len(self._synonym_index)} indexed terms"
        )

    def _exact_search(
        self,
        term: str,
        domain_id: str | None = None,
    ) -> list[SearchResult]:
        """Perform exact/synonym matching.

        Args:
            term: Search term.
            domain_id: Optional domain filter.

        Returns:
            List of exact matches.
        """
        term_lower = term.lower().strip()
        results = []

        # Look up in synonym index
        concept_ids = self._synonym_index.get(term_lower, [])

        for cid in concept_ids:
            if cid not in self._concept_cache:
                continue

            name, domain, vocab = self._concept_cache[cid]

            # Apply domain filter
            if domain_id and domain != domain_id:
                continue

            # Determine match type
            if name.lower() == term_lower:
                match_type = "exact"
                score = EXACT_MATCH_SCORE
            else:
                match_type = "synonym"
                score = SYNONYM_MATCH_SCORE

            results.append(SearchResult(
                concept_id=cid,
                concept_name=name,
                domain_id=domain,
                vocabulary_id=vocab,
                score=score,
                match_type=match_type,
                matched_term=term,
            ))

        return results

    def _semantic_search(
        self,
        term: str,
        domain_id: str | None = None,
        top_k: int = 10,
        threshold: float = 0.6,
    ) -> list[SearchResult]:
        """Perform semantic similarity search.

        Args:
            term: Search term.
            domain_id: Optional domain filter.
            top_k: Maximum results.
            threshold: Minimum similarity threshold.

        Returns:
            List of semantic matches.
        """
        if not self._concept_embeddings:
            return []

        # Generate embedding for search term
        query_embedding = self._embedding_service.encode(term)
        query_vec = np.array(query_embedding)
        query_norm = np.linalg.norm(query_vec)

        if query_norm == 0:
            return []

        # Filter concepts by domain if specified
        if domain_id:
            candidate_ids = [
                cid for cid, (_, d, _) in self._concept_cache.items()
                if d == domain_id and cid in self._concept_embeddings
            ]
        else:
            candidate_ids = list(self._concept_embeddings.keys())

        if not candidate_ids:
            return []

        # Compute similarities efficiently
        candidate_embeddings = np.array([
            self._concept_embeddings[cid] for cid in candidate_ids
        ])
        candidate_norms = np.linalg.norm(candidate_embeddings, axis=1)

        # Avoid division by zero
        valid_mask = candidate_norms > 0
        similarities = np.zeros(len(candidate_ids))
        similarities[valid_mask] = (
            np.dot(candidate_embeddings[valid_mask], query_vec) /
            (candidate_norms[valid_mask] * query_norm)
        )

        # Get top-k above threshold
        results = []
        for idx, score in enumerate(similarities):
            if score >= threshold:
                cid = candidate_ids[idx]
                name, domain, vocab = self._concept_cache[cid]
                results.append(SearchResult(
                    concept_id=cid,
                    concept_name=name,
                    domain_id=domain,
                    vocabulary_id=vocab,
                    score=float(score) * SEMANTIC_SCORE_MULTIPLIER,
                    match_type="semantic",
                    matched_term=term,
                ))

        # Sort by score and limit
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    async def search(
        self,
        term: str,
        domain_id: str | None = None,
        top_k: int = 10,
        semantic_threshold: float = 0.6,
        include_semantic: bool = True,
    ) -> list[SearchResult]:
        """Hybrid search combining exact and semantic matching.

        First tries exact/synonym matching (fast, high confidence).
        If no exact matches found and include_semantic=True, falls back
        to semantic search (slower, lower confidence but handles typos).

        Args:
            term: Search term.
            domain_id: Optional domain filter.
            top_k: Maximum results.
            semantic_threshold: Minimum semantic similarity.
            include_semantic: Whether to include semantic results.

        Returns:
            List of SearchResults sorted by score.
        """
        if not self._initialized:
            logger.warning("Hybrid search not initialized - returning empty results")
            return []

        # Try exact matching first
        exact_results = self._exact_search(term, domain_id)

        if exact_results:
            # Have exact matches - return them sorted by score
            exact_results.sort(key=lambda r: r.score, reverse=True)
            return exact_results[:top_k]

        # No exact matches - try semantic search
        if include_semantic:
            return self._semantic_search(
                term, domain_id, top_k, semantic_threshold
            )

        return []

    async def batch_search(
        self,
        terms: Sequence[str],
        domain_id: str | None = None,
        top_k_per_term: int = 1,
    ) -> dict[str, list[SearchResult]]:
        """Search multiple terms efficiently.

        Args:
            terms: List of search terms.
            domain_id: Optional domain filter.
            top_k_per_term: Max results per term.

        Returns:
            Dictionary mapping terms to their results.
        """
        results = {}
        for term in terms:
            results[term] = await self.search(
                term,
                domain_id=domain_id,
                top_k=top_k_per_term,
            )
        return results


# Singleton instance
_hybrid_search_service: HybridSearchService | None = None
_hybrid_search_lock = asyncio.Lock()


async def get_hybrid_search_service(
    session: AsyncSession,
    domains: Sequence[str] | None = None,
) -> HybridSearchService:
    """Get or create the singleton hybrid search service.

    Args:
        session: Database session for initialization.
        domains: Optional domain filter for initialization.

    Returns:
        Initialized HybridSearchService instance.
    """
    global _hybrid_search_service

    # VP-ThreadSafety: Double-checked locking for thread safety
    if _hybrid_search_service is None:
        async with _hybrid_search_lock:
            if _hybrid_search_service is None:
                _hybrid_search_service = HybridSearchService()

    if not _hybrid_search_service._initialized:
        await _hybrid_search_service.initialize(session, domains)

    return _hybrid_search_service
