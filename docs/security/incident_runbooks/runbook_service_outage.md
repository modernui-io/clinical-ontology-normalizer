# Runbook: Critical Service Outage

**Runbook ID:** RB-OUTAGE-001
**Version:** 1.0
**Severity:** SEV2
**Last Updated:** 2026-02-08
**Parent Plan:** [Incident Response Plan](../incident_response_plan.md)

---

## Trigger Conditions

This runbook is activated when ANY of the following conditions are confirmed:

- **API unavailability:** FastAPI backend returns 5xx errors for more than 5 minutes or health endpoint (`/health`) fails
- **Database outage:** PostgreSQL primary is unreachable, read replicas are all down, or replication lag exceeds 60 seconds
- **Redis unavailability:** Job queue (Redis) is unreachable, causing pipeline processing failures
- **Frontend outage:** Next.js application is unreachable or returning errors for all users
- **Authentication failure:** Auth service is down, preventing all user logins
- **FHIR endpoint failure:** FHIR import/export endpoints are unreachable, blocking clinical data exchange
- **Complete platform outage:** Multiple core services are simultaneously unavailable
- **Data integrity failure:** Evidence of data corruption in clinical records, knowledge graph, or OMOP mappings
- **Infrastructure failure:** Kubernetes cluster degradation, container orchestration failure, or network partition
- **DDoS attack:** Traffic volume causing service degradation or unavailability

---

## Step-by-Step Response Actions

### Phase 1: Detection and Initial Assessment (0-15 minutes)

- [ ] **1.1** Confirm the outage
  - Check health endpoints: `/health`, `/ready`
  - Verify from multiple network locations (internal, external, different regions)
  - Review monitoring dashboards for error rates and latency
  - Check infrastructure status (Kubernetes pods, containers, VMs)
- [ ] **1.2** Determine the scope
  - Which services are affected? (API, frontend, database, Redis, Neo4j, FHIR)
  - Is the outage complete or partial? (all endpoints vs. specific routes)
  - How many users or downstream systems are affected?
  - What is the geographic scope? (all regions vs. specific region)
- [ ] **1.3** Assess security implications
  - Could this outage be caused by a security incident? (DDoS, ransomware, destructive attack)
  - Are audit logs and monitoring systems still functioning?
  - If security-related, activate the appropriate security runbook in parallel
- [ ] **1.4** Create the incident record
  - `POST /api/v1/security/incidents` with severity SEV2, type SERVICE_OUTAGE
  - If the incident tracking system is also affected, use the backup communication channel
- [ ] **1.5** Notify the Incident Commander and activate the response team
  - Notify: IC, Engineering Lead, IT Operations Lead, Clinical Safety Officer
  - Establish communication channel (secure chat, video bridge)

### Phase 2: Triage and Immediate Mitigation (15 minutes - 1 hour)

- [ ] **2.1** Identify the root cause category
  - **Application failure:** Check application logs, recent deployments, configuration changes
  - **Database failure:** Check PostgreSQL logs, connection pool status, disk space, replication status
  - **Infrastructure failure:** Check Kubernetes status, node health, network connectivity, DNS
  - **Dependency failure:** Check external service status (Metriport, SMART on FHIR endpoints)
  - **Resource exhaustion:** Check CPU, memory, disk, connection pool usage
  - **DDoS/traffic spike:** Check traffic patterns, request rates, source IP distribution
- [ ] **2.2** Implement immediate mitigation
  - **Application crash:** Restart affected pods/containers; roll back if recent deployment caused the issue
  - **Database failure:**
    - If primary is down: failover to replica (if available)
    - If disk full: emergency cleanup of temp files and WAL segments
    - If connection pool exhausted: increase limits or terminate idle connections
  - **Infrastructure failure:**
    - If node failure: drain and replace the node; verify pod rescheduling
    - If network partition: contact cloud provider; activate backup network path
  - **DDoS attack:**
    - Enable DDoS mitigation mode (rate limiting, geo-blocking)
    - Activate CDN/WAF protections
    - Contact cloud provider for upstream mitigation if needed
  - **Resource exhaustion:**
    - Scale up affected services (horizontal or vertical)
    - Identify and terminate resource-hogging processes
    - Implement emergency resource limits
- [ ] **2.3** Communicate status
  - Update internal status page
  - Notify affected downstream systems and integration partners
  - If clinical operations are impacted, notify Clinical Safety Officer for patient safety assessment
- [ ] **2.4** Assess clinical impact
  - Are clinical trial screening workflows blocked?
  - Is patient data inaccessible to authorized clinical staff?
  - Are FHIR-based integrations failing, impacting care delivery?
  - Document clinical workflow impact for post-incident analysis

### Phase 3: Service Restoration (1-4 hours)

- [ ] **3.1** Implement the permanent fix (or robust workaround)
  - If application bug: deploy the fix through the standard pipeline (expedited review)
  - If infrastructure: complete the repair and verify stability
  - If external dependency: implement fallback or cache-based degraded mode
- [ ] **3.2** Verify service health
  - Confirm all health endpoints are passing
  - Verify end-to-end functionality: document ingestion, NLP processing, OMOP mapping, knowledge graph queries
  - Check data integrity: no data loss or corruption during the outage
  - Verify all integrations are reconnected and functioning
- [ ] **3.3** Process backlog
  - If job queue (Redis) had a backlog, monitor processing catch-up
  - Verify queued jobs are processed in order without data loss
  - Check for any duplicate processing from retry logic
- [ ] **3.4** Gradually restore full capacity
  - Remove any emergency rate limits or feature flags
  - Scale back to normal resource allocation once stable
  - Monitor for 1 hour at full capacity before declaring recovery

### Phase 4: Root Cause Analysis (4-48 hours)

- [ ] **4.1** Collect all relevant data
  - Application logs from the outage period
  - Infrastructure metrics (CPU, memory, disk, network)
  - Database logs and performance metrics
  - Deployment history and configuration change log
  - Monitoring alert timeline
- [ ] **4.2** Determine root cause
  - Conduct a blameless analysis using the 5-Whys method
  - Identify the triggering event and contributing factors
  - Document the causal chain from root cause to user impact
- [ ] **4.3** Assess preventability
  - Could monitoring have detected this earlier?
  - Could the impact have been reduced with better redundancy?
  - Were there warning signs that were missed?

### Phase 5: Post-Incident (within 7 days)

- [ ] **5.1** Write the post-mortem document
  - Timeline of events with timestamps
  - Root cause and contributing factors
  - Impact: duration, affected users, data impact, clinical workflow impact
  - Response assessment: what went well, what to improve
  - Action items with owners and due dates
- [ ] **5.2** Hold the post-mortem meeting
  - Blameless review with all responders
  - Discuss timeline, decisions made, and alternatives
  - Agree on action items and priorities
- [ ] **5.3** Implement improvements
  - Assign and track CAPA items
  - Update monitoring and alerting
  - Improve runbook based on lessons learned
  - Schedule follow-up to verify improvements

---

## Escalation Points

| Trigger | Escalation Action |
|---|---|
| Outage exceeds 1 hour | Notify executive leadership; escalate Engineering resources |
| Data loss confirmed | Escalate to SEV1; activate data recovery procedures |
| Security cause confirmed | Activate appropriate security runbook (PHI Breach or Unauthorized Access) |
| Clinical safety impact confirmed | Escalate to Clinical Safety Officer and CMO; assess patient risk |
| Unable to identify root cause within 2 hours | Engage vendor support or external consultants |
| DDoS attack with ransom demand | Engage Legal and law enforcement; do NOT respond to demands |
| Database corruption detected | Escalate to SEV1; initiate point-in-time recovery |
| Multiple cascading failures | Declare major incident; activate full IRT |

---

## Resolution Criteria

The incident may be moved to CLOSED status when ALL of the following are satisfied:

- [ ] All affected services are fully operational and verified
- [ ] Health endpoints are consistently passing (minimum 1 hour of stability)
- [ ] No data loss or corruption has occurred (or has been fully recovered)
- [ ] Job queue backlog has been fully processed
- [ ] All integrations are reconnected and functioning
- [ ] Root cause has been identified
- [ ] Monitoring/alerting improvements are in place to detect recurrence
- [ ] Post-mortem document has been completed and reviewed
- [ ] CAPA items have been assigned with owners and due dates

---

## Post-Incident Checklist

- [ ] Post-mortem document completed
- [ ] Post-mortem meeting held with all responders
- [ ] Root cause documented and communicated
- [ ] CAPA items created in tracking system
- [ ] Monitoring and alerting improvements deployed
- [ ] Runbook updated with lessons learned
- [ ] Redundancy and failover improvements identified
- [ ] Capacity planning reviewed and updated
- [ ] SLA impact calculated and documented
- [ ] Customer/partner communication sent (if external impact)
- [ ] Incident record closed with complete timeline
- [ ] 30-day follow-up review scheduled

---

## Quick Reference: Service Health Commands

| Check | Command / Endpoint |
|---|---|
| API health | `GET /health` |
| API readiness | `GET /ready` |
| Database connectivity | Check PostgreSQL connection pool in application logs |
| Redis connectivity | Check Redis ping in job queue logs |
| Pod status | `kubectl get pods -n <namespace>` |
| Recent deployments | `kubectl rollout history deployment/<name>` |
| Rollback | `kubectl rollout undo deployment/<name>` |
| Application logs | `kubectl logs -f deployment/<name> --tail=100` |
| Database logs | Check PostgreSQL log files or CloudWatch |
| Network status | `kubectl get services,ingresses -n <namespace>` |
