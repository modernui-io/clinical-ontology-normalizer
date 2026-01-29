"""SMART on FHIR API endpoints for EHR integration.

Provides OAuth2 authorization endpoints for SMART App Launch:
- EHR launch flow
- Standalone launch flow
- Token management
- Patient/Encounter context access
"""

import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Cookie, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.api.errors import log_and_raise_internal_error
from app.core.smart_config import (
    EHRVendor,
    SMARTScope,
    WellKnownConfig,
    get_recommended_scopes,
    smart_settings,
)
from app.services.smart_fhir import (
    AuthorizationError,
    FHIRRequestError,
    LaunchContext,
    SMARTClient,
    TokenError,
    TokenSet,
    get_smart_client,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/smart", tags=["smart"])


# Request/Response Models
class LaunchRequest(BaseModel):
    """Request to initiate SMART launch."""

    fhir_base_url: str | None = Field(
        None,
        description="FHIR server base URL (uses default if not provided)",
    )
    scopes: list[str] | None = Field(
        None,
        description="OAuth scopes to request (uses default if not provided)",
    )
    launch_token: str | None = Field(
        None,
        description="EHR launch token (for EHR launch flow)",
    )
    vendor: EHRVendor | None = Field(
        None,
        description="EHR vendor for vendor-specific handling",
    )


class LaunchResponse(BaseModel):
    """Response with authorization URL."""

    authorization_url: str = Field(..., description="URL to redirect user for authorization")
    state: str = Field(..., description="State parameter for CSRF protection")
    session_id: str = Field(..., description="Session ID for token retrieval")


class TokenResponse(BaseModel):
    """Response with token information."""

    access_token: str = Field(..., description="OAuth2 access token")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_in: int | None = Field(None, description="Token expiration in seconds")
    scope: str | None = Field(None, description="Granted scopes")
    patient: str | None = Field(None, description="Patient ID in context")
    encounter: str | None = Field(None, description="Encounter ID in context")
    fhir_user: str | None = Field(None, description="FHIR User reference")
    has_refresh_token: bool = Field(False, description="Whether refresh token is available")


class PatientResponse(BaseModel):
    """Patient resource response."""

    id: str = Field(..., description="Patient FHIR ID")
    name: str | None = Field(None, description="Patient name")
    gender: str | None = Field(None, description="Patient gender")
    birth_date: str | None = Field(None, description="Patient birth date")
    mrn: str | None = Field(None, description="Medical record number")
    resource: dict[str, Any] = Field(..., description="Full FHIR Patient resource")


class EncounterResponse(BaseModel):
    """Encounter resource response."""

    id: str = Field(..., description="Encounter FHIR ID")
    status: str | None = Field(None, description="Encounter status")
    class_code: str | None = Field(None, description="Encounter class")
    period_start: str | None = Field(None, description="Encounter start time")
    period_end: str | None = Field(None, description="Encounter end time")
    resource: dict[str, Any] = Field(..., description="Full FHIR Encounter resource")


class ContextResponse(BaseModel):
    """Launch context response."""

    patient: str | None = Field(None, description="Patient ID in context")
    encounter: str | None = Field(None, description="Encounter ID in context")
    fhir_user: str | None = Field(None, description="FHIR User reference")
    need_patient_banner: bool = Field(True, description="Whether to show patient banner")
    smart_style_url: str | None = Field(None, description="Style URL for branding")


class RevokeRequest(BaseModel):
    """Request to revoke access."""

    session_id: str = Field(..., description="Session ID to revoke")


class RevokeResponse(BaseModel):
    """Response from token revocation."""

    success: bool = Field(..., description="Whether revocation succeeded")
    message: str = Field(..., description="Status message")


class SMARTConfigResponse(BaseModel):
    """SMART configuration response."""

    fhir_base_url: str
    authorization_endpoint: str
    token_endpoint: str
    revocation_endpoint: str | None = None
    scopes_supported: list[str]
    capabilities: list[str]
    recommended_scopes: list[str]


class ErrorResponse(BaseModel):
    """Error response."""

    error: str = Field(..., description="Error code")
    error_description: str = Field(..., description="Error description")


# Endpoints
@router.get("/launch", response_model=LaunchResponse)
async def handle_ehr_launch(
    iss: str = Query(..., description="FHIR server issuer URL"),
    launch: str | None = Query(None, description="EHR launch token"),
    response: Response = None,
) -> LaunchResponse:
    """Handle EHR launch request.

    This endpoint is called by the EHR when launching the app.
    It initiates the OAuth2 authorization flow.

    Args:
        iss: FHIR server issuer URL (base URL)
        launch: Launch token from EHR
        response: FastAPI response for setting cookies

    Returns:
        Authorization URL and session info
    """
    logger.info(f"EHR launch initiated from {iss}")

    client = get_smart_client()
    session_id = str(uuid4())

    try:
        # Determine scopes based on vendor
        scopes = get_recommended_scopes(smart_settings.ehr_vendor)

        # Add launch scope if we have a launch token
        if launch and SMARTScope.LAUNCH.value not in scopes:
            scopes.insert(0, SMARTScope.LAUNCH.value)

        auth_url, state = await client.initiate_authorization(
            fhir_base_url=iss,
            scopes=scopes,
            launch_token=launch,
        )

        # Set session cookie
        if response:
            response.set_cookie(
                key="smart_session_id",
                value=session_id,
                httponly=True,
                secure=True,  # Require HTTPS in production
                samesite="lax",
                max_age=3600,  # 1 hour
            )

        return LaunchResponse(
            authorization_url=auth_url,
            state=state,
            session_id=session_id,
        )

    except AuthorizationError as e:
        logger.error(f"Authorization initiation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/launch", response_model=LaunchResponse)
async def initiate_standalone_launch(
    request: LaunchRequest,
    response: Response,
) -> LaunchResponse:
    """Initiate standalone SMART launch.

    This endpoint is called by the app to start authorization
    without being launched from an EHR.

    Args:
        request: Launch configuration
        response: FastAPI response for setting cookies

    Returns:
        Authorization URL and session info
    """
    client = get_smart_client()
    session_id = str(uuid4())

    fhir_base_url = request.fhir_base_url or smart_settings.fhir_base_url
    vendor = request.vendor or smart_settings.ehr_vendor

    try:
        # Use requested scopes or get recommended ones
        scopes = request.scopes or get_recommended_scopes(vendor)

        auth_url, state = await client.initiate_authorization(
            fhir_base_url=fhir_base_url,
            scopes=scopes,
            launch_token=request.launch_token,
        )

        # Set session cookie
        response.set_cookie(
            key="smart_session_id",
            value=session_id,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=3600,
        )

        logger.info(f"Standalone launch initiated for {fhir_base_url}")

        return LaunchResponse(
            authorization_url=auth_url,
            state=state,
            session_id=session_id,
        )

    except AuthorizationError as e:
        logger.error(f"Authorization initiation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/callback", response_model=None)
async def handle_oauth_callback(
    code: str | None = Query(None, description="Authorization code"),
    state: str | None = Query(None, description="State parameter"),
    error: str | None = Query(None, description="Error code"),
    error_description: str | None = Query(None, description="Error description"),
    smart_session_id: str | None = Cookie(None),
):
    """Handle OAuth2 callback from authorization server.

    This endpoint receives the authorization code after user
    grants consent in the EHR.

    Args:
        code: Authorization code
        state: State parameter for CSRF validation
        error: Error code if authorization failed
        error_description: Error description
        smart_session_id: Session ID from cookie

    Returns:
        Redirect to app with session info or error
    """
    # Handle authorization errors
    if error:
        logger.error(f"OAuth callback error: {error} - {error_description}")
        # In production, redirect to error page
        raise HTTPException(
            status_code=400,
            detail=error_description or error,
        )

    if not code or not state:
        raise HTTPException(
            status_code=400,
            detail="Missing authorization code or state",
        )

    client = get_smart_client()

    try:
        # Exchange code for tokens
        tokens = await client.exchange_code(
            code=code,
            state=state,
            session_id=smart_session_id,
        )

        logger.info(
            f"OAuth callback successful, patient={tokens.patient}, "
            f"session={smart_session_id}"
        )

        # In production, redirect to app's main page
        # For now, return token info (minus sensitive data)
        return {
            "success": True,
            "message": "Authorization successful",
            "patient": tokens.patient,
            "encounter": tokens.encounter,
            "session_id": smart_session_id,
            "scopes": tokens.scope,
        }

    except AuthorizationError as e:
        logger.error(f"Code exchange failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except TokenError as e:
        logger.error(f"Token exchange failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/token", response_model=TokenResponse)
async def get_current_token(
    smart_session_id: str | None = Cookie(None),
) -> TokenResponse:
    """Get current token information for the session.

    Args:
        smart_session_id: Session ID from cookie

    Returns:
        Current token information (without exposing the actual token)
    """
    if not smart_session_id:
        raise HTTPException(status_code=401, detail="No active session")

    client = get_smart_client()
    tokens = client.get_tokens(smart_session_id)

    if not tokens:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    return TokenResponse(
        access_token="[REDACTED]",  # Don't expose actual token
        token_type=tokens.token_type.value,
        expires_in=tokens.expires_in,
        scope=tokens.scope,
        patient=tokens.patient,
        encounter=tokens.encounter,
        fhir_user=tokens.fhir_user,
        has_refresh_token=tokens.refresh_token is not None,
    )


@router.get("/context", response_model=ContextResponse)
async def get_launch_context(
    smart_session_id: str | None = Cookie(None),
) -> ContextResponse:
    """Get the current launch context.

    Args:
        smart_session_id: Session ID from cookie

    Returns:
        Launch context with patient/encounter info
    """
    if not smart_session_id:
        raise HTTPException(status_code=401, detail="No active session")

    client = get_smart_client()
    tokens = client.get_tokens(smart_session_id)

    if not tokens:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    context = tokens.get_launch_context()
    return ContextResponse(
        patient=context.patient,
        encounter=context.encounter,
        fhir_user=context.fhir_user,
        need_patient_banner=context.need_patient_banner,
        smart_style_url=context.smart_style_url,
    )


@router.get("/patient", response_model=PatientResponse)
async def get_patient_in_context(
    smart_session_id: str | None = Cookie(None),
) -> PatientResponse:
    """Get the patient in the current launch context.

    Args:
        smart_session_id: Session ID from cookie

    Returns:
        Patient resource information
    """
    if not smart_session_id:
        raise HTTPException(status_code=401, detail="No active session")

    client = get_smart_client()
    tokens = client.get_tokens(smart_session_id)

    if not tokens:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    if not tokens.patient:
        raise HTTPException(
            status_code=404,
            detail="No patient in current context",
        )

    try:
        patient = await client.get_patient(
            patient_id=tokens.patient,
            access_token=tokens.access_token,
        )

        if not patient:
            raise HTTPException(
                status_code=404,
                detail=f"Patient {tokens.patient} not found",
            )

        # Extract patient info
        name = _extract_patient_name(patient)
        mrn = _extract_identifier(patient)

        return PatientResponse(
            id=patient.get("id", tokens.patient),
            name=name,
            gender=patient.get("gender"),
            birth_date=patient.get("birthDate"),
            mrn=mrn,
            resource=patient,
        )

    except FHIRRequestError as e:
        # VP-Security-2: Sanitize error messages
        raise log_and_raise_internal_error(
            exception=e,
            endpoint="/api/v1/smart/patient",
            user_message="Failed to fetch patient data",
        )


@router.get("/encounter", response_model=EncounterResponse)
async def get_encounter_in_context(
    smart_session_id: str | None = Cookie(None),
) -> EncounterResponse:
    """Get the encounter in the current launch context.

    Args:
        smart_session_id: Session ID from cookie

    Returns:
        Encounter resource information
    """
    if not smart_session_id:
        raise HTTPException(status_code=401, detail="No active session")

    client = get_smart_client()
    tokens = client.get_tokens(smart_session_id)

    if not tokens:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    if not tokens.encounter:
        raise HTTPException(
            status_code=404,
            detail="No encounter in current context",
        )

    try:
        encounter = await client.get_encounter(
            encounter_id=tokens.encounter,
            access_token=tokens.access_token,
        )

        if not encounter:
            raise HTTPException(
                status_code=404,
                detail=f"Encounter {tokens.encounter} not found",
            )

        # Extract encounter info
        period = encounter.get("period", {})
        class_info = encounter.get("class", {})

        return EncounterResponse(
            id=encounter.get("id", tokens.encounter),
            status=encounter.get("status"),
            class_code=class_info.get("code"),
            period_start=period.get("start"),
            period_end=period.get("end"),
            resource=encounter,
        )

    except FHIRRequestError as e:
        raise log_and_raise_internal_error(
            exception=e,
            endpoint="/api/v1/smart/encounter",
            user_message="Failed to fetch encounter data",
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(
    smart_session_id: str | None = Cookie(None),
) -> TokenResponse:
    """Refresh the access token for the current session.

    Args:
        smart_session_id: Session ID from cookie

    Returns:
        Updated token information
    """
    if not smart_session_id:
        raise HTTPException(status_code=401, detail="No active session")

    client = get_smart_client()
    tokens = client.get_tokens(smart_session_id)

    if not tokens:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    if not tokens.refresh_token:
        raise HTTPException(
            status_code=400,
            detail="No refresh token available",
        )

    try:
        new_tokens = await client.refresh_token(
            refresh_token=tokens.refresh_token,
            session_id=smart_session_id,
        )

        return TokenResponse(
            access_token="[REDACTED]",
            token_type=new_tokens.token_type.value,
            expires_in=new_tokens.expires_in,
            scope=new_tokens.scope,
            patient=new_tokens.patient,
            encounter=new_tokens.encounter,
            fhir_user=new_tokens.fhir_user,
            has_refresh_token=new_tokens.refresh_token is not None,
        )

    except TokenError as e:
        logger.error(f"Token refresh failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/revoke", response_model=RevokeResponse)
async def revoke_access(
    request: RevokeRequest,
    response: Response,
) -> RevokeResponse:
    """Revoke access for a session.

    This endpoint revokes the access token and clears the session.

    Args:
        request: Revocation request with session ID
        response: FastAPI response for clearing cookies

    Returns:
        Revocation status
    """
    client = get_smart_client()
    tokens = client.get_tokens(request.session_id)

    success = True
    message = "Session cleared"

    if tokens:
        # Try to revoke the access token
        revoked = await client.revoke_token(tokens.access_token)

        # Try to revoke refresh token if available
        if tokens.refresh_token:
            await client.revoke_token(
                tokens.refresh_token,
                token_type_hint="refresh_token",
            )

        success = revoked
        message = "Access revoked" if revoked else "Session cleared (revocation not supported)"

    # Clear session tokens
    client.remove_tokens(request.session_id)

    # Clear session cookie
    response.delete_cookie(key="smart_session_id")

    logger.info(f"Session {request.session_id} revoked")

    return RevokeResponse(
        success=success,
        message=message,
    )


@router.get("/config", response_model=SMARTConfigResponse)
async def get_smart_configuration(
    fhir_base_url: str | None = Query(
        None,
        description="FHIR server URL (uses default if not provided)",
    ),
) -> SMARTConfigResponse:
    """Get SMART configuration for a FHIR server.

    Discovers the SMART configuration from the well-known endpoint.

    Args:
        fhir_base_url: FHIR server base URL

    Returns:
        SMART configuration details
    """
    fhir_base_url = fhir_base_url or smart_settings.fhir_base_url
    client = get_smart_client()

    config = await client.get_smart_config(fhir_base_url)

    if not config:
        raise HTTPException(
            status_code=404,
            detail=f"SMART configuration not found for {fhir_base_url}",
        )

    return SMARTConfigResponse(
        fhir_base_url=fhir_base_url,
        authorization_endpoint=config.authorization_endpoint,
        token_endpoint=config.token_endpoint,
        revocation_endpoint=config.revocation_endpoint,
        scopes_supported=config.scopes_supported,
        capabilities=config.capabilities,
        recommended_scopes=get_recommended_scopes(smart_settings.ehr_vendor),
    )


@router.get("/scopes")
async def list_available_scopes() -> dict[str, Any]:
    """List all available SMART scopes.

    Returns:
        Dictionary of scope categories and their scopes
    """
    return {
        "patient_scopes": [
            {"scope": SMARTScope.PATIENT_READ.value, "description": "Read all patient data"},
            {"scope": SMARTScope.PATIENT_WRITE.value, "description": "Write patient data"},
            {"scope": SMARTScope.PATIENT_CONDITION_READ.value, "description": "Read conditions"},
            {"scope": SMARTScope.PATIENT_MEDICATION_READ.value, "description": "Read medications"},
            {"scope": SMARTScope.PATIENT_OBSERVATION_READ.value, "description": "Read observations"},
            {"scope": SMARTScope.PATIENT_ALLERGY_READ.value, "description": "Read allergies"},
            {"scope": SMARTScope.PATIENT_PROCEDURE_READ.value, "description": "Read procedures"},
        ],
        "launch_scopes": [
            {"scope": SMARTScope.LAUNCH.value, "description": "EHR launch"},
            {"scope": SMARTScope.LAUNCH_PATIENT.value, "description": "Patient context"},
            {"scope": SMARTScope.LAUNCH_ENCOUNTER.value, "description": "Encounter context"},
        ],
        "identity_scopes": [
            {"scope": SMARTScope.OPENID.value, "description": "OpenID Connect"},
            {"scope": SMARTScope.FHIR_USER.value, "description": "FHIR user identity"},
            {"scope": SMARTScope.PROFILE.value, "description": "User profile"},
            {"scope": SMARTScope.OFFLINE_ACCESS.value, "description": "Refresh tokens"},
        ],
        "default_scopes": smart_settings.default_scopes,
    }


@router.get("/status")
async def get_service_status() -> dict[str, Any]:
    """Get SMART service status and statistics.

    Returns:
        Service status and statistics
    """
    client = get_smart_client()
    stats = client.get_stats()

    # Cleanup expired states
    expired_count = client.cleanup_expired_states()
    if expired_count > 0:
        logger.info(f"Cleaned up {expired_count} expired OAuth states")

    return {
        "status": "healthy",
        "client_id_configured": bool(smart_settings.client_id),
        "fhir_base_url": smart_settings.fhir_base_url,
        "ehr_vendor": smart_settings.ehr_vendor.value,
        **stats,
    }


# Helper functions
def _extract_patient_name(patient: dict[str, Any]) -> str | None:
    """Extract patient name from FHIR Patient resource."""
    names = patient.get("name", [])
    if names:
        name = names[0]
        given = " ".join(name.get("given", []))
        family = name.get("family", "")
        full_name = f"{given} {family}".strip()
        return full_name if full_name else None
    return None


def _extract_identifier(patient: dict[str, Any]) -> str | None:
    """Extract MRN from FHIR Patient resource."""
    identifiers = patient.get("identifier", [])
    for ident in identifiers:
        if ident.get("system", "").endswith("/mrn"):
            return ident.get("value")
    if identifiers:
        return identifiers[0].get("value")
    return None
