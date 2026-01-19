"""Semantic Search Service for Clinical Ontology Normalizer.

Provides intelligent search across clinical terminology vocabularies with:
- TF-IDF vectorization for text matching
- BM25 ranking for relevance scoring
- Cosine similarity for semantic matching
- Fuzzy matching for typo tolerance
- Cross-vocabulary mapping (ICD-10 <-> SNOMED <-> RxNorm)
- Query expansion with synonyms
- Concept hierarchy traversal
"""

import json
import logging
import math
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)

# Singleton instance and lock
_semantic_search_instance: "SemanticSearchService | None" = None
_semantic_search_lock = Lock()


class VocabularyType(str, Enum):
    """Supported vocabulary types."""
    ICD10 = "ICD10CM"
    SNOMED = "SNOMED"
    RXNORM = "RxNorm"
    CPT = "CPT4"
    LOINC = "LOINC"
    ALL = "ALL"


class MatchType(str, Enum):
    """Type of match found."""
    EXACT = "exact"
    SYNONYM = "synonym"
    FUZZY = "fuzzy"
    SEMANTIC = "semantic"
    HIERARCHY = "hierarchy"
    CROSSWALK = "crosswalk"


@dataclass
class ConceptEntry:
    """Represents a vocabulary concept."""
    concept_id: int
    concept_code: str
    concept_name: str
    vocabulary_id: str
    domain_id: str
    concept_class_id: str | None = None
    standard_concept: str | None = None
    synonyms: list[str] = field(default_factory=list)
    semantic_type: str | None = None
    parents: list[int] = field(default_factory=list)
    children: list[int] = field(default_factory=list)
    crosswalk_mappings: dict[str, list[int]] = field(default_factory=dict)


@dataclass
class SearchResult:
    """A single search result."""
    concept_id: int
    concept_code: str
    concept_name: str
    vocabulary_id: str
    domain_id: str
    score: float
    match_type: MatchType
    matched_term: str | None = None
    explanation: str | None = None
    synonyms: list[str] = field(default_factory=list)
    crosswalk: dict[str, list[dict[str, Any]]] = field(default_factory=dict)


@dataclass
class ClusterResult:
    """A cluster of related search results."""
    cluster_id: str
    cluster_name: str
    concept_type: str
    results: list[SearchResult]
    total_count: int


@dataclass
class CrosswalkMapping:
    """Cross-vocabulary mapping result."""
    source_concept_id: int
    source_vocabulary: str
    source_code: str
    source_name: str
    target_concept_id: int
    target_vocabulary: str
    target_code: str
    target_name: str
    mapping_type: str
    confidence: float


class TFIDFVectorizer:
    """TF-IDF vectorization for terminology matching."""

    def __init__(self):
        self.vocabulary: dict[str, int] = {}
        self.idf: dict[str, float] = {}
        self.document_count = 0
        self.fitted = False

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text into normalized terms."""
        # Lowercase, remove punctuation, split on whitespace
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        tokens = text.split()
        # Remove very short tokens
        tokens = [t for t in tokens if len(t) > 1]
        return tokens

    def fit(self, documents: list[str]) -> None:
        """Fit the vectorizer on a corpus of documents."""
        self.document_count = len(documents)
        document_frequency: dict[str, int] = defaultdict(int)

        # Build vocabulary and count document frequencies
        for doc in documents:
            tokens = set(self._tokenize(doc))
            for token in tokens:
                if token not in self.vocabulary:
                    self.vocabulary[token] = len(self.vocabulary)
                document_frequency[token] += 1

        # Calculate IDF scores
        for term, df in document_frequency.items():
            self.idf[term] = math.log((self.document_count + 1) / (df + 1)) + 1

        self.fitted = True
        logger.info(f"TF-IDF vectorizer fitted with {len(self.vocabulary)} terms from {self.document_count} documents")

    def transform(self, text: str) -> dict[str, float]:
        """Transform text into TF-IDF vector (sparse representation)."""
        if not self.fitted:
            return {}

        tokens = self._tokenize(text)
        if not tokens:
            return {}

        # Calculate term frequencies
        tf: dict[str, float] = defaultdict(float)
        for token in tokens:
            tf[token] += 1

        # Normalize by document length
        max_tf = max(tf.values()) if tf else 1

        # Calculate TF-IDF scores
        tfidf: dict[str, float] = {}
        for term, freq in tf.items():
            if term in self.vocabulary:
                normalized_tf = 0.5 + 0.5 * (freq / max_tf)
                tfidf[term] = normalized_tf * self.idf.get(term, 1.0)

        return tfidf

    def cosine_similarity(self, vec1: dict[str, float], vec2: dict[str, float]) -> float:
        """Calculate cosine similarity between two sparse vectors."""
        if not vec1 or not vec2:
            return 0.0

        # Find common terms
        common_terms = set(vec1.keys()) & set(vec2.keys())
        if not common_terms:
            return 0.0

        # Calculate dot product
        dot_product = sum(vec1[t] * vec2[t] for t in common_terms)

        # Calculate magnitudes
        mag1 = math.sqrt(sum(v ** 2 for v in vec1.values()))
        mag2 = math.sqrt(sum(v ** 2 for v in vec2.values()))

        if mag1 == 0 or mag2 == 0:
            return 0.0

        return dot_product / (mag1 * mag2)


class BM25Scorer:
    """BM25 ranking algorithm for relevance scoring."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.avgdl = 0.0
        self.doc_lengths: dict[int, int] = {}
        self.doc_freqs: dict[str, int] = defaultdict(int)
        self.term_freqs: dict[int, dict[str, int]] = {}
        self.idf: dict[str, float] = {}
        self.n_docs = 0
        self.fitted = False

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text."""
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        return [t for t in text.split() if len(t) > 1]

    def fit(self, documents: list[tuple[int, str]]) -> None:
        """Fit BM25 on documents (list of (id, text) tuples)."""
        self.n_docs = len(documents)
        total_length = 0

        for doc_id, text in documents:
            tokens = self._tokenize(text)
            self.doc_lengths[doc_id] = len(tokens)
            total_length += len(tokens)

            # Count term frequencies
            tf: dict[str, int] = defaultdict(int)
            for token in tokens:
                tf[token] += 1
            self.term_freqs[doc_id] = dict(tf)

            # Count document frequencies
            for token in set(tokens):
                self.doc_freqs[token] += 1

        self.avgdl = total_length / self.n_docs if self.n_docs > 0 else 0

        # Calculate IDF
        for term, df in self.doc_freqs.items():
            self.idf[term] = math.log((self.n_docs - df + 0.5) / (df + 0.5) + 1)

        self.fitted = True
        logger.info(f"BM25 fitted with {self.n_docs} documents, {len(self.doc_freqs)} unique terms")

    def score(self, query: str, doc_id: int) -> float:
        """Score a document against a query."""
        if not self.fitted or doc_id not in self.term_freqs:
            return 0.0

        query_tokens = self._tokenize(query)
        doc_tf = self.term_freqs[doc_id]
        doc_len = self.doc_lengths[doc_id]

        score = 0.0
        for token in query_tokens:
            if token not in self.idf:
                continue

            tf = doc_tf.get(token, 0)
            idf = self.idf[token]

            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * (doc_len / self.avgdl))

            score += idf * (numerator / denominator) if denominator > 0 else 0

        return score


class FuzzyMatcher:
    """Fuzzy string matching for typo tolerance."""

    @staticmethod
    def levenshtein_distance(s1: str, s2: str) -> int:
        """Calculate Levenshtein edit distance between two strings."""
        if len(s1) < len(s2):
            return FuzzyMatcher.levenshtein_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    @staticmethod
    def similarity(s1: str, s2: str) -> float:
        """Calculate similarity ratio (0-1) between two strings."""
        s1, s2 = s1.lower(), s2.lower()
        if s1 == s2:
            return 1.0

        max_len = max(len(s1), len(s2))
        if max_len == 0:
            return 1.0

        distance = FuzzyMatcher.levenshtein_distance(s1, s2)
        return 1 - (distance / max_len)

    @staticmethod
    def find_matches(query: str, candidates: list[str], threshold: float = 0.7) -> list[tuple[str, float]]:
        """Find fuzzy matches above threshold."""
        matches = []
        query_lower = query.lower()

        for candidate in candidates:
            sim = FuzzyMatcher.similarity(query_lower, candidate.lower())
            if sim >= threshold:
                matches.append((candidate, sim))

        # Sort by similarity descending
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches


class SemanticSearchService:
    """Main semantic search service for clinical terminologies."""

    def __init__(self):
        self._concepts: dict[int, ConceptEntry] = {}
        self._code_index: dict[str, list[int]] = defaultdict(list)  # code -> concept_ids
        self._name_index: dict[str, list[int]] = defaultdict(list)  # normalized name -> concept_ids
        self._synonym_index: dict[str, list[int]] = defaultdict(list)  # synonym -> concept_ids
        self._vocabulary_index: dict[str, list[int]] = defaultdict(list)  # vocab -> concept_ids
        self._domain_index: dict[str, list[int]] = defaultdict(list)  # domain -> concept_ids

        self._tfidf = TFIDFVectorizer()
        self._bm25 = BM25Scorer()
        self._concept_vectors: dict[int, dict[str, float]] = {}

        self._loaded = False
        self._load_time_ms = 0.0
        self._stats: dict[str, Any] = {}

        # Synonym expansions for query expansion
        self._synonym_expansions: dict[str, list[str]] = {
            "dm": ["diabetes mellitus", "diabetes"],
            "htn": ["hypertension", "high blood pressure"],
            "chf": ["congestive heart failure", "heart failure"],
            "copd": ["chronic obstructive pulmonary disease"],
            "mi": ["myocardial infarction", "heart attack"],
            "cva": ["cerebrovascular accident", "stroke"],
            "uti": ["urinary tract infection"],
            "cad": ["coronary artery disease"],
            "afib": ["atrial fibrillation"],
            "dvt": ["deep vein thrombosis"],
            "pe": ["pulmonary embolism"],
            "aki": ["acute kidney injury"],
            "ckd": ["chronic kidney disease"],
            "gerd": ["gastroesophageal reflux disease"],
            "bp": ["blood pressure"],
            "hr": ["heart rate"],
            "rr": ["respiratory rate"],
            "temp": ["temperature"],
            "o2 sat": ["oxygen saturation", "spo2"],
        }

    def _find_fixtures_dir(self) -> Path:
        """Find the fixtures directory."""
        current = Path(__file__).parent
        while current.parent != current:
            potential_path = current / "fixtures"
            if potential_path.exists():
                return potential_path
            current = current.parent
        return Path("fixtures")

    def load(self) -> None:
        """Load all vocabulary fixtures and build indexes."""
        if self._loaded:
            return

        start_time = time.perf_counter()
        fixtures_dir = self._find_fixtures_dir()

        # Load vocabulary files
        vocab_files = {
            "ICD10CM": ["icd10_codes.json", "icd10_codes_full.json"],
            "SNOMED": ["snomed_codes.json", "snomed_concepts.json"],
            "RxNorm": ["rxnorm_drugs.json"],
            "CPT4": ["cpt_codes.json", "cpt_codes_full.json"],
            "LOINC": ["loinc_measurements.json"],
        }

        all_documents: list[str] = []
        bm25_documents: list[tuple[int, str]] = []

        for vocab_id, files in vocab_files.items():
            for filename in files:
                filepath = fixtures_dir / filename
                if filepath.exists():
                    self._load_vocabulary_file(filepath, vocab_id, all_documents, bm25_documents)
                    break  # Only load first found file per vocabulary

        # Build TF-IDF vectorizer
        if all_documents:
            self._tfidf.fit(all_documents)

            # Pre-compute concept vectors
            for concept_id, concept in self._concepts.items():
                doc_text = f"{concept.concept_name} {' '.join(concept.synonyms)}"
                self._concept_vectors[concept_id] = self._tfidf.transform(doc_text)

        # Build BM25 scorer
        if bm25_documents:
            self._bm25.fit(bm25_documents)

        self._loaded = True
        self._load_time_ms = (time.perf_counter() - start_time) * 1000

        # Calculate stats
        self._stats = {
            "total_concepts": len(self._concepts),
            "vocabularies": {v: len(ids) for v, ids in self._vocabulary_index.items()},
            "domains": {d: len(ids) for d, ids in self._domain_index.items()},
            "unique_codes": sum(len(ids) for ids in self._code_index.values()),
            "indexed_synonyms": sum(len(ids) for ids in self._synonym_index.values()),
            "load_time_ms": round(self._load_time_ms, 2),
        }

        logger.info(f"Semantic search loaded: {len(self._concepts)} concepts in {self._load_time_ms:.2f}ms")

    def _load_vocabulary_file(
        self,
        filepath: Path,
        vocab_id: str,
        all_documents: list[str],
        bm25_documents: list[tuple[int, str]],
    ) -> None:
        """Load concepts from a vocabulary JSON file."""
        try:
            with open(filepath) as f:
                data = json.load(f)

            concepts = data.get("concepts", [])
            loaded = 0

            for concept_data in concepts:
                concept_id = concept_data.get("concept_id")
                if not concept_id or concept_id in self._concepts:
                    continue

                concept = ConceptEntry(
                    concept_id=concept_id,
                    concept_code=concept_data.get("concept_code", ""),
                    concept_name=concept_data.get("concept_name", ""),
                    vocabulary_id=concept_data.get("vocabulary_id", vocab_id),
                    domain_id=concept_data.get("domain_id", "Unknown"),
                    concept_class_id=concept_data.get("concept_class_id"),
                    standard_concept=concept_data.get("standard_concept"),
                    synonyms=concept_data.get("synonyms", []),
                    semantic_type=concept_data.get("semantic_type"),
                )

                # Load hierarchy if available
                if "parents" in concept_data:
                    concept.parents = concept_data["parents"]
                if "children" in concept_data:
                    concept.children = concept_data["children"]
                if "icd10_mappings" in concept_data:
                    concept.crosswalk_mappings["ICD10CM"] = concept_data["icd10_mappings"]

                self._concepts[concept_id] = concept

                # Build indexes
                code_key = concept.concept_code.lower()
                self._code_index[code_key].append(concept_id)

                name_key = concept.concept_name.lower()
                self._name_index[name_key].append(concept_id)

                for synonym in concept.synonyms:
                    syn_key = synonym.lower()
                    self._synonym_index[syn_key].append(concept_id)

                self._vocabulary_index[concept.vocabulary_id].append(concept_id)
                self._domain_index[concept.domain_id].append(concept_id)

                # Build document for TF-IDF
                doc_text = f"{concept.concept_name} {' '.join(concept.synonyms)}"
                all_documents.append(doc_text)
                bm25_documents.append((concept_id, doc_text))

                loaded += 1

            logger.info(f"Loaded {loaded} concepts from {filepath.name}")

        except Exception as e:
            logger.error(f"Error loading {filepath}: {e}")

    def expand_query(self, query: str) -> list[str]:
        """Expand query with synonyms and related terms."""
        expanded = [query]
        query_lower = query.lower()

        # Check for known abbreviations
        for abbrev, expansions in self._synonym_expansions.items():
            if abbrev in query_lower:
                for expansion in expansions:
                    expanded.append(query_lower.replace(abbrev, expansion))

        return list(set(expanded))

    def search_semantic(
        self,
        query: str,
        vocabularies: list[VocabularyType] | None = None,
        domains: list[str] | None = None,
        top_k: int = 20,
        threshold: float = 0.3,
        include_fuzzy: bool = True,
        expand_query: bool = True,
    ) -> list[SearchResult]:
        """Perform semantic search across vocabularies.

        Args:
            query: Natural language search query.
            vocabularies: List of vocabularies to search (None = all).
            domains: List of domains to filter by.
            top_k: Maximum results to return.
            threshold: Minimum relevance score.
            include_fuzzy: Include fuzzy matches for typo tolerance.
            expand_query: Expand query with synonyms.

        Returns:
            List of SearchResult objects sorted by relevance.
        """
        if not self._loaded:
            self.load()

        start_time = time.perf_counter()
        results: dict[int, SearchResult] = {}

        # Expand query if enabled
        queries = self.expand_query(query) if expand_query else [query]

        for q in queries:
            # 1. Exact code match
            self._search_exact_code(q, results, vocabularies, domains)

            # 2. Exact name match
            self._search_exact_name(q, results, vocabularies, domains)

            # 3. Synonym match
            self._search_synonyms(q, results, vocabularies, domains)

            # 4. TF-IDF semantic match
            self._search_tfidf(q, results, vocabularies, domains, threshold)

            # 5. BM25 ranking
            self._search_bm25(q, results, vocabularies, domains, threshold)

            # 6. Fuzzy match
            if include_fuzzy:
                self._search_fuzzy(q, results, vocabularies, domains, threshold)

        # Sort by score and limit
        sorted_results = sorted(results.values(), key=lambda x: x.score, reverse=True)[:top_k]

        search_time = (time.perf_counter() - start_time) * 1000
        logger.debug(f"Semantic search for '{query}' returned {len(sorted_results)} results in {search_time:.2f}ms")

        return sorted_results

    def _filter_concept(
        self,
        concept: ConceptEntry,
        vocabularies: list[VocabularyType] | None,
        domains: list[str] | None,
    ) -> bool:
        """Check if concept matches vocabulary and domain filters."""
        if vocabularies:
            vocab_match = any(
                v.value == concept.vocabulary_id or v == VocabularyType.ALL
                for v in vocabularies
            )
            if not vocab_match:
                return False

        if domains and concept.domain_id not in domains:
            return False

        return True

    def _add_result(
        self,
        results: dict[int, SearchResult],
        concept: ConceptEntry,
        score: float,
        match_type: MatchType,
        matched_term: str | None = None,
        explanation: str | None = None,
    ) -> None:
        """Add or update a search result."""
        if concept.concept_id in results:
            # Update if new score is higher
            if score > results[concept.concept_id].score:
                results[concept.concept_id].score = score
                results[concept.concept_id].match_type = match_type
                results[concept.concept_id].matched_term = matched_term
                results[concept.concept_id].explanation = explanation
        else:
            results[concept.concept_id] = SearchResult(
                concept_id=concept.concept_id,
                concept_code=concept.concept_code,
                concept_name=concept.concept_name,
                vocabulary_id=concept.vocabulary_id,
                domain_id=concept.domain_id,
                score=score,
                match_type=match_type,
                matched_term=matched_term,
                explanation=explanation,
                synonyms=concept.synonyms[:5],  # Limit synonyms in response
            )

    def _search_exact_code(
        self,
        query: str,
        results: dict[int, SearchResult],
        vocabularies: list[VocabularyType] | None,
        domains: list[str] | None,
    ) -> None:
        """Search for exact code matches."""
        query_lower = query.lower().strip()

        if query_lower in self._code_index:
            for concept_id in self._code_index[query_lower]:
                concept = self._concepts[concept_id]
                if self._filter_concept(concept, vocabularies, domains):
                    self._add_result(
                        results, concept, 1.0, MatchType.EXACT,
                        query, f"Exact code match: {concept.concept_code}"
                    )

    def _search_exact_name(
        self,
        query: str,
        results: dict[int, SearchResult],
        vocabularies: list[VocabularyType] | None,
        domains: list[str] | None,
    ) -> None:
        """Search for exact name matches."""
        query_lower = query.lower().strip()

        if query_lower in self._name_index:
            for concept_id in self._name_index[query_lower]:
                concept = self._concepts[concept_id]
                if self._filter_concept(concept, vocabularies, domains):
                    self._add_result(
                        results, concept, 0.98, MatchType.EXACT,
                        query, f"Exact name match"
                    )

    def _search_synonyms(
        self,
        query: str,
        results: dict[int, SearchResult],
        vocabularies: list[VocabularyType] | None,
        domains: list[str] | None,
    ) -> None:
        """Search for synonym matches."""
        query_lower = query.lower().strip()

        if query_lower in self._synonym_index:
            for concept_id in self._synonym_index[query_lower]:
                concept = self._concepts[concept_id]
                if self._filter_concept(concept, vocabularies, domains):
                    self._add_result(
                        results, concept, 0.95, MatchType.SYNONYM,
                        query, f"Synonym match"
                    )

    def _search_tfidf(
        self,
        query: str,
        results: dict[int, SearchResult],
        vocabularies: list[VocabularyType] | None,
        domains: list[str] | None,
        threshold: float,
    ) -> None:
        """Search using TF-IDF cosine similarity."""
        query_vector = self._tfidf.transform(query)
        if not query_vector:
            return

        # Get candidate concepts
        candidates = self._get_candidate_concepts(vocabularies, domains)

        for concept_id in candidates:
            if concept_id not in self._concept_vectors:
                continue

            similarity = self._tfidf.cosine_similarity(query_vector, self._concept_vectors[concept_id])

            if similarity >= threshold:
                concept = self._concepts[concept_id]
                self._add_result(
                    results, concept, similarity * 0.9, MatchType.SEMANTIC,
                    None, f"TF-IDF similarity: {similarity:.2f}"
                )

    def _search_bm25(
        self,
        query: str,
        results: dict[int, SearchResult],
        vocabularies: list[VocabularyType] | None,
        domains: list[str] | None,
        threshold: float,
    ) -> None:
        """Search using BM25 ranking."""
        candidates = self._get_candidate_concepts(vocabularies, domains)

        # Score all candidates
        scores: list[tuple[int, float]] = []
        for concept_id in candidates:
            score = self._bm25.score(query, concept_id)
            if score > 0:
                scores.append((concept_id, score))

        if not scores:
            return

        # Normalize scores
        max_score = max(s for _, s in scores)

        for concept_id, score in scores:
            normalized_score = score / max_score if max_score > 0 else 0
            if normalized_score >= threshold:
                concept = self._concepts[concept_id]
                self._add_result(
                    results, concept, normalized_score * 0.85, MatchType.SEMANTIC,
                    None, f"BM25 score: {score:.2f}"
                )

    def _search_fuzzy(
        self,
        query: str,
        results: dict[int, SearchResult],
        vocabularies: list[VocabularyType] | None,
        domains: list[str] | None,
        threshold: float,
    ) -> None:
        """Search using fuzzy string matching."""
        candidates = self._get_candidate_concepts(vocabularies, domains)
        query_lower = query.lower()

        # Limit fuzzy search to reasonable number of candidates
        sample_size = min(len(candidates), 5000)
        sampled = list(candidates)[:sample_size]

        for concept_id in sampled:
            concept = self._concepts[concept_id]

            # Check name similarity
            name_sim = FuzzyMatcher.similarity(query_lower, concept.concept_name.lower())
            if name_sim >= 0.7:
                self._add_result(
                    results, concept, name_sim * 0.8, MatchType.FUZZY,
                    concept.concept_name, f"Fuzzy name match: {name_sim:.2f}"
                )
                continue

            # Check code similarity for short queries
            if len(query) <= 10:
                code_sim = FuzzyMatcher.similarity(query_lower, concept.concept_code.lower())
                if code_sim >= 0.8:
                    self._add_result(
                        results, concept, code_sim * 0.75, MatchType.FUZZY,
                        concept.concept_code, f"Fuzzy code match: {code_sim:.2f}"
                    )

    def _get_candidate_concepts(
        self,
        vocabularies: list[VocabularyType] | None,
        domains: list[str] | None,
    ) -> set[int]:
        """Get candidate concept IDs based on filters."""
        if vocabularies is None and domains is None:
            return set(self._concepts.keys())

        candidates: set[int] = set()

        if vocabularies:
            for vocab in vocabularies:
                if vocab == VocabularyType.ALL:
                    candidates.update(self._concepts.keys())
                    break
                elif vocab.value in self._vocabulary_index:
                    candidates.update(self._vocabulary_index[vocab.value])
        else:
            candidates = set(self._concepts.keys())

        if domains:
            domain_concepts: set[int] = set()
            for domain in domains:
                if domain in self._domain_index:
                    domain_concepts.update(self._domain_index[domain])
            candidates &= domain_concepts

        return candidates

    def find_similar(
        self,
        concept_id: int,
        vocabularies: list[VocabularyType] | None = None,
        top_k: int = 10,
        threshold: float = 0.5,
    ) -> list[SearchResult]:
        """Find concepts similar to a given concept.

        Args:
            concept_id: Source concept ID.
            vocabularies: Vocabularies to search for similar concepts.
            top_k: Maximum results.
            threshold: Minimum similarity score.

        Returns:
            List of similar concepts.
        """
        if not self._loaded:
            self.load()

        if concept_id not in self._concepts:
            return []

        source = self._concepts[concept_id]

        # Search using the concept name
        results = self.search_semantic(
            source.concept_name,
            vocabularies=vocabularies,
            top_k=top_k + 1,  # Extra because source might be included
            threshold=threshold,
        )

        # Filter out the source concept
        results = [r for r in results if r.concept_id != concept_id]

        return results[:top_k]

    def crosswalk(
        self,
        concept_id: int,
        target_vocabulary: VocabularyType,
    ) -> list[CrosswalkMapping]:
        """Map a concept to equivalent concepts in another vocabulary.

        Args:
            concept_id: Source concept ID.
            target_vocabulary: Target vocabulary for mapping.

        Returns:
            List of CrosswalkMapping results.
        """
        if not self._loaded:
            self.load()

        if concept_id not in self._concepts:
            return []

        source = self._concepts[concept_id]
        mappings: list[CrosswalkMapping] = []

        # Check stored crosswalk mappings
        target_vocab = target_vocabulary.value
        if target_vocab in source.crosswalk_mappings:
            for target_id in source.crosswalk_mappings[target_vocab]:
                if target_id in self._concepts:
                    target = self._concepts[target_id]
                    mappings.append(CrosswalkMapping(
                        source_concept_id=source.concept_id,
                        source_vocabulary=source.vocabulary_id,
                        source_code=source.concept_code,
                        source_name=source.concept_name,
                        target_concept_id=target.concept_id,
                        target_vocabulary=target.vocabulary_id,
                        target_code=target.concept_code,
                        target_name=target.concept_name,
                        mapping_type="direct",
                        confidence=0.95,
                    ))

        # If no direct mappings, use semantic similarity
        if not mappings:
            similar = self.find_similar(concept_id, [target_vocabulary], top_k=5, threshold=0.6)
            for result in similar:
                mappings.append(CrosswalkMapping(
                    source_concept_id=source.concept_id,
                    source_vocabulary=source.vocabulary_id,
                    source_code=source.concept_code,
                    source_name=source.concept_name,
                    target_concept_id=result.concept_id,
                    target_vocabulary=result.vocabulary_id,
                    target_code=result.concept_code,
                    target_name=result.concept_name,
                    mapping_type="semantic",
                    confidence=result.score,
                ))

        return mappings

    def get_suggestions(
        self,
        prefix: str,
        vocabularies: list[VocabularyType] | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get autocomplete suggestions for a prefix.

        Args:
            prefix: Text prefix for autocomplete.
            vocabularies: Vocabularies to search.
            limit: Maximum suggestions.

        Returns:
            List of suggestion dictionaries.
        """
        if not self._loaded:
            self.load()

        prefix_lower = prefix.lower()
        suggestions: list[tuple[str, int, float]] = []  # (name, concept_id, score)

        candidates = self._get_candidate_concepts(vocabularies, None)

        for concept_id in candidates:
            concept = self._concepts[concept_id]

            # Check name prefix
            if concept.concept_name.lower().startswith(prefix_lower):
                suggestions.append((concept.concept_name, concept_id, 1.0))
            elif prefix_lower in concept.concept_name.lower():
                suggestions.append((concept.concept_name, concept_id, 0.8))

            # Check code prefix
            if concept.concept_code.lower().startswith(prefix_lower):
                suggestions.append((f"{concept.concept_code}: {concept.concept_name}", concept_id, 0.9))

            if len(suggestions) >= limit * 3:  # Get extra for sorting
                break

        # Sort by score and deduplicate
        suggestions.sort(key=lambda x: x[2], reverse=True)
        seen: set[int] = set()
        result: list[dict[str, Any]] = []

        for name, concept_id, score in suggestions:
            if concept_id not in seen:
                seen.add(concept_id)
                concept = self._concepts[concept_id]
                result.append({
                    "concept_id": concept_id,
                    "concept_code": concept.concept_code,
                    "concept_name": concept.concept_name,
                    "vocabulary_id": concept.vocabulary_id,
                    "domain_id": concept.domain_id,
                    "display": name,
                })
            if len(result) >= limit:
                break

        return result

    def cluster_results(
        self,
        results: list[SearchResult],
    ) -> list[ClusterResult]:
        """Cluster search results by concept type/domain.

        Args:
            results: Search results to cluster.

        Returns:
            List of ClusterResult objects.
        """
        clusters: dict[str, list[SearchResult]] = defaultdict(list)

        for result in results:
            # Use vocabulary + domain as cluster key
            cluster_key = f"{result.vocabulary_id}:{result.domain_id}"
            clusters[cluster_key].append(result)

        # Convert to ClusterResult objects
        cluster_results: list[ClusterResult] = []
        for key, cluster_results_list in clusters.items():
            vocab, domain = key.split(":", 1)
            cluster_results.append(ClusterResult(
                cluster_id=key,
                cluster_name=f"{vocab} - {domain}",
                concept_type=domain,
                results=sorted(cluster_results_list, key=lambda x: x.score, reverse=True),
                total_count=len(cluster_results_list),
            ))

        # Sort clusters by total count
        cluster_results.sort(key=lambda x: x.total_count, reverse=True)

        return cluster_results

    def get_concept(self, concept_id: int) -> ConceptEntry | None:
        """Get a concept by ID."""
        if not self._loaded:
            self.load()
        return self._concepts.get(concept_id)

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        if not self._loaded:
            self.load()
        return self._stats


def get_semantic_search_service() -> SemanticSearchService:
    """Get the singleton SemanticSearchService instance."""
    global _semantic_search_instance

    if _semantic_search_instance is None:
        with _semantic_search_lock:
            if _semantic_search_instance is None:
                logger.info("Creating singleton SemanticSearchService instance")
                _semantic_search_instance = SemanticSearchService()
                _semantic_search_instance.load()

    return _semantic_search_instance


def reset_semantic_search_service() -> None:
    """Reset the singleton instance (for testing only)."""
    global _semantic_search_instance
    with _semantic_search_lock:
        _semantic_search_instance = None
