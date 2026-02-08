"""Security Hardening Service (CISO-2/3/4).

Audits and enforces security configurations for:
- TLS enforcement: version, ciphers, HSTS, certificates (CISO-2)
- Auth defaults hardening: passwords, sessions, JWT, lockout, MFA (CISO-3)
- CORS tightening: origin allowlist, methods, credentials (CISO-4)

Produces a security audit report with per-check PASS/WARN/FAIL status,
an overall score (0-100), and remediation recommendations.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from app.core.config import settings
from app.schemas.security_hardening import (
    AccountLockoutConfig,
    APIKeyConfig,
    AuthConfig,
    CertificateInfo,
    CheckStatus,
    CipherSuite,
    CORSConfig,
    CORSProfile,
    CORSProfileName,
    HSTSConfig,
    JWTAlgorithm,
    JWTConfig,
    MFAConfig,
    MFARequirement,
    OriginValidationResponse,
    PasswordPolicy,
    SecurityAuditReport,
    SecurityCheck,
    SecurityDomain,
    SecurityRecommendation,
    SecurityRecommendationsResponse,
    SessionConfig,
    TLSConfig,
    TLSProfile,
    TLSProfileName,
    TLSVersion,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Strong cipher suites (TLS 1.3 + TLS 1.2 AEAD ciphers)
# ============================================================================

TLS_13_CIPHERS: list[str] = [
    "TLS_AES_256_GCM_SHA384",
    "TLS_AES_128_GCM_SHA256",
    "TLS_CHACHA20_POLY1305_SHA256",
]

TLS_12_STRONG_CIPHERS: list[str] = [
    "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384",
    "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",
    "TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256",
    "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384",
    "TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256",
    "TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256",
    "TLS_DHE_RSA_WITH_AES_256_GCM_SHA384",
    "TLS_DHE_RSA_WITH_AES_128_GCM_SHA256",
]

TLS_12_ACCEPTABLE_CIPHERS: list[str] = [
    "TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA384",
    "TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA256",
]

WEAK_CIPHERS: list[str] = [
    "TLS_RSA_WITH_AES_256_GCM_SHA384",
    "TLS_RSA_WITH_AES_128_GCM_SHA256",
    "TLS_RSA_WITH_AES_256_CBC_SHA256",
    "TLS_RSA_WITH_AES_128_CBC_SHA256",
    "TLS_RSA_WITH_3DES_EDE_CBC_SHA",
    "TLS_RSA_WITH_RC4_128_SHA",
    "TLS_RSA_WITH_RC4_128_MD5",
    "TLS_RSA_WITH_DES_CBC_SHA",
]

ALL_STRONG_CIPHERS = TLS_13_CIPHERS + TLS_12_STRONG_CIPHERS


# ============================================================================
# TLS Profiles
# ============================================================================

TLS_PROFILES: dict[TLSProfileName, TLSProfile] = {
    TLSProfileName.MODERN: TLSProfile(
        name=TLSProfileName.MODERN,
        description="TLS 1.3 only. Maximum security for modern clients.",
        minimum_version=TLSVersion.TLS_1_3,
        preferred_version=TLSVersion.TLS_1_3,
        cipher_suites=TLS_13_CIPHERS,
        recommended_for="Modern browsers and API clients (2020+)",
        security_level="high",
    ),
    TLSProfileName.INTERMEDIATE: TLSProfile(
        name=TLSProfileName.INTERMEDIATE,
        description="TLS 1.2+ with strong AEAD ciphers. Broad compatibility.",
        minimum_version=TLSVersion.TLS_1_2,
        preferred_version=TLSVersion.TLS_1_3,
        cipher_suites=TLS_13_CIPHERS + TLS_12_STRONG_CIPHERS,
        recommended_for="General-purpose servers needing broad compatibility",
        security_level="medium",
    ),
    TLSProfileName.OLD: TLSProfile(
        name=TLSProfileName.OLD,
        description=(
            "TLS 1.2+ with CBC fallback. NOT recommended for new deployments."
        ),
        minimum_version=TLSVersion.TLS_1_2,
        preferred_version=TLSVersion.TLS_1_3,
        cipher_suites=TLS_13_CIPHERS + TLS_12_STRONG_CIPHERS + TLS_12_ACCEPTABLE_CIPHERS,
        recommended_for="Legacy compatibility only -- migrate to INTERMEDIATE",
        security_level="low",
    ),
}


# ============================================================================
# CORS Profiles
# ============================================================================

CORS_PROFILES: dict[CORSProfileName, CORSProfile] = {
    CORSProfileName.STRICT: CORSProfile(
        name=CORSProfileName.STRICT,
        description="Specific origins only. For production deployments.",
        allowed_origins=[],  # Must be configured per deployment
        allowed_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_credentials=True,
        recommended_for="Production environments",
    ),
    CORSProfileName.DEVELOPMENT: CORSProfile(
        name=CORSProfileName.DEVELOPMENT,
        description="Localhost origins for development.",
        allowed_origins=[
            "http://localhost:3000",
            "http://localhost:3001",
            "http://localhost:3002",
            "http://localhost:8080",
        ],
        allowed_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_credentials=True,
        recommended_for="Local development environments",
    ),
    CORSProfileName.API_ONLY: CORSProfile(
        name=CORSProfileName.API_ONLY,
        description="No credentials, specific methods. For public API access.",
        allowed_origins=["*"],
        allowed_methods=["GET", "POST", "OPTIONS"],
        allow_credentials=False,
        recommended_for="Public read-only APIs",
    ),
}


# ============================================================================
# SecurityHardeningService
# ============================================================================


class SecurityHardeningService:
    """Audits and enforces TLS, auth, and CORS security configurations.

    Thread-safe singleton. Instantiate via get_security_hardening_service().
    """

    def __init__(
        self,
        *,
        environment: Optional[str] = None,
        tls_config: Optional[TLSConfig] = None,
        auth_config: Optional[AuthConfig] = None,
        cors_config: Optional[CORSConfig] = None,
    ) -> None:
        self._environment = environment or getattr(settings, "environment", "development")
        self._tls_config = tls_config or self._default_tls_config()
        self._auth_config = auth_config or AuthConfig()
        self._cors_config = cors_config or self._default_cors_config()

    # ------------------------------------------------------------------
    # Default configuration builders
    # ------------------------------------------------------------------

    def _default_tls_config(self) -> TLSConfig:
        """Build default TLS config based on environment."""
        profile = TLSProfileName.MODERN if self._is_production else TLSProfileName.INTERMEDIATE
        tls_profile = TLS_PROFILES[profile]
        return TLSConfig(
            minimum_version=tls_profile.minimum_version,
            preferred_version=tls_profile.preferred_version,
            allowed_cipher_suites=list(tls_profile.cipher_suites),
            hsts=HSTSConfig(
                enabled=True,
                max_age=31536000,
                include_subdomains=True,
                preload=self._is_production,
            ),
            profile=profile,
        )

    def _default_cors_config(self) -> CORSConfig:
        """Build default CORS config from application settings."""
        origins = getattr(settings, "cors_origins_list", [])
        if not origins:
            origins = ["http://localhost:3000"]
        profile = CORSProfileName.STRICT if self._is_production else CORSProfileName.DEVELOPMENT
        return CORSConfig(
            allowed_origins=origins,
            allow_credentials=getattr(settings, "cors_allow_credentials", True),
            profile=profile,
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def _is_production(self) -> bool:
        return self._environment.lower() == "production"

    @property
    def tls_config(self) -> TLSConfig:
        return self._tls_config

    @property
    def auth_config(self) -> AuthConfig:
        return self._auth_config

    @property
    def cors_config(self) -> CORSConfig:
        return self._cors_config

    # ------------------------------------------------------------------
    # TLS validation (CISO-2)
    # ------------------------------------------------------------------

    def validate_tls_version(self, version: TLSVersion) -> bool:
        """Check if a TLS version meets the minimum requirement."""
        version_order = {
            TLSVersion.TLS_1_0: 0,
            TLSVersion.TLS_1_1: 1,
            TLSVersion.TLS_1_2: 2,
            TLSVersion.TLS_1_3: 3,
        }
        return version_order.get(version, -1) >= version_order.get(
            self._tls_config.minimum_version, 2
        )

    def validate_cipher_suite(self, cipher: str) -> CipherSuite:
        """Classify a cipher suite by strength."""
        if cipher in TLS_13_CIPHERS:
            strength = "strong"
        elif cipher in TLS_12_STRONG_CIPHERS:
            strength = "strong"
        elif cipher in TLS_12_ACCEPTABLE_CIPHERS:
            strength = "acceptable"
        elif cipher in WEAK_CIPHERS:
            strength = "weak"
        else:
            strength = "unknown"

        # Parse key exchange / auth from name
        key_exchange = ""
        authentication = ""
        encryption = ""
        mac = ""

        if "ECDHE" in cipher:
            key_exchange = "ECDHE"
        elif "DHE" in cipher:
            key_exchange = "DHE"
        elif cipher.startswith("TLS_") and "WITH" not in cipher:
            # TLS 1.3 cipher suite
            key_exchange = "ECDHE (TLS 1.3)"

        if "ECDSA" in cipher:
            authentication = "ECDSA"
        elif "RSA" in cipher:
            authentication = "RSA"

        if "AES_256_GCM" in cipher:
            encryption = "AES-256-GCM"
        elif "AES_128_GCM" in cipher:
            encryption = "AES-128-GCM"
        elif "CHACHA20" in cipher:
            encryption = "ChaCha20-Poly1305"
        elif "AES_256_CBC" in cipher:
            encryption = "AES-256-CBC"
        elif "AES_128_CBC" in cipher:
            encryption = "AES-128-CBC"
        elif "3DES" in cipher:
            encryption = "3DES"
        elif "RC4" in cipher:
            encryption = "RC4"
        elif "DES_CBC" in cipher:
            encryption = "DES"

        if "SHA384" in cipher:
            mac = "SHA384"
        elif "SHA256" in cipher:
            mac = "SHA256"
        elif "SHA" in cipher:
            mac = "SHA1"
        elif "MD5" in cipher:
            mac = "MD5"

        return CipherSuite(
            name=cipher,
            strength=strength,
            key_exchange=key_exchange,
            authentication=authentication,
            encryption=encryption,
            mac=mac,
        )

    def is_cipher_allowed(self, cipher: str) -> bool:
        """Check if a cipher is in the allowed list."""
        return cipher in self._tls_config.allowed_cipher_suites

    def validate_certificate(self, cert: CertificateInfo) -> list[SecurityCheck]:
        """Validate certificate properties."""
        checks: list[SecurityCheck] = []

        # Expiry check
        if cert.is_expired:
            checks.append(SecurityCheck(
                id="tls-cert-expired",
                domain=SecurityDomain.TLS,
                name="Certificate expiry",
                description="Certificate must not be expired",
                status=CheckStatus.FAIL,
                details="Certificate is expired",
                remediation="Renew the TLS certificate immediately",
                severity="critical",
            ))
        elif cert.days_until_expiry is not None and cert.days_until_expiry < 30:
            checks.append(SecurityCheck(
                id="tls-cert-expiring-soon",
                domain=SecurityDomain.TLS,
                name="Certificate expiry",
                description="Certificate must not expire within 30 days",
                status=CheckStatus.WARN,
                details=f"Certificate expires in {cert.days_until_expiry} days",
                remediation="Renew the TLS certificate before expiry",
                severity="high",
            ))
        else:
            checks.append(SecurityCheck(
                id="tls-cert-valid",
                domain=SecurityDomain.TLS,
                name="Certificate expiry",
                description="Certificate validity period",
                status=CheckStatus.PASS,
                details=(
                    f"Certificate valid for {cert.days_until_expiry} days"
                    if cert.days_until_expiry
                    else "Certificate validity OK"
                ),
            ))

        # Self-signed check
        if cert.is_self_signed and self._is_production:
            checks.append(SecurityCheck(
                id="tls-cert-self-signed",
                domain=SecurityDomain.TLS,
                name="Certificate authority",
                description="Production must use CA-signed certificate",
                status=CheckStatus.FAIL,
                details="Self-signed certificate detected in production",
                remediation="Obtain a certificate from a trusted Certificate Authority",
                severity="critical",
            ))
        elif cert.is_self_signed:
            checks.append(SecurityCheck(
                id="tls-cert-self-signed",
                domain=SecurityDomain.TLS,
                name="Certificate authority",
                description="Certificate should be CA-signed",
                status=CheckStatus.WARN,
                details="Self-signed certificate (acceptable in development)",
                remediation="Use a CA-signed certificate for non-development environments",
                severity="low",
            ))
        else:
            checks.append(SecurityCheck(
                id="tls-cert-ca-signed",
                domain=SecurityDomain.TLS,
                name="Certificate authority",
                description="Certificate is CA-signed",
                status=CheckStatus.PASS,
                details="Certificate is signed by a trusted CA",
            ))

        # Chain check
        if not cert.chain_valid:
            checks.append(SecurityCheck(
                id="tls-cert-chain",
                domain=SecurityDomain.TLS,
                name="Certificate chain",
                description="Certificate chain must be valid",
                status=CheckStatus.FAIL,
                details="Certificate chain is invalid or incomplete",
                remediation="Ensure full certificate chain is configured correctly",
                severity="critical",
            ))
        else:
            checks.append(SecurityCheck(
                id="tls-cert-chain",
                domain=SecurityDomain.TLS,
                name="Certificate chain",
                description="Certificate chain validation",
                status=CheckStatus.PASS,
                details="Certificate chain is valid",
            ))

        return checks

    # ------------------------------------------------------------------
    # Auth validation (CISO-3)
    # ------------------------------------------------------------------

    def validate_password(self, password: str) -> tuple[bool, list[str]]:
        """Validate a password against the configured policy.

        Returns (is_valid, list_of_violations).
        """
        policy = self._auth_config.password_policy
        violations: list[str] = []

        if len(password) < policy.min_length:
            violations.append(
                f"Password must be at least {policy.min_length} characters "
                f"(got {len(password)})"
            )
        if len(password) > policy.max_length:
            violations.append(
                f"Password must be at most {policy.max_length} characters"
            )
        if policy.require_uppercase and not re.search(r"[A-Z]", password):
            violations.append("Password must contain at least one uppercase letter")
        if policy.require_lowercase and not re.search(r"[a-z]", password):
            violations.append("Password must contain at least one lowercase letter")
        if policy.require_digit and not re.search(r"\d", password):
            violations.append("Password must contain at least one digit")
        if policy.require_special:
            # Escape special regex characters for the character class
            escaped = re.escape(policy.special_characters)
            if not re.search(f"[{escaped}]", password):
                violations.append("Password must contain at least one special character")

        return (len(violations) == 0, violations)

    def calculate_lockout_duration(self, consecutive_failures: int) -> int:
        """Calculate lockout duration in minutes given consecutive failures.

        Returns 0 if under the threshold.
        """
        lockout = self._auth_config.lockout
        if consecutive_failures < lockout.max_failed_attempts:
            return 0

        if not lockout.progressive_backoff:
            return lockout.lockout_duration_minutes

        # How many lockouts beyond the first
        lockout_count = (
            consecutive_failures - lockout.max_failed_attempts
        ) // lockout.max_failed_attempts
        duration = lockout.lockout_duration_minutes * (
            lockout.backoff_multiplier ** lockout_count
        )
        return min(int(duration), lockout.max_lockout_minutes)

    def validate_jwt_config(self) -> list[SecurityCheck]:
        """Validate JWT configuration."""
        checks: list[SecurityCheck] = []
        jwt = self._auth_config.jwt

        # Algorithm check
        symmetric_algos = {JWTAlgorithm.HS256, JWTAlgorithm.HS384, JWTAlgorithm.HS512}
        if jwt.algorithm in symmetric_algos and self._is_production:
            checks.append(SecurityCheck(
                id="auth-jwt-algo",
                domain=SecurityDomain.AUTH,
                name="JWT signing algorithm",
                description="Production should use asymmetric signing (RS256/ES256)",
                status=CheckStatus.WARN,
                details=f"Using symmetric algorithm {jwt.algorithm.value}",
                remediation="Switch to RS256 or ES256 for production",
                severity="high",
            ))
        else:
            checks.append(SecurityCheck(
                id="auth-jwt-algo",
                domain=SecurityDomain.AUTH,
                name="JWT signing algorithm",
                description="JWT algorithm configuration",
                status=CheckStatus.PASS,
                details=f"Using {jwt.algorithm.value}",
            ))

        # Token lifetime check
        if jwt.access_token_expire_minutes > 60:
            checks.append(SecurityCheck(
                id="auth-jwt-access-ttl",
                domain=SecurityDomain.AUTH,
                name="Access token lifetime",
                description="Access tokens should be short-lived (<=60 min)",
                status=CheckStatus.WARN,
                details=f"Access token lifetime is {jwt.access_token_expire_minutes} minutes",
                remediation="Reduce access token lifetime to 15-30 minutes",
                severity="medium",
            ))
        elif jwt.access_token_expire_minutes > 30:
            checks.append(SecurityCheck(
                id="auth-jwt-access-ttl",
                domain=SecurityDomain.AUTH,
                name="Access token lifetime",
                description="Access tokens should be short-lived",
                status=CheckStatus.PASS,
                details=f"Access token lifetime is {jwt.access_token_expire_minutes} minutes",
            ))
        else:
            checks.append(SecurityCheck(
                id="auth-jwt-access-ttl",
                domain=SecurityDomain.AUTH,
                name="Access token lifetime",
                description="Access tokens are short-lived",
                status=CheckStatus.PASS,
                details=f"Access token lifetime is {jwt.access_token_expire_minutes} minutes",
            ))

        # Refresh token check
        if jwt.refresh_token_expire_days > 30:
            checks.append(SecurityCheck(
                id="auth-jwt-refresh-ttl",
                domain=SecurityDomain.AUTH,
                name="Refresh token lifetime",
                description="Refresh tokens should expire within 30 days",
                status=CheckStatus.WARN,
                details=f"Refresh token lifetime is {jwt.refresh_token_expire_days} days",
                remediation="Reduce refresh token lifetime to 7-14 days",
                severity="medium",
            ))
        else:
            checks.append(SecurityCheck(
                id="auth-jwt-refresh-ttl",
                domain=SecurityDomain.AUTH,
                name="Refresh token lifetime",
                description="Refresh token lifetime check",
                status=CheckStatus.PASS,
                details=f"Refresh token lifetime is {jwt.refresh_token_expire_days} days",
            ))

        return checks

    def validate_session_config(self) -> list[SecurityCheck]:
        """Validate session configuration."""
        checks: list[SecurityCheck] = []
        session = self._auth_config.session

        # Idle timeout
        if session.max_idle_minutes > 60:
            checks.append(SecurityCheck(
                id="auth-session-idle",
                domain=SecurityDomain.AUTH,
                name="Session idle timeout",
                description="Session idle timeout should be <= 60 minutes",
                status=CheckStatus.WARN,
                details=f"Session idle timeout is {session.max_idle_minutes} minutes",
                remediation="Reduce idle timeout to 30 minutes",
                severity="medium",
            ))
        else:
            checks.append(SecurityCheck(
                id="auth-session-idle",
                domain=SecurityDomain.AUTH,
                name="Session idle timeout",
                description="Session idle timeout",
                status=CheckStatus.PASS,
                details=f"Session idle timeout is {session.max_idle_minutes} minutes",
            ))

        # Secure cookie
        if not session.secure_cookie and self._is_production:
            checks.append(SecurityCheck(
                id="auth-session-secure",
                domain=SecurityDomain.AUTH,
                name="Secure cookie flag",
                description="Session cookies must have Secure flag in production",
                status=CheckStatus.FAIL,
                details="Secure cookie flag is disabled",
                remediation="Enable Secure flag on session cookies",
                severity="high",
            ))
        else:
            checks.append(SecurityCheck(
                id="auth-session-secure",
                domain=SecurityDomain.AUTH,
                name="Secure cookie flag",
                description="Session cookie security flags",
                status=CheckStatus.PASS,
                details=f"Secure={session.secure_cookie}, HttpOnly={session.http_only}",
            ))

        # HttpOnly cookie
        if not session.http_only:
            checks.append(SecurityCheck(
                id="auth-session-httponly",
                domain=SecurityDomain.AUTH,
                name="HttpOnly cookie flag",
                description="Session cookies should have HttpOnly flag",
                status=CheckStatus.WARN,
                details="HttpOnly cookie flag is disabled",
                remediation="Enable HttpOnly flag on session cookies",
                severity="medium",
            ))
        else:
            checks.append(SecurityCheck(
                id="auth-session-httponly",
                domain=SecurityDomain.AUTH,
                name="HttpOnly cookie flag",
                description="HttpOnly flag is set",
                status=CheckStatus.PASS,
                details="HttpOnly flag enabled",
            ))

        # SameSite attribute
        if session.same_site.lower() == "none" and self._is_production:
            checks.append(SecurityCheck(
                id="auth-session-samesite",
                domain=SecurityDomain.AUTH,
                name="SameSite cookie attribute",
                description="SameSite should be Lax or Strict in production",
                status=CheckStatus.WARN,
                details=f"SameSite is set to {session.same_site}",
                remediation="Set SameSite to Lax or Strict",
                severity="medium",
            ))
        else:
            checks.append(SecurityCheck(
                id="auth-session-samesite",
                domain=SecurityDomain.AUTH,
                name="SameSite cookie attribute",
                description="SameSite cookie policy",
                status=CheckStatus.PASS,
                details=f"SameSite={session.same_site}",
            ))

        return checks

    def validate_password_policy(self) -> list[SecurityCheck]:
        """Validate password policy configuration."""
        checks: list[SecurityCheck] = []
        policy = self._auth_config.password_policy

        if policy.min_length < 8:
            checks.append(SecurityCheck(
                id="auth-pw-length",
                domain=SecurityDomain.AUTH,
                name="Password minimum length",
                description="Password min length must be at least 8",
                status=CheckStatus.FAIL,
                details=f"Minimum length is {policy.min_length}",
                remediation="Set minimum password length to 12+",
                severity="critical",
            ))
        elif policy.min_length < 12:
            checks.append(SecurityCheck(
                id="auth-pw-length",
                domain=SecurityDomain.AUTH,
                name="Password minimum length",
                description="Password min length should be 12+",
                status=CheckStatus.WARN,
                details=f"Minimum length is {policy.min_length}",
                remediation="Increase minimum password length to 12",
                severity="medium",
            ))
        else:
            checks.append(SecurityCheck(
                id="auth-pw-length",
                domain=SecurityDomain.AUTH,
                name="Password minimum length",
                description="Password length policy",
                status=CheckStatus.PASS,
                details=f"Minimum length is {policy.min_length}",
            ))

        # Complexity check
        complexity_count = sum([
            policy.require_uppercase,
            policy.require_lowercase,
            policy.require_digit,
            policy.require_special,
        ])
        if complexity_count < 3:
            checks.append(SecurityCheck(
                id="auth-pw-complexity",
                domain=SecurityDomain.AUTH,
                name="Password complexity",
                description="Password should require at least 3 character classes",
                status=CheckStatus.WARN,
                details=f"Only {complexity_count} character classes required",
                remediation="Enable uppercase, lowercase, digit, and special requirements",
                severity="medium",
            ))
        else:
            checks.append(SecurityCheck(
                id="auth-pw-complexity",
                domain=SecurityDomain.AUTH,
                name="Password complexity",
                description="Password complexity requirements",
                status=CheckStatus.PASS,
                details=f"Requires {complexity_count} character classes",
            ))

        return checks

    def validate_lockout_config(self) -> list[SecurityCheck]:
        """Validate account lockout configuration."""
        checks: list[SecurityCheck] = []
        lockout = self._auth_config.lockout

        if lockout.max_failed_attempts > 10:
            checks.append(SecurityCheck(
                id="auth-lockout-threshold",
                domain=SecurityDomain.AUTH,
                name="Lockout threshold",
                description="Account lockout threshold should be <= 10 attempts",
                status=CheckStatus.WARN,
                details=f"Lockout after {lockout.max_failed_attempts} attempts",
                remediation="Reduce lockout threshold to 5 attempts",
                severity="medium",
            ))
        elif lockout.max_failed_attempts <= 0:
            checks.append(SecurityCheck(
                id="auth-lockout-threshold",
                domain=SecurityDomain.AUTH,
                name="Lockout threshold",
                description="Account lockout must be enabled",
                status=CheckStatus.FAIL,
                details="Account lockout is disabled (threshold <= 0)",
                remediation="Enable account lockout with threshold of 5",
                severity="high",
            ))
        else:
            checks.append(SecurityCheck(
                id="auth-lockout-threshold",
                domain=SecurityDomain.AUTH,
                name="Lockout threshold",
                description="Account lockout configuration",
                status=CheckStatus.PASS,
                details=f"Lockout after {lockout.max_failed_attempts} attempts",
            ))

        return checks

    def validate_mfa_config(self) -> list[SecurityCheck]:
        """Validate MFA configuration."""
        checks: list[SecurityCheck] = []
        mfa = self._auth_config.mfa

        if mfa.requirement == MFARequirement.DISABLED:
            if self._is_production:
                checks.append(SecurityCheck(
                    id="auth-mfa",
                    domain=SecurityDomain.AUTH,
                    name="MFA requirement",
                    description="MFA should be enabled in production",
                    status=CheckStatus.FAIL,
                    details="MFA is disabled",
                    remediation="Enable MFA for at least admin roles",
                    severity="critical",
                ))
            else:
                checks.append(SecurityCheck(
                    id="auth-mfa",
                    domain=SecurityDomain.AUTH,
                    name="MFA requirement",
                    description="MFA configuration",
                    status=CheckStatus.WARN,
                    details="MFA is disabled",
                    remediation="Consider enabling MFA for admin roles",
                    severity="low",
                ))
        elif mfa.requirement == MFARequirement.RECOMMENDED:
            checks.append(SecurityCheck(
                id="auth-mfa",
                domain=SecurityDomain.AUTH,
                name="MFA requirement",
                description="MFA configuration",
                status=CheckStatus.WARN,
                details="MFA is recommended but not required",
                remediation="Require MFA for admin roles at minimum",
                severity="medium",
            ))
        else:
            checks.append(SecurityCheck(
                id="auth-mfa",
                domain=SecurityDomain.AUTH,
                name="MFA requirement",
                description="MFA is required",
                status=CheckStatus.PASS,
                details=f"MFA requirement: {mfa.requirement.value}",
            ))

        return checks

    # ------------------------------------------------------------------
    # CORS validation (CISO-4)
    # ------------------------------------------------------------------

    def validate_origin(self, origin: str) -> OriginValidationResponse:
        """Check if an origin is allowed by the current CORS config."""
        cors = self._cors_config

        # Check wildcard
        if "*" in cors.allowed_origins:
            if cors.allow_credentials:
                return OriginValidationResponse(
                    origin=origin,
                    allowed=False,
                    reason="Wildcard origins with credentials is not allowed",
                )
            return OriginValidationResponse(
                origin=origin,
                allowed=True,
                matched_rule="wildcard (*)",
            )

        # Normalize origin
        normalized = origin.rstrip("/")
        for allowed in cors.allowed_origins:
            if allowed.rstrip("/") == normalized:
                return OriginValidationResponse(
                    origin=origin,
                    allowed=True,
                    matched_rule=allowed,
                )

        return OriginValidationResponse(
            origin=origin,
            allowed=False,
            reason=f"Origin not in allowed list ({len(cors.allowed_origins)} origins configured)",
        )

    def validate_cors_config(self) -> list[SecurityCheck]:
        """Validate CORS configuration."""
        checks: list[SecurityCheck] = []
        cors = self._cors_config

        # Wildcard check
        if "*" in cors.allowed_origins:
            if self._is_production:
                checks.append(SecurityCheck(
                    id="cors-wildcard",
                    domain=SecurityDomain.CORS,
                    name="CORS wildcard origins",
                    description="Wildcard origins must not be used in production",
                    status=CheckStatus.FAIL,
                    details="Wildcard (*) origin found in production",
                    remediation="Replace wildcard with explicit origin list",
                    severity="critical",
                ))
            else:
                checks.append(SecurityCheck(
                    id="cors-wildcard",
                    domain=SecurityDomain.CORS,
                    name="CORS wildcard origins",
                    description="Wildcard origins should be avoided",
                    status=CheckStatus.WARN,
                    details="Wildcard (*) origin found",
                    remediation="Use explicit origin list instead of wildcard",
                    severity="medium",
                ))
        else:
            checks.append(SecurityCheck(
                id="cors-wildcard",
                domain=SecurityDomain.CORS,
                name="CORS wildcard origins",
                description="No wildcard origins",
                status=CheckStatus.PASS,
                details=f"{len(cors.allowed_origins)} explicit origins configured",
            ))

        # Empty origins check
        if not cors.allowed_origins:
            checks.append(SecurityCheck(
                id="cors-origins-empty",
                domain=SecurityDomain.CORS,
                name="CORS origins configured",
                description="At least one CORS origin must be configured",
                status=CheckStatus.FAIL,
                details="No CORS origins configured",
                remediation="Add allowed origins to CORS configuration",
                severity="high",
            ))
        else:
            checks.append(SecurityCheck(
                id="cors-origins-configured",
                domain=SecurityDomain.CORS,
                name="CORS origins configured",
                description="CORS origins are configured",
                status=CheckStatus.PASS,
                details=f"{len(cors.allowed_origins)} origins configured",
            ))

        # Credentials + wildcard check
        if cors.allow_credentials and "*" in cors.allowed_origins:
            checks.append(SecurityCheck(
                id="cors-creds-wildcard",
                domain=SecurityDomain.CORS,
                name="CORS credentials with wildcard",
                description="Credentials must not be used with wildcard origins",
                status=CheckStatus.FAIL,
                details="allow_credentials=True with wildcard origin",
                remediation="Either disable credentials or use explicit origins",
                severity="critical",
            ))
        else:
            checks.append(SecurityCheck(
                id="cors-creds-wildcard",
                domain=SecurityDomain.CORS,
                name="CORS credentials configuration",
                description="Credentials and origins configuration is valid",
                status=CheckStatus.PASS,
                details=f"Credentials={'enabled' if cors.allow_credentials else 'disabled'}",
            ))

        # Max age check
        if cors.max_age > 86400:
            checks.append(SecurityCheck(
                id="cors-max-age",
                domain=SecurityDomain.CORS,
                name="CORS preflight max age",
                description="Preflight max age should be <= 24 hours",
                status=CheckStatus.WARN,
                details=f"Max age is {cors.max_age} seconds",
                remediation="Reduce preflight cache max age to 600-3600 seconds",
                severity="low",
            ))
        else:
            checks.append(SecurityCheck(
                id="cors-max-age",
                domain=SecurityDomain.CORS,
                name="CORS preflight max age",
                description="Preflight cache max age",
                status=CheckStatus.PASS,
                details=f"Max age is {cors.max_age} seconds",
            ))

        # Origin format validation
        invalid_origins = []
        for origin in cors.allowed_origins:
            if origin == "*":
                continue
            if not origin.startswith(("http://", "https://")):
                invalid_origins.append(origin)

        if invalid_origins:
            checks.append(SecurityCheck(
                id="cors-origin-format",
                domain=SecurityDomain.CORS,
                name="CORS origin format",
                description="All origins must be valid absolute URLs",
                status=CheckStatus.FAIL,
                details=f"Invalid origins: {', '.join(invalid_origins)}",
                remediation="Origins must start with http:// or https://",
                severity="high",
            ))
        else:
            checks.append(SecurityCheck(
                id="cors-origin-format",
                domain=SecurityDomain.CORS,
                name="CORS origin format",
                description="All origins have valid format",
                status=CheckStatus.PASS,
                details="All origins are valid absolute URLs",
            ))

        return checks

    # ------------------------------------------------------------------
    # TLS security checks
    # ------------------------------------------------------------------

    def run_tls_checks(self) -> list[SecurityCheck]:
        """Run all TLS security checks."""
        checks: list[SecurityCheck] = []
        tls = self._tls_config

        # Minimum version check
        if tls.minimum_version in (TLSVersion.TLS_1_0, TLSVersion.TLS_1_1):
            checks.append(SecurityCheck(
                id="tls-min-version",
                domain=SecurityDomain.TLS,
                name="TLS minimum version",
                description="Minimum TLS version must be 1.2 or higher",
                status=CheckStatus.FAIL,
                details=f"Minimum version is {tls.minimum_version.value}",
                remediation="Set minimum TLS version to 1.2",
                severity="critical",
            ))
        elif tls.minimum_version == TLSVersion.TLS_1_2:
            checks.append(SecurityCheck(
                id="tls-min-version",
                domain=SecurityDomain.TLS,
                name="TLS minimum version",
                description="TLS minimum version check",
                status=CheckStatus.PASS,
                details=f"Minimum version is {tls.minimum_version.value}",
            ))
        else:
            checks.append(SecurityCheck(
                id="tls-min-version",
                domain=SecurityDomain.TLS,
                name="TLS minimum version",
                description="TLS minimum version check",
                status=CheckStatus.PASS,
                details=f"Minimum version is {tls.minimum_version.value} (modern)",
            ))

        # Preferred version check
        if tls.preferred_version != TLSVersion.TLS_1_3:
            checks.append(SecurityCheck(
                id="tls-preferred-version",
                domain=SecurityDomain.TLS,
                name="TLS preferred version",
                description="Preferred TLS version should be 1.3",
                status=CheckStatus.WARN,
                details=f"Preferred version is {tls.preferred_version.value}",
                remediation="Set preferred TLS version to 1.3",
                severity="medium",
            ))
        else:
            checks.append(SecurityCheck(
                id="tls-preferred-version",
                domain=SecurityDomain.TLS,
                name="TLS preferred version",
                description="Preferred TLS version check",
                status=CheckStatus.PASS,
                details="Preferred version is TLSv1.3",
            ))

        # HSTS check
        hsts = tls.hsts
        if not hsts.enabled:
            checks.append(SecurityCheck(
                id="tls-hsts",
                domain=SecurityDomain.TLS,
                name="HSTS enabled",
                description="HSTS must be enabled",
                status=CheckStatus.FAIL,
                details="HSTS is disabled",
                remediation="Enable HSTS with max-age of at least 1 year",
                severity="high",
            ))
        elif hsts.max_age < 31536000:
            checks.append(SecurityCheck(
                id="tls-hsts",
                domain=SecurityDomain.TLS,
                name="HSTS max-age",
                description="HSTS max-age should be at least 1 year (31536000)",
                status=CheckStatus.WARN,
                details=f"HSTS max-age is {hsts.max_age}",
                remediation="Set HSTS max-age to 31536000 (1 year)",
                severity="medium",
            ))
        else:
            checks.append(SecurityCheck(
                id="tls-hsts",
                domain=SecurityDomain.TLS,
                name="HSTS configuration",
                description="HSTS is properly configured",
                status=CheckStatus.PASS,
                details=hsts.header_value,
            ))

        # HSTS includeSubDomains
        if hsts.enabled and not hsts.include_subdomains and self._is_production:
            checks.append(SecurityCheck(
                id="tls-hsts-subdomains",
                domain=SecurityDomain.TLS,
                name="HSTS includeSubDomains",
                description="HSTS should include subdomains in production",
                status=CheckStatus.WARN,
                details="includeSubDomains is not set",
                remediation="Enable includeSubDomains in HSTS",
                severity="medium",
            ))
        elif hsts.enabled:
            checks.append(SecurityCheck(
                id="tls-hsts-subdomains",
                domain=SecurityDomain.TLS,
                name="HSTS includeSubDomains",
                description="HSTS subdomain configuration",
                status=CheckStatus.PASS,
                details=f"includeSubDomains={'enabled' if hsts.include_subdomains else 'disabled'}",
            ))

        # Cipher suite check
        weak_ciphers_found = []
        for cipher in tls.allowed_cipher_suites:
            suite = self.validate_cipher_suite(cipher)
            if suite.strength in ("weak", "unknown"):
                weak_ciphers_found.append(cipher)

        if weak_ciphers_found:
            checks.append(SecurityCheck(
                id="tls-weak-ciphers",
                domain=SecurityDomain.TLS,
                name="Weak cipher suites",
                description="No weak cipher suites should be allowed",
                status=CheckStatus.FAIL,
                details=f"Weak ciphers found: {', '.join(weak_ciphers_found)}",
                remediation="Remove weak cipher suites from configuration",
                severity="high",
            ))
        else:
            checks.append(SecurityCheck(
                id="tls-ciphers",
                domain=SecurityDomain.TLS,
                name="Cipher suite strength",
                description="All cipher suites are strong",
                status=CheckStatus.PASS,
                details=f"{len(tls.allowed_cipher_suites)} strong cipher suites configured",
            ))

        # Certificate checks (if available)
        if tls.certificate:
            checks.extend(self.validate_certificate(tls.certificate))

        return checks

    # ------------------------------------------------------------------
    # Full security audit
    # ------------------------------------------------------------------

    def run_audit(self) -> SecurityAuditReport:
        """Run complete security audit across TLS, Auth, and CORS."""
        all_checks: list[SecurityCheck] = []

        # TLS checks
        tls_checks = self.run_tls_checks()
        all_checks.extend(tls_checks)

        # Auth checks
        auth_checks: list[SecurityCheck] = []
        auth_checks.extend(self.validate_password_policy())
        auth_checks.extend(self.validate_session_config())
        auth_checks.extend(self.validate_jwt_config())
        auth_checks.extend(self.validate_lockout_config())
        auth_checks.extend(self.validate_mfa_config())
        all_checks.extend(auth_checks)

        # CORS checks
        cors_checks = self.validate_cors_config()
        all_checks.extend(cors_checks)

        # Calculate scores
        pass_count = sum(1 for c in all_checks if c.status == CheckStatus.PASS)
        warn_count = sum(1 for c in all_checks if c.status == CheckStatus.WARN)
        fail_count = sum(1 for c in all_checks if c.status == CheckStatus.FAIL)

        tls_score = self._calculate_domain_score(tls_checks)
        auth_score = self._calculate_domain_score(auth_checks)
        cors_score = self._calculate_domain_score(cors_checks)

        overall_score = self._calculate_domain_score(all_checks)

        # Generate recommendations
        recommendations = self._generate_recommendations(all_checks)

        return SecurityAuditReport(
            timestamp=datetime.now(timezone.utc),
            environment=self._environment,
            overall_score=overall_score,
            tls_score=tls_score,
            auth_score=auth_score,
            cors_score=cors_score,
            checks=all_checks,
            pass_count=pass_count,
            warn_count=warn_count,
            fail_count=fail_count,
            recommendations=recommendations,
            tls_config=self._tls_config,
            auth_config=self._auth_config,
            cors_config=self._cors_config,
        )

    def get_recommendations(self) -> SecurityRecommendationsResponse:
        """Get security improvement recommendations."""
        report = self.run_audit()
        return SecurityRecommendationsResponse(
            environment=self._environment,
            total_recommendations=len(report.recommendations),
            critical_count=sum(
                1 for r in report.recommendations if r.priority == "critical"
            ),
            high_count=sum(
                1 for r in report.recommendations if r.priority == "high"
            ),
            recommendations=report.recommendations,
        )

    # ------------------------------------------------------------------
    # Scoring helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _calculate_domain_score(checks: list[SecurityCheck]) -> int:
        """Calculate a 0-100 score for a set of checks.

        PASS = full weight, WARN = half weight, FAIL = 0.
        """
        if not checks:
            return 100
        total = len(checks)
        score = sum(
            1.0 if c.status == CheckStatus.PASS
            else 0.5 if c.status == CheckStatus.WARN
            else 0.0
            for c in checks
        )
        return int(round(score / total * 100))

    @staticmethod
    def _generate_recommendations(checks: list[SecurityCheck]) -> list[SecurityRecommendation]:
        """Generate actionable recommendations from failed/warned checks."""
        recommendations: list[SecurityRecommendation] = []
        for check in checks:
            if check.status in (CheckStatus.WARN, CheckStatus.FAIL) and check.remediation:
                priority = check.severity if check.status == CheckStatus.FAIL else "medium"
                effort = "low" if check.severity in ("low", "medium") else "medium"
                recommendations.append(SecurityRecommendation(
                    id=f"rec-{check.id}",
                    domain=check.domain,
                    title=check.name,
                    description=check.remediation,
                    priority=priority,
                    effort=effort,
                    current_state=check.details,
                    recommended_state=check.remediation,
                ))

        # Sort by priority: critical > high > medium > low
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        recommendations.sort(key=lambda r: priority_order.get(r.priority, 4))
        return recommendations

    # ------------------------------------------------------------------
    # Profile accessors
    # ------------------------------------------------------------------

    @staticmethod
    def get_tls_profiles() -> list[TLSProfile]:
        """Return all available TLS profiles."""
        return list(TLS_PROFILES.values())

    @staticmethod
    def get_cors_profiles() -> list[CORSProfile]:
        """Return all available CORS profiles."""
        return list(CORS_PROFILES.values())

    def get_stats(self) -> dict:
        """Return service stats for health check."""
        report = self.run_audit()
        return {
            "environment": self._environment,
            "overall_score": report.overall_score,
            "tls_score": report.tls_score,
            "auth_score": report.auth_score,
            "cors_score": report.cors_score,
            "checks_total": len(report.checks),
            "checks_pass": report.pass_count,
            "checks_warn": report.warn_count,
            "checks_fail": report.fail_count,
        }


# ============================================================================
# Singleton accessor
# ============================================================================

_service: Optional[SecurityHardeningService] = None


def get_security_hardening_service() -> SecurityHardeningService:
    """Get or create the SecurityHardeningService singleton."""
    global _service
    if _service is None:
        _service = SecurityHardeningService()
    return _service
