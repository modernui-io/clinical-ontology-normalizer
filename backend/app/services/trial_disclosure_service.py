"""Trial Disclosure Management Service (TRIAL-DISC).

Manages trial disclosure operations: results disclosure tracking,
registry submission records, publication mandates, lay summaries,
and compliance timeline management with disclosure metrics.

Usage:
    from app.services.trial_disclosure_service import (
        get_trial_disclosure_service,
    )

    svc = get_trial_disclosure_service()
    disclosures = svc.list_results_disclosures()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.trial_disclosure import (
    ComplianceTimeline,
    ComplianceTimelineCreate,
    ComplianceTimelineUpdate,
    DisclosureStatus,
    DisclosureType,
    LaySummary,
    LaySummaryCreate,
    LaySummaryUpdate,
    MandateType,
    PublicationMandate,
    PublicationMandateCreate,
    PublicationMandateUpdate,
    RegistryName,
    RegistrySubmission,
    RegistrySubmissionCreate,
    RegistrySubmissionUpdate,
    ResultsDisclosure,
    ResultsDisclosureCreate,
    ResultsDisclosureUpdate,
    SummaryAudience,
    TrialDisclosureMetrics,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class TrialDisclosureService:
    """In-memory Trial Disclosure Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._results_disclosures: dict[str, ResultsDisclosure] = {}
        self._registry_submissions: dict[str, RegistrySubmission] = {}
        self._publication_mandates: dict[str, PublicationMandate] = {}
        self._lay_summaries: dict[str, LaySummary] = {}
        self._compliance_timelines: dict[str, ComplianceTimeline] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic trial disclosure data."""
        now = datetime.now(timezone.utc)

        # --- 12 Results Disclosures ---
        disclosures_data = [
            {
                "id": "RD-001",
                "trial_id": EYLEA_TRIAL,
                "disclosure_type": DisclosureType.RESULTS_POSTING,
                "status": DisclosureStatus.POSTED,
                "registry_name": RegistryName.CLINICALTRIALS_GOV,
                "registry_id": "NCT04012345",
                "primary_completion_date": now - timedelta(days=365),
                "disclosure_deadline": now - timedelta(days=0),
                "submission_date": now - timedelta(days=30),
                "posting_date": now - timedelta(days=15),
                "days_to_deadline": 0,
                "days_overdue": 0,
                "results_summary_approved": True,
                "statistical_tables_included": True,
                "adverse_events_included": True,
                "protocol_amendments_noted": True,
                "prepared_by": "Dr. Sarah Chen",
                "approved_by": "Dr. William Torres",
                "notes": "Results posted on time to ClinicalTrials.gov.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "RD-002",
                "trial_id": EYLEA_TRIAL,
                "disclosure_type": DisclosureType.SUMMARY_REPORT,
                "status": DisclosureStatus.SUBMITTED,
                "registry_name": RegistryName.EUDRACT,
                "registry_id": "2021-001234-56",
                "primary_completion_date": now - timedelta(days=365),
                "disclosure_deadline": now - timedelta(days=0),
                "submission_date": now - timedelta(days=10),
                "posting_date": None,
                "days_to_deadline": 0,
                "days_overdue": 0,
                "results_summary_approved": True,
                "statistical_tables_included": True,
                "adverse_events_included": True,
                "protocol_amendments_noted": False,
                "prepared_by": "Dr. Sarah Chen",
                "approved_by": "Dr. William Torres",
                "notes": "Summary report submitted to EudraCT. Awaiting posting.",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "RD-003",
                "trial_id": EYLEA_TRIAL,
                "disclosure_type": DisclosureType.LAY_SUMMARY,
                "status": DisclosureStatus.IN_PREPARATION,
                "registry_name": None,
                "registry_id": None,
                "primary_completion_date": now - timedelta(days=365),
                "disclosure_deadline": now + timedelta(days=180),
                "submission_date": None,
                "posting_date": None,
                "days_to_deadline": 180,
                "days_overdue": 0,
                "results_summary_approved": False,
                "statistical_tables_included": False,
                "adverse_events_included": False,
                "protocol_amendments_noted": False,
                "prepared_by": "Dr. Emily Watson",
                "approved_by": None,
                "notes": "Lay summary in preparation for EU CTR requirement.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "RD-004",
                "trial_id": DUPIXENT_TRIAL,
                "disclosure_type": DisclosureType.RESULTS_POSTING,
                "status": DisclosureStatus.OVERDUE,
                "registry_name": RegistryName.CLINICALTRIALS_GOV,
                "registry_id": "NCT04056789",
                "primary_completion_date": now - timedelta(days=400),
                "disclosure_deadline": now - timedelta(days=35),
                "submission_date": None,
                "posting_date": None,
                "days_to_deadline": -35,
                "days_overdue": 35,
                "results_summary_approved": False,
                "statistical_tables_included": False,
                "adverse_events_included": False,
                "protocol_amendments_noted": False,
                "prepared_by": "Dr. Maria Lopez",
                "approved_by": None,
                "notes": "OVERDUE: ClinicalTrials.gov results posting past deadline.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "RD-005",
                "trial_id": DUPIXENT_TRIAL,
                "disclosure_type": DisclosureType.CSR_SYNOPSIS,
                "status": DisclosureStatus.UNDER_REVIEW,
                "registry_name": None,
                "registry_id": None,
                "primary_completion_date": now - timedelta(days=400),
                "disclosure_deadline": now + timedelta(days=60),
                "submission_date": None,
                "posting_date": None,
                "days_to_deadline": 60,
                "days_overdue": 0,
                "results_summary_approved": True,
                "statistical_tables_included": True,
                "adverse_events_included": True,
                "protocol_amendments_noted": True,
                "prepared_by": "Dr. Robert Kim",
                "approved_by": None,
                "notes": "CSR synopsis under medical writing review.",
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "RD-006",
                "trial_id": DUPIXENT_TRIAL,
                "disclosure_type": DisclosureType.REGISTRY_UPDATE,
                "status": DisclosureStatus.POSTED,
                "registry_name": RegistryName.CTIS,
                "registry_id": "EU/CT/2022/001234",
                "primary_completion_date": now - timedelta(days=400),
                "disclosure_deadline": now - timedelta(days=100),
                "submission_date": now - timedelta(days=120),
                "posting_date": now - timedelta(days=105),
                "days_to_deadline": 0,
                "days_overdue": 0,
                "results_summary_approved": True,
                "statistical_tables_included": False,
                "adverse_events_included": True,
                "protocol_amendments_noted": True,
                "prepared_by": "Dr. Maria Lopez",
                "approved_by": "Dr. David Patel",
                "notes": "CTIS registry update completed ahead of deadline.",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "RD-007",
                "trial_id": DUPIXENT_TRIAL,
                "disclosure_type": DisclosureType.PUBLICATION,
                "status": DisclosureStatus.PENDING,
                "registry_name": None,
                "registry_id": None,
                "primary_completion_date": now - timedelta(days=400),
                "disclosure_deadline": now + timedelta(days=120),
                "submission_date": None,
                "posting_date": None,
                "days_to_deadline": 120,
                "days_overdue": 0,
                "results_summary_approved": False,
                "statistical_tables_included": False,
                "adverse_events_included": False,
                "protocol_amendments_noted": False,
                "prepared_by": "Dr. Robert Kim",
                "approved_by": None,
                "notes": "Primary manuscript publication pending data lock.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "RD-008",
                "trial_id": LIBTAYO_TRIAL,
                "disclosure_type": DisclosureType.RESULTS_POSTING,
                "status": DisclosureStatus.PENDING,
                "registry_name": RegistryName.CLINICALTRIALS_GOV,
                "registry_id": "NCT04098765",
                "primary_completion_date": now - timedelta(days=200),
                "disclosure_deadline": now + timedelta(days=165),
                "submission_date": None,
                "posting_date": None,
                "days_to_deadline": 165,
                "days_overdue": 0,
                "results_summary_approved": False,
                "statistical_tables_included": False,
                "adverse_events_included": False,
                "protocol_amendments_noted": False,
                "prepared_by": "Dr. Angela Park",
                "approved_by": None,
                "notes": "Results posting planned after database lock.",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "RD-009",
                "trial_id": LIBTAYO_TRIAL,
                "disclosure_type": DisclosureType.SUMMARY_REPORT,
                "status": DisclosureStatus.NOT_DUE,
                "registry_name": RegistryName.JAPIC,
                "registry_id": "JapicCTI-225678",
                "primary_completion_date": now - timedelta(days=200),
                "disclosure_deadline": now + timedelta(days=200),
                "submission_date": None,
                "posting_date": None,
                "days_to_deadline": 200,
                "days_overdue": 0,
                "results_summary_approved": False,
                "statistical_tables_included": False,
                "adverse_events_included": False,
                "protocol_amendments_noted": False,
                "prepared_by": "Dr. Angela Park",
                "approved_by": None,
                "notes": "JAPIC summary report not yet due.",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "RD-010",
                "trial_id": LIBTAYO_TRIAL,
                "disclosure_type": DisclosureType.RESULTS_POSTING,
                "status": DisclosureStatus.OVERDUE,
                "registry_name": RegistryName.EUDRACT,
                "registry_id": "2022-003456-78",
                "primary_completion_date": now - timedelta(days=500),
                "disclosure_deadline": now - timedelta(days=135),
                "submission_date": None,
                "posting_date": None,
                "days_to_deadline": -135,
                "days_overdue": 135,
                "results_summary_approved": False,
                "statistical_tables_included": False,
                "adverse_events_included": False,
                "protocol_amendments_noted": False,
                "prepared_by": "Dr. James Wright",
                "approved_by": None,
                "notes": "OVERDUE: EudraCT results posting significantly past deadline.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "RD-011",
                "trial_id": EYLEA_TRIAL,
                "disclosure_type": DisclosureType.PUBLICATION,
                "status": DisclosureStatus.POSTED,
                "registry_name": None,
                "registry_id": None,
                "primary_completion_date": now - timedelta(days=365),
                "disclosure_deadline": now - timedelta(days=30),
                "submission_date": now - timedelta(days=90),
                "posting_date": now - timedelta(days=45),
                "days_to_deadline": 0,
                "days_overdue": 0,
                "results_summary_approved": True,
                "statistical_tables_included": True,
                "adverse_events_included": True,
                "protocol_amendments_noted": True,
                "prepared_by": "Dr. Sarah Chen",
                "approved_by": "Dr. William Torres",
                "notes": "Primary publication in NEJM.",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "RD-012",
                "trial_id": LIBTAYO_TRIAL,
                "disclosure_type": DisclosureType.CSR_SYNOPSIS,
                "status": DisclosureStatus.IN_PREPARATION,
                "registry_name": None,
                "registry_id": None,
                "primary_completion_date": now - timedelta(days=200),
                "disclosure_deadline": now + timedelta(days=90),
                "submission_date": None,
                "posting_date": None,
                "days_to_deadline": 90,
                "days_overdue": 0,
                "results_summary_approved": False,
                "statistical_tables_included": False,
                "adverse_events_included": False,
                "protocol_amendments_noted": False,
                "prepared_by": "Dr. Angela Park",
                "approved_by": None,
                "notes": "CSR synopsis draft in progress.",
                "created_at": now - timedelta(days=5),
            },
        ]

        for d in disclosures_data:
            self._results_disclosures[d["id"]] = ResultsDisclosure(**d)

        # --- 12 Registry Submissions ---
        submissions_data = [
            {
                "id": "RS-001",
                "trial_id": EYLEA_TRIAL,
                "registry_name": RegistryName.CLINICALTRIALS_GOV,
                "registry_id": "NCT04012345",
                "submission_type": "initial",
                "submission_date": now - timedelta(days=730),
                "acknowledgment_date": now - timedelta(days=725),
                "acceptance_date": now - timedelta(days=720),
                "rejection_reason": None,
                "protocol_version_submitted": "1.0",
                "amendments_included": 0,
                "qc_passed": True,
                "prs_review_status": "accepted",
                "submitted_by": "Dr. Sarah Chen",
                "reviewer": "PRS Team Lead",
                "notes": "Initial registration accepted.",
                "created_at": now - timedelta(days=730),
            },
            {
                "id": "RS-002",
                "trial_id": EYLEA_TRIAL,
                "registry_name": RegistryName.CLINICALTRIALS_GOV,
                "registry_id": "NCT04012345",
                "submission_type": "amendment",
                "submission_date": now - timedelta(days=500),
                "acknowledgment_date": now - timedelta(days=498),
                "acceptance_date": now - timedelta(days=490),
                "rejection_reason": None,
                "protocol_version_submitted": "2.0",
                "amendments_included": 1,
                "qc_passed": True,
                "prs_review_status": "accepted",
                "submitted_by": "Dr. Sarah Chen",
                "reviewer": "PRS Team Lead",
                "notes": "Protocol amendment 1 submitted.",
                "created_at": now - timedelta(days=500),
            },
            {
                "id": "RS-003",
                "trial_id": EYLEA_TRIAL,
                "registry_name": RegistryName.EUDRACT,
                "registry_id": "2021-001234-56",
                "submission_type": "initial",
                "submission_date": now - timedelta(days=720),
                "acknowledgment_date": now - timedelta(days=710),
                "acceptance_date": now - timedelta(days=700),
                "rejection_reason": None,
                "protocol_version_submitted": "1.0",
                "amendments_included": 0,
                "qc_passed": True,
                "prs_review_status": "accepted",
                "submitted_by": "Dr. Emily Watson",
                "reviewer": "EU Regulatory",
                "notes": "EudraCT initial registration.",
                "created_at": now - timedelta(days=720),
            },
            {
                "id": "RS-004",
                "trial_id": DUPIXENT_TRIAL,
                "registry_name": RegistryName.CLINICALTRIALS_GOV,
                "registry_id": "NCT04056789",
                "submission_type": "initial",
                "submission_date": now - timedelta(days=600),
                "acknowledgment_date": now - timedelta(days=595),
                "acceptance_date": now - timedelta(days=585),
                "rejection_reason": None,
                "protocol_version_submitted": "1.0",
                "amendments_included": 0,
                "qc_passed": True,
                "prs_review_status": "accepted",
                "submitted_by": "Dr. Maria Lopez",
                "reviewer": "PRS Team Lead",
                "notes": "Initial DUPIXENT trial registration.",
                "created_at": now - timedelta(days=600),
            },
            {
                "id": "RS-005",
                "trial_id": DUPIXENT_TRIAL,
                "registry_name": RegistryName.CTIS,
                "registry_id": "EU/CT/2022/001234",
                "submission_type": "initial",
                "submission_date": now - timedelta(days=580),
                "acknowledgment_date": now - timedelta(days=575),
                "acceptance_date": now - timedelta(days=560),
                "rejection_reason": None,
                "protocol_version_submitted": "1.0",
                "amendments_included": 0,
                "qc_passed": True,
                "prs_review_status": "validated",
                "submitted_by": "Dr. Maria Lopez",
                "reviewer": "CTIS Assessor",
                "notes": "CTIS initial submission validated.",
                "created_at": now - timedelta(days=580),
            },
            {
                "id": "RS-006",
                "trial_id": DUPIXENT_TRIAL,
                "registry_name": RegistryName.CLINICALTRIALS_GOV,
                "registry_id": "NCT04056789",
                "submission_type": "results",
                "submission_date": now - timedelta(days=5),
                "acknowledgment_date": None,
                "acceptance_date": None,
                "rejection_reason": None,
                "protocol_version_submitted": "3.0",
                "amendments_included": 2,
                "qc_passed": False,
                "prs_review_status": "pending_review",
                "submitted_by": "Dr. Robert Kim",
                "reviewer": None,
                "notes": "Results submission pending PRS review.",
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "RS-007",
                "trial_id": LIBTAYO_TRIAL,
                "registry_name": RegistryName.CLINICALTRIALS_GOV,
                "registry_id": "NCT04098765",
                "submission_type": "initial",
                "submission_date": now - timedelta(days=500),
                "acknowledgment_date": now - timedelta(days=497),
                "acceptance_date": now - timedelta(days=490),
                "rejection_reason": None,
                "protocol_version_submitted": "1.0",
                "amendments_included": 0,
                "qc_passed": True,
                "prs_review_status": "accepted",
                "submitted_by": "Dr. Angela Park",
                "reviewer": "PRS Team Lead",
                "notes": "LIBTAYO trial initial registration.",
                "created_at": now - timedelta(days=500),
            },
            {
                "id": "RS-008",
                "trial_id": LIBTAYO_TRIAL,
                "registry_name": RegistryName.EUDRACT,
                "registry_id": "2022-003456-78",
                "submission_type": "initial",
                "submission_date": now - timedelta(days=490),
                "acknowledgment_date": now - timedelta(days=485),
                "acceptance_date": now - timedelta(days=475),
                "rejection_reason": None,
                "protocol_version_submitted": "1.0",
                "amendments_included": 0,
                "qc_passed": True,
                "prs_review_status": "accepted",
                "submitted_by": "Dr. Angela Park",
                "reviewer": "EU Regulatory",
                "notes": "EudraCT registration for LIBTAYO.",
                "created_at": now - timedelta(days=490),
            },
            {
                "id": "RS-009",
                "trial_id": LIBTAYO_TRIAL,
                "registry_name": RegistryName.JAPIC,
                "registry_id": "JapicCTI-225678",
                "submission_type": "initial",
                "submission_date": now - timedelta(days=480),
                "acknowledgment_date": now - timedelta(days=475),
                "acceptance_date": now - timedelta(days=465),
                "rejection_reason": None,
                "protocol_version_submitted": "1.0",
                "amendments_included": 0,
                "qc_passed": True,
                "prs_review_status": "accepted",
                "submitted_by": "Dr. James Wright",
                "reviewer": "JAPIC Reviewer",
                "notes": "JAPIC registration for Japan sites.",
                "created_at": now - timedelta(days=480),
            },
            {
                "id": "RS-010",
                "trial_id": LIBTAYO_TRIAL,
                "registry_name": RegistryName.CLINICALTRIALS_GOV,
                "registry_id": "NCT04098765",
                "submission_type": "amendment",
                "submission_date": now - timedelta(days=300),
                "acknowledgment_date": now - timedelta(days=298),
                "acceptance_date": None,
                "rejection_reason": "Incomplete SAE reporting table",
                "protocol_version_submitted": "2.0",
                "amendments_included": 1,
                "qc_passed": False,
                "prs_review_status": "rejected",
                "submitted_by": "Dr. Angela Park",
                "reviewer": "PRS Team Lead",
                "notes": "Rejected due to incomplete SAE data. Resubmission needed.",
                "created_at": now - timedelta(days=300),
            },
            {
                "id": "RS-011",
                "trial_id": EYLEA_TRIAL,
                "registry_name": RegistryName.ANZCTR,
                "registry_id": "ACTRN12621001234",
                "submission_type": "initial",
                "submission_date": now - timedelta(days=700),
                "acknowledgment_date": now - timedelta(days=695),
                "acceptance_date": now - timedelta(days=688),
                "rejection_reason": None,
                "protocol_version_submitted": "1.0",
                "amendments_included": 0,
                "qc_passed": True,
                "prs_review_status": "accepted",
                "submitted_by": "Dr. Emily Watson",
                "reviewer": "ANZCTR Reviewer",
                "notes": "Australia/NZ registration for EYLEA trial.",
                "created_at": now - timedelta(days=700),
            },
            {
                "id": "RS-012",
                "trial_id": DUPIXENT_TRIAL,
                "registry_name": RegistryName.ISRCTN,
                "registry_id": "ISRCTN12345678",
                "submission_type": "initial",
                "submission_date": now - timedelta(days=570),
                "acknowledgment_date": now - timedelta(days=565),
                "acceptance_date": now - timedelta(days=555),
                "rejection_reason": None,
                "protocol_version_submitted": "1.0",
                "amendments_included": 0,
                "qc_passed": True,
                "prs_review_status": "accepted",
                "submitted_by": "Dr. Maria Lopez",
                "reviewer": "ISRCTN Assessor",
                "notes": "ISRCTN registration for UK sites.",
                "created_at": now - timedelta(days=570),
            },
        ]

        for s in submissions_data:
            self._registry_submissions[s["id"]] = RegistrySubmission(**s)

        # --- 12 Publication Mandates ---
        mandates_data = [
            {
                "id": "PM-001",
                "trial_id": EYLEA_TRIAL,
                "mandate_type": MandateType.FDAAA_801,
                "regulation_reference": "42 USC 282(j)(3)(C)",
                "deadline_months_from_completion": 12,
                "applicable": True,
                "exemption_claimed": False,
                "exemption_reason": None,
                "exemption_approved": False,
                "compliance_status": "compliant",
                "penalty_risk": "none",
                "penalty_amount": None,
                "responsible_party": "Dr. William Torres",
                "legal_review_required": False,
                "legal_reviewed": True,
                "notes": "Results posted within 12-month FDAAA 801 deadline.",
                "created_at": now - timedelta(days=400),
            },
            {
                "id": "PM-002",
                "trial_id": EYLEA_TRIAL,
                "mandate_type": MandateType.EU_CTR,
                "regulation_reference": "EU CTR Article 37",
                "deadline_months_from_completion": 12,
                "applicable": True,
                "exemption_claimed": False,
                "exemption_reason": None,
                "exemption_approved": False,
                "compliance_status": "on_track",
                "penalty_risk": "low",
                "penalty_amount": None,
                "responsible_party": "Dr. Emily Watson",
                "legal_review_required": True,
                "legal_reviewed": True,
                "notes": "EU CTR lay summary in preparation.",
                "created_at": now - timedelta(days=380),
            },
            {
                "id": "PM-003",
                "trial_id": EYLEA_TRIAL,
                "mandate_type": MandateType.ICMJE,
                "regulation_reference": "ICMJE Policy 2019",
                "deadline_months_from_completion": 24,
                "applicable": True,
                "exemption_claimed": False,
                "exemption_reason": None,
                "exemption_approved": False,
                "compliance_status": "compliant",
                "penalty_risk": "none",
                "penalty_amount": None,
                "responsible_party": "Dr. Sarah Chen",
                "legal_review_required": False,
                "legal_reviewed": False,
                "notes": "Publication submitted to ICMJE-compliant journal.",
                "created_at": now - timedelta(days=350),
            },
            {
                "id": "PM-004",
                "trial_id": DUPIXENT_TRIAL,
                "mandate_type": MandateType.FDAAA_801,
                "regulation_reference": "42 USC 282(j)(3)(C)",
                "deadline_months_from_completion": 12,
                "applicable": True,
                "exemption_claimed": False,
                "exemption_reason": None,
                "exemption_approved": False,
                "compliance_status": "at_risk",
                "penalty_risk": "high",
                "penalty_amount": 11569.0,
                "responsible_party": "Dr. David Patel",
                "legal_review_required": True,
                "legal_reviewed": True,
                "notes": "OVERDUE: Civil money penalty risk of $11,569/day under FDAAA.",
                "created_at": now - timedelta(days=420),
            },
            {
                "id": "PM-005",
                "trial_id": DUPIXENT_TRIAL,
                "mandate_type": MandateType.EU_CTR,
                "regulation_reference": "EU CTR Article 37",
                "deadline_months_from_completion": 12,
                "applicable": True,
                "exemption_claimed": False,
                "exemption_reason": None,
                "exemption_approved": False,
                "compliance_status": "on_track",
                "penalty_risk": "medium",
                "penalty_amount": None,
                "responsible_party": "Dr. Maria Lopez",
                "legal_review_required": True,
                "legal_reviewed": False,
                "notes": "EU CTR summary report in progress.",
                "created_at": now - timedelta(days=410),
            },
            {
                "id": "PM-006",
                "trial_id": DUPIXENT_TRIAL,
                "mandate_type": MandateType.HEALTH_CANADA,
                "regulation_reference": "Food and Drug Regulations C.05.012",
                "deadline_months_from_completion": 12,
                "applicable": True,
                "exemption_claimed": True,
                "exemption_reason": "Trial did not include Canadian sites",
                "exemption_approved": True,
                "compliance_status": "exempt",
                "penalty_risk": "none",
                "penalty_amount": None,
                "responsible_party": "Dr. Robert Kim",
                "legal_review_required": True,
                "legal_reviewed": True,
                "notes": "Health Canada exemption approved - no Canadian sites.",
                "created_at": now - timedelta(days=390),
            },
            {
                "id": "PM-007",
                "trial_id": DUPIXENT_TRIAL,
                "mandate_type": MandateType.COMPANY_POLICY,
                "regulation_reference": "Regeneron Disclosure Policy v3.2",
                "deadline_months_from_completion": 18,
                "applicable": True,
                "exemption_claimed": False,
                "exemption_reason": None,
                "exemption_approved": False,
                "compliance_status": "on_track",
                "penalty_risk": "low",
                "penalty_amount": None,
                "responsible_party": "Dr. David Patel",
                "legal_review_required": False,
                "legal_reviewed": False,
                "notes": "Company policy requires primary publication within 18 months.",
                "created_at": now - timedelta(days=380),
            },
            {
                "id": "PM-008",
                "trial_id": LIBTAYO_TRIAL,
                "mandate_type": MandateType.FDAAA_801,
                "regulation_reference": "42 USC 282(j)(3)(C)",
                "deadline_months_from_completion": 12,
                "applicable": True,
                "exemption_claimed": False,
                "exemption_reason": None,
                "exemption_approved": False,
                "compliance_status": "on_track",
                "penalty_risk": "low",
                "penalty_amount": None,
                "responsible_party": "Dr. William Torres",
                "legal_review_required": False,
                "legal_reviewed": False,
                "notes": "LIBTAYO results posting timeline on track.",
                "created_at": now - timedelta(days=250),
            },
            {
                "id": "PM-009",
                "trial_id": LIBTAYO_TRIAL,
                "mandate_type": MandateType.EU_CTR,
                "regulation_reference": "EU CTR Article 37",
                "deadline_months_from_completion": 12,
                "applicable": True,
                "exemption_claimed": False,
                "exemption_reason": None,
                "exemption_approved": False,
                "compliance_status": "at_risk",
                "penalty_risk": "high",
                "penalty_amount": None,
                "responsible_party": "Dr. James Wright",
                "legal_review_required": True,
                "legal_reviewed": False,
                "notes": "EudraCT submission overdue. Remediation plan needed.",
                "created_at": now - timedelta(days=240),
            },
            {
                "id": "PM-010",
                "trial_id": LIBTAYO_TRIAL,
                "mandate_type": MandateType.WHO_ICTRP,
                "regulation_reference": "WHO ICTRP Policy 2015",
                "deadline_months_from_completion": 12,
                "applicable": True,
                "exemption_claimed": False,
                "exemption_reason": None,
                "exemption_approved": False,
                "compliance_status": "on_track",
                "penalty_risk": "none",
                "penalty_amount": None,
                "responsible_party": "Dr. Angela Park",
                "legal_review_required": False,
                "legal_reviewed": False,
                "notes": "WHO ICTRP primary registry link active.",
                "created_at": now - timedelta(days=220),
            },
            {
                "id": "PM-011",
                "trial_id": EYLEA_TRIAL,
                "mandate_type": MandateType.COMPANY_POLICY,
                "regulation_reference": "Regeneron Disclosure Policy v3.2",
                "deadline_months_from_completion": 18,
                "applicable": True,
                "exemption_claimed": False,
                "exemption_reason": None,
                "exemption_approved": False,
                "compliance_status": "compliant",
                "penalty_risk": "none",
                "penalty_amount": None,
                "responsible_party": "Dr. Sarah Chen",
                "legal_review_required": False,
                "legal_reviewed": False,
                "notes": "EYLEA primary publication completed within policy timeframe.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "PM-012",
                "trial_id": LIBTAYO_TRIAL,
                "mandate_type": MandateType.ICMJE,
                "regulation_reference": "ICMJE Policy 2019",
                "deadline_months_from_completion": 24,
                "applicable": True,
                "exemption_claimed": False,
                "exemption_reason": None,
                "exemption_approved": False,
                "compliance_status": "on_track",
                "penalty_risk": "none",
                "penalty_amount": None,
                "responsible_party": "Dr. Angela Park",
                "legal_review_required": False,
                "legal_reviewed": False,
                "notes": "ICMJE publication requirement tracked.",
                "created_at": now - timedelta(days=180),
            },
        ]

        for m in mandates_data:
            self._publication_mandates[m["id"]] = PublicationMandate(**m)

        # --- 12 Lay Summaries ---
        summaries_data = [
            {
                "id": "LS-001",
                "trial_id": EYLEA_TRIAL,
                "target_audience": SummaryAudience.GENERAL_PUBLIC,
                "language": "en",
                "version": "1.0",
                "status": DisclosureStatus.POSTED,
                "word_count": 1250,
                "reading_level_grade": 8.0,
                "patient_reviewed": True,
                "patient_review_date": now - timedelta(days=60),
                "ethics_committee_approved": True,
                "translated_languages": ["es", "fr", "de"],
                "distribution_date": now - timedelta(days=30),
                "distribution_channels": ["website", "patient_portal", "registry"],
                "authored_by": "Dr. Emily Watson",
                "reviewed_by": "Patient Advisory Board",
                "notes": "English lay summary published and distributed.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "LS-002",
                "trial_id": EYLEA_TRIAL,
                "target_audience": SummaryAudience.PATIENTS,
                "language": "en",
                "version": "1.0",
                "status": DisclosureStatus.SUBMITTED,
                "word_count": 850,
                "reading_level_grade": 6.5,
                "patient_reviewed": True,
                "patient_review_date": now - timedelta(days=45),
                "ethics_committee_approved": True,
                "translated_languages": ["es"],
                "distribution_date": None,
                "distribution_channels": [],
                "authored_by": "Dr. Emily Watson",
                "reviewed_by": "Patient Focus Group",
                "notes": "Patient-specific summary submitted for publication.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "LS-003",
                "trial_id": EYLEA_TRIAL,
                "target_audience": SummaryAudience.HEALTHCARE_PROVIDERS,
                "language": "en",
                "version": "1.0",
                "status": DisclosureStatus.UNDER_REVIEW,
                "word_count": 2100,
                "reading_level_grade": 12.0,
                "patient_reviewed": False,
                "patient_review_date": None,
                "ethics_committee_approved": False,
                "translated_languages": [],
                "distribution_date": None,
                "distribution_channels": [],
                "authored_by": "Dr. Sarah Chen",
                "reviewed_by": None,
                "notes": "HCP summary under medical review.",
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "LS-004",
                "trial_id": DUPIXENT_TRIAL,
                "target_audience": SummaryAudience.GENERAL_PUBLIC,
                "language": "en",
                "version": "1.0",
                "status": DisclosureStatus.IN_PREPARATION,
                "word_count": 600,
                "reading_level_grade": 7.5,
                "patient_reviewed": False,
                "patient_review_date": None,
                "ethics_committee_approved": False,
                "translated_languages": [],
                "distribution_date": None,
                "distribution_channels": [],
                "authored_by": "Dr. Robert Kim",
                "reviewed_by": None,
                "notes": "Draft in preparation. Target grade 8 reading level.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "LS-005",
                "trial_id": DUPIXENT_TRIAL,
                "target_audience": SummaryAudience.PATIENTS,
                "language": "en",
                "version": "1.0",
                "status": DisclosureStatus.PENDING,
                "word_count": 0,
                "reading_level_grade": None,
                "patient_reviewed": False,
                "patient_review_date": None,
                "ethics_committee_approved": False,
                "translated_languages": [],
                "distribution_date": None,
                "distribution_channels": [],
                "authored_by": "Dr. Maria Lopez",
                "reviewed_by": None,
                "notes": "Patient summary pending completion of general public version.",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "LS-006",
                "trial_id": DUPIXENT_TRIAL,
                "target_audience": SummaryAudience.REGULATORS,
                "language": "en",
                "version": "1.0",
                "status": DisclosureStatus.SUBMITTED,
                "word_count": 3200,
                "reading_level_grade": 14.0,
                "patient_reviewed": False,
                "patient_review_date": None,
                "ethics_committee_approved": True,
                "translated_languages": [],
                "distribution_date": now - timedelta(days=10),
                "distribution_channels": ["regulatory_portal"],
                "authored_by": "Dr. Robert Kim",
                "reviewed_by": "Regulatory Affairs Team",
                "notes": "Regulatory summary submitted via portal.",
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "LS-007",
                "trial_id": DUPIXENT_TRIAL,
                "target_audience": SummaryAudience.INVESTIGATORS,
                "language": "en",
                "version": "2.0",
                "status": DisclosureStatus.POSTED,
                "word_count": 1800,
                "reading_level_grade": 13.0,
                "patient_reviewed": False,
                "patient_review_date": None,
                "ethics_committee_approved": True,
                "translated_languages": ["ja", "zh"],
                "distribution_date": now - timedelta(days=50),
                "distribution_channels": ["investigator_portal", "email"],
                "authored_by": "Dr. Maria Lopez",
                "reviewed_by": "Dr. David Patel",
                "notes": "Investigator summary version 2 published.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "LS-008",
                "trial_id": LIBTAYO_TRIAL,
                "target_audience": SummaryAudience.GENERAL_PUBLIC,
                "language": "en",
                "version": "1.0",
                "status": DisclosureStatus.PENDING,
                "word_count": 0,
                "reading_level_grade": None,
                "patient_reviewed": False,
                "patient_review_date": None,
                "ethics_committee_approved": False,
                "translated_languages": [],
                "distribution_date": None,
                "distribution_channels": [],
                "authored_by": "Dr. Angela Park",
                "reviewed_by": None,
                "notes": "Lay summary planned after database lock.",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "LS-009",
                "trial_id": LIBTAYO_TRIAL,
                "target_audience": SummaryAudience.PATIENTS,
                "language": "en",
                "version": "1.0",
                "status": DisclosureStatus.NOT_DUE,
                "word_count": 0,
                "reading_level_grade": None,
                "patient_reviewed": False,
                "patient_review_date": None,
                "ethics_committee_approved": False,
                "translated_languages": [],
                "distribution_date": None,
                "distribution_channels": [],
                "authored_by": "Dr. Angela Park",
                "reviewed_by": None,
                "notes": "Patient summary not yet due.",
                "created_at": now - timedelta(days=8),
            },
            {
                "id": "LS-010",
                "trial_id": LIBTAYO_TRIAL,
                "target_audience": SummaryAudience.REGULATORS,
                "language": "en",
                "version": "1.0",
                "status": DisclosureStatus.IN_PREPARATION,
                "word_count": 1500,
                "reading_level_grade": 14.0,
                "patient_reviewed": False,
                "patient_review_date": None,
                "ethics_committee_approved": False,
                "translated_languages": [],
                "distribution_date": None,
                "distribution_channels": [],
                "authored_by": "Dr. James Wright",
                "reviewed_by": None,
                "notes": "Regulatory summary draft in progress.",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "LS-011",
                "trial_id": LIBTAYO_TRIAL,
                "target_audience": SummaryAudience.INVESTIGATORS,
                "language": "en",
                "version": "1.0",
                "status": DisclosureStatus.POSTED,
                "word_count": 1600,
                "reading_level_grade": 13.0,
                "patient_reviewed": False,
                "patient_review_date": None,
                "ethics_committee_approved": True,
                "translated_languages": ["ja"],
                "distribution_date": now - timedelta(days=100),
                "distribution_channels": ["investigator_portal"],
                "authored_by": "Dr. Angela Park",
                "reviewed_by": "Dr. William Torres",
                "notes": "Interim investigator summary posted.",
                "created_at": now - timedelta(days=130),
            },
            {
                "id": "LS-012",
                "trial_id": EYLEA_TRIAL,
                "target_audience": SummaryAudience.GENERAL_PUBLIC,
                "language": "es",
                "version": "1.0",
                "status": DisclosureStatus.POSTED,
                "word_count": 1300,
                "reading_level_grade": 8.0,
                "patient_reviewed": True,
                "patient_review_date": now - timedelta(days=50),
                "ethics_committee_approved": True,
                "translated_languages": [],
                "distribution_date": now - timedelta(days=25),
                "distribution_channels": ["website", "patient_portal"],
                "authored_by": "Dr. Emily Watson",
                "reviewed_by": "Patient Advisory Board",
                "notes": "Spanish translation of lay summary published.",
                "created_at": now - timedelta(days=70),
            },
        ]

        for ls in summaries_data:
            self._lay_summaries[ls["id"]] = LaySummary(**ls)

        # --- 12 Compliance Timelines ---
        timelines_data = [
            {
                "id": "CT-001",
                "trial_id": EYLEA_TRIAL,
                "milestone_name": "ClinicalTrials.gov results posting",
                "mandate_id": "PM-001",
                "target_date": now - timedelta(days=0),
                "actual_date": now - timedelta(days=15),
                "status": "completed",
                "days_remaining": 0,
                "days_late": 0,
                "blocking_issues": [],
                "responsible_party": "Dr. Sarah Chen",
                "escalation_required": False,
                "escalated_to": None,
                "escalation_date": None,
                "managed_by": "Disclosure Team Lead",
                "notes": "Completed ahead of deadline.",
                "created_at": now - timedelta(days=365),
            },
            {
                "id": "CT-002",
                "trial_id": EYLEA_TRIAL,
                "milestone_name": "EU CTR lay summary submission",
                "mandate_id": "PM-002",
                "target_date": now + timedelta(days=180),
                "actual_date": None,
                "status": "in_progress",
                "days_remaining": 180,
                "days_late": 0,
                "blocking_issues": ["Patient review pending"],
                "responsible_party": "Dr. Emily Watson",
                "escalation_required": False,
                "escalated_to": None,
                "escalation_date": None,
                "managed_by": "Disclosure Team Lead",
                "notes": "On track. Patient review scheduled next month.",
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "CT-003",
                "trial_id": EYLEA_TRIAL,
                "milestone_name": "Primary publication submission",
                "mandate_id": "PM-003",
                "target_date": now - timedelta(days=30),
                "actual_date": now - timedelta(days=90),
                "status": "completed",
                "days_remaining": 0,
                "days_late": 0,
                "blocking_issues": [],
                "responsible_party": "Dr. Sarah Chen",
                "escalation_required": False,
                "escalated_to": None,
                "escalation_date": None,
                "managed_by": "Publications Manager",
                "notes": "Published in NEJM ahead of deadline.",
                "created_at": now - timedelta(days=300),
            },
            {
                "id": "CT-004",
                "trial_id": DUPIXENT_TRIAL,
                "milestone_name": "ClinicalTrials.gov results posting",
                "mandate_id": "PM-004",
                "target_date": now - timedelta(days=35),
                "actual_date": None,
                "status": "overdue",
                "days_remaining": -35,
                "days_late": 35,
                "blocking_issues": ["Statistical tables incomplete", "Medical writing backlog"],
                "responsible_party": "Dr. Maria Lopez",
                "escalation_required": True,
                "escalated_to": "Dr. David Patel",
                "escalation_date": now - timedelta(days=20),
                "managed_by": "Disclosure Team Lead",
                "notes": "ESCALATED: 35 days overdue. Daily penalty accruing.",
                "created_at": now - timedelta(days=400),
            },
            {
                "id": "CT-005",
                "trial_id": DUPIXENT_TRIAL,
                "milestone_name": "EU CTR summary report",
                "mandate_id": "PM-005",
                "target_date": now + timedelta(days=60),
                "actual_date": None,
                "status": "in_progress",
                "days_remaining": 60,
                "days_late": 0,
                "blocking_issues": ["Legal review pending"],
                "responsible_party": "Dr. Maria Lopez",
                "escalation_required": False,
                "escalated_to": None,
                "escalation_date": None,
                "managed_by": "Disclosure Team Lead",
                "notes": "Draft under legal review.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "CT-006",
                "trial_id": DUPIXENT_TRIAL,
                "milestone_name": "Company policy publication deadline",
                "mandate_id": "PM-007",
                "target_date": now + timedelta(days=120),
                "actual_date": None,
                "status": "upcoming",
                "days_remaining": 120,
                "days_late": 0,
                "blocking_issues": [],
                "responsible_party": "Dr. Robert Kim",
                "escalation_required": False,
                "escalated_to": None,
                "escalation_date": None,
                "managed_by": "Publications Manager",
                "notes": "Manuscript in preparation.",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "CT-007",
                "trial_id": LIBTAYO_TRIAL,
                "milestone_name": "ClinicalTrials.gov results posting",
                "mandate_id": "PM-008",
                "target_date": now + timedelta(days=165),
                "actual_date": None,
                "status": "upcoming",
                "days_remaining": 165,
                "days_late": 0,
                "blocking_issues": [],
                "responsible_party": "Dr. Angela Park",
                "escalation_required": False,
                "escalated_to": None,
                "escalation_date": None,
                "managed_by": "Disclosure Team Lead",
                "notes": "Timeline established. Pending database lock.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "CT-008",
                "trial_id": LIBTAYO_TRIAL,
                "milestone_name": "EudraCT results posting",
                "mandate_id": "PM-009",
                "target_date": now - timedelta(days=135),
                "actual_date": None,
                "status": "overdue",
                "days_remaining": -135,
                "days_late": 135,
                "blocking_issues": ["Resource constraints", "Data quality issues", "Vendor delays"],
                "responsible_party": "Dr. James Wright",
                "escalation_required": True,
                "escalated_to": "Dr. William Torres",
                "escalation_date": now - timedelta(days=90),
                "managed_by": "Disclosure Team Lead",
                "notes": "ESCALATED: Remediation plan in place. Target resolution in 30 days.",
                "created_at": now - timedelta(days=300),
            },
            {
                "id": "CT-009",
                "trial_id": LIBTAYO_TRIAL,
                "milestone_name": "WHO ICTRP update",
                "mandate_id": "PM-010",
                "target_date": now + timedelta(days=200),
                "actual_date": None,
                "status": "upcoming",
                "days_remaining": 200,
                "days_late": 0,
                "blocking_issues": [],
                "responsible_party": "Dr. Angela Park",
                "escalation_required": False,
                "escalated_to": None,
                "escalation_date": None,
                "managed_by": "Disclosure Team Lead",
                "notes": "WHO registry update scheduled.",
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "CT-010",
                "trial_id": LIBTAYO_TRIAL,
                "milestone_name": "JAPIC summary submission",
                "mandate_id": None,
                "target_date": now + timedelta(days=200),
                "actual_date": None,
                "status": "upcoming",
                "days_remaining": 200,
                "days_late": 0,
                "blocking_issues": [],
                "responsible_party": "Dr. James Wright",
                "escalation_required": False,
                "escalated_to": None,
                "escalation_date": None,
                "managed_by": "Japan Regulatory Lead",
                "notes": "JAPIC submission not yet due.",
                "created_at": now - timedelta(days=160),
            },
            {
                "id": "CT-011",
                "trial_id": EYLEA_TRIAL,
                "milestone_name": "EudraCT summary report finalization",
                "mandate_id": "PM-002",
                "target_date": now + timedelta(days=150),
                "actual_date": None,
                "status": "in_progress",
                "days_remaining": 150,
                "days_late": 0,
                "blocking_issues": ["Translation pending"],
                "responsible_party": "Dr. Emily Watson",
                "escalation_required": False,
                "escalated_to": None,
                "escalation_date": None,
                "managed_by": "Disclosure Team Lead",
                "notes": "Report drafted. Awaiting translation to local languages.",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "CT-012",
                "trial_id": DUPIXENT_TRIAL,
                "milestone_name": "Lay summary patient review",
                "mandate_id": "PM-005",
                "target_date": now + timedelta(days=30),
                "actual_date": None,
                "status": "in_progress",
                "days_remaining": 30,
                "days_late": 0,
                "blocking_issues": ["Patient advisory board scheduling"],
                "responsible_party": "Dr. Robert Kim",
                "escalation_required": False,
                "escalated_to": None,
                "escalation_date": None,
                "managed_by": "Patient Engagement Lead",
                "notes": "Patient review session scheduled for next week.",
                "created_at": now - timedelta(days=50),
            },
        ]

        for t in timelines_data:
            self._compliance_timelines[t["id"]] = ComplianceTimeline(**t)

    # ------------------------------------------------------------------
    # Results Disclosures
    # ------------------------------------------------------------------

    def list_results_disclosures(
        self,
        *,
        trial_id: str | None = None,
        disclosure_type: DisclosureType | None = None,
        status: DisclosureStatus | None = None,
    ) -> list[ResultsDisclosure]:
        """List results disclosures with optional filters."""
        with self._lock:
            result = list(self._results_disclosures.values())

        if trial_id is not None:
            result = [d for d in result if d.trial_id == trial_id]
        if disclosure_type is not None:
            result = [d for d in result if d.disclosure_type == disclosure_type]
        if status is not None:
            result = [d for d in result if d.status == status]

        return sorted(result, key=lambda d: d.created_at, reverse=True)

    def get_results_disclosure(self, disclosure_id: str) -> ResultsDisclosure | None:
        """Get a single results disclosure by ID."""
        with self._lock:
            return self._results_disclosures.get(disclosure_id)

    def create_results_disclosure(self, payload: ResultsDisclosureCreate) -> ResultsDisclosure:
        """Create a new results disclosure."""
        now = datetime.now(timezone.utc)
        disclosure_id = f"RD-{uuid4().hex[:8].upper()}"
        disclosure = ResultsDisclosure(
            id=disclosure_id,
            trial_id=payload.trial_id,
            disclosure_type=payload.disclosure_type,
            status=DisclosureStatus.NOT_DUE,
            registry_name=payload.registry_name,
            registry_id=payload.registry_id,
            primary_completion_date=None,
            disclosure_deadline=payload.disclosure_deadline,
            submission_date=None,
            posting_date=None,
            days_to_deadline=None,
            days_overdue=None,
            results_summary_approved=False,
            statistical_tables_included=False,
            adverse_events_included=False,
            protocol_amendments_noted=False,
            prepared_by=payload.prepared_by,
            approved_by=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._results_disclosures[disclosure_id] = disclosure
        logger.info("Created results disclosure %s for trial %s", disclosure_id, payload.trial_id)
        return disclosure

    def update_results_disclosure(
        self, disclosure_id: str, payload: ResultsDisclosureUpdate
    ) -> ResultsDisclosure | None:
        """Update an existing results disclosure."""
        with self._lock:
            existing = self._results_disclosures.get(disclosure_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ResultsDisclosure(**data)
            self._results_disclosures[disclosure_id] = updated
        return updated

    def delete_results_disclosure(self, disclosure_id: str) -> bool:
        """Delete a results disclosure. Returns True if deleted."""
        with self._lock:
            if disclosure_id in self._results_disclosures:
                del self._results_disclosures[disclosure_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Registry Submissions
    # ------------------------------------------------------------------

    def list_registry_submissions(
        self,
        *,
        trial_id: str | None = None,
        registry_name: RegistryName | None = None,
    ) -> list[RegistrySubmission]:
        """List registry submissions with optional filters."""
        with self._lock:
            result = list(self._registry_submissions.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if registry_name is not None:
            result = [s for s in result if s.registry_name == registry_name]

        return sorted(result, key=lambda s: s.submission_date, reverse=True)

    def get_registry_submission(self, submission_id: str) -> RegistrySubmission | None:
        """Get a single registry submission by ID."""
        with self._lock:
            return self._registry_submissions.get(submission_id)

    def create_registry_submission(self, payload: RegistrySubmissionCreate) -> RegistrySubmission:
        """Create a new registry submission."""
        now = datetime.now(timezone.utc)
        submission_id = f"RS-{uuid4().hex[:8].upper()}"
        submission = RegistrySubmission(
            id=submission_id,
            trial_id=payload.trial_id,
            registry_name=payload.registry_name,
            registry_id=payload.registry_id,
            submission_type=payload.submission_type,
            submission_date=now,
            acknowledgment_date=None,
            acceptance_date=None,
            rejection_reason=None,
            protocol_version_submitted=None,
            amendments_included=0,
            qc_passed=False,
            prs_review_status=None,
            submitted_by=payload.submitted_by,
            reviewer=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._registry_submissions[submission_id] = submission
        logger.info("Created registry submission %s for trial %s", submission_id, payload.trial_id)
        return submission

    def update_registry_submission(
        self, submission_id: str, payload: RegistrySubmissionUpdate
    ) -> RegistrySubmission | None:
        """Update an existing registry submission."""
        with self._lock:
            existing = self._registry_submissions.get(submission_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = RegistrySubmission(**data)
            self._registry_submissions[submission_id] = updated
        return updated

    def delete_registry_submission(self, submission_id: str) -> bool:
        """Delete a registry submission. Returns True if deleted."""
        with self._lock:
            if submission_id in self._registry_submissions:
                del self._registry_submissions[submission_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Publication Mandates
    # ------------------------------------------------------------------

    def list_publication_mandates(
        self,
        *,
        trial_id: str | None = None,
        mandate_type: MandateType | None = None,
    ) -> list[PublicationMandate]:
        """List publication mandates with optional filters."""
        with self._lock:
            result = list(self._publication_mandates.values())

        if trial_id is not None:
            result = [m for m in result if m.trial_id == trial_id]
        if mandate_type is not None:
            result = [m for m in result if m.mandate_type == mandate_type]

        return sorted(result, key=lambda m: m.created_at, reverse=True)

    def get_publication_mandate(self, mandate_id: str) -> PublicationMandate | None:
        """Get a single publication mandate by ID."""
        with self._lock:
            return self._publication_mandates.get(mandate_id)

    def create_publication_mandate(self, payload: PublicationMandateCreate) -> PublicationMandate:
        """Create a new publication mandate."""
        now = datetime.now(timezone.utc)
        mandate_id = f"PM-{uuid4().hex[:8].upper()}"
        mandate = PublicationMandate(
            id=mandate_id,
            trial_id=payload.trial_id,
            mandate_type=payload.mandate_type,
            regulation_reference=payload.regulation_reference,
            deadline_months_from_completion=payload.deadline_months_from_completion,
            applicable=True,
            exemption_claimed=False,
            exemption_reason=None,
            exemption_approved=False,
            compliance_status="on_track",
            penalty_risk="none",
            penalty_amount=None,
            responsible_party=payload.responsible_party,
            legal_review_required=False,
            legal_reviewed=False,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._publication_mandates[mandate_id] = mandate
        logger.info("Created publication mandate %s for trial %s", mandate_id, payload.trial_id)
        return mandate

    def update_publication_mandate(
        self, mandate_id: str, payload: PublicationMandateUpdate
    ) -> PublicationMandate | None:
        """Update an existing publication mandate."""
        with self._lock:
            existing = self._publication_mandates.get(mandate_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = PublicationMandate(**data)
            self._publication_mandates[mandate_id] = updated
        return updated

    def delete_publication_mandate(self, mandate_id: str) -> bool:
        """Delete a publication mandate. Returns True if deleted."""
        with self._lock:
            if mandate_id in self._publication_mandates:
                del self._publication_mandates[mandate_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Lay Summaries
    # ------------------------------------------------------------------

    def list_lay_summaries(
        self,
        *,
        trial_id: str | None = None,
        target_audience: SummaryAudience | None = None,
        status: DisclosureStatus | None = None,
    ) -> list[LaySummary]:
        """List lay summaries with optional filters."""
        with self._lock:
            result = list(self._lay_summaries.values())

        if trial_id is not None:
            result = [ls for ls in result if ls.trial_id == trial_id]
        if target_audience is not None:
            result = [ls for ls in result if ls.target_audience == target_audience]
        if status is not None:
            result = [ls for ls in result if ls.status == status]

        return sorted(result, key=lambda ls: ls.created_at, reverse=True)

    def get_lay_summary(self, summary_id: str) -> LaySummary | None:
        """Get a single lay summary by ID."""
        with self._lock:
            return self._lay_summaries.get(summary_id)

    def create_lay_summary(self, payload: LaySummaryCreate) -> LaySummary:
        """Create a new lay summary."""
        now = datetime.now(timezone.utc)
        summary_id = f"LS-{uuid4().hex[:8].upper()}"
        summary = LaySummary(
            id=summary_id,
            trial_id=payload.trial_id,
            target_audience=payload.target_audience,
            language=payload.language,
            version="1.0",
            status=DisclosureStatus.PENDING,
            word_count=payload.word_count,
            reading_level_grade=None,
            patient_reviewed=False,
            patient_review_date=None,
            ethics_committee_approved=False,
            translated_languages=[],
            distribution_date=None,
            distribution_channels=[],
            authored_by=payload.authored_by,
            reviewed_by=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._lay_summaries[summary_id] = summary
        logger.info("Created lay summary %s for trial %s", summary_id, payload.trial_id)
        return summary

    def update_lay_summary(
        self, summary_id: str, payload: LaySummaryUpdate
    ) -> LaySummary | None:
        """Update an existing lay summary."""
        with self._lock:
            existing = self._lay_summaries.get(summary_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = LaySummary(**data)
            self._lay_summaries[summary_id] = updated
        return updated

    def delete_lay_summary(self, summary_id: str) -> bool:
        """Delete a lay summary. Returns True if deleted."""
        with self._lock:
            if summary_id in self._lay_summaries:
                del self._lay_summaries[summary_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Compliance Timelines
    # ------------------------------------------------------------------

    def list_compliance_timelines(
        self,
        *,
        trial_id: str | None = None,
        status: str | None = None,
    ) -> list[ComplianceTimeline]:
        """List compliance timelines with optional filters."""
        with self._lock:
            result = list(self._compliance_timelines.values())

        if trial_id is not None:
            result = [t for t in result if t.trial_id == trial_id]
        if status is not None:
            result = [t for t in result if t.status == status]

        return sorted(result, key=lambda t: t.target_date, reverse=True)

    def get_compliance_timeline(self, timeline_id: str) -> ComplianceTimeline | None:
        """Get a single compliance timeline by ID."""
        with self._lock:
            return self._compliance_timelines.get(timeline_id)

    def create_compliance_timeline(self, payload: ComplianceTimelineCreate) -> ComplianceTimeline:
        """Create a new compliance timeline."""
        now = datetime.now(timezone.utc)
        timeline_id = f"CT-{uuid4().hex[:8].upper()}"
        timeline = ComplianceTimeline(
            id=timeline_id,
            trial_id=payload.trial_id,
            milestone_name=payload.milestone_name,
            mandate_id=payload.mandate_id,
            target_date=payload.target_date,
            actual_date=None,
            status="upcoming",
            days_remaining=None,
            days_late=None,
            blocking_issues=[],
            responsible_party=payload.responsible_party,
            escalation_required=False,
            escalated_to=None,
            escalation_date=None,
            managed_by=payload.managed_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._compliance_timelines[timeline_id] = timeline
        logger.info("Created compliance timeline %s for trial %s", timeline_id, payload.trial_id)
        return timeline

    def update_compliance_timeline(
        self, timeline_id: str, payload: ComplianceTimelineUpdate
    ) -> ComplianceTimeline | None:
        """Update an existing compliance timeline."""
        with self._lock:
            existing = self._compliance_timelines.get(timeline_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ComplianceTimeline(**data)
            self._compliance_timelines[timeline_id] = updated
        return updated

    def delete_compliance_timeline(self, timeline_id: str) -> bool:
        """Delete a compliance timeline. Returns True if deleted."""
        with self._lock:
            if timeline_id in self._compliance_timelines:
                del self._compliance_timelines[timeline_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> TrialDisclosureMetrics:
        """Compute aggregated trial disclosure metrics."""
        with self._lock:
            disclosures = list(self._results_disclosures.values())
            submissions = list(self._registry_submissions.values())
            mandates = list(self._publication_mandates.values())
            summaries = list(self._lay_summaries.values())
            timelines = list(self._compliance_timelines.values())

        # Disclosures by type
        disclosures_by_type: dict[str, int] = {}
        for d in disclosures:
            key = d.disclosure_type.value
            disclosures_by_type[key] = disclosures_by_type.get(key, 0) + 1

        # Disclosures by status
        disclosures_by_status: dict[str, int] = {}
        for d in disclosures:
            key = d.status.value
            disclosures_by_status[key] = disclosures_by_status.get(key, 0) + 1

        # Overdue disclosures
        overdue_disclosures = sum(1 for d in disclosures if d.status == DisclosureStatus.OVERDUE)

        # Submissions by registry
        submissions_by_registry: dict[str, int] = {}
        for s in submissions:
            key = s.registry_name.value
            submissions_by_registry[key] = submissions_by_registry.get(key, 0) + 1

        # Mandates by type
        mandates_by_type: dict[str, int] = {}
        for m in mandates:
            key = m.mandate_type.value
            mandates_by_type[key] = mandates_by_type.get(key, 0) + 1

        # Mandates at risk
        mandates_at_risk = sum(
            1 for m in mandates if m.compliance_status == "at_risk"
        )

        # Summaries by audience
        summaries_by_audience: dict[str, int] = {}
        for ls in summaries:
            key = ls.target_audience.value
            summaries_by_audience[key] = summaries_by_audience.get(key, 0) + 1

        # Milestones overdue
        milestones_overdue = sum(1 for t in timelines if t.status == "overdue")

        # Milestones escalated
        milestones_escalated = sum(1 for t in timelines if t.escalation_required)

        return TrialDisclosureMetrics(
            total_disclosures=len(disclosures),
            disclosures_by_type=disclosures_by_type,
            disclosures_by_status=disclosures_by_status,
            overdue_disclosures=overdue_disclosures,
            total_registry_submissions=len(submissions),
            submissions_by_registry=submissions_by_registry,
            total_mandates=len(mandates),
            mandates_by_type=mandates_by_type,
            mandates_at_risk=mandates_at_risk,
            total_lay_summaries=len(summaries),
            summaries_by_audience=summaries_by_audience,
            total_milestones=len(timelines),
            milestones_overdue=milestones_overdue,
            milestones_escalated=milestones_escalated,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: TrialDisclosureService | None = None
_instance_lock = threading.Lock()


def get_trial_disclosure_service() -> TrialDisclosureService:
    """Return the singleton TrialDisclosureService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = TrialDisclosureService()
    return _instance


def reset_trial_disclosure_service() -> TrialDisclosureService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = TrialDisclosureService()
    return _instance
