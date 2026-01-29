"""TEFCA (Trusted Exchange Framework and Common Agreement) API endpoints.

Provides RESTful endpoints for health information exchange:
- QHIN discovery and status
- Patient discovery (IHE PDQm)
- Document query and retrieve (IHE MHD)
- Direct secure messaging
- Audit log access
- Consent management
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.tefca_service import (
    AuditEventType,
    AuditLog,
    ClinicalDocument,
    ConsentStatus,
    DirectMessage,
    DirectMessageStatus,
    DocumentClass,
    DocumentQueryResponse,
    DocumentReference,
    ExchangePurpose,
    MatchConfidence,
    PatientConsent,
    PatientDemographics,
    PatientMatch,
    QHIN,
    QHINStatus,
    QueryResponse,
    SendResult,
    TEFCAQuery,
    ValidationResult,
    get_tefca_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tefca", tags=["tefca"])


# ============================================================================
# Request/Response Models
# ============================================================================

class QHINListResponse(BaseModel):
    """Response for QHIN list."""

    total: int = Field(..., description="Total number of QHINs")
    qhins: list[QHIN] = Field(..., description="List of QHINs")
    timestamp: datetime = Field(..., description="Response timestamp")


class PatientSearchRequest(BaseModel):
    """Request for patient search."""

    # Demographics
    family_name: str = Field(..., description="Patient family/last name", min_length=1)
    given_name: str | None = Field(None, description="Patient given/first name")
    birth_date: str | None = Field(None, description="Birth date (YYYY-MM-DD)")
    gender: str | None = Field(None, description="Gender (male/female/other)")
    address_line: str | None = Field(None, description="Street address")
    city: str | None = Field(None, description="City")
    state: str | None = Field(None, description="State (2-letter code)")
    postal_code: str | None = Field(None, description="ZIP code")
    ssn_last_four: str | None = Field(None, description="Last 4 of SSN")
    mrn: str | None = Field(None, description="MRN")
    phone: str | None = Field(None, description="Phone number")
    email: str | None = Field(None, description="Email address")

    # Query parameters
    purpose: ExchangePurpose = Field(
        ExchangePurpose.TREATMENT,
        description="Purpose of use",
    )
    qhin_filter: list[str] | None = Field(None, description="Filter to specific QHINs")


class DocumentQueryRequest(BaseModel):
    """Request for document query."""

    patient_id: str = Field(..., description="Patient identifier")
    source_qhin: str | None = Field(None, description="Source QHIN from patient match")
    purpose: ExchangePurpose = Field(ExchangePurpose.TREATMENT, description="Purpose of use")
    qhin_filter: list[str] | None = Field(None, description="Filter to specific QHINs")
    document_types: list[DocumentClass] | None = Field(None, description="Document type filter")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")


class DocumentRetrieveRequest(BaseModel):
    """Request for document retrieval."""

    patient_id: str = Field(..., description="Patient identifier")
    document_refs: list[str] = Field(..., description="Document reference IDs to retrieve")
    purpose: ExchangePurpose = Field(ExchangePurpose.TREATMENT, description="Purpose of use")


class DocumentRetrieveResponse(BaseModel):
    """Response for document retrieval."""

    patient_id: str = Field(..., description="Patient identifier")
    documents: list[ClinicalDocument] = Field(..., description="Retrieved documents")
    total: int = Field(..., description="Total documents retrieved")
    timestamp: datetime = Field(..., description="Retrieval timestamp")


class DirectMessageRequest(BaseModel):
    """Request to send Direct message."""

    recipient_qhin: str = Field(..., description="Target QHIN")
    to_address: str = Field(..., description="Recipient Direct address")
    subject: str = Field(..., description="Message subject")
    body: str = Field(..., description="Message body")
    patient_id: str | None = Field(None, description="Related patient ID")
    attachments: list[dict[str, Any]] = Field(default_factory=list, description="Attachments")
    purpose: ExchangePurpose = Field(ExchangePurpose.TREATMENT, description="Purpose of use")


class AuditLogQuery(BaseModel):
    """Query parameters for audit log search."""

    patient_id: str | None = Field(None, description="Filter by patient")
    user_id: str | None = Field(None, description="Filter by user")
    event_type: AuditEventType | None = Field(None, description="Filter by event type")
    start_date: datetime | None = Field(None, description="Start date filter")
    end_date: datetime | None = Field(None, description="End date filter")


class AuditLogResponse(BaseModel):
    """Response for audit log query."""

    total: int = Field(..., description="Total matching logs")
    logs: list[AuditLog] = Field(..., description="Audit log entries")
    limit: int = Field(..., description="Page size")
    offset: int = Field(..., description="Page offset")


class ConsentRequest(BaseModel):
    """Request to set patient consent."""

    patient_id: str = Field(..., description="Patient identifier")
    status: ConsentStatus = Field(..., description="Consent status")
    scope: list[ExchangePurpose] = Field(
        default_factory=list,
        description="Permitted purposes",
    )
    includes_sensitive: bool = Field(False, description="Include sensitive records")
    effective_date: datetime | None = Field(None, description="Effective date")
    expiration_date: datetime | None = Field(None, description="Expiration date")
    excluded_organizations: list[str] = Field(default_factory=list, description="Excluded orgs")
    excluded_document_types: list[str] = Field(default_factory=list, description="Excluded types")


class SAMLValidationRequest(BaseModel):
    """Request to validate SAML assertion."""

    assertion: str = Field(..., description="Base64-encoded SAML assertion")


class ServiceStatusResponse(BaseModel):
    """Response for service status."""

    status: str = Field(..., description="Service status")
    total_qhins: int = Field(..., description="Total QHINs")
    active_qhins: int = Field(..., description="Active QHINs")
    total_participants: int = Field(..., description="Total participating organizations")
    audit_log_count: int = Field(..., description="Total audit logs")
    timestamp: datetime = Field(..., description="Status timestamp")


# ============================================================================
# QHIN Discovery Endpoints
# ============================================================================

@router.get("/qhins", response_model=QHINListResponse)
async def list_qhins(
    include_offline: bool = Query(False, description="Include offline QHINs"),
    capability: str | None = Query(None, description="Filter by capability"),
) -> QHINListResponse:
    """List all available Qualified Health Information Networks.

    Returns a list of QHINs with their current status, capabilities,
    and network information.
    """
    service = get_tefca_service()

    capability_filter = [capability] if capability else None
    qhins = service.discover_qhins(
        include_offline=include_offline,
        capability_filter=capability_filter,
    )

    return QHINListResponse(
        total=len(qhins),
        qhins=qhins,
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/qhins/{qhin_id}", response_model=QHIN)
async def get_qhin(qhin_id: str) -> QHIN:
    """Get details for a specific QHIN.

    Args:
        qhin_id: QHIN identifier
    """
    service = get_tefca_service()
    qhin = service.get_qhin(qhin_id)

    if not qhin:
        raise HTTPException(status_code=404, detail=f"QHIN {qhin_id} not found")

    return qhin


# ============================================================================
# Patient Discovery Endpoints
# ============================================================================

@router.post("/patient-discovery", response_model=QueryResponse)
async def search_patient(request: PatientSearchRequest) -> QueryResponse:
    """Search for patient records across QHINs.

    Implements IHE PDQm (Patient Demographics Query for Mobile) profile.
    Queries participating QHINs for patient matches based on demographics.
    """
    service = get_tefca_service()

    demographics = PatientDemographics(
        family_name=request.family_name,
        given_name=request.given_name,
        birth_date=request.birth_date,
        gender=request.gender,
        address_line=request.address_line,
        city=request.city,
        state=request.state,
        postal_code=request.postal_code,
        ssn_last_four=request.ssn_last_four,
        mrn=request.mrn,
        phone=request.phone,
        email=request.email,
    )

    query = TEFCAQuery(
        purpose=request.purpose,
        user_id="api-user",  # Would come from auth context
        organization="Clinical Ontology Normalizer",
        qhin_filter=request.qhin_filter,
    )

    response = service.query_patient(demographics, query)

    logger.info(
        f"Patient search for '{request.family_name}': "
        f"{response.total_matches} matches from {len(response.qhins_responded)} QHINs"
    )

    return response


# ============================================================================
# Document Query/Retrieve Endpoints
# ============================================================================

@router.post("/document-query", response_model=DocumentQueryResponse)
async def query_documents(request: DocumentQueryRequest) -> DocumentQueryResponse:
    """Query for documents for a patient.

    Implements IHE MHD (Mobile access to Health Documents) profile.
    Returns document references that can be retrieved.
    """
    service = get_tefca_service()

    # Build patient match if we have source QHIN
    patient_match = None
    if request.source_qhin:
        patient_match = PatientMatch(
            id=request.patient_id,
            source_qhin=request.source_qhin,
            source_organization="",
            confidence=MatchConfidence.HIGH,
            confidence_score=0.9,
            family_name="",
            given_name="",
        )

    query = TEFCAQuery(
        purpose=request.purpose,
        user_id="api-user",
        organization="Clinical Ontology Normalizer",
        qhin_filter=request.qhin_filter or ([request.source_qhin] if request.source_qhin else None),
        date_range_start=request.date_from,
        date_range_end=request.date_to,
        document_types=request.document_types,
    )

    response = service.query_documents(
        patient_id=request.patient_id,
        query=query,
        patient_match=patient_match,
    )

    logger.info(
        f"Document query for patient {request.patient_id}: "
        f"{response.total_documents} documents"
    )

    return response


@router.post("/document-retrieve", response_model=DocumentRetrieveResponse)
async def retrieve_documents(request: DocumentRetrieveRequest) -> DocumentRetrieveResponse:
    """Retrieve clinical documents from QHINs.

    Implements IHE XDS.b retrieve document set.
    Returns the actual document content (C-CDA, etc.).
    """
    service = get_tefca_service()

    if not request.document_refs:
        raise HTTPException(status_code=400, detail="At least one document reference required")

    query = TEFCAQuery(
        purpose=request.purpose,
        user_id="api-user",
        organization="Clinical Ontology Normalizer",
    )

    documents = service.retrieve_documents(
        patient_id=request.patient_id,
        document_refs=request.document_refs,
        query=query,
    )

    logger.info(
        f"Retrieved {len(documents)} documents for patient {request.patient_id}"
    )

    return DocumentRetrieveResponse(
        patient_id=request.patient_id,
        documents=documents,
        total=len(documents),
        timestamp=datetime.now(timezone.utc),
    )


# ============================================================================
# Direct Messaging Endpoints
# ============================================================================

@router.post("/direct-message", response_model=SendResult)
async def send_direct_message(request: DirectMessageRequest) -> SendResult:
    """Send a Direct secure message.

    Sends a message to a recipient at a specified QHIN using
    the Direct messaging protocol.
    """
    service = get_tefca_service()

    message = DirectMessage(
        to_address=request.to_address,
        from_address="sender@clinicalontology.example.com",  # From config
        subject=request.subject,
        body=request.body,
        attachments=request.attachments,
        patient_id=request.patient_id,
        purpose=request.purpose,
    )

    query = TEFCAQuery(
        purpose=request.purpose,
        user_id="api-user",
        organization="Clinical Ontology Normalizer",
    )

    result = service.send_message(
        recipient_qhin=request.recipient_qhin,
        message=message,
        query=query,
    )

    if result.status == DirectMessageStatus.FAILED:
        raise HTTPException(status_code=400, detail=result.error_message)

    logger.info(f"Direct message {result.message_id} sent to {request.to_address}")

    return result


# ============================================================================
# Audit Log Endpoints
# ============================================================================

@router.get("/audit-logs", response_model=AuditLogResponse)
async def get_audit_logs(
    patient_id: str | None = Query(None, description="Filter by patient"),
    user_id: str | None = Query(None, description="Filter by user"),
    event_type: AuditEventType | None = Query(None, description="Event type filter"),
    start_date: datetime | None = Query(None, description="Start date"),
    end_date: datetime | None = Query(None, description="End date"),
    limit: int = Query(100, ge=1, le=1000, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> AuditLogResponse:
    """Get audit logs for health information exchange activities.

    Returns ATNA-compliant audit logs for TEFCA exchange activities.
    """
    service = get_tefca_service()

    logs = service.get_audit_logs(
        patient_id=patient_id,
        user_id=user_id,
        event_type=event_type,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )

    # Get total count (without pagination)
    all_logs = service.get_audit_logs(
        patient_id=patient_id,
        user_id=user_id,
        event_type=event_type,
        start_date=start_date,
        end_date=end_date,
        limit=10000,
        offset=0,
    )

    return AuditLogResponse(
        total=len(all_logs),
        logs=logs,
        limit=limit,
        offset=offset,
    )


# ============================================================================
# Consent Management Endpoints
# ============================================================================

@router.get("/consent/{patient_id}", response_model=PatientConsent | None)
async def get_patient_consent(patient_id: str) -> PatientConsent | None:
    """Get patient consent for health information exchange.

    Args:
        patient_id: Patient identifier
    """
    service = get_tefca_service()
    return service.get_patient_consent(patient_id)


@router.post("/consent", response_model=PatientConsent)
async def set_patient_consent(request: ConsentRequest) -> PatientConsent:
    """Set or update patient consent for health information exchange.

    Manages patient consent directives for TEFCA exchange.
    """
    service = get_tefca_service()

    consent = PatientConsent(
        id=f"consent-{request.patient_id}",
        patient_id=request.patient_id,
        status=request.status,
        scope=request.scope,
        includes_sensitive=request.includes_sensitive,
        effective_date=request.effective_date,
        expiration_date=request.expiration_date,
        excluded_organizations=request.excluded_organizations,
        excluded_document_types=request.excluded_document_types,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        created_by="api-user",
    )

    updated_consent = service.set_patient_consent(consent)

    logger.info(f"Updated consent for patient {request.patient_id}: {request.status.value}")

    return updated_consent


# ============================================================================
# SAML Validation Endpoint
# ============================================================================

@router.post("/validate-saml", response_model=ValidationResult)
async def validate_saml_assertion(request: SAMLValidationRequest) -> ValidationResult:
    """Validate a SAML assertion for TEFCA authentication.

    Validates the SAML assertion and returns the contained claims.
    """
    service = get_tefca_service()

    result = service.validate_saml_assertion(request.assertion)

    if not result.valid:
        raise HTTPException(status_code=401, detail=result.error_message)

    return result


# ============================================================================
# Service Status Endpoint
# ============================================================================

@router.get("/status", response_model=ServiceStatusResponse)
async def get_service_status() -> ServiceStatusResponse:
    """Get TEFCA service status and statistics.

    Returns current service health and metrics.
    """
    service = get_tefca_service()
    stats = service.get_stats()

    return ServiceStatusResponse(
        status="healthy",
        total_qhins=stats["total_qhins"],
        active_qhins=stats["active_qhins"],
        total_participants=stats["total_participants"],
        audit_log_count=stats["audit_log_count"],
        timestamp=datetime.now(timezone.utc),
    )


# ============================================================================
# Reference Data Endpoints
# ============================================================================

@router.get("/exchange-purposes")
async def list_exchange_purposes() -> list[dict[str, str]]:
    """List all valid TEFCA exchange purposes of use."""
    return [
        {
            "code": ExchangePurpose.TREATMENT.value,
            "display": "Treatment",
            "description": "Direct patient care activities",
        },
        {
            "code": ExchangePurpose.PAYMENT.value,
            "display": "Payment",
            "description": "Payment and reimbursement activities",
        },
        {
            "code": ExchangePurpose.HEALTHCARE_OPERATIONS.value,
            "display": "Healthcare Operations",
            "description": "Administrative and quality activities",
        },
        {
            "code": ExchangePurpose.PUBLIC_HEALTH.value,
            "display": "Public Health",
            "description": "Public health reporting and activities",
        },
        {
            "code": ExchangePurpose.INDIVIDUAL_ACCESS_SERVICES.value,
            "display": "Individual Access Services",
            "description": "Patient access to their own records",
        },
        {
            "code": ExchangePurpose.BENEFITS_DETERMINATION.value,
            "display": "Benefits Determination",
            "description": "Insurance benefits determination",
        },
        {
            "code": ExchangePurpose.COVERAGE_DETERMINATION.value,
            "display": "Coverage Determination",
            "description": "Insurance coverage determination",
        },
        {
            "code": ExchangePurpose.EMERGENCY.value,
            "display": "Emergency",
            "description": "Emergency treatment scenarios",
        },
    ]


@router.get("/document-classes")
async def list_document_classes() -> list[dict[str, str]]:
    """List all valid clinical document classes."""
    return [
        {
            "code": DocumentClass.CCD.value,
            "display": "Continuity of Care Document",
            "description": "Summarization of episode note (CCD)",
        },
        {
            "code": DocumentClass.DISCHARGE_SUMMARY.value,
            "display": "Discharge Summary",
            "description": "Hospital discharge summary",
        },
        {
            "code": DocumentClass.CONSULTATION_NOTE.value,
            "display": "Consultation Note",
            "description": "Consultation note",
        },
        {
            "code": DocumentClass.PROGRESS_NOTE.value,
            "display": "Progress Note",
            "description": "Progress note",
        },
        {
            "code": DocumentClass.HISTORY_AND_PHYSICAL.value,
            "display": "History and Physical",
            "description": "History and physical examination",
        },
        {
            "code": DocumentClass.OPERATIVE_NOTE.value,
            "display": "Operative Note",
            "description": "Operative/surgical note",
        },
        {
            "code": DocumentClass.PROCEDURE_NOTE.value,
            "display": "Procedure Note",
            "description": "Procedure note",
        },
        {
            "code": DocumentClass.LABORATORY_REPORT.value,
            "display": "Laboratory Report",
            "description": "Laboratory results report",
        },
        {
            "code": DocumentClass.DIAGNOSTIC_IMAGING.value,
            "display": "Diagnostic Imaging",
            "description": "Diagnostic imaging report",
        },
        {
            "code": DocumentClass.PATHOLOGY_REPORT.value,
            "display": "Pathology Report",
            "description": "Pathology report",
        },
        {
            "code": DocumentClass.REFERRAL_NOTE.value,
            "display": "Referral Note",
            "description": "Referral note",
        },
        {
            "code": DocumentClass.CARE_PLAN.value,
            "display": "Care Plan",
            "description": "Care plan document",
        },
    ]
