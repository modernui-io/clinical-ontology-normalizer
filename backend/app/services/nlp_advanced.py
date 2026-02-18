"""Advanced NLP Post-Processing Service.

Enhances extracted mentions with context-aware processing:
1. Abbreviation disambiguation - PE, MI, MS, PT, OD based on context
2. Clause-boundary-aware negation - Respects "but", ";", "however" boundaries
3. Compound condition extraction - Links "diabetes with nephropathy"
4. Laterality extraction - Captures left/right/bilateral

Usage:
    from app.services.nlp_advanced import get_advanced_nlp_service

    # Get extracted mentions from ensemble
    mentions = ensemble.extract_mentions(text, doc_id)

    # Enhance with advanced processing
    advanced = get_advanced_nlp_service()
    enhanced = advanced.enhance_mentions(text, mentions)

    # Access enhancements
    for em in enhanced:
        if em.enhancement.laterality:
            print(f"{em.mention.text}: {em.enhancement.laterality.value}")

# MATURITY: experimental — not integrated into any production path
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field
from enum import Enum

from app.schemas.base import Assertion
from app.services.nlp import ExtractedMention

logger = logging.getLogger(__name__)


# ==============================================================================
# Enums and Data Classes
# ==============================================================================


class Laterality(Enum):
    """Laterality designation for anatomical conditions."""

    LEFT = "left"
    RIGHT = "right"
    BILATERAL = "bilateral"
    UNILATERAL = "unilateral"
    UNSPECIFIED = "unspecified"


class AbbreviationContext(Enum):
    """Context types for abbreviation disambiguation."""

    CARDIOLOGY = "cardiology"
    NEUROLOGY = "neurology"
    PULMONOLOGY = "pulmonology"
    OPHTHALMOLOGY = "ophthalmology"
    GENERAL = "general"
    PHARMACY = "pharmacy"
    REHAB = "rehabilitation"


@dataclass
class MentionEnhancement:
    """Enhancement data for an extracted mention."""

    # Abbreviation disambiguation
    disambiguation_context: AbbreviationContext | None = None
    original_abbreviation: str | None = None
    disambiguated_term: str | None = None

    # Negation scope
    negation_scope_start: int | None = None
    negation_scope_end: int | None = None
    negation_trigger: str | None = None
    negation_boundary: str | None = None

    # Compound conditions
    linked_modifier: str | None = None
    compound_condition_text: str | None = None
    base_condition: str | None = None

    # Laterality
    laterality: Laterality | None = None
    laterality_text: str | None = None


@dataclass
class EnhancedMention:
    """A mention with its enhancement data."""

    mention: ExtractedMention
    enhancement: MentionEnhancement


@dataclass
class AdvancedNLPConfig:
    """Configuration for advanced NLP processing."""

    # Enable/disable features
    enable_abbreviation_disambiguation: bool = True
    enable_clause_negation: bool = True
    enable_compound_extraction: bool = True
    enable_laterality_extraction: bool = True

    # Context window sizes (characters)
    abbreviation_context_window: int = 100
    negation_scope_window: int = 50
    laterality_window: int = 30

    # Confidence thresholds
    min_abbreviation_confidence: float = 0.6
    min_compound_confidence: float = 0.7


# ==============================================================================
# Data Structures for Processing
# ==============================================================================


# Ambiguous abbreviations with context indicators
AMBIGUOUS_ABBREVIATIONS: dict[str, dict[str, dict]] = {
    "PE": {
        AbbreviationContext.CARDIOLOGY.value: {
            "expansion": "pulmonary embolism",
            "indicators": [
                "chest", "troponin", "dvt", "anticoagul", "stemi", "nstemi",
                "heparin", "warfarin", "clot", "embol", "venous", "d-dimer",
                "shortness of breath", "dyspnea", "tachycardia", "hypoxia"
            ],
        },
        AbbreviationContext.GENERAL.value: {
            "expansion": "physical exam",
            "indicators": [
                "exam", "vitals", "inspection", "palpation", "auscultation",
                "normal", "unremarkable", "review", "findings", "reveals"
            ],
        },
    },
    "MI": {
        AbbreviationContext.CARDIOLOGY.value: {
            "expansion": "myocardial infarction",
            "indicators": [
                "chest", "troponin", "stemi", "nstemi", "cardiac", "heart",
                "ecg", "ekg", "cath", "pci", "cabg", "infarct", "ischemia"
            ],
        },
    },
    "MS": {
        AbbreviationContext.CARDIOLOGY.value: {
            "expansion": "mitral stenosis",
            "indicators": [
                "valve", "mitral", "murmur", "rheumatic", "stenosis",
                "auscultation", "echo", "cardiac"
            ],
        },
        AbbreviationContext.NEUROLOGY.value: {
            "expansion": "multiple sclerosis",
            "indicators": [
                "brain", "mri", "demyelinat", "lesion", "neuro", "optic",
                "plaques", "relapsing", "remitting", "spinal cord"
            ],
        },
    },
    "PT": {
        AbbreviationContext.CARDIOLOGY.value: {
            "expansion": "prothrombin time",
            "indicators": [
                "inr", "coagul", "warfarin", "anticoag", "clotting",
                "bleeding", "coumadin", "blood thin"
            ],
        },
        AbbreviationContext.REHAB.value: {
            "expansion": "physical therapy",
            "indicators": [
                "therapy", "rehab", "exercise", "mobility", "strength",
                "range of motion", "gait", "ambulation"
            ],
        },
        AbbreviationContext.GENERAL.value: {
            "expansion": "patient",
            "indicators": [],  # Default when no context
        },
    },
    "OD": {
        AbbreviationContext.GENERAL.value: {
            "expansion": "overdose",
            "indicators": [
                "overdos", "toxic", "ingestion", "suicide", "intentional",
                "accidental", "narcan", "naloxone", "poison"
            ],
        },
        AbbreviationContext.PHARMACY.value: {
            "expansion": "once daily",
            "indicators": [
                "daily", "dose", "mg", "tablet", "capsule", "take",
                "medication", "prescribed", "bid", "tid", "qid"
            ],
        },
        AbbreviationContext.OPHTHALMOLOGY.value: {
            "expansion": "right eye (oculus dexter)",
            "indicators": [
                "eye", "ocul", "vision", "ophthalm", "pupil", "os",
                "ou", "retina", "cornea"
            ],
        },
    },
    "SOB": {
        AbbreviationContext.PULMONOLOGY.value: {
            "expansion": "shortness of breath",
            "indicators": [
                "breath", "dyspnea", "oxygen", "respiratory", "lung",
                "pulmonary", "copd", "asthma", "hypoxia"
            ],
        },
    },
    "CAD": {
        AbbreviationContext.CARDIOLOGY.value: {
            "expansion": "coronary artery disease",
            "indicators": [
                "coronary", "artery", "heart", "cardiac", "stent", "cabg",
                "angina", "ischemia", "mi", "infarct"
            ],
        },
    },
    "CHF": {
        AbbreviationContext.CARDIOLOGY.value: {
            "expansion": "congestive heart failure",
            "indicators": [
                "heart", "failure", "edema", "fluid", "diuretic", "ef",
                "ejection", "lasix", "congestion"
            ],
        },
    },
    "HTN": {
        AbbreviationContext.CARDIOLOGY.value: {
            "expansion": "hypertension",
            "indicators": [
                "blood pressure", "bp", "systolic", "diastolic", "mmhg",
                "amlodipine", "lisinopril", "antihypertensive"
            ],
        },
    },
    "DM": {
        AbbreviationContext.GENERAL.value: {
            "expansion": "diabetes mellitus",
            "indicators": [
                "diabetes", "glucose", "sugar", "a1c", "hba1c", "insulin",
                "metformin", "hypoglycemia", "hyperglycemia"
            ],
        },
    },
    "COPD": {
        AbbreviationContext.PULMONOLOGY.value: {
            "expansion": "chronic obstructive pulmonary disease",
            "indicators": [
                "lung", "pulmonary", "breath", "oxygen", "inhaler",
                "bronchodilator", "emphysema", "bronchitis"
            ],
        },
    },
    "CKD": {
        AbbreviationContext.GENERAL.value: {
            "expansion": "chronic kidney disease",
            "indicators": [
                "kidney", "renal", "creatinine", "gfr", "egfr", "dialysis",
                "nephro", "uremia"
            ],
        },
    },
    "GERD": {
        AbbreviationContext.GENERAL.value: {
            "expansion": "gastroesophageal reflux disease",
            "indicators": [
                "reflux", "heartburn", "acid", "ppi", "omeprazole",
                "esophag", "stomach"
            ],
        },
    },
    "BPH": {
        AbbreviationContext.GENERAL.value: {
            "expansion": "benign prostatic hyperplasia",
            "indicators": [
                "prostate", "urinary", "void", "nocturia", "hesitancy",
                "tamsulosin", "flomax"
            ],
        },
    },
}

# Negation triggers and clause boundaries
# Canonical source: app.services.nlp_shared.CANONICAL_NEGATION_TRIGGERS
# Pre-mention negation triggers (appear BEFORE the mention)
NEGATION_TRIGGERS_PRE = [
    "no", "not", "none", "denies", "denied", "without", "negative for",
    "no evidence of", "absence of", "r/o", "free of", "no signs of",
    "no symptoms of", "never", "neither", "no history of", "no h/o"
]

# Post-mention negation triggers (appear AFTER the mention)
NEGATION_TRIGGERS_POST = [
    "ruled out", "has been ruled out", "was ruled out", "is ruled out",
    "excluded", "has been excluded", "was excluded", "is excluded",
    "negative", "was negative", "is negative", "came back negative",
    "not found", "not seen", "not detected", "not identified"
]

# Combined for backwards compatibility
NEGATION_TRIGGERS = NEGATION_TRIGGERS_PRE + NEGATION_TRIGGERS_POST

CLAUSE_BOUNDARIES = [
    "but", "however", "although", "except", "yet", "still", "though",
    ";", ".", ":", "\n"
]

# Compound condition patterns
# Embedded abbreviation patterns (the modifier IS the abbreviation)
EMBEDDED_COMPOUND_ABBREVIATIONS = {
    "hfref": {"base": "heart failure", "modifier": "with reduced EF (HFrEF)"},
    "hfpef": {"base": "heart failure", "modifier": "with preserved EF (HFpEF)"},
    "aecopd": {"base": "COPD", "modifier": "with acute exacerbation"},
    "esrd": {"base": "chronic kidney disease", "modifier": "end-stage (ESRD)"},
    "t2dm": {"base": "diabetes mellitus", "modifier": "type 2"},
    "t1dm": {"base": "diabetes mellitus", "modifier": "type 1"},
    "dm2": {"base": "diabetes mellitus", "modifier": "type 2"},
    "dm1": {"base": "diabetes mellitus", "modifier": "type 1"},
}

COMPOUND_PATTERNS: dict[str, dict] = {
    "heart_failure": {
        "base_patterns": ["heart failure", "hf", "chf", "cardiac failure", "hfref", "hfpef"],
        "modifiers": [
            {"pattern": r"with\s+reduced\s+ef", "text": "with reduced EF (HFrEF)"},
            {"pattern": r"with\s+preserved\s+ef", "text": "with preserved EF (HFpEF)"},
            {"pattern": r"reduced\s+(?:ef|ejection\s+fraction)", "text": "with reduced EF (HFrEF)"},
            {"pattern": r"preserved\s+(?:ef|ejection\s+fraction)", "text": "with preserved EF (HFpEF)"},
            {"pattern": r"systolic\s+(?:dysfunction|failure)", "text": "systolic dysfunction"},
            {"pattern": r"diastolic\s+(?:dysfunction|failure)", "text": "diastolic dysfunction"},
            {"pattern": r"(?:ef|ejection\s+fraction)\s*(?:of\s*)?~?(\d+)\s*%?", "text": "EF {0}%"},
            {"pattern": r"acute(?:\s+on\s+chronic)?\s+decompensated", "text": "acute decompensated"},
            {"pattern": r"decompensated", "text": "decompensated"},
            {"pattern": r"acute\s+(?:on\s+chronic)?", "text": "acute exacerbation"},
        ],
    },
    "diabetes": {
        "base_patterns": ["diabetes", "dm", "diabetes mellitus", "type 2 diabetes", "t2dm", "type 1 diabetes", "t1dm"],
        "modifiers": [
            {"pattern": r"with\s+nephropathy", "text": "with nephropathy"},
            {"pattern": r"with\s+retinopathy", "text": "with retinopathy"},
            {"pattern": r"with\s+neuropathy", "text": "with neuropathy"},
            {"pattern": r"with\s+chronic\s+kidney\s+disease", "text": "with CKD"},
            {"pattern": r"with\s+ckd", "text": "with CKD"},
            {"pattern": r"with\s+peripheral\s+vascular", "text": "with PVD"},
            {"pattern": r"with\s+foot\s+ulcer", "text": "with foot ulcer"},
            {"pattern": r"with\s+gastroparesis", "text": "with gastroparesis"},
            {"pattern": r"poorly\s+controlled", "text": "poorly controlled"},
            {"pattern": r"uncontrolled", "text": "uncontrolled"},
            {"pattern": r"insulin[- ]?dependent", "text": "insulin-dependent"},
        ],
    },
    "copd": {
        "base_patterns": ["copd", "chronic obstructive pulmonary disease"],
        "modifiers": [
            {"pattern": r"with\s+acute\s+exacerbation", "text": "with acute exacerbation"},
            {"pattern": r"acute\s+exacerbation\s+of", "text": "acute exacerbation"},
            {"pattern": r"aecopd", "text": "acute exacerbation"},
            {"pattern": r"gold\s+stage\s+(\d)", "text": "GOLD stage {0}"},
            {"pattern": r"stage\s+(\d)", "text": "stage {0}"},
        ],
    },
    "ckd": {
        "base_patterns": ["ckd", "chronic kidney disease", "chronic renal disease"],
        "modifiers": [
            {"pattern": r"stage\s+([1-5])", "text": "stage {0}"},
            {"pattern": r"stage\s+(i{1,3}v?|iv|v)", "text": "stage {0}"},
            {"pattern": r"end[- ]?stage", "text": "end-stage (ESRD)"},
            {"pattern": r"esrd", "text": "end-stage (ESRD)"},
            {"pattern": r"on\s+dialysis", "text": "on dialysis"},
            {"pattern": r"hemodialysis", "text": "on hemodialysis"},
            {"pattern": r"peritoneal\s+dialysis", "text": "on peritoneal dialysis"},
        ],
    },
    "hypertension": {
        "base_patterns": ["hypertension", "htn", "high blood pressure"],
        "modifiers": [
            {"pattern": r"essential", "text": "essential"},
            {"pattern": r"malignant", "text": "malignant"},
            {"pattern": r"resistant", "text": "resistant"},
            {"pattern": r"uncontrolled", "text": "uncontrolled"},
            {"pattern": r"poorly\s+controlled", "text": "poorly controlled"},
            {"pattern": r"with\s+ckd", "text": "with CKD"},
            {"pattern": r"with\s+heart\s+failure", "text": "with heart failure"},
            {"pattern": r"severe", "text": "severe"},
        ],
    },
}

# Laterality patterns - ORDER MATTERS! Check bilateral/unilateral BEFORE left/right
# to avoid "b/l" matching as "l" (left)
LATERALITY_PATTERNS_ORDERED = [
    (Laterality.BILATERAL, [
        r"\bbilateral(?:ly)?\b", r"\bb/l\b", r"\bbilat\b",
        r"\bboth\s+(?:sides|extremities|eyes|ears|lungs|kidneys)\b"
    ]),
    (Laterality.UNILATERAL, [
        r"\bunilateral(?:ly)?\b"
    ]),
    (Laterality.LEFT, [
        r"\bleft\b", r"\bleft-sided\b", r"\bl\.\s*", r"\blt\b"
    ]),
    (Laterality.RIGHT, [
        r"\bright\b", r"\bright-sided\b", r"\br\.\s*", r"\brt\b"
    ]),
]

# Keep dict for backwards compatibility but it won't be used for ordered matching
LATERALITY_PATTERNS = {lat: patterns for lat, patterns in LATERALITY_PATTERNS_ORDERED}

# Anatomical structures that can have laterality
LATERALIZED_ANATOMY = [
    "knee", "hip", "shoulder", "ankle", "elbow", "wrist", "foot", "hand",
    "arm", "leg", "thigh", "calf", "lung", "eye", "ear", "kidney", "breast",
    "ovary", "testicle", "adrenal", "carotid", "femoral", "radial", "tibial",
    "extremity", "lower extremity", "upper extremity", "side", "lobe",
    "hemothorax", "pneumothorax", "pleural effusion", "edema", "weakness",
    "numbness", "pain", "fracture", "dislocation", "hemiparesis", "hemiplegia"
]


# ==============================================================================
# Advanced NLP Service
# ==============================================================================


class AdvancedNLPService:
    """Service for advanced NLP post-processing of extracted mentions.

    Enhances mentions with:
    - Context-aware abbreviation disambiguation
    - Clause-boundary-aware negation detection
    - Compound condition extraction
    - Laterality extraction
    """

    def __init__(self, config: AdvancedNLPConfig | None = None):
        """Initialize the service.

        Args:
            config: Configuration options. Uses defaults if not provided.
        """
        self.config = config or AdvancedNLPConfig()
        self._lock = threading.Lock()

        # Compile regex patterns for efficiency
        # Pre-mention negation (appears before the mention)
        self._negation_pattern_pre = re.compile(
            r"\b(" + "|".join(re.escape(t) for t in NEGATION_TRIGGERS_PRE) + r")\b",
            re.IGNORECASE
        )
        # Post-mention negation (appears after the mention)
        self._negation_pattern_post = re.compile(
            r"\b(" + "|".join(re.escape(t) for t in NEGATION_TRIGGERS_POST) + r")\b",
            re.IGNORECASE
        )
        self._boundary_pattern = re.compile(
            r"(" + "|".join(re.escape(b) for b in CLAUSE_BOUNDARIES) + r")",
            re.IGNORECASE
        )

        # Compile laterality patterns IN ORDER (bilateral/unilateral before left/right)
        self._laterality_patterns_ordered: list[tuple[Laterality, re.Pattern]] = []
        for lat, patterns in LATERALITY_PATTERNS_ORDERED:
            compiled = re.compile("|".join(patterns), re.IGNORECASE)
            self._laterality_patterns_ordered.append((lat, compiled))

        # Keep dict for backwards compatibility
        self._laterality_patterns: dict[Laterality, re.Pattern] = {}
        for lat, patterns in LATERALITY_PATTERNS.items():
            self._laterality_patterns[lat] = re.compile(
                "|".join(patterns), re.IGNORECASE
            )

        # Compile compound patterns
        self._compound_patterns: dict[str, dict] = {}
        for name, data in COMPOUND_PATTERNS.items():
            base_re = re.compile(
                r"\b(" + "|".join(re.escape(p) for p in data["base_patterns"]) + r")\b",
                re.IGNORECASE
            )
            modifier_res = [
                (re.compile(m["pattern"], re.IGNORECASE), m["text"])
                for m in data["modifiers"]
            ]
            self._compound_patterns[name] = {
                "base": base_re,
                "modifiers": modifier_res,
            }

        logger.info("AdvancedNLPService initialized")

    def _get_context_window(
        self,
        text: str,
        start: int,
        end: int,
        window_size: int,
    ) -> str:
        """Get text context around a span.

        Args:
            text: Full text
            start: Span start offset
            end: Span end offset
            window_size: Characters to include before and after

        Returns:
            Context string (lowercased)
        """
        ctx_start = max(0, start - window_size)
        ctx_end = min(len(text), end + window_size)
        return text[ctx_start:ctx_end].lower()

    def _disambiguate_abbreviation(
        self,
        text: str,
        mention: ExtractedMention,
    ) -> tuple[AbbreviationContext | None, str | None]:
        """Disambiguate an abbreviation based on context.

        Args:
            text: Full document text
            mention: The mention to check

        Returns:
            Tuple of (context_type, expanded_term) or (None, None)
        """
        abbr = mention.text.upper()
        if abbr not in AMBIGUOUS_ABBREVIATIONS:
            return None, None

        contexts = AMBIGUOUS_ABBREVIATIONS[abbr]
        context_window = self._get_context_window(
            text,
            mention.start_offset,
            mention.end_offset,
            self.config.abbreviation_context_window,
        )

        # Score each possible context
        scores: dict[str, int] = {}
        for ctx_name, ctx_data in contexts.items():
            score = 0
            for indicator in ctx_data["indicators"]:
                if indicator.lower() in context_window:
                    score += 1
            scores[ctx_name] = score

        # Find best match
        if not scores:
            return None, None

        best_ctx = max(scores.items(), key=lambda x: x[1])
        if best_ctx[1] == 0:
            # No indicators matched, use first context as default
            first_ctx = list(contexts.keys())[0]
            return (
                AbbreviationContext(first_ctx),
                contexts[first_ctx]["expansion"]
            )

        return (
            AbbreviationContext(best_ctx[0]),
            contexts[best_ctx[0]]["expansion"]
        )

    def _detect_clause_aware_negation(
        self,
        text: str,
        mention: ExtractedMention,
    ) -> tuple[int | None, int | None, str | None, str | None]:
        """Detect negation with clause boundary awareness.

        Checks for both pre-mention negation ("no chest pain") and
        post-mention negation ("PE ruled out").

        Args:
            text: Full document text
            mention: The mention to check

        Returns:
            Tuple of (scope_start, scope_end, trigger, boundary)
        """
        # === Check PRE-MENTION negation ===
        ctx_start = max(0, mention.start_offset - self.config.negation_scope_window)
        context_before = text[ctx_start:mention.start_offset]

        # Find negation triggers before the mention
        negation_match = None
        for match in self._negation_pattern_pre.finditer(context_before):
            negation_match = match

        if negation_match:
            # Calculate absolute positions
            trigger_start = ctx_start + negation_match.start()
            trigger_end = ctx_start + negation_match.end()
            trigger_text = negation_match.group(1)

            # Find clause boundaries between trigger and mention
            between_text = text[trigger_end:mention.start_offset]
            boundary_match = self._boundary_pattern.search(between_text)

            if not boundary_match or boundary_match.start() >= (mention.start_offset - trigger_end):
                # No boundary between trigger and mention, or boundary is after mention
                # Mention is within negation scope
                after_text = text[mention.end_offset:mention.end_offset + self.config.negation_scope_window]
                after_boundary = self._boundary_pattern.search(after_text)

                scope_end = mention.end_offset
                boundary_text = None
                if after_boundary:
                    scope_end = mention.end_offset + after_boundary.start()
                    boundary_text = after_boundary.group(1)

                return trigger_start, scope_end, trigger_text, boundary_text

        # === Check POST-MENTION negation ===
        ctx_end = min(len(text), mention.end_offset + self.config.negation_scope_window)
        context_after = text[mention.end_offset:ctx_end]

        # Find negation triggers after the mention
        post_match = self._negation_pattern_post.search(context_after)

        if post_match:
            # Check for clause boundaries between mention and trigger
            between_text = context_after[:post_match.start()]
            boundary_match = self._boundary_pattern.search(between_text)

            if not boundary_match:
                # No boundary between mention and post-trigger
                trigger_start = mention.end_offset + post_match.start()
                trigger_text = post_match.group(1)

                return mention.start_offset, trigger_start + len(trigger_text), trigger_text, None

        return None, None, None, None

    def _extract_compound_conditions(
        self,
        text: str,
        mention: ExtractedMention,
    ) -> tuple[str | None, str | None, str | None]:
        """Extract compound condition modifiers.

        Checks for modifiers both BEFORE and AFTER the base term:
        - "heart failure with reduced EF" (after)
        - "uncontrolled hypertension" (before)
        - "HFrEF" (embedded in abbreviation)

        Args:
            text: Full document text
            mention: The mention to check

        Returns:
            Tuple of (linked_modifier, compound_text, base_condition)
        """
        mention_text_lower = mention.text.lower()

        # First check embedded abbreviations (HFrEF, AECOPD, etc.)
        for abbr, data in EMBEDDED_COMPOUND_ABBREVIATIONS.items():
            if abbr in mention_text_lower:
                compound_text = f"{data['base']} {data['modifier']}"
                return data["modifier"], compound_text, data["base"]

        # Check each compound pattern
        for condition_name, pattern_data in self._compound_patterns.items():
            base_re = pattern_data["base"]

            # Check if mention matches base pattern
            if not base_re.search(mention_text_lower):
                continue

            # Get extended context BEFORE mention (for "uncontrolled hypertension")
            ctx_start = max(0, mention.start_offset - 30)
            before_text = text[ctx_start:mention.start_offset].lower()

            # Get extended context AFTER mention (for "hypertension with CKD")
            ctx_end = min(len(text), mention.end_offset + 50)
            after_text = text[mention.end_offset:ctx_end].lower()

            # Build full context: before + mention + after
            full_context = before_text + " " + mention_text_lower + " " + after_text

            # Look for modifiers in the full context
            for modifier_re, modifier_template in pattern_data["modifiers"]:
                match = modifier_re.search(full_context)
                if match:
                    # Format the modifier text
                    if "{0}" in modifier_template and match.groups():
                        modifier_text = modifier_template.format(match.group(1))
                    else:
                        modifier_text = modifier_template

                    # Build compound text
                    base_patterns = COMPOUND_PATTERNS[condition_name]["base_patterns"]
                    base_text = base_patterns[0]  # Use canonical form
                    compound_text = f"{base_text} {modifier_text}"

                    return modifier_text, compound_text, base_text

        return None, None, None

    def _extract_laterality(
        self,
        text: str,
        mention: ExtractedMention,
    ) -> tuple[Laterality | None, str | None]:
        """Extract laterality for anatomical mentions.

        Uses ordered pattern matching to check bilateral/unilateral
        BEFORE left/right (prevents "b/l" matching as "l").

        Args:
            text: Full document text
            mention: The mention to check

        Returns:
            Tuple of (laterality, laterality_text)
        """
        # Check if mention is anatomical
        mention_lower = mention.text.lower()
        is_anatomical = any(
            anat in mention_lower for anat in LATERALIZED_ANATOMY
        )

        if not is_anatomical:
            # Also check if it's a condition that commonly has laterality
            anatomical_conditions = ["pain", "fracture", "weakness", "numbness", "edema", "swelling"]
            is_anatomical = any(cond in mention_lower for cond in anatomical_conditions)

        if not is_anatomical:
            return None, None

        # Get context before and including mention
        ctx_start = max(0, mention.start_offset - self.config.laterality_window)
        context = text[ctx_start:mention.end_offset].lower()

        # Check each laterality pattern IN ORDER (bilateral before left/right)
        for laterality, pattern in self._laterality_patterns_ordered:
            match = pattern.search(context)
            if match:
                return laterality, match.group(0).strip()

        return None, None

    def enhance_mention(
        self,
        text: str,
        mention: ExtractedMention,
    ) -> EnhancedMention:
        """Enhance a single mention with all available processing.

        Args:
            text: Full document text
            mention: Mention to enhance

        Returns:
            EnhancedMention with enhancement data
        """
        enhancement = MentionEnhancement()

        # Abbreviation disambiguation
        if self.config.enable_abbreviation_disambiguation:
            ctx, expanded = self._disambiguate_abbreviation(text, mention)
            if ctx:
                enhancement.disambiguation_context = ctx
                enhancement.original_abbreviation = mention.text
                enhancement.disambiguated_term = expanded

        # Clause-aware negation
        if self.config.enable_clause_negation:
            scope_start, scope_end, trigger, boundary = self._detect_clause_aware_negation(
                text, mention
            )
            if trigger:
                enhancement.negation_scope_start = scope_start
                enhancement.negation_scope_end = scope_end
                enhancement.negation_trigger = trigger
                enhancement.negation_boundary = boundary
                # Update assertion if negated
                mention.assertion = Assertion.ABSENT

        # Compound conditions
        if self.config.enable_compound_extraction:
            modifier, compound, base = self._extract_compound_conditions(text, mention)
            if modifier:
                enhancement.linked_modifier = modifier
                enhancement.compound_condition_text = compound
                enhancement.base_condition = base

        # Laterality
        if self.config.enable_laterality_extraction:
            lat, lat_text = self._extract_laterality(text, mention)
            if lat:
                enhancement.laterality = lat
                enhancement.laterality_text = lat_text

        return EnhancedMention(mention=mention, enhancement=enhancement)

    def enhance_mentions(
        self,
        text: str,
        mentions: list[ExtractedMention],
    ) -> list[EnhancedMention]:
        """Enhance multiple mentions.

        Args:
            text: Full document text
            mentions: List of mentions to enhance

        Returns:
            List of EnhancedMention objects
        """
        enhanced = []
        for mention in mentions:
            enhanced.append(self.enhance_mention(text, mention))
        return enhanced

    def process_mentions(
        self,
        text: str,
        mentions: list[ExtractedMention],
    ) -> list[ExtractedMention]:
        """Process mentions and return updated mentions (without enhancement wrapper).

        This is a convenience method that applies enhancements and returns
        the modified ExtractedMention objects directly.

        Args:
            text: Full document text
            mentions: List of mentions to process

        Returns:
            List of modified ExtractedMention objects
        """
        enhanced = self.enhance_mentions(text, mentions)
        return [em.mention for em in enhanced]

    def get_stats(self) -> dict:
        """Get service statistics.

        Returns:
            Dict with service stats
        """
        return {
            "abbreviations_tracked": len(AMBIGUOUS_ABBREVIATIONS),
            "negation_triggers": len(NEGATION_TRIGGERS),
            "clause_boundaries": len(CLAUSE_BOUNDARIES),
            "compound_patterns": len(COMPOUND_PATTERNS),
            "laterality_patterns": sum(len(p) for p in LATERALITY_PATTERNS.values()),
            "lateralized_anatomy": len(LATERALIZED_ANATOMY),
            "features_enabled": {
                "abbreviation_disambiguation": self.config.enable_abbreviation_disambiguation,
                "clause_negation": self.config.enable_clause_negation,
                "compound_extraction": self.config.enable_compound_extraction,
                "laterality_extraction": self.config.enable_laterality_extraction,
            },
        }


# ==============================================================================
# Singleton Management
# ==============================================================================


_advanced_nlp_service: AdvancedNLPService | None = None
_service_lock = threading.Lock()


def get_advanced_nlp_service(
    config: AdvancedNLPConfig | None = None,
) -> AdvancedNLPService:
    """Get the singleton advanced NLP service.

    Args:
        config: Configuration options. Only used on first call.

    Returns:
        AdvancedNLPService instance
    """
    global _advanced_nlp_service
    with _service_lock:
        if _advanced_nlp_service is None:
            _advanced_nlp_service = AdvancedNLPService(config=config)
        return _advanced_nlp_service


def reset_advanced_nlp_service() -> None:
    """Reset the singleton service (mainly for testing)."""
    global _advanced_nlp_service
    with _service_lock:
        _advanced_nlp_service = None
