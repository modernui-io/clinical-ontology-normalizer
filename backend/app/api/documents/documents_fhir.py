"""Document FHIR API endpoints - FHIR export/import."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents", "export"])


# ============================================================================
# FHIR Export Endpoints
# ============================================================================


class PatientFactRequest(BaseModel):
    """A clinical fact for summarization."""

    fact_type: str = Field(..., description="Type: condition, drug, measurement, procedure, observation")
    label: str = Field(..., description="Fact label/name")
    value: str | None = Field(None, description="Value if applicable")
    unit: str | None = Field(None, description="Unit if applicable")
    assertion: str = Field("present", description="present, absent, possible")
    temporality: str = Field("current", description="current, historical, future")
    icd10_code: str | None = Field(None, description="ICD-10 code")
    omop_concept_id: int | None = Field(None, description="OMOP concept ID")
    confidence: float = Field(1.0, description="Confidence score 0-1")


class FHIRExportRequest(BaseModel):
    """Request for FHIR export."""

    patient_id: str = Field(..., description="Patient identifier")
    facts: list[PatientFactRequest] = Field(..., description="Facts to export")
    include_patient: bool = Field(True, description="Include Patient resource")


class FHIRBundleResponse(BaseModel):
    """FHIR Bundle response."""

    bundle_id: str
    total_resources: int
    resource_types: list[str]
    fhir_json: str


@router.post(
    "/export/fhir",
    response_model=FHIRBundleResponse,
    tags=["export"],
    summary="Export facts to FHIR R4 Bundle",
)
async def export_fhir(
    request: FHIRExportRequest,
) -> FHIRBundleResponse:
    """Export clinical facts to FHIR R4 Bundle format."""
    from app.services.fhir_exporter import FHIRExporterService, ClinicalFact

    service = FHIRExporterService()

    facts = [
        ClinicalFact(
            fact_type=f.fact_type,
            label=f.label,
            value=f.value,
            unit=f.unit,
            icd10_code=f.icd10_code,
            omop_concept_id=f.omop_concept_id,
            assertion=f.assertion,
            temporality=f.temporality,
            patient_id=request.patient_id,
            confidence=f.confidence,
        )
        for f in request.facts
    ]

    bundle = service.export_facts(
        facts,
        patient_id=request.patient_id,
        include_patient=request.include_patient,
    )

    return FHIRBundleResponse(
        bundle_id=bundle.bundle_id,
        total_resources=bundle.total,
        resource_types=[e.resource_type.value for e in bundle.entries],
        fhir_json=service.to_json(bundle),
    )
