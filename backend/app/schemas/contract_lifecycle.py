"""Pydantic schemas for Contract Lifecycle Management (CLO-6).

Defines contract records, milestones, obligations, amendments, IP records,
and compliance reporting models for pharma-grade contract lifecycle management
in the clinical trial patient recruitment platform.

CLO-6: Contract Lifecycle Management
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ContractType(str, Enum):
    """Type of contract or agreement."""

    MASTER_SERVICE = "MASTER_SERVICE"
    DATA_USE = "DATA_USE"
    BAA = "BAA"
    CLINICAL_TRIAL = "CLINICAL_TRIAL"
    LICENSING = "LICENSING"
    NDA = "NDA"
    AMENDMENT = "AMENDMENT"
    STATEMENT_OF_WORK = "STATEMENT_OF_WORK"


class ContractStatus(str, Enum):
    """Lifecycle status of a contract."""

    DRAFT = "DRAFT"
    REVIEW = "REVIEW"
    NEGOTIATION = "NEGOTIATION"
    PENDING_SIGNATURE = "PENDING_SIGNATURE"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    TERMINATED = "TERMINATED"
    RENEWED = "RENEWED"
    SUSPENDED = "SUSPENDED"


class MilestoneStatus(str, Enum):
    """Status of a contract milestone."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    OVERDUE = "OVERDUE"
    WAIVED = "WAIVED"


class ObligationType(str, Enum):
    """Type of contractual obligation."""

    FINANCIAL = "FINANCIAL"
    REPORTING = "REPORTING"
    DATA_DELIVERY = "DATA_DELIVERY"
    REGULATORY = "REGULATORY"
    OPERATIONAL = "OPERATIONAL"
    CONFIDENTIALITY = "CONFIDENTIALITY"


class IPType(str, Enum):
    """Type of intellectual property."""

    PATENT = "PATENT"
    TRADEMARK = "TRADEMARK"
    COPYRIGHT = "COPYRIGHT"
    TRADE_SECRET = "TRADE_SECRET"
    INVENTION_DISCLOSURE = "INVENTION_DISCLOSURE"


class RiskLevel(str, Enum):
    """Risk level classification for contracts."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# ---------------------------------------------------------------------------
# Core Models
# ---------------------------------------------------------------------------


class ContractParty(BaseModel):
    """A party to a contract."""

    name: str = Field(..., description="Full legal name of the party")
    role: str = Field(..., description="Role in the contract (e.g. Sponsor, CRO, Site)")
    contact_email: str = Field(..., description="Primary contact email")
    organization: str = Field(..., description="Organization name")


class ContractMilestone(BaseModel):
    """A milestone within a contract."""

    id: str = Field(..., description="Unique milestone identifier")
    contract_id: str = Field(..., description="Parent contract identifier")
    title: str = Field(..., description="Milestone title")
    description: str = Field(default="", description="Detailed description")
    due_date: datetime = Field(..., description="Due date for the milestone")
    status: MilestoneStatus = Field(
        default=MilestoneStatus.PENDING, description="Current status"
    )
    responsible_party: str = Field(default="", description="Party responsible for delivery")
    deliverable: str = Field(default="", description="Expected deliverable")
    completion_date: Optional[datetime] = Field(
        default=None, description="Actual completion date"
    )


class ContractObligation(BaseModel):
    """A contractual obligation that must be fulfilled."""

    id: str = Field(..., description="Unique obligation identifier")
    contract_id: str = Field(..., description="Parent contract identifier")
    obligation_type: ObligationType = Field(..., description="Type of obligation")
    description: str = Field(..., description="Obligation description")
    owner: str = Field(..., description="Party responsible for fulfillment")
    due_date: datetime = Field(..., description="Due date for the obligation")
    recurring: bool = Field(default=False, description="Whether the obligation recurs")
    frequency_days: Optional[int] = Field(
        default=None, description="Recurrence frequency in days"
    )
    status: MilestoneStatus = Field(
        default=MilestoneStatus.PENDING, description="Current status"
    )
    last_completed: Optional[datetime] = Field(
        default=None, description="Last completion date for recurring obligations"
    )


class ContractAmendment(BaseModel):
    """An amendment to an existing contract."""

    id: str = Field(..., description="Unique amendment identifier")
    contract_id: str = Field(..., description="Parent contract identifier")
    title: str = Field(..., description="Amendment title")
    description: str = Field(default="", description="Amendment description")
    changes_summary: str = Field(
        default="", description="Summary of changes introduced"
    )
    effective_date: datetime = Field(..., description="Date amendment takes effect")
    approved_by: str = Field(default="", description="Person/entity who approved")
    created_at: datetime = Field(..., description="Creation timestamp")


class IPRecord(BaseModel):
    """An intellectual property record related to contracts."""

    id: str = Field(..., description="Unique IP record identifier")
    title: str = Field(..., description="IP title")
    ip_type: IPType = Field(..., description="Type of intellectual property")
    description: str = Field(default="", description="IP description")
    filing_date: Optional[datetime] = Field(
        default=None, description="Date of filing/registration"
    )
    status: str = Field(default="ACTIVE", description="IP record status")
    registration_number: Optional[str] = Field(
        default=None, description="Official registration number"
    )
    jurisdiction: str = Field(default="US", description="Jurisdiction of IP protection")
    owner: str = Field(..., description="IP owner")
    expiry_date: Optional[datetime] = Field(
        default=None, description="IP expiry date"
    )
    related_contracts: list[str] = Field(
        default_factory=list, description="IDs of related contracts"
    )


class Contract(BaseModel):
    """A contract or agreement in the lifecycle management system."""

    id: str = Field(..., description="Unique contract identifier")
    title: str = Field(..., description="Contract title")
    contract_type: ContractType = Field(..., description="Type of contract")
    status: ContractStatus = Field(
        default=ContractStatus.DRAFT, description="Current status"
    )
    description: str = Field(default="", description="Contract description")
    parties: list[ContractParty] = Field(
        default_factory=list, description="Parties to the contract"
    )
    effective_date: Optional[datetime] = Field(
        default=None, description="Date the contract becomes effective"
    )
    expiry_date: Optional[datetime] = Field(
        default=None, description="Contract expiry date"
    )
    auto_renew: bool = Field(
        default=False, description="Whether the contract auto-renews"
    )
    renewal_notice_days: int = Field(
        default=90, description="Days before expiry to send renewal notice"
    )
    total_value: Optional[float] = Field(
        default=None, description="Total contract value"
    )
    currency: str = Field(default="USD", description="Currency for contract value")
    milestones: list[ContractMilestone] = Field(
        default_factory=list, description="Contract milestones"
    )
    obligations: list[ContractObligation] = Field(
        default_factory=list, description="Contract obligations"
    )
    amendments: list[ContractAmendment] = Field(
        default_factory=list, description="Contract amendments"
    )
    ip_records: list[str] = Field(
        default_factory=list, description="Related IP record IDs"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    signed_date: Optional[datetime] = Field(
        default=None, description="Date the contract was signed"
    )
    terminated_date: Optional[datetime] = Field(
        default=None, description="Date of termination"
    )
    termination_reason: Optional[str] = Field(
        default=None, description="Reason for termination"
    )
    risk_level: RiskLevel = Field(
        default=RiskLevel.MEDIUM, description="Risk classification"
    )
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")


# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------


class ContractCreateRequest(BaseModel):
    """Request to create a new contract."""

    title: str = Field(..., description="Contract title")
    contract_type: ContractType = Field(..., description="Type of contract")
    description: str = Field(default="", description="Contract description")
    parties: list[ContractParty] = Field(
        default_factory=list, description="Contract parties"
    )
    effective_date: Optional[datetime] = Field(default=None)
    expiry_date: Optional[datetime] = Field(default=None)
    auto_renew: bool = Field(default=False)
    renewal_notice_days: int = Field(default=90)
    total_value: Optional[float] = Field(default=None)
    currency: str = Field(default="USD")
    risk_level: RiskLevel = Field(default=RiskLevel.MEDIUM)
    tags: list[str] = Field(default_factory=list)


class ContractUpdateRequest(BaseModel):
    """Request to update an existing contract."""

    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ContractStatus] = None
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    auto_renew: Optional[bool] = None
    renewal_notice_days: Optional[int] = None
    total_value: Optional[float] = None
    currency: Optional[str] = None
    risk_level: Optional[RiskLevel] = None
    tags: Optional[list[str]] = None
    termination_reason: Optional[str] = None


class MilestoneCreateRequest(BaseModel):
    """Request to create a new milestone."""

    title: str = Field(..., description="Milestone title")
    description: str = Field(default="")
    due_date: datetime = Field(..., description="Due date")
    responsible_party: str = Field(default="")
    deliverable: str = Field(default="")


class ObligationCreateRequest(BaseModel):
    """Request to create a new obligation."""

    obligation_type: ObligationType = Field(...)
    description: str = Field(...)
    owner: str = Field(...)
    due_date: datetime = Field(...)
    recurring: bool = Field(default=False)
    frequency_days: Optional[int] = Field(default=None)


class AmendmentCreateRequest(BaseModel):
    """Request to create a new amendment."""

    title: str = Field(...)
    description: str = Field(default="")
    changes_summary: str = Field(default="")
    effective_date: datetime = Field(...)
    approved_by: str = Field(default="")


class IPRecordCreateRequest(BaseModel):
    """Request to create a new IP record."""

    title: str = Field(...)
    ip_type: IPType = Field(...)
    description: str = Field(default="")
    filing_date: Optional[datetime] = Field(default=None)
    status: str = Field(default="ACTIVE")
    registration_number: Optional[str] = Field(default=None)
    jurisdiction: str = Field(default="US")
    owner: str = Field(...)
    expiry_date: Optional[datetime] = Field(default=None)
    related_contracts: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Response Models
# ---------------------------------------------------------------------------


class ContractListResponse(BaseModel):
    """Paginated list of contracts."""

    items: list[Contract] = Field(default_factory=list)
    total: int = Field(default=0)
    limit: int = Field(default=50)
    offset: int = Field(default=0)


class IPRecordListResponse(BaseModel):
    """List of IP records."""

    items: list[IPRecord] = Field(default_factory=list)
    total: int = Field(default=0)


class ContractMetrics(BaseModel):
    """Aggregated metrics for the contract portfolio."""

    total_contracts: int = Field(default=0)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)
    total_value: float = Field(default=0.0)
    expiring_soon: int = Field(
        default=0, description="Contracts expiring within 90 days"
    )
    overdue_milestones: int = Field(default=0)
    overdue_obligations: int = Field(default=0)
    active_ip_records: int = Field(default=0)


class ContractComplianceReport(BaseModel):
    """Compliance report summarizing contract health."""

    contracts_with_overdue_obligations: list[str] = Field(default_factory=list)
    unsigned_past_due: list[str] = Field(
        default_factory=list,
        description="Contracts past effective date without signature",
    )
    approaching_expiry: list[str] = Field(
        default_factory=list,
        description="Contracts expiring within 90 days",
    )
    auto_renewal_pending: list[str] = Field(
        default_factory=list,
        description="Auto-renew contracts approaching expiry within renewal notice window",
    )
    total_issues: int = Field(default=0)
    generated_at: datetime = Field(..., description="Report generation timestamp")
