"""Veeva Vault CDMS Integration Service.

Async client for Veeva Vault CDMS REST API. Handles:
    - Session-based authentication
    - Study listing and metadata retrieval
    - Eligibility criteria import
    - Screening result push
    - Enrollment status sync
    - Subject listing
    - Connection testing

When Vault credentials are not configured, operates in demo mode
with realistic mock data for frontend demonstration.

API Reference: https://developer-cdms.veevavault.com/
Base URL pattern: https://{vault}.veevavault.com/api/v24.3
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Vault CDMS REST API version
_VAULT_API_VERSION = "v24.3"


class VeevaVaultError(Exception):
    """Base error for Veeva Vault CDMS operations."""

    def __init__(self, message: str, status_code: int | None = None, detail: Any = None):
        self.status_code = status_code
        self.detail = detail
        super().__init__(message)


class VeevaVaultService:
    """Async client for Veeva Vault CDMS REST API.

    Usage::

        async with VeevaVaultService() as vault:
            studies = await vault.list_studies()
            study = await vault.import_study("REG-ONCO-3001")

    When credentials are not configured, all methods return demo data.
    """

    def __init__(
        self,
        vault_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout: float = 30.0,
    ):
        self._vault_url = (vault_url or settings.veeva_vault_url).rstrip("/")
        self._username = username or settings.veeva_vault_username
        self._password = password or settings.veeva_vault_password
        self._timeout = timeout
        self._demo_mode = not (self._vault_url and self._username and self._password)
        self._client: httpx.AsyncClient | None = None
        self._session_id: str | None = None

        if self._demo_mode:
            logger.info("Veeva Vault CDMS service running in DEMO mode (no credentials configured)")
        else:
            logger.info("Veeva Vault CDMS service configured for %s", self._vault_url)

    @property
    def demo_mode(self) -> bool:
        return self._demo_mode

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=f"{self._vault_url}/api/{_VAULT_API_VERSION}" if self._vault_url else "",
                timeout=self._timeout,
                headers={"Accept": "application/json"},
            )
        return self._client

    async def __aenter__(self) -> VeevaVaultService:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
        self._session_id = None

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def authenticate(self) -> str:
        """Authenticate with Veeva Vault and obtain a session ID.

        Veeva Vault uses session-based auth: POST /api/v24.3/auth
        with username/password, returns a sessionId.

        Returns:
            Session ID string.
        """
        if self._demo_mode:
            self._session_id = "DEMO-SESSION-ID"
            return self._session_id

        client = await self._get_client()
        start_time = time.perf_counter()
        try:
            resp = await client.post(
                "/auth",
                data={"username": self._username, "password": self._password},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        except httpx.HTTPError as e:
            elapsed = (time.perf_counter() - start_time) * 1000
            logger.error("Vault auth failed (%.1fms): %s", elapsed, e)
            raise VeevaVaultError(f"Vault authentication failed: {e}") from e

        elapsed = (time.perf_counter() - start_time) * 1000
        logger.info("Vault auth -> %d (%.1fms)", resp.status_code, elapsed)

        if resp.status_code >= 400:
            detail = resp.text[:500]
            raise VeevaVaultError(
                f"Vault auth error {resp.status_code}: {detail}",
                status_code=resp.status_code,
                detail=detail,
            )

        data = resp.json()
        self._session_id = data.get("sessionId")
        if not self._session_id:
            raise VeevaVaultError("No sessionId in Vault auth response")

        return self._session_id

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
        content: str | None = None,
        content_type: str | None = None,
    ) -> httpx.Response:
        """Make an authenticated request to Vault CDMS REST API."""
        if self._demo_mode:
            raise VeevaVaultError("Cannot make real API calls in demo mode")

        # Ensure we have a session
        if not self._session_id:
            await self.authenticate()

        client = await self._get_client()
        headers: dict[str, str] = {"Authorization": self._session_id or ""}
        if content_type:
            headers["Content-Type"] = content_type

        start_time = time.perf_counter()
        try:
            resp = await client.request(
                method,
                path,
                params=params,
                json=json_body,
                content=content,
                headers=headers,
            )
        except httpx.HTTPError as e:
            elapsed = (time.perf_counter() - start_time) * 1000
            logger.error(
                "Vault API request failed: %s %s (%.1fms): %s",
                method, path, elapsed, e,
            )
            raise VeevaVaultError(f"Vault request failed: {e}") from e

        elapsed = (time.perf_counter() - start_time) * 1000
        logger.info(
            "Vault API %s %s -> %d (%.1fms)",
            method, path, resp.status_code, elapsed,
        )

        if resp.status_code >= 400:
            detail = resp.text[:500]
            raise VeevaVaultError(
                f"Vault API error {resp.status_code}: {detail}",
                status_code=resp.status_code,
                detail=detail,
            )

        return resp

    # ------------------------------------------------------------------
    # Connection Test
    # ------------------------------------------------------------------

    async def test_connection(self) -> dict[str, Any]:
        """Verify Vault connectivity and return basic info.

        Returns:
            Dict with connected, version, studies_count, latency_ms, session_valid, demo_mode.
        """
        if self._demo_mode:
            return {
                "connected": True,
                "version": "Vault CDMS v24.3 (Demo)",
                "studies_count": 5,
                "latency_ms": 10.2,
                "session_valid": True,
                "error": None,
                "demo_mode": True,
            }

        start_time = time.perf_counter()
        try:
            # Authenticate first
            await self.authenticate()
            # Then list studies to verify full connectivity
            resp = await self._request("GET", "/app/cdm/studies")
            elapsed = (time.perf_counter() - start_time) * 1000

            data = resp.json()
            studies_count = len(data.get("studies", []))

            return {
                "connected": True,
                "version": data.get("responseDetails", {}).get("vaultVersion", "Unknown"),
                "studies_count": studies_count,
                "latency_ms": round(elapsed, 1),
                "session_valid": True,
                "error": None,
                "demo_mode": False,
            }
        except VeevaVaultError as e:
            elapsed = (time.perf_counter() - start_time) * 1000
            return {
                "connected": False,
                "version": None,
                "studies_count": 0,
                "latency_ms": round(elapsed, 1),
                "session_valid": False,
                "error": str(e),
                "demo_mode": False,
            }

    # ------------------------------------------------------------------
    # Studies
    # ------------------------------------------------------------------

    async def list_studies(self) -> list[dict[str, Any]]:
        """List available studies in the Vault CDMS instance.

        Returns:
            List of study summary dicts with name, title, phase, status, etc.
        """
        if self._demo_mode:
            return _demo_studies()

        resp = await self._request("GET", "/app/cdm/studies")
        data = resp.json()

        studies = []
        for study in data.get("studies", []):
            studies.append({
                "name": study.get("name", ""),
                "title": study.get("title", "Unknown"),
                "phase": study.get("phase"),
                "status": study.get("status", "active"),
                "sponsor": study.get("sponsor"),
                "therapeutic_area": study.get("therapeuticArea"),
                "subject_count": study.get("subjectCount", 0),
            })
        return studies

    # ------------------------------------------------------------------
    # Study Import
    # ------------------------------------------------------------------

    async def import_study(self, study_name: str) -> dict[str, Any]:
        """Import a study definition from Vault CDMS.

        Pulls the study metadata, extracts eligibility criteria, and
        returns structured data suitable for creating a trial record.

        Args:
            study_name: Study name in Vault CDMS.

        Returns:
            Dict with study definition, criteria, forms, and mapping info.
        """
        if self._demo_mode:
            return _demo_study_import(study_name)

        # Fetch study definition
        resp = await self._request("GET", f"/app/cdm/studies/{study_name}")
        study_data = resp.json()

        # Fetch eligibility criteria (Vault uses casebook definitions)
        criteria_resp = await self._request(
            "GET", f"/app/cdm/studies/{study_name}/casebookdefinitions"
        )
        criteria_data = criteria_resp.json()

        # Parse criteria from casebook definitions
        criteria: list[dict[str, Any]] = []
        for item in criteria_data.get("definitions", []):
            if "eligibility" in item.get("name", "").lower() or "ie" in item.get("name", "").lower():
                criteria.append({
                    "oid": item.get("id", ""),
                    "criterion_type": "inclusion" if "incl" in item.get("name", "").lower() else "exclusion",
                    "description": item.get("label", ""),
                    "code_system": None,
                    "code": None,
                    "data_type": item.get("dataType", "text"),
                })

        mapped_count = sum(1 for c in criteria if c.get("code"))
        mapping_summary = {
            "total_criteria": len(criteria),
            "inclusion": sum(1 for c in criteria if c["criterion_type"] == "inclusion"),
            "exclusion": sum(1 for c in criteria if c["criterion_type"] == "exclusion"),
            "coded": mapped_count,
            "unmapped": len(criteria) - mapped_count,
        }

        return {
            "trial_id": None,
            "study_name": study_name,
            "study_title": study_data.get("title", study_name),
            "criteria_count": len(criteria),
            "criteria": criteria,
            "forms_count": len(study_data.get("forms", [])),
            "mapping_summary": mapping_summary,
            "demo_mode": False,
        }

    # ------------------------------------------------------------------
    # Screening Push
    # ------------------------------------------------------------------

    async def push_screening_result(
        self,
        trial_id: str,
        patient_id: str,
        eligibility_result: dict[str, Any],
        *,
        study_name: str = "",
    ) -> dict[str, Any]:
        """Push a screening result to Vault CDMS as clinical data.

        Args:
            trial_id: Internal trial ID.
            patient_id: Internal patient ID.
            eligibility_result: Screening result data with criterion outcomes.
            study_name: Target study name in Vault.

        Returns:
            Dict with success status, vault_subject_id, and any errors.
        """
        if self._demo_mode:
            return _demo_screening_push(patient_id)

        subject_id = f"VSUBJ-{patient_id[:8]}"
        items = []
        for criterion in eligibility_result.get("criteria_results", []):
            items.append({
                "definitionId": criterion.get("criterion_id", ""),
                "value": "Yes" if criterion.get("met") else "No",
            })

        try:
            await self._request(
                "POST",
                f"/app/cdm/studies/{study_name or trial_id}/subjects",
                json_body={
                    "subjectId": subject_id,
                    "screeningData": items,
                },
            )
            return {
                "patient_id": patient_id,
                "success": True,
                "vault_subject_id": subject_id,
                "error": None,
            }
        except VeevaVaultError as e:
            return {
                "patient_id": patient_id,
                "success": False,
                "vault_subject_id": None,
                "error": str(e),
            }

    # ------------------------------------------------------------------
    # Enrollment Sync
    # ------------------------------------------------------------------

    async def sync_enrollment_status(self, trial_id: str) -> dict[str, Any]:
        """Pull enrollment status updates from Vault CDMS.

        Args:
            trial_id: Internal trial ID (mapped to Vault study name).

        Returns:
            Dict with synced_count and list of status_updates.
        """
        if self._demo_mode:
            return _demo_enrollment_sync()

        resp = await self._request("GET", f"/app/cdm/studies/{trial_id}/subjects")
        data = resp.json()

        updates = []
        for subject in data.get("subjects", []):
            updates.append({
                "subject_id": subject.get("subjectId", ""),
                "patient_id": subject.get("externalId"),
                "status": subject.get("status", "Screening"),
                "status_date": subject.get("lastModified"),
                "site_name": subject.get("siteName"),
            })

        return {
            "synced_count": len(updates),
            "status_updates": updates,
            "demo_mode": False,
        }

    # ------------------------------------------------------------------
    # Study Subjects
    # ------------------------------------------------------------------

    async def list_subjects(self, study_name: str) -> list[dict[str, Any]]:
        """Get subjects in a Vault CDMS study.

        Args:
            study_name: Study name in Vault.

        Returns:
            List of subject dicts.
        """
        if self._demo_mode:
            return _demo_subjects()

        resp = await self._request("GET", f"/app/cdm/studies/{study_name}/subjects")
        data = resp.json()

        subjects = []
        for subject in data.get("subjects", []):
            subjects.append({
                "subject_id": subject.get("subjectId", ""),
                "subject_name": subject.get("label"),
                "site_id": subject.get("siteId"),
                "site_name": subject.get("siteName"),
                "status": subject.get("status"),
                "created_date": subject.get("createdDate"),
            })
        return subjects


# ==============================================================================
# Demo Data
# ==============================================================================


def _demo_studies() -> list[dict[str, Any]]:
    """Realistic demo study list for UI demonstration."""
    return [
        {
            "name": "REG-ONCO-3001",
            "title": "A Phase 3 Study of Fianlimab + Cemiplimab in Advanced Melanoma",
            "phase": "Phase 3",
            "status": "active",
            "sponsor": "Regeneron Pharmaceuticals",
            "therapeutic_area": "Oncology",
            "subject_count": 1580,
        },
        {
            "name": "REG-HEM-2001",
            "title": "A Phase 2 Study of Linvoseltamab in Relapsed/Refractory Multiple Myeloma",
            "phase": "Phase 2",
            "status": "active",
            "sponsor": "Regeneron Pharmaceuticals",
            "therapeutic_area": "Hematology",
            "subject_count": 432,
        },
        {
            "name": "REG-RESP-3002",
            "title": "A Phase 3 Study of Itepekimab in Moderate-to-Severe COPD",
            "phase": "Phase 3",
            "status": "active",
            "sponsor": "Regeneron / Sanofi",
            "therapeutic_area": "Respiratory",
            "subject_count": 918,
        },
        {
            "name": "REG-DRM-3003",
            "title": "A Phase 3 Study of Dupilumab in Bullous Pemphigoid",
            "phase": "Phase 3",
            "status": "active",
            "sponsor": "Regeneron / Sanofi",
            "therapeutic_area": "Dermatology",
            "subject_count": 275,
        },
        {
            "name": "REG-NHL-3001",
            "title": "A Phase 3 Study of Odronextamab in Relapsed/Refractory Follicular Lymphoma",
            "phase": "Phase 3",
            "status": "active",
            "sponsor": "Regeneron Pharmaceuticals",
            "therapeutic_area": "Oncology",
            "subject_count": 614,
        },
    ]


def _demo_study_import(study_name: str) -> dict[str, Any]:
    """Demo study import with realistic eligibility criteria."""
    demo_studies = _demo_studies()
    study = next((s for s in demo_studies if s["name"] == study_name), None)
    study_title = study["title"] if study else f"Study {study_name}"

    # Study-specific criteria for more realism
    study_criteria: dict[str, list[dict[str, Any]]] = {
        "REG-ONCO-3001": [
            {
                "oid": "IE.INCL01",
                "criterion_type": "inclusion",
                "description": "Age >= 18 years at screening",
                "code_system": None,
                "code": None,
                "data_type": "integer",
            },
            {
                "oid": "IE.INCL02",
                "criterion_type": "inclusion",
                "description": "Histologically confirmed unresectable Stage III or Stage IV melanoma",
                "code_system": "SNOMED-CT",
                "code": "372244006",
                "data_type": "text",
            },
            {
                "oid": "IE.INCL03",
                "criterion_type": "inclusion",
                "description": "ECOG performance status 0-1",
                "code_system": None,
                "code": None,
                "data_type": "integer",
            },
            {
                "oid": "IE.INCL04",
                "criterion_type": "inclusion",
                "description": "At least one measurable lesion per RECIST v1.1",
                "code_system": None,
                "code": None,
                "data_type": "text",
            },
            {
                "oid": "IE.INCL05",
                "criterion_type": "inclusion",
                "description": "Adequate organ function per protocol-specified laboratory values",
                "code_system": None,
                "code": None,
                "data_type": "text",
            },
            {
                "oid": "IE.EXCL01",
                "criterion_type": "exclusion",
                "description": "Prior treatment with anti-LAG-3 therapy",
                "code_system": None,
                "code": None,
                "data_type": "text",
            },
            {
                "oid": "IE.EXCL02",
                "criterion_type": "exclusion",
                "description": "Active or untreated CNS metastases",
                "code_system": "SNOMED-CT",
                "code": "94225005",
                "data_type": "text",
            },
            {
                "oid": "IE.EXCL03",
                "criterion_type": "exclusion",
                "description": "Active autoimmune disease requiring systemic immunosuppression",
                "code_system": None,
                "code": None,
                "data_type": "text",
            },
            {
                "oid": "IE.EXCL04",
                "criterion_type": "exclusion",
                "description": "Pregnant or breastfeeding",
                "code_system": "SNOMED-CT",
                "code": "77386006",
                "data_type": "text",
            },
            {
                "oid": "IE.EXCL05",
                "criterion_type": "exclusion",
                "description": "Known hypersensitivity to cemiplimab or fianlimab components",
                "code_system": None,
                "code": None,
                "data_type": "text",
            },
        ],
    }

    # Default generic criteria for studies not in the map
    default_criteria = [
        {
            "oid": "IE.INCL01",
            "criterion_type": "inclusion",
            "description": "Age >= 18 years at screening",
            "code_system": None,
            "code": None,
            "data_type": "integer",
        },
        {
            "oid": "IE.INCL02",
            "criterion_type": "inclusion",
            "description": "Confirmed diagnosis per study-specific criteria",
            "code_system": "SNOMED-CT",
            "code": "404684003",
            "data_type": "text",
        },
        {
            "oid": "IE.INCL03",
            "criterion_type": "inclusion",
            "description": "ECOG performance status 0-1",
            "code_system": None,
            "code": None,
            "data_type": "integer",
        },
        {
            "oid": "IE.INCL04",
            "criterion_type": "inclusion",
            "description": "Adequate organ function as defined by laboratory values within protocol-specified ranges",
            "code_system": None,
            "code": None,
            "data_type": "text",
        },
        {
            "oid": "IE.INCL05",
            "criterion_type": "inclusion",
            "description": "Written informed consent obtained",
            "code_system": None,
            "code": None,
            "data_type": "text",
        },
        {
            "oid": "IE.EXCL01",
            "criterion_type": "exclusion",
            "description": "Prior treatment with study drug or similar mechanism of action within 6 months",
            "code_system": None,
            "code": None,
            "data_type": "text",
        },
        {
            "oid": "IE.EXCL02",
            "criterion_type": "exclusion",
            "description": "Active or untreated CNS metastases",
            "code_system": "SNOMED-CT",
            "code": "94225005",
            "data_type": "text",
        },
        {
            "oid": "IE.EXCL03",
            "criterion_type": "exclusion",
            "description": "Known hypersensitivity to study drug components",
            "code_system": None,
            "code": None,
            "data_type": "text",
        },
        {
            "oid": "IE.EXCL04",
            "criterion_type": "exclusion",
            "description": "Pregnant or breastfeeding",
            "code_system": "SNOMED-CT",
            "code": "77386006",
            "data_type": "text",
        },
        {
            "oid": "IE.EXCL05",
            "criterion_type": "exclusion",
            "description": "Uncontrolled intercurrent illness including active infection",
            "code_system": None,
            "code": None,
            "data_type": "text",
        },
    ]

    criteria = study_criteria.get(study_name, default_criteria)
    coded_count = sum(1 for c in criteria if c.get("code"))

    return {
        "trial_id": str(uuid.uuid4()),
        "study_name": study_name,
        "study_title": study_title,
        "criteria_count": len(criteria),
        "criteria": criteria,
        "forms_count": 14,
        "mapping_summary": {
            "total_criteria": len(criteria),
            "inclusion": sum(1 for c in criteria if c["criterion_type"] == "inclusion"),
            "exclusion": sum(1 for c in criteria if c["criterion_type"] == "exclusion"),
            "coded": coded_count,
            "unmapped": len(criteria) - coded_count,
        },
        "demo_mode": True,
    }


def _demo_screening_push(patient_id: str) -> dict[str, Any]:
    """Demo screening push result."""
    return {
        "patient_id": patient_id,
        "success": True,
        "vault_subject_id": f"VSUBJ-{patient_id[:8].upper()}",
        "error": None,
    }


def _demo_enrollment_sync() -> dict[str, Any]:
    """Demo enrollment status sync."""
    return {
        "synced_count": 4,
        "status_updates": [
            {
                "subject_id": "VSUBJ-001",
                "patient_id": "pat-1001",
                "status": "Enrolled",
                "status_date": datetime.now(timezone.utc).isoformat(),
                "site_name": "Memorial Sloan Kettering",
            },
            {
                "subject_id": "VSUBJ-002",
                "patient_id": "pat-1002",
                "status": "Screening",
                "status_date": datetime.now(timezone.utc).isoformat(),
                "site_name": "MD Anderson Cancer Center",
            },
            {
                "subject_id": "VSUBJ-003",
                "patient_id": "pat-1003",
                "status": "Screen Failed",
                "status_date": datetime.now(timezone.utc).isoformat(),
                "site_name": "Dana-Farber Cancer Institute",
            },
            {
                "subject_id": "VSUBJ-004",
                "patient_id": "pat-1004",
                "status": "Randomized",
                "status_date": datetime.now(timezone.utc).isoformat(),
                "site_name": "Cleveland Clinic",
            },
        ],
        "demo_mode": True,
    }


def _demo_subjects() -> list[dict[str, Any]]:
    """Demo study subjects list."""
    return [
        {
            "subject_id": "VSUBJ-001",
            "subject_name": "Subject 001",
            "site_id": "SITE-MSK",
            "site_name": "Memorial Sloan Kettering",
            "status": "Enrolled",
            "created_date": "2024-06-15T10:00:00Z",
        },
        {
            "subject_id": "VSUBJ-002",
            "subject_name": "Subject 002",
            "site_id": "SITE-MDA",
            "site_name": "MD Anderson Cancer Center",
            "status": "Screening",
            "created_date": "2024-07-01T14:30:00Z",
        },
        {
            "subject_id": "VSUBJ-003",
            "subject_name": "Subject 003",
            "site_id": "SITE-DFCI",
            "site_name": "Dana-Farber Cancer Institute",
            "status": "Screen Failed",
            "created_date": "2024-07-10T09:15:00Z",
        },
    ]


# ==============================================================================
# Singleton accessor
# ==============================================================================

_instance: VeevaVaultService | None = None


def get_veeva_vault_service() -> VeevaVaultService:
    """Get or create the singleton VeevaVaultService instance."""
    global _instance
    if _instance is None:
        _instance = VeevaVaultService()
    return _instance
