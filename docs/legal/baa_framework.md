# Business Associate Agreement (BAA) Framework

## Purpose

This document defines the BAA framework for the Clinical Ontology Normalizer
platform operating as a clinical trial patient recruitment system. Because the
platform creates, receives, maintains, and transmits Protected Health
Information (PHI) on behalf of Covered Entities (healthcare providers, health
plans, and clinical trial sponsors), the platform operator is classified as a
**Business Associate** under HIPAA (45 CFR 160.103).

Every relationship in which a third party accesses, stores, processes, or
transmits PHI on behalf of the platform must be governed by a signed BAA
before any PHI is shared.

---

## 1. Covered Entities vs Business Associates

### 1.1 Covered Entities (CEs) in the System Context

| Entity | Role | Relationship |
|---|---|---|
| Healthcare providers (hospitals, clinics) | Supply patient data for trial screening | CE -- the platform acts as their BA |
| Health plans | May supply claims/eligibility data | CE -- the platform acts as their BA |
| Clinical trial sponsors (pharma/biotech) | Define trial criteria, receive de-identified results | May be CE or research entity |

### 1.2 Business Associates (BAs)

The platform operator is a Business Associate to each Covered Entity whose
PHI it processes. The platform must execute a BAA with each CE before
receiving any PHI.

### 1.3 Subcontractors (Sub-BAs)

Under the HITECH Act, Business Associates must obtain BAAs from their own
subcontractors who handle PHI. The platform must execute subcontractor BAAs
with every vendor, cloud provider, or service that touches PHI.

---

## 2. BAA Template -- Required HIPAA Provisions

Every BAA executed by the platform must include the following provisions
per 45 CFR 164.504(e):

### 2.1 Permitted Uses and Disclosures

- BA may use or disclose PHI **only** as permitted by the BAA or as
  required by law.
- BA shall not use or disclose PHI in a manner that would violate HIPAA
  if done by the CE, except for the specific uses listed.
- Permitted purposes: treatment, payment, health care operations,
  clinical trial screening, research (with authorization or waiver),
  and de-identification.

### 2.2 Safeguards

- BA shall implement administrative, physical, and technical safeguards
  that reasonably and appropriately protect the confidentiality,
  integrity, and availability of ePHI.
- BA shall comply with the Security Rule (45 CFR Part 164, Subpart C).
- BA shall implement encryption at rest (AES-256) and in transit (TLS 1.2+).

### 2.3 Reporting

- BA shall report to CE any use or disclosure of PHI not provided for by
  the BAA within **3 business days** of discovery.
- BA shall report any Security Incident (successful or attempted
  unauthorized access) within **3 business days**.
- BA shall report any Breach of Unsecured PHI within **24 hours** of
  discovery (stricter than the HIPAA 60-day window to allow CE adequate
  response time).

### 2.4 Subcontractor Requirements

- BA shall ensure that any subcontractor to whom it provides PHI agrees
  to the same restrictions and conditions that apply to the BA under the
  BAA.
- BA shall obtain a written subcontractor BAA before sharing any PHI.
- BA is responsible for the acts and omissions of its subcontractors.

### 2.5 Access to PHI

- BA shall make PHI available to CE as necessary to satisfy CE's
  obligations under 45 CFR 164.524 (individual access right).
- BA shall respond to individual access requests within **15 business
  days**.

### 2.6 Amendment of PHI

- BA shall make PHI available for amendment and shall incorporate any
  amendments directed by CE, per 45 CFR 164.526.

### 2.7 Accounting of Disclosures

- BA shall maintain and make available the information required to
  provide an accounting of disclosures per 45 CFR 164.528.
- BA shall track all disclosures for a minimum of **6 years**.

### 2.8 Internal Practices and Records

- BA shall make its internal practices, books, and records relating to
  the use and disclosure of PHI available to the Secretary of HHS for
  purposes of determining compliance.

### 2.9 Return or Destruction of PHI

- Upon termination of the BAA, BA shall return or destroy all PHI
  received from CE, or created/received on behalf of CE.
- If return or destruction is not feasible, BA shall extend the
  protections of the BAA to the PHI and limit further uses and
  disclosures to those purposes that make return or destruction
  infeasible.
- Destruction must follow NIST SP 800-88 guidelines for media
  sanitization.
- BA shall certify destruction in writing within **30 days** of
  termination.

### 2.10 Term and Termination

- BAA shall be in effect for the duration of the underlying service
  agreement.
- CE may terminate the BAA if CE determines that BA has violated a
  material term of the BAA.
- BA obligations regarding PHI survive termination of the BAA.

---

## 3. Subcontractor BAA Requirements

### 3.1 Cloud Infrastructure

| Vendor | Service | PHI Exposure | BAA Required | Status |
|---|---|---|---|---|
| AWS | EC2, RDS, S3, EKS | Yes -- stores and processes ePHI | Yes | [ ] Pending |
| Google Cloud | (if used) | Yes | Yes | [ ] N/A |
| Azure | (if used) | Yes | Yes | [ ] N/A |

### 3.2 Health Data Integration

| Vendor | Service | PHI Exposure | BAA Required | Status |
|---|---|---|---|---|
| Metriport | FHIR API, C-CDA exchange | Yes -- transmits and processes PHI | Yes | [ ] Pending |
| Epic/FHIR endpoints | EHR integration | Yes -- receives PHI via SMART on FHIR | Yes (covered by CE BAA) | [ ] Pending |

### 3.3 Data Processing and Analytics

| Vendor | Service | PHI Exposure | BAA Required | Status |
|---|---|---|---|---|
| OpenAI / LLM Provider | Clinical NLP, summarization | Yes if PHI sent to API | Yes | [ ] Pending |
| Neo4j (cloud) | Knowledge graph persistence | Yes -- stores patient graph data | Yes | [ ] Pending |
| Redis (cloud) | Job queue, caching | Possible -- may cache PHI temporarily | Yes | [ ] Pending |

### 3.4 Monitoring and Operations

| Vendor | Service | PHI Exposure | BAA Required | Status |
|---|---|---|---|---|
| Sentry / Error tracking | Error logs | Possible -- stack traces may contain PHI | Yes | [ ] Pending |
| Datadog / monitoring | Application metrics | Low risk but logs may contain PHI | Yes | [ ] Pending |
| PagerDuty | Incident alerts | Low risk -- alert text may reference PHI | Evaluate | [ ] Pending |

### 3.5 Communication

| Vendor | Service | PHI Exposure | BAA Required | Status |
|---|---|---|---|---|
| SendGrid / Email | Patient notifications | Yes -- email content may contain PHI | Yes | [ ] Pending |
| Twilio / SMS | Patient notifications | Yes -- SMS content may contain PHI | Yes | [ ] Pending |

---

## 4. BAA Tracking Checklist

### 4.1 Pre-Execution Checklist

For each vendor relationship involving PHI:

- [ ] Identify PHI data elements that will be shared
- [ ] Determine minimum necessary scope
- [ ] Verify vendor's HIPAA compliance posture (SOC 2 Type II, HITRUST)
- [ ] Review vendor's security practices and incident response plan
- [ ] Draft BAA using approved template
- [ ] Legal review of BAA terms
- [ ] Obtain authorized signatures from both parties
- [ ] Record BAA execution date and expiration in the BAA registry
- [ ] Store executed BAA in secure document management system

### 4.2 Ongoing Monitoring

- [ ] Annual review of all active BAAs
- [ ] Verify vendor compliance attestations are current
- [ ] Update BAA registry with any vendor changes
- [ ] Re-execute BAAs when material changes occur
- [ ] Track subcontractor BAA chain (vendor's vendors)

### 4.3 BAA Registry Fields

Each BAA record must capture:

| Field | Description |
|---|---|
| vendor_name | Legal name of the Business Associate |
| vendor_contact | Primary compliance contact |
| baa_execution_date | Date BAA was signed |
| baa_expiration_date | Expiration or renewal date |
| phi_categories | Categories of PHI shared (demographics, clinical, genomic, etc.) |
| permitted_uses | Specific permitted uses under the BAA |
| data_flow_direction | Inbound, outbound, or bidirectional |
| encryption_requirements | Encryption standards required |
| breach_notification_sla | Hours/days for breach notification |
| last_compliance_review | Date of last compliance review |
| status | Active, Expired, Terminated |

---

## 5. Incident Notification Provisions

### 5.1 Breach Response Timeline

| Event | Deadline | Responsible Party |
|---|---|---|
| Discovery of potential breach | Immediate internal escalation | BA Security Team |
| Notification to CE | Within 24 hours of discovery | BA Privacy Officer |
| Risk assessment completion | Within 48 hours | BA Security Team |
| CE notification to individuals | Within 60 days (per HIPAA) | CE |
| CE notification to HHS | Within 60 days (or annual for <500) | CE |
| Media notification (if >500 residents of a state) | Within 60 days | CE |

### 5.2 Incident Classification

| Level | Description | Example |
|---|---|---|
| Level 1 -- Critical | Confirmed breach of unsecured PHI affecting 500+ individuals | Database exfiltration |
| Level 2 -- High | Confirmed breach affecting <500 individuals | Misdirected PHI, lost device |
| Level 3 -- Medium | Security incident without confirmed PHI exposure | Failed intrusion attempt with PHI access |
| Level 4 -- Low | Security event with no PHI exposure | Unsuccessful login attempts |

### 5.3 Required Breach Notification Content

Per 45 CFR 164.404(c), breach notifications must include:

1. Description of the breach, including date(s)
2. Types of PHI involved (names, SSNs, diagnoses, etc.)
3. Steps individuals should take to protect themselves
4. Description of what the entity is doing to investigate and mitigate
5. Contact information for questions

---

## 6. Data Use Limitations

### 6.1 Minimum Necessary Standard

All PHI access and disclosure must comply with the Minimum Necessary
standard (45 CFR 164.502(b)):

- **Role-based access**: Users see only PHI necessary for their role
- **Purpose limitation**: PHI used only for the stated purpose
- **Data segmentation**: Sensitive categories (behavioral health,
  substance abuse, HIV, genetic) require additional controls per
  42 CFR Part 2 and state laws
- **De-identification**: Where possible, use de-identified data
  (Safe Harbor or Expert Determination per 45 CFR 164.514)

### 6.2 Research Use

PHI used for clinical trial screening requires one of:

1. **Individual HIPAA authorization** (preferred path for this platform)
2. **IRB/Privacy Board waiver** of authorization (45 CFR 164.512(i))
3. **Preparatory to research** exception (limited, no PHI removal)
4. **De-identified dataset** (no authorization needed)

### 6.3 Prohibited Uses

PHI shall NOT be used for:

- Marketing (without valid authorization)
- Sale of PHI
- Employment decisions
- Underwriting
- Any purpose not specified in the BAA

---

## 7. Audit Rights

### 7.1 CE Audit Rights

The CE retains the right to:

- Audit BA's compliance with the BAA and HIPAA requirements
- Request evidence of security controls and risk assessments
- Review BA's subcontractor BAA chain
- Inspect BA's breach notification and incident response records
- Request penetration test results and vulnerability assessments

### 7.2 Audit Frequency

- **Annual**: Comprehensive compliance audit
- **Quarterly**: Review of access logs and security incidents
- **On-demand**: Following any security incident or breach
- **Pre-contract**: Initial security assessment before BAA execution

### 7.3 Audit Deliverables

BA shall provide upon request:

- SOC 2 Type II report (or equivalent)
- HIPAA risk assessment (annual)
- Security incident log
- Access control review results
- Encryption verification
- Business continuity/disaster recovery test results
- Employee training completion records
- Subcontractor BAA inventory

---

## 8. Implementation Notes

### 8.1 System-Level Controls

The platform implements the following controls to support BAA compliance:

1. **Consent service** (`consent_service.py`): Tracks patient HIPAA
   authorizations and research consent before PHI access
2. **Audit middleware** (`AuditMiddleware`): Logs all PHI access with
   user, timestamp, and purpose
3. **RBAC service** (`rbac_service.py`): Enforces role-based access
   to PHI
4. **Encryption**: TLS 1.2+ in transit, AES-256 at rest (database,
   backups, file storage)
5. **Access logging**: All API access to patient endpoints logged with
   request ID for audit trail

### 8.2 Key Regulatory References

- 45 CFR 160.103 -- Definitions (Business Associate, Covered Entity)
- 45 CFR 164.502(e) -- BA contractual requirements
- 45 CFR 164.504(e) -- BAA required provisions
- 45 CFR 164.308 -- Administrative safeguards
- 45 CFR 164.310 -- Physical safeguards
- 45 CFR 164.312 -- Technical safeguards
- 45 CFR 164.400-414 -- Breach notification requirements
- HITECH Act Section 13401 -- BA direct liability
