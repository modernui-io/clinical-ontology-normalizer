"""Guideline RAG service for clinical guideline retrieval-augmented generation.

Loads clinical guideline sections from a fixture file, embeds them using
EmbeddingService, and provides semantic search with keyword boosting based
on patient context (conditions, medications, measurements).

Now enhanced with OMOP hierarchy support via Neo4j - patient condition
"Type 2 diabetes mellitus" will match guidelines for "diabetes" via
IS_A relationship traversal.

This module uses a singleton pattern consistent with VocabularyService
and LLMService.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import ClassVar

logger = logging.getLogger(__name__)


def _expand_conditions_with_hierarchy(conditions: set[str]) -> set[str]:
    """Expand patient conditions using OMOP hierarchy.

    Patient with "type 2 diabetes mellitus" will also match against
    "diabetes mellitus", "disorder of glucose metabolism", etc.
    """
    if not conditions:
        return conditions

    expanded = set(conditions)

    try:
        from app.services.omop_hierarchy_service import get_omop_hierarchy_service

        hierarchy = get_omop_hierarchy_service()
        if hierarchy.is_available:
            for condition in conditions:
                # Get ancestor names for this condition
                ancestor_names = hierarchy.expand_condition_names(
                    condition, max_distance=3
                )
                expanded.update(ancestor_names)
                if ancestor_names - {condition.lower()}:
                    logger.debug(
                        f"Hierarchy expanded '{condition}' to include: "
                        f"{ancestor_names - {condition.lower()}}"
                    )
    except Exception as e:
        logger.warning(f"Hierarchy expansion failed, using original conditions: {e}")

    return expanded

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
    primary_conditions: list[str] = field(default_factory=list)
    omop_concept_ids: list[int] = field(default_factory=list)
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
                primary_conditions=entry.get("primary_conditions", []),
                omop_concept_ids=entry.get("omop_concept_ids", []),
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

        # Expand conditions using OMOP hierarchy
        raw_conditions = {c.lower() for c in (patient_conditions or [])}
        conditions = _expand_conditions_with_hierarchy(raw_conditions)
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

        # Phase 2: Query-keyword matching + patient context boosting
        _stopwords = {
            "the", "and", "for", "are", "was", "were", "been", "being", "have",
            "has", "had", "does", "did", "will", "would", "could", "should",
            "may", "can", "this", "that", "with", "from", "into", "than",
            "what", "which", "who", "how", "not", "but", "all", "any", "our",
            "their", "them", "they", "its", "his", "her", "she", "him",
            "about", "also", "each", "most", "need", "well", "been",
        }
        # Medical synonym groups for query expansion
        _synonyms: dict[str, set[str]] = {
            "treatment": {"treatment", "management", "therapy", "medications"},
            "management": {"treatment", "management", "therapy"},
            "therapy": {"treatment", "management", "therapy"},
            "medications": {"medications", "treatment", "drugs", "pharmacotherapy"},
            "diagnosis": {"diagnosis", "evaluation", "assessment", "workup"},
            "evaluation": {"diagnosis", "evaluation", "assessment", "workup"},
            "screening": {"screening", "prevention", "detection"},
            "prevention": {"screening", "prevention", "prophylaxis"},
        }

        raw_terms = set()
        for w in query.split():
            cleaned = w.lower().strip("?.,!:;\"'()")
            if len(cleaned) > 2 and cleaned not in _stopwords:
                raw_terms.add(cleaned)
                # Also split hyphens so "step-up" produces "step" and "up"
                if "-" in cleaned:
                    raw_terms.update(
                        p for p in cleaned.split("-") if len(p) > 2 and p not in _stopwords
                    )
                # Add stemmed variant (strip trailing 's') for matching
                if len(cleaned) > 3 and cleaned.endswith("s"):
                    raw_terms.add(cleaned[:-1])
                # Add plural variant for matching
                if len(cleaned) > 3 and not cleaned.endswith("s"):
                    raw_terms.add(cleaned + "s")
                # Expand medical synonyms
                if cleaned in _synonyms:
                    raw_terms.update(_synonyms[cleaned])
        query_terms = raw_terms

        for idx, section in enumerate(self._sections):
            if idx not in scored:
                scored[idx] = 0.0
                reasons[idx] = []

            section_conditions = {c.lower() for c in section.applies_to_conditions}
            section_medications = {m.lower() for m in section.applies_to_medications}
            section_measurements = {m.lower() for m in section.applies_to_measurements}
            section_keywords = {k.lower() for k in section.keywords}
            # Expand matchable terms: keywords + applies_to fields + title + guideline name
            title_words = {w.lower() for w in section.section_title.split() if len(w) > 2}
            guideline_words = set()
            for w in section.guideline.split():
                cleaned_w = w.lower().strip("()'\"—-")
                if len(cleaned_w) > 2 and cleaned_w not in _stopwords:
                    guideline_words.add(cleaned_w)
            all_section_terms = (
                section_keywords | section_conditions | section_medications
                | section_measurements | title_words | guideline_words
            )
            # Decompose multi-word terms into individual words.
            # NOTE: We intentionally exclude applies_to_conditions from
            # decomposition — splitting "sickle cell anemia" into individual
            # words causes false matches (e.g., "anemia" matching a patient
            # who has a different type of anemia). Condition matching is
            # handled by ConditionMatchingService instead.
            for term_source in [
                section.keywords,
                section.applies_to_medications, section.applies_to_measurements,
            ]:
                for term in term_source:
                    if " " in term:
                        for word in term.lower().split():
                            if len(word) > 2 and word not in _stopwords:
                                all_section_terms.add(word)
            # Add stemmed variants (strip trailing 's' for simple plural/possessive)
            stemmed_terms: set[str] = set()
            for t in list(all_section_terms):
                if len(t) > 3 and t.endswith("s"):
                    stemmed_terms.add(t[:-1])
            all_section_terms |= stemmed_terms

            # Query-keyword match: up to +0.40 (scaled by match count)
            keyword_matches = query_terms & all_section_terms
            # Also check multi-word terms against query string (worth double)
            query_lower = query.lower()
            multi_word_matches: set[str] = set()
            for term_source in [section.keywords, section.applies_to_conditions]:
                for term in term_source:
                    if " " in term and term.lower() in query_lower:
                        multi_word_matches.add(term.lower())
            keyword_matches |= multi_word_matches
            if keyword_matches:
                # Multi-word matches count double for scoring
                match_weight = (
                    (len(keyword_matches) - len(multi_word_matches)) * 0.10
                    + len(multi_word_matches) * 0.20
                )
                kw_score = min(0.40, match_weight)
                scored[idx] += kw_score
                reasons[idx].append(
                    f"Query keyword match: {', '.join(sorted(keyword_matches))}"
                )

            # Primary topic match: strong boost when query names a condition
            # or core keyword this section covers. Excludes generic terms
            # (treatment, management, therapy, etc.) to avoid false positives.
            _generic_terms = {
                "treatment", "management", "therapy", "medications", "medication",
                "drugs", "pharmacotherapy", "diagnosis", "evaluation", "assessment",
                "workup", "screening", "prevention", "prophylaxis", "detection",
                "monitoring", "follow-up", "guidelines", "guideline",
            }
            core_terms = section_conditions | section_keywords
            # Also include stemmed/decomposed core terms
            expanded_core: set[str] = set(core_terms)
            for t in core_terms:
                if " " in t:
                    for word in t.lower().split():
                        if len(word) > 2 and word not in _stopwords:
                            expanded_core.add(word)
                if len(t) > 3 and t.endswith("s"):
                    expanded_core.add(t[:-1])
            topic_matches = (query_terms & expanded_core) - _generic_terms
            # Also check multi-word conditions/keywords in query
            for term in list(section.applies_to_conditions) + list(section.keywords):
                t = term.lower()
                if " " in t and t in query_lower:
                    topic_matches.add(t)
            if topic_matches:
                topic_score = min(0.35, len(topic_matches) * 0.15)
                scored[idx] += topic_score
                reasons[idx].append(
                    f"Topic match: {', '.join(sorted(topic_matches))}"
                )

            # Condition match: up to +0.25 (scaled by match quality)
            # Uses ConditionMatchingService for tiered matching with
            # compound-term protection and primary-condition gating.
            from app.services.condition_matching_service import match_conditions

            cond_result = match_conditions(
                list(conditions),
                list(section_conditions),
                primary_conditions=section.primary_conditions or None,
                use_hierarchy=False,  # hierarchy is slow; skip in scoring loop
            )
            if cond_result.has_match:
                # Scale score by match quality tier
                best = cond_result.best_score
                n_matches = len(cond_result.matches)
                if best >= 1.0:
                    # Exact match
                    cond_score = min(0.20, n_matches * 0.07)
                    match_display = [m.target_condition for m in cond_result.matches]
                    reasons[idx].append(
                        f"Condition match: {', '.join(sorted(set(match_display)))}"
                    )
                else:
                    # Partial/qualified match
                    cond_score = min(0.15, n_matches * 0.05)
                    match_display = [m.target_condition for m in cond_result.matches]
                    reasons[idx].append(
                        f"Partial condition match: {', '.join(sorted(set(match_display)))}"
                    )
                scored[idx] += cond_score

            # Medication match: up to +0.12 (scaled by match quality)
            medication_overlap = medications & section_medications
            partial_medication_matches: set[str] = set()

            if not medication_overlap:
                for pm in medications:
                    for sm in section_medications:
                        if pm == sm:
                            continue
                        # Check substring matches (e.g., "metformin" in "metformin hcl")
                        if sm in pm or pm in sm:
                            partial_medication_matches.add(f"{pm}~{sm}")

            if medication_overlap:
                med_score = min(0.12, len(medication_overlap) * 0.04)
                scored[idx] += med_score
                reasons[idx].append(
                    f"Medication match: {', '.join(sorted(medication_overlap))}"
                )
            elif partial_medication_matches:
                med_score = min(0.08, len(partial_medication_matches) * 0.03)
                scored[idx] += med_score
                match_display = [m.split('~')[1] for m in partial_medication_matches]
                reasons[idx].append(
                    f"Partial medication match: {', '.join(sorted(set(match_display)))}"
                )

            # Measurement match: up to +0.12 (scaled by match quality)
            measurement_overlap = measurements & section_measurements
            partial_measurement_matches: set[str] = set()

            if not measurement_overlap:
                for pm in measurements:
                    for sm in section_measurements:
                        if pm == sm:
                            continue
                        # Check substring matches (e.g., "a1c" in "hemoglobin a1c")
                        if sm in pm or pm in sm:
                            partial_measurement_matches.add(f"{pm}~{sm}")
                        # Word overlap check
                        pm_words = set(pm.split())
                        sm_words = set(sm.split())
                        if pm_words & sm_words:
                            partial_measurement_matches.add(f"{pm}~{sm}")

            if measurement_overlap:
                meas_score = min(0.12, len(measurement_overlap) * 0.04)
                scored[idx] += meas_score
                reasons[idx].append(
                    f"Measurement match: {', '.join(sorted(measurement_overlap))}"
                )
            elif partial_measurement_matches:
                meas_score = min(0.08, len(partial_measurement_matches) * 0.03)
                scored[idx] += meas_score
                match_display = [m.split('~')[1] for m in partial_measurement_matches]
                reasons[idx].append(
                    f"Partial measurement match: {', '.join(sorted(set(match_display)))}"
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
