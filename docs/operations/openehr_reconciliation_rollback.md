# OpenEHR Reconciliation and Rollback Procedure

**Document ID**: OPS-P0-019
**Version**: 1.0
**Effective Date**: 2026-02-15
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

- [ ] Select 5 representative Meditech encounters (mixed domains)
- [ ] Import via `POST /api/v1/openehr/composition` with `source_metadata` including site ID
- [ ] Record import stats (conditions, medications, measurements, procedures, allergies)
- [ ] Compare against manually counted expected values
- [ ] Verify lineage chain includes `meditech_to_openehr_adapter` step with contract signature

### 3. Round-Trip Verification

- [ ] Export imported facts via `POST /api/v1/openehr/export/{patient_id}`
- [ ] Validate exported COMPOSITION has valid RM structure
- [ ] Confirm all entries have `archetype_node_id` starting with `openEHR-EHR-`
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

### Step 1: Stop Ingest

```bash
# Disable OpenEHR import endpoint
curl -X POST https://api.internal/admin/feature-flags \
  -d '{"openehr_import_enabled": false}'
```

### Step 2: Identify Affected Records

```sql
-- Find all ClinicalFacts from the affected import batch
SELECT cf.id, cf.domain, cf.display_name, cf.patient_id, cf.created_at
FROM clinical_facts cf
JOIN data_lineage dl ON dl.fact_id = cf.id
WHERE dl.source_type = 'openehr_import'
  AND dl.created_at >= '{batch_start_time}'
  AND dl.created_at <= '{batch_end_time}';
```

### Step 3: Archive Before Delete

```sql
-- Archive affected facts to rollback table
INSERT INTO clinical_facts_rollback
SELECT * FROM clinical_facts
WHERE id IN (SELECT fact_id FROM data_lineage
             WHERE source_type = 'openehr_import'
             AND created_at >= '{batch_start_time}');

-- Archive affected KG nodes
INSERT INTO kg_nodes_rollback
SELECT * FROM kg_nodes
WHERE patient_id IN (SELECT DISTINCT patient_id FROM clinical_facts
                     WHERE id IN (SELECT fact_id FROM data_lineage
                                  WHERE source_type = 'openehr_import'
                                  AND created_at >= '{batch_start_time}'));
```

### Step 4: Remove Affected Data

```sql
-- Remove in reverse dependency order
DELETE FROM kg_edges WHERE source_node_id IN (SELECT id FROM kg_nodes_rollback);
DELETE FROM kg_nodes WHERE id IN (SELECT id FROM kg_nodes_rollback);
DELETE FROM data_lineage WHERE fact_id IN (SELECT id FROM clinical_facts_rollback);
DELETE FROM clinical_facts WHERE id IN (SELECT id FROM clinical_facts_rollback);
```

### Step 5: Verify Rollback

```sql
-- Confirm zero affected records remain
SELECT COUNT(*) FROM data_lineage
WHERE source_type = 'openehr_import'
  AND created_at >= '{batch_start_time}'
  AND created_at <= '{batch_end_time}';
-- Expected: 0
```

### Step 6: Root Cause Analysis

- [ ] Identify which contract mapping or code path caused the error
- [ ] Create regression test reproducing the failure
- [ ] Fix and deploy updated contract/service
- [ ] Re-run dry-run reconciliation before re-enabling imports

### Step 7: Re-Enable

```bash
curl -X POST https://api.internal/admin/feature-flags \
  -d '{"openehr_import_enabled": true}'
```

## Dry-Run Evidence Template

| Field | Value |
|---|---|
| Date | |
| Operator | |
| Contract Version | |
| Contract Signature | |
| Sample Size | |
| Expected Facts | |
| Actual Facts | |
| Match | YES / NO |
| Lineage Verified | YES / NO |
| Round-Trip Verified | YES / NO |
| Approval | |

## Schedule

- Pre-pilot: Full reconciliation with 5+ encounters
- Weekly during pilot: Spot-check 2 encounters with full lineage audit
- Monthly post-pilot: Automated reconciliation via canary tests
