"""Comprehensive Clinical Calculator Service.

Provides validated clinical calculators for:
- Cardiovascular Risk (ASCVD, Framingham, HEART, CHA2DS2-VASc, HAS-BLED)
- Renal Function (CKD-EPI 2021 eGFR, Cockcroft-Gault, UACR)
- Hepatic Function (MELD, Child-Pugh, FIB-4)
- Critical Care (APACHE II, SOFA, qSOFA, Wells PE/DVT)
- Other (BMI, BSA, Corrected Calcium, Anion Gap)

Each calculator includes:
- Input validation with Pydantic schemas
- Formula implementation with citations
- Risk interpretation and categorization
- Reference ranges and recommendations
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from threading import Lock
from typing import Any

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Base Classes
# =============================================================================

class RiskLevel(str, Enum):
    """Risk stratification levels."""
    LOW = "low"
    LOW_MODERATE = "low_moderate"
    MODERATE = "moderate"
    MODERATE_HIGH = "moderate_high"
    HIGH = "high"
    VERY_HIGH = "very_high"


class CalculatorCategory(str, Enum):
    """Calculator categories."""
    CARDIOVASCULAR = "cardiovascular"
    RENAL = "renal"
    HEPATIC = "hepatic"
    CRITICAL_CARE = "critical_care"
    GENERAL = "general"
    LABORATORY = "laboratory"


@dataclass
class CalculatorResult:
    """Result from a clinical calculator."""
    calculator_id: str
    calculator_name: str
    score: float
    score_unit: str
    risk_level: RiskLevel
    interpretation: str
    recommendations: list[str]
    components: dict[str, Any] = field(default_factory=dict)
    references: list[str] = field(default_factory=list)
    formula_used: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass
class CalculatorDefinition:
    """Definition of a clinical calculator."""
    id: str
    name: str
    short_name: str
    description: str
    category: CalculatorCategory
    version: str
    formula_description: str
    inputs: list[dict[str, Any]]
    output_unit: str
    references: list[str]
    notes: list[str] = field(default_factory=list)


# =============================================================================
# Input Schemas (Pydantic)
# =============================================================================

class BMIInput(BaseModel):
    """Input for BMI calculator."""
    weight_kg: float = Field(..., gt=0, le=500, description="Weight in kilograms")
    height_cm: float = Field(..., gt=50, le=300, description="Height in centimeters")


class BSAInput(BaseModel):
    """Input for Body Surface Area calculator."""
    weight_kg: float = Field(..., gt=0, le=500, description="Weight in kilograms")
    height_cm: float = Field(..., gt=50, le=300, description="Height in centimeters")


class ASCVDInput(BaseModel):
    """Input for ASCVD 10-year risk calculator (Pooled Cohort Equations)."""
    age: int = Field(..., ge=40, le=79, description="Age in years (40-79)")
    sex: str = Field(..., pattern="^(male|female)$", description="Sex (male/female)")
    race: str = Field(..., pattern="^(white|african_american|other)$", description="Race")
    total_cholesterol: float = Field(..., ge=130, le=320, description="Total cholesterol mg/dL")
    hdl_cholesterol: float = Field(..., ge=20, le=100, description="HDL cholesterol mg/dL")
    systolic_bp: float = Field(..., ge=90, le=200, description="Systolic BP mmHg")
    bp_treated: bool = Field(default=False, description="On BP medication")
    diabetes: bool = Field(default=False, description="Has diabetes")
    smoker: bool = Field(default=False, description="Current smoker")


class FraminghamInput(BaseModel):
    """Input for Framingham Risk Score."""
    age: int = Field(..., ge=30, le=79, description="Age in years")
    sex: str = Field(..., pattern="^(male|female)$", description="Sex")
    total_cholesterol: float = Field(..., ge=100, le=400, description="Total cholesterol mg/dL")
    hdl_cholesterol: float = Field(..., ge=20, le=150, description="HDL cholesterol mg/dL")
    systolic_bp: float = Field(..., ge=80, le=200, description="Systolic BP mmHg")
    bp_treated: bool = Field(default=False, description="On BP medication")
    smoker: bool = Field(default=False, description="Current smoker")
    diabetic: bool = Field(default=False, description="Has diabetes")


class HEARTInput(BaseModel):
    """Input for HEART Score (chest pain evaluation)."""
    age: int = Field(..., ge=18, le=120, description="Age in years")
    history: str = Field(..., pattern="^(highly_suspicious|moderately_suspicious|slightly_suspicious)$")
    ecg: str = Field(..., pattern="^(significant_st_depression|nonspecific_repolarization|normal)$")
    troponin: str = Field(..., pattern="^(greater_than_3x|1_to_3x|normal)$")
    risk_factors: int = Field(..., ge=0, le=7, description="Number of risk factors (0-7)")


class CHA2DS2VAScInput(BaseModel):
    """Input for CHA2DS2-VASc Score."""
    age: int = Field(..., ge=18, le=120, description="Age in years")
    sex: str = Field(..., pattern="^(male|female)$", description="Sex")
    chf: bool = Field(default=False, description="Congestive heart failure")
    hypertension: bool = Field(default=False, description="Hypertension")
    diabetes: bool = Field(default=False, description="Diabetes mellitus")
    stroke_tia: bool = Field(default=False, description="Prior stroke/TIA/thromboembolism")
    vascular_disease: bool = Field(default=False, description="Vascular disease (MI, PAD, aortic plaque)")


class HASBLEDInput(BaseModel):
    """Input for HAS-BLED Score."""
    hypertension: bool = Field(default=False, description="Uncontrolled SBP >160 mmHg")
    renal_disease: bool = Field(default=False, description="Dialysis, transplant, Cr >2.6 mg/dL")
    liver_disease: bool = Field(default=False, description="Cirrhosis or bilirubin >2x + ALT/AST >3x")
    stroke_history: bool = Field(default=False, description="Prior stroke")
    bleeding_history: bool = Field(default=False, description="Prior major bleeding")
    labile_inr: bool = Field(default=False, description="Unstable INRs or <60% TTR")
    age_over_65: bool = Field(default=False, description="Age >65 years")
    antiplatelet_nsaid: bool = Field(default=False, description="Antiplatelet or NSAID use")
    alcohol_use: bool = Field(default=False, description=">=8 drinks/week")


class EGFRInput(BaseModel):
    """Input for CKD-EPI 2021 eGFR calculator."""
    creatinine: float = Field(..., gt=0, le=30, description="Serum creatinine mg/dL")
    age: int = Field(..., ge=18, le=120, description="Age in years")
    sex: str = Field(..., pattern="^(male|female)$", description="Sex")


class CockcroftGaultInput(BaseModel):
    """Input for Cockcroft-Gault creatinine clearance."""
    creatinine: float = Field(..., gt=0, le=30, description="Serum creatinine mg/dL")
    age: int = Field(..., ge=18, le=120, description="Age in years")
    weight_kg: float = Field(..., gt=0, le=500, description="Weight in kg")
    sex: str = Field(..., pattern="^(male|female)$", description="Sex")


class UACRInput(BaseModel):
    """Input for UACR interpretation."""
    uacr: float = Field(..., ge=0, description="Urine albumin-to-creatinine ratio mg/g")


class MELDInput(BaseModel):
    """Input for MELD/MELD-Na Score."""
    creatinine: float = Field(..., ge=0.1, le=15, description="Serum creatinine mg/dL")
    bilirubin: float = Field(..., ge=0.1, le=50, description="Total bilirubin mg/dL")
    inr: float = Field(..., ge=0.5, le=15, description="INR")
    sodium: float | None = Field(None, ge=100, le=160, description="Serum sodium mEq/L (for MELD-Na)")
    on_dialysis: bool = Field(default=False, description="On dialysis (sets Cr to 4)")


class ChildPughInput(BaseModel):
    """Input for Child-Pugh Score."""
    bilirubin: float = Field(..., ge=0.1, le=50, description="Total bilirubin mg/dL")
    albumin: float = Field(..., ge=1, le=6, description="Serum albumin g/dL")
    inr: float = Field(..., ge=0.5, le=10, description="INR")
    ascites: str = Field(..., pattern="^(none|mild|moderate_severe)$", description="Ascites severity")
    encephalopathy: str = Field(..., pattern="^(none|grade_1_2|grade_3_4)$", description="Encephalopathy grade")


class FIB4Input(BaseModel):
    """Input for FIB-4 Score."""
    age: int = Field(..., ge=18, le=120, description="Age in years")
    ast: float = Field(..., gt=0, le=2000, description="AST U/L")
    alt: float = Field(..., gt=0, le=2000, description="ALT U/L")
    platelets: float = Field(..., gt=0, le=1000, description="Platelet count (10^9/L)")


class APACHEIIInput(BaseModel):
    """Input for APACHE II Score."""
    age: int = Field(..., ge=0, le=120, description="Age in years")
    temperature: float = Field(..., ge=25, le=45, description="Core temperature C")
    map: float = Field(..., ge=0, le=300, description="Mean arterial pressure mmHg")
    heart_rate: float = Field(..., ge=0, le=300, description="Heart rate bpm")
    respiratory_rate: float = Field(..., ge=0, le=80, description="Respiratory rate /min")
    fio2: float = Field(..., ge=0.21, le=1.0, description="FiO2")
    pao2: float | None = Field(None, ge=0, le=700, description="PaO2 mmHg (if FiO2 >= 0.5)")
    aa_gradient: float | None = Field(None, ge=0, le=700, description="A-a gradient (if FiO2 >= 0.5)")
    ph: float = Field(..., ge=6.5, le=8.0, description="Arterial pH")
    sodium: float = Field(..., ge=100, le=200, description="Serum sodium mEq/L")
    potassium: float = Field(..., ge=1, le=10, description="Serum potassium mEq/L")
    creatinine: float = Field(..., ge=0.1, le=20, description="Serum creatinine mg/dL")
    hematocrit: float = Field(..., ge=10, le=70, description="Hematocrit %")
    wbc: float = Field(..., ge=0, le=100, description="WBC count (10^3/uL)")
    gcs: int = Field(..., ge=3, le=15, description="Glasgow Coma Scale")
    chronic_health: str = Field(default="none", description="Chronic health status")
    acute_renal_failure: bool = Field(default=False, description="Acute renal failure")


class SOFAInput(BaseModel):
    """Input for SOFA Score."""
    pao2_fio2: float = Field(..., ge=0, le=700, description="PaO2/FiO2 ratio")
    on_ventilator: bool = Field(default=False, description="On mechanical ventilation")
    platelets: float = Field(..., ge=0, le=1000, description="Platelet count (10^3/uL)")
    bilirubin: float = Field(..., ge=0, le=50, description="Total bilirubin mg/dL")
    map: float = Field(..., ge=0, le=300, description="Mean arterial pressure mmHg")
    vasopressor: str = Field(default="none", description="Vasopressor use")
    gcs: int = Field(..., ge=3, le=15, description="Glasgow Coma Scale")
    creatinine: float = Field(..., ge=0, le=20, description="Creatinine mg/dL")
    urine_output: float | None = Field(None, ge=0, description="24h urine output mL")


class QSOFAInput(BaseModel):
    """Input for qSOFA Score."""
    respiratory_rate: float = Field(..., ge=0, le=80, description="Respiratory rate /min")
    systolic_bp: float = Field(..., ge=0, le=300, description="Systolic BP mmHg")
    altered_mental_status: bool = Field(default=False, description="Altered mental status (GCS <15)")


class WellsPEInput(BaseModel):
    """Input for Wells Score for Pulmonary Embolism."""
    clinical_dvt: bool = Field(default=False, description="Clinical signs of DVT")
    pe_most_likely: bool = Field(default=False, description="PE most likely diagnosis")
    heart_rate_over_100: bool = Field(default=False, description="Heart rate >100 bpm")
    immobilization_surgery: bool = Field(default=False, description="Immobilization or surgery in past 4 weeks")
    previous_pe_dvt: bool = Field(default=False, description="Previous PE or DVT")
    hemoptysis: bool = Field(default=False, description="Hemoptysis")
    malignancy: bool = Field(default=False, description="Malignancy (treatment within 6 months)")


class WellsDVTInput(BaseModel):
    """Input for Wells Score for DVT."""
    active_cancer: bool = Field(default=False, description="Active cancer")
    paralysis_immobilization: bool = Field(default=False, description="Paralysis or immobilization")
    bedridden_surgery: bool = Field(default=False, description="Bedridden >3 days or surgery <12 weeks")
    localized_tenderness: bool = Field(default=False, description="Localized tenderness along deep veins")
    entire_leg_swollen: bool = Field(default=False, description="Entire leg swollen")
    calf_swelling_3cm: bool = Field(default=False, description="Calf swelling >3cm vs other leg")
    pitting_edema: bool = Field(default=False, description="Pitting edema (symptomatic leg)")
    collateral_veins: bool = Field(default=False, description="Collateral superficial veins")
    previous_dvt: bool = Field(default=False, description="Previous DVT")
    alternative_diagnosis_likely: bool = Field(default=False, description="Alternative diagnosis likely")


class CorrectedCalciumInput(BaseModel):
    """Input for Corrected Calcium calculator."""
    calcium: float = Field(..., ge=4, le=20, description="Total calcium mg/dL")
    albumin: float = Field(..., ge=0.5, le=6, description="Serum albumin g/dL")


class AnionGapInput(BaseModel):
    """Input for Anion Gap calculator."""
    sodium: float = Field(..., ge=100, le=180, description="Sodium mEq/L")
    chloride: float = Field(..., ge=70, le=130, description="Chloride mEq/L")
    bicarbonate: float = Field(..., ge=5, le=50, description="Bicarbonate mEq/L")
    albumin: float | None = Field(None, ge=0.5, le=6, description="Albumin g/dL (for correction)")


class GCSInput(BaseModel):
    """Input for Glasgow Coma Scale."""
    eye_response: int = Field(..., ge=1, le=4, description="Eye response (1-4)")
    verbal_response: int = Field(..., ge=1, le=5, description="Verbal response (1-5)")
    motor_response: int = Field(..., ge=1, le=6, description="Motor response (1-6)")


class NEWS2Input(BaseModel):
    """Input for NEWS2 (National Early Warning Score 2)."""
    respiratory_rate: int = Field(..., ge=0, le=60, description="Respiratory rate /min")
    spo2: float = Field(..., ge=50, le=100, description="Oxygen saturation %")
    supplemental_o2: bool = Field(default=False, description="On supplemental oxygen")
    temperature: float = Field(..., ge=30, le=42, description="Temperature °C")
    systolic_bp: int = Field(..., ge=50, le=250, description="Systolic BP mmHg")
    heart_rate: int = Field(..., ge=20, le=250, description="Heart rate bpm")
    consciousness: str = Field(default="alert", description="AVPU: alert, verbal, pain, unresponsive, or confusion")
    copd_scale_2: bool = Field(default=False, description="Use Scale 2 for COPD (target SpO2 88-92%)")


class CURB65Input(BaseModel):
    """Input for CURB-65 pneumonia severity score."""
    confusion: bool = Field(default=False, description="New mental confusion")
    bun_over_19: bool = Field(default=False, description="BUN >19 mg/dL (or urea >7 mmol/L)")
    respiratory_rate_over_30: bool = Field(default=False, description="Respiratory rate ≥30/min")
    low_bp: bool = Field(default=False, description="SBP <90 or DBP ≤60 mmHg")
    age_65_or_older: bool = Field(default=False, description="Age ≥65 years")


class PERCInput(BaseModel):
    """Input for PERC Rule (PE rule-out criteria)."""
    age_under_50: bool = Field(default=True, description="Age <50 years")
    heart_rate_under_100: bool = Field(default=True, description="Heart rate <100 bpm")
    spo2_over_94: bool = Field(default=True, description="SpO2 >94% on room air")
    no_leg_swelling: bool = Field(default=True, description="No unilateral leg swelling")
    no_hemoptysis: bool = Field(default=True, description="No hemoptysis")
    no_recent_surgery: bool = Field(default=True, description="No surgery/trauma in past 4 weeks")
    no_prior_pe_dvt: bool = Field(default=True, description="No prior PE or DVT")
    no_hormone_use: bool = Field(default=True, description="No exogenous estrogen")


class TIMIInput(BaseModel):
    """Input for TIMI Risk Score (UA/NSTEMI)."""
    age_65_or_older: bool = Field(default=False, description="Age ≥65 years")
    cad_risk_factors_3_plus: bool = Field(default=False, description="≥3 CAD risk factors")
    known_cad: bool = Field(default=False, description="Known CAD ≥50% stenosis")
    aspirin_use_7_days: bool = Field(default=False, description="Aspirin use in past 7 days")
    severe_angina_24h: bool = Field(default=False, description="≥2 anginal episodes in past 24h")
    st_deviation: bool = Field(default=False, description="ST deviation ≥0.5mm")
    elevated_troponin: bool = Field(default=False, description="Elevated cardiac markers")


class SIRSInput(BaseModel):
    """Input for SIRS Criteria."""
    temperature: float = Field(..., ge=30, le=44, description="Temperature °C")
    heart_rate: int = Field(..., ge=20, le=250, description="Heart rate bpm")
    respiratory_rate: int = Field(..., ge=0, le=60, description="Respiratory rate /min")
    paco2: float | None = Field(None, ge=10, le=100, description="PaCO2 mmHg (optional)")
    wbc: float | None = Field(None, ge=0, le=100, description="WBC 10^3/µL (optional)")
    bands: float | None = Field(None, ge=0, le=100, description="Band percentage (optional)")


class ABCD2Input(BaseModel):
    """Input for ABCD2 Score (TIA stroke risk)."""
    age_60_or_older: bool = Field(default=False, description="Age ≥60 years")
    bp_140_90_or_higher: bool = Field(default=False, description="SBP ≥140 or DBP ≥90 mmHg")
    clinical_weakness: bool = Field(default=False, description="Unilateral weakness")
    clinical_speech_only: bool = Field(default=False, description="Speech impairment without weakness")
    duration_60_plus_min: bool = Field(default=False, description="Symptoms ≥60 minutes")
    duration_10_59_min: bool = Field(default=False, description="Symptoms 10-59 minutes")
    diabetes: bool = Field(default=False, description="History of diabetes")


class CentorInput(BaseModel):
    """Input for Modified Centor Score (strep pharyngitis)."""
    tonsillar_exudates: bool = Field(default=False, description="Tonsillar exudates")
    tender_nodes: bool = Field(default=False, description="Tender anterior cervical adenopathy")
    fever: bool = Field(default=False, description="History of fever >38°C")
    no_cough: bool = Field(default=False, description="Absence of cough")
    age_3_14: bool = Field(default=False, description="Age 3-14 years")
    age_15_44: bool = Field(default=False, description="Age 15-44 years")
    age_45_plus: bool = Field(default=False, description="Age ≥45 years")


class MAPInput(BaseModel):
    """Input for Mean Arterial Pressure calculator."""
    systolic_bp: float = Field(..., ge=40, le=300, description="Systolic BP mmHg")
    diastolic_bp: float = Field(..., ge=20, le=200, description="Diastolic BP mmHg")


class CorrectedSodiumInput(BaseModel):
    """Input for Corrected Sodium calculator."""
    measured_sodium: float = Field(..., ge=100, le=180, description="Measured sodium mEq/L")
    glucose: float = Field(..., ge=50, le=2000, description="Glucose mg/dL")


class OsmolalityInput(BaseModel):
    """Input for Serum Osmolality calculator."""
    sodium: float = Field(..., ge=100, le=180, description="Sodium mEq/L")
    glucose: float = Field(..., ge=0, le=2000, description="Glucose mg/dL")
    bun: float = Field(..., ge=0, le=200, description="BUN mg/dL")
    measured_osmolality: float | None = Field(None, ge=200, le=500, description="Measured osmolality mOsm/kg")


class BISAPInput(BaseModel):
    """Input for BISAP Score (acute pancreatitis)."""
    bun_over_25: bool = Field(default=False, description="BUN >25 mg/dL")
    impaired_mental_status: bool = Field(default=False, description="Impaired mental status")
    sirs_2_or_more: bool = Field(default=False, description="≥2 SIRS criteria")
    age_over_60: bool = Field(default=False, description="Age >60 years")
    pleural_effusion: bool = Field(default=False, description="Pleural effusion on imaging")


# =============================================================================
# Calculator Implementations
# =============================================================================

def calculate_bmi(input_data: BMIInput) -> CalculatorResult:
    """Calculate Body Mass Index.

    Formula: BMI = weight(kg) / height(m)^2
    Reference: WHO BMI Classification
    """
    height_m = input_data.height_cm / 100
    bmi = input_data.weight_kg / (height_m ** 2)

    if bmi < 16:
        risk = RiskLevel.VERY_HIGH
        interpretation = "Severe Thinness"
        recommendations = ["Urgent nutritional assessment", "Evaluate for eating disorders", "Medical evaluation for underlying causes"]
    elif bmi < 17:
        risk = RiskLevel.HIGH
        interpretation = "Moderate Thinness"
        recommendations = ["Nutritional counseling", "Medical evaluation", "Monitor weight closely"]
    elif bmi < 18.5:
        risk = RiskLevel.MODERATE
        interpretation = "Mild Thinness (Underweight)"
        recommendations = ["Dietary assessment", "Consider nutritional supplementation"]
    elif bmi < 25:
        risk = RiskLevel.LOW
        interpretation = "Normal Weight"
        recommendations = ["Maintain healthy lifestyle", "Regular physical activity"]
    elif bmi < 30:
        risk = RiskLevel.MODERATE
        interpretation = "Overweight (Pre-obese)"
        recommendations = ["Lifestyle modifications", "Diet and exercise counseling", "Screen for metabolic syndrome"]
    elif bmi < 35:
        risk = RiskLevel.HIGH
        interpretation = "Obese Class I"
        recommendations = ["Intensive lifestyle intervention", "Screen for comorbidities", "Consider pharmacotherapy"]
    elif bmi < 40:
        risk = RiskLevel.HIGH
        interpretation = "Obese Class II"
        recommendations = ["Intensive lifestyle intervention", "Pharmacotherapy consideration", "Evaluate for bariatric surgery"]
    else:
        risk = RiskLevel.VERY_HIGH
        interpretation = "Obese Class III (Morbid Obesity)"
        recommendations = ["Bariatric surgery evaluation", "Multidisciplinary management", "Aggressive comorbidity treatment"]

    return CalculatorResult(
        calculator_id="bmi",
        calculator_name="Body Mass Index (BMI)",
        score=round(bmi, 1),
        score_unit="kg/m2",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components={"weight_kg": input_data.weight_kg, "height_cm": input_data.height_cm, "height_m": height_m},
        references=["WHO BMI Classification", "NIH Clinical Guidelines on Obesity"],
        formula_used="BMI = weight(kg) / height(m)^2"
    )


def calculate_bsa(input_data: BSAInput) -> CalculatorResult:
    """Calculate Body Surface Area using Du Bois formula.

    Formula: BSA = 0.007184 x height(cm)^0.725 x weight(kg)^0.425
    Reference: Du Bois D, Du Bois EF. Arch Intern Med 1916
    """
    bsa = 0.007184 * (input_data.height_cm ** 0.725) * (input_data.weight_kg ** 0.425)

    if bsa < 1.5:
        risk = RiskLevel.LOW_MODERATE
        interpretation = "Below average BSA"
    elif bsa <= 2.0:
        risk = RiskLevel.LOW
        interpretation = "Normal BSA range"
    else:
        risk = RiskLevel.LOW_MODERATE
        interpretation = "Above average BSA"

    return CalculatorResult(
        calculator_id="bsa",
        calculator_name="Body Surface Area (BSA)",
        score=round(bsa, 2),
        score_unit="m2",
        risk_level=risk,
        interpretation=f"{interpretation}. Average adult BSA is ~1.7 m2",
        recommendations=["Use for chemotherapy dosing", "Use for cardiac index calculations", "Use for renal function indexing"],
        components={"weight_kg": input_data.weight_kg, "height_cm": input_data.height_cm},
        references=["Du Bois D, Du Bois EF. Arch Intern Med 1916;17:863-871"],
        formula_used="BSA = 0.007184 x height(cm)^0.725 x weight(kg)^0.425"
    )


def calculate_ascvd(input_data: ASCVDInput) -> CalculatorResult:
    """Calculate 10-year ASCVD risk using Pooled Cohort Equations.

    Reference: 2013 ACC/AHA Guideline on Cardiovascular Risk Assessment
    """
    # Pooled Cohort Equations coefficients
    ln_age = math.log(input_data.age)
    ln_tc = math.log(input_data.total_cholesterol)
    ln_hdl = math.log(input_data.hdl_cholesterol)
    ln_sbp = math.log(input_data.systolic_bp)

    if input_data.sex == "female":
        if input_data.race == "african_american":
            # African American Female
            s0_10 = 0.9533
            mean_coef = 86.61
            terms = (
                17.1141 * ln_age +
                0.9396 * ln_tc +
                (-18.9196) * ln_hdl +
                4.4748 * ln_age * ln_hdl +
                29.2907 * ln_sbp * (1 if input_data.bp_treated else 0) +
                (-6.4321) * ln_age * ln_sbp * (1 if input_data.bp_treated else 0) +
                27.8197 * ln_sbp * (0 if input_data.bp_treated else 1) +
                (-6.0873) * ln_age * ln_sbp * (0 if input_data.bp_treated else 1) +
                0.6908 * (1 if input_data.smoker else 0) +
                0.8738 * (1 if input_data.diabetes else 0)
            )
        else:
            # White/Other Female
            s0_10 = 0.9665
            mean_coef = -29.18
            terms = (
                (-29.799) * ln_age +
                4.884 * ln_age ** 2 +
                13.54 * ln_tc +
                (-3.114) * ln_age * ln_tc +
                (-13.578) * ln_hdl +
                3.149 * ln_age * ln_hdl +
                2.019 * ln_sbp * (1 if input_data.bp_treated else 0) +
                1.957 * ln_sbp * (0 if input_data.bp_treated else 1) +
                7.574 * (1 if input_data.smoker else 0) +
                (-1.665) * ln_age * (1 if input_data.smoker else 0) +
                0.661 * (1 if input_data.diabetes else 0)
            )
    else:
        if input_data.race == "african_american":
            # African American Male
            s0_10 = 0.8954
            mean_coef = 19.54
            terms = (
                2.469 * ln_age +
                0.302 * ln_tc +
                (-0.307) * ln_hdl +
                1.916 * ln_sbp * (1 if input_data.bp_treated else 0) +
                1.809 * ln_sbp * (0 if input_data.bp_treated else 1) +
                0.549 * (1 if input_data.smoker else 0) +
                0.645 * (1 if input_data.diabetes else 0)
            )
        else:
            # White/Other Male
            s0_10 = 0.9144
            mean_coef = 61.18
            terms = (
                12.344 * ln_age +
                11.853 * ln_tc +
                (-2.664) * ln_age * ln_tc +
                (-7.99) * ln_hdl +
                1.769 * ln_age * ln_hdl +
                1.797 * ln_sbp * (1 if input_data.bp_treated else 0) +
                1.764 * ln_sbp * (0 if input_data.bp_treated else 1) +
                7.837 * (1 if input_data.smoker else 0) +
                (-1.795) * ln_age * (1 if input_data.smoker else 0) +
                0.658 * (1 if input_data.diabetes else 0)
            )

    risk_10yr = 1 - s0_10 ** math.exp(terms - mean_coef)
    risk_pct = risk_10yr * 100

    if risk_pct < 5:
        risk = RiskLevel.LOW
        interpretation = f"Low 10-year ASCVD risk ({risk_pct:.1f}%)"
        recommendations = ["Lifestyle counseling", "Reassess in 4-6 years"]
    elif risk_pct < 7.5:
        risk = RiskLevel.LOW_MODERATE
        interpretation = f"Borderline 10-year ASCVD risk ({risk_pct:.1f}%)"
        recommendations = ["Lifestyle modifications", "Consider risk-enhancing factors", "Shared decision-making for statin"]
    elif risk_pct < 20:
        risk = RiskLevel.MODERATE
        interpretation = f"Intermediate 10-year ASCVD risk ({risk_pct:.1f}%)"
        recommendations = ["Moderate-intensity statin if risk-enhancing factors", "Consider CAC scoring for decision", "Aggressive lifestyle modification"]
    else:
        risk = RiskLevel.HIGH
        interpretation = f"High 10-year ASCVD risk ({risk_pct:.1f}%)"
        recommendations = ["High-intensity statin recommended", "Target LDL <70 mg/dL", "Aspirin if benefit > bleeding risk", "Aggressive risk factor control"]

    return CalculatorResult(
        calculator_id="ascvd",
        calculator_name="ASCVD 10-Year Risk (Pooled Cohort Equations)",
        score=round(risk_pct, 1),
        score_unit="%",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components={
            "age": input_data.age,
            "sex": input_data.sex,
            "race": input_data.race,
            "total_cholesterol": input_data.total_cholesterol,
            "hdl_cholesterol": input_data.hdl_cholesterol,
            "systolic_bp": input_data.systolic_bp,
            "bp_treated": input_data.bp_treated,
            "diabetes": input_data.diabetes,
            "smoker": input_data.smoker
        },
        references=["2013 ACC/AHA Guideline on Cardiovascular Risk Assessment", "2018 ACC/AHA Cholesterol Guideline"],
        formula_used="Pooled Cohort Equations (2013)"
    )


def calculate_heart_score(input_data: HEARTInput) -> CalculatorResult:
    """Calculate HEART Score for chest pain evaluation.

    Reference: Six AJ, et al. Neth Heart J 2008
    """
    score = 0
    components = {}

    # History
    if input_data.history == "highly_suspicious":
        score += 2
        components["history"] = 2
    elif input_data.history == "moderately_suspicious":
        score += 1
        components["history"] = 1
    else:
        components["history"] = 0

    # ECG
    if input_data.ecg == "significant_st_depression":
        score += 2
        components["ecg"] = 2
    elif input_data.ecg == "nonspecific_repolarization":
        score += 1
        components["ecg"] = 1
    else:
        components["ecg"] = 0

    # Age
    if input_data.age >= 65:
        score += 2
        components["age"] = 2
    elif input_data.age >= 45:
        score += 1
        components["age"] = 1
    else:
        components["age"] = 0

    # Risk factors
    if input_data.risk_factors >= 3:
        score += 2
        components["risk_factors"] = 2
    elif input_data.risk_factors >= 1:
        score += 1
        components["risk_factors"] = 1
    else:
        components["risk_factors"] = 0

    # Troponin
    if input_data.troponin == "greater_than_3x":
        score += 2
        components["troponin"] = 2
    elif input_data.troponin == "1_to_3x":
        score += 1
        components["troponin"] = 1
    else:
        components["troponin"] = 0

    if score <= 3:
        risk = RiskLevel.LOW
        interpretation = f"HEART Score {score}: Low risk (~1.7% MACE)"
        recommendations = ["Consider early discharge", "Outpatient follow-up", "Risk factor modification"]
    elif score <= 6:
        risk = RiskLevel.MODERATE
        interpretation = f"HEART Score {score}: Intermediate risk (~12% MACE)"
        recommendations = ["Admit for observation", "Serial troponins", "Consider stress testing or coronary CTA"]
    else:
        risk = RiskLevel.HIGH
        interpretation = f"HEART Score {score}: High risk (~50% MACE)"
        recommendations = ["Urgent cardiology consultation", "Consider early invasive strategy", "Antiplatelet therapy", "Heparin anticoagulation"]

    return CalculatorResult(
        calculator_id="heart",
        calculator_name="HEART Score",
        score=score,
        score_unit="points",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Six AJ, et al. Neth Heart J 2008;16:191-196", "Backus BE, et al. Int J Cardiol 2013;168:2153-2158"],
        formula_used="H(istory) + E(CG) + A(ge) + R(isk factors) + T(roponin)"
    )


def calculate_cha2ds2_vasc(input_data: CHA2DS2VAScInput) -> CalculatorResult:
    """Calculate CHA2DS2-VASc Score for stroke risk in atrial fibrillation.

    Reference: 2019 AHA/ACC/HRS AF Guidelines
    """
    score = 0
    components = {}

    if input_data.chf:
        score += 1
        components["CHF"] = 1
    if input_data.hypertension:
        score += 1
        components["Hypertension"] = 1
    if input_data.age >= 75:
        score += 2
        components["Age >=75"] = 2
    elif input_data.age >= 65:
        score += 1
        components["Age 65-74"] = 1
    if input_data.diabetes:
        score += 1
        components["Diabetes"] = 1
    if input_data.stroke_tia:
        score += 2
        components["Stroke/TIA"] = 2
    if input_data.vascular_disease:
        score += 1
        components["Vascular disease"] = 1
    if input_data.sex == "female":
        score += 1
        components["Female sex"] = 1

    # Annual stroke rates
    stroke_rates = {0: 0, 1: 1.3, 2: 2.2, 3: 3.2, 4: 4.0, 5: 6.7, 6: 9.8, 7: 9.6, 8: 12.5, 9: 15.2}
    stroke_rate = stroke_rates.get(score, 15.2)

    if score == 0:
        risk = RiskLevel.LOW
        interpretation = f"Low risk - Annual stroke rate ~{stroke_rate}%"
        recommendations = ["Anticoagulation generally not recommended", "May consider no therapy or aspirin", "Reassess risk factors annually"]
    elif score == 1:
        risk = RiskLevel.LOW_MODERATE
        interpretation = f"Low-moderate risk - Annual stroke rate ~{stroke_rate}%"
        recommendations = ["Consider oral anticoagulation", "If male with score 1, may consider no therapy", "Shared decision-making based on bleeding risk"]
    elif score == 2:
        risk = RiskLevel.MODERATE
        interpretation = f"Moderate risk - Annual stroke rate ~{stroke_rate}%"
        recommendations = ["Oral anticoagulation recommended", "DOAC preferred over warfarin", "Assess bleeding risk with HAS-BLED"]
    else:
        risk = RiskLevel.HIGH if score <= 4 else RiskLevel.VERY_HIGH
        interpretation = f"High risk - Annual stroke rate ~{stroke_rate}%"
        recommendations = ["Oral anticoagulation strongly recommended", "DOAC preferred unless contraindicated", "Consider LAA closure if anticoagulation contraindicated", "Strict risk factor control"]

    return CalculatorResult(
        calculator_id="cha2ds2_vasc",
        calculator_name="CHA2DS2-VASc Score",
        score=score,
        score_unit="points",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["2019 AHA/ACC/HRS AF Guidelines", "Lip GY, et al. Chest 2010"],
        formula_used="C(HF)+H(ypertension)+A2(ge>=75)+D(iabetes)+S2(troke)+V(ascular)+A(ge 65-74)+Sc(female)"
    )


def calculate_has_bled(input_data: HASBLEDInput) -> CalculatorResult:
    """Calculate HAS-BLED Score for bleeding risk on anticoagulation.

    Reference: Pisters R, et al. Chest 2010
    """
    score = 0
    components = {}

    if input_data.hypertension:
        score += 1
        components["Hypertension"] = 1
    if input_data.renal_disease:
        score += 1
        components["Abnormal renal function"] = 1
    if input_data.liver_disease:
        score += 1
        components["Abnormal liver function"] = 1
    if input_data.stroke_history:
        score += 1
        components["Stroke history"] = 1
    if input_data.bleeding_history:
        score += 1
        components["Bleeding history"] = 1
    if input_data.labile_inr:
        score += 1
        components["Labile INR"] = 1
    if input_data.age_over_65:
        score += 1
        components["Elderly (>65)"] = 1
    if input_data.antiplatelet_nsaid:
        score += 1
        components["Drugs (antiplatelet/NSAID)"] = 1
    if input_data.alcohol_use:
        score += 1
        components["Alcohol use"] = 1

    if score <= 1:
        risk = RiskLevel.LOW
        interpretation = f"Low bleeding risk (score {score})"
        recommendations = ["Anticoagulation generally safe", "Standard monitoring", "Annual bleeding risk reassessment"]
    elif score == 2:
        risk = RiskLevel.MODERATE
        interpretation = f"Moderate bleeding risk (score {score})"
        recommendations = ["Anticoagulation can be considered", "Address modifiable risk factors", "More frequent monitoring recommended"]
    else:
        risk = RiskLevel.HIGH
        interpretation = f"High bleeding risk (score {score}) - requires caution"
        recommendations = ["High risk does NOT contraindicate anticoagulation", "Address ALL modifiable risk factors", "Consider DOAC over warfarin", "Close monitoring and follow-up", "Consider PPI for GI protection"]

    return CalculatorResult(
        calculator_id="has_bled",
        calculator_name="HAS-BLED Score",
        score=score,
        score_unit="points",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Pisters R, et al. Chest 2010;138:1093-1100"],
        formula_used="H(ypertension)+A(bnormal renal/liver)+S(troke)+B(leeding)+L(abile INR)+E(lderly)+D(rugs/alcohol)"
    )


def calculate_egfr_ckdepi(input_data: EGFRInput) -> CalculatorResult:
    """Calculate eGFR using CKD-EPI 2021 equation (race-free).

    Formula: eGFR = 142 x min(Scr/k, 1)^a x max(Scr/k, 1)^-1.200 x 0.9938^Age x (1.012 if female)
    Reference: Inker LA, et al. NEJM 2021
    """
    female = input_data.sex == "female"
    kappa = 0.7 if female else 0.9
    alpha = -0.241 if female else -0.302

    scr_ratio = input_data.creatinine / kappa
    min_term = min(scr_ratio, 1) ** alpha
    max_term = max(scr_ratio, 1) ** -1.200
    age_term = 0.9938 ** input_data.age
    sex_term = 1.012 if female else 1

    egfr = 142 * min_term * max_term * age_term * sex_term
    egfr = round(egfr, 1)

    if egfr >= 90:
        stage = "G1"
        risk = RiskLevel.LOW
        interpretation = f"CKD Stage {stage}: Normal or high kidney function"
        recommendations = ["Annual monitoring if risk factors present", "Control blood pressure and diabetes", "Avoid nephrotoxic medications when possible"]
    elif egfr >= 60:
        stage = "G2"
        risk = RiskLevel.LOW_MODERATE
        interpretation = f"CKD Stage {stage}: Mildly decreased kidney function"
        recommendations = ["Monitor eGFR annually", "Optimize blood pressure control", "Review medications for renal dosing"]
    elif egfr >= 45:
        stage = "G3a"
        risk = RiskLevel.MODERATE
        interpretation = f"CKD Stage {stage}: Mild-moderate decrease"
        recommendations = ["Monitor eGFR every 6 months", "Nephrology referral if rapid decline", "Screen for CKD complications", "Adjust medications for renal function"]
    elif egfr >= 30:
        stage = "G3b"
        risk = RiskLevel.MODERATE_HIGH
        interpretation = f"CKD Stage {stage}: Moderate-severe decrease"
        recommendations = ["Nephrology referral recommended", "Monitor every 3-6 months", "Prepare for kidney replacement therapy", "Strict avoidance of nephrotoxins"]
    elif egfr >= 15:
        stage = "G4"
        risk = RiskLevel.HIGH
        interpretation = f"CKD Stage {stage}: Severely decreased kidney function"
        recommendations = ["Nephrology co-management essential", "Plan for dialysis or transplant", "Monthly monitoring", "Strict medication review"]
    else:
        stage = "G5"
        risk = RiskLevel.VERY_HIGH
        interpretation = f"CKD Stage {stage}: Kidney failure"
        recommendations = ["Initiate dialysis or transplant evaluation", "Intensive nephrology management", "Discuss goals of care", "Urgent management of complications"]

    return CalculatorResult(
        calculator_id="egfr_ckdepi",
        calculator_name="CKD-EPI eGFR (2021)",
        score=egfr,
        score_unit="mL/min/1.73m2",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components={"creatinine": input_data.creatinine, "age": input_data.age, "sex": input_data.sex, "ckd_stage": stage},
        references=["Inker LA, et al. NEJM 2021;385:1737-1749", "KDIGO 2012 CKD Guidelines"],
        formula_used="eGFR = 142 x min(Scr/k, 1)^a x max(Scr/k, 1)^-1.200 x 0.9938^Age x (1.012 if female)"
    )


def calculate_cockcroft_gault(input_data: CockcroftGaultInput) -> CalculatorResult:
    """Calculate Creatinine Clearance using Cockcroft-Gault equation.

    Formula: CrCl = [(140 - age) x weight] / (72 x Scr) x 0.85 if female
    Reference: Cockcroft DW, Gault MH. Nephron 1976
    """
    female = input_data.sex == "female"

    crcl = ((140 - input_data.age) * input_data.weight_kg) / (72 * input_data.creatinine)
    if female:
        crcl *= 0.85
    crcl = round(crcl, 1)

    if crcl >= 90:
        risk = RiskLevel.LOW
        interpretation = "Normal creatinine clearance"
        recommendations = ["Standard medication dosing", "Continue current management"]
    elif crcl >= 60:
        risk = RiskLevel.LOW_MODERATE
        interpretation = "Mildly reduced creatinine clearance"
        recommendations = ["Review medications for renal dosing", "Monitor kidney function"]
    elif crcl >= 30:
        risk = RiskLevel.MODERATE
        interpretation = "Moderately reduced creatinine clearance"
        recommendations = ["Adjust renally-cleared medications", "Avoid nephrotoxins", "Consider nephrology referral"]
    elif crcl >= 15:
        risk = RiskLevel.HIGH
        interpretation = "Severely reduced creatinine clearance"
        recommendations = ["Significant dose adjustments needed", "Nephrology involvement", "Avoid contrast if possible"]
    else:
        risk = RiskLevel.VERY_HIGH
        interpretation = "End-stage kidney function"
        recommendations = ["Dialysis consideration", "Avoid renally-cleared medications", "Urgent nephrology consultation"]

    return CalculatorResult(
        calculator_id="cockcroft_gault",
        calculator_name="Creatinine Clearance (Cockcroft-Gault)",
        score=crcl,
        score_unit="mL/min",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components={"creatinine": input_data.creatinine, "age": input_data.age, "weight_kg": input_data.weight_kg, "sex": input_data.sex},
        references=["Cockcroft DW, Gault MH. Nephron 1976;16:31-41"],
        formula_used="CrCl = [(140 - age) x weight] / (72 x Scr) x 0.85 if female",
        warnings=["Not indexed to body surface area", "May overestimate in obese patients", "Less accurate at extremes of muscle mass"]
    )


def calculate_uacr(input_data: UACRInput) -> CalculatorResult:
    """Interpret Urine Albumin-to-Creatinine Ratio.

    Reference: KDIGO 2012 CKD Guidelines
    """
    uacr = input_data.uacr

    if uacr < 30:
        category = "A1"
        risk = RiskLevel.LOW
        interpretation = f"Normal to mildly increased albuminuria (A1): UACR {uacr} mg/g"
        recommendations = ["Annual monitoring in at-risk patients", "Continue risk factor control"]
    elif uacr < 300:
        category = "A2"
        risk = RiskLevel.MODERATE
        interpretation = f"Moderately increased albuminuria (A2): UACR {uacr} mg/g"
        recommendations = ["ACE inhibitor or ARB therapy", "Optimize BP control (<130/80)", "Monitor UACR every 6 months", "Screen for cardiovascular disease"]
    else:
        category = "A3"
        risk = RiskLevel.HIGH
        interpretation = f"Severely increased albuminuria (A3): UACR {uacr} mg/g"
        recommendations = ["Maximize ACE inhibitor or ARB", "Consider SGLT2 inhibitor", "Nephrology referral", "Aggressive cardiovascular risk reduction", "Monitor UACR every 3-6 months"]

    return CalculatorResult(
        calculator_id="uacr",
        calculator_name="UACR Interpretation",
        score=uacr,
        score_unit="mg/g",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components={"uacr": uacr, "category": category},
        references=["KDIGO 2012 CKD Guidelines", "KDIGO 2021 Management of CKD"],
        formula_used="Direct measurement interpretation"
    )


def calculate_meld(input_data: MELDInput) -> CalculatorResult:
    """Calculate MELD or MELD-Na Score.

    MELD = 10 x (0.957 x ln(Cr) + 0.378 x ln(Bili) + 1.120 x ln(INR) + 0.643)
    MELD-Na = MELD + 1.32 x (137 - Na) - 0.033 x MELD x (137 - Na)
    Reference: UNOS MELD allocation policy
    """
    # Apply bounds
    cr = 4.0 if input_data.on_dialysis else max(1.0, min(input_data.creatinine, 4.0))
    bili = max(1.0, input_data.bilirubin)
    inr_val = max(1.0, input_data.inr)

    # MELD calculation
    meld = 10 * (0.957 * math.log(cr) + 0.378 * math.log(bili) + 1.120 * math.log(inr_val) + 0.643)

    # MELD-Na if sodium provided
    if input_data.sodium is not None:
        na = max(125, min(input_data.sodium, 137))
        meld_na = meld + 1.32 * (137 - na) - 0.033 * meld * (137 - na)
        meld_na = max(6, min(round(meld_na), 40))
        score = meld_na
        calc_name = "MELD-Na Score"
    else:
        score = max(6, min(round(meld), 40))
        calc_name = "MELD Score"

    if score < 10:
        risk = RiskLevel.LOW
        interpretation = f"{calc_name} {score}: Low risk - 3-month mortality ~2%"
        recommendations = ["Continue medical management", "Monitor for disease progression", "Routine follow-up"]
    elif score < 20:
        risk = RiskLevel.MODERATE
        interpretation = f"{calc_name} {score}: Moderate risk - 3-month mortality ~6-20%"
        recommendations = ["Liver transplant evaluation", "Optimize medical management", "Monitor closely for complications"]
    elif score < 30:
        risk = RiskLevel.HIGH
        interpretation = f"{calc_name} {score}: High risk - 3-month mortality ~50%"
        recommendations = ["Urgent transplant evaluation", "ICU monitoring may be needed", "Aggressive complication management"]
    else:
        risk = RiskLevel.VERY_HIGH
        interpretation = f"{calc_name} {score}: Very high risk - 3-month mortality ~70-80%"
        recommendations = ["Emergent transplant consideration", "ICU care required", "Discuss goals of care", "Palliative care consultation"]

    components = {"creatinine": input_data.creatinine, "bilirubin": input_data.bilirubin, "inr": input_data.inr, "on_dialysis": input_data.on_dialysis}
    if input_data.sodium:
        components["sodium"] = input_data.sodium
        components["meld_basic"] = round(meld)

    return CalculatorResult(
        calculator_id="meld",
        calculator_name=calc_name,
        score=score,
        score_unit="points",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["UNOS MELD allocation policy", "Kim WR, et al. Hepatology 2008"],
        formula_used="MELD = 10 x (0.957 x ln(Cr) + 0.378 x ln(Bili) + 1.120 x ln(INR) + 0.643)"
    )


def calculate_child_pugh(input_data: ChildPughInput) -> CalculatorResult:
    """Calculate Child-Pugh Score for cirrhosis severity.

    Reference: Pugh RN, et al. Br J Surg 1973
    """
    score = 0
    components = {}

    # Bilirubin
    if input_data.bilirubin < 2:
        score += 1
        components["bilirubin"] = 1
    elif input_data.bilirubin <= 3:
        score += 2
        components["bilirubin"] = 2
    else:
        score += 3
        components["bilirubin"] = 3

    # Albumin
    if input_data.albumin > 3.5:
        score += 1
        components["albumin"] = 1
    elif input_data.albumin >= 2.8:
        score += 2
        components["albumin"] = 2
    else:
        score += 3
        components["albumin"] = 3

    # INR
    if input_data.inr < 1.7:
        score += 1
        components["inr"] = 1
    elif input_data.inr <= 2.3:
        score += 2
        components["inr"] = 2
    else:
        score += 3
        components["inr"] = 3

    # Ascites
    if input_data.ascites == "none":
        score += 1
        components["ascites"] = 1
    elif input_data.ascites == "mild":
        score += 2
        components["ascites"] = 2
    else:
        score += 3
        components["ascites"] = 3

    # Encephalopathy
    if input_data.encephalopathy == "none":
        score += 1
        components["encephalopathy"] = 1
    elif input_data.encephalopathy == "grade_1_2":
        score += 2
        components["encephalopathy"] = 2
    else:
        score += 3
        components["encephalopathy"] = 3

    if score <= 6:
        grade = "A"
        risk = RiskLevel.LOW
        interpretation = f"Child-Pugh Class A (score {score}): Well-compensated cirrhosis"
        recommendations = ["Continue surveillance", "Variceal screening if not done", "HCC screening every 6 months"]
    elif score <= 9:
        grade = "B"
        risk = RiskLevel.MODERATE
        interpretation = f"Child-Pugh Class B (score {score}): Significant functional compromise"
        recommendations = ["Transplant evaluation", "Avoid hepatotoxins", "Dose-adjust medications", "Consider surgical risk carefully"]
    else:
        grade = "C"
        risk = RiskLevel.HIGH
        interpretation = f"Child-Pugh Class C (score {score}): Decompensated cirrhosis"
        recommendations = ["Urgent transplant evaluation", "Avoid surgery if possible", "Palliative care discussion", "Aggressive complication management"]

    components["grade"] = grade

    return CalculatorResult(
        calculator_id="child_pugh",
        calculator_name="Child-Pugh Score",
        score=score,
        score_unit="points",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Pugh RN, et al. Br J Surg 1973;60:646-649"],
        formula_used="Bilirubin + Albumin + INR + Ascites + Encephalopathy (each 1-3 points)"
    )


def calculate_fib4(input_data: FIB4Input) -> CalculatorResult:
    """Calculate FIB-4 Score for liver fibrosis.

    Formula: FIB-4 = (Age x AST) / (Platelets x sqrt(ALT))
    Reference: Sterling RK, et al. Hepatology 2006
    """
    fib4 = (input_data.age * input_data.ast) / (input_data.platelets * math.sqrt(input_data.alt))
    fib4 = round(fib4, 2)

    if fib4 < 1.30:
        risk = RiskLevel.LOW
        interpretation = f"FIB-4 {fib4}: Low probability of advanced fibrosis (F3-F4)"
        recommendations = ["Low likelihood of advanced fibrosis", "Repeat FIB-4 in 1-2 years", "Continue lifestyle modifications"]
    elif fib4 <= 2.67:
        risk = RiskLevel.MODERATE
        interpretation = f"FIB-4 {fib4}: Indeterminate - further testing needed"
        recommendations = ["Consider liver elastography (FibroScan)", "Consider liver biopsy if elastography indeterminate", "Evaluate for other liver diseases"]
    else:
        risk = RiskLevel.HIGH
        interpretation = f"FIB-4 {fib4}: High probability of advanced fibrosis (F3-F4)"
        recommendations = ["High likelihood of advanced fibrosis/cirrhosis", "Hepatology referral", "HCC surveillance if cirrhosis", "Variceal screening"]

    return CalculatorResult(
        calculator_id="fib4",
        calculator_name="FIB-4 Score",
        score=fib4,
        score_unit="",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components={"age": input_data.age, "ast": input_data.ast, "alt": input_data.alt, "platelets": input_data.platelets},
        references=["Sterling RK, et al. Hepatology 2006;43:1317-1325", "AASLD/EASL Guidelines"],
        formula_used="FIB-4 = (Age x AST) / (Platelets x sqrt(ALT))"
    )


def calculate_sofa(input_data: SOFAInput) -> CalculatorResult:
    """Calculate SOFA Score for organ dysfunction.

    Reference: Vincent JL, et al. Intensive Care Med 1996
    """
    score = 0
    components = {}

    # Respiratory: PaO2/FiO2
    if input_data.pao2_fio2 >= 400:
        components["respiratory"] = 0
    elif input_data.pao2_fio2 >= 300:
        score += 1
        components["respiratory"] = 1
    elif input_data.pao2_fio2 >= 200:
        score += 2
        components["respiratory"] = 2
    elif input_data.pao2_fio2 >= 100:
        score += 3 if input_data.on_ventilator else 2
        components["respiratory"] = 3 if input_data.on_ventilator else 2
    else:
        score += 4 if input_data.on_ventilator else 3
        components["respiratory"] = 4 if input_data.on_ventilator else 3

    # Coagulation: Platelets
    if input_data.platelets >= 150:
        components["coagulation"] = 0
    elif input_data.platelets >= 100:
        score += 1
        components["coagulation"] = 1
    elif input_data.platelets >= 50:
        score += 2
        components["coagulation"] = 2
    elif input_data.platelets >= 20:
        score += 3
        components["coagulation"] = 3
    else:
        score += 4
        components["coagulation"] = 4

    # Liver: Bilirubin
    if input_data.bilirubin < 1.2:
        components["liver"] = 0
    elif input_data.bilirubin < 2:
        score += 1
        components["liver"] = 1
    elif input_data.bilirubin < 6:
        score += 2
        components["liver"] = 2
    elif input_data.bilirubin < 12:
        score += 3
        components["liver"] = 3
    else:
        score += 4
        components["liver"] = 4

    # Cardiovascular: MAP and vasopressors
    if input_data.map >= 70 and input_data.vasopressor == "none":
        components["cardiovascular"] = 0
    elif input_data.map < 70 and input_data.vasopressor == "none":
        score += 1
        components["cardiovascular"] = 1
    elif input_data.vasopressor in ["dopamine_low", "dobutamine"]:
        score += 2
        components["cardiovascular"] = 2
    elif input_data.vasopressor in ["dopamine_high", "epi_low", "norepi_low"]:
        score += 3
        components["cardiovascular"] = 3
    else:
        score += 4
        components["cardiovascular"] = 4

    # CNS: GCS
    if input_data.gcs == 15:
        components["cns"] = 0
    elif input_data.gcs >= 13:
        score += 1
        components["cns"] = 1
    elif input_data.gcs >= 10:
        score += 2
        components["cns"] = 2
    elif input_data.gcs >= 6:
        score += 3
        components["cns"] = 3
    else:
        score += 4
        components["cns"] = 4

    # Renal: Creatinine or urine output
    if input_data.creatinine < 1.2:
        components["renal"] = 0
    elif input_data.creatinine < 2:
        score += 1
        components["renal"] = 1
    elif input_data.creatinine < 3.5:
        score += 2
        components["renal"] = 2
    elif input_data.creatinine < 5 or (input_data.urine_output and input_data.urine_output < 500):
        score += 3
        components["renal"] = 3
    else:
        score += 4
        components["renal"] = 4

    # Mortality estimates
    if score <= 1:
        risk = RiskLevel.LOW
        interpretation = f"SOFA {score}: Minimal organ dysfunction - mortality <10%"
    elif score <= 5:
        risk = RiskLevel.MODERATE
        interpretation = f"SOFA {score}: Mild organ dysfunction - mortality ~15-20%"
    elif score <= 9:
        risk = RiskLevel.HIGH
        interpretation = f"SOFA {score}: Moderate organ dysfunction - mortality ~40-50%"
    elif score <= 14:
        risk = RiskLevel.HIGH
        interpretation = f"SOFA {score}: Severe organ dysfunction - mortality ~50-80%"
    else:
        risk = RiskLevel.VERY_HIGH
        interpretation = f"SOFA {score}: Very severe - mortality >80%"

    recommendations = ["Monitor organ function trends", "Address individual organ failures", "Consider sepsis if change >=2 from baseline"]
    if score >= 6:
        recommendations.extend(["ICU level care required", "Consider goals of care discussion"])

    return CalculatorResult(
        calculator_id="sofa",
        calculator_name="SOFA Score",
        score=score,
        score_unit="points",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Vincent JL, et al. Intensive Care Med 1996;22:707-710", "Sepsis-3 Criteria"],
        formula_used="Respiratory + Coagulation + Liver + Cardiovascular + CNS + Renal (each 0-4)"
    )


def calculate_qsofa(input_data: QSOFAInput) -> CalculatorResult:
    """Calculate qSOFA Score for sepsis screening.

    Reference: Seymour CW, et al. JAMA 2016 (Sepsis-3)
    """
    score = 0
    components = {}

    if input_data.respiratory_rate >= 22:
        score += 1
        components["respiratory_rate"] = 1
    else:
        components["respiratory_rate"] = 0

    if input_data.systolic_bp <= 100:
        score += 1
        components["systolic_bp"] = 1
    else:
        components["systolic_bp"] = 0

    if input_data.altered_mental_status:
        score += 1
        components["altered_mental_status"] = 1
    else:
        components["altered_mental_status"] = 0

    if score < 2:
        risk = RiskLevel.LOW
        interpretation = f"qSOFA {score}: Low risk - sepsis unlikely"
        recommendations = ["Continue monitoring", "Reassess if clinical status changes", "Consider other diagnoses"]
    else:
        risk = RiskLevel.HIGH
        interpretation = f"qSOFA {score}: High risk - suspect sepsis"
        recommendations = ["Obtain lactate and cultures", "Start empiric antibiotics", "Fluid resuscitation", "Full SOFA assessment", "ICU consultation"]

    return CalculatorResult(
        calculator_id="qsofa",
        calculator_name="qSOFA Score",
        score=score,
        score_unit="points",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Seymour CW, et al. JAMA 2016;315:762-774", "Sepsis-3 Guidelines"],
        formula_used="RR>=22 + SBP<=100 + Altered mental status (GCS<15)"
    )


def calculate_wells_pe(input_data: WellsPEInput) -> CalculatorResult:
    """Calculate Wells Score for Pulmonary Embolism.

    Reference: Wells PS, et al. Ann Intern Med 2001
    """
    score = 0.0
    components = {}

    if input_data.clinical_dvt:
        score += 3
        components["clinical_dvt"] = 3
    if input_data.pe_most_likely:
        score += 3
        components["pe_most_likely"] = 3
    if input_data.heart_rate_over_100:
        score += 1.5
        components["heart_rate_over_100"] = 1.5
    if input_data.immobilization_surgery:
        score += 1.5
        components["immobilization_surgery"] = 1.5
    if input_data.previous_pe_dvt:
        score += 1.5
        components["previous_pe_dvt"] = 1.5
    if input_data.hemoptysis:
        score += 1
        components["hemoptysis"] = 1
    if input_data.malignancy:
        score += 1
        components["malignancy"] = 1

    if score <= 1:
        risk = RiskLevel.LOW
        interpretation = f"Wells PE {score}: Low probability (~1.3% PE risk)"
        recommendations = ["Check D-dimer", "If D-dimer negative, PE excluded", "If D-dimer positive, CT angiography"]
    elif score <= 4:
        risk = RiskLevel.MODERATE
        interpretation = f"Wells PE {score}: Moderate probability (~16.2% PE risk)"
        recommendations = ["Check D-dimer", "If D-dimer negative, PE unlikely", "If D-dimer positive, CT angiography"]
    else:
        risk = RiskLevel.HIGH
        interpretation = f"Wells PE {score}: High probability (~37.5% PE risk)"
        recommendations = ["CT pulmonary angiography recommended", "Consider empiric anticoagulation", "D-dimer not recommended (high false negative)"]

    return CalculatorResult(
        calculator_id="wells_pe",
        calculator_name="Wells Score for PE",
        score=score,
        score_unit="points",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Wells PS, et al. Ann Intern Med 2001;135:98-107", "ACEP Clinical Policy 2018"],
        formula_used="Clinical DVT(3) + PE most likely(3) + HR>100(1.5) + Immob/Surg(1.5) + Previous VTE(1.5) + Hemoptysis(1) + Malignancy(1)"
    )


def calculate_wells_dvt(input_data: WellsDVTInput) -> CalculatorResult:
    """Calculate Wells Score for DVT.

    Reference: Wells PS, et al. NEJM 2003
    """
    score = 0
    components = {}

    if input_data.active_cancer:
        score += 1
        components["active_cancer"] = 1
    if input_data.paralysis_immobilization:
        score += 1
        components["paralysis_immobilization"] = 1
    if input_data.bedridden_surgery:
        score += 1
        components["bedridden_surgery"] = 1
    if input_data.localized_tenderness:
        score += 1
        components["localized_tenderness"] = 1
    if input_data.entire_leg_swollen:
        score += 1
        components["entire_leg_swollen"] = 1
    if input_data.calf_swelling_3cm:
        score += 1
        components["calf_swelling_3cm"] = 1
    if input_data.pitting_edema:
        score += 1
        components["pitting_edema"] = 1
    if input_data.collateral_veins:
        score += 1
        components["collateral_veins"] = 1
    if input_data.previous_dvt:
        score += 1
        components["previous_dvt"] = 1
    if input_data.alternative_diagnosis_likely:
        score -= 2
        components["alternative_diagnosis_likely"] = -2

    if score <= 0:
        risk = RiskLevel.LOW
        interpretation = f"Wells DVT {score}: Low probability (~5% DVT risk)"
        recommendations = ["Check D-dimer", "If D-dimer negative, DVT excluded", "If D-dimer positive, ultrasound"]
    elif score <= 2:
        risk = RiskLevel.MODERATE
        interpretation = f"Wells DVT {score}: Moderate probability (~17% DVT risk)"
        recommendations = ["Check D-dimer", "If D-dimer negative, DVT unlikely", "If D-dimer positive, ultrasound"]
    else:
        risk = RiskLevel.HIGH
        interpretation = f"Wells DVT {score}: High probability (~53% DVT risk)"
        recommendations = ["Venous ultrasound recommended", "Consider empiric anticoagulation", "D-dimer not recommended"]

    return CalculatorResult(
        calculator_id="wells_dvt",
        calculator_name="Wells Score for DVT",
        score=score,
        score_unit="points",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Wells PS, et al. NEJM 2003;349:1227-1235"],
        formula_used="Sum of criteria (cancer, paralysis, bedridden, tenderness, leg swollen, calf swelling, edema, veins, previous DVT) - 2 if alternative diagnosis"
    )


def calculate_corrected_calcium(input_data: CorrectedCalciumInput) -> CalculatorResult:
    """Calculate Albumin-Corrected Calcium.

    Formula: Corrected Ca = Total Ca + 0.8 x (4 - Albumin)
    Reference: Bushinsky DA, Monk RD. Lancet 1998
    """
    corrected = input_data.calcium + 0.8 * (4 - input_data.albumin)
    corrected = round(corrected, 1)

    if corrected < 8.5:
        risk = RiskLevel.MODERATE_HIGH
        interpretation = f"Hypocalcemia: Corrected calcium {corrected} mg/dL"
        recommendations = ["Evaluate for vitamin D deficiency", "Check PTH level", "Consider calcium supplementation", "Check magnesium"]
    elif corrected <= 10.5:
        risk = RiskLevel.LOW
        interpretation = f"Normal calcium: Corrected calcium {corrected} mg/dL"
        recommendations = ["No intervention needed"]
    elif corrected <= 12:
        risk = RiskLevel.MODERATE
        interpretation = f"Mild hypercalcemia: Corrected calcium {corrected} mg/dL"
        recommendations = ["Evaluate for primary hyperparathyroidism", "Check PTH and vitamin D", "Review medications"]
    elif corrected <= 14:
        risk = RiskLevel.HIGH
        interpretation = f"Moderate hypercalcemia: Corrected calcium {corrected} mg/dL"
        recommendations = ["Urgent evaluation", "IV hydration", "Evaluate for malignancy or hyperparathyroidism"]
    else:
        risk = RiskLevel.VERY_HIGH
        interpretation = f"Severe hypercalcemia: Corrected calcium {corrected} mg/dL"
        recommendations = ["Medical emergency", "IV hydration and calcitonin", "Consider bisphosphonates", "ICU monitoring"]

    return CalculatorResult(
        calculator_id="corrected_calcium",
        calculator_name="Corrected Calcium",
        score=corrected,
        score_unit="mg/dL",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components={"calcium": input_data.calcium, "albumin": input_data.albumin},
        references=["Bushinsky DA, Monk RD. Lancet 1998;352:306-311"],
        formula_used="Corrected Ca = Total Ca + 0.8 x (4 - Albumin)"
    )


def calculate_anion_gap(input_data: AnionGapInput) -> CalculatorResult:
    """Calculate Serum Anion Gap.

    Formula: AG = Na - (Cl + HCO3)
    Corrected AG = AG + 2.5 x (4 - Albumin)
    Reference: Seifter JL. NEJM 2014
    """
    ag = input_data.sodium - (input_data.chloride + input_data.bicarbonate)

    components = {"sodium": input_data.sodium, "chloride": input_data.chloride, "bicarbonate": input_data.bicarbonate, "anion_gap": ag}

    if input_data.albumin:
        ag_corrected = ag + 2.5 * (4 - input_data.albumin)
        ag_corrected = round(ag_corrected, 1)
        components["albumin"] = input_data.albumin
        components["corrected_anion_gap"] = ag_corrected
        score = ag_corrected
        calc_name = "Corrected Anion Gap"
    else:
        score = ag
        calc_name = "Anion Gap"

    if score < 3:
        risk = RiskLevel.MODERATE
        interpretation = f"Low {calc_name}: {score} mEq/L - consider lab error"
        recommendations = ["Verify lab values", "Consider hypoalbuminemia", "Consider lithium toxicity or lab error"]
    elif score <= 12:
        risk = RiskLevel.LOW
        interpretation = f"Normal {calc_name}: {score} mEq/L"
        recommendations = ["Normal finding"]
    elif score <= 20:
        risk = RiskLevel.MODERATE
        interpretation = f"Elevated {calc_name}: {score} mEq/L"
        recommendations = ["Evaluate for causes (MUDPILES)", "Check lactate and ketones", "Review medications"]
    else:
        risk = RiskLevel.HIGH
        interpretation = f"High {calc_name}: {score} mEq/L - metabolic acidosis"
        recommendations = ["Urgent evaluation for high AG metabolic acidosis", "Consider: ketoacidosis, lactic acidosis, toxins, uremia", "Check lactate, ketones, toxicology", "Check osmolar gap"]

    return CalculatorResult(
        calculator_id="anion_gap",
        calculator_name=calc_name,
        score=round(score, 1),
        score_unit="mEq/L",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Seifter JL. NEJM 2014;371:1434-1445", "Kraut JA, Madias NE. CJASN 2007"],
        formula_used="AG = Na - (Cl + HCO3); Corrected AG = AG + 2.5 x (4 - Albumin)"
    )


def calculate_gcs(input_data: GCSInput) -> CalculatorResult:
    """Calculate Glasgow Coma Scale.

    Reference: Teasdale G, Jennett B. Lancet 1974
    """
    score = input_data.eye_response + input_data.verbal_response + input_data.motor_response

    components = {
        "eye_response": input_data.eye_response,
        "verbal_response": input_data.verbal_response,
        "motor_response": input_data.motor_response,
    }

    if score >= 13:
        risk = RiskLevel.LOW
        severity = "Mild"
        interpretation = f"GCS {score}: Mild brain injury"
        recommendations = ["Monitor neurological status", "Head CT if trauma with risk factors"]
    elif score >= 9:
        risk = RiskLevel.MODERATE
        severity = "Moderate"
        interpretation = f"GCS {score}: Moderate brain injury"
        recommendations = ["Urgent head CT", "Close monitoring", "Consider neurosurgery consult", "Admission recommended"]
    else:
        risk = RiskLevel.VERY_HIGH
        severity = "Severe"
        interpretation = f"GCS {score}: Severe brain injury"
        recommendations = ["Emergent head CT", "Airway protection - consider intubation", "ICU admission", "Neurosurgery consultation urgent"]

    return CalculatorResult(
        calculator_id="gcs",
        calculator_name="Glasgow Coma Scale",
        score=score,
        score_unit="points",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Teasdale G, Jennett B. Lancet 1974"],
        formula_used="GCS = Eye + Verbal + Motor"
    )


def calculate_news2(input_data: NEWS2Input) -> CalculatorResult:
    """Calculate NEWS2 (National Early Warning Score 2).

    Reference: Royal College of Physicians 2017
    """
    score = 0
    components = {}

    # Respiratory rate
    rr = input_data.respiratory_rate
    if rr <= 8:
        rr_pts = 3
    elif rr <= 11:
        rr_pts = 1
    elif rr <= 20:
        rr_pts = 0
    elif rr <= 24:
        rr_pts = 2
    else:
        rr_pts = 3
    score += rr_pts
    components["respiratory_rate"] = rr_pts

    # SpO2 (Scale 1 or Scale 2 for COPD)
    spo2 = input_data.spo2
    if input_data.copd_scale_2:
        if spo2 <= 83:
            spo2_pts = 3
        elif spo2 <= 85:
            spo2_pts = 2
        elif spo2 <= 87:
            spo2_pts = 1
        elif spo2 <= 92:
            spo2_pts = 0
        elif spo2 <= 94:
            spo2_pts = 1
        elif spo2 <= 96:
            spo2_pts = 2
        else:
            spo2_pts = 3
    else:
        if spo2 <= 91:
            spo2_pts = 3
        elif spo2 <= 93:
            spo2_pts = 2
        elif spo2 <= 95:
            spo2_pts = 1
        else:
            spo2_pts = 0
    score += spo2_pts
    components["spo2"] = spo2_pts

    # Supplemental oxygen
    o2_pts = 2 if input_data.supplemental_o2 else 0
    score += o2_pts
    components["supplemental_o2"] = o2_pts

    # Temperature
    temp = input_data.temperature
    if temp <= 35.0:
        temp_pts = 3
    elif temp <= 36.0:
        temp_pts = 1
    elif temp <= 38.0:
        temp_pts = 0
    elif temp <= 39.0:
        temp_pts = 1
    else:
        temp_pts = 2
    score += temp_pts
    components["temperature"] = temp_pts

    # Systolic BP
    sbp = input_data.systolic_bp
    if sbp <= 90:
        sbp_pts = 3
    elif sbp <= 100:
        sbp_pts = 2
    elif sbp <= 110:
        sbp_pts = 1
    elif sbp <= 219:
        sbp_pts = 0
    else:
        sbp_pts = 3
    score += sbp_pts
    components["systolic_bp"] = sbp_pts

    # Heart rate
    hr = input_data.heart_rate
    if hr <= 40:
        hr_pts = 3
    elif hr <= 50:
        hr_pts = 1
    elif hr <= 90:
        hr_pts = 0
    elif hr <= 110:
        hr_pts = 1
    elif hr <= 130:
        hr_pts = 2
    else:
        hr_pts = 3
    score += hr_pts
    components["heart_rate"] = hr_pts

    # Consciousness
    cons_lower = input_data.consciousness.lower()
    cons_pts = 0 if cons_lower in ("alert", "a") else 3
    score += cons_pts
    components["consciousness"] = cons_pts

    # Risk stratification
    if score == 0:
        risk = RiskLevel.LOW
        interpretation = "NEWS2 = 0: Low clinical risk"
        recommendations = ["Continue routine monitoring", "Minimum 12-hourly observations"]
    elif score <= 4:
        risk = RiskLevel.LOW_MODERATE
        interpretation = f"NEWS2 = {score}: Low-medium clinical risk"
        recommendations = ["Increase monitoring to 4-6 hourly", "RN to assess patient"]
    elif score <= 6:
        risk = RiskLevel.MODERATE
        interpretation = f"NEWS2 = {score}: Medium clinical risk"
        recommendations = ["Urgent response required", "Hourly observations", "Urgent assessment by clinician"]
    else:
        risk = RiskLevel.HIGH
        interpretation = f"NEWS2 = {score}: High clinical risk"
        recommendations = ["Emergency response required", "Continuous monitoring", "Critical care team assessment", "Consider ICU/HDU"]

    return CalculatorResult(
        calculator_id="news2",
        calculator_name="NEWS2 (National Early Warning Score 2)",
        score=score,
        score_unit="points",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Royal College of Physicians 2017"],
        formula_used="Sum of parameter scores (RR, SpO2, O2, Temp, SBP, HR, AVPU)"
    )


def calculate_curb65(input_data: CURB65Input) -> CalculatorResult:
    """Calculate CURB-65 pneumonia severity score.

    Reference: Lim WS, et al. Thorax 2003
    """
    score = 0
    components = {}

    if input_data.confusion:
        score += 1
        components["confusion"] = 1
    if input_data.bun_over_19:
        score += 1
        components["bun_over_19"] = 1
    if input_data.respiratory_rate_over_30:
        score += 1
        components["respiratory_rate_over_30"] = 1
    if input_data.low_bp:
        score += 1
        components["low_bp"] = 1
    if input_data.age_65_or_older:
        score += 1
        components["age_65_or_older"] = 1

    mortality_rates = {0: "0.7%", 1: "3.2%", 2: "13%", 3: "17%", 4: "41-57%", 5: "41-57%"}

    if score <= 1:
        risk = RiskLevel.LOW
        interpretation = f"CURB-65 = {score}: Low risk (mortality ~{mortality_rates[score]})"
        recommendations = ["Outpatient treatment likely appropriate", "Oral antibiotics", "Close follow-up"]
    elif score == 2:
        risk = RiskLevel.MODERATE
        interpretation = f"CURB-65 = {score}: Moderate risk (mortality ~{mortality_rates[score]})"
        recommendations = ["Hospital admission recommended", "IV antibiotics initially", "Oxygen as needed"]
    else:
        risk = RiskLevel.HIGH
        interpretation = f"CURB-65 = {score}: High risk (mortality ~{mortality_rates[score]})"
        recommendations = ["Inpatient treatment required", "Consider ICU admission", "Broad-spectrum IV antibiotics", "Monitor for sepsis"]

    return CalculatorResult(
        calculator_id="curb65",
        calculator_name="CURB-65 Score",
        score=score,
        score_unit="points",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Lim WS, et al. Thorax 2003;58:377-382"],
        formula_used="Sum of: Confusion, BUN >19, RR ≥30, low BP, Age ≥65"
    )


def calculate_perc(input_data: PERCInput) -> CalculatorResult:
    """Calculate PERC Rule for PE rule-out.

    Reference: Kline JA, et al. J Thromb Haemost 2004
    """
    criteria_met = sum([
        input_data.age_under_50,
        input_data.heart_rate_under_100,
        input_data.spo2_over_94,
        input_data.no_leg_swelling,
        input_data.no_hemoptysis,
        input_data.no_recent_surgery,
        input_data.no_prior_pe_dvt,
        input_data.no_hormone_use,
    ])

    components = {
        "age_under_50": input_data.age_under_50,
        "heart_rate_under_100": input_data.heart_rate_under_100,
        "spo2_over_94": input_data.spo2_over_94,
        "no_leg_swelling": input_data.no_leg_swelling,
        "no_hemoptysis": input_data.no_hemoptysis,
        "no_recent_surgery": input_data.no_recent_surgery,
        "no_prior_pe_dvt": input_data.no_prior_pe_dvt,
        "no_hormone_use": input_data.no_hormone_use,
        "criteria_met": criteria_met,
    }

    all_criteria_met = criteria_met == 8

    if all_criteria_met:
        risk = RiskLevel.LOW
        score = 0
        interpretation = "PERC negative - PE can be excluded without D-dimer"
        recommendations = ["In low pretest probability patients, no further workup needed", "PE risk <2%", "Consider alternative diagnoses"]
    else:
        risk = RiskLevel.MODERATE
        score = 8 - criteria_met
        interpretation = f"PERC positive - {score} criteria not met"
        recommendations = ["Cannot rule out PE by PERC alone", "Proceed with D-dimer testing", "If D-dimer positive, CT pulmonary angiography"]

    return CalculatorResult(
        calculator_id="perc",
        calculator_name="PERC Rule",
        score=score,
        score_unit="criteria failed",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Kline JA, et al. J Thromb Haemost 2004", "Ann Emerg Med 2008"],
        formula_used="All 8 criteria must be met to rule out PE"
    )


def calculate_timi(input_data: TIMIInput) -> CalculatorResult:
    """Calculate TIMI Risk Score for UA/NSTEMI.

    Reference: Antman EM, et al. JAMA 2000
    """
    score = 0
    components = {}

    if input_data.age_65_or_older:
        score += 1
        components["age_65_or_older"] = 1
    if input_data.cad_risk_factors_3_plus:
        score += 1
        components["cad_risk_factors_3_plus"] = 1
    if input_data.known_cad:
        score += 1
        components["known_cad"] = 1
    if input_data.aspirin_use_7_days:
        score += 1
        components["aspirin_use_7_days"] = 1
    if input_data.severe_angina_24h:
        score += 1
        components["severe_angina_24h"] = 1
    if input_data.st_deviation:
        score += 1
        components["st_deviation"] = 1
    if input_data.elevated_troponin:
        score += 1
        components["elevated_troponin"] = 1

    risk_rates = {0: "4.7%", 1: "4.7%", 2: "8.3%", 3: "13.2%", 4: "19.9%", 5: "26.2%", 6: "40.9%", 7: "40.9%"}

    if score <= 2:
        risk = RiskLevel.LOW
        interpretation = f"TIMI {score}: Low risk (14-day event rate: {risk_rates.get(score, '40.9%')})"
        recommendations = ["May be suitable for early non-invasive evaluation", "Medical management with close follow-up"]
    elif score <= 4:
        risk = RiskLevel.MODERATE
        interpretation = f"TIMI {score}: Intermediate risk (14-day event rate: {risk_rates.get(score, '40.9%')})"
        recommendations = ["Admission recommended", "Consider early invasive strategy", "Dual antiplatelet therapy", "Cardiology consultation"]
    else:
        risk = RiskLevel.HIGH
        interpretation = f"TIMI {score}: High risk (14-day event rate: {risk_rates.get(score, '40.9%')})"
        recommendations = ["Early invasive strategy recommended (<24h)", "Dual antiplatelet therapy", "Anticoagulation", "Urgent cardiology consultation"]

    return CalculatorResult(
        calculator_id="timi",
        calculator_name="TIMI Risk Score (UA/NSTEMI)",
        score=score,
        score_unit="points",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Antman EM, et al. JAMA 2000;284:835-842"],
        formula_used="Sum of 7 risk factors"
    )


def calculate_sirs(input_data: SIRSInput) -> CalculatorResult:
    """Calculate SIRS Criteria.

    Reference: Bone RC, et al. Chest 1992
    """
    criteria_met = 0
    components = {}

    # Temperature: >38°C or <36°C
    if input_data.temperature > 38 or input_data.temperature < 36:
        criteria_met += 1
        components["temperature_abnormal"] = 1
    else:
        components["temperature_normal"] = 0

    # Heart rate: >90 bpm
    if input_data.heart_rate > 90:
        criteria_met += 1
        components["heart_rate_over_90"] = 1
    else:
        components["heart_rate_normal"] = 0

    # Respiratory: RR >20 or PaCO2 <32 mmHg
    if input_data.respiratory_rate > 20 or (input_data.paco2 and input_data.paco2 < 32):
        criteria_met += 1
        components["respiratory_abnormal"] = 1
    else:
        components["respiratory_normal"] = 0

    # WBC: >12,000 or <4,000 or >10% bands
    if input_data.wbc is not None:
        if input_data.wbc > 12 or input_data.wbc < 4 or (input_data.bands and input_data.bands > 10):
            criteria_met += 1
            components["wbc_abnormal"] = 1
        else:
            components["wbc_normal"] = 0

    components["criteria_met"] = criteria_met

    if criteria_met >= 2:
        risk = RiskLevel.MODERATE
        interpretation = f"SIRS positive ({criteria_met}/4 criteria met)"
        recommendations = ["SIRS criteria met - evaluate for infection source", "Consider sepsis workup", "Early antibiotics if infection suspected"]
    else:
        risk = RiskLevel.LOW
        interpretation = f"SIRS negative ({criteria_met}/4 criteria met)"
        recommendations = ["SIRS criteria not met", "Continue monitoring vital signs"]

    return CalculatorResult(
        calculator_id="sirs",
        calculator_name="SIRS Criteria",
        score=criteria_met,
        score_unit="criteria",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Bone RC, et al. Chest 1992;101:1644-1655"],
        formula_used="≥2 of: Temp, HR, RR/PaCO2, WBC"
    )


def calculate_abcd2(input_data: ABCD2Input) -> CalculatorResult:
    """Calculate ABCD2 Score for stroke risk after TIA.

    Reference: Johnston SC, et al. Lancet 2007
    """
    score = 0
    components = {}

    if input_data.age_60_or_older:
        score += 1
        components["age_60_or_older"] = 1
    if input_data.bp_140_90_or_higher:
        score += 1
        components["bp_elevated"] = 1
    if input_data.clinical_weakness:
        score += 2
        components["weakness"] = 2
    elif input_data.clinical_speech_only:
        score += 1
        components["speech_impairment"] = 1
    if input_data.duration_60_plus_min:
        score += 2
        components["duration_60_plus"] = 2
    elif input_data.duration_10_59_min:
        score += 1
        components["duration_10_59"] = 1
    if input_data.diabetes:
        score += 1
        components["diabetes"] = 1

    if score <= 3:
        risk = RiskLevel.LOW
        interpretation = f"ABCD2 {score}: Low risk (2-day stroke risk ~1%)"
        recommendations = ["May be appropriate for outpatient workup", "Complete workup within 48-72 hours", "Aspirin 325mg immediately"]
    elif score <= 5:
        risk = RiskLevel.MODERATE
        interpretation = f"ABCD2 {score}: Moderate risk (2-day stroke risk ~4%)"
        recommendations = ["Consider hospital admission", "Expedited workup recommended", "Brain MRI and carotid imaging", "DAPT for 21 days"]
    else:
        risk = RiskLevel.HIGH
        interpretation = f"ABCD2 {score}: High risk (2-day stroke risk ~8%)"
        recommendations = ["Hospital admission recommended", "Urgent neurology consultation", "Immediate brain and vascular imaging", "DAPT (aspirin + clopidogrel)"]

    return CalculatorResult(
        calculator_id="abcd2",
        calculator_name="ABCD2 Score",
        score=score,
        score_unit="points",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Johnston SC, et al. Lancet 2007;369:283-292"],
        formula_used="Age + BP + Clinical + Duration + Diabetes"
    )


def calculate_centor(input_data: CentorInput) -> CalculatorResult:
    """Calculate Modified Centor Score for strep pharyngitis.

    Reference: McIsaac WJ, et al. CMAJ 1998
    """
    score = 0
    components = {}

    if input_data.tonsillar_exudates:
        score += 1
        components["tonsillar_exudates"] = 1
    if input_data.tender_nodes:
        score += 1
        components["tender_nodes"] = 1
    if input_data.fever:
        score += 1
        components["fever"] = 1
    if input_data.no_cough:
        score += 1
        components["no_cough"] = 1

    # Age adjustment
    if input_data.age_3_14:
        score += 1
        components["age_3_14"] = 1
    elif input_data.age_45_plus:
        score -= 1
        components["age_45_plus"] = -1

    probabilities = {-1: "1-2.5%", 0: "1-2.5%", 1: "5-10%", 2: "11-17%", 3: "28-35%", 4: "51-53%", 5: "51-53%"}

    if score <= 1:
        risk = RiskLevel.LOW
        interpretation = f"Modified Centor {score}: Low strep probability ({probabilities.get(score, '51-53%')})"
        recommendations = ["No testing or antibiotics recommended", "Symptomatic treatment", "Likely viral pharyngitis"]
    elif score <= 3:
        risk = RiskLevel.MODERATE
        interpretation = f"Modified Centor {score}: Intermediate probability ({probabilities.get(score, '51-53%')})"
        recommendations = ["Rapid strep test recommended", "Throat culture if rapid test negative", "Treat only if test positive"]
    else:
        risk = RiskLevel.MODERATE_HIGH
        interpretation = f"Modified Centor {score}: High strep probability ({probabilities.get(score, '51-53%')})"
        recommendations = ["Consider empiric antibiotics or rapid strep test", "Penicillin V or amoxicillin first-line"]

    return CalculatorResult(
        calculator_id="centor",
        calculator_name="Modified Centor Score",
        score=score,
        score_unit="points",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["McIsaac WJ, et al. CMAJ 1998;158:75-83"],
        formula_used="Exudates + Adenopathy + Fever + No cough ± Age"
    )


def calculate_map(input_data: MAPInput) -> CalculatorResult:
    """Calculate Mean Arterial Pressure.

    Formula: MAP = (SBP + 2×DBP) / 3
    """
    map_value = (input_data.systolic_bp + 2 * input_data.diastolic_bp) / 3

    components = {
        "systolic_bp": input_data.systolic_bp,
        "diastolic_bp": input_data.diastolic_bp,
    }

    if map_value < 60:
        risk = RiskLevel.VERY_HIGH
        interpretation = f"MAP {map_value:.0f}: Hypotension/Shock - inadequate organ perfusion"
        recommendations = ["Immediate fluid resuscitation", "Consider vasopressors (target MAP ≥65)", "ICU admission likely needed"]
    elif map_value < 70:
        risk = RiskLevel.HIGH
        interpretation = f"MAP {map_value:.0f}: Low (borderline perfusion)"
        recommendations = ["MAP borderline for organ perfusion", "Monitor closely", "IV fluids if hypovolemic"]
    elif map_value > 130:
        risk = RiskLevel.HIGH
        interpretation = f"MAP {map_value:.0f}: Severely elevated"
        recommendations = ["Evaluate for hypertensive emergency", "Check for end-organ damage", "May need IV antihypertensives"]
    else:
        risk = RiskLevel.LOW
        interpretation = f"MAP {map_value:.0f}: Normal range"
        recommendations = ["MAP within normal limits (70-100 mmHg)"]

    return CalculatorResult(
        calculator_id="map",
        calculator_name="Mean Arterial Pressure",
        score=round(map_value, 0),
        score_unit="mmHg",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Standard hemodynamic calculation"],
        formula_used="MAP = (SBP + 2×DBP) / 3"
    )


def calculate_corrected_sodium(input_data: CorrectedSodiumInput) -> CalculatorResult:
    """Calculate Corrected Sodium for hyperglycemia.

    Formula: Na + 2.4 × [(Glucose - 100) / 100]
    Reference: Hillier TA, et al. Am J Med 1999
    """
    correction = 2.4 * ((input_data.glucose - 100) / 100)
    corrected_na = input_data.measured_sodium + correction

    components = {
        "measured_sodium": input_data.measured_sodium,
        "glucose": input_data.glucose,
        "correction_factor": round(correction, 1),
    }

    if corrected_na < 135:
        risk = RiskLevel.MODERATE
        interpretation = f"Corrected Na {corrected_na:.1f}: True hyponatremia persists"
        recommendations = ["True hyponatremia present", "Evaluate volume status", "Check serum osmolality"]
    elif corrected_na > 145:
        risk = RiskLevel.MODERATE
        interpretation = f"Corrected Na {corrected_na:.1f}: True hypernatremia revealed"
        recommendations = ["True hypernatremia present", "Free water replacement needed", "Monitor Na correction rate"]
    else:
        risk = RiskLevel.LOW
        interpretation = f"Corrected Na {corrected_na:.1f}: Normal range"
        recommendations = ["Sodium will normalize with glucose treatment", "Dilutional hyponatremia from hyperglycemia"]

    return CalculatorResult(
        calculator_id="corrected_sodium",
        calculator_name="Corrected Sodium",
        score=round(corrected_na, 1),
        score_unit="mEq/L",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Hillier TA, et al. Am J Med 1999"],
        formula_used="Corrected Na = Measured Na + 2.4 × [(Glucose - 100) / 100]"
    )


def calculate_osmolality(input_data: OsmolalityInput) -> CalculatorResult:
    """Calculate Serum Osmolality and Osmolar Gap.

    Formula: Calculated Osm = 2×Na + Glucose/18 + BUN/2.8
    """
    calc_osm = 2 * input_data.sodium + input_data.glucose / 18 + input_data.bun / 2.8

    components = {
        "sodium_contribution": round(2 * input_data.sodium, 1),
        "glucose_contribution": round(input_data.glucose / 18, 1),
        "bun_contribution": round(input_data.bun / 2.8, 1),
        "calculated_osmolality": round(calc_osm, 1),
    }

    osm_gap = None
    if input_data.measured_osmolality:
        osm_gap = input_data.measured_osmolality - calc_osm
        components["measured_osmolality"] = input_data.measured_osmolality
        components["osmolar_gap"] = round(osm_gap, 1)

    if osm_gap and osm_gap > 10:
        risk = RiskLevel.HIGH
        interpretation = f"Calculated Osm {calc_osm:.0f}, Gap {osm_gap:.0f} (elevated)"
        recommendations = ["Elevated osmolar gap - consider toxic alcohols", "Check for methanol, ethylene glycol", "Urgent toxicology workup"]
    elif calc_osm > 320:
        risk = RiskLevel.HIGH
        interpretation = f"Calculated Osm {calc_osm:.0f}: Hyperosmolar"
        recommendations = ["Hyperosmolar state", "Evaluate for HHS, DKA", "Careful fluid management"]
    else:
        risk = RiskLevel.LOW
        interpretation = f"Calculated Osm {calc_osm:.0f}: Normal range"
        recommendations = ["Serum osmolality within normal limits"]

    return CalculatorResult(
        calculator_id="osmolality",
        calculator_name="Serum Osmolality",
        score=round(calc_osm, 0),
        score_unit="mOsm/kg",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Purssell RA, et al. Ann Emerg Med 2001"],
        formula_used="Osm = 2×Na + Glucose/18 + BUN/2.8"
    )


def calculate_bisap(input_data: BISAPInput) -> CalculatorResult:
    """Calculate BISAP Score for acute pancreatitis.

    Reference: Wu BU, et al. Gut 2008
    """
    score = 0
    components = {}

    if input_data.bun_over_25:
        score += 1
        components["bun_over_25"] = 1
    if input_data.impaired_mental_status:
        score += 1
        components["impaired_mental_status"] = 1
    if input_data.sirs_2_or_more:
        score += 1
        components["sirs_2_or_more"] = 1
    if input_data.age_over_60:
        score += 1
        components["age_over_60"] = 1
    if input_data.pleural_effusion:
        score += 1
        components["pleural_effusion"] = 1

    mortality_rates = {0: "<1%", 1: "~1%", 2: "2%", 3: "5-8%", 4: "12-20%", 5: ">20%"}

    if score <= 2:
        risk = RiskLevel.LOW
        interpretation = f"BISAP {score}: Low risk (mortality {mortality_rates.get(score, '>20%')})"
        recommendations = ["Low risk for in-hospital mortality", "Conservative management", "Monitor for clinical deterioration"]
    else:
        risk = RiskLevel.HIGH
        interpretation = f"BISAP {score}: High risk (mortality {mortality_rates.get(score, '>20%')})"
        recommendations = ["Higher risk for severe pancreatitis", "Consider ICU admission", "Aggressive fluid resuscitation", "Early CT if necrotizing pancreatitis suspected"]

    return CalculatorResult(
        calculator_id="bisap",
        calculator_name="BISAP Score",
        score=score,
        score_unit="points",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Wu BU, et al. Gut 2008;57:1698-1703"],
        formula_used="BUN + Impaired mental status + SIRS + Age + Pleural effusion"
    )


# =============================================================================
# Calculator Service Class
# =============================================================================

class ClinicalCalculatorService:
    """Service for comprehensive clinical calculations.

    Provides validated clinical calculators organized by category:
    - Cardiovascular: ASCVD, Framingham, HEART, CHA2DS2-VASc, HAS-BLED
    - Renal: CKD-EPI eGFR, Cockcroft-Gault, UACR
    - Hepatic: MELD, Child-Pugh, FIB-4
    - Critical Care: SOFA, qSOFA, Wells PE/DVT
    - General: BMI, BSA, Corrected Calcium, Anion Gap
    """

    CALCULATORS: dict[str, dict[str, Any]] = {
        "bmi": {
            "name": "Body Mass Index (BMI)",
            "short_name": "BMI",
            "category": CalculatorCategory.GENERAL,
            "description": "Calculate body mass index for obesity classification",
            "function": calculate_bmi,
            "input_class": BMIInput,
        },
        "bsa": {
            "name": "Body Surface Area (BSA)",
            "short_name": "BSA",
            "category": CalculatorCategory.GENERAL,
            "description": "Calculate body surface area using Du Bois formula",
            "function": calculate_bsa,
            "input_class": BSAInput,
        },
        "ascvd": {
            "name": "ASCVD 10-Year Risk",
            "short_name": "ASCVD",
            "category": CalculatorCategory.CARDIOVASCULAR,
            "description": "10-year atherosclerotic cardiovascular disease risk using Pooled Cohort Equations",
            "function": calculate_ascvd,
            "input_class": ASCVDInput,
        },
        "framingham": {
            "name": "Framingham Risk Score",
            "short_name": "Framingham",
            "category": CalculatorCategory.CARDIOVASCULAR,
            "description": "10-year cardiovascular disease risk",
            "function": None,  # Use existing implementation
            "input_class": FraminghamInput,
        },
        "heart": {
            "name": "HEART Score",
            "short_name": "HEART",
            "category": CalculatorCategory.CARDIOVASCULAR,
            "description": "Major adverse cardiac event risk for chest pain patients",
            "function": calculate_heart_score,
            "input_class": HEARTInput,
        },
        "cha2ds2_vasc": {
            "name": "CHA2DS2-VASc Score",
            "short_name": "CHA2DS2-VASc",
            "category": CalculatorCategory.CARDIOVASCULAR,
            "description": "Stroke risk in atrial fibrillation",
            "function": calculate_cha2ds2_vasc,
            "input_class": CHA2DS2VAScInput,
        },
        "has_bled": {
            "name": "HAS-BLED Score",
            "short_name": "HAS-BLED",
            "category": CalculatorCategory.CARDIOVASCULAR,
            "description": "Bleeding risk on anticoagulation",
            "function": calculate_has_bled,
            "input_class": HASBLEDInput,
        },
        "egfr_ckdepi": {
            "name": "CKD-EPI eGFR (2021)",
            "short_name": "eGFR",
            "category": CalculatorCategory.RENAL,
            "description": "Estimated glomerular filtration rate using race-free CKD-EPI 2021 equation",
            "function": calculate_egfr_ckdepi,
            "input_class": EGFRInput,
        },
        "cockcroft_gault": {
            "name": "Creatinine Clearance (Cockcroft-Gault)",
            "short_name": "CrCl",
            "category": CalculatorCategory.RENAL,
            "description": "Creatinine clearance for medication dosing",
            "function": calculate_cockcroft_gault,
            "input_class": CockcroftGaultInput,
        },
        "uacr": {
            "name": "UACR Interpretation",
            "short_name": "UACR",
            "category": CalculatorCategory.RENAL,
            "description": "Urine albumin-to-creatinine ratio interpretation",
            "function": calculate_uacr,
            "input_class": UACRInput,
        },
        "meld": {
            "name": "MELD/MELD-Na Score",
            "short_name": "MELD",
            "category": CalculatorCategory.HEPATIC,
            "description": "Liver disease severity for transplant prioritization",
            "function": calculate_meld,
            "input_class": MELDInput,
        },
        "child_pugh": {
            "name": "Child-Pugh Score",
            "short_name": "Child-Pugh",
            "category": CalculatorCategory.HEPATIC,
            "description": "Cirrhosis severity classification",
            "function": calculate_child_pugh,
            "input_class": ChildPughInput,
        },
        "fib4": {
            "name": "FIB-4 Score",
            "short_name": "FIB-4",
            "category": CalculatorCategory.HEPATIC,
            "description": "Liver fibrosis risk assessment",
            "function": calculate_fib4,
            "input_class": FIB4Input,
        },
        "sofa": {
            "name": "SOFA Score",
            "short_name": "SOFA",
            "category": CalculatorCategory.CRITICAL_CARE,
            "description": "Sequential organ failure assessment",
            "function": calculate_sofa,
            "input_class": SOFAInput,
        },
        "qsofa": {
            "name": "qSOFA Score",
            "short_name": "qSOFA",
            "category": CalculatorCategory.CRITICAL_CARE,
            "description": "Quick sepsis screening",
            "function": calculate_qsofa,
            "input_class": QSOFAInput,
        },
        "wells_pe": {
            "name": "Wells Score for PE",
            "short_name": "Wells PE",
            "category": CalculatorCategory.CRITICAL_CARE,
            "description": "Pulmonary embolism probability",
            "function": calculate_wells_pe,
            "input_class": WellsPEInput,
        },
        "wells_dvt": {
            "name": "Wells Score for DVT",
            "short_name": "Wells DVT",
            "category": CalculatorCategory.CRITICAL_CARE,
            "description": "Deep vein thrombosis probability",
            "function": calculate_wells_dvt,
            "input_class": WellsDVTInput,
        },
        "corrected_calcium": {
            "name": "Corrected Calcium",
            "short_name": "Corr Ca",
            "category": CalculatorCategory.LABORATORY,
            "description": "Albumin-corrected calcium level",
            "function": calculate_corrected_calcium,
            "input_class": CorrectedCalciumInput,
        },
        "anion_gap": {
            "name": "Anion Gap",
            "short_name": "AG",
            "category": CalculatorCategory.LABORATORY,
            "description": "Serum anion gap calculation",
            "function": calculate_anion_gap,
            "input_class": AnionGapInput,
        },
        # Additional Critical Care / Emergency
        "gcs": {
            "name": "Glasgow Coma Scale",
            "short_name": "GCS",
            "category": CalculatorCategory.CRITICAL_CARE,
            "description": "Neurological assessment for consciousness level",
            "function": calculate_gcs,
            "input_class": GCSInput,
        },
        "news2": {
            "name": "NEWS2 (National Early Warning Score 2)",
            "short_name": "NEWS2",
            "category": CalculatorCategory.CRITICAL_CARE,
            "description": "Clinical deterioration risk assessment",
            "function": calculate_news2,
            "input_class": NEWS2Input,
        },
        "curb65": {
            "name": "CURB-65 Score",
            "short_name": "CURB-65",
            "category": CalculatorCategory.CRITICAL_CARE,
            "description": "Pneumonia severity and mortality prediction",
            "function": calculate_curb65,
            "input_class": CURB65Input,
        },
        "perc": {
            "name": "PERC Rule",
            "short_name": "PERC",
            "category": CalculatorCategory.CRITICAL_CARE,
            "description": "PE rule-out criteria for low-risk patients",
            "function": calculate_perc,
            "input_class": PERCInput,
        },
        "sirs": {
            "name": "SIRS Criteria",
            "short_name": "SIRS",
            "category": CalculatorCategory.CRITICAL_CARE,
            "description": "Systemic inflammatory response syndrome",
            "function": calculate_sirs,
            "input_class": SIRSInput,
        },
        # Cardiovascular
        "timi": {
            "name": "TIMI Risk Score (UA/NSTEMI)",
            "short_name": "TIMI",
            "category": CalculatorCategory.CARDIOVASCULAR,
            "description": "14-day adverse outcome risk in ACS",
            "function": calculate_timi,
            "input_class": TIMIInput,
        },
        "abcd2": {
            "name": "ABCD2 Score",
            "short_name": "ABCD2",
            "category": CalculatorCategory.CARDIOVASCULAR,
            "description": "Stroke risk after TIA",
            "function": calculate_abcd2,
            "input_class": ABCD2Input,
        },
        "map": {
            "name": "Mean Arterial Pressure",
            "short_name": "MAP",
            "category": CalculatorCategory.CARDIOVASCULAR,
            "description": "Calculate MAP from blood pressure",
            "function": calculate_map,
            "input_class": MAPInput,
        },
        # Infectious Disease
        "centor": {
            "name": "Modified Centor Score",
            "short_name": "Centor",
            "category": CalculatorCategory.GENERAL,
            "description": "Strep pharyngitis probability",
            "function": calculate_centor,
            "input_class": CentorInput,
        },
        # Laboratory
        "corrected_sodium": {
            "name": "Corrected Sodium",
            "short_name": "Corr Na",
            "category": CalculatorCategory.LABORATORY,
            "description": "Sodium correction for hyperglycemia",
            "function": calculate_corrected_sodium,
            "input_class": CorrectedSodiumInput,
        },
        "osmolality": {
            "name": "Serum Osmolality",
            "short_name": "Osm",
            "category": CalculatorCategory.LABORATORY,
            "description": "Calculated osmolality and osmolar gap",
            "function": calculate_osmolality,
            "input_class": OsmolalityInput,
        },
        # GI/Hepatic
        "bisap": {
            "name": "BISAP Score",
            "short_name": "BISAP",
            "category": CalculatorCategory.HEPATIC,
            "description": "Acute pancreatitis mortality prediction",
            "function": calculate_bisap,
            "input_class": BISAPInput,
        },
    }

    def __init__(self) -> None:
        """Initialize the calculator service."""
        self._favorites: dict[str, set[str]] = {}  # user_id -> set of calculator_ids
        logger.info(f"ClinicalCalculatorService initialized with {len(self.CALCULATORS)} calculators")

    def list_calculators(self, category: str | None = None) -> list[dict[str, Any]]:
        """List all available calculators.

        Args:
            category: Optional category filter.

        Returns:
            List of calculator summaries.
        """
        result = []
        for calc_id, calc_def in self.CALCULATORS.items():
            if category and calc_def["category"].value != category:
                continue
            result.append({
                "id": calc_id,
                "name": calc_def["name"],
                "short_name": calc_def["short_name"],
                "category": calc_def["category"].value,
                "description": calc_def["description"],
            })
        return result

    def get_calculator(self, calculator_id: str) -> dict[str, Any] | None:
        """Get calculator definition with input schema.

        Args:
            calculator_id: Calculator identifier.

        Returns:
            Calculator definition or None.
        """
        calc_def = self.CALCULATORS.get(calculator_id)
        if not calc_def:
            return None

        input_class = calc_def["input_class"]
        schema = input_class.model_json_schema()

        return {
            "id": calculator_id,
            "name": calc_def["name"],
            "short_name": calc_def["short_name"],
            "category": calc_def["category"].value,
            "description": calc_def["description"],
            "inputs": schema.get("properties", {}),
            "required": schema.get("required", []),
        }

    def calculate(self, calculator_id: str, inputs: dict[str, Any]) -> CalculatorResult:
        """Execute a calculator.

        Args:
            calculator_id: Calculator identifier.
            inputs: Input values.

        Returns:
            CalculatorResult.

        Raises:
            ValueError: If calculator not found or inputs invalid.
        """
        calc_def = self.CALCULATORS.get(calculator_id)
        if not calc_def:
            raise ValueError(f"Calculator not found: {calculator_id}")

        if not calc_def["function"]:
            raise ValueError(f"Calculator not implemented: {calculator_id}")

        # Validate inputs using Pydantic
        input_class = calc_def["input_class"]
        try:
            validated_input = input_class(**inputs)
        except Exception as e:
            raise ValueError(f"Invalid input: {e}")

        # Execute calculator
        return calc_def["function"](validated_input)

    def get_favorites(self, user_id: str) -> list[dict[str, Any]]:
        """Get user's favorite calculators.

        Args:
            user_id: User identifier.

        Returns:
            List of favorite calculator summaries.
        """
        favorite_ids = self._favorites.get(user_id, set())
        return [
            calc for calc in self.list_calculators()
            if calc["id"] in favorite_ids
        ]

    def toggle_favorite(self, user_id: str, calculator_id: str) -> bool:
        """Toggle calculator favorite status.

        Args:
            user_id: User identifier.
            calculator_id: Calculator identifier.

        Returns:
            True if now favorited, False if unfavorited.
        """
        if calculator_id not in self.CALCULATORS:
            raise ValueError(f"Calculator not found: {calculator_id}")

        if user_id not in self._favorites:
            self._favorites[user_id] = set()

        if calculator_id in self._favorites[user_id]:
            self._favorites[user_id].discard(calculator_id)
            return False
        else:
            self._favorites[user_id].add(calculator_id)
            return True

    def get_categories(self) -> list[dict[str, Any]]:
        """Get all calculator categories.

        Returns:
            List of categories with counts.
        """
        category_counts: dict[str, int] = {}
        for calc_def in self.CALCULATORS.values():
            cat = calc_def["category"].value
            category_counts[cat] = category_counts.get(cat, 0) + 1

        return [
            {"id": cat, "name": cat.replace("_", " ").title(), "count": count}
            for cat, count in category_counts.items()
        ]

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics.

        Returns:
            Dictionary with service statistics.
        """
        category_counts = {}
        for calc_def in self.CALCULATORS.values():
            cat = calc_def["category"].value
            category_counts[cat] = category_counts.get(cat, 0) + 1

        return {
            "total_calculators": len(self.CALCULATORS),
            "categories": list(category_counts.keys()),
            "category_counts": category_counts,
            "total_users_with_favorites": len(self._favorites),
        }


# Singleton instance
_clinical_calculator_service: ClinicalCalculatorService | None = None
_clinical_calculator_lock = Lock()


def get_clinical_calculator_service() -> ClinicalCalculatorService:
    """Get the singleton ClinicalCalculatorService instance."""
    global _clinical_calculator_service

    if _clinical_calculator_service is None:
        with _clinical_calculator_lock:
            if _clinical_calculator_service is None:
                logger.info("Creating singleton ClinicalCalculatorService instance")
                _clinical_calculator_service = ClinicalCalculatorService()

    return _clinical_calculator_service


def reset_clinical_calculator_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _clinical_calculator_service
    with _clinical_calculator_lock:
        _clinical_calculator_service = None
