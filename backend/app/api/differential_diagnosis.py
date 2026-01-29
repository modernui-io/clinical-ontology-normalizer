"""Differential Diagnosis API Endpoints.

Provides clinical decision support for generating ranked
differential diagnoses based on presenting symptoms and findings.
"""

from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field, field_validator

from app.services.differential_diagnosis import (
    get_differential_diagnosis_service,
    ClinicalDomain,
)

router = APIRouter(prefix="/differential-diagnosis", tags=["Differential Diagnosis"])


# ============================================================================
# Request/Response Models
# ============================================================================


class DifferentialRequest(BaseModel):
    """Request for differential diagnosis generation."""

    findings: list[str] = Field(
        ..., min_length=1, description="List of clinical findings/symptoms"
    )
    age: int | None = Field(None, ge=0, le=150, description="Patient age")
    gender: str | None = Field(None, description="Patient gender (male/female)")
    domain: str | None = Field(None, description="Clinical domain to focus on")
    max_diagnoses: int = Field(10, ge=1, le=30, description="Maximum diagnoses to return")

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: str | None) -> str | None:
        if v is None:
            return v
        allowed = {"male", "female"}
        if v.lower() not in allowed:
            raise ValueError(
                f"Invalid gender '{v}'. Must be one of: male, female"
            )
        return v.lower()

    @field_validator("findings")
    @classmethod
    def validate_findings(cls, v: list[str]) -> list[str]:
        cleaned = [s.strip() for s in v if s.strip()]
        if not cleaned:
            raise ValueError("At least one non-empty finding is required")
        return cleaned

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "findings": ["chest pain", "shortness of breath", "diaphoresis", "ST elevation"],
                    "age": 62,
                    "gender": "male",
                    "domain": "cardiology",
                    "max_diagnoses": 10,
                }
            ]
        }
    }


class CERCitationResponse(BaseModel):
    """Claim-Evidence-Reasoning citation."""

    claim: str
    supporting_evidence: list[str]
    opposing_evidence: list[str]
    reasoning: str
    strength: str
    clinical_pearls: list[str]
    diagnostic_criteria: list[str]
    must_rule_out: list[str]


class DiagnosisCandidateResponse(BaseModel):
    """A candidate diagnosis."""

    name: str
    probability: float
    urgency: str
    domain: str
    concept_id: int | None
    cer_citation: CERCitationResponse
    suggested_workup: list[str]


class DifferentialResponse(BaseModel):
    """Response with ranked differential diagnoses."""

    request_id: str
    findings: list[str]
    total_candidates: int
    diagnoses: list[DiagnosisCandidateResponse]
    red_flags: list[str]
    suggested_history: list[str]
    suggested_exam: list[str]
    processing_time_ms: float


class DomainListResponse(BaseModel):
    """Available clinical domains."""

    domains: list[dict[str, str]]


class DiagnosisStatsResponse(BaseModel):
    """Service statistics."""

    total_diagnoses: int
    total_findings: int
    domains: dict[str, int]


# ============================================================================
# Endpoints
# ============================================================================


@router.post(
    "/generate",
    response_model=DifferentialResponse,
    summary="Generate differential diagnosis",
    description="Generate ranked differential diagnoses from clinical findings.",
)
async def generate_differential(request: DifferentialRequest) -> DifferentialResponse:
    start = time.time()
    service = get_differential_diagnosis_service()

    result = service.generate_differential(
        findings=request.findings,
        age=request.age,
        gender=request.gender,
        max_diagnoses=request.max_diagnoses,
    )

    diagnoses = []
    for d in result.differential:
        cer = CERCitationResponse(
            claim=d.cer_citation.claim if d.cer_citation else "",
            supporting_evidence=d.cer_citation.supporting_evidence if d.cer_citation else [],
            opposing_evidence=d.cer_citation.opposing_evidence if d.cer_citation else [],
            reasoning=d.cer_citation.reasoning if d.cer_citation else "",
            strength=d.cer_citation.strength.value if d.cer_citation else "weak",
            clinical_pearls=d.cer_citation.clinical_pearls if d.cer_citation else [],
            diagnostic_criteria=d.cer_citation.diagnostic_criteria if d.cer_citation else [],
            must_rule_out=d.cer_citation.must_rule_out if d.cer_citation else [],
        )
        diagnoses.append(DiagnosisCandidateResponse(
            name=d.name,
            probability=d.probability_score,
            urgency=d.urgency.value,
            domain=d.domain.value if d.domain else "unknown",
            concept_id=d.omop_concept_id,
            cer_citation=cer,
            suggested_workup=d.recommended_workup,
        ))

    return DifferentialResponse(
        request_id=str(uuid4()),
        findings=request.findings,
        total_candidates=len(diagnoses),
        diagnoses=diagnoses,
        red_flags=result.red_flag_diagnoses,
        suggested_history=result.suggested_history,
        suggested_exam=result.suggested_exam,
        processing_time_ms=(time.time() - start) * 1000,
    )


@router.get(
    "/domains",
    response_model=DomainListResponse,
    summary="List clinical domains",
)
async def list_domains() -> DomainListResponse:
    return DomainListResponse(
        domains=[
            {"value": d.value, "label": d.value.replace("_", " ").title()}
            for d in ClinicalDomain
        ]
    )


@router.get(
    "/stats",
    response_model=DiagnosisStatsResponse,
    summary="Get service statistics",
)
async def get_differential_stats() -> DiagnosisStatsResponse:
    service = get_differential_diagnosis_service()
    stats = service.get_stats()
    return DiagnosisStatsResponse(
        total_diagnoses=stats.get("total_diagnoses", 0),
        total_findings=stats.get("total_findings", 0),
        domains=stats.get("domains", {}),
    )
