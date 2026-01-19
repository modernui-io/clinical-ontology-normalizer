"""CPT-4 Code Suggester Service with Claim-Evidence-Reasoning Framework.

This module provides CPT-4 (Current Procedural Terminology) code suggestions
for medical procedures and services. It includes:

- Procedure-to-code mapping with natural language processing
- Claim-Evidence-Reasoning (CER) citations for each suggestion
- Modifier suggestions where applicable
- Documentation requirements
- Related diagnosis codes for medical necessity

Note: CPT codes are owned by the American Medical Association (AMA).
Code suggestions should be verified by qualified medical coders.
"""

from dataclasses import dataclass, field
from enum import Enum
import json
import logging
from pathlib import Path
import threading
from typing import Any

logger = logging.getLogger(__name__)


class CPTCategory(Enum):
    """CPT code categories."""

    EVALUATION_MANAGEMENT = "Evaluation and Management"
    ANESTHESIA = "Anesthesia"
    SURGERY = "Surgery"
    RADIOLOGY = "Radiology"
    PATHOLOGY = "Pathology and Laboratory"
    MEDICINE = "Medicine"


class ServicePlace(Enum):
    """Place of service for CPT codes."""

    OFFICE = "11"  # Office
    INPATIENT = "21"  # Inpatient Hospital
    OUTPATIENT = "22"  # On Campus-Outpatient Hospital
    EMERGENCY = "23"  # Emergency Room - Hospital
    ASC = "24"  # Ambulatory Surgical Center
    TELEHEALTH = "02"  # Telehealth


class ConfidenceLevel(Enum):
    """Confidence level for code suggestion."""

    HIGH = "high"  # Strong documentation support
    MEDIUM = "medium"  # Good support, may need review
    LOW = "low"  # Weak support, needs verification


@dataclass
class CERCitation:
    """Claim-Evidence-Reasoning citation for a code suggestion.

    This framework helps clinicians understand WHY a code is suggested:
    - Claim: What code is being suggested
    - Evidence: What clinical documentation supports this
    - Reasoning: Why the evidence supports this code
    """

    claim: str  # The assertion (e.g., "99214 is appropriate for this encounter")
    evidence: list[str]  # Clinical findings supporting the claim
    reasoning: str  # Explanation connecting evidence to claim
    strength: ConfidenceLevel  # How strong is this CER


@dataclass
class DocumentationRequirement:
    """Required documentation elements for a CPT code."""

    element: str  # What needs to be documented
    present: bool | None = None  # Whether it's documented (None = unknown)
    notes: str = ""


@dataclass
class CPTCode:
    """A CPT-4 code with description and metadata."""

    code: str
    description: str
    category: CPTCategory
    work_rvu: float = 0.0  # Work Relative Value Unit
    typical_time_minutes: int = 0
    global_period: str = ""  # XXX, 000, 010, 090

    # Related codes
    add_on_codes: list[str] = field(default_factory=list)
    related_codes: list[str] = field(default_factory=list)

    # Synonyms for matching
    synonyms: list[str] = field(default_factory=list)

    # Common modifiers
    common_modifiers: list[tuple[str, str]] = field(default_factory=list)  # (modifier, description)

    # Documentation requirements
    documentation_elements: list[str] = field(default_factory=list)

    # Medical necessity - ICD-10 codes commonly used
    common_diagnoses: list[str] = field(default_factory=list)


@dataclass
class CPTSuggestion:
    """A suggested CPT code with CER citation."""

    code: str
    description: str
    category: str
    confidence: ConfidenceLevel

    # CER Framework
    cer_citation: CERCitation

    # Additional info
    work_rvu: float
    typical_time_minutes: int

    # Modifiers that may apply
    suggested_modifiers: list[tuple[str, str]] = field(default_factory=list)

    # Documentation checklist
    documentation_checklist: list[DocumentationRequirement] = field(default_factory=list)

    # Related diagnosis codes for medical necessity
    supporting_diagnoses: list[tuple[str, str]] = field(default_factory=list)  # (ICD-10, description)

    # Alternative codes to consider
    alternative_codes: list[tuple[str, str]] = field(default_factory=list)

    # Coding guidance
    coding_notes: list[str] = field(default_factory=list)


@dataclass
class CPTSuggestionResult:
    """Result from CPT code suggestion."""

    query: str
    clinical_context: dict[str, str]  # Extracted clinical context
    suggestions: list[CPTSuggestion]
    total_matches: int
    documentation_gaps: list[str]  # Missing documentation that would affect coding
    coding_tips: list[str]


# ============================================================================
# CPT Code Database
# ============================================================================

CPT_CODES: list[CPTCode] = [
    # =========================================================================
    # EVALUATION AND MANAGEMENT (99201-99499)
    # =========================================================================
    # Office/Outpatient Visits - New Patient
    CPTCode(
        code="99202",
        description="Office/outpatient visit, new patient, straightforward MDM or 15-29 min",
        category=CPTCategory.EVALUATION_MANAGEMENT,
        work_rvu=0.93,
        typical_time_minutes=22,
        synonyms=["new patient visit", "new patient office visit", "level 2 new"],
        documentation_elements=[
            "Chief complaint",
            "History of present illness",
            "Medical decision making straightforward OR time 15-29 min",
        ],
        common_diagnoses=["Z00.00", "Z00.01"],  # General exam
    ),
    CPTCode(
        code="99203",
        description="Office/outpatient visit, new patient, low MDM or 30-44 min",
        category=CPTCategory.EVALUATION_MANAGEMENT,
        work_rvu=1.60,
        typical_time_minutes=37,
        synonyms=["new patient visit", "level 3 new"],
        documentation_elements=[
            "Chief complaint",
            "History of present illness",
            "Medical decision making low complexity OR time 30-44 min",
            "2+ chronic conditions",
        ],
        common_diagnoses=["I10", "E11.9"],
    ),
    CPTCode(
        code="99204",
        description="Office/outpatient visit, new patient, moderate MDM or 45-59 min",
        category=CPTCategory.EVALUATION_MANAGEMENT,
        work_rvu=2.60,
        typical_time_minutes=52,
        synonyms=["new patient visit", "level 4 new", "moderate complexity new"],
        documentation_elements=[
            "Chief complaint",
            "Comprehensive history",
            "Medical decision making moderate complexity OR time 45-59 min",
            "Undiagnosed new problem with uncertain prognosis",
            "Prescription drug management",
        ],
        common_diagnoses=["I10", "E11.9", "I25.10"],
    ),
    CPTCode(
        code="99205",
        description="Office/outpatient visit, new patient, high MDM or 60-74 min",
        category=CPTCategory.EVALUATION_MANAGEMENT,
        work_rvu=3.50,
        typical_time_minutes=67,
        synonyms=["new patient visit", "level 5 new", "high complexity new"],
        documentation_elements=[
            "Chief complaint",
            "Comprehensive history",
            "Medical decision making high complexity OR time 60-74 min",
            "Acute illness with systemic symptoms",
            "Drug therapy requiring intensive monitoring",
        ],
        common_diagnoses=["I50.9", "J44.1", "I21.9"],
    ),

    # Office/Outpatient Visits - Established Patient
    CPTCode(
        code="99211",
        description="Office/outpatient visit, established patient, may not require physician presence",
        category=CPTCategory.EVALUATION_MANAGEMENT,
        work_rvu=0.18,
        typical_time_minutes=5,
        synonyms=["nurse visit", "level 1 established", "brief visit"],
        documentation_elements=[
            "Presenting problem minimal",
            "Nurse or clinical staff evaluation",
        ],
        common_diagnoses=["Z23", "Z79.01"],  # Immunization, anticoagulant monitoring
    ),
    CPTCode(
        code="99212",
        description="Office/outpatient visit, established patient, straightforward MDM or 10-19 min",
        category=CPTCategory.EVALUATION_MANAGEMENT,
        work_rvu=0.70,
        typical_time_minutes=15,
        synonyms=["follow up visit", "level 2 established", "brief follow up"],
        documentation_elements=[
            "Chief complaint",
            "Medical decision making straightforward OR time 10-19 min",
            "Self-limited or minor problem",
        ],
        common_diagnoses=["J06.9", "B34.9"],  # URI, viral infection
    ),
    CPTCode(
        code="99213",
        description="Office/outpatient visit, established patient, low MDM or 20-29 min",
        category=CPTCategory.EVALUATION_MANAGEMENT,
        work_rvu=1.30,
        typical_time_minutes=24,
        synonyms=["follow up visit", "level 3 established", "routine follow up"],
        documentation_elements=[
            "Chief complaint",
            "History of present illness",
            "Medical decision making low complexity OR time 20-29 min",
            "2+ self-limited problems OR 1 chronic illness stable",
        ],
        common_diagnoses=["I10", "E11.9", "E78.5"],
    ),
    CPTCode(
        code="99214",
        description="Office/outpatient visit, established patient, moderate MDM or 30-39 min",
        category=CPTCategory.EVALUATION_MANAGEMENT,
        work_rvu=1.92,
        typical_time_minutes=34,
        synonyms=["follow up visit", "level 4 established", "moderate complexity"],
        documentation_elements=[
            "Chief complaint",
            "Extended history of present illness",
            "Medical decision making moderate complexity OR time 30-39 min",
            "1+ chronic illness with mild exacerbation",
            "Prescription drug management",
        ],
        common_diagnoses=["I10", "E11.65", "I50.9", "J44.1"],
    ),
    CPTCode(
        code="99215",
        description="Office/outpatient visit, established patient, high MDM or 40-54 min",
        category=CPTCategory.EVALUATION_MANAGEMENT,
        work_rvu=2.80,
        typical_time_minutes=47,
        synonyms=["follow up visit", "level 5 established", "high complexity"],
        documentation_elements=[
            "Chief complaint",
            "Comprehensive history",
            "Medical decision making high complexity OR time 40-54 min",
            "Chronic illness with severe exacerbation",
            "Drug therapy requiring intensive monitoring",
        ],
        common_diagnoses=["I50.22", "I21.9", "J44.1", "E11.65"],
    ),

    # Hospital Inpatient Services
    CPTCode(
        code="99221",
        description="Initial hospital care, low or moderate MDM or 40 min",
        category=CPTCategory.EVALUATION_MANAGEMENT,
        work_rvu=2.00,
        typical_time_minutes=40,
        synonyms=["hospital admission", "inpatient admission", "admit"],
        documentation_elements=[
            "Chief complaint",
            "Comprehensive history",
            "Admission orders",
            "Medical decision making low/moderate complexity",
        ],
        common_diagnoses=["J18.9", "I50.9"],
    ),
    CPTCode(
        code="99222",
        description="Initial hospital care, moderate MDM or 55 min",
        category=CPTCategory.EVALUATION_MANAGEMENT,
        work_rvu=2.61,
        typical_time_minutes=55,
        synonyms=["hospital admission", "inpatient admission"],
        documentation_elements=[
            "Comprehensive history",
            "Comprehensive examination",
            "Medical decision making moderate complexity",
            "Multiple conditions requiring workup",
        ],
        common_diagnoses=["J18.9", "I50.22", "I21.9"],
    ),
    CPTCode(
        code="99223",
        description="Initial hospital care, high MDM or 75 min",
        category=CPTCategory.EVALUATION_MANAGEMENT,
        work_rvu=3.86,
        typical_time_minutes=75,
        synonyms=["hospital admission", "complex admission"],
        documentation_elements=[
            "Comprehensive history",
            "Comprehensive examination",
            "Medical decision making high complexity",
            "Severely ill patient",
            "Multiple diagnoses requiring active management",
        ],
        common_diagnoses=["A41.9", "I21.9", "I50.22"],
    ),

    # Emergency Department
    CPTCode(
        code="99281",
        description="Emergency department visit, self-limited problem",
        category=CPTCategory.EVALUATION_MANAGEMENT,
        work_rvu=0.45,
        typical_time_minutes=10,
        synonyms=["ed visit", "er visit", "emergency room"],
        documentation_elements=[
            "Chief complaint",
            "Self-limited or minor problem",
        ],
        common_diagnoses=["S61.419A"],  # Minor laceration
    ),
    CPTCode(
        code="99283",
        description="Emergency department visit, moderate severity problem",
        category=CPTCategory.EVALUATION_MANAGEMENT,
        work_rvu=1.42,
        typical_time_minutes=30,
        synonyms=["ed visit", "er visit", "emergency room"],
        documentation_elements=[
            "Chief complaint",
            "Extended history",
            "Moderately severe problem",
        ],
        common_diagnoses=["R07.9", "R10.9"],  # Chest pain, abdominal pain
    ),
    CPTCode(
        code="99284",
        description="Emergency department visit, high severity problem",
        category=CPTCategory.EVALUATION_MANAGEMENT,
        work_rvu=2.56,
        typical_time_minutes=45,
        synonyms=["ed visit", "er visit", "emergency room"],
        documentation_elements=[
            "Chief complaint",
            "Comprehensive history",
            "High severity problem requiring urgent evaluation",
        ],
        common_diagnoses=["R07.9", "I21.9", "I63.9"],
    ),
    CPTCode(
        code="99285",
        description="Emergency department visit, imminent life threat",
        category=CPTCategory.EVALUATION_MANAGEMENT,
        work_rvu=3.80,
        typical_time_minutes=60,
        synonyms=["ed visit", "er visit", "critical ed"],
        documentation_elements=[
            "Chief complaint",
            "Comprehensive history",
            "Life-threatening condition",
            "Immediate intervention required",
        ],
        common_diagnoses=["I21.9", "I63.9", "A41.9"],
    ),

    # =========================================================================
    # COMMON PROCEDURES
    # =========================================================================
    CPTCode(
        code="93000",
        description="Electrocardiogram, routine ECG with interpretation and report",
        category=CPTCategory.MEDICINE,
        work_rvu=0.17,
        typical_time_minutes=5,
        synonyms=["ecg", "ekg", "electrocardiogram", "12 lead ecg"],
        documentation_elements=[
            "12-lead ECG performed",
            "Interpretation of rhythm and findings",
        ],
        common_diagnoses=["R00.0", "R00.1", "I48.91", "I25.10"],
        common_modifiers=[("26", "Professional component only")],
    ),
    CPTCode(
        code="71046",
        description="Radiologic examination, chest; 2 views",
        category=CPTCategory.RADIOLOGY,
        work_rvu=0.22,
        typical_time_minutes=5,
        synonyms=["chest xray", "cxr", "chest x-ray", "pa and lateral chest"],
        documentation_elements=[
            "PA and lateral views obtained",
            "Radiology interpretation",
        ],
        common_diagnoses=["R05", "R06.02", "J18.9"],
        common_modifiers=[("26", "Professional component only"), ("TC", "Technical component only")],
    ),
    CPTCode(
        code="80053",
        description="Comprehensive metabolic panel",
        category=CPTCategory.PATHOLOGY,
        work_rvu=0.0,  # Lab tests don't have work RVU
        typical_time_minutes=0,
        synonyms=["cmp", "comprehensive metabolic panel", "basic labs"],
        documentation_elements=[
            "14 chemistry tests including electrolytes, glucose, renal and liver function",
        ],
        common_diagnoses=["E11.9", "N18.9", "K76.0"],
    ),
    CPTCode(
        code="85025",
        description="Blood count; complete (CBC), automated, and automated differential WBC count",
        category=CPTCategory.PATHOLOGY,
        work_rvu=0.0,
        typical_time_minutes=0,
        synonyms=["cbc", "complete blood count", "cbc with diff"],
        documentation_elements=[
            "CBC with differential performed",
        ],
        common_diagnoses=["D64.9", "J18.9", "A41.9"],
    ),
    CPTCode(
        code="36415",
        description="Collection of venous blood by venipuncture",
        category=CPTCategory.SURGERY,
        work_rvu=0.0,
        typical_time_minutes=5,
        synonyms=["blood draw", "venipuncture", "phlebotomy"],
        documentation_elements=[
            "Venous blood sample collected",
        ],
        common_diagnoses=[],  # Usually not separately billable in office
    ),
    CPTCode(
        code="96372",
        description="Therapeutic, prophylactic, or diagnostic injection, SC or IM",
        category=CPTCategory.MEDICINE,
        work_rvu=0.17,
        typical_time_minutes=5,
        synonyms=["injection", "im injection", "subq injection", "shot"],
        documentation_elements=[
            "Drug administered",
            "Route of administration",
            "Site of injection",
        ],
        common_diagnoses=["M54.5", "M79.3"],
        add_on_codes=["J0702", "J1030"],  # Drug codes
    ),
    CPTCode(
        code="99406",
        description="Smoking and tobacco use cessation counseling visit; 3-10 min",
        category=CPTCategory.MEDICINE,
        work_rvu=0.24,
        typical_time_minutes=7,
        synonyms=["smoking cessation", "tobacco counseling"],
        documentation_elements=[
            "Tobacco cessation counseling provided",
            "Duration of counseling",
            "Discussion of cessation strategies",
        ],
        common_diagnoses=["F17.210", "Z87.891"],
    ),

    # =========================================================================
    # TELEHEALTH
    # =========================================================================
    CPTCode(
        code="99441",
        description="Telephone E/M service, 5-10 minutes",
        category=CPTCategory.EVALUATION_MANAGEMENT,
        work_rvu=0.25,
        typical_time_minutes=8,
        synonyms=["phone visit", "telephone visit", "phone call"],
        documentation_elements=[
            "Medical discussion by telephone",
            "Time documented",
            "Clinical assessment",
        ],
        common_diagnoses=["J06.9", "R05"],
    ),
    CPTCode(
        code="99442",
        description="Telephone E/M service, 11-20 minutes",
        category=CPTCategory.EVALUATION_MANAGEMENT,
        work_rvu=0.50,
        typical_time_minutes=15,
        synonyms=["phone visit", "telephone visit"],
        documentation_elements=[
            "Medical discussion by telephone",
            "Time documented",
            "Clinical assessment and plan",
        ],
        common_diagnoses=["I10", "E11.9"],
    ),

    # =========================================================================
    # RADIOLOGY - CT SCANS
    # =========================================================================
    CPTCode(
        code="70450",
        description="Computed tomography, head or brain; without contrast material",
        category=CPTCategory.RADIOLOGY,
        work_rvu=0.85,
        synonyms=["ct head", "ct brain", "head ct", "brain ct", "ct scan head"],
        documentation_elements=["CT head/brain performed", "Indication documented"],
        common_diagnoses=["R51", "S06.9X0A", "I63.9"],
    ),
    CPTCode(
        code="70460",
        description="Computed tomography, head or brain; with contrast material",
        category=CPTCategory.RADIOLOGY,
        work_rvu=1.13,
        synonyms=["ct head with contrast", "ct brain with contrast"],
        common_diagnoses=["R51", "C71.9"],
    ),
    CPTCode(
        code="71250",
        description="Computed tomography, thorax; without contrast material",
        category=CPTCategory.RADIOLOGY,
        work_rvu=1.16,
        synonyms=["ct chest", "chest ct", "ct thorax", "ct scan chest"],
        common_diagnoses=["R91.8", "J18.9", "C34.90"],
    ),
    CPTCode(
        code="71260",
        description="Computed tomography, thorax; with contrast material",
        category=CPTCategory.RADIOLOGY,
        work_rvu=1.38,
        synonyms=["ct chest with contrast", "cta chest"],
        common_diagnoses=["I26.99", "C34.90"],
    ),
    CPTCode(
        code="74176",
        description="Computed tomography, abdomen and pelvis; without contrast material",
        category=CPTCategory.RADIOLOGY,
        work_rvu=1.74,
        synonyms=["ct abdomen", "ct pelvis", "ct abd/pelvis", "abdominal ct", "ct scan abdomen"],
        common_diagnoses=["R10.9", "K35.80", "N20.0"],
    ),
    CPTCode(
        code="74177",
        description="Computed tomography, abdomen and pelvis; with contrast material",
        category=CPTCategory.RADIOLOGY,
        work_rvu=2.01,
        synonyms=["ct abdomen pelvis with contrast", "ct ap with contrast"],
        common_diagnoses=["R10.9", "C18.9", "K80.20"],
    ),

    # =========================================================================
    # RADIOLOGY - MRI
    # =========================================================================
    CPTCode(
        code="70551",
        description="Magnetic resonance imaging, brain; without contrast material",
        category=CPTCategory.RADIOLOGY,
        work_rvu=1.48,
        synonyms=["mri brain", "brain mri", "mri head", "head mri"],
        common_diagnoses=["R51", "G43.909", "I63.9"],
    ),
    CPTCode(
        code="70553",
        description="Magnetic resonance imaging, brain; without contrast material, followed by contrast and further sequences",
        category=CPTCategory.RADIOLOGY,
        work_rvu=2.10,
        synonyms=["mri brain with and without contrast", "mri brain w/wo"],
        common_diagnoses=["C71.9", "G35", "I63.9"],
    ),
    CPTCode(
        code="72141",
        description="Magnetic resonance imaging, spinal canal, cervical; without contrast material",
        category=CPTCategory.RADIOLOGY,
        work_rvu=1.48,
        synonyms=["mri cervical spine", "mri c-spine", "mri neck"],
        common_diagnoses=["M54.2", "M50.20"],
    ),
    CPTCode(
        code="72148",
        description="Magnetic resonance imaging, spinal canal, lumbar; without contrast material",
        category=CPTCategory.RADIOLOGY,
        work_rvu=1.48,
        synonyms=["mri lumbar spine", "mri l-spine", "mri lower back", "lumbar mri"],
        common_diagnoses=["M54.5", "M51.16"],
    ),
    CPTCode(
        code="73721",
        description="Magnetic resonance imaging, any joint of lower extremity; without contrast material",
        category=CPTCategory.RADIOLOGY,
        work_rvu=1.30,
        synonyms=["mri knee", "knee mri", "mri hip", "mri ankle"],
        common_diagnoses=["M23.90", "S83.509A"],
    ),
    CPTCode(
        code="73221",
        description="Magnetic resonance imaging, any joint of upper extremity; without contrast material",
        category=CPTCategory.RADIOLOGY,
        work_rvu=1.30,
        synonyms=["mri shoulder", "shoulder mri", "mri elbow", "mri wrist"],
        common_diagnoses=["M75.10", "S43.409A"],
    ),

    # =========================================================================
    # SURGERY - GI PROCEDURES
    # =========================================================================
    CPTCode(
        code="43239",
        description="Esophagogastroduodenoscopy with biopsy",
        category=CPTCategory.SURGERY,
        work_rvu=3.25,
        synonyms=["egd", "upper endoscopy", "egd with biopsy", "upper gi endoscopy", "esophagogastroduodenoscopy"],
        documentation_elements=["Procedure findings", "Biopsy sites", "Pathology report"],
        common_diagnoses=["K21.0", "K25.9", "K29.70"],
    ),
    CPTCode(
        code="45378",
        description="Colonoscopy, flexible; diagnostic",
        category=CPTCategory.SURGERY,
        work_rvu=3.69,
        synonyms=["colonoscopy", "diagnostic colonoscopy", "colon scope"],
        documentation_elements=["Procedure findings", "Quality of prep", "Extent of examination"],
        common_diagnoses=["Z12.11", "K92.1", "K57.30"],
    ),
    CPTCode(
        code="45380",
        description="Colonoscopy with biopsy",
        category=CPTCategory.SURGERY,
        work_rvu=4.43,
        synonyms=["colonoscopy with biopsy", "colon biopsy"],
        common_diagnoses=["K51.90", "K50.90", "D12.6"],
    ),
    CPTCode(
        code="45385",
        description="Colonoscopy with removal of polyp(s) by snare technique",
        category=CPTCategory.SURGERY,
        work_rvu=5.18,
        synonyms=["colonoscopy polypectomy", "polyp removal", "colonoscopy with polypectomy"],
        common_diagnoses=["D12.6", "K63.5"],
    ),

    # =========================================================================
    # VACCINATIONS / IMMUNIZATIONS
    # =========================================================================
    CPTCode(
        code="90471",
        description="Immunization administration (first vaccine/toxoid)",
        category=CPTCategory.MEDICINE,
        work_rvu=0.17,
        synonyms=["vaccine administration", "immunization", "vaccination", "shot administration"],
        documentation_elements=["Vaccine administered", "Route", "Site"],
        common_diagnoses=["Z23"],
    ),
    CPTCode(
        code="90472",
        description="Immunization administration (each additional vaccine/toxoid)",
        category=CPTCategory.MEDICINE,
        work_rvu=0.15,
        synonyms=["additional vaccine", "second vaccine"],
        common_diagnoses=["Z23"],
    ),
    CPTCode(
        code="90658",
        description="Influenza virus vaccine, split virus, for intramuscular use",
        category=CPTCategory.MEDICINE,
        synonyms=["flu shot", "flu vaccine", "influenza vaccine", "flu"],
        common_diagnoses=["Z23"],
    ),
    CPTCode(
        code="90715",
        description="Tetanus, diphtheria toxoids and acellular pertussis vaccine (Tdap)",
        category=CPTCategory.MEDICINE,
        synonyms=["tdap", "tetanus shot", "tetanus vaccine", "pertussis vaccine"],
        common_diagnoses=["Z23"],
    ),
    CPTCode(
        code="90732",
        description="Pneumococcal polysaccharide vaccine, 23-valent (PPSV23)",
        category=CPTCategory.MEDICINE,
        synonyms=["pneumonia vaccine", "pneumococcal vaccine", "ppsv23", "pneumovax"],
        common_diagnoses=["Z23"],
    ),
    CPTCode(
        code="90750",
        description="Zoster (shingles) vaccine, recombinant, adjuvanted (Shingrix)",
        category=CPTCategory.MEDICINE,
        synonyms=["shingles vaccine", "shingrix", "zoster vaccine", "herpes zoster vaccine"],
        common_diagnoses=["Z23"],
    ),

    # =========================================================================
    # PHYSICAL THERAPY / REHABILITATION
    # =========================================================================
    CPTCode(
        code="97110",
        description="Therapeutic procedure, therapeutic exercises",
        category=CPTCategory.MEDICINE,
        work_rvu=0.45,
        typical_time_minutes=15,
        synonyms=["therapeutic exercise", "pt exercises", "physical therapy", "exercise therapy"],
        common_diagnoses=["M54.5", "M17.9", "S83.509A"],
    ),
    CPTCode(
        code="97140",
        description="Manual therapy techniques (eg, mobilization, manipulation)",
        category=CPTCategory.MEDICINE,
        work_rvu=0.43,
        typical_time_minutes=15,
        synonyms=["manual therapy", "manipulation", "mobilization", "joint mobilization"],
        common_diagnoses=["M54.5", "M54.2", "M25.50"],
    ),
    CPTCode(
        code="97530",
        description="Therapeutic activities, direct patient contact",
        category=CPTCategory.MEDICINE,
        work_rvu=0.44,
        typical_time_minutes=15,
        synonyms=["therapeutic activities", "functional training", "adl training"],
        common_diagnoses=["M54.5", "I63.9", "S72.90XA"],
    ),
    CPTCode(
        code="97161",
        description="Physical therapy evaluation, low complexity",
        category=CPTCategory.MEDICINE,
        work_rvu=1.20,
        synonyms=["pt evaluation", "physical therapy eval", "pt eval low"],
        common_diagnoses=["M54.5", "M79.3"],
    ),
    CPTCode(
        code="97162",
        description="Physical therapy evaluation, moderate complexity",
        category=CPTCategory.MEDICINE,
        work_rvu=1.50,
        synonyms=["pt evaluation moderate", "physical therapy eval moderate"],
        common_diagnoses=["M54.5", "S83.509A", "M17.9"],
    ),

    # =========================================================================
    # SURGERY - ORTHOPEDIC
    # =========================================================================
    CPTCode(
        code="29881",
        description="Arthroscopy, knee, surgical; with meniscectomy",
        category=CPTCategory.SURGERY,
        work_rvu=8.67,
        synonyms=["knee arthroscopy", "knee scope", "meniscectomy", "meniscus surgery"],
        common_diagnoses=["M23.20", "S83.20XA"],
    ),
    CPTCode(
        code="27447",
        description="Arthroplasty, knee, condyle and plateau; medial AND lateral compartments (total knee)",
        category=CPTCategory.SURGERY,
        work_rvu=20.69,
        synonyms=["total knee replacement", "tkr", "knee replacement", "total knee arthroplasty"],
        common_diagnoses=["M17.11", "M17.12"],
    ),
    CPTCode(
        code="27130",
        description="Arthroplasty, acetabular and proximal femoral prosthetic replacement (total hip)",
        category=CPTCategory.SURGERY,
        work_rvu=20.05,
        synonyms=["total hip replacement", "thr", "hip replacement", "total hip arthroplasty"],
        common_diagnoses=["M16.11", "S72.001A"],
    ),

    # =========================================================================
    # CARDIOVASCULAR PROCEDURES
    # =========================================================================
    CPTCode(
        code="93306",
        description="Echocardiography, transthoracic, with Doppler",
        category=CPTCategory.MEDICINE,
        work_rvu=1.50,
        synonyms=["echo", "echocardiogram", "tte", "transthoracic echo", "cardiac echo"],
        common_diagnoses=["I50.9", "I25.10", "I42.9"],
    ),
    CPTCode(
        code="93458",
        description="Catheter placement in coronary artery(s), selective coronary angiography",
        category=CPTCategory.SURGERY,
        work_rvu=6.37,
        synonyms=["cardiac cath", "heart cath", "coronary angiography", "left heart cath"],
        common_diagnoses=["I25.10", "I21.9", "R07.9"],
    ),
    CPTCode(
        code="92928",
        description="Percutaneous coronary intervention; single major coronary artery or branch",
        category=CPTCategory.SURGERY,
        work_rvu=12.43,
        synonyms=["pci", "coronary stent", "angioplasty", "ptca", "stent placement"],
        common_diagnoses=["I21.9", "I25.10"],
    ),
]


# Build synonym index
SYNONYM_TO_CPT: dict[str, list[str]] = {}
for _code in CPT_CODES:
    for syn in _code.synonyms:
        syn_lower = syn.lower()
        if syn_lower not in SYNONYM_TO_CPT:
            SYNONYM_TO_CPT[syn_lower] = []
        SYNONYM_TO_CPT[syn_lower].append(_code.code)


# ============================================================================
# Load Extended CPT/HCPCS Codes from Fixture
# ============================================================================

# Use the expanded CPT codes fixture file if available, otherwise fall back to original
FIXTURE_FILE_FULL = Path(__file__).parent.parent.parent / "fixtures" / "cpt_codes_full.json"
FIXTURE_FILE_ORIGINAL = Path(__file__).parent.parent.parent / "fixtures" / "cpt_codes.json"
FIXTURE_FILE = FIXTURE_FILE_FULL if FIXTURE_FILE_FULL.exists() else FIXTURE_FILE_ORIGINAL


# =============================================================================
# ADDITIONAL CLINICAL SYNONYMS - Maps common clinical terms to CPT codes
# =============================================================================
CLINICAL_SYNONYM_MAPPINGS: dict[str, list[str]] = {
    # E/M Office Visits
    "office visit": ["99202", "99203", "99204", "99205", "99211", "99212", "99213", "99214", "99215"],
    "new patient visit": ["99202", "99203", "99204", "99205"],
    "established patient visit": ["99211", "99212", "99213", "99214", "99215"],
    "follow up": ["99211", "99212", "99213", "99214", "99215"],
    "routine visit": ["99213", "99214"],
    "level 3 visit": ["99203", "99213"],
    "level 4 visit": ["99204", "99214"],
    "level 5 visit": ["99205", "99215"],

    # Hospital
    "hospital admission": ["99221", "99222", "99223"],
    "inpatient admission": ["99221", "99222", "99223"],
    "hospital visit": ["99231", "99232", "99233"],
    "subsequent hospital": ["99231", "99232", "99233"],
    "discharge": ["99238", "99239"],
    "hospital discharge": ["99238", "99239"],

    # Emergency
    "er visit": ["99281", "99282", "99283", "99284", "99285"],
    "ed visit": ["99281", "99282", "99283", "99284", "99285"],
    "emergency visit": ["99281", "99282", "99283", "99284", "99285"],
    "emergency room": ["99281", "99282", "99283", "99284", "99285"],

    # Critical Care
    "critical care": ["99291", "99292"],
    "icu": ["99291", "99292"],

    # GI Procedures
    "colonoscopy": ["45378", "45380", "45381", "45382", "45384", "45385", "45386", "45388"],
    "screening colonoscopy": ["45378"],
    "colonoscopy with biopsy": ["45380"],
    "colonoscopy with polypectomy": ["45384", "45385"],
    "egd": ["43235", "43239", "43249", "43251"],
    "upper endoscopy": ["43235", "43239", "43249"],

    # Radiology
    "chest xray": ["71045", "71046", "71047", "71048"],
    "cxr": ["71045", "71046"],
    "chest x-ray": ["71045", "71046"],
    "ct head": ["70450", "70460", "70470"],
    "ct brain": ["70450", "70460", "70470"],
    "ct chest": ["71250", "71260", "71270"],
    "ct abdomen": ["74150", "74160", "74170", "74176", "74177", "74178"],
    "ct abdomen pelvis": ["74176", "74177", "74178"],
    "mri brain": ["70551", "70552", "70553"],
    "mri lumbar": ["72148", "72149", "72158"],
    "mri knee": ["73721", "73722", "73723"],
    "ultrasound abdomen": ["76700", "76705"],
    "echocardiogram": ["93306", "93307", "93308"],
    "echo": ["93306", "93307", "93308"],
    "stress test": ["93015", "93016", "93017", "93018"],
    "mammogram": ["77065", "77066", "77067"],
    "dexa": ["77080", "77081"],
    "bone density": ["77080", "77081"],

    # Cardiac
    "ecg": ["93000", "93005", "93010"],
    "ekg": ["93000", "93005", "93010"],
    "electrocardiogram": ["93000", "93005", "93010"],
    "holter": ["93224", "93225", "93226", "93227"],
    "cardiac cath": ["93451", "93452", "93453", "93454", "93455", "93456", "93457", "93458", "93459"],
    "heart cath": ["93458", "93459", "93460"],
    "pci": ["92920", "92924", "92928", "92933", "92937", "92941", "92943"],
    "stent": ["92928", "92929", "92933", "92934"],

    # Labs
    "cbc": ["85025", "85027"],
    "complete blood count": ["85025", "85027"],
    "cmp": ["80053"],
    "comprehensive metabolic": ["80053"],
    "bmp": ["80048"],
    "basic metabolic": ["80048"],
    "lipid panel": ["80061"],
    "hemoglobin a1c": ["83036"],
    "hba1c": ["83036"],
    "a1c": ["83036"],
    "tsh": ["84443"],
    "psa": ["84153", "84154"],
    "urinalysis": ["81001", "81002", "81003"],
    "ua": ["81001", "81002", "81003"],
    "urine culture": ["87086", "87088"],
    "blood culture": ["87040"],
    "strep test": ["87880"],
    "flu test": ["87804"],
    "covid test": ["87635", "87426"],
    "pt inr": ["85610", "85730"],
    "troponin": ["84484"],
    "bnp": ["83880"],

    # Injections
    "injection": ["96372", "96373", "96374", "96375"],
    "im injection": ["96372"],
    "iv injection": ["96374"],
    "joint injection": ["20600", "20605", "20610"],
    "knee injection": ["20610"],
    "shoulder injection": ["20610"],
    "steroid injection": ["20610", "62320", "62321", "62322", "62323"],
    "epidural": ["62320", "62321", "62322", "62323"],
    "trigger point": ["20552", "20553"],

    # Vaccines
    "flu shot": ["90658", "90686", "90688"],
    "flu vaccine": ["90658", "90686", "90688"],
    "influenza vaccine": ["90658", "90686", "90688"],
    "tdap": ["90715"],
    "tetanus": ["90714", "90715"],
    "pneumonia vaccine": ["90670", "90671", "90732"],
    "shingles vaccine": ["90750"],
    "covid vaccine": ["91300", "91301", "91303"],

    # Surgery - Orthopedic
    "knee arthroscopy": ["29870", "29871", "29873", "29874", "29875", "29876", "29877", "29879", "29880", "29881"],
    "knee scope": ["29870", "29881"],
    "meniscectomy": ["29880", "29881"],
    "acl repair": ["29888"],
    "total knee replacement": ["27447"],
    "tkr": ["27447"],
    "total hip replacement": ["27130"],
    "thr": ["27130"],
    "hip replacement": ["27130"],
    "rotator cuff repair": ["23410", "23412", "23420", "29827"],
    "carpal tunnel": ["64721"],

    # Surgery - General
    "appendectomy": ["44950", "44955", "44960", "44970"],
    "cholecystectomy": ["47562", "47563", "47564", "47600", "47605"],
    "lap chole": ["47562", "47563", "47564"],
    "gallbladder removal": ["47562", "47563", "47564"],
    "hernia repair": ["49505", "49507", "49520", "49521", "49560", "49561", "49650", "49651"],
    "inguinal hernia": ["49505", "49507", "49520", "49521", "49650"],
    "umbilical hernia": ["49580", "49582", "49585", "49587"],
    "biopsy": ["11102", "11104", "11106"],
    "skin biopsy": ["11102", "11104", "11106"],
    "wound repair": ["12001", "12002", "12004", "12005", "12006", "12007"],
    "laceration repair": ["12001", "12002", "12004", "12005"],

    # Physical Therapy
    "physical therapy": ["97110", "97112", "97116", "97140", "97530", "97535"],
    "pt": ["97110", "97112", "97116", "97140"],
    "therapeutic exercise": ["97110"],
    "manual therapy": ["97140"],
    "gait training": ["97116"],

    # Mental Health
    "psychotherapy": ["90832", "90834", "90837", "90847"],
    "therapy session": ["90832", "90834", "90837"],
    "counseling": ["90832", "90834", "90837", "90847"],
    "psychiatric evaluation": ["90791", "90792"],
    "psych eval": ["90791", "90792"],

    # Sleep
    "sleep study": ["95810", "95811"],
    "polysomnography": ["95810", "95811"],

    # Pulmonary
    "pulmonary function": ["94010", "94060", "94726", "94727", "94728", "94729"],
    "pft": ["94010", "94060", "94726", "94727", "94728", "94729"],
    "spirometry": ["94010", "94060"],

    # Ophthalmology
    "cataract surgery": ["66982", "66984"],
    "cataract removal": ["66982", "66984"],
    "eye exam": ["92002", "92004", "92012", "92014"],

    # Dialysis
    "dialysis": ["90935", "90937", "90945", "90947"],
    "hemodialysis": ["90935", "90937"],

    # Chemotherapy
    "chemotherapy": ["96401", "96402", "96409", "96411", "96413", "96415"],
    "chemo": ["96401", "96402", "96409", "96411", "96413", "96415"],
    "infusion": ["96360", "96361", "96365", "96366", "96367", "96374", "96375"],

    # Wound Care
    "wound care": ["97597", "97598", "97602", "97605", "97606"],
    "debridement": ["11042", "11043", "11044", "97597", "97598"],
}


# =============================================================================
# DOCUMENTATION REQUIREMENTS - Required elements for code categories
# =============================================================================
DOCUMENTATION_REQUIREMENTS: dict[str, list[str]] = {
    # E/M Office New Patient
    "99202": ["Chief complaint", "History of present illness", "MDM straightforward OR time 15-29 min"],
    "99203": ["Chief complaint", "HPI", "Review of systems", "MDM low complexity OR time 30-44 min"],
    "99204": ["Chief complaint", "HPI", "ROS", "PFSH", "MDM moderate complexity OR time 45-59 min", "Prescription drug management"],
    "99205": ["Chief complaint", "Comprehensive HPI", "Complete ROS", "Complete PFSH", "MDM high complexity OR time 60-74 min"],

    # E/M Office Established Patient
    "99211": ["Minimal problem", "May not require physician presence"],
    "99212": ["Chief complaint", "Brief HPI", "MDM straightforward OR time 10-19 min"],
    "99213": ["Chief complaint", "HPI", "2+ self-limited problems OR 1 stable chronic illness", "MDM low OR time 20-29 min"],
    "99214": ["Chief complaint", "Extended HPI", "1+ chronic illness with mild exacerbation", "Prescription drug management", "MDM moderate OR time 30-39 min"],
    "99215": ["Chief complaint", "Comprehensive HPI", "Chronic illness with severe exacerbation", "Drug therapy requiring intensive monitoring", "MDM high OR time 40-54 min"],

    # Hospital
    "99221": ["Chief complaint", "Comprehensive history", "Admission orders", "MDM low/moderate complexity OR 40 min"],
    "99222": ["Comprehensive history", "Comprehensive examination", "Multiple conditions requiring workup", "MDM moderate OR 55 min"],
    "99223": ["Comprehensive history", "Comprehensive examination", "Severely ill patient", "Multiple diagnoses requiring active management", "MDM high OR 75 min"],

    # Emergency
    "99281": ["Chief complaint", "Self-limited/minor problem"],
    "99283": ["Chief complaint", "Extended history", "Moderately severe problem"],
    "99284": ["Chief complaint", "Comprehensive history", "High severity problem requiring urgent evaluation"],
    "99285": ["Chief complaint", "Comprehensive history", "Life-threatening condition", "Immediate intervention required"],

    # Critical Care
    "99291": ["Critical illness/injury documentation", "Time spent in critical care activities", "Vital organ dysfunction", "Direct personal management"],

    # Procedures
    "45378": ["Indication for procedure", "Prep quality", "Extent of examination", "Findings", "Recommendations for follow-up"],
    "45380": ["Indication", "Prep quality", "Biopsy sites documented", "Pathology correlation"],
    "45385": ["Indication", "Number and location of polyps", "Removal technique", "Pathology report"],
    "43239": ["Indication", "Procedure findings", "Biopsy sites", "Pathology report"],
}


def _get_cpt_category(domain: str, concept_class: str) -> CPTCategory:
    """Determine CPT category from domain and concept class."""
    domain_lower = domain.lower() if domain else ""
    class_lower = concept_class.lower() if concept_class else ""

    if "evaluation" in class_lower or "e/m" in class_lower:
        return CPTCategory.EVALUATION_MANAGEMENT
    elif "anesthesia" in class_lower:
        return CPTCategory.ANESTHESIA
    elif "surgery" in class_lower or "surgical" in class_lower:
        return CPTCategory.SURGERY
    elif "radiology" in class_lower or "imaging" in class_lower:
        return CPTCategory.RADIOLOGY
    elif "pathology" in class_lower or "laboratory" in class_lower or "lab" in class_lower:
        return CPTCategory.PATHOLOGY
    elif domain_lower == "measurement":
        return CPTCategory.PATHOLOGY
    elif domain_lower == "procedure":
        return CPTCategory.SURGERY
    else:
        return CPTCategory.MEDICINE


def load_extended_cpt_codes() -> tuple[list[CPTCode], dict[str, list[str]]]:
    """Load extended CPT/HCPCS codes from fixture file.

    Returns:
        Tuple of (list of CPTCode objects, synonym-to-code index)
    """
    codes: list[CPTCode] = []
    synonym_index: dict[str, list[str]] = {}

    # Start with core codes
    codes.extend(CPT_CODES)
    for _code in CPT_CODES:
        for syn in _code.synonyms:
            syn_lower = syn.lower()
            if syn_lower not in synonym_index:
                synonym_index[syn_lower] = []
            if _code.code not in synonym_index[syn_lower]:
                synonym_index[syn_lower].append(_code.code)

    # Load from fixture file if available
    if FIXTURE_FILE.exists():
        try:
            with open(FIXTURE_FILE, "r") as f:
                data = json.load(f)

            concepts = data.get("concepts", [])
            loaded_codes = set(c.code for c in codes)

            for concept in concepts:
                code_str = concept.get("concept_code", "")
                if not code_str or code_str in loaded_codes:
                    continue

                # Determine category from the concept data
                cat_str = concept.get("category", "")
                if cat_str:
                    category = _get_cpt_category_from_string(cat_str)
                else:
                    category = _get_cpt_category(
                        concept.get("domain_id", ""),
                        concept.get("concept_class_id", "")
                    )

                synonyms = concept.get("synonyms", [])
                description = concept.get("concept_name", "")

                # Get RVU and time from concept if available
                work_rvu = concept.get("work_rvu", 0.0)
                typical_time = concept.get("typical_time_minutes", 0)

                # Get documentation requirements if defined
                doc_elements = DOCUMENTATION_REQUIREMENTS.get(code_str, [])

                cpt_code = CPTCode(
                    code=code_str,
                    description=description,
                    category=category,
                    work_rvu=work_rvu,
                    typical_time_minutes=typical_time,
                    synonyms=synonyms,
                    documentation_elements=doc_elements,
                )

                codes.append(cpt_code)
                loaded_codes.add(code_str)

                # Index synonyms
                for syn in synonyms:
                    syn_lower = syn.lower()
                    if syn_lower not in synonym_index:
                        synonym_index[syn_lower] = []
                    if code_str not in synonym_index[syn_lower]:
                        synonym_index[syn_lower].append(code_str)

                # Index description words
                desc_words = description.lower().split()
                meaningful_words = [w for w in desc_words if len(w) > 4 and w not in
                    {"services", "procedure", "other", "unspecified", "without", "with"}]
                for word in meaningful_words[:3]:
                    if word not in synonym_index:
                        synonym_index[word] = []
                    if code_str not in synonym_index[word]:
                        synonym_index[word].append(code_str)

            logger.info(f"Loaded {len(codes)} CPT/HCPCS codes ({len(codes) - len(CPT_CODES)} from fixture)")
        except Exception as e:
            logger.warning(f"Failed to load extended CPT codes from {FIXTURE_FILE}: {e}")
    else:
        logger.warning(f"CPT fixture file not found: {FIXTURE_FILE}")

    # Add clinical synonym mappings to the index
    for synonym, code_list in CLINICAL_SYNONYM_MAPPINGS.items():
        syn_lower = synonym.lower()
        if syn_lower not in synonym_index:
            synonym_index[syn_lower] = []
        for code_str in code_list:
            if code_str not in synonym_index[syn_lower]:
                synonym_index[syn_lower].append(code_str)

    return codes, synonym_index


def _get_cpt_category_from_string(cat_str: str) -> CPTCategory:
    """Determine CPT category from category string."""
    cat_lower = cat_str.lower()

    if "evaluation" in cat_lower or "e/m" in cat_lower:
        return CPTCategory.EVALUATION_MANAGEMENT
    elif "anesthesia" in cat_lower:
        return CPTCategory.ANESTHESIA
    elif "surgery" in cat_lower:
        return CPTCategory.SURGERY
    elif "radiology" in cat_lower:
        return CPTCategory.RADIOLOGY
    elif "pathology" in cat_lower or "laboratory" in cat_lower:
        return CPTCategory.PATHOLOGY
    elif "medicine" in cat_lower:
        return CPTCategory.MEDICINE
    elif "category ii" in cat_lower:
        return CPTCategory.MEDICINE  # Category II maps to Medicine
    elif "category iii" in cat_lower:
        return CPTCategory.MEDICINE  # Category III maps to Medicine
    else:
        return CPTCategory.MEDICINE


# ============================================================================
# CPT Suggester Service
# ============================================================================

# Singleton instance and lock
_cpt_service: "CPTSuggesterService | None" = None
_cpt_lock = threading.Lock()


def get_cpt_suggester_service() -> "CPTSuggesterService":
    """Get the singleton CPT suggester service instance."""
    global _cpt_service
    if _cpt_service is None:
        with _cpt_lock:
            if _cpt_service is None:
                _cpt_service = CPTSuggesterService()
    return _cpt_service


def reset_cpt_suggester_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _cpt_service
    with _cpt_lock:
        _cpt_service = None


class CPTSuggesterService:
    """Service for suggesting CPT codes with CER citations."""

    def __init__(self) -> None:
        """Initialize the CPT suggester service."""
        self._codes: dict[str, CPTCode] = {}
        self._synonym_index: dict[str, list[str]] = {}

        # Load extended codes from fixture
        codes, self._synonym_index = load_extended_cpt_codes()

        for code in codes:
            self._codes[code.code] = code

        logger.info(f"CPT suggester initialized with {len(self._codes)} codes, {len(self._synonym_index)} synonyms")

    def suggest_codes(
        self,
        query: str,
        clinical_context: dict[str, str] | None = None,
        max_suggestions: int = 10,
    ) -> CPTSuggestionResult:
        """Suggest CPT codes with CER citations.

        Args:
            query: Description of procedure/service
            clinical_context: Optional context dict with keys like
                             'time_spent', 'mdm_complexity', 'new_patient',
                             'setting', 'diagnoses'
            max_suggestions: Maximum number of suggestions

        Returns:
            CPTSuggestionResult with CER-cited suggestions.
        """
        query_lower = query.lower().strip()
        clinical_context = clinical_context or {}
        suggestions: list[CPTSuggestion] = []
        seen_codes: set[str] = set()

        # 1. Exact synonym match
        if query_lower in self._synonym_index:
            for code_str in self._synonym_index[query_lower]:
                if code_str in self._codes and code_str not in seen_codes:
                    code = self._codes[code_str]
                    suggestion = self._create_suggestion_with_cer(
                        code, clinical_context,
                        match_type="exact_synonym",
                        matched_term=query_lower
                    )
                    suggestions.append(suggestion)
                    seen_codes.add(code_str)

        # 2. Partial synonym match
        for synonym, code_list in self._synonym_index.items():
            if query_lower in synonym or synonym in query_lower:
                for code_str in code_list:
                    if code_str in self._codes and code_str not in seen_codes:
                        code = self._codes[code_str]
                        suggestion = self._create_suggestion_with_cer(
                            code, clinical_context,
                            match_type="partial_synonym",
                            matched_term=synonym
                        )
                        suggestions.append(suggestion)
                        seen_codes.add(code_str)

        # 3. Description search
        query_words = set(query_lower.split())
        for code in self._codes.values():
            if code.code in seen_codes:
                continue

            desc_lower = code.description.lower()
            desc_words = set(desc_lower.split())

            stopwords = {"of", "the", "and", "or", "a", "an", "with", "without", "for", "to"}
            common_words = (query_words & desc_words) - stopwords

            if len(common_words) >= 2:
                suggestion = self._create_suggestion_with_cer(
                    code, clinical_context,
                    match_type="description",
                    matched_term=", ".join(common_words)
                )
                suggestions.append(suggestion)
                seen_codes.add(code.code)

        # Sort by confidence
        confidence_order = {ConfidenceLevel.HIGH: 0, ConfidenceLevel.MEDIUM: 1, ConfidenceLevel.LOW: 2}
        suggestions.sort(key=lambda s: confidence_order[s.confidence])

        # Identify documentation gaps
        documentation_gaps = self._identify_documentation_gaps(suggestions, clinical_context)

        # Generate coding tips
        coding_tips = self._generate_coding_tips(query, suggestions, clinical_context)

        return CPTSuggestionResult(
            query=query,
            clinical_context=clinical_context,
            suggestions=suggestions[:max_suggestions],
            total_matches=len(suggestions),
            documentation_gaps=documentation_gaps,
            coding_tips=coding_tips,
        )

    def _create_suggestion_with_cer(
        self,
        code: CPTCode,
        clinical_context: dict[str, str],
        match_type: str,
        matched_term: str,
    ) -> CPTSuggestion:
        """Create a CPT suggestion with CER citation."""

        # Build evidence from clinical context
        evidence: list[str] = []

        # Time-based evidence
        if "time_spent" in clinical_context:
            time = int(clinical_context.get("time_spent", 0))
            if time > 0:
                evidence.append(f"Total time spent: {time} minutes")

        # MDM complexity evidence
        if "mdm_complexity" in clinical_context:
            evidence.append(f"Medical decision making: {clinical_context['mdm_complexity']} complexity")

        # Setting evidence
        if "setting" in clinical_context:
            evidence.append(f"Setting: {clinical_context['setting']}")

        # Patient type
        if "new_patient" in clinical_context:
            patient_type = "new" if clinical_context.get("new_patient", "").lower() in ["true", "yes", "1"] else "established"
            evidence.append(f"Patient type: {patient_type}")

        # Diagnoses
        if "diagnoses" in clinical_context:
            evidence.append(f"Diagnoses documented: {clinical_context['diagnoses']}")

        # If no context provided, use generic evidence
        if not evidence:
            evidence = [f"Match based on: {matched_term}"]

        # Determine confidence
        if match_type == "exact_synonym" and len(evidence) > 2:
            confidence = ConfidenceLevel.HIGH
        elif match_type in ["exact_synonym", "partial_synonym"]:
            confidence = ConfidenceLevel.MEDIUM
        else:
            confidence = ConfidenceLevel.LOW

        # Build reasoning
        reasoning_parts = []
        if "E/M" in code.description or "visit" in code.description.lower():
            reasoning_parts.append(
                f"The code {code.code} is appropriate for E/M services when "
                f"documentation supports the corresponding level of complexity."
            )
        if code.typical_time_minutes > 0:
            reasoning_parts.append(
                f"Typical time for this service is {code.typical_time_minutes} minutes."
            )
        if code.work_rvu > 0:
            reasoning_parts.append(f"Work RVU: {code.work_rvu}")

        reasoning = " ".join(reasoning_parts) if reasoning_parts else (
            f"This code matches based on {match_type} matching for '{matched_term}'."
        )

        # Create CER citation
        cer = CERCitation(
            claim=f"{code.code} ({code.description}) is appropriate for this service",
            evidence=evidence,
            reasoning=reasoning,
            strength=confidence,
        )

        # Build documentation checklist
        doc_checklist = [
            DocumentationRequirement(
                element=elem,
                present=None,  # Unknown without parsing actual documentation
                notes=""
            )
            for elem in code.documentation_elements
        ]

        # Get supporting diagnoses
        supporting_dx = []
        for dx in code.common_diagnoses[:5]:
            # In a full implementation, would lookup ICD-10 descriptions
            supporting_dx.append((dx, f"Common diagnosis for {code.code}"))

        # Get alternative codes
        alternatives = []
        for other_code in self._codes.values():
            if other_code.code != code.code and other_code.category == code.category:
                if code.code.startswith("992") and other_code.code.startswith("992"):
                    # Same E/M category
                    alternatives.append((other_code.code, other_code.description))

        # Build coding notes
        coding_notes = []
        if code.add_on_codes:
            coding_notes.append(f"Consider add-on codes: {', '.join(code.add_on_codes[:3])}")
        if code.global_period:
            coding_notes.append(f"Global period: {code.global_period}")
        if code.common_modifiers:
            mod_str = ", ".join([f"{m[0]} ({m[1]})" for m in code.common_modifiers[:3]])
            coding_notes.append(f"Common modifiers: {mod_str}")

        return CPTSuggestion(
            code=code.code,
            description=code.description,
            category=code.category.value,
            confidence=confidence,
            cer_citation=cer,
            work_rvu=code.work_rvu,
            typical_time_minutes=code.typical_time_minutes,
            suggested_modifiers=code.common_modifiers[:5],
            documentation_checklist=doc_checklist,
            supporting_diagnoses=supporting_dx,
            alternative_codes=alternatives[:5],
            coding_notes=coding_notes,
        )

    def _identify_documentation_gaps(
        self,
        suggestions: list[CPTSuggestion],
        clinical_context: dict[str, str],
    ) -> list[str]:
        """Identify documentation gaps that could affect coding."""
        gaps = []

        # Check for time documentation
        has_time = "time_spent" in clinical_context
        em_codes = [s for s in suggestions if s.category == "Evaluation and Management"]
        if em_codes and not has_time:
            gaps.append("Total time spent not documented - required for time-based coding")

        # Check for MDM complexity
        if em_codes and "mdm_complexity" not in clinical_context:
            gaps.append("Medical decision making complexity not specified")

        # Check for patient type
        if em_codes and "new_patient" not in clinical_context:
            gaps.append("Patient type (new vs established) not documented")

        return gaps

    def _generate_coding_tips(
        self,
        query: str,
        suggestions: list[CPTSuggestion],
        clinical_context: dict[str, str],
    ) -> list[str]:
        """Generate coding tips based on context."""
        tips = []

        # E/M specific tips
        em_codes = [s for s in suggestions if "992" in s.code]
        if em_codes:
            tips.append("For E/M coding, document either time OR MDM complexity (whichever supports higher level)")

            if "time_spent" in clinical_context:
                time = int(clinical_context.get("time_spent", 0))
                if time > 40:
                    tips.append("Consider prolonged services codes (99354-99357) if time exceeds typical")

        # Hospital vs office tips
        query_lower = query.lower()
        if "hospital" in query_lower or "inpatient" in query_lower:
            tips.append("For hospital E/M, use 99221-99223 for admission, 99231-99233 for subsequent")
        elif "emergency" in query_lower or "ed" in query_lower:
            tips.append("ED visits (99281-99285) do not distinguish new vs established patients")

        # Procedure tips
        if any(s.category == "Radiology" for s in suggestions):
            tips.append("For radiology, specify professional (26) vs technical (TC) component if split billing")

        return tips[:5]

    def get_code(self, code: str) -> CPTCode | None:
        """Get a specific CPT code."""
        return self._codes.get(code)

    def search_codes(self, query: str, limit: int = 20) -> list[CPTCode]:
        """Search for codes by description or synonym."""
        query_lower = query.lower()
        matches = []

        for code in self._codes.values():
            if query_lower in code.description.lower():
                matches.append(code)
                continue
            if any(query_lower in syn.lower() for syn in code.synonyms):
                matches.append(code)

        return matches[:limit]

    def get_codes_by_category(self, category: CPTCategory) -> list[CPTCode]:
        """Get all codes in a category."""
        return [code for code in self._codes.values() if code.category == category]

    def get_stats(self) -> dict:
        """Get statistics about the code database."""
        by_category: dict[str, int] = {}

        for code in self._codes.values():
            cat = code.category.value
            by_category[cat] = by_category.get(cat, 0) + 1

        return {
            "total_codes": len(self._codes),
            "total_synonyms": len(self._synonym_index),
            "by_category": by_category,
        }

    # =========================================================================
    # AI-POWERED SUGGESTIONS FROM CLINICAL TEXT
    # =========================================================================

    def suggest_codes_from_text(
        self,
        clinical_text: str,
        encounter_context: dict[str, Any] | None = None,
        max_suggestions: int = 15,
    ) -> "TextCodeSuggestionResult":
        """AI-powered code suggestion from clinical text.

        Extracts diagnoses from clinical notes and suggests ICD-10/CPT codes
        with confidence scores and cited evidence from the text.

        Args:
            clinical_text: Clinical note text (progress note, H&P, etc.)
            encounter_context: Optional context (setting, patient type, etc.)
            max_suggestions: Maximum suggestions to return

        Returns:
            TextCodeSuggestionResult with suggestions and evidence
        """
        import re
        import time
        from uuid import uuid4

        start_time = time.perf_counter()
        encounter_context = encounter_context or {}
        suggestions: list["TextCodeSuggestion"] = []

        # Extract clinical concepts from text using pattern matching
        extracted_concepts = self._extract_clinical_concepts(clinical_text)

        # For each concept, suggest codes
        for concept in extracted_concepts:
            # Get CPT suggestions for procedures
            if concept["type"] == "procedure":
                cpt_result = self.suggest_codes(
                    query=concept["text"],
                    clinical_context=encounter_context,
                    max_suggestions=3,
                )
                for s in cpt_result.suggestions:
                    suggestions.append(TextCodeSuggestion(
                        code=s.code,
                        code_type="CPT",
                        description=s.description,
                        confidence=0.85 if s.confidence == ConfidenceLevel.HIGH else 0.65 if s.confidence == ConfidenceLevel.MEDIUM else 0.45,
                        evidence_text=concept["evidence"],
                        evidence_span=(concept["start"], concept["end"]),
                        rationale=s.cer_citation.claim if s.cer_citation else f"Matched '{concept['text']}'",
                        category=s.category,
                        work_rvu=s.work_rvu,
                    ))

        # E/M code suggestion based on encounter context
        em_suggestion = self._suggest_em_code(clinical_text, encounter_context)
        if em_suggestion:
            suggestions.insert(0, em_suggestion)

        # Sort by confidence
        suggestions.sort(key=lambda s: s.confidence, reverse=True)

        processing_time = (time.perf_counter() - start_time) * 1000

        return TextCodeSuggestionResult(
            request_id=str(uuid4()),
            text_length=len(clinical_text),
            suggestions=suggestions[:max_suggestions],
            total_concepts=len(extracted_concepts),
            em_level=em_suggestion.code if em_suggestion else None,
            processing_time_ms=round(processing_time, 2),
        )

    def _extract_clinical_concepts(self, text: str) -> list[dict[str, Any]]:
        """Extract clinical concepts from text using pattern matching."""
        import re

        concepts = []
        text_lower = text.lower()

        # Procedure patterns
        procedure_patterns = [
            (r"performed\s+([\w\s]+(?:ectomy|oscopy|otomy|plasty|ography))", "procedure"),
            (r"underwent\s+([\w\s]+(?:surgery|procedure|biopsy|injection))", "procedure"),
            (r"(ct\s+scan|mri|x-?ray|ultrasound|ecg|ekg|echo)\s+(?:of\s+)?(?:the\s+)?([\w\s]+)", "imaging"),
            (r"(colonoscopy|endoscopy|bronchoscopy|arthroscopy)", "procedure"),
            (r"(injection|vaccination|immunization)\s+(?:of\s+|with\s+)?([\w\s]+)?", "procedure"),
        ]

        for pattern, concept_type in procedure_patterns:
            for match in re.finditer(pattern, text_lower):
                concepts.append({
                    "text": match.group(0).strip(),
                    "type": concept_type,
                    "start": match.start(),
                    "end": match.end(),
                    "evidence": text[max(0, match.start()-50):min(len(text), match.end()+50)].strip(),
                })

        return concepts

    def _suggest_em_code(
        self,
        clinical_text: str,
        encounter_context: dict[str, Any]
    ) -> "TextCodeSuggestion | None":
        """Suggest E/M code based on clinical text and context."""
        import re

        text_lower = clinical_text.lower()

        # Time-based detection
        time_match = re.search(r"(?:total\s+)?(?:time|duration)[:\s]+(\d+)\s*(?:min|minutes)", text_lower)
        documented_time = int(time_match.group(1)) if time_match else None

        # Check for patient type
        is_new = encounter_context.get("new_patient", False)
        if "new patient" in text_lower:
            is_new = True
        elif "established patient" in text_lower or "follow up" in text_lower:
            is_new = False

        # Check for setting
        setting = encounter_context.get("setting", "office")
        if "emergency" in text_lower or "ed " in text_lower:
            setting = "emergency"
        elif "hospital" in text_lower or "inpatient" in text_lower:
            setting = "inpatient"

        # Determine MDM complexity based on text analysis
        mdm_complexity = self._assess_mdm_complexity(text_lower)

        # Select E/M code
        if setting == "emergency":
            codes = {"low": "99283", "moderate": "99284", "high": "99285"}
            code = codes.get(mdm_complexity, "99283")
        elif setting == "inpatient":
            codes = {"low": "99221", "moderate": "99222", "high": "99223"}
            code = codes.get(mdm_complexity, "99222")
        elif is_new:
            if documented_time:
                if documented_time >= 60:
                    code = "99205"
                elif documented_time >= 45:
                    code = "99204"
                elif documented_time >= 30:
                    code = "99203"
                else:
                    code = "99202"
            else:
                codes = {"low": "99203", "moderate": "99204", "high": "99205"}
                code = codes.get(mdm_complexity, "99203")
        else:  # Established
            if documented_time:
                if documented_time >= 40:
                    code = "99215"
                elif documented_time >= 30:
                    code = "99214"
                elif documented_time >= 20:
                    code = "99213"
                else:
                    code = "99212"
            else:
                codes = {"straightforward": "99212", "low": "99213", "moderate": "99214", "high": "99215"}
                code = codes.get(mdm_complexity, "99213")

        # Get code details
        cpt_code = self.get_code(code)
        if not cpt_code:
            return None

        rationale_parts = []
        if documented_time:
            rationale_parts.append(f"Time documented: {documented_time} minutes")
        rationale_parts.append(f"MDM complexity: {mdm_complexity}")
        if is_new:
            rationale_parts.append("New patient")
        else:
            rationale_parts.append("Established patient")

        return TextCodeSuggestion(
            code=code,
            code_type="CPT",
            description=cpt_code.description,
            confidence=0.85 if documented_time else 0.70,
            evidence_text=time_match.group(0) if time_match else "MDM-based selection",
            evidence_span=(time_match.start(), time_match.end()) if time_match else (0, 0),
            rationale="; ".join(rationale_parts),
            category="Evaluation and Management",
            work_rvu=cpt_code.work_rvu,
        )

    def _assess_mdm_complexity(self, text: str) -> str:
        """Assess MDM complexity from clinical text."""
        score = 0

        # Number of problems addressed
        problem_indicators = [
            "chronic", "condition", "diagnosis", "problem", "disease",
            "disorder", "syndrome", "illness"
        ]
        problem_count = sum(1 for p in problem_indicators if p in text)
        if problem_count >= 4:
            score += 3
        elif problem_count >= 2:
            score += 2
        else:
            score += 1

        # Data reviewed
        data_indicators = [
            "lab", "imaging", "ct", "mri", "x-ray", "ecg", "ekg",
            "pathology", "biopsy", "culture", "result"
        ]
        data_count = sum(1 for d in data_indicators if d in text)
        if data_count >= 3:
            score += 2
        elif data_count >= 1:
            score += 1

        # Risk indicators
        risk_indicators = [
            "hospitalization", "surgery", "high risk", "severe", "acute",
            "emergent", "critical", "intensive", "iv drug", "parenteral"
        ]
        risk_count = sum(1 for r in risk_indicators if r in text)
        if risk_count >= 2:
            score += 3
        elif risk_count >= 1:
            score += 2

        # Prescription drug management
        if any(x in text for x in ["prescription", "medication", "drug", "started on", "adjusted"]):
            score += 1

        # Map score to complexity
        if score >= 7:
            return "high"
        elif score >= 4:
            return "moderate"
        elif score >= 2:
            return "low"
        else:
            return "straightforward"

    # =========================================================================
    # E/M LEVEL CALCULATION
    # =========================================================================

    def calculate_em_level(
        self,
        time_spent_minutes: int | None = None,
        mdm_elements: dict[str, Any] | None = None,
        is_new_patient: bool = False,
        setting: str = "office",
    ) -> "EMLevelResult":
        """Calculate appropriate E/M code based on time or MDM.

        Args:
            time_spent_minutes: Total time spent on encounter date
            mdm_elements: Dict with MDM element assessments
            is_new_patient: Whether this is a new patient
            setting: office, inpatient, emergency, etc.

        Returns:
            EMLevelResult with recommended code and rationale
        """
        # MDM-based calculation
        mdm_result = None
        if mdm_elements:
            mdm_result = self._calculate_mdm_level(mdm_elements, is_new_patient, setting)

        # Time-based calculation
        time_result = None
        if time_spent_minutes:
            time_result = self._calculate_time_based_level(time_spent_minutes, is_new_patient, setting)

        # Use higher of the two
        if mdm_result and time_result:
            if self._code_level(time_result.code) > self._code_level(mdm_result.code):
                final_result = time_result
                final_result.rationale = f"Time-based: {time_result.rationale}. MDM would support {mdm_result.code}."
            else:
                final_result = mdm_result
                if time_result:
                    final_result.rationale = f"MDM-based: {mdm_result.rationale}. Time would support {time_result.code}."
        elif time_result:
            final_result = time_result
        elif mdm_result:
            final_result = mdm_result
        else:
            # Default
            code = "99213" if not is_new_patient else "99203"
            cpt = self.get_code(code)
            final_result = EMLevelResult(
                code=code,
                description=cpt.description if cpt else "Office visit",
                rationale="Insufficient information; defaulting to moderate level",
                work_rvu=cpt.work_rvu if cpt else 1.30,
                calculation_method="default",
                mdm_level=None,
                time_documented=None,
            )

        return final_result

    def _calculate_mdm_level(
        self,
        mdm_elements: dict[str, Any],
        is_new_patient: bool,
        setting: str
    ) -> "EMLevelResult":
        """Calculate E/M level based on MDM elements."""
        # MDM has 3 elements: problems, data, risk
        # Need 2 of 3 to meet a level

        problems = mdm_elements.get("problems", "minimal")  # minimal, low, moderate, high
        data = mdm_elements.get("data", "minimal")  # minimal, limited, moderate, extensive
        risk = mdm_elements.get("risk", "minimal")  # minimal, low, moderate, high

        level_map = {"minimal": 1, "low": 2, "limited": 2, "moderate": 3, "extensive": 4, "high": 4}
        levels = sorted([
            level_map.get(problems, 1),
            level_map.get(data, 1),
            level_map.get(risk, 1)
        ], reverse=True)

        # Second highest determines level
        mdm_level = levels[1]

        # Map to E/M code
        if setting == "emergency":
            code_map = {1: "99281", 2: "99283", 3: "99284", 4: "99285"}
        elif setting == "inpatient":
            code_map = {1: "99221", 2: "99221", 3: "99222", 4: "99223"}
        elif is_new_patient:
            code_map = {1: "99202", 2: "99203", 3: "99204", 4: "99205"}
        else:
            code_map = {1: "99212", 2: "99213", 3: "99214", 4: "99215"}

        code = code_map.get(mdm_level, "99213")
        cpt = self.get_code(code)

        mdm_text = {1: "straightforward", 2: "low", 3: "moderate", 4: "high"}

        return EMLevelResult(
            code=code,
            description=cpt.description if cpt else "Office visit",
            rationale=f"MDM {mdm_text.get(mdm_level, 'moderate')} (Problems: {problems}, Data: {data}, Risk: {risk})",
            work_rvu=cpt.work_rvu if cpt else 0,
            calculation_method="mdm",
            mdm_level=mdm_text.get(mdm_level),
            time_documented=None,
        )

    def _calculate_time_based_level(
        self,
        time_minutes: int,
        is_new_patient: bool,
        setting: str
    ) -> "EMLevelResult":
        """Calculate E/M level based on time."""
        if setting == "emergency":
            # ED doesn't use time-based coding in the same way
            return EMLevelResult(
                code="99283",
                description="ED visit",
                rationale="Time-based coding not standard for ED visits",
                work_rvu=1.42,
                calculation_method="time",
                mdm_level=None,
                time_documented=time_minutes,
            )
        elif setting == "inpatient":
            if time_minutes >= 75:
                code = "99223"
            elif time_minutes >= 55:
                code = "99222"
            else:
                code = "99221"
        elif is_new_patient:
            if time_minutes >= 60:
                code = "99205"
            elif time_minutes >= 45:
                code = "99204"
            elif time_minutes >= 30:
                code = "99203"
            else:
                code = "99202"
        else:
            if time_minutes >= 40:
                code = "99215"
            elif time_minutes >= 30:
                code = "99214"
            elif time_minutes >= 20:
                code = "99213"
            elif time_minutes >= 10:
                code = "99212"
            else:
                code = "99211"

        cpt = self.get_code(code)

        return EMLevelResult(
            code=code,
            description=cpt.description if cpt else "Office visit",
            rationale=f"Time-based: {time_minutes} minutes documented",
            work_rvu=cpt.work_rvu if cpt else 0,
            calculation_method="time",
            mdm_level=None,
            time_documented=time_minutes,
        )

    def _code_level(self, code: str) -> int:
        """Get numeric level from E/M code."""
        level_map = {
            "99211": 1, "99212": 2, "99213": 3, "99214": 4, "99215": 5,
            "99202": 2, "99203": 3, "99204": 4, "99205": 5,
            "99221": 2, "99222": 3, "99223": 4,
            "99281": 1, "99283": 3, "99284": 4, "99285": 5,
        }
        return level_map.get(code, 3)


# ============================================================================
# Additional Data Classes for Enhanced Features
# ============================================================================

from typing import Any


@dataclass
class TextCodeSuggestion:
    """A code suggestion from clinical text analysis."""

    code: str
    code_type: str  # "CPT", "ICD10"
    description: str
    confidence: float  # 0-1
    evidence_text: str  # The text that supports this code
    evidence_span: tuple[int, int]  # Start, end offsets
    rationale: str
    category: str
    work_rvu: float = 0.0


@dataclass
class TextCodeSuggestionResult:
    """Result of AI-powered code suggestion from text."""

    request_id: str
    text_length: int
    suggestions: list[TextCodeSuggestion]
    total_concepts: int
    em_level: str | None
    processing_time_ms: float


@dataclass
class EMLevelResult:
    """Result of E/M level calculation."""

    code: str
    description: str
    rationale: str
    work_rvu: float
    calculation_method: str  # "time", "mdm", "default"
    mdm_level: str | None
    time_documented: int | None


@dataclass
class CodingWorksheetEntry:
    """An entry in a coding worksheet."""

    code: str
    code_type: str  # "ICD10", "CPT"
    description: str
    sequence: int
    is_primary: bool = False
    confidence: float = 1.0
    status: str = "pending"  # pending, accepted, rejected
    source: str = "manual"  # manual, ai_suggested, extracted
    evidence_text: str | None = None
    modifier: str | None = None
    notes: str | None = None


@dataclass
class CodingWorksheet:
    """A coding worksheet for an encounter."""

    encounter_id: str
    patient_id: str
    encounter_date: str
    status: str  # draft, submitted, finalized
    diagnosis_codes: list[CodingWorksheetEntry] = field(default_factory=list)
    procedure_codes: list[CodingWorksheetEntry] = field(default_factory=list)
    em_code: CodingWorksheetEntry | None = None
    validation_warnings: list[str] = field(default_factory=list)
    audit_trail: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    submitted_at: str | None = None
    submitted_by: str | None = None


# In-memory worksheet storage (would be database in production)
_worksheets: dict[str, CodingWorksheet] = {}
_worksheet_lock = threading.Lock()


def get_worksheet(encounter_id: str) -> CodingWorksheet | None:
    """Get a coding worksheet by encounter ID."""
    with _worksheet_lock:
        return _worksheets.get(encounter_id)


def save_worksheet(worksheet: CodingWorksheet) -> None:
    """Save a coding worksheet."""
    from datetime import datetime
    with _worksheet_lock:
        worksheet.updated_at = datetime.now().isoformat()
        _worksheets[worksheet.encounter_id] = worksheet


def create_worksheet(
    encounter_id: str,
    patient_id: str,
    encounter_date: str
) -> CodingWorksheet:
    """Create a new coding worksheet."""
    from datetime import datetime
    worksheet = CodingWorksheet(
        encounter_id=encounter_id,
        patient_id=patient_id,
        encounter_date=encounter_date,
        status="draft",
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
    )
    save_worksheet(worksheet)
    return worksheet


def add_worksheet_entry(
    encounter_id: str,
    entry: CodingWorksheetEntry,
    entry_type: str  # "diagnosis", "procedure", "em"
) -> CodingWorksheet | None:
    """Add an entry to a coding worksheet."""
    from datetime import datetime
    worksheet = get_worksheet(encounter_id)
    if not worksheet:
        return None

    if entry_type == "diagnosis":
        worksheet.diagnosis_codes.append(entry)
    elif entry_type == "procedure":
        worksheet.procedure_codes.append(entry)
    elif entry_type == "em":
        worksheet.em_code = entry

    worksheet.audit_trail.append({
        "action": f"add_{entry_type}",
        "code": entry.code,
        "timestamp": datetime.now().isoformat(),
    })

    save_worksheet(worksheet)
    return worksheet


def submit_worksheet(encounter_id: str, submitted_by: str) -> CodingWorksheet | None:
    """Submit a coding worksheet for billing."""
    from datetime import datetime
    worksheet = get_worksheet(encounter_id)
    if not worksheet:
        return None

    # Validate before submission
    warnings = validate_worksheet(worksheet)
    worksheet.validation_warnings = warnings

    if not any("ERROR" in w for w in warnings):
        worksheet.status = "submitted"
        worksheet.submitted_at = datetime.now().isoformat()
        worksheet.submitted_by = submitted_by

        worksheet.audit_trail.append({
            "action": "submit",
            "submitted_by": submitted_by,
            "timestamp": datetime.now().isoformat(),
        })

    save_worksheet(worksheet)
    return worksheet


def validate_worksheet(worksheet: CodingWorksheet) -> list[str]:
    """Validate a coding worksheet before submission."""
    warnings = []

    # Must have at least one diagnosis
    if not worksheet.diagnosis_codes:
        warnings.append("ERROR: At least one diagnosis code is required")

    # Must have E/M code
    if not worksheet.em_code:
        warnings.append("WARNING: No E/M code assigned")

    # Check for primary diagnosis
    has_primary = any(d.is_primary for d in worksheet.diagnosis_codes)
    if worksheet.diagnosis_codes and not has_primary:
        warnings.append("WARNING: No primary diagnosis designated")

    # Check diagnosis sequence
    sequences = [d.sequence for d in worksheet.diagnosis_codes]
    if sequences and sequences != sorted(sequences):
        warnings.append("INFO: Diagnosis sequence may need review")

    return warnings
