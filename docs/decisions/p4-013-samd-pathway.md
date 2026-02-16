# P4-013-D: SaMD Pathway Exploration Decision

**Decision ID:** P4-013-D
**Status:** DECIDED
**Date:** 2026-02-16
**Decision Owner:** Compliance + Legal
**Risk Owner:** Legal
**Evidence Owner:** Compliance

## Context

Comprehensive regulatory documentation exists:

- `docs/regulatory/regulatory_determination.md` — regulatory classification analysis
- `docs/regulatory/intended_use_statement.md` — intended use definition
- `docs/regulatory/software_risk_assessment.md` — IEC 62304 risk assessment
- `docs/regulatory/phi_data_flow.md` — PHI data flow documentation
- `docs/regulatory/PHI_INVENTORY.csv` — PHI inventory
- `docs/regulatory/change_control_process.md` — change control process
- `docs/regulatory/VALIDATION_STUDY_PROTOCOL.md` — validation protocol
- `docs/compliance/soc2_gap_analysis.md` — SOC 2 readiness (~82%)
- `docs/compliance/hitrust_roadmap.md` — HITRUST roadmap

**Key question:** Does the clinical ontology normalizer meet the definition of Software as a Medical Device (SaMD) under TGA (Australia) or FDA (US) guidance?

## Decision

**Current feature set does NOT meet SaMD definition. Monitor for threshold crossing as features expand.**

### Regulatory Determination Analysis

| Feature | SaMD Risk? | Rationale |
|---------|-----------|-----------|
| Clinical data normalization (OMOP mapping) | No | Data transformation, not diagnostic or therapeutic recommendation |
| Knowledge graph construction | No | Data organization and visualization, not clinical decision |
| Clinical Q&A with provenance | Borderline | Provides clinical information WITH explicit labeling as non-diagnostic |
| Confidence-gated responses | Reduces risk | Explicitly prevents high-confidence claims on uncertain data |
| Differential diagnosis scores | Borderline | P1-015 labels as "ranking" not "probability" — reduces SaMD risk |
| Drug interaction checking | Yes (if standalone) | Currently integrated with clinician-in-the-loop requirement |
| Clinical calculators | Yes (if autonomous) | Currently labeled with "verify with clinician" warnings |

### Current Mitigations Against SaMD Classification

1. **Intended use statement** explicitly positions as clinical decision SUPPORT (not autonomous decision)
2. **Clinician-in-the-loop** required for all clinical actions (P0-024 degraded mode blocks autonomous operation)
3. **Confidence labeling** prevents false certainty (P0-021, P0-022, P0-023)
4. **No autonomous treatment recommendations** — all outputs require clinician review

### SaMD Threshold Triggers (Monitor These)

If ANY of the following become true, immediate SaMD determination review required:

1. System makes autonomous treatment recommendations without clinician review
2. Drug interaction checker operates as standalone safety system
3. Marketing materials claim diagnostic capability
4. Clinical calculators remove "verify with clinician" warnings
5. Confidence thresholds are removed or lowered below safety floor (P4-011)
6. System is marketed as replacement for (not supplement to) clinician judgment

### If SaMD Determination Changes

| Jurisdiction | Framework | Timeline | Key Requirements |
|-------------|-----------|----------|-----------------|
| Australia (TGA) | Therapeutic Goods Act 1989, SaMD guidance | 6-12 months | Classification, conformity assessment, ARTG registration |
| US (FDA) | 21 CFR Part 820, SaMD guidance | 12-18 months | 510(k) or De Novo, QMS, design history file |
| EU (MDR) | EU MDR 2017/745 | 18-24 months | CE marking, Notified Body assessment, QMS |

### Quality Management System Readiness

| QMS Component | Current State | Gap |
|---------------|--------------|-----|
| Design controls | Change control process exists | Formal design history file needed |
| Risk management (ISO 14971) | Software risk assessment exists | Full risk management file needed |
| Validation | Validation study protocol exists | Formal V&V per IEC 62304 needed |
| Post-market surveillance | Feedback capture exists (P2-009) | Formal PMS plan needed |
| Complaint handling | Incident taxonomy exists (P1-032) | Formal complaint process needed |

## Consequences

- No SaMD-specific compliance work during pilot
- Existing regulatory documentation maintained and updated
- Threshold triggers monitored continuously by Compliance + Legal
- If SaMD determination changes, minimum 6-month lead time before compliance
- Cross-dependencies: P4-007 (copilot), P4-010 (causal inference) may trigger SaMD review

## Evidence Paths

- Regulatory determination: `docs/regulatory/regulatory_determination.md`
- Intended use: `docs/regulatory/intended_use_statement.md`
- Risk assessment: `docs/regulatory/software_risk_assessment.md`
- Change control: `docs/regulatory/change_control_process.md`
- Validation protocol: `docs/regulatory/VALIDATION_STUDY_PROTOCOL.md`
- SOC 2: `docs/compliance/soc2_gap_analysis.md`
- This decision: `docs/decisions/p4-013-samd-pathway.md`
