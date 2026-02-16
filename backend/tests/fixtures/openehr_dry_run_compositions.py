"""Dry-run test compositions for OpenEHR reconciliation & rollback (P0-019).

5 mixed-domain compositions covering all domain combinations, each with
deterministic EXPECTED_* dicts for assertion in reconciliation tests.
"""

from __future__ import annotations

from typing import Any


# ===========================================================================
# Composition 1: Mixed-all — condition + medication + vitals + procedure + allergy
# (Reuses structure from build_meditech_encounter_composition)
# ===========================================================================

def build_mixed_all_composition() -> dict[str, Any]:
    """Full clinical encounter with all 5 domain types."""
    return {
        "_type": "COMPOSITION",
        "archetype_node_id": "openEHR-EHR-COMPOSITION.encounter.v1",
        "name": {"_type": "DV_TEXT", "value": "Mixed-All Encounter"},
        "language": {
            "_type": "CODE_PHRASE",
            "terminology_id": {"value": "ISO_639-1"},
            "code_string": "en",
        },
        "territory": {
            "_type": "CODE_PHRASE",
            "terminology_id": {"value": "ISO_3166-1"},
            "code_string": "US",
        },
        "category": {
            "_type": "DV_CODED_TEXT",
            "value": "event",
            "defining_code": {
                "terminology_id": {"value": "openehr"},
                "code_string": "433",
            },
        },
        "composer": {"_type": "PARTY_IDENTIFIED", "name": "Dr. Reconcile"},
        "context": {
            "_type": "EVENT_CONTEXT",
            "start_time": {"_type": "DV_DATE_TIME", "value": "2026-01-20T08:00:00Z"},
            "setting": {
                "_type": "DV_CODED_TEXT",
                "value": "primary medical care",
                "defining_code": {
                    "terminology_id": {"value": "openehr"},
                    "code_string": "228",
                },
            },
        },
        "content": [
            # Condition: Asthma
            {
                "_type": "EVALUATION",
                "archetype_node_id": "openEHR-EHR-EVALUATION.problem_diagnosis.v1",
                "name": {"_type": "DV_TEXT", "value": "Problem/Diagnosis"},
                "data": {
                    "_type": "ITEM_TREE",
                    "items": [
                        {
                            "_type": "ELEMENT",
                            "name": {"_type": "DV_TEXT", "value": "Problem/Diagnosis name"},
                            "value": {
                                "_type": "DV_CODED_TEXT",
                                "value": "Asthma",
                                "defining_code": {
                                    "terminology_id": {"value": "SNOMED-CT"},
                                    "code_string": "195967001",
                                },
                            },
                        },
                    ],
                },
            },
            # Medication: Salbutamol
            {
                "_type": "INSTRUCTION",
                "archetype_node_id": "openEHR-EHR-INSTRUCTION.medication_order.v3",
                "name": {"_type": "DV_TEXT", "value": "Medication order"},
                "activities": [
                    {
                        "_type": "ACTIVITY",
                        "description": {
                            "_type": "ITEM_TREE",
                            "items": [
                                {
                                    "_type": "ELEMENT",
                                    "name": {"_type": "DV_TEXT", "value": "Medication item"},
                                    "value": {
                                        "_type": "DV_CODED_TEXT",
                                        "value": "Salbutamol 100mcg",
                                        "defining_code": {
                                            "terminology_id": {"value": "RXNORM"},
                                            "code_string": "435",
                                        },
                                    },
                                },
                            ],
                        },
                    }
                ],
            },
            # Blood Pressure
            {
                "_type": "OBSERVATION",
                "archetype_node_id": "openEHR-EHR-OBSERVATION.blood_pressure.v2",
                "name": {"_type": "DV_TEXT", "value": "Blood Pressure"},
                "data": {
                    "_type": "HISTORY",
                    "events": [
                        {
                            "_type": "POINT_EVENT",
                            "time": {"_type": "DV_DATE_TIME", "value": "2026-01-20T08:10:00Z"},
                            "data": {
                                "_type": "ITEM_TREE",
                                "items": [
                                    {
                                        "_type": "ELEMENT",
                                        "name": {"_type": "DV_TEXT", "value": "Systolic"},
                                        "value": {"_type": "DV_QUANTITY", "magnitude": 118.0, "units": "mm[Hg]"},
                                    },
                                    {
                                        "_type": "ELEMENT",
                                        "name": {"_type": "DV_TEXT", "value": "Diastolic"},
                                        "value": {"_type": "DV_QUANTITY", "magnitude": 76.0, "units": "mm[Hg]"},
                                    },
                                ],
                            },
                        }
                    ],
                },
            },
            # Procedure: Spirometry
            {
                "_type": "ACTION",
                "archetype_node_id": "openEHR-EHR-ACTION.procedure.v1",
                "name": {"_type": "DV_TEXT", "value": "Procedure"},
                "description": {
                    "_type": "ITEM_TREE",
                    "items": [
                        {
                            "_type": "ELEMENT",
                            "name": {"_type": "DV_TEXT", "value": "Procedure name"},
                            "value": {
                                "_type": "DV_CODED_TEXT",
                                "value": "Spirometry",
                                "defining_code": {
                                    "terminology_id": {"value": "SNOMED-CT"},
                                    "code_string": "127783003",
                                },
                            },
                        },
                    ],
                },
            },
            # Allergy: Aspirin
            {
                "_type": "EVALUATION",
                "archetype_node_id": "openEHR-EHR-EVALUATION.adverse_reaction_risk.v1",
                "name": {"_type": "DV_TEXT", "value": "Adverse reaction risk"},
                "data": {
                    "_type": "ITEM_TREE",
                    "items": [
                        {
                            "_type": "ELEMENT",
                            "name": {"_type": "DV_TEXT", "value": "Substance"},
                            "value": {
                                "_type": "DV_CODED_TEXT",
                                "value": "Aspirin",
                                "defining_code": {
                                    "terminology_id": {"value": "SNOMED-CT"},
                                    "code_string": "387458008",
                                },
                            },
                        },
                    ],
                },
            },
        ],
    }


EXPECTED_MIXED_ALL = {
    "conditions": 1,
    "medications": 1,
    "measurements": 2,  # systolic + diastolic
    "procedures": 1,
    "allergies": 1,
    "total_facts": 6,
    "concept_names": {
        "Asthma", "Salbutamol 100mcg",
        "Blood Pressure - Systolic", "Blood Pressure - Diastolic",
        "Spirometry", "Aspirin",
    },
}


# ===========================================================================
# Composition 2: Labs-only — 3 lab results
# ===========================================================================

def build_labs_only_composition() -> dict[str, Any]:
    """Labs-only encounter with 3 lab test results."""
    return {
        "_type": "COMPOSITION",
        "archetype_node_id": "openEHR-EHR-COMPOSITION.encounter.v1",
        "name": {"_type": "DV_TEXT", "value": "Lab Results"},
        "language": {
            "_type": "CODE_PHRASE",
            "terminology_id": {"value": "ISO_639-1"},
            "code_string": "en",
        },
        "territory": {
            "_type": "CODE_PHRASE",
            "terminology_id": {"value": "ISO_3166-1"},
            "code_string": "US",
        },
        "category": {
            "_type": "DV_CODED_TEXT",
            "value": "event",
            "defining_code": {
                "terminology_id": {"value": "openehr"},
                "code_string": "433",
            },
        },
        "composer": {"_type": "PARTY_IDENTIFIED", "name": "Lab System"},
        "context": {
            "_type": "EVENT_CONTEXT",
            "start_time": {"_type": "DV_DATE_TIME", "value": "2026-01-21T09:00:00Z"},
            "setting": {
                "_type": "DV_CODED_TEXT",
                "value": "secondary medical care",
                "defining_code": {
                    "terminology_id": {"value": "openehr"},
                    "code_string": "232",
                },
            },
        },
        "content": [
            _lab_entry("Hemoglobin", 14.2, "g/dL"),
            _lab_entry("White blood cell count", 7.5, "10*9/L"),
            _lab_entry("Platelet count", 250.0, "10*9/L"),
        ],
    }


def _lab_entry(name: str, magnitude: float, units: str) -> dict[str, Any]:
    return {
        "_type": "OBSERVATION",
        "archetype_node_id": "openEHR-EHR-OBSERVATION.laboratory_test_result.v1",
        "name": {"_type": "DV_TEXT", "value": "Laboratory test result"},
        "data": {
            "_type": "HISTORY",
            "events": [
                {
                    "_type": "POINT_EVENT",
                    "time": {"_type": "DV_DATE_TIME", "value": "2026-01-21T09:30:00Z"},
                    "data": {
                        "_type": "ITEM_TREE",
                        "items": [
                            {
                                "_type": "ELEMENT",
                                "name": {"_type": "DV_TEXT", "value": name},
                                "value": {"_type": "DV_QUANTITY", "magnitude": magnitude, "units": units},
                            },
                        ],
                    },
                }
            ],
        },
    }


EXPECTED_LABS_ONLY = {
    "conditions": 0,
    "medications": 0,
    "measurements": 3,
    "procedures": 0,
    "allergies": 0,
    "total_facts": 3,
    "concept_names": {"Hemoglobin", "White blood cell count", "Platelet count"},
}


# ===========================================================================
# Composition 3: Medications-heavy — 4 medications + 1 condition (polypharmacy)
# ===========================================================================

def build_medications_heavy_composition() -> dict[str, Any]:
    """Polypharmacy scenario: 4 medications + 1 condition."""
    return {
        "_type": "COMPOSITION",
        "archetype_node_id": "openEHR-EHR-COMPOSITION.encounter.v1",
        "name": {"_type": "DV_TEXT", "value": "Polypharmacy Review"},
        "language": {
            "_type": "CODE_PHRASE",
            "terminology_id": {"value": "ISO_639-1"},
            "code_string": "en",
        },
        "territory": {
            "_type": "CODE_PHRASE",
            "terminology_id": {"value": "ISO_3166-1"},
            "code_string": "US",
        },
        "category": {
            "_type": "DV_CODED_TEXT",
            "value": "event",
            "defining_code": {
                "terminology_id": {"value": "openehr"},
                "code_string": "433",
            },
        },
        "composer": {"_type": "PARTY_IDENTIFIED", "name": "Dr. Pharmacy"},
        "context": {
            "_type": "EVENT_CONTEXT",
            "start_time": {"_type": "DV_DATE_TIME", "value": "2026-01-22T10:00:00Z"},
            "setting": {
                "_type": "DV_CODED_TEXT",
                "value": "primary medical care",
                "defining_code": {
                    "terminology_id": {"value": "openehr"},
                    "code_string": "228",
                },
            },
        },
        "content": [
            # Condition: Heart failure
            {
                "_type": "EVALUATION",
                "archetype_node_id": "openEHR-EHR-EVALUATION.problem_diagnosis.v1",
                "name": {"_type": "DV_TEXT", "value": "Problem/Diagnosis"},
                "data": {
                    "_type": "ITEM_TREE",
                    "items": [
                        {
                            "_type": "ELEMENT",
                            "name": {"_type": "DV_TEXT", "value": "Problem/Diagnosis name"},
                            "value": {
                                "_type": "DV_CODED_TEXT",
                                "value": "Heart failure",
                                "defining_code": {
                                    "terminology_id": {"value": "SNOMED-CT"},
                                    "code_string": "84114007",
                                },
                            },
                        },
                    ],
                },
            },
            # Medication 1: Furosemide
            _med_entry("Furosemide 40mg", "4603", 40.0, "mg"),
            # Medication 2: Lisinopril
            _med_entry("Lisinopril 10mg", "29046", 10.0, "mg"),
            # Medication 3: Carvedilol
            _med_entry("Carvedilol 12.5mg", "20352", 12.5, "mg"),
            # Medication 4: Spironolactone
            _med_entry("Spironolactone 25mg", "9997", 25.0, "mg"),
        ],
    }


def _med_entry(
    name: str, code: str, dose: float | None = None, dose_unit: str | None = None
) -> dict[str, Any]:
    items: list[dict[str, Any]] = [
        {
            "_type": "ELEMENT",
            "name": {"_type": "DV_TEXT", "value": "Medication item"},
            "value": {
                "_type": "DV_CODED_TEXT",
                "value": name,
                "defining_code": {
                    "terminology_id": {"value": "RXNORM"},
                    "code_string": code,
                },
            },
        },
    ]
    if dose is not None and dose_unit:
        items.append({
            "_type": "ELEMENT",
            "name": {"_type": "DV_TEXT", "value": "Dose amount"},
            "value": {"_type": "DV_QUANTITY", "magnitude": dose, "units": dose_unit},
        })
    return {
        "_type": "INSTRUCTION",
        "archetype_node_id": "openEHR-EHR-INSTRUCTION.medication_order.v3",
        "name": {"_type": "DV_TEXT", "value": "Medication order"},
        "activities": [
            {
                "_type": "ACTIVITY",
                "description": {"_type": "ITEM_TREE", "items": items},
            }
        ],
    }


EXPECTED_MEDICATIONS_HEAVY = {
    "conditions": 1,
    "medications": 4,
    "measurements": 0,
    "procedures": 0,
    "allergies": 0,
    "total_facts": 5,
    "concept_names": {
        "Heart failure",
        "Furosemide 40mg", "Lisinopril 10mg",
        "Carvedilol 12.5mg", "Spironolactone 25mg",
    },
}


# ===========================================================================
# Composition 4: Procedures-vitals — 2 procedures + BP + SpO2 + weight (pre-op)
# ===========================================================================

def build_procedures_vitals_composition() -> dict[str, Any]:
    """Surgical pre-op scenario: 2 procedures + vital signs."""
    return {
        "_type": "COMPOSITION",
        "archetype_node_id": "openEHR-EHR-COMPOSITION.encounter.v1",
        "name": {"_type": "DV_TEXT", "value": "Pre-Op Assessment"},
        "language": {
            "_type": "CODE_PHRASE",
            "terminology_id": {"value": "ISO_639-1"},
            "code_string": "en",
        },
        "territory": {
            "_type": "CODE_PHRASE",
            "terminology_id": {"value": "ISO_3166-1"},
            "code_string": "US",
        },
        "category": {
            "_type": "DV_CODED_TEXT",
            "value": "event",
            "defining_code": {
                "terminology_id": {"value": "openehr"},
                "code_string": "433",
            },
        },
        "composer": {"_type": "PARTY_IDENTIFIED", "name": "Surgical Team"},
        "context": {
            "_type": "EVENT_CONTEXT",
            "start_time": {"_type": "DV_DATE_TIME", "value": "2026-01-23T06:00:00Z"},
            "setting": {
                "_type": "DV_CODED_TEXT",
                "value": "secondary medical care",
                "defining_code": {
                    "terminology_id": {"value": "openehr"},
                    "code_string": "232",
                },
            },
        },
        "content": [
            # Procedure 1: Appendectomy
            {
                "_type": "ACTION",
                "archetype_node_id": "openEHR-EHR-ACTION.procedure.v1",
                "name": {"_type": "DV_TEXT", "value": "Procedure"},
                "description": {
                    "_type": "ITEM_TREE",
                    "items": [
                        {
                            "_type": "ELEMENT",
                            "name": {"_type": "DV_TEXT", "value": "Procedure name"},
                            "value": {
                                "_type": "DV_CODED_TEXT",
                                "value": "Appendectomy",
                                "defining_code": {
                                    "terminology_id": {"value": "SNOMED-CT"},
                                    "code_string": "80146002",
                                },
                            },
                        },
                    ],
                },
                "time": {"_type": "DV_DATE_TIME", "value": "2026-01-23T07:00:00Z"},
            },
            # Procedure 2: Wound closure
            {
                "_type": "ACTION",
                "archetype_node_id": "openEHR-EHR-ACTION.procedure.v1",
                "name": {"_type": "DV_TEXT", "value": "Procedure"},
                "description": {
                    "_type": "ITEM_TREE",
                    "items": [
                        {
                            "_type": "ELEMENT",
                            "name": {"_type": "DV_TEXT", "value": "Procedure name"},
                            "value": {
                                "_type": "DV_CODED_TEXT",
                                "value": "Wound closure",
                                "defining_code": {
                                    "terminology_id": {"value": "SNOMED-CT"},
                                    "code_string": "385949008",
                                },
                            },
                        },
                    ],
                },
                "time": {"_type": "DV_DATE_TIME", "value": "2026-01-23T07:45:00Z"},
            },
            # Blood Pressure
            {
                "_type": "OBSERVATION",
                "archetype_node_id": "openEHR-EHR-OBSERVATION.blood_pressure.v2",
                "name": {"_type": "DV_TEXT", "value": "Blood Pressure"},
                "data": {
                    "_type": "HISTORY",
                    "events": [
                        {
                            "_type": "POINT_EVENT",
                            "time": {"_type": "DV_DATE_TIME", "value": "2026-01-23T06:05:00Z"},
                            "data": {
                                "_type": "ITEM_TREE",
                                "items": [
                                    {
                                        "_type": "ELEMENT",
                                        "name": {"_type": "DV_TEXT", "value": "Systolic"},
                                        "value": {"_type": "DV_QUANTITY", "magnitude": 130.0, "units": "mm[Hg]"},
                                    },
                                    {
                                        "_type": "ELEMENT",
                                        "name": {"_type": "DV_TEXT", "value": "Diastolic"},
                                        "value": {"_type": "DV_QUANTITY", "magnitude": 82.0, "units": "mm[Hg]"},
                                    },
                                ],
                            },
                        }
                    ],
                },
            },
            # SpO2
            {
                "_type": "OBSERVATION",
                "archetype_node_id": "openEHR-EHR-OBSERVATION.pulse_oximetry.v1",
                "name": {"_type": "DV_TEXT", "value": "SpO2"},
                "data": {
                    "_type": "HISTORY",
                    "events": [
                        {
                            "_type": "POINT_EVENT",
                            "time": {"_type": "DV_DATE_TIME", "value": "2026-01-23T06:05:00Z"},
                            "data": {
                                "_type": "ITEM_TREE",
                                "items": [
                                    {
                                        "_type": "ELEMENT",
                                        "name": {"_type": "DV_TEXT", "value": "SpO2"},
                                        "value": {"_type": "DV_QUANTITY", "magnitude": 99.0, "units": "%"},
                                    },
                                ],
                            },
                        }
                    ],
                },
            },
            # Body Weight
            {
                "_type": "OBSERVATION",
                "archetype_node_id": "openEHR-EHR-OBSERVATION.body_weight.v2",
                "name": {"_type": "DV_TEXT", "value": "Body weight"},
                "data": {
                    "_type": "HISTORY",
                    "events": [
                        {
                            "_type": "POINT_EVENT",
                            "time": {"_type": "DV_DATE_TIME", "value": "2026-01-23T06:03:00Z"},
                            "data": {
                                "_type": "ITEM_TREE",
                                "items": [
                                    {
                                        "_type": "ELEMENT",
                                        "name": {"_type": "DV_TEXT", "value": "Weight"},
                                        "value": {"_type": "DV_QUANTITY", "magnitude": 72.0, "units": "kg"},
                                    },
                                ],
                            },
                        }
                    ],
                },
            },
        ],
    }


EXPECTED_PROCEDURES_VITALS = {
    "conditions": 0,
    "medications": 0,
    "measurements": 4,  # systolic + diastolic + SpO2 + weight
    "procedures": 2,
    "allergies": 0,
    "total_facts": 6,
    "concept_names": {
        "Appendectomy", "Wound closure",
        "Blood Pressure - Systolic", "Blood Pressure - Diastolic",
        "SpO2", "Weight",
    },
}


# ===========================================================================
# Composition 5: Allergies-conditions — 3 allergies + 2 conditions (intake)
# ===========================================================================

def build_allergies_conditions_composition() -> dict[str, Any]:
    """Allergy-focused intake: 3 allergies + 2 conditions."""
    return {
        "_type": "COMPOSITION",
        "archetype_node_id": "openEHR-EHR-COMPOSITION.encounter.v1",
        "name": {"_type": "DV_TEXT", "value": "Allergy Intake"},
        "language": {
            "_type": "CODE_PHRASE",
            "terminology_id": {"value": "ISO_639-1"},
            "code_string": "en",
        },
        "territory": {
            "_type": "CODE_PHRASE",
            "terminology_id": {"value": "ISO_3166-1"},
            "code_string": "US",
        },
        "category": {
            "_type": "DV_CODED_TEXT",
            "value": "event",
            "defining_code": {
                "terminology_id": {"value": "openehr"},
                "code_string": "433",
            },
        },
        "composer": {"_type": "PARTY_IDENTIFIED", "name": "Intake Nurse"},
        "context": {
            "_type": "EVENT_CONTEXT",
            "start_time": {"_type": "DV_DATE_TIME", "value": "2026-01-24T14:00:00Z"},
            "setting": {
                "_type": "DV_CODED_TEXT",
                "value": "primary medical care",
                "defining_code": {
                    "terminology_id": {"value": "openehr"},
                    "code_string": "228",
                },
            },
        },
        "content": [
            # Allergy 1: Penicillin
            _allergy_entry("Penicillin", "91936005"),
            # Allergy 2: Sulfonamides
            _allergy_entry("Sulfonamides", "91939003"),
            # Allergy 3: Latex
            _allergy_entry("Latex", "111088007"),
            # Condition 1: Allergic rhinitis
            _condition_entry("Allergic rhinitis", "61582004"),
            # Condition 2: Eczema
            _condition_entry("Eczema", "43116000"),
        ],
    }


def _allergy_entry(substance: str, code: str) -> dict[str, Any]:
    return {
        "_type": "EVALUATION",
        "archetype_node_id": "openEHR-EHR-EVALUATION.adverse_reaction_risk.v1",
        "name": {"_type": "DV_TEXT", "value": "Adverse reaction risk"},
        "data": {
            "_type": "ITEM_TREE",
            "items": [
                {
                    "_type": "ELEMENT",
                    "name": {"_type": "DV_TEXT", "value": "Substance"},
                    "value": {
                        "_type": "DV_CODED_TEXT",
                        "value": substance,
                        "defining_code": {
                            "terminology_id": {"value": "SNOMED-CT"},
                            "code_string": code,
                        },
                    },
                },
            ],
        },
    }


def _condition_entry(name: str, code: str) -> dict[str, Any]:
    return {
        "_type": "EVALUATION",
        "archetype_node_id": "openEHR-EHR-EVALUATION.problem_diagnosis.v1",
        "name": {"_type": "DV_TEXT", "value": "Problem/Diagnosis"},
        "data": {
            "_type": "ITEM_TREE",
            "items": [
                {
                    "_type": "ELEMENT",
                    "name": {"_type": "DV_TEXT", "value": "Problem/Diagnosis name"},
                    "value": {
                        "_type": "DV_CODED_TEXT",
                        "value": name,
                        "defining_code": {
                            "terminology_id": {"value": "SNOMED-CT"},
                            "code_string": code,
                        },
                    },
                },
            ],
        },
    }


EXPECTED_ALLERGIES_CONDITIONS = {
    "conditions": 2,
    "medications": 0,
    "measurements": 0,
    "procedures": 0,
    "allergies": 3,
    "total_facts": 5,
    "concept_names": {
        "Penicillin", "Sulfonamides", "Latex",
        "Allergic rhinitis", "Eczema",
    },
}


# ===========================================================================
# All compositions + expected outputs, keyed for parametrized tests
# ===========================================================================

ALL_COMPOSITIONS = {
    "mixed_all": (build_mixed_all_composition, EXPECTED_MIXED_ALL),
    "labs_only": (build_labs_only_composition, EXPECTED_LABS_ONLY),
    "medications_heavy": (build_medications_heavy_composition, EXPECTED_MEDICATIONS_HEAVY),
    "procedures_vitals": (build_procedures_vitals_composition, EXPECTED_PROCEDURES_VITALS),
    "allergies_conditions": (build_allergies_conditions_composition, EXPECTED_ALLERGIES_CONDITIONS),
}
