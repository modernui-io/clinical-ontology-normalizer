"""Interim Analysis Service (IA-MGT).

Manages interim analysis operations: analysis plans, data cut definitions,
DSMB review records, statistical review outcomes, and interim analysis metrics.

Usage:
    from app.services.interim_analysis_service import (
        get_interim_analysis_service,
    )

    svc = get_interim_analysis_service()
    plans = svc.list_analysis_plans()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.interim_analysis import (
    AnalysisPlan,
    AnalysisPlanCreate,
    AnalysisPlanStatus,
    AnalysisPlanUpdate,
    BlindingStatus,
    DSMBRecommendation,
    DSMBReview,
    DSMBReviewCreate,
    DSMBReviewUpdate,
    DataCutDefinition,
    DataCutDefinitionCreate,
    DataCutDefinitionUpdate,
    DataCutStatus,
    InterimAnalysisMetrics,
    ReviewOutcome,
    StatisticalReviewOutcome,
    StatisticalReviewOutcomeCreate,
    StatisticalReviewOutcomeUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class InterimAnalysisService:
    """In-memory Interim Analysis engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._analysis_plans: dict[str, AnalysisPlan] = {}
        self._data_cut_definitions: dict[str, DataCutDefinition] = {}
        self._dsmb_reviews: dict[str, DSMBReview] = {}
        self._statistical_review_outcomes: dict[str, StatisticalReviewOutcome] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic interim analysis data."""
        now = datetime.now(timezone.utc)

        # --- 12 Analysis Plans ---
        plans_data = [
            {
                "id": "IAP-001",
                "trial_id": EYLEA_TRIAL,
                "plan_name": "EYLEA Phase 3 Primary Efficacy IA Plan",
                "version": "1.0",
                "analysis_plan_status": AnalysisPlanStatus.APPROVED,
                "planned_analyses_count": 3,
                "primary_endpoint": "Best corrected visual acuity change from baseline at Week 48",
                "secondary_endpoints": "Central retinal thickness; proportion with 15-letter gain",
                "alpha_spending_function": "O'Brien-Fleming",
                "information_fraction": 0.5,
                "stopping_boundaries": "Z=2.96 at 50% information",
                "authored_by": "Dr. Sarah Chen",
                "approved_by": "Dr. James Wilson",
                "approval_date": now - timedelta(days=180),
                "effective_date": now - timedelta(days=170),
                "notes": "Primary IA plan approved by steering committee.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "IAP-002",
                "trial_id": EYLEA_TRIAL,
                "plan_name": "EYLEA Futility Analysis Plan",
                "version": "1.0",
                "analysis_plan_status": AnalysisPlanStatus.ACTIVE,
                "planned_analyses_count": 2,
                "primary_endpoint": "Best corrected visual acuity change from baseline at Week 48",
                "secondary_endpoints": None,
                "alpha_spending_function": "Pocock",
                "information_fraction": 0.33,
                "stopping_boundaries": "Conditional power <10%",
                "authored_by": "Dr. Sarah Chen",
                "approved_by": "Dr. James Wilson",
                "approval_date": now - timedelta(days=160),
                "effective_date": now - timedelta(days=155),
                "notes": "Futility monitoring per DSMB charter.",
                "created_at": now - timedelta(days=190),
            },
            {
                "id": "IAP-003",
                "trial_id": EYLEA_TRIAL,
                "plan_name": "EYLEA Safety Monitoring IA Plan",
                "version": "2.0",
                "analysis_plan_status": AnalysisPlanStatus.AMENDED,
                "planned_analyses_count": 4,
                "primary_endpoint": "Incidence of treatment-emergent adverse events",
                "secondary_endpoints": "Serious adverse events; ocular adverse events",
                "alpha_spending_function": None,
                "information_fraction": 0.25,
                "stopping_boundaries": "Descriptive safety review at each interim",
                "authored_by": "Dr. Maria Lopez",
                "approved_by": "Dr. James Wilson",
                "approval_date": now - timedelta(days=100),
                "effective_date": now - timedelta(days=95),
                "notes": "Amended to include new safety signal monitoring after v1.0 DSMB recommendation.",
                "created_at": now - timedelta(days=185),
            },
            {
                "id": "IAP-004",
                "trial_id": EYLEA_TRIAL,
                "plan_name": "EYLEA Subgroup Analysis Plan",
                "version": "1.0",
                "analysis_plan_status": AnalysisPlanStatus.DRAFT,
                "planned_analyses_count": 1,
                "primary_endpoint": "Best corrected visual acuity change by baseline severity subgroup",
                "secondary_endpoints": None,
                "alpha_spending_function": None,
                "information_fraction": None,
                "stopping_boundaries": None,
                "authored_by": "Dr. Kevin Park",
                "approved_by": None,
                "approval_date": None,
                "effective_date": None,
                "notes": "Draft subgroup analysis plan pending steering committee review.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "IAP-005",
                "trial_id": DUPIXENT_TRIAL,
                "plan_name": "DUPIXENT Phase 3 Primary IA Plan",
                "version": "1.0",
                "analysis_plan_status": AnalysisPlanStatus.APPROVED,
                "planned_analyses_count": 2,
                "primary_endpoint": "EASI-75 response rate at Week 16",
                "secondary_endpoints": "IGA 0/1 response; SCORAD reduction; DLQI improvement",
                "alpha_spending_function": "Lan-DeMets (O'Brien-Fleming)",
                "information_fraction": 0.6,
                "stopping_boundaries": "Z=2.58 at 60% information",
                "authored_by": "Dr. Emily Richards",
                "approved_by": "Dr. Robert Kim",
                "approval_date": now - timedelta(days=150),
                "effective_date": now - timedelta(days=145),
                "notes": "Approved by IDMC and sponsor jointly.",
                "created_at": now - timedelta(days=175),
            },
            {
                "id": "IAP-006",
                "trial_id": DUPIXENT_TRIAL,
                "plan_name": "DUPIXENT Efficacy Early Stopping Plan",
                "version": "1.0",
                "analysis_plan_status": AnalysisPlanStatus.ACTIVE,
                "planned_analyses_count": 2,
                "primary_endpoint": "EASI-75 response rate at Week 16",
                "secondary_endpoints": None,
                "alpha_spending_function": "Haybittle-Peto",
                "information_fraction": 0.5,
                "stopping_boundaries": "p<0.001 at interim",
                "authored_by": "Dr. Emily Richards",
                "approved_by": "Dr. Robert Kim",
                "approval_date": now - timedelta(days=140),
                "effective_date": now - timedelta(days=135),
                "notes": "Conservative boundary for early efficacy stop.",
                "created_at": now - timedelta(days=170),
            },
            {
                "id": "IAP-007",
                "trial_id": DUPIXENT_TRIAL,
                "plan_name": "DUPIXENT Safety IA Plan",
                "version": "1.0",
                "analysis_plan_status": AnalysisPlanStatus.COMPLETED,
                "planned_analyses_count": 3,
                "primary_endpoint": "Incidence of conjunctivitis and injection site reactions",
                "secondary_endpoints": "Eosinophil counts; infection rates",
                "alpha_spending_function": None,
                "information_fraction": 0.75,
                "stopping_boundaries": "Qualitative safety assessment",
                "authored_by": "Dr. Amanda Torres",
                "approved_by": "Dr. Robert Kim",
                "approval_date": now - timedelta(days=130),
                "effective_date": now - timedelta(days=125),
                "notes": "All planned safety analyses completed successfully.",
                "created_at": now - timedelta(days=165),
            },
            {
                "id": "IAP-008",
                "trial_id": DUPIXENT_TRIAL,
                "plan_name": "DUPIXENT Dose-Response IA Plan",
                "version": "1.0",
                "analysis_plan_status": AnalysisPlanStatus.CANCELLED,
                "planned_analyses_count": 1,
                "primary_endpoint": "Dose-response relationship for EASI score reduction",
                "secondary_endpoints": None,
                "alpha_spending_function": None,
                "information_fraction": None,
                "stopping_boundaries": None,
                "authored_by": "Dr. Kevin Park",
                "approved_by": None,
                "approval_date": None,
                "effective_date": None,
                "notes": "Cancelled after Phase 2 dose selection confirmed single dose arm.",
                "created_at": now - timedelta(days=160),
            },
            {
                "id": "IAP-009",
                "trial_id": LIBTAYO_TRIAL,
                "plan_name": "LIBTAYO Phase 3 Primary IA Plan",
                "version": "1.0",
                "analysis_plan_status": AnalysisPlanStatus.APPROVED,
                "planned_analyses_count": 3,
                "primary_endpoint": "Overall survival",
                "secondary_endpoints": "Progression-free survival; objective response rate; duration of response",
                "alpha_spending_function": "O'Brien-Fleming",
                "information_fraction": 0.4,
                "stopping_boundaries": "Z=3.36 at 40% events; Z=2.68 at 60% events",
                "authored_by": "Dr. Thomas Anderson",
                "approved_by": "Dr. Lisa Wang",
                "approval_date": now - timedelta(days=120),
                "effective_date": now - timedelta(days=115),
                "notes": "OS interim analysis plan with conservative boundaries per regulatory guidance.",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "IAP-010",
                "trial_id": LIBTAYO_TRIAL,
                "plan_name": "LIBTAYO PFS Interim Analysis Plan",
                "version": "1.0",
                "analysis_plan_status": AnalysisPlanStatus.ACTIVE,
                "planned_analyses_count": 2,
                "primary_endpoint": "Progression-free survival by RECIST 1.1",
                "secondary_endpoints": "PFS by investigator assessment",
                "alpha_spending_function": "Lan-DeMets (Pocock)",
                "information_fraction": 0.5,
                "stopping_boundaries": "HR boundary 0.65 at 50% events",
                "authored_by": "Dr. Thomas Anderson",
                "approved_by": "Dr. Lisa Wang",
                "approval_date": now - timedelta(days=110),
                "effective_date": now - timedelta(days=105),
                "notes": "Secondary PFS analysis with independent review.",
                "created_at": now - timedelta(days=145),
            },
            {
                "id": "IAP-011",
                "trial_id": LIBTAYO_TRIAL,
                "plan_name": "LIBTAYO Biomarker Subgroup IA Plan",
                "version": "1.0",
                "analysis_plan_status": AnalysisPlanStatus.DRAFT,
                "planned_analyses_count": 1,
                "primary_endpoint": "Overall survival by PD-L1 expression subgroup",
                "secondary_endpoints": "Tumor mutational burden subgroup analysis",
                "alpha_spending_function": None,
                "information_fraction": None,
                "stopping_boundaries": None,
                "authored_by": "Dr. Rachel Green",
                "approved_by": None,
                "approval_date": None,
                "effective_date": None,
                "notes": "Exploratory biomarker analysis plan in development.",
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "IAP-012",
                "trial_id": LIBTAYO_TRIAL,
                "plan_name": "LIBTAYO Safety Monitoring IA Plan",
                "version": "1.0",
                "analysis_plan_status": AnalysisPlanStatus.ACTIVE,
                "planned_analyses_count": 4,
                "primary_endpoint": "Immune-related adverse events grade 3+",
                "secondary_endpoints": "Treatment discontinuation rate; irAE management outcomes",
                "alpha_spending_function": None,
                "information_fraction": 0.25,
                "stopping_boundaries": "irAE rate >30% triggers safety review",
                "authored_by": "Dr. Amanda Torres",
                "approved_by": "Dr. Lisa Wang",
                "approval_date": now - timedelta(days=105),
                "effective_date": now - timedelta(days=100),
                "notes": "Ongoing safety monitoring per immuno-oncology trial guidance.",
                "created_at": now - timedelta(days=140),
            },
        ]

        for p in plans_data:
            self._analysis_plans[p["id"]] = AnalysisPlan(**p)

        # --- 12 Data Cut Definitions ---
        data_cuts_data = [
            {
                "id": "DCT-001",
                "trial_id": EYLEA_TRIAL,
                "analysis_plan_id": "IAP-001",
                "cut_name": "EYLEA IA1 - 50% Information",
                "data_cut_status": DataCutStatus.COMPLETED,
                "cut_date": now - timedelta(days=90),
                "target_enrollment": 300,
                "actual_enrollment": 312,
                "target_events": 150,
                "actual_events": 158,
                "blinding_status": BlindingStatus.INDEPENDENT_REVIEW,
                "database_lock_date": now - timedelta(days=95),
                "data_transfer_date": now - timedelta(days=92),
                "responsible_statistician": "Dr. Wei Zhang",
                "notes": "First interim data cut completed. Database locked on schedule.",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "DCT-002",
                "trial_id": EYLEA_TRIAL,
                "analysis_plan_id": "IAP-001",
                "cut_name": "EYLEA IA2 - 75% Information",
                "data_cut_status": DataCutStatus.IN_PROGRESS,
                "cut_date": None,
                "target_enrollment": 300,
                "actual_enrollment": 298,
                "target_events": 225,
                "actual_events": 210,
                "blinding_status": BlindingStatus.FULLY_BLINDED,
                "database_lock_date": None,
                "data_transfer_date": None,
                "responsible_statistician": "Dr. Wei Zhang",
                "notes": "Second interim approaching target events. Database lock pending.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "DCT-003",
                "trial_id": EYLEA_TRIAL,
                "analysis_plan_id": "IAP-002",
                "cut_name": "EYLEA Futility Look 1",
                "data_cut_status": DataCutStatus.VALIDATED,
                "cut_date": now - timedelta(days=100),
                "target_enrollment": 200,
                "actual_enrollment": 205,
                "target_events": 100,
                "actual_events": 103,
                "blinding_status": BlindingStatus.INDEPENDENT_REVIEW,
                "database_lock_date": now - timedelta(days=105),
                "data_transfer_date": now - timedelta(days=102),
                "responsible_statistician": "Dr. Jennifer Liu",
                "notes": "Futility data cut validated. No futility signal detected.",
                "created_at": now - timedelta(days=130),
            },
            {
                "id": "DCT-004",
                "trial_id": EYLEA_TRIAL,
                "analysis_plan_id": "IAP-003",
                "cut_name": "EYLEA Safety Review Cut 1",
                "data_cut_status": DataCutStatus.RELEASED,
                "cut_date": now - timedelta(days=80),
                "target_enrollment": 150,
                "actual_enrollment": 162,
                "target_events": 0,
                "actual_events": 0,
                "blinding_status": BlindingStatus.PARTIALLY_UNBLINDED,
                "database_lock_date": now - timedelta(days=85),
                "data_transfer_date": now - timedelta(days=82),
                "responsible_statistician": "Dr. Jennifer Liu",
                "notes": "Safety data cut released to DSMB. Unblinded safety tables prepared.",
                "created_at": now - timedelta(days=110),
            },
            {
                "id": "DCT-005",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_plan_id": "IAP-005",
                "cut_name": "DUPIXENT IA1 - 60% Information",
                "data_cut_status": DataCutStatus.COMPLETED,
                "cut_date": now - timedelta(days=70),
                "target_enrollment": 400,
                "actual_enrollment": 415,
                "target_events": 240,
                "actual_events": 248,
                "blinding_status": BlindingStatus.INDEPENDENT_REVIEW,
                "database_lock_date": now - timedelta(days=75),
                "data_transfer_date": now - timedelta(days=72),
                "responsible_statistician": "Dr. Michael Ross",
                "notes": "Primary interim data cut completed ahead of schedule.",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "DCT-006",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_plan_id": "IAP-006",
                "cut_name": "DUPIXENT Efficacy Stop Check",
                "data_cut_status": DataCutStatus.COMPLETED,
                "cut_date": now - timedelta(days=65),
                "target_enrollment": 400,
                "actual_enrollment": 415,
                "target_events": 200,
                "actual_events": 208,
                "blinding_status": BlindingStatus.INDEPENDENT_REVIEW,
                "database_lock_date": now - timedelta(days=70),
                "data_transfer_date": now - timedelta(days=67),
                "responsible_statistician": "Dr. Michael Ross",
                "notes": "Early efficacy data cut completed for Haybittle-Peto boundary evaluation.",
                "created_at": now - timedelta(days=95),
            },
            {
                "id": "DCT-007",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_plan_id": "IAP-007",
                "cut_name": "DUPIXENT Safety Review Cut 1",
                "data_cut_status": DataCutStatus.RELEASED,
                "cut_date": now - timedelta(days=50),
                "target_enrollment": 300,
                "actual_enrollment": 320,
                "target_events": 0,
                "actual_events": 0,
                "blinding_status": BlindingStatus.PARTIALLY_UNBLINDED,
                "database_lock_date": now - timedelta(days=55),
                "data_transfer_date": now - timedelta(days=52),
                "responsible_statistician": "Dr. Anna Patel",
                "notes": "Safety data cut for conjunctivitis and injection site reaction review.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "DCT-008",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_plan_id": "IAP-005",
                "cut_name": "DUPIXENT IA2 - Final Planned IA",
                "data_cut_status": DataCutStatus.PLANNED,
                "cut_date": None,
                "target_enrollment": 400,
                "actual_enrollment": 0,
                "target_events": 360,
                "actual_events": 0,
                "blinding_status": BlindingStatus.FULLY_BLINDED,
                "database_lock_date": None,
                "data_transfer_date": None,
                "responsible_statistician": "Dr. Michael Ross",
                "notes": "Second and final planned interim analysis. Pending event accumulation.",
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "DCT-009",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_plan_id": "IAP-009",
                "cut_name": "LIBTAYO OS IA1 - 40% Events",
                "data_cut_status": DataCutStatus.COMPLETED,
                "cut_date": now - timedelta(days=45),
                "target_enrollment": 500,
                "actual_enrollment": 520,
                "target_events": 200,
                "actual_events": 205,
                "blinding_status": BlindingStatus.INDEPENDENT_REVIEW,
                "database_lock_date": now - timedelta(days=50),
                "data_transfer_date": now - timedelta(days=47),
                "responsible_statistician": "Dr. David Kim",
                "notes": "First OS interim analysis data cut. Independent statistical center performed analysis.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "DCT-010",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_plan_id": "IAP-010",
                "cut_name": "LIBTAYO PFS IA1 - 50% Events",
                "data_cut_status": DataCutStatus.VALIDATED,
                "cut_date": now - timedelta(days=40),
                "target_enrollment": 500,
                "actual_enrollment": 520,
                "target_events": 300,
                "actual_events": 310,
                "blinding_status": BlindingStatus.INDEPENDENT_REVIEW,
                "database_lock_date": now - timedelta(days=45),
                "data_transfer_date": now - timedelta(days=42),
                "responsible_statistician": "Dr. David Kim",
                "notes": "PFS interim data validated by independent statistician and IRC.",
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "DCT-011",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_plan_id": "IAP-012",
                "cut_name": "LIBTAYO Safety Review Cut 1",
                "data_cut_status": DataCutStatus.SUPERSEDED,
                "cut_date": now - timedelta(days=60),
                "target_enrollment": 250,
                "actual_enrollment": 265,
                "target_events": 0,
                "actual_events": 0,
                "blinding_status": BlindingStatus.PARTIALLY_UNBLINDED,
                "database_lock_date": now - timedelta(days=65),
                "data_transfer_date": now - timedelta(days=62),
                "responsible_statistician": "Dr. Anna Patel",
                "notes": "Superseded by updated safety cut with expanded irAE criteria.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "DCT-012",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_plan_id": "IAP-012",
                "cut_name": "LIBTAYO Safety Review Cut 2",
                "data_cut_status": DataCutStatus.IN_PROGRESS,
                "cut_date": None,
                "target_enrollment": 400,
                "actual_enrollment": 380,
                "target_events": 0,
                "actual_events": 0,
                "blinding_status": BlindingStatus.FULLY_BLINDED,
                "database_lock_date": None,
                "data_transfer_date": None,
                "responsible_statistician": "Dr. Anna Patel",
                "notes": "Updated safety data cut in progress with expanded irAE definitions.",
                "created_at": now - timedelta(days=20),
            },
        ]

        for d in data_cuts_data:
            self._data_cut_definitions[d["id"]] = DataCutDefinition(**d)

        # --- 12 DSMB Reviews ---
        dsmb_data = [
            {
                "id": "DSMB-001",
                "trial_id": EYLEA_TRIAL,
                "data_cut_id": "DCT-001",
                "meeting_date": now - timedelta(days=85),
                "meeting_number": 1,
                "dsmb_recommendation": DSMBRecommendation.CONTINUE_AS_PLANNED,
                "attendees_count": 7,
                "quorum_met": True,
                "safety_concerns_raised": False,
                "efficacy_signal_detected": False,
                "minutes_document_id": "DOC-DSMB-001",
                "letter_sent_date": now - timedelta(days=82),
                "sponsor_notified_date": now - timedelta(days=80),
                "chair_name": "Prof. Richard Hughes",
                "notes": "First DSMB review. No safety concerns. Trial continues as planned.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "DSMB-002",
                "trial_id": EYLEA_TRIAL,
                "data_cut_id": "DCT-003",
                "meeting_date": now - timedelta(days=95),
                "meeting_number": 2,
                "dsmb_recommendation": DSMBRecommendation.CONTINUE_AS_PLANNED,
                "attendees_count": 6,
                "quorum_met": True,
                "safety_concerns_raised": False,
                "efficacy_signal_detected": False,
                "minutes_document_id": "DOC-DSMB-002",
                "letter_sent_date": now - timedelta(days=92),
                "sponsor_notified_date": now - timedelta(days=90),
                "chair_name": "Prof. Richard Hughes",
                "notes": "Futility analysis showed no futility signal. Conditional power adequate.",
                "created_at": now - timedelta(days=95),
            },
            {
                "id": "DSMB-003",
                "trial_id": EYLEA_TRIAL,
                "data_cut_id": "DCT-004",
                "meeting_date": now - timedelta(days=75),
                "meeting_number": 3,
                "dsmb_recommendation": DSMBRecommendation.MODIFY_PROTOCOL,
                "attendees_count": 7,
                "quorum_met": True,
                "safety_concerns_raised": True,
                "efficacy_signal_detected": False,
                "minutes_document_id": "DOC-DSMB-003",
                "letter_sent_date": now - timedelta(days=72),
                "sponsor_notified_date": now - timedelta(days=70),
                "chair_name": "Prof. Richard Hughes",
                "notes": "Safety signal noted for endophthalmitis rate. Recommended enhanced monitoring protocol.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "DSMB-004",
                "trial_id": EYLEA_TRIAL,
                "data_cut_id": "DCT-001",
                "meeting_date": now - timedelta(days=55),
                "meeting_number": 4,
                "dsmb_recommendation": DSMBRecommendation.REQUEST_ADDITIONAL_DATA,
                "attendees_count": 5,
                "quorum_met": True,
                "safety_concerns_raised": True,
                "efficacy_signal_detected": False,
                "minutes_document_id": "DOC-DSMB-004",
                "letter_sent_date": now - timedelta(days=52),
                "sponsor_notified_date": now - timedelta(days=50),
                "chair_name": "Prof. Richard Hughes",
                "notes": "Requested additional safety data on endophthalmitis cases before next review.",
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "DSMB-005",
                "trial_id": DUPIXENT_TRIAL,
                "data_cut_id": "DCT-005",
                "meeting_date": now - timedelta(days=65),
                "meeting_number": 1,
                "dsmb_recommendation": DSMBRecommendation.CONTINUE_AS_PLANNED,
                "attendees_count": 8,
                "quorum_met": True,
                "safety_concerns_raised": False,
                "efficacy_signal_detected": True,
                "minutes_document_id": "DOC-DSMB-005",
                "letter_sent_date": now - timedelta(days=62),
                "sponsor_notified_date": now - timedelta(days=60),
                "chair_name": "Prof. Catherine Brooks",
                "notes": "Strong efficacy signal detected but did not cross early stopping boundary.",
                "created_at": now - timedelta(days=65),
            },
            {
                "id": "DSMB-006",
                "trial_id": DUPIXENT_TRIAL,
                "data_cut_id": "DCT-006",
                "meeting_date": now - timedelta(days=60),
                "meeting_number": 2,
                "dsmb_recommendation": DSMBRecommendation.STOP_FOR_EFFICACY,
                "attendees_count": 8,
                "quorum_met": True,
                "safety_concerns_raised": False,
                "efficacy_signal_detected": True,
                "minutes_document_id": "DOC-DSMB-006",
                "letter_sent_date": now - timedelta(days=57),
                "sponsor_notified_date": now - timedelta(days=55),
                "chair_name": "Prof. Catherine Brooks",
                "notes": "Efficacy boundary crossed. DSMB recommends early stopping for overwhelming efficacy.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "DSMB-007",
                "trial_id": DUPIXENT_TRIAL,
                "data_cut_id": "DCT-007",
                "meeting_date": now - timedelta(days=45),
                "meeting_number": 3,
                "dsmb_recommendation": DSMBRecommendation.CONTINUE_AS_PLANNED,
                "attendees_count": 7,
                "quorum_met": True,
                "safety_concerns_raised": False,
                "efficacy_signal_detected": False,
                "minutes_document_id": "DOC-DSMB-007",
                "letter_sent_date": now - timedelta(days=42),
                "sponsor_notified_date": now - timedelta(days=40),
                "chair_name": "Prof. Catherine Brooks",
                "notes": "Safety review satisfactory. Conjunctivitis rates within expected range.",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "DSMB-008",
                "trial_id": DUPIXENT_TRIAL,
                "data_cut_id": "DCT-005",
                "meeting_date": now - timedelta(days=30),
                "meeting_number": 4,
                "dsmb_recommendation": DSMBRecommendation.CONTINUE_AS_PLANNED,
                "attendees_count": 6,
                "quorum_met": True,
                "safety_concerns_raised": False,
                "efficacy_signal_detected": False,
                "minutes_document_id": None,
                "letter_sent_date": None,
                "sponsor_notified_date": None,
                "chair_name": "Prof. Catherine Brooks",
                "notes": "Routine follow-up review. Minutes pending finalization.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "DSMB-009",
                "trial_id": LIBTAYO_TRIAL,
                "data_cut_id": "DCT-009",
                "meeting_date": now - timedelta(days=40),
                "meeting_number": 1,
                "dsmb_recommendation": DSMBRecommendation.CONTINUE_AS_PLANNED,
                "attendees_count": 9,
                "quorum_met": True,
                "safety_concerns_raised": False,
                "efficacy_signal_detected": True,
                "minutes_document_id": "DOC-DSMB-009",
                "letter_sent_date": now - timedelta(days=37),
                "sponsor_notified_date": now - timedelta(days=35),
                "chair_name": "Prof. Mark Stevens",
                "notes": "OS trend favorable but boundary not crossed at 40% events. Continue enrollment.",
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "DSMB-010",
                "trial_id": LIBTAYO_TRIAL,
                "data_cut_id": "DCT-010",
                "meeting_date": now - timedelta(days=35),
                "meeting_number": 2,
                "dsmb_recommendation": DSMBRecommendation.CONTINUE_AS_PLANNED,
                "attendees_count": 8,
                "quorum_met": True,
                "safety_concerns_raised": False,
                "efficacy_signal_detected": True,
                "minutes_document_id": "DOC-DSMB-010",
                "letter_sent_date": now - timedelta(days=32),
                "sponsor_notified_date": now - timedelta(days=30),
                "chair_name": "Prof. Mark Stevens",
                "notes": "PFS results highly encouraging. OS analysis to follow at next milestone.",
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "DSMB-011",
                "trial_id": LIBTAYO_TRIAL,
                "data_cut_id": "DCT-011",
                "meeting_date": now - timedelta(days=55),
                "meeting_number": 3,
                "dsmb_recommendation": DSMBRecommendation.STOP_FOR_SAFETY,
                "attendees_count": 9,
                "quorum_met": True,
                "safety_concerns_raised": True,
                "efficacy_signal_detected": False,
                "minutes_document_id": "DOC-DSMB-011",
                "letter_sent_date": now - timedelta(days=53),
                "sponsor_notified_date": now - timedelta(days=52),
                "chair_name": "Prof. Mark Stevens",
                "notes": "Elevated Grade 4+ irAE rate in combination arm. Recommended stopping combination cohort.",
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "DSMB-012",
                "trial_id": LIBTAYO_TRIAL,
                "data_cut_id": "DCT-012",
                "meeting_date": now - timedelta(days=15),
                "meeting_number": 4,
                "dsmb_recommendation": DSMBRecommendation.STOP_FOR_FUTILITY,
                "attendees_count": 7,
                "quorum_met": False,
                "safety_concerns_raised": False,
                "efficacy_signal_detected": False,
                "minutes_document_id": None,
                "letter_sent_date": None,
                "sponsor_notified_date": None,
                "chair_name": "Prof. Mark Stevens",
                "notes": "Combination cohort futility assessment. Quorum not met; recommendation advisory only.",
                "created_at": now - timedelta(days=15),
            },
        ]

        for d in dsmb_data:
            self._dsmb_reviews[d["id"]] = DSMBReview(**d)

        # --- 12 Statistical Review Outcomes ---
        outcomes_data = [
            {
                "id": "SRO-001",
                "trial_id": EYLEA_TRIAL,
                "data_cut_id": "DCT-001",
                "dsmb_review_id": "DSMB-001",
                "review_outcome": ReviewOutcome.NO_SIGNAL,
                "test_statistic": 1.45,
                "p_value": 0.147,
                "confidence_interval_lower": -0.5,
                "confidence_interval_upper": 3.2,
                "effect_size": 1.35,
                "conditional_power": 0.72,
                "predictive_probability": 0.68,
                "sample_size_reestimation": False,
                "reviewed_by": "Dr. Wei Zhang",
                "review_date": now - timedelta(days=86),
                "notes": "No efficacy signal at first interim. Conditional power supports continuation.",
                "created_at": now - timedelta(days=86),
            },
            {
                "id": "SRO-002",
                "trial_id": EYLEA_TRIAL,
                "data_cut_id": "DCT-003",
                "dsmb_review_id": "DSMB-002",
                "review_outcome": ReviewOutcome.NO_SIGNAL,
                "test_statistic": 0.85,
                "p_value": 0.395,
                "confidence_interval_lower": -1.2,
                "confidence_interval_upper": 2.8,
                "effect_size": 0.80,
                "conditional_power": 0.55,
                "predictive_probability": 0.50,
                "sample_size_reestimation": False,
                "reviewed_by": "Dr. Jennifer Liu",
                "review_date": now - timedelta(days=96),
                "notes": "Futility boundary not crossed. Conditional power borderline but adequate.",
                "created_at": now - timedelta(days=96),
            },
            {
                "id": "SRO-003",
                "trial_id": EYLEA_TRIAL,
                "data_cut_id": "DCT-004",
                "dsmb_review_id": "DSMB-003",
                "review_outcome": ReviewOutcome.INCONCLUSIVE,
                "test_statistic": None,
                "p_value": None,
                "confidence_interval_lower": None,
                "confidence_interval_upper": None,
                "effect_size": None,
                "conditional_power": None,
                "predictive_probability": None,
                "sample_size_reestimation": False,
                "reviewed_by": "Dr. Jennifer Liu",
                "review_date": now - timedelta(days=76),
                "notes": "Safety review only. No formal efficacy hypothesis testing performed.",
                "created_at": now - timedelta(days=76),
            },
            {
                "id": "SRO-004",
                "trial_id": EYLEA_TRIAL,
                "data_cut_id": "DCT-001",
                "dsmb_review_id": "DSMB-004",
                "review_outcome": ReviewOutcome.DEFERRED,
                "test_statistic": None,
                "p_value": None,
                "confidence_interval_lower": None,
                "confidence_interval_upper": None,
                "effect_size": None,
                "conditional_power": None,
                "predictive_probability": None,
                "sample_size_reestimation": True,
                "reviewed_by": "Dr. Wei Zhang",
                "review_date": now - timedelta(days=56),
                "notes": "Outcome deferred pending additional safety data. Sample size reestimation triggered.",
                "created_at": now - timedelta(days=56),
            },
            {
                "id": "SRO-005",
                "trial_id": DUPIXENT_TRIAL,
                "data_cut_id": "DCT-005",
                "dsmb_review_id": "DSMB-005",
                "review_outcome": ReviewOutcome.FAVORABLE,
                "test_statistic": 2.85,
                "p_value": 0.004,
                "confidence_interval_lower": 8.5,
                "confidence_interval_upper": 22.3,
                "effect_size": 15.4,
                "conditional_power": 0.95,
                "predictive_probability": 0.92,
                "sample_size_reestimation": False,
                "reviewed_by": "Dr. Michael Ross",
                "review_date": now - timedelta(days=66),
                "notes": "Strong efficacy signal. EASI-75 difference 15.4% favoring treatment. Boundary not crossed.",
                "created_at": now - timedelta(days=66),
            },
            {
                "id": "SRO-006",
                "trial_id": DUPIXENT_TRIAL,
                "data_cut_id": "DCT-006",
                "dsmb_review_id": "DSMB-006",
                "review_outcome": ReviewOutcome.BOUNDARY_CROSSED,
                "test_statistic": 3.92,
                "p_value": 0.00009,
                "confidence_interval_lower": 12.1,
                "confidence_interval_upper": 28.7,
                "effect_size": 20.4,
                "conditional_power": 0.99,
                "predictive_probability": 0.98,
                "sample_size_reestimation": False,
                "reviewed_by": "Dr. Michael Ross",
                "review_date": now - timedelta(days=61),
                "notes": "Haybittle-Peto boundary crossed (p<0.001). Overwhelming efficacy confirmed.",
                "created_at": now - timedelta(days=61),
            },
            {
                "id": "SRO-007",
                "trial_id": DUPIXENT_TRIAL,
                "data_cut_id": "DCT-007",
                "dsmb_review_id": "DSMB-007",
                "review_outcome": ReviewOutcome.NO_SIGNAL,
                "test_statistic": None,
                "p_value": None,
                "confidence_interval_lower": None,
                "confidence_interval_upper": None,
                "effect_size": None,
                "conditional_power": None,
                "predictive_probability": None,
                "sample_size_reestimation": False,
                "reviewed_by": "Dr. Anna Patel",
                "review_date": now - timedelta(days=46),
                "notes": "Safety review only. Conjunctivitis and injection site reactions within expected ranges.",
                "created_at": now - timedelta(days=46),
            },
            {
                "id": "SRO-008",
                "trial_id": DUPIXENT_TRIAL,
                "data_cut_id": "DCT-005",
                "dsmb_review_id": "DSMB-008",
                "review_outcome": ReviewOutcome.FAVORABLE,
                "test_statistic": 3.10,
                "p_value": 0.002,
                "confidence_interval_lower": 10.0,
                "confidence_interval_upper": 24.5,
                "effect_size": 17.2,
                "conditional_power": 0.97,
                "predictive_probability": 0.94,
                "sample_size_reestimation": False,
                "reviewed_by": "Dr. Michael Ross",
                "review_date": now - timedelta(days=31),
                "notes": "Continued favorable trend in follow-up data. Consistent with prior findings.",
                "created_at": now - timedelta(days=31),
            },
            {
                "id": "SRO-009",
                "trial_id": LIBTAYO_TRIAL,
                "data_cut_id": "DCT-009",
                "dsmb_review_id": "DSMB-009",
                "review_outcome": ReviewOutcome.FAVORABLE,
                "test_statistic": 2.20,
                "p_value": 0.028,
                "confidence_interval_lower": 0.52,
                "confidence_interval_upper": 0.88,
                "effect_size": 0.68,
                "conditional_power": 0.82,
                "predictive_probability": 0.78,
                "sample_size_reestimation": False,
                "reviewed_by": "Dr. David Kim",
                "review_date": now - timedelta(days=41),
                "notes": "OS HR 0.68 favoring treatment. O'Brien-Fleming boundary not crossed at this interim.",
                "created_at": now - timedelta(days=41),
            },
            {
                "id": "SRO-010",
                "trial_id": LIBTAYO_TRIAL,
                "data_cut_id": "DCT-010",
                "dsmb_review_id": "DSMB-010",
                "review_outcome": ReviewOutcome.BOUNDARY_CROSSED,
                "test_statistic": 3.45,
                "p_value": 0.0006,
                "confidence_interval_lower": 0.42,
                "confidence_interval_upper": 0.72,
                "effect_size": 0.55,
                "conditional_power": 0.98,
                "predictive_probability": 0.96,
                "sample_size_reestimation": False,
                "reviewed_by": "Dr. David Kim",
                "review_date": now - timedelta(days=36),
                "notes": "PFS boundary crossed. HR 0.55 with highly significant p-value.",
                "created_at": now - timedelta(days=36),
            },
            {
                "id": "SRO-011",
                "trial_id": LIBTAYO_TRIAL,
                "data_cut_id": "DCT-011",
                "dsmb_review_id": "DSMB-011",
                "review_outcome": ReviewOutcome.UNFAVORABLE,
                "test_statistic": None,
                "p_value": None,
                "confidence_interval_lower": None,
                "confidence_interval_upper": None,
                "effect_size": None,
                "conditional_power": 0.15,
                "predictive_probability": 0.10,
                "sample_size_reestimation": False,
                "reviewed_by": "Dr. Anna Patel",
                "review_date": now - timedelta(days=56),
                "notes": "Combination arm safety profile unacceptable. Grade 4+ irAE rate 35% vs expected <15%.",
                "created_at": now - timedelta(days=56),
            },
            {
                "id": "SRO-012",
                "trial_id": LIBTAYO_TRIAL,
                "data_cut_id": "DCT-012",
                "dsmb_review_id": "DSMB-012",
                "review_outcome": ReviewOutcome.INCONCLUSIVE,
                "test_statistic": 0.45,
                "p_value": 0.653,
                "confidence_interval_lower": 0.75,
                "confidence_interval_upper": 1.45,
                "effect_size": 1.05,
                "conditional_power": 0.08,
                "predictive_probability": 0.05,
                "sample_size_reestimation": False,
                "reviewed_by": "Dr. David Kim",
                "review_date": now - timedelta(days=16),
                "notes": "Combination cohort futility threshold met. Very low conditional power.",
                "created_at": now - timedelta(days=16),
            },
        ]

        for o in outcomes_data:
            self._statistical_review_outcomes[o["id"]] = StatisticalReviewOutcome(**o)

    # ------------------------------------------------------------------
    # Analysis Plans
    # ------------------------------------------------------------------

    def list_analysis_plans(
        self,
        *,
        trial_id: str | None = None,
        analysis_plan_status: AnalysisPlanStatus | None = None,
    ) -> list[AnalysisPlan]:
        """List analysis plans with optional filters."""
        with self._lock:
            result = list(self._analysis_plans.values())

        if trial_id is not None:
            result = [p for p in result if p.trial_id == trial_id]
        if analysis_plan_status is not None:
            result = [p for p in result if p.analysis_plan_status == analysis_plan_status]

        return sorted(result, key=lambda p: p.created_at, reverse=True)

    def get_analysis_plan(self, plan_id: str) -> AnalysisPlan | None:
        """Get a single analysis plan by ID."""
        with self._lock:
            return self._analysis_plans.get(plan_id)

    def create_analysis_plan(self, payload: AnalysisPlanCreate) -> AnalysisPlan:
        """Create a new analysis plan."""
        now = datetime.now(timezone.utc)
        plan_id = f"IAP-{uuid4().hex[:8].upper()}"
        record = AnalysisPlan(
            id=plan_id,
            trial_id=payload.trial_id,
            plan_name=payload.plan_name,
            version=payload.version,
            analysis_plan_status=AnalysisPlanStatus.DRAFT,
            planned_analyses_count=payload.planned_analyses_count,
            primary_endpoint=payload.primary_endpoint,
            secondary_endpoints=None,
            alpha_spending_function=None,
            information_fraction=None,
            stopping_boundaries=None,
            authored_by=payload.authored_by,
            approved_by=None,
            approval_date=None,
            effective_date=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._analysis_plans[plan_id] = record
        logger.info("Created analysis plan %s for trial %s", plan_id, payload.trial_id)
        return record

    def update_analysis_plan(
        self, plan_id: str, payload: AnalysisPlanUpdate
    ) -> AnalysisPlan | None:
        """Update an existing analysis plan."""
        with self._lock:
            existing = self._analysis_plans.get(plan_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = AnalysisPlan(**data)
            self._analysis_plans[plan_id] = updated
        return updated

    def delete_analysis_plan(self, plan_id: str) -> bool:
        """Delete an analysis plan. Returns True if deleted."""
        with self._lock:
            if plan_id in self._analysis_plans:
                del self._analysis_plans[plan_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Data Cut Definitions
    # ------------------------------------------------------------------

    def list_data_cut_definitions(
        self,
        *,
        trial_id: str | None = None,
        data_cut_status: DataCutStatus | None = None,
        analysis_plan_id: str | None = None,
    ) -> list[DataCutDefinition]:
        """List data cut definitions with optional filters."""
        with self._lock:
            result = list(self._data_cut_definitions.values())

        if trial_id is not None:
            result = [d for d in result if d.trial_id == trial_id]
        if data_cut_status is not None:
            result = [d for d in result if d.data_cut_status == data_cut_status]
        if analysis_plan_id is not None:
            result = [d for d in result if d.analysis_plan_id == analysis_plan_id]

        return sorted(result, key=lambda d: d.created_at, reverse=True)

    def get_data_cut_definition(self, cut_id: str) -> DataCutDefinition | None:
        """Get a single data cut definition by ID."""
        with self._lock:
            return self._data_cut_definitions.get(cut_id)

    def create_data_cut_definition(self, payload: DataCutDefinitionCreate) -> DataCutDefinition:
        """Create a new data cut definition."""
        now = datetime.now(timezone.utc)
        cut_id = f"DCT-{uuid4().hex[:8].upper()}"
        record = DataCutDefinition(
            id=cut_id,
            trial_id=payload.trial_id,
            analysis_plan_id=payload.analysis_plan_id,
            cut_name=payload.cut_name,
            data_cut_status=DataCutStatus.PLANNED,
            cut_date=None,
            target_enrollment=payload.target_enrollment,
            actual_enrollment=0,
            target_events=payload.target_events,
            actual_events=0,
            blinding_status=BlindingStatus.FULLY_BLINDED,
            database_lock_date=None,
            data_transfer_date=None,
            responsible_statistician=payload.responsible_statistician,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._data_cut_definitions[cut_id] = record
        logger.info("Created data cut definition %s for trial %s", cut_id, payload.trial_id)
        return record

    def update_data_cut_definition(
        self, cut_id: str, payload: DataCutDefinitionUpdate
    ) -> DataCutDefinition | None:
        """Update an existing data cut definition."""
        with self._lock:
            existing = self._data_cut_definitions.get(cut_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DataCutDefinition(**data)
            self._data_cut_definitions[cut_id] = updated
        return updated

    def delete_data_cut_definition(self, cut_id: str) -> bool:
        """Delete a data cut definition. Returns True if deleted."""
        with self._lock:
            if cut_id in self._data_cut_definitions:
                del self._data_cut_definitions[cut_id]
                return True
            return False

    # ------------------------------------------------------------------
    # DSMB Reviews
    # ------------------------------------------------------------------

    def list_dsmb_reviews(
        self,
        *,
        trial_id: str | None = None,
        dsmb_recommendation: DSMBRecommendation | None = None,
        data_cut_id: str | None = None,
    ) -> list[DSMBReview]:
        """List DSMB reviews with optional filters."""
        with self._lock:
            result = list(self._dsmb_reviews.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if dsmb_recommendation is not None:
            result = [r for r in result if r.dsmb_recommendation == dsmb_recommendation]
        if data_cut_id is not None:
            result = [r for r in result if r.data_cut_id == data_cut_id]

        return sorted(result, key=lambda r: r.meeting_date, reverse=True)

    def get_dsmb_review(self, review_id: str) -> DSMBReview | None:
        """Get a single DSMB review by ID."""
        with self._lock:
            return self._dsmb_reviews.get(review_id)

    def create_dsmb_review(self, payload: DSMBReviewCreate) -> DSMBReview:
        """Create a new DSMB review."""
        now = datetime.now(timezone.utc)
        review_id = f"DSMB-{uuid4().hex[:8].upper()}"
        record = DSMBReview(
            id=review_id,
            trial_id=payload.trial_id,
            data_cut_id=payload.data_cut_id,
            meeting_date=payload.meeting_date,
            meeting_number=payload.meeting_number,
            dsmb_recommendation=DSMBRecommendation.CONTINUE_AS_PLANNED,
            attendees_count=payload.attendees_count,
            quorum_met=True,
            safety_concerns_raised=False,
            efficacy_signal_detected=False,
            minutes_document_id=None,
            letter_sent_date=None,
            sponsor_notified_date=None,
            chair_name=payload.chair_name,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._dsmb_reviews[review_id] = record
        logger.info("Created DSMB review %s for trial %s", review_id, payload.trial_id)
        return record

    def update_dsmb_review(
        self, review_id: str, payload: DSMBReviewUpdate
    ) -> DSMBReview | None:
        """Update an existing DSMB review."""
        with self._lock:
            existing = self._dsmb_reviews.get(review_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DSMBReview(**data)
            self._dsmb_reviews[review_id] = updated
        return updated

    def delete_dsmb_review(self, review_id: str) -> bool:
        """Delete a DSMB review. Returns True if deleted."""
        with self._lock:
            if review_id in self._dsmb_reviews:
                del self._dsmb_reviews[review_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Statistical Review Outcomes
    # ------------------------------------------------------------------

    def list_statistical_review_outcomes(
        self,
        *,
        trial_id: str | None = None,
        review_outcome: ReviewOutcome | None = None,
        data_cut_id: str | None = None,
    ) -> list[StatisticalReviewOutcome]:
        """List statistical review outcomes with optional filters."""
        with self._lock:
            result = list(self._statistical_review_outcomes.values())

        if trial_id is not None:
            result = [o for o in result if o.trial_id == trial_id]
        if review_outcome is not None:
            result = [o for o in result if o.review_outcome == review_outcome]
        if data_cut_id is not None:
            result = [o for o in result if o.data_cut_id == data_cut_id]

        return sorted(result, key=lambda o: o.review_date, reverse=True)

    def get_statistical_review_outcome(self, outcome_id: str) -> StatisticalReviewOutcome | None:
        """Get a single statistical review outcome by ID."""
        with self._lock:
            return self._statistical_review_outcomes.get(outcome_id)

    def create_statistical_review_outcome(
        self, payload: StatisticalReviewOutcomeCreate
    ) -> StatisticalReviewOutcome:
        """Create a new statistical review outcome."""
        now = datetime.now(timezone.utc)
        outcome_id = f"SRO-{uuid4().hex[:8].upper()}"
        record = StatisticalReviewOutcome(
            id=outcome_id,
            trial_id=payload.trial_id,
            data_cut_id=payload.data_cut_id,
            dsmb_review_id=payload.dsmb_review_id,
            review_outcome=ReviewOutcome.INCONCLUSIVE,
            test_statistic=None,
            p_value=None,
            confidence_interval_lower=None,
            confidence_interval_upper=None,
            effect_size=None,
            conditional_power=None,
            predictive_probability=None,
            sample_size_reestimation=False,
            reviewed_by=payload.reviewed_by,
            review_date=payload.review_date,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._statistical_review_outcomes[outcome_id] = record
        logger.info("Created statistical review outcome %s for trial %s", outcome_id, payload.trial_id)
        return record

    def update_statistical_review_outcome(
        self, outcome_id: str, payload: StatisticalReviewOutcomeUpdate
    ) -> StatisticalReviewOutcome | None:
        """Update an existing statistical review outcome."""
        with self._lock:
            existing = self._statistical_review_outcomes.get(outcome_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = StatisticalReviewOutcome(**data)
            self._statistical_review_outcomes[outcome_id] = updated
        return updated

    def delete_statistical_review_outcome(self, outcome_id: str) -> bool:
        """Delete a statistical review outcome. Returns True if deleted."""
        with self._lock:
            if outcome_id in self._statistical_review_outcomes:
                del self._statistical_review_outcomes[outcome_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> InterimAnalysisMetrics:
        """Compute aggregated interim analysis metrics, optionally filtered by trial."""
        with self._lock:
            plans = list(self._analysis_plans.values())
            cuts = list(self._data_cut_definitions.values())
            reviews = list(self._dsmb_reviews.values())
            outcomes = list(self._statistical_review_outcomes.values())

        if trial_id is not None:
            plans = [p for p in plans if p.trial_id == trial_id]
            cuts = [d for d in cuts if d.trial_id == trial_id]
            reviews = [r for r in reviews if r.trial_id == trial_id]
            outcomes = [o for o in outcomes if o.trial_id == trial_id]

        # Plans by status
        plans_by_status: dict[str, int] = {}
        for p in plans:
            key = p.analysis_plan_status.value
            plans_by_status[key] = plans_by_status.get(key, 0) + 1

        # Cuts by status
        cuts_by_status: dict[str, int] = {}
        for d in cuts:
            key = d.data_cut_status.value
            cuts_by_status[key] = cuts_by_status.get(key, 0) + 1

        # Data cut completion rate
        completed_cuts = sum(
            1
            for d in cuts
            if d.data_cut_status in (DataCutStatus.COMPLETED, DataCutStatus.VALIDATED, DataCutStatus.RELEASED)
        )
        data_cut_completion_rate = round(
            (completed_cuts / max(1, len(cuts))) * 100, 1
        )

        # Reviews by recommendation
        reviews_by_recommendation: dict[str, int] = {}
        for r in reviews:
            key = r.dsmb_recommendation.value
            reviews_by_recommendation[key] = reviews_by_recommendation.get(key, 0) + 1

        # Outcomes by result
        outcomes_by_result: dict[str, int] = {}
        for o in outcomes:
            key = o.review_outcome.value
            outcomes_by_result[key] = outcomes_by_result.get(key, 0) + 1

        # Boundary crossing rate
        boundary_crossings = sum(
            1 for o in outcomes if o.review_outcome == ReviewOutcome.BOUNDARY_CROSSED
        )
        boundary_crossing_rate = round(
            (boundary_crossings / max(1, len(outcomes))) * 100, 1
        )

        return InterimAnalysisMetrics(
            total_analysis_plans=len(plans),
            plans_by_status=plans_by_status,
            total_data_cuts=len(cuts),
            cuts_by_status=cuts_by_status,
            data_cut_completion_rate=data_cut_completion_rate,
            total_dsmb_reviews=len(reviews),
            reviews_by_recommendation=reviews_by_recommendation,
            total_statistical_outcomes=len(outcomes),
            outcomes_by_result=outcomes_by_result,
            boundary_crossing_rate=boundary_crossing_rate,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: InterimAnalysisService | None = None
_instance_lock = threading.Lock()


def get_interim_analysis_service() -> InterimAnalysisService:
    """Return the singleton InterimAnalysisService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = InterimAnalysisService()
    return _instance


def reset_interim_analysis_service() -> InterimAnalysisService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = InterimAnalysisService()
    return _instance
