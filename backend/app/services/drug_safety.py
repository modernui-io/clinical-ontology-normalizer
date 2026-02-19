"""Drug Safety Checker Service.

This module provides comprehensive drug safety checking including:
- Contraindications (patient conditions where drug should not be used)
- Warnings and precautions
- Dosing considerations (age, renal, hepatic adjustments)
- Pregnancy and lactation safety
- Black box warnings
- Common adverse effects

This service integrates with RxNormService for enhanced drug name
normalization and therapeutic class identification.

Note: This is a clinical decision support tool and should not replace
clinical judgment. Always consult current prescribing information.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
import json
import logging
import os
from pathlib import Path
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.rxnorm_service import RxNormService

logger = logging.getLogger(__name__)

FIXTURE_FILE = Path(__file__).parent.parent.parent / "fixtures" / "drug_safety_profiles_expanded.json"


class SafetyLevel(Enum):
    """Safety level classifications."""

    SAFE = "safe"
    CAUTION = "caution"
    WARNING = "warning"
    CONTRAINDICATED = "contraindicated"


class PregnancyCategory(Enum):
    """FDA pregnancy categories (legacy) and current classifications."""

    A = "A"  # Adequate studies show no risk
    B = "B"  # Animal studies no risk, no human studies
    C = "C"  # Animal studies show risk, no human studies
    D = "D"  # Evidence of human fetal risk, may be acceptable
    X = "X"  # Contraindicated in pregnancy
    UNKNOWN = "unknown"


class LactationSafety(Enum):
    """Lactation safety classifications."""

    SAFE = "safe"
    PROBABLY_SAFE = "probably_safe"
    POTENTIALLY_HAZARDOUS = "potentially_hazardous"
    CONTRAINDICATED = "contraindicated"
    UNKNOWN = "unknown"


@dataclass
class DrugContraindication:
    """A contraindication for a drug."""

    condition: str
    severity: SafetyLevel
    rationale: str


@dataclass
class DosingGuideline:
    """Dosing adjustment guideline."""

    population: str  # e.g., "renal_impairment", "hepatic_impairment", "elderly"
    adjustment: str  # Description of adjustment
    reason: str


@dataclass
class DrugSafetyProfile:
    """Complete safety profile for a drug."""

    drug_name: str
    generic_name: str
    drug_class: str
    omop_concept_id: int | None = None

    # Warnings
    black_box_warnings: list[str] = field(default_factory=list)
    warnings_precautions: list[str] = field(default_factory=list)

    # Contraindications
    contraindications: list[DrugContraindication] = field(default_factory=list)

    # Special populations
    pregnancy_category: PregnancyCategory = PregnancyCategory.UNKNOWN
    pregnancy_notes: str = ""
    lactation_safety: LactationSafety = LactationSafety.UNKNOWN
    lactation_notes: str = ""
    pediatric_notes: str = ""
    geriatric_notes: str = ""

    # Dosing adjustments
    dosing_guidelines: list[DosingGuideline] = field(default_factory=list)

    # Adverse effects
    common_adverse_effects: list[str] = field(default_factory=list)
    serious_adverse_effects: list[str] = field(default_factory=list)

    # Monitoring
    monitoring_parameters: list[str] = field(default_factory=list)

    # Max doses
    max_daily_dose: str = ""
    max_single_dose: str = ""


@dataclass
class SafetyCheckResult:
    """Result of a drug safety check."""

    drug_name: str
    patient_conditions: list[str]
    overall_safety: SafetyLevel
    contraindicated_conditions: list[tuple[str, str]]  # (condition, rationale)
    warnings: list[str]
    cautions: list[str]
    dosing_considerations: list[str]
    monitoring_needed: list[str]
    pregnancy_warning: str | None
    lactation_warning: str | None
    profile: DrugSafetyProfile | None


@dataclass
class DrugInteraction:
    """A drug-drug interaction."""

    drug_a: str
    drug_b: str
    severity: str  # "major", "moderate", "minor"
    description: str
    mechanism: str
    clinical_effect: str
    management: str


@dataclass
class InteractionCheckResult:
    """Result of a drug interaction check."""

    drugs_checked: list[str]
    interactions_found: list[DrugInteraction]
    total_interactions: int
    # P1-013: Coverage status for each checked pair
    coverage_status: str = "covered"  # "covered" | "partially_covered" | "uncovered"
    drug_coverage_warning: str | None = None


@dataclass
class DrugCoverageReport:
    """Report on drug safety database coverage."""

    total_drugs_known: int
    total_interactions: int
    coverage_percent: float
    known_drug_names: list[str]


# Known drug-drug interactions
KNOWN_INTERACTIONS: list[dict] = [
    {
        "drugs": ("warfarin", "aspirin"),
        "severity": "major",
        "description": "Increased risk of bleeding",
        "mechanism": "Additive anticoagulant/antiplatelet effects",
        "clinical_effect": "Significantly increased risk of GI and intracranial hemorrhage",
        "management": "Avoid combination unless clearly indicated. Monitor INR closely if used together.",
    },
    {
        "drugs": ("warfarin", "ibuprofen"),
        "severity": "major",
        "description": "Increased anticoagulant effect and GI bleeding risk",
        "mechanism": "NSAIDs inhibit platelet function and may displace warfarin from protein binding",
        "clinical_effect": "Elevated INR and increased risk of hemorrhage",
        "management": "Avoid NSAIDs in patients on warfarin. Use acetaminophen for pain if possible.",
    },
    {
        "drugs": ("metformin", "contrast dye"),
        "severity": "major",
        "description": "Risk of lactic acidosis",
        "mechanism": "Contrast-induced nephropathy reduces metformin clearance",
        "clinical_effect": "Accumulation of metformin leading to lactic acidosis",
        "management": "Hold metformin 48 hours before and after contrast administration.",
    },
    {
        "drugs": ("lisinopril", "potassium"),
        "severity": "major",
        "description": "Risk of hyperkalemia",
        "mechanism": "ACE inhibitors reduce aldosterone-mediated potassium excretion",
        "clinical_effect": "Dangerous elevation of serum potassium levels",
        "management": "Monitor potassium levels closely. Avoid potassium supplements unless hypokalemic.",
    },
    {
        "drugs": ("metoprolol", "verapamil"),
        "severity": "major",
        "description": "Excessive cardiac depression",
        "mechanism": "Additive negative chronotropic and inotropic effects",
        "clinical_effect": "Severe bradycardia, heart block, or heart failure",
        "management": "Avoid combination. If necessary, use with extreme caution and monitoring.",
    },
    {
        "drugs": ("simvastatin", "amiodarone"),
        "severity": "major",
        "description": "Increased risk of rhabdomyolysis",
        "mechanism": "Amiodarone inhibits CYP3A4-mediated statin metabolism",
        "clinical_effect": "Elevated statin levels leading to myopathy and rhabdomyolysis",
        "management": "Limit simvastatin dose to 20mg daily when combined with amiodarone.",
    },
    {
        "drugs": ("fluoxetine", "tramadol"),
        "severity": "major",
        "description": "Serotonin syndrome risk",
        "mechanism": "Additive serotonergic effects",
        "clinical_effect": "Hyperthermia, rigidity, myoclonus, autonomic instability",
        "management": "Avoid combination. Use alternative analgesic without serotonergic activity.",
    },
    {
        "drugs": ("ciprofloxacin", "theophylline"),
        "severity": "major",
        "description": "Theophylline toxicity",
        "mechanism": "Ciprofloxacin inhibits CYP1A2-mediated theophylline metabolism",
        "clinical_effect": "Nausea, vomiting, seizures, cardiac arrhythmias",
        "management": "Reduce theophylline dose by 30-50% or use alternative antibiotic.",
    },
    {
        "drugs": ("methotrexate", "ibuprofen"),
        "severity": "major",
        "description": "Methotrexate toxicity",
        "mechanism": "NSAIDs reduce renal clearance of methotrexate",
        "clinical_effect": "Pancytopenia, mucositis, renal failure",
        "management": "Avoid NSAIDs with high-dose methotrexate. Monitor CBC and renal function.",
    },
    {
        "drugs": ("digoxin", "amiodarone"),
        "severity": "major",
        "description": "Digoxin toxicity",
        "mechanism": "Amiodarone increases digoxin levels via P-glycoprotein inhibition",
        "clinical_effect": "Nausea, visual changes, cardiac arrhythmias",
        "management": "Reduce digoxin dose by 50% when initiating amiodarone. Monitor levels.",
    },
    {
        "drugs": ("lisinopril", "spironolactone"),
        "severity": "moderate",
        "description": "Risk of hyperkalemia",
        "mechanism": "Both agents increase serum potassium through different mechanisms",
        "clinical_effect": "Hyperkalemia with potential cardiac effects",
        "management": "Monitor potassium levels regularly. Avoid in patients with renal impairment.",
    },
    {
        "drugs": ("metformin", "alcohol"),
        "severity": "moderate",
        "description": "Increased risk of lactic acidosis",
        "mechanism": "Alcohol impairs gluconeogenesis and may worsen metformin-related lactate accumulation",
        "clinical_effect": "Hypoglycemia and lactic acidosis",
        "management": "Advise patients to limit alcohol intake while on metformin.",
    },
    {
        "drugs": ("amlodipine", "simvastatin"),
        "severity": "moderate",
        "description": "Increased statin exposure",
        "mechanism": "Amlodipine inhibits CYP3A4 metabolism of simvastatin",
        "clinical_effect": "Increased risk of myopathy",
        "management": "Limit simvastatin to 20mg daily when combined with amlodipine.",
    },
    {
        "drugs": ("omeprazole", "clopidogrel"),
        "severity": "moderate",
        "description": "Reduced clopidogrel efficacy",
        "mechanism": "Omeprazole inhibits CYP2C19 activation of clopidogrel",
        "clinical_effect": "Reduced antiplatelet effect, increased cardiovascular risk",
        "management": "Use pantoprazole or famotidine instead of omeprazole.",
    },
    {
        "drugs": ("lisinopril", "ibuprofen"),
        "severity": "moderate",
        "description": "Reduced antihypertensive effect and renal risk",
        "mechanism": "NSAIDs inhibit prostaglandin-mediated renal blood flow",
        "clinical_effect": "Elevated blood pressure and risk of acute kidney injury",
        "management": "Use lowest NSAID dose for shortest duration. Monitor BP and renal function.",
    },
]


# ============================================================================
# Drug Safety Database
# ============================================================================

DRUG_SAFETY_PROFILES: list[DrugSafetyProfile] = [
    # =========================================================================
    # CARDIOVASCULAR
    # =========================================================================
    DrugSafetyProfile(
        drug_name="Warfarin",
        generic_name="warfarin",
        drug_class="Anticoagulant",
        omop_concept_id=1310149,
        black_box_warnings=[
            "Can cause major or fatal bleeding",
            "Risk of bleeding is increased in patients with atrial fibrillation who undergo spinal/epidural anesthesia",
        ],
        warnings_precautions=[
            "Regular INR monitoring required",
            "Numerous drug and food interactions",
            "Vitamin K intake should be consistent",
        ],
        contraindications=[
            DrugContraindication("Active bleeding", SafetyLevel.CONTRAINDICATED, "Risk of hemorrhagic complications"),
            DrugContraindication("Hemorrhagic stroke", SafetyLevel.CONTRAINDICATED, "May worsen bleeding"),
            DrugContraindication("Severe uncontrolled hypertension", SafetyLevel.CONTRAINDICATED, "Increased bleeding risk"),
            DrugContraindication("Recent surgery", SafetyLevel.WARNING, "Increased bleeding risk perioperatively"),
            DrugContraindication("Peptic ulcer disease", SafetyLevel.WARNING, "Increased GI bleeding risk"),
            DrugContraindication("Thrombocytopenia", SafetyLevel.WARNING, "Compounded bleeding risk"),
        ],
        pregnancy_category=PregnancyCategory.X,
        pregnancy_notes="Teratogenic, can cause fetal warfarin syndrome. Use LMWH in pregnancy instead.",
        lactation_safety=LactationSafety.PROBABLY_SAFE,
        lactation_notes="Minimal excretion in breast milk, considered compatible.",
        geriatric_notes="Increased sensitivity, start with lower doses. Falls risk assessment important.",
        dosing_guidelines=[
            DosingGuideline("elderly", "Start at lower dose (2-5mg), more frequent INR monitoring", "Increased sensitivity"),
            DosingGuideline("hepatic_impairment", "Reduced doses, closer monitoring", "Decreased metabolism"),
            DosingGuideline("renal_impairment", "No specific adjustment, but monitor closely", "Increased bleeding risk"),
        ],
        common_adverse_effects=["Bleeding", "Bruising", "Hematuria"],
        serious_adverse_effects=["Major hemorrhage", "Skin necrosis", "Purple toe syndrome"],
        monitoring_parameters=["INR (target 2-3 for most indications)", "Signs of bleeding", "Hemoglobin/Hematocrit"],
    ),
    DrugSafetyProfile(
        drug_name="Metoprolol",
        generic_name="metoprolol",
        drug_class="Beta-blocker",
        omop_concept_id=1307046,
        black_box_warnings=[],
        warnings_precautions=[
            "Do not abruptly discontinue - taper over 1-2 weeks",
            "May mask symptoms of hypoglycemia in diabetics",
            "May exacerbate peripheral vascular disease",
        ],
        contraindications=[
            DrugContraindication("Severe bradycardia", SafetyLevel.CONTRAINDICATED, "May worsen bradycardia"),
            DrugContraindication("Heart block (2nd/3rd degree)", SafetyLevel.CONTRAINDICATED, "Risk of complete heart block"),
            DrugContraindication("Cardiogenic shock", SafetyLevel.CONTRAINDICATED, "Negative inotropic effect"),
            DrugContraindication("Decompensated heart failure", SafetyLevel.CONTRAINDICATED, "May worsen failure acutely"),
            DrugContraindication("Severe asthma/COPD", SafetyLevel.WARNING, "May cause bronchospasm"),
            DrugContraindication("Pheochromocytoma (untreated)", SafetyLevel.CONTRAINDICATED, "Risk of hypertensive crisis"),
        ],
        pregnancy_category=PregnancyCategory.C,
        pregnancy_notes="May cause fetal bradycardia and hypoglycemia. Use only if benefit outweighs risk.",
        lactation_safety=LactationSafety.PROBABLY_SAFE,
        lactation_notes="Small amounts excreted, considered compatible with breastfeeding.",
        geriatric_notes="Start low, go slow. Increased risk of bradycardia and hypotension.",
        dosing_guidelines=[
            DosingGuideline("hepatic_impairment", "Consider dose reduction with severe impairment", "Hepatic metabolism"),
            DosingGuideline("renal_impairment", "No adjustment needed", "Hepatically eliminated"),
        ],
        common_adverse_effects=["Fatigue", "Dizziness", "Bradycardia", "Cold extremities"],
        serious_adverse_effects=["Severe bradycardia", "Heart block", "Bronchospasm", "Heart failure exacerbation"],
        monitoring_parameters=["Heart rate", "Blood pressure", "Signs of heart failure"],
    ),
    DrugSafetyProfile(
        drug_name="Lisinopril",
        generic_name="lisinopril",
        drug_class="ACE Inhibitor",
        omop_concept_id=1308216,
        black_box_warnings=[
            "Can cause fetal injury and death when used during 2nd and 3rd trimesters",
        ],
        warnings_precautions=[
            "Risk of angioedema, higher in Black patients",
            "May cause hyperkalemia",
            "Risk of acute kidney injury, especially with NSAIDs or volume depletion",
        ],
        contraindications=[
            DrugContraindication("History of ACE inhibitor angioedema", SafetyLevel.CONTRAINDICATED, "Life-threatening reaction"),
            DrugContraindication("Hereditary/idiopathic angioedema", SafetyLevel.CONTRAINDICATED, "May precipitate attacks"),
            DrugContraindication("Bilateral renal artery stenosis", SafetyLevel.CONTRAINDICATED, "Risk of acute renal failure"),
            DrugContraindication("Pregnancy", SafetyLevel.CONTRAINDICATED, "Teratogenic in 2nd/3rd trimester"),
            DrugContraindication("Hyperkalemia", SafetyLevel.WARNING, "May worsen hyperkalemia"),
            DrugContraindication("Severe aortic stenosis", SafetyLevel.WARNING, "Risk of hypotension"),
        ],
        pregnancy_category=PregnancyCategory.D,
        pregnancy_notes="Contraindicated in 2nd/3rd trimester. May cause oligohydramnios, fetal renal failure, skull hypoplasia.",
        lactation_safety=LactationSafety.PROBABLY_SAFE,
        lactation_notes="Present in breast milk in small amounts, considered compatible.",
        geriatric_notes="Start with lower doses. Monitor renal function and potassium.",
        dosing_guidelines=[
            DosingGuideline("renal_impairment", "CrCl 10-30: Start 2.5-5mg; CrCl <10: Start 2.5mg", "Renally eliminated"),
            DosingGuideline("hepatic_impairment", "No adjustment needed", "Not hepatically metabolized"),
        ],
        common_adverse_effects=["Cough (dry)", "Dizziness", "Headache", "Hyperkalemia"],
        serious_adverse_effects=["Angioedema", "Acute kidney injury", "Severe hypotension"],
        monitoring_parameters=["Blood pressure", "Potassium", "Creatinine/BUN", "Cough"],
    ),
    # =========================================================================
    # DIABETES
    # =========================================================================
    DrugSafetyProfile(
        drug_name="Metformin",
        generic_name="metformin",
        drug_class="Biguanide",
        omop_concept_id=1503297,
        black_box_warnings=[
            "Lactic acidosis is a rare but serious complication. Risk increased with renal impairment, dehydration, sepsis, excessive alcohol, hepatic insufficiency, and acute heart failure.",
        ],
        warnings_precautions=[
            "Hold before and after iodinated contrast procedures",
            "Temporarily discontinue before surgery",
            "May cause vitamin B12 deficiency with long-term use",
        ],
        contraindications=[
            DrugContraindication("Severe renal impairment (eGFR <30)", SafetyLevel.CONTRAINDICATED, "Risk of lactic acidosis"),
            DrugContraindication("Metabolic acidosis", SafetyLevel.CONTRAINDICATED, "Risk of lactic acidosis"),
            DrugContraindication("Decompensated heart failure", SafetyLevel.CONTRAINDICATED, "Risk of lactic acidosis"),
            DrugContraindication("Severe hepatic impairment", SafetyLevel.CONTRAINDICATED, "Impaired lactate clearance"),
            DrugContraindication("Moderate renal impairment (eGFR 30-45)", SafetyLevel.CAUTION, "Consider dose reduction"),
            DrugContraindication("Alcohol abuse", SafetyLevel.WARNING, "Increased lactic acidosis risk"),
        ],
        pregnancy_category=PregnancyCategory.B,
        pregnancy_notes="May be used in gestational diabetes. Switch to insulin if glycemic control inadequate.",
        lactation_safety=LactationSafety.PROBABLY_SAFE,
        lactation_notes="Present in breast milk in small amounts, no adverse effects reported.",
        geriatric_notes="Assess renal function before starting and periodically. Avoid in >80 years if CrCl not measured.",
        dosing_guidelines=[
            DosingGuideline("renal_impairment", "eGFR 30-45: Max 1000mg/day; eGFR <30: Contraindicated", "Renally cleared"),
            DosingGuideline("hepatic_impairment", "Avoid use due to lactic acidosis risk", "Impaired lactate metabolism"),
            DosingGuideline("elderly", "Start at lower dose, monitor renal function", "Age-related renal decline"),
        ],
        common_adverse_effects=["Diarrhea", "Nausea", "Abdominal discomfort", "Metallic taste"],
        serious_adverse_effects=["Lactic acidosis", "Vitamin B12 deficiency"],
        monitoring_parameters=["Renal function (at least annually)", "Vitamin B12 levels", "Blood glucose/A1c"],
    ),
    DrugSafetyProfile(
        drug_name="Insulin",
        generic_name="insulin",
        drug_class="Antidiabetic",
        omop_concept_id=21600713,
        black_box_warnings=[],
        warnings_precautions=[
            "Hypoglycemia is the most common adverse effect",
            "Changes in insulin regimen should be made cautiously",
            "Never share insulin pens between patients",
        ],
        contraindications=[
            DrugContraindication("Hypoglycemia", SafetyLevel.CONTRAINDICATED, "Will worsen hypoglycemia"),
            DrugContraindication("Hypokalemia", SafetyLevel.WARNING, "Insulin drives potassium into cells"),
        ],
        pregnancy_category=PregnancyCategory.B,
        pregnancy_notes="Insulin is the preferred agent for diabetes in pregnancy. Does not cross placenta.",
        lactation_safety=LactationSafety.SAFE,
        lactation_notes="Compatible with breastfeeding. Destroyed in infant's GI tract.",
        geriatric_notes="Higher risk of hypoglycemia. Less stringent glycemic targets may be appropriate.",
        dosing_guidelines=[
            DosingGuideline("renal_impairment", "Reduce dose and monitor closely", "Decreased insulin clearance"),
            DosingGuideline("hepatic_impairment", "Reduce dose and monitor closely", "Decreased gluconeogenesis"),
        ],
        common_adverse_effects=["Hypoglycemia", "Weight gain", "Injection site reactions"],
        serious_adverse_effects=["Severe hypoglycemia", "Hypokalemia"],
        monitoring_parameters=["Blood glucose", "A1c", "Signs of hypoglycemia", "Potassium (if at risk)"],
    ),
    # =========================================================================
    # ANTIINFECTIVES
    # =========================================================================
    DrugSafetyProfile(
        drug_name="Ciprofloxacin",
        generic_name="ciprofloxacin",
        drug_class="Fluoroquinolone",
        omop_concept_id=1797513,
        black_box_warnings=[
            "Tendinitis and tendon rupture risk, especially in patients >60, those taking corticosteroids, or organ transplant recipients",
            "May exacerbate muscle weakness in myasthenia gravis",
            "Associated with disabling and potentially irreversible adverse reactions (peripheral neuropathy, CNS effects)",
        ],
        warnings_precautions=[
            "Avoid excessive sun exposure",
            "May prolong QT interval",
            "CNS effects including seizures, dizziness, confusion",
        ],
        contraindications=[
            DrugContraindication("Myasthenia gravis", SafetyLevel.CONTRAINDICATED, "May exacerbate weakness"),
            DrugContraindication("History of tendon disorders with fluoroquinolones", SafetyLevel.CONTRAINDICATED, "Increased rupture risk"),
            DrugContraindication("QT prolongation", SafetyLevel.WARNING, "May worsen QT prolongation"),
            DrugContraindication("Seizure disorder", SafetyLevel.CAUTION, "May lower seizure threshold"),
            DrugContraindication("Renal impairment", SafetyLevel.CAUTION, "Dose adjustment needed"),
        ],
        pregnancy_category=PregnancyCategory.C,
        pregnancy_notes="Animal studies show cartilage damage in young animals. Use only if no safer alternative.",
        lactation_safety=LactationSafety.PROBABLY_SAFE,
        lactation_notes="Present in breast milk. American Academy of Pediatrics considers compatible.",
        geriatric_notes="Higher risk of tendon rupture, QT prolongation, and CNS effects. Use with caution.",
        pediatric_notes="Not first-line in children due to concerns about cartilage damage.",
        dosing_guidelines=[
            DosingGuideline("renal_impairment", "CrCl 30-50: 250-500mg q12h; CrCl <30: 250-500mg q18h", "Renally eliminated"),
            DosingGuideline("hepatic_impairment", "No adjustment for mild-moderate", "Partially hepatic metabolism"),
        ],
        common_adverse_effects=["Nausea", "Diarrhea", "Headache", "Dizziness"],
        serious_adverse_effects=["Tendon rupture", "QT prolongation", "C. diff colitis", "Peripheral neuropathy"],
        monitoring_parameters=["Renal function", "Signs of tendinitis", "QT interval if at risk"],
    ),
    DrugSafetyProfile(
        drug_name="Vancomycin",
        generic_name="vancomycin",
        drug_class="Glycopeptide Antibiotic",
        omop_concept_id=1707687,
        black_box_warnings=[],
        warnings_precautions=[
            "Nephrotoxicity risk, especially with other nephrotoxins",
            "Ototoxicity with prolonged use or high trough levels",
            "Red man syndrome with rapid infusion",
        ],
        contraindications=[
            DrugContraindication("Vancomycin allergy", SafetyLevel.CONTRAINDICATED, "Hypersensitivity reaction"),
            DrugContraindication("Renal impairment", SafetyLevel.CAUTION, "Dose adjustment and monitoring required"),
            DrugContraindication("Concurrent nephrotoxins", SafetyLevel.WARNING, "Additive nephrotoxicity"),
        ],
        pregnancy_category=PregnancyCategory.C,
        pregnancy_notes="No adequate human studies. Use if clearly needed.",
        lactation_safety=LactationSafety.PROBABLY_SAFE,
        lactation_notes="Poorly absorbed orally by infant. Consider compatible.",
        geriatric_notes="Higher risk of nephrotoxicity. Dose based on renal function and monitor levels.",
        dosing_guidelines=[
            DosingGuideline("renal_impairment", "Dose based on CrCl and levels. May need q24-48h dosing", "Renally eliminated"),
            DosingGuideline("hemodialysis", "Dose after dialysis, monitor levels", "Partially removed by HD"),
            DosingGuideline("obesity", "Use actual body weight for dosing up to 2g", "Vd increases with weight"),
        ],
        common_adverse_effects=["Red man syndrome (if infused too fast)", "Phlebitis", "Nausea"],
        serious_adverse_effects=["Nephrotoxicity", "Ototoxicity", "DRESS syndrome"],
        monitoring_parameters=["Vancomycin trough levels (15-20 for serious infections)", "Creatinine", "Hearing"],
        max_daily_dose="4g for most infections (higher doses may be used)",
    ),
    # =========================================================================
    # PAIN/ANTIINFLAMMATORY
    # =========================================================================
    DrugSafetyProfile(
        drug_name="Ibuprofen",
        generic_name="ibuprofen",
        drug_class="NSAID",
        omop_concept_id=1177480,
        black_box_warnings=[
            "NSAIDs increase risk of serious cardiovascular thrombotic events, MI, and stroke",
            "NSAIDs increase risk of serious GI adverse events including bleeding, ulceration, and perforation",
        ],
        warnings_precautions=[
            "Avoid in patients with recent CABG surgery",
            "May cause renal impairment, especially with dehydration or CKD",
            "Use lowest effective dose for shortest duration",
        ],
        contraindications=[
            DrugContraindication("Active GI bleeding", SafetyLevel.CONTRAINDICATED, "May worsen bleeding"),
            DrugContraindication("History of GI ulcer/bleeding", SafetyLevel.WARNING, "Increased recurrence risk"),
            DrugContraindication("Severe heart failure", SafetyLevel.CONTRAINDICATED, "Fluid retention, worsening failure"),
            DrugContraindication("Advanced CKD (stage 4-5)", SafetyLevel.CONTRAINDICATED, "May worsen renal function"),
            DrugContraindication("Aspirin-sensitive asthma", SafetyLevel.CONTRAINDICATED, "Cross-reactivity, bronchospasm"),
            DrugContraindication("Third trimester pregnancy", SafetyLevel.CONTRAINDICATED, "Premature ductus closure"),
            DrugContraindication("Coronary artery disease", SafetyLevel.WARNING, "Increased cardiovascular events"),
            DrugContraindication("Concurrent anticoagulation", SafetyLevel.WARNING, "Increased bleeding risk"),
        ],
        pregnancy_category=PregnancyCategory.C,
        pregnancy_notes="Avoid in 3rd trimester (premature ductus closure). Category D in 3rd trimester.",
        lactation_safety=LactationSafety.PROBABLY_SAFE,
        lactation_notes="Short-term use compatible. Prefer acetaminophen if possible.",
        geriatric_notes="Higher GI bleeding risk. Start at lowest dose. Consider gastroprotection.",
        dosing_guidelines=[
            DosingGuideline("renal_impairment", "Avoid if CrCl <30. Use lowest dose if mild impairment", "May worsen renal function"),
            DosingGuideline("hepatic_impairment", "Use with caution in severe impairment", "Hepatic metabolism"),
            DosingGuideline("elderly", "Start at lowest effective dose, shorter duration", "Increased GI/renal/CV risk"),
        ],
        common_adverse_effects=["Dyspepsia", "Nausea", "Abdominal pain", "Edema"],
        serious_adverse_effects=["GI bleeding/perforation", "MI/stroke", "Acute kidney injury", "Heart failure"],
        monitoring_parameters=["Renal function", "Blood pressure", "Signs of GI bleeding", "Edema"],
        max_daily_dose="3200mg (OTC: 1200mg)",
    ),
    DrugSafetyProfile(
        drug_name="Oxycodone",
        generic_name="oxycodone",
        drug_class="Opioid Analgesic",
        omop_concept_id=1124957,
        black_box_warnings=[
            "Risk of addiction, abuse, and misuse leading to overdose and death",
            "Risk of life-threatening respiratory depression",
            "Accidental exposure, especially in children, can be fatal",
            "Concomitant use with benzodiazepines or other CNS depressants may result in profound sedation, respiratory depression, coma, and death",
            "Prolonged use during pregnancy can cause neonatal opioid withdrawal syndrome",
        ],
        warnings_precautions=[
            "Screen for opioid use disorder risk",
            "Use lowest effective dose for shortest duration",
            "Consider naloxone prescription for overdose risk",
        ],
        contraindications=[
            DrugContraindication("Significant respiratory depression", SafetyLevel.CONTRAINDICATED, "May cause fatal respiratory arrest"),
            DrugContraindication("Acute/severe asthma", SafetyLevel.CONTRAINDICATED, "Respiratory depression risk"),
            DrugContraindication("GI obstruction (including ileus)", SafetyLevel.CONTRAINDICATED, "May worsen obstruction"),
            DrugContraindication("Concurrent MAO inhibitor use", SafetyLevel.CONTRAINDICATED, "Serotonin syndrome risk"),
            DrugContraindication("Head injury/increased ICP", SafetyLevel.WARNING, "May increase ICP, obscure neuro exam"),
            DrugContraindication("Sleep apnea", SafetyLevel.WARNING, "Increased respiratory depression risk"),
            DrugContraindication("Concurrent benzodiazepine use", SafetyLevel.WARNING, "Synergistic respiratory depression"),
        ],
        pregnancy_category=PregnancyCategory.C,
        pregnancy_notes="Prolonged use can cause neonatal withdrawal. Use only if clearly needed.",
        lactation_safety=LactationSafety.POTENTIALLY_HAZARDOUS,
        lactation_notes="Excreted in breast milk. May cause sedation and respiratory depression in nursing infant.",
        geriatric_notes="Start at 1/3 to 1/2 usual dose. Increased sensitivity to opioids.",
        dosing_guidelines=[
            DosingGuideline("renal_impairment", "Reduce dose by 50% if CrCl <30, extend interval", "Accumulation of metabolites"),
            DosingGuideline("hepatic_impairment", "Start with lowest dose, extend interval", "Decreased metabolism"),
            DosingGuideline("opioid_naive", "Start 5-10mg IR q4-6h as needed", "Risk of respiratory depression"),
        ],
        common_adverse_effects=["Constipation", "Nausea", "Drowsiness", "Dizziness", "Pruritus"],
        serious_adverse_effects=["Respiratory depression", "Overdose", "Dependence/addiction", "Serotonin syndrome"],
        monitoring_parameters=["Pain level", "Respiratory rate", "Sedation", "Signs of misuse/abuse", "Bowel function"],
    ),
    # =========================================================================
    # PSYCHIATRIC
    # =========================================================================
    DrugSafetyProfile(
        drug_name="Sertraline",
        generic_name="sertraline",
        drug_class="SSRI",
        omop_concept_id=739138,
        black_box_warnings=[
            "Antidepressants increase risk of suicidal thinking and behavior in children, adolescents, and young adults with major depressive disorder and other psychiatric disorders",
        ],
        warnings_precautions=[
            "Risk of serotonin syndrome, especially with other serotonergic drugs",
            "May increase bleeding risk, especially with anticoagulants or NSAIDs",
            "Discontinuation syndrome if stopped abruptly - taper gradually",
        ],
        contraindications=[
            DrugContraindication("Concurrent MAO inhibitor use", SafetyLevel.CONTRAINDICATED, "Serotonin syndrome risk"),
            DrugContraindication("Concurrent pimozide use", SafetyLevel.CONTRAINDICATED, "QT prolongation"),
            DrugContraindication("Bipolar disorder (undiagnosed)", SafetyLevel.WARNING, "May precipitate mania"),
            DrugContraindication("Bleeding disorders", SafetyLevel.CAUTION, "SSRIs impair platelet function"),
            DrugContraindication("Seizure disorder", SafetyLevel.CAUTION, "May lower seizure threshold"),
        ],
        pregnancy_category=PregnancyCategory.C,
        pregnancy_notes="PPHN risk if used in 3rd trimester. Weigh benefits vs risks. Do not abruptly stop.",
        lactation_safety=LactationSafety.PROBABLY_SAFE,
        lactation_notes="Lowest plasma levels among SSRIs. Considered compatible.",
        geriatric_notes="May need lower starting dose. Monitor for hyponatremia (SIADH).",
        pediatric_notes="Monitor closely for suicidal ideation, especially early in treatment.",
        dosing_guidelines=[
            DosingGuideline("hepatic_impairment", "Use lower dose or less frequent dosing", "Decreased metabolism"),
            DosingGuideline("renal_impairment", "No adjustment needed for mild-moderate", "Primarily hepatic metabolism"),
        ],
        common_adverse_effects=["Nausea", "Diarrhea", "Insomnia", "Sexual dysfunction", "Headache"],
        serious_adverse_effects=["Serotonin syndrome", "Suicidal ideation", "Hyponatremia", "Bleeding", "QT prolongation"],
        monitoring_parameters=["Depression/suicidal thoughts", "Signs of mania", "Sodium (in elderly)", "Bleeding signs"],
    ),
    # =========================================================================
    # ADDITIONAL COMMON DRUGS
    # =========================================================================
    DrugSafetyProfile(
        drug_name="Amoxicillin",
        generic_name="amoxicillin",
        drug_class="Penicillin Antibiotic",
        omop_concept_id=1713332,
        black_box_warnings=[],
        warnings_precautions=[
            "Cross-reactivity with cephalosporins in penicillin-allergic patients",
            "May cause C. difficile-associated diarrhea",
        ],
        contraindications=[
            DrugContraindication("Penicillin allergy", SafetyLevel.CONTRAINDICATED, "Risk of anaphylaxis"),
            DrugContraindication("Cephalosporin allergy (with anaphylaxis)", SafetyLevel.WARNING, "Cross-reactivity possible"),
            DrugContraindication("Mononucleosis", SafetyLevel.CAUTION, "High incidence of rash"),
        ],
        pregnancy_category=PregnancyCategory.B,
        pregnancy_notes="Considered safe in pregnancy. Widely used for UTIs, respiratory infections.",
        lactation_safety=LactationSafety.SAFE,
        lactation_notes="Compatible with breastfeeding. Small amounts in milk.",
        dosing_guidelines=[
            DosingGuideline("renal_impairment", "CrCl 10-30: 250-500mg q12h; CrCl <10: 250-500mg q24h", "Renally eliminated"),
        ],
        common_adverse_effects=["Diarrhea", "Nausea", "Rash"],
        serious_adverse_effects=["Anaphylaxis", "C. diff colitis", "Stevens-Johnson syndrome (rare)"],
        monitoring_parameters=["Allergic reactions", "Signs of C. diff (severe diarrhea)"],
    ),
    DrugSafetyProfile(
        drug_name="Amlodipine",
        generic_name="amlodipine",
        drug_class="Calcium Channel Blocker",
        omop_concept_id=1332418,
        black_box_warnings=[],
        warnings_precautions=[
            "May cause peripheral edema, especially at higher doses",
            "Caution in severe aortic stenosis",
        ],
        contraindications=[
            DrugContraindication("Severe hypotension", SafetyLevel.CONTRAINDICATED, "May worsen hypotension"),
            DrugContraindication("Severe aortic stenosis", SafetyLevel.CAUTION, "Risk of hypotension"),
            DrugContraindication("Cardiogenic shock", SafetyLevel.CONTRAINDICATED, "Negative inotropic effect"),
        ],
        pregnancy_category=PregnancyCategory.C,
        pregnancy_notes="Limited human data. Other antihypertensives preferred (e.g., labetalol, methyldopa).",
        lactation_safety=LactationSafety.PROBABLY_SAFE,
        lactation_notes="Present in milk. Limited data but likely compatible.",
        geriatric_notes="Start with lower dose (2.5-5mg). Higher plasma levels in elderly.",
        dosing_guidelines=[
            DosingGuideline("hepatic_impairment", "Start at 2.5mg daily, titrate slowly", "Decreased metabolism"),
            DosingGuideline("elderly", "Start at 2.5mg daily", "Increased sensitivity"),
        ],
        common_adverse_effects=["Peripheral edema", "Headache", "Flushing", "Dizziness"],
        serious_adverse_effects=["Severe hypotension", "Worsening angina (rare)"],
        monitoring_parameters=["Blood pressure", "Heart rate", "Peripheral edema"],
    ),
    DrugSafetyProfile(
        drug_name="Gabapentin",
        generic_name="gabapentin",
        drug_class="Anticonvulsant",
        omop_concept_id=797399,
        black_box_warnings=[],
        warnings_precautions=[
            "CNS depression, especially with opioids",
            "Risk of respiratory depression when combined with CNS depressants",
            "Do not abruptly discontinue - taper over at least 1 week",
        ],
        contraindications=[
            DrugContraindication("Severe renal impairment", SafetyLevel.CAUTION, "Requires significant dose reduction"),
            DrugContraindication("Concurrent opioid use", SafetyLevel.WARNING, "Increased CNS depression and respiratory risk"),
        ],
        pregnancy_category=PregnancyCategory.C,
        pregnancy_notes="May cause fetal harm. Use only if benefit outweighs risk.",
        lactation_safety=LactationSafety.PROBABLY_SAFE,
        lactation_notes="Present in breast milk but poorly absorbed orally. Likely compatible.",
        geriatric_notes="Start at lower doses. Higher risk of CNS effects and falls.",
        dosing_guidelines=[
            DosingGuideline("renal_impairment", "CrCl 30-59: Max 600mg TID; CrCl 15-29: Max 300mg BID; CrCl <15: Max 300mg daily", "Renally eliminated unchanged"),
            DosingGuideline("hemodialysis", "300mg after each HD session", "Removed by dialysis"),
        ],
        common_adverse_effects=["Dizziness", "Somnolence", "Peripheral edema", "Ataxia"],
        serious_adverse_effects=["Respiratory depression (with opioids)", "Suicidal ideation", "Angioedema (rare)"],
        monitoring_parameters=["Sedation", "Dizziness/falls", "Suicidal thoughts", "Renal function"],
    ),
]

# Drug name aliases for lookup
DRUG_ALIASES: dict[str, str] = {
    "coumadin": "warfarin",
    "lopressor": "metoprolol",
    "toprol": "metoprolol",
    "toprol xl": "metoprolol",
    "zestril": "lisinopril",
    "prinivil": "lisinopril",
    "glucophage": "metformin",
    "cipro": "ciprofloxacin",
    "motrin": "ibuprofen",
    "advil": "ibuprofen",
    "percocet": "oxycodone",
    "oxycontin": "oxycodone",
    "zoloft": "sertraline",
    "amoxil": "amoxicillin",
    "norvasc": "amlodipine",
    "neurontin": "gabapentin",
    "gralise": "gabapentin",
}


# ============================================================================
# Load Extended Drug Safety Profiles from Fixture
# ============================================================================


def _pregnancy_category_from_string(category: str) -> PregnancyCategory:
    """Convert pregnancy category string to enum."""
    category_map = {
        "A": PregnancyCategory.A,
        "B": PregnancyCategory.B,
        "C": PregnancyCategory.C,
        "D": PregnancyCategory.D,
        "X": PregnancyCategory.X,
        "C/D": PregnancyCategory.C,  # Take the safer category
    }
    return category_map.get(category.upper(), PregnancyCategory.UNKNOWN)


def load_extended_safety_profiles() -> list[DrugSafetyProfile]:
    """Load extended drug safety profiles from fixture file.

    Returns:
        List of DrugSafetyProfile objects
    """
    profiles: list[DrugSafetyProfile] = list(DRUG_SAFETY_PROFILES)
    loaded_drugs = set(p.generic_name.lower() for p in profiles)

    if FIXTURE_FILE.exists():
        try:
            with open(FIXTURE_FILE, "r") as f:
                data = json.load(f)

            fixture_profiles = data.get("profiles", [])

            for item in fixture_profiles:
                drug_name = item.get("drug_name", "").lower()

                if not drug_name or drug_name in loaded_drugs:
                    continue

                # Build contraindications
                contraindications = []
                for cond in item.get("contraindications", []):
                    contraindications.append(
                        DrugContraindication(
                            condition=cond,
                            severity=SafetyLevel.CONTRAINDICATED,
                            rationale=f"Contraindicated in patients with {cond}",
                        )
                    )

                # Build dosing guidelines
                dosing_guidelines = []
                if item.get("renal_adjustment"):
                    dosing_guidelines.append(
                        DosingGuideline(
                            population="renal_impairment",
                            adjustment="Dose reduction required",
                            reason="Reduced renal clearance",
                        )
                    )
                if item.get("hepatic_adjustment"):
                    dosing_guidelines.append(
                        DosingGuideline(
                            population="hepatic_impairment",
                            adjustment="Dose reduction required",
                            reason="Reduced hepatic metabolism",
                        )
                    )

                # Build warnings
                black_box_warnings = []
                if item.get("black_box_warning") and item.get("black_box_text"):
                    black_box_warnings.append(item["black_box_text"])

                profile = DrugSafetyProfile(
                    drug_name=item.get("drug_name", "").title(),
                    generic_name=drug_name,
                    drug_class=item.get("drug_class", ""),
                    black_box_warnings=black_box_warnings,
                    contraindications=contraindications,
                    pregnancy_category=_pregnancy_category_from_string(item.get("pregnancy_category", "")),
                    dosing_guidelines=dosing_guidelines,
                    monitoring_parameters=item.get("monitoring_required", []),
                )

                profiles.append(profile)
                loaded_drugs.add(drug_name)

            logger.info(f"Loaded {len(profiles)} drug safety profiles ({len(fixture_profiles)} from fixture)")
        except Exception as e:
            logger.warning(f"Failed to load extended safety profiles from {FIXTURE_FILE}: {e}")
    else:
        logger.warning(f"Drug safety fixture file not found: {FIXTURE_FILE}")

    return profiles


# ============================================================================
# Drug Safety Service
# ============================================================================

# Singleton instance and lock for thread safety
_drug_safety_service: "DrugSafetyService | None" = None
_drug_safety_lock = threading.Lock()


def get_drug_safety_service() -> "DrugSafetyService":
    """Get the singleton drug safety service instance."""
    global _drug_safety_service
    if _drug_safety_service is None:
        with _drug_safety_lock:
            if _drug_safety_service is None:
                _drug_safety_service = DrugSafetyService()
    return _drug_safety_service


def reset_drug_safety_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _drug_safety_service
    with _drug_safety_lock:
        _drug_safety_service = None


class DrugSafetyService:
    """Service for checking drug safety and contraindications.

    Integrates with RxNormService for enhanced drug name normalization
    and therapeutic class identification.
    """

    def __hash__(self) -> int:
        return id(self)

    def __eq__(self, other: object) -> bool:
        return self is other

    def __init__(self, use_rxnorm: bool = True) -> None:
        """Initialize the drug safety service.

        Args:
            use_rxnorm: Whether to use RxNormService for enhanced drug name resolution.
                       Defaults to True. Set to False to disable RxNorm integration.
        """
        self._profiles: dict[str, DrugSafetyProfile] = {}
        self._aliases: dict[str, str] = DRUG_ALIASES
        self._rxnorm_service: "RxNormService | None" = None
        self._use_rxnorm = use_rxnorm

        # Load extended profiles from fixture
        profiles = load_extended_safety_profiles()

        # Index profiles by normalized name
        for profile in profiles:
            self._profiles[profile.generic_name.lower()] = profile

        if use_rxnorm:
            self._init_rxnorm()

        logger.info(f"Drug safety service initialized with {len(self._profiles)} drug profiles")

    def _init_rxnorm(self) -> None:
        """Initialize RxNorm service integration."""
        try:
            from app.services.rxnorm_service import get_rxnorm_service
            self._rxnorm_service = get_rxnorm_service()
            logger.info("RxNorm service integration enabled for drug safety")
        except Exception as e:
            logger.warning(f"Failed to initialize RxNorm service: {e}")
            self._rxnorm_service = None

    def normalize_drug_name(self, drug: str) -> str:
        """Normalize a drug name to its generic form.

        Uses RxNormService if available for enhanced brand-to-generic resolution.
        """
        drug_lower = drug.lower().strip()

        # First check local aliases
        if drug_lower in self._aliases:
            return self._aliases[drug_lower]

        # Try RxNorm service for brand-to-generic resolution
        if self._rxnorm_service:
            try:
                generic = self._rxnorm_service.normalize_to_generic(drug)
                if generic:
                    return generic.lower()
            except Exception as e:
                logger.debug(f"RxNorm lookup failed for {drug}: {e}")

        return drug_lower

    def get_therapeutic_class(self, drug: str) -> list[str]:
        """Get therapeutic class(es) for a drug.

        Uses RxNormService if available for class identification.
        """
        # First check if we have a profile with class info
        profile = self.get_profile(drug)
        if profile and profile.drug_class:
            return [profile.drug_class]

        # Try RxNorm service for therapeutic class
        if self._rxnorm_service:
            try:
                classes = self._rxnorm_service.get_therapeutic_class(drug)
                if classes:
                    return classes
            except Exception as e:
                logger.debug(f"RxNorm class lookup failed for {drug}: {e}")

        return []

    def get_profile(self, drug: str) -> DrugSafetyProfile | None:
        """Get the safety profile for a drug."""
        normalized = self.normalize_drug_name(drug)
        return self._profiles.get(normalized)

    def check_safety(
        self,
        drug: str,
        patient_conditions: list[str] | None = None,
        age: int | None = None,
        pregnant: bool = False,
        lactating: bool = False,
        egfr: float | None = None,
    ) -> SafetyCheckResult:
        """Check drug safety for a patient."""
        conditions_key = tuple(sorted(c.lower() for c in patient_conditions)) if patient_conditions else ()
        return self._check_safety_cached(
            drug, conditions_key, age, pregnant, lactating, egfr,
        )

    @lru_cache(maxsize=256)
    def _check_safety_cached(
        self,
        drug: str,
        conditions_key: tuple[str, ...],
        age: int | None,
        pregnant: bool,
        lactating: bool,
        egfr: float | None,
    ) -> SafetyCheckResult:
        """Cached implementation of check_safety."""
        patient_conditions = list(conditions_key) if conditions_key else None
        profile = self.get_profile(drug)

        contraindicated: list[tuple[str, str]] = []
        warnings: list[str] = []
        cautions: list[str] = []
        dosing_considerations: list[str] = []
        monitoring_needed: list[str] = []
        pregnancy_warning: str | None = None
        lactation_warning: str | None = None

        if profile is None:
            return SafetyCheckResult(
                drug_name=drug,
                patient_conditions=patient_conditions or [],
                overall_safety=SafetyLevel.CAUTION,
                contraindicated_conditions=[],
                warnings=["Drug not found in safety database - review prescribing information"],
                cautions=[],
                dosing_considerations=[],
                monitoring_needed=[],
                pregnancy_warning=None,
                lactation_warning=None,
                profile=None,
            )

        # Add black box warnings
        warnings.extend(profile.black_box_warnings)

        # Check patient conditions against contraindications
        if patient_conditions:
            conditions_lower = [c.lower() for c in patient_conditions]

            for ci in profile.contraindications:
                # Simple matching - in production would use proper term matching
                for cond in conditions_lower:
                    if ci.condition.lower() in cond or cond in ci.condition.lower():
                        if ci.severity == SafetyLevel.CONTRAINDICATED:
                            contraindicated.append((ci.condition, ci.rationale))
                        elif ci.severity == SafetyLevel.WARNING:
                            warnings.append(f"{ci.condition}: {ci.rationale}")
                        elif ci.severity == SafetyLevel.CAUTION:
                            cautions.append(f"{ci.condition}: {ci.rationale}")

        # Pregnancy check
        if pregnant:
            if profile.pregnancy_category in [PregnancyCategory.D, PregnancyCategory.X]:
                pregnancy_warning = f"Pregnancy Category {profile.pregnancy_category.value}: {profile.pregnancy_notes}"
                if profile.pregnancy_category == PregnancyCategory.X:
                    contraindicated.append(("Pregnancy", profile.pregnancy_notes))
                else:
                    warnings.append(f"Pregnancy: {profile.pregnancy_notes}")
            else:
                pregnancy_warning = f"Pregnancy Category {profile.pregnancy_category.value}: {profile.pregnancy_notes}"

        # Lactation check
        if lactating:
            lactation_warning = f"{profile.lactation_safety.value}: {profile.lactation_notes}"
            if profile.lactation_safety == LactationSafety.CONTRAINDICATED:
                contraindicated.append(("Lactation", profile.lactation_notes))
            elif profile.lactation_safety == LactationSafety.POTENTIALLY_HAZARDOUS:
                warnings.append(f"Lactation: {profile.lactation_notes}")

        # Age-based considerations
        if age is not None:
            if age >= 65 and profile.geriatric_notes:
                dosing_considerations.append(f"Geriatric: {profile.geriatric_notes}")

            if age < 18 and profile.pediatric_notes:
                dosing_considerations.append(f"Pediatric: {profile.pediatric_notes}")

        # Renal dosing
        if egfr is not None:
            for guideline in profile.dosing_guidelines:
                if guideline.population == "renal_impairment":
                    if egfr < 60:
                        dosing_considerations.append(f"Renal (eGFR {egfr}): {guideline.adjustment}")
                        break

        # Add monitoring
        monitoring_needed.extend(profile.monitoring_parameters)

        # Determine overall safety level
        overall_safety = SafetyLevel.SAFE
        if cautions:
            overall_safety = SafetyLevel.CAUTION
        if warnings:
            overall_safety = SafetyLevel.WARNING
        if contraindicated:
            overall_safety = SafetyLevel.CONTRAINDICATED

        return SafetyCheckResult(
            drug_name=profile.drug_name,
            patient_conditions=patient_conditions or [],
            overall_safety=overall_safety,
            contraindicated_conditions=contraindicated,
            warnings=warnings,
            cautions=cautions,
            dosing_considerations=dosing_considerations,
            monitoring_needed=monitoring_needed,
            pregnancy_warning=pregnancy_warning,
            lactation_warning=lactation_warning,
            profile=profile,
        )

    def get_all_profiles(self) -> list[DrugSafetyProfile]:
        """Get all drug safety profiles."""
        return list(self._profiles.values())

    def search_profiles(self, query: str, limit: int = 10) -> list[DrugSafetyProfile]:
        """Search for drug profiles by name or class."""
        query_lower = query.lower()
        matches = []

        for profile in self._profiles.values():
            if (
                query_lower in profile.drug_name.lower()
                or query_lower in profile.generic_name.lower()
                or query_lower in profile.drug_class.lower()
            ):
                matches.append(profile)

        return matches[:limit]

    def get_stats(self) -> dict:
        """Get statistics about the drug safety database."""
        profiles = list(self._profiles.values())

        by_class: dict[str, int] = {}
        with_bbw = 0
        category_d_x = 0

        for p in profiles:
            by_class[p.drug_class] = by_class.get(p.drug_class, 0) + 1
            if p.black_box_warnings:
                with_bbw += 1
            if p.pregnancy_category in [PregnancyCategory.D, PregnancyCategory.X]:
                category_d_x += 1

        return {
            "total_drugs": len(profiles),
            "total_aliases": len(self._aliases),
            "by_class": by_class,
            "with_black_box_warnings": with_bbw,
            "pregnancy_category_d_or_x": category_d_x,
        }

    def check_interactions(self, drugs: list[str]) -> InteractionCheckResult:
        """Check for known drug-drug interactions among a list of medications."""
        normalized = tuple(sorted(self.normalize_drug_name(d) for d in drugs))
        return self._check_interactions_cached(normalized)

    @lru_cache(maxsize=256)
    def _check_interactions_cached(self, normalized_drugs: tuple[str, ...]) -> InteractionCheckResult:
        """Cached implementation of check_interactions.

        P1-013: Returns coverage_status indicating whether the checked drug
        pairs are in the interaction database.  When DRUG_SAFETY_STRICT_MODE
        is set, uncovered pairs produce an explicit warning.
        """
        normalized = list(normalized_drugs)
        # Check against normalized names for matching
        all_names = [n.lower() for n in normalized]
        found: list[DrugInteraction] = []

        for interaction_data in KNOWN_INTERACTIONS:
            drug_a, drug_b = interaction_data["drugs"]
            # Check if both drugs in the interaction are in the patient's list
            a_match = any(drug_a in name for name in all_names)
            b_match = any(drug_b in name for name in all_names)
            if a_match and b_match:
                found.append(DrugInteraction(
                    drug_a=drug_a,
                    drug_b=drug_b,
                    severity=interaction_data["severity"],
                    description=interaction_data["description"],
                    mechanism=interaction_data["mechanism"],
                    clinical_effect=interaction_data["clinical_effect"],
                    management=interaction_data["management"],
                ))

        # P1-013: Determine coverage status
        coverage_status, coverage_warning = self._compute_coverage(normalized, found)

        return InteractionCheckResult(
            drugs_checked=normalized,
            interactions_found=found,
            total_interactions=len(found),
            coverage_status=coverage_status,
            drug_coverage_warning=coverage_warning,
        )

    # ------------------------------------------------------------------
    # P1-013 helpers
    # ------------------------------------------------------------------

    def _compute_coverage(
        self,
        normalized_drugs: list[str],
        found_interactions: list[DrugInteraction],
    ) -> tuple[str, str | None]:
        """Determine coverage status and optional warning for a drug list.

        A drug is considered "known" if it appears in either the safety
        profiles database or the interaction database.

        Returns:
            (coverage_status, warning_message | None)
        """
        # Build set of all drugs the system knows about
        known_set = {name.lower() for name in self._profiles}
        for entry in KNOWN_INTERACTIONS:
            for drug_name in entry["drugs"]:
                known_set.add(drug_name.lower())
        # Also include aliases
        for alias, generic in self._aliases.items():
            known_set.add(alias.lower())
            known_set.add(generic.lower())

        checked = {d.lower() for d in normalized_drugs}

        known_count = len(checked & known_set)
        unknown_drugs = checked - known_set

        if not checked:
            return "covered", None

        if known_count == len(checked):
            status = "covered"
        elif known_count > 0:
            status = "partially_covered"
        else:
            status = "uncovered"

        # Build warning
        warning: str | None = None
        strict = os.environ.get("DRUG_SAFETY_STRICT_MODE", "").lower() in (
            "1", "true", "yes",
        )

        if unknown_drugs:
            drug_list = ", ".join(sorted(unknown_drugs))
            warning = (
                f"The following drugs are not in the interaction database and "
                f"their interactions could not be checked: {drug_list}. "
                f"Consult clinical references for complete information."
            )
            if strict:
                warning = f"[STRICT MODE] {warning}"

        return status, warning

    def get_coverage_report(self) -> DrugCoverageReport:
        """Return a summary of drug safety database coverage.

        P1-013: Provides total_drugs_known, total_interactions, and
        coverage_percent (ratio of drugs with at least one profile).
        """
        known_drugs = sorted(self._profiles.keys())

        # Collect unique drugs mentioned in the interaction database
        interaction_drug_set: set[str] = set()
        for entry in KNOWN_INTERACTIONS:
            interaction_drug_set.update(entry["drugs"])

        # coverage_percent = drugs in profiles that also appear in interactions
        if interaction_drug_set:
            covered = len(interaction_drug_set & set(self._profiles.keys()))
            coverage_pct = round((covered / len(interaction_drug_set)) * 100, 1)
        else:
            coverage_pct = 0.0

        return DrugCoverageReport(
            total_drugs_known=len(known_drugs),
            total_interactions=len(KNOWN_INTERACTIONS),
            coverage_percent=coverage_pct,
            known_drug_names=known_drugs,
        )
