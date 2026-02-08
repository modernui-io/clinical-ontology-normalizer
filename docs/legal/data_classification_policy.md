# Data Classification Policy and Handling Procedures

**CLO-3: Data Classification Policy**
**Version**: 1.0
**Effective Date**: 2026-01-14
**Last Reviewed**: 2026-01-14
**Owner**: Chief Information Security Officer (CISO)
**Approved By**: Executive Leadership Team

---

## 1. Purpose

This policy establishes a framework for classifying data assets based on sensitivity, regulatory requirements, and business impact. It defines handling procedures that ensure appropriate protections are applied throughout the data lifecycle, aligned with HIPAA, NIST SP 800-60, and 21 CFR Part 11 requirements.

## 2. Scope

This policy applies to all data created, collected, processed, stored, transmitted, or disposed of by the clinical trial patient recruitment platform, including:

- Patient health information and identifiers
- Clinical trial protocols and results
- Business and operational data
- System logs and audit trails
- Third-party data received under Data Use Agreements

## 3. Classification Levels

### 3.1 PUBLIC

**Definition**: Information intended for public disclosure. Unauthorized disclosure would have no adverse impact on the organization or individuals.

**Examples**:
- Marketing materials and website content
- General trial information (NCT numbers, conditions studied)
- Public API documentation
- Published research abstracts

**Severity**: Lowest (0)

### 3.2 INTERNAL

**Definition**: Information intended for internal use only. Unauthorized disclosure could cause minor operational disruption but no regulatory violation.

**Examples**:
- Internal analytics dashboards
- Aggregated and anonymized reports
- System performance logs
- OMOP vocabulary reference data
- API usage metrics

**Severity**: Low (1)

### 3.3 CONFIDENTIAL

**Definition**: Sensitive business or de-identified patient data. Unauthorized disclosure could cause significant reputational, financial, or competitive harm.

**Examples**:
- De-identified patient datasets
- Trial protocol details and amendments
- Business metrics and financial data
- Internal audit reports (without patient data)
- Vendor contracts and SLAs
- Data Use Agreement records

**Severity**: High (2)

### 3.4 RESTRICTED

**Definition**: Highest sensitivity data requiring maximum protection. Includes PHI, PII, credentials, and encryption keys. Unauthorized disclosure could result in HIPAA penalties, legal liability, and patient harm.

**Examples**:
- Protected Health Information (PHI)
- Personally Identifiable Information (PII)
- Database credentials and API keys
- Encryption keys and certificates
- Audit logs containing patient data
- Patient screening results with identifiers
- Informed consent records

**Severity**: Critical (3)

## 4. Handling Procedures

### 4.1 PUBLIC Data

| Control | Requirement |
|---------|------------|
| **Storage** | No encryption required; standard backup |
| **Access** | No authentication required |
| **Transmission** | No encryption required |
| **Retention** | No default retention; dispose when obsolete |
| **Disposal** | Standard delete |
| **Incident Response** | No notification required |
| **Sharing** | Unrestricted |

### 4.2 INTERNAL Data

| Control | Requirement |
|---------|------------|
| **Storage** | Encrypted backups |
| **Access** | Authenticated access; standard logging |
| **Transmission** | TLS 1.2+ required |
| **Retention** | 2 years default |
| **Disposal** | Standard delete |
| **Incident Response** | Internal notification recommended |
| **Sharing** | Internal: authenticated; External: with approval |

### 4.3 CONFIDENTIAL Data

| Control | Requirement |
|---------|------------|
| **Storage** | AES-256 encryption at rest; encrypted backups; US-only |
| **Access** | Role-based access; need-to-know; full audit logging |
| **Transmission** | TLS 1.2+; secure channels only |
| **Retention** | 6 years (21 CFR Part 11) |
| **Disposal** | Secure erase with verification |
| **Incident Response** | Notification within 72 hours; breach report required |
| **Sharing** | Internal: role-based; External: DUA required; de-identification required |

### 4.4 RESTRICTED Data

| Control | Requirement |
|---------|------------|
| **Storage** | AES-256-GCM encryption at rest; isolated storage; encrypted backups; US-only HIPAA-compliant facility |
| **Access** | MFA required; role-based; DUA required; need-to-know; full audit logging |
| **Transmission** | TLS 1.3+; VPN required; secure channels only |
| **Retention** | 6 years minimum (21 CFR Part 11) |
| **Disposal** | Cryptographic shredding with verification |
| **Incident Response** | Notification within 24 hours; HHS and patient notification required |
| **Sharing** | Internal: role-based only; External: prohibited; Third-party: prohibited |

## 5. Roles and Responsibilities

### 5.1 Data Owner

The senior leader accountable for a data asset. Responsible for:
- Approving initial data classification
- Authorizing access to data assets
- Reviewing and approving reclassification requests
- Ensuring compliance with retention policies
- Participating in periodic classification reviews

**Required for**: CONFIDENTIAL and RESTRICTED data

### 5.2 Data Steward

Subject matter expert for day-to-day management. Responsible for:
- Maintaining accurate metadata and classification
- Conducting periodic classification reviews
- Identifying data quality issues
- Recommending reclassification when needed
- Training staff on data handling procedures

**Required for**: INTERNAL, CONFIDENTIAL, and RESTRICTED data

### 5.3 Data Custodian

IT/infrastructure team implementing technical controls. Responsible for:
- Implementing encryption per classification requirements
- Configuring access controls and RBAC
- Managing backups and disaster recovery
- Monitoring for unauthorized access
- Executing disposal procedures

**Required for**: INTERNAL, CONFIDENTIAL, and RESTRICTED data

### 5.4 Privacy Officer

Oversees HIPAA and privacy compliance. Responsible for:
- Reviewing RESTRICTED data asset classifications
- Conducting privacy impact assessments
- Investigating potential breaches
- Ensuring HIPAA compliance
- Approving external data sharing agreements

**Required for**: RESTRICTED data

## 6. Classification Review Process

### 6.1 Review Frequency

| Classification | Review Frequency |
|---------------|-----------------|
| PUBLIC | Annual |
| INTERNAL | Annual |
| CONFIDENTIAL | Semi-annual |
| RESTRICTED | Quarterly |

### 6.2 Review Procedure

1. Data Steward initiates review at the scheduled interval
2. Data Steward verifies classification accuracy against current data content
3. Data Steward recommends continuation or reclassification
4. Data Owner approves the review outcome
5. System records the review completion and resets the review clock

### 6.3 Overdue Reviews

The system automatically flags assets with overdue reviews. Overdue assets appear in the governance dashboard and trigger alerts to the Data Steward and Data Owner.

## 7. Reclassification Process

### 7.1 Workflow

1. **Request**: Any authorized user submits a reclassification request with justification
2. **Review**: Data Owner (and Privacy Officer for RESTRICTED) reviews the request
3. **Approve/Reject**: Reviewer approves or rejects with documented rationale
4. **Update**: If approved, classification is updated with full audit trail
5. **Controls**: Handling procedures are automatically updated to match the new level

### 7.2 Reclassification Triggers

- Change in data content or usage
- Regulatory requirement changes
- Business process changes
- Periodic review findings
- Incident response findings
- De-identification of previously restricted data

### 7.3 Audit Trail

All reclassification actions are logged with:
- Request details and justification
- Reviewer identity and decision
- Timestamp of each state transition
- Previous and new classification levels

## 8. Enforcement

### 8.1 Technical Controls

- The platform enforces handling rules programmatically
- Access controls are checked at API boundaries
- Encryption is applied automatically based on classification
- Audit logging captures all access to CONFIDENTIAL and RESTRICTED data

### 8.2 Violations

Violations of this policy may result in:
- Immediate access revocation
- Security incident investigation
- Regulatory reporting (if PHI involved)
- Disciplinary action per organizational policy

### 8.3 Exceptions

Exceptions to this policy require:
- Written request with business justification
- Risk assessment by the Privacy Officer
- Approval by the CISO
- Time-limited duration with re-evaluation date
- Compensating controls documented

## 9. Data Asset Inventory

The platform maintains an automated inventory of 30+ data assets, each tracked with:
- Unique asset identifier
- Classification level
- Data Owner and Data Steward
- Storage location
- Retention period
- Encryption status
- Access restrictions
- Review frequency and due dates
- Associated handling rules

The inventory is accessible via the `/governance/classification/assets` API endpoint.

## 10. Regulatory Alignment

| Regulation | Requirement | How Addressed |
|-----------|------------|---------------|
| HIPAA Security Rule | Administrative, physical, technical safeguards | Classification-based handling rules |
| HIPAA Privacy Rule | Minimum necessary use | Need-to-know access for CONFIDENTIAL/RESTRICTED |
| 21 CFR Part 11 | Electronic records integrity | Audit trails, encryption, access controls |
| NIST SP 800-60 | Information categorization | Four-level classification aligned to FIPS 199 |
| GDPR (if applicable) | Data protection by design | Classification drives technical controls |

## 11. Related Policies

- CLO-1: Business Associate Agreements (BAA Framework)
- CLO-2: Data Use Agreements and Right-to-Deletion
- CLO-4: Incident Response Plan
- CLO-5: Access Control Policy
- SOC 2 Trust Services Criteria

## 12. Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-14 | CISO | Initial policy |
