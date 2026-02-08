"""Validation Study API endpoints.

CMO-1.4: Clinical Validation Study Design

Endpoints for designing and executing clinical validation studies
that measure the system's screening accuracy against gold-standard
clinical review.

Endpoints:
    POST /api/v1/validation/studies              - Create a new study
    GET  /api/v1/validation/studies              - List all studies
    GET  /api/v1/validation/studies/{id}         - Get study detail
    POST /api/v1/validation/studies/{id}/cases   - Add a case
    GET  /api/v1/validation/studies/{id}/metrics - Compute and return metrics
    GET  /api/v1/validation/studies/{id}/report  - Full study report
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.schemas.validation_study import (
    StudyCase,
    StudyCaseCreate,
    StudyReport,
    ValidationMetrics,
    ValidationStudy,
    ValidationStudyCreate,
)
from app.services.validation_study_service import get_validation_study_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/validation", tags=["Validation Studies"])


# ==============================================================================
# Study CRUD
# ==============================================================================


@router.post(
    "/studies",
    response_model=ValidationStudy,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new validation study",
)
def create_study(body: ValidationStudyCreate) -> ValidationStudy:
    """Create a new clinical validation study.

    A validation study compares the system's automated screening results
    against a gold-standard clinical review to measure accuracy.
    """
    service = get_validation_study_service()
    return service.create_study(body)


@router.get(
    "/studies",
    response_model=list[ValidationStudy],
    summary="List all validation studies",
)
def list_studies() -> list[ValidationStudy]:
    """List all validation studies, ordered by creation time descending."""
    service = get_validation_study_service()
    return service.list_studies()


@router.get(
    "/studies/{study_id}",
    response_model=ValidationStudy,
    summary="Get study details",
)
def get_study(study_id: str) -> ValidationStudy:
    """Get a validation study by ID."""
    service = get_validation_study_service()
    study = service.get_study(study_id)
    if study is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Validation study {study_id} not found",
        )
    return study


# ==============================================================================
# Case Management
# ==============================================================================


@router.post(
    "/studies/{study_id}/cases",
    response_model=StudyCase,
    status_code=status.HTTP_201_CREATED,
    summary="Add a reviewed case to a study",
)
def add_case(study_id: str, body: StudyCaseCreate) -> StudyCase:
    """Add a case comparing system vs. gold-standard screening result.

    Automatically transitions the study from DESIGN -> IN_PROGRESS on
    the first case, and from IN_PROGRESS -> COMPLETE when the target
    sample size is reached.
    """
    service = get_validation_study_service()
    case = service.add_case(study_id, body)
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Validation study {study_id} not found",
        )
    return case


# ==============================================================================
# Metrics & Report
# ==============================================================================


@router.get(
    "/studies/{study_id}/metrics",
    response_model=ValidationMetrics,
    summary="Compute and return validation metrics",
)
def get_metrics(study_id: str) -> ValidationMetrics:
    """Compute validation metrics (sensitivity, specificity, PPV, NPV, etc.)
    for the given study.
    """
    service = get_validation_study_service()
    study = service.get_study(study_id)
    if study is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Validation study {study_id} not found",
        )
    metrics = service.compute_metrics(study_id)
    if metrics is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Validation study {study_id} not found",
        )
    return metrics


@router.get(
    "/studies/{study_id}/report",
    response_model=StudyReport,
    summary="Full study report with metrics and completion stats",
)
def get_report(study_id: str) -> StudyReport:
    """Generate a full validation study report including metrics,
    sample characteristics, completion rate, and target achievement.
    """
    service = get_validation_study_service()
    report = service.get_study_report(study_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Validation study {study_id} not found",
        )
    return report
