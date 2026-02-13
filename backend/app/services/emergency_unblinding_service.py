"""Emergency Unblinding Service (EMRG-UBL).

Manages emergency unblinding operations: unblinding requests, approval
workflows, unblinding notifications, audit log entries, and unblinding metrics.

Usage:
    from app.services.emergency_unblinding_service import (
        get_emergency_unblinding_service,
    )

    svc = get_emergency_unblinding_service()
    requests = svc.list_requests()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.emergency_unblinding import (
    ApprovalDecision,
    AuditAction,
    EmergencyUnblindingMetrics,
    NotificationChannel,
    RequestStatus,
    UnblindingApproval,
    UnblindingApprovalCreate,
    UnblindingApprovalUpdate,
    UnblindingAuditLog,
    UnblindingAuditLogCreate,
    UnblindingAuditLogUpdate,
    UnblindingNotification,
    UnblindingNotificationCreate,
    UnblindingNotificationUpdate,
    UnblindingReason,
    UnblindingRequest,
    UnblindingRequestCreate,
    UnblindingRequestUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class EmergencyUnblindingService:
    """In-memory Emergency Unblinding engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._requests: dict[str, UnblindingRequest] = {}
        self._approvals: dict[str, UnblindingApproval] = {}
        self._notifications: dict[str, UnblindingNotification] = {}
        self._audit_logs: dict[str, UnblindingAuditLog] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic emergency unblinding data."""
        now = datetime.now(timezone.utc)

        # --- 12 Unblinding Requests ---
        requests_data = [
            {
                "id": "UBR-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "subject_id": "SUBJ-E001",
                "requestor_name": "Dr. Sarah Chen",
                "requestor_role": "Principal Investigator",
                "unblinding_reason": UnblindingReason.MEDICAL_EMERGENCY,
                "request_status": RequestStatus.EXECUTED,
                "clinical_justification": "Patient presented with acute anaphylaxis requiring immediate knowledge of treatment assignment for appropriate management.",
                "is_emergency": True,
                "request_date": now - timedelta(days=90),
                "resolved_date": now - timedelta(days=90),
                "treatment_arm_revealed": "Aflibercept 2mg",
                "impact_on_study": "Subject discontinued from study per protocol.",
                "notes": "Emergency unblinding completed within 15 minutes of request.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "UBR-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "subject_id": "SUBJ-E002",
                "requestor_name": "Dr. Sarah Chen",
                "requestor_role": "Principal Investigator",
                "unblinding_reason": UnblindingReason.SERIOUS_ADVERSE_EVENT,
                "request_status": RequestStatus.APPROVED,
                "clinical_justification": "Grade 4 hepatotoxicity requiring urgent clinical decision on treatment continuation.",
                "is_emergency": True,
                "request_date": now - timedelta(days=75),
                "resolved_date": None,
                "treatment_arm_revealed": None,
                "impact_on_study": None,
                "notes": "Approval granted. Awaiting investigator execution.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "UBR-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-LA-001",
                "subject_id": "SUBJ-E003",
                "requestor_name": "Dr. James Wilson",
                "requestor_role": "Sub-Investigator",
                "unblinding_reason": UnblindingReason.OVERDOSE,
                "request_status": RequestStatus.SUBMITTED,
                "clinical_justification": "Patient accidentally received double dose. Need to confirm active vs placebo for toxicology management.",
                "is_emergency": True,
                "request_date": now - timedelta(days=60),
                "resolved_date": None,
                "treatment_arm_revealed": None,
                "impact_on_study": None,
                "notes": "Urgent review requested.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "UBR-004",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-LA-001",
                "subject_id": "SUBJ-E004",
                "requestor_name": "Dr. James Wilson",
                "requestor_role": "Sub-Investigator",
                "unblinding_reason": UnblindingReason.PREGNANCY,
                "request_status": RequestStatus.DENIED,
                "clinical_justification": "Subject reported positive pregnancy test. Unblinding requested to assess fetal risk.",
                "is_emergency": False,
                "request_date": now - timedelta(days=45),
                "resolved_date": now - timedelta(days=44),
                "treatment_arm_revealed": None,
                "impact_on_study": None,
                "notes": "Denied: Protocol allows pregnancy management without unblinding per DSMB guidance.",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "UBR-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "subject_id": "SUBJ-D001",
                "requestor_name": "Dr. Maria Garcia",
                "requestor_role": "Principal Investigator",
                "unblinding_reason": UnblindingReason.MEDICAL_EMERGENCY,
                "request_status": RequestStatus.EXECUTED,
                "clinical_justification": "Patient admitted to ICU with respiratory failure. Treatment identity needed for ventilator management decisions.",
                "is_emergency": True,
                "request_date": now - timedelta(days=80),
                "resolved_date": now - timedelta(days=80),
                "treatment_arm_revealed": "Dupilumab 300mg",
                "impact_on_study": "Subject withdrawn. Data up to unblinding included in ITT analysis.",
                "notes": "Rapid unblinding per emergency protocol.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "UBR-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "subject_id": "SUBJ-D002",
                "requestor_name": "Dr. Maria Garcia",
                "requestor_role": "Principal Investigator",
                "unblinding_reason": UnblindingReason.SERIOUS_ADVERSE_EVENT,
                "request_status": RequestStatus.UNDER_REVIEW,
                "clinical_justification": "Severe Stevens-Johnson syndrome suspected. Need treatment identity for dermatology consult.",
                "is_emergency": True,
                "request_date": now - timedelta(days=30),
                "resolved_date": None,
                "treatment_arm_revealed": None,
                "impact_on_study": None,
                "notes": "Under medical monitor review.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "UBR-007",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-BOS-001",
                "subject_id": "SUBJ-D003",
                "requestor_name": "Dr. Robert Kim",
                "requestor_role": "Principal Investigator",
                "unblinding_reason": UnblindingReason.REGULATORY_REQUEST,
                "request_status": RequestStatus.APPROVED,
                "clinical_justification": "FDA requested individual treatment assignment as part of safety review for SUSAR.",
                "is_emergency": False,
                "request_date": now - timedelta(days=20),
                "resolved_date": None,
                "treatment_arm_revealed": None,
                "impact_on_study": None,
                "notes": "Regulatory-mandated unblinding. DSMB notified.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "UBR-008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-BOS-001",
                "subject_id": "SUBJ-D004",
                "requestor_name": "Dr. Robert Kim",
                "requestor_role": "Principal Investigator",
                "unblinding_reason": UnblindingReason.INVESTIGATOR_DECISION,
                "request_status": RequestStatus.CANCELLED,
                "clinical_justification": "Investigator initially concerned about drug interaction. Resolved without unblinding.",
                "is_emergency": False,
                "request_date": now - timedelta(days=15),
                "resolved_date": now - timedelta(days=14),
                "treatment_arm_revealed": None,
                "impact_on_study": None,
                "notes": "Request withdrawn by investigator after pharmacy consultation.",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "UBR-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-HOU-001",
                "subject_id": "SUBJ-L001",
                "requestor_name": "Dr. Angela Martinez",
                "requestor_role": "Principal Investigator",
                "unblinding_reason": UnblindingReason.MEDICAL_EMERGENCY,
                "request_status": RequestStatus.EXECUTED,
                "clinical_justification": "Immune-related myocarditis detected. Urgent need to confirm cemiplimab exposure for cardiology management.",
                "is_emergency": True,
                "request_date": now - timedelta(days=70),
                "resolved_date": now - timedelta(days=70),
                "treatment_arm_revealed": "Cemiplimab 350mg",
                "impact_on_study": "Subject permanently discontinued. Cardiac monitoring ongoing.",
                "notes": "Unblinding completed per emergency SOP within 20 minutes.",
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "UBR-010",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-HOU-001",
                "subject_id": "SUBJ-L002",
                "requestor_name": "Dr. Angela Martinez",
                "requestor_role": "Principal Investigator",
                "unblinding_reason": UnblindingReason.SERIOUS_ADVERSE_EVENT,
                "request_status": RequestStatus.SUBMITTED,
                "clinical_justification": "Grade 3 pneumonitis requiring immunosuppressive therapy decision.",
                "is_emergency": True,
                "request_date": now - timedelta(days=10),
                "resolved_date": None,
                "treatment_arm_revealed": None,
                "impact_on_study": None,
                "notes": "Awaiting DSMB review.",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "UBR-011",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-SEA-001",
                "subject_id": "SUBJ-L003",
                "requestor_name": "Dr. David Park",
                "requestor_role": "Sub-Investigator",
                "unblinding_reason": UnblindingReason.PREGNANCY,
                "request_status": RequestStatus.EXECUTED,
                "clinical_justification": "Partner pregnancy reported. Unblinding required for reproductive toxicology assessment.",
                "is_emergency": False,
                "request_date": now - timedelta(days=50),
                "resolved_date": now - timedelta(days=49),
                "treatment_arm_revealed": "Placebo",
                "impact_on_study": "Subject continues in study. No teratogenic risk from placebo.",
                "notes": "Minimal study impact as subject on placebo arm.",
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "UBR-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-SEA-001",
                "subject_id": "SUBJ-L004",
                "requestor_name": "Dr. David Park",
                "requestor_role": "Sub-Investigator",
                "unblinding_reason": UnblindingReason.OVERDOSE,
                "request_status": RequestStatus.UNDER_REVIEW,
                "clinical_justification": "Pharmacy dispensing error resulted in potential overdose. Need to confirm active treatment for toxicology assessment.",
                "is_emergency": True,
                "request_date": now - timedelta(days=5),
                "resolved_date": None,
                "treatment_arm_revealed": None,
                "impact_on_study": None,
                "notes": "Pharmacy error investigation ongoing concurrently.",
                "created_at": now - timedelta(days=5),
            },
        ]

        for r in requests_data:
            self._requests[r["id"]] = UnblindingRequest(**r)

        # --- 12 Unblinding Approvals ---
        approvals_data = [
            {
                "id": "UBA-001",
                "trial_id": EYLEA_TRIAL,
                "request_id": "UBR-001",
                "approver_name": "Dr. William Hayes",
                "approver_role": "Medical Monitor",
                "approval_decision": ApprovalDecision.APPROVED,
                "decision_date": now - timedelta(days=90),
                "conditions": None,
                "rationale": "Life-threatening anaphylaxis. Immediate unblinding justified per emergency protocol.",
                "escalated_to": None,
                "response_time_minutes": 8,
                "notes": "Verbal approval followed by written confirmation within 1 hour.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "UBA-002",
                "trial_id": EYLEA_TRIAL,
                "request_id": "UBR-002",
                "approver_name": "Dr. William Hayes",
                "approver_role": "Medical Monitor",
                "approval_decision": ApprovalDecision.APPROVED,
                "decision_date": now - timedelta(days=75),
                "conditions": "Unblinding limited to treating physician only. Study team remains blinded.",
                "rationale": "Grade 4 hepatotoxicity warrants unblinding for clinical management.",
                "escalated_to": None,
                "response_time_minutes": 25,
                "notes": "Conditional approval with restricted information sharing.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "UBA-003",
                "trial_id": EYLEA_TRIAL,
                "request_id": "UBR-003",
                "approver_name": "Dr. William Hayes",
                "approver_role": "Medical Monitor",
                "approval_decision": ApprovalDecision.DEFERRED,
                "decision_date": now - timedelta(days=59),
                "conditions": None,
                "rationale": "Need additional clinical information before decision. Requested labs and vitals within 4 hours.",
                "escalated_to": None,
                "response_time_minutes": 45,
                "notes": "Decision pending receipt of additional clinical data.",
                "created_at": now - timedelta(days=59),
            },
            {
                "id": "UBA-004",
                "trial_id": EYLEA_TRIAL,
                "request_id": "UBR-004",
                "approver_name": "Dr. Elizabeth Foster",
                "approver_role": "DSMB Chair",
                "approval_decision": ApprovalDecision.DENIED,
                "decision_date": now - timedelta(days=44),
                "conditions": None,
                "rationale": "Protocol-specified pregnancy management does not require unblinding. Standard pregnancy monitoring sufficient.",
                "escalated_to": None,
                "response_time_minutes": 120,
                "notes": "DSMB consensus decision. Pregnancy follow-up plan provided.",
                "created_at": now - timedelta(days=44),
            },
            {
                "id": "UBA-005",
                "trial_id": DUPIXENT_TRIAL,
                "request_id": "UBR-005",
                "approver_name": "Dr. Thomas Wright",
                "approver_role": "Medical Monitor",
                "approval_decision": ApprovalDecision.APPROVED,
                "decision_date": now - timedelta(days=80),
                "conditions": None,
                "rationale": "ICU admission with respiratory failure. Immediate unblinding medically necessary.",
                "escalated_to": None,
                "response_time_minutes": 12,
                "notes": "Emergency approval. Patient in critical condition.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "UBA-006",
                "trial_id": DUPIXENT_TRIAL,
                "request_id": "UBR-006",
                "approver_name": "Dr. Thomas Wright",
                "approver_role": "Medical Monitor",
                "approval_decision": ApprovalDecision.ESCALATED,
                "decision_date": now - timedelta(days=29),
                "conditions": None,
                "rationale": "Case complexity requires DSMB review. Severity warrants expedited DSMB session.",
                "escalated_to": "Dr. Elizabeth Foster, DSMB Chair",
                "response_time_minutes": 60,
                "notes": "Emergency DSMB session scheduled within 24 hours.",
                "created_at": now - timedelta(days=29),
            },
            {
                "id": "UBA-007",
                "trial_id": DUPIXENT_TRIAL,
                "request_id": "UBR-007",
                "approver_name": "Dr. Elizabeth Foster",
                "approver_role": "DSMB Chair",
                "approval_decision": ApprovalDecision.APPROVED,
                "decision_date": now - timedelta(days=19),
                "conditions": "Information to be shared with FDA only. Internal study team remains blinded.",
                "rationale": "Regulatory-mandated disclosure. DSMB approves with controlled information flow.",
                "escalated_to": None,
                "response_time_minutes": 180,
                "notes": "DSMB formal vote: 5-0 in favor.",
                "created_at": now - timedelta(days=19),
            },
            {
                "id": "UBA-008",
                "trial_id": DUPIXENT_TRIAL,
                "request_id": "UBR-008",
                "approver_name": "Dr. Thomas Wright",
                "approver_role": "Medical Monitor",
                "approval_decision": ApprovalDecision.DENIED,
                "decision_date": now - timedelta(days=14),
                "conditions": None,
                "rationale": "Request withdrawn by investigator. No clinical need for unblinding confirmed.",
                "escalated_to": None,
                "response_time_minutes": 30,
                "notes": "Investigator concurred with decision to maintain blinding.",
                "created_at": now - timedelta(days=14),
            },
            {
                "id": "UBA-009",
                "trial_id": LIBTAYO_TRIAL,
                "request_id": "UBR-009",
                "approver_name": "Dr. Patricia Lee",
                "approver_role": "Medical Monitor",
                "approval_decision": ApprovalDecision.APPROVED,
                "decision_date": now - timedelta(days=70),
                "conditions": None,
                "rationale": "Immune-related myocarditis is life-threatening. Immediate unblinding essential for cardiac management.",
                "escalated_to": None,
                "response_time_minutes": 10,
                "notes": "Fastest approval in program history due to severity.",
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "UBA-010",
                "trial_id": LIBTAYO_TRIAL,
                "request_id": "UBR-010",
                "approver_name": "Dr. Patricia Lee",
                "approver_role": "Medical Monitor",
                "approval_decision": ApprovalDecision.CONDITIONAL,
                "decision_date": now - timedelta(days=9),
                "conditions": "Approval contingent on HRCT scan results confirming pneumonitis diagnosis.",
                "rationale": "Clinical presentation suggestive but not confirmed. Conditional approval pending diagnostic confirmation.",
                "escalated_to": None,
                "response_time_minutes": 90,
                "notes": "Awaiting radiology report.",
                "created_at": now - timedelta(days=9),
            },
            {
                "id": "UBA-011",
                "trial_id": LIBTAYO_TRIAL,
                "request_id": "UBR-011",
                "approver_name": "Dr. Patricia Lee",
                "approver_role": "Medical Monitor",
                "approval_decision": ApprovalDecision.APPROVED,
                "decision_date": now - timedelta(days=49),
                "conditions": None,
                "rationale": "Partner pregnancy with potential teratogenic exposure warrants unblinding per regulatory guidance.",
                "escalated_to": None,
                "response_time_minutes": 45,
                "notes": "Standard approval process.",
                "created_at": now - timedelta(days=49),
            },
            {
                "id": "UBA-012",
                "trial_id": LIBTAYO_TRIAL,
                "request_id": "UBR-012",
                "approver_name": "Dr. Patricia Lee",
                "approver_role": "Medical Monitor",
                "approval_decision": ApprovalDecision.ESCALATED,
                "decision_date": now - timedelta(days=4),
                "conditions": None,
                "rationale": "Pharmacy dispensing error requires both unblinding decision and root cause analysis. Escalating to DSMB.",
                "escalated_to": "DSMB Emergency Sub-Committee",
                "response_time_minutes": 55,
                "notes": "DSMB emergency session requested.",
                "created_at": now - timedelta(days=4),
            },
        ]

        for a in approvals_data:
            self._approvals[a["id"]] = UnblindingApproval(**a)

        # --- 12 Unblinding Notifications ---
        notifications_data = [
            {
                "id": "UBN-001",
                "trial_id": EYLEA_TRIAL,
                "request_id": "UBR-001",
                "recipient_name": "Dr. Sarah Chen",
                "recipient_role": "Principal Investigator",
                "notification_channel": NotificationChannel.PHONE,
                "sent_date": now - timedelta(days=90),
                "acknowledged": True,
                "acknowledged_date": now - timedelta(days=90),
                "content_summary": "Treatment assignment revealed: Aflibercept 2mg. Subject SUBJ-E001.",
                "delivery_confirmed": True,
                "retry_count": 0,
                "notes": "Verbal confirmation received immediately.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "UBN-002",
                "trial_id": EYLEA_TRIAL,
                "request_id": "UBR-001",
                "recipient_name": "Sponsor Safety Team",
                "recipient_role": "Sponsor Medical Affairs",
                "notification_channel": NotificationChannel.EMAIL,
                "sent_date": now - timedelta(days=90),
                "acknowledged": True,
                "acknowledged_date": now - timedelta(days=89),
                "content_summary": "Emergency unblinding notification for SUBJ-E001. SAE report to follow.",
                "delivery_confirmed": True,
                "retry_count": 0,
                "notes": "Email receipt confirmed by sponsor safety team.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "UBN-003",
                "trial_id": EYLEA_TRIAL,
                "request_id": "UBR-002",
                "recipient_name": "Dr. Sarah Chen",
                "recipient_role": "Principal Investigator",
                "notification_channel": NotificationChannel.SYSTEM_ALERT,
                "sent_date": now - timedelta(days=75),
                "acknowledged": True,
                "acknowledged_date": now - timedelta(days=75),
                "content_summary": "Unblinding request UBR-002 approved with conditions. See approval details.",
                "delivery_confirmed": True,
                "retry_count": 0,
                "notes": "System alert acknowledged via portal.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "UBN-004",
                "trial_id": EYLEA_TRIAL,
                "request_id": "UBR-004",
                "recipient_name": "Dr. James Wilson",
                "recipient_role": "Sub-Investigator",
                "notification_channel": NotificationChannel.EMAIL,
                "sent_date": now - timedelta(days=44),
                "acknowledged": False,
                "acknowledged_date": None,
                "content_summary": "Unblinding request UBR-004 denied. See rationale in system.",
                "delivery_confirmed": True,
                "retry_count": 1,
                "notes": "Follow-up email sent after no acknowledgment.",
                "created_at": now - timedelta(days=44),
            },
            {
                "id": "UBN-005",
                "trial_id": DUPIXENT_TRIAL,
                "request_id": "UBR-005",
                "recipient_name": "Dr. Maria Garcia",
                "recipient_role": "Principal Investigator",
                "notification_channel": NotificationChannel.PHONE,
                "sent_date": now - timedelta(days=80),
                "acknowledged": True,
                "acknowledged_date": now - timedelta(days=80),
                "content_summary": "Treatment assignment revealed: Dupilumab 300mg. Subject SUBJ-D001.",
                "delivery_confirmed": True,
                "retry_count": 0,
                "notes": "Immediate phone notification to ICU team.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "UBN-006",
                "trial_id": DUPIXENT_TRIAL,
                "request_id": "UBR-005",
                "recipient_name": "IRB Office",
                "recipient_role": "Ethics Committee",
                "notification_channel": NotificationChannel.FAX,
                "sent_date": now - timedelta(days=79),
                "acknowledged": True,
                "acknowledged_date": now - timedelta(days=78),
                "content_summary": "Emergency unblinding report for SUBJ-D001. IRB notification per protocol.",
                "delivery_confirmed": True,
                "retry_count": 0,
                "notes": "Fax confirmation page received.",
                "created_at": now - timedelta(days=79),
            },
            {
                "id": "UBN-007",
                "trial_id": DUPIXENT_TRIAL,
                "request_id": "UBR-006",
                "recipient_name": "Dr. Maria Garcia",
                "recipient_role": "Principal Investigator",
                "notification_channel": NotificationChannel.SMS,
                "sent_date": now - timedelta(days=29),
                "acknowledged": True,
                "acknowledged_date": now - timedelta(days=29),
                "content_summary": "Unblinding request UBR-006 escalated to DSMB. Await further instructions.",
                "delivery_confirmed": True,
                "retry_count": 0,
                "notes": "SMS delivery confirmed.",
                "created_at": now - timedelta(days=29),
            },
            {
                "id": "UBN-008",
                "trial_id": DUPIXENT_TRIAL,
                "request_id": "UBR-007",
                "recipient_name": "FDA Safety Reviewer",
                "recipient_role": "Regulatory Authority",
                "notification_channel": NotificationChannel.EMAIL,
                "sent_date": now - timedelta(days=19),
                "acknowledged": False,
                "acknowledged_date": None,
                "content_summary": "SUSAR unblinding completed per regulatory request. Full report attached.",
                "delivery_confirmed": True,
                "retry_count": 2,
                "notes": "Awaiting FDA acknowledgment. Second follow-up sent.",
                "created_at": now - timedelta(days=19),
            },
            {
                "id": "UBN-009",
                "trial_id": LIBTAYO_TRIAL,
                "request_id": "UBR-009",
                "recipient_name": "Dr. Angela Martinez",
                "recipient_role": "Principal Investigator",
                "notification_channel": NotificationChannel.PHONE,
                "sent_date": now - timedelta(days=70),
                "acknowledged": True,
                "acknowledged_date": now - timedelta(days=70),
                "content_summary": "Treatment assignment revealed: Cemiplimab 350mg. Subject SUBJ-L001.",
                "delivery_confirmed": True,
                "retry_count": 0,
                "notes": "Cardiology team notified simultaneously.",
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "UBN-010",
                "trial_id": LIBTAYO_TRIAL,
                "request_id": "UBR-009",
                "recipient_name": "Sponsor Pharmacovigilance",
                "recipient_role": "Sponsor Safety",
                "notification_channel": NotificationChannel.SYSTEM_ALERT,
                "sent_date": now - timedelta(days=70),
                "acknowledged": True,
                "acknowledged_date": now - timedelta(days=70),
                "content_summary": "Emergency unblinding for SUBJ-L001. Immune-related myocarditis. SUSAR reporting initiated.",
                "delivery_confirmed": True,
                "retry_count": 0,
                "notes": "Automatic system notification to PV team.",
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "UBN-011",
                "trial_id": LIBTAYO_TRIAL,
                "request_id": "UBR-011",
                "recipient_name": "Dr. David Park",
                "recipient_role": "Sub-Investigator",
                "notification_channel": NotificationChannel.IN_PERSON,
                "sent_date": now - timedelta(days=49),
                "acknowledged": True,
                "acknowledged_date": now - timedelta(days=49),
                "content_summary": "Treatment assignment revealed: Placebo. Subject SUBJ-L003. No teratogenic risk.",
                "delivery_confirmed": True,
                "retry_count": 0,
                "notes": "In-person notification during site visit.",
                "created_at": now - timedelta(days=49),
            },
            {
                "id": "UBN-012",
                "trial_id": LIBTAYO_TRIAL,
                "request_id": "UBR-012",
                "recipient_name": "Pharmacy Director",
                "recipient_role": "Site Pharmacist",
                "notification_channel": NotificationChannel.EMAIL,
                "sent_date": now - timedelta(days=4),
                "acknowledged": False,
                "acknowledged_date": None,
                "content_summary": "Unblinding request UBR-012 escalated. Pharmacy error investigation required.",
                "delivery_confirmed": False,
                "retry_count": 3,
                "notes": "Multiple delivery attempts. Alternative contact being sought.",
                "created_at": now - timedelta(days=4),
            },
        ]

        for n in notifications_data:
            self._notifications[n["id"]] = UnblindingNotification(**n)

        # --- 12 Unblinding Audit Logs ---
        audit_data = [
            {
                "id": "UBL-001",
                "trial_id": EYLEA_TRIAL,
                "request_id": "UBR-001",
                "audit_action": AuditAction.REQUEST_CREATED,
                "action_date": now - timedelta(days=90),
                "performed_by": "Dr. Sarah Chen",
                "ip_address": "10.0.1.15",
                "details": "Emergency unblinding request created for SUBJ-E001 due to anaphylaxis.",
                "document_reference": "DOC-UBL-2025-001",
                "regulatory_reported": True,
                "report_date": now - timedelta(days=89),
                "notes": "IND safety report filed.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "UBL-002",
                "trial_id": EYLEA_TRIAL,
                "request_id": "UBR-001",
                "audit_action": AuditAction.APPROVAL_GRANTED,
                "action_date": now - timedelta(days=90),
                "performed_by": "Dr. William Hayes",
                "ip_address": "10.0.1.20",
                "details": "Emergency unblinding approved for SUBJ-E001. Response time: 8 minutes.",
                "document_reference": "DOC-UBL-2025-001",
                "regulatory_reported": True,
                "report_date": now - timedelta(days=89),
                "notes": None,
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "UBL-003",
                "trial_id": EYLEA_TRIAL,
                "request_id": "UBR-001",
                "audit_action": AuditAction.TREATMENT_REVEALED,
                "action_date": now - timedelta(days=90),
                "performed_by": "System - IVRS",
                "ip_address": "10.0.2.100",
                "details": "Treatment assignment Aflibercept 2mg revealed for SUBJ-E001 via IVRS.",
                "document_reference": "DOC-UBL-2025-001",
                "regulatory_reported": True,
                "report_date": now - timedelta(days=89),
                "notes": "IVRS automated revelation with audit trail.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "UBL-004",
                "trial_id": EYLEA_TRIAL,
                "request_id": "UBR-004",
                "audit_action": AuditAction.APPROVAL_DENIED,
                "action_date": now - timedelta(days=44),
                "performed_by": "Dr. Elizabeth Foster",
                "ip_address": "10.0.3.50",
                "details": "Unblinding denied for SUBJ-E004. Pregnancy management per protocol does not require unblinding.",
                "document_reference": "DOC-UBL-2025-004",
                "regulatory_reported": False,
                "report_date": None,
                "notes": "DSMB guidance document referenced.",
                "created_at": now - timedelta(days=44),
            },
            {
                "id": "UBL-005",
                "trial_id": DUPIXENT_TRIAL,
                "request_id": "UBR-005",
                "audit_action": AuditAction.REQUEST_CREATED,
                "action_date": now - timedelta(days=80),
                "performed_by": "Dr. Maria Garcia",
                "ip_address": "10.0.4.10",
                "details": "Emergency unblinding request for SUBJ-D001. ICU admission with respiratory failure.",
                "document_reference": "DOC-UBL-2025-005",
                "regulatory_reported": True,
                "report_date": now - timedelta(days=79),
                "notes": "Expedited regulatory reporting.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "UBL-006",
                "trial_id": DUPIXENT_TRIAL,
                "request_id": "UBR-005",
                "audit_action": AuditAction.TREATMENT_REVEALED,
                "action_date": now - timedelta(days=80),
                "performed_by": "System - IWRS",
                "ip_address": "10.0.2.101",
                "details": "Treatment assignment Dupilumab 300mg revealed for SUBJ-D001 via IWRS.",
                "document_reference": "DOC-UBL-2025-005",
                "regulatory_reported": True,
                "report_date": now - timedelta(days=79),
                "notes": None,
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "UBL-007",
                "trial_id": DUPIXENT_TRIAL,
                "request_id": "UBR-005",
                "audit_action": AuditAction.NOTIFICATION_SENT,
                "action_date": now - timedelta(days=80),
                "performed_by": "Clinical Ops Coordinator",
                "ip_address": "10.0.4.15",
                "details": "Notifications sent to PI, sponsor safety team, and IRB for SUBJ-D001 unblinding.",
                "document_reference": "DOC-UBL-2025-005",
                "regulatory_reported": False,
                "report_date": None,
                "notes": "All required parties notified per SOP.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "UBL-008",
                "trial_id": DUPIXENT_TRIAL,
                "request_id": "UBR-005",
                "audit_action": AuditAction.DOCUMENTATION_FILED,
                "action_date": now - timedelta(days=78),
                "performed_by": "Regulatory Affairs Specialist",
                "ip_address": "10.0.4.20",
                "details": "Complete unblinding documentation package filed for SUBJ-D001 including SAE report, unblinding form, and notification log.",
                "document_reference": "DOC-UBL-2025-005-COMPLETE",
                "regulatory_reported": True,
                "report_date": now - timedelta(days=78),
                "notes": "Full documentation package archived in eTMF.",
                "created_at": now - timedelta(days=78),
            },
            {
                "id": "UBL-009",
                "trial_id": LIBTAYO_TRIAL,
                "request_id": "UBR-009",
                "audit_action": AuditAction.REQUEST_CREATED,
                "action_date": now - timedelta(days=70),
                "performed_by": "Dr. Angela Martinez",
                "ip_address": "10.0.5.10",
                "details": "Emergency unblinding request for SUBJ-L001. Immune-related myocarditis.",
                "document_reference": "DOC-UBL-2025-009",
                "regulatory_reported": True,
                "report_date": now - timedelta(days=69),
                "notes": "SUSAR reporting initiated simultaneously.",
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "UBL-010",
                "trial_id": LIBTAYO_TRIAL,
                "request_id": "UBR-009",
                "audit_action": AuditAction.TREATMENT_REVEALED,
                "action_date": now - timedelta(days=70),
                "performed_by": "System - IVRS",
                "ip_address": "10.0.2.102",
                "details": "Treatment assignment Cemiplimab 350mg revealed for SUBJ-L001 via IVRS.",
                "document_reference": "DOC-UBL-2025-009",
                "regulatory_reported": True,
                "report_date": now - timedelta(days=69),
                "notes": None,
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "UBL-011",
                "trial_id": LIBTAYO_TRIAL,
                "request_id": "UBR-011",
                "audit_action": AuditAction.APPROVAL_GRANTED,
                "action_date": now - timedelta(days=49),
                "performed_by": "Dr. Patricia Lee",
                "ip_address": "10.0.5.15",
                "details": "Unblinding approved for SUBJ-L003. Partner pregnancy warranting treatment identification.",
                "document_reference": "DOC-UBL-2025-011",
                "regulatory_reported": False,
                "report_date": None,
                "notes": "Placebo arm - minimal regulatory reporting impact.",
                "created_at": now - timedelta(days=49),
            },
            {
                "id": "UBL-012",
                "trial_id": LIBTAYO_TRIAL,
                "request_id": "UBR-012",
                "audit_action": AuditAction.REQUEST_CREATED,
                "action_date": now - timedelta(days=5),
                "performed_by": "Dr. David Park",
                "ip_address": "10.0.6.10",
                "details": "Unblinding request for SUBJ-L004 due to pharmacy dispensing error and potential overdose.",
                "document_reference": None,
                "regulatory_reported": False,
                "report_date": None,
                "notes": "Pending DSMB review.",
                "created_at": now - timedelta(days=5),
            },
        ]

        for al in audit_data:
            self._audit_logs[al["id"]] = UnblindingAuditLog(**al)

    # ------------------------------------------------------------------
    # Unblinding Requests
    # ------------------------------------------------------------------

    def list_requests(
        self,
        *,
        trial_id: str | None = None,
        unblinding_reason: UnblindingReason | None = None,
        request_status: RequestStatus | None = None,
    ) -> list[UnblindingRequest]:
        """List unblinding requests with optional filters."""
        with self._lock:
            result = list(self._requests.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if unblinding_reason is not None:
            result = [r for r in result if r.unblinding_reason == unblinding_reason]
        if request_status is not None:
            result = [r for r in result if r.request_status == request_status]

        return sorted(result, key=lambda r: r.request_date, reverse=True)

    def get_request(self, request_id: str) -> UnblindingRequest | None:
        """Get a single unblinding request by ID."""
        with self._lock:
            return self._requests.get(request_id)

    def create_request(self, payload: UnblindingRequestCreate) -> UnblindingRequest:
        """Create a new unblinding request."""
        now = datetime.now(timezone.utc)
        record_id = f"UBR-{uuid4().hex[:8].upper()}"
        record = UnblindingRequest(
            id=record_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            subject_id=payload.subject_id,
            requestor_name=payload.requestor_name,
            requestor_role=payload.requestor_role,
            unblinding_reason=payload.unblinding_reason,
            request_status=RequestStatus.SUBMITTED,
            clinical_justification=payload.clinical_justification,
            is_emergency=payload.is_emergency,
            request_date=now,
            resolved_date=None,
            treatment_arm_revealed=None,
            impact_on_study=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._requests[record_id] = record
        logger.info("Created unblinding request %s for trial %s", record_id, payload.trial_id)
        return record

    def update_request(
        self, request_id: str, payload: UnblindingRequestUpdate
    ) -> UnblindingRequest | None:
        """Update an existing unblinding request."""
        with self._lock:
            existing = self._requests.get(request_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = UnblindingRequest(**data)
            self._requests[request_id] = updated
        return updated

    def delete_request(self, request_id: str) -> bool:
        """Delete an unblinding request. Returns True if deleted."""
        with self._lock:
            if request_id in self._requests:
                del self._requests[request_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Unblinding Approvals
    # ------------------------------------------------------------------

    def list_approvals(
        self,
        *,
        trial_id: str | None = None,
        approval_decision: ApprovalDecision | None = None,
        request_id: str | None = None,
    ) -> list[UnblindingApproval]:
        """List unblinding approvals with optional filters."""
        with self._lock:
            result = list(self._approvals.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if approval_decision is not None:
            result = [a for a in result if a.approval_decision == approval_decision]
        if request_id is not None:
            result = [a for a in result if a.request_id == request_id]

        return sorted(result, key=lambda a: a.decision_date, reverse=True)

    def get_approval(self, approval_id: str) -> UnblindingApproval | None:
        """Get a single unblinding approval by ID."""
        with self._lock:
            return self._approvals.get(approval_id)

    def create_approval(self, payload: UnblindingApprovalCreate) -> UnblindingApproval:
        """Create a new unblinding approval."""
        now = datetime.now(timezone.utc)
        record_id = f"UBA-{uuid4().hex[:8].upper()}"
        record = UnblindingApproval(
            id=record_id,
            trial_id=payload.trial_id,
            request_id=payload.request_id,
            approver_name=payload.approver_name,
            approver_role=payload.approver_role,
            approval_decision=payload.approval_decision,
            decision_date=now,
            conditions=None,
            rationale=payload.rationale,
            escalated_to=None,
            response_time_minutes=payload.response_time_minutes,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._approvals[record_id] = record
        logger.info("Created unblinding approval %s for request %s", record_id, payload.request_id)
        return record

    def update_approval(
        self, approval_id: str, payload: UnblindingApprovalUpdate
    ) -> UnblindingApproval | None:
        """Update an existing unblinding approval."""
        with self._lock:
            existing = self._approvals.get(approval_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = UnblindingApproval(**data)
            self._approvals[approval_id] = updated
        return updated

    def delete_approval(self, approval_id: str) -> bool:
        """Delete an unblinding approval. Returns True if deleted."""
        with self._lock:
            if approval_id in self._approvals:
                del self._approvals[approval_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Unblinding Notifications
    # ------------------------------------------------------------------

    def list_notifications(
        self,
        *,
        trial_id: str | None = None,
        notification_channel: NotificationChannel | None = None,
        acknowledged: bool | None = None,
    ) -> list[UnblindingNotification]:
        """List unblinding notifications with optional filters."""
        with self._lock:
            result = list(self._notifications.values())

        if trial_id is not None:
            result = [n for n in result if n.trial_id == trial_id]
        if notification_channel is not None:
            result = [n for n in result if n.notification_channel == notification_channel]
        if acknowledged is not None:
            result = [n for n in result if n.acknowledged == acknowledged]

        return sorted(result, key=lambda n: n.sent_date, reverse=True)

    def get_notification(self, notification_id: str) -> UnblindingNotification | None:
        """Get a single unblinding notification by ID."""
        with self._lock:
            return self._notifications.get(notification_id)

    def create_notification(self, payload: UnblindingNotificationCreate) -> UnblindingNotification:
        """Create a new unblinding notification."""
        now = datetime.now(timezone.utc)
        record_id = f"UBN-{uuid4().hex[:8].upper()}"
        record = UnblindingNotification(
            id=record_id,
            trial_id=payload.trial_id,
            request_id=payload.request_id,
            recipient_name=payload.recipient_name,
            recipient_role=payload.recipient_role,
            notification_channel=payload.notification_channel,
            sent_date=now,
            acknowledged=False,
            acknowledged_date=None,
            content_summary=payload.content_summary,
            delivery_confirmed=False,
            retry_count=0,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._notifications[record_id] = record
        logger.info("Created unblinding notification %s for request %s", record_id, payload.request_id)
        return record

    def update_notification(
        self, notification_id: str, payload: UnblindingNotificationUpdate
    ) -> UnblindingNotification | None:
        """Update an existing unblinding notification."""
        with self._lock:
            existing = self._notifications.get(notification_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = UnblindingNotification(**data)
            self._notifications[notification_id] = updated
        return updated

    def delete_notification(self, notification_id: str) -> bool:
        """Delete an unblinding notification. Returns True if deleted."""
        with self._lock:
            if notification_id in self._notifications:
                del self._notifications[notification_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Unblinding Audit Logs
    # ------------------------------------------------------------------

    def list_audit_logs(
        self,
        *,
        trial_id: str | None = None,
        audit_action: AuditAction | None = None,
        request_id: str | None = None,
    ) -> list[UnblindingAuditLog]:
        """List unblinding audit logs with optional filters."""
        with self._lock:
            result = list(self._audit_logs.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if audit_action is not None:
            result = [a for a in result if a.audit_action == audit_action]
        if request_id is not None:
            result = [a for a in result if a.request_id == request_id]

        return sorted(result, key=lambda a: a.action_date, reverse=True)

    def get_audit_log(self, log_id: str) -> UnblindingAuditLog | None:
        """Get a single unblinding audit log by ID."""
        with self._lock:
            return self._audit_logs.get(log_id)

    def create_audit_log(self, payload: UnblindingAuditLogCreate) -> UnblindingAuditLog:
        """Create a new unblinding audit log."""
        now = datetime.now(timezone.utc)
        record_id = f"UBL-{uuid4().hex[:8].upper()}"
        record = UnblindingAuditLog(
            id=record_id,
            trial_id=payload.trial_id,
            request_id=payload.request_id,
            audit_action=payload.audit_action,
            action_date=now,
            performed_by=payload.performed_by,
            ip_address=None,
            details=payload.details,
            document_reference=payload.document_reference,
            regulatory_reported=False,
            report_date=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._audit_logs[record_id] = record
        logger.info("Created unblinding audit log %s for request %s", record_id, payload.request_id)
        return record

    def update_audit_log(
        self, log_id: str, payload: UnblindingAuditLogUpdate
    ) -> UnblindingAuditLog | None:
        """Update an existing unblinding audit log."""
        with self._lock:
            existing = self._audit_logs.get(log_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = UnblindingAuditLog(**data)
            self._audit_logs[log_id] = updated
        return updated

    def delete_audit_log(self, log_id: str) -> bool:
        """Delete an unblinding audit log. Returns True if deleted."""
        with self._lock:
            if log_id in self._audit_logs:
                del self._audit_logs[log_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> EmergencyUnblindingMetrics:
        """Compute aggregated emergency unblinding metrics."""
        with self._lock:
            requests = list(self._requests.values())
            approvals = list(self._approvals.values())
            notifications = list(self._notifications.values())
            audit_logs = list(self._audit_logs.values())

        # Apply trial_id filter if provided
        if trial_id is not None:
            requests = [r for r in requests if r.trial_id == trial_id]
            approvals = [a for a in approvals if a.trial_id == trial_id]
            notifications = [n for n in notifications if n.trial_id == trial_id]
            audit_logs = [al for al in audit_logs if al.trial_id == trial_id]

        # Requests by reason
        requests_by_reason: dict[str, int] = {}
        for r in requests:
            key = r.unblinding_reason.value
            requests_by_reason[key] = requests_by_reason.get(key, 0) + 1

        # Requests by status
        requests_by_status: dict[str, int] = {}
        for r in requests:
            key = r.request_status.value
            requests_by_status[key] = requests_by_status.get(key, 0) + 1

        # Emergency request rate
        emergency_count = sum(1 for r in requests if r.is_emergency)
        emergency_request_rate = round(
            (emergency_count / max(1, len(requests))) * 100, 1
        )

        # Approvals by decision
        approvals_by_decision: dict[str, int] = {}
        for a in approvals:
            key = a.approval_decision.value
            approvals_by_decision[key] = approvals_by_decision.get(key, 0) + 1

        # Average response time
        response_times = [a.response_time_minutes for a in approvals]
        avg_response_time = round(
            sum(response_times) / max(1, len(response_times)), 1
        )

        # Notification acknowledgment rate
        acknowledged_count = sum(1 for n in notifications if n.acknowledged)
        notification_ack_rate = round(
            (acknowledged_count / max(1, len(notifications))) * 100, 1
        )

        # Audit actions by type
        audit_actions_by_type: dict[str, int] = {}
        for al in audit_logs:
            key = al.audit_action.value
            audit_actions_by_type[key] = audit_actions_by_type.get(key, 0) + 1

        # Regulatory reporting rate
        reported_count = sum(1 for al in audit_logs if al.regulatory_reported)
        regulatory_reporting_rate = round(
            (reported_count / max(1, len(audit_logs))) * 100, 1
        )

        return EmergencyUnblindingMetrics(
            total_requests=len(requests),
            requests_by_reason=requests_by_reason,
            requests_by_status=requests_by_status,
            emergency_request_rate=emergency_request_rate,
            total_approvals=len(approvals),
            approvals_by_decision=approvals_by_decision,
            avg_response_time_minutes=avg_response_time,
            total_notifications=len(notifications),
            notification_acknowledgment_rate=notification_ack_rate,
            total_audit_entries=len(audit_logs),
            audit_actions_by_type=audit_actions_by_type,
            regulatory_reporting_rate=regulatory_reporting_rate,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: EmergencyUnblindingService | None = None
_instance_lock = threading.Lock()


def get_emergency_unblinding_service() -> EmergencyUnblindingService:
    """Return the singleton EmergencyUnblindingService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = EmergencyUnblindingService()
    return _instance


def reset_emergency_unblinding_service() -> EmergencyUnblindingService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = EmergencyUnblindingService()
    return _instance
