"""Mapping of clinical conditions to applicable clinical calculators.

This module defines which clinical risk calculators are appropriate for
which conditions. Used to automatically suggest calculators based on
patient conditions from the knowledge graph.

Now enhanced with OMOP hierarchy support via Neo4j - patient condition
"Type 2 diabetes mellitus" will match calculators for "diabetes" via
IS_A relationship traversal.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

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


def get_calculators_for_condition(
    condition_name: str,
    use_hierarchy: bool = True,
) -> list[str]:
    """Get applicable calculators for a given condition.

    Uses OMOP hierarchy via Neo4j when available to find calculators
    that apply to ancestor conditions. For example, patient with
    "Type 2 diabetes mellitus" will match calculators for "diabetes".

    Args:
        condition_name: The condition name to look up.
        use_hierarchy: Whether to use Neo4j hierarchy expansion.

    Returns:
        List of calculator IDs applicable to this condition.
    """
    normalized = condition_name.lower().strip()
    matches: list[str] = []

    # Direct lookup first (fastest)
    if normalized in CONDITION_CALCULATOR_MAP:
        matches.extend(CONDITION_CALCULATOR_MAP[normalized])

    # If no direct match and hierarchy enabled, use OMOP hierarchy
    if not matches and use_hierarchy:
        try:
            from app.services.omop_hierarchy_service import get_omop_hierarchy_service

            hierarchy = get_omop_hierarchy_service()
            if hierarchy.is_available:
                # Expand condition to include ancestors
                expanded_names = hierarchy.expand_condition_names(
                    normalized, max_distance=3
                )

                # Check each expanded name against our map
                for exp_name in expanded_names:
                    if exp_name in CONDITION_CALCULATOR_MAP:
                        for calc in CONDITION_CALCULATOR_MAP[exp_name]:
                            if calc not in matches:
                                matches.append(calc)
                        logger.debug(
                            f"Hierarchy match: '{normalized}' -> '{exp_name}' "
                            f"-> {CONDITION_CALCULATOR_MAP[exp_name]}"
                        )
        except Exception as e:
            logger.warning(f"Hierarchy lookup failed, falling back to string: {e}")

    # Fallback: Fuzzy string matching
    if not matches:
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


def get_calculators_for_condition_with_hierarchy(
    condition_name: str,
    concept_id: int | None = None,
) -> tuple[list[str], list[dict]]:
    """Get calculators with detailed hierarchy match info.

    Args:
        condition_name: The condition name to look up.
        concept_id: Optional OMOP concept ID for precise matching.

    Returns:
        Tuple of (calculator_ids, match_details)
    """
    normalized = condition_name.lower().strip()
    matches: list[str] = []
    match_details: list[dict] = []

    # Direct lookup
    if normalized in CONDITION_CALCULATOR_MAP:
        calcs = CONDITION_CALCULATOR_MAP[normalized]
        matches.extend(calcs)
        match_details.append({
            "match_type": "exact",
            "matched_condition": normalized,
            "calculators": calcs,
            "distance": 0,
        })
        return matches, match_details

    # Try hierarchy matching
    try:
        from app.services.omop_hierarchy_service import get_omop_hierarchy_service

        hierarchy = get_omop_hierarchy_service()
        if hierarchy.is_available:
            # Get ancestors with distances
            condition_to_lookup = concept_id if concept_id else condition_name
            concepts = (
                [hierarchy.get_concept_by_id(concept_id)]
                if concept_id
                else hierarchy.find_concepts_by_name(
                    condition_name, domain_ids=["Condition"], limit=1
                )
            )

            if concepts and concepts[0]:
                ancestors = hierarchy.get_ancestors(
                    concepts[0].concept_id,
                    max_distance=3,
                    include_self=True,
                )

                for ancestor, distance in ancestors:
                    ancestor_name = ancestor.name.lower()
                    if ancestor_name in CONDITION_CALCULATOR_MAP:
                        calcs = CONDITION_CALCULATOR_MAP[ancestor_name]
                        for calc in calcs:
                            if calc not in matches:
                                matches.append(calc)
                        match_details.append({
                            "match_type": "exact" if distance == 0 else "hierarchy",
                            "matched_condition": ancestor_name,
                            "matched_concept_id": ancestor.concept_id,
                            "calculators": calcs,
                            "distance": distance,
                        })

    except Exception as e:
        logger.warning(f"Hierarchy lookup failed: {e}")

    # Fallback to string matching if no hierarchy matches
    if not matches:
        for key, calculators in CONDITION_CALCULATOR_MAP.items():
            if key in normalized or normalized in key:
                for calc in calculators:
                    if calc not in matches:
                        matches.append(calc)
                match_details.append({
                    "match_type": "fuzzy",
                    "matched_condition": key,
                    "calculators": calculators,
                    "distance": -1,  # Indicates string match, not hierarchy
                })

    return matches, match_details


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
