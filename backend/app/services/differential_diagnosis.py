"""Differential Diagnosis Generator Service.

This module provides clinical decision support by generating ranked
differential diagnoses based on presenting symptoms, signs, and findings.

Features:
- Symptom-to-diagnosis mapping with probability estimates
- Support for multiple clinical domains
- Consideration of red flags and critical diagnoses
- Age and gender adjustments for prevalence
- OMOP concept integration

Note: This is a clinical decision support tool and should not replace
clinical judgment. All diagnoses should be confirmed through appropriate
diagnostic workup.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class DiagnosisUrgency(Enum):
    """Urgency level for a diagnosis."""

    EMERGENT = "emergent"  # Requires immediate intervention
    URGENT = "urgent"  # Requires same-day evaluation
    SEMI_URGENT = "semi_urgent"  # Requires evaluation within days
    ROUTINE = "routine"  # Can be evaluated electively


class CERStrength(Enum):
    """Strength of the CER citation."""

    STRONG = "strong"  # High clinical evidence supports this diagnosis
    MODERATE = "moderate"  # Good clinical evidence, consider alternatives
    WEAK = "weak"  # Limited evidence, needs further workup


@dataclass
class DiagnosisCERCitation:
    """Claim-Evidence-Reasoning citation for a differential diagnosis.

    This framework helps clinicians understand WHY a diagnosis is suggested:
    - Claim: What diagnosis is being considered and its probability
    - Evidence: Clinical findings supporting and opposing this diagnosis
    - Reasoning: Clinical logic connecting findings to the diagnosis
    """

    claim: str  # The diagnostic assertion
    supporting_evidence: list[str]  # Findings that support this diagnosis
    opposing_evidence: list[str]  # Findings that argue against
    reasoning: str  # Clinical reasoning connecting evidence to claim
    strength: CERStrength  # How strong is this CER
    clinical_pearls: list[str] = field(default_factory=list)  # Clinical teaching points
    diagnostic_criteria: list[str] = field(default_factory=list)  # Formal criteria if applicable
    must_rule_out: list[str] = field(default_factory=list)  # Critical diagnoses to exclude


class ClinicalDomain(Enum):
    """Clinical domains for categorizing diagnoses."""

    CARDIOVASCULAR = "cardiovascular"
    RESPIRATORY = "respiratory"
    GASTROINTESTINAL = "gastrointestinal"
    NEUROLOGICAL = "neurological"
    MUSCULOSKELETAL = "musculoskeletal"
    ENDOCRINE = "endocrine"
    INFECTIOUS = "infectious"
    RENAL = "renal"
    HEMATOLOGIC = "hematologic"
    PSYCHIATRIC = "psychiatric"
    DERMATOLOGIC = "dermatologic"
    RHEUMATOLOGIC = "rheumatologic"


@dataclass
class DiagnosisCandidate:
    """A candidate diagnosis in the differential with CER citation."""

    name: str
    omop_concept_id: int | None
    icd10_code: str | None
    domain: ClinicalDomain
    urgency: DiagnosisUrgency
    probability_score: float  # 0.0 to 1.0
    supporting_findings: list[str]  # Findings that support this diagnosis
    opposing_findings: list[str]  # Findings that argue against
    red_flags: list[str]  # Critical findings to watch for
    recommended_workup: list[str]  # Suggested diagnostic tests
    key_features: list[str]  # Classic presentation features
    prevalence_modifier: str = "average"  # low, average, high for demographics

    # CER Framework for clinical reasoning transparency
    cer_citation: DiagnosisCERCitation | None = None


@dataclass
class DifferentialResult:
    """Result from differential diagnosis generation."""

    presenting_findings: list[str]
    age: int | None
    gender: str | None
    differential: list[DiagnosisCandidate]
    red_flag_diagnoses: list[str]  # High-urgency diagnoses that must be ruled out
    cannot_miss_diagnoses: list[str]  # Diagnoses with serious consequences if missed
    suggested_history: list[str]  # Additional history to gather
    suggested_exam: list[str]  # Physical exam maneuvers to perform


@dataclass
class FindingAssociation:
    """Association between a finding and a diagnosis."""

    diagnosis_name: str
    association_strength: float  # 0.0 to 1.0 (likelihood ratio concept)
    is_pathognomonic: bool = False  # Nearly diagnostic if present
    is_sensitive: bool = False  # Usually present if diagnosis is true
    is_specific: bool = False  # Usually absent if diagnosis is false


# ============================================================================
# Clinical Knowledge Base
# ============================================================================


@dataclass
class DiagnosisTemplate:
    """Template for a diagnosis with its clinical features."""

    name: str
    omop_concept_id: int | None
    icd10_code: str | None
    domain: ClinicalDomain
    urgency: DiagnosisUrgency
    classic_findings: list[str]  # Findings strongly associated
    common_findings: list[str]  # Frequently present
    uncommon_findings: list[str]  # Sometimes present
    key_features: list[str]  # Distinguishing characteristics
    red_flags: list[str]  # Warning signs
    recommended_workup: list[str]
    prevalence_base: float = 0.01  # Base prevalence in general population
    age_peak: tuple[int, int] | None = None  # Age range of peak incidence
    gender_ratio: float = 1.0  # M:F ratio (>1 = more common in males)


# Symptom aliases for normalization
FINDING_ALIASES: dict[str, str] = {
    # Chest pain
    "chest pain": "chest_pain",
    "chest discomfort": "chest_pain",
    "angina": "chest_pain",
    "substernal pain": "chest_pain",
    "pressure in chest": "chest_pain",
    # Shortness of breath
    "shortness of breath": "dyspnea",
    "sob": "dyspnea",
    "difficulty breathing": "dyspnea",
    "breathlessness": "dyspnea",
    "short of breath": "dyspnea",
    # Headache
    "headache": "headache",
    "head pain": "headache",
    "cephalgia": "headache",
    # Fever
    "fever": "fever",
    "febrile": "fever",
    "elevated temperature": "fever",
    "temp": "fever",
    # Fatigue
    "fatigue": "fatigue",
    "tiredness": "fatigue",
    "lethargy": "fatigue",
    "weakness": "fatigue",
    "malaise": "fatigue",
    # Abdominal pain
    "abdominal pain": "abdominal_pain",
    "stomach pain": "abdominal_pain",
    "belly pain": "abdominal_pain",
    "epigastric pain": "epigastric_pain",
    "rlq pain": "rlq_pain",
    "right lower quadrant pain": "rlq_pain",
    "ruq pain": "ruq_pain",
    "right upper quadrant pain": "ruq_pain",
    # Nausea/vomiting
    "nausea": "nausea",
    "nauseated": "nausea",
    "vomiting": "vomiting",
    "emesis": "vomiting",
    # Cough
    "cough": "cough",
    "productive cough": "productive_cough",
    "dry cough": "dry_cough",
    # Dizziness
    "dizziness": "dizziness",
    "lightheadedness": "lightheadedness",
    "vertigo": "vertigo",
    "room spinning": "vertigo",
    # Pain characteristics
    "radiating to arm": "radiation_to_arm",
    "radiates to arm": "radiation_to_arm",
    "pain radiating to jaw": "radiation_to_jaw",
    "crushing pain": "crushing_chest_pain",
    "pleuritic pain": "pleuritic_pain",
    "worse with breathing": "pleuritic_pain",
    # Associated symptoms
    "diaphoresis": "diaphoresis",
    "sweating": "diaphoresis",
    "palpitations": "palpitations",
    "heart racing": "palpitations",
    "edema": "edema",
    "swelling": "edema",
    "leg swelling": "leg_edema",
    "orthopnea": "orthopnea",
    "pnd": "pnd",
    "paroxysmal nocturnal dyspnea": "pnd",
    # Neurological
    "confusion": "confusion",
    "altered mental status": "altered_mental_status",
    "ams": "altered_mental_status",
    "numbness": "numbness",
    "tingling": "paresthesias",
    "weakness in arm": "arm_weakness",
    "weakness in leg": "leg_weakness",
    "facial droop": "facial_weakness",
    "slurred speech": "dysarthria",
    "vision changes": "vision_changes",
    "double vision": "diplopia",
    # GI
    "diarrhea": "diarrhea",
    "constipation": "constipation",
    "bloody stool": "hematochezia",
    "melena": "melena",
    "black stool": "melena",
    "jaundice": "jaundice",
    "yellow skin": "jaundice",
    # Urinary
    "dysuria": "dysuria",
    "painful urination": "dysuria",
    "frequency": "urinary_frequency",
    "urgency": "urinary_urgency",
    "hematuria": "hematuria",
    "blood in urine": "hematuria",
    # Musculoskeletal
    "joint pain": "arthralgia",
    "arthralgia": "arthralgia",
    "back pain": "back_pain",
    "lower back pain": "low_back_pain",
    "neck pain": "neck_pain",
    "stiffness": "stiffness",
    # Skin
    "rash": "rash",
    "itching": "pruritus",
    "pruritus": "pruritus",
}

# Database of diagnosis templates
DIAGNOSIS_TEMPLATES: list[DiagnosisTemplate] = [
    # =========================================================================
    # CARDIOVASCULAR
    # =========================================================================
    DiagnosisTemplate(
        name="Acute Coronary Syndrome (ACS)",
        omop_concept_id=312327,
        icd10_code="I21.9",
        domain=ClinicalDomain.CARDIOVASCULAR,
        urgency=DiagnosisUrgency.EMERGENT,
        classic_findings=["chest_pain", "radiation_to_arm", "diaphoresis", "crushing_chest_pain"],
        common_findings=["dyspnea", "nausea", "radiation_to_jaw", "fatigue"],
        uncommon_findings=["epigastric_pain", "vomiting", "syncope"],
        key_features=[
            "Substernal chest pressure/pain",
            "Radiation to arm, jaw, or back",
            "Associated diaphoresis",
            "May be atypical in women, elderly, diabetics",
        ],
        red_flags=["Hemodynamic instability", "Cardiogenic shock", "Ventricular arrhythmias"],
        recommended_workup=["ECG", "Troponin (serial)", "Chest X-ray", "BMP", "CBC"],
        prevalence_base=0.05,
        age_peak=(50, 80),
        gender_ratio=1.5,
    ),
    DiagnosisTemplate(
        name="Congestive Heart Failure (CHF)",
        omop_concept_id=316139,
        icd10_code="I50.9",
        domain=ClinicalDomain.CARDIOVASCULAR,
        urgency=DiagnosisUrgency.URGENT,
        classic_findings=["dyspnea", "leg_edema", "orthopnea", "pnd"],
        common_findings=["fatigue", "cough", "palpitations", "weight_gain"],
        uncommon_findings=["confusion", "abdominal_distension", "nocturia"],
        key_features=[
            "Progressive dyspnea on exertion",
            "Orthopnea (need to sleep propped up)",
            "Paroxysmal nocturnal dyspnea",
            "Lower extremity edema",
        ],
        red_flags=["Acute pulmonary edema", "Cardiogenic shock", "New arrhythmia"],
        recommended_workup=["BNP/NT-proBNP", "ECG", "Chest X-ray", "Echocardiogram", "BMP"],
        prevalence_base=0.03,
        age_peak=(65, 85),
        gender_ratio=1.0,
    ),
    DiagnosisTemplate(
        name="Atrial Fibrillation",
        omop_concept_id=313217,
        icd10_code="I48.91",
        domain=ClinicalDomain.CARDIOVASCULAR,
        urgency=DiagnosisUrgency.URGENT,
        classic_findings=["palpitations", "irregular_pulse"],
        common_findings=["dyspnea", "fatigue", "lightheadedness", "chest_pain"],
        uncommon_findings=["syncope", "confusion"],
        key_features=[
            "Irregularly irregular pulse",
            "Variable intensity first heart sound",
            "May be asymptomatic",
            "Risk of stroke",
        ],
        red_flags=["Rapid ventricular response", "Hemodynamic instability", "Stroke symptoms"],
        recommended_workup=["ECG", "Echocardiogram", "TSH", "BMP", "CHA2DS2-VASc score"],
        prevalence_base=0.02,
        age_peak=(65, 85),
        gender_ratio=1.2,
    ),
    DiagnosisTemplate(
        name="Pulmonary Embolism",
        omop_concept_id=440417,
        icd10_code="I26.99",
        domain=ClinicalDomain.CARDIOVASCULAR,
        urgency=DiagnosisUrgency.EMERGENT,
        classic_findings=["dyspnea", "pleuritic_pain", "tachycardia"],
        common_findings=["cough", "leg_edema", "hemoptysis"],
        uncommon_findings=["syncope", "hypotension", "fever"],
        key_features=[
            "Sudden onset dyspnea",
            "Pleuritic chest pain",
            "Risk factors: immobility, surgery, cancer, DVT history",
            "Tachycardia out of proportion to findings",
        ],
        red_flags=["Massive PE with hypotension", "Right heart strain", "Cardiac arrest"],
        recommended_workup=["D-dimer", "CT-PA", "ECG", "ABG", "Wells score for PE"],
        prevalence_base=0.01,
        age_peak=(50, 80),
        gender_ratio=0.9,
    ),
    # =========================================================================
    # RESPIRATORY
    # =========================================================================
    DiagnosisTemplate(
        name="Community-Acquired Pneumonia",
        omop_concept_id=255848,
        icd10_code="J18.9",
        domain=ClinicalDomain.RESPIRATORY,
        urgency=DiagnosisUrgency.URGENT,
        classic_findings=["fever", "productive_cough", "dyspnea"],
        common_findings=["chest_pain", "fatigue", "chills"],
        uncommon_findings=["confusion", "pleuritic_pain", "hemoptysis"],
        key_features=[
            "Fever with productive cough",
            "Rales/crackles on auscultation",
            "Lobar consolidation on imaging",
            "Elevated WBC",
        ],
        red_flags=["Sepsis", "Respiratory failure", "Multilobar involvement"],
        recommended_workup=["Chest X-ray", "CBC", "BMP", "Blood cultures", "CURB-65 score"],
        prevalence_base=0.03,
        age_peak=(0, 100),
        gender_ratio=1.1,
    ),
    DiagnosisTemplate(
        name="COPD Exacerbation",
        omop_concept_id=255573,
        icd10_code="J44.1",
        domain=ClinicalDomain.RESPIRATORY,
        urgency=DiagnosisUrgency.URGENT,
        classic_findings=["dyspnea", "productive_cough", "wheezing"],
        common_findings=["increased_sputum", "chest_tightness"],
        uncommon_findings=["fever", "confusion", "peripheral_edema"],
        key_features=[
            "Baseline COPD with acute worsening",
            "Increased dyspnea, sputum volume, or purulence",
            "History of smoking",
            "Prolonged expiratory phase",
        ],
        red_flags=["Respiratory failure", "Altered mental status", "Severe acidosis"],
        recommended_workup=["ABG", "Chest X-ray", "Sputum culture", "BNP"],
        prevalence_base=0.02,
        age_peak=(55, 85),
        gender_ratio=1.5,
    ),
    DiagnosisTemplate(
        name="Asthma Exacerbation",
        omop_concept_id=317009,
        icd10_code="J45.901",
        domain=ClinicalDomain.RESPIRATORY,
        urgency=DiagnosisUrgency.URGENT,
        classic_findings=["dyspnea", "wheezing", "cough"],
        common_findings=["chest_tightness", "tachypnea"],
        uncommon_findings=["silent_chest", "cyanosis"],
        key_features=[
            "Known asthma with acute worsening",
            "Triggers: URI, allergens, exercise",
            "Wheezing on exam",
            "Response to bronchodilators",
        ],
        red_flags=["Silent chest (severe obstruction)", "Altered mental status", "Inability to speak"],
        recommended_workup=["Peak flow", "Pulse oximetry", "Chest X-ray (if severe)", "ABG (if severe)"],
        prevalence_base=0.08,
        age_peak=(5, 40),
        gender_ratio=0.8,
    ),
    # =========================================================================
    # GASTROINTESTINAL
    # =========================================================================
    DiagnosisTemplate(
        name="Acute Appendicitis",
        omop_concept_id=440448,
        icd10_code="K35.80",
        domain=ClinicalDomain.GASTROINTESTINAL,
        urgency=DiagnosisUrgency.EMERGENT,
        classic_findings=["rlq_pain", "fever", "nausea"],
        common_findings=["vomiting", "anorexia", "rebound_tenderness"],
        uncommon_findings=["diarrhea", "dysuria"],
        key_features=[
            "Pain migrating from periumbilical to RLQ",
            "McBurney's point tenderness",
            "Rebound tenderness, guarding",
            "Low-grade fever",
        ],
        red_flags=["Perforation", "Peritonitis", "Sepsis"],
        recommended_workup=["CT abdomen/pelvis", "CBC", "CRP", "Urinalysis"],
        prevalence_base=0.07,
        age_peak=(10, 30),
        gender_ratio=1.2,
    ),
    DiagnosisTemplate(
        name="Acute Cholecystitis",
        omop_concept_id=201606,
        icd10_code="K81.0",
        domain=ClinicalDomain.GASTROINTESTINAL,
        urgency=DiagnosisUrgency.URGENT,
        classic_findings=["ruq_pain", "fever", "murphy_sign"],
        common_findings=["nausea", "vomiting", "anorexia"],
        uncommon_findings=["jaundice", "referred_shoulder_pain"],
        key_features=[
            "RUQ pain, often after fatty meal",
            "Positive Murphy's sign",
            "Fever and elevated WBC",
            "Risk factors: female, fertile, forty, fat",
        ],
        red_flags=["Gangrenous cholecystitis", "Cholangitis", "Sepsis"],
        recommended_workup=["RUQ ultrasound", "CBC", "LFTs", "Lipase", "HIDA scan if equivocal"],
        prevalence_base=0.02,
        age_peak=(40, 70),
        gender_ratio=0.5,
    ),
    DiagnosisTemplate(
        name="Peptic Ulcer Disease",
        omop_concept_id=4027663,
        icd10_code="K27.9",
        domain=ClinicalDomain.GASTROINTESTINAL,
        urgency=DiagnosisUrgency.SEMI_URGENT,
        classic_findings=["epigastric_pain", "nausea"],
        common_findings=["bloating", "heartburn", "anorexia"],
        uncommon_findings=["melena", "hematemesis", "weight_loss"],
        key_features=[
            "Epigastric burning or gnawing pain",
            "Relation to meals (gastric: worse with food; duodenal: better with food)",
            "NSAID or H. pylori association",
        ],
        red_flags=["GI bleeding (melena, hematemesis)", "Perforation", "Obstruction"],
        recommended_workup=["H. pylori testing", "CBC", "EGD if alarm symptoms"],
        prevalence_base=0.04,
        age_peak=(30, 60),
        gender_ratio=1.5,
    ),
    # =========================================================================
    # NEUROLOGICAL
    # =========================================================================
    DiagnosisTemplate(
        name="Ischemic Stroke",
        omop_concept_id=443454,
        icd10_code="I63.9",
        domain=ClinicalDomain.NEUROLOGICAL,
        urgency=DiagnosisUrgency.EMERGENT,
        classic_findings=["arm_weakness", "facial_weakness", "dysarthria"],
        common_findings=["numbness", "vision_changes", "confusion"],
        uncommon_findings=["headache", "vertigo", "diplopia"],
        key_features=[
            "Sudden onset focal neurological deficit",
            "FAST: Face drooping, Arm weakness, Speech difficulty, Time",
            "Vascular territory distribution",
            "Risk factors: HTN, DM, afib, prior stroke",
        ],
        red_flags=["Large vessel occlusion", "Hemorrhagic transformation", "Brainstem stroke"],
        recommended_workup=["CT head (stat)", "CT-A head/neck", "MRI brain", "ECG", "Echo"],
        prevalence_base=0.02,
        age_peak=(60, 85),
        gender_ratio=1.2,
    ),
    DiagnosisTemplate(
        name="Migraine",
        omop_concept_id=4133004,
        icd10_code="G43.909",
        domain=ClinicalDomain.NEUROLOGICAL,
        urgency=DiagnosisUrgency.ROUTINE,
        classic_findings=["headache", "photophobia", "nausea"],
        common_findings=["vomiting", "phonophobia", "aura"],
        uncommon_findings=["vertigo", "paresthesias", "vision_changes"],
        key_features=[
            "Unilateral, pulsating headache",
            "Moderate to severe intensity",
            "Aggravated by activity",
            "Associated nausea, photophobia, phonophobia",
        ],
        red_flags=["Thunderclap onset", "Worst headache of life", "Neurological deficits"],
        recommended_workup=["Usually clinical diagnosis", "Consider CT/MRI if red flags"],
        prevalence_base=0.12,
        age_peak=(20, 50),
        gender_ratio=0.3,
    ),
    DiagnosisTemplate(
        name="Meningitis",
        omop_concept_id=4085159,
        icd10_code="G03.9",
        domain=ClinicalDomain.NEUROLOGICAL,
        urgency=DiagnosisUrgency.EMERGENT,
        classic_findings=["headache", "fever", "neck_stiffness"],
        common_findings=["photophobia", "nausea", "vomiting", "altered_mental_status"],
        uncommon_findings=["rash", "seizures"],
        key_features=[
            "Classic triad: fever, headache, neck stiffness",
            "Positive Kernig's and Brudzinski's signs",
            "Altered mental status",
            "Photophobia",
        ],
        red_flags=["Rapid deterioration", "Seizures", "Focal neurological signs"],
        recommended_workup=[
            "Lumbar puncture (CSF analysis)",
            "Blood cultures",
            "CT head before LP if indicated",
            "CBC",
            "BMP",
        ],
        prevalence_base=0.001,
        age_peak=(0, 30),
        gender_ratio=1.2,
    ),
    # =========================================================================
    # INFECTIOUS
    # =========================================================================
    DiagnosisTemplate(
        name="Urinary Tract Infection",
        omop_concept_id=81902,
        icd10_code="N39.0",
        domain=ClinicalDomain.INFECTIOUS,
        urgency=DiagnosisUrgency.SEMI_URGENT,
        classic_findings=["dysuria", "urinary_frequency", "urinary_urgency"],
        common_findings=["suprapubic_pain", "hematuria"],
        uncommon_findings=["fever", "back_pain", "nausea"],
        key_features=[
            "Dysuria with frequency/urgency",
            "Suprapubic discomfort",
            "Cloudy or malodorous urine",
            "More common in women",
        ],
        red_flags=["Pyelonephritis (flank pain, fever)", "Sepsis", "Obstruction"],
        recommended_workup=["Urinalysis", "Urine culture", "Consider CT if pyelonephritis suspected"],
        prevalence_base=0.08,
        age_peak=(18, 50),
        gender_ratio=0.2,
    ),
    DiagnosisTemplate(
        name="Pyelonephritis",
        omop_concept_id=81893,
        icd10_code="N10",
        domain=ClinicalDomain.INFECTIOUS,
        urgency=DiagnosisUrgency.URGENT,
        classic_findings=["fever", "flank_pain", "dysuria"],
        common_findings=["nausea", "vomiting", "urinary_frequency"],
        uncommon_findings=["hematuria", "confusion"],
        key_features=[
            "Fever with flank/CVA tenderness",
            "UTI symptoms plus systemic illness",
            "May have bacteremia",
        ],
        red_flags=["Sepsis", "Abscess formation", "Obstruction"],
        recommended_workup=["Urinalysis", "Urine culture", "Blood cultures", "CBC", "BMP", "CT if complicated"],
        prevalence_base=0.02,
        age_peak=(18, 50),
        gender_ratio=0.3,
    ),
    # =========================================================================
    # ENDOCRINE
    # =========================================================================
    DiagnosisTemplate(
        name="Diabetic Ketoacidosis",
        omop_concept_id=443727,
        icd10_code="E10.10",
        domain=ClinicalDomain.ENDOCRINE,
        urgency=DiagnosisUrgency.EMERGENT,
        classic_findings=["nausea", "vomiting", "abdominal_pain", "polyuria"],
        common_findings=["fatigue", "altered_mental_status", "fruity_breath"],
        uncommon_findings=["kussmaul_breathing"],
        key_features=[
            "Hyperglycemia (>250 mg/dL)",
            "Metabolic acidosis (pH <7.3)",
            "Ketones in blood/urine",
            "Anion gap >10",
        ],
        red_flags=["Severe acidosis (pH <7.0)", "Cerebral edema", "Cardiovascular collapse"],
        recommended_workup=["BMP", "ABG/VBG", "Serum ketones", "Urinalysis", "CBC"],
        prevalence_base=0.01,
        age_peak=(20, 50),
        gender_ratio=1.0,
    ),
    DiagnosisTemplate(
        name="Hyperthyroidism",
        omop_concept_id=4177777,
        icd10_code="E05.90",
        domain=ClinicalDomain.ENDOCRINE,
        urgency=DiagnosisUrgency.SEMI_URGENT,
        classic_findings=["palpitations", "weight_loss", "heat_intolerance"],
        common_findings=["tremor", "anxiety", "diarrhea", "fatigue"],
        uncommon_findings=["eye_changes", "pretibial_myxedema"],
        key_features=[
            "Weight loss despite good appetite",
            "Heat intolerance, diaphoresis",
            "Tachycardia, tremor",
            "May have goiter or eye findings (Graves)",
        ],
        red_flags=["Thyroid storm", "Atrial fibrillation", "Heart failure"],
        recommended_workup=["TSH", "Free T4", "Free T3", "Thyroid antibodies"],
        prevalence_base=0.02,
        age_peak=(20, 50),
        gender_ratio=0.2,
    ),
    # =========================================================================
    # MUSCULOSKELETAL
    # =========================================================================
    DiagnosisTemplate(
        name="Gout",
        omop_concept_id=4070697,
        icd10_code="M10.9",
        domain=ClinicalDomain.MUSCULOSKELETAL,
        urgency=DiagnosisUrgency.SEMI_URGENT,
        classic_findings=["joint_pain", "joint_swelling", "joint_redness"],
        common_findings=["warmth", "limited_rom"],
        uncommon_findings=["fever", "tophi"],
        key_features=[
            "Acute monoarticular arthritis",
            "First MTP joint classic (podagra)",
            "Rapid onset, extremely painful",
            "Hyperuricemia history",
        ],
        red_flags=["Septic arthritis must be excluded", "Polyarticular gout"],
        recommended_workup=["Serum uric acid", "Joint aspiration if available", "CBC", "BMP"],
        prevalence_base=0.04,
        age_peak=(40, 70),
        gender_ratio=4.0,
    ),
    DiagnosisTemplate(
        name="Lumbar Disc Herniation",
        omop_concept_id=4063684,
        icd10_code="M51.16",
        domain=ClinicalDomain.MUSCULOSKELETAL,
        urgency=DiagnosisUrgency.SEMI_URGENT,
        classic_findings=["low_back_pain", "leg_pain", "numbness"],
        common_findings=["paresthesias", "weakness"],
        uncommon_findings=["bowel_bladder_dysfunction", "saddle_anesthesia"],
        key_features=[
            "Radicular pain following dermatomal pattern",
            "Positive straight leg raise",
            "May have sensory or motor deficit",
            "L4-L5 and L5-S1 most common",
        ],
        red_flags=["Cauda equina syndrome", "Progressive neurological deficit", "Significant weakness"],
        recommended_workup=["MRI lumbar spine if red flags", "Consider EMG if chronic"],
        prevalence_base=0.05,
        age_peak=(30, 55),
        gender_ratio=1.2,
    ),
]


# ============================================================================
# Differential Diagnosis Service
# ============================================================================

# Singleton instance and lock for thread safety
_differential_service: "DifferentialDiagnosisService | None" = None
_differential_lock = threading.Lock()


def get_differential_diagnosis_service() -> "DifferentialDiagnosisService":
    """Get the singleton differential diagnosis service instance."""
    global _differential_service
    if _differential_service is None:
        with _differential_lock:
            if _differential_service is None:
                _differential_service = DifferentialDiagnosisService()
    return _differential_service


def reset_differential_diagnosis_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _differential_service
    with _differential_lock:
        _differential_service = None


class DifferentialDiagnosisService:
    """Service for generating differential diagnoses from clinical findings."""

    def __init__(self) -> None:
        """Initialize the differential diagnosis service."""
        self._diagnoses: list[DiagnosisTemplate] = DIAGNOSIS_TEMPLATES
        self._finding_aliases: dict[str, str] = FINDING_ALIASES

        # Build index: finding -> list of (diagnosis, strength)
        self._finding_index: dict[str, list[tuple[DiagnosisTemplate, float]]] = {}
        self._build_finding_index()

    def _build_finding_index(self) -> None:
        """Build index mapping findings to diagnoses."""
        for dx in self._diagnoses:
            # Classic findings have high association strength
            for finding in dx.classic_findings:
                if finding not in self._finding_index:
                    self._finding_index[finding] = []
                self._finding_index[finding].append((dx, 0.9))

            # Common findings have moderate association
            for finding in dx.common_findings:
                if finding not in self._finding_index:
                    self._finding_index[finding] = []
                self._finding_index[finding].append((dx, 0.6))

            # Uncommon findings have lower association
            for finding in dx.uncommon_findings:
                if finding not in self._finding_index:
                    self._finding_index[finding] = []
                self._finding_index[finding].append((dx, 0.3))

    def normalize_finding(self, finding: str) -> str:
        """Normalize a finding to its canonical form."""
        finding_lower = finding.lower().strip()
        return self._finding_aliases.get(finding_lower, finding_lower.replace(" ", "_"))

    def generate_differential(
        self,
        findings: list[str],
        age: int | None = None,
        gender: str | None = None,
        max_diagnoses: int = 10,
    ) -> DifferentialResult:
        """Generate a ranked differential diagnosis.

        Args:
            findings: List of clinical findings/symptoms
            age: Patient age for prevalence adjustment
            gender: Patient gender ('male' or 'female')
            max_diagnoses: Maximum number of diagnoses to return

        Returns:
            DifferentialResult with ranked diagnoses and recommendations.
        """
        # Normalize findings
        normalized_findings = [self.normalize_finding(f) for f in findings]

        # Score each diagnosis
        diagnosis_scores: dict[str, dict] = {}

        for finding in normalized_findings:
            if finding not in self._finding_index:
                continue

            for dx, strength in self._finding_index[finding]:
                if dx.name not in diagnosis_scores:
                    diagnosis_scores[dx.name] = {
                        "template": dx,
                        "score": 0.0,
                        "supporting": [],
                        "classic_count": 0,
                    }

                diagnosis_scores[dx.name]["score"] += strength
                diagnosis_scores[dx.name]["supporting"].append(finding)

                if finding in dx.classic_findings:
                    diagnosis_scores[dx.name]["classic_count"] += 1

        # Adjust scores based on demographics
        for name, data in diagnosis_scores.items():
            dx = data["template"]

            # Base prevalence boost
            data["score"] += dx.prevalence_base * 2

            # Age adjustment
            if age is not None and dx.age_peak:
                age_min, age_max = dx.age_peak
                if age_min <= age <= age_max:
                    data["score"] *= 1.3
                elif abs(age - age_min) > 30 or abs(age - age_max) > 30:
                    data["score"] *= 0.7

            # Gender adjustment
            if gender is not None:
                if gender.lower() == "male" and dx.gender_ratio > 1:
                    data["score"] *= min(1.5, 1 + (dx.gender_ratio - 1) * 0.3)
                elif gender.lower() == "female" and dx.gender_ratio < 1:
                    data["score"] *= min(1.5, 1 + (1 / dx.gender_ratio - 1) * 0.3)

            # Bonus for multiple classic findings
            if data["classic_count"] >= 2:
                data["score"] *= 1.5

        # Sort by score
        sorted_diagnoses = sorted(
            diagnosis_scores.values(),
            key=lambda x: x["score"],
            reverse=True,
        )[:max_diagnoses]

        # Build result
        differential: list[DiagnosisCandidate] = []
        red_flag_diagnoses: list[str] = []
        cannot_miss: list[str] = []

        for data in sorted_diagnoses:
            dx = data["template"]

            # Calculate opposing findings
            all_dx_findings = set(dx.classic_findings + dx.common_findings + dx.uncommon_findings)
            opposing = [f for f in normalized_findings if f not in all_dx_findings]

            # Normalize probability score to 0-1 range
            max_possible_score = len(dx.classic_findings) * 0.9 + len(dx.common_findings) * 0.6
            prob_score = min(1.0, data["score"] / (max_possible_score + 0.1)) if max_possible_score > 0 else 0.5

            # Determine prevalence modifier
            prevalence_mod = "average"
            if age is not None and dx.age_peak:
                age_min, age_max = dx.age_peak
                if age_min <= age <= age_max:
                    prevalence_mod = "high"
                elif abs(age - (age_min + age_max) / 2) > 40:
                    prevalence_mod = "low"

            # Build CER citation for this diagnosis
            cer_citation = self._build_diagnosis_cer(
                dx=dx,
                supporting=data["supporting"],
                opposing=opposing[:5],
                prob_score=prob_score,
                classic_count=data["classic_count"],
                age=age,
                gender=gender,
            )

            candidate = DiagnosisCandidate(
                name=dx.name,
                omop_concept_id=dx.omop_concept_id,
                icd10_code=dx.icd10_code,
                domain=dx.domain,
                urgency=dx.urgency,
                probability_score=round(prob_score, 3),
                supporting_findings=data["supporting"],
                opposing_findings=opposing[:5],  # Limit for readability
                red_flags=dx.red_flags,
                recommended_workup=dx.recommended_workup,
                key_features=dx.key_features,
                prevalence_modifier=prevalence_mod,
                cer_citation=cer_citation,
            )
            differential.append(candidate)

            # Track critical diagnoses
            if dx.urgency == DiagnosisUrgency.EMERGENT:
                red_flag_diagnoses.append(dx.name)
                cannot_miss.append(dx.name)

        # Generate suggestions for additional history/exam
        suggested_history = self._suggest_history(findings, differential)
        suggested_exam = self._suggest_exam(findings, differential)

        return DifferentialResult(
            presenting_findings=findings,
            age=age,
            gender=gender,
            differential=differential,
            red_flag_diagnoses=red_flag_diagnoses,
            cannot_miss_diagnoses=cannot_miss,
            suggested_history=suggested_history,
            suggested_exam=suggested_exam,
        )

    def _suggest_history(
        self, findings: list[str], differential: list[DiagnosisCandidate]
    ) -> list[str]:
        """Suggest additional history questions based on differential."""
        suggestions = []

        # Check for certain finding patterns
        normalized = [self.normalize_finding(f) for f in findings]

        if "chest_pain" in normalized:
            suggestions.extend([
                "Character of pain (sharp, dull, pressure)?",
                "Radiation pattern?",
                "Aggravating/relieving factors?",
                "Associated symptoms (diaphoresis, nausea)?",
            ])

        if "dyspnea" in normalized:
            suggestions.extend([
                "Onset (sudden vs gradual)?",
                "Positional component (orthopnea, PND)?",
                "Exercise tolerance?",
            ])

        if "headache" in normalized:
            suggestions.extend([
                "Onset and severity?",
                "Prior similar headaches?",
                "Associated symptoms (vision changes, nausea)?",
                "Fever or neck stiffness?",
            ])

        if any("pain" in f for f in normalized):
            suggestions.extend([
                "Pain severity (0-10)?",
                "Duration?",
                "Previous episodes?",
            ])

        return list(set(suggestions))[:8]

    def _suggest_exam(
        self, findings: list[str], differential: list[DiagnosisCandidate]
    ) -> list[str]:
        """Suggest physical exam maneuvers based on differential."""
        suggestions = []

        # Based on top diagnoses
        for dx in differential[:3]:
            if dx.domain == ClinicalDomain.CARDIOVASCULAR:
                suggestions.extend([
                    "Cardiac auscultation",
                    "JVD assessment",
                    "Peripheral edema",
                    "Lung auscultation for rales",
                ])
            elif dx.domain == ClinicalDomain.RESPIRATORY:
                suggestions.extend([
                    "Lung auscultation",
                    "Respiratory rate",
                    "Oxygen saturation",
                    "Work of breathing",
                ])
            elif dx.domain == ClinicalDomain.NEUROLOGICAL:
                suggestions.extend([
                    "Neurological exam (cranial nerves, motor, sensory)",
                    "Meningeal signs (Kernig, Brudzinski)",
                    "Gait assessment",
                ])
            elif dx.domain == ClinicalDomain.GASTROINTESTINAL:
                suggestions.extend([
                    "Abdominal exam (inspection, auscultation, palpation)",
                    "Rebound/guarding assessment",
                    "Murphy's sign",
                    "Costovertebral angle tenderness",
                ])

        return list(set(suggestions))[:8]

    def _build_diagnosis_cer(
        self,
        dx: DiagnosisTemplate,
        supporting: list[str],
        opposing: list[str],
        prob_score: float,
        classic_count: int,
        age: int | None,
        gender: str | None,
    ) -> DiagnosisCERCitation:
        """Build a CER (Claim-Evidence-Reasoning) citation for a diagnosis.

        This provides structured clinical reasoning for why a diagnosis is considered.
        """
        # Build the claim based on probability
        if prob_score >= 0.7:
            probability_term = "highly likely"
        elif prob_score >= 0.5:
            probability_term = "likely"
        elif prob_score >= 0.3:
            probability_term = "possible"
        else:
            probability_term = "less likely but should be considered"

        claim = (
            f"{dx.name} is {probability_term} given the presenting findings "
            f"(estimated probability: {prob_score:.0%})"
        )

        # Build supporting evidence
        supporting_evidence: list[str] = []

        # Add matched findings as evidence
        if supporting:
            for finding in supporting[:4]:
                finding_readable = finding.replace("_", " ")
                if finding in dx.classic_findings:
                    supporting_evidence.append(f"Classic finding present: {finding_readable}")
                elif finding in dx.common_findings:
                    supporting_evidence.append(f"Common finding present: {finding_readable}")
                else:
                    supporting_evidence.append(f"Associated finding: {finding_readable}")

        # Add demographic evidence
        if age is not None and dx.age_peak:
            age_min, age_max = dx.age_peak
            if age_min <= age <= age_max:
                supporting_evidence.append(
                    f"Patient age ({age}) within peak incidence range ({age_min}-{age_max})"
                )

        if gender is not None and dx.gender_ratio != 1.0:
            if gender.lower() == "male" and dx.gender_ratio > 1.5:
                supporting_evidence.append(f"More common in males (ratio {dx.gender_ratio}:1)")
            elif gender.lower() == "female" and dx.gender_ratio < 0.7:
                supporting_evidence.append(f"More common in females (ratio 1:{1/dx.gender_ratio:.1f})")

        # Add classic findings count
        if classic_count >= 2:
            supporting_evidence.append(f"Multiple classic findings present ({classic_count})")

        # Build opposing evidence
        opposing_evidence: list[str] = []
        if opposing:
            for finding in opposing[:3]:
                finding_readable = finding.replace("_", " ")
                opposing_evidence.append(f"Atypical finding: {finding_readable}")

        # Add demographic counter-evidence
        if age is not None and dx.age_peak:
            age_min, age_max = dx.age_peak
            mid_age = (age_min + age_max) / 2
            if abs(age - mid_age) > 30:
                opposing_evidence.append(
                    f"Patient age ({age}) outside typical range ({age_min}-{age_max})"
                )

        # Build reasoning
        reasoning_parts = []

        # Core diagnostic reasoning
        if classic_count >= 2:
            reasoning_parts.append(
                f"The presence of {classic_count} classic findings strongly suggests {dx.name}."
            )
        elif classic_count == 1:
            reasoning_parts.append(
                f"One classic finding is present, supporting consideration of {dx.name}."
            )
        elif supporting:
            reasoning_parts.append(
                f"While no pathognomonic findings are present, "
                f"the constellation of {len(supporting)} associated symptoms "
                f"warrants consideration of {dx.name}."
            )

        # Urgency reasoning
        if dx.urgency == DiagnosisUrgency.EMERGENT:
            reasoning_parts.append(
                "This is a time-sensitive diagnosis requiring immediate evaluation and intervention."
            )
        elif dx.urgency == DiagnosisUrgency.URGENT:
            reasoning_parts.append(
                "This diagnosis requires prompt evaluation, typically same-day."
            )

        # Workup recommendation reasoning
        if dx.recommended_workup:
            workup_str = ", ".join(dx.recommended_workup[:3])
            reasoning_parts.append(
                f"Recommended workup ({workup_str}) will help confirm or exclude this diagnosis."
            )

        reasoning = " ".join(reasoning_parts)

        # Determine CER strength
        if prob_score >= 0.7 and classic_count >= 2:
            strength = CERStrength.STRONG
        elif prob_score >= 0.4 or classic_count >= 1:
            strength = CERStrength.MODERATE
        else:
            strength = CERStrength.WEAK

        # Build clinical pearls from key features
        clinical_pearls = dx.key_features[:4] if dx.key_features else []

        # Build diagnostic criteria (for diagnoses that have formal criteria)
        diagnostic_criteria: list[str] = []
        if dx.name == "Acute Coronary Syndrome (ACS)":
            diagnostic_criteria = [
                "ECG changes (ST elevation, depression, or T-wave inversion)",
                "Elevated cardiac biomarkers (troponin)",
                "Characteristic symptoms",
            ]
        elif dx.name == "Meningitis":
            diagnostic_criteria = [
                "Classic triad: fever, headache, neck stiffness",
                "CSF analysis abnormalities",
                "Positive meningeal signs",
            ]
        elif dx.name == "Diabetic Ketoacidosis":
            diagnostic_criteria = [
                "Blood glucose >250 mg/dL",
                "Arterial pH <7.3 or bicarbonate <18 mEq/L",
                "Positive serum or urine ketones",
                "Anion gap >10",
            ]

        # Build must-rule-out list for emergent diagnoses
        must_rule_out: list[str] = []
        if dx.urgency == DiagnosisUrgency.EMERGENT:
            must_rule_out = dx.red_flags[:3] if dx.red_flags else []

        return DiagnosisCERCitation(
            claim=claim,
            supporting_evidence=supporting_evidence,
            opposing_evidence=opposing_evidence,
            reasoning=reasoning,
            strength=strength,
            clinical_pearls=clinical_pearls,
            diagnostic_criteria=diagnostic_criteria,
            must_rule_out=must_rule_out,
        )

    def get_diagnoses_by_domain(self, domain: ClinicalDomain) -> list[DiagnosisTemplate]:
        """Get all diagnoses in a specific domain."""
        return [dx for dx in self._diagnoses if dx.domain == domain]

    def get_diagnosis_by_name(self, name: str) -> DiagnosisTemplate | None:
        """Get a specific diagnosis template by name."""
        for dx in self._diagnoses:
            if dx.name.lower() == name.lower():
                return dx
        return None

    def get_stats(self) -> dict:
        """Get statistics about the diagnosis database."""
        by_domain: dict[str, int] = {}
        by_urgency: dict[str, int] = {}

        for dx in self._diagnoses:
            domain = dx.domain.value
            by_domain[domain] = by_domain.get(domain, 0) + 1

            urgency = dx.urgency.value
            by_urgency[urgency] = by_urgency.get(urgency, 0) + 1

        return {
            "total_diagnoses": len(self._diagnoses),
            "total_findings": len(self._finding_index),
            "total_aliases": len(self._finding_aliases),
            "by_domain": by_domain,
            "by_urgency": by_urgency,
        }
