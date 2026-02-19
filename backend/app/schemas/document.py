"""Document and StructuredResource schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.base import ConsentStatus, JobStatus, ResourceType


class DocumentCreate(BaseModel):
    """Schema for creating a new document.

    Base schema with core document fields. Used for document creation
    and as a base class for the full Document response schema.
    """

    patient_id: str = Field(..., description="Patient identifier")
    note_type: str = Field(
        ..., description="Type of clinical note (progress_note, discharge_summary, etc.)"
    )
    text: str = Field(..., description="Raw clinical note text")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    # P1-027: Consent and residency metadata
    residency_country: str | None = Field(
        None,
        min_length=2,
        max_length=2,
        description="ISO 3166-1 alpha-2 country code (e.g. AU, US)",
    )
    consent_status: ConsentStatus | None = Field(
        None,
        description="Consent status: obtained, pending, declined, not_required",
    )
    consent_date: datetime | None = Field(
        None,
        description="When consent was obtained or last updated",
    )
    consent_reference: str | None = Field(
        None,
        max_length=500,
        description="URI or ID of the external consent record",
    )
    note_date: datetime | None = Field(
        None,
        description="Clinical note date, used as reference for resolving relative temporal expressions",
    )

    @field_validator("residency_country")
    @classmethod
    def uppercase_country(cls, v: str | None) -> str | None:
        """Normalize country code to uppercase."""
        return v.upper() if v else v


class Document(DocumentCreate):
    """Schema for a clinical document response.

    Extends DocumentCreate with server-generated fields (id, timestamps, status).
    """

    id: UUID = Field(..., description="Unique document identifier")
    owner_id: str | None = Field(None, description="ID of user who uploaded this document")
    status: JobStatus = Field(default=JobStatus.QUEUED, description="Processing status")
    job_id: UUID | None = Field(None, description="Processing job ID")
    created_at: datetime = Field(..., description="When the document was uploaded")
    processed_at: datetime | None = Field(None, description="When processing completed")

    model_config = {"from_attributes": True}


class DocumentUploadResponse(BaseModel):
    """Response from document upload."""

    document_id: UUID = Field(..., description="ID of the uploaded document")
    job_id: UUID = Field(..., description="ID of the processing job")
    status: JobStatus = Field(..., description="Initial job status")


class StructuredResourceCreate(BaseModel):
    """Schema for creating a structured resource (FHIR/CSV).

    Base schema with core resource fields. Used for resource creation
    and as a base class for the full StructuredResource response schema.
    """

    patient_id: str = Field(..., description="Patient identifier")
    resource_type: ResourceType = Field(..., description="Type of structured resource")
    payload: dict[str, Any] = Field(..., description="The structured data payload")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class StructuredResource(StructuredResourceCreate):
    """Schema for a structured clinical resource response.

    Extends StructuredResourceCreate with server-generated fields.
    """

    id: UUID = Field(..., description="Unique resource identifier")
    status: JobStatus = Field(default=JobStatus.QUEUED, description="Processing status")
    created_at: datetime = Field(..., description="When the resource was uploaded")
    processed_at: datetime | None = Field(None, description="When processing completed")

    model_config = {"from_attributes": True}
