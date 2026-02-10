"""Pydantic schemas for Ancillary Study Management.

Manages sub-studies, companion diagnostics, biomarker studies, pharmacokinetic
studies, and their integration with parent trials. Covers ancillary study
lifecycle, sample collection and tracking, study endpoint definitions,
sub-study site activation, data sharing agreements, and operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AncillaryStudyType(str, Enum):
    """Type of ancillary or sub-study."""

    PK_STUDY = "pk_study"
    PD_STUDY = "pd_study"
    BIOMARKER = "biomarker"
    COMPANION_DIAGNOSTIC = "companion_diagnostic"
    IMAGING = "imaging"
    GENETIC = "genetic"
    QUALITY_OF_LIFE = "quality_of_life"
    HEALTH_ECONOMICS = "health_economics"
    REGISTRY = "registry"
    LONG_TERM_EXTENSION = "long_term_extension"


class StudyRelationship(str, Enum):
    """Relationship between the ancillary study and the parent trial."""

    EMBEDDED = "embedded"
    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"
    OPTIONAL = "optional"
    MANDATORY = "mandatory"


class AncillaryStatus(str, Enum):
    """Lifecycle status of an ancillary study."""

    PLANNED = "planned"
    PROTOCOL_DEVELOPMENT = "protocol_development"
    IRB_PENDING = "irb_pending"
    ACTIVE = "active"
    ENROLLING = "enrolling"
    FOLLOW_UP = "follow_up"
    COMPLETED = "completed"
    TERMINATED = "terminated"


class SampleType(str, Enum):
    """Biological sample type collected for the ancillary study."""

    BLOOD = "blood"
    SERUM = "serum"
    PLASMA = "plasma"
    URINE = "urine"
    TISSUE = "tissue"
    CSF = "csf"
    SALIVA = "saliva"
    BONE_MARROW = "bone_marrow"


class AnalysisStatus(str, Enum):
    """Status of sample analysis."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REPEATED = "repeated"


class EndpointType(str, Enum):
    """Type of study endpoint."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    EXPLORATORY = "exploratory"
    SAFETY = "safety"


class SubStudySiteStatus(str, Enum):
    """Activation status of a sub-study site."""

    PENDING = "pending"
    ACTIVATED = "activated"
    ENROLLING = "enrolling"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class AgreementType(str, Enum):
    """Type of data sharing agreement."""

    DATA_USE_AGREEMENT = "data_use_agreement"
    MATERIAL_TRANSFER = "material_transfer"
    COLLABORATION = "collaboration"
    LICENSE = "license"


class AgreementStatus(str, Enum):
    """Status of a data sharing agreement."""

    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class AncillaryStudy(BaseModel):
    """An ancillary or sub-study linked to a parent clinical trial."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique ancillary study identifier")
    parent_trial_id: str = Field(..., description="Parent clinical trial identifier")
    study_name: str = Field(..., description="Name of the ancillary study")
    study_type: AncillaryStudyType = Field(..., description="Type of ancillary study")
    relationship: StudyRelationship = Field(
        ..., description="Relationship to parent trial"
    )
    status: AncillaryStatus = Field(..., description="Current lifecycle status")
    protocol_number: str = Field(..., description="Protocol number for the sub-study")
    pi_name: str = Field(..., description="Principal Investigator name")
    pi_institution: str = Field(..., description="PI institutional affiliation")
    start_date: datetime | None = Field(None, description="Planned or actual start date")
    end_date: datetime | None = Field(None, description="Planned or actual end date")
    target_enrollment: int = Field(ge=0, description="Target enrollment count")
    current_enrollment: int = Field(default=0, ge=0, description="Current enrollment count")
    budget: float = Field(ge=0.0, description="Study budget in USD")
    funding_source: str = Field(..., description="Source of study funding")
    description: str = Field(..., description="Detailed study description")
    created_at: datetime = Field(..., description="Record creation timestamp")


class StudySample(BaseModel):
    """A biological sample collected for an ancillary study."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique sample identifier")
    ancillary_study_id: str = Field(..., description="Associated ancillary study ID")
    patient_id: str = Field(..., description="Patient identifier")
    site_id: str = Field(..., description="Collection site identifier")
    sample_type: SampleType = Field(..., description="Type of biological sample")
    collection_date: datetime = Field(..., description="Date sample was collected")
    visit_number: int = Field(ge=1, description="Visit number at which sample was collected")
    processing_instructions: str = Field(
        ..., description="Instructions for sample processing"
    )
    storage_condition: str = Field(..., description="Required storage condition (e.g., -80C)")
    aliquot_count: int = Field(ge=1, description="Number of aliquots created")
    shipped_to_lab: bool = Field(default=False, description="Whether sample has been shipped to lab")
    lab_received_date: datetime | None = Field(
        None, description="Date lab received the sample"
    )
    analysis_status: AnalysisStatus = Field(
        default=AnalysisStatus.PENDING, description="Current analysis status"
    )
    results_available: bool = Field(
        default=False, description="Whether analysis results are available"
    )


class StudyEndpoint(BaseModel):
    """A defined endpoint for an ancillary study."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique endpoint identifier")
    ancillary_study_id: str = Field(..., description="Associated ancillary study ID")
    endpoint_name: str = Field(..., description="Name of the endpoint")
    endpoint_type: EndpointType = Field(..., description="Type of endpoint")
    description: str = Field(..., description="Detailed endpoint description")
    measurement_method: str = Field(..., description="How the endpoint is measured")
    measurement_timepoints: list[str] = Field(
        default_factory=list,
        description="Timepoints at which endpoint is measured (e.g., Baseline, Week 4)",
    )
    target_value: str | None = Field(
        None, description="Target value or threshold for success"
    )
    statistical_method: str = Field(
        ..., description="Statistical method for analysis"
    )
    analysis_population: str = Field(
        ..., description="Population used for analysis (e.g., ITT, Per-Protocol)"
    )


class SubStudySite(BaseModel):
    """A participating site in an ancillary study."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique sub-study site record identifier")
    ancillary_study_id: str = Field(..., description="Associated ancillary study ID")
    site_id: str = Field(..., description="Site identifier")
    site_name: str = Field(..., description="Site name")
    activation_date: datetime | None = Field(
        None, description="Date the site was activated for the sub-study"
    )
    status: SubStudySiteStatus = Field(
        default=SubStudySiteStatus.PENDING, description="Site activation status"
    )
    patients_enrolled: int = Field(
        default=0, ge=0, description="Number of patients enrolled at this site"
    )
    samples_collected: int = Field(
        default=0, ge=0, description="Number of samples collected at this site"
    )
    irb_approval_date: datetime | None = Field(
        None, description="Date of IRB approval for the sub-study at this site"
    )
    irb_expiry_date: datetime | None = Field(
        None, description="IRB approval expiry date"
    )


class DataSharingAgreement(BaseModel):
    """A data sharing agreement for an ancillary study."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique agreement identifier")
    ancillary_study_id: str = Field(..., description="Associated ancillary study ID")
    partner_organization: str = Field(
        ..., description="Partner organization name"
    )
    agreement_type: AgreementType = Field(
        ..., description="Type of data sharing agreement"
    )
    effective_date: datetime = Field(..., description="Agreement effective date")
    expiry_date: datetime = Field(..., description="Agreement expiry date")
    data_types_shared: list[str] = Field(
        default_factory=list,
        description="Types of data shared under the agreement",
    )
    restrictions: str | None = Field(
        None, description="Restrictions on data usage"
    )
    status: AgreementStatus = Field(
        default=AgreementStatus.DRAFT, description="Agreement status"
    )


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class AncillaryStudyCreate(BaseModel):
    """Request to create a new ancillary study."""

    model_config = ConfigDict(from_attributes=True)

    parent_trial_id: str = Field(..., description="Parent clinical trial ID")
    study_name: str = Field(..., description="Study name")
    study_type: AncillaryStudyType = Field(..., description="Study type")
    relationship: StudyRelationship = Field(
        ..., description="Relationship to parent trial"
    )
    protocol_number: str = Field(..., description="Protocol number")
    pi_name: str = Field(..., description="Principal Investigator name")
    pi_institution: str = Field(..., description="PI institution")
    start_date: datetime | None = Field(None, description="Start date")
    end_date: datetime | None = Field(None, description="End date")
    target_enrollment: int = Field(ge=0, description="Target enrollment")
    budget: float = Field(ge=0.0, description="Budget in USD")
    funding_source: str = Field(..., description="Funding source")
    description: str = Field(..., description="Study description")


class AncillaryStudyUpdate(BaseModel):
    """Request to update an ancillary study."""

    model_config = ConfigDict(from_attributes=True)

    study_name: str | None = Field(None, description="Study name")
    status: AncillaryStatus | None = Field(None, description="Status")
    pi_name: str | None = Field(None, description="PI name")
    pi_institution: str | None = Field(None, description="PI institution")
    start_date: datetime | None = Field(None, description="Start date")
    end_date: datetime | None = Field(None, description="End date")
    target_enrollment: int | None = Field(None, ge=0, description="Target enrollment")
    current_enrollment: int | None = Field(None, ge=0, description="Current enrollment")
    budget: float | None = Field(None, ge=0.0, description="Budget")
    description: str | None = Field(None, description="Description")


class StudySampleCreate(BaseModel):
    """Request to collect (register) a new sample."""

    model_config = ConfigDict(from_attributes=True)

    ancillary_study_id: str = Field(..., description="Ancillary study ID")
    patient_id: str = Field(..., description="Patient ID")
    site_id: str = Field(..., description="Site ID")
    sample_type: SampleType = Field(..., description="Sample type")
    collection_date: datetime = Field(..., description="Collection date")
    visit_number: int = Field(ge=1, description="Visit number")
    processing_instructions: str = Field(
        ..., description="Processing instructions"
    )
    storage_condition: str = Field(..., description="Storage condition")
    aliquot_count: int = Field(ge=1, description="Number of aliquots")


class StudySampleUpdate(BaseModel):
    """Request to update a sample record."""

    model_config = ConfigDict(from_attributes=True)

    shipped_to_lab: bool | None = Field(None, description="Shipped to lab")
    lab_received_date: datetime | None = Field(None, description="Lab received date")
    analysis_status: AnalysisStatus | None = Field(None, description="Analysis status")
    results_available: bool | None = Field(None, description="Results available")


class StudyEndpointCreate(BaseModel):
    """Request to create a study endpoint."""

    model_config = ConfigDict(from_attributes=True)

    ancillary_study_id: str = Field(..., description="Ancillary study ID")
    endpoint_name: str = Field(..., description="Endpoint name")
    endpoint_type: EndpointType = Field(..., description="Endpoint type")
    description: str = Field(..., description="Description")
    measurement_method: str = Field(..., description="Measurement method")
    measurement_timepoints: list[str] = Field(
        default_factory=list, description="Measurement timepoints"
    )
    target_value: str | None = Field(None, description="Target value")
    statistical_method: str = Field(..., description="Statistical method")
    analysis_population: str = Field(..., description="Analysis population")


class StudyEndpointUpdate(BaseModel):
    """Request to update a study endpoint."""

    model_config = ConfigDict(from_attributes=True)

    endpoint_name: str | None = Field(None, description="Endpoint name")
    endpoint_type: EndpointType | None = Field(None, description="Endpoint type")
    description: str | None = Field(None, description="Description")
    measurement_method: str | None = Field(None, description="Measurement method")
    measurement_timepoints: list[str] | None = Field(
        None, description="Measurement timepoints"
    )
    target_value: str | None = Field(None, description="Target value")
    statistical_method: str | None = Field(None, description="Statistical method")
    analysis_population: str | None = Field(None, description="Analysis population")


class SubStudySiteCreate(BaseModel):
    """Request to add a site to an ancillary study."""

    model_config = ConfigDict(from_attributes=True)

    ancillary_study_id: str = Field(..., description="Ancillary study ID")
    site_id: str = Field(..., description="Site ID")
    site_name: str = Field(..., description="Site name")
    irb_approval_date: datetime | None = Field(None, description="IRB approval date")
    irb_expiry_date: datetime | None = Field(None, description="IRB expiry date")


class SubStudySiteUpdate(BaseModel):
    """Request to update a sub-study site."""

    model_config = ConfigDict(from_attributes=True)

    status: SubStudySiteStatus | None = Field(None, description="Status")
    patients_enrolled: int | None = Field(None, ge=0, description="Patients enrolled")
    samples_collected: int | None = Field(None, ge=0, description="Samples collected")
    irb_approval_date: datetime | None = Field(None, description="IRB approval date")
    irb_expiry_date: datetime | None = Field(None, description="IRB expiry date")


class DataSharingAgreementCreate(BaseModel):
    """Request to create a data sharing agreement."""

    model_config = ConfigDict(from_attributes=True)

    ancillary_study_id: str = Field(..., description="Ancillary study ID")
    partner_organization: str = Field(..., description="Partner organization")
    agreement_type: AgreementType = Field(..., description="Agreement type")
    effective_date: datetime = Field(..., description="Effective date")
    expiry_date: datetime = Field(..., description="Expiry date")
    data_types_shared: list[str] = Field(
        default_factory=list, description="Data types shared"
    )
    restrictions: str | None = Field(None, description="Restrictions")


class DataSharingAgreementUpdate(BaseModel):
    """Request to update a data sharing agreement."""

    model_config = ConfigDict(from_attributes=True)

    partner_organization: str | None = Field(None, description="Partner organization")
    effective_date: datetime | None = Field(None, description="Effective date")
    expiry_date: datetime | None = Field(None, description="Expiry date")
    data_types_shared: list[str] | None = Field(None, description="Data types shared")
    restrictions: str | None = Field(None, description="Restrictions")
    status: AgreementStatus | None = Field(None, description="Status")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class AncillaryStudyListResponse(BaseModel):
    """List of ancillary studies."""

    model_config = ConfigDict(from_attributes=True)

    items: list[AncillaryStudy] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class StudySampleListResponse(BaseModel):
    """List of study samples."""

    model_config = ConfigDict(from_attributes=True)

    items: list[StudySample] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class StudyEndpointListResponse(BaseModel):
    """List of study endpoints."""

    model_config = ConfigDict(from_attributes=True)

    items: list[StudyEndpoint] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class SubStudySiteListResponse(BaseModel):
    """List of sub-study sites."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SubStudySite] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class DataSharingAgreementListResponse(BaseModel):
    """List of data sharing agreements."""

    model_config = ConfigDict(from_attributes=True)

    items: list[DataSharingAgreement] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


# ---------------------------------------------------------------------------
# Metrics / dashboard
# ---------------------------------------------------------------------------


class StudyProgress(BaseModel):
    """Progress summary for an ancillary study."""

    model_config = ConfigDict(from_attributes=True)

    study_id: str = Field(..., description="Ancillary study identifier")
    study_name: str = Field(..., description="Study name")
    status: AncillaryStatus = Field(..., description="Current status")
    enrollment_percentage: float = Field(
        ge=0.0, le=100.0, description="Enrollment progress percentage"
    )
    samples_collected: int = Field(ge=0, description="Total samples collected")
    samples_analyzed: int = Field(ge=0, description="Total samples with completed analysis")
    active_sites: int = Field(ge=0, description="Number of active sites")
    endpoints_defined: int = Field(ge=0, description="Number of endpoints defined")
    agreements_active: int = Field(ge=0, description="Number of active data sharing agreements")


class AncillaryMetrics(BaseModel):
    """Aggregated ancillary study operational metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_studies: int = Field(ge=0, description="Total ancillary studies")
    studies_by_type: dict[str, int] = Field(
        default_factory=dict, description="Study counts by type"
    )
    studies_by_status: dict[str, int] = Field(
        default_factory=dict, description="Study counts by status"
    )
    total_samples: int = Field(ge=0, description="Total samples collected")
    samples_pending_analysis: int = Field(
        ge=0, description="Samples awaiting analysis"
    )
    samples_analyzed: int = Field(ge=0, description="Samples with completed analysis")
    total_endpoints: int = Field(ge=0, description="Total endpoints defined")
    total_sites: int = Field(ge=0, description="Total sub-study sites")
    active_sites: int = Field(ge=0, description="Sites currently active or enrolling")
    total_agreements: int = Field(ge=0, description="Total data sharing agreements")
    active_agreements: int = Field(ge=0, description="Currently active agreements")
    total_budget: float = Field(ge=0.0, description="Total budget across all studies")
    total_enrollment: int = Field(ge=0, description="Total current enrollment across studies")
    avg_enrollment_percentage: float = Field(
        ge=0.0, description="Average enrollment percentage across studies"
    )
