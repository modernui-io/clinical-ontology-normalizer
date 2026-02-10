"""Patient Travel & Logistics Management API endpoints (OPS-TRAVEL).

Provides comprehensive patient travel operations: travel request management,
booking coordination, reimbursement processing, accommodation arrangements,
transportation mode selection, caregiver travel support, approval workflows,
and travel metrics.

Endpoints:
    GET    /patient-travel/requests                              - List travel requests
    GET    /patient-travel/requests/{request_id}                 - Get single travel request
    POST   /patient-travel/requests                              - Create travel request
    PUT    /patient-travel/requests/{request_id}                 - Update travel request
    DELETE /patient-travel/requests/{request_id}                 - Delete travel request
    POST   /patient-travel/requests/{request_id}/approve         - Approve travel request
    GET    /patient-travel/bookings                              - List bookings
    GET    /patient-travel/bookings/{booking_id}                 - Get single booking
    POST   /patient-travel/bookings                              - Create booking
    PUT    /patient-travel/bookings/{booking_id}                 - Update booking
    DELETE /patient-travel/bookings/{booking_id}                 - Delete booking
    GET    /patient-travel/reimbursements                        - List reimbursements
    GET    /patient-travel/reimbursements/{reimbursement_id}     - Get single reimbursement
    POST   /patient-travel/reimbursements                        - Create reimbursement
    PUT    /patient-travel/reimbursements/{reimbursement_id}     - Update reimbursement
    DELETE /patient-travel/reimbursements/{reimbursement_id}     - Delete reimbursement
    GET    /patient-travel/metrics                               - Travel metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.patient_travel import (
    PatientTravelMetrics,
    ReimbursementStatus,
    TravelBooking,
    TravelBookingCreate,
    TravelBookingListResponse,
    TravelBookingUpdate,
    TravelReimbursement,
    TravelReimbursementCreate,
    TravelReimbursementListResponse,
    TravelReimbursementUpdate,
    TravelRequest,
    TravelRequestCreate,
    TravelRequestListResponse,
    TravelRequestStatus,
    TravelRequestUpdate,
)
from app.services.patient_travel_service import get_patient_travel_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/patient-travel",
    tags=["Patient Travel"],
)


# ---------------------------------------------------------------------------
# Travel Request Management
# ---------------------------------------------------------------------------


@router.get(
    "/requests",
    response_model=TravelRequestListResponse,
    summary="List travel requests",
    description="Retrieve travel requests with optional filtering by trial, status, and patient.",
)
async def list_travel_requests(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[TravelRequestStatus] = Query(None, description="Filter by status"),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
) -> TravelRequestListResponse:
    svc = get_patient_travel_service()
    items = svc.list_travel_requests(
        trial_id=trial_id, status=status, patient_id=patient_id,
    )
    return TravelRequestListResponse(items=items, total=len(items))


@router.get(
    "/requests/{request_id}",
    response_model=TravelRequest,
    summary="Get a travel request",
)
async def get_travel_request(request_id: str) -> TravelRequest:
    svc = get_patient_travel_service()
    travel_request = svc.get_travel_request(request_id)
    if travel_request is None:
        raise HTTPException(status_code=404, detail=f"Travel request '{request_id}' not found")
    return travel_request


@router.post(
    "/requests",
    response_model=TravelRequest,
    status_code=201,
    summary="Create a travel request",
)
async def create_travel_request(payload: TravelRequestCreate) -> TravelRequest:
    svc = get_patient_travel_service()
    return svc.create_travel_request(payload)


@router.put(
    "/requests/{request_id}",
    response_model=TravelRequest,
    summary="Update a travel request",
)
async def update_travel_request(
    request_id: str, payload: TravelRequestUpdate
) -> TravelRequest:
    svc = get_patient_travel_service()
    updated = svc.update_travel_request(request_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Travel request '{request_id}' not found")
    return updated


@router.delete(
    "/requests/{request_id}",
    status_code=204,
    summary="Delete a travel request",
)
async def delete_travel_request(request_id: str) -> None:
    svc = get_patient_travel_service()
    deleted = svc.delete_travel_request(request_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Travel request '{request_id}' not found")


@router.post(
    "/requests/{request_id}/approve",
    response_model=TravelRequest,
    summary="Approve a travel request",
    description="Approve a pending travel request. Sets status to approved with approver info.",
)
async def approve_travel_request(
    request_id: str,
    approved_by: str = Query(..., description="Name of the approver"),
) -> TravelRequest:
    svc = get_patient_travel_service()
    result = svc.approve_travel_request(request_id, approved_by)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Travel request '{request_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Booking Management
# ---------------------------------------------------------------------------


@router.get(
    "/bookings",
    response_model=TravelBookingListResponse,
    summary="List travel bookings",
    description="Retrieve travel bookings with optional filtering by travel request.",
)
async def list_bookings(
    travel_request_id: Optional[str] = Query(None, description="Filter by travel request ID"),
) -> TravelBookingListResponse:
    svc = get_patient_travel_service()
    items = svc.list_bookings(travel_request_id=travel_request_id)
    return TravelBookingListResponse(items=items, total=len(items))


@router.get(
    "/bookings/{booking_id}",
    response_model=TravelBooking,
    summary="Get a travel booking",
)
async def get_booking(booking_id: str) -> TravelBooking:
    svc = get_patient_travel_service()
    booking = svc.get_booking(booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail=f"Booking '{booking_id}' not found")
    return booking


@router.post(
    "/bookings",
    response_model=TravelBooking,
    status_code=201,
    summary="Create a travel booking",
)
async def create_booking(payload: TravelBookingCreate) -> TravelBooking:
    svc = get_patient_travel_service()
    return svc.create_booking(payload)


@router.put(
    "/bookings/{booking_id}",
    response_model=TravelBooking,
    summary="Update a travel booking",
)
async def update_booking(
    booking_id: str, payload: TravelBookingUpdate
) -> TravelBooking:
    svc = get_patient_travel_service()
    updated = svc.update_booking(booking_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Booking '{booking_id}' not found")
    return updated


@router.delete(
    "/bookings/{booking_id}",
    status_code=204,
    summary="Delete a travel booking",
)
async def delete_booking(booking_id: str) -> None:
    svc = get_patient_travel_service()
    deleted = svc.delete_booking(booking_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Booking '{booking_id}' not found")


# ---------------------------------------------------------------------------
# Reimbursement Management
# ---------------------------------------------------------------------------


@router.get(
    "/reimbursements",
    response_model=TravelReimbursementListResponse,
    summary="List travel reimbursements",
    description="Retrieve travel reimbursements with optional filtering by travel request, patient, and status.",
)
async def list_reimbursements(
    travel_request_id: Optional[str] = Query(None, description="Filter by travel request ID"),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    status: Optional[ReimbursementStatus] = Query(None, description="Filter by status"),
) -> TravelReimbursementListResponse:
    svc = get_patient_travel_service()
    items = svc.list_reimbursements(
        travel_request_id=travel_request_id, patient_id=patient_id, status=status,
    )
    return TravelReimbursementListResponse(items=items, total=len(items))


@router.get(
    "/reimbursements/{reimbursement_id}",
    response_model=TravelReimbursement,
    summary="Get a travel reimbursement",
)
async def get_reimbursement(reimbursement_id: str) -> TravelReimbursement:
    svc = get_patient_travel_service()
    reimbursement = svc.get_reimbursement(reimbursement_id)
    if reimbursement is None:
        raise HTTPException(status_code=404, detail=f"Reimbursement '{reimbursement_id}' not found")
    return reimbursement


@router.post(
    "/reimbursements",
    response_model=TravelReimbursement,
    status_code=201,
    summary="Create a travel reimbursement",
)
async def create_reimbursement(payload: TravelReimbursementCreate) -> TravelReimbursement:
    svc = get_patient_travel_service()
    return svc.create_reimbursement(payload)


@router.put(
    "/reimbursements/{reimbursement_id}",
    response_model=TravelReimbursement,
    summary="Update a travel reimbursement",
)
async def update_reimbursement(
    reimbursement_id: str, payload: TravelReimbursementUpdate
) -> TravelReimbursement:
    svc = get_patient_travel_service()
    updated = svc.update_reimbursement(reimbursement_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Reimbursement '{reimbursement_id}' not found")
    return updated


@router.delete(
    "/reimbursements/{reimbursement_id}",
    status_code=204,
    summary="Delete a travel reimbursement",
)
async def delete_reimbursement(reimbursement_id: str) -> None:
    svc = get_patient_travel_service()
    deleted = svc.delete_reimbursement(reimbursement_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Reimbursement '{reimbursement_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=PatientTravelMetrics,
    summary="Get patient travel metrics",
    description="Aggregated patient travel metrics including request counts, booking stats, "
                "reimbursement totals, cost analysis, and traveler demographics.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter metrics by trial ID"),
) -> PatientTravelMetrics:
    svc = get_patient_travel_service()
    return svc.get_metrics(trial_id=trial_id)
