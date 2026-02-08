"""Consent Management API endpoints.

HIPAA-compliant consent management for patient PHI access control.

Endpoints:
    POST /api/v1/consent                              - Record new consent
    GET  /api/v1/consent/patients/{patient_id}         - Get all patient consents
    GET  /api/v1/consent/check/{patient_id}/{consent_type} - Check consent status
    POST /api/v1/consent/revoke                        - Revoke consent
    GET  /api/v1/consent/audit/{patient_id}            - Get consent audit trail
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.schemas.consent import (
    ConsentAuditTrail,
    ConsentCheck,
    ConsentRecord,
    ConsentRecordRequest,
    ConsentRevokeRequest,
    ConsentStatus,
    ConsentType,
    DataUsePurpose,
)
from app.services.consent_service import get_consent_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/consent", tags=["Consent Management"])


# ==============================================================================
# Record consent
# ==============================================================================


@router.post(
    "",
    response_model=ConsentRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Record a new consent",
    description=(
        "Record a patient's consent for a specific type (HIPAA authorization, "
        "research participation, screening, or data sharing). If a consent of "
        "the same type already exists, it is superseded."
    ),
)
async def record_consent(request: ConsentRecordRequest) -> ConsentRecord:
    """Record a new consent for a patient."""
    svc = get_consent_service()
    record = svc.record_consent(
        patient_id=request.patient_id,
        consent_type=request.consent_type,
        scope=request.scope,
        granted_by=request.granted_by,
        expires_at=request.expires_at,
    )
    return record


# ==============================================================================
# Get patient consents
# ==============================================================================


@router.get(
    "/patients/{patient_id}",
    response_model=list[ConsentRecord],
    summary="Get all consents for a patient",
    description="Retrieve all consent records (active, revoked, expired) for a patient.",
)
async def get_patient_consents(patient_id: str) -> list[ConsentRecord]:
    """Get all consent records for a patient."""
    svc = get_consent_service()
    return svc.get_patient_consents(patient_id)


# ==============================================================================
# Check consent status
# ==============================================================================


@router.get(
    "/check/{patient_id}/{consent_type}",
    response_model=ConsentStatus,
    summary="Check consent status",
    description=(
        "Check the current status of a specific consent type for a patient. "
        "Returns active, expired, revoked, or not_found."
    ),
)
async def check_consent(patient_id: str, consent_type: ConsentType) -> ConsentStatus:
    """Check consent status for a patient and consent type."""
    svc = get_consent_service()
    return svc.check_consent(patient_id, consent_type)


# ==============================================================================
# Revoke consent
# ==============================================================================


@router.post(
    "/revoke",
    response_model=ConsentRecord,
    summary="Revoke a consent",
    description=(
        "Revoke an existing consent. Revocation is effective immediately "
        "and applies prospectively only (does not undo prior uses)."
    ),
)
async def revoke_consent(request: ConsentRevokeRequest) -> ConsentRecord:
    """Revoke a patient's consent."""
    svc = get_consent_service()
    try:
        record = svc.revoke_consent(
            patient_id=request.patient_id,
            consent_type=request.consent_type,
            revoked_by=request.revoked_by,
            reason=request.reason,
        )
        return record
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


# ==============================================================================
# Consent audit trail
# ==============================================================================


@router.get(
    "/audit/{patient_id}",
    response_model=ConsentAuditTrail,
    summary="Get consent audit trail",
    description=(
        "Retrieve the full consent audit trail for a patient, including all "
        "consent grants, revocations, checks, and expirations."
    ),
)
async def get_consent_audit_trail(patient_id: str) -> ConsentAuditTrail:
    """Get the consent audit trail for a patient."""
    svc = get_consent_service()
    return svc.get_consent_audit_trail(patient_id)


# ==============================================================================
# Data use authorization check
# ==============================================================================


@router.get(
    "/authorize/{patient_id}/{purpose}",
    response_model=ConsentCheck,
    summary="Check data use authorization",
    description=(
        "Check whether a specific data use purpose is authorized for a patient "
        "based on their active consents. Used to enforce the minimum necessary "
        "standard and purpose limitation."
    ),
)
async def check_data_use_authorization(
    patient_id: str, purpose: DataUsePurpose
) -> ConsentCheck:
    """Check if a data use purpose is authorized for a patient."""
    svc = get_consent_service()
    return svc.get_data_use_check(patient_id, purpose)
