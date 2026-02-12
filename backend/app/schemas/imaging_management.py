"""Pydantic schemas for Clinical Imaging Management (IMG-MGMT).

Manages medical imaging operations: imaging study definitions, image acquisition
tracking, central reader assignments, RECIST/disease assessments, reader
training/qualification, image quality reviews, and imaging metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ImagingModality(str, Enum):
    CT = "ct"
    MRI = "mri"
    PET_CT = "pet_ct"
    XRAY = "xray"
    ULTRASOUND = "ultrasound"
    OCT = "oct"
    FUNDUS_PHOTO = "fundus_photography"
    DEXA = "dexa"
    MAMMOGRAPHY = "mammography"


class AssessmentCriteria(str, Enum):
    RECIST_1_1 = "recist_1_1"
    IRECIST = "irecist"
    RANO = "rano"
    CHOI = "choi"
    LUGANO = "lugano"
    EASI = "easi"
    ETDRS = "etdrs"
    CUSTOM = "custom"


class ReadingDesign(str, Enum):
    SINGLE_READER = "single_reader"
    DUAL_READER = "dual_reader"
    CONSENSUS = "consensus"
    ADJUDICATION = "adjudication"


class ImageStatus(str, Enum):
    PENDING_UPLOAD = "pending_upload"
    UPLOADED = "uploaded"
    QC_PASSED = "qc_passed"
    QC_FAILED = "qc_failed"
    ASSIGNED = "assigned"
    READ_COMPLETE = "read_complete"
    QUERY_RAISED = "query_raised"


class OverallResponse(str, Enum):
    COMPLETE_RESPONSE = "complete_response"
    PARTIAL_RESPONSE = "partial_response"
    STABLE_DISEASE = "stable_disease"
    PROGRESSIVE_DISEASE = "progressive_disease"
    NOT_EVALUABLE = "not_evaluable"


class QualificationStatus(str, Enum):
    IN_TRAINING = "in_training"
    QUALIFIED = "qualified"
    PROVISIONALLY_QUALIFIED = "provisionally_qualified"
    DISQUALIFIED = "disqualified"
    REQUALIFICATION_DUE = "requalification_due"


class QCOutcome(str, Enum):
    PASS = "pass"
    MINOR_DEVIATION = "minor_deviation"
    MAJOR_DEVIATION = "major_deviation"
    FAIL = "fail"
    RESCAN_REQUIRED = "rescan_required"


class ImagingStudy(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    title: str
    modalities: list[ImagingModality] = Field(default_factory=list)
    assessment_criteria: AssessmentCriteria
    reading_design: ReadingDesign
    blinded: bool = True
    assessment_schedule: list[str] = Field(default_factory=list)
    total_subjects: int = Field(ge=0, default=0)
    charter_version: str
    vendor: str
    status: str = "active"
    created_at: datetime


class ImageAcquisition(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    study_id: str
    subject_id: str
    visit: str
    modality: ImagingModality
    acquisition_date: datetime
    site_id: str
    status: ImageStatus = ImageStatus.PENDING_UPLOAD
    upload_date: datetime | None = None
    file_count: int = Field(ge=0, default=0)
    total_size_mb: float = Field(ge=0, default=0)
    series_description: str | None = None
    slice_thickness_mm: float | None = None
    contrast_used: bool = False
    technologist: str | None = None


class CentralReader(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    specialty: str
    institution: str
    qualification_status: QualificationStatus = QualificationStatus.IN_TRAINING
    qualified_modalities: list[ImagingModality] = Field(default_factory=list)
    qualified_criteria: list[AssessmentCriteria] = Field(default_factory=list)
    training_completed_date: datetime | None = None
    cases_read: int = Field(ge=0, default=0)
    agreement_rate: float | None = None
    active: bool = True


class DiseaseAssessment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    acquisition_id: str
    reader_id: str
    assessment_criteria: AssessmentCriteria
    timepoint: str
    target_lesion_count: int = Field(ge=0, default=0)
    target_lesion_sum_mm: float | None = None
    non_target_status: str | None = None
    new_lesions: bool = False
    overall_response: OverallResponse | None = None
    best_overall_response: OverallResponse | None = None
    percent_change_from_baseline: float | None = None
    percent_change_from_nadir: float | None = None
    assessment_date: datetime
    comments: str | None = None


class ImageQualityReview(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    acquisition_id: str
    reviewer: str
    review_date: datetime
    outcome: QCOutcome
    issues: list[str] = Field(default_factory=list)
    protocol_compliant: bool = True
    resolution_adequate: bool = True
    coverage_adequate: bool = True
    action_required: str | None = None


class ImagingStudyCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    title: str
    modalities: list[ImagingModality] = Field(default_factory=list)
    assessment_criteria: AssessmentCriteria
    reading_design: ReadingDesign
    blinded: bool = True
    assessment_schedule: list[str] = Field(default_factory=list)
    charter_version: str
    vendor: str


class ImagingStudyUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    title: str | None = None
    total_subjects: int | None = None
    status: str | None = None
    charter_version: str | None = None


class ImageAcquisitionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    study_id: str
    subject_id: str
    visit: str
    modality: ImagingModality
    site_id: str
    series_description: str | None = None
    slice_thickness_mm: float | None = None
    contrast_used: bool = False
    technologist: str | None = None


class ImageAcquisitionUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: ImageStatus | None = None
    file_count: int | None = None
    total_size_mb: float | None = None


class CentralReaderCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    specialty: str
    institution: str
    qualified_modalities: list[ImagingModality] = Field(default_factory=list)
    qualified_criteria: list[AssessmentCriteria] = Field(default_factory=list)


class CentralReaderUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    qualification_status: QualificationStatus | None = None
    qualified_modalities: list[ImagingModality] | None = None
    qualified_criteria: list[AssessmentCriteria] | None = None
    cases_read: int | None = None
    agreement_rate: float | None = None
    active: bool | None = None


class DiseaseAssessmentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    acquisition_id: str
    reader_id: str
    assessment_criteria: AssessmentCriteria
    timepoint: str
    target_lesion_count: int = Field(ge=0, default=0)
    target_lesion_sum_mm: float | None = None
    non_target_status: str | None = None
    new_lesions: bool = False
    overall_response: OverallResponse | None = None
    percent_change_from_baseline: float | None = None
    percent_change_from_nadir: float | None = None
    comments: str | None = None


class ImageQualityReviewCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    acquisition_id: str
    reviewer: str
    outcome: QCOutcome
    issues: list[str] = Field(default_factory=list)
    protocol_compliant: bool = True
    resolution_adequate: bool = True
    coverage_adequate: bool = True
    action_required: str | None = None


class ImagingStudyListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ImagingStudy] = Field(default_factory=list)
    total: int = Field(ge=0)


class ImageAcquisitionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ImageAcquisition] = Field(default_factory=list)
    total: int = Field(ge=0)


class CentralReaderListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CentralReader] = Field(default_factory=list)
    total: int = Field(ge=0)


class DiseaseAssessmentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DiseaseAssessment] = Field(default_factory=list)
    total: int = Field(ge=0)


class ImageQualityReviewListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ImageQualityReview] = Field(default_factory=list)
    total: int = Field(ge=0)


class ImagingManagementMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_studies: int = Field(ge=0)
    total_acquisitions: int = Field(ge=0)
    acquisitions_by_status: dict[str, int] = Field(default_factory=dict)
    acquisitions_by_modality: dict[str, int] = Field(default_factory=dict)
    total_readers: int = Field(ge=0)
    qualified_readers: int = Field(ge=0)
    readers_by_status: dict[str, int] = Field(default_factory=dict)
    total_assessments: int = Field(ge=0)
    assessments_by_response: dict[str, int] = Field(default_factory=dict)
    total_qc_reviews: int = Field(ge=0)
    qc_by_outcome: dict[str, int] = Field(default_factory=dict)
    qc_pass_rate: float = Field(ge=0, le=100)
    avg_reader_agreement_rate: float = Field(ge=0, le=100)
