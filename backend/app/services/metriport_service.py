"""Metriport Medical API Client.

Async client for the Metriport Medical API v1. Handles:
    - Organization & facility management
    - Patient creation and matching
    - Document query initiation
    - Consolidated data query
    - Downloading FHIR Bundles from pre-signed S3 URLs

API Reference: https://docs.metriport.com/medical-api
Base URLs:
    - Production: https://api.metriport.com
    - Sandbox:    https://api.sandbox.metriport.com
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Metriport API version prefix
_API_PREFIX = "/medical/v1"


class MetriportError(Exception):
    """Base error for Metriport API operations."""

    def __init__(self, message: str, status_code: int | None = None, detail: Any = None):
        self.status_code = status_code
        self.detail = detail
        super().__init__(message)


class MetriportService:
    """Async client for Metriport Medical API.

    Usage::

        async with MetriportService() as mp:
            patient = await mp.create_patient(facility_id, {...})
            await mp.start_document_query(patient["id"], facility_id)
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
    ):
        self._api_key = api_key or settings.metriport_api_key
        self._base_url = (base_url or settings.metriport_base_url).rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=f"{self._base_url}{_API_PREFIX}",
            headers={
                "x-api-key": self._api_key or "",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    async def __aenter__(self) -> MetriportService:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated request to Metriport API."""
        if not self._api_key:
            raise MetriportError("Metriport API key not configured")

        try:
            resp = await self._client.request(
                method, path, params=params, json=json_body
            )
        except httpx.HTTPError as e:
            raise MetriportError(f"Metriport request failed: {e}") from e

        if resp.status_code >= 400:
            detail = resp.text
            try:
                detail = resp.json()
            except Exception:
                pass
            raise MetriportError(
                f"Metriport API error {resp.status_code}: {detail}",
                status_code=resp.status_code,
                detail=detail,
            )
        if resp.status_code == 204:
            return {}
        return resp.json()

    # ------------------------------------------------------------------
    # Organization
    # ------------------------------------------------------------------

    async def get_organization(self) -> dict[str, Any]:
        """Get current organization details."""
        return await self._request("GET", "/organization")

    async def create_organization(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new organization.

        Args:
            data: Organization data with name, type, location.
        """
        return await self._request("POST", "/organization", json_body=data)

    # ------------------------------------------------------------------
    # Facility
    # ------------------------------------------------------------------

    async def get_facility(self, facility_id: str) -> dict[str, Any]:
        """Get facility details."""
        return await self._request("GET", f"/facility/{facility_id}")

    async def list_facilities(self) -> list[dict[str, Any]]:
        """List all facilities."""
        result = await self._request("GET", "/facility")
        return result if isinstance(result, list) else result.get("facilities", [])

    async def create_facility(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new facility.

        Args:
            data: Facility data with name, npi, tin, active, address.
        """
        return await self._request("POST", "/facility", json_body=data)

    # ------------------------------------------------------------------
    # Patient
    # ------------------------------------------------------------------

    async def create_patient(
        self,
        facility_id: str,
        patient_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Create or match a patient in Metriport.

        Args:
            facility_id: UUID of the facility.
            patient_data: Patient demographics (firstName, lastName, dob, genderAtBirth,
                         address, contact, personalIdentifiers, externalId).

        Returns:
            Patient object with id, externalId, etc.
        """
        return await self._request(
            "POST",
            "/patient",
            params={"facilityId": facility_id},
            json_body=patient_data,
        )

    async def get_patient(self, patient_id: str, facility_id: str) -> dict[str, Any]:
        """Get patient details."""
        return await self._request(
            "GET",
            f"/patient/{patient_id}",
            params={"facilityId": facility_id},
        )

    async def list_patients(self, facility_id: str) -> list[dict[str, Any]]:
        """List all patients for a facility."""
        result = await self._request(
            "GET", "/patient", params={"facilityId": facility_id}
        )
        return result if isinstance(result, list) else result.get("patients", [])

    async def delete_patient(self, patient_id: str, facility_id: str) -> None:
        """Delete a patient."""
        await self._request(
            "DELETE",
            f"/patient/{patient_id}",
            params={"facilityId": facility_id},
        )

    # ------------------------------------------------------------------
    # Document Query
    # ------------------------------------------------------------------

    async def start_document_query(
        self,
        patient_id: str,
        facility_id: str,
    ) -> dict[str, Any]:
        """Start a document query across HIE networks.

        Triggers queries to Carequality, CommonWell, and eHealth Exchange.
        Results arrive via webhooks (document-download, document-conversion).

        Args:
            patient_id: Metriport patient UUID.
            facility_id: Facility UUID for the query context.

        Returns:
            Query status with requestId.
        """
        return await self._request(
            "POST",
            f"/document/query",
            params={"patientId": patient_id, "facilityId": facility_id},
        )

    async def list_documents(
        self,
        patient_id: str,
        facility_id: str,
    ) -> list[dict[str, Any]]:
        """List all documents for a patient."""
        result = await self._request(
            "GET",
            f"/document",
            params={"patientId": patient_id, "facilityId": facility_id},
        )
        return result if isinstance(result, list) else result.get("documents", [])

    # ------------------------------------------------------------------
    # Consolidated Data (FHIR Bundle)
    # ------------------------------------------------------------------

    async def start_consolidated_query(
        self,
        patient_id: str,
        resources: list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        conversion_type: str = "json",
    ) -> dict[str, Any]:
        """Start a consolidated data query for a patient.

        Triggers compilation of all patient data into a single FHIR Bundle.
        Result arrives via webhook (medical.consolidated-data).

        Args:
            patient_id: Metriport patient UUID.
            resources: Optional list of FHIR resource types to include
                      (e.g., ["Condition", "MedicationRequest", "Observation"]).
                      If None/empty, all resource types are returned.
            date_from: Start date filter (YYYY-MM-DD).
            date_to: End date filter (YYYY-MM-DD).
            conversion_type: "json" for FHIR JSON, "pdf" for PDF, "html" for HTML.

        Returns:
            Query status with requestId.
        """
        params: dict[str, Any] = {"conversionType": conversion_type}
        if resources:
            params["resources"] = ",".join(resources)
        if date_from:
            params["dateFrom"] = date_from
        if date_to:
            params["dateTo"] = date_to

        return await self._request(
            "POST", f"/patient/{patient_id}/consolidated/query", params=params
        )

    async def get_consolidated_count(self, patient_id: str) -> dict[str, Any]:
        """Get count of consolidated data resources for a patient."""
        return await self._request(
            "GET",
            "/patient/consolidated/count",
            params={"patientId": patient_id},
        )

    # ------------------------------------------------------------------
    # Download Bundle from S3 URL
    # ------------------------------------------------------------------

    async def download_bundle_from_url(self, url: str) -> dict[str, Any]:
        """Download a FHIR Bundle from a pre-signed S3 URL.

        Metriport consolidated-data webhooks include a Bundle with
        DocumentReference resources containing pre-signed S3 URLs
        (valid for ~3 minutes). This method downloads the actual
        FHIR Bundle from that URL.

        Args:
            url: Pre-signed S3 URL from the DocumentReference.

        Returns:
            The FHIR Bundle as a dict.
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as e:
                raise MetriportError(
                    f"Failed to download bundle from S3: {e.response.status_code}",
                    status_code=e.response.status_code,
                ) from e
            except Exception as e:
                raise MetriportError(f"Failed to download bundle: {e}") from e

    # ------------------------------------------------------------------
    # Convenience: Full patient onboarding flow
    # ------------------------------------------------------------------

    async def onboard_patient_and_query(
        self,
        facility_id: str,
        patient_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Create patient and immediately start document + consolidated queries.

        Convenience method for the common flow:
        1. Create/match patient
        2. Start document query (HIE network)
        3. Start consolidated data query

        Results arrive asynchronously via webhooks.

        Returns:
            Dict with patient info and query request IDs.
        """
        patient = await self.create_patient(facility_id, patient_data)
        patient_id = patient["id"]

        doc_query = await self.start_document_query(patient_id, facility_id)
        consolidated = await self.start_consolidated_query(patient_id)

        return {
            "patient": patient,
            "document_query": doc_query,
            "consolidated_query": consolidated,
        }
