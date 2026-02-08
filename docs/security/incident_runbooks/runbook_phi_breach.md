# Runbook: PHI Data Breach

**Runbook ID:** RB-PHI-001
**Version:** 1.0
**Severity:** SEV1
**Last Updated:** 2026-02-08
**Parent Plan:** [Incident Response Plan](../incident_response_plan.md)

---

## Trigger Conditions

This runbook is activated when ANY of the following conditions are confirmed or strongly suspected:

- Unauthorized access to databases or data stores containing PHI (PostgreSQL, Redis, Neo4j)
- Exfiltration of data containing patient information, clinical records, or FHIR resources
- Unauthorized disclosure of PHI to external parties
- Lost or stolen devices/media containing unencrypted PHI
- Compromised credentials with evidence of PHI access in the audit trail
- Ransomware affecting systems that store or process PHI
- Business associate reports a breach involving our PHI
- Audit log anomalies indicating bulk PHI access (e.g., abnormal export volume, sequential patient record access)
- SIEM alert indicating data exfiltration patterns from PHI-containing services

---

## Step-by-Step Response Actions

### Phase 1: Immediate Response (0-15 minutes)

- [ ] **1.1** Confirm the incident is a PHI breach (not a false positive)
  - Review audit logs via `GET /api/v1/audit/logs?phi_only=true`
  - Check SIEM alerts for corroborating evidence
  - Verify with the reporting source
- [ ] **1.2** Create an incident record
  - `POST /api/v1/security/incidents` with severity SEV1, type PHI_BREACH
- [ ] **1.3** Notify the Incident Commander
  - Use emergency contact protocol (phone, then secure messaging)
  - If IC is unavailable within 5 minutes, activate backup IC
- [ ] **1.4** Activate the Incident Response Team
  - Notify: Security Lead, Engineering Lead, Legal/Compliance, Privacy Officer, Clinical Safety Officer
  - Establish secure war room (video bridge + encrypted chat channel)
- [ ] **1.5** Begin incident timeline documentation
  - Record all actions with timestamps in the incident tracking system
  - `POST /api/v1/security/incidents/{id}/timeline`

### Phase 2: Containment (15 minutes - 1 hour)

- [ ] **2.1** Identify the scope of the breach
  - Which systems are affected? (PostgreSQL, Redis, Neo4j, FHIR endpoints, API)
  - What types of PHI are exposed? (patient demographics, clinical data, trial enrollment, diagnoses)
  - How many patient records are potentially affected?
  - Is the breach ongoing or historical?
- [ ] **2.2** Implement immediate containment
  - **If compromised credentials:** Immediately revoke/reset affected credentials and API keys; terminate active sessions
  - **If application vulnerability:** Deploy emergency patch or WAF rule; disable affected endpoint if safe to do so
  - **If malware/ransomware:** Isolate affected systems from network; do NOT power off (preserve memory)
  - **If insider threat:** Revoke user access; preserve audit logs; notify HR and Legal
  - **If third-party/business associate:** Contact the BA; request their containment actions; document communications
- [ ] **2.3** Preserve evidence BEFORE remediation
  - Capture system memory dump if applicable
  - Export relevant audit logs: `GET /api/v1/audit/logs?start_date=...&end_date=...&phi_only=true`
  - Snapshot affected database(s)
  - Save network flow logs and firewall logs
  - Record running processes, network connections, and user sessions on affected systems
- [ ] **2.4** Verify containment is effective
  - Monitor for continued unauthorized access
  - Confirm affected entry points are closed
  - Validate that legitimate operations can continue (or document clinical impact)

### Phase 3: Assessment and Breach Determination (1-24 hours)

- [ ] **3.1** Conduct the HIPAA four-factor risk assessment
  - **Factor 1 -- Nature and extent of PHI involved:**
    - Document specific data elements exposed (names, DOBs, MRNs, diagnoses, medications, SSNs, etc.)
    - Assess sensitivity (e.g., HIV status, mental health, substance abuse carry higher risk)
  - **Factor 2 -- Unauthorized person who accessed/received PHI:**
    - Identify the unauthorized party (known individual, unknown attacker, specific IP addresses)
    - Assess their ability to use or further disclose the information
  - **Factor 3 -- Whether PHI was actually acquired or viewed:**
    - Review audit trail hash chain for evidence of actual data access
    - Analyze network logs for data transfer evidence
    - Determine if data was downloaded, copied, or only potentially viewable
  - **Factor 4 -- Extent to which risk has been mitigated:**
    - Document all containment and mitigation actions taken
    - Determine if PHI has been or can be recovered/destroyed
    - Obtain written assurances from unauthorized recipients (if applicable)
- [ ] **3.2** Legal/Compliance makes the breach determination
  - Is this a reportable breach under HIPAA?
  - Does the low-probability exception apply based on the four factors?
  - Document the determination rationale with supporting evidence
- [ ] **3.3** Determine the count of affected individuals
  - Query affected records to establish an accurate count
  - Identify individuals by state of residence (for state AG notification thresholds)
  - If exact count is unknown, document the methodology and best estimate

### Phase 4: Eradication (24-72 hours)

- [ ] **4.1** Identify and eliminate the root cause
  - Patch the exploited vulnerability
  - Remove malware or unauthorized access mechanisms
  - Close the attack vector permanently
- [ ] **4.2** Reset all potentially compromised credentials
  - Application-level: API keys, service account passwords, database credentials
  - User-level: All users who may have been affected
  - Infrastructure-level: SSH keys, TLS certificates if necessary
- [ ] **4.3** Implement additional security controls
  - Deploy enhanced monitoring on previously affected systems
  - Add new detection rules to SIEM for this attack pattern
  - Review and strengthen access controls
- [ ] **4.4** Validate the eradication
  - Run vulnerability scans against affected systems
  - Verify no backdoors or persistent access remains
  - Confirm audit log integrity (hash chain verification)

### Phase 5: Recovery (72 hours - 2 weeks)

- [ ] **5.1** Restore affected systems
  - Restore from verified clean backups if necessary
  - Verify data integrity after restoration
  - Implement enhanced logging and monitoring
- [ ] **5.2** Resume normal operations
  - Gradually restore full service with heightened monitoring
  - Confirm clinical workflows are functioning correctly
  - Verify FHIR endpoints and integrations are operational
- [ ] **5.3** Monitor for recurrence
  - Implement 30-day enhanced monitoring period
  - Daily review of audit logs for affected systems
  - Alert on any access patterns similar to the breach

### Phase 6: Notification (within 60 days of discovery)

- [ ] **6.1** Prepare individual notification letters
  - Use template from Incident Response Plan Section 6.4
  - Customize with specific breach details and PHI types
  - Include credit monitoring enrollment information
- [ ] **6.2** Send individual notifications
  - First-class mail to last known address
  - Email if individual has consented to electronic communication
  - Substitute notice if contact information is insufficient
- [ ] **6.3** HHS OCR notification
  - If 500+ individuals: submit via OCR Breach Portal within 60 days
  - If fewer than 500: log for annual submission
- [ ] **6.4** State Attorney General notification
  - If 500+ residents of a single state: notify that state's AG contemporaneously
  - Research state-specific requirements (some states have shorter timelines)
- [ ] **6.5** Media notification
  - If 500+ residents of a single state: notify prominent media outlets
  - Use media statement template from Incident Response Plan Section 8.3

---

## Escalation Points

| Trigger | Escalation Action |
|---|---|
| IC not acknowledged within 15 minutes | Activate backup IC; notify CISO |
| Containment not achieved within 1 hour | Escalate to executive leadership; consider engaging external forensics firm |
| PHI count exceeds 500 individuals | Activate media and regulatory notification procedures |
| Breach involves clinical trial data | Notify IRB (Institutional Review Board) and trial sponsors |
| Evidence of advanced persistent threat (APT) | Engage external threat intelligence; notify FBI/CISA |
| Insider threat confirmed | Engage HR, Legal, and law enforcement as appropriate |
| Ransom demand received | Do NOT respond; engage Legal and law enforcement immediately |

---

## Resolution Criteria

The incident may be moved to CLOSED status when ALL of the following are satisfied:

- [ ] Root cause has been identified and documented
- [ ] The attack vector has been permanently eliminated
- [ ] All compromised credentials have been rotated
- [ ] Affected systems have been restored to a known-good state
- [ ] Data integrity has been verified (audit log hash chain intact)
- [ ] Four-factor risk assessment is complete and documented
- [ ] Breach determination has been made by Legal/Compliance
- [ ] All required notifications have been sent (or determined not required)
- [ ] HHS OCR reporting is complete (or logged for annual submission)
- [ ] Enhanced monitoring is in place and no recurrence detected for 14+ days
- [ ] Post-incident review meeting has been conducted
- [ ] CAPA items have been identified and assigned

---

## Post-Incident Checklist

- [ ] Root cause analysis completed and documented
- [ ] Post-mortem meeting held with all IRT members
- [ ] Lessons learned documented and shared with relevant teams
- [ ] CAPA items created with owners and due dates
- [ ] Incident Response Plan updated if needed
- [ ] Detection rules and monitoring updated
- [ ] Security awareness training updated to cover this incident type
- [ ] Tabletop exercise scheduled to test improved procedures
- [ ] All evidence securely archived per retention policy
- [ ] Incident record closed in tracking system with complete timeline
- [ ] 30-day follow-up review scheduled
- [ ] Metrics updated (MTTD, MTTR, MTTC)
- [ ] Board/executive briefing prepared (for SEV1 incidents)
- [ ] Cyber insurance carrier notified (if applicable)
