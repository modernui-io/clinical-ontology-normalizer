"""Pydantic schemas for Companion Diagnostics (CDx) Management.

Manages companion diagnostic lifecycle operations: CDx registration and tracking,
biomarker-drug pairing, analytical/clinical validation studies, regulatory pathway
management, assay performance metrics (sensitivity, specificity, PPV, NPV),
concordance analysis, and CDx portfolio metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CdxStatus(str, Enum):
    """Lifecycle status of a companion diagnostic."""

    IN_DEVELOPMENT = "in_development"
    ANALYTICAL_VALIDATION = "analytical_validation"
    CLINICAL_VALIDATION = "clinical_validation"
    REGULATORY_SUBMISSION = "regulatory_submission"
    APPROVED = "approved"
    WITHDRAWN = "withdrawn"


class CdxType(str, Enum):
    """Technology type of a companion diagnostic assay."""

    IVD = "ivd"
    LDT = "ldt"
    NGS_PANEL = "ngs_panel"
    PCR = "pcr"
    IHC = "ihc"
    FISH = "fish"
    LIQUID_BIOPSY = "liquid_biopsy"


class BiomarkerType(str, Enum):
    """Category of the biomarker measured by the CDx."""

    GENOMIC = "genomic"
    PROTEOMIC = "proteomic"
    METABOLOMIC = "metabolomic"
    IMAGING = "imaging"
    COMPOSITE = "composite"


class RegulatoryPathway(str, Enum):
    """Regulatory submission pathway for CDx approval."""

    PMA = "pma"
    DE_NOVO_510K = "de_novo_510k"
    HDE = "hde"
    CE_MARK = "ce_mark"
    PMDA = "pmda"


class ValidationStudyType(str, Enum):
    """Type of CDx validation study."""

    ANALYTICAL_VALIDATION = "analytical_validation"
    CLINICAL_VALIDATION = "clinical_validation"
    BRIDGING_STUDY = "bridging_study"
    CONCORDANCE = "concordance"
    REPRODUCIBILITY = "reproducibility"
    PROFICIENCY_TESTING = "proficiency_testing"


class ValidationStudyStatus(str, Enum):
    """Status of a CDx validation study."""

    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class CompanionDiagnostic(BaseModel):
    """A companion diagnostic assay linked to a therapeutic product."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique CDx identifier")
    cdx_name: str = Field(..., description="Companion diagnostic assay name")
    cdx_type: CdxType = Field(..., description="Technology type of the assay")
    status: CdxStatus = Field(..., description="Current lifecycle status")
    biomarker_name: str = Field(..., description="Name of the measured biomarker")
    biomarker_type: BiomarkerType = Field(..., description="Category of biomarker")
    gene_target: str | None = Field(None, description="Target gene (e.g., KRAS, EGFR, BRAF)")
    variant: str | None = Field(None, description="Specific variant or mutation (e.g., G12C, V600E)")
    assay_manufacturer: str = Field(..., description="Manufacturer of the assay kit or platform")
    assay_platform: str = Field(..., description="Instrument or platform used (e.g., cobas 6800, Dako)")
    sensitivity: float | None = Field(
        None, ge=0.0, le=100.0, description="Analytical sensitivity (%)"
    )
    specificity: float | None = Field(
        None, ge=0.0, le=100.0, description="Analytical specificity (%)"
    )
    ppv: float | None = Field(
        None, ge=0.0, le=100.0, description="Positive predictive value (%)"
    )
    npv: float | None = Field(
        None, ge=0.0, le=100.0, description="Negative predictive value (%)"
    )
    concordance_rate: float | None = Field(
        None, ge=0.0, le=100.0, description="Concordance rate with reference method (%)"
    )
    trial_ids: list[str] = Field(
        default_factory=list, description="Associated clinical trial identifiers"
    )
    drug_name: str = Field(..., description="Linked therapeutic drug name")
    therapeutic_area: str = Field(..., description="Therapeutic area (e.g., oncology, immunology)")
    regulatory_pathway: RegulatoryPathway | None = Field(
        None, description="Regulatory submission pathway"
    )
    submission_date: datetime | None = Field(None, description="Date of regulatory submission")
    approval_date: datetime | None = Field(None, description="Date of regulatory approval")
    labeling_text: str | None = Field(
        None, description="Approved labeling indication text"
    )
    cutoff_value: float | None = Field(None, description="Biomarker cutoff value for positivity")
    cutoff_unit: str | None = Field(None, description="Unit for the cutoff value (e.g., %, TPS, copies/mL)")
    sample_type: str | None = Field(None, description="Required sample type (e.g., FFPE tissue, blood)")
    turnaround_days: int | None = Field(
        None, ge=0, description="Expected turnaround time in days"
    )
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record last update timestamp")


class CdxValidationStudy(BaseModel):
    """A validation study associated with a companion diagnostic."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique validation study identifier")
    cdx_id: str = Field(..., description="Associated CDx identifier")
    study_type: ValidationStudyType = Field(..., description="Type of validation study")
    study_name: str = Field(..., description="Name of the validation study")
    sample_size: int = Field(..., ge=1, description="Number of samples in the study")
    concordance_rate: float | None = Field(
        None, ge=0.0, le=100.0, description="Concordance rate achieved (%)"
    )
    sensitivity: float | None = Field(
        None, ge=0.0, le=100.0, description="Sensitivity achieved (%)"
    )
    specificity: float | None = Field(
        None, ge=0.0, le=100.0, description="Specificity achieved (%)"
    )
    status: ValidationStudyStatus = Field(..., description="Current study status")
    start_date: datetime | None = Field(None, description="Study start date")
    completion_date: datetime | None = Field(None, description="Study completion date")
    findings: str | None = Field(None, description="Summary of study findings")
    created_at: datetime = Field(..., description="Record creation timestamp")


class CdxMetrics(BaseModel):
    """Aggregated companion diagnostics portfolio metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_cdx: int = Field(ge=0, description="Total CDx in portfolio")
    cdx_by_status: dict[str, int] = Field(
        default_factory=dict, description="CDx counts by lifecycle status"
    )
    cdx_by_type: dict[str, int] = Field(
        default_factory=dict, description="CDx counts by technology type"
    )
    cdx_by_biomarker_type: dict[str, int] = Field(
        default_factory=dict, description="CDx counts by biomarker category"
    )
    total_validation_studies: int = Field(
        ge=0, description="Total validation studies across all CDx"
    )
    studies_in_progress: int = Field(
        ge=0, description="Number of validation studies currently in progress"
    )
    studies_completed: int = Field(
        ge=0, description="Number of completed validation studies"
    )
    avg_sensitivity: float | None = Field(
        None, description="Average sensitivity across approved CDx (%)"
    )
    avg_specificity: float | None = Field(
        None, description="Average specificity across approved CDx (%)"
    )
    avg_concordance: float | None = Field(
        None, description="Average concordance rate across CDx with data (%)"
    )
    approved_count: int = Field(ge=0, description="Number of approved CDx")
    pending_submission_count: int = Field(
        ge=0, description="Number of CDx pending regulatory submission"
    )


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class CdxCreate(BaseModel):
    """Request to create a new companion diagnostic."""

    model_config = ConfigDict(from_attributes=True)

    cdx_name: str = Field(..., description="Companion diagnostic assay name")
    cdx_type: CdxType = Field(..., description="Technology type")
    biomarker_name: str = Field(..., description="Biomarker name")
    biomarker_type: BiomarkerType = Field(..., description="Biomarker category")
    gene_target: str | None = Field(None, description="Target gene")
    variant: str | None = Field(None, description="Specific variant or mutation")
    assay_manufacturer: str = Field(..., description="Assay manufacturer")
    assay_platform: str = Field(..., description="Assay platform")
    drug_name: str = Field(..., description="Linked drug name")
    therapeutic_area: str = Field(..., description="Therapeutic area")
    regulatory_pathway: RegulatoryPathway | None = Field(None, description="Regulatory pathway")
    sensitivity: float | None = Field(None, ge=0.0, le=100.0, description="Sensitivity (%)")
    specificity: float | None = Field(None, ge=0.0, le=100.0, description="Specificity (%)")
    ppv: float | None = Field(None, ge=0.0, le=100.0, description="PPV (%)")
    npv: float | None = Field(None, ge=0.0, le=100.0, description="NPV (%)")
    concordance_rate: float | None = Field(None, ge=0.0, le=100.0, description="Concordance rate (%)")
    trial_ids: list[str] = Field(default_factory=list, description="Associated trial IDs")
    labeling_text: str | None = Field(None, description="Labeling text")
    cutoff_value: float | None = Field(None, description="Cutoff value")
    cutoff_unit: str | None = Field(None, description="Cutoff unit")
    sample_type: str | None = Field(None, description="Sample type")
    turnaround_days: int | None = Field(None, ge=0, description="Turnaround days")


class CdxUpdate(BaseModel):
    """Request to update an existing companion diagnostic."""

    model_config = ConfigDict(from_attributes=True)

    cdx_name: str | None = Field(None, description="CDx name")
    cdx_type: CdxType | None = Field(None, description="Technology type")
    status: CdxStatus | None = Field(None, description="Lifecycle status")
    biomarker_name: str | None = Field(None, description="Biomarker name")
    biomarker_type: BiomarkerType | None = Field(None, description="Biomarker category")
    gene_target: str | None = Field(None, description="Target gene")
    variant: str | None = Field(None, description="Variant")
    assay_manufacturer: str | None = Field(None, description="Manufacturer")
    assay_platform: str | None = Field(None, description="Platform")
    sensitivity: float | None = Field(None, ge=0.0, le=100.0, description="Sensitivity")
    specificity: float | None = Field(None, ge=0.0, le=100.0, description="Specificity")
    ppv: float | None = Field(None, ge=0.0, le=100.0, description="PPV")
    npv: float | None = Field(None, ge=0.0, le=100.0, description="NPV")
    concordance_rate: float | None = Field(None, ge=0.0, le=100.0, description="Concordance rate")
    trial_ids: list[str] | None = Field(None, description="Trial IDs")
    drug_name: str | None = Field(None, description="Drug name")
    therapeutic_area: str | None = Field(None, description="Therapeutic area")
    regulatory_pathway: RegulatoryPathway | None = Field(None, description="Regulatory pathway")
    submission_date: datetime | None = Field(None, description="Submission date")
    approval_date: datetime | None = Field(None, description="Approval date")
    labeling_text: str | None = Field(None, description="Labeling text")
    cutoff_value: float | None = Field(None, description="Cutoff value")
    cutoff_unit: str | None = Field(None, description="Cutoff unit")
    sample_type: str | None = Field(None, description="Sample type")
    turnaround_days: int | None = Field(None, ge=0, description="Turnaround days")


class CdxValidationStudyCreate(BaseModel):
    """Request to create a validation study for a CDx."""

    model_config = ConfigDict(from_attributes=True)

    study_type: ValidationStudyType = Field(..., description="Study type")
    study_name: str = Field(..., description="Study name")
    sample_size: int = Field(..., ge=1, description="Sample size")
    concordance_rate: float | None = Field(None, ge=0.0, le=100.0, description="Concordance rate")
    sensitivity: float | None = Field(None, ge=0.0, le=100.0, description="Sensitivity")
    specificity: float | None = Field(None, ge=0.0, le=100.0, description="Specificity")
    start_date: datetime | None = Field(None, description="Start date")
    completion_date: datetime | None = Field(None, description="Completion date")
    findings: str | None = Field(None, description="Findings summary")


class CdxValidationStudyUpdate(BaseModel):
    """Request to update a validation study."""

    model_config = ConfigDict(from_attributes=True)

    study_name: str | None = Field(None, description="Study name")
    sample_size: int | None = Field(None, ge=1, description="Sample size")
    concordance_rate: float | None = Field(None, ge=0.0, le=100.0, description="Concordance rate")
    sensitivity: float | None = Field(None, ge=0.0, le=100.0, description="Sensitivity")
    specificity: float | None = Field(None, ge=0.0, le=100.0, description="Specificity")
    status: ValidationStudyStatus | None = Field(None, description="Study status")
    start_date: datetime | None = Field(None, description="Start date")
    completion_date: datetime | None = Field(None, description="Completion date")
    findings: str | None = Field(None, description="Findings summary")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class CdxListResponse(BaseModel):
    """List of companion diagnostics."""

    model_config = ConfigDict(from_attributes=True)

    items: list[CompanionDiagnostic] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class CdxValidationStudyListResponse(BaseModel):
    """List of CDx validation studies."""

    model_config = ConfigDict(from_attributes=True)

    items: list[CdxValidationStudy] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")
