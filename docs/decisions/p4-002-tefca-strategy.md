# P4-002-D: TEFCA Productionization Strategy Decision

**Decision ID:** P4-002-D
**Status:** DECIDED
**Date:** 2026-02-16
**Decision Owner:** Interop + CIO
**Risk Owner:** CIO
**Evidence Owner:** Interop

## Context

TEFCA (Trusted Exchange Framework and Common Agreement) enables nationwide health information exchange via Qualified Health Information Networks (QHINs). The system has a comprehensive simulation at `backend/app/services/tefca_service.py` (1,244 lines) implementing:

- QHIN discovery with 8 mock networks (Epic/Carequality, CommonWell, eHealth Exchange, Health Gorilla, Surescripts, Konza HIIN, Medicity)
- IHE PDQm patient discovery with match confidence scoring
- IHE MHD document query/retrieve with document caching
- Direct secure messaging simulation
- SAML assertion validation
- ATNA-compliant audit logging
- Patient consent management (opt-in/opt-out)
- Exchange purposes: treatment, payment, operations, public health, individual access, benefits/coverage determination, emergency

**Current maturity:** Simulation only. No real QHIN connectivity, no SAML certificates, no Direct messaging infrastructure.

**Market context:** Ramsey Health Australia pilot uses OpenEHR (not TEFCA). TEFCA is US-specific. Relevance is for future US market entry.

## Decision

**DEFER** TEFCA productionization. Pursue as a US market entry prerequisite, not a pilot requirement.

### Participation Model Decision

When activated, recommend **Framework Participant** (not QHIN) as initial strategy:
- Lower compliance burden than becoming a QHIN
- Connect through existing QHINs (CommonWell or Carequality) as designated participant
- Reduces timeline from 18-24 months (QHIN) to 6-9 months (participant)

### Timeline and Triggers

| Trigger | Action | Timeline |
|---------|--------|----------|
| US customer LOI signed | Begin TEFCA participant onboarding assessment | +0 months |
| Partner QHIN selected | Submit participant application | +2 months |
| Application approved | Build production TEFCA endpoints | +4 months |
| Certification testing | End-to-end QHIN sandbox validation | +6 months |
| Production go-live | Limited production exchange | +9 months |

### Partner Selection Criteria

1. QHIN must support IHE PDQm and MHD (already simulated in codebase)
2. QHIN must have AU/APAC-aware privacy controls OR explicit data residency boundary
3. Prefer QHIN with existing clinical ontology normalization customers
4. Must support Individual Access Services exchange purpose (patient-facing use case)

## Alternatives Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| Pursue QHIN status | Maximum control, direct network access | 18-24 month timeline, high compliance cost, premature | Rejected |
| Framework Participant via CommonWell | Large network, EHR-centric | May overlap with Epic customers | Reserve as option |
| Framework Participant via Carequality | Broadest reach | Complex multi-QHIN routing | **Preferred when activated** |
| Remove TEFCA entirely | Simplifies codebase | Loses US market readiness signal | Rejected |

## Consequences

- TEFCA service remains in scaffold/demonstration mode for current pilot
- No US-specific exchange claims in pilot materials
- `tefca_service.py` maintained for demonstration and future activation
- US market entry timeline: minimum 9 months from decision-to-activate
- Cross-dependency: P4-003 (ONC certification) may accelerate TEFCA readiness

## Evidence Paths

- Current implementation: `backend/app/services/tefca_service.py`
- QHIN discovery: `discover_qhins()` method with 8 simulated networks
- IHE profile support: PDQm (`query_patient`), MHD (`query_documents`, `retrieve_documents`)
- Audit compliance: `audit_query()` ATNA simulation
- This decision: `docs/decisions/p4-002-tefca-strategy.md`
