"""Pydantic schemas for Patient Travel & Logistics Management (OPS-TRAVEL).

Manages patient travel for clinical trial visits: travel requests, booking
management, reimbursement processing, accommodation arrangements, transportation
coordination, caregiver travel support, and travel metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TravelRequestStatus(str, Enum):
    """Status of a patient travel request."""

    REQUESTED = "requested"
    APPROVED = "approved"
    BOOKED = "booked"
    IN_TRANSIT = "in_transit"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REIMBURSEMENT_PENDING = "reimbursement_pending"
    REIMBURSED = "reimbursed"


class TransportMode(str, Enum):
    """Mode of transportation."""

    AIR = "air"
    RAIL = "rail"
    CAR_SERVICE = "car_service"
    RIDESHARE = "rideshare"
    PERSONAL_VEHICLE = "personal_vehicle"
    PUBLIC_TRANSIT = "public_transit"
    MEDICAL_TRANSPORT = "medical_transport"


class AccommodationType(str, Enum):
    """Type of accommodation."""

    HOTEL = "hotel"
    EXTENDED_STAY = "extended_stay"
    PATIENT_HOUSING = "patient_housing"
    NONE_REQUIRED = "none_required"


class ReimbursementStatus(str, Enum):
    """Status of a travel reimbursement."""

    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    PAID = "paid"
    DENIED = "denied"


class TravelerType(str, Enum):
    """Type of traveler."""

    PATIENT = "patient"
    CAREGIVER = "caregiver"
    LEGAL_GUARDIAN = "legal_guardian"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class TravelRequest(BaseModel):
    """A patient or caregiver travel request for a trial visit."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique travel request identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    site_id: str = Field(..., description="Destination site identifier")
    patient_id: str = Field(..., description="Patient identifier")
    traveler_type: TravelerType = Field(..., description="Type of traveler")
    visit_type: str = Field(..., description="Type of visit (screening, treatment, follow-up)")
    visit_date: datetime = Field(..., description="Date of the clinical visit")
    origin_city: str = Field(..., description="Traveler's origin city")
    origin_country: str = Field(..., description="Traveler's origin country")
    destination_city: str = Field(..., description="Destination city")
    destination_country: str = Field(..., description="Destination country")
    transport_mode: TransportMode = Field(..., description="Primary mode of transportation")
    accommodation_type: AccommodationType = Field(
        default=AccommodationType.NONE_REQUIRED, description="Accommodation type needed"
    )
    accommodation_nights: int = Field(default=0, ge=0, description="Number of accommodation nights")
    special_needs: str | None = Field(None, description="Special travel needs or accommodations")
    status: TravelRequestStatus = Field(
        default=TravelRequestStatus.REQUESTED, description="Request status"
    )
    estimated_cost: float = Field(default=0.0, ge=0, description="Estimated total travel cost")
    actual_cost: float | None = Field(None, ge=0, description="Actual total travel cost")
    approved_by: str | None = Field(None, description="Person who approved the request")
    approved_date: datetime | None = Field(None, description="Approval date")
    booking_reference: str | None = Field(None, description="Booking reference number")
    created_at: datetime = Field(..., description="Record creation timestamp")


class TravelBooking(BaseModel):
    """A booking associated with a travel request."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique booking identifier")
    travel_request_id: str = Field(..., description="Associated travel request ID")
    booking_type: str = Field(..., description="Type: flight, hotel, car_service, etc.")
    provider: str = Field(..., description="Service provider name")
    confirmation_number: str = Field(..., description="Provider confirmation number")
    departure_date: datetime = Field(..., description="Departure or check-in date")
    return_date: datetime | None = Field(None, description="Return or check-out date")
    cost: float = Field(ge=0, description="Booking cost")
    currency: str = Field(default="USD", description="Currency code")
    notes: str | None = Field(None, description="Additional booking notes")
    cancelled: bool = Field(default=False, description="Whether booking has been cancelled")


class TravelReimbursement(BaseModel):
    """A reimbursement for patient travel expenses."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique reimbursement identifier")
    travel_request_id: str = Field(..., description="Associated travel request ID")
    patient_id: str = Field(..., description="Patient identifier")
    expense_type: str = Field(..., description="Type of expense (transport, meals, parking, etc.)")
    amount: float = Field(ge=0, description="Reimbursement amount")
    currency: str = Field(default="USD", description="Currency code")
    receipt_provided: bool = Field(default=False, description="Whether receipt was provided")
    status: ReimbursementStatus = Field(
        default=ReimbursementStatus.PENDING, description="Reimbursement status"
    )
    submitted_date: datetime = Field(..., description="Date submitted")
    reviewed_by: str | None = Field(None, description="Reviewer")
    reviewed_date: datetime | None = Field(None, description="Review date")
    paid_date: datetime | None = Field(None, description="Payment date")
    payment_method: str | None = Field(None, description="Payment method used")
    denial_reason: str | None = Field(None, description="Reason for denial if denied")


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class TravelRequestCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    patient_id: str
    traveler_type: TravelerType
    visit_type: str
    visit_date: datetime
    origin_city: str
    origin_country: str
    destination_city: str
    destination_country: str
    transport_mode: TransportMode
    accommodation_type: AccommodationType = AccommodationType.NONE_REQUIRED
    accommodation_nights: int = 0
    special_needs: str | None = None
    estimated_cost: float = 0.0


class TravelRequestUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: TravelRequestStatus | None = None
    transport_mode: TransportMode | None = None
    accommodation_type: AccommodationType | None = None
    accommodation_nights: int | None = None
    special_needs: str | None = None
    estimated_cost: float | None = None
    actual_cost: float | None = None
    approved_by: str | None = None
    booking_reference: str | None = None


class TravelBookingCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    travel_request_id: str
    booking_type: str
    provider: str
    confirmation_number: str
    departure_date: datetime
    return_date: datetime | None = None
    cost: float = Field(ge=0)
    currency: str = "USD"
    notes: str | None = None


class TravelBookingUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    provider: str | None = None
    confirmation_number: str | None = None
    departure_date: datetime | None = None
    return_date: datetime | None = None
    cost: float | None = None
    cancelled: bool | None = None
    notes: str | None = None


class TravelReimbursementCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    travel_request_id: str
    patient_id: str
    expense_type: str
    amount: float = Field(ge=0)
    currency: str = "USD"
    receipt_provided: bool = False


class TravelReimbursementUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: ReimbursementStatus | None = None
    reviewed_by: str | None = None
    payment_method: str | None = None
    denial_reason: str | None = None


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class TravelRequestListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[TravelRequest] = Field(default_factory=list)
    total: int = Field(ge=0)


class TravelBookingListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[TravelBooking] = Field(default_factory=list)
    total: int = Field(ge=0)


class TravelReimbursementListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[TravelReimbursement] = Field(default_factory=list)
    total: int = Field(ge=0)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


class PatientTravelMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_requests: int = Field(ge=0)
    requests_by_status: dict[str, int] = Field(default_factory=dict)
    requests_by_transport: dict[str, int] = Field(default_factory=dict)
    total_bookings: int = Field(ge=0)
    active_bookings: int = Field(ge=0)
    cancelled_bookings: int = Field(ge=0)
    total_reimbursements: int = Field(ge=0)
    reimbursements_by_status: dict[str, int] = Field(default_factory=dict)
    total_reimbursement_amount: float = Field(ge=0)
    pending_reimbursement_amount: float = Field(ge=0)
    total_travel_cost: float = Field(ge=0)
    avg_cost_per_visit: float = Field(ge=0)
    total_patients_traveled: int = Field(ge=0)
    total_caregivers_traveled: int = Field(ge=0)
