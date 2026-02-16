# P0-019 Evidence Capture Packet (OpenEHR Dry-run, Reconcile, Rollback)

Date: 2026-02-16
Owner: CTO + Ops
Priority: P0-019-A/B readiness evidence

## Goal

Capture machine-readable and human-readable evidence for:

- `P0-019-A` — 5 dry-run executions with expected-count validation
- `P0-019-B` — round-trip validation and rollback verification on staged test data

## 1) Environment Variables and Inputs

- `X-API-Key` is optional only if your service enforces it.
- `--base-url` should point to a **staging** backend with DB + Neo4j available.
- Recommended: clear previous test patients before execution.

## 2) Run Command

```bash
cd /Users/alexstinard/projects/brainstorm/jan-14-2026
export X_API_KEY="<ops-api-key>"   # optional if API key enforcement is enabled
python3 scripts/p0_019_evidence_capture.py \
  --base-url "http://localhost:8000/api/v1" \
  --api-key "$X_API_KEY" \
  --operator "<Operator Name>" \
  --out-dir "docs/evidence/p0-019"
```

Optional one-off: dry-run only (no writes / rollback checks):

```bash
python3 scripts/p0_019_evidence_capture.py \
  --skip-rollback \
  --out-dir "docs/evidence/p0-019"
```

## 3) Expected Output Paths (Evidence columns)

For each run:

- JSON bundle: `docs/evidence/p0-019/p0-019-evidence-<RUN_ID>.json`
- Human summary: `docs/evidence/p0-019/p0-019-evidence-<RUN_ID>.md`

Use `Evidence path` in `tasks/08_autonomous_execution_board.md` and `tasks/09_master_change_backlog_p0_p4.md` with the same path.

## 4) What the harness validates

Scenario set:

1. `mixed_all`
2. `labs_only`
3. `medications_heavy`
4. `procedures_vitals`
5. `allergies_conditions`

For each scenario, script runs:

- `POST /api/v1/openehr/dry-run`
- `POST /api/v1/openehr/composition` (roundtrip path)
- `POST /api/v1/openehr/reconcile/{patient_id}`
- `POST /api/v1/openehr/rollback`
- `POST /api/v1/openehr/reconcile/{patient_id}` (post-rollback residual check)

### Pass/Fail rules

- Dry-run passes only if:
  - HTTP 200
  - `success: true`
  - count fields exactly match expected fixture counts
- Round-trip pass only if:
  - import persists (`/composition` success)
  - reconcile returns `match: true`
  - fingerprints exist and are equal
- Rollback pass only if:
  - rollback returns `success: true`
  - residual reconcile contains “No facts found for patient”

## 5) Suggested board updates (next step)

Use this for P0-019:

- `P0-019-A` -> evidence path = most recent markdown or JSON
- `P0-019-B` -> same path, with timestamp and status “PASS” if all 5 scenarios pass end-to-end
- `P0-028-A` -> reference this evidence as prerequisite for Go/Conditional-Go narrative

## 6) Front-end evidence surfaces to add next (P4-aligned planning)

You already have existing production-facing components that can host this:

- `/frontend/src/app/security/page.tsx` (trust and controls)
- `/frontend/src/app/docs/page.tsx` (reference architecture + evidence links)
- `/frontend/src/app/changelog/page.tsx` (evidence-backed change log)

Add new components for sales/reviewer confidence:

- **Trust Evidence Center** (`P4-016`) with claim → artifact mapping + expiry checks
- **Readiness Command Bar** (`P4-018`) with live run status, DR test dates, and evidence links
- **Ops Drill Replay** (`P4-020`) showing archived evidence artifacts for each P0 drill

If you want, I can generate these three pages as concrete frontend tickets with API wiring and acceptance criteria next.
