# P4-009-I: Specialty Guideline Ingestion Framework

**Task:** P4-009-I (Implementation Plan)
**Date:** 2026-02-17
**Operator:** autonomous-agent
**Status:** Framework design complete (deferred activation per ADR)
**ADR Reference:** `docs/decisions/p4-009-guideline-corpus.md`

## Summary

This document defines the implementation plan for specialty guideline corpus expansion with editorial governance. Activation begins post-pilot with General Internal Medicine, then expands through the priority queue (Cardiology, Oncology, Nephrology, Endocrinology). No specialty expansion occurs during initial pilot. The guideline RAG service already supports multi-specialty retrieval; the work is corpus curation, governance, and validation -- not code changes.

---

## 1. Current State Assessment

### guideline_rag_service.py (535 lines)

| Capability | Status | Notes |
|-----------|--------|-------|
| Semantic search over guideline sections | Implemented | Embedding-based similarity with keyword boosting |
| OMOP hierarchy expansion | Implemented | Patient condition "Type 2 diabetes mellitus" matches "diabetes" via IS_A traversal |
| Patient context integration | Implemented | Conditions, medications, and measurements used for retrieval context |
| Multi-specialty corpus support | Architecturally ready | No code changes needed to add specialty-scoped guidelines |
| Singleton pattern | Implemented | Thread-safe initialization consistent with VocabularyService |

### guideline_version_service.py (407 lines)

| Capability | Status | Notes |
|-----------|--------|-------|
| Lifecycle status tracking | Implemented | `GuidelineStatus` enum: CURRENT, STALE, EXPIRED, SUPERSEDED |
| Metadata model | Implemented | `GuidelineMetadata` dataclass with id, title, version, source_org, published_date, expiry_date, superseded_by |
| Bulk freshness scan (P3-013) | Implemented | `check_all_guidelines_freshness()` scans entire corpus |
| Approaching-stale detection (P3-013) | Implemented | `get_guidelines_needing_review()` flags guidelines within 90 days of staleness |
| Alert generation (P3-013) | Implemented | `GuidelineAlert` model with `GuidelineAlertType` enum (APPROACHING_STALE, STALE, EXPIRED) |
| Configurable staleness threshold | Implemented | `GUIDELINE_STALENESS_DAYS` env var, default 730 days |
| Expiry threshold | Implemented | 1825 days (5 years) hard expiry |

### Prerequisite Tickets

| Ticket | Description | Status |
|--------|------------|--------|
| P1-012 | Guideline corpus versioning | Closed |
| P3-013 | Stale guideline detection | Closed |

**Assessment:** Infrastructure is complete. The gap is corpus content (specialty-specific guidelines) and governance process (editorial board), not code.

---

## 2. Specialty Guideline Ingestion Pipeline Design

### 2.1 Pipeline Architecture

```
Source Guideline Document
        |
        v
+---------------------+
| Source Acquisition   |  (download from NICE, AHA/ACC, NCCN, KDIGO, ADA, etc.)
+--------+------------+
         |
+--------v------------+
| Intake + Metadata    |  (source org, pub date, version, evidence grade, specialty)
+--------+------------+
         |
+--------v------------+
| Structured Parse     |  (sections, recommendations, evidence levels per section)
+--------+------------+
         |
+--------v------------+
| OMOP Concept Link    |  (condition -> OMOP, drug -> OMOP, procedure -> OMOP)
+--------+------------+
         |
+--------v------------+
| Coverage Scoring     |  (% of specialty conditions covered, gap identification)
+--------+------------+
         |
+--------v------------+
| Quality Validation   |  (domain expert spot-check, inter-rater reliability)
+--------+------------+
         |
+--------v------------+
| Editorial Board      |  (sign-off required before corpus entry)
| Approval             |
+--------+------------+
         |
+--------v------------+
| Corpus Publish       |  (versioned, searchable via guideline_rag_service.py)
+---------------------+
```

### 2.2 Source Acquisition Workflow

| Step | Action | Responsible | Output |
|------|--------|-------------|--------|
| 1 | Identify authoritative guideline organizations for target specialty | Domain Expert | Source organization list |
| 2 | Verify licensing and copyright terms for each source | Compliance Representative | Licensing clearance register |
| 3 | Download current guideline documents (PDF, HTML, structured XML where available) | Ingestion Operator | Raw guideline archive |
| 4 | Verify document authenticity (URL, checksum, publication metadata) | Ingestion Operator | Authenticity log |
| 5 | Extract machine-readable content (text, sections, tables) | Ingestion Pipeline | Structured guideline content |
| 6 | Tag with structured metadata per schema below | Ingestion Pipeline | Metadata-tagged guideline |

**Per-Specialty Source Organizations:**

| Specialty | Primary Sources | Secondary Sources |
|-----------|----------------|-------------------|
| General Internal Medicine | NICE, ACP, UpToDate | RACGP, WHO |
| Cardiology | AHA/ACC, ESC | CSANZ, HFSA |
| Oncology | NCCN, ESMO, ASCO | Cancer Australia, NICE (cancer) |
| Nephrology | KDIGO | KHA-CARI, NICE (renal) |
| Endocrinology | ADA, Endocrine Society | ADEA, NICE (diabetes/endocrine) |

### 2.3 Structured Metadata Schema

Every ingested guideline carries the following metadata:

```json
{
  "guideline_id": "uuid",
  "title": "string",
  "source_organization": "string (e.g., AHA, NICE, NCCN)",
  "publication_date": "date",
  "version": "string (e.g., 2025.1)",
  "evidence_grade": "enum (A|B|C|D|expert_opinion)",
  "specialty": "enum (general_im|cardiology|oncology|nephrology|endocrinology)",
  "condition_omop_ids": ["int (OMOP condition concept IDs)"],
  "drug_omop_ids": ["int (OMOP drug concept IDs)"],
  "procedure_omop_ids": ["int (OMOP procedure concept IDs)"],
  "supersedes_id": "uuid | null (guideline this version replaces)",
  "review_status": "enum (pending_review|reviewed|approved|rejected)",
  "sections": [
    {
      "section_id": "uuid",
      "title": "string",
      "content_hash": "sha256",
      "recommendation_count": "int",
      "evidence_level": "enum (I|IIa|IIb|III per ACC/AHA or equivalent)"
    }
  ],
  "ingested_at": "datetime",
  "ingested_by": "string (operator ID)",
  "reviewed_by": "string (domain expert name)",
  "approved_by": "string (editorial board approver)",
  "approved_at": "datetime",
  "expires_at": "datetime (computed from expiry policy)",
  "status": "enum (draft|approved|active|stale|superseded|retired)"
}
```

**Fields added beyond ADR baseline:** `specialty`, `evidence_grade`, `supersedes_id`, `review_status`. These support the versioning integration and editorial governance workflow.

### 2.4 OMOP Concept Linkage Strategy

Each guideline is linked to OMOP concepts at three levels:

| Concept Domain | Linkage Method | Validation |
|---------------|----------------|------------|
| Condition | Semantic search via `guideline_rag_service.py` against OMOP condition vocabulary, confirmed by domain expert | Expert reviews top-5 suggested mappings |
| Drug | Lookup via `omop_hierarchy_service.py` drug concept hierarchy, matching guideline drug names to RxNorm/OMOP | Automated exact-match + expert review of fuzzy matches |
| Procedure | Manual mapping by domain expert for procedure-specific guidelines (e.g., PCI, dialysis) | Expert assigns OMOP procedure concept IDs |

**Coverage score formula:**

```
Coverage Score = (# OMOP conditions with >=1 active guideline) / (# total OMOP conditions in specialty set)
```

**Per-specialty target coverage:**

| Specialty | Target Coverage | Rationale |
|-----------|----------------|-----------|
| General IM | >80% | Broad, high guideline availability from NICE/ACP |
| Cardiology | >75% | Well-covered by AHA/ACC/ESC consensus guidelines |
| Oncology | >60% | Rapidly evolving, many tumor types, lower achievable coverage |
| Nephrology | >85% | KDIGO provides comprehensive CKD/AKI coverage |
| Endocrinology | >70% | ADA comprehensive for diabetes; other endocrine areas less covered |

### 2.5 Versioning Integration with guideline_version_service.py

The ingestion pipeline writes to `GuidelineMetadata` using the existing version service infrastructure:

| Lifecycle State | Trigger | Service Method |
|----------------|---------|---------------|
| `draft` | Guideline ingested but not yet reviewed | New entry created in corpus metadata |
| `active` (CURRENT) | Editorial board approves guideline | Status updated to CURRENT via version service |
| `superseded` (SUPERSEDED) | New version of same guideline approved | Old version marked SUPERSEDED, `superseded_by` populated |
| `stale` (STALE) | Age exceeds staleness threshold | Detected by `check_all_guidelines_freshness()` |
| `expired` (EXPIRED) | Age exceeds expiry threshold | Detected by `check_all_guidelines_freshness()` |
| `retired` | Board explicitly retires guideline | Status updated, guideline excluded from RAG active results |

**New states added by this framework:** `draft` and `retired` extend the existing `GuidelineStatus` enum. `draft` captures pre-approval state; `retired` captures explicit board-initiated removal distinct from age-based expiry.

### 2.6 Coverage Reporting Framework

Coverage reports are generated per specialty and presented to the editorial board:

```
Specialty Coverage Report
=========================
Specialty: Cardiology
Report Date: ________
Generated By: Coverage Scoring Pipeline

Total OMOP conditions in specialty set: ___
Conditions with >=1 active guideline: ___
Coverage Score: ___%

Gap Analysis:
  Conditions without guideline coverage:
    - [OMOP concept ID] [Concept name] [Severity/prevalence rank]
    - ...

Guideline Age Distribution:
  <1 year: ___ guidelines
  1-2 years: ___ guidelines
  2-3 years: ___ guidelines
  >3 years: ___ guidelines (flagged for review)

Source Distribution:
  AHA/ACC: ___ guidelines
  ESC: ___ guidelines
  Other: ___ guidelines
```

**Gap identification:** Uncovered OMOP condition concepts are ranked by clinical prevalence and severity to prioritize future guideline acquisition.

---

## 3. Editorial Governance Board Charter

### 3.1 Board Composition

| Role | Named Individual | Responsibility | Required for Quorum? |
|------|-----------------|----------------|---------------------|
| Clinical AI Lead (Chair) | TBD (assigned at activation) | Convenes board, final approval authority, maintains corpus quality standards | Yes |
| Domain Expert -- General IM | TBD | Reviews General IM guidelines for accuracy, completeness, clinical relevance | Yes (when IM on agenda) |
| Domain Expert -- Cardiology | TBD | Reviews Cardiology guidelines | Yes (when Cardiology on agenda) |
| Domain Expert -- Oncology | TBD | Reviews Oncology guidelines | Yes (when Oncology on agenda) |
| Domain Expert -- Nephrology | TBD | Reviews Nephrology guidelines | Yes (when Nephrology on agenda) |
| Domain Expert -- Endocrinology | TBD | Reviews Endocrinology guidelines | Yes (when Endocrinology on agenda) |
| Compliance Representative | TBD | Ensures licensing, copyright, regulatory alignment | Yes |
| VP Product (Observer) | TBD | Awareness of corpus changes affecting product capabilities | No (advisory only) |

### 3.2 Board Responsibilities

1. **Approve new guideline additions** -- verify source authority, version, scope, evidence grade
2. **Review stale guideline alerts** -- decide: update, confirm continued validity, or retire
3. **Sign off on coverage reports** -- per-specialty coverage and accuracy reports reviewed quarterly
4. **Approve retirement of superseded guidelines** -- ensure no active clinical path depends solely on retired guideline
5. **Approve specialty expansion** -- new specialty added to corpus only with board approval and assigned domain expert
6. **Maintain conflict-of-interest register** -- board members disclose relevant industry relationships annually

### 3.3 Meeting Cadence and Quorum Rules

| Frequency | Scope | Required Attendees | Quorum Rule |
|-----------|-------|--------------------|-------------|
| Monthly | Active specialties: new additions, stale alerts, coverage metrics | Chair + relevant domain expert(s) + Compliance | Chair + at least 1 domain expert + Compliance |
| Quarterly | All specialties: coverage report, accuracy spot-check results, expansion decisions | Full board + VP Product | Chair + at least 2 domain experts + Compliance |
| Ad-hoc | Urgent: adverse event linked to guideline, major guideline withdrawal | Chair + affected domain expert | Chair + affected domain expert |

### 3.4 Approval Workflow

```
New Guideline / Update / Retirement Request
        |
        v
  Ingestion Operator submits request with:
    - Guideline metadata (per schema)
    - Domain expert review summary
    - OMOP linkage report
    - Coverage impact assessment
        |
        v
  Domain Expert reviews (5 business days SLA)
    - Clinical accuracy
    - Evidence grade assignment
    - OMOP linkage verification
        |
        v
  Compliance Representative reviews (3 business days SLA)
    - Licensing/copyright clearance
    - Regulatory alignment
        |
        v
  Board vote at next scheduled meeting
    - APPROVED: guideline status -> active
    - APPROVED WITH CONDITIONS: conditions documented, re-review at next meeting
    - REJECTED: rejection reason documented, guideline status -> rejected
```

### 3.5 Conflict Resolution Process

1. If board cannot reach majority vote, Chair facilitates structured discussion with documented positions
2. If consensus still not reached, decision escalated to CTO + Medical Director for binding resolution
3. Escalation decisions are recorded with full rationale and appended to board meeting minutes
4. Any board member may request formal escalation at any point

### 3.6 Annual Charter Review

- Charter reviewed and reaffirmed (or amended) at the first quarterly meeting of each calendar year
- Amendments require majority board vote
- Charter version history maintained in `docs/governance/` directory

---

## 4. Expiry and Staleness Policy

### 4.1 Default Expiry by Guideline Type

| Guideline Type | Default Expiry Period | Staleness Alert Threshold | Rationale |
|---------------|----------------------|--------------------------|-----------|
| Clinical practice guideline (NICE, AHA/ACC, KDIGO) | 5 years from publication | 18 months before expiry | Major societies typically update every 3-5 years |
| Drug safety guideline / drug-specific recommendation | 2 years from publication | 6 months before expiry | Pharmacovigilance data evolves rapidly |
| Expert opinion / position paper | 3 years from publication | 12 months before expiry | Lower evidence grade, faster obsolescence |
| Rapidly evolving specialty (NCCN oncology) | 2 years from publication | 6 months before expiry | NCCN updates multiple times per year |

### 4.2 Stale Detection Integration with P3-013

The existing P3-013 infrastructure provides:

| P3-013 Component | Integration Point |
|------------------|-------------------|
| `check_all_guidelines_freshness()` | Bulk scan runs on configurable schedule (default: weekly) |
| `get_guidelines_needing_review()` | Flags guidelines within `APPROACHING_STALE_DAYS` (90 days) of threshold |
| `GuidelineAlert` model | Generates typed alerts: APPROACHING_STALE, STALE, EXPIRED |
| `GUIDELINE_STALENESS_DAYS` env var | Per-specialty override possible via specialty-specific config |

**New integration required at activation:** Route P3-013 alerts to editorial board notification channel (email digest or dashboard).

### 4.3 Owner Notification Workflow

| Alert Type | Notification Target | Action Required | SLA |
|-----------|-------------------|-----------------|-----|
| APPROACHING_STALE | Domain expert for affected specialty | Review guideline, confirm still current or initiate update | 30 days |
| STALE | Domain expert + Chair | Board decision: update, confirm, or retire | 30 days (grace period) |
| EXPIRED | Chair + Compliance | Mandatory retirement or emergency revalidation | 14 days |

### 4.4 Grace Period Before Auto-Retirement

- **Grace period:** 30 days from STALE alert to required board action
- **Auto-label:** If no action within grace period, guideline status automatically set to `stale` (still visible in RAG results but labeled with staleness warning)
- **Auto-retire:** If no action within 60 days of STALE alert, guideline status set to `retired` and excluded from active RAG results
- **Reinstatement:** Retired guidelines can be reinstated by board vote confirming continued clinical validity
- **Audit trail:** All auto-label and auto-retire events recorded with timestamp and reason

---

## 5. Per-Specialty Ingestion Timeline

All timelines are relative to activation date (post-pilot, post-editorial-board formation).

| Phase | Specialty | Timeline | Corpus Size | Key Activities |
|-------|----------|----------|-------------|---------------|
| 1 | General Internal Medicine | Month 1-2 | ~200 guidelines | Source from NICE, ACP, UpToDate; broadest coverage; establishes ingestion process baseline |
| 2 | Cardiology | Month 3-4 | ~150 guidelines | Source from AHA/ACC, ESC; high-risk specialty; validates cross-specialty RAG quality |
| 3 | Oncology | Month 5-7 | ~300 guidelines | Source from NCCN, ESMO, ASCO; largest corpus; requires extended ingestion sprint due to volume |
| 4 | Nephrology | Month 8-9 | ~50 guidelines | Source from KDIGO; smaller corpus but high clinical risk (medication dosing) |
| 5 | Endocrinology | Month 10-11 | ~100 guidelines | Source from ADA, Endocrine Society; diabetes management breadth |

**Month 12:** Retrospective review of full corpus. Coverage gap analysis across all specialties. Board decides on Year 2 expansion priorities.

### Per-Specialty Expansion Process

1. **Domain expert assigned** -- Named individual with specialty credentials identified and confirmed
2. **Source guidelines identified** -- Comprehensive list from recognized organizations assembled
3. **Ingestion sprint** (2-4 weeks per specialty, 6 weeks for Oncology):
   - Batch ingest with metadata tagging per schema
   - OMOP concept linkage for each guideline
   - Coverage score computed against specialty OMOP condition set
4. **Quality validation** -- Domain expert spot-checks minimum 20 guidelines (or 10% of corpus, whichever is greater)
5. **Inter-rater reliability** -- Second reviewer spot-checks subset (10 guidelines minimum) for kappa measurement
6. **Board sign-off** -- Coverage and accuracy report presented to editorial board at next scheduled meeting
7. **Publish** -- Specialty corpus activated in `guideline_rag_service.py`

---

## 6. Quality Assurance Process

### 6.1 Domain Expert Spot-Check

| Parameter | Requirement |
|-----------|------------|
| Sample size | Minimum 20 guidelines per specialty (or 10% of corpus, whichever is greater) |
| Reviewer | Board-appointed domain expert with specialty credentials |
| Review scope | Clinical accuracy, evidence grade correctness, OMOP linkage validity, section completeness |
| Review SLA | 5 business days per batch of 20 guidelines |
| Documentation | Spot-check log with per-guideline pass/fail and comments |

### 6.2 Inter-Rater Reliability

| Parameter | Requirement |
|-----------|------------|
| Measurement | Cohen's kappa statistic |
| Target | kappa > 0.8 (substantial to almost perfect agreement) |
| Method | Two independent reviewers assess same 10-guideline subset per specialty |
| Dimensions rated | Evidence grade, OMOP condition linkage, clinical accuracy (binary: acceptable/not acceptable) |
| Remediation | If kappa < 0.8, reviewers calibrate criteria and re-assess until threshold met |

### 6.3 Automated Consistency Checks

| Check | Description | Automated? |
|-------|------------|-----------|
| Metadata completeness | All required fields populated (no nulls in required fields) | Yes |
| OMOP concept validity | All linked concept IDs exist in current OMOP vocabulary | Yes |
| Duplicate detection | No two active guidelines with identical title + source + version | Yes |
| Expiry date computation | `expires_at` correctly computed from `publication_date` + type-specific expiry period | Yes |
| Section hash integrity | `content_hash` matches actual section content (no silent corruption) | Yes |
| Supersedes chain validity | If `supersedes_id` is set, referenced guideline exists and is marked SUPERSEDED | Yes |

---

## 7. Quality Gate: Board Sign-Off Per Specialty

### Sign-Off Template

```
Specialty Corpus Sign-Off
=========================

Specialty: _______________
Domain Expert: _______________
Date: _______________

Metrics:
  Total guidelines ingested: ____
  OMOP concepts linked: ____
  Coverage score: ____%
  Coverage target: ____%
  Gap conditions identified: ____
  Spot-check sample size: ____
  Spot-check accuracy: ____%
  Inter-rater kappa: __.__
  Stale guidelines (>threshold): ____

Automated Consistency Checks:
  Metadata completeness: [ ] PASS  [ ] FAIL
  OMOP concept validity: [ ] PASS  [ ] FAIL
  Duplicate detection: [ ] PASS  [ ] FAIL
  Expiry computation: [ ] PASS  [ ] FAIL

Board Decision: [ ] APPROVED  [ ] APPROVED WITH CONDITIONS  [ ] REJECTED
Conditions (if any): _______________

Approvers:
  Clinical AI Lead: _____________ Date: _________
  Domain Expert: _____________ Date: _________
  Compliance: _____________ Date: _________
```

---

## 8. Activation Criteria Checklist

- [ ] Editorial board chartered with named members
- [ ] First domain expert (General IM) assigned
- [ ] Ingestion pipeline implemented and tested on sample guidelines
- [ ] Metadata schema validated against sample corpus (minimum 10 test guidelines)
- [ ] OMOP linkage validated for accuracy (>90% precision on test set)
- [ ] Coverage scoring implemented and calibrated against known specialty condition lists
- [ ] P3-013 stale detection integrated with editorial board notification workflow
- [ ] Board meeting cadence established and first meeting scheduled
- [ ] Conflict-of-interest register created and initial disclosures collected
- [ ] Licensing/copyright clearance confirmed for all primary source organizations
- [ ] Inter-rater reliability process piloted and kappa >0.8 achieved on test set

---

## 9. Cross-Dependencies

| Dependency | Direction | Impact | Status |
|-----------|-----------|--------|--------|
| P1-012 (Guideline versioning) | Prerequisite | Version tracking infrastructure used by ingestion pipeline | Closed |
| P3-013 (Stale detection) | Prerequisite | Automated staleness alerts routed to editorial board | Closed |
| P4-010 (Causal inference) | Downstream | Richer specialty corpus improves causal reasoning quality | Deferred (monitoring) |
| `guideline_rag_service.py` | Integration | RAG service already supports multi-specialty corpus retrieval | Available (535 lines) |
| `guideline_version_service.py` | Integration | Version lifecycle management used for status transitions | Available (407 lines) |
| `omop_hierarchy_service.py` | Integration | OMOP hierarchy expansion used for concept linkage | Available |
| Editorial board formation | Blocking | No specialty corpus published without board sign-off | Not started |
| Source licensing clearance | Blocking | No guidelines ingested without copyright clearance | Not started |
