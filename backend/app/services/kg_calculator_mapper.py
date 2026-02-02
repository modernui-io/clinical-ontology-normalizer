"""Mapping of KG MEASUREMENT nodes to calculator input parameters.

This module defines how measurement values from the knowledge graph
map to calculator input parameters. This allows automatic population
of calculator inputs from patient data.
"""

from __future__ import annotations

from typing import Any


# Mapping of measurement labels (lowercase) to calculator parameters
# Format: measurement_label -> {calculator_id: param_name}
MEASUREMENT_TO_PARAM: dict[str, dict[str, str]] = {
    # Renal measurements
    "creatinine": {
        "egfr_ckd_epi": "creatinine",
        "meld": "creatinine",
        "meld_na": "creatinine",
        "kdigo_aki": "creatinine",
    },
    "serum creatinine": {
        "egfr_ckd_epi": "creatinine",
        "meld": "creatinine",
        "meld_na": "creatinine",
    },
    "creatinine level": {
        "egfr_ckd_epi": "creatinine",
        "meld": "creatinine",
    },
    "gfr": {"kdigo_stage": "gfr"},
    "egfr": {"kdigo_stage": "gfr", "egfr_ckd_epi": "egfr"},
    "bun": {"bun_creatinine_ratio": "bun"},
    "blood urea nitrogen": {"bun_creatinine_ratio": "bun"},

    # Hepatic measurements
    "bilirubin": {
        "meld": "bilirubin",
        "meld_na": "bilirubin",
        "child_pugh": "bilirubin",
    },
    "total bilirubin": {
        "meld": "bilirubin",
        "meld_na": "bilirubin",
        "child_pugh": "bilirubin",
    },
    "inr": {
        "meld": "inr",
        "meld_na": "inr",
        "child_pugh": "inr",
        "chadsvasc": "inr",
    },
    "albumin": {
        "child_pugh": "albumin",
        "meld_na": "albumin",
    },
    "serum albumin": {"child_pugh": "albumin"},
    "ast": {"fib4": "ast", "nafld_fibrosis": "ast"},
    "alt": {"fib4": "alt", "nafld_fibrosis": "alt"},
    "platelet count": {"fib4": "platelets"},
    "platelets": {"fib4": "platelets"},

    # Cardiovascular measurements
    "systolic blood pressure": {
        "ascvd": "systolic_bp",
        "framingham": "systolic_bp",
        "chadsvasc": "systolic_bp",
        "curb65": "systolic_bp",
        "qsofa": "systolic_bp",
    },
    "sbp": {
        "ascvd": "systolic_bp",
        "framingham": "systolic_bp",
    },
    "diastolic blood pressure": {
        "ascvd": "diastolic_bp",
        "framingham": "diastolic_bp",
    },
    "dbp": {"ascvd": "diastolic_bp"},
    "heart rate": {
        "grace": "heart_rate",
        "pesi": "heart_rate",
        "timi": "heart_rate",
    },
    "pulse": {"grace": "heart_rate", "pesi": "heart_rate"},
    "ejection fraction": {
        "maggic": "ejection_fraction",
        "nyha": "ef",
    },
    "ef": {"maggic": "ejection_fraction"},
    "lvef": {"maggic": "ejection_fraction"},
    "bnp": {"maggic": "bnp", "gwtg_hf": "bnp"},
    "nt-probnp": {"maggic": "bnp", "gwtg_hf": "bnp"},

    # Lipid measurements
    "total cholesterol": {
        "ascvd": "total_cholesterol",
        "framingham": "total_cholesterol",
    },
    "cholesterol": {"ascvd": "total_cholesterol"},
    "hdl": {
        "ascvd": "hdl",
        "framingham": "hdl",
    },
    "hdl cholesterol": {"ascvd": "hdl"},
    "ldl": {"ascvd": "ldl"},
    "ldl cholesterol": {"ascvd": "ldl"},
    "triglycerides": {"ascvd": "triglycerides"},

    # Glucose/Diabetes measurements
    "glucose": {
        "hba1c_estimated": "average_glucose",
        "sofa": "glucose",
    },
    "blood glucose": {"hba1c_estimated": "average_glucose"},
    "fasting glucose": {"hba1c_estimated": "fasting_glucose"},
    "hba1c": {"hba1c_estimated": "hba1c", "ukpds_risk": "hba1c"},
    "hemoglobin a1c": {"hba1c_estimated": "hba1c"},
    "a1c": {"hba1c_estimated": "hba1c"},

    # Respiratory measurements
    "respiratory rate": {
        "curb65": "respiratory_rate",
        "qsofa": "respiratory_rate",
        "sofa": "respiratory_rate",
        "psi": "respiratory_rate",
    },
    "rr": {"curb65": "respiratory_rate", "qsofa": "respiratory_rate"},
    "oxygen saturation": {
        "psi": "o2_sat",
        "sofa": "pao2",
    },
    "spo2": {"psi": "o2_sat"},
    "o2 sat": {"psi": "o2_sat"},
    "fio2": {"sofa": "fio2"},
    "pao2": {"sofa": "pao2"},

    # Hematology measurements
    "hemoglobin": {
        "sofa": "hemoglobin",
        "rockall": "hemoglobin",
        "glasgow_blatchford": "hemoglobin",
    },
    "hgb": {"sofa": "hemoglobin"},
    "hematocrit": {"sofa": "hematocrit"},
    "wbc": {"sofa": "wbc", "sirs": "wbc"},
    "white blood cell count": {"sofa": "wbc", "sirs": "wbc"},

    # Electrolytes
    "sodium": {
        "meld_na": "sodium",
        "sofa": "sodium",
    },
    "serum sodium": {"meld_na": "sodium"},
    "potassium": {"sofa": "potassium"},
    "serum potassium": {"sofa": "potassium"},

    # Other measurements
    "temperature": {
        "sirs": "temperature",
        "psi": "temperature",
    },
    "temp": {"sirs": "temperature"},
    "bmi": {"bmi": "bmi", "bode": "bmi"},
    "body mass index": {"bmi": "bmi"},
    "weight": {"bmi": "weight"},
    "height": {"bmi": "height"},
    "age": {
        "ascvd": "age",
        "framingham": "age",
        "chadsvasc": "age",
        "egfr_ckd_epi": "age",
        "meld": "age",
        "psi": "age",
    },
}


def get_calculator_params_for_measurement(
    measurement_label: str,
) -> dict[str, str]:
    """Get calculator parameters that use this measurement.

    Args:
        measurement_label: The measurement label from KG node.

    Returns:
        Dict mapping calculator_id -> parameter_name.
    """
    normalized = measurement_label.lower().strip()

    # Direct lookup
    if normalized in MEASUREMENT_TO_PARAM:
        return MEASUREMENT_TO_PARAM[normalized]

    # Fuzzy matching
    for key, params in MEASUREMENT_TO_PARAM.items():
        if key in normalized or normalized in key:
            return params

    return {}


def get_measurements_for_calculator(calculator_id: str) -> list[str]:
    """Get all measurements needed by a calculator.

    Args:
        calculator_id: The calculator ID.

    Returns:
        List of measurement labels that feed into this calculator.
    """
    measurements = []
    for measurement, calc_params in MEASUREMENT_TO_PARAM.items():
        if calculator_id in calc_params:
            measurements.append(measurement)
    return measurements


def build_calculator_inputs_from_measurements(
    calculator_id: str,
    measurements: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    """Build calculator inputs from measurement data.

    Args:
        calculator_id: The calculator to build inputs for.
        measurements: List of measurement dicts with 'label' and 'value' keys.

    Returns:
        Tuple of (inputs dict, list of missing required params).
    """
    inputs = {}
    used_measurements = []

    for measurement in measurements:
        label = measurement.get("label", "").lower().strip()
        value = measurement.get("value")

        if not label or value is None:
            continue

        # Check if this measurement maps to the calculator
        calc_params = get_calculator_params_for_measurement(label)
        if calculator_id in calc_params:
            param_name = calc_params[calculator_id]
            # Try to convert to float
            try:
                inputs[param_name] = float(value)
                used_measurements.append(label)
            except (ValueError, TypeError):
                # Keep as string if not numeric
                inputs[param_name] = value
                used_measurements.append(label)

    # Determine missing inputs (would need calculator-specific required params list)
    missing = []  # TODO: Implement based on calculator requirements

    return inputs, missing
