"""FHIR R4 Export Service.

Exports clinical facts to FHIR R4 resources including:
- Condition resources
- MedicationStatement resources
- Observation resources
- Procedure resources
- DiagnosticReport resources
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import json
import logging
import threading
import uuid

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Data Classes
# ============================================================================


class FHIRResourceType(Enum):
    """FHIR R4 resource types."""

    CONDITION = "Condition"
    MEDICATION_STATEMENT = "MedicationStatement"
    OBSERVATION = "Observation"
    PROCEDURE = "Procedure"
    DIAGNOSTIC_REPORT = "DiagnosticReport"
    PATIENT = "Patient"
    ENCOUNTER = "Encounter"
    BUNDLE = "Bundle"


class ConditionClinicalStatus(Enum):
    """FHIR Condition clinical status."""

    ACTIVE = "active"
    RECURRENCE = "recurrence"
    RELAPSE = "relapse"
    INACTIVE = "inactive"
    REMISSION = "remission"
    RESOLVED = "resolved"


class ConditionVerificationStatus(Enum):
    """FHIR Condition verification status."""

    UNCONFIRMED = "unconfirmed"
    PROVISIONAL = "provisional"
    DIFFERENTIAL = "differential"
    CONFIRMED = "confirmed"
    REFUTED = "refuted"
    ENTERED_IN_ERROR = "entered-in-error"


class ObservationStatus(Enum):
    """FHIR Observation status."""

    REGISTERED = "registered"
    PRELIMINARY = "preliminary"
    FINAL = "final"
    AMENDED = "amended"
    CORRECTED = "corrected"
    CANCELLED = "cancelled"
    ENTERED_IN_ERROR = "entered-in-error"
    UNKNOWN = "unknown"


@dataclass
class ClinicalFact:
    """Input clinical fact for FHIR conversion."""

    fact_type: str  # condition, drug, measurement, procedure
    label: str
    value: str | None = None
    unit: str | None = None

    # Coding
    omop_concept_id: int | None = None
    icd10_code: str | None = None
    snomed_code: str | None = None
    loinc_code: str | None = None
    rxnorm_code: str | None = None

    # Context
    assertion: str = "present"  # present, absent, possible
    temporality: str = "current"  # current, historical, future
    section: str | None = None

    # Metadata
    patient_id: str | None = None
    encounter_id: str | None = None
    recorded_date: str | None = None
    confidence: float = 1.0


@dataclass
class FHIRResource:
    """Generated FHIR resource."""

    resource_type: FHIRResourceType
    resource_id: str
    resource: dict[str, Any]
    source_fact_id: str | None = None


@dataclass
class FHIRBundle:
    """FHIR Bundle containing multiple resources."""

    bundle_id: str
    bundle_type: str = "collection"
    total: int = 0
    entries: list[FHIRResource] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ============================================================================
# FHIR Code Systems
# ============================================================================


FHIR_CODE_SYSTEMS = {
    "icd10": "http://hl7.org/fhir/sid/icd-10-cm",
    "snomed": "http://snomed.info/sct",
    "loinc": "http://loinc.org",
    "rxnorm": "http://www.nlm.nih.gov/research/umls/rxnorm",
    "omop": "http://ohdsi.org/omop/concept",
}

CONDITION_CATEGORY_CODE = {
    "system": "http://terminology.hl7.org/CodeSystem/condition-category",
    "code": "encounter-diagnosis",
    "display": "Encounter Diagnosis",
}

OBSERVATION_CATEGORY_VITAL = {
    "system": "http://terminology.hl7.org/CodeSystem/observation-category",
    "code": "vital-signs",
    "display": "Vital Signs",
}

OBSERVATION_CATEGORY_LAB = {
    "system": "http://terminology.hl7.org/CodeSystem/observation-category",
    "code": "laboratory",
    "display": "Laboratory",
}


# ============================================================================
# FHIR Exporter Service
# ============================================================================


class FHIRExporterService:
    """Service for exporting clinical facts to FHIR R4 resources."""

    def __init__(self):
        """Initialize the FHIR exporter."""
        self._resource_counter = 0
        self._lock = threading.Lock()

    def _generate_id(self) -> str:
        """Generate unique resource ID."""
        with self._lock:
            self._resource_counter += 1
            return f"res-{uuid.uuid4().hex[:12]}"

    def export_fact(self, fact: ClinicalFact) -> FHIRResource | None:
        """
        Export a single clinical fact to FHIR resource.

        Args:
            fact: Clinical fact to export

        Returns:
            FHIR resource or None if not exportable
        """
        if fact.fact_type == "condition":
            return self._create_condition(fact)
        elif fact.fact_type == "drug":
            return self._create_medication_statement(fact)
        elif fact.fact_type == "measurement":
            return self._create_observation(fact)
        elif fact.fact_type == "procedure":
            return self._create_procedure(fact)
        else:
            return None

    def export_facts(
        self,
        facts: list[ClinicalFact],
        patient_id: str | None = None,
        include_patient: bool = True,
    ) -> FHIRBundle:
        """
        Export multiple facts to a FHIR Bundle.

        Args:
            facts: List of clinical facts
            patient_id: Patient ID for all resources
            include_patient: Whether to include Patient resource

        Returns:
            FHIR Bundle with all resources
        """
        bundle_id = f"bundle-{uuid.uuid4().hex[:12]}"
        entries: list[FHIRResource] = []

        # Add Patient resource if requested
        if include_patient and patient_id:
            patient_resource = self._create_patient(patient_id)
            entries.append(patient_resource)

        # Export each fact
        for fact in facts:
            if patient_id and not fact.patient_id:
                fact.patient_id = patient_id

            resource = self.export_fact(fact)
            if resource:
                entries.append(resource)

        return FHIRBundle(
            bundle_id=bundle_id,
            bundle_type="collection",
            total=len(entries),
            entries=entries,
        )

    def to_json(self, bundle: FHIRBundle) -> str:
        """
        Convert bundle to FHIR JSON.

        Args:
            bundle: FHIR Bundle to convert

        Returns:
            JSON string
        """
        fhir_bundle = {
            "resourceType": "Bundle",
            "id": bundle.bundle_id,
            "type": bundle.bundle_type,
            "timestamp": bundle.generated_at,
            "total": bundle.total,
            "entry": [
                {
                    "fullUrl": f"urn:uuid:{entry.resource_id}",
                    "resource": entry.resource,
                }
                for entry in bundle.entries
            ],
        }
        return json.dumps(fhir_bundle, indent=2)

    def _create_patient(self, patient_id: str) -> FHIRResource:
        """Create FHIR Patient resource."""
        resource_id = self._generate_id()

        resource = {
            "resourceType": "Patient",
            "id": resource_id,
            "identifier": [
                {
                    "system": "http://hospital.example.org/patients",
                    "value": patient_id,
                }
            ],
        }

        return FHIRResource(
            resource_type=FHIRResourceType.PATIENT,
            resource_id=resource_id,
            resource=resource,
        )

    def _create_condition(self, fact: ClinicalFact) -> FHIRResource:
        """Create FHIR Condition resource."""
        resource_id = self._generate_id()

        # Determine clinical status
        if fact.temporality == "historical":
            clinical_status = ConditionClinicalStatus.RESOLVED
        elif fact.assertion == "absent":
            clinical_status = ConditionClinicalStatus.INACTIVE
        else:
            clinical_status = ConditionClinicalStatus.ACTIVE

        # Determine verification status
        if fact.assertion == "possible":
            verification_status = ConditionVerificationStatus.PROVISIONAL
        elif fact.assertion == "absent":
            verification_status = ConditionVerificationStatus.REFUTED
        elif fact.confidence >= 0.9:
            verification_status = ConditionVerificationStatus.CONFIRMED
        else:
            verification_status = ConditionVerificationStatus.UNCONFIRMED

        # Build coding
        coding = []
        if fact.icd10_code:
            coding.append({
                "system": FHIR_CODE_SYSTEMS["icd10"],
                "code": fact.icd10_code,
                "display": fact.label,
            })
        if fact.snomed_code:
            coding.append({
                "system": FHIR_CODE_SYSTEMS["snomed"],
                "code": fact.snomed_code,
                "display": fact.label,
            })
        if fact.omop_concept_id:
            coding.append({
                "system": FHIR_CODE_SYSTEMS["omop"],
                "code": str(fact.omop_concept_id),
                "display": fact.label,
            })

        # Fallback to text if no coding
        if not coding:
            coding.append({
                "system": "http://hospital.example.org/conditions",
                "code": fact.label.lower().replace(" ", "-"),
                "display": fact.label,
            })

        resource = {
            "resourceType": "Condition",
            "id": resource_id,
            "clinicalStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                        "code": clinical_status.value,
                    }
                ]
            },
            "verificationStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                        "code": verification_status.value,
                    }
                ]
            },
            "category": [{"coding": [CONDITION_CATEGORY_CODE]}],
            "code": {
                "coding": coding,
                "text": fact.label,
            },
        }

        # Add patient reference
        if fact.patient_id:
            resource["subject"] = {
                "reference": f"Patient/{fact.patient_id}",
            }

        # Add recorded date
        if fact.recorded_date:
            resource["recordedDate"] = fact.recorded_date

        # Add encounter reference
        if fact.encounter_id:
            resource["encounter"] = {
                "reference": f"Encounter/{fact.encounter_id}",
            }

        return FHIRResource(
            resource_type=FHIRResourceType.CONDITION,
            resource_id=resource_id,
            resource=resource,
        )

    def _create_medication_statement(self, fact: ClinicalFact) -> FHIRResource:
        """Create FHIR MedicationStatement resource."""
        resource_id = self._generate_id()

        # Determine status
        if fact.assertion == "absent" or fact.temporality == "historical":
            status = "stopped"
        else:
            status = "active"

        # Build medication coding
        coding = []
        if fact.rxnorm_code:
            coding.append({
                "system": FHIR_CODE_SYSTEMS["rxnorm"],
                "code": fact.rxnorm_code,
                "display": fact.label,
            })
        if fact.omop_concept_id:
            coding.append({
                "system": FHIR_CODE_SYSTEMS["omop"],
                "code": str(fact.omop_concept_id),
                "display": fact.label,
            })

        if not coding:
            coding.append({
                "system": "http://hospital.example.org/medications",
                "code": fact.label.lower().replace(" ", "-"),
                "display": fact.label,
            })

        resource = {
            "resourceType": "MedicationStatement",
            "id": resource_id,
            "status": status,
            "medicationCodeableConcept": {
                "coding": coding,
                "text": fact.label,
            },
        }

        # Add patient reference
        if fact.patient_id:
            resource["subject"] = {
                "reference": f"Patient/{fact.patient_id}",
            }

        # Add dosage if value present
        if fact.value:
            resource["dosage"] = [
                {
                    "text": f"{fact.value} {fact.unit or ''}".strip(),
                }
            ]

        # Add effective date
        if fact.recorded_date:
            resource["effectiveDateTime"] = fact.recorded_date

        return FHIRResource(
            resource_type=FHIRResourceType.MEDICATION_STATEMENT,
            resource_id=resource_id,
            resource=resource,
        )

    def _create_observation(self, fact: ClinicalFact) -> FHIRResource:
        """Create FHIR Observation resource."""
        resource_id = self._generate_id()

        # Determine status
        status = ObservationStatus.FINAL if fact.confidence >= 0.9 else ObservationStatus.PRELIMINARY

        # Determine category
        vital_signs = ["blood pressure", "heart rate", "pulse", "temperature", "respiratory rate", "oxygen", "weight", "height", "bmi"]
        is_vital = any(vs in fact.label.lower() for vs in vital_signs)
        category = OBSERVATION_CATEGORY_VITAL if is_vital else OBSERVATION_CATEGORY_LAB

        # Build coding
        coding = []
        if fact.loinc_code:
            coding.append({
                "system": FHIR_CODE_SYSTEMS["loinc"],
                "code": fact.loinc_code,
                "display": fact.label,
            })
        if fact.omop_concept_id:
            coding.append({
                "system": FHIR_CODE_SYSTEMS["omop"],
                "code": str(fact.omop_concept_id),
                "display": fact.label,
            })

        if not coding:
            coding.append({
                "system": "http://hospital.example.org/observations",
                "code": fact.label.lower().replace(" ", "-"),
                "display": fact.label,
            })

        resource = {
            "resourceType": "Observation",
            "id": resource_id,
            "status": status.value,
            "category": [{"coding": [category]}],
            "code": {
                "coding": coding,
                "text": fact.label,
            },
        }

        # Add patient reference
        if fact.patient_id:
            resource["subject"] = {
                "reference": f"Patient/{fact.patient_id}",
            }

        # Add value
        if fact.value is not None:
            try:
                numeric_value = float(fact.value)
                resource["valueQuantity"] = {
                    "value": numeric_value,
                    "unit": fact.unit or "",
                    "system": "http://unitsofmeasure.org",
                }
            except ValueError:
                resource["valueString"] = str(fact.value)

        # Add effective date
        if fact.recorded_date:
            resource["effectiveDateTime"] = fact.recorded_date

        return FHIRResource(
            resource_type=FHIRResourceType.OBSERVATION,
            resource_id=resource_id,
            resource=resource,
        )

    def _create_procedure(self, fact: ClinicalFact) -> FHIRResource:
        """Create FHIR Procedure resource."""
        resource_id = self._generate_id()

        # Determine status
        if fact.temporality == "future":
            status = "preparation"
        elif fact.temporality == "historical":
            status = "completed"
        else:
            status = "in-progress"

        # Build coding
        coding = []
        if fact.snomed_code:
            coding.append({
                "system": FHIR_CODE_SYSTEMS["snomed"],
                "code": fact.snomed_code,
                "display": fact.label,
            })
        if fact.omop_concept_id:
            coding.append({
                "system": FHIR_CODE_SYSTEMS["omop"],
                "code": str(fact.omop_concept_id),
                "display": fact.label,
            })

        if not coding:
            coding.append({
                "system": "http://hospital.example.org/procedures",
                "code": fact.label.lower().replace(" ", "-"),
                "display": fact.label,
            })

        resource = {
            "resourceType": "Procedure",
            "id": resource_id,
            "status": status,
            "code": {
                "coding": coding,
                "text": fact.label,
            },
        }

        # Add patient reference
        if fact.patient_id:
            resource["subject"] = {
                "reference": f"Patient/{fact.patient_id}",
            }

        # Add performed date
        if fact.recorded_date:
            resource["performedDateTime"] = fact.recorded_date

        return FHIRResource(
            resource_type=FHIRResourceType.PROCEDURE,
            resource_id=resource_id,
            resource=resource,
        )

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        return {
            "resources_generated": self._resource_counter,
            "supported_resource_types": [rt.value for rt in FHIRResourceType],
            "code_systems": list(FHIR_CODE_SYSTEMS.keys()),
        }


# ============================================================================
# Singleton Pattern
# ============================================================================


_service_instance: FHIRExporterService | None = None
_service_lock = threading.Lock()


def get_fhir_exporter_service() -> FHIRExporterService:
    """Get or create the singleton service instance."""
    global _service_instance

    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = FHIRExporterService()

    return _service_instance


def reset_fhir_exporter_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _service_instance
    with _service_lock:
        _service_instance = None
