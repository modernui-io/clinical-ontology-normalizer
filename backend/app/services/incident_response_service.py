"""Incident Response Playbooks Service (CISO-12).

Manages structured incident response playbooks, automated escalation,
regulatory notification tracking, SLA enforcement, and post-incident
review workflows for pharma-grade security operations.

Usage:
    from app.services.incident_response_service import (
        get_incident_response_service,
    )

    svc = get_incident_response_service()
    incident = svc.create_incident(...)
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from collections import Counter
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.incident_response import (
    EscalationContact,
    EscalationLevel,
    EscalationMatrix,
    EventCreateRequest,
    IncidentCategory,
    IncidentCreateRequest,
    IncidentEvent,
    IncidentMetrics,
    IncidentPhase,
    IncidentRecord,
    IncidentSeverity,
    IncidentUpdateRequest,
    NotificationCreateRequest,
    NotificationStatus,
    NotificationType,
    NOTIFICATION_DEADLINES,
    Playbook,
    PlaybookStep,
    PlaybookTestResult,
    PlaybookType,
    PostIncidentReview,
    PostIncidentReviewRequest,
    RegulatoryNotification,
    SLA_TARGETS,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Valid phase transitions
# ---------------------------------------------------------------------------

VALID_PHASE_TRANSITIONS: dict[IncidentPhase, set[IncidentPhase]] = {
    IncidentPhase.DETECTION: {IncidentPhase.TRIAGE},
    IncidentPhase.TRIAGE: {IncidentPhase.CONTAINMENT, IncidentPhase.CLOSED},
    IncidentPhase.CONTAINMENT: {IncidentPhase.ERADICATION, IncidentPhase.CLOSED},
    IncidentPhase.ERADICATION: {IncidentPhase.RECOVERY, IncidentPhase.CLOSED},
    IncidentPhase.RECOVERY: {IncidentPhase.POST_INCIDENT, IncidentPhase.CLOSED},
    IncidentPhase.POST_INCIDENT: {IncidentPhase.CLOSED},
    IncidentPhase.CLOSED: set(),  # terminal
}


class IncidentResponseService:
    """In-memory incident response management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._playbooks: dict[str, Playbook] = {}
        self._incidents: dict[str, IncidentRecord] = {}
        self._reviews: dict[str, PostIncidentReview] = {}
        self._escalation_matrix: list[EscalationMatrix] = []
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo seed data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic playbooks, incidents, and reviews."""
        now = datetime.now(timezone.utc)

        # ---- Playbooks (8 types) ----
        self._seed_playbooks(now)

        # ---- Escalation matrix ----
        self._seed_escalation_matrix()

        # ---- Incidents (6 total: 2 active, 4 closed) ----
        self._seed_incidents(now)

        # ---- Post-incident reviews (3 for closed incidents) ----
        self._seed_reviews(now)

    def _seed_playbooks(self, now: datetime) -> None:
        """Seed 8 playbooks with 5-8 steps each."""
        playbook_defs = [
            {
                "id": "PB-DATA-BREACH",
                "playbook_type": PlaybookType.DATA_BREACH,
                "title": "Data Breach Response Playbook",
                "description": "Comprehensive response procedures for data breaches involving PHI, PII, or clinical trial data. Covers HIPAA and GDPR notification requirements.",
                "severity_threshold": IncidentSeverity.SEV1_CRITICAL,
                "steps": [
                    PlaybookStep(step_number=1, title="Initial Detection Verification", description="Verify the breach alert and confirm scope of data exposure. Check SIEM logs, DLP alerts, and access logs.", responsible_role="SOC Analyst", time_limit_minutes=15, automated=True, checklist_items=["Verify alert source", "Check SIEM correlation", "Identify data types exposed", "Determine initial scope"]),
                    PlaybookStep(step_number=2, title="Incident Classification", description="Classify the breach type, severity, and regulatory impact. Determine if PHI/PII is involved.", responsible_role="IR Lead", time_limit_minutes=15, automated=False, checklist_items=["Classify data types", "Assess regulatory impact", "Determine severity level", "Identify affected systems"]),
                    PlaybookStep(step_number=3, title="Containment Actions", description="Isolate affected systems, revoke compromised credentials, and block exfiltration channels.", responsible_role="IR Team", time_limit_minutes=60, automated=True, checklist_items=["Isolate affected hosts", "Revoke compromised creds", "Block exfiltration IPs", "Preserve forensic evidence"]),
                    PlaybookStep(step_number=4, title="Evidence Collection", description="Collect and preserve forensic evidence including memory dumps, disk images, and network captures.", responsible_role="Forensics Analyst", time_limit_minutes=120, automated=False, checklist_items=["Capture memory dumps", "Create disk images", "Save network captures", "Document chain of custody"]),
                    PlaybookStep(step_number=5, title="Patient Impact Assessment", description="Determine the number of affected patients and types of clinical data compromised.", responsible_role="Privacy Officer", time_limit_minutes=240, automated=False, checklist_items=["Count affected patients", "Identify data elements exposed", "Assess clinical trial impact", "Document findings"]),
                    PlaybookStep(step_number=6, title="Regulatory Notification", description="Prepare and submit required notifications to HHS, state AGs, and affected individuals per HIPAA.", responsible_role="Compliance Officer", time_limit_minutes=480, automated=False, checklist_items=["Draft HHS notification", "Prepare state notifications", "Draft patient letters", "Coordinate media response"]),
                    PlaybookStep(step_number=7, title="Eradication and Recovery", description="Remove threat actor access, patch vulnerabilities, and restore systems from clean backups.", responsible_role="IR Team", time_limit_minutes=480, automated=False, checklist_items=["Remove malware/backdoors", "Patch vulnerabilities", "Restore from backups", "Verify system integrity"]),
                    PlaybookStep(step_number=8, title="Post-Incident Review", description="Conduct lessons learned meeting and update security controls.", responsible_role="CISO", time_limit_minutes=1440, automated=False, checklist_items=["Schedule review meeting", "Document timeline", "Identify improvements", "Update playbook"]),
                ],
            },
            {
                "id": "PB-RANSOMWARE",
                "playbook_type": PlaybookType.RANSOMWARE,
                "title": "Ransomware Response Playbook",
                "description": "Response procedures for ransomware attacks targeting clinical systems. Includes backup verification, negotiation guidance, and recovery procedures.",
                "severity_threshold": IncidentSeverity.SEV1_CRITICAL,
                "steps": [
                    PlaybookStep(step_number=1, title="Detect and Confirm Ransomware", description="Verify ransomware indicators, identify strain, and determine encryption scope.", responsible_role="SOC Analyst", time_limit_minutes=10, automated=True, checklist_items=["Identify ransomware strain", "Determine encryption scope", "Check for lateral movement", "Preserve ransom note"]),
                    PlaybookStep(step_number=2, title="Network Isolation", description="Immediately isolate infected systems to prevent lateral spread.", responsible_role="Network Engineer", time_limit_minutes=15, automated=True, checklist_items=["Isolate infected segments", "Block C2 communications", "Disable SMB shares", "Kill suspicious processes"]),
                    PlaybookStep(step_number=3, title="Backup Assessment", description="Verify backup integrity and determine recovery point objectives.", responsible_role="Backup Admin", time_limit_minutes=60, automated=False, checklist_items=["Check backup integrity", "Verify RPO/RTO", "Test restore capability", "Identify clean restore points"]),
                    PlaybookStep(step_number=4, title="Law Enforcement Notification", description="Report to FBI IC3, CISA, and coordinate with cyber insurance carrier.", responsible_role="Legal Counsel", time_limit_minutes=120, automated=False, checklist_items=["Notify FBI IC3", "Report to CISA", "Contact cyber insurance", "Engage external IR firm"]),
                    PlaybookStep(step_number=5, title="System Recovery", description="Rebuild systems from clean backups and reimages, apply patches.", responsible_role="IT Operations", time_limit_minutes=480, automated=False, checklist_items=["Rebuild from clean images", "Apply security patches", "Restore data from backups", "Verify system integrity"]),
                    PlaybookStep(step_number=6, title="Threat Hunting", description="Hunt for persistence mechanisms and additional compromised systems.", responsible_role="Threat Hunter", time_limit_minutes=480, automated=False, checklist_items=["Scan for IOCs", "Check for persistence", "Review all endpoints", "Verify AD integrity"]),
                ],
            },
            {
                "id": "PB-INSIDER",
                "playbook_type": PlaybookType.INSIDER_THREAT,
                "title": "Insider Threat Response Playbook",
                "description": "Procedures for investigating and responding to malicious or negligent insider threats within clinical trial operations.",
                "severity_threshold": IncidentSeverity.SEV2_HIGH,
                "steps": [
                    PlaybookStep(step_number=1, title="Alert Verification", description="Verify DLP, UEBA, or HR-reported insider threat indicators.", responsible_role="SOC Analyst", time_limit_minutes=30, automated=True, checklist_items=["Verify alert source", "Review UEBA anomalies", "Check DLP alerts", "Cross-reference HR reports"]),
                    PlaybookStep(step_number=2, title="Covert Investigation", description="Initiate covert investigation without tipping off the subject.", responsible_role="IR Lead", time_limit_minutes=60, automated=False, checklist_items=["Brief legal counsel", "Set up monitoring", "Review access logs", "Check data exfiltration"]),
                    PlaybookStep(step_number=3, title="Access Restriction", description="Restrict or revoke subject access based on risk assessment.", responsible_role="IAM Team", time_limit_minutes=30, automated=True, checklist_items=["Revoke privileged access", "Disable remote access", "Monitor remaining access", "Preserve audit logs"]),
                    PlaybookStep(step_number=4, title="Evidence Preservation", description="Preserve all digital evidence for potential legal proceedings.", responsible_role="Forensics Analyst", time_limit_minutes=120, automated=False, checklist_items=["Image workstation", "Export email archives", "Capture cloud activity", "Document chain of custody"]),
                    PlaybookStep(step_number=5, title="HR and Legal Coordination", description="Coordinate with HR, legal, and management for appropriate response.", responsible_role="CISO", time_limit_minutes=240, automated=False, checklist_items=["Brief HR leadership", "Engage legal counsel", "Plan termination if needed", "Prepare regulatory filings"]),
                ],
            },
            {
                "id": "PB-PHISHING",
                "playbook_type": PlaybookType.PHISHING,
                "title": "Phishing Response Playbook",
                "description": "Response procedures for phishing campaigns targeting clinical trial personnel and researchers.",
                "severity_threshold": IncidentSeverity.SEV3_MEDIUM,
                "steps": [
                    PlaybookStep(step_number=1, title="Report Analysis", description="Analyze reported phishing email for IOCs and threat intelligence.", responsible_role="SOC Analyst", time_limit_minutes=15, automated=True, checklist_items=["Analyze email headers", "Extract URLs and attachments", "Check threat intel feeds", "Identify affected users"]),
                    PlaybookStep(step_number=2, title="Scope Assessment", description="Determine how many users received and/or clicked the phishing email.", responsible_role="SOC Analyst", time_limit_minutes=30, automated=True, checklist_items=["Search email gateway logs", "Identify all recipients", "Check web proxy for clicks", "Assess credential exposure"]),
                    PlaybookStep(step_number=3, title="Containment", description="Block malicious URLs, quarantine emails, and reset compromised credentials.", responsible_role="Email Admin", time_limit_minutes=30, automated=True, checklist_items=["Block sender domain", "Quarantine all copies", "Block malicious URLs", "Reset compromised passwords"]),
                    PlaybookStep(step_number=4, title="User Communication", description="Notify affected users and provide guidance on recognizing phishing.", responsible_role="Security Awareness", time_limit_minutes=60, automated=False, checklist_items=["Notify affected users", "Send awareness reminder", "Update phishing examples", "Track acknowledgments"]),
                    PlaybookStep(step_number=5, title="Post-Action Review", description="Update detection rules and conduct targeted training.", responsible_role="IR Lead", time_limit_minutes=120, automated=False, checklist_items=["Update email filters", "Add IOCs to blocklists", "Schedule targeted training", "Document lessons learned"]),
                ],
            },
            {
                "id": "PB-DDOS",
                "playbook_type": PlaybookType.DDOS,
                "title": "DDoS Response Playbook",
                "description": "Procedures for mitigating distributed denial of service attacks against clinical trial platform infrastructure.",
                "severity_threshold": IncidentSeverity.SEV2_HIGH,
                "steps": [
                    PlaybookStep(step_number=1, title="Attack Detection", description="Identify DDoS attack vector, volume, and target services.", responsible_role="NOC Analyst", time_limit_minutes=5, automated=True, checklist_items=["Identify attack type", "Measure attack volume", "Determine target services", "Check CDN status"]),
                    PlaybookStep(step_number=2, title="Initial Mitigation", description="Activate DDoS protection services and rate limiting.", responsible_role="Network Engineer", time_limit_minutes=15, automated=True, checklist_items=["Enable DDoS scrubbing", "Activate rate limiting", "Geo-block if appropriate", "Scale infrastructure"]),
                    PlaybookStep(step_number=3, title="Traffic Analysis", description="Analyze attack patterns and adjust mitigation rules.", responsible_role="SOC Analyst", time_limit_minutes=30, automated=False, checklist_items=["Analyze traffic patterns", "Tune WAF rules", "Identify botnet sources", "Monitor effectiveness"]),
                    PlaybookStep(step_number=4, title="Service Restoration", description="Verify service restoration and monitor for re-attack.", responsible_role="IT Operations", time_limit_minutes=60, automated=False, checklist_items=["Verify service availability", "Check data integrity", "Monitor for re-attack", "Update stakeholders"]),
                    PlaybookStep(step_number=5, title="Post-Attack Hardening", description="Update DDoS protection configuration and document attack details.", responsible_role="Security Engineer", time_limit_minutes=240, automated=False, checklist_items=["Update DDoS profiles", "Document attack details", "Review architecture", "Update runbooks"]),
                ],
            },
            {
                "id": "PB-SUPPLY-CHAIN",
                "playbook_type": PlaybookType.SUPPLY_CHAIN,
                "title": "Supply Chain Attack Response Playbook",
                "description": "Response procedures for supply chain compromises affecting clinical platform dependencies and third-party integrations.",
                "severity_threshold": IncidentSeverity.SEV1_CRITICAL,
                "steps": [
                    PlaybookStep(step_number=1, title="Compromise Identification", description="Identify the compromised component, version, and blast radius.", responsible_role="Security Engineer", time_limit_minutes=30, automated=True, checklist_items=["Identify compromised package", "Check SBOM for exposure", "Determine blast radius", "Review advisories"]),
                    PlaybookStep(step_number=2, title="Impact Assessment", description="Assess impact on clinical systems, data integrity, and patient safety.", responsible_role="IR Lead", time_limit_minutes=60, automated=False, checklist_items=["Map affected systems", "Check data integrity", "Assess patient safety impact", "Review deployment history"]),
                    PlaybookStep(step_number=3, title="Containment", description="Isolate affected components, block malicious updates, and pin dependencies.", responsible_role="DevOps Team", time_limit_minutes=60, automated=True, checklist_items=["Pin affected dependencies", "Block malicious registries", "Isolate build pipelines", "Review CI/CD logs"]),
                    PlaybookStep(step_number=4, title="Remediation", description="Remove compromised components, apply patches, and rebuild from trusted sources.", responsible_role="Development Team", time_limit_minutes=480, automated=False, checklist_items=["Remove compromised code", "Apply vendor patches", "Rebuild from trusted source", "Verify integrity"]),
                    PlaybookStep(step_number=5, title="Vendor Notification", description="Notify affected vendors, partners, and regulatory bodies.", responsible_role="Compliance Officer", time_limit_minutes=240, automated=False, checklist_items=["Notify affected vendors", "Report to CISA", "Update vendor risk assessments", "Review contracts"]),
                    PlaybookStep(step_number=6, title="Enhanced Monitoring", description="Implement enhanced monitoring for supply chain indicators.", responsible_role="SOC Team", time_limit_minutes=1440, automated=True, checklist_items=["Deploy SBOM monitoring", "Add supply chain IOCs", "Monitor dependency changes", "Review access patterns"]),
                ],
            },
            {
                "id": "PB-ZERO-DAY",
                "playbook_type": PlaybookType.ZERO_DAY,
                "title": "Zero-Day Exploit Response Playbook",
                "description": "Response procedures for zero-day vulnerability exploitation in clinical systems.",
                "severity_threshold": IncidentSeverity.SEV1_CRITICAL,
                "steps": [
                    PlaybookStep(step_number=1, title="Exploit Detection", description="Detect and confirm zero-day exploitation through behavioral analysis.", responsible_role="SOC Analyst", time_limit_minutes=15, automated=True, checklist_items=["Confirm exploitation", "Identify affected component", "Check for active exploitation", "Assess scope"]),
                    PlaybookStep(step_number=2, title="Emergency Containment", description="Apply emergency mitigations including virtual patching and network restrictions.", responsible_role="Security Engineer", time_limit_minutes=30, automated=True, checklist_items=["Apply virtual patch", "Restrict network access", "Enable enhanced logging", "Block known exploit patterns"]),
                    PlaybookStep(step_number=3, title="Threat Intelligence Sharing", description="Share IOCs with industry peers and ISAC.", responsible_role="Threat Intel", time_limit_minutes=60, automated=False, checklist_items=["Document IOCs", "Share with H-ISAC", "Contact vendor", "Monitor for patches"]),
                    PlaybookStep(step_number=4, title="Forensic Analysis", description="Conduct detailed forensic analysis of exploitation.", responsible_role="Forensics Analyst", time_limit_minutes=240, automated=False, checklist_items=["Analyze exploit chain", "Determine data access", "Check for persistence", "Document findings"]),
                    PlaybookStep(step_number=5, title="Patch and Harden", description="Apply vendor patch when available and harden affected systems.", responsible_role="IT Operations", time_limit_minutes=480, automated=False, checklist_items=["Apply vendor patch", "Remove virtual patch", "Harden configuration", "Verify remediation"]),
                ],
            },
            {
                "id": "PB-UNAUTH-ACCESS",
                "playbook_type": PlaybookType.UNAUTHORIZED_ACCESS,
                "title": "Unauthorized Access Response Playbook",
                "description": "Response procedures for unauthorized access to clinical systems, patient data, or administrative functions.",
                "severity_threshold": IncidentSeverity.SEV2_HIGH,
                "steps": [
                    PlaybookStep(step_number=1, title="Access Verification", description="Verify unauthorized access alert and determine access method.", responsible_role="SOC Analyst", time_limit_minutes=15, automated=True, checklist_items=["Verify alert", "Identify access method", "Check credentials used", "Determine access scope"]),
                    PlaybookStep(step_number=2, title="Account Lockdown", description="Disable compromised accounts and revoke active sessions.", responsible_role="IAM Team", time_limit_minutes=15, automated=True, checklist_items=["Disable compromised accounts", "Revoke active sessions", "Reset credentials", "Review MFA status"]),
                    PlaybookStep(step_number=3, title="Access Log Review", description="Review detailed access logs to determine data accessed.", responsible_role="SOC Analyst", time_limit_minutes=60, automated=False, checklist_items=["Review access logs", "Identify data accessed", "Check for data export", "Document timeline"]),
                    PlaybookStep(step_number=4, title="Impact Assessment", description="Determine impact on patient data, trial integrity, and compliance.", responsible_role="Privacy Officer", time_limit_minutes=120, automated=False, checklist_items=["Assess patient data impact", "Check trial data integrity", "Review compliance impact", "Determine notification needs"]),
                    PlaybookStep(step_number=5, title="Access Control Remediation", description="Strengthen access controls and implement additional safeguards.", responsible_role="Security Engineer", time_limit_minutes=240, automated=False, checklist_items=["Review RBAC policies", "Implement additional controls", "Update monitoring rules", "Schedule access review"]),
                ],
            },
        ]

        for pb_def in playbook_defs:
            steps = pb_def.pop("steps")
            pb = Playbook(
                **pb_def,
                steps=steps,
                last_tested=now - timedelta(days=45),
                test_frequency_days=90,
                version="1.0",
                created_at=now - timedelta(days=180),
                updated_at=now - timedelta(days=30),
            )
            self._playbooks[pb.id] = pb

    def _seed_escalation_matrix(self) -> None:
        """Seed escalation matrix for each severity level."""
        self._escalation_matrix = [
            EscalationMatrix(
                severity=IncidentSeverity.SEV1_CRITICAL,
                escalation_level=EscalationLevel.L4_EXECUTIVE,
                contacts=[
                    EscalationContact(name="Dr. Sarah Mitchell", role="CISO", email="ciso@pharma.com", phone="+1-555-0101", notification_methods=["phone", "email", "sms"]),
                    EscalationContact(name="James Rodriguez", role="VP Engineering", email="vpe@pharma.com", phone="+1-555-0102", notification_methods=["phone", "email", "sms"]),
                    EscalationContact(name="Maria Chen", role="General Counsel", email="legal@pharma.com", phone="+1-555-0103", notification_methods=["phone", "email"]),
                ],
                auto_escalate_after_minutes=15,
            ),
            EscalationMatrix(
                severity=IncidentSeverity.SEV2_HIGH,
                escalation_level=EscalationLevel.L3_CISO,
                contacts=[
                    EscalationContact(name="Dr. Sarah Mitchell", role="CISO", email="ciso@pharma.com", phone="+1-555-0101", notification_methods=["phone", "email"]),
                    EscalationContact(name="David Park", role="IR Manager", email="ir-manager@pharma.com", phone="+1-555-0104", notification_methods=["phone", "email", "sms"]),
                ],
                auto_escalate_after_minutes=30,
            ),
            EscalationMatrix(
                severity=IncidentSeverity.SEV3_MEDIUM,
                escalation_level=EscalationLevel.L2_IR_TEAM,
                contacts=[
                    EscalationContact(name="David Park", role="IR Manager", email="ir-manager@pharma.com", phone="+1-555-0104", notification_methods=["email", "sms"]),
                    EscalationContact(name="Alex Johnson", role="SOC Lead", email="soc-lead@pharma.com", phone="+1-555-0105", notification_methods=["email"]),
                ],
                auto_escalate_after_minutes=120,
            ),
            EscalationMatrix(
                severity=IncidentSeverity.SEV4_LOW,
                escalation_level=EscalationLevel.L1_SOC,
                contacts=[
                    EscalationContact(name="Alex Johnson", role="SOC Lead", email="soc-lead@pharma.com", phone="+1-555-0105", notification_methods=["email"]),
                ],
                auto_escalate_after_minutes=480,
            ),
        ]

    def _seed_incidents(self, now: datetime) -> None:
        """Seed 6 incidents (2 active, 4 closed)."""
        # Active Incident 1: Data breach in CONTAINMENT
        inc1_id = "INC-20260101-001"
        inc1_events = [
            IncidentEvent(id="EVT-001-01", incident_id=inc1_id, timestamp=now - timedelta(hours=6), phase=IncidentPhase.DETECTION, description="SIEM alert triggered: anomalous data export from clinical database", actor="SIEM System", evidence_refs=["siem-alert-4521"]),
            IncidentEvent(id="EVT-001-02", incident_id=inc1_id, timestamp=now - timedelta(hours=5, minutes=45), phase=IncidentPhase.TRIAGE, description="SOC analyst confirmed unauthorized bulk export of patient screening data", actor="Alex Johnson", evidence_refs=["siem-alert-4521", "access-log-export-001"]),
            IncidentEvent(id="EVT-001-03", incident_id=inc1_id, timestamp=now - timedelta(hours=5), phase=IncidentPhase.CONTAINMENT, description="Compromised service account disabled, database access revoked", actor="IAM Team", evidence_refs=["iam-ticket-789"]),
        ]
        inc1_notifications = [
            RegulatoryNotification(id="NOTIF-001-01", incident_id=inc1_id, notification_type=NotificationType.INTERNAL_STAKEHOLDER, deadline=now - timedelta(hours=5), sent_at=now - timedelta(hours=5, minutes=30), recipient="CISO Office", status=NotificationStatus.SENT, content_summary="Data breach detected - patient screening data exported"),
            RegulatoryNotification(id="NOTIF-001-02", incident_id=inc1_id, notification_type=NotificationType.HIPAA_BREACH, deadline=now + timedelta(days=58), sent_at=None, recipient="HHS OCR", status=NotificationStatus.PENDING, content_summary="HIPAA breach notification - pending investigation completion"),
        ]
        self._incidents[inc1_id] = IncidentRecord(
            id=inc1_id, title="Unauthorized PHI Export from Screening Database", description="Anomalous bulk export of patient screening data detected via SIEM. Compromised service account used to export 2,847 patient records.",
            severity=IncidentSeverity.SEV1_CRITICAL, category=IncidentCategory.DATA_BREACH, phase=IncidentPhase.CONTAINMENT,
            detected_at=now - timedelta(hours=6), reported_by="SIEM Auto-Alert", assigned_to="David Park",
            playbook_id="PB-DATA-BREACH", events=inc1_events, notifications=inc1_notifications,
            containment_time_minutes=60, resolution_time_minutes=None, root_cause=None, lessons_learned=None,
            affected_systems=["screening-db", "patient-api", "etl-pipeline"], affected_patients_count=2847,
            data_compromised=True, escalation_level=EscalationLevel.L4_EXECUTIVE,
            created_at=now - timedelta(hours=6), updated_at=now - timedelta(hours=1), closed_at=None,
        )

        # Active Incident 2: Phishing in TRIAGE
        inc2_id = "INC-20260101-002"
        inc2_events = [
            IncidentEvent(id="EVT-002-01", incident_id=inc2_id, timestamp=now - timedelta(hours=2), phase=IncidentPhase.DETECTION, description="User reported suspicious email impersonating clinical trial coordinator", actor="Jane Researcher", evidence_refs=["phish-report-088"]),
            IncidentEvent(id="EVT-002-02", incident_id=inc2_id, timestamp=now - timedelta(hours=1, minutes=40), phase=IncidentPhase.TRIAGE, description="SOC confirmed targeted spear-phishing campaign against trial staff", actor="SOC Analyst", evidence_refs=["phish-report-088", "email-analysis-012"]),
        ]
        self._incidents[inc2_id] = IncidentRecord(
            id=inc2_id, title="Targeted Spear-Phishing Campaign Against Trial Staff", description="Spear-phishing emails targeting clinical trial coordinators with fake IRB approval documents containing credential harvester.",
            severity=IncidentSeverity.SEV3_MEDIUM, category=IncidentCategory.PHISHING, phase=IncidentPhase.TRIAGE,
            detected_at=now - timedelta(hours=2), reported_by="Jane Researcher", assigned_to="Alex Johnson",
            playbook_id="PB-PHISHING", events=inc2_events, notifications=[],
            containment_time_minutes=None, resolution_time_minutes=None, root_cause=None, lessons_learned=None,
            affected_systems=["email-gateway", "office365"], affected_patients_count=0,
            data_compromised=False, escalation_level=EscalationLevel.L2_IR_TEAM,
            created_at=now - timedelta(hours=2), updated_at=now - timedelta(hours=1), closed_at=None,
        )

        # Closed Incident 3: Ransomware (resolved 30 days ago)
        inc3_id = "INC-20251201-003"
        closed3 = now - timedelta(days=28)
        self._incidents[inc3_id] = IncidentRecord(
            id=inc3_id, title="Ransomware Attack on Development Environment", description="LockBit 3.0 ransomware detected in development environment. No production or clinical data affected.",
            severity=IncidentSeverity.SEV2_HIGH, category=IncidentCategory.RANSOMWARE, phase=IncidentPhase.CLOSED,
            detected_at=now - timedelta(days=32), reported_by="EDR Auto-Alert", assigned_to="David Park",
            playbook_id="PB-RANSOMWARE",
            events=[
                IncidentEvent(id="EVT-003-01", incident_id=inc3_id, timestamp=now - timedelta(days=32), phase=IncidentPhase.DETECTION, description="EDR detected ransomware execution on dev server", actor="EDR System", evidence_refs=["edr-alert-772"]),
                IncidentEvent(id="EVT-003-02", incident_id=inc3_id, timestamp=now - timedelta(days=32) + timedelta(minutes=10), phase=IncidentPhase.TRIAGE, description="Confirmed LockBit 3.0 strain, dev environment only", actor="SOC Analyst", evidence_refs=["edr-alert-772", "malware-hash-001"]),
                IncidentEvent(id="EVT-003-03", incident_id=inc3_id, timestamp=now - timedelta(days=32) + timedelta(minutes=25), phase=IncidentPhase.CONTAINMENT, description="Dev network segment isolated from production", actor="Network Team", evidence_refs=["fw-change-445"]),
                IncidentEvent(id="EVT-003-04", incident_id=inc3_id, timestamp=now - timedelta(days=30), phase=IncidentPhase.RECOVERY, description="Dev environment rebuilt from clean images", actor="IT Operations", evidence_refs=["rebuild-ticket-201"]),
            ],
            notifications=[
                RegulatoryNotification(id="NOTIF-003-01", incident_id=inc3_id, notification_type=NotificationType.CYBER_INSURANCE, deadline=now - timedelta(days=30), sent_at=now - timedelta(days=31), recipient="Cyber Insurance Provider", status=NotificationStatus.SENT, content_summary="Ransomware incident - dev environment only, no clinical data affected"),
                RegulatoryNotification(id="NOTIF-003-02", incident_id=inc3_id, notification_type=NotificationType.LAW_ENFORCEMENT, deadline=now - timedelta(days=25), sent_at=now - timedelta(days=30), recipient="FBI IC3", status=NotificationStatus.SENT, content_summary="LockBit 3.0 ransomware incident report"),
            ],
            containment_time_minutes=25, resolution_time_minutes=2880,
            root_cause="Unpatched development server exposed RDP to internet via misconfigured firewall rule.",
            lessons_learned="Implement network segmentation verification checks. Add RDP exposure monitoring. Require MFA for all remote access.",
            affected_systems=["dev-server-01", "dev-server-02", "dev-ci-runner"], affected_patients_count=0,
            data_compromised=False, escalation_level=EscalationLevel.L3_CISO,
            created_at=now - timedelta(days=32), updated_at=closed3, closed_at=closed3,
        )

        # Closed Incident 4: Insider threat (resolved 45 days ago)
        inc4_id = "INC-20251115-004"
        closed4 = now - timedelta(days=43)
        self._incidents[inc4_id] = IncidentRecord(
            id=inc4_id, title="Departing Employee Data Exfiltration Attempt", description="DLP alert triggered when departing employee attempted to download trial enrollment data to personal cloud storage.",
            severity=IncidentSeverity.SEV2_HIGH, category=IncidentCategory.INSIDER_THREAT, phase=IncidentPhase.CLOSED,
            detected_at=now - timedelta(days=48), reported_by="DLP System", assigned_to="David Park",
            playbook_id="PB-INSIDER",
            events=[
                IncidentEvent(id="EVT-004-01", incident_id=inc4_id, timestamp=now - timedelta(days=48), phase=IncidentPhase.DETECTION, description="DLP blocked upload of trial enrollment data to personal Google Drive", actor="DLP System", evidence_refs=["dlp-alert-331"]),
                IncidentEvent(id="EVT-004-02", incident_id=inc4_id, timestamp=now - timedelta(days=48) + timedelta(hours=1), phase=IncidentPhase.CONTAINMENT, description="Employee access suspended pending investigation", actor="IAM Team", evidence_refs=["iam-ticket-445"]),
            ],
            notifications=[
                RegulatoryNotification(id="NOTIF-004-01", incident_id=inc4_id, notification_type=NotificationType.INTERNAL_STAKEHOLDER, deadline=now - timedelta(days=47), sent_at=now - timedelta(days=47, hours=-2), recipient="HR Department", status=NotificationStatus.SENT, content_summary="Employee data exfiltration attempt - DLP blocked"),
            ],
            containment_time_minutes=60, resolution_time_minutes=7200,
            root_cause="Departing employee attempted to retain competitive intelligence before resignation effective date.",
            lessons_learned="Implement automated access restriction upon resignation notice. Enhance DLP monitoring for departing employees.",
            affected_systems=["cloud-storage", "enrollment-system"], affected_patients_count=0,
            data_compromised=False, escalation_level=EscalationLevel.L3_CISO,
            created_at=now - timedelta(days=48), updated_at=closed4, closed_at=closed4,
        )

        # Closed Incident 5: DDoS (resolved 60 days ago)
        inc5_id = "INC-20251101-005"
        closed5 = now - timedelta(days=58)
        self._incidents[inc5_id] = IncidentRecord(
            id=inc5_id, title="DDoS Attack on Patient Portal", description="Volumetric DDoS attack targeting patient screening portal during peak enrollment period.",
            severity=IncidentSeverity.SEV3_MEDIUM, category=IncidentCategory.DDOS, phase=IncidentPhase.CLOSED,
            detected_at=now - timedelta(days=62), reported_by="CDN Auto-Alert", assigned_to="Network Team",
            playbook_id="PB-DDOS",
            events=[
                IncidentEvent(id="EVT-005-01", incident_id=inc5_id, timestamp=now - timedelta(days=62), phase=IncidentPhase.DETECTION, description="CDN detected 40Gbps volumetric DDoS attack", actor="CDN System", evidence_refs=["cdn-alert-667"]),
                IncidentEvent(id="EVT-005-02", incident_id=inc5_id, timestamp=now - timedelta(days=62) + timedelta(minutes=5), phase=IncidentPhase.CONTAINMENT, description="DDoS scrubbing activated, traffic normalized within 20 minutes", actor="CDN System", evidence_refs=["cdn-scrub-report-112"]),
            ],
            notifications=[],
            containment_time_minutes=25, resolution_time_minutes=120,
            root_cause="Botnet targeting healthcare portals. Attack sourced from compromised IoT devices.",
            lessons_learned="Pre-position DDoS scrubbing for enrollment peak periods. Implement geo-based rate limiting.",
            affected_systems=["patient-portal", "cdn-edge"], affected_patients_count=0,
            data_compromised=False, escalation_level=EscalationLevel.L2_IR_TEAM,
            created_at=now - timedelta(days=62), updated_at=closed5, closed_at=closed5,
        )

        # Closed Incident 6: Compliance violation (resolved 20 days ago)
        inc6_id = "INC-20260110-006"
        closed6 = now - timedelta(days=18)
        self._incidents[inc6_id] = IncidentRecord(
            id=inc6_id, title="Unencrypted PHI Transmission via Legacy API", description="Audit discovered legacy API endpoint transmitting PHI without TLS encryption.",
            severity=IncidentSeverity.SEV4_LOW, category=IncidentCategory.COMPLIANCE_VIOLATION, phase=IncidentPhase.CLOSED,
            detected_at=now - timedelta(days=25), reported_by="Internal Audit", assigned_to="Security Engineer",
            playbook_id=None,
            events=[
                IncidentEvent(id="EVT-006-01", incident_id=inc6_id, timestamp=now - timedelta(days=25), phase=IncidentPhase.DETECTION, description="Internal audit found legacy API endpoint without TLS", actor="Internal Audit", evidence_refs=["audit-finding-102"]),
                IncidentEvent(id="EVT-006-02", incident_id=inc6_id, timestamp=now - timedelta(days=24), phase=IncidentPhase.CONTAINMENT, description="Legacy API endpoint disabled pending TLS enforcement", actor="DevOps Team", evidence_refs=["change-ticket-889"]),
            ],
            notifications=[
                RegulatoryNotification(id="NOTIF-006-01", incident_id=inc6_id, notification_type=NotificationType.INTERNAL_STAKEHOLDER, deadline=now - timedelta(days=24), sent_at=now - timedelta(days=24), recipient="Compliance Team", status=NotificationStatus.SENT, content_summary="Legacy API PHI transmission without TLS - endpoint disabled"),
            ],
            containment_time_minutes=1440, resolution_time_minutes=10080,
            root_cause="Legacy API endpoint from v1 migration was not decommissioned and lacked TLS enforcement.",
            lessons_learned="Conduct API inventory audit quarterly. Enforce TLS at load balancer level to prevent endpoint-level gaps.",
            affected_systems=["legacy-api-v1"], affected_patients_count=12,
            data_compromised=False, escalation_level=EscalationLevel.L1_SOC,
            created_at=now - timedelta(days=25), updated_at=closed6, closed_at=closed6,
        )

    def _seed_reviews(self, now: datetime) -> None:
        """Seed 3 post-incident reviews for closed incidents."""
        self._reviews["PIR-003"] = PostIncidentReview(
            id="PIR-003", incident_id="INC-20251201-003", review_date=now - timedelta(days=26),
            participants=["Dr. Sarah Mitchell", "David Park", "Alex Johnson", "Network Team Lead"],
            findings=[
                "RDP was exposed to internet due to firewall misconfiguration during maintenance window",
                "EDR detected ransomware within 3 minutes of execution - detection capability validated",
                "Dev environment isolation from production prevented clinical data exposure",
                "Backup restoration took longer than expected due to incomplete backup verification",
            ],
            action_items=[
                "Implement automated firewall rule auditing (due in 30 days)",
                "Add RDP exposure check to continuous monitoring dashboard",
                "Reduce dev environment backup RTO from 48h to 12h",
                "Conduct quarterly tabletop exercises for ransomware scenarios",
            ],
            effectiveness_rating=7.5, recurrence_risk="LOW",
        )

        self._reviews["PIR-004"] = PostIncidentReview(
            id="PIR-004", incident_id="INC-20251115-004", review_date=now - timedelta(days=40),
            participants=["Dr. Sarah Mitchell", "David Park", "HR Director", "Legal Counsel"],
            findings=[
                "DLP successfully blocked the exfiltration attempt",
                "Employee access was not restricted upon resignation notice submission",
                "Investigation revealed no prior successful exfiltration",
                "HR-Security coordination process had communication gaps",
            ],
            action_items=[
                "Automate access restriction trigger upon HR resignation notice",
                "Implement enhanced monitoring for employees in notice period",
                "Create cross-functional HR-Security coordination SOP",
                "Review and update acceptable use policy language",
            ],
            effectiveness_rating=8.0, recurrence_risk="MEDIUM",
        )

        self._reviews["PIR-005"] = PostIncidentReview(
            id="PIR-005", incident_id="INC-20251101-005", review_date=now - timedelta(days=55),
            participants=["David Park", "Network Team Lead", "CDN Provider Rep"],
            findings=[
                "CDN auto-scrubbing mitigated attack within 20 minutes",
                "Patient portal experienced 15-minute service degradation during mitigation ramp-up",
                "No data loss or patient safety impact",
                "Attack was part of broader healthcare sector targeting campaign",
            ],
            action_items=[
                "Pre-activate enhanced DDoS protection during enrollment peaks",
                "Implement always-on scrubbing for critical endpoints",
                "Join Health-ISAC information sharing for threat intelligence",
            ],
            effectiveness_rating=8.5, recurrence_risk="MEDIUM",
        )

    # ------------------------------------------------------------------
    # Playbook CRUD
    # ------------------------------------------------------------------

    def list_playbooks(
        self,
        *,
        playbook_type: PlaybookType | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Playbook], int]:
        """List playbooks with optional filtering and pagination."""
        records = list(self._playbooks.values())
        if playbook_type is not None:
            records = [r for r in records if r.playbook_type == playbook_type]
        records.sort(key=lambda r: r.created_at, reverse=True)
        total = len(records)
        return records[offset : offset + limit], total

    def get_playbook(self, playbook_id: str) -> Playbook:
        """Get a specific playbook by ID.

        Raises ``KeyError`` if not found.
        """
        pb = self._playbooks.get(playbook_id)
        if pb is None:
            raise KeyError(f"Playbook {playbook_id} not found")
        return pb

    def create_playbook(
        self,
        playbook_type: PlaybookType,
        title: str,
        description: str,
        severity_threshold: IncidentSeverity,
        steps: list[PlaybookStep],
        test_frequency_days: int = 90,
    ) -> Playbook:
        """Create a new playbook."""
        now = datetime.now(timezone.utc)
        pb_id = f"PB-{uuid4().hex[:8].upper()}"
        pb = Playbook(
            id=pb_id,
            playbook_type=playbook_type,
            title=title,
            description=description,
            severity_threshold=severity_threshold,
            steps=steps,
            test_frequency_days=test_frequency_days,
            version="1.0",
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._playbooks[pb_id] = pb
        logger.info("Created playbook %s: %s", pb_id, title)
        return pb

    def update_playbook(
        self,
        playbook_id: str,
        *,
        title: str | None = None,
        description: str | None = None,
        steps: list[PlaybookStep] | None = None,
        severity_threshold: IncidentSeverity | None = None,
        test_frequency_days: int | None = None,
    ) -> Playbook:
        """Update an existing playbook.

        Raises ``KeyError`` if not found.
        """
        with self._lock:
            pb = self._playbooks.get(playbook_id)
            if pb is None:
                raise KeyError(f"Playbook {playbook_id} not found")

            now = datetime.now(timezone.utc)
            updates: dict = {"updated_at": now}
            if title is not None:
                updates["title"] = title
            if description is not None:
                updates["description"] = description
            if steps is not None:
                updates["steps"] = steps
            if severity_threshold is not None:
                updates["severity_threshold"] = severity_threshold
            if test_frequency_days is not None:
                updates["test_frequency_days"] = test_frequency_days

            # Bump version
            major, minor = pb.version.split(".")
            updates["version"] = f"{major}.{int(minor) + 1}"

            updated = pb.model_copy(update=updates)
            self._playbooks[playbook_id] = updated
        return updated

    def delete_playbook(self, playbook_id: str) -> None:
        """Delete a playbook.

        Raises ``KeyError`` if not found.
        """
        with self._lock:
            if playbook_id not in self._playbooks:
                raise KeyError(f"Playbook {playbook_id} not found")
            del self._playbooks[playbook_id]
        logger.info("Deleted playbook %s", playbook_id)

    def record_playbook_test(
        self,
        playbook_id: str,
        participants: list[str],
        findings: list[str],
        passed: bool,
    ) -> PlaybookTestResult:
        """Record a playbook tabletop exercise / test.

        Updates the playbook's last_tested date.
        Raises ``KeyError`` if playbook not found.
        """
        with self._lock:
            pb = self._playbooks.get(playbook_id)
            if pb is None:
                raise KeyError(f"Playbook {playbook_id} not found")

            now = datetime.now(timezone.utc)
            next_test = now + timedelta(days=pb.test_frequency_days)

            updated = pb.model_copy(update={"last_tested": now, "updated_at": now})
            self._playbooks[playbook_id] = updated

        return PlaybookTestResult(
            playbook_id=playbook_id,
            tested_at=now,
            participants=participants,
            findings=findings,
            passed=passed,
            next_test_due=next_test,
        )

    def get_playbook_testing_schedule(self) -> list[dict]:
        """Get playbook testing schedule with overdue indicators."""
        now = datetime.now(timezone.utc)
        schedule = []
        for pb in self._playbooks.values():
            if pb.last_tested is not None:
                next_due = pb.last_tested + timedelta(days=pb.test_frequency_days)
                overdue = now > next_due
            else:
                next_due = pb.created_at + timedelta(days=pb.test_frequency_days)
                overdue = True

            schedule.append({
                "playbook_id": pb.id,
                "title": pb.title,
                "last_tested": pb.last_tested.isoformat() if pb.last_tested else None,
                "test_frequency_days": pb.test_frequency_days,
                "next_test_due": next_due.isoformat(),
                "overdue": overdue,
                "days_until_due": max(0, (next_due - now).days) if not overdue else 0,
                "days_overdue": max(0, (now - next_due).days) if overdue else 0,
            })
        schedule.sort(key=lambda x: x["next_test_due"])
        return schedule

    # ------------------------------------------------------------------
    # Incident CRUD
    # ------------------------------------------------------------------

    def create_incident(self, request: IncidentCreateRequest) -> IncidentRecord:
        """Create a new incident record."""
        now = datetime.now(timezone.utc)
        inc_id = f"INC-{now.strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}"

        # Auto-assign playbook based on category
        playbook_id = self._auto_assign_playbook(request.category, request.severity)

        # Auto-determine escalation level
        escalation = self._determine_escalation_level(request.severity)

        # Create initial detection event
        initial_event = IncidentEvent(
            id=f"EVT-{uuid4().hex[:8].upper()}",
            incident_id=inc_id,
            timestamp=now,
            phase=IncidentPhase.DETECTION,
            description=f"Incident detected and reported by {request.reported_by}: {request.title}",
            actor=request.reported_by,
            evidence_refs=[],
        )

        incident = IncidentRecord(
            id=inc_id,
            title=request.title,
            description=request.description,
            severity=request.severity,
            category=request.category,
            phase=IncidentPhase.DETECTION,
            detected_at=now,
            reported_by=request.reported_by,
            assigned_to=None,
            playbook_id=playbook_id,
            events=[initial_event],
            notifications=[],
            affected_systems=request.affected_systems,
            affected_patients_count=request.affected_patients_count,
            data_compromised=request.data_compromised,
            escalation_level=escalation,
            created_at=now,
            updated_at=now,
        )

        with self._lock:
            self._incidents[inc_id] = incident

        logger.info("Created incident %s: %s (severity=%s)", inc_id, request.title, request.severity.value)
        return incident

    def get_incident(self, incident_id: str) -> IncidentRecord:
        """Get a specific incident by ID.

        Raises ``KeyError`` if not found.
        """
        inc = self._incidents.get(incident_id)
        if inc is None:
            raise KeyError(f"Incident {incident_id} not found")
        return inc

    def list_incidents(
        self,
        *,
        severity: IncidentSeverity | None = None,
        category: IncidentCategory | None = None,
        phase: IncidentPhase | None = None,
        active_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[IncidentRecord], int]:
        """List incidents with optional filtering and pagination."""
        records = list(self._incidents.values())

        if severity is not None:
            records = [r for r in records if r.severity == severity]
        if category is not None:
            records = [r for r in records if r.category == category]
        if phase is not None:
            records = [r for r in records if r.phase == phase]
        if active_only:
            records = [r for r in records if r.phase != IncidentPhase.CLOSED]

        records.sort(key=lambda r: r.detected_at, reverse=True)
        total = len(records)
        return records[offset : offset + limit], total

    def update_incident(self, incident_id: str, request: IncidentUpdateRequest) -> IncidentRecord:
        """Update an incident with phase transition validation.

        Raises ``KeyError`` if not found.
        Raises ``ValueError`` for invalid phase transitions.
        """
        with self._lock:
            inc = self._incidents.get(incident_id)
            if inc is None:
                raise KeyError(f"Incident {incident_id} not found")

            # Validate phase transition
            if request.phase is not None and request.phase != inc.phase:
                allowed = VALID_PHASE_TRANSITIONS.get(inc.phase, set())
                if request.phase not in allowed:
                    raise ValueError(
                        f"Invalid phase transition from {inc.phase.value} to "
                        f"{request.phase.value}. Allowed: {[p.value for p in allowed]}"
                    )

            now = datetime.now(timezone.utc)
            updates: dict = {"updated_at": now}

            if request.title is not None:
                updates["title"] = request.title
            if request.description is not None:
                updates["description"] = request.description
            if request.severity is not None:
                updates["severity"] = request.severity
            if request.assigned_to is not None:
                updates["assigned_to"] = request.assigned_to
            if request.playbook_id is not None:
                updates["playbook_id"] = request.playbook_id
            if request.root_cause is not None:
                updates["root_cause"] = request.root_cause
            if request.lessons_learned is not None:
                updates["lessons_learned"] = request.lessons_learned
            if request.affected_systems is not None:
                updates["affected_systems"] = request.affected_systems
            if request.affected_patients_count is not None:
                updates["affected_patients_count"] = request.affected_patients_count
            if request.data_compromised is not None:
                updates["data_compromised"] = request.data_compromised
            if request.escalation_level is not None:
                updates["escalation_level"] = request.escalation_level

            if request.phase is not None and request.phase != inc.phase:
                updates["phase"] = request.phase

                # Calculate containment time when entering CONTAINMENT
                if request.phase == IncidentPhase.CONTAINMENT and inc.containment_time_minutes is None:
                    delta = (now - inc.detected_at).total_seconds() / 60
                    updates["containment_time_minutes"] = round(delta, 2)

                # Calculate resolution time and close when entering CLOSED
                if request.phase == IncidentPhase.CLOSED:
                    delta = (now - inc.detected_at).total_seconds() / 60
                    updates["resolution_time_minutes"] = round(delta, 2)
                    updates["closed_at"] = now

                # Add phase transition event
                event = IncidentEvent(
                    id=f"EVT-{uuid4().hex[:8].upper()}",
                    incident_id=incident_id,
                    timestamp=now,
                    phase=request.phase,
                    description=f"Phase transitioned from {inc.phase.value} to {request.phase.value}",
                    actor=request.assigned_to or inc.assigned_to or "System",
                    evidence_refs=[],
                )
                updates["events"] = inc.events + [event]

            updated = inc.model_copy(update=updates)
            self._incidents[incident_id] = updated

        return updated

    def get_active_incidents(self) -> list[IncidentRecord]:
        """Get all active (non-closed) incidents."""
        return [
            inc for inc in self._incidents.values()
            if inc.phase != IncidentPhase.CLOSED
        ]

    # ------------------------------------------------------------------
    # Event logging (timeline)
    # ------------------------------------------------------------------

    def add_event(self, incident_id: str, request: EventCreateRequest) -> IncidentEvent:
        """Log a timeline event for an incident.

        Raises ``KeyError`` if incident not found.
        """
        with self._lock:
            inc = self._incidents.get(incident_id)
            if inc is None:
                raise KeyError(f"Incident {incident_id} not found")

            now = datetime.now(timezone.utc)
            event = IncidentEvent(
                id=f"EVT-{uuid4().hex[:8].upper()}",
                incident_id=incident_id,
                timestamp=now,
                phase=inc.phase,
                description=request.description,
                actor=request.actor,
                evidence_refs=request.evidence_refs,
            )

            updated = inc.model_copy(update={
                "events": inc.events + [event],
                "updated_at": now,
            })
            self._incidents[incident_id] = updated

        return event

    def get_incident_timeline(self, incident_id: str) -> list[IncidentEvent]:
        """Get the full event timeline for an incident.

        Raises ``KeyError`` if not found.
        """
        inc = self._incidents.get(incident_id)
        if inc is None:
            raise KeyError(f"Incident {incident_id} not found")
        return sorted(inc.events, key=lambda e: e.timestamp)

    # ------------------------------------------------------------------
    # Regulatory notifications
    # ------------------------------------------------------------------

    def create_notification(
        self, incident_id: str, request: NotificationCreateRequest
    ) -> RegulatoryNotification:
        """Create a regulatory notification for an incident.

        Automatically calculates deadline based on notification type.
        Raises ``KeyError`` if incident not found.
        """
        with self._lock:
            inc = self._incidents.get(incident_id)
            if inc is None:
                raise KeyError(f"Incident {incident_id} not found")

            now = datetime.now(timezone.utc)
            deadline_hours = NOTIFICATION_DEADLINES.get(request.notification_type.value, 72)
            deadline = inc.detected_at + timedelta(hours=deadline_hours)

            # Check if already overdue
            status = NotificationStatus.OVERDUE if now > deadline else NotificationStatus.PENDING

            notif = RegulatoryNotification(
                id=f"NOTIF-{uuid4().hex[:8].upper()}",
                incident_id=incident_id,
                notification_type=request.notification_type,
                deadline=deadline,
                sent_at=None,
                recipient=request.recipient,
                status=status,
                content_summary=request.content_summary,
            )

            updated = inc.model_copy(update={
                "notifications": inc.notifications + [notif],
                "updated_at": now,
            })
            self._incidents[incident_id] = updated

        return notif

    def send_notification(self, incident_id: str, notification_id: str) -> RegulatoryNotification:
        """Mark a notification as sent.

        Raises ``KeyError`` if incident or notification not found.
        """
        with self._lock:
            inc = self._incidents.get(incident_id)
            if inc is None:
                raise KeyError(f"Incident {incident_id} not found")

            now = datetime.now(timezone.utc)
            updated_notifs = []
            found = False
            result = None

            for notif in inc.notifications:
                if notif.id == notification_id:
                    found = True
                    updated_notif = notif.model_copy(update={
                        "sent_at": now,
                        "status": NotificationStatus.SENT,
                    })
                    updated_notifs.append(updated_notif)
                    result = updated_notif
                else:
                    updated_notifs.append(notif)

            if not found:
                raise KeyError(f"Notification {notification_id} not found in incident {incident_id}")

            updated = inc.model_copy(update={"notifications": updated_notifs, "updated_at": now})
            self._incidents[incident_id] = updated

        return result  # type: ignore[return-value]

    def get_overdue_notifications(self) -> list[RegulatoryNotification]:
        """Get all overdue notifications across all incidents."""
        now = datetime.now(timezone.utc)
        overdue = []
        for inc in self._incidents.values():
            for notif in inc.notifications:
                if notif.status == NotificationStatus.PENDING and now > notif.deadline:
                    overdue.append(notif)
                elif notif.status == NotificationStatus.OVERDUE:
                    overdue.append(notif)
        overdue.sort(key=lambda n: n.deadline)
        return overdue

    def get_incident_notifications(self, incident_id: str) -> list[RegulatoryNotification]:
        """Get all notifications for a specific incident.

        Raises ``KeyError`` if not found.
        """
        inc = self._incidents.get(incident_id)
        if inc is None:
            raise KeyError(f"Incident {incident_id} not found")
        return inc.notifications

    # ------------------------------------------------------------------
    # Escalation
    # ------------------------------------------------------------------

    def get_escalation_matrix(self) -> list[EscalationMatrix]:
        """Get the full escalation matrix."""
        return self._escalation_matrix

    def escalate_incident(self, incident_id: str, level: EscalationLevel) -> IncidentRecord:
        """Escalate an incident to a specific level.

        Raises ``KeyError`` if not found.
        """
        with self._lock:
            inc = self._incidents.get(incident_id)
            if inc is None:
                raise KeyError(f"Incident {incident_id} not found")

            now = datetime.now(timezone.utc)
            event = IncidentEvent(
                id=f"EVT-{uuid4().hex[:8].upper()}",
                incident_id=incident_id,
                timestamp=now,
                phase=inc.phase,
                description=f"Incident escalated from {inc.escalation_level.value} to {level.value}",
                actor="Escalation System",
                evidence_refs=[],
            )

            updated = inc.model_copy(update={
                "escalation_level": level,
                "events": inc.events + [event],
                "updated_at": now,
            })
            self._incidents[incident_id] = updated

        logger.info("Escalated incident %s to %s", incident_id, level.value)
        return updated

    def check_sla_breaches(self) -> list[dict]:
        """Check for SLA breaches on active incidents and auto-escalate."""
        now = datetime.now(timezone.utc)
        breaches = []

        for inc in self._incidents.values():
            if inc.phase == IncidentPhase.CLOSED:
                continue

            sla = SLA_TARGETS.get(inc.severity.value, {})
            elapsed_minutes = (now - inc.detected_at).total_seconds() / 60

            breach_info = {
                "incident_id": inc.id,
                "severity": inc.severity.value,
                "current_phase": inc.phase.value,
                "elapsed_minutes": round(elapsed_minutes, 2),
                "breaches": [],
            }

            # Check triage SLA
            if inc.phase == IncidentPhase.DETECTION:
                triage_sla = sla.get("triage_minutes", 60)
                if elapsed_minutes > triage_sla:
                    breach_info["breaches"].append({
                        "sla_type": "triage",
                        "limit_minutes": triage_sla,
                        "exceeded_by_minutes": round(elapsed_minutes - triage_sla, 2),
                    })

            # Check containment SLA
            if inc.phase in (IncidentPhase.DETECTION, IncidentPhase.TRIAGE):
                contain_sla = sla.get("containment_minutes", 240)
                if elapsed_minutes > contain_sla:
                    breach_info["breaches"].append({
                        "sla_type": "containment",
                        "limit_minutes": contain_sla,
                        "exceeded_by_minutes": round(elapsed_minutes - contain_sla, 2),
                    })

            # Check resolution SLA
            resolve_sla = sla.get("resolution_minutes", 1440)
            if elapsed_minutes > resolve_sla:
                breach_info["breaches"].append({
                    "sla_type": "resolution",
                    "limit_minutes": resolve_sla,
                    "exceeded_by_minutes": round(elapsed_minutes - resolve_sla, 2),
                })

            if breach_info["breaches"]:
                breaches.append(breach_info)

        return breaches

    # ------------------------------------------------------------------
    # Post-incident reviews
    # ------------------------------------------------------------------

    def create_review(
        self, incident_id: str, request: PostIncidentReviewRequest
    ) -> PostIncidentReview:
        """Create a post-incident review.

        Raises ``KeyError`` if incident not found.
        Raises ``ValueError`` if incident is not in POST_INCIDENT or CLOSED phase.
        """
        inc = self._incidents.get(incident_id)
        if inc is None:
            raise KeyError(f"Incident {incident_id} not found")

        if inc.phase not in (IncidentPhase.POST_INCIDENT, IncidentPhase.CLOSED):
            raise ValueError(
                f"Cannot create review for incident in {inc.phase.value} phase. "
                f"Must be in POST_INCIDENT or CLOSED phase."
            )

        now = datetime.now(timezone.utc)
        review_id = f"PIR-{uuid4().hex[:6].upper()}"
        review = PostIncidentReview(
            id=review_id,
            incident_id=incident_id,
            review_date=now,
            participants=request.participants,
            findings=request.findings,
            action_items=request.action_items,
            effectiveness_rating=request.effectiveness_rating,
            recurrence_risk=request.recurrence_risk,
        )

        with self._lock:
            self._reviews[review_id] = review
        logger.info("Created post-incident review %s for incident %s", review_id, incident_id)
        return review

    def get_review(self, review_id: str) -> PostIncidentReview:
        """Get a specific post-incident review.

        Raises ``KeyError`` if not found.
        """
        review = self._reviews.get(review_id)
        if review is None:
            raise KeyError(f"Post-incident review {review_id} not found")
        return review

    def list_reviews(
        self,
        *,
        incident_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PostIncidentReview], int]:
        """List post-incident reviews with optional filtering."""
        records = list(self._reviews.values())
        if incident_id is not None:
            records = [r for r in records if r.incident_id == incident_id]
        records.sort(key=lambda r: r.review_date, reverse=True)
        total = len(records)
        return records[offset : offset + limit], total

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> IncidentMetrics:
        """Compute aggregated incident response metrics."""
        incidents = list(self._incidents.values())
        if not incidents:
            return IncidentMetrics(
                total_incidents=0, active_incidents=0, closed_incidents=0,
                by_severity={}, by_category={},
                mttd_minutes=None, mttc_minutes=None, mttr_minutes=None,
                sla_compliance_rate=1.0, overdue_notifications=0,
                playbook_coverage_rate=0.0, reviews_completed=0,
            )

        active = [i for i in incidents if i.phase != IncidentPhase.CLOSED]
        closed = [i for i in incidents if i.phase == IncidentPhase.CLOSED]

        by_severity = dict(Counter(i.severity.value for i in incidents))
        by_category = dict(Counter(i.category.value for i in incidents))

        # MTTD: for seed data we measure from created_at to detected_at (effectively 0)
        # In real world this would be time from actual occurrence to detection
        # We use a simulated MTTD for seed incidents
        mttd_values = []
        for i in incidents:
            # Simulated: detection latency is first event timestamp - detected_at
            if i.events:
                mttd_values.append(0.0)  # auto-detected

        mttd = round(sum(mttd_values) / len(mttd_values), 2) if mttd_values else None

        # MTTC: Mean time to contain
        contained = [i for i in incidents if i.containment_time_minutes is not None]
        mttc = round(
            sum(i.containment_time_minutes for i in contained) / len(contained), 2  # type: ignore[arg-type]
        ) if contained else None

        # MTTR: Mean time to resolve
        resolved = [i for i in incidents if i.resolution_time_minutes is not None]
        mttr = round(
            sum(i.resolution_time_minutes for i in resolved) / len(resolved), 2  # type: ignore[arg-type]
        ) if resolved else None

        # SLA compliance
        sla_breaches = self.check_sla_breaches()
        active_count = len(active)
        breached_count = len(sla_breaches)
        total_checked = active_count + len(closed)
        sla_compliance = round(
            (total_checked - breached_count) / total_checked, 4
        ) if total_checked > 0 else 1.0

        # Overdue notifications
        overdue = self.get_overdue_notifications()

        # Playbook coverage
        with_playbook = sum(1 for i in incidents if i.playbook_id is not None)
        playbook_coverage = round(with_playbook / len(incidents), 4) if incidents else 0.0

        return IncidentMetrics(
            total_incidents=len(incidents),
            active_incidents=len(active),
            closed_incidents=len(closed),
            by_severity=by_severity,
            by_category=by_category,
            mttd_minutes=mttd,
            mttc_minutes=mttc,
            mttr_minutes=mttr,
            sla_compliance_rate=sla_compliance,
            overdue_notifications=len(overdue),
            playbook_coverage_rate=playbook_coverage,
            reviews_completed=len(self._reviews),
        )

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    def _auto_assign_playbook(
        self, category: IncidentCategory, severity: IncidentSeverity
    ) -> str | None:
        """Auto-assign a playbook based on incident category."""
        category_to_playbook: dict[IncidentCategory, str] = {
            IncidentCategory.DATA_BREACH: "PB-DATA-BREACH",
            IncidentCategory.RANSOMWARE: "PB-RANSOMWARE",
            IncidentCategory.INSIDER_THREAT: "PB-INSIDER",
            IncidentCategory.PHISHING: "PB-PHISHING",
            IncidentCategory.DDOS: "PB-DDOS",
            IncidentCategory.SUPPLY_CHAIN: "PB-SUPPLY-CHAIN",
            IncidentCategory.ZERO_DAY: "PB-ZERO-DAY",
            IncidentCategory.UNAUTHORIZED_ACCESS: "PB-UNAUTH-ACCESS",
        }
        pb_id = category_to_playbook.get(category)
        if pb_id and pb_id in self._playbooks:
            return pb_id
        return None

    def _determine_escalation_level(self, severity: IncidentSeverity) -> EscalationLevel:
        """Determine initial escalation level based on severity."""
        severity_to_level: dict[IncidentSeverity, EscalationLevel] = {
            IncidentSeverity.SEV1_CRITICAL: EscalationLevel.L4_EXECUTIVE,
            IncidentSeverity.SEV2_HIGH: EscalationLevel.L3_CISO,
            IncidentSeverity.SEV3_MEDIUM: EscalationLevel.L2_IR_TEAM,
            IncidentSeverity.SEV4_LOW: EscalationLevel.L1_SOC,
        }
        return severity_to_level.get(severity, EscalationLevel.L1_SOC)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Clear all data (for testing)."""
        with self._lock:
            self._playbooks.clear()
            self._incidents.clear()
            self._reviews.clear()
            self._escalation_matrix.clear()

    def get_stats(self) -> dict:
        """Return service stats for health/prewarm."""
        return {
            "total_playbooks": len(self._playbooks),
            "total_incidents": len(self._incidents),
            "active_incidents": len([i for i in self._incidents.values() if i.phase != IncidentPhase.CLOSED]),
            "total_reviews": len(self._reviews),
            "service": "incident_response",
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: IncidentResponseService | None = None
_instance_lock = threading.Lock()


def get_incident_response_service() -> IncidentResponseService:
    """Return the singleton IncidentResponseService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = IncidentResponseService()
    return _instance


def reset_incident_response_service() -> IncidentResponseService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = IncidentResponseService()
    return _instance
