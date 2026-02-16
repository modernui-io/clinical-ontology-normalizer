# P4-003-D: ONC Certification Roadmap Decision

**Decision ID:** P4-003-D
**Status:** DECIDED
**Date:** 2026-02-16
**Decision Owner:** Compliance + Interop
**Risk Owner:** Compliance
**Evidence Owner:** Interop

## Context

ONC Health IT Certification (21st Century Cures Act) is required for EHR modules participating in US interoperability mandates. The system's current compliance posture:

- **SOC 2 readiness:** ~82% (33/45 controls implemented) per `docs/compliance/soc2_gap_analysis.md` (CISO-12)
- **HITRUST roadmap:** Exists at `docs/compliance/hitrust_roadmap.md`
- **FHIR support:** Import/export services implemented (`backend/app/services/fhir_import_service.py`, `backend/app/services/fhir_export_service.py`)
- **USCDI support:** Partial — covers conditions, medications, allergies, procedures, labs, vitals via OMOP mapping; gaps in social determinants, care team, goals
- **OpenEHR:** Primary exchange format for AU pilot (Ramsey Health)

**Market question:** Does the target customer base (AU health systems, potential US expansion) require ONC certification?

## Decision

**CONDITIONAL DEFER** — ONC certification is NOT required for AU pilot. Build readiness assessment for US market entry decision.

### Market Analysis

| Market | ONC Required? | Rationale |
|--------|--------------|-----------|
| Australia (Ramsey Health) | No | AU uses ADHA standards, OpenEHR, My Health Record. ONC is US-specific. |
| US Health Systems | Yes (if EHR module) | Required for certified EHR technology under Cures Act |
| US Clinical Decision Support | Depends | CDS not always in certification scope; depends on claims and integration model |
| US Research/Analytics | No | Analytics platforms typically exempt unless making EHR claims |

### Determination

The system is positioned as a **clinical ontology normalization and intelligence platform**, not an EHR module. ONC certification is likely NOT required unless:
1. The product is marketed as a certified EHR module
2. The product performs functions that require information blocking exceptions
3. A US customer contractually requires ONC certification

### Readiness Gap Analysis (If Activated)

| ONC Criterion | Current State | Gap | Effort |
|---------------|--------------|-----|--------|
| USCDI v3 data classes | 6/12 covered via OMOP | 6 classes missing (social determinants, goals, care team, health concerns, clinical notes format, provenance) | Medium |
| API Conditions (FHIR R4) | FHIR import/export implemented | Capability statement, SMART on FHIR auth, bulk export | High |
| Information Blocking | Not applicable (not an EHR) | Would need compliant API access policy | Low |
| Real World Testing | No plan | Would need 12-month testing plan | High |
| Attestation | Not started | Would need ONC-ACB engagement | High |

### Timeline (If Triggered)

- Month 1-2: Formal ONC-ACB engagement and scope determination
- Month 3-6: USCDI gap remediation and SMART on FHIR implementation
- Month 7-9: Real world testing plan and initial execution
- Month 10-12: Certification testing with ONC-ACB
- Month 13-15: Certification issuance (optimistic)

## Consequences

- No ONC certification work during AU pilot
- FHIR services maintained and improved as part of interoperability baseline
- If US customer requires ONC, trigger P4-003-I with 15-month lead time
- Cross-dependency: P4-002 (TEFCA) benefits from ONC FHIR readiness work

## Evidence Paths

- SOC 2 gap analysis: `docs/compliance/soc2_gap_analysis.md`
- HITRUST roadmap: `docs/compliance/hitrust_roadmap.md`
- FHIR services: `backend/app/services/fhir_import_service.py`, `backend/app/services/fhir_export_service.py`
- OpenEHR contract: `backend/app/connectors/meditech_openehr_contract.py`
- This decision: `docs/decisions/p4-003-onc-certification.md`
