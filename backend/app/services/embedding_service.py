"""Embedding service for semantic search.

Uses sentence-transformers to generate embeddings for clinical text,
enabling semantic similarity search across clinical facts and concepts.
"""

import logging
import threading
from functools import lru_cache
from typing import Sequence

import numpy as np

logger = logging.getLogger(__name__)

# Model configuration
DEFAULT_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384  # Dimension for MiniLM model


class EmbeddingService:
    """Service for generating and comparing text embeddings.

    Uses sentence-transformers for efficient embedding generation.
    The all-MiniLM-L6-v2 model provides a good balance of:
    - Speed (fast inference)
    - Quality (good semantic understanding)
    - Size (small memory footprint)

    Usage:
        service = EmbeddingService()
        embedding = service.encode("heart failure")
        similar = service.find_similar(embedding, candidates)
    """

    _instance: "EmbeddingService | None" = None
    _instance_lock = threading.Lock()
    _model = None

    def __new__(cls) -> "EmbeddingService":
        """Singleton pattern for efficient model reuse."""
        # VP-ThreadSafety-4: Double-checked locking for thread safety
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        """Initialize the embedding service.

        Args:
            model_name: Name of the sentence-transformers model to use.
        """
        self.model_name = model_name
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazy initialization of the model."""
        if self._initialized and self._model is not None:
            return

        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
            self._initialized = True
            logger.info(f"Embedding model loaded successfully (dim={EMBEDDING_DIM})")
        except ImportError:
            logger.error("sentence-transformers not installed. Run: pip install sentence-transformers")
            raise
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise

    def encode(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Input text to encode.

        Returns:
            List of floats representing the embedding vector.
        """
        self._ensure_initialized()

        # Normalize text for better embedding quality
        text = text.strip().lower()
        if not text:
            return [0.0] * EMBEDDING_DIM

        embedding = self._model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def encode_batch(self, texts: Sequence[str], batch_size: int = 32) -> list[list[float]]:
        """Generate embeddings for multiple texts efficiently.

        Args:
            texts: List of texts to encode.
            batch_size: Number of texts to process at once.

        Returns:
            List of embedding vectors.
        """
        self._ensure_initialized()

        if not texts:
            return []

        # Normalize texts
        normalized = [t.strip().lower() if t else "" for t in texts]

        # Handle empty texts
        embeddings = self._model.encode(
            normalized,
            batch_size=batch_size,
            convert_to_numpy=True,
            show_progress_bar=len(texts) > 100,
        )

        return embeddings.tolist()

    def cosine_similarity(
        self,
        embedding1: list[float],
        embedding2: list[float],
    ) -> float:
        """Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector.
            embedding2: Second embedding vector.

        Returns:
            Cosine similarity score between -1 and 1.
        """
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(np.dot(vec1, vec2) / (norm1 * norm2))

    def find_similar(
        self,
        query_embedding: list[float],
        candidate_embeddings: list[list[float]],
        top_k: int = 10,
        threshold: float = 0.5,
    ) -> list[tuple[int, float]]:
        """Find most similar embeddings to a query.

        Args:
            query_embedding: The query embedding vector.
            candidate_embeddings: List of candidate embeddings to search.
            top_k: Maximum number of results to return.
            threshold: Minimum similarity score to include.

        Returns:
            List of (index, similarity_score) tuples, sorted by score descending.
        """
        if not candidate_embeddings:
            return []

        query = np.array(query_embedding)
        candidates = np.array(candidate_embeddings)

        # Compute all similarities at once
        query_norm = np.linalg.norm(query)
        if query_norm == 0:
            return []

        candidate_norms = np.linalg.norm(candidates, axis=1)

        # Avoid division by zero
        valid_mask = candidate_norms > 0
        similarities = np.zeros(len(candidates))
        similarities[valid_mask] = (
            np.dot(candidates[valid_mask], query) /
            (candidate_norms[valid_mask] * query_norm)
        )

        # Filter by threshold and get top-k
        results = []
        for idx, score in enumerate(similarities):
            if score >= threshold:
                results.append((idx, float(score)))

        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)

        return results[:top_k]


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    """Get the singleton embedding service instance.

    Returns:
        The embedding service instance.
    """
    return EmbeddingService()
