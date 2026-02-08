"""Tests for Security Hardening (CISO-2/3/4).

Tests cover:
- TLS: cipher validation, TLS version checks, HSTS headers, cert expiry
- Auth: password policy (valid/invalid), session timeouts, lockout logic, JWT config
- CORS: origin validation (allowed/blocked), wildcard rejection, credentials mode
- Security audit: scoring, pass/warn/fail classification
- Profile selection per environment
- Remediation recommendations
- API endpoint responses
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.schemas.security_hardening import (
    AccountLockoutConfig,
    AuthConfig,
    CertificateInfo,
    CheckStatus,
    CORSConfig,
    CORSProfileName,
    HSTSConfig,
    JWTAlgorithm,
    JWTConfig,
    MFAConfig,
    MFARequirement,
    PasswordPolicy,
    SecurityCheck,
    SecurityDomain,
    SessionConfig,
    TLSConfig,
    TLSProfileName,
    TLSVersion,
)
from app.services.security_hardening_service import (
    ALL_STRONG_CIPHERS,
    CORS_PROFILES,
    TLS_12_ACCEPTABLE_CIPHERS,
    TLS_12_STRONG_CIPHERS,
    TLS_13_CIPHERS,
    TLS_PROFILES,
    WEAK_CIPHERS,
    SecurityHardeningService,
    get_security_hardening_service,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def dev_service() -> SecurityHardeningService:
    """Service configured for development environment."""
    return SecurityHardeningService(environment="development")


@pytest.fixture
def prod_service() -> SecurityHardeningService:
    """Service configured for production environment."""
    return SecurityHardeningService(environment="production")


@pytest.fixture
def custom_tls_config() -> TLSConfig:
    """TLS config with custom settings."""
    return TLSConfig(
        minimum_version=TLSVersion.TLS_1_2,
        preferred_version=TLSVersion.TLS_1_3,
        allowed_cipher_suites=list(TLS_13_CIPHERS + TLS_12_STRONG_CIPHERS),
        hsts=HSTSConfig(enabled=True, max_age=31536000, include_subdomains=True),
        profile=TLSProfileName.INTERMEDIATE,
    )


@pytest.fixture
def custom_auth_config() -> AuthConfig:
    """Auth config with custom settings."""
    return AuthConfig(
        password_policy=PasswordPolicy(min_length=12),
        session=SessionConfig(max_idle_minutes=30),
        jwt=JWTConfig(algorithm=JWTAlgorithm.RS256, access_token_expire_minutes=15),
        lockout=AccountLockoutConfig(max_failed_attempts=5),
        mfa=MFAConfig(requirement=MFARequirement.REQUIRED_ADMIN),
    )


@pytest.fixture
def custom_cors_config() -> CORSConfig:
    """CORS config with explicit origins."""
    return CORSConfig(
        allowed_origins=["https://app.example.com", "https://admin.example.com"],
        allow_credentials=True,
        max_age=600,
        profile=CORSProfileName.STRICT,
    )


@pytest.fixture
def strict_service(
    custom_tls_config: TLSConfig,
    custom_auth_config: AuthConfig,
    custom_cors_config: CORSConfig,
) -> SecurityHardeningService:
    """Fully configured service for strict testing."""
    return SecurityHardeningService(
        environment="production",
        tls_config=custom_tls_config,
        auth_config=custom_auth_config,
        cors_config=custom_cors_config,
    )


# ============================================================================
# TLS Version Checks (CISO-2)
# ============================================================================


class TestTLSVersionValidation:
    """Tests for TLS version validation."""

    def test_tls_13_passes(self, dev_service: SecurityHardeningService) -> None:
        """TLS 1.3 passes validation."""
        assert dev_service.validate_tls_version(TLSVersion.TLS_1_3) is True

    def test_tls_12_passes(self, dev_service: SecurityHardeningService) -> None:
        """TLS 1.2 passes when minimum is 1.2."""
        assert dev_service.validate_tls_version(TLSVersion.TLS_1_2) is True

    def test_tls_11_fails(self, dev_service: SecurityHardeningService) -> None:
        """TLS 1.1 fails when minimum is 1.2."""
        assert dev_service.validate_tls_version(TLSVersion.TLS_1_1) is False

    def test_tls_10_fails(self, dev_service: SecurityHardeningService) -> None:
        """TLS 1.0 fails when minimum is 1.2."""
        assert dev_service.validate_tls_version(TLSVersion.TLS_1_0) is False

    def test_modern_profile_rejects_tls_12(self) -> None:
        """MODERN profile (TLS 1.3 only) rejects TLS 1.2."""
        tls = TLSConfig(
            minimum_version=TLSVersion.TLS_1_3,
            preferred_version=TLSVersion.TLS_1_3,
            allowed_cipher_suites=TLS_13_CIPHERS,
            profile=TLSProfileName.MODERN,
        )
        svc = SecurityHardeningService(tls_config=tls)
        assert svc.validate_tls_version(TLSVersion.TLS_1_2) is False
        assert svc.validate_tls_version(TLSVersion.TLS_1_3) is True


# ============================================================================
# Cipher Suite Validation (CISO-2)
# ============================================================================


class TestCipherSuiteValidation:
    """Tests for cipher suite classification and validation."""

    def test_tls13_cipher_classified_strong(self, dev_service: SecurityHardeningService) -> None:
        """TLS 1.3 ciphers are classified as strong."""
        suite = dev_service.validate_cipher_suite("TLS_AES_256_GCM_SHA384")
        assert suite.strength == "strong"
        assert suite.encryption == "AES-256-GCM"

    def test_ecdhe_rsa_cipher_classified_strong(self, dev_service: SecurityHardeningService) -> None:
        """ECDHE_RSA AEAD ciphers are classified as strong."""
        suite = dev_service.validate_cipher_suite("TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384")
        assert suite.strength == "strong"
        assert suite.key_exchange == "ECDHE"
        assert suite.authentication == "RSA"

    def test_cbc_cipher_classified_acceptable(self, dev_service: SecurityHardeningService) -> None:
        """CBC ciphers are classified as acceptable."""
        suite = dev_service.validate_cipher_suite("TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA384")
        assert suite.strength == "acceptable"

    def test_rsa_only_cipher_classified_weak(self, dev_service: SecurityHardeningService) -> None:
        """RSA-only (no ECDHE/DHE) ciphers are classified as weak."""
        suite = dev_service.validate_cipher_suite("TLS_RSA_WITH_AES_256_GCM_SHA384")
        assert suite.strength == "weak"

    def test_rc4_cipher_classified_weak(self, dev_service: SecurityHardeningService) -> None:
        """RC4 ciphers are classified as weak."""
        suite = dev_service.validate_cipher_suite("TLS_RSA_WITH_RC4_128_SHA")
        assert suite.strength == "weak"
        assert suite.encryption == "RC4"

    def test_unknown_cipher_classified_unknown(self, dev_service: SecurityHardeningService) -> None:
        """Unknown ciphers are classified as unknown."""
        suite = dev_service.validate_cipher_suite("CUSTOM_UNKNOWN_CIPHER")
        assert suite.strength == "unknown"

    def test_cipher_in_allowed_list(self, dev_service: SecurityHardeningService) -> None:
        """Cipher in the allowed list returns True."""
        # TLS 1.3 ciphers should be in the default allowed list
        assert dev_service.is_cipher_allowed("TLS_AES_256_GCM_SHA384") is True

    def test_weak_cipher_not_in_allowed_list(self, dev_service: SecurityHardeningService) -> None:
        """Weak ciphers are not in the default allowed list."""
        assert dev_service.is_cipher_allowed("TLS_RSA_WITH_RC4_128_SHA") is False

    def test_chacha20_cipher_strong(self, dev_service: SecurityHardeningService) -> None:
        """ChaCha20 ciphers are classified as strong."""
        suite = dev_service.validate_cipher_suite("TLS_CHACHA20_POLY1305_SHA256")
        assert suite.strength == "strong"
        assert suite.encryption == "ChaCha20-Poly1305"

    def test_dhe_rsa_cipher_strong(self, dev_service: SecurityHardeningService) -> None:
        """DHE_RSA ciphers are classified as strong."""
        suite = dev_service.validate_cipher_suite("TLS_DHE_RSA_WITH_AES_256_GCM_SHA384")
        assert suite.strength == "strong"
        assert suite.key_exchange == "DHE"

    def test_ecdsa_cipher_strong(self, dev_service: SecurityHardeningService) -> None:
        """ECDSA ciphers are classified as strong."""
        suite = dev_service.validate_cipher_suite("TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384")
        assert suite.strength == "strong"
        assert suite.authentication == "ECDSA"


# ============================================================================
# HSTS & Certificate Checks (CISO-2)
# ============================================================================


class TestHSTSAndCertificates:
    """Tests for HSTS configuration and certificate validation."""

    def test_hsts_header_value(self) -> None:
        """HSTS header value is correctly formatted."""
        hsts = HSTSConfig(
            enabled=True, max_age=31536000, include_subdomains=True, preload=True
        )
        assert hsts.header_value == "max-age=31536000; includeSubDomains; preload"

    def test_hsts_header_without_preload(self) -> None:
        """HSTS header value without preload."""
        hsts = HSTSConfig(enabled=True, max_age=31536000, include_subdomains=True, preload=False)
        assert hsts.header_value == "max-age=31536000; includeSubDomains"

    def test_hsts_header_minimal(self) -> None:
        """HSTS header with minimal directives."""
        hsts = HSTSConfig(enabled=True, max_age=86400, include_subdomains=False, preload=False)
        assert hsts.header_value == "max-age=86400"

    def test_expired_cert_fails(self, dev_service: SecurityHardeningService) -> None:
        """Expired certificate produces FAIL check."""
        cert = CertificateInfo(
            subject="CN=expired.example.com",
            is_expired=True,
            days_until_expiry=-10,
        )
        checks = dev_service.validate_certificate(cert)
        expiry_checks = [c for c in checks if "expir" in c.name.lower()]
        assert any(c.status == CheckStatus.FAIL for c in expiry_checks)

    def test_cert_expiring_soon_warns(self, dev_service: SecurityHardeningService) -> None:
        """Certificate expiring within 30 days produces WARN."""
        cert = CertificateInfo(
            subject="CN=soon.example.com",
            is_expired=False,
            days_until_expiry=15,
        )
        checks = dev_service.validate_certificate(cert)
        expiry_checks = [c for c in checks if "expir" in c.name.lower()]
        assert any(c.status == CheckStatus.WARN for c in expiry_checks)

    def test_valid_cert_passes(self, dev_service: SecurityHardeningService) -> None:
        """Valid certificate produces PASS check."""
        cert = CertificateInfo(
            subject="CN=valid.example.com",
            is_expired=False,
            days_until_expiry=365,
            chain_valid=True,
        )
        checks = dev_service.validate_certificate(cert)
        expiry_checks = [c for c in checks if "expir" in c.name.lower()]
        assert all(c.status == CheckStatus.PASS for c in expiry_checks)

    def test_self_signed_cert_fails_in_production(self, prod_service: SecurityHardeningService) -> None:
        """Self-signed certificate FAIL in production."""
        cert = CertificateInfo(
            subject="CN=selfsigned.example.com",
            is_self_signed=True,
            is_expired=False,
            days_until_expiry=365,
            chain_valid=True,
        )
        checks = prod_service.validate_certificate(cert)
        ca_checks = [c for c in checks if "authority" in c.name.lower()]
        assert any(c.status == CheckStatus.FAIL for c in ca_checks)

    def test_self_signed_cert_warns_in_dev(self, dev_service: SecurityHardeningService) -> None:
        """Self-signed certificate WARN in development."""
        cert = CertificateInfo(
            subject="CN=selfsigned.example.com",
            is_self_signed=True,
            is_expired=False,
            days_until_expiry=365,
            chain_valid=True,
        )
        checks = dev_service.validate_certificate(cert)
        ca_checks = [c for c in checks if "authority" in c.name.lower()]
        assert any(c.status == CheckStatus.WARN for c in ca_checks)

    def test_invalid_cert_chain_fails(self, dev_service: SecurityHardeningService) -> None:
        """Invalid certificate chain produces FAIL."""
        cert = CertificateInfo(
            subject="CN=badchain.example.com",
            is_expired=False,
            days_until_expiry=365,
            chain_valid=False,
        )
        checks = dev_service.validate_certificate(cert)
        chain_checks = [c for c in checks if "chain" in c.name.lower()]
        assert any(c.status == CheckStatus.FAIL for c in chain_checks)


# ============================================================================
# Password Policy Validation (CISO-3)
# ============================================================================


class TestPasswordPolicy:
    """Tests for password policy validation."""

    def test_valid_password(self, dev_service: SecurityHardeningService) -> None:
        """Password meeting all requirements passes."""
        valid, violations = dev_service.validate_password("SecureP@ss123!")
        assert valid is True
        assert violations == []

    def test_too_short_password(self, dev_service: SecurityHardeningService) -> None:
        """Password too short fails."""
        valid, violations = dev_service.validate_password("Sh0rt!")
        assert valid is False
        assert any("at least" in v for v in violations)

    def test_no_uppercase_fails(self, dev_service: SecurityHardeningService) -> None:
        """Password without uppercase fails."""
        valid, violations = dev_service.validate_password("securep@ss123!")
        assert valid is False
        assert any("uppercase" in v for v in violations)

    def test_no_lowercase_fails(self, dev_service: SecurityHardeningService) -> None:
        """Password without lowercase fails."""
        valid, violations = dev_service.validate_password("SECUREP@SS123!")
        assert valid is False
        assert any("lowercase" in v for v in violations)

    def test_no_digit_fails(self, dev_service: SecurityHardeningService) -> None:
        """Password without digit fails."""
        valid, violations = dev_service.validate_password("SecureP@ssword!")
        assert valid is False
        assert any("digit" in v for v in violations)

    def test_no_special_char_fails(self, dev_service: SecurityHardeningService) -> None:
        """Password without special character fails."""
        valid, violations = dev_service.validate_password("SecurePassword1")
        assert valid is False
        assert any("special" in v for v in violations)

    def test_multiple_violations_reported(self, dev_service: SecurityHardeningService) -> None:
        """Multiple violations are all reported."""
        valid, violations = dev_service.validate_password("short")
        assert valid is False
        assert len(violations) >= 3  # too short, no uppercase, no digit, no special

    def test_custom_min_length(self) -> None:
        """Custom minimum length is enforced."""
        auth = AuthConfig(password_policy=PasswordPolicy(min_length=20))
        svc = SecurityHardeningService(auth_config=auth)
        valid, violations = svc.validate_password("SecureP@ss123!")  # 14 chars
        assert valid is False
        assert any("20" in v for v in violations)

    def test_password_policy_check_pass(self, dev_service: SecurityHardeningService) -> None:
        """Password policy check PASS for 12+ length."""
        checks = dev_service.validate_password_policy()
        length_checks = [c for c in checks if "length" in c.name.lower()]
        assert all(c.status == CheckStatus.PASS for c in length_checks)

    def test_password_policy_check_fail_for_short_min(self) -> None:
        """Password policy check FAIL for min_length < 8."""
        auth = AuthConfig(password_policy=PasswordPolicy(min_length=6))
        svc = SecurityHardeningService(auth_config=auth)
        checks = svc.validate_password_policy()
        length_checks = [c for c in checks if "length" in c.name.lower()]
        assert any(c.status == CheckStatus.FAIL for c in length_checks)

    def test_password_policy_check_warn_for_medium_min(self) -> None:
        """Password policy check WARN for min_length 8-11."""
        auth = AuthConfig(password_policy=PasswordPolicy(min_length=10))
        svc = SecurityHardeningService(auth_config=auth)
        checks = svc.validate_password_policy()
        length_checks = [c for c in checks if "length" in c.name.lower()]
        assert any(c.status == CheckStatus.WARN for c in length_checks)


# ============================================================================
# Session Configuration Checks (CISO-3)
# ============================================================================


class TestSessionConfig:
    """Tests for session configuration validation."""

    def test_session_idle_within_limit(self, dev_service: SecurityHardeningService) -> None:
        """Session idle timeout <= 60 min passes."""
        checks = dev_service.validate_session_config()
        idle_checks = [c for c in checks if "idle" in c.name.lower()]
        assert all(c.status == CheckStatus.PASS for c in idle_checks)

    def test_session_idle_too_long_warns(self) -> None:
        """Session idle timeout > 60 min warns."""
        auth = AuthConfig(session=SessionConfig(max_idle_minutes=120))
        svc = SecurityHardeningService(auth_config=auth)
        checks = svc.validate_session_config()
        idle_checks = [c for c in checks if "idle" in c.name.lower()]
        assert any(c.status == CheckStatus.WARN for c in idle_checks)

    def test_insecure_cookie_fails_in_production(self) -> None:
        """Insecure cookie flag fails in production."""
        auth = AuthConfig(session=SessionConfig(secure_cookie=False))
        svc = SecurityHardeningService(environment="production", auth_config=auth)
        checks = svc.validate_session_config()
        secure_checks = [c for c in checks if "secure" in c.name.lower() and "cookie" in c.name.lower()]
        assert any(c.status == CheckStatus.FAIL for c in secure_checks)

    def test_httponly_disabled_warns(self) -> None:
        """HttpOnly disabled warns."""
        auth = AuthConfig(session=SessionConfig(http_only=False))
        svc = SecurityHardeningService(auth_config=auth)
        checks = svc.validate_session_config()
        httponly_checks = [c for c in checks if "httponly" in c.name.lower()]
        assert any(c.status == CheckStatus.WARN for c in httponly_checks)

    def test_samesite_none_warns_production(self) -> None:
        """SameSite=None warns in production."""
        auth = AuthConfig(session=SessionConfig(same_site="None"))
        svc = SecurityHardeningService(environment="production", auth_config=auth)
        checks = svc.validate_session_config()
        samesite_checks = [c for c in checks if "samesite" in c.name.lower()]
        assert any(c.status == CheckStatus.WARN for c in samesite_checks)


# ============================================================================
# JWT Configuration Checks (CISO-3)
# ============================================================================


class TestJWTConfig:
    """Tests for JWT configuration validation."""

    def test_rs256_passes(self, dev_service: SecurityHardeningService) -> None:
        """RS256 algorithm passes."""
        checks = dev_service.validate_jwt_config()
        algo_checks = [c for c in checks if "algorithm" in c.name.lower()]
        assert all(c.status == CheckStatus.PASS for c in algo_checks)

    def test_hs256_warns_in_production(self) -> None:
        """HS256 warns in production."""
        auth = AuthConfig(jwt=JWTConfig(algorithm=JWTAlgorithm.HS256))
        svc = SecurityHardeningService(environment="production", auth_config=auth)
        checks = svc.validate_jwt_config()
        algo_checks = [c for c in checks if "algorithm" in c.name.lower()]
        assert any(c.status == CheckStatus.WARN for c in algo_checks)

    def test_long_access_token_warns(self) -> None:
        """Access token > 60 min warns."""
        auth = AuthConfig(jwt=JWTConfig(access_token_expire_minutes=120))
        svc = SecurityHardeningService(auth_config=auth)
        checks = svc.validate_jwt_config()
        ttl_checks = [c for c in checks if "access" in c.name.lower() and "lifetime" in c.name.lower()]
        assert any(c.status == CheckStatus.WARN for c in ttl_checks)

    def test_short_access_token_passes(self, dev_service: SecurityHardeningService) -> None:
        """15 min access token passes."""
        checks = dev_service.validate_jwt_config()
        ttl_checks = [c for c in checks if "access" in c.name.lower() and "lifetime" in c.name.lower()]
        assert all(c.status == CheckStatus.PASS for c in ttl_checks)

    def test_long_refresh_token_warns(self) -> None:
        """Refresh token > 30 days warns."""
        auth = AuthConfig(jwt=JWTConfig(refresh_token_expire_days=60))
        svc = SecurityHardeningService(auth_config=auth)
        checks = svc.validate_jwt_config()
        refresh_checks = [c for c in checks if "refresh" in c.name.lower()]
        assert any(c.status == CheckStatus.WARN for c in refresh_checks)


# ============================================================================
# Account Lockout Logic (CISO-3)
# ============================================================================


class TestAccountLockout:
    """Tests for account lockout calculations."""

    def test_under_threshold_no_lockout(self, dev_service: SecurityHardeningService) -> None:
        """Below threshold returns 0 lockout minutes."""
        assert dev_service.calculate_lockout_duration(3) == 0

    def test_at_threshold_locks_out(self, dev_service: SecurityHardeningService) -> None:
        """At threshold triggers lockout."""
        duration = dev_service.calculate_lockout_duration(5)
        assert duration == 15  # initial lockout_duration_minutes

    def test_progressive_backoff(self, dev_service: SecurityHardeningService) -> None:
        """Progressive backoff doubles duration."""
        # 10 failures = 1 additional lockout (2x)
        duration = dev_service.calculate_lockout_duration(10)
        assert duration == 30  # 15 * 2^1

    def test_max_lockout_cap(self, dev_service: SecurityHardeningService) -> None:
        """Lockout duration is capped at max."""
        # Very high failure count
        duration = dev_service.calculate_lockout_duration(1000)
        assert duration <= 1440  # max_lockout_minutes

    def test_no_progressive_backoff(self) -> None:
        """Without progressive backoff, duration is fixed."""
        auth = AuthConfig(
            lockout=AccountLockoutConfig(
                max_failed_attempts=5,
                lockout_duration_minutes=15,
                progressive_backoff=False,
            )
        )
        svc = SecurityHardeningService(auth_config=auth)
        assert svc.calculate_lockout_duration(10) == 15
        assert svc.calculate_lockout_duration(100) == 15

    def test_lockout_threshold_check_pass(self, dev_service: SecurityHardeningService) -> None:
        """Lockout threshold of 5 passes validation."""
        checks = dev_service.validate_lockout_config()
        threshold_checks = [c for c in checks if "threshold" in c.name.lower()]
        assert all(c.status == CheckStatus.PASS for c in threshold_checks)

    def test_lockout_threshold_too_high_warns(self) -> None:
        """Lockout threshold > 10 warns."""
        auth = AuthConfig(lockout=AccountLockoutConfig(max_failed_attempts=20))
        svc = SecurityHardeningService(auth_config=auth)
        checks = svc.validate_lockout_config()
        threshold_checks = [c for c in checks if "threshold" in c.name.lower()]
        assert any(c.status == CheckStatus.WARN for c in threshold_checks)

    def test_lockout_disabled_fails(self) -> None:
        """Lockout threshold <= 0 fails."""
        auth = AuthConfig(lockout=AccountLockoutConfig(max_failed_attempts=0))
        svc = SecurityHardeningService(auth_config=auth)
        checks = svc.validate_lockout_config()
        threshold_checks = [c for c in checks if "threshold" in c.name.lower()]
        assert any(c.status == CheckStatus.FAIL for c in threshold_checks)


# ============================================================================
# MFA Configuration (CISO-3)
# ============================================================================


class TestMFAConfig:
    """Tests for MFA configuration validation."""

    def test_mfa_required_admin_passes(self, dev_service: SecurityHardeningService) -> None:
        """MFA required for admin passes."""
        checks = dev_service.validate_mfa_config()
        mfa_checks = [c for c in checks if "mfa" in c.name.lower()]
        assert all(c.status == CheckStatus.PASS for c in mfa_checks)

    def test_mfa_disabled_fails_production(self) -> None:
        """MFA disabled fails in production."""
        auth = AuthConfig(mfa=MFAConfig(requirement=MFARequirement.DISABLED))
        svc = SecurityHardeningService(environment="production", auth_config=auth)
        checks = svc.validate_mfa_config()
        mfa_checks = [c for c in checks if "mfa" in c.name.lower()]
        assert any(c.status == CheckStatus.FAIL for c in mfa_checks)

    def test_mfa_disabled_warns_dev(self) -> None:
        """MFA disabled warns in development."""
        auth = AuthConfig(mfa=MFAConfig(requirement=MFARequirement.DISABLED))
        svc = SecurityHardeningService(environment="development", auth_config=auth)
        checks = svc.validate_mfa_config()
        mfa_checks = [c for c in checks if "mfa" in c.name.lower()]
        assert any(c.status == CheckStatus.WARN for c in mfa_checks)

    def test_mfa_recommended_warns(self) -> None:
        """MFA recommended-only warns."""
        auth = AuthConfig(mfa=MFAConfig(requirement=MFARequirement.RECOMMENDED))
        svc = SecurityHardeningService(auth_config=auth)
        checks = svc.validate_mfa_config()
        mfa_checks = [c for c in checks if "mfa" in c.name.lower()]
        assert any(c.status == CheckStatus.WARN for c in mfa_checks)


# ============================================================================
# CORS Validation (CISO-4)
# ============================================================================


class TestCORSValidation:
    """Tests for CORS configuration validation."""

    def test_allowed_origin_passes(self, strict_service: SecurityHardeningService) -> None:
        """Origin in allowed list is accepted."""
        result = strict_service.validate_origin("https://app.example.com")
        assert result.allowed is True
        assert result.matched_rule == "https://app.example.com"

    def test_blocked_origin_denied(self, strict_service: SecurityHardeningService) -> None:
        """Origin not in allowed list is denied."""
        result = strict_service.validate_origin("https://evil.example.com")
        assert result.allowed is False
        assert result.reason is not None

    def test_wildcard_without_credentials(self) -> None:
        """Wildcard origin without credentials is allowed."""
        cors = CORSConfig(allowed_origins=["*"], allow_credentials=False)
        svc = SecurityHardeningService(cors_config=cors)
        result = svc.validate_origin("https://any.example.com")
        assert result.allowed is True
        assert result.matched_rule == "wildcard (*)"

    def test_wildcard_with_credentials_blocked(self) -> None:
        """Wildcard origin with credentials is blocked."""
        cors = CORSConfig(allowed_origins=["*"], allow_credentials=True)
        svc = SecurityHardeningService(cors_config=cors)
        result = svc.validate_origin("https://any.example.com")
        assert result.allowed is False

    def test_origin_trailing_slash_normalized(self, strict_service: SecurityHardeningService) -> None:
        """Trailing slash on origin is normalized."""
        result = strict_service.validate_origin("https://app.example.com/")
        assert result.allowed is True

    def test_cors_wildcard_fails_production(self) -> None:
        """Wildcard CORS origin fails in production."""
        cors = CORSConfig(allowed_origins=["*"])
        svc = SecurityHardeningService(environment="production", cors_config=cors)
        checks = svc.validate_cors_config()
        wildcard_checks = [c for c in checks if "wildcard" in c.name.lower() and c.id == "cors-wildcard"]
        assert any(c.status == CheckStatus.FAIL for c in wildcard_checks)

    def test_cors_wildcard_warns_dev(self) -> None:
        """Wildcard CORS origin warns in development."""
        cors = CORSConfig(allowed_origins=["*"])
        svc = SecurityHardeningService(environment="development", cors_config=cors)
        checks = svc.validate_cors_config()
        wildcard_checks = [c for c in checks if "wildcard" in c.name.lower() and c.id == "cors-wildcard"]
        assert any(c.status == CheckStatus.WARN for c in wildcard_checks)

    def test_cors_no_origins_fails(self) -> None:
        """No CORS origins configured fails."""
        cors = CORSConfig(allowed_origins=[])
        svc = SecurityHardeningService(cors_config=cors)
        checks = svc.validate_cors_config()
        empty_checks = [c for c in checks if "configured" in c.name.lower()]
        assert any(c.status == CheckStatus.FAIL for c in empty_checks)

    def test_cors_credentials_with_wildcard_fails(self) -> None:
        """Credentials + wildcard fails."""
        cors = CORSConfig(allowed_origins=["*"], allow_credentials=True)
        svc = SecurityHardeningService(cors_config=cors)
        checks = svc.validate_cors_config()
        creds_checks = [c for c in checks if "credentials" in c.name.lower()]
        assert any(c.status == CheckStatus.FAIL for c in creds_checks)

    def test_cors_max_age_too_high_warns(self) -> None:
        """Max age > 24 hours warns."""
        cors = CORSConfig(
            allowed_origins=["https://example.com"],
            max_age=172800,  # 48 hours
        )
        svc = SecurityHardeningService(cors_config=cors)
        checks = svc.validate_cors_config()
        age_checks = [c for c in checks if "max age" in c.name.lower()]
        assert any(c.status == CheckStatus.WARN for c in age_checks)

    def test_cors_invalid_origin_format_fails(self) -> None:
        """Invalid origin format (no protocol) fails."""
        cors = CORSConfig(allowed_origins=["example.com", "http://valid.com"])
        svc = SecurityHardeningService(cors_config=cors)
        checks = svc.validate_cors_config()
        format_checks = [c for c in checks if "format" in c.name.lower()]
        assert any(c.status == CheckStatus.FAIL for c in format_checks)

    def test_cors_explicit_origins_pass(self, strict_service: SecurityHardeningService) -> None:
        """Explicit origins with proper format pass."""
        checks = strict_service.validate_cors_config()
        wildcard_checks = [c for c in checks if c.id == "cors-wildcard"]
        assert all(c.status == CheckStatus.PASS for c in wildcard_checks)


# ============================================================================
# Security Audit & Scoring
# ============================================================================


class TestSecurityAudit:
    """Tests for security audit report generation."""

    def test_audit_returns_all_domains(self, dev_service: SecurityHardeningService) -> None:
        """Audit covers TLS, Auth, and CORS domains."""
        report = dev_service.run_audit()
        domains = {c.domain for c in report.checks}
        assert SecurityDomain.TLS in domains
        assert SecurityDomain.AUTH in domains
        assert SecurityDomain.CORS in domains

    def test_audit_score_range(self, dev_service: SecurityHardeningService) -> None:
        """Audit score is between 0 and 100."""
        report = dev_service.run_audit()
        assert 0 <= report.overall_score <= 100
        assert 0 <= report.tls_score <= 100
        assert 0 <= report.auth_score <= 100
        assert 0 <= report.cors_score <= 100

    def test_audit_counts_match(self, dev_service: SecurityHardeningService) -> None:
        """Pass + warn + fail counts equal total checks."""
        report = dev_service.run_audit()
        assert report.pass_count + report.warn_count + report.fail_count == len(report.checks)

    def test_perfect_score_all_pass(self) -> None:
        """All PASS checks yield score of 100."""
        score = SecurityHardeningService._calculate_domain_score([
            SecurityCheck(
                id="test", domain=SecurityDomain.TLS, name="test",
                description="test", status=CheckStatus.PASS,
            ),
            SecurityCheck(
                id="test2", domain=SecurityDomain.TLS, name="test2",
                description="test2", status=CheckStatus.PASS,
            ),
        ])
        assert score == 100

    def test_zero_score_all_fail(self) -> None:
        """All FAIL checks yield score of 0."""
        score = SecurityHardeningService._calculate_domain_score([
            SecurityCheck(
                id="test", domain=SecurityDomain.TLS, name="test",
                description="test", status=CheckStatus.FAIL,
            ),
        ])
        assert score == 0

    def test_mixed_score(self) -> None:
        """Mix of PASS, WARN, FAIL yields expected score."""
        score = SecurityHardeningService._calculate_domain_score([
            SecurityCheck(
                id="t1", domain=SecurityDomain.TLS, name="t1",
                description="t1", status=CheckStatus.PASS,
            ),
            SecurityCheck(
                id="t2", domain=SecurityDomain.TLS, name="t2",
                description="t2", status=CheckStatus.WARN,
            ),
            SecurityCheck(
                id="t3", domain=SecurityDomain.TLS, name="t3",
                description="t3", status=CheckStatus.FAIL,
            ),
        ])
        # 1.0 + 0.5 + 0.0 = 1.5 / 3 = 0.5 = 50
        assert score == 50

    def test_empty_checks_score_100(self) -> None:
        """Empty check list yields 100."""
        score = SecurityHardeningService._calculate_domain_score([])
        assert score == 100

    def test_audit_includes_recommendations(self, dev_service: SecurityHardeningService) -> None:
        """Audit includes recommendations for non-PASS checks."""
        report = dev_service.run_audit()
        if report.warn_count + report.fail_count > 0:
            assert len(report.recommendations) > 0

    def test_recommendations_sorted_by_priority(self, dev_service: SecurityHardeningService) -> None:
        """Recommendations are sorted by priority."""
        report = dev_service.run_audit()
        if len(report.recommendations) > 1:
            priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            for i in range(len(report.recommendations) - 1):
                curr = priority_order.get(report.recommendations[i].priority, 4)
                nxt = priority_order.get(report.recommendations[i + 1].priority, 4)
                assert curr <= nxt

    def test_strict_service_high_score(self, strict_service: SecurityHardeningService) -> None:
        """Properly configured service gets a high score."""
        report = strict_service.run_audit()
        assert report.overall_score >= 70


# ============================================================================
# TLS Checks Integration
# ============================================================================


class TestTLSChecks:
    """Tests for TLS check generation."""

    def test_tls_10_min_version_fails(self) -> None:
        """TLS 1.0 minimum version fails."""
        tls = TLSConfig(minimum_version=TLSVersion.TLS_1_0, allowed_cipher_suites=[])
        svc = SecurityHardeningService(tls_config=tls)
        checks = svc.run_tls_checks()
        version_checks = [c for c in checks if "min" in c.name.lower() and "version" in c.name.lower()]
        assert any(c.status == CheckStatus.FAIL for c in version_checks)

    def test_tls_12_min_version_passes(self, dev_service: SecurityHardeningService) -> None:
        """TLS 1.2 minimum version passes."""
        checks = dev_service.run_tls_checks()
        version_checks = [c for c in checks if "min" in c.name.lower() and "version" in c.name.lower()]
        assert all(c.status == CheckStatus.PASS for c in version_checks)

    def test_preferred_not_13_warns(self) -> None:
        """Preferred version != 1.3 warns."""
        tls = TLSConfig(
            minimum_version=TLSVersion.TLS_1_2,
            preferred_version=TLSVersion.TLS_1_2,
            allowed_cipher_suites=[],
        )
        svc = SecurityHardeningService(tls_config=tls)
        checks = svc.run_tls_checks()
        pref_checks = [c for c in checks if "preferred" in c.name.lower()]
        assert any(c.status == CheckStatus.WARN for c in pref_checks)

    def test_hsts_disabled_fails(self) -> None:
        """HSTS disabled fails."""
        tls = TLSConfig(
            hsts=HSTSConfig(enabled=False),
            allowed_cipher_suites=[],
        )
        svc = SecurityHardeningService(tls_config=tls)
        checks = svc.run_tls_checks()
        hsts_checks = [c for c in checks if "hsts" in c.name.lower() and c.id == "tls-hsts"]
        assert any(c.status == CheckStatus.FAIL for c in hsts_checks)

    def test_weak_ciphers_fail(self) -> None:
        """Weak ciphers in config produce FAIL."""
        tls = TLSConfig(
            allowed_cipher_suites=["TLS_RSA_WITH_RC4_128_SHA"],
        )
        svc = SecurityHardeningService(tls_config=tls)
        checks = svc.run_tls_checks()
        cipher_checks = [c for c in checks if "cipher" in c.name.lower() or "weak" in c.name.lower()]
        assert any(c.status == CheckStatus.FAIL for c in cipher_checks)


# ============================================================================
# Profile Tests
# ============================================================================


class TestProfiles:
    """Tests for TLS and CORS profile management."""

    def test_tls_profiles_available(self) -> None:
        """All three TLS profiles are available."""
        profiles = SecurityHardeningService.get_tls_profiles()
        names = {p.name for p in profiles}
        assert TLSProfileName.MODERN in names
        assert TLSProfileName.INTERMEDIATE in names
        assert TLSProfileName.OLD in names

    def test_cors_profiles_available(self) -> None:
        """All three CORS profiles are available."""
        profiles = SecurityHardeningService.get_cors_profiles()
        names = {p.name for p in profiles}
        assert CORSProfileName.STRICT in names
        assert CORSProfileName.DEVELOPMENT in names
        assert CORSProfileName.API_ONLY in names

    def test_modern_profile_tls_13_only(self) -> None:
        """MODERN profile only includes TLS 1.3 ciphers."""
        profile = TLS_PROFILES[TLSProfileName.MODERN]
        assert profile.minimum_version == TLSVersion.TLS_1_3
        for cipher in profile.cipher_suites:
            assert cipher in TLS_13_CIPHERS

    def test_intermediate_profile_includes_tls_12(self) -> None:
        """INTERMEDIATE profile includes TLS 1.2 ciphers."""
        profile = TLS_PROFILES[TLSProfileName.INTERMEDIATE]
        assert profile.minimum_version == TLSVersion.TLS_1_2
        # Should have both TLS 1.3 and TLS 1.2 ciphers
        has_12 = any(c in TLS_12_STRONG_CIPHERS for c in profile.cipher_suites)
        has_13 = any(c in TLS_13_CIPHERS for c in profile.cipher_suites)
        assert has_12 and has_13

    def test_development_cors_profile(self) -> None:
        """DEVELOPMENT CORS profile includes localhost origins."""
        profile = CORS_PROFILES[CORSProfileName.DEVELOPMENT]
        assert any("localhost" in o for o in profile.allowed_origins)

    def test_api_only_cors_profile_no_credentials(self) -> None:
        """API_ONLY CORS profile disables credentials."""
        profile = CORS_PROFILES[CORSProfileName.API_ONLY]
        assert profile.allow_credentials is False

    def test_production_defaults_to_modern_or_intermediate(self) -> None:
        """Production environment selects MODERN TLS profile."""
        svc = SecurityHardeningService(environment="production")
        assert svc.tls_config.profile == TLSProfileName.MODERN

    def test_dev_defaults_to_intermediate(self) -> None:
        """Development environment selects INTERMEDIATE TLS profile."""
        svc = SecurityHardeningService(environment="development")
        assert svc.tls_config.profile == TLSProfileName.INTERMEDIATE


# ============================================================================
# Recommendations
# ============================================================================


class TestRecommendations:
    """Tests for security recommendations generation."""

    def test_recommendations_have_required_fields(self, dev_service: SecurityHardeningService) -> None:
        """All recommendations have required fields."""
        resp = dev_service.get_recommendations()
        for rec in resp.recommendations:
            assert rec.id
            assert rec.domain
            assert rec.title
            assert rec.description
            assert rec.priority in ("critical", "high", "medium", "low")
            assert rec.effort in ("low", "medium", "high")

    def test_recommendations_response_structure(self, dev_service: SecurityHardeningService) -> None:
        """Recommendations response has correct structure."""
        resp = dev_service.get_recommendations()
        assert resp.environment == "development"
        assert resp.total_recommendations == len(resp.recommendations)
        assert resp.critical_count >= 0
        assert resp.high_count >= 0


# ============================================================================
# Singleton
# ============================================================================


class TestSingleton:
    """Tests for singleton accessor."""

    def test_get_service_returns_instance(self) -> None:
        """get_security_hardening_service returns an instance."""
        import app.services.security_hardening_service as module
        module._service = None  # reset singleton
        svc = get_security_hardening_service()
        assert isinstance(svc, SecurityHardeningService)

    def test_get_service_returns_same_instance(self) -> None:
        """Singleton returns the same instance."""
        import app.services.security_hardening_service as module
        module._service = None
        svc1 = get_security_hardening_service()
        svc2 = get_security_hardening_service()
        assert svc1 is svc2


# ============================================================================
# API Endpoint Tests
# ============================================================================


class TestAPIEndpoints:
    """Tests for API endpoint responses."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create a TestClient for the FastAPI app."""
        from app.main import app
        return TestClient(app, raise_server_exceptions=False)

    def test_audit_endpoint(self, client: TestClient) -> None:
        """GET /security/audit returns 200 with report."""
        resp = client.get("/api/v1/security/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert "overall_score" in data
        assert "checks" in data
        assert "tls_config" in data
        assert "auth_config" in data
        assert "cors_config" in data

    def test_tls_config_endpoint(self, client: TestClient) -> None:
        """GET /security/tls/config returns TLS configuration."""
        resp = client.get("/api/v1/security/tls/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "minimum_version" in data
        assert "hsts" in data

    def test_tls_profiles_endpoint(self, client: TestClient) -> None:
        """GET /security/tls/profiles returns TLS profiles."""
        resp = client.get("/api/v1/security/tls/profiles")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        names = {p["name"] for p in data}
        assert "MODERN" in names

    def test_auth_config_endpoint(self, client: TestClient) -> None:
        """GET /security/auth/config returns auth configuration."""
        resp = client.get("/api/v1/security/auth/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "password_policy" in data
        assert "session" in data
        assert "jwt" in data

    def test_auth_policy_endpoint(self, client: TestClient) -> None:
        """GET /security/auth/policy returns auth policies."""
        resp = client.get("/api/v1/security/auth/policy")
        assert resp.status_code == 200
        data = resp.json()
        assert "password_policy" in data
        assert "session_config" in data
        assert "lockout_config" in data
        assert "mfa_config" in data

    def test_cors_config_endpoint(self, client: TestClient) -> None:
        """GET /security/cors/config returns CORS configuration."""
        resp = client.get("/api/v1/security/cors/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "allowed_origins" in data
        assert "allow_credentials" in data

    def test_cors_profiles_endpoint(self, client: TestClient) -> None:
        """GET /security/cors/profiles returns CORS profiles."""
        resp = client.get("/api/v1/security/cors/profiles")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3

    def test_validate_origin_endpoint(self, client: TestClient) -> None:
        """POST /security/validate-origin validates origins."""
        resp = client.post(
            "/api/v1/security/validate-origin",
            json={"origin": "http://localhost:3000"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "origin" in data
        assert "allowed" in data

    def test_recommendations_endpoint(self, client: TestClient) -> None:
        """GET /security/recommendations returns recommendations."""
        resp = client.get("/api/v1/security/recommendations")
        assert resp.status_code == 200
        data = resp.json()
        assert "recommendations" in data
        assert "total_recommendations" in data


# ============================================================================
# Stats / Health
# ============================================================================


class TestServiceStats:
    """Tests for service statistics."""

    def test_get_stats(self, dev_service: SecurityHardeningService) -> None:
        """get_stats returns expected structure."""
        stats = dev_service.get_stats()
        assert "environment" in stats
        assert "overall_score" in stats
        assert "tls_score" in stats
        assert "auth_score" in stats
        assert "cors_score" in stats
        assert "checks_total" in stats
        assert stats["checks_total"] == stats["checks_pass"] + stats["checks_warn"] + stats["checks_fail"]
