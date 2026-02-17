# P4 Deferred Gates Index

**Created:** 2026-02-17
**Purpose:** Consolidated view of all P4 items with ADR-approved DEFER/CONDITIONAL DEFER decisions. I/V subtasks are intentionally blocked pending activation conditions defined in each ADR.
**Next Review:** 2026-05-17 (90-day audit cycle)

## Summary

| # | P4 ID | Title | ADR Decision | Trigger | Gate Owner | Evidence Dir | Next Review |
|---|-------|-------|-------------|---------|------------|-------------|-------------|
| 1 | P4-001 | Federated Learning | DEFER | 90-day stability + privacy counsel + 2 partners | VP ML | [`p4-001`](../p4-001/p4-001-deferred-gate.md) | 2026-05-17 |
| 2 | P4-002 | TEFCA Strategy | DEFER | US customer LOI signed | Interop | [`p4-002`](../p4-002/p4-002-deferred-gate.md) | 2026-05-17 |
| 3 | P4-003 | ONC Certification | CONDITIONAL DEFER | US customer requires ONC | Interop | [`p4-003`](../p4-003/p4-003-deferred-gate.md) | 2026-05-17 |
| 4 | P4-004 | Graph Platform | Maintain Community | 50K patients OR graph SLO violations | Ops | [`p4-004`](../p4-004/p4-004-deferred-gate.md) | 2026-05-17 |
| 5 | P4-005 | Multi-Region | Single-region AU | Second AU customer OR non-AU customer | CTO | [`p4-005`](../p4-005/p4-005-deferred-gate.md) | 2026-05-17 |
| 6 | P4-011 | Adaptive Confidence | Ethics review required | Clinical demand + ethics review + simulation | Clinical AI | [`p4-011`](../p4-011/p4-011-deferred-gate.md) | 2026-05-17 |
| 7 | P4-012 | Developer Platform | DEFER | External partner LOI + sandbox capability | Product | [`p4-012`](../p4-012/p4-012-deferred-gate.md) | 2026-05-17 |
| 8 | P4-013 | SaMD Pathway | NOT SaMD (monitored) | Any SaMD threshold trigger confirmed | Compliance | [`p4-013`](../p4-013/p4-013-deferred-gate.md) | 2026-05-17 |
| 9 | P4-014 | Data Mesh | PREMATURE | 100K patients + 10 engineers + bottleneck | Data | [`p4-014`](../p4-014/p4-014-deferred-gate.md) | 2026-05-17 |
| 10 | P4-015 | Outcome Feedback | Framework defined | 90-day pilot + EHR data feed + advisor sign-off | Clinical AI | [`p4-015`](../p4-015/p4-015-deferred-gate.md) | 2026-05-17 |

## ADR Cross-References

| P4 ID | ADR Path |
|-------|----------|
| P4-001 | `docs/decisions/p4-001-federated-learning.md` |
| P4-002 | `docs/decisions/p4-002-tefca-strategy.md` |
| P4-003 | `docs/decisions/p4-003-onc-certification.md` |
| P4-004 | `docs/decisions/p4-004-graph-platform.md` |
| P4-005 | `docs/decisions/p4-005-multi-region.md` |
| P4-011 | `docs/decisions/p4-011-adaptive-confidence.md` |
| P4-012 | `docs/decisions/p4-012-developer-platform.md` |
| P4-013 | `docs/decisions/p4-013-samd-pathway.md` |
| P4-014 | `docs/decisions/p4-014-data-mesh.md` |
| P4-015 | `docs/decisions/p4-015-outcome-feedback.md` |

## Governance Rules

1. **No silent activation:** A deferred gate may not be activated without the trigger condition being met and documented in the evidence directory.
2. **90-day review cycle:** All gates are reviewed at minimum every 90 days. Next review: 2026-05-17.
3. **Trigger-fires protocol:** If a trigger fires between scheduled reviews, the gate owner must initiate activation review within 5 business days.
4. **Escalation path:** If no progress after two consecutive review cycles (180 days), escalate to CTO for strategic re-evaluation or formal retirement.
5. **Evidence requirement:** Activation requires a written memo from the gate owner confirming trigger conditions met, with supporting evidence artifacts.
