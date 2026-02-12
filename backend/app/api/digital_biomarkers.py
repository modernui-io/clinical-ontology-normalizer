"""Digital Biomarkers Management (DIGI-BIO) API endpoints.

Provides comprehensive digital biomarker operations: digital endpoint definitions,
wearable data collection streams, algorithm validation, digital measure scoring,
regulatory qualification, and digital biomarker operational metrics.

Endpoints:
    GET    /digital-biomarkers/endpoints                           - List endpoints
    GET    /digital-biomarkers/endpoints/{endpoint_id}             - Get single endpoint
    POST   /digital-biomarkers/endpoints                           - Create endpoint
    PUT    /digital-biomarkers/endpoints/{endpoint_id}             - Update endpoint
    DELETE /digital-biomarkers/endpoints/{endpoint_id}             - Delete endpoint
    GET    /digital-biomarkers/streams                             - List data streams
    GET    /digital-biomarkers/streams/{stream_id}                 - Get single stream
    POST   /digital-biomarkers/streams                             - Create stream
    PUT    /digital-biomarkers/streams/{stream_id}                 - Update stream
    DELETE /digital-biomarkers/streams/{stream_id}                 - Delete stream
    GET    /digital-biomarkers/algorithms                          - List algorithms
    GET    /digital-biomarkers/algorithms/{algorithm_id}           - Get single algorithm
    POST   /digital-biomarkers/algorithms                          - Create algorithm
    PUT    /digital-biomarkers/algorithms/{algorithm_id}           - Update algorithm
    DELETE /digital-biomarkers/algorithms/{algorithm_id}           - Delete algorithm
    GET    /digital-biomarkers/scores                              - List scores
    GET    /digital-biomarkers/scores/{score_id}                   - Get single score
    POST   /digital-biomarkers/scores                              - Create score
    PUT    /digital-biomarkers/scores/{score_id}                   - Update score
    DELETE /digital-biomarkers/scores/{score_id}                   - Delete score
    GET    /digital-biomarkers/qualifications                      - List qualifications
    GET    /digital-biomarkers/qualifications/{qualification_id}   - Get single qualification
    POST   /digital-biomarkers/qualifications                      - Create qualification
    PUT    /digital-biomarkers/qualifications/{qualification_id}   - Update qualification
    DELETE /digital-biomarkers/qualifications/{qualification_id}   - Delete qualification
    GET    /digital-biomarkers/metrics                             - Digital biomarker metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.digital_biomarkers import (
    AlgorithmValidation,
    AlgorithmValidationCreate,
    AlgorithmValidationListResponse,
    AlgorithmValidationUpdate,
    DataStream,
    DataStreamCreate,
    DataStreamListResponse,
    DataStreamUpdate,
    DigitalBiomarkerMetrics,
    DigitalEndpoint,
    DigitalEndpointCreate,
    DigitalEndpointListResponse,
    DigitalEndpointUpdate,
    DigitalMeasureScore,
    DigitalMeasureScoreCreate,
    DigitalMeasureScoreListResponse,
    DigitalMeasureScoreUpdate,
    RegulatoryQualification,
    RegulatoryQualificationCreate,
    RegulatoryQualificationListResponse,
    RegulatoryQualificationUpdate,
)
from app.services.digital_biomarkers_service import get_digital_biomarkers_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/digital-biomarkers",
    tags=["Digital Biomarkers"],
)


# ---------------------------------------------------------------------------
# Digital Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/endpoints",
    response_model=DigitalEndpointListResponse,
    summary="List Digital Endpoints",
    description="Retrieve digital endpoints with optional filtering by trial_id.",
)
async def list_endpoints(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> DigitalEndpointListResponse:
    svc = get_digital_biomarkers_service()
    items = svc.list_endpoints(trial_id=trial_id)
    return DigitalEndpointListResponse(items=items, total=len(items))


@router.get(
    "/endpoints/{endpoint_id}",
    response_model=DigitalEndpoint,
    summary="Get a Digital Endpoint",
)
async def get_endpoint(endpoint_id: str) -> DigitalEndpoint:
    svc = get_digital_biomarkers_service()
    ep = svc.get_endpoint(endpoint_id)
    if ep is None:
        raise HTTPException(status_code=404, detail=f"Endpoint '{endpoint_id}' not found")
    return ep


@router.post(
    "/endpoints",
    response_model=DigitalEndpoint,
    status_code=201,
    summary="Create a Digital Endpoint",
)
async def create_endpoint(payload: DigitalEndpointCreate) -> DigitalEndpoint:
    svc = get_digital_biomarkers_service()
    return svc.create_endpoint(payload)


@router.put(
    "/endpoints/{endpoint_id}",
    response_model=DigitalEndpoint,
    summary="Update a Digital Endpoint",
)
async def update_endpoint(endpoint_id: str, payload: DigitalEndpointUpdate) -> DigitalEndpoint:
    svc = get_digital_biomarkers_service()
    updated = svc.update_endpoint(endpoint_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Endpoint '{endpoint_id}' not found")
    return updated


@router.delete(
    "/endpoints/{endpoint_id}",
    status_code=204,
    summary="Delete a Digital Endpoint",
)
async def delete_endpoint(endpoint_id: str) -> None:
    svc = get_digital_biomarkers_service()
    if not svc.delete_endpoint(endpoint_id):
        raise HTTPException(status_code=404, detail=f"Endpoint '{endpoint_id}' not found")


# ---------------------------------------------------------------------------
# Data Streams
# ---------------------------------------------------------------------------


@router.get(
    "/streams",
    response_model=DataStreamListResponse,
    summary="List Data Streams",
    description="Retrieve data streams with optional filtering by trial_id and endpoint_id.",
)
async def list_streams(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    endpoint_id: Optional[str] = Query(None, description="Filter by endpoint ID"),
) -> DataStreamListResponse:
    svc = get_digital_biomarkers_service()
    items = svc.list_streams(trial_id=trial_id, endpoint_id=endpoint_id)
    return DataStreamListResponse(items=items, total=len(items))


@router.get(
    "/streams/{stream_id}",
    response_model=DataStream,
    summary="Get a Data Stream",
)
async def get_stream(stream_id: str) -> DataStream:
    svc = get_digital_biomarkers_service()
    stream = svc.get_stream(stream_id)
    if stream is None:
        raise HTTPException(status_code=404, detail=f"Stream '{stream_id}' not found")
    return stream


@router.post(
    "/streams",
    response_model=DataStream,
    status_code=201,
    summary="Create a Data Stream",
)
async def create_stream(payload: DataStreamCreate) -> DataStream:
    svc = get_digital_biomarkers_service()
    return svc.create_stream(payload)


@router.put(
    "/streams/{stream_id}",
    response_model=DataStream,
    summary="Update a Data Stream",
)
async def update_stream(stream_id: str, payload: DataStreamUpdate) -> DataStream:
    svc = get_digital_biomarkers_service()
    updated = svc.update_stream(stream_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Stream '{stream_id}' not found")
    return updated


@router.delete(
    "/streams/{stream_id}",
    status_code=204,
    summary="Delete a Data Stream",
)
async def delete_stream(stream_id: str) -> None:
    svc = get_digital_biomarkers_service()
    if not svc.delete_stream(stream_id):
        raise HTTPException(status_code=404, detail=f"Stream '{stream_id}' not found")


# ---------------------------------------------------------------------------
# Algorithm Validations
# ---------------------------------------------------------------------------


@router.get(
    "/algorithms",
    response_model=AlgorithmValidationListResponse,
    summary="List Algorithm Validations",
    description="Retrieve algorithm validations with optional filtering by endpoint_id.",
)
async def list_algorithms(
    endpoint_id: Optional[str] = Query(None, description="Filter by endpoint ID"),
) -> AlgorithmValidationListResponse:
    svc = get_digital_biomarkers_service()
    items = svc.list_algorithms(endpoint_id=endpoint_id)
    return AlgorithmValidationListResponse(items=items, total=len(items))


@router.get(
    "/algorithms/{algorithm_id}",
    response_model=AlgorithmValidation,
    summary="Get an Algorithm Validation",
)
async def get_algorithm(algorithm_id: str) -> AlgorithmValidation:
    svc = get_digital_biomarkers_service()
    algo = svc.get_algorithm(algorithm_id)
    if algo is None:
        raise HTTPException(status_code=404, detail=f"Algorithm '{algorithm_id}' not found")
    return algo


@router.post(
    "/algorithms",
    response_model=AlgorithmValidation,
    status_code=201,
    summary="Create an Algorithm Validation",
)
async def create_algorithm(payload: AlgorithmValidationCreate) -> AlgorithmValidation:
    svc = get_digital_biomarkers_service()
    return svc.create_algorithm(payload)


@router.put(
    "/algorithms/{algorithm_id}",
    response_model=AlgorithmValidation,
    summary="Update an Algorithm Validation",
)
async def update_algorithm(algorithm_id: str, payload: AlgorithmValidationUpdate) -> AlgorithmValidation:
    svc = get_digital_biomarkers_service()
    updated = svc.update_algorithm(algorithm_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Algorithm '{algorithm_id}' not found")
    return updated


@router.delete(
    "/algorithms/{algorithm_id}",
    status_code=204,
    summary="Delete an Algorithm Validation",
)
async def delete_algorithm(algorithm_id: str) -> None:
    svc = get_digital_biomarkers_service()
    if not svc.delete_algorithm(algorithm_id):
        raise HTTPException(status_code=404, detail=f"Algorithm '{algorithm_id}' not found")


# ---------------------------------------------------------------------------
# Digital Measure Scores
# ---------------------------------------------------------------------------


@router.get(
    "/scores",
    response_model=DigitalMeasureScoreListResponse,
    summary="List Digital Measure Scores",
    description="Retrieve digital measure scores with optional filtering by trial_id and endpoint_id.",
)
async def list_scores(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    endpoint_id: Optional[str] = Query(None, description="Filter by endpoint ID"),
) -> DigitalMeasureScoreListResponse:
    svc = get_digital_biomarkers_service()
    items = svc.list_scores(trial_id=trial_id, endpoint_id=endpoint_id)
    return DigitalMeasureScoreListResponse(items=items, total=len(items))


@router.get(
    "/scores/{score_id}",
    response_model=DigitalMeasureScore,
    summary="Get a Digital Measure Score",
)
async def get_score(score_id: str) -> DigitalMeasureScore:
    svc = get_digital_biomarkers_service()
    score = svc.get_score(score_id)
    if score is None:
        raise HTTPException(status_code=404, detail=f"Score '{score_id}' not found")
    return score


@router.post(
    "/scores",
    response_model=DigitalMeasureScore,
    status_code=201,
    summary="Create a Digital Measure Score",
)
async def create_score(payload: DigitalMeasureScoreCreate) -> DigitalMeasureScore:
    svc = get_digital_biomarkers_service()
    return svc.create_score(payload)


@router.put(
    "/scores/{score_id}",
    response_model=DigitalMeasureScore,
    summary="Update a Digital Measure Score",
)
async def update_score(score_id: str, payload: DigitalMeasureScoreUpdate) -> DigitalMeasureScore:
    svc = get_digital_biomarkers_service()
    updated = svc.update_score(score_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Score '{score_id}' not found")
    return updated


@router.delete(
    "/scores/{score_id}",
    status_code=204,
    summary="Delete a Digital Measure Score",
)
async def delete_score(score_id: str) -> None:
    svc = get_digital_biomarkers_service()
    if not svc.delete_score(score_id):
        raise HTTPException(status_code=404, detail=f"Score '{score_id}' not found")


# ---------------------------------------------------------------------------
# Regulatory Qualifications
# ---------------------------------------------------------------------------


@router.get(
    "/qualifications",
    response_model=RegulatoryQualificationListResponse,
    summary="List Regulatory Qualifications",
    description="Retrieve regulatory qualifications with optional filtering by endpoint_id.",
)
async def list_qualifications(
    endpoint_id: Optional[str] = Query(None, description="Filter by endpoint ID"),
) -> RegulatoryQualificationListResponse:
    svc = get_digital_biomarkers_service()
    items = svc.list_qualifications(endpoint_id=endpoint_id)
    return RegulatoryQualificationListResponse(items=items, total=len(items))


@router.get(
    "/qualifications/{qualification_id}",
    response_model=RegulatoryQualification,
    summary="Get a Regulatory Qualification",
)
async def get_qualification(qualification_id: str) -> RegulatoryQualification:
    svc = get_digital_biomarkers_service()
    qual = svc.get_qualification(qualification_id)
    if qual is None:
        raise HTTPException(status_code=404, detail=f"Qualification '{qualification_id}' not found")
    return qual


@router.post(
    "/qualifications",
    response_model=RegulatoryQualification,
    status_code=201,
    summary="Create a Regulatory Qualification",
)
async def create_qualification(payload: RegulatoryQualificationCreate) -> RegulatoryQualification:
    svc = get_digital_biomarkers_service()
    return svc.create_qualification(payload)


@router.put(
    "/qualifications/{qualification_id}",
    response_model=RegulatoryQualification,
    summary="Update a Regulatory Qualification",
)
async def update_qualification(
    qualification_id: str, payload: RegulatoryQualificationUpdate
) -> RegulatoryQualification:
    svc = get_digital_biomarkers_service()
    updated = svc.update_qualification(qualification_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Qualification '{qualification_id}' not found")
    return updated


@router.delete(
    "/qualifications/{qualification_id}",
    status_code=204,
    summary="Delete a Regulatory Qualification",
)
async def delete_qualification(qualification_id: str) -> None:
    svc = get_digital_biomarkers_service()
    if not svc.delete_qualification(qualification_id):
        raise HTTPException(status_code=404, detail=f"Qualification '{qualification_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=DigitalBiomarkerMetrics,
    summary="Digital Biomarker Metrics",
    description="Get aggregated digital biomarker operational metrics across all entities.",
)
async def get_metrics() -> DigitalBiomarkerMetrics:
    svc = get_digital_biomarkers_service()
    return svc.get_metrics()
