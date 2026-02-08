# Security Hardening Guide (CISO-2/3/4)

This guide covers the security hardening controls implemented for the Clinical Trial Patient Recruitment Platform.

## Overview

Three security domains are addressed:

| CISO ID | Domain | Description |
|---------|--------|-------------|
| CISO-2  | TLS Enforcement | TLS version, cipher suites, HSTS, certificate management |
| CISO-3  | Auth Defaults Hardening | Password policy, session config, JWT, lockout, MFA |
| CISO-4  | CORS Tightening | Origin allowlist, methods, credentials, preflight caching |

## TLS Configuration (CISO-2)

### Minimum Requirements

- **Minimum TLS version**: TLS 1.2
- **Preferred TLS version**: TLS 1.3
- **HSTS**: Enabled with max-age of 1 year, includeSubDomains
- **Session tickets**: Disabled (forward secrecy)
- **OCSP stapling**: Enabled

### TLS Profiles

| Profile | Min Version | Ciphers | Use Case |
|---------|-------------|---------|----------|
| MODERN | TLS 1.3 | TLS 1.3 ciphers only | Modern browsers (2020+) |
| INTERMEDIATE | TLS 1.2 | TLS 1.3 + TLS 1.2 AEAD | General purpose |
| OLD | TLS 1.2 | TLS 1.3 + TLS 1.2 AEAD + CBC | Legacy compat (not recommended) |

### Allowed Cipher Suites

**TLS 1.3 (all profiles):**
- TLS_AES_256_GCM_SHA384
- TLS_AES_128_GCM_SHA256
- TLS_CHACHA20_POLY1305_SHA256

**TLS 1.2 Strong (INTERMEDIATE+):**
- TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384
- TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256
- TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256
- TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384
- TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256
- TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256
- TLS_DHE_RSA_WITH_AES_256_GCM_SHA384
- TLS_DHE_RSA_WITH_AES_128_GCM_SHA256

### Certificate Requirements

- Must be CA-signed in production (self-signed only for development)
- Must not be expired (warn 30 days before expiry)
- Certificate chain must be valid and complete
- Certificate Transparency logging recommended

### HSTS Header

```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```

In production, the `preload` directive is included for browser preload list submission.

## Auth Defaults Hardening (CISO-3)

### Password Policy

| Setting | Value | Rationale |
|---------|-------|-----------|
| Minimum length | 12 characters | NIST SP 800-63B recommendation |
| Uppercase required | Yes | Complexity requirement |
| Lowercase required | Yes | Complexity requirement |
| Digit required | Yes | Complexity requirement |
| Special character required | Yes | Complexity requirement |
| Maximum length | 128 characters | Prevent DoS via long passwords |
| Password reuse prevention | Last 5 passwords | Prevent credential cycling |
| Maximum age | 90 days | Force periodic rotation |

### Session Configuration

| Setting | Value | Rationale |
|---------|-------|-----------|
| Idle timeout | 30 minutes | HIPAA security rule |
| Absolute timeout | 8 hours | Prevent indefinite sessions |
| Secure cookie flag | Yes | Prevent transmission over HTTP |
| HttpOnly cookie flag | Yes | Prevent XSS cookie theft |
| SameSite attribute | Lax | CSRF protection |
| Regenerate on auth | Yes | Prevent session fixation |

### JWT Configuration

| Setting | Value | Rationale |
|---------|-------|-----------|
| Algorithm | RS256 | Asymmetric signing for production |
| Access token lifetime | 15 minutes | Short-lived to limit exposure |
| Refresh token lifetime | 7 days | Balance security and usability |
| Required claims | exp, iat | Prevent token reuse |
| Clock skew leeway | 30 seconds | Account for clock drift |

### Account Lockout

| Setting | Value | Rationale |
|---------|-------|-----------|
| Max failed attempts | 5 | Brute force protection |
| Lockout duration | 15 minutes (initial) | Rate limiting |
| Progressive backoff | Yes (2x multiplier) | Escalating protection |
| Max lockout | 24 hours | Upper bound |
| Counter reset | 60 minutes | Allow recovery |

### MFA Configuration

| Setting | Value |
|---------|-------|
| Requirement | Required for admin roles |
| Methods | TOTP, WebAuthn |
| TOTP digits | 6 |
| TOTP period | 30 seconds |
| Recovery codes | 10 |
| Device trust period | 30 days |

### API Key Management

| Setting | Value |
|---------|-------|
| Rotation interval | 90 days |
| Max keys per user | 5 |
| Rate limit per key | 1000/hour |
| Key length | 48 characters |
| Storage | SHA-256 hash |

## CORS Tightening (CISO-4)

### Baseline Requirements

- **No wildcard origins in production** -- explicit allowlist only
- Credentials mode must not be combined with wildcard origins
- All origins must be valid absolute URLs (http:// or https://)
- Preflight cache max-age should be <= 24 hours

### CORS Profiles

| Profile | Origins | Credentials | Methods | Use Case |
|---------|---------|-------------|---------|----------|
| STRICT | Explicit list | Yes | All standard | Production |
| DEVELOPMENT | localhost:3000-3002,8080 | Yes | All standard | Local dev |
| API_ONLY | Wildcard (*) | No | GET, POST, OPTIONS | Public APIs |

### Allowed Methods

```
GET, POST, PUT, DELETE, PATCH, OPTIONS
```

### Allowed Headers

```
Content-Type, Authorization, X-Request-ID, Accept
```

### Exposed Headers

```
X-Request-ID, X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset
```

## Security Audit

The security audit endpoint (`GET /api/v1/security/audit`) runs all checks and returns:

- **Per-check status**: PASS, WARN, or FAIL
- **Domain scores**: Separate scores for TLS, Auth, and CORS (0-100)
- **Overall score**: Weighted average across all domains (0-100)
- **Remediation recommendations**: Prioritized list of improvements

### Scoring

- PASS = full credit
- WARN = half credit
- FAIL = no credit
- Score = (sum of credits / total checks) * 100

### Check Categories

**TLS Checks:**
- Minimum TLS version (>= 1.2)
- Preferred TLS version (1.3)
- HSTS enabled and properly configured
- No weak cipher suites
- Certificate validity and chain

**Auth Checks:**
- Password length (>= 12)
- Password complexity (>= 3 character classes)
- Session idle timeout (<= 60 min)
- Secure cookie flags
- JWT algorithm (asymmetric in production)
- Token lifetimes
- Account lockout enabled
- MFA configuration

**CORS Checks:**
- No wildcard origins in production
- Origins are configured
- No credentials with wildcard
- Preflight max age
- Origin URL format validation

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /security/audit | Full security audit report |
| GET | /security/tls/config | Current TLS configuration |
| GET | /security/tls/profiles | Available TLS profiles |
| GET | /security/auth/config | Current auth configuration |
| GET | /security/auth/policy | Password and session policies |
| GET | /security/cors/config | Current CORS configuration |
| GET | /security/cors/profiles | Available CORS profiles |
| POST | /security/validate-origin | Check if origin is allowed |
| GET | /security/recommendations | Security improvement recommendations |

## Security Baseline Checklist

- [ ] TLS minimum version set to 1.2+
- [ ] TLS 1.3 preferred
- [ ] HSTS enabled with 1-year max-age
- [ ] No weak cipher suites
- [ ] CA-signed certificate in production
- [ ] Password minimum 12 characters
- [ ] 4 character class complexity requirement
- [ ] Session idle timeout <= 30 minutes
- [ ] Secure + HttpOnly cookie flags
- [ ] RS256 JWT in production
- [ ] Access tokens <= 15 minutes
- [ ] Account lockout at 5 attempts
- [ ] MFA required for admins
- [ ] No wildcard CORS origins in production
- [ ] Explicit CORS origin allowlist
- [ ] API keys rotated every 90 days
