"""Mention and MentionConceptCandidate schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from app.schemas.base import Assertion, Domain, Experiencer, Temporality


class MentionCreate(BaseModel):
    """Schema for creating a mention extracted from text.

    Base schema with core mention fields. Used for mention creation
    and as a base class for the full Mention response schema.
    """

    document_id: UUID = Field(..., description="ID of source document")
    text: str = Field(..., description="The extracted text span")
    start_offset: int = Field(..., ge=0, description="Character start position in document")
    end_offset: int = Field(..., gt=0, description="Character end position in document")
    lexical_variant: str = Field(..., description="Normalized form of the mention")
    section: str | None = Field(None, description="Clinical section where mention appears")
    assertion: Assertion = Field(default=Assertion.PRESENT, description="Assertion status")
    temporality: Temporality = Field(default=Temporality.CURRENT, description="Temporal context")
    experiencer: Experiencer = Field(default=Experiencer.PATIENT, description="Who it applies to")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence")
    event_date: datetime | None = Field(None, description="When the clinical event occurred")

    @field_validator("end_offset")
    @classmethod
    def end_after_start(cls, v: int, info: ValidationInfo) -> int:
        """Validate that end_offset is after start_offset."""
        start = info.data.get("start_offset", 0) if info.data else 0
        if v <= start:
            raise ValueError("end_offset must be greater than start_offset")
        return v


class Mention(MentionCreate):
    """Schema for an extracted mention response.

    Extends MentionCreate with server-generated fields (id, created_at).
    """

    id: UUID = Field(..., description="Unique mention identifier")
    created_at: datetime = Field(..., description="When mention was created")

    model_config = {"from_attributes": True}


class MentionConceptCandidateCreate(BaseModel):
    """Schema for creating a concept mapping candidate.

    Base schema with core candidate fields. Used for candidate creation
    and as a base class for the full MentionConceptCandidate response schema.
    """

    mention_id: UUID = Field(..., description="ID of the mention being mapped")
    omop_concept_id: int = Field(..., description="OMOP concept ID")
    concept_name: str = Field(..., description="Human-readable concept name")
    concept_code: str = Field(..., description="Source vocabulary code")
    vocabulary_id: str = Field(..., description="Source vocabulary (SNOMED, ICD10CM, etc.)")
    domain_id: Domain = Field(..., description="OMOP domain")
    score: float = Field(..., ge=0.0, le=1.0, description="Mapping confidence score")
    method: str = Field(..., description="Mapping method (exact, fuzzy, ml)")
    rank: int = Field(..., ge=1, description="Rank among candidates (1=best)")


class MentionConceptCandidate(MentionConceptCandidateCreate):
    """Schema for a concept mapping candidate response.

    Extends MentionConceptCandidateCreate with server-generated fields.
    """

    id: UUID = Field(..., description="Unique candidate identifier")
    created_at: datetime = Field(..., description="When candidate was created")

    model_config = {"from_attributes": True}
