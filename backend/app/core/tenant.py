"""Tenant and patient isolation for Clinical Ontology Normalizer.

P0-016: Enforces tenant/org boundary checks at query boundaries.

Provides multi-tenant support and patient-level access control.
Each API key can be associated with a set of allowed patient IDs,
ensuring data isolation between different clients.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from fastapi import Depends, HTTPException, Request, status

from app.core.audit import AuditAction, log_audit

logger = logging.getLogger(__name__)


@lru_cache
def get_tenant_patient_mapping() -> dict[str, set[str]]:
    """Get the mapping of API keys to allowed patient IDs.

    Configuration is via environment variables:
    - CON_TENANT_<KEY>_PATIENTS: Comma-separated list of patient IDs for <KEY>

    Example:
        CON_TENANT_KEY1_PATIENTS=P001,P002
        CON_TENANT_KEY2_PATIENTS=P003,P004

    Returns:
        Dictionary mapping API keys to sets of allowed patient IDs
    """
    mapping: dict[str, set[str]] = {}

    for key, value in os.environ.items():
        if key.startswith("CON_TENANT_") and key.endswith("_PATIENTS"):
            # Extract API key name from CON_TENANT_<KEY>_PATIENTS
            api_key = key.replace("CON_TENANT_", "").replace("_PATIENTS", "")
            patients = {p.strip() for p in value.split(",") if p.strip()}
            if patients:
                mapping[api_key] = patients
                logger.info(
                    f"Tenant {api_key}: {len(patients)} patient(s) configured"
                )

    if not mapping:
        logger.warning(
            "No tenant-patient mappings configured. "
            "All API keys can access all patients."
        )

    return mapping


def is_tenant_isolation_enabled() -> bool:
    """Check if tenant isolation is enabled.

    Tenant isolation is enabled when tenant-patient mappings are configured.

    Returns:
        True if tenant isolation is enabled
    """
    return len(get_tenant_patient_mapping()) > 0


def get_allowed_patients(api_key: str | None) -> set[str] | None:
    """Get the set of patient IDs allowed for an API key.

    Args:
        api_key: The API key to check

    Returns:
        Set of allowed patient IDs, or None if no restrictions
    """
    if api_key is None:
        return None

    mapping = get_tenant_patient_mapping()
    if not mapping:
        return None

    return mapping.get(api_key)


def verify_patient_access(
    api_key: str | None,
    patient_id: str,
    action: str = "access",
) -> None:
    """Verify that an API key has access to a specific patient.

    Args:
        api_key: The API key making the request
        patient_id: The patient ID being accessed
        action: Description of the action (for logging)

    Raises:
        HTTPException: 403 if access is denied
    """
    # If no API key (auth disabled), allow access
    if api_key is None:
        return

    # If no tenant mappings configured, allow access
    allowed_patients = get_allowed_patients(api_key)
    if allowed_patients is None:
        return

    # Check if patient is in allowed list
    if patient_id not in allowed_patients:
        logger.warning(
            f"Access denied: API key attempted to {action} patient {patient_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: not authorized to {action} patient {patient_id}",
        )

    logger.debug(f"Access granted: {action} patient {patient_id}")


def verify_document_access(
    api_key: str | None,
    patient_id: str,
    document_id: str,
    action: str = "access",
) -> None:
    """Verify that an API key has access to a patient's document.

    Args:
        api_key: The API key making the request
        patient_id: The patient ID owning the document
        document_id: The document ID being accessed
        action: Description of the action (for logging)

    Raises:
        HTTPException: 403 if access is denied
    """
    verify_patient_access(api_key, patient_id, f"{action} document {document_id}")


class TenantContext:
    """Context object for tracking tenant information in requests.

    Use this to pass tenant context through the request lifecycle.
    """

    def __init__(
        self,
        api_key: str | None = None,
        tenant_id: str | None = None,
    ):
        self.api_key = api_key
        self.tenant_id = tenant_id or api_key
        self._allowed_patients: set[str] | None = None

    @property
    def allowed_patients(self) -> set[str] | None:
        """Get the set of allowed patients for this tenant."""
        if self._allowed_patients is None:
            self._allowed_patients = get_allowed_patients(self.api_key)
        return self._allowed_patients

    def can_access_patient(self, patient_id: str) -> bool:
        """Check if this tenant can access a specific patient.

        Args:
            patient_id: The patient ID to check

        Returns:
            True if access is allowed
        """
        allowed = self.allowed_patients
        if allowed is None:
            return True
        return patient_id in allowed

    def verify_patient_access(self, patient_id: str, action: str = "access") -> None:
        """Verify access to a patient, raising if denied.

        Args:
            patient_id: The patient ID to verify
            action: Description of the action

        Raises:
            HTTPException: 403 if access is denied
        """
        verify_patient_access(self.api_key, patient_id, action)


# ---------------------------------------------------------------------------
# P0-016: FastAPI dependency for tenant context extraction and enforcement
# ---------------------------------------------------------------------------


def get_tenant_context(request: Request) -> TenantContext:
    """Extract tenant context from the current request.

    Reads the API key from request state (set by auth middleware) and
    builds a TenantContext for downstream tenant isolation checks.

    Args:
        request: The incoming FastAPI request.

    Returns:
        TenantContext with the caller's tenant identity.
    """
    api_key: str | None = None

    # Try auth middleware user first
    user = getattr(request.state, "user", None)
    if user and hasattr(user, "api_key"):
        api_key = user.api_key

    # Fall back to raw header
    if api_key is None:
        api_key = request.headers.get("X-API-Key")

    tenant_id = getattr(request.state, "tenant_id", None) or api_key
    return TenantContext(api_key=api_key, tenant_id=tenant_id)


def require_tenant_isolation(
    request: Request,
    tenant: TenantContext = Depends(get_tenant_context),
) -> TenantContext:
    """FastAPI dependency that enforces tenant isolation is active.

    P0-016: When tenant mappings are configured, this dependency ensures
    the caller has a recognized tenant identity. If no mappings are
    configured (development mode), it passes through.

    Args:
        request: The incoming FastAPI request.
        tenant: The resolved TenantContext.

    Returns:
        The validated TenantContext.

    Raises:
        HTTPException: 403 if tenant isolation is enabled but caller has
            no recognized tenant identity.
    """
    if is_tenant_isolation_enabled() and tenant.tenant_id is None:
        log_audit(
            action=AuditAction.AUTH_FAILURE,
            resource_type="tenant_isolation",
            ip_address=request.client.host if request.client else "unknown",
            details={"reason": "no_tenant_identity"},
            success=False,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant identity required. Provide a valid API key.",
        )
    return tenant
