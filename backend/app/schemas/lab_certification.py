"""Pydantic schemas for Lab Certification & Accreditation (CLINICAL-LC).

Manages central and local laboratory certifications, accreditation tracking,
proficiency testing, lab qualifications for clinical trials, and compliance
monitoring with corrective action tracking.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CertificationType(str, Enum):
    """Type of laboratory certification held."""

    CLIA = "clia"
    CAP = "cap"
    ISO_15189 = "iso_15189"
    GCP_COMPLIANT = "gcp_compliant"
    GMP_COMPLIANT = "gmp_compliant"
    STATE_LICENSE = "state_license"


class CertificationStatus(str, Enum):
    """Lifecycle status of a laboratory certification."""

    ACTIVE = "active"
    PENDING = "pending"
    EXPIRED = "expired"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class AccreditationBody(str, Enum):
    """Organization that granted the accreditation."""

    CAP = "cap"
    CLIA = "clia"
    ISO = "iso"
    JIS = "jis"
    COFRAC = "cofrac"
    UKAS = "ukas"
    DAKKS = "dakks"


class ProficiencyResult(str, Enum):
    """Outcome of a proficiency testing cycle."""

    SATISFACTORY = "satisfactory"
    UNSATISFACTORY = "unsatisfactory"
    NOT_GRADED = "not_graded"
    PENDING = "pending"


class LabType(str, Enum):
    """Classification of laboratory facility."""

    CENTRAL = "central"
    LOCAL = "local"
    SPECIALTY = "specialty"
    REFERENCE = "reference"
    BIOANALYTICAL = "bioanalytical"


class FindingSeverity(str, Enum):
    """Severity classification for a compliance finding."""

    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    OBSERVATION = "observation"


class FindingType(str, Enum):
    """Category of compliance finding."""

    DOCUMENTATION = "documentation"
    PROCESS = "process"
    EQUIPMENT = "equipment"
    PERSONNEL = "personnel"
    QUALITY_CONTROL = "quality_control"
    DATA_INTEGRITY = "data_integrity"


class ComplianceFindingStatus(str, Enum):
    """Lifecycle status of a compliance finding."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    VERIFIED = "verified"
    OVERDUE = "overdue"


class QualificationStatus(str, Enum):
    """Status of a laboratory qualification for a clinical trial."""

    PENDING = "pending"
    QUALIFIED = "qualified"
    CONDITIONALLY_QUALIFIED = "conditionally_qualified"
    DISQUALIFIED = "disqualified"
    SUSPENDED = "suspended"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class Laboratory(BaseModel):
    """A laboratory facility participating in clinical trials."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique laboratory identifier")
    name: str = Field(..., description="Laboratory name")
    lab_type: LabType = Field(..., description="Type of laboratory")
    address: str = Field(..., description="Full mailing address")
    country: str = Field(..., description="Country code (ISO 3166-1 alpha-2)")
    contact_name: str = Field(..., description="Primary contact person name")
    contact_email: str = Field(..., description="Primary contact email address")
    phone: str = Field(..., description="Primary phone number")
    active: bool = Field(default=True, description="Whether the laboratory is currently active")
    capabilities: list[str] = Field(
        default_factory=list,
        description="List of analytical capabilities (e.g., hematology, chemistry)",
    )
    specializations: list[str] = Field(
        default_factory=list,
        description="List of therapeutic area specializations",
    )


class LabCertification(BaseModel):
    """A certification or accreditation held by a laboratory."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique certification record identifier")
    lab_id: str = Field(..., description="Associated laboratory identifier")
    certification_type: CertificationType = Field(
        ..., description="Type of certification"
    )
    accreditation_body: AccreditationBody = Field(
        ..., description="Body that granted the accreditation"
    )
    certificate_number: str = Field(..., description="Official certificate or license number")
    issued_date: datetime = Field(..., description="Date the certification was issued")
    expiry_date: datetime = Field(..., description="Date the certification expires")
    status: CertificationStatus = Field(
        default=CertificationStatus.ACTIVE,
        description="Current certification status",
    )
    scope: str = Field(
        ..., description="Scope of the certification (e.g., analytes, test categories)"
    )
    last_inspection_date: datetime | None = Field(
        None, description="Date of the most recent inspection"
    )
    next_inspection_date: datetime | None = Field(
        None, description="Scheduled date for the next inspection"
    )
    findings_count: int = Field(
        default=0, ge=0, description="Number of findings from the last inspection"
    )
    corrective_actions_pending: int = Field(
        default=0, ge=0, description="Number of pending corrective actions"
    )


class ProficiencyTest(BaseModel):
    """A proficiency testing event for a laboratory analyte."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique proficiency test identifier")
    lab_id: str = Field(..., description="Associated laboratory identifier")
    test_name: str = Field(..., description="Name of the proficiency test program")
    analyte: str = Field(..., description="Analyte tested (e.g., Hemoglobin A1c, Creatinine)")
    sample_id: str = Field(..., description="Proficiency sample identifier")
    expected_value: float = Field(..., description="Expected/target value for the analyte")
    reported_value: float = Field(..., description="Value reported by the laboratory")
    result: ProficiencyResult = Field(
        default=ProficiencyResult.PENDING,
        description="Proficiency test outcome",
    )
    tested_date: datetime = Field(..., description="Date the sample was tested")
    reported_date: datetime = Field(..., description="Date the result was reported")
    cycle: str = Field(..., description="Proficiency testing cycle (e.g., 2026-Q1)")
    notes: str | None = Field(None, description="Additional notes or comments")


class LabQualification(BaseModel):
    """Qualification record for a laboratory to participate in a specific trial."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique qualification record identifier")
    lab_id: str = Field(..., description="Associated laboratory identifier")
    trial_id: str = Field(..., description="Clinical trial identifier")
    qualified_date: datetime | None = Field(
        None, description="Date the lab was qualified for the trial"
    )
    qualification_status: QualificationStatus = Field(
        default=QualificationStatus.PENDING,
        description="Current qualification status",
    )
    assays_qualified: list[str] = Field(
        default_factory=list,
        description="List of assays the lab is qualified to run for the trial",
    )
    training_completed: bool = Field(
        default=False, description="Whether trial-specific training has been completed"
    )
    equipment_verified: bool = Field(
        default=False, description="Whether required equipment has been verified"
    )
    sop_reviewed: bool = Field(
        default=False, description="Whether SOPs have been reviewed and acknowledged"
    )
    qualified_by: str | None = Field(
        None, description="Name of the person who approved the qualification"
    )
    notes: str | None = Field(None, description="Qualification notes or conditions")


class ComplianceFinding(BaseModel):
    """A compliance finding from an inspection or audit of a laboratory."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique finding identifier")
    lab_id: str = Field(..., description="Associated laboratory identifier")
    certification_id: str | None = Field(
        None, description="Associated certification record identifier"
    )
    finding_type: FindingType = Field(..., description="Category of the finding")
    severity: FindingSeverity = Field(..., description="Severity classification")
    description: str = Field(..., description="Detailed description of the finding")
    identified_date: datetime = Field(..., description="Date the finding was identified")
    due_date: datetime = Field(..., description="Due date for corrective action")
    resolved_date: datetime | None = Field(
        None, description="Date the finding was resolved"
    )
    corrective_action: str | None = Field(
        None, description="Description of the corrective action taken"
    )
    status: ComplianceFindingStatus = Field(
        default=ComplianceFindingStatus.OPEN,
        description="Current finding status",
    )


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class LaboratoryCreate(BaseModel):
    """Request to create a new laboratory."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Laboratory name")
    lab_type: LabType = Field(..., description="Type of laboratory")
    address: str = Field(..., description="Full mailing address")
    country: str = Field(..., description="Country code (ISO 3166-1 alpha-2)")
    contact_name: str = Field(..., description="Primary contact person name")
    contact_email: str = Field(..., description="Primary contact email address")
    phone: str = Field(..., description="Primary phone number")
    capabilities: list[str] = Field(default_factory=list, description="Analytical capabilities")
    specializations: list[str] = Field(
        default_factory=list, description="Therapeutic area specializations"
    )


class LaboratoryUpdate(BaseModel):
    """Request to update a laboratory."""

    model_config = ConfigDict(from_attributes=True)

    name: str | None = Field(None, description="Laboratory name")
    lab_type: LabType | None = Field(None, description="Type of laboratory")
    address: str | None = Field(None, description="Address")
    country: str | None = Field(None, description="Country code")
    contact_name: str | None = Field(None, description="Contact name")
    contact_email: str | None = Field(None, description="Contact email")
    phone: str | None = Field(None, description="Phone number")
    active: bool | None = Field(None, description="Active status")
    capabilities: list[str] | None = Field(None, description="Capabilities")
    specializations: list[str] | None = Field(None, description="Specializations")


class LabCertificationCreate(BaseModel):
    """Request to create a new lab certification."""

    model_config = ConfigDict(from_attributes=True)

    lab_id: str = Field(..., description="Laboratory identifier")
    certification_type: CertificationType = Field(..., description="Certification type")
    accreditation_body: AccreditationBody = Field(..., description="Accreditation body")
    certificate_number: str = Field(..., description="Certificate number")
    issued_date: datetime = Field(..., description="Date issued")
    expiry_date: datetime = Field(..., description="Expiry date")
    scope: str = Field(..., description="Certification scope")
    status: CertificationStatus = Field(
        default=CertificationStatus.ACTIVE, description="Initial status"
    )


class LabCertificationUpdate(BaseModel):
    """Request to update a lab certification."""

    model_config = ConfigDict(from_attributes=True)

    certification_type: CertificationType | None = Field(None, description="Certification type")
    accreditation_body: AccreditationBody | None = Field(None, description="Accreditation body")
    certificate_number: str | None = Field(None, description="Certificate number")
    issued_date: datetime | None = Field(None, description="Date issued")
    expiry_date: datetime | None = Field(None, description="Expiry date")
    status: CertificationStatus | None = Field(None, description="Status")
    scope: str | None = Field(None, description="Scope")
    last_inspection_date: datetime | None = Field(None, description="Last inspection date")
    next_inspection_date: datetime | None = Field(None, description="Next inspection date")
    findings_count: int | None = Field(None, ge=0, description="Findings count")
    corrective_actions_pending: int | None = Field(
        None, ge=0, description="Pending corrective actions"
    )


class ProficiencyTestCreate(BaseModel):
    """Request to record a proficiency test."""

    model_config = ConfigDict(from_attributes=True)

    lab_id: str = Field(..., description="Laboratory identifier")
    test_name: str = Field(..., description="Proficiency test program name")
    analyte: str = Field(..., description="Analyte tested")
    sample_id: str = Field(..., description="Proficiency sample ID")
    expected_value: float = Field(..., description="Expected value")
    reported_value: float = Field(..., description="Reported value")
    result: ProficiencyResult = Field(
        default=ProficiencyResult.PENDING, description="Test result"
    )
    tested_date: datetime = Field(..., description="Date tested")
    reported_date: datetime = Field(..., description="Date reported")
    cycle: str = Field(..., description="Testing cycle")
    notes: str | None = Field(None, description="Notes")


class ProficiencyTestUpdate(BaseModel):
    """Request to update a proficiency test record."""

    model_config = ConfigDict(from_attributes=True)

    reported_value: float | None = Field(None, description="Reported value")
    result: ProficiencyResult | None = Field(None, description="Test result")
    reported_date: datetime | None = Field(None, description="Date reported")
    notes: str | None = Field(None, description="Notes")


class LabQualificationCreate(BaseModel):
    """Request to qualify a lab for a trial."""

    model_config = ConfigDict(from_attributes=True)

    lab_id: str = Field(..., description="Laboratory identifier")
    trial_id: str = Field(..., description="Trial identifier")
    assays_qualified: list[str] = Field(
        default_factory=list, description="Assays to qualify"
    )
    training_completed: bool = Field(default=False, description="Training completed")
    equipment_verified: bool = Field(default=False, description="Equipment verified")
    sop_reviewed: bool = Field(default=False, description="SOPs reviewed")
    qualified_by: str | None = Field(None, description="Qualified by")
    notes: str | None = Field(None, description="Qualification notes")


class LabQualificationUpdate(BaseModel):
    """Request to update a lab qualification."""

    model_config = ConfigDict(from_attributes=True)

    qualification_status: QualificationStatus | None = Field(
        None, description="Qualification status"
    )
    assays_qualified: list[str] | None = Field(None, description="Assays qualified")
    training_completed: bool | None = Field(None, description="Training completed")
    equipment_verified: bool | None = Field(None, description="Equipment verified")
    sop_reviewed: bool | None = Field(None, description="SOPs reviewed")
    qualified_by: str | None = Field(None, description="Qualified by")
    notes: str | None = Field(None, description="Notes")


class ComplianceFindingCreate(BaseModel):
    """Request to log a compliance finding."""

    model_config = ConfigDict(from_attributes=True)

    lab_id: str = Field(..., description="Laboratory identifier")
    certification_id: str | None = Field(None, description="Certification identifier")
    finding_type: FindingType = Field(..., description="Finding type")
    severity: FindingSeverity = Field(..., description="Severity")
    description: str = Field(..., description="Description")
    due_date: datetime = Field(..., description="Due date for corrective action")
    corrective_action: str | None = Field(None, description="Corrective action plan")


class ComplianceFindingUpdate(BaseModel):
    """Request to update a compliance finding."""

    model_config = ConfigDict(from_attributes=True)

    finding_type: FindingType | None = Field(None, description="Finding type")
    severity: FindingSeverity | None = Field(None, description="Severity")
    description: str | None = Field(None, description="Description")
    due_date: datetime | None = Field(None, description="Due date")
    resolved_date: datetime | None = Field(None, description="Resolved date")
    corrective_action: str | None = Field(None, description="Corrective action")
    status: ComplianceFindingStatus | None = Field(None, description="Status")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class LaboratoryListResponse(BaseModel):
    """List of laboratories."""

    model_config = ConfigDict(from_attributes=True)

    items: list[Laboratory] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class LabCertificationListResponse(BaseModel):
    """List of lab certifications."""

    model_config = ConfigDict(from_attributes=True)

    items: list[LabCertification] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class ProficiencyTestListResponse(BaseModel):
    """List of proficiency tests."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ProficiencyTest] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class LabQualificationListResponse(BaseModel):
    """List of lab qualifications."""

    model_config = ConfigDict(from_attributes=True)

    items: list[LabQualification] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class ComplianceFindingListResponse(BaseModel):
    """List of compliance findings."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ComplianceFinding] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


# ---------------------------------------------------------------------------
# Metrics / dashboard
# ---------------------------------------------------------------------------


class LabMetrics(BaseModel):
    """Aggregated lab certification and accreditation metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_labs: int = Field(ge=0, description="Total registered laboratories")
    active_labs: int = Field(ge=0, description="Number of active laboratories")
    labs_by_type: dict[str, int] = Field(
        default_factory=dict, description="Lab counts by type"
    )
    total_certifications: int = Field(ge=0, description="Total certifications tracked")
    active_certifications: int = Field(ge=0, description="Number of active certifications")
    expiring_soon: int = Field(
        ge=0, description="Certifications expiring within 90 days"
    )
    expired_certifications: int = Field(ge=0, description="Number of expired certifications")
    certifications_by_status: dict[str, int] = Field(
        default_factory=dict, description="Certification counts by status"
    )
    total_proficiency_tests: int = Field(ge=0, description="Total proficiency tests recorded")
    satisfactory_rate: float = Field(
        ge=0.0, le=100.0,
        description="Percentage of proficiency tests with satisfactory results",
    )
    total_qualifications: int = Field(ge=0, description="Total lab-trial qualifications")
    qualified_count: int = Field(ge=0, description="Number of fully qualified labs")
    total_compliance_findings: int = Field(ge=0, description="Total compliance findings")
    open_findings: int = Field(ge=0, description="Number of open/in-progress findings")
    overdue_findings: int = Field(ge=0, description="Number of overdue findings")
    critical_findings: int = Field(ge=0, description="Number of critical severity findings")
