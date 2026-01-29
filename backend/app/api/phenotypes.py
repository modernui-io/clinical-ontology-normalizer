"""Phenotypes API Endpoints.

Provides computable phenotype evaluation for clinical decision support:
- GET /phenotypes - List all available phenotype definitions
- GET /phenotypes/{phenotype_id} - Get phenotype definition details
- POST /phenotypes/{patient_id}/evaluate/{phenotype_id} - Evaluate single phenotype
- POST /phenotypes/{patient_id}/evaluate-all - Evaluate all phenotypes for patient

Based on standards from OHDSI, PheKB, and eMERGE.
"""

import logging
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.errors import ErrorCode, NotFoundError
from app.api.middleware.auth_middleware import CurrentUser, get_current_user
from app.core.audit import AuditAction, log_data_access
from app.core.database import get_sync_engine
from app.services.phenotype_engine import (
    CareGap,
    CriterionResult,
    PhenotypeEngine,
    PhenotypeResult,
    PhenotypeStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/phenotypes", tags=["Phenotypes"])


# =============================================================================
# Response Models
# =============================================================================


class PhenotypeSummary(BaseModel):
    """Summary of a phenotype definition."""

    id: str = Field(..., description="Unique phenotype identifier")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Detailed description")
    version: str = Field(..., description="Version of the phenotype definition")
    source: str = Field(..., description="Source of the phenotype (OHDSI, PheKB, custom)")


class CriterionDetail(BaseModel):
    """Details of a criterion definition."""

    name: str
    description: str
    concept_codes: list[int]
    lookback_days: int | None = None
    min_occurrences: int = 1
    value_field: str | None = None
    value_operator: str | None = None
    value_threshold: float | list[float] | None = None


class PhenotypeDetail(BaseModel):
    """Full details of a phenotype definition."""

    id: str
    name: str
    description: str
    version: str
    source: str
    inclusion_criteria: list[CriterionDetail]
    exclusion_criteria: list[CriterionDetail]
    care_gap_criteria: list[CriterionDetail]
    inclusion_logic: str = "and"


class CriterionResultResponse(BaseModel):
    """Result of evaluating a single criterion."""

    name: str
    description: str
    met: bool
    occurrence_count: int
    most_recent_date: datetime | None = None
    value: float | None = None
    matched_concepts: list[dict[str, Any]] = Field(default_factory=list)


class CareGapResponse(BaseModel):
    """A care gap identified during phenotype evaluation."""

    name: str
    description: str
    severity: str
    recommendation: str


class PhenotypeEvaluationResponse(BaseModel):
    """Response for phenotype evaluation."""

    phenotype_id: str = Field(..., description="ID of evaluated phenotype")
    phenotype_name: str = Field(..., description="Name of evaluated phenotype")
    patient_id: str = Field(..., description="Patient identifier")
    status: str = Field(..., description="Phenotype status (present, absent, possible, insufficient_data)")
    confidence: float = Field(..., ge=0, le=1, description="Confidence in evaluation")
    inclusion_criteria_met: int = Field(..., description="Number of inclusion criteria met")
    total_inclusion_criteria: int = Field(..., description="Total inclusion criteria")
    has_care_gaps: bool = Field(..., description="Whether care gaps were identified")
    care_gaps: list[CareGapResponse] = Field(default_factory=list)
    inclusion_results: list[CriterionResultResponse] = Field(default_factory=list)
    exclusion_results: list[CriterionResultResponse] = Field(default_factory=list)
    evidence_summary: str = Field(..., description="Human-readable evidence summary")
    evaluated_at: datetime = Field(..., description="When evaluation was performed")


class BatchEvaluationResponse(BaseModel):
    """Response for batch phenotype evaluation."""

    patient_id: str
    evaluated_at: datetime
    phenotype_count: int
    present_count: int
    possible_count: int
    care_gap_count: int
    results: list[PhenotypeEvaluationResponse]


# =============================================================================
# Helper Functions
# =============================================================================


def _criterion_to_detail(criterion: Any) -> CriterionDetail:
    """Convert criterion to response model."""
    return CriterionDetail(
        name=criterion.name,
        description=criterion.description,
        concept_codes=criterion.concept_codes,
        lookback_days=criterion.lookback_days,
        min_occurrences=criterion.min_occurrences,
        value_field=criterion.value_field,
        value_operator=criterion.value_operator.value if criterion.value_operator else None,
        value_threshold=criterion.value_threshold,
    )


def _result_to_response(result: CriterionResult) -> CriterionResultResponse:
    """Convert criterion result to response model."""
    return CriterionResultResponse(
        name=result.criterion.name,
        description=result.criterion.description,
        met=result.met,
        occurrence_count=result.occurrence_count,
        most_recent_date=result.most_recent_date,
        value=result.value,
        matched_concepts=result.matched_concepts,
    )


def _care_gap_to_response(gap: CareGap) -> CareGapResponse:
    """Convert care gap to response model."""
    return CareGapResponse(
        name=gap.criterion.name,
        description=gap.description,
        severity=gap.severity,
        recommendation=gap.recommendation,
    )


def _phenotype_result_to_response(
    result: PhenotypeResult,
    phenotype_name: str,
) -> PhenotypeEvaluationResponse:
    """Convert phenotype result to response model."""
    return PhenotypeEvaluationResponse(
        phenotype_id=result.phenotype_id,
        phenotype_name=phenotype_name,
        patient_id=result.patient_id,
        status=result.status.value,
        confidence=result.confidence,
        inclusion_criteria_met=result.inclusion_criteria_met,
        total_inclusion_criteria=result.total_inclusion_criteria,
        has_care_gaps=result.has_care_gaps,
        care_gaps=[_care_gap_to_response(g) for g in result.care_gaps],
        inclusion_results=[_result_to_response(r) for r in result.inclusion_results],
        exclusion_results=[_result_to_response(r) for r in result.exclusion_results],
        evidence_summary=result.evidence_summary,
        evaluated_at=result.evaluated_at,
    )


# =============================================================================
# API Endpoints
# =============================================================================


@router.get(
    "",
    response_model=list[PhenotypeSummary],
    summary="List available phenotypes",
    description="Get a list of all registered computable phenotype definitions.",
)
def list_phenotypes(
    current_user: CurrentUser = Depends(get_current_user),
) -> list[PhenotypeSummary]:
    """List all available phenotype definitions.

    Returns:
        List of phenotype summaries with ID, name, and description.
    """
    with Session(get_sync_engine()) as session:
        engine = PhenotypeEngine(session)
        phenotypes = engine.list_phenotypes()

        return [
            PhenotypeSummary(
                id=p["id"],
                name=p["name"],
                description=p["description"],
                version=p["version"],
                source=p["source"],
            )
            for p in phenotypes
        ]


@router.get(
    "/{phenotype_id}",
    response_model=PhenotypeDetail,
    summary="Get phenotype definition",
    description="Get full details of a phenotype definition including all criteria.",
)
def get_phenotype(
    phenotype_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> PhenotypeDetail:
    """Get full details of a phenotype definition.

    Args:
        phenotype_id: The phenotype identifier.

    Returns:
        Complete phenotype definition with all criteria.

    Raises:
        NotFoundError: If phenotype is not found.
    """
    with Session(get_sync_engine()) as session:
        engine = PhenotypeEngine(session)
        phenotype = engine.get_phenotype(phenotype_id)

        if phenotype is None:
            raise NotFoundError(
                message=f"Phenotype '{phenotype_id}' not found",
                error_code=ErrorCode.NOT_FOUND,
            )

        return PhenotypeDetail(
            id=phenotype.id,
            name=phenotype.name,
            description=phenotype.description,
            version=phenotype.version,
            source=phenotype.source,
            inclusion_criteria=[_criterion_to_detail(c) for c in phenotype.inclusion_criteria],
            exclusion_criteria=[_criterion_to_detail(c) for c in phenotype.exclusion_criteria],
            care_gap_criteria=[_criterion_to_detail(c) for c in phenotype.care_gap_criteria],
            inclusion_logic=phenotype.inclusion_logic.value,
        )


@router.post(
    "/{patient_id}/evaluate/{phenotype_id}",
    response_model=PhenotypeEvaluationResponse,
    summary="Evaluate phenotype for patient",
    description="Evaluate a specific phenotype for a patient using their knowledge graph.",
)
def evaluate_phenotype(
    patient_id: str,
    phenotype_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> PhenotypeEvaluationResponse:
    """Evaluate a phenotype for a specific patient.

    Uses the patient's knowledge graph to determine if they meet
    the phenotype criteria. Also identifies care gaps for patients
    who have the phenotype.

    Args:
        patient_id: The patient identifier.
        phenotype_id: The phenotype to evaluate.

    Returns:
        Evaluation result with status, confidence, and care gaps.

    Raises:
        NotFoundError: If phenotype is not found.
    """
    # VP-Compliance-1: Log PHI access
    log_data_access(
        resource_type="phenotype_evaluation",
        resource_id=f"{patient_id}:{phenotype_id}",
        patient_id=patient_id,
        user_id=current_user.id,
        action=AuditAction.READ,
    )

    logger.info(
        f"Evaluating phenotype '{phenotype_id}' for patient '{patient_id}' "
        f"by user '{current_user.id}'"
    )

    with Session(get_sync_engine()) as session:
        engine = PhenotypeEngine(session)

        # Check if phenotype exists
        phenotype = engine.get_phenotype(phenotype_id)
        if phenotype is None:
            raise NotFoundError(
                message=f"Phenotype '{phenotype_id}' not found",
                error_code=ErrorCode.NOT_FOUND,
            )

        # Evaluate phenotype
        result = engine.evaluate(phenotype_id, patient_id)

        return _phenotype_result_to_response(result, phenotype.name)


@router.post(
    "/{patient_id}/evaluate-all",
    response_model=BatchEvaluationResponse,
    summary="Evaluate all phenotypes for patient",
    description="Evaluate all registered phenotypes for a patient.",
)
def evaluate_all_phenotypes(
    patient_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> BatchEvaluationResponse:
    """Evaluate all phenotypes for a patient.

    Evaluates every registered phenotype against the patient's
    knowledge graph. Useful for comprehensive patient assessment.

    Args:
        patient_id: The patient identifier.

    Returns:
        Batch evaluation results with all phenotype statuses.
    """
    # VP-Compliance-1: Log PHI access
    log_data_access(
        resource_type="phenotype_evaluation_all",
        resource_id=patient_id,
        patient_id=patient_id,
        user_id=current_user.id,
        action=AuditAction.READ,
    )

    logger.info(f"Evaluating all phenotypes for patient '{patient_id}' by user '{current_user.id}'")

    with Session(get_sync_engine()) as session:
        engine = PhenotypeEngine(session)
        results = engine.evaluate_all(patient_id)

        # Build response
        response_results = []
        present_count = 0
        possible_count = 0
        total_care_gaps = 0

        for result in results:
            phenotype = engine.get_phenotype(result.phenotype_id)
            phenotype_name = phenotype.name if phenotype else result.phenotype_id

            response_results.append(_phenotype_result_to_response(result, phenotype_name))

            if result.status == PhenotypeStatus.PRESENT:
                present_count += 1
            elif result.status == PhenotypeStatus.POSSIBLE:
                possible_count += 1

            total_care_gaps += len(result.care_gaps)

        return BatchEvaluationResponse(
            patient_id=patient_id,
            evaluated_at=datetime.now(timezone.utc),
            phenotype_count=len(results),
            present_count=present_count,
            possible_count=possible_count,
            care_gap_count=total_care_gaps,
            results=response_results,
        )
