"""Electronic Data Capture (EDC) Form Management API endpoints (CLINICAL-24).

Provides comprehensive EDC operations: CRF template definitions & management,
CRF field configuration with SDTM mapping, CRF instance lifecycle (blank through
locked/frozen), data query management with auto-generation, edit check definitions
and execution, form-level data entry/validation, and EDC operational metrics.

Endpoints:
    GET    /edc/templates                                   - List CRF templates
    GET    /edc/templates/{template_id}                     - Get single template
    POST   /edc/templates                                   - Create template
    PUT    /edc/templates/{template_id}                     - Update template
    DELETE /edc/templates/{template_id}                     - Delete template
    GET    /edc/instances                                   - List CRF instances
    GET    /edc/instances/{instance_id}                     - Get single instance
    POST   /edc/instances                                   - Create instance
    PUT    /edc/instances/{instance_id}                     - Update instance data
    POST   /edc/instances/{instance_id}/sign                - Sign instance
    POST   /edc/instances/{instance_id}/lock                - Lock instance
    POST   /edc/instances/{instance_id}/freeze              - Freeze instance
    DELETE /edc/instances/{instance_id}                     - Delete instance
    GET    /edc/queries                                     - List data queries
    GET    /edc/queries/{query_id}                          - Get single query
    POST   /edc/queries                                     - Create data query
    POST   /edc/queries/{query_id}/respond                  - Respond to query
    POST   /edc/queries/{query_id}/close                    - Close query
    POST   /edc/queries/{query_id}/cancel                   - Cancel query
    GET    /edc/edit-checks                                 - List edit checks
    GET    /edc/edit-checks/{check_id}                      - Get single edit check
    POST   /edc/edit-checks                                 - Create edit check
    PUT    /edc/edit-checks/{check_id}                      - Update edit check
    DELETE /edc/edit-checks/{check_id}                      - Delete edit check
    POST   /edc/instances/{instance_id}/run-edit-checks     - Run edit checks
    GET    /edc/metrics                                     - EDC dashboard metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.edc_forms import (
    CRFInstance,
    CRFInstanceCreate,
    CRFInstanceListResponse,
    CRFInstanceSign,
    CRFInstanceUpdate,
    CRFTemplate,
    CRFTemplateCreate,
    CRFTemplateListResponse,
    CRFTemplateUpdate,
    DataQuery,
    DataQueryClose,
    DataQueryCreate,
    DataQueryListResponse,
    DataQueryRespond,
    EditCheck,
    EditCheckCreate,
    EditCheckListResponse,
    EditCheckResult,
    EditCheckType,
    EditCheckUpdate,
    EDCMetrics,
    FormStatus,
    QueryStatus,
)
from app.services.edc_forms_service import get_edc_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/edc",
    tags=["Electronic Data Capture"],
)


# ---------------------------------------------------------------------------
# CRF Templates
# ---------------------------------------------------------------------------


@router.get(
    "/templates",
    response_model=CRFTemplateListResponse,
    summary="List CRF templates",
    description="Retrieve CRF templates with optional filtering by trial, form name, and status.",
)
async def list_templates(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    form_name: Optional[str] = Query(None, description="Filter by form name (partial match)"),
    status: Optional[str] = Query(None, description="Filter by template status"),
) -> CRFTemplateListResponse:
    svc = get_edc_service()
    items = svc.list_templates(trial_id=trial_id, form_name=form_name, status=status)
    return CRFTemplateListResponse(items=items, total=len(items))


@router.get(
    "/templates/{template_id}",
    response_model=CRFTemplate,
    summary="Get a CRF template",
)
async def get_template(template_id: str) -> CRFTemplate:
    svc = get_edc_service()
    tpl = svc.get_template(template_id)
    if tpl is None:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
    return tpl


@router.post(
    "/templates",
    response_model=CRFTemplate,
    status_code=201,
    summary="Create a CRF template",
)
async def create_template(payload: CRFTemplateCreate) -> CRFTemplate:
    svc = get_edc_service()
    return svc.create_template(payload)


@router.put(
    "/templates/{template_id}",
    response_model=CRFTemplate,
    summary="Update a CRF template",
)
async def update_template(template_id: str, payload: CRFTemplateUpdate) -> CRFTemplate:
    svc = get_edc_service()
    updated = svc.update_template(template_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
    return updated


@router.delete(
    "/templates/{template_id}",
    status_code=204,
    summary="Delete a CRF template",
)
async def delete_template(template_id: str) -> None:
    svc = get_edc_service()
    deleted = svc.delete_template(template_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")


# ---------------------------------------------------------------------------
# CRF Instances
# ---------------------------------------------------------------------------


@router.get(
    "/instances",
    response_model=CRFInstanceListResponse,
    summary="List CRF instances",
    description="Retrieve CRF instances with optional filtering by template, patient, site, status, and visit.",
)
async def list_instances(
    template_id: Optional[str] = Query(None, description="Filter by template ID"),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    status: Optional[FormStatus] = Query(None, description="Filter by form status"),
    visit_number: Optional[int] = Query(None, description="Filter by visit number"),
) -> CRFInstanceListResponse:
    svc = get_edc_service()
    items = svc.list_instances(
        template_id=template_id,
        patient_id=patient_id,
        site_id=site_id,
        status=status,
        visit_number=visit_number,
    )
    return CRFInstanceListResponse(items=items, total=len(items))


@router.get(
    "/instances/{instance_id}",
    response_model=CRFInstance,
    summary="Get a CRF instance",
)
async def get_instance(instance_id: str) -> CRFInstance:
    svc = get_edc_service()
    inst = svc.get_instance(instance_id)
    if inst is None:
        raise HTTPException(status_code=404, detail=f"Instance '{instance_id}' not found")
    return inst


@router.post(
    "/instances",
    response_model=CRFInstance,
    status_code=201,
    summary="Create a CRF instance",
)
async def create_instance(payload: CRFInstanceCreate) -> CRFInstance:
    svc = get_edc_service()
    try:
        return svc.create_instance(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/instances/{instance_id}",
    response_model=CRFInstance,
    summary="Update CRF instance data",
    description="Update form data and/or status. Cannot update locked or frozen forms.",
)
async def update_instance(instance_id: str, payload: CRFInstanceUpdate) -> CRFInstance:
    svc = get_edc_service()
    try:
        updated = svc.update_instance(instance_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Instance '{instance_id}' not found")
    return updated


@router.post(
    "/instances/{instance_id}/sign",
    response_model=CRFInstance,
    summary="Sign a CRF instance",
    description="Apply electronic signature to a completed CRF instance.",
)
async def sign_instance(instance_id: str, payload: CRFInstanceSign) -> CRFInstance:
    svc = get_edc_service()
    try:
        result = svc.sign_instance(instance_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Instance '{instance_id}' not found")
    return result


@router.post(
    "/instances/{instance_id}/lock",
    response_model=CRFInstance,
    summary="Lock a CRF instance",
    description="Lock a signed CRF instance to prevent further edits.",
)
async def lock_instance(instance_id: str) -> CRFInstance:
    svc = get_edc_service()
    try:
        result = svc.lock_instance(instance_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Instance '{instance_id}' not found")
    return result


@router.post(
    "/instances/{instance_id}/freeze",
    response_model=CRFInstance,
    summary="Freeze a CRF instance",
    description="Apply database freeze to a locked CRF instance.",
)
async def freeze_instance(instance_id: str) -> CRFInstance:
    svc = get_edc_service()
    try:
        result = svc.freeze_instance(instance_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Instance '{instance_id}' not found")
    return result


@router.delete(
    "/instances/{instance_id}",
    status_code=204,
    summary="Delete a CRF instance",
)
async def delete_instance(instance_id: str) -> None:
    svc = get_edc_service()
    deleted = svc.delete_instance(instance_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Instance '{instance_id}' not found")


# ---------------------------------------------------------------------------
# Data Queries
# ---------------------------------------------------------------------------


@router.get(
    "/queries",
    response_model=DataQueryListResponse,
    summary="List data queries",
    description="Retrieve data queries with optional filtering by instance, status, and auto-generation.",
)
async def list_queries(
    instance_id: Optional[str] = Query(None, description="Filter by CRF instance ID"),
    status: Optional[QueryStatus] = Query(None, description="Filter by query status"),
    auto_generated: Optional[bool] = Query(None, description="Filter by auto-generated flag"),
) -> DataQueryListResponse:
    svc = get_edc_service()
    items = svc.list_queries(
        instance_id=instance_id, status=status, auto_generated=auto_generated
    )
    return DataQueryListResponse(items=items, total=len(items))


@router.get(
    "/queries/{query_id}",
    response_model=DataQuery,
    summary="Get a data query",
)
async def get_query(query_id: str) -> DataQuery:
    svc = get_edc_service()
    query = svc.get_query(query_id)
    if query is None:
        raise HTTPException(status_code=404, detail=f"Query '{query_id}' not found")
    return query


@router.post(
    "/queries",
    response_model=DataQuery,
    status_code=201,
    summary="Create a data query",
    description="Raise a new data query against a CRF instance field.",
)
async def create_query(payload: DataQueryCreate) -> DataQuery:
    svc = get_edc_service()
    try:
        return svc.create_query(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/queries/{query_id}/respond",
    response_model=DataQuery,
    summary="Respond to a data query",
    description="Provide a response to an open data query.",
)
async def respond_to_query(query_id: str, payload: DataQueryRespond) -> DataQuery:
    svc = get_edc_service()
    try:
        result = svc.respond_to_query(query_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Query '{query_id}' not found")
    return result


@router.post(
    "/queries/{query_id}/close",
    response_model=DataQuery,
    summary="Close a data query",
    description="Close an open or answered data query.",
)
async def close_query(query_id: str, payload: DataQueryClose) -> DataQuery:
    svc = get_edc_service()
    try:
        result = svc.close_query(query_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Query '{query_id}' not found")
    return result


@router.post(
    "/queries/{query_id}/cancel",
    response_model=DataQuery,
    summary="Cancel a data query",
)
async def cancel_query(query_id: str) -> DataQuery:
    svc = get_edc_service()
    try:
        result = svc.cancel_query(query_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Query '{query_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Edit Checks
# ---------------------------------------------------------------------------


@router.get(
    "/edit-checks",
    response_model=EditCheckListResponse,
    summary="List edit checks",
    description="Retrieve edit checks with optional filtering by template, type, and active status.",
)
async def list_edit_checks(
    template_id: Optional[str] = Query(None, description="Filter by template ID"),
    check_type: Optional[EditCheckType] = Query(None, description="Filter by check type"),
    active: Optional[bool] = Query(None, description="Filter by active status"),
) -> EditCheckListResponse:
    svc = get_edc_service()
    items = svc.list_edit_checks(
        template_id=template_id, check_type=check_type, active=active
    )
    return EditCheckListResponse(items=items, total=len(items))


@router.get(
    "/edit-checks/{check_id}",
    response_model=EditCheck,
    summary="Get an edit check",
)
async def get_edit_check(check_id: str) -> EditCheck:
    svc = get_edc_service()
    ec = svc.get_edit_check(check_id)
    if ec is None:
        raise HTTPException(status_code=404, detail=f"Edit check '{check_id}' not found")
    return ec


@router.post(
    "/edit-checks",
    response_model=EditCheck,
    status_code=201,
    summary="Create an edit check",
)
async def create_edit_check(payload: EditCheckCreate) -> EditCheck:
    svc = get_edc_service()
    try:
        return svc.create_edit_check(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/edit-checks/{check_id}",
    response_model=EditCheck,
    summary="Update an edit check",
)
async def update_edit_check(check_id: str, payload: EditCheckUpdate) -> EditCheck:
    svc = get_edc_service()
    updated = svc.update_edit_check(check_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Edit check '{check_id}' not found")
    return updated


@router.delete(
    "/edit-checks/{check_id}",
    status_code=204,
    summary="Delete an edit check",
)
async def delete_edit_check(check_id: str) -> None:
    svc = get_edc_service()
    deleted = svc.delete_edit_check(check_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Edit check '{check_id}' not found")


# ---------------------------------------------------------------------------
# Edit Check Execution
# ---------------------------------------------------------------------------


@router.post(
    "/instances/{instance_id}/run-edit-checks",
    response_model=EditCheckResult,
    summary="Run edit checks on a CRF instance",
    description="Execute all active edit checks against a CRF instance and return results.",
)
async def run_edit_checks(instance_id: str) -> EditCheckResult:
    svc = get_edc_service()
    try:
        return svc.run_edit_checks(instance_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=EDCMetrics,
    summary="Get EDC dashboard metrics",
    description="Aggregated Electronic Data Capture metrics across all forms and queries.",
)
async def get_metrics() -> EDCMetrics:
    svc = get_edc_service()
    return svc.get_metrics()
