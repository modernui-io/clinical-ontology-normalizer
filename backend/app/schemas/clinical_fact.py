"""ClinicalFact and FactEvidence schemas."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.base import Assertion, Domain, Experiencer, Temporality


class EvidenceType(str, Enum):
    """Type of evidence source."""

    MENTION = "mention"  # From NLP extraction
    STRUCTURED = "structured"  # From FHIR/CSV data
    INFERRED = "inferred"  # Derived from other facts


class ClinicalFactCreate(BaseModel):
    """Schema for creating a canonical clinical fact.

    Base schema with core clinical fact fields. Used for fact creation
    and as a base class for the full ClinicalFact response schema.
    """

    patient_id: str = Field(..., description="Patient identifier")
    domain: Domain = Field(..., description="OMOP domain (condition, drug, etc.)")
    omop_concept_id: int = Field(..., description="Standard OMOP concept ID")
    concept_name: str = Field(..., description="Human-readable concept name")
    assertion: Assertion = Field(default=Assertion.PRESENT, description="Assertion status")
    temporality: Temporality = Field(default=Temporality.CURRENT, description="Temporal context")
    experiencer: Experiencer = Field(default=Experiencer.PATIENT, description="Who it applies to")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Overall confidence")
    value: str | None = Field(None, description="Value for measurements")
    unit: str | None = Field(None, description="Unit for measurements")
    start_date: datetime | None = Field(None, description="When the fact started/occurred")
    end_date: datetime | None = Field(None, description="When the fact ended (if applicable)")


class ClinicalFact(ClinicalFactCreate):
    """Schema for a canonical clinical fact response.

    Extends ClinicalFactCreate with server-generated fields (id, created_at).

    ClinicalFacts are the normalized, deduplicated representation of clinical
    information. They combine evidence from both unstructured (NLP) and
    structured (FHIR/CSV) sources.

    IMPORTANT: Negated findings (assertion=absent) are preserved as facts.
    They should NOT be inserted into positive event tables but should be
    exported in NOTE_NLP format with term_exists='N'.
    """

    id: UUID = Field(..., description="Unique fact identifier")
    created_at: datetime = Field(..., description="When fact was created")

    model_config = {"from_attributes": True}

    @property
    def is_negated(self) -> bool:
        """Check if this fact represents a negated finding."""
        return self.assertion == Assertion.ABSENT

    @property
    def is_uncertain(self) -> bool:
        """Check if this fact represents an uncertain finding."""
        return self.assertion == Assertion.POSSIBLE

    @property
    def is_family_history(self) -> bool:
        """Check if this fact is about a family member."""
        return self.experiencer == Experiencer.FAMILY


class FactEvidenceCreate(BaseModel):
    """Schema for creating a link between a fact and its evidence.

    Base schema with core evidence fields. Used for evidence creation
    and as a base class for the full FactEvidence response schema.
    """

    fact_id: UUID = Field(..., description="ID of the clinical fact")
    evidence_type: EvidenceType = Field(..., description="Type of evidence")
    source_id: UUID = Field(..., description="ID of source (mention_id, document_id, etc.)")
    source_table: str = Field(..., description="Source table name")
    weight: float = Field(default=1.0, ge=0.0, le=1.0, description="Evidence weight/contribution")
    metadata: dict = Field(default_factory=dict, description="Additional evidence metadata")


class FactEvidence(FactEvidenceCreate):
    """Schema for evidence supporting a clinical fact response.

    Extends FactEvidenceCreate with server-generated fields (id, created_at).

    Links ClinicalFacts to their source evidence, enabling full provenance
    tracking. A single fact may have multiple evidence sources (e.g., a
    condition mentioned in multiple notes, or confirmed by both NLP and
    structured data).
    """

    id: UUID = Field(..., description="Unique evidence link identifier")
    created_at: datetime = Field(..., description="When evidence link was created")

    model_config = {"from_attributes": True}
