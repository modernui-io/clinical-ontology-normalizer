"""Pydantic schemas for Vendor Qualification & Oversight (QA-VENDOR).

Manages CRO, central lab, and service provider qualification, performance
monitoring, quality agreements, risk assessments, audit findings, and
vendor scorecards for clinical trial operations.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class VendorCategory(str, Enum):
    CRO = "cro"
    CENTRAL_LAB = "central_lab"
    IRT_PROVIDER = "irt_provider"
    EDC_PROVIDER = "edc_provider"
    PACKAGING = "packaging"
    LOGISTICS = "logistics"
    IMAGING = "imaging"
    BIOANALYTICAL_LAB = "bioanalytical_lab"
    SAFETY_DATABASE = "safety_database"
    MEDICAL_WRITING = "medical_writing"


class QualificationStatus(str, Enum):
    PENDING = "pending"
    QUALIFIED = "qualified"
    CONDITIONALLY_QUALIFIED = "conditionally_qualified"
    DISQUALIFIED = "disqualified"
    REQUALIFICATION_DUE = "requalification_due"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AgreementStatus(str, Enum):
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    EXECUTED = "executed"
    EXPIRED = "expired"
    TERMINATED = "terminated"


class PerformanceRating(str, Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    BELOW_EXPECTATIONS = "below_expectations"
    UNACCEPTABLE = "unacceptable"


class Vendor(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    category: VendorCategory
    qualification_status: QualificationStatus = QualificationStatus.PENDING
    risk_level: RiskLevel = RiskLevel.MEDIUM
    contact_name: str
    contact_email: str
    country: str
    services_provided: list[str] = Field(default_factory=list)
    qualification_date: datetime | None = None
    requalification_due_date: datetime | None = None
    active_trials: list[str] = Field(default_factory=list)
    overall_rating: PerformanceRating | None = None
    created_at: datetime


class QualityAgreement(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    vendor_id: str
    trial_id: str
    agreement_number: str
    title: str
    status: AgreementStatus = AgreementStatus.DRAFT
    effective_date: datetime | None = None
    expiry_date: datetime | None = None
    signed_by_sponsor: str | None = None
    signed_by_vendor: str | None = None
    key_terms: list[str] = Field(default_factory=list)
    created_at: datetime


class VendorAssessment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    vendor_id: str
    trial_id: str | None = None
    assessment_date: datetime
    assessor: str
    quality_score: float = Field(ge=0, le=100)
    timeliness_score: float = Field(ge=0, le=100)
    communication_score: float = Field(ge=0, le=100)
    compliance_score: float = Field(ge=0, le=100)
    overall_score: float = Field(ge=0, le=100)
    rating: PerformanceRating
    strengths: list[str] = Field(default_factory=list)
    improvements_needed: list[str] = Field(default_factory=list)
    notes: str | None = None


class VendorRiskAssessment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    vendor_id: str
    assessed_date: datetime
    assessed_by: str
    risk_level: RiskLevel
    risk_factors: list[str] = Field(default_factory=list)
    mitigation_plan: str | None = None
    next_review_date: datetime | None = None


class VendorCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    category: VendorCategory
    contact_name: str
    contact_email: str
    country: str
    services_provided: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.MEDIUM


class VendorUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str | None = None
    qualification_status: QualificationStatus | None = None
    risk_level: RiskLevel | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    services_provided: list[str] | None = None
    overall_rating: PerformanceRating | None = None
    active_trials: list[str] | None = None


class QualityAgreementCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    vendor_id: str
    trial_id: str
    agreement_number: str
    title: str
    effective_date: datetime | None = None
    expiry_date: datetime | None = None
    key_terms: list[str] = Field(default_factory=list)


class QualityAgreementUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: AgreementStatus | None = None
    signed_by_sponsor: str | None = None
    signed_by_vendor: str | None = None
    effective_date: datetime | None = None
    expiry_date: datetime | None = None
    key_terms: list[str] | None = None


class VendorAssessmentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    vendor_id: str
    trial_id: str | None = None
    assessor: str
    quality_score: float = Field(ge=0, le=100)
    timeliness_score: float = Field(ge=0, le=100)
    communication_score: float = Field(ge=0, le=100)
    compliance_score: float = Field(ge=0, le=100)
    rating: PerformanceRating
    strengths: list[str] = Field(default_factory=list)
    improvements_needed: list[str] = Field(default_factory=list)
    notes: str | None = None


class VendorRiskAssessmentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    vendor_id: str
    assessed_by: str
    risk_level: RiskLevel
    risk_factors: list[str] = Field(default_factory=list)
    mitigation_plan: str | None = None
    next_review_date: datetime | None = None


class VendorListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[Vendor] = Field(default_factory=list)
    total: int = Field(ge=0)


class QualityAgreementListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[QualityAgreement] = Field(default_factory=list)
    total: int = Field(ge=0)


class VendorAssessmentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[VendorAssessment] = Field(default_factory=list)
    total: int = Field(ge=0)


class VendorRiskAssessmentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[VendorRiskAssessment] = Field(default_factory=list)
    total: int = Field(ge=0)


class VendorQualificationMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_vendors: int = Field(ge=0)
    vendors_by_category: dict[str, int] = Field(default_factory=dict)
    vendors_by_status: dict[str, int] = Field(default_factory=dict)
    vendors_by_risk: dict[str, int] = Field(default_factory=dict)
    total_agreements: int = Field(ge=0)
    agreements_by_status: dict[str, int] = Field(default_factory=dict)
    total_assessments: int = Field(ge=0)
    avg_quality_score: float = Field(ge=0)
    avg_overall_score: float = Field(ge=0)
    total_risk_assessments: int = Field(ge=0)
    high_risk_vendors: int = Field(ge=0)
    requalification_due: int = Field(ge=0)
