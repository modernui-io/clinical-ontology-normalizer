"""Ancillary Study Management API endpoints.

Provides comprehensive ancillary study management: study CRUD, sample
collection & tracking, study endpoint definitions, sub-study site activation,
data sharing agreement lifecycle, study progress, and operational metrics.

Endpoints:
    GET    /ancillary-studies/                                   - List studies
    GET    /ancillary-studies/{study_id}                         - Get single study
    POST   /ancillary-studies/                                   - Create study
    PUT    /ancillary-studies/{study_id}                         - Update study
    DELETE /ancillary-studies/{study_id}                         - Delete study
    GET    /ancillary-studies/{study_id}/progress                - Get study progress
    GET    /ancillary-studies/samples                            - List samples
    GET    /ancillary-studies/samples/{sample_id}                - Get single sample
    POST   /ancillary-studies/samples                            - Collect sample
    PUT    /ancillary-studies/samples/{sample_id}                - Update sample
    POST   /ancillary-studies/samples/{sample_id}/track-analysis - Track analysis
    DELETE /ancillary-studies/samples/{sample_id}                - Delete sample
    GET    /ancillary-studies/endpoints                          - List endpoints
    GET    /ancillary-studies/endpoints/{endpoint_id}            - Get single endpoint
    POST   /ancillary-studies/endpoints                          - Create endpoint
    PUT    /ancillary-studies/endpoints/{endpoint_id}            - Update endpoint
    DELETE /ancillary-studies/endpoints/{endpoint_id}            - Delete endpoint
    GET    /ancillary-studies/sites                              - List sub-study sites
    GET    /ancillary-studies/sites/{site_record_id}             - Get single site
    POST   /ancillary-studies/sites                              - Add site
    PUT    /ancillary-studies/sites/{site_record_id}             - Update site
    POST   /ancillary-studies/sites/{site_record_id}/activate   - Activate site
    DELETE /ancillary-studies/sites/{site_record_id}             - Delete site
    GET    /ancillary-studies/agreements                         - List agreements
    GET    /ancillary-studies/agreements/{agreement_id}          - Get single agreement
    POST   /ancillary-studies/agreements                         - Create agreement
    PUT    /ancillary-studies/agreements/{agreement_id}          - Update agreement
    DELETE /ancillary-studies/agreements/{agreement_id}          - Delete agreement
    GET    /ancillary-studies/metrics                            - Operational metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.ancillary_study import (
    AgreementStatus,
    AnalysisStatus,
    AncillaryMetrics,
    AncillaryStatus,
    AncillaryStudy,
    AncillaryStudyCreate,
    AncillaryStudyListResponse,
    AncillaryStudyType,
    AncillaryStudyUpdate,
    DataSharingAgreement,
    DataSharingAgreementCreate,
    DataSharingAgreementListResponse,
    DataSharingAgreementUpdate,
    EndpointType,
    SampleType,
    StudyEndpoint,
    StudyEndpointCreate,
    StudyEndpointListResponse,
    StudyEndpointUpdate,
    StudyProgress,
    StudySample,
    StudySampleCreate,
    StudySampleListResponse,
    StudySampleUpdate,
    SubStudySite,
    SubStudySiteCreate,
    SubStudySiteListResponse,
    SubStudySiteStatus,
    SubStudySiteUpdate,
)
from app.services.ancillary_study_service import get_ancillary_study_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ancillary-studies",
    tags=["Ancillary Studies"],
)


# ---------------------------------------------------------------------------
# Study CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/",
    response_model=AncillaryStudyListResponse,
    summary="List ancillary studies",
    description="Retrieve ancillary studies with optional filtering by type, status, and parent trial.",
)
async def list_studies(
    study_type: Optional[AncillaryStudyType] = Query(
        None, description="Filter by study type"
    ),
    status: Optional[AncillaryStatus] = Query(
        None, description="Filter by status"
    ),
    parent_trial_id: Optional[str] = Query(
        None, description="Filter by parent trial ID"
    ),
) -> AncillaryStudyListResponse:
    svc = get_ancillary_study_service()
    items = svc.list_studies(
        study_type=study_type, status=status, parent_trial_id=parent_trial_id
    )
    return AncillaryStudyListResponse(items=items, total=len(items))


@router.get(
    "/{study_id}",
    response_model=AncillaryStudy,
    summary="Get an ancillary study",
)
async def get_study(study_id: str) -> AncillaryStudy:
    svc = get_ancillary_study_service()
    study = svc.get_study(study_id)
    if study is None:
        raise HTTPException(
            status_code=404, detail=f"Ancillary study '{study_id}' not found"
        )
    return study


@router.post(
    "/",
    response_model=AncillaryStudy,
    status_code=201,
    summary="Create an ancillary study",
)
async def create_study(payload: AncillaryStudyCreate) -> AncillaryStudy:
    svc = get_ancillary_study_service()
    return svc.create_study(payload)


@router.put(
    "/{study_id}",
    response_model=AncillaryStudy,
    summary="Update an ancillary study",
)
async def update_study(
    study_id: str, payload: AncillaryStudyUpdate
) -> AncillaryStudy:
    svc = get_ancillary_study_service()
    updated = svc.update_study(study_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Ancillary study '{study_id}' not found"
        )
    return updated


@router.delete(
    "/{study_id}",
    status_code=204,
    summary="Delete an ancillary study",
)
async def delete_study(study_id: str) -> None:
    svc = get_ancillary_study_service()
    deleted = svc.delete_study(study_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Ancillary study '{study_id}' not found"
        )


@router.get(
    "/{study_id}/progress",
    response_model=StudyProgress,
    summary="Get study progress",
    description="Get enrollment, sample, site, and endpoint progress for a study.",
)
async def get_study_progress(study_id: str) -> StudyProgress:
    svc = get_ancillary_study_service()
    progress = svc.get_study_progress(study_id)
    if progress is None:
        raise HTTPException(
            status_code=404, detail=f"Ancillary study '{study_id}' not found"
        )
    return progress


# ---------------------------------------------------------------------------
# Sample Management
# ---------------------------------------------------------------------------


@router.get(
    "/samples/",
    response_model=StudySampleListResponse,
    summary="List study samples",
    description="Retrieve samples with optional filtering by study, patient, site, type, and analysis status.",
)
async def list_samples(
    ancillary_study_id: Optional[str] = Query(
        None, description="Filter by ancillary study ID"
    ),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    sample_type: Optional[SampleType] = Query(
        None, description="Filter by sample type"
    ),
    analysis_status: Optional[AnalysisStatus] = Query(
        None, description="Filter by analysis status"
    ),
) -> StudySampleListResponse:
    svc = get_ancillary_study_service()
    items = svc.list_samples(
        ancillary_study_id=ancillary_study_id,
        patient_id=patient_id,
        site_id=site_id,
        sample_type=sample_type,
        analysis_status=analysis_status,
    )
    return StudySampleListResponse(items=items, total=len(items))


@router.get(
    "/samples/{sample_id}",
    response_model=StudySample,
    summary="Get a study sample",
)
async def get_sample(sample_id: str) -> StudySample:
    svc = get_ancillary_study_service()
    sample = svc.get_sample(sample_id)
    if sample is None:
        raise HTTPException(
            status_code=404, detail=f"Sample '{sample_id}' not found"
        )
    return sample


@router.post(
    "/samples/",
    response_model=StudySample,
    status_code=201,
    summary="Collect a study sample",
    description="Register a new sample collection for an ancillary study.",
)
async def collect_sample(payload: StudySampleCreate) -> StudySample:
    svc = get_ancillary_study_service()
    try:
        return svc.collect_sample(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/samples/{sample_id}",
    response_model=StudySample,
    summary="Update a study sample",
)
async def update_sample(
    sample_id: str, payload: StudySampleUpdate
) -> StudySample:
    svc = get_ancillary_study_service()
    updated = svc.update_sample(sample_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Sample '{sample_id}' not found"
        )
    return updated


@router.post(
    "/samples/{sample_id}/track-analysis",
    response_model=StudySample,
    summary="Track sample analysis",
    description="Update the analysis status and results availability for a sample.",
)
async def track_analysis(
    sample_id: str,
    analysis_status: AnalysisStatus = Query(
        ..., description="New analysis status"
    ),
    results_available: bool = Query(
        False, description="Whether results are available"
    ),
) -> StudySample:
    svc = get_ancillary_study_service()
    result = svc.track_analysis(sample_id, analysis_status, results_available)
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"Sample '{sample_id}' not found"
        )
    return result


@router.delete(
    "/samples/{sample_id}",
    status_code=204,
    summary="Delete a study sample",
)
async def delete_sample(sample_id: str) -> None:
    svc = get_ancillary_study_service()
    deleted = svc.delete_sample(sample_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Sample '{sample_id}' not found"
        )


# ---------------------------------------------------------------------------
# Endpoint Management
# ---------------------------------------------------------------------------


@router.get(
    "/endpoints/",
    response_model=StudyEndpointListResponse,
    summary="List study endpoints",
    description="Retrieve study endpoints with optional filtering by study and endpoint type.",
)
async def list_endpoints(
    ancillary_study_id: Optional[str] = Query(
        None, description="Filter by ancillary study ID"
    ),
    endpoint_type: Optional[EndpointType] = Query(
        None, description="Filter by endpoint type"
    ),
) -> StudyEndpointListResponse:
    svc = get_ancillary_study_service()
    items = svc.list_endpoints(
        ancillary_study_id=ancillary_study_id, endpoint_type=endpoint_type
    )
    return StudyEndpointListResponse(items=items, total=len(items))


@router.get(
    "/endpoints/{endpoint_id}",
    response_model=StudyEndpoint,
    summary="Get a study endpoint",
)
async def get_endpoint(endpoint_id: str) -> StudyEndpoint:
    svc = get_ancillary_study_service()
    endpoint = svc.get_endpoint(endpoint_id)
    if endpoint is None:
        raise HTTPException(
            status_code=404, detail=f"Endpoint '{endpoint_id}' not found"
        )
    return endpoint


@router.post(
    "/endpoints/",
    response_model=StudyEndpoint,
    status_code=201,
    summary="Create a study endpoint",
)
async def create_endpoint(payload: StudyEndpointCreate) -> StudyEndpoint:
    svc = get_ancillary_study_service()
    try:
        return svc.create_endpoint(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/endpoints/{endpoint_id}",
    response_model=StudyEndpoint,
    summary="Update a study endpoint",
)
async def update_endpoint(
    endpoint_id: str, payload: StudyEndpointUpdate
) -> StudyEndpoint:
    svc = get_ancillary_study_service()
    updated = svc.update_endpoint(endpoint_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Endpoint '{endpoint_id}' not found"
        )
    return updated


@router.delete(
    "/endpoints/{endpoint_id}",
    status_code=204,
    summary="Delete a study endpoint",
)
async def delete_endpoint(endpoint_id: str) -> None:
    svc = get_ancillary_study_service()
    deleted = svc.delete_endpoint(endpoint_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Endpoint '{endpoint_id}' not found"
        )


# ---------------------------------------------------------------------------
# Sub-Study Site Management
# ---------------------------------------------------------------------------


@router.get(
    "/sites/",
    response_model=SubStudySiteListResponse,
    summary="List sub-study sites",
    description="Retrieve sub-study sites with optional filtering by study and status.",
)
async def list_sites(
    ancillary_study_id: Optional[str] = Query(
        None, description="Filter by ancillary study ID"
    ),
    status: Optional[SubStudySiteStatus] = Query(
        None, description="Filter by site status"
    ),
) -> SubStudySiteListResponse:
    svc = get_ancillary_study_service()
    items = svc.list_sites(
        ancillary_study_id=ancillary_study_id, status=status
    )
    return SubStudySiteListResponse(items=items, total=len(items))


@router.get(
    "/sites/{site_record_id}",
    response_model=SubStudySite,
    summary="Get a sub-study site",
)
async def get_site(site_record_id: str) -> SubStudySite:
    svc = get_ancillary_study_service()
    site = svc.get_site(site_record_id)
    if site is None:
        raise HTTPException(
            status_code=404, detail=f"Sub-study site '{site_record_id}' not found"
        )
    return site


@router.post(
    "/sites/",
    response_model=SubStudySite,
    status_code=201,
    summary="Add a site to an ancillary study",
)
async def create_site(payload: SubStudySiteCreate) -> SubStudySite:
    svc = get_ancillary_study_service()
    try:
        return svc.create_site(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/sites/{site_record_id}",
    response_model=SubStudySite,
    summary="Update a sub-study site",
)
async def update_site(
    site_record_id: str, payload: SubStudySiteUpdate
) -> SubStudySite:
    svc = get_ancillary_study_service()
    updated = svc.update_site(site_record_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Sub-study site '{site_record_id}' not found"
        )
    return updated


@router.post(
    "/sites/{site_record_id}/activate",
    response_model=SubStudySite,
    summary="Activate a sub-study site",
    description="Activate a pending or suspended site, setting activation date and status.",
)
async def activate_site(site_record_id: str) -> SubStudySite:
    svc = get_ancillary_study_service()
    try:
        result = svc.activate_site(site_record_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"Sub-study site '{site_record_id}' not found"
        )
    return result


@router.delete(
    "/sites/{site_record_id}",
    status_code=204,
    summary="Delete a sub-study site",
)
async def delete_site(site_record_id: str) -> None:
    svc = get_ancillary_study_service()
    deleted = svc.delete_site(site_record_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Sub-study site '{site_record_id}' not found"
        )


# ---------------------------------------------------------------------------
# Data Sharing Agreements
# ---------------------------------------------------------------------------


@router.get(
    "/agreements/",
    response_model=DataSharingAgreementListResponse,
    summary="List data sharing agreements",
    description="Retrieve data sharing agreements with optional filtering by study and status.",
)
async def list_agreements(
    ancillary_study_id: Optional[str] = Query(
        None, description="Filter by ancillary study ID"
    ),
    status: Optional[AgreementStatus] = Query(
        None, description="Filter by agreement status"
    ),
) -> DataSharingAgreementListResponse:
    svc = get_ancillary_study_service()
    items = svc.list_agreements(
        ancillary_study_id=ancillary_study_id, status=status
    )
    return DataSharingAgreementListResponse(items=items, total=len(items))


@router.get(
    "/agreements/{agreement_id}",
    response_model=DataSharingAgreement,
    summary="Get a data sharing agreement",
)
async def get_agreement(agreement_id: str) -> DataSharingAgreement:
    svc = get_ancillary_study_service()
    agreement = svc.get_agreement(agreement_id)
    if agreement is None:
        raise HTTPException(
            status_code=404, detail=f"Agreement '{agreement_id}' not found"
        )
    return agreement


@router.post(
    "/agreements/",
    response_model=DataSharingAgreement,
    status_code=201,
    summary="Create a data sharing agreement",
)
async def create_agreement(
    payload: DataSharingAgreementCreate,
) -> DataSharingAgreement:
    svc = get_ancillary_study_service()
    try:
        return svc.create_agreement(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/agreements/{agreement_id}",
    response_model=DataSharingAgreement,
    summary="Update a data sharing agreement",
)
async def update_agreement(
    agreement_id: str, payload: DataSharingAgreementUpdate
) -> DataSharingAgreement:
    svc = get_ancillary_study_service()
    updated = svc.update_agreement(agreement_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Agreement '{agreement_id}' not found"
        )
    return updated


@router.delete(
    "/agreements/{agreement_id}",
    status_code=204,
    summary="Delete a data sharing agreement",
)
async def delete_agreement(agreement_id: str) -> None:
    svc = get_ancillary_study_service()
    deleted = svc.delete_agreement(agreement_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Agreement '{agreement_id}' not found"
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics/",
    response_model=AncillaryMetrics,
    summary="Get ancillary study metrics",
    description="Aggregated operational metrics across all ancillary studies.",
)
async def get_metrics() -> AncillaryMetrics:
    svc = get_ancillary_study_service()
    return svc.get_metrics()
