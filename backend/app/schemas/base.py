"""Base schemas and enums for Clinical Ontology Normalizer."""

from __future__ import annotations

from enum import Enum


class Assertion(str, Enum):
    """Assertion status for clinical mentions and facts."""

    PRESENT = "present"
    ABSENT = "absent"  # Negated
    POSSIBLE = "possible"  # Uncertain
    CONDITIONAL = "conditional"  # Conditional statement
    HYPOTHETICAL = "hypothetical"  # Hypothetical scenario
    FAMILY_HISTORY = "family_history"  # Family history mention
    HISTORICAL = "historical"  # Past/former condition (e.g., former smoker)


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


class ExtractionStatus(str, Enum):
    """Extraction status propagated across import, KG build, and Q&A.

    P0-006: Tracks whether NLP extraction succeeded, partially failed, or
    completely failed at the note or pipeline level.
    """

    OK = "ok"
    PARTIAL = "partial"  # Some notes extracted, some failed
    FAILED = "failed"  # All notes failed extraction


class JobStatus(str, Enum):
    """Status of a processing job."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ConsentStatus(str, Enum):
    """Consent status for document ingestion (P1-027)."""

    OBTAINED = "obtained"
    PENDING = "pending"
    DECLINED = "declined"
    NOT_REQUIRED = "not_required"


class PurposeOfUse(str, Enum):
    """Standard purpose-of-use values for audit events (P1-029)."""

    TREATMENT = "treatment"
    PAYMENT = "payment"
    OPERATIONS = "operations"
    RESEARCH = "research"
    PUBLIC_HEALTH = "public_health"
    QUALITY_ASSURANCE = "quality_assurance"


class ResourceType(str, Enum):
    """Type of structured resource."""

    FHIR_BUNDLE = "fhir_bundle"
    CSV = "csv"
