"""Pydantic schemas for Electronic Trial Master File (CLINICAL-5).

Implements the DIA TMF Reference Model for organizing, tracking, and managing
essential clinical trial documents across all 11 TMF zones.

Provides structured models for:
- TMF document lifecycle (draft -> review -> approval -> effective -> archived)
- Document signatures (electronic, wet-ink, digital certificate)
- Zone completeness analysis and section tracking
- Inspection readiness checklists and findings
- Compliance rules (21 CFR Part 11, GDPR, ICH E6)
- TMF metrics and dashboard data
- Bulk import capabilities
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TMFZone(str, Enum):
    """DIA TMF Reference Model zones (1-11)."""

    ZONE_01_TRIAL_MANAGEMENT = "ZONE_01_TRIAL_MANAGEMENT"
    ZONE_02_CENTRAL_TRIAL_DOCS = "ZONE_02_CENTRAL_TRIAL_DOCS"
    ZONE_03_IRB_IEC = "ZONE_03_IRB_IEC"
    ZONE_04_REGULATORY = "ZONE_04_REGULATORY"
    ZONE_05_SITE_MANAGEMENT = "ZONE_05_SITE_MANAGEMENT"
    ZONE_06_IP_MANAGEMENT = "ZONE_06_IP_MANAGEMENT"
    ZONE_07_SAFETY_REPORTING = "ZONE_07_SAFETY_REPORTING"
    ZONE_08_CENTRAL_AND_LOCAL_TESTING = "ZONE_08_CENTRAL_AND_LOCAL_TESTING"
    ZONE_09_THIRD_PARTIES = "ZONE_09_THIRD_PARTIES"
    ZONE_10_DATA_MANAGEMENT = "ZONE_10_DATA_MANAGEMENT"
    ZONE_11_STATISTICS = "ZONE_11_STATISTICS"


class DocumentStatus(str, Enum):
    """Lifecycle status of a TMF document."""

    DRAFT = "DRAFT"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    EFFECTIVE = "EFFECTIVE"
    SUPERSEDED = "SUPERSEDED"
    ARCHIVED = "ARCHIVED"
    WITHDRAWN = "WITHDRAWN"


class ComplianceStatus(str, Enum):
    """Compliance assessment status."""

    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    PARTIALLY_COMPLIANT = "PARTIALLY_COMPLIANT"
    NOT_ASSESSED = "NOT_ASSESSED"


class ArtifactType(str, Enum):
    """TMF artifact types per DIA reference model."""

    PROTOCOL = "PROTOCOL"
    ICF = "ICF"
    IB = "IB"
    CSR = "CSR"
    SAP = "SAP"
    CRF = "CRF"
    SAE_REPORT = "SAE_REPORT"
    MONITORING_REPORT = "MONITORING_REPORT"
    DELEGATION_LOG = "DELEGATION_LOG"
    FINANCIAL_DISCLOSURE = "FINANCIAL_DISCLOSURE"
    CV = "CV"
    MEDICAL_LICENSE = "MEDICAL_LICENSE"
    IRB_APPROVAL = "IRB_APPROVAL"
    SITE_CONTRACT = "SITE_CONTRACT"
    DRUG_ACCOUNTABILITY = "DRUG_ACCOUNTABILITY"


class InspectionReadiness(str, Enum):
    """Overall inspection readiness assessment."""

    READY = "READY"
    AT_RISK = "AT_RISK"
    NOT_READY = "NOT_READY"
    IN_PREPARATION = "IN_PREPARATION"


class SignatureType(str, Enum):
    """Type of document signature."""

    ELECTRONIC = "ELECTRONIC"
    WET_INK = "WET_INK"
    DIGITAL_CERTIFICATE = "DIGITAL_CERTIFICATE"


# ---------------------------------------------------------------------------
# Core Models
# ---------------------------------------------------------------------------


class DocumentSignature(BaseModel):
    """A signature applied to a TMF document."""

    model_config = ConfigDict(from_attributes=True)

    signer_name: str = Field(..., description="Full name of the signer")
    signer_role: str = Field(..., description="Role of the signer (e.g. PI, Sponsor, CRA)")
    signature_type: SignatureType = Field(..., description="Type of signature")
    signed_at: datetime = Field(..., description="Timestamp when signed")
    reason: str = Field(default="", description="Reason for signature (e.g. approval, acknowledgement)")


class TMFDocument(BaseModel):
    """A document within the Trial Master File."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique document identifier")
    trial_id: str = Field(..., description="Associated clinical trial ID")
    zone: TMFZone = Field(..., description="TMF zone classification")
    artifact_type: ArtifactType = Field(..., description="Document artifact type")
    title: str = Field(..., description="Document title")
    description: str = Field(default="", description="Document description")
    version: str = Field(default="1.0", description="Document version")
    status: DocumentStatus = Field(default=DocumentStatus.DRAFT, description="Current status")
    file_path: str = Field(default="", description="Storage path for the document file")
    file_size_bytes: int = Field(default=0, ge=0, description="File size in bytes")
    mime_type: str = Field(default="application/pdf", description="MIME type of the file")
    uploaded_by: str = Field(default="", description="User who uploaded the document")
    uploaded_at: datetime = Field(..., description="Upload timestamp")
    reviewed_by: str | None = Field(default=None, description="Reviewer name")
    reviewed_at: datetime | None = Field(default=None, description="Review timestamp")
    approved_by: str | None = Field(default=None, description="Approver name")
    approved_at: datetime | None = Field(default=None, description="Approval timestamp")
    effective_date: date | None = Field(default=None, description="Date document becomes effective")
    expiry_date: date | None = Field(default=None, description="Document expiry date")
    site_id: str | None = Field(default=None, description="Site ID if site-specific")
    country: str | None = Field(default=None, description="Country code if country-specific")
    signatures: list[DocumentSignature] = Field(default_factory=list, description="Applied signatures")
    metadata_tags: dict[str, str] = Field(default_factory=dict, description="Arbitrary metadata tags")
    compliance_status: ComplianceStatus = Field(
        default=ComplianceStatus.NOT_ASSESSED, description="Compliance assessment"
    )
    part11_compliant: bool = Field(default=False, description="21 CFR Part 11 compliance flag")
    gdpr_compliant: bool = Field(default=False, description="GDPR compliance flag")


class InspectionFinding(BaseModel):
    """A finding from an inspection checklist."""

    model_config = ConfigDict(from_attributes=True)

    zone: TMFZone = Field(..., description="TMF zone where finding was identified")
    description: str = Field(..., description="Finding description")
    severity: str = Field(default="minor", description="Severity: critical, major, minor, observation")
    corrective_action: str = Field(default="", description="Planned corrective action")
    due_date: date | None = Field(default=None, description="CAPA due date")
    resolved: bool = Field(default=False, description="Whether finding has been resolved")


class TMFSection(BaseModel):
    """Analysis of a TMF zone section for completeness and compliance."""

    model_config = ConfigDict(from_attributes=True)

    zone: TMFZone = Field(..., description="TMF zone")
    artifact_type: ArtifactType | None = Field(
        default=None, description="Specific artifact type (None = zone-level)"
    )
    expected_documents: int = Field(default=0, ge=0, description="Expected document count")
    actual_documents: int = Field(default=0, ge=0, description="Actual document count")
    completeness_percent: float = Field(default=0.0, ge=0.0, le=100.0, description="Completeness %")
    compliance_status: ComplianceStatus = Field(
        default=ComplianceStatus.NOT_ASSESSED, description="Section compliance"
    )
    missing_documents: list[str] = Field(default_factory=list, description="List of missing document titles")
    overdue_documents: list[str] = Field(default_factory=list, description="List of overdue document titles")


class InspectionChecklist(BaseModel):
    """An inspection readiness checklist."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Checklist identifier")
    trial_id: str = Field(..., description="Associated trial ID")
    inspector_name: str = Field(default="", description="Inspector or auditor name")
    inspection_type: str = Field(default="routine", description="Type: routine, for-cause, pre-approval")
    inspection_date: date | None = Field(default=None, description="Planned inspection date")
    zones_reviewed: list[TMFZone] = Field(default_factory=list, description="Zones under review")
    findings: list[InspectionFinding] = Field(default_factory=list, description="Inspection findings")
    overall_readiness: InspectionReadiness = Field(
        default=InspectionReadiness.IN_PREPARATION, description="Overall readiness"
    )
    created_at: datetime = Field(..., description="Checklist creation timestamp")


class TMFMetrics(BaseModel):
    """Aggregated eTMF metrics for a trial or across trials."""

    model_config = ConfigDict(from_attributes=True)

    total_documents: int = Field(default=0, ge=0, description="Total document count")
    by_zone: dict[str, int] = Field(default_factory=dict, description="Document count per zone")
    by_status: dict[str, int] = Field(default_factory=dict, description="Document count per status")
    completeness_percent: float = Field(default=0.0, ge=0.0, le=100.0, description="Overall completeness %")
    compliance_percent: float = Field(default=0.0, ge=0.0, le=100.0, description="Overall compliance %")
    overdue_reviews: int = Field(default=0, ge=0, description="Documents with overdue reviews")
    pending_signatures: int = Field(default=0, ge=0, description="Documents awaiting signatures")
    inspection_readiness: InspectionReadiness = Field(
        default=InspectionReadiness.IN_PREPARATION, description="Overall readiness"
    )
    part11_compliance_rate: float = Field(default=0.0, ge=0.0, le=100.0, description="Part 11 compliance %")
    documents_expiring_30d: int = Field(default=0, ge=0, description="Documents expiring within 30 days")


class ComplianceRule(BaseModel):
    """A compliance rule defining requirements for TMF documents."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Rule identifier")
    name: str = Field(..., description="Rule name")
    zone: TMFZone = Field(..., description="Applicable TMF zone")
    artifact_type: ArtifactType = Field(..., description="Applicable artifact type")
    description: str = Field(default="", description="Rule description")
    required: bool = Field(default=True, description="Whether this document is required")
    review_frequency_days: int = Field(default=365, ge=0, description="Review frequency in days")
    retention_years: int = Field(default=15, ge=0, description="Retention period in years")
    part11_requirement: bool = Field(default=False, description="Requires 21 CFR Part 11 compliance")
    gdpr_requirement: bool = Field(default=False, description="Requires GDPR compliance")


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------


class TMFDocumentCreate(BaseModel):
    """Request to create a new TMF document."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Associated clinical trial ID")
    zone: TMFZone = Field(..., description="TMF zone classification")
    artifact_type: ArtifactType = Field(..., description="Artifact type")
    title: str = Field(..., min_length=1, description="Document title")
    description: str = Field(default="", description="Description")
    version: str = Field(default="1.0", description="Version string")
    file_path: str = Field(default="", description="File storage path")
    file_size_bytes: int = Field(default=0, ge=0, description="File size in bytes")
    mime_type: str = Field(default="application/pdf", description="MIME type")
    uploaded_by: str = Field(default="system", description="Uploader name")
    effective_date: date | None = Field(default=None, description="Effective date")
    expiry_date: date | None = Field(default=None, description="Expiry date")
    site_id: str | None = Field(default=None, description="Site ID if site-specific")
    country: str | None = Field(default=None, description="Country code")
    metadata_tags: dict[str, str] = Field(default_factory=dict, description="Metadata tags")


class TMFDocumentUpdate(BaseModel):
    """Request to update a TMF document."""

    model_config = ConfigDict(from_attributes=True)

    title: str | None = Field(default=None, description="Updated title")
    description: str | None = Field(default=None, description="Updated description")
    version: str | None = Field(default=None, description="Updated version")
    status: DocumentStatus | None = Field(default=None, description="Updated status")
    file_path: str | None = Field(default=None, description="Updated file path")
    file_size_bytes: int | None = Field(default=None, ge=0, description="Updated file size")
    mime_type: str | None = Field(default=None, description="Updated MIME type")
    effective_date: date | None = Field(default=None, description="Updated effective date")
    expiry_date: date | None = Field(default=None, description="Updated expiry date")
    site_id: str | None = Field(default=None, description="Updated site ID")
    country: str | None = Field(default=None, description="Updated country")
    metadata_tags: dict[str, str] | None = Field(default=None, description="Updated metadata tags")
    compliance_status: ComplianceStatus | None = Field(default=None, description="Updated compliance")
    part11_compliant: bool | None = Field(default=None, description="Updated Part 11 flag")
    gdpr_compliant: bool | None = Field(default=None, description="Updated GDPR flag")


class DocumentApprovalRequest(BaseModel):
    """Request to approve a TMF document."""

    approved_by: str = Field(..., min_length=1, description="Approver name")
    effective_date: date | None = Field(default=None, description="Effective date override")
    comment: str = Field(default="", description="Approval comment")


class DocumentReviewRequest(BaseModel):
    """Request to submit a review for a TMF document."""

    reviewed_by: str = Field(..., min_length=1, description="Reviewer name")
    comment: str = Field(default="", description="Review comment")
    approved: bool = Field(default=True, description="Whether to advance to APPROVED status")


class SignatureRequest(BaseModel):
    """Request to add a signature to a document."""

    signer_name: str = Field(..., min_length=1, description="Signer name")
    signer_role: str = Field(..., min_length=1, description="Signer role")
    signature_type: SignatureType = Field(default=SignatureType.ELECTRONIC, description="Signature type")
    reason: str = Field(default="", description="Reason for signing")


class ComplianceRuleCreate(BaseModel):
    """Request to create a compliance rule."""

    name: str = Field(..., min_length=1, description="Rule name")
    zone: TMFZone = Field(..., description="Applicable zone")
    artifact_type: ArtifactType = Field(..., description="Applicable artifact type")
    description: str = Field(default="", description="Rule description")
    required: bool = Field(default=True, description="Whether required")
    review_frequency_days: int = Field(default=365, ge=0, description="Review frequency")
    retention_years: int = Field(default=15, ge=0, description="Retention period")
    part11_requirement: bool = Field(default=False, description="Part 11 required")
    gdpr_requirement: bool = Field(default=False, description="GDPR required")


class ComplianceRuleUpdate(BaseModel):
    """Request to update a compliance rule."""

    name: str | None = Field(default=None, description="Updated name")
    description: str | None = Field(default=None, description="Updated description")
    required: bool | None = Field(default=None, description="Updated required flag")
    review_frequency_days: int | None = Field(default=None, ge=0, description="Updated frequency")
    retention_years: int | None = Field(default=None, ge=0, description="Updated retention")
    part11_requirement: bool | None = Field(default=None, description="Updated Part 11 flag")
    gdpr_requirement: bool | None = Field(default=None, description="Updated GDPR flag")


class InspectionChecklistCreate(BaseModel):
    """Request to create an inspection checklist."""

    trial_id: str = Field(..., description="Trial ID")
    inspector_name: str = Field(default="", description="Inspector name")
    inspection_type: str = Field(default="routine", description="Inspection type")
    inspection_date: date | None = Field(default=None, description="Planned date")
    zones_reviewed: list[TMFZone] = Field(default_factory=list, description="Zones to review")


class InspectionFindingCreate(BaseModel):
    """Request to add a finding to an inspection checklist."""

    zone: TMFZone = Field(..., description="Zone where finding identified")
    description: str = Field(..., min_length=1, description="Finding description")
    severity: str = Field(default="minor", description="Severity level")
    corrective_action: str = Field(default="", description="Corrective action")
    due_date: date | None = Field(default=None, description="CAPA due date")


class BulkImportRequest(BaseModel):
    """Request for bulk document import."""

    documents: list[TMFDocumentCreate] = Field(..., min_length=1, description="Documents to import")


class BulkImportResponse(BaseModel):
    """Response from bulk document import."""

    imported: int = Field(default=0, description="Number of documents imported")
    failed: int = Field(default=0, description="Number of failures")
    document_ids: list[str] = Field(default_factory=list, description="IDs of imported documents")
    errors: list[str] = Field(default_factory=list, description="Error messages")


# ---------------------------------------------------------------------------
# List / Paginated Response Models
# ---------------------------------------------------------------------------


class TMFDocumentListResponse(BaseModel):
    """Paginated list of TMF documents."""

    items: list[TMFDocument] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=0)
    offset: int = Field(default=0, ge=0)


class ComplianceRuleListResponse(BaseModel):
    """List of compliance rules."""

    items: list[ComplianceRule] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)


class InspectionChecklistListResponse(BaseModel):
    """List of inspection checklists."""

    items: list[InspectionChecklist] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)


class TMFSectionListResponse(BaseModel):
    """List of TMF zone sections."""

    items: list[TMFSection] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)


class ExpiringDocumentsResponse(BaseModel):
    """Documents approaching expiry."""

    items: list[TMFDocument] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)
    days_ahead: int = Field(default=30, description="Look-ahead window in days")


class MissingDocumentsResponse(BaseModel):
    """Missing documents per zone."""

    trial_id: str = Field(..., description="Trial ID")
    missing: list[TMFSection] = Field(default_factory=list)
    total_missing: int = Field(default=0, ge=0)
