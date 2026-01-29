"""Clinical Risk Calculators Service.

Provides validated clinical risk scoring calculators for common
medical conditions and decision support.

This module is being migrated to a data-driven approach using
calculator_definitions.py. CRITERIA-type calculators can now use
the generic calculate_from_definition() function instead of
individual implementations.
"""

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any

from app.services.calculator_definitions import (
    CALCULATOR_DEFINITIONS,
    CalculatorType,
    calculate_point_based_score,
    get_calculator_definition,
)
from app.services.calculator_definitions import (
    RiskLevel as DDRiskLevel,
)

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """Risk stratification levels."""

    LOW = "low"
    LOW_MODERATE = "low_moderate"
    MODERATE = "moderate"
    MODERATE_HIGH = "moderate_high"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass
class CalculatorResult:
    """Result from a clinical calculator."""

    calculator_name: str
    score: float
    score_unit: str
    risk_level: RiskLevel
    interpretation: str
    recommendations: list[str]
    components: dict[str, Any] = field(default_factory=dict)
    references: list[str] = field(default_factory=list)


# ============================================================================
# Data-Driven Calculator Bridge
# ============================================================================

def calculate_from_definition(
    calculator_id: str,
    values: dict[str, bool | int | float],
    age: int | None = None,
) -> CalculatorResult:
    """Calculate using data-driven definition from calculator_definitions.py.

    This function provides a bridge to the data-driven calculator definitions,
    enabling CRITERIA-type calculators to use the generic point-based scoring
    engine instead of individual function implementations.

    Args:
        calculator_id: Calculator ID from CALCULATOR_DEFINITIONS.
        values: Dict mapping criterion names to values (bool, int, or float).
        age: Patient age (for calculators with age-based scoring).

    Returns:
        CalculatorResult with score and interpretation.

    Raises:
        ValueError: If calculator not found or not a CRITERIA type.

    Example:
        >>> result = calculate_from_definition(
        ...     "chadsvasc",
        ...     {"hypertension": True, "diabetes": True, "female": True},
        ...     age=72
        ... )
        >>> result.score  # 5 (HTN + DM + female + age 65-74)
    """
    definition = get_calculator_definition(calculator_id)
    if definition is None:
        raise ValueError(f"Data-driven calculator not found: {calculator_id}")

    if definition.calc_type != CalculatorType.CRITERIA:
        raise ValueError(
            f"Calculator {calculator_id} is type {definition.calc_type.value}. "
            f"Use the specific formula function instead."
        )

    # Use the generic point-based calculation
    dd_result = calculate_point_based_score(definition, values, age)

    # Convert to this module's CalculatorResult format
    return CalculatorResult(
        calculator_name=dd_result.calculator_name,
        score=dd_result.score,
        score_unit=dd_result.score_unit,
        risk_level=RiskLevel(dd_result.risk_level.value),
        interpretation=dd_result.interpretation,
        recommendations=dd_result.recommendations,
        components=dd_result.components,
        references=dd_result.references,
    )


def get_data_driven_calculators() -> list[str]:
    """Get list of calculator IDs available via data-driven definitions.

    Returns:
        List of calculator IDs that can be used with calculate_from_definition().
    """
    return [
        calc_id for calc_id, defn in CALCULATOR_DEFINITIONS.items()
        if defn.calc_type == CalculatorType.CRITERIA
    ]


# ============================================================================
# BMI Calculator
# ============================================================================

def calculate_bmi(
    weight_kg: float,
    height_cm: float,
) -> CalculatorResult:
    """Calculate Body Mass Index (BMI).

    Args:
        weight_kg: Weight in kilograms.
        height_cm: Height in centimeters.

    Returns:
        CalculatorResult with BMI classification.
    """
    height_m = height_cm / 100
    bmi = weight_kg / (height_m ** 2)

    if bmi < 18.5:
        risk = RiskLevel.MODERATE
        interpretation = "Underweight"
        recommendations = [
            "Evaluate for malnutrition or underlying disease",
            "Consider nutritional supplementation",
            "Monitor weight trend",
        ]
    elif bmi < 25:
        risk = RiskLevel.LOW
        interpretation = "Normal weight"
        recommendations = [
            "Maintain current healthy lifestyle",
            "Continue regular physical activity",
        ]
    elif bmi < 30:
        risk = RiskLevel.MODERATE
        interpretation = "Overweight"
        recommendations = [
            "Lifestyle modifications: diet and exercise",
            "Screen for metabolic syndrome",
            "Monitor blood pressure and lipids",
        ]
    elif bmi < 35:
        risk = RiskLevel.HIGH
        interpretation = "Class I Obesity"
        recommendations = [
            "Intensive lifestyle intervention",
            "Screen for obesity-related comorbidities",
            "Consider pharmacotherapy if lifestyle fails",
        ]
    elif bmi < 40:
        risk = RiskLevel.HIGH
        interpretation = "Class II Obesity"
        recommendations = [
            "Intensive lifestyle intervention",
            "Consider pharmacotherapy",
            "Evaluate for bariatric surgery eligibility",
        ]
    else:
        risk = RiskLevel.VERY_HIGH
        interpretation = "Class III Obesity (Morbid)"
        recommendations = [
            "Bariatric surgery evaluation recommended",
            "Intensive medical management",
            "Screen for obesity-related comorbidities",
        ]

    return CalculatorResult(
        calculator_name="Body Mass Index (BMI)",
        score=round(bmi, 1),
        score_unit="kg/m²",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components={"weight_kg": weight_kg, "height_cm": height_cm},
        references=["WHO BMI Classification"],
    )


# ============================================================================
# CHADS₂-VASc Score (Atrial Fibrillation Stroke Risk)
# ============================================================================

def calculate_chadsvasc(
    age: int = 0,
    female: bool = False,
    congestive_heart_failure: bool = False,
    hypertension: bool = False,
    diabetes: bool = False,
    stroke_tia_thromboembolism: bool = False,
    vascular_disease: bool = False,
) -> CalculatorResult:
    """Calculate CHA₂DS₂-VASc score for stroke risk in atrial fibrillation.

    Uses data-driven definition from calculator_definitions.py.

    Args:
        age: Patient age in years.
        female: True if female sex.
        congestive_heart_failure: History of CHF.
        hypertension: History of hypertension.
        diabetes: History of diabetes mellitus.
        stroke_tia_thromboembolism: Prior stroke, TIA, or thromboembolism.
        vascular_disease: Prior MI, PAD, or aortic plaque.

    Returns:
        CalculatorResult with stroke risk assessment.
    """
    return calculate_from_definition(
        "chadsvasc",
        {
            "congestive_heart_failure": congestive_heart_failure,
            "hypertension": hypertension,
            "diabetes": diabetes,
            "stroke_tia_thromboembolism": stroke_tia_thromboembolism,
            "vascular_disease": vascular_disease,
            "female": female,
        },
        age=age,
    )


# ============================================================================
# HAS-BLED Score (Bleeding Risk)
# ============================================================================

def calculate_hasbled(
    hypertension: bool = False,
    renal_disease: bool = False,
    liver_disease: bool = False,
    stroke_history: bool = False,
    bleeding_history: bool = False,
    labile_inr: bool = False,
    age_over_65: bool = False,
    antiplatelet_nsaid: bool = False,
    alcohol_use: bool = False,
) -> CalculatorResult:
    """Calculate HAS-BLED score for major bleeding risk on anticoagulation.

    Uses data-driven definition from calculator_definitions.py.

    Args:
        hypertension: Uncontrolled SBP >160 mmHg.
        renal_disease: Dialysis, transplant, Cr >2.6 mg/dL.
        liver_disease: Cirrhosis or bilirubin >2x normal + ALT/AST >3x normal.
        stroke_history: Prior stroke.
        bleeding_history: Prior major bleeding or predisposition.
        labile_inr: Unstable/high INRs or <60% time in therapeutic range.
        age_over_65: Age over 65 years.
        antiplatelet_nsaid: Concomitant aspirin or NSAIDs.
        alcohol_use: ≥8 drinks/week.

    Returns:
        CalculatorResult with bleeding risk assessment.
    """
    return calculate_from_definition(
        "hasbled",
        {
            "hypertension": hypertension,
            "renal_disease": renal_disease,
            "liver_disease": liver_disease,
            "stroke_history": stroke_history,
            "bleeding_history": bleeding_history,
            "labile_inr": labile_inr,
            "age_over_65": age_over_65,
            "antiplatelet_nsaid": antiplatelet_nsaid,
            "alcohol_use": alcohol_use,
        },
    )


# ============================================================================
# MELD Score (Liver Disease Severity)
# ============================================================================

def calculate_meld(
    creatinine: float,
    bilirubin: float,
    inr: float,
    sodium: float | None = None,
    on_dialysis: bool = False,
) -> CalculatorResult:
    """Calculate MELD score for liver disease severity.

    Args:
        creatinine: Serum creatinine in mg/dL.
        bilirubin: Total bilirubin in mg/dL.
        inr: International Normalized Ratio.
        sodium: Serum sodium in mEq/L (for MELD-Na).
        on_dialysis: True if on dialysis (creatinine set to 4).

    Returns:
        CalculatorResult with liver disease severity.
    """
    # Apply bounds and dialysis adjustment
    cr = 4.0 if on_dialysis else max(1.0, min(creatinine, 4.0))
    bili = max(1.0, bilirubin)
    inr_val = max(1.0, inr)

    # MELD = 10 * (0.957 * ln(Cr) + 0.378 * ln(Bili) + 1.120 * ln(INR) + 0.643)
    meld = 10 * (
        0.957 * math.log(cr) +
        0.378 * math.log(bili) +
        1.120 * math.log(inr_val) +
        0.643
    )

    # MELD-Na calculation if sodium provided
    meld_na = None
    if sodium is not None:
        na = max(125, min(sodium, 137))
        meld_na = meld + 1.32 * (137 - na) - (0.033 * meld * (137 - na))
        meld_na = max(6, min(meld_na, 40))

    score = round(meld_na if meld_na else meld)
    score = max(6, min(score, 40))  # MELD bounded 6-40

    # Risk stratification
    if score < 10:
        risk = RiskLevel.LOW
        interpretation = "Low risk - 3-month mortality ~2%"
        recommendations = [
            "Continue medical management",
            "Monitor for disease progression",
        ]
    elif score < 20:
        risk = RiskLevel.MODERATE
        interpretation = "Moderate risk - 3-month mortality ~6-20%"
        recommendations = [
            "Consider liver transplant evaluation",
            "Optimize medical management",
            "Monitor closely for complications",
        ]
    elif score < 30:
        risk = RiskLevel.HIGH
        interpretation = "High risk - 3-month mortality ~50%"
        recommendations = [
            "Urgent liver transplant evaluation",
            "ICU monitoring may be needed",
            "Aggressive management of complications",
        ]
    else:
        risk = RiskLevel.VERY_HIGH
        interpretation = "Very high risk - 3-month mortality ~70-80%"
        recommendations = [
            "Emergent liver transplant consideration",
            "ICU care likely required",
            "Discuss goals of care",
        ]

    components = {
        "creatinine": creatinine,
        "bilirubin": bilirubin,
        "inr": inr,
        "on_dialysis": on_dialysis,
    }
    if sodium is not None:
        components["sodium"] = sodium
        components["meld_basic"] = round(meld)

    return CalculatorResult(
        calculator_name="MELD-Na Score" if sodium else "MELD Score",
        score=score,
        score_unit="points",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["UNOS MELD allocation policy"],
    )


# ============================================================================
# CKD-EPI eGFR Calculator
# ============================================================================

def calculate_egfr_ckdepi(
    creatinine: float,
    age: int,
    female: bool,
    black: bool = False,
) -> CalculatorResult:
    """Calculate eGFR using CKD-EPI equation (2021 race-free version).

    Args:
        creatinine: Serum creatinine in mg/dL.
        age: Patient age in years.
        female: True if female.
        black: Deprecated - included for API compatibility but not used.

    Returns:
        CalculatorResult with CKD staging.
    """
    # 2021 CKD-EPI equation (race-free)
    # eGFR = 142 × min(Scr/κ, 1)^α × max(Scr/κ, 1)^-1.200 × 0.9938^Age × (1.012 if female)

    kappa = 0.7 if female else 0.9
    alpha = -0.241 if female else -0.302

    scr_ratio = creatinine / kappa
    min_term = min(scr_ratio, 1) ** alpha
    max_term = max(scr_ratio, 1) ** -1.200
    age_term = 0.9938 ** age
    sex_term = 1.012 if female else 1

    egfr = 142 * min_term * max_term * age_term * sex_term
    egfr = round(egfr, 1)

    # CKD staging
    if egfr >= 90:
        stage = "G1"
        risk = RiskLevel.LOW
        interpretation = "Normal or high kidney function"
        recommendations = [
            "Annual monitoring if risk factors present",
            "Control blood pressure and diabetes",
        ]
    elif egfr >= 60:
        stage = "G2"
        risk = RiskLevel.LOW_MODERATE
        interpretation = "Mildly decreased kidney function"
        recommendations = [
            "Monitor eGFR annually",
            "Optimize blood pressure control",
            "Avoid nephrotoxic medications",
        ]
    elif egfr >= 45:
        stage = "G3a"
        risk = RiskLevel.MODERATE
        interpretation = "Mild-moderately decreased function"
        recommendations = [
            "Monitor eGFR every 6 months",
            "Referral to nephrology if rapid decline",
            "Adjust medications for renal function",
            "Screen for complications (anemia, bone disease)",
        ]
    elif egfr >= 30:
        stage = "G3b"
        risk = RiskLevel.MODERATE_HIGH
        interpretation = "Moderate-severely decreased function"
        recommendations = [
            "Nephrology referral recommended",
            "Monitor every 3-6 months",
            "Prepare for kidney replacement therapy",
            "Avoid contrast and nephrotoxins",
        ]
    elif egfr >= 15:
        stage = "G4"
        risk = RiskLevel.HIGH
        interpretation = "Severely decreased kidney function"
        recommendations = [
            "Nephrology co-management essential",
            "Plan for dialysis or transplant",
            "Avoid nephrotoxins strictly",
            "Monthly monitoring",
        ]
    else:
        stage = "G5"
        risk = RiskLevel.VERY_HIGH
        interpretation = "Kidney failure"
        recommendations = [
            "Initiate dialysis or transplant",
            "Intensive nephrology management",
            "Discuss goals of care",
        ]

    return CalculatorResult(
        calculator_name="CKD-EPI eGFR (2021)",
        score=egfr,
        score_unit="mL/min/1.73m²",
        risk_level=risk,
        interpretation=f"CKD Stage {stage}: {interpretation}",
        recommendations=recommendations,
        components={
            "creatinine": creatinine,
            "age": age,
            "female": female,
            "ckd_stage": stage,
        },
        references=["CKD-EPI 2021 (Inker et al., NEJM 2021)"],
    )


# ============================================================================
# Wells Score for DVT
# ============================================================================

def calculate_wells_dvt(
    active_cancer: bool = False,
    paralysis_immobilization: bool = False,
    bedridden_surgery: bool = False,
    localized_tenderness: bool = False,
    entire_leg_swollen: bool = False,
    calf_swelling_3cm: bool = False,
    pitting_edema: bool = False,
    collateral_veins: bool = False,
    previous_dvt: bool = False,
    alternative_diagnosis_likely: bool = False,
) -> CalculatorResult:
    """Calculate Wells Score for DVT probability.

    Uses data-driven definition from calculator_definitions.py.

    Args:
        active_cancer: Active cancer (treatment within 6 months).
        paralysis_immobilization: Paralysis or recent immobilization.
        bedridden_surgery: Bedridden >3 days or major surgery within 12 weeks.
        localized_tenderness: Localized tenderness along deep venous system.
        entire_leg_swollen: Entire leg swollen.
        calf_swelling_3cm: Calf swelling >3 cm compared to asymptomatic leg.
        pitting_edema: Pitting edema in symptomatic leg.
        collateral_veins: Collateral superficial veins (non-varicose).
        previous_dvt: Previous documented DVT.
        alternative_diagnosis_likely: Alternative diagnosis at least as likely.

    Returns:
        CalculatorResult with DVT probability assessment.
    """
    return calculate_from_definition(
        "wells_dvt",
        {
            "active_cancer": active_cancer,
            "paralysis_paresis": paralysis_immobilization,
            "bedridden": bedridden_surgery,
            "localized_tenderness": localized_tenderness,
            "entire_leg_swollen": entire_leg_swollen,
            "calf_swelling": calf_swelling_3cm,
            "pitting_edema": pitting_edema,
            "collateral_veins": collateral_veins,
            "previous_dvt": previous_dvt,
            "alternative_diagnosis": alternative_diagnosis_likely,
        },
    )


# ============================================================================
# CURB-65 (Pneumonia Severity)
# ============================================================================

def calculate_curb65(
    confusion: bool = False,
    bun_over_19: bool = False,
    respiratory_rate_over_30: bool = False,
    sbp_under_90_or_dbp_under_60: bool = False,
    age_65_or_older: bool = False,
) -> CalculatorResult:
    """Calculate CURB-65 score for community-acquired pneumonia severity.

    Uses data-driven definition from calculator_definitions.py.

    Args:
        confusion: New mental confusion (AMT ≤8 or disorientation).
        bun_over_19: BUN >19 mg/dL (or urea >7 mmol/L).
        respiratory_rate_over_30: Respiratory rate ≥30/min.
        sbp_under_90_or_dbp_under_60: SBP <90 or DBP ≤60 mmHg.
        age_65_or_older: Age ≥65 years.

    Returns:
        CalculatorResult with pneumonia severity and disposition.
    """
    return calculate_from_definition(
        "curb65",
        {
            "confusion": confusion,
            "uremia": bun_over_19,
            "respiratory_rate": respiratory_rate_over_30,
            "low_blood_pressure": sbp_under_90_or_dbp_under_60,
            "age_65_or_older": age_65_or_older,
        },
    )


# ============================================================================
# Framingham Risk Score (10-year CVD Risk)
# ============================================================================

def calculate_framingham_10yr(
    age: int,
    female: bool,
    total_cholesterol: float,
    hdl_cholesterol: float,
    systolic_bp: float,
    bp_treated: bool = False,
    smoker: bool = False,
    diabetic: bool = False,
) -> CalculatorResult:
    """Calculate Framingham 10-year cardiovascular disease risk.

    Args:
        age: Patient age in years (30-79).
        female: True if female.
        total_cholesterol: Total cholesterol in mg/dL.
        hdl_cholesterol: HDL cholesterol in mg/dL.
        systolic_bp: Systolic blood pressure in mmHg.
        bp_treated: True if on BP medication.
        smoker: Current smoker.
        diabetic: Has diabetes.

    Returns:
        CalculatorResult with 10-year CVD risk.
    """
    # Simplified Framingham calculation (based on 2008 general CVD risk)
    # Using point system for easier calculation

    points = 0
    components = {}

    # Age points
    if female:
        if age < 35:
            age_pts = -7
        elif age < 40:
            age_pts = -3
        elif age < 45:
            age_pts = 0
        elif age < 50:
            age_pts = 3
        elif age < 55:
            age_pts = 6
        elif age < 60:
            age_pts = 8
        elif age < 65:
            age_pts = 10
        elif age < 70:
            age_pts = 12
        elif age < 75:
            age_pts = 14
        else:
            age_pts = 16
    else:
        if age < 35:
            age_pts = -9
        elif age < 40:
            age_pts = -4
        elif age < 45:
            age_pts = 0
        elif age < 50:
            age_pts = 3
        elif age < 55:
            age_pts = 6
        elif age < 60:
            age_pts = 8
        elif age < 65:
            age_pts = 10
        elif age < 70:
            age_pts = 11
        elif age < 75:
            age_pts = 12
        else:
            age_pts = 13

    points += age_pts
    components["Age points"] = age_pts

    # Total cholesterol points
    if total_cholesterol < 160:
        tc_pts = 0
    elif total_cholesterol < 200:
        tc_pts = 1 if female else 1
    elif total_cholesterol < 240:
        tc_pts = 2 if female else 2
    elif total_cholesterol < 280:
        tc_pts = 3 if female else 3
    else:
        tc_pts = 4 if female else 4

    points += tc_pts
    components["Cholesterol points"] = tc_pts

    # HDL points
    if hdl_cholesterol >= 60:
        hdl_pts = -1
    elif hdl_cholesterol >= 50:
        hdl_pts = 0
    elif hdl_cholesterol >= 40:
        hdl_pts = 1
    else:
        hdl_pts = 2

    points += hdl_pts
    components["HDL points"] = hdl_pts

    # BP points
    if systolic_bp < 120:
        bp_pts = 0
    elif systolic_bp < 130:
        bp_pts = 1 if bp_treated else 0
    elif systolic_bp < 140:
        bp_pts = 2 if bp_treated else 1
    elif systolic_bp < 160:
        bp_pts = 3 if bp_treated else 2
    else:
        bp_pts = 4 if bp_treated else 3

    points += bp_pts
    components["BP points"] = bp_pts

    # Smoking
    if smoker:
        smoke_pts = 3 if female else 3
        points += smoke_pts
        components["Smoking"] = smoke_pts

    # Diabetes
    if diabetic:
        dm_pts = 4 if female else 3
        points += dm_pts
        components["Diabetes"] = dm_pts

    # Convert points to 10-year risk (simplified)
    if female:
        if points <= 0:
            risk_pct = 1
        elif points <= 5:
            risk_pct = 2
        elif points <= 8:
            risk_pct = 4
        elif points <= 11:
            risk_pct = 8
        elif points <= 14:
            risk_pct = 15
        elif points <= 17:
            risk_pct = 22
        else:
            risk_pct = 30
    else:
        if points <= 0:
            risk_pct = 1
        elif points <= 5:
            risk_pct = 3
        elif points <= 8:
            risk_pct = 6
        elif points <= 11:
            risk_pct = 11
        elif points <= 14:
            risk_pct = 18
        elif points <= 17:
            risk_pct = 27
        else:
            risk_pct = 35

    # Risk stratification
    if risk_pct < 5:
        risk = RiskLevel.LOW
        interpretation = f"Low 10-year CVD risk ({risk_pct}%)"
        recommendations = [
            "Lifestyle modifications recommended",
            "Healthy diet and regular exercise",
            "Reassess in 4-6 years",
        ]
    elif risk_pct < 10:
        risk = RiskLevel.LOW_MODERATE
        interpretation = f"Borderline 10-year CVD risk ({risk_pct}%)"
        recommendations = [
            "Aggressive lifestyle modifications",
            "Consider statin therapy if risk-enhancing factors",
            "Target LDL <100 mg/dL",
        ]
    elif risk_pct < 20:
        risk = RiskLevel.MODERATE
        interpretation = f"Intermediate 10-year CVD risk ({risk_pct}%)"
        recommendations = [
            "Moderate-intensity statin therapy recommended",
            "Target LDL <100 mg/dL (some recommend <70)",
            "Aspirin if benefit outweighs bleeding risk",
            "Strict BP control",
        ]
    else:
        risk = RiskLevel.HIGH
        interpretation = f"High 10-year CVD risk ({risk_pct}%)"
        recommendations = [
            "High-intensity statin therapy",
            "Target LDL <70 mg/dL",
            "Aspirin therapy",
            "Aggressive BP control (<130/80)",
            "Consider additional therapies (ezetimibe, PCSK9i)",
        ]

    return CalculatorResult(
        calculator_name="Framingham 10-Year CVD Risk",
        score=risk_pct,
        score_unit="%",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["D'Agostino RB, et al. Circulation 2008"],
    )


# ============================================================================
# HEART Score (Major Adverse Cardiac Events)
# ============================================================================

def calculate_heart_score(
    history_highly_suspicious: bool = False,
    history_moderately_suspicious: bool = False,
    ekg_significant_st_depression: bool = False,
    ekg_nonspecific_repolarization: bool = False,
    age: int = 45,
    risk_factors_count: int = 0,
    initial_troponin_elevated_3x: bool = False,
    initial_troponin_elevated_1_3x: bool = False,
) -> CalculatorResult:
    """Calculate HEART Score for major adverse cardiac events in chest pain patients.

    Uses data-driven definition from calculator_definitions.py.
    """
    # Map risk_factors_count to boolean level flags
    risk_factors_three_or_more = risk_factors_count >= 3
    risk_factors_one_or_two = 1 <= risk_factors_count < 3

    return calculate_from_definition(
        "heart_score",
        {
            # History multi-level
            "history_highly_suspicious": history_highly_suspicious,
            "history_moderately_suspicious": history_moderately_suspicious,
            # EKG multi-level
            "ekg_significant_st_depression": ekg_significant_st_depression,
            "ekg_nonspecific_repolarization": ekg_nonspecific_repolarization,
            # Risk factors multi-level (converted from count)
            "risk_factors_three_or_more": risk_factors_three_or_more,
            "risk_factors_one_or_two": risk_factors_one_or_two,
            # Troponin multi-level
            "initial_troponin_elevated_3x": initial_troponin_elevated_3x,
            "initial_troponin_elevated_1_3x": initial_troponin_elevated_1_3x,
        },
        age=age,
    )


# ============================================================================
# ASCVD Risk Calculator (Pooled Cohort Equations)
# ============================================================================

def calculate_ascvd_risk(
    age: int,
    female: bool,
    black: bool,
    total_cholesterol: float,
    hdl_cholesterol: float,
    systolic_bp: float,
    bp_treated: bool = False,
    diabetic: bool = False,
    smoker: bool = False,
) -> CalculatorResult:
    """Calculate 10-year ASCVD risk using the Pooled Cohort Equations.

    Args:
        age: Patient age in years (40-79).
        female: True if female.
        black: True if African American.
        total_cholesterol: Total cholesterol in mg/dL.
        hdl_cholesterol: HDL cholesterol in mg/dL.
        systolic_bp: Systolic blood pressure in mmHg.
        bp_treated: True if on BP medication.
        diabetic: Has diabetes.
        smoker: Current smoker.

    Returns:
        CalculatorResult with 10-year ASCVD risk.
    """
    # Coefficients for the Pooled Cohort Equations
    ln_age = math.log(age)
    ln_tc = math.log(total_cholesterol)
    ln_hdl = math.log(hdl_cholesterol)
    ln_sbp = math.log(systolic_bp)

    if female:
        if black:
            # Black Female
            coef_age = 17.1141
            coef_age_sq = 0
            coef_tc = 0.9396
            coef_age_tc = 0
            coef_hdl = -18.9196
            coef_age_hdl = 4.4748
            coef_sbp_treated = 29.2907
            coef_age_sbp_treated = -6.4321
            coef_sbp_untreated = 27.8197
            coef_age_sbp_untreated = -6.0873
            coef_smoke = 0.6908
            coef_age_smoke = 0
            coef_dm = 0.8738
            baseline_survival = 0.9533
            mean_value = 86.61
        else:
            # White/Other Female
            coef_age = -29.799
            coef_age_sq = 4.884
            coef_tc = 13.540
            coef_age_tc = -3.114
            coef_hdl = -13.578
            coef_age_hdl = 3.149
            coef_sbp_treated = 2.019
            coef_age_sbp_treated = 0
            coef_sbp_untreated = 1.957
            coef_age_sbp_untreated = 0
            coef_smoke = 7.574
            coef_age_smoke = -1.665
            coef_dm = 0.661
            baseline_survival = 0.9665
            mean_value = -29.18
    else:
        if black:
            # Black Male
            coef_age = 2.469
            coef_age_sq = 0
            coef_tc = 0.302
            coef_age_tc = 0
            coef_hdl = -0.307
            coef_age_hdl = 0
            coef_sbp_treated = 1.916
            coef_age_sbp_treated = 0
            coef_sbp_untreated = 1.809
            coef_age_sbp_untreated = 0
            coef_smoke = 0.549
            coef_age_smoke = 0
            coef_dm = 0.645
            baseline_survival = 0.8954
            mean_value = 19.54
        else:
            # White/Other Male
            coef_age = 12.344
            coef_age_sq = 0
            coef_tc = 11.853
            coef_age_tc = -2.664
            coef_hdl = -7.990
            coef_age_hdl = 1.769
            coef_sbp_treated = 1.797
            coef_age_sbp_treated = 0
            coef_sbp_untreated = 1.764
            coef_age_sbp_untreated = 0
            coef_smoke = 7.837
            coef_age_smoke = -1.795
            coef_dm = 0.658
            baseline_survival = 0.9144
            mean_value = 61.18

    # Calculate individual sum
    individual_sum = (
        coef_age * ln_age +
        coef_age_sq * (ln_age ** 2) +
        coef_tc * ln_tc +
        coef_age_tc * ln_age * ln_tc +
        coef_hdl * ln_hdl +
        coef_age_hdl * ln_age * ln_hdl
    )

    # Add blood pressure contribution
    if bp_treated:
        individual_sum += coef_sbp_treated * ln_sbp + coef_age_sbp_treated * ln_age * ln_sbp
    else:
        individual_sum += coef_sbp_untreated * ln_sbp + coef_age_sbp_untreated * ln_age * ln_sbp

    # Add smoking
    if smoker:
        individual_sum += coef_smoke + coef_age_smoke * ln_age

    # Add diabetes
    if diabetic:
        individual_sum += coef_dm

    # Calculate 10-year risk
    risk_pct = 100 * (1 - baseline_survival ** math.exp(individual_sum - mean_value))
    risk_pct = round(max(0.1, min(risk_pct, 99.9)), 1)

    components = {
        "age": age,
        "sex": "Female" if female else "Male",
        "race": "Black" if black else "White/Other",
        "total_cholesterol": total_cholesterol,
        "hdl_cholesterol": hdl_cholesterol,
        "systolic_bp": systolic_bp,
        "bp_treated": bp_treated,
        "diabetic": diabetic,
        "smoker": smoker,
    }

    # Risk stratification
    if risk_pct < 5:
        risk = RiskLevel.LOW
        interpretation = f"Low 10-year ASCVD risk ({risk_pct}%)"
        recommendations = [
            "Emphasize lifestyle to reduce risk factors",
            "Reassess in 4-6 years",
            "Statin therapy generally not indicated",
        ]
    elif risk_pct < 7.5:
        risk = RiskLevel.LOW_MODERATE
        interpretation = f"Borderline 10-year ASCVD risk ({risk_pct}%)"
        recommendations = [
            "Lifestyle counseling",
            "Consider risk-enhancing factors",
            "If risk-enhancing factors, consider moderate-intensity statin",
            "Coronary artery calcium score may help guide decision",
        ]
    elif risk_pct < 20:
        risk = RiskLevel.MODERATE
        interpretation = f"Intermediate 10-year ASCVD risk ({risk_pct}%)"
        recommendations = [
            "Moderate-intensity statin therapy recommended",
            "Lifestyle modifications",
            "Consider high-intensity statin if multiple risk enhancers",
            "Target LDL reduction ≥30%",
        ]
    else:
        risk = RiskLevel.HIGH
        interpretation = f"High 10-year ASCVD risk ({risk_pct}%)"
        recommendations = [
            "High-intensity statin therapy recommended",
            "Target LDL <70 mg/dL or ≥50% reduction",
            "Consider ezetimibe if LDL goal not achieved",
            "Aspirin if benefit outweighs bleeding risk",
            "Aggressive lifestyle modifications",
        ]

    return CalculatorResult(
        calculator_name="ASCVD 10-Year Risk (PCE)",
        score=risk_pct,
        score_unit="%",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["2013 ACC/AHA Guideline", "Goff DC, et al. Circulation 2014"],
    )


# ============================================================================
# Wells Score for Pulmonary Embolism
# ============================================================================

def calculate_wells_pe(
    clinical_signs_dvt: bool = False,
    pe_most_likely: bool = False,
    heart_rate_over_100: bool = False,
    immobilization_surgery: bool = False,
    previous_pe_dvt: bool = False,
    hemoptysis: bool = False,
    malignancy: bool = False,
) -> CalculatorResult:
    """Calculate Wells Score for Pulmonary Embolism probability.

    Uses data-driven definition from calculator_definitions.py.
    """
    return calculate_from_definition(
        "wells_pe",
        {
            "clinical_signs_dvt": clinical_signs_dvt,
            "pe_most_likely": pe_most_likely,
            "heart_rate_over_100": heart_rate_over_100,
            "immobilization_surgery": immobilization_surgery,
            "previous_pe_dvt": previous_pe_dvt,
            "hemoptysis": hemoptysis,
            "malignancy": malignancy,
        },
    )


# ============================================================================
# qSOFA Score (Quick Sequential Organ Failure Assessment)
# ============================================================================

def calculate_qsofa(
    respiratory_rate_22_or_higher: bool = False,
    altered_mental_status: bool = False,
    systolic_bp_100_or_lower: bool = False,
) -> CalculatorResult:
    """Calculate qSOFA score for sepsis screening.

    Uses data-driven definition from calculator_definitions.py.

    Args:
        respiratory_rate_22_or_higher: Respiratory rate ≥22/min.
        altered_mental_status: Altered mentation (GCS <15).
        systolic_bp_100_or_lower: Systolic BP ≤100 mmHg.

    Returns:
        CalculatorResult with sepsis risk assessment.
    """
    return calculate_from_definition(
        "qsofa",
        {
            "respiratory_rate_22": respiratory_rate_22_or_higher,
            "altered_mentation": altered_mental_status,
            "systolic_bp_100": systolic_bp_100_or_lower,
        },
    )


# ============================================================================
# Glasgow Coma Scale (GCS)
# ============================================================================

def calculate_gcs(
    eye_response: int,
    verbal_response: int,
    motor_response: int,
) -> CalculatorResult:
    """Calculate Glasgow Coma Scale score.

    Uses data-driven definition from calculator_definitions.py.

    Args:
        eye_response: Eye opening (1-4): 4=Spontaneous, 3=To voice, 2=To pain, 1=None
        verbal_response: Verbal response (1-5): 5=Oriented, 4=Confused, 3=Inappropriate, 2=Incomprehensible, 1=None
        motor_response: Motor response (1-6): 6=Obeys, 5=Localizes, 4=Withdraws, 3=Flexion, 2=Extension, 1=None
    """
    # Validate and clamp inputs
    eye = max(1, min(eye_response, 4))
    verbal = max(1, min(verbal_response, 5))
    motor = max(1, min(motor_response, 6))

    # Map integer subscores to multi-level boolean flags
    eye_map = {4: "spontaneous", 3: "to_voice", 2: "to_pain", 1: "none"}
    verbal_map = {5: "oriented", 4: "confused", 3: "inappropriate", 2: "incomprehensible", 1: "none"}
    motor_map = {6: "obeys", 5: "localizes", 4: "withdraws", 3: "flexion", 2: "extension", 1: "none"}

    return calculate_from_definition(
        "gcs",
        {
            f"eye_{eye_map[eye]}": True,
            f"verbal_{verbal_map[verbal]}": True,
            f"motor_{motor_map[motor]}": True,
        },
    )


# ============================================================================
# Child-Pugh Score (Cirrhosis Severity)
# ============================================================================

def calculate_child_pugh(
    bilirubin: float,
    albumin: float,
    inr: float,
    ascites: str = "none",
    encephalopathy: str = "none",
) -> CalculatorResult:
    """Calculate Child-Pugh score for cirrhosis severity.

    Uses data-driven definition from calculator_definitions.py.

    Args:
        bilirubin: Total bilirubin in mg/dL.
        albumin: Serum albumin in g/dL.
        inr: International Normalized Ratio.
        ascites: "none", "mild"/"slight", or "moderate_severe"/"moderate".
        encephalopathy: "none", "grade_1_2", or "grade_3_4".
    """
    # Map string values to multi-level boolean flags
    ascites_lower = ascites.lower()
    enceph_lower = encephalopathy.lower()

    # Map ascites string to flag
    ascites_map = {
        "none": "none", "absent": "none",
        "mild": "slight", "slight": "slight", "controlled": "slight",
        "moderate": "moderate", "moderate_severe": "moderate", "severe": "moderate", "refractory": "moderate",
    }
    ascites_flag = ascites_map.get(ascites_lower, "moderate")

    # Map encephalopathy string to flag
    enceph_map = {
        "none": "none", "absent": "none",
        "grade_1_2": "grade_1_2", "grade 1-2": "grade_1_2", "mild": "grade_1_2", "controlled": "grade_1_2",
        "grade_3_4": "grade_3_4", "grade 3-4": "grade_3_4", "severe": "grade_3_4", "refractory": "grade_3_4",
    }
    enceph_flag = enceph_map.get(enceph_lower, "grade_3_4")

    return calculate_from_definition(
        "child_pugh",
        {
            # Numeric threshold criteria
            "bilirubin": bilirubin,
            "albumin": albumin,
            "inr": inr,
            # Multi-level criteria as booleans
            f"ascites_{ascites_flag}": True,
            f"encephalopathy_{enceph_flag}": True,
        },
    )


# ============================================================================
# FIB-4 Index (Liver Fibrosis)
# ============================================================================

def calculate_fib4(
    age: int,
    ast: float,
    alt: float,
    platelet_count: float,
) -> CalculatorResult:
    """Calculate FIB-4 index for liver fibrosis estimation.

    Args:
        age: Patient age in years.
        ast: AST in U/L.
        alt: ALT in U/L.
        platelet_count: Platelet count in 10^9/L (or thousands).

    Returns:
        CalculatorResult with fibrosis risk assessment.
    """
    # FIB-4 = (Age × AST) / (Platelet count × √ALT)
    if alt <= 0 or platelet_count <= 0:
        raise ValueError("ALT and platelet count must be positive")

    fib4 = (age * ast) / (platelet_count * math.sqrt(alt))
    fib4 = round(fib4, 2)

    components = {
        "age": age,
        "AST": ast,
        "ALT": alt,
        "platelet_count": platelet_count,
    }

    # Risk stratification
    if fib4 < 1.30:
        risk = RiskLevel.LOW
        interpretation = "Low probability of advanced fibrosis"
        recommendations = [
            "Advanced fibrosis unlikely (NPV ~90%)",
            "Monitor transaminases periodically",
            "Reassess if risk factors change",
        ]
    elif fib4 <= 2.67:
        risk = RiskLevel.MODERATE
        interpretation = "Indeterminate - further evaluation needed"
        recommendations = [
            "Consider elastography (FibroScan)",
            "Or liver biopsy for definitive staging",
            "Hepatology referral recommended",
            "Address underlying liver disease",
        ]
    else:
        risk = RiskLevel.HIGH
        interpretation = "High probability of advanced fibrosis (F3-F4)"
        recommendations = [
            "Advanced fibrosis likely (PPV ~65%)",
            "Hepatology referral essential",
            "HCC surveillance every 6 months",
            "Evaluate for cirrhosis complications",
            "Consider liver biopsy or elastography",
        ]

    return CalculatorResult(
        calculator_name="FIB-4 Index",
        score=fib4,
        score_unit="",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Sterling RK, et al. Hepatology 2006"],
    )


# ============================================================================
# Creatinine Clearance (Cockcroft-Gault)
# ============================================================================

def calculate_creatinine_clearance(
    age: int,
    weight_kg: float,
    creatinine: float,
    female: bool,
) -> CalculatorResult:
    """Calculate creatinine clearance using Cockcroft-Gault equation.

    Args:
        age: Patient age in years.
        weight_kg: Body weight in kg (use actual or adjusted body weight).
        creatinine: Serum creatinine in mg/dL.
        female: True if female.

    Returns:
        CalculatorResult with CrCl for drug dosing.
    """
    if creatinine <= 0:
        raise ValueError("Creatinine must be positive")

    # CrCl = [(140 - Age) × Weight] / (72 × SCr) × 0.85 if female
    crcl = ((140 - age) * weight_kg) / (72 * creatinine)
    if female:
        crcl *= 0.85

    crcl = round(crcl, 1)

    components = {
        "age": age,
        "weight_kg": weight_kg,
        "creatinine": creatinine,
        "female": female,
    }

    # Risk stratification for drug dosing
    if crcl >= 90:
        risk = RiskLevel.LOW
        interpretation = "Normal renal function"
        recommendations = [
            "Standard drug dosing appropriate",
            "No renal dose adjustments needed",
        ]
    elif crcl >= 60:
        risk = RiskLevel.LOW_MODERATE
        interpretation = "Mildly reduced renal function"
        recommendations = [
            "Some medications may need dose adjustment",
            "Check package inserts for renal dosing",
        ]
    elif crcl >= 30:
        risk = RiskLevel.MODERATE
        interpretation = "Moderately reduced renal function"
        recommendations = [
            "Many drugs require dose reduction",
            "Avoid nephrotoxic medications when possible",
            "Check all medications for renal dosing",
        ]
    elif crcl >= 15:
        risk = RiskLevel.HIGH
        interpretation = "Severely reduced renal function"
        recommendations = [
            "Significant dose reductions needed for most renally-cleared drugs",
            "Avoid nephrotoxic drugs",
            "Pharmacy consult recommended",
        ]
    else:
        risk = RiskLevel.VERY_HIGH
        interpretation = "End-stage renal disease"
        recommendations = [
            "Dialysis-level dosing adjustments",
            "Consider dialyzability of medications",
            "Nephrology and pharmacy consultation essential",
        ]

    return CalculatorResult(
        calculator_name="Creatinine Clearance (Cockcroft-Gault)",
        score=crcl,
        score_unit="mL/min",
        risk_level=risk,
        interpretation=f"{interpretation}. CrCl = {crcl} mL/min",
        recommendations=recommendations,
        components=components,
        references=["Cockcroft DW, Gault MH. Nephron 1976"],
    )


# ============================================================================
# PERC Rule (Pulmonary Embolism Rule-out Criteria)
# ============================================================================

def calculate_perc(
    age_under_50: bool = True,
    heart_rate_under_100: bool = True,
    spo2_over_94: bool = True,
    no_unilateral_leg_swelling: bool = True,
    no_hemoptysis: bool = True,
    no_recent_surgery_trauma: bool = True,
    no_prior_pe_dvt: bool = True,
    no_hormone_use: bool = True,
) -> CalculatorResult:
    """Apply PERC rule to exclude PE without D-dimer in low-risk patients.

    Args:
        age_under_50: Age <50 years.
        heart_rate_under_100: Heart rate <100 bpm.
        spo2_over_94: SpO2 >94% on room air.
        no_unilateral_leg_swelling: No unilateral leg swelling.
        no_hemoptysis: No hemoptysis.
        no_recent_surgery_trauma: No surgery/trauma requiring hospitalization in past 4 weeks.
        no_prior_pe_dvt: No prior PE or DVT.
        no_hormone_use: No exogenous estrogen use.

    Returns:
        CalculatorResult indicating if PERC criteria are met.
    """
    # Count how many criteria are MET (all must be true to pass)
    criteria_met = sum([
        age_under_50,
        heart_rate_under_100,
        spo2_over_94,
        no_unilateral_leg_swelling,
        no_hemoptysis,
        no_recent_surgery_trauma,
        no_prior_pe_dvt,
        no_hormone_use,
    ])

    components = {
        "Age <50": "Yes" if age_under_50 else "No",
        "HR <100": "Yes" if heart_rate_under_100 else "No",
        "SpO2 >94%": "Yes" if spo2_over_94 else "No",
        "No leg swelling": "Yes" if no_unilateral_leg_swelling else "No",
        "No hemoptysis": "Yes" if no_hemoptysis else "No",
        "No recent surgery/trauma": "Yes" if no_recent_surgery_trauma else "No",
        "No prior PE/DVT": "Yes" if no_prior_pe_dvt else "No",
        "No hormone use": "Yes" if no_hormone_use else "No",
    }

    all_criteria_met = criteria_met == 8

    if all_criteria_met:
        risk = RiskLevel.LOW
        interpretation = "PERC negative - PE can be excluded without D-dimer"
        recommendations = [
            "In low pretest probability patients, no further workup needed",
            "PE risk <2% - below test threshold",
            "Consider alternative diagnoses",
            "Return precautions for worsening symptoms",
        ]
        score = 0  # All criteria met = PERC negative
    else:
        risk = RiskLevel.MODERATE
        failed_criteria = 8 - criteria_met
        interpretation = f"PERC positive - {failed_criteria} criteria not met"
        recommendations = [
            "Cannot rule out PE by PERC alone",
            "Proceed with D-dimer testing",
            "If D-dimer positive, CT pulmonary angiography",
        ]
        score = failed_criteria

    return CalculatorResult(
        calculator_name="PERC Rule",
        score=score,
        score_unit="criteria failed",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Kline JA, et al. J Thromb Haemost 2004", "Ann Emerg Med 2008"],
    )


# ============================================================================
# TIMI Risk Score for UA/NSTEMI
# ============================================================================

def calculate_timi_ua_nstemi(
    age_65_or_older: bool = False,
    three_or_more_cad_risk_factors: bool = False,
    known_cad_50_stenosis: bool = False,
    aspirin_use_past_7_days: bool = False,
    severe_angina_two_or_more_episodes_24h: bool = False,
    st_changes_05mm_or_more: bool = False,
    elevated_cardiac_markers: bool = False,
) -> CalculatorResult:
    """Calculate TIMI Risk Score for Unstable Angina/NSTEMI.

    Uses data-driven definition from calculator_definitions.py.
    """
    return calculate_from_definition(
        "timi_nstemi",
        {
            "age_65_or_older": age_65_or_older,
            "three_or_more_cad_risk_factors": three_or_more_cad_risk_factors,
            "known_cad_50_stenosis": known_cad_50_stenosis,
            "aspirin_use_past_7_days": aspirin_use_past_7_days,
            "severe_angina_two_or_more_episodes_24h": severe_angina_two_or_more_episodes_24h,
            "st_changes_05mm_or_more": st_changes_05mm_or_more,
            "elevated_cardiac_markers": elevated_cardiac_markers,
        },
    )


# ============================================================================
# APACHE II Score (Critical Care)
# ============================================================================

def calculate_apache_ii(
    age: int,
    temperature: float,  # Celsius, rectal
    mean_arterial_pressure: float,  # mmHg
    heart_rate: int,
    respiratory_rate: int,
    fio2: float,  # Fraction (0.21-1.0)
    pao2: float | None = None,  # mmHg, if FiO2 < 0.5
    aa_gradient: float | None = None,  # if FiO2 >= 0.5
    arterial_ph: float | None = None,
    serum_sodium: float = 140,  # mEq/L
    serum_potassium: float = 4.0,  # mEq/L
    serum_creatinine: float = 1.0,  # mg/dL
    acute_renal_failure: bool = False,
    hematocrit: float = 40,  # %
    wbc: float = 10,  # 1000/mm³
    gcs: int = 15,
    chronic_health: str = "none",  # "none", "nonoperative", "emergency_postop", "elective_postop"
) -> CalculatorResult:
    """Calculate APACHE II score for ICU mortality prediction.

    Args:
        age: Patient age in years.
        temperature: Rectal temperature in Celsius.
        mean_arterial_pressure: MAP in mmHg.
        heart_rate: Heart rate in bpm.
        respiratory_rate: Respiratory rate per minute.
        fio2: Fraction of inspired oxygen (0.21-1.0).
        pao2: PaO2 in mmHg (use if FiO2 < 0.5).
        aa_gradient: A-a gradient (use if FiO2 >= 0.5).
        arterial_ph: Arterial blood pH.
        serum_sodium: Serum sodium in mEq/L.
        serum_potassium: Serum potassium in mEq/L.
        serum_creatinine: Serum creatinine in mg/dL.
        acute_renal_failure: True if ARF present.
        hematocrit: Hematocrit in %.
        wbc: WBC count in 1000/mm³.
        gcs: Glasgow Coma Scale (3-15).
        chronic_health: Chronic health status.

    Returns:
        CalculatorResult with APACHE II score and mortality prediction.
    """
    score = 0
    components = {}

    # Temperature points
    if temperature >= 41:
        temp_pts = 4
    elif temperature >= 39:
        temp_pts = 3
    elif temperature >= 38.5:
        temp_pts = 1
    elif temperature >= 36:
        temp_pts = 0
    elif temperature >= 34:
        temp_pts = 1
    elif temperature >= 32:
        temp_pts = 2
    elif temperature >= 30:
        temp_pts = 3
    else:
        temp_pts = 4
    score += temp_pts
    components["Temperature"] = temp_pts

    # MAP points
    if mean_arterial_pressure >= 160:
        map_pts = 4
    elif mean_arterial_pressure >= 130:
        map_pts = 3
    elif mean_arterial_pressure >= 110:
        map_pts = 2
    elif mean_arterial_pressure >= 70:
        map_pts = 0
    elif mean_arterial_pressure >= 50:
        map_pts = 2
    else:
        map_pts = 4
    score += map_pts
    components["MAP"] = map_pts

    # Heart rate points
    if heart_rate >= 180:
        hr_pts = 4
    elif heart_rate >= 140:
        hr_pts = 3
    elif heart_rate >= 110:
        hr_pts = 2
    elif heart_rate >= 70:
        hr_pts = 0
    elif heart_rate >= 55:
        hr_pts = 2
    elif heart_rate >= 40:
        hr_pts = 3
    else:
        hr_pts = 4
    score += hr_pts
    components["Heart rate"] = hr_pts

    # Respiratory rate points
    if respiratory_rate >= 50:
        rr_pts = 4
    elif respiratory_rate >= 35:
        rr_pts = 3
    elif respiratory_rate >= 25:
        rr_pts = 1
    elif respiratory_rate >= 12:
        rr_pts = 0
    elif respiratory_rate >= 10:
        rr_pts = 1
    elif respiratory_rate >= 6:
        rr_pts = 2
    else:
        rr_pts = 4
    score += rr_pts
    components["Respiratory rate"] = rr_pts

    # Oxygenation points
    if fio2 >= 0.5 and aa_gradient is not None:
        if aa_gradient >= 500:
            oxy_pts = 4
        elif aa_gradient >= 350:
            oxy_pts = 3
        elif aa_gradient >= 200:
            oxy_pts = 2
        else:
            oxy_pts = 0
    elif pao2 is not None:
        if pao2 > 70:
            oxy_pts = 0
        elif pao2 >= 61:
            oxy_pts = 1
        elif pao2 >= 55:
            oxy_pts = 3
        else:
            oxy_pts = 4
    else:
        oxy_pts = 0
    score += oxy_pts
    components["Oxygenation"] = oxy_pts

    # Arterial pH points
    if arterial_ph is not None:
        if arterial_ph >= 7.7:
            ph_pts = 4
        elif arterial_ph >= 7.6:
            ph_pts = 3
        elif arterial_ph >= 7.5:
            ph_pts = 1
        elif arterial_ph >= 7.33:
            ph_pts = 0
        elif arterial_ph >= 7.25:
            ph_pts = 2
        elif arterial_ph >= 7.15:
            ph_pts = 3
        else:
            ph_pts = 4
        score += ph_pts
        components["Arterial pH"] = ph_pts

    # Sodium points
    if serum_sodium >= 180:
        na_pts = 4
    elif serum_sodium >= 160:
        na_pts = 3
    elif serum_sodium >= 155:
        na_pts = 2
    elif serum_sodium >= 150:
        na_pts = 1
    elif serum_sodium >= 130:
        na_pts = 0
    elif serum_sodium >= 120:
        na_pts = 2
    elif serum_sodium >= 111:
        na_pts = 3
    else:
        na_pts = 4
    score += na_pts
    components["Sodium"] = na_pts

    # Potassium points
    if serum_potassium >= 7:
        k_pts = 4
    elif serum_potassium >= 6:
        k_pts = 3
    elif serum_potassium >= 5.5:
        k_pts = 1
    elif serum_potassium >= 3.5:
        k_pts = 0
    elif serum_potassium >= 3:
        k_pts = 1
    elif serum_potassium >= 2.5:
        k_pts = 2
    else:
        k_pts = 4
    score += k_pts
    components["Potassium"] = k_pts

    # Creatinine points (double if ARF)
    cr_multiplier = 2 if acute_renal_failure else 1
    if serum_creatinine >= 3.5:
        cr_pts = 4 * cr_multiplier
    elif serum_creatinine >= 2:
        cr_pts = 3 * cr_multiplier
    elif serum_creatinine >= 1.5:
        cr_pts = 2 * cr_multiplier
    elif serum_creatinine >= 0.6:
        cr_pts = 0
    else:
        cr_pts = 2 * cr_multiplier
    score += cr_pts
    components["Creatinine"] = cr_pts

    # Hematocrit points
    if hematocrit >= 60:
        hct_pts = 4
    elif hematocrit >= 50:
        hct_pts = 2
    elif hematocrit >= 46:
        hct_pts = 1
    elif hematocrit >= 30:
        hct_pts = 0
    elif hematocrit >= 20:
        hct_pts = 2
    else:
        hct_pts = 4
    score += hct_pts
    components["Hematocrit"] = hct_pts

    # WBC points
    if wbc >= 40:
        wbc_pts = 4
    elif wbc >= 20:
        wbc_pts = 2
    elif wbc >= 15:
        wbc_pts = 1
    elif wbc >= 3:
        wbc_pts = 0
    elif wbc >= 1:
        wbc_pts = 2
    else:
        wbc_pts = 4
    score += wbc_pts
    components["WBC"] = wbc_pts

    # GCS points (15 - GCS)
    gcs_pts = 15 - gcs
    score += gcs_pts
    components["GCS"] = gcs_pts

    # Age points
    if age >= 75:
        age_pts = 6
    elif age >= 65:
        age_pts = 5
    elif age >= 55:
        age_pts = 3
    elif age >= 45:
        age_pts = 2
    else:
        age_pts = 0
    score += age_pts
    components["Age"] = age_pts

    # Chronic health points
    chronic_pts = 0
    if chronic_health == "nonoperative" or chronic_health == "emergency_postop":
        chronic_pts = 5
    elif chronic_health == "elective_postop":
        chronic_pts = 2
    score += chronic_pts
    components["Chronic health"] = chronic_pts

    # Mortality estimation (approximate)
    if score <= 4:
        mortality = "~4%"
        risk = RiskLevel.LOW
    elif score <= 9:
        mortality = "~8%"
        risk = RiskLevel.LOW_MODERATE
    elif score <= 14:
        mortality = "~15%"
        risk = RiskLevel.MODERATE
    elif score <= 19:
        mortality = "~25%"
        risk = RiskLevel.MODERATE_HIGH
    elif score <= 24:
        mortality = "~40%"
        risk = RiskLevel.HIGH
    elif score <= 29:
        mortality = "~55%"
        risk = RiskLevel.HIGH
    elif score <= 34:
        mortality = "~75%"
        risk = RiskLevel.VERY_HIGH
    else:
        mortality = "~85%"
        risk = RiskLevel.VERY_HIGH

    interpretation = f"APACHE II Score {score}. Estimated in-hospital mortality: {mortality}"

    if score <= 14:
        recommendations = [
            "Continue ICU monitoring and supportive care",
            "Serial APACHE II calculations to track trajectory",
            "Address specific organ dysfunctions",
        ]
    elif score <= 24:
        recommendations = [
            "Aggressive ICU management",
            "Consider subspecialty consultations",
            "Family discussions regarding prognosis",
            "Monitor for complications",
        ]
    else:
        recommendations = [
            "Maximum ICU support",
            "Early family conference regarding prognosis",
            "Consider palliative care consultation",
            "Document goals of care",
        ]

    return CalculatorResult(
        calculator_name="APACHE II Score",
        score=score,
        score_unit="points",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Knaus WA, et al. Crit Care Med 1985"],
    )


# ============================================================================
# SOFA Score (Sequential Organ Failure Assessment)
# ============================================================================

def calculate_sofa(
    pao2_fio2_ratio: float,  # PaO2/FiO2 ratio
    on_mechanical_ventilation: bool = False,
    platelets: float = 150,  # × 10³/µL
    bilirubin: float = 1.0,  # mg/dL
    map: float | None = None,  # Mean arterial pressure
    dopamine_dose: float = 0,  # µg/kg/min
    dobutamine_any: bool = False,
    epinephrine_dose: float = 0,  # µg/kg/min
    norepinephrine_dose: float = 0,  # µg/kg/min
    gcs: int = 15,
    creatinine: float = 1.0,  # mg/dL
    urine_output_ml_day: float | None = None,
) -> CalculatorResult:
    """Calculate SOFA score for organ dysfunction in sepsis.

    Args:
        pao2_fio2_ratio: PaO2/FiO2 ratio.
        on_mechanical_ventilation: True if on ventilator.
        platelets: Platelet count × 10³/µL.
        bilirubin: Total bilirubin in mg/dL.
        map: Mean arterial pressure in mmHg.
        dopamine_dose: Dopamine dose in µg/kg/min.
        dobutamine_any: Any dobutamine use.
        epinephrine_dose: Epinephrine dose in µg/kg/min.
        norepinephrine_dose: Norepinephrine dose in µg/kg/min.
        gcs: Glasgow Coma Scale.
        creatinine: Serum creatinine in mg/dL.
        urine_output_ml_day: Urine output in mL/day.

    Returns:
        CalculatorResult with SOFA score and mortality prediction.
    """
    score = 0
    components = {}

    # Respiration (PaO2/FiO2)
    if pao2_fio2_ratio >= 400:
        resp_pts = 0
    elif pao2_fio2_ratio >= 300:
        resp_pts = 1
    elif pao2_fio2_ratio >= 200:
        resp_pts = 2
    elif pao2_fio2_ratio >= 100:
        resp_pts = 3 if on_mechanical_ventilation else 2
    else:
        resp_pts = 4 if on_mechanical_ventilation else 3
    score += resp_pts
    components["Respiration"] = resp_pts

    # Coagulation (Platelets)
    if platelets >= 150:
        plt_pts = 0
    elif platelets >= 100:
        plt_pts = 1
    elif platelets >= 50:
        plt_pts = 2
    elif platelets >= 20:
        plt_pts = 3
    else:
        plt_pts = 4
    score += plt_pts
    components["Coagulation (Platelets)"] = plt_pts

    # Liver (Bilirubin)
    if bilirubin < 1.2:
        bili_pts = 0
    elif bilirubin < 2:
        bili_pts = 1
    elif bilirubin < 6:
        bili_pts = 2
    elif bilirubin < 12:
        bili_pts = 3
    else:
        bili_pts = 4
    score += bili_pts
    components["Liver (Bilirubin)"] = bili_pts

    # Cardiovascular
    if map is not None and map < 70 and dopamine_dose == 0 and not dobutamine_any and epinephrine_dose == 0 and norepinephrine_dose == 0:
        cardio_pts = 1
    elif dopamine_dose <= 5 or dobutamine_any:
        cardio_pts = 2 if dopamine_dose > 0 or dobutamine_any else 0
    elif dopamine_dose > 5 or epinephrine_dose <= 0.1 or norepinephrine_dose <= 0.1:
        if dopamine_dose > 5 or epinephrine_dose > 0 or norepinephrine_dose > 0:
            if dopamine_dose > 15 or epinephrine_dose > 0.1 or norepinephrine_dose > 0.1:
                cardio_pts = 4
            else:
                cardio_pts = 3
        else:
            cardio_pts = 0
    else:
        cardio_pts = 0

    # Simplified cardiovascular scoring
    if epinephrine_dose > 0.1 or norepinephrine_dose > 0.1 or dopamine_dose > 15:
        cardio_pts = 4
    elif epinephrine_dose > 0 or norepinephrine_dose > 0 or dopamine_dose > 5:
        cardio_pts = 3
    elif dopamine_dose > 0 or dobutamine_any:
        cardio_pts = 2
    elif map is not None and map < 70:
        cardio_pts = 1
    else:
        cardio_pts = 0
    score += cardio_pts
    components["Cardiovascular"] = cardio_pts

    # CNS (GCS)
    if gcs >= 15:
        cns_pts = 0
    elif gcs >= 13:
        cns_pts = 1
    elif gcs >= 10:
        cns_pts = 2
    elif gcs >= 6:
        cns_pts = 3
    else:
        cns_pts = 4
    score += cns_pts
    components["CNS (GCS)"] = cns_pts

    # Renal (Creatinine or urine output)
    if creatinine < 1.2:
        renal_pts = 0
    elif creatinine < 2:
        renal_pts = 1
    elif creatinine < 3.5:
        renal_pts = 2
    elif creatinine < 5:
        renal_pts = 3
    else:
        renal_pts = 4

    # Check urine output if provided
    if urine_output_ml_day is not None:
        if urine_output_ml_day < 200:
            renal_pts = max(renal_pts, 4)
        elif urine_output_ml_day < 500:
            renal_pts = max(renal_pts, 3)

    score += renal_pts
    components["Renal"] = renal_pts

    # Mortality estimation
    if score <= 1:
        mortality = "<1%"
        risk = RiskLevel.LOW
    elif score <= 5:
        mortality = "~6%"
        risk = RiskLevel.LOW_MODERATE
    elif score <= 9:
        mortality = "~22%"
        risk = RiskLevel.MODERATE
    elif score <= 12:
        mortality = "~40%"
        risk = RiskLevel.HIGH
    else:
        mortality = ">50%"
        risk = RiskLevel.VERY_HIGH

    interpretation = f"SOFA Score {score}. ICU mortality: ~{mortality}"

    if score < 2:
        recommendations = [
            "Low organ dysfunction",
            "Continue monitoring",
            "Sepsis unlikely with score <2",
        ]
    elif score <= 6:
        recommendations = [
            "Moderate organ dysfunction",
            "Source control if infection suspected",
            "Serial SOFA monitoring",
            "Fluid resuscitation if septic shock",
        ]
    else:
        recommendations = [
            "Severe organ dysfunction",
            "Aggressive sepsis management",
            "Early antibiotics and source control",
            "Consider vasopressors",
            "Close ICU monitoring",
        ]

    return CalculatorResult(
        calculator_name="SOFA Score",
        score=score,
        score_unit="points",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Vincent JL, et al. Intensive Care Med 1996", "Singer M, et al. JAMA 2016 (Sepsis-3)"],
    )


# ============================================================================
# NEWS2 (National Early Warning Score 2)
# ============================================================================

def calculate_news2(
    respiratory_rate: int,
    spo2: float,  # %
    on_supplemental_o2: bool = False,
    temperature: float = 37.0,  # Celsius
    systolic_bp: int = 120,
    heart_rate: int = 80,
    consciousness: str = "alert",  # "alert", "verbal", "pain", "unresponsive" (AVPU) or "confusion"
    is_copd_target_88_92: bool = False,  # Use Scale 2 for COPD patients
) -> CalculatorResult:
    """Calculate NEWS2 score for clinical deterioration risk.

    Args:
        respiratory_rate: Respiratory rate per minute.
        spo2: Oxygen saturation %.
        on_supplemental_o2: True if on supplemental oxygen.
        temperature: Temperature in Celsius.
        systolic_bp: Systolic blood pressure in mmHg.
        heart_rate: Heart rate in bpm.
        consciousness: AVPU status or confusion.
        is_copd_target_88_92: Use SpO2 Scale 2 for COPD patients.

    Returns:
        CalculatorResult with NEWS2 score and response recommendations.
    """
    score = 0
    components = {}

    # Respiratory rate
    if respiratory_rate <= 8:
        rr_pts = 3
    elif respiratory_rate <= 11:
        rr_pts = 1
    elif respiratory_rate <= 20:
        rr_pts = 0
    elif respiratory_rate <= 24:
        rr_pts = 2
    else:
        rr_pts = 3
    score += rr_pts
    components["Respiratory rate"] = rr_pts

    # SpO2 (Scale 1 or Scale 2 for COPD)
    if is_copd_target_88_92:
        # Scale 2 for COPD patients with hypercapnic respiratory failure
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
        # Scale 1 (standard)
        if spo2 <= 91:
            spo2_pts = 3
        elif spo2 <= 93:
            spo2_pts = 2
        elif spo2 <= 95:
            spo2_pts = 1
        else:
            spo2_pts = 0
    score += spo2_pts
    components["SpO2"] = spo2_pts

    # Supplemental oxygen
    o2_pts = 2 if on_supplemental_o2 else 0
    score += o2_pts
    components["Supplemental O2"] = o2_pts

    # Temperature
    if temperature <= 35.0:
        temp_pts = 3
    elif temperature <= 36.0:
        temp_pts = 1
    elif temperature <= 38.0:
        temp_pts = 0
    elif temperature <= 39.0:
        temp_pts = 1
    else:
        temp_pts = 2
    score += temp_pts
    components["Temperature"] = temp_pts

    # Systolic BP
    if systolic_bp <= 90:
        sbp_pts = 3
    elif systolic_bp <= 100:
        sbp_pts = 2
    elif systolic_bp <= 110:
        sbp_pts = 1
    elif systolic_bp <= 219:
        sbp_pts = 0
    else:
        sbp_pts = 3
    score += sbp_pts
    components["Systolic BP"] = sbp_pts

    # Heart rate
    if heart_rate <= 40:
        hr_pts = 3
    elif heart_rate <= 50:
        hr_pts = 1
    elif heart_rate <= 90:
        hr_pts = 0
    elif heart_rate <= 110:
        hr_pts = 1
    elif heart_rate <= 130:
        hr_pts = 2
    else:
        hr_pts = 3
    score += hr_pts
    components["Heart rate"] = hr_pts

    # Consciousness
    consciousness_lower = consciousness.lower()
    if consciousness_lower == "alert" or consciousness_lower == "a":
        cons_pts = 0
    else:
        cons_pts = 3  # CVPU or confusion
    score += cons_pts
    components["Consciousness"] = cons_pts

    # Risk level and response
    # Check for single parameter score of 3
    single_extreme = any(pts == 3 for pts in [rr_pts, spo2_pts, temp_pts, sbp_pts, hr_pts, cons_pts])

    if score == 0:
        risk = RiskLevel.LOW
        interpretation = "NEWS2 = 0: Low clinical risk"
        recommendations = [
            "Continue routine NEWS monitoring",
            "Minimum 12-hourly observations",
        ]
    elif score <= 4:
        risk = RiskLevel.LOW if not single_extreme else RiskLevel.LOW_MODERATE
        if single_extreme:
            interpretation = f"NEWS2 = {score}: Low-medium risk (single parameter at 3)"
            recommendations = [
                "Urgent ward-based response",
                "Increase monitoring to 4-6 hourly minimum",
                "Inform registered nurse and medical team",
            ]
        else:
            interpretation = f"NEWS2 = {score}: Low clinical risk"
            recommendations = [
                "Continue routine monitoring",
                "Minimum 4-6 hourly observations",
                "RN to assess patient",
            ]
    elif score <= 6:
        risk = RiskLevel.MODERATE
        interpretation = f"NEWS2 = {score}: Medium clinical risk"
        recommendations = [
            "Urgent response required",
            "Hourly observations",
            "Urgent assessment by clinician",
            "Consider need for higher level of care",
        ]
    else:
        risk = RiskLevel.HIGH
        interpretation = f"NEWS2 = {score}: High clinical risk"
        recommendations = [
            "Emergency response required",
            "Continuous monitoring",
            "Urgent assessment by critical care team",
            "Consider ICU/HDU admission",
            "Treat as clinical emergency",
        ]

    return CalculatorResult(
        calculator_name="NEWS2 (National Early Warning Score 2)",
        score=score,
        score_unit="points",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Royal College of Physicians 2017"],
    )


# ============================================================================
# SIRS Criteria (Systemic Inflammatory Response Syndrome)
# ============================================================================

def calculate_sirs(
    temperature: float,  # Celsius
    heart_rate: int,
    respiratory_rate: int,
    paco2: float | None = None,  # mmHg
    wbc: float | None = None,  # 1000/mm³
    bands: float | None = None,  # % bands
) -> CalculatorResult:
    """Calculate SIRS criteria.

    Args:
        temperature: Body temperature in Celsius.
        heart_rate: Heart rate in bpm.
        respiratory_rate: Respiratory rate per minute.
        paco2: PaCO2 in mmHg (optional).
        wbc: WBC count in 1000/mm³ (optional).
        bands: Percentage of band forms (optional).

    Returns:
        CalculatorResult with SIRS criteria assessment.
    """
    criteria_met = 0
    components = {}

    # Temperature: >38°C or <36°C
    if temperature > 38 or temperature < 36:
        criteria_met += 1
        components["Temperature abnormal"] = 1
    else:
        components["Temperature normal"] = 0

    # Heart rate: >90 bpm
    if heart_rate > 90:
        criteria_met += 1
        components["Heart rate >90"] = 1
    else:
        components["Heart rate ≤90"] = 0

    # Respiratory: RR >20 or PaCO2 <32 mmHg
    if respiratory_rate > 20 or (paco2 is not None and paco2 < 32):
        criteria_met += 1
        components["Respiratory abnormal"] = 1
    else:
        components["Respiratory normal"] = 0

    # WBC: >12,000 or <4,000 or >10% bands
    if wbc is not None:
        if wbc > 12 or wbc < 4 or (bands is not None and bands > 10):
            criteria_met += 1
            components["WBC abnormal"] = 1
        else:
            components["WBC normal"] = 0

    # SIRS positive if ≥2 criteria met
    if criteria_met >= 2:
        risk = RiskLevel.MODERATE
        interpretation = f"SIRS positive ({criteria_met}/4 criteria met)"
        recommendations = [
            "SIRS criteria met - evaluate for infection source",
            "Consider sepsis workup (cultures, lactate)",
            "Monitor for organ dysfunction (qSOFA, SOFA)",
            "Early antibiotics if infection suspected",
        ]
    else:
        risk = RiskLevel.LOW
        interpretation = f"SIRS negative ({criteria_met}/4 criteria met)"
        recommendations = [
            "SIRS criteria not met",
            "Continue monitoring vital signs",
            "Investigate other causes of symptoms",
        ]

    return CalculatorResult(
        calculator_name="SIRS Criteria",
        score=criteria_met,
        score_unit="criteria",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Bone RC, et al. Chest 1992"],
    )


# ============================================================================
# Revised Cardiac Risk Index (RCRI / Lee Index)
# ============================================================================

def calculate_rcri(
    high_risk_surgery: bool = False,  # Intraperitoneal, intrathoracic, suprainguinal vascular
    history_of_ihd: bool = False,  # MI, positive exercise test, angina, nitrate use, Q waves
    history_of_chf: bool = False,  # CHF history, pulmonary edema, PND, bilateral rales, S3, BNP elevated
    history_of_cvd: bool = False,  # Stroke or TIA
    insulin_therapy: bool = False,  # Pre-operative insulin use
    preop_creatinine_over_2: bool = False,  # Cr >2 mg/dL
) -> CalculatorResult:
    """Calculate Revised Cardiac Risk Index (Lee Index) for perioperative cardiac risk.

    Uses data-driven definition from calculator_definitions.py.
    """
    return calculate_from_definition(
        "rcri",
        {
            "high_risk_surgery": high_risk_surgery,
            "history_of_ihd": history_of_ihd,
            "history_of_chf": history_of_chf,
            "history_of_cvd": history_of_cvd,
            "insulin_therapy": insulin_therapy,
            "preop_creatinine_over_2": preop_creatinine_over_2,
        },
    )


# ============================================================================
# Charlson Comorbidity Index (CCI)
# ============================================================================

def calculate_charlson(
    age: int,
    myocardial_infarction: bool = False,
    congestive_heart_failure: bool = False,
    peripheral_vascular_disease: bool = False,
    cerebrovascular_disease: bool = False,
    dementia: bool = False,
    chronic_pulmonary_disease: bool = False,
    connective_tissue_disease: bool = False,
    peptic_ulcer_disease: bool = False,
    mild_liver_disease: bool = False,
    diabetes_uncomplicated: bool = False,
    diabetes_with_complications: bool = False,
    hemiplegia: bool = False,
    moderate_severe_renal_disease: bool = False,
    solid_tumor_no_metastasis: bool = False,
    leukemia: bool = False,
    lymphoma: bool = False,
    moderate_severe_liver_disease: bool = False,
    solid_tumor_metastatic: bool = False,
    aids: bool = False,
) -> CalculatorResult:
    """Calculate Charlson Comorbidity Index.

    Args:
        age: Patient age in years.
        myocardial_infarction: History of MI.
        congestive_heart_failure: CHF.
        peripheral_vascular_disease: PVD.
        cerebrovascular_disease: CVA or TIA.
        dementia: Dementia.
        chronic_pulmonary_disease: COPD.
        connective_tissue_disease: Rheumatologic disease.
        peptic_ulcer_disease: PUD.
        mild_liver_disease: Mild liver disease.
        diabetes_uncomplicated: DM without complications.
        diabetes_with_complications: DM with end-organ damage.
        hemiplegia: Hemiplegia or paraplegia.
        moderate_severe_renal_disease: CKD stage 4-5.
        solid_tumor_no_metastasis: Cancer without metastasis.
        leukemia: Leukemia.
        lymphoma: Lymphoma.
        moderate_severe_liver_disease: Cirrhosis with complications.
        solid_tumor_metastatic: Metastatic solid tumor.
        aids: AIDS.

    Returns:
        CalculatorResult with mortality prediction.
    """
    score = 0
    components = {}

    # 1-point conditions
    one_point = [
        (myocardial_infarction, "MI"),
        (congestive_heart_failure, "CHF"),
        (peripheral_vascular_disease, "PVD"),
        (cerebrovascular_disease, "CVD"),
        (dementia, "Dementia"),
        (chronic_pulmonary_disease, "COPD"),
        (connective_tissue_disease, "Connective tissue"),
        (peptic_ulcer_disease, "PUD"),
        (mild_liver_disease, "Mild liver disease"),
        (diabetes_uncomplicated, "DM uncomplicated"),
    ]

    for condition, name in one_point:
        if condition:
            score += 1
            components[name] = 1

    # 2-point conditions
    two_point = [
        (diabetes_with_complications, "DM with complications"),
        (hemiplegia, "Hemiplegia"),
        (moderate_severe_renal_disease, "Renal disease"),
        (solid_tumor_no_metastasis, "Solid tumor"),
        (leukemia, "Leukemia"),
        (lymphoma, "Lymphoma"),
    ]

    for condition, name in two_point:
        if condition:
            score += 2
            components[name] = 2

    # 3-point conditions
    if moderate_severe_liver_disease:
        score += 3
        components["Severe liver disease"] = 3

    # 6-point conditions
    six_point = [
        (solid_tumor_metastatic, "Metastatic tumor"),
        (aids, "AIDS"),
    ]

    for condition, name in six_point:
        if condition:
            score += 6
            components[name] = 6

    # Age adjustment
    if age >= 80:
        age_pts = 4
    elif age >= 70:
        age_pts = 3
    elif age >= 60:
        age_pts = 2
    elif age >= 50:
        age_pts = 1
    else:
        age_pts = 0
    score += age_pts
    components["Age adjustment"] = age_pts

    # Mortality estimation (10-year survival)
    if score == 0:
        survival_10yr = "98%"
        risk = RiskLevel.LOW
    elif score == 1:
        survival_10yr = "96%"
        risk = RiskLevel.LOW
    elif score == 2:
        survival_10yr = "90%"
        risk = RiskLevel.LOW_MODERATE
    elif score == 3:
        survival_10yr = "77%"
        risk = RiskLevel.MODERATE
    elif score == 4:
        survival_10yr = "53%"
        risk = RiskLevel.MODERATE_HIGH
    elif score <= 6:
        survival_10yr = "21%"
        risk = RiskLevel.HIGH
    else:
        survival_10yr = "<21%"
        risk = RiskLevel.VERY_HIGH

    interpretation = f"Charlson Comorbidity Index: {score}. Estimated 10-year survival: ~{survival_10yr}"

    if score <= 2:
        recommendations = [
            "Low comorbidity burden",
            "Standard age-appropriate screening",
            "Preventive care as indicated",
        ]
    elif score <= 4:
        recommendations = [
            "Moderate comorbidity burden",
            "Consider functional status assessment",
            "Coordinate care among specialists",
            "Medication reconciliation important",
        ]
    else:
        recommendations = [
            "High comorbidity burden",
            "Goals of care discussion",
            "Palliative care consultation may benefit",
            "Focus on quality of life",
            "Careful medication review",
        ]

    return CalculatorResult(
        calculator_name="Charlson Comorbidity Index",
        score=score,
        score_unit="points",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Charlson ME, et al. J Chronic Dis 1987"],
    )


# ============================================================================
# PSI/PORT Score (Pneumonia Severity Index)
# ============================================================================

def calculate_psi_port(
    age: int,
    female: bool,
    nursing_home_resident: bool = False,
    neoplastic_disease: bool = False,
    liver_disease: bool = False,
    chf: bool = False,
    cerebrovascular_disease: bool = False,
    renal_disease: bool = False,
    altered_mental_status: bool = False,
    respiratory_rate_over_30: bool = False,
    systolic_bp_under_90: bool = False,
    temperature_under_35_or_over_40: bool = False,
    heart_rate_over_125: bool = False,
    arterial_ph_under_7_35: bool = False,
    bun_over_30: bool = False,
    sodium_under_130: bool = False,
    glucose_over_250: bool = False,
    hematocrit_under_30: bool = False,
    pao2_under_60_or_spo2_under_90: bool = False,
    pleural_effusion: bool = False,
) -> CalculatorResult:
    """Calculate PSI/PORT score for pneumonia severity.

    Args:
        age: Patient age in years.
        female: True if female (subtract 10 points).
        nursing_home_resident: Nursing home resident.
        neoplastic_disease: Active cancer.
        liver_disease: Liver disease.
        chf: Congestive heart failure.
        cerebrovascular_disease: Stroke/CVD.
        renal_disease: Renal disease.
        altered_mental_status: Altered mental status.
        respiratory_rate_over_30: RR >30/min.
        systolic_bp_under_90: SBP <90 mmHg.
        temperature_under_35_or_over_40: Temp <35°C or >40°C.
        heart_rate_over_125: HR >125 bpm.
        arterial_ph_under_7_35: pH <7.35.
        bun_over_30: BUN >30 mg/dL.
        sodium_under_130: Na <130 mEq/L.
        glucose_over_250: Glucose >250 mg/dL.
        hematocrit_under_30: Hct <30%.
        pao2_under_60_or_spo2_under_90: PaO2 <60 or SpO2 <90%.
        pleural_effusion: Pleural effusion on imaging.

    Returns:
        CalculatorResult with pneumonia severity class and mortality.
    """
    score = age
    components = {"Age": age}

    if female:
        score -= 10
        components["Female"] = -10

    # Nursing home
    if nursing_home_resident:
        score += 10
        components["Nursing home"] = 10

    # Comorbidities
    comorbidities = [
        (neoplastic_disease, "Neoplastic disease", 30),
        (liver_disease, "Liver disease", 20),
        (chf, "CHF", 10),
        (cerebrovascular_disease, "CVD", 10),
        (renal_disease, "Renal disease", 10),
    ]
    for condition, name, points in comorbidities:
        if condition:
            score += points
            components[name] = points

    # Physical exam findings
    exam_findings = [
        (altered_mental_status, "Altered mental status", 20),
        (respiratory_rate_over_30, "RR >30", 20),
        (systolic_bp_under_90, "SBP <90", 20),
        (temperature_under_35_or_over_40, "Temp abnormal", 15),
        (heart_rate_over_125, "HR >125", 10),
    ]
    for condition, name, points in exam_findings:
        if condition:
            score += points
            components[name] = points

    # Lab/imaging findings
    lab_findings = [
        (arterial_ph_under_7_35, "pH <7.35", 30),
        (bun_over_30, "BUN >30", 20),
        (sodium_under_130, "Na <130", 20),
        (glucose_over_250, "Glucose >250", 10),
        (hematocrit_under_30, "Hct <30", 10),
        (pao2_under_60_or_spo2_under_90, "Hypoxemia", 10),
        (pleural_effusion, "Pleural effusion", 10),
    ]
    for condition, name, points in lab_findings:
        if condition:
            score += points
            components[name] = points

    # Risk class assignment
    if score <= 50:
        risk_class = "I"
        mortality = "0.1%"
        risk = RiskLevel.LOW
        recommendations = [
            "PSI Class I - Outpatient treatment appropriate",
            "Oral antibiotics",
            "Close follow-up in 24-48 hours",
        ]
    elif score <= 70:
        risk_class = "II"
        mortality = "0.6%"
        risk = RiskLevel.LOW
        recommendations = [
            "PSI Class II - Outpatient treatment appropriate",
            "Oral antibiotics",
            "Close follow-up in 24-48 hours",
        ]
    elif score <= 90:
        risk_class = "III"
        mortality = "2.8%"
        risk = RiskLevel.LOW_MODERATE
        recommendations = [
            "PSI Class III - Consider brief inpatient observation",
            "May be managed as outpatient with close follow-up",
            "Social situation and ability to take PO meds important",
        ]
    elif score <= 130:
        risk_class = "IV"
        mortality = "8.2%"
        risk = RiskLevel.MODERATE
        recommendations = [
            "PSI Class IV - Inpatient treatment recommended",
            "IV antibiotics",
            "Monitor for complications",
        ]
    else:
        risk_class = "V"
        mortality = "29.2%"
        risk = RiskLevel.HIGH
        recommendations = [
            "PSI Class V - Inpatient treatment required",
            "Consider ICU admission",
            "Broad-spectrum IV antibiotics",
            "Close monitoring for sepsis/respiratory failure",
        ]

    interpretation = f"PSI Class {risk_class} (score {score}). 30-day mortality: ~{mortality}"

    return CalculatorResult(
        calculator_name="PSI/PORT Score",
        score=score,
        score_unit="points",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Fine MJ, et al. NEJM 1997"],
    )


# ============================================================================
# ABCD2 Score (TIA Stroke Risk)
# ============================================================================

def calculate_abcd2(
    age_60_or_older: bool = False,
    blood_pressure_140_90_or_higher: bool = False,
    clinical_unilateral_weakness: bool = False,
    clinical_speech_impairment_no_weakness: bool = False,
    duration_60_or_more_minutes: bool = False,
    duration_10_to_59_minutes: bool = False,
    diabetes: bool = False,
) -> CalculatorResult:
    """Calculate ABCD2 score for stroke risk after TIA.

    Args:
        age_60_or_older: Age ≥60 years.
        blood_pressure_140_90_or_higher: SBP ≥140 or DBP ≥90 mmHg.
        clinical_unilateral_weakness: Unilateral weakness.
        clinical_speech_impairment_no_weakness: Speech impairment without weakness.
        duration_60_or_more_minutes: Symptoms ≥60 minutes.
        duration_10_to_59_minutes: Symptoms 10-59 minutes.
        diabetes: History of diabetes.

    Returns:
        CalculatorResult with 2-day and 7-day stroke risk.
    """
    score = 0
    components = {}

    # A - Age
    if age_60_or_older:
        score += 1
        components["Age ≥60"] = 1

    # B - Blood pressure
    if blood_pressure_140_90_or_higher:
        score += 1
        components["BP ≥140/90"] = 1

    # C - Clinical features
    if clinical_unilateral_weakness:
        score += 2
        components["Unilateral weakness"] = 2
    elif clinical_speech_impairment_no_weakness:
        score += 1
        components["Speech impairment"] = 1

    # D - Duration
    if duration_60_or_more_minutes:
        score += 2
        components["Duration ≥60 min"] = 2
    elif duration_10_to_59_minutes:
        score += 1
        components["Duration 10-59 min"] = 1

    # D - Diabetes
    if diabetes:
        score += 1
        components["Diabetes"] = 1

    # Risk stratification
    if score <= 3:
        risk_2day = "1.0%"
        risk_7day = "1.2%"
        risk = RiskLevel.LOW
        recommendations = [
            "Low risk - may be appropriate for outpatient workup",
            "Complete workup within 48-72 hours",
            "Brain and vascular imaging",
            "Aspirin 325mg immediately",
        ]
    elif score <= 5:
        risk_2day = "4.1%"
        risk_7day = "5.9%"
        risk = RiskLevel.MODERATE
        recommendations = [
            "Moderate risk - consider hospital admission",
            "Expedited workup recommended",
            "Brain MRI with DWI",
            "Carotid imaging",
            "Cardiac evaluation (ECG, echo)",
            "Dual antiplatelet therapy (DAPT) for 21 days",
        ]
    else:
        risk_2day = "8.1%"
        risk_7day = "11.7%"
        risk = RiskLevel.HIGH
        recommendations = [
            "High risk - hospital admission recommended",
            "Urgent neurology consultation",
            "Immediate brain and vascular imaging",
            "Consider thrombolytics if symptoms recur",
            "DAPT (aspirin + clopidogrel) for 21 days",
            "Aggressive risk factor management",
        ]

    interpretation = f"ABCD2 Score {score}. 2-day stroke risk: {risk_2day}, 7-day risk: {risk_7day}"

    return CalculatorResult(
        calculator_name="ABCD2 Score",
        score=score,
        score_unit="points",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Johnston SC, et al. Lancet 2007"],
    )


# ============================================================================
# Corrected Sodium (Hyperglycemia)
# ============================================================================

def calculate_corrected_sodium(
    measured_sodium: float,  # mEq/L
    glucose: float,  # mg/dL
) -> CalculatorResult:
    """Calculate corrected sodium for hyperglycemia.

    Uses the Hillier formula: Na + 2.4 × [(Glucose - 100) / 100]

    Args:
        measured_sodium: Measured serum sodium in mEq/L.
        glucose: Serum glucose in mg/dL.

    Returns:
        CalculatorResult with corrected sodium value.
    """
    # Hillier formula (more accurate than Katz)
    correction = 2.4 * ((glucose - 100) / 100)
    corrected_na = measured_sodium + correction

    components = {
        "Measured Na": measured_sodium,
        "Glucose": glucose,
        "Correction factor": round(correction, 1),
    }

    if corrected_na < 135:
        risk = RiskLevel.MODERATE
        interpretation = f"Corrected Na: {corrected_na:.1f} mEq/L - Hyponatremia persists"
        recommendations = [
            "True hyponatremia present",
            "Evaluate volume status",
            "Check serum osmolality and urine studies",
            "Treat underlying cause",
        ]
    elif corrected_na > 145:
        risk = RiskLevel.MODERATE
        interpretation = f"Corrected Na: {corrected_na:.1f} mEq/L - Hypernatremia revealed"
        recommendations = [
            "True hypernatremia present",
            "Water deficit should be corrected",
            "Free water replacement needed",
            "Monitor Na correction rate (<10-12 mEq/L per 24h)",
        ]
    else:
        risk = RiskLevel.LOW
        interpretation = f"Corrected Na: {corrected_na:.1f} mEq/L - Normal range"
        recommendations = [
            "Sodium will normalize with glucose treatment",
            "Dilutional hyponatremia from hyperglycemia",
            "Focus on treating hyperglycemia",
        ]

    return CalculatorResult(
        calculator_name="Corrected Sodium (Hyperglycemia)",
        score=round(corrected_na, 1),
        score_unit="mEq/L",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Hillier TA, et al. Am J Med 1999"],
    )


# ============================================================================
# Corrected Calcium (Albumin)
# ============================================================================

def calculate_corrected_calcium(
    measured_calcium: float,  # mg/dL
    albumin: float,  # g/dL
) -> CalculatorResult:
    """Calculate corrected calcium for hypoalbuminemia.

    Formula: Corrected Ca = Measured Ca + 0.8 × (4 - Albumin)

    Args:
        measured_calcium: Measured serum calcium in mg/dL.
        albumin: Serum albumin in g/dL.

    Returns:
        CalculatorResult with corrected calcium value.
    """
    correction = 0.8 * (4 - albumin)
    corrected_ca = measured_calcium + correction

    components = {
        "Measured Ca": measured_calcium,
        "Albumin": albumin,
        "Correction factor": round(correction, 2),
    }

    if corrected_ca < 8.5:
        risk = RiskLevel.MODERATE
        interpretation = f"Corrected Ca: {corrected_ca:.1f} mg/dL - True hypocalcemia"
        recommendations = [
            "True hypocalcemia present",
            "Check PTH, vitamin D, magnesium",
            "ECG for QT prolongation",
            "IV calcium if symptomatic or severely low",
        ]
    elif corrected_ca > 10.5:
        risk = RiskLevel.MODERATE
        interpretation = f"Corrected Ca: {corrected_ca:.1f} mg/dL - True hypercalcemia"
        recommendations = [
            "True hypercalcemia present",
            "Check PTH and PTHrP",
            "Evaluate for malignancy if PTH suppressed",
            "IV fluids and bisphosphonates for severe cases",
        ]
    else:
        risk = RiskLevel.LOW
        interpretation = f"Corrected Ca: {corrected_ca:.1f} mg/dL - Normal range"
        recommendations = [
            "Calcium is normal when corrected for albumin",
            "Low measured calcium due to hypoalbuminemia",
            "No calcium replacement needed",
        ]

    return CalculatorResult(
        calculator_name="Corrected Calcium (Albumin)",
        score=round(corrected_ca, 1),
        score_unit="mg/dL",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Payne RB, et al. Br Med J 1973"],
    )


# ============================================================================
# Anion Gap
# ============================================================================

def calculate_anion_gap(
    sodium: float,  # mEq/L
    chloride: float,  # mEq/L
    bicarbonate: float,  # mEq/L
    albumin: float | None = None,  # g/dL for correction
) -> CalculatorResult:
    """Calculate serum anion gap.

    Formula: AG = Na - (Cl + HCO3)
    Corrected AG = AG + 2.5 × (4 - Albumin)

    Args:
        sodium: Serum sodium in mEq/L.
        chloride: Serum chloride in mEq/L.
        bicarbonate: Serum bicarbonate in mEq/L.
        albumin: Serum albumin in g/dL (optional, for correction).

    Returns:
        CalculatorResult with anion gap assessment.
    """
    ag = sodium - (chloride + bicarbonate)

    components = {
        "Sodium": sodium,
        "Chloride": chloride,
        "Bicarbonate": bicarbonate,
        "Anion Gap": round(ag, 1),
    }

    # Correct for albumin if provided
    if albumin is not None:
        ag_correction = 2.5 * (4 - albumin)
        corrected_ag = ag + ag_correction
        components["Albumin"] = albumin
        components["Corrected AG"] = round(corrected_ag, 1)
        ag_for_interpretation = corrected_ag
    else:
        ag_for_interpretation = ag

    # Interpretation (normal AG 8-12)
    if ag_for_interpretation > 12:
        risk = RiskLevel.MODERATE
        interpretation = f"Elevated anion gap: {ag_for_interpretation:.1f} mEq/L"
        recommendations = [
            "High anion gap metabolic acidosis (HAGMA)",
            "Consider MUDPILES: Methanol, Uremia, DKA, Propylene glycol, INH/Iron, Lactic acidosis, Ethylene glycol, Salicylates",
            "Check lactate, ketones, BUN/Cr, toxicology",
            "Calculate osmolar gap if ingestion suspected",
            "Calculate delta-delta ratio",
        ]
    elif ag_for_interpretation < 8:
        risk = RiskLevel.LOW_MODERATE
        interpretation = f"Low anion gap: {ag_for_interpretation:.1f} mEq/L"
        recommendations = [
            "Low AG may indicate hypoalbuminemia, multiple myeloma, lithium toxicity",
            "Check albumin if not already done",
            "Consider SPEP if myeloma suspected",
        ]
    else:
        risk = RiskLevel.LOW
        interpretation = f"Normal anion gap: {ag_for_interpretation:.1f} mEq/L"
        recommendations = [
            "Normal anion gap",
            "If acidosis present, consider non-AG causes (RTA, diarrhea, normal saline excess)",
        ]

    return CalculatorResult(
        calculator_name="Anion Gap",
        score=round(ag_for_interpretation, 1),
        score_unit="mEq/L",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Kraut JA, Madias NE. NEJM 2014"],
    )


# ============================================================================
# Serum Osmolality
# ============================================================================

def calculate_serum_osmolality(
    sodium: float,  # mEq/L
    glucose: float,  # mg/dL
    bun: float,  # mg/dL
    measured_osmolality: float | None = None,  # mOsm/kg for gap calculation
) -> CalculatorResult:
    """Calculate serum osmolality and osmolar gap.

    Formula: Calculated Osm = 2×Na + Glucose/18 + BUN/2.8
    Osmolar Gap = Measured Osm - Calculated Osm

    Args:
        sodium: Serum sodium in mEq/L.
        glucose: Serum glucose in mg/dL.
        bun: Blood urea nitrogen in mg/dL.
        measured_osmolality: Measured serum osmolality (optional).

    Returns:
        CalculatorResult with osmolality and gap assessment.
    """
    calc_osm = 2 * sodium + glucose / 18 + bun / 2.8

    components = {
        "Sodium contribution": round(2 * sodium, 1),
        "Glucose contribution": round(glucose / 18, 1),
        "BUN contribution": round(bun / 2.8, 1),
        "Calculated osmolality": round(calc_osm, 1),
    }

    osm_gap = None
    if measured_osmolality is not None:
        osm_gap = measured_osmolality - calc_osm
        components["Measured osmolality"] = measured_osmolality
        components["Osmolar gap"] = round(osm_gap, 1)

    # Interpretation
    if osm_gap is not None and osm_gap > 10:
        risk = RiskLevel.HIGH
        interpretation = f"Calculated Osm: {calc_osm:.0f}, Osmolar gap: {osm_gap:.0f} (elevated)"
        recommendations = [
            "Elevated osmolar gap suggests unmeasured osmoles",
            "Consider toxic alcohols: methanol, ethylene glycol, isopropyl alcohol",
            "Consider ethanol (calculate ethanol contribution)",
            "Urgent toxicology workup",
            "May need antidote (fomepizole) and dialysis",
        ]
    elif calc_osm > 320:
        risk = RiskLevel.HIGH
        interpretation = f"Calculated Osm: {calc_osm:.0f} mOsm/kg - Hyperosmolar"
        recommendations = [
            "Hyperosmolar state",
            "Evaluate for HHS, DKA, severe hypernatremia",
            "Careful fluid management",
            "Monitor for cerebral edema with rapid correction",
        ]
    elif calc_osm < 275:
        risk = RiskLevel.MODERATE
        interpretation = f"Calculated Osm: {calc_osm:.0f} mOsm/kg - Hypoosmolar"
        recommendations = [
            "Hypoosmolar state - risk of cerebral edema",
            "Evaluate cause of hyponatremia",
            "Fluid restrict if SIADH suspected",
            "Careful correction to avoid osmotic demyelination",
        ]
    else:
        risk = RiskLevel.LOW
        interpretation = f"Calculated Osm: {calc_osm:.0f} mOsm/kg - Normal range"
        recommendations = [
            "Serum osmolality within normal limits",
        ]

    return CalculatorResult(
        calculator_name="Serum Osmolality",
        score=round(calc_osm, 0),
        score_unit="mOsm/kg",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Purssell RA, et al. Ann Emerg Med 2001"],
    )


# ============================================================================
# Mean Arterial Pressure (MAP)
# ============================================================================

def calculate_map(
    systolic_bp: float,
    diastolic_bp: float,
) -> CalculatorResult:
    """Calculate Mean Arterial Pressure.

    Formula: MAP = DBP + 1/3(SBP - DBP) = (SBP + 2×DBP) / 3

    Args:
        systolic_bp: Systolic blood pressure in mmHg.
        diastolic_bp: Diastolic blood pressure in mmHg.

    Returns:
        CalculatorResult with MAP value.
    """
    map_value = (systolic_bp + 2 * diastolic_bp) / 3

    components = {
        "Systolic BP": systolic_bp,
        "Diastolic BP": diastolic_bp,
    }

    if map_value < 60:
        risk = RiskLevel.VERY_HIGH
        interpretation = f"MAP: {map_value:.0f} mmHg - Hypotension/Shock"
        recommendations = [
            "MAP <60-65 indicates inadequate organ perfusion",
            "Immediate fluid resuscitation",
            "Consider vasopressors (target MAP ≥65)",
            "Identify and treat underlying cause",
            "ICU admission likely needed",
        ]
    elif map_value < 70:
        risk = RiskLevel.HIGH
        interpretation = f"MAP: {map_value:.0f} mmHg - Low (borderline perfusion)"
        recommendations = [
            "MAP borderline for organ perfusion",
            "Monitor closely",
            "IV fluids if hypovolemic",
            "Target MAP ≥65 in sepsis",
        ]
    elif map_value > 130:
        risk = RiskLevel.HIGH
        interpretation = f"MAP: {map_value:.0f} mmHg - Severely elevated"
        recommendations = [
            "Severe hypertension",
            "Evaluate for hypertensive emergency",
            "Check for end-organ damage",
            "May need IV antihypertensives",
        ]
    elif map_value > 110:
        risk = RiskLevel.MODERATE
        interpretation = f"MAP: {map_value:.0f} mmHg - Elevated"
        recommendations = [
            "Elevated blood pressure",
            "Optimize oral antihypertensives",
            "Lifestyle modifications",
        ]
    else:
        risk = RiskLevel.LOW
        interpretation = f"MAP: {map_value:.0f} mmHg - Normal range"
        recommendations = [
            "MAP within normal limits (70-100 mmHg)",
            "Adequate organ perfusion pressure",
        ]

    return CalculatorResult(
        calculator_name="Mean Arterial Pressure (MAP)",
        score=round(map_value, 0),
        score_unit="mmHg",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Standard hemodynamic calculation"],
    )


# ============================================================================
# A-a Gradient (Alveolar-arterial oxygen gradient)
# ============================================================================

def calculate_aa_gradient(
    pao2: float,  # mmHg
    paco2: float,  # mmHg
    fio2: float = 0.21,  # Fraction (default room air)
    age: int | None = None,  # For expected normal calculation
    atmospheric_pressure: float = 760,  # mmHg (sea level)
) -> CalculatorResult:
    """Calculate Alveolar-arterial oxygen gradient.

    Formula: A-a gradient = PAO2 - PaO2
    PAO2 = (FiO2 × (Patm - 47)) - (PaCO2 / 0.8)

    Args:
        pao2: Arterial PaO2 in mmHg.
        paco2: Arterial PaCO2 in mmHg.
        fio2: Fraction of inspired oxygen (0.21-1.0).
        age: Patient age (for expected normal calculation).
        atmospheric_pressure: Atmospheric pressure in mmHg.

    Returns:
        CalculatorResult with A-a gradient assessment.
    """
    # Calculate alveolar oxygen (PAO2)
    pao2_alveolar = (fio2 * (atmospheric_pressure - 47)) - (paco2 / 0.8)
    aa_gradient = pao2_alveolar - pao2

    components = {
        "PAO2 (alveolar)": round(pao2_alveolar, 1),
        "PaO2 (arterial)": pao2,
        "FiO2": fio2,
        "A-a gradient": round(aa_gradient, 1),
    }

    # Expected normal A-a gradient = (Age/4) + 4 on room air
    expected_normal = None
    if age is not None and fio2 <= 0.21:
        expected_normal = (age / 4) + 4
        components["Expected normal (age-based)"] = round(expected_normal, 1)

    # Interpretation
    is_elevated = aa_gradient > 15 or (expected_normal and aa_gradient > expected_normal + 5)

    if is_elevated:
        risk = RiskLevel.MODERATE
        interpretation = f"A-a gradient: {aa_gradient:.0f} mmHg (elevated)"
        recommendations = [
            "Elevated A-a gradient indicates V/Q mismatch or diffusion impairment",
            "Consider: PE, pneumonia, pulmonary edema, ARDS, interstitial lung disease",
            "Further workup based on clinical context",
            "Consider CT chest or V/Q scan if PE suspected",
        ]
    else:
        risk = RiskLevel.LOW
        interpretation = f"A-a gradient: {aa_gradient:.0f} mmHg (normal)"
        recommendations = [
            "Normal A-a gradient suggests hypoventilation or low FiO2 as cause",
            "Consider: sedation, neuromuscular weakness, CNS depression",
            "High altitude exposure",
        ]

    return CalculatorResult(
        calculator_name="A-a Gradient",
        score=round(aa_gradient, 0),
        score_unit="mmHg",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Standard pulmonary physiology calculation"],
    )


# ============================================================================
# QTc Calculation (Corrected QT Interval)
# ============================================================================

def calculate_qtc(
    qt_interval: float,  # milliseconds
    heart_rate: int,  # bpm
    formula: str = "bazett",  # "bazett", "fridericia", "framingham"
) -> CalculatorResult:
    """Calculate corrected QT interval.

    Bazett: QTc = QT / √RR
    Fridericia: QTc = QT / ∛RR
    Framingham: QTc = QT + 0.154 × (1 - RR)

    Args:
        qt_interval: QT interval in milliseconds.
        heart_rate: Heart rate in bpm.
        formula: Correction formula to use.

    Returns:
        CalculatorResult with QTc value.
    """
    rr_interval = 60 / heart_rate  # RR interval in seconds

    if formula.lower() == "bazett":
        qtc = qt_interval / math.sqrt(rr_interval)
        formula_name = "Bazett"
    elif formula.lower() == "fridericia":
        qtc = qt_interval / (rr_interval ** (1/3))
        formula_name = "Fridericia"
    elif formula.lower() == "framingham":
        qtc = qt_interval + 154 * (1 - rr_interval)
        formula_name = "Framingham"
    else:
        qtc = qt_interval / math.sqrt(rr_interval)
        formula_name = "Bazett"

    components = {
        "QT interval": qt_interval,
        "Heart rate": heart_rate,
        "RR interval": round(rr_interval * 1000, 0),  # Convert to ms
        "Formula": formula_name,
    }

    # Interpretation (using standard cutoffs)
    if qtc > 500:
        risk = RiskLevel.HIGH
        interpretation = f"QTc: {qtc:.0f} ms - Significantly prolonged"
        recommendations = [
            "High risk of Torsades de Pointes",
            "Discontinue QT-prolonging medications",
            "Check electrolytes (K, Mg, Ca)",
            "Continuous cardiac monitoring",
            "Avoid additional QT-prolonging drugs",
            "Cardiology consultation",
        ]
    elif qtc > 470:  # Male >450, Female >470 generally
        risk = RiskLevel.MODERATE
        interpretation = f"QTc: {qtc:.0f} ms - Prolonged"
        recommendations = [
            "Review medications for QT prolongation",
            "Check and correct electrolytes",
            "Monitor QTc serially",
            "Avoid adding QT-prolonging drugs",
        ]
    elif qtc < 350:
        risk = RiskLevel.LOW_MODERATE
        interpretation = f"QTc: {qtc:.0f} ms - Short QT"
        recommendations = [
            "Short QT syndrome is rare but associated with arrhythmias",
            "Consider genetic testing if persistent",
            "Cardiology evaluation recommended",
        ]
    else:
        risk = RiskLevel.LOW
        interpretation = f"QTc: {qtc:.0f} ms - Normal range"
        recommendations = [
            "QTc within normal limits",
            "Continue monitoring if on QT-prolonging medications",
        ]

    return CalculatorResult(
        calculator_name=f"QTc ({formula_name})",
        score=round(qtc, 0),
        score_unit="ms",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Bazett HC. Heart 1920", "Fridericia LS. Acta Med Scand 1920"],
    )


# ============================================================================
# Maintenance IV Fluids (Holliday-Segar)
# ============================================================================

def calculate_maintenance_fluids(
    weight_kg: float,
) -> CalculatorResult:
    """Calculate maintenance IV fluid rate using Holliday-Segar formula.

    4-2-1 Rule:
    - 4 mL/kg/hr for first 10 kg
    - 2 mL/kg/hr for next 10 kg (11-20 kg)
    - 1 mL/kg/hr for each kg above 20 kg

    Args:
        weight_kg: Patient weight in kilograms.

    Returns:
        CalculatorResult with maintenance fluid rate.
    """
    if weight_kg <= 10:
        rate = 4 * weight_kg
    elif weight_kg <= 20:
        rate = 40 + 2 * (weight_kg - 10)
    else:
        rate = 60 + 1 * (weight_kg - 20)

    daily_volume = rate * 24

    components = {
        "Weight": weight_kg,
        "Hourly rate": round(rate, 1),
        "Daily volume": round(daily_volume, 0),
    }

    risk = RiskLevel.LOW
    interpretation = f"Maintenance fluids: {rate:.0f} mL/hr ({daily_volume:.0f} mL/day)"
    recommendations = [
        "Standard maintenance fluid calculation",
        "Adjust for ongoing losses (fever, diarrhea, surgical drains)",
        "Consider insensible losses in calculation",
        "Monitor electrolytes and fluid balance",
        "Reduce in patients with renal or cardiac impairment",
    ]

    return CalculatorResult(
        calculator_name="Maintenance IV Fluids (Holliday-Segar)",
        score=round(rate, 0),
        score_unit="mL/hr",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Holliday MA, Segar WE. Pediatrics 1957"],
    )


# ============================================================================
# Parkland Formula (Burn Resuscitation)
# ============================================================================

def calculate_parkland_formula(
    weight_kg: float,
    tbsa_percent: float,  # Total body surface area burned (%)
) -> CalculatorResult:
    """Calculate fluid resuscitation for burn patients using Parkland formula.

    Formula: 4 mL × weight (kg) × %TBSA burned
    Give half in first 8 hours, remainder over next 16 hours.

    Args:
        weight_kg: Patient weight in kilograms.
        tbsa_percent: Percentage of total body surface area burned.

    Returns:
        CalculatorResult with fluid resuscitation volumes.
    """
    total_24hr = 4 * weight_kg * tbsa_percent
    first_8hr = total_24hr / 2
    next_16hr = total_24hr / 2
    first_8hr_rate = first_8hr / 8
    next_16hr_rate = next_16hr / 16

    components = {
        "Weight": weight_kg,
        "TBSA burned": tbsa_percent,
        "Total 24hr volume": round(total_24hr, 0),
        "First 8hr volume": round(first_8hr, 0),
        "First 8hr rate": round(first_8hr_rate, 0),
        "Next 16hr volume": round(next_16hr, 0),
        "Next 16hr rate": round(next_16hr_rate, 0),
    }

    if tbsa_percent >= 50:
        risk = RiskLevel.VERY_HIGH
    elif tbsa_percent >= 30:
        risk = RiskLevel.HIGH
    elif tbsa_percent >= 20:
        risk = RiskLevel.MODERATE
    else:
        risk = RiskLevel.LOW_MODERATE

    interpretation = f"Parkland: {total_24hr:.0f} mL over 24hr for {tbsa_percent}% TBSA burn"
    recommendations = [
        f"First 8 hours: {first_8hr:.0f} mL ({first_8hr_rate:.0f} mL/hr) - from time of burn",
        f"Next 16 hours: {next_16hr:.0f} mL ({next_16hr_rate:.0f} mL/hr)",
        "Use Lactated Ringer's solution",
        "Titrate to urine output 0.5-1 mL/kg/hr (adults)",
        "Consider albumin after 24 hours if needed",
        "Burn center transfer for major burns",
    ]

    return CalculatorResult(
        calculator_name="Parkland Formula (Burn Resuscitation)",
        score=round(total_24hr, 0),
        score_unit="mL/24hr",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Baxter CR, Shires T. Surg Clin North Am 1968"],
    )


# ============================================================================
# BISAP Score (Acute Pancreatitis Severity)
# ============================================================================

def calculate_bisap(
    bun_over_25: bool = False,
    impaired_mental_status: bool = False,
    sirs_criteria_2_or_more: bool = False,
    age_over_60: bool = False,
    pleural_effusion: bool = False,
) -> CalculatorResult:
    """Calculate BISAP score for acute pancreatitis mortality prediction.

    Uses data-driven definition from calculator_definitions.py.
    """
    return calculate_from_definition(
        "bisap",
        {
            "bun_over_25": bun_over_25,
            "impaired_mental_status": impaired_mental_status,
            "sirs_present": sirs_criteria_2_or_more,  # Map to definition's criterion name
            "age_over_60": age_over_60,
            "pleural_effusion": pleural_effusion,
        },
    )


# ============================================================================
# Centor Score (Strep Pharyngitis)
# ============================================================================

def calculate_centor(
    tonsillar_exudates: bool = False,
    tender_anterior_cervical_adenopathy: bool = False,
    fever_over_38: bool = False,
    absence_of_cough: bool = False,
    age_3_to_14: bool = False,
    age_15_to_44: bool = False,
    age_45_and_older: bool = False,
) -> CalculatorResult:
    """Calculate Modified Centor Score (McIsaac) for strep pharyngitis.

    Args:
        tonsillar_exudates: Presence of tonsillar exudates.
        tender_anterior_cervical_adenopathy: Tender anterior cervical nodes.
        fever_over_38: History of fever >38°C (100.4°F).
        absence_of_cough: Absence of cough.
        age_3_to_14: Age 3-14 years (+1 point).
        age_15_to_44: Age 15-44 years (0 points).
        age_45_and_older: Age ≥45 years (-1 point).

    Returns:
        CalculatorResult with strep probability and treatment recommendations.
    """
    score = 0
    components = {}

    if tonsillar_exudates:
        score += 1
        components["Tonsillar exudates"] = 1
    if tender_anterior_cervical_adenopathy:
        score += 1
        components["Cervical adenopathy"] = 1
    if fever_over_38:
        score += 1
        components["Fever >38°C"] = 1
    if absence_of_cough:
        score += 1
        components["Absence of cough"] = 1

    # Age adjustment (Modified Centor / McIsaac)
    if age_3_to_14:
        score += 1
        components["Age 3-14"] = 1
    elif age_45_and_older:
        score -= 1
        components["Age ≥45"] = -1
    else:
        components["Age 15-44"] = 0

    # Strep probability and recommendations
    probabilities = {
        -1: ("1-2.5%", RiskLevel.LOW),
        0: ("1-2.5%", RiskLevel.LOW),
        1: ("5-10%", RiskLevel.LOW),
        2: ("11-17%", RiskLevel.LOW_MODERATE),
        3: ("28-35%", RiskLevel.MODERATE),
        4: ("51-53%", RiskLevel.MODERATE_HIGH),
        5: ("51-53%", RiskLevel.HIGH),
    }

    probability, risk = probabilities.get(score, ("51-53%", RiskLevel.HIGH))

    if score <= 1:
        interpretation = f"Modified Centor {score}: Low strep probability ({probability})"
        recommendations = [
            "No testing or antibiotics recommended",
            "Symptomatic treatment",
            "Likely viral pharyngitis",
        ]
    elif score == 2 or score == 3:
        interpretation = f"Modified Centor {score}: Intermediate probability ({probability})"
        recommendations = [
            "Rapid strep test recommended",
            "Throat culture if rapid test negative",
            "Treat only if test positive",
        ]
    else:
        interpretation = f"Modified Centor {score}: High strep probability ({probability})"
        recommendations = [
            "Consider empiric antibiotics OR",
            "Rapid strep test with treatment if positive",
            "Penicillin V or amoxicillin first-line",
            "Azithromycin if penicillin allergy",
        ]

    return CalculatorResult(
        calculator_name="Modified Centor Score",
        score=score,
        score_unit="points",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["McIsaac WJ, et al. CMAJ 1998"],
    )


# ============================================================================
# Ottawa Ankle Rules
# ============================================================================

def calculate_ottawa_ankle(
    bone_tenderness_posterior_lateral_malleolus: bool = False,
    bone_tenderness_posterior_medial_malleolus: bool = False,
    bone_tenderness_base_5th_metatarsal: bool = False,
    bone_tenderness_navicular: bool = False,
    inability_to_bear_weight_4_steps: bool = False,
) -> CalculatorResult:
    """Apply Ottawa Ankle Rules for imaging decision.

    Args:
        bone_tenderness_posterior_lateral_malleolus: Tenderness at posterior edge of lateral malleolus.
        bone_tenderness_posterior_medial_malleolus: Tenderness at posterior edge of medial malleolus.
        bone_tenderness_base_5th_metatarsal: Tenderness at base of 5th metatarsal.
        bone_tenderness_navicular: Tenderness at navicular bone.
        inability_to_bear_weight_4_steps: Unable to bear weight for 4 steps immediately and in ED.

    Returns:
        CalculatorResult with imaging recommendation.
    """
    # Ankle series criteria
    ankle_xray_needed = (
        bone_tenderness_posterior_lateral_malleolus or
        bone_tenderness_posterior_medial_malleolus or
        inability_to_bear_weight_4_steps
    )

    # Foot series criteria
    foot_xray_needed = (
        bone_tenderness_base_5th_metatarsal or
        bone_tenderness_navicular or
        inability_to_bear_weight_4_steps
    )

    components = {}
    if bone_tenderness_posterior_lateral_malleolus:
        components["Lateral malleolus tenderness"] = "Yes"
    if bone_tenderness_posterior_medial_malleolus:
        components["Medial malleolus tenderness"] = "Yes"
    if bone_tenderness_base_5th_metatarsal:
        components["5th metatarsal tenderness"] = "Yes"
    if bone_tenderness_navicular:
        components["Navicular tenderness"] = "Yes"
    if inability_to_bear_weight_4_steps:
        components["Unable to bear weight"] = "Yes"

    if ankle_xray_needed and foot_xray_needed:
        score = 2
        risk = RiskLevel.MODERATE
        interpretation = "Ankle and foot X-rays indicated"
        recommendations = [
            "Obtain ankle X-ray series (AP, lateral, mortise)",
            "Obtain foot X-ray series (AP, lateral, oblique)",
            "RICE therapy while awaiting results",
        ]
    elif ankle_xray_needed:
        score = 1
        risk = RiskLevel.LOW_MODERATE
        interpretation = "Ankle X-ray indicated"
        recommendations = [
            "Obtain ankle X-ray series (AP, lateral, mortise)",
            "Foot X-ray not required by Ottawa rules",
            "RICE therapy",
        ]
    elif foot_xray_needed:
        score = 1
        risk = RiskLevel.LOW_MODERATE
        interpretation = "Foot X-ray indicated"
        recommendations = [
            "Obtain foot X-ray series (AP, lateral, oblique)",
            "Ankle X-ray not required by Ottawa rules",
            "RICE therapy",
        ]
    else:
        score = 0
        risk = RiskLevel.LOW
        interpretation = "No X-ray indicated by Ottawa rules"
        recommendations = [
            "X-rays not required - fracture risk <2%",
            "RICE therapy: Rest, Ice, Compression, Elevation",
            "NSAIDs for pain",
            "Return if no improvement in 5-7 days",
        ]

    return CalculatorResult(
        calculator_name="Ottawa Ankle Rules",
        score=score,
        score_unit="imaging needed",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Stiell IG, et al. JAMA 1993"],
    )


# ============================================================================
# Caprini VTE Risk Score
# ============================================================================

def calculate_caprini(
    age_41_60: bool = False,
    age_61_74: bool = False,
    age_75_plus: bool = False,
    minor_surgery: bool = False,
    major_surgery: bool = False,
    bmi_over_25: bool = False,
    swollen_legs: bool = False,
    varicose_veins: bool = False,
    pregnant_or_postpartum: bool = False,
    history_unexplained_stillborn: bool = False,
    oral_contraceptives_hrt: bool = False,
    sepsis: bool = False,
    serious_lung_disease: bool = False,
    copd: bool = False,
    immobilizing_plaster_cast: bool = False,
    central_venous_access: bool = False,
    bed_rest_over_72hr: bool = False,
    history_dvt_pe: bool = False,
    family_history_vte: bool = False,
    factor_v_leiden: bool = False,
    prothrombin_mutation: bool = False,
    lupus_anticoagulant: bool = False,
    anticardiolipin_antibodies: bool = False,
    elevated_homocysteine: bool = False,
    heparin_induced_thrombocytopenia: bool = False,
    other_thrombophilia: bool = False,
    stroke: bool = False,
    elective_arthroplasty: bool = False,
    hip_pelvis_leg_fracture: bool = False,
    acute_spinal_cord_injury: bool = False,
    malignancy: bool = False,
) -> CalculatorResult:
    """Calculate Caprini VTE Risk Score for surgical patients.

    Args:
        Various risk factors for VTE.

    Returns:
        CalculatorResult with VTE risk and prophylaxis recommendations.
    """
    score = 0
    components = {}

    # 1-point factors
    one_point_factors = [
        (age_41_60, "Age 41-60"),
        (minor_surgery, "Minor surgery"),
        (bmi_over_25, "BMI >25"),
        (swollen_legs, "Swollen legs"),
        (varicose_veins, "Varicose veins"),
        (pregnant_or_postpartum, "Pregnant/postpartum"),
        (history_unexplained_stillborn, "Unexplained stillborn"),
        (oral_contraceptives_hrt, "OCP/HRT use"),
        (sepsis, "Sepsis"),
        (serious_lung_disease, "Serious lung disease"),
        (copd, "COPD"),
    ]

    for factor, name in one_point_factors:
        if factor:
            score += 1
            components[name] = 1

    # 2-point factors
    two_point_factors = [
        (age_61_74, "Age 61-74"),
        (major_surgery, "Major surgery (>45 min)"),
        (immobilizing_plaster_cast, "Immobilizing cast"),
        (central_venous_access, "Central venous access"),
        (bed_rest_over_72hr, "Bed rest >72hr"),
        (malignancy, "Malignancy"),
    ]

    for factor, name in two_point_factors:
        if factor:
            score += 2
            components[name] = 2

    # 3-point factors
    three_point_factors = [
        (age_75_plus, "Age ≥75"),
        (history_dvt_pe, "History DVT/PE"),
        (family_history_vte, "Family history VTE"),
        (factor_v_leiden, "Factor V Leiden"),
        (prothrombin_mutation, "Prothrombin 20210A"),
        (lupus_anticoagulant, "Lupus anticoagulant"),
        (anticardiolipin_antibodies, "Anticardiolipin antibodies"),
        (elevated_homocysteine, "Elevated homocysteine"),
        (heparin_induced_thrombocytopenia, "HIT"),
        (other_thrombophilia, "Other thrombophilia"),
    ]

    for factor, name in three_point_factors:
        if factor:
            score += 3
            components[name] = 3

    # 5-point factors
    five_point_factors = [
        (stroke, "Stroke <1 month"),
        (elective_arthroplasty, "Elective arthroplasty"),
        (hip_pelvis_leg_fracture, "Hip/pelvis/leg fracture"),
        (acute_spinal_cord_injury, "Acute spinal cord injury"),
    ]

    for factor, name in five_point_factors:
        if factor:
            score += 5
            components[name] = 5

    # Risk stratification
    if score == 0:
        risk = RiskLevel.LOW
        vte_risk = "Minimal (<0.5%)"
        recommendations = [
            "No specific prophylaxis required",
            "Early ambulation",
        ]
    elif score <= 2:
        risk = RiskLevel.LOW
        vte_risk = "Low (~1.5%)"
        recommendations = [
            "Consider mechanical prophylaxis (SCDs)",
            "Early ambulation",
        ]
    elif score <= 4:
        risk = RiskLevel.MODERATE
        vte_risk = "Moderate (~3%)"
        recommendations = [
            "Pharmacologic prophylaxis recommended",
            "LMWH or UFH",
            "Plus mechanical prophylaxis",
        ]
    elif score <= 8:
        risk = RiskLevel.HIGH
        vte_risk = "High (~6%)"
        recommendations = [
            "Pharmacologic prophylaxis required",
            "LMWH or UFH",
            "Plus mechanical prophylaxis",
            "Extended prophylaxis for high-risk surgery",
        ]
    else:
        risk = RiskLevel.VERY_HIGH
        vte_risk = "Very high (>10%)"
        recommendations = [
            "Aggressive pharmacologic prophylaxis",
            "LMWH or UFH at higher doses if bleeding risk allows",
            "Mechanical prophylaxis mandatory",
            "Extended prophylaxis (4-6 weeks post-op)",
            "Consider IVC filter if anticoagulation contraindicated",
        ]

    interpretation = f"Caprini Score {score}: {vte_risk} VTE risk"

    return CalculatorResult(
        calculator_name="Caprini VTE Risk Score",
        score=score,
        score_unit="points",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Caprini JA. Dis Mon 2005"],
    )


# ============================================================================
# Apgar Score (Newborn Assessment)
# ============================================================================

def calculate_apgar(
    appearance: int,  # 0=blue/pale, 1=body pink/extremities blue, 2=completely pink
    pulse: int,  # 0=absent, 1=<100, 2=≥100
    grimace: int,  # 0=no response, 1=grimace, 2=cry/cough
    activity: int,  # 0=limp, 1=some flexion, 2=active motion
    respiration: int,  # 0=absent, 1=slow/irregular, 2=good/crying
    time_minutes: int = 1,  # Usually 1 and 5 minutes
) -> CalculatorResult:
    """Calculate Apgar score for newborn assessment.

    Args:
        appearance: Skin color (0-2).
        pulse: Heart rate (0-2).
        grimace: Reflex irritability (0-2).
        activity: Muscle tone (0-2).
        respiration: Breathing effort (0-2).
        time_minutes: Time of assessment (1, 5, or 10 minutes).

    Returns:
        CalculatorResult with newborn assessment.
    """
    score = appearance + pulse + grimace + activity + respiration

    components = {
        "Appearance": appearance,
        "Pulse": pulse,
        "Grimace": grimace,
        "Activity": activity,
        "Respiration": respiration,
        "Time": f"{time_minutes} min",
    }

    if score >= 7:
        risk = RiskLevel.LOW
        interpretation = f"Apgar {score} at {time_minutes} min: Normal/Reassuring"
        recommendations = [
            "Normal transition",
            "Routine newborn care",
            "Skin-to-skin contact",
            "Initiate breastfeeding when ready",
        ]
    elif score >= 4:
        risk = RiskLevel.MODERATE
        interpretation = f"Apgar {score} at {time_minutes} min: Moderately depressed"
        recommendations = [
            "Stimulation and tactile support",
            "Clear airway as needed",
            "Supplemental oxygen if needed",
            "Continue monitoring",
            "Repeat Apgar at 5 minutes",
        ]
    else:
        risk = RiskLevel.VERY_HIGH
        interpretation = f"Apgar {score} at {time_minutes} min: Severely depressed"
        recommendations = [
            "Immediate resuscitation",
            "Bag-mask ventilation",
            "Consider intubation if no response",
            "Chest compressions if HR <60 despite ventilation",
            "Consider epinephrine if HR <60 despite CPR",
            "NICU admission",
        ]

    return CalculatorResult(
        calculator_name="Apgar Score",
        score=score,
        score_unit=f"at {time_minutes} min",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Apgar V. Anesth Analg 1953"],
    )


# ============================================================================
# Bishop Score (Cervical Favorability)
# ============================================================================

def calculate_bishop(
    dilation: int,  # cm (0=closed, 1=1-2cm, 2=3-4cm, 3=≥5cm)
    effacement: int,  # % (0=0-30%, 1=40-50%, 2=60-70%, 3=≥80%)
    station: int,  # -3 to +3 (0=-3, 1=-2, 2=-1/0, 3=+1/+2)
    consistency: int,  # 0=firm, 1=medium, 2=soft
    position: int,  # 0=posterior, 1=mid, 2=anterior
) -> CalculatorResult:
    """Calculate Bishop score for cervical favorability before induction.

    Args:
        dilation: Cervical dilation points (0-3).
        effacement: Cervical effacement points (0-3).
        station: Fetal station points (0-3).
        consistency: Cervical consistency points (0-2).
        position: Cervical position points (0-2).

    Returns:
        CalculatorResult with induction success prediction.
    """
    score = dilation + effacement + station + consistency + position

    components = {
        "Dilation": dilation,
        "Effacement": effacement,
        "Station": station,
        "Consistency": consistency,
        "Position": position,
    }

    if score >= 8:
        risk = RiskLevel.LOW
        interpretation = f"Bishop Score {score}: Favorable cervix"
        recommendations = [
            "Favorable for induction",
            "High likelihood of vaginal delivery",
            "Consider oxytocin induction",
            "Amniotomy may be considered",
        ]
    elif score >= 5:
        risk = RiskLevel.MODERATE
        interpretation = f"Bishop Score {score}: Intermediate cervix"
        recommendations = [
            "Moderately favorable cervix",
            "Consider cervical ripening",
            "Prostaglandins (PGE2, misoprostol) or",
            "Mechanical methods (Foley balloon)",
            "Then oxytocin when favorable",
        ]
    else:
        risk = RiskLevel.HIGH
        interpretation = f"Bishop Score {score}: Unfavorable cervix"
        recommendations = [
            "Unfavorable for induction",
            "Cervical ripening strongly recommended",
            "Higher risk of failed induction",
            "Consider waiting if not urgent",
            "Prostaglandins or mechanical ripening",
        ]

    return CalculatorResult(
        calculator_name="Bishop Score",
        score=score,
        score_unit="points",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Bishop EH. Obstet Gynecol 1964"],
    )


# ============================================================================
# Ranson Criteria (Acute Pancreatitis)
# ============================================================================

def calculate_ranson(
    # At admission
    age_over_55: bool = False,
    wbc_over_16000: bool = False,
    glucose_over_200: bool = False,
    ldh_over_350: bool = False,
    ast_over_250: bool = False,
    # At 48 hours
    hematocrit_drop_over_10: bool = False,
    bun_rise_over_5: bool = False,
    calcium_under_8: bool = False,
    pao2_under_60: bool = False,
    base_deficit_over_4: bool = False,
    fluid_sequestration_over_6L: bool = False,
) -> CalculatorResult:
    """Calculate Ranson criteria for acute pancreatitis severity.

    Args:
        At admission criteria and 48-hour criteria.

    Returns:
        CalculatorResult with mortality prediction.
    """
    score = 0
    components = {}

    # Admission criteria (GALOP: Glucose, Age, LDH, AST, WBC)
    admission_criteria = [
        (age_over_55, "Age >55"),
        (wbc_over_16000, "WBC >16,000"),
        (glucose_over_200, "Glucose >200"),
        (ldh_over_350, "LDH >350"),
        (ast_over_250, "AST >250"),
    ]

    for criterion, name in admission_criteria:
        if criterion:
            score += 1
            components[name] = 1

    # 48-hour criteria (CHOBBS: Calcium, Hematocrit drop, O2, Base deficit, BUN rise, Sequestration)
    hour_48_criteria = [
        (hematocrit_drop_over_10, "Hct drop >10%"),
        (bun_rise_over_5, "BUN rise >5"),
        (calcium_under_8, "Ca <8"),
        (pao2_under_60, "PaO2 <60"),
        (base_deficit_over_4, "Base deficit >4"),
        (fluid_sequestration_over_6L, "Fluid >6L"),
    ]

    for criterion, name in hour_48_criteria:
        if criterion:
            score += 1
            components[name] = 1

    # Mortality prediction
    if score <= 2:
        mortality = "<5%"
        risk = RiskLevel.LOW
        recommendations = [
            "Mild pancreatitis predicted",
            "Conservative management",
            "NPO, IV fluids, pain control",
            "Monitor for complications",
        ]
    elif score <= 4:
        mortality = "15-20%"
        risk = RiskLevel.MODERATE
        recommendations = [
            "Moderate severity predicted",
            "Close monitoring, possibly ICU",
            "Aggressive fluid resuscitation",
            "Consider CT scan",
        ]
    elif score <= 6:
        mortality = "40%"
        risk = RiskLevel.HIGH
        recommendations = [
            "Severe pancreatitis predicted",
            "ICU admission recommended",
            "Aggressive resuscitation",
            "CT to evaluate for necrosis",
            "Nutrition support planning",
        ]
    else:
        mortality = ">50%"
        risk = RiskLevel.VERY_HIGH
        recommendations = [
            "Very severe pancreatitis",
            "ICU mandatory",
            "Multi-organ failure likely",
            "Consider interventional therapy",
            "Family discussions regarding prognosis",
        ]

    interpretation = f"Ranson Score {score}: Predicted mortality ~{mortality}"

    return CalculatorResult(
        calculator_name="Ranson Criteria",
        score=score,
        score_unit="points",
        risk_level=risk,
        interpretation=interpretation,
        recommendations=recommendations,
        components=components,
        references=["Ranson JH, et al. Surg Gynecol Obstet 1974"],
    )


# ============================================================================
# Calculator Service
# ============================================================================

class ClinicalCalculatorService:
    """Service for clinical risk calculations.

    Provides access to validated clinical calculators including:
    - BMI
    - CHA₂DS₂-VASc (stroke risk in AF)
    - HAS-BLED (bleeding risk)
    - MELD/MELD-Na (liver disease severity)
    - CKD-EPI eGFR (kidney function)
    - Wells DVT score
    - CURB-65 (pneumonia severity)
    - Framingham 10-year CVD risk

    Usage:
        service = ClinicalCalculatorService()

        # Calculate BMI
        result = service.calculate("bmi", weight_kg=70, height_cm=175)

        # Calculate stroke risk
        result = service.calculate("chadsvasc",
            age=72, female=True, hypertension=True, diabetes=True)
    """

    CALCULATORS = {
        # General / Anthropometric
        "bmi": calculate_bmi,
        # Cardiology
        "chadsvasc": calculate_chadsvasc,
        "hasbled": calculate_hasbled,
        "heart": calculate_heart_score,
        "ascvd": calculate_ascvd_risk,
        "framingham": calculate_framingham_10yr,
        "rcri": calculate_rcri,
        "timi": calculate_timi_ua_nstemi,
        "abcd2": calculate_abcd2,
        "qtc": calculate_qtc,
        "map": calculate_map,
        # Pulmonary / PE / DVT
        "wells_dvt": calculate_wells_dvt,
        "wells_pe": calculate_wells_pe,
        "perc": calculate_perc,
        "curb65": calculate_curb65,
        "psi_port": calculate_psi_port,
        "aa_gradient": calculate_aa_gradient,
        # Critical Care
        "apache_ii": calculate_apache_ii,
        "sofa": calculate_sofa,
        "news2": calculate_news2,
        "sirs": calculate_sirs,
        "qsofa": calculate_qsofa,
        "gcs": calculate_gcs,
        # Hepatology / GI
        "meld": calculate_meld,
        "child_pugh": calculate_child_pugh,
        "fib4": calculate_fib4,
        "bisap": calculate_bisap,
        "ranson": calculate_ranson,
        # Nephrology / Electrolytes
        "egfr": calculate_egfr_ckdepi,
        "crcl": calculate_creatinine_clearance,
        "corrected_sodium": calculate_corrected_sodium,
        "corrected_calcium": calculate_corrected_calcium,
        "anion_gap": calculate_anion_gap,
        "serum_osmolality": calculate_serum_osmolality,
        "maintenance_fluids": calculate_maintenance_fluids,
        # Comorbidity / Risk Scores
        "charlson": calculate_charlson,
        "caprini": calculate_caprini,
        # Infectious Disease
        "centor": calculate_centor,
        # Orthopedic / ED
        "ottawa_ankle": calculate_ottawa_ankle,
        # Burns
        "parkland": calculate_parkland_formula,
        # OB/GYN
        "apgar": calculate_apgar,
        "bishop": calculate_bishop,
    }

    def __init__(self) -> None:
        """Initialize the calculator service."""
        pass

    def get_available_calculators(self) -> dict[str, str]:
        """Get list of available calculators with descriptions.

        Returns:
            Dict of calculator name to description.
        """
        return {
            # General / Anthropometric
            "bmi": "Body Mass Index",
            # Cardiology
            "chadsvasc": "CHA₂DS₂-VASc Score (AF stroke risk)",
            "hasbled": "HAS-BLED Score (bleeding risk on anticoagulation)",
            "heart": "HEART Score (chest pain MACE risk)",
            "ascvd": "ASCVD 10-Year Risk (Pooled Cohort Equations)",
            "framingham": "Framingham 10-Year CVD Risk",
            "rcri": "Revised Cardiac Risk Index (perioperative cardiac risk)",
            "timi": "TIMI Risk Score (UA/NSTEMI)",
            "abcd2": "ABCD2 Score (stroke risk after TIA)",
            "qtc": "QTc Calculation (corrected QT interval)",
            "map": "Mean Arterial Pressure",
            # Pulmonary / PE / DVT
            "wells_dvt": "Wells Score for DVT",
            "wells_pe": "Wells Score for PE",
            "perc": "PERC Rule (PE rule-out criteria)",
            "curb65": "CURB-65 (pneumonia severity)",
            "psi_port": "PSI/PORT Score (pneumonia severity index)",
            "aa_gradient": "A-a Gradient (alveolar-arterial oxygen gradient)",
            # Critical Care
            "apache_ii": "APACHE II Score (ICU mortality prediction)",
            "sofa": "SOFA Score (sepsis-related organ dysfunction)",
            "news2": "NEWS2 (National Early Warning Score 2)",
            "sirs": "SIRS Criteria (systemic inflammatory response)",
            "qsofa": "qSOFA Score (quick sepsis screening)",
            "gcs": "Glasgow Coma Scale",
            # Hepatology / GI
            "meld": "MELD/MELD-Na Score (liver disease severity)",
            "child_pugh": "Child-Pugh Score (cirrhosis classification)",
            "fib4": "FIB-4 Index (liver fibrosis estimation)",
            "bisap": "BISAP Score (acute pancreatitis mortality)",
            "ranson": "Ranson Criteria (acute pancreatitis severity)",
            # Nephrology / Electrolytes
            "egfr": "CKD-EPI eGFR (kidney function)",
            "crcl": "Creatinine Clearance (Cockcroft-Gault)",
            "corrected_sodium": "Corrected Sodium (for hyperglycemia)",
            "corrected_calcium": "Corrected Calcium (for hypoalbuminemia)",
            "anion_gap": "Anion Gap (with albumin correction)",
            "serum_osmolality": "Serum Osmolality & Osmolar Gap",
            "maintenance_fluids": "Maintenance IV Fluids (Holliday-Segar 4-2-1)",
            # Comorbidity / Risk Scores
            "charlson": "Charlson Comorbidity Index",
            "caprini": "Caprini VTE Risk Score (surgical VTE prophylaxis)",
            # Infectious Disease
            "centor": "Modified Centor Score (strep pharyngitis)",
            # Orthopedic / ED
            "ottawa_ankle": "Ottawa Ankle Rules (X-ray decision)",
            # Burns
            "parkland": "Parkland Formula (burn fluid resuscitation)",
            # OB/GYN
            "apgar": "Apgar Score (newborn assessment)",
            "bishop": "Bishop Score (cervical favorability)",
        }

    def calculate(
        self,
        calculator: str,
        **kwargs: Any,
    ) -> CalculatorResult:
        """Run a clinical calculator.

        Args:
            calculator: Name of calculator to run.
            **kwargs: Parameters for the calculator.

        Returns:
            CalculatorResult with score and interpretation.

        Raises:
            ValueError: If calculator not found or parameters invalid.
        """
        calc_name = calculator.lower().replace("-", "_")

        if calc_name not in self.CALCULATORS:
            available = ", ".join(self.CALCULATORS.keys())
            raise ValueError(f"Unknown calculator: {calculator}. Available: {available}")

        calc_func = self.CALCULATORS[calc_name]

        try:
            return calc_func(**kwargs)
        except TypeError as e:
            raise ValueError(f"Invalid parameters for {calculator}: {e}")

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about available calculators.

        Returns:
            Dictionary with calculator statistics.
        """
        return {
            "total_calculators": len(self.CALCULATORS),
            "calculator_list": list(self.CALCULATORS.keys()),
        }


# Singleton instance and lock
_clinical_calculator_service: ClinicalCalculatorService | None = None
_clinical_calculator_lock = Lock()


def get_clinical_calculator_service() -> ClinicalCalculatorService:
    """Get the singleton ClinicalCalculatorService instance.

    Returns:
        The singleton ClinicalCalculatorService instance.
    """
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
