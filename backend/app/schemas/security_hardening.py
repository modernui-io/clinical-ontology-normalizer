"""Pydantic schemas for Security Hardening (CISO-2/3/4).

Provides request/response models for the security hardening API including:
- TLS configuration and profiles (CISO-2)
- Auth defaults: password policy, session config, JWT, lockout, MFA (CISO-3)
- CORS configuration and profiles (CISO-4)
- Security audit reports with scoring and remediation
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ============================================================================
# Enums
# ============================================================================


class CheckStatus(str, Enum):
    """Status of an individual security check."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class TLSVersion(str, Enum):
    """TLS protocol versions."""

    TLS_1_0 = "TLSv1.0"
    TLS_1_1 = "TLSv1.1"
    TLS_1_2 = "TLSv1.2"
    TLS_1_3 = "TLSv1.3"


class TLSProfileName(str, Enum):
    """Pre-defined TLS configuration profiles."""

    MODERN = "MODERN"
    INTERMEDIATE = "INTERMEDIATE"
    OLD = "OLD"


class CORSProfileName(str, Enum):
    """Pre-defined CORS configuration profiles."""

    STRICT = "STRICT"
    DEVELOPMENT = "DEVELOPMENT"
    API_ONLY = "API_ONLY"


class SecurityDomain(str, Enum):
    """Security domain categories."""

    TLS = "TLS"
    AUTH = "AUTH"
    CORS = "CORS"


class MFARequirement(str, Enum):
    """MFA requirement levels."""

    DISABLED = "DISABLED"
    RECOMMENDED = "RECOMMENDED"
    REQUIRED_ADMIN = "REQUIRED_ADMIN"
    REQUIRED_ALL = "REQUIRED_ALL"


class JWTAlgorithm(str, Enum):
    """Supported JWT signing algorithms."""

    HS256 = "HS256"
    HS384 = "HS384"
    HS512 = "HS512"
    RS256 = "RS256"
    RS384 = "RS384"
    RS512 = "RS512"
    ES256 = "ES256"
    ES384 = "ES384"


# ============================================================================
# TLS Schemas (CISO-2)
# ============================================================================


class CipherSuite(BaseModel):
    """A TLS cipher suite with security classification."""

    name: str = Field(..., description="Cipher suite name (e.g., TLS_AES_256_GCM_SHA384)")
    strength: str = Field(..., description="Strength classification: strong, acceptable, weak")
    key_exchange: str = Field("", description="Key exchange algorithm")
    authentication: str = Field("", description="Authentication algorithm")
    encryption: str = Field("", description="Encryption algorithm")
    mac: str = Field("", description="MAC algorithm")


class HSTSConfig(BaseModel):
    """HTTP Strict Transport Security configuration."""

    enabled: bool = Field(True, description="Whether HSTS is enabled")
    max_age: int = Field(31536000, description="Max-age in seconds (default 1 year)")
    include_subdomains: bool = Field(True, description="Include subdomains directive")
    preload: bool = Field(False, description="Preload directive for browser preload lists")

    @property
    def header_value(self) -> str:
        """Build the HSTS header string."""
        parts = [f"max-age={self.max_age}"]
        if self.include_subdomains:
            parts.append("includeSubDomains")
        if self.preload:
            parts.append("preload")
        return "; ".join(parts)


class CertificateInfo(BaseModel):
    """TLS certificate information."""

    subject: str = Field("", description="Certificate subject CN")
    issuer: str = Field("", description="Certificate issuer")
    not_before: Optional[datetime] = Field(None, description="Certificate validity start")
    not_after: Optional[datetime] = Field(None, description="Certificate validity end")
    days_until_expiry: Optional[int] = Field(None, description="Days until certificate expires")
    is_expired: bool = Field(False, description="Whether certificate is expired")
    is_self_signed: bool = Field(False, description="Whether certificate is self-signed")
    chain_valid: bool = Field(True, description="Whether certificate chain is valid")
    transparency_logged: bool = Field(False, description="Whether CT log is present")


class TLSConfig(BaseModel):
    """Complete TLS configuration."""

    minimum_version: TLSVersion = Field(
        TLSVersion.TLS_1_2, description="Minimum TLS version allowed"
    )
    preferred_version: TLSVersion = Field(
        TLSVersion.TLS_1_3, description="Preferred TLS version"
    )
    allowed_cipher_suites: list[str] = Field(
        default_factory=list, description="Allowed cipher suite names"
    )
    hsts: HSTSConfig = Field(default_factory=HSTSConfig, description="HSTS configuration")
    certificate: Optional[CertificateInfo] = Field(
        None, description="Certificate information (if available)"
    )
    ocsp_stapling: bool = Field(True, description="OCSP stapling enabled")
    session_tickets: bool = Field(False, description="TLS session tickets (disable for forward secrecy)")
    profile: TLSProfileName = Field(
        TLSProfileName.INTERMEDIATE, description="Active TLS profile"
    )


class TLSProfile(BaseModel):
    """A pre-defined TLS configuration profile."""

    name: TLSProfileName = Field(..., description="Profile name")
    description: str = Field(..., description="Profile description")
    minimum_version: TLSVersion = Field(..., description="Minimum TLS version")
    preferred_version: TLSVersion = Field(..., description="Preferred TLS version")
    cipher_suites: list[str] = Field(..., description="Allowed cipher suites")
    recommended_for: str = Field(..., description="Recommended use case")
    security_level: str = Field(..., description="Security level: high, medium, low")


# ============================================================================
# Auth Schemas (CISO-3)
# ============================================================================


class PasswordPolicy(BaseModel):
    """Password policy configuration."""

    min_length: int = Field(12, description="Minimum password length")
    require_uppercase: bool = Field(True, description="Require uppercase letter")
    require_lowercase: bool = Field(True, description="Require lowercase letter")
    require_digit: bool = Field(True, description="Require digit")
    require_special: bool = Field(True, description="Require special character")
    special_characters: str = Field(
        "!@#$%^&*()_+-=[]{}|;:',.<>?/`~",
        description="Allowed special characters",
    )
    max_length: int = Field(128, description="Maximum password length")
    prevent_reuse_count: int = Field(5, description="Number of previous passwords to block")
    max_age_days: int = Field(90, description="Maximum password age in days")


class SessionConfig(BaseModel):
    """Session configuration."""

    max_idle_minutes: int = Field(30, description="Max idle time before session expires")
    absolute_timeout_hours: int = Field(8, description="Absolute session timeout in hours")
    secure_cookie: bool = Field(True, description="Secure flag on session cookies")
    http_only: bool = Field(True, description="HttpOnly flag on session cookies")
    same_site: str = Field("Lax", description="SameSite cookie attribute: Strict, Lax, None")
    cookie_name: str = Field("session_id", description="Session cookie name")
    regenerate_on_auth: bool = Field(True, description="Regenerate session ID on authentication")


class JWTConfig(BaseModel):
    """JWT configuration."""

    algorithm: JWTAlgorithm = Field(JWTAlgorithm.RS256, description="Signing algorithm")
    access_token_expire_minutes: int = Field(15, description="Access token expiry in minutes")
    refresh_token_expire_days: int = Field(7, description="Refresh token expiry in days")
    issuer: str = Field("clinical-ontology-normalizer", description="Token issuer claim")
    audience: str = Field("clinical-ontology-api", description="Token audience claim")
    require_exp: bool = Field(True, description="Require expiration claim")
    require_iat: bool = Field(True, description="Require issued-at claim")
    leeway_seconds: int = Field(30, description="Clock skew leeway in seconds")


class AccountLockoutConfig(BaseModel):
    """Account lockout configuration."""

    max_failed_attempts: int = Field(5, description="Max failed login attempts before lockout")
    lockout_duration_minutes: int = Field(15, description="Initial lockout duration in minutes")
    progressive_backoff: bool = Field(True, description="Enable progressive lockout backoff")
    backoff_multiplier: float = Field(2.0, description="Multiplier for progressive backoff")
    max_lockout_minutes: int = Field(1440, description="Maximum lockout duration (24 hours)")
    reset_attempts_after_minutes: int = Field(
        60, description="Reset failed attempt counter after minutes"
    )


class MFAConfig(BaseModel):
    """Multi-factor authentication configuration."""

    requirement: MFARequirement = Field(
        MFARequirement.REQUIRED_ADMIN,
        description="MFA requirement level",
    )
    allowed_methods: list[str] = Field(
        default_factory=lambda: ["totp", "webauthn"],
        description="Allowed MFA methods",
    )
    totp_digits: int = Field(6, description="TOTP code digits")
    totp_period_seconds: int = Field(30, description="TOTP period in seconds")
    recovery_codes_count: int = Field(10, description="Number of recovery codes to generate")
    remember_device_days: int = Field(30, description="Remember trusted device for N days")


class APIKeyConfig(BaseModel):
    """API key management configuration."""

    rotation_interval_days: int = Field(90, description="Key rotation interval in days")
    max_keys_per_user: int = Field(5, description="Maximum active keys per user")
    rate_limit_per_key: int = Field(1000, description="Rate limit per key per hour")
    require_prefix: bool = Field(True, description="Require key prefix (e.g., 'sk_live_')")
    key_length: int = Field(48, description="Key length in characters")
    hash_algorithm: str = Field("sha256", description="Algorithm for storing key hashes")


class AuthConfig(BaseModel):
    """Complete auth defaults configuration."""

    password_policy: PasswordPolicy = Field(
        default_factory=PasswordPolicy, description="Password policy"
    )
    session: SessionConfig = Field(
        default_factory=SessionConfig, description="Session configuration"
    )
    jwt: JWTConfig = Field(default_factory=JWTConfig, description="JWT configuration")
    lockout: AccountLockoutConfig = Field(
        default_factory=AccountLockoutConfig, description="Account lockout policy"
    )
    mfa: MFAConfig = Field(default_factory=MFAConfig, description="MFA configuration")
    api_keys: APIKeyConfig = Field(
        default_factory=APIKeyConfig, description="API key management"
    )


# ============================================================================
# CORS Schemas (CISO-4)
# ============================================================================


class CORSConfig(BaseModel):
    """CORS configuration."""

    allowed_origins: list[str] = Field(
        default_factory=list, description="Allowed origins (no wildcards in production)"
    )
    allowed_methods: list[str] = Field(
        default_factory=lambda: ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        description="Allowed HTTP methods",
    )
    allowed_headers: list[str] = Field(
        default_factory=lambda: [
            "Content-Type",
            "Authorization",
            "X-Request-ID",
            "Accept",
        ],
        description="Allowed request headers",
    )
    expose_headers: list[str] = Field(
        default_factory=lambda: [
            "X-Request-ID",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
        ],
        description="Headers exposed to the browser",
    )
    allow_credentials: bool = Field(True, description="Allow credentials (cookies, auth headers)")
    max_age: int = Field(600, description="Preflight cache max age in seconds")
    profile: CORSProfileName = Field(
        CORSProfileName.DEVELOPMENT, description="Active CORS profile"
    )


class CORSProfile(BaseModel):
    """A pre-defined CORS configuration profile."""

    name: CORSProfileName = Field(..., description="Profile name")
    description: str = Field(..., description="Profile description")
    allowed_origins: list[str] = Field(..., description="Allowed origins")
    allowed_methods: list[str] = Field(..., description="Allowed methods")
    allow_credentials: bool = Field(..., description="Allow credentials")
    recommended_for: str = Field(..., description="Recommended environment")


class OriginValidationRequest(BaseModel):
    """Request to validate if an origin is allowed."""

    origin: str = Field(..., description="Origin URL to validate")


class OriginValidationResponse(BaseModel):
    """Response for origin validation."""

    origin: str = Field(..., description="Origin that was checked")
    allowed: bool = Field(..., description="Whether the origin is allowed")
    matched_rule: Optional[str] = Field(None, description="Rule that matched (if allowed)")
    reason: Optional[str] = Field(None, description="Reason for denial (if denied)")


# ============================================================================
# Audit & Reporting Schemas
# ============================================================================


class SecurityCheck(BaseModel):
    """Result of a single security check."""

    id: str = Field(..., description="Unique check identifier")
    domain: SecurityDomain = Field(..., description="Security domain (TLS, AUTH, CORS)")
    name: str = Field(..., description="Check name")
    description: str = Field(..., description="What the check verifies")
    status: CheckStatus = Field(..., description="Check result: PASS, WARN, FAIL")
    details: str = Field("", description="Additional details about the result")
    remediation: Optional[str] = Field(None, description="How to fix (if WARN or FAIL)")
    severity: str = Field("medium", description="Severity if failed: critical, high, medium, low")


class SecurityRecommendation(BaseModel):
    """A security improvement recommendation."""

    id: str = Field(..., description="Recommendation identifier")
    domain: SecurityDomain = Field(..., description="Security domain")
    title: str = Field(..., description="Recommendation title")
    description: str = Field(..., description="Detailed description")
    priority: str = Field(..., description="Priority: critical, high, medium, low")
    effort: str = Field(..., description="Estimated effort: low, medium, high")
    current_state: str = Field("", description="Current configuration state")
    recommended_state: str = Field("", description="Recommended configuration state")


class SecurityAuditReport(BaseModel):
    """Comprehensive security audit report."""

    timestamp: datetime = Field(..., description="When the audit was performed")
    environment: str = Field(..., description="Environment: development, staging, production")
    overall_score: int = Field(
        ..., ge=0, le=100, description="Overall security score (0-100)"
    )
    tls_score: int = Field(..., ge=0, le=100, description="TLS security score")
    auth_score: int = Field(..., ge=0, le=100, description="Auth security score")
    cors_score: int = Field(..., ge=0, le=100, description="CORS security score")
    checks: list[SecurityCheck] = Field(..., description="Individual check results")
    pass_count: int = Field(..., description="Number of passed checks")
    warn_count: int = Field(..., description="Number of warning checks")
    fail_count: int = Field(..., description="Number of failed checks")
    recommendations: list[SecurityRecommendation] = Field(
        default_factory=list, description="Improvement recommendations"
    )
    tls_config: TLSConfig = Field(..., description="Current TLS configuration")
    auth_config: AuthConfig = Field(..., description="Current auth configuration")
    cors_config: CORSConfig = Field(..., description="Current CORS configuration")


class SecurityRecommendationsResponse(BaseModel):
    """Response for security recommendations endpoint."""

    environment: str = Field(..., description="Current environment")
    total_recommendations: int = Field(..., description="Total number of recommendations")
    critical_count: int = Field(..., description="Number of critical recommendations")
    high_count: int = Field(..., description="Number of high-priority recommendations")
    recommendations: list[SecurityRecommendation] = Field(
        ..., description="Ordered recommendations"
    )
