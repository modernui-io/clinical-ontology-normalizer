# P2-008 Regression Results

**ROL-08** | **Date**: 2026-02-17 | **Operator**: autonomous-agent

## Test Execution

| Metric | Result |
|---|---|
| Test file | `backend/tests/test_omop_hierarchy_guardrails.py` |
| Total tests | 40 |
| Passed | 40 |
| Failed | 0 |
| Skipped | 0 |
| Duration | 0.07s |

## False-Positive Gate

| Metric | Result |
|---|---|
| Corpus false-positive pairs | 12 |
| Pairs correctly rejected | 12/12 |
| Gate result | PASS |

## Must-Accept Gate

| Metric | Result |
|---|---|
| Corpus must-accept pairs | 6 |
| Pairs correctly accepted | 6/6 |
| Gate result | PASS |

## Lint Check

| Tool | Result |
|---|---|
| ruff check | All checks passed |

## Full Suite Regression

| Metric | Result |
|---|---|
| Full pytest (guardrail file) | 40/40 PASS |
| Regressions introduced | 0 |

---

## Precision Guardrail Extension (P2-008 Phase 2)

**Date**: 2026-02-17 | **Operator**: autonomous-agent

### Precision Guardrail Test Execution

| Metric | Result |
|---|---|
| Test file | `backend/tests/test_umls_omop_precision_guardrails.py` |
| Total tests | 39 |
| Passed (unit) | 32 |
| Skipped (integration/regression — mapping service unavailable) | 7 |
| Failed | 0 |
| Duration | 0.08s |

### Corpus Extension Summary

| Section | Count | Status |
|---|---|---|
| Ambiguous mapping pairs (Section 4) | 15 | Added |
| Domain positive pairs (Section 5) | 30 (8 medication + 8 condition + 7 procedure + 7 measurement) | Added |
| Domain precision thresholds (Section 6) | 4 domains | Added |

### Per-Domain Precision Thresholds

| Domain | Threshold | Gate Status |
|---|---|---|
| medication | 0.90 | SKIP (mapping service unavailable) |
| condition | 0.80 | SKIP (mapping service unavailable) |
| procedure | 0.75 | SKIP (mapping service unavailable) |
| measurement | 0.80 | SKIP (mapping service unavailable) |

### Ambiguous Pair Validation

| Action | Count | Status |
|---|---|---|
| reject | 12 | SKIP (mapping service unavailable — unit corpus validation PASS) |
| downgrade | 1 | SKIP (mapping service unavailable — unit corpus validation PASS) |
| flag_for_review | 2 | SKIP (mapping service unavailable — unit corpus validation PASS) |

### False-Positive Drift Detection

| Metric | Result |
|---|---|
| Strict-mode false-positive sweep | 12/12 rejected — PASS |
| Aggregate precision no-regression | SKIP (mapping service unavailable) |
| Max false-positive count allowed | 0 |

### Lint Check

| Tool | Result |
|---|---|
| ruff check (both files) | All checks passed |

### Existing Suite Regression

| Test File | Result |
|---|---|
| `test_omop_hierarchy_guardrails.py` | 40/40 PASS — no regression |
| `test_omop_acceptance.py` | No changes — unaffected |
