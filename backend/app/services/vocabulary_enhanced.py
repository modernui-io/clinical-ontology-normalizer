"""Enhanced vocabulary service with full OMOP vocabulary and UMLS synonyms.

This service extends the basic vocabulary service with:
- Full OMOP vocabulary loading (~10k+ concepts)
- UMLS synonym expansion
- Semantic similarity search using embeddings
- Efficient lookup with Aho-Corasick automaton
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any, ClassVar

import numpy as np

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SentenceTransformer = None
    SENTENCE_TRANSFORMERS_AVAILABLE = False

from app.schemas.base import Domain
from app.services.vocabulary import OMOPConcept, VocabularyService

logger = logging.getLogger(__name__)


# ============================================================================
# UMLS Synonym Patterns
# ============================================================================

# Common medical synonym patterns for automatic expansion
SYNONYM_PATTERNS = {
    # Spelling variations
    "emia": ["emia", "aemia"],
    "edema": ["edema", "oedema"],
    "fiber": ["fiber", "fibre"],
    "tumor": ["tumor", "tumour"],
    "anemia": ["anemia", "anaemia"],
    "leukemia": ["leukemia", "leukaemia"],
    "esophagus": ["esophagus", "oesophagus"],
    "estrogen": ["estrogen", "oestrogen"],
    "fetus": ["fetus", "foetus"],
    "hemoglobin": ["hemoglobin", "haemoglobin"],
    "hemorrhage": ["hemorrhage", "haemorrhage"],

    # Common abbreviation patterns
    "disease": ["disease", "dis", "disorder"],
    "syndrome": ["syndrome", "synd"],
    "acute": ["acute", "a.", "ac."],
    "chronic": ["chronic", "chr", "c."],
    "bilateral": ["bilateral", "b/l", "bil"],
    "unilateral": ["unilateral", "u/l", "uni"],
}

# Common clinical abbreviations to expand
ABBREVIATION_EXPANSIONS = {
    # Conditions
    "htn": ["hypertension", "high blood pressure"],
    "dm": ["diabetes mellitus", "diabetes", "type 2 diabetes"],
    "dm2": ["type 2 diabetes mellitus", "type 2 diabetes", "t2dm"],
    "dm1": ["type 1 diabetes mellitus", "type 1 diabetes", "t1dm"],
    "cad": ["coronary artery disease", "coronary heart disease"],
    "chf": ["congestive heart failure", "heart failure"],
    "afib": ["atrial fibrillation", "a-fib", "af"],
    "copd": ["chronic obstructive pulmonary disease"],
    "ckd": ["chronic kidney disease", "chronic renal disease"],
    "aki": ["acute kidney injury", "acute renal failure"],
    "uti": ["urinary tract infection", "bladder infection"],
    "cva": ["cerebrovascular accident", "stroke"],
    "tia": ["transient ischemic attack", "mini stroke"],
    "mi": ["myocardial infarction", "heart attack"],
    "pe": ["pulmonary embolism", "lung clot"],
    "dvt": ["deep vein thrombosis", "leg clot"],
    "gerd": ["gastroesophageal reflux disease", "acid reflux"],
    "ibs": ["irritable bowel syndrome", "spastic colon"],
    "ra": ["rheumatoid arthritis", "rheumatoid disease"],
    "oa": ["osteoarthritis", "degenerative joint disease"],
    "bph": ["benign prostatic hyperplasia", "enlarged prostate"],
    "osa": ["obstructive sleep apnea", "sleep apnea"],

    # Drugs
    "asa": ["aspirin", "acetylsalicylic acid"],
    "apap": ["acetaminophen", "tylenol", "paracetamol"],
    "hctz": ["hydrochlorothiazide", "water pill"],
    "ppi": ["proton pump inhibitor", "acid reducer"],
    "ssri": ["selective serotonin reuptake inhibitor", "antidepressant"],
    "snri": ["serotonin-norepinephrine reuptake inhibitor"],
    "nsaid": ["nonsteroidal anti-inflammatory drug", "anti-inflammatory"],
    "ace": ["angiotensin converting enzyme inhibitor", "ace inhibitor"],
    "arb": ["angiotensin receptor blocker"],
    "ccb": ["calcium channel blocker"],
    "bb": ["beta blocker", "beta-blocker"],

    # Labs/Measurements
    "bp": ["blood pressure"],
    "hr": ["heart rate", "pulse"],
    "rr": ["respiratory rate", "respirations"],
    "spo2": ["oxygen saturation", "o2 sat"],
    "bmi": ["body mass index"],
    "bmp": ["basic metabolic panel"],
    "cmp": ["comprehensive metabolic panel"],
    "cbc": ["complete blood count"],
    "wbc": ["white blood cell count", "white count"],
    "hgb": ["hemoglobin"],
    "hct": ["hematocrit"],
    "plt": ["platelet count", "platelets"],
    "bun": ["blood urea nitrogen"],
    "cr": ["creatinine", "serum creatinine"],
    "gfr": ["glomerular filtration rate"],
    "alt": ["alanine aminotransferase", "sgpt"],
    "ast": ["aspartate aminotransferase", "sgot"],
    "alp": ["alkaline phosphatase"],
    "inr": ["international normalized ratio"],
    "pt": ["prothrombin time"],
    "ptt": ["partial thromboplastin time"],
    "bnp": ["b-type natriuretic peptide"],
    "tsh": ["thyroid stimulating hormone"],
    "hba1c": ["hemoglobin a1c", "glycated hemoglobin", "a1c"],
    "ldl": ["ldl cholesterol", "bad cholesterol"],
    "hdl": ["hdl cholesterol", "good cholesterol"],
    "tg": ["triglycerides"],
    "crp": ["c-reactive protein"],
    "esr": ["erythrocyte sedimentation rate", "sed rate"],

    # Procedures
    "ekg": ["electrocardiogram", "ecg", "12-lead ecg"],
    "echo": ["echocardiogram", "cardiac ultrasound"],
    "cxr": ["chest x-ray", "chest radiograph"],
    "ct": ["computed tomography", "cat scan"],
    "mri": ["magnetic resonance imaging"],
    "us": ["ultrasound", "sonogram"],
    "egd": ["esophagogastroduodenoscopy", "upper endoscopy"],
    "ercp": ["endoscopic retrograde cholangiopancreatography"],
    "pft": ["pulmonary function test", "spirometry"],
    "cabg": ["coronary artery bypass graft", "bypass surgery"],
    "pci": ["percutaneous coronary intervention", "angioplasty"],
    "lp": ["lumbar puncture", "spinal tap"],
    "cvc": ["central venous catheter", "central line"],
}


@dataclass
class EnhancedOMOPConcept(OMOPConcept):
    """OMOP concept with additional fields for enhanced matching."""

    umls_cui: str | None = None
    icd10_codes: list[str] = field(default_factory=list)
    snomed_codes: list[str] = field(default_factory=list)
    rxnorm_codes: list[str] = field(default_factory=list)
    loinc_codes: list[str] = field(default_factory=list)
    embedding: np.ndarray | None = None


class EnhancedVocabularyService(VocabularyService):
    """Enhanced vocabulary service with semantic search and UMLS expansion.

    Extends the base vocabulary service with:
    - Full OMOP vocabulary support
    - UMLS synonym expansion
    - Semantic similarity search using embeddings
    - Efficient multi-pattern matching with Aho-Corasick

    Usage:
        vocab = EnhancedVocabularyService()
        vocab.load()

        # Basic search
        matches = vocab.search("diabetes")

        # Semantic search
        matches = vocab.semantic_search("sugar disease", limit=5)

        # Multi-term extraction
        found = vocab.find_all_concepts("Patient has DM and HTN")
    """

    # Default paths
    FULL_VOCABULARY_PATH: ClassVar[str] = "fixtures/omop_vocabulary_full.json"
    EMBEDDING_MODEL: ClassVar[str] = "all-MiniLM-L6-v2"

    def __init__(
        self,
        fixture_path: str | Path | None = None,
        use_embeddings: bool = True,
        use_automaton: bool = True,
    ) -> None:
        """Initialize the enhanced vocabulary service.

        Args:
            fixture_path: Path to the vocabulary JSON fixture.
            use_embeddings: Enable semantic similarity search.
            use_automaton: Enable Aho-Corasick multi-pattern matching.
        """
        super().__init__(fixture_path)
        self._use_embeddings = use_embeddings
        self._use_automaton = use_automaton
        self._embedder: SentenceTransformer | None = None
        self._concept_embeddings: np.ndarray | None = None
        self._automaton: Any = None

    @property
    def full_vocabulary_path(self) -> Path:
        """Get the full vocabulary file path."""
        return self._find_fixtures_dir() / "omop_vocabulary_full.json"

    def load(self) -> None:
        """Load vocabulary with UMLS expansion and embeddings."""
        if self._loaded:
            return

        start_time = time.perf_counter()

        self._concepts = []
        self._synonym_index = {}

        # Load clinical abbreviations first
        self._load_clinical_abbreviations()
        curated_synonyms = set(self._synonym_index.keys())

        # Try to load full vocabulary first, fall back to basic
        vocab_path = self.full_vocabulary_path
        if not vocab_path.exists():
            vocab_path = self.fixture_path

        if vocab_path.exists():
            with open(vocab_path) as f:
                data = json.load(f)

            for concept_data in data.get("concepts", []):
                # Get base synonyms
                synonyms = list(concept_data.get("synonyms", []))

                # Expand synonyms using patterns
                expanded_synonyms = self._expand_synonyms(synonyms)

                # Filter out already curated synonyms
                final_synonyms = [
                    s for s in expanded_synonyms
                    if s.lower() not in curated_synonyms
                ]

                if not final_synonyms:
                    continue

                concept = OMOPConcept(
                    concept_id=concept_data["concept_id"],
                    concept_name=concept_data["concept_name"],
                    concept_code=concept_data.get("concept_code", ""),
                    vocabulary_id=concept_data.get("vocabulary_id", ""),
                    domain_id=concept_data.get("domain_id", ""),
                    synonyms=final_synonyms,
                )
                self._concepts.append(concept)

                # Build synonym index
                for synonym in final_synonyms:
                    key = synonym.lower()
                    if key not in self._synonym_index:
                        self._synonym_index[key] = []
                    self._synonym_index[key].append(concept)

        # Build Aho-Corasick automaton for efficient multi-pattern matching
        if self._use_automaton:
            self._build_automaton()

        # Build embeddings for semantic search
        if self._use_embeddings:
            self._build_embeddings()

        self._loaded = True
        self._load_time_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            f"Enhanced vocabulary loaded: {len(self._concepts)} concepts, "
            f"{len(self._synonym_index)} terms in {self._load_time_ms:.2f}ms"
        )

    def _expand_synonyms(self, synonyms: list[str]) -> list[str]:
        """Expand synonyms using UMLS patterns and abbreviations."""
        expanded = set(synonyms)

        for synonym in synonyms:
            lower = synonym.lower()

            # Add abbreviation expansions
            if lower in ABBREVIATION_EXPANSIONS:
                expanded.update(ABBREVIATION_EXPANSIONS[lower])

            # Apply spelling variation patterns
            for pattern, variations in SYNONYM_PATTERNS.items():
                if pattern in lower:
                    for var in variations:
                        expanded.add(lower.replace(pattern, var))

        return list(expanded)

    def _build_automaton(self) -> None:
        """Build Aho-Corasick automaton for multi-pattern matching."""
        try:
            import ahocorasick

            self._automaton = ahocorasick.Automaton()
            for term, concepts in self._synonym_index.items():
                self._automaton.add_word(term, (term, concepts))
            self._automaton.make_automaton()
            logger.info(f"Built Aho-Corasick automaton with {len(self._synonym_index)} patterns")

        except ImportError:
            logger.warning("ahocorasick not installed, multi-pattern matching disabled")
            self._automaton = None

    def _build_embeddings(self) -> None:
        """Build concept embeddings for semantic search."""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.warning("sentence_transformers not installed, semantic search disabled")
            self._embedder = None
            self._concept_embeddings = None
            return

        try:
            self._embedder = SentenceTransformer(self.EMBEDDING_MODEL)

            # Embed all concept names
            concept_texts = [c.concept_name for c in self._concepts]
            if concept_texts:
                self._concept_embeddings = self._embedder.encode(
                    concept_texts,
                    show_progress_bar=False,
                    convert_to_numpy=True,
                )
                logger.info(f"Built embeddings for {len(concept_texts)} concepts")

        except Exception as e:
            logger.warning(f"Failed to build embeddings: {e}")
            self._embedder = None
            self._concept_embeddings = None

    def semantic_search(
        self,
        query: str,
        limit: int = 5,
        domain: Domain | None = None,
    ) -> list[tuple[OMOPConcept, float]]:
        """Search concepts using semantic similarity.

        Args:
            query: Natural language query
            limit: Maximum number of results
            domain: Optional domain filter

        Returns:
            List of (concept, similarity_score) tuples
        """
        if not self._loaded:
            self.load()

        if self._embedder is None or self._concept_embeddings is None:
            # Fall back to text search
            matches = self.search(query, limit=limit)
            return [(c, 1.0) for c in matches]

        # Encode query
        query_embedding = self._embedder.encode(
            query,
            show_progress_bar=False,
            convert_to_numpy=True,
        )

        # Compute similarities
        similarities = np.dot(self._concept_embeddings, query_embedding)

        # Get top matches
        indices = np.argsort(similarities)[::-1]

        results = []
        for idx in indices:
            if len(results) >= limit:
                break

            concept = self._concepts[idx]

            # Apply domain filter
            if domain is not None and concept.domain != domain:
                continue

            score = float(similarities[idx])
            if score > 0.3:  # Minimum threshold
                results.append((concept, score))

        return results

    def find_all_concepts(
        self,
        text: str,
    ) -> list[tuple[OMOPConcept, int, int]]:
        """Find all concept mentions in text using Aho-Corasick.

        Args:
            text: Text to search

        Returns:
            List of (concept, start_offset, end_offset) tuples
        """
        if not self._loaded:
            self.load()

        if self._automaton is None:
            return []

        results = []
        text_lower = text.lower()

        for end_idx, (term, concepts) in self._automaton.iter(text_lower):
            start_idx = end_idx - len(term) + 1
            for concept in concepts:
                results.append((concept, start_idx, end_idx + 1))

        # Remove duplicates and overlapping matches
        return self._deduplicate_matches(results)

    def _deduplicate_matches(
        self,
        matches: list[tuple[OMOPConcept, int, int]],
    ) -> list[tuple[OMOPConcept, int, int]]:
        """Remove overlapping matches, keeping longer spans."""
        if not matches:
            return []

        # Sort by start position, then by length (descending)
        sorted_matches = sorted(
            matches,
            key=lambda x: (x[1], -(x[2] - x[1]))
        )

        result = []
        last_end = -1

        for concept, start, end in sorted_matches:
            if start >= last_end:
                result.append((concept, start, end))
                last_end = end

        return result

    def get_enhanced_stats(self) -> dict[str, Any]:
        """Get enhanced vocabulary statistics."""
        stats = self.get_stats()
        stats.update({
            "embeddings_enabled": self._embedder is not None,
            "automaton_enabled": self._automaton is not None,
            "expansion_patterns": len(ABBREVIATION_EXPANSIONS),
        })
        return stats


# Singleton instance and lock
_enhanced_vocabulary_instance: EnhancedVocabularyService | None = None
_enhanced_vocabulary_lock = Lock()


def get_enhanced_vocabulary_service(
    use_embeddings: bool = True,
    use_automaton: bool = True,
) -> EnhancedVocabularyService:
    """Get the singleton EnhancedVocabularyService instance.

    Args:
        use_embeddings: Enable semantic similarity search.
        use_automaton: Enable Aho-Corasick multi-pattern matching.

    Returns:
        The singleton EnhancedVocabularyService instance.
    """
    global _enhanced_vocabulary_instance

    if _enhanced_vocabulary_instance is None:
        with _enhanced_vocabulary_lock:
            if _enhanced_vocabulary_instance is None:
                logger.info("Creating singleton EnhancedVocabularyService instance")
                _enhanced_vocabulary_instance = EnhancedVocabularyService(
                    use_embeddings=use_embeddings,
                    use_automaton=use_automaton,
                )
                _enhanced_vocabulary_instance.load()

    return _enhanced_vocabulary_instance


def reset_enhanced_vocabulary_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _enhanced_vocabulary_instance
    with _enhanced_vocabulary_lock:
        _enhanced_vocabulary_instance = None
