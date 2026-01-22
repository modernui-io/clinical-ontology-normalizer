"""SNOMED CT Service for Clinical Ontology Normalizer.

This module provides SNOMED CT concept lookup and matching services:
- Concept lookup by code or name
- Synonym matching for clinical terms
- Hierarchy navigation (is-a relationships)
- Cross-mapping to ICD-10 codes

SNOMED CT is a comprehensive clinical terminology system covering:
- Clinical findings/disorders
- Procedures
- Body structures
- Substances
- Organisms
- And more

Note: This service requires proper SNOMED CT licensing for production use.
"""

from dataclasses import dataclass, field
from enum import Enum
import json
import logging
from pathlib import Path
import re
import threading
from typing import Any

from app.services.trie_index import TrieIndex, MatchResult as TrieMatchResult

logger = logging.getLogger(__name__)


class SemanticType(Enum):
    """SNOMED CT semantic types (concept categories)."""

    CLINICAL_FINDING = "Clinical Finding"
    DISORDER = "Disorder"
    PROCEDURE = "Procedure"
    BODY_STRUCTURE = "Body Structure"
    SUBSTANCE = "Substance"
    ORGANISM = "Organism"
    OBSERVABLE = "Observable Entity"
    QUALIFIER = "Qualifier Value"
    MORPHOLOGY = "Morphologic Abnormality"
    SITUATION = "Situation"
    EVENT = "Event"
    PHYSICAL_OBJECT = "Physical Object"
    SPECIMEN = "Specimen"
    DRUG = "Pharmaceutical/Biologic Product"
    UNKNOWN = "Unknown"


class MatchConfidence(Enum):
    """Confidence level for concept matches."""

    EXACT = "exact"  # Exact code or synonym match
    HIGH = "high"  # Very close match
    MEDIUM = "medium"  # Good match but may need verification
    LOW = "low"  # Possible match, needs review


@dataclass
class SNOMEDConcept:
    """A SNOMED CT concept with metadata."""

    concept_id: str  # SNOMED CT ID (numeric)
    concept_code: str  # Same as concept_id for SNOMED
    concept_name: str  # Fully Specified Name (FSN) or preferred term
    semantic_type: SemanticType
    domain_id: str  # OMOP domain (Condition, Procedure, etc.)
    is_standard: bool = True  # Is this a standard SNOMED concept
    synonyms: list[str] = field(default_factory=list)
    parent_codes: list[str] = field(default_factory=list)  # Is-a relationships
    child_codes: list[str] = field(default_factory=list)  # Inverse is-a
    icd10_mappings: list[str] = field(default_factory=list)  # ICD-10-CM cross-maps
    omop_concept_id: int | None = None


@dataclass
class ConceptMatch:
    """A matched SNOMED CT concept with confidence."""

    concept: SNOMEDConcept
    confidence: MatchConfidence
    match_type: str  # How the match was made (exact, synonym, partial, etc.)
    matched_term: str  # The term that matched
    score: float = 1.0  # Numeric score for ranking


@dataclass
class HierarchyResult:
    """Result of hierarchy navigation."""

    concept: SNOMEDConcept
    ancestors: list[SNOMEDConcept]  # Parent concepts (is-a)
    descendants: list[SNOMEDConcept]  # Child concepts
    siblings: list[SNOMEDConcept]  # Same parent concepts


@dataclass
class CrossMapResult:
    """Result of cross-mapping to ICD-10."""

    snomed_concept: SNOMEDConcept
    icd10_codes: list[str]
    map_type: str  # "exact", "broader", "narrower", "equivalent"


# ============================================================================
# Fixture Path
# ============================================================================

SNOMED_FIXTURE_FILE = Path(__file__).parent.parent.parent / "fixtures" / "snomed_codes.json"
SNOMED_CONCEPTS_FILE = Path(__file__).parent.parent.parent / "fixtures" / "snomed_concepts.json"


# ============================================================================
# Singleton Instance
# ============================================================================

_snomed_service: "SNOMEDService | None" = None
_snomed_lock = threading.Lock()


def get_snomed_service() -> "SNOMEDService":
    """Get the singleton SNOMED service instance."""
    global _snomed_service
    if _snomed_service is None:
        with _snomed_lock:
            if _snomed_service is None:
                _snomed_service = SNOMEDService()
    return _snomed_service


def reset_snomed_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _snomed_service
    with _snomed_lock:
        _snomed_service = None


# ============================================================================
# SNOMED Service Implementation
# ============================================================================

class SNOMEDService:
    """Service for SNOMED CT concept lookup and matching.

    Provides:
    - Concept lookup by code
    - Text-to-concept matching with synonyms
    - Hierarchy navigation (is-a relationships)
    - Cross-mapping to ICD-10
    """

    def __init__(self) -> None:
        """Initialize the SNOMED service."""
        self._concepts: dict[str, SNOMEDConcept] = {}
        self._synonym_index: dict[str, list[str]] = {}  # synonym -> list of codes
        self._word_index: dict[str, set[str]] = {}  # word -> set of codes
        self._parent_index: dict[str, list[str]] = {}  # code -> parent codes
        self._child_index: dict[str, list[str]] = {}  # code -> child codes
        self._icd10_to_snomed: dict[str, list[str]] = {}  # ICD-10 -> SNOMED codes

        # Trie index for fast O(m) prefix/partial matching
        self._trie_index: TrieIndex = TrieIndex(index_words=True, index_ngrams=False)

        self._load_concepts()
        trie_stats = self._trie_index.get_stats()
        logger.info(
            f"SNOMED service initialized with {len(self._concepts)} concepts, "
            f"{len(self._synonym_index)} synonyms, "
            f"trie: {trie_stats['node_count']} nodes"
        )

    def _load_concepts(self) -> None:
        """Load SNOMED concepts from fixture files."""
        # Try enriched file first, then fall back to raw concepts
        loaded = False

        if SNOMED_FIXTURE_FILE.exists():
            loaded = self._load_from_file(SNOMED_FIXTURE_FILE)

        if not loaded and SNOMED_CONCEPTS_FILE.exists():
            loaded = self._load_from_file(SNOMED_CONCEPTS_FILE)

        if not loaded:
            logger.warning("No SNOMED fixture files found. Service will have limited data.")

    def _load_from_file(self, file_path: Path) -> bool:
        """Load concepts from a specific file."""
        try:
            with open(file_path, "r") as f:
                data = json.load(f)

            concepts = data.get("concepts", [])
            if not concepts:
                return False

            for concept_data in concepts:
                concept = self._parse_concept(concept_data)
                if concept:
                    self._index_concept(concept)

            logger.info(f"Loaded {len(self._concepts)} concepts from {file_path.name}")
            return True

        except Exception as e:
            logger.warning(f"Error loading SNOMED concepts from {file_path}: {e}")
            return False

    def _parse_concept(self, data: dict[str, Any]) -> SNOMEDConcept | None:
        """Parse a concept from JSON data."""
        code = data.get("concept_code", "")
        if not code:
            return None

        # Determine semantic type
        semantic_type = self._determine_semantic_type(data)

        # Parse synonyms
        synonyms = data.get("synonyms", [])
        if isinstance(synonyms, str):
            synonyms = [synonyms]

        # Parse ICD-10 mappings
        icd10_mappings = data.get("icd10_mappings", [])
        if isinstance(icd10_mappings, str):
            icd10_mappings = [icd10_mappings]

        # Parse parent codes
        parent_code = data.get("parent_code")
        parent_codes = [parent_code] if parent_code else []

        return SNOMEDConcept(
            concept_id=str(data.get("concept_id", code)),
            concept_code=code,
            concept_name=data.get("concept_name", ""),
            semantic_type=semantic_type,
            domain_id=data.get("domain_id", "Condition"),
            is_standard=data.get("standard_concept") == "S",
            synonyms=synonyms,
            parent_codes=parent_codes,
            icd10_mappings=icd10_mappings,
            omop_concept_id=data.get("concept_id") if isinstance(data.get("concept_id"), int) else None,
        )

    def _determine_semantic_type(self, data: dict[str, Any]) -> SemanticType:
        """Determine semantic type from concept data."""
        concept_class = data.get("concept_class_id", "").lower()
        semantic_type_str = data.get("semantic_type", "").lower()
        concept_name = data.get("concept_name", "").lower()

        # Check explicit semantic type
        type_mapping = {
            "clinical finding": SemanticType.CLINICAL_FINDING,
            "disorder": SemanticType.DISORDER,
            "procedure": SemanticType.PROCEDURE,
            "body structure": SemanticType.BODY_STRUCTURE,
            "substance": SemanticType.SUBSTANCE,
            "organism": SemanticType.ORGANISM,
            "observable": SemanticType.OBSERVABLE,
            "qualifier": SemanticType.QUALIFIER,
            "morphology": SemanticType.MORPHOLOGY,
            "situation": SemanticType.SITUATION,
            "event": SemanticType.EVENT,
            "physical object": SemanticType.PHYSICAL_OBJECT,
            "specimen": SemanticType.SPECIMEN,
            "drug": SemanticType.DRUG,
            "pharmaceutical": SemanticType.DRUG,
        }

        for key, sem_type in type_mapping.items():
            if key in concept_class or key in semantic_type_str:
                return sem_type

        # Infer from concept name
        if "(disorder)" in concept_name:
            return SemanticType.DISORDER
        elif "(finding)" in concept_name:
            return SemanticType.CLINICAL_FINDING
        elif "(procedure)" in concept_name:
            return SemanticType.PROCEDURE
        elif "(body structure)" in concept_name:
            return SemanticType.BODY_STRUCTURE
        elif "(organism)" in concept_name:
            return SemanticType.ORGANISM
        elif "(substance)" in concept_name:
            return SemanticType.SUBSTANCE

        return SemanticType.UNKNOWN

    def _index_concept(self, concept: SNOMEDConcept) -> None:
        """Index a concept for fast lookup."""
        code = concept.concept_code
        self._concepts[code] = concept

        # Index by name (lowercase)
        name_lower = concept.concept_name.lower()
        if name_lower not in self._synonym_index:
            self._synonym_index[name_lower] = []
        self._synonym_index[name_lower].append(code)

        # Index by synonyms
        for synonym in concept.synonyms:
            syn_lower = synonym.lower()
            if syn_lower not in self._synonym_index:
                self._synonym_index[syn_lower] = []
            if code not in self._synonym_index[syn_lower]:
                self._synonym_index[syn_lower].append(code)

        # Add to trie index for fast prefix/partial matching
        self._trie_index.add_term(
            code=code,
            display=concept.concept_name,
            weight=1.0,
            synonyms=concept.synonyms,
        )

        # Index words for partial matching
        words = self._extract_words(concept.concept_name)
        for word in words:
            if word not in self._word_index:
                self._word_index[word] = set()
            self._word_index[word].add(code)

        for synonym in concept.synonyms:
            words = self._extract_words(synonym)
            for word in words:
                if word not in self._word_index:
                    self._word_index[word] = set()
                self._word_index[word].add(code)

        # Index hierarchy
        for parent_code in concept.parent_codes:
            if code not in self._parent_index:
                self._parent_index[code] = []
            self._parent_index[code].append(parent_code)

            if parent_code not in self._child_index:
                self._child_index[parent_code] = []
            self._child_index[parent_code].append(code)

        # Index ICD-10 cross-maps
        for icd10_code in concept.icd10_mappings:
            icd10_upper = icd10_code.upper()
            if icd10_upper not in self._icd10_to_snomed:
                self._icd10_to_snomed[icd10_upper] = []
            if code not in self._icd10_to_snomed[icd10_upper]:
                self._icd10_to_snomed[icd10_upper].append(code)

    def _extract_words(self, text: str) -> set[str]:
        """Extract meaningful words from text for indexing."""
        # Remove parenthetical semantic tags
        text = re.sub(r'\([^)]+\)$', '', text)

        # Split on non-alphanumeric
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())

        # Filter stopwords
        stopwords = {
            "the", "and", "with", "without", "for", "from", "that", "this",
            "other", "unspecified", "not", "nor", "type", "due",
        }
        return {w for w in words if w not in stopwords}

    # ========================================================================
    # Public API: Lookup
    # ========================================================================

    def get_concept(self, code: str) -> SNOMEDConcept | None:
        """Get a SNOMED concept by code.

        Args:
            code: SNOMED CT concept code

        Returns:
            SNOMEDConcept or None if not found
        """
        return self._concepts.get(code)

    def get_concepts_by_codes(self, codes: list[str]) -> list[SNOMEDConcept]:
        """Get multiple concepts by codes.

        Args:
            codes: List of SNOMED CT codes

        Returns:
            List of found concepts (may be shorter than input if codes not found)
        """
        return [self._concepts[c] for c in codes if c in self._concepts]

    # ========================================================================
    # Public API: Matching
    # ========================================================================

    def match_concept(
        self,
        query: str,
        max_results: int = 10,
        semantic_types: list[SemanticType] | None = None,
    ) -> list[ConceptMatch]:
        """Match a clinical term to SNOMED concepts.

        Uses synonym matching and partial text matching to find relevant concepts.

        Args:
            query: Clinical term to match
            max_results: Maximum number of results
            semantic_types: Optional filter by semantic type

        Returns:
            List of ConceptMatch objects sorted by confidence
        """
        query_lower = query.lower().strip()
        matches: list[ConceptMatch] = []
        seen_codes: set[str] = set()

        # 1. Exact synonym match
        if query_lower in self._synonym_index:
            for code in self._synonym_index[query_lower]:
                if code in self._concepts and code not in seen_codes:
                    concept = self._concepts[code]
                    if self._matches_semantic_filter(concept, semantic_types):
                        matches.append(ConceptMatch(
                            concept=concept,
                            confidence=MatchConfidence.EXACT,
                            match_type="exact_synonym",
                            matched_term=query,
                            score=1.0,
                        ))
                        seen_codes.add(code)

        # 2. Trie-based prefix/partial matching - O(m) instead of O(n)
        # Uses trie index for fast prefix and word-boundary matching
        if len(matches) < max_results and len(query_lower) >= 3:
            trie_results = self._trie_index.search(
                query_lower,
                limit=max_results * 2,
                match_types=["prefix", "word"],
            )

            for trie_match in trie_results:
                code = trie_match.code
                if code not in seen_codes and code in self._concepts:
                    concept = self._concepts[code]
                    if self._matches_semantic_filter(concept, semantic_types):
                        # Determine confidence based on match type
                        if trie_match.match_type == "exact":
                            confidence = MatchConfidence.EXACT
                        elif trie_match.match_type == "prefix":
                            confidence = MatchConfidence.HIGH
                        else:
                            confidence = MatchConfidence.MEDIUM

                        matches.append(ConceptMatch(
                            concept=concept,
                            confidence=confidence,
                            match_type=f"trie_{trie_match.match_type}",
                            matched_term=trie_match.matched_text,
                            score=trie_match.score,
                        ))
                        seen_codes.add(code)

        # 3. Word-based matching (fallback using word index)
        query_words = self._extract_words(query)
        if query_words and len(matches) < max_results:
            # Find codes that have multiple matching words
            code_word_counts: dict[str, int] = {}
            for word in query_words:
                if word in self._word_index:
                    for code in self._word_index[word]:
                        if code not in seen_codes:
                            code_word_counts[code] = code_word_counts.get(code, 0) + 1

            # Sort by word count - require higher threshold for relevance
            min_word_threshold = max(2, len(query_words) // 2 + 1)  # At least 2 words or half+1
            for code, count in sorted(code_word_counts.items(), key=lambda x: -x[1]):
                # Require at least half the query words to match
                if count >= min_word_threshold or (count == len(query_words) and len(query_words) == 1):
                    if code in self._concepts:
                        concept = self._concepts[code]
                        if self._matches_semantic_filter(concept, semantic_types):
                            # Extra validation: ensure concept name is semantically related
                            concept_name_lower = concept.concept_name.lower()
                            # Skip if concept contains misleading or unrelated terms
                            misleading_terms = [
                                # Psychiatric/psychological mismatches
                                "delusion", "delusional", "hallucination", "fear", "phobia",
                                # Negation/absence
                                "absence", "lack", "no ", "without", "non-", "pseudo",
                                # History/risk
                                "history", "family history", "risk", "suspected", "possible",
                                # Opposite meanings
                                "sweet", "pleasant", "normal", "good",
                            ]
                            if any(term in concept_name_lower for term in misleading_terms):
                                continue

                            score = count / len(query_words) if query_words else 0
                            matches.append(ConceptMatch(
                                concept=concept,
                                confidence=MatchConfidence.LOW,
                                match_type="word_match",
                                matched_term=f"{count} word(s) matched",
                                score=score,
                            ))
                            seen_codes.add(code)
                            if len(matches) >= max_results * 2:
                                break

        # Sort by confidence and score
        confidence_order = {
            MatchConfidence.EXACT: 0,
            MatchConfidence.HIGH: 1,
            MatchConfidence.MEDIUM: 2,
            MatchConfidence.LOW: 3,
        }
        matches.sort(key=lambda m: (confidence_order[m.confidence], -m.score))

        return matches[:max_results]

    def _matches_semantic_filter(
        self,
        concept: SNOMEDConcept,
        semantic_types: list[SemanticType] | None,
    ) -> bool:
        """Check if concept matches semantic type filter."""
        if semantic_types is None:
            return True
        return concept.semantic_type in semantic_types

    def search_concepts(
        self,
        query: str,
        limit: int = 20,
        domain: str | None = None,
    ) -> list[SNOMEDConcept]:
        """Search for concepts by description or synonym.

        Args:
            query: Search query
            limit: Maximum results
            domain: Optional filter by OMOP domain

        Returns:
            List of matching concepts
        """
        matches = self.match_concept(query, max_results=limit)
        concepts = [m.concept for m in matches]

        if domain:
            concepts = [c for c in concepts if c.domain_id == domain]

        return concepts[:limit]

    # ========================================================================
    # Public API: Hierarchy Navigation
    # ========================================================================

    def get_ancestors(self, code: str, max_depth: int = 5) -> list[SNOMEDConcept]:
        """Get ancestor concepts (is-a relationship).

        Args:
            code: SNOMED CT code
            max_depth: Maximum depth to traverse

        Returns:
            List of ancestor concepts
        """
        ancestors: list[SNOMEDConcept] = []
        visited: set[str] = set()
        to_visit: list[tuple[str, int]] = [(code, 0)]

        while to_visit:
            current_code, depth = to_visit.pop(0)

            if depth >= max_depth:
                continue

            parent_codes = self._parent_index.get(current_code, [])
            for parent_code in parent_codes:
                if parent_code not in visited and parent_code in self._concepts:
                    visited.add(parent_code)
                    ancestors.append(self._concepts[parent_code])
                    to_visit.append((parent_code, depth + 1))

        return ancestors

    def get_descendants(self, code: str, max_depth: int = 3) -> list[SNOMEDConcept]:
        """Get descendant concepts (inverse is-a relationship).

        Args:
            code: SNOMED CT code
            max_depth: Maximum depth to traverse

        Returns:
            List of descendant concepts
        """
        descendants: list[SNOMEDConcept] = []
        visited: set[str] = set()
        to_visit: list[tuple[str, int]] = [(code, 0)]

        while to_visit:
            current_code, depth = to_visit.pop(0)

            if depth >= max_depth:
                continue

            child_codes = self._child_index.get(current_code, [])
            for child_code in child_codes:
                if child_code not in visited and child_code in self._concepts:
                    visited.add(child_code)
                    descendants.append(self._concepts[child_code])
                    to_visit.append((child_code, depth + 1))

        return descendants

    def get_siblings(self, code: str) -> list[SNOMEDConcept]:
        """Get sibling concepts (same parent).

        Args:
            code: SNOMED CT code

        Returns:
            List of sibling concepts
        """
        siblings: list[SNOMEDConcept] = []

        # Get parent codes for this concept
        parent_codes = self._parent_index.get(code, [])

        # Get all children of parents (siblings)
        for parent_code in parent_codes:
            for child_code in self._child_index.get(parent_code, []):
                if child_code != code and child_code in self._concepts:
                    siblings.append(self._concepts[child_code])

        return siblings

    def get_hierarchy(self, code: str) -> HierarchyResult | None:
        """Get full hierarchy information for a concept.

        Args:
            code: SNOMED CT code

        Returns:
            HierarchyResult or None if concept not found
        """
        concept = self.get_concept(code)
        if not concept:
            return None

        return HierarchyResult(
            concept=concept,
            ancestors=self.get_ancestors(code),
            descendants=self.get_descendants(code),
            siblings=self.get_siblings(code),
        )

    def is_descendant_of(self, code: str, ancestor_code: str) -> bool:
        """Check if code is a descendant of another code.

        Args:
            code: SNOMED CT code to check
            ancestor_code: Potential ancestor code

        Returns:
            True if code is a descendant of ancestor_code
        """
        ancestors = self.get_ancestors(code, max_depth=10)
        return any(a.concept_code == ancestor_code for a in ancestors)

    # ========================================================================
    # Public API: Cross-Mapping
    # ========================================================================

    def get_icd10_mappings(self, snomed_code: str) -> CrossMapResult | None:
        """Get ICD-10 mappings for a SNOMED concept.

        Args:
            snomed_code: SNOMED CT code

        Returns:
            CrossMapResult or None if no mappings
        """
        concept = self.get_concept(snomed_code)
        if not concept:
            return None

        if not concept.icd10_mappings:
            return None

        return CrossMapResult(
            snomed_concept=concept,
            icd10_codes=concept.icd10_mappings,
            map_type="equivalent",
        )

    def get_snomed_from_icd10(self, icd10_code: str) -> list[SNOMEDConcept]:
        """Get SNOMED concepts mapped from an ICD-10 code.

        Args:
            icd10_code: ICD-10-CM code

        Returns:
            List of SNOMED concepts
        """
        icd10_upper = icd10_code.upper().replace(".", "")
        snomed_codes = self._icd10_to_snomed.get(icd10_upper, [])

        # Also try with dot
        if "." not in icd10_code and len(icd10_code) > 3:
            formatted = f"{icd10_code[:3]}.{icd10_code[3:]}"
            snomed_codes.extend(self._icd10_to_snomed.get(formatted.upper(), []))

        return self.get_concepts_by_codes(list(set(snomed_codes)))

    # ========================================================================
    # Public API: Statistics
    # ========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the SNOMED database."""
        by_semantic_type: dict[str, int] = {}
        by_domain: dict[str, int] = {}
        with_synonyms = 0
        with_icd10 = 0
        with_hierarchy = 0

        for concept in self._concepts.values():
            sem_type = concept.semantic_type.value
            by_semantic_type[sem_type] = by_semantic_type.get(sem_type, 0) + 1

            domain = concept.domain_id
            by_domain[domain] = by_domain.get(domain, 0) + 1

            if concept.synonyms:
                with_synonyms += 1
            if concept.icd10_mappings:
                with_icd10 += 1
            if concept.parent_codes:
                with_hierarchy += 1

        return {
            "total_concepts": len(self._concepts),
            "total_synonyms": len(self._synonym_index),
            "total_icd10_mappings": len(self._icd10_to_snomed),
            "concepts_with_synonyms": with_synonyms,
            "concepts_with_icd10": with_icd10,
            "concepts_with_hierarchy": with_hierarchy,
            "by_semantic_type": by_semantic_type,
            "by_domain": by_domain,
        }

    def get_concepts_by_semantic_type(
        self,
        semantic_type: SemanticType,
        limit: int = 100,
    ) -> list[SNOMEDConcept]:
        """Get concepts by semantic type.

        Args:
            semantic_type: The semantic type to filter by
            limit: Maximum number of results

        Returns:
            List of concepts with the specified semantic type
        """
        concepts = [
            c for c in self._concepts.values()
            if c.semantic_type == semantic_type
        ]
        return concepts[:limit]

    def get_concepts_by_domain(self, domain: str, limit: int = 100) -> list[SNOMEDConcept]:
        """Get concepts by OMOP domain.

        Args:
            domain: OMOP domain (Condition, Procedure, etc.)
            limit: Maximum number of results

        Returns:
            List of concepts in the specified domain
        """
        concepts = [c for c in self._concepts.values() if c.domain_id == domain]
        return concepts[:limit]
