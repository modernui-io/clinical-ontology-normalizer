"""
Graph Embedding Service for Neo4j Knowledge Graph.

Provides vector embedding capabilities for clinical concepts:
- Generate embeddings using sentence-transformers
- Store embeddings in Neo4j nodes
- Vector similarity search for semantic matching
- Hybrid search combining graph traversal with vector similarity

Based on published approaches:
- DR.KNOWS: Embedding-enhanced knowledge retrieval
- Clinical concept embeddings for semantic similarity
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Model configuration
DEFAULT_MODEL = "all-MiniLM-L6-v2"  # 384-dim, fast and effective
EMBEDDING_DIM = 384


@dataclass
class SimilarConcept:
    """A concept found via embedding similarity."""

    cui: str
    name: str
    similarity: float
    semantic_type: str | None = None
    properties: dict[str, Any] | None = None


class GraphEmbeddingService:
    """Service for managing concept embeddings in Neo4j.

    Features:
    - On-demand embedding generation using sentence-transformers
    - Batch embedding for large concept sets
    - Vector similarity search in Neo4j
    - Hybrid graph+vector retrieval
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_user: str = "neo4j",
        neo4j_password: str = "clinical123",
    ):
        self.model_name = model_name
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password

        self._model = None
        self._driver = None

    def _get_model(self):
        """Lazy load the sentence transformer model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self.model_name)
                logger.info(f"Loaded embedding model: {self.model_name}")
            except ImportError:
                logger.warning("sentence-transformers not installed, embeddings disabled")
                return None
        return self._model

    def generate_embedding(self, text: str) -> list[float] | None:
        """Generate embedding for a single text.

        Args:
            text: Text to embed (concept name, description, etc.)

        Returns:
            List of floats (embedding vector) or None if model unavailable
        """
        model = self._get_model()
        if model is None:
            return None

        try:
            embedding = model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None

    def generate_embeddings_batch(
        self,
        texts: list[str],
        batch_size: int = 64,
    ) -> list[list[float]]:
        """Generate embeddings for multiple texts in batches.

        Args:
            texts: List of texts to embed
            batch_size: Batch size for encoding

        Returns:
            List of embedding vectors
        """
        model = self._get_model()
        if model is None:
            return []

        try:
            embeddings = model.encode(
                texts,
                batch_size=batch_size,
                convert_to_numpy=True,
                show_progress_bar=len(texts) > 1000,
            )
            return [e.tolist() for e in embeddings]
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            return []

    def cosine_similarity(
        self,
        embedding1: list[float],
        embedding2: list[float],
    ) -> float:
        """Calculate cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Cosine similarity score (0-1)
        """
        v1 = np.array(embedding1)
        v2 = np.array(embedding2)

        dot = np.dot(v1, v2)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot / (norm1 * norm2))

    async def connect_neo4j(self) -> None:
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

    async def create_vector_index(self) -> None:
        """Create vector index in Neo4j for similarity search.

        Requires Neo4j 5.11+ with vector search support.
        """
        if not self._driver:
            logger.warning("Neo4j not connected")
            return

        # Create vector index using Neo4j 5.x syntax
        query = """
        CREATE VECTOR INDEX concept_embedding IF NOT EXISTS
        FOR (c:Concept)
        ON c.embedding
        OPTIONS {
            indexConfig: {
                `vector.dimensions`: $dimensions,
                `vector.similarity_function`: 'cosine'
            }
        }
        """

        try:
            async with self._driver.session() as session:
                await session.run(query, dimensions=EMBEDDING_DIM)
            logger.info("Created vector index 'concept_embedding'")
        except Exception as e:
            logger.debug(f"Vector index creation skipped: {e}")

    async def store_embedding(
        self,
        cui: str,
        embedding: list[float],
    ) -> None:
        """Store an embedding for a concept in Neo4j.

        Args:
            cui: Concept Unique Identifier
            embedding: Embedding vector
        """
        if not self._driver:
            return

        query = """
        MATCH (c:Concept {cui: $cui})
        SET c.embedding = $embedding
        """

        try:
            async with self._driver.session() as session:
                await session.run(query, cui=cui, embedding=embedding)
        except Exception as e:
            logger.error(f"Error storing embedding for {cui}: {e}")

    async def store_embeddings_batch(
        self,
        concepts: list[dict[str, Any]],
        batch_size: int = 1000,
    ) -> int:
        """Store embeddings for multiple concepts.

        Args:
            concepts: List of dicts with 'cui' and 'embedding' keys
            batch_size: Batch size for database operations

        Returns:
            Number of embeddings stored
        """
        if not self._driver:
            return 0

        query = """
        UNWIND $concepts AS concept
        MATCH (c:Concept {cui: concept.cui})
        SET c.embedding = concept.embedding
        """

        stored = 0
        async with self._driver.session() as session:
            for i in range(0, len(concepts), batch_size):
                batch = concepts[i : i + batch_size]
                await session.run(query, concepts=batch)
                stored += len(batch)
                if stored % 10000 == 0:
                    logger.info(f"Stored {stored:,} embeddings...")

        return stored

    async def find_similar_concepts(
        self,
        query_text: str,
        top_k: int = 10,
        min_similarity: float = 0.5,
        semantic_types: list[str] | None = None,
    ) -> list[SimilarConcept]:
        """Find concepts similar to a query using vector search.

        Args:
            query_text: Text to search for
            top_k: Number of results to return
            min_similarity: Minimum similarity threshold
            semantic_types: Optional filter by semantic types

        Returns:
            List of similar concepts with scores
        """
        # Generate query embedding
        query_embedding = self.generate_embedding(query_text)
        if query_embedding is None:
            return []

        return await self.find_similar_by_embedding(
            query_embedding,
            top_k=top_k,
            min_similarity=min_similarity,
            semantic_types=semantic_types,
        )

    async def find_similar_by_embedding(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        min_similarity: float = 0.5,
        semantic_types: list[str] | None = None,
    ) -> list[SimilarConcept]:
        """Find concepts similar to an embedding vector.

        Uses Neo4j vector index for efficient similarity search.

        Args:
            query_embedding: Embedding vector to search with
            top_k: Number of results
            min_similarity: Minimum similarity threshold
            semantic_types: Optional semantic type filter

        Returns:
            List of similar concepts
        """
        if not self._driver:
            return []

        # Build query with optional semantic type filter
        type_filter = ""
        if semantic_types:
            type_filter = "AND c.semantic_type IN $semantic_types"

        # Use Neo4j vector search
        query = f"""
        CALL db.index.vector.queryNodes('concept_embedding', $top_k, $embedding)
        YIELD node as c, score
        WHERE score >= $min_similarity {type_filter}
        RETURN c.cui as cui, c.name as name, c.semantic_type as semantic_type,
               score as similarity
        ORDER BY score DESC
        LIMIT $top_k
        """

        results = []
        try:
            async with self._driver.session() as session:
                result = await session.run(
                    query,
                    embedding=query_embedding,
                    top_k=top_k * 2,  # Over-fetch to account for filtering
                    min_similarity=min_similarity,
                    semantic_types=semantic_types or [],
                )
                async for record in result:
                    results.append(
                        SimilarConcept(
                            cui=record["cui"],
                            name=record["name"],
                            similarity=record["similarity"],
                            semantic_type=record["semantic_type"],
                        )
                    )
        except Exception as e:
            logger.debug(f"Vector search error (may need index): {e}")
            # Fallback to brute-force if vector index not available
            return await self._fallback_similarity_search(
                query_embedding, top_k, min_similarity, semantic_types
            )

        return results[:top_k]

    async def _fallback_similarity_search(
        self,
        query_embedding: list[float],
        top_k: int,
        min_similarity: float,
        semantic_types: list[str] | None,
    ) -> list[SimilarConcept]:
        """Fallback brute-force similarity search when vector index unavailable.

        This is slower but works on all Neo4j versions.
        """
        if not self._driver:
            return []

        type_filter = ""
        if semantic_types:
            type_filter = "AND c.semantic_type IN $semantic_types"

        # Fetch all concepts with embeddings and compute similarity in Python
        query = f"""
        MATCH (c:Concept)
        WHERE c.embedding IS NOT NULL {type_filter}
        RETURN c.cui as cui, c.name as name, c.semantic_type as semantic_type,
               c.embedding as embedding
        LIMIT 10000
        """

        results = []
        try:
            async with self._driver.session() as session:
                result = await session.run(
                    query,
                    semantic_types=semantic_types or [],
                )
                async for record in result:
                    concept_embedding = record["embedding"]
                    if concept_embedding:
                        similarity = self.cosine_similarity(
                            query_embedding, concept_embedding
                        )
                        if similarity >= min_similarity:
                            results.append(
                                SimilarConcept(
                                    cui=record["cui"],
                                    name=record["name"],
                                    similarity=similarity,
                                    semantic_type=record["semantic_type"],
                                )
                            )
        except Exception as e:
            logger.error(f"Fallback similarity search error: {e}")
            return []

        # Sort by similarity and return top-k
        results.sort(key=lambda x: x.similarity, reverse=True)
        return results[:top_k]

    async def hybrid_search(
        self,
        query_text: str,
        patient_id: str | None = None,
        top_k: int = 10,
        vector_weight: float = 0.5,
        graph_hops: int = 2,
    ) -> list[dict[str, Any]]:
        """Hybrid search combining vector similarity with graph traversal.

        This implements the hybrid retrieval pattern from DR.KNOWS:
        1. Find semantically similar concepts via vector search
        2. Expand via graph traversal to find related concepts
        3. Combine scores from both sources

        Args:
            query_text: Search query
            patient_id: Optional patient context for personalization
            top_k: Number of results
            vector_weight: Weight for vector vs graph scores (0-1)
            graph_hops: Number of hops for graph expansion

        Returns:
            List of concepts with hybrid scores
        """
        if not self._driver:
            return []

        # Step 1: Vector search for initial candidates
        similar = await self.find_similar_concepts(
            query_text,
            top_k=top_k * 2,  # Get more candidates for expansion
            min_similarity=0.3,
        )

        if not similar:
            return []

        # Step 2: Graph expansion from similar concepts
        seed_cuis = [s.cui for s in similar]
        similarity_scores = {s.cui: s.similarity for s in similar}

        # Expand via graph traversal
        query = """
        UNWIND $seed_cuis as seed_cui
        MATCH (seed:Concept {cui: seed_cui})
        OPTIONAL MATCH path = (seed)-[*1..$hops]-(neighbor:Concept)
        WHERE neighbor.cui <> seed_cui
        WITH seed, neighbor, length(path) as distance
        RETURN DISTINCT
            neighbor.cui as cui,
            neighbor.name as name,
            neighbor.semantic_type as semantic_type,
            min(distance) as min_distance,
            count(*) as path_count
        ORDER BY min_distance, path_count DESC
        LIMIT $limit
        """

        expanded_results = {}
        graph_weight = 1 - vector_weight

        try:
            async with self._driver.session() as session:
                result = await session.run(
                    query,
                    seed_cuis=seed_cuis,
                    hops=graph_hops,
                    limit=top_k * 3,
                )
                async for record in result:
                    cui = record["cui"]
                    if cui:
                        # Graph score based on distance and path count
                        distance = record["min_distance"] or 1
                        path_count = record["path_count"] or 1
                        graph_score = (1 / distance) * min(path_count / 10, 1.0)

                        # Get vector score if available
                        vector_score = similarity_scores.get(cui, 0)

                        # Combine scores
                        hybrid_score = (
                            vector_weight * vector_score + graph_weight * graph_score
                        )

                        expanded_results[cui] = {
                            "cui": cui,
                            "name": record["name"],
                            "semantic_type": record["semantic_type"],
                            "vector_score": vector_score,
                            "graph_score": graph_score,
                            "hybrid_score": hybrid_score,
                            "min_distance": distance,
                            "path_count": path_count,
                        }

        except Exception as e:
            logger.error(f"Graph expansion error: {e}")
            # Return vector-only results
            return [
                {
                    "cui": s.cui,
                    "name": s.name,
                    "semantic_type": s.semantic_type,
                    "vector_score": s.similarity,
                    "graph_score": 0,
                    "hybrid_score": s.similarity * vector_weight,
                }
                for s in similar[:top_k]
            ]

        # Add original vector results that weren't in graph expansion
        for s in similar:
            if s.cui not in expanded_results:
                expanded_results[s.cui] = {
                    "cui": s.cui,
                    "name": s.name,
                    "semantic_type": s.semantic_type,
                    "vector_score": s.similarity,
                    "graph_score": 0,
                    "hybrid_score": s.similarity * vector_weight,
                }

        # Sort by hybrid score and return top-k
        sorted_results = sorted(
            expanded_results.values(),
            key=lambda x: x["hybrid_score"],
            reverse=True,
        )
        return sorted_results[:top_k]

    async def embed_all_concepts(
        self,
        batch_size: int = 1000,
    ) -> dict[str, int]:
        """Generate and store embeddings for all concepts without embeddings.

        This is a batch operation for initial population.

        Args:
            batch_size: Batch size for processing

        Returns:
            Statistics about the embedding operation
        """
        if not self._driver:
            return {"error": "Neo4j not connected"}

        # Get concepts without embeddings
        query = """
        MATCH (c:Concept)
        WHERE c.embedding IS NULL AND c.name IS NOT NULL
        RETURN c.cui as cui, c.name as name
        LIMIT 100000
        """

        stats = {"processed": 0, "embedded": 0, "errors": 0}

        try:
            async with self._driver.session() as session:
                result = await session.run(query)
                concepts_to_embed = []

                async for record in result:
                    concepts_to_embed.append({
                        "cui": record["cui"],
                        "name": record["name"],
                    })

            logger.info(f"Found {len(concepts_to_embed)} concepts to embed")

            # Generate embeddings in batches
            for i in range(0, len(concepts_to_embed), batch_size):
                batch = concepts_to_embed[i : i + batch_size]
                names = [c["name"] for c in batch]

                embeddings = self.generate_embeddings_batch(names)

                if embeddings:
                    # Prepare for storage
                    embed_data = [
                        {"cui": batch[j]["cui"], "embedding": embeddings[j]}
                        for j in range(len(embeddings))
                    ]
                    await self.store_embeddings_batch(embed_data)
                    stats["embedded"] += len(embeddings)
                else:
                    stats["errors"] += len(batch)

                stats["processed"] += len(batch)

                if stats["processed"] % 10000 == 0:
                    logger.info(f"Processed {stats['processed']:,} concepts...")

        except Exception as e:
            logger.error(f"Error embedding concepts: {e}")
            stats["error"] = str(e)

        logger.info(f"Embedding complete: {stats}")
        return stats


# Singleton instance
_embedding_service: GraphEmbeddingService | None = None


def get_graph_embedding_service() -> GraphEmbeddingService:
    """Get the singleton graph embedding service."""
    global _embedding_service
    if _embedding_service is None:
        from app.core.config import settings

        _embedding_service = GraphEmbeddingService(
            neo4j_uri=getattr(settings, "neo4j_uri", "bolt://localhost:7687"),
            neo4j_user=getattr(settings, "neo4j_user", "neo4j"),
            neo4j_password=getattr(settings, "neo4j_password", "clinical123"),
        )
    return _embedding_service
