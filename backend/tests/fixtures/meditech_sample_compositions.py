"""Sample Meditech-sourced OpenEHR compositions for replay validation (P1-031).

These fixtures represent realistic clinical encounters as they would arrive
after Meditech-to-OpenEHR transformation via the canonical contract
(P0-018-MEDITECH-OPENEHR-CNX).  Each composition has a deterministic
expected-output specification so replay tests can verify end-to-end
correctness.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Meditech source metadata (simulates what the adapter passes through)
# ---------------------------------------------------------------------------

MEDITECH_SOURCE_META_AU: dict[str, Any] = {
    "source_system": "meditech",
    "source_record_id": "MT-AU-2026-00421",
    "encounter_id": "ENC-2026-10087",
    "visit_id": "VIS-20260210-003",
    "pipeline_id": "pipeline-aus-prod-01",
    "source_record_type": "encounter",
    "site_id": "AU-MEL-ROYAL",
}


# ---------------------------------------------------------------------------
# Sample 1: Multi-domain encounter (condition + medication + vitals + procedure)
# ---------------------------------------------------------------------------

def build_meditech_encounter_composition() -> dict[str, Any]:
    """Full clinical encounter with all major entry types."""
    return {
        "_type": "COMPOSITION",
        "archetype_node_id": "openEHR-EHR-COMPOSITION.encounter.v1",
        "name": {"_type": "DV_TEXT", "value": "Meditech Clinical Encounter"},
        "language": {
            "_type": "CODE_PHRASE",
            "terminology_id": {"value": "ISO_639-1"},
            "code_string": "en",
        },
        "territory": {
            "_type": "CODE_PHRASE",
            "terminology_id": {"value": "ISO_3166-1"},
            "code_string": "AU",
        },
        "category": {
            "_type": "DV_CODED_TEXT",
            "value": "event",
            "defining_code": {
                "terminology_id": {"value": "openehr"},
                "code_string": "433",
            },
        },
        "composer": {"_type": "PARTY_IDENTIFIED", "name": "Dr. Sarah Chen"},
        "context": {
            "_type": "EVENT_CONTEXT",
            "start_time": {
                "_type": "DV_DATE_TIME",
                "value": "2026-02-10T09:30:00+11:00",
            },
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
            # --- Condition: Type 2 Diabetes ---
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
                                "value": "Type 2 diabetes mellitus",
                                "defining_code": {
                                    "terminology_id": {"value": "SNOMED-CT"},
                                    "code_string": "44054006",
                                },
                            },
                        },
                        {
                            "_type": "ELEMENT",
                            "name": {"_type": "DV_TEXT", "value": "Date/time of onset"},
                            "value": {"_type": "DV_DATE_TIME", "value": "2024-06-15T00:00:00Z"},
                        },
                    ],
                },
            },
            # --- Condition: Essential Hypertension ---
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
                                "value": "Essential hypertension",
                                "defining_code": {
                                    "terminology_id": {"value": "SNOMEDCT"},
                                    "code_string": "59621000",
                                },
                            },
                        },
                    ],
                },
            },
            # --- Medication: Metformin ---
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
                                        "value": "Metformin 500mg",
                                        "defining_code": {
                                            "terminology_id": {"value": "RXN"},
                                            "code_string": "6809",
                                        },
                                    },
                                },
                                {
                                    "_type": "ELEMENT",
                                    "name": {"_type": "DV_TEXT", "value": "Dose amount"},
                                    "value": {
                                        "_type": "DV_QUANTITY",
                                        "magnitude": 500.0,
                                        "units": "mg",
                                    },
                                },
                            ],
                        },
                    }
                ],
            },
            # --- Medication: Lisinopril ---
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
                                        "value": "Lisinopril 10mg",
                                        "defining_code": {
                                            "terminology_id": {"value": "RXNORM"},
                                            "code_string": "29046",
                                        },
                                    },
                                },
                            ],
                        },
                    }
                ],
            },
            # --- Blood Pressure ---
            {
                "_type": "OBSERVATION",
                "archetype_node_id": "openEHR-EHR-OBSERVATION.blood_pressure.v2",
                "name": {"_type": "DV_TEXT", "value": "Blood pressure"},
                "data": {
                    "_type": "HISTORY",
                    "events": [
                        {
                            "_type": "POINT_EVENT",
                            "time": {
                                "_type": "DV_DATE_TIME",
                                "value": "2026-02-10T09:35:00+11:00",
                            },
                            "data": {
                                "_type": "ITEM_TREE",
                                "items": [
                                    {
                                        "_type": "ELEMENT",
                                        "name": {"_type": "DV_TEXT", "value": "Systolic"},
                                        "value": {
                                            "_type": "DV_QUANTITY",
                                            "magnitude": 142.0,
                                            "units": "mm[Hg]",
                                        },
                                    },
                                    {
                                        "_type": "ELEMENT",
                                        "name": {"_type": "DV_TEXT", "value": "Diastolic"},
                                        "value": {
                                            "_type": "DV_QUANTITY",
                                            "magnitude": 88.0,
                                            "units": "mm[Hg]",
                                        },
                                    },
                                ],
                            },
                        }
                    ],
                },
            },
            # --- Body Temperature ---
            {
                "_type": "OBSERVATION",
                "archetype_node_id": "openEHR-EHR-OBSERVATION.body_temperature.v2",
                "name": {"_type": "DV_TEXT", "value": "Body temperature"},
                "data": {
                    "_type": "HISTORY",
                    "events": [
                        {
                            "_type": "POINT_EVENT",
                            "time": {
                                "_type": "DV_DATE_TIME",
                                "value": "2026-02-10T09:36:00+11:00",
                            },
                            "data": {
                                "_type": "ITEM_TREE",
                                "items": [
                                    {
                                        "_type": "ELEMENT",
                                        "name": {"_type": "DV_TEXT", "value": "Temperature"},
                                        "value": {
                                            "_type": "DV_QUANTITY",
                                            "magnitude": 36.8,
                                            "units": "Cel",
                                        },
                                    },
                                ],
                            },
                        }
                    ],
                },
            },
            # --- Procedure: Blood glucose test ---
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
                                "value": "Blood glucose measurement",
                                "defining_code": {
                                    "terminology_id": {"value": "SNOMED-CT"},
                                    "code_string": "33747003",
                                },
                            },
                        },
                        {
                            "_type": "ELEMENT",
                            "name": {"_type": "DV_TEXT", "value": "Procedure performed"},
                            "value": {"_type": "DV_DATE_TIME", "value": "2026-02-10T09:40:00+11:00"},
                        },
                    ],
                },
            },
            # --- Allergy: Penicillin ---
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
                                "value": "Penicillin",
                                "defining_code": {
                                    "terminology_id": {"value": "SCT"},
                                    "code_string": "91936005",
                                },
                            },
                        },
                        {
                            "_type": "ELEMENT",
                            "name": {"_type": "DV_TEXT", "value": "Category"},
                            "value": {"_type": "DV_TEXT", "value": "Drug"},
                        },
                    ],
                },
            },
        ],
    }


# ---------------------------------------------------------------------------
# Sample 2: Lab-only encounter (multiple lab results)
# ---------------------------------------------------------------------------

def build_meditech_lab_composition() -> dict[str, Any]:
    """Lab-only encounter with multiple test results."""
    return {
        "_type": "COMPOSITION",
        "archetype_node_id": "openEHR-EHR-COMPOSITION.encounter.v1",
        "name": {"_type": "DV_TEXT", "value": "Laboratory Results"},
        "language": {
            "_type": "CODE_PHRASE",
            "terminology_id": {"value": "ISO_639-1"},
            "code_string": "en",
        },
        "territory": {
            "_type": "CODE_PHRASE",
            "terminology_id": {"value": "ISO_3166-1"},
            "code_string": "AU",
        },
        "category": {
            "_type": "DV_CODED_TEXT",
            "value": "event",
            "defining_code": {
                "terminology_id": {"value": "openehr"},
                "code_string": "433",
            },
        },
        "composer": {"_type": "PARTY_IDENTIFIED", "name": "Pathology Lab"},
        "context": {
            "_type": "EVENT_CONTEXT",
            "start_time": {
                "_type": "DV_DATE_TIME",
                "value": "2026-02-10T11:00:00+11:00",
            },
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
            # --- HbA1c ---
            {
                "_type": "OBSERVATION",
                "archetype_node_id": "openEHR-EHR-OBSERVATION.laboratory_test_result.v1",
                "name": {"_type": "DV_TEXT", "value": "Laboratory test result"},
                "data": {
                    "_type": "HISTORY",
                    "events": [
                        {
                            "_type": "POINT_EVENT",
                            "time": {
                                "_type": "DV_DATE_TIME",
                                "value": "2026-02-10T10:45:00+11:00",
                            },
                            "data": {
                                "_type": "ITEM_TREE",
                                "items": [
                                    {
                                        "_type": "ELEMENT",
                                        "name": {"_type": "DV_TEXT", "value": "HbA1c"},
                                        "value": {
                                            "_type": "DV_QUANTITY",
                                            "magnitude": 7.2,
                                            "units": "%",
                                        },
                                    },
                                ],
                            },
                        }
                    ],
                },
            },
            # --- Fasting Glucose ---
            {
                "_type": "OBSERVATION",
                "archetype_node_id": "openEHR-EHR-OBSERVATION.laboratory_test_result.v1",
                "name": {"_type": "DV_TEXT", "value": "Laboratory test result"},
                "data": {
                    "_type": "HISTORY",
                    "events": [
                        {
                            "_type": "POINT_EVENT",
                            "time": {
                                "_type": "DV_DATE_TIME",
                                "value": "2026-02-10T10:50:00+11:00",
                            },
                            "data": {
                                "_type": "ITEM_TREE",
                                "items": [
                                    {
                                        "_type": "ELEMENT",
                                        "name": {"_type": "DV_TEXT", "value": "Fasting glucose"},
                                        "value": {
                                            "_type": "DV_QUANTITY",
                                            "magnitude": 8.1,
                                            "units": "mmol/L",
                                        },
                                    },
                                ],
                            },
                        }
                    ],
                },
            },
            # --- Serum Creatinine ---
            {
                "_type": "OBSERVATION",
                "archetype_node_id": "openEHR-EHR-OBSERVATION.laboratory_test_result.v1",
                "name": {"_type": "DV_TEXT", "value": "Laboratory test result"},
                "data": {
                    "_type": "HISTORY",
                    "events": [
                        {
                            "_type": "POINT_EVENT",
                            "time": {
                                "_type": "DV_DATE_TIME",
                                "value": "2026-02-10T10:55:00+11:00",
                            },
                            "data": {
                                "_type": "ITEM_TREE",
                                "items": [
                                    {
                                        "_type": "ELEMENT",
                                        "name": {"_type": "DV_TEXT", "value": "Serum creatinine"},
                                        "value": {
                                            "_type": "DV_QUANTITY",
                                            "magnitude": 92.0,
                                            "units": "umol/L",
                                        },
                                    },
                                ],
                            },
                        }
                    ],
                },
            },
        ],
    }


# ---------------------------------------------------------------------------
# Expected outputs — deterministic replay assertions
# ---------------------------------------------------------------------------

EXPECTED_ENCOUNTER_FACTS = {
    "total": 9,  # 2 conditions + 2 medications + 3 vitals (sys+dia+temp) + 1 procedure + 1 allergy
    "conditions": 2,
    "medications": 2,
    "measurements": 3,  # systolic, diastolic, temperature
    "procedures": 1,
    "allergies": 1,
    "condition_names": {"Type 2 diabetes mellitus", "Essential hypertension"},
    "medication_names": {"Metformin 500mg", "Lisinopril 10mg"},
    "allergy_names": {"Penicillin"},
    "procedure_names": {"Blood glucose measurement"},
}

EXPECTED_LAB_FACTS = {
    "total": 3,
    "conditions": 0,
    "medications": 0,
    "measurements": 3,
    "procedures": 0,
    "allergies": 0,
    "measurement_labels": {"HbA1c", "Fasting glucose", "Serum creatinine"},
}

# Contract lineage fields expected when source_metadata is from Meditech
EXPECTED_LINEAGE_CONTRACT_FIELDS = {
    "step": "meditech_to_openehr_adapter",
    "contract_id": "P0-018-MEDITECH-OPENEHR-CNX",
    "source_system": "meditech",
}
