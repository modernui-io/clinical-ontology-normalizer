# P4-019-D: Production Report Pipeline Decision

**Decision ID:** P4-019-D
**Status:** DECIDED
**Date:** 2026-02-16
**Decision Owner:** CTO + CISO + Ops
**Risk Owner:** CTO
**Evidence Owner:** Ops

## Context

Report and export pages currently use mock/seeded data:

- `frontend/src/app/reports/page.tsx` — report listing with mock templates/jobs
- `frontend/src/app/reports/export/page.tsx` — export interface with seeded data
- `DataSourceModeBanner` already wired to both pages (P4-017 progress)
- Backend reporting endpoints exist but are not wired to frontend

**Current state:** Reports page shows template previews and simulated job history. No production report generation pipeline connected.

## Report Contract Definition

### Report Types

| Report Type | Template | Parameters | Owner | Retention | Signing Required? |
|------------|----------|-----------|-------|-----------|------------------|
| Cohort Summary | Patient demographics + clinical fact rollup | date_range, cohort_filter, tenant_id | Clinical Ops | 7 years | No |
| Billing Quality (HCC) | HCC code capture rates and recapture opportunities | date_range, payer_filter | RCM Lead | 7 years | Yes (by RCM Lead) |
| Clinical Safety | Confidence policy gate activations and decline events | date_range, severity_filter | Clinical AI Lead | 7 years | Yes (by CISO) |
| Operational Health | SLO compliance, uptime, incident summary | date_range | Ops Lead | 3 years | No |
| Audit Trail | PHI access events, user actions, export log | date_range, user_filter | CISO | 7 years (HIPAA) | Yes (by CISO) |

### Export Evidence Metadata

Every exported report must include:
1. `report_id`: Unique identifier (UUID)
2. `template_id`: Which template generated this report
3. `parameters`: Exact parameters used for generation
4. `generated_at`: UTC timestamp
5. `generated_by`: Operator identity
6. `row_count`: Number of data rows in report
7. `data_freshness`: Timestamp of most recent data point included
8. `sha256_hash`: Integrity hash of report content
9. `audit_record_id`: Link to audit trail entry for this export

### Pipeline Architecture (When Wired)

```
Frontend (report request)
  → Backend report endpoint (validates params, checks RBAC)
    → PostgreSQL query (parameterized, tenant-scoped)
      → Report renderer (template + data)
        → Export artifact (PDF/CSV + metadata JSON)
          → Audit log entry (who, what, when, hash)
            → Storage (encrypted at rest, retention-tagged)
```

## Consequences

- Reports page remains in simulation mode with explicit `DataSourceModeBanner` during pilot
- Report contracts defined and ready for backend wiring
- No mock report data presented as production data
- Backend wiring is Implementation phase (P4-019-I) work — deferred to post-pilot sprint
- Audit trail for exports already partially supported by P0-014 audit coverage

## Evidence Paths

- Reports page: `frontend/src/app/reports/page.tsx`
- Export page: `frontend/src/app/reports/export/page.tsx`
- Data source banner: `frontend/src/components/readiness/DataSourceModeBanner.tsx`
- Audit middleware: `backend/app/middleware/audit_middleware.py`
- This decision: `docs/decisions/p4-019-production-reports.md`
