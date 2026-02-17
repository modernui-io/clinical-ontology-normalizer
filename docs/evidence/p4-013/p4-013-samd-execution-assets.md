# P4-013-I: SaMD Pathway Execution Assets

**Task:** P4-013-I (Implementation Plan)
**Date:** 2026-02-17
**Operator:** autonomous-agent
**Status:** Governance plan complete (deferred activation per ADR)
**ADR Reference:** `docs/decisions/p4-013-samd-pathway.md`

## Summary

This document codifies the execution assets required if the system crosses a SaMD threshold trigger defined in P4-013-D. Current determination: features do NOT meet SaMD definition. This plan ensures readiness to initiate QMS and regulatory pathway within 30 days of any threshold trigger firing.

## Current State Assessment

| Component | File | Maturity |
|-----------|------|----------|
| Regulatory Determination | `docs/regulatory/regulatory_determination.md` | Current (reviewed 2026-02-16) |
| Intended Use Statement | `docs/regulatory/intended_use_statement.md` | Current |
| Software Risk Assessment | `docs/regulatory/software_risk_assessment.md` | Current |
| PHI Data Flow | `docs/regulatory/phi_data_flow.md` | Current |
| PHI Inventory | `docs/regulatory/PHI_INVENTORY.csv` | Current |
| Change Control Process | `docs/regulatory/change_control_process.md` | Current |
| Validation Study Protocol | `docs/regulatory/VALIDATION_STUDY_PROTOCOL.md` | Current |
| SOC 2 Gap Analysis | `docs/compliance/soc2_gap_analysis.md` | ~82% ready |
| HITRUST Roadmap | `docs/compliance/hitrust_roadmap.md` | Roadmap-level |

## Classification Evidence Matrix

### TGA (Therapeutic Goods Administration — Australia)

| Classification Dimension | Current Assessment | Evidence |
|--------------------------|-------------------|----------|
| Is it software? | Yes | Software-based clinical system |
| Does it meet SaMD definition? | No (currently) | Clinical decision SUPPORT, not autonomous decision |
| Intended purpose | Informational | Assists clinician, does not replace judgment |
| IVD classification | Not applicable | No in-vitro diagnostic function |
| Risk classification (if SaMD) | Class IIa (likely) | Medium risk — clinical decision support |
| Conformity assessment | Not required (currently) | Would require Australian Conformity Assessment via TGA |
| ARTG registration | Not required (currently) | Would require ARTG entry if classified as SaMD |

### FDA (US — if US market entry)

| Classification Dimension | Current Assessment | Evidence |
|--------------------------|-------------------|----------|
| Product code | QMT (Clinical Decision Support) | Pending formal classification |
| 21 CFR Part | Part 820 (QMS), Part 11 (electronic records) | Not yet applicable |
| Submission pathway | De Novo (likely) or 510(k) | No predicate device identified |
| Clinical Decision Support exemption | Potentially eligible | Meets 4 criteria under 21st Century Cures Act if no autonomous action |
| Breakthrough designation | Not applicable | Not pursuing accelerated pathway |

### EU MDR (if EU market entry)

| Classification Dimension | Current Assessment | Evidence |
|--------------------------|-------------------|----------|
| MDR classification | Class IIa (likely) | Rule 11 — software providing clinical information |
| Notified Body | Not selected | Would require NB assessment |
| CE marking | Not applicable (currently) | Required if classified as medical device |
| EUDAMED registration | Not applicable (currently) | Required if CE marked |

## QMS Trigger Criteria

### 6 SaMD Threshold Triggers (from ADR)

| Trigger | Description | Monitoring Method | Current Status |
|---------|-------------|-------------------|---------------|
| T-1 | System makes autonomous treatment recommendations without clinician review | Feature flag audit + product roadmap review | NOT TRIGGERED |
| T-2 | Drug interaction checker operates as standalone safety system | Architecture review + intended use review | NOT TRIGGERED |
| T-3 | Marketing materials claim diagnostic capability | Marketing review + legal review | NOT TRIGGERED |
| T-4 | Clinical calculators remove "verify with clinician" warnings | UI audit + product review | NOT TRIGGERED |
| T-5 | Confidence thresholds lowered below safety floor (P4-011) | Automated policy monitoring | NOT TRIGGERED |
| T-6 | System marketed as replacement for clinician judgment | Marketing review + legal review | NOT TRIGGERED |

### Monitoring Cadence
- **Quarterly review:** Compliance + Legal review all 6 triggers against current product state
- **Ad-hoc review:** Any feature change touching clinical decision paths triggers immediate assessment
- **Product roadmap review:** Every major release reviewed against trigger criteria before launch

## Regulatory Monitoring Checklist (Quarterly)

| Check | Reviewer | Frequency | Last Review |
|-------|----------|-----------|-------------|
| SaMD threshold trigger assessment (6 triggers) | Compliance + Legal | Quarterly | 2026-02-16 (initial) |
| Intended use statement accuracy | Clinical AI Lead | Quarterly | 2026-02-16 (initial) |
| Marketing materials review for diagnostic claims | Legal | Quarterly | PENDING |
| Feature roadmap regulatory impact | CTO + Compliance | Per release | Ongoing |
| International regulatory landscape changes | Compliance | Quarterly | PENDING |
| Post-market surveillance (if SaMD) | Quality Manager | N/A (not SaMD) | N/A |

## Design History File (DHF) Template Structure

If SaMD determination changes, the following DHF structure must be populated:

```
DHF/
  01_design_input/
    user_needs.md
    regulatory_requirements.md
    risk_analysis_input.md
    design_specifications.md
  02_design_output/
    software_architecture.md
    software_detailed_design.md
    interface_specifications.md
    labeling.md
  03_design_verification/
    unit_test_results.md
    integration_test_results.md
    system_test_results.md
    code_review_records.md
  04_design_validation/
    usability_study.md
    clinical_validation_study.md
    performance_validation.md
  05_design_transfer/
    manufacturing_procedures.md (deployment procedures)
    installation_procedures.md
    servicing_procedures.md
  06_design_changes/
    change_control_log.md
    change_impact_assessments/
  07_risk_management/
    risk_management_plan.md
    risk_analysis.md
    risk_evaluation.md
    risk_control.md
    risk_management_report.md
  08_reviews/
    design_review_records.md
    management_review_records.md
```

## IEC 62304 Software Lifecycle Process Mapping

| IEC 62304 Phase | Current Implementation | Gap to Compliance |
|----------------|----------------------|-------------------|
| 5.1 Software development planning | Sprint/wave planning exists | Formal SDP document needed |
| 5.2 Software requirements analysis | Requirements in backlog | Formal SRS with traceability matrix needed |
| 5.3 Software architectural design | Architecture docs exist | Formal SAD with hazard analysis needed |
| 5.4 Software detailed design | Code + inline docs | Formal SDD per module needed |
| 5.5 Software unit implementation | Code exists | Coding standards document needed |
| 5.6 Software integration and integration testing | Integration tests exist (P2-001) | Formal ITP with traceability needed |
| 5.7 Software system testing | System tests exist | Formal STP with acceptance criteria needed |
| 5.8 Software release | Release checklist exists (P1-035) | Formal release procedure + release record needed |
| 6 Software maintenance | Operational runbooks exist | Formal maintenance plan needed |
| 7 Software risk management | Risk assessment exists | Full ISO 14971 process needed |
| 8 Software configuration management | Git + change control | Formal CM plan needed |
| 9 Software problem resolution | Incident taxonomy exists (P1-032) | Formal problem resolution procedure needed |

## Risk Management File (ISO 14971) Gap-to-Full Assessment

| ISO 14971 Requirement | Current State | Gap | Effort to Close |
|-----------------------|---------------|-----|-----------------|
| Risk management plan | Not formalized | Full plan needed | 2-3 weeks |
| Hazard identification | Partial (software risk assessment) | Comprehensive hazard analysis needed | 3-4 weeks |
| Risk estimation | Qualitative (in risk assessment) | Quantitative risk estimation needed | 2-3 weeks |
| Risk evaluation | Implicit in design decisions | Formal acceptability matrix needed | 1-2 weeks |
| Risk control | Implemented in code (confidence policy, etc.) | Formal risk control documentation needed | 2-3 weeks |
| Residual risk evaluation | Not documented | Formal residual risk evaluation needed | 1-2 weeks |
| Risk management report | Not created | Summary report needed | 1 week |
| Production/post-production information | Feedback pipeline exists (P2-009) | Formal PMS plan needed | 2-3 weeks |

**Total estimated effort for full ISO 14971 compliance: 14-21 weeks (1 dedicated quality engineer)**

## Activation Gate Checklist

- [ ] Any SaMD threshold trigger fires (T-1 through T-6)
- [ ] Regulatory counsel confirms SaMD classification change
- [ ] Quality Manager hired or contracted
- [ ] DHF structure created and populated from existing documentation
- [ ] IEC 62304 gap closure plan initiated
- [ ] ISO 14971 risk management file initiated
- [ ] Budget approved for regulatory submission ($50K-200K estimated)
- [ ] Notified Body / regulatory body pre-submission meeting scheduled

## Cross-Dependencies

| Dependency | Impact | Status |
|-----------|--------|--------|
| P4-006 (Model registry) | SaMD may require design history file integration | Deferred (ADR) |
| P4-007 (Copilot experiments) | Experiments may cross SaMD threshold | Deferred (ADR) |
| P4-010 (Causal inference) | Causal claims may trigger SaMD | Deferred (ADR) |
| P4-011 (Adaptive confidence) | Lowering below safety floor triggers review | Deferred (ADR) |
| P1-035 (Release checklist) | Foundation for IEC 62304 release procedure | Closed |
| P1-032 (Incident taxonomy) | Foundation for IEC 62304 problem resolution | Closed |
