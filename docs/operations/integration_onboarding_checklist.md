# External Integration Onboarding Checklist

**Document ID**: OPS-P1-030
**Version**: 1.0
**Effective Date**: 2026-02-15
**Owner**: CIO + Interoperability
**Classification**: Internal — Operational

## Purpose

Mandatory checklist for onboarding each new external integration (EHR system, data source, or partner). Ensures data contracts, validation, and rollback procedures are in place before any live data flows.

## Pre-Onboarding (Before Any Data)

### 1. Contract and Governance

- [ ] Data sharing agreement executed
- [ ] Data processing addendum signed (if PHI)
- [ ] Integration point-of-contact identified (both sides)
- [ ] Escalation path defined
- [ ] SLA for data delivery and support agreed

### 2. Technical Specification

- [ ] Source data format documented (HL7v2, FHIR, OpenEHR, CSV, etc.)
- [ ] Field mapping specification published
- [ ] Code system mapping defined (ICD-10, SNOMED, LOINC, RxNorm variants)
- [ ] Sample data provided (minimum 10 representative records)
- [ ] Authentication method agreed (API key, OAuth, mTLS)
- [ ] Network connectivity verified (VPN, allow-listing, etc.)

### 3. Connector Implementation

- [ ] Connector class created extending `SourceConnector` base
- [ ] Config schema defined (endpoint, auth, timeouts, page size)
- [ ] SSRF protection validated (no private IP access)
- [ ] Error handling for all failure modes
- [ ] Rate limiting configured
- [ ] Unit tests passing

### 4. Mapping Contract

- [ ] Canonical mapping contract created (see P0-018 pattern)
- [ ] Contract ID and version assigned
- [ ] Code system normalization rules defined
- [ ] Exception policy documented (reject, normalize, manual review)
- [ ] Contract signature (deterministic hash) generated
- [ ] Lineage step builder implemented

## Validation Phase (Staging)

### 5. Sample Replay

- [ ] Import sample records via connector
- [ ] Verify ClinicalFact domain assignments correct
- [ ] Verify OMOP concept mapping accuracy (spot-check 10 records)
- [ ] Verify KG structure (patient nodes, edges, types)
- [ ] Verify lineage chain complete (source → transform → fact)
- [ ] Run deterministic replay test (same input → same output)
- [ ] Record replay results as evidence

### 6. Round-Trip Verification (if export supported)

- [ ] Export imported facts back to source format
- [ ] Validate exported structure matches source format spec
- [ ] Compare key fields (codes, values, dates) for fidelity
- [ ] Document any expected transformation losses

### 7. Edge Cases

- [ ] Test with empty/missing fields
- [ ] Test with unknown code systems
- [ ] Test with duplicate records
- [ ] Test with malformed input
- [ ] Test with maximum payload size
- [ ] All edge cases handled without crash

## Go-Live Checklist

### 8. Monitoring

- [ ] Health check covers new connector
- [ ] Alert routing configured for connector failures
- [ ] Dashboard includes connector metrics (volume, errors, latency)
- [ ] Reconciliation schedule defined (daily/weekly)

### 9. Rollback Readiness

- [ ] Rollback procedure documented (see P0-019 pattern)
- [ ] Feature flag to disable connector without deployment
- [ ] Archive/delete queries prepared for affected data range
- [ ] Recovery tested in staging

### 10. Final Approval

- [ ] Interoperability Lead sign-off
- [ ] Data Integrity Lead sign-off
- [ ] Operations Lead sign-off
- [ ] Compliance sign-off (if PHI)

## Evidence Record

| Field | Value |
|---|---|
| Integration Name | |
| Source System | |
| Connector Type | |
| Onboarding Date | |
| Sample Size Validated | |
| Replay Results | PASS / FAIL |
| Round-Trip Verified | YES / NO / N/A |
| Go-Live Approved | YES / NO |
| Approved By | |
