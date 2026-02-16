"""OpenEHR Export Service - Export ClinicalFacts as OpenEHR COMPOSITION.

Builds standard OpenEHR RM structures including DV_CODED_TEXT, DV_QUANTITY,
DV_DATE_TIME, and DV_TEXT mapped from ClinicalFact domain and properties.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Domain -> archetype mapping
DOMAIN_ARCHETYPE_MAP: dict[str, str] = {
    "condition": "openEHR-EHR-EVALUATION.problem_diagnosis.v1",
    "drug": "openEHR-EHR-INSTRUCTION.medication_order.v3",
    "measurement": "openEHR-EHR-OBSERVATION.laboratory_test_result.v1",
    "procedure": "openEHR-EHR-ACTION.procedure.v1",
    "observation": "openEHR-EHR-EVALUATION.adverse_reaction_risk.v1",
}

# Measurement concept name -> specific observation archetype
MEASUREMENT_ARCHETYPE_MAP: dict[str, str] = {
    "blood pressure": "openEHR-EHR-OBSERVATION.blood_pressure.v2",
    "systolic": "openEHR-EHR-OBSERVATION.blood_pressure.v2",
    "diastolic": "openEHR-EHR-OBSERVATION.blood_pressure.v2",
    "temperature": "openEHR-EHR-OBSERVATION.body_temperature.v2",
    "body temperature": "openEHR-EHR-OBSERVATION.body_temperature.v2",
    "weight": "openEHR-EHR-OBSERVATION.body_weight.v2",
    "body weight": "openEHR-EHR-OBSERVATION.body_weight.v2",
    "height": "openEHR-EHR-OBSERVATION.height.v2",
    "body height": "openEHR-EHR-OBSERVATION.height.v2",
    "heart rate": "openEHR-EHR-OBSERVATION.pulse.v1",
    "pulse": "openEHR-EHR-OBSERVATION.pulse.v1",
    "spo2": "openEHR-EHR-OBSERVATION.pulse_oximetry.v1",
    "oxygen saturation": "openEHR-EHR-OBSERVATION.pulse_oximetry.v1",
    "pulse oximetry": "openEHR-EHR-OBSERVATION.pulse_oximetry.v1",
}


# ============================================================================
# RM Data Type Builders
# ============================================================================


def build_dv_text(value: str) -> dict[str, Any]:
    """Build a DV_TEXT RM structure."""
    return {"_type": "DV_TEXT", "value": value}


def build_dv_coded_text(
    value: str,
    code: str | None = None,
    terminology_id: str | None = None,
) -> dict[str, Any]:
    """Build a DV_CODED_TEXT RM structure."""
    result: dict[str, Any] = {"_type": "DV_CODED_TEXT", "value": value}
    if code and terminology_id:
        result["defining_code"] = {
            "terminology_id": {"value": terminology_id},
            "code_string": code,
        }
    return result


def build_dv_quantity(magnitude: float, units: str) -> dict[str, Any]:
    """Build a DV_QUANTITY RM structure."""
    return {"_type": "DV_QUANTITY", "magnitude": magnitude, "units": units}


def build_dv_date_time(dt: datetime | str | None = None) -> dict[str, Any]:
    """Build a DV_DATE_TIME RM structure."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    if isinstance(dt, datetime):
        dt = dt.isoformat()
    return {"_type": "DV_DATE_TIME", "value": dt}


def build_element(name: str, value: dict[str, Any]) -> dict[str, Any]:
    """Build an ELEMENT RM structure."""
    return {
        "_type": "ELEMENT",
        "name": build_dv_text(name),
        "value": value,
    }


# ============================================================================
# Export Service
# ============================================================================


class OpenEHRExporterService:
    """Service for exporting ClinicalFacts as OpenEHR COMPOSITIONs."""

    def export_fact(self, fact: Any) -> dict[str, Any]:
        """Export a single ClinicalFact as an archetype entry dict.

        Args:
            fact: ClinicalFact ORM object or dict-like with domain, concept_name, etc.

        Returns:
            OpenEHR entry dict matching the appropriate archetype.
        """
        domain = self._get_domain(fact)
        concept_name = self._get_attr(fact, "concept_name", "Unknown")

        if domain == "condition":
            return self._export_condition(fact)
        elif domain == "drug":
            return self._export_drug(fact)
        elif domain == "measurement":
            return self._export_measurement(fact)
        elif domain == "procedure":
            return self._export_procedure(fact)
        elif domain == "observation":
            return self._export_allergy(fact)
        else:
            return self._export_generic(fact)

    def export_facts(
        self,
        facts: list[Any],
        patient_id: str,
        *,
        composer_name: str = "System",
        territory: str = "US",
        language: str = "en",
    ) -> dict[str, Any]:
        """Export multiple ClinicalFacts as a full COMPOSITION.

        Args:
            facts: List of ClinicalFact objects.
            patient_id: Patient identifier.
            composer_name: Name of the composer.
            territory: ISO 3166-1 territory code.
            language: ISO 639-1 language code.

        Returns:
            Full OpenEHR COMPOSITION dict.
        """
        content = [self.export_fact(f) for f in facts]

        return {
            "_type": "COMPOSITION",
            "archetype_node_id": "openEHR-EHR-COMPOSITION.encounter.v1",
            "name": build_dv_text("Clinical Encounter"),
            "language": {
                "_type": "CODE_PHRASE",
                "terminology_id": {"value": "ISO_639-1"},
                "code_string": language,
            },
            "territory": {
                "_type": "CODE_PHRASE",
                "terminology_id": {"value": "ISO_3166-1"},
                "code_string": territory,
            },
            "category": build_dv_coded_text("event", "433", "openehr"),
            "composer": {
                "_type": "PARTY_IDENTIFIED",
                "name": composer_name,
            },
            "context": {
                "_type": "EVENT_CONTEXT",
                "start_time": build_dv_date_time(),
                "setting": build_dv_coded_text(
                    "primary medical care", "228", "openehr"
                ),
                "other_context": {
                    "_type": "ITEM_TREE",
                    "items": [
                        build_element("Patient ID", build_dv_text(patient_id)),
                    ],
                },
            },
            "content": content,
        }

    # -------------------------------------------------------------------------
    # Helper to extract attributes from ORM objects or dicts
    # -------------------------------------------------------------------------

    @staticmethod
    def _get_attr(obj: Any, attr: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(attr, default)
        return getattr(obj, attr, default)

    @staticmethod
    def _get_domain(obj: Any) -> str:
        if isinstance(obj, dict):
            domain = obj.get("domain", "")
        else:
            domain = getattr(obj, "domain", "")
        if hasattr(domain, "value"):
            return domain.value
        return str(domain).lower()

    # -------------------------------------------------------------------------
    # Domain-specific exporters
    # -------------------------------------------------------------------------

    def _export_condition(self, fact: Any) -> dict[str, Any]:
        """Export a condition fact as EVALUATION.problem_diagnosis.v1."""
        concept_name = self._get_attr(fact, "concept_name", "Unknown condition")
        omop_id = self._get_attr(fact, "omop_concept_id")
        start_date = self._get_attr(fact, "start_date")

        items = [
            build_element(
                "Problem/Diagnosis name",
                build_dv_coded_text(
                    concept_name,
                    str(omop_id) if omop_id else None,
                    "OMOP" if omop_id else None,
                ),
            ),
        ]

        if start_date:
            items.append(
                build_element("Date/time of onset", build_dv_date_time(start_date))
            )

        return {
            "_type": "EVALUATION",
            "archetype_node_id": DOMAIN_ARCHETYPE_MAP["condition"],
            "name": build_dv_text("Problem/Diagnosis"),
            "data": {
                "_type": "ITEM_TREE",
                "items": items,
            },
        }

    def _export_drug(self, fact: Any) -> dict[str, Any]:
        """Export a drug fact as INSTRUCTION.medication_order.v3."""
        concept_name = self._get_attr(fact, "concept_name", "Unknown medication")
        omop_id = self._get_attr(fact, "omop_concept_id")

        items = [
            build_element(
                "Medication item",
                build_dv_coded_text(
                    concept_name,
                    str(omop_id) if omop_id else None,
                    "OMOP" if omop_id else None,
                ),
            ),
        ]

        return {
            "_type": "INSTRUCTION",
            "archetype_node_id": DOMAIN_ARCHETYPE_MAP["drug"],
            "name": build_dv_text("Medication order"),
            "activities": [
                {
                    "_type": "ACTIVITY",
                    "description": {
                        "_type": "ITEM_TREE",
                        "items": items,
                    },
                }
            ],
        }

    def _export_measurement(self, fact: Any) -> dict[str, Any]:
        """Export a measurement fact as the appropriate OBSERVATION archetype."""
        concept_name = self._get_attr(fact, "concept_name", "Unknown measurement")
        concept_lower = concept_name.lower()

        # Select the most specific archetype
        archetype = DOMAIN_ARCHETYPE_MAP["measurement"]  # default to lab
        for key, arch in MEASUREMENT_ARCHETYPE_MAP.items():
            if key in concept_lower:
                archetype = arch
                break

        # Build observation items
        items = []

        # Check if we have numeric value in properties or as a separate field
        value = None
        unit = None

        # Try properties first (from import)
        props = self._get_attr(fact, "properties")
        if isinstance(props, dict):
            value = props.get("value")
            unit = props.get("unit")

        if value is not None and unit:
            items.append(
                build_element(concept_name, build_dv_quantity(float(value), unit))
            )
        else:
            items.append(
                build_element(concept_name, build_dv_text(str(concept_name)))
            )

        return {
            "_type": "OBSERVATION",
            "archetype_node_id": archetype,
            "name": build_dv_text(concept_name),
            "data": {
                "_type": "HISTORY",
                "events": [
                    {
                        "_type": "POINT_EVENT",
                        "time": build_dv_date_time(),
                        "data": {
                            "_type": "ITEM_TREE",
                            "items": items,
                        },
                    }
                ],
            },
        }

    def _export_procedure(self, fact: Any) -> dict[str, Any]:
        """Export a procedure fact as ACTION.procedure.v1."""
        concept_name = self._get_attr(fact, "concept_name", "Unknown procedure")
        omop_id = self._get_attr(fact, "omop_concept_id")
        start_date = self._get_attr(fact, "start_date")

        items = [
            build_element(
                "Procedure name",
                build_dv_coded_text(
                    concept_name,
                    str(omop_id) if omop_id else None,
                    "OMOP" if omop_id else None,
                ),
            ),
        ]

        result: dict[str, Any] = {
            "_type": "ACTION",
            "archetype_node_id": DOMAIN_ARCHETYPE_MAP["procedure"],
            "name": build_dv_text("Procedure"),
            "description": {
                "_type": "ITEM_TREE",
                "items": items,
            },
        }

        if start_date:
            result["time"] = build_dv_date_time(start_date)

        return result

    def _export_allergy(self, fact: Any) -> dict[str, Any]:
        """Export an observation/allergy fact as EVALUATION.adverse_reaction_risk.v1."""
        concept_name = self._get_attr(fact, "concept_name", "Unknown substance")

        items = [
            build_element(
                "Substance",
                build_dv_coded_text(concept_name),
            ),
        ]

        return {
            "_type": "EVALUATION",
            "archetype_node_id": DOMAIN_ARCHETYPE_MAP["observation"],
            "name": build_dv_text("Adverse reaction risk"),
            "data": {
                "_type": "ITEM_TREE",
                "items": items,
            },
        }

    def _export_generic(self, fact: Any) -> dict[str, Any]:
        """Export a fact with unknown domain as a generic EVALUATION."""
        concept_name = self._get_attr(fact, "concept_name", "Unknown")
        return {
            "_type": "EVALUATION",
            "archetype_node_id": "openEHR-EHR-EVALUATION.clinical_synopsis.v1",
            "name": build_dv_text("Clinical Synopsis"),
            "data": {
                "_type": "ITEM_TREE",
                "items": [
                    build_element("Synopsis", build_dv_text(concept_name)),
                ],
            },
        }
