"""Data Privacy Management API endpoints (DATA-PRIV).

Provides comprehensive data privacy operations: consent record management,
anonymization tracking, data subject request (DSR) lifecycle, privacy impact
assessments, data retention policy management, and privacy compliance metrics.

Endpoints:
    GET    /data-privacy/consent-records                     - List consent records
    GET    /data-privacy/consent-records/{record_id}         - Get single consent record
    POST   /data-privacy/consent-records                     - Create consent record
    PUT    /data-privacy/consent-records/{record_id}         - Update consent record
    DELETE /data-privacy/consent-records/{record_id}         - Delete consent record
    GET    /data-privacy/anonymization-records               - List anonymization records
    GET    /data-privacy/anonymization-records/{record_id}   - Get single anonymization record
    POST   /data-privacy/anonymization-records               - Create anonymization record
    PUT    /data-privacy/anonymization-records/{record_id}   - Update anonymization record
    DELETE /data-privacy/anonymization-records/{record_id}   - Delete anonymization record
    GET    /data-privacy/dsr                                 - List data subject requests
    GET    /data-privacy/dsr/{record_id}                     - Get single DSR
    POST   /data-privacy/dsr                                 - Create DSR
    PUT    /data-privacy/dsr/{record_id}                     - Update DSR
    DELETE /data-privacy/dsr/{record_id}                     - Delete DSR
    GET    /data-privacy/pia                                 - List privacy impact assessments
    GET    /data-privacy/pia/{record_id}                     - Get single PIA
    POST   /data-privacy/pia                                 - Create PIA
    PUT    /data-privacy/pia/{record_id}                     - Update PIA
    DELETE /data-privacy/pia/{record_id}                     - Delete PIA
    GET    /data-privacy/retention-policies                  - List data retention policies
    GET    /data-privacy/retention-policies/{record_id}      - Get single retention policy
    POST   /data-privacy/retention-policies                  - Create retention policy
    PUT    /data-privacy/retention-policies/{record_id}      - Update retention policy
    DELETE /data-privacy/retention-policies/{record_id}      - Delete retention policy
    GET    /data-privacy/metrics                             - Privacy compliance metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.data_privacy import (
    AnonymizationMethod,
    AnonymizationRecord,
    AnonymizationRecordCreate,
    AnonymizationRecordListResponse,
    AnonymizationRecordUpdate,
    ConsentRecord,
    ConsentRecordCreate,
    ConsentRecordListResponse,
    ConsentRecordUpdate,
    ConsentStatus,
    ConsentType,
    DataPrivacyMetrics,
    DataRetentionPolicy,
    DataRetentionPolicyCreate,
    DataRetentionPolicyListResponse,
    DataRetentionPolicyUpdate,
    DataSubjectRequest,
    DataSubjectRequestCreate,
    DataSubjectRequestListResponse,
    DataSubjectRequestUpdate,
    DSRStatus,
    DSRType,
    PIAStatus,
    PrivacyImpactAssessment,
    PrivacyImpactAssessmentCreate,
    PrivacyImpactAssessmentListResponse,
    PrivacyImpactAssessmentUpdate,
)
from app.services.data_privacy_service import get_data_privacy_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/data-privacy",
    tags=["Data Privacy"],
)


# ---------------------------------------------------------------------------
# Consent Records
# ---------------------------------------------------------------------------


@router.get(
    "/consent-records",
    response_model=ConsentRecordListResponse,
    summary="List consent records",
    description="Retrieve consent records with optional filtering by trial, type, and status.",
)
async def list_consent_records(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    consent_type: Optional[ConsentType] = Query(None, description="Filter by consent type"),
    consent_status: Optional[ConsentStatus] = Query(None, description="Filter by consent status"),
) -> ConsentRecordListResponse:
    svc = get_data_privacy_service()
    items = svc.list_consent_records(
        trial_id=trial_id,
        consent_type=consent_type,
        consent_status=consent_status,
    )
    return ConsentRecordListResponse(items=items, total=len(items))


@router.get(
    "/consent-records/{record_id}",
    response_model=ConsentRecord,
    summary="Get a consent record",
)
async def get_consent_record(record_id: str) -> ConsentRecord:
    svc = get_data_privacy_service()
    rec = svc.get_consent_record(record_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"Consent record '{record_id}' not found")
    return rec


@router.post(
    "/consent-records",
    response_model=ConsentRecord,
    status_code=201,
    summary="Create a consent record",
)
async def create_consent_record(payload: ConsentRecordCreate) -> ConsentRecord:
    svc = get_data_privacy_service()
    return svc.create_consent_record(payload)


@router.put(
    "/consent-records/{record_id}",
    response_model=ConsentRecord,
    summary="Update a consent record",
)
async def update_consent_record(record_id: str, payload: ConsentRecordUpdate) -> ConsentRecord:
    svc = get_data_privacy_service()
    updated = svc.update_consent_record(record_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Consent record '{record_id}' not found")
    return updated


@router.delete(
    "/consent-records/{record_id}",
    status_code=204,
    summary="Delete a consent record",
)
async def delete_consent_record(record_id: str) -> None:
    svc = get_data_privacy_service()
    deleted = svc.delete_consent_record(record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Consent record '{record_id}' not found")


# ---------------------------------------------------------------------------
# Anonymization Records
# ---------------------------------------------------------------------------


@router.get(
    "/anonymization-records",
    response_model=AnonymizationRecordListResponse,
    summary="List anonymization records",
    description="Retrieve anonymization records with optional filtering by trial, method, and validation status.",
)
async def list_anonymization_records(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    method: Optional[AnonymizationMethod] = Query(None, description="Filter by anonymization method"),
    validated: Optional[bool] = Query(None, description="Filter by validation status"),
) -> AnonymizationRecordListResponse:
    svc = get_data_privacy_service()
    items = svc.list_anonymization_records(
        trial_id=trial_id,
        method=method,
        validated=validated,
    )
    return AnonymizationRecordListResponse(items=items, total=len(items))


@router.get(
    "/anonymization-records/{record_id}",
    response_model=AnonymizationRecord,
    summary="Get an anonymization record",
)
async def get_anonymization_record(record_id: str) -> AnonymizationRecord:
    svc = get_data_privacy_service()
    rec = svc.get_anonymization_record(record_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"Anonymization record '{record_id}' not found")
    return rec


@router.post(
    "/anonymization-records",
    response_model=AnonymizationRecord,
    status_code=201,
    summary="Create an anonymization record",
)
async def create_anonymization_record(payload: AnonymizationRecordCreate) -> AnonymizationRecord:
    svc = get_data_privacy_service()
    return svc.create_anonymization_record(payload)


@router.put(
    "/anonymization-records/{record_id}",
    response_model=AnonymizationRecord,
    summary="Update an anonymization record",
)
async def update_anonymization_record(
    record_id: str, payload: AnonymizationRecordUpdate
) -> AnonymizationRecord:
    svc = get_data_privacy_service()
    updated = svc.update_anonymization_record(record_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Anonymization record '{record_id}' not found")
    return updated


@router.delete(
    "/anonymization-records/{record_id}",
    status_code=204,
    summary="Delete an anonymization record",
)
async def delete_anonymization_record(record_id: str) -> None:
    svc = get_data_privacy_service()
    deleted = svc.delete_anonymization_record(record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Anonymization record '{record_id}' not found")


# ---------------------------------------------------------------------------
# Data Subject Requests
# ---------------------------------------------------------------------------


@router.get(
    "/dsr",
    response_model=DataSubjectRequestListResponse,
    summary="List data subject requests",
    description="Retrieve DSRs with optional filtering by trial, request type, and status.",
)
async def list_dsr(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    request_type: Optional[DSRType] = Query(None, description="Filter by request type"),
    status: Optional[DSRStatus] = Query(None, description="Filter by status"),
) -> DataSubjectRequestListResponse:
    svc = get_data_privacy_service()
    items = svc.list_dsr(
        trial_id=trial_id,
        request_type=request_type,
        status=status,
    )
    return DataSubjectRequestListResponse(items=items, total=len(items))


@router.get(
    "/dsr/{record_id}",
    response_model=DataSubjectRequest,
    summary="Get a data subject request",
)
async def get_dsr(record_id: str) -> DataSubjectRequest:
    svc = get_data_privacy_service()
    rec = svc.get_dsr(record_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"DSR '{record_id}' not found")
    return rec


@router.post(
    "/dsr",
    response_model=DataSubjectRequest,
    status_code=201,
    summary="Create a data subject request",
)
async def create_dsr(payload: DataSubjectRequestCreate) -> DataSubjectRequest:
    svc = get_data_privacy_service()
    return svc.create_dsr(payload)


@router.put(
    "/dsr/{record_id}",
    response_model=DataSubjectRequest,
    summary="Update a data subject request",
)
async def update_dsr(record_id: str, payload: DataSubjectRequestUpdate) -> DataSubjectRequest:
    svc = get_data_privacy_service()
    updated = svc.update_dsr(record_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"DSR '{record_id}' not found")
    return updated


@router.delete(
    "/dsr/{record_id}",
    status_code=204,
    summary="Delete a data subject request",
)
async def delete_dsr(record_id: str) -> None:
    svc = get_data_privacy_service()
    deleted = svc.delete_dsr(record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"DSR '{record_id}' not found")


# ---------------------------------------------------------------------------
# Privacy Impact Assessments
# ---------------------------------------------------------------------------


@router.get(
    "/pia",
    response_model=PrivacyImpactAssessmentListResponse,
    summary="List privacy impact assessments",
    description="Retrieve PIAs with optional filtering by trial, status, and risk level.",
)
async def list_pia(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[PIAStatus] = Query(None, description="Filter by PIA status"),
    risk_level: Optional[str] = Query(None, description="Filter by risk level"),
) -> PrivacyImpactAssessmentListResponse:
    svc = get_data_privacy_service()
    items = svc.list_pia(
        trial_id=trial_id,
        status=status,
        risk_level=risk_level,
    )
    return PrivacyImpactAssessmentListResponse(items=items, total=len(items))


@router.get(
    "/pia/{record_id}",
    response_model=PrivacyImpactAssessment,
    summary="Get a privacy impact assessment",
)
async def get_pia(record_id: str) -> PrivacyImpactAssessment:
    svc = get_data_privacy_service()
    rec = svc.get_pia(record_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"PIA '{record_id}' not found")
    return rec


@router.post(
    "/pia",
    response_model=PrivacyImpactAssessment,
    status_code=201,
    summary="Create a privacy impact assessment",
)
async def create_pia(payload: PrivacyImpactAssessmentCreate) -> PrivacyImpactAssessment:
    svc = get_data_privacy_service()
    return svc.create_pia(payload)


@router.put(
    "/pia/{record_id}",
    response_model=PrivacyImpactAssessment,
    summary="Update a privacy impact assessment",
)
async def update_pia(
    record_id: str, payload: PrivacyImpactAssessmentUpdate
) -> PrivacyImpactAssessment:
    svc = get_data_privacy_service()
    updated = svc.update_pia(record_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"PIA '{record_id}' not found")
    return updated


@router.delete(
    "/pia/{record_id}",
    status_code=204,
    summary="Delete a privacy impact assessment",
)
async def delete_pia(record_id: str) -> None:
    svc = get_data_privacy_service()
    deleted = svc.delete_pia(record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"PIA '{record_id}' not found")


# ---------------------------------------------------------------------------
# Data Retention Policies
# ---------------------------------------------------------------------------


@router.get(
    "/retention-policies",
    response_model=DataRetentionPolicyListResponse,
    summary="List data retention policies",
    description="Retrieve retention policies with optional filtering by trial, active status, and data category.",
)
async def list_retention_policies(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    data_category: Optional[str] = Query(None, description="Filter by data category"),
) -> DataRetentionPolicyListResponse:
    svc = get_data_privacy_service()
    items = svc.list_retention_policies(
        trial_id=trial_id,
        is_active=is_active,
        data_category=data_category,
    )
    return DataRetentionPolicyListResponse(items=items, total=len(items))


@router.get(
    "/retention-policies/{record_id}",
    response_model=DataRetentionPolicy,
    summary="Get a data retention policy",
)
async def get_retention_policy(record_id: str) -> DataRetentionPolicy:
    svc = get_data_privacy_service()
    rec = svc.get_retention_policy(record_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"Retention policy '{record_id}' not found")
    return rec


@router.post(
    "/retention-policies",
    response_model=DataRetentionPolicy,
    status_code=201,
    summary="Create a data retention policy",
)
async def create_retention_policy(payload: DataRetentionPolicyCreate) -> DataRetentionPolicy:
    svc = get_data_privacy_service()
    return svc.create_retention_policy(payload)


@router.put(
    "/retention-policies/{record_id}",
    response_model=DataRetentionPolicy,
    summary="Update a data retention policy",
)
async def update_retention_policy(
    record_id: str, payload: DataRetentionPolicyUpdate
) -> DataRetentionPolicy:
    svc = get_data_privacy_service()
    updated = svc.update_retention_policy(record_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Retention policy '{record_id}' not found")
    return updated


@router.delete(
    "/retention-policies/{record_id}",
    status_code=204,
    summary="Delete a data retention policy",
)
async def delete_retention_policy(record_id: str) -> None:
    svc = get_data_privacy_service()
    deleted = svc.delete_retention_policy(record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Retention policy '{record_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=DataPrivacyMetrics,
    summary="Get data privacy metrics",
    description="Retrieve comprehensive data privacy compliance metrics across all entities.",
)
async def get_metrics() -> DataPrivacyMetrics:
    svc = get_data_privacy_service()
    return svc.get_metrics()
