# Right-to-Deletion Policy

## Clinical Trial Patient Recruitment Platform

**Policy Version:** 1.0
**Effective Date:** [Date]
**Last Reviewed:** [Date]
**Policy Owner:** Chief Privacy Officer

---

## 1. Scope

This policy governs the right of individuals to request deletion of their personal data from the clinical trial patient recruitment platform. It applies to:

- All patient data stored in the platform
- Data shared with clinical trial sites, sponsors, and vendors
- Data in all storage systems including databases, knowledge graphs, and document stores

## 2. Regulatory Basis

This policy implements deletion rights under:

- **HIPAA Privacy Rule** (45 CFR 164.524): Right to request amendment/restriction of PHI
- **GDPR Article 17**: Right to erasure ("right to be forgotten")
- **CCPA/CPRA**: Right to deletion of personal information
- **21 CFR Part 11**: Electronic records retention requirements for clinical trials

## 3. Eligibility

The following individuals may submit a deletion request:

- The patient (data subject) themselves
- A legally authorized representative
- A parent or guardian (for minors)
- An executor of a deceased patient's estate

Identity verification is required before processing any deletion request.

## 4. Verification Requirements

Before processing a deletion request, the platform shall verify:

1. **Identity:** Government-issued ID or matching credentials on file
2. **Authority:** Proof of legal authorization (if not the data subject)
3. **Scope:** Clear specification of what data should be deleted

Verification must be completed within 5 business days of request receipt.

## 5. Process

### 5.1 Request Submission

Deletion requests may be submitted via:
- The platform's data governance API
- Written request to the Privacy Officer
- Through the patient portal (when available)

### 5.2 Request Lifecycle

| Status | Description | Timeline |
|--------|-------------|----------|
| RECEIVED | Request logged with timestamp | Day 0 |
| VALIDATING | Identity verification, legal hold and retention checks | Days 1-5 |
| IN_PROGRESS | Deletion executing across all data stores | Days 6-25 |
| COMPLETED | All eligible data deleted, certificate issued | By Day 30 |
| DENIED | Request denied with documented reason | Within 10 days |
| PARTIALLY_COMPLETED | Some data deleted, exceptions documented | By Day 30 |

### 5.3 Response Timeline

- **Acknowledgment:** Within 2 business days of receipt
- **Completion:** Within 30 calendar days of receipt (GDPR requirement)
- **Extension:** Up to 60 additional days with notification (complex requests)

## 6. Data Inventory for Deletion

The following data stores are checked and processed:

| Data Store | Action | Notes |
|-----------|--------|-------|
| clinical_facts | DELETE | All patient clinical facts |
| kg_nodes / kg_edges | DELETE | Knowledge graph patient nodes and relationships |
| documents | DELETE | Clinical documents and associated metadata |
| screening_results | DELETE | Trial screening and eligibility results |
| audit_logs | RETAIN + REDACT | Retained per legal requirement; PHI fields redacted |
| backups | FLAG | Flagged for deletion on next backup rotation cycle |

## 7. Exceptions

Deletion may be denied or limited in the following circumstances:

### 7.1 Legal Holds

If the patient is subject to active litigation, investigation, or legal proceedings, deletion is suspended until the hold is released. The requestor will be notified of the hold (without disclosing investigation details).

### 7.2 Clinical Trial Data Retention

Per **21 CFR Part 11**, clinical trial data must be retained for a minimum of **6 years** from the date of trial completion or patient enrollment. During this period:

- PHI may be further restricted in access
- De-identification may be applied where possible
- Full deletion will be scheduled for the earliest permissible date

### 7.3 Public Health Requirements

Data required for public health reporting, adverse event tracking, or FDA-mandated safety monitoring may not be deleted.

### 7.4 Audit Trail Integrity

Audit log entries documenting data access and processing are retained to maintain compliance audit trails. PHI within audit logs is redacted rather than deleted.

## 8. Partial Deletion

When full deletion is not possible, partial deletion is performed:

- **PHI_ONLY scope:** Remove identifiable information while retaining de-identified data
- **SPECIFIC_RECORDS scope:** Delete only specified record types
- The requestor is informed of what was and was not deleted

## 9. Deletion Certificate

Upon completion, a deletion certificate is issued documenting:

- What data was deleted (by category)
- What data was retained (with legal justification)
- Any exceptions or limitations
- Backup purge schedule
- Compliance statement

The certificate is retained as part of the platform's compliance records.

## 10. Third-Party Notification

When patient data has been shared with third parties under Data Use Agreements:

- Third parties are notified of the deletion request within 5 business days
- Third parties must confirm deletion within 30 days
- Confirmation is documented in the deletion certificate

## 11. Audit and Accountability

- All deletion requests and actions are logged in the audit trail
- The Privacy Officer reviews deletion activity quarterly
- Annual compliance audits include deletion request review
- Metrics tracked: request volume, completion time, denial rate, exception frequency

## 12. Staff Training

All personnel involved in deletion request processing must complete:

- HIPAA Privacy and Security training (annual)
- Platform-specific deletion procedure training
- Identity verification procedure training

## 13. Policy Review

This policy is reviewed annually and updated to reflect:

- Changes in applicable law or regulation
- Platform capability changes
- Lessons learned from deletion request processing
- Regulatory guidance updates
