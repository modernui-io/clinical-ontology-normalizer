# P4-001-D: Federated Learning Feasibility Decision

**Decision ID:** P4-001-D
**Status:** DECIDED
**Date:** 2026-02-16
**Decision Owner:** VP ML + CTO
**Risk Owner:** CTO
**Evidence Owner:** VP ML

## Context

Federated learning enables cross-organization model training without centralizing PHI. The system already has a production-ready simulation at `backend/app/services/federated_learning_service.py` (1,602 lines) implementing:

- FedAvg and FedProx aggregation protocols
- Differential privacy (gradient clipping + noise injection) via `PrivacyEngine`
- Secure aggregation simulation via `AggregationEngine`
- 5 model types: readmission prediction, mortality risk, length of stay, phenotyping, treatment response
- Multi-organization mock data generation with realistic heterogeneity
- Full round lifecycle: create federation, register participants, local training, aggregation, metrics

**Current maturity:** Scaffold-to-simulation. No real network communication, no actual cross-org data exchange, no production privacy guarantees.

## Decision

**DEFER** federated learning productionization until single-site production stability is achieved (minimum 90 days post-pilot launch with all P0/P1 closed and staging conditions met).

### Gate Criteria for Re-evaluation

1. **Single-site stability gate:** 90 consecutive days of production operation with zero SEV-1 incidents and <3 SEV-2 incidents.
2. **Privacy framework:** Formal differential privacy budget analysis (epsilon/delta) reviewed by external privacy counsel.
3. **Regulatory clarity:** Determination from legal on whether federated model outputs constitute SaMD under TGA (AU) or FDA guidance. Cross-reference P4-013.
4. **Multi-site demand:** At least 2 committed partner organizations with signed data sharing agreements (even for federated use).
5. **Infrastructure readiness:** Secure communication layer (mTLS between federation nodes), model versioning registry (P4-006), and audit trail for training rounds.

### Privacy Framework Requirements (When Activated)

- Minimum epsilon = 1.0 for clinical models (strong privacy guarantee)
- Gradient clipping norm bound defined per model type
- Noise calibration validated against utility loss benchmarks
- Per-round privacy budget accounting with cumulative tracking
- Formal privacy audit before each federation launch

## Alternatives Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| Productionize now | First-mover advantage | No multi-site demand, privacy unvalidated, diverts from P0/P1 closure | Rejected |
| Remove scaffold entirely | Simplifies codebase | Loses demonstration value for investor/partner conversations | Rejected |
| Keep scaffold, gate activation | Preserves optionality, zero production risk | Requires maintenance of unused code | **Selected** |

## Consequences

- Federated learning remains in scaffold/demonstration mode
- `federated_learning_service.py` is maintained but not exposed in pilot routes
- Any external claims about federated learning capability must be labeled "demonstration only"
- Re-evaluation trigger: single-site stability gate criteria met OR strategic partner signs LOI

## Evidence Paths

- Current implementation: `backend/app/services/federated_learning_service.py`
- Privacy engine: `PrivacyEngine` class (gradient clipping, noise injection)
- Aggregation protocols: `AggregationEngine` class (FedAvg, FedProx, SecureAgg)
- This decision: `docs/decisions/p4-001-federated-learning.md`
