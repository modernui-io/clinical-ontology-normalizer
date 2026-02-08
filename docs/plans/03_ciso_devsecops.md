# Deep Implementation Plan: CISO + DevSecOps + VP Engineering (Security)

> Generated: 2026-02-08
> Scope: All items from HARDENING_PLAN.md CISO and DevOps/SRE sections
> Research basis: `docs/research/02_security_hardening_research.md` (22 critical/high gaps, 45 prioritized actions)
> Codebase version: commit 44b6074 (regeneron-trial-demo branch)
> Regulatory context: HIPAA Security Rule 2026 NPRM (all safeguards mandatory), SOC 2, HITRUST CSF r2

---

## Table of Contents

1. [CISO-1: Remove Hardcoded Credentials](#ciso-1-remove-hardcoded-credentials)
2. [CISO-2: Enable TLS Everywhere](#ciso-2-enable-tls-everywhere)
3. [CISO-3: Fix Auth Defaults](#ciso-3-fix-auth-defaults)
4. [CISO-4: Wildcard CORS](#ciso-4-wildcard-cors)
5. [CISO-5: Network Segmentation](#ciso-5-network-segmentation)
6. [CISO-6: Webhook HMAC Verification](#ciso-6-webhook-hmac-verification)
7. [CISO-7: PHI Data Flow Mapping](#ciso-7-phi-data-flow-mapping)
8. [CISO-8: Comprehensive Audit Logging](#ciso-8-comprehensive-audit-logging)
9. [CISO-9: RBAC with Least Privilege](#ciso-9-rbac-with-least-privilege)
10. [CISO-10: Vulnerability Management Program](#ciso-10-vulnerability-management-program)
11. [CISO-11: Incident Response Plan](#ciso-11-incident-response-plan)
12. [CISO-12: SOC 2 Type II Path](#ciso-12-soc-2-type-ii-path)
13. [CISO-13: HITRUST CSF r2 Path](#ciso-13-hitrust-csf-r2-path)
14. [DEVOPS-1: Infrastructure as Code](#devops-1-infrastructure-as-code)
15. [DEVOPS-2: Observability Stack](#devops-2-observability-stack)
16. [DEVOPS-3: Auto-scaling](#devops-3-auto-scaling)
17. [DEVOPS-4: Secret Rotation](#devops-4-secret-rotation)
18. [DEVOPS-5: Cost Monitoring](#devops-5-cost-monitoring)
19. [DEVOPS-6: Container Hardening](#devops-6-container-hardening)
20. [DEVOPS-7: Network Segmentation (Docker)](#devops-7-network-segmentation-docker)
21. [DEVOPS-8: CI/CD Security Scanning](#devops-8-cicd-security-scanning)

---

## CISO-1: Remove Hardcoded Credentials

**Priority**: P0 (Critical) | **Effort**: 4 hours | **Dependencies**: None

### Current State

Hardcoded credentials appear across 5 compose files with 18+ instances:

| Location | Line | Secret | Value |
|----------|------|--------|-------|
| `docker-compose.yml:14` | POSTGRES_PASSWORD | `postgres` |
| `docker-compose.yml:48` | NEO4J_AUTH | `neo4j/password` |
| `docker-compose.yml:119` | DATABASE_URL | contains `postgres:postgres` |
| `docker-compose.yml:123` | NEO4J_PASSWORD | `clinical123` |
| `docker-compose.yml:128` | API_KEY default | `dev-api-key-change-in-production` |
| `docker-compose.yml:165` | Worker DATABASE_URL | contains `postgres:postgres` |
| `docker-compose.yml:169` | Worker NEO4J_PASSWORD | `clinical123` |
| `docker-compose.yml:184` | Migrations DATABASE_URL | contains `postgres:postgres` |
| `docker-compose.fhir.yml:21` | POSTGRES_PASSWORD | `password` |
| `docker-compose.fhir.yml:45` | spring.datasource.password | `password` |
| `docker-compose.fhir.yml:82` | FHIR_SERVER_DISABLE_AUTHORIZATION | `True` |
| `fhir-mcp/docker-compose.yml:9` | spring.datasource.password | `password` |
| `fhir-mcp/docker-compose.yml:28` | POSTGRES_PASSWORD | `password` |
| `fhir-mcp/docker-compose.yml:41` | FHIR_SERVER_DISABLE_AUTHORIZATION | `True` |
| `.env.example:8` | POSTGRES_PASSWORD | `postgres` |
| `.env.example:23` | NEO4J_PASSWORD | `password` |
| `.env.example:43` | API_KEY | `dev-api-key-change-in-production` |
| `backend/app/core/config.py:52` | database_url default | `postgres:postgres` in connection string |
| `k8s/config/secrets.yaml:13-32` | All secrets | `CHANGE_ME` placeholders checked into git |

**NEO4J_PASSWORD mismatch**: docker-compose.yml line 48 sets `NEO4J_AUTH: neo4j/password` but backend env on line 123 uses `NEO4J_PASSWORD: clinical123`. One of these is wrong, meaning either the graph database or the backend fails to connect.

**Redis has NO authentication**: `docker-compose.yml` line 31 runs `redis-server --appendonly yes` with no `--requirepass` flag. Any container on the same Docker network can read/write Redis data (which may contain cached PHI).

**Note**: `docker-compose.prod.yml` already uses `${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}` syntax (lines 28, 91, 161, 169, 195, 199) -- good pattern to replicate in base compose file.

**Note**: `.env` and `backend/.env` are in `.gitignore` (line 40) and NOT tracked by git (verified via `git ls-files --cached`). However, `.env.example` IS tracked and contains working insecure defaults.

### Files to Modify

| File | Action |
|------|--------|
| `docker-compose.yml` | Replace all hardcoded creds with `${VAR:?error}` references |
| `docker-compose.fhir.yml` | Replace hardcoded passwords with env var references |
| `fhir-mcp/docker-compose.yml` | Replace hardcoded passwords with env var references |
| `.env.example` | Replace insecure defaults with placeholder comments |
| `backend/app/core/config.py:52` | Remove password from default database_url |
| `k8s/config/secrets.yaml` | Add comment that this is a TEMPLATE; production must use External Secrets Operator |

### Implementation Steps

**Step 1**: Update `docker-compose.yml` to use environment variable references

For the postgres service (line 12-14):
```yaml
environment:
  POSTGRES_DB: ${POSTGRES_DB:-clinical_ontology}
  POSTGRES_USER: ${POSTGRES_USER:-postgres}
  POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set in .env}
```

For the redis service (line 31):
```yaml
command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD:?REDIS_PASSWORD must be set in .env}
```

For the neo4j service (line 47-48):
```yaml
environment:
  NEO4J_AUTH: ${NEO4J_USER:-neo4j}/${NEO4J_PASSWORD:?NEO4J_PASSWORD must be set in .env}
```

For the backend service (lines 119-128):
```yaml
environment:
  DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD:?required}@postgres:5432/${POSTGRES_DB:-clinical_ontology}
  REDIS_URL: redis://:${REDIS_PASSWORD:?required}@redis:6379
  NEO4J_PASSWORD: ${NEO4J_PASSWORD:?required}
  API_KEY: ${API_KEY:-}
```

Apply the same pattern to worker service (lines 165-169) and migrations service (line 184).

**Step 2**: Update `.env.example` to be a safe template

```bash
# REQUIRED: Set these before running docker compose
# Generate secure values with: scripts/generate_env.sh
POSTGRES_PASSWORD=   # Generate: openssl rand -base64 32
NEO4J_PASSWORD=      # Generate: openssl rand -base64 32
REDIS_PASSWORD=      # Generate: openssl rand -base64 32
API_KEY=             # Generate: openssl rand -hex 32
JWT_SECRET_KEY=      # Generate: openssl rand -base64 64
ETL_ENCRYPTION_KEY=  # Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Optional overrides
POSTGRES_USER=postgres
POSTGRES_DB=clinical_ontology
NEO4J_USER=neo4j

# External API keys (required for respective features)
# ANTHROPIC_API_KEY=
# UMLS_API_KEY=
# METRIPORT_API_KEY=
# METRIPORT_WEBHOOK_KEY=
```

**Step 3**: Update `backend/app/core/config.py` line 52 to remove password from default:

```python
database_url: str = "postgresql+asyncpg://postgres@localhost:5432/clinical_ontology"
```

**Step 4**: Add a `.env` generation script (`scripts/generate_env.sh`)

```bash
#!/bin/bash
# Generate a .env file with secure random credentials
if [ -f .env ]; then
  echo ".env already exists. Remove it first to regenerate."
  exit 1
fi
cp .env.example .env
sed -i '' "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(openssl rand -base64 32)/" .env
sed -i '' "s/^NEO4J_PASSWORD=.*/NEO4J_PASSWORD=$(openssl rand -base64 32)/" .env
sed -i '' "s/^REDIS_PASSWORD=.*/REDIS_PASSWORD=$(openssl rand -base64 32)/" .env
sed -i '' "s/^API_KEY=.*/API_KEY=$(openssl rand -hex 32)/" .env
sed -i '' "s/^JWT_SECRET_KEY=.*/JWT_SECRET_KEY=$(openssl rand -base64 64 | tr -d '\n')/" .env
echo ".env generated with random credentials"
```

**Step 5**: Add pre-commit hook to scan for credential patterns

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
```

### Acceptance Criteria

- [ ] `grep -rn 'postgres:postgres\|neo4j/password\|clinical123\|dev-api-key-change-in-production' docker-compose.yml` returns zero matches
- [ ] `docker compose config` with no `.env` file produces clear error messages about required vars
- [ ] `docker compose config` with valid `.env` file produces valid config with no hardcoded creds
- [ ] `.env` is in `.gitignore` (already confirmed)
- [ ] NEO4J_PASSWORD is consistent between neo4j service and backend service
- [ ] Redis requires authentication (`--requirepass`)
- [ ] `detect-secrets` pre-commit hook blocks commits containing credential patterns
- [ ] `k8s/config/secrets.yaml` has clear TEMPLATE header; no `CHANGE_ME` values pass CI

---

## CISO-2: Enable TLS Everywhere

**Priority**: P0 (Critical) | **Effort**: 8 hours | **Dependencies**: None

### Current State

- `nginx/nginx.conf:59-64`: HTTP-to-HTTPS redirect **commented out**
- `nginx/nginx.conf:69`: Server listens on `listen 80;` only
- `nginx/nginx.conf:69`: `# listen 443 ssl http2;` -- HTTPS is **commented out**
- `nginx/nginx.conf:72-80`: Entire SSL configuration block is **commented out**:
```nginx
# ssl_certificate /etc/nginx/ssl/cert.pem;
# ssl_certificate_key /etc/nginx/ssl/key.pem;
# ssl_session_timeout 1d;
# ssl_session_cache shared:SSL:50m;
# ssl_session_tickets off;
# ssl_protocols TLSv1.2 TLSv1.3;
# ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
# ssl_prefer_server_ciphers off;
```
- No HSTS header configured anywhere in `nginx/nginx.conf`
- No Content-Security-Policy header
- `nginx/ssl/.gitkeep` exists but directory is otherwise empty
- `nginx/nginx.conf:82-86`: Has X-Frame-Options, X-Content-Type-Options, X-XSS-Protection, Referrer-Policy -- but missing HSTS, CSP, Permissions-Policy
- `nginx/nginx.conf`: No `client_max_body_size` limits (default 1MB, but should be explicit)
- `docker-compose.prod.yml:243-244`: Ports 80 and 443 are exposed, but only port 80 is functional
- `docker-compose.prod.yml:247`: `./nginx/ssl:/etc/nginx/ssl:ro` -- volume mount exists but directory is empty

**Internal services -- all plaintext**:
- `docker-compose.yml:119`: `DATABASE_URL: postgresql+asyncpg://postgres:postgres@postgres:5432/` -- no `?sslmode=require`
- `docker-compose.yml:120`: `REDIS_URL: redis://redis:6379` -- no TLS
- `docker-compose.yml:121`: `NEO4J_URI: bolt://con-neo4j:7687` -- `bolt://` is plaintext (`bolt+s://` is TLS)
- `docker-compose.yml:92-93`: Kafka uses `PLAINTEXT://kafka:9092,PLAINTEXT_HOST://localhost:29092`
- `docker-compose.prod.yml:131-132`: Kafka production also uses `PLAINTEXT://kafka:9092`

**Kubernetes** (`k8s/ingress.yaml:11,27-30`): TLS is properly configured with cert-manager and Let's Encrypt. This only covers the k8s deployment path, not Docker Compose.

### Specific Vulnerability

All data in transit -- including PHI, authentication tokens, and API keys -- is transmitted in cleartext. Any network observer on the same segment can read patient data. This violates HIPAA Security Rule 164.312(e)(1) (transmission security) and the 2026 NPRM which makes encryption mandatory (no longer "addressable").

### Files to Modify/Create

| File | Action |
|------|--------|
| `nginx/nginx.conf` | Uncomment TLS config, add HSTS, CSP, Permissions-Policy, client_max_body_size |
| `nginx/ssl/README.md` | Create with cert generation instructions |
| `docker-compose.prod.yml` | Add SSL volume mount, enable postgres SSL params |
| `scripts/generate_dev_certs.sh` | Create self-signed cert generator for local dev |

### Implementation Steps

**Step 1**: Create `scripts/generate_dev_certs.sh`

```bash
#!/bin/bash
CERT_DIR="nginx/ssl"
mkdir -p "$CERT_DIR"
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout "$CERT_DIR/key.pem" \
  -out "$CERT_DIR/cert.pem" \
  -subj "/C=US/ST=Dev/L=Local/O=CON/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,DNS:*.localhost,IP:127.0.0.1"
echo "Dev certs generated in $CERT_DIR/"
echo "WARNING: These are self-signed and for development only."
```

**Step 2**: Update `nginx/nginx.conf` with TLS enabled and security headers

Enable the HTTP-to-HTTPS redirect (lines 59-64), uncomment TLS config (lines 69-80), and add:
```nginx
# HSTS
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

# Content Security Policy
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self' wss:; frame-ancestors 'self';" always;

# Permissions Policy
add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;

# Request body size limits
client_max_body_size 10m;  # 10MB for document uploads

# In the /api/ location block:
client_max_body_size 50m;  # 50MB for FHIR bundle uploads
```

**Step 3**: Enable PostgreSQL SSL connections

In `docker-compose.prod.yml`, add SSL params to postgres command and `?sslmode=require` to DATABASE_URL.

**Step 4**: Enable Redis TLS (Redis 7+ supports native TLS)

Update redis command and REDIS_URL to use `rediss://` (double s).

**Step 5**: Switch Neo4j to TLS

Change `NEO4J_URI` from `bolt://` to `bolt+s://` and configure Neo4j TLS.

### Acceptance Criteria

- [ ] `curl -I http://localhost` returns 301 redirect to HTTPS (prod config)
- [ ] `curl -I https://localhost` returns 200 with `Strict-Transport-Security` header
- [ ] `nmap --script ssl-enum-ciphers -p 443 localhost` shows only TLS 1.2+ with strong ciphers
- [ ] Content-Security-Policy header present on all responses
- [ ] Permissions-Policy header present on all responses
- [ ] `client_max_body_size` set on all location blocks
- [ ] PostgreSQL connections use `sslmode=require` in production
- [ ] Redis connections use TLS in production
- [ ] Dev environment still works on HTTP (separate nginx config or compose override)

---

## CISO-3: Fix Auth Defaults

**Priority**: P0 (Critical) | **Effort**: 4 hours | **Dependencies**: CISO-1

### Current State

**Backend docker-compose defaults** (`docker-compose.yml`):
- Line 125: `DEBUG: ${DEBUG:-true}` -- Debug mode ON by default
- Line 126: `AUTH_BYPASS_DEV: ${AUTH_BYPASS_DEV:-true}` -- Auth bypass ON by default
- Line 127: `AUTH_ENABLED: ${AUTH_ENABLED:-false}` -- Auth DISABLED by default

**Backend config** (`backend/app/core/config.py`):
- Line 49: `debug: bool = False` -- Config default is safe
- Line 102: `auth_enabled: bool = False` -- Auth off by default
- Line 118: `auth_bypass_dev: bool = False` -- Config default is safe, BUT docker-compose overrides it

**Auth bypass effect** (`backend/app/api/middleware/auth_middleware.py:116-135`):
When `auth_bypass_dev=True` AND `debug=True`, a mock admin user with ALL permissions is returned:
```python
if settings.auth_bypass_dev and settings.debug:
    return CurrentUser(
        id="dev-admin-user",
        email="dev@local.test",
        roles=["admin"],
        permissions=[
            "documents:read", "documents:write", "documents:delete", "documents:admin",
            "patients:read", "patients:write", "patients:delete", "patients:admin",
            "billing:read", "billing:write", "billing:delete", "billing:admin",
            "coding:read", "coding:write", "coding:delete", "coding:admin",
            "audit:read", "audit:write", "audit:export", "audit:admin",
            "admin:read", "admin:write", "admin:manage_users", "admin:manage_roles",
            # ... ALL permissions granted ...
        ],
    )
```

**Tenant context stub** (`backend/app/core/security.py:220-231`):
```python
def get_tenant_context() -> TenantContext:
    # For now, return unrestricted context (dev mode)
    return TenantContext(tenant_id=None)
```
`TenantContext(tenant_id=None)` means `is_authorized_for()` returns `True` for ALL patients -- no patient data isolation.

**Frontend auth bypass** (`frontend/.env.local:2`):
```
NEXT_PUBLIC_AUTH_BYPASS=true
```

**Frontend middleware** (`frontend/src/middleware.ts:48-50`):
```typescript
if (process.env.NEXT_PUBLIC_AUTH_BYPASS === "true") {
    return NextResponse.next();
}
```
When `NEXT_PUBLIC_AUTH_BYPASS=true`, ALL frontend route protection is bypassed.

**Frontend Dockerfile** (`frontend/Dockerfile:17-18`):
```dockerfile
ARG NEXT_PUBLIC_AUTH_BYPASS=false
ENV NEXT_PUBLIC_AUTH_BYPASS=${NEXT_PUBLIC_AUTH_BYPASS}
```
Build-time default is `false` (good), but `frontend/.env.local` overrides it locally.

**Root .env file** (`.env:6-7`, not tracked in git):
```
AUTH_BYPASS_DEV=true
JWT_SECRET_KEY=u1jHVsDjJQFNBZKrKxFaF2TNI8ALuexM6VgVkvycpRo
```
Static JWT secret in local .env -- acceptable for dev but must never reach production.

### Specific Vulnerability

The default configuration of `docker-compose.yml` results in a system where:
1. Authentication is completely disabled (`AUTH_ENABLED=false`)
2. Even if enabled, it is bypassed (`AUTH_BYPASS_DEV=true`)
3. The bypass grants full admin permissions to all requests
4. Patient data isolation is non-functional (tenant context always unrestricted)
5. Frontend skips all route protection (`NEXT_PUBLIC_AUTH_BYPASS=true`)

If this configuration reaches any non-local environment, all 726 endpoints are publicly accessible without authentication.

### Files to Modify

| File | Action |
|------|--------|
| `docker-compose.yml:125-128` | Change defaults to secure values |
| `docker-compose.dev.yml` | Add dev-mode overrides here instead |
| `backend/app/core/config.py` | Add startup validation for production |
| `backend/app/api/middleware/auth_middleware.py:116` | Add environment guard |
| `backend/app/core/security.py:220-231` | Wire tenant context to JWT claims |
| `frontend/.env.local` | Change auth bypass to false |
| `frontend/Dockerfile:17` | Ensure default is false (already is) |

### Implementation Steps

**Step 1**: Change `docker-compose.yml` defaults (lines 125-128):
```yaml
DEBUG: ${DEBUG:-false}                     # was: ${DEBUG:-true}
AUTH_BYPASS_DEV: ${AUTH_BYPASS_DEV:-false}  # was: ${AUTH_BYPASS_DEV:-true}
AUTH_ENABLED: ${AUTH_ENABLED:-false}        # keep: dev doesn't need auth
API_KEY: ${API_KEY:-}                       # remove insecure default
```

**Step 2**: Move dev-mode overrides to `docker-compose.dev.yml`:
```yaml
services:
  backend:
    environment:
      DEBUG: "true"
      AUTH_BYPASS_DEV: "true"
```

**Step 3**: Add environment guard in `auth_middleware.py` after line 116:
```python
if settings.auth_bypass_dev and settings.debug:
    if settings.environment.lower() in ("production", "staging"):
        logger.critical(
            "SECURITY: auth_bypass_dev=true in %s. Auth bypass DISABLED.",
            settings.environment,
        )
    else:
        logger.warning("Auth bypass enabled - returning dev admin user")
        return CurrentUser(...)
```

**Step 4**: Add startup validation in `config.py` model_validator:
```python
if is_production and self.auth_bypass_dev:
    raise ValueError("AUTH_BYPASS_DEV must be False in production.")
if is_production and self.debug:
    raise ValueError("DEBUG must be False in production.")
```

**Step 5**: Wire tenant context in `security.py` to extract tenant_id from JWT claims.

**Step 6**: Change `frontend/.env.local` to `NEXT_PUBLIC_AUTH_BYPASS=false`.

### Acceptance Criteria

- [ ] `docker compose config | grep AUTH_BYPASS_DEV` shows `false` (without .env overrides)
- [ ] `docker compose config | grep -w DEBUG` shows `false` (without .env overrides)
- [ ] `docker compose -f docker-compose.yml -f docker-compose.dev.yml config | grep AUTH_BYPASS_DEV` shows `true`
- [ ] `docker compose -f docker-compose.yml -f docker-compose.prod.yml config | grep AUTH_ENABLED` shows `true`
- [ ] `AUTH_BYPASS_DEV=true` in production causes startup failure
- [ ] `DEBUG=true` in production causes startup failure
- [ ] Frontend auth bypass only active when explicitly enabled via build arg
- [ ] Tenant context extracts scope from JWT in production

---

## CISO-4: Wildcard CORS

**Priority**: P0 (Critical) | **Effort**: 2 hours | **Dependencies**: None

### Current State

Two CORS configurations exist -- one correct, one insecure:

1. **FastAPI CORS middleware** (`backend/app/main.py:615-637`): Uses `settings.cors_origins_list` which parses from `CORS_ORIGINS` env var. Validates absolute URLs, no wildcards. **Correct.**

2. **nginx CORS headers** (`nginx/nginx.conf:113-115`):
```nginx
add_header 'Access-Control-Allow-Origin' '*' always;
add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS' always;
add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization' always;
```
This is in the `/api/` location block (lines 96-116). **Wildcard CORS at nginx layer.**

The nginx wildcard CORS renders the FastAPI CORSMiddleware entirely useless because nginx adds `Access-Control-Allow-Origin: *` to EVERY API response, and browsers will use the most permissive value. This also creates duplicate CORS headers.

The `nginx/nginx.conf:118-127` WebSocket location block at `/api/ws` has no origin validation at all.

### Files to Modify

| File | Action |
|------|--------|
| `nginx/nginx.conf:113-115` | Remove CORS headers (let FastAPI handle it) |

### Implementation Steps

**Option A (recommended)**: Remove CORS from nginx entirely and let FastAPI handle it:

Delete lines 112-115 from the `/api/` location block in `nginx/nginx.conf`:
```nginx
# DELETE these lines:
add_header 'Access-Control-Allow-Origin' '*' always;
add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS' always;
add_header 'Access-Control-Allow-Headers' 'DNT,...' always;
```

The FastAPI CORSMiddleware (already properly configured in `main.py:625-637`) will handle all CORS headers with the origin allowlist from `settings.cors_origins_list`.

**Option B**: If nginx must handle CORS, use a map directive:
```nginx
map $http_origin $cors_origin {
    default "";
    "http://localhost:3000"  $http_origin;
    "https://app.example.com" $http_origin;
}
```

**Also**: Add origin validation for the WebSocket endpoint at line 119-127.

### Acceptance Criteria

- [ ] `curl -H "Origin: https://evil.com" -I http://localhost/api/v1/health` does NOT return `Access-Control-Allow-Origin: *`
- [ ] `curl -H "Origin: http://localhost:3000" -I http://localhost/api/v1/health` returns `Access-Control-Allow-Origin: http://localhost:3000`
- [ ] No duplicate CORS headers in responses
- [ ] WebSocket endpoint validates Origin header
- [ ] Preflight OPTIONS requests return proper CORS headers from FastAPI

---

## CISO-5: Network Segmentation

**Priority**: P0 (High) | **Effort**: 4 hours | **Dependencies**: None

### Current State

**`docker-compose.yml`**: No `networks:` section at all. All 7 services share the default Docker bridge network. Every container can reach every other container.

Host-exposed ports:
| Service | Host Port | Risk |
|---------|-----------|------|
| PostgreSQL | 15432 (line 16) | Direct DB access from host |
| Redis | 16379 (line 33) | Direct cache access from host (no auth!) |
| Neo4j Browser | 7474 (line 51) | Web console exposed |
| Neo4j Bolt | 7687 (line 52) | Direct graph DB access |
| Kafka | 9092, 29092 (lines 100-101) | Message broker exposed |
| Zookeeper | 2181 (line 71) | Coordination exposed |
| Backend | 8080 (line 140) | API exposed |
| Frontend | 3000 (line 203) | UI exposed |

**`docker-compose.prod.yml`**: Also has **no** `networks:` section. Despite being the "production" configuration, all services still share the default network. Ports are inherited from base compose.

**`docker-compose.fhir.yml`**: Has proper network isolation (lines 88-90):
```yaml
networks:
  fhir-network:
    name: fhir-network
```
This is the only compose file with network segmentation -- and it's for the separate FHIR stack.

**Kubernetes** (`k8s/network-policies.yaml`): Has comprehensive NetworkPolicies:
- Default deny-all (lines 1-13) -- excellent
- DNS egress allowed for all pods (lines 14-34)
- Backend: ingress from ingress-nginx and frontend only, egress to postgres/redis and external HTTPS only (lines 35-105)
- Frontend: ingress from ingress-nginx only, egress to backend only (lines 106-141)
- Postgres: ingress from backend only, no egress (lines 142-169)
- Redis: ingress from backend only, no egress (lines 170-197)

The k8s network policies are well-designed, but the Docker Compose topology (used for dev and potentially staging) has zero segmentation.

### Implementation Steps

**Step 1**: Add network definitions to `docker-compose.yml`:
```yaml
networks:
  frontend-net:
    driver: bridge
  backend-net:
    driver: bridge
  data-net:
    driver: bridge
    internal: true    # No external access
  queue-net:
    driver: bridge
    internal: true    # No external access
```

**Step 2**: Assign services to networks (see Implementation Sequence below).

**Step 3**: Remove host port mappings in `docker-compose.prod.yml` for data services.

**Step 4**: Keep host ports in `docker-compose.dev.yml` for developer convenience.

Service-to-network mapping:
- **postgres**: data-net only
- **redis**: data-net + queue-net
- **neo4j**: data-net only
- **zookeeper**: queue-net only
- **kafka**: queue-net only
- **backend**: backend-net + data-net + queue-net
- **worker**: data-net + queue-net
- **frontend**: frontend-net + backend-net (for SSR)
- **nginx** (prod only): frontend-net + backend-net

### Acceptance Criteria

- [ ] Frontend container cannot connect to postgres, redis, neo4j, kafka directly
- [ ] Backend container can connect to all data stores and queue services
- [ ] No database/broker ports exposed to host in production compose
- [ ] Only nginx ports 80/443 externally accessible in production
- [ ] All services function correctly with segmented networks
- [ ] Dev compose override re-exposes ports for local development

---

## CISO-6: Webhook HMAC Verification

**Priority**: P0 (High) | **Effort**: 6 hours | **Dependencies**: CISO-1

### Current State

**Already implemented** in `backend/app/api/metriport_webhook.py:252-279`:

```python
def _verify_webhook_signature(payload_body, signature, webhook_key):
    if not webhook_key:
        return True  # No key configured -- skip verification (dev mode)
    if not signature:
        return False
    expected = hmac.new(webhook_key.encode(), payload_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)  # Constant-time comparison -- good
```

Called at lines 329-336:
```python
webhook_key = settings.metriport_webhook_key
if webhook_key and not _verify_webhook_signature(body, x_metriport_signature, webhook_key):
    raise HTTPException(status_code=401, ...)
```

**Issues**:
1. **Line 331**: `if webhook_key and ...` -- when `webhook_key` is None/empty, verification is **silently skipped**. No warning logged. An attacker can send forged webhooks.
2. **`backend/app/core/config.py:156`**: `metriport_webhook_key: str | None = None` -- defaults to None, no production validation.
3. **No timestamp validation**: Replay attacks possible. Attacker captures valid webhook and replays it.
4. **No IP allowlisting**: No filtering for Metriport's egress IPs.
5. **In-memory dedup** (`metriport_webhook.py:41`): `_processed_message_ids: set[str]` -- lost on restart, not shared across workers. Lines 291-298 show eviction at 10K entries with FIFO eviction (arbitrary eviction of `list(_processed_message_ids)[:5000]`).

### Implementation Steps

**Step 1**: Make webhook key required in production (add to `config.py` model_validator):
```python
if is_production and not self.metriport_webhook_key:
    raise ValueError("METRIPORT_WEBHOOK_KEY is required in production.")
```

**Step 2**: Log warning when key is not configured, reject in production:
```python
webhook_key = settings.metriport_webhook_key
if settings.is_production and not webhook_key:
    raise HTTPException(status_code=503, detail="Webhook verification not configured")
if webhook_key:
    if not _verify_webhook_signature(body, x_metriport_signature, webhook_key):
        raise HTTPException(status_code=401, detail="Invalid signature")
else:
    logger.warning("Webhook key not configured - signature verification SKIPPED")
```

**Step 3**: Add timestamp validation (reject payloads older than 5 minutes).

**Step 4**: Move dedup to Redis with TTL-based expiry for persistence across restarts.

**Step 5**: Add webhook-specific rate limiting in nginx.

### Acceptance Criteria

- [ ] Webhook without valid signature returns 401 when key is configured
- [ ] Missing webhook key in production causes startup failure
- [ ] Webhook payloads older than 5 minutes are rejected
- [ ] Duplicate message IDs rejected (persisted via Redis)
- [ ] Dev mode accepts unsigned webhooks with warning log

---

## CISO-7: PHI Data Flow Mapping

**Priority**: P1 (Compliance) | **Effort**: 5 days | **Dependencies**: None

### Current State

No formal PHI data flow documentation exists. Based on codebase analysis, PHI flows through:

```
1. INGRESS: Metriport webhook -> backend/app/api/metriport_webhook.py
   PHI: Patient names, DOB, MRN, addresses, phone, SSN, clinical notes, labs, meds, diagnoses

2. FHIR IMPORT: backend/app/services/fhir_import.py
   PHI stored: PostgreSQL (patients, conditions, observations, medications, procedures, etc.)

3. NLP EXTRACTION: backend/app/services/nlp_*.py (6+ NLP service variants)
   PHI in memory during processing. Extracted mentions stored in PostgreSQL.

4. OMOP MAPPING: backend/app/services/mapping*.py
   Clinical facts created with patient linkage in PostgreSQL.

5. KNOWLEDGE GRAPH: backend/app/services/graph_builder*.py
   Patient nodes + clinical relationships stored in Neo4j.

6. TRIAL MATCHING: backend/app/services/trial_eligibility_service.py
   Patient data compared against criteria. Results include patient identifiers.

7. CACHING: Redis
   May contain cached patient data, session state. No encryption.

8. API RESPONSES: 726+ endpoints
   Patient data returned to frontend, displayed in browser.

9. EXPORTS: backend/app/api/export*.py
   Full PHI in FHIR/OMOP/CSV export files.

10. AUDIT LOGS: backend/app/services/audit_service.py
    Patient IDs and resource IDs in audit trail (PostgreSQL).

11. APPLICATION LOGS: stdout/stderr
    Potential PHI leakage in error messages and debug logging.
```

**Data stores containing PHI**:
| Store | PHI Content | Encryption at Rest | Access Control |
|-------|------------|-------------------|----------------|
| PostgreSQL | Full patient records, clinical notes, labs | None | Single shared user (`postgres`) |
| Neo4j | Patient knowledge graph with identifiers | None | Weak password (`clinical123`/`password` mismatch) |
| Redis | Cached responses, job queue data | None | No authentication at all |
| Log files | Patient IDs in audit/error logs | None | File system only |
| Export files | Full PHI in FHIR/OMOP/CSV | None | File system only |

### Implementation Steps

1. Audit all database models in `backend/app/models/` for PHI fields.
2. Map PHI through each processing stage with data flow diagram.
3. Search codebase for PHI in log output.
4. Document all external systems that receive PHI.
5. Create machine-readable PHI inventory CSV.

### Acceptance Criteria

- [ ] Complete PHI inventory with every table/field containing PHI
- [ ] Data flow diagram showing PHI movement through all stages
- [ ] Log audit confirming no PHI in application logs
- [ ] All external PHI recipients documented
- [ ] Minimum necessary principle documented per endpoint

---

## CISO-8: Comprehensive Audit Logging

**Priority**: P1 (HIPAA) | **Effort**: 3 days | **Dependencies**: None

### Current State

**Partially implemented** (`backend/app/services/audit_service.py`, 973 lines):
- PHI detection patterns (SSN, MRN, phone, email, DOB, patient name, address, insurance ID) at lines 56-84
- `log_event()`, `log_access()`, `log_create()`, `log_update()`, `log_delete()`, `log_export()`, `log_search()` methods
- Query interface with filters (lines 573-641)
- HIPAA-format export (lines 854-908)
- Auto-detection of PHI access by resource type, API path, and content scanning
- AuditMiddleware registered in `backend/app/main.py:600`

**Gaps**:
1. **Not immutable**: Audit logs stored in same PostgreSQL with same user. Application user can DELETE audit records.
2. **No external log shipping**: No SIEM integration.
3. **No 6-year retention enforcement**: No archival or retention policy.
4. **No anomaly alerting**: No detection of bulk PHI access, after-hours access, or brute force.
5. **In-memory counter** (`audit_service.py:303`): `self._log_count += 1` -- not meaningful across restarts/workers.
6. **Missing instrumentation**: NLP processing, graph queries, and internal service calls may not be logged.
7. **pgaudit not enabled**: No database-level query auditing.

### Implementation Steps

1. **Enable pgaudit** in PostgreSQL (shared_preload_libraries).
2. **Add tamper-evidence**: Chain hash linking each audit entry to previous.
3. **Separate audit DB user**: Revoke DELETE/UPDATE on audit tables from app user.
4. **Add SIEM export**: Structured log output for Splunk/Elastic/cloud-native.
5. **Add anomaly alerting**: Bulk access, after-hours, brute force detection.
6. **Instrument missing paths**: NLP processing, graph queries, service-level operations.
7. **Set 6-year retention** with automated archival.

### Acceptance Criteria

- [ ] Audit logs cannot be deleted by application database user
- [ ] Chain hash provides tamper detection
- [ ] pgaudit captures DDL and write operations
- [ ] All PHI access paths instrumented
- [ ] Anomaly alerting fires within 5 minutes
- [ ] HIPAA-format export available
- [ ] 6-year retention configured

---

## CISO-9: RBAC with Least Privilege

**Priority**: P1 (High) | **Effort**: 2-3 weeks | **Dependencies**: CISO-3

### Current State

**Significant RBAC infrastructure exists** (`backend/app/api/middleware/auth_middleware.py`, 559 lines):
- `CurrentUser` dataclass with `has_role()`, `has_permission()`, `is_admin()` (lines 49-72)
- `require_permission()` decorator (lines 249-293)
- `require_role()` decorator (lines 296-337)
- `require_any_role()`, `require_any_permission()` decorators
- `PermissionChecker` class for dependency injection (lines 430-478)
- `RoleChecker` class (lines 481-520)
- Convenience functions: `require_documents_read`, `require_documents_write`, `require_patients_read`, `require_admin`

**RBAC service** exists at `backend/app/services/rbac_service.py` with database-backed roles/permissions.

**Gaps**:
1. **Not applied to most endpoints**: RBAC decorators exist but need to be applied to all 726 endpoints. Many use binary API key auth.
2. **No endpoint inventory**: No mapping of endpoints to required permissions.
3. **Auth bypass grants ALL permissions** (lines 118-135): Makes permission testing impossible in dev.
4. **`/docs` and `/redoc` are public** (`security.py:79-80`): OpenAPI docs expose full API surface.
5. **No row-level security**: `TenantContext` stub at `security.py:220-231` always returns unrestricted.
6. **Scaffold endpoints accessible**: No maturity-tier gating to block Scaffold endpoints in production.

### Implementation Steps

1. **Inventory all 726 endpoints** with current auth status.
2. **Define permission matrix**: resource x action x role.
3. **Apply `PermissionChecker` dependencies** to all endpoint routers.
4. **Define predefined roles**: clinical_coordinator, data_analyst, system_admin, api_integration, viewer.
5. **Disable OpenAPI docs in production**: `docs_url=None, redoc_url=None, openapi_url=None` when `is_production`.
6. **Wire tenant context**: Extract scope from JWT claims for patient data isolation.
7. **Add maturity-tier gating**: Block Scaffold endpoints when `environment=production`.

### Acceptance Criteria

- [ ] Every endpoint has documented required permission
- [ ] All PHI-accessing endpoints require authentication
- [ ] Permission checks enforced on all CRUD operations
- [ ] Admin-only endpoints restricted to admin role
- [ ] OpenAPI docs disabled in production
- [ ] Tenant context restricts data access per user scope
- [ ] Scaffold endpoints blocked in production

---

## CISO-10: Vulnerability Management Program

**Priority**: P1 (Ongoing) | **Effort**: 2 days setup + ongoing | **Dependencies**: None

### Current State

- **No CI/CD pipeline exists** in the repository. No `.github/workflows/`, no `.gitlab-ci.yml`, no `Jenkinsfile`.
- **No SAST** (Bandit, Semgrep)
- **No dependency scanning** (pip-audit, npm audit automated)
- **No container scanning** (Trivy, Grype)
- **No secret scanning** (detect-secrets, trufflehog)
- **No DAST** (OWASP ZAP)
- `CLAUDE.md` mentions `make test`, `make lint`, `make typecheck` -- local commands only, not CI-enforced

### Implementation Steps

1. **Create `.github/workflows/security.yml`**: SAST (Bandit + Semgrep), dependency scan (pip-audit + npm audit), container scan (Trivy), secret scan (trufflehog).
2. **Create `.pre-commit-config.yaml`**: bandit, detect-secrets, ruff hooks.
3. **Create `.github/dependabot.yml`**: Automated dependency updates for pip, npm, docker.
4. **Add security Makefile targets**: `make security-scan`, `make security-sast`, `make security-deps`, `make security-containers`.

### Acceptance Criteria

- [ ] Every PR triggers SAST, dependency scan, and secret scan
- [ ] PR cannot merge with HIGH/CRITICAL findings (CI blocks)
- [ ] Container images scanned before deployment
- [ ] Dependency update PRs created automatically (weekly)
- [ ] Pre-commit hooks catch secrets before commit

---

## CISO-11: Incident Response Plan

**Priority**: P2 (Compliance) | **Effort**: 1-2 weeks | **Dependencies**: CISO-8

### Current State

No incident response plan exists. `docs/HARDENING_PLAN.md` line 154 references the need.

### Implementation Steps

Create `docs/security/incident_response_plan.md` with:
1. **Roles and responsibilities**: Incident Commander, Technical Lead, Communications Lead, Legal
2. **Classification**: P1 (active PHI breach), P2 (suspected exposure), P3 (vulnerability), P4 (policy violation)
3. **Response procedures**: Detection, Containment, Eradication, Recovery, Post-Incident
4. **HIPAA notification**: 24-hour HHS notification (2026 NPRM), 60-day individual notification
5. **Technical runbooks**: Credential revocation, service isolation, evidence preservation
6. **Communication templates**: Pre-drafted notifications for patients, regulators, media
7. **Testing schedule**: Quarterly tabletop exercises, annual full simulation

### Acceptance Criteria

- [ ] IRP documented and approved
- [ ] Notification templates ready for P1 incidents
- [ ] Contact list for HHS, state AGs, patients
- [ ] Technical runbooks for top 5 scenarios
- [ ] First tabletop exercise scheduled within 90 days

---

## CISO-12: SOC 2 Type II Path

**Priority**: P3 | **Effort**: 6-12 months | **Dependencies**: CISO-1 through CISO-11

### Current State vs. SOC 2 Trust Services Criteria

| TSC | Control Area | Status | Gap |
|-----|-------------|--------|-----|
| CC1 | Control Environment | No formal policies | Need InfoSec Policy, Acceptable Use, Data Classification |
| CC2 | Communication | No security training | Need annual training, onboarding checklist |
| CC3 | Risk Assessment | Research doc exists but not formal | Need annual assessment with methodology |
| CC4 | Monitoring | k8s Prometheus rules but no SIEM | Need centralized monitoring + alerting |
| CC5 | Control Activities | Auth/RBAC exists but unenforced | Need RBAC enforcement, change management |
| CC6 | Logical Access | API key + JWT framework exists | Need MFA, session management, access review |
| CC7 | System Operations | Health checks exist | Need IR plan, backup testing, DR plan |
| CC8 | Change Management | Git-based, no formal approval | Need formal change control for clinical paths |
| CC9 | Risk Mitigation | SSRF prevention, rate limiting exist | Need vendor risk management, BAA framework |
| A1 | Availability | k8s HPA + resource limits exist | Need SLAs, DR testing, capacity planning |
| PI1 | Processing Integrity | Pydantic validation, NLP pipeline | Need data quality monitoring |
| C1 | Confidentiality | No encryption at rest | Need encryption at rest, data classification |
| P1 | Privacy | Audit logging, FHIR consent model | Need privacy notice, consent management |

### Implementation Steps

1. **Gap analysis** (2-4 weeks): Assess against Trust Services Criteria
2. **Remediation** (3-6 months): Address P0-P2 items
3. **Evidence collection** (ongoing): Audit logs, access reviews, change records
4. **Audit engagement** (3-6 months): Type I then Type II
5. **Budget**: $20K-$100K

### Acceptance Criteria

- [ ] Gap analysis complete with remediation plan
- [ ] All P0 and P1 items resolved
- [ ] SOC 2 Type I report issued
- [ ] 6-month observation period begins

---

## CISO-13: HITRUST CSF r2 Path

**Priority**: P3 | **Effort**: 12-18 months | **Dependencies**: CISO-12

### Implementation Steps

1. Complete SOC 2 first (builds foundation)
2. Scope HITRUST assessment (200-800 controls)
3. Select Authorized HITRUST External Assessor
4. Complete self-assessment + validated assessment
5. **Budget**: $60K-$200K

### Acceptance Criteria

- [ ] HITRUST scope defined
- [ ] Assessor selected and engaged
- [ ] Self-assessment complete
- [ ] Remediation plan for failed controls

---

## DEVOPS-1: Infrastructure as Code

**Priority**: P2 | **Effort**: 2-3 weeks | **Dependencies**: None

### Current State

**Docker Compose** (5 files):
| File | Status |
|------|--------|
| `docker-compose.yml` | Base config, insecure defaults, no networks |
| `docker-compose.dev.yml` | Minimal (hot reload, 32 lines) |
| `docker-compose.prod.yml` | Good: required env vars, resource limits, replicas, multi-stage builds |
| `docker-compose.fhir.yml` | Standalone FHIR stack with network isolation |
| `fhir-mcp/docker-compose.yml` | Standalone FHIR MCP server |

**Kubernetes** (`k8s/`, 28 files): Well-structured with:
- Kustomize base + overlays (dev/staging/prod)
- NetworkPolicies (default-deny + per-service)
- RBAC (ServiceAccounts, Roles, RoleBindings)
- HPA, PDB, monitoring (ServiceMonitor, PrometheusRules, Grafana dashboard)
- Secrets and ConfigMaps
- Backend deployment: securityContext with `runAsNonRoot`, `readOnlyRootFilesystem`, capability drops

**Gaps**:
1. **No Terraform/Pulumi**: Cloud infra not codified
2. **k8s secrets.yaml** has `CHANGE_ME` placeholders checked into git
3. **No GitOps** (ArgoCD/Flux)
4. **Mutable image tags**: `backend/deployment.yaml:39` uses `image: clinical-ontology/backend:latest`
5. **k8s overlays incomplete**: `overlays/prod/kustomization.yaml` uses `newTag: v1.0.0` but no CI builds this

### Implementation Steps

1. **Add Terraform** for cloud infra (VPC, EKS/GKE, RDS, ElastiCache, S3, IAM, KMS)
2. **Replace k8s secrets.yaml** with External Secrets Operator
3. **Pin image digests** in all k8s deployments
4. **Implement GitOps** via ArgoCD
5. **Connect CI/CD** to build and tag images

### Acceptance Criteria

- [ ] All infrastructure reproducible from code
- [ ] No secrets in git-tracked files
- [ ] Images referenced by digest
- [ ] Deployments triggered by git merge

---

## DEVOPS-2: Observability Stack

**Priority**: P1 | **Effort**: 1-2 weeks | **Dependencies**: None

### Current State

- `backend/app/main.py:603`: MetricsMiddleware registered (Prometheus metrics)
- `backend/app/main.py:597`: RequestIdMiddleware adds X-Request-ID
- `k8s/monitoring/`: ServiceMonitor, PrometheusRules (error rate, latency, pod health, PG connections, Redis memory), Grafana dashboard ConfigMap
- `k8s/backend/deployment.yaml:29-30`: Prometheus scrape annotations configured

**Gaps**:
1. **No Prometheus/Grafana in Docker Compose**: Monitoring only exists in k8s path
2. **No distributed tracing**: No Jaeger/OpenTelemetry
3. **No log aggregation**: Each container logs independently
4. **No NLP/pipeline metrics**: Processing time, accuracy, mapping rates not tracked
5. **No AlertManager**: Prometheus rules exist but no notification routing

### Implementation Steps

1. Create `docker-compose.observability.yml` with Prometheus + Grafana + Loki
2. Add OpenTelemetry instrumentation to FastAPI
3. Create domain dashboards: pipeline health, security events, SLAs
4. Configure AlertManager with PagerDuty/Slack
5. Implement structured JSON logging

### Acceptance Criteria

- [ ] Prometheus scrapes all services
- [ ] Grafana dashboards show pipeline health, security events, infrastructure
- [ ] Alerts fire to PagerDuty/Slack for critical conditions
- [ ] Logs searchable via Loki/Grafana

---

## DEVOPS-3: Auto-scaling

**Priority**: P2 | **Effort**: 1-2 weeks | **Dependencies**: DEVOPS-1, DEVOPS-2

### Current State

- `docker-compose.prod.yml:159`: Backend `replicas: 2`, Worker `replicas: 2`
- `k8s/backend/hpa.yaml`: HPA exists
- `k8s/overlays/prod/kustomization.yaml:30-37`: Prod HPA: minReplicas=3, maxReplicas=15
- No queue-based scaling for workers

### Implementation Steps

1. For k8s: Configure KEDA ScaledObject for workers (Redis queue depth)
2. Define scale-down grace period for in-flight requests
3. Add scaling event alerting

### Acceptance Criteria

- [ ] Backend scales 2-15 replicas based on CPU
- [ ] Workers scale based on queue depth
- [ ] Scale-down is graceful

---

## DEVOPS-4: Secret Rotation

**Priority**: P2 | **Effort**: 2 days (scripts) to 2 weeks (Vault) | **Dependencies**: CISO-1

### Current State

| Secret | Current Location | Rotation | Risk |
|--------|-----------------|----------|------|
| PostgreSQL password | `.env` / docker-compose | Never | CRITICAL |
| Neo4j password | `.env` / docker-compose | Never | HIGH |
| Redis password | Not configured | N/A | HIGH |
| API key | `.env` / docker-compose | Never | HIGH |
| JWT secret key | `.env` (static value) | Never | CRITICAL |
| ETL encryption key | `config.py:163`: None default | New key per restart! | HIGH |
| Metriport webhook key | `.env` (when configured) | Manual | HIGH |
| Anthropic API key | `.env` | Manual | MEDIUM |
| UMLS API key | `.env` | Manual | MEDIUM |

**Critical bug**: `backend/app/core/config.py:162-163`:
```python
# IMPORTANT: Set this in production - otherwise each restart generates new key
etl_encryption_key: str | None = None
```
If ETL encryption key is not set, each restart generates a new key, making previously encrypted data unrecoverable.

### Implementation Steps

1. **Immediate**: Make ETL encryption key required in production (add to model_validator).
2. **Short-term**: Script-based rotation with `scripts/rotate_secrets.sh`.
3. **Medium-term**: HashiCorp Vault with dynamic database credentials.
4. **Policy**: No secret lifetime > 90 days.

### Acceptance Criteria

- [ ] All secrets have documented rotation schedule
- [ ] ETL encryption key is required and persistent in production
- [ ] Rotation script exists and tested
- [ ] Secret age monitoring in place

---

## DEVOPS-5: Cost Monitoring

**Priority**: P3 | **Effort**: 1-2 days | **Dependencies**: DEVOPS-2

### Implementation Steps

1. Add resource labels for cost attribution
2. Track per-service resource usage in Grafana
3. Document cost-per-patient model
4. Alert on >2x normal consumption

### Acceptance Criteria

- [ ] Per-service resource dashboards
- [ ] Cost model documented
- [ ] Spend anomaly alerting

---

## DEVOPS-6: Container Hardening

**Priority**: P1 | **Effort**: 1 day | **Dependencies**: None

### Current State

| File | Non-root User | Multi-stage | Read-only FS | Cap Drops | Image Pinning |
|------|:------------:|:-----------:|:------------:|:---------:|:-------------:|
| `backend/Dockerfile` (dev) | Yes (L25-27) | No | No | No | Tag only |
| `backend/Dockerfile.prod` | Yes (L51-55) | Yes (L7,29) | No | No | Tag only |
| `frontend/Dockerfile` (dev) | **No** | No | No | No | Tag only |
| `frontend/Dockerfile.prod` | Yes (L55-56) | Yes (3-stage) | No | No | Tag only |
| `fhir-mcp/Dockerfile` | Yes (L47-48) | Yes (L17,31) | No | No | Tag only |

**`backend/Dockerfile:1`**: Uses `python:3.11-slim` but `CLAUDE.md` says Python 3.13.

**`frontend/Dockerfile:1`**: `FROM node:20-alpine` -- **runs as root** (no USER directive).

**k8s backend deployment** (`k8s/backend/deployment.yaml:112-117`): Has excellent container security:
```yaml
securityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities:
    drop: [ALL]
```
But this only applies to k8s, not Docker Compose.

### Implementation Steps

1. **Add non-root user to `frontend/Dockerfile`**.
2. **Add security directives to `docker-compose.prod.yml`** for each service:
```yaml
security_opt: ["no-new-privileges:true"]
cap_drop: [ALL]
read_only: true
tmpfs: ["/tmp:size=100M"]
```
3. **Pin base images by digest** in all Dockerfiles.
4. **Update Python version** from 3.11-slim to 3.13-slim.
5. **Scan images with Trivy** in CI.

### Acceptance Criteria

- [ ] All containers run as non-root
- [ ] `no-new-privileges` set on all production containers
- [ ] All unnecessary capabilities dropped
- [ ] Read-only root filesystem where possible
- [ ] Base images pinned by digest
- [ ] Trivy scan shows zero CRITICAL CVEs

---

## DEVOPS-7: Network Segmentation (Docker)

**Priority**: P0 | **Effort**: 4 hours | **Dependencies**: None

> Same as CISO-5. See [CISO-5: Network Segmentation](#ciso-5-network-segmentation) for details.

---

## DEVOPS-8: CI/CD Security Scanning

**Priority**: P1 | **Effort**: 2 days | **Dependencies**: None

### Current State

**No CI/CD configuration exists in the repository.** No `.github/workflows/`, no `.gitlab-ci.yml`, no `Jenkinsfile`, no `Makefile` with security targets.

### Implementation Steps

1. **Create `.github/workflows/security.yml`**:
   - SAST: Bandit (Python), Semgrep (OWASP rules)
   - Dependency scan: pip-audit, npm audit
   - Container scan: Trivy
   - Secret scan: trufflehog
   - DAST: OWASP ZAP (staging only, on main branch)

2. **Create `.pre-commit-config.yaml`**:
   - bandit (Python SAST)
   - detect-secrets (credential scanning)
   - ruff (linting)

3. **Create `.github/dependabot.yml`**:
   - pip ecosystem (backend/)
   - npm ecosystem (frontend/)
   - docker ecosystem (all Dockerfiles)

4. **Add Makefile security targets**:
   - `make security-scan`: Run all scans locally
   - `make security-sast`: Bandit only
   - `make security-deps`: pip-audit + npm audit
   - `make security-containers`: Trivy image scan

### Acceptance Criteria

- [ ] Every PR triggers SAST + dependency scan + secret scan
- [ ] CI blocks merge on HIGH/CRITICAL findings
- [ ] Container images scanned pre-deployment
- [ ] DAST runs against staging on main branch deploys
- [ ] Dependency update PRs weekly (Dependabot)
- [ ] Pre-commit hooks installed

---

## Implementation Sequence

### Week 1-2 (P0 -- stop the bleeding)

| Order | Item | Effort | Blocker? |
|-------|------|--------|----------|
| 1 | CISO-1: Remove hardcoded creds | 4h | Blocks CISO-3, CISO-6 |
| 2 | CISO-3: Fix auth defaults | 4h | - |
| 3 | CISO-4: Wildcard CORS | 2h | - |
| 4 | CISO-5/DEVOPS-7: Network segmentation | 4h | - |
| 5 | CISO-2: TLS everywhere | 8h | - |
| 6 | CISO-6: Webhook HMAC hardening | 6h | - |
| 7 | DEVOPS-6: Container hardening | 8h | - |

### Month 1 (P1 -- compliance foundation)

| Order | Item | Effort | Blocker? |
|-------|------|--------|----------|
| 8 | CISO-8: Audit logging enhancements | 3 days | - |
| 9 | CISO-10: Vulnerability management | 2 days | - |
| 10 | DEVOPS-8: CI/CD security scanning | 2 days | - |
| 11 | DEVOPS-2: Observability stack | 1-2 weeks | - |
| 12 | CISO-9: RBAC rollout (phase 1) | 1 week | - |
| 13 | CISO-7: PHI data flow mapping | 5 days | - |

### Month 2-3 (P2 -- maturity)

| Order | Item | Effort | Blocker? |
|-------|------|--------|----------|
| 14 | DEVOPS-4: Secret rotation | 2d-2w | CISO-1 |
| 15 | CISO-9: RBAC rollout (phase 2) | 1-2 weeks | - |
| 16 | DEVOPS-1: Infrastructure as code | 2-3 weeks | - |
| 17 | DEVOPS-3: Auto-scaling | 1-2 weeks | DEVOPS-1, DEVOPS-2 |
| 18 | CISO-11: Incident response plan | 1-2 weeks | - |

### Month 3-12 (P3 -- certification)

| Order | Item | Effort | Blocker? |
|-------|------|--------|----------|
| 19 | CISO-12: SOC 2 Type II | 6-12 months | All P0-P2 |
| 20 | DEVOPS-5: Cost monitoring | 1-2 days | DEVOPS-2 |
| 21 | CISO-13: HITRUST CSF r2 | 12-18 months | CISO-12 |

---

## Cross-references

| Resource | Path |
|----------|------|
| Security research | `docs/research/02_security_hardening_research.md` |
| Hardening plan | `docs/HARDENING_PLAN.md` |
| Architecture overview | `CLAUDE.md` |
| Backend config | `backend/app/core/config.py` |
| Auth module | `backend/app/core/security.py` |
| Auth middleware | `backend/app/api/middleware/auth_middleware.py` |
| Audit service | `backend/app/services/audit_service.py` |
| Webhook handler | `backend/app/api/metriport_webhook.py` |
| Docker base | `docker-compose.yml` |
| Docker prod | `docker-compose.prod.yml` |
| Docker dev | `docker-compose.dev.yml` |
| Docker FHIR | `docker-compose.fhir.yml` |
| FHIR MCP compose | `fhir-mcp/docker-compose.yml` |
| Nginx config | `nginx/nginx.conf` |
| Backend Dockerfile (dev) | `backend/Dockerfile` |
| Backend Dockerfile (prod) | `backend/Dockerfile.prod` |
| Frontend Dockerfile (dev) | `frontend/Dockerfile` |
| Frontend Dockerfile (prod) | `frontend/Dockerfile.prod` |
| Frontend middleware | `frontend/src/middleware.ts` |
| Frontend env | `frontend/.env.local` |
| Env example | `.env.example` |
| K8s secrets | `k8s/config/secrets.yaml` |
| K8s configmap | `k8s/config/configmap.yaml` |
| K8s network policies | `k8s/network-policies.yaml` |
| K8s backend deploy | `k8s/backend/deployment.yaml` |
| K8s ingress | `k8s/ingress.yaml` |
| K8s monitoring | `k8s/monitoring/prometheus-rules.yaml` |
| K8s prod overlay | `k8s/overlays/prod/kustomization.yaml` |
| K8s RBAC | `k8s/rbac/roles.yaml` |
