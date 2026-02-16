# P4-018-D: Production Demo Workspace Decision

**Decision ID:** P4-018-D
**Status:** DECIDED
**Date:** 2026-02-16
**Decision Owner:** VP Product + Clinical AI + CTO
**Risk Owner:** VP Product
**Evidence Owner:** Clinical AI

## Context

Sales demo infrastructure substantially built per `tasks/26_frontend_sales_readiness_p0_p4_todo.md`:

- [x] 3 sales scenarios defined with deterministic inputs/output manifest
- [x] One-click run + evidence package export (API payloads, response hashes, evidence IDs, provenance summary)
- [x] `/sales-demo` showcase page wired to nav + docs/trust flow
- Remaining: [ ] Reviewer checklist and acceptance signature before presenting externally

**Components:**
- `frontend/src/app/sales-demo/page.tsx`
- `frontend/src/components/readiness/EvidenceBundleButton.tsx`
- `frontend/src/components/readiness/TrustProofContent.tsx`

## 3 Sales Scenarios

### Scenario 1: Clinical Safety Path
- **Input:** Mixed-domain clinical note (medications, conditions, labs, vitals)
- **Flow:** Ingest → NLP extraction → OMOP mapping → Confidence gating → Clinical Q&A
- **Evidence output:** Extraction spans, concept mappings, confidence scores, provenance chain, decline behavior on low-confidence
- **Key proof point:** System refuses to act on uncertain data (P0-021/022/023)

### Scenario 2: Interoperability Path
- **Input:** Meditech source document
- **Flow:** Meditech → OpenEHR contract mapping → Round-trip export/reimport → Reconciliation
- **Evidence output:** Mapping contract lineage, round-trip hash parity, reconciliation delta report
- **Key proof point:** Lossless data transformation with audit trail (P0-018/019)

### Scenario 3: Operations + DR/Resilience Path
- **Input:** Dependency outage simulation trigger
- **Flow:** Health probe detection → Degraded banner → Escalation matrix → Recovery → Data integrity check
- **Evidence output:** MTTR measurement, zero data loss assertion, escalation timeline, recovery validation
- **Key proof point:** System fails safely and recovers with evidence (P0-025/026/027)

### Acceptance Criteria Per Scenario

| Criteria | Required? | Verification |
|----------|-----------|-------------|
| Deterministic output (same input = same evidence) | Yes | Hash comparison across 3 runs |
| No silent demo fallbacks | Yes | DataSourceModeBanner shows Live or explicit Simulation |
| Evidence bundle exportable | Yes | One-click download with JSON + summary |
| Provenance chain complete | Yes | Every output traces to source document |
| Reviewer signoff captured | Yes | Reviewer name + date in exported bundle |

### Reviewer Checklist (Before External Presentation)

- [ ] All 3 scenarios executed successfully in last 24 hours
- [ ] Evidence bundles downloaded and spot-checked
- [ ] No simulation banners visible on demo path (or explicitly acknowledged)
- [ ] Provenance chain verified for at least 1 scenario end-to-end
- [ ] Reviewer name and sign-off date recorded
- [ ] Demo environment matches production configuration (or deviations documented)

## Consequences

- Demo workspace is functional and wired to navigation
- Remaining work: reviewer checklist component and acceptance signature capture
- No external demo without completed reviewer checklist
- Cross-dependency: P4-017 (mock surface removal) ensures demo paths show accurate data source mode

## Evidence Paths

- Sales demo page: `frontend/src/app/sales-demo/page.tsx`
- Evidence bundle: `frontend/src/components/readiness/EvidenceBundleButton.tsx`
- Trust content: `frontend/src/components/readiness/TrustProofContent.tsx`
- Sidebar nav: `frontend/src/components/Sidebar.tsx`
- This decision: `docs/decisions/p4-018-demo-workspace.md`
