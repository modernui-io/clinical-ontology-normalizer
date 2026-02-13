"""Site Communication Service (SCM-MGT).

Manages site communication operations: communication logs, newsletter
distributions, site query threads, site broadcast alerts, and communication
metrics.

Usage:
    from app.services.site_communication_service import (
        get_site_communication_service,
    )

    svc = get_site_communication_service()
    logs = svc.list_communication_logs()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.site_communication import (
    AlertLevel,
    CommunicationChannel,
    CommunicationLog,
    CommunicationLogCreate,
    CommunicationLogUpdate,
    CommunicationPriority,
    DistributionStatus,
    NewsletterDistribution,
    NewsletterDistributionCreate,
    NewsletterDistributionUpdate,
    QueryStatus,
    SiteBroadcastAlert,
    SiteBroadcastAlertCreate,
    SiteBroadcastAlertUpdate,
    SiteCommunicationMetrics,
    SiteQueryThread,
    SiteQueryThreadCreate,
    SiteQueryThreadUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class SiteCommunicationService:
    """In-memory Site Communication engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._communication_logs: dict[str, CommunicationLog] = {}
        self._newsletter_distributions: dict[str, NewsletterDistribution] = {}
        self._site_query_threads: dict[str, SiteQueryThread] = {}
        self._site_broadcast_alerts: dict[str, SiteBroadcastAlert] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic site communication data."""
        now = datetime.now(timezone.utc)

        # --- 12 Communication Logs ---
        logs_data = [
            {
                "id": "CML-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "communication_channel": CommunicationChannel.EMAIL,
                "communication_priority": CommunicationPriority.NORMAL,
                "subject": "Protocol Amendment 3 Distribution",
                "summary": "Distributed Protocol Amendment 3 to site PI and study coordinator. Acknowledgment requested within 5 business days.",
                "direction": "outbound",
                "initiated_by": "Clinical Operations Manager",
                "recipient_name": "Dr. Sarah Chen",
                "communication_date": now - timedelta(days=90),
                "duration_minutes": 0,
                "follow_up_required": True,
                "follow_up_date": now - timedelta(days=85),
                "attachments_count": 2,
                "notes": "Amendment includes updated eligibility criteria and dosing schedule.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "CML-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "communication_channel": CommunicationChannel.PHONE,
                "communication_priority": CommunicationPriority.HIGH,
                "subject": "Enrollment Target Discussion",
                "summary": "Discussed enrollment pace with site coordinator. Site is behind target by 3 subjects. Action plan agreed upon.",
                "direction": "outbound",
                "initiated_by": "CRA Lead",
                "recipient_name": "Study Coordinator Jane Miller",
                "communication_date": now - timedelta(days=75),
                "duration_minutes": 25,
                "follow_up_required": True,
                "follow_up_date": now - timedelta(days=60),
                "attachments_count": 0,
                "notes": "Site agreed to extend screening hours and increase referral outreach.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "CML-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-LA-001",
                "communication_channel": CommunicationChannel.VIDEO_CONFERENCE,
                "communication_priority": CommunicationPriority.NORMAL,
                "subject": "Investigator Meeting Recap",
                "summary": "Post-investigator meeting debrief with LA site team. Reviewed updated safety data and protocol clarifications.",
                "direction": "outbound",
                "initiated_by": "Medical Monitor",
                "recipient_name": "Dr. Robert Kim",
                "communication_date": now - timedelta(days=65),
                "duration_minutes": 45,
                "follow_up_required": False,
                "follow_up_date": None,
                "attachments_count": 3,
                "notes": "Meeting recording shared via portal. Q&A document to follow.",
                "created_at": now - timedelta(days=65),
            },
            {
                "id": "CML-004",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-LA-001",
                "communication_channel": CommunicationChannel.PORTAL,
                "communication_priority": CommunicationPriority.LOW,
                "subject": "Updated IRT Manual Upload",
                "summary": "Uploaded revised IRT manual v2.1 to site portal. Notification sent to site staff.",
                "direction": "outbound",
                "initiated_by": "IRT Manager",
                "recipient_name": "Site Staff - LA-001",
                "communication_date": now - timedelta(days=50),
                "duration_minutes": 0,
                "follow_up_required": False,
                "follow_up_date": None,
                "attachments_count": 1,
                "notes": "IRT manual updated to reflect new randomization stratification factors.",
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "CML-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "communication_channel": CommunicationChannel.EMAIL,
                "communication_priority": CommunicationPriority.URGENT,
                "subject": "Safety Alert - Updated Contraindication",
                "summary": "Urgent safety communication regarding newly identified contraindication. Immediate action required at all sites.",
                "direction": "outbound",
                "initiated_by": "Drug Safety Officer",
                "recipient_name": "Dr. Michael Torres",
                "communication_date": now - timedelta(days=80),
                "duration_minutes": 0,
                "follow_up_required": True,
                "follow_up_date": now - timedelta(days=78),
                "attachments_count": 1,
                "notes": "DHPC letter and updated IB section distributed. Acknowledgment mandatory within 48 hours.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "CML-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "communication_channel": CommunicationChannel.IN_PERSON,
                "communication_priority": CommunicationPriority.HIGH,
                "subject": "Monitoring Visit Pre-Study",
                "summary": "Conducted pre-study monitoring visit. Reviewed site facilities, staff qualifications, and regulatory documentation.",
                "direction": "inbound",
                "initiated_by": "Senior CRA",
                "recipient_name": "Site PI and Coordinator",
                "communication_date": now - timedelta(days=70),
                "duration_minutes": 180,
                "follow_up_required": True,
                "follow_up_date": now - timedelta(days=63),
                "attachments_count": 0,
                "notes": "Site meets all qualification criteria. Minor documentation gaps identified and corrective actions assigned.",
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "CML-007",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-BOS-001",
                "communication_channel": CommunicationChannel.LETTER,
                "communication_priority": CommunicationPriority.NORMAL,
                "subject": "IRB Approval Confirmation",
                "summary": "Sent formal letter confirming receipt of IRB approval for protocol v4.0 and updated ICF.",
                "direction": "outbound",
                "initiated_by": "Regulatory Affairs",
                "recipient_name": "Dr. Emily Watson",
                "communication_date": now - timedelta(days=55),
                "duration_minutes": 0,
                "follow_up_required": False,
                "follow_up_date": None,
                "attachments_count": 4,
                "notes": "Includes stamped ICF, IRB approval letter, and site signature page.",
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "CML-008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-BOS-001",
                "communication_channel": CommunicationChannel.VIDEO_CONFERENCE,
                "communication_priority": CommunicationPriority.INFORMATIONAL,
                "subject": "Quarterly Site Performance Review",
                "summary": "Quarterly review of site performance metrics including enrollment, data quality, and protocol compliance.",
                "direction": "outbound",
                "initiated_by": "Clinical Project Manager",
                "recipient_name": "Dr. Emily Watson",
                "communication_date": now - timedelta(days=40),
                "duration_minutes": 60,
                "follow_up_required": False,
                "follow_up_date": None,
                "attachments_count": 2,
                "notes": "Site performing above average. Commended for data entry timeliness.",
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "CML-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-HOU-001",
                "communication_channel": CommunicationChannel.PHONE,
                "communication_priority": CommunicationPriority.URGENT,
                "subject": "SAE Reporting Follow-up",
                "summary": "Follow-up call regarding SAE reported for subject L001. Additional clinical details requested for expedited regulatory submission.",
                "direction": "outbound",
                "initiated_by": "Pharmacovigilance Lead",
                "recipient_name": "Dr. Angela Martinez",
                "communication_date": now - timedelta(days=45),
                "duration_minutes": 35,
                "follow_up_required": True,
                "follow_up_date": now - timedelta(days=43),
                "attachments_count": 0,
                "notes": "PI to provide additional medical records within 24 hours for regulatory submission.",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "CML-010",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-HOU-001",
                "communication_channel": CommunicationChannel.EMAIL,
                "communication_priority": CommunicationPriority.NORMAL,
                "subject": "EDC System Upgrade Notification",
                "summary": "Notification of upcoming EDC system upgrade with scheduled downtime and new feature overview.",
                "direction": "outbound",
                "initiated_by": "Data Management Lead",
                "recipient_name": "Site Data Entry Staff",
                "communication_date": now - timedelta(days=30),
                "duration_minutes": 0,
                "follow_up_required": False,
                "follow_up_date": None,
                "attachments_count": 1,
                "notes": "Scheduled maintenance window: Saturday 2 AM to 6 AM EST. Training webinar link included.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "CML-011",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-SEA-001",
                "communication_channel": CommunicationChannel.PORTAL,
                "communication_priority": CommunicationPriority.HIGH,
                "subject": "Corrective Action Plan Response",
                "summary": "Site submitted corrective action plan in response to monitoring findings. Plan under review by sponsor.",
                "direction": "inbound",
                "initiated_by": "Study Coordinator Tom Bradley",
                "recipient_name": "CRA Lead",
                "communication_date": now - timedelta(days=20),
                "duration_minutes": 0,
                "follow_up_required": True,
                "follow_up_date": now - timedelta(days=13),
                "attachments_count": 2,
                "notes": "CAPA addresses temperature excursion documentation gaps and staff retraining schedule.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "CML-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-SEA-001",
                "communication_channel": CommunicationChannel.EMAIL,
                "communication_priority": CommunicationPriority.LOW,
                "subject": "Holiday Schedule and Contact Information",
                "summary": "Shared updated holiday schedule and after-hours emergency contact information for Q1.",
                "direction": "outbound",
                "initiated_by": "Clinical Operations Coordinator",
                "recipient_name": "All Seattle Site Staff",
                "communication_date": now - timedelta(days=10),
                "duration_minutes": 0,
                "follow_up_required": False,
                "follow_up_date": None,
                "attachments_count": 1,
                "notes": "Includes updated 24/7 medical monitor contact line and sponsor emergency procedures.",
                "created_at": now - timedelta(days=10),
            },
        ]

        for log in logs_data:
            self._communication_logs[log["id"]] = CommunicationLog(**log)

        # --- 12 Newsletter Distributions ---
        newsletters_data = [
            {
                "id": "NWS-001",
                "trial_id": EYLEA_TRIAL,
                "newsletter_title": "EYLEA Trial Monthly Update - January",
                "edition_number": "Vol. 3, Issue 1",
                "distribution_status": DistributionStatus.DELIVERED,
                "target_audience": "All Site PIs and Coordinators",
                "recipients_count": 45,
                "delivered_count": 43,
                "opened_count": 38,
                "scheduled_date": now - timedelta(days=95),
                "sent_date": now - timedelta(days=95),
                "authored_by": "Clinical Communications Team",
                "approved_by": "Medical Director",
                "content_topics": "Enrollment update, protocol amendment summary, upcoming milestones",
                "notes": "High open rate. Positive feedback on enrollment dashboard inclusion.",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "NWS-002",
                "trial_id": EYLEA_TRIAL,
                "newsletter_title": "EYLEA Trial Monthly Update - February",
                "edition_number": "Vol. 3, Issue 2",
                "distribution_status": DistributionStatus.DELIVERED,
                "target_audience": "All Site PIs and Coordinators",
                "recipients_count": 47,
                "delivered_count": 46,
                "opened_count": 35,
                "scheduled_date": now - timedelta(days=65),
                "sent_date": now - timedelta(days=65),
                "authored_by": "Clinical Communications Team",
                "approved_by": "Medical Director",
                "content_topics": "Safety data review, investigator meeting highlights, data quality tips",
                "notes": None,
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "NWS-003",
                "trial_id": EYLEA_TRIAL,
                "newsletter_title": "EYLEA Site Operations Bulletin",
                "edition_number": "Special Edition 1",
                "distribution_status": DistributionStatus.SENT,
                "target_audience": "Study Coordinators Only",
                "recipients_count": 30,
                "delivered_count": 28,
                "opened_count": 20,
                "scheduled_date": now - timedelta(days=35),
                "sent_date": now - timedelta(days=35),
                "authored_by": "Site Management Lead",
                "approved_by": "Clinical Operations Director",
                "content_topics": "IRT update, supply chain changes, holiday scheduling reminders",
                "notes": "Targeted distribution to coordinators for operational changes.",
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "NWS-004",
                "trial_id": EYLEA_TRIAL,
                "newsletter_title": "EYLEA Trial Monthly Update - March",
                "edition_number": "Vol. 3, Issue 3",
                "distribution_status": DistributionStatus.SCHEDULED,
                "target_audience": "All Site PIs and Coordinators",
                "recipients_count": 48,
                "delivered_count": 0,
                "opened_count": 0,
                "scheduled_date": now + timedelta(days=5),
                "sent_date": None,
                "authored_by": "Clinical Communications Team",
                "approved_by": "Medical Director",
                "content_topics": "Enrollment milestone celebration, upcoming DSMB meeting summary",
                "notes": "Content finalized. Awaiting scheduled distribution date.",
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "NWS-005",
                "trial_id": DUPIXENT_TRIAL,
                "newsletter_title": "DUPIXENT Study Insights - Q4",
                "edition_number": "Quarterly Vol. 2, Q4",
                "distribution_status": DistributionStatus.DELIVERED,
                "target_audience": "All Site Staff",
                "recipients_count": 62,
                "delivered_count": 60,
                "opened_count": 48,
                "scheduled_date": now - timedelta(days=85),
                "sent_date": now - timedelta(days=85),
                "authored_by": "Medical Writing Team",
                "approved_by": "Study Medical Lead",
                "content_topics": "Efficacy interim results, patient retention strategies, site spotlight",
                "notes": "Included site spotlight feature on CHI-001 top enrollment.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "NWS-006",
                "trial_id": DUPIXENT_TRIAL,
                "newsletter_title": "DUPIXENT Safety Update Bulletin",
                "edition_number": "Safety Bulletin 3",
                "distribution_status": DistributionStatus.DELIVERED,
                "target_audience": "PIs and Sub-Investigators",
                "recipients_count": 28,
                "delivered_count": 28,
                "opened_count": 26,
                "scheduled_date": now - timedelta(days=60),
                "sent_date": now - timedelta(days=60),
                "authored_by": "Drug Safety Team",
                "approved_by": "Chief Medical Officer",
                "content_topics": "Updated SUSAR summary, new safety signal assessment, IB addendum",
                "notes": "Mandatory read-and-acknowledge required for all PIs.",
                "created_at": now - timedelta(days=65),
            },
            {
                "id": "NWS-007",
                "trial_id": DUPIXENT_TRIAL,
                "newsletter_title": "DUPIXENT Study Insights - Q1",
                "edition_number": "Quarterly Vol. 3, Q1",
                "distribution_status": DistributionStatus.DRAFT,
                "target_audience": "All Site Staff",
                "recipients_count": 0,
                "delivered_count": 0,
                "opened_count": 0,
                "scheduled_date": None,
                "sent_date": None,
                "authored_by": "Medical Writing Team",
                "approved_by": None,
                "content_topics": "Enrollment completion update, database lock timeline, close-out preparation",
                "notes": "Draft in review. Pending medical director approval.",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "NWS-008",
                "trial_id": DUPIXENT_TRIAL,
                "newsletter_title": "DUPIXENT Site Training Digest",
                "edition_number": "Training Vol. 1, Issue 4",
                "distribution_status": DistributionStatus.PARTIALLY_DELIVERED,
                "target_audience": "Newly Activated Sites",
                "recipients_count": 15,
                "delivered_count": 12,
                "opened_count": 9,
                "scheduled_date": now - timedelta(days=25),
                "sent_date": now - timedelta(days=25),
                "authored_by": "Training Coordinator",
                "approved_by": "Clinical Operations Manager",
                "content_topics": "EDC training reminder, specimen handling refresher, IRT access instructions",
                "notes": "3 emails bounced due to outdated addresses. Re-send in progress.",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "NWS-009",
                "trial_id": LIBTAYO_TRIAL,
                "newsletter_title": "LIBTAYO Oncology Trial Report - January",
                "edition_number": "Vol. 1, Issue 1",
                "distribution_status": DistributionStatus.DELIVERED,
                "target_audience": "All Site PIs and Coordinators",
                "recipients_count": 35,
                "delivered_count": 34,
                "opened_count": 30,
                "scheduled_date": now - timedelta(days=80),
                "sent_date": now - timedelta(days=80),
                "authored_by": "Oncology Communications Lead",
                "approved_by": "Oncology Medical Director",
                "content_topics": "Study launch update, first patient enrolled, biomarker sub-study overview",
                "notes": "Inaugural issue. Well received by sites.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "NWS-010",
                "trial_id": LIBTAYO_TRIAL,
                "newsletter_title": "LIBTAYO Oncology Trial Report - February",
                "edition_number": "Vol. 1, Issue 2",
                "distribution_status": DistributionStatus.DELIVERED,
                "target_audience": "All Site PIs and Coordinators",
                "recipients_count": 37,
                "delivered_count": 36,
                "opened_count": 28,
                "scheduled_date": now - timedelta(days=50),
                "sent_date": now - timedelta(days=50),
                "authored_by": "Oncology Communications Lead",
                "approved_by": "Oncology Medical Director",
                "content_topics": "Enrollment progress, immune profiling results, adverse event trends",
                "notes": None,
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "NWS-011",
                "trial_id": LIBTAYO_TRIAL,
                "newsletter_title": "LIBTAYO Regulatory Update",
                "edition_number": "Regulatory Bulletin 1",
                "distribution_status": DistributionStatus.FAILED,
                "target_audience": "Regulatory Contacts at All Sites",
                "recipients_count": 20,
                "delivered_count": 0,
                "opened_count": 0,
                "scheduled_date": now - timedelta(days=15),
                "sent_date": now - timedelta(days=15),
                "authored_by": "Regulatory Affairs Lead",
                "approved_by": "Head of Regulatory",
                "content_topics": "IND annual report filing, IRB renewal reminders, regulatory timeline",
                "notes": "Email server issue caused delivery failure. Re-distribution scheduled.",
                "created_at": now - timedelta(days=18),
            },
            {
                "id": "NWS-012",
                "trial_id": LIBTAYO_TRIAL,
                "newsletter_title": "LIBTAYO Oncology Trial Report - March",
                "edition_number": "Vol. 1, Issue 3",
                "distribution_status": DistributionStatus.DRAFT,
                "target_audience": "All Site PIs and Coordinators",
                "recipients_count": 0,
                "delivered_count": 0,
                "opened_count": 0,
                "scheduled_date": None,
                "sent_date": None,
                "authored_by": "Oncology Communications Lead",
                "approved_by": None,
                "content_topics": "DSMB interim analysis summary, site activation updates, Q2 planning",
                "notes": "Content drafting in progress. Expected completion next week.",
                "created_at": now - timedelta(days=3),
            },
        ]

        for nws in newsletters_data:
            self._newsletter_distributions[nws["id"]] = NewsletterDistribution(**nws)

        # --- 12 Site Query Threads ---
        queries_data = [
            {
                "id": "SQT-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "query_status": QueryStatus.RESOLVED,
                "subject": "Clarification on Visit Window for Week 8",
                "query_text": "Can you confirm the allowable visit window for the Week 8 assessment? Protocol states +/- 3 days but the schedule of assessments shows +/- 5 days.",
                "queried_by": "Study Coordinator Jane Miller",
                "assigned_to": "Protocol Manager",
                "query_date": now - timedelta(days=85),
                "response_text": "The correct visit window is +/- 5 days as shown in the Schedule of Assessments (Table 3). The protocol synopsis will be corrected in the next amendment.",
                "response_date": now - timedelta(days=84),
                "response_time_hours": 18.5,
                "escalated_to": None,
                "resolution_date": now - timedelta(days=84),
                "satisfaction_rating": 5,
                "notes": "Quick resolution. Protocol clarification memo issued to all sites.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "SQT-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "query_status": QueryStatus.RESOLVED,
                "subject": "IRT Drug Dispensing Error",
                "query_text": "IRT system assigned wrong treatment kit number for subject E002. Kit 1045 was dispensed instead of 1047. Need guidance on corrective action.",
                "queried_by": "Pharmacist Dr. Lisa Huang",
                "assigned_to": "IRT Help Desk",
                "query_date": now - timedelta(days=70),
                "response_text": "Confirmed IRT configuration error. Corrected in system. Subject should continue with Kit 1047. Complete a protocol deviation form and document in source.",
                "response_date": now - timedelta(days=69),
                "response_time_hours": 4.0,
                "escalated_to": "IRT Vendor Manager",
                "resolution_date": now - timedelta(days=68),
                "satisfaction_rating": 4,
                "notes": "Root cause identified as IRT stratification factor mapping error. Vendor CAPA initiated.",
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "SQT-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-LA-001",
                "query_status": QueryStatus.CLOSED,
                "subject": "Subject Eligibility Borderline Lab Value",
                "query_text": "Subject has screening creatinine of 1.51 mg/dL. Protocol exclusion is >1.5 mg/dL. Can subject be rescreened or is this a screen failure?",
                "queried_by": "Sub-Investigator Dr. Park",
                "assigned_to": "Medical Monitor",
                "query_date": now - timedelta(days=60),
                "response_text": "Per protocol, the value exceeds the exclusion threshold. Subject is a screen failure. A rescreen is permitted after 30 days if clinically appropriate.",
                "response_date": now - timedelta(days=59),
                "response_time_hours": 22.0,
                "escalated_to": None,
                "resolution_date": now - timedelta(days=58),
                "satisfaction_rating": 3,
                "notes": "Site requested reconsideration. Medical monitor confirmed original decision.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "SQT-004",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-LA-001",
                "query_status": QueryStatus.OPEN,
                "subject": "Missing Investigator Delegation Log Update",
                "query_text": "New sub-investigator Dr. Patel joined the team last week. Delegation log update has been submitted via portal but status shows pending for 7 days.",
                "queried_by": "Regulatory Coordinator",
                "assigned_to": None,
                "query_date": now - timedelta(days=7),
                "response_text": None,
                "response_date": None,
                "response_time_hours": 0.0,
                "escalated_to": None,
                "resolution_date": None,
                "satisfaction_rating": None,
                "notes": "Pending review by sponsor regulatory team.",
                "created_at": now - timedelta(days=7),
            },
            {
                "id": "SQT-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "query_status": QueryStatus.RESOLVED,
                "subject": "Concomitant Medication Reporting Clarification",
                "query_text": "Patient started OTC antihistamine. Protocol says report all concomitant medications but the CRF only has space for prescription medications. Where to document OTC?",
                "queried_by": "Study Coordinator Karen Liu",
                "assigned_to": "Data Management Lead",
                "query_date": now - timedelta(days=55),
                "response_text": "OTC medications should be documented in the 'Other Medications' section of the Concomitant Medications CRF page. A supplemental form has been added to EDC.",
                "response_date": now - timedelta(days=53),
                "response_time_hours": 48.0,
                "escalated_to": None,
                "resolution_date": now - timedelta(days=52),
                "satisfaction_rating": 4,
                "notes": "EDC updated with supplemental OTC medication form for all sites.",
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "SQT-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "query_status": QueryStatus.ESCALATED,
                "subject": "Drug Supply Temperature Excursion at Site",
                "query_text": "Pharmacy freezer alarm triggered over weekend. Temperature reached -15C for approximately 6 hours. Drug supply potentially affected. Need guidance on usability.",
                "queried_by": "Site Pharmacist Dr. Alan Wright",
                "assigned_to": "Drug Supply Manager",
                "query_date": now - timedelta(days=25),
                "response_text": "Quarantine all affected kits immediately. Do not dispense until stability assessment is complete. Replacement kits being shipped.",
                "response_date": now - timedelta(days=25),
                "response_time_hours": 2.0,
                "escalated_to": "Quality Assurance Director",
                "resolution_date": None,
                "satisfaction_rating": None,
                "notes": "Stability assessment in progress by CMC team. Expected completion in 5 business days.",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "SQT-007",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-BOS-001",
                "query_status": QueryStatus.PENDING_RESPONSE,
                "subject": "Subject Withdrawal Process Clarification",
                "query_text": "Subject D003 wishes to withdraw from study but consents to continued safety follow-up. What forms need to be completed and what data collection continues?",
                "queried_by": "Study Coordinator Alex Yun",
                "assigned_to": "Clinical Operations Lead",
                "query_date": now - timedelta(days=12),
                "response_text": None,
                "response_date": None,
                "response_time_hours": 0.0,
                "escalated_to": None,
                "resolution_date": None,
                "satisfaction_rating": None,
                "notes": "Response being prepared with input from medical monitor and data management.",
                "created_at": now - timedelta(days=12),
            },
            {
                "id": "SQT-008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-BOS-001",
                "query_status": QueryStatus.RESPONDED,
                "subject": "Lab Sample Shipping Delay Impact",
                "query_text": "Central lab shipment was delayed by 2 days due to courier issue. Will this affect sample integrity or require recollection?",
                "queried_by": "Lab Coordinator",
                "assigned_to": "Central Lab Liaison",
                "query_date": now - timedelta(days=18),
                "response_text": "Based on stability data, samples are acceptable if maintained at 2-8C during the delay. Please confirm storage conditions during the delay period.",
                "response_date": now - timedelta(days=17),
                "response_time_hours": 8.5,
                "escalated_to": None,
                "resolution_date": None,
                "satisfaction_rating": None,
                "notes": "Site confirming storage temperature logs for the delay period.",
                "created_at": now - timedelta(days=18),
            },
            {
                "id": "SQT-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-HOU-001",
                "query_status": QueryStatus.RESOLVED,
                "subject": "Tumor Assessment Scheduling Conflict",
                "query_text": "Subject L001 tumor assessment due on same day as infusion. Can imaging be done day before to avoid scheduling conflict?",
                "queried_by": "Study Coordinator David Park",
                "assigned_to": "Medical Monitor",
                "query_date": now - timedelta(days=42),
                "response_text": "Imaging may be performed within 3 days prior to the scheduled assessment date per protocol Section 7.2. Day before is acceptable.",
                "response_date": now - timedelta(days=41),
                "response_time_hours": 12.0,
                "escalated_to": None,
                "resolution_date": now - timedelta(days=41),
                "satisfaction_rating": 5,
                "notes": None,
                "created_at": now - timedelta(days=42),
            },
            {
                "id": "SQT-010",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-HOU-001",
                "query_status": QueryStatus.RESOLVED,
                "subject": "Biomarker Sample Processing Delay",
                "query_text": "Biomarker samples for subject L002 were not processed within the required 2-hour window due to lab staffing shortage. Processed at 3.5 hours. Are samples usable?",
                "queried_by": "Lab Tech Kevin Owens",
                "assigned_to": "Biomarker Sciences Lead",
                "query_date": now - timedelta(days=35),
                "response_text": "Samples processed outside the 2-hour window may have reduced biomarker stability. Document as protocol deviation. Samples will be analyzed but flagged for sensitivity analysis.",
                "response_date": now - timedelta(days=34),
                "response_time_hours": 16.0,
                "escalated_to": None,
                "resolution_date": now - timedelta(days=33),
                "satisfaction_rating": 4,
                "notes": "Deviation reported. Site implementing backup lab technician staffing plan.",
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "SQT-011",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-SEA-001",
                "query_status": QueryStatus.OPEN,
                "subject": "New Regulatory Requirement for State-Level Reporting",
                "query_text": "Washington State has introduced new reporting requirements for oncology trials effective next quarter. Does the sponsor have guidance on compliance?",
                "queried_by": "Regulatory Coordinator",
                "assigned_to": None,
                "query_date": now - timedelta(days=5),
                "response_text": None,
                "response_date": None,
                "response_time_hours": 0.0,
                "escalated_to": None,
                "resolution_date": None,
                "satisfaction_rating": None,
                "notes": "Under review by sponsor regulatory and legal teams.",
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "SQT-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-SEA-001",
                "query_status": QueryStatus.CLOSED,
                "subject": "Incorrect Subject ID on Specimen Labels",
                "query_text": "Lab identified specimen labels for subject L003 printed with transposed digits (L030 instead of L003). Three tubes affected. How to proceed?",
                "queried_by": "Lab Tech Amy Chen",
                "assigned_to": "Quality Assurance Lead",
                "query_date": now - timedelta(days=48),
                "response_text": "Relabel specimens with correct subject ID under witnessed correction procedure. Complete incident report and specimen tracking deviation form.",
                "response_date": now - timedelta(days=47),
                "response_time_hours": 6.5,
                "escalated_to": None,
                "resolution_date": now - timedelta(days=46),
                "satisfaction_rating": 5,
                "notes": "Specimens relabeled successfully. Root cause: manual label entry. Recommendation to implement barcode scanning.",
                "created_at": now - timedelta(days=48),
            },
        ]

        for q in queries_data:
            self._site_query_threads[q["id"]] = SiteQueryThread(**q)

        # --- 12 Site Broadcast Alerts ---
        alerts_data = [
            {
                "id": "SBA-001",
                "trial_id": EYLEA_TRIAL,
                "alert_level": AlertLevel.ADVISORY,
                "alert_title": "Protocol Amendment 3 Effective Date Reminder",
                "alert_message": "Protocol Amendment 3 is now effective at all sites. Ensure all subjects enrolled after this date follow the amended protocol. Updated ICF must be used for all new consents.",
                "issued_by": "Clinical Operations Director",
                "issued_date": now - timedelta(days=88),
                "expiry_date": now - timedelta(days=58),
                "sites_targeted": 12,
                "sites_acknowledged": 12,
                "requires_acknowledgment": True,
                "action_required": "Implement amended protocol procedures and confirm updated ICF in use",
                "action_deadline": now - timedelta(days=83),
                "supersedes_alert_id": None,
                "notes": "All sites acknowledged within deadline.",
                "created_at": now - timedelta(days=89),
            },
            {
                "id": "SBA-002",
                "trial_id": EYLEA_TRIAL,
                "alert_level": AlertLevel.WARNING,
                "alert_title": "Drug Supply Shortage - Reduced Allocation",
                "alert_message": "Due to manufacturing delay, drug supply allocation is temporarily reduced by 25%. Sites should limit new enrollment to subjects already in screening pipeline.",
                "issued_by": "Drug Supply Chain Manager",
                "issued_date": now - timedelta(days=60),
                "expiry_date": now - timedelta(days=30),
                "sites_targeted": 12,
                "sites_acknowledged": 10,
                "requires_acknowledgment": True,
                "action_required": "Pause new enrollment screening. Continue dosing enrolled subjects per protocol.",
                "action_deadline": now - timedelta(days=57),
                "supersedes_alert_id": None,
                "notes": "2 sites failed to acknowledge within deadline. Follow-up calls made.",
                "created_at": now - timedelta(days=61),
            },
            {
                "id": "SBA-003",
                "trial_id": EYLEA_TRIAL,
                "alert_level": AlertLevel.ALL_CLEAR,
                "alert_title": "Drug Supply Restored - Normal Operations Resume",
                "alert_message": "Manufacturing issue resolved. Full drug supply allocation restored. Sites may resume normal enrollment activities immediately.",
                "issued_by": "Drug Supply Chain Manager",
                "issued_date": now - timedelta(days=28),
                "expiry_date": now + timedelta(days=30),
                "sites_targeted": 12,
                "sites_acknowledged": 11,
                "requires_acknowledgment": True,
                "action_required": "Resume normal enrollment screening and subject recruitment activities",
                "action_deadline": now - timedelta(days=21),
                "supersedes_alert_id": "SBA-002",
                "notes": "Supersedes drug shortage alert SBA-002.",
                "created_at": now - timedelta(days=29),
            },
            {
                "id": "SBA-004",
                "trial_id": EYLEA_TRIAL,
                "alert_level": AlertLevel.INFORMATIONAL,
                "alert_title": "EDC System Planned Maintenance",
                "alert_message": "The EDC system will undergo scheduled maintenance on Saturday from 2:00 AM to 6:00 AM EST. Data entry will be unavailable during this window.",
                "issued_by": "IT Operations",
                "issued_date": now - timedelta(days=15),
                "expiry_date": now - timedelta(days=13),
                "sites_targeted": 12,
                "sites_acknowledged": 8,
                "requires_acknowledgment": False,
                "action_required": None,
                "action_deadline": None,
                "supersedes_alert_id": None,
                "notes": "Informational only. No action required.",
                "created_at": now - timedelta(days=16),
            },
            {
                "id": "SBA-005",
                "trial_id": DUPIXENT_TRIAL,
                "alert_level": AlertLevel.CRITICAL,
                "alert_title": "Urgent Safety Communication - New Contraindication",
                "alert_message": "A new contraindication has been identified based on post-marketing data. All sites must review the updated IB and implement the revised exclusion criteria immediately. Do not enroll any new subjects until site has acknowledged this alert and confirmed protocol implementation.",
                "issued_by": "Chief Medical Officer",
                "issued_date": now - timedelta(days=79),
                "expiry_date": now - timedelta(days=49),
                "sites_targeted": 18,
                "sites_acknowledged": 18,
                "requires_acknowledgment": True,
                "action_required": "Review updated IB, implement revised exclusion criteria, and confirm compliance",
                "action_deadline": now - timedelta(days=77),
                "supersedes_alert_id": None,
                "notes": "100% site acknowledgment achieved within 48-hour deadline.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "SBA-006",
                "trial_id": DUPIXENT_TRIAL,
                "alert_level": AlertLevel.WARNING,
                "alert_title": "Data Entry Deadline Approaching - Q4 Clean Point",
                "alert_message": "Q4 data clean point deadline is in 10 days. All outstanding queries must be resolved and data entry completed for all subject visits through the cut-off date.",
                "issued_by": "Data Management Director",
                "issued_date": now - timedelta(days=45),
                "expiry_date": now - timedelta(days=35),
                "sites_targeted": 18,
                "sites_acknowledged": 15,
                "requires_acknowledgment": True,
                "action_required": "Complete all outstanding data entry and resolve open queries by deadline",
                "action_deadline": now - timedelta(days=35),
                "supersedes_alert_id": None,
                "notes": "3 sites with >50 open queries receiving daily follow-up calls.",
                "created_at": now - timedelta(days=46),
            },
            {
                "id": "SBA-007",
                "trial_id": DUPIXENT_TRIAL,
                "alert_level": AlertLevel.ADVISORY,
                "alert_title": "Flu Season Precautions for Study Subjects",
                "alert_message": "With flu season approaching, sites are reminded to assess all subjects for flu-like symptoms at each visit. Refer to the updated concomitant illness management guidelines.",
                "issued_by": "Medical Monitor",
                "issued_date": now - timedelta(days=30),
                "expiry_date": now + timedelta(days=60),
                "sites_targeted": 18,
                "sites_acknowledged": 14,
                "requires_acknowledgment": False,
                "action_required": "Review updated concomitant illness management guidelines",
                "action_deadline": None,
                "supersedes_alert_id": None,
                "notes": "Seasonal advisory. Guidelines posted to study portal.",
                "created_at": now - timedelta(days=31),
            },
            {
                "id": "SBA-008",
                "trial_id": DUPIXENT_TRIAL,
                "alert_level": AlertLevel.INFORMATIONAL,
                "alert_title": "New Training Module Available - Skin Biopsy Procedure",
                "alert_message": "A new e-learning training module for the updated skin biopsy collection procedure is now available on the training portal. All site staff involved in biopsy collection should complete within 30 days.",
                "issued_by": "Training Manager",
                "issued_date": now - timedelta(days=20),
                "expiry_date": now + timedelta(days=10),
                "sites_targeted": 18,
                "sites_acknowledged": 10,
                "requires_acknowledgment": False,
                "action_required": "Complete training module within 30 days",
                "action_deadline": now + timedelta(days=10),
                "supersedes_alert_id": None,
                "notes": None,
                "created_at": now - timedelta(days=21),
            },
            {
                "id": "SBA-009",
                "trial_id": LIBTAYO_TRIAL,
                "alert_level": AlertLevel.EMERGENCY,
                "alert_title": "Clinical Hold - Enrollment Suspension",
                "alert_message": "FDA has placed a partial clinical hold on the study. All new enrollment must cease immediately. Currently enrolled subjects may continue treatment pending further review. Sites will receive detailed guidance within 24 hours.",
                "issued_by": "Chief Medical Officer",
                "issued_date": now - timedelta(days=50),
                "expiry_date": now - timedelta(days=35),
                "sites_targeted": 15,
                "sites_acknowledged": 15,
                "requires_acknowledgment": True,
                "action_required": "Immediately suspend all new enrollment. Continue current subjects per protocol. Await further sponsor communication.",
                "action_deadline": now - timedelta(days=50),
                "supersedes_alert_id": None,
                "notes": "100% acknowledgment within 4 hours. All sites confirmed enrollment suspension.",
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "SBA-010",
                "trial_id": LIBTAYO_TRIAL,
                "alert_level": AlertLevel.ALL_CLEAR,
                "alert_title": "Clinical Hold Lifted - Enrollment May Resume",
                "alert_message": "FDA has lifted the partial clinical hold. Enrollment may resume with updated protocol including additional safety monitoring requirements. Updated protocol and ICF being distributed.",
                "issued_by": "Chief Medical Officer",
                "issued_date": now - timedelta(days=34),
                "expiry_date": now + timedelta(days=30),
                "sites_targeted": 15,
                "sites_acknowledged": 13,
                "requires_acknowledgment": True,
                "action_required": "Obtain IRB approval for protocol update before resuming enrollment. Implement additional safety monitoring per updated protocol.",
                "action_deadline": now - timedelta(days=20),
                "supersedes_alert_id": "SBA-009",
                "notes": "Supersedes clinical hold alert SBA-009. 2 sites pending IRB approval.",
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "SBA-011",
                "trial_id": LIBTAYO_TRIAL,
                "alert_level": AlertLevel.WARNING,
                "alert_title": "Specimen Shipping Protocol Change",
                "alert_message": "Effective immediately, all immune profiling specimens must be shipped via cryoport dry shipper instead of standard dry ice packaging. New shipping kits being distributed to all sites.",
                "issued_by": "Central Lab Director",
                "issued_date": now - timedelta(days=22),
                "expiry_date": now + timedelta(days=60),
                "sites_targeted": 15,
                "sites_acknowledged": 12,
                "requires_acknowledgment": True,
                "action_required": "Discontinue dry ice shipping for immune profiling specimens. Use cryoport dry shippers only.",
                "action_deadline": now - timedelta(days=15),
                "supersedes_alert_id": None,
                "notes": "New shipping kits dispatched. 3 sites awaiting delivery.",
                "created_at": now - timedelta(days=23),
            },
            {
                "id": "SBA-012",
                "trial_id": LIBTAYO_TRIAL,
                "alert_level": AlertLevel.ADVISORY,
                "alert_title": "Upcoming DSMB Meeting - Data Freeze Reminder",
                "alert_message": "The next DSMB meeting is scheduled for 2 weeks from now. A data freeze will be implemented 5 days prior. All sites must complete data entry for visits through the cut-off date.",
                "issued_by": "Biostatistics Lead",
                "issued_date": now - timedelta(days=8),
                "expiry_date": now + timedelta(days=6),
                "sites_targeted": 15,
                "sites_acknowledged": 9,
                "requires_acknowledgment": True,
                "action_required": "Complete all data entry for visits through the data cut-off date",
                "action_deadline": now + timedelta(days=2),
                "supersedes_alert_id": None,
                "notes": "Data freeze date communicated. Sites with outstanding data receiving daily reminders.",
                "created_at": now - timedelta(days=9),
            },
        ]

        for alert in alerts_data:
            self._site_broadcast_alerts[alert["id"]] = SiteBroadcastAlert(**alert)

    # ------------------------------------------------------------------
    # Communication Logs
    # ------------------------------------------------------------------

    def list_communication_logs(
        self,
        *,
        trial_id: str | None = None,
        communication_channel: CommunicationChannel | None = None,
        communication_priority: CommunicationPriority | None = None,
        site_id: str | None = None,
    ) -> list[CommunicationLog]:
        """List communication logs with optional filters."""
        with self._lock:
            result = list(self._communication_logs.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if communication_channel is not None:
            result = [r for r in result if r.communication_channel == communication_channel]
        if communication_priority is not None:
            result = [r for r in result if r.communication_priority == communication_priority]
        if site_id is not None:
            result = [r for r in result if r.site_id == site_id]

        return sorted(result, key=lambda r: r.communication_date, reverse=True)

    def get_communication_log(self, log_id: str) -> CommunicationLog | None:
        """Get a single communication log by ID."""
        with self._lock:
            return self._communication_logs.get(log_id)

    def create_communication_log(self, payload: CommunicationLogCreate) -> CommunicationLog:
        """Create a new communication log."""
        now = datetime.now(timezone.utc)
        log_id = f"CML-{uuid4().hex[:8].upper()}"
        record = CommunicationLog(
            id=log_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            communication_channel=payload.communication_channel,
            communication_priority=payload.communication_priority,
            subject=payload.subject,
            summary=payload.summary,
            direction="outbound",
            initiated_by=payload.initiated_by,
            recipient_name=payload.recipient_name,
            communication_date=payload.communication_date,
            duration_minutes=0,
            follow_up_required=False,
            follow_up_date=None,
            attachments_count=0,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._communication_logs[log_id] = record
        logger.info("Created communication log %s for trial %s", log_id, payload.trial_id)
        return record

    def update_communication_log(
        self, log_id: str, payload: CommunicationLogUpdate
    ) -> CommunicationLog | None:
        """Update an existing communication log."""
        with self._lock:
            existing = self._communication_logs.get(log_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CommunicationLog(**data)
            self._communication_logs[log_id] = updated
        return updated

    def delete_communication_log(self, log_id: str) -> bool:
        """Delete a communication log. Returns True if deleted."""
        with self._lock:
            if log_id in self._communication_logs:
                del self._communication_logs[log_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Newsletter Distributions
    # ------------------------------------------------------------------

    def list_newsletter_distributions(
        self,
        *,
        trial_id: str | None = None,
        distribution_status: DistributionStatus | None = None,
    ) -> list[NewsletterDistribution]:
        """List newsletter distributions with optional filters."""
        with self._lock:
            result = list(self._newsletter_distributions.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if distribution_status is not None:
            result = [r for r in result if r.distribution_status == distribution_status]

        return sorted(result, key=lambda r: r.created_at, reverse=True)

    def get_newsletter_distribution(self, newsletter_id: str) -> NewsletterDistribution | None:
        """Get a single newsletter distribution by ID."""
        with self._lock:
            return self._newsletter_distributions.get(newsletter_id)

    def create_newsletter_distribution(
        self, payload: NewsletterDistributionCreate
    ) -> NewsletterDistribution:
        """Create a new newsletter distribution."""
        now = datetime.now(timezone.utc)
        newsletter_id = f"NWS-{uuid4().hex[:8].upper()}"
        record = NewsletterDistribution(
            id=newsletter_id,
            trial_id=payload.trial_id,
            newsletter_title=payload.newsletter_title,
            edition_number=payload.edition_number,
            distribution_status=DistributionStatus.DRAFT,
            target_audience=payload.target_audience,
            recipients_count=payload.recipients_count,
            delivered_count=0,
            opened_count=0,
            scheduled_date=None,
            sent_date=None,
            authored_by=payload.authored_by,
            approved_by=None,
            content_topics=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._newsletter_distributions[newsletter_id] = record
        logger.info(
            "Created newsletter distribution %s for trial %s", newsletter_id, payload.trial_id
        )
        return record

    def update_newsletter_distribution(
        self, newsletter_id: str, payload: NewsletterDistributionUpdate
    ) -> NewsletterDistribution | None:
        """Update an existing newsletter distribution."""
        with self._lock:
            existing = self._newsletter_distributions.get(newsletter_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = NewsletterDistribution(**data)
            self._newsletter_distributions[newsletter_id] = updated
        return updated

    def delete_newsletter_distribution(self, newsletter_id: str) -> bool:
        """Delete a newsletter distribution. Returns True if deleted."""
        with self._lock:
            if newsletter_id in self._newsletter_distributions:
                del self._newsletter_distributions[newsletter_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Site Query Threads
    # ------------------------------------------------------------------

    def list_site_query_threads(
        self,
        *,
        trial_id: str | None = None,
        query_status: QueryStatus | None = None,
        site_id: str | None = None,
    ) -> list[SiteQueryThread]:
        """List site query threads with optional filters."""
        with self._lock:
            result = list(self._site_query_threads.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if query_status is not None:
            result = [r for r in result if r.query_status == query_status]
        if site_id is not None:
            result = [r for r in result if r.site_id == site_id]

        return sorted(result, key=lambda r: r.query_date, reverse=True)

    def get_site_query_thread(self, query_id: str) -> SiteQueryThread | None:
        """Get a single site query thread by ID."""
        with self._lock:
            return self._site_query_threads.get(query_id)

    def create_site_query_thread(self, payload: SiteQueryThreadCreate) -> SiteQueryThread:
        """Create a new site query thread."""
        now = datetime.now(timezone.utc)
        query_id = f"SQT-{uuid4().hex[:8].upper()}"
        record = SiteQueryThread(
            id=query_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            query_status=QueryStatus.OPEN,
            subject=payload.subject,
            query_text=payload.query_text,
            queried_by=payload.queried_by,
            assigned_to=None,
            query_date=payload.query_date,
            response_text=None,
            response_date=None,
            response_time_hours=0.0,
            escalated_to=None,
            resolution_date=None,
            satisfaction_rating=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._site_query_threads[query_id] = record
        logger.info("Created site query thread %s for trial %s", query_id, payload.trial_id)
        return record

    def update_site_query_thread(
        self, query_id: str, payload: SiteQueryThreadUpdate
    ) -> SiteQueryThread | None:
        """Update an existing site query thread."""
        with self._lock:
            existing = self._site_query_threads.get(query_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = SiteQueryThread(**data)
            self._site_query_threads[query_id] = updated
        return updated

    def delete_site_query_thread(self, query_id: str) -> bool:
        """Delete a site query thread. Returns True if deleted."""
        with self._lock:
            if query_id in self._site_query_threads:
                del self._site_query_threads[query_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Site Broadcast Alerts
    # ------------------------------------------------------------------

    def list_site_broadcast_alerts(
        self,
        *,
        trial_id: str | None = None,
        alert_level: AlertLevel | None = None,
    ) -> list[SiteBroadcastAlert]:
        """List site broadcast alerts with optional filters."""
        with self._lock:
            result = list(self._site_broadcast_alerts.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if alert_level is not None:
            result = [r for r in result if r.alert_level == alert_level]

        return sorted(result, key=lambda r: r.issued_date, reverse=True)

    def get_site_broadcast_alert(self, alert_id: str) -> SiteBroadcastAlert | None:
        """Get a single site broadcast alert by ID."""
        with self._lock:
            return self._site_broadcast_alerts.get(alert_id)

    def create_site_broadcast_alert(
        self, payload: SiteBroadcastAlertCreate
    ) -> SiteBroadcastAlert:
        """Create a new site broadcast alert."""
        now = datetime.now(timezone.utc)
        alert_id = f"SBA-{uuid4().hex[:8].upper()}"
        record = SiteBroadcastAlert(
            id=alert_id,
            trial_id=payload.trial_id,
            alert_level=payload.alert_level,
            alert_title=payload.alert_title,
            alert_message=payload.alert_message,
            issued_by=payload.issued_by,
            issued_date=payload.issued_date,
            expiry_date=None,
            sites_targeted=payload.sites_targeted,
            sites_acknowledged=0,
            requires_acknowledgment=True,
            action_required=None,
            action_deadline=None,
            supersedes_alert_id=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._site_broadcast_alerts[alert_id] = record
        logger.info("Created site broadcast alert %s for trial %s", alert_id, payload.trial_id)
        return record

    def update_site_broadcast_alert(
        self, alert_id: str, payload: SiteBroadcastAlertUpdate
    ) -> SiteBroadcastAlert | None:
        """Update an existing site broadcast alert."""
        with self._lock:
            existing = self._site_broadcast_alerts.get(alert_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = SiteBroadcastAlert(**data)
            self._site_broadcast_alerts[alert_id] = updated
        return updated

    def delete_site_broadcast_alert(self, alert_id: str) -> bool:
        """Delete a site broadcast alert. Returns True if deleted."""
        with self._lock:
            if alert_id in self._site_broadcast_alerts:
                del self._site_broadcast_alerts[alert_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> SiteCommunicationMetrics:
        """Compute aggregated site communication metrics."""
        with self._lock:
            logs = list(self._communication_logs.values())
            newsletters = list(self._newsletter_distributions.values())
            queries = list(self._site_query_threads.values())
            alerts = list(self._site_broadcast_alerts.values())

        # Communications by channel
        communications_by_channel: dict[str, int] = {}
        for log in logs:
            key = log.communication_channel.value
            communications_by_channel[key] = communications_by_channel.get(key, 0) + 1

        # Communications by priority
        communications_by_priority: dict[str, int] = {}
        for log in logs:
            key = log.communication_priority.value
            communications_by_priority[key] = communications_by_priority.get(key, 0) + 1

        # Newsletters by status
        newsletters_by_status: dict[str, int] = {}
        for nws in newsletters:
            key = nws.distribution_status.value
            newsletters_by_status[key] = newsletters_by_status.get(key, 0) + 1

        # Average newsletter open rate
        delivered_newsletters = [n for n in newsletters if n.delivered_count > 0]
        if delivered_newsletters:
            total_open_rate = sum(
                (n.opened_count / max(1, n.delivered_count)) * 100
                for n in delivered_newsletters
            )
            avg_open_rate = round(total_open_rate / len(delivered_newsletters), 1)
        else:
            avg_open_rate = 0.0

        # Queries by status
        queries_by_status: dict[str, int] = {}
        for q in queries:
            key = q.query_status.value
            queries_by_status[key] = queries_by_status.get(key, 0) + 1

        # Average query response time (only for queries with a response)
        responded_queries = [q for q in queries if q.response_time_hours > 0]
        if responded_queries:
            avg_response_hours = round(
                sum(q.response_time_hours for q in responded_queries)
                / len(responded_queries),
                1,
            )
        else:
            avg_response_hours = 0.0

        # Alerts by level
        alerts_by_level: dict[str, int] = {}
        for alert in alerts:
            key = alert.alert_level.value
            alerts_by_level[key] = alerts_by_level.get(key, 0) + 1

        # Alert acknowledgment rate
        ack_required_alerts = [a for a in alerts if a.requires_acknowledgment]
        if ack_required_alerts:
            total_ack_rate = sum(
                (a.sites_acknowledged / max(1, a.sites_targeted)) * 100
                for a in ack_required_alerts
            )
            ack_rate = round(total_ack_rate / len(ack_required_alerts), 1)
        else:
            ack_rate = 0.0

        return SiteCommunicationMetrics(
            total_communications=len(logs),
            communications_by_channel=communications_by_channel,
            communications_by_priority=communications_by_priority,
            total_newsletters=len(newsletters),
            newsletters_by_status=newsletters_by_status,
            avg_newsletter_open_rate=avg_open_rate,
            total_queries=len(queries),
            queries_by_status=queries_by_status,
            avg_query_response_hours=avg_response_hours,
            total_alerts=len(alerts),
            alerts_by_level=alerts_by_level,
            alert_acknowledgment_rate=ack_rate,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: SiteCommunicationService | None = None
_instance_lock = threading.Lock()


def get_site_communication_service() -> SiteCommunicationService:
    """Return the singleton SiteCommunicationService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = SiteCommunicationService()
    return _instance


def reset_site_communication_service() -> SiteCommunicationService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = SiteCommunicationService()
    return _instance
