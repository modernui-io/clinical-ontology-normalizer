# Swarm Findings (Living)

## Initial Findings (2026-02-10)

1. Repository size is data-heavy, not just code-heavy.
- `json`/`csv` accounts for 3,241,852 LOC (~77%).
- Most of this is in `backend/fixtures`.

2. Backend service layer is the largest executable concentration.
- `backend/app/services`: 303,578 LOC across 343 files.
- This is 60.34% of `backend/app`.

3. API footprint is very large and mostly pilot maturity.
- 3,113 endpoints across 232 API files.
- Maturity: Pilot 2,745, Production 283, Scaffold 85.

4. Auth coverage needs deeper validation.
- Inventory flags show 73 endpoints requiring auth and 3,040 without explicit auth.
- This may undercount router-level or dependency-injected auth constraints.

5. Frontend complexity is material but secondary to backend sprawl.
- `frontend/src`: 130,698 LOC across 241 files.
- Highest concentration currently appears in `analytics`, then `clinical` and `etl`.

6. Auth inventory currently undercounts protected endpoints.
- Endpoint inventory reports 73 auth-required endpoints.
- AST auth semantics pass reports 93 endpoints with auth signals.
- Delta: +20 endpoints, with a known heuristic false positive case in `quality_measures.close_gap`.

7. Router-level auth guardrails are effectively absent.
- No `APIRouter(...dependencies=[...])` auth enforcement was detected in the API scan.
- Auth is mostly per-endpoint/per-module, which increases drift risk as module count grows.

8. Service lifecycle boilerplate is pervasive.
- `246/343` service files expose `get_*service` factories.
- `191/343` include corresponding `reset_*service`.
- `200/343` include explicit lock patterns, suggesting repeated singleton lifecycle code.

9. Largest service modules skew DB-backed.
- In top 100 largest service files: 69 classify as DB-backed.
- In-memory/fixture class remains large (23 of top 100), indicating parallel implementation styles.

10. Document processing pipeline favors availability over strict consistency.
- Upload persists document even when queue enqueue fails.
- Graph sync failure is tolerated and does not fail document processing.
- This is pragmatic, but creates deferred-consistency and observability requirements.

11. Recent pharma module family (batches 28-32) is complete but fully unauth-signaled.
- 25/25 modules have api/service/schema/test file completeness.
- 647/647 endpoints in this family are currently unauth-signaled by AST pass.
- Test density is uneven (e.g., `sae_reporting`, `data_lock`, `clinical_monitoring` lower per-endpoint ratios).

12. Auth contract tests are absent in this pharma module family.
- Across `backend/tests/test_<module>.py` for these 25 modules, 401/403 assertions were not detected.
- Existing tests strongly validate lifecycle and CRUD behavior, but not access-control behavior.

13. Document processing retries are only partially idempotent.
- Fact/graph layers have dedup behavior, but mention/candidate layers can amplify on reprocessing.
- No explicit single-consumer lock was observed for per-document processing.
- Retry contract tests for duplicate execution behavior are not currently evident.

14. Org-level readiness is strong on breadth, weak on policy-consistent hardening.
- Multi-role review indicates velocity and module completeness are high.
- Primary blockers to enterprise-grade posture are auth policy enforcement, idempotency controls, and control-plane test contracts.

15. Executive operating model now has explicit CEO/COO/Founder lenses, but execution mapping is still pending.
- Strategic and operational priorities are now documented per executive role.
- Next gap is direct owner-mapped implementation backlog to convert guidance into delivery.

## Hypotheses To Validate
- Many service modules follow repeated in-memory CRUD scaffolds that can be consolidated.
- Router registration and endpoint patterns likely support generation/composition to reduce boilerplate.
- Some test volume may be broad but shallow; contract-level API tests may be uneven by domain.

## Next Analysis Pass
1. Deep file-by-file pass on highest-exposure API modules (auth + business criticality).
2. Module family comparison for pharma batch modules (schema/service/api/test consistency quality).
3. Idempotency and failure-mode analysis for document processing retries.
4. Test signal pass: compare module size vs test depth to identify high-risk gaps.
