# Incident Postmortem Template — Clinical AI Platform

**Document ID**: OPS-P3-019
**Version**: 1.0
**Effective Date**: 2026-02-15
**Owner**: Operations + Clinical AI
**Classification**: Internal — Operational

## Postmortem Report

### Incident Overview

| Field | Value |
|---|---|
| Incident ID | INC-YYYY-NNN |
| Severity | SEV-1 / SEV-2 |
| Category | (from incident taxonomy P1-032) |
| Date/Time | |
| Duration | |
| Incident Commander | |
| Postmortem Author | |
| Postmortem Date | |

### Executive Summary

*2-3 sentences describing what happened, the impact, and the resolution.*

### Timeline

| Time (UTC) | Event |
|---|---|
| HH:MM | Incident detected by [source] |
| HH:MM | Alert received by [person/system] |
| HH:MM | Investigation started |
| HH:MM | Root cause identified |
| HH:MM | Mitigation applied |
| HH:MM | Service restored |
| HH:MM | Incident resolved |

### Impact Assessment

| Dimension | Impact |
|---|---|
| Users affected | |
| Patients affected | |
| Data records affected | |
| Revenue impact | |
| Compliance impact | |
| Clinical safety impact | |

### Clinical AI Misguidance Risk Assessment

*This section is specific to clinical AI incidents. Complete for any incident where clinical outputs may have been incorrect.*

| Question | Answer |
|---|---|
| Were clinical decisions potentially affected? | YES / NO |
| Were incorrect results displayed to clinicians? | YES / NO |
| Were drug interactions missed or falsely reported? | YES / NO |
| Were clinical facts created with wrong domains? | YES / NO |
| Were confidence scores accurate during the incident? | YES / NO |
| Was degraded mode properly activated? | YES / NO |
| Were affected results identified and corrected? | YES / NO |
| Is clinician notification required? | YES / NO |
| Is regulatory notification required? | YES / NO |

### Root Cause Analysis

*Describe the technical root cause. Use the "5 Whys" technique.*

1. **Why** did the incident occur?
2. **Why** was that condition present?
3. **Why** was that not caught earlier?
4. **Why** was there no safeguard?
5. **Why** was the safeguard missing?

**Root cause**: [Clear statement]

### Contributing Factors

- [ ] Code defect
- [ ] Configuration error
- [ ] Infrastructure failure
- [ ] Third-party service failure
- [ ] Human error
- [ ] Monitoring gap
- [ ] Process gap
- [ ] Missing test coverage
- [ ] Inadequate documentation

### What Went Well

- *What worked as expected during incident response*

### What Went Poorly

- *What didn't work or took longer than expected*

### Action Items

| ID | Action | Owner | Priority | Deadline | Status |
|---|---|---|---|---|---|
| AI-001 | | | P0/P1/P2 | | Open |
| AI-002 | | | | | |
| AI-003 | | | | | |

### Lessons Learned

1. ...
2. ...
3. ...

### Follow-Up Schedule

| Date | Activity | Owner |
|---|---|---|
| +1 week | Review action item progress | IC |
| +2 weeks | Verify fixes deployed | IC |
| +1 month | Confirm all action items closed | Program Lead |

## Review and Approval

| Role | Name | Date | Approved |
|---|---|---|---|
| Incident Commander | | | |
| CTO | | | |
| Clinical Safety (if applicable) | | | |
| CISO (if security-related) | | | |
