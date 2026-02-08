# Regeneron Demo API Test Results

**Date**: 2026-02-08
**Backend**: http://localhost:8000
**Tester**: api-tester agent

## Summary

| # | Endpoint | Method | Status | Result |
|---|----------|--------|--------|--------|
| 1 | `/api/v1/trials` | GET | 200 | PASS |
| 2 | `/api/v1/trials/stats` | GET | 200 | PASS |
| 3 | `/api/v1/trials/bulk-screen` | POST | 200 | PASS (with note) |
| 4 | `/api/v1/screening-results` | GET | 200 | PASS (empty - results not persisted) |
| 5 | `/api/v1/sites` | GET | 200 | PASS |
| 6 | `/api/v1/sites/{id}/screening-summary` | GET | 200 | PASS (after bug fix) |
| 7 | `/api/v1/trials/dual-enrollment-candidates` | POST | 200 | PASS |
| 8 | `/api/v1/dashboard/roi-summary` | GET | 200 | PASS (empty - depends on persisted screening) |

**Overall**: 8/8 endpoints returning 200. 1 bug found and fixed. 2 data-dependency notes.

---

## Detailed Results

### 1. GET /api/v1/trials

**Status**: 200 OK

All 3 Regeneron trials returned correctly:

| Trial | NCT | Phase | Status | Therapeutic Area | Enrollment |
|-------|-----|-------|--------|-----------------|------------|
| EYLEA HD - Aflibercept for DME | NCT04429503 | Phase 3 | Recruiting | Ophthalmology | 2/900 |
| LIBERTY ADCHRONOS - Dupilumab for AD | NCT02395133 | Phase 3 | Recruiting | Dermatology | 2/600 |
| LIBTAYO - Cemiplimab for CSCC | NCT02760498 | Phase 3 | Recruiting | Oncology | 2/200 |

### 2. GET /api/v1/trials/stats

**Status**: 200 OK

```json
{
  "total_trials": 3,
  "trials_by_status": {"recruiting": 3},
  "total_enrolled_patients": 6
}
```

Data looks correct: 3 trials, all recruiting, 6 total enrolled patients (2 per trial from seeded data).

### 3. POST /api/v1/trials/bulk-screen

**Status**: 200 OK (after correction)

**Note**: The task description said `"trial_ids": []` (empty) should screen against all active trials. However, the endpoint validation requires at least 1 trial ID (`min_length=1`). Had to provide all 3 trial IDs explicitly.

**Request body used**:
```json
{
  "patient_ids": [
    "metriport-019c3e38-61b4-7b3d-8ebf-bf5be0e08757",
    "metriport-019c3e38-5df6-7c09-b338-e102316bfefa",
    "metriport-019c3e38-51b0-7f53-8174-ae769b005597"
  ],
  "trial_ids": [
    "00000000-de00-0001-0000-000000000001",
    "00000000-de00-0002-0000-000000000002",
    "00000000-de00-0003-0000-000000000003"
  ]
}
```

**Results summary**:
- 3 patients x 3 trials = 9 pairs screened
- 0 eligible (0% pass rate)
- Screening duration: ~297ms
- All 3 patients met "Adult patients" inclusion criterion
- Andreas Brown (metriport-...-bf5be0e08757) partially matched EYLEA HD (score 0.455) with "Adult patients" + "Type 2 Diabetes" met
- Missing data flags: DME, AD, and CSCC diagnoses not found in Metriport patient records

**Suggestion**: Consider making `trial_ids: []` mean "screen all active trials" to match the documented behavior.

### 4. GET /api/v1/screening-results

**Status**: 200 OK

```json
{"results": [], "total": 0, "offset": 0, "limit": 50}
```

Results are empty even after running bulk-screen. The bulk-screen endpoint returns results inline but does not persist them to the screening_results table.

**Suggestion**: The bulk-screen endpoint should persist ScreeningResult records so the `/screening-results` and `/dashboard/roi-summary` endpoints have data to work with.

### 5. GET /api/v1/sites

**Status**: 200 OK

All 3 sites returned correctly:

| Site | Code | Organization | City | State |
|------|------|-------------|------|-------|
| Columbia Dermatology Associates | COLUMBIA-DERM-001 | Columbia University Irving Medical Center | New York | NY |
| Emory Eye Center | EMORY-EYE-001 | Emory Healthcare | Atlanta | GA |
| Mount Sinai Internal Medicine | MSINAI-IM-001 | Icahn School of Medicine at Mount Sinai | New York | NY |

### 6. GET /api/v1/sites/{site_id}/screening-summary

**Status**: 200 OK (after bug fix)

**Bug found and fixed**: `AttributeError: 'PatientEligibility' object has no attribute 'is_eligible'`
- **File**: `backend/app/api/sites.py`, line 294
- **Cause**: Code used `eligibility.is_eligible` but the `PatientEligibility` schema field is named `eligible`
- **Fix**: Changed `eligibility.is_eligible` to `eligibility.eligible`

**After fix**, all 3 sites return valid responses:

| Site | Total Patients | Screened | Matched | Trial Matches |
|------|---------------|----------|---------|---------------|
| Emory Eye Center | 1 | 1 | 0 | [] |
| Columbia Dermatology Associates | 1 | 1 | 0 | [] |
| Mount Sinai Internal Medicine | 1 | 1 | 0 | [] |

Each site has 1 patient (from seeded data) but no matches since Metriport patients lack the specific diagnoses required.

### 7. POST /api/v1/trials/dual-enrollment-candidates

**Status**: 200 OK

```
Summary:
- 11 enrolled patients checked
- 11 patients with additional matches
- 19 total additional match opportunities
- 3 trials checked
- Screening duration: ~309ms
```

Returns cross-trial matching for all currently enrolled patients (from seeded enrollment data). Each enrolled patient gets screened against other trials. No patients are flagged as eligible for additional trials (all match_scores < 0.5), but the endpoint correctly identifies potential candidates for clinician review.

### 8. GET /api/v1/dashboard/roi-summary

**Status**: 200 OK

**Query params**: `conversion_rate=0.15&screening_cost=1.0&enrollment_value=50000`

All metrics are zero because screening results are not persisted (see #4 above):

```json
{
  "screening_overview": {
    "total_screenings": 0,
    "total_patients_screened": 0,
    "overall_pass_rate": 0.0
  },
  "projected_enrollment": {
    "eligible_patients": 0,
    "conversion_rate": 0.15,
    "projected_enrollments": 0
  },
  "cost_analysis": {
    "patients_screened": 0,
    "screening_cost_per_patient": 1.0,
    "total_screening_cost": 0.0,
    "roi_ratio": null
  }
}
```

**Suggestion**: Once bulk-screen persists results, this endpoint should populate with meaningful ROI data.

---

## Bugs Found

### BUG-1: `is_eligible` attribute error in site screening summary (FIXED)

- **Severity**: High (500 error on every site screening summary request)
- **File**: `backend/app/api/sites.py:294`
- **Error**: `AttributeError: 'PatientEligibility' object has no attribute 'is_eligible'. Did you mean: 'eligible'?`
- **Fix applied**: Changed `eligibility.is_eligible` to `eligibility.eligible`

## Issues / Improvement Suggestions

### ISSUE-1: Bulk screen requires explicit trial_ids (not critical)

The `trial_ids` field has `min_length=1` validation, so passing `[]` returns 422. The task description suggests `[]` should mean "screen all active trials."

**Suggestion**: Allow empty `trial_ids` to default to all active/recruiting trials.

### ISSUE-2: Bulk screen does not persist screening results

The `/api/v1/trials/bulk-screen` endpoint returns results inline but does not write `ScreeningResult` records to the database. This means:
- `/api/v1/screening-results` always returns empty
- `/api/v1/dashboard/roi-summary` has no data to compute metrics from

**Suggestion**: Add persistence logic to the bulk-screen flow so downstream endpoints have data.

### ISSUE-3: Metriport patients lack condition-specific data

All 3 Metriport patients are flagged as adults but lack the specific diagnoses (DME, Atopic Dermatitis, CSCC) needed for trial matching. This is expected since they are real patient records, but for demo purposes it may be useful to have at least one patient match a trial.
