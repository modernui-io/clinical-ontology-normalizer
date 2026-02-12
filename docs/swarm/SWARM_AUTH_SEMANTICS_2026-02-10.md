# Auth Semantics Audit (2026-02-10)

## Purpose
Validate actual endpoint auth signals beyond the baseline endpoint inventory, and identify mismatch risks.

## Sources
- Inventory extractor logic: `backend/scripts/endpoint_inventory.py:120`, `backend/scripts/endpoint_inventory.py:226`
- Router wiring: `backend/app/main.py:808`
- Auth primitives: `backend/app/api/middleware/auth_middleware.py:93`, `backend/app/api/middleware/auth_middleware.py:430`
- Swarm data artifacts:
  - `docs/swarm/data/auth_semantics_2026-02-10.json`
  - `docs/swarm/data/auth_semantics_file_summary_2026-02-10.tsv`
  - `docs/swarm/data/endpoint_inventory_2026-02-10.json`

## Method
AST scan across `backend/app/api/**/*.py` for each endpoint decorator (`@router.get/post/...`):
- Signature auth signal: dependency/auth primitives in endpoint signature/defaults.
- Decorator auth signal: `dependencies=[Depends(...)]` on endpoint decorator.
- Router auth signal: `APIRouter(..., dependencies=[...])` on router definitions.

## Key Results
- Endpoint count: `3113` (matches inventory).
- Inventory-reported auth-required endpoints: `73`.
- Swarm auth semantic scan (signature/decorator/router): `93`.
- Net difference: `+20` endpoints likely missed by inventory heuristic.
- Router-level auth dependencies detected: `0` endpoints.
- Endpoints with no auth signal detected: `3020`.

Interpretation:
- Baseline inventory undercounts some auth-protected endpoints.
- Most routes still appear effectively public unless protected by another layer not visible in endpoint signatures/decorators.

## Why Inventory Undercounts
`endpoint_inventory.py` currently uses `_has_auth_dependency()` with a narrow indicator list in function AST dumps (`backend/scripts/endpoint_inventory.py:120`), which misses some real patterns (notably permission checker wrappers and local dependency helpers).

## Why Inventory Can Also Overcount
At least one endpoint appears as a false positive in the inventory:
- `backend/app/api/quality_measures.py:913` (`close_gap`) does not declare auth dependency, but includes the literal string `"current_user"` in response data (`backend/app/api/quality_measures.py:936`), which can trip broad string matching.

## Highest-Exposure Endpoint Files (no detected auth signal)
From swarm AST audit (`unauth/total`):
- `34/34` `backend/app/api/data_lock.py`
- `33/33` `backend/app/api/threat_intelligence.py`
- `33/33` `backend/app/api/clinical_ops_metrics.py`
- `33/33` `backend/app/api/clinical_monitoring.py`
- `32/32` `backend/app/api/dsmb_management.py`
- `31/31` `backend/app/api/biomarker_analysis.py`
- `30/30` `backend/app/api/supply_forecasting.py`
- `30/30` `backend/app/api/language_services.py`
- `30/30` `backend/app/api/clinical_data_management.py`
- `29/29` `backend/app/api/trial_management.py`

## Most Auth-Protected Files (all endpoints protected, min 5 endpoints)
- `15/15` `backend/app/api/trials.py`
- `9/9` `backend/app/api/users.py`
- `7/7` `backend/app/api/fairness_audit.py`
- `7/7` `backend/app/api/scalability_audit.py`
- `6/6` `backend/app/api/observability.py`
- `5/5` `backend/app/api/diversity_analytics.py`
- `5/5` `backend/app/api/sites.py`

## Architectural Notes
- `backend/app/main.py` includes routers without global dependency enforcement at include time (`backend/app/main.py:808` onward).
- This means auth is mostly local and per-endpoint/per-module, which is easy to drift.

## Recommendations
1. Add explicit auth policy metadata to each router (public/internal/protected) and validate in CI.
2. Strengthen inventory script to parse `Depends(...)` and `APIRouter(...dependencies=...)` semantically rather than string heuristics.
3. Add a security gate test that fails if new “protected-domain” endpoints are added without auth dependency.
4. Consider introducing guarded parent routers for sensitive domains to reduce per-endpoint drift.
