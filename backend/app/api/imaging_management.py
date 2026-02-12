"""Clinical Imaging Management API endpoints (IMG-MGMT).

Provides comprehensive imaging management operations: imaging study definitions,
image acquisition tracking, central reader assignments, RECIST/disease assessments,
reader training/qualification, image quality reviews, and imaging metrics.

Endpoints:
    GET    /imaging-management/studies                        - List imaging studies
    GET    /imaging-management/studies/{study_id}             - Get single study
    POST   /imaging-management/studies                        - Create study
    PUT    /imaging-management/studies/{study_id}             - Update study
    DELETE /imaging-management/studies/{study_id}             - Delete study
    GET    /imaging-management/acquisitions                   - List acquisitions
    GET    /imaging-management/acquisitions/{acquisition_id}  - Get single acquisition
    POST   /imaging-management/acquisitions                   - Create acquisition
    PUT    /imaging-management/acquisitions/{acquisition_id}  - Update acquisition
    DELETE /imaging-management/acquisitions/{acquisition_id}  - Delete acquisition
    GET    /imaging-management/readers                        - List central readers
    GET    /imaging-management/readers/{reader_id}            - Get single reader
    POST   /imaging-management/readers                        - Create reader
    PUT    /imaging-management/readers/{reader_id}            - Update reader
    DELETE /imaging-management/readers/{reader_id}            - Delete reader
    GET    /imaging-management/assessments                    - List assessments
    GET    /imaging-management/assessments/{assessment_id}    - Get single assessment
    POST   /imaging-management/assessments                    - Create assessment
    DELETE /imaging-management/assessments/{assessment_id}    - Delete assessment
    GET    /imaging-management/qc-reviews                     - List QC reviews
    GET    /imaging-management/qc-reviews/{qc_id}             - Get single QC review
    POST   /imaging-management/qc-reviews                     - Create QC review
    DELETE /imaging-management/qc-reviews/{qc_id}             - Delete QC review
    GET    /imaging-management/metrics                        - Imaging metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.imaging_management import (
    AssessmentCriteria,
    CentralReader,
    CentralReaderCreate,
    CentralReaderListResponse,
    CentralReaderUpdate,
    DiseaseAssessment,
    DiseaseAssessmentCreate,
    DiseaseAssessmentListResponse,
    ImageAcquisition,
    ImageAcquisitionCreate,
    ImageAcquisitionListResponse,
    ImageAcquisitionUpdate,
    ImageQualityReview,
    ImageQualityReviewCreate,
    ImageQualityReviewListResponse,
    ImageStatus,
    ImagingManagementMetrics,
    ImagingModality,
    ImagingStudy,
    ImagingStudyCreate,
    ImagingStudyListResponse,
    ImagingStudyUpdate,
    QCOutcome,
    QualificationStatus,
)
from app.services.imaging_management_service import get_imaging_management_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/imaging-management",
    tags=["Imaging Management"],
)


# ---------------------------------------------------------------------------
# Imaging Studies
# ---------------------------------------------------------------------------


@router.get(
    "/studies",
    response_model=ImagingStudyListResponse,
    summary="List imaging studies",
    description="Retrieve imaging studies with optional filtering by trial, modality, and assessment criteria.",
)
async def list_studies(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    modality: Optional[ImagingModality] = Query(None, description="Filter by imaging modality"),
    criteria: Optional[AssessmentCriteria] = Query(None, description="Filter by assessment criteria"),
) -> ImagingStudyListResponse:
    svc = get_imaging_management_service()
    items = svc.list_studies(trial_id=trial_id, modality=modality, criteria=criteria)
    return ImagingStudyListResponse(items=items, total=len(items))


@router.get(
    "/studies/{study_id}",
    response_model=ImagingStudy,
    summary="Get an imaging study",
)
async def get_study(study_id: str) -> ImagingStudy:
    svc = get_imaging_management_service()
    study = svc.get_study(study_id)
    if study is None:
        raise HTTPException(status_code=404, detail=f"Imaging study '{study_id}' not found")
    return study


@router.post(
    "/studies",
    response_model=ImagingStudy,
    status_code=201,
    summary="Create an imaging study",
)
async def create_study(payload: ImagingStudyCreate) -> ImagingStudy:
    svc = get_imaging_management_service()
    return svc.create_study(payload)


@router.put(
    "/studies/{study_id}",
    response_model=ImagingStudy,
    summary="Update an imaging study",
)
async def update_study(study_id: str, payload: ImagingStudyUpdate) -> ImagingStudy:
    svc = get_imaging_management_service()
    updated = svc.update_study(study_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Imaging study '{study_id}' not found")
    return updated


@router.delete(
    "/studies/{study_id}",
    status_code=204,
    summary="Delete an imaging study",
)
async def delete_study(study_id: str) -> None:
    svc = get_imaging_management_service()
    deleted = svc.delete_study(study_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Imaging study '{study_id}' not found")


# ---------------------------------------------------------------------------
# Image Acquisitions
# ---------------------------------------------------------------------------


@router.get(
    "/acquisitions",
    response_model=ImageAcquisitionListResponse,
    summary="List image acquisitions",
    description="Retrieve image acquisitions with optional filtering by study, modality, and status.",
)
async def list_acquisitions(
    study_id: Optional[str] = Query(None, description="Filter by study ID"),
    modality: Optional[ImagingModality] = Query(None, description="Filter by imaging modality"),
    status: Optional[ImageStatus] = Query(None, description="Filter by acquisition status"),
) -> ImageAcquisitionListResponse:
    svc = get_imaging_management_service()
    items = svc.list_acquisitions(study_id=study_id, modality=modality, status=status)
    return ImageAcquisitionListResponse(items=items, total=len(items))


@router.get(
    "/acquisitions/{acquisition_id}",
    response_model=ImageAcquisition,
    summary="Get an image acquisition",
)
async def get_acquisition(acquisition_id: str) -> ImageAcquisition:
    svc = get_imaging_management_service()
    acq = svc.get_acquisition(acquisition_id)
    if acq is None:
        raise HTTPException(status_code=404, detail=f"Image acquisition '{acquisition_id}' not found")
    return acq


@router.post(
    "/acquisitions",
    response_model=ImageAcquisition,
    status_code=201,
    summary="Create an image acquisition",
)
async def create_acquisition(payload: ImageAcquisitionCreate) -> ImageAcquisition:
    svc = get_imaging_management_service()
    return svc.create_acquisition(payload)


@router.put(
    "/acquisitions/{acquisition_id}",
    response_model=ImageAcquisition,
    summary="Update an image acquisition",
)
async def update_acquisition(acquisition_id: str, payload: ImageAcquisitionUpdate) -> ImageAcquisition:
    svc = get_imaging_management_service()
    updated = svc.update_acquisition(acquisition_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Image acquisition '{acquisition_id}' not found")
    return updated


@router.delete(
    "/acquisitions/{acquisition_id}",
    status_code=204,
    summary="Delete an image acquisition",
)
async def delete_acquisition(acquisition_id: str) -> None:
    svc = get_imaging_management_service()
    deleted = svc.delete_acquisition(acquisition_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Image acquisition '{acquisition_id}' not found")


# ---------------------------------------------------------------------------
# Central Readers
# ---------------------------------------------------------------------------


@router.get(
    "/readers",
    response_model=CentralReaderListResponse,
    summary="List central readers",
    description="Retrieve central readers with optional filtering by qualification status and modality.",
)
async def list_readers(
    qualification_status: Optional[QualificationStatus] = Query(None, description="Filter by qualification status"),
    modality: Optional[ImagingModality] = Query(None, description="Filter by qualified modality"),
) -> CentralReaderListResponse:
    svc = get_imaging_management_service()
    items = svc.list_readers(qualification_status=qualification_status, modality=modality)
    return CentralReaderListResponse(items=items, total=len(items))


@router.get(
    "/readers/{reader_id}",
    response_model=CentralReader,
    summary="Get a central reader",
)
async def get_reader(reader_id: str) -> CentralReader:
    svc = get_imaging_management_service()
    reader = svc.get_reader(reader_id)
    if reader is None:
        raise HTTPException(status_code=404, detail=f"Central reader '{reader_id}' not found")
    return reader


@router.post(
    "/readers",
    response_model=CentralReader,
    status_code=201,
    summary="Create a central reader",
)
async def create_reader(payload: CentralReaderCreate) -> CentralReader:
    svc = get_imaging_management_service()
    return svc.create_reader(payload)


@router.put(
    "/readers/{reader_id}",
    response_model=CentralReader,
    summary="Update a central reader",
)
async def update_reader(reader_id: str, payload: CentralReaderUpdate) -> CentralReader:
    svc = get_imaging_management_service()
    updated = svc.update_reader(reader_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Central reader '{reader_id}' not found")
    return updated


@router.delete(
    "/readers/{reader_id}",
    status_code=204,
    summary="Delete a central reader",
)
async def delete_reader(reader_id: str) -> None:
    svc = get_imaging_management_service()
    deleted = svc.delete_reader(reader_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Central reader '{reader_id}' not found")


# ---------------------------------------------------------------------------
# Disease Assessments
# ---------------------------------------------------------------------------


@router.get(
    "/assessments",
    response_model=DiseaseAssessmentListResponse,
    summary="List disease assessments",
    description="Retrieve disease assessments with optional filtering by acquisition, reader, and criteria.",
)
async def list_assessments(
    acquisition_id: Optional[str] = Query(None, description="Filter by acquisition ID"),
    reader_id: Optional[str] = Query(None, description="Filter by reader ID"),
    criteria: Optional[AssessmentCriteria] = Query(None, description="Filter by assessment criteria"),
) -> DiseaseAssessmentListResponse:
    svc = get_imaging_management_service()
    items = svc.list_assessments(acquisition_id=acquisition_id, reader_id=reader_id, criteria=criteria)
    return DiseaseAssessmentListResponse(items=items, total=len(items))


@router.get(
    "/assessments/{assessment_id}",
    response_model=DiseaseAssessment,
    summary="Get a disease assessment",
)
async def get_assessment(assessment_id: str) -> DiseaseAssessment:
    svc = get_imaging_management_service()
    assessment = svc.get_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail=f"Disease assessment '{assessment_id}' not found")
    return assessment


@router.post(
    "/assessments",
    response_model=DiseaseAssessment,
    status_code=201,
    summary="Create a disease assessment",
)
async def create_assessment(payload: DiseaseAssessmentCreate) -> DiseaseAssessment:
    svc = get_imaging_management_service()
    return svc.create_assessment(payload)


@router.delete(
    "/assessments/{assessment_id}",
    status_code=204,
    summary="Delete a disease assessment",
)
async def delete_assessment(assessment_id: str) -> None:
    svc = get_imaging_management_service()
    deleted = svc.delete_assessment(assessment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Disease assessment '{assessment_id}' not found")


# ---------------------------------------------------------------------------
# Image Quality Reviews
# ---------------------------------------------------------------------------


@router.get(
    "/qc-reviews",
    response_model=ImageQualityReviewListResponse,
    summary="List image quality reviews",
    description="Retrieve QC reviews with optional filtering by acquisition and outcome.",
)
async def list_qc_reviews(
    acquisition_id: Optional[str] = Query(None, description="Filter by acquisition ID"),
    outcome: Optional[QCOutcome] = Query(None, description="Filter by QC outcome"),
) -> ImageQualityReviewListResponse:
    svc = get_imaging_management_service()
    items = svc.list_qc_reviews(acquisition_id=acquisition_id, outcome=outcome)
    return ImageQualityReviewListResponse(items=items, total=len(items))


@router.get(
    "/qc-reviews/{qc_id}",
    response_model=ImageQualityReview,
    summary="Get an image quality review",
)
async def get_qc_review(qc_id: str) -> ImageQualityReview:
    svc = get_imaging_management_service()
    qc = svc.get_qc_review(qc_id)
    if qc is None:
        raise HTTPException(status_code=404, detail=f"QC review '{qc_id}' not found")
    return qc


@router.post(
    "/qc-reviews",
    response_model=ImageQualityReview,
    status_code=201,
    summary="Create an image quality review",
)
async def create_qc_review(payload: ImageQualityReviewCreate) -> ImageQualityReview:
    svc = get_imaging_management_service()
    return svc.create_qc_review(payload)


@router.delete(
    "/qc-reviews/{qc_id}",
    status_code=204,
    summary="Delete an image quality review",
)
async def delete_qc_review(qc_id: str) -> None:
    svc = get_imaging_management_service()
    deleted = svc.delete_qc_review(qc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"QC review '{qc_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=ImagingManagementMetrics,
    summary="Get imaging management metrics",
    description="Aggregated imaging management metrics across all studies, acquisitions, readers, assessments, and QC reviews.",
)
async def get_metrics() -> ImagingManagementMetrics:
    svc = get_imaging_management_service()
    return svc.get_metrics()
