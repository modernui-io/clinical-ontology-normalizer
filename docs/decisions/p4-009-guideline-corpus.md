# P4-009-D: Guideline Corpus Specialty Expansion Decision

**Decision ID:** P4-009-D
**Status:** DECIDED
**Date:** 2026-02-16
**Decision Owner:** Clinical AI + Clinical Governance
**Risk Owner:** Clinical Governance
**Evidence Owner:** Clinical AI

## Context

Guideline services are well-implemented:

- `backend/app/services/guideline_rag_service.py` (537 lines) — RAG-based guideline retrieval with OMOP hierarchy support, semantic search, keyword boosting
- `backend/app/services/guideline_version_service.py` (407 lines) — versioning, lifecycle management, expiry detection
- P1-012 (guideline corpus versioning) and P3-013 (stale guideline detection) are closed

**Current coverage:** General clinical guidelines. No specialty-specific corpus depth (cardiology, oncology, nephrology, etc.).

## Decision

**Prioritize specialty expansion by pilot demand and clinical risk. Establish editorial governance board before adding any specialty corpus.**

### Specialty Priority Ranking

| Priority | Specialty | Rationale | Guideline Source | Estimated Corpus Size |
|----------|----------|-----------|-----------------|---------------------|
| 1 | General Internal Medicine | Broadest pilot applicability at Ramsey Health | NICE, UpToDate, ACP | ~200 guidelines |
| 2 | Cardiology | High volume, high risk, strong guideline ecosystem | AHA/ACC, ESC | ~150 guidelines |
| 3 | Oncology | High complexity, rapidly evolving, high clinical value | NCCN, ESMO, ASCO | ~300 guidelines |
| 4 | Nephrology | CKD management, medication dosing, high risk | KDIGO | ~50 guidelines |
| 5 | Endocrinology | Diabetes management breadth | ADA, Endocrine Society | ~100 guidelines |

### Editorial Governance Board Requirements

1. **Board composition:** Clinical AI Lead + at least one domain expert per active specialty + Compliance representative
2. **Review cadence:** Monthly for active specialties, quarterly for inactive
3. **Responsibilities:**
   - Approve new guideline additions (source, version, scope)
   - Review stale guideline alerts (P3-013 infrastructure)
   - Sign off on coverage and accuracy reports per specialty
   - Approve retirement of superseded guidelines
4. **Quality gate:** No guideline enters production corpus without board sign-off

### Ingestion Requirements Per Specialty

- Structured metadata: source organization, publication date, version, expiry date, evidence grade
- OMOP concept linkage: each guideline mapped to relevant OMOP condition/drug concepts
- Coverage report: percentage of specialty conditions covered by corpus
- Accuracy validation: spot-check by domain expert (minimum 20 guidelines per specialty)

## Consequences

- No specialty expansion during initial pilot (general medicine only)
- Editorial governance board charter drafted and ready for activation
- First specialty addition (cardiology) targeted for post-pilot Month 2
- Guideline RAG service already supports multi-specialty corpus (no code changes needed)
- Cross-dependency: P4-010 (causal inference) benefits from richer guideline corpus

## Evidence Paths

- Guideline RAG: `backend/app/services/guideline_rag_service.py`
- Guideline versioning: `backend/app/services/guideline_version_service.py`
- Stale detection: P3-013 closed
- This decision: `docs/decisions/p4-009-guideline-corpus.md`
