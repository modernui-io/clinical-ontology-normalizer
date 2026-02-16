# P4-007-D: Advanced Clinician Copilot UX Experiments Decision

**Decision ID:** P4-007-D
**Status:** DECIDED
**Date:** 2026-02-16
**Decision Owner:** VP Product
**Risk Owner:** VP Product
**Evidence Owner:** Clinical AI

## Context

The clinical UI surfaces are extensive (19 clinical sub-pages, 1,067-line main clinical page, 1,273-line intelligence page). Current state:

- `frontend/src/app/clinical/page.tsx` — full clinical dashboard with safety, calculators, differential diagnosis
- `frontend/src/app/clinical/intelligence/page.tsx` — advanced graph visualization, AI reasoning UI
- Confidence policy enforced (P0-021) with risk-tier gating
- Degraded UX mode active (P0-024) with clinician escalation
- Pilot UI locked to canonical route (P0-020)

**Key constraint:** Safety baseline must be locked before any copilot experiments. 77% accuracy class gated by confidence policy per P1-016.

## Decision

**No copilot experiments during pilot. Define experiment framework and safety guardrails now for post-pilot activation.**

### Experiment Scope Definition

| Experiment Class | Description | Safety Risk | Allowed in Pilot? |
|-----------------|-------------|-------------|-------------------|
| Passive suggestions | AI-generated notes visible alongside clinician workflow | Low | No (post-pilot) |
| Active alerts | AI flags potential issues requiring clinician attention | Medium | No (post-pilot) |
| Auto-complete | AI completes clinical documentation fields | High | No (requires separate safety review) |
| Decision support | AI recommends treatment pathways | Critical | No (requires SaMD determination per P4-013) |

### Safety Guardrails (Pre-Approved for Post-Pilot)

1. **A/B routing:** Feature flags with per-clinician opt-in, not org-wide rollout
2. **Feedback capture:** Every AI suggestion must have accept/reject/modify feedback loop (P2-009 infrastructure exists)
3. **Abort triggers:** Auto-disable experiment if: (a) >5% reject rate on safety-critical suggestions, (b) any adverse event report linked to AI suggestion, (c) confidence calibration drift >10% from baseline
4. **Monitoring dashboard:** Real-time experiment metrics visible to Clinical AI Lead
5. **Minimum baseline:** 90 days of stable pilot operation with zero SEV-1 AI-related incidents

### Success Criteria (Per Experiment)

- Clinician satisfaction score >4.0/5.0 on post-interaction survey
- No increase in clinical documentation errors vs. baseline
- Task completion time reduction >10% for targeted workflows
- Zero adverse events attributable to AI suggestions

## Consequences

- No UX experiments during pilot
- Experiment framework defined and ready for post-pilot activation
- Feature flag infrastructure required before first experiment (low effort, use existing config patterns)
- Cross-dependency: P4-013 (SaMD) may classify certain copilot features as medical devices

## Evidence Paths

- Clinical UI: `frontend/src/app/clinical/page.tsx`, `frontend/src/app/clinical/intelligence/page.tsx`
- Confidence policy: `backend/app/services/confidence_policy_service.py`
- Feedback capture: P2-009 infrastructure
- Pilot accuracy policy: `docs/operations/pilot_accuracy_policy.md`
- This decision: `docs/decisions/p4-007-clinician-copilot-ux.md`
