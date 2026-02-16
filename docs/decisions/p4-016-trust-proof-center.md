# P4-016-D: Trust/Proof Center Decision

**Decision ID:** P4-016-D
**Status:** DECIDED
**Date:** 2026-02-16
**Decision Owner:** VP Product + CISO
**Risk Owner:** VP Product
**Evidence Owner:** CISO

## Context

Trust/Proof Center frontend work is substantially complete per `tasks/26_frontend_sales_readiness_p0_p4_todo.md`:

- [x] `/trust` + `/proof` surfaces built with role-specific evidence cards
- [x] P0/P1/P4 status cards with repository evidence links and source timestamps
- [x] Claim-to-evidence linkage for readiness, uptime, incident-control claims
- [x] Trust dashboard hooked to static evidence index from backlog and ops docs

**Frontend components:**
- `frontend/src/components/readiness/PilotReadinessShowcase.tsx`
- `frontend/src/components/readiness/TrustProofContent.tsx`
- `frontend/src/app/proof/` route
- `frontend/src/app/trust/` route

## Evidence Model Decision

**One claim = one or more evidence artifacts with freshness SLA and review owner.**

| Claim Category | Evidence Source | Freshness SLA | Review Owner |
|---------------|---------------|---------------|-------------|
| P0 closure status | `tasks/09_master_change_backlog_p0_p4.md` | Real-time (reflects current backlog) | Program Lead |
| Operational readiness | `docs/evidence/p0-025/`, `p0-026/`, `p0-027/` | Per-drill (refresh on each drill execution) | Ops Lead |
| Security controls | `docs/compliance/soc2_gap_analysis.md`, P0-009 through P0-017 evidence | Quarterly refresh | CISO |
| Clinical AI safety | Confidence policy, extraction precision corpus | Monthly refresh | Clinical AI Lead |
| API health | `/api/v1/health` live endpoint | Real-time (30s polling) | Ops Lead |
| Release evidence | `docs/operations/release_checklist.md` | Per-release | CTO |

### Freshness Enforcement

- Every evidence card displays "last verified" timestamp
- Stale evidence (>SLA) shows amber warning
- Missing evidence shows red "unverified" badge
- No claim displayed without at least one evidence path

## Consequences

- Trust/Proof Center is live and functional
- Evidence model defined with freshness SLA per category
- Remaining work: ensure every individual claim block has per-entry artifact path (not just section-level)
- No unbacked claims allowed in external-facing trust pages

## Evidence Paths

- Trust page: `frontend/src/app/trust/`
- Proof page: `frontend/src/app/proof/`
- Readiness showcase: `frontend/src/components/readiness/PilotReadinessShowcase.tsx`
- Trust content: `frontend/src/components/readiness/TrustProofContent.tsx`
- Backlog evidence: `tasks/09_master_change_backlog_p0_p4.md`
- This decision: `docs/decisions/p4-016-trust-proof-center.md`
