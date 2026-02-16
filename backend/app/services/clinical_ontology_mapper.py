"""Clinical Ontology Mapper - Complete word-level coverage for clinical notes.

This service provides deterministic, ontology-based mapping for EVERY token
in a clinical note, creating structured representations that can be used
alongside LLM analysis for more reliable outputs.

Key principles:
1. Every word gets classified into an ontology category
2. Relationships between words are explicitly extracted
3. Standard vocabularies (SNOMED, ICD-10, RxNorm, LOINC) are mapped
4. Output is deterministic and reproducible
5. Handles negation, uncertainty, and temporal context

Architecture:
- Word-level classification (no word left behind)
- Phrase-level entity extraction
- Relationship extraction (subject-predicate-object triples)
- Ontology normalization
- Structured output for downstream processing
"""

from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, NamedTuple

logger = logging.getLogger(__name__)


# =============================================================================
# ONTOLOGY CATEGORIES - Every word must fit into one of these
# =============================================================================


class OntologyCategory(str, Enum):
    """Complete ontology categories for clinical text."""

    # Clinical Entities
    DIAGNOSIS = "diagnosis"
    SYMPTOM = "symptom"
    MEDICATION = "medication"
    PROCEDURE = "procedure"
    LAB_TEST = "lab_test"
    LAB_VALUE = "lab_value"
    VITAL_SIGN = "vital_sign"
    VITAL_VALUE = "vital_value"
    IMAGING = "imaging"
    FINDING = "finding"

    # Anatomical
    ANATOMY = "anatomy"
    BODY_SYSTEM = "body_system"
    LATERALITY = "laterality"
    LOCATION_QUALIFIER = "location_qualifier"

    # Modifiers
    SEVERITY = "severity"
    ACUITY = "acuity"
    FREQUENCY = "frequency"
    DURATION = "duration"
    QUALITY = "quality"
    STATUS = "status"

    # Measurements
    NUMERIC_VALUE = "numeric_value"
    UNIT = "unit"
    RANGE = "range"
    RATIO = "ratio"

    # Temporal
    TEMPORAL_MARKER = "temporal"
    DATE = "date"
    TIME = "time"
    AGE = "age"

    # Context
    NEGATION = "negation"
    UNCERTAINTY = "uncertainty"
    ASSERTION = "assertion"
    EXPERIENCER = "experiencer"

    # Clinical Actions
    ACTION = "action"
    ORDER = "order"
    INSTRUCTION = "instruction"

    # Demographics
    DEMOGRAPHIC = "demographic"
    SOCIAL_HISTORY = "social_history"
    FAMILY_HISTORY = "family_history"

    # Document Structure
    SECTION_HEADER = "section_header"
    LIST_MARKER = "list_marker"
    PUNCTUATION = "punctuation"

    # Language
    CONNECTOR = "connector"
    PREPOSITION = "preposition"
    ARTICLE = "article"
    PRONOUN = "pronoun"
    VERB = "verb"
    ADJECTIVE = "adjective"
    ADVERB = "adverb"

    # Special
    ABBREVIATION = "abbreviation"
    ACRONYM = "acronym"
    CODE_STATUS = "code_status"
    ALLERGY = "allergy"

    # Catch-all
    UNKNOWN = "unknown"


class RelationType(str, Enum):
    """Types of relationships between clinical concepts."""

    # Value relationships
    HAS_VALUE = "has_value"
    HAS_UNIT = "has_unit"
    HAS_RANGE = "has_range"
    HAS_BASELINE = "has_baseline"

    # Clinical relationships
    HAS_DOSE = "has_dose"
    HAS_FREQUENCY = "has_frequency"
    HAS_ROUTE = "has_route"
    HAS_DURATION = "has_duration"
    HAS_SEVERITY = "has_severity"
    HAS_QUALITY = "has_quality"
    HAS_LOCATION = "has_location"

    # Diagnostic relationships
    EVIDENCED_BY = "evidenced_by"
    DIAGNOSED_BY = "diagnosed_by"
    INDICATED_BY = "indicated_by"
    MONITORED_BY = "monitored_by"

    # Treatment relationships
    TREATED_WITH = "treated_with"
    CONTRAINDICATED_WITH = "contraindicated_with"
    INTERACTS_WITH = "interacts_with"

    # Temporal relationships
    OCCURRED_AT = "occurred_at"
    STARTED_AT = "started_at"
    ENDED_AT = "ended_at"
    DURATION_OF = "duration_of"

    # Anatomical relationships
    LOCATED_IN = "located_in"
    RADIATES_TO = "radiates_to"
    AFFECTS = "affects"

    # Context relationships
    NEGATED_BY = "negated_by"
    MODIFIED_BY = "modified_by"
    QUALIFIED_BY = "qualified_by"

    # Attribution
    EXPERIENCED_BY = "experienced_by"
    REPORTED_BY = "reported_by"

    # Causation
    CAUSED_BY = "caused_by"
    RESULTS_IN = "results_in"
    RISK_FACTOR_FOR = "risk_factor_for"


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class TokenSpan:
    """A span of text with position information."""
    text: str
    start: int
    end: int
    normalized: str = ""

    def __post_init__(self):
        if not self.normalized:
            self.normalized = self.text.lower().strip()


@dataclass
class ClassifiedToken:
    """A token with its ontology classification."""
    span: TokenSpan
    category: OntologyCategory
    subcategory: str = ""
    confidence: float = 1.0
    vocabulary_code: str = ""
    vocabulary_system: str = ""
    attributes: dict = field(default_factory=dict)


@dataclass
class Relationship:
    """A relationship between two tokens/entities."""
    subject: ClassifiedToken
    relation: RelationType
    object: ClassifiedToken
    confidence: float = 1.0
    context: str = ""


@dataclass
class ClinicalFrame:
    """A clinical frame capturing a complete clinical statement."""
    frame_type: str  # e.g., "medication_order", "lab_result", "diagnosis"
    tokens: list[ClassifiedToken]
    relationships: list[Relationship]
    section: str = ""
    assertion: str = "present"  # present, absent, possible, conditional
    temporality: str = "current"  # current, historical, future
    experiencer: str = "patient"  # patient, family, other


@dataclass
class OntologyMappingResult:
    """Complete result of ontology mapping for a clinical note."""
    # Word-level coverage
    tokens: list[ClassifiedToken]
    coverage_stats: dict[str, Any]

    # Entity-level
    entities: list[ClassifiedToken]

    # Relationships
    relationships: list[Relationship]

    # Frames (higher-level structures)
    frames: list[ClinicalFrame]

    # Vocabulary mappings
    vocabulary_codes: dict[str, list[str]]

    # Metadata
    processing_time_ms: float = 0.0
    note_length: int = 0


# =============================================================================
# CLINICAL LEXICON - Comprehensive word mappings
# =============================================================================


class ClinicalLexicon:
    """Comprehensive clinical lexicon for word classification."""

    # Physical exam findings
    EXAM_FINDINGS = {
        # Cardiac
        "murmur": ("finding", "cardiac", "SNOMED:88610006"),
        "murmurs": ("finding", "cardiac", "SNOMED:88610006"),
        "irregular": ("finding", "rhythm", "SNOMED:61086009"),
        "regular": ("finding", "rhythm", "SNOMED:271636001"),
        "jvd": ("finding", "cardiac", "SNOMED:271653008"),
        "s3": ("finding", "cardiac", "SNOMED:277454000"),
        "s4": ("finding", "cardiac", "SNOMED:277455004"),
        "gallop": ("finding", "cardiac", "SNOMED:12929001"),
        "bruit": ("finding", "vascular", "SNOMED:63372003"),

        # Respiratory
        "crackles": ("finding", "respiratory", "SNOMED:48409008"),
        "rales": ("finding", "respiratory", "SNOMED:48409008"),
        "rhonchi": ("finding", "respiratory", "SNOMED:24612001"),
        "wheezes": ("finding", "respiratory", "SNOMED:56018004"),
        "wheezing": ("finding", "respiratory", "SNOMED:56018004"),
        "stridor": ("finding", "respiratory", "SNOMED:70407001"),
        "diminished": ("finding", "respiratory", "SNOMED:48348007"),

        # Abdominal
        "tenderness": ("finding", "abdominal", "SNOMED:247348008"),
        "tender": ("finding", "abdominal", "SNOMED:247348008"),
        "non-tender": ("finding", "abdominal", "SNOMED:300824004"),
        "guarding": ("finding", "abdominal", "SNOMED:249545003"),
        "rebound": ("finding", "abdominal", "SNOMED:35611005"),
        "distended": ("finding", "abdominal", "SNOMED:60728008"),
        "distension": ("finding", "abdominal", "SNOMED:41931001"),
        "organomegaly": ("finding", "abdominal", "SNOMED:93651007"),
        "hepatomegaly": ("finding", "abdominal", "SNOMED:80515008"),
        "splenomegaly": ("finding", "abdominal", "SNOMED:16294009"),

        # Neurological
        "oriented": ("finding", "neurological", "SNOMED:247651000"),
        "alert": ("finding", "neurological", "SNOMED:248234008"),
        "lethargic": ("finding", "neurological", "SNOMED:214264003"),
        "obtunded": ("finding", "neurological", "SNOMED:40917007"),
        "comatose": ("finding", "neurological", "SNOMED:371632003"),
        "focal": ("finding", "neurological", "SNOMED:255287005"),
        "deficits": ("finding", "neurological", "SNOMED:260379002"),
        "weakness": ("finding", "neurological", "SNOMED:13791008"),
        "numbness": ("finding", "neurological", "SNOMED:44077006"),
        "tingling": ("finding", "neurological", "SNOMED:62507009"),

        # Skin/General
        "diaphoretic": ("finding", "skin", "SNOMED:415690000"),
        "diaphoresis": ("finding", "skin", "SNOMED:161857006"),
        "pale": ("finding", "skin", "SNOMED:398979000"),
        "cyanotic": ("finding", "skin", "SNOMED:3415004"),
        "jaundiced": ("finding", "skin", "SNOMED:18165001"),
        "edema": ("finding", "skin", "SNOMED:267038008"),
        "swelling": ("finding", "skin", "SNOMED:442672001"),
        "rash": ("finding", "skin", "SNOMED:271807003"),
        "moist": ("finding", "skin", "SNOMED:255245000"),
        "dry": ("finding", "skin", "SNOMED:13880007"),

        # Eyes
        "perrla": ("finding", "ophthalmologic", "exam_abbrev"),
        "eomi": ("finding", "ophthalmologic", "exam_abbrev"),
        "anisocoria": ("finding", "ophthalmologic", "SNOMED:13045006"),
        "nystagmus": ("finding", "ophthalmologic", "SNOMED:563001"),

        # General
        "anxious": ("finding", "general", "SNOMED:48694002"),
        "distress": ("finding", "general", "SNOMED:69328002"),
        "comfortable": ("finding", "general", "SNOMED:103306004"),
        "ill-appearing": ("finding", "general", "SNOMED:39104002"),
        "well-appearing": ("finding", "general", "SNOMED:102499006"),
    }

    # Clinical abbreviations
    ABBREVIATIONS = {
        # Exam
        "perrla": "Pupils Equal Round Reactive to Light and Accommodation",
        "eomi": "Extraocular Movements Intact",
        "rrr": "Regular Rate and Rhythm",
        "ctab": "Clear To Auscultation Bilaterally",
        "nt/nd": "Non-Tender/Non-Distended",
        "a&o": "Alert and Oriented",
        "nad": "No Acute Distress",
        "wnl": "Within Normal Limits",

        # Diagnoses
        "mi": "Myocardial Infarction",
        "cva": "Cerebrovascular Accident",
        "tia": "Transient Ischemic Attack",
        "dvt": "Deep Vein Thrombosis",
        "pe": "Pulmonary Embolism",
        "copd": "Chronic Obstructive Pulmonary Disease",
        "chf": "Congestive Heart Failure",
        "hf": "Heart Failure",
        "ckd": "Chronic Kidney Disease",
        "aki": "Acute Kidney Injury",
        "arf": "Acute Renal Failure",
        "dm": "Diabetes Mellitus",
        "htn": "Hypertension",
        "afib": "Atrial Fibrillation",
        "aflutter": "Atrial Flutter",
        "nstemi": "Non-ST Elevation Myocardial Infarction",
        "stemi": "ST Elevation Myocardial Infarction",
        "acs": "Acute Coronary Syndrome",
        "cad": "Coronary Artery Disease",
        "gerd": "Gastroesophageal Reflux Disease",
        "uti": "Urinary Tract Infection",
        "cap": "Community-Acquired Pneumonia",
        "hap": "Hospital-Acquired Pneumonia",
        "ards": "Acute Respiratory Distress Syndrome",
        "sirs": "Systemic Inflammatory Response Syndrome",
        "dic": "Disseminated Intravascular Coagulation",
        "rvr": "Rapid Ventricular Response",

        # Procedures/Tests
        "ecg": "Electrocardiogram",
        "ekg": "Electrocardiogram",
        "cxr": "Chest X-Ray",
        "ct": "Computed Tomography",
        "mri": "Magnetic Resonance Imaging",
        "us": "Ultrasound",
        "echo": "Echocardiogram",
        "tte": "Transthoracic Echocardiogram",
        "tee": "Transesophageal Echocardiogram",
        "cath": "Catheterization",
        "pci": "Percutaneous Coronary Intervention",
        "cabg": "Coronary Artery Bypass Grafting",
        "ercp": "Endoscopic Retrograde Cholangiopancreatography",
        "egd": "Esophagogastroduodenoscopy",

        # Labs
        "cbc": "Complete Blood Count",
        "bmp": "Basic Metabolic Panel",
        "cmp": "Comprehensive Metabolic Panel",
        "lfts": "Liver Function Tests",
        "ua": "Urinalysis",
        "abg": "Arterial Blood Gas",
        "vbg": "Venous Blood Gas",
        "pt": "Prothrombin Time",
        "ptt": "Partial Thromboplastin Time",
        "inr": "International Normalized Ratio",
        "bnp": "B-type Natriuretic Peptide",
        "wbc": "White Blood Cell Count",
        "rbc": "Red Blood Cell Count",
        "hgb": "Hemoglobin",
        "hct": "Hematocrit",
        "plt": "Platelets",
        "cr": "Creatinine",
        "bun": "Blood Urea Nitrogen",
        "gfr": "Glomerular Filtration Rate",
        "egfr": "Estimated GFR",

        # Vitals
        "hr": "Heart Rate",
        "bp": "Blood Pressure",
        "rr": "Respiratory Rate",
        "spo2": "Oxygen Saturation",
        "o2sat": "Oxygen Saturation",
        "t": "Temperature",
        "temp": "Temperature",

        # Routes/Frequency
        "po": "Per Os (by mouth)",
        "iv": "Intravenous",
        "im": "Intramuscular",
        "sq": "Subcutaneous",
        "sc": "Subcutaneous",
        "pr": "Per Rectum",
        "sl": "Sublingual",
        "bid": "Twice Daily",
        "tid": "Three Times Daily",
        "qid": "Four Times Daily",
        "qd": "Once Daily",
        "qhs": "At Bedtime",
        "prn": "As Needed",
        "ac": "Before Meals",
        "pc": "After Meals",

        # Status
        "nkda": "No Known Drug Allergies",
        "nka": "No Known Allergies",
        "dnr": "Do Not Resuscitate",
        "dni": "Do Not Intubate",
        "ccu": "Coronary Care Unit",
        "icu": "Intensive Care Unit",
        "micu": "Medical Intensive Care Unit",
        "sicu": "Surgical Intensive Care Unit",
        "or": "Operating Room",
        "er": "Emergency Room",
        "ed": "Emergency Department",

        # Other
        "sob": "Shortness of Breath",
        "cp": "Chest Pain",
        "loc": "Loss of Consciousness",
        "ha": "Headache",
        "n/v": "Nausea/Vomiting",
        "d/c": "Discharge/Discontinue",
        "f/u": "Follow Up",
        "h/o": "History Of",
        "r/o": "Rule Out",
        "w/u": "Work Up",
        "i/o": "Intake/Output",
    }

    # Clinical modifiers
    SEVERITY_TERMS = {
        "mild": 1,
        "slight": 1,
        "minimal": 1,
        "moderate": 2,
        "significant": 2,
        "severe": 3,
        "marked": 3,
        "extreme": 3,
        "critical": 3,
        "life-threatening": 3,
    }

    ACUITY_TERMS = {
        "acute": "acute",
        "subacute": "subacute",
        "chronic": "chronic",
        "recurrent": "recurrent",
        "intermittent": "intermittent",
        "persistent": "persistent",
        "progressive": "progressive",
        "stable": "stable",
        "unstable": "unstable",
        "resolving": "resolving",
        "worsening": "worsening",
        "improving": "improving",
    }

    STATUS_TERMS = {
        "elevated": "increased",
        "increased": "increased",
        "high": "increased",
        "raised": "increased",
        "decreased": "decreased",
        "low": "decreased",
        "reduced": "decreased",
        "diminished": "decreased",
        "normal": "normal",
        "abnormal": "abnormal",
        "positive": "positive",
        "negative": "negative",
        "present": "present",
        "absent": "absent",
        "baseline": "baseline",
    }

    NEGATION_TERMS = {
        "no", "not", "none", "negative", "denies", "denied",
        "without", "absent", "never", "neither", "nor",
        "ruled out", "rules out", "unlikely", "no evidence",
    }

    UNCERTAINTY_TERMS = {
        "possible", "possibly", "probable", "probably",
        "likely", "unlikely", "suspected", "suspect",
        "concerning for", "consistent with", "suggestive of",
        "cannot rule out", "differential includes",
        "consider", "may", "might", "could",
    }

    # Clinical actions
    ACTION_TERMS = {
        "hold": "hold",
        "continue": "continue",
        "discontinue": "discontinue",
        "d/c": "discontinue",
        "start": "start",
        "initiate": "start",
        "begin": "start",
        "stop": "stop",
        "restart": "restart",
        "increase": "increase",
        "decrease": "decrease",
        "titrate": "titrate",
        "wean": "wean",
        "taper": "taper",
        "monitor": "monitor",
        "check": "check",
        "recheck": "recheck",
        "order": "order",
        "consult": "consult",
        "admit": "admit",
        "discharge": "discharge",
        "transfer": "transfer",
        "bridge": "bridge",
        "add": "add",
    }

    # Units of measurement
    UNITS = {
        # Mass
        "mg": ("mass", "milligram"),
        "g": ("mass", "gram"),
        "kg": ("mass", "kilogram"),
        "mcg": ("mass", "microgram"),
        "ug": ("mass", "microgram"),
        "ng": ("mass", "nanogram"),
        "pg": ("mass", "picogram"),

        # Volume
        "ml": ("volume", "milliliter"),
        "l": ("volume", "liter"),
        "dl": ("volume", "deciliter"),
        "ul": ("volume", "microliter"),
        "cc": ("volume", "cubic centimeter"),

        # Concentration
        "mg/dl": ("concentration", "milligrams per deciliter"),
        "g/dl": ("concentration", "grams per deciliter"),
        "meq/l": ("concentration", "milliequivalents per liter"),
        "mmol/l": ("concentration", "millimoles per liter"),
        "ng/ml": ("concentration", "nanograms per milliliter"),
        "pg/ml": ("concentration", "picograms per milliliter"),
        "k/ul": ("concentration", "thousands per microliter"),
        "u/l": ("concentration", "units per liter"),
        "iu/l": ("concentration", "international units per liter"),

        # Rates
        "bpm": ("rate", "beats per minute"),
        "breaths/min": ("rate", "breaths per minute"),
        "mmhg": ("pressure", "millimeters of mercury"),

        # Percentages
        "%": ("percentage", "percent"),
        "percent": ("percentage", "percent"),

        # Time
        "seconds": ("time", "seconds"),
        "sec": ("time", "seconds"),
        "minutes": ("time", "minutes"),
        "min": ("time", "minutes"),
        "hours": ("time", "hours"),
        "hr": ("time", "hours"),
        "days": ("time", "days"),
        "weeks": ("time", "weeks"),
        "months": ("time", "months"),
        "years": ("time", "years"),

        # Temperature
        "°f": ("temperature", "fahrenheit"),
        "°c": ("temperature", "celsius"),
        "f": ("temperature", "fahrenheit"),
        "c": ("temperature", "celsius"),
    }

    # Body systems and anatomy
    BODY_SYSTEMS = {
        "cardiovascular": "SNOMED:113257007",
        "cardiac": "SNOMED:113257007",
        "respiratory": "SNOMED:20139000",
        "pulmonary": "SNOMED:20139000",
        "gastrointestinal": "SNOMED:86762007",
        "gi": "SNOMED:86762007",
        "abdominal": "SNOMED:113345001",
        "neurological": "SNOMED:21483005",
        "neuro": "SNOMED:21483005",
        "musculoskeletal": "SNOMED:26107004",
        "genitourinary": "SNOMED:21514008",
        "gu": "SNOMED:21514008",
        "renal": "SNOMED:64033007",
        "endocrine": "SNOMED:113331007",
        "hematologic": "SNOMED:113257007",
        "integumentary": "SNOMED:48075008",
        "dermatologic": "SNOMED:48075008",
        "psychiatric": "SNOMED:74732009",
        "ophthalmologic": "SNOMED:81745001",
        "heent": "SNOMED:774007",
        "vascular": "SNOMED:59820001",
        "general": "SNOMED:general",
    }

    # Anatomical locations
    ANATOMY_TERMS = {
        # Body parts
        "chest": "SNOMED:51185008",
        "arm": "SNOMED:40983000",
        "leg": "SNOMED:61685007",
        "abdomen": "SNOMED:818983003",
        "head": "SNOMED:69536005",
        "neck": "SNOMED:45048000",
        "back": "SNOMED:77568009",
        "extremity": "SNOMED:66019005",
        "extremities": "SNOMED:66019005",
        # Qualifiers
        "substernal": "SNOMED:substernal",
        "bibasilar": "SNOMED:bibasilar",
        "epigastric": "SNOMED:epigastric",
        "periumbilical": "SNOMED:periumbilical",
        "suprapubic": "SNOMED:suprapubic",
        "flank": "SNOMED:58602004",
        "groin": "SNOMED:26893007",
        "axilla": "SNOMED:422543003",
        "axillary": "SNOMED:422543003",
        # Organ-related
        "mucous": "SNOMED:mucous",
        "membranes": "SNOMED:membranes",
    }

    # Symptoms and complaints
    SYMPTOM_TERMS = {
        "pain": "SNOMED:22253000",
        "nausea": "SNOMED:422587007",
        "vomiting": "SNOMED:422400008",
        "diarrhea": "SNOMED:62315008",
        "constipation": "SNOMED:14760008",
        "fatigue": "SNOMED:84229001",
        "weakness": "SNOMED:13791008",
        "dizziness": "SNOMED:404640003",
        "headache": "SNOMED:25064002",
        "fever": "SNOMED:386661006",
        "fevers": "SNOMED:386661006",  # plural
        "chills": "SNOMED:43724002",
        "cough": "SNOMED:49727002",
        "dyspnea": "SNOMED:267036007",
        "shortness": "SNOMED:267036007",
        "breath": "SNOMED:breath",
        "palpitations": "SNOMED:80313002",
        "syncope": "SNOMED:271594007",
        "confusion": "SNOMED:40917007",
        "anxiety": "SNOMED:48694002",
        "depression": "SNOMED:35489007",
        "insomnia": "SNOMED:193462001",
        # Additional symptoms
        "drainage": "SNOMED:307488001",
        "odor": "SNOMED:406534008",
        "swelling": "SNOMED:65124004",
        "erythema": "SNOMED:247441003",
        "warmth": "SNOMED:102598003",
        "tenderness": "SNOMED:247348008",
        "edema": "SNOMED:267038008",
        "redness": "SNOMED:247441003",
        "discharge": "SNOMED:307488001",
        "purulent": "SNOMED:409774005",
    }

    # Temporal markers
    TEMPORAL_TERMS = {
        "ago": "temporal",
        "prior": "temporal",
        "previous": "temporal",
        "last": "temporal",
        "recent": "temporal",
        "current": "temporal",
        "today": "temporal",
        "yesterday": "temporal",
        "morning": "temporal",
        "evening": "temporal",
        "night": "temporal",
        "approximately": "temporal",
        "about": "temporal",
        "starting": "temporal",
        "onset": "temporal",
        "since": "temporal",
        "until": "temporal",
        "duration": "temporal",
    }

    # Clinical verbs and actions (extended)
    CLINICAL_VERBS = {
        "presents": "clinical_verb",
        "reports": "clinical_verb",
        "denies": "clinical_verb",
        "admits": "clinical_verb",
        "describes": "clinical_verb",
        "notes": "clinical_verb",
        "complains": "clinical_verb",
        "states": "clinical_verb",
        "diagnosed": "clinical_verb",
        "treated": "clinical_verb",
        "admitted": "clinical_verb",
        "discharged": "clinical_verb",
        "referred": "clinical_verb",
        "died": "clinical_verb",
        "quit": "clinical_verb",
        "radiating": "clinical_verb",
        "associated": "clinical_verb",
        "described": "clinical_verb",
    }

    # Connectors and function words
    CONNECTORS = {
        "the", "a", "an", "is", "are", "was", "were", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "must", "shall",
        "and", "or", "but", "if", "then", "because", "although",
        "while", "when", "where", "which", "who", "whom", "whose",
        "that", "this", "these", "those", "also", "any", "as",
    }

    PREPOSITIONS = {
        "in", "on", "at", "to", "for", "with", "by", "from", "of",
        "about", "through", "during", "before", "after", "above",
        "below", "between", "into", "onto", "upon", "within",
        "without", "against", "among", "per", "via", "given",
    }

    PRONOUNS = {
        "he", "she", "it", "they", "him", "her", "them",
        "his", "hers", "its", "their", "theirs",
        "i", "me", "my", "mine", "we", "us", "our", "ours",
        "you", "your", "yours",
    }

    # Medical adjectives
    MEDICAL_ADJECTIVES = {
        "occasional": "frequency",
        "frequent": "frequency",
        "rare": "frequency",
        "intermittent": "frequency",
        "daily": "frequency",
        "strict": "modifier",
        "full": "modifier",
        "similar": "modifier",
        "significant": "modifier",
        "former": "modifier",
        "retired": "modifier",
        "illicit": "modifier",
        "planned": "modifier",
        "loading": "modifier",
        "sliding": "modifier",
        "cautiously": "modifier",
    }

    # Procedures and imaging
    PROCEDURE_TERMS = {
        "catheterization": "SNOMED:procedure",
        "drip": "SNOMED:procedure",
        "weights": "SNOMED:procedure",
        "restriction": "SNOMED:procedure",
        "scale": "SNOMED:procedure",
        "consult": "SNOMED:procedure",
        "x-ray": "SNOMED:procedure",
        "function": "SNOMED:procedure",
        "elevation": "SNOMED:finding",
        "depression": "SNOMED:finding",
        "response": "SNOMED:finding",
        "control": "SNOMED:procedure",
        "rate": "SNOMED:procedure",
    }

    # Code status and disposition
    CODE_STATUS_TERMS = {
        "code": "code_status",
        "status": "code_status",
        "full": "code_status",
        "dnr": "code_status",
        "dni": "code_status",
        "comfort": "code_status",
        "hospice": "code_status",
    }

    # Social/occupational terms
    SOCIAL_TERMS = {
        "smoker": "social_history",
        "smoking": "social_history",
        "alcohol": "social_history",
        "drug": "social_history",
        "use": "social_history",
        "worker": "social_history",
        "construction": "social_history",
        "pack-year": "social_history",
        "pack": "social_history",
        "year": "social_history",
        "history": "social_history",
    }

    # Additional clinical terms for complete coverage
    ADDITIONAL_CLINICAL_TERMS = {
        # Specialties/departments
        "cardiology": ("procedure", "specialty"),
        "neurology": ("procedure", "specialty"),
        "pulmonology": ("procedure", "specialty"),
        "nephrology": ("procedure", "specialty"),
        "oncology": ("procedure", "specialty"),
        "radiology": ("procedure", "specialty"),
        "surgery": ("procedure", "specialty"),

        # ECG/Imaging terms
        "leads": ("finding", "ecg"),
        "st": ("finding", "ecg"),
        "v4": ("finding", "ecg"),
        "v5": ("finding", "ecg"),
        "v6": ("finding", "ecg"),
        "ray": ("procedure", "imaging"),
        "x-ray": ("procedure", "imaging"),

        # Lab indicators
        "h": ("status", "high"),
        "l": ("status", "low"),
        "k": ("unit", "thousand"),

        # Oxygen/breathing
        "ra": ("finding", "room_air"),
        "spo": ("vital_sign", "oxygen"),
        "spo2": ("vital_sign", "oxygen"),
        "o2": ("vital_sign", "oxygen"),
        "o": ("anatomy", "oxygen"),

        # Actions
        "initiated": ("action", "start"),
        "planned": ("action", "plan"),
        "present": ("finding", "present"),

        # Units
        "meq": ("unit", "milliequivalent"),

        # Numeric modifiers
        "x": ("connector", "times"),
        "x3": ("numeric_value", "times_three"),

        # Other
        "v": ("finding", "ecg_lead"),
        "age": ("demographic", "age"),
        "like": ("adjective", "quality"),
    }


# =============================================================================
# CLINICAL ONTOLOGY MAPPER SERVICE
# =============================================================================


class ClinicalOntologyMapper:
    """Maps every word in a clinical note to an ontology category.

    This service provides complete coverage of clinical text, ensuring
    that every token is classified and relationships are extracted.
    """

    def __init__(self):
        """Initialize the mapper with lexicons and patterns."""
        self.lexicon = ClinicalLexicon()
        self._load_vocabulary_files()
        self._compile_patterns()

    def _load_vocabulary_files(self) -> None:
        """Load vocabulary files for enhanced coverage."""
        fixtures_dir = Path(__file__).parent.parent.parent / "fixtures"

        # Load medication names from RxNorm
        self._medications: set[str] = set()
        rxnorm_file = fixtures_dir / "rxnorm_drugs.json"
        if rxnorm_file.exists():
            try:
                with open(rxnorm_file) as f:
                    data = json.load(f)
                    for concept in data.get("concepts", []):
                        name = concept.get("concept_name", "").lower()
                        if name and len(name) > 2:
                            self._medications.add(name)
                            # Add first word for brand names
                            first_word = name.split()[0] if ' ' in name else name
                            if len(first_word) > 3:
                                self._medications.add(first_word)
                logger.info(f"Loaded {len(self._medications)} medication terms from RxNorm")
            except Exception as e:
                logger.warning(f"Failed to load RxNorm: {e}")

        # Load diagnosis terms from ICD-10
        self._diagnoses: set[str] = set()
        icd_file = fixtures_dir / "icd10_codes_full.json"
        if icd_file.exists():
            try:
                with open(icd_file) as f:
                    data = json.load(f)
                    # Handle both list and dict structures
                    concepts = data.get("concepts", []) if isinstance(data, dict) else data
                    for concept in concepts:
                        if isinstance(concept, dict):
                            desc = concept.get("concept_name", concept.get("description", "")).lower()
                        else:
                            continue
                        if desc:
                            # Add key terms from description
                            words = desc.split()
                            for word in words:
                                word = word.strip(",.;:()")
                                if len(word) > 3 and word not in self.lexicon.CONNECTORS:
                                    self._diagnoses.add(word)
                logger.info(f"Loaded {len(self._diagnoses)} diagnosis terms from ICD-10")
            except Exception as e:
                logger.warning(f"Failed to load ICD-10: {e}")

        # Load lab test names from LOINC
        self._lab_tests: set[str] = set()
        loinc_file = fixtures_dir / "loinc_measurements.json"
        if loinc_file.exists():
            try:
                with open(loinc_file) as f:
                    data = json.load(f)
                    concepts = data.get("concepts", []) if isinstance(data, dict) else data
                    for concept in concepts:
                        if isinstance(concept, dict):
                            name = concept.get("component", concept.get("concept_name", "")).lower()
                            if name:
                                self._lab_tests.add(name)
                                # Add individual words for multi-word tests
                                for word in name.split():
                                    word = word.strip(",.;:()")
                                    if len(word) > 2:
                                        self._lab_tests.add(word)
                logger.info(f"Loaded {len(self._lab_tests)} lab test terms from LOINC")
            except Exception as e:
                logger.warning(f"Failed to load LOINC: {e}")

        # Add common clinical terms that might be missing from vocabularies
        self._add_common_clinical_terms()

        logger.info(f"Total loaded: {len(self._medications)} medications, "
                    f"{len(self._diagnoses)} diagnosis terms, "
                    f"{len(self._lab_tests)} lab tests")

    def _add_common_clinical_terms(self) -> None:
        """Add common clinical terms that may be missing from vocabulary files."""
        # Common medication names
        common_meds = {
            "aspirin", "metformin", "lisinopril", "atorvastatin", "omeprazole",
            "warfarin", "heparin", "clopidogrel", "furosemide", "diltiazem",
            "insulin", "metoprolol", "amlodipine", "losartan", "gabapentin",
            "prednisone", "albuterol", "levothyroxine", "pantoprazole",
            "acetaminophen", "ibuprofen", "naproxen", "morphine", "hydrocodone",
            "oxycodone", "fentanyl", "lorazepam", "diazepam", "alprazolam",
            "sertraline", "fluoxetine", "escitalopram", "amitriptyline",
            "amoxicillin", "azithromycin", "ciprofloxacin", "vancomycin",
            "ceftriaxone", "piperacillin", "tazobactam", "meropenem",
        }
        self._medications.update(common_meds)

        # Common diagnosis/clinical terms
        common_diagnoses = {
            "hypertension", "diabetes", "mellitus", "fibrillation", "atrial",
            "failure", "heart", "kidney", "disease", "chronic", "acute",
            "injury", "infarction", "myocardial", "stroke", "pneumonia",
            "sepsis", "infection", "cancer", "carcinoma", "tumor", "mass",
            "anemia", "bleeding", "hemorrhage", "embolism", "thrombosis",
            "arrhythmia", "tachycardia", "bradycardia", "hypotension",
            "hyperglycemia", "hypoglycemia", "acidosis", "alkalosis",
            "respiratory", "pulmonary", "congestion", "cardiomegaly",
            "hepatitis", "cirrhosis", "pancreatitis", "cholecystitis",
            "appendicitis", "diverticulitis", "colitis", "gastritis",
            "nephritis", "pyelonephritis", "cystitis", "encephalopathy",
            "neuropathy", "myopathy", "arthritis", "osteoporosis",
            # Ketoacidosis and metabolic
            "ketoacidosis", "dka", "ketosis", "ketonuria", "metabolic",
            # Wound/ulcer terms
            "ulcer", "ulcers", "wound", "wounds", "abscess", "cellulitis",
            "gangrene", "necrosis", "osteomyelitis", "decubitus", "erosion",
            "plantar", "diabetic", "venous", "arterial", "pressure",
            # Foot-specific conditions
            "foot", "ankle", "toe", "heel", "metatarsal",
            # Other common terms
            "peripheral", "vascular", "ischemia", "ischemic",
        }
        self._diagnoses.update(common_diagnoses)

        # Common lab test terms
        common_labs = {
            "hemoglobin", "hematocrit", "platelets", "creatinine", "glucose",
            "sodium", "potassium", "chloride", "bicarbonate", "calcium",
            "magnesium", "phosphorus", "albumin", "bilirubin", "troponin",
            "lactate", "ammonia", "lipase", "amylase", "procalcitonin",
        }
        self._lab_tests.update(common_labs)

    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficient matching."""
        # Numeric patterns
        self._numeric_pattern = re.compile(
            r'^-?\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)?$'
        )

        # Age pattern
        self._age_pattern = re.compile(
            r'^(\d+)[-\s]?(?:year[-\s]?old|yo|y/?o)$', re.IGNORECASE
        )

        # Date patterns
        self._date_pattern = re.compile(
            r'^\d{1,2}[/-]\d{1,2}[/-](?:\d{2}|\d{4})$'
        )

        # Time pattern
        self._time_pattern = re.compile(
            r'^\d{1,2}:\d{2}(?::\d{2})?(?:\s*(?:am|pm))?$', re.IGNORECASE
        )

        # Ratio/range patterns
        self._ratio_pattern = re.compile(
            r'^(\d+(?:\.\d+)?)\s*[-:to/]\s*(\d+(?:\.\d+)?)$'
        )

        # Section header patterns
        self._section_pattern = re.compile(
            r'^(?:HISTORY|ASSESSMENT|PLAN|MEDICATIONS?|ALLERGIES|'
            r'PHYSICAL|EXAMINATION|LABORATORY|RESULTS|VITALS?|'
            r'SOCIAL|FAMILY|PAST|MEDICAL|SURGICAL|REVIEW|SYSTEMS?|'
            r'CHIEF|COMPLAINT|HPI|PMH|PSH|FH|SH|ROS|PE|A/?P|IMPRESSION|'
            r'CC|LABS?|IMAGING|RADIOLOGY|DISCHARGE|SUMMARY|SUBJECTIVE|'
            r'OBJECTIVE|ADDENDUM|NOTE|FINDINGS)(?:\s+(?:OF|AND)\s+\w+)*:?$',
            re.IGNORECASE
        )

    def map_note(self, text: str) -> OntologyMappingResult:
        """Map every word in a clinical note to ontology categories.

        Args:
            text: The clinical note text

        Returns:
            Complete ontology mapping result
        """
        import time
        start_time = time.perf_counter()

        # Tokenize
        tokens = self._tokenize(text)

        # Classify each token
        classified_tokens = []
        for token in tokens:
            classified = self._classify_token(token, text, classified_tokens)
            classified_tokens.append(classified)

        # Extract relationships
        relationships = self._extract_relationships(classified_tokens, text)

        # Build frames
        frames = self._build_frames(classified_tokens, relationships, text)

        # Collect vocabulary codes
        vocab_codes: dict[str, list[str]] = {}
        for ct in classified_tokens:
            if ct.vocabulary_code and ct.vocabulary_system:
                if ct.vocabulary_system not in vocab_codes:
                    vocab_codes[ct.vocabulary_system] = []
                vocab_codes[ct.vocabulary_system].append(ct.vocabulary_code)

        # Calculate coverage statistics
        coverage_stats = self._calculate_coverage(classified_tokens)

        processing_time = (time.perf_counter() - start_time) * 1000

        # Filter to entities (clinical content only)
        entity_categories = {
            OntologyCategory.DIAGNOSIS,
            OntologyCategory.SYMPTOM,
            OntologyCategory.MEDICATION,
            OntologyCategory.PROCEDURE,
            OntologyCategory.LAB_TEST,
            OntologyCategory.LAB_VALUE,
            OntologyCategory.VITAL_SIGN,
            OntologyCategory.VITAL_VALUE,
            OntologyCategory.IMAGING,
            OntologyCategory.FINDING,
            OntologyCategory.ANATOMY,
        }
        entities = [ct for ct in classified_tokens if ct.category in entity_categories]

        return OntologyMappingResult(
            tokens=classified_tokens,
            coverage_stats=coverage_stats,
            entities=entities,
            relationships=relationships,
            frames=frames,
            vocabulary_codes=vocab_codes,
            processing_time_ms=round(processing_time, 2),
            note_length=len(text),
        )

    def _tokenize(self, text: str) -> list[TokenSpan]:
        """Tokenize text into spans."""
        tokens = []

        # Pattern to match words, numbers with units, abbreviations, etc.
        pattern = re.compile(
            r"([A-Za-z]+(?:'[A-Za-z]+)?|"  # Words including contractions
            r"\d+(?:\.\d+)?(?:[-/]\d+(?:\.\d+)?)?|"  # Numbers including fractions/ranges
            r"[A-Za-z]+\d+|"  # Alphanumeric like V4, T2
            r"\d+[A-Za-z]+|"  # Numbers with units like 1000mg
            r"[A-Za-z]{2,}[-/][A-Za-z]{2,}|"  # Hyphenated terms
            r"[^\s\w])"  # Punctuation
        )

        for match in pattern.finditer(text):
            start = match.start()
            end = match.end()
            token_text = match.group()

            if token_text.strip():
                tokens.append(TokenSpan(
                    text=token_text,
                    start=start,
                    end=end,
                ))

        return tokens

    def tokenize_text(self, text: str) -> list[TokenSpan]:
        """Public interface for tokenizing text into spans."""
        return self._tokenize(text)

    def _classify_token(
        self,
        token: TokenSpan,
        full_text: str,
        previous_tokens: list[ClassifiedToken]
    ) -> ClassifiedToken:
        """Classify a single token into an ontology category."""
        text = token.text
        text_lower = text.lower()

        # Check for punctuation
        if len(text) == 1 and not text.isalnum():
            return ClassifiedToken(
                span=token,
                category=OntologyCategory.PUNCTUATION,
            )

        # Check for section headers
        if self._section_pattern.match(text):
            return ClassifiedToken(
                span=token,
                category=OntologyCategory.SECTION_HEADER,
            )

        # Check for list markers
        if re.match(r'^[0-9]+[.)\-]?$', text) or re.match(r'^[-•*]$', text):
            return ClassifiedToken(
                span=token,
                category=OntologyCategory.LIST_MARKER,
            )

        # Check for numeric values
        if self._numeric_pattern.match(text):
            return ClassifiedToken(
                span=token,
                category=OntologyCategory.NUMERIC_VALUE,
            )

        # Check for age patterns
        age_match = self._age_pattern.match(text)
        if age_match:
            return ClassifiedToken(
                span=token,
                category=OntologyCategory.AGE,
                attributes={"years": int(age_match.group(1))},
            )

        # Check for dates
        if self._date_pattern.match(text):
            return ClassifiedToken(
                span=token,
                category=OntologyCategory.DATE,
            )

        # Check for times
        if self._time_pattern.match(text):
            return ClassifiedToken(
                span=token,
                category=OntologyCategory.TIME,
            )

        # Check for number+unit combinations (e.g., "1000mg")
        num_unit_match = re.match(r'^(\d+(?:\.\d+)?)\s*([a-zA-Z/%]+)$', text)
        if num_unit_match:
            unit = num_unit_match.group(2).lower()
            if unit in self.lexicon.UNITS:
                return ClassifiedToken(
                    span=token,
                    category=OntologyCategory.LAB_VALUE if '/' in unit else OntologyCategory.NUMERIC_VALUE,
                    subcategory="value_with_unit",
                    attributes={
                        "value": float(num_unit_match.group(1)),
                        "unit": unit,
                    },
                )

        # Check for units
        if text_lower in self.lexicon.UNITS:
            unit_info = self.lexicon.UNITS[text_lower]
            return ClassifiedToken(
                span=token,
                category=OntologyCategory.UNIT,
                subcategory=unit_info[0],
                attributes={"full_name": unit_info[1]},
            )

        # Check for exam findings
        if text_lower in self.lexicon.EXAM_FINDINGS:
            finding_info = self.lexicon.EXAM_FINDINGS[text_lower]
            return ClassifiedToken(
                span=token,
                category=OntologyCategory.FINDING,
                subcategory=finding_info[1],
                vocabulary_code=finding_info[2].split(":")[-1] if ":" in finding_info[2] else "",
                vocabulary_system="SNOMED-CT" if finding_info[2].startswith("SNOMED") else "",
            )

        # Check for abbreviations
        if text_lower in self.lexicon.ABBREVIATIONS or text.upper() in self.lexicon.ABBREVIATIONS:
            key = text_lower if text_lower in self.lexicon.ABBREVIATIONS else text.upper().lower()
            expansion = self.lexicon.ABBREVIATIONS.get(key, self.lexicon.ABBREVIATIONS.get(text.upper().lower(), ""))

            # Determine category based on expansion
            category = OntologyCategory.ABBREVIATION
            if any(x in key for x in ['mi', 'cva', 'dvt', 'pe', 'copd', 'chf', 'ckd', 'dm', 'htn', 'afib', 'gerd', 'uti']):
                category = OntologyCategory.DIAGNOSIS
            elif any(x in key for x in ['ecg', 'ekg', 'cxr', 'ct', 'mri', 'echo']):
                category = OntologyCategory.PROCEDURE
            elif any(x in key for x in ['cbc', 'bmp', 'cmp', 'pt', 'ptt', 'inr', 'bnp', 'wbc', 'hgb']):
                category = OntologyCategory.LAB_TEST
            elif any(x in key for x in ['hr', 'bp', 'rr', 'spo2', 'temp']):
                category = OntologyCategory.VITAL_SIGN
            elif any(x in key for x in ['po', 'iv', 'im', 'sq', 'bid', 'tid', 'qid', 'prn']):
                category = OntologyCategory.FREQUENCY if any(x in key for x in ['bid', 'tid', 'qid', 'prn', 'qd']) else OntologyCategory.INSTRUCTION

            return ClassifiedToken(
                span=token,
                category=category,
                subcategory="abbreviation",
                attributes={"expansion": expansion},
            )

        # Check for severity terms
        if text_lower in self.lexicon.SEVERITY_TERMS:
            return ClassifiedToken(
                span=token,
                category=OntologyCategory.SEVERITY,
                attributes={"level": self.lexicon.SEVERITY_TERMS[text_lower]},
            )

        # Check for acuity terms
        if text_lower in self.lexicon.ACUITY_TERMS:
            return ClassifiedToken(
                span=token,
                category=OntologyCategory.ACUITY,
                attributes={"type": self.lexicon.ACUITY_TERMS[text_lower]},
            )

        # Check for status terms
        if text_lower in self.lexicon.STATUS_TERMS:
            return ClassifiedToken(
                span=token,
                category=OntologyCategory.STATUS,
                attributes={"type": self.lexicon.STATUS_TERMS[text_lower]},
            )

        # Check for negation
        if text_lower in self.lexicon.NEGATION_TERMS:
            return ClassifiedToken(
                span=token,
                category=OntologyCategory.NEGATION,
            )

        # Check for uncertainty
        if text_lower in self.lexicon.UNCERTAINTY_TERMS:
            return ClassifiedToken(
                span=token,
                category=OntologyCategory.UNCERTAINTY,
            )

        # Check for clinical actions
        if text_lower in self.lexicon.ACTION_TERMS:
            return ClassifiedToken(
                span=token,
                category=OntologyCategory.ACTION,
                attributes={"type": self.lexicon.ACTION_TERMS[text_lower]},
            )

        # Check for body systems
        if text_lower in self.lexicon.BODY_SYSTEMS:
            return ClassifiedToken(
                span=token,
                category=OntologyCategory.BODY_SYSTEM,
                vocabulary_code=self.lexicon.BODY_SYSTEMS[text_lower].split(":")[-1],
                vocabulary_system="SNOMED-CT",
            )

        # Check for anatomy terms
        if text_lower in self.lexicon.ANATOMY_TERMS:
            return ClassifiedToken(
                span=token,
                category=OntologyCategory.ANATOMY,
                vocabulary_code=self.lexicon.ANATOMY_TERMS[text_lower].split(":")[-1] if ":" in self.lexicon.ANATOMY_TERMS[text_lower] else "",
                vocabulary_system="SNOMED-CT",
            )

        # Check for symptom terms
        if text_lower in self.lexicon.SYMPTOM_TERMS:
            return ClassifiedToken(
                span=token,
                category=OntologyCategory.SYMPTOM,
                vocabulary_code=self.lexicon.SYMPTOM_TERMS[text_lower].split(":")[-1] if ":" in self.lexicon.SYMPTOM_TERMS[text_lower] else "",
                vocabulary_system="SNOMED-CT",
            )

        # Check for temporal terms
        if text_lower in self.lexicon.TEMPORAL_TERMS:
            return ClassifiedToken(
                span=token,
                category=OntologyCategory.TEMPORAL_MARKER,
            )

        # Check for clinical verbs
        if text_lower in self.lexicon.CLINICAL_VERBS:
            return ClassifiedToken(
                span=token,
                category=OntologyCategory.VERB,
                subcategory="clinical",
            )

        # Check for medical adjectives
        if text_lower in self.lexicon.MEDICAL_ADJECTIVES:
            return ClassifiedToken(
                span=token,
                category=OntologyCategory.ADJECTIVE,
                subcategory=self.lexicon.MEDICAL_ADJECTIVES[text_lower],
            )

        # Check for procedure terms
        if text_lower in self.lexicon.PROCEDURE_TERMS:
            return ClassifiedToken(
                span=token,
                category=OntologyCategory.PROCEDURE,
                vocabulary_system="SNOMED-CT",
            )

        # Check for code status terms
        if text_lower in self.lexicon.CODE_STATUS_TERMS:
            return ClassifiedToken(
                span=token,
                category=OntologyCategory.CODE_STATUS,
            )

        # Check for social history terms
        if text_lower in self.lexicon.SOCIAL_TERMS:
            return ClassifiedToken(
                span=token,
                category=OntologyCategory.SOCIAL_HISTORY,
            )

        # Check for additional clinical terms
        if text_lower in self.lexicon.ADDITIONAL_CLINICAL_TERMS:
            term_info = self.lexicon.ADDITIONAL_CLINICAL_TERMS[text_lower]
            category_map = {
                "procedure": OntologyCategory.PROCEDURE,
                "finding": OntologyCategory.FINDING,
                "status": OntologyCategory.STATUS,
                "unit": OntologyCategory.UNIT,
                "vital_sign": OntologyCategory.VITAL_SIGN,
                "action": OntologyCategory.ACTION,
                "anatomy": OntologyCategory.ANATOMY,
                "connector": OntologyCategory.CONNECTOR,
                "numeric_value": OntologyCategory.NUMERIC_VALUE,
                "demographic": OntologyCategory.DEMOGRAPHIC,
                "adjective": OntologyCategory.ADJECTIVE,
            }
            return ClassifiedToken(
                span=token,
                category=category_map.get(term_info[0], OntologyCategory.UNKNOWN),
                subcategory=term_info[1] if len(term_info) > 1 else "",
            )

        # Check vocabulary files
        if text_lower in self._medications:
            return ClassifiedToken(
                span=token,
                category=OntologyCategory.MEDICATION,
                vocabulary_system="RxNorm",
            )

        if text_lower in self._diagnoses:
            return ClassifiedToken(
                span=token,
                category=OntologyCategory.DIAGNOSIS,
                vocabulary_system="ICD-10-CM",
            )

        if text_lower in self._lab_tests:
            return ClassifiedToken(
                span=token,
                category=OntologyCategory.LAB_TEST,
                vocabulary_system="LOINC",
            )

        # Check for connectors
        if text_lower in self.lexicon.CONNECTORS:
            return ClassifiedToken(
                span=token,
                category=OntologyCategory.CONNECTOR,
            )

        # Check for prepositions
        if text_lower in self.lexicon.PREPOSITIONS:
            return ClassifiedToken(
                span=token,
                category=OntologyCategory.PREPOSITION,
            )

        # Check for pronouns
        if text_lower in self.lexicon.PRONOUNS:
            return ClassifiedToken(
                span=token,
                category=OntologyCategory.PRONOUN,
            )

        # Check for laterality
        laterality_terms = {"left", "right", "bilateral", "unilateral", "l", "r"}
        if text_lower in laterality_terms:
            return ClassifiedToken(
                span=token,
                category=OntologyCategory.LATERALITY,
            )

        # Check for location qualifiers
        location_qualifiers = {
            "upper", "lower", "anterior", "posterior", "medial", "lateral",
            "proximal", "distal", "superficial", "deep", "central", "peripheral"
        }
        if text_lower in location_qualifiers:
            return ClassifiedToken(
                span=token,
                category=OntologyCategory.LOCATION_QUALIFIER,
            )

        # Check for demographic terms
        demographics = {
            "male", "female", "man", "woman", "boy", "girl",
            "patient", "father", "mother", "brother", "sister",
            "son", "daughter", "parent", "child", "husband", "wife"
        }
        if text_lower in demographics:
            return ClassifiedToken(
                span=token,
                category=OntologyCategory.DEMOGRAPHIC,
            )

        # Default to unknown
        return ClassifiedToken(
            span=token,
            category=OntologyCategory.UNKNOWN,
        )

    def _extract_relationships(
        self,
        tokens: list[ClassifiedToken],
        text: str
    ) -> list[Relationship]:
        """Extract relationships between classified tokens."""
        relationships = []

        # Window-based relationship extraction
        for i, token in enumerate(tokens):
            # Look for value relationships (lab + value)
            if token.category == OntologyCategory.LAB_TEST:
                # Look ahead for values
                for j in range(i + 1, min(i + 5, len(tokens))):
                    if tokens[j].category in (OntologyCategory.NUMERIC_VALUE, OntologyCategory.LAB_VALUE):
                        relationships.append(Relationship(
                            subject=token,
                            relation=RelationType.HAS_VALUE,
                            object=tokens[j],
                        ))
                        break
                    if tokens[j].category in (OntologyCategory.LAB_TEST, OntologyCategory.DIAGNOSIS):
                        break

            # Medication + dose relationships
            if token.category == OntologyCategory.MEDICATION:
                for j in range(i + 1, min(i + 4, len(tokens))):
                    next_token = tokens[j]
                    if next_token.category == OntologyCategory.NUMERIC_VALUE:
                        # Check if followed by unit that suggests dose
                        if j + 1 < len(tokens) and tokens[j + 1].category == OntologyCategory.UNIT:
                            relationships.append(Relationship(
                                subject=token,
                                relation=RelationType.HAS_DOSE,
                                object=next_token,
                            ))
                    elif next_token.category == OntologyCategory.FREQUENCY:
                        relationships.append(Relationship(
                            subject=token,
                            relation=RelationType.HAS_FREQUENCY,
                            object=next_token,
                        ))
                    elif next_token.category == OntologyCategory.MEDICATION:
                        break

            # Diagnosis + treatment relationships
            if token.category == OntologyCategory.DIAGNOSIS:
                # Look for medications in nearby context
                for j in range(max(0, i - 10), min(i + 10, len(tokens))):
                    if tokens[j].category == OntologyCategory.MEDICATION:
                        # Check if "on" or treatment context
                        for k in range(j - 3, j):
                            if k >= 0 and tokens[k].span.text.lower() in ("on", "taking", "started", "given"):
                                relationships.append(Relationship(
                                    subject=token,
                                    relation=RelationType.TREATED_WITH,
                                    object=tokens[j],
                                ))
                                break

            # Finding + body system relationships
            if token.category == OntologyCategory.FINDING:
                for j in range(max(0, i - 5), i):
                    if tokens[j].category == OntologyCategory.BODY_SYSTEM:
                        relationships.append(Relationship(
                            subject=token,
                            relation=RelationType.LOCATED_IN,
                            object=tokens[j],
                        ))
                        break

            # Negation relationships
            if token.category == OntologyCategory.NEGATION:
                # Look ahead for what's negated
                for j in range(i + 1, min(i + 5, len(tokens))):
                    if tokens[j].category in (
                        OntologyCategory.FINDING,
                        OntologyCategory.SYMPTOM,
                        OntologyCategory.DIAGNOSIS,
                    ):
                        relationships.append(Relationship(
                            subject=tokens[j],
                            relation=RelationType.NEGATED_BY,
                            object=token,
                        ))
                        break

            # Severity relationships
            if token.category == OntologyCategory.SEVERITY:
                # Look ahead for what's modified
                for j in range(i + 1, min(i + 4, len(tokens))):
                    if tokens[j].category in (
                        OntologyCategory.SYMPTOM,
                        OntologyCategory.DIAGNOSIS,
                        OntologyCategory.FINDING,
                    ):
                        relationships.append(Relationship(
                            subject=tokens[j],
                            relation=RelationType.HAS_SEVERITY,
                            object=token,
                        ))
                        break

        return relationships

    def _build_frames(
        self,
        tokens: list[ClassifiedToken],
        relationships: list[Relationship],
        text: str
    ) -> list[ClinicalFrame]:
        """Build higher-level clinical frames from tokens and relationships."""
        frames = []

        # Group tokens by clinical concept
        current_frame_tokens: list[ClassifiedToken] = []
        current_frame_type = ""

        for token in tokens:
            # Start new frame for clinical entities
            if token.category in (
                OntologyCategory.DIAGNOSIS,
                OntologyCategory.MEDICATION,
                OntologyCategory.LAB_TEST,
                OntologyCategory.VITAL_SIGN,
                OntologyCategory.PROCEDURE,
            ):
                if current_frame_tokens:
                    frames.append(ClinicalFrame(
                        frame_type=current_frame_type,
                        tokens=current_frame_tokens,
                        relationships=[r for r in relationships
                                      if r.subject in current_frame_tokens or r.object in current_frame_tokens],
                    ))
                current_frame_tokens = [token]
                current_frame_type = token.category.value
            elif current_frame_tokens:
                # Add modifiers to current frame
                if token.category in (
                    OntologyCategory.NUMERIC_VALUE,
                    OntologyCategory.UNIT,
                    OntologyCategory.SEVERITY,
                    OntologyCategory.ACUITY,
                    OntologyCategory.STATUS,
                    OntologyCategory.FREQUENCY,
                    OntologyCategory.NEGATION,
                ):
                    current_frame_tokens.append(token)

        # Don't forget the last frame
        if current_frame_tokens:
            frames.append(ClinicalFrame(
                frame_type=current_frame_type,
                tokens=current_frame_tokens,
                relationships=[r for r in relationships
                              if r.subject in current_frame_tokens or r.object in current_frame_tokens],
            ))

        return frames

    def _calculate_coverage(self, tokens: list[ClassifiedToken]) -> dict[str, Any]:
        """Calculate coverage statistics."""
        total = len(tokens)
        if total == 0:
            return {"total_tokens": 0, "coverage_pct": 0}

        by_category: dict[str, int] = {}
        unknown_count = 0

        for token in tokens:
            cat = token.category.value
            by_category[cat] = by_category.get(cat, 0) + 1
            if token.category == OntologyCategory.UNKNOWN:
                unknown_count += 1

        coverage_pct = ((total - unknown_count) / total) * 100

        # Clinical coverage (entities only)
        clinical_categories = {
            'diagnosis', 'symptom', 'medication', 'procedure',
            'lab_test', 'lab_value', 'vital_sign', 'vital_value',
            'imaging', 'finding', 'anatomy'
        }
        clinical_count = sum(by_category.get(cat, 0) for cat in clinical_categories)

        return {
            "total_tokens": total,
            "classified_tokens": total - unknown_count,
            "unknown_tokens": unknown_count,
            "coverage_pct": round(coverage_pct, 1),
            "by_category": by_category,
            "clinical_entities": clinical_count,
            "clinical_entity_pct": round((clinical_count / total) * 100, 1) if total > 0 else 0,
        }


# =============================================================================
# FACTORY FUNCTION
# =============================================================================


_mapper_instance: ClinicalOntologyMapper | None = None
_mapper_lock = threading.Lock()


def get_ontology_mapper() -> ClinicalOntologyMapper:
    """Get or create the singleton ontology mapper instance."""
    global _mapper_instance
    # VP-ThreadSafety-3: Double-checked locking for thread safety
    if _mapper_instance is None:
        with _mapper_lock:
            if _mapper_instance is None:
                _mapper_instance = ClinicalOntologyMapper()
    return _mapper_instance
