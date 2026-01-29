"""TEFCA (Trusted Exchange Framework and Common Agreement) service.

Provides integration with Qualified Health Information Networks (QHINs) for
nationwide health information exchange. Implements IHE profiles (PDQm, MHD, XDS.b)
for patient discovery, document query/retrieve, and Direct messaging.

TEFCA enables standardized, secure exchange of health information across
different healthcare organizations and EHR systems.
"""

import hashlib
import logging
import secrets
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Constants
# ============================================================================

class QHINStatus(str, Enum):
    """QHIN network status."""
    ACTIVE = "active"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"


class ExchangePurpose(str, Enum):
    """TEFCA exchange purposes of use."""
    TREATMENT = "treatment"
    PAYMENT = "payment"
    HEALTHCARE_OPERATIONS = "healthcare_operations"
    PUBLIC_HEALTH = "public_health"
    INDIVIDUAL_ACCESS_SERVICES = "individual_access_services"
    BENEFITS_DETERMINATION = "benefits_determination"
    COVERAGE_DETERMINATION = "coverage_determination"
    EMERGENCY = "emergency"


class DocumentClass(str, Enum):
    """Clinical document classes."""
    CCD = "34133-9"  # Summarization of Episode Note (CCD)
    DISCHARGE_SUMMARY = "18842-5"
    CONSULTATION_NOTE = "11488-4"
    PROGRESS_NOTE = "11506-3"
    HISTORY_AND_PHYSICAL = "34117-2"
    OPERATIVE_NOTE = "11504-8"
    PROCEDURE_NOTE = "28570-0"
    LABORATORY_REPORT = "11502-2"
    DIAGNOSTIC_IMAGING = "18748-4"
    PATHOLOGY_REPORT = "11526-1"
    REFERRAL_NOTE = "57133-1"
    CARE_PLAN = "18776-5"


class MatchConfidence(str, Enum):
    """Patient match confidence levels."""
    EXACT = "exact"
    HIGH = "high"
    PROBABLE = "probable"
    POSSIBLE = "possible"
    LOW = "low"


class AuditEventType(str, Enum):
    """ATNA audit event types."""
    PATIENT_RECORD_QUERY = "patient_record_query"
    DOCUMENT_QUERY = "document_query"
    DOCUMENT_RETRIEVE = "document_retrieve"
    MESSAGE_SEND = "message_send"
    AUTHENTICATION = "authentication"
    CONSENT_QUERY = "consent_query"


class ConsentStatus(str, Enum):
    """Patient consent status."""
    ACTIVE = "active"
    DENIED = "denied"
    NOT_ASKED = "not_asked"
    EXPIRED = "expired"
    PENDING = "pending"


class DirectMessageStatus(str, Enum):
    """Direct message delivery status."""
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    PENDING = "pending"
    QUEUED = "queued"


# ============================================================================
# Pydantic Models
# ============================================================================

class QHIN(BaseModel):
    """Qualified Health Information Network."""

    id: str = Field(..., description="Unique QHIN identifier")
    name: str = Field(..., description="QHIN display name")
    description: str = Field(..., description="QHIN description")
    status: QHINStatus = Field(..., description="Current network status")
    endpoint_url: str = Field(..., description="QHIN service endpoint URL")

    # Capabilities
    supports_patient_discovery: bool = Field(True, description="Supports IHE PDQm")
    supports_document_query: bool = Field(True, description="Supports IHE MHD/XDS.b")
    supports_document_retrieve: bool = Field(True, description="Supports document retrieval")
    supports_direct_messaging: bool = Field(True, description="Supports Direct messaging")
    supports_query_based_exchange: bool = Field(True, description="Supports QBE")

    # Network info
    participant_count: int = Field(0, description="Number of participating organizations")
    coverage_states: list[str] = Field(default_factory=list, description="States with coverage")
    organization_types: list[str] = Field(default_factory=list, description="Types of organizations")

    # Technical details
    fhir_version: str = Field("R4", description="FHIR version supported")
    ihe_profiles: list[str] = Field(default_factory=list, description="Supported IHE profiles")
    last_health_check: datetime | None = Field(None, description="Last health check timestamp")
    average_response_time_ms: int = Field(0, description="Average response time")


class PatientDemographics(BaseModel):
    """Patient demographics for search."""

    family_name: str = Field(..., description="Patient family/last name")
    given_name: str | None = Field(None, description="Patient given/first name")
    birth_date: str | None = Field(None, description="Patient birth date (YYYY-MM-DD)")
    gender: str | None = Field(None, description="Patient gender (male/female/other)")
    address_line: str | None = Field(None, description="Street address")
    city: str | None = Field(None, description="City")
    state: str | None = Field(None, description="State (2-letter code)")
    postal_code: str | None = Field(None, description="ZIP/Postal code")

    # Identifiers
    ssn_last_four: str | None = Field(None, description="Last 4 digits of SSN")
    mrn: str | None = Field(None, description="Medical Record Number")
    phone: str | None = Field(None, description="Phone number")
    email: str | None = Field(None, description="Email address")


class PatientMatch(BaseModel):
    """Patient match result from QHIN."""

    id: str = Field(..., description="Patient identifier")
    source_qhin: str = Field(..., description="QHIN that returned this match")
    source_organization: str = Field(..., description="Organization holding records")
    confidence: MatchConfidence = Field(..., description="Match confidence level")
    confidence_score: float = Field(..., description="Numeric confidence score (0-1)")

    # Demographics
    family_name: str = Field(..., description="Patient family name")
    given_name: str = Field(..., description="Patient given name")
    birth_date: str | None = Field(None, description="Birth date")
    gender: str | None = Field(None, description="Gender")
    address: str | None = Field(None, description="Full address")

    # Additional info
    mrn: str | None = Field(None, description="MRN at source organization")
    document_count: int = Field(0, description="Number of available documents")
    last_updated: datetime | None = Field(None, description="Last record update")


class QueryResponse(BaseModel):
    """Response from patient discovery query."""

    query_id: str = Field(..., description="Unique query identifier")
    query_time: datetime = Field(..., description="Query timestamp")
    query_duration_ms: int = Field(..., description="Query duration in milliseconds")

    total_matches: int = Field(..., description="Total matches found")
    matches: list[PatientMatch] = Field(default_factory=list, description="Patient matches")

    qhins_queried: list[str] = Field(default_factory=list, description="QHINs that were queried")
    qhins_responded: list[str] = Field(default_factory=list, description="QHINs that responded")
    qhins_errors: dict[str, str] = Field(default_factory=dict, description="QHINs with errors")


class DocumentReference(BaseModel):
    """Reference to a clinical document."""

    id: str = Field(..., description="Document identifier")
    repository_id: str = Field(..., description="Repository identifier")
    source_qhin: str = Field(..., description="Source QHIN")
    source_organization: str = Field(..., description="Source organization")

    # Document metadata
    document_type: str = Field(..., description="Document type code")
    document_type_display: str = Field(..., description="Document type display name")
    document_class: DocumentClass = Field(..., description="Document class")
    format_code: str = Field(..., description="Format code (e.g., CCDA)")
    mime_type: str = Field("application/xml", description="MIME type")

    # Clinical context
    title: str = Field(..., description="Document title")
    author: str | None = Field(None, description="Document author")
    facility: str | None = Field(None, description="Facility name")

    # Dates
    creation_date: datetime = Field(..., description="Document creation date")
    service_start_date: datetime | None = Field(None, description="Service start date")
    service_end_date: datetime | None = Field(None, description="Service end date")

    # Size info
    size_bytes: int | None = Field(None, description="Document size in bytes")
    hash: str | None = Field(None, description="Document hash")

    # Status
    status: str = Field("current", description="Document status")
    availability: str = Field("available", description="Document availability")


class DocumentQueryResponse(BaseModel):
    """Response from document query."""

    query_id: str = Field(..., description="Unique query identifier")
    patient_id: str = Field(..., description="Patient identifier")
    query_time: datetime = Field(..., description="Query timestamp")
    query_duration_ms: int = Field(..., description="Query duration in milliseconds")

    total_documents: int = Field(..., description="Total documents found")
    documents: list[DocumentReference] = Field(default_factory=list, description="Document references")

    qhins_queried: list[str] = Field(default_factory=list, description="QHINs that were queried")


class ClinicalDocument(BaseModel):
    """Retrieved clinical document."""

    id: str = Field(..., description="Document identifier")
    reference_id: str = Field(..., description="Original reference ID")
    source_qhin: str = Field(..., description="Source QHIN")

    # Content
    content: str = Field(..., description="Document content (base64 or XML)")
    mime_type: str = Field(..., description="MIME type")
    format: str = Field(..., description="Document format")

    # Metadata
    title: str = Field(..., description="Document title")
    document_type: str = Field(..., description="Document type")
    creation_date: datetime = Field(..., description="Creation date")

    # Retrieval info
    retrieved_at: datetime = Field(..., description="Retrieval timestamp")
    retrieval_duration_ms: int = Field(..., description="Retrieval duration")


class DirectMessage(BaseModel):
    """Direct secure message."""

    to_address: str = Field(..., description="Recipient Direct address")
    from_address: str | None = Field(None, description="Sender Direct address")
    subject: str = Field(..., description="Message subject")
    body: str = Field(..., description="Message body")

    # Attachments
    attachments: list[dict[str, Any]] = Field(default_factory=list, description="Message attachments")

    # Metadata
    patient_id: str | None = Field(None, description="Related patient ID")
    purpose: ExchangePurpose = Field(ExchangePurpose.TREATMENT, description="Purpose of use")


class SendResult(BaseModel):
    """Result of sending a Direct message."""

    message_id: str = Field(..., description="Message identifier")
    status: DirectMessageStatus = Field(..., description="Delivery status")
    sent_at: datetime = Field(..., description="Send timestamp")

    recipient_qhin: str = Field(..., description="Recipient QHIN")
    recipient_organization: str | None = Field(None, description="Recipient organization")

    tracking_id: str | None = Field(None, description="Tracking identifier")
    error_message: str | None = Field(None, description="Error message if failed")


class ValidationResult(BaseModel):
    """SAML assertion validation result."""

    valid: bool = Field(..., description="Whether assertion is valid")
    issuer: str | None = Field(None, description="Assertion issuer")
    subject: str | None = Field(None, description="Assertion subject")
    not_before: datetime | None = Field(None, description="Validity start")
    not_after: datetime | None = Field(None, description="Validity end")

    purpose_of_use: ExchangePurpose | None = Field(None, description="Declared purpose")
    user_role: str | None = Field(None, description="User role")
    organization: str | None = Field(None, description="User organization")

    error_message: str | None = Field(None, description="Validation error")


class AuditLog(BaseModel):
    """ATNA audit log entry."""

    id: str = Field(..., description="Audit log ID")
    timestamp: datetime = Field(..., description="Event timestamp")
    event_type: AuditEventType = Field(..., description="Event type")

    # Actor info
    user_id: str = Field(..., description="User identifier")
    user_name: str | None = Field(None, description="User name")
    user_role: str | None = Field(None, description="User role")
    organization: str | None = Field(None, description="Organization")
    ip_address: str | None = Field(None, description="IP address")

    # Action info
    action: str = Field(..., description="Action performed")
    outcome: str = Field(..., description="Outcome (success/failure)")
    purpose_of_use: ExchangePurpose = Field(..., description="Purpose of use")

    # Patient info
    patient_id: str | None = Field(None, description="Patient ID")

    # Query/Result info
    query_id: str | None = Field(None, description="Query identifier")
    qhins_queried: list[str] = Field(default_factory=list, description="QHINs queried")
    documents_accessed: list[str] = Field(default_factory=list, description="Documents accessed")

    # Additional details
    details: dict[str, Any] = Field(default_factory=dict, description="Additional details")


class PatientConsent(BaseModel):
    """Patient consent for health information exchange."""

    id: str = Field(..., description="Consent ID")
    patient_id: str = Field(..., description="Patient ID")
    status: ConsentStatus = Field(..., description="Consent status")

    # Consent scope
    scope: list[ExchangePurpose] = Field(default_factory=list, description="Permitted purposes")
    includes_sensitive: bool = Field(False, description="Includes sensitive records")

    # Time bounds
    effective_date: datetime | None = Field(None, description="Consent effective date")
    expiration_date: datetime | None = Field(None, description="Consent expiration date")

    # Restrictions
    excluded_organizations: list[str] = Field(default_factory=list, description="Excluded orgs")
    excluded_document_types: list[str] = Field(default_factory=list, description="Excluded doc types")

    # Audit
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime | None = Field(None, description="Last update timestamp")
    created_by: str | None = Field(None, description="Created by user")


class TEFCAQuery(BaseModel):
    """TEFCA query parameters."""

    purpose: ExchangePurpose = Field(..., description="Purpose of use")
    user_id: str = Field(..., description="Requesting user ID")
    organization: str = Field(..., description="Requesting organization")

    # Optional filters
    qhin_filter: list[str] | None = Field(None, description="Filter to specific QHINs")
    date_range_start: datetime | None = Field(None, description="Date range start")
    date_range_end: datetime | None = Field(None, description="Date range end")
    document_types: list[DocumentClass] | None = Field(None, description="Document type filter")


# ============================================================================
# Mock Data
# ============================================================================

MOCK_QHINS: list[dict[str, Any]] = [
    {
        "id": "epic-carequality",
        "name": "Epic via Carequality",
        "description": "Epic's nationwide health information network connecting Epic-based organizations through Carequality",
        "status": QHINStatus.ACTIVE,
        "endpoint_url": "https://carequality.epic.com/fhir",
        "participant_count": 4500,
        "coverage_states": ["ALL"],
        "organization_types": ["Hospital", "Health System", "Physician Practice"],
        "fhir_version": "R4",
        "ihe_profiles": ["PDQm", "MHD", "XCA", "XDS.b"],
        "average_response_time_ms": 250,
    },
    {
        "id": "commonwell",
        "name": "CommonWell Health Alliance",
        "description": "National health data exchange network connecting diverse EHR systems",
        "status": QHINStatus.ACTIVE,
        "endpoint_url": "https://api.commonwellalliance.org",
        "participant_count": 35000,
        "coverage_states": ["ALL"],
        "organization_types": ["Hospital", "Ambulatory", "Post-Acute", "Labs"],
        "fhir_version": "R4",
        "ihe_profiles": ["PDQm", "MHD", "XCA", "XDS.b"],
        "average_response_time_ms": 300,
    },
    {
        "id": "carequality",
        "name": "Carequality",
        "description": "Interoperability framework enabling nationwide exchange across organizations",
        "status": QHINStatus.ACTIVE,
        "endpoint_url": "https://hub.carequality.org",
        "participant_count": 70000,
        "coverage_states": ["ALL"],
        "organization_types": ["Hospital", "Health System", "HIE", "Payer"],
        "fhir_version": "R4",
        "ihe_profiles": ["PDQm", "MHD", "XCA", "XDS.b", "XCPD"],
        "average_response_time_ms": 350,
    },
    {
        "id": "ehealth-exchange",
        "name": "eHealth Exchange",
        "description": "Largest health information network serving federal, state, and private organizations",
        "status": QHINStatus.ACTIVE,
        "endpoint_url": "https://gateway.ehealthexchange.org",
        "participant_count": 180,
        "coverage_states": ["ALL"],
        "organization_types": ["Federal", "State", "VA", "DoD", "SSA", "CMS"],
        "fhir_version": "R4",
        "ihe_profiles": ["PDQm", "MHD", "XCA", "XDS.b", "XCPD"],
        "average_response_time_ms": 400,
    },
    {
        "id": "healthgorilla",
        "name": "Health Gorilla",
        "description": "Clinical data network connecting labs, imaging centers, and healthcare facilities",
        "status": QHINStatus.ACTIVE,
        "endpoint_url": "https://api.healthgorilla.com",
        "participant_count": 5000,
        "coverage_states": ["ALL"],
        "organization_types": ["Labs", "Imaging", "Specialty", "Primary Care"],
        "fhir_version": "R4",
        "ihe_profiles": ["PDQm", "MHD"],
        "average_response_time_ms": 200,
    },
    {
        "id": "surescripts",
        "name": "Surescripts",
        "description": "National network for medication history and e-prescribing information",
        "status": QHINStatus.ACTIVE,
        "endpoint_url": "https://api.surescripts.net",
        "participant_count": 1500000,
        "coverage_states": ["ALL"],
        "organization_types": ["Pharmacy", "PBM", "Hospital", "Prescriber"],
        "fhir_version": "R4",
        "ihe_profiles": ["MHD"],
        "supports_patient_discovery": False,
        "average_response_time_ms": 150,
    },
    {
        "id": "konza-hie",
        "name": "Konza National Network (KHIN)",
        "description": "Regional QHIN serving Kansas and surrounding areas",
        "status": QHINStatus.DEGRADED,
        "endpoint_url": "https://gateway.konzanetwork.org",
        "participant_count": 450,
        "coverage_states": ["KS", "MO", "NE", "OK"],
        "organization_types": ["Hospital", "Rural Health", "Federally Qualified"],
        "fhir_version": "R4",
        "ihe_profiles": ["PDQm", "MHD", "XDS.b"],
        "average_response_time_ms": 500,
    },
    {
        "id": "medicity",
        "name": "Medicity (Aetna/CVS)",
        "description": "Health information exchange network connecting payer and provider data",
        "status": QHINStatus.ACTIVE,
        "endpoint_url": "https://api.medicity.com",
        "participant_count": 2500,
        "coverage_states": ["ALL"],
        "organization_types": ["Payer", "Hospital", "Ambulatory"],
        "fhir_version": "R4",
        "ihe_profiles": ["PDQm", "MHD", "XCA"],
        "average_response_time_ms": 280,
    },
]


MOCK_ORGANIZATIONS = [
    "Massachusetts General Hospital",
    "Cleveland Clinic",
    "Mayo Clinic - Rochester",
    "Johns Hopkins Hospital",
    "UCLA Medical Center",
    "Northwestern Memorial Hospital",
    "Duke University Hospital",
    "Stanford Health Care",
    "UCSF Medical Center",
    "Cedars-Sinai Medical Center",
]


# ============================================================================
# TEFCA Service Class
# ============================================================================

class TEFCAService:
    """TEFCA service for QHIN integration.

    Provides methods for:
    - QHIN discovery and capability lookup
    - Patient discovery (IHE PDQm)
    - Document query/retrieve (IHE MHD, XDS.b)
    - Direct secure messaging
    - SAML assertion validation
    - ATNA audit logging

    Usage:
        service = TEFCAService.get_instance()

        # Discover QHINs
        qhins = service.discover_qhins()

        # Query for patient
        response = service.query_patient(
            PatientDemographics(family_name="Smith", given_name="John"),
            TEFCAQuery(purpose=ExchangePurpose.TREATMENT, ...)
        )

        # Retrieve documents
        docs = service.retrieve_documents("patient-123", ["doc-ref-1", "doc-ref-2"])
    """

    _instance: "TEFCAService | None" = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        """Initialize the TEFCA service."""
        self._qhins: list[QHIN] = []
        self._audit_logs: list[AuditLog] = []
        self._consents: dict[str, PatientConsent] = {}
        self._cached_documents: dict[str, ClinicalDocument] = {}

        # Initialize mock QHINs
        self._initialize_qhins()

    @classmethod
    def get_instance(cls) -> "TEFCAService":
        """Get the singleton instance of TEFCAService."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (for testing)."""
        with cls._lock:
            cls._instance = None

    def _initialize_qhins(self) -> None:
        """Initialize mock QHIN data."""
        for qhin_data in MOCK_QHINS:
            qhin = QHIN(
                id=qhin_data["id"],
                name=qhin_data["name"],
                description=qhin_data["description"],
                status=qhin_data["status"],
                endpoint_url=qhin_data["endpoint_url"],
                supports_patient_discovery=qhin_data.get("supports_patient_discovery", True),
                supports_document_query=True,
                supports_document_retrieve=True,
                supports_direct_messaging=True,
                supports_query_based_exchange=True,
                participant_count=qhin_data["participant_count"],
                coverage_states=qhin_data["coverage_states"],
                organization_types=qhin_data["organization_types"],
                fhir_version=qhin_data["fhir_version"],
                ihe_profiles=qhin_data["ihe_profiles"],
                last_health_check=datetime.now(timezone.utc),
                average_response_time_ms=qhin_data["average_response_time_ms"],
            )
            self._qhins.append(qhin)

    def discover_qhins(
        self,
        include_offline: bool = False,
        capability_filter: list[str] | None = None,
    ) -> list[QHIN]:
        """Discover available Qualified Health Information Networks.

        Args:
            include_offline: Whether to include offline QHINs
            capability_filter: Filter by required capabilities

        Returns:
            List of available QHINs
        """
        qhins = self._qhins.copy()

        # Filter offline QHINs
        if not include_offline:
            qhins = [q for q in qhins if q.status != QHINStatus.OFFLINE]

        # Filter by capabilities
        if capability_filter:
            filtered = []
            for qhin in qhins:
                has_all = True
                for cap in capability_filter:
                    if cap == "patient_discovery" and not qhin.supports_patient_discovery:
                        has_all = False
                        break
                    if cap == "document_query" and not qhin.supports_document_query:
                        has_all = False
                        break
                    if cap == "direct_messaging" and not qhin.supports_direct_messaging:
                        has_all = False
                        break
                if has_all:
                    filtered.append(qhin)
            qhins = filtered

        logger.info(f"Discovered {len(qhins)} QHINs")
        return qhins

    def get_qhin(self, qhin_id: str) -> QHIN | None:
        """Get a specific QHIN by ID.

        Args:
            qhin_id: QHIN identifier

        Returns:
            QHIN if found, None otherwise
        """
        for qhin in self._qhins:
            if qhin.id == qhin_id:
                return qhin
        return None

    def query_patient(
        self,
        demographics: PatientDemographics,
        query: TEFCAQuery,
    ) -> QueryResponse:
        """Query for patient records across QHINs.

        Implements IHE PDQm (Patient Demographics Query for Mobile) profile.

        Args:
            demographics: Patient demographics for matching
            query: Query parameters including purpose of use

        Returns:
            QueryResponse with patient matches
        """
        start_time = time.time()
        query_id = f"pdq-{uuid.uuid4().hex[:12]}"

        # Get active QHINs to query
        qhins_to_query = self.discover_qhins(capability_filter=["patient_discovery"])
        if query.qhin_filter:
            qhins_to_query = [q for q in qhins_to_query if q.id in query.qhin_filter]

        qhin_ids = [q.id for q in qhins_to_query]
        matches: list[PatientMatch] = []
        errors: dict[str, str] = {}
        responded: list[str] = []

        # Simulate querying each QHIN (mock data)
        for qhin in qhins_to_query:
            if qhin.status == QHINStatus.OFFLINE:
                errors[qhin.id] = "QHIN is offline"
                continue

            if qhin.status == QHINStatus.DEGRADED:
                # 50% chance of error for degraded QHINs
                if secrets.randbelow(100) < 50:
                    errors[qhin.id] = "Connection timeout"
                    continue

            # Generate mock matches
            num_matches = secrets.randbelow(4)  # 0-3 matches per QHIN
            for i in range(num_matches):
                org = MOCK_ORGANIZATIONS[secrets.randbelow(len(MOCK_ORGANIZATIONS))]
                confidence_val = 0.5 + (secrets.randbelow(50) / 100)  # 0.5-1.0

                if confidence_val >= 0.95:
                    confidence = MatchConfidence.EXACT
                elif confidence_val >= 0.85:
                    confidence = MatchConfidence.HIGH
                elif confidence_val >= 0.70:
                    confidence = MatchConfidence.PROBABLE
                elif confidence_val >= 0.50:
                    confidence = MatchConfidence.POSSIBLE
                else:
                    confidence = MatchConfidence.LOW

                match = PatientMatch(
                    id=f"pt-{uuid.uuid4().hex[:8]}",
                    source_qhin=qhin.id,
                    source_organization=org,
                    confidence=confidence,
                    confidence_score=round(confidence_val, 3),
                    family_name=demographics.family_name,
                    given_name=demographics.given_name or "Unknown",
                    birth_date=demographics.birth_date,
                    gender=demographics.gender,
                    address=f"{demographics.city or 'Unknown'}, {demographics.state or 'XX'}",
                    mrn=f"MRN{secrets.randbelow(1000000):07d}",
                    document_count=secrets.randbelow(50) + 1,
                    last_updated=datetime.now(timezone.utc) - timedelta(days=secrets.randbelow(365)),
                )
                matches.append(match)

            responded.append(qhin.id)

        # Sort matches by confidence score
        matches.sort(key=lambda m: m.confidence_score, reverse=True)

        duration_ms = int((time.time() - start_time) * 1000)

        response = QueryResponse(
            query_id=query_id,
            query_time=datetime.now(timezone.utc),
            query_duration_ms=duration_ms,
            total_matches=len(matches),
            matches=matches,
            qhins_queried=qhin_ids,
            qhins_responded=responded,
            qhins_errors=errors,
        )

        # Create audit log
        self.audit_query(
            query=query,
            result=response,
            event_type=AuditEventType.PATIENT_RECORD_QUERY,
        )

        logger.info(
            f"Patient query {query_id}: {len(matches)} matches from "
            f"{len(responded)}/{len(qhin_ids)} QHINs"
        )

        return response

    def query_documents(
        self,
        patient_id: str,
        query: TEFCAQuery,
        patient_match: PatientMatch | None = None,
    ) -> DocumentQueryResponse:
        """Query for documents for a patient.

        Implements IHE MHD (Mobile access to Health Documents) profile.

        Args:
            patient_id: Patient identifier
            query: Query parameters
            patient_match: Optional patient match info

        Returns:
            DocumentQueryResponse with document references
        """
        start_time = time.time()
        query_id = f"mhd-{uuid.uuid4().hex[:12]}"

        # Get QHINs to query
        qhins_to_query = self.discover_qhins(capability_filter=["document_query"])
        if query.qhin_filter:
            qhins_to_query = [q for q in qhins_to_query if q.id in query.qhin_filter]

        if patient_match:
            # If we have a match, only query that QHIN
            qhins_to_query = [q for q in qhins_to_query if q.id == patient_match.source_qhin]

        qhin_ids = [q.id for q in qhins_to_query]
        documents: list[DocumentReference] = []

        # Document type options
        doc_types = list(DocumentClass)

        # Generate mock documents
        for qhin in qhins_to_query:
            if qhin.status == QHINStatus.OFFLINE:
                continue

            org = (patient_match.source_organization if patient_match
                   else MOCK_ORGANIZATIONS[secrets.randbelow(len(MOCK_ORGANIZATIONS))])

            num_docs = secrets.randbelow(15) + 1  # 1-15 documents
            for i in range(num_docs):
                doc_class = doc_types[secrets.randbelow(len(doc_types))]
                creation_date = datetime.now(timezone.utc) - timedelta(days=secrets.randbelow(730))

                doc_type_displays = {
                    DocumentClass.CCD: "Continuity of Care Document",
                    DocumentClass.DISCHARGE_SUMMARY: "Discharge Summary",
                    DocumentClass.CONSULTATION_NOTE: "Consultation Note",
                    DocumentClass.PROGRESS_NOTE: "Progress Note",
                    DocumentClass.HISTORY_AND_PHYSICAL: "History and Physical",
                    DocumentClass.OPERATIVE_NOTE: "Operative Note",
                    DocumentClass.PROCEDURE_NOTE: "Procedure Note",
                    DocumentClass.LABORATORY_REPORT: "Laboratory Report",
                    DocumentClass.DIAGNOSTIC_IMAGING: "Diagnostic Imaging Report",
                    DocumentClass.PATHOLOGY_REPORT: "Pathology Report",
                    DocumentClass.REFERRAL_NOTE: "Referral Note",
                    DocumentClass.CARE_PLAN: "Care Plan",
                }

                doc = DocumentReference(
                    id=f"doc-{uuid.uuid4().hex[:10]}",
                    repository_id=f"repo-{qhin.id}",
                    source_qhin=qhin.id,
                    source_organization=org,
                    document_type=doc_class.value,
                    document_type_display=doc_type_displays.get(doc_class, doc_class.name),
                    document_class=doc_class,
                    format_code="urn:hl7-org:sdwg:ccda-structuredBody:2.1",
                    mime_type="application/xml",
                    title=f"{doc_type_displays.get(doc_class, doc_class.name)} - {creation_date.strftime('%Y-%m-%d')}",
                    author=f"Dr. {['Smith', 'Johnson', 'Williams', 'Brown', 'Jones'][secrets.randbelow(5)]}",
                    facility=org,
                    creation_date=creation_date,
                    service_start_date=creation_date,
                    service_end_date=creation_date + timedelta(hours=secrets.randbelow(24)),
                    size_bytes=secrets.randbelow(500000) + 10000,
                    hash=hashlib.sha256(f"doc-{uuid.uuid4()}".encode()).hexdigest(),
                )
                documents.append(doc)

        # Apply document type filter
        if query.document_types:
            documents = [d for d in documents if d.document_class in query.document_types]

        # Apply date filter
        if query.date_range_start:
            documents = [d for d in documents if d.creation_date >= query.date_range_start]
        if query.date_range_end:
            documents = [d for d in documents if d.creation_date <= query.date_range_end]

        # Sort by date descending
        documents.sort(key=lambda d: d.creation_date, reverse=True)

        duration_ms = int((time.time() - start_time) * 1000)

        response = DocumentQueryResponse(
            query_id=query_id,
            patient_id=patient_id,
            query_time=datetime.now(timezone.utc),
            query_duration_ms=duration_ms,
            total_documents=len(documents),
            documents=documents,
            qhins_queried=qhin_ids,
        )

        # Create audit log
        self.audit_query(
            query=query,
            result=None,
            event_type=AuditEventType.DOCUMENT_QUERY,
            patient_id=patient_id,
            details={"document_count": len(documents)},
        )

        logger.info(
            f"Document query {query_id}: {len(documents)} documents for patient {patient_id}"
        )

        return response

    def retrieve_documents(
        self,
        patient_id: str,
        document_refs: list[str],
        query: TEFCAQuery,
    ) -> list[ClinicalDocument]:
        """Retrieve clinical documents from QHINs.

        Implements IHE XDS.b retrieve document set.

        Args:
            patient_id: Patient identifier
            document_refs: List of document reference IDs to retrieve
            query: Query parameters

        Returns:
            List of retrieved clinical documents
        """
        start_time = time.time()
        documents: list[ClinicalDocument] = []

        for ref_id in document_refs:
            # Check cache
            if ref_id in self._cached_documents:
                documents.append(self._cached_documents[ref_id])
                continue

            retrieval_start = time.time()

            # Generate mock C-CDA content
            ccda_content = self._generate_mock_ccda(patient_id, ref_id)

            doc = ClinicalDocument(
                id=f"retrieved-{uuid.uuid4().hex[:8]}",
                reference_id=ref_id,
                source_qhin="epic-carequality",  # Mock
                content=ccda_content,
                mime_type="application/xml",
                format="C-CDA",
                title=f"Clinical Document - {ref_id[:8]}",
                document_type="34133-9",
                creation_date=datetime.now(timezone.utc) - timedelta(days=secrets.randbelow(365)),
                retrieved_at=datetime.now(timezone.utc),
                retrieval_duration_ms=int((time.time() - retrieval_start) * 1000),
            )

            documents.append(doc)
            self._cached_documents[ref_id] = doc

        # Create audit log
        self.audit_query(
            query=query,
            result=None,
            event_type=AuditEventType.DOCUMENT_RETRIEVE,
            patient_id=patient_id,
            details={"documents_retrieved": [d.id for d in documents]},
        )

        logger.info(f"Retrieved {len(documents)} documents for patient {patient_id}")

        return documents

    def _generate_mock_ccda(self, patient_id: str, doc_id: str) -> str:
        """Generate mock C-CDA XML content."""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<ClinicalDocument xmlns="urn:hl7-org:v3" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <realmCode code="US"/>
    <typeId root="2.16.840.1.113883.1.3" extension="POCD_HD000040"/>
    <templateId root="2.16.840.1.113883.10.20.22.1.1"/>
    <templateId root="2.16.840.1.113883.10.20.22.1.2"/>
    <id root="{doc_id}"/>
    <code code="34133-9" codeSystem="2.16.840.1.113883.6.1" displayName="Summarization of Episode Note"/>
    <title>Continuity of Care Document</title>
    <effectiveTime value="{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"/>
    <confidentialityCode code="N" codeSystem="2.16.840.1.113883.5.25"/>
    <languageCode code="en-US"/>
    <recordTarget>
        <patientRole>
            <id root="{patient_id}"/>
        </patientRole>
    </recordTarget>
    <!-- Mock C-CDA content for demonstration -->
    <component>
        <structuredBody>
            <component>
                <section>
                    <templateId root="2.16.840.1.113883.10.20.22.2.6.1"/>
                    <code code="48765-2" codeSystem="2.16.840.1.113883.6.1" displayName="Allergies"/>
                    <title>Allergies and Adverse Reactions</title>
                    <text>No known allergies</text>
                </section>
            </component>
            <component>
                <section>
                    <templateId root="2.16.840.1.113883.10.20.22.2.1.1"/>
                    <code code="10160-0" codeSystem="2.16.840.1.113883.6.1" displayName="Medications"/>
                    <title>Medications</title>
                    <text>Current medications on file</text>
                </section>
            </component>
        </structuredBody>
    </component>
</ClinicalDocument>"""

    def send_message(
        self,
        recipient_qhin: str,
        message: DirectMessage,
        query: TEFCAQuery,
    ) -> SendResult:
        """Send Direct secure message.

        Args:
            recipient_qhin: Target QHIN identifier
            message: Message to send
            query: Query parameters

        Returns:
            SendResult with delivery status
        """
        message_id = f"msg-{uuid.uuid4().hex[:12]}"

        qhin = self.get_qhin(recipient_qhin)
        if not qhin:
            return SendResult(
                message_id=message_id,
                status=DirectMessageStatus.FAILED,
                sent_at=datetime.now(timezone.utc),
                recipient_qhin=recipient_qhin,
                error_message=f"QHIN {recipient_qhin} not found",
            )

        if not qhin.supports_direct_messaging:
            return SendResult(
                message_id=message_id,
                status=DirectMessageStatus.FAILED,
                sent_at=datetime.now(timezone.utc),
                recipient_qhin=recipient_qhin,
                error_message=f"QHIN {recipient_qhin} does not support Direct messaging",
            )

        if qhin.status == QHINStatus.OFFLINE:
            return SendResult(
                message_id=message_id,
                status=DirectMessageStatus.FAILED,
                sent_at=datetime.now(timezone.utc),
                recipient_qhin=recipient_qhin,
                error_message=f"QHIN {recipient_qhin} is offline",
            )

        # Mock successful send
        status = DirectMessageStatus.SENT
        if qhin.status == QHINStatus.DEGRADED:
            status = DirectMessageStatus.QUEUED

        # Create audit log
        self.audit_query(
            query=query,
            result=None,
            event_type=AuditEventType.MESSAGE_SEND,
            patient_id=message.patient_id,
            details={
                "recipient_address": message.to_address,
                "subject": message.subject,
                "has_attachments": len(message.attachments) > 0,
            },
        )

        logger.info(f"Direct message {message_id} sent to {message.to_address}")

        return SendResult(
            message_id=message_id,
            status=status,
            sent_at=datetime.now(timezone.utc),
            recipient_qhin=recipient_qhin,
            recipient_organization=None,
            tracking_id=f"track-{uuid.uuid4().hex[:8]}",
        )

    def validate_saml_assertion(self, assertion: str) -> ValidationResult:
        """Validate SAML assertion for TEFCA authentication.

        Args:
            assertion: Base64-encoded SAML assertion

        Returns:
            ValidationResult with validation status
        """
        # Mock SAML validation
        # In production, this would use a proper SAML library

        if not assertion or len(assertion) < 10:
            return ValidationResult(
                valid=False,
                error_message="Invalid assertion format",
            )

        # Mock successful validation
        now = datetime.now(timezone.utc)
        return ValidationResult(
            valid=True,
            issuer="https://idp.example.com",
            subject="user@organization.example.com",
            not_before=now - timedelta(minutes=5),
            not_after=now + timedelta(hours=1),
            purpose_of_use=ExchangePurpose.TREATMENT,
            user_role="Physician",
            organization="Example Health System",
        )

    def audit_query(
        self,
        query: TEFCAQuery,
        result: QueryResponse | None,
        event_type: AuditEventType,
        patient_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Create TEFCA-compliant audit log (ATNA).

        Args:
            query: Original query
            result: Query result (if applicable)
            event_type: Type of audit event
            patient_id: Patient identifier (if applicable)
            details: Additional details

        Returns:
            Created AuditLog entry
        """
        audit_id = f"audit-{uuid.uuid4().hex[:12]}"

        audit_log = AuditLog(
            id=audit_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            user_id=query.user_id,
            user_name=None,  # Would be populated from user context
            user_role=None,
            organization=query.organization,
            ip_address=None,  # Would be populated from request context
            action=event_type.value,
            outcome="success",
            purpose_of_use=query.purpose,
            patient_id=patient_id,
            query_id=result.query_id if result else None,
            qhins_queried=result.qhins_queried if result else [],
            documents_accessed=details.get("documents_retrieved", []) if details else [],
            details=details or {},
        )

        self._audit_logs.append(audit_log)

        logger.debug(f"Created audit log {audit_id} for {event_type.value}")

        return audit_log

    def get_audit_logs(
        self,
        patient_id: str | None = None,
        user_id: str | None = None,
        event_type: AuditEventType | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLog]:
        """Get audit logs with optional filters.

        Args:
            patient_id: Filter by patient
            user_id: Filter by user
            event_type: Filter by event type
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of matching audit logs
        """
        logs = self._audit_logs.copy()

        if patient_id:
            logs = [l for l in logs if l.patient_id == patient_id]
        if user_id:
            logs = [l for l in logs if l.user_id == user_id]
        if event_type:
            logs = [l for l in logs if l.event_type == event_type]
        if start_date:
            logs = [l for l in logs if l.timestamp >= start_date]
        if end_date:
            logs = [l for l in logs if l.timestamp <= end_date]

        # Sort by timestamp descending
        logs.sort(key=lambda l: l.timestamp, reverse=True)

        return logs[offset:offset + limit]

    def get_patient_consent(self, patient_id: str) -> PatientConsent | None:
        """Get patient consent for health information exchange.

        Args:
            patient_id: Patient identifier

        Returns:
            PatientConsent if exists, None otherwise
        """
        return self._consents.get(patient_id)

    def set_patient_consent(self, consent: PatientConsent) -> PatientConsent:
        """Set or update patient consent.

        Args:
            consent: Patient consent to set

        Returns:
            Updated consent
        """
        self._consents[consent.patient_id] = consent

        logger.info(f"Updated consent for patient {consent.patient_id}: {consent.status.value}")

        return consent

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics.

        Returns:
            Dictionary with service stats
        """
        active_qhins = len([q for q in self._qhins if q.status == QHINStatus.ACTIVE])
        total_participants = sum(q.participant_count for q in self._qhins)

        return {
            "total_qhins": len(self._qhins),
            "active_qhins": active_qhins,
            "total_participants": total_participants,
            "audit_log_count": len(self._audit_logs),
            "consent_records": len(self._consents),
            "cached_documents": len(self._cached_documents),
        }


# Module-level accessor functions
def get_tefca_service() -> TEFCAService:
    """Get the singleton TEFCA service instance."""
    return TEFCAService.get_instance()


def reset_tefca_service() -> None:
    """Reset the singleton TEFCA service instance (for testing)."""
    TEFCAService.reset_instance()
