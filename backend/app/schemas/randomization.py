"""Pydantic schemas for Randomization & Blinding Service (CLINICAL-1).

Manages treatment arm randomization across clinical trials using various
randomization methods (simple, block, stratified, adaptive, minimization),
enforces blinding levels, handles unblinding requests, and provides
balance checking and audit trails.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RandomizationMethod(str, Enum):
    """Algorithm used to randomize patients to treatment arms."""

    SIMPLE = "SIMPLE"
    BLOCK = "BLOCK"
    STRATIFIED = "STRATIFIED"
    ADAPTIVE = "ADAPTIVE"
    MINIMIZATION = "MINIMIZATION"
    DYNAMIC = "DYNAMIC"
    RESPONSE_ADAPTIVE = "RESPONSE_ADAPTIVE"


class AllocationRatio(str, Enum):
    """Pre-defined allocation ratios between treatment arms."""

    EQUAL_1_1 = "EQUAL_1_1"
    RATIO_2_1 = "RATIO_2_1"
    RATIO_3_1 = "RATIO_3_1"
    RATIO_3_2 = "RATIO_3_2"
    CUSTOM = "CUSTOM"


class BlindingLevel(str, Enum):
    """Level of blinding applied to the study."""

    OPEN_LABEL = "OPEN_LABEL"
    SINGLE_BLIND = "SINGLE_BLIND"
    DOUBLE_BLIND = "DOUBLE_BLIND"
    TRIPLE_BLIND = "TRIPLE_BLIND"


class ArmType(str, Enum):
    """Type of treatment arm in the study."""

    TREATMENT = "TREATMENT"
    CONTROL = "CONTROL"
    PLACEBO = "PLACEBO"
    ACTIVE_COMPARATOR = "ACTIVE_COMPARATOR"
    SHAM = "SHAM"


class UnblindingReason(str, Enum):
    """Justification for requesting unblinding of a participant."""

    MEDICAL_EMERGENCY = "MEDICAL_EMERGENCY"
    SAE_ASSESSMENT = "SAE_ASSESSMENT"
    INTERIM_ANALYSIS = "INTERIM_ANALYSIS"
    STUDY_COMPLETION = "STUDY_COMPLETION"
    REGULATORY_REQUEST = "REGULATORY_REQUEST"
    DSMB_RECOMMENDATION = "DSMB_RECOMMENDATION"


class RandomizationStatus(str, Enum):
    """Lifecycle status of a randomization scheme."""

    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    ACTIVE = "ACTIVE"
    LOCKED = "LOCKED"
    COMPLETED = "COMPLETED"


# ---------------------------------------------------------------------------
# Core models
# ---------------------------------------------------------------------------


class TreatmentArm(BaseModel):
    """A treatment arm within a randomization scheme."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique arm identifier")
    name: str = Field(..., description="Human-readable arm name")
    arm_type: ArmType = Field(..., description="Type of arm")
    description: str = Field("", description="Arm description")
    allocation_weight: float = Field(
        1.0, ge=0.0, description="Relative allocation weight"
    )
    current_count: int = Field(0, ge=0, description="Current enrolled count")
    target_count: int = Field(0, ge=0, description="Target enrollment count")


class StratificationFactor(BaseModel):
    """A stratification factor used for balanced randomization."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique factor identifier")
    name: str = Field(..., description="Factor name (e.g. 'Disease Severity')")
    description: str = Field("", description="Factor description")
    levels: list[str] = Field(
        default_factory=list, description="Possible levels/categories"
    )


class RandomizationScheme(BaseModel):
    """Top-level randomization design for a clinical trial."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique scheme identifier")
    trial_id: str = Field(..., description="Associated trial ID")
    trial_name: str = Field(..., description="Associated trial name")
    method: RandomizationMethod = Field(..., description="Randomization algorithm")
    blinding_level: BlindingLevel = Field(..., description="Blinding level")
    allocation_ratio: AllocationRatio = Field(..., description="Allocation ratio")
    status: RandomizationStatus = Field(
        RandomizationStatus.DRAFT, description="Scheme status"
    )
    arms: list[TreatmentArm] = Field(
        default_factory=list, description="Treatment arms"
    )
    stratification_factors: list[StratificationFactor] = Field(
        default_factory=list, description="Stratification factors"
    )
    block_sizes: list[int] = Field(
        default_factory=list,
        description="Block sizes for block randomization (e.g. [4, 6])",
    )
    seed: Optional[int] = Field(None, description="Random seed for reproducibility")
    total_randomized: int = Field(0, ge=0, description="Total patients randomized")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    locked_at: Optional[datetime] = Field(
        None, description="Timestamp when scheme was locked"
    )
    validated_by: Optional[str] = Field(
        None, description="User who validated the scheme"
    )


class RandomizationAssignment(BaseModel):
    """A single patient randomization assignment."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique assignment identifier")
    scheme_id: str = Field(..., description="Parent randomization scheme ID")
    patient_id: str = Field(..., description="Patient identifier")
    arm_id: str = Field(..., description="Assigned treatment arm ID")
    arm_name: str = Field(..., description="Assigned treatment arm name")
    stratum: Optional[str] = Field(
        None, description="Stratum key for stratified randomization"
    )
    sequence_number: int = Field(
        ..., description="Sequential randomization number within scheme"
    )
    randomized_at: datetime = Field(..., description="Randomization timestamp")
    randomized_by: str = Field(..., description="User who performed randomization")
    blinding_code: str = Field(
        ..., description="Blinding code (masks arm identity in blinded studies)"
    )
    is_unblinded: bool = Field(False, description="Whether assignment has been unblinded")
    unblinding_reason: Optional[UnblindingReason] = Field(
        None, description="Reason for unblinding"
    )
    unblinded_at: Optional[datetime] = Field(
        None, description="Timestamp of unblinding"
    )
    unblinded_by: Optional[str] = Field(None, description="User who unblinded")


class BlindedAssignment(BaseModel):
    """A blinded view of a randomization assignment (arm details hidden)."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Assignment identifier")
    scheme_id: str = Field(..., description="Scheme identifier")
    patient_id: str = Field(..., description="Patient identifier")
    blinding_code: str = Field(..., description="Blinding code (no arm info)")
    sequence_number: int = Field(..., description="Sequence number")
    randomized_at: datetime = Field(..., description="Randomization timestamp")
    is_unblinded: bool = Field(False, description="Whether assignment is unblinded")


class UnblindingRequest(BaseModel):
    """A request to unblind a patient's treatment assignment."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique request identifier")
    assignment_id: str = Field(..., description="Assignment to unblind")
    patient_id: str = Field(..., description="Patient identifier")
    requestor: str = Field(..., description="Person requesting unblinding")
    reason: UnblindingReason = Field(..., description="Reason for unblinding")
    urgency: str = Field("standard", description="Urgency level: standard, urgent, emergency")
    approved: Optional[bool] = Field(None, description="Approval decision (None=pending)")
    approved_by: Optional[str] = Field(None, description="Approver identity")
    approved_at: Optional[datetime] = Field(None, description="Approval timestamp")
    created_at: datetime = Field(..., description="Request creation timestamp")


class RandomizationAuditEntry(BaseModel):
    """An immutable audit trail entry for randomization actions."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique audit entry identifier")
    scheme_id: str = Field(..., description="Associated scheme ID")
    action: str = Field(..., description="Action performed (e.g. 'RANDOMIZE', 'UNBLIND')")
    actor: str = Field(..., description="User who performed the action")
    timestamp: datetime = Field(..., description="Action timestamp")
    details: dict[str, Any] = Field(
        default_factory=dict, description="Action-specific details"
    )


# ---------------------------------------------------------------------------
# Balance checking
# ---------------------------------------------------------------------------


class BalanceCheck(BaseModel):
    """Balance assessment for a single stratification factor."""

    model_config = ConfigDict(from_attributes=True)

    factor: str = Field(..., description="Stratification factor name")
    levels: list[str] = Field(default_factory=list, description="Factor levels")
    counts_per_arm: dict[str, dict[str, int]] = Field(
        default_factory=dict,
        description="Counts by arm and level: {arm_id: {level: count}}",
    )
    imbalance_score: float = Field(
        0.0, description="Chi-square-based imbalance score"
    )
    acceptable: bool = Field(True, description="Whether imbalance is acceptable")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class SchemeCreate(BaseModel):
    """Request body to create a new randomization scheme."""

    trial_id: str = Field(..., description="Trial ID")
    trial_name: str = Field(..., description="Trial name")
    method: RandomizationMethod = Field(..., description="Randomization method")
    blinding_level: BlindingLevel = Field(..., description="Blinding level")
    allocation_ratio: AllocationRatio = Field(..., description="Allocation ratio")
    arms: list[TreatmentArm] = Field(..., min_length=2, description="Treatment arms")
    stratification_factors: list[StratificationFactor] = Field(
        default_factory=list, description="Stratification factors"
    )
    block_sizes: list[int] = Field(
        default_factory=list, description="Block sizes"
    )
    seed: Optional[int] = Field(None, description="Random seed")


class SchemeUpdate(BaseModel):
    """Request body to update a randomization scheme."""

    trial_name: Optional[str] = None
    method: Optional[RandomizationMethod] = None
    blinding_level: Optional[BlindingLevel] = None
    allocation_ratio: Optional[AllocationRatio] = None
    block_sizes: Optional[list[int]] = None
    seed: Optional[int] = None


class RandomizePatientRequest(BaseModel):
    """Request body to randomize a patient."""

    patient_id: str = Field(..., description="Patient to randomize")
    randomized_by: str = Field("system", description="Performing user")
    stratum: Optional[dict[str, str]] = Field(
        None,
        description="Stratification factor values: {factor_name: level}",
    )


class UnblindingRequestCreate(BaseModel):
    """Request body to create an unblinding request."""

    assignment_id: str = Field(..., description="Assignment to unblind")
    patient_id: str = Field(..., description="Patient identifier")
    requestor: str = Field(..., description="Person requesting unblinding")
    reason: UnblindingReason = Field(..., description="Reason")
    urgency: str = Field("standard", description="Urgency: standard, urgent, emergency")


class UnblindingApproval(BaseModel):
    """Request body to approve or reject an unblinding request."""

    approved: bool = Field(..., description="True to approve, False to reject")
    approved_by: str = Field(..., description="Approver identity")


class SchemeListResponse(BaseModel):
    """Paginated response for randomization schemes."""

    items: list[RandomizationScheme]
    total: int
    limit: int
    offset: int


class AssignmentListResponse(BaseModel):
    """Paginated response for randomization assignments."""

    items: list[RandomizationAssignment]
    total: int
    limit: int
    offset: int


class BlindedAssignmentListResponse(BaseModel):
    """Paginated response for blinded assignments."""

    items: list[BlindedAssignment]
    total: int
    limit: int
    offset: int


class UnblindingRequestListResponse(BaseModel):
    """Response for unblinding requests."""

    items: list[UnblindingRequest]
    total: int


class AuditListResponse(BaseModel):
    """Response for audit trail entries."""

    items: list[RandomizationAuditEntry]
    total: int


class BalanceReport(BaseModel):
    """Full balance report across all stratification factors."""

    scheme_id: str
    overall_imbalance: float = Field(
        0.0, description="Overall imbalance score across all factors"
    )
    acceptable: bool = Field(True, description="Whether overall balance is acceptable")
    factors: list[BalanceCheck] = Field(
        default_factory=list, description="Per-factor balance details"
    )
    arm_totals: dict[str, int] = Field(
        default_factory=dict, description="Total count per arm"
    )


class RandomizationMetrics(BaseModel):
    """Aggregated randomization metrics across schemes."""

    model_config = ConfigDict(from_attributes=True)

    total_schemes: int = Field(0, description="Total randomization schemes")
    active_schemes: int = Field(0, description="Currently active schemes")
    total_randomized: int = Field(0, description="Total patients randomized")
    total_unblinded: int = Field(0, description="Total unblinded assignments")
    pending_unblinding_requests: int = Field(
        0, description="Unblinding requests awaiting approval"
    )
    schemes_by_method: dict[str, int] = Field(
        default_factory=dict, description="Count of schemes by method"
    )
    schemes_by_blinding: dict[str, int] = Field(
        default_factory=dict, description="Count of schemes by blinding level"
    )
    schemes_by_status: dict[str, int] = Field(
        default_factory=dict, description="Count of schemes by status"
    )
    average_imbalance_score: float = Field(
        0.0, description="Average imbalance score across active schemes"
    )
    randomizations_by_scheme: dict[str, int] = Field(
        default_factory=dict, description="Count by scheme ID"
    )
