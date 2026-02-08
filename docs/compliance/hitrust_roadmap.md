# HITRUST CSF v11 Certification Roadmap

**CISO-13** | Clinical Trial Patient Recruitment Platform

## Executive Summary

This document outlines the HITRUST CSF v11 certification roadmap for the clinical trial patient recruitment platform. The assessment covers all 14 HITRUST control categories with 50+ controls mapped to platform features, identifying current maturity levels and a phased approach to achieving certification readiness.

## Current Maturity Assessment

### Category Overview

| # | Category | Controls | Avg Maturity | Readiness |
|---|----------|----------|-------------|-----------|
| 0 | Information Security Management Program | 4 | IMPLEMENTED | Moderate |
| 1 | Access Control | 6 | IMPLEMENTED | Good |
| 2 | Human Resources Security | 3 | POLICY | Low |
| 3 | Risk Management | 4 | PROCEDURE | Moderate |
| 4 | Security Policy | 3 | POLICY | Low |
| 5 | Organization of Information Security | 3 | POLICY | Low |
| 6 | Compliance | 4 | PROCEDURE | Moderate |
| 7 | Asset Management | 3 | PROCEDURE | Moderate |
| 8 | Physical and Environmental Security | 3 | NOT_STARTED | Low |
| 9 | Communications and Operations Management | 5 | IMPLEMENTED | Good |
| 10 | Systems Acquisition, Development, Maintenance | 5 | IMPLEMENTED | Good |
| 11 | Information Security Incident Management | 4 | IMPLEMENTED | Good |
| 12 | Business Continuity Management | 4 | PROCEDURE | Moderate |
| 13 | Privacy Practices | 5 | IMPLEMENTED | Good |

### Maturity Level Definitions

| Level | Score | Description |
|-------|-------|-------------|
| NOT_STARTED | 0 | Control not yet addressed |
| POLICY | 1 | Documented in policy |
| PROCEDURE | 2 | Procedures implemented |
| IMPLEMENTED | 3 | Operationally deployed |
| MEASURED | 4 | Monitored with metrics |
| MANAGED | 5 | Continuously improved |

## Gap Analysis

### Critical Gaps (NOT_STARTED Controls)

1. **00.c** - Security Program Review: No formal periodic review process
2. **01.f** - Multi-Factor Authentication: MFA not implemented for platform access
3. **02.b** - Security Awareness Training: No formal training program
4. **03.d** - Third-Party Risk Management: No vendor risk assessment process
5. **04.b** - Policy Review: No formal policy review cadence
6. **05.c** - Contact with Special Interest Groups: No H-ISAC membership
7. **06.d** - Data Protection Impact Assessment: No DPIA process
8. **07.c** - Media Handling and Disposal: No formal procedures
9. **08.a/b/c** - Physical and Environmental Security: Cloud-hosted, need documentation
10. **09.e** - Malware Protection: No documented strategy
11. **12.c** - Recovery Testing: No BCP/DR testing program

### Partially Mature Controls (POLICY or PROCEDURE)

Controls at POLICY or PROCEDURE level that need advancement:
- Access control password policy enforcement
- HR security role formalization
- Risk treatment plan documentation
- Network security documentation
- Vulnerability management process
- Business continuity planning
- Privacy notice publication

## 4-Phase Certification Roadmap

### Phase 1: Quick Wins (Weeks 1-4)

**Objective**: Address low-effort, high-impact controls to establish baseline compliance.

**Focus Areas**:
- Document security roles and responsibilities (RACI matrix)
- Publish information security policy
- Formalize existing operational procedures
- Verify existing controls meet HITRUST requirements

**Controls Addressed**:
- 00.b: Security Roles and Responsibilities
- 04.a: Information Security Policy

**Estimated Effort**: Variable (see API for current calculations)

### Phase 2: Foundational Controls (Weeks 5-16)

**Objective**: Implement core security controls required for HITRUST certification.

**Focus Areas**:
- Implement multi-factor authentication
- Develop security awareness training program
- Formalize HR security procedures
- Document risk treatment plans
- Establish vulnerability management process
- Build comprehensive Business Continuity Plan
- Publish privacy notice

**Key Deliverables**:
1. MFA implementation for all user accounts
2. Annual security awareness training program
3. Automated access revocation on termination
4. Formal risk treatment plans
5. Network security documentation
6. Business Continuity Plan with RTOs/RPOs
7. Comprehensive privacy notice

**Controls Addressed**:
- 01.e, 01.f: Password policy and MFA
- 02.a, 02.b, 02.c: HR security controls
- 03.b: Risk treatment
- 05.a: Internal organization
- 07.a: Asset inventory
- 09.d, 09.e: Network security and malware protection
- 10.d, 10.e: Acceptance testing and vulnerability management
- 12.a, 12.d: Business continuity and redundancy
- 13.c, 13.d: Privacy notice and data minimization

**Estimated Effort**: ~400 hours

### Phase 3: Advanced Controls (Weeks 17-26)

**Objective**: Deploy advanced controls including monitoring, incident response maturation, and privacy enhancements.

**Focus Areas**:
- Establish security program review process
- Implement third-party risk management
- Formalize incident lessons-learned process
- Document cloud provider physical security controls
- Implement data protection impact assessments
- Establish regulatory compliance monitoring

**Key Deliverables**:
1. Quarterly security program review process
2. Vendor risk assessment questionnaire and register
3. Post-incident review templates
4. Cloud provider security documentation
5. DPIA templates and process
6. Regulatory change monitoring

**Controls Addressed**:
- 00.c: Security program review
- 03.d: Third-party risk management
- 04.b: Policy review
- 05.b: Contact with authorities
- 06.b, 06.d: Regulatory monitoring and DPIA
- 07.c: Media handling
- 08.a, 08.b, 08.c: Physical/environmental documentation
- 11.d: Lessons learned
- 12.c: Recovery testing

**Estimated Effort**: ~250 hours

### Phase 4: Certification Readiness (Weeks 27-32)

**Objective**: Final preparation for HITRUST certification assessment.

**Focus Areas**:
- Evidence collection and organization
- Internal audit and control testing
- Assessor selection and preparation
- Gap remediation verification

**Key Deliverables**:
1. Complete evidence package for all controls
2. Internal audit report
3. Corrective action plans for any remaining gaps
4. Assessor engagement and readiness review

**Controls Addressed**:
- 05.c: Special interest group contacts (H-ISAC)
- Final evidence collection across all categories

**Estimated Effort**: ~100 hours

## Resource Requirements

### Personnel

| Role | Commitment | Duration |
|------|-----------|----------|
| Security Lead | 50% FTE | 32 weeks |
| Compliance Analyst | 75% FTE | 32 weeks |
| Engineering Team | 25% FTE | 16 weeks |
| Privacy Officer | 25% FTE | 20 weeks |
| External Assessor | Engagement | Weeks 27-32 |

### Budget Considerations

- HITRUST Assessment Fee (e1 Assessment)
- External assessor engagement
- Security training platform
- MFA infrastructure
- H-ISAC membership
- Ongoing monitoring tools

## Monitoring and Tracking

The HITRUST compliance status is tracked programmatically via the platform API:

- **Controls**: `GET /api/v1/compliance/hitrust/controls`
- **Readiness**: `GET /api/v1/compliance/hitrust/readiness`
- **Roadmap**: `GET /api/v1/compliance/hitrust/roadmap`
- **Categories**: `GET /api/v1/compliance/hitrust/categories`
- **Evidence**: `POST /api/v1/compliance/hitrust/evidence`

## Revision History

| Date | Version | Author | Changes |
|------|---------|--------|---------|
| 2026-02-08 | 1.0 | Security Team | Initial assessment and roadmap |
