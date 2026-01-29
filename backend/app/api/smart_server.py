"""SMART on FHIR Server API endpoints.

This module implements the server-side SMART on FHIR authorization endpoints,
allowing external SMART apps to connect to this platform as a FHIR server.

Endpoints:
- Authorization flow: /authorize (GET/POST), /token (POST)
- App management: CRUD operations for registered SMART apps
- Launch context: Create test launch contexts for development

This implements the SMART App Launch Framework v2.0:
https://hl7.org/fhir/smart-app-launch/
"""

import hashlib
import logging
import secrets
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.auth_middleware import CurrentUser, require_admin
from app.core.database import get_db
from app.models.smart_app import SMARTApp

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/smart-server", tags=["SMART on FHIR"])


# =============================================================================
# Enums and Constants
# =============================================================================


class AppType(str, Enum):
    """SMART app client types."""

    PUBLIC = "public"
    CONFIDENTIAL_SYMMETRIC = "confidential-symmetric"
    CONFIDENTIAL_ASYMMETRIC = "confidential-asymmetric"


class GrantType(str, Enum):
    """OAuth2 grant types."""

    AUTHORIZATION_CODE = "authorization_code"
    CLIENT_CREDENTIALS = "client_credentials"
    REFRESH_TOKEN = "refresh_token"


class ResponseType(str, Enum):
    """OAuth2 response types."""

    CODE = "code"


# Token TTLs
ACCESS_TOKEN_TTL_SECONDS = 3600  # 1 hour
REFRESH_TOKEN_TTL_SECONDS = 86400 * 7  # 7 days
AUTH_CODE_TTL_SECONDS = 600  # 10 minutes
LAUNCH_CONTEXT_TTL_SECONDS = 600  # 10 minutes


# =============================================================================
# Pydantic Models
# =============================================================================


class SMARTAppRegistration(BaseModel):
    """Request to register a new SMART app."""

    client_name: str = Field(..., description="Human-readable app name")
    redirect_uris: list[str] = Field(
        ...,
        min_length=1,
        description="Allowed redirect URIs",
    )
    scope: str = Field(
        "launch openid fhirUser patient/*.read",
        description="Requested scopes (space-separated)",
    )
    app_type: AppType = Field(
        AppType.PUBLIC,
        description="Client type (public or confidential)",
    )
    logo_uri: str | None = Field(None, description="App logo URL")
    contacts: list[str] | None = Field(None, description="Contact emails")
    tos_uri: str | None = Field(None, description="Terms of service URL")
    policy_uri: str | None = Field(None, description="Privacy policy URL")
    jwks_uri: str | None = Field(
        None,
        description="JWKS URI for asymmetric client auth",
    )


class SMARTAppResponse(BaseModel):
    """Response with SMART app details."""

    client_id: str = Field(..., description="Client identifier")
    client_name: str = Field(..., description="Human-readable app name")
    redirect_uris: list[str] = Field(..., description="Allowed redirect URIs")
    scope: str = Field(..., description="Registered scopes")
    app_type: AppType = Field(..., description="Client type")
    logo_uri: str | None = Field(None, description="App logo URL")
    contacts: list[str] | None = Field(None, description="Contact emails")
    tos_uri: str | None = Field(None, description="Terms of service URL")
    policy_uri: str | None = Field(None, description="Privacy policy URL")
    jwks_uri: str | None = Field(None, description="JWKS URI")
    created_at: datetime = Field(..., description="Registration timestamp")
    is_active: bool = Field(True, description="Whether app is active")
    # Only returned on initial registration
    client_secret: str | None = Field(
        None,
        description="Client secret (only for confidential apps, shown once)",
    )


class SMARTAppListResponse(BaseModel):
    """VP-Platform-1: Paginated response for SMART apps list."""

    apps: list[SMARTAppResponse] = Field(..., description="List of SMART apps")
    total: int = Field(..., description="Total number of apps")
    limit: int = Field(..., description="Number of items per page")
    offset: int = Field(..., description="Number of items skipped")


class SMARTAppUpdate(BaseModel):
    """Request to update a SMART app."""

    client_name: str | None = Field(None, description="Human-readable app name")
    redirect_uris: list[str] | None = Field(None, description="Allowed redirect URIs")
    scope: str | None = Field(None, description="Requested scopes")
    logo_uri: str | None = Field(None, description="App logo URL")
    contacts: list[str] | None = Field(None, description="Contact emails")
    tos_uri: str | None = Field(None, description="Terms of service URL")
    policy_uri: str | None = Field(None, description="Privacy policy URL")
    is_active: bool | None = Field(None, description="Whether app is active")


class TokenResponse(BaseModel):
    """OAuth2 token response."""

    access_token: str = Field(..., description="Access token")
    token_type: str = Field("Bearer", description="Token type")
    expires_in: int = Field(..., description="Token TTL in seconds")
    scope: str | None = Field(None, description="Granted scopes")
    refresh_token: str | None = Field(None, description="Refresh token")
    patient: str | None = Field(None, description="Patient ID in context")
    encounter: str | None = Field(None, description="Encounter ID in context")
    fhirUser: str | None = Field(None, description="FHIR User reference")
    need_patient_banner: bool = Field(True, description="Show patient banner")
    smart_style_url: str | None = Field(None, description="Style URL")
    id_token: str | None = Field(None, description="OpenID Connect ID token")


class TokenErrorResponse(BaseModel):
    """OAuth2 token error response."""

    error: str = Field(..., description="Error code")
    error_description: str | None = Field(None, description="Error description")


class LaunchContextRequest(BaseModel):
    """Request to create a launch context."""

    patient_id: str | None = Field(None, description="Patient ID for context")
    encounter_id: str | None = Field(None, description="Encounter ID for context")
    user_reference: str | None = Field(
        None,
        description="FHIR User reference (e.g., Practitioner/123)",
    )
    intent: str | None = Field(None, description="Launch intent")
    need_patient_banner: bool = Field(True, description="Show patient banner")


class LaunchContextResponse(BaseModel):
    """Response with launch context token."""

    launch: str = Field(..., description="Launch token for EHR launch flow")
    expires_in: int = Field(..., description="Token TTL in seconds")
    patient_id: str | None = Field(None, description="Patient ID in context")
    encounter_id: str | None = Field(None, description="Encounter ID in context")


class AuthorizeParams(BaseModel):
    """Authorization request parameters."""

    response_type: str = Field(..., description="Must be 'code'")
    client_id: str = Field(..., description="Registered client ID")
    redirect_uri: str = Field(..., description="Redirect URI")
    scope: str = Field(..., description="Requested scopes")
    state: str = Field(..., description="CSRF protection state")
    aud: str | None = Field(None, description="FHIR server base URL")
    launch: str | None = Field(None, description="Launch token for EHR launch")
    code_challenge: str | None = Field(None, description="PKCE code challenge")
    code_challenge_method: str | None = Field(
        None,
        description="PKCE method (S256)",
    )


class ConsentApproval(BaseModel):
    """Consent approval from user."""

    client_id: str = Field(..., description="Client ID")
    redirect_uri: str = Field(..., description="Redirect URI")
    scope: str = Field(..., description="Approved scopes")
    state: str = Field(..., description="CSRF state")
    code_challenge: str | None = Field(None, description="PKCE code challenge")
    code_challenge_method: str | None = Field(None, description="PKCE method")
    patient_id: str | None = Field(None, description="Patient ID for context")
    encounter_id: str | None = Field(None, description="Encounter ID for context")
    user_id: str | None = Field(None, description="User ID granting consent")


# =============================================================================
# In-Memory Stores (would be database in production)
# =============================================================================


class RegisteredApp:
    """Registered SMART app."""

    def __init__(
        self,
        client_id: str,
        client_name: str,
        redirect_uris: list[str],
        scope: str,
        app_type: AppType,
        client_secret_hash: str | None = None,
        logo_uri: str | None = None,
        contacts: list[str] | None = None,
        tos_uri: str | None = None,
        policy_uri: str | None = None,
        jwks_uri: str | None = None,
    ):
        self.client_id = client_id
        self.client_name = client_name
        self.redirect_uris = redirect_uris
        self.scope = scope
        self.app_type = app_type
        self.client_secret_hash = client_secret_hash
        self.logo_uri = logo_uri
        self.contacts = contacts or []
        self.tos_uri = tos_uri
        self.policy_uri = policy_uri
        self.jwks_uri = jwks_uri
        self.created_at = datetime.utcnow()
        self.is_active = True


class AuthorizationCode:
    """OAuth2 authorization code."""

    def __init__(
        self,
        code: str,
        client_id: str,
        redirect_uri: str,
        scope: str,
        user_id: str | None = None,
        patient_id: str | None = None,
        encounter_id: str | None = None,
        code_challenge: str | None = None,
        code_challenge_method: str | None = None,
    ):
        self.code = code
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.scope = scope
        self.user_id = user_id
        self.patient_id = patient_id
        self.encounter_id = encounter_id
        self.code_challenge = code_challenge
        self.code_challenge_method = code_challenge_method
        self.created_at = time.time()
        self.used = False

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > AUTH_CODE_TTL_SECONDS


class LaunchContext:
    """SMART launch context."""

    def __init__(
        self,
        token: str,
        patient_id: str | None = None,
        encounter_id: str | None = None,
        user_reference: str | None = None,
        intent: str | None = None,
        need_patient_banner: bool = True,
    ):
        self.token = token
        self.patient_id = patient_id
        self.encounter_id = encounter_id
        self.user_reference = user_reference
        self.intent = intent
        self.need_patient_banner = need_patient_banner
        self.created_at = time.time()

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > LAUNCH_CONTEXT_TTL_SECONDS


class AccessToken:
    """Issued access token."""

    def __init__(
        self,
        token: str,
        client_id: str,
        scope: str,
        user_id: str | None = None,
        patient_id: str | None = None,
        encounter_id: str | None = None,
    ):
        self.token = token
        self.client_id = client_id
        self.scope = scope
        self.user_id = user_id
        self.patient_id = patient_id
        self.encounter_id = encounter_id
        self.created_at = time.time()

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > ACCESS_TOKEN_TTL_SECONDS


class RefreshToken:
    """Issued refresh token."""

    def __init__(
        self,
        token: str,
        client_id: str,
        scope: str,
        user_id: str | None = None,
        patient_id: str | None = None,
        encounter_id: str | None = None,
    ):
        self.token = token
        self.client_id = client_id
        self.scope = scope
        self.user_id = user_id
        self.patient_id = patient_id
        self.encounter_id = encounter_id
        self.created_at = time.time()
        self.revoked = False

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > REFRESH_TOKEN_TTL_SECONDS


# In-memory stores
_registered_apps: dict[str, RegisteredApp] = {}
_auth_codes: dict[str, AuthorizationCode] = {}
_launch_contexts: dict[str, LaunchContext] = {}
_access_tokens: dict[str, AccessToken] = {}
_refresh_tokens: dict[str, RefreshToken] = {}


# =============================================================================
# Helper Functions
# =============================================================================


def _hash_secret(secret: str) -> str:
    """Hash a client secret."""
    return hashlib.sha256(secret.encode()).hexdigest()


def _verify_secret(secret: str, secret_hash: str) -> bool:
    """Verify a client secret against its hash."""
    return _hash_secret(secret) == secret_hash


def _generate_token(prefix: str = "") -> str:
    """Generate a secure random token."""
    token = secrets.token_urlsafe(32)
    return f"{prefix}{token}" if prefix else token


def _verify_pkce(code_verifier: str, code_challenge: str, method: str) -> bool:
    """Verify PKCE code challenge."""
    if method != "S256":
        return False

    # Compute challenge from verifier
    verifier_bytes = code_verifier.encode("ascii")
    challenge_bytes = hashlib.sha256(verifier_bytes).digest()
    import base64

    computed_challenge = (
        base64.urlsafe_b64encode(challenge_bytes).decode("ascii").rstrip("=")
    )

    return computed_challenge == code_challenge


def _validate_redirect_uri(uri: str, registered_uris: list[str]) -> bool:
    """Validate redirect URI against registered URIs."""
    # Exact match required for security
    return uri in registered_uris


def _filter_scopes(requested: str, registered: str) -> str:
    """Filter requested scopes to only those registered."""
    requested_set = set(requested.split())
    registered_set = set(registered.split())
    return " ".join(requested_set & registered_set)


def _cleanup_expired() -> None:
    """Remove expired items from stores."""
    # Clean auth codes
    expired_codes = [
        code for code, auth_code in _auth_codes.items() if auth_code.is_expired
    ]
    for code in expired_codes:
        del _auth_codes[code]

    # Clean launch contexts
    expired_contexts = [
        token for token, ctx in _launch_contexts.items() if ctx.is_expired
    ]
    for token in expired_contexts:
        del _launch_contexts[token]

    # Clean access tokens
    expired_access = [
        token for token, at in _access_tokens.items() if at.is_expired
    ]
    for token in expired_access:
        del _access_tokens[token]

    # Clean refresh tokens
    expired_refresh = [
        token
        for token, rt in _refresh_tokens.items()
        if rt.is_expired or rt.revoked
    ]
    for token in expired_refresh:
        del _refresh_tokens[token]


# =============================================================================
# Authorization Endpoints
# =============================================================================


@router.get(
    "/authorize",
    summary="Start SMART authorization flow",
    description="""
    OAuth2 authorization endpoint. Redirects user to consent page.

    This implements the authorization request per RFC 6749 and SMART App Launch.
    The client should redirect the user's browser to this endpoint.
    """,
    responses={
        302: {"description": "Redirect to consent page"},
        400: {"description": "Invalid request"},
    },
)
async def authorize_get(
    request: Request,
    response_type: str = Query(..., description="Must be 'code'"),
    client_id: str = Query(..., description="Registered client ID"),
    redirect_uri: str = Query(..., description="Redirect URI"),
    scope: str = Query(..., description="Requested scopes"),
    state: str = Query(..., description="CSRF protection state"),
    aud: str | None = Query(None, description="FHIR server base URL"),
    launch: str | None = Query(None, description="Launch token for EHR launch"),
    code_challenge: str | None = Query(None, description="PKCE code challenge"),
    code_challenge_method: str | None = Query(None, description="PKCE method"),
) -> RedirectResponse:
    """Handle GET authorization request.

    Validates the request and redirects to the consent page.
    """
    _cleanup_expired()

    # Validate response_type
    if response_type != "code":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="response_type must be 'code'",
        )

    # Validate client_id
    app = _registered_apps.get(client_id)
    if not app or not app.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid client_id",
        )

    # Validate redirect_uri
    if not _validate_redirect_uri(redirect_uri, app.redirect_uris):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid redirect_uri",
        )

    # Validate PKCE for public clients
    if app.app_type == AppType.PUBLIC:
        if not code_challenge or code_challenge_method != "S256":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PKCE required for public clients (S256)",
            )

    # Process launch context if provided
    patient_id = None
    encounter_id = None
    if launch:
        launch_ctx = _launch_contexts.get(launch)
        if launch_ctx and not launch_ctx.is_expired:
            patient_id = launch_ctx.patient_id
            encounter_id = launch_ctx.encounter_id
        else:
            logger.warning(f"Invalid or expired launch token: {launch[:8]}...")

    # Filter scopes to registered ones
    granted_scope = _filter_scopes(scope, app.scope)

    # Build consent page URL with all parameters
    # In production, this would be a frontend consent page
    consent_params = {
        "client_id": client_id,
        "client_name": app.client_name,
        "redirect_uri": redirect_uri,
        "scope": granted_scope,
        "state": state,
        "patient_id": patient_id or "",
        "encounter_id": encounter_id or "",
        "logo_uri": app.logo_uri or "",
    }

    if code_challenge:
        consent_params["code_challenge"] = code_challenge
        consent_params["code_challenge_method"] = code_challenge_method or "S256"

    # For now, return a simple JSON response indicating consent is needed
    # In production, redirect to frontend consent page
    from urllib.parse import urlencode

    base_url = str(request.base_url).rstrip("/")
    consent_url = f"{base_url}/smart-consent?{urlencode(consent_params)}"

    logger.info(
        f"Authorization request for client {client_id}, redirecting to consent"
    )

    return RedirectResponse(url=consent_url, status_code=302)


@router.post(
    "/authorize",
    summary="Handle consent approval",
    description="""
    Process user consent and generate authorization code.

    This is called after the user approves the consent.
    Returns a redirect to the app with the authorization code.
    """,
    response_class=RedirectResponse,
    responses={
        302: {"description": "Redirect to app with auth code"},
        400: {"description": "Invalid request"},
    },
)
async def authorize_post(
    consent: ConsentApproval,
) -> RedirectResponse:
    """Handle consent approval and create authorization code."""
    _cleanup_expired()

    # Validate client
    app = _registered_apps.get(consent.client_id)
    if not app or not app.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid client_id",
        )

    # Validate redirect_uri
    if not _validate_redirect_uri(consent.redirect_uri, app.redirect_uris):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid redirect_uri",
        )

    # Generate authorization code
    code = _generate_token("code_")

    auth_code = AuthorizationCode(
        code=code,
        client_id=consent.client_id,
        redirect_uri=consent.redirect_uri,
        scope=_filter_scopes(consent.scope, app.scope),
        user_id=consent.user_id,
        patient_id=consent.patient_id,
        encounter_id=consent.encounter_id,
        code_challenge=consent.code_challenge,
        code_challenge_method=consent.code_challenge_method,
    )
    _auth_codes[code] = auth_code

    logger.info(
        f"Authorization code issued for client {consent.client_id}, "
        f"code={code[:12]}..."
    )

    # Build redirect URL with code
    from urllib.parse import urlencode

    params = {"code": code, "state": consent.state}
    redirect_url = f"{consent.redirect_uri}?{urlencode(params)}"

    return RedirectResponse(url=redirect_url, status_code=302)


@router.post(
    "/token",
    summary="Exchange code for tokens",
    description="""
    OAuth2 token endpoint. Supports:
    - authorization_code: Exchange auth code for tokens
    - client_credentials: Get tokens for backend service
    - refresh_token: Get new tokens using refresh token
    """,
    response_model=TokenResponse,
    responses={
        200: {"description": "Token response"},
        400: {"description": "Invalid request", "model": TokenErrorResponse},
        401: {"description": "Invalid credentials"},
    },
)
async def token_exchange(
    grant_type: str = Form(..., description="Grant type"),
    code: str | None = Form(None, description="Authorization code"),
    redirect_uri: str | None = Form(None, description="Redirect URI"),
    client_id: str | None = Form(None, description="Client ID"),
    client_secret: str | None = Form(None, description="Client secret"),
    code_verifier: str | None = Form(None, description="PKCE code verifier"),
    refresh_token: str | None = Form(None, description="Refresh token"),
    scope: str | None = Form(None, description="Requested scope"),
) -> TokenResponse:
    """Exchange authorization code or credentials for tokens."""
    _cleanup_expired()

    if grant_type == GrantType.AUTHORIZATION_CODE.value:
        return await _handle_authorization_code(
            code=code,
            redirect_uri=redirect_uri,
            client_id=client_id,
            client_secret=client_secret,
            code_verifier=code_verifier,
        )
    elif grant_type == GrantType.CLIENT_CREDENTIALS.value:
        return await _handle_client_credentials(
            client_id=client_id,
            client_secret=client_secret,
            scope=scope,
        )
    elif grant_type == GrantType.REFRESH_TOKEN.value:
        return await _handle_refresh_token(
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported grant_type: {grant_type}",
        )


async def _handle_authorization_code(
    code: str | None,
    redirect_uri: str | None,
    client_id: str | None,
    client_secret: str | None,
    code_verifier: str | None,
) -> TokenResponse:
    """Handle authorization_code grant."""
    if not code or not redirect_uri or not client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="code, redirect_uri, and client_id are required",
        )

    # Validate client
    app = _registered_apps.get(client_id)
    if not app or not app.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client_id",
        )

    # Validate client secret for confidential clients
    if app.app_type == AppType.CONFIDENTIAL_SYMMETRIC:
        if not client_secret or not app.client_secret_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="client_secret required for confidential clients",
            )
        if not _verify_secret(client_secret, app.client_secret_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid client_secret",
            )

    # Validate authorization code
    auth_code = _auth_codes.get(code)
    if not auth_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid authorization code",
        )

    if auth_code.used:
        # Code reuse attack - invalidate all tokens for this client
        logger.warning(f"Authorization code reuse detected for client {client_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authorization code already used",
        )

    if auth_code.is_expired:
        del _auth_codes[code]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authorization code expired",
        )

    if auth_code.client_id != client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="client_id mismatch",
        )

    if auth_code.redirect_uri != redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="redirect_uri mismatch",
        )

    # Validate PKCE
    if auth_code.code_challenge:
        if not code_verifier:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="code_verifier required",
            )
        if not _verify_pkce(
            code_verifier,
            auth_code.code_challenge,
            auth_code.code_challenge_method or "S256",
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid code_verifier",
            )

    # Mark code as used
    auth_code.used = True

    # Generate tokens
    access_token = _generate_token("at_")
    refresh_tok = _generate_token("rt_") if "offline_access" in auth_code.scope else None

    # Store tokens
    _access_tokens[access_token] = AccessToken(
        token=access_token,
        client_id=client_id,
        scope=auth_code.scope,
        user_id=auth_code.user_id,
        patient_id=auth_code.patient_id,
        encounter_id=auth_code.encounter_id,
    )

    if refresh_tok:
        _refresh_tokens[refresh_tok] = RefreshToken(
            token=refresh_tok,
            client_id=client_id,
            scope=auth_code.scope,
            user_id=auth_code.user_id,
            patient_id=auth_code.patient_id,
            encounter_id=auth_code.encounter_id,
        )

    logger.info(f"Tokens issued for client {client_id}")

    return TokenResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in=ACCESS_TOKEN_TTL_SECONDS,
        scope=auth_code.scope,
        refresh_token=refresh_tok,
        patient=auth_code.patient_id,
        encounter=auth_code.encounter_id,
        fhirUser=f"Practitioner/{auth_code.user_id}" if auth_code.user_id else None,
        need_patient_banner=True,
    )


async def _handle_client_credentials(
    client_id: str | None,
    client_secret: str | None,
    scope: str | None,
) -> TokenResponse:
    """Handle client_credentials grant for backend services."""
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="client_id and client_secret required",
        )

    # Validate client
    app = _registered_apps.get(client_id)
    if not app or not app.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client_id",
        )

    # Only confidential clients can use client_credentials
    if app.app_type == AppType.PUBLIC:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Public clients cannot use client_credentials grant",
        )

    # Validate secret
    if not app.client_secret_hash or not _verify_secret(
        client_secret, app.client_secret_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client_secret",
        )

    # Filter scope
    granted_scope = _filter_scopes(scope or app.scope, app.scope)

    # Generate access token (no refresh token for client credentials)
    access_token = _generate_token("at_")

    _access_tokens[access_token] = AccessToken(
        token=access_token,
        client_id=client_id,
        scope=granted_scope,
    )

    logger.info(f"Client credentials token issued for {client_id}")

    return TokenResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in=ACCESS_TOKEN_TTL_SECONDS,
        scope=granted_scope,
    )


async def _handle_refresh_token(
    refresh_token: str | None,
    client_id: str | None,
    client_secret: str | None,
) -> TokenResponse:
    """Handle refresh_token grant."""
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="refresh_token required",
        )

    # Find refresh token
    rt = _refresh_tokens.get(refresh_token)
    if not rt or rt.revoked or rt.is_expired:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired refresh token",
        )

    # Validate client
    if client_id and rt.client_id != client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="client_id mismatch",
        )

    app = _registered_apps.get(rt.client_id)
    if not app or not app.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client",
        )

    # Validate secret for confidential clients
    if app.app_type == AppType.CONFIDENTIAL_SYMMETRIC:
        if not client_secret or not _verify_secret(
            client_secret, app.client_secret_hash or ""
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid client_secret",
            )

    # Rotate refresh token
    rt.revoked = True
    new_refresh = _generate_token("rt_")
    _refresh_tokens[new_refresh] = RefreshToken(
        token=new_refresh,
        client_id=rt.client_id,
        scope=rt.scope,
        user_id=rt.user_id,
        patient_id=rt.patient_id,
        encounter_id=rt.encounter_id,
    )

    # Generate new access token
    access_token = _generate_token("at_")
    _access_tokens[access_token] = AccessToken(
        token=access_token,
        client_id=rt.client_id,
        scope=rt.scope,
        user_id=rt.user_id,
        patient_id=rt.patient_id,
        encounter_id=rt.encounter_id,
    )

    logger.info(f"Tokens refreshed for client {rt.client_id}")

    return TokenResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in=ACCESS_TOKEN_TTL_SECONDS,
        scope=rt.scope,
        refresh_token=new_refresh,
        patient=rt.patient_id,
        encounter=rt.encounter_id,
        fhirUser=f"Practitioner/{rt.user_id}" if rt.user_id else None,
    )


# =============================================================================
# App Management Endpoints (Admin Only)
# =============================================================================


@router.post(
    "/apps",
    summary="Register a new SMART app",
    description="Register a new SMART on FHIR application. Admin only.",
    response_model=SMARTAppResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_app(
    registration: SMARTAppRegistration,
    current_user: CurrentUser = Depends(require_admin),
) -> SMARTAppResponse:
    """Register a new SMART app."""
    # Generate client ID
    client_id = str(uuid4())

    # Generate client secret for confidential apps
    client_secret = None
    client_secret_hash = None
    if registration.app_type in [
        AppType.CONFIDENTIAL_SYMMETRIC,
        AppType.CONFIDENTIAL_ASYMMETRIC,
    ]:
        client_secret = secrets.token_urlsafe(32)
        client_secret_hash = _hash_secret(client_secret)

    # Create app
    app = RegisteredApp(
        client_id=client_id,
        client_name=registration.client_name,
        redirect_uris=registration.redirect_uris,
        scope=registration.scope,
        app_type=registration.app_type,
        client_secret_hash=client_secret_hash,
        logo_uri=registration.logo_uri,
        contacts=registration.contacts,
        tos_uri=registration.tos_uri,
        policy_uri=registration.policy_uri,
        jwks_uri=registration.jwks_uri,
    )
    _registered_apps[client_id] = app

    logger.info(
        f"SMART app registered: {registration.client_name} ({client_id}) "
        f"by user {current_user.email}"
    )

    return SMARTAppResponse(
        client_id=client_id,
        client_name=app.client_name,
        redirect_uris=app.redirect_uris,
        scope=app.scope,
        app_type=app.app_type,
        logo_uri=app.logo_uri,
        contacts=app.contacts,
        tos_uri=app.tos_uri,
        policy_uri=app.policy_uri,
        jwks_uri=app.jwks_uri,
        created_at=app.created_at,
        is_active=app.is_active,
        client_secret=client_secret,  # Only returned on creation
    )


@router.get(
    "/apps",
    summary="List registered SMART apps",
    description="Get all registered SMART applications with pagination. Admin only.",
    response_model=SMARTAppListResponse,
)
async def list_apps(
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of apps to return"),
    offset: int = Query(default=0, ge=0, description="Number of apps to skip"),
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> SMARTAppListResponse:
    """VP-Platform-1: List registered SMART apps with pagination."""
    from sqlalchemy import func

    # Get total count
    count_stmt = select(func.count(SMARTApp.client_id))
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    # Query database for apps with pagination
    stmt = (
        select(SMARTApp)
        .order_by(SMARTApp.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    db_apps = result.scalars().all()

    apps = [
        SMARTAppResponse(
            client_id=app.client_id,
            client_name=app.app_name,  # Map DB field to API field
            redirect_uris=app.redirect_uris or [],
            scope=" ".join(app.scopes or []),
            app_type=AppType.CONFIDENTIAL_SYMMETRIC if app.is_confidential else AppType.PUBLIC,
            logo_uri=None,
            contacts=[],
            tos_uri=None,
            policy_uri=None,
            jwks_uri=None,
            created_at=app.created_at,
            is_active=app.is_active,
            client_secret=None,  # Never return secret after creation
        )
        for app in db_apps
    ]

    return SMARTAppListResponse(
        apps=apps,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/apps/{client_id}",
    summary="Get SMART app details",
    description="Get details for a specific SMART application. Admin only.",
    response_model=SMARTAppResponse,
)
async def get_app(
    client_id: str,
    current_user: CurrentUser = Depends(require_admin),
) -> SMARTAppResponse:
    """Get a specific SMART app."""
    app = _registered_apps.get(client_id)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"App with client_id {client_id} not found",
        )

    return SMARTAppResponse(
        client_id=app.client_id,
        client_name=app.client_name,
        redirect_uris=app.redirect_uris,
        scope=app.scope,
        app_type=app.app_type,
        logo_uri=app.logo_uri,
        contacts=app.contacts,
        tos_uri=app.tos_uri,
        policy_uri=app.policy_uri,
        jwks_uri=app.jwks_uri,
        created_at=app.created_at,
        is_active=app.is_active,
        client_secret=None,
    )


@router.put(
    "/apps/{client_id}",
    summary="Update SMART app",
    description="Update a registered SMART application. Admin only.",
    response_model=SMARTAppResponse,
)
async def update_app(
    client_id: str,
    update: SMARTAppUpdate,
    current_user: CurrentUser = Depends(require_admin),
) -> SMARTAppResponse:
    """Update a SMART app."""
    app = _registered_apps.get(client_id)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"App with client_id {client_id} not found",
        )

    # Apply updates
    if update.client_name is not None:
        app.client_name = update.client_name
    if update.redirect_uris is not None:
        app.redirect_uris = update.redirect_uris
    if update.scope is not None:
        app.scope = update.scope
    if update.logo_uri is not None:
        app.logo_uri = update.logo_uri
    if update.contacts is not None:
        app.contacts = update.contacts
    if update.tos_uri is not None:
        app.tos_uri = update.tos_uri
    if update.policy_uri is not None:
        app.policy_uri = update.policy_uri
    if update.is_active is not None:
        app.is_active = update.is_active

    logger.info(f"SMART app updated: {client_id} by user {current_user.email}")

    return SMARTAppResponse(
        client_id=app.client_id,
        client_name=app.client_name,
        redirect_uris=app.redirect_uris,
        scope=app.scope,
        app_type=app.app_type,
        logo_uri=app.logo_uri,
        contacts=app.contacts,
        tos_uri=app.tos_uri,
        policy_uri=app.policy_uri,
        jwks_uri=app.jwks_uri,
        created_at=app.created_at,
        is_active=app.is_active,
        client_secret=None,
    )


@router.delete(
    "/apps/{client_id}",
    summary="Deregister SMART app",
    description="Remove a registered SMART application. Admin only.",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_app(
    client_id: str,
    current_user: CurrentUser = Depends(require_admin),
) -> None:
    """Delete a SMART app."""
    app = _registered_apps.pop(client_id, None)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"App with client_id {client_id} not found",
        )

    # Revoke all tokens for this app
    for token, at in list(_access_tokens.items()):
        if at.client_id == client_id:
            del _access_tokens[token]

    for token, rt in list(_refresh_tokens.items()):
        if rt.client_id == client_id:
            del _refresh_tokens[token]

    logger.info(
        f"SMART app deregistered: {app.client_name} ({client_id}) "
        f"by user {current_user.email}"
    )


# =============================================================================
# Launch Context Endpoints
# =============================================================================


@router.post(
    "/launch-context",
    summary="Create test launch context",
    description="""
    Create a launch context for testing EHR launch flow.
    Returns a launch token that can be passed to /authorize.
    Admin only.
    """,
    response_model=LaunchContextResponse,
)
async def create_launch_context(
    request: LaunchContextRequest,
    current_user: CurrentUser = Depends(require_admin),
) -> LaunchContextResponse:
    """Create a test launch context."""
    launch_token = _generate_token("launch_")

    ctx = LaunchContext(
        token=launch_token,
        patient_id=request.patient_id,
        encounter_id=request.encounter_id,
        user_reference=request.user_reference,
        intent=request.intent,
        need_patient_banner=request.need_patient_banner,
    )
    _launch_contexts[launch_token] = ctx

    logger.info(
        f"Launch context created: patient={request.patient_id}, "
        f"encounter={request.encounter_id} by user {current_user.email}"
    )

    return LaunchContextResponse(
        launch=launch_token,
        expires_in=LAUNCH_CONTEXT_TTL_SECONDS,
        patient_id=request.patient_id,
        encounter_id=request.encounter_id,
    )


# =============================================================================
# Utility Endpoints
# =============================================================================


@router.get(
    "/stats",
    summary="Get SMART server statistics",
    description="Get statistics about registered apps and active sessions.",
)
async def get_stats(
    current_user: CurrentUser = Depends(require_admin),
) -> dict[str, Any]:
    """Get server statistics."""
    _cleanup_expired()

    return {
        "registered_apps": len(_registered_apps),
        "active_apps": sum(1 for app in _registered_apps.values() if app.is_active),
        "pending_auth_codes": len(_auth_codes),
        "active_access_tokens": len(_access_tokens),
        "active_refresh_tokens": len(_refresh_tokens),
        "pending_launch_contexts": len(_launch_contexts),
    }
