"""Guideline RAG service for clinical guideline retrieval-augmented generation.

Loads clinical guideline sections from a fixture file, embeds them using
EmbeddingService, and provides semantic search with keyword boosting based
on patient context (conditions, medications, measurements).

This module uses a singleton pattern consistent with VocabularyService
and LLMService.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import ClassVar

logger = logging.getLogger(__name__)

# Singleton instance and lock for thread-safe initialization
_guideline_rag_instance: "GuidelineRAGService | None" = None
_guideline_rag_lock = Lock()


@dataclass
class GuidelineSection:
    """A single retrievable guideline section."""

    section_id: str
    guideline: str
    section_title: str
    recommendation_text: str
    evidence_grade: str
    recommendation_level: str
    applies_to_conditions: list[str] = field(default_factory=list)
    applies_to_medications: list[str] = field(default_factory=list)
    applies_to_measurements: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    embedding: list[float] = field(default_factory=list, repr=False)


@dataclass
class GuidelineCitation:
    """A guideline search result with relevance score."""

    section: GuidelineSection
    score: float
    match_reasons: list[str] = field(default_factory=list)


class GuidelineRAGService:
    """Service for retrieving relevant clinical guideline sections.

    Loads guideline sections from a JSON fixture, embeds them using
    EmbeddingService, and supports semantic search with keyword boosting
    from patient context.

    Usage:
        service = GuidelineRAGService()
        service.load()
        citations = service.search("a1c target", patient_conditions=["diabetes"])
    """

    DEFAULT_FIXTURE_PATH: ClassVar[str] = "fixtures/clinical_guidelines.json"

    def __init__(self, fixture_path: str | Path | None = None) -> None:
        self._fixture_path = fixture_path
        self._sections: list[GuidelineSection] = []
        self._embeddings: list[list[float]] = []
        self._loaded = False
        self._load_time_ms: float = 0.0

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def section_count(self) -> int:
        return len(self._sections)

    def load(self) -> None:
        """Load guideline sections from fixture and compute embeddings."""
        if self._loaded:
            return

        start = time.perf_counter()

        # Resolve fixture path
        if self._fixture_path:
            path = Path(self._fixture_path)
        else:
            path = Path(__file__).resolve().parent.parent.parent / self.DEFAULT_FIXTURE_PATH

        if not path.exists():
            logger.warning(f"Guideline fixture not found: {path}")
            self._loaded = True
            return

        # Load JSON
        with open(path) as f:
            data = json.load(f)

        raw_sections = data.get("guidelines", [])
        if not raw_sections:
            logger.warning("No guideline sections found in fixture")
            self._loaded = True
            return

        # Build GuidelineSection objects
        sections: list[GuidelineSection] = []
        embed_texts: list[str] = []

        for entry in raw_sections:
            section = GuidelineSection(
                section_id=entry["section_id"],
                guideline=entry["guideline"],
                section_title=entry["section_title"],
                recommendation_text=entry["recommendation_text"],
                evidence_grade=entry.get("evidence_grade", ""),
                recommendation_level=entry.get("recommendation_level", ""),
                applies_to_conditions=entry.get("applies_to_conditions", []),
                applies_to_medications=entry.get("applies_to_medications", []),
                applies_to_measurements=entry.get("applies_to_measurements", []),
                keywords=entry.get("keywords", []),
            )
            sections.append(section)

            # Build embedding text: combine title, keywords, and recommendation
            embed_text = (
                f"{section.section_title} {' '.join(section.keywords)} "
                f"{section.recommendation_text[:200]}"
            )
            embed_texts.append(embed_text)

        # Compute embeddings
        try:
            from app.services.embedding_service import get_embedding_service

            embedding_service = get_embedding_service()
            embeddings = embedding_service.encode_batch(embed_texts)

            for i, section in enumerate(sections):
                section.embedding = embeddings[i]

            self._sections = sections
            self._embeddings = embeddings
        except Exception as e:
            logger.error(f"Failed to compute guideline embeddings: {e}")
            # Still store sections for keyword-only fallback
            self._sections = sections
            self._embeddings = []

        self._loaded = True
        elapsed = (time.perf_counter() - start) * 1000
        self._load_time_ms = elapsed
        logger.info(
            f"Loaded {len(self._sections)} guideline sections in {elapsed:.0f}ms"
        )

    def search(
        self,
        query: str,
        patient_conditions: list[str] | None = None,
        patient_medications: list[str] | None = None,
        patient_measurements: list[str] | None = None,
        top_k: int = 5,
        min_score: float = 0.3,
    ) -> list[GuidelineCitation]:
        """Search for relevant guideline sections.

        Uses two phases:
        1. Semantic similarity via EmbeddingService.find_similar()
        2. Keyword boost from patient context

        Args:
            query: Natural language search query.
            patient_conditions: Patient's conditions for keyword boosting.
            patient_medications: Patient's medications for keyword boosting.
            patient_measurements: Patient's measurements for keyword boosting.
            top_k: Maximum number of results.
            min_score: Minimum relevance score to include.

        Returns:
            List of GuidelineCitation sorted by score descending.
        """
        if not self._loaded:
            self.load()

        if not self._sections:
            return []

        conditions = {c.lower() for c in (patient_conditions or [])}
        medications = {m.lower() for m in (patient_medications or [])}
        measurements = {m.lower() for m in (patient_measurements or [])}

        # Phase 1: Semantic search
        scored: dict[int, float] = {}
        reasons: dict[int, list[str]] = {}

        if self._embeddings:
            try:
                from app.services.embedding_service import get_embedding_service

                embedding_service = get_embedding_service()
                query_embedding = embedding_service.encode(query)
                semantic_results = embedding_service.find_similar(
                    query_embedding,
                    self._embeddings,
                    top_k=min(top_k * 2, len(self._sections)),
                    threshold=0.2,
                )

                for idx, sim_score in semantic_results:
                    scored[idx] = sim_score
                    reasons[idx] = [f"Semantic match ({sim_score:.2f})"]

            except Exception as e:
                logger.warning(f"Semantic search failed, using keyword-only: {e}")

        # Phase 2: Keyword boosting from patient context
        for idx, section in enumerate(self._sections):
            if idx not in scored:
                # Start with a base score of 0 if not found semantically
                scored[idx] = 0.0
                reasons[idx] = []

            section_conditions = {c.lower() for c in section.applies_to_conditions}
            section_medications = {m.lower() for m in section.applies_to_medications}
            section_measurements = {m.lower() for m in section.applies_to_measurements}

            # Condition match: +0.15
            condition_overlap = conditions & section_conditions
            if condition_overlap:
                scored[idx] += 0.15
                reasons[idx].append(
                    f"Condition match: {', '.join(sorted(condition_overlap))}"
                )

            # Medication match: +0.10
            medication_overlap = medications & section_medications
            if medication_overlap:
                scored[idx] += 0.10
                reasons[idx].append(
                    f"Medication match: {', '.join(sorted(medication_overlap))}"
                )

            # Measurement match: +0.10
            measurement_overlap = measurements & section_measurements
            if measurement_overlap:
                scored[idx] += 0.10
                reasons[idx].append(
                    f"Measurement match: {', '.join(sorted(measurement_overlap))}"
                )

        # Filter, sort, and return
        citations: list[GuidelineCitation] = []
        for idx, score in sorted(scored.items(), key=lambda x: x[1], reverse=True):
            if score < min_score:
                continue
            citations.append(
                GuidelineCitation(
                    section=self._sections[idx],
                    score=round(score, 3),
                    match_reasons=reasons.get(idx, []),
                )
            )
            if len(citations) >= top_k:
                break

        return citations


def get_guideline_rag_service() -> GuidelineRAGService:
    """Get the singleton GuidelineRAGService instance.

    Thread-safe accessor using double-check locking.

    Returns:
        The singleton GuidelineRAGService instance.
    """
    global _guideline_rag_instance

    if _guideline_rag_instance is None:
        with _guideline_rag_lock:
            if _guideline_rag_instance is None:
                logger.info("Creating singleton GuidelineRAGService instance")
                _guideline_rag_instance = GuidelineRAGService()
                _guideline_rag_instance.load()
    return _guideline_rag_instance


def reset_guideline_rag_singleton() -> None:
    """Reset the singleton instance. Useful for testing."""
    global _guideline_rag_instance
    with _guideline_rag_lock:
        _guideline_rag_instance = None
