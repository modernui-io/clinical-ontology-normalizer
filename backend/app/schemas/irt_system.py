"""Pydantic schemas for Interactive Response Technology (IRT/IWRS) (CLINICAL-19).

Manages IRT operations: transaction processing (screening, randomization, drug
assignment, resupply, visit confirmation, unblinding, dose modification,
discontinuation), drug supply tracking and accountability, visit schedule
management with window calculations, stratification factor management,
and IRT operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class IRTTransactionType(str, Enum):
    """Type of IRT transaction."""

    SCREENING = "screening"
    RANDOMIZATION = "randomization"
    DRUG_ASSIGNMENT = "drug_assignment"
    DRUG_RESUPPLY = "drug_resupply"
    VISIT_CONFIRMATION = "visit_confirmation"
    UNBLINDING = "unblinding"
    DOSE_MODIFICATION = "dose_modification"
    DISCONTINUATION = "discontinuation"


class DrugSupplyStatus(str, Enum):
    """Status of a drug supply kit."""

    AVAILABLE = "available"
    ASSIGNED = "assigned"
    DISPENSED = "dispensed"
    RETURNED = "returned"
    DESTROYED = "destroyed"
    EXPIRED = "expired"


class VisitWindow(str, Enum):
    """Visit window compliance status."""

    EARLY = "early"
    ON_TIME = "on_time"
    LATE = "late"
    MISSED = "missed"


class StratificationFactor(str, Enum):
    """Stratification factor for randomization."""

    AGE_GROUP = "age_group"
    SEX = "sex"
    DISEASE_SEVERITY = "disease_severity"
    PRIOR_THERAPY = "prior_therapy"
    GEOGRAPHIC_REGION = "geographic_region"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class IRTTransaction(BaseModel):
    """A single IRT transaction record."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique transaction identifier")
    trial_id: str = Field(..., description="Trial identifier")
    site_id: str = Field(..., description="Site identifier")
    patient_id: str = Field(..., description="Patient identifier")
    transaction_type: IRTTransactionType = Field(..., description="Type of IRT transaction")
    timestamp: datetime = Field(..., description="When the transaction occurred")
    details: str = Field(..., description="Transaction details or notes")
    performed_by: str = Field(..., description="User who performed the transaction")
    system_response: str = Field(..., description="IRT system response message")
    confirmation_number: str = Field(..., description="Unique confirmation number")


class DrugAssignment(BaseModel):
    """Drug kit assignment to a patient."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique assignment identifier")
    transaction_id: str = Field(..., description="Associated IRT transaction ID")
    patient_id: str = Field(..., description="Patient identifier")
    treatment_arm: str = Field(..., description="Treatment arm assignment")
    kit_number: str = Field(..., description="Drug kit number")
    lot_number: str = Field(..., description="Drug lot number")
    dispensed_date: datetime = Field(..., description="Date drug was dispensed")
    return_date: datetime | None = Field(None, description="Date drug was returned")
    compliance_pct: float = Field(
        ge=0.0, le=100.0, description="Patient compliance percentage (doses taken)"
    )


class VisitSchedule(BaseModel):
    """A scheduled visit with window tracking."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique visit schedule identifier")
    patient_id: str = Field(..., description="Patient identifier")
    trial_id: str = Field(..., description="Trial identifier")
    visit_number: int = Field(ge=1, description="Visit number in sequence")
    visit_name: str = Field(..., description="Visit name (e.g., Screening, Week 4)")
    window_open: datetime = Field(..., description="Earliest acceptable visit date")
    window_close: datetime = Field(..., description="Latest acceptable visit date")
    scheduled_date: datetime = Field(..., description="Target scheduled date")
    actual_date: datetime | None = Field(None, description="Actual date the visit occurred")
    window_status: VisitWindow = Field(
        default=VisitWindow.ON_TIME, description="Visit window compliance status"
    )


class StratificationEntry(BaseModel):
    """Stratification factor values for a patient."""

    model_config = ConfigDict(from_attributes=True)

    patient_id: str = Field(..., description="Patient identifier")
    factors: dict[str, str] = Field(
        default_factory=dict, description="Stratification factor name to value mapping"
    )
    stratum_id: str = Field(..., description="Assigned stratum identifier")


class IRTConfiguration(BaseModel):
    """IRT system configuration for a trial."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    randomization_ratio: str = Field(..., description="Randomization ratio (e.g., 1:1, 2:1)")
    stratification_factors: list[str] = Field(
        default_factory=list, description="List of stratification factor names"
    )
    drug_supply_buffer_weeks: int = Field(
        ge=1, description="Weeks of buffer drug supply to maintain at each site"
    )
    visit_windows: list[str] = Field(
        default_factory=list, description="List of visit window definitions"
    )
    dose_levels: list[str] = Field(
        default_factory=list, description="Available dose levels"
    )


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class IRTTransactionCreate(BaseModel):
    """Request to create a new IRT transaction."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial ID")
    site_id: str = Field(..., description="Site ID")
    patient_id: str = Field(..., description="Patient ID")
    transaction_type: IRTTransactionType = Field(..., description="Transaction type")
    details: str = Field(..., description="Transaction details")
    performed_by: str = Field(..., description="User performing the transaction")


class DrugAssignmentCreate(BaseModel):
    """Request to assign a drug kit to a patient."""

    model_config = ConfigDict(from_attributes=True)

    patient_id: str = Field(..., description="Patient ID")
    treatment_arm: str = Field(..., description="Treatment arm")
    kit_number: str = Field(..., description="Drug kit number")
    lot_number: str = Field(..., description="Drug lot number")


class DrugAssignmentUpdate(BaseModel):
    """Request to update a drug assignment."""

    model_config = ConfigDict(from_attributes=True)

    return_date: datetime | None = Field(None, description="Return date")
    compliance_pct: float | None = Field(None, ge=0.0, le=100.0, description="Compliance %")


class VisitScheduleCreate(BaseModel):
    """Request to create a visit schedule entry."""

    model_config = ConfigDict(from_attributes=True)

    patient_id: str = Field(..., description="Patient ID")
    trial_id: str = Field(..., description="Trial ID")
    visit_number: int = Field(ge=1, description="Visit number")
    visit_name: str = Field(..., description="Visit name")
    window_open: datetime = Field(..., description="Window open date")
    window_close: datetime = Field(..., description="Window close date")
    scheduled_date: datetime = Field(..., description="Scheduled date")


class VisitConfirmation(BaseModel):
    """Request to confirm a visit occurred."""

    model_config = ConfigDict(from_attributes=True)

    actual_date: datetime = Field(..., description="Actual visit date")
    performed_by: str = Field(default="system", description="Who confirmed the visit")


class DoseModificationRequest(BaseModel):
    """Request to modify a patient's dose level."""

    model_config = ConfigDict(from_attributes=True)

    patient_id: str = Field(..., description="Patient ID")
    trial_id: str = Field(..., description="Trial ID")
    current_dose: str = Field(..., description="Current dose level")
    new_dose: str = Field(..., description="New dose level")
    reason: str = Field(..., description="Reason for dose modification")
    performed_by: str = Field(..., description="User requesting modification")


class DrugResupplyRequest(BaseModel):
    """Request to resupply drug kits to a site."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial ID")
    site_id: str = Field(..., description="Site ID")
    kit_count: int = Field(ge=1, description="Number of kits to resupply")
    performed_by: str = Field(..., description="User requesting resupply")


class UnblindingRequest(BaseModel):
    """Request to unblind a patient's treatment assignment."""

    model_config = ConfigDict(from_attributes=True)

    patient_id: str = Field(..., description="Patient ID")
    trial_id: str = Field(..., description="Trial ID")
    reason: str = Field(..., description="Reason for unblinding")
    performed_by: str = Field(..., description="User requesting unblinding")


class StratificationEntryCreate(BaseModel):
    """Request to create a stratification entry for a patient."""

    model_config = ConfigDict(from_attributes=True)

    patient_id: str = Field(..., description="Patient ID")
    factors: dict[str, str] = Field(..., description="Stratification factor values")


class IRTConfigurationUpdate(BaseModel):
    """Request to update IRT configuration for a trial."""

    model_config = ConfigDict(from_attributes=True)

    randomization_ratio: str | None = Field(None, description="Randomization ratio")
    stratification_factors: list[str] | None = Field(
        None, description="Stratification factors"
    )
    drug_supply_buffer_weeks: int | None = Field(
        None, ge=1, description="Buffer weeks"
    )
    visit_windows: list[str] | None = Field(None, description="Visit windows")
    dose_levels: list[str] | None = Field(None, description="Dose levels")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class IRTTransactionListResponse(BaseModel):
    """List of IRT transactions."""

    model_config = ConfigDict(from_attributes=True)

    items: list[IRTTransaction] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class DrugAssignmentListResponse(BaseModel):
    """List of drug assignments."""

    model_config = ConfigDict(from_attributes=True)

    items: list[DrugAssignment] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class VisitScheduleListResponse(BaseModel):
    """List of visit schedules."""

    model_config = ConfigDict(from_attributes=True)

    items: list[VisitSchedule] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class StratificationEntryListResponse(BaseModel):
    """List of stratification entries."""

    model_config = ConfigDict(from_attributes=True)

    items: list[StratificationEntry] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class IRTConfigurationListResponse(BaseModel):
    """List of IRT configurations."""

    model_config = ConfigDict(from_attributes=True)

    items: list[IRTConfiguration] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


# ---------------------------------------------------------------------------
# Drug supply / accountability
# ---------------------------------------------------------------------------


class DrugKit(BaseModel):
    """A drug supply kit tracked in the IRT system."""

    model_config = ConfigDict(from_attributes=True)

    kit_number: str = Field(..., description="Drug kit number")
    lot_number: str = Field(..., description="Drug lot number")
    site_id: str = Field(..., description="Site where kit is located")
    trial_id: str = Field(..., description="Trial identifier")
    status: DrugSupplyStatus = Field(..., description="Current kit status")
    assigned_patient: str | None = Field(None, description="Patient assigned to this kit")
    expiry_date: datetime = Field(..., description="Kit expiry date")
    created_at: datetime = Field(..., description="When the kit was registered")


class DrugKitListResponse(BaseModel):
    """List of drug kits."""

    model_config = ConfigDict(from_attributes=True)

    items: list[DrugKit] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class DrugAccountabilitySummary(BaseModel):
    """Drug accountability summary for a site."""

    model_config = ConfigDict(from_attributes=True)

    site_id: str = Field(..., description="Site identifier")
    total_kits: int = Field(ge=0, description="Total kits at site")
    available: int = Field(ge=0, description="Kits available for dispensing")
    assigned: int = Field(ge=0, description="Kits assigned to patients")
    dispensed: int = Field(ge=0, description="Kits dispensed to patients")
    returned: int = Field(ge=0, description="Kits returned")
    destroyed: int = Field(ge=0, description="Kits destroyed")
    expired: int = Field(ge=0, description="Kits expired")
    buffer_weeks_remaining: float = Field(
        ge=0.0, description="Estimated weeks of supply remaining"
    )
    resupply_needed: bool = Field(
        default=False, description="Whether resupply is needed"
    )


# ---------------------------------------------------------------------------
# Metrics / dashboard
# ---------------------------------------------------------------------------


class IRTMetrics(BaseModel):
    """Aggregated IRT operational metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_transactions: int = Field(ge=0, description="Total IRT transactions")
    transactions_by_type: dict[str, int] = Field(
        default_factory=dict, description="Transaction counts by type"
    )
    active_patients: int = Field(ge=0, description="Currently active patients")
    drug_kits_available: int = Field(ge=0, description="Drug kits available across all sites")
    drug_kits_dispensed: int = Field(ge=0, description="Total drug kits dispensed")
    visit_compliance_rate: float = Field(
        ge=0.0, le=100.0, description="Percentage of visits within window"
    )
    avg_drug_compliance_pct: float = Field(
        ge=0.0, le=100.0, description="Average patient drug compliance percentage"
    )
    missed_visits_30d: int = Field(ge=0, description="Missed visits in last 30 days")
