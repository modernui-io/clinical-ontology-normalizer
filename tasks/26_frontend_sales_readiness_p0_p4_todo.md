# Frontend + Product-Readiness To-Do (P0 → P4)

**Created:** 2026-02-16
**Goal:** Keep pilot-safe operations first, then make the product clearly demonstrable to humans (sales/investors/site leads) with production-evidence backed UI.
**Primary sources:** `tasks/09_master_change_backlog_p0_p4.md`, `tasks/16_sprint1_execution_board.md`, existing frontend routes under `frontend/src/app/`.

## 0) Current state (non-negotiables)
- Open P0s: `P0-019`, `P0-025`, `P0-026`, `P0-027`, `P0-028`
- Sprint 1 board `todo` items still match those 5 P0 tasks (`tasks/16_sprint1_execution_board.md`)
- Several visible UI pages are demo-heavy and should be converted before sales-facing claims:
  - `frontend/src/app/admin/dashboard/page.tsx` (simulated request/CPU/memory sections)
  - `frontend/src/app/reports/page.tsx` and `frontend/src/app/reports/export/page.tsx` (mock datasets)
  - `frontend/src/app/clinical/reconciliation/page.tsx` (mock reconciliation)
  - `frontend/src/app/pipelines/openehr/operations/page.tsx` (UI fallback mode currently allowed)
  - `frontend/src/app/docs/page.tsx`/`frontend/src/app/changelog/page.tsx` (static claims, no evidence trail)

## 1) P0 closure first (same order as sprint board)

### P0-019 OpenEHR reconciliation and rollback
- [ ] **P0-019-A (OpenEHR dry-run evidence)**
  - Run `scripts/p0_019_evidence_capture.py --base-url http://localhost:8000/api/v1 --out-dir docs/evidence/p0-019 --operator "ops-runner"` against 5 mixed-domain fixtures.
  - Verify `scripts/p0_019_evidence_capture.py` output: pass/fail per scenario and reconciliation deltas.
  - Evidence path:
    - `docs/evidence/p0-019/p0-019-evidence-*.md`/`.json`

- [ ] **P0-019-B (round-trip + rollback proof)**
  - Resolve existing measurement-parity failures in `backend/app/services/openehr_rollback.py` and extraction/reimport symmetry (if still failing after current patch).
  - Re-run harness full execution and record round-trip hash parity + no orphaned entities + deterministic rollback.
  - Evidence path:
    - `docs/evidence/p0-019/p0-019-evidence-*.md`

### P0-025 Incident escalation and breach path
- [ ] **P0-025-A (drill + timing)**
  - Execute escalation drill using real on-call contacts; capture paging + response sequence.
  - Record response duration for detection → page → assign → stable handoff.
  - Evidence path:
    - `docs/operations/incident_escalation_matrix.md`
    - `docs/operations/incident_logbook.md` (new if missing)

- [ ] **P0-025-B (HIPAA clock and notification path)**
  - Add and evidence-seal a clock path for external notification windows, aligned with 60-day/notification requirements in policy docs.
  - Evidence path:
    - `docs/operations/incident_escalation_matrix.md`
    - `docs/operations/incident_response_run_log.md` (new/updated)

### P0-026 Backup restore readiness
- [ ] **P0-026-A (PostgreSQL PITR proof)**
  - Execute controlled PostgreSQL restore drill; collect RPO/RTO and row-count/integrity checks.
  - Evidence path:
    - `docs/operations/backup_restore_drill.md`
    - `docs/evidence/backup_restore/p0-026/*.md`

- [ ] **P0-026-B (Neo4j backup restore proof)**
  - Execute Neo4j backup/restore drill; verify chain integrity + consistency.
  - Evidence path:
    - `docs/operations/backup_restore_drill.md`
    - `docs/evidence/backup_restore/p0-026/*.md`

### P0-027 Failover and degraded-mode behavior
- [ ] **P0-027-A (dependency outage simulations)**
  - Run dependency outage scenarios for LLM, Neo4j, Postgres, Kafka/network.
  - Collect MTTR and immediate clinician impact.
  - Evidence path:
    - `docs/operations/failover_simulation.md`
    - `docs/evidence/failover/p0-027/*.md`

- [ ] **P0-027-B (no-data-loss + UX assertion)**
  - Add explicit checks for no orphaned records + degraded banner behavior + clinician-safe paths.
  - Evidence path:
    - `docs/operations/failover_simulation.md`

### P0-028 Final signoff
- [ ] **P0-028-A (go/no-go matrix)**
  - Pull validated outputs from P0-019/025/026/027; add approver names/dates/expiry by role.
  - Evidence path:
    - `docs/operations/pre_pilot_signoff_matrix.md`

- [ ] **P0-028-B (rollback criteria)**
  - Finalize severity thresholds, data-integrity gates, and who calls rollback under live incidents.
  - Evidence path:
    - `docs/operations/pre_pilot_signoff_matrix.md`

## 2) Frontend components needed for “we can show this in production” (P4 track)

### P4-016 Trust/Proof Center
- [x] Build `/trust` + `/proof` surfaces with role-specific evidence cards.
- [x] Add cards for P0/P1/P4 status with repository evidence links and source timestamps.
- [x] Add `claim → evidence` linkage for readiness, uptime, and incident-control claims.
- [x] Hook trust dashboard to static evidence index derived from `tasks/09_master_change_backlog_p0_p4.md` and `docs/operations` path probes.
  - Anchors: `docs/operations/`, `docs/evidence/`, `tasks/09_master_change_backlog_p0_p4.md`

### P4-017 Remove mock-only operational surfaces
- [x] Create shared source-mode marker component (`frontend/src/components/readiness/DataSourceModeBanner.tsx`).
- [x] Wire source-mode marker into all known simulation-backed operator/reports pages:
  - `frontend/src/app/admin/dashboard/page.tsx`
  - `frontend/src/app/reports/page.tsx`
  - `frontend/src/app/reports/export/page.tsx`
- [x] Expand marker coverage to:
  - `frontend/src/app/clinical/reconciliation/page.tsx`
  - `frontend/src/app/pipelines/openehr/operations/page.tsx`
  - Any other mock-only clinical/ops demo tools prior to external demos.
- [x] Add a visual mode indicator: `Live` / `Mixed` / `Simulation`.
- [x] Add explicit evidence timestamps and backend endpoint placeholders for every remaining simulated section. Done 2026-02-16: `DataSourceModeBanner` now supports `backendEndpoints` and `signoffText` props. Applied to reports, export, and clinical intelligence pages.
- [x] Add the same marker pattern to `frontend/src/app/admin/audit/page.tsx` (mock audit logs + operational evidence).
- [x] Add the same marker pattern to `frontend/src/app/clinical/intelligence/page.tsx` (demonstration graph view when API unavailable). Done 2026-02-16: Replaced ad-hoc demo banner with `DataSourceModeBanner` that toggles between Live/Simulation based on API availability.
- [x] Add signoff text in each banner clarifying "simulation only" when user actions are not writing to backend. Done 2026-02-16: Added `signoffText` prop to `DataSourceModeBanner` and applied across reports, export, and clinical intelligence pages.

### P4-018 Production demo workspace
- [x] Define 3 sales scenarios with deterministic inputs/output manifest:
  1. Clinical safety path
  2. Interoperability path
  3. Operations + DR/resilience path
- [x] Add one-click run + evidence package export.
  - Include API payloads, response hashes, evidence IDs, provenance summary.
- [ ] Add reviewer checklist and acceptance signature before presenting externally.
  - Suggested anchor: `frontend/src/app/clinical/intelligence/page.tsx` + `frontend/src/app/pipelines/openehr/page.tsx`
- [x] Add `/sales-demo` showcase page and wire it to nav + docs/trust flow.
  - Anchors: `frontend/src/app/sales-demo/page.tsx`, `frontend/src/components/readiness/EvidenceBundleButton.tsx`,
    `frontend/src/components/readiness/TrustProofContent.tsx`, `frontend/src/components/Sidebar.tsx`,
    `frontend/src/app/docs/page.tsx`.

### P4-019 Reporting from real pipeline
- [x] Replace mock report tables with backend-backed report generation. Done 2026-02-16: Reports page now attempts `/api/v1/reports` fetch on mount, falls back to mock data with explicit Simulation banner when backend unavailable.
- [x] Add provenance metadata per export: template id, report timestamp, operator, parameters, source patient set. Done 2026-02-16: Added `ReportProvenance` type and provenance column to both `/reports` and `/reports/export` tables.
  - Anchors: `frontend/src/app/reports/page.tsx`, `frontend/src/app/reports/export/page.tsx`, `backend` report endpoints.

### P4-020 Evidence-indexed docs/changelog
- [x] Add evidence index surfaces to `frontend/src/app/docs/page.tsx` and `frontend/src/app/changelog/page.tsx`.
- [x] Convert all claim blocks on these pages to per-entry supporting artifact path + update date + freshness. Done 2026-02-16: Docs sections now include per-card `evidenceArtifact` + `evidenceFreshness`. Changelog entries now have per-change `artifact` + `freshness` rendered below each line.
- [x] Add a "supporting artifact" verification note for every claim block (not just section-level summaries). Done 2026-02-16: Both docs and changelog now render artifact path + freshness date at each individual claim level.
- [x] Extract shared evidence types/utilities to `frontend/src/lib/evidence.ts` and add consistency test at `frontend/__tests__/lib/evidence-consistency.test.ts`. Done 2026-02-16.

## 3) Suggested owners and sequencing

- **Ops Lead (first)**: complete P0-025/026/027 drills and incident timeline artifacts.
- **CTO + Platform + Clinical AI**: resolve P0-019 execution issues, harden rollback parity.
- **Program Lead**: finalize P0-028 and risk owner signoff.
- **Frontend Squad**:
  - Week 1: trust/proof pages + evidence wiring
  - Week 2: remove simulated operations surfaces + report/export integration
- **Sales + Product**: define scenario pack (P4-018) and external demo packaging.

## 4) One-day execution plan to move from “mixed readiness” to “show-ready”

- [ ] **Sprint-1 P0 close sequence (in order):**
  - `P0-019-A`: run 5 mixed-domain dry-runs and capture op/replay evidence (`docs/evidence/p0-019/*`).
  - `P0-019-B`: close rollback + round-trip parity evidence (hash diffs + orphan checks).
  - `P0-025-A`: execute escalation drill with timing evidence.
  - `P0-025-B`: add HIPAA response-clock evidence + escalation recipient chain.
  - `P0-026-A` + `P0-026-B`: run PostgreSQL + Neo4j restore drills and record RTO/RPO.
  - `P0-027-A` + `P0-027-B`: execute failover outages + degraded-mode assertion evidence.
  - `P0-028-A` + `P0-028-B`: run signoff matrix closure with approver names/dates/blocker status.
- [ ] **Frontend P4 closure (no behavior break):**
  - finish banner evidence timestamps and endpoint placeholders on all remaining simulated operational pages.
  - convert reports/reconciliation/demo surfaces to endpoint-driven data (or keep explicit simulation mode banner if unavailable).
  - add per-claim evidence artifact links to `/docs` and `/changelog` entries.
- [ ] **Publish external-readiness package:**
  - run a 20-minute investor demo rehearsal against `/sales-demo`, `/trust`, and `/proof`.
  - capture evidence bundle with route links, timestamps, and fallback status for every screen shown.

## 5) Exit criteria (before external show/pilot narrative)
- All 5 P0 items marked `done` in `tasks/16_sprint1_execution_board.md`.
- `P0-019` artifacts include at least one pass for mixed-domain dry-run and one pass for rollback completeness.
- One public-safe demo workspace available with deterministic evidence export and no silent demo fallbacks.
- Claim pages (`/docs`, `/changelog`, trust page) traceable to evidence files in repo.

## 6) Notes for the next agent
- Keep operational execution evidence files as first-class artifacts; use `.md` summaries plus JSON payload dumps.
- Do not present any UI claim without an evidence link during pre-sale/demo sessions.
- Prefer wiring to existing services first before creating new APIs (e.g., health/audit/healthiness signals and compliance binder patterns).
