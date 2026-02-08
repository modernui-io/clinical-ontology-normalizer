"""Patient Consent Preference Center API (VP-Product-7).

Comprehensive consent preference management endpoints for pharma-regulated
clinical trial recruitment. Provides profile CRUD, preference updates,
withdrawals, audit trails, consent checks, template management, consent
export for data portability, and program-wide metrics.

Endpoints:
    GET  /consent-preferences/profiles                      - List profiles
    GET  /consent-preferences/profiles/{patient_id}         - Get profile
    PUT  /consent-preferences/profiles/{patient_id}/preferences  - Update preference
    PUT  /consent-preferences/profiles/{patient_id}/preferences/bulk - Bulk update
    POST /consent-preferences/profiles/{patient_id}/withdraw/{category} - Withdraw category
    POST /consent-preferences/profiles/{patient_id}/withdraw-all       - Withdraw all
    GET  /consent-preferences/profiles/{patient_id}/audit              - Audit trail
    GET  /consent-preferences/profiles/{patient_id}/audit/{category}   - Audit by category
    GET  /consent-preferences/check/{patient_id}/{category}            - Consent check
    GET  /consent-preferences/check/{patient_id}/{category}/{channel}  - Consent + channel check
    GET  /consent-preferences/expiring                      - Expiring consents
    GET  /consent-preferences/metrics                       - Program metrics
    GET  /consent-preferences/templates                     - List templates
    GET  /consent-preferences/templates/{template_id}       - Get template
    POST /consent-preferences/profiles/{patient_id}/apply-template     - Apply template
    GET  /consent-preferences/profiles/{patient_id}/export             - Export record
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.consent_preferences import (
    ApplyTemplateRequest,
    BulkPreferenceUpdateRequest,
    ConsentCategory,
    ConsentCheckResponse,
    ConsentExportRecord,
    ConsentMetrics,
    ConsentPreference,
    ConsentPreferenceAuditEntry,
    ConsentTemplate,
    ExpiringConsentsResponse,
    OverallConsentStatus,
    PreferenceProfile,
    PreferenceUpdateRequest,
    ProfileListResponse,
    WithdrawAllConsentRequest,
    WithdrawConsentRequest,
)
from app.services.consent_preferences_service import get_consent_preferences_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/consent-preferences", tags=["Consent Preferences"])


# ==============================================================================
# Profile endpoints
# ==============================================================================


@router.get(
    "/profiles",
    response_model=ProfileListResponse,
    summary="List consent preference profiles",
    description="List all patient consent preference profiles with optional status filter and pagination.",
)
async def list_profiles(
    status_filter: OverallConsentStatus | None = Query(
        default=None,
        alias="status",
        description="Filter by overall consent status",
    ),
    limit: int = Query(default=20, ge=1, le=100, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Page offset"),
) -> ProfileListResponse:
    """List consent preference profiles."""
    svc = get_consent_preferences_service()
    profiles, total = svc.list_profiles(status=status_filter, limit=limit, offset=offset)
    return ProfileListResponse(
        profiles=profiles,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/profiles/{patient_id}",
    response_model=PreferenceProfile,
    summary="Get patient consent preference profile",
    description="Get the full consent preference profile for a specific patient.",
)
async def get_profile(patient_id: str) -> PreferenceProfile:
    """Get a patient's consent preference profile."""
    svc = get_consent_preferences_service()
    try:
        return svc.get_profile(patient_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient profile not found: {patient_id}",
        )


# ==============================================================================
# Preference update endpoints
# ==============================================================================


@router.put(
    "/profiles/{patient_id}/preferences",
    response_model=ConsentPreference,
    summary="Update a single consent preference",
    description="Update or create a consent preference for a specific category.",
)
async def update_preference(
    patient_id: str,
    request: PreferenceUpdateRequest,
) -> ConsentPreference:
    """Update a single consent preference."""
    svc = get_consent_preferences_service()
    return svc.update_preference(
        patient_id=patient_id,
        category=request.category,
        status=request.status,
        channel_prefs=request.channel_preferences,
        source=request.source,
        grantor=request.grantor,
        ip_address=request.ip_address,
    )


@router.put(
    "/profiles/{patient_id}/preferences/bulk",
    response_model=PreferenceProfile,
    summary="Bulk update consent preferences",
    description="Update multiple consent preferences at once for a patient.",
)
async def bulk_update_preferences(
    patient_id: str,
    request: BulkPreferenceUpdateRequest,
) -> PreferenceProfile:
    """Bulk update consent preferences."""
    svc = get_consent_preferences_service()
    prefs_data = [
        {
            "category": p.category,
            "status": p.status,
            "channel_preferences": p.channel_preferences,
            "source": p.source,
            "grantor": p.grantor,
            "ip_address": p.ip_address,
        }
        for p in request.preferences
    ]
    return svc.bulk_update_preferences(patient_id=patient_id, preferences=prefs_data)


# ==============================================================================
# Withdrawal endpoints
# ==============================================================================


@router.post(
    "/profiles/{patient_id}/withdraw/{category}",
    response_model=ConsentPreference,
    summary="Withdraw consent for a category",
    description="Withdraw consent for a specific category with a required reason.",
)
async def withdraw_consent(
    patient_id: str,
    category: ConsentCategory,
    request: WithdrawConsentRequest,
) -> ConsentPreference:
    """Withdraw consent for a specific category."""
    svc = get_consent_preferences_service()
    try:
        return svc.withdraw_consent(
            patient_id=patient_id,
            category=category,
            reason=request.reason,
        )
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient profile not found: {patient_id}",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/profiles/{patient_id}/withdraw-all",
    response_model=PreferenceProfile,
    summary="Withdraw all consent",
    description="Withdraw consent across all categories for a patient with a required reason.",
)
async def withdraw_all_consent(
    patient_id: str,
    request: WithdrawAllConsentRequest,
) -> PreferenceProfile:
    """Withdraw all consent for a patient."""
    svc = get_consent_preferences_service()
    try:
        return svc.withdraw_all_consent(
            patient_id=patient_id,
            reason=request.reason,
        )
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient profile not found: {patient_id}",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ==============================================================================
# Audit trail endpoints
# ==============================================================================


@router.get(
    "/profiles/{patient_id}/audit",
    response_model=list[ConsentPreferenceAuditEntry],
    summary="Get consent audit trail",
    description="Get the consent change audit trail for a patient.",
)
async def get_audit_trail(
    patient_id: str,
    limit: int = Query(default=50, ge=1, le=500, description="Max entries"),
) -> list[ConsentPreferenceAuditEntry]:
    """Get the audit trail for a patient."""
    svc = get_consent_preferences_service()
    return svc.get_audit_trail(patient_id=patient_id, limit=limit)


@router.get(
    "/profiles/{patient_id}/audit/{category}",
    response_model=list[ConsentPreferenceAuditEntry],
    summary="Get consent audit trail by category",
    description="Get the consent change audit trail for a patient filtered by category.",
)
async def get_audit_trail_by_category(
    patient_id: str,
    category: ConsentCategory,
    limit: int = Query(default=50, ge=1, le=500, description="Max entries"),
) -> list[ConsentPreferenceAuditEntry]:
    """Get the audit trail for a patient filtered by category."""
    svc = get_consent_preferences_service()
    return svc.get_audit_trail(patient_id=patient_id, category=category, limit=limit)


# ==============================================================================
# Consent check endpoints
# ==============================================================================


@router.get(
    "/check/{patient_id}/{category}",
    response_model=ConsentCheckResponse,
    summary="Check consent status",
    description="Quick check whether a patient has consented to a specific category.",
)
async def check_consent(
    patient_id: str,
    category: ConsentCategory,
) -> ConsentCheckResponse:
    """Check consent for a category."""
    svc = get_consent_preferences_service()
    return svc.check_consent(patient_id=patient_id, category=category)


@router.get(
    "/check/{patient_id}/{category}/{channel}",
    response_model=ConsentCheckResponse,
    summary="Check consent status with channel",
    description="Quick check whether a patient has consented to a specific category and channel.",
)
async def check_consent_with_channel(
    patient_id: str,
    category: ConsentCategory,
    channel: str,
) -> ConsentCheckResponse:
    """Check consent for a category and channel."""
    svc = get_consent_preferences_service()
    return svc.check_consent(patient_id=patient_id, category=category, channel=channel)


# ==============================================================================
# Expiring consents
# ==============================================================================


@router.get(
    "/expiring",
    response_model=ExpiringConsentsResponse,
    summary="Get expiring consents",
    description="Get consents that will expire within the specified number of days.",
)
async def get_expiring_consents(
    days_ahead: int = Query(default=30, ge=1, le=365, description="Look-ahead window in days"),
) -> ExpiringConsentsResponse:
    """Get consents expiring within N days."""
    svc = get_consent_preferences_service()
    items = svc.get_expiring_consents(days_ahead=days_ahead)
    return ExpiringConsentsResponse(
        items=items,
        total=len(items),
        days_ahead=days_ahead,
    )


# ==============================================================================
# Metrics
# ==============================================================================


@router.get(
    "/metrics",
    response_model=ConsentMetrics,
    summary="Get consent metrics",
    description="Get program-wide consent metrics including rates and trends.",
)
async def get_metrics() -> ConsentMetrics:
    """Get program-wide consent metrics."""
    svc = get_consent_preferences_service()
    return svc.get_metrics()


# ==============================================================================
# Template endpoints
# ==============================================================================


@router.get(
    "/templates",
    response_model=list[ConsentTemplate],
    summary="List consent templates",
    description="List all available consent templates.",
)
async def list_templates() -> list[ConsentTemplate]:
    """List all consent templates."""
    svc = get_consent_preferences_service()
    return svc.get_templates()


@router.get(
    "/templates/{template_id}",
    response_model=ConsentTemplate,
    summary="Get consent template",
    description="Get a specific consent template by ID.",
)
async def get_template(template_id: str) -> ConsentTemplate:
    """Get a specific consent template."""
    svc = get_consent_preferences_service()
    try:
        return svc.get_template(template_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template not found: {template_id}",
        )


# ==============================================================================
# Apply template
# ==============================================================================


@router.post(
    "/profiles/{patient_id}/apply-template",
    response_model=PreferenceProfile,
    summary="Apply consent template to patient",
    description="Apply a consent template, opting the patient into all template categories.",
)
async def apply_template(
    patient_id: str,
    request: ApplyTemplateRequest,
) -> PreferenceProfile:
    """Apply a consent template to a patient."""
    svc = get_consent_preferences_service()
    try:
        return svc.apply_template(
            patient_id=patient_id,
            template_id=request.template_id,
            source=request.source,
            grantor=request.grantor,
            ip_address=request.ip_address,
        )
    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# ==============================================================================
# Export
# ==============================================================================


@router.get(
    "/profiles/{patient_id}/export",
    response_model=ConsentExportRecord,
    summary="Export consent record",
    description="Export the full consent record for a patient for data portability.",
)
async def export_consent_record(patient_id: str) -> ConsentExportRecord:
    """Export the full consent record for a patient."""
    svc = get_consent_preferences_service()
    try:
        return svc.export_consent_record(patient_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient profile not found: {patient_id}",
        )
