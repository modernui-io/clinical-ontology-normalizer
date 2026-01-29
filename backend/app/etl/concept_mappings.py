"""OMOP Concept Mappings for ETL Services.

This module provides centralized concept mappings used across all ETL modules.
Consolidating these mappings eliminates duplication and ensures consistency.

Standard OMOP Vocabularies:
    - Gender: 8507 (Male), 8532 (Female), 8551 (Unknown)
    - Race: CDC/OMB categories
    - Ethnicity: Hispanic/Non-Hispanic
    - Units: UCUM standard
    - Routes: SNOMED drug routes
    - Type Concepts: EHR source indicators
"""

from __future__ import annotations

from app.connectors.base import Gender


# =============================================================================
# DEMOGRAPHIC CONCEPTS
# =============================================================================

# Standard OMOP Gender Concept IDs
GENDER_CONCEPT_MAP = {
    Gender.MALE: 8507,
    Gender.FEMALE: 8532,
    Gender.OTHER: 8551,
    Gender.UNKNOWN: 8551,
}

# Gender source value to concept ID (case-insensitive lookups)
GENDER_SOURCE_MAP = {
    "m": 8507,
    "male": 8507,
    "f": 8532,
    "female": 8532,
    "o": 8551,
    "other": 8551,
    "u": 8551,
    "unknown": 8551,
    "un": 8551,
    "undifferentiated": 8551,
    "ambiguous": 8570,
}

# Standard OMOP Race Concept IDs (CDC/OMB categories)
RACE_CONCEPT_MAP = {
    # White
    "white": 8527,
    "caucasian": 8527,
    "european": 8527,
    "w": 8527,
    "2106-3": 8527,  # CDC code
    # Black or African American
    "black": 8516,
    "black or african american": 8516,
    "african american": 8516,
    "african-american": 8516,
    "b": 8516,
    "2054-5": 8516,  # CDC code
    # Asian
    "asian": 8515,
    "a": 8515,
    "2028-9": 8515,  # CDC code
    # American Indian or Alaska Native
    "american indian": 8657,
    "american indian or alaska native": 8657,
    "alaska native": 8657,
    "native american": 8657,
    "1002-5": 8657,  # CDC code
    # Native Hawaiian or Other Pacific Islander
    "native hawaiian": 8557,
    "native hawaiian or other pacific islander": 8557,
    "pacific islander": 8557,
    "hawaiian": 8557,
    "2076-8": 8557,  # CDC code
    # Other
    "other": 8522,
    "other race": 8522,
    "multiracial": 8522,
    "mixed": 8522,
    "2131-1": 8522,  # CDC code
    # Unknown
    "unknown": 8552,
    "u": 8552,
    "declined": 8552,
    "refused": 8552,
    "not reported": 8552,
}

# Standard OMOP Ethnicity Concept IDs
ETHNICITY_CONCEPT_MAP = {
    # Hispanic or Latino
    "hispanic": 38003563,
    "hispanic or latino": 38003563,
    "latino": 38003563,
    "latina": 38003563,
    "latinx": 38003563,
    "h": 38003563,
    "y": 38003563,  # Yes (to Hispanic question)
    "2135-2": 38003563,  # CDC code
    # Not Hispanic or Latino
    "not hispanic": 38003564,
    "not hispanic or latino": 38003564,
    "non-hispanic": 38003564,
    "n": 38003564,
    "2186-5": 38003564,  # CDC code
    # Unknown
    "unknown": 0,
    "u": 0,
    "declined": 0,
    "refused": 0,
}

# Default demographic concept IDs
DEFAULT_GENDER_CONCEPT_ID = 8551  # Unknown
DEFAULT_RACE_CONCEPT_ID = 8552  # Unknown
DEFAULT_ETHNICITY_CONCEPT_ID = 0  # Unknown


# =============================================================================
# UNIT CONCEPTS (UCUM)
# =============================================================================

# Common Unit to UCUM Concept ID mapping
UNIT_CONCEPT_MAP = {
    # Mass/volume
    "mg/dl": 8840,
    "mg/dL": 8840,
    "g/dl": 8713,
    "g/dL": 8713,
    "mmol/l": 8753,
    "mmol/L": 8753,
    "meq/l": 9557,
    "meq/L": 9557,
    "ng/ml": 8842,
    "ng/mL": 8842,
    "ug/dl": 8837,
    "ug/dL": 8837,
    "pg/ml": 8845,
    "pg/mL": 8845,
    # Count
    "/uL": 8784,
    "/ul": 8784,
    "10*3/uL": 8848,
    "10*6/uL": 8815,
    "cells/uL": 8784,
    # Percentage
    "%": 8554,
    "percent": 8554,
    # Temperature
    "degc": 586323,
    "degf": 9289,
    "celsius": 586323,
    "fahrenheit": 9289,
    "C": 586323,
    "F": 9289,
    # Pressure
    "mmhg": 8876,
    "mm[hg]": 8876,
    "mmHg": 8876,
    # Weight/Height
    "kg": 9529,
    "lb": 9529,
    "lbs": 9529,
    "cm": 8582,
    "in": 9330,
    "inch": 9330,
    "inches": 9330,
    "m": 8582,
    # Rate
    "/min": 8541,
    "bpm": 8541,
    "beats/min": 8541,
    "breaths/min": 8541,
    # Time
    "sec": 8555,
    "s": 8555,
    "min": 8550,
    "h": 8505,
    "hr": 8505,
    # BMI
    "kg/m2": 9531,
    "kg/m^2": 9531,
    # Volume
    "ml": 8587,
    "mL": 8587,
    "l": 8519,
    "L": 8519,
    "ul": 8576,
    "uL": 8576,
    # Mass
    "mg": 8576,
    "g": 8504,
    "ug": 8576,
    "mcg": 8576,
}

# UCUM Unit Concept Map (lowercase normalized)
UCUM_UNIT_CONCEPT_MAP = {k.lower(): v for k, v in UNIT_CONCEPT_MAP.items()}


# =============================================================================
# ROUTE CONCEPTS
# =============================================================================

# Drug Route to OMOP Concept ID mapping
ROUTE_CONCEPT_MAP = {
    # Oral
    "oral": 4128794,
    "po": 4128794,
    "by mouth": 4128794,
    "orally": 4128794,
    # Intravenous
    "intravenous": 4302612,
    "iv": 4302612,
    "ivpb": 4302612,  # IV piggyback
    # Subcutaneous
    "subcutaneous": 4132161,
    "subq": 4132161,
    "sc": 4132161,
    "sq": 4132161,
    # Intramuscular
    "intramuscular": 4303155,
    "im": 4303155,
    # Inhalation
    "inhalation": 45956874,
    "inhaled": 45956874,
    "nebulized": 45956874,
    # Topical
    "topical": 4186832,
    "external": 4186832,
    # Transdermal
    "transdermal": 4302254,
    "patch": 4302254,
    # Ophthalmic
    "ophthalmic": 4184451,
    "eye": 4184451,
    # Otic
    "otic": 4023156,
    "ear": 4023156,
    # Nasal
    "nasal": 4262914,
    "intranasal": 4262914,
    # Rectal
    "rectal": 4290759,
    "pr": 4290759,
}


# =============================================================================
# TYPE CONCEPTS (EHR Source Indicators)
# =============================================================================

# Condition Type Concept IDs
CONDITION_TYPE_CONCEPT_MAP = {
    "ehr": 32817,
    "problem_list": 32818,
    "encounter_diagnosis": 32840,
    "claim": 32840,
    "billing": 32840,
    "registry": 32879,
}

# Drug Type Concept IDs
DRUG_TYPE_CONCEPT_MAP = {
    "prescription": 32839,
    "dispense": 32838,
    "administration": 32817,
    "claim": 32840,
    "ehr": 32817,
}

# Measurement Type Concept IDs
MEASUREMENT_TYPE_CONCEPT_MAP = {
    "lab": 32856,
    "vital": 32836,
    "vital_sign": 32836,
    "vitals": 32836,
    "ehr": 32817,
    "registry": 32879,
}

# Observation Type Concept IDs
OBSERVATION_TYPE_CONCEPT_MAP = {
    "ehr": 32817,
    "survey": 32865,
    "patient_reported": 32865,
    "claim": 32840,
    "registry": 32879,
}

# Procedure Type Concept IDs
PROCEDURE_TYPE_CONCEPT_MAP = {
    "ehr": 32817,
    "inpatient": 32821,
    "outpatient": 32823,
    "claim": 32840,
    "registry": 32879,
}

# Visit Type Concept IDs
VISIT_CONCEPT_MAP = {
    "inpatient": 9201,
    "outpatient": 9202,
    "emergency": 9203,
    "office": 9202,
    "home": 581476,
    "telehealth": 5083,
    "unknown": 0,
}

# Device Type Concept IDs
DEVICE_TYPE_CONCEPT_MAP = {
    "request": 32817,
    "use_statement": 32817,
    "ehr": 32817,
    "claim": 32840,
}

# Specimen Type Concept IDs
SPECIMEN_TYPE_CONCEPT_MAP = {
    "blood": 4001225,
    "serum": 4001225,
    "plasma": 4001225,
    "urine": 4046280,
    "stool": 4002879,
    "saliva": 4001394,
    "tissue": 4001394,
    "csf": 4001394,
    "other": 4001394,
}

# Death Type Concept IDs
DEATH_TYPE_CONCEPT_MAP = {
    "ehr": 32817,
    "death_certificate": 32815,
    "autopsy": 32816,
    "registry": 32879,
}

# Default type concept IDs
DEFAULT_CONDITION_TYPE_CONCEPT_ID = 32817  # EHR
DEFAULT_DRUG_TYPE_CONCEPT_ID = 32817  # EHR
DEFAULT_MEASUREMENT_TYPE_CONCEPT_ID = 32817  # EHR
DEFAULT_OBSERVATION_TYPE_CONCEPT_ID = 32817  # EHR
DEFAULT_PROCEDURE_TYPE_CONCEPT_ID = 32817  # EHR
DEFAULT_DEVICE_TYPE_CONCEPT_ID = 32817  # EHR
DEFAULT_SPECIMEN_TYPE_CONCEPT_ID = 4001394  # Generic specimen
DEFAULT_DEATH_TYPE_CONCEPT_ID = 32817  # EHR


# =============================================================================
# OPERATOR CONCEPTS
# =============================================================================

# Operator concept IDs (for lab value comparisons)
OPERATOR_CONCEPT_MAP = {
    "=": 4172703,
    "<": 4171756,
    "<=": 4171754,
    ">": 4172704,
    ">=": 4171755,
    "~": 4172703,  # approximately equal
}


# =============================================================================
# CONDITION STATUS CONCEPTS
# =============================================================================

CONDITION_STATUS_CONCEPT_MAP = {
    "active": 32902,
    "inactive": 32904,
    "resolved": 32906,
    "remission": 32903,
    "recurrence": 32907,
}


# =============================================================================
# VALUE CONCEPTS (for categorical observations)
# =============================================================================

VALUE_CONCEPT_MAP = {
    # Boolean-like values
    "positive": 9191,
    "pos": 9191,
    "+": 9191,
    "detected": 9191,
    "reactive": 9191,
    "negative": 9189,
    "neg": 9189,
    "-": 9189,
    "not detected": 9189,
    "non-reactive": 9189,
    # Yes/No
    "yes": 4188539,
    "y": 4188539,
    "no": 4188540,
    "n": 4188540,
    # Normal/Abnormal
    "normal": 4069590,
    "abnormal": 4135493,
    "high": 4328749,
    "low": 4267416,
    "critical": 4135493,
}


# =============================================================================
# QUALIFIER CONCEPTS
# =============================================================================

QUALIFIER_CONCEPT_MAP = {
    "before meals": 4181332,
    "after meals": 4181331,
    "fasting": 4324124,
    "random": 4185215,
    "morning": 4188539,
    "evening": 4188540,
}


# =============================================================================
# CODE SYSTEM VOCABULARY MAPPING
# =============================================================================

CODE_SYSTEM_VOCABULARY_MAP = {
    # ICD-10
    "icd10": "ICD10CM",
    "icd-10": "ICD10CM",
    "icd10cm": "ICD10CM",
    "2.16.840.1.113883.6.90": "ICD10CM",  # ICD-10-CM OID
    # ICD-9
    "icd9": "ICD9CM",
    "icd-9": "ICD9CM",
    "icd9cm": "ICD9CM",
    "2.16.840.1.113883.6.103": "ICD9CM",  # ICD-9-CM OID
    # SNOMED
    "snomed": "SNOMED",
    "snomedct": "SNOMED",
    "snomed-ct": "SNOMED",
    "2.16.840.1.113883.6.96": "SNOMED",  # SNOMED CT OID
    # LOINC
    "loinc": "LOINC",
    "2.16.840.1.113883.6.1": "LOINC",  # LOINC OID
    # RxNorm
    "rxnorm": "RxNorm",
    "2.16.840.1.113883.6.88": "RxNorm",  # RxNorm OID
    # NDC
    "ndc": "NDC",
    "2.16.840.1.113883.6.69": "NDC",  # NDC OID
    # CPT
    "cpt": "CPT4",
    "cpt4": "CPT4",
    "2.16.840.1.113883.6.12": "CPT4",  # CPT OID
    # HCPCS
    "hcpcs": "HCPCS",
    "2.16.840.1.113883.6.14": "HCPCS",  # HCPCS OID
    # ATC
    "atc": "ATC",
    "whoatc": "ATC",
}


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_unit_concept_id(unit: str | None) -> int | None:
    """Get OMOP concept ID for a unit string.

    Args:
        unit: Unit string (e.g., "mg/dL", "mmHg")

    Returns:
        OMOP concept ID or None if not found
    """
    if not unit:
        return None
    # Try exact match first
    if unit in UNIT_CONCEPT_MAP:
        return UNIT_CONCEPT_MAP[unit]
    # Try lowercase
    return UCUM_UNIT_CONCEPT_MAP.get(unit.lower())


def get_route_concept_id(route: str | None) -> int | None:
    """Get OMOP concept ID for a route string.

    Args:
        route: Route string (e.g., "oral", "IV", "subcutaneous")

    Returns:
        OMOP concept ID or None if not found
    """
    if not route:
        return None
    return ROUTE_CONCEPT_MAP.get(route.lower())


def get_vocabulary_id(code_system: str | None) -> str | None:
    """Get OMOP vocabulary ID for a code system.

    Args:
        code_system: Code system string or OID

    Returns:
        OMOP vocabulary ID or None if not found
    """
    if not code_system:
        return None
    return CODE_SYSTEM_VOCABULARY_MAP.get(code_system.lower())
