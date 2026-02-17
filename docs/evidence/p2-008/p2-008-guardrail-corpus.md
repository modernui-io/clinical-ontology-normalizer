# P2-008 UMLS/OMOP Precision Guardrail Corpus

**ROL-08** | **Date**: 2026-02-17 | **Owner**: Clinical AI + QA

## Purpose

This corpus validates that `OMOPHierarchyService._string_fallback_match()` correctly rejects clinically dangerous near-matches when Neo4j is unavailable and the service falls back to string similarity. The P1-008 strict mode (0.85 Jaccard bigram threshold) is the production guardrail being tested.

## Anchor Service

- **File**: `backend/app/services/omop_hierarchy_service.py`
- **Class**: `OMOPHierarchyService`
- **Methods under test**: `_string_fallback_match()`, `_compute_string_similarity()`, `check_hierarchy_match()`

## Test Files

- `backend/tests/test_omop_hierarchy_guardrails.py` — Unit tests for fallback matching (40 tests)
- `backend/tests/test_umls_omop_precision_guardrails.py` — Precision guardrail regression suite (39 tests: 32 unit + 7 integration/regression)

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

### Section 4: Ambiguous Mapping Pairs — 15 pairs

| Category | Count | Action | Examples |
|---|---|---|---|
| LASA drugs | 4 | reject | losartan→lisinopril, cephalexin→amoxicillin, hydroxychloroquine→ibuprofen, omeprazole→atorvastatin |
| Unqualified conditions | 3 | reject/flag | "diabetes"→T2DM, "hypertension"→essential, "anemia"→pneumonia |
| Abbreviation collisions | 3 | reject | MS→MI, PE→pneumonia, RA→hypertension |
| Specimen ambiguity | 2 | reject | urine glucose→HbA1c, urine sodium→serum creatinine |
| Cross-domain collisions | 3 | reject/downgrade | aspirin allergy→aspirin(Drug), insulin resistance→metformin(Drug), colonoscopy finding→colonoscopy(Proc) |

### Section 5: Per-Domain Positive Pairs — 30 pairs

| Domain | Count | Examples |
|---|---|---|
| medication | 8 | aspirin, metformin, lisinopril, atorvastatin, amoxicillin, omeprazole, ibuprofen, warfarin |
| condition | 8 | T2DM, essential hypertension, pneumonia, AMI, MDD, asthma, CKD, heart failure |
| procedure | 7 | CT, MRI, phlebotomy, colonoscopy, echo, CXR, EKG |
| measurement | 7 | CBC, BMP, HbA1c, lipid panel, creatinine, BUN, TSH |

### Section 6: Per-Domain Precision Thresholds

| Domain | Threshold | Justification |
|---|---|---|
| medication | 0.90 | Drug confusion is the most directly dangerous mapping error |
| condition | 0.80 | Condition misattribution may alter treatment decisions |
| procedure | 0.75 | Procedure mapping errors are lower-risk (clinical context usually disambiguates) |
| measurement | 0.80 | Lab misidentification can cause incorrect clinical interpretation |

## Reason Code Taxonomy

| Code | Meaning |
|---|---|
| `LASA_DRUG` | Look-Alike Sound-Alike drug confusion |
| `UNQUALIFIED_CONDITION` | Ambiguous condition lacking required qualifier |
| `ABBREVIATION_COLLISION` | Clinical abbreviation with multiple expansions |
| `SPECIMEN_AMBIGUITY` | Same analyte in different specimen contexts |
| `CROSS_DOMAIN_COLLISION` | Term exists in multiple OMOP domains |

## Test Coverage Matrix

### test_omop_hierarchy_guardrails.py (40 tests)

| Test Class | Tests | What it validates |
|---|---|---|
| `TestComputeStringSimilarity` | 7 | Static method correctness, boundary scores, edge cases |
| `TestStringFallbackMatchStrict` | ~18 | Each false-positive pair rejected, exact matches accepted, strict-mode contract |
| `TestStringFallbackMatchNonStrict` | 4 | Non-strict mode permits substring/word-overlap (two-mode contract) |
| `TestPrecisionGuardrailCorpus` | 4 | Sweep all corpus sections, minimum corpus size guard |
| `TestCheckHierarchyMatchFallback` | 4 | Public API delegates to fallback when Neo4j absent |

### test_umls_omop_precision_guardrails.py (39 tests)

| Test Class | Tests | Type | What it validates |
|---|---|---|---|
| `TestGuardrailCorpusStructure` | 13 | Unit | Corpus counts, tuple shapes, valid actions/reason codes, domain coverage, no overlap with acceptance corpus |
| `TestHierarchyFalsePositiveRejection` | 12 | Unit | Each false-positive pair rejected in strict mode |
| `TestSimilarityBoundary` | 6 | Unit | Similarity scores within expected ranges |
| `TestAmbiguousMappingHandling` | 2 | Integration | Reject pairs NOT returned as top match; downgrade pairs quality != "exact" |
| `TestDomainPrecisionGates` | 4 | Integration | Per-domain precision >= threshold (medication 0.90, condition 0.80, procedure 0.75, measurement 0.80) |
| `TestPrecisionDriftDetection` | 2 | Regression | Aggregate precision no-regression; false-positive count = 0 |

## Relationship to P1-010

This corpus **extends** the P1-010 acceptance corpus (`backend/tests/fixtures/omop_acceptance_corpus.py`). P1-010 validates the mapping pipeline end-to-end. This corpus validates the fallback matching path in isolation with pairs specifically chosen for patient-safety risk. The precision guardrail test file adds per-domain precision gates and drift detection on top of the base corpus.
