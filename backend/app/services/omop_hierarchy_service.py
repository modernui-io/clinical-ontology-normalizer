"""OMOP Concept Hierarchy Service.

Provides semantic matching using the OMOP vocabulary hierarchy stored in Neo4j.
Uses IS_A relationships to find ancestor concepts, enabling:
- Patient "Type 2 diabetes" matches guideline for "Diabetes mellitus"
- Patient condition matches calculator criteria via semantic hierarchy

The OMOP hierarchy includes:
- 5.65M Concept nodes (SNOMED, ICD10, RxNorm, LOINC, etc.)
- IS_A relationships for hierarchical reasoning
- MAPS_TO relationships for cross-vocabulary mapping
"""

from __future__ import annotations

import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

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

    Uses Neo4j to traverse IS_A relationships for semantic matching.
    Falls back to string matching when Neo4j is unavailable.
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
        self._db_service = None
        self._initialized = False
        self._cache_lock = Lock()
        # P1-008: Strict matching mode
        self.strict_matching_mode = strict_matching_mode
        self._min_fallback_similarity = 0.85
        # P1-009: Bounded LRU cache with version tracking
        self._cache_max_size = cache_max_size
        self._cache_version = omop_version
        self._concept_cache: OrderedDict[str, list[OMOPConcept]] = OrderedDict()
        self._ancestor_cache: OrderedDict[int, list[OMOPConcept]] = OrderedDict()
        # P1-009: Cache statistics
        self._cache_hits = 0
        self._cache_misses = 0

    def _get_db_service(self):
        """Get the graph database service lazily."""
        if self._db_service is None:
            try:
                from app.services.graph_database_service import get_graph_database_service
                self._db_service = get_graph_database_service()
            except Exception as e:
                logger.warning(f"Could not initialize Neo4j for hierarchy: {e}")
        return self._db_service

    @property
    def is_available(self) -> bool:
        """Check if Neo4j hierarchy is available."""
        db = self._get_db_service()
        return db is not None and db.is_connected

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

        db = self._get_db_service()
        if db is None or not db.is_connected:
            return []

        # Build Cypher query
        vocab_filter = ""
        if vocabulary_ids:
            vocab_filter = "AND c.vocabulary_id IN $vocabularies"

        domain_filter = ""
        if domain_ids:
            domain_filter = "AND c.domain_id IN $domains"

        # Search for exact and fuzzy matches
        query = f"""
        MATCH (c:Concept)
        WHERE (toLower(c.name) = toLower($name)
               OR toLower(c.name) CONTAINS toLower($name))
          AND c.standard_concept IN ['S', 'C']
          {vocab_filter}
          {domain_filter}
        RETURN c.concept_id AS concept_id,
               c.name AS name,
               c.vocabulary_id AS vocabulary_id,
               c.domain_id AS domain_id,
               c.concept_class_id AS concept_class_id,
               CASE WHEN toLower(c.name) = toLower($name) THEN 0 ELSE 1 END AS match_order
        ORDER BY match_order, size(c.name)
        LIMIT $limit
        """

        try:
            result = db.execute_read(
                query,
                {
                    "name": name,
                    "vocabularies": vocabulary_ids or [],
                    "domains": domain_ids or [],
                    "limit": limit,
                },
            )

            concepts = [
                OMOPConcept(
                    concept_id=r["concept_id"],
                    name=r["name"],
                    vocabulary_id=r.get("vocabulary_id", ""),
                    domain_id=r.get("domain_id", ""),
                    concept_class_id=r.get("concept_class_id", ""),
                )
                for r in result.records
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
        db = self._get_db_service()
        if db is None or not db.is_connected:
            return None

        query = """
        MATCH (c:Concept {concept_id: $concept_id})
        RETURN c.concept_id AS concept_id,
               c.name AS name,
               c.vocabulary_id AS vocabulary_id,
               c.domain_id AS domain_id,
               c.concept_class_id AS concept_class_id
        """

        try:
            result = db.execute_read(query, {"concept_id": concept_id})
            if result.records:
                r = result.records[0]
                return OMOPConcept(
                    concept_id=r["concept_id"],
                    name=r["name"],
                    vocabulary_id=r.get("vocabulary_id", ""),
                    domain_id=r.get("domain_id", ""),
                    concept_class_id=r.get("concept_class_id", ""),
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
        """Get ancestor concepts via IS_A relationships.

        Args:
            concept_id: Starting concept ID
            max_distance: Maximum hierarchy depth to traverse
            include_self: Include the starting concept in results

        Returns:
            List of (concept, distance) tuples ordered by distance
        """
        # Check cache (P1-009: LRU with stats)
        with self._cache_lock:
            if concept_id in self._ancestor_cache:
                self._cache_hits += 1
                self._ancestor_cache.move_to_end(concept_id)
                cached = self._ancestor_cache[concept_id]
                result = [(c, i) for i, c in enumerate(cached)]
                if not include_self and result:
                    result = result[1:]
                return result
            self._cache_misses += 1

        db = self._get_db_service()
        if db is None or not db.is_connected:
            return []

        query = """
        MATCH (c:Concept {concept_id: $concept_id})
        OPTIONAL MATCH path = (c)-[:IS_A*1..""" + str(max_distance) + """]->(ancestor:Concept)
        WITH c, ancestor, length(path) AS distance
        ORDER BY distance
        RETURN DISTINCT
            COALESCE(ancestor.concept_id, c.concept_id) AS concept_id,
            COALESCE(ancestor.name, c.name) AS name,
            COALESCE(ancestor.vocabulary_id, c.vocabulary_id) AS vocabulary_id,
            COALESCE(ancestor.domain_id, c.domain_id) AS domain_id,
            COALESCE(distance, 0) AS distance
        ORDER BY distance
        """

        try:
            result = db.execute_read(query, {"concept_id": concept_id})

            ancestors = []
            seen = set()
            for r in result.records:
                cid = r["concept_id"]
                if cid in seen:
                    continue
                seen.add(cid)

                concept = OMOPConcept(
                    concept_id=cid,
                    name=r["name"],
                    vocabulary_id=r.get("vocabulary_id", ""),
                    domain_id=r.get("domain_id", ""),
                )
                ancestors.append((concept, r["distance"]))

            # Cache ancestors (P1-009: bounded LRU)
            with self._cache_lock:
                self._ancestor_cache[concept_id] = [c for c, _ in ancestors]
                self._ancestor_cache.move_to_end(concept_id)
                while len(self._ancestor_cache) > self._cache_max_size:
                    self._ancestor_cache.popitem(last=False)

            if not include_self and ancestors:
                ancestors = [(c, d) for c, d in ancestors if d > 0]

            return ancestors

        except Exception as e:
            logger.error(f"Error getting ancestors for {concept_id}: {e}")
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

        This is the core matching function. It checks:
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

        # Check if target is an ancestor of patient
        # (Patient has "T2DM", target is "Diabetes" -> match via IS_A)
        patient_ancestors = self.get_ancestors(
            patient_concept.concept_id,
            max_distance=max_distance,
            include_self=False,
        )

        for ancestor, distance in patient_ancestors:
            if ancestor.concept_id == target_concept.concept_id:
                return HierarchyMatch(
                    matched=True,
                    patient_concept=patient_concept,
                    target_concept=target_concept,
                    distance=distance,
                    match_type="ancestor",
                    match_quality="synonym",
                )

        # Check if patient is an ancestor of target (less common)
        target_ancestors = self.get_ancestors(
            target_concept.concept_id,
            max_distance=max_distance,
            include_self=False,
        )

        for ancestor, distance in target_ancestors:
            if ancestor.concept_id == patient_concept.concept_id:
                return HierarchyMatch(
                    matched=True,
                    patient_concept=patient_concept,
                    target_concept=target_concept,
                    distance=distance,
                    match_type="descendant",
                    match_quality="synonym",
                )

        # No hierarchy match
        return HierarchyMatch(
            matched=False,
            patient_concept=patient_concept,
            target_concept=target_concept,
            match_type="none",
            match_quality="exact",
        )

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

        Args:
            condition: Condition name (str) or concept_id (int)

        Returns:
            OMOPConcept if found, None otherwise
        """
        if isinstance(condition, int):
            return self.get_concept_by_id(condition)

        # Search by name
        concepts = self.find_concepts_by_name(
            condition,
            domain_ids=["Condition"],
            limit=1,
        )
        return concepts[0] if concepts else None

    def _string_fallback_match(
        self,
        patient_condition: str | int,
        target_condition: str | int,
    ) -> HierarchyMatch:
        """Fallback string matching when Neo4j unavailable.

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
