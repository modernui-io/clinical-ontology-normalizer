# OpenEHR Reconciliation and Rollback Procedure

**Document ID**: OPS-P0-019
**Version**: 2.0
**Effective Date**: 2026-02-16
**Owner**: CIO + Operations
**Classification**: Internal — Operational

## Purpose

Define the reconciliation workflow and rollback procedure for OpenEHR data imports before live patient onboarding. This ensures any data transformation errors can be identified, isolated, and reversed without data loss or clinical impact.

## Scope

Applies to all OpenEHR COMPOSITION imports from Meditech (or any future EHR source) into the OMOP-normalized ClinicalFact store and Knowledge Graph.

## Pre-Onboarding Reconciliation Checklist

### 1. Contract Validation

- [ ] Verify canonical contract signature matches `MEDITECH_CANONICAL_CONTRACT_SIGNATURE`
- [ ] Confirm contract version matches expected (`1.0.0`)
- [ ] Validate all archetype mappings resolve to known `ARCHETYPE_DOMAIN_MAP` entries
- [ ] Run `GET /api/v1/openehr/archetypes` and confirm all 12 standard archetypes listed

### 2. Dry-Run Import

Use the **dry-run endpoint** to validate imports without persisting any data:

```bash
# Dry-run a composition — returns stats without committing to DB
curl -X POST https://api.internal/api/v1/openehr/dry-run \
  -H "Content-Type: application/json" \
  -d '{
    "composition": { ... },
    "patient_id": "dry-run-test-001",
    "source_metadata": {
      "source_system": "meditech",
      "site_id": "AU-MEL-ROYAL",
      "pipeline_id": "pipeline-aus-prod-01"
    }
  }'
```

- [ ] Select 5 representative Meditech encounters (mixed domains)
- [ ] Dry-run each via `POST /api/v1/openehr/dry-run` with `source_metadata` including site ID
- [ ] Record import stats from response (conditions, medications, measurements, procedures, allergies)
- [ ] Compare against manually counted expected values
- [ ] Verify all dry-runs return `success: true` with expected counts
- [ ] Confirm no rows persisted in DB after dry-run (savepoint rollback)

### 3. Round-Trip Verification

Use the **reconciliation endpoint** to programmatically validate round-trip integrity:

```bash
# After a real import, run reconciliation to verify round-trip integrity
curl -X POST https://api.internal/api/v1/openehr/reconcile/{patient_id}
```

The reconciliation endpoint:
1. Reads existing facts for the patient
2. Exports them to a COMPOSITION
3. Re-imports the export via dry-run
4. Compares row counts + content hashes (SHA-256 fingerprint)
5. Returns a `ReconciliationReport` with `match: true/false` and mismatch details

- [ ] Import test encounters via `POST /api/v1/openehr/composition`
- [ ] Run `POST /api/v1/openehr/reconcile/{patient_id}` for each
- [ ] Confirm `match: true` and zero mismatches in all reports
- [ ] Record `import_fingerprint` and `export_reimport_fingerprint` — they should be identical
- [ ] Spot-check 3 entries for correct DV_CODED_TEXT/DV_QUANTITY/DV_DATE_TIME

### 4. KG Integrity Check

- [ ] Verify patient KGNode created with correct `patient_id`
- [ ] Verify condition/drug/measurement KGNodes linked via correct EdgeTypes
- [ ] Confirm no orphaned nodes (nodes without edges to patient)

## Rollback Procedure

### Trigger Conditions

Rollback is initiated when any of the following occur:

1. Import produces incorrect domain assignments (condition mapped as drug, etc.)
2. Lineage chain is missing or incomplete
3. Duplicate facts created for same source entry
4. Code system normalization produces wrong mappings
5. Import statistics diverge >10% from manual count
6. Reconciliation endpoint reports `match: false`

### Step 1: Stop Ingest

```bash
# Disable OpenEHR import endpoint
curl -X POST https://api.internal/admin/feature-flags \
  -d '{"openehr_import_enabled": false}'
```

### Step 2: Execute Batch Rollback

Use the **rollback endpoint** instead of manual SQL:

```bash
# Roll back all OpenEHR imports for a patient within a time window
curl -X POST https://api.internal/api/v1/openehr/rollback \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "affected-patient-001",
    "batch_start": "2026-02-16T00:00:00Z",
    "batch_end": "2026-02-16T23:59:59Z"
  }'
```

The rollback endpoint:
1. Identifies affected ClinicalFacts via lineage (`source_type=openehr_import`)
2. Soft-deletes facts (preserves audit trail via `SoftDeleteMixin`)
3. Soft-deletes KG edges referencing those facts
4. Soft-deletes KG nodes that were targets of those edges (preserves patient node)
5. Returns a `RollbackResponse` with counts of deleted entities

Response example:
```json
{
  "patient_id": "affected-patient-001",
  "success": true,
  "facts_deleted": 9,
  "nodes_deleted": 9,
  "edges_deleted": 9
}
```

### Step 3: Verify Rollback

Run the reconciliation endpoint to confirm zero residual data:

```bash
# Verify no active facts remain from the rolled-back batch
curl -X POST https://api.internal/api/v1/openehr/reconcile/{patient_id}
# Should return match: false with "No facts found for patient"
```

Additionally, the rollback service includes a `verify_rollback()` method that confirms zero remaining active facts/nodes/edges from the batch.

### Step 4: Root Cause Analysis

- [ ] Identify which contract mapping or code path caused the error
- [ ] Create regression test reproducing the failure
- [ ] Fix and deploy updated contract/service
- [ ] Re-run dry-run reconciliation before re-enabling imports

### Step 5: Re-Enable

```bash
curl -X POST https://api.internal/admin/feature-flags \
  -d '{"openehr_import_enabled": true}'
```

## Dry-Run Evidence Template

| Field | Value | API Command |
|---|---|---|
| Date | | |
| Operator | | |
| Contract Version | | `GET /api/v1/openehr/archetypes` |
| Contract Signature | | Check lineage chain in response |
| Sample Size | | |
| Dry-Run Results | | `POST /api/v1/openehr/dry-run` |
| Expected Facts | | |
| Actual Facts | | From dry-run response |
| Match | YES / NO | Compare expected vs actual |
| Lineage Verified | YES / NO | Check `source_metadata` in dry-run |
| Round-Trip Verified | YES / NO | `POST /api/v1/openehr/reconcile/{patient_id}` |
| Round-Trip Fingerprint Match | YES / NO | `match` field in reconciliation response |
| Rollback Tested | YES / NO | `POST /api/v1/openehr/rollback` (on test data) |
| Approval | | |

## API Endpoint Reference (P0-019)

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v1/openehr/dry-run` | POST | Dry-run import — same payload as `/composition`, returns stats without persisting |
| `/api/v1/openehr/reconcile/{patient_id}` | POST | Round-trip reconciliation — compares import vs export-reimport fingerprints |
| `/api/v1/openehr/rollback` | POST | Batch rollback — soft-deletes facts/nodes/edges for patient + time range |

## Schedule

- Pre-pilot: Full reconciliation with 5+ encounters using dry-run endpoint
- Weekly during pilot: Spot-check 2 encounters with full reconciliation endpoint
- Monthly post-pilot: Automated reconciliation via canary tests + rollback drill
