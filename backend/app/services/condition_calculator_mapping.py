"""Mapping of clinical conditions to applicable clinical calculators.

This module defines which clinical risk calculators are appropriate for
which conditions. Used to automatically suggest calculators based on
patient conditions from the knowledge graph.
"""

from __future__ import annotations


# Condition-to-calculator mapping
# Keys are normalized condition names (lowercase)
# Values are lists of calculator IDs that apply to that condition
CONDITION_CALCULATOR_MAP: dict[str, list[str]] = {
    # Cardiovascular conditions
    "atrial fibrillation": ["chadsvasc", "hasbled"],
    "afib": ["chadsvasc", "hasbled"],
    "a-fib": ["chadsvasc", "hasbled"],
    "heart failure": ["nyha", "maggic", "gwtg_hf"],
    "hfref": ["nyha", "maggic", "gwtg_hf"],
    "hfpef": ["nyha", "maggic", "gwtg_hf"],
    "chf": ["nyha", "maggic", "gwtg_hf"],
    "congestive heart failure": ["nyha", "maggic", "gwtg_hf"],
    "coronary artery disease": ["ascvd", "framingham", "heart_score"],
    "cad": ["ascvd", "framingham", "heart_score"],
    "myocardial infarction": ["grace", "timi", "heart_score"],
    "mi": ["grace", "timi", "heart_score"],
    "acute coronary syndrome": ["grace", "timi", "heart_score"],
    "acs": ["grace", "timi", "heart_score"],
    "hypertension": ["ascvd", "framingham"],
    "htn": ["ascvd", "framingham"],
    "hyperlipidemia": ["ascvd", "framingham"],
    "dyslipidemia": ["ascvd", "framingham"],

    # Renal conditions
    "chronic kidney disease": ["egfr_ckd_epi", "kdigo_stage"],
    "ckd": ["egfr_ckd_epi", "kdigo_stage"],
    "ckd stage 1": ["egfr_ckd_epi"],
    "ckd stage 2": ["egfr_ckd_epi"],
    "ckd stage 3": ["egfr_ckd_epi"],
    "ckd stage 4": ["egfr_ckd_epi"],
    "ckd stage 5": ["egfr_ckd_epi"],
    "esrd": ["egfr_ckd_epi"],
    "end stage renal disease": ["egfr_ckd_epi"],
    "acute kidney injury": ["kdigo_aki"],
    "aki": ["kdigo_aki"],

    # Hepatic conditions
    "cirrhosis": ["meld", "meld_na", "child_pugh"],
    "liver cirrhosis": ["meld", "meld_na", "child_pugh"],
    "liver disease": ["meld", "child_pugh", "fib4"],
    "hepatic encephalopathy": ["child_pugh", "west_haven"],
    "ascites": ["child_pugh"],
    "fatty liver disease": ["fib4", "nafld_fibrosis"],
    "nafld": ["fib4", "nafld_fibrosis"],
    "nash": ["fib4", "nafld_fibrosis"],

    # Thromboembolic conditions
    "deep vein thrombosis": ["wells_dvt", "perc"],
    "dvt": ["wells_dvt", "perc"],
    "pulmonary embolism": ["wells_pe", "pesi", "geneva"],
    "pe": ["wells_pe", "pesi", "geneva"],
    "venous thromboembolism": ["wells_dvt", "wells_pe"],
    "vte": ["wells_dvt", "wells_pe"],

    # Bleeding/Anticoagulation
    "gastrointestinal bleeding": ["rockall", "glasgow_blatchford", "aims65"],
    "gi bleed": ["rockall", "glasgow_blatchford", "aims65"],
    "upper gi bleed": ["rockall", "glasgow_blatchford", "aims65"],
    "anticoagulation": ["hasbled", "chadsvasc"],

    # Respiratory conditions
    "copd": ["bode", "gold_stage"],
    "chronic obstructive pulmonary disease": ["bode", "gold_stage"],
    "pneumonia": ["curb65", "psi", "a_drop"],
    "community acquired pneumonia": ["curb65", "psi"],

    # Diabetes
    "diabetes": ["hba1c_estimated", "ukpds_risk"],
    "diabetes mellitus": ["hba1c_estimated", "ukpds_risk"],
    "type 2 diabetes": ["hba1c_estimated", "ukpds_risk", "ascvd"],
    "dm": ["hba1c_estimated", "ukpds_risk"],
    "dm2": ["hba1c_estimated", "ukpds_risk"],

    # Stroke
    "stroke": ["nihss", "abcd2"],
    "cva": ["nihss", "abcd2"],
    "tia": ["abcd2"],
    "transient ischemic attack": ["abcd2"],

    # Sepsis
    "sepsis": ["sofa", "qsofa", "sirs"],
    "septic shock": ["sofa", "qsofa"],

    # Falls/Frailty
    "falls": ["morse_fall", "stratify"],
    "fall risk": ["morse_fall", "stratify"],
    "frailty": ["clinical_frailty"],

    # Other
    "obesity": ["bmi"],
    "malnutrition": ["must", "nrs2002"],
}


def get_calculators_for_condition(condition_name: str) -> list[str]:
    """Get applicable calculators for a given condition.

    Args:
        condition_name: The condition name to look up.

    Returns:
        List of calculator IDs applicable to this condition.
    """
    normalized = condition_name.lower().strip()

    # Direct lookup
    if normalized in CONDITION_CALCULATOR_MAP:
        return CONDITION_CALCULATOR_MAP[normalized]

    # Fuzzy matching - check if condition contains any key
    matches = []
    for key, calculators in CONDITION_CALCULATOR_MAP.items():
        if key in normalized or normalized in key:
            matches.extend(calculators)

    # Deduplicate while preserving order
    seen = set()
    result = []
    for calc in matches:
        if calc not in seen:
            seen.add(calc)
            result.append(calc)

    return result


def get_conditions_for_calculator(calculator_id: str) -> list[str]:
    """Get conditions that use a specific calculator.

    Args:
        calculator_id: The calculator ID to look up.

    Returns:
        List of condition names that use this calculator.
    """
    conditions = []
    for condition, calculators in CONDITION_CALCULATOR_MAP.items():
        if calculator_id in calculators:
            conditions.append(condition)
    return conditions
