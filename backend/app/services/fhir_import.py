"""FHIR Import Service - Import patient data from FHIR into knowledge graph."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Self
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinical_fact import ClinicalFact, FactEvidence
from app.models.knowledge_graph import KGEdge, KGNode
from app.schemas.base import Assertion, Domain, Experiencer, Temporality
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
