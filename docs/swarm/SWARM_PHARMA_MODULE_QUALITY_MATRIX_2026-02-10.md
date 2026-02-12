# Pharma Module Quality Matrix (Batches 28-32)

## Scope
Audit of 25 enterprise pharma modules from recent batches:
- Batch 28: `site_initiation`, `clinical_monitoring`, `data_queries`, `sae_reporting`, `data_lock`
- Batch 29: `ip_accountability`, `protocol_feasibility`, `central_irb`, `medical_monitor`, `study_closeout`
- Batch 30: `lab_certification`, `patient_stipend`, `supply_forecasting`, `inspection_readiness`, `dsmb_management`
- Batch 31: `language_services`, `ancillary_study`, `clinical_ops_metrics`, `trial_insurance`, `payment_reconciliation`
- Batch 32: `vendor_qualification`, `document_management`, `risk_management`, `country_regulatory`, `data_transfer`

## Artifacts
- `docs/swarm/data/pharma_module_quality_matrix_2026-02-10.json`
- `docs/swarm/data/pharma_module_quality_matrix_2026-02-10.tsv`

## Summary
- Modules analyzed: `25`
- Modules with complete 4-file pattern (api + service + schema + tests): `25/25`
- Total endpoints across these modules: `647`
- Endpoints with auth signal (AST scan): `0`
- Endpoints without auth signal: `647`
- Total test functions in module test files (name-based count): `2910`
- Average endpoints/module: `25.88`
- Average tests/module: `116.4`

## Service Pattern in This Module Family
- Service classification:
  - `db_backed`: `25`
  - Others: `0`

Interpretation:
- This family is structurally consistent and complete.
- Auth exposure is uniformly high (all endpoints currently unauth-signaled).

## Highest Endpoint Density (Unauthenticated)
- `data_lock`: `34/34` unauth
- `clinical_monitoring`: `33/33` unauth
- `clinical_ops_metrics`: `33/33` unauth
- `dsmb_management`: `32/32` unauth
- `supply_forecasting`: `30/30` unauth
- `language_services`: `30/30` unauth

## Test Density Extremes (test funcs per endpoint, rough)
Lowest:
- `sae_reporting`: `1.50` (`39/26`)
- `data_lock`: `1.68` (`57/34`)
- `clinical_monitoring`: `1.73` (`57/33`)

Highest:
- `risk_management`: `7.74` (`147/19`)
- `vendor_qualification`: `7.21` (`137/19`)
- `data_transfer`: `7.20` (`144/20`)

## Implications
1. Delivery consistency is high:
- The codegen/scaffold pattern is repeatable and complete for this family.

2. Security posture needs explicit design decision:
- Either these modules are intentionally internal/public, or auth enforcement is missing by default.

3. Test distribution is uneven:
- Some modules have materially lower test density per endpoint, suggesting weaker regression confidence in those slices.

## Recommended Next Actions
1. Decide and encode default auth policy for these module families.
2. Standardize minimum test density/contract coverage thresholds per endpoint.
3. Add CI checks for module completeness + auth policy + contract test presence.
