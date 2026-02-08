"""Security Hardening API endpoints (CISO-2/3/4).

Exposes TLS enforcement, auth defaults hardening, and CORS tightening
configuration and audit endpoints.

Endpoints:
    GET  /security/audit             - Full security audit report
    GET  /security/tls/config        - Current TLS configuration
    GET  /security/tls/profiles      - Available TLS profiles
    GET  /security/auth/config       - Current auth configuration
    GET  /security/auth/policy       - Password and session policies
    GET  /security/cors/config       - Current CORS configuration
    GET  /security/cors/profiles     - Available CORS profiles
    POST /security/validate-origin   - Check if origin is allowed
    GET  /security/recommendations   - Security improvement recommendations
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, status

from app.schemas.security_hardening import (
    AuthConfig,
    CORSConfig,
    CORSProfile,
    OriginValidationRequest,
    OriginValidationResponse,
    PasswordPolicy,
    SecurityAuditReport,
    SecurityRecommendationsResponse,
    SessionConfig,
    TLSConfig,
    TLSProfile,
)
from app.services.security_hardening_service import get_security_hardening_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/security", tags=["Security Hardening"])


# ---------------------------------------------------------------------------
# Security Audit
# ---------------------------------------------------------------------------


@router.get(
    "/audit",
    response_model=SecurityAuditReport,
    summary="Run full security audit",
    description=(
        "Runs a comprehensive security audit across TLS, Auth, and CORS "
        "configurations. Returns per-check PASS/WARN/FAIL status, domain "
        "scores, overall score (0-100), and remediation recommendations."
    ),
)
async def security_audit() -> SecurityAuditReport:
    """Run full security audit and return report."""
    svc = get_security_hardening_service()
    return svc.run_audit()


# ---------------------------------------------------------------------------
# TLS (CISO-2)
# ---------------------------------------------------------------------------


@router.get(
    "/tls/config",
    response_model=TLSConfig,
    summary="Get current TLS configuration",
    description="Returns the active TLS configuration including version, ciphers, and HSTS settings.",
)
async def get_tls_config() -> TLSConfig:
    """Return current TLS configuration."""
    svc = get_security_hardening_service()
    return svc.tls_config


@router.get(
    "/tls/profiles",
    response_model=list[TLSProfile],
    summary="List available TLS profiles",
    description=(
        "Returns all pre-defined TLS profiles: MODERN (TLS 1.3 only), "
        "INTERMEDIATE (TLS 1.2+), OLD (not recommended)."
    ),
)
async def list_tls_profiles() -> list[TLSProfile]:
    """Return available TLS profiles."""
    svc = get_security_hardening_service()
    return svc.get_tls_profiles()


# ---------------------------------------------------------------------------
# Auth (CISO-3)
# ---------------------------------------------------------------------------


@router.get(
    "/auth/config",
    response_model=AuthConfig,
    summary="Get current auth configuration",
    description=(
        "Returns the complete auth configuration including password policy, "
        "session settings, JWT config, lockout rules, MFA, and API key management."
    ),
)
async def get_auth_config() -> AuthConfig:
    """Return current auth configuration."""
    svc = get_security_hardening_service()
    return svc.auth_config


class AuthPolicyResponse(PasswordPolicy):
    """Response combining password and session policies."""

    class Config:
        """Pydantic config."""


@router.get(
    "/auth/policy",
    summary="Get password and session policies",
    description="Returns the password policy and session configuration.",
)
async def get_auth_policy() -> dict:
    """Return password and session policies."""
    svc = get_security_hardening_service()
    auth = svc.auth_config
    return {
        "password_policy": auth.password_policy.model_dump(),
        "session_config": auth.session.model_dump(),
        "lockout_config": auth.lockout.model_dump(),
        "mfa_config": auth.mfa.model_dump(),
    }


# ---------------------------------------------------------------------------
# CORS (CISO-4)
# ---------------------------------------------------------------------------


@router.get(
    "/cors/config",
    response_model=CORSConfig,
    summary="Get current CORS configuration",
    description="Returns the active CORS configuration including origins, methods, and credentials.",
)
async def get_cors_config() -> CORSConfig:
    """Return current CORS configuration."""
    svc = get_security_hardening_service()
    return svc.cors_config


@router.get(
    "/cors/profiles",
    response_model=list[CORSProfile],
    summary="List available CORS profiles",
    description=(
        "Returns pre-defined CORS profiles: STRICT (specific origins), "
        "DEVELOPMENT (localhost), API_ONLY (no credentials)."
    ),
)
async def list_cors_profiles() -> list[CORSProfile]:
    """Return available CORS profiles."""
    svc = get_security_hardening_service()
    return svc.get_cors_profiles()


@router.post(
    "/validate-origin",
    response_model=OriginValidationResponse,
    summary="Validate an origin against CORS config",
    description="Checks whether a given origin URL is allowed by the current CORS configuration.",
)
async def validate_origin(request: OriginValidationRequest) -> OriginValidationResponse:
    """Validate if an origin is allowed."""
    svc = get_security_hardening_service()
    return svc.validate_origin(request.origin)


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


@router.get(
    "/recommendations",
    response_model=SecurityRecommendationsResponse,
    summary="Get security recommendations",
    description=(
        "Returns prioritized security improvement recommendations based on "
        "the current configuration. Ordered by priority: critical > high > medium > low."
    ),
)
async def get_recommendations() -> SecurityRecommendationsResponse:
    """Get security improvement recommendations."""
    svc = get_security_hardening_service()
    return svc.get_recommendations()
