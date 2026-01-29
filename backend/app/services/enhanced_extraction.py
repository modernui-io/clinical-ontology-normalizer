"""Enhanced Entity Extraction Service.

Provides high-quality entity extraction with:
- Entity deduplication and normalization
- Confidence scoring
- Caching for performance
- Retry logic for reliability
- Integration with vocabulary services for OMOP mapping
"""

from __future__ import annotations

import hashlib
import logging
import re
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class ExtractedEntity:
    """A normalized clinical entity."""

    text: str
    normalized_text: str
    entity_type: str  # condition, drug, measurement, procedure
    confidence: float = 1.0

    # Optional value/unit for measurements
    value: str | None = None
    unit: str | None = None

    # OMOP mapping (if available)
    omop_concept_id: int | None = None
    omop_concept_name: str | None = None

    # Source information
    span_start: int = 0
    span_end: int = 0
    section: str | None = None

    # Additional metadata
    icd10_code: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionResult:
    """Result from entity extraction."""

    document_id: str
    entities: list[ExtractedEntity]
    processing_time_ms: float

    # Quality metrics
    raw_mention_count: int = 0
    deduplicated_count: int = 0
    low_confidence_filtered: int = 0

    # Errors/warnings
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ============================================================================
# Entity Normalizer
# ============================================================================


class EntityNormalizer:
    """Normalizes and deduplicates extracted entities."""

    # Condition normalization mappings
    CONDITION_ALIASES = {
        # Diabetes
        "dm": "type 2 diabetes mellitus",
        "dm2": "type 2 diabetes mellitus",
        "dm1": "type 1 diabetes mellitus",
        "type 2 diabetes": "type 2 diabetes mellitus",
        "type 1 diabetes": "type 1 diabetes mellitus",
        "diabetes mellitus": "type 2 diabetes mellitus",
        "niddm": "type 2 diabetes mellitus",
        "iddm": "type 1 diabetes mellitus",

        # Hypertension
        "htn": "hypertension",
        "high blood pressure": "hypertension",
        "elevated blood pressure": "hypertension",

        # Heart conditions
        "chf": "heart failure",
        "hfref": "heart failure with reduced ejection fraction",
        "hfpef": "heart failure with preserved ejection fraction",
        "cad": "coronary artery disease",
        "afib": "atrial fibrillation",
        "a-fib": "atrial fibrillation",
        "af": "atrial fibrillation",

        # Kidney
        "ckd": "chronic kidney disease",
        "aki": "acute kidney injury",
        "arf": "acute renal failure",
        "esrd": "end-stage renal disease",

        # Pulmonary
        "copd": "chronic obstructive pulmonary disease",
        "sob": "shortness of breath",
        "dyspnea": "shortness of breath",
        "pe": "pulmonary embolism",
        "dvt": "deep vein thrombosis",
        "osa": "obstructive sleep apnea",

        # GI
        "gerd": "gastroesophageal reflux disease",
        "nausea/vomiting": "nausea and vomiting",
        "n/v": "nausea and vomiting",

        # Neuro
        "cva": "stroke",
        "tia": "transient ischemic attack",
        "ha": "headache",
        "gad": "generalized anxiety disorder",

        # Other
        "bph": "benign prostatic hyperplasia",
        "uti": "urinary tract infection",
        "uri": "upper respiratory infection",
        "dka": "diabetic ketoacidosis",
        "hhs": "hyperosmolar hyperglycemic state",
    }

    # Drug normalization (generic name preference)
    DRUG_ALIASES = {
        "lantus": "insulin glargine",
        "humalog": "insulin lispro",
        "novolog": "insulin aspart",
        "lasix": "furosemide",
        "coreg": "carvedilol",
        "norvasc": "amlodipine",
        "zoloft": "sertraline",
        "lipitor": "atorvastatin",
        "crestor": "rosuvastatin",
        "protonix": "pantoprazole",
        "prilosec": "omeprazole",
        "nexium": "esomeprazole",
        "zofran": "ondansetron",
        "benadryl": "diphenhydramine",
        "tylenol": "acetaminophen",
        "advil": "ibuprofen",
        "motrin": "ibuprofen",
        "aleve": "naproxen",
        "coumadin": "warfarin",
        "eliquis": "apixaban",
        "xarelto": "rivaroxaban",
        "plavix": "clopidogrel",
        "glucophage": "metformin",
        "lopressor": "metoprolol",
        "toprol": "metoprolol",
        "zestril": "lisinopril",
        "prinivil": "lisinopril",
        "aldactone": "spironolactone",
        "spiriva": "tiotropium",
        "flomax": "tamsulosin",
        "fosamax": "alendronate",
        "claritin": "loratadine",
        "zyrtec": "cetirizine",
        "solumedrol": "methylprednisolone",
        "decadron": "dexamethasone",
        "zithromax": "azithromycin",
        "z-pack": "azithromycin",
    }

    @classmethod
    def normalize_condition(cls, text: str) -> str:
        """Normalize a condition name."""
        normalized = text.lower().strip()
        return cls.CONDITION_ALIASES.get(normalized, normalized)

    @classmethod
    def normalize_drug(cls, text: str) -> str:
        """Normalize a drug name to generic."""
        normalized = text.lower().strip()
        return cls.DRUG_ALIASES.get(normalized, normalized)

    @classmethod
    def normalize_entity(cls, entity: ExtractedEntity) -> ExtractedEntity:
        """Normalize an entity based on its type."""
        if entity.entity_type == "condition":
            entity.normalized_text = cls.normalize_condition(entity.text)
        elif entity.entity_type == "drug":
            entity.normalized_text = cls.normalize_drug(entity.text)
        else:
            entity.normalized_text = entity.text.lower().strip()

        return entity


# ============================================================================
# Entity Deduplicator
# ============================================================================


class EntityDeduplicator:
    """Removes duplicate entities from extraction results."""

    @staticmethod
    def deduplicate(entities: list[ExtractedEntity]) -> list[ExtractedEntity]:
        """
        Remove duplicate entities, keeping the highest confidence version.

        Args:
            entities: List of extracted entities

        Returns:
            Deduplicated list of entities
        """
        # Group by (normalized_text, entity_type)
        grouped: dict[tuple[str, str], list[ExtractedEntity]] = defaultdict(list)

        for entity in entities:
            key = (entity.normalized_text, entity.entity_type)
            grouped[key].append(entity)

        # Keep highest confidence from each group
        deduplicated = []
        for key, group in grouped.items():
            best = max(group, key=lambda e: e.confidence)

            # Merge attributes from all instances
            for e in group:
                if e != best:
                    best.attributes.update(e.attributes)
                    # Keep value/unit if not set
                    if not best.value and e.value:
                        best.value = e.value
                    if not best.unit and e.unit:
                        best.unit = e.unit

            deduplicated.append(best)

        return deduplicated


# ============================================================================
# Caching Layer
# ============================================================================


class ExtractionCache:
    """LRU cache for extraction results."""

    def __init__(self, max_size: int = 1000):
        self._cache: dict[str, tuple[ExtractionResult, float]] = {}
        self._max_size = max_size
        self._lock = threading.Lock()
        self._ttl_seconds = 3600  # 1 hour TTL
        self._hits = 0
        self._misses = 0

    def _make_key(self, text: str, options: dict[str, Any] | None = None) -> str:
        """Create cache key from text and options."""
        content = text
        if options:
            content += str(sorted(options.items()))
        return hashlib.md5(content.encode()).hexdigest()

    def get(self, text: str, options: dict[str, Any] | None = None) -> ExtractionResult | None:
        """Get cached result if available and not expired."""
        key = self._make_key(text, options)

        with self._lock:
            if key in self._cache:
                result, timestamp = self._cache[key]
                if time.time() - timestamp < self._ttl_seconds:
                    self._hits += 1
                    return result
                else:
                    # Expired
                    del self._cache[key]

            self._misses += 1
            return None

    def put(self, text: str, result: ExtractionResult, options: dict[str, Any] | None = None) -> None:
        """Store result in cache."""
        key = self._make_key(text, options)

        with self._lock:
            # Evict oldest if at capacity
            if len(self._cache) >= self._max_size:
                oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
                del self._cache[oldest_key]

            self._cache[key] = (result, time.time())

    def clear(self) -> None:
        """Clear the cache."""
        with self._lock:
            self._cache.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self._hits / total if total > 0 else 0,
            }


# ============================================================================
# Retry Logic
# ============================================================================


def with_retry(
    func: Callable,
    max_retries: int = 3,
    backoff_factor: float = 1.5,
    initial_delay: float = 0.1,
) -> Callable:
    """
    Decorator to add retry logic with exponential backoff.

    Args:
        func: Function to wrap
        max_retries: Maximum number of retry attempts
        backoff_factor: Multiplier for delay between retries
        initial_delay: Initial delay in seconds

    Returns:
        Wrapped function with retry logic
    """
    def wrapper(*args, **kwargs):
        delay = initial_delay
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < max_retries:
                    time.sleep(delay)
                    delay *= backoff_factor

        raise last_exception

    return wrapper


# ============================================================================
# Enhanced Extraction Service
# ============================================================================


class EnhancedExtractionService:
    """
    High-quality entity extraction service with:
    - Entity normalization and deduplication
    - Confidence filtering
    - Caching for performance
    - Retry logic for reliability
    """

    def __init__(
        self,
        min_confidence: float = 0.3,
        enable_cache: bool = True,
        cache_size: int = 1000,
    ):
        self._min_confidence = min_confidence
        self._cache = ExtractionCache(cache_size) if enable_cache else None
        self._lock = threading.Lock()

        # Patterns for extraction
        self._condition_patterns = self._build_condition_patterns()
        self._drug_patterns = self._build_drug_patterns()
        self._measurement_patterns = self._build_measurement_patterns()

    def _build_condition_patterns(self) -> list[tuple[re.Pattern, str, float]]:
        """Build regex patterns for condition extraction."""
        patterns = [
            # High confidence - specific conditions
            (r'\b(type [12] diabetes mellitus)\b', 'diabetes', 0.95),
            (r'\b(diabetic ketoacidosis)\b', 'dka', 0.95),
            (r'\b(heart failure with reduced ejection fraction)\b', 'hfref', 0.95),
            (r'\b(acute myocardial infarction)\b', 'ami', 0.95),
            (r'\b(chronic obstructive pulmonary disease)\b', 'copd', 0.95),
            (r'\b(transient ischemic attack)\b', 'tia', 0.95),
            (r'\b(pulmonary embolism)\b', 'pe', 0.95),
            (r'\b(acute kidney injury)\b', 'aki', 0.95),
            (r'\b(acute appendicitis)\b', 'appendicitis', 0.95),
            (r'\b(gastroesophageal reflux disease)\b', 'gerd', 0.95),

            # Medium-high confidence - common conditions
            (r'\b(diabetes mellitus)\b', 'diabetes', 0.90),
            (r'\b(hypertension)\b', 'hypertension', 0.90),
            (r'\b(hyperlipidemia)\b', 'hyperlipidemia', 0.90),
            (r'\b(atrial fibrillation)\b', 'afib', 0.90),
            (r'\b(heart failure)\b', 'hf', 0.90),
            (r'\b(chronic kidney disease)\b', 'ckd', 0.90),
            (r'\b(coronary artery disease)\b', 'cad', 0.90),
            (r'\b(obesity)\b', 'obesity', 0.90),
            (r'\b(anemia)\b', 'anemia', 0.90),
            (r'\b(depression)\b', 'depression', 0.85),
            (r'\b(anxiety)\b', 'anxiety', 0.85),
            (r'\b(osteoporosis)\b', 'osteoporosis', 0.90),
            (r'\b(osteoarthritis)\b', 'osteoarthritis', 0.90),
            (r'\b(sleep apnea)\b', 'sleep_apnea', 0.90),
            (r'\b(pleural effusion)\b', 'effusion', 0.90),

            # Medium confidence - abbreviated forms
            (r'\b(dm2?)\b', 'dm', 0.75),
            (r'\b(htn)\b', 'htn', 0.80),
            (r'\b(hfref|hfpef)\b', 'hf_type', 0.85),
            (r'\b(afib|a-?fib)\b', 'afib', 0.80),
            (r'\b(copd)\b', 'copd', 0.85),
            (r'\b(ckd)\b', 'ckd', 0.80),
            (r'\b(cad)\b', 'cad', 0.80),
            (r'\b(dka)\b', 'dka', 0.85),
            (r'\b(pe\b)\b', 'pe', 0.70),  # Lower due to ambiguity
            (r'\b(tia)\b', 'tia', 0.85),
            (r'\b(aki)\b', 'aki', 0.80),
            (r'\b(bph)\b', 'bph', 0.80),
            (r'\b(gerd)\b', 'gerd', 0.80),
            (r'\b(gad)\b', 'gad', 0.75),
            (r'\b(osa)\b', 'osa', 0.80),

            # Lower confidence - symptoms/findings
            (r'\b(chest pain)\b', 'chest_pain', 0.80),
            (r'\b(abdominal pain)\b', 'abd_pain', 0.80),
            (r'\b(headache)\b', 'headache', 0.75),
            (r'\b(nausea)\b', 'nausea', 0.75),
            (r'\b(vomiting)\b', 'vomiting', 0.75),
            (r'\b(dyspnea|shortness of breath)\b', 'dyspnea', 0.80),
            (r'\b(edema)\b', 'edema', 0.70),
            (r'\b(hyperkalemia)\b', 'hyperkalemia', 0.85),
            (r'\b(hypoglycemia)\b', 'hypoglycemia', 0.85),
            (r'\b(dehydration)\b', 'dehydration', 0.80),
            (r'\b(urticaria|hives)\b', 'urticaria', 0.85),
            (r'\b(allergic reaction)\b', 'allergic', 0.80),
            (r'\b(costochondritis)\b', 'costochondritis', 0.90),
            (r'\b(migraine)\b', 'migraine', 0.85),
            (r'\b(pulmonary edema)\b', 'pulm_edema', 0.90),
            (r'\b(carotid.{0,15}stenosis)\b', 'carotid_stenosis', 0.85),
        ]

        return [(re.compile(p, re.IGNORECASE), name, conf) for p, name, conf in patterns]

    def _build_drug_patterns(self) -> list[tuple[re.Pattern, str, float]]:
        """Build regex patterns for drug extraction."""
        drugs = [
            # Diabetes medications
            ('metformin', 0.95), ('insulin glargine', 0.95), ('insulin lispro', 0.95),
            ('insulin aspart', 0.95), ('glipizide', 0.90), ('glyburide', 0.90),
            ('sitagliptin', 0.90), ('empagliflozin', 0.90), ('dapagliflozin', 0.90),
            ('semaglutide', 0.90), ('liraglutide', 0.90),

            # Cardiac medications
            ('lisinopril', 0.95), ('enalapril', 0.90), ('losartan', 0.90),
            ('valsartan', 0.90), ('amlodipine', 0.95), ('metoprolol', 0.95),
            ('carvedilol', 0.95), ('atenolol', 0.90), ('furosemide', 0.95),
            ('hydrochlorothiazide', 0.90), ('spironolactone', 0.90),
            ('atorvastatin', 0.95), ('rosuvastatin', 0.90), ('simvastatin', 0.90),
            ('aspirin', 0.90), ('clopidogrel', 0.90), ('apixaban', 0.95),
            ('rivaroxaban', 0.90), ('warfarin', 0.90), ('nitroglycerin', 0.90),

            # Pain/Anti-inflammatory
            ('ibuprofen', 0.90), ('naproxen', 0.90), ('acetaminophen', 0.90),
            ('morphine', 0.90), ('oxycodone', 0.85), ('hydrocodone', 0.85),
            ('prednisone', 0.90), ('methylprednisolone', 0.90), ('dexamethasone', 0.90),

            # GI medications
            ('omeprazole', 0.90), ('pantoprazole', 0.90), ('esomeprazole', 0.90),
            ('ondansetron', 0.90), ('metoclopramide', 0.85),

            # Respiratory
            ('albuterol', 0.90), ('tiotropium', 0.90), ('fluticasone', 0.85),
            ('salmeterol', 0.85), ('budesonide', 0.85), ('ipratropium', 0.85),
            ('azithromycin', 0.90), ('amoxicillin', 0.90), ('levofloxacin', 0.90),

            # Psych medications
            ('sertraline', 0.90), ('fluoxetine', 0.90), ('escitalopram', 0.90),
            ('bupropion', 0.85), ('trazodone', 0.85), ('lorazepam', 0.85),

            # Other
            ('tamsulosin', 0.90), ('alendronate', 0.90), ('levothyroxine', 0.90),
            ('gabapentin', 0.85), ('pregabalin', 0.85),
            ('diphenhydramine', 0.85), ('cetirizine', 0.85), ('loratadine', 0.85),
            ('epinephrine', 0.90), ('epipen', 0.90),
            ('sumatriptan', 0.85),
        ]

        return [(re.compile(rf'\b({drug})\b', re.IGNORECASE), drug, conf) for drug, conf in drugs]

    def _build_measurement_patterns(self) -> list[tuple[re.Pattern, str, str, float]]:
        """Build regex patterns for measurement extraction."""
        patterns = [
            # Vitals
            (r'\b(?:bp|blood pressure)[:\s]+(\d+/\d+)', 'Blood Pressure', 'mmHg', 0.95),
            (r'\b(?:hr|heart rate)[:\s]+(\d+)', 'Heart Rate', 'bpm', 0.90),
            (r'\b(?:rr|respiratory rate)[:\s]+(\d+)', 'Respiratory Rate', '/min', 0.90),
            (r'\b(?:temp|temperature)[:\s]+(\d+\.?\d*)', 'Temperature', 'C', 0.90),
            (r'\b(?:spo2|oxygen saturation|o2 sat)[:\s]+(\d+)', 'SpO2', '%', 0.95),

            # Labs
            (r'\b(?:hba1c|a1c)[:\s]+(\d+\.?\d*)\s*%?', 'HbA1c', '%', 0.95),
            (r'\bglucose[:\s]+(\d+)', 'Glucose', 'mg/dL', 0.90),
            (r'\bcreatinine[:\s]+(\d+\.?\d*)', 'Creatinine', 'mg/dL', 0.90),
            (r'\b(?:k\+?|potassium)[:\s]+(\d+\.?\d*)', 'Potassium', 'mmol/L', 0.90),
            (r'\b(?:na\+?|sodium)[:\s]+(\d+)', 'Sodium', 'mmol/L', 0.90),
            (r'\bbnp[:\s]+(\d+)', 'BNP', 'pg/mL', 0.90),
            (r'\b(?:hgb|hemoglobin)[:\s]+(\d+\.?\d*)', 'Hemoglobin', 'g/dL', 0.90),
            (r'\bwbc[:\s]+(\d+\.?\d*)', 'WBC', 'K/uL', 0.90),
            (r'\btroponin[:\s]+<?(\d+\.?\d*)', 'Troponin', 'ng/mL', 0.90),
            (r'\bldl[:\s]+(\d+)', 'LDL', 'mg/dL', 0.85),
            (r'\b(?:egfr|gfr)[:\s]+(\d+)', 'eGFR', 'mL/min', 0.85),
            (r'\bph[:\s]+(\d+\.?\d*)', 'pH', '', 0.85),
            (r'\bpco2[:\s]+(\d+)', 'pCO2', 'mmHg', 0.85),
            (r'\bbicarbonate[:\s]+(\d+)', 'Bicarbonate', 'mmol/L', 0.85),
            (r'\banion gap[:\s]+(\d+)', 'Anion Gap', '', 0.85),
            (r'\blipase[:\s]+(\d+)', 'Lipase', 'U/L', 0.85),

            # Scores
            (r'\bnihss[:\s]+(\d+)', 'NIHSS', '', 0.95),
            (r'\balvarado[:\s]+(\d+)', 'Alvarado Score', '', 0.90),
        ]

        return [(re.compile(p, re.IGNORECASE), name, unit, conf) for p, name, unit, conf in patterns]

    def extract(self, document_id: str, text: str) -> ExtractionResult:
        """
        Extract entities from clinical text.

        Args:
            document_id: Document identifier
            text: Clinical text to process

        Returns:
            ExtractionResult with normalized, deduplicated entities
        """
        # Check cache
        if self._cache:
            cached = self._cache.get(text)
            if cached:
                return cached

        start_time = time.time()
        entities: list[ExtractedEntity] = []
        warnings: list[str] = []

        # Extract conditions
        for pattern, name, confidence in self._condition_patterns:
            for match in pattern.finditer(text):
                entity = ExtractedEntity(
                    text=match.group(0),
                    normalized_text="",
                    entity_type="condition",
                    confidence=confidence,
                    span_start=match.start(),
                    span_end=match.end(),
                )
                entity = EntityNormalizer.normalize_entity(entity)
                entities.append(entity)

        # Extract drugs
        for pattern, name, confidence in self._drug_patterns:
            for match in pattern.finditer(text):
                entity = ExtractedEntity(
                    text=match.group(0),
                    normalized_text="",
                    entity_type="drug",
                    confidence=confidence,
                    span_start=match.start(),
                    span_end=match.end(),
                )
                entity = EntityNormalizer.normalize_entity(entity)
                entities.append(entity)

        # Extract measurements
        for pattern, name, unit, confidence in self._measurement_patterns:
            for match in pattern.finditer(text):
                entity = ExtractedEntity(
                    text=name,
                    normalized_text=name.lower(),
                    entity_type="measurement",
                    confidence=confidence,
                    value=match.group(1),
                    unit=unit,
                    span_start=match.start(),
                    span_end=match.end(),
                )
                entities.append(entity)

        # Track raw count
        raw_count = len(entities)

        # Filter by confidence
        filtered_entities = [e for e in entities if e.confidence >= self._min_confidence]
        low_conf_count = raw_count - len(filtered_entities)

        # Deduplicate
        deduplicated = EntityDeduplicator.deduplicate(filtered_entities)

        # Sort by span position
        deduplicated.sort(key=lambda e: e.span_start)

        processing_time = (time.time() - start_time) * 1000

        result = ExtractionResult(
            document_id=document_id,
            entities=deduplicated,
            processing_time_ms=processing_time,
            raw_mention_count=raw_count,
            deduplicated_count=len(deduplicated),
            low_confidence_filtered=low_conf_count,
            warnings=warnings,
        )

        # Cache result
        if self._cache:
            self._cache.put(text, result)

        return result

    def extract_with_retry(
        self,
        document_id: str,
        text: str,
        max_retries: int = 3,
    ) -> ExtractionResult:
        """
        Extract entities with retry logic.

        Args:
            document_id: Document identifier
            text: Clinical text to process
            max_retries: Maximum retry attempts

        Returns:
            ExtractionResult with normalized, deduplicated entities
        """
        retry_func = with_retry(self.extract, max_retries=max_retries)
        return retry_func(document_id, text)

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        if self._cache:
            return self._cache.get_stats()
        return {"enabled": False}

    def clear_cache(self) -> None:
        """Clear the extraction cache."""
        if self._cache:
            self._cache.clear()


# ============================================================================
# Singleton Pattern
# ============================================================================


_service_instance: EnhancedExtractionService | None = None
_service_lock = threading.Lock()


def get_enhanced_extraction_service() -> EnhancedExtractionService:
    """Get or create the singleton service instance."""
    global _service_instance

    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = EnhancedExtractionService()

    return _service_instance


def reset_enhanced_extraction_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _service_instance
    with _service_lock:
        _service_instance = None
