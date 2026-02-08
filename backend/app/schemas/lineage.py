"""Pydantic schemas for Data Lineage tracking.

CDO-1: Data Lineage Tracking - request/response models for the lineage API.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    """Source type for lineage records."""

    FHIR_IMPORT = "fhir_import"
    NLP_EXTRACTION = "nlp_extraction"
    MANUAL_ENTRY = "manual_entry"
    DERIVED = "derived"
    EXTERNAL_API = "external_api"


class DataLineageRecordCreate(BaseModel):
    """Schema for creating a data lineage record."""

    clinical_fact_id: UUID = Field(..., description="ID of the associated ClinicalFact")
    source_type: SourceType = Field(..., description="How the fact was produced")
    source_document_id: UUID | None = Field(None, description="Source document ID (if from a document)")
    source_resource_type: str | None = Field(None, description="FHIR resource type (e.g., Condition, Observation)")
    source_resource_id: str | None = Field(None, description="Original FHIR resource ID")
    extraction_method: str | None = Field(None, description="Extraction method (e.g., fhir_direct_mapping, nlp_rule_based)")
    extraction_confidence: float | None = Field(None, ge=0.0, le=1.0, description="Confidence score 0-1")
    transformation_chain: list[dict] | None = Field(None, description="Ordered list of transformations applied")


class DataLineageRecordResponse(DataLineageRecordCreate):
    """Schema for a data lineage record response."""

    id: UUID = Field(..., description="Unique lineage record identifier")
    created_at: datetime = Field(..., description="When the lineage record was created")

    model_config = {"from_attributes": True}


class LineageSourceDistribution(BaseModel):
    """Distribution of lineage sources for a patient."""

    source_type: SourceType
    count: int
    percentage: float = Field(..., ge=0.0, le=100.0)


class LineageSummary(BaseModel):
    """Aggregated lineage statistics for a patient."""

    patient_id: str = Field(..., description="Patient identifier")
    total_facts: int = Field(..., description="Total number of ClinicalFacts with lineage")
    source_distribution: list[LineageSourceDistribution] = Field(
        default_factory=list,
        description="Breakdown of facts by source type",
    )
    avg_confidence: float | None = Field(None, description="Average extraction confidence across all facts")
    extraction_methods: list[str] = Field(
        default_factory=list,
        description="Distinct extraction methods used",
    )
    earliest_record: datetime | None = Field(None, description="Earliest lineage record timestamp")
    latest_record: datetime | None = Field(None, description="Latest lineage record timestamp")
