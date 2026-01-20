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

import json
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Protocol
from uuid import uuid4

logger = logging.getLogger(__name__)

# Fixture paths for clinical terminology data
FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures"
CLINICAL_ABBREVIATIONS_FILE = FIXTURES_DIR / "clinical_abbreviations.json"
LOINC_MEASUREMENTS_FILE = FIXTURES_DIR / "loinc_measurements.json"


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
        r"\blow\s+suspicion\s+for\b",
        r"\bno\s+suspicion\s+for\b",
        r"\blow\s+concern\s+for\b",
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
        # Common conditions - all use (?:...) non-capturing groups with \b on both sides
        (r"\b(?:(?:type\s*[12]?\s*)?diabet(?:es|ic)(?:\s+mellitus)?(?:\s+(?:with|without)\s+\w+)?)\b", "Diabetes"),
        (r"\b(?:hypertension|htn|high\s+blood\s+pressure)\b", "Hypertension"),
        (r"\b(?:(?:congestive\s+)?heart\s+failure|chf|hfref|hfpef)\b", "Heart Failure"),
        (r"\b(?:coronary\s+artery\s+disease|cad)\b", "Coronary Artery Disease"),
        (r"\b(?:atrial\s+fibrillation|afib|a\.?\s*fib)\b", "Atrial Fibrillation"),
        (r"\b(?:chronic\s+(?:kidney|renal)\s+disease|ckd)\s+(?:stage\s+)?(?:5|v|five)\b", "CKD Stage 5"),
        (r"\b(?:chronic\s+(?:kidney|renal)\s+disease|ckd)\s+(?:stage\s+)?(?:4|iv|four)\b", "CKD Stage 4"),
        (r"\b(?:chronic\s+(?:kidney|renal)\s+disease|ckd)\s+(?:stage\s+)?(?:3b?|iii|three)\b", "CKD Stage 3"),
        (r"\b(?:chronic\s+(?:kidney|renal)\s+disease|ckd)\s+(?:stage\s+)?(?:2|ii|two)\b", "CKD Stage 2"),
        (r"\b(?:chronic\s+(?:kidney|renal)\s+disease|ckd)\s+(?:stage\s+)?(?:1|i|one)\b", "CKD Stage 1"),
        (r"\b(?:esrd|eskd|end[\s-]?stage\s+(?:kidney|renal)\s+disease)\b", "End Stage Renal Disease"),
        (r"\b(?:chronic\s+(?:kidney|renal)\s+disease|ckd)\b", "Chronic Kidney Disease"),
        (r"\b(?:copd|chronic\s+obstructive\s+pulmonary\s+disease)\b", "COPD"),
        (r"\basthma\b", "Asthma"),
        (r"\bpneumonia\b", "Pneumonia"),
        (r"\b(?:stroke|cva|cerebrovascular\s+accident)\b", "Stroke"),
        (r"\b(?:mi|myocardial\s+infarction|heart\s+attack)\b", "Myocardial Infarction"),
        (r"\b(?:depression|major\s+depressive\s+disorder|mdd)\b", "Depression"),
        (r"\banxiety(?:\s+disorder)?\b", "Anxiety"),
        (r"\b(?:hyperlipidemia|dyslipidemia|high\s+cholesterol)\b", "Hyperlipidemia"),
        (r"\bhypothyroidism\b", "Hypothyroidism"),
        (r"\bhyperthyroidism\b", "Hyperthyroidism"),
        (r"\b(?:gerd|gastroesophageal\s+reflux)\b", "GERD"),
        (r"\b(?:osteoarthritis|oa)\b", "Osteoarthritis"),
        (r"\b(?:rheumatoid\s+arthritis|ra)\b", "Rheumatoid Arthritis"),
        (r"\bobesity\b", "Obesity"),
        (r"\b(?:sleep\s+apnea|osa|obstructive\s+sleep\s+apnea)\b", "Sleep Apnea"),
        (r"\b(?:dvt|deep\s+vein\s+thrombosis)\b", "Deep Vein Thrombosis"),
        (r"\b(?:pulmonary\s+embolism|pe)\b", "Pulmonary Embolism"),
        (r"\b(?:uti|urinary\s+tract\s+infection)\b", "Urinary Tract Infection"),
        (r"\bsepsis\b", "Sepsis"),
        (r"\b(?:cancer|malignancy|carcinoma|neoplasm)\b", "Cancer"),
        (r"\b(?:iron\s+deficiency\s+anemia|iron\s+deficiency\s+anaemia|ida)\b", "Iron Deficiency Anemia"),
        (r"\banemia\b", "Anemia"),
        (r"\b(?:viral\s+)?gastroenteritis\b", "Gastroenteritis"),
        (r"\b(?:syncope|fainting|fainted|passed\s+out|loss\s+of\s+consciousness)\b", "Syncope"),
        (r"\bdehydration\b", "Dehydration"),
        (r"\b(?:volume\s+depletion|hypovolemia)\b", "Volume Depletion"),
        (r"\b(?:orthostatic\s+hypotension|orthostatic\s+syncope|postural\s+hypotension)\b", "Orthostatic Hypotension"),
        # Neurological conditions
        (r"\b(?:peripheral\s+neuropathy|diabetic\s+neuropathy|neuropathy)\b", "Peripheral Neuropathy"),
        (r"\b(?:autonomic\s+neuropathy)\b", "Autonomic Neuropathy"),
        (r"\b(?:dementia|alzheimer(?:'?s)?(?:\s+disease)?)\b", "Dementia"),
        (r"\b(?:parkinson(?:'?s)?(?:\s+disease)?)\b", "Parkinson Disease"),
        (r"\b(?:multiple\s+sclerosis|ms)\b", "Multiple Sclerosis"),
        (r"\b(?:epilepsy|seizure\s+disorder)\b", "Epilepsy"),
        (r"\b(?:migraine(?:s)?)\b", "Migraine"),
        # Vascular conditions
        (r"\b(?:peripheral\s+(?:arterial|artery|vascular)\s+disease|pad|pvd)\b", "Peripheral Arterial Disease"),
        (r"\b(?:aortic\s+aneurysm|aaa)\b", "Aortic Aneurysm"),
        (r"\b(?:carotid\s+(?:stenosis|disease))\b", "Carotid Stenosis"),
        (r"\b(?:claudication|intermittent\s+claudication)\b", "Claudication"),
        (r"\b(?:varicose\s+veins)\b", "Varicose Veins"),
        (r"\b(?:chronic\s+venous\s+insufficiency|cvi)\b", "Chronic Venous Insufficiency"),
        # Infectious diseases
        (r"\b(?:osteomyelitis)\b", "Osteomyelitis"),
        (r"\b(?:cellulitis)\b", "Cellulitis"),
        (r"\b(?:abscess)\b", "Abscess"),
        (r"\b(?:bacteremia)\b", "Bacteremia"),
        (r"\b(?:endocarditis)\b", "Endocarditis"),
        (r"\b(?:meningitis)\b", "Meningitis"),
        (r"\b(?:encephalitis)\b", "Encephalitis"),
        (r"\b(?:wound\s+infection|infected\s+wound)\b", "Wound Infection"),
        (r"\b(?:diabetic\s+foot\s+infection|foot\s+infection)\b", "Diabetic Foot Infection"),
        (r"\b(?:skin\s+(?:and\s+)?soft\s+tissue\s+infection|ssti)\b", "Skin and Soft Tissue Infection"),
        (r"\b(?:necrotizing\s+fasciitis)\b", "Necrotizing Fasciitis"),
        (r"\b(?:gangrene)\b", "Gangrene"),
        (r"\b(?:covid(?:-?19)?|sars-cov-2|coronavirus)\b", "COVID-19"),
        (r"\b(?:influenza|flu)\b", "Influenza"),
        (r"\b(?:hepatitis\s*[abc]?)\b", "Hepatitis"),
        (r"\b(?:hiv|aids|human\s+immunodeficiency\s+virus)\b", "HIV"),
        # Diabetic complications
        (r"\b(?:diabetic\s+ketoacidosis|dka)\b", "Diabetic Ketoacidosis"),
        (r"\b(?:hyperglycemia|high\s+(?:blood\s+)?(?:sugar|glucose))\b", "Hyperglycemia"),
        (r"\b(?:hypoglycemia|low\s+(?:blood\s+)?(?:sugar|glucose))\b", "Hypoglycemia"),
        (r"\b(?:diabetic\s+retinopathy|retinopathy)\b", "Diabetic Retinopathy"),
        (r"\b(?:diabetic\s+nephropathy|nephropathy)\b", "Diabetic Nephropathy"),
        (r"\b(?:foot\s+ulcer|diabetic\s+(?:foot\s+)?ulcer|plantar\s+ulcer)\b", "Foot Ulcer"),
        (r"\b(?:hyperosmolar\s+(?:hyperglycemic\s+)?(?:state|syndrome)|hhs)\b", "Hyperosmolar Hyperglycemic State"),
        # Skin/wound conditions
        (r"\b(?:pressure\s+(?:ulcer|sore|injury)|decubitus(?:\s+ulcer)?|bedsore)\b", "Pressure Ulcer"),
        (r"\b(?:venous\s+(?:stasis\s+)?ulcer|venous\s+ulcer)\b", "Venous Ulcer"),
        (r"\b(?:arterial\s+ulcer)\b", "Arterial Ulcer"),
        (r"\b(?:skin\s+tear)\b", "Skin Tear"),
        (r"\b(?:dermatitis)\b", "Dermatitis"),
        (r"\b(?:eczema)\b", "Eczema"),
        (r"\b(?:psoriasis)\b", "Psoriasis"),
        # Renal conditions
        (r"\b(?:acute\s+kidney\s+injury|aki|acute\s+renal\s+failure|arf)\b", "Acute Kidney Injury"),
        (r"\b(?:end[\s-]?stage\s+(?:renal|kidney)\s+disease|esrd|eskd)\b", "End Stage Renal Disease"),
        (r"\b(?:nephrolithiasis|kidney\s+stone(?:s)?|renal\s+calcul(?:i|us))\b", "Kidney Stones"),
        (r"\b(?:hydronephrosis)\b", "Hydronephrosis"),
        (r"\b(?:pyelonephritis)\b", "Pyelonephritis"),
        (r"\b(?:glomerulonephritis)\b", "Glomerulonephritis"),
        # Hepatic/GI conditions
        (r"\b(?:cirrhosis|liver\s+cirrhosis)\b", "Cirrhosis"),
        (r"\b(?:fatty\s+liver|nafld|nash|hepatic\s+steatosis)\b", "Fatty Liver Disease"),
        (r"\b(?:pancreatitis)\b", "Pancreatitis"),
        (r"\b(?:cholecystitis)\b", "Cholecystitis"),
        (r"\b(?:cholelithiasis|gallstone(?:s)?)\b", "Cholelithiasis"),
        (r"\b(?:diverticulitis)\b", "Diverticulitis"),
        (r"\b(?:diverticulosis)\b", "Diverticulosis"),
        (r"\b(?:crohn(?:'?s)?(?:\s+disease)?)\b", "Crohn Disease"),
        (r"\b(?:ulcerative\s+colitis)\b", "Ulcerative Colitis"),
        (r"\b(?:irritable\s+bowel\s+syndrome|ibs)\b", "Irritable Bowel Syndrome"),
        (r"\b(?:gi\s+bleed(?:ing)?|gastrointestinal\s+(?:bleed(?:ing)?|hemorrhage))\b", "GI Bleeding"),
        (r"\b(?:peptic\s+ulcer(?:\s+disease)?|pud)\b", "Peptic Ulcer Disease"),
        (r"\b(?:gastric\s+ulcer)\b", "Gastric Ulcer"),
        (r"\b(?:duodenal\s+ulcer)\b", "Duodenal Ulcer"),
        (r"\b(?:bowel\s+obstruction|intestinal\s+obstruction|sbo|lbo)\b", "Bowel Obstruction"),
        (r"\b(?:ileus)\b", "Ileus"),
        (r"\b(?:ascites)\b", "Ascites"),
        (r"\b(?:hepatic\s+encephalopathy)\b", "Hepatic Encephalopathy"),
        # Hematologic conditions
        (r"\b(?:thrombocytopenia)\b", "Thrombocytopenia"),
        (r"\b(?:leukocytosis)\b", "Leukocytosis"),
        (r"\b(?:leukopenia|neutropenia)\b", "Leukopenia"),
        (r"\b(?:pancytopenia)\b", "Pancytopenia"),
        (r"\b(?:coagulopathy)\b", "Coagulopathy"),
        (r"\b(?:dic|disseminated\s+intravascular\s+coagulation)\b", "DIC"),
        # Electrolyte/metabolic disorders
        (r"\b(?:hyponatremia|low\s+sodium)\b", "Hyponatremia"),
        (r"\b(?:hypernatremia|high\s+sodium)\b", "Hypernatremia"),
        (r"\b(?:hypokalemia|low\s+potassium)\b", "Hypokalemia"),
        (r"\b(?:hyperkalemia|high\s+potassium)\b", "Hyperkalemia"),
        (r"\b(?:hypocalcemia|low\s+calcium)\b", "Hypocalcemia"),
        (r"\b(?:hypercalcemia|high\s+calcium)\b", "Hypercalcemia"),
        (r"\b(?:hypomagnesemia|low\s+magnesium)\b", "Hypomagnesemia"),
        (r"\b(?:metabolic\s+acidosis)\b", "Metabolic Acidosis"),
        (r"\b(?:metabolic\s+alkalosis)\b", "Metabolic Alkalosis"),
        (r"\b(?:respiratory\s+acidosis)\b", "Respiratory Acidosis"),
        (r"\b(?:respiratory\s+alkalosis)\b", "Respiratory Alkalosis"),
        (r"\b(?:lactic\s+acidosis)\b", "Lactic Acidosis"),
        # Cardiac conditions
        (r"\b(?:acute\s+coronary\s+syndrome|acs)\b", "Acute Coronary Syndrome"),
        (r"\b(?:unstable\s+angina|ua)\b", "Unstable Angina"),
        (r"\b(?:stable\s+angina|angina\s+pectoris)\b", "Stable Angina"),
        (r"\b(?:nstemi|non[\s-]?st[\s-]?elevation\s+mi)\b", "NSTEMI"),
        (r"\b(?:stemi|st[\s-]?elevation\s+mi)\b", "STEMI"),
        (r"\b(?:cardiomyopathy)\b", "Cardiomyopathy"),
        (r"\b(?:pericarditis)\b", "Pericarditis"),
        (r"\b(?:pericardial\s+effusion)\b", "Pericardial Effusion"),
        (r"\b(?:cardiac\s+tamponade|tamponade)\b", "Cardiac Tamponade"),
        (r"\b(?:aortic\s+stenosis|as)\b", "Aortic Stenosis"),
        (r"\b(?:aortic\s+regurgitation|ar|aortic\s+insufficiency)\b", "Aortic Regurgitation"),
        (r"\b(?:mitral\s+stenosis|ms)\b", "Mitral Stenosis"),
        (r"\b(?:mitral\s+regurgitation|mr|mitral\s+insufficiency)\b", "Mitral Regurgitation"),
        (r"\b(?:atrial\s+flutter)\b", "Atrial Flutter"),
        (r"\b(?:ventricular\s+tachycardia|vtach|vt)\b", "Ventricular Tachycardia"),
        (r"\b(?:ventricular\s+fibrillation|vfib|vf)\b", "Ventricular Fibrillation"),
        (r"\b(?:bradycardia)\b", "Bradycardia"),
        (r"\b(?:tachycardia)\b", "Tachycardia"),
        (r"\b(?:heart\s+block|av\s+block)\b", "Heart Block"),
        (r"\b(?:sick\s+sinus\s+syndrome)\b", "Sick Sinus Syndrome"),
        # Pulmonary conditions
        (r"\b(?:pulmonary\s+edema|flash\s+pulmonary\s+edema)\b", "Pulmonary Edema"),
        (r"\b(?:pleural\s+effusion)\b", "Pleural Effusion"),
        (r"\b(?:pneumothorax)\b", "Pneumothorax"),
        (r"\b(?:hemothorax)\b", "Hemothorax"),
        (r"\b(?:ards|acute\s+respiratory\s+distress\s+syndrome)\b", "ARDS"),
        (r"\b(?:respiratory\s+failure)\b", "Respiratory Failure"),
        (r"\b(?:pulmonary\s+fibrosis|ipf)\b", "Pulmonary Fibrosis"),
        (r"\b(?:bronchitis)\b", "Bronchitis"),
        (r"\b(?:bronchiectasis)\b", "Bronchiectasis"),
        (r"\b(?:lung\s+cancer)\b", "Lung Cancer"),
        # Musculoskeletal
        (r"\b(?:fracture)\b", "Fracture"),
        (r"\b(?:osteoporosis)\b", "Osteoporosis"),
        (r"\b(?:gout)\b", "Gout"),
        (r"\b(?:fibromyalgia)\b", "Fibromyalgia"),
        (r"\b(?:lupus|sle|systemic\s+lupus\s+erythematosus)\b", "Systemic Lupus Erythematosus"),
        (r"\b(?:spondylosis)\b", "Spondylosis"),
        (r"\b(?:spinal\s+stenosis)\b", "Spinal Stenosis"),
        (r"\b(?:disc\s+herniation|herniated\s+disc)\b", "Disc Herniation"),
        (r"\b(?:rotator\s+cuff\s+(?:tear|injury))\b", "Rotator Cuff Tear"),
        # Psychiatric
        (r"\b(?:bipolar\s+disorder)\b", "Bipolar Disorder"),
        (r"\b(?:schizophrenia)\b", "Schizophrenia"),
        (r"\b(?:ptsd|post[\s-]?traumatic\s+stress\s+disorder)\b", "PTSD"),
        (r"\b(?:ocd|obsessive[\s-]?compulsive\s+disorder)\b", "OCD"),
        (r"\b(?:adhd|attention\s+deficit)\b", "ADHD"),
        (r"\b(?:substance\s+(?:abuse|use\s+disorder)|sud)\b", "Substance Use Disorder"),
        (r"\b(?:alcohol(?:ism|\s+use\s+disorder|\s+abuse)?)\b", "Alcohol Use Disorder"),
        (r"\b(?:opioid\s+(?:use\s+disorder|abuse|dependence))\b", "Opioid Use Disorder"),
        # Other
        (r"\b(?:shock)\b", "Shock"),
        (r"\b(?:septic\s+shock)\b", "Septic Shock"),
        (r"\b(?:cardiogenic\s+shock)\b", "Cardiogenic Shock"),
        (r"\b(?:hypovolemic\s+shock)\b", "Hypovolemic Shock"),
        (r"\b(?:anaphylaxis|anaphylactic\s+shock)\b", "Anaphylaxis"),
        (r"\b(?:allergic\s+reaction)\b", "Allergic Reaction"),
        (r"\b(?:hypothermia)\b", "Hypothermia"),
        (r"\b(?:hyperthermia|heat\s+stroke)\b", "Hyperthermia"),
        (r"\b(?:malnutrition)\b", "Malnutrition"),
        (r"\b(?:failure\s+to\s+thrive)\b", "Failure to Thrive"),
        (r"\b(?:altered\s+mental\s+status|ams)\b", "Altered Mental Status"),
        (r"\b(?:encephalopathy)\b", "Encephalopathy"),
        (r"\b(?:delirium)\b", "Delirium"),
        (r"\b(?:coma)\b", "Coma"),
        (r"\b(?:benign\s+prostatic\s+hyperplasia|bph)\b", "Benign Prostatic Hyperplasia"),
        (r"\b(?:urinary\s+retention)\b", "Urinary Retention"),
        (r"\b(?:chronic\s+pain)\b", "Chronic Pain"),
        (r"\b(?:neuropathic\s+pain)\b", "Neuropathic Pain"),
        (r"\b(?:falls?|fall\s+risk|recurrent\s+falls)\b", "Fall Risk"),
        (r"\b(?:frailty)\b", "Frailty"),
        (r"\b(?:cachexia)\b", "Cachexia"),
    ]

    # Symptom patterns
    SYMPTOM_PATTERNS = [
        (r"\b(?:fever|febrile)\b", "Fever"),
        (r"\bcough(?:ing)?\b", "Cough"),
        (r"\b(?:shortness\s+of\s+breath|sob|dyspnea)\b", "Shortness of Breath"),
        (r"\bchest\s+pain\b", "Chest Pain"),
        (r"\b(?:abdominal\s+pain|stomach\s+ache)\b", "Abdominal Pain"),
        (r"\b(?:headache|cephalgia)\b", "Headache"),
        (r"\bnausea\b", "Nausea"),
        (r"\b(?:vomiting|emesis)\b", "Vomiting"),
        (r"\b(?:diarrhea|diarrhoea)\b", "Diarrhea"),
        (r"\bconstipation\b", "Constipation"),
        (r"\b(?:fatigue|tiredness)\b", "Fatigue"),
        (r"\b(?:dizziness|vertigo|dizzy)\b", "Dizziness"),
        (r"\b(?:lightheaded(?:ness)?|light[\s-]?headed(?:ness)?)\b", "Lightheadedness"),
        (r"\btunnel\s+vision\b", "Tunnel Vision"),
        (r"\b(?:pre[\s-]?syncope|presyncope|near\s+syncope|near\s+fainting)\b", "Presyncope"),
        (r"\b(?:blurred\s+vision|blurry\s+vision|vision\s+changes?)\b", "Vision Changes"),
        (r"\bpalpitations\b", "Palpitations"),
        (r"\b(?:edema|swelling)\b", "Edema"),
        (r"\brash\b", "Rash"),
        (r"\b(?:itching|pruritus)\b", "Itching"),
        (r"\bweight\s+(?:loss|gain)\b", "Weight Change"),
        (r"\binsomnia\b", "Insomnia"),
        (r"\b(?:joint\s+pain|arthralgia)\b", "Joint Pain"),
        (r"\bback\s+pain\b", "Back Pain"),
        (r"\bneck\s+pain\b", "Neck Pain"),
        (r"\bweakness\b", "Weakness"),
        (r"\b(?:numbness|paresthesia)\b", "Numbness"),
        (r"\bconfusion\b", "Confusion"),
        (r"\b(?:loss\s+of\s+consciousness|loc|passed\s+out|passing\s+out|faint(?:ed|ing)?)\b", "Loss of Consciousness"),
        (r"\b(?:seizure[\s-]?like\s+activity|convulsion)\b", "Seizure-like Activity"),
        (r"\btongue\s+bite\b", "Tongue Bite"),
        (r"\bincontinence\b", "Incontinence"),
        (r"\b(?:post[\s-]?ictal\s+confusion|post[\s-]?ictal)\b", "Post-ictal State"),
        (r"\b(?:poor\s+)?(?:oral|po)\s+intake\b", "Poor Oral Intake"),
        # Additional symptoms from clinical notes
        (r"\b(?:chills?|rigor(?:s)?)\b", "Chills"),
        (r"\b(?:purulent\s+)?drainage\b", "Drainage"),
        (r"\berythema\b", "Erythema"),
        (r"\bwarmth\b", "Warmth"),
        (r"\b(?:foul\s+)?odor\b", "Foul Odor"),
        (r"\b(?:sore\s+throat|pharyngitis)\b", "Sore Throat"),
        (r"\b(?:runny\s+nose|rhinorrhea)\b", "Rhinorrhea"),
        (r"\b(?:nasal\s+congestion|congestion)\b", "Nasal Congestion"),
        (r"\b(?:wheezing|wheeze)\b", "Wheezing"),
        (r"\bstridor\b", "Stridor"),
        (r"\b(?:chest\s+tightness)\b", "Chest Tightness"),
        (r"\b(?:hemoptysis|coughing\s+(?:up\s+)?blood)\b", "Hemoptysis"),
        (r"\b(?:melena|black\s+(?:tarry\s+)?stool(?:s)?)\b", "Melena"),
        (r"\b(?:hematochezia|blood(?:y)?\s+stool(?:s)?|rectal\s+bleed(?:ing)?)\b", "Hematochezia"),
        (r"\b(?:hematuria|blood(?:y)?\s+urine)\b", "Hematuria"),
        (r"\b(?:dysuria|painful\s+urination)\b", "Dysuria"),
        (r"\b(?:urinary\s+)?frequency\b", "Urinary Frequency"),
        (r"\b(?:urinary\s+)?urgency\b", "Urinary Urgency"),
        (r"\blethargy\b", "Lethargy"),
        (r"\bmalaise\b", "Malaise"),
        (r"\b(?:night\s+sweats)\b", "Night Sweats"),
        (r"\b(?:anorexia|loss\s+of\s+appetite|decreased\s+appetite)\b", "Anorexia"),
        (r"\b(?:polydipsia|excessive\s+thirst)\b", "Polydipsia"),
        (r"\b(?:polyuria|frequent\s+urination)\b", "Polyuria"),
        (r"\b(?:polyphagia|excessive\s+hunger)\b", "Polyphagia"),
        (r"\b(?:diplopia|double\s+vision)\b", "Diplopia"),
        (r"\b(?:photophobia|light\s+sensitivity)\b", "Photophobia"),
        (r"\b(?:tinnitus|ringing\s+in\s+(?:the\s+)?ears?)\b", "Tinnitus"),
        (r"\b(?:hearing\s+loss)\b", "Hearing Loss"),
        (r"\b(?:tremor(?:s)?)\b", "Tremor"),
        (r"\bataxia\b", "Ataxia"),
        (r"\bdysarthria\b", "Dysarthria"),
        (r"\b(?:dysphagia|difficulty\s+swallowing)\b", "Dysphagia"),
        (r"\b(?:odynophagia|painful\s+swallowing)\b", "Odynophagia"),
        (r"\bhiccups?\b", "Hiccups"),
        (r"\b(?:abdominal\s+)?distension\b", "Abdominal Distension"),
        (r"\b(?:flank\s+pain)\b", "Flank Pain"),
        (r"\b(?:tenderness)\b", "Tenderness"),
        (r"\b(?:guarding)\b", "Guarding"),
        (r"\b(?:rebound\s+tenderness|rebound)\b", "Rebound Tenderness"),
        (r"\b(?:jaundice|icterus|yellow\s+skin)\b", "Jaundice"),
        (r"\b(?:cyanosis|blue\s+(?:skin|lips))\b", "Cyanosis"),
        (r"\b(?:pallor|pale)\b", "Pallor"),
        (r"\b(?:petechiae)\b", "Petechiae"),
        (r"\b(?:purpura)\b", "Purpura"),
        (r"\b(?:ecchymosis|bruising)\b", "Ecchymosis"),
        (r"\b(?:hives|urticaria)\b", "Urticaria"),
        (r"\b(?:angioedema)\b", "Angioedema"),
        (r"\b(?:clubbing)\b", "Clubbing"),
        (r"\b(?:crepitus)\b", "Crepitus"),
        (r"\b(?:muscle\s+(?:ache|pain)|myalgia)\b", "Myalgia"),
        (r"\b(?:bone\s+pain)\b", "Bone Pain"),
        (r"\b(?:radicular\s+pain|radiculopathy)\b", "Radicular Pain"),
        (r"\b(?:sciatica)\b", "Sciatica"),
        (r"\b(?:stiffness)\b", "Stiffness"),
        (r"\b(?:morning\s+stiffness)\b", "Morning Stiffness"),
        (r"\b(?:limited\s+(?:range\s+of\s+)?motion|rom)\b", "Limited Range of Motion"),
        (r"\b(?:focal\s+neurological\s+deficit(?:s)?|focal\s+neuro\s+deficit)\b", "Focal Neurological Deficit"),
        (r"\b(?:aphasia)\b", "Aphasia"),
        (r"\b(?:facial\s+droop(?:ing)?)\b", "Facial Droop"),
        (r"\b(?:hemiparesis|hemiplegia)\b", "Hemiparesis"),
        (r"\b(?:quadriparesis|quadriplegia)\b", "Quadriparesis"),
        (r"\b(?:paraparesis|paraplegia)\b", "Paraparesis"),
        (r"\b(?:foot\s+drop)\b", "Foot Drop"),
        (r"\b(?:wrist\s+drop)\b", "Wrist Drop"),
        (r"\b(?:hyperreflexia)\b", "Hyperreflexia"),
        (r"\b(?:hyporeflexia|areflexia)\b", "Hyporeflexia"),
        (r"\b(?:clonus)\b", "Clonus"),
        (r"\b(?:babinski(?:\s+sign)?|upgoing\s+toes?)\b", "Babinski Sign"),
        # Emergency/critical symptoms
        (r"\b(?:unresponsive|unresponsiveness)\b", "Unresponsive"),
        (r"\b(?:apnea|apneic|apnoea|apnoeic)\b", "Apnea"),
        (r"\b(?:nauseated|feeling\s+sick)\b", "Nauseated"),
        (r"\b(?:diaphoretic|sweating|sweaty)\b", "Diaphoresis"),
        (r"\b(?:irritable|irritability)\b", "Irritability"),
        (r"\b(?:restless(?:ness)?|agitated|agitation)\b", "Restlessness"),
        (r"\b(?:altered\s+mental\s+status|ams)\b", "Altered Mental Status"),
        (r"\b(?:decreased\s+(?:loc|level\s+of\s+consciousness))\b", "Decreased Level of Consciousness"),
        (r"\b(?:obtunded)\b", "Obtunded"),
        (r"\b(?:somnolent|somnolence)\b", "Somnolence"),
        (r"\b(?:stupor(?:ous)?)\b", "Stupor"),
        (r"\b(?:comatose|coma)\b", "Coma"),
        (r"\b(?:bradypnea|bradypneic)\b", "Bradypnea"),
        (r"\b(?:tachypnea|tachypneic)\b", "Tachypnea"),
        (r"\b(?:hypoxic|hypoxia)\b", "Hypoxia"),
        (r"\b(?:cyanotic)\b", "Cyanotic"),
        (r"\b(?:respiratory\s+distress)\b", "Respiratory Distress"),
        (r"\b(?:respiratory\s+depression)\b", "Respiratory Depression"),
        (r"\b(?:tachycardic)\b", "Tachycardia"),
        (r"\b(?:bradycardic)\b", "Bradycardia"),
        (r"\b(?:hypotensive)\b", "Hypotension"),
        (r"\b(?:hypertensive)\b", "Hypertension"),
        (r"\b(?:trauma(?:tic)?)\b", "Trauma"),
        (r"\b(?:self[\s-]?harm)\b", "Self-harm"),
        (r"\b(?:overdose|od)\b", "Overdose"),
        (r"\b(?:intoxicated|intoxication)\b", "Intoxication"),
        (r"\b(?:withdrawal)\b", "Withdrawal"),
        (r"\b(?:seizing|convulsing)\b", "Active Seizure"),
        (r"\b(?:bleeding|hemorrhage|hemorrhaging)\b", "Bleeding"),
        (r"\b(?:pain(?:ful)?)\b", "Pain"),
        (r"\b(?:anxious|anxiety)\b", "Anxiety"),
        (r"\b(?:depressed)\b", "Depressed Mood"),
        (r"\b(?:suicidal(?:\s+ideation)?|si)\b", "Suicidal Ideation"),
        (r"\b(?:homicidal(?:\s+ideation)?|hi)\b", "Homicidal Ideation"),
    ]

    # Medication patterns
    MEDICATION_PATTERNS = [
        # Pattern: drug name followed by optional dosage, frequency, route
        # Diabetes medications
        r"\b(metformin|glucophage)\s*(?:(\d+(?:\.\d+)?\s*(?:mg|g)))?(?:\s+(daily|bid|tid|qid|qd|prn))?",
        r"\b(insulin\s+glargine|lantus|basaglar)\s*(?:(\d+(?:\.\d+)?\s*(?:units?|u)))?(?:\s+(nightly|daily|qhs))?",
        r"\b(insulin\s+lispro|humalog)\s*(?:(\d+(?:\.\d+)?\s*(?:units?|u)))?(?:\s+(with\s+meals|ac|tid))?",
        r"\b(insulin\s+aspart|novolog)\s*(?:(\d+(?:\.\d+)?\s*(?:units?|u)))?(?:\s+(with\s+meals|ac|tid))?",
        r"\b(insulin\s+regular|regular\s+insulin|humulin\s+r|novolin\s+r)\s*(?:(\d+(?:\.\d+)?\s*(?:units?|u)))?",
        r"\b(insulin\s+nph|nph\s+insulin|humulin\s+n)\s*(?:(\d+(?:\.\d+)?\s*(?:units?|u)))?",
        r"\b(insulin\s+detemir|levemir)\s*(?:(\d+(?:\.\d+)?\s*(?:units?|u)))?",
        r"\b(insulin\s+degludec|tresiba)\s*(?:(\d+(?:\.\d+)?\s*(?:units?|u)))?",
        r"\b(insulin(?:\s+(?:glargine|lispro|aspart|regular|nph|detemir|degludec))?)\s*(?:(\d+(?:\.\d+)?\s*(?:units?|u)))?",
        r"\b(glipizide|glucotrol)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
        r"\b(glyburide|diabeta|micronase)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
        r"\b(glimepiride|amaryl)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
        r"\b(sitagliptin|januvia)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
        r"\b(empagliflozin|jardiance)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
        r"\b(canagliflozin|invokana)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
        r"\b(dapagliflozin|farxiga)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
        r"\b(semaglutide|ozempic|wegovy|rybelsus)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(weekly|daily))?",
        r"\b(liraglutide|victoza|saxenda)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
        r"\b(pioglitazone|actos)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
        # Cardiovascular medications
        r"\b(lisinopril|prinivil|zestril)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid|qd))?",
        r"\b(atorvastatin|lipitor)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|qd|qhs))?",
        r"\b(amlodipine|norvasc)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|qd))?",
        r"\b(aspirin|asa)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|qd))?",
        r"\b(warfarin|coumadin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|qd))?",
        r"\b(furosemide|lasix)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
        r"\b(carvedilol|coreg)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(bid))?",
        r"\b(metoprolol(?:\s+(?:tartrate|succinate))?)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
        r"\b(clopidogrel|plavix)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
        r"\b(rosuvastatin|crestor)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
        r"\b(simvastatin|zocor)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|qhs))?",
        r"\b(pravastatin|pravachol)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
        r"\b(losartan|cozaar)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
        r"\b(valsartan|diovan)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
        r"\b(hydrochlorothiazide|hctz|microzide)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
        r"\b(spironolactone|aldactone)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
        r"\b(diltiazem|cardizem|tiazac)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid|tid))?",
        r"\b(verapamil|calan|isoptin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid|tid))?",
        r"\b(atenolol|tenormin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
        r"\b(propranolol|inderal)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid|tid))?",
        r"\b(bisoprolol|zebeta)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
        r"\b(digoxin|lanoxin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg|mcg)))?(?:\s+(daily))?",
        r"\b(amiodarone|cordarone|pacerone)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
        r"\b(isosorbide(?:\s+(?:mononitrate|dinitrate))?|imdur|isordil)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?",
        r"\b(nitroglycerin|nitro|ntg)\s*(?:(\d+(?:\.\d+)?\s*(?:mg|mcg)))?",
        r"\b(hydralazine|apresoline)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(tid|qid))?",
        r"\b(clonidine|catapres)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid|tid))?",
        r"\b(prazosin|minipress)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid|tid))?",
        r"\b(doxazosin|cardura)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
        r"\b(apixaban|eliquis)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(bid))?",
        r"\b(rivaroxaban|xarelto)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
        r"\b(dabigatran|pradaxa)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(bid))?",
        r"\b(enoxaparin|lovenox)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid|q12h))?",
        r"\b(heparin)\s*(?:(\d+(?:\.\d+)?\s*(?:units?|u)))?",
        # GI medications
        r"\b(omeprazole|prilosec)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid|qd))?",
        r"\b(pantoprazole|protonix)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
        r"\b(esomeprazole|nexium)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
        r"\b(lansoprazole|prevacid)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
        r"\b(famotidine|pepcid)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
        r"\b(ranitidine|zantac)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
        r"\b(sucralfate|carafate)\s*(?:(\d+(?:\.\d+)?\s*(?:g|mg)))?(?:\s+(qid|tid))?",
        r"\b(ondansetron|zofran)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(q\d+h|prn))?",
        r"\b(metoclopramide|reglan)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(qid|tid|prn))?",
        r"\b(promethazine|phenergan)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(q\d+h|prn))?",
        r"\b(docusate|colace)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
        r"\b(polyethylene\s+glycol|miralax|peg)\s*(?:(\d+(?:\.\d+)?\s*(?:g|ml)))?(?:\s+(daily))?",
        r"\b(lactulose)\s*(?:(\d+(?:\.\d+)?\s*(?:ml|g)))?(?:\s+(daily|bid|tid|qid))?",
        # Pain/Neurologic medications
        r"\b(acetaminophen|tylenol)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(q\d+h|prn))?",
        r"\b(ibuprofen|advil|motrin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(q\d+h|prn|tid))?",
        r"\b(naproxen|aleve|naprosyn)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(bid|prn))?",
        r"\b(hydrocodone|norco|vicodin)\s*(?:(\d+(?:[\/\-]\d+)?\s*(?:mg)))?(?:\s+(q\d+h|prn))?",
        r"\b(oxycodone|oxycontin|roxicodone|percocet)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(q\d+h|prn))?",
        r"\b(morphine|ms\s+contin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(q\d+h|prn))?",
        r"\b(fentanyl|duragesic)\s*(?:(\d+(?:\.\d+)?\s*(?:mcg|mcg/h)))?",
        r"\b(hydromorphone|dilaudid)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(q\d+h|prn))?",
        r"\b(tramadol|ultram)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(q\d+h|prn|tid|qid))?",
        r"\b(gabapentin|neurontin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(tid|bid|qhs))?",
        r"\b(pregabalin|lyrica)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(bid|tid))?",
        r"\b(duloxetine|cymbalta)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
        r"\b(amitriptyline|elavil)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(qhs|daily))?",
        r"\b(cyclobenzaprine|flexeril)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(tid|prn))?",
        r"\b(baclofen|lioresal)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(tid|qid))?",
        r"\b(tizanidine|zanaflex)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(q\d+h|tid|prn))?",
        # Thyroid
        r"\b(levothyroxine|synthroid|levoxyl)\s*(?:(\d+(?:\.\d+)?\s*(?:mcg|mg)))?(?:\s+(daily))?",
        # Respiratory
        r"\b(albuterol|proventil|ventolin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg|puffs?)))?(?:\s+(q\d+h|prn))?",
        r"\b(ipratropium|atrovent)\s*(?:(\d+(?:\.\d+)?\s*(?:mcg|puffs?)))?(?:\s+(q\d+h|qid))?",
        r"\b(budesonide|pulmicort)\s*(?:(\d+(?:\.\d+)?\s*(?:mcg)))?(?:\s+(bid|daily))?",
        r"\b(fluticasone|flovent|flonase)\s*(?:(\d+(?:\.\d+)?\s*(?:mcg)))?(?:\s+(bid|daily))?",
        r"\b(montelukast|singulair)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|qhs))?",
        r"\b(prednisone)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|taper))?",
        r"\b(methylprednisolone|solu-?medrol)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?",
        r"\b(dexamethasone|decadron)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|q\d+h))?",
        # Psychiatric
        r"\b(sertraline|zoloft)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
        r"\b(fluoxetine|prozac)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
        r"\b(escitalopram|lexapro)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
        r"\b(citalopram|celexa)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
        r"\b(paroxetine|paxil)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
        r"\b(venlafaxine|effexor)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
        r"\b(bupropion|wellbutrin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
        r"\b(mirtazapine|remeron)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(qhs|daily))?",
        r"\b(trazodone|desyrel)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(qhs|prn))?",
        r"\b(quetiapine|seroquel)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid|qhs))?",
        r"\b(risperidone|risperdal)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
        r"\b(olanzapine|zyprexa)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|qhs))?",
        r"\b(aripiprazole|abilify)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
        r"\b(haloperidol|haldol)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid|prn))?",
        r"\b(lorazepam|ativan)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(q\d+h|prn|tid))?",
        r"\b(alprazolam|xanax)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(tid|prn))?",
        r"\b(clonazepam|klonopin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(bid|tid))?",
        r"\b(diazepam|valium)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(bid|tid|prn))?",
        r"\b(zolpidem|ambien)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(qhs|prn))?",
        # Antibiotics - IV and PO
        r"\b(vancomycin|vanc)\s*(?:(\d+(?:\.\d+)?\s*(?:mg|g)))?(?:\s+(?:iv|po|q\d+h))?",
        r"\b(piperacillin[\s/-]?tazobactam|pip[\s/-]?tazo?|zosyn)\s*(?:(\d+(?:\.\d+)?\s*(?:g)))?(?:\s+(?:iv|q\d+h))?",
        r"\b(ceftriaxone|rocephin)\s*(?:(\d+(?:\.\d+)?\s*(?:g|mg)))?(?:\s+(?:iv|im|daily))?",
        r"\b(cefepime|maxipime)\s*(?:(\d+(?:\.\d+)?\s*(?:g|mg)))?(?:\s+(?:iv|q\d+h))?",
        r"\b(cefazolin|ancef|kefzol)\s*(?:(\d+(?:\.\d+)?\s*(?:g|mg)))?(?:\s+(?:iv|q\d+h))?",
        r"\b(cephalexin|keflex)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(qid|tid|bid))?",
        r"\b(cefdinir|omnicef)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
        r"\b(amoxicillin|amoxil)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(tid|bid))?",
        r"\b(amoxicillin[\s/-]?clavulanate|augmentin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(bid|tid))?",
        r"\b(ampicillin[\s/-]?sulbactam|unasyn)\s*(?:(\d+(?:\.\d+)?\s*(?:g)))?(?:\s+(?:iv|q\d+h))?",
        r"\b(azithromycin|zithromax|z[\s-]?pack)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
        r"\b(ciprofloxacin|cipro)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(bid|daily))?",
        r"\b(levofloxacin|levaquin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
        r"\b(moxifloxacin|avelox)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
        r"\b(metronidazole|flagyl)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(tid|bid|q\d+h))?",
        r"\b(doxycycline|vibramycin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(bid|daily))?",
        r"\b(trimethoprim[\s/-]?sulfamethoxazole|tmp[\s/-]?smx|bactrim|septra)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(bid))?",
        r"\b(nitrofurantoin|macrobid|macrodantin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(bid|qid))?",
        r"\b(clindamycin|cleocin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(tid|qid|q\d+h))?",
        r"\b(meropenem|merrem)\s*(?:(\d+(?:\.\d+)?\s*(?:g|mg)))?(?:\s+(?:iv|q\d+h))?",
        r"\b(ertapenem|invanz)\s*(?:(\d+(?:\.\d+)?\s*(?:g)))?(?:\s+(?:iv|daily))?",
        r"\b(imipenem[\s/-]?cilastatin|primaxin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(?:iv|q\d+h))?",
        r"\b(linezolid|zyvox)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(?:iv|po|bid))?",
        r"\b(daptomycin|cubicin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(?:iv|daily))?",
        r"\b(gentamicin|garamycin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(?:iv|q\d+h))?",
        r"\b(tobramycin|tobrex)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(?:iv|q\d+h))?",
        r"\b(fluconazole|diflucan)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
        r"\b(micafungin|mycamine)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(?:iv|daily))?",
        r"\b(caspofungin|cancidas)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(?:iv|daily))?",
        r"\b(voriconazole|vfend)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(bid))?",
        r"\b(acyclovir|valacyclovir|zovirax|valtrex)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid|tid))?",
        r"\b(oseltamivir|tamiflu)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(bid))?",
        # IV Fluids
        r"\b(iv\s+fluids?|intravenous\s+fluids?|ivf)\b",
        r"\b(normal\s+saline|ns|0\.9%?\s*(?:saline|nacl)|0\.9\s*ns)\b",
        r"\b(lactated\s+ringer(?:'?s)?|lr|ringer(?:'?s)?\s+lactate)\b",
        r"\b(d5(?:w|\s*1/2\s*ns|ns)?|dextrose\s+5%?)\b",
        r"\b(half\s+normal\s+saline|1/2\s*ns|0\.45%?\s*(?:saline|nacl))\b",
        r"\b(plasmalyte)\b",
        r"\b(albumin)\s*(?:(\d+(?:\.\d+)?\s*(?:%|g)))?",
        # Miscellaneous
        r"\b(potassium\s+chloride|kcl|k-?dur)\s*(?:(\d+(?:\.\d+)?\s*(?:meq|mg)))?",
        r"\b(magnesium(?:\s+(?:sulfate|oxide|chloride))?|mag\s+(?:sulfate|ox))\s*(?:(\d+(?:\.\d+)?\s*(?:g|mg|meq)))?",
        r"\b(calcium(?:\s+(?:carbonate|gluconate|chloride))?|tums)\s*(?:(\d+(?:\.\d+)?\s*(?:mg|g)))?",
        r"\b(sodium\s+bicarbonate|bicarb|nahco3)\s*(?:(\d+(?:\.\d+)?\s*(?:meq|mg)))?",
        r"\b(thiamine|vitamin\s+b1)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?",
        r"\b(folic\s+acid|folate)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?",
        r"\b(multivitamin|mvi)\s*(?:\s+(daily))?",
        r"\b(vitamin\s+d|cholecalciferol|ergocalciferol)\s*(?:(\d+(?:\.\d+)?\s*(?:iu|units?|mcg)))?",
        r"\b(iron(?:\s+(?:sulfate|gluconate))?|ferrous\s+(?:sulfate|gluconate))\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?",
        r"\b(epoetin|procrit|epogen|epo)\s*(?:(\d+(?:\.\d+)?\s*(?:units?|u)))?",
        r"\b(darbepoetin|aranesp)\s*(?:(\d+(?:\.\d+)?\s*(?:mcg)))?",
        r"\b(filgrastim|neupogen|g-?csf)\s*(?:(\d+(?:\.\d+)?\s*(?:mcg)))?",
        r"\b(allopurinol|zyloprim)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
        r"\b(colchicine|colcrys)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
        r"\b(tamsulosin|flomax)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
        r"\b(finasteride|proscar|propecia)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
        r"\b(sildenafil|viagra|revatio)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(prn|tid))?",
        r"\b(naloxone|narcan)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?",
        r"\b(flumazenil|romazicon)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?",
        r"\b(diphenhydramine|benadryl)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(q\d+h|prn))?",
        r"\b(hydroxyzine|vistaril|atarax)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(q\d+h|prn|tid))?",
        r"\b(cetirizine|zyrtec)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
        r"\b(loratadine|claritin)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily))?",
        r"\b(fexofenadine|allegra)\s*(?:(\d+(?:\.\d+)?\s*(?:mg)))?(?:\s+(daily|bid))?",
        r"\b(epinephrine|epi|epipen|adrenaline)\s*(?:(\d+(?:\.\d+)?\s*(?:mg|ml)))?",
        r"\b(norepinephrine|levophed|norepi)\s*(?:(\d+(?:\.\d+)?\s*(?:mcg)))?",
        r"\b(vasopressin|pitressin)\s*(?:(\d+(?:\.\d+)?\s*(?:units?|u)))?",
        r"\b(dopamine)\s*(?:(\d+(?:\.\d+)?\s*(?:mcg)))?",
        r"\b(dobutamine)\s*(?:(\d+(?:\.\d+)?\s*(?:mcg)))?",
        r"\b(phenylephrine|neosynephrine)\s*(?:(\d+(?:\.\d+)?\s*(?:mcg|mg)))?",
    ]

    # Procedure patterns
    PROCEDURE_PATTERNS = [
        # Cardiac procedures
        (r"\b(?:coronary\s+)?angiography|cath(?:eterization)?\b", "Cardiac Catheterization"),
        (r"\b(?:coronary\s+)?angioplasty|pci|ptca\b", "Coronary Angioplasty"),
        (r"\bcabg|coronary\s+(?:artery\s+)?bypass(?:\s+graft(?:ing)?)?\b", "CABG"),
        (r"\b(?:pacemaker|pacer|ppm)(?:\s+(?:implant(?:ation)?|insertion|placement))?\b", "Pacemaker Implantation"),
        (r"\b(?:icd|defibrillator)(?:\s+(?:implant(?:ation)?|insertion|placement))?\b", "ICD Implantation"),
        (r"\b(?:ablation)\b", "Cardiac Ablation"),
        (r"\b(?:cardioversion)\b", "Cardioversion"),
        (r"\b(?:echocardiogram|echo|tte|tee)\b", "Echocardiogram"),
        (r"\b(?:stress\s+test|exercise\s+tolerance\s+test|ett|treadmill\s+test)\b", "Stress Test"),
        # GI procedures
        (r"\bcolonoscopy\b", "Colonoscopy"),
        (r"\b(?:endoscopy|egd|esophagogastroduodenoscopy)\b", "Endoscopy"),
        (r"\bappendectomy\b", "Appendectomy"),
        (r"\bcholecystectomy\b", "Cholecystectomy"),
        (r"\b(?:paracentesis)\b", "Paracentesis"),
        (r"\b(?:thoracentesis)\b", "Thoracentesis"),
        (r"\b(?:ercp)\b", "ERCP"),
        # Surgical procedures
        (r"\bhysterectomy\b", "Hysterectomy"),
        (r"\b(?:c[\s-]?section|cesarean(?:\s+section)?)\b", "Cesarean Section"),
        (r"\b(?:joint\s+replacement|arthroplasty)\b", "Joint Replacement"),
        (r"\b(?:knee\s+replacement|tka)\b", "Total Knee Arthroplasty"),
        (r"\b(?:hip\s+replacement|tha)\b", "Total Hip Arthroplasty"),
        (r"\blaminectomy\b", "Laminectomy"),
        (r"\bspinal\s+fusion\b", "Spinal Fusion"),
        (r"\b(?:amputation)\b", "Amputation"),
        (r"\b(?:debridement)\b", "Debridement"),
        (r"\b(?:i\s*&\s*d|incision\s+and\s+drainage|incision\s+&\s+drainage)\b", "Incision and Drainage"),
        (r"\b(?:wound\s+care)\b", "Wound Care"),
        (r"\b(?:skin\s+graft(?:ing)?)\b", "Skin Grafting"),
        (r"\b(?:laparotomy|exploratory\s+laparotomy)\b", "Laparotomy"),
        (r"\b(?:laparoscopy|laparoscopic)\b", "Laparoscopy"),
        (r"\b(?:hernia\s+repair|herniorrhaphy)\b", "Hernia Repair"),
        (r"\b(?:mastectomy)\b", "Mastectomy"),
        (r"\b(?:thyroidectomy)\b", "Thyroidectomy"),
        (r"\b(?:nephrectomy)\b", "Nephrectomy"),
        (r"\b(?:prostatectomy)\b", "Prostatectomy"),
        (r"\b(?:tracheostomy|trach)\b", "Tracheostomy"),
        # Medical procedures
        (r"\b(?:dialysis|hemodialysis|hd|peritoneal\s+dialysis|pd)\b", "Dialysis"),
        (r"\b(?:chemotherapy|chemo)\b", "Chemotherapy"),
        (r"\b(?:radiation(?:\s+therapy)?|radiotherapy|xrt)\b", "Radiation Therapy"),
        (r"\b(?:surgery|surgical\s+(?:procedure|intervention))\b", "Surgery"),
        (r"\b(?:biopsy)\b", "Biopsy"),
        (r"\b(?:transfusion|blood\s+transfusion|prbc(?:s)?|ffp)\b", "Transfusion"),
        (r"\b(?:intubation)\b", "Intubation"),
        (r"\b(?:extubation)\b", "Extubation"),
        (r"\b(?:ventilation|mechanical\s+ventilation)\b", "Mechanical Ventilation"),
        (r"\b(?:cpr|cardiopulmonary\s+resuscitation)\b", "CPR"),
        (r"\b(?:lumbar\s+puncture|lp|spinal\s+tap)\b", "Lumbar Puncture"),
        (r"\b(?:central\s+line|central\s+venous\s+catheter|cvc|picc(?:\s+line)?)\b", "Central Line Insertion"),
        (r"\b(?:arterial\s+line|a[\s-]?line)\b", "Arterial Line"),
        (r"\b(?:foley(?:\s+catheter)?|urinary\s+catheter(?:ization)?)\b", "Urinary Catheterization"),
        (r"\b(?:ng\s+tube|nasogastric\s+tube)\b", "NG Tube Placement"),
        (r"\b(?:feeding\s+tube|peg(?:\s+tube)?|g[\s-]?tube)\b", "Feeding Tube Placement"),
        (r"\b(?:chest\s+tube|thoracostomy)\b", "Chest Tube Insertion"),
        # Imaging procedures/studies
        (r"\b(?:x[\s-]?ray|xray|radiograph)\b", "X-Ray"),
        (r"\b(?:ct(?:\s+scan)?|cat\s+scan|computed\s+tomography)\b", "CT Scan"),
        (r"\b(?:mri|magnetic\s+resonance\s+imaging)\b", "MRI"),
        (r"\b(?:ultrasound|us|sonogram|sonography)\b", "Ultrasound"),
        (r"\b(?:pet(?:\s+scan)?|positron\s+emission\s+tomography)\b", "PET Scan"),
        (r"\b(?:nuclear\s+(?:medicine\s+)?(?:study|scan)|bone\s+scan)\b", "Nuclear Medicine Scan"),
        (r"\b(?:angiogram)\b", "Angiogram"),
        (r"\b(?:venogram)\b", "Venogram"),
        (r"\b(?:doppler(?:\s+(?:ultrasound|study))?)\b", "Doppler Study"),
        (r"\b(?:ekg|ecg|electrocardiogram)\b", "EKG"),
        (r"\b(?:eeg|electroencephalogram)\b", "EEG"),
        (r"\b(?:emg|electromyography|nerve\s+conduction\s+study|ncs)\b", "EMG/NCS"),
        # Lab draws/cultures
        (r"\b(?:blood\s+cultur(?:e|es)?)\b", "Blood Culture"),
        (r"\b(?:urine\s+cultur(?:e|es)?|ucx)\b", "Urine Culture"),
        (r"\b(?:wound\s+cultur(?:e|es)?)\b", "Wound Culture"),
        (r"\b(?:sputum\s+cultur(?:e|es)?)\b", "Sputum Culture"),
        (r"\b(?:csf\s+(?:cultur(?:e|es)?|analysis))\b", "CSF Analysis"),
        (r"\b(?:stool\s+(?:cultur(?:e|es)?|(?:studies|sample)))\b", "Stool Culture"),
        (r"\b(?:blood\s+(?:draw|work)|labs|laboratory)\b", "Laboratory Testing"),
        (r"\b(?:urinalysis|ua)\b", "Urinalysis"),
        (r"\b(?:cbc|complete\s+blood\s+count)\b", "CBC"),
        (r"\b(?:bmp|basic\s+metabolic\s+panel)\b", "BMP"),
        (r"\b(?:cmp|comprehensive\s+metabolic\s+panel)\b", "CMP"),
        (r"\b(?:lipid\s+panel)\b", "Lipid Panel"),
        (r"\b(?:coagulation\s+(?:panel|studies)|pt/inr|ptt)\b", "Coagulation Studies"),
        (r"\b(?:abg|arterial\s+blood\s+gas)\b", "ABG"),
        (r"\b(?:vbg|venous\s+blood\s+gas)\b", "VBG"),
        (r"\b(?:troponin)\b", "Troponin"),
        (r"\b(?:bnp|brain\s+natriuretic\s+peptide)\b", "BNP"),
        (r"\b(?:d[\s-]?dimer)\b", "D-Dimer"),
        (r"\b(?:crp|c[\s-]?reactive\s+protein)\b", "CRP"),
        (r"\b(?:esr|sed\s+rate|sedimentation\s+rate)\b", "ESR"),
        (r"\b(?:lactate|lactic\s+acid)\b", "Lactate"),
        (r"\b(?:procalcitonin|pct)\b", "Procalcitonin"),
        # Consults
        (r"\b(?:consult(?:ation)?)\b", "Consultation"),
        (r"\b(?:podiatry(?:\s+consult)?)\b", "Podiatry Consult"),
        (r"\b(?:ortho(?:pedic)?(?:s)?(?:\s+consult)?)\b", "Orthopedic Consult"),
        (r"\b(?:cardiology(?:\s+consult)?)\b", "Cardiology Consult"),
        (r"\b(?:nephrology(?:\s+consult)?)\b", "Nephrology Consult"),
        (r"\b(?:pulmonology(?:\s+consult)?)\b", "Pulmonology Consult"),
        (r"\b(?:gi(?:\s+consult)?|gastroenterology(?:\s+consult)?)\b", "GI Consult"),
        (r"\b(?:neurology(?:\s+consult)?)\b", "Neurology Consult"),
        (r"\b(?:infectious\s+disease(?:s)?(?:\s+consult)?|id\s+consult)\b", "Infectious Disease Consult"),
        (r"\b(?:surgery(?:\s+consult)?|surgical\s+consult)\b", "Surgery Consult"),
        (r"\b(?:vascular(?:\s+surgery)?(?:\s+consult)?)\b", "Vascular Surgery Consult"),
        (r"\b(?:palliative\s+care(?:\s+consult)?)\b", "Palliative Care Consult"),
        (r"\b(?:social\s+work(?:\s+consult)?|sw\s+consult)\b", "Social Work Consult"),
        (r"\b(?:physical\s+therapy|pt(?:\s+consult)?)\b", "Physical Therapy"),
        (r"\b(?:occupational\s+therapy|ot(?:\s+consult)?)\b", "Occupational Therapy"),
        (r"\b(?:speech\s+(?:language\s+)?therapy|slp|st)\b", "Speech Therapy"),
        (r"\b(?:nutrition(?:\s+consult)?|dietitian(?:\s+consult)?|rd\s+consult)\b", "Nutrition Consult"),
        (r"\b(?:case\s+management|cm\s+consult)\b", "Case Management"),
        (r"\b(?:wound\s+care(?:\s+consult)?)\b", "Wound Care Consult"),
        # Discharge/disposition
        (r"\b(?:admit(?:ted)?|admission)\b", "Admission"),
        (r"\b(?:discharge(?:d)?)\b", "Discharge"),
        (r"\b(?:transfer(?:red)?)\b", "Transfer"),
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
        # CBC
        (
            r"\b(?:wbc|white\s+blood\s+cell(?:s)?(?:\s+count)?)\s*:?\s*([\d.]+)\s*(k/ul|k/µl|x10\^?9/l|×10\^?9/l)?",
            "wbc",
            "K/uL",
            "4.5-11.0",
        ),
        (
            r"\b(?:hemoglobin|hgb|hb)\s*:?\s*([\d.]+)\s*(g/dl|g/l)?",
            "hemoglobin",
            "g/dL",
            "12-17",
        ),
        (
            r"\b(?:hematocrit|hct)\s*:?\s*([\d.]+)\s*%?",
            "hematocrit",
            "%",
            "36-48",
        ),
        (
            r"\b(?:platelet(?:s)?|plt)\s*:?\s*([\d.]+)\s*(k/ul|k/µl|x10\^?9/l)?",
            "platelets",
            "K/uL",
            "150-400",
        ),
        (
            r"\b(?:mcv)\s*:?\s*([\d.]+)\s*(fl)?",
            "mcv",
            "fL",
            "80-100",
        ),
        (
            r"\b(?:mch)\s*:?\s*([\d.]+)\s*(pg)?",
            "mch",
            "pg",
            "27-33",
        ),
        (
            r"\b(?:mchc)\s*:?\s*([\d.]+)\s*(g/dl)?",
            "mchc",
            "g/dL",
            "32-36",
        ),
        (
            r"\b(?:rdw)\s*:?\s*([\d.]+)\s*%?",
            "rdw",
            "%",
            "11.5-14.5",
        ),
        # Metabolic panel
        (
            r"\b(?:glucose|blood\s+sugar|bs|fbs|fasting\s+glucose)\s*:?\s*([\d.]+)\s*(mg/dl|mmol/l)?",
            "glucose",
            "mg/dL",
            "70-100",
        ),
        (
            r"\b(?:sodium|na)\s*[:\-=]?\s*([\d.]+)\s*(meq/l|mmol/l)?",
            "sodium",
            "mEq/L",
            "136-145",
        ),
        (
            r"\b(?:potassium|k)\s*[:\-=]?\s*([\d.]+)\s*(meq/l|mmol/l)?",
            "potassium",
            "mEq/L",
            "3.5-5.0",
        ),
        (
            r"\b(?:chloride|cl)\s*[:\-=]?\s*([\d.]+)\s*(meq/l|mmol/l)?",
            "chloride",
            "mEq/L",
            "98-106",
        ),
        (
            r"\b(?:co2|bicarbonate|bicarb|hco3)\s*[:\-=]?\s*([\d.]+)\s*(meq/l|mmol/l)?",
            "co2",
            "mEq/L",
            "22-29",
        ),
        (
            r"\b(?:bun|blood\s+urea\s+nitrogen)\s*[:\-=]?\s*([\d.]+)\s*(mg/dl)?",
            "bun",
            "mg/dL",
            "7-20",
        ),
        (
            r"\b(?:creatinine|cr)\s*[:\-=]?\s*([\d.]+)\s*(mg/dl)?",
            "creatinine",
            "mg/dL",
            "0.7-1.3",
        ),
        (
            r"\b(?:egfr|gfr|estimated\s+gfr)\s*:?\s*([\d.]+)\s*(ml/min)?",
            "egfr",
            "mL/min",
            ">60",
        ),
        (
            r"\b(?:anion\s+gap|ag)\s*:?\s*([\d.]+)",
            "anion_gap",
            "mEq/L",
            "8-12",
        ),
        (
            r"\b(?:calcium|ca)\s*:?\s*([\d.]+)\s*(mg/dl)?",
            "calcium",
            "mg/dL",
            "8.5-10.5",
        ),
        (
            r"\b(?:magnesium|mag|mg)\s*:?\s*([\d.]+)\s*(mg/dl|meq/l)?",
            "magnesium",
            "mg/dL",
            "1.7-2.2",
        ),
        (
            r"\b(?:phosphorus|phos)\s*:?\s*([\d.]+)\s*(mg/dl)?",
            "phosphorus",
            "mg/dL",
            "2.5-4.5",
        ),
        # Liver function tests
        (
            r"\b(?:ast|sgot|aspartate\s+(?:amino)?transaminase)\s*:?\s*([\d.]+)\s*(u/l|iu/l)?",
            "ast",
            "U/L",
            "10-40",
        ),
        (
            r"\b(?:alt|sgpt|alanine\s+(?:amino)?transaminase)\s*:?\s*([\d.]+)\s*(u/l|iu/l)?",
            "alt",
            "U/L",
            "7-56",
        ),
        (
            r"\b(?:alk\s*phos|alkaline\s+phosphatase|alp)\s*:?\s*([\d.]+)\s*(u/l|iu/l)?",
            "alk_phos",
            "U/L",
            "44-147",
        ),
        (
            r"\b(?:total\s+bilirubin|t[\s-]?bili|tbili)\s*:?\s*([\d.]+)\s*(mg/dl)?",
            "total_bilirubin",
            "mg/dL",
            "0.1-1.2",
        ),
        (
            r"\b(?:direct\s+bilirubin|d[\s-]?bili|dbili)\s*:?\s*([\d.]+)\s*(mg/dl)?",
            "direct_bilirubin",
            "mg/dL",
            "0.0-0.3",
        ),
        (
            r"\b(?:albumin|alb)\s*:?\s*([\d.]+)\s*(g/dl)?",
            "albumin",
            "g/dL",
            "3.5-5.0",
        ),
        (
            r"\b(?:total\s+protein|tp)\s*:?\s*([\d.]+)\s*(g/dl)?",
            "total_protein",
            "g/dL",
            "6.0-8.3",
        ),
        (
            r"\b(?:ggt|gamma[\s-]?glutamyl\s+transferase)\s*:?\s*([\d.]+)\s*(u/l)?",
            "ggt",
            "U/L",
            "9-48",
        ),
        (
            r"\b(?:ldh|lactate\s+dehydrogenase)\s*:?\s*([\d.]+)\s*(u/l)?",
            "ldh",
            "U/L",
            "140-280",
        ),
        # Diabetes
        (
            r"\b(?:hba1c|hemoglobin\s+a1c|a1c|glycated\s+hemoglobin)\s*:?\s*([\d.]+)\s*%?",
            "hba1c",
            "%",
            "<5.7",
        ),
        # Lipid panel
        (
            r"\b(?:total\s+)?(?:cholesterol|chol)\s*:?\s*([\d.]+)\s*(mg/dl)?",
            "cholesterol",
            "mg/dL",
            "<200",
        ),
        (
            r"\b(?:ldl|low\s+density\s+lipoprotein)\s*:?\s*([\d.]+)\s*(mg/dl)?",
            "ldl",
            "mg/dL",
            "<100",
        ),
        (
            r"\b(?:hdl|high\s+density\s+lipoprotein)\s*:?\s*([\d.]+)\s*(mg/dl)?",
            "hdl",
            "mg/dL",
            ">40",
        ),
        (
            r"\b(?:triglycerides|tg)\s*:?\s*([\d.]+)\s*(mg/dl)?",
            "triglycerides",
            "mg/dL",
            "<150",
        ),
        # Thyroid
        (
            r"\b(?:tsh|thyroid\s+stimulating\s+hormone)\s*:?\s*([\d.]+)\s*(miu/l|uiu/ml)?",
            "tsh",
            "mIU/L",
            "0.4-4.0",
        ),
        (
            r"\b(?:free\s+t4|ft4)\s*:?\s*([\d.]+)\s*(ng/dl)?",
            "free_t4",
            "ng/dL",
            "0.8-1.8",
        ),
        (
            r"\b(?:free\s+t3|ft3)\s*:?\s*([\d.]+)\s*(pg/ml)?",
            "free_t3",
            "pg/mL",
            "2.3-4.2",
        ),
        # Coagulation
        (
            r"\b(?:inr|international\s+normalized\s+ratio)\s*:?\s*([\d.]+)",
            "inr",
            "",
            "0.9-1.1",
        ),
        (
            r"\b(?:pt|prothrombin\s+time)\s*:?\s*([\d.]+)\s*(sec(?:onds)?)?",
            "pt",
            "sec",
            "11-13.5",
        ),
        (
            r"\b(?:ptt|aptt|activated\s+partial\s+thromboplastin\s+time)\s*:?\s*([\d.]+)\s*(sec(?:onds)?)?",
            "ptt",
            "sec",
            "25-35",
        ),
        (
            r"\b(?:fibrinogen)\s*:?\s*([\d.]+)\s*(mg/dl)?",
            "fibrinogen",
            "mg/dL",
            "200-400",
        ),
        (
            r"\b(?:d[\s-]?dimer)\s*:?\s*([\d.]+)\s*(ng/ml|µg/l|mcg/l)?",
            "d_dimer",
            "ng/mL",
            "<500",
        ),
        # Cardiac markers
        (
            r"\b(?:bnp|b[\s-]?type\s+natriuretic\s+peptide)\s*:?\s*([\d.]+)\s*(pg/ml)?",
            "bnp",
            "pg/mL",
            "<100",
        ),
        (
            r"\b(?:troponin(?:\s+[it])?|tn[it])\s*:?\s*([\d.]+)\s*(ng/ml|ng/l)?",
            "troponin",
            "ng/mL",
            "<0.04",
        ),
        (
            r"\b(?:ck[\s-]?mb|creatine\s+kinase\s+mb)\s*:?\s*([\d.]+)\s*(ng/ml)?",
            "ck_mb",
            "ng/mL",
            "<5",
        ),
        # Inflammatory markers
        (
            r"\b(?:crp|c[\s-]?reactive\s+protein)\s*:?\s*([\d.]+)\s*(mg/l|mg/dl)?",
            "crp",
            "mg/L",
            "<10",
        ),
        (
            r"\b(?:esr|sed\s+rate|sedimentation\s+rate|erythrocyte\s+sedimentation\s+rate)\s*:?\s*([\d.]+)\s*(mm/hr)?",
            "esr",
            "mm/hr",
            "<20",
        ),
        (
            r"\b(?:procalcitonin|pct)\s*:?\s*([\d.]+)\s*(ng/ml)?",
            "procalcitonin",
            "ng/mL",
            "<0.1",
        ),
        (
            r"\b(?:lactate|lactic\s+acid)\s*:?\s*([\d.]+)\s*(mmol/l|mg/dl)?",
            "lactate",
            "mmol/L",
            "<2.0",
        ),
        # Urinalysis (qualitative/semi-quantitative indicators)
        (
            r"\b(?:urine\s+)?(?:ph)\s*:?\s*([\d.]+)",
            "urine_ph",
            "",
            "4.5-8.0",
        ),
        (
            r"\b(?:specific\s+gravity|sp\s*gr|sg)\s*:?\s*([\d.]+)",
            "specific_gravity",
            "",
            "1.005-1.030",
        ),
        # Blood gases
        (
            r"\b(?:ph)\s*:?\s*([\d.]+)",
            "ph",
            "",
            "7.35-7.45",
        ),
        (
            r"\b(?:pco2|paco2)\s*:?\s*([\d.]+)\s*(mmhg)?",
            "pco2",
            "mmHg",
            "35-45",
        ),
        (
            r"\b(?:po2|pao2)\s*:?\s*([\d.]+)\s*(mmhg)?",
            "po2",
            "mmHg",
            "80-100",
        ),
        (
            r"\b(?:base\s+excess|be)\s*:?\s*(-?[\d.]+)\s*(meq/l|mmol/l)?",
            "base_excess",
            "mEq/L",
            "-2 to +2",
        ),
        # Other
        (
            r"\b(?:ammonia|nh3)\s*:?\s*([\d.]+)\s*(µmol/l|mcmol/l|umol/l)?",
            "ammonia",
            "µmol/L",
            "15-45",
        ),
        (
            r"\b(?:uric\s+acid)\s*:?\s*([\d.]+)\s*(mg/dl)?",
            "uric_acid",
            "mg/dL",
            "3.5-7.2",
        ),
        (
            r"\b(?:ferritin)\s*:?\s*([\d.]+)\s*(ng/ml)?",
            "ferritin",
            "ng/mL",
            "12-300",
        ),
        (
            r"\b(?:iron|serum\s+iron)\s*:?\s*([\d.]+)\s*(µg/dl|mcg/dl|ug/dl)?",
            "iron",
            "µg/dL",
            "60-170",
        ),
        (
            r"\b(?:tibc|total\s+iron\s+binding\s+capacity)\s*:?\s*([\d.]+)\s*(µg/dl|mcg/dl)?",
            "tibc",
            "µg/dL",
            "250-400",
        ),
        (
            r"\b(?:transferrin\s+saturation|tsat)\s*:?\s*([\d.]+)\s*%?",
            "transferrin_sat",
            "%",
            "20-50",
        ),
        (
            r"\b(?:vitamin\s+b12|b12|cobalamin)\s*:?\s*([\d.]+)\s*(pg/ml)?",
            "vitamin_b12",
            "pg/mL",
            "200-900",
        ),
        (
            r"\b(?:folate|folic\s+acid)\s*:?\s*([\d.]+)\s*(ng/ml)?",
            "folate",
            "ng/mL",
            ">3.0",
        ),
        (
            r"\b(?:vitamin\s+d|25[\s-]?oh[\s-]?d|25\s+hydroxyvitamin\s+d)\s*:?\s*([\d.]+)\s*(ng/ml)?",
            "vitamin_d",
            "ng/mL",
            "30-100",
        ),
        (
            r"\b(?:lipase)\s*:?\s*([\d.]+)\s*(u/l)?",
            "lipase",
            "U/L",
            "0-160",
        ),
        (
            r"\b(?:amylase)\s*:?\s*([\d.]+)\s*(u/l)?",
            "amylase",
            "U/L",
            "28-100",
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

        # Terminology service references (lazy-loaded)
        self._rxnorm_service: Any = None
        self._snomed_service: Any = None
        self._icd10_service: Any = None
        self._cpt_service: Any = None

        # Clinical abbreviations and LOINC data (loaded from fixtures)
        self._clinical_abbreviations: dict[str, dict] = {}
        self._loinc_codes: dict[str, dict] = {}
        self._abbreviations_loaded = False

        logger.info("ClinicalNLPEntityService initialized")

    def _get_rxnorm_service(self) -> Any:
        """Lazy-load the RxNorm service."""
        if self._rxnorm_service is None:
            try:
                from app.services.rxnorm_service import get_rxnorm_service

                self._rxnorm_service = get_rxnorm_service()
                logger.debug("RxNorm service loaded")
            except ImportError as e:
                logger.warning(f"Could not load RxNorm service: {e}")
        return self._rxnorm_service

    def _get_snomed_service(self) -> Any:
        """Lazy-load the SNOMED service."""
        if self._snomed_service is None:
            try:
                from app.services.snomed_service import get_snomed_service

                self._snomed_service = get_snomed_service()
                logger.debug("SNOMED service loaded")
            except ImportError as e:
                logger.warning(f"Could not load SNOMED service: {e}")
        return self._snomed_service

    def _get_icd10_service(self) -> Any:
        """Lazy-load the ICD-10 suggester service."""
        if self._icd10_service is None:
            try:
                from app.services.icd10_suggester import get_icd10_suggester_service

                self._icd10_service = get_icd10_suggester_service()
                logger.debug("ICD-10 service loaded")
            except ImportError as e:
                logger.warning(f"Could not load ICD-10 service: {e}")
        return self._icd10_service

    def _get_cpt_service(self) -> Any:
        """Lazy-load the CPT suggester service."""
        if self._cpt_service is None:
            try:
                from app.services.cpt_suggester import get_cpt_suggester_service

                self._cpt_service = get_cpt_suggester_service()
                logger.debug("CPT service loaded")
            except ImportError as e:
                logger.warning(f"Could not load CPT service: {e}")
        return self._cpt_service

    def _load_clinical_abbreviations(self) -> None:
        """Load clinical abbreviations from fixture file."""
        if self._abbreviations_loaded:
            return

        # Load clinical abbreviations with OMOP concept IDs
        if CLINICAL_ABBREVIATIONS_FILE.exists():
            try:
                with open(CLINICAL_ABBREVIATIONS_FILE) as f:
                    data = json.load(f)
                    for term in data.get("terms", []):
                        name = term.get("name", "").lower()
                        self._clinical_abbreviations[name] = term
                        # Also index by synonyms
                        for syn in term.get("synonyms", []):
                            self._clinical_abbreviations[syn.lower()] = term
                logger.info(
                    f"Loaded {len(data.get('terms', []))} clinical abbreviations"
                )
            except Exception as e:
                logger.warning(f"Could not load clinical abbreviations: {e}")

        # Load LOINC measurements
        if LOINC_MEASUREMENTS_FILE.exists():
            try:
                with open(LOINC_MEASUREMENTS_FILE) as f:
                    data = json.load(f)
                    for concept in data.get("concepts", []):
                        code = concept.get("concept_code", "")
                        name = concept.get("concept_name", "").lower()
                        self._loinc_codes[name] = concept
                        self._loinc_codes[code] = concept
                        # Also index by synonyms
                        for syn in concept.get("synonyms", []):
                            if isinstance(syn, str):
                                self._loinc_codes[syn.lower()] = concept
                logger.info(f"Loaded {len(data.get('concepts', []))} LOINC codes")
            except Exception as e:
                logger.warning(f"Could not load LOINC measurements: {e}")

        self._abbreviations_loaded = True

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

            # Respect section/paragraph boundaries - don't let negation cross double newlines
            # This prevents "No headache" from negating entities in subsequent sections
            if "\n\n" in preceding_context:
                # Only use context after the last section boundary
                last_boundary = preceding_context.rfind("\n\n")
                preceding_context = preceding_context[last_boundary + 2:]

            # Also truncate at single newline for list items (- item)
            if "\n-" in preceding_context or "\n•" in preceding_context:
                last_newline = max(preceding_context.rfind("\n-"), preceding_context.rfind("\n•"))
                if last_newline >= 0:
                    preceding_context = preceding_context[last_newline + 1:]

            # For lab results, vitals, and procedures, truncate at any newline
            # This prevents "no ischemic changes" from negating lab values/procedures on the next line
            if entity.entity_type in (EntityType.LAB_RESULT, EntityType.VITAL_SIGN, EntityType.PROCEDURE):
                if "\n" in preceding_context:
                    last_newline = preceding_context.rfind("\n")
                    preceding_context = preceding_context[last_newline + 1:]

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
        """Remove duplicate entities based on span overlap.

        Prefers longer (more specific) matches over shorter ones.
        Among matches of same length, prefers diagnoses/medications/procedures
        over temporal/anatomical entities, then higher confidence.
        """
        if not entities:
            return entities

        # Entity type priority: diagnoses/meds/procedures > symptoms > labs/vitals > others
        type_priority = {
            EntityType.DIAGNOSIS: 0,
            EntityType.MEDICATION: 0,
            EntityType.PROCEDURE: 0,
            EntityType.SYMPTOM: 1,
            EntityType.LAB_RESULT: 2,
            EntityType.VITAL_SIGN: 2,
            EntityType.ALLERGY: 3,
            EntityType.ANATOMICAL_LOCATION: 4,
            EntityType.TEMPORAL: 5,
        }

        # Sort by: start position, then span length (descending, prefer longer),
        # then entity type priority, then confidence (descending)
        entities.sort(key=lambda e: (
            e.span.start,
            -(e.span.end - e.span.start),  # Longer spans first
            type_priority.get(e.entity_type, 10),  # Important types first
            -e.confidence
        ))

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

        # Use real terminology services for normalization
        normalized_codes = self._normalize_with_services(entity, vocabularies)

        processing_time = (time.perf_counter() - start_time) * 1000

        return NormalizationResult(
            entity_id=entity.id,
            original_text=entity.text,
            normalized_codes=normalized_codes,
            best_match=normalized_codes[0] if normalized_codes else None,
            processing_time_ms=round(processing_time, 2),
        )

    # Comprehensive clinical code mappings
    # Format: "Normalized Text": {"VOCABULARY": ("code", "display name")}
    CLINICAL_CODE_MAPPINGS: dict[str, dict[str, tuple[str, str]]] = {
        # ========================================================================
        # DIAGNOSES - SNOMED-CT and ICD-10-CM codes
        # ========================================================================
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
        "Coronary Artery Disease": {
            "SNOMED-CT": ("53741008", "Coronary arteriosclerosis"),
            "ICD-10-CM": ("I25.10", "Atherosclerotic heart disease of native coronary artery"),
        },
        "Atrial Fibrillation": {
            "SNOMED-CT": ("49436004", "Atrial fibrillation"),
            "ICD-10-CM": ("I48.91", "Unspecified atrial fibrillation"),
        },
        "Chronic Kidney Disease": {
            "SNOMED-CT": ("709044004", "Chronic kidney disease"),
            "ICD-10-CM": ("N18.9", "Chronic kidney disease, unspecified"),
        },
        "CKD Stage 1": {
            "SNOMED-CT": ("431855005", "Chronic kidney disease stage 1"),
            "ICD-10-CM": ("N18.1", "Chronic kidney disease, stage 1"),
        },
        "CKD Stage 2": {
            "SNOMED-CT": ("431856006", "Chronic kidney disease stage 2"),
            "ICD-10-CM": ("N18.2", "Chronic kidney disease, stage 2"),
        },
        "CKD Stage 3": {
            "SNOMED-CT": ("433144002", "Chronic kidney disease stage 3"),
            "ICD-10-CM": ("N18.3", "Chronic kidney disease, stage 3"),
        },
        "CKD Stage 4": {
            "SNOMED-CT": ("431857002", "Chronic kidney disease stage 4"),
            "ICD-10-CM": ("N18.4", "Chronic kidney disease, stage 4"),
        },
        "CKD Stage 5": {
            "SNOMED-CT": ("433146000", "Chronic kidney disease stage 5"),
            "ICD-10-CM": ("N18.5", "Chronic kidney disease, stage 5"),
        },
        "End Stage Renal Disease": {
            "SNOMED-CT": ("46177005", "End-stage renal disease"),
            "ICD-10-CM": ("N18.6", "End stage renal disease"),
        },
        "COPD": {
            "SNOMED-CT": ("13645005", "Chronic obstructive lung disease"),
            "ICD-10-CM": ("J44.9", "Chronic obstructive pulmonary disease, unspecified"),
        },
        "Asthma": {
            "SNOMED-CT": ("195967001", "Asthma"),
            "ICD-10-CM": ("J45.909", "Unspecified asthma, uncomplicated"),
        },
        "Pneumonia": {
            "SNOMED-CT": ("233604007", "Pneumonia"),
            "ICD-10-CM": ("J18.9", "Pneumonia, unspecified organism"),
        },
        "Stroke": {
            "SNOMED-CT": ("230690007", "Cerebrovascular accident"),
            "ICD-10-CM": ("I63.9", "Cerebral infarction, unspecified"),
        },
        "Myocardial Infarction": {
            "SNOMED-CT": ("22298006", "Myocardial infarction"),
            "ICD-10-CM": ("I21.9", "Acute myocardial infarction, unspecified"),
        },
        "Depression": {
            "SNOMED-CT": ("35489007", "Depressive disorder"),
            "ICD-10-CM": ("F32.9", "Major depressive disorder, single episode, unspecified"),
        },
        "Anxiety": {
            "SNOMED-CT": ("48694002", "Anxiety"),
            "ICD-10-CM": ("F41.9", "Anxiety disorder, unspecified"),
        },
        "Hyperlipidemia": {
            "SNOMED-CT": ("55822004", "Hyperlipidemia"),
            "ICD-10-CM": ("E78.5", "Hyperlipidemia, unspecified"),
        },
        "Hypothyroidism": {
            "SNOMED-CT": ("40930008", "Hypothyroidism"),
            "ICD-10-CM": ("E03.9", "Hypothyroidism, unspecified"),
        },
        "Hyperthyroidism": {
            "SNOMED-CT": ("34486009", "Hyperthyroidism"),
            "ICD-10-CM": ("E05.90", "Thyrotoxicosis, unspecified"),
        },
        "GERD": {
            "SNOMED-CT": ("235595009", "Gastroesophageal reflux disease"),
            "ICD-10-CM": ("K21.0", "Gastro-esophageal reflux disease with esophagitis"),
        },
        "Osteoarthritis": {
            "SNOMED-CT": ("396275006", "Osteoarthritis"),
            "ICD-10-CM": ("M19.90", "Unspecified osteoarthritis, unspecified site"),
        },
        "Rheumatoid Arthritis": {
            "SNOMED-CT": ("69896004", "Rheumatoid arthritis"),
            "ICD-10-CM": ("M06.9", "Rheumatoid arthritis, unspecified"),
        },
        "Obesity": {
            "SNOMED-CT": ("414916001", "Obesity"),
            "ICD-10-CM": ("E66.9", "Obesity, unspecified"),
        },
        "Sleep Apnea": {
            "SNOMED-CT": ("73430006", "Sleep apnea"),
            "ICD-10-CM": ("G47.30", "Sleep apnea, unspecified"),
        },
        "Deep Vein Thrombosis": {
            "SNOMED-CT": ("128053003", "Deep venous thrombosis"),
            "ICD-10-CM": ("I82.409", "Acute embolism and thrombosis of unspecified deep veins of lower extremity"),
        },
        "Pulmonary Embolism": {
            "SNOMED-CT": ("59282003", "Pulmonary embolism"),
            "ICD-10-CM": ("I26.99", "Other pulmonary embolism without acute cor pulmonale"),
        },
        "Urinary Tract Infection": {
            "SNOMED-CT": ("68566005", "Urinary tract infection"),
            "ICD-10-CM": ("N39.0", "Urinary tract infection, site not specified"),
        },
        "Sepsis": {
            "SNOMED-CT": ("91302008", "Sepsis"),
            "ICD-10-CM": ("A41.9", "Sepsis, unspecified organism"),
        },
        "Cancer": {
            "SNOMED-CT": ("363346000", "Malignant neoplastic disease"),
            "ICD-10-CM": ("C80.1", "Malignant (primary) neoplasm, unspecified"),
        },
        "Iron Deficiency Anemia": {
            "SNOMED-CT": ("87522002", "Iron deficiency anemia"),
            "ICD-10-CM": ("D50.9", "Iron deficiency anemia, unspecified"),
        },
        "Anemia": {
            "SNOMED-CT": ("271737000", "Anemia"),
            "ICD-10-CM": ("D64.9", "Anemia, unspecified"),
        },
        "Gastroenteritis": {
            "SNOMED-CT": ("25374005", "Gastroenteritis"),
            "ICD-10-CM": ("K52.9", "Noninfective gastroenteritis and colitis, unspecified"),
        },
        "Syncope": {
            "SNOMED-CT": ("271594007", "Syncope"),
            "ICD-10-CM": ("R55", "Syncope and collapse"),
        },
        "Dehydration": {
            "SNOMED-CT": ("34095006", "Dehydration"),
            "ICD-10-CM": ("E86.0", "Dehydration"),
        },
        "Volume Depletion": {
            "SNOMED-CT": ("28560003", "Volume depletion"),
            "ICD-10-CM": ("E86.9", "Volume depletion, unspecified"),
        },
        "Orthostatic Hypotension": {
            "SNOMED-CT": ("28651003", "Orthostatic hypotension"),
            "ICD-10-CM": ("I95.1", "Orthostatic hypotension"),
        },
        # ------------------------------------------------------------------------
        # Additional Diagnoses - Neurological, Vascular, Infectious, Diabetic
        # ------------------------------------------------------------------------
        "Peripheral Neuropathy": {
            "SNOMED-CT": ("302226006", "Peripheral neuropathy"),
            "ICD-10-CM": ("G62.9", "Polyneuropathy, unspecified"),
        },
        "Diabetic Neuropathy": {
            "SNOMED-CT": ("230572002", "Diabetic neuropathy"),
            "ICD-10-CM": ("E11.40", "Type 2 diabetes mellitus with diabetic neuropathy, unspecified"),
        },
        "Peripheral Arterial Disease": {
            "SNOMED-CT": ("399957001", "Peripheral arterial occlusive disease"),
            "ICD-10-CM": ("I73.9", "Peripheral vascular disease, unspecified"),
        },
        "Osteomyelitis": {
            "SNOMED-CT": ("60168000", "Osteomyelitis"),
            "ICD-10-CM": ("M86.9", "Osteomyelitis, unspecified"),
        },
        "Cellulitis": {
            "SNOMED-CT": ("128045006", "Cellulitis"),
            "ICD-10-CM": ("L03.90", "Cellulitis, unspecified"),
        },
        "Diabetic Foot Infection": {
            "SNOMED-CT": ("280137006", "Diabetic foot infection"),
            "ICD-10-CM": ("E11.621", "Type 2 diabetes mellitus with foot ulcer"),
        },
        "Foot Ulcer": {
            "SNOMED-CT": ("95345008", "Foot ulcer"),
            "ICD-10-CM": ("L97.509", "Non-pressure chronic ulcer of other part of unspecified foot with unspecified severity"),
        },
        "Diabetic Foot Ulcer": {
            "SNOMED-CT": ("280137006", "Diabetic foot ulcer"),
            "ICD-10-CM": ("E11.621", "Type 2 diabetes mellitus with foot ulcer"),
        },
        "Hyperglycemia": {
            "SNOMED-CT": ("80394007", "Hyperglycemia"),
            "ICD-10-CM": ("R73.9", "Hyperglycemia, unspecified"),
        },
        "Hypoglycemia": {
            "SNOMED-CT": ("302866003", "Hypoglycemia"),
            "ICD-10-CM": ("E16.2", "Hypoglycemia, unspecified"),
        },
        "Diabetic Ketoacidosis": {
            "SNOMED-CT": ("420422005", "Diabetic ketoacidosis"),
            "ICD-10-CM": ("E11.10", "Type 2 diabetes mellitus with ketoacidosis without coma"),
        },
        "Hyperosmolar Hyperglycemic State": {
            "SNOMED-CT": ("359642000", "Hyperosmolar hyperglycemic state"),
            "ICD-10-CM": ("E11.00", "Type 2 diabetes mellitus with hyperosmolarity without nonketotic hyperglycemic-hyperosmolar coma"),
        },
        "Acute Kidney Injury": {
            "SNOMED-CT": ("14669001", "Acute kidney injury"),
            "ICD-10-CM": ("N17.9", "Acute kidney failure, unspecified"),
        },
        "Tachycardia": {
            "SNOMED-CT": ("3424008", "Tachycardia"),
            "ICD-10-CM": ("R00.0", "Tachycardia, unspecified"),
        },
        "Bradycardia": {
            "SNOMED-CT": ("48867003", "Bradycardia"),
            "ICD-10-CM": ("R00.1", "Bradycardia, unspecified"),
        },
        "Hyponatremia": {
            "SNOMED-CT": ("89627008", "Hyponatremia"),
            "ICD-10-CM": ("E87.1", "Hypo-osmolality and hyponatremia"),
        },
        "Hypernatremia": {
            "SNOMED-CT": ("286933003", "Hypernatremia"),
            "ICD-10-CM": ("E87.0", "Hyperosmolality and hypernatremia"),
        },
        "Hypokalemia": {
            "SNOMED-CT": ("43339004", "Hypokalemia"),
            "ICD-10-CM": ("E87.6", "Hypokalemia"),
        },
        "Hyperkalemia": {
            "SNOMED-CT": ("14140009", "Hyperkalemia"),
            "ICD-10-CM": ("E87.5", "Hyperkalemia"),
        },
        "Metabolic Acidosis": {
            "SNOMED-CT": ("59455009", "Metabolic acidosis"),
            "ICD-10-CM": ("E87.2", "Acidosis"),
        },
        "Respiratory Failure": {
            "SNOMED-CT": ("409623005", "Respiratory failure"),
            "ICD-10-CM": ("J96.90", "Respiratory failure, unspecified, unspecified whether with hypoxia or hypercapnia"),
        },
        "Acute Respiratory Distress Syndrome": {
            "SNOMED-CT": ("67782005", "Acute respiratory distress syndrome"),
            "ICD-10-CM": ("J80", "Acute respiratory distress syndrome"),
        },
        "Shock": {
            "SNOMED-CT": ("27942005", "Shock"),
            "ICD-10-CM": ("R57.9", "Shock, unspecified"),
        },
        "Septic Shock": {
            "SNOMED-CT": ("76571007", "Septic shock"),
            "ICD-10-CM": ("R65.21", "Severe sepsis with septic shock"),
        },
        "Cardiogenic Shock": {
            "SNOMED-CT": ("89138009", "Cardiogenic shock"),
            "ICD-10-CM": ("R57.0", "Cardiogenic shock"),
        },
        "Abscess": {
            "SNOMED-CT": ("44132006", "Abscess"),
            "ICD-10-CM": ("L02.91", "Cutaneous abscess, unspecified"),
        },
        "Gangrene": {
            "SNOMED-CT": ("372070002", "Gangrene"),
            "ICD-10-CM": ("R02", "Gangrene, not elsewhere classified"),
        },
        "Wound Infection": {
            "SNOMED-CT": ("312099009", "Wound infection"),
            "ICD-10-CM": ("T81.49XA", "Infection following a procedure, other surgical site, initial encounter"),
        },
        "Bacteremia": {
            "SNOMED-CT": ("5758002", "Bacteremia"),
            "ICD-10-CM": ("R78.81", "Bacteremia"),
        },
        "Endocarditis": {
            "SNOMED-CT": ("56819008", "Endocarditis"),
            "ICD-10-CM": ("I33.0", "Acute and subacute infective endocarditis"),
        },
        "Meningitis": {
            "SNOMED-CT": ("7180009", "Meningitis"),
            "ICD-10-CM": ("G03.9", "Meningitis, unspecified"),
        },
        "Encephalitis": {
            "SNOMED-CT": ("45170000", "Encephalitis"),
            "ICD-10-CM": ("G04.90", "Encephalitis and encephalomyelitis, unspecified"),
        },
        "Seizure": {
            "SNOMED-CT": ("91175000", "Seizure"),
            "ICD-10-CM": ("R56.9", "Unspecified convulsions"),
        },
        "Epilepsy": {
            "SNOMED-CT": ("84757009", "Epilepsy"),
            "ICD-10-CM": ("G40.909", "Epilepsy, unspecified, not intractable, without status epilepticus"),
        },
        "Status Epilepticus": {
            "SNOMED-CT": ("230456007", "Status epilepticus"),
            "ICD-10-CM": ("G41.9", "Status epilepticus, unspecified"),
        },
        "Altered Mental Status": {
            "SNOMED-CT": ("419284004", "Altered mental status"),
            "ICD-10-CM": ("R41.82", "Altered mental status, unspecified"),
        },
        "Delirium": {
            "SNOMED-CT": ("2776000", "Delirium"),
            "ICD-10-CM": ("R41.0", "Disorientation, unspecified"),
        },
        "Dementia": {
            "SNOMED-CT": ("52448006", "Dementia"),
            "ICD-10-CM": ("F03.90", "Unspecified dementia without behavioral disturbance"),
        },
        "Parkinson Disease": {
            "SNOMED-CT": ("49049000", "Parkinson disease"),
            "ICD-10-CM": ("G20", "Parkinson's disease"),
        },
        "Multiple Sclerosis": {
            "SNOMED-CT": ("24700007", "Multiple sclerosis"),
            "ICD-10-CM": ("G35", "Multiple sclerosis"),
        },
        "Transient Ischemic Attack": {
            "SNOMED-CT": ("266257000", "Transient ischemic attack"),
            "ICD-10-CM": ("G45.9", "Transient cerebral ischemic attack, unspecified"),
        },
        "Intracranial Hemorrhage": {
            "SNOMED-CT": ("1386000", "Intracranial hemorrhage"),
            "ICD-10-CM": ("I62.9", "Nontraumatic intracranial hemorrhage, unspecified"),
        },
        "Subarachnoid Hemorrhage": {
            "SNOMED-CT": ("21454007", "Subarachnoid hemorrhage"),
            "ICD-10-CM": ("I60.9", "Nontraumatic subarachnoid hemorrhage, unspecified"),
        },
        "Coronary Artery Disease": {
            "SNOMED-CT": ("53741008", "Coronary artery disease"),
            "ICD-10-CM": ("I25.10", "Atherosclerotic heart disease of native coronary artery without angina pectoris"),
        },
        "Angina": {
            "SNOMED-CT": ("194828000", "Angina pectoris"),
            "ICD-10-CM": ("I20.9", "Angina pectoris, unspecified"),
        },
        "Unstable Angina": {
            "SNOMED-CT": ("25106000", "Unstable angina"),
            "ICD-10-CM": ("I20.0", "Unstable angina"),
        },
        "NSTEMI": {
            "SNOMED-CT": ("401303003", "Non-ST elevation myocardial infarction"),
            "ICD-10-CM": ("I21.4", "Non-ST elevation (NSTEMI) myocardial infarction"),
        },
        "STEMI": {
            "SNOMED-CT": ("401314000", "ST elevation myocardial infarction"),
            "ICD-10-CM": ("I21.3", "ST elevation (STEMI) myocardial infarction of unspecified site"),
        },
        "Aortic Stenosis": {
            "SNOMED-CT": ("60573004", "Aortic stenosis"),
            "ICD-10-CM": ("I35.0", "Nonrheumatic aortic (valve) stenosis"),
        },
        "Mitral Regurgitation": {
            "SNOMED-CT": ("79619009", "Mitral valve regurgitation"),
            "ICD-10-CM": ("I34.0", "Nonrheumatic mitral (valve) insufficiency"),
        },
        "Aortic Dissection": {
            "SNOMED-CT": ("308546005", "Aortic dissection"),
            "ICD-10-CM": ("I71.00", "Dissection of unspecified site of aorta"),
        },
        "Aortic Aneurysm": {
            "SNOMED-CT": ("233985008", "Aortic aneurysm"),
            "ICD-10-CM": ("I71.9", "Aortic aneurysm of unspecified site, without rupture"),
        },
        "Peripheral Edema": {
            "SNOMED-CT": ("102572006", "Peripheral edema"),
            "ICD-10-CM": ("R60.0", "Localized edema"),
        },
        "Pleural Effusion": {
            "SNOMED-CT": ("60046008", "Pleural effusion"),
            "ICD-10-CM": ("J90", "Pleural effusion, not elsewhere classified"),
        },
        "Pulmonary Hypertension": {
            "SNOMED-CT": ("70995007", "Pulmonary hypertension"),
            "ICD-10-CM": ("I27.20", "Pulmonary hypertension, unspecified"),
        },
        "Acute Bronchitis": {
            "SNOMED-CT": ("10509002", "Acute bronchitis"),
            "ICD-10-CM": ("J20.9", "Acute bronchitis, unspecified"),
        },
        "Influenza": {
            "SNOMED-CT": ("6142004", "Influenza"),
            "ICD-10-CM": ("J11.1", "Influenza due to unidentified influenza virus with other respiratory manifestations"),
        },
        "COVID-19": {
            "SNOMED-CT": ("840539006", "COVID-19"),
            "ICD-10-CM": ("U07.1", "COVID-19"),
        },
        "Tuberculosis": {
            "SNOMED-CT": ("56717001", "Tuberculosis"),
            "ICD-10-CM": ("A15.9", "Respiratory tuberculosis unspecified"),
        },
        "Pancreatitis": {
            "SNOMED-CT": ("75694006", "Pancreatitis"),
            "ICD-10-CM": ("K85.9", "Acute pancreatitis, unspecified"),
        },
        "Hepatitis": {
            "SNOMED-CT": ("128241005", "Hepatitis"),
            "ICD-10-CM": ("K75.9", "Inflammatory liver disease, unspecified"),
        },
        "Cirrhosis": {
            "SNOMED-CT": ("19943007", "Cirrhosis of liver"),
            "ICD-10-CM": ("K74.60", "Unspecified cirrhosis of liver"),
        },
        "Hepatic Encephalopathy": {
            "SNOMED-CT": ("13920009", "Hepatic encephalopathy"),
            "ICD-10-CM": ("K72.90", "Hepatic failure, unspecified without coma"),
        },
        "GI Bleed": {
            "SNOMED-CT": ("74474003", "Gastrointestinal hemorrhage"),
            "ICD-10-CM": ("K92.2", "Gastrointestinal hemorrhage, unspecified"),
        },
        "Upper GI Bleed": {
            "SNOMED-CT": ("37372002", "Upper gastrointestinal hemorrhage"),
            "ICD-10-CM": ("K92.0", "Hematemesis"),
        },
        "Lower GI Bleed": {
            "SNOMED-CT": ("12063002", "Rectal hemorrhage"),
            "ICD-10-CM": ("K62.5", "Hemorrhage of anus and rectum"),
        },
        "Peptic Ulcer": {
            "SNOMED-CT": ("13200003", "Peptic ulcer"),
            "ICD-10-CM": ("K27.9", "Peptic ulcer, site unspecified, unspecified as acute or chronic, without hemorrhage or perforation"),
        },
        "Bowel Obstruction": {
            "SNOMED-CT": ("81060008", "Intestinal obstruction"),
            "ICD-10-CM": ("K56.60", "Unspecified intestinal obstruction"),
        },
        "Appendicitis": {
            "SNOMED-CT": ("74400008", "Appendicitis"),
            "ICD-10-CM": ("K37", "Unspecified appendicitis"),
        },
        "Cholecystitis": {
            "SNOMED-CT": ("76581006", "Cholecystitis"),
            "ICD-10-CM": ("K81.9", "Cholecystitis, unspecified"),
        },
        "Cholelithiasis": {
            "SNOMED-CT": ("235919008", "Cholelithiasis"),
            "ICD-10-CM": ("K80.20", "Calculus of gallbladder without cholecystitis without obstruction"),
        },
        "Diverticulitis": {
            "SNOMED-CT": ("427910000", "Diverticulitis"),
            "ICD-10-CM": ("K57.92", "Diverticulitis of intestine, part unspecified, without perforation or abscess without bleeding"),
        },
        "Nephrolithiasis": {
            "SNOMED-CT": ("95570007", "Kidney stone"),
            "ICD-10-CM": ("N20.0", "Calculus of kidney"),
        },
        "Pyelonephritis": {
            "SNOMED-CT": ("45816000", "Pyelonephritis"),
            "ICD-10-CM": ("N10", "Acute tubulo-interstitial nephritis"),
        },
        "Prostatitis": {
            "SNOMED-CT": ("9713002", "Prostatitis"),
            "ICD-10-CM": ("N41.9", "Inflammatory disease of prostate, unspecified"),
        },
        "Benign Prostatic Hyperplasia": {
            "SNOMED-CT": ("266569009", "Benign prostatic hyperplasia"),
            "ICD-10-CM": ("N40.0", "Benign prostatic hyperplasia without lower urinary tract symptoms"),
        },
        "Gout": {
            "SNOMED-CT": ("90560007", "Gout"),
            "ICD-10-CM": ("M10.9", "Gout, unspecified"),
        },
        "Pseudogout": {
            "SNOMED-CT": ("201727003", "Calcium pyrophosphate deposition disease"),
            "ICD-10-CM": ("M11.20", "Other chondrocalcinosis, unspecified site"),
        },
        "Fracture": {
            "SNOMED-CT": ("125605004", "Fracture of bone"),
            "ICD-10-CM": ("T14.8XXA", "Other injury of unspecified body region, initial encounter"),
        },
        "Hip Fracture": {
            "SNOMED-CT": ("263225007", "Fracture of hip"),
            "ICD-10-CM": ("S72.009A", "Fracture of unspecified part of neck of unspecified femur, initial encounter for closed fracture"),
        },
        "Vertebral Fracture": {
            "SNOMED-CT": ("207957008", "Fracture of vertebra"),
            "ICD-10-CM": ("S22.009A", "Unspecified fracture of unspecified thoracic vertebra, initial encounter for closed fracture"),
        },
        "Osteoporosis": {
            "SNOMED-CT": ("64859006", "Osteoporosis"),
            "ICD-10-CM": ("M81.0", "Age-related osteoporosis without current pathological fracture"),
        },
        "Spinal Stenosis": {
            "SNOMED-CT": ("76107001", "Spinal stenosis"),
            "ICD-10-CM": ("M48.06", "Spinal stenosis, lumbar region"),
        },
        "Herniated Disc": {
            "SNOMED-CT": ("76107001", "Intervertebral disc disorder"),
            "ICD-10-CM": ("M51.16", "Intervertebral disc disorders with radiculopathy, lumbar region"),
        },
        "Skin Ulcer": {
            "SNOMED-CT": ("46742003", "Skin ulcer"),
            "ICD-10-CM": ("L98.499", "Non-pressure chronic ulcer of skin of other sites with unspecified severity"),
        },
        "Pressure Ulcer": {
            "SNOMED-CT": ("420324007", "Pressure ulcer"),
            "ICD-10-CM": ("L89.90", "Pressure ulcer of unspecified site, unspecified stage"),
        },
        "Venous Stasis Ulcer": {
            "SNOMED-CT": ("402863005", "Venous stasis ulcer"),
            "ICD-10-CM": ("I87.2", "Venous insufficiency (chronic) (peripheral)"),
        },
        "Contact Dermatitis": {
            "SNOMED-CT": ("40275004", "Contact dermatitis"),
            "ICD-10-CM": ("L25.9", "Unspecified contact dermatitis, unspecified cause"),
        },
        "Eczema": {
            "SNOMED-CT": ("43116000", "Eczema"),
            "ICD-10-CM": ("L30.9", "Dermatitis, unspecified"),
        },
        "Psoriasis": {
            "SNOMED-CT": ("9014002", "Psoriasis"),
            "ICD-10-CM": ("L40.9", "Psoriasis, unspecified"),
        },
        "Herpes Zoster": {
            "SNOMED-CT": ("4740000", "Herpes zoster"),
            "ICD-10-CM": ("B02.9", "Zoster without complications"),
        },
        "Herpes Simplex": {
            "SNOMED-CT": ("88594005", "Herpes simplex"),
            "ICD-10-CM": ("B00.9", "Herpesviral infection, unspecified"),
        },
        "Systemic Lupus Erythematosus": {
            "SNOMED-CT": ("55464009", "Systemic lupus erythematosus"),
            "ICD-10-CM": ("M32.9", "Systemic lupus erythematosus, unspecified"),
        },
        "Sarcoidosis": {
            "SNOMED-CT": ("31541009", "Sarcoidosis"),
            "ICD-10-CM": ("D86.9", "Sarcoidosis, unspecified"),
        },
        "Fibromyalgia": {
            "SNOMED-CT": ("203082005", "Fibromyalgia"),
            "ICD-10-CM": ("M79.7", "Fibromyalgia"),
        },
        "Chronic Pain": {
            "SNOMED-CT": ("82423001", "Chronic pain"),
            "ICD-10-CM": ("G89.29", "Other chronic pain"),
        },
        "Bipolar Disorder": {
            "SNOMED-CT": ("13746004", "Bipolar disorder"),
            "ICD-10-CM": ("F31.9", "Bipolar disorder, unspecified"),
        },
        "Schizophrenia": {
            "SNOMED-CT": ("58214004", "Schizophrenia"),
            "ICD-10-CM": ("F20.9", "Schizophrenia, unspecified"),
        },
        "PTSD": {
            "SNOMED-CT": ("47505003", "Posttraumatic stress disorder"),
            "ICD-10-CM": ("F43.10", "Post-traumatic stress disorder, unspecified"),
        },
        "Substance Use Disorder": {
            "SNOMED-CT": ("66214007", "Substance abuse"),
            "ICD-10-CM": ("F19.10", "Other psychoactive substance abuse, uncomplicated"),
        },
        "Alcohol Use Disorder": {
            "SNOMED-CT": ("7200002", "Alcoholism"),
            "ICD-10-CM": ("F10.10", "Alcohol abuse, uncomplicated"),
        },
        "Opioid Use Disorder": {
            "SNOMED-CT": ("75544000", "Opioid dependence"),
            "ICD-10-CM": ("F11.10", "Opioid abuse, uncomplicated"),
        },
        "Tobacco Use Disorder": {
            "SNOMED-CT": ("89765005", "Tobacco use disorder"),
            "ICD-10-CM": ("F17.200", "Nicotine dependence, unspecified, uncomplicated"),
        },
        "Alcohol Withdrawal": {
            "SNOMED-CT": ("8635005", "Alcohol withdrawal"),
            "ICD-10-CM": ("F10.239", "Alcohol dependence with withdrawal, unspecified"),
        },
        # ========================================================================
        # SYMPTOMS - SNOMED-CT codes
        # ========================================================================
        "Fever": {
            "SNOMED-CT": ("386661006", "Fever"),
            "ICD-10-CM": ("R50.9", "Fever, unspecified"),
        },
        "Cough": {
            "SNOMED-CT": ("49727002", "Cough"),
            "ICD-10-CM": ("R05.9", "Cough, unspecified"),
        },
        "Shortness of Breath": {
            "SNOMED-CT": ("267036007", "Dyspnea"),
            "ICD-10-CM": ("R06.00", "Dyspnea, unspecified"),
        },
        "Chest Pain": {
            "SNOMED-CT": ("29857009", "Chest pain"),
            "ICD-10-CM": ("R07.9", "Chest pain, unspecified"),
        },
        "Abdominal Pain": {
            "SNOMED-CT": ("21522001", "Abdominal pain"),
            "ICD-10-CM": ("R10.9", "Unspecified abdominal pain"),
        },
        "Headache": {
            "SNOMED-CT": ("25064002", "Headache"),
            "ICD-10-CM": ("R51.9", "Headache, unspecified"),
        },
        "Nausea": {
            "SNOMED-CT": ("422587007", "Nausea"),
            "ICD-10-CM": ("R11.0", "Nausea"),
        },
        "Vomiting": {
            "SNOMED-CT": ("422400008", "Vomiting"),
            "ICD-10-CM": ("R11.10", "Vomiting, unspecified"),
        },
        "Diarrhea": {
            "SNOMED-CT": ("62315008", "Diarrhea"),
            "ICD-10-CM": ("R19.7", "Diarrhea, unspecified"),
        },
        "Constipation": {
            "SNOMED-CT": ("14760008", "Constipation"),
            "ICD-10-CM": ("K59.00", "Constipation, unspecified"),
        },
        "Fatigue": {
            "SNOMED-CT": ("84229001", "Fatigue"),
            "ICD-10-CM": ("R53.83", "Other fatigue"),
        },
        "Dizziness": {
            "SNOMED-CT": ("404640003", "Dizziness"),
            "ICD-10-CM": ("R42", "Dizziness and giddiness"),
        },
        "Lightheadedness": {
            "SNOMED-CT": ("386705008", "Lightheadedness"),
            "ICD-10-CM": ("R42", "Dizziness and giddiness"),
        },
        "Tunnel Vision": {
            "SNOMED-CT": ("246656009", "Tunnel vision"),
            "ICD-10-CM": ("H53.469", "Unspecified visual field defects, unspecified eye"),
        },
        "Presyncope": {
            "SNOMED-CT": ("698247007", "Presyncope"),
            "ICD-10-CM": ("R55", "Syncope and collapse"),
        },
        "Vision Changes": {
            "SNOMED-CT": ("246636008", "Visual disturbance"),
            "ICD-10-CM": ("H53.9", "Unspecified visual disturbance"),
        },
        "Palpitations": {
            "SNOMED-CT": ("80313002", "Palpitations"),
            "ICD-10-CM": ("R00.2", "Palpitations"),
        },
        "Edema": {
            "SNOMED-CT": ("267038008", "Edema"),
            "ICD-10-CM": ("R60.9", "Edema, unspecified"),
        },
        "Rash": {
            "SNOMED-CT": ("271807003", "Skin rash"),
            "ICD-10-CM": ("R21", "Rash and other nonspecific skin eruption"),
        },
        "Itching": {
            "SNOMED-CT": ("418290006", "Itching"),
            "ICD-10-CM": ("L29.9", "Pruritus, unspecified"),
        },
        "Weight Change": {
            "SNOMED-CT": ("267024001", "Abnormal weight"),
            "ICD-10-CM": ("R63.4", "Abnormal weight loss"),
        },
        "Insomnia": {
            "SNOMED-CT": ("193462001", "Insomnia"),
            "ICD-10-CM": ("G47.00", "Insomnia, unspecified"),
        },
        "Joint Pain": {
            "SNOMED-CT": ("57676002", "Joint pain"),
            "ICD-10-CM": ("M25.50", "Pain in unspecified joint"),
        },
        "Back Pain": {
            "SNOMED-CT": ("161891005", "Back pain"),
            "ICD-10-CM": ("M54.9", "Dorsalgia, unspecified"),
        },
        "Neck Pain": {
            "SNOMED-CT": ("81680005", "Neck pain"),
            "ICD-10-CM": ("M54.2", "Cervicalgia"),
        },
        "Weakness": {
            "SNOMED-CT": ("13791008", "Asthenia"),
            "ICD-10-CM": ("R53.1", "Weakness"),
        },
        "Numbness": {
            "SNOMED-CT": ("44077006", "Numbness"),
            "ICD-10-CM": ("R20.0", "Anesthesia of skin"),
        },
        "Confusion": {
            "SNOMED-CT": ("40917007", "Confusion"),
            "ICD-10-CM": ("R41.0", "Disorientation, unspecified"),
        },
        "Loss of Consciousness": {
            "SNOMED-CT": ("419045004", "Loss of consciousness"),
            "ICD-10-CM": ("R40.20", "Unspecified coma"),
        },
        "Seizure-like Activity": {
            "SNOMED-CT": ("91175000", "Seizure"),
            "ICD-10-CM": ("R56.9", "Unspecified convulsions"),
        },
        "Tongue Bite": {
            "SNOMED-CT": ("283682007", "Bite of tongue"),
            "ICD-10-CM": ("S01.502A", "Unspecified open wound of oral cavity, initial encounter"),
        },
        "Incontinence": {
            "SNOMED-CT": ("48340000", "Incontinence"),
            "ICD-10-CM": ("R32", "Unspecified urinary incontinence"),
        },
        "Post-ictal State": {
            "SNOMED-CT": ("25064002", "Postictal state"),
            "ICD-10-CM": ("G40.911", "Epilepsy, unspecified, intractable, with status epilepticus"),
        },
        "Poor Oral Intake": {
            "SNOMED-CT": ("78164000", "Feeding problems in newborn"),
            "ICD-10-CM": ("R63.3", "Feeding difficulties"),
        },
        # ------------------------------------------------------------------------
        # Additional Symptoms - Physical Exam Findings, Infection Signs
        # ------------------------------------------------------------------------
        "Chills": {
            "SNOMED-CT": ("43724002", "Chills"),
            "ICD-10-CM": ("R68.83", "Chills (without fever)"),
        },
        "Rigors": {
            "SNOMED-CT": ("271766005", "Shivering"),
            "ICD-10-CM": ("R68.83", "Chills (without fever)"),
        },
        "Erythema": {
            "SNOMED-CT": ("444827008", "Erythema"),
            "ICD-10-CM": ("L53.9", "Erythematous condition, unspecified"),
        },
        "Drainage": {
            "SNOMED-CT": ("307488001", "Drainage"),
            "ICD-10-CM": ("R89.9", "Unspecified abnormal finding in specimens from other organs, systems and tissues"),
        },
        "Purulent Drainage": {
            "SNOMED-CT": ("255306003", "Purulent"),
            "ICD-10-CM": ("L08.89", "Other specified local infections of the skin and subcutaneous tissue"),
        },
        "Warmth": {
            "SNOMED-CT": ("421637006", "Localized heat"),
            "ICD-10-CM": ("R23.9", "Unspecified skin changes"),
        },
        "Swelling": {
            "SNOMED-CT": ("442672001", "Swelling"),
            "ICD-10-CM": ("R22.9", "Localized swelling, mass and lump, unspecified"),
        },
        "Tenderness": {
            "SNOMED-CT": ("247348008", "Tenderness"),
            "ICD-10-CM": ("R68.89", "Other general symptoms and signs"),
        },
        "Foul Odor": {
            "SNOMED-CT": ("394625008", "Malodorous"),
            "ICD-10-CM": ("R68.89", "Other general symptoms and signs"),
        },
        "Wheezing": {
            "SNOMED-CT": ("56018004", "Wheezing"),
            "ICD-10-CM": ("R06.2", "Wheezing"),
        },
        "Stridor": {
            "SNOMED-CT": ("70407001", "Stridor"),
            "ICD-10-CM": ("R06.1", "Stridor"),
        },
        "Crackles": {
            "SNOMED-CT": ("48409008", "Crackles"),
            "ICD-10-CM": ("R09.89", "Other specified symptoms and signs involving the circulatory and respiratory systems"),
        },
        "Rales": {
            "SNOMED-CT": ("48409008", "Rale"),
            "ICD-10-CM": ("R09.89", "Other specified symptoms and signs involving the circulatory and respiratory systems"),
        },
        "Rhonchi": {
            "SNOMED-CT": ("24612001", "Rhonchi"),
            "ICD-10-CM": ("R09.89", "Other specified symptoms and signs involving the circulatory and respiratory systems"),
        },
        "Hemoptysis": {
            "SNOMED-CT": ("66857006", "Hemoptysis"),
            "ICD-10-CM": ("R04.2", "Hemoptysis"),
        },
        "Dysphagia": {
            "SNOMED-CT": ("40739000", "Dysphagia"),
            "ICD-10-CM": ("R13.10", "Dysphagia, unspecified"),
        },
        "Dysuria": {
            "SNOMED-CT": ("49650001", "Dysuria"),
            "ICD-10-CM": ("R30.0", "Dysuria"),
        },
        "Hematuria": {
            "SNOMED-CT": ("53298000", "Hematuria"),
            "ICD-10-CM": ("R31.9", "Hematuria, unspecified"),
        },
        "Urinary Frequency": {
            "SNOMED-CT": ("162116003", "Urinary frequency"),
            "ICD-10-CM": ("R35.0", "Frequency of micturition"),
        },
        "Urinary Urgency": {
            "SNOMED-CT": ("75088002", "Urinary urgency"),
            "ICD-10-CM": ("R35.81", "Urinary urgency"),
        },
        "Urinary Retention": {
            "SNOMED-CT": ("267064002", "Urinary retention"),
            "ICD-10-CM": ("R33.9", "Retention of urine, unspecified"),
        },
        "Melena": {
            "SNOMED-CT": ("2901004", "Melena"),
            "ICD-10-CM": ("K92.1", "Melena"),
        },
        "Hematemesis": {
            "SNOMED-CT": ("8765009", "Hematemesis"),
            "ICD-10-CM": ("K92.0", "Hematemesis"),
        },
        "Hematochezia": {
            "SNOMED-CT": ("405729008", "Hematochezia"),
            "ICD-10-CM": ("K62.5", "Hemorrhage of anus and rectum"),
        },
        "Diaphoresis": {
            "SNOMED-CT": ("415690000", "Sweating"),
            "ICD-10-CM": ("R61", "Generalized hyperhidrosis"),
        },
        "Tachypnea": {
            "SNOMED-CT": ("271823003", "Tachypnea"),
            "ICD-10-CM": ("R06.82", "Tachypnea, not elsewhere classified"),
        },
        "Hypoxia": {
            "SNOMED-CT": ("389086002", "Hypoxia"),
            "ICD-10-CM": ("R09.02", "Hypoxemia"),
        },
        "Hypoxemia": {
            "SNOMED-CT": ("389087006", "Hypoxemia"),
            "ICD-10-CM": ("R09.02", "Hypoxemia"),
        },
        "Cyanosis": {
            "SNOMED-CT": ("3415004", "Cyanosis"),
            "ICD-10-CM": ("R23.0", "Cyanosis"),
        },
        "Pallor": {
            "SNOMED-CT": ("398979000", "Pallor"),
            "ICD-10-CM": ("R23.1", "Pallor"),
        },
        "Jaundice": {
            "SNOMED-CT": ("18165001", "Jaundice"),
            "ICD-10-CM": ("R17", "Unspecified jaundice"),
        },
        "Ascites": {
            "SNOMED-CT": ("389026000", "Ascites"),
            "ICD-10-CM": ("R18.8", "Other ascites"),
        },
        "Tingling": {
            "SNOMED-CT": ("62507009", "Tingling sensation"),
            "ICD-10-CM": ("R20.2", "Paresthesia of skin"),
        },
        "Paresthesias": {
            "SNOMED-CT": ("91019004", "Paresthesia"),
            "ICD-10-CM": ("R20.2", "Paresthesia of skin"),
        },
        "Claudication": {
            "SNOMED-CT": ("16973004", "Intermittent claudication"),
            "ICD-10-CM": ("I73.9", "Peripheral vascular disease, unspecified"),
        },
        "Dyspnea on Exertion": {
            "SNOMED-CT": ("60845006", "Dyspnea on exertion"),
            "ICD-10-CM": ("R06.09", "Other forms of dyspnea"),
        },
        "Orthopnea": {
            "SNOMED-CT": ("62744007", "Orthopnea"),
            "ICD-10-CM": ("R06.01", "Orthopnea"),
        },
        "Paroxysmal Nocturnal Dyspnea": {
            "SNOMED-CT": ("55442000", "Paroxysmal nocturnal dyspnea"),
            "ICD-10-CM": ("R06.09", "Other forms of dyspnea"),
        },
        "Anorexia": {
            "SNOMED-CT": ("79890006", "Loss of appetite"),
            "ICD-10-CM": ("R63.0", "Anorexia"),
        },
        "Malaise": {
            "SNOMED-CT": ("367391008", "Malaise"),
            "ICD-10-CM": ("R53.81", "Other malaise"),
        },
        "Night Sweats": {
            "SNOMED-CT": ("42984000", "Night sweats"),
            "ICD-10-CM": ("R61", "Generalized hyperhidrosis"),
        },
        "Weight Loss": {
            "SNOMED-CT": ("89362005", "Weight loss"),
            "ICD-10-CM": ("R63.4", "Abnormal weight loss"),
        },
        "Weight Gain": {
            "SNOMED-CT": ("8943002", "Weight gain"),
            "ICD-10-CM": ("R63.5", "Abnormal weight gain"),
        },
        "Lethargy": {
            "SNOMED-CT": ("214264003", "Lethargy"),
            "ICD-10-CM": ("R53.83", "Other fatigue"),
        },
        "Somnolence": {
            "SNOMED-CT": ("271782001", "Drowsiness"),
            "ICD-10-CM": ("R40.0", "Somnolence"),
        },
        "Agitation": {
            "SNOMED-CT": ("24199005", "Agitation"),
            "ICD-10-CM": ("R45.1", "Restlessness and agitation"),
        },
        "Tremor": {
            "SNOMED-CT": ("26079004", "Tremor"),
            "ICD-10-CM": ("R25.1", "Tremor, unspecified"),
        },
        "Ataxia": {
            "SNOMED-CT": ("20262006", "Ataxia"),
            "ICD-10-CM": ("R27.0", "Ataxia, unspecified"),
        },
        "Vertigo": {
            "SNOMED-CT": ("399153001", "Vertigo"),
            "ICD-10-CM": ("R42", "Dizziness and giddiness"),
        },
        "Tinnitus": {
            "SNOMED-CT": ("60862001", "Tinnitus"),
            "ICD-10-CM": ("H93.19", "Tinnitus, unspecified ear"),
        },
        "Hearing Loss": {
            "SNOMED-CT": ("15188001", "Hearing loss"),
            "ICD-10-CM": ("H91.90", "Unspecified hearing loss, unspecified ear"),
        },
        "Blurred Vision": {
            "SNOMED-CT": ("246636008", "Blurred vision"),
            "ICD-10-CM": ("H53.8", "Other visual disturbances"),
        },
        "Diplopia": {
            "SNOMED-CT": ("24982008", "Diplopia"),
            "ICD-10-CM": ("H53.2", "Diplopia"),
        },
        "Photophobia": {
            "SNOMED-CT": ("409668002", "Photophobia"),
            "ICD-10-CM": ("H53.149", "Visual discomfort, unspecified"),
        },
        "Neck Stiffness": {
            "SNOMED-CT": ("161882006", "Stiff neck"),
            "ICD-10-CM": ("M43.6", "Torticollis"),
        },
        "Myalgia": {
            "SNOMED-CT": ("68962001", "Myalgia"),
            "ICD-10-CM": ("M79.10", "Myalgia, unspecified site"),
        },
        "Arthralgia": {
            "SNOMED-CT": ("57676002", "Arthralgia"),
            "ICD-10-CM": ("M25.50", "Pain in unspecified joint"),
        },
        "Stiffness": {
            "SNOMED-CT": ("84229001", "Joint stiffness"),
            "ICD-10-CM": ("M25.60", "Stiffness of unspecified joint, not elsewhere classified"),
        },
        "Swollen Joints": {
            "SNOMED-CT": ("57676002", "Joint swelling"),
            "ICD-10-CM": ("M25.40", "Effusion, unspecified joint"),
        },
        "Decreased Range of Motion": {
            "SNOMED-CT": ("304321006", "Reduced range of joint movement"),
            "ICD-10-CM": ("M25.60", "Stiffness of unspecified joint, not elsewhere classified"),
        },
        "Bruising": {
            "SNOMED-CT": ("125667009", "Contusion"),
            "ICD-10-CM": ("T14.8XXA", "Other injury of unspecified body region, initial encounter"),
        },
        "Petechiae": {
            "SNOMED-CT": ("271813007", "Petechiae"),
            "ICD-10-CM": ("R23.3", "Spontaneous ecchymoses"),
        },
        "Ecchymosis": {
            "SNOMED-CT": ("302227002", "Ecchymosis"),
            "ICD-10-CM": ("R23.3", "Spontaneous ecchymoses"),
        },
        "Bleeding": {
            "SNOMED-CT": ("131148009", "Bleeding"),
            "ICD-10-CM": ("R58", "Hemorrhage, not elsewhere classified"),
        },
        "Easy Bruising": {
            "SNOMED-CT": ("302227002", "Easy bruising"),
            "ICD-10-CM": ("D69.9", "Hemorrhagic condition, unspecified"),
        },
        "Epistaxis": {
            "SNOMED-CT": ("12441001", "Epistaxis"),
            "ICD-10-CM": ("R04.0", "Epistaxis"),
        },
        "Gingival Bleeding": {
            "SNOMED-CT": ("86134005", "Gingival bleeding"),
            "ICD-10-CM": ("K06.8", "Other specified disorders of gingiva and edentulous alveolar ridge"),
        },
        # ========================================================================
        # MEDICATIONS - RxNorm codes
        # ========================================================================
        "Metformin": {
            "RxNorm": ("6809", "metformin"),
        },
        "Lisinopril": {
            "RxNorm": ("29046", "lisinopril"),
        },
        "Atorvastatin": {
            "RxNorm": ("83367", "atorvastatin"),
        },
        "Amlodipine": {
            "RxNorm": ("17767", "amlodipine"),
        },
        "Omeprazole": {
            "RxNorm": ("7646", "omeprazole"),
        },
        "Aspirin": {
            "RxNorm": ("1191", "aspirin"),
        },
        "Warfarin": {
            "RxNorm": ("11289", "warfarin"),
        },
        "Insulin": {
            "RxNorm": ("5856", "insulin"),
        },
        "Acetaminophen": {
            "RxNorm": ("161", "acetaminophen"),
        },
        "Ibuprofen": {
            "RxNorm": ("5640", "ibuprofen"),
        },
        "Hydrocodone": {
            "RxNorm": ("5489", "hydrocodone"),
        },
        "Gabapentin": {
            "RxNorm": ("25480", "gabapentin"),
        },
        "Prednisone": {
            "RxNorm": ("8640", "prednisone"),
        },
        "Albuterol": {
            "RxNorm": ("435", "albuterol"),
        },
        "Furosemide": {
            "RxNorm": ("4603", "furosemide"),
        },
        "Carvedilol": {
            "RxNorm": ("20352", "carvedilol"),
        },
        "Metoprolol": {
            "RxNorm": ("6918", "metoprolol"),
        },
        "Pantoprazole": {
            "RxNorm": ("40790", "pantoprazole"),
        },
        "Clopidogrel": {
            "RxNorm": ("32968", "clopidogrel"),
        },
        "Levothyroxine": {
            "RxNorm": ("10582", "levothyroxine"),
        },
        # ------------------------------------------------------------------------
        # Additional Medications - Specific Insulins
        # ------------------------------------------------------------------------
        "Insulin Glargine": {
            "RxNorm": ("274783", "insulin glargine"),
        },
        "Lantus": {
            "RxNorm": ("274783", "insulin glargine"),
        },
        "Basaglar": {
            "RxNorm": ("274783", "insulin glargine"),
        },
        "Insulin Lispro": {
            "RxNorm": ("86009", "insulin lispro"),
        },
        "Humalog": {
            "RxNorm": ("86009", "insulin lispro"),
        },
        "Insulin Aspart": {
            "RxNorm": ("325072", "insulin aspart"),
        },
        "Novolog": {
            "RxNorm": ("325072", "insulin aspart"),
        },
        "Insulin Detemir": {
            "RxNorm": ("400008", "insulin detemir"),
        },
        "Levemir": {
            "RxNorm": ("400008", "insulin detemir"),
        },
        "Insulin Degludec": {
            "RxNorm": ("1373458", "insulin degludec"),
        },
        "Tresiba": {
            "RxNorm": ("1373458", "insulin degludec"),
        },
        "Insulin NPH": {
            "RxNorm": ("5856", "insulin isophane"),
        },
        "Regular Insulin": {
            "RxNorm": ("5856", "insulin regular"),
        },
        "Sliding Scale Insulin": {
            "RxNorm": ("5856", "insulin regular"),
        },
        # ------------------------------------------------------------------------
        # Additional Medications - IV Antibiotics
        # ------------------------------------------------------------------------
        "Vancomycin": {
            "RxNorm": ("11124", "vancomycin"),
        },
        "Piperacillin-Tazobactam": {
            "RxNorm": ("8339", "piperacillin/tazobactam"),
        },
        "Zosyn": {
            "RxNorm": ("8339", "piperacillin/tazobactam"),
        },
        "Ceftriaxone": {
            "RxNorm": ("2193", "ceftriaxone"),
        },
        "Rocephin": {
            "RxNorm": ("2193", "ceftriaxone"),
        },
        "Cefepime": {
            "RxNorm": ("20481", "cefepime"),
        },
        "Maxipime": {
            "RxNorm": ("20481", "cefepime"),
        },
        "Meropenem": {
            "RxNorm": ("29561", "meropenem"),
        },
        "Merrem": {
            "RxNorm": ("29561", "meropenem"),
        },
        "Imipenem": {
            "RxNorm": ("5690", "imipenem"),
        },
        "Ertapenem": {
            "RxNorm": ("82122", "ertapenem"),
        },
        "Invanz": {
            "RxNorm": ("82122", "ertapenem"),
        },
        "Ciprofloxacin": {
            "RxNorm": ("2551", "ciprofloxacin"),
        },
        "Cipro": {
            "RxNorm": ("2551", "ciprofloxacin"),
        },
        "Levofloxacin": {
            "RxNorm": ("82122", "levofloxacin"),
        },
        "Levaquin": {
            "RxNorm": ("82122", "levofloxacin"),
        },
        "Metronidazole": {
            "RxNorm": ("6922", "metronidazole"),
        },
        "Flagyl": {
            "RxNorm": ("6922", "metronidazole"),
        },
        "Ampicillin-Sulbactam": {
            "RxNorm": ("733", "ampicillin/sulbactam"),
        },
        "Unasyn": {
            "RxNorm": ("733", "ampicillin/sulbactam"),
        },
        "Cefazolin": {
            "RxNorm": ("2180", "cefazolin"),
        },
        "Ancef": {
            "RxNorm": ("2180", "cefazolin"),
        },
        "Gentamicin": {
            "RxNorm": ("4750", "gentamicin"),
        },
        "Tobramycin": {
            "RxNorm": ("10829", "tobramycin"),
        },
        "Amikacin": {
            "RxNorm": ("641", "amikacin"),
        },
        "Clindamycin": {
            "RxNorm": ("2582", "clindamycin"),
        },
        "Azithromycin": {
            "RxNorm": ("18631", "azithromycin"),
        },
        "Zithromax": {
            "RxNorm": ("18631", "azithromycin"),
        },
        "Doxycycline": {
            "RxNorm": ("3640", "doxycycline"),
        },
        "Trimethoprim-Sulfamethoxazole": {
            "RxNorm": ("10831", "trimethoprim/sulfamethoxazole"),
        },
        "Bactrim": {
            "RxNorm": ("10831", "trimethoprim/sulfamethoxazole"),
        },
        "Septra": {
            "RxNorm": ("10831", "trimethoprim/sulfamethoxazole"),
        },
        "Linezolid": {
            "RxNorm": ("190376", "linezolid"),
        },
        "Zyvox": {
            "RxNorm": ("190376", "linezolid"),
        },
        "Daptomycin": {
            "RxNorm": ("325642", "daptomycin"),
        },
        "Cubicin": {
            "RxNorm": ("325642", "daptomycin"),
        },
        "Ceftaroline": {
            "RxNorm": ("1009148", "ceftaroline"),
        },
        "Teflaro": {
            "RxNorm": ("1009148", "ceftaroline"),
        },
        "Penicillin": {
            "RxNorm": ("7984", "penicillin G"),
        },
        "Ampicillin": {
            "RxNorm": ("733", "ampicillin"),
        },
        "Amoxicillin": {
            "RxNorm": ("723", "amoxicillin"),
        },
        "Augmentin": {
            "RxNorm": ("151392", "amoxicillin/clavulanate"),
        },
        "Amoxicillin-Clavulanate": {
            "RxNorm": ("151392", "amoxicillin/clavulanate"),
        },
        "Fluconazole": {
            "RxNorm": ("4450", "fluconazole"),
        },
        "Diflucan": {
            "RxNorm": ("4450", "fluconazole"),
        },
        "Micafungin": {
            "RxNorm": ("349871", "micafungin"),
        },
        "Mycamine": {
            "RxNorm": ("349871", "micafungin"),
        },
        "Caspofungin": {
            "RxNorm": ("121243", "caspofungin"),
        },
        "Cancidas": {
            "RxNorm": ("121243", "caspofungin"),
        },
        "Voriconazole": {
            "RxNorm": ("121243", "voriconazole"),
        },
        "Vfend": {
            "RxNorm": ("121243", "voriconazole"),
        },
        "Acyclovir": {
            "RxNorm": ("281", "acyclovir"),
        },
        "Zovirax": {
            "RxNorm": ("281", "acyclovir"),
        },
        "Valacyclovir": {
            "RxNorm": ("69618", "valacyclovir"),
        },
        "Valtrex": {
            "RxNorm": ("69618", "valacyclovir"),
        },
        # ------------------------------------------------------------------------
        # Additional Medications - IV Fluids
        # ------------------------------------------------------------------------
        "IV Fluids": {
            "RxNorm": ("313002", "intravenous solution"),
        },
        "Normal Saline": {
            "RxNorm": ("313002", "sodium chloride 0.9% injection"),
        },
        "NS": {
            "RxNorm": ("313002", "sodium chloride 0.9% injection"),
        },
        "Lactated Ringers": {
            "RxNorm": ("237650", "lactated Ringer's injection"),
        },
        "LR": {
            "RxNorm": ("237650", "lactated Ringer's injection"),
        },
        "D5W": {
            "RxNorm": ("309778", "dextrose 5% in water"),
        },
        "D5NS": {
            "RxNorm": ("309781", "dextrose 5% and sodium chloride 0.9%"),
        },
        "Half Normal Saline": {
            "RxNorm": ("313003", "sodium chloride 0.45% injection"),
        },
        "D5 Half Normal Saline": {
            "RxNorm": ("309780", "dextrose 5% and sodium chloride 0.45%"),
        },
        "Albumin": {
            "RxNorm": ("453", "albumin human"),
        },
        "Plasmalyte": {
            "RxNorm": ("237650", "balanced crystalloid"),
        },
        # ------------------------------------------------------------------------
        # Additional Medications - Cardiac/Critical Care
        # ------------------------------------------------------------------------
        "Heparin": {
            "RxNorm": ("5224", "heparin"),
        },
        "Enoxaparin": {
            "RxNorm": ("67108", "enoxaparin"),
        },
        "Lovenox": {
            "RxNorm": ("67108", "enoxaparin"),
        },
        "Apixaban": {
            "RxNorm": ("1364430", "apixaban"),
        },
        "Eliquis": {
            "RxNorm": ("1364430", "apixaban"),
        },
        "Rivaroxaban": {
            "RxNorm": ("1114195", "rivaroxaban"),
        },
        "Xarelto": {
            "RxNorm": ("1114195", "rivaroxaban"),
        },
        "Dabigatran": {
            "RxNorm": ("1037042", "dabigatran"),
        },
        "Pradaxa": {
            "RxNorm": ("1037042", "dabigatran"),
        },
        "Norepinephrine": {
            "RxNorm": ("7512", "norepinephrine"),
        },
        "Levophed": {
            "RxNorm": ("7512", "norepinephrine"),
        },
        "Epinephrine": {
            "RxNorm": ("3992", "epinephrine"),
        },
        "Adrenalin": {
            "RxNorm": ("3992", "epinephrine"),
        },
        "Dopamine": {
            "RxNorm": ("3616", "dopamine"),
        },
        "Dobutamine": {
            "RxNorm": ("3616", "dobutamine"),
        },
        "Vasopressin": {
            "RxNorm": ("11149", "vasopressin"),
        },
        "Phenylephrine": {
            "RxNorm": ("8163", "phenylephrine"),
        },
        "Neosynephrine": {
            "RxNorm": ("8163", "phenylephrine"),
        },
        "Nitroglycerin": {
            "RxNorm": ("7417", "nitroglycerin"),
        },
        "Nitroprusside": {
            "RxNorm": ("7418", "nitroprusside"),
        },
        "Nicardipine": {
            "RxNorm": ("7396", "nicardipine"),
        },
        "Cardene": {
            "RxNorm": ("7396", "nicardipine"),
        },
        "Labetalol": {
            "RxNorm": ("6185", "labetalol"),
        },
        "Esmolol": {
            "RxNorm": ("49737", "esmolol"),
        },
        "Brevibloc": {
            "RxNorm": ("49737", "esmolol"),
        },
        "Diltiazem": {
            "RxNorm": ("3443", "diltiazem"),
        },
        "Cardizem": {
            "RxNorm": ("3443", "diltiazem"),
        },
        "Amiodarone": {
            "RxNorm": ("703", "amiodarone"),
        },
        "Cordarone": {
            "RxNorm": ("703", "amiodarone"),
        },
        "Digoxin": {
            "RxNorm": ("3407", "digoxin"),
        },
        "Lanoxin": {
            "RxNorm": ("3407", "digoxin"),
        },
        "Adenosine": {
            "RxNorm": ("313", "adenosine"),
        },
        "Atropine": {
            "RxNorm": ("1223", "atropine"),
        },
        "Sodium Bicarbonate": {
            "RxNorm": ("9863", "sodium bicarbonate"),
        },
        "Calcium Gluconate": {
            "RxNorm": ("1895", "calcium gluconate"),
        },
        "Calcium Chloride": {
            "RxNorm": ("1895", "calcium chloride"),
        },
        "Potassium Chloride": {
            "RxNorm": ("8591", "potassium chloride"),
        },
        "KCL": {
            "RxNorm": ("8591", "potassium chloride"),
        },
        "Magnesium Sulfate": {
            "RxNorm": ("6585", "magnesium sulfate"),
        },
        # ------------------------------------------------------------------------
        # Additional Medications - Pain/Sedation/Anesthesia
        # ------------------------------------------------------------------------
        "Morphine": {
            "RxNorm": ("7052", "morphine"),
        },
        "Fentanyl": {
            "RxNorm": ("4337", "fentanyl"),
        },
        "Hydromorphone": {
            "RxNorm": ("3423", "hydromorphone"),
        },
        "Dilaudid": {
            "RxNorm": ("3423", "hydromorphone"),
        },
        "Oxycodone": {
            "RxNorm": ("7804", "oxycodone"),
        },
        "Percocet": {
            "RxNorm": ("42844", "oxycodone/acetaminophen"),
        },
        "Tramadol": {
            "RxNorm": ("10689", "tramadol"),
        },
        "Ultram": {
            "RxNorm": ("10689", "tramadol"),
        },
        "Ketorolac": {
            "RxNorm": ("6135", "ketorolac"),
        },
        "Toradol": {
            "RxNorm": ("6135", "ketorolac"),
        },
        "Propofol": {
            "RxNorm": ("8782", "propofol"),
        },
        "Diprivan": {
            "RxNorm": ("8782", "propofol"),
        },
        "Midazolam": {
            "RxNorm": ("6960", "midazolam"),
        },
        "Versed": {
            "RxNorm": ("6960", "midazolam"),
        },
        "Lorazepam": {
            "RxNorm": ("6470", "lorazepam"),
        },
        "Ativan": {
            "RxNorm": ("6470", "lorazepam"),
        },
        "Diazepam": {
            "RxNorm": ("3322", "diazepam"),
        },
        "Valium": {
            "RxNorm": ("3322", "diazepam"),
        },
        "Ketamine": {
            "RxNorm": ("6130", "ketamine"),
        },
        "Dexmedetomidine": {
            "RxNorm": ("202398", "dexmedetomidine"),
        },
        "Precedex": {
            "RxNorm": ("202398", "dexmedetomidine"),
        },
        "Naloxone": {
            "RxNorm": ("7242", "naloxone"),
        },
        "Narcan": {
            "RxNorm": ("7242", "naloxone"),
        },
        "Flumazenil": {
            "RxNorm": ("4498", "flumazenil"),
        },
        "Romazicon": {
            "RxNorm": ("4498", "flumazenil"),
        },
        # ------------------------------------------------------------------------
        # Additional Medications - GI/Other
        # ------------------------------------------------------------------------
        "Ondansetron": {
            "RxNorm": ("26225", "ondansetron"),
        },
        "Zofran": {
            "RxNorm": ("26225", "ondansetron"),
        },
        "Metoclopramide": {
            "RxNorm": ("6915", "metoclopramide"),
        },
        "Reglan": {
            "RxNorm": ("6915", "metoclopramide"),
        },
        "Promethazine": {
            "RxNorm": ("8745", "promethazine"),
        },
        "Phenergan": {
            "RxNorm": ("8745", "promethazine"),
        },
        "Prochlorperazine": {
            "RxNorm": ("8704", "prochlorperazine"),
        },
        "Compazine": {
            "RxNorm": ("8704", "prochlorperazine"),
        },
        "Famotidine": {
            "RxNorm": ("4278", "famotidine"),
        },
        "Pepcid": {
            "RxNorm": ("4278", "famotidine"),
        },
        "Ranitidine": {
            "RxNorm": ("9143", "ranitidine"),
        },
        "Zantac": {
            "RxNorm": ("9143", "ranitidine"),
        },
        "Sucralfate": {
            "RxNorm": ("10154", "sucralfate"),
        },
        "Carafate": {
            "RxNorm": ("10154", "sucralfate"),
        },
        "Lactulose": {
            "RxNorm": ("6227", "lactulose"),
        },
        "Polyethylene Glycol": {
            "RxNorm": ("8455", "polyethylene glycol"),
        },
        "Miralax": {
            "RxNorm": ("8455", "polyethylene glycol"),
        },
        "Dexamethasone": {
            "RxNorm": ("3264", "dexamethasone"),
        },
        "Decadron": {
            "RxNorm": ("3264", "dexamethasone"),
        },
        "Methylprednisolone": {
            "RxNorm": ("6902", "methylprednisolone"),
        },
        "Solumedrol": {
            "RxNorm": ("6902", "methylprednisolone"),
        },
        "Hydrocortisone": {
            "RxNorm": ("5492", "hydrocortisone"),
        },
        "Diphenhydramine": {
            "RxNorm": ("3498", "diphenhydramine"),
        },
        "Benadryl": {
            "RxNorm": ("3498", "diphenhydramine"),
        },
        "Hydroxyzine": {
            "RxNorm": ("5553", "hydroxyzine"),
        },
        "Vistaril": {
            "RxNorm": ("5553", "hydroxyzine"),
        },
        "Spironolactone": {
            "RxNorm": ("9997", "spironolactone"),
        },
        "Aldactone": {
            "RxNorm": ("9997", "spironolactone"),
        },
        "Bumetanide": {
            "RxNorm": ("1808", "bumetanide"),
        },
        "Bumex": {
            "RxNorm": ("1808", "bumetanide"),
        },
        "Torsemide": {
            "RxNorm": ("38413", "torsemide"),
        },
        "Hydrochlorothiazide": {
            "RxNorm": ("5487", "hydrochlorothiazide"),
        },
        "HCTZ": {
            "RxNorm": ("5487", "hydrochlorothiazide"),
        },
        "Chlorthalidone": {
            "RxNorm": ("2409", "chlorthalidone"),
        },
        # ========================================================================
        # PROCEDURES - CPT and SNOMED-CT codes
        # ========================================================================
        "Cardiac Catheterization": {
            "SNOMED-CT": ("41976001", "Cardiac catheterization"),
            "CPT": ("93452", "Left heart catheterization"),
        },
        "Coronary Angioplasty": {
            "SNOMED-CT": ("41339005", "Coronary angioplasty"),
            "CPT": ("92920", "Percutaneous transluminal coronary angioplasty"),
        },
        "CABG": {
            "SNOMED-CT": ("232717009", "Coronary artery bypass grafting"),
            "CPT": ("33533", "Coronary artery bypass, single arterial graft"),
        },
        "Colonoscopy": {
            "SNOMED-CT": ("73761001", "Colonoscopy"),
            "CPT": ("45378", "Colonoscopy, diagnostic"),
        },
        "Endoscopy": {
            "SNOMED-CT": ("386718000", "Upper gastrointestinal endoscopy"),
            "CPT": ("43235", "Esophagogastroduodenoscopy, diagnostic"),
        },
        "Appendectomy": {
            "SNOMED-CT": ("80146002", "Appendectomy"),
            "CPT": ("44950", "Appendectomy"),
        },
        "Cholecystectomy": {
            "SNOMED-CT": ("38102005", "Cholecystectomy"),
            "CPT": ("47562", "Laparoscopic cholecystectomy"),
        },
        "Hysterectomy": {
            "SNOMED-CT": ("236886002", "Hysterectomy"),
            "CPT": ("58150", "Total abdominal hysterectomy"),
        },
        "Joint Replacement": {
            "SNOMED-CT": ("179344006", "Joint prosthesis procedure"),
            "CPT": ("27447", "Total knee arthroplasty"),
        },
        "Total Knee Arthroplasty": {
            "SNOMED-CT": ("609588000", "Total knee replacement"),
            "CPT": ("27447", "Total knee arthroplasty"),
        },
        "Total Hip Arthroplasty": {
            "SNOMED-CT": ("52734007", "Total hip replacement"),
            "CPT": ("27130", "Total hip arthroplasty"),
        },
        "Laminectomy": {
            "SNOMED-CT": ("387731002", "Laminectomy"),
            "CPT": ("63030", "Laminotomy"),
        },
        "Spinal Fusion": {
            "SNOMED-CT": ("112727005", "Spinal fusion"),
            "CPT": ("22612", "Arthrodesis, posterior or posterolateral technique"),
        },
        "Dialysis": {
            "SNOMED-CT": ("265764009", "Renal dialysis"),
            "CPT": ("90935", "Hemodialysis procedure"),
        },
        "Chemotherapy": {
            "SNOMED-CT": ("367336001", "Chemotherapy"),
            "CPT": ("96413", "Chemotherapy administration, intravenous infusion"),
        },
        "Radiation Therapy": {
            "SNOMED-CT": ("108290001", "Radiation therapy"),
            "CPT": ("77385", "Intensity modulated radiation therapy"),
        },
        "Surgery": {
            "SNOMED-CT": ("387713003", "Surgical procedure"),
        },
        "Biopsy": {
            "SNOMED-CT": ("86273004", "Biopsy"),
        },
        "Transfusion": {
            "SNOMED-CT": ("116859006", "Transfusion of blood product"),
            "CPT": ("36430", "Transfusion, blood or blood components"),
        },
        "Intubation": {
            "SNOMED-CT": ("112798008", "Insertion of endotracheal tube"),
            "CPT": ("31500", "Intubation, endotracheal"),
        },
        "Mechanical Ventilation": {
            "SNOMED-CT": ("40617009", "Artificial ventilation"),
            "CPT": ("94002", "Ventilation management, initial day"),
        },
        "CPR": {
            "SNOMED-CT": ("89666000", "Cardiopulmonary resuscitation"),
            "CPT": ("92950", "Cardiopulmonary resuscitation"),
        },
        # ------------------------------------------------------------------------
        # Additional Procedures - Imaging
        # ------------------------------------------------------------------------
        "X-Ray": {
            "SNOMED-CT": ("168537006", "Plain X-ray"),
            "CPT": ("71046", "Radiologic examination, chest; 2 views"),
        },
        "Chest X-Ray": {
            "SNOMED-CT": ("399208008", "Plain chest X-ray"),
            "CPT": ("71046", "Radiologic examination, chest; 2 views"),
        },
        "CT Scan": {
            "SNOMED-CT": ("77477000", "Computed tomography"),
            "CPT": ("71250", "Computed tomography, thorax; without contrast"),
        },
        "CT Head": {
            "SNOMED-CT": ("303653007", "CT of head"),
            "CPT": ("70450", "Computed tomography, head or brain; without contrast"),
        },
        "CT Chest": {
            "SNOMED-CT": ("169069000", "CT of chest"),
            "CPT": ("71250", "Computed tomography, thorax; without contrast"),
        },
        "CT Abdomen": {
            "SNOMED-CT": ("169070004", "CT of abdomen"),
            "CPT": ("74150", "Computed tomography, abdomen; without contrast"),
        },
        "CT Abdomen Pelvis": {
            "SNOMED-CT": ("419394006", "CT of abdomen and pelvis"),
            "CPT": ("74176", "Computed tomography, abdomen and pelvis; without contrast"),
        },
        "CTA": {
            "SNOMED-CT": ("418272005", "Computed tomography angiography"),
            "CPT": ("71275", "CT angiography, chest"),
        },
        "MRI": {
            "SNOMED-CT": ("113091000", "Magnetic resonance imaging"),
            "CPT": ("70553", "Magnetic resonance imaging, brain"),
        },
        "MRI Brain": {
            "SNOMED-CT": ("241601008", "MRI of brain"),
            "CPT": ("70553", "Magnetic resonance imaging, brain"),
        },
        "MRI Spine": {
            "SNOMED-CT": ("241577003", "MRI of spine"),
            "CPT": ("72148", "Magnetic resonance imaging, spinal canal and contents, lumbar"),
        },
        "MRA": {
            "SNOMED-CT": ("241620005", "Magnetic resonance angiography"),
            "CPT": ("70544", "Magnetic resonance angiography, head"),
        },
        "Ultrasound": {
            "SNOMED-CT": ("16310003", "Diagnostic ultrasonography"),
            "CPT": ("76705", "Ultrasound, abdominal, limited"),
        },
        "Abdominal Ultrasound": {
            "SNOMED-CT": ("45036003", "Ultrasonography of abdomen"),
            "CPT": ("76700", "Ultrasound, abdominal, complete"),
        },
        "RUQ Ultrasound": {
            "SNOMED-CT": ("45036003", "Ultrasonography of right upper quadrant"),
            "CPT": ("76705", "Ultrasound, abdominal, limited"),
        },
        "Doppler Ultrasound": {
            "SNOMED-CT": ("252892001", "Doppler ultrasonography"),
            "CPT": ("93880", "Duplex scan of extracranial arteries"),
        },
        "Lower Extremity Doppler": {
            "SNOMED-CT": ("420006008", "Doppler ultrasonography of lower extremity"),
            "CPT": ("93970", "Duplex scan of extremity veins"),
        },
        "Venous Doppler": {
            "SNOMED-CT": ("420006008", "Venous Doppler ultrasound"),
            "CPT": ("93970", "Duplex scan of extremity veins"),
        },
        "PET Scan": {
            "SNOMED-CT": ("82918005", "Positron emission tomography"),
            "CPT": ("78815", "Positron emission tomography (PET) with concurrently acquired computed tomography (CT)"),
        },
        "Bone Scan": {
            "SNOMED-CT": ("418007002", "Bone scan"),
            "CPT": ("78306", "Bone and/or joint imaging; whole body"),
        },
        "Nuclear Medicine Scan": {
            "SNOMED-CT": ("363680008", "Radioisotope scan"),
            "CPT": ("78999", "Nuclear medicine procedure"),
        },
        "Angiography": {
            "SNOMED-CT": ("77343006", "Angiography"),
            "CPT": ("36221", "Selective catheter placement, thoracic aorta"),
        },
        "Fluoroscopy": {
            "SNOMED-CT": ("44491008", "Fluoroscopy"),
            "CPT": ("76000", "Fluoroscopy"),
        },
        # ------------------------------------------------------------------------
        # Additional Procedures - Cultures and Labs
        # ------------------------------------------------------------------------
        "Blood Culture": {
            "SNOMED-CT": ("30088009", "Blood culture"),
            "CPT": ("87040", "Culture, blood"),
            "LOINC": ("600-7", "Blood culture"),
        },
        "Urine Culture": {
            "SNOMED-CT": ("117010004", "Urine culture"),
            "CPT": ("87086", "Culture, urine, quantitative"),
            "LOINC": ("6463-4", "Urine culture"),
        },
        "Wound Culture": {
            "SNOMED-CT": ("117020000", "Wound culture"),
            "CPT": ("87070", "Culture, bacterial; any other source except urine, blood or stool"),
        },
        "Sputum Culture": {
            "SNOMED-CT": ("117015009", "Sputum culture"),
            "CPT": ("87070", "Culture, bacterial; any other source except urine, blood or stool"),
        },
        "CSF Culture": {
            "SNOMED-CT": ("117017001", "Cerebrospinal fluid culture"),
            "CPT": ("87070", "Culture, bacterial; any other source except urine, blood or stool"),
        },
        "Stool Culture": {
            "SNOMED-CT": ("117016005", "Stool culture"),
            "CPT": ("87046", "Culture, stool"),
        },
        "Throat Culture": {
            "SNOMED-CT": ("117014008", "Throat culture"),
            "CPT": ("87070", "Culture, bacterial; any other source except urine, blood or stool"),
        },
        "Urinalysis": {
            "SNOMED-CT": ("27171005", "Urinalysis"),
            "CPT": ("81001", "Urinalysis, by dip stick or tablet reagent"),
            "LOINC": ("24356-8", "Urinalysis complete panel"),
        },
        "Lumbar Puncture": {
            "SNOMED-CT": ("277762005", "Lumbar puncture"),
            "CPT": ("62270", "Spinal puncture, lumbar, diagnostic"),
        },
        "Spinal Tap": {
            "SNOMED-CT": ("277762005", "Lumbar puncture"),
            "CPT": ("62270", "Spinal puncture, lumbar, diagnostic"),
        },
        "Paracentesis": {
            "SNOMED-CT": ("86088003", "Paracentesis"),
            "CPT": ("49083", "Abdominal paracentesis"),
        },
        "Thoracentesis": {
            "SNOMED-CT": ("91602002", "Thoracentesis"),
            "CPT": ("32555", "Thoracentesis, needle or catheter"),
        },
        "Arthrocentesis": {
            "SNOMED-CT": ("14766002", "Arthrocentesis"),
            "CPT": ("20610", "Arthrocentesis, aspiration and/or injection"),
        },
        "Bone Marrow Biopsy": {
            "SNOMED-CT": ("234326000", "Bone marrow biopsy"),
            "CPT": ("38221", "Bone marrow biopsy"),
        },
        # ------------------------------------------------------------------------
        # Additional Procedures - Cardiac Studies
        # ------------------------------------------------------------------------
        "ECG": {
            "SNOMED-CT": ("164847006", "Electrocardiogram"),
            "CPT": ("93000", "Electrocardiogram, routine ECG with at least 12 leads"),
            "LOINC": ("11524-6", "EKG study"),
        },
        "EKG": {
            "SNOMED-CT": ("164847006", "Electrocardiogram"),
            "CPT": ("93000", "Electrocardiogram, routine ECG with at least 12 leads"),
            "LOINC": ("11524-6", "EKG study"),
        },
        "Echocardiogram": {
            "SNOMED-CT": ("40701008", "Echocardiography"),
            "CPT": ("93306", "Echocardiography, transthoracic"),
        },
        "Echo": {
            "SNOMED-CT": ("40701008", "Echocardiography"),
            "CPT": ("93306", "Echocardiography, transthoracic"),
        },
        "TTE": {
            "SNOMED-CT": ("433236007", "Transthoracic echocardiography"),
            "CPT": ("93306", "Echocardiography, transthoracic"),
        },
        "TEE": {
            "SNOMED-CT": ("105376000", "Transesophageal echocardiography"),
            "CPT": ("93312", "Echocardiography, transesophageal"),
        },
        "Stress Test": {
            "SNOMED-CT": ("76746007", "Cardiac stress test"),
            "CPT": ("93015", "Cardiovascular stress test using maximal or submaximal treadmill"),
        },
        "Nuclear Stress Test": {
            "SNOMED-CT": ("152195001", "Nuclear medicine stress test"),
            "CPT": ("78451", "Myocardial perfusion imaging, tomographic"),
        },
        "Holter Monitor": {
            "SNOMED-CT": ("164848001", "Holter electrocardiography"),
            "CPT": ("93224", "External electrocardiographic recording up to 48 hours"),
        },
        "Event Monitor": {
            "SNOMED-CT": ("252455007", "Cardiac event monitoring"),
            "CPT": ("93268", "External patient and, when performed, auto activated electrocardiographic rhythm derived event recording"),
        },
        "Cardiac Monitor": {
            "SNOMED-CT": ("268557000", "Cardiac monitoring"),
            "CPT": ("93042", "Rhythm ECG, interpretation and report only"),
        },
        "Telemetry": {
            "SNOMED-CT": ("268557000", "Telemetry monitoring"),
            "CPT": ("93042", "Rhythm ECG, interpretation and report only"),
        },
        # ------------------------------------------------------------------------
        # Additional Procedures - Wound Care and Surgery
        # ------------------------------------------------------------------------
        "Debridement": {
            "SNOMED-CT": ("36777000", "Debridement"),
            "CPT": ("97597", "Debridement, open wound; selective"),
        },
        "Wound Debridement": {
            "SNOMED-CT": ("36777000", "Debridement of wound"),
            "CPT": ("97597", "Debridement, open wound; selective"),
        },
        "Wound Care": {
            "SNOMED-CT": ("225358003", "Wound care"),
            "CPT": ("97597", "Wound care"),
        },
        "Dressing Change": {
            "SNOMED-CT": ("18949003", "Change of wound dressing"),
            "CPT": ("97606", "Negative pressure wound therapy"),
        },
        "I&D": {
            "SNOMED-CT": ("5154007", "Incision and drainage"),
            "CPT": ("10060", "Incision and drainage of abscess"),
        },
        "Incision and Drainage": {
            "SNOMED-CT": ("5154007", "Incision and drainage"),
            "CPT": ("10060", "Incision and drainage of abscess"),
        },
        "Amputation": {
            "SNOMED-CT": ("81723002", "Amputation"),
            "CPT": ("27590", "Amputation, thigh"),
        },
        "Skin Graft": {
            "SNOMED-CT": ("72310004", "Skin graft"),
            "CPT": ("15100", "Split-thickness autograft"),
        },
        "Suture": {
            "SNOMED-CT": ("18557009", "Suture of skin"),
            "CPT": ("12001", "Simple repair of superficial wounds"),
        },
        "Laceration Repair": {
            "SNOMED-CT": ("30549001", "Repair of wound"),
            "CPT": ("12001", "Simple repair of superficial wounds"),
        },
        "Reduction": {
            "SNOMED-CT": ("56620000", "Reduction of fracture"),
            "CPT": ("25600", "Closed treatment of distal radial fracture"),
        },
        "Splinting": {
            "SNOMED-CT": ("79321009", "Application of splint"),
            "CPT": ("29105", "Application of long arm splint"),
        },
        "Casting": {
            "SNOMED-CT": ("61160003", "Application of cast"),
            "CPT": ("29075", "Application of forearm cast"),
        },
        # ------------------------------------------------------------------------
        # Additional Procedures - Lines and Access
        # ------------------------------------------------------------------------
        "Central Line": {
            "SNOMED-CT": ("233527006", "Insertion of central venous catheter"),
            "CPT": ("36556", "Insertion of central venous catheter"),
        },
        "Central Venous Catheter": {
            "SNOMED-CT": ("233527006", "Insertion of central venous catheter"),
            "CPT": ("36556", "Insertion of central venous catheter"),
        },
        "PICC Line": {
            "SNOMED-CT": ("392230005", "Insertion of peripherally inserted central catheter"),
            "CPT": ("36569", "Insertion of PICC line"),
        },
        "Arterial Line": {
            "SNOMED-CT": ("392247006", "Insertion of arterial catheter"),
            "CPT": ("36620", "Arterial catheterization"),
        },
        "Foley Catheter": {
            "SNOMED-CT": ("45211000", "Insertion of urinary catheter"),
            "CPT": ("51702", "Insertion of temporary indwelling bladder catheter"),
        },
        "Urinary Catheter": {
            "SNOMED-CT": ("45211000", "Insertion of urinary catheter"),
            "CPT": ("51702", "Insertion of temporary indwelling bladder catheter"),
        },
        "NG Tube": {
            "SNOMED-CT": ("91602002", "Insertion of nasogastric tube"),
            "CPT": ("43752", "Naso- or oro-gastric tube placement"),
        },
        "Nasogastric Tube": {
            "SNOMED-CT": ("91602002", "Insertion of nasogastric tube"),
            "CPT": ("43752", "Naso- or oro-gastric tube placement"),
        },
        "G Tube": {
            "SNOMED-CT": ("54956002", "Gastrostomy tube placement"),
            "CPT": ("43246", "Esophagogastroduodenoscopy with percutaneous gastrostomy tube placement"),
        },
        "PEG Tube": {
            "SNOMED-CT": ("54956002", "Percutaneous endoscopic gastrostomy"),
            "CPT": ("43246", "Esophagogastroduodenoscopy with percutaneous gastrostomy tube placement"),
        },
        "Chest Tube": {
            "SNOMED-CT": ("264957007", "Insertion of chest tube"),
            "CPT": ("32551", "Tube thoracostomy"),
        },
        "Tracheostomy": {
            "SNOMED-CT": ("48387007", "Tracheostomy"),
            "CPT": ("31600", "Tracheostomy, planned"),
        },
        # ------------------------------------------------------------------------
        # Additional Procedures - Consults
        # ------------------------------------------------------------------------
        "Consult": {
            "SNOMED-CT": ("11429006", "Consultation"),
            "CPT": ("99243", "Office consultation"),
        },
        "Podiatry Consult": {
            "SNOMED-CT": ("11429006", "Podiatry consultation"),
            "CPT": ("99243", "Consultation"),
        },
        "Orthopedic Consult": {
            "SNOMED-CT": ("11429006", "Orthopedic consultation"),
            "CPT": ("99243", "Consultation"),
        },
        "ID Consult": {
            "SNOMED-CT": ("11429006", "Infectious disease consultation"),
            "CPT": ("99243", "Consultation"),
        },
        "Infectious Disease Consult": {
            "SNOMED-CT": ("11429006", "Infectious disease consultation"),
            "CPT": ("99243", "Consultation"),
        },
        "Cardiology Consult": {
            "SNOMED-CT": ("11429006", "Cardiology consultation"),
            "CPT": ("99243", "Consultation"),
        },
        "Neurology Consult": {
            "SNOMED-CT": ("11429006", "Neurology consultation"),
            "CPT": ("99243", "Consultation"),
        },
        "Pulmonology Consult": {
            "SNOMED-CT": ("11429006", "Pulmonology consultation"),
            "CPT": ("99243", "Consultation"),
        },
        "GI Consult": {
            "SNOMED-CT": ("11429006", "Gastroenterology consultation"),
            "CPT": ("99243", "Consultation"),
        },
        "Nephrology Consult": {
            "SNOMED-CT": ("11429006", "Nephrology consultation"),
            "CPT": ("99243", "Consultation"),
        },
        "Surgery Consult": {
            "SNOMED-CT": ("11429006", "Surgery consultation"),
            "CPT": ("99243", "Consultation"),
        },
        "Vascular Surgery Consult": {
            "SNOMED-CT": ("11429006", "Vascular surgery consultation"),
            "CPT": ("99243", "Consultation"),
        },
        "Oncology Consult": {
            "SNOMED-CT": ("11429006", "Oncology consultation"),
            "CPT": ("99243", "Consultation"),
        },
        "Psychiatry Consult": {
            "SNOMED-CT": ("11429006", "Psychiatry consultation"),
            "CPT": ("99243", "Consultation"),
        },
        "Pain Management Consult": {
            "SNOMED-CT": ("11429006", "Pain management consultation"),
            "CPT": ("99243", "Consultation"),
        },
        "Palliative Care Consult": {
            "SNOMED-CT": ("11429006", "Palliative care consultation"),
            "CPT": ("99243", "Consultation"),
        },
        "Physical Therapy": {
            "SNOMED-CT": ("91251008", "Physical therapy procedure"),
            "CPT": ("97110", "Therapeutic exercises"),
        },
        "Occupational Therapy": {
            "SNOMED-CT": ("84478008", "Occupational therapy"),
            "CPT": ("97165", "Occupational therapy evaluation"),
        },
        "Speech Therapy": {
            "SNOMED-CT": ("311555007", "Speech therapy"),
            "CPT": ("92507", "Treatment of speech, language, voice, communication, and/or auditory processing disorder"),
        },
        "Respiratory Therapy": {
            "SNOMED-CT": ("53950000", "Respiratory therapy"),
            "CPT": ("94640", "Pressurized or nonpressurized inhalation treatment"),
        },
        "Social Work Consult": {
            "SNOMED-CT": ("11429006", "Social work consultation"),
            "CPT": ("99243", "Consultation"),
        },
        "Case Management": {
            "SNOMED-CT": ("386472008", "Case management"),
            "CPT": ("99487", "Chronic care management services"),
        },
        "Nutrition Consult": {
            "SNOMED-CT": ("11429006", "Nutrition consultation"),
            "CPT": ("97802", "Medical nutrition therapy; initial assessment"),
        },
        "Wound Care Consult": {
            "SNOMED-CT": ("11429006", "Wound care consultation"),
            "CPT": ("99243", "Consultation"),
        },
        # ========================================================================
        # LAB RESULTS - LOINC codes
        # ========================================================================
        "GLUCOSE": {
            "LOINC": ("2345-7", "Glucose [Mass/volume] in Serum or Plasma"),
        },
        "HBA1C": {
            "LOINC": ("4548-4", "Hemoglobin A1c/Hemoglobin.total in Blood"),
        },
        "HEMOGLOBIN": {
            "LOINC": ("718-7", "Hemoglobin [Mass/volume] in Blood"),
        },
        "WBC": {
            "LOINC": ("6690-2", "Leukocytes [#/volume] in Blood"),
        },
        "PLATELETS": {
            "LOINC": ("777-3", "Platelets [#/volume] in Blood"),
        },
        "CREATININE": {
            "LOINC": ("2160-0", "Creatinine [Mass/volume] in Serum or Plasma"),
        },
        "BUN": {
            "LOINC": ("3094-0", "Urea nitrogen [Mass/volume] in Serum or Plasma"),
        },
        "EGFR": {
            "LOINC": ("33914-3", "Glomerular filtration rate/1.73 sq M.predicted"),
        },
        "SODIUM": {
            "LOINC": ("2951-2", "Sodium [Moles/volume] in Serum or Plasma"),
        },
        "POTASSIUM": {
            "LOINC": ("2823-3", "Potassium [Moles/volume] in Serum or Plasma"),
        },
        "CHLORIDE": {
            "LOINC": ("2075-0", "Chloride [Moles/volume] in Serum or Plasma"),
        },
        "CO2": {
            "LOINC": ("2028-9", "Carbon dioxide, total [Moles/volume] in Serum or Plasma"),
        },
        "CHOLESTEROL": {
            "LOINC": ("2093-3", "Cholesterol [Mass/volume] in Serum or Plasma"),
        },
        "LDL": {
            "LOINC": ("13457-7", "LDL Cholesterol [Mass/volume] in Serum or Plasma"),
        },
        "HDL": {
            "LOINC": ("2085-9", "HDL Cholesterol [Mass/volume] in Serum or Plasma"),
        },
        "TRIGLYCERIDES": {
            "LOINC": ("2571-8", "Triglycerides [Mass/volume] in Serum or Plasma"),
        },
        "TSH": {
            "LOINC": ("3016-3", "Thyrotropin [Units/volume] in Serum or Plasma"),
        },
        "INR": {
            "LOINC": ("6301-6", "INR in Platelet poor plasma"),
        },
        "BNP": {
            "LOINC": ("30934-4", "Natriuretic peptide B [Mass/volume] in Serum or Plasma"),
        },
        "TROPONIN": {
            "LOINC": ("10839-9", "Troponin I.cardiac [Mass/volume] in Serum or Plasma"),
        },
        "PROCALCITONIN": {
            "LOINC": ("33959-8", "Procalcitonin [Mass/volume] in Serum or Plasma"),
        },
        # ------------------------------------------------------------------------
        # Additional Lab Results - Inflammatory Markers
        # ------------------------------------------------------------------------
        "CRP": {
            "LOINC": ("1988-5", "C reactive protein [Mass/volume] in Serum or Plasma"),
        },
        "C-REACTIVE PROTEIN": {
            "LOINC": ("1988-5", "C reactive protein [Mass/volume] in Serum or Plasma"),
        },
        "ESR": {
            "LOINC": ("30341-2", "Erythrocyte sedimentation rate"),
        },
        "SED RATE": {
            "LOINC": ("30341-2", "Erythrocyte sedimentation rate"),
        },
        "LACTATE": {
            "LOINC": ("2524-7", "Lactate [Moles/volume] in Serum or Plasma"),
        },
        "LACTIC ACID": {
            "LOINC": ("2524-7", "Lactate [Moles/volume] in Serum or Plasma"),
        },
        "FERRITIN": {
            "LOINC": ("2276-4", "Ferritin [Mass/volume] in Serum or Plasma"),
        },
        "D-DIMER": {
            "LOINC": ("48065-7", "Fibrin D-dimer FEU [Mass/volume] in Platelet poor plasma"),
        },
        "FIBRINOGEN": {
            "LOINC": ("3255-7", "Fibrinogen [Mass/volume] in Platelet poor plasma"),
        },
        # ------------------------------------------------------------------------
        # Additional Lab Results - CBC Components
        # ------------------------------------------------------------------------
        "HEMATOCRIT": {
            "LOINC": ("4544-3", "Hematocrit [Volume Fraction] of Blood"),
        },
        "HCT": {
            "LOINC": ("4544-3", "Hematocrit [Volume Fraction] of Blood"),
        },
        "HGB": {
            "LOINC": ("718-7", "Hemoglobin [Mass/volume] in Blood"),
        },
        "RBC": {
            "LOINC": ("789-8", "Erythrocytes [#/volume] in Blood"),
        },
        "MCV": {
            "LOINC": ("787-2", "Mean corpuscular volume [Entitic volume]"),
        },
        "MCH": {
            "LOINC": ("785-6", "Mean corpuscular hemoglobin [Entitic mass]"),
        },
        "MCHC": {
            "LOINC": ("786-4", "Mean corpuscular hemoglobin concentration [Mass/volume]"),
        },
        "RDW": {
            "LOINC": ("788-0", "Red cell distribution width [Ratio]"),
        },
        "PLT": {
            "LOINC": ("777-3", "Platelets [#/volume] in Blood"),
        },
        "MPV": {
            "LOINC": ("32623-1", "Mean platelet volume [Entitic volume] in Blood"),
        },
        "NEUTROPHILS": {
            "LOINC": ("751-8", "Neutrophils [#/volume] in Blood"),
        },
        "LYMPHOCYTES": {
            "LOINC": ("731-0", "Lymphocytes [#/volume] in Blood"),
        },
        "MONOCYTES": {
            "LOINC": ("742-7", "Monocytes [#/volume] in Blood"),
        },
        "EOSINOPHILS": {
            "LOINC": ("711-2", "Eosinophils [#/volume] in Blood"),
        },
        "BASOPHILS": {
            "LOINC": ("704-7", "Basophils [#/volume] in Blood"),
        },
        "BANDS": {
            "LOINC": ("764-1", "Band form neutrophils [#/volume] in Blood"),
        },
        "RETICULOCYTES": {
            "LOINC": ("17849-1", "Reticulocytes [#/volume] in Blood"),
        },
        # ------------------------------------------------------------------------
        # Additional Lab Results - Metabolic Panel
        # ------------------------------------------------------------------------
        "CALCIUM": {
            "LOINC": ("17861-6", "Calcium [Mass/volume] in Serum or Plasma"),
        },
        "IONIZED CALCIUM": {
            "LOINC": ("1995-0", "Calcium, ionized [Moles/volume] in Serum or Plasma"),
        },
        "MAGNESIUM": {
            "LOINC": ("19123-9", "Magnesium [Mass/volume] in Serum or Plasma"),
        },
        "PHOSPHORUS": {
            "LOINC": ("2777-1", "Phosphate [Mass/volume] in Serum or Plasma"),
        },
        "ANION GAP": {
            "LOINC": ("33037-3", "Anion gap in Serum or Plasma"),
        },
        "AG": {
            "LOINC": ("33037-3", "Anion gap in Serum or Plasma"),
        },
        "OSMOLALITY": {
            "LOINC": ("2692-2", "Osmolality of Serum or Plasma"),
        },
        "URIC ACID": {
            "LOINC": ("3084-1", "Urate [Mass/volume] in Serum or Plasma"),
        },
        # ------------------------------------------------------------------------
        # Additional Lab Results - Liver Function Tests
        # ------------------------------------------------------------------------
        "AST": {
            "LOINC": ("1920-8", "Aspartate aminotransferase [Enzymatic activity/volume] in Serum or Plasma"),
        },
        "SGOT": {
            "LOINC": ("1920-8", "Aspartate aminotransferase [Enzymatic activity/volume] in Serum or Plasma"),
        },
        "ALT": {
            "LOINC": ("1742-6", "Alanine aminotransferase [Enzymatic activity/volume] in Serum or Plasma"),
        },
        "SGPT": {
            "LOINC": ("1742-6", "Alanine aminotransferase [Enzymatic activity/volume] in Serum or Plasma"),
        },
        "ALKALINE PHOSPHATASE": {
            "LOINC": ("6768-6", "Alkaline phosphatase [Enzymatic activity/volume] in Serum or Plasma"),
        },
        "ALP": {
            "LOINC": ("6768-6", "Alkaline phosphatase [Enzymatic activity/volume] in Serum or Plasma"),
        },
        "BILIRUBIN": {
            "LOINC": ("1975-2", "Bilirubin.total [Mass/volume] in Serum or Plasma"),
        },
        "TOTAL BILIRUBIN": {
            "LOINC": ("1975-2", "Bilirubin.total [Mass/volume] in Serum or Plasma"),
        },
        "DIRECT BILIRUBIN": {
            "LOINC": ("1968-7", "Bilirubin.direct [Mass/volume] in Serum or Plasma"),
        },
        "INDIRECT BILIRUBIN": {
            "LOINC": ("1971-1", "Bilirubin.indirect [Mass/volume] in Serum or Plasma"),
        },
        "GGT": {
            "LOINC": ("2324-2", "Gamma glutamyl transferase [Enzymatic activity/volume] in Serum or Plasma"),
        },
        "ALBUMIN": {
            "LOINC": ("1751-7", "Albumin [Mass/volume] in Serum or Plasma"),
        },
        "TOTAL PROTEIN": {
            "LOINC": ("2885-2", "Protein [Mass/volume] in Serum or Plasma"),
        },
        "AMMONIA": {
            "LOINC": ("1846-0", "Ammonia [Mass/volume] in Plasma"),
        },
        "LDH": {
            "LOINC": ("2532-0", "Lactate dehydrogenase [Enzymatic activity/volume] in Serum or Plasma"),
        },
        # ------------------------------------------------------------------------
        # Additional Lab Results - Coagulation
        # ------------------------------------------------------------------------
        "PT": {
            "LOINC": ("5902-2", "Prothrombin time (PT)"),
        },
        "PROTHROMBIN TIME": {
            "LOINC": ("5902-2", "Prothrombin time (PT)"),
        },
        "PTT": {
            "LOINC": ("3173-2", "Activated partial thromboplastin time (aPTT)"),
        },
        "APTT": {
            "LOINC": ("3173-2", "Activated partial thromboplastin time (aPTT)"),
        },
        "ANTI-XA": {
            "LOINC": ("34714-6", "Coagulation factor X activity actual/normal in Platelet poor plasma"),
        },
        "HEPARIN LEVEL": {
            "LOINC": ("34714-6", "Heparin unfractionated in blood"),
        },
        # ------------------------------------------------------------------------
        # Additional Lab Results - Cardiac Markers
        # ------------------------------------------------------------------------
        "TROPONIN I": {
            "LOINC": ("10839-9", "Troponin I.cardiac [Mass/volume] in Serum or Plasma"),
        },
        "TROPONIN T": {
            "LOINC": ("6598-7", "Troponin T.cardiac [Mass/volume] in Serum or Plasma"),
        },
        "HIGH-SENSITIVITY TROPONIN": {
            "LOINC": ("89579-7", "Troponin I.cardiac [Mass/volume] in Serum or Plasma by High sensitivity method"),
        },
        "NT-PROBNP": {
            "LOINC": ("33762-6", "Natriuretic peptide.B prohormone N-Terminal [Mass/volume] in Serum or Plasma"),
        },
        "CK": {
            "LOINC": ("2157-6", "Creatine kinase [Enzymatic activity/volume] in Serum or Plasma"),
        },
        "CREATINE KINASE": {
            "LOINC": ("2157-6", "Creatine kinase [Enzymatic activity/volume] in Serum or Plasma"),
        },
        "CK-MB": {
            "LOINC": ("13969-1", "Creatine kinase.MB [Enzymatic activity/volume] in Serum or Plasma"),
        },
        "MYOGLOBIN": {
            "LOINC": ("2639-3", "Myoglobin [Mass/volume] in Serum or Plasma"),
        },
        # ------------------------------------------------------------------------
        # Additional Lab Results - Thyroid Panel
        # ------------------------------------------------------------------------
        "FREE T4": {
            "LOINC": ("3024-7", "Thyroxine (T4) free [Mass/volume] in Serum or Plasma"),
        },
        "FREE T3": {
            "LOINC": ("3051-0", "Triiodothyronine (T3) free [Mass/volume] in Serum or Plasma"),
        },
        "T3": {
            "LOINC": ("3053-6", "Triiodothyronine (T3) [Mass/volume] in Serum or Plasma"),
        },
        "T4": {
            "LOINC": ("3026-2", "Thyroxine (T4) [Mass/volume] in Serum or Plasma"),
        },
        # ------------------------------------------------------------------------
        # Additional Lab Results - ABG/VBG
        # ------------------------------------------------------------------------
        "PH": {
            "LOINC": ("2744-1", "pH of Arterial blood"),
        },
        "PCO2": {
            "LOINC": ("2019-8", "Carbon dioxide [Partial pressure] in Arterial blood"),
        },
        "PO2": {
            "LOINC": ("2703-7", "Oxygen [Partial pressure] in Arterial blood"),
        },
        "HCO3": {
            "LOINC": ("1959-6", "Bicarbonate [Moles/volume] in Arterial blood"),
        },
        "BICARBONATE": {
            "LOINC": ("1959-6", "Bicarbonate [Moles/volume] in Arterial blood"),
        },
        "BASE EXCESS": {
            "LOINC": ("1925-7", "Base excess in Arterial blood"),
        },
        "O2 SAT": {
            "LOINC": ("2708-6", "Oxygen saturation in Arterial blood"),
        },
        "CARBOXYHEMOGLOBIN": {
            "LOINC": ("2030-5", "Carboxyhemoglobin/Hemoglobin.total in Blood"),
        },
        "METHEMOGLOBIN": {
            "LOINC": ("2614-6", "Methemoglobin/Hemoglobin.total in Blood"),
        },
        # ------------------------------------------------------------------------
        # Additional Lab Results - Urinalysis
        # ------------------------------------------------------------------------
        "URINE PH": {
            "LOINC": ("2756-5", "pH of Urine"),
        },
        "URINE SPECIFIC GRAVITY": {
            "LOINC": ("2965-2", "Specific gravity of Urine"),
        },
        "URINE PROTEIN": {
            "LOINC": ("2888-6", "Protein [Mass/volume] in Urine"),
        },
        "URINE GLUCOSE": {
            "LOINC": ("2350-7", "Glucose [Mass/volume] in Urine"),
        },
        "URINE KETONES": {
            "LOINC": ("2514-8", "Ketones [Mass/volume] in Urine"),
        },
        "URINE BLOOD": {
            "LOINC": ("5794-3", "Hemoglobin [Presence] in Urine"),
        },
        "URINE WBC": {
            "LOINC": ("5821-4", "Leukocytes [#/area] in Urine sediment by Microscopy high power field"),
        },
        "URINE RBC": {
            "LOINC": ("5808-1", "Erythrocytes [#/area] in Urine sediment by Microscopy high power field"),
        },
        "URINE BACTERIA": {
            "LOINC": ("5769-5", "Bacteria [#/area] in Urine sediment by Microscopy high power field"),
        },
        "URINE LEUKOCYTE ESTERASE": {
            "LOINC": ("5799-2", "Leukocyte esterase [Presence] in Urine by Test strip"),
        },
        "URINE NITRITE": {
            "LOINC": ("5802-4", "Nitrite [Presence] in Urine by Test strip"),
        },
        # ------------------------------------------------------------------------
        # Additional Lab Results - Toxicology/Drug Levels
        # ------------------------------------------------------------------------
        "VANCOMYCIN LEVEL": {
            "LOINC": ("20578-1", "Vancomycin [Mass/volume] in Serum or Plasma"),
        },
        "VANC TROUGH": {
            "LOINC": ("20578-1", "Vancomycin [Mass/volume] in Serum or Plasma --trough"),
        },
        "DIGOXIN LEVEL": {
            "LOINC": ("10535-3", "Digoxin [Mass/volume] in Serum or Plasma"),
        },
        "PHENYTOIN LEVEL": {
            "LOINC": ("3968-5", "Phenytoin [Mass/volume] in Serum or Plasma"),
        },
        "VALPROIC ACID LEVEL": {
            "LOINC": ("4086-5", "Valproate [Mass/volume] in Serum or Plasma"),
        },
        "LITHIUM LEVEL": {
            "LOINC": ("14334-7", "Lithium [Moles/volume] in Serum or Plasma"),
        },
        "ACETAMINOPHEN LEVEL": {
            "LOINC": ("3298-7", "Acetaminophen [Mass/volume] in Serum or Plasma"),
        },
        "SALICYLATE LEVEL": {
            "LOINC": ("4024-6", "Salicylates [Mass/volume] in Serum or Plasma"),
        },
        "ETHANOL LEVEL": {
            "LOINC": ("5643-2", "Ethanol [Mass/volume] in Serum or Plasma"),
        },
        "ALCOHOL LEVEL": {
            "LOINC": ("5643-2", "Ethanol [Mass/volume] in Serum or Plasma"),
        },
        "URINE DRUG SCREEN": {
            "LOINC": ("19295-5", "Drugs of abuse panel - Urine"),
        },
        # ------------------------------------------------------------------------
        # Additional Lab Results - Miscellaneous
        # ------------------------------------------------------------------------
        "LIPASE": {
            "LOINC": ("3040-3", "Lipase [Enzymatic activity/volume] in Serum or Plasma"),
        },
        "AMYLASE": {
            "LOINC": ("1798-8", "Amylase [Enzymatic activity/volume] in Serum or Plasma"),
        },
        "CORTISOL": {
            "LOINC": ("2143-6", "Cortisol [Mass/volume] in Serum or Plasma"),
        },
        "VITAMIN D": {
            "LOINC": ("1989-3", "25-hydroxyvitamin D3 [Mass/volume] in Serum or Plasma"),
        },
        "VITAMIN B12": {
            "LOINC": ("2132-9", "Cobalamin (Vitamin B12) [Mass/volume] in Serum or Plasma"),
        },
        "FOLATE": {
            "LOINC": ("2284-8", "Folate [Mass/volume] in Serum or Plasma"),
        },
        "IRON": {
            "LOINC": ("2498-4", "Iron [Mass/volume] in Serum or Plasma"),
        },
        "TIBC": {
            "LOINC": ("2500-7", "Iron binding capacity [Mass/volume] in Serum or Plasma"),
        },
        "TRANSFERRIN": {
            "LOINC": ("3034-6", "Transferrin [Mass/volume] in Serum or Plasma"),
        },
        "HAPTOGLOBIN": {
            "LOINC": ("4542-7", "Haptoglobin [Mass/volume] in Serum or Plasma"),
        },
        "BLOOD TYPE": {
            "LOINC": ("882-1", "ABO and Rh group [Type] in Blood"),
        },
        "TYPE AND SCREEN": {
            "LOINC": ("57021-8", "Type and screen panel - Blood"),
        },
        "CROSSMATCH": {
            "LOINC": ("50099-8", "Crossmatch [interpretation] in Blood"),
        },
        "COOMBS TEST": {
            "LOINC": ("886-2", "Direct antiglobulin test.IgG specific reagent [Presence] on Red Blood Cells"),
        },
        "BETA HCG": {
            "LOINC": ("21198-7", "Choriogonadotropin.beta subunit [Mass/volume] in Serum or Plasma"),
        },
        "PREGNANCY TEST": {
            "LOINC": ("2106-3", "Choriogonadotropin [Presence] in Urine"),
        },
        "PSA": {
            "LOINC": ("2857-1", "Prostate specific antigen [Mass/volume] in Serum or Plasma"),
        },
        "HBA1C": {
            "LOINC": ("4548-4", "Hemoglobin A1c/Hemoglobin.total in Blood"),
        },
        # ========================================================================
        # VITAL SIGNS - LOINC codes
        # ========================================================================
        "Blood Pressure": {
            "LOINC": ("85354-9", "Blood pressure panel"),
        },
        "Heart Rate": {
            "LOINC": ("8867-4", "Heart rate"),
        },
        "Temperature": {
            "LOINC": ("8310-5", "Body temperature"),
        },
        "Respiratory Rate": {
            "LOINC": ("9279-1", "Respiratory rate"),
        },
        "Oxygen Saturation": {
            "LOINC": ("2708-6", "Oxygen saturation in Arterial blood"),
        },
        "Weight": {
            "LOINC": ("29463-7", "Body weight"),
        },
        "Height": {
            "LOINC": ("8302-2", "Body height"),
        },
        "Bmi": {
            "LOINC": ("39156-5", "Body mass index (BMI)"),
        },
    }

    def _normalize_with_services(
        self,
        entity: ExtractedEntity,
        vocabularies: list[NormalizationVocabulary],
    ) -> list[NormalizedCode]:
        """Normalize entity using real terminology services.

        Uses comprehensive clinical terminology services:
        - RxNorm for medications
        - SNOMED-CT for diagnoses, symptoms, and anatomical locations
        - ICD-10-CM for diagnoses
        - CPT for procedures
        - LOINC for lab results and vital signs

        Falls back to static CLINICAL_CODE_MAPPINGS if services unavailable.
        """
        # Ensure clinical abbreviations are loaded
        self._load_clinical_abbreviations()

        codes: list[NormalizedCode] = []
        normalized_text = entity.normalized_text
        search_text = normalized_text.lower().strip()

        # Try clinical abbreviations first (fast lookup with OMOP concept IDs)
        abbrev = self._clinical_abbreviations.get(search_text)
        if abbrev:
            omop_id = abbrev.get("omop_concept_id")
            domain = abbrev.get("domain", "")
            if omop_id:
                # Map domain to appropriate vocabulary
                if domain == "Drug" and NormalizationVocabulary.RXNORM in vocabularies:
                    codes.append(
                        NormalizedCode(
                            code=str(omop_id),
                            display=abbrev.get("name", normalized_text),
                            system=NormalizationVocabulary.RXNORM,
                            confidence=0.95,
                            is_preferred=True,
                        )
                    )
                elif domain in ("Condition", "Observation") and NormalizationVocabulary.SNOMED_CT in vocabularies:
                    codes.append(
                        NormalizedCode(
                            code=str(omop_id),
                            display=abbrev.get("name", normalized_text),
                            system=NormalizationVocabulary.SNOMED_CT,
                            confidence=0.95,
                            is_preferred=True,
                        )
                    )
                elif domain == "Measurement" and NormalizationVocabulary.LOINC in vocabularies:
                    codes.append(
                        NormalizedCode(
                            code=str(omop_id),
                            display=abbrev.get("name", normalized_text),
                            system=NormalizationVocabulary.LOINC,
                            confidence=0.95,
                            is_preferred=True,
                        )
                    )
                elif domain == "Procedure" and NormalizationVocabulary.CPT in vocabularies:
                    codes.append(
                        NormalizedCode(
                            code=str(omop_id),
                            display=abbrev.get("name", normalized_text),
                            system=NormalizationVocabulary.CPT,
                            confidence=0.95,
                            is_preferred=True,
                        )
                    )

        # Use terminology services based on entity type
        if entity.entity_type == EntityType.MEDICATION:
            codes.extend(self._normalize_medication(normalized_text, vocabularies))
        elif entity.entity_type in (EntityType.DIAGNOSIS, EntityType.SYMPTOM):
            codes.extend(self._normalize_diagnosis(normalized_text, vocabularies))
        elif entity.entity_type == EntityType.PROCEDURE:
            codes.extend(self._normalize_procedure(normalized_text, vocabularies))
        elif entity.entity_type in (EntityType.LAB_RESULT, EntityType.VITAL_SIGN):
            codes.extend(self._normalize_lab_or_vital(normalized_text, vocabularies))

        # Fall back to static mappings if no codes found
        if not codes:
            codes = self._fallback_static_lookup(normalized_text, vocabularies)

        return codes

    def _normalize_medication(
        self, text: str, vocabularies: list[NormalizationVocabulary]
    ) -> list[NormalizedCode]:
        """Normalize medication using RxNorm service."""
        codes: list[NormalizedCode] = []

        if NormalizationVocabulary.RXNORM not in vocabularies:
            return codes

        rxnorm = self._get_rxnorm_service()
        if rxnorm is None:
            return codes

        try:
            result = rxnorm.lookup_drug(text)
            if result.found and result.drug_info:
                drug = result.drug_info
                codes.append(
                    NormalizedCode(
                        code=drug.rxcui,
                        display=drug.generic_name or drug.concept_name,
                        system=NormalizationVocabulary.RXNORM,
                        confidence=0.95 if result.match_type.value == "exact" else 0.85,
                        is_preferred=True,
                    )
                )
                # Add OMOP concept ID if available
                if drug.omop_concept_id:
                    codes[0].code = f"{drug.rxcui} (OMOP: {drug.omop_concept_id})"
        except Exception as e:
            logger.debug(f"RxNorm lookup failed for '{text}': {e}")

        return codes

    def _normalize_diagnosis(
        self, text: str, vocabularies: list[NormalizationVocabulary]
    ) -> list[NormalizedCode]:
        """Normalize diagnosis using SNOMED and ICD-10 services."""
        codes: list[NormalizedCode] = []

        # Try SNOMED-CT first
        if NormalizationVocabulary.SNOMED_CT in vocabularies:
            snomed = self._get_snomed_service()
            if snomed:
                try:
                    matches = snomed.match_concept(text, max_results=3)
                    for i, match in enumerate(matches):
                        concept = match.concept
                        codes.append(
                            NormalizedCode(
                                code=concept.concept_id,
                                display=concept.concept_name,
                                system=NormalizationVocabulary.SNOMED_CT,
                                confidence=match.score * 0.95,
                                is_preferred=(i == 0),
                            )
                        )
                except Exception as e:
                    logger.debug(f"SNOMED lookup failed for '{text}': {e}")

        # Also try ICD-10-CM
        if NormalizationVocabulary.ICD10_CM in vocabularies:
            icd10 = self._get_icd10_service()
            if icd10:
                try:
                    result = icd10.suggest_codes(text, max_suggestions=3)
                    for suggestion in result.suggestions:
                        codes.append(
                            NormalizedCode(
                                code=suggestion.code,
                                display=suggestion.description,
                                system=NormalizationVocabulary.ICD10_CM,
                                confidence=0.90 if suggestion.confidence.value == "high" else 0.75,
                                is_preferred=(len(codes) == 0),
                            )
                        )
                except Exception as e:
                    logger.debug(f"ICD-10 lookup failed for '{text}': {e}")

        return codes

    def _normalize_procedure(
        self, text: str, vocabularies: list[NormalizationVocabulary]
    ) -> list[NormalizedCode]:
        """Normalize procedure using CPT and SNOMED services."""
        codes: list[NormalizedCode] = []

        # Try CPT first
        if NormalizationVocabulary.CPT in vocabularies:
            cpt = self._get_cpt_service()
            if cpt:
                try:
                    result = cpt.suggest_codes(text)
                    for suggestion in result.suggestions[:3]:
                        codes.append(
                            NormalizedCode(
                                code=suggestion.code,
                                display=suggestion.description,
                                system=NormalizationVocabulary.CPT,
                                confidence=0.90 if suggestion.confidence.value == "high" else 0.75,
                                is_preferred=(len(codes) == 0),
                            )
                        )
                except Exception as e:
                    logger.debug(f"CPT lookup failed for '{text}': {e}")

        # Also try SNOMED for procedures
        if NormalizationVocabulary.SNOMED_CT in vocabularies or not codes:
            snomed = self._get_snomed_service()
            if snomed:
                try:
                    # Import SemanticType for filtering
                    from app.services.snomed_service import SemanticType

                    matches = snomed.match_concept(
                        text, max_results=2, semantic_types=[SemanticType.PROCEDURE]
                    )
                    for match in matches:
                        concept = match.concept
                        codes.append(
                            NormalizedCode(
                                code=concept.concept_id,
                                display=concept.concept_name,
                                system=NormalizationVocabulary.SNOMED_CT,
                                confidence=match.score * 0.90,
                                is_preferred=(len(codes) == 0),
                            )
                        )
                except Exception as e:
                    logger.debug(f"SNOMED procedure lookup failed for '{text}': {e}")

        return codes

    def _normalize_lab_or_vital(
        self, text: str, vocabularies: list[NormalizationVocabulary]
    ) -> list[NormalizedCode]:
        """Normalize lab result or vital sign using LOINC data."""
        codes: list[NormalizedCode] = []

        if NormalizationVocabulary.LOINC not in vocabularies:
            return codes

        # Search in LOINC codes loaded from fixture
        search_text = text.lower().strip()

        # Try exact match first
        loinc_concept = self._loinc_codes.get(search_text)
        if loinc_concept:
            codes.append(
                NormalizedCode(
                    code=loinc_concept.get("concept_code", ""),
                    display=loinc_concept.get("concept_name", text),
                    system=NormalizationVocabulary.LOINC,
                    confidence=0.95,
                    is_preferred=True,
                )
            )
        else:
            # Try partial match on common lab names
            for key, concept in self._loinc_codes.items():
                if isinstance(key, str) and search_text in key:
                    codes.append(
                        NormalizedCode(
                            code=concept.get("concept_code", ""),
                            display=concept.get("concept_name", text),
                            system=NormalizationVocabulary.LOINC,
                            confidence=0.80,
                            is_preferred=(len(codes) == 0),
                        )
                    )
                    if len(codes) >= 3:
                        break

        return codes

    def _fallback_static_lookup(
        self, normalized_text: str, vocabularies: list[NormalizationVocabulary]
    ) -> list[NormalizedCode]:
        """Fall back to static CLINICAL_CODE_MAPPINGS lookup."""
        codes: list[NormalizedCode] = []

        if normalized_text in self.CLINICAL_CODE_MAPPINGS:
            for vocab in vocabularies:
                vocab_key = vocab.value
                if vocab_key in self.CLINICAL_CODE_MAPPINGS[normalized_text]:
                    code, display = self.CLINICAL_CODE_MAPPINGS[normalized_text][vocab_key]
                    codes.append(
                        NormalizedCode(
                            code=code,
                            display=display,
                            system=vocab,
                            confidence=0.85,
                            is_preferred=len(codes) == 0,
                        )
                    )

        return codes

    # Keep the old method name as an alias for backwards compatibility
    def _mock_normalize(
        self,
        entity: ExtractedEntity,
        vocabularies: list[NormalizationVocabulary],
    ) -> list[NormalizedCode]:
        """Normalize entity to standard vocabulary codes.

        This method now uses real terminology services when available,
        with fallback to static mappings.
        """
        return self._normalize_with_services(entity, vocabularies)

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
