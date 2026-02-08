# Incident Response Plan

**Document ID:** CISO-11-IRP
**Version:** 1.0
**Effective Date:** 2026-02-08
**Last Reviewed:** 2026-02-08
**Next Review:** 2027-02-08
**Classification:** CONFIDENTIAL
**Owner:** Chief Information Security Officer (CISO)

---

## Table of Contents

1. [Purpose and Scope](#1-purpose-and-scope)
2. [Incident Classification](#2-incident-classification)
3. [Roles and Responsibilities](#3-roles-and-responsibilities)
4. [Detection and Reporting](#4-detection-and-reporting)
5. [Response Procedures by Severity](#5-response-procedures-by-severity)
6. [HIPAA Breach Notification](#6-hipaa-breach-notification)
7. [Evidence Preservation](#7-evidence-preservation)
8. [Communication Templates](#8-communication-templates)
9. [Post-Incident](#9-post-incident)

---

## 1. Purpose and Scope

### 1.1 Purpose

This Incident Response Plan (IRP) establishes a structured approach for identifying, responding to, containing, eradicating, and recovering from security incidents affecting the Clinical Ontology Normalizer platform. The plan ensures that security incidents -- particularly those involving Protected Health Information (PHI) -- are handled in compliance with applicable regulations and with minimal impact to patients, clinical operations, and organizational integrity.

### 1.2 Scope

This plan applies to:

- **All systems** within the Clinical Ontology Normalizer platform, including backend services (FastAPI), frontend applications (Next.js), databases (PostgreSQL, Redis, Neo4j), and supporting infrastructure
- **All environments**: production, staging, development, and disaster recovery
- **All personnel** who develop, operate, administer, or have access to the platform
- **All data** processed by the platform, including PHI, clinical trial data, OMOP-mapped concepts, knowledge graph data, and FHIR resources
- **Third-party integrations** including Metriport, SMART on FHIR endpoints, and TEFCA connections

### 1.3 Applicable Regulations

| Regulation | Relevance |
|---|---|
| HIPAA Privacy Rule (45 CFR 164.500-534) | Governs use and disclosure of PHI |
| HIPAA Security Rule (45 CFR 164.302-318) | Administrative, physical, and technical safeguards |
| HITECH Act (42 USC 17932) | Breach notification requirements, penalty enhancements |
| HIPAA Breach Notification Rule (45 CFR 164.400-414) | Notification timelines and procedures |
| 21 CFR Part 11 | Electronic records and signatures (clinical trial context) |
| State breach notification laws | Varying requirements by jurisdiction |
| NIST SP 800-61 Rev 2 | Computer security incident handling guide (framework reference) |

### 1.4 Plan Maintenance

This plan shall be:

- **Reviewed annually** or after any significant incident
- **Tested** via tabletop exercises at least twice annually
- **Updated** within 30 days of any material change to systems, regulations, or organizational structure
- **Distributed** to all incident response team members within 5 business days of any update

---

## 2. Incident Classification

### 2.1 Severity Levels

| Severity | Name | Description | Response SLA | Example |
|---|---|---|---|---|
| **SEV1** | Critical / Data Breach | Confirmed or highly probable PHI breach, active data exfiltration, ransomware, or complete system compromise | Acknowledge: 15 min, Contain: 1 hr, IC assigned: 15 min | Confirmed PHI exfiltration, ransomware encryption of production DB, compromised admin credentials with evidence of data access |
| **SEV2** | High / Service Outage | Major service degradation or outage affecting clinical operations, unauthorized access without confirmed data exfiltration, or significant security control failure | Acknowledge: 30 min, Contain: 4 hr | Production API down, database unavailable, authentication bypass discovered, failed but detected intrusion attempt |
| **SEV3** | Medium / Security Event | Security policy violation, suspicious activity requiring investigation, or minor security control degradation | Acknowledge: 4 hr, Investigate: 24 hr | Repeated failed login attempts from single IP, minor misconfiguration discovered, unusual API usage pattern, expired certificate |
| **SEV4** | Low / Anomaly | Informational security event, anomalous but non-threatening activity, or minor policy deviation | Acknowledge: 24 hr, Review: 72 hr | Single failed login, informational SIEM alert, minor log anomaly, routine vulnerability scan detection |

### 2.2 Incident Types

| Type | Description | Default Severity | PHI Risk |
|---|---|---|---|
| **PHI Breach** | Unauthorized acquisition, access, use, or disclosure of PHI | SEV1 | Critical |
| **Unauthorized Access** | Access to systems or data without proper authorization | SEV1-SEV2 | High |
| **Data Exfiltration** | Unauthorized transfer of data outside organizational boundaries | SEV1 | Critical |
| **Ransomware** | Malware that encrypts data and demands payment | SEV1 | Critical |
| **DDoS** | Distributed denial of service attack | SEV2 | Low |
| **Insider Threat** | Malicious or negligent activity by authorized personnel | SEV1-SEV2 | High |
| **System Compromise** | Unauthorized modification or control of system components | SEV1-SEV2 | High |
| **Credential Leak** | Exposure of authentication credentials (API keys, passwords, tokens) | SEV2-SEV3 | Medium |
| **Vulnerability Exploitation** | Active exploitation of a known or zero-day vulnerability | SEV1-SEV2 | High |
| **Configuration Error** | Security-relevant misconfiguration discovered | SEV3-SEV4 | Medium |

### 2.3 Severity Escalation Criteria

An incident MUST be escalated to a higher severity if:

- PHI exposure is confirmed or newly suspected
- The scope of affected systems or users increases
- Containment efforts fail or are circumvented
- A regulatory reporting threshold is reached (500+ individuals for HHS OCR)
- Media or public attention is received
- Law enforcement involvement is required or recommended

---

## 3. Roles and Responsibilities

### 3.1 Incident Response Team (IRT)

| Role | Primary Responsibility | Backup |
|---|---|---|
| **Incident Commander (IC)** | Overall incident coordination, decision authority, communication orchestration | CISO or designated alternate |
| **Security Lead** | Technical security analysis, forensics, containment strategy | Senior Security Engineer |
| **Engineering Lead** | System remediation, service restoration, technical implementation | Senior Platform Engineer |
| **Legal / Compliance Officer** | Regulatory assessment, breach determination, notification requirements | External legal counsel |
| **Communications Lead** | Internal and external communications, media relations | VP of Marketing / PR |
| **Clinical Safety Officer** | Patient safety assessment, clinical workflow impact analysis | Chief Medical Officer |
| **Privacy Officer** | PHI impact assessment, individual notification coordination | Compliance Manager |
| **IT Operations Lead** | Infrastructure support, log collection, system access management | Sr. DevOps Engineer |

### 3.2 RACI Matrix

**R** = Responsible, **A** = Accountable, **C** = Consulted, **I** = Informed

| Activity | IC | Security Lead | Engineering Lead | Legal / Compliance | Communications | Clinical Safety | Privacy Officer |
|---|---|---|---|---|---|---|---|
| **Initial triage** | A | R | C | I | I | I | I |
| **Severity classification** | A | R | C | C | I | C | C |
| **Containment** | A | R | R | C | I | C | I |
| **Evidence preservation** | A | R | C | C | I | I | I |
| **PHI breach determination** | I | C | I | A | I | C | R |
| **Eradication** | A | C | R | I | I | I | I |
| **Recovery** | A | C | R | I | I | C | I |
| **HIPAA notification** | I | I | I | A | R | I | R |
| **Internal communication** | A | I | I | C | R | I | I |
| **External communication** | A | I | I | C | R | I | C |
| **Post-incident review** | A | R | R | C | I | C | C |
| **CAPA implementation** | A | R | R | C | I | C | I |

### 3.3 Contact Information

Maintain a separate, secure, and regularly updated contact roster containing:

- Primary and secondary phone numbers for all IRT members
- Encrypted email addresses
- Secure messaging handles (e.g., Signal)
- Physical addresses for after-hours notification
- External contacts: legal counsel, cyber insurance carrier, forensics firm, HHS OCR, state attorneys general

> **Note:** The contact roster is maintained separately in a secure, access-controlled document. This plan does not contain actual contact information.

---

## 4. Detection and Reporting

### 4.1 Detection Sources

| Source | Description | Monitoring |
|---|---|---|
| **Audit Log System** | HIPAA-compliant audit trail (CISO-8) with tamper-evident hash chain | Continuous, automated alerting |
| **SIEM Alerts** | Centralized security event correlation and alerting | Continuous, 24/7 SOC coverage |
| **Application Monitoring** | FastAPI error rates, latency anomalies, unusual API patterns | Continuous, threshold-based alerts |
| **Infrastructure Monitoring** | Server metrics, network traffic, database performance | Continuous, threshold-based alerts |
| **User Reports** | Reports from employees, contractors, or end users | Manual, via reporting channels |
| **Vulnerability Scanners** | Automated vulnerability discovery and assessment | Scheduled (daily/weekly) |
| **WAF / IDS / IPS** | Web application firewall and intrusion detection/prevention | Continuous, real-time |
| **Threat Intelligence** | External threat feeds, vendor advisories, CVE monitoring | Continuous, automated ingestion |
| **Automated Health Checks** | Application health endpoints (`/health`, `/ready`) | Every 30 seconds |
| **Database Activity Monitoring** | PostgreSQL audit logging, query analysis | Continuous |

### 4.2 Reporting Procedures

Any person who suspects or discovers a security incident MUST report it immediately:

1. **Immediate verbal notification** to direct supervisor AND the Security Lead
2. **Written incident report** submitted within 1 hour of discovery via the incident tracking system (`POST /api/v1/security/incidents`)
3. **Do NOT** attempt to investigate, contain, or remediate independently unless immediate action is required to prevent ongoing data loss
4. **Do NOT** discuss the incident with unauthorized individuals
5. **Do NOT** delete, modify, or tamper with any evidence

### 4.3 Reporting Timeframes

| Action | Timeframe |
|---|---|
| Initial verbal report | Immediately upon discovery |
| Written incident report | Within 1 hour of discovery |
| IC acknowledgment (SEV1) | Within 15 minutes of report |
| IC acknowledgment (SEV2) | Within 30 minutes of report |
| IC acknowledgment (SEV3) | Within 4 hours of report |
| IC acknowledgment (SEV4) | Within 24 hours of report |

### 4.4 Initial Triage Checklist

Upon receiving an incident report, the Security Lead shall:

- [ ] Record the date, time, and source of the report
- [ ] Identify the reporter and obtain contact information
- [ ] Gather initial facts: what happened, when, which systems, who is affected
- [ ] Determine if PHI is potentially involved
- [ ] Assign initial severity classification
- [ ] Create an incident record in the tracking system
- [ ] Notify the Incident Commander
- [ ] Establish a secure communication channel for the response team
- [ ] Begin an incident timeline log
- [ ] Determine if immediate containment action is required
- [ ] Assess if the incident is ongoing or historical
- [ ] Identify initial scope: number of records, patients, and systems potentially affected

---

## 5. Response Procedures by Severity

### 5.1 SEV1 -- Critical / Data Breach

**Objective:** Immediate containment, evidence preservation, regulatory compliance.

**Phase 1: Detection and Initial Response (0-15 minutes)**

1. Security Lead confirms the incident and validates the severity classification
2. Incident Commander is notified and assumes coordination
3. Secure war room (physical or virtual) is established
4. All IRT members are activated via emergency contact protocol
5. Incident timeline logging begins

**Phase 2: Containment (15 minutes - 1 hour)**

1. Identify affected systems and data stores
2. Implement immediate containment:
   - Isolate compromised systems from the network
   - Revoke compromised credentials and API keys
   - Block malicious IP addresses or network segments
   - Disable affected user accounts
   - Activate failover systems if available
3. Preserve forensic evidence before any remediation (see Section 7)
4. Assess whether PHI has been accessed, acquired, or disclosed
5. Notify Legal/Compliance Officer for breach determination

**Phase 3: Eradication (1-24 hours)**

1. Identify root cause and attack vector
2. Remove malware, backdoors, or unauthorized access mechanisms
3. Patch exploited vulnerabilities
4. Reset all potentially compromised credentials
5. Verify eradication with security scanning

**Phase 4: Recovery (24-72 hours)**

1. Restore affected systems from clean backups
2. Implement additional monitoring on affected systems
3. Gradually restore services with enhanced logging
4. Verify system integrity before full restoration
5. Confirm no residual threat indicators

**Phase 5: HIPAA Breach Notification (within 60 days)**

1. Complete the four-factor risk assessment (see Section 6)
2. Determine if breach notification is required
3. Execute notification procedures per Section 6
4. File required regulatory reports

**Phase 6: Post-Incident (within 14 days of closure)**

1. Conduct root cause analysis
2. Document lessons learned
3. Implement corrective and preventive actions (CAPA)
4. Update this incident response plan as needed
5. Schedule follow-up review in 30 days

### 5.2 SEV2 -- High / Service Outage

**Objective:** Rapid service restoration, root cause identification, impact mitigation.

**Phase 1: Detection and Assessment (0-30 minutes)**

1. Security Lead assesses scope and impact
2. Incident Commander is notified
3. Determine if the outage is security-related or operational
4. Assess clinical workflow impact with Clinical Safety Officer
5. Activate relevant IRT members

**Phase 2: Containment and Stabilization (30 minutes - 4 hours)**

1. Implement temporary mitigations (failover, traffic rerouting, service isolation)
2. If security-related, isolate compromised components
3. Communicate status to affected users
4. Engage vendor support if third-party services are involved

**Phase 3: Resolution (4-24 hours)**

1. Identify and implement a permanent fix
2. Restore full service capability
3. Verify service health and data integrity
4. Remove temporary mitigations

**Phase 4: Post-Incident (within 7 days)**

1. Conduct a post-mortem meeting
2. Document root cause, timeline, and impact
3. Identify and assign follow-up actions
4. Publish a post-mortem report to stakeholders

### 5.3 SEV3 -- Medium / Security Event

**Objective:** Thorough investigation, appropriate remediation, trend identification.

**Phase 1: Assessment (0-4 hours)**

1. Security Lead reviews the alert or report
2. Determine if further investigation is warranted
3. Assess potential for escalation

**Phase 2: Investigation (4-24 hours)**

1. Collect and analyze relevant logs
2. Determine scope and impact
3. Identify affected systems and users
4. Assess whether PHI was involved

**Phase 3: Remediation (24-72 hours)**

1. Implement corrective actions (patching, configuration changes, access revocation)
2. Verify remediation effectiveness
3. Update detection rules to prevent recurrence

**Phase 4: Documentation (within 5 days)**

1. Document findings and remediation actions
2. Update incident record with final status
3. Identify any lessons learned

### 5.4 SEV4 -- Low / Anomaly

**Objective:** Record, monitor, and identify trends.

**Phase 1: Logging (0-24 hours)**

1. Record the event in the incident tracking system
2. Review available logs for context

**Phase 2: Assessment (24-72 hours)**

1. Determine if the anomaly is part of a larger pattern
2. Check against known threat intelligence
3. Decide if further action is needed

**Phase 3: Closure**

1. Document findings
2. Close the incident record
3. Include in monthly security metrics and trend analysis

---

## 6. HIPAA Breach Notification

### 6.1 Breach Definition

Under HIPAA, a **breach** is the acquisition, access, use, or disclosure of PHI in a manner not permitted under the HIPAA Privacy Rule that compromises the security or privacy of the PHI.

**Exceptions** (not considered a breach):

1. Unintentional acquisition, access, or use by a workforce member acting in good faith and within scope of authority, provided PHI is not further used or disclosed improperly
2. Inadvertent disclosure between authorized persons at the same covered entity or business associate, provided PHI is not further used or disclosed improperly
3. The covered entity or business associate has a good faith belief that the unauthorized person would not have been able to retain the PHI

### 6.2 Four-Factor Risk Assessment

Per 45 CFR 164.402, the following four factors MUST be evaluated to determine if an impermissible use or disclosure of PHI constitutes a breach requiring notification:

| Factor | Assessment Questions |
|---|---|
| **1. Nature and Extent of PHI** | What types of PHI were involved? (identifiers, clinical data, financial data, SSNs) What is the sensitivity level? Were direct identifiers combined with clinical information? |
| **2. Unauthorized Person** | Who impermissibly used or received the PHI? Was it an authorized workforce member? A business associate? An unknown external party? What is their capacity to use or further disclose the PHI? |
| **3. Whether PHI Was Actually Acquired or Viewed** | Was the PHI actually accessed or viewed, or was there merely an opportunity? Are there audit logs confirming access? Is there evidence of data download or exfiltration? |
| **4. Mitigation Measures** | What steps were taken to mitigate the risk? Has the PHI been returned or destroyed? Were assurances obtained that PHI will not be further used or disclosed? Was the risk effectively mitigated? |

**Determination:**

- If the risk assessment demonstrates a **low probability** that PHI has been compromised across all four factors, notification is NOT required
- If there is a reasonable probability that PHI was compromised, notification IS required
- When in doubt, treat the incident as a reportable breach

### 6.3 Notification Timeline and Requirements

| Requirement | Details |
|---|---|
| **Individual notification** | Without unreasonable delay and no later than **60 calendar days** from discovery of the breach |
| **Method** | First-class mail to last known address, or email if individual has agreed to electronic notice |
| **Content** | Description of breach, types of PHI involved, steps individuals should take, what the organization is doing, contact information |
| **Substitute notice** | If contact information is insufficient for 10+ individuals: conspicuous posting on website for 90 days OR notice in major media |
| **HHS OCR notification** | If 500+ individuals affected: notify HHS OCR **contemporaneously** with individual notification. If fewer than 500: maintain a log and submit annually within 60 days of end of calendar year |
| **State AG notification** | If 500+ residents of a single state: notify that state's Attorney General contemporaneously with individual notification |
| **Media notification** | If 500+ residents of a single state or jurisdiction: notify prominent media outlets serving that area |

### 6.4 Template: Individual Breach Notification Letter

```
[Organization Letterhead]
[Date]

[Individual Name]
[Address]

RE: Notice of Data Breach

Dear [Individual Name],

We are writing to inform you of a security incident that may have affected your
protected health information. We take the protection of your information very
seriously and want to provide you with details about what happened, what
information was involved, and what we are doing in response.

WHAT HAPPENED:
[Description of the breach -- what occurred, dates of the breach and discovery]

WHAT INFORMATION WAS INVOLVED:
[Specific types of PHI involved -- e.g., name, date of birth, medical record
number, diagnosis codes, treatment information]

WHAT WE ARE DOING:
[Steps taken to investigate, contain, and remediate the breach; steps taken to
prevent future occurrences]

WHAT YOU CAN DO:
[Recommended protective actions -- e.g., monitor health insurance statements,
request copies of medical records, place fraud alerts, obtain credit monitoring]

We are offering [X months] of complimentary credit monitoring and identity
theft protection services through [Provider Name]. To enroll, please
[enrollment instructions].

FOR MORE INFORMATION:
If you have questions or need additional information, please contact:
[Contact name, toll-free number, email, mailing address, website]

We sincerely regret any inconvenience or concern this may cause you.

Sincerely,
[Name]
[Title]
[Organization]
```

### 6.5 HHS OCR Reporting

**For breaches affecting 500+ individuals:**

1. Report via the HHS OCR Breach Portal (https://ocrportal.hhs.gov/ocr/breach/wizard_breach.jsf)
2. Submit within 60 days of breach discovery
3. Include: covered entity information, business associate (if applicable), breach details, number of individuals affected, type of breach, location of breach, type of PHI involved, safeguards in place, actions taken

**For breaches affecting fewer than 500 individuals:**

1. Maintain an internal breach log throughout the calendar year
2. Submit the log to HHS OCR within 60 days of the end of the calendar year
3. Include the same information as above for each incident

### 6.6 State Attorney General Notification

When 500 or more residents of a single state are affected:

1. Identify applicable state breach notification laws (requirements vary by state)
2. Prepare state-specific notifications as required
3. Submit to the appropriate AG office contemporaneously with individual notifications
4. Document all notifications and confirmations of receipt

---

## 7. Evidence Preservation

### 7.1 Principles

- **Do no harm:** Preservation activities must not alter or destroy evidence
- **Chain of custody:** All evidence must be documented with an unbroken chain of custody
- **Integrity:** Evidence must be verifiable (cryptographic hashes)
- **Completeness:** Collect all relevant evidence, erring on the side of over-collection

### 7.2 Log Retention

| Log Type | Retention Period | Storage | Integrity |
|---|---|---|---|
| HIPAA audit logs (AuditLog) | Minimum 6 years | Encrypted at rest, immutable storage | SHA-256 hash chain (CISO-8) |
| Application logs | 1 year standard, 6 years if PHI-related | Centralized log management | Write-once storage |
| Infrastructure/system logs | 1 year | Centralized log management | Syslog integrity |
| Network flow logs | 90 days standard, 1 year for incidents | Network monitoring platform | Checksums |
| Database transaction logs | 90 days standard, 6 years for incidents | Database backup system | Database checksums |
| Authentication logs | 6 years | Centralized log management | Hash chain |

### 7.3 Forensic Imaging

When forensic analysis is required (typically SEV1):

1. **Isolate** the system -- do NOT power off if possible (volatile memory is evidence)
2. **Document** the system state: running processes, network connections, logged-in users
3. **Capture volatile data** first: memory dump, running processes, network state
4. **Create forensic disk image** using write-blocking hardware or validated software
5. **Hash the original media** (SHA-256) and the forensic image
6. **Verify** the image hash matches the original
7. **Store** the forensic image in a secure, access-controlled location
8. **Work only on copies** -- never analyze the original evidence

### 7.4 Chain of Custody

Each piece of evidence must be documented with:

| Field | Description |
|---|---|
| Evidence ID | Unique identifier |
| Description | What the evidence is |
| Date/time collected | When it was collected |
| Collected by | Who collected it (name, role) |
| Location found | Where it was found |
| Hash value | SHA-256 hash at time of collection |
| Storage location | Where it is stored |
| Access log | Who has accessed it and when |
| Transfer log | Any transfers between custodians |

---

## 8. Communication Templates

### 8.1 Internal Escalation Email

```
Subject: [SECURITY INCIDENT] [SEV-X] - [Brief Description] - [Incident ID]

CLASSIFICATION: CONFIDENTIAL

Incident ID: [INC-YYYY-NNNN]
Severity: [SEV1/SEV2/SEV3/SEV4]
Status: [DETECTED/TRIAGING/CONTAINED/ERADICATING/RECOVERING]
Reported: [Date/Time UTC]
Incident Commander: [Name]

SUMMARY:
[2-3 sentence description of the incident]

AFFECTED SYSTEMS:
[List of affected systems/services]

PHI INVOLVEMENT:
[Yes/No/Under Investigation]
[If yes: estimated number of records/individuals]

CURRENT ACTIONS:
[What is being done right now]

NEXT STEPS:
[Planned actions and timeline]

REQUIRED FROM YOU:
[Specific actions needed from the recipient]

War Room: [Link to secure channel]
Status Page: [Link to internal status page]

Do NOT forward this email or discuss outside the incident response team.
```

### 8.2 External Breach Notification Letter

See Section 6.4 for the individual breach notification template.

### 8.3 Media Statement Template

```
[Organization Name] Statement Regarding Security Incident

[Date]

[Organization Name] recently identified a security incident affecting
[general description -- do not include technical details].

Upon discovering the incident on [date], we immediately [took action X]
and engaged [external forensics firm/law enforcement] to assist with
our investigation.

[If applicable: We have determined that certain personal health information
may have been affected, and we are in the process of notifying impacted
individuals directly.]

The security of our users' information is our top priority. We have
implemented [additional safeguards] to prevent similar incidents in
the future.

We encourage anyone with questions to contact [toll-free number]
or visit [website URL] for additional information.

[If applicable: We are offering complimentary credit monitoring and
identity theft protection services to affected individuals.]

Media Contact:
[Name]
[Phone]
[Email]
```

### 8.4 Regulatory Notification Template

```
To: U.S. Department of Health and Human Services
    Office for Civil Rights (OCR)

From: [Organization Name]
      [Address]

RE: Notification of Breach of Unsecured Protected Health Information
    Pursuant to 45 CFR 164.408

Covered Entity Information:
  Name: [Organization Name]
  Contact: [Privacy Officer Name, Phone, Email]

Breach Information:
  Date of Breach: [Date(s)]
  Date of Discovery: [Date]
  Type of Breach: [Hacking/IT Incident, Unauthorized Access/Disclosure,
                    Theft, Loss, Improper Disposal, Other]
  Location of Breached Information: [Network Server, Email, Desktop Computer,
                                     Electronic Medical Record, Paper/Films, Other]

Individuals Affected:
  Number: [Count]
  States of Residence: [List]

Type of PHI Involved:
  [Check all that apply: Names, SSN, Date of Birth, Address, Phone,
   Email, Medical Record Numbers, Health Plan Beneficiary Numbers,
   Account Numbers, Diagnosis/Treatment Information, Lab Results,
   Medications, Other Clinical Information]

Description of Breach:
  [Detailed narrative of what occurred]

Safeguards in Place at Time of Breach:
  [Encryption status, access controls, monitoring]

Actions Taken in Response:
  [Containment, investigation, remediation steps]

Individual Notification:
  Date(s) of notification: [Date(s)]
  Method: [First-class mail / Email / Substitute notice]

Corrective Actions:
  [Steps taken to prevent recurrence]
```

---

## 9. Post-Incident

### 9.1 Root Cause Analysis Template

| Section | Content |
|---|---|
| **Incident ID** | INC-YYYY-NNNN |
| **Severity** | SEV-X |
| **Date Range** | [Start] to [End] |
| **Incident Commander** | [Name] |
| **Summary** | [2-3 paragraph description] |
| **Timeline** | [Chronological event list with timestamps] |
| **Root Cause** | [Primary root cause identified through 5-Whys or other analysis] |
| **Contributing Factors** | [Secondary factors that enabled or worsened the incident] |
| **Impact** | Systems affected, data affected, users affected, downtime duration, PHI records involved |
| **Detection** | How was the incident detected? How long was the detection gap? |
| **Response Assessment** | What went well? What could be improved? Were SLAs met? |
| **Lessons Learned** | [Key takeaways for the organization] |
| **Action Items** | [Specific corrective and preventive actions with owners and due dates] |

### 9.2 CAPA (Corrective and Preventive Action) Process

**Corrective Actions** address the specific root cause of the incident:

1. Identify the root cause through formal analysis (5-Whys, fishbone diagram, fault tree)
2. Define specific corrective actions with measurable success criteria
3. Assign an owner and due date for each action
4. Implement the corrective actions
5. Verify effectiveness through testing or monitoring
6. Document completion and evidence of effectiveness

**Preventive Actions** address systemic issues to prevent similar incidents:

1. Identify systemic weaknesses or patterns revealed by the incident
2. Define preventive measures (process changes, technical controls, training)
3. Prioritize based on risk and feasibility
4. Assign owners and due dates
5. Implement and verify
6. Incorporate into regular security assessment cycles

**CAPA Tracking:**

| Field | Description |
|---|---|
| CAPA ID | Unique identifier linked to incident |
| Type | Corrective or Preventive |
| Description | What needs to be done |
| Owner | Person responsible |
| Due Date | Target completion date |
| Status | Open / In Progress / Completed / Verified |
| Verification Method | How effectiveness will be confirmed |
| Evidence | Documentation of completion |

### 9.3 Plan Update Cadence

| Trigger | Action | Timeline |
|---|---|---|
| Annual review | Full plan review and update | Annually (by plan anniversary date) |
| After SEV1 incident | Review and update relevant sections | Within 30 days of incident closure |
| After SEV2 incident | Review relevant sections | Within 60 days of incident closure |
| After tabletop exercise | Incorporate lessons learned | Within 14 days of exercise |
| Regulatory change | Update affected sections | Within 30 days of regulation effective date |
| Organizational change | Update roles, contacts, procedures | Within 14 days of change |
| Technology change | Update affected detection/response procedures | Within 30 days of deployment |

### 9.4 Metrics and Reporting

The following metrics shall be tracked and reported quarterly to leadership:

| Metric | Target |
|---|---|
| Mean time to detect (MTTD) | < 1 hour |
| Mean time to respond (MTTR) | SEV1: < 15 min, SEV2: < 30 min |
| Mean time to contain (MTTC) | SEV1: < 1 hr, SEV2: < 4 hr |
| Incident volume by severity | Trending downward |
| CAPA completion rate | > 95% on-time |
| Tabletop exercises completed | >= 2 per year |
| Plan review completed | Annually |
| Breach notification compliance | 100% within 60 days |

---

## Appendix A: Definitions

| Term | Definition |
|---|---|
| **Breach** | Unauthorized acquisition, access, use, or disclosure of PHI that compromises its security or privacy (per HIPAA) |
| **CAPA** | Corrective and Preventive Action |
| **Covered Entity** | A health plan, healthcare clearinghouse, or healthcare provider that transmits health information electronically |
| **IC** | Incident Commander |
| **IRT** | Incident Response Team |
| **PHI** | Protected Health Information -- individually identifiable health information transmitted or maintained in any form |
| **SIEM** | Security Information and Event Management |
| **SEV** | Severity level |

## Appendix B: Document History

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | 2026-02-08 | CISO | Initial release |

## Appendix C: Related Documents

| Document | Location |
|---|---|
| Incident Runbook: PHI Breach | `docs/security/incident_runbooks/runbook_phi_breach.md` |
| Incident Runbook: Unauthorized Access | `docs/security/incident_runbooks/runbook_unauthorized_access.md` |
| Incident Runbook: Service Outage | `docs/security/incident_runbooks/runbook_service_outage.md` |
| Audit Service Documentation | `backend/app/services/audit_service.py` |
| Incident Tracking API | `backend/app/api/incidents.py` |
| HIPAA Security Policies | `docs/security/` |
