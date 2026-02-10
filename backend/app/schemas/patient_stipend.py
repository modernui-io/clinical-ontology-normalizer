"""Pydantic schemas for Patient Stipend Management.

Manages patient compensation for clinical trial participation including stipend
schedules, payment processing, tax reporting, travel reimbursements, and
compliance with fair market value (FMV) guidelines.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class StipendType(str, Enum):
    """Type of patient stipend or compensation."""

    VISIT_COMPENSATION = "visit_compensation"
    TRAVEL_REIMBURSEMENT = "travel_reimbursement"
    MEAL_ALLOWANCE = "meal_allowance"
    PARKING = "parking"
    LODGING = "lodging"
    LOST_WAGES = "lost_wages"
    COMPLETION_BONUS = "completion_bonus"
    SCREEN_FAILURE_COMPENSATION = "screen_failure_compensation"


class PaymentMethod(str, Enum):
    """Method used to pay patient stipends."""

    CHECK = "check"
    DIRECT_DEPOSIT = "direct_deposit"
    PREPAID_CARD = "prepaid_card"
    WIRE_TRANSFER = "wire_transfer"
    GIFT_CARD = "gift_card"


class StipendStatus(str, Enum):
    """Lifecycle status of a patient stipend payment."""

    SCHEDULED = "scheduled"
    APPROVED = "approved"
    PROCESSING = "processing"
    PAID = "paid"
    CANCELLED = "cancelled"
    ON_HOLD = "on_hold"
    RETURNED = "returned"


class TaxFormType(str, Enum):
    """Type of tax form for patient compensation reporting."""

    W9 = "w9"
    W8BEN = "w8ben"
    T4A = "t4a"
    SELF_CERTIFICATION = "self_certification"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class StipendSchedule(BaseModel):
    """Defines the compensation schedule template for a trial visit/activity."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique schedule identifier")
    trial_id: str = Field(..., description="Associated clinical trial identifier")
    stipend_type: StipendType = Field(..., description="Type of stipend")
    visit_number: int | None = Field(None, description="Visit number this schedule applies to (null for non-visit stipends)")
    amount: float = Field(..., ge=0.0, description="Stipend amount in the specified currency")
    currency: str = Field(default="USD", description="ISO 4217 currency code")
    description: str = Field(..., description="Human-readable description of the stipend")
    requires_receipt: bool = Field(default=False, description="Whether a receipt is required for reimbursement")
    max_amount: float | None = Field(None, ge=0.0, description="Maximum reimbursable amount (null if fixed)")


class PatientStipend(BaseModel):
    """A specific stipend payment record for a patient in a trial."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique stipend payment identifier")
    patient_id: str = Field(..., description="Patient identifier")
    trial_id: str = Field(..., description="Clinical trial identifier")
    site_id: str = Field(..., description="Site identifier where patient is enrolled")
    schedule_id: str | None = Field(None, description="Reference to stipend schedule template")
    stipend_type: StipendType = Field(..., description="Type of stipend payment")
    visit_number: int | None = Field(None, description="Visit number for visit-based stipends")
    visit_date: datetime | None = Field(None, description="Date the visit occurred")
    amount: float = Field(..., ge=0.0, description="Payment amount")
    currency: str = Field(default="USD", description="ISO 4217 currency code")
    status: StipendStatus = Field(default=StipendStatus.SCHEDULED, description="Current payment status")
    payment_method: PaymentMethod | None = Field(None, description="Payment method used")
    payment_date: datetime | None = Field(None, description="Date the payment was issued")
    payment_reference: str | None = Field(None, description="Payment transaction reference number")
    receipt_submitted: bool = Field(default=False, description="Whether patient submitted a receipt")
    receipt_verified: bool = Field(default=False, description="Whether the submitted receipt has been verified")
    notes: str | None = Field(None, description="Additional notes about this payment")
    created_at: datetime = Field(..., description="Record creation timestamp")


class TravelReimbursement(BaseModel):
    """Travel reimbursement claim for a patient trial visit."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique travel reimbursement identifier")
    patient_id: str = Field(..., description="Patient identifier")
    trial_id: str = Field(..., description="Clinical trial identifier")
    visit_number: int = Field(..., description="Visit number the travel was for")
    travel_date: datetime = Field(..., description="Date of travel")
    distance_miles: float = Field(default=0.0, ge=0.0, description="Round-trip distance in miles")
    mileage_rate: float = Field(default=0.67, ge=0.0, description="IRS standard mileage rate per mile")
    parking_amount: float = Field(default=0.0, ge=0.0, description="Parking fees")
    tolls_amount: float = Field(default=0.0, ge=0.0, description="Toll charges")
    lodging_amount: float = Field(default=0.0, ge=0.0, description="Lodging/hotel costs")
    meal_amount: float = Field(default=0.0, ge=0.0, description="Meal expenses")
    total_amount: float = Field(..., ge=0.0, description="Total reimbursement amount")
    receipt_path: str | None = Field(None, description="File path or reference to uploaded receipt")
    status: StipendStatus = Field(default=StipendStatus.SCHEDULED, description="Reimbursement status")
    created_at: datetime = Field(..., description="Record creation timestamp")


class TaxRecord(BaseModel):
    """Tax reporting record for patient compensation in a tax year."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique tax record identifier")
    patient_id: str = Field(..., description="Patient identifier")
    trial_id: str = Field(..., description="Clinical trial identifier")
    tax_year: int = Field(..., ge=2020, description="Tax reporting year")
    total_paid_ytd: float = Field(default=0.0, ge=0.0, description="Total amount paid year-to-date")
    form_type: TaxFormType = Field(..., description="Type of tax form required")
    form_submitted: bool = Field(default=False, description="Whether the tax form has been submitted")
    form_date: datetime | None = Field(None, description="Date the tax form was submitted or generated")
    threshold_amount: float = Field(default=600.0, ge=0.0, description="IRS reporting threshold amount")
    threshold_exceeded: bool = Field(default=False, description="Whether the reporting threshold has been exceeded")
    withholding_required: bool = Field(default=False, description="Whether tax withholding is required")
    created_at: datetime = Field(..., description="Record creation timestamp")


class PatientPaymentSummary(BaseModel):
    """Aggregated payment summary for a patient across a trial."""

    model_config = ConfigDict(from_attributes=True)

    patient_id: str = Field(..., description="Patient identifier")
    trial_id: str = Field(..., description="Clinical trial identifier")
    total_earned: float = Field(default=0.0, ge=0.0, description="Total amount earned (all statuses)")
    total_paid: float = Field(default=0.0, ge=0.0, description="Total amount actually paid")
    total_pending: float = Field(default=0.0, ge=0.0, description="Total amount pending payment")
    payments_by_type: dict[str, float] = Field(
        default_factory=dict, description="Breakdown of payments by stipend type"
    )
    visits_completed: int = Field(default=0, ge=0, description="Number of visits with compensation")


class StipendMetrics(BaseModel):
    """Aggregated metrics for the patient stipend management module."""

    model_config = ConfigDict(from_attributes=True)

    total_schedules: int = Field(default=0, ge=0, description="Total stipend schedules defined")
    total_stipends: int = Field(default=0, ge=0, description="Total individual stipend records")
    total_paid_amount: float = Field(default=0.0, ge=0.0, description="Total amount paid across all patients")
    total_pending_amount: float = Field(default=0.0, ge=0.0, description="Total amount pending payment")
    stipends_by_status: dict[str, int] = Field(
        default_factory=dict, description="Count of stipends by status"
    )
    stipends_by_type: dict[str, int] = Field(
        default_factory=dict, description="Count of stipends by type"
    )
    total_travel_reimbursements: int = Field(default=0, ge=0, description="Total travel reimbursement claims")
    total_travel_amount: float = Field(default=0.0, ge=0.0, description="Total travel reimbursement amount")
    total_tax_records: int = Field(default=0, ge=0, description="Total tax records")
    patients_exceeding_threshold: int = Field(default=0, ge=0, description="Patients exceeding tax reporting threshold")
    avg_payment_per_visit: float = Field(default=0.0, ge=0.0, description="Average payment amount per visit")
    unique_patients: int = Field(default=0, ge=0, description="Number of unique patients with stipends")


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class StipendScheduleCreate(BaseModel):
    """Request to create a new stipend schedule."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Clinical trial identifier")
    stipend_type: StipendType = Field(..., description="Type of stipend")
    visit_number: int | None = Field(None, description="Visit number (null for non-visit stipends)")
    amount: float = Field(..., ge=0.0, description="Stipend amount")
    currency: str = Field(default="USD", description="Currency code")
    description: str = Field(..., description="Description of the stipend")
    requires_receipt: bool = Field(default=False, description="Whether receipt is required")
    max_amount: float | None = Field(None, ge=0.0, description="Maximum reimbursable amount")


class StipendScheduleUpdate(BaseModel):
    """Request to update a stipend schedule."""

    model_config = ConfigDict(from_attributes=True)

    stipend_type: StipendType | None = Field(None, description="Type of stipend")
    visit_number: int | None = Field(None, description="Visit number")
    amount: float | None = Field(None, ge=0.0, description="Stipend amount")
    currency: str | None = Field(None, description="Currency code")
    description: str | None = Field(None, description="Description")
    requires_receipt: bool | None = Field(None, description="Whether receipt is required")
    max_amount: float | None = Field(None, ge=0.0, description="Maximum amount")


class PatientStipendCreate(BaseModel):
    """Request to create a new patient stipend payment."""

    model_config = ConfigDict(from_attributes=True)

    patient_id: str = Field(..., description="Patient identifier")
    trial_id: str = Field(..., description="Clinical trial identifier")
    site_id: str = Field(..., description="Site identifier")
    schedule_id: str | None = Field(None, description="Schedule template reference")
    stipend_type: StipendType = Field(..., description="Type of stipend")
    visit_number: int | None = Field(None, description="Visit number")
    visit_date: datetime | None = Field(None, description="Date of visit")
    amount: float = Field(..., ge=0.0, description="Payment amount")
    currency: str = Field(default="USD", description="Currency code")
    payment_method: PaymentMethod | None = Field(None, description="Payment method")
    notes: str | None = Field(None, description="Notes")


class PatientStipendUpdate(BaseModel):
    """Request to update a patient stipend payment."""

    model_config = ConfigDict(from_attributes=True)

    status: StipendStatus | None = Field(None, description="Payment status")
    payment_method: PaymentMethod | None = Field(None, description="Payment method")
    amount: float | None = Field(None, ge=0.0, description="Payment amount")
    notes: str | None = Field(None, description="Notes")


class TravelReimbursementCreate(BaseModel):
    """Request to create a new travel reimbursement claim."""

    model_config = ConfigDict(from_attributes=True)

    patient_id: str = Field(..., description="Patient identifier")
    trial_id: str = Field(..., description="Clinical trial identifier")
    visit_number: int = Field(..., description="Visit number")
    travel_date: datetime = Field(..., description="Date of travel")
    distance_miles: float = Field(default=0.0, ge=0.0, description="Round-trip distance in miles")
    mileage_rate: float = Field(default=0.67, ge=0.0, description="Mileage rate per mile")
    parking_amount: float = Field(default=0.0, ge=0.0, description="Parking fees")
    tolls_amount: float = Field(default=0.0, ge=0.0, description="Toll charges")
    lodging_amount: float = Field(default=0.0, ge=0.0, description="Lodging costs")
    meal_amount: float = Field(default=0.0, ge=0.0, description="Meal expenses")
    receipt_path: str | None = Field(None, description="Receipt file reference")


class TravelReimbursementUpdate(BaseModel):
    """Request to update a travel reimbursement claim."""

    model_config = ConfigDict(from_attributes=True)

    distance_miles: float | None = Field(None, ge=0.0, description="Distance in miles")
    mileage_rate: float | None = Field(None, ge=0.0, description="Mileage rate")
    parking_amount: float | None = Field(None, ge=0.0, description="Parking fees")
    tolls_amount: float | None = Field(None, ge=0.0, description="Toll charges")
    lodging_amount: float | None = Field(None, ge=0.0, description="Lodging costs")
    meal_amount: float | None = Field(None, ge=0.0, description="Meal expenses")
    receipt_path: str | None = Field(None, description="Receipt file reference")
    status: StipendStatus | None = Field(None, description="Reimbursement status")


class ProcessPaymentRequest(BaseModel):
    """Request to process a stipend payment."""

    model_config = ConfigDict(from_attributes=True)

    payment_method: PaymentMethod = Field(..., description="Payment method to use")
    payment_reference: str | None = Field(None, description="External payment reference")
    notes: str | None = Field(None, description="Processing notes")


class ReceiptSubmission(BaseModel):
    """Request to submit or verify a receipt."""

    model_config = ConfigDict(from_attributes=True)

    receipt_path: str = Field(..., description="File path or reference to the receipt")
    notes: str | None = Field(None, description="Notes about the receipt")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class StipendScheduleListResponse(BaseModel):
    """List of stipend schedules."""

    model_config = ConfigDict(from_attributes=True)

    items: list[StipendSchedule] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class PatientStipendListResponse(BaseModel):
    """List of patient stipend payments."""

    model_config = ConfigDict(from_attributes=True)

    items: list[PatientStipend] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class TravelReimbursementListResponse(BaseModel):
    """List of travel reimbursement claims."""

    model_config = ConfigDict(from_attributes=True)

    items: list[TravelReimbursement] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class TaxRecordListResponse(BaseModel):
    """List of tax records."""

    model_config = ConfigDict(from_attributes=True)

    items: list[TaxRecord] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")
