# Off-Hours Clinical Escalation Playbook

**Document ID**: OPS-P3-018
**Version**: 1.0
**Effective Date**: 2026-02-15
**Owner**: CIO + Clinical Operations
**Classification**: Internal — Operational

## Purpose

Guide on-call engineers through clinical escalation decisions when clinical domain experts are unavailable (nights, weekends, holidays).

## Decision Framework

### Step 1: Classify the Issue

| Classification | Description | Action |
|---|---|---|
| **Technical only** | Infrastructure, connectivity, performance | Handle per standard on-call procedures |
| **Clinical data** | Data accuracy, mapping errors, extraction issues | Follow clinical triage below |
| **Patient safety** | Potential harm, wrong results displayed | Immediate escalation (always) |

### Step 2: Clinical Triage Decision Tree

```
Is patient safety potentially affected?
├─ YES → ESCALATE IMMEDIATELY (see Emergency below)
└─ NO
   ├─ Is the issue affecting active clinical workflows?
   │  ├─ YES → Can affected feature be safely disabled?
   │  │  ├─ YES → Disable feature, create SEV-2, notify next morning
   │  │  └─ NO → Escalate to Clinical AI Lead
   │  └─ NO → Create SEV-3 ticket, address next business day
   └─ Is it a data quality issue?
      ├─ Widespread (>10 patients) → Quarantine pipeline, SEV-2
      └─ Isolated (1-2 records) → Flag records, SEV-3
```

### Step 3: Safe Actions (On-Call Can Take)

These actions are always safe and do not require clinical expertise:

- Restart a service that has crashed
- Scale up workers for queue backup
- Disable a non-critical feature behind feature flag
- Quarantine a data pipeline (stop new imports)
- Increase logging for diagnosis
- Page secondary on-call for assistance

### Step 4: Unsafe Actions (Require Clinical Approval)

**NEVER** take these actions without clinical domain expert approval:

- Modify clinical fact data directly in database
- Change confidence thresholds
- Alter drug safety rules or interaction databases
- Push a clinical pathway change to production
- Re-enable a quarantined clinical pipeline
- Override extraction or mapping results

## Emergency Escalation

For potential patient safety issues (any hour):

1. **Page Clinical AI Lead** via PagerDuty (5 min response SLA)
2. If no response in 10 min: **Page CMO backup**
3. If no response in 20 min: **Page CTO** (who has authority to shut down clinical features)
4. **Document everything**: Times, decisions, actions taken

## Contact Priority

| Priority | Role | Method | Response |
|---|---|---|---|
| 1 | Clinical AI Lead | PagerDuty | 5 min |
| 2 | CMO / Clinical Safety | PagerDuty | 10 min |
| 3 | CTO | PagerDuty + Phone | 15 min |
| 4 | CIO | Phone | 30 min |

## Common Off-Hours Scenarios

### Scenario A: NLP extraction producing unusual results

**Symptoms**: Alert on extraction quality metric dropping
**Safe action**: Quarantine new imports, existing data unaffected
**Next step**: Clinical AI Lead reviews next morning

### Scenario B: Drug interaction check returning errors

**Symptoms**: 500 errors on drug safety endpoint
**Safe action**: Enable fallback "check unavailable" response (already built)
**NEVER**: Disable drug safety checks entirely
**Next step**: Fix and redeploy with Clinical AI Lead approval

### Scenario C: Patient KG showing wrong connections

**Symptoms**: User report or monitoring alert on KG anomaly
**Safe action**: Flag affected patient records, disable KG visualization for that patient
**NEVER**: Delete or modify KG data directly
**Next step**: Data integrity investigation next business day

### Scenario D: OpenEHR import producing duplicate facts

**Symptoms**: Import stats higher than expected
**Safe action**: Pause import pipeline
**Next step**: Reconciliation by Data Engineer next morning
