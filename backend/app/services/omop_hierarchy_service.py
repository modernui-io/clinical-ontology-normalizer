"""OMOP Concept Hierarchy Service.

Provides semantic matching using the OMOP vocabulary hierarchy stored in
PostgreSQL via the pre-computed concept_ancestor closure table.

Uses the closure table for O(1) ancestor/descendant lookups, enabling:
- Patient "Type 2 diabetes" matches guideline for "Diabetes mellitus"
- Patient condition matches calculator criteria via semantic hierarchy
- Cross-vocabulary mapping via "Maps to" relationships

The OMOP hierarchy includes:
- 5.65M Concept nodes (SNOMED, ICD10, RxNorm, LOINC, etc.)
- concept_ancestor closure table for hierarchical reasoning
- concept_relationship "Maps to" for cross-vocabulary mapping
"""

from __future__ import annotations

import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# P1-009: Bounded cache constants
_CACHE_MAX_SIZE = 10_000
_DEFAULT_OMOP_VERSION = "v5.4"

# Singleton instance
_omop_hierarchy_service: "OMOPHierarchyService | None" = None
_service_lock = Lock()


@dataclass
class OMOPConcept:
    """An OMOP vocabulary concept."""

    concept_id: int
    name: str
    vocabulary_id: str = ""
    domain_id: str = ""
    concept_class_id: str = ""

    def __hash__(self) -> int:
        return hash(self.concept_id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, OMOPConcept):
            return False
        return self.concept_id == other.concept_id


@dataclass
class HierarchyMatch:
    """Result of a hierarchy-based match."""

    matched: bool
    patient_concept: OMOPConcept | None = None
    target_concept: OMOPConcept | None = None
    distance: int = 0  # 0 = exact, 1+ = via IS_A
    path: list[OMOPConcept] = field(default_factory=list)
    match_type: str = "none"  # exact, ancestor, descendant, mapped
    # P1-008: match quality tier for downstream consumers
    match_quality: str = "exact"  # exact | synonym | fuzzy | fallback


@dataclass
class CacheStats:
    """P1-009: Cache statistics."""

    hits: int = 0
    misses: int = 0
    size: int = 0
    max_size: int = _CACHE_MAX_SIZE
    omop_version: str = _DEFAULT_OMOP_VERSION

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class OMOPHierarchyService:
    """Service for OMOP concept hierarchy operations.

    Uses PostgreSQL concept_ancestor closure table for O(1) hierarchy lookups.
    Falls back to string matching when PostgreSQL is unavailable.
    """

    def __init__(
        self,
        *,
        strict_matching_mode: bool = True,
        omop_version: str = _DEFAULT_OMOP_VERSION,
        cache_max_size: int = _CACHE_MAX_SIZE,
    ) -> None:
        """Initialize the hierarchy service.

        Args:
            strict_matching_mode: P1-008 - when True, disables fuzzy/substring
                fallback matching and requires minimum 0.85 similarity for any
                fallback match. Default True in production.
            omop_version: P1-009 - OMOP vocabulary version for cache
                invalidation tracking.
            cache_max_size: P1-009 - maximum number of entries in each cache
                (concept cache and ancestor cache independently bounded).
        """
        self._engine = None
        self._initialized = False
        self._cache_lock = Lock()
        # P1-008: Strict matching mode
        self.strict_matching_mode = strict_matching_mode
        self._min_fallback_similarity = 0.85
        # P1-009: Bounded LRU cache with version tracking
        self._cache_max_size = cache_max_size
        self._cache_version = omop_version
        self._concept_cache: OrderedDict[str, list[OMOPConcept]] = OrderedDict()
        self._ancestor_cache: OrderedDict[int, list[tuple[OMOPConcept, int]]] = OrderedDict()
        # P1-009: Cache statistics
        self._cache_hits = 0
        self._cache_misses = 0

    def _get_engine(self):
        """Get the PostgreSQL sync engine lazily."""
        if self._engine is None:
            try:
                from app.core.database import get_sync_engine
                self._engine = get_sync_engine()
            except Exception as e:
                logger.warning(f"Could not get PostgreSQL engine for hierarchy: {e}")
        return self._engine

    @property
    def is_available(self) -> bool:
        """Check if PostgreSQL hierarchy (concept_ancestor) is available."""
        engine = self._get_engine()
        if engine is None:
            return False
        try:
            with Session(engine) as session:
                row = session.execute(
                    text("SELECT 1 FROM omop_concept_ancestor LIMIT 1")
                ).fetchone()
                return row is not None
        except Exception:
            return False

    def find_concepts_by_name(
        self,
        name: str,
        vocabulary_ids: list[str] | None = None,
        domain_ids: list[str] | None = None,
        limit: int = 10,
    ) -> list[OMOPConcept]:
        """Find OMOP concepts by name (case-insensitive).

        Args:
            name: Concept name to search for
            vocabulary_ids: Optional filter by vocabulary (SNOMED, ICD10CM, etc.)
            domain_ids: Optional filter by domain (Condition, Drug, etc.)
            limit: Maximum results to return

        Returns:
            List of matching OMOPConcept objects
        """
        # Check cache first (P1-009: LRU with stats)
        cache_key = f"{name.lower()}:{vocabulary_ids}:{domain_ids}"
        with self._cache_lock:
            if cache_key in self._concept_cache:
                self._cache_hits += 1
                # Move to end for LRU ordering
                self._concept_cache.move_to_end(cache_key)
                return self._concept_cache[cache_key][:limit]
            self._cache_misses += 1

        engine = self._get_engine()
        if engine is None:
            return []

        params: dict[str, Any] = {
            "name": name,
            "pattern": f"%{name}%",
            "limit": limit,
            "no_vocab_filter": vocabulary_ids is None,
            "no_domain_filter": domain_ids is None,
            "vocabularies": vocabulary_ids or [],
            "domains": domain_ids or [],
        }

        sql = text("""
            SELECT concept_id, concept_name, vocabulary_id, domain_id, concept_class_id
            FROM omop_concept
            WHERE (LOWER(concept_name) = LOWER(:name) OR concept_name ILIKE :pattern)
              AND standard_concept IN ('S', 'C')
              AND (:no_vocab_filter OR vocabulary_id = ANY(:vocabularies))
              AND (:no_domain_filter OR domain_id = ANY(:domains))
            ORDER BY
                CASE WHEN LOWER(concept_name) = LOWER(:name) THEN 0 ELSE 1 END,
                LENGTH(concept_name)
            LIMIT :limit
        """)

        try:
            with Session(engine) as session:
                rows = session.execute(sql, params).fetchall()

            concepts = [
                OMOPConcept(
                    concept_id=r.concept_id,
                    name=r.concept_name,
                    vocabulary_id=r.vocabulary_id or "",
                    domain_id=r.domain_id or "",
                    concept_class_id=r.concept_class_id or "",
                )
                for r in rows
            ]

            # Cache the results (P1-009: bounded LRU)
            with self._cache_lock:
                self._concept_cache[cache_key] = concepts
                self._concept_cache.move_to_end(cache_key)
                while len(self._concept_cache) > self._cache_max_size:
                    self._concept_cache.popitem(last=False)

            return concepts[:limit]

        except Exception as e:
            logger.error(f"Error finding concepts by name '{name}': {e}")
            return []

    def get_concept_by_id(self, concept_id: int) -> OMOPConcept | None:
        """Get a concept by its OMOP concept_id.

        Args:
            concept_id: The OMOP concept ID

        Returns:
            OMOPConcept if found, None otherwise
        """
        engine = self._get_engine()
        if engine is None:
            return None

        sql = text("""
            SELECT concept_id, concept_name, vocabulary_id, domain_id, concept_class_id
            FROM omop_concept
            WHERE concept_id = :concept_id
        """)

        try:
            with Session(engine) as session:
                row = session.execute(sql, {"concept_id": concept_id}).fetchone()

            if row:
                return OMOPConcept(
                    concept_id=row.concept_id,
                    name=row.concept_name,
                    vocabulary_id=row.vocabulary_id or "",
                    domain_id=row.domain_id or "",
                    concept_class_id=row.concept_class_id or "",
                )
            return None
        except Exception as e:
            logger.error(f"Error getting concept {concept_id}: {e}")
            return None

    def get_ancestors(
        self,
        concept_id: int,
        max_distance: int = 5,
        include_self: bool = True,
    ) -> list[tuple[OMOPConcept, int]]:
        """Get ancestor concepts via the concept_ancestor closure table.

        Args:
            concept_id: Starting concept ID
            max_distance: Maximum hierarchy depth to traverse
            include_self: Include the starting concept in results

        Returns:
            List of (concept, distance) tuples ordered by distance
        """
        # Check cache (P1-009: LRU with stats)
        cache_key = concept_id
        with self._cache_lock:
            if cache_key in self._ancestor_cache:
                self._cache_hits += 1
                self._ancestor_cache.move_to_end(cache_key)
                cached = self._ancestor_cache[cache_key]
                if not include_self:
                    return [(c, d) for c, d in cached if d > 0]
                return [
                    (c, d) for c, d in cached if d <= max_distance
                ]
            self._cache_misses += 1

        engine = self._get_engine()
        if engine is None:
            return []

        sql = text("""
            SELECT c.concept_id, c.concept_name, c.vocabulary_id,
                   c.domain_id, c.concept_class_id,
                   ca.min_levels_of_separation AS distance
            FROM omop_concept_ancestor ca
            JOIN omop_concept c ON c.concept_id = ca.ancestor_concept_id
            WHERE ca.descendant_concept_id = :concept_id
              AND ca.min_levels_of_separation <= :max_distance
            ORDER BY ca.min_levels_of_separation
        """)

        try:
            with Session(engine) as session:
                rows = session.execute(
                    sql, {"concept_id": concept_id, "max_distance": max_distance}
                ).fetchall()

            ancestors: list[tuple[OMOPConcept, int]] = []
            seen: set[int] = set()
            for r in rows:
                cid = r.concept_id
                if cid in seen:
                    continue
                seen.add(cid)
                concept = OMOPConcept(
                    concept_id=cid,
                    name=r.concept_name,
                    vocabulary_id=r.vocabulary_id or "",
                    domain_id=r.domain_id or "",
                    concept_class_id=r.concept_class_id or "",
                )
                ancestors.append((concept, r.distance))

            # Cache ancestors (P1-009: bounded LRU)
            with self._cache_lock:
                self._ancestor_cache[cache_key] = ancestors
                self._ancestor_cache.move_to_end(cache_key)
                while len(self._ancestor_cache) > self._cache_max_size:
                    self._ancestor_cache.popitem(last=False)

            if not include_self:
                ancestors = [(c, d) for c, d in ancestors if d > 0]

            return ancestors

        except Exception as e:
            logger.error(f"Error getting ancestors for {concept_id}: {e}")
            return []

    def get_descendants(
        self,
        concept_id: int,
        max_distance: int = 5,
        include_self: bool = True,
    ) -> list[tuple[OMOPConcept, int]]:
        """Get descendant concepts via the concept_ancestor closure table.

        Args:
            concept_id: Starting concept ID
            max_distance: Maximum hierarchy depth to traverse
            include_self: Include the starting concept in results

        Returns:
            List of (concept, distance) tuples ordered by distance
        """
        engine = self._get_engine()
        if engine is None:
            return []

        sql = text("""
            SELECT c.concept_id, c.concept_name, c.vocabulary_id,
                   c.domain_id, c.concept_class_id,
                   ca.min_levels_of_separation AS distance
            FROM omop_concept_ancestor ca
            JOIN omop_concept c ON c.concept_id = ca.descendant_concept_id
            WHERE ca.ancestor_concept_id = :concept_id
              AND ca.min_levels_of_separation <= :max_distance
            ORDER BY ca.min_levels_of_separation
        """)

        try:
            with Session(engine) as session:
                rows = session.execute(
                    sql, {"concept_id": concept_id, "max_distance": max_distance}
                ).fetchall()

            descendants: list[tuple[OMOPConcept, int]] = []
            seen: set[int] = set()
            for r in rows:
                cid = r.concept_id
                if cid in seen:
                    continue
                seen.add(cid)
                concept = OMOPConcept(
                    concept_id=cid,
                    name=r.concept_name,
                    vocabulary_id=r.vocabulary_id or "",
                    domain_id=r.domain_id or "",
                    concept_class_id=r.concept_class_id or "",
                )
                descendants.append((concept, r.distance))

            if not include_self:
                descendants = [(c, d) for c, d in descendants if d > 0]

            return descendants

        except Exception as e:
            logger.error(f"Error getting descendants for {concept_id}: {e}")
            return []

    def get_ancestor_names(
        self,
        concept_id: int,
        max_distance: int = 5,
        include_self: bool = True,
    ) -> list[str]:
        """Get ancestor concept names for easy string matching.

        Args:
            concept_id: Starting concept ID
            max_distance: Maximum hierarchy depth
            include_self: Include starting concept name

        Returns:
            List of ancestor concept names (lowercase)
        """
        ancestors = self.get_ancestors(concept_id, max_distance, include_self)
        return [c.name.lower() for c, _ in ancestors]

    def check_hierarchy_match(
        self,
        patient_condition: str | int,
        target_condition: str | int,
        max_distance: int = 3,
    ) -> HierarchyMatch:
        """Check if patient condition matches target via hierarchy.

        Uses a single bidirectional query against the concept_ancestor closure
        table for O(1) lookup. Checks:
        1. Exact match (same concept)
        2. Patient condition IS_A target (patient has specific, target is general)
        3. Target IS_A patient condition (less common, target is specific)

        P1-008: When strict_matching_mode is on, fallback string matching
        requires minimum 0.85 similarity threshold.

        Args:
            patient_condition: Patient's condition (name or concept_id)
            target_condition: Target condition to match (name or concept_id)
            max_distance: Maximum IS_A hops to consider a match

        Returns:
            HierarchyMatch with match details and match_quality field
        """
        # Resolve concepts
        patient_concept = self._resolve_concept(patient_condition)
        target_concept = self._resolve_concept(target_condition)

        if patient_concept is None or target_concept is None:
            # Fall back to string matching (P1-008: strict mode applies)
            return self._string_fallback_match(patient_condition, target_condition)

        # Check exact match
        if patient_concept.concept_id == target_concept.concept_id:
            return HierarchyMatch(
                matched=True,
                patient_concept=patient_concept,
                target_concept=target_concept,
                distance=0,
                match_type="exact",
                match_quality="exact",
            )

        # Single bidirectional query against closure table
        engine = self._get_engine()
        if engine is not None:
            sql = text("""
                SELECT ancestor_concept_id, descendant_concept_id,
                       min_levels_of_separation
                FROM omop_concept_ancestor
                WHERE (
                    (descendant_concept_id = :patient_id
                     AND ancestor_concept_id = :target_id)
                    OR
                    (descendant_concept_id = :target_id
                     AND ancestor_concept_id = :patient_id)
                )
                AND min_levels_of_separation <= :max_distance
                AND min_levels_of_separation > 0
                ORDER BY min_levels_of_separation
                LIMIT 1
            """)

            try:
                with Session(engine) as session:
                    row = session.execute(
                        sql,
                        {
                            "patient_id": patient_concept.concept_id,
                            "target_id": target_concept.concept_id,
                            "max_distance": max_distance,
                        },
                    ).fetchone()

                if row:
                    distance = row.min_levels_of_separation
                    # Determine direction
                    if row.descendant_concept_id == patient_concept.concept_id:
                        match_type = "ancestor"
                    else:
                        match_type = "descendant"

                    # Distance-weighted quality
                    match_quality = self._distance_to_quality(distance)

                    return HierarchyMatch(
                        matched=True,
                        patient_concept=patient_concept,
                        target_concept=target_concept,
                        distance=distance,
                        match_type=match_type,
                        match_quality=match_quality,
                    )
            except Exception as e:
                logger.error(
                    f"Error checking hierarchy match {patient_condition} "
                    f"vs {target_condition}: {e}"
                )

        # No hierarchy match
        return HierarchyMatch(
            matched=False,
            patient_concept=patient_concept,
            target_concept=target_concept,
            match_type="none",
            match_quality="exact",
        )

    @staticmethod
    def _distance_to_quality(distance: int) -> str:
        """Map hierarchy distance to match quality tier.

        Args:
            distance: Number of hops in the hierarchy

        Returns:
            Quality tier: "exact", "synonym", or "fuzzy"
        """
        if distance == 0:
            return "exact"
        if distance <= 2:
            return "synonym"
        return "fuzzy"

    def expand_condition_names(
        self,
        condition_name: str,
        max_distance: int = 3,
    ) -> set[str]:
        """Expand a condition name to include ancestor names.

        Useful for matching - if patient has "type 2 diabetes mellitus",
        this returns {"type 2 diabetes mellitus", "diabetes mellitus",
        "disorder of glucose metabolism", ...}

        Args:
            condition_name: Condition name to expand
            max_distance: Maximum hierarchy depth

        Returns:
            Set of condition names (all lowercase)
        """
        expanded = {condition_name.lower()}

        # Try to find the concept
        concepts = self.find_concepts_by_name(
            condition_name,
            domain_ids=["Condition"],
            limit=1,
        )

        if not concepts:
            return expanded

        # Get ancestor names
        ancestor_names = self.get_ancestor_names(
            concepts[0].concept_id,
            max_distance=max_distance,
            include_self=True,
        )

        expanded.update(ancestor_names)
        return expanded

    def get_matching_conditions(
        self,
        patient_conditions: list[str | int],
        target_conditions: list[str],
        max_distance: int = 3,
    ) -> dict[str, list[HierarchyMatch]]:
        """Find all matches between patient conditions and targets.

        Args:
            patient_conditions: List of patient conditions (names or IDs)
            target_conditions: List of target condition names
            max_distance: Maximum hierarchy depth

        Returns:
            Dict mapping target condition to list of matches
        """
        matches: dict[str, list[HierarchyMatch]] = {t: [] for t in target_conditions}

        for patient_cond in patient_conditions:
            for target_cond in target_conditions:
                match = self.check_hierarchy_match(
                    patient_cond, target_cond, max_distance
                )
                if match.matched:
                    matches[target_cond].append(match)

        return matches

    def _resolve_concept(self, condition: str | int) -> OMOPConcept | None:
        """Resolve a condition to an OMOPConcept.

        Searches without domain restriction so the service works for drugs,
        measurements, procedures, etc. If the initial lookup returns a
        non-standard concept, chases "Maps to" to find the standard concept.

        Args:
            condition: Condition name (str) or concept_id (int)

        Returns:
            OMOPConcept if found, None otherwise
        """
        if isinstance(condition, int):
            concept = self.get_concept_by_id(condition)
            if concept is not None:
                # Chase "Maps to" for non-standard concepts
                mapped = self._resolve_via_maps_to(concept.concept_id)
                if mapped is not None:
                    return self.get_concept_by_id(mapped)
            return concept

        # Search by name — no hard-coded domain filter
        concepts = self.find_concepts_by_name(condition, limit=1)
        if not concepts:
            return None

        concept = concepts[0]
        # Chase "Maps to" for non-standard concepts
        mapped = self._resolve_via_maps_to(concept.concept_id)
        if mapped is not None:
            return self.get_concept_by_id(mapped)
        return concept

    def _resolve_via_maps_to(self, concept_id: int) -> int | None:
        """Follow "Maps to" relationship to find standard concept.

        Returns the target standard concept_id if the source concept maps to
        a different standard concept, None if already standard or no mapping.

        Args:
            concept_id: Source concept ID

        Returns:
            Standard concept_id if mapped, None otherwise
        """
        engine = self._get_engine()
        if engine is None:
            return None

        sql = text("""
            SELECT cr.concept_id_2
            FROM omop_concept_relationship cr
            JOIN omop_concept c ON c.concept_id = cr.concept_id_2
            WHERE cr.concept_id_1 = :concept_id
              AND cr.relationship_id = 'Maps to'
              AND cr.invalid_reason IS NULL
              AND c.standard_concept = 'S'
              AND cr.concept_id_2 != :concept_id
            LIMIT 1
        """)

        try:
            with Session(engine) as session:
                row = session.execute(sql, {"concept_id": concept_id}).fetchone()
            if row:
                return row.concept_id_2
            return None
        except Exception as e:
            logger.warning(f"Error resolving Maps to for {concept_id}: {e}")
            return None

    def _string_fallback_match(
        self,
        patient_condition: str | int,
        target_condition: str | int,
    ) -> HierarchyMatch:
        """Fallback string matching when PostgreSQL unavailable.

        P1-008: When strict_matching_mode is True, fuzzy/substring fallback
        matching is disabled. Only exact string matches are accepted. Matches
        that would have been accepted in non-strict mode are logged as warnings.

        Args:
            patient_condition: Patient condition
            target_condition: Target condition

        Returns:
            HierarchyMatch based on string similarity
        """
        patient_str = str(patient_condition).lower()
        target_str = str(target_condition).lower()

        # Exact string match - always accepted
        if patient_str == target_str:
            return HierarchyMatch(
                matched=True, distance=0, match_type="exact", match_quality="exact",
            )

        # Compute similarity for strict mode threshold check
        similarity = self._compute_string_similarity(patient_str, target_str)

        # Substring match
        if target_str in patient_str or patient_str in target_str:
            if self.strict_matching_mode:
                if similarity >= self._min_fallback_similarity:
                    return HierarchyMatch(
                        matched=True,
                        distance=1,
                        match_type="substring",
                        match_quality="fuzzy",
                    )
                else:
                    logger.warning(
                        "P1-008 strict mode: rejected substring fallback match "
                        "'%s' vs '%s' (similarity=%.2f < %.2f threshold)",
                        patient_condition,
                        target_condition,
                        similarity,
                        self._min_fallback_similarity,
                    )
                    return HierarchyMatch(
                        matched=False,
                        match_type="substring",
                        match_quality="fallback",
                    )
            return HierarchyMatch(
                matched=True, distance=1, match_type="substring", match_quality="fuzzy",
            )

        # Word overlap
        patient_words = set(patient_str.split())
        target_words = set(target_str.split())
        common = patient_words & target_words
        if any(len(w) > 3 for w in common):
            if self.strict_matching_mode:
                logger.warning(
                    "P1-008 strict mode: rejected word-overlap fallback match "
                    "'%s' vs '%s' (similarity=%.2f < %.2f threshold)",
                    patient_condition,
                    target_condition,
                    similarity,
                    self._min_fallback_similarity,
                )
                return HierarchyMatch(
                    matched=False,
                    match_type="word_overlap",
                    match_quality="fallback",
                )
            return HierarchyMatch(
                matched=True, distance=2, match_type="word_overlap", match_quality="fallback",
            )

        return HierarchyMatch(matched=False, match_type="none", match_quality="exact")

    @staticmethod
    def _compute_string_similarity(a: str, b: str) -> float:
        """Compute simple string similarity (Jaccard on character bigrams).

        Returns a score between 0.0 and 1.0.
        """
        if not a or not b:
            return 0.0
        bigrams_a = {a[i : i + 2] for i in range(len(a) - 1)} if len(a) > 1 else {a}
        bigrams_b = {b[i : i + 2] for i in range(len(b) - 1)} if len(b) > 1 else {b}
        intersection = bigrams_a & bigrams_b
        union = bigrams_a | bigrams_b
        return len(intersection) / len(union) if union else 0.0

    def clear_cache(self) -> None:
        """Clear the concept caches and reset stats."""
        with self._cache_lock:
            self._concept_cache.clear()
            self._ancestor_cache.clear()
            self._cache_hits = 0
            self._cache_misses = 0
        logger.info("OMOP hierarchy cache cleared")

    def invalidate_cache(self) -> None:
        """P1-009: Invalidate cache (alias for clear_cache with logging)."""
        logger.info(
            "OMOP cache invalidated (version=%s, entries=%d)",
            self._cache_version,
            len(self._concept_cache) + len(self._ancestor_cache),
        )
        self.clear_cache()

    def get_cache_stats(self) -> CacheStats:
        """P1-009: Return cache hit/miss counts and size."""
        with self._cache_lock:
            return CacheStats(
                hits=self._cache_hits,
                misses=self._cache_misses,
                size=len(self._concept_cache) + len(self._ancestor_cache),
                max_size=self._cache_max_size,
                omop_version=self._cache_version,
            )

    def set_omop_version(self, version: str) -> None:
        """P1-009: Update the OMOP version; auto-invalidates if changed.

        Args:
            version: New OMOP vocabulary version string.
        """
        if version != self._cache_version:
            logger.info(
                "OMOP version changed from %s to %s - invalidating cache",
                self._cache_version,
                version,
            )
            self._cache_version = version
            self.invalidate_cache()


def get_omop_hierarchy_service() -> OMOPHierarchyService:
    """Get the singleton OMOPHierarchyService instance.

    Returns:
        The OMOPHierarchyService singleton.
    """
    global _omop_hierarchy_service

    if _omop_hierarchy_service is None:
        with _service_lock:
            if _omop_hierarchy_service is None:
                _omop_hierarchy_service = OMOPHierarchyService()

    return _omop_hierarchy_service


def reset_omop_hierarchy_service() -> None:
    """Reset the singleton for testing."""
    global _omop_hierarchy_service

    with _service_lock:
        if _omop_hierarchy_service is not None:
            _omop_hierarchy_service.clear_cache()
            _omop_hierarchy_service = None
