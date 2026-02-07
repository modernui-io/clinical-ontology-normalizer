"""Metriport Medical API Endpoints.

Management endpoints for interacting with the Metriport Medical API:
    - Patient registration and lookup
    - Document query initiation
    - Consolidated data query
    - Facility management
    - Integration status

These endpoints proxy through to Metriport's API and provide
a simplified interface for the clinical trial recruitment workflow.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.metriport_service import MetriportError, MetriportService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metriport", tags=["Metriport Integration"])


# ==============================================================================
# Request/Response Models
# ==============================================================================


class PatientAddress(BaseModel):
    """Patient address for Metriport."""

    addressLine1: str
    addressLine2: str | None = None
    city: str
    state: str
    zip: str
    country: str = "US"


class PatientContact(BaseModel):
    """Patient contact info."""

    phone: str | None = None
    email: str | None = None


class CreatePatientRequest(BaseModel):
    """Request to create a patient in Metriport."""

    firstName: str
    lastName: str
    dob: str = Field(..., description="Date of birth (YYYY-MM-DD)")
    genderAtBirth: str = Field(..., description="M or F")
    address: list[PatientAddress]
    contact: PatientContact | None = None
    externalId: str | None = Field(
        None, description="Your internal patient ID for correlation"
    )
    facility_id: str | None = Field(
        None, description="Override facility ID (uses default if not provided)"
    )


class PatientResponse(BaseModel):
    """Metriport patient response."""

    id: str
    externalId: str | None = None
    firstName: str | None = None
    lastName: str | None = None
    dob: str | None = None
    genderAtBirth: str | None = None
    facilityIds: list[str] | None = None


class DocumentQueryRequest(BaseModel):
    """Request to start a document query."""

    patient_id: str = Field(..., description="Metriport patient UUID")
    facility_id: str | None = Field(
        None, description="Override facility ID (uses default if not provided)"
    )


class ConsolidatedQueryRequest(BaseModel):
    """Request to start a consolidated data query."""

    patient_id: str = Field(..., description="Metriport patient UUID")
    resources: list[str] | None = Field(
        None,
        description="FHIR resource types to include (e.g., Condition, Observation)",
    )
    date_from: str | None = Field(None, description="Start date filter (YYYY-MM-DD)")
    date_to: str | None = Field(None, description="End date filter (YYYY-MM-DD)")


class OnboardPatientRequest(BaseModel):
    """Request to onboard a patient and immediately query HIE networks."""

    firstName: str
    lastName: str
    dob: str = Field(..., description="Date of birth (YYYY-MM-DD)")
    genderAtBirth: str = Field(..., description="M or F")
    address: list[PatientAddress]
    contact: PatientContact | None = None
    externalId: str | None = None
    facility_id: str | None = None


class IntegrationStatusResponse(BaseModel):
    """Metriport integration status."""

    configured: bool
    api_key_set: bool
    webhook_key_set: bool
    facility_id_set: bool
    base_url: str
    organization: dict[str, Any] | None = None
    facilities: list[dict[str, Any]] | None = None


class QueryResponse(BaseModel):
    """Generic query response."""

    status: str = "ok"
    message: str = ""
    data: dict[str, Any] | None = None


# ==============================================================================
# Helper
# ==============================================================================


def _get_facility_id(override: str | None = None) -> str:
    """Get facility ID from override or settings."""
    fid = override or settings.metriport_facility_id
    if not fid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No facility_id provided and METRIPORT_FACILITY_ID not configured",
        )
    return fid


# ==============================================================================
# Integration Status
# ==============================================================================


@router.get(
    "/status",
    response_model=IntegrationStatusResponse,
    summary="Get Metriport integration status",
)
async def get_metriport_status() -> IntegrationStatusResponse:
    """Check Metriport integration configuration and connectivity."""
    resp = IntegrationStatusResponse(
        configured=bool(settings.metriport_api_key),
        api_key_set=bool(settings.metriport_api_key),
        webhook_key_set=bool(settings.metriport_webhook_key),
        facility_id_set=bool(settings.metriport_facility_id),
        base_url=settings.metriport_base_url,
    )

    if settings.metriport_api_key:
        try:
            async with MetriportService() as mp:
                resp.organization = await mp.get_organization()
                resp.facilities = await mp.list_facilities()
        except MetriportError as e:
            logger.warning(f"Metriport connectivity check failed: {e}")
        except Exception as e:
            logger.warning(f"Metriport status check error: {e}")

    return resp


# ==============================================================================
# Patient Endpoints
# ==============================================================================


@router.post(
    "/patients",
    response_model=QueryResponse,
    summary="Create or match a patient in Metriport",
)
async def create_patient(req: CreatePatientRequest) -> QueryResponse:
    """Register a patient with Metriport for HIE network queries.

    This creates the patient in Metriport's system and enables
    document queries across Carequality, CommonWell, and eHealth Exchange.
    """
    facility_id = _get_facility_id(req.facility_id)

    patient_data = req.model_dump(exclude={"facility_id"}, exclude_none=True)

    try:
        async with MetriportService() as mp:
            result = await mp.create_patient(facility_id, patient_data)
            return QueryResponse(
                status="ok",
                message=f"Patient created: {result.get('id', 'unknown')}",
                data=result,
            )
    except MetriportError as e:
        raise HTTPException(
            status_code=e.status_code or 500,
            detail=str(e),
        )


@router.get(
    "/patients",
    response_model=QueryResponse,
    summary="List patients in Metriport",
)
async def list_patients(facility_id: str | None = None) -> QueryResponse:
    """List all patients registered with Metriport for a facility."""
    fid = _get_facility_id(facility_id)

    try:
        async with MetriportService() as mp:
            patients = await mp.list_patients(fid)
            return QueryResponse(
                status="ok",
                message=f"Found {len(patients)} patient(s)",
                data={"patients": patients, "total": len(patients)},
            )
    except MetriportError as e:
        raise HTTPException(
            status_code=e.status_code or 500,
            detail=str(e),
        )


@router.get(
    "/patients/{patient_id}",
    response_model=QueryResponse,
    summary="Get a Metriport patient",
)
async def get_patient(patient_id: str, facility_id: str | None = None) -> QueryResponse:
    """Get details for a specific Metriport patient."""
    fid = _get_facility_id(facility_id)

    try:
        async with MetriportService() as mp:
            patient = await mp.get_patient(patient_id, fid)
            return QueryResponse(status="ok", data=patient)
    except MetriportError as e:
        raise HTTPException(
            status_code=e.status_code or 500,
            detail=str(e),
        )


# ==============================================================================
# Document Query Endpoints
# ==============================================================================


@router.post(
    "/documents/query",
    response_model=QueryResponse,
    summary="Start document query across HIE networks",
)
async def start_document_query(req: DocumentQueryRequest) -> QueryResponse:
    """Start a document query for a patient across HIE networks.

    Triggers queries to Carequality, CommonWell, and eHealth Exchange.
    Results arrive asynchronously via webhooks:
    1. medical.document-download — documents found and downloaded
    2. medical.document-conversion — documents converted to FHIR
    3. medical.consolidated-data — all data compiled into FHIR Bundle
    """
    facility_id = _get_facility_id(req.facility_id)

    try:
        async with MetriportService() as mp:
            result = await mp.start_document_query(req.patient_id, facility_id)
            return QueryResponse(
                status="ok",
                message="Document query started. Results will arrive via webhook.",
                data=result,
            )
    except MetriportError as e:
        raise HTTPException(
            status_code=e.status_code or 500,
            detail=str(e),
        )


@router.get(
    "/documents/{patient_id}",
    response_model=QueryResponse,
    summary="List documents for a patient",
)
async def list_documents(
    patient_id: str, facility_id: str | None = None
) -> QueryResponse:
    """List all documents available for a patient."""
    fid = _get_facility_id(facility_id)

    try:
        async with MetriportService() as mp:
            docs = await mp.list_documents(patient_id, fid)
            return QueryResponse(
                status="ok",
                message=f"Found {len(docs)} document(s)",
                data={"documents": docs, "total": len(docs)},
            )
    except MetriportError as e:
        raise HTTPException(
            status_code=e.status_code or 500,
            detail=str(e),
        )


# ==============================================================================
# Consolidated Data Endpoints
# ==============================================================================


@router.post(
    "/consolidated/query",
    response_model=QueryResponse,
    summary="Start consolidated FHIR data query",
)
async def start_consolidated_query(req: ConsolidatedQueryRequest) -> QueryResponse:
    """Start a consolidated data query for a patient.

    Compiles all patient data into a single FHIR Bundle.
    The result arrives via the medical.consolidated-data webhook and
    is automatically imported through the FHIR pipeline.
    """
    try:
        async with MetriportService() as mp:
            result = await mp.start_consolidated_query(
                patient_id=req.patient_id,
                resources=req.resources,
                date_from=req.date_from,
                date_to=req.date_to,
            )
            return QueryResponse(
                status="ok",
                message="Consolidated query started. Results will arrive via webhook.",
                data=result,
            )
    except MetriportError as e:
        raise HTTPException(
            status_code=e.status_code or 500,
            detail=str(e),
        )


@router.get(
    "/consolidated/count/{patient_id}",
    response_model=QueryResponse,
    summary="Get resource count for a patient",
)
async def get_consolidated_count(patient_id: str) -> QueryResponse:
    """Get count of available FHIR resources for a patient."""
    try:
        async with MetriportService() as mp:
            result = await mp.get_consolidated_count(patient_id)
            return QueryResponse(status="ok", data=result)
    except MetriportError as e:
        raise HTTPException(
            status_code=e.status_code or 500,
            detail=str(e),
        )


# ==============================================================================
# Patient Onboarding (Convenience)
# ==============================================================================


@router.post(
    "/onboard",
    response_model=QueryResponse,
    summary="Onboard patient and start HIE queries",
)
async def onboard_patient(req: OnboardPatientRequest) -> QueryResponse:
    """Full patient onboarding: create in Metriport + start all queries.

    Convenience endpoint that:
    1. Creates/matches the patient in Metriport
    2. Starts document query across HIE networks
    3. Starts consolidated FHIR data query

    Results arrive asynchronously via webhooks and are automatically
    processed through the FHIR import pipeline.
    """
    facility_id = _get_facility_id(req.facility_id)

    patient_data = req.model_dump(exclude={"facility_id"}, exclude_none=True)

    try:
        async with MetriportService() as mp:
            result = await mp.onboard_patient_and_query(facility_id, patient_data)
            return QueryResponse(
                status="ok",
                message=(
                    f"Patient {result['patient'].get('id')} onboarded. "
                    f"Document and consolidated queries started."
                ),
                data=result,
            )
    except MetriportError as e:
        raise HTTPException(
            status_code=e.status_code or 500,
            detail=str(e),
        )


# ==============================================================================
# Facility Endpoints
# ==============================================================================


@router.get(
    "/facilities",
    response_model=QueryResponse,
    summary="List Metriport facilities",
)
async def list_facilities() -> QueryResponse:
    """List all facilities configured in Metriport."""
    try:
        async with MetriportService() as mp:
            facilities = await mp.list_facilities()
            return QueryResponse(
                status="ok",
                message=f"Found {len(facilities)} facility/ies",
                data={"facilities": facilities, "total": len(facilities)},
            )
    except MetriportError as e:
        raise HTTPException(
            status_code=e.status_code or 500,
            detail=str(e),
        )
