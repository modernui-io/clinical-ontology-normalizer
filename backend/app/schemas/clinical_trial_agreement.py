"""Pydantic schemas for Clinical Trial Agreement Management (CTA-MGT).

Manages legal agreement operations: clinical trial agreements, confidentiality
agreements, budget negotiations, site contract execution, amendment tracking,
and agreement operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class AgreementType(str, Enum):
    CTA = "clinical_trial_agreement"
    CDA = "confidentiality_agreement"
    BUDGET = "budget_agreement"
    AMENDMENT = "amendment"
    MASTER_CTA = "master_cta"
    SITE_SPECIFIC = "site_specific"
    INVESTIGATOR = "investigator_agreement"


class AgreementStatus(str, Enum):
    DRAFT = "draft"
    INTERNAL_REVIEW = "internal_review"
    SITE_REVIEW = "site_review"
    NEGOTIATION = "negotiation"
    LEGAL_REVIEW = "legal_review"
    FINAL = "final"
    EXECUTED = "executed"
    EXPIRED = "expired"
    TERMINATED = "terminated"


class NegotiationIssue(str, Enum):
    INDEMNIFICATION = "indemnification"
    PUBLICATION_RIGHTS = "publication_rights"
    IP_OWNERSHIP = "ip_ownership"
    BUDGET_PER_PATIENT = "budget_per_patient"
    OVERHEAD_RATE = "overhead_rate"
    INSURANCE = "insurance"
    REGULATORY_COMPLIANCE = "regulatory_compliance"
    DATA_OWNERSHIP = "data_ownership"
    TERMINATION_CLAUSE = "termination_clause"


class PaymentTerms(str, Enum):
    NET_30 = "net_30"
    NET_45 = "net_45"
    NET_60 = "net_60"
    MILESTONE = "milestone_based"
    QUARTERLY = "quarterly"


class Agreement(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    agreement_type: AgreementType
    status: AgreementStatus = AgreementStatus.DRAFT
    title: str
    version: str = "1.0"
    effective_date: datetime | None = None
    expiry_date: datetime | None = None
    total_budget: float | None = None
    currency: str = "USD"
    payment_terms: PaymentTerms | None = None
    per_patient_cost: float | None = None
    overhead_rate_pct: float | None = None
    sponsor_signatory: str | None = None
    site_signatory: str | None = None
    executed_date: datetime | None = None
    contract_manager: str
    legal_reviewer: str | None = None
    negotiation_rounds: int = Field(ge=0, default=0)
    created_at: datetime


class NegotiationRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    agreement_id: str
    round_number: int = Field(ge=1)
    issue: NegotiationIssue
    sponsor_position: str
    site_position: str
    resolution: str | None = None
    resolved: bool = False
    escalated: bool = False
    negotiated_by: str
    negotiation_date: datetime
    notes: str | None = None
    created_at: datetime


class BudgetLineItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    agreement_id: str
    category: str
    description: str
    unit_cost: float
    quantity: int = Field(ge=0, default=1)
    total_cost: float
    currency: str = "USD"
    fair_market_value: float | None = None
    justification: str | None = None
    approved: bool = False
    approved_by: str | None = None
    created_at: datetime


class AgreementAmendment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    agreement_id: str
    amendment_number: int = Field(ge=1)
    title: str
    description: str
    change_type: str
    budget_impact: float | None = None
    status: AgreementStatus = AgreementStatus.DRAFT
    effective_date: datetime | None = None
    initiated_by: str
    approved_by: str | None = None
    created_at: datetime


class ContractMilestone(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    agreement_id: str
    milestone_name: str
    description: str
    payment_amount: float
    currency: str = "USD"
    due_date: datetime
    completed_date: datetime | None = None
    status: str = "pending"
    evidence_required: str | None = None
    verified_by: str | None = None
    created_at: datetime


class AgreementCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    agreement_type: AgreementType
    title: str
    contract_manager: str
    total_budget: float | None = None
    currency: str = "USD"
    payment_terms: PaymentTerms | None = None


class AgreementUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: AgreementStatus | None = None
    per_patient_cost: float | None = None
    overhead_rate_pct: float | None = None
    legal_reviewer: str | None = None
    sponsor_signatory: str | None = None
    site_signatory: str | None = None


class NegotiationRecordCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    agreement_id: str
    round_number: int = Field(ge=1)
    issue: NegotiationIssue
    sponsor_position: str
    site_position: str
    negotiated_by: str


class NegotiationRecordUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    resolution: str | None = None
    resolved: bool | None = None
    escalated: bool | None = None
    notes: str | None = None


class BudgetLineItemCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    agreement_id: str
    category: str
    description: str
    unit_cost: float
    quantity: int = Field(ge=0, default=1)
    total_cost: float
    currency: str = "USD"
    fair_market_value: float | None = None


class BudgetLineItemUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    approved: bool | None = None
    approved_by: str | None = None
    justification: str | None = None


class AgreementAmendmentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    agreement_id: str
    amendment_number: int = Field(ge=1)
    title: str
    description: str
    change_type: str
    initiated_by: str
    budget_impact: float | None = None


class AgreementAmendmentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: AgreementStatus | None = None
    approved_by: str | None = None
    budget_impact: float | None = None


class ContractMilestoneCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    agreement_id: str
    milestone_name: str
    description: str
    payment_amount: float
    due_date: datetime
    currency: str = "USD"
    evidence_required: str | None = None


class ContractMilestoneUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: str | None = None
    verified_by: str | None = None


class AgreementListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[Agreement] = Field(default_factory=list)
    total: int = Field(ge=0)


class NegotiationRecordListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[NegotiationRecord] = Field(default_factory=list)
    total: int = Field(ge=0)


class BudgetLineItemListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[BudgetLineItem] = Field(default_factory=list)
    total: int = Field(ge=0)


class AgreementAmendmentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[AgreementAmendment] = Field(default_factory=list)
    total: int = Field(ge=0)


class ContractMilestoneListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ContractMilestone] = Field(default_factory=list)
    total: int = Field(ge=0)


class ClinicalTrialAgreementMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_agreements: int = Field(ge=0)
    agreements_by_type: dict[str, int] = Field(default_factory=dict)
    agreements_by_status: dict[str, int] = Field(default_factory=dict)
    executed_agreements: int = Field(ge=0)
    avg_negotiation_rounds: float = Field(ge=0)
    total_budget_committed: float = Field(ge=0)
    total_negotiations: int = Field(ge=0)
    open_negotiations: int = Field(ge=0)
    total_line_items: int = Field(ge=0)
    approved_line_items: int = Field(ge=0)
    total_amendments: int = Field(ge=0)
    total_milestones: int = Field(ge=0)
    completed_milestones: int = Field(ge=0)
