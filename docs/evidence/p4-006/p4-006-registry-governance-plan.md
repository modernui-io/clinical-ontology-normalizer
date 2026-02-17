# P4-006-I: Model Registry and Lifecycle Governance Plan

**Task:** P4-006-I (Implementation Plan)
**Date:** 2026-02-17
**Operator:** autonomous-agent
**Status:** Governance plan complete (deferred activation per ADR)
**ADR Reference:** `docs/decisions/p4-006-model-registry.md`

## Summary

This document codifies the implementation plan for transitioning from the in-process model registry to production-grade registry infrastructure. Activation is gated on post-pilot scale criteria defined in P4-006-D: >5 active model versions, >3 model developers, or regulatory reproducibility requirements (P4-013).

## Current State Assessment

| Component | File | Lines | Maturity |
|-----------|------|-------|----------|
| Model Registry Service | `backend/app/services/model_registry_service.py` | 363 | Pilot-level (in-process) |
| Model Governance Service | `backend/app/services/model_governance_service.py` | — | Pilot-level |
| Model Evaluation Service | `backend/app/services/model_evaluation_service.py` | — | Pilot-level |
| ML Model Service | `backend/app/services/ml_model_service.py` | — | Pilot-level |

## Deployment Path

### Phase 1: Pilot (Current)
- **Registry:** In-process `model_registry_service.py`
- **Storage:** PostgreSQL model metadata tables
- **Versioning:** SHA-pinned model artifacts with `ModelVersion` dataclass
- **No external dependencies required**

### Phase 2: Post-Pilot Evaluation (Gate: >5 active versions OR >3 developers)
- **Evaluate:** MLflow (self-hosted or Databricks-managed) vs Weights & Biases
- **Decision criteria:** Self-hosted preference for PHI environments, BAA availability, experiment tracking depth
- **Timeline:** 2-week evaluation sprint with proof-of-concept migration

### Phase 3: Production Registry (Gate: Evaluation approval + budget)
- **Deploy:** Selected platform alongside existing in-process registry (dual-write during transition)
- **Migrate:** Model metadata, evaluation metrics, lineage records
- **Cutover:** Disable in-process registry after 30-day parallel operation with zero discrepancies
- **Target:** MLflow on dedicated infrastructure with PostgreSQL backend and S3-compatible artifact store

## Model Versioning Strategy

### Version Identification
- **Format:** `{model_type}-{major}.{minor}.{patch}-{git_sha_short}`
- **Example:** `nlp-extraction-2.1.0-a3f7b2c`
- **Immutability:** Once registered, a version's artifacts and metadata cannot be modified (append-only)

### Metadata Per Version
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `model_id` | UUID | Yes | Unique model identifier |
| `version` | semver | Yes | Semantic version string |
| `git_sha` | string(40) | Yes | Full commit SHA of training code |
| `training_data_hash` | string(64) | Yes | SHA-256 of training dataset manifest |
| `framework` | enum | Yes | PyTorch, scikit-learn, transformers, etc. |
| `evaluation_metrics` | JSON | Yes | Precision, recall, F1, calibration error |
| `registered_at` | datetime | Yes | Registration timestamp (UTC) |
| `registered_by` | string | Yes | Operator or CI pipeline identity |
| `parent_version` | UUID | No | Previous version in lineage chain |
| `training_config` | JSON | Yes | Full hyperparameter snapshot |

### Stage Enum (from `ModelStage`)
```
development -> staging -> production -> archived
```

## Promotion Flow

### Development -> Staging
- **Trigger:** Developer submits promotion request
- **Automated gates:**
  - Evaluation metrics computed against P1-010 UMLS/OMOP acceptance corpus
  - Precision >= threshold for model type (NLP extraction: 85%, classification: 90%)
  - No regression on existing test suite (`backend/tests/`)
  - Training data provenance validated (no PHI leakage in test splits)
- **Approval:** Automated (all gates pass)

### Staging -> Production
- **Trigger:** Clinical AI Lead submits promotion request
- **Automated gates:**
  - 7-day staging soak with canary traffic (P2-003 infrastructure)
  - Confidence calibration error <10% (Brier score) on staging queries
  - No SEV-1 or SEV-2 incidents during soak period
  - Latency p95 within SLO bounds (P2-017)
- **Manual gates:**
  - Clinical AI Lead review and approval
  - CTO signoff (for models affecting clinical decision paths)
- **Approval:** Manual (both signoffs required)

### Production -> Archived
- **Trigger:** New version promoted to production OR model retired
- **Automated:** Previous production version moved to archived with retention metadata
- **Retention:** Minimum 7 years per HIPAA requirements (P1-028)
- **Archived models remain queryable for audit** but are not served in production paths

## Rollback Procedure

**Target: <15 minutes from decision to rollback completion**

### Rollback Steps
1. **Decision:** Clinical AI Lead or on-call operator identifies rollback need (SEV-1/2 incident, metric regression, clinician report)
2. **Identify target:** Select previous production version from registry (most recent archived version by default)
3. **Execute rollback:**
   - Update model stage: current production -> archived (reason: rollback)
   - Update model stage: target archived -> production
   - Invalidate model cache (Redis key eviction)
   - Health check confirms new model serving
4. **Verify:** Run canary test suite (P2-003) against rolled-back model
5. **Notify:** Alert to Clinical AI Lead + CTO + Ops via incident channel
6. **Post-mortem:** Within 48 hours, document root cause and prevention

### Rollback Authority
| Severity | Who Can Trigger | Approval Required |
|----------|----------------|-------------------|
| SEV-1 (patient safety) | Any on-call operator | None (immediate) |
| SEV-2 (clinical accuracy) | Clinical AI Lead or CTO | None (immediate) |
| SEV-3 (performance) | Clinical AI Lead | CTO notification within 1 hour |
| Planned | Clinical AI Lead | CTO approval |

## Approval Gates by Risk Tier

Risk tiers are defined in `model_governance_service.py`:

| Risk Tier | Model Scope | Staging Soak | Manual Approvers | Rollback Authority |
|-----------|-------------|-------------|-----------------|-------------------|
| Critical | Drug safety, clinical decisions | 14 days | Clinical AI Lead + CTO + Medical Director | Any operator (SEV-1) |
| High | NLP extraction, OMOP mapping | 7 days | Clinical AI Lead + CTO | Clinical AI Lead |
| Medium | Classification, clustering | 3 days | Clinical AI Lead | Clinical AI Lead |
| Low | Internal analytics, reporting | 1 day | Team lead | Team lead |

## Lineage Tracking Requirements

Every model version must record:
1. **Data lineage:** Training dataset ID -> preprocessing pipeline version -> feature extraction version
2. **Code lineage:** Git SHA of training script + framework version + dependency lock file hash
3. **Evaluation lineage:** Evaluation corpus version (P1-010) -> metric computation method -> result snapshot
4. **Promotion lineage:** Promotion request ID -> gate results -> approver identities -> timestamps
5. **Serving lineage:** Which endpoints serve this model -> traffic percentage -> request count

### Lineage Query API (Future)
```
GET /api/v1/models/{model_id}/versions/{version}/lineage
Response: { data_lineage, code_lineage, evaluation_lineage, promotion_lineage, serving_lineage }
```

## Activation Criteria Checklist

- [ ] >5 active model versions in production simultaneously
- [ ] >3 model developers contributing regularly
- [ ] Experiment tracking needed for hyperparameter optimization
- [ ] P4-013 (SaMD) regulatory reproducibility requirements triggered
- [ ] Budget approved for MLflow infrastructure ($0-$500/mo estimated)
- [ ] BAA confirmed with managed platform provider (if not self-hosted)

## Cross-Dependencies

| Dependency | Impact | Status |
|-----------|--------|--------|
| P4-013 (SaMD) | May require design history file integration | Monitoring thresholds |
| P1-010 (Acceptance corpus) | Required for promotion gate metrics | Closed |
| P2-003 (Canary tests) | Used for staging soak and rollback verification | Closed |
| P2-017 (SLO dashboard) | Latency bounds for staging soak | Closed |
| P3-005 (Calibration plots) | Confidence calibration gate | Closed |
