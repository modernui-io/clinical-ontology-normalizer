# P2-008 UMLS/OMOP Precision Guardrail Corpus

**ROL-08** | **Date**: 2026-02-17 | **Owner**: Clinical AI + QA

## Purpose

This corpus validates that `OMOPHierarchyService._string_fallback_match()` correctly rejects clinically dangerous near-matches when Neo4j is unavailable and the service falls back to string similarity. The P1-008 strict mode (0.85 Jaccard bigram threshold) is the production guardrail being tested.

## Anchor Service

- **File**: `backend/app/services/omop_hierarchy_service.py`
- **Class**: `OMOPHierarchyService`
- **Methods under test**: `_string_fallback_match()`, `_compute_string_similarity()`, `check_hierarchy_match()`

## Test File

- `backend/tests/test_omop_hierarchy_guardrails.py`

## Corpus File

- `backend/tests/fixtures/omop_guardrail_corpus.py`

## Pair Categories

### Section 1: False-Positive Pairs (MUST REJECT) — 12 pairs

| Category | Count | Examples |
|---|---|---|
| Unsafe medication near-matches | 6 | metformin/metronidazole, hydralazine/hydroxyzine, carboplatin/carbamazepine, prednisone/prednisolone, clonidine/clonazepam, vincristine/vinblastine |
| Condition word-overlap false positives | 5 | type 1/type 2 diabetes, pulmonary/essential hypertension, SCLC/NSCLC, acute/chronic pancreatitis, CKD/PKD |
| Ambiguous single-token overlap | 1 | chest pain/chest tube |

### Section 2: Must-Accept Pairs (Exact Matches) — 6 pairs

Exact string matches that must always be accepted regardless of mode: pneumonia, essential hypertension, type 2 diabetes mellitus, aspirin, acute myocardial infarction, serum creatinine.

### Section 3: Similarity Boundary Cases — 6 cases

Tests around the 0.85 Jaccard bigram threshold: identical strings (1.0), empty strings (0.0), single-char mismatch (0.0), dangerous drug pairs (< 0.40), corticosteroid pairs (0.30-0.75), near-match with qualifier (< 0.85).

## Similarity Threshold Justification

The 0.85 Jaccard bigram threshold was selected in P1-008 to:
1. Accept exact and near-exact matches (score 1.0)
2. Reject all dangerous medication near-matches (highest observed: prednisone/prednisolone at ~0.65)
3. Reject condition word-overlap pairs that share significant tokens but refer to clinically distinct entities
4. Provide a safety margin above the highest observed false-positive score

## Test Coverage Matrix

| Test Class | Tests | What it validates |
|---|---|---|
| `TestComputeStringSimilarity` | 7 | Static method correctness, boundary scores, edge cases |
| `TestStringFallbackMatchStrict` | ~18 | Each false-positive pair rejected, exact matches accepted, strict-mode contract |
| `TestStringFallbackMatchNonStrict` | 4 | Non-strict mode permits substring/word-overlap (two-mode contract) |
| `TestPrecisionGuardrailCorpus` | 4 | Sweep all corpus sections, minimum corpus size guard |
| `TestCheckHierarchyMatchFallback` | 4 | Public API delegates to fallback when Neo4j absent |

## Relationship to P1-010

This corpus **extends** the P1-010 acceptance corpus (`backend/tests/fixtures/omop_acceptance_corpus.py`). P1-010 validates the mapping pipeline end-to-end. This corpus validates the fallback matching path in isolation with pairs specifically chosen for patient-safety risk.
