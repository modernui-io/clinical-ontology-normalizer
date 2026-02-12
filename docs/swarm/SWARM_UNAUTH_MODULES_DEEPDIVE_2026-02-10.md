# Unauthenticated Module Deep Dive (2026-02-10)

## Focus
Deep-read of high-exposure API modules with large unauthenticated endpoint counts, starting with:
- `backend/app/api/data_lock.py`
- `backend/app/api/clinical_monitoring.py`

## Observed Pattern
1. Rich domain semantics and lifecycle operations:
- `data_lock` exposes lock lifecycle, unblinding, and checklist operations (`backend/app/api/data_lock.py:1`).
- `clinical_monitoring` exposes visit lifecycle, findings, SDV, CAPA, and reports (`backend/app/api/clinical_monitoring.py:1`).

2. No auth dependencies in router or endpoint signatures:
- Routers created without auth dependencies:
  - `backend/app/api/data_lock.py:83`
  - `backend/app/api/clinical_monitoring.py:89`
- Endpoint signatures are domain payloads/query params only (no `Depends(get_current_user)` or `PermissionChecker` patterns in these files).

3. Service implementations are in-memory singleton engines:
- `data_lock` service is explicitly in-memory with thread lock and seeded demo data:
  - `backend/app/services/data_lock_service.py:64`
  - `backend/app/services/data_lock_service.py:71`
  - `backend/app/services/data_lock_service.py:83`

4. Tests validate CRUD/lifecycle behavior but not auth gates:
- `data_lock` tests cover status and workflow transitions (`backend/tests/test_data_lock.py:56`) with no 401/403 assertions.
- `clinical_monitoring` tests similarly validate business behavior (`backend/tests/test_clinical_monitoring.py:56`) with no 401/403 assertions.

## Family-Level Signal (Batches 28-32)
From matrix artifacts:
- 25/25 modules complete (api/service/schema/test).
- 647/647 endpoints unauth-signaled by AST pass.
- Auth test signal scan across these test modules:
  - modules with 401 assertions: `0/25`
  - modules with 403 assertions: `0/25`
- Artifact: `docs/swarm/data/pharma_module_auth_test_signals_2026-02-10.json`

## Interpretation
Two plausible realities:
1. These modules are intentionally internal/demo-grade and currently public by design.
2. These modules are intended to be protected but auth integration is missing.

Given domain sensitivity (clinical operations, lock/unblinding workflows), default-public is a high-risk default unless constrained by infrastructure/network policy.

## Recommended Decision Gate
1. Classify each module as:
- `public`
- `internal`
- `protected`

2. Enforce via CI:
- `protected` modules must contain explicit auth dependency in router or endpoints.
- `protected` modules must include 401/403 contract tests.

3. Apply staged hardening:
- Stage 1: read operations.
- Stage 2: write/lifecycle transition operations.
- Stage 3: high-impact operations (lock, unblinding, CAPA closure, approvals).
