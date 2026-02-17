# P4-007-I: Clinician Copilot Experiment Framework Design

**Task:** P4-007-I (Implementation Plan)
**Date:** 2026-02-17
**Operator:** autonomous-agent
**Status:** Framework design complete (deferred activation per ADR)
**ADR Reference:** `docs/decisions/p4-007-clinician-copilot-ux.md`

## Summary

This document defines the experiment framework architecture for clinician copilot UX experiments. No experiments are permitted during pilot. This framework activates after 90 days of stable pilot operation with zero SEV-1 AI-related incidents, as specified in P4-007-D.

## Feature Flag Architecture

### Per-Clinician Opt-In Model
```
ExperimentConfig:
  experiment_id: UUID
  experiment_name: string
  experiment_class: enum (passive_suggestions | active_alerts | auto_complete | decision_support)
  safety_risk_tier: enum (low | medium | high | critical)
  status: enum (draft | active | paused | completed | aborted)
  opt_in_mode: "per_clinician"  # NOT org-wide rollout
  eligible_clinicians: list[clinician_id]
  enrolled_clinicians: list[clinician_id]
  control_group_pct: float  # minimum 50% for safety
  created_at: datetime
  activated_at: datetime | null
  completed_at: datetime | null
  abort_reason: string | null
```

### Config-Driven Feature Flags
- Feature flags stored in `backend/app/core/config.py` pattern (environment variables + database overrides)
- Flag format: `EXPERIMENT_{experiment_id}_ENABLED=true|false`
- Per-clinician enrollment checked at request time via middleware
- Flag evaluation order: global kill switch -> experiment status -> clinician enrollment -> A/B assignment

### Kill Switch Hierarchy
1. **Global kill switch:** `EXPERIMENTS_GLOBAL_ENABLED=false` disables all experiments immediately
2. **Class kill switch:** `EXPERIMENTS_{class}_ENABLED=false` disables all experiments of a class
3. **Individual switch:** `EXPERIMENT_{id}_ENABLED=false` disables specific experiment
4. **Clinician opt-out:** Any clinician can opt out at any time via UI toggle

## A/B Routing Architecture

### Traffic Split
```
Request -> Auth Middleware -> Experiment Middleware -> Route Handler

Experiment Middleware:
  1. Check global kill switch
  2. Check if clinician is enrolled in any active experiment
  3. Determine assignment (treatment vs control) via consistent hashing on clinician_id
  4. Set request context: experiment_id, variant, enrolled_at
  5. Pass to route handler with experiment context
```

### Assignment Strategy
- **Consistent hashing:** `hash(clinician_id + experiment_id) % 100` determines treatment/control
- **Sticky assignment:** Once assigned, clinician stays in same group for experiment duration
- **Minimum control:** 50% of enrolled clinicians in control group (safety requirement)
- **No cross-contamination:** Clinician cannot be in treatment group for two experiments simultaneously

### Response Augmentation
- Treatment group: Standard response + experiment augmentation (suggestion, alert, etc.)
- Control group: Standard response only
- Both groups: Feedback capture enabled, latency tracked, metrics recorded

## Experiment Classes with Safety Risk Tiers

### Class 1: Passive Suggestions (Risk: Low)
- **Description:** AI-generated notes visible alongside clinician workflow
- **UX pattern:** Non-intrusive sidebar or tooltip, no workflow interruption
- **Data captured:** View time, dismiss/expand, copy/edit/ignore
- **Safety controls:** Standard feedback capture, no action gating
- **Minimum baseline:** 30 days stable pilot, zero SEV-1

### Class 2: Active Alerts (Risk: Medium)
- **Description:** AI flags potential issues requiring clinician attention
- **UX pattern:** Banner or notification, requires acknowledgment
- **Data captured:** Alert viewed, acknowledged, acted upon, dismissed with reason
- **Safety controls:** Alert fatigue monitoring (P2-018), acknowledgment required, escalation if ignored for >30 min on critical alerts
- **Minimum baseline:** 60 days stable pilot, zero SEV-1, alert infrastructure validated

### Class 3: Auto-Complete (Risk: High)
- **Description:** AI completes clinical documentation fields
- **UX pattern:** Inline suggestion with accept/reject/modify
- **Data captured:** Suggestion accuracy, edit distance between suggestion and final, time savings
- **Safety controls:** All completions reviewed before save, medication/allergy fields excluded, confidence threshold >0.9 required
- **Minimum baseline:** 90 days stable pilot, zero SEV-1, separate safety review board approval

### Class 4: Decision Support (Risk: Critical)
- **Description:** AI recommends treatment pathways
- **UX pattern:** Structured recommendation panel with evidence citations
- **Data captured:** Recommendation followed/modified/rejected with clinical rationale
- **Safety controls:** All recommendations labeled "AI suggestion — clinical judgment required", P4-013 SaMD determination required before activation, dual-clinician review for high-risk recommendations
- **Minimum baseline:** 180 days stable pilot, zero SEV-1, SaMD regulatory determination, IRB approval

## Guardrails: Abort Triggers

### Automatic Abort Triggers
| Trigger | Threshold | Action | Recovery |
|---------|-----------|--------|----------|
| Reject rate on safety-critical suggestions | >5% within any 7-day window | Immediate experiment pause | Clinical AI Lead review required to resume |
| Adverse event linked to AI suggestion | Any single event | Immediate experiment abort | Post-mortem + safety review before new experiments |
| Confidence calibration drift | >10% from baseline (Brier score) | Immediate experiment pause | Recalibration required before resume |
| Alert fatigue signal | >50% dismiss rate on active alerts | Experiment pause | Alert tuning review by Clinical AI Lead |
| Latency degradation | p95 > 2x baseline | Experiment pause | Performance investigation required |

### Manual Abort Authority
| Role | Can Abort | Scope |
|------|-----------|-------|
| Any enrolled clinician | Opt-out from personal enrollment | Self only |
| Clinical AI Lead | Pause/abort any experiment | Per-experiment |
| VP Product | Pause/abort any experiment | Per-experiment or all |
| CTO | Global kill switch | All experiments |
| Medical Director | Abort on patient safety grounds | All experiments |

## Feedback Capture Integration

### P2-009 Infrastructure Reuse
- Clinician feedback capture pipeline (P2-009) provides: accept/reject/modify actions, free-text rationale, star rating
- **Extension for experiments:**
  - Add `experiment_id` and `variant` (treatment/control) to feedback payload
  - Add `suggestion_id` for per-suggestion tracking
  - Add `time_to_decision` (milliseconds from suggestion display to action)
  - Weekly feedback dataset review by Clinical AI Lead (P2-009 cadence)

### Feedback Schema Extension
```json
{
  "feedback_id": "uuid",
  "experiment_id": "uuid",
  "variant": "treatment|control",
  "clinician_id": "uuid",
  "suggestion_id": "uuid|null",
  "action": "accept|reject|modify|dismiss|ignore",
  "rationale": "free text (optional)",
  "rating": 1-5,
  "time_to_decision_ms": 1234,
  "context": {
    "page": "clinical|intelligence|nlp",
    "workflow": "extraction|diagnosis|medication_review",
    "patient_acuity": "routine|urgent|critical"
  },
  "created_at": "2026-MM-DDT..."
}
```

## Monitoring Dashboard Requirements

### Real-Time Metrics (Per Experiment)
| Metric | Update Frequency | Visualization |
|--------|-----------------|---------------|
| Enrollment count (treatment vs control) | Real-time | Bar chart |
| Suggestion accept/reject rate | Hourly rolling | Time series |
| Average time-to-decision | Hourly rolling | Time series + histogram |
| Adverse event count | Real-time | Counter (0 = green, >0 = red) |
| Confidence calibration drift | Daily | Calibration plot overlay |
| Clinician satisfaction (rating) | Daily | Distribution chart |
| Latency impact (treatment vs control) | Hourly | Comparison time series |

### Alert Thresholds
| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| Reject rate | >3% | >5% | Pause experiment |
| Adverse events | N/A | >0 | Abort experiment |
| Calibration drift | >5% | >10% | Pause experiment |
| Dismiss rate (alerts) | >30% | >50% | Pause experiment |

### Dashboard Access
- Clinical AI Lead: Full access to all experiment metrics
- VP Product: Summary view + abort capability
- Enrolled clinicians: Personal metrics only (own feedback history)
- CTO: Global experiment health summary

## Activation Criteria Checklist

- [ ] 90 days stable pilot with zero SEV-1 AI-related incidents
- [ ] Feature flag infrastructure deployed and tested
- [ ] A/B routing middleware implemented and validated
- [ ] Feedback schema extension deployed
- [ ] Monitoring dashboard operational
- [ ] Clinical AI Lead trained on experiment management
- [ ] First experiment design reviewed and approved by VP Product + Clinical AI Lead
- [ ] IRB consultation completed (for Class 3-4 experiments)

## Cross-Dependencies

| Dependency | Impact | Status |
|-----------|--------|--------|
| P0-021 (Confidence policy) | Experiment suggestions must respect risk-tier gating | Closed |
| P0-024 (Degraded mode) | Experiments auto-disabled in degraded mode | Closed |
| P2-009 (Feedback capture) | Foundation for experiment feedback pipeline | Closed |
| P2-018 (Alert fatigue) | Alert experiment class depends on fatigue controls | Closed |
| P4-013 (SaMD) | Decision support class requires regulatory determination | Monitoring |
