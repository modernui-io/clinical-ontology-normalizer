"""Base schemas and enums for Clinical Ontology Normalizer."""

from __future__ import annotations

from enum import Enum


class Assertion(str, Enum):
    """Assertion status for clinical mentions and facts."""

    PRESENT = "present"
    ABSENT = "absent"  # Negated
    POSSIBLE = "possible"  # Uncertain


class Temporality(str, Enum):
    """Temporal context for clinical mentions and facts."""

    CURRENT = "current"
    PAST = "past"
    FUTURE = "future"


class Experiencer(str, Enum):
    """Who the clinical finding applies to."""

    PATIENT = "patient"
    FAMILY = "family"
    OTHER = "other"


class Domain(str, Enum):
    """OMOP domain categories for clinical concepts."""

    CONDITION = "condition"
    DRUG = "drug"
    MEASUREMENT = "measurement"
    PROCEDURE = "procedure"
    OBSERVATION = "observation"
    DEVICE = "device"
    VISIT = "visit"
    SPEC_ANATOMIC_SITE = "spec_anatomic_site"


class JobStatus(str, Enum):
    """Status of a processing job."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ResourceType(str, Enum):
    """Type of structured resource."""

    FHIR_BUNDLE = "fhir_bundle"
    CSV = "csv"
