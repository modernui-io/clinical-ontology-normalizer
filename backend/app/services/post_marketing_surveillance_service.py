"""Post-Marketing Surveillance (PMS) Service.

Manages post-marketing surveillance operations: safety signal tracking,
periodic safety update reports (PSURs), risk management plan updates,
product quality review, and post-marketing commitment tracking with
PMS metrics.

Usage:
    from app.services.post_marketing_surveillance_service import (
        get_post_marketing_surveillance_service,
    )

    svc = get_post_marketing_surveillance_service()
    signals = svc.list_safety_signals()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.post_marketing_surveillance import (
    CommitmentType,
    PostMarketingCommitment,
    PostMarketingCommitmentCreate,
    PostMarketingCommitmentUpdate,
    PostMarketingSurveillanceMetrics,
    ProductQualityReview,
    ProductQualityReviewCreate,
    ProductQualityReviewUpdate,
    PSURRecord,
    PSURRecordCreate,
    PSURRecordUpdate,
    PSURStatus,
    RiskCategory,
    RiskManagementPlan,
    RiskManagementPlanCreate,
    RiskManagementPlanUpdate,
    SafetySignalTracker,
    SafetySignalTrackerCreate,
    SafetySignalTrackerUpdate,
    SignalSource,
    SignalStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class PostMarketingSurveillanceService:
    """In-memory Post-Marketing Surveillance engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._safety_signals: dict[str, SafetySignalTracker] = {}
        self._psur_records: dict[str, PSURRecord] = {}
        self._risk_management_plans: dict[str, RiskManagementPlan] = {}
        self._product_quality_reviews: dict[str, ProductQualityReview] = {}
        self._post_marketing_commitments: dict[str, PostMarketingCommitment] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic post-marketing surveillance data."""
        now = datetime.now(timezone.utc)

        # --- 12 Safety Signals ---
        signals_data = [
            {
                "id": "SIG-001",
                "trial_id": EYLEA_TRIAL,
                "signal_name": "Endophthalmitis post-injection",
                "signal_source": SignalSource.SPONTANEOUS_REPORT,
                "status": SignalStatus.CONFIRMED,
                "detection_date": now - timedelta(days=365),
                "product_name": "EYLEA (aflibercept)",
                "event_term": "Endophthalmitis",
                "meddra_pt": "Endophthalmitis",
                "case_count": 47,
                "reporting_rate": 0.08,
                "pro_score": 3.2,
                "disproportionality_score": 2.85,
                "clinical_significance": "Serious - requires immediate treatment",
                "regulatory_impact": True,
                "label_change_needed": True,
                "assessed_by": "Dr. Sarah Chen",
                "notes": "Confirmed signal. Label updated to reflect risk.",
                "created_at": now - timedelta(days=365),
            },
            {
                "id": "SIG-002",
                "trial_id": EYLEA_TRIAL,
                "signal_name": "Retinal detachment",
                "signal_source": SignalSource.CLINICAL_TRIAL,
                "status": SignalStatus.UNDER_EVALUATION,
                "detection_date": now - timedelta(days=180),
                "product_name": "EYLEA (aflibercept)",
                "event_term": "Retinal detachment",
                "meddra_pt": "Retinal detachment",
                "case_count": 12,
                "reporting_rate": 0.02,
                "pro_score": 2.1,
                "disproportionality_score": 1.95,
                "clinical_significance": "Serious - under evaluation",
                "regulatory_impact": False,
                "label_change_needed": False,
                "assessed_by": "Dr. James Wright",
                "notes": "Evaluating whether rate exceeds background incidence.",
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "SIG-003",
                "trial_id": EYLEA_TRIAL,
                "signal_name": "Intraocular pressure increase",
                "signal_source": SignalSource.REGISTRY,
                "status": SignalStatus.MONITORING,
                "detection_date": now - timedelta(days=120),
                "product_name": "EYLEA (aflibercept)",
                "event_term": "Intraocular pressure increased",
                "meddra_pt": "Intraocular pressure increased",
                "case_count": 85,
                "reporting_rate": 0.14,
                "pro_score": 1.8,
                "disproportionality_score": 1.52,
                "clinical_significance": "Known class effect - monitoring",
                "regulatory_impact": False,
                "label_change_needed": False,
                "assessed_by": "Dr. Sarah Chen",
                "notes": "Already in label. Monitoring for rate changes.",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "SIG-004",
                "trial_id": EYLEA_TRIAL,
                "signal_name": "Arterial thromboembolic events",
                "signal_source": SignalSource.LITERATURE,
                "status": SignalStatus.REFUTED,
                "detection_date": now - timedelta(days=400),
                "product_name": "EYLEA (aflibercept)",
                "event_term": "Cerebrovascular accident",
                "meddra_pt": "Cerebrovascular accident",
                "case_count": 8,
                "reporting_rate": 0.01,
                "pro_score": 0.9,
                "disproportionality_score": 0.78,
                "clinical_significance": "Not confirmed after thorough evaluation",
                "regulatory_impact": False,
                "label_change_needed": False,
                "assessed_by": "Dr. James Wright",
                "notes": "Refuted - rate consistent with background in elderly population.",
                "created_at": now - timedelta(days=400),
            },
            {
                "id": "SIG-005",
                "trial_id": DUPIXENT_TRIAL,
                "signal_name": "Conjunctivitis",
                "signal_source": SignalSource.SPONTANEOUS_REPORT,
                "status": SignalStatus.CONFIRMED,
                "detection_date": now - timedelta(days=300),
                "product_name": "DUPIXENT (dupilumab)",
                "event_term": "Conjunctivitis",
                "meddra_pt": "Conjunctivitis",
                "case_count": 234,
                "reporting_rate": 0.32,
                "pro_score": 4.1,
                "disproportionality_score": 3.95,
                "clinical_significance": "Common - included in labeling",
                "regulatory_impact": True,
                "label_change_needed": False,
                "assessed_by": "Dr. Maria Lopez",
                "notes": "Confirmed known risk. Monitoring ongoing.",
                "created_at": now - timedelta(days=300),
            },
            {
                "id": "SIG-006",
                "trial_id": DUPIXENT_TRIAL,
                "signal_name": "Eosinophilic granulomatosis",
                "signal_source": SignalSource.HEALTH_AUTHORITY,
                "status": SignalStatus.UNDER_EVALUATION,
                "detection_date": now - timedelta(days=90),
                "product_name": "DUPIXENT (dupilumab)",
                "event_term": "Eosinophilic granulomatosis with polyangiitis",
                "meddra_pt": "Eosinophilic granulomatosis with polyangiitis",
                "case_count": 18,
                "reporting_rate": 0.02,
                "pro_score": 2.8,
                "disproportionality_score": 2.45,
                "clinical_significance": "Serious - potential class effect",
                "regulatory_impact": True,
                "label_change_needed": False,
                "assessed_by": "Dr. Maria Lopez",
                "notes": "FDA requested evaluation after FAERS signal detection.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "SIG-007",
                "trial_id": DUPIXENT_TRIAL,
                "signal_name": "Arthralgia",
                "signal_source": SignalSource.SOCIAL_MEDIA,
                "status": SignalStatus.DETECTED,
                "detection_date": now - timedelta(days=45),
                "product_name": "DUPIXENT (dupilumab)",
                "event_term": "Arthralgia",
                "meddra_pt": "Arthralgia",
                "case_count": 56,
                "reporting_rate": 0.08,
                "pro_score": 1.5,
                "disproportionality_score": 1.22,
                "clinical_significance": None,
                "regulatory_impact": False,
                "label_change_needed": False,
                "assessed_by": "Dr. Robert Kim",
                "notes": "Detected via social media monitoring. Formal evaluation pending.",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "SIG-008",
                "trial_id": DUPIXENT_TRIAL,
                "signal_name": "Injection site reactions",
                "signal_source": SignalSource.CLINICAL_TRIAL,
                "status": SignalStatus.CLOSED,
                "detection_date": now - timedelta(days=500),
                "product_name": "DUPIXENT (dupilumab)",
                "event_term": "Injection site reaction",
                "meddra_pt": "Injection site reaction",
                "case_count": 412,
                "reporting_rate": 0.56,
                "pro_score": 1.2,
                "disproportionality_score": 1.05,
                "clinical_significance": "Known, non-serious, well-characterized",
                "regulatory_impact": False,
                "label_change_needed": False,
                "assessed_by": "Dr. Maria Lopez",
                "notes": "Closed - well-characterized known reaction in labeling.",
                "created_at": now - timedelta(days=500),
            },
            {
                "id": "SIG-009",
                "trial_id": LIBTAYO_TRIAL,
                "signal_name": "Immune-mediated hepatitis",
                "signal_source": SignalSource.SPONTANEOUS_REPORT,
                "status": SignalStatus.CONFIRMED,
                "detection_date": now - timedelta(days=220),
                "product_name": "LIBTAYO (cemiplimab)",
                "event_term": "Hepatitis",
                "meddra_pt": "Autoimmune hepatitis",
                "case_count": 35,
                "reporting_rate": 0.12,
                "pro_score": 3.6,
                "disproportionality_score": 3.15,
                "clinical_significance": "Serious immune-related adverse event",
                "regulatory_impact": True,
                "label_change_needed": True,
                "assessed_by": "Dr. Angela Park",
                "notes": "Confirmed. REMS updated. Label strengthened.",
                "created_at": now - timedelta(days=220),
            },
            {
                "id": "SIG-010",
                "trial_id": LIBTAYO_TRIAL,
                "signal_name": "Pneumonitis",
                "signal_source": SignalSource.CLINICAL_TRIAL,
                "status": SignalStatus.MONITORING,
                "detection_date": now - timedelta(days=160),
                "product_name": "LIBTAYO (cemiplimab)",
                "event_term": "Pneumonitis",
                "meddra_pt": "Pneumonitis",
                "case_count": 28,
                "reporting_rate": 0.09,
                "pro_score": 3.1,
                "disproportionality_score": 2.78,
                "clinical_significance": "Known checkpoint inhibitor class effect",
                "regulatory_impact": False,
                "label_change_needed": False,
                "assessed_by": "Dr. Angela Park",
                "notes": "Known class effect. Active monitoring for rate changes.",
                "created_at": now - timedelta(days=160),
            },
            {
                "id": "SIG-011",
                "trial_id": LIBTAYO_TRIAL,
                "signal_name": "Hypothyroidism",
                "signal_source": SignalSource.REGISTRY,
                "status": SignalStatus.CONFIRMED,
                "detection_date": now - timedelta(days=280),
                "product_name": "LIBTAYO (cemiplimab)",
                "event_term": "Hypothyroidism",
                "meddra_pt": "Hypothyroidism",
                "case_count": 92,
                "reporting_rate": 0.31,
                "pro_score": 2.4,
                "disproportionality_score": 2.10,
                "clinical_significance": "Common immune-related endocrinopathy",
                "regulatory_impact": False,
                "label_change_needed": False,
                "assessed_by": "Dr. William Torres",
                "notes": "Confirmed. Already in labeling. Monitoring continues.",
                "created_at": now - timedelta(days=280),
            },
            {
                "id": "SIG-012",
                "trial_id": LIBTAYO_TRIAL,
                "signal_name": "Myocarditis",
                "signal_source": SignalSource.HEALTH_AUTHORITY,
                "status": SignalStatus.DETECTED,
                "detection_date": now - timedelta(days=30),
                "product_name": "LIBTAYO (cemiplimab)",
                "event_term": "Myocarditis",
                "meddra_pt": "Myocarditis",
                "case_count": 5,
                "reporting_rate": 0.02,
                "pro_score": None,
                "disproportionality_score": None,
                "clinical_significance": None,
                "regulatory_impact": False,
                "label_change_needed": False,
                "assessed_by": "Dr. Angela Park",
                "notes": "EMA signal detected. Initial evaluation underway.",
                "created_at": now - timedelta(days=30),
            },
        ]

        for s in signals_data:
            self._safety_signals[s["id"]] = SafetySignalTracker(**s)

        # --- 12 PSUR Records ---
        psur_data = [
            {
                "id": "PSUR-001",
                "trial_id": EYLEA_TRIAL,
                "psur_number": 1,
                "reporting_period_start": now - timedelta(days=730),
                "reporting_period_end": now - timedelta(days=365),
                "status": PSURStatus.ACKNOWLEDGED,
                "product_name": "EYLEA (aflibercept)",
                "submission_date": now - timedelta(days=335),
                "submission_deadline": now - timedelta(days=335),
                "regulatory_authority": "FDA",
                "total_cases_reviewed": 1245,
                "new_signals_identified": 2,
                "benefit_risk_conclusion": "favorable",
                "label_changes_proposed": 1,
                "prepared_by": "Dr. Sarah Chen",
                "reviewed_by": "Dr. James Wright",
                "notes": "First PSUR cycle. One label update for endophthalmitis risk.",
                "created_at": now - timedelta(days=380),
            },
            {
                "id": "PSUR-002",
                "trial_id": EYLEA_TRIAL,
                "psur_number": 2,
                "reporting_period_start": now - timedelta(days=365),
                "reporting_period_end": now - timedelta(days=1),
                "status": PSURStatus.DRAFTING,
                "product_name": "EYLEA (aflibercept)",
                "submission_date": None,
                "submission_deadline": now + timedelta(days=30),
                "regulatory_authority": "FDA",
                "total_cases_reviewed": 890,
                "new_signals_identified": 1,
                "benefit_risk_conclusion": "favorable",
                "label_changes_proposed": 0,
                "prepared_by": "Dr. Sarah Chen",
                "reviewed_by": None,
                "notes": "Second cycle in progress. IOP signal under monitoring.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "PSUR-003",
                "trial_id": EYLEA_TRIAL,
                "psur_number": 3,
                "reporting_period_start": now - timedelta(days=730),
                "reporting_period_end": now - timedelta(days=365),
                "status": PSURStatus.SUBMITTED,
                "product_name": "EYLEA (aflibercept)",
                "submission_date": now - timedelta(days=340),
                "submission_deadline": now - timedelta(days=335),
                "regulatory_authority": "EMA",
                "total_cases_reviewed": 2310,
                "new_signals_identified": 2,
                "benefit_risk_conclusion": "favorable",
                "label_changes_proposed": 1,
                "prepared_by": "Dr. Sarah Chen",
                "reviewed_by": "Dr. James Wright",
                "notes": "EMA submission aligned with FDA PSUR cycle.",
                "created_at": now - timedelta(days=385),
            },
            {
                "id": "PSUR-004",
                "trial_id": EYLEA_TRIAL,
                "psur_number": 4,
                "reporting_period_start": now - timedelta(days=365),
                "reporting_period_end": now - timedelta(days=1),
                "status": PSURStatus.PLANNING,
                "product_name": "EYLEA (aflibercept)",
                "submission_date": None,
                "submission_deadline": now + timedelta(days=60),
                "regulatory_authority": "EMA",
                "total_cases_reviewed": 0,
                "new_signals_identified": 0,
                "benefit_risk_conclusion": "favorable",
                "label_changes_proposed": 0,
                "prepared_by": "Dr. James Wright",
                "reviewed_by": None,
                "notes": "EMA cycle 2 planning phase.",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "PSUR-005",
                "trial_id": DUPIXENT_TRIAL,
                "psur_number": 1,
                "reporting_period_start": now - timedelta(days=730),
                "reporting_period_end": now - timedelta(days=365),
                "status": PSURStatus.ACKNOWLEDGED,
                "product_name": "DUPIXENT (dupilumab)",
                "submission_date": now - timedelta(days=330),
                "submission_deadline": now - timedelta(days=335),
                "regulatory_authority": "FDA",
                "total_cases_reviewed": 3450,
                "new_signals_identified": 3,
                "benefit_risk_conclusion": "favorable",
                "label_changes_proposed": 2,
                "prepared_by": "Dr. Maria Lopez",
                "reviewed_by": "Dr. Robert Kim",
                "notes": "Conjunctivitis and EGPA signals assessed. Benefit-risk remains favorable.",
                "created_at": now - timedelta(days=375),
            },
            {
                "id": "PSUR-006",
                "trial_id": DUPIXENT_TRIAL,
                "psur_number": 2,
                "reporting_period_start": now - timedelta(days=365),
                "reporting_period_end": now - timedelta(days=1),
                "status": PSURStatus.MEDICAL_REVIEW,
                "product_name": "DUPIXENT (dupilumab)",
                "submission_date": None,
                "submission_deadline": now + timedelta(days=15),
                "regulatory_authority": "FDA",
                "total_cases_reviewed": 2780,
                "new_signals_identified": 1,
                "benefit_risk_conclusion": "favorable",
                "label_changes_proposed": 0,
                "prepared_by": "Dr. Maria Lopez",
                "reviewed_by": "Dr. Robert Kim",
                "notes": "Under medical review. EGPA signal evaluation ongoing.",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "PSUR-007",
                "trial_id": DUPIXENT_TRIAL,
                "psur_number": 3,
                "reporting_period_start": now - timedelta(days=730),
                "reporting_period_end": now - timedelta(days=365),
                "status": PSURStatus.SUBMITTED,
                "product_name": "DUPIXENT (dupilumab)",
                "submission_date": now - timedelta(days=328),
                "submission_deadline": now - timedelta(days=335),
                "regulatory_authority": "PMDA",
                "total_cases_reviewed": 1890,
                "new_signals_identified": 2,
                "benefit_risk_conclusion": "favorable",
                "label_changes_proposed": 1,
                "prepared_by": "Dr. Robert Kim",
                "reviewed_by": "Dr. Maria Lopez",
                "notes": "PMDA submission complete. Awaiting acknowledgement.",
                "created_at": now - timedelta(days=373),
            },
            {
                "id": "PSUR-008",
                "trial_id": DUPIXENT_TRIAL,
                "psur_number": 4,
                "reporting_period_start": now - timedelta(days=365),
                "reporting_period_end": now - timedelta(days=1),
                "status": PSURStatus.DATA_COLLECTION,
                "product_name": "DUPIXENT (dupilumab)",
                "submission_date": None,
                "submission_deadline": now + timedelta(days=45),
                "regulatory_authority": "PMDA",
                "total_cases_reviewed": 450,
                "new_signals_identified": 0,
                "benefit_risk_conclusion": "favorable",
                "label_changes_proposed": 0,
                "prepared_by": "Dr. Robert Kim",
                "reviewed_by": None,
                "notes": "PMDA cycle 2 data collection in progress.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "PSUR-009",
                "trial_id": LIBTAYO_TRIAL,
                "psur_number": 1,
                "reporting_period_start": now - timedelta(days=730),
                "reporting_period_end": now - timedelta(days=365),
                "status": PSURStatus.ACKNOWLEDGED,
                "product_name": "LIBTAYO (cemiplimab)",
                "submission_date": now - timedelta(days=345),
                "submission_deadline": now - timedelta(days=335),
                "regulatory_authority": "FDA",
                "total_cases_reviewed": 980,
                "new_signals_identified": 4,
                "benefit_risk_conclusion": "favorable",
                "label_changes_proposed": 2,
                "prepared_by": "Dr. Angela Park",
                "reviewed_by": "Dr. William Torres",
                "notes": "Multiple immune-mediated AE signals assessed. Label updated.",
                "created_at": now - timedelta(days=390),
            },
            {
                "id": "PSUR-010",
                "trial_id": LIBTAYO_TRIAL,
                "psur_number": 2,
                "reporting_period_start": now - timedelta(days=365),
                "reporting_period_end": now - timedelta(days=1),
                "status": PSURStatus.DRAFTING,
                "product_name": "LIBTAYO (cemiplimab)",
                "submission_date": None,
                "submission_deadline": now + timedelta(days=25),
                "regulatory_authority": "FDA",
                "total_cases_reviewed": 720,
                "new_signals_identified": 1,
                "benefit_risk_conclusion": "favorable",
                "label_changes_proposed": 0,
                "prepared_by": "Dr. Angela Park",
                "reviewed_by": None,
                "notes": "Myocarditis signal under initial evaluation.",
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "PSUR-011",
                "trial_id": LIBTAYO_TRIAL,
                "psur_number": 3,
                "reporting_period_start": now - timedelta(days=730),
                "reporting_period_end": now - timedelta(days=365),
                "status": PSURStatus.ACKNOWLEDGED,
                "product_name": "LIBTAYO (cemiplimab)",
                "submission_date": now - timedelta(days=338),
                "submission_deadline": now - timedelta(days=335),
                "regulatory_authority": "EMA",
                "total_cases_reviewed": 1540,
                "new_signals_identified": 3,
                "benefit_risk_conclusion": "favorable",
                "label_changes_proposed": 2,
                "prepared_by": "Dr. Angela Park",
                "reviewed_by": "Dr. William Torres",
                "notes": "EMA PSUR aligned. Hepatitis, pneumonitis, hypothyroidism signals included.",
                "created_at": now - timedelta(days=383),
            },
            {
                "id": "PSUR-012",
                "trial_id": LIBTAYO_TRIAL,
                "psur_number": 4,
                "reporting_period_start": now - timedelta(days=365),
                "reporting_period_end": now - timedelta(days=1),
                "status": PSURStatus.PLANNING,
                "product_name": "LIBTAYO (cemiplimab)",
                "submission_date": None,
                "submission_deadline": now + timedelta(days=55),
                "regulatory_authority": "EMA",
                "total_cases_reviewed": 0,
                "new_signals_identified": 0,
                "benefit_risk_conclusion": "favorable",
                "label_changes_proposed": 0,
                "prepared_by": "Dr. William Torres",
                "reviewed_by": None,
                "notes": "EMA cycle 2 planning initiated.",
                "created_at": now - timedelta(days=8),
            },
        ]

        for p in psur_data:
            self._psur_records[p["id"]] = PSURRecord(**p)

        # --- 12 Risk Management Plans ---
        rmp_data = [
            {
                "id": "RMP-001",
                "trial_id": EYLEA_TRIAL,
                "plan_version": "3.0",
                "effective_date": now - timedelta(days=300),
                "product_name": "EYLEA (aflibercept)",
                "risk_category": RiskCategory.IMPORTANT_IDENTIFIED,
                "risk_description": "Endophthalmitis following intravitreal injection",
                "pharmacovigilance_activity": "Enhanced spontaneous reporting and targeted follow-up questionnaire",
                "risk_minimization_measure": "Healthcare professional training materials for aseptic technique",
                "milestones": ["Interim report Q2 2025", "Final report Q4 2025"],
                "milestone_status": "on_track",
                "next_update_due": now + timedelta(days=90),
                "regulatory_requirement": True,
                "managed_by": "Dr. Sarah Chen",
                "approved_by": "Dr. James Wright",
                "notes": "Core RMP element. Ongoing since approval.",
                "created_at": now - timedelta(days=300),
            },
            {
                "id": "RMP-002",
                "trial_id": EYLEA_TRIAL,
                "plan_version": "3.0",
                "effective_date": now - timedelta(days=300),
                "product_name": "EYLEA (aflibercept)",
                "risk_category": RiskCategory.IMPORTANT_POTENTIAL,
                "risk_description": "Arterial thromboembolic events in patients with prior history",
                "pharmacovigilance_activity": "Signal detection in claims databases and FAERS",
                "risk_minimization_measure": None,
                "milestones": ["Annual review Q1 2026"],
                "milestone_status": "on_track",
                "next_update_due": now + timedelta(days=180),
                "regulatory_requirement": True,
                "managed_by": "Dr. James Wright",
                "approved_by": "Dr. Sarah Chen",
                "notes": "Monitoring continues despite refuted signal.",
                "created_at": now - timedelta(days=300),
            },
            {
                "id": "RMP-003",
                "trial_id": EYLEA_TRIAL,
                "plan_version": "3.0",
                "effective_date": now - timedelta(days=300),
                "product_name": "EYLEA (aflibercept)",
                "risk_category": RiskCategory.MISSING_INFORMATION,
                "risk_description": "Long-term safety beyond 5 years of continuous treatment",
                "pharmacovigilance_activity": "Post-authorization safety study (PASS) in registry population",
                "risk_minimization_measure": None,
                "milestones": ["Enrollment completion 2025", "Interim 2027", "Final 2030"],
                "milestone_status": "on_track",
                "next_update_due": now + timedelta(days=365),
                "regulatory_requirement": True,
                "managed_by": "Dr. Sarah Chen",
                "approved_by": "Dr. James Wright",
                "notes": "10-year PASS study. Enrollment 85% complete.",
                "created_at": now - timedelta(days=300),
            },
            {
                "id": "RMP-004",
                "trial_id": EYLEA_TRIAL,
                "plan_version": "3.0",
                "effective_date": now - timedelta(days=300),
                "product_name": "EYLEA (aflibercept)",
                "risk_category": RiskCategory.IDENTIFIED_RISK,
                "risk_description": "Transient intraocular pressure increase post-injection",
                "pharmacovigilance_activity": "Routine pharmacovigilance with enhanced monitoring",
                "risk_minimization_measure": "IOP monitoring recommendation in SmPC section 4.4",
                "milestones": ["Ongoing monitoring"],
                "milestone_status": "on_track",
                "next_update_due": now + timedelta(days=90),
                "regulatory_requirement": False,
                "managed_by": "Dr. Sarah Chen",
                "approved_by": None,
                "notes": "Routine monitoring. No rate changes observed.",
                "created_at": now - timedelta(days=300),
            },
            {
                "id": "RMP-005",
                "trial_id": DUPIXENT_TRIAL,
                "plan_version": "5.0",
                "effective_date": now - timedelta(days=200),
                "product_name": "DUPIXENT (dupilumab)",
                "risk_category": RiskCategory.IMPORTANT_IDENTIFIED,
                "risk_description": "Conjunctivitis and keratitis in atopic dermatitis patients",
                "pharmacovigilance_activity": "Targeted follow-up questionnaire for ocular events",
                "risk_minimization_measure": "Patient information card and ophthalmology referral guidance",
                "milestones": ["Interim analysis 2025", "Final 2027"],
                "milestone_status": "on_track",
                "next_update_due": now + timedelta(days=120),
                "regulatory_requirement": True,
                "managed_by": "Dr. Maria Lopez",
                "approved_by": "Dr. Robert Kim",
                "notes": "Key safety concern across indications.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "RMP-006",
                "trial_id": DUPIXENT_TRIAL,
                "plan_version": "5.0",
                "effective_date": now - timedelta(days=200),
                "product_name": "DUPIXENT (dupilumab)",
                "risk_category": RiskCategory.IMPORTANT_POTENTIAL,
                "risk_description": "Eosinophilic granulomatosis with polyangiitis (EGPA) emergence",
                "pharmacovigilance_activity": "Signal evaluation and enhanced case review",
                "risk_minimization_measure": "HCP communication about monitoring for eosinophilia",
                "milestones": ["Signal evaluation Q3 2025", "Regulatory update Q4 2025"],
                "milestone_status": "delayed",
                "next_update_due": now + timedelta(days=30),
                "regulatory_requirement": True,
                "managed_by": "Dr. Maria Lopez",
                "approved_by": "Dr. Robert Kim",
                "notes": "FDA request for EGPA evaluation. Timeline under pressure.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "RMP-007",
                "trial_id": DUPIXENT_TRIAL,
                "plan_version": "5.0",
                "effective_date": now - timedelta(days=200),
                "product_name": "DUPIXENT (dupilumab)",
                "risk_category": RiskCategory.MISSING_INFORMATION,
                "risk_description": "Safety in pediatric patients under 6 months of age",
                "pharmacovigilance_activity": "Pediatric PASS study (registry-based)",
                "risk_minimization_measure": None,
                "milestones": ["Protocol finalization 2025", "Enrollment start 2026"],
                "milestone_status": "on_track",
                "next_update_due": now + timedelta(days=200),
                "regulatory_requirement": True,
                "managed_by": "Dr. Robert Kim",
                "approved_by": None,
                "notes": "Protocol in development for pediatric safety study.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "RMP-008",
                "trial_id": DUPIXENT_TRIAL,
                "plan_version": "5.0",
                "effective_date": now - timedelta(days=200),
                "product_name": "DUPIXENT (dupilumab)",
                "risk_category": RiskCategory.POTENTIAL_RISK,
                "risk_description": "Helminth infection exacerbation in endemic areas",
                "pharmacovigilance_activity": "Literature monitoring and targeted pharmacovigilance",
                "risk_minimization_measure": "Labeling recommendation for helminth screening",
                "milestones": ["Annual literature review"],
                "milestone_status": "on_track",
                "next_update_due": now + timedelta(days=180),
                "regulatory_requirement": False,
                "managed_by": "Dr. Maria Lopez",
                "approved_by": None,
                "notes": "Low priority. Annual monitoring sufficient.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "RMP-009",
                "trial_id": LIBTAYO_TRIAL,
                "plan_version": "4.0",
                "effective_date": now - timedelta(days=250),
                "product_name": "LIBTAYO (cemiplimab)",
                "risk_category": RiskCategory.IMPORTANT_IDENTIFIED,
                "risk_description": "Immune-mediated hepatitis",
                "pharmacovigilance_activity": "Enhanced spontaneous reporting and PASS in oncology registries",
                "risk_minimization_measure": "Hepatic function monitoring guide for oncologists",
                "milestones": ["Interim report 2025", "Final PASS 2028"],
                "milestone_status": "on_track",
                "next_update_due": now + timedelta(days=60),
                "regulatory_requirement": True,
                "managed_by": "Dr. Angela Park",
                "approved_by": "Dr. William Torres",
                "notes": "Critical safety measure for checkpoint inhibitor class.",
                "created_at": now - timedelta(days=250),
            },
            {
                "id": "RMP-010",
                "trial_id": LIBTAYO_TRIAL,
                "plan_version": "4.0",
                "effective_date": now - timedelta(days=250),
                "product_name": "LIBTAYO (cemiplimab)",
                "risk_category": RiskCategory.IMPORTANT_IDENTIFIED,
                "risk_description": "Immune-mediated pneumonitis",
                "pharmacovigilance_activity": "Targeted case review and registry surveillance",
                "risk_minimization_measure": "Respiratory symptom monitoring checklist",
                "milestones": ["Ongoing with PSUR cycle"],
                "milestone_status": "on_track",
                "next_update_due": now + timedelta(days=60),
                "regulatory_requirement": True,
                "managed_by": "Dr. Angela Park",
                "approved_by": "Dr. William Torres",
                "notes": "Class effect. Integrated into routine PV.",
                "created_at": now - timedelta(days=250),
            },
            {
                "id": "RMP-011",
                "trial_id": LIBTAYO_TRIAL,
                "plan_version": "4.0",
                "effective_date": now - timedelta(days=250),
                "product_name": "LIBTAYO (cemiplimab)",
                "risk_category": RiskCategory.IMPORTANT_POTENTIAL,
                "risk_description": "Myocarditis (immune-mediated)",
                "pharmacovigilance_activity": "Signal evaluation with cardiac biomarker analysis",
                "risk_minimization_measure": None,
                "milestones": ["Signal evaluation Q1 2026", "Regulatory update Q2 2026"],
                "milestone_status": "on_track",
                "next_update_due": now + timedelta(days=90),
                "regulatory_requirement": True,
                "managed_by": "Dr. Angela Park",
                "approved_by": None,
                "notes": "New potential risk identified. Evaluation plan in development.",
                "created_at": now - timedelta(days=250),
            },
            {
                "id": "RMP-012",
                "trial_id": LIBTAYO_TRIAL,
                "plan_version": "4.0",
                "effective_date": now - timedelta(days=250),
                "product_name": "LIBTAYO (cemiplimab)",
                "risk_category": RiskCategory.MISSING_INFORMATION,
                "risk_description": "Safety in patients with autoimmune disease at baseline",
                "pharmacovigilance_activity": "Post-authorization safety study in autoimmune-disease population",
                "risk_minimization_measure": None,
                "milestones": ["Protocol submitted 2024", "Enrollment start 2025", "Interim 2027"],
                "milestone_status": "on_track",
                "next_update_due": now + timedelta(days=150),
                "regulatory_requirement": True,
                "managed_by": "Dr. William Torres",
                "approved_by": "Dr. Angela Park",
                "notes": "Excluded population from pivotal trials. PASS addresses gap.",
                "created_at": now - timedelta(days=250),
            },
        ]

        for r in rmp_data:
            self._risk_management_plans[r["id"]] = RiskManagementPlan(**r)

        # --- 12 Product Quality Reviews ---
        pqr_data = [
            {
                "id": "PQR-001",
                "trial_id": EYLEA_TRIAL,
                "product_name": "EYLEA (aflibercept)",
                "batch_number": "EYL-2024-A001",
                "review_period": "2024-H1",
                "review_date": now - timedelta(days=200),
                "batches_reviewed": 24,
                "batches_within_spec": 24,
                "out_of_spec_events": 0,
                "stability_data_adequate": True,
                "trend_analysis_performed": True,
                "deviations_identified": 1,
                "capa_required": False,
                "overall_compliance": "compliant",
                "reviewed_by": "Dr. Sarah Chen",
                "approved_by": "Dr. James Wright",
                "notes": "All batches within specification. Minor documentation deviation.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "PQR-002",
                "trial_id": EYLEA_TRIAL,
                "product_name": "EYLEA (aflibercept)",
                "batch_number": "EYL-2024-B001",
                "review_period": "2024-H2",
                "review_date": now - timedelta(days=30),
                "batches_reviewed": 28,
                "batches_within_spec": 27,
                "out_of_spec_events": 1,
                "stability_data_adequate": True,
                "trend_analysis_performed": True,
                "deviations_identified": 3,
                "capa_required": True,
                "overall_compliance": "compliant_with_observations",
                "reviewed_by": "Dr. Sarah Chen",
                "approved_by": None,
                "notes": "One OOS event in particulate matter testing. CAPA initiated.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "PQR-003",
                "trial_id": EYLEA_TRIAL,
                "product_name": "EYLEA (aflibercept)",
                "batch_number": "EYL-2025-A001",
                "review_period": "2025-Q1",
                "review_date": now - timedelta(days=10),
                "batches_reviewed": 12,
                "batches_within_spec": 12,
                "out_of_spec_events": 0,
                "stability_data_adequate": True,
                "trend_analysis_performed": False,
                "deviations_identified": 0,
                "capa_required": False,
                "overall_compliance": "compliant",
                "reviewed_by": "Dr. James Wright",
                "approved_by": None,
                "notes": "Quarterly review. All batches meet specifications.",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "PQR-004",
                "trial_id": EYLEA_TRIAL,
                "product_name": "EYLEA (aflibercept)",
                "batch_number": "EYL-2023-C001",
                "review_period": "2023-Annual",
                "review_date": now - timedelta(days=400),
                "batches_reviewed": 48,
                "batches_within_spec": 48,
                "out_of_spec_events": 0,
                "stability_data_adequate": True,
                "trend_analysis_performed": True,
                "deviations_identified": 2,
                "capa_required": False,
                "overall_compliance": "compliant",
                "reviewed_by": "Dr. Sarah Chen",
                "approved_by": "Dr. James Wright",
                "notes": "Annual review. Excellent batch consistency.",
                "created_at": now - timedelta(days=400),
            },
            {
                "id": "PQR-005",
                "trial_id": DUPIXENT_TRIAL,
                "product_name": "DUPIXENT (dupilumab)",
                "batch_number": "DUP-2024-A001",
                "review_period": "2024-H1",
                "review_date": now - timedelta(days=190),
                "batches_reviewed": 36,
                "batches_within_spec": 35,
                "out_of_spec_events": 1,
                "stability_data_adequate": True,
                "trend_analysis_performed": True,
                "deviations_identified": 4,
                "capa_required": True,
                "overall_compliance": "compliant_with_observations",
                "reviewed_by": "Dr. Maria Lopez",
                "approved_by": "Dr. Robert Kim",
                "notes": "One OOS in protein aggregation. Process improvement implemented.",
                "created_at": now - timedelta(days=190),
            },
            {
                "id": "PQR-006",
                "trial_id": DUPIXENT_TRIAL,
                "product_name": "DUPIXENT (dupilumab)",
                "batch_number": "DUP-2024-B001",
                "review_period": "2024-H2",
                "review_date": now - timedelta(days=25),
                "batches_reviewed": 40,
                "batches_within_spec": 40,
                "out_of_spec_events": 0,
                "stability_data_adequate": True,
                "trend_analysis_performed": True,
                "deviations_identified": 1,
                "capa_required": False,
                "overall_compliance": "compliant",
                "reviewed_by": "Dr. Maria Lopez",
                "approved_by": "Dr. Robert Kim",
                "notes": "All batches compliant post-process improvement.",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "PQR-007",
                "trial_id": DUPIXENT_TRIAL,
                "product_name": "DUPIXENT (dupilumab)",
                "batch_number": "DUP-2023-C001",
                "review_period": "2023-Annual",
                "review_date": now - timedelta(days=380),
                "batches_reviewed": 72,
                "batches_within_spec": 71,
                "out_of_spec_events": 1,
                "stability_data_adequate": True,
                "trend_analysis_performed": True,
                "deviations_identified": 5,
                "capa_required": True,
                "overall_compliance": "compliant_with_observations",
                "reviewed_by": "Dr. Robert Kim",
                "approved_by": "Dr. Maria Lopez",
                "notes": "Annual review. One OOS in sterility. Root cause: media fill failure.",
                "created_at": now - timedelta(days=380),
            },
            {
                "id": "PQR-008",
                "trial_id": DUPIXENT_TRIAL,
                "product_name": "DUPIXENT (dupilumab)",
                "batch_number": "DUP-2025-A001",
                "review_period": "2025-Q1",
                "review_date": now - timedelta(days=8),
                "batches_reviewed": 18,
                "batches_within_spec": 18,
                "out_of_spec_events": 0,
                "stability_data_adequate": True,
                "trend_analysis_performed": False,
                "deviations_identified": 0,
                "capa_required": False,
                "overall_compliance": "compliant",
                "reviewed_by": "Dr. Maria Lopez",
                "approved_by": None,
                "notes": "Quarterly review. Clean batch record.",
                "created_at": now - timedelta(days=8),
            },
            {
                "id": "PQR-009",
                "trial_id": LIBTAYO_TRIAL,
                "product_name": "LIBTAYO (cemiplimab)",
                "batch_number": "LIB-2024-A001",
                "review_period": "2024-H1",
                "review_date": now - timedelta(days=185),
                "batches_reviewed": 16,
                "batches_within_spec": 16,
                "out_of_spec_events": 0,
                "stability_data_adequate": True,
                "trend_analysis_performed": True,
                "deviations_identified": 0,
                "capa_required": False,
                "overall_compliance": "compliant",
                "reviewed_by": "Dr. Angela Park",
                "approved_by": "Dr. William Torres",
                "notes": "All batches fully compliant. Excellent quality profile.",
                "created_at": now - timedelta(days=185),
            },
            {
                "id": "PQR-010",
                "trial_id": LIBTAYO_TRIAL,
                "product_name": "LIBTAYO (cemiplimab)",
                "batch_number": "LIB-2024-B001",
                "review_period": "2024-H2",
                "review_date": now - timedelta(days=20),
                "batches_reviewed": 18,
                "batches_within_spec": 17,
                "out_of_spec_events": 1,
                "stability_data_adequate": True,
                "trend_analysis_performed": True,
                "deviations_identified": 2,
                "capa_required": True,
                "overall_compliance": "non_compliant",
                "reviewed_by": "Dr. Angela Park",
                "approved_by": None,
                "notes": "One batch failed potency test. CAPA and lot quarantine initiated.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "PQR-011",
                "trial_id": LIBTAYO_TRIAL,
                "product_name": "LIBTAYO (cemiplimab)",
                "batch_number": "LIB-2023-C001",
                "review_period": "2023-Annual",
                "review_date": now - timedelta(days=370),
                "batches_reviewed": 32,
                "batches_within_spec": 32,
                "out_of_spec_events": 0,
                "stability_data_adequate": True,
                "trend_analysis_performed": True,
                "deviations_identified": 1,
                "capa_required": False,
                "overall_compliance": "compliant",
                "reviewed_by": "Dr. William Torres",
                "approved_by": "Dr. Angela Park",
                "notes": "Annual review. Strong quality performance.",
                "created_at": now - timedelta(days=370),
            },
            {
                "id": "PQR-012",
                "trial_id": LIBTAYO_TRIAL,
                "product_name": "LIBTAYO (cemiplimab)",
                "batch_number": "LIB-2025-A001",
                "review_period": "2025-Q1",
                "review_date": now - timedelta(days=5),
                "batches_reviewed": 8,
                "batches_within_spec": 8,
                "out_of_spec_events": 0,
                "stability_data_adequate": True,
                "trend_analysis_performed": False,
                "deviations_identified": 0,
                "capa_required": False,
                "overall_compliance": "compliant",
                "reviewed_by": "Dr. Angela Park",
                "approved_by": None,
                "notes": "Early Q1 review. All batches meeting specifications.",
                "created_at": now - timedelta(days=5),
            },
        ]

        for q in pqr_data:
            self._product_quality_reviews[q["id"]] = ProductQualityReview(**q)

        # --- 12 Post-Marketing Commitments ---
        pmc_data = [
            {
                "id": "PMC-001",
                "trial_id": EYLEA_TRIAL,
                "commitment_type": CommitmentType.SAFETY_STUDY,
                "commitment_number": "PMR-2021-001",
                "description": "Post-authorization safety study evaluating long-term retinal outcomes in AMD patients treated with EYLEA for >5 years",
                "regulatory_authority": "FDA",
                "product_name": "EYLEA (aflibercept)",
                "agreed_date": now - timedelta(days=900),
                "due_date": now + timedelta(days=1095),
                "status": "in_progress",
                "progress_pct": 65.0,
                "last_update_date": now - timedelta(days=30),
                "annual_report_included": True,
                "milestone_met": False,
                "responsible_party": "Dr. Sarah Chen",
                "notes": "Enrollment complete. Follow-up ongoing. 65% of data collected.",
                "created_at": now - timedelta(days=900),
            },
            {
                "id": "PMC-002",
                "trial_id": EYLEA_TRIAL,
                "commitment_type": CommitmentType.LABEL_UPDATE,
                "commitment_number": "PMR-2023-002",
                "description": "Update prescribing information to include endophthalmitis incidence rate from post-marketing experience",
                "regulatory_authority": "FDA",
                "product_name": "EYLEA (aflibercept)",
                "agreed_date": now - timedelta(days=365),
                "due_date": now - timedelta(days=180),
                "status": "completed",
                "progress_pct": 100.0,
                "last_update_date": now - timedelta(days=200),
                "annual_report_included": True,
                "milestone_met": True,
                "responsible_party": "Dr. James Wright",
                "notes": "Label update approved and implemented.",
                "created_at": now - timedelta(days=365),
            },
            {
                "id": "PMC-003",
                "trial_id": EYLEA_TRIAL,
                "commitment_type": CommitmentType.REGISTRY,
                "commitment_number": "PMR-2022-003",
                "description": "Participate in international AMD treatment registry for comparative safety outcomes",
                "regulatory_authority": "EMA",
                "product_name": "EYLEA (aflibercept)",
                "agreed_date": now - timedelta(days=730),
                "due_date": now + timedelta(days=730),
                "status": "in_progress",
                "progress_pct": 45.0,
                "last_update_date": now - timedelta(days=60),
                "annual_report_included": True,
                "milestone_met": False,
                "responsible_party": "Dr. Sarah Chen",
                "notes": "Registry enrollment ongoing. 12,000 patients enrolled to date.",
                "created_at": now - timedelta(days=730),
            },
            {
                "id": "PMC-004",
                "trial_id": EYLEA_TRIAL,
                "commitment_type": CommitmentType.EFFECTIVENESS_STUDY,
                "commitment_number": "PMR-2023-004",
                "description": "Real-world effectiveness study in diabetic macular edema across diverse populations",
                "regulatory_authority": "FDA",
                "product_name": "EYLEA (aflibercept)",
                "agreed_date": now - timedelta(days=500),
                "due_date": now + timedelta(days=500),
                "status": "in_progress",
                "progress_pct": 35.0,
                "last_update_date": now - timedelta(days=45),
                "annual_report_included": False,
                "milestone_met": False,
                "responsible_party": "Dr. James Wright",
                "notes": "Multi-site enrollment in progress. 8 of 25 sites active.",
                "created_at": now - timedelta(days=500),
            },
            {
                "id": "PMC-005",
                "trial_id": DUPIXENT_TRIAL,
                "commitment_type": CommitmentType.CLINICAL_STUDY,
                "commitment_number": "PMR-2022-005",
                "description": "Post-marketing clinical study evaluating dupilumab safety in pediatric patients aged 6 months to 5 years",
                "regulatory_authority": "FDA",
                "product_name": "DUPIXENT (dupilumab)",
                "agreed_date": now - timedelta(days=600),
                "due_date": now + timedelta(days=400),
                "status": "in_progress",
                "progress_pct": 55.0,
                "last_update_date": now - timedelta(days=20),
                "annual_report_included": True,
                "milestone_met": False,
                "responsible_party": "Dr. Maria Lopez",
                "notes": "Pediatric study enrolling. Interim safety data favorable.",
                "created_at": now - timedelta(days=600),
            },
            {
                "id": "PMC-006",
                "trial_id": DUPIXENT_TRIAL,
                "commitment_type": CommitmentType.SAFETY_STUDY,
                "commitment_number": "PMR-2023-006",
                "description": "Epidemiological study to characterize EGPA risk in dupilumab-treated asthma patients",
                "regulatory_authority": "FDA",
                "product_name": "DUPIXENT (dupilumab)",
                "agreed_date": now - timedelta(days=300),
                "due_date": now + timedelta(days=700),
                "status": "in_progress",
                "progress_pct": 20.0,
                "last_update_date": now - timedelta(days=15),
                "annual_report_included": False,
                "milestone_met": False,
                "responsible_party": "Dr. Maria Lopez",
                "notes": "Protocol finalized. Data sources identified. Analysis plan under review.",
                "created_at": now - timedelta(days=300),
            },
            {
                "id": "PMC-007",
                "trial_id": DUPIXENT_TRIAL,
                "commitment_type": CommitmentType.LABEL_UPDATE,
                "commitment_number": "PMR-2024-007",
                "description": "Update prescribing information with conjunctivitis management guidance",
                "regulatory_authority": "EMA",
                "product_name": "DUPIXENT (dupilumab)",
                "agreed_date": now - timedelta(days=180),
                "due_date": now + timedelta(days=30),
                "status": "open",
                "progress_pct": 80.0,
                "last_update_date": now - timedelta(days=10),
                "annual_report_included": False,
                "milestone_met": False,
                "responsible_party": "Dr. Robert Kim",
                "notes": "Draft label update under EMA review. Expected approval soon.",
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "PMC-008",
                "trial_id": DUPIXENT_TRIAL,
                "commitment_type": CommitmentType.REMS,
                "commitment_number": "PMR-2021-008",
                "description": "Risk Evaluation and Mitigation Strategy for monitoring immunosuppression-related infections",
                "regulatory_authority": "FDA",
                "product_name": "DUPIXENT (dupilumab)",
                "agreed_date": now - timedelta(days=800),
                "due_date": now + timedelta(days=200),
                "status": "in_progress",
                "progress_pct": 70.0,
                "last_update_date": now - timedelta(days=30),
                "annual_report_included": True,
                "milestone_met": False,
                "responsible_party": "Dr. Maria Lopez",
                "notes": "REMS assessment report due. Compliance rate 92%.",
                "created_at": now - timedelta(days=800),
            },
            {
                "id": "PMC-009",
                "trial_id": LIBTAYO_TRIAL,
                "commitment_type": CommitmentType.SAFETY_STUDY,
                "commitment_number": "PMR-2022-009",
                "description": "Post-authorization safety study for immune-mediated adverse events in real-world oncology population",
                "regulatory_authority": "FDA",
                "product_name": "LIBTAYO (cemiplimab)",
                "agreed_date": now - timedelta(days=700),
                "due_date": now + timedelta(days=600),
                "status": "in_progress",
                "progress_pct": 40.0,
                "last_update_date": now - timedelta(days=25),
                "annual_report_included": True,
                "milestone_met": False,
                "responsible_party": "Dr. Angela Park",
                "notes": "Multi-registry study. 5,000 patients enrolled across 4 registries.",
                "created_at": now - timedelta(days=700),
            },
            {
                "id": "PMC-010",
                "trial_id": LIBTAYO_TRIAL,
                "commitment_type": CommitmentType.CLINICAL_STUDY,
                "commitment_number": "PMR-2023-010",
                "description": "Phase IV study evaluating cemiplimab in patients with autoimmune disease at baseline",
                "regulatory_authority": "EMA",
                "product_name": "LIBTAYO (cemiplimab)",
                "agreed_date": now - timedelta(days=400),
                "due_date": now + timedelta(days=900),
                "status": "open",
                "progress_pct": 10.0,
                "last_update_date": now - timedelta(days=40),
                "annual_report_included": False,
                "milestone_met": False,
                "responsible_party": "Dr. William Torres",
                "notes": "Protocol approved. Site selection in progress.",
                "created_at": now - timedelta(days=400),
            },
            {
                "id": "PMC-011",
                "trial_id": LIBTAYO_TRIAL,
                "commitment_type": CommitmentType.REMS,
                "commitment_number": "PMR-2021-011",
                "description": "REMS for immune-mediated adverse event monitoring and prescriber education",
                "regulatory_authority": "FDA",
                "product_name": "LIBTAYO (cemiplimab)",
                "agreed_date": now - timedelta(days=850),
                "due_date": now + timedelta(days=150),
                "status": "in_progress",
                "progress_pct": 75.0,
                "last_update_date": now - timedelta(days=15),
                "annual_report_included": True,
                "milestone_met": False,
                "responsible_party": "Dr. Angela Park",
                "notes": "REMS assessment ongoing. 95% prescriber training compliance.",
                "created_at": now - timedelta(days=850),
            },
            {
                "id": "PMC-012",
                "trial_id": LIBTAYO_TRIAL,
                "commitment_type": CommitmentType.LABEL_UPDATE,
                "commitment_number": "PMR-2024-012",
                "description": "Update labeling with hepatitis monitoring recommendations from PASS interim results",
                "regulatory_authority": "FDA",
                "product_name": "LIBTAYO (cemiplimab)",
                "agreed_date": now - timedelta(days=150),
                "due_date": now - timedelta(days=30),
                "status": "completed",
                "progress_pct": 100.0,
                "last_update_date": now - timedelta(days=35),
                "annual_report_included": True,
                "milestone_met": True,
                "responsible_party": "Dr. Angela Park",
                "notes": "Label update approved. Hepatitis section strengthened.",
                "created_at": now - timedelta(days=150),
            },
        ]

        for c in pmc_data:
            self._post_marketing_commitments[c["id"]] = PostMarketingCommitment(**c)

    # ------------------------------------------------------------------
    # Safety Signals
    # ------------------------------------------------------------------

    def list_safety_signals(
        self,
        *,
        trial_id: str | None = None,
        signal_source: SignalSource | None = None,
        status: SignalStatus | None = None,
    ) -> list[SafetySignalTracker]:
        """List safety signals with optional filters."""
        with self._lock:
            result = list(self._safety_signals.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if signal_source is not None:
            result = [s for s in result if s.signal_source == signal_source]
        if status is not None:
            result = [s for s in result if s.status == status]

        return sorted(result, key=lambda s: s.detection_date, reverse=True)

    def get_safety_signal(self, signal_id: str) -> SafetySignalTracker | None:
        """Get a single safety signal by ID."""
        with self._lock:
            return self._safety_signals.get(signal_id)

    def create_safety_signal(self, payload: SafetySignalTrackerCreate) -> SafetySignalTracker:
        """Create a new safety signal."""
        now = datetime.now(timezone.utc)
        signal_id = f"SIG-{uuid4().hex[:8].upper()}"
        signal = SafetySignalTracker(
            id=signal_id,
            trial_id=payload.trial_id,
            signal_name=payload.signal_name,
            signal_source=payload.signal_source,
            status=SignalStatus.DETECTED,
            detection_date=now,
            product_name=payload.product_name,
            event_term=payload.event_term,
            meddra_pt=None,
            case_count=payload.case_count,
            reporting_rate=0.0,
            pro_score=None,
            disproportionality_score=None,
            clinical_significance=None,
            regulatory_impact=False,
            label_change_needed=False,
            assessed_by=payload.assessed_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._safety_signals[signal_id] = signal
        logger.info("Created safety signal %s for trial %s", signal_id, payload.trial_id)
        return signal

    def update_safety_signal(
        self, signal_id: str, payload: SafetySignalTrackerUpdate
    ) -> SafetySignalTracker | None:
        """Update an existing safety signal."""
        with self._lock:
            existing = self._safety_signals.get(signal_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = SafetySignalTracker(**data)
            self._safety_signals[signal_id] = updated
        return updated

    def delete_safety_signal(self, signal_id: str) -> bool:
        """Delete a safety signal. Returns True if deleted."""
        with self._lock:
            if signal_id in self._safety_signals:
                del self._safety_signals[signal_id]
                return True
            return False

    # ------------------------------------------------------------------
    # PSUR Records
    # ------------------------------------------------------------------

    def list_psur_records(
        self,
        *,
        trial_id: str | None = None,
        status: PSURStatus | None = None,
    ) -> list[PSURRecord]:
        """List PSUR records with optional filters."""
        with self._lock:
            result = list(self._psur_records.values())

        if trial_id is not None:
            result = [p for p in result if p.trial_id == trial_id]
        if status is not None:
            result = [p for p in result if p.status == status]

        return sorted(result, key=lambda p: p.submission_deadline, reverse=True)

    def get_psur_record(self, psur_id: str) -> PSURRecord | None:
        """Get a single PSUR record by ID."""
        with self._lock:
            return self._psur_records.get(psur_id)

    def create_psur_record(self, payload: PSURRecordCreate) -> PSURRecord:
        """Create a new PSUR record."""
        now = datetime.now(timezone.utc)
        psur_id = f"PSUR-{uuid4().hex[:8].upper()}"
        psur = PSURRecord(
            id=psur_id,
            trial_id=payload.trial_id,
            psur_number=payload.psur_number,
            reporting_period_start=payload.reporting_period_start,
            reporting_period_end=payload.reporting_period_end,
            status=PSURStatus.PLANNING,
            product_name=payload.product_name,
            submission_date=None,
            submission_deadline=payload.submission_deadline,
            regulatory_authority=payload.regulatory_authority,
            total_cases_reviewed=0,
            new_signals_identified=0,
            benefit_risk_conclusion="favorable",
            label_changes_proposed=0,
            prepared_by=payload.prepared_by,
            reviewed_by=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._psur_records[psur_id] = psur
        logger.info("Created PSUR record %s for trial %s", psur_id, payload.trial_id)
        return psur

    def update_psur_record(
        self, psur_id: str, payload: PSURRecordUpdate
    ) -> PSURRecord | None:
        """Update an existing PSUR record."""
        with self._lock:
            existing = self._psur_records.get(psur_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = PSURRecord(**data)
            self._psur_records[psur_id] = updated
        return updated

    def delete_psur_record(self, psur_id: str) -> bool:
        """Delete a PSUR record. Returns True if deleted."""
        with self._lock:
            if psur_id in self._psur_records:
                del self._psur_records[psur_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Risk Management Plans
    # ------------------------------------------------------------------

    def list_risk_management_plans(
        self,
        *,
        trial_id: str | None = None,
        risk_category: RiskCategory | None = None,
    ) -> list[RiskManagementPlan]:
        """List risk management plans with optional filters."""
        with self._lock:
            result = list(self._risk_management_plans.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if risk_category is not None:
            result = [r for r in result if r.risk_category == risk_category]

        return sorted(result, key=lambda r: r.effective_date, reverse=True)

    def get_risk_management_plan(self, plan_id: str) -> RiskManagementPlan | None:
        """Get a single risk management plan by ID."""
        with self._lock:
            return self._risk_management_plans.get(plan_id)

    def create_risk_management_plan(self, payload: RiskManagementPlanCreate) -> RiskManagementPlan:
        """Create a new risk management plan."""
        now = datetime.now(timezone.utc)
        plan_id = f"RMP-{uuid4().hex[:8].upper()}"
        plan = RiskManagementPlan(
            id=plan_id,
            trial_id=payload.trial_id,
            plan_version=payload.plan_version,
            effective_date=now,
            product_name=payload.product_name,
            risk_category=payload.risk_category,
            risk_description=payload.risk_description,
            pharmacovigilance_activity=payload.pharmacovigilance_activity,
            risk_minimization_measure=None,
            milestones=[],
            milestone_status="on_track",
            next_update_due=None,
            regulatory_requirement=True,
            managed_by=payload.managed_by,
            approved_by=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._risk_management_plans[plan_id] = plan
        logger.info("Created risk management plan %s for trial %s", plan_id, payload.trial_id)
        return plan

    def update_risk_management_plan(
        self, plan_id: str, payload: RiskManagementPlanUpdate
    ) -> RiskManagementPlan | None:
        """Update an existing risk management plan."""
        with self._lock:
            existing = self._risk_management_plans.get(plan_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = RiskManagementPlan(**data)
            self._risk_management_plans[plan_id] = updated
        return updated

    def delete_risk_management_plan(self, plan_id: str) -> bool:
        """Delete a risk management plan. Returns True if deleted."""
        with self._lock:
            if plan_id in self._risk_management_plans:
                del self._risk_management_plans[plan_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Product Quality Reviews
    # ------------------------------------------------------------------

    def list_product_quality_reviews(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[ProductQualityReview]:
        """List product quality reviews with optional filters."""
        with self._lock:
            result = list(self._product_quality_reviews.values())

        if trial_id is not None:
            result = [q for q in result if q.trial_id == trial_id]

        return sorted(result, key=lambda q: q.review_date, reverse=True)

    def get_product_quality_review(self, review_id: str) -> ProductQualityReview | None:
        """Get a single product quality review by ID."""
        with self._lock:
            return self._product_quality_reviews.get(review_id)

    def create_product_quality_review(self, payload: ProductQualityReviewCreate) -> ProductQualityReview:
        """Create a new product quality review."""
        now = datetime.now(timezone.utc)
        review_id = f"PQR-{uuid4().hex[:8].upper()}"
        review = ProductQualityReview(
            id=review_id,
            trial_id=payload.trial_id,
            product_name=payload.product_name,
            batch_number=payload.batch_number,
            review_period=payload.review_period,
            review_date=now,
            batches_reviewed=payload.batches_reviewed,
            batches_within_spec=0,
            out_of_spec_events=0,
            stability_data_adequate=True,
            trend_analysis_performed=False,
            deviations_identified=0,
            capa_required=False,
            overall_compliance="compliant",
            reviewed_by=payload.reviewed_by,
            approved_by=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._product_quality_reviews[review_id] = review
        logger.info("Created product quality review %s for trial %s", review_id, payload.trial_id)
        return review

    def update_product_quality_review(
        self, review_id: str, payload: ProductQualityReviewUpdate
    ) -> ProductQualityReview | None:
        """Update an existing product quality review."""
        with self._lock:
            existing = self._product_quality_reviews.get(review_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ProductQualityReview(**data)
            self._product_quality_reviews[review_id] = updated
        return updated

    def delete_product_quality_review(self, review_id: str) -> bool:
        """Delete a product quality review. Returns True if deleted."""
        with self._lock:
            if review_id in self._product_quality_reviews:
                del self._product_quality_reviews[review_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Post-Marketing Commitments
    # ------------------------------------------------------------------

    def list_post_marketing_commitments(
        self,
        *,
        trial_id: str | None = None,
        commitment_type: CommitmentType | None = None,
    ) -> list[PostMarketingCommitment]:
        """List post-marketing commitments with optional filters."""
        with self._lock:
            result = list(self._post_marketing_commitments.values())

        if trial_id is not None:
            result = [c for c in result if c.trial_id == trial_id]
        if commitment_type is not None:
            result = [c for c in result if c.commitment_type == commitment_type]

        return sorted(result, key=lambda c: c.due_date, reverse=True)

    def get_post_marketing_commitment(self, commitment_id: str) -> PostMarketingCommitment | None:
        """Get a single post-marketing commitment by ID."""
        with self._lock:
            return self._post_marketing_commitments.get(commitment_id)

    def create_post_marketing_commitment(
        self, payload: PostMarketingCommitmentCreate
    ) -> PostMarketingCommitment:
        """Create a new post-marketing commitment."""
        now = datetime.now(timezone.utc)
        commitment_id = f"PMC-{uuid4().hex[:8].upper()}"
        commitment = PostMarketingCommitment(
            id=commitment_id,
            trial_id=payload.trial_id,
            commitment_type=payload.commitment_type,
            commitment_number=payload.commitment_number,
            description=payload.description,
            regulatory_authority=payload.regulatory_authority,
            product_name=payload.product_name,
            agreed_date=now,
            due_date=payload.due_date,
            status="open",
            progress_pct=0.0,
            last_update_date=None,
            annual_report_included=False,
            milestone_met=False,
            responsible_party=payload.responsible_party,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._post_marketing_commitments[commitment_id] = commitment
        logger.info(
            "Created post-marketing commitment %s for trial %s",
            commitment_id,
            payload.trial_id,
        )
        return commitment

    def update_post_marketing_commitment(
        self, commitment_id: str, payload: PostMarketingCommitmentUpdate
    ) -> PostMarketingCommitment | None:
        """Update an existing post-marketing commitment."""
        with self._lock:
            existing = self._post_marketing_commitments.get(commitment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = PostMarketingCommitment(**data)
            self._post_marketing_commitments[commitment_id] = updated
        return updated

    def delete_post_marketing_commitment(self, commitment_id: str) -> bool:
        """Delete a post-marketing commitment. Returns True if deleted."""
        with self._lock:
            if commitment_id in self._post_marketing_commitments:
                del self._post_marketing_commitments[commitment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self, *, trial_id: str | None = None) -> PostMarketingSurveillanceMetrics:
        """Compute aggregate post-marketing surveillance metrics."""
        signals = self.list_safety_signals(trial_id=trial_id)
        psurs = self.list_psur_records(trial_id=trial_id)
        risk_plans = self.list_risk_management_plans(trial_id=trial_id)
        quality_reviews = self.list_product_quality_reviews(trial_id=trial_id)
        commitments = self.list_post_marketing_commitments(trial_id=trial_id)

        # Signals by source
        signals_by_source: dict[str, int] = {}
        for s in signals:
            key = s.signal_source.value
            signals_by_source[key] = signals_by_source.get(key, 0) + 1

        # Signals by status
        signals_by_status: dict[str, int] = {}
        for s in signals:
            key = s.status.value
            signals_by_status[key] = signals_by_status.get(key, 0) + 1

        # Confirmed signals
        confirmed_signals = sum(1 for s in signals if s.status == SignalStatus.CONFIRMED)

        # PSURs by status
        psurs_by_status: dict[str, int] = {}
        for p in psurs:
            key = p.status.value
            psurs_by_status[key] = psurs_by_status.get(key, 0) + 1

        # PSURs pending submission (not yet submitted and deadline in future)
        psurs_pending = sum(
            1
            for p in psurs
            if p.status not in (PSURStatus.SUBMITTED, PSURStatus.ACKNOWLEDGED)
        )

        # Risks by category
        risks_by_category: dict[str, int] = {}
        for r in risk_plans:
            key = r.risk_category.value
            risks_by_category[key] = risks_by_category.get(key, 0) + 1

        # Out-of-spec reviews
        oos_reviews = sum(1 for q in quality_reviews if q.out_of_spec_events > 0)

        # Commitments by type
        commitments_by_type: dict[str, int] = {}
        for c in commitments:
            key = c.commitment_type.value
            commitments_by_type[key] = commitments_by_type.get(key, 0) + 1

        # Open commitments
        open_commitments = sum(
            1 for c in commitments if c.status in ("open", "in_progress")
        )

        return PostMarketingSurveillanceMetrics(
            total_signals=len(signals),
            signals_by_source=signals_by_source,
            signals_by_status=signals_by_status,
            confirmed_signals=confirmed_signals,
            total_psurs=len(psurs),
            psurs_by_status=psurs_by_status,
            psurs_pending_submission=psurs_pending,
            total_risk_plans=len(risk_plans),
            risks_by_category=risks_by_category,
            total_quality_reviews=len(quality_reviews),
            out_of_spec_reviews=oos_reviews,
            total_commitments=len(commitments),
            commitments_by_type=commitments_by_type,
            open_commitments=open_commitments,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: PostMarketingSurveillanceService | None = None
_instance_lock = threading.Lock()


def get_post_marketing_surveillance_service() -> PostMarketingSurveillanceService:
    """Return the singleton PostMarketingSurveillanceService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = PostMarketingSurveillanceService()
    return _instance


def reset_post_marketing_surveillance_service() -> PostMarketingSurveillanceService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = PostMarketingSurveillanceService()
    return _instance
