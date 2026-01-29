"""AI-Powered Auto-Coding Service.

This module provides intelligent clinical code suggestions using TF-IDF text matching
and pattern recognition. It integrates ICD-10-CM, CPT, and HCC coding capabilities.

Key capabilities:
1. Analyze clinical documentation text
2. Suggest ICD-10-CM diagnosis codes with confidence scores
3. Suggest CPT procedure codes with evidence
4. Provide HCC risk adjustment codes and RAF values
5. Detect coding opportunities (missing specificity, laterality, etc.)
6. Validate code combinations and bundling rules
7. Export coding worksheets for billing

Uses TF-IDF based text matching with:
- Keyword extraction and medical concept matching
- Code hierarchy awareness (parent/child relationships)
- Specificity scoring (prefer more specific codes)
- Query expansion using synonyms from vocabulary data
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
import logging
import math
import re
import threading
from pathlib import Path
from typing import Any
from collections import Counter

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Data Classes
# ============================================================================

class CodeType(Enum):
    """Type of medical code."""
    ICD10 = "ICD10"
    CPT = "CPT"
    HCPCS = "HCPCS"
    HCC = "HCC"


class ConfidenceLevel(Enum):
    """Confidence level for code suggestions."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CodingOpportunityType(Enum):
    """Type of coding opportunity identified."""
    MISSING_SPECIFICITY = "missing_specificity"
    MISSING_LATERALITY = "missing_laterality"
    MISSING_EPISODE = "missing_episode"
    UNSPECIFIED_CODE = "unspecified_code"
    POSSIBLE_ADDITIONAL = "possible_additional"
    BUNDLING_ISSUE = "bundling_issue"
    HCC_OPPORTUNITY = "hcc_opportunity"


@dataclass
class EvidenceSnippet:
    """Evidence from clinical text supporting a code suggestion."""
    text: str  # The text snippet
    start_offset: int  # Character offset start
    end_offset: int  # Character offset end
    relevance_score: float  # How relevant this evidence is (0-1)
    highlight_terms: list[str] = field(default_factory=list)  # Terms to highlight


@dataclass
class CodeSuggestion:
    """A suggested medical code with supporting evidence."""
    code: str
    code_type: CodeType
    description: str
    confidence: ConfidenceLevel
    confidence_score: float  # Numeric score 0-1

    # Evidence from clinical text
    evidence_snippets: list[EvidenceSnippet] = field(default_factory=list)
    match_reason: str = ""

    # Code details
    category: str = ""
    is_billable: bool = True
    parent_code: str | None = None

    # Related codes
    more_specific_codes: list[tuple[str, str]] = field(default_factory=list)
    related_codes: list[tuple[str, str]] = field(default_factory=list)

    # HCC information (if applicable)
    hcc_code: str | None = None
    hcc_description: str | None = None
    raf_value: float = 0.0

    # Coding guidance
    coding_tips: list[str] = field(default_factory=list)
    use_additional_code: str | None = None
    code_first: str | None = None


@dataclass
class CodingOpportunity:
    """An identified opportunity to improve coding."""
    opportunity_type: CodingOpportunityType
    current_code: str | None
    suggested_code: str | None
    description: str
    impact: str  # e.g., "Improves specificity", "HCC capture", "Revenue impact"
    evidence_text: str = ""
    priority: str = "medium"  # high, medium, low


@dataclass
class ValidationIssue:
    """A code validation issue."""
    issue_type: str  # "invalid_code", "bundling", "incompatible", "duplicate"
    severity: str  # "error", "warning", "info"
    codes_involved: list[str]
    message: str
    suggestion: str = ""


@dataclass
class HCCRiskResult:
    """HCC risk calculation result."""
    total_raf_score: float
    hcc_codes: list[str]
    hcc_details: list[dict[str, Any]]
    estimated_annual_revenue: float
    opportunities: list[CodingOpportunity]


@dataclass
class SuggestionResult:
    """Complete result from AI coding analysis."""
    # Input info
    request_id: str
    text_length: int
    analysis_timestamp: str
    processing_time_ms: float

    # Suggestions by type
    diagnosis_codes: list[CodeSuggestion] = field(default_factory=list)
    procedure_codes: list[CodeSuggestion] = field(default_factory=list)

    # Opportunities and issues
    coding_opportunities: list[CodingOpportunity] = field(default_factory=list)
    validation_issues: list[ValidationIssue] = field(default_factory=list)

    # HCC analysis
    hcc_analysis: HCCRiskResult | None = None

    # E/M suggestion
    em_code: CodeSuggestion | None = None
    em_rationale: str = ""

    # Summary stats
    total_diagnosis_suggestions: int = 0
    total_procedure_suggestions: int = 0
    high_confidence_count: int = 0


@dataclass
class CodingRule:
    """A coding rule or guideline."""
    rule_id: str
    category: str  # "bundling", "sequencing", "modifier", "medical_necessity"
    title: str
    description: str
    codes_affected: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    source: str = ""  # CMS, AMA, etc.


# ============================================================================
# Fixture File Paths
# ============================================================================

FIXTURES_PATH = Path(__file__).parent.parent.parent / "fixtures"
ICD10_FIXTURE_FILE = FIXTURES_PATH / "icd10_codes_full.json"
CPT_FIXTURE_FILE = FIXTURES_PATH / "cpt_codes_full.json"


# ============================================================================
# TF-IDF Implementation
# ============================================================================

class TFIDFVectorizer:
    """Simple TF-IDF vectorizer for text matching."""

    def __init__(self):
        self._vocabulary: dict[str, int] = {}
        self._idf: dict[str, float] = {}
        self._documents: list[dict[str, float]] = []
        self._document_count = 0

    def fit(self, documents: list[str]) -> None:
        """Fit the vectorizer on a list of documents."""
        self._document_count = len(documents)

        # Build vocabulary and compute document frequencies
        doc_freq: dict[str, int] = Counter()

        for doc in documents:
            terms = self._tokenize(doc)
            unique_terms = set(terms)
            for term in unique_terms:
                doc_freq[term] += 1
                if term not in self._vocabulary:
                    self._vocabulary[term] = len(self._vocabulary)

        # Compute IDF for each term
        for term, freq in doc_freq.items():
            # IDF with smoothing
            self._idf[term] = math.log((self._document_count + 1) / (freq + 1)) + 1

    def transform(self, document: str) -> dict[str, float]:
        """Transform a document to TF-IDF vector."""
        terms = self._tokenize(document)
        term_freq = Counter(terms)

        vector: dict[str, float] = {}
        for term, freq in term_freq.items():
            if term in self._vocabulary:
                tf = freq / len(terms) if terms else 0
                idf = self._idf.get(term, 1.0)
                vector[term] = tf * idf

        return vector

    def cosine_similarity(self, vec1: dict[str, float], vec2: dict[str, float]) -> float:
        """Compute cosine similarity between two vectors."""
        # Find common terms
        common_terms = set(vec1.keys()) & set(vec2.keys())

        if not common_terms:
            return 0.0

        # Compute dot product
        dot_product = sum(vec1[term] * vec2[term] for term in common_terms)

        # Compute magnitudes
        mag1 = math.sqrt(sum(v ** 2 for v in vec1.values()))
        mag2 = math.sqrt(sum(v ** 2 for v in vec2.values()))

        if mag1 == 0 or mag2 == 0:
            return 0.0

        return dot_product / (mag1 * mag2)

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text into terms."""
        # Convert to lowercase and extract words
        text_lower = text.lower()
        # Remove punctuation except hyphens within words
        text_clean = re.sub(r'[^\w\s\-]', ' ', text_lower)
        # Split on whitespace
        tokens = text_clean.split()
        # Filter short tokens and stopwords
        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
            'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'need',
            'not', 'no', 'yes', 'other', 'unspecified', 'type', 'without'
        }
        return [t for t in tokens if len(t) > 2 and t not in stopwords]


# ============================================================================
# Clinical Concept Patterns
# ============================================================================

# Patterns to extract clinical concepts from text
CLINICAL_PATTERNS = {
    'diabetes': [
        r'diabet(?:es|ic)',
        r'dm\s*(?:type\s*)?[12]',
        r'type\s*[12]\s*(?:diabetes|dm)',
        r'a1c\s*(?:of\s*)?\d+\.?\d*',
        r'hemoglobin\s*a1c',
        r'insulin\s*(?:dependent|requiring)',
        r'hyperglycemi[ac]',
    ],
    'hypertension': [
        r'hypertension',
        r'htn\b',
        r'high\s*blood\s*pressure',
        r'elevated\s*(?:blood\s*)?(?:bp|pressure)',
        r'bp\s*\d+/\d+',
    ],
    'heart_failure': [
        r'heart\s*failure',
        r'chf\b',
        r'congestive',
        r'hfref\b',
        r'hfpef\b',
        r'ejection\s*fraction',
        r'ef\s*(?:of\s*)?\d+%?',
        r'cardiomyopathy',
    ],
    'copd': [
        r'copd\b',
        r'chronic\s*obstructive',
        r'emphysema',
        r'chronic\s*bronchitis',
        r'gold\s*stage',
    ],
    'ckd': [
        r'ckd\s*(?:stage\s*)?[1-5]',
        r'chronic\s*kidney',
        r'renal\s*(?:failure|disease|insufficiency)',
        r'egfr\s*(?:of\s*)?\d+',
        r'creatinine\s*(?:of\s*)?\d+\.?\d*',
    ],
    'pain': [
        r'(?:chronic|acute)\s*pain',
        r'pain\s*(?:in|of)\s*(?:the\s*)?\w+',
        r'back\s*pain',
        r'neck\s*pain',
        r'headache',
        r'migraine',
    ],
    'depression': [
        r'depression',
        r'depressive\s*(?:disorder|episode)',
        r'mdd\b',
        r'major\s*depression',
    ],
    'obesity': [
        r'obes(?:e|ity)',
        r'bmi\s*(?:of\s*)?\d+',
        r'morbid(?:ly)?\s*obese',
    ],
    'stroke': [
        r'stroke',
        r'cva\b',
        r'cerebrovascular\s*accident',
        r'cerebral\s*infarction',
        r'tia\b',
    ],
    'cancer': [
        r'cancer',
        r'malignant',
        r'neoplasm',
        r'carcinoma',
        r'tumor',
        r'oncolog',
    ],
}

# Medical abbreviation expansions
ABBREVIATION_MAP = {
    'htn': 'hypertension',
    'dm': 'diabetes mellitus',
    'dm1': 'type 1 diabetes',
    'dm2': 'type 2 diabetes',
    'chf': 'congestive heart failure',
    'cad': 'coronary artery disease',
    'copd': 'chronic obstructive pulmonary disease',
    'ckd': 'chronic kidney disease',
    'mi': 'myocardial infarction',
    'cva': 'cerebrovascular accident',
    'afib': 'atrial fibrillation',
    'dvt': 'deep vein thrombosis',
    'pe': 'pulmonary embolism',
    'uri': 'upper respiratory infection',
    'uti': 'urinary tract infection',
    'sob': 'shortness of breath',
    'hpi': 'history of present illness',
    'pmh': 'past medical history',
    'ros': 'review of systems',
    'a1c': 'hemoglobin a1c',
    'bp': 'blood pressure',
    'hr': 'heart rate',
    'rr': 'respiratory rate',
    'bmi': 'body mass index',
    'egfr': 'estimated glomerular filtration rate',
}


# ============================================================================
# Code Bundling Rules
# ============================================================================

BUNDLING_RULES = [
    {
        "primary": "99213",
        "bundled": ["36415", "81002"],  # Blood draw and UA often bundled with office visit
        "note": "Venipuncture and simple UA typically bundled with E/M services"
    },
    {
        "primary": "45378",  # Diagnostic colonoscopy
        "bundled": ["45380", "45381", "45384", "45385"],  # Colonoscopy with biopsy/polypectomy
        "note": "Only bill highest level colonoscopy code"
    },
    {
        "primary": "93000",  # ECG
        "bundled": ["93005", "93010"],
        "note": "Use only one ECG code"
    },
]


# ============================================================================
# AI Coding Service
# ============================================================================

# Singleton instance and lock
_service_instance: "AICodingService | None" = None
_service_lock = threading.Lock()


def get_ai_coding_service() -> "AICodingService":
    """Get the singleton AI coding service instance."""
    global _service_instance
    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = AICodingService()
    return _service_instance


def reset_ai_coding_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _service_instance
    with _service_lock:
        _service_instance = None


class AICodingService:
    """AI-powered clinical coding service using TF-IDF matching."""

    def __init__(self) -> None:
        """Initialize the AI coding service."""
        # Code databases
        self._icd10_codes: dict[str, dict] = {}
        self._cpt_codes: dict[str, dict] = {}

        # TF-IDF vectorizers
        self._icd10_vectorizer = TFIDFVectorizer()
        self._cpt_vectorizer = TFIDFVectorizer()

        # Code vectors for similarity matching
        self._icd10_vectors: dict[str, dict[str, float]] = {}
        self._cpt_vectors: dict[str, dict[str, float]] = {}

        # Synonym indices
        self._icd10_synonyms: dict[str, list[str]] = {}
        self._cpt_synonyms: dict[str, list[str]] = {}

        # HCC mappings
        self._icd10_to_hcc: dict[str, str] = {}
        self._hcc_raf_values: dict[str, float] = {}

        # Load data
        self._load_icd10_codes()
        self._load_cpt_codes()
        self._build_hcc_mappings()

        logger.info(
            f"AICodingService initialized with {len(self._icd10_codes)} ICD-10 codes, "
            f"{len(self._cpt_codes)} CPT codes"
        )

    # =========================================================================
    # Data Loading
    # =========================================================================

    def _load_icd10_codes(self) -> None:
        """Load ICD-10 codes from fixture file."""
        if not ICD10_FIXTURE_FILE.exists():
            logger.warning(f"ICD-10 fixture file not found: {ICD10_FIXTURE_FILE}")
            self._load_default_icd10_codes()
            return

        try:
            with open(ICD10_FIXTURE_FILE, 'r') as f:
                data = json.load(f)

            concepts = data.get('concepts', [])
            descriptions = []

            for concept in concepts:
                code = concept.get('concept_code', '')
                if not code:
                    continue

                description = concept.get('concept_name', '')
                synonyms = concept.get('synonyms', [])

                self._icd10_codes[code] = {
                    'code': code,
                    'description': description,
                    'synonyms': synonyms,
                    'concept_id': concept.get('concept_id'),
                    'domain_id': concept.get('domain_id', ''),
                    'concept_class_id': concept.get('concept_class_id', ''),
                    'is_billable': 'billing' in concept.get('concept_class_id', '').lower(),
                }

                # Build search text for TF-IDF
                search_text = f"{code} {description} {' '.join(synonyms)}"
                descriptions.append(search_text)

                # Build synonym index
                for syn in synonyms:
                    syn_lower = syn.lower()
                    if syn_lower not in self._icd10_synonyms:
                        self._icd10_synonyms[syn_lower] = []
                    self._icd10_synonyms[syn_lower].append(code)

            # Fit TF-IDF vectorizer
            if descriptions:
                self._icd10_vectorizer.fit(descriptions)

                # Create vectors for each code
                for code, code_data in self._icd10_codes.items():
                    search_text = f"{code} {code_data['description']} {' '.join(code_data.get('synonyms', []))}"
                    self._icd10_vectors[code] = self._icd10_vectorizer.transform(search_text)

            logger.info(f"Loaded {len(self._icd10_codes)} ICD-10 codes from fixture")

        except Exception as e:
            logger.error(f"Failed to load ICD-10 codes: {e}")
            self._load_default_icd10_codes()

    def _load_default_icd10_codes(self) -> None:
        """Load a minimal set of default ICD-10 codes."""
        default_codes = [
            ('I10', 'Essential (primary) hypertension', ['hypertension', 'htn', 'high blood pressure']),
            ('E11.9', 'Type 2 diabetes mellitus without complications', ['diabetes', 'dm2', 'type 2 diabetes']),
            ('J06.9', 'Acute upper respiratory infection, unspecified', ['uri', 'cold', 'upper respiratory infection']),
            ('M54.5', 'Low back pain', ['back pain', 'lbp', 'lumbar pain']),
            ('F32.9', 'Major depressive disorder, single episode, unspecified', ['depression', 'mdd']),
            ('I50.9', 'Heart failure, unspecified', ['heart failure', 'chf', 'congestive heart failure']),
            ('J44.9', 'Chronic obstructive pulmonary disease, unspecified', ['copd', 'emphysema']),
            ('N18.9', 'Chronic kidney disease, unspecified', ['ckd', 'chronic kidney disease']),
        ]

        descriptions = []
        for code, description, synonyms in default_codes:
            self._icd10_codes[code] = {
                'code': code,
                'description': description,
                'synonyms': synonyms,
                'is_billable': True,
            }
            search_text = f"{code} {description} {' '.join(synonyms)}"
            descriptions.append(search_text)

            for syn in synonyms:
                syn_lower = syn.lower()
                if syn_lower not in self._icd10_synonyms:
                    self._icd10_synonyms[syn_lower] = []
                self._icd10_synonyms[syn_lower].append(code)

        if descriptions:
            self._icd10_vectorizer.fit(descriptions)
            for code, code_data in self._icd10_codes.items():
                search_text = f"{code} {code_data['description']} {' '.join(code_data.get('synonyms', []))}"
                self._icd10_vectors[code] = self._icd10_vectorizer.transform(search_text)

    def _load_cpt_codes(self) -> None:
        """Load CPT codes from fixture file."""
        if not CPT_FIXTURE_FILE.exists():
            logger.warning(f"CPT fixture file not found: {CPT_FIXTURE_FILE}")
            self._load_default_cpt_codes()
            return

        try:
            with open(CPT_FIXTURE_FILE, 'r') as f:
                data = json.load(f)

            concepts = data.get('concepts', [])
            descriptions = []

            for concept in concepts:
                code = concept.get('concept_code', '')
                if not code:
                    continue

                description = concept.get('concept_name', '')
                synonyms = concept.get('synonyms', [])

                self._cpt_codes[code] = {
                    'code': code,
                    'description': description,
                    'synonyms': synonyms,
                    'category': concept.get('category', ''),
                    'work_rvu': concept.get('work_rvu', 0.0),
                    'typical_time': concept.get('typical_time_minutes', 0),
                }

                search_text = f"{code} {description} {' '.join(synonyms)}"
                descriptions.append(search_text)

                for syn in synonyms:
                    syn_lower = syn.lower()
                    if syn_lower not in self._cpt_synonyms:
                        self._cpt_synonyms[syn_lower] = []
                    self._cpt_synonyms[syn_lower].append(code)

            if descriptions:
                self._cpt_vectorizer.fit(descriptions)
                for code, code_data in self._cpt_codes.items():
                    search_text = f"{code} {code_data['description']} {' '.join(code_data.get('synonyms', []))}"
                    self._cpt_vectors[code] = self._cpt_vectorizer.transform(search_text)

            logger.info(f"Loaded {len(self._cpt_codes)} CPT codes from fixture")

        except Exception as e:
            logger.error(f"Failed to load CPT codes: {e}")
            self._load_default_cpt_codes()

    def _load_default_cpt_codes(self) -> None:
        """Load a minimal set of default CPT codes."""
        default_codes = [
            ('99213', 'Office visit, established patient, low MDM', ['office visit', 'follow up', 'level 3']),
            ('99214', 'Office visit, established patient, moderate MDM', ['office visit', 'follow up', 'level 4']),
            ('99203', 'Office visit, new patient, low MDM', ['new patient', 'level 3 new']),
            ('99204', 'Office visit, new patient, moderate MDM', ['new patient', 'level 4 new']),
            ('93000', 'Electrocardiogram, routine ECG', ['ecg', 'ekg', 'electrocardiogram']),
            ('71046', 'Chest x-ray, 2 views', ['chest xray', 'cxr', 'chest x-ray']),
            ('80053', 'Comprehensive metabolic panel', ['cmp', 'metabolic panel']),
            ('85025', 'Complete blood count', ['cbc', 'complete blood count']),
        ]

        descriptions = []
        for code, description, synonyms in default_codes:
            self._cpt_codes[code] = {
                'code': code,
                'description': description,
                'synonyms': synonyms,
                'category': 'Evaluation and Management' if code.startswith('99') else 'Diagnostic',
            }
            search_text = f"{code} {description} {' '.join(synonyms)}"
            descriptions.append(search_text)

            for syn in synonyms:
                syn_lower = syn.lower()
                if syn_lower not in self._cpt_synonyms:
                    self._cpt_synonyms[syn_lower] = []
                self._cpt_synonyms[syn_lower].append(code)

        if descriptions:
            self._cpt_vectorizer.fit(descriptions)
            for code, code_data in self._cpt_codes.items():
                search_text = f"{code} {code_data['description']} {' '.join(code_data.get('synonyms', []))}"
                self._cpt_vectors[code] = self._cpt_vectorizer.transform(search_text)

    def _build_hcc_mappings(self) -> None:
        """Build HCC mappings from ICD-10 codes."""
        # Simplified HCC mappings - in production, would load from CMS data
        hcc_mappings = {
            # Diabetes with complications
            'E11.21': ('HCC37', 0.302),
            'E11.22': ('HCC37', 0.302),
            'E11.29': ('HCC37', 0.302),
            'E11.311': ('HCC37', 0.302),
            'E11.319': ('HCC37', 0.302),
            'E11.40': ('HCC37', 0.302),
            'E11.42': ('HCC37', 0.302),
            'E11.51': ('HCC37', 0.302),
            'E11.621': ('HCC37', 0.302),
            'E11.65': ('HCC37', 0.302),

            # Heart failure
            'I50.1': ('HCC85', 0.323),
            'I50.20': ('HCC85', 0.323),
            'I50.21': ('HCC85', 0.323),
            'I50.22': ('HCC85', 0.323),
            'I50.23': ('HCC85', 0.323),
            'I50.30': ('HCC85', 0.323),
            'I50.31': ('HCC85', 0.323),
            'I50.32': ('HCC85', 0.323),
            'I50.33': ('HCC85', 0.323),
            'I50.9': ('HCC85', 0.323),

            # CKD Stage 4/5
            'N18.4': ('HCC327', 0.237),
            'N18.5': ('HCC326', 0.237),
            'N18.6': ('HCC326', 0.237),

            # COPD
            'J44.0': ('HCC111', 0.335),
            'J44.1': ('HCC111', 0.335),
            'J44.9': ('HCC111', 0.335),

            # Stroke
            'I63.9': ('HCC100', 0.268),

            # Major depression
            'F32.1': ('HCC155', 0.309),
            'F32.2': ('HCC155', 0.309),
            'F33.1': ('HCC155', 0.309),
            'F33.2': ('HCC155', 0.309),

            # Morbid obesity
            'E66.01': ('HCC48', 0.250),

            # Vascular disease
            'I70.201': ('HCC108', 0.288),
            'I73.9': ('HCC108', 0.288),

            # Rheumatoid arthritis
            'M05.00': ('HCC40', 0.374),
            'M05.10': ('HCC40', 0.374),
            'M06.00': ('HCC40', 0.374),
        }

        for icd10, (hcc, raf) in hcc_mappings.items():
            self._icd10_to_hcc[icd10] = hcc
            self._hcc_raf_values[hcc] = raf

    # =========================================================================
    # Main Analysis Methods
    # =========================================================================

    def suggest_codes(
        self,
        clinical_text: str,
        max_diagnosis_codes: int = 10,
        max_procedure_codes: int = 10,
        include_hcc: bool = True,
        encounter_context: dict[str, Any] | None = None,
    ) -> SuggestionResult:
        """Analyze clinical text and suggest codes.

        Args:
            clinical_text: Clinical documentation text
            max_diagnosis_codes: Maximum diagnosis code suggestions
            max_procedure_codes: Maximum procedure code suggestions
            include_hcc: Whether to include HCC analysis
            encounter_context: Optional context (new_patient, setting, etc.)

        Returns:
            SuggestionResult with all suggestions and analysis
        """
        import time
        from uuid import uuid4

        start_time = time.perf_counter()
        encounter_context = encounter_context or {}

        # Extract clinical concepts from text
        extracted_concepts = self._extract_clinical_concepts(clinical_text)

        # Get diagnosis code suggestions
        diagnosis_codes = self._suggest_diagnosis_codes(
            clinical_text,
            extracted_concepts,
            max_suggestions=max_diagnosis_codes,
        )

        # Get procedure code suggestions
        procedure_codes = self._suggest_procedure_codes(
            clinical_text,
            extracted_concepts,
            encounter_context,
            max_suggestions=max_procedure_codes,
        )

        # Get E/M code suggestion
        em_code, em_rationale = self._suggest_em_code(clinical_text, encounter_context)

        # Identify coding opportunities
        opportunities = self._identify_coding_opportunities(
            clinical_text,
            diagnosis_codes,
            procedure_codes,
        )

        # HCC analysis
        hcc_analysis = None
        if include_hcc:
            diagnosed_codes = [s.code for s in diagnosis_codes]
            hcc_analysis = self.calculate_hcc_risk(diagnosed_codes, clinical_text)

        # Calculate stats
        processing_time = (time.perf_counter() - start_time) * 1000
        high_conf = sum(1 for s in diagnosis_codes + procedure_codes if s.confidence == ConfidenceLevel.HIGH)

        return SuggestionResult(
            request_id=str(uuid4()),
            text_length=len(clinical_text),
            analysis_timestamp=datetime.now(timezone.utc).isoformat(),
            processing_time_ms=round(processing_time, 2),
            diagnosis_codes=diagnosis_codes,
            procedure_codes=procedure_codes,
            coding_opportunities=opportunities,
            validation_issues=[],
            hcc_analysis=hcc_analysis,
            em_code=em_code,
            em_rationale=em_rationale,
            total_diagnosis_suggestions=len(diagnosis_codes),
            total_procedure_suggestions=len(procedure_codes),
            high_confidence_count=high_conf,
        )

    def _extract_clinical_concepts(self, text: str) -> list[dict[str, Any]]:
        """Extract clinical concepts from text using pattern matching."""
        concepts = []
        text_lower = text.lower()

        for concept_type, patterns in CLINICAL_PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text_lower, re.IGNORECASE):
                    concepts.append({
                        'type': concept_type,
                        'text': match.group(0),
                        'start': match.start(),
                        'end': match.end(),
                        'context': text[max(0, match.start()-50):min(len(text), match.end()+50)],
                    })

        return concepts

    def _suggest_diagnosis_codes(
        self,
        clinical_text: str,
        extracted_concepts: list[dict[str, Any]],
        max_suggestions: int = 10,
    ) -> list[CodeSuggestion]:
        """Suggest ICD-10 diagnosis codes based on clinical text."""
        suggestions: list[CodeSuggestion] = []
        seen_codes: set[str] = set()
        text_lower = clinical_text.lower()

        # Expand abbreviations
        expanded_text = self._expand_abbreviations(text_lower)

        # 1. Match extracted concepts to codes
        for concept in extracted_concepts:
            concept_text = concept['text']

            # Check synonym index
            if concept_text in self._icd10_synonyms:
                for code in self._icd10_synonyms[concept_text]:
                    if code not in seen_codes and code in self._icd10_codes:
                        code_data = self._icd10_codes[code]
                        evidence = EvidenceSnippet(
                            text=concept['context'],
                            start_offset=concept['start'],
                            end_offset=concept['end'],
                            relevance_score=0.9,
                            highlight_terms=[concept_text],
                        )

                        suggestion = self._create_diagnosis_suggestion(
                            code_data,
                            ConfidenceLevel.HIGH,
                            0.9,
                            [evidence],
                            f"Direct match for '{concept_text}'",
                        )
                        suggestions.append(suggestion)
                        seen_codes.add(code)

        # 2. TF-IDF similarity search
        query_vector = self._icd10_vectorizer.transform(expanded_text)

        similarity_scores: list[tuple[str, float]] = []
        for code, code_vector in self._icd10_vectors.items():
            if code not in seen_codes:
                similarity = self._icd10_vectorizer.cosine_similarity(query_vector, code_vector)
                if similarity > 0.1:  # Threshold
                    similarity_scores.append((code, similarity))

        # Sort by similarity
        similarity_scores.sort(key=lambda x: x[1], reverse=True)

        for code, score in similarity_scores[:max_suggestions - len(suggestions)]:
            if code in self._icd10_codes:
                code_data = self._icd10_codes[code]

                # Find evidence in text
                evidence = self._find_evidence_for_code(clinical_text, code_data)

                confidence = ConfidenceLevel.HIGH if score > 0.5 else ConfidenceLevel.MEDIUM if score > 0.3 else ConfidenceLevel.LOW

                suggestion = self._create_diagnosis_suggestion(
                    code_data,
                    confidence,
                    score,
                    evidence,
                    f"TF-IDF match (score: {score:.2f})",
                )
                suggestions.append(suggestion)
                seen_codes.add(code)

        # Sort by confidence score
        suggestions.sort(key=lambda s: s.confidence_score, reverse=True)

        return suggestions[:max_suggestions]

    def _suggest_procedure_codes(
        self,
        clinical_text: str,
        extracted_concepts: list[dict[str, Any]],
        encounter_context: dict[str, Any],
        max_suggestions: int = 10,
    ) -> list[CodeSuggestion]:
        """Suggest CPT procedure codes based on clinical text."""
        suggestions: list[CodeSuggestion] = []
        seen_codes: set[str] = set()
        text_lower = clinical_text.lower()

        # Look for procedure-related terms
        procedure_patterns = [
            (r'performed\s+([\w\s]+)', 'procedure'),
            (r'underwent\s+([\w\s]+)', 'procedure'),
            (r'(ct\s+scan|mri|x-?ray|ultrasound)', 'imaging'),
            (r'(colonoscopy|endoscopy|bronchoscopy)', 'endoscopy'),
            (r'(injection|vaccination|immunization)', 'injection'),
            (r'(lab|blood\s+test|urinalysis)', 'lab'),
        ]

        for pattern, proc_type in procedure_patterns:
            for match in re.finditer(pattern, text_lower, re.IGNORECASE):
                matched_text = match.group(0)

                # Check synonym index
                for syn in self._cpt_synonyms:
                    if syn in matched_text or matched_text in syn:
                        for code in self._cpt_synonyms[syn]:
                            if code not in seen_codes and code in self._cpt_codes:
                                code_data = self._cpt_codes[code]
                                evidence = EvidenceSnippet(
                                    text=clinical_text[max(0, match.start()-30):min(len(clinical_text), match.end()+30)],
                                    start_offset=match.start(),
                                    end_offset=match.end(),
                                    relevance_score=0.8,
                                    highlight_terms=[matched_text],
                                )

                                suggestion = self._create_procedure_suggestion(
                                    code_data,
                                    ConfidenceLevel.MEDIUM,
                                    0.75,
                                    [evidence],
                                    f"Match for '{matched_text}'",
                                )
                                suggestions.append(suggestion)
                                seen_codes.add(code)

        # TF-IDF similarity search for CPT
        query_vector = self._cpt_vectorizer.transform(text_lower)

        similarity_scores: list[tuple[str, float]] = []
        for code, code_vector in self._cpt_vectors.items():
            if code not in seen_codes:
                similarity = self._cpt_vectorizer.cosine_similarity(query_vector, code_vector)
                if similarity > 0.1:
                    similarity_scores.append((code, similarity))

        similarity_scores.sort(key=lambda x: x[1], reverse=True)

        for code, score in similarity_scores[:max_suggestions - len(suggestions)]:
            if code in self._cpt_codes:
                code_data = self._cpt_codes[code]
                evidence = self._find_evidence_for_code(clinical_text, code_data)

                confidence = ConfidenceLevel.HIGH if score > 0.5 else ConfidenceLevel.MEDIUM if score > 0.3 else ConfidenceLevel.LOW

                suggestion = self._create_procedure_suggestion(
                    code_data,
                    confidence,
                    score,
                    evidence,
                    f"TF-IDF match (score: {score:.2f})",
                )
                suggestions.append(suggestion)
                seen_codes.add(code)

        suggestions.sort(key=lambda s: s.confidence_score, reverse=True)
        return suggestions[:max_suggestions]

    def _suggest_em_code(
        self,
        clinical_text: str,
        encounter_context: dict[str, Any],
    ) -> tuple[CodeSuggestion | None, str]:
        """Suggest E/M code based on clinical text and context."""
        text_lower = clinical_text.lower()

        # Extract time if documented
        time_match = re.search(r'(?:total\s+)?(?:time|duration)[:\s]+(\d+)\s*(?:min|minutes)', text_lower)
        documented_time = int(time_match.group(1)) if time_match else None

        # Determine patient type
        is_new = encounter_context.get('new_patient', False)
        if 'new patient' in text_lower:
            is_new = True
        elif 'established' in text_lower or 'follow up' in text_lower:
            is_new = False

        # Determine setting
        setting = encounter_context.get('setting', 'office')
        if 'emergency' in text_lower or 'ed ' in text_lower:
            setting = 'emergency'
        elif 'hospital' in text_lower or 'inpatient' in text_lower:
            setting = 'inpatient'

        # Assess MDM complexity
        mdm_complexity = self._assess_mdm_complexity(text_lower)

        # Select E/M code
        if setting == 'emergency':
            codes = {'straightforward': '99281', 'low': '99283', 'moderate': '99284', 'high': '99285'}
            code = codes.get(mdm_complexity, '99283')
        elif setting == 'inpatient':
            codes = {'straightforward': '99221', 'low': '99221', 'moderate': '99222', 'high': '99223'}
            code = codes.get(mdm_complexity, '99221')
        elif is_new:
            if documented_time:
                if documented_time >= 60:
                    code = '99205'
                elif documented_time >= 45:
                    code = '99204'
                elif documented_time >= 30:
                    code = '99203'
                else:
                    code = '99202'
            else:
                codes = {'straightforward': '99202', 'low': '99203', 'moderate': '99204', 'high': '99205'}
                code = codes.get(mdm_complexity, '99203')
        else:
            if documented_time:
                if documented_time >= 40:
                    code = '99215'
                elif documented_time >= 30:
                    code = '99214'
                elif documented_time >= 20:
                    code = '99213'
                else:
                    code = '99212'
            else:
                codes = {'straightforward': '99212', 'low': '99213', 'moderate': '99214', 'high': '99215'}
                code = codes.get(mdm_complexity, '99213')

        # Get code details
        if code not in self._cpt_codes:
            return None, ""

        code_data = self._cpt_codes[code]

        # Build rationale
        rationale_parts = []
        if documented_time:
            rationale_parts.append(f"Time documented: {documented_time} minutes")
        rationale_parts.append(f"MDM complexity: {mdm_complexity}")
        rationale_parts.append(f"Patient type: {'new' if is_new else 'established'}")
        rationale_parts.append(f"Setting: {setting}")

        rationale = "; ".join(rationale_parts)

        suggestion = CodeSuggestion(
            code=code,
            code_type=CodeType.CPT,
            description=code_data.get('description', ''),
            confidence=ConfidenceLevel.HIGH if documented_time else ConfidenceLevel.MEDIUM,
            confidence_score=0.85 if documented_time else 0.70,
            match_reason="E/M level determination",
            category="Evaluation and Management",
            is_billable=True,
            coding_tips=[
                "Document either time OR MDM (use whichever supports higher level)",
                "Ensure all MDM elements are documented",
            ],
        )

        return suggestion, rationale

    def _assess_mdm_complexity(self, text: str) -> str:
        """Assess MDM complexity from clinical text."""
        score = 0

        # Number of problems
        problem_terms = ['chronic', 'acute', 'condition', 'diagnosis', 'problem', 'disease']
        problem_count = sum(1 for term in problem_terms if term in text)
        if problem_count >= 4:
            score += 3
        elif problem_count >= 2:
            score += 2
        else:
            score += 1

        # Data reviewed
        data_terms = ['lab', 'imaging', 'ct', 'mri', 'x-ray', 'ecg', 'pathology', 'result']
        data_count = sum(1 for term in data_terms if term in text)
        if data_count >= 3:
            score += 2
        elif data_count >= 1:
            score += 1

        # Risk
        risk_terms = ['hospitalization', 'surgery', 'high risk', 'severe', 'acute', 'critical']
        risk_count = sum(1 for term in risk_terms if term in text)
        if risk_count >= 2:
            score += 3
        elif risk_count >= 1:
            score += 2

        if score >= 7:
            return 'high'
        elif score >= 4:
            return 'moderate'
        elif score >= 2:
            return 'low'
        else:
            return 'straightforward'

    def _identify_coding_opportunities(
        self,
        clinical_text: str,
        diagnosis_codes: list[CodeSuggestion],
        procedure_codes: list[CodeSuggestion],
    ) -> list[CodingOpportunity]:
        """Identify opportunities to improve coding."""
        opportunities = []
        text_lower = clinical_text.lower()

        # Check for unspecified codes
        for suggestion in diagnosis_codes:
            if 'unspecified' in suggestion.description.lower():
                opportunities.append(CodingOpportunity(
                    opportunity_type=CodingOpportunityType.UNSPECIFIED_CODE,
                    current_code=suggestion.code,
                    suggested_code=None,
                    description=f"Code {suggestion.code} is unspecified. Review for more specific code.",
                    impact="Improves specificity and may capture HCC",
                    priority="medium",
                ))

        # Check for HCC opportunities
        for suggestion in diagnosis_codes:
            if suggestion.hcc_code:
                if suggestion.confidence != ConfidenceLevel.HIGH:
                    opportunities.append(CodingOpportunity(
                        opportunity_type=CodingOpportunityType.HCC_OPPORTUNITY,
                        current_code=suggestion.code,
                        suggested_code=suggestion.code,
                        description=f"HCC opportunity: {suggestion.hcc_description}",
                        impact=f"RAF value: {suggestion.raf_value:.3f}",
                        evidence_text="Review documentation for support",
                        priority="high",
                    ))

        # Check for missing laterality
        laterality_indicators = ['right', 'left', 'bilateral']
        laterality_conditions = ['knee', 'hip', 'shoulder', 'eye', 'ear', 'arm', 'leg']

        for indicator in laterality_indicators:
            if indicator in text_lower:
                for condition in laterality_conditions:
                    if condition in text_lower:
                        opportunities.append(CodingOpportunity(
                            opportunity_type=CodingOpportunityType.MISSING_LATERALITY,
                            current_code=None,
                            suggested_code=None,
                            description=f"Laterality mentioned ({indicator} {condition}). Ensure code reflects laterality.",
                            impact="Improves specificity",
                            priority="low",
                        ))
                        break

        return opportunities

    # =========================================================================
    # Validation Methods
    # =========================================================================

    def validate_codes(
        self,
        diagnosis_codes: list[str],
        procedure_codes: list[str],
    ) -> list[ValidationIssue]:
        """Validate a set of codes for issues.

        Args:
            diagnosis_codes: List of ICD-10 codes
            procedure_codes: List of CPT codes

        Returns:
            List of validation issues
        """
        issues = []

        # Check for invalid codes
        for code in diagnosis_codes:
            if code not in self._icd10_codes:
                issues.append(ValidationIssue(
                    issue_type="invalid_code",
                    severity="error",
                    codes_involved=[code],
                    message=f"ICD-10 code {code} is not recognized",
                    suggestion="Verify code is valid and formatted correctly",
                ))

        for code in procedure_codes:
            if code not in self._cpt_codes:
                issues.append(ValidationIssue(
                    issue_type="invalid_code",
                    severity="error",
                    codes_involved=[code],
                    message=f"CPT code {code} is not recognized",
                    suggestion="Verify code is valid and formatted correctly",
                ))

        # Check for duplicates
        dx_counts = Counter(diagnosis_codes)
        for code, count in dx_counts.items():
            if count > 1:
                issues.append(ValidationIssue(
                    issue_type="duplicate",
                    severity="warning",
                    codes_involved=[code],
                    message=f"Diagnosis code {code} appears {count} times",
                    suggestion="Remove duplicate codes",
                ))

        proc_counts = Counter(procedure_codes)
        for code, count in proc_counts.items():
            if count > 1:
                issues.append(ValidationIssue(
                    issue_type="duplicate",
                    severity="warning",
                    codes_involved=[code],
                    message=f"Procedure code {code} appears {count} times",
                    suggestion="Remove duplicate or add modifier for distinct services",
                ))

        # Check bundling rules
        for rule in BUNDLING_RULES:
            primary = rule['primary']
            bundled = rule['bundled']

            if primary in procedure_codes:
                for bundled_code in bundled:
                    if bundled_code in procedure_codes:
                        issues.append(ValidationIssue(
                            issue_type="bundling",
                            severity="warning",
                            codes_involved=[primary, bundled_code],
                            message=f"Code {bundled_code} may be bundled with {primary}",
                            suggestion=rule['note'],
                        ))

        return issues

    # =========================================================================
    # HCC Methods
    # =========================================================================

    def calculate_hcc_risk(
        self,
        icd10_codes: list[str],
        clinical_text: str | None = None,
    ) -> HCCRiskResult:
        """Calculate HCC risk score from ICD-10 codes.

        Args:
            icd10_codes: List of ICD-10 diagnosis codes
            clinical_text: Optional clinical text for opportunity analysis

        Returns:
            HCCRiskResult with RAF score and details
        """
        hcc_codes = []
        hcc_details = []
        total_raf = 0.0

        for code in icd10_codes:
            if code in self._icd10_to_hcc:
                hcc_code = self._icd10_to_hcc[code]
                if hcc_code not in hcc_codes:
                    hcc_codes.append(hcc_code)
                    raf_value = self._hcc_raf_values.get(hcc_code, 0.0)
                    total_raf += raf_value

                    hcc_details.append({
                        'hcc_code': hcc_code,
                        'icd10_code': code,
                        'icd10_description': self._icd10_codes.get(code, {}).get('description', ''),
                        'raf_value': raf_value,
                    })

        # Calculate estimated revenue (PMPM * 12 months)
        pmpm = 1200.0
        estimated_revenue = total_raf * pmpm * 12

        # Find opportunities from clinical text
        opportunities = []
        if clinical_text:
            text_lower = clinical_text.lower()

            # Check for conditions that might map to HCCs but aren't coded
            hcc_indicators = {
                'HCC37': ['diabetic nephropathy', 'diabetic retinopathy', 'diabetic neuropathy'],
                'HCC85': ['heart failure', 'chf', 'ejection fraction', 'cardiomyopathy'],
                'HCC111': ['copd', 'emphysema', 'chronic bronchitis'],
            }

            for hcc, indicators in hcc_indicators.items():
                if hcc not in hcc_codes:
                    for indicator in indicators:
                        if indicator in text_lower:
                            opportunities.append(CodingOpportunity(
                                opportunity_type=CodingOpportunityType.HCC_OPPORTUNITY,
                                current_code=None,
                                suggested_code=None,
                                description=f"Potential {hcc} opportunity: '{indicator}' mentioned in text",
                                impact=f"RAF value: {self._hcc_raf_values.get(hcc, 0):.3f}",
                                evidence_text=indicator,
                                priority="high",
                            ))
                            break

        return HCCRiskResult(
            total_raf_score=round(total_raf, 3),
            hcc_codes=hcc_codes,
            hcc_details=hcc_details,
            estimated_annual_revenue=round(estimated_revenue, 2),
            opportunities=opportunities,
        )

    # =========================================================================
    # Rules and Guidelines
    # =========================================================================

    def get_coding_rules(
        self,
        category: str | None = None,
    ) -> list[CodingRule]:
        """Get coding rules and guidelines.

        Args:
            category: Optional category filter

        Returns:
            List of CodingRule objects
        """
        rules = [
            CodingRule(
                rule_id="MDM_VS_TIME",
                category="E/M",
                title="MDM vs Time-Based Coding",
                description="For office visits, code based on either MDM complexity OR total time, whichever supports the higher level.",
                examples=["Use 99214 for 30-39 minutes OR moderate MDM"],
                source="AMA CPT Guidelines",
            ),
            CodingRule(
                rule_id="PRIMARY_DX",
                category="sequencing",
                title="Primary Diagnosis Selection",
                description="Code the diagnosis that is chiefly responsible for the visit as the primary diagnosis.",
                examples=["If patient presents with chest pain, code chest pain first, then underlying conditions"],
                source="ICD-10-CM Official Guidelines",
            ),
            CodingRule(
                rule_id="SPECIFICITY",
                category="specificity",
                title="Code to Highest Specificity",
                description="Always code to the highest level of specificity supported by documentation.",
                examples=["Use E11.65 (DM2 with hyperglycemia) instead of E11.9 (DM2 unspecified) when documented"],
                source="ICD-10-CM Official Guidelines",
            ),
            CodingRule(
                rule_id="BUNDLING_ECG",
                category="bundling",
                title="ECG Bundling",
                description="ECG interpretation is often bundled with E/M services. Use modifier 25 on E/M if separately identifiable.",
                codes_affected=["93000", "93005", "93010"],
                source="CMS NCCI Edits",
            ),
            CodingRule(
                rule_id="HCC_ANNUAL",
                category="HCC",
                title="Annual HCC Recapture",
                description="HCC conditions must be coded annually to maintain RAF scores. Conditions from prior years must be recaptured.",
                examples=["Document and code all chronic conditions at annual wellness visit"],
                source="CMS HCC Model",
            ),
        ]

        if category:
            rules = [r for r in rules if r.category.lower() == category.lower()]

        return rules

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _expand_abbreviations(self, text: str) -> str:
        """Expand medical abbreviations in text."""
        expanded = text
        for abbrev, expansion in ABBREVIATION_MAP.items():
            pattern = r'\b' + re.escape(abbrev) + r'\b'
            expanded = re.sub(pattern, f"{abbrev} {expansion}", expanded, flags=re.IGNORECASE)
        return expanded

    def _find_evidence_for_code(
        self,
        text: str,
        code_data: dict,
    ) -> list[EvidenceSnippet]:
        """Find evidence snippets in text for a code."""
        evidence = []
        text_lower = text.lower()

        # Check description words
        description = code_data.get('description', '').lower()
        desc_words = [w for w in description.split() if len(w) > 3]

        for word in desc_words:
            if word in text_lower:
                pos = text_lower.find(word)
                start = max(0, pos - 50)
                end = min(len(text), pos + len(word) + 50)

                evidence.append(EvidenceSnippet(
                    text=text[start:end],
                    start_offset=start,
                    end_offset=end,
                    relevance_score=0.7,
                    highlight_terms=[word],
                ))
                break

        # Check synonyms
        synonyms = code_data.get('synonyms', [])
        for syn in synonyms:
            if syn.lower() in text_lower:
                pos = text_lower.find(syn.lower())
                start = max(0, pos - 50)
                end = min(len(text), pos + len(syn) + 50)

                evidence.append(EvidenceSnippet(
                    text=text[start:end],
                    start_offset=start,
                    end_offset=end,
                    relevance_score=0.85,
                    highlight_terms=[syn],
                ))
                break

        return evidence

    def _create_diagnosis_suggestion(
        self,
        code_data: dict,
        confidence: ConfidenceLevel,
        score: float,
        evidence: list[EvidenceSnippet],
        match_reason: str,
    ) -> CodeSuggestion:
        """Create a diagnosis code suggestion."""
        code = code_data['code']

        # Check for HCC mapping
        hcc_code = self._icd10_to_hcc.get(code)
        hcc_description = None
        raf_value = 0.0

        if hcc_code:
            raf_value = self._hcc_raf_values.get(hcc_code, 0.0)
            hcc_description = f"Maps to {hcc_code}"

        # Get category from code
        category = self._get_icd10_category(code)

        # Build coding tips
        tips = []
        if 'unspecified' in code_data.get('description', '').lower():
            tips.append("Consider more specific code if documentation supports")
        if hcc_code:
            tips.append(f"HCC condition - ensure annual recapture")

        return CodeSuggestion(
            code=code,
            code_type=CodeType.ICD10,
            description=code_data.get('description', ''),
            confidence=confidence,
            confidence_score=score,
            evidence_snippets=evidence,
            match_reason=match_reason,
            category=category,
            is_billable=code_data.get('is_billable', True),
            hcc_code=hcc_code,
            hcc_description=hcc_description,
            raf_value=raf_value,
            coding_tips=tips,
        )

    def _create_procedure_suggestion(
        self,
        code_data: dict,
        confidence: ConfidenceLevel,
        score: float,
        evidence: list[EvidenceSnippet],
        match_reason: str,
    ) -> CodeSuggestion:
        """Create a procedure code suggestion."""
        return CodeSuggestion(
            code=code_data['code'],
            code_type=CodeType.CPT,
            description=code_data.get('description', ''),
            confidence=confidence,
            confidence_score=score,
            evidence_snippets=evidence,
            match_reason=match_reason,
            category=code_data.get('category', ''),
            is_billable=True,
        )

    def _get_icd10_category(self, code: str) -> str:
        """Get ICD-10 category from code."""
        if not code:
            return "Unknown"

        first_char = code[0].upper()
        categories = {
            'A': "Infectious Diseases",
            'B': "Infectious Diseases",
            'C': "Neoplasms",
            'D': "Neoplasms/Blood Disorders",
            'E': "Endocrine/Metabolic",
            'F': "Mental/Behavioral",
            'G': "Nervous System",
            'H': "Eye/Ear",
            'I': "Circulatory System",
            'J': "Respiratory System",
            'K': "Digestive System",
            'L': "Skin",
            'M': "Musculoskeletal",
            'N': "Genitourinary",
            'O': "Pregnancy",
            'P': "Perinatal",
            'Q': "Congenital",
            'R': "Signs/Symptoms",
            'S': "Injury",
            'T': "Injury/Poisoning",
            'V': "External Causes",
            'W': "External Causes",
            'X': "External Causes",
            'Y': "External Causes",
            'Z': "Factors Influencing Health",
        }
        return categories.get(first_char, "Unknown")

    # =========================================================================
    # Stats and Info
    # =========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        return {
            "total_icd10_codes": len(self._icd10_codes),
            "total_cpt_codes": len(self._cpt_codes),
            "total_icd10_synonyms": len(self._icd10_synonyms),
            "total_cpt_synonyms": len(self._cpt_synonyms),
            "hcc_mappings": len(self._icd10_to_hcc),
        }

    def get_code_details(self, code: str, code_type: CodeType) -> dict | None:
        """Get details for a specific code."""
        if code_type == CodeType.ICD10:
            return self._icd10_codes.get(code)
        elif code_type == CodeType.CPT:
            return self._cpt_codes.get(code)
        return None

    def search_codes(
        self,
        query: str,
        code_type: CodeType,
        limit: int = 20,
    ) -> list[dict]:
        """Search for codes by description or synonym."""
        query_lower = query.lower()
        results = []

        codes = self._icd10_codes if code_type == CodeType.ICD10 else self._cpt_codes

        for code, data in codes.items():
            if query_lower in data.get('description', '').lower():
                results.append(data)
            elif any(query_lower in syn.lower() for syn in data.get('synonyms', [])):
                results.append(data)

        return results[:limit]
