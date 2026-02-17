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
