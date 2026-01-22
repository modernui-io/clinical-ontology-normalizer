"""
Trie-based Index for Fast Clinical Terminology Lookup.

Provides O(m) prefix/substring matching where m is the query length,
instead of O(n) where n is the number of terms.

This enables fast partial matching for:
- SNOMED-CT (187K+ synonyms)
- ICD-10-CM (83K+ codes)
- RxNorm, LOINC, CPT, etc.

The trie supports:
- Prefix matching: "diabet" -> "diabetes", "diabetic neuropathy", etc.
- Case-insensitive matching
- Word boundary matching: "heart" matches "congestive heart failure"
- Ranked results by match quality and usage frequency
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Iterator
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class TrieNode:
    """A node in the trie structure."""
    children: Dict[str, 'TrieNode'] = field(default_factory=dict)
    is_end: bool = False
    # Store references to matching items (code, display, etc.)
    items: List[Tuple[str, str, float]] = field(default_factory=list)  # (code, display, weight)


@dataclass
class MatchResult:
    """Result from a trie search."""
    code: str
    display: str
    matched_text: str
    match_type: str  # "exact", "prefix", "word", "substring"
    score: float  # Relevance score


class TrieIndex:
    """
    Trie-based index for fast terminology lookup.

    Supports multiple indexing strategies:
    1. Full term indexing: Index complete terms for exact and prefix matching
    2. Word indexing: Index individual words for word-boundary matching
    3. N-gram indexing: Index character sequences for substring matching

    Example:
        >>> trie = TrieIndex()
        >>> trie.add_term("E11.42", "Type 2 diabetes mellitus with diabetic polyneuropathy")
        >>> results = trie.search("diabetic poly", limit=5)
    """

    def __init__(
        self,
        index_words: bool = True,
        index_ngrams: bool = False,
        ngram_min: int = 3,
    ):
        """
        Initialize the trie index.

        Args:
            index_words: Whether to index individual words
            index_ngrams: Whether to index character n-grams (more memory, better substring matching)
            ngram_min: Minimum n-gram length to index
        """
        self.root = TrieNode()
        self.word_root = TrieNode() if index_words else None
        self.ngram_root = TrieNode() if index_ngrams else None
        self.ngram_min = ngram_min

        self._term_count = 0
        self._node_count = 1  # Root node

        # For reverse lookup
        self._code_to_terms: Dict[str, List[str]] = defaultdict(list)

    def add_term(
        self,
        code: str,
        display: str,
        weight: float = 1.0,
        synonyms: Optional[List[str]] = None
    ):
        """
        Add a term to the index.

        Args:
            code: The code (e.g., ICD-10 code, SNOMED concept ID)
            display: The display text
            weight: Relevance weight (higher = more relevant in results)
            synonyms: Additional synonyms to index
        """
        terms_to_index = [display]
        if synonyms:
            terms_to_index.extend(synonyms)

        for term in terms_to_index:
            normalized = self._normalize(term)
            if not normalized:
                continue

            # Index full term for exact/prefix matching
            self._add_to_trie(self.root, normalized, code, display, weight)

            # Index individual words for word-boundary matching
            if self.word_root:
                words = normalized.split()
                for word in words:
                    if len(word) >= 2:  # Skip single-char words
                        self._add_to_trie(self.word_root, word, code, display, weight * 0.8)

            # Index n-grams for substring matching
            if self.ngram_root:
                for ngram in self._generate_ngrams(normalized):
                    self._add_to_trie(self.ngram_root, ngram, code, display, weight * 0.6)

            self._code_to_terms[code].append(term)
            self._term_count += 1

    def _normalize(self, text: str) -> str:
        """Normalize text for indexing."""
        return text.lower().strip()

    def _add_to_trie(
        self,
        root: TrieNode,
        text: str,
        code: str,
        display: str,
        weight: float
    ):
        """Add a text string to the trie."""
        node = root
        for char in text:
            if char not in node.children:
                node.children[char] = TrieNode()
                self._node_count += 1
            node = node.children[char]

        node.is_end = True

        # Avoid duplicates
        existing_codes = {item[0] for item in node.items}
        if code not in existing_codes:
            node.items.append((code, display, weight))

    def _generate_ngrams(self, text: str) -> Iterator[str]:
        """Generate character n-grams from text."""
        # Remove spaces for n-gram generation
        text = text.replace(" ", "")
        for i in range(len(text) - self.ngram_min + 1):
            for length in range(self.ngram_min, min(len(text) - i + 1, 8)):
                yield text[i:i + length]

    def search(
        self,
        query: str,
        limit: int = 10,
        match_types: Optional[List[str]] = None
    ) -> List[MatchResult]:
        """
        Search the index for matching terms.

        Args:
            query: Search query
            limit: Maximum results to return
            match_types: Types of matches to include ("exact", "prefix", "word", "substring")
                        If None, all types are included.

        Returns:
            List of MatchResult objects sorted by relevance
        """
        if not query:
            return []

        normalized = self._normalize(query)
        results: Dict[str, MatchResult] = {}  # code -> result (dedupe by code)

        if match_types is None:
            match_types = ["exact", "prefix", "word", "substring"]

        # 1. Exact/Prefix matching in main trie
        if "exact" in match_types or "prefix" in match_types:
            self._search_trie(
                self.root, normalized, results,
                include_exact="exact" in match_types,
                include_prefix="prefix" in match_types
            )

        # 2. Word-boundary matching
        if "word" in match_types and self.word_root:
            # Search for each query word
            query_words = normalized.split()
            for word in query_words:
                if len(word) >= 2:
                    self._search_trie(
                        self.word_root, word, results,
                        match_type="word",
                        include_exact=True,
                        include_prefix=True
                    )

        # 3. Substring matching via n-grams
        if "substring" in match_types and self.ngram_root and len(normalized) >= self.ngram_min:
            self._search_trie(
                self.ngram_root, normalized[:8], results,  # Limit query length
                match_type="substring",
                include_exact=True,
                include_prefix=False
            )

        # Sort by score and return top results
        sorted_results = sorted(results.values(), key=lambda r: -r.score)
        return sorted_results[:limit]

    def _search_trie(
        self,
        root: TrieNode,
        query: str,
        results: Dict[str, MatchResult],
        match_type: str = "prefix",
        include_exact: bool = True,
        include_prefix: bool = True
    ):
        """Search a specific trie and add results."""
        node = root

        # Navigate to query endpoint
        for i, char in enumerate(query):
            if char not in node.children:
                return  # No matches
            node = node.children[char]

        # Check for exact match
        if include_exact and node.is_end:
            for code, display, weight in node.items:
                if code not in results or results[code].score < weight * 1.5:
                    results[code] = MatchResult(
                        code=code,
                        display=display,
                        matched_text=query,
                        match_type="exact" if match_type == "prefix" else match_type,
                        score=weight * 1.5  # Exact matches get bonus
                    )

        # Collect prefix matches (items in subtree)
        if include_prefix:
            self._collect_subtree(node, query, results, match_type)

    def _collect_subtree(
        self,
        node: TrieNode,
        prefix: str,
        results: Dict[str, MatchResult],
        match_type: str,
        max_items: int = 100
    ):
        """Collect all items in a subtree (BFS for relevance ordering)."""
        collected = 0
        stack = [(node, prefix)]

        while stack and collected < max_items:
            current, current_prefix = stack.pop()

            if current.is_end:
                for code, display, weight in current.items:
                    if code not in results:
                        results[code] = MatchResult(
                            code=code,
                            display=display,
                            matched_text=current_prefix,
                            match_type=match_type,
                            score=weight
                        )
                        collected += 1
                    elif results[code].score < weight:
                        results[code].score = weight

            # Add children to stack (sorted by frequency if we had that data)
            for char, child in current.children.items():
                stack.append((child, current_prefix + char))

    def search_prefix(self, prefix: str, limit: int = 10) -> List[MatchResult]:
        """Convenience method for prefix-only search."""
        return self.search(prefix, limit=limit, match_types=["exact", "prefix"])

    def search_words(self, query: str, limit: int = 10) -> List[MatchResult]:
        """Convenience method for word-boundary search."""
        return self.search(query, limit=limit, match_types=["word"])

    def has_exact_match(self, query: str) -> bool:
        """Check if there's an exact match for a query."""
        normalized = self._normalize(query)
        node = self.root

        for char in normalized:
            if char not in node.children:
                return False
            node = node.children[char]

        return node.is_end

    def get_terms_for_code(self, code: str) -> List[str]:
        """Get all indexed terms for a code."""
        return self._code_to_terms.get(code, [])

    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        return {
            "term_count": self._term_count,
            "node_count": self._node_count,
            "unique_codes": len(self._code_to_terms),
            "has_word_index": self.word_root is not None,
            "has_ngram_index": self.ngram_root is not None,
        }

    def clear(self):
        """Clear the index."""
        self.root = TrieNode()
        if self.word_root:
            self.word_root = TrieNode()
        if self.ngram_root:
            self.ngram_root = TrieNode()
        self._term_count = 0
        self._node_count = 1
        self._code_to_terms.clear()


class ClinicalTerminologyIndex:
    """
    High-level clinical terminology index with pre-configured settings.

    Optimized for clinical terminology matching with:
    - Case-insensitive matching
    - Word-boundary matching (for multi-word terms)
    - Synonym expansion
    - Ranked results by clinical relevance
    """

    def __init__(self):
        self.trie = TrieIndex(index_words=True, index_ngrams=False)
        self._loaded_vocabularies: Set[str] = set()

    def load_icd10_codes(self, codes: List[Dict[str, Any]]):
        """
        Load ICD-10-CM codes into the index.

        Expected format: [{"code": "E11.42", "display": "...", "synonyms": [...]}]
        """
        for item in codes:
            code = item.get("code", "")
            display = item.get("display", item.get("description", ""))
            synonyms = item.get("synonyms", [])

            # Higher weight for more specific codes
            weight = 1.0 + (0.1 * code.count("."))

            self.trie.add_term(code, display, weight=weight, synonyms=synonyms)

        self._loaded_vocabularies.add("ICD10CM")
        logger.info(f"Loaded {len(codes)} ICD-10-CM codes into trie index")

    def load_snomed_codes(self, concepts: List[Dict[str, Any]]):
        """
        Load SNOMED-CT concepts into the index.

        Expected format: [{"id": "123", "fsn": "...", "pt": "...", "synonyms": [...]}]
        """
        for item in concepts:
            code = str(item.get("id", item.get("concept_id", "")))
            fsn = item.get("fsn", "")
            pt = item.get("pt", item.get("preferred_term", ""))
            synonyms = item.get("synonyms", [])

            # Preferred term gets higher weight
            if pt:
                self.trie.add_term(code, pt, weight=1.2, synonyms=synonyms)
            if fsn and fsn != pt:
                self.trie.add_term(code, fsn, weight=1.0)

        self._loaded_vocabularies.add("SNOMED")
        logger.info(f"Loaded {len(concepts)} SNOMED concepts into trie index")

    def load_rxnorm_codes(self, drugs: List[Dict[str, Any]]):
        """Load RxNorm drug concepts."""
        for item in drugs:
            code = str(item.get("rxcui", item.get("code", "")))
            name = item.get("name", item.get("display", ""))
            synonyms = item.get("synonyms", item.get("brand_names", []))

            self.trie.add_term(code, name, weight=1.0, synonyms=synonyms)

        self._loaded_vocabularies.add("RxNorm")
        logger.info(f"Loaded {len(drugs)} RxNorm drugs into trie index")

    def search(
        self,
        query: str,
        vocabulary: Optional[str] = None,
        limit: int = 10
    ) -> List[MatchResult]:
        """
        Search for clinical terms.

        Args:
            query: Search query
            vocabulary: Filter by vocabulary (ICD10CM, SNOMED, RxNorm)
            limit: Maximum results

        Returns:
            List of MatchResult objects
        """
        results = self.trie.search(query, limit=limit * 2)  # Get extra for filtering

        if vocabulary:
            # Filter by vocabulary - would need vocabulary info in results
            # For now, return all results
            pass

        return results[:limit]

    def autocomplete(self, prefix: str, limit: int = 10) -> List[Dict[str, str]]:
        """
        Get autocomplete suggestions for a prefix.

        Returns simplified suggestions suitable for UI autocomplete.
        """
        results = self.trie.search_prefix(prefix, limit=limit)

        return [
            {
                "code": r.code,
                "display": r.display,
                "match_type": r.match_type,
            }
            for r in results
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        stats = self.trie.get_stats()
        stats["loaded_vocabularies"] = list(self._loaded_vocabularies)
        return stats


# Singleton instance
_terminology_index: Optional[ClinicalTerminologyIndex] = None


def get_terminology_index() -> ClinicalTerminologyIndex:
    """Get singleton terminology index."""
    global _terminology_index
    if _terminology_index is None:
        _terminology_index = ClinicalTerminologyIndex()
    return _terminology_index
