"""Dose Escalation Management (DOSE-ESC) Service.

Manages dose-finding operations: dose level definitions, escalation decisions,
dose-limiting toxicity (DLT) tracking, PK result management, RP2D
recommendation, and dose escalation operational metrics.

Usage:
    from app.services.dose_escalation_service import (
        get_dose_escalation_service,
    )

    svc = get_dose_escalation_service()
    levels = svc.list_dose_levels()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.dose_escalation import (
    CohortDecision,
    CohortDecisionCreate,
    CohortDecisionUpdate,
    DLTEvent,
    DLTEventCreate,
    DLTEventUpdate,
    DLTGrade,
    DoseEscalationMetrics,
    DoseLevel,
    DoseLevelCreate,
    DoseLevelStatus,
    DoseLevelUpdate,
    EscalationDecision,
    EscalationDesign,
    PKParameter,
    PKResult,
    PKResultCreate,
    PKResultUpdate,
    RP2DRecommendation,
    RP2DRecommendationCreate,
    RP2DRecommendationUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class DoseEscalationService:
    """In-memory Dose Escalation Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._dose_levels: dict[str, DoseLevel] = {}
        self._dlt_events: dict[str, DLTEvent] = {}
        self._cohort_decisions: dict[str, CohortDecision] = {}
        self._pk_results: dict[str, PKResult] = {}
        self._rp2d_recommendations: dict[str, RP2DRecommendation] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic dose escalation data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- Dose Levels (12 records) ---
        dose_levels_data = [
            # EYLEA HD dose escalation (intravitreal aflibercept)
            {"id": "DL-001", "trial_id": EYLEA_TRIAL, "cohort_number": 1, "dose_amount": 2.0, "dose_unit": "mg", "route": "intravitreal", "schedule": "Q8W", "status": DoseLevelStatus.COMPLETED, "design": EscalationDesign.THREE_PLUS_THREE, "target_enrollment": 3, "actual_enrollment": 3, "dlt_count": 0, "dlt_rate_pct": 0.0, "evaluation_period_days": 28, "start_date": now - timedelta(days=180), "completion_date": now - timedelta(days=150), "created_at": now - timedelta(days=200)},
            {"id": "DL-002", "trial_id": EYLEA_TRIAL, "cohort_number": 2, "dose_amount": 4.0, "dose_unit": "mg", "route": "intravitreal", "schedule": "Q8W", "status": DoseLevelStatus.COMPLETED, "design": EscalationDesign.THREE_PLUS_THREE, "target_enrollment": 3, "actual_enrollment": 3, "dlt_count": 0, "dlt_rate_pct": 0.0, "evaluation_period_days": 28, "start_date": now - timedelta(days=150), "completion_date": now - timedelta(days=120), "created_at": now - timedelta(days=200)},
            {"id": "DL-003", "trial_id": EYLEA_TRIAL, "cohort_number": 3, "dose_amount": 8.0, "dose_unit": "mg", "route": "intravitreal", "schedule": "Q8W", "status": DoseLevelStatus.EXPANDED, "design": EscalationDesign.THREE_PLUS_THREE, "target_enrollment": 6, "actual_enrollment": 6, "dlt_count": 1, "dlt_rate_pct": 16.7, "evaluation_period_days": 28, "start_date": now - timedelta(days=120), "completion_date": now - timedelta(days=60), "created_at": now - timedelta(days=200)},
            {"id": "DL-004", "trial_id": EYLEA_TRIAL, "cohort_number": 4, "dose_amount": 12.0, "dose_unit": "mg", "route": "intravitreal", "schedule": "Q12W", "status": DoseLevelStatus.ENROLLING, "design": EscalationDesign.THREE_PLUS_THREE, "target_enrollment": 3, "actual_enrollment": 2, "dlt_count": 0, "dlt_rate_pct": 0.0, "evaluation_period_days": 28, "start_date": now - timedelta(days=30), "completion_date": None, "created_at": now - timedelta(days=200)},
            # Dupixent dose escalation (subcutaneous dupilumab)
            {"id": "DL-005", "trial_id": DUPIXENT_TRIAL, "cohort_number": 1, "dose_amount": 100.0, "dose_unit": "mg", "route": "subcutaneous", "schedule": "Q2W", "status": DoseLevelStatus.COMPLETED, "design": EscalationDesign.BOIN, "target_enrollment": 6, "actual_enrollment": 6, "dlt_count": 0, "dlt_rate_pct": 0.0, "evaluation_period_days": 42, "start_date": now - timedelta(days=200), "completion_date": now - timedelta(days=155), "created_at": now - timedelta(days=220)},
            {"id": "DL-006", "trial_id": DUPIXENT_TRIAL, "cohort_number": 2, "dose_amount": 200.0, "dose_unit": "mg", "route": "subcutaneous", "schedule": "Q2W", "status": DoseLevelStatus.COMPLETED, "design": EscalationDesign.BOIN, "target_enrollment": 6, "actual_enrollment": 6, "dlt_count": 1, "dlt_rate_pct": 16.7, "evaluation_period_days": 42, "start_date": now - timedelta(days=155), "completion_date": now - timedelta(days=110), "created_at": now - timedelta(days=220)},
            {"id": "DL-007", "trial_id": DUPIXENT_TRIAL, "cohort_number": 3, "dose_amount": 300.0, "dose_unit": "mg", "route": "subcutaneous", "schedule": "Q2W", "status": DoseLevelStatus.COMPLETED, "design": EscalationDesign.BOIN, "target_enrollment": 6, "actual_enrollment": 6, "dlt_count": 0, "dlt_rate_pct": 0.0, "evaluation_period_days": 42, "start_date": now - timedelta(days=110), "completion_date": now - timedelta(days=65), "created_at": now - timedelta(days=220)},
            {"id": "DL-008", "trial_id": DUPIXENT_TRIAL, "cohort_number": 4, "dose_amount": 400.0, "dose_unit": "mg", "route": "subcutaneous", "schedule": "Q2W", "status": DoseLevelStatus.CLOSED_TOXICITY, "design": EscalationDesign.BOIN, "target_enrollment": 6, "actual_enrollment": 4, "dlt_count": 2, "dlt_rate_pct": 50.0, "evaluation_period_days": 42, "start_date": now - timedelta(days=65), "completion_date": now - timedelta(days=30), "created_at": now - timedelta(days=220)},
            # Libtayo dose escalation (IV cemiplimab)
            {"id": "DL-009", "trial_id": LIBTAYO_TRIAL, "cohort_number": 1, "dose_amount": 1.0, "dose_unit": "mg/kg", "route": "intravenous", "schedule": "Q3W", "status": DoseLevelStatus.COMPLETED, "design": EscalationDesign.CRM, "target_enrollment": 3, "actual_enrollment": 3, "dlt_count": 0, "dlt_rate_pct": 0.0, "evaluation_period_days": 21, "start_date": now - timedelta(days=250), "completion_date": now - timedelta(days=225), "created_at": now - timedelta(days=260)},
            {"id": "DL-010", "trial_id": LIBTAYO_TRIAL, "cohort_number": 2, "dose_amount": 3.0, "dose_unit": "mg/kg", "route": "intravenous", "schedule": "Q3W", "status": DoseLevelStatus.COMPLETED, "design": EscalationDesign.CRM, "target_enrollment": 3, "actual_enrollment": 3, "dlt_count": 1, "dlt_rate_pct": 33.3, "evaluation_period_days": 21, "start_date": now - timedelta(days=225), "completion_date": now - timedelta(days=200), "created_at": now - timedelta(days=260)},
            {"id": "DL-011", "trial_id": LIBTAYO_TRIAL, "cohort_number": 3, "dose_amount": 350.0, "dose_unit": "mg", "route": "intravenous", "schedule": "Q3W", "status": DoseLevelStatus.COMPLETED, "design": EscalationDesign.CRM, "target_enrollment": 6, "actual_enrollment": 6, "dlt_count": 1, "dlt_rate_pct": 16.7, "evaluation_period_days": 21, "start_date": now - timedelta(days=200), "completion_date": now - timedelta(days=150), "created_at": now - timedelta(days=260)},
            {"id": "DL-012", "trial_id": LIBTAYO_TRIAL, "cohort_number": 4, "dose_amount": 500.0, "dose_unit": "mg", "route": "intravenous", "schedule": "Q3W", "status": DoseLevelStatus.PLANNED, "design": EscalationDesign.CRM, "target_enrollment": 3, "actual_enrollment": 0, "dlt_count": 0, "dlt_rate_pct": 0.0, "evaluation_period_days": 21, "start_date": None, "completion_date": None, "created_at": now - timedelta(days=260)},
        ]

        for dl in dose_levels_data:
            self._dose_levels[dl["id"]] = DoseLevel(**dl)

        # --- DLT Events (10 records) ---
        dlt_events_data = [
            {"id": "DLT-001", "dose_level_id": "DL-003", "trial_id": EYLEA_TRIAL, "subject_id": "SUBJ-1003", "dlt_grade": DLTGrade.GRADE_3, "toxicity_term": "Intraocular inflammation", "organ_system": "Eye", "onset_day": 14, "resolved": True, "resolution_day": 28, "attribution": "probable", "dose_modification": "Dose held 1 cycle", "reported_by": "Dr. Smith", "reported_date": now - timedelta(days=100), "reviewed_by": "Dr. Chen", "created_at": now - timedelta(days=100)},
            {"id": "DLT-002", "dose_level_id": "DL-006", "trial_id": DUPIXENT_TRIAL, "subject_id": "SUBJ-2004", "dlt_grade": DLTGrade.GRADE_3, "toxicity_term": "Injection site reaction", "organ_system": "Skin", "onset_day": 7, "resolved": True, "resolution_day": 21, "attribution": "definite", "dose_modification": None, "reported_by": "Dr. Johnson", "reported_date": now - timedelta(days=130), "reviewed_by": "Dr. Williams", "created_at": now - timedelta(days=130)},
            {"id": "DLT-003", "dose_level_id": "DL-008", "trial_id": DUPIXENT_TRIAL, "subject_id": "SUBJ-2007", "dlt_grade": DLTGrade.GRADE_4, "toxicity_term": "Anaphylaxis", "organ_system": "Immune system", "onset_day": 3, "resolved": True, "resolution_day": 5, "attribution": "definite", "dose_modification": "Discontinued", "reported_by": "Dr. Martinez", "reported_date": now - timedelta(days=50), "reviewed_by": "Dr. Kim", "created_at": now - timedelta(days=50)},
            {"id": "DLT-004", "dose_level_id": "DL-008", "trial_id": DUPIXENT_TRIAL, "subject_id": "SUBJ-2008", "dlt_grade": DLTGrade.GRADE_3, "toxicity_term": "Conjunctivitis", "organ_system": "Eye", "onset_day": 10, "resolved": True, "resolution_day": 25, "attribution": "probable", "dose_modification": "Dose reduced", "reported_by": "Dr. Patel", "reported_date": now - timedelta(days=45), "reviewed_by": "Dr. Williams", "created_at": now - timedelta(days=45)},
            {"id": "DLT-005", "dose_level_id": "DL-010", "trial_id": LIBTAYO_TRIAL, "subject_id": "SUBJ-3002", "dlt_grade": DLTGrade.GRADE_3, "toxicity_term": "Immune-mediated colitis", "organ_system": "Gastrointestinal", "onset_day": 18, "resolved": True, "resolution_day": 35, "attribution": "probable", "dose_modification": "Dose held", "reported_by": "Dr. Foster", "reported_date": now - timedelta(days=210), "reviewed_by": "Dr. Liu", "created_at": now - timedelta(days=210)},
            {"id": "DLT-006", "dose_level_id": "DL-011", "trial_id": LIBTAYO_TRIAL, "subject_id": "SUBJ-3005", "dlt_grade": DLTGrade.GRADE_3, "toxicity_term": "Hepatitis", "organ_system": "Hepatobiliary", "onset_day": 12, "resolved": True, "resolution_day": 30, "attribution": "possible", "dose_modification": "Dose held 2 cycles", "reported_by": "Dr. Wong", "reported_date": now - timedelta(days=170), "reviewed_by": "Dr. Harris", "created_at": now - timedelta(days=170)},
            {"id": "DLT-007", "dose_level_id": "DL-003", "trial_id": EYLEA_TRIAL, "subject_id": "SUBJ-1005", "dlt_grade": DLTGrade.GRADE_3, "toxicity_term": "Retinal detachment", "organ_system": "Eye", "onset_day": 21, "resolved": False, "resolution_day": None, "attribution": "possible", "dose_modification": "Discontinued", "reported_by": "Dr. Rodriguez", "reported_date": now - timedelta(days=80), "reviewed_by": None, "created_at": now - timedelta(days=80)},
            {"id": "DLT-008", "dose_level_id": "DL-010", "trial_id": LIBTAYO_TRIAL, "subject_id": "SUBJ-3003", "dlt_grade": DLTGrade.GRADE_4, "toxicity_term": "Pneumonitis", "organ_system": "Respiratory", "onset_day": 15, "resolved": True, "resolution_day": 40, "attribution": "probable", "dose_modification": "Discontinued", "reported_by": "Dr. Thompson", "reported_date": now - timedelta(days=205), "reviewed_by": "Dr. Liu", "created_at": now - timedelta(days=205)},
            {"id": "DLT-009", "dose_level_id": "DL-006", "trial_id": DUPIXENT_TRIAL, "subject_id": "SUBJ-2005", "dlt_grade": DLTGrade.GRADE_3, "toxicity_term": "Eczema herpeticum", "organ_system": "Skin", "onset_day": 20, "resolved": True, "resolution_day": 35, "attribution": "unlikely", "dose_modification": None, "reported_by": "Dr. Nakamura", "reported_date": now - timedelta(days=125), "reviewed_by": "Dr. Sullivan", "created_at": now - timedelta(days=125)},
            {"id": "DLT-010", "dose_level_id": "DL-004", "trial_id": EYLEA_TRIAL, "subject_id": "SUBJ-1008", "dlt_grade": DLTGrade.GRADE_3, "toxicity_term": "Vitreous hemorrhage", "organ_system": "Eye", "onset_day": 5, "resolved": False, "resolution_day": None, "attribution": "probable", "dose_modification": "Dose held", "reported_by": "Dr. Kim", "reported_date": now - timedelta(days=20), "reviewed_by": None, "created_at": now - timedelta(days=20)},
        ]

        for dlt in dlt_events_data:
            self._dlt_events[dlt["id"]] = DLTEvent(**dlt)

        # --- Cohort Decisions (10 records) ---
        cohort_decisions_data = [
            {"id": "CD-001", "dose_level_id": "DL-001", "trial_id": EYLEA_TRIAL, "decision": EscalationDecision.ESCALATE, "rationale": "0/3 DLTs observed at 2mg. Safe to escalate per 3+3 rules.", "dlt_rate_observed": 0.0, "target_toxicity_rate": 33.3, "model_recommendation": None, "safety_review_date": now - timedelta(days=150), "committee_members": ["Dr. Chen", "Dr. Rodriguez", "Dr. Thompson"], "next_dose_level_id": "DL-002", "approved_by": "Dr. Chen", "created_at": now - timedelta(days=150)},
            {"id": "CD-002", "dose_level_id": "DL-002", "trial_id": EYLEA_TRIAL, "decision": EscalationDecision.ESCALATE, "rationale": "0/3 DLTs at 4mg. Escalation to 8mg recommended.", "dlt_rate_observed": 0.0, "target_toxicity_rate": 33.3, "model_recommendation": None, "safety_review_date": now - timedelta(days=120), "committee_members": ["Dr. Chen", "Dr. Rodriguez", "Dr. Thompson"], "next_dose_level_id": "DL-003", "approved_by": "Dr. Chen", "created_at": now - timedelta(days=120)},
            {"id": "CD-003", "dose_level_id": "DL-003", "trial_id": EYLEA_TRIAL, "decision": EscalationDecision.EXPAND, "rationale": "1/3 DLTs at 8mg. Expand cohort to 6 per 3+3 design.", "dlt_rate_observed": 33.3, "target_toxicity_rate": 33.3, "model_recommendation": None, "safety_review_date": now - timedelta(days=90), "committee_members": ["Dr. Chen", "Dr. Rodriguez", "Dr. Thompson", "Dr. Patel"], "next_dose_level_id": None, "approved_by": "Dr. Chen", "created_at": now - timedelta(days=90)},
            {"id": "CD-004", "dose_level_id": "DL-003", "trial_id": EYLEA_TRIAL, "decision": EscalationDecision.ESCALATE, "rationale": "1/6 DLTs at 8mg expanded cohort. Below threshold, escalate to 12mg.", "dlt_rate_observed": 16.7, "target_toxicity_rate": 33.3, "model_recommendation": None, "safety_review_date": now - timedelta(days=60), "committee_members": ["Dr. Chen", "Dr. Rodriguez", "Dr. Thompson"], "next_dose_level_id": "DL-004", "approved_by": "Dr. Chen", "created_at": now - timedelta(days=60)},
            {"id": "CD-005", "dose_level_id": "DL-005", "trial_id": DUPIXENT_TRIAL, "decision": EscalationDecision.ESCALATE, "rationale": "0/6 DLTs at 100mg. BOIN model supports escalation.", "dlt_rate_observed": 0.0, "target_toxicity_rate": 30.0, "model_recommendation": "Escalate (BOIN posterior prob < 0.236)", "safety_review_date": now - timedelta(days=155), "committee_members": ["Dr. Williams", "Dr. Martinez", "Dr. Nakamura"], "next_dose_level_id": "DL-006", "approved_by": "Dr. Williams", "created_at": now - timedelta(days=155)},
            {"id": "CD-006", "dose_level_id": "DL-006", "trial_id": DUPIXENT_TRIAL, "decision": EscalationDecision.ESCALATE, "rationale": "1/6 DLTs at 200mg. BOIN model: escalate.", "dlt_rate_observed": 16.7, "target_toxicity_rate": 30.0, "model_recommendation": "Escalate (BOIN posterior prob = 0.31)", "safety_review_date": now - timedelta(days=110), "committee_members": ["Dr. Williams", "Dr. Martinez", "Dr. Nakamura"], "next_dose_level_id": "DL-007", "approved_by": "Dr. Williams", "created_at": now - timedelta(days=110)},
            {"id": "CD-007", "dose_level_id": "DL-007", "trial_id": DUPIXENT_TRIAL, "decision": EscalationDecision.ESCALATE, "rationale": "0/6 DLTs at 300mg. Proceed to 400mg.", "dlt_rate_observed": 0.0, "target_toxicity_rate": 30.0, "model_recommendation": "Escalate (BOIN posterior prob < 0.236)", "safety_review_date": now - timedelta(days=65), "committee_members": ["Dr. Williams", "Dr. Martinez", "Dr. Nakamura"], "next_dose_level_id": "DL-008", "approved_by": "Dr. Williams", "created_at": now - timedelta(days=65)},
            {"id": "CD-008", "dose_level_id": "DL-008", "trial_id": DUPIXENT_TRIAL, "decision": EscalationDecision.DE_ESCALATE, "rationale": "2/4 DLTs at 400mg. Exceeds target toxicity. De-escalate and declare RP2D at 300mg.", "dlt_rate_observed": 50.0, "target_toxicity_rate": 30.0, "model_recommendation": "De-escalate (BOIN posterior prob = 0.78)", "safety_review_date": now - timedelta(days=30), "committee_members": ["Dr. Williams", "Dr. Martinez", "Dr. Nakamura", "Dr. Sullivan"], "next_dose_level_id": "DL-007", "approved_by": "Dr. Williams", "created_at": now - timedelta(days=30)},
            {"id": "CD-009", "dose_level_id": "DL-009", "trial_id": LIBTAYO_TRIAL, "decision": EscalationDecision.ESCALATE, "rationale": "0/3 DLTs at 1mg/kg. CRM model supports escalation.", "dlt_rate_observed": 0.0, "target_toxicity_rate": 25.0, "model_recommendation": "Escalate (CRM target interval)", "safety_review_date": now - timedelta(days=225), "committee_members": ["Dr. Liu", "Dr. Foster", "Dr. Wong"], "next_dose_level_id": "DL-010", "approved_by": "Dr. Liu", "created_at": now - timedelta(days=225)},
            {"id": "CD-010", "dose_level_id": "DL-010", "trial_id": LIBTAYO_TRIAL, "decision": EscalationDecision.STAY, "rationale": "1/3 DLTs at 3mg/kg. CRM recommends staying at current dose. Expand cohort.", "dlt_rate_observed": 33.3, "target_toxicity_rate": 25.0, "model_recommendation": "Stay (CRM posterior DLT rate = 0.28)", "safety_review_date": now - timedelta(days=200), "committee_members": ["Dr. Liu", "Dr. Foster", "Dr. Wong", "Dr. Harris"], "next_dose_level_id": None, "approved_by": "Dr. Liu", "created_at": now - timedelta(days=200)},
        ]

        for cd in cohort_decisions_data:
            self._cohort_decisions[cd["id"]] = CohortDecision(**cd)

        # --- PK Results (12 records) ---
        pk_results_data = [
            {"id": "PK-001", "dose_level_id": "DL-001", "trial_id": EYLEA_TRIAL, "subject_id": "SUBJ-1001", "parameter": PKParameter.CMAX, "value": 0.45, "unit": "ug/mL", "time_point_hours": 24.0, "dose_proportional": True, "food_effect": False, "sample_matrix": "vitreous", "bioanalytical_method": "ELISA", "below_lloq": False, "created_at": now - timedelta(days=160)},
            {"id": "PK-002", "dose_level_id": "DL-002", "trial_id": EYLEA_TRIAL, "subject_id": "SUBJ-1002", "parameter": PKParameter.CMAX, "value": 0.92, "unit": "ug/mL", "time_point_hours": 24.0, "dose_proportional": True, "food_effect": False, "sample_matrix": "vitreous", "bioanalytical_method": "ELISA", "below_lloq": False, "created_at": now - timedelta(days=130)},
            {"id": "PK-003", "dose_level_id": "DL-003", "trial_id": EYLEA_TRIAL, "subject_id": "SUBJ-1003", "parameter": PKParameter.AUC_0_INF, "value": 156.3, "unit": "ug*h/mL", "time_point_hours": None, "dose_proportional": True, "food_effect": False, "sample_matrix": "plasma", "bioanalytical_method": "LC-MS/MS", "below_lloq": False, "created_at": now - timedelta(days=90)},
            {"id": "PK-004", "dose_level_id": "DL-003", "trial_id": EYLEA_TRIAL, "subject_id": "SUBJ-1004", "parameter": PKParameter.HALF_LIFE, "value": 5.4, "unit": "days", "time_point_hours": None, "dose_proportional": None, "food_effect": False, "sample_matrix": "plasma", "bioanalytical_method": "LC-MS/MS", "below_lloq": False, "created_at": now - timedelta(days=85)},
            {"id": "PK-005", "dose_level_id": "DL-005", "trial_id": DUPIXENT_TRIAL, "subject_id": "SUBJ-2001", "parameter": PKParameter.CMAX, "value": 12.5, "unit": "ug/mL", "time_point_hours": 168.0, "dose_proportional": True, "food_effect": False, "sample_matrix": "plasma", "bioanalytical_method": "ELISA", "below_lloq": False, "created_at": now - timedelta(days=170)},
            {"id": "PK-006", "dose_level_id": "DL-006", "trial_id": DUPIXENT_TRIAL, "subject_id": "SUBJ-2002", "parameter": PKParameter.TMAX, "value": 7.0, "unit": "days", "time_point_hours": 168.0, "dose_proportional": None, "food_effect": False, "sample_matrix": "plasma", "bioanalytical_method": "ELISA", "below_lloq": False, "created_at": now - timedelta(days=140)},
            {"id": "PK-007", "dose_level_id": "DL-007", "trial_id": DUPIXENT_TRIAL, "subject_id": "SUBJ-2003", "parameter": PKParameter.AUC_0_T, "value": 2856.0, "unit": "ug*day/mL", "time_point_hours": None, "dose_proportional": True, "food_effect": False, "sample_matrix": "plasma", "bioanalytical_method": "ELISA", "below_lloq": False, "created_at": now - timedelta(days=80)},
            {"id": "PK-008", "dose_level_id": "DL-007", "trial_id": DUPIXENT_TRIAL, "subject_id": "SUBJ-2003", "parameter": PKParameter.CLEARANCE, "value": 0.105, "unit": "L/day", "time_point_hours": None, "dose_proportional": None, "food_effect": False, "sample_matrix": "plasma", "bioanalytical_method": "ELISA", "below_lloq": False, "created_at": now - timedelta(days=78)},
            {"id": "PK-009", "dose_level_id": "DL-009", "trial_id": LIBTAYO_TRIAL, "subject_id": "SUBJ-3001", "parameter": PKParameter.CMAX, "value": 28.3, "unit": "ug/mL", "time_point_hours": 2.0, "dose_proportional": True, "food_effect": False, "sample_matrix": "plasma", "bioanalytical_method": "LC-MS/MS", "below_lloq": False, "created_at": now - timedelta(days=230)},
            {"id": "PK-010", "dose_level_id": "DL-010", "trial_id": LIBTAYO_TRIAL, "subject_id": "SUBJ-3002", "parameter": PKParameter.AUC_0_INF, "value": 8540.0, "unit": "ug*h/mL", "time_point_hours": None, "dose_proportional": True, "food_effect": False, "sample_matrix": "plasma", "bioanalytical_method": "LC-MS/MS", "below_lloq": False, "created_at": now - timedelta(days=210)},
            {"id": "PK-011", "dose_level_id": "DL-011", "trial_id": LIBTAYO_TRIAL, "subject_id": "SUBJ-3004", "parameter": PKParameter.VOLUME_DIST, "value": 5.2, "unit": "L", "time_point_hours": None, "dose_proportional": None, "food_effect": False, "sample_matrix": "plasma", "bioanalytical_method": "LC-MS/MS", "below_lloq": False, "created_at": now - timedelta(days=160)},
            {"id": "PK-012", "dose_level_id": "DL-011", "trial_id": LIBTAYO_TRIAL, "subject_id": "SUBJ-3005", "parameter": PKParameter.HALF_LIFE, "value": 19.4, "unit": "days", "time_point_hours": None, "dose_proportional": None, "food_effect": False, "sample_matrix": "plasma", "bioanalytical_method": "LC-MS/MS", "below_lloq": False, "created_at": now - timedelta(days=155)},
        ]

        for pk in pk_results_data:
            self._pk_results[pk["id"]] = PKResult(**pk)

        # --- RP2D Recommendations (3 records) ---
        rp2d_data = [
            {"id": "RP2D-001", "trial_id": EYLEA_TRIAL, "recommended_dose": 8.0, "dose_unit": "mg", "recommended_schedule": "Q8W after loading", "selected_dose_level_id": "DL-003", "safety_summary": "1/6 DLTs at 8mg (16.7%). Well-tolerated across all cohorts. Intraocular inflammation was manageable.", "efficacy_signals": "Robust BCVA improvement observed at 8mg dose level", "pk_rationale": "Dose-proportional PK; 8mg achieves target vitreous exposure", "exposure_target": "Vitreous Cmax > 0.5 ug/mL", "therapeutic_index": 2.8, "total_subjects_evaluated": 12, "overall_dlt_rate_pct": 8.3, "status": "proposed", "proposed_by": "Dr. Chen", "approved_by": None, "proposed_date": now - timedelta(days=15), "approved_date": None, "created_at": now - timedelta(days=15)},
            {"id": "RP2D-002", "trial_id": DUPIXENT_TRIAL, "recommended_dose": 300.0, "dose_unit": "mg", "recommended_schedule": "Q2W subcutaneous", "selected_dose_level_id": "DL-007", "safety_summary": "0/6 DLTs at 300mg (0%). MTD identified at 400mg (2/4 DLTs). 300mg is highest dose below MTD.", "efficacy_signals": "EASI-75 response rate 67% at 300mg; IGA 0/1 in 42%", "pk_rationale": "300mg achieves steady-state trough above EC90 target", "exposure_target": "Trough > 25 ug/mL", "therapeutic_index": 3.5, "total_subjects_evaluated": 22, "overall_dlt_rate_pct": 13.6, "status": "approved", "proposed_by": "Dr. Williams", "approved_by": "Dr. Sullivan", "proposed_date": now - timedelta(days=25), "approved_date": now - timedelta(days=20), "created_at": now - timedelta(days=25)},
            {"id": "RP2D-003", "trial_id": LIBTAYO_TRIAL, "recommended_dose": 350.0, "dose_unit": "mg", "recommended_schedule": "Q3W intravenous", "selected_dose_level_id": "DL-011", "safety_summary": "1/6 DLTs at 350mg flat dose (16.7%). Immune-related AEs manageable with established guidelines.", "efficacy_signals": "Durable ORR of 40% across tumor types at 350mg", "pk_rationale": "Flat dose of 350mg provides equivalent exposure to 3mg/kg; reduces dosing variability", "exposure_target": "AUC > 5000 ug*h/mL per cycle", "therapeutic_index": 2.1, "total_subjects_evaluated": 15, "overall_dlt_rate_pct": 13.3, "status": "approved", "proposed_by": "Dr. Liu", "approved_by": "Dr. Harris", "proposed_date": now - timedelta(days=100), "approved_date": now - timedelta(days=90), "created_at": now - timedelta(days=100)},
        ]

        for rp in rp2d_data:
            self._rp2d_recommendations[rp["id"]] = RP2DRecommendation(**rp)

    # ------------------------------------------------------------------
    # Dose Level Management
    # ------------------------------------------------------------------

    def list_dose_levels(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[DoseLevel]:
        """List dose levels with optional trial filter."""
        with self._lock:
            result = list(self._dose_levels.values())
        if trial_id is not None:
            result = [dl for dl in result if dl.trial_id == trial_id]
        return sorted(result, key=lambda dl: (dl.trial_id, dl.cohort_number))

    def get_dose_level(self, dose_level_id: str) -> DoseLevel | None:
        """Get a single dose level by ID."""
        with self._lock:
            return self._dose_levels.get(dose_level_id)

    def create_dose_level(self, payload: DoseLevelCreate) -> DoseLevel:
        """Create a new dose level."""
        now = datetime.now(timezone.utc)
        dl_id = f"DL-{uuid4().hex[:8].upper()}"
        dose_level = DoseLevel(
            id=dl_id,
            trial_id=payload.trial_id,
            cohort_number=payload.cohort_number,
            dose_amount=payload.dose_amount,
            dose_unit=payload.dose_unit,
            route=payload.route,
            schedule=payload.schedule,
            design=payload.design,
            target_enrollment=payload.target_enrollment,
            evaluation_period_days=payload.evaluation_period_days,
            actual_enrollment=0,
            dlt_count=0,
            dlt_rate_pct=0.0,
            status=DoseLevelStatus.PLANNED,
            start_date=None,
            completion_date=None,
            created_at=now,
        )
        with self._lock:
            self._dose_levels[dl_id] = dose_level
        logger.info("Created dose level %s for trial %s", dl_id, payload.trial_id)
        return dose_level

    def update_dose_level(
        self, dose_level_id: str, payload: DoseLevelUpdate
    ) -> DoseLevel | None:
        """Update an existing dose level."""
        with self._lock:
            existing = self._dose_levels.get(dose_level_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DoseLevel(**data)
            self._dose_levels[dose_level_id] = updated
        return updated

    def delete_dose_level(self, dose_level_id: str) -> bool:
        """Delete a dose level. Returns True if deleted."""
        with self._lock:
            if dose_level_id in self._dose_levels:
                del self._dose_levels[dose_level_id]
                return True
            return False

    # ------------------------------------------------------------------
    # DLT Event Management
    # ------------------------------------------------------------------

    def list_dlt_events(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[DLTEvent]:
        """List DLT events with optional trial filter."""
        with self._lock:
            result = list(self._dlt_events.values())
        if trial_id is not None:
            result = [e for e in result if e.trial_id == trial_id]
        return sorted(result, key=lambda e: e.reported_date, reverse=True)

    def get_dlt_event(self, dlt_event_id: str) -> DLTEvent | None:
        """Get a single DLT event by ID."""
        with self._lock:
            return self._dlt_events.get(dlt_event_id)

    def create_dlt_event(self, payload: DLTEventCreate) -> DLTEvent:
        """Create a new DLT event."""
        now = datetime.now(timezone.utc)
        dlt_id = f"DLT-{uuid4().hex[:8].upper()}"
        dlt_event = DLTEvent(
            id=dlt_id,
            dose_level_id=payload.dose_level_id,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            dlt_grade=payload.dlt_grade,
            toxicity_term=payload.toxicity_term,
            organ_system=payload.organ_system,
            onset_day=payload.onset_day,
            attribution=payload.attribution,
            reported_by=payload.reported_by,
            reported_date=now,
            resolved=False,
            resolution_day=None,
            dose_modification=None,
            reviewed_by=None,
            created_at=now,
        )
        with self._lock:
            self._dlt_events[dlt_id] = dlt_event
        logger.info("Created DLT event %s for trial %s", dlt_id, payload.trial_id)
        return dlt_event

    def update_dlt_event(
        self, dlt_event_id: str, payload: DLTEventUpdate
    ) -> DLTEvent | None:
        """Update an existing DLT event."""
        with self._lock:
            existing = self._dlt_events.get(dlt_event_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DLTEvent(**data)
            self._dlt_events[dlt_event_id] = updated
        return updated

    def delete_dlt_event(self, dlt_event_id: str) -> bool:
        """Delete a DLT event. Returns True if deleted."""
        with self._lock:
            if dlt_event_id in self._dlt_events:
                del self._dlt_events[dlt_event_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Cohort Decision Management
    # ------------------------------------------------------------------

    def list_cohort_decisions(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[CohortDecision]:
        """List cohort decisions with optional trial filter."""
        with self._lock:
            result = list(self._cohort_decisions.values())
        if trial_id is not None:
            result = [d for d in result if d.trial_id == trial_id]
        return sorted(result, key=lambda d: d.safety_review_date, reverse=True)

    def get_cohort_decision(self, decision_id: str) -> CohortDecision | None:
        """Get a single cohort decision by ID."""
        with self._lock:
            return self._cohort_decisions.get(decision_id)

    def create_cohort_decision(self, payload: CohortDecisionCreate) -> CohortDecision:
        """Create a new cohort decision."""
        now = datetime.now(timezone.utc)
        cd_id = f"CD-{uuid4().hex[:8].upper()}"
        decision = CohortDecision(
            id=cd_id,
            dose_level_id=payload.dose_level_id,
            trial_id=payload.trial_id,
            decision=payload.decision,
            rationale=payload.rationale,
            dlt_rate_observed=payload.dlt_rate_observed,
            target_toxicity_rate=33.3,
            model_recommendation=None,
            safety_review_date=payload.safety_review_date,
            committee_members=payload.committee_members,
            next_dose_level_id=payload.next_dose_level_id,
            approved_by=payload.approved_by,
            created_at=now,
        )
        with self._lock:
            self._cohort_decisions[cd_id] = decision
        logger.info("Created cohort decision %s for trial %s", cd_id, payload.trial_id)
        return decision

    def update_cohort_decision(
        self, decision_id: str, payload: CohortDecisionUpdate
    ) -> CohortDecision | None:
        """Update an existing cohort decision."""
        with self._lock:
            existing = self._cohort_decisions.get(decision_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CohortDecision(**data)
            self._cohort_decisions[decision_id] = updated
        return updated

    def delete_cohort_decision(self, decision_id: str) -> bool:
        """Delete a cohort decision. Returns True if deleted."""
        with self._lock:
            if decision_id in self._cohort_decisions:
                del self._cohort_decisions[decision_id]
                return True
            return False

    # ------------------------------------------------------------------
    # PK Result Management
    # ------------------------------------------------------------------

    def list_pk_results(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[PKResult]:
        """List PK results with optional trial filter."""
        with self._lock:
            result = list(self._pk_results.values())
        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        return sorted(result, key=lambda r: r.created_at, reverse=True)

    def get_pk_result(self, pk_result_id: str) -> PKResult | None:
        """Get a single PK result by ID."""
        with self._lock:
            return self._pk_results.get(pk_result_id)

    def create_pk_result(self, payload: PKResultCreate) -> PKResult:
        """Create a new PK result."""
        now = datetime.now(timezone.utc)
        pk_id = f"PK-{uuid4().hex[:8].upper()}"
        pk_result = PKResult(
            id=pk_id,
            dose_level_id=payload.dose_level_id,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            parameter=payload.parameter,
            value=payload.value,
            unit=payload.unit,
            time_point_hours=payload.time_point_hours,
            sample_matrix=payload.sample_matrix,
            dose_proportional=None,
            food_effect=False,
            bioanalytical_method=None,
            below_lloq=False,
            created_at=now,
        )
        with self._lock:
            self._pk_results[pk_id] = pk_result
        logger.info("Created PK result %s for trial %s", pk_id, payload.trial_id)
        return pk_result

    def update_pk_result(
        self, pk_result_id: str, payload: PKResultUpdate
    ) -> PKResult | None:
        """Update an existing PK result."""
        with self._lock:
            existing = self._pk_results.get(pk_result_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = PKResult(**data)
            self._pk_results[pk_result_id] = updated
        return updated

    def delete_pk_result(self, pk_result_id: str) -> bool:
        """Delete a PK result. Returns True if deleted."""
        with self._lock:
            if pk_result_id in self._pk_results:
                del self._pk_results[pk_result_id]
                return True
            return False

    # ------------------------------------------------------------------
    # RP2D Recommendation Management
    # ------------------------------------------------------------------

    def list_rp2d_recommendations(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[RP2DRecommendation]:
        """List RP2D recommendations with optional trial filter."""
        with self._lock:
            result = list(self._rp2d_recommendations.values())
        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        return sorted(result, key=lambda r: r.proposed_date, reverse=True)

    def get_rp2d_recommendation(self, rp2d_id: str) -> RP2DRecommendation | None:
        """Get a single RP2D recommendation by ID."""
        with self._lock:
            return self._rp2d_recommendations.get(rp2d_id)

    def create_rp2d_recommendation(
        self, payload: RP2DRecommendationCreate
    ) -> RP2DRecommendation:
        """Create a new RP2D recommendation."""
        now = datetime.now(timezone.utc)
        rp2d_id = f"RP2D-{uuid4().hex[:8].upper()}"
        recommendation = RP2DRecommendation(
            id=rp2d_id,
            trial_id=payload.trial_id,
            recommended_dose=payload.recommended_dose,
            dose_unit=payload.dose_unit,
            recommended_schedule=payload.recommended_schedule,
            selected_dose_level_id=payload.selected_dose_level_id,
            safety_summary=payload.safety_summary,
            proposed_by=payload.proposed_by,
            total_subjects_evaluated=payload.total_subjects_evaluated,
            overall_dlt_rate_pct=payload.overall_dlt_rate_pct,
            efficacy_signals=None,
            pk_rationale=None,
            exposure_target=None,
            therapeutic_index=None,
            status="proposed",
            approved_by=None,
            proposed_date=now,
            approved_date=None,
            created_at=now,
        )
        with self._lock:
            self._rp2d_recommendations[rp2d_id] = recommendation
        logger.info("Created RP2D recommendation %s for trial %s", rp2d_id, payload.trial_id)
        return recommendation

    def update_rp2d_recommendation(
        self, rp2d_id: str, payload: RP2DRecommendationUpdate
    ) -> RP2DRecommendation | None:
        """Update an existing RP2D recommendation."""
        with self._lock:
            existing = self._rp2d_recommendations.get(rp2d_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = RP2DRecommendation(**data)
            self._rp2d_recommendations[rp2d_id] = updated
        return updated

    def delete_rp2d_recommendation(self, rp2d_id: str) -> bool:
        """Delete an RP2D recommendation. Returns True if deleted."""
        with self._lock:
            if rp2d_id in self._rp2d_recommendations:
                del self._rp2d_recommendations[rp2d_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> DoseEscalationMetrics:
        """Compute aggregated dose escalation metrics."""
        with self._lock:
            dose_levels = list(self._dose_levels.values())
            dlt_events = list(self._dlt_events.values())
            decisions = list(self._cohort_decisions.values())
            pk_results = list(self._pk_results.values())
            rp2d_recs = list(self._rp2d_recommendations.values())

        if trial_id is not None:
            dose_levels = [dl for dl in dose_levels if dl.trial_id == trial_id]
            dlt_events = [e for e in dlt_events if e.trial_id == trial_id]
            decisions = [d for d in decisions if d.trial_id == trial_id]
            pk_results = [r for r in pk_results if r.trial_id == trial_id]
            rp2d_recs = [r for r in rp2d_recs if r.trial_id == trial_id]

        # Levels by status
        levels_by_status: dict[str, int] = {}
        for dl in dose_levels:
            key = dl.status.value
            levels_by_status[key] = levels_by_status.get(key, 0) + 1

        # Levels by design
        levels_by_design: dict[str, int] = {}
        for dl in dose_levels:
            key = dl.design.value
            levels_by_design[key] = levels_by_design.get(key, 0) + 1

        # Total subjects enrolled
        total_subjects = sum(dl.actual_enrollment for dl in dose_levels)

        # DLT stats
        total_dlts = len(dlt_events)
        overall_dlt_rate = (
            round(total_dlts / total_subjects * 100.0, 1)
            if total_subjects > 0
            else 0.0
        )

        # DLTs by grade
        dlts_by_grade: dict[str, int] = {}
        for e in dlt_events:
            key = e.dlt_grade.value
            dlts_by_grade[key] = dlts_by_grade.get(key, 0) + 1

        # Decisions by type
        decisions_by_type: dict[str, int] = {}
        for d in decisions:
            key = d.decision.value
            decisions_by_type[key] = decisions_by_type.get(key, 0) + 1

        # RP2D approved
        rp2d_approved = sum(1 for r in rp2d_recs if r.status == "approved")

        return DoseEscalationMetrics(
            total_dose_levels=len(dose_levels),
            levels_by_status=levels_by_status,
            levels_by_design=levels_by_design,
            total_subjects_enrolled=total_subjects,
            total_dlts=total_dlts,
            overall_dlt_rate_pct=overall_dlt_rate,
            dlts_by_grade=dlts_by_grade,
            total_decisions=len(decisions),
            decisions_by_type=decisions_by_type,
            total_pk_results=len(pk_results),
            total_rp2d_recommendations=len(rp2d_recs),
            rp2d_approved=rp2d_approved,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: DoseEscalationService | None = None
_instance_lock = threading.Lock()


def get_dose_escalation_service() -> DoseEscalationService:
    """Return the singleton DoseEscalationService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = DoseEscalationService()
    return _instance


def reset_dose_escalation_service() -> DoseEscalationService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = DoseEscalationService()
    return _instance
