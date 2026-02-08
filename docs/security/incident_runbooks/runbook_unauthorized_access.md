# Runbook: Unauthorized System Access

**Runbook ID:** RB-UNAUTH-001
**Version:** 1.0
**Severity:** SEV1-SEV2 (depends on PHI access)
**Last Updated:** 2026-02-08
**Parent Plan:** [Incident Response Plan](../incident_response_plan.md)

---

## Trigger Conditions

This runbook is activated when ANY of the following conditions are confirmed or strongly suspected:

- Authentication bypass detected (e.g., JWT forgery, session hijacking, token reuse)
- Successful login from known-compromised credentials
- Brute-force attack with one or more successful authentications
- Privilege escalation: user accessing resources beyond their authorized role
- Unauthorized API key usage from unrecognized IP addresses or clients
- Suspicious admin-level activity from non-admin accounts
- SIEM or WAF alert indicating unauthorized access patterns
- Audit log showing access by deactivated or unknown user accounts
- Anomalous access patterns: access at unusual hours, unusual data volumes, unusual endpoints
- Shared credential usage detected (same credentials from multiple geographic locations simultaneously)

---

## Step-by-Step Response Actions

### Phase 1: Detection and Validation (0-30 minutes)

- [ ] **1.1** Validate the alert
  - Review the source alert or report for accuracy
  - Check for false positives (e.g., legitimate user, VPN, authorized automation)
  - Correlate across multiple data sources: audit logs, SIEM, application logs, network logs
- [ ] **1.2** Identify the unauthorized actor
  - Source IP address(es), geolocation, ASN
  - User account(s) involved
  - API key(s) or token(s) used
  - User agent string and client fingerprint
- [ ] **1.3** Determine the scope of access
  - What systems were accessed? (API endpoints, databases, admin interfaces)
  - What data was accessed? Query audit logs: `GET /api/v1/audit/logs?user_id=...`
  - Was PHI accessed? Check `phi_accessed` flag in audit records
  - How long has unauthorized access been occurring? Check first and last access timestamps
- [ ] **1.4** Classify severity
  - **SEV1** if: PHI was accessed, admin-level access achieved, evidence of data exfiltration, or active exploitation ongoing
  - **SEV2** if: No PHI accessed, limited scope, no evidence of data theft, access was blocked before data retrieval
- [ ] **1.5** Create the incident record
  - `POST /api/v1/security/incidents` with appropriate severity and type UNAUTHORIZED_ACCESS
  - Notify the Incident Commander

### Phase 2: Containment (30 minutes - 4 hours)

- [ ] **2.1** Revoke unauthorized access immediately
  - **Compromised user account:** Disable the account, terminate all active sessions, reset password
  - **Compromised API key:** Revoke the key, issue a new one to the legitimate owner
  - **Session hijacking:** Invalidate all sessions for the affected user, force re-authentication
  - **Privilege escalation:** Revoke elevated permissions, audit recent permission changes
- [ ] **2.2** Block the attack source
  - Add source IP(s) to blocklist (WAF, firewall, application-level)
  - If attack originates from a known hosting provider or VPN, consider blocking the range
  - Update rate limiting rules if brute-force was involved
- [ ] **2.3** Secure the authentication mechanism
  - If authentication bypass: disable the affected authentication endpoint until patched
  - If credential stuffing: enable or enforce MFA for all affected accounts
  - If JWT vulnerability: rotate signing keys, invalidate all existing tokens
- [ ] **2.4** Preserve evidence
  - Export audit logs for the affected time period
  - Save authentication logs, session records, and access tokens
  - Capture network logs showing the unauthorized connections
  - Document the attack methodology
- [ ] **2.5** Assess lateral movement
  - Did the attacker access additional systems after initial compromise?
  - Were any credentials stored in the compromised system used elsewhere?
  - Check for new user accounts, API keys, or access grants created by the attacker

### Phase 3: Investigation (4-24 hours)

- [ ] **3.1** Determine the root cause
  - **Credential compromise:** How were credentials obtained? (phishing, breach of another service, weak password, credential stuffing)
  - **Authentication vulnerability:** What is the technical vulnerability? (CVE, logic error, misconfiguration)
  - **Insider access:** Was this a current/former employee? Was access appropriate at any point?
  - **Session issue:** How was the session obtained/forged? (XSS, CSRF, session fixation)
- [ ] **3.2** Map the attacker's activity timeline
  - First unauthorized access attempt
  - First successful access
  - Resources accessed (enumerate specific endpoints, records, data)
  - Data exfiltration (if any) -- volume, method, destination
  - Last observed activity
- [ ] **3.3** Assess PHI impact
  - If PHI was accessed, initiate the PHI Breach runbook (RB-PHI-001) in parallel
  - If PHI was NOT accessed, document the evidence supporting this determination
- [ ] **3.4** Check for persistence mechanisms
  - New user accounts or API keys created by the attacker
  - Modified application code, configuration, or startup scripts
  - Scheduled tasks, cron jobs, or background processes
  - Modified firewall rules or network configurations
  - Backdoor endpoints or debug modes enabled

### Phase 4: Eradication (24-72 hours)

- [ ] **4.1** Eliminate the root cause
  - Patch the authentication vulnerability
  - Remove any backdoors or persistence mechanisms
  - Deactivate any accounts or keys created by the attacker
- [ ] **4.2** Strengthen authentication controls
  - Review and update password policies
  - Enable or enforce multi-factor authentication
  - Implement account lockout policies
  - Review API key management practices
- [ ] **4.3** Review access controls
  - Audit all user permissions against the principle of least privilege
  - Review role assignments for appropriateness
  - Remove any stale or unnecessary accounts
  - Verify service account permissions
- [ ] **4.4** Update detection capabilities
  - Add SIEM rules for the specific attack pattern observed
  - Enhance audit logging for the affected endpoints
  - Implement anomaly detection for authentication events
  - Set up alerts for concurrent sessions from different locations

### Phase 5: Recovery (72 hours - 1 week)

- [ ] **5.1** Restore normal authentication
  - Re-enable patched endpoints or services
  - Issue new credentials to affected legitimate users
  - Communicate authentication changes to users
- [ ] **5.2** Verify system integrity
  - Compare current system configuration to known-good baseline
  - Verify no unauthorized changes to application code or data
  - Confirm audit log hash chain integrity
- [ ] **5.3** Implement enhanced monitoring
  - Deploy heightened monitoring for the affected systems (30-day period)
  - Monitor for the specific attacker's indicators of compromise (IoCs)
  - Track failed authentication rates for anomalies
- [ ] **5.4** Credential reset campaign
  - If scope warrants, force password reset for all users of the affected system
  - Rotate all service account credentials as a precaution
  - Regenerate all API keys and distribute to legitimate consumers

---

## Escalation Points

| Trigger | Escalation Action |
|---|---|
| PHI confirmed accessed | Activate PHI Breach runbook (RB-PHI-001); escalate to SEV1 |
| Admin or superuser access achieved | Escalate to SEV1; engage external forensics |
| Multiple systems compromised (lateral movement) | Escalate to SEV1; consider full network isolation |
| Credentials obtained via supply chain compromise | Notify all affected downstream systems; engage vendor |
| Insider threat confirmed | Engage HR and Legal immediately; consider law enforcement |
| Unable to determine scope of access | Assume worst case; treat as SEV1 until proven otherwise |
| Attacker persistence mechanism found | Escalate to SEV1; comprehensive sweep required |

---

## Resolution Criteria

The incident may be moved to CLOSED status when ALL of the following are satisfied:

- [ ] Unauthorized access has been terminated and confirmed stopped
- [ ] Root cause has been identified and permanently remediated
- [ ] All compromised credentials have been revoked and replaced
- [ ] No persistence mechanisms remain in the environment
- [ ] Scope of accessed data has been fully determined
- [ ] PHI impact assessment is complete (and PHI Breach runbook followed if applicable)
- [ ] Enhanced monitoring is in place with no recurrence for 14+ days
- [ ] All affected users have been notified and re-credentialed
- [ ] Post-incident review meeting has been conducted

---

## Post-Incident Checklist

- [ ] Root cause analysis completed and documented
- [ ] Post-mortem meeting held with relevant IRT members
- [ ] Lessons learned documented
- [ ] Authentication and access control improvements identified and assigned
- [ ] SIEM rules and detection capabilities updated
- [ ] Security awareness training updated (especially if phishing was involved)
- [ ] Incident Response Plan updated if needed
- [ ] All evidence securely archived per retention policy
- [ ] Incident record closed in tracking system with complete timeline
- [ ] 30-day follow-up review scheduled
- [ ] Metrics updated (MTTD, MTTR, MTTC)
