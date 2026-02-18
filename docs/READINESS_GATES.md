# API Readiness Gates

Promotion and demotion criteria for API maturity tiers.

## Tier Definitions

| Tier | Stability | Audience | Headers |
|------|-----------|----------|---------|
| **PRODUCTION** | Stable, breaking changes require deprecation cycle | All consumers | `X-API-Maturity: production` |
| **PILOT** | Functional, may change between releases | Internal + beta partners | `X-API-Maturity: pilot` |
| **SCAFFOLD** | Experimental, no stability guarantees | Internal development only | `X-API-Maturity: scaffold`, `X-API-Stability: experimental`, `Warning: 299` |

## Promotion: SCAFFOLD → PILOT

All of the following must be satisfied:

1. **Integration test coverage** — at least one backend test exercising the happy path
2. **Schema definitions** — request/response schemas use Pydantic models (not raw dicts)
3. **Structured error handling** — error responses use the project's `ErrorResponse` pattern, not bare `except: pass`
4. **Service owner identified** — a team or individual is accountable for the route's behavior
5. **No silent failures** — critical operations must not swallow exceptions (Phase 1 safety envelope)

## Promotion: PILOT → PRODUCTION

All of the following must be satisfied:

1. **Frontend integration** — actively called from UI hooks in `frontend/src/hooks/api/`
2. **Contract tests** — tests cover both success and error paths
3. **No broad exception handlers** — no `except Exception` on critical flow paths
4. **Degradation metadata** — responses include Phase 1 degradation metadata when applicable
5. **Performance baseline** — load/latency baseline established and documented
6. **Security review** — authentication enforced, input validation present, no OWASP top-10 gaps
7. **OpenAPI documentation** — all endpoints documented with descriptions and example responses

## Demotion Criteria

| Condition | Action |
|-----------|--------|
| No frontend references for 2 release cycles | Demote from PRODUCTION to PILOT |
| No test coverage | Cannot promote above SCAFFOLD |
| Silent failure pattern discovered | Demote to SCAFFOLD until remediated |
| Security vulnerability found | Demote to SCAFFOLD until patched and reviewed |
| Service owner departs without transfer | Demote to PILOT until new owner assigned |

## Deprecation Lifecycle

When a route is deprecated:

1. Add entry to `DEPRECATION_SCHEDULE` in `backend/app/core/api_maturity.py`
2. Middleware automatically emits `Deprecation: true`, `Sunset: <date>`, and `Link: <successor>` headers
3. Minimum 90-day notice period before sunset date
4. After sunset: route returns `410 Gone` or is removed

## Registry Maintenance

- Every new router MUST have a maturity classification in `ENDPOINT_MATURITY_REGISTRY`
- The `test_api_maturity_labeling.py` contract test enforces registry completeness
- Classifications are reviewed quarterly during architecture review
