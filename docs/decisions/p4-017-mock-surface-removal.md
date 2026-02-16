# P4-017-D: Mock-Only Operational Surface Removal Decision

**Decision ID:** P4-017-D
**Status:** DECIDED
**Date:** 2026-02-16
**Decision Owner:** CTO + Ops
**Risk Owner:** Ops
**Evidence Owner:** CTO

## Context

Significant progress on mock surface labeling per `tasks/26_frontend_sales_readiness_p0_p4_todo.md`:

- [x] `DataSourceModeBanner.tsx` shared component created with `Live` / `Mixed` / `Simulation` modes
- [x] Banner wired into: admin dashboard, reports, reports/export, reconciliation, OpenEHR operations, admin audit
- Remaining unchecked:
  - [ ] Evidence timestamps and backend endpoint placeholders for remaining simulated sections
  - [ ] Banner for `clinical/intelligence/page.tsx` (demonstration graph view when API unavailable)
  - [ ] Signoff text in each banner clarifying "simulation only" when actions are not writing to backend

## Production-Only vs. Demonstration-Mode Rules

| Metric/Surface | Source | Current State | Rule |
|---------------|--------|---------------|------|
| Request volume (admin dashboard) | Simulated | Mock data | Label: "Simulation — no live API" |
| CPU/Memory gauges (admin dashboard) | Simulated | Mock data | Label: "Simulation — connect to metrics API for live data" |
| Audit log table (admin audit) | Simulated | Mock events | Label: "Demonstration — audit events from live system pending" |
| Report templates (reports page) | Seeded | Static fixtures | Label: "Template preview — generate from production data" |
| Reconciliation table (clinical) | Simulated | Mock reconciliation | Label: "Demonstration — connect to OpenEHR endpoint for live data" |
| Health/readiness (proof page) | Live API | Real `/health` endpoint | No label needed (live) |
| P0 evidence cards (trust page) | Repository evidence | Real file paths | No label needed (evidence-backed) |

### Explicit "Simulated" Labeling Standard

Every simulation banner must include:
1. Mode indicator: `Simulation` (amber), `Mixed` (yellow), `Live` (green)
2. Reason: Why this surface is simulated (e.g., "API endpoint not connected")
3. Action: What would make it live (e.g., "Connect to Prometheus metrics API")
4. Timestamp: When this page was last evaluated for data source mode

## Consequences

- Most mock surfaces already labeled with `DataSourceModeBanner`
- Remaining 3 items are incremental frontend additions (evidence timestamps, intelligence page banner, signoff text)
- No backend changes needed — banner component reads from data source availability
- QA walkthrough required before external demos (every card must resolve to live API or show explicit fallback reason)

## Evidence Paths

- Data source banner: `frontend/src/components/readiness/DataSourceModeBanner.tsx`
- Admin dashboard: `frontend/src/app/admin/dashboard/page.tsx`
- Admin audit: `frontend/src/app/admin/audit/page.tsx`
- Reports: `frontend/src/app/reports/page.tsx`, `frontend/src/app/reports/export/page.tsx`
- Reconciliation: `frontend/src/app/clinical/reconciliation/page.tsx`
- OpenEHR ops: `frontend/src/app/pipelines/openehr/operations/page.tsx`
- This decision: `docs/decisions/p4-017-mock-surface-removal.md`
