# P4-006-D: Model Registry and Lifecycle Governance Decision

**Decision ID:** P4-006-D
**Status:** DECIDED
**Date:** 2026-02-16
**Decision Owner:** VP ML
**Risk Owner:** VP ML
**Evidence Owner:** CTO

## Context

The system has a model registry service at `backend/app/services/model_registry_service.py` (363 lines) implementing:

- `ModelStage` enum: development, staging, production, archived
- `ModelType` enum: classification, regression, NLP, clustering, etc.
- `ModelVersion` dataclass with versioning and lifecycle tracking
- ML model versioning and promotion pipeline

Additional ML services exist: `ml_model_service.py`, `model_evaluation_service.py`, `model_governance_service.py`.

**Current maturity:** Implemented (pilot-level). Runs in-process, no persistent registry infrastructure.

## Decision

**Use in-process model registry for pilot. Evaluate MLflow or Weights & Biases at post-pilot scale.**

### Registry Platform Comparison

| Platform | Self-hosted | Managed | Model Lineage | Experiment Tracking | Cost | Migration from current |
|----------|-----------|---------|--------------|-------------------|------|----------------------|
| Current (in-process) | Yes | N/A | Basic | None | $0 | N/A |
| MLflow | Yes | Databricks | Full | Full | $0-$500/mo | Medium |
| Weights & Biases | No | Yes (SaaS) | Full | Full | $50-$500/mo | Medium |
| Custom (extend current) | Yes | N/A | Basic | Custom | Dev time | Low |

### Versioning and Promotion Policy

1. **Development:** Any model commit with evaluation metrics
2. **Staging:** Passes automated quality gates (precision, recall, calibration against P1-010 corpus)
3. **Production:** Manual approval by Clinical AI Lead + CTO signoff
4. **Archived:** Retained for audit (minimum 7 years per HIPAA)
5. **Rollback:** Any production model can be reverted to previous version within 15 minutes

### Gate Criteria for External Registry

- >5 active model versions in production simultaneously
- >3 model developers contributing regularly
- Experiment tracking needed for hyperparameter optimization
- Reproducibility requirements from regulatory (P4-013)

## Consequences

- Current `model_registry_service.py` is sufficient for pilot
- Add model version SHA and evaluation metrics to audit trail
- MLflow evaluation deferred to post-pilot (gated on team size and model count)
- Cross-dependency: P4-013 (SaMD) may require formal design history file integration with registry

## Evidence Paths

- Model registry: `backend/app/services/model_registry_service.py`
- Model governance: `backend/app/services/model_governance_service.py`
- Model evaluation: `backend/app/services/model_evaluation_service.py`
- This decision: `docs/decisions/p4-006-model-registry.md`
