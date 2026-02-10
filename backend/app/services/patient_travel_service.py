"""Patient Travel & Logistics Management Service (OPS-TRAVEL).

Manages patient travel for clinical trial visits: travel requests, booking
management, reimbursement processing, accommodation arrangements, transportation
coordination, caregiver travel support, and travel metrics.

Usage:
    from app.services.patient_travel_service import (
        get_patient_travel_service,
    )

    svc = get_patient_travel_service()
    requests = svc.list_travel_requests()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.patient_travel import (
    AccommodationType,
    PatientTravelMetrics,
    ReimbursementStatus,
    TransportMode,
    TravelBooking,
    TravelBookingCreate,
    TravelBookingUpdate,
    TravelReimbursement,
    TravelReimbursementCreate,
    TravelReimbursementUpdate,
    TravelRequest,
    TravelRequestCreate,
    TravelRequestStatus,
    TravelRequestUpdate,
    TravelerType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class PatientTravelService:
    """In-memory Patient Travel & Logistics engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._travel_requests: dict[str, TravelRequest] = {}
        self._bookings: dict[str, TravelBooking] = {}
        self._reimbursements: dict[str, TravelReimbursement] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic patient travel data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 12 Travel Requests ---
        requests_data = [
            # EYLEA trial requests
            {
                "id": "TR-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "patient_id": "PT-1001",
                "traveler_type": TravelerType.PATIENT,
                "visit_type": "screening",
                "visit_date": now - timedelta(days=60),
                "origin_city": "Hartford",
                "origin_country": "US",
                "destination_city": "Boston",
                "destination_country": "US",
                "transport_mode": TransportMode.CAR_SERVICE,
                "accommodation_type": AccommodationType.HOTEL,
                "accommodation_nights": 1,
                "special_needs": None,
                "status": TravelRequestStatus.COMPLETED,
                "estimated_cost": 450.0,
                "actual_cost": 475.50,
                "approved_by": "Dr. Sarah Chen",
                "approved_date": now - timedelta(days=65),
                "booking_reference": "BK-REF-001",
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "TR-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "patient_id": "PT-1002",
                "traveler_type": TravelerType.PATIENT,
                "visit_type": "treatment",
                "visit_date": now - timedelta(days=30),
                "origin_city": "Providence",
                "origin_country": "US",
                "destination_city": "Boston",
                "destination_country": "US",
                "transport_mode": TransportMode.RAIL,
                "accommodation_type": AccommodationType.NONE_REQUIRED,
                "accommodation_nights": 0,
                "special_needs": "Wheelchair accessible transport required",
                "status": TravelRequestStatus.REIMBURSED,
                "estimated_cost": 120.0,
                "actual_cost": 115.00,
                "approved_by": "Dr. Sarah Chen",
                "approved_date": now - timedelta(days=35),
                "booking_reference": "BK-REF-002",
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "TR-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "patient_id": "PT-1003",
                "traveler_type": TravelerType.CAREGIVER,
                "visit_type": "treatment",
                "visit_date": now - timedelta(days=15),
                "origin_city": "Philadelphia",
                "origin_country": "US",
                "destination_city": "New York",
                "destination_country": "US",
                "transport_mode": TransportMode.RAIL,
                "accommodation_type": AccommodationType.NONE_REQUIRED,
                "accommodation_nights": 0,
                "special_needs": None,
                "status": TravelRequestStatus.COMPLETED,
                "estimated_cost": 95.0,
                "actual_cost": 89.00,
                "approved_by": "Dr. James Lee",
                "approved_date": now - timedelta(days=20),
                "booking_reference": "BK-REF-003",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "TR-004",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-103",
                "patient_id": "PT-1004",
                "traveler_type": TravelerType.PATIENT,
                "visit_type": "follow-up",
                "visit_date": now + timedelta(days=10),
                "origin_city": "Baltimore",
                "origin_country": "US",
                "destination_city": "Washington",
                "destination_country": "US",
                "transport_mode": TransportMode.RIDESHARE,
                "accommodation_type": AccommodationType.NONE_REQUIRED,
                "accommodation_nights": 0,
                "special_needs": None,
                "status": TravelRequestStatus.APPROVED,
                "estimated_cost": 65.0,
                "actual_cost": None,
                "approved_by": "Dr. James Lee",
                "approved_date": now - timedelta(days=2),
                "booking_reference": None,
                "created_at": now - timedelta(days=5),
            },
            # Dupixent trial requests
            {
                "id": "TR-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "patient_id": "PT-2001",
                "traveler_type": TravelerType.PATIENT,
                "visit_type": "screening",
                "visit_date": now - timedelta(days=90),
                "origin_city": "San Diego",
                "origin_country": "US",
                "destination_city": "Los Angeles",
                "destination_country": "US",
                "transport_mode": TransportMode.CAR_SERVICE,
                "accommodation_type": AccommodationType.NONE_REQUIRED,
                "accommodation_nights": 0,
                "special_needs": None,
                "status": TravelRequestStatus.COMPLETED,
                "estimated_cost": 200.0,
                "actual_cost": 210.00,
                "approved_by": "Dr. Maria Lopez",
                "approved_date": now - timedelta(days=95),
                "booking_reference": "BK-REF-005",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "TR-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-105",
                "patient_id": "PT-2002",
                "traveler_type": TravelerType.LEGAL_GUARDIAN,
                "visit_type": "treatment",
                "visit_date": now - timedelta(days=45),
                "origin_city": "Sacramento",
                "origin_country": "US",
                "destination_city": "San Francisco",
                "destination_country": "US",
                "transport_mode": TransportMode.AIR,
                "accommodation_type": AccommodationType.HOTEL,
                "accommodation_nights": 2,
                "special_needs": "Pediatric patient - guardian must accompany",
                "status": TravelRequestStatus.REIMBURSEMENT_PENDING,
                "estimated_cost": 850.0,
                "actual_cost": 920.00,
                "approved_by": "Dr. Maria Lopez",
                "approved_date": now - timedelta(days=50),
                "booking_reference": "BK-REF-006",
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "TR-007",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-106",
                "patient_id": "PT-2003",
                "traveler_type": TravelerType.PATIENT,
                "visit_type": "treatment",
                "visit_date": now + timedelta(days=5),
                "origin_city": "Portland",
                "origin_country": "US",
                "destination_city": "Seattle",
                "destination_country": "US",
                "transport_mode": TransportMode.AIR,
                "accommodation_type": AccommodationType.EXTENDED_STAY,
                "accommodation_nights": 3,
                "special_needs": "Oxygen support during travel",
                "status": TravelRequestStatus.BOOKED,
                "estimated_cost": 1200.0,
                "actual_cost": None,
                "approved_by": "Dr. Robert Kim",
                "approved_date": now - timedelta(days=3),
                "booking_reference": "BK-REF-007",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "TR-008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "patient_id": "PT-2004",
                "traveler_type": TravelerType.PATIENT,
                "visit_type": "follow-up",
                "visit_date": now + timedelta(days=20),
                "origin_city": "Phoenix",
                "origin_country": "US",
                "destination_city": "Los Angeles",
                "destination_country": "US",
                "transport_mode": TransportMode.AIR,
                "accommodation_type": AccommodationType.HOTEL,
                "accommodation_nights": 1,
                "special_needs": None,
                "status": TravelRequestStatus.REQUESTED,
                "estimated_cost": 550.0,
                "actual_cost": None,
                "approved_by": None,
                "approved_date": None,
                "booking_reference": None,
                "created_at": now - timedelta(days=1),
            },
            # Libtayo trial requests
            {
                "id": "TR-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-107",
                "patient_id": "PT-3001",
                "traveler_type": TravelerType.PATIENT,
                "visit_type": "treatment",
                "visit_date": now - timedelta(days=50),
                "origin_city": "Dallas",
                "origin_country": "US",
                "destination_city": "Houston",
                "destination_country": "US",
                "transport_mode": TransportMode.MEDICAL_TRANSPORT,
                "accommodation_type": AccommodationType.PATIENT_HOUSING,
                "accommodation_nights": 4,
                "special_needs": "Medical transport with IV support",
                "status": TravelRequestStatus.COMPLETED,
                "estimated_cost": 2500.0,
                "actual_cost": 2750.00,
                "approved_by": "Dr. Angela White",
                "approved_date": now - timedelta(days=55),
                "booking_reference": "BK-REF-009",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "TR-010",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-107",
                "patient_id": "PT-3002",
                "traveler_type": TravelerType.CAREGIVER,
                "visit_type": "treatment",
                "visit_date": now - timedelta(days=20),
                "origin_city": "Austin",
                "origin_country": "US",
                "destination_city": "Houston",
                "destination_country": "US",
                "transport_mode": TransportMode.PERSONAL_VEHICLE,
                "accommodation_type": AccommodationType.HOTEL,
                "accommodation_nights": 2,
                "special_needs": None,
                "status": TravelRequestStatus.REIMBURSEMENT_PENDING,
                "estimated_cost": 400.0,
                "actual_cost": 385.00,
                "approved_by": "Dr. Angela White",
                "approved_date": now - timedelta(days=25),
                "booking_reference": "BK-REF-010",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "TR-011",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-108",
                "patient_id": "PT-3003",
                "traveler_type": TravelerType.PATIENT,
                "visit_type": "screening",
                "visit_date": now + timedelta(days=15),
                "origin_city": "Miami",
                "origin_country": "US",
                "destination_city": "Tampa",
                "destination_country": "US",
                "transport_mode": TransportMode.AIR,
                "accommodation_type": AccommodationType.HOTEL,
                "accommodation_nights": 1,
                "special_needs": None,
                "status": TravelRequestStatus.APPROVED,
                "estimated_cost": 350.0,
                "actual_cost": None,
                "approved_by": "Dr. Thomas Park",
                "approved_date": now - timedelta(days=1),
                "booking_reference": None,
                "created_at": now - timedelta(days=7),
            },
            {
                "id": "TR-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-108",
                "patient_id": "PT-3004",
                "traveler_type": TravelerType.PATIENT,
                "visit_type": "treatment",
                "visit_date": now - timedelta(days=10),
                "origin_city": "Orlando",
                "origin_country": "US",
                "destination_city": "Tampa",
                "destination_country": "US",
                "transport_mode": TransportMode.CAR_SERVICE,
                "accommodation_type": AccommodationType.NONE_REQUIRED,
                "accommodation_nights": 0,
                "special_needs": None,
                "status": TravelRequestStatus.CANCELLED,
                "estimated_cost": 150.0,
                "actual_cost": None,
                "approved_by": "Dr. Thomas Park",
                "approved_date": now - timedelta(days=15),
                "booking_reference": None,
                "created_at": now - timedelta(days=20),
            },
        ]

        for r in requests_data:
            self._travel_requests[r["id"]] = TravelRequest(**r)

        # --- 10 Travel Bookings ---
        bookings_data = [
            {"id": "BK-001", "travel_request_id": "TR-001", "booking_type": "car_service", "provider": "Executive Car Service", "confirmation_number": "ECS-44521", "departure_date": now - timedelta(days=60), "return_date": now - timedelta(days=59), "cost": 180.0, "currency": "USD", "notes": "Round-trip Hartford to Boston", "cancelled": False},
            {"id": "BK-002", "travel_request_id": "TR-001", "booking_type": "hotel", "provider": "Boston Marriott Copley", "confirmation_number": "MAR-78923", "departure_date": now - timedelta(days=60), "return_date": now - timedelta(days=59), "cost": 295.50, "currency": "USD", "notes": "One night, accessible room", "cancelled": False},
            {"id": "BK-003", "travel_request_id": "TR-002", "booking_type": "rail", "provider": "Amtrak", "confirmation_number": "AMT-55123", "departure_date": now - timedelta(days=30), "return_date": now - timedelta(days=30), "cost": 115.0, "currency": "USD", "notes": "Acela round-trip, wheelchair accessible", "cancelled": False},
            {"id": "BK-004", "travel_request_id": "TR-005", "booking_type": "car_service", "provider": "Pacific Luxury Transport", "confirmation_number": "PLT-33210", "departure_date": now - timedelta(days=90), "return_date": now - timedelta(days=90), "cost": 210.0, "currency": "USD", "notes": "Round-trip San Diego to LA", "cancelled": False},
            {"id": "BK-005", "travel_request_id": "TR-006", "booking_type": "flight", "provider": "United Airlines", "confirmation_number": "UA-KL9821", "departure_date": now - timedelta(days=46), "return_date": now - timedelta(days=43), "cost": 520.0, "currency": "USD", "notes": "SMF to SFO round-trip", "cancelled": False},
            {"id": "BK-006", "travel_request_id": "TR-006", "booking_type": "hotel", "provider": "Hilton Union Square", "confirmation_number": "HLT-92031", "departure_date": now - timedelta(days=46), "return_date": now - timedelta(days=44), "cost": 400.0, "currency": "USD", "notes": "Two nights near clinic", "cancelled": False},
            {"id": "BK-007", "travel_request_id": "TR-007", "booking_type": "flight", "provider": "Alaska Airlines", "confirmation_number": "AS-44782", "departure_date": now + timedelta(days=5), "return_date": now + timedelta(days=8), "cost": 380.0, "currency": "USD", "notes": "PDX to SEA round-trip", "cancelled": False},
            {"id": "BK-008", "travel_request_id": "TR-007", "booking_type": "extended_stay", "provider": "Residence Inn Seattle", "confirmation_number": "RI-12098", "departure_date": now + timedelta(days=5), "return_date": now + timedelta(days=8), "cost": 750.0, "currency": "USD", "notes": "3-night extended stay, kitchenette", "cancelled": False},
            {"id": "BK-009", "travel_request_id": "TR-009", "booking_type": "medical_transport", "provider": "MedFlight Services", "confirmation_number": "MFS-20198", "departure_date": now - timedelta(days=50), "return_date": now - timedelta(days=46), "cost": 1800.0, "currency": "USD", "notes": "Medical transport with IV support, Dallas to Houston", "cancelled": False},
            {"id": "BK-010", "travel_request_id": "TR-009", "booking_type": "patient_housing", "provider": "MD Anderson Patient Housing", "confirmation_number": "MDAPH-7721", "departure_date": now - timedelta(days=50), "return_date": now - timedelta(days=46), "cost": 600.0, "currency": "USD", "notes": "4 nights in patient housing facility", "cancelled": False},
        ]

        for b in bookings_data:
            self._bookings[b["id"]] = TravelBooking(**b)

        # --- 10 Travel Reimbursements ---
        reimbursements_data = [
            {"id": "RE-001", "travel_request_id": "TR-002", "patient_id": "PT-1002", "expense_type": "transport", "amount": 115.0, "currency": "USD", "receipt_provided": True, "status": ReimbursementStatus.PAID, "submitted_date": now - timedelta(days=28), "reviewed_by": "Finance Team - Jane Smith", "reviewed_date": now - timedelta(days=25), "paid_date": now - timedelta(days=20), "payment_method": "direct_deposit", "denial_reason": None},
            {"id": "RE-002", "travel_request_id": "TR-001", "patient_id": "PT-1001", "expense_type": "meals", "amount": 45.0, "currency": "USD", "receipt_provided": True, "status": ReimbursementStatus.PAID, "submitted_date": now - timedelta(days=58), "reviewed_by": "Finance Team - Jane Smith", "reviewed_date": now - timedelta(days=55), "paid_date": now - timedelta(days=50), "payment_method": "check", "denial_reason": None},
            {"id": "RE-003", "travel_request_id": "TR-003", "patient_id": "PT-1003", "expense_type": "transport", "amount": 89.0, "currency": "USD", "receipt_provided": True, "status": ReimbursementStatus.APPROVED, "submitted_date": now - timedelta(days=13), "reviewed_by": "Finance Team - Mark Davis", "reviewed_date": now - timedelta(days=10), "paid_date": None, "payment_method": None, "denial_reason": None},
            {"id": "RE-004", "travel_request_id": "TR-005", "patient_id": "PT-2001", "expense_type": "parking", "amount": 35.0, "currency": "USD", "receipt_provided": False, "status": ReimbursementStatus.DENIED, "submitted_date": now - timedelta(days=88), "reviewed_by": "Finance Team - Mark Davis", "reviewed_date": now - timedelta(days=85), "paid_date": None, "payment_method": None, "denial_reason": "No receipt provided for parking expense"},
            {"id": "RE-005", "travel_request_id": "TR-006", "patient_id": "PT-2002", "expense_type": "transport", "amount": 520.0, "currency": "USD", "receipt_provided": True, "status": ReimbursementStatus.PENDING, "submitted_date": now - timedelta(days=5), "reviewed_by": None, "reviewed_date": None, "paid_date": None, "payment_method": None, "denial_reason": None},
            {"id": "RE-006", "travel_request_id": "TR-006", "patient_id": "PT-2002", "expense_type": "accommodation", "amount": 400.0, "currency": "USD", "receipt_provided": True, "status": ReimbursementStatus.PENDING, "submitted_date": now - timedelta(days=5), "reviewed_by": None, "reviewed_date": None, "paid_date": None, "payment_method": None, "denial_reason": None},
            {"id": "RE-007", "travel_request_id": "TR-009", "patient_id": "PT-3001", "expense_type": "transport", "amount": 1800.0, "currency": "USD", "receipt_provided": True, "status": ReimbursementStatus.PAID, "submitted_date": now - timedelta(days=45), "reviewed_by": "Finance Team - Lisa Wang", "reviewed_date": now - timedelta(days=42), "paid_date": now - timedelta(days=38), "payment_method": "wire_transfer", "denial_reason": None},
            {"id": "RE-008", "travel_request_id": "TR-009", "patient_id": "PT-3001", "expense_type": "meals", "amount": 120.0, "currency": "USD", "receipt_provided": True, "status": ReimbursementStatus.PAID, "submitted_date": now - timedelta(days=45), "reviewed_by": "Finance Team - Lisa Wang", "reviewed_date": now - timedelta(days=42), "paid_date": now - timedelta(days=38), "payment_method": "wire_transfer", "denial_reason": None},
            {"id": "RE-009", "travel_request_id": "TR-010", "patient_id": "PT-3002", "expense_type": "transport", "amount": 185.0, "currency": "USD", "receipt_provided": True, "status": ReimbursementStatus.UNDER_REVIEW, "submitted_date": now - timedelta(days=18), "reviewed_by": "Finance Team - Lisa Wang", "reviewed_date": None, "paid_date": None, "payment_method": None, "denial_reason": None},
            {"id": "RE-010", "travel_request_id": "TR-010", "patient_id": "PT-3002", "expense_type": "accommodation", "amount": 280.0, "currency": "USD", "receipt_provided": True, "status": ReimbursementStatus.UNDER_REVIEW, "submitted_date": now - timedelta(days=18), "reviewed_by": "Finance Team - Lisa Wang", "reviewed_date": None, "paid_date": None, "payment_method": None, "denial_reason": None},
        ]

        for r in reimbursements_data:
            self._reimbursements[r["id"]] = TravelReimbursement(**r)

    # ------------------------------------------------------------------
    # Travel Request Management
    # ------------------------------------------------------------------

    def list_travel_requests(
        self,
        *,
        trial_id: str | None = None,
        status: TravelRequestStatus | None = None,
        patient_id: str | None = None,
    ) -> list[TravelRequest]:
        """List travel requests with optional filters."""
        with self._lock:
            result = list(self._travel_requests.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if status is not None:
            result = [r for r in result if r.status == status]
        if patient_id is not None:
            result = [r for r in result if r.patient_id == patient_id]

        return sorted(result, key=lambda r: r.created_at, reverse=True)

    def get_travel_request(self, request_id: str) -> TravelRequest | None:
        """Get a single travel request by ID."""
        with self._lock:
            return self._travel_requests.get(request_id)

    def create_travel_request(self, payload: TravelRequestCreate) -> TravelRequest:
        """Create a new travel request."""
        now = datetime.now(timezone.utc)
        request_id = f"TR-{uuid4().hex[:8].upper()}"
        travel_request = TravelRequest(
            id=request_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            patient_id=payload.patient_id,
            traveler_type=payload.traveler_type,
            visit_type=payload.visit_type,
            visit_date=payload.visit_date,
            origin_city=payload.origin_city,
            origin_country=payload.origin_country,
            destination_city=payload.destination_city,
            destination_country=payload.destination_country,
            transport_mode=payload.transport_mode,
            accommodation_type=payload.accommodation_type,
            accommodation_nights=payload.accommodation_nights,
            special_needs=payload.special_needs,
            status=TravelRequestStatus.REQUESTED,
            estimated_cost=payload.estimated_cost,
            actual_cost=None,
            approved_by=None,
            approved_date=None,
            booking_reference=None,
            created_at=now,
        )
        with self._lock:
            self._travel_requests[request_id] = travel_request
        logger.info(
            "Created travel request %s: trial=%s patient=%s",
            request_id, payload.trial_id, payload.patient_id,
        )
        return travel_request

    def update_travel_request(
        self, request_id: str, payload: TravelRequestUpdate
    ) -> TravelRequest | None:
        """Update an existing travel request."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._travel_requests.get(request_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set approved_date when approved_by is set
            if "approved_by" in updates and updates["approved_by"] is not None:
                if existing.approved_by is None:
                    updates["approved_date"] = now

            # Auto-set status to approved when approved_by is provided
            if "status" in updates and updates["status"] == TravelRequestStatus.APPROVED:
                if "approved_date" not in updates:
                    updates["approved_date"] = now

            data.update(updates)
            updated = TravelRequest(**data)
            self._travel_requests[request_id] = updated
        return updated

    def delete_travel_request(self, request_id: str) -> bool:
        """Delete a travel request. Returns True if deleted."""
        with self._lock:
            if request_id in self._travel_requests:
                del self._travel_requests[request_id]
                return True
            return False

    def approve_travel_request(
        self, request_id: str, approved_by: str
    ) -> TravelRequest | None:
        """Approve a travel request."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._travel_requests.get(request_id)
            if existing is None:
                return None
            data = existing.model_dump()
            data["status"] = TravelRequestStatus.APPROVED
            data["approved_by"] = approved_by
            data["approved_date"] = now
            updated = TravelRequest(**data)
            self._travel_requests[request_id] = updated
        logger.info("Approved travel request %s by %s", request_id, approved_by)
        return updated

    # ------------------------------------------------------------------
    # Booking Management
    # ------------------------------------------------------------------

    def list_bookings(
        self,
        *,
        travel_request_id: str | None = None,
    ) -> list[TravelBooking]:
        """List bookings with optional filter by travel request."""
        with self._lock:
            result = list(self._bookings.values())

        if travel_request_id is not None:
            result = [b for b in result if b.travel_request_id == travel_request_id]

        return sorted(result, key=lambda b: b.departure_date, reverse=True)

    def get_booking(self, booking_id: str) -> TravelBooking | None:
        """Get a single booking by ID."""
        with self._lock:
            return self._bookings.get(booking_id)

    def create_booking(self, payload: TravelBookingCreate) -> TravelBooking:
        """Create a new booking."""
        booking_id = f"BK-{uuid4().hex[:8].upper()}"
        booking = TravelBooking(
            id=booking_id,
            travel_request_id=payload.travel_request_id,
            booking_type=payload.booking_type,
            provider=payload.provider,
            confirmation_number=payload.confirmation_number,
            departure_date=payload.departure_date,
            return_date=payload.return_date,
            cost=payload.cost,
            currency=payload.currency,
            notes=payload.notes,
            cancelled=False,
        )
        with self._lock:
            self._bookings[booking_id] = booking
        logger.info(
            "Created booking %s for travel request %s",
            booking_id, payload.travel_request_id,
        )
        return booking

    def update_booking(
        self, booking_id: str, payload: TravelBookingUpdate
    ) -> TravelBooking | None:
        """Update an existing booking."""
        with self._lock:
            existing = self._bookings.get(booking_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = TravelBooking(**data)
            self._bookings[booking_id] = updated
        return updated

    def delete_booking(self, booking_id: str) -> bool:
        """Delete a booking. Returns True if deleted."""
        with self._lock:
            if booking_id in self._bookings:
                del self._bookings[booking_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Reimbursement Management
    # ------------------------------------------------------------------

    def list_reimbursements(
        self,
        *,
        travel_request_id: str | None = None,
        patient_id: str | None = None,
        status: ReimbursementStatus | None = None,
    ) -> list[TravelReimbursement]:
        """List reimbursements with optional filters."""
        with self._lock:
            result = list(self._reimbursements.values())

        if travel_request_id is not None:
            result = [r for r in result if r.travel_request_id == travel_request_id]
        if patient_id is not None:
            result = [r for r in result if r.patient_id == patient_id]
        if status is not None:
            result = [r for r in result if r.status == status]

        return sorted(result, key=lambda r: r.submitted_date, reverse=True)

    def get_reimbursement(self, reimbursement_id: str) -> TravelReimbursement | None:
        """Get a single reimbursement by ID."""
        with self._lock:
            return self._reimbursements.get(reimbursement_id)

    def create_reimbursement(self, payload: TravelReimbursementCreate) -> TravelReimbursement:
        """Create a new reimbursement."""
        now = datetime.now(timezone.utc)
        reimbursement_id = f"RE-{uuid4().hex[:8].upper()}"
        reimbursement = TravelReimbursement(
            id=reimbursement_id,
            travel_request_id=payload.travel_request_id,
            patient_id=payload.patient_id,
            expense_type=payload.expense_type,
            amount=payload.amount,
            currency=payload.currency,
            receipt_provided=payload.receipt_provided,
            status=ReimbursementStatus.PENDING,
            submitted_date=now,
            reviewed_by=None,
            reviewed_date=None,
            paid_date=None,
            payment_method=None,
            denial_reason=None,
        )
        with self._lock:
            self._reimbursements[reimbursement_id] = reimbursement
        logger.info(
            "Created reimbursement %s for travel request %s",
            reimbursement_id, payload.travel_request_id,
        )
        return reimbursement

    def update_reimbursement(
        self, reimbursement_id: str, payload: TravelReimbursementUpdate
    ) -> TravelReimbursement | None:
        """Update an existing reimbursement."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._reimbursements.get(reimbursement_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set reviewed_date when reviewed_by is set
            if "reviewed_by" in updates and updates["reviewed_by"] is not None:
                if existing.reviewed_by is None:
                    updates["reviewed_date"] = now

            # Auto-set paid_date when status changes to paid
            if "status" in updates and updates["status"] == ReimbursementStatus.PAID:
                if existing.status != ReimbursementStatus.PAID:
                    updates["paid_date"] = now

            data.update(updates)
            updated = TravelReimbursement(**data)
            self._reimbursements[reimbursement_id] = updated
        return updated

    def delete_reimbursement(self, reimbursement_id: str) -> bool:
        """Delete a reimbursement. Returns True if deleted."""
        with self._lock:
            if reimbursement_id in self._reimbursements:
                del self._reimbursements[reimbursement_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> PatientTravelMetrics:
        """Compute aggregated patient travel metrics."""
        with self._lock:
            requests = list(self._travel_requests.values())
            bookings = list(self._bookings.values())
            reimbursements = list(self._reimbursements.values())

        if trial_id is not None:
            requests = [r for r in requests if r.trial_id == trial_id]
            # Filter bookings by travel requests in this trial
            request_ids = {r.id for r in requests}
            bookings = [b for b in bookings if b.travel_request_id in request_ids]
            reimbursements = [
                r for r in reimbursements
                if r.travel_request_id in request_ids
            ]

        # Requests by status
        requests_by_status: dict[str, int] = {}
        for r in requests:
            key = r.status.value
            requests_by_status[key] = requests_by_status.get(key, 0) + 1

        # Requests by transport mode
        requests_by_transport: dict[str, int] = {}
        for r in requests:
            key = r.transport_mode.value
            requests_by_transport[key] = requests_by_transport.get(key, 0) + 1

        # Booking stats
        active_bookings = sum(1 for b in bookings if not b.cancelled)
        cancelled_bookings = sum(1 for b in bookings if b.cancelled)

        # Reimbursement stats
        reimbursements_by_status: dict[str, int] = {}
        for r in reimbursements:
            key = r.status.value
            reimbursements_by_status[key] = reimbursements_by_status.get(key, 0) + 1

        total_reimbursement_amount = sum(r.amount for r in reimbursements)
        pending_reimbursement_amount = sum(
            r.amount for r in reimbursements
            if r.status in (ReimbursementStatus.PENDING, ReimbursementStatus.UNDER_REVIEW)
        )

        # Cost stats
        total_travel_cost = sum(
            r.actual_cost for r in requests if r.actual_cost is not None
        )
        completed_requests = [
            r for r in requests
            if r.actual_cost is not None
        ]
        avg_cost_per_visit = (
            round(total_travel_cost / len(completed_requests), 2)
            if completed_requests else 0.0
        )

        # Traveler counts
        patient_ids = set()
        caregiver_ids = set()
        for r in requests:
            if r.traveler_type == TravelerType.PATIENT:
                patient_ids.add(r.patient_id)
            else:
                caregiver_ids.add(r.patient_id)

        return PatientTravelMetrics(
            total_requests=len(requests),
            requests_by_status=requests_by_status,
            requests_by_transport=requests_by_transport,
            total_bookings=len(bookings),
            active_bookings=active_bookings,
            cancelled_bookings=cancelled_bookings,
            total_reimbursements=len(reimbursements),
            reimbursements_by_status=reimbursements_by_status,
            total_reimbursement_amount=total_reimbursement_amount,
            pending_reimbursement_amount=pending_reimbursement_amount,
            total_travel_cost=total_travel_cost,
            avg_cost_per_visit=avg_cost_per_visit,
            total_patients_traveled=len(patient_ids),
            total_caregivers_traveled=len(caregiver_ids),
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: PatientTravelService | None = None
_instance_lock = threading.Lock()


def get_patient_travel_service() -> PatientTravelService:
    """Return the singleton PatientTravelService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = PatientTravelService()
    return _instance


def reset_patient_travel_service() -> PatientTravelService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = PatientTravelService()
    return _instance
