# P4-020-D: Evidence-Indexed Documentation Decision

**Decision ID:** P4-020-D
**Status:** DECIDED
**Date:** 2026-02-16
**Decision Owner:** VP Product + CISO
**Risk Owner:** VP Product
**Evidence Owner:** CISO

## Context

Documentation and changelog pages have partial evidence indexing per `tasks/26_frontend_sales_readiness_p0_p4_todo.md`:

- [x] Evidence index surfaces added to `frontend/src/app/docs/page.tsx` and `frontend/src/app/changelog/page.tsx`
- Remaining:
  - [ ] Convert all claim blocks to per-entry supporting artifact path + update date + freshness
  - [ ] Add "supporting artifact" verification note for every claim block (not just section-level)

**Goal:** Every feature statement or capability claim is navigable to supporting evidence and run records in <=3 clicks.

## Canonical Artifact Index Schema

### Schema Definition

```typescript
interface EvidenceEntry {
  claim_id: string;          // Unique claim identifier (e.g., "CLAIM-SEC-001")
  claim_text: string;        // The statement being made
  category: ClaimCategory;   // security | clinical | operational | interop | product
  evidence_paths: string[];  // Repository paths to supporting artifacts
  last_verified: string;     // ISO 8601 timestamp of last verification
  verified_by: string;       // Role or operator who last verified
  freshness_sla: string;     // "quarterly" | "monthly" | "per-release" | "real-time"
  status: EvidenceStatus;    // verified | stale | unverified | disputed
}

type ClaimCategory = "security" | "clinical" | "operational" | "interop" | "product";
type EvidenceStatus = "verified" | "stale" | "unverified" | "disputed";
```

### Evidence Registry Sources

| Source Directory | Category | Refresh Trigger |
|-----------------|----------|----------------|
| `tasks/09_master_change_backlog_p0_p4.md` | All categories | Per backlog update |
| `docs/evidence/p0-019/` through `p0-028/` | Operational | Per drill execution |
| `docs/operations/*.md` | Operational | Per policy update |
| `docs/compliance/*.md` | Security | Quarterly review |
| `docs/regulatory/*.md` | Clinical/Compliance | Per regulatory change |
| `docs/decisions/p4-*.md` | All categories | Per decision update |

### Navigation Target

**3-click path:** Feature statement → Evidence card → Source artifact

1. User reads claim on `/docs` or `/changelog`
2. Clicks evidence link → shows evidence card with paths, timestamps, verification status
3. Clicks artifact path → opens source file or evidence document

## Consequences

- Evidence index schema defined and ready for implementation
- Remaining frontend work: per-claim artifact linking (not just section-level)
- Every claim block must have at least one evidence path before external visibility
- Stale claims (beyond freshness SLA) show amber warning automatically
- Cross-dependency: P4-016 (Trust Center) uses same evidence schema

## Evidence Paths

- Docs page: `frontend/src/app/docs/page.tsx`
- Changelog page: `frontend/src/app/changelog/page.tsx`
- Evidence directories: `docs/evidence/`
- Operations docs: `docs/operations/`
- Compliance docs: `docs/compliance/`
- Decisions: `docs/decisions/`
- This decision: `docs/decisions/p4-020-evidence-indexed-docs.md`
