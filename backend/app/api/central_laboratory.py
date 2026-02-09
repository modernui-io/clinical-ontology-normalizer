"""Central Laboratory Management API endpoints (CLINICAL-8).

Provides comprehensive central lab operations: lab test definitions, kit
inventory and assignment, sample lifecycle (registration, receipt, rejection),
result submission with auto-flagging and reference range evaluation, critical
value alerting and acknowledgment, sample shipment tracking, turnaround time
analysis, rejection analysis, and lab metrics dashboard.

Endpoints:
    GET    /central-laboratory/tests                              - List lab tests
    GET    /central-laboratory/tests/{test_id}                    - Get single lab test
    POST   /central-laboratory/tests                              - Create lab test
    PUT    /central-laboratory/tests/{test_id}                    - Update lab test
    DELETE /central-laboratory/tests/{test_id}                    - Delete lab test
    GET    /central-laboratory/kits                               - List lab kits
    GET    /central-laboratory/kits/{kit_id}                      - Get single kit
    POST   /central-laboratory/kits/assign                        - Assign kits to site
    GET    /central-laboratory/kits/inventory-summary             - Kit inventory summary
    GET    /central-laboratory/samples                            - List samples
    GET    /central-laboratory/samples/{sample_id}                - Get single sample
    GET    /central-laboratory/samples/{sample_id}/with-results   - Get sample with results
    POST   /central-laboratory/samples/register                   - Register new sample
    POST   /central-laboratory/samples/{sample_id}/receive        - Receive sample at lab
    POST   /central-laboratory/samples/{sample_id}/reject         - Reject sample
    GET    /central-laboratory/results                            - List results
    GET    /central-laboratory/results/{result_id}                - Get single result
    POST   /central-laboratory/results/submit                     - Submit batch results
    GET    /central-laboratory/patients/{patient_id}/results      - Patient result history
    GET    /central-laboratory/alerts                             - List critical value alerts
    POST   /central-laboratory/alerts/{alert_id}/acknowledge      - Acknowledge alert
    GET    /central-laboratory/shipments                          - List shipments
    GET    /central-laboratory/shipments/{shipment_id}            - Get single shipment
    POST   /central-laboratory/shipments                          - Create shipment
    GET    /central-laboratory/metrics                            - Lab metrics dashboard
    GET    /central-laboratory/turnaround-analysis                - TAT analysis by category
    GET    /central-laboratory/rejection-analysis                 - Rejection analysis
    GET    /central-laboratory/query-suggestions                  - Auto-query suggestions
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.central_laboratory import (
    AlertAcknowledgeRequest,
    CriticalValueAlert,
    CriticalValueAlertListResponse,
    KitAssignRequest,
    KitStatus,
    LabKit,
    LabKitListResponse,
    LabMetrics,
    LabResult,
    LabResultListResponse,
    LabTest,
    LabTestCategory,
    LabTestCreate,
    LabTestListResponse,
    LabTestUpdate,
    ResultBatchSubmitRequest,
    ResultFlag,
    ResultStatus,
    Sample,
    SampleListResponse,
    SampleReceiveRequest,
    SampleRegisterRequest,
    SampleRejectRequest,
    SampleShipment,
    SampleStatus,
    SampleType,
    SampleWithResults,
    ShipmentCreateRequest,
    ShipmentListResponse,
    TurnaroundTimeAnalysis,
)
from app.services.central_laboratory_service import get_central_lab_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/central-laboratory",
    tags=["Central Laboratory"],
)


# ---------------------------------------------------------------------------
# Lab Test CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/tests",
    response_model=LabTestListResponse,
    summary="List lab test definitions",
    description="Retrieve lab tests with optional filtering by category and specimen type.",
)
async def list_tests(
    category: Optional[LabTestCategory] = Query(None, description="Filter by test category"),
    specimen_type: Optional[SampleType] = Query(None, description="Filter by specimen type"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> LabTestListResponse:
    svc = get_central_lab_service()
    items, total = svc.list_tests(
        category=category, specimen_type=specimen_type, limit=limit, offset=offset
    )
    return LabTestListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/tests/{test_id}",
    response_model=LabTest,
    summary="Get a lab test definition",
)
async def get_test(test_id: str) -> LabTest:
    svc = get_central_lab_service()
    test = svc.get_test(test_id)
    if test is None:
        raise HTTPException(status_code=404, detail=f"Lab test '{test_id}' not found")
    return test


@router.post(
    "/tests",
    response_model=LabTest,
    status_code=201,
    summary="Create a lab test definition",
)
async def create_test(payload: LabTestCreate) -> LabTest:
    svc = get_central_lab_service()
    return svc.create_test(payload)


@router.put(
    "/tests/{test_id}",
    response_model=LabTest,
    summary="Update a lab test definition",
)
async def update_test(test_id: str, payload: LabTestUpdate) -> LabTest:
    svc = get_central_lab_service()
    updated = svc.update_test(test_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Lab test '{test_id}' not found")
    return updated


@router.delete(
    "/tests/{test_id}",
    status_code=204,
    summary="Delete a lab test definition",
)
async def delete_test(test_id: str) -> None:
    svc = get_central_lab_service()
    deleted = svc.delete_test(test_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Lab test '{test_id}' not found")


# ---------------------------------------------------------------------------
# Kit Management
# ---------------------------------------------------------------------------


@router.get(
    "/kits",
    response_model=LabKitListResponse,
    summary="List lab kits",
    description="Retrieve lab kits with optional filtering by site and status.",
)
async def list_kits(
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    status: Optional[KitStatus] = Query(None, description="Filter by kit status"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> LabKitListResponse:
    svc = get_central_lab_service()
    items, total = svc.list_kits(site_id=site_id, status=status, limit=limit, offset=offset)
    return LabKitListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/kits/inventory-summary",
    summary="Get kit inventory summary",
    description="Retrieve a summary of kit inventory by status and site, including kits expiring within 30 days.",
)
async def get_kit_inventory_summary() -> dict[str, Any]:
    svc = get_central_lab_service()
    return svc.get_kit_inventory_summary()


@router.get(
    "/kits/{kit_id}",
    response_model=LabKit,
    summary="Get a lab kit",
)
async def get_kit(kit_id: str) -> LabKit:
    svc = get_central_lab_service()
    kit = svc.get_kit(kit_id)
    if kit is None:
        raise HTTPException(status_code=404, detail=f"Kit '{kit_id}' not found")
    return kit


@router.post(
    "/kits/assign",
    response_model=list[LabKit],
    summary="Assign kits to a site",
    description="Assign one or more available kits to a specific site.",
)
async def assign_kits(payload: KitAssignRequest) -> list[LabKit]:
    svc = get_central_lab_service()
    return svc.assign_kits(payload)


# ---------------------------------------------------------------------------
# Sample Management
# ---------------------------------------------------------------------------


@router.get(
    "/samples",
    response_model=SampleListResponse,
    summary="List samples",
    description="Retrieve samples with optional filtering by site, patient, status, and specimen type.",
)
async def list_samples(
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    status: Optional[SampleStatus] = Query(None, description="Filter by sample status"),
    sample_type: Optional[SampleType] = Query(None, description="Filter by specimen type"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> SampleListResponse:
    svc = get_central_lab_service()
    items, total = svc.list_samples(
        site_id=site_id,
        patient_id=patient_id,
        status=status,
        sample_type=sample_type,
        limit=limit,
        offset=offset,
    )
    return SampleListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/samples/{sample_id}",
    response_model=Sample,
    summary="Get a sample",
)
async def get_sample(sample_id: str) -> Sample:
    svc = get_central_lab_service()
    sample = svc.get_sample(sample_id)
    if sample is None:
        raise HTTPException(status_code=404, detail=f"Sample '{sample_id}' not found")
    return sample


@router.get(
    "/samples/{sample_id}/with-results",
    response_model=SampleWithResults,
    summary="Get a sample with its results",
    description="Retrieve a sample along with all associated lab results.",
)
async def get_sample_with_results(sample_id: str) -> SampleWithResults:
    svc = get_central_lab_service()
    result = svc.get_sample_with_results(sample_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Sample '{sample_id}' not found")
    sample, results = result
    return SampleWithResults(sample=sample, results=results)


@router.post(
    "/samples/register",
    response_model=Sample,
    status_code=201,
    summary="Register a new sample",
    description="Register a new sample collection. Optionally marks the kit as used.",
)
async def register_sample(payload: SampleRegisterRequest) -> Sample:
    svc = get_central_lab_service()
    return svc.register_sample(payload)


@router.post(
    "/samples/{sample_id}/receive",
    response_model=Sample,
    summary="Receive a sample at central lab",
    description="Mark a collected or in-transit sample as received at the central laboratory.",
)
async def receive_sample(sample_id: str, payload: SampleReceiveRequest) -> Sample:
    svc = get_central_lab_service()
    updated = svc.receive_sample(sample_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot receive sample '{sample_id}'. Sample not found or not in a receivable state.",
        )
    return updated


@router.post(
    "/samples/{sample_id}/reject",
    response_model=Sample,
    summary="Reject a sample",
    description="Reject a sample with a specified reason.",
)
async def reject_sample(sample_id: str, payload: SampleRejectRequest) -> Sample:
    svc = get_central_lab_service()
    updated = svc.reject_sample(sample_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reject sample '{sample_id}'. Sample not found or already rejected.",
        )
    return updated


# ---------------------------------------------------------------------------
# Result Management
# ---------------------------------------------------------------------------


@router.get(
    "/results",
    response_model=LabResultListResponse,
    summary="List lab results",
    description="Retrieve lab results with optional filtering by sample, test, status, and flag.",
)
async def list_results(
    sample_id: Optional[str] = Query(None, description="Filter by sample ID"),
    test_id: Optional[str] = Query(None, description="Filter by test ID"),
    status: Optional[ResultStatus] = Query(None, description="Filter by result status"),
    flag: Optional[ResultFlag] = Query(None, description="Filter by result flag"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> LabResultListResponse:
    svc = get_central_lab_service()
    items, total = svc.list_results(
        sample_id=sample_id, test_id=test_id, status=status, flag=flag,
        limit=limit, offset=offset,
    )
    return LabResultListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/results/{result_id}",
    response_model=LabResult,
    summary="Get a lab result",
)
async def get_result(result_id: str) -> LabResult:
    svc = get_central_lab_service()
    result = svc.get_result(result_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Result '{result_id}' not found")
    return result


@router.post(
    "/results/submit",
    response_model=list[LabResult],
    status_code=201,
    summary="Submit batch lab results",
    description="Submit one or more lab results. Values are automatically evaluated against "
    "reference ranges and critical thresholds. Critical values trigger alerts.",
)
async def submit_results(payload: ResultBatchSubmitRequest) -> list[LabResult]:
    svc = get_central_lab_service()
    return svc.submit_results(payload)


# ---------------------------------------------------------------------------
# Patient Results
# ---------------------------------------------------------------------------


@router.get(
    "/patients/{patient_id}/results",
    response_model=LabResultListResponse,
    summary="Get patient result history",
    description="Retrieve all lab results for a specific patient, optionally filtered by test.",
)
async def get_patient_results(
    patient_id: str,
    test_id: Optional[str] = Query(None, description="Filter by test ID"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> LabResultListResponse:
    svc = get_central_lab_service()
    items, total = svc.get_patient_results(
        patient_id=patient_id, test_id=test_id, limit=limit, offset=offset
    )
    return LabResultListResponse(items=items, total=total, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# Critical Value Alerts
# ---------------------------------------------------------------------------


@router.get(
    "/alerts",
    response_model=CriticalValueAlertListResponse,
    summary="List critical value alerts",
    description="Retrieve critical value alerts with optional filtering by acknowledgment status.",
)
async def list_alerts(
    acknowledged: Optional[bool] = Query(None, description="Filter by acknowledged status"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> CriticalValueAlertListResponse:
    svc = get_central_lab_service()
    items, total = svc.get_critical_results(
        acknowledged=acknowledged, limit=limit, offset=offset
    )
    return CriticalValueAlertListResponse(items=items, total=total)


@router.post(
    "/alerts/{alert_id}/acknowledge",
    response_model=CriticalValueAlert,
    summary="Acknowledge a critical value alert",
    description="Acknowledge a critical value alert, recording who acknowledged it.",
)
async def acknowledge_alert(alert_id: str, payload: AlertAcknowledgeRequest) -> CriticalValueAlert:
    svc = get_central_lab_service()
    updated = svc.acknowledge_alert(alert_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")
    return updated


# ---------------------------------------------------------------------------
# Shipment Management
# ---------------------------------------------------------------------------


@router.get(
    "/shipments",
    response_model=ShipmentListResponse,
    summary="List sample shipments",
    description="Retrieve sample shipments with optional filtering by site.",
)
async def list_shipments(
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> ShipmentListResponse:
    svc = get_central_lab_service()
    items, total = svc.list_shipments(site_id=site_id, limit=limit, offset=offset)
    return ShipmentListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/shipments/{shipment_id}",
    response_model=SampleShipment,
    summary="Get a sample shipment",
)
async def get_shipment(shipment_id: str) -> SampleShipment:
    svc = get_central_lab_service()
    shipment = svc.get_shipment(shipment_id)
    if shipment is None:
        raise HTTPException(status_code=404, detail=f"Shipment '{shipment_id}' not found")
    return shipment


@router.post(
    "/shipments",
    response_model=SampleShipment,
    status_code=201,
    summary="Create a sample shipment",
    description="Create a new sample shipment. Updates included samples to in-transit status.",
)
async def create_shipment(payload: ShipmentCreateRequest) -> SampleShipment:
    svc = get_central_lab_service()
    return svc.create_shipment(payload)


# ---------------------------------------------------------------------------
# Metrics & Analytics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=LabMetrics,
    summary="Get lab metrics dashboard",
    description="Retrieve aggregated laboratory metrics including sample counts, TAT, rejection rate, and more.",
)
async def get_metrics() -> LabMetrics:
    svc = get_central_lab_service()
    return svc.get_metrics()


@router.get(
    "/turnaround-analysis",
    response_model=list[TurnaroundTimeAnalysis],
    summary="Get turnaround time analysis",
    description="Analyze turnaround times by test category with average, median, and P95 statistics.",
)
async def get_turnaround_analysis() -> list[TurnaroundTimeAnalysis]:
    svc = get_central_lab_service()
    return svc.get_turnaround_analysis()


@router.get(
    "/rejection-analysis",
    summary="Get sample rejection analysis",
    description="Analyze sample rejections by site and reason.",
)
async def get_rejection_analysis() -> dict[str, Any]:
    svc = get_central_lab_service()
    return svc.get_rejection_analysis()


@router.get(
    "/query-suggestions",
    summary="Get auto-query suggestions",
    description="Generate suggestions for missing or inconsistent results that may need follow-up.",
)
async def get_query_suggestions() -> list[dict[str, str]]:
    svc = get_central_lab_service()
    return svc.get_query_suggestions()
