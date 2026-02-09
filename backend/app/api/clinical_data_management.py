"""Clinical Data Management & Data Cleaning API endpoints (CLINICAL-2).

Provides data query management, validation rule CRUD, CDISC dataset lifecycle,
conformance checking, audit trail, and data cleaning metrics.

Endpoints:
    GET    /clinical-data-management/queries                          - List data queries
    GET    /clinical-data-management/queries/{query_id}               - Get single query
    POST   /clinical-data-management/queries                          - Create query
    PUT    /clinical-data-management/queries/{query_id}               - Update query
    POST   /clinical-data-management/queries/{query_id}/answer        - Answer query
    POST   /clinical-data-management/queries/{query_id}/close         - Close query
    POST   /clinical-data-management/queries/{query_id}/requery       - Requery
    POST   /clinical-data-management/queries/{query_id}/cancel        - Cancel query
    GET    /clinical-data-management/rules                            - List validation rules
    GET    /clinical-data-management/rules/{rule_id}                  - Get single rule
    POST   /clinical-data-management/rules                            - Create rule
    PUT    /clinical-data-management/rules/{rule_id}                  - Update rule
    DELETE /clinical-data-management/rules/{rule_id}                  - Delete rule
    POST   /clinical-data-management/validation/run                   - Batch validation
    GET    /clinical-data-management/validation/results               - List results
    GET    /clinical-data-management/datasets                         - List datasets
    GET    /clinical-data-management/datasets/{dataset_id}            - Get dataset
    POST   /clinical-data-management/datasets                         - Create dataset
    PUT    /clinical-data-management/datasets/{dataset_id}            - Update dataset
    POST   /clinical-data-management/datasets/{dataset_id}/freeze     - Freeze dataset
    POST   /clinical-data-management/datasets/{dataset_id}/lock       - Lock dataset
    POST   /clinical-data-management/datasets/{dataset_id}/release    - Release dataset
    POST   /clinical-data-management/datasets/{dataset_id}/archive    - Archive dataset
    GET    /clinical-data-management/datasets/{dataset_id}/conformance - Conformance check
    GET    /clinical-data-management/datasets/compare                 - Compare datasets
    GET    /clinical-data-management/domains                          - List CDISC domains
    GET    /clinical-data-management/domains/{domain_name}            - Get domain
    GET    /clinical-data-management/audit-trail                      - Audit trail
    GET    /clinical-data-management/metrics/{trial_id}/cleaning      - Cleaning metrics
    GET    /clinical-data-management/metrics/{trial_id}/resolution    - Resolution metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.clinical_data_management import (
    AuditTrailListResponse,
    BatchValidationRequest,
    BatchValidationResponse,
    CDISCConformanceReport,
    CDISCDomain,
    CDISCStandard,
    ClinicalDataset,
    ClinicalDatasetCreate,
    ClinicalDatasetUpdate,
    DataCleaningMetrics,
    DataLockLevel,
    DataQuery,
    DataQueryAnswer,
    DataQueryClose,
    DataQueryCreate,
    DataQueryListResponse,
    DataQueryRequery,
    DataQueryUpdate,
    DatasetComparisonResult,
    DatasetFreezeRequest,
    DatasetLockRequest,
    DatasetListResponse,
    DatasetReleaseRequest,
    DatasetStatus,
    QueryCategory,
    QueryResolutionMetrics,
    QueryStatus,
    ValidationResult,
    ValidationResultListResponse,
    ValidationRule,
    ValidationRuleCreate,
    ValidationRuleListResponse,
    ValidationRuleType,
    ValidationRuleUpdate,
)
from app.services.clinical_data_management_service import get_clinical_data_management_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/clinical-data-management",
    tags=["Clinical Data Management"],
)


# ---------------------------------------------------------------------------
# Data Queries
# ---------------------------------------------------------------------------


@router.get(
    "/queries",
    response_model=DataQueryListResponse,
    summary="List data queries",
    description="List data queries with optional filtering by trial, site, status, category, patient, and auto-generated flag.",
)
async def list_queries(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    status: Optional[QueryStatus] = Query(None, description="Filter by status"),
    category: Optional[QueryCategory] = Query(None, description="Filter by category"),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    auto_generated: Optional[bool] = Query(None, description="Filter by auto-generated flag"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> DataQueryListResponse:
    svc = get_clinical_data_management_service()
    items, total = svc.list_queries(
        trial_id=trial_id, site_id=site_id, status=status,
        category=category, patient_id=patient_id,
        auto_generated=auto_generated, limit=limit, offset=offset,
    )
    return DataQueryListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/queries/{query_id}",
    response_model=DataQuery,
    summary="Get data query",
)
async def get_query(query_id: str) -> DataQuery:
    svc = get_clinical_data_management_service()
    query = svc.get_query(query_id)
    if not query:
        raise HTTPException(status_code=404, detail=f"Query {query_id} not found")
    return query


@router.post(
    "/queries",
    response_model=DataQuery,
    status_code=201,
    summary="Create data query",
)
async def create_query(req: DataQueryCreate) -> DataQuery:
    svc = get_clinical_data_management_service()
    return svc.create_query(req)


@router.put(
    "/queries/{query_id}",
    response_model=DataQuery,
    summary="Update data query",
)
async def update_query(query_id: str, req: DataQueryUpdate) -> DataQuery:
    svc = get_clinical_data_management_service()
    result = svc.update_query(query_id, req)
    if not result:
        raise HTTPException(status_code=404, detail=f"Query {query_id} not found")
    return result


@router.post(
    "/queries/{query_id}/answer",
    response_model=DataQuery,
    summary="Answer a data query",
)
async def answer_query(query_id: str, req: DataQueryAnswer) -> DataQuery:
    svc = get_clinical_data_management_service()
    try:
        result = svc.answer_query(query_id, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail=f"Query {query_id} not found")
    return result


@router.post(
    "/queries/{query_id}/close",
    response_model=DataQuery,
    summary="Close a data query",
)
async def close_query(query_id: str, req: DataQueryClose) -> DataQuery:
    svc = get_clinical_data_management_service()
    try:
        result = svc.close_query(query_id, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail=f"Query {query_id} not found")
    return result


@router.post(
    "/queries/{query_id}/requery",
    response_model=DataQuery,
    summary="Requery a data query",
)
async def requery(query_id: str, req: DataQueryRequery) -> DataQuery:
    svc = get_clinical_data_management_service()
    try:
        result = svc.requery(query_id, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail=f"Query {query_id} not found")
    return result


@router.post(
    "/queries/{query_id}/cancel",
    response_model=DataQuery,
    summary="Cancel a data query",
)
async def cancel_query(query_id: str) -> DataQuery:
    svc = get_clinical_data_management_service()
    try:
        result = svc.cancel_query(query_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail=f"Query {query_id} not found")
    return result


# ---------------------------------------------------------------------------
# Validation Rules
# ---------------------------------------------------------------------------


@router.get(
    "/rules",
    response_model=ValidationRuleListResponse,
    summary="List validation rules",
)
async def list_rules(
    domain: Optional[str] = Query(None, description="Filter by CDISC domain"),
    rule_type: Optional[ValidationRuleType] = Query(None, description="Filter by rule type"),
    active: Optional[bool] = Query(None, description="Filter by active status"),
) -> ValidationRuleListResponse:
    svc = get_clinical_data_management_service()
    items, total = svc.list_rules(domain=domain, rule_type=rule_type, active=active)
    return ValidationRuleListResponse(items=items, total=total)


@router.get(
    "/rules/{rule_id}",
    response_model=ValidationRule,
    summary="Get validation rule",
)
async def get_rule(rule_id: str) -> ValidationRule:
    svc = get_clinical_data_management_service()
    rule = svc.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    return rule


@router.post(
    "/rules",
    response_model=ValidationRule,
    status_code=201,
    summary="Create validation rule",
)
async def create_rule(req: ValidationRuleCreate) -> ValidationRule:
    svc = get_clinical_data_management_service()
    return svc.create_rule(req)


@router.put(
    "/rules/{rule_id}",
    response_model=ValidationRule,
    summary="Update validation rule",
)
async def update_rule(rule_id: str, req: ValidationRuleUpdate) -> ValidationRule:
    svc = get_clinical_data_management_service()
    result = svc.update_rule(rule_id, req)
    if not result:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    return result


@router.delete(
    "/rules/{rule_id}",
    status_code=204,
    summary="Delete validation rule",
)
async def delete_rule(rule_id: str) -> None:
    svc = get_clinical_data_management_service()
    if not svc.delete_rule(rule_id):
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")


# ---------------------------------------------------------------------------
# Batch Validation
# ---------------------------------------------------------------------------


@router.post(
    "/validation/run",
    response_model=BatchValidationResponse,
    summary="Run batch validation",
    description="Execute validation rules against a trial's data.",
)
async def run_batch_validation(req: BatchValidationRequest) -> BatchValidationResponse:
    svc = get_clinical_data_management_service()
    return svc.run_batch_validation(trial_id=req.trial_id, rule_ids=req.rule_ids)


@router.get(
    "/validation/results",
    response_model=ValidationResultListResponse,
    summary="List validation results",
)
async def list_validation_results(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    rule_id: Optional[str] = Query(None, description="Filter by rule ID"),
    passed: Optional[bool] = Query(None, description="Filter by pass/fail"),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> ValidationResultListResponse:
    svc = get_clinical_data_management_service()
    items, total = svc.list_results(
        trial_id=trial_id, rule_id=rule_id, passed=passed,
        patient_id=patient_id, limit=limit, offset=offset,
    )
    return ValidationResultListResponse(items=items, total=total, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# Clinical Datasets
# ---------------------------------------------------------------------------


@router.get(
    "/datasets",
    response_model=DatasetListResponse,
    summary="List clinical datasets",
)
async def list_datasets(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[DatasetStatus] = Query(None, description="Filter by status"),
    cdisc_standard: Optional[CDISCStandard] = Query(None, description="Filter by CDISC standard"),
) -> DatasetListResponse:
    svc = get_clinical_data_management_service()
    items, total = svc.list_datasets(trial_id=trial_id, status=status, cdisc_standard=cdisc_standard)
    return DatasetListResponse(items=items, total=total)


@router.get(
    "/datasets/compare",
    response_model=DatasetComparisonResult,
    summary="Compare two datasets",
)
async def compare_datasets(
    dataset_a_id: str = Query(..., description="First dataset ID"),
    dataset_b_id: str = Query(..., description="Second dataset ID"),
) -> DatasetComparisonResult:
    svc = get_clinical_data_management_service()
    result = svc.compare_datasets(dataset_a_id, dataset_b_id)
    if not result:
        raise HTTPException(status_code=404, detail="One or both datasets not found")
    return result


@router.get(
    "/datasets/{dataset_id}",
    response_model=ClinicalDataset,
    summary="Get clinical dataset",
)
async def get_dataset(dataset_id: str) -> ClinicalDataset:
    svc = get_clinical_data_management_service()
    ds = svc.get_dataset(dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
    return ds


@router.post(
    "/datasets",
    response_model=ClinicalDataset,
    status_code=201,
    summary="Create clinical dataset",
)
async def create_dataset(req: ClinicalDatasetCreate) -> ClinicalDataset:
    svc = get_clinical_data_management_service()
    return svc.create_dataset(req)


@router.put(
    "/datasets/{dataset_id}",
    response_model=ClinicalDataset,
    summary="Update clinical dataset",
)
async def update_dataset(dataset_id: str, req: ClinicalDatasetUpdate) -> ClinicalDataset:
    svc = get_clinical_data_management_service()
    try:
        result = svc.update_dataset(dataset_id, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
    return result


@router.post(
    "/datasets/{dataset_id}/freeze",
    response_model=ClinicalDataset,
    summary="Freeze clinical dataset",
)
async def freeze_dataset(dataset_id: str, req: DatasetFreezeRequest) -> ClinicalDataset:
    svc = get_clinical_data_management_service()
    try:
        result = svc.freeze_dataset(dataset_id, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
    return result


@router.post(
    "/datasets/{dataset_id}/lock",
    response_model=ClinicalDataset,
    summary="Lock clinical dataset",
)
async def lock_dataset(dataset_id: str, req: DatasetLockRequest) -> ClinicalDataset:
    svc = get_clinical_data_management_service()
    try:
        result = svc.lock_dataset(dataset_id, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
    return result


@router.post(
    "/datasets/{dataset_id}/release",
    response_model=ClinicalDataset,
    summary="Release clinical dataset",
)
async def release_dataset(dataset_id: str, req: DatasetReleaseRequest) -> ClinicalDataset:
    svc = get_clinical_data_management_service()
    try:
        result = svc.release_dataset(dataset_id, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
    return result


@router.post(
    "/datasets/{dataset_id}/archive",
    response_model=ClinicalDataset,
    summary="Archive clinical dataset",
)
async def archive_dataset(dataset_id: str, actor: str = Query(..., description="User performing the archive")) -> ClinicalDataset:
    svc = get_clinical_data_management_service()
    try:
        result = svc.archive_dataset(dataset_id, actor)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
    return result


@router.get(
    "/datasets/{dataset_id}/conformance",
    response_model=CDISCConformanceReport,
    summary="Run CDISC conformance check",
)
async def run_conformance_check(dataset_id: str) -> CDISCConformanceReport:
    svc = get_clinical_data_management_service()
    report = svc.run_conformance_check(dataset_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
    return report


# ---------------------------------------------------------------------------
# CDISC Domains
# ---------------------------------------------------------------------------


@router.get(
    "/domains",
    response_model=list[CDISCDomain],
    summary="List CDISC domains",
)
async def list_domains() -> list[CDISCDomain]:
    svc = get_clinical_data_management_service()
    return svc.list_domains()


@router.get(
    "/domains/{domain_name}",
    response_model=CDISCDomain,
    summary="Get CDISC domain",
)
async def get_domain(domain_name: str) -> CDISCDomain:
    svc = get_clinical_data_management_service()
    domain = svc.get_domain(domain_name.upper())
    if not domain:
        raise HTTPException(status_code=404, detail=f"Domain {domain_name} not found")
    return domain


# ---------------------------------------------------------------------------
# Audit Trail
# ---------------------------------------------------------------------------


@router.get(
    "/audit-trail",
    response_model=AuditTrailListResponse,
    summary="List audit trail entries",
)
async def list_audit_trail(
    dataset_id: Optional[str] = Query(None, description="Filter by dataset ID"),
    action: Optional[str] = Query(None, description="Filter by action"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> AuditTrailListResponse:
    svc = get_clinical_data_management_service()
    items, total = svc.get_audit_trail(dataset_id=dataset_id, action=action, limit=limit, offset=offset)
    return AuditTrailListResponse(items=items, total=total)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics/{trial_id}/cleaning",
    response_model=DataCleaningMetrics,
    summary="Get data cleaning metrics",
)
async def get_cleaning_metrics(trial_id: str) -> DataCleaningMetrics:
    svc = get_clinical_data_management_service()
    return svc.get_cleaning_metrics(trial_id)


@router.get(
    "/metrics/{trial_id}/resolution",
    response_model=QueryResolutionMetrics,
    summary="Get query resolution metrics",
)
async def get_resolution_metrics(trial_id: str) -> QueryResolutionMetrics:
    svc = get_clinical_data_management_service()
    return svc.get_resolution_metrics(trial_id)
