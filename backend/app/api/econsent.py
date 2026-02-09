"""Electronic Informed Consent (eConsent) Management API endpoints (CLINICAL-18).

Provides comprehensive eConsent operations: consent document management with
versioned elements, patient consent lifecycle tracking, 21 CFR Part 11 compliant
audit trails, quiz-based comprehension verification with 80% pass threshold,
electronic signature capture, withdrawal management with data retention preferences,
re-consent tracking for protocol amendments, comprehension analytics, and
multi-language support.

Endpoints:
    GET    /econsent/documents                                  - List consent documents
    GET    /econsent/documents/{document_id}                    - Get single document
    POST   /econsent/documents                                  - Create document
    PUT    /econsent/documents/{document_id}                    - Update document
    DELETE /econsent/documents/{document_id}                    - Delete document
    POST   /econsent/documents/{document_id}/elements           - Add element to document
    GET    /econsent/consents                                   - List patient consents
    GET    /econsent/consents/{consent_id}                      - Get single consent
    POST   /econsent/consents                                   - Create patient consent
    PUT    /econsent/consents/{consent_id}                      - Update patient consent
    POST   /econsent/consents/{consent_id}/sign                 - Sign consent
    POST   /econsent/consents/{consent_id}/view-element         - Record element view
    POST   /econsent/consents/{consent_id}/complete-element     - Record element completion
    POST   /econsent/consents/{consent_id}/withdraw             - Withdraw consent
    GET    /econsent/withdrawals                                - List withdrawals
    GET    /econsent/withdrawals/{withdrawal_id}                - Get single withdrawal
    GET    /econsent/audit                                      - List audit entries
    GET    /econsent/audit/{audit_id}                           - Get single audit entry
    GET    /econsent/re-consent-pending                         - Get re-consent pending list
    GET    /econsent/comprehension-analytics                    - Comprehension analytics
    GET    /econsent/metrics                                    - eConsent dashboard metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.econsent import (
    ComprehensionAnalytics,
    CompleteElementRequest,
    ConsentAuditAction,
    ConsentAuditEntry,
    ConsentAuditListResponse,
    ConsentDocument,
    ConsentDocumentCreate,
    ConsentDocumentListResponse,
    ConsentDocumentUpdate,
    ConsentElementCreate,
    ConsentSignRequest,
    ConsentStatus,
    ConsentType,
    ConsentWithdrawal,
    ConsentWithdrawalCreate,
    ConsentWithdrawalListResponse,
    DocumentLanguage,
    EConsentMetrics,
    PatientConsent,
    PatientConsentCreate,
    PatientConsentListResponse,
    PatientConsentUpdate,
    ViewElementRequest,
)
from app.services.econsent_service import get_econsent_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/econsent",
    tags=["Electronic Consent"],
)


# ---------------------------------------------------------------------------
# Document Management
# ---------------------------------------------------------------------------


@router.get(
    "/documents",
    response_model=ConsentDocumentListResponse,
    summary="List consent documents",
    description="Retrieve consent documents with optional filtering by trial, type, and language.",
)
async def list_documents(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    consent_type: Optional[ConsentType] = Query(None, description="Filter by consent type"),
    language: Optional[DocumentLanguage] = Query(None, description="Filter by language"),
) -> ConsentDocumentListResponse:
    svc = get_econsent_service()
    items = svc.list_documents(trial_id=trial_id, consent_type=consent_type, language=language)
    return ConsentDocumentListResponse(items=items, total=len(items))


@router.get(
    "/documents/{document_id}",
    response_model=ConsentDocument,
    summary="Get a consent document",
)
async def get_document(document_id: str) -> ConsentDocument:
    svc = get_econsent_service()
    doc = svc.get_document(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")
    return doc


@router.post(
    "/documents",
    response_model=ConsentDocument,
    status_code=201,
    summary="Create a consent document",
)
async def create_document(payload: ConsentDocumentCreate) -> ConsentDocument:
    svc = get_econsent_service()
    return svc.create_document(payload)


@router.put(
    "/documents/{document_id}",
    response_model=ConsentDocument,
    summary="Update a consent document",
)
async def update_document(document_id: str, payload: ConsentDocumentUpdate) -> ConsentDocument:
    svc = get_econsent_service()
    updated = svc.update_document(document_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")
    return updated


@router.delete(
    "/documents/{document_id}",
    status_code=204,
    summary="Delete a consent document",
)
async def delete_document(document_id: str) -> None:
    svc = get_econsent_service()
    deleted = svc.delete_document(document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")


@router.post(
    "/documents/{document_id}/elements",
    response_model=ConsentDocument,
    status_code=201,
    summary="Add an element to a consent document",
    description="Add a text, video, quiz, signature, checkbox, or acknowledgment element.",
)
async def add_element(document_id: str, payload: ConsentElementCreate) -> ConsentDocument:
    svc = get_econsent_service()
    result = svc.add_element_to_document(document_id, payload)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Patient Consent Management
# ---------------------------------------------------------------------------


@router.get(
    "/consents",
    response_model=PatientConsentListResponse,
    summary="List patient consents",
    description="Retrieve patient consents with optional filtering by patient, trial, site, status, and document.",
)
async def list_consents(
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    status: Optional[ConsentStatus] = Query(None, description="Filter by status"),
    document_id: Optional[str] = Query(None, description="Filter by document ID"),
) -> PatientConsentListResponse:
    svc = get_econsent_service()
    items = svc.list_consents(
        patient_id=patient_id, trial_id=trial_id, site_id=site_id,
        status=status, document_id=document_id,
    )
    return PatientConsentListResponse(items=items, total=len(items))


@router.get(
    "/consents/{consent_id}",
    response_model=PatientConsent,
    summary="Get a patient consent",
)
async def get_consent(consent_id: str) -> PatientConsent:
    svc = get_econsent_service()
    consent = svc.get_consent(consent_id)
    if consent is None:
        raise HTTPException(status_code=404, detail=f"Consent '{consent_id}' not found")
    return consent


@router.post(
    "/consents",
    response_model=PatientConsent,
    status_code=201,
    summary="Create a patient consent record",
)
async def create_consent(payload: PatientConsentCreate) -> PatientConsent:
    svc = get_econsent_service()
    return svc.create_consent(payload)


@router.put(
    "/consents/{consent_id}",
    response_model=PatientConsent,
    summary="Update a patient consent",
)
async def update_consent(consent_id: str, payload: PatientConsentUpdate) -> PatientConsent:
    svc = get_econsent_service()
    updated = svc.update_consent(consent_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Consent '{consent_id}' not found")
    return updated


@router.post(
    "/consents/{consent_id}/sign",
    response_model=PatientConsent,
    summary="Sign a patient consent",
    description="Sign a consent with 21 CFR Part 11 compliance. Validates quiz answers "
                "against 80% pass threshold. Records IP, device, and timestamp.",
)
async def sign_consent(consent_id: str, payload: ConsentSignRequest) -> PatientConsent:
    svc = get_econsent_service()
    try:
        result = svc.sign_consent(consent_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Consent '{consent_id}' not found")
    return result


@router.post(
    "/consents/{consent_id}/view-element",
    response_model=PatientConsent,
    summary="Record element view",
    description="Record that a patient has viewed a specific consent element.",
)
async def view_element(consent_id: str, payload: ViewElementRequest) -> PatientConsent:
    svc = get_econsent_service()
    result = svc.view_element(consent_id, payload)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Consent '{consent_id}' not found")
    return result


@router.post(
    "/consents/{consent_id}/complete-element",
    response_model=PatientConsent,
    summary="Record element completion",
    description="Record that a patient has completed a consent element (checkbox, quiz answer, etc.).",
)
async def complete_element(consent_id: str, payload: CompleteElementRequest) -> PatientConsent:
    svc = get_econsent_service()
    result = svc.complete_element(consent_id, payload)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Consent '{consent_id}' not found")
    return result


@router.post(
    "/consents/{consent_id}/withdraw",
    response_model=ConsentWithdrawal,
    summary="Withdraw consent",
    description="Withdraw a patient's consent with data retention preference and specimen disposition.",
)
async def withdraw_consent(consent_id: str, payload: ConsentWithdrawalCreate) -> ConsentWithdrawal:
    svc = get_econsent_service()
    try:
        result = svc.withdraw_consent(consent_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Consent '{consent_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Withdrawal Management
# ---------------------------------------------------------------------------


@router.get(
    "/withdrawals",
    response_model=ConsentWithdrawalListResponse,
    summary="List consent withdrawals",
    description="Retrieve consent withdrawals with optional patient filter.",
)
async def list_withdrawals(
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
) -> ConsentWithdrawalListResponse:
    svc = get_econsent_service()
    items = svc.list_withdrawals(patient_id=patient_id)
    return ConsentWithdrawalListResponse(items=items, total=len(items))


@router.get(
    "/withdrawals/{withdrawal_id}",
    response_model=ConsentWithdrawal,
    summary="Get a consent withdrawal",
)
async def get_withdrawal(withdrawal_id: str) -> ConsentWithdrawal:
    svc = get_econsent_service()
    wd = svc.get_withdrawal(withdrawal_id)
    if wd is None:
        raise HTTPException(status_code=404, detail=f"Withdrawal '{withdrawal_id}' not found")
    return wd


# ---------------------------------------------------------------------------
# Audit Trail (21 CFR Part 11)
# ---------------------------------------------------------------------------


@router.get(
    "/audit",
    response_model=ConsentAuditListResponse,
    summary="List consent audit entries",
    description="21 CFR Part 11 compliant audit trail. Filter by consent ID or action type.",
)
async def list_audit_entries(
    patient_consent_id: Optional[str] = Query(None, description="Filter by consent ID"),
    action: Optional[ConsentAuditAction] = Query(None, description="Filter by action type"),
) -> ConsentAuditListResponse:
    svc = get_econsent_service()
    items = svc.list_audit_entries(patient_consent_id=patient_consent_id, action=action)
    return ConsentAuditListResponse(items=items, total=len(items))


@router.get(
    "/audit/{audit_id}",
    response_model=ConsentAuditEntry,
    summary="Get a consent audit entry",
)
async def get_audit_entry(audit_id: str) -> ConsentAuditEntry:
    svc = get_econsent_service()
    entry = svc.get_audit_entry(audit_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Audit entry '{audit_id}' not found")
    return entry


# ---------------------------------------------------------------------------
# Re-consent & Analytics
# ---------------------------------------------------------------------------


@router.get(
    "/re-consent-pending",
    response_model=PatientConsentListResponse,
    summary="Get patients pending re-consent",
    description="List patients who need re-consent due to protocol amendments.",
)
async def get_re_consent_pending(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> PatientConsentListResponse:
    svc = get_econsent_service()
    items = svc.get_re_consent_pending(trial_id=trial_id)
    return PatientConsentListResponse(items=items, total=len(items))


@router.get(
    "/comprehension-analytics",
    response_model=ComprehensionAnalytics,
    summary="Get comprehension analytics",
    description="Quiz performance analytics including pass rates, score distribution, and time spent.",
)
async def get_comprehension_analytics(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> ComprehensionAnalytics:
    svc = get_econsent_service()
    return svc.get_comprehension_analytics(trial_id=trial_id)


# ---------------------------------------------------------------------------
# Metrics & Dashboard
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=EConsentMetrics,
    summary="Get eConsent dashboard metrics",
    description="Aggregated eConsent metrics: documents, consents by status, quiz scores, "
                "withdrawal rates, re-consent pending, and language distribution.",
)
async def get_metrics() -> EConsentMetrics:
    svc = get_econsent_service()
    return svc.get_metrics()
