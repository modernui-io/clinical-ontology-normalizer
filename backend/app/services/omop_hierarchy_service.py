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
from dataclasses import dataclass, field
from functools import lru_cache
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)

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


class OMOPHierarchyService:
    """Service for OMOP concept hierarchy operations.

    Uses Neo4j to traverse IS_A relationships for semantic matching.
    Falls back to string matching when Neo4j is unavailable.
    """

    def __init__(self) -> None:
        """Initialize the hierarchy service."""
        self._db_service = None
        self._initialized = False
        self._cache_lock = Lock()
        # Simple in-memory cache for frequently accessed concepts
        self._concept_cache: dict[str, list[OMOPConcept]] = {}
        self._ancestor_cache: dict[int, list[OMOPConcept]] = {}

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
        # Check cache first
        cache_key = f"{name.lower()}:{vocabulary_ids}:{domain_ids}"
        with self._cache_lock:
            if cache_key in self._concept_cache:
                return self._concept_cache[cache_key][:limit]

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

            # Cache the results
            with self._cache_lock:
                self._concept_cache[cache_key] = concepts

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
        # Check cache
        with self._cache_lock:
            if concept_id in self._ancestor_cache:
                cached = self._ancestor_cache[concept_id]
                result = [(c, i) for i, c in enumerate(cached)]
                if not include_self and result:
                    result = result[1:]
                return result

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

            # Cache ancestors (just the concepts, not distances)
            with self._cache_lock:
                self._ancestor_cache[concept_id] = [c for c, _ in ancestors]

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

        Args:
            patient_condition: Patient's condition (name or concept_id)
            target_condition: Target condition to match (name or concept_id)
            max_distance: Maximum IS_A hops to consider a match

        Returns:
            HierarchyMatch with match details
        """
        # Resolve concepts
        patient_concept = self._resolve_concept(patient_condition)
        target_concept = self._resolve_concept(target_condition)

        if patient_concept is None or target_concept is None:
            # Fall back to string matching
            return self._string_fallback_match(patient_condition, target_condition)

        # Check exact match
        if patient_concept.concept_id == target_concept.concept_id:
            return HierarchyMatch(
                matched=True,
                patient_concept=patient_concept,
                target_concept=target_concept,
                distance=0,
                match_type="exact",
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
                )

        # No hierarchy match
        return HierarchyMatch(
            matched=False,
            patient_concept=patient_concept,
            target_concept=target_concept,
            match_type="none",
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

        Args:
            patient_condition: Patient condition
            target_condition: Target condition

        Returns:
            HierarchyMatch based on string similarity
        """
        patient_str = str(patient_condition).lower()
        target_str = str(target_condition).lower()

        # Exact match
        if patient_str == target_str:
            return HierarchyMatch(matched=True, distance=0, match_type="exact")

        # Substring match
        if target_str in patient_str or patient_str in target_str:
            return HierarchyMatch(matched=True, distance=1, match_type="substring")

        # Word overlap
        patient_words = set(patient_str.split())
        target_words = set(target_str.split())
        common = patient_words & target_words
        if any(len(w) > 3 for w in common):
            return HierarchyMatch(matched=True, distance=2, match_type="word_overlap")

        return HierarchyMatch(matched=False, match_type="none")

    def clear_cache(self) -> None:
        """Clear the concept caches."""
        with self._cache_lock:
            self._concept_cache.clear()
            self._ancestor_cache.clear()
        logger.info("OMOP hierarchy cache cleared")


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
