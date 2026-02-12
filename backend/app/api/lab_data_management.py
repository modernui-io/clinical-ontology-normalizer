"""Lab Data Management API endpoints (LAB-DATA).

Provides comprehensive lab data operations: normal range definitions, alert rule
management, specimen tracking, lab result management, alert lifecycle, and
lab data operational metrics.

Endpoints:
    GET    /lab-data-management/normal-ranges                        - List normal ranges
    GET    /lab-data-management/normal-ranges/{range_id}             - Get single normal range
    POST   /lab-data-management/normal-ranges                        - Create normal range
    PUT    /lab-data-management/normal-ranges/{range_id}             - Update normal range
    DELETE /lab-data-management/normal-ranges/{range_id}             - Delete normal range
    GET    /lab-data-management/alert-rules                          - List alert rules
    GET    /lab-data-management/alert-rules/{rule_id}                - Get single alert rule
    POST   /lab-data-management/alert-rules                          - Create alert rule
    PUT    /lab-data-management/alert-rules/{rule_id}                - Update alert rule
    DELETE /lab-data-management/alert-rules/{rule_id}                - Delete alert rule
    GET    /lab-data-management/specimens                            - List specimens
    GET    /lab-data-management/specimens/{specimen_id}              - Get single specimen
    POST   /lab-data-management/specimens                            - Create specimen
    PUT    /lab-data-management/specimens/{specimen_id}              - Update specimen
    DELETE /lab-data-management/specimens/{specimen_id}              - Delete specimen
    GET    /lab-data-management/results                              - List results
    GET    /lab-data-management/results/{result_id}                  - Get single result
    POST   /lab-data-management/results                              - Create result
    PUT    /lab-data-management/results/{result_id}                  - Update result
    DELETE /lab-data-management/results/{result_id}                  - Delete result
    GET    /lab-data-management/alerts                               - List alerts
    GET    /lab-data-management/alerts/{alert_id}                    - Get single alert
    PUT    /lab-data-management/alerts/{alert_id}                    - Update (acknowledge) alert
    DELETE /lab-data-management/alerts/{alert_id}                    - Delete alert
    GET    /lab-data-management/metrics                              - Lab data metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Response

from app.schemas.lab_data_management import (
    AbnormalFlag,
    AlertSeverity,
    LabAlert,
    LabAlertListResponse,
    LabAlertRule,
    LabAlertRuleCreate,
    LabAlertRuleListResponse,
    LabAlertRuleUpdate,
    LabAlertUpdate,
    LabCategory,
    LabDataMetrics,
    LabNormalRange,
    LabNormalRangeCreate,
    LabNormalRangeListResponse,
    LabResult,
    LabResultCreate,
    LabResultListResponse,
    LabResultUpdate,
    LabSpecimen,
    LabSpecimenCreate,
    LabSpecimenListResponse,
    LabSpecimenUpdate,
    ResultStatus,
    SpecimenStatus,
)
from app.services.lab_data_management_service import get_lab_data_management_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/lab-data-management",
    tags=["Lab Data Management"],
)


# ---------------------------------------------------------------------------
# Normal Range Management
# ---------------------------------------------------------------------------


@router.get(
    "/normal-ranges",
    response_model=LabNormalRangeListResponse,
    summary="List lab normal ranges",
    description="Retrieve lab normal ranges with optional filtering by category or test code.",
)
async def list_normal_ranges(
    category: Optional[LabCategory] = Query(None, description="Filter by lab category"),
    test_code: Optional[str] = Query(None, description="Filter by test code"),
) -> LabNormalRangeListResponse:
    svc = get_lab_data_management_service()
    items = svc.list_normal_ranges(category=category, test_code=test_code)
    return LabNormalRangeListResponse(items=items, total=len(items))


@router.get(
    "/normal-ranges/{range_id}",
    response_model=LabNormalRange,
    summary="Get a single normal range",
)
async def get_normal_range(range_id: str) -> LabNormalRange:
    svc = get_lab_data_management_service()
    item = svc.get_normal_range(range_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Normal range '{range_id}' not found")
    return item


@router.post(
    "/normal-ranges",
    response_model=LabNormalRange,
    status_code=201,
    summary="Create a new normal range",
)
async def create_normal_range(payload: LabNormalRangeCreate) -> LabNormalRange:
    svc = get_lab_data_management_service()
    return svc.create_normal_range(payload)


@router.put(
    "/normal-ranges/{range_id}",
    response_model=LabNormalRange,
    summary="Update an existing normal range",
)
async def update_normal_range(range_id: str, payload: LabNormalRangeCreate) -> LabNormalRange:
    svc = get_lab_data_management_service()
    updated = svc.update_normal_range(range_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Normal range '{range_id}' not found")
    return updated


@router.delete(
    "/normal-ranges/{range_id}",
    status_code=204,
    summary="Delete a normal range",
)
async def delete_normal_range(range_id: str) -> Response:
    svc = get_lab_data_management_service()
    deleted = svc.delete_normal_range(range_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Normal range '{range_id}' not found")
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Alert Rule Management
# ---------------------------------------------------------------------------


@router.get(
    "/alert-rules",
    response_model=LabAlertRuleListResponse,
    summary="List lab alert rules",
    description="Retrieve lab alert rules with optional filtering by trial ID or active status.",
)
async def list_alert_rules(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    active: Optional[bool] = Query(None, description="Filter by active status"),
) -> LabAlertRuleListResponse:
    svc = get_lab_data_management_service()
    items = svc.list_alert_rules(trial_id=trial_id, active=active)
    return LabAlertRuleListResponse(items=items, total=len(items))


@router.get(
    "/alert-rules/{rule_id}",
    response_model=LabAlertRule,
    summary="Get a single alert rule",
)
async def get_alert_rule(rule_id: str) -> LabAlertRule:
    svc = get_lab_data_management_service()
    item = svc.get_alert_rule(rule_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Alert rule '{rule_id}' not found")
    return item


@router.post(
    "/alert-rules",
    response_model=LabAlertRule,
    status_code=201,
    summary="Create a new alert rule",
)
async def create_alert_rule(payload: LabAlertRuleCreate) -> LabAlertRule:
    svc = get_lab_data_management_service()
    return svc.create_alert_rule(payload)


@router.put(
    "/alert-rules/{rule_id}",
    response_model=LabAlertRule,
    summary="Update an existing alert rule",
)
async def update_alert_rule(rule_id: str, payload: LabAlertRuleUpdate) -> LabAlertRule:
    svc = get_lab_data_management_service()
    updated = svc.update_alert_rule(rule_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Alert rule '{rule_id}' not found")
    return updated


@router.delete(
    "/alert-rules/{rule_id}",
    status_code=204,
    summary="Delete an alert rule",
)
async def delete_alert_rule(rule_id: str) -> Response:
    svc = get_lab_data_management_service()
    deleted = svc.delete_alert_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Alert rule '{rule_id}' not found")
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Specimen Management
# ---------------------------------------------------------------------------


@router.get(
    "/specimens",
    response_model=LabSpecimenListResponse,
    summary="List lab specimens",
    description="Retrieve lab specimens with optional filtering by trial ID, status, or subject.",
)
async def list_specimens(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[SpecimenStatus] = Query(None, description="Filter by specimen status"),
    subject_id: Optional[str] = Query(None, description="Filter by subject ID"),
) -> LabSpecimenListResponse:
    svc = get_lab_data_management_service()
    items = svc.list_specimens(trial_id=trial_id, status=status, subject_id=subject_id)
    return LabSpecimenListResponse(items=items, total=len(items))


@router.get(
    "/specimens/{specimen_id}",
    response_model=LabSpecimen,
    summary="Get a single specimen",
)
async def get_specimen(specimen_id: str) -> LabSpecimen:
    svc = get_lab_data_management_service()
    item = svc.get_specimen(specimen_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Specimen '{specimen_id}' not found")
    return item


@router.post(
    "/specimens",
    response_model=LabSpecimen,
    status_code=201,
    summary="Create a new specimen",
)
async def create_specimen(payload: LabSpecimenCreate) -> LabSpecimen:
    svc = get_lab_data_management_service()
    return svc.create_specimen(payload)


@router.put(
    "/specimens/{specimen_id}",
    response_model=LabSpecimen,
    summary="Update an existing specimen",
)
async def update_specimen(specimen_id: str, payload: LabSpecimenUpdate) -> LabSpecimen:
    svc = get_lab_data_management_service()
    updated = svc.update_specimen(specimen_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Specimen '{specimen_id}' not found")
    return updated


@router.delete(
    "/specimens/{specimen_id}",
    status_code=204,
    summary="Delete a specimen",
)
async def delete_specimen(specimen_id: str) -> Response:
    svc = get_lab_data_management_service()
    deleted = svc.delete_specimen(specimen_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Specimen '{specimen_id}' not found")
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Result Management
# ---------------------------------------------------------------------------


@router.get(
    "/results",
    response_model=LabResultListResponse,
    summary="List lab results",
    description="Retrieve lab results with optional filtering by trial, status, subject, category, or abnormal flag.",
)
async def list_results(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[ResultStatus] = Query(None, description="Filter by result status"),
    subject_id: Optional[str] = Query(None, description="Filter by subject ID"),
    category: Optional[LabCategory] = Query(None, description="Filter by lab category"),
    abnormal_flag: Optional[AbnormalFlag] = Query(None, description="Filter by abnormal flag"),
) -> LabResultListResponse:
    svc = get_lab_data_management_service()
    items = svc.list_results(
        trial_id=trial_id,
        status=status,
        subject_id=subject_id,
        category=category,
        abnormal_flag=abnormal_flag,
    )
    return LabResultListResponse(items=items, total=len(items))


@router.get(
    "/results/{result_id}",
    response_model=LabResult,
    summary="Get a single lab result",
)
async def get_result(result_id: str) -> LabResult:
    svc = get_lab_data_management_service()
    item = svc.get_result(result_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Result '{result_id}' not found")
    return item


@router.post(
    "/results",
    response_model=LabResult,
    status_code=201,
    summary="Create a new lab result",
)
async def create_result(payload: LabResultCreate) -> LabResult:
    svc = get_lab_data_management_service()
    return svc.create_result(payload)


@router.put(
    "/results/{result_id}",
    response_model=LabResult,
    summary="Update an existing lab result",
)
async def update_result(result_id: str, payload: LabResultUpdate) -> LabResult:
    svc = get_lab_data_management_service()
    updated = svc.update_result(result_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Result '{result_id}' not found")
    return updated


@router.delete(
    "/results/{result_id}",
    status_code=204,
    summary="Delete a lab result",
)
async def delete_result(result_id: str) -> Response:
    svc = get_lab_data_management_service()
    deleted = svc.delete_result(result_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Result '{result_id}' not found")
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Alert Management
# ---------------------------------------------------------------------------


@router.get(
    "/alerts",
    response_model=LabAlertListResponse,
    summary="List lab alerts",
    description="Retrieve lab alerts with optional filtering by trial ID, severity, or acknowledgment status.",
)
async def list_alerts(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    severity: Optional[AlertSeverity] = Query(None, description="Filter by severity"),
    acknowledged: Optional[bool] = Query(None, description="Filter by acknowledgment status"),
) -> LabAlertListResponse:
    svc = get_lab_data_management_service()
    items = svc.list_alerts(trial_id=trial_id, severity=severity, acknowledged=acknowledged)
    return LabAlertListResponse(items=items, total=len(items))


@router.get(
    "/alerts/{alert_id}",
    response_model=LabAlert,
    summary="Get a single alert",
)
async def get_alert(alert_id: str) -> LabAlert:
    svc = get_lab_data_management_service()
    item = svc.get_alert(alert_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")
    return item


@router.put(
    "/alerts/{alert_id}",
    response_model=LabAlert,
    summary="Update (acknowledge) an alert",
)
async def update_alert(alert_id: str, payload: LabAlertUpdate) -> LabAlert:
    svc = get_lab_data_management_service()
    updated = svc.update_alert(alert_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")
    return updated


@router.delete(
    "/alerts/{alert_id}",
    status_code=204,
    summary="Delete an alert",
)
async def delete_alert(alert_id: str) -> Response:
    svc = get_lab_data_management_service()
    deleted = svc.delete_alert(alert_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=LabDataMetrics,
    summary="Get lab data metrics",
    description="Compute aggregated lab data management metrics with optional trial filter.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> LabDataMetrics:
    svc = get_lab_data_management_service()
    return svc.get_metrics(trial_id=trial_id)
