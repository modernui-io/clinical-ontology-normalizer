"""OpenEHR Import Service - Import COMPOSITION data into ClinicalFact + KG."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Self
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pipeline_version import get_current_pipeline_version
from app.models.clinical_fact import ClinicalFact
from app.models.data_lineage import SourceType
from app.models.knowledge_graph import KGEdge, KGNode
from app.schemas.base import Assertion, Domain, Experiencer, Temporality
from app.schemas.knowledge_graph import EdgeType, NodeType
from app.services.lineage_service import record_lineage

logger = logging.getLogger(__name__)

# Archetype -> (domain, node_type, edge_type)
ARCHETYPE_DOMAIN_MAP: dict[str, tuple[Domain, NodeType, EdgeType]] = {
    "EVALUATION.problem_diagnosis.v1": (
        Domain.CONDITION,
        NodeType.CONDITION,
        EdgeType.HAS_CONDITION,
    ),
    "INSTRUCTION.medication_order.v3": (
        Domain.DRUG,
        NodeType.DRUG,
        EdgeType.TAKES_DRUG,
    ),
    "OBSERVATION.laboratory_test_result.v1": (
        Domain.MEASUREMENT,
        NodeType.MEASUREMENT,
        EdgeType.HAS_MEASUREMENT,
    ),
    "OBSERVATION.blood_pressure.v2": (
        Domain.MEASUREMENT,
        NodeType.MEASUREMENT,
        EdgeType.HAS_MEASUREMENT,
    ),
    "OBSERVATION.body_temperature.v2": (
        Domain.MEASUREMENT,
        NodeType.MEASUREMENT,
        EdgeType.HAS_MEASUREMENT,
    ),
    "OBSERVATION.body_weight.v2": (
        Domain.MEASUREMENT,
        NodeType.MEASUREMENT,
        EdgeType.HAS_MEASUREMENT,
    ),
    "OBSERVATION.height.v2": (
        Domain.MEASUREMENT,
        NodeType.MEASUREMENT,
        EdgeType.HAS_MEASUREMENT,
    ),
    "OBSERVATION.pulse.v1": (
        Domain.MEASUREMENT,
        NodeType.MEASUREMENT,
        EdgeType.HAS_MEASUREMENT,
    ),
    "OBSERVATION.pulse_oximetry.v1": (
        Domain.MEASUREMENT,
        NodeType.MEASUREMENT,
        EdgeType.HAS_MEASUREMENT,
    ),
    "ACTION.procedure.v1": (
        Domain.PROCEDURE,
        NodeType.PROCEDURE,
        EdgeType.HAS_PROCEDURE,
    ),
    "EVALUATION.adverse_reaction_risk.v1": (
        Domain.OBSERVATION,
        NodeType.OBSERVATION,
        EdgeType.HAS_OBSERVATION,
    ),
}


def _get_archetype_key(archetype_node_id: str) -> str | None:
    """Extract archetype key from full archetype_node_id.

    e.g., openEHR-EHR-EVALUATION.problem_diagnosis.v1 -> EVALUATION.problem_diagnosis.v1
    """
    parts = archetype_node_id.split("-", 2)
    if len(parts) == 3:
        return parts[2]
    return archetype_node_id


def _parse_dv_coded_text(
    dv: dict[str, Any] | None,
) -> tuple[str | None, str | None, str | None]:
    """Parse DV_CODED_TEXT -> (code, system, display)."""
    if not dv:
        return None, None, None
    display = dv.get("value")
    defining_code = dv.get("defining_code", {})
    code = defining_code.get("code_string")
    terminology = defining_code.get("terminology_id", {}).get("value")
    return code, terminology, display


def _parse_dv_quantity(dv: dict[str, Any] | None) -> tuple[float | None, str | None]:
    """Parse DV_QUANTITY -> (magnitude, units)."""
    if not dv:
        return None, None
    return dv.get("magnitude"), dv.get("units")


def _parse_dv_date_time(dv: dict[str, Any] | None) -> datetime | None:
    """Parse DV_DATE_TIME -> datetime."""
    if not dv:
        return None
    value = dv.get("value")
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _find_element_by_name(
    items: list[dict[str, Any]], name: str
) -> dict[str, Any] | None:
    """Find an ELEMENT in items list by its name value."""
    for item in items:
        item_name = item.get("name", {}).get("value", "")
        if item_name.lower() == name.lower():
            return item
    return None


class OpenEHRImportService:
    """Service for importing OpenEHR COMPOSITION data into ClinicalFacts and KG."""

    def __init__(self) -> None:
        self._pipeline_version = get_current_pipeline_version().version_string

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: type | None, exc_val: Exception | None, exc_tb: Any) -> None:
        pass

    async def _record_openehr_lineage(
        self,
        session: AsyncSession,
        fact: ClinicalFact,
        archetype_id: str,
        entry_data: dict[str, Any],
    ) -> None:
        """Record lineage for a ClinicalFact created from an OpenEHR entry."""
        try:
            await record_lineage(
                session=session,
                fact_id=fact.id,
                source_type=SourceType.OPENEHR_IMPORT,
                source_resource_type=archetype_id,
                source_resource_id=entry_data.get("archetype_node_id"),
                extraction_method="openehr_composition_mapping",
                extraction_confidence=1.0,
                transformation_chain=[
                    {
                        "step": "openehr_composition_import",
                        "archetype": archetype_id,
                        "pipeline_version": self._pipeline_version,
                    }
                ],
            )
        except Exception as e:
            logger.warning(
                f"Failed to record lineage for fact {fact.id} from "
                f"archetype {archetype_id}: {e}"
            )

    async def import_composition(
        self,
        session: AsyncSession,
        composition: dict[str, Any],
        patient_id: str,
    ) -> dict[str, Any]:
        """Import an OpenEHR COMPOSITION into ClinicalFacts and KG.

        Args:
            session: Database session.
            composition: OpenEHR COMPOSITION dict.
            patient_id: Internal patient ID.

        Returns:
            Import stats dict.
        """
        if composition.get("_type") != "COMPOSITION":
            return {"success": False, "error": "Not a COMPOSITION"}

        content = composition.get("content", [])
        if not content:
            return {"success": False, "error": "Empty composition"}

        # Extract demographics from composition context if available
        composer_name = composition.get("composer", {}).get("name", "Unknown")

        # Create patient KG node
        patient_node = KGNode(
            patient_id=patient_id,
            node_type=NodeType.PATIENT,
            label=f"Patient {patient_id}",
            properties={
                "source": "openehr",
                "composer": composer_name,
                "territory": composition.get("territory", {}).get("code_string"),
                "language": composition.get("language", {}).get("code_string"),
            },
        )
        session.add(patient_node)
        await session.flush()

        stats: dict[str, Any] = {
            "success": True,
            "patient_id": patient_id,
            "conditions": 0,
            "medications": 0,
            "measurements": 0,
            "procedures": 0,
            "allergies": 0,
            "nodes": 1,  # patient node
            "edges": 0,
            "skipped": 0,
        }

        for entry in content:
            node_id = entry.get("archetype_node_id", "")
            archetype_key = _get_archetype_key(node_id)

            if not archetype_key or archetype_key not in ARCHETYPE_DOMAIN_MAP:
                stats["skipped"] += 1
                continue

            domain, node_type, edge_type = ARCHETYPE_DOMAIN_MAP[archetype_key]

            try:
                if domain == Domain.CONDITION:
                    count = await self._import_condition(
                        session, patient_id, patient_node.id,
                        entry, archetype_key, node_type, edge_type,
                    )
                    stats["conditions"] += count
                    stats["nodes"] += count
                    stats["edges"] += count
                elif domain == Domain.DRUG:
                    count = await self._import_medication(
                        session, patient_id, patient_node.id,
                        entry, archetype_key, node_type, edge_type,
                    )
                    stats["medications"] += count
                    stats["nodes"] += count
                    stats["edges"] += count
                elif domain == Domain.MEASUREMENT:
                    count = await self._import_measurement(
                        session, patient_id, patient_node.id,
                        entry, archetype_key, node_type, edge_type,
                    )
                    stats["measurements"] += count
                    stats["nodes"] += count
                    stats["edges"] += count
                elif domain == Domain.PROCEDURE:
                    count = await self._import_procedure(
                        session, patient_id, patient_node.id,
                        entry, archetype_key, node_type, edge_type,
                    )
                    stats["procedures"] += count
                    stats["nodes"] += count
                    stats["edges"] += count
                elif domain == Domain.OBSERVATION:
                    count = await self._import_allergy(
                        session, patient_id, patient_node.id,
                        entry, archetype_key, node_type, edge_type,
                    )
                    stats["allergies"] += count
                    stats["nodes"] += count
                    stats["edges"] += count
            except Exception as e:
                logger.warning(f"Error importing {archetype_key} entry: {e}")
                stats["skipped"] += 1

        return stats

    async def _create_fact_and_node(
        self,
        session: AsyncSession,
        patient_id: str,
        patient_node_id: str | UUID,
        domain: Domain,
        concept_name: str,
        node_type: NodeType,
        edge_type: EdgeType,
        archetype_key: str,
        entry: dict[str, Any],
        *,
        assertion: Assertion = Assertion.PRESENT,
        temporality: Temporality = Temporality.CURRENT,
        omop_concept_id: int = 0,
        properties: dict[str, Any] | None = None,
        start_date: datetime | None = None,
    ) -> int:
        """Create a ClinicalFact, KGNode, and KGEdge for an entry.

        Returns:
            1 if created, 0 if skipped.
        """
        fact = ClinicalFact(
            patient_id=patient_id,
            domain=domain,
            omop_concept_id=omop_concept_id,
            concept_name=concept_name,
            assertion=assertion,
            temporality=temporality,
            experiencer=Experiencer.PATIENT,
            confidence=1.0,
            start_date=start_date,
            pipeline_version=self._pipeline_version,
        )
        session.add(fact)
        await session.flush()

        await self._record_openehr_lineage(session, fact, archetype_key, entry)

        node = KGNode(
            patient_id=patient_id,
            node_type=node_type,
            omop_concept_id=omop_concept_id if omop_concept_id else None,
            label=concept_name,
            properties=properties or {"archetype": archetype_key},
        )
        session.add(node)
        await session.flush()

        edge = KGEdge(
            patient_id=patient_id,
            source_node_id=patient_node_id,
            target_node_id=node.id,
            edge_type=edge_type,
            fact_id=fact.id,
            properties={"assertion": assertion.value},
        )
        session.add(edge)

        return 1

    async def _import_condition(
        self,
        session: AsyncSession,
        patient_id: str,
        patient_node_id: str | UUID,
        entry: dict[str, Any],
        archetype_key: str,
        node_type: NodeType,
        edge_type: EdgeType,
    ) -> int:
        """Import a problem_diagnosis entry."""
        items = entry.get("data", {}).get("items", [])
        name_elem = _find_element_by_name(items, "Problem/Diagnosis name")
        if not name_elem:
            return 0

        code, system, display = _parse_dv_coded_text(name_elem.get("value"))
        if not display:
            return 0

        onset_elem = _find_element_by_name(items, "Date/time of onset")
        onset = _parse_dv_date_time(onset_elem.get("value") if onset_elem else None)

        return await self._create_fact_and_node(
            session, patient_id, patient_node_id,
            Domain.CONDITION, display, node_type, edge_type,
            archetype_key, entry,
            omop_concept_id=int(code) if code and code.isdigit() else 0,
            start_date=onset,
            temporality=Temporality.PAST if onset else Temporality.CURRENT,
            properties={
                "archetype": archetype_key,
                "code": code,
                "code_system": system,
                "onset": onset.isoformat() if onset else None,
            },
        )

    async def _import_medication(
        self,
        session: AsyncSession,
        patient_id: str,
        patient_node_id: str | UUID,
        entry: dict[str, Any],
        archetype_key: str,
        node_type: NodeType,
        edge_type: EdgeType,
    ) -> int:
        """Import a medication_order entry."""
        activities = entry.get("activities", [])
        if not activities:
            return 0

        items = activities[0].get("description", {}).get("items", [])
        med_elem = _find_element_by_name(items, "Medication item")
        if not med_elem:
            return 0

        code, system, display = _parse_dv_coded_text(med_elem.get("value"))
        if not display:
            return 0

        dose_elem = _find_element_by_name(items, "Dose amount")
        dose_value, dose_unit = _parse_dv_quantity(
            dose_elem.get("value") if dose_elem else None
        )

        return await self._create_fact_and_node(
            session, patient_id, patient_node_id,
            Domain.DRUG, display, node_type, edge_type,
            archetype_key, entry,
            omop_concept_id=int(code) if code and code.isdigit() else 0,
            properties={
                "archetype": archetype_key,
                "code": code,
                "code_system": system,
                "dose_value": dose_value,
                "dose_unit": dose_unit,
            },
        )

    async def _import_measurement(
        self,
        session: AsyncSession,
        patient_id: str,
        patient_node_id: str | UUID,
        entry: dict[str, Any],
        archetype_key: str,
        node_type: NodeType,
        edge_type: EdgeType,
    ) -> int:
        """Import an OBSERVATION measurement entry (may produce multiple facts)."""
        data = entry.get("data", {})
        events = data.get("events", [])
        if not events:
            return 0

        event_data = events[0].get("data", {})
        items = event_data.get("items", [])
        count = 0

        if "blood_pressure" in archetype_key:
            # Blood pressure produces two measurements
            for name in ("Systolic", "Diastolic"):
                elem = _find_element_by_name(items, name)
                if elem:
                    mag, unit = _parse_dv_quantity(elem.get("value"))
                    label = f"Blood Pressure - {name}"
                    count += await self._create_fact_and_node(
                        session, patient_id, patient_node_id,
                        Domain.MEASUREMENT, label, node_type, edge_type,
                        archetype_key, entry,
                        properties={
                            "archetype": archetype_key,
                            "component": name.lower(),
                            "value": mag,
                            "unit": unit,
                        },
                    )
        else:
            # Single-value observation
            for item in items:
                value_node = item.get("value", {})
                if value_node.get("_type") == "DV_QUANTITY":
                    mag, unit = _parse_dv_quantity(value_node)
                    label = item.get("name", {}).get("value", archetype_key)
                    count += await self._create_fact_and_node(
                        session, patient_id, patient_node_id,
                        Domain.MEASUREMENT, label, node_type, edge_type,
                        archetype_key, entry,
                        properties={
                            "archetype": archetype_key,
                            "value": mag,
                            "unit": unit,
                        },
                    )
                    break  # Single primary value for simple observations

        return count

    async def _import_procedure(
        self,
        session: AsyncSession,
        patient_id: str,
        patient_node_id: str | UUID,
        entry: dict[str, Any],
        archetype_key: str,
        node_type: NodeType,
        edge_type: EdgeType,
    ) -> int:
        """Import a procedure entry."""
        items = entry.get("description", {}).get("items", [])
        name_elem = _find_element_by_name(items, "Procedure name")
        if not name_elem:
            return 0

        code, system, display = _parse_dv_coded_text(name_elem.get("value"))
        if not display:
            return 0

        time_data = entry.get("time", {})
        performed = _parse_dv_date_time(time_data)

        return await self._create_fact_and_node(
            session, patient_id, patient_node_id,
            Domain.PROCEDURE, display, node_type, edge_type,
            archetype_key, entry,
            omop_concept_id=int(code) if code and code.isdigit() else 0,
            start_date=performed,
            properties={
                "archetype": archetype_key,
                "code": code,
                "code_system": system,
                "performed": performed.isoformat() if performed else None,
            },
        )

    async def _import_allergy(
        self,
        session: AsyncSession,
        patient_id: str,
        patient_node_id: str | UUID,
        entry: dict[str, Any],
        archetype_key: str,
        node_type: NodeType,
        edge_type: EdgeType,
    ) -> int:
        """Import an adverse_reaction_risk entry."""
        items = entry.get("data", {}).get("items", [])
        substance_elem = _find_element_by_name(items, "Substance")
        if not substance_elem:
            return 0

        code, system, display = _parse_dv_coded_text(substance_elem.get("value"))
        if not display:
            return 0

        # Find reaction manifestation
        reaction_text = None
        for item in items:
            if item.get("_type") == "CLUSTER":
                for sub in item.get("items", []):
                    if "Manifestation" in sub.get("name", {}).get("value", ""):
                        _, _, reaction_text = _parse_dv_coded_text(sub.get("value"))
                        break

        return await self._create_fact_and_node(
            session, patient_id, patient_node_id,
            Domain.OBSERVATION, display, node_type, edge_type,
            archetype_key, entry,
            properties={
                "archetype": archetype_key,
                "code": code,
                "code_system": system,
                "category": "allergy",
                "reaction": reaction_text,
            },
        )
