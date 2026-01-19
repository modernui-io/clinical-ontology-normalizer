"""Clinical NLP Entity Extraction Service.

A comprehensive NLP service for extracting clinical entities from clinical notes
including diagnoses, medications, procedures, lab results, vital signs, anatomical
locations, and temporal expressions.

Features:
- Regex patterns and rule-based extraction as baseline
- Entity normalization to standard codes (SNOMED, RxNorm, LOINC, ICD-10)
- Negation detection (e.g., "no fever", "denies chest pain")
- Confidence scoring for each extraction
- Section detection (HPI, ROS, Assessment, Plan, etc.)
- Mock integration points for future ML models (spaCy, transformers)
"""

import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Protocol
from uuid import uuid4

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Types
# ============================================================================


class EntityType(str, Enum):
    """Types of clinical entities that can be extracted."""

    DIAGNOSIS = "diagnosis"
    MEDICATION = "medication"
    PROCEDURE = "procedure"
    LAB_RESULT = "lab_result"
    VITAL_SIGN = "vital_sign"
    ANATOMICAL_LOCATION = "anatomical_location"
    TEMPORAL = "temporal"
    SYMPTOM = "symptom"
    ALLERGY = "allergy"


class AssertionStatus(str, Enum):
    """Assertion status for extracted entities."""

    PRESENT = "present"
    ABSENT = "absent"
    POSSIBLE = "possible"
    CONDITIONAL = "conditional"
    HYPOTHETICAL = "hypothetical"
    FAMILY_HISTORY = "family_history"


class ClinicalSection(str, Enum):
    """Clinical document sections."""

    CHIEF_COMPLAINT = "chief_complaint"
    HPI = "hpi"
    ROS = "ros"
    PAST_MEDICAL_HISTORY = "pmh"
    PAST_SURGICAL_HISTORY = "psh"
    FAMILY_HISTORY = "fhx"
    SOCIAL_HISTORY = "shx"
    MEDICATIONS = "medications"
    ALLERGIES = "allergies"
    VITAL_SIGNS = "vitals"
    PHYSICAL_EXAM = "physical_exam"
    LABS = "labs"
    IMAGING = "imaging"
    ASSESSMENT = "assessment"
    PLAN = "plan"
    UNKNOWN = "unknown"


class NormalizationVocabulary(str, Enum):
    """Standard vocabularies for entity normalization."""

    SNOMED_CT = "SNOMED-CT"
    RXNORM = "RxNorm"
    LOINC = "LOINC"
    ICD10_CM = "ICD-10-CM"
    ICD10_PCS = "ICD-10-PCS"
    CPT = "CPT"
    NDC = "NDC"


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class EntitySpan:
    """Represents a text span in the source document."""

    start: int
    end: int
    text: str


@dataclass
class NormalizedCode:
    """A normalized code from a standard vocabulary."""

    code: str
    display: str
    system: NormalizationVocabulary
    confidence: float = 0.0
    is_preferred: bool = False


@dataclass
class ExtractedEntity:
    """A clinical entity extracted from text."""

    id: str
    entity_type: EntityType
    text: str
    normalized_text: str
    span: EntitySpan
    section: ClinicalSection
    assertion: AssertionStatus
    confidence: float
    normalized_codes: list[NormalizedCode] = field(default_factory=list)

    # Entity-specific fields
    value: str | None = None
    unit: str | None = None
    reference_range: str | None = None
    laterality: str | None = None
    dosage: str | None = None
    frequency: str | None = None
    route: str | None = None
    duration: str | None = None

    # Negation information
    negation_trigger: str | None = None
    negation_scope_start: int | None = None
    negation_scope_end: int | None = None


@dataclass
class SectionSpan:
    """A detected clinical section in the document."""

    section: ClinicalSection
    start: int
    end: int
    header_text: str | None = None


@dataclass
class ExtractionResult:
    """Result of entity extraction from a clinical note."""

    request_id: str
    text_length: int
    entities: list[ExtractedEntity]
    sections: list[SectionSpan]
    processing_time_ms: float
    model_used: str

    @property
    def entity_count(self) -> int:
        return len(self.entities)

    @property
    def entities_by_type(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for entity in self.entities:
            key = entity.entity_type.value
            counts[key] = counts.get(key, 0) + 1
        return counts


@dataclass
class NormalizationResult:
    """Result of normalizing entities to standard codes."""

    entity_id: str
    original_text: str
    normalized_codes: list[NormalizedCode]
    best_match: NormalizedCode | None
    processing_time_ms: float


@dataclass
class NLPModelInfo:
    """Information about an available NLP model."""

    model_id: str
    name: str
    description: str
    entity_types: list[EntityType]
    is_available: bool
    requires_gpu: bool = False
    version: str = "1.0.0"


# ============================================================================
# Protocols for ML Model Integration
# ============================================================================


class MLModelProtocol(Protocol):
    """Protocol for ML model integration (spaCy, transformers, etc.)."""

    def extract_entities(
        self, text: str, entity_types: list[EntityType] | None = None
    ) -> list[ExtractedEntity]:
        """Extract entities using the ML model."""
        ...

    def get_model_info(self) -> NLPModelInfo:
        """Get information about the model."""
        ...


# ============================================================================
# Clinical NLP Entity Service
# ============================================================================


class ClinicalNLPEntityService:
    """Service for extracting clinical entities from clinical notes.

    This service provides:
    - Rule-based entity extraction using regex patterns
    - Negation detection using NegEx-style algorithms
    - Section detection for clinical documents
    - Entity normalization to standard vocabularies
    - Confidence scoring for extractions
    - Integration points for ML models

    Usage:
        service = get_nlp_entity_service()
        result = service.extract_entities(clinical_text)
        for entity in result.entities:
            print(f"{entity.entity_type}: {entity.text} ({entity.confidence})")
    """

    # ========================================================================
    # Section Detection Patterns
    # ========================================================================

    SECTION_PATTERNS: dict[ClinicalSection, list[str]] = {
        ClinicalSection.CHIEF_COMPLAINT: [
            r"(?:chief\s+complaint|cc|presenting\s+complaint)[\s:]+",
        ],
        ClinicalSection.HPI: [
            r"(?:history\s+of\s+present(?:ing)?\s+illness|hpi|present\s+illness)[\s:]+",
        ],
        ClinicalSection.ROS: [
            r"(?:review\s+of\s+systems?|ros)[\s:]+",
        ],
        ClinicalSection.PAST_MEDICAL_HISTORY: [
            r"(?:past\s+medical\s+history|pmh|medical\s+history)[\s:]+",
        ],
        ClinicalSection.PAST_SURGICAL_HISTORY: [
            r"(?:past\s+surgical\s+history|psh|surgical\s+history)[\s:]+",
        ],
        ClinicalSection.FAMILY_HISTORY: [
            r"(?:family\s+history|fh|fhx)[\s:]+",
        ],
        ClinicalSection.SOCIAL_HISTORY: [
            r"(?:social\s+history|sh|shx)[\s:]+",
        ],
        ClinicalSection.MEDICATIONS: [
            r"(?:medications?|meds|current\s+medications?|home\s+medications?)[\s:]+",
        ],
        ClinicalSection.ALLERGIES: [
            r"(?:allergies|drug\s+allergies|medication\s+allergies|nkda)[\s:]+",
        ],
        ClinicalSection.VITAL_SIGNS: [
            r"(?:vital\s+signs?|vitals)[\s:]+",
        ],
        ClinicalSection.PHYSICAL_EXAM: [
            r"(?:physical\s+exam(?:ination)?|pe|exam)[\s:]+",
        ],
        ClinicalSection.LABS: [
            r"(?:lab(?:oratory)?\s+(?:results?|data|values?)|labs)[\s:]+",
        ],
        ClinicalSection.IMAGING: [
            r"(?:imaging|radiology|x-?ray|ct|mri|ultrasound)[\s:]+",
        ],
        ClinicalSection.ASSESSMENT: [
            r"(?:assessment|impression|diagnosis|diagnoses)[\s:]+",
        ],
        ClinicalSection.PLAN: [
            r"(?:plan|recommendations?|disposition)[\s:]+",
        ],
    }

    # ========================================================================
    # Negation Detection Patterns
    # ========================================================================

    NEGATION_TRIGGERS = [
        r"\bno\b",
        r"\bnot\b",
        r"\bdenies\b",
        r"\bdenied\b",
        r"\bwithout\b",
        r"\babsence\s+of\b",
        r"\bnegative\s+for\b",
        r"\bruled\s+out\b",
        r"\bunlikely\b",
        r"\bno\s+evidence\s+of\b",
        r"\bnever\b",
        r"\bnone\b",
        r"\bfree\s+of\b",
        r"\brules\s+out\b",
        r"\bdeclines\b",
        r"\bdoes\s+not\s+have\b",
        r"\bnon-?\b",
    ]

    UNCERTAINTY_TRIGGERS = [
        r"\bcannot\s+rule\s+out\b",
        r"\bcan\'?t\s+rule\s+out\b",
        r"\bpossible\b",
        r"\bprobable\b",
        r"\bsuspected?\b",
        r"\bquestionable\b",
        r"\bmay\s+have\b",
        r"\bmight\s+have\b",
        r"\bcould\s+be\b",
        r"\bappears?\s+to\s+be\b",
        r"\blikely\b",
        r"\bconcern\s+for\b",
        r"\brule\s+out\b",
        r"\b(?:r/o|ro)\b",
    ]

    FAMILY_HISTORY_TRIGGERS = [
        r"\bfamily\s+history\b",
        r"\bfamily\s+hx\b",
        r"\bfhx\b",
        r"\bmother\s+(?:has|had|with|diagnosed)\b",
        r"\bfather\s+(?:has|had|with|diagnosed)\b",
        r"\bsibling\s+(?:has|had|with|diagnosed)\b",
        r"\bbrother\s+(?:has|had|with|diagnosed)\b",
        r"\bsister\s+(?:has|had|with|diagnosed)\b",
        r"\bparent\s+(?:has|had|with|diagnosed)\b",
    ]

    # ========================================================================
    # Entity Extraction Patterns
    # ========================================================================

    # Diagnosis/Problem patterns
    DIAGNOSIS_PATTERNS = [
        # Common conditions
        (r"\b(type\s*[12]?\s*)?diabet(?:es|ic)(?:\s+mellitus)?(?:\s+(?:with|without)\s+\w+)?\b", "Diabetes"),
        (r"\bhypertension|htn|high\s+blood\s+pressure\b", "Hypertension"),
        (r"\b(?:congestive\s+)?heart\s+failure|chf|hfref|hfpef\b", "Heart Failure"),
        (r"\bcoronary\s+artery\s+disease|cad\b", "Coronary Artery Disease"),
        (r"\batrial\s+fibrillation|afib|a\.?\s*fib\b", "Atrial Fibrillation"),
        (r"\bchronic\s+(?:kidney|renal)\s+disease|ckd\b", "Chronic Kidney Disease"),
        (r"\bcopd|chronic\s+obstructive\s+pulmonary\s+disease\b", "COPD"),
        (r"\basthma\b", "Asthma"),
        (r"\bpneumonia\b", "Pneumonia"),
        (r"\bstroke|cva|cerebrovascular\s+accident\b", "Stroke"),
        (r"\bmi|myocardial\s+infarction|heart\s+attack\b", "Myocardial Infarction"),
        (r"\bdepression|major\s+depressive\s+disorder|mdd\b", "Depression"),
        (r"\banxiety(?:\s+disorder)?\b", "Anxiety"),
        (r"\bhyperlipidemia|dyslipidemia|high\s+cholesterol\b", "Hyperlipidemia"),
        (r"\bhypothyroidism\b", "Hypothyroidism"),
        (r"\bhyperthyroidism\b", "Hyperthyroidism"),
        (r"\bgerd|gastroesophageal\s+reflux\b", "GERD"),
        (r"\bosteoarthritis|oa\b", "Osteoarthritis"),
        (r"\brheumatoid\s+arthritis|ra\b", "Rheumatoid Arthritis"),
        (r"\bobesity\b", "Obesity"),
        (r"\bsleep\s+apnea|osa|obstructive\s+sleep\s+apnea\b", "Sleep Apnea"),
        (r"\bdvt|deep\s+vein\s+thrombosis\b", "Deep Vein Thrombosis"),
        (r"\bpulmonary\s+embolism|pe\b", "Pulmonary Embolism"),
        (r"\buti|urinary\s+tract\s+infection\b", "Urinary Tract Infection"),
        (r"\bsepsis\b", "Sepsis"),
        (r"\bcancer|malignancy|carcinoma|neoplasm\b", "Cancer"),
        (r"\banemia\b", "Anemia"),
    ]

    # Symptom patterns
    SYMPTOM_PATTERNS = [
        (r"\bfever|febrile\b", "Fever"),
        (r"\bcough(?:ing)?\b", "Cough"),
        (r"\bshortness\s+of\s+breath|sob|dyspnea\b", "Shortness of Breath"),
        (r"\bchest\s+pain\b", "Chest Pain"),
        (r"\babdominal\s+pain|stomach\s+ache\b", "Abdominal Pain"),
        (r"\bheadache|cephalgia\b", "Headache"),
        (r"\bnausea\b", "Nausea"),
        (r"\bvomiting|emesis\b", "Vomiting"),
        (r"\bdiarrhea\b", "Diarrhea"),
        (r"\bconstipation\b", "Constipation"),
        (r"\bfatigue|tiredness\b", "Fatigue"),
        (r"\bdizziness|vertigo\b", "Dizziness"),
        (r"\bpalpitations\b", "Palpitations"),
        (r"\bedema|swelling\b", "Edema"),
        (r"\brash\b", "Rash"),
        (r"\bitching|pruritus\b", "Itching"),
        (r"\bweight\s+(?:loss|gain)\b", "Weight Change"),
        (r"\binsomnia\b", "Insomnia"),
        (r"\bjoint\s+pain|arthralgia\b", "Joint Pain"),
        (r"\bback\s+pain\b", "Back Pain"),
        (r"\bneck\s+pain\b", "Neck Pain"),
        (r"\bweakness\b", "Weakness"),
        (r"\bnumbness|paresthesia\b", "Numbness"),
        (r"\bconfusion\b", "Confusion"),
    ]

    # Medication patterns
    MEDICATION_PATTERNS = [
        # Pattern: drug name followed by optional dosage, frequency, route
        r"\b(metformin|glucophage)\s*(?:(\d+(?:\.\d+)?\s*(?:mg|g)))?(?:\s+(daily|bid|tid|qid|qd|prn))?",
        r"\b(lisinopril|prinivil|zestril)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid|qd))?",
        r"\b(atorvastatin|lipitor)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|qd|qhs))?",
        r"\b(amlodipine|norvasc)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|qd))?",
        r"\b(omeprazole|prilosec)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid|qd))?",
        r"\b(aspirin|asa)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|qd))?",
        r"\b(warfarin|coumadin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|qd))?",
        r"\b(insulin(?:\s+(?:glargine|lispro|aspart|regular|nph))?)\s*(?:(\d+(?:\.\d+)?\s*(?:units?|u)))?",
        r"\b(acetaminophen|tylenol)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(q\d+h|prn))?",
        r"\b(ibuprofen|advil|motrin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(q\d+h|prn|tid))?",
        r"\b(hydrocodone|norco|vicodin)\s*(?:(\d+(?:[\/\-]\d+)?\s*(?:mg)))?(?:\s+(q\d+h|prn))?",
        r"\b(gabapentin|neurontin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(tid|bid|qhs))?",
        r"\b(prednisone)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|taper))?",
        r"\b(albuterol|proventil|ventolin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg|puffs?)))?(?:\s+(q\d+h|prn))?",
        r"\b(furosemide|lasix)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
        r"\b(carvedilol|coreg)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(bid))?",
        r"\b(metoprolol(?:\s+(?:tartrate|succinate))?)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
        r"\b(pantoprazole|protonix)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
        r"\b(clopidogrel|plavix)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
        r"\b(levothyroxine|synthroid)\s*(?:(\d+(?:\.\d+)?\s*(?:mcg|mg)))?(?:\s+(daily))?",
    ]

    # Procedure patterns
    PROCEDURE_PATTERNS = [
        (r"\b(?:coronary\s+)?angiography|cath(?:eterization)?\b", "Cardiac Catheterization"),
        (r"\b(?:coronary\s+)?angioplasty|pci|ptca\b", "Coronary Angioplasty"),
        (r"\bcabg|coronary\s+(?:artery\s+)?bypass(?:\s+graft(?:ing)?)?\b", "CABG"),
        (r"\bcolonoscopy\b", "Colonoscopy"),
        (r"\bendoscopy|egd\b", "Endoscopy"),
        (r"\bappendectomy\b", "Appendectomy"),
        (r"\bcholecystectomy\b", "Cholecystectomy"),
        (r"\bhysterectomy\b", "Hysterectomy"),
        (r"\bjoint\s+replacement|arthroplasty\b", "Joint Replacement"),
        (r"\bknee\s+replacement|tka\b", "Total Knee Arthroplasty"),
        (r"\bhip\s+replacement|tha\b", "Total Hip Arthroplasty"),
        (r"\blaminectomy\b", "Laminectomy"),
        (r"\bspinal\s+fusion\b", "Spinal Fusion"),
        (r"\bdialysis|hemodialysis|hd\b", "Dialysis"),
        (r"\bchemotherapy|chemo\b", "Chemotherapy"),
        (r"\bradiation(?:\s+therapy)?\b", "Radiation Therapy"),
        (r"\bsurgery|surgical\s+(?:procedure|intervention)\b", "Surgery"),
        (r"\bbiopsy\b", "Biopsy"),
        (r"\btransfusion\b", "Transfusion"),
        (r"\bintubation\b", "Intubation"),
        (r"\bventilation|mechanical\s+ventilation\b", "Mechanical Ventilation"),
        (r"\bcpr|cardiopulmonary\s+resuscitation\b", "CPR"),
    ]

    # Vital sign patterns
    VITAL_SIGN_PATTERNS = [
        # Blood pressure: "BP 120/80", "blood pressure 120/80 mmHg"
        (
            r"(?:blood\s+pressure|bp)\s*[:\s]*(\d{2,3})\s*/\s*(\d{2,3})\s*(?:mm\s*hg)?",
            "blood_pressure",
        ),
        # Heart rate: "HR 72", "pulse 72 bpm", "heart rate 72"
        (
            r"(?:heart\s+rate|hr|pulse)\s*[:\s]*(\d{2,3})\s*(?:bpm|beats?\s*(?:per\s*)?(?:min(?:ute)?)?)?",
            "heart_rate",
        ),
        # Temperature: "temp 98.6 F", "temperature 37.0 C"
        (
            r"(?:temperature|temp)\s*[:\s]*([\d.]+)\s*(?:°?\s*)?([FCfc])?",
            "temperature",
        ),
        # Respiratory rate: "RR 16", "respirations 16/min"
        (
            r"(?:respiratory\s+rate|resp(?:iratory)?\s+rate|rr|respirations?)\s*[:\s]*(\d{1,2})\s*(?:/\s*min)?",
            "respiratory_rate",
        ),
        # Oxygen saturation: "SpO2 98%", "O2 sat 98%", "oxygen saturation 98%"
        (
            r"(?:spo2|o2\s*sat(?:uration)?|oxygen\s+saturation|sat)\s*[:\s]*(\d{2,3})\s*%?",
            "oxygen_saturation",
        ),
        # Weight: "weight 70 kg", "wt 154 lbs"
        (
            r"(?:weight|wt)\s*[:\s]*([\d.]+)\s*(kg|lbs?|pounds?|kilograms?)?",
            "weight",
        ),
        # Height: "height 5'10\"", "ht 170 cm"
        (
            r"(?:height|ht)\s*[:\s]*(?:(\d+)\s*[\'\']\s*(\d+)\s*[\"\"]?|([\d.]+)\s*(?:cm|in(?:ches)?|m(?:eters?)?)?)",
            "height",
        ),
        # BMI: "BMI 25.4"
        (
            r"(?:bmi|body\s+mass\s+index)\s*[:\s]*([\d.]+)",
            "bmi",
        ),
    ]

    # Lab result patterns
    LAB_RESULT_PATTERNS = [
        # Glucose/blood sugar
        (
            r"(?:glucose|blood\s+sugar|bs|fbs|fasting\s+glucose)\s*[:\s]*([\d.]+)\s*(mg/dl|mmol/l)?",
            "glucose",
            "mg/dL",
            "70-100",
        ),
        # Hemoglobin A1c
        (
            r"(?:hba1c|hemoglobin\s+a1c|a1c|glycated\s+hemoglobin)\s*[:\s]*([\d.]+)\s*%?",
            "hba1c",
            "%",
            "<5.7",
        ),
        # Hemoglobin
        (
            r"(?:hemoglobin|hgb|hb)\s*[:\s]*([\d.]+)\s*(g/dl)?",
            "hemoglobin",
            "g/dL",
            "12-17",
        ),
        # WBC
        (
            r"(?:wbc|white\s+blood\s+cell(?:s)?(?:\s+count)?)\s*[:\s]*([\d.]+)\s*(k/ul|x10\^?9/l)?",
            "wbc",
            "K/uL",
            "4.5-11.0",
        ),
        # Platelet count
        (
            r"(?:platelet(?:s)?|plt)\s*[:\s]*([\d.]+)\s*(k/ul|x10\^?9/l)?",
            "platelets",
            "K/uL",
            "150-400",
        ),
        # Creatinine
        (
            r"(?:creatinine|cr)\s*[:\s]*([\d.]+)\s*(mg/dl)?",
            "creatinine",
            "mg/dL",
            "0.7-1.3",
        ),
        # BUN
        (
            r"(?:bun|blood\s+urea\s+nitrogen)\s*[:\s]*([\d.]+)\s*(mg/dl)?",
            "bun",
            "mg/dL",
            "7-20",
        ),
        # eGFR
        (
            r"(?:egfr|gfr|estimated\s+gfr)\s*[:\s]*([\d.]+)\s*(ml/min)?",
            "egfr",
            "mL/min",
            ">60",
        ),
        # Sodium
        (
            r"(?:sodium|na)\s*[:\s]*([\d.]+)\s*(meq/l|mmol/l)?",
            "sodium",
            "mEq/L",
            "136-145",
        ),
        # Potassium
        (
            r"(?:potassium|k)\s*[:\s]*([\d.]+)\s*(meq/l|mmol/l)?",
            "potassium",
            "mEq/L",
            "3.5-5.0",
        ),
        # Chloride
        (
            r"(?:chloride|cl)\s*[:\s]*([\d.]+)\s*(meq/l|mmol/l)?",
            "chloride",
            "mEq/L",
            "98-106",
        ),
        # CO2/Bicarbonate
        (
            r"(?:co2|bicarbonate|bicarb|hco3)\s*[:\s]*([\d.]+)\s*(meq/l|mmol/l)?",
            "co2",
            "mEq/L",
            "22-29",
        ),
        # Total cholesterol
        (
            r"(?:total\s+)?(?:cholesterol|chol)\s*[:\s]*([\d.]+)\s*(mg/dl)?",
            "cholesterol",
            "mg/dL",
            "<200",
        ),
        # LDL
        (
            r"(?:ldl|low\s+density\s+lipoprotein)\s*[:\s]*([\d.]+)\s*(mg/dl)?",
            "ldl",
            "mg/dL",
            "<100",
        ),
        # HDL
        (
            r"(?:hdl|high\s+density\s+lipoprotein)\s*[:\s]*([\d.]+)\s*(mg/dl)?",
            "hdl",
            "mg/dL",
            ">40",
        ),
        # Triglycerides
        (
            r"(?:triglycerides|tg)\s*[:\s]*([\d.]+)\s*(mg/dl)?",
            "triglycerides",
            "mg/dL",
            "<150",
        ),
        # TSH
        (
            r"(?:tsh|thyroid\s+stimulating\s+hormone)\s*[:\s]*([\d.]+)\s*(miu/l|uiu/ml)?",
            "tsh",
            "mIU/L",
            "0.4-4.0",
        ),
        # INR
        (
            r"(?:inr|international\s+normalized\s+ratio)\s*[:\s]*([\d.]+)",
            "inr",
            "",
            "0.9-1.1",
        ),
        # BNP
        (
            r"(?:bnp|b-?type\s+natriuretic\s+peptide)\s*[:\s]*([\d.]+)\s*(pg/ml)?",
            "bnp",
            "pg/mL",
            "<100",
        ),
        # Troponin
        (
            r"(?:troponin(?:\s+[it])?|tn[it])\s*[:\s]*([\d.]+)\s*(ng/ml|ng/l)?",
            "troponin",
            "ng/mL",
            "<0.04",
        ),
        # Procalcitonin
        (
            r"(?:procalcitonin|pct)\s*[:\s]*([\d.]+)\s*(ng/ml)?",
            "procalcitonin",
            "ng/mL",
            "<0.1",
        ),
    ]

    # Anatomical location patterns
    ANATOMICAL_PATTERNS = [
        (r"\b(left|right|bilateral)\s+(arm|leg|hand|foot|eye|ear|lung|kidney|breast)\b", None),
        (r"\b(upper|lower)\s+(extremity|extremities|lobe|quadrant)\b", None),
        (r"\b(anterior|posterior|lateral|medial)\s+\w+\b", None),
        (r"\b(head|neck|chest|abdomen|pelvis|back|spine)\b", None),
        (r"\b(heart|lungs?|liver|kidneys?|brain|stomach|intestines?|colon)\b", None),
        (r"\b(lul|rul|lll|rll|rml)\b", None),  # Lung lobes
        (r"\b(ruq|luq|rlq|llq)\b", None),  # Abdominal quadrants
    ]

    # Temporal expression patterns
    TEMPORAL_PATTERNS = [
        (r"\b(\d+)\s*(days?|weeks?|months?|years?)\s+(ago|prior)\b", "relative_past"),
        (r"\b(since|for)\s+(\d+)\s*(days?|weeks?|months?|years?)\b", "duration"),
        (r"\b(yesterday|today|tomorrow)\b", "relative_day"),
        (r"\b(morning|afternoon|evening|night|overnight)\b", "time_of_day"),
        (r"\b(daily|weekly|monthly|yearly|annually)\b", "frequency"),
        (r"\b(chronic|acute|subacute|intermittent|persistent)\b", "temporal_quality"),
        (r"\b(onset|started|began|developed)\s+(\d+)\s*(days?|weeks?|months?|years?)\s+ago\b", "onset"),
        (r"\b(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})\b", "date"),
    ]

    # Laterality patterns
    LATERALITY_PATTERNS = [
        (r"\bleft\b", "left"),
        (r"\bright\b", "right"),
        (r"\bbilateral\b", "bilateral"),
        (r"\bunilateral\b", "unilateral"),
    ]

    def __init__(self) -> None:
        """Initialize the Clinical NLP Entity Service."""
        self._ml_models: dict[str, MLModelProtocol] = {}
        self._initialized = False
        logger.info("ClinicalNLPEntityService initialized")

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for efficiency."""
        if self._initialized:
            return

        # Compile section patterns
        self._section_regexes: dict[ClinicalSection, list[re.Pattern]] = {}
        for section, patterns in self.SECTION_PATTERNS.items():
            self._section_regexes[section] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]

        # Compile negation patterns
        self._negation_regexes = [
            re.compile(p, re.IGNORECASE) for p in self.NEGATION_TRIGGERS
        ]
        self._uncertainty_regexes = [
            re.compile(p, re.IGNORECASE) for p in self.UNCERTAINTY_TRIGGERS
        ]
        self._family_history_regexes = [
            re.compile(p, re.IGNORECASE) for p in self.FAMILY_HISTORY_TRIGGERS
        ]

        self._initialized = True

    def extract_entities(
        self,
        text: str,
        entity_types: list[EntityType] | None = None,
        use_ml_models: bool = False,
        model_id: str | None = None,
    ) -> ExtractionResult:
        """Extract clinical entities from text.

        Args:
            text: The clinical note text to process.
            entity_types: Optional list of entity types to extract. If None, extracts all.
            use_ml_models: Whether to use ML models if available.
            model_id: Specific ML model to use. If None, uses default.

        Returns:
            ExtractionResult with extracted entities and metadata.
        """
        start_time = time.perf_counter()
        request_id = str(uuid4())

        self._compile_patterns()

        # Default to all entity types
        if entity_types is None:
            entity_types = list(EntityType)

        # Detect sections first
        sections = self._detect_sections(text)

        # Extract entities by type
        entities: list[ExtractedEntity] = []

        if EntityType.DIAGNOSIS in entity_types or EntityType.SYMPTOM in entity_types:
            entities.extend(self._extract_diagnoses_and_symptoms(text, sections))

        if EntityType.MEDICATION in entity_types:
            entities.extend(self._extract_medications(text, sections))

        if EntityType.PROCEDURE in entity_types:
            entities.extend(self._extract_procedures(text, sections))

        if EntityType.LAB_RESULT in entity_types:
            entities.extend(self._extract_lab_results(text, sections))

        if EntityType.VITAL_SIGN in entity_types:
            entities.extend(self._extract_vital_signs(text, sections))

        if EntityType.ANATOMICAL_LOCATION in entity_types:
            entities.extend(self._extract_anatomical_locations(text, sections))

        if EntityType.TEMPORAL in entity_types:
            entities.extend(self._extract_temporal_expressions(text, sections))

        # Apply negation detection to all entities
        entities = self._apply_negation_detection(text, entities)

        # Use ML models if requested
        model_used = "rule_based"
        if use_ml_models and model_id and model_id in self._ml_models:
            ml_entities = self._ml_models[model_id].extract_entities(text, entity_types)
            entities = self._merge_entities(entities, ml_entities)
            model_used = f"ensemble_{model_id}"

        # Sort entities by position
        entities.sort(key=lambda e: e.span.start)

        # Remove duplicates
        entities = self._deduplicate_entities(entities)

        processing_time = (time.perf_counter() - start_time) * 1000

        return ExtractionResult(
            request_id=request_id,
            text_length=len(text),
            entities=entities,
            sections=sections,
            processing_time_ms=round(processing_time, 2),
            model_used=model_used,
        )

    def _detect_sections(self, text: str) -> list[SectionSpan]:
        """Detect clinical sections in the document."""
        sections: list[SectionSpan] = []
        text_lower = text.lower()

        for section, patterns in self._section_regexes.items():
            for pattern in patterns:
                for match in pattern.finditer(text_lower):
                    sections.append(
                        SectionSpan(
                            section=section,
                            start=match.start(),
                            end=len(text),  # Will be adjusted
                            header_text=match.group(0).strip(),
                        )
                    )

        # Sort by start position and adjust end positions
        sections.sort(key=lambda s: s.start)
        for i, section in enumerate(sections):
            if i < len(sections) - 1:
                section.end = sections[i + 1].start

        return sections

    def _get_section_at_offset(
        self, offset: int, sections: list[SectionSpan]
    ) -> ClinicalSection:
        """Get the section at a given offset."""
        for section in reversed(sections):
            if section.start <= offset < section.end:
                return section.section
        return ClinicalSection.UNKNOWN

    def _extract_diagnoses_and_symptoms(
        self, text: str, sections: list[SectionSpan]
    ) -> list[ExtractedEntity]:
        """Extract diagnosis and symptom entities."""
        entities: list[ExtractedEntity] = []
        text_lower = text.lower()

        # Extract diagnoses
        for pattern, normalized_name in self.DIAGNOSIS_PATTERNS:
            for match in re.finditer(pattern, text_lower, re.IGNORECASE):
                span = EntitySpan(
                    start=match.start(),
                    end=match.end(),
                    text=text[match.start() : match.end()],
                )
                section = self._get_section_at_offset(match.start(), sections)
                confidence = self._calculate_confidence(
                    match.group(0), normalized_name, section, EntityType.DIAGNOSIS
                )

                entity = ExtractedEntity(
                    id=str(uuid4()),
                    entity_type=EntityType.DIAGNOSIS,
                    text=span.text,
                    normalized_text=normalized_name,
                    span=span,
                    section=section,
                    assertion=AssertionStatus.PRESENT,  # Will be updated by negation detection
                    confidence=confidence,
                )
                entities.append(entity)

        # Extract symptoms
        for pattern, normalized_name in self.SYMPTOM_PATTERNS:
            for match in re.finditer(pattern, text_lower, re.IGNORECASE):
                span = EntitySpan(
                    start=match.start(),
                    end=match.end(),
                    text=text[match.start() : match.end()],
                )
                section = self._get_section_at_offset(match.start(), sections)
                confidence = self._calculate_confidence(
                    match.group(0), normalized_name, section, EntityType.SYMPTOM
                )

                entity = ExtractedEntity(
                    id=str(uuid4()),
                    entity_type=EntityType.SYMPTOM,
                    text=span.text,
                    normalized_text=normalized_name,
                    span=span,
                    section=section,
                    assertion=AssertionStatus.PRESENT,
                    confidence=confidence,
                )
                entities.append(entity)

        return entities

    def _extract_medications(
        self, text: str, sections: list[SectionSpan]
    ) -> list[ExtractedEntity]:
        """Extract medication entities with dosage, frequency, and route."""
        entities: list[ExtractedEntity] = []

        for pattern in self.MEDICATION_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                drug_name = match.group(1)
                dosage = match.group(2) if match.lastindex >= 2 else None
                frequency = match.group(3) if match.lastindex >= 3 else None

                span = EntitySpan(
                    start=match.start(),
                    end=match.end(),
                    text=text[match.start() : match.end()],
                )
                section = self._get_section_at_offset(match.start(), sections)

                # Higher confidence in Medications section
                confidence = 0.85 if section == ClinicalSection.MEDICATIONS else 0.75

                entity = ExtractedEntity(
                    id=str(uuid4()),
                    entity_type=EntityType.MEDICATION,
                    text=span.text,
                    normalized_text=drug_name.title(),
                    span=span,
                    section=section,
                    assertion=AssertionStatus.PRESENT,
                    confidence=confidence,
                    dosage=dosage,
                    frequency=frequency,
                )
                entities.append(entity)

        return entities

    def _extract_procedures(
        self, text: str, sections: list[SectionSpan]
    ) -> list[ExtractedEntity]:
        """Extract procedure entities."""
        entities: list[ExtractedEntity] = []
        text_lower = text.lower()

        for pattern, normalized_name in self.PROCEDURE_PATTERNS:
            for match in re.finditer(pattern, text_lower, re.IGNORECASE):
                span = EntitySpan(
                    start=match.start(),
                    end=match.end(),
                    text=text[match.start() : match.end()],
                )
                section = self._get_section_at_offset(match.start(), sections)

                # Higher confidence for PSH section
                confidence = 0.85 if section == ClinicalSection.PAST_SURGICAL_HISTORY else 0.75

                entity = ExtractedEntity(
                    id=str(uuid4()),
                    entity_type=EntityType.PROCEDURE,
                    text=span.text,
                    normalized_text=normalized_name,
                    span=span,
                    section=section,
                    assertion=AssertionStatus.PRESENT,
                    confidence=confidence,
                )
                entities.append(entity)

        return entities

    def _extract_vital_signs(
        self, text: str, sections: list[SectionSpan]
    ) -> list[ExtractedEntity]:
        """Extract vital sign entities with values and units."""
        entities: list[ExtractedEntity] = []

        for pattern, vital_name in self.VITAL_SIGN_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                span = EntitySpan(
                    start=match.start(),
                    end=match.end(),
                    text=text[match.start() : match.end()],
                )
                section = self._get_section_at_offset(match.start(), sections)

                # Extract value based on vital type
                value = None
                unit = None

                if vital_name == "blood_pressure":
                    value = f"{match.group(1)}/{match.group(2)}"
                    unit = "mmHg"
                elif vital_name == "heart_rate":
                    value = match.group(1)
                    unit = "bpm"
                elif vital_name == "temperature":
                    value = match.group(1)
                    unit = match.group(2).upper() if match.group(2) else "F"
                elif vital_name == "respiratory_rate":
                    value = match.group(1)
                    unit = "/min"
                elif vital_name == "oxygen_saturation":
                    value = match.group(1)
                    unit = "%"
                elif vital_name == "weight":
                    value = match.group(1)
                    unit = match.group(2) if match.lastindex >= 2 and match.group(2) else "kg"
                elif vital_name == "bmi":
                    value = match.group(1)
                    unit = "kg/m2"

                # Higher confidence in Vitals section
                confidence = 0.9 if section == ClinicalSection.VITAL_SIGNS else 0.8

                entity = ExtractedEntity(
                    id=str(uuid4()),
                    entity_type=EntityType.VITAL_SIGN,
                    text=span.text,
                    normalized_text=vital_name.replace("_", " ").title(),
                    span=span,
                    section=section,
                    assertion=AssertionStatus.PRESENT,
                    confidence=confidence,
                    value=value,
                    unit=unit,
                )
                entities.append(entity)

        return entities

    def _extract_lab_results(
        self, text: str, sections: list[SectionSpan]
    ) -> list[ExtractedEntity]:
        """Extract lab result entities with values, units, and reference ranges."""
        entities: list[ExtractedEntity] = []

        for pattern, lab_name, default_unit, ref_range in self.LAB_RESULT_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                span = EntitySpan(
                    start=match.start(),
                    end=match.end(),
                    text=text[match.start() : match.end()],
                )
                section = self._get_section_at_offset(match.start(), sections)

                value = match.group(1)
                unit = match.group(2) if match.lastindex >= 2 and match.group(2) else default_unit

                # Higher confidence in Labs section
                confidence = 0.9 if section == ClinicalSection.LABS else 0.8

                entity = ExtractedEntity(
                    id=str(uuid4()),
                    entity_type=EntityType.LAB_RESULT,
                    text=span.text,
                    normalized_text=lab_name.upper(),
                    span=span,
                    section=section,
                    assertion=AssertionStatus.PRESENT,
                    confidence=confidence,
                    value=value,
                    unit=unit,
                    reference_range=ref_range,
                )
                entities.append(entity)

        return entities

    def _extract_anatomical_locations(
        self, text: str, sections: list[SectionSpan]
    ) -> list[ExtractedEntity]:
        """Extract anatomical location entities with laterality."""
        entities: list[ExtractedEntity] = []

        for pattern, _ in self.ANATOMICAL_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                span = EntitySpan(
                    start=match.start(),
                    end=match.end(),
                    text=text[match.start() : match.end()],
                )
                section = self._get_section_at_offset(match.start(), sections)

                # Detect laterality
                laterality = None
                for lat_pattern, lat_value in self.LATERALITY_PATTERNS:
                    if re.search(lat_pattern, span.text, re.IGNORECASE):
                        laterality = lat_value
                        break

                entity = ExtractedEntity(
                    id=str(uuid4()),
                    entity_type=EntityType.ANATOMICAL_LOCATION,
                    text=span.text,
                    normalized_text=span.text.title(),
                    span=span,
                    section=section,
                    assertion=AssertionStatus.PRESENT,
                    confidence=0.75,
                    laterality=laterality,
                )
                entities.append(entity)

        return entities

    def _extract_temporal_expressions(
        self, text: str, sections: list[SectionSpan]
    ) -> list[ExtractedEntity]:
        """Extract temporal expression entities."""
        entities: list[ExtractedEntity] = []

        for pattern, temporal_type in self.TEMPORAL_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                span = EntitySpan(
                    start=match.start(),
                    end=match.end(),
                    text=text[match.start() : match.end()],
                )
                section = self._get_section_at_offset(match.start(), sections)

                entity = ExtractedEntity(
                    id=str(uuid4()),
                    entity_type=EntityType.TEMPORAL,
                    text=span.text,
                    normalized_text=temporal_type,
                    span=span,
                    section=section,
                    assertion=AssertionStatus.PRESENT,
                    confidence=0.85,
                )
                entities.append(entity)

        return entities

    def _apply_negation_detection(
        self, text: str, entities: list[ExtractedEntity]
    ) -> list[ExtractedEntity]:
        """Apply negation detection to entities using NegEx-style algorithm."""
        text_lower = text.lower()

        for entity in entities:
            # Get preceding context (50 chars before entity)
            context_start = max(0, entity.span.start - 50)
            preceding_context = text_lower[context_start : entity.span.start]

            # Check for family history context
            for pattern in self._family_history_regexes:
                if pattern.search(preceding_context):
                    entity.assertion = AssertionStatus.FAMILY_HISTORY
                    break

            if entity.assertion == AssertionStatus.FAMILY_HISTORY:
                continue

            # Check for uncertainty triggers
            for pattern in self._uncertainty_regexes:
                match = pattern.search(preceding_context)
                if match:
                    entity.assertion = AssertionStatus.POSSIBLE
                    entity.negation_trigger = match.group(0)
                    break

            if entity.assertion == AssertionStatus.POSSIBLE:
                continue

            # Check for negation triggers
            for pattern in self._negation_regexes:
                match = pattern.search(preceding_context)
                if match:
                    entity.assertion = AssertionStatus.ABSENT
                    entity.negation_trigger = match.group(0)
                    entity.negation_scope_start = context_start + match.start()
                    entity.negation_scope_end = entity.span.end
                    break

        return entities

    def _calculate_confidence(
        self,
        matched_text: str,
        normalized_text: str,
        section: ClinicalSection,
        entity_type: EntityType,
    ) -> float:
        """Calculate confidence score for an extraction."""
        base_confidence = 0.7

        # Bonus for longer matches (more specific)
        length_bonus = min(0.1, len(matched_text) / 100)
        base_confidence += length_bonus

        # Section-specific bonuses
        section_bonuses = {
            (EntityType.DIAGNOSIS, ClinicalSection.ASSESSMENT): 0.1,
            (EntityType.DIAGNOSIS, ClinicalSection.PAST_MEDICAL_HISTORY): 0.1,
            (EntityType.MEDICATION, ClinicalSection.MEDICATIONS): 0.1,
            (EntityType.SYMPTOM, ClinicalSection.HPI): 0.1,
            (EntityType.SYMPTOM, ClinicalSection.ROS): 0.1,
            (EntityType.PROCEDURE, ClinicalSection.PAST_SURGICAL_HISTORY): 0.1,
            (EntityType.VITAL_SIGN, ClinicalSection.VITAL_SIGNS): 0.1,
            (EntityType.LAB_RESULT, ClinicalSection.LABS): 0.1,
        }

        bonus = section_bonuses.get((entity_type, section), 0)
        base_confidence += bonus

        return min(1.0, base_confidence)

    def _deduplicate_entities(
        self, entities: list[ExtractedEntity]
    ) -> list[ExtractedEntity]:
        """Remove duplicate entities based on span overlap."""
        if not entities:
            return entities

        # Sort by start position, then by confidence (descending)
        entities.sort(key=lambda e: (e.span.start, -e.confidence))

        deduplicated: list[ExtractedEntity] = []
        for entity in entities:
            # Check for overlap with existing entities
            overlaps = False
            for existing in deduplicated:
                if (
                    entity.span.start < existing.span.end
                    and entity.span.end > existing.span.start
                ):
                    overlaps = True
                    break

            if not overlaps:
                deduplicated.append(entity)

        return deduplicated

    def _merge_entities(
        self,
        rule_entities: list[ExtractedEntity],
        ml_entities: list[ExtractedEntity],
    ) -> list[ExtractedEntity]:
        """Merge entities from rule-based and ML extractions."""
        # Simple merge: prefer ML entities when there's overlap
        merged = list(ml_entities)

        for rule_entity in rule_entities:
            overlaps = False
            for ml_entity in ml_entities:
                if (
                    rule_entity.span.start < ml_entity.span.end
                    and rule_entity.span.end > ml_entity.span.start
                ):
                    overlaps = True
                    break

            if not overlaps:
                merged.append(rule_entity)

        return merged

    def normalize_entity(
        self,
        entity: ExtractedEntity,
        vocabularies: list[NormalizationVocabulary] | None = None,
    ) -> NormalizationResult:
        """Normalize an entity to standard vocabulary codes.

        Args:
            entity: The entity to normalize.
            vocabularies: Optional list of vocabularies to use. If None, uses defaults.

        Returns:
            NormalizationResult with matched codes.
        """
        start_time = time.perf_counter()

        if vocabularies is None:
            # Default vocabularies based on entity type
            vocab_map = {
                EntityType.DIAGNOSIS: [NormalizationVocabulary.SNOMED_CT, NormalizationVocabulary.ICD10_CM],
                EntityType.SYMPTOM: [NormalizationVocabulary.SNOMED_CT],
                EntityType.MEDICATION: [NormalizationVocabulary.RXNORM, NormalizationVocabulary.NDC],
                EntityType.PROCEDURE: [NormalizationVocabulary.CPT, NormalizationVocabulary.ICD10_PCS],
                EntityType.LAB_RESULT: [NormalizationVocabulary.LOINC],
                EntityType.VITAL_SIGN: [NormalizationVocabulary.LOINC],
                EntityType.ANATOMICAL_LOCATION: [NormalizationVocabulary.SNOMED_CT],
            }
            vocabularies = vocab_map.get(entity.entity_type, [NormalizationVocabulary.SNOMED_CT])

        # Mock normalization - in production, would query vocabulary services
        normalized_codes = self._mock_normalize(entity, vocabularies)

        processing_time = (time.perf_counter() - start_time) * 1000

        return NormalizationResult(
            entity_id=entity.id,
            original_text=entity.text,
            normalized_codes=normalized_codes,
            best_match=normalized_codes[0] if normalized_codes else None,
            processing_time_ms=round(processing_time, 2),
        )

    def _mock_normalize(
        self,
        entity: ExtractedEntity,
        vocabularies: list[NormalizationVocabulary],
    ) -> list[NormalizedCode]:
        """Mock normalization for demonstration."""
        # In production, this would query actual vocabulary services
        mock_codes: dict[str, dict[str, tuple[str, str]]] = {
            "Diabetes": {
                "SNOMED-CT": ("73211009", "Diabetes mellitus"),
                "ICD-10-CM": ("E11.9", "Type 2 diabetes mellitus without complications"),
            },
            "Hypertension": {
                "SNOMED-CT": ("38341003", "Hypertensive disorder"),
                "ICD-10-CM": ("I10", "Essential (primary) hypertension"),
            },
            "Heart Failure": {
                "SNOMED-CT": ("84114007", "Heart failure"),
                "ICD-10-CM": ("I50.9", "Heart failure, unspecified"),
            },
            "Metformin": {
                "RxNorm": ("6809", "metformin"),
            },
            "Lisinopril": {
                "RxNorm": ("29046", "lisinopril"),
            },
            "Chest Pain": {
                "SNOMED-CT": ("29857009", "Chest pain"),
            },
            "Fever": {
                "SNOMED-CT": ("386661006", "Fever"),
            },
        }

        codes: list[NormalizedCode] = []
        normalized_text = entity.normalized_text

        if normalized_text in mock_codes:
            for vocab in vocabularies:
                vocab_key = vocab.value
                if vocab_key in mock_codes[normalized_text]:
                    code, display = mock_codes[normalized_text][vocab_key]
                    codes.append(
                        NormalizedCode(
                            code=code,
                            display=display,
                            system=vocab,
                            confidence=0.9,
                            is_preferred=len(codes) == 0,
                        )
                    )

        return codes

    def get_available_models(self) -> list[NLPModelInfo]:
        """Get list of available NLP models."""
        models = [
            NLPModelInfo(
                model_id="rule_based",
                name="Rule-Based Extractor",
                description="Pattern-based clinical entity extraction using regex and clinical rules",
                entity_types=list(EntityType),
                is_available=True,
                version="1.0.0",
            ),
        ]

        # Add registered ML models
        for model_id, model in self._ml_models.items():
            models.append(model.get_model_info())

        return models

    def register_ml_model(self, model_id: str, model: MLModelProtocol) -> None:
        """Register an ML model for entity extraction.

        Args:
            model_id: Unique identifier for the model.
            model: The ML model implementing MLModelProtocol.
        """
        self._ml_models[model_id] = model
        logger.info(f"Registered ML model: {model_id}")

    def get_stats(self) -> dict:
        """Get service statistics."""
        return {
            "registered_ml_models": len(self._ml_models),
            "available_entity_types": [e.value for e in EntityType],
            "negation_patterns": len(self.NEGATION_TRIGGERS),
            "diagnosis_patterns": len(self.DIAGNOSIS_PATTERNS),
            "medication_patterns": len(self.MEDICATION_PATTERNS),
            "procedure_patterns": len(self.PROCEDURE_PATTERNS),
            "lab_patterns": len(self.LAB_RESULT_PATTERNS),
            "vital_sign_patterns": len(self.VITAL_SIGN_PATTERNS),
        }


# ============================================================================
# Singleton Management
# ============================================================================

_nlp_entity_service: ClinicalNLPEntityService | None = None


def get_nlp_entity_service() -> ClinicalNLPEntityService:
    """Get the singleton NLP entity service instance."""
    global _nlp_entity_service
    if _nlp_entity_service is None:
        _nlp_entity_service = ClinicalNLPEntityService()
    return _nlp_entity_service


def reset_nlp_entity_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _nlp_entity_service
    _nlp_entity_service = None
