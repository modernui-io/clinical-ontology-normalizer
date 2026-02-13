"""Investigator Oversight Service (INV-OVS).

Manages investigator oversight operations: investigator performance reviews,
site supervision records, GCP compliance checks, investigator communications,
and oversight metrics.

Usage:
    from app.services.investigator_oversight_service import (
        get_investigator_oversight_service,
    )

    svc = get_investigator_oversight_service()
    performances = svc.list_investigator_performances()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.investigator_oversight import (
    CommunicationStatus,
    CommunicationType,
    ComplianceResult,
    GCPComplianceCheck,
    GCPComplianceCheckCreate,
    GCPComplianceCheckUpdate,
    InvestigatorCommunication,
    InvestigatorCommunicationCreate,
    InvestigatorCommunicationUpdate,
    InvestigatorOversightMetrics,
    InvestigatorPerformance,
    InvestigatorPerformanceCreate,
    InvestigatorPerformanceUpdate,
    PerformanceRating,
    SiteSupervision,
    SiteSupervisionCreate,
    SiteSupervisionUpdate,
    SupervisionType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class InvestigatorOversightService:
    """In-memory Investigator Oversight engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._investigator_performances: dict[str, InvestigatorPerformance] = {}
        self._site_supervisions: dict[str, SiteSupervision] = {}
        self._gcp_compliance_checks: dict[str, GCPComplianceCheck] = {}
        self._investigator_communications: dict[str, InvestigatorCommunication] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic investigator oversight data."""
        now = datetime.now(timezone.utc)

        # --- 12 Investigator Performance Records ---
        performance_data = [
            {
                "id": "IP-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "investigator_name": "Dr. Sarah Chen",
                "performance_rating": PerformanceRating.OUTSTANDING,
                "review_period_start": now - timedelta(days=180),
                "review_period_end": now - timedelta(days=90),
                "enrollment_target": 20,
                "enrollment_actual": 24,
                "protocol_deviations": 1,
                "query_response_days": 1.5,
                "sae_reporting_compliance_pct": 100.0,
                "training_completion_pct": 100.0,
                "reviewed_by": "Dr. James Wilson",
                "notes": "Exceptional enrollment and compliance. Model investigator site.",
                "created_at": now - timedelta(days=88),
            },
            {
                "id": "IP-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "investigator_name": "Dr. Sarah Chen",
                "performance_rating": PerformanceRating.EXCEEDS_EXPECTATIONS,
                "review_period_start": now - timedelta(days=90),
                "review_period_end": now,
                "enrollment_target": 15,
                "enrollment_actual": 17,
                "protocol_deviations": 2,
                "query_response_days": 2.0,
                "sae_reporting_compliance_pct": 100.0,
                "training_completion_pct": 100.0,
                "reviewed_by": "Dr. James Wilson",
                "notes": "Continued strong performance. Minor increase in protocol deviations addressed.",
                "created_at": now - timedelta(days=2),
            },
            {
                "id": "IP-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-LA-001",
                "investigator_name": "Dr. Michael Torres",
                "performance_rating": PerformanceRating.MEETS_EXPECTATIONS,
                "review_period_start": now - timedelta(days=180),
                "review_period_end": now - timedelta(days=90),
                "enrollment_target": 15,
                "enrollment_actual": 14,
                "protocol_deviations": 4,
                "query_response_days": 4.5,
                "sae_reporting_compliance_pct": 95.0,
                "training_completion_pct": 90.0,
                "reviewed_by": "Dr. James Wilson",
                "notes": "Adequate performance. Query response time needs improvement.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "IP-004",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-LA-001",
                "investigator_name": "Dr. Michael Torres",
                "performance_rating": PerformanceRating.NEEDS_IMPROVEMENT,
                "review_period_start": now - timedelta(days=90),
                "review_period_end": now,
                "enrollment_target": 15,
                "enrollment_actual": 8,
                "protocol_deviations": 7,
                "query_response_days": 8.0,
                "sae_reporting_compliance_pct": 85.0,
                "training_completion_pct": 75.0,
                "reviewed_by": "Dr. James Wilson",
                "notes": "Significant decline in enrollment and compliance. Corrective action plan initiated.",
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "IP-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "investigator_name": "Dr. Karen Liu",
                "performance_rating": PerformanceRating.EXCEEDS_EXPECTATIONS,
                "review_period_start": now - timedelta(days=180),
                "review_period_end": now - timedelta(days=90),
                "enrollment_target": 25,
                "enrollment_actual": 28,
                "protocol_deviations": 2,
                "query_response_days": 2.0,
                "sae_reporting_compliance_pct": 100.0,
                "training_completion_pct": 100.0,
                "reviewed_by": "Dr. Patricia Evans",
                "notes": "Strong enrollment and excellent data quality.",
                "created_at": now - timedelta(days=87),
            },
            {
                "id": "IP-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "investigator_name": "Dr. Karen Liu",
                "performance_rating": PerformanceRating.OUTSTANDING,
                "review_period_start": now - timedelta(days=90),
                "review_period_end": now,
                "enrollment_target": 20,
                "enrollment_actual": 25,
                "protocol_deviations": 0,
                "query_response_days": 1.0,
                "sae_reporting_compliance_pct": 100.0,
                "training_completion_pct": 100.0,
                "reviewed_by": "Dr. Patricia Evans",
                "notes": "Zero deviations. Best performing site across all metrics.",
                "created_at": now - timedelta(days=1),
            },
            {
                "id": "IP-007",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-BOS-001",
                "investigator_name": "Dr. Robert Kim",
                "performance_rating": PerformanceRating.MEETS_EXPECTATIONS,
                "review_period_start": now - timedelta(days=180),
                "review_period_end": now - timedelta(days=90),
                "enrollment_target": 18,
                "enrollment_actual": 16,
                "protocol_deviations": 3,
                "query_response_days": 3.5,
                "sae_reporting_compliance_pct": 100.0,
                "training_completion_pct": 95.0,
                "reviewed_by": "Dr. Patricia Evans",
                "notes": "Steady enrollment. Minor query response delays noted.",
                "created_at": now - timedelta(days=86),
            },
            {
                "id": "IP-008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-BOS-001",
                "investigator_name": "Dr. Robert Kim",
                "performance_rating": PerformanceRating.UNSATISFACTORY,
                "review_period_start": now - timedelta(days=90),
                "review_period_end": now,
                "enrollment_target": 18,
                "enrollment_actual": 5,
                "protocol_deviations": 12,
                "query_response_days": 14.0,
                "sae_reporting_compliance_pct": 70.0,
                "training_completion_pct": 60.0,
                "reviewed_by": "Dr. Patricia Evans",
                "notes": "Critical performance issues. Site at risk of closure. Immediate remediation required.",
                "created_at": now - timedelta(days=2),
            },
            {
                "id": "IP-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-HOU-001",
                "investigator_name": "Dr. Angela Martinez",
                "performance_rating": PerformanceRating.OUTSTANDING,
                "review_period_start": now - timedelta(days=180),
                "review_period_end": now - timedelta(days=90),
                "enrollment_target": 12,
                "enrollment_actual": 15,
                "protocol_deviations": 0,
                "query_response_days": 1.0,
                "sae_reporting_compliance_pct": 100.0,
                "training_completion_pct": 100.0,
                "reviewed_by": "Dr. David Park",
                "notes": "Top-tier oncology site. Perfect compliance record.",
                "created_at": now - timedelta(days=89),
            },
            {
                "id": "IP-010",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-HOU-001",
                "investigator_name": "Dr. Angela Martinez",
                "performance_rating": PerformanceRating.EXCEEDS_EXPECTATIONS,
                "review_period_start": now - timedelta(days=90),
                "review_period_end": now,
                "enrollment_target": 10,
                "enrollment_actual": 12,
                "protocol_deviations": 1,
                "query_response_days": 1.5,
                "sae_reporting_compliance_pct": 100.0,
                "training_completion_pct": 100.0,
                "reviewed_by": "Dr. David Park",
                "notes": "Sustained excellence. Single minor deviation documented and resolved.",
                "created_at": now - timedelta(days=1),
            },
            {
                "id": "IP-011",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-SEA-001",
                "investigator_name": "Dr. Thomas Wright",
                "performance_rating": PerformanceRating.NEEDS_IMPROVEMENT,
                "review_period_start": now - timedelta(days=180),
                "review_period_end": now - timedelta(days=90),
                "enrollment_target": 10,
                "enrollment_actual": 6,
                "protocol_deviations": 5,
                "query_response_days": 7.0,
                "sae_reporting_compliance_pct": 90.0,
                "training_completion_pct": 80.0,
                "reviewed_by": "Dr. David Park",
                "notes": "Below-target enrollment. Training gaps identified. Remediation plan in place.",
                "created_at": now - timedelta(days=88),
            },
            {
                "id": "IP-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-SEA-001",
                "investigator_name": "Dr. Thomas Wright",
                "performance_rating": PerformanceRating.NOT_EVALUATED,
                "review_period_start": now - timedelta(days=90),
                "review_period_end": now,
                "enrollment_target": 10,
                "enrollment_actual": 3,
                "protocol_deviations": 2,
                "query_response_days": 5.0,
                "sae_reporting_compliance_pct": 95.0,
                "training_completion_pct": 85.0,
                "reviewed_by": "Dr. David Park",
                "notes": "Evaluation pending completion of remediation review cycle.",
                "created_at": now - timedelta(days=1),
            },
        ]

        for p in performance_data:
            self._investigator_performances[p["id"]] = InvestigatorPerformance(**p)

        # --- 12 Site Supervision Records ---
        supervision_data = [
            {
                "id": "SS-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "supervision_type": SupervisionType.ROUTINE_MONITORING,
                "visit_date": now - timedelta(days=60),
                "monitor_name": "Lisa Chang, CRA",
                "duration_hours": 8.0,
                "findings_count": 2,
                "critical_findings": 0,
                "action_items_generated": 3,
                "action_items_resolved": 3,
                "report_finalized": True,
                "follow_up_required": False,
                "follow_up_date": None,
                "notes": "Routine monitoring visit. Minor documentation findings resolved on-site.",
                "created_at": now - timedelta(days=59),
            },
            {
                "id": "SS-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "supervision_type": SupervisionType.REMOTE_REVIEW,
                "visit_date": now - timedelta(days=30),
                "monitor_name": "Lisa Chang, CRA",
                "duration_hours": 4.0,
                "findings_count": 0,
                "critical_findings": 0,
                "action_items_generated": 1,
                "action_items_resolved": 1,
                "report_finalized": True,
                "follow_up_required": False,
                "follow_up_date": None,
                "notes": "Remote data review. All queries addressed. No new findings.",
                "created_at": now - timedelta(days=29),
            },
            {
                "id": "SS-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-LA-001",
                "supervision_type": SupervisionType.FOR_CAUSE,
                "visit_date": now - timedelta(days=20),
                "monitor_name": "Mark Stevens, Sr. CRA",
                "duration_hours": 10.0,
                "findings_count": 8,
                "critical_findings": 2,
                "action_items_generated": 12,
                "action_items_resolved": 5,
                "report_finalized": True,
                "follow_up_required": True,
                "follow_up_date": now + timedelta(days=10),
                "notes": "For-cause visit triggered by declining performance metrics. Critical consent form issues identified.",
                "created_at": now - timedelta(days=19),
            },
            {
                "id": "SS-004",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-LA-001",
                "supervision_type": SupervisionType.TRIGGERED,
                "visit_date": now - timedelta(days=45),
                "monitor_name": "Mark Stevens, Sr. CRA",
                "duration_hours": 6.0,
                "findings_count": 5,
                "critical_findings": 1,
                "action_items_generated": 7,
                "action_items_resolved": 4,
                "report_finalized": True,
                "follow_up_required": True,
                "follow_up_date": now - timedelta(days=20),
                "notes": "Triggered by high protocol deviation rate. IP accountability gap identified.",
                "created_at": now - timedelta(days=44),
            },
            {
                "id": "SS-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "supervision_type": SupervisionType.ROUTINE_MONITORING,
                "visit_date": now - timedelta(days=55),
                "monitor_name": "Jennifer Park, CRA",
                "duration_hours": 8.0,
                "findings_count": 1,
                "critical_findings": 0,
                "action_items_generated": 2,
                "action_items_resolved": 2,
                "report_finalized": True,
                "follow_up_required": False,
                "follow_up_date": None,
                "notes": "Clean monitoring visit. One minor labeling finding corrected.",
                "created_at": now - timedelta(days=54),
            },
            {
                "id": "SS-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "supervision_type": SupervisionType.CENTRALIZED,
                "visit_date": now - timedelta(days=15),
                "monitor_name": "Analytics Team",
                "duration_hours": 3.0,
                "findings_count": 0,
                "critical_findings": 0,
                "action_items_generated": 0,
                "action_items_resolved": 0,
                "report_finalized": True,
                "follow_up_required": False,
                "follow_up_date": None,
                "notes": "Centralized monitoring review. All KRIs within acceptable thresholds.",
                "created_at": now - timedelta(days=14),
            },
            {
                "id": "SS-007",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-BOS-001",
                "supervision_type": SupervisionType.ROUTINE_MONITORING,
                "visit_date": now - timedelta(days=40),
                "monitor_name": "Jennifer Park, CRA",
                "duration_hours": 8.0,
                "findings_count": 6,
                "critical_findings": 1,
                "action_items_generated": 9,
                "action_items_resolved": 3,
                "report_finalized": True,
                "follow_up_required": True,
                "follow_up_date": now - timedelta(days=10),
                "notes": "Multiple findings including ICF version control issue. Immediate corrective action required.",
                "created_at": now - timedelta(days=39),
            },
            {
                "id": "SS-008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-BOS-001",
                "supervision_type": SupervisionType.FOR_CAUSE,
                "visit_date": now - timedelta(days=10),
                "monitor_name": "Mark Stevens, Sr. CRA",
                "duration_hours": 12.0,
                "findings_count": 15,
                "critical_findings": 4,
                "action_items_generated": 20,
                "action_items_resolved": 2,
                "report_finalized": False,
                "follow_up_required": True,
                "follow_up_date": now + timedelta(days=5),
                "notes": "For-cause visit due to unsatisfactory performance. Major GCP violations. Site closure under consideration.",
                "created_at": now - timedelta(days=9),
            },
            {
                "id": "SS-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-HOU-001",
                "supervision_type": SupervisionType.ROUTINE_MONITORING,
                "visit_date": now - timedelta(days=50),
                "monitor_name": "David Kim, CRA",
                "duration_hours": 8.0,
                "findings_count": 1,
                "critical_findings": 0,
                "action_items_generated": 2,
                "action_items_resolved": 2,
                "report_finalized": True,
                "follow_up_required": False,
                "follow_up_date": None,
                "notes": "Exemplary site. One minor documentation correction. All source data verified.",
                "created_at": now - timedelta(days=49),
            },
            {
                "id": "SS-010",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-HOU-001",
                "supervision_type": SupervisionType.CENTRALIZED,
                "visit_date": now - timedelta(days=10),
                "monitor_name": "Analytics Team",
                "duration_hours": 2.0,
                "findings_count": 0,
                "critical_findings": 0,
                "action_items_generated": 0,
                "action_items_resolved": 0,
                "report_finalized": True,
                "follow_up_required": False,
                "follow_up_date": None,
                "notes": "Centralized review. All safety and enrollment KRIs within range.",
                "created_at": now - timedelta(days=9),
            },
            {
                "id": "SS-011",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-SEA-001",
                "supervision_type": SupervisionType.TRIGGERED,
                "visit_date": now - timedelta(days=35),
                "monitor_name": "David Kim, CRA",
                "duration_hours": 8.0,
                "findings_count": 7,
                "critical_findings": 2,
                "action_items_generated": 10,
                "action_items_resolved": 4,
                "report_finalized": True,
                "follow_up_required": True,
                "follow_up_date": now + timedelta(days=15),
                "notes": "Triggered visit after hemolyzed specimen incident. Training deficiencies confirmed.",
                "created_at": now - timedelta(days=34),
            },
            {
                "id": "SS-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-SEA-001",
                "supervision_type": SupervisionType.CLOSEOUT,
                "visit_date": now - timedelta(days=5),
                "monitor_name": "David Kim, CRA",
                "duration_hours": 6.0,
                "findings_count": 3,
                "critical_findings": 0,
                "action_items_generated": 5,
                "action_items_resolved": 0,
                "report_finalized": False,
                "follow_up_required": True,
                "follow_up_date": now + timedelta(days=20),
                "notes": "Closeout monitoring visit. Pending resolution of outstanding action items from triggered visit.",
                "created_at": now - timedelta(days=4),
            },
        ]

        for s in supervision_data:
            self._site_supervisions[s["id"]] = SiteSupervision(**s)

        # --- 12 GCP Compliance Check Records ---
        compliance_data = [
            {
                "id": "GCP-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "investigator_name": "Dr. Sarah Chen",
                "compliance_result": ComplianceResult.COMPLIANT,
                "check_date": now - timedelta(days=60),
                "gcp_area": "Informed Consent",
                "finding_description": None,
                "corrective_action": None,
                "corrective_action_due": None,
                "corrective_action_completed": None,
                "verified_by": "Lisa Chang, CRA",
                "assessed_by": "QA Team Lead",
                "notes": "All ICFs properly executed. Version control maintained.",
                "created_at": now - timedelta(days=59),
            },
            {
                "id": "GCP-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "investigator_name": "Dr. Sarah Chen",
                "compliance_result": ComplianceResult.MINOR_FINDING,
                "check_date": now - timedelta(days=30),
                "gcp_area": "Essential Documents",
                "finding_description": "Delegation log update delayed by 5 days for new study coordinator.",
                "corrective_action": "Update delegation log within 24 hours of staff changes.",
                "corrective_action_due": now - timedelta(days=23),
                "corrective_action_completed": now - timedelta(days=25),
                "verified_by": "Lisa Chang, CRA",
                "assessed_by": "QA Team Lead",
                "notes": "Minor finding resolved ahead of deadline.",
                "created_at": now - timedelta(days=29),
            },
            {
                "id": "GCP-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-LA-001",
                "investigator_name": "Dr. Michael Torres",
                "compliance_result": ComplianceResult.MAJOR_FINDING,
                "check_date": now - timedelta(days=20),
                "gcp_area": "Informed Consent",
                "finding_description": "Two subjects consented using outdated ICF version (v2 instead of v3).",
                "corrective_action": "Re-consent affected subjects with current ICF. Retrain all site staff on version control.",
                "corrective_action_due": now + timedelta(days=10),
                "corrective_action_completed": None,
                "verified_by": None,
                "assessed_by": "Sr. QA Auditor",
                "notes": "Major GCP finding. Sponsor notification required. CAPA initiated.",
                "created_at": now - timedelta(days=19),
            },
            {
                "id": "GCP-004",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-LA-001",
                "investigator_name": "Dr. Michael Torres",
                "compliance_result": ComplianceResult.CRITICAL_FINDING,
                "check_date": now - timedelta(days=15),
                "gcp_area": "Investigational Product",
                "finding_description": "IP temperature excursion not documented for 72 hours. Affected doses may have been administered.",
                "corrective_action": "Full IP reconciliation. Assess affected subjects. Implement continuous temperature monitoring.",
                "corrective_action_due": now + timedelta(days=5),
                "corrective_action_completed": None,
                "verified_by": None,
                "assessed_by": "Sr. QA Auditor",
                "notes": "Critical finding escalated to Medical Monitor and Sponsor QA.",
                "created_at": now - timedelta(days=14),
            },
            {
                "id": "GCP-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "investigator_name": "Dr. Karen Liu",
                "compliance_result": ComplianceResult.COMPLIANT,
                "check_date": now - timedelta(days=55),
                "gcp_area": "Data Recording",
                "finding_description": None,
                "corrective_action": None,
                "corrective_action_due": None,
                "corrective_action_completed": None,
                "verified_by": "Jennifer Park, CRA",
                "assessed_by": "QA Team Lead",
                "notes": "Data entry timely and accurate. Source verification complete.",
                "created_at": now - timedelta(days=54),
            },
            {
                "id": "GCP-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "investigator_name": "Dr. Karen Liu",
                "compliance_result": ComplianceResult.COMPLIANT,
                "check_date": now - timedelta(days=15),
                "gcp_area": "Safety Reporting",
                "finding_description": None,
                "corrective_action": None,
                "corrective_action_due": None,
                "corrective_action_completed": None,
                "verified_by": "Jennifer Park, CRA",
                "assessed_by": "QA Team Lead",
                "notes": "All SAEs reported within 24 hours. Documentation complete.",
                "created_at": now - timedelta(days=14),
            },
            {
                "id": "GCP-007",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-BOS-001",
                "investigator_name": "Dr. Robert Kim",
                "compliance_result": ComplianceResult.MAJOR_FINDING,
                "check_date": now - timedelta(days=40),
                "gcp_area": "Informed Consent",
                "finding_description": "ICF signed but not dated by investigator for 3 subjects.",
                "corrective_action": "Obtain dated signatures. Implement ICF completion checklist.",
                "corrective_action_due": now - timedelta(days=25),
                "corrective_action_completed": now - timedelta(days=28),
                "verified_by": "Jennifer Park, CRA",
                "assessed_by": "Sr. QA Auditor",
                "notes": "Finding remediated. Checklist implemented for all future consents.",
                "created_at": now - timedelta(days=39),
            },
            {
                "id": "GCP-008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-BOS-001",
                "investigator_name": "Dr. Robert Kim",
                "compliance_result": ComplianceResult.CRITICAL_FINDING,
                "check_date": now - timedelta(days=10),
                "gcp_area": "Subject Safety",
                "finding_description": "Eligibility criteria not met for 2 subjects. Subjects enrolled despite exclusion criterion present.",
                "corrective_action": "Medical review of affected subjects. Implement independent eligibility verification.",
                "corrective_action_due": now + timedelta(days=5),
                "corrective_action_completed": None,
                "verified_by": None,
                "assessed_by": "Sr. QA Auditor",
                "notes": "Critical subject safety finding. Medical Monitor notified. May require IRB reporting.",
                "created_at": now - timedelta(days=9),
            },
            {
                "id": "GCP-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-HOU-001",
                "investigator_name": "Dr. Angela Martinez",
                "compliance_result": ComplianceResult.COMPLIANT,
                "check_date": now - timedelta(days=50),
                "gcp_area": "Investigational Product",
                "finding_description": None,
                "corrective_action": None,
                "corrective_action_due": None,
                "corrective_action_completed": None,
                "verified_by": "David Kim, CRA",
                "assessed_by": "QA Team Lead",
                "notes": "IP accountability log current. Storage conditions verified. Dispensing accurate.",
                "created_at": now - timedelta(days=49),
            },
            {
                "id": "GCP-010",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-HOU-001",
                "investigator_name": "Dr. Angela Martinez",
                "compliance_result": ComplianceResult.REMEDIATED,
                "check_date": now - timedelta(days=10),
                "gcp_area": "Essential Documents",
                "finding_description": "Lab certification expired by 2 weeks before renewal obtained.",
                "corrective_action": "Implement certification expiry tracking system with 60-day advance alerts.",
                "corrective_action_due": now - timedelta(days=5),
                "corrective_action_completed": now - timedelta(days=7),
                "verified_by": "David Kim, CRA",
                "assessed_by": "QA Team Lead",
                "notes": "Finding remediated. Automated tracking system now in place.",
                "created_at": now - timedelta(days=9),
            },
            {
                "id": "GCP-011",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-SEA-001",
                "investigator_name": "Dr. Thomas Wright",
                "compliance_result": ComplianceResult.MAJOR_FINDING,
                "check_date": now - timedelta(days=35),
                "gcp_area": "Data Recording",
                "finding_description": "Source data missing for 5 subjects across multiple visits. CRF entries without corresponding source.",
                "corrective_action": "Reconstruct source documentation. Retrain staff on source data requirements.",
                "corrective_action_due": now + timedelta(days=15),
                "corrective_action_completed": None,
                "verified_by": None,
                "assessed_by": "Sr. QA Auditor",
                "notes": "Significant source data gaps. Data integrity concern. Audit trail review initiated.",
                "created_at": now - timedelta(days=34),
            },
            {
                "id": "GCP-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-SEA-001",
                "investigator_name": "Dr. Thomas Wright",
                "compliance_result": ComplianceResult.NOT_ASSESSED,
                "check_date": now - timedelta(days=5),
                "gcp_area": "Safety Reporting",
                "finding_description": None,
                "corrective_action": None,
                "corrective_action_due": None,
                "corrective_action_completed": None,
                "verified_by": None,
                "assessed_by": "David Kim, CRA",
                "notes": "Assessment scheduled but deferred pending resolution of data recording findings.",
                "created_at": now - timedelta(days=4),
            },
        ]

        for c in compliance_data:
            self._gcp_compliance_checks[c["id"]] = GCPComplianceCheck(**c)

        # --- 12 Investigator Communication Records ---
        communication_data = [
            {
                "id": "IC-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "investigator_name": "Dr. Sarah Chen",
                "communication_type": CommunicationType.PROTOCOL_UPDATE,
                "communication_status": CommunicationStatus.ACKNOWLEDGED,
                "subject_line": "Protocol Amendment 3 - Updated Eligibility Criteria",
                "content_summary": "Amendment 3 modifies inclusion criterion 5 to expand age range from 18-75 to 18-80.",
                "sent_date": now - timedelta(days=45),
                "acknowledged_date": now - timedelta(days=43),
                "sent_by": "Clinical Operations Lead",
                "response_required": True,
                "response_deadline": now - timedelta(days=30),
                "distribution_count": 1,
                "notes": "Acknowledged within 48 hours. Site implementing changes.",
                "created_at": now - timedelta(days=46),
            },
            {
                "id": "IC-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": None,
                "investigator_name": None,
                "communication_type": CommunicationType.SAFETY_ALERT,
                "communication_status": CommunicationStatus.DELIVERED,
                "subject_line": "Urgent Safety Alert - New Contraindication Identified",
                "content_summary": "New safety signal identified requiring immediate assessment of all enrolled subjects for hepatic function.",
                "sent_date": now - timedelta(days=10),
                "acknowledged_date": None,
                "sent_by": "Medical Monitor",
                "response_required": True,
                "response_deadline": now - timedelta(days=3),
                "distribution_count": 15,
                "notes": "Broadcast to all sites. Acknowledgment tracking in progress.",
                "created_at": now - timedelta(days=11),
            },
            {
                "id": "IC-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-LA-001",
                "investigator_name": "Dr. Michael Torres",
                "communication_type": CommunicationType.REGULATORY_NOTICE,
                "communication_status": CommunicationStatus.READ,
                "subject_line": "IRB Annual Review Deadline Reminder",
                "content_summary": "Annual IRB continuing review is due in 30 days. Please submit renewal documentation.",
                "sent_date": now - timedelta(days=30),
                "acknowledged_date": None,
                "sent_by": "Regulatory Affairs Manager",
                "response_required": True,
                "response_deadline": now,
                "distribution_count": 1,
                "notes": "Read but not yet acknowledged. Follow-up sent.",
                "created_at": now - timedelta(days=31),
            },
            {
                "id": "IC-004",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-LA-001",
                "investigator_name": "Dr. Michael Torres",
                "communication_type": CommunicationType.TRAINING_REMINDER,
                "communication_status": CommunicationStatus.SENT,
                "subject_line": "Mandatory Retraining - Protocol Deviation Prevention",
                "content_summary": "Site-specific retraining required following for-cause monitoring visit findings.",
                "sent_date": now - timedelta(days=5),
                "acknowledged_date": None,
                "sent_by": "Clinical Operations Lead",
                "response_required": True,
                "response_deadline": now + timedelta(days=10),
                "distribution_count": 1,
                "notes": "Retraining materials attached. Completion certificate required.",
                "created_at": now - timedelta(days=6),
            },
            {
                "id": "IC-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "investigator_name": "Dr. Karen Liu",
                "communication_type": CommunicationType.ENROLLMENT_STATUS,
                "communication_status": CommunicationStatus.ACKNOWLEDGED,
                "subject_line": "Monthly Enrollment Update - Dupixent Trial",
                "content_summary": "Site CHI-001 has exceeded enrollment target by 25%. Congratulations on outstanding recruitment.",
                "sent_date": now - timedelta(days=15),
                "acknowledged_date": now - timedelta(days=14),
                "sent_by": "Clinical Operations Lead",
                "response_required": False,
                "response_deadline": None,
                "distribution_count": 1,
                "notes": "Positive feedback communicated. Site recognized in sponsor newsletter.",
                "created_at": now - timedelta(days=16),
            },
            {
                "id": "IC-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": None,
                "investigator_name": None,
                "communication_type": CommunicationType.PROTOCOL_UPDATE,
                "communication_status": CommunicationStatus.ACKNOWLEDGED,
                "subject_line": "Protocol Clarification Memo - Visit Window Flexibility",
                "content_summary": "Clarification on acceptable visit windows for subjects with scheduling conflicts due to holidays.",
                "sent_date": now - timedelta(days=25),
                "acknowledged_date": now - timedelta(days=20),
                "sent_by": "Medical Director",
                "response_required": True,
                "response_deadline": now - timedelta(days=10),
                "distribution_count": 12,
                "notes": "All sites acknowledged. No questions received.",
                "created_at": now - timedelta(days=26),
            },
            {
                "id": "IC-007",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-BOS-001",
                "investigator_name": "Dr. Robert Kim",
                "communication_type": CommunicationType.SAFETY_ALERT,
                "communication_status": CommunicationStatus.FAILED,
                "subject_line": "Site-Specific Safety Review Required",
                "content_summary": "Review of all enrolled subjects required following identification of potential eligibility violations.",
                "sent_date": now - timedelta(days=8),
                "acknowledged_date": None,
                "sent_by": "Medical Monitor",
                "response_required": True,
                "response_deadline": now - timedelta(days=1),
                "distribution_count": 1,
                "notes": "Email delivery failed. Alternate contact attempted. Phone follow-up completed.",
                "created_at": now - timedelta(days=9),
            },
            {
                "id": "IC-008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-BOS-001",
                "investigator_name": "Dr. Robert Kim",
                "communication_type": CommunicationType.GENERAL_CORRESPONDENCE,
                "communication_status": CommunicationStatus.DRAFT,
                "subject_line": "Site Performance Improvement Plan - Action Required",
                "content_summary": "Formal notification of performance improvement plan requirements following for-cause visit.",
                "sent_date": None,
                "acknowledged_date": None,
                "sent_by": "Clinical Operations Director",
                "response_required": True,
                "response_deadline": None,
                "distribution_count": 0,
                "notes": "Draft pending legal and medical review before issuance.",
                "created_at": now - timedelta(days=2),
            },
            {
                "id": "IC-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-HOU-001",
                "investigator_name": "Dr. Angela Martinez",
                "communication_type": CommunicationType.ENROLLMENT_STATUS,
                "communication_status": CommunicationStatus.ACKNOWLEDGED,
                "subject_line": "Enrollment Milestone Achievement - 100th Subject",
                "content_summary": "Trial has reached 100-subject enrollment milestone. Site HOU-001 contributed 15 subjects.",
                "sent_date": now - timedelta(days=20),
                "acknowledged_date": now - timedelta(days=19),
                "sent_by": "Program Director",
                "response_required": False,
                "response_deadline": None,
                "distribution_count": 1,
                "notes": "Milestone celebration communication. Investigator appreciation acknowledged.",
                "created_at": now - timedelta(days=21),
            },
            {
                "id": "IC-010",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": None,
                "investigator_name": None,
                "communication_type": CommunicationType.REGULATORY_NOTICE,
                "communication_status": CommunicationStatus.DELIVERED,
                "subject_line": "FDA Annual IND Update - Information Request",
                "content_summary": "Annual IND update requires site-specific enrollment and safety data. Submission due in 60 days.",
                "sent_date": now - timedelta(days=5),
                "acknowledged_date": None,
                "sent_by": "Regulatory Affairs Director",
                "response_required": True,
                "response_deadline": now + timedelta(days=55),
                "distribution_count": 8,
                "notes": "Data collection template attached. Sites to submit within 30 days.",
                "created_at": now - timedelta(days=6),
            },
            {
                "id": "IC-011",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-SEA-001",
                "investigator_name": "Dr. Thomas Wright",
                "communication_type": CommunicationType.TRAINING_REMINDER,
                "communication_status": CommunicationStatus.SENT,
                "subject_line": "Overdue GCP Training Certification",
                "content_summary": "GCP certification has expired. Recertification required within 14 days to maintain site eligibility.",
                "sent_date": now - timedelta(days=7),
                "acknowledged_date": None,
                "sent_by": "Training Coordinator",
                "response_required": True,
                "response_deadline": now + timedelta(days=7),
                "distribution_count": 1,
                "notes": "Second reminder sent. Escalation to site director if not completed.",
                "created_at": now - timedelta(days=8),
            },
            {
                "id": "IC-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-SEA-001",
                "investigator_name": "Dr. Thomas Wright",
                "communication_type": CommunicationType.GENERAL_CORRESPONDENCE,
                "communication_status": CommunicationStatus.SENT,
                "subject_line": "Corrective Action Plan Follow-Up",
                "content_summary": "Follow-up on outstanding corrective actions from triggered monitoring visit. Status update requested.",
                "sent_date": now - timedelta(days=3),
                "acknowledged_date": None,
                "sent_by": "Clinical Operations Lead",
                "response_required": True,
                "response_deadline": now + timedelta(days=7),
                "distribution_count": 1,
                "notes": "Third request for status update. Escalation path initiated.",
                "created_at": now - timedelta(days=4),
            },
        ]

        for comm in communication_data:
            self._investigator_communications[comm["id"]] = InvestigatorCommunication(**comm)

    # ------------------------------------------------------------------
    # Investigator Performances
    # ------------------------------------------------------------------

    def list_investigator_performances(
        self,
        *,
        trial_id: str | None = None,
        performance_rating: PerformanceRating | None = None,
        site_id: str | None = None,
    ) -> list[InvestigatorPerformance]:
        """List investigator performances with optional filters."""
        with self._lock:
            result = list(self._investigator_performances.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if performance_rating is not None:
            result = [r for r in result if r.performance_rating == performance_rating]
        if site_id is not None:
            result = [r for r in result if r.site_id == site_id]

        return sorted(result, key=lambda r: r.review_period_end, reverse=True)

    def get_investigator_performance(self, perf_id: str) -> InvestigatorPerformance | None:
        """Get a single investigator performance record by ID."""
        with self._lock:
            return self._investigator_performances.get(perf_id)

    def create_investigator_performance(
        self, payload: InvestigatorPerformanceCreate
    ) -> InvestigatorPerformance:
        """Create a new investigator performance record."""
        now = datetime.now(timezone.utc)
        perf_id = f"IP-{uuid4().hex[:8].upper()}"
        record = InvestigatorPerformance(
            id=perf_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            investigator_name=payload.investigator_name,
            performance_rating=PerformanceRating.NOT_EVALUATED,
            review_period_start=payload.review_period_start,
            review_period_end=payload.review_period_end,
            enrollment_target=payload.enrollment_target,
            enrollment_actual=0,
            protocol_deviations=0,
            query_response_days=0.0,
            sae_reporting_compliance_pct=100.0,
            training_completion_pct=100.0,
            reviewed_by=payload.reviewed_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._investigator_performances[perf_id] = record
        logger.info("Created investigator performance %s for trial %s", perf_id, payload.trial_id)
        return record

    def update_investigator_performance(
        self, perf_id: str, payload: InvestigatorPerformanceUpdate
    ) -> InvestigatorPerformance | None:
        """Update an existing investigator performance record."""
        with self._lock:
            existing = self._investigator_performances.get(perf_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = InvestigatorPerformance(**data)
            self._investigator_performances[perf_id] = updated
        return updated

    def delete_investigator_performance(self, perf_id: str) -> bool:
        """Delete an investigator performance record. Returns True if deleted."""
        with self._lock:
            if perf_id in self._investigator_performances:
                del self._investigator_performances[perf_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Site Supervisions
    # ------------------------------------------------------------------

    def list_site_supervisions(
        self,
        *,
        trial_id: str | None = None,
        supervision_type: SupervisionType | None = None,
        site_id: str | None = None,
    ) -> list[SiteSupervision]:
        """List site supervisions with optional filters."""
        with self._lock:
            result = list(self._site_supervisions.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if supervision_type is not None:
            result = [s for s in result if s.supervision_type == supervision_type]
        if site_id is not None:
            result = [s for s in result if s.site_id == site_id]

        return sorted(result, key=lambda s: s.visit_date, reverse=True)

    def get_site_supervision(self, supervision_id: str) -> SiteSupervision | None:
        """Get a single site supervision record by ID."""
        with self._lock:
            return self._site_supervisions.get(supervision_id)

    def create_site_supervision(self, payload: SiteSupervisionCreate) -> SiteSupervision:
        """Create a new site supervision record."""
        now = datetime.now(timezone.utc)
        supervision_id = f"SS-{uuid4().hex[:8].upper()}"
        record = SiteSupervision(
            id=supervision_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            supervision_type=payload.supervision_type,
            visit_date=payload.visit_date,
            monitor_name=payload.monitor_name,
            duration_hours=payload.duration_hours,
            findings_count=0,
            critical_findings=0,
            action_items_generated=0,
            action_items_resolved=0,
            report_finalized=False,
            follow_up_required=False,
            follow_up_date=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._site_supervisions[supervision_id] = record
        logger.info("Created site supervision %s for trial %s", supervision_id, payload.trial_id)
        return record

    def update_site_supervision(
        self, supervision_id: str, payload: SiteSupervisionUpdate
    ) -> SiteSupervision | None:
        """Update an existing site supervision record."""
        with self._lock:
            existing = self._site_supervisions.get(supervision_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = SiteSupervision(**data)
            self._site_supervisions[supervision_id] = updated
        return updated

    def delete_site_supervision(self, supervision_id: str) -> bool:
        """Delete a site supervision record. Returns True if deleted."""
        with self._lock:
            if supervision_id in self._site_supervisions:
                del self._site_supervisions[supervision_id]
                return True
            return False

    # ------------------------------------------------------------------
    # GCP Compliance Checks
    # ------------------------------------------------------------------

    def list_gcp_compliance_checks(
        self,
        *,
        trial_id: str | None = None,
        compliance_result: ComplianceResult | None = None,
        site_id: str | None = None,
    ) -> list[GCPComplianceCheck]:
        """List GCP compliance checks with optional filters."""
        with self._lock:
            result = list(self._gcp_compliance_checks.values())

        if trial_id is not None:
            result = [c for c in result if c.trial_id == trial_id]
        if compliance_result is not None:
            result = [c for c in result if c.compliance_result == compliance_result]
        if site_id is not None:
            result = [c for c in result if c.site_id == site_id]

        return sorted(result, key=lambda c: c.check_date, reverse=True)

    def get_gcp_compliance_check(self, check_id: str) -> GCPComplianceCheck | None:
        """Get a single GCP compliance check by ID."""
        with self._lock:
            return self._gcp_compliance_checks.get(check_id)

    def create_gcp_compliance_check(
        self, payload: GCPComplianceCheckCreate
    ) -> GCPComplianceCheck:
        """Create a new GCP compliance check."""
        now = datetime.now(timezone.utc)
        check_id = f"GCP-{uuid4().hex[:8].upper()}"
        record = GCPComplianceCheck(
            id=check_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            investigator_name=payload.investigator_name,
            compliance_result=ComplianceResult.NOT_ASSESSED,
            check_date=payload.check_date,
            gcp_area=payload.gcp_area,
            finding_description=None,
            corrective_action=None,
            corrective_action_due=None,
            corrective_action_completed=None,
            verified_by=None,
            assessed_by=payload.assessed_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._gcp_compliance_checks[check_id] = record
        logger.info("Created GCP compliance check %s for trial %s", check_id, payload.trial_id)
        return record

    def update_gcp_compliance_check(
        self, check_id: str, payload: GCPComplianceCheckUpdate
    ) -> GCPComplianceCheck | None:
        """Update an existing GCP compliance check."""
        with self._lock:
            existing = self._gcp_compliance_checks.get(check_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = GCPComplianceCheck(**data)
            self._gcp_compliance_checks[check_id] = updated
        return updated

    def delete_gcp_compliance_check(self, check_id: str) -> bool:
        """Delete a GCP compliance check. Returns True if deleted."""
        with self._lock:
            if check_id in self._gcp_compliance_checks:
                del self._gcp_compliance_checks[check_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Investigator Communications
    # ------------------------------------------------------------------

    def list_investigator_communications(
        self,
        *,
        trial_id: str | None = None,
        communication_type: CommunicationType | None = None,
        communication_status: CommunicationStatus | None = None,
    ) -> list[InvestigatorCommunication]:
        """List investigator communications with optional filters."""
        with self._lock:
            result = list(self._investigator_communications.values())

        if trial_id is not None:
            result = [c for c in result if c.trial_id == trial_id]
        if communication_type is not None:
            result = [c for c in result if c.communication_type == communication_type]
        if communication_status is not None:
            result = [c for c in result if c.communication_status == communication_status]

        return sorted(result, key=lambda c: c.created_at, reverse=True)

    def get_investigator_communication(self, comm_id: str) -> InvestigatorCommunication | None:
        """Get a single investigator communication by ID."""
        with self._lock:
            return self._investigator_communications.get(comm_id)

    def create_investigator_communication(
        self, payload: InvestigatorCommunicationCreate
    ) -> InvestigatorCommunication:
        """Create a new investigator communication."""
        now = datetime.now(timezone.utc)
        comm_id = f"IC-{uuid4().hex[:8].upper()}"
        record = InvestigatorCommunication(
            id=comm_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            investigator_name=payload.investigator_name,
            communication_type=payload.communication_type,
            communication_status=CommunicationStatus.DRAFT,
            subject_line=payload.subject_line,
            content_summary=payload.content_summary,
            sent_date=None,
            acknowledged_date=None,
            sent_by=payload.sent_by,
            response_required=False,
            response_deadline=None,
            distribution_count=0,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._investigator_communications[comm_id] = record
        logger.info("Created investigator communication %s for trial %s", comm_id, payload.trial_id)
        return record

    def update_investigator_communication(
        self, comm_id: str, payload: InvestigatorCommunicationUpdate
    ) -> InvestigatorCommunication | None:
        """Update an existing investigator communication."""
        with self._lock:
            existing = self._investigator_communications.get(comm_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = InvestigatorCommunication(**data)
            self._investigator_communications[comm_id] = updated
        return updated

    def delete_investigator_communication(self, comm_id: str) -> bool:
        """Delete an investigator communication. Returns True if deleted."""
        with self._lock:
            if comm_id in self._investigator_communications:
                del self._investigator_communications[comm_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> InvestigatorOversightMetrics:
        """Compute aggregated investigator oversight metrics."""
        with self._lock:
            performances = list(self._investigator_performances.values())
            supervisions = list(self._site_supervisions.values())
            compliance = list(self._gcp_compliance_checks.values())
            communications = list(self._investigator_communications.values())

        # Reviews by rating
        reviews_by_rating: dict[str, int] = {}
        for p in performances:
            key = p.performance_rating.value
            reviews_by_rating[key] = reviews_by_rating.get(key, 0) + 1

        # Average enrollment achievement
        achievement_pcts = []
        for p in performances:
            if p.enrollment_target > 0:
                achievement_pcts.append(
                    (p.enrollment_actual / p.enrollment_target) * 100
                )
        avg_enrollment_achievement = round(
            sum(achievement_pcts) / max(1, len(achievement_pcts)), 1
        )

        # Supervisions by type
        supervisions_by_type: dict[str, int] = {}
        for s in supervisions:
            key = s.supervision_type.value
            supervisions_by_type[key] = supervisions_by_type.get(key, 0) + 1

        # Compliance checks by result
        checks_by_result: dict[str, int] = {}
        for c in compliance:
            key = c.compliance_result.value
            checks_by_result[key] = checks_by_result.get(key, 0) + 1

        # Compliance rate (compliant + remediated / assessed)
        assessed = [
            c for c in compliance
            if c.compliance_result != ComplianceResult.NOT_ASSESSED
        ]
        compliant_count = sum(
            1 for c in assessed
            if c.compliance_result in (ComplianceResult.COMPLIANT, ComplianceResult.REMEDIATED)
        )
        compliance_rate = round(
            (compliant_count / max(1, len(assessed))) * 100, 1
        )

        # Communications by type
        communications_by_type: dict[str, int] = {}
        for c in communications:
            key = c.communication_type.value
            communications_by_type[key] = communications_by_type.get(key, 0) + 1

        # Communication acknowledgment rate
        ack_eligible = [
            c for c in communications
            if c.communication_status not in (CommunicationStatus.DRAFT, CommunicationStatus.FAILED)
        ]
        acknowledged_count = sum(
            1 for c in ack_eligible
            if c.communication_status == CommunicationStatus.ACKNOWLEDGED
        )
        ack_rate = round(
            (acknowledged_count / max(1, len(ack_eligible))) * 100, 1
        )

        return InvestigatorOversightMetrics(
            total_performance_reviews=len(performances),
            reviews_by_rating=reviews_by_rating,
            avg_enrollment_achievement_pct=avg_enrollment_achievement,
            total_supervisions=len(supervisions),
            supervisions_by_type=supervisions_by_type,
            total_compliance_checks=len(compliance),
            checks_by_result=checks_by_result,
            compliance_rate=compliance_rate,
            total_communications=len(communications),
            communications_by_type=communications_by_type,
            communication_acknowledgment_rate=ack_rate,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: InvestigatorOversightService | None = None
_instance_lock = threading.Lock()


def get_investigator_oversight_service() -> InvestigatorOversightService:
    """Return the singleton InvestigatorOversightService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = InvestigatorOversightService()
    return _instance


def reset_investigator_oversight_service() -> InvestigatorOversightService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = InvestigatorOversightService()
    return _instance
