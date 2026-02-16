# Threat Model Update Cadence

**Document ID**: SEC-P2-026
**Version**: 1.0
**Effective Date**: 2026-02-15
**Owner**: CISO
**Classification**: Internal — Security Governance

## Purpose

Tie threat model updates to the release cycle, ensuring security posture evolves with the platform.

## Update Triggers

| Trigger | Update Scope | Timeline |
|---|---|---|
| Major release (new feature domain) | Full threat model review | Before release |
| New external integration | Integration-specific threat assessment | Before go-live |
| Security incident (SEV-1/SEV-2) | Targeted update for affected attack surface | Within 1 week post-incident |
| Quarterly review cycle | Comprehensive review of all threat categories | Every 90 days |
| Regulatory change | Compliance-driven threat reassessment | Within 30 days of notification |
| Infrastructure change | Infrastructure-specific update | Before deployment |

## Threat Categories

| Category | Last Reviewed | Next Review | Owner |
|---|---|---|---|
| Authentication & Authorization | | | CISO |
| PHI Data Protection | | | CISO + Compliance |
| External API Exposure | | | CTO |
| LLM/AI Supply Chain | | | Clinical AI Lead |
| Infrastructure & Network | | | Operations |
| Insider Threat | | | CISO + HR |
| Third-Party/Vendor | | | CIO |
| Interoperability (FHIR/OpenEHR) | | | Interop Lead |

## Review Process

1. **Preparation** (1 week before): Gather change log since last review, new CVEs, incident reports
2. **Workshop** (2 hours): CISO + CTO + domain leads review each category
3. **Documentation** (1 week after): Update threat model document with findings
4. **Action Items**: Create backlog items for identified gaps
5. **Sign-off**: CISO approves updated model

## Deliverables

- Updated `docs/security/threat_model.md` (versioned)
- New backlog items for identified gaps
- Risk register updates for new/changed risks
- Executive summary for quarterly report

## Metrics

| Metric | Target |
|---|---|
| Threat model age | <90 days |
| Open threat items | <5 high-severity |
| Average time to mitigate | <30 days for high |
| Categories reviewed per quarter | All 8 |
