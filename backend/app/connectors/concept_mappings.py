"""Consolidated Concept Mappings for Healthcare Data Connectors.

This module provides shared mappings used across FHIR, HL7v2, C-CDA, and other
connector modules. Centralizing these mappings ensures consistency and reduces
code duplication.

Mappings include:
- CODE_SYSTEM_MAP: OID/URL to standardized vocabulary names
- FHIR_RESOURCE_MAP: FHIR resource types to OMOP domain mappings
- HL7_SEGMENT_MAP: HL7v2 segment identifiers to clinical domains
- CCDA_SECTION_MAP: C-CDA section template OIDs to domains
- STATUS_MAPS: Clinical status value mappings

Usage:
    from app.connectors.concept_mappings import (
        CODE_SYSTEM_MAP,
        normalize_code_system,
        CCDA_SECTION_TEMPLATE_IDS,
    )

    vocab = normalize_code_system("http://loinc.org")  # Returns "LOINC"
"""

from __future__ import annotations

from app.connectors.base import (
    ConditionStatus,
    DrugStatus,
    Gender,
    ProcedureStatus,
    VisitType,
)


# =============================================================================
# Code System Mappings (OID/URL to Vocabulary Name)
# =============================================================================

CODE_SYSTEM_MAP: dict[str, str] = {
    # FHIR System URLs
    "http://snomed.info/sct": "SNOMED",
    "http://hl7.org/fhir/sid/icd-10": "ICD10",
    "http://hl7.org/fhir/sid/icd-10-cm": "ICD10CM",
    "http://hl7.org/fhir/sid/icd-10-pcs": "ICD10PCS",
    "http://hl7.org/fhir/sid/icd-9-cm": "ICD9CM",
    "http://hl7.org/fhir/sid/icd-9-cm-procedure": "ICD9Proc",
    "http://www.ama-assn.org/go/cpt": "CPT4",
    "http://www.nlm.nih.gov/research/umls/rxnorm": "RxNorm",
    "http://loinc.org": "LOINC",
    "http://hl7.org/fhir/sid/ndc": "NDC",
    "http://unitsofmeasure.org": "UCUM",
    "http://terminology.hl7.org/CodeSystem/v3-ActCode": "ActCode",
    "http://terminology.hl7.org/CodeSystem/v2-0203": "IdentifierType",
    "http://hl7.org/fhir/sid/cvx": "CVX",
    "http://www.whocc.no/atc": "ATC",
    "http://hl7.org/fhir/sid/srt": "SRT",
    "urn:oid:2.16.840.1.113883.6.96": "SNOMED",
    "urn:oid:2.16.840.1.113883.6.1": "LOINC",
    "urn:oid:2.16.840.1.113883.6.88": "RxNorm",
    "urn:oid:2.16.840.1.113883.6.69": "NDC",
    "urn:oid:2.16.840.1.113883.6.12": "CPT4",
    "urn:oid:2.16.840.1.113883.6.4": "ICD10PCS",
    "urn:oid:2.16.840.1.113883.6.90": "ICD10CM",
    "urn:oid:2.16.840.1.113883.6.103": "ICD9CM",
    "urn:oid:2.16.840.1.113883.6.104": "ICD9Proc",
    # C-CDA OIDs
    "2.16.840.1.113883.6.96": "SNOMED",
    "2.16.840.1.113883.6.1": "LOINC",
    "2.16.840.1.113883.6.88": "RxNorm",
    "2.16.840.1.113883.6.69": "NDC",
    "2.16.840.1.113883.6.12": "CPT4",
    "2.16.840.1.113883.6.4": "ICD10PCS",
    "2.16.840.1.113883.6.90": "ICD10CM",
    "2.16.840.1.113883.6.103": "ICD9CM",
    "2.16.840.1.113883.6.104": "ICD9Proc",
    "2.16.840.1.113883.6.59": "CVX",
    "2.16.840.1.113883.4.9": "UNII",
    # HL7v2 coding method identifiers
    "I9": "ICD9CM",
    "I10": "ICD10CM",
    "C4": "CPT4",
    "LN": "LOINC",
    "RXN": "RxNorm",
    "NDC": "NDC",
    "SCT": "SNOMED",
    "SNM": "SNOMED",
}


def normalize_code_system(code_system: str | None) -> str | None:
    """Normalize a code system URL/OID to a standard vocabulary name.

    Args:
        code_system: FHIR URL, OID, or HL7v2 coding method identifier.

    Returns:
        Standardized vocabulary name (e.g., "SNOMED", "LOINC") or the
        original value if no mapping exists.
    """
    if not code_system:
        return None
    return CODE_SYSTEM_MAP.get(code_system, code_system)


# =============================================================================
# Default Code Systems by Domain
# =============================================================================

DEFAULT_CODE_SYSTEMS: dict[str, str] = {
    "condition": "ICD10CM",
    "procedure": "CPT4",
    "drug": "RxNorm",
    "measurement": "LOINC",
    "observation": "SNOMED",
    "allergy": "RxNorm",
    "immunization": "CVX",
    "device": "SNOMED",
    "specimen": "SNOMED",
}


# =============================================================================
# FHIR Resource Type to OMOP Domain Mapping
# =============================================================================

FHIR_RESOURCE_MAP: dict[str, str] = {
    # Core clinical resources
    "Patient": "Person",
    "Encounter": "Visit",
    "Condition": "Condition",
    "MedicationRequest": "Drug",
    "MedicationStatement": "Drug",
    "MedicationAdministration": "Drug",
    "MedicationDispense": "Drug",
    "Procedure": "Procedure",
    "Observation": "Measurement",  # Labs/vitals -> Measurement, others -> Observation
    "DiagnosticReport": "Measurement",
    "AllergyIntolerance": "Observation",
    "Immunization": "Drug",
    # Device-related resources
    "Device": "Device",
    "DeviceRequest": "Device",
    "DeviceUseStatement": "Device",
    # Specimen
    "Specimen": "Specimen",
    # Clinical notes
    "DocumentReference": "Note",
    "ClinicalImpression": "Note",
    # Care management
    "CarePlan": "Observation",
    "Goal": "Observation",
    "ServiceRequest": "Procedure",
    # Provider/organization
    "Practitioner": "Provider",
    "Organization": "CareSite",
    "Location": "Location",
}


# =============================================================================
# FHIR Encounter Class to Visit Type Mapping
# =============================================================================

FHIR_ENCOUNTER_CLASS_MAP: dict[str, VisitType] = {
    "IMP": VisitType.INPATIENT,
    "ACUTE": VisitType.INPATIENT,
    "NONAC": VisitType.INPATIENT,
    "SS": VisitType.INPATIENT,
    "EMER": VisitType.EMERGENCY,
    "AMB": VisitType.OUTPATIENT,
    "VR": VisitType.TELEHEALTH,
    "HH": VisitType.HOME,
    "OBSENC": VisitType.OBSERVATION,
    "PRENC": VisitType.OUTPATIENT,
    "FLD": VisitType.OUTPATIENT,
}


# =============================================================================
# HL7v2 Segment to Domain Mapping
# =============================================================================

HL7_SEGMENT_MAP: dict[str, str] = {
    # Message header
    "MSH": "Header",
    # Patient administration
    "PID": "Person",
    "PD1": "Person",
    "NK1": "Person",
    # Visit/encounter
    "PV1": "Visit",
    "PV2": "Visit",
    # Diagnosis
    "DG1": "Condition",
    # Procedures
    "PR1": "Procedure",
    # Medications
    "RXA": "Drug",
    "RXD": "Drug",
    "RXE": "Drug",
    "RXO": "Drug",
    "RXR": "Drug",
    # Observations
    "OBX": "Measurement",
    "OBR": "Measurement",
    # Allergies
    "AL1": "Observation",
    # Insurance
    "IN1": "Payer",
    "IN2": "Payer",
}

HL7_PATIENT_CLASS_MAP: dict[str, VisitType] = {
    "I": VisitType.INPATIENT,
    "INPATIENT": VisitType.INPATIENT,
    "O": VisitType.OUTPATIENT,
    "OUTPATIENT": VisitType.OUTPATIENT,
    "E": VisitType.EMERGENCY,
    "EMERGENCY": VisitType.EMERGENCY,
    "R": VisitType.OUTPATIENT,  # Recurring
    "B": VisitType.OBSERVATION,  # Observation
    "P": VisitType.OUTPATIENT,  # Preadmit
}

HL7_CODING_METHOD_MAP: dict[str, str] = {
    "I9": "ICD9CM",
    "I10": "ICD10CM",
    "C4": "CPT4",
    "C5": "CPT4",
    "LN": "LOINC",
    "RXN": "RxNorm",
    "NDC": "NDC",
    "SCT": "SNOMED",
    "SNM": "SNOMED",
    "99ZZZ": "LOCAL",  # Local codes
}


# =============================================================================
# C-CDA Section Template IDs
# =============================================================================

CCDA_SECTION_TEMPLATE_IDS: dict[str, str] = {
    "problems": "2.16.840.1.113883.10.20.22.2.5.1",
    "medications": "2.16.840.1.113883.10.20.22.2.1.1",
    "allergies": "2.16.840.1.113883.10.20.22.2.6.1",
    "vital_signs": "2.16.840.1.113883.10.20.22.2.4.1",
    "results": "2.16.840.1.113883.10.20.22.2.3.1",
    "procedures": "2.16.840.1.113883.10.20.22.2.7.1",
    "encounters": "2.16.840.1.113883.10.20.22.2.22.1",
    "immunizations": "2.16.840.1.113883.10.20.22.2.2.1",
    "social_history": "2.16.840.1.113883.10.20.22.2.17",
    "plan_of_care": "2.16.840.1.113883.10.20.22.2.10",
    "functional_status": "2.16.840.1.113883.10.20.22.2.14",
    "mental_status": "2.16.840.1.113883.10.20.22.2.56",
    "family_history": "2.16.840.1.113883.10.20.22.2.15",
    "medical_equipment": "2.16.840.1.113883.10.20.22.2.23",
    "payers": "2.16.840.1.113883.10.20.22.2.18",
    "advance_directives": "2.16.840.1.113883.10.20.22.2.21.1",
    "reason_for_visit": "2.16.840.1.113883.10.20.22.2.12",
    "chief_complaint": "2.16.840.1.113883.10.20.22.2.13",
    "history_of_present_illness": "2.16.840.1.113883.10.20.22.2.65",
    "assessment_and_plan": "2.16.840.1.113883.10.20.22.2.9",
}

CCDA_SECTION_MAP: dict[str, str] = {
    # Map template ID to OMOP domain
    "2.16.840.1.113883.10.20.22.2.5.1": "Condition",
    "2.16.840.1.113883.10.20.22.2.1.1": "Drug",
    "2.16.840.1.113883.10.20.22.2.6.1": "Observation",
    "2.16.840.1.113883.10.20.22.2.4.1": "Measurement",
    "2.16.840.1.113883.10.20.22.2.3.1": "Measurement",
    "2.16.840.1.113883.10.20.22.2.7.1": "Procedure",
    "2.16.840.1.113883.10.20.22.2.22.1": "Visit",
    "2.16.840.1.113883.10.20.22.2.2.1": "Drug",
    "2.16.840.1.113883.10.20.22.2.17": "Observation",
    "2.16.840.1.113883.10.20.22.2.10": "Observation",
    "2.16.840.1.113883.10.20.22.2.23": "Device",
}

CCDA_ENCOUNTER_CODE_MAP: dict[str, VisitType] = {
    "IMP": VisitType.INPATIENT,
    "ACUTE": VisitType.INPATIENT,
    "NONAC": VisitType.INPATIENT,
    "EMER": VisitType.EMERGENCY,
    "ER": VisitType.EMERGENCY,
    "AMB": VisitType.OUTPATIENT,
    "VR": VisitType.OUTPATIENT,
}


# =============================================================================
# Clinical Status Value Mappings
# =============================================================================

GENDER_MAP: dict[str, Gender] = {
    # Common values
    "m": Gender.MALE,
    "male": Gender.MALE,
    "f": Gender.FEMALE,
    "female": Gender.FEMALE,
    "o": Gender.OTHER,
    "other": Gender.OTHER,
    "u": Gender.UNKNOWN,
    "unknown": Gender.UNKNOWN,
    "unk": Gender.UNKNOWN,
    # HL7v2 codes
    "a": Gender.OTHER,  # Ambiguous
    "n": Gender.UNKNOWN,  # Not applicable
    # FHIR codes
    "un": Gender.OTHER,
}

VISIT_TYPE_MAP: dict[str, VisitType] = {
    # Full names
    "inpatient": VisitType.INPATIENT,
    "outpatient": VisitType.OUTPATIENT,
    "emergency": VisitType.EMERGENCY,
    "observation": VisitType.OBSERVATION,
    "home": VisitType.HOME,
    "telehealth": VisitType.TELEHEALTH,
    # Abbreviations
    "ip": VisitType.INPATIENT,
    "op": VisitType.OUTPATIENT,
    "er": VisitType.EMERGENCY,
    "ed": VisitType.EMERGENCY,
    "obs": VisitType.OBSERVATION,
    "tele": VisitType.TELEHEALTH,
    "virtual": VisitType.TELEHEALTH,
    # Single letter codes
    "i": VisitType.INPATIENT,
    "o": VisitType.OUTPATIENT,
    "e": VisitType.EMERGENCY,
    # Other common terms
    "ambulatory": VisitType.OUTPATIENT,
    "office": VisitType.OUTPATIENT,
    "clinic": VisitType.OUTPATIENT,
    "hospital": VisitType.INPATIENT,
}

CONDITION_STATUS_MAP: dict[str, ConditionStatus] = {
    # FHIR clinical status values
    "active": ConditionStatus.ACTIVE,
    "recurrence": ConditionStatus.ACTIVE,
    "relapse": ConditionStatus.ACTIVE,
    "inactive": ConditionStatus.INACTIVE,
    "remission": ConditionStatus.INACTIVE,
    "resolved": ConditionStatus.RESOLVED,
    # Common synonyms
    "current": ConditionStatus.ACTIVE,
    "completed": ConditionStatus.RESOLVED,
    "aborted": ConditionStatus.INACTIVE,
    "chronic": ConditionStatus.ACTIVE,
}

DRUG_STATUS_MAP: dict[str, DrugStatus] = {
    # FHIR medication status values
    "active": DrugStatus.ACTIVE,
    "completed": DrugStatus.COMPLETED,
    "stopped": DrugStatus.STOPPED,
    "on-hold": DrugStatus.ON_HOLD,
    "cancelled": DrugStatus.STOPPED,
    "entered-in-error": DrugStatus.STOPPED,
    # Common synonyms
    "discontinued": DrugStatus.STOPPED,
    "hold": DrugStatus.ON_HOLD,
    "suspended": DrugStatus.ON_HOLD,
    "current": DrugStatus.ACTIVE,
    "finished": DrugStatus.COMPLETED,
}

PROCEDURE_STATUS_MAP: dict[str, ProcedureStatus] = {
    # FHIR procedure status values
    "completed": ProcedureStatus.COMPLETED,
    "in-progress": ProcedureStatus.IN_PROGRESS,
    "not-done": ProcedureStatus.NOT_DONE,
    "entered-in-error": ProcedureStatus.NOT_DONE,
    # Common synonyms
    "done": ProcedureStatus.COMPLETED,
    "pending": ProcedureStatus.IN_PROGRESS,
    "scheduled": ProcedureStatus.IN_PROGRESS,
    "cancelled": ProcedureStatus.NOT_DONE,
    "aborted": ProcedureStatus.NOT_DONE,
}


# =============================================================================
# FHIR Observation Category to Domain Mapping
# =============================================================================

FHIR_OBSERVATION_CATEGORY_MAP: dict[str, str] = {
    "vital-signs": "Measurement",
    "laboratory": "Measurement",
    "imaging": "Measurement",
    "procedure": "Measurement",
    "survey": "Observation",
    "exam": "Observation",
    "therapy": "Observation",
    "activity": "Observation",
    "social-history": "Observation",
}


# =============================================================================
# Helper Functions for Status Parsing
# =============================================================================

def parse_gender(value: str | None) -> Gender:
    """Parse a gender value to the Gender enum.

    Args:
        value: Raw gender value from source data.

    Returns:
        Corresponding Gender enum value.
    """
    if not value:
        return Gender.UNKNOWN
    return GENDER_MAP.get(value.lower().strip(), Gender.UNKNOWN)


def parse_visit_type(value: str | None) -> VisitType:
    """Parse a visit type value to the VisitType enum.

    Args:
        value: Raw visit type value from source data.

    Returns:
        Corresponding VisitType enum value.
    """
    if not value:
        return VisitType.UNKNOWN
    return VISIT_TYPE_MAP.get(value.lower().strip(), VisitType.UNKNOWN)


def parse_condition_status(value: str | None) -> ConditionStatus:
    """Parse a condition status value to the ConditionStatus enum.

    Args:
        value: Raw status value from source data.

    Returns:
        Corresponding ConditionStatus enum value.
    """
    if not value:
        return ConditionStatus.UNKNOWN
    return CONDITION_STATUS_MAP.get(value.lower().strip(), ConditionStatus.UNKNOWN)


def parse_drug_status(value: str | None) -> DrugStatus:
    """Parse a drug status value to the DrugStatus enum.

    Args:
        value: Raw status value from source data.

    Returns:
        Corresponding DrugStatus enum value.
    """
    if not value:
        return DrugStatus.UNKNOWN
    return DRUG_STATUS_MAP.get(value.lower().strip(), DrugStatus.UNKNOWN)


def parse_procedure_status(value: str | None) -> ProcedureStatus:
    """Parse a procedure status value to the ProcedureStatus enum.

    Args:
        value: Raw status value from source data.

    Returns:
        Corresponding ProcedureStatus enum value.
    """
    if not value:
        return ProcedureStatus.UNKNOWN
    return PROCEDURE_STATUS_MAP.get(value.lower().strip(), ProcedureStatus.UNKNOWN)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Code system mappings
    "CODE_SYSTEM_MAP",
    "normalize_code_system",
    "DEFAULT_CODE_SYSTEMS",
    # FHIR mappings
    "FHIR_RESOURCE_MAP",
    "FHIR_ENCOUNTER_CLASS_MAP",
    "FHIR_OBSERVATION_CATEGORY_MAP",
    # HL7v2 mappings
    "HL7_SEGMENT_MAP",
    "HL7_PATIENT_CLASS_MAP",
    "HL7_CODING_METHOD_MAP",
    # C-CDA mappings
    "CCDA_SECTION_TEMPLATE_IDS",
    "CCDA_SECTION_MAP",
    "CCDA_ENCOUNTER_CODE_MAP",
    # Status mappings
    "GENDER_MAP",
    "VISIT_TYPE_MAP",
    "CONDITION_STATUS_MAP",
    "DRUG_STATUS_MAP",
    "PROCEDURE_STATUS_MAP",
    # Helper functions
    "parse_gender",
    "parse_visit_type",
    "parse_condition_status",
    "parse_drug_status",
    "parse_procedure_status",
]
