"""FHIR Import Service - Import patient data from FHIR into knowledge graph."""

from __future__ import annotations

import base64
import logging
from datetime import datetime
from typing import Any, Self
from uuid import UUID, uuid4

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinical_fact import ClinicalFact, FactEvidence
from app.models.document import Document as DocumentModel
from app.models.knowledge_graph import KGEdge, KGNode
from app.schemas.base import Assertion, Domain, Experiencer, JobStatus, Temporality
from app.schemas.clinical_fact import EvidenceType
from app.schemas.knowledge_graph import EdgeType, NodeType

logger = logging.getLogger(__name__)

# SNOMED to OMOP domain mapping
SNOMED_DOMAIN_MAP = {
    # Conditions
    "44054006": Domain.CONDITION,  # Type 2 diabetes
    "38341003": Domain.CONDITION,  # Hypertension
    # Procedures
    "252779009": Domain.PROCEDURE,  # Cardiac SPECT
    "314972000": Domain.PROCEDURE,  # Fundus exam
    "29303009": Domain.PROCEDURE,  # ECG
}


class FHIRImportService:
    """Service for importing FHIR patient data into the knowledge graph."""

    def __init__(self, fhir_base_url: str = "http://localhost:8090/fhir"):
        """Initialize the FHIR import service.

        Args:
            fhir_base_url: Base URL of the FHIR server
        """
        self.fhir_base_url = fhir_base_url
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    # VP-Lifecycle-1: Async context manager support for proper resource cleanup
    async def __aenter__(self) -> Self:
        """Enter async context manager."""
        return self

    async def __aexit__(self, exc_type: type | None, exc_val: Exception | None, exc_tb: Any) -> None:
        """Exit async context manager, ensuring client is closed."""
        await self.close()

    async def fetch_patient(self, patient_id: str) -> dict[str, Any] | None:
        """Fetch a patient resource from FHIR.

        Args:
            patient_id: FHIR patient ID

        Returns:
            Patient resource dict or None if not found
        """
        try:
            response = await self.client.get(f"{self.fhir_base_url}/Patient/{patient_id}")
            if response.status_code == 200:
                return response.json()
            logger.warning(f"Patient {patient_id} not found: {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Error fetching patient {patient_id}: {e}")
            return None

    async def fetch_patient_resources(
        self, patient_id: str, resource_type: str
    ) -> list[dict[str, Any]]:
        """Fetch all resources of a type for a patient.

        Args:
            patient_id: FHIR patient ID
            resource_type: FHIR resource type (e.g., Condition, MedicationRequest)

        Returns:
            List of resource dicts
        """
        try:
            # Different resources use different search params
            if resource_type == "AllergyIntolerance":
                param = "patient"
            else:
                param = "subject"

            response = await self.client.get(
                f"{self.fhir_base_url}/{resource_type}",
                params={param: f"Patient/{patient_id}"},
            )
            if response.status_code == 200:
                bundle = response.json()
                entries = bundle.get("entry", [])
                return [e["resource"] for e in entries]
            logger.warning(f"Error fetching {resource_type} for patient {patient_id}")
            return []
        except Exception as e:
            logger.error(f"Error fetching {resource_type}: {e}")
            return []

    def _parse_fhir_datetime(self, dt_str: str | None) -> datetime | None:
        """Parse a FHIR datetime string.

        Args:
            dt_str: FHIR datetime string (ISO 8601)

        Returns:
            Python datetime or None
        """
        if not dt_str:
            return None
        try:
            # Handle various FHIR date formats
            if "T" in dt_str:
                # Full datetime
                if dt_str.endswith("Z"):
                    dt_str = dt_str[:-1] + "+00:00"
                return datetime.fromisoformat(dt_str)
            # Date only
            return datetime.fromisoformat(dt_str + "T00:00:00+00:00")
        except ValueError:
            logger.warning(f"Could not parse datetime: {dt_str}")
            return None

    def _get_code_from_codeable_concept(
        self, codeable_concept: dict[str, Any]
    ) -> tuple[str | None, str | None, str | None]:
        """Extract code, display, and system from a CodeableConcept.

        Args:
            codeable_concept: FHIR CodeableConcept

        Returns:
            Tuple of (code, display, system)
        """
        codings = codeable_concept.get("coding", [])
        if codings:
            coding = codings[0]
            return (
                coding.get("code"),
                coding.get("display") or codeable_concept.get("text"),
                coding.get("system"),
            )
        return (None, codeable_concept.get("text"), None)

    def _map_snomed_to_domain(self, code: str | None, system: str | None) -> Domain:
        """Map a SNOMED code to an OMOP domain.

        Args:
            code: SNOMED code
            system: Code system URI

        Returns:
            Domain enum value
        """
        if code and code in SNOMED_DOMAIN_MAP:
            return SNOMED_DOMAIN_MAP[code]
        # Default based on resource type will be set by caller
        return Domain.CONDITION

    async def import_bundle(
        self,
        session: AsyncSession,
        bundle: dict[str, Any],
        internal_patient_id: str | None = None,
    ) -> dict[str, Any]:
        """Import a FHIR R4 Bundle directly (no FHIR server needed).

        Extracts Patient, Condition, MedicationRequest, AllergyIntolerance,
        Observation, and Procedure resources from the Bundle entries and
        creates ClinicalFacts and KG nodes/edges.

        Args:
            session: Database session
            bundle: FHIR R4 Bundle dict
            internal_patient_id: Optional override for patient ID

        Returns:
            Import summary with counts
        """
        resource_type = bundle.get("resourceType")
        if resource_type != "Bundle":
            return {"success": False, "error": f"Expected Bundle, got {resource_type}"}

        entries = bundle.get("entry", [])
        if not entries:
            return {"success": False, "error": "Bundle contains no entries"}

        # Group resources by type
        resources_by_type: dict[str, list[dict[str, Any]]] = {}
        patient_resource: dict[str, Any] | None = None

        for entry in entries:
            resource = entry.get("resource")
            if not resource:
                continue
            rtype = resource.get("resourceType")
            if not rtype:
                continue
            if rtype == "Patient":
                patient_resource = resource
            resources_by_type.setdefault(rtype, []).append(resource)

        if not patient_resource:
            return {"success": False, "error": "Bundle contains no Patient resource"}

        fhir_patient_id = patient_resource.get("id", "unknown")
        patient_id = internal_patient_id or f"fhir-{fhir_patient_id}"
        logger.info(
            f"Importing FHIR Bundle for patient {fhir_patient_id} as {patient_id} "
            f"({len(entries)} entries, {len(resources_by_type)} resource types)"
        )

        # Clear existing data for this patient
        from sqlalchemy import delete

        await session.execute(delete(KGEdge).where(KGEdge.patient_id == patient_id))
        await session.execute(delete(KGNode).where(KGNode.patient_id == patient_id))
        await session.execute(
            delete(ClinicalFact).where(ClinicalFact.patient_id == patient_id)
        )
        await session.flush()

        # Create patient node
        patient_name = self._extract_patient_name(patient_resource)
        patient_node = KGNode(
            patient_id=patient_id,
            node_type=NodeType.PATIENT,
            label=patient_name,
            properties={
                "fhir_id": fhir_patient_id,
                "gender": patient_resource.get("gender"),
                "birth_date": patient_resource.get("birthDate"),
                "mrn": self._extract_identifier(patient_resource),
            },
        )
        session.add(patient_node)
        await session.flush()

        stats = {
            "patient_id": patient_id,
            "patient_name": patient_name,
            "conditions": 0,
            "medications": 0,
            "allergies": 0,
            "observations": 0,
            "procedures": 0,
            "encounters": 0,
            "immunizations": 0,
            "clinical_notes": 0,
            "diagnostic_reports": 0,
            "nodes": 1,
            "edges": 0,
            "skipped_resource_types": [],
        }

        # Dispatch each resource type to its handler
        handler_map = {
            "Condition": ("conditions", self._import_condition),
            "MedicationRequest": ("medications", self._import_medication),
            "MedicationStatement": ("medications", self._import_medication_statement),
            "AllergyIntolerance": ("allergies", self._import_allergy),
            "Observation": ("observations", self._import_observation),
            "Procedure": ("procedures", self._import_procedure),
            "Encounter": ("encounters", self._import_encounter),
            "Immunization": ("immunizations", self._import_immunization),
            "DocumentReference": ("clinical_notes", self._import_document_reference),
            "DiagnosticReport": ("diagnostic_reports", self._import_diagnostic_report),
        }

        for rtype, resources in resources_by_type.items():
            if rtype == "Patient":
                continue
            if rtype not in handler_map:
                if rtype not in stats["skipped_resource_types"]:
                    stats["skipped_resource_types"].append(rtype)
                continue

            stat_key, handler = handler_map[rtype]
            for resource in resources:
                try:
                    fact, node, edge = await handler(
                        session, patient_id, patient_node.id, resource
                    )
                    # Count if either a fact or node was created
                    if fact or node:
                        stats[stat_key] += 1
                    if node:
                        stats["nodes"] += 1
                    if edge:
                        stats["edges"] += 1
                except Exception as e:
                    logger.warning(
                        f"Failed to import {rtype} resource "
                        f"{resource.get('id', '?')}: {e}"
                    )

        await session.commit()
        logger.info(f"Bundle import complete for patient {patient_id}: {stats}")
        return {"success": True, **stats}

    async def _import_medication_statement(
        self,
        session: AsyncSession,
        patient_id: str,
        patient_node_id: UUID,
        med_statement: dict[str, Any],
    ) -> tuple[ClinicalFact | None, KGNode | None, KGEdge | None]:
        """Import a FHIR MedicationStatement (same structure as MedicationRequest)."""
        # MedicationStatement uses medicationCodeableConcept like MedicationRequest
        med_concept = med_statement.get("medicationCodeableConcept", {})
        code, display, system = self._get_code_from_codeable_concept(med_concept)

        if not display:
            return None, None, None

        status = med_statement.get("status", "active")
        assertion = Assertion.PRESENT if status == "active" else Assertion.ABSENT
        effective = self._parse_fhir_datetime(
            med_statement.get("effectiveDateTime")
            or med_statement.get("effectivePeriod", {}).get("start")
            or med_statement.get("dateAsserted")
        )

        fact = ClinicalFact(
            patient_id=patient_id,
            domain=Domain.DRUG,
            omop_concept_id=int(code) if code and code.isdigit() else 0,
            concept_name=display,
            assertion=assertion,
            temporality=Temporality.CURRENT,
            experiencer=Experiencer.PATIENT,
            confidence=1.0,
            start_date=effective,
        )
        session.add(fact)
        await session.flush()

        node = KGNode(
            patient_id=patient_id,
            node_type=NodeType.DRUG,
            omop_concept_id=int(code) if code and code.isdigit() else None,
            label=display,
            properties={
                "fhir_id": med_statement.get("id"),
                "rxnorm_code": code,
                "status": status,
            },
        )
        session.add(node)
        await session.flush()

        edge = KGEdge(
            patient_id=patient_id,
            source_node_id=patient_node_id,
            target_node_id=node.id,
            edge_type=EdgeType.TAKES_DRUG,
            fact_id=fact.id,
            properties={"status": status},
        )
        session.add(edge)

        return fact, node, edge

    async def import_patient(
        self,
        session: AsyncSession,
        fhir_patient_id: str,
        internal_patient_id: str | None = None,
    ) -> dict[str, Any]:
        """Import a complete patient record from FHIR.

        Args:
            session: Database session
            fhir_patient_id: FHIR patient ID
            internal_patient_id: Optional internal patient ID (defaults to fhir-{id})

        Returns:
            Import summary with counts
        """
        patient_id = internal_patient_id or f"fhir-{fhir_patient_id}"
        logger.info(f"Importing FHIR patient {fhir_patient_id} as {patient_id}")

        # Fetch patient demographics
        patient_resource = await self.fetch_patient(fhir_patient_id)
        if not patient_resource:
            return {"success": False, "error": f"Patient {fhir_patient_id} not found"}

        # Clear existing data for this patient
        from sqlalchemy import delete

        await session.execute(delete(KGEdge).where(KGEdge.patient_id == patient_id))
        await session.execute(delete(KGNode).where(KGNode.patient_id == patient_id))
        await session.execute(
            delete(ClinicalFact).where(ClinicalFact.patient_id == patient_id)
        )
        await session.flush()

        # Create patient node
        patient_name = self._extract_patient_name(patient_resource)
        patient_node = KGNode(
            patient_id=patient_id,
            node_type=NodeType.PATIENT,
            label=patient_name,
            properties={
                "fhir_id": fhir_patient_id,
                "gender": patient_resource.get("gender"),
                "birth_date": patient_resource.get("birthDate"),
                "mrn": self._extract_identifier(patient_resource),
            },
        )
        session.add(patient_node)
        await session.flush()

        # Import each resource type
        stats = {
            "patient_id": patient_id,
            "patient_name": patient_name,
            "conditions": 0,
            "medications": 0,
            "allergies": 0,
            "observations": 0,
            "procedures": 0,
            "nodes": 1,  # Patient node
            "edges": 0,
        }

        # Import conditions
        conditions = await self.fetch_patient_resources(fhir_patient_id, "Condition")
        for condition in conditions:
            fact, node, edge = await self._import_condition(
                session, patient_id, patient_node.id, condition
            )
            if fact:
                stats["conditions"] += 1
                stats["nodes"] += 1
                stats["edges"] += 1

        # Import medications
        medications = await self.fetch_patient_resources(
            fhir_patient_id, "MedicationRequest"
        )
        for med in medications:
            fact, node, edge = await self._import_medication(
                session, patient_id, patient_node.id, med
            )
            if fact:
                stats["medications"] += 1
                stats["nodes"] += 1
                stats["edges"] += 1

        # Import allergies
        allergies = await self.fetch_patient_resources(
            fhir_patient_id, "AllergyIntolerance"
        )
        for allergy in allergies:
            fact, node, edge = await self._import_allergy(
                session, patient_id, patient_node.id, allergy
            )
            if fact:
                stats["allergies"] += 1
                stats["nodes"] += 1
                stats["edges"] += 1

        # Import observations (labs, vitals)
        observations = await self.fetch_patient_resources(fhir_patient_id, "Observation")
        for obs in observations:
            fact, node, edge = await self._import_observation(
                session, patient_id, patient_node.id, obs
            )
            if fact:
                stats["observations"] += 1
                stats["nodes"] += 1
                stats["edges"] += 1

        # Import procedures
        procedures = await self.fetch_patient_resources(fhir_patient_id, "Procedure")
        for proc in procedures:
            fact, node, edge = await self._import_procedure(
                session, patient_id, patient_node.id, proc
            )
            if fact:
                stats["procedures"] += 1
                stats["nodes"] += 1
                stats["edges"] += 1

        await session.commit()
        logger.info(f"Import complete for patient {patient_id}: {stats}")
        return {"success": True, **stats}

    def _extract_patient_name(self, patient: dict[str, Any]) -> str:
        """Extract patient name from FHIR Patient resource."""
        names = patient.get("name", [])
        if names:
            name = names[0]
            given = " ".join(name.get("given", []))
            family = name.get("family", "")
            return f"{given} {family}".strip() or "Unknown"
        return "Unknown"

    def _extract_identifier(self, patient: dict[str, Any]) -> str | None:
        """Extract MRN or first identifier from FHIR Patient resource."""
        identifiers = patient.get("identifier", [])
        for ident in identifiers:
            if ident.get("system", "").endswith("/mrn"):
                return ident.get("value")
        if identifiers:
            return identifiers[0].get("value")
        return None

    async def _import_condition(
        self,
        session: AsyncSession,
        patient_id: str,
        patient_node_id: UUID,
        condition: dict[str, Any],
    ) -> tuple[ClinicalFact | None, KGNode | None, KGEdge | None]:
        """Import a FHIR Condition as a clinical fact and KG node."""
        code_concept = condition.get("code", {})
        code, display, system = self._get_code_from_codeable_concept(code_concept)

        if not display:
            return None, None, None

        # Determine assertion from clinicalStatus
        clinical_status = condition.get("clinicalStatus", {})
        status_code = None
        for coding in clinical_status.get("coding", []):
            status_code = coding.get("code")
            break

        assertion = Assertion.PRESENT
        if status_code in ("inactive", "remission", "resolved"):
            assertion = Assertion.ABSENT

        # Parse onset date
        onset = self._parse_fhir_datetime(condition.get("onsetDateTime"))

        # Create clinical fact
        fact = ClinicalFact(
            patient_id=patient_id,
            domain=Domain.CONDITION,
            omop_concept_id=int(code) if code and code.isdigit() else 0,
            concept_name=display,
            assertion=assertion,
            temporality=Temporality.PAST if onset else Temporality.CURRENT,
            experiencer=Experiencer.PATIENT,
            confidence=1.0,
            start_date=onset,
        )
        session.add(fact)
        await session.flush()

        # Create KG node
        node = KGNode(
            patient_id=patient_id,
            node_type=NodeType.CONDITION,
            omop_concept_id=int(code) if code and code.isdigit() else None,
            label=display,
            properties={
                "fhir_id": condition.get("id"),
                "snomed_code": code,
                "assertion": assertion.value,
                "onset": onset.isoformat() if onset else None,
            },
        )
        session.add(node)
        await session.flush()

        # Create edge from patient to condition
        edge = KGEdge(
            patient_id=patient_id,
            source_node_id=patient_node_id,
            target_node_id=node.id,
            edge_type=EdgeType.HAS_CONDITION,
            fact_id=fact.id,
            properties={"assertion": assertion.value},
        )
        session.add(edge)

        return fact, node, edge

    async def _import_medication(
        self,
        session: AsyncSession,
        patient_id: str,
        patient_node_id: UUID,
        med_request: dict[str, Any],
    ) -> tuple[ClinicalFact | None, KGNode | None, KGEdge | None]:
        """Import a FHIR MedicationRequest as a clinical fact and KG node."""
        med_concept = med_request.get("medicationCodeableConcept", {})
        code, display, system = self._get_code_from_codeable_concept(med_concept)

        if not display:
            return None, None, None

        # Check status
        status = med_request.get("status", "active")
        assertion = Assertion.PRESENT if status == "active" else Assertion.ABSENT

        # Get authored date
        authored = self._parse_fhir_datetime(med_request.get("authoredOn"))

        # Extract dosage info
        dosage_text = None
        dosage_instructions = med_request.get("dosageInstruction", [])
        if dosage_instructions:
            dosage_text = dosage_instructions[0].get("text")

        # Create clinical fact
        fact = ClinicalFact(
            patient_id=patient_id,
            domain=Domain.DRUG,
            omop_concept_id=int(code) if code and code.isdigit() else 0,
            concept_name=display,
            assertion=assertion,
            temporality=Temporality.CURRENT,
            experiencer=Experiencer.PATIENT,
            confidence=1.0,
            start_date=authored,
        )
        session.add(fact)
        await session.flush()

        # Create KG node
        node = KGNode(
            patient_id=patient_id,
            node_type=NodeType.DRUG,
            omop_concept_id=int(code) if code and code.isdigit() else None,
            label=display,
            properties={
                "fhir_id": med_request.get("id"),
                "rxnorm_code": code,
                "status": status,
                "dosage": dosage_text,
            },
        )
        session.add(node)
        await session.flush()

        # Create edge from patient to drug
        edge = KGEdge(
            patient_id=patient_id,
            source_node_id=patient_node_id,
            target_node_id=node.id,
            edge_type=EdgeType.TAKES_DRUG,
            fact_id=fact.id,
            properties={"status": status},
        )
        session.add(edge)

        return fact, node, edge

    async def _import_allergy(
        self,
        session: AsyncSession,
        patient_id: str,
        patient_node_id: UUID,
        allergy: dict[str, Any],
    ) -> tuple[ClinicalFact | None, KGNode | None, KGEdge | None]:
        """Import a FHIR AllergyIntolerance as a clinical fact and KG node."""
        code_concept = allergy.get("code", {})
        code, display, system = self._get_code_from_codeable_concept(code_concept)

        if not display:
            return None, None, None

        # Check clinical status
        clinical_status = allergy.get("clinicalStatus", {})
        status_code = None
        for coding in clinical_status.get("coding", []):
            status_code = coding.get("code")
            break

        assertion = Assertion.PRESENT if status_code == "active" else Assertion.ABSENT

        # Get criticality and category
        criticality = allergy.get("criticality", "unknown")
        categories = allergy.get("category", [])
        category = categories[0] if categories else "unknown"

        # Get recorded date
        recorded = self._parse_fhir_datetime(allergy.get("recordedDate"))

        # Extract reaction info
        reactions = allergy.get("reaction", [])
        reaction_text = None
        if reactions:
            manifestations = reactions[0].get("manifestation", [])
            if manifestations:
                _, reaction_text, _ = self._get_code_from_codeable_concept(
                    manifestations[0]
                )

        # Create clinical fact (allergies go to Observation domain)
        fact = ClinicalFact(
            patient_id=patient_id,
            domain=Domain.OBSERVATION,
            omop_concept_id=int(code) if code and code.isdigit() else 0,
            concept_name=f"Allergy to {display}",
            assertion=assertion,
            temporality=Temporality.CURRENT,
            experiencer=Experiencer.PATIENT,
            confidence=1.0,
            start_date=recorded,
        )
        session.add(fact)
        await session.flush()

        # Create KG node
        node = KGNode(
            patient_id=patient_id,
            node_type=NodeType.OBSERVATION,
            omop_concept_id=int(code) if code and code.isdigit() else None,
            label=f"Allergy: {display}",
            properties={
                "fhir_id": allergy.get("id"),
                "allergen_code": code,
                "category": category,
                "criticality": criticality,
                "reaction": reaction_text,
            },
        )
        session.add(node)
        await session.flush()

        # Create edge from patient to allergy
        edge = KGEdge(
            patient_id=patient_id,
            source_node_id=patient_node_id,
            target_node_id=node.id,
            edge_type=EdgeType.HAS_OBSERVATION,
            fact_id=fact.id,
            properties={"criticality": criticality},
        )
        session.add(edge)

        return fact, node, edge

    async def _import_observation(
        self,
        session: AsyncSession,
        patient_id: str,
        patient_node_id: UUID,
        observation: dict[str, Any],
    ) -> tuple[ClinicalFact | None, KGNode | None, KGEdge | None]:
        """Import a FHIR Observation as a clinical fact and KG node."""
        code_concept = observation.get("code", {})
        code, display, system = self._get_code_from_codeable_concept(code_concept)

        if not display:
            return None, None, None

        # Check status
        status = observation.get("status", "final")
        if status not in ("final", "amended", "corrected"):
            return None, None, None  # Skip preliminary/cancelled

        # Get effective date
        effective = self._parse_fhir_datetime(
            observation.get("effectiveDateTime")
            or observation.get("effectivePeriod", {}).get("start")
        )

        # Get value
        value_quantity = observation.get("valueQuantity", {})
        value = value_quantity.get("value")
        unit = value_quantity.get("unit")

        # Determine domain based on category
        categories = observation.get("category", [])
        domain = Domain.OBSERVATION
        node_type = NodeType.OBSERVATION
        for cat in categories:
            for coding in cat.get("coding", []):
                cat_code = coding.get("code")
                if cat_code in ("vital-signs", "laboratory"):
                    domain = Domain.MEASUREMENT
                    node_type = NodeType.MEASUREMENT
                    break

        # Create clinical fact
        fact = ClinicalFact(
            patient_id=patient_id,
            domain=domain,
            omop_concept_id=int(code) if code and code.isdigit() else 0,
            concept_name=display,
            assertion=Assertion.PRESENT,
            temporality=Temporality.CURRENT,
            experiencer=Experiencer.PATIENT,
            confidence=1.0,
            value=str(value) if value is not None else None,
            unit=unit,
            start_date=effective,
        )
        session.add(fact)
        await session.flush()

        # Create KG node
        node = KGNode(
            patient_id=patient_id,
            node_type=node_type,
            omop_concept_id=int(code) if code and code.isdigit() else None,
            label=display,
            properties={
                "fhir_id": observation.get("id"),
                "loinc_code": code if system and "loinc" in system.lower() else None,
                "value": value,
                "unit": unit,
            },
        )
        session.add(node)
        await session.flush()

        # Create edge from patient to observation
        edge_type = (
            EdgeType.HAS_MEASUREMENT
            if domain == Domain.MEASUREMENT
            else EdgeType.HAS_OBSERVATION
        )
        edge = KGEdge(
            patient_id=patient_id,
            source_node_id=patient_node_id,
            target_node_id=node.id,
            edge_type=edge_type,
            fact_id=fact.id,
            properties={"value": value, "unit": unit},
        )
        session.add(edge)

        return fact, node, edge

    async def _import_procedure(
        self,
        session: AsyncSession,
        patient_id: str,
        patient_node_id: UUID,
        procedure: dict[str, Any],
    ) -> tuple[ClinicalFact | None, KGNode | None, KGEdge | None]:
        """Import a FHIR Procedure as a clinical fact and KG node."""
        code_concept = procedure.get("code", {})
        code, display, system = self._get_code_from_codeable_concept(code_concept)

        if not display:
            return None, None, None

        # Check status
        status = procedure.get("status", "completed")
        if status not in ("completed", "in-progress"):
            return None, None, None  # Skip not-done, entered-in-error

        # Get performed date
        performed = self._parse_fhir_datetime(
            procedure.get("performedDateTime")
            or procedure.get("performedPeriod", {}).get("start")
        )

        # Get outcome
        outcome = procedure.get("outcome", {})
        _, outcome_text, _ = self._get_code_from_codeable_concept(outcome)

        # Create clinical fact
        fact = ClinicalFact(
            patient_id=patient_id,
            domain=Domain.PROCEDURE,
            omop_concept_id=int(code) if code and code.isdigit() else 0,
            concept_name=display,
            assertion=Assertion.PRESENT,
            temporality=Temporality.PAST if performed else Temporality.CURRENT,
            experiencer=Experiencer.PATIENT,
            confidence=1.0,
            start_date=performed,
        )
        session.add(fact)
        await session.flush()

        # Create KG node
        node = KGNode(
            patient_id=patient_id,
            node_type=NodeType.PROCEDURE,
            omop_concept_id=int(code) if code and code.isdigit() else None,
            label=display,
            properties={
                "fhir_id": procedure.get("id"),
                "snomed_code": code,
                "status": status,
                "outcome": outcome_text,
            },
        )
        session.add(node)
        await session.flush()

        # Create edge from patient to procedure
        edge = KGEdge(
            patient_id=patient_id,
            source_node_id=patient_node_id,
            target_node_id=node.id,
            edge_type=EdgeType.HAS_PROCEDURE,
            fact_id=fact.id,
            properties={"status": status, "outcome": outcome_text},
        )
        session.add(edge)

        return fact, node, edge

    async def _import_encounter(
        self,
        session: AsyncSession,
        patient_id: str,
        patient_node_id: UUID,
        encounter: dict[str, Any],
    ) -> tuple[ClinicalFact | None, KGNode | None, KGEdge | None]:
        """Import a FHIR Encounter as a clinical fact and KG node.

        Extracts encounter type, period (start/end), status, reason codes,
        and service type. Maps to OMOP Visit domain.

        Args:
            session: Database session
            patient_id: Internal patient ID
            patient_node_id: Patient KG node UUID
            encounter: FHIR Encounter resource

        Returns:
            Tuple of (fact, node, edge) or (None, None, None) if malformed
        """
        # Check status -- skip entered-in-error encounters
        status = encounter.get("status", "finished")
        if status == "entered-in-error":
            return None, None, None

        # Extract encounter type (e.g., ambulatory, emergency, inpatient)
        encounter_types = encounter.get("type", [])
        type_code, type_display, type_system = None, None, None
        if encounter_types:
            type_code, type_display, type_system = self._get_code_from_codeable_concept(
                encounter_types[0]
            )

        # Extract class (broader category: AMB, IMP, EMER, etc.)
        encounter_class = encounter.get("class", {})
        class_code = encounter_class.get("code")
        class_display = encounter_class.get("display")

        # Build a display label from the best available info
        display = type_display or class_display or f"Encounter ({status})"

        # Extract period (start/end)
        period = encounter.get("period", {})
        period_start = self._parse_fhir_datetime(period.get("start"))
        period_end = self._parse_fhir_datetime(period.get("end"))

        # Extract reason codes
        reason_codes = encounter.get("reasonCode", [])
        reason_texts = []
        for reason in reason_codes:
            _, reason_display, _ = self._get_code_from_codeable_concept(reason)
            if reason_display:
                reason_texts.append(reason_display)

        # Extract service type
        service_type = encounter.get("serviceType", {})
        _, service_display, _ = self._get_code_from_codeable_concept(service_type) if service_type else (None, None, None)

        # Determine assertion from status
        assertion = Assertion.PRESENT
        if status in ("cancelled", "entered-in-error"):
            assertion = Assertion.ABSENT

        # Determine temporality
        temporality = Temporality.PAST if period_end else Temporality.CURRENT
        if status == "planned":
            temporality = Temporality.FUTURE

        # Use type code for concept ID if numeric, otherwise 0
        concept_id = int(type_code) if type_code and type_code.isdigit() else 0

        # Create clinical fact with Visit domain
        fact = ClinicalFact(
            patient_id=patient_id,
            domain=Domain.VISIT,
            omop_concept_id=concept_id,
            concept_name=display,
            assertion=assertion,
            temporality=temporality,
            experiencer=Experiencer.PATIENT,
            confidence=1.0,
            start_date=period_start,
            end_date=period_end,
        )
        session.add(fact)
        await session.flush()

        # Create KG node -- use ADMISSION node type (closest to visit/encounter)
        node = KGNode(
            patient_id=patient_id,
            node_type=NodeType.ADMISSION,
            omop_concept_id=concept_id if concept_id else None,
            label=display,
            properties={
                "fhir_id": encounter.get("id"),
                "status": status,
                "class_code": class_code,
                "class_display": class_display,
                "type_code": type_code,
                "type_system": type_system,
                "service_type": service_display,
                "reason_codes": reason_texts,
                "period_start": period_start.isoformat() if period_start else None,
                "period_end": period_end.isoformat() if period_end else None,
            },
        )
        session.add(node)
        await session.flush()

        # Create edge from patient to encounter
        edge = KGEdge(
            patient_id=patient_id,
            source_node_id=patient_node_id,
            target_node_id=node.id,
            edge_type=EdgeType.HAS_EPISODE,
            fact_id=fact.id,
            properties={
                "status": status,
                "class": class_code,
                "reason": ", ".join(reason_texts) if reason_texts else None,
            },
        )
        session.add(edge)

        return fact, node, edge

    async def _import_immunization(
        self,
        session: AsyncSession,
        patient_id: str,
        patient_node_id: UUID,
        immunization: dict[str, Any],
    ) -> tuple[ClinicalFact | None, KGNode | None, KGEdge | None]:
        """Import a FHIR Immunization as a clinical fact and KG node.

        Extracts vaccine code (CVX), status, occurrence date, and dose info.
        Maps to OMOP Drug domain (immunizations are Drug Exposures in OMOP).

        Args:
            session: Database session
            patient_id: Internal patient ID
            patient_node_id: Patient KG node UUID
            immunization: FHIR Immunization resource

        Returns:
            Tuple of (fact, node, edge) or (None, None, None) if malformed
        """
        # Extract vaccine code from vaccineCode CodeableConcept
        vaccine_concept = immunization.get("vaccineCode", {})
        code, display, system = self._get_code_from_codeable_concept(vaccine_concept)

        if not display:
            return None, None, None

        # Check status
        status = immunization.get("status", "completed")
        if status == "entered-in-error":
            return None, None, None

        # Determine assertion from status
        assertion = Assertion.PRESENT
        if status == "not-done":
            assertion = Assertion.ABSENT

        # Extract occurrence date (occurrenceDateTime or occurrenceString)
        occurrence = self._parse_fhir_datetime(
            immunization.get("occurrenceDateTime")
        )

        # Extract dose information
        dose_quantity = immunization.get("doseQuantity", {})
        dose_value = dose_quantity.get("value")
        dose_unit = dose_quantity.get("unit")

        # Extract protocol applied (dose number, series)
        protocol_applied = immunization.get("protocolApplied", [])
        dose_number = None
        series_name = None
        if protocol_applied:
            protocol = protocol_applied[0]
            dose_number = protocol.get("doseNumberPositiveInt") or protocol.get("doseNumberString")
            series_name = protocol.get("series")

        # Extract manufacturer
        manufacturer = immunization.get("manufacturer", {})
        manufacturer_display = manufacturer.get("display") if manufacturer else None

        # Extract site and route
        site_concept = immunization.get("site", {})
        _, site_display, _ = self._get_code_from_codeable_concept(site_concept) if site_concept else (None, None, None)

        route_concept = immunization.get("route", {})
        _, route_display, _ = self._get_code_from_codeable_concept(route_concept) if route_concept else (None, None, None)

        # Determine if this is a CVX code
        is_cvx = system and "cvx" in system.lower() if system else False

        # Create clinical fact -- immunizations map to Drug domain in OMOP
        fact = ClinicalFact(
            patient_id=patient_id,
            domain=Domain.DRUG,
            omop_concept_id=int(code) if code and code.isdigit() else 0,
            concept_name=display,
            assertion=assertion,
            temporality=Temporality.PAST if occurrence else Temporality.CURRENT,
            experiencer=Experiencer.PATIENT,
            confidence=1.0,
            value=str(dose_value) if dose_value is not None else None,
            unit=dose_unit,
            start_date=occurrence,
        )
        session.add(fact)
        await session.flush()

        # Create KG node
        node = KGNode(
            patient_id=patient_id,
            node_type=NodeType.DRUG,
            omop_concept_id=int(code) if code and code.isdigit() else None,
            label=display,
            properties={
                "fhir_id": immunization.get("id"),
                "fhir_resource_type": "Immunization",
                "vaccine_code": code,
                "vaccine_system": system,
                "is_cvx": is_cvx,
                "status": status,
                "manufacturer": manufacturer_display,
                "dose_number": dose_number,
                "series": series_name,
                "site": site_display,
                "route": route_display,
                "dose_value": dose_value,
                "dose_unit": dose_unit,
            },
        )
        session.add(node)
        await session.flush()

        # Create edge from patient to immunization
        edge = KGEdge(
            patient_id=patient_id,
            source_node_id=patient_node_id,
            target_node_id=node.id,
            edge_type=EdgeType.TAKES_DRUG,
            fact_id=fact.id,
            properties={
                "status": status,
                "immunization": True,
                "dose_number": dose_number,
            },
        )
        session.add(edge)

        return fact, node, edge

    def _extract_document_reference_text(
        self, doc_ref: dict[str, Any]
    ) -> tuple[str | None, str | None]:
        """Extract text content from a FHIR DocumentReference.

        Handles multiple attachment formats:
        1. data (base64-encoded inline content)
        2. Plain text content type with data
        3. C-CDA XML (extracts text sections)

        Args:
            doc_ref: FHIR DocumentReference resource

        Returns:
            Tuple of (extracted_text, mime_type)
        """
        for content_entry in doc_ref.get("content", []):
            attachment = content_entry.get("attachment", {})
            content_type = attachment.get("contentType", "")
            data = attachment.get("data")

            if not data:
                continue

            try:
                decoded = base64.b64decode(data).decode("utf-8", errors="replace")
            except Exception:
                continue

            # Plain text — use directly
            if "text/plain" in content_type:
                return decoded.strip(), content_type

            # C-CDA XML — extract text sections
            if "xml" in content_type or "cda" in content_type.lower():
                text = self._extract_text_from_ccda(decoded)
                if text:
                    return text, content_type

            # HTML — strip tags for raw text
            if "html" in content_type:
                import re
                text = re.sub(r"<[^>]+>", " ", decoded)
                text = re.sub(r"\s+", " ", text).strip()
                if text:
                    return text, content_type

            # Fallback: if it looks like text, use it
            if decoded and not decoded.startswith(("%PDF", "\x89PNG", "\xff\xd8")):
                return decoded.strip(), content_type

        return None, None

    def _extract_text_from_ccda(self, xml_content: str) -> str | None:
        """Extract narrative text from C-CDA XML sections.

        C-CDA documents contain <text> elements within each section
        that hold the human-readable clinical narrative.

        Args:
            xml_content: Raw C-CDA XML string

        Returns:
            Concatenated section text or None
        """
        import re

        # Extract text from <text>...</text> blocks in sections
        text_blocks = re.findall(
            r"<text[^>]*>(.*?)</text>",
            xml_content,
            re.DOTALL | re.IGNORECASE,
        )
        if not text_blocks:
            return None

        sections = []
        for block in text_blocks:
            # Strip XML/HTML tags
            clean = re.sub(r"<[^>]+>", " ", block)
            clean = re.sub(r"\s+", " ", clean).strip()
            if clean and len(clean) > 20:  # Skip trivially short sections
                sections.append(clean)

        return "\n\n".join(sections) if sections else None

    def _determine_note_type(self, doc_ref: dict[str, Any]) -> str:
        """Determine the clinical note type from a DocumentReference.

        Uses the type CodeableConcept and category to classify the note.

        Args:
            doc_ref: FHIR DocumentReference resource

        Returns:
            Note type string (e.g., 'progress_note', 'discharge_summary')
        """
        # Check type CodeableConcept
        type_concept = doc_ref.get("type", {})
        codings = type_concept.get("coding", [])
        for coding in codings:
            code = coding.get("code", "")
            display = (coding.get("display") or "").lower()

            # LOINC document type codes
            loinc_map = {
                "18842-5": "discharge_summary",
                "11506-3": "progress_note",
                "34117-2": "history_and_physical",
                "11488-4": "consultation_note",
                "28570-0": "procedure_note",
                "11502-2": "lab_report",
                "18748-4": "radiology_report",
                "34133-9": "clinical_summary",  # CCD
                "34111-5": "emergency_note",
                "57133-1": "referral_note",
            }
            if code in loinc_map:
                return loinc_map[code]

            # Fallback: match on display text
            if "discharge" in display:
                return "discharge_summary"
            if "progress" in display:
                return "progress_note"
            if "history" in display or "h&p" in display:
                return "history_and_physical"
            if "consult" in display:
                return "consultation_note"
            if "operative" in display or "procedure" in display:
                return "procedure_note"
            if "radiology" in display or "imaging" in display:
                return "radiology_report"
            if "pathology" in display or "lab" in display:
                return "lab_report"

        # Check category
        for cat in doc_ref.get("category", []):
            for coding in cat.get("coding", []):
                code = coding.get("code", "")
                if code == "clinical-note":
                    return "clinical_note"

        return "clinical_note"

    async def _import_document_reference(
        self,
        session: AsyncSession,
        patient_id: str,
        patient_node_id: UUID,
        doc_ref: dict[str, Any],
    ) -> tuple[ClinicalFact | None, KGNode | None, KGEdge | None]:
        """Import a FHIR DocumentReference as a clinical note.

        Extracts text from the DocumentReference attachment (base64 data,
        C-CDA XML, or plain text), creates a Document record for NLP
        processing, and adds a clinical_note node to the knowledge graph.

        Args:
            session: Database session
            patient_id: Internal patient ID
            patient_node_id: Patient KG node UUID
            doc_ref: FHIR DocumentReference resource

        Returns:
            Tuple of (fact, node, edge) or (None, None, None) if no text
        """
        # Skip non-current documents
        doc_status = doc_ref.get("status", "current")
        if doc_status == "entered-in-error":
            return None, None, None

        # Extract text content
        text, mime_type = self._extract_document_reference_text(doc_ref)
        if not text or len(text.strip()) < 30:
            logger.debug(
                f"Skipping DocumentReference {doc_ref.get('id', '?')}: "
                f"no extractable text (mime={mime_type})"
            )
            return None, None, None

        note_type = self._determine_note_type(doc_ref)
        doc_date = self._parse_fhir_datetime(
            doc_ref.get("date") or doc_ref.get("context", {}).get("period", {}).get("start")
        )

        # Get description for display
        description = doc_ref.get("description") or f"Clinical note ({note_type})"

        # Create Document record for NLP pipeline
        job_id = uuid4()
        db_document = DocumentModel(
            patient_id=patient_id,
            note_type=note_type,
            text=text,
            extra_metadata={
                "source": "metriport_hie",
                "fhir_id": doc_ref.get("id"),
                "mime_type": mime_type,
                "description": description,
                "doc_status": doc_status,
            },
            status=JobStatus.QUEUED,
            job_id=job_id,
        )
        session.add(db_document)
        await session.flush()

        # Queue NLP processing
        try:
            from app.core.queue import QUEUE_NAMES, enqueue_job
            from app.jobs import process_document

            enqueue_job(
                process_document,
                str(db_document.id),
                queue_name=QUEUE_NAMES["document"],
                job_id=job_id,
            )
            logger.info(
                f"Queued NLP processing for HIE note {db_document.id} "
                f"(type={note_type}, {len(text)} chars)"
            )
        except Exception as e:
            logger.warning(f"Could not queue NLP job for HIE note: {e}")

        # Create KG node for the clinical note
        node = KGNode(
            patient_id=patient_id,
            node_type=NodeType.CLINICAL_NOTE,
            label=description[:200],
            properties={
                "fhir_id": doc_ref.get("id"),
                "note_type": note_type,
                "mime_type": mime_type,
                "document_id": str(db_document.id),
                "char_count": len(text),
                "date": doc_date.isoformat() if doc_date else None,
            },
        )
        session.add(node)
        await session.flush()

        # Create edge from patient to clinical note
        edge = KGEdge(
            patient_id=patient_id,
            source_node_id=patient_node_id,
            target_node_id=node.id,
            edge_type=EdgeType.EXTRACTED_FROM,
            properties={
                "note_type": note_type,
                "date": doc_date.isoformat() if doc_date else None,
            },
        )
        session.add(edge)

        logger.info(
            f"Imported DocumentReference {doc_ref.get('id', '?')} as "
            f"{note_type} ({len(text)} chars) -> document {db_document.id}"
        )

        # Return None for fact since the NLP pipeline will create facts
        return None, node, edge

    async def _import_diagnostic_report(
        self,
        session: AsyncSession,
        patient_id: str,
        patient_node_id: UUID,
        report: dict[str, Any],
    ) -> tuple[ClinicalFact | None, KGNode | None, KGEdge | None]:
        """Import a FHIR DiagnosticReport as a clinical note and/or observations.

        DiagnosticReports contain:
        1. presentedForm: Attachments (PDF, text) with full report
        2. conclusion: Short text conclusion
        3. conclusionCode: Coded conclusions
        4. result: References to Observation resources (already handled)

        This handler extracts the narrative text and feeds it through
        the NLP pipeline for mention extraction.

        Args:
            session: Database session
            patient_id: Internal patient ID
            patient_node_id: Patient KG node UUID
            report: FHIR DiagnosticReport resource

        Returns:
            Tuple of (fact, node, edge) or (None, None, None)
        """
        report_status = report.get("status", "final")
        if report_status in ("entered-in-error", "cancelled"):
            return None, None, None

        # Extract text — prefer presentedForm, fall back to conclusion
        text = None
        mime_type = None

        # Try presentedForm attachments first
        for form in report.get("presentedForm", []):
            data = form.get("data")
            content_type = form.get("contentType", "")
            if data:
                try:
                    decoded = base64.b64decode(data).decode("utf-8", errors="replace")
                    if "text/plain" in content_type:
                        text = decoded.strip()
                        mime_type = content_type
                        break
                    if "xml" in content_type:
                        text = self._extract_text_from_ccda(decoded)
                        mime_type = content_type
                        if text:
                            break
                    # HTML
                    if "html" in content_type:
                        import re
                        text = re.sub(r"<[^>]+>", " ", decoded)
                        text = re.sub(r"\s+", " ", text).strip()
                        mime_type = content_type
                        if text:
                            break
                except Exception:
                    continue

        # Fall back to conclusion text
        if not text:
            conclusion = report.get("conclusion")
            if conclusion and len(conclusion.strip()) >= 20:
                text = conclusion.strip()
                mime_type = "text/plain"

        if not text or len(text.strip()) < 20:
            return None, None, None

        # Determine note type from category
        code_concept = report.get("code", {})
        code, display, system = self._get_code_from_codeable_concept(code_concept)
        report_display = display or "Diagnostic Report"

        # Map category to note type
        note_type = "diagnostic_report"
        for cat in report.get("category", []):
            for coding in cat.get("coding", []):
                cat_display = (coding.get("display") or "").lower()
                if "radiology" in cat_display or "imaging" in cat_display:
                    note_type = "radiology_report"
                elif "pathology" in cat_display:
                    note_type = "pathology_report"
                elif "laboratory" in cat_display or "lab" in cat_display:
                    note_type = "lab_report"

        effective = self._parse_fhir_datetime(
            report.get("effectiveDateTime")
            or report.get("effectivePeriod", {}).get("start")
        )

        # Create Document record for NLP pipeline
        job_id = uuid4()
        db_document = DocumentModel(
            patient_id=patient_id,
            note_type=note_type,
            text=text,
            extra_metadata={
                "source": "metriport_hie",
                "fhir_id": report.get("id"),
                "fhir_resource_type": "DiagnosticReport",
                "mime_type": mime_type,
                "report_name": report_display,
                "report_status": report_status,
            },
            status=JobStatus.QUEUED,
            job_id=job_id,
        )
        session.add(db_document)
        await session.flush()

        # Queue NLP processing
        try:
            from app.core.queue import QUEUE_NAMES, enqueue_job
            from app.jobs import process_document

            enqueue_job(
                process_document,
                str(db_document.id),
                queue_name=QUEUE_NAMES["document"],
                job_id=job_id,
            )
            logger.info(
                f"Queued NLP processing for DiagnosticReport {db_document.id} "
                f"(type={note_type}, {len(text)} chars)"
            )
        except Exception as e:
            logger.warning(f"Could not queue NLP job for DiagnosticReport: {e}")

        # Create KG node
        node = KGNode(
            patient_id=patient_id,
            node_type=NodeType.CLINICAL_NOTE,
            omop_concept_id=int(code) if code and code.isdigit() else None,
            label=report_display[:200],
            properties={
                "fhir_id": report.get("id"),
                "fhir_resource_type": "DiagnosticReport",
                "note_type": note_type,
                "document_id": str(db_document.id),
                "char_count": len(text),
                "date": effective.isoformat() if effective else None,
            },
        )
        session.add(node)
        await session.flush()

        # Create edge from patient to report note
        edge = KGEdge(
            patient_id=patient_id,
            source_node_id=patient_node_id,
            target_node_id=node.id,
            edge_type=EdgeType.EXTRACTED_FROM,
            properties={
                "note_type": note_type,
                "date": effective.isoformat() if effective else None,
            },
        )
        session.add(edge)

        logger.info(
            f"Imported DiagnosticReport {report.get('id', '?')} as "
            f"{note_type} ({len(text)} chars) -> document {db_document.id}"
        )

        return None, node, edge
