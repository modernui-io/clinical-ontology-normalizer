"""Medical Monitor Dashboard Service.

Manages medical monitoring operations: safety signal review, benefit-risk
assessments, medical queries, patient case reviews, safety trend analysis,
monitor notes, and operational metrics.

Usage:
    from app.services.medical_monitor_service import (
        get_medical_monitor_service,
    )

    svc = get_medical_monitor_service()
    signals = svc.list_signals()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.medical_monitor import (
    AssessmentOutcome,
    BenefitRiskAssessment,
    BenefitRiskAssessmentCreate,
    BenefitRiskAssessmentUpdate,
    CaseReviewCompletion,
    CaseReviewStatus,
    MedicalMonitorMetrics,
    MedicalMonitorNote,
    MedicalMonitorNoteCreate,
    MedicalQuery,
    MedicalQueryCreate,
    MedicalQueryResponse,
    MedicalQueryUpdate,
    NoteCategory,
    NoteVisibility,
    PatientCaseReview,
    PatientCaseReviewCreate,
    PatientCaseReviewUpdate,
    QueryCategory,
    QueryStatus,
    ReviewPriority,
    RiskLevel,
    SafetySignal,
    SafetySignalCreate,
    SafetySignalUpdate,
    SafetyTrend,
    SignalEscalation,
    SignalStatus,
    TrendDirection,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

# Query considered overdue after this many days without response
QUERY_OVERDUE_DAYS = 7


class MedicalMonitorService:
    """In-memory Medical Monitor Dashboard engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._signals: dict[str, SafetySignal] = {}
        self._assessments: dict[str, BenefitRiskAssessment] = {}
        self._queries: dict[str, MedicalQuery] = {}
        self._case_reviews: dict[str, PatientCaseReview] = {}
        self._trends: dict[str, SafetyTrend] = {}
        self._notes: dict[str, MedicalMonitorNote] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic medical monitoring data."""
        now = datetime.now(timezone.utc)

        # --- Safety Signals (4) ---
        signals_data = [
            {
                "id": "SIG-001",
                "trial_id": EYLEA_TRIAL,
                "signal_name": "Elevated hepatotoxicity cluster",
                "signal_type": "AE cluster",
                "detected_date": now - timedelta(days=45),
                "source": "Automated statistical detection",
                "description": (
                    "Cluster of 8 hepatotoxicity events observed in treatment arm "
                    "exceeding expected background rate. ALT/AST elevations >3x ULN "
                    "noted in 5 patients within a 30-day window."
                ),
                "affected_patients_count": 8,
                "incidence_rate": 4.2,
                "expected_rate": 1.5,
                "risk_level": RiskLevel.HIGH,
                "status": SignalStatus.UNDER_REVIEW,
                "assigned_to": "Dr. Rachel Kim",
                "reviewed_date": now - timedelta(days=40),
                "assessment_notes": "Initial review confirms disproportionality. Requesting hepatology consult.",
                "action_taken": None,
            },
            {
                "id": "SIG-002",
                "trial_id": DUPIXENT_TRIAL,
                "signal_name": "Injection site reaction increase",
                "signal_type": "AE frequency change",
                "detected_date": now - timedelta(days=30),
                "source": "SMC periodic review",
                "description": (
                    "Injection site reactions increased from 12% to 22% in the "
                    "last reporting period. Primarily mild-to-moderate severity."
                ),
                "affected_patients_count": 15,
                "incidence_rate": 22.0,
                "expected_rate": 12.0,
                "risk_level": RiskLevel.MODERATE,
                "status": SignalStatus.CONFIRMED,
                "assigned_to": "Dr. James Chen",
                "reviewed_date": now - timedelta(days=20),
                "assessment_notes": "Confirmed increased rate. Updating IB and consent forms.",
                "action_taken": "Updated Investigator Brochure section 5.3",
            },
            {
                "id": "SIG-003",
                "trial_id": LIBTAYO_TRIAL,
                "signal_name": "Cardiac QTc prolongation",
                "signal_type": "Lab abnormality",
                "detected_date": now - timedelta(days=15),
                "source": "Central ECG monitoring",
                "description": (
                    "Three patients showed QTcF prolongation >60ms from baseline. "
                    "One patient experienced syncope. All events occurred within "
                    "2 weeks of dose escalation to 480mg."
                ),
                "affected_patients_count": 3,
                "incidence_rate": 2.1,
                "expected_rate": 0.3,
                "risk_level": RiskLevel.VERY_HIGH,
                "status": SignalStatus.ESCALATED,
                "assigned_to": "Dr. Rachel Kim",
                "reviewed_date": now - timedelta(days=10),
                "assessment_notes": "Urgent review. Potential dose-dependent effect. Cardiology review requested.",
                "action_taken": "Enrollment pause at 480mg cohort. DSMB emergency meeting requested.",
            },
            {
                "id": "SIG-004",
                "trial_id": EYLEA_TRIAL,
                "signal_name": "Headache frequency in placebo arm",
                "signal_type": "AE cluster",
                "detected_date": now - timedelta(days=60),
                "source": "Routine safety review",
                "description": (
                    "Higher-than-expected headache rate in placebo arm. "
                    "Rate of 8.5% vs expected 5%. Review concluded likely "
                    "related to study procedures rather than IP."
                ),
                "affected_patients_count": 6,
                "incidence_rate": 8.5,
                "expected_rate": 5.0,
                "risk_level": RiskLevel.LOW,
                "status": SignalStatus.REFUTED,
                "assigned_to": "Dr. James Chen",
                "reviewed_date": now - timedelta(days=50),
                "assessment_notes": "Signal assessed as not related to IP. Attributable to lumbar puncture procedure.",
                "action_taken": "No further action required. Signal closed.",
            },
        ]
        for s in signals_data:
            self._signals[s["id"]] = SafetySignal(**s)

        # --- Benefit-Risk Assessments (3) ---
        assessments_data = [
            {
                "id": "BRA-001",
                "trial_id": EYLEA_TRIAL,
                "assessment_date": now - timedelta(days=90),
                "assessor": "Dr. Rachel Kim",
                "overall_outcome": AssessmentOutcome.FAVORABLE,
                "benefit_score": 78.0,
                "risk_score": 32.0,
                "benefit_summary": (
                    "Primary endpoint data shows 45% improvement in visual acuity "
                    "vs placebo (p<0.001). Secondary endpoints trending positive. "
                    "Durability of response observed through month 6."
                ),
                "risk_summary": (
                    "AE profile manageable. Most common AEs: headache (8%), "
                    "nasopharyngitis (6%), injection site reaction (5%). "
                    "One SAE (hepatotoxicity) under investigation."
                ),
                "data_cutoff_date": now - timedelta(days=95),
                "enrollment_at_assessment": 245,
                "next_review_date": now + timedelta(days=5),
                "recommendations": "Continue enrollment. Enhanced hepatic monitoring recommended.",
                "supporting_data": {
                    "primary_endpoint_met": True,
                    "interim_analysis_number": 2,
                    "dsmb_recommendation": "continue",
                },
            },
            {
                "id": "BRA-002",
                "trial_id": DUPIXENT_TRIAL,
                "assessment_date": now - timedelta(days=60),
                "assessor": "Dr. James Chen",
                "overall_outcome": AssessmentOutcome.FAVORABLE,
                "benefit_score": 82.0,
                "risk_score": 28.0,
                "benefit_summary": (
                    "Significant reduction in eczema severity score (EASI-75 response "
                    "rate: 62% vs 15% placebo). Quality of life improvements confirmed. "
                    "Response maintained through week 16."
                ),
                "risk_summary": (
                    "Injection site reactions noted at higher rate (22% vs expected 12%). "
                    "No dose-limiting toxicities. No deaths. "
                    "Infection rate comparable between arms."
                ),
                "data_cutoff_date": now - timedelta(days=65),
                "enrollment_at_assessment": 310,
                "next_review_date": now + timedelta(days=30),
                "recommendations": "Continue enrollment. Monitor injection site reaction rates.",
                "supporting_data": {
                    "primary_endpoint_met": True,
                    "interim_analysis_number": 3,
                    "dsmb_recommendation": "continue",
                },
            },
            {
                "id": "BRA-003",
                "trial_id": LIBTAYO_TRIAL,
                "assessment_date": now - timedelta(days=14),
                "assessor": "Dr. Rachel Kim",
                "overall_outcome": AssessmentOutcome.NEUTRAL,
                "benefit_score": 55.0,
                "risk_score": 58.0,
                "benefit_summary": (
                    "ORR of 28% in evaluable patients. Median PFS not yet reached. "
                    "Some durable responses observed but data immature."
                ),
                "risk_summary": (
                    "Concerning QTc prolongation signal at 480mg dose level. "
                    "Enrollment paused for that cohort. Grade 3-4 AE rate: 35%. "
                    "One treatment-related death under investigation."
                ),
                "data_cutoff_date": now - timedelta(days=16),
                "enrollment_at_assessment": 142,
                "next_review_date": now + timedelta(days=14),
                "recommendations": (
                    "Await cardiology review. Consider protocol amendment to cap dose at 360mg. "
                    "Convene DSMB for formal recommendation."
                ),
                "supporting_data": {
                    "primary_endpoint_met": False,
                    "interim_analysis_number": 1,
                    "dsmb_recommendation": "review_pending",
                },
            },
        ]
        for a in assessments_data:
            self._assessments[a["id"]] = BenefitRiskAssessment(**a)

        # --- Medical Queries (6) ---
        queries_data = [
            {
                "id": "MQ-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "patient_id": "PAT-1001",
                "category": QueryCategory.SAFETY,
                "priority": ReviewPriority.URGENT,
                "subject": "SAE causality assessment clarification",
                "query_text": (
                    "Patient PAT-1001 experienced Grade 3 hepatotoxicity. "
                    "Site assessed as 'possibly related'. Requesting medical "
                    "monitor's independent assessment of causality."
                ),
                "raised_by": "Dr. Sarah Mitchell (Site PI)",
                "raised_date": now - timedelta(days=10),
                "assigned_to": "Dr. Rachel Kim",
                "response_text": (
                    "Reviewed case in detail. Temporal relationship supports possible "
                    "causality. Recommend continued monitoring with weekly LFTs. "
                    "Agree with site's assessment of 'possibly related'."
                ),
                "responded_date": now - timedelta(days=8),
                "status": QueryStatus.RESOLVED,
                "resolution_date": now - timedelta(days=7),
                "follow_up_required": True,
            },
            {
                "id": "MQ-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-103",
                "patient_id": "PAT-3042",
                "category": QueryCategory.ELIGIBILITY,
                "priority": ReviewPriority.ELEVATED,
                "subject": "Borderline exclusion criterion - prior retinal surgery",
                "query_text": (
                    "Patient had vitrectomy 14 months ago. Exclusion criterion "
                    "states 'retinal surgery within 12 months'. Patient's surgeon "
                    "confirms full recovery. Requesting eligibility determination."
                ),
                "raised_by": "Dr. David Park (Sub-investigator)",
                "raised_date": now - timedelta(days=5),
                "assigned_to": "Dr. James Chen",
                "response_text": None,
                "responded_date": None,
                "status": QueryStatus.ASSIGNED,
                "resolution_date": None,
                "follow_up_required": False,
            },
            {
                "id": "MQ-003",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "patient_id": None,
                "category": QueryCategory.PROTOCOL_COMPLIANCE,
                "priority": ReviewPriority.ROUTINE,
                "subject": "Dose modification guidance for mild renal impairment",
                "query_text": (
                    "Three patients at site have developed mild renal impairment "
                    "(eGFR 45-59 mL/min). Protocol does not specify dose adjustments "
                    "for this level. Requesting guidance."
                ),
                "raised_by": "Jennifer Lee (CRA)",
                "raised_date": now - timedelta(days=15),
                "assigned_to": "Dr. James Chen",
                "response_text": (
                    "No dose adjustment required for mild renal impairment (eGFR 45-59). "
                    "Continue current dose. Monitor renal function monthly. "
                    "Discontinue if eGFR <30 mL/min. Will issue protocol clarification letter."
                ),
                "responded_date": now - timedelta(days=12),
                "status": QueryStatus.RESOLVED,
                "resolution_date": now - timedelta(days=11),
                "follow_up_required": False,
            },
            {
                "id": "MQ-004",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-107",
                "patient_id": "PAT-7023",
                "category": QueryCategory.SAFETY,
                "priority": ReviewPriority.CRITICAL,
                "subject": "Syncope event with QTc prolongation - immediate guidance needed",
                "query_text": (
                    "Patient experienced syncope with QTcF interval of 510ms. "
                    "Currently in hospital observation. Requesting immediate "
                    "guidance on study drug management and reporting requirements."
                ),
                "raised_by": "Dr. Lisa Wong (Site PI)",
                "raised_date": now - timedelta(days=3),
                "assigned_to": "Dr. Rachel Kim",
                "response_text": None,
                "responded_date": None,
                "status": QueryStatus.ASSIGNED,
                "resolution_date": None,
                "follow_up_required": False,
            },
            {
                "id": "MQ-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-105",
                "patient_id": "PAT-5011",
                "category": QueryCategory.DATA_CLARIFICATION,
                "priority": ReviewPriority.ROUTINE,
                "subject": "Inconsistent lab values between local and central lab",
                "query_text": (
                    "Local lab eosinophil count is 0.8x10^9/L but central lab "
                    "reports 0.3x10^9/L from same-day draw. Requesting guidance "
                    "on which value to use for efficacy analysis."
                ),
                "raised_by": "Maria Santos (Data Manager)",
                "raised_date": now - timedelta(days=20),
                "assigned_to": None,
                "response_text": None,
                "responded_date": None,
                "status": QueryStatus.OPEN,
                "resolution_date": None,
                "follow_up_required": False,
            },
            {
                "id": "MQ-006",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "patient_id": "PAT-2015",
                "category": QueryCategory.EFFICACY,
                "priority": ReviewPriority.ELEVATED,
                "subject": "Early discontinuation due to lack of efficacy",
                "query_text": (
                    "Patient shows no improvement after 4 months on treatment. "
                    "Site PI considering early discontinuation. Protocol allows "
                    "discontinuation for lack of efficacy after 3 months. "
                    "Requesting medical monitor review."
                ),
                "raised_by": "Dr. Sarah Mitchell (Site PI)",
                "raised_date": now - timedelta(days=2),
                "assigned_to": "Dr. Rachel Kim",
                "response_text": None,
                "responded_date": None,
                "status": QueryStatus.ASSIGNED,
                "resolution_date": None,
                "follow_up_required": False,
            },
        ]
        for q in queries_data:
            self._queries[q["id"]] = MedicalQuery(**q)

        # --- Patient Case Reviews (4) ---
        case_reviews_data = [
            {
                "id": "CR-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "patient_id": "PAT-1001",
                "review_reason": "SAE - Grade 3 hepatotoxicity. Causality assessment required.",
                "priority": ReviewPriority.URGENT,
                "status": CaseReviewStatus.COMPLETED,
                "reviewer": "Dr. Rachel Kim",
                "review_date": now - timedelta(days=8),
                "clinical_summary": (
                    "65-year-old male, treatment arm. Developed elevated ALT (5.2x ULN) "
                    "and AST (3.8x ULN) at Week 8 visit. No prior liver disease. "
                    "Concurrent medications reviewed - no known hepatotoxins."
                ),
                "findings": (
                    "Temporal relationship supports possible causality. "
                    "Hy's Law criteria not met (bilirubin normal). "
                    "Pattern consistent with hepatocellular injury."
                ),
                "recommendations": (
                    "Continue dose hold. Repeat LFTs weekly until normalization. "
                    "Rechallenge only if LFTs normalize within 4 weeks and after "
                    "hepatology consult. Report as SUSAR per protocol."
                ),
                "action_items": [
                    "Schedule hepatology consult within 5 days",
                    "Order weekly LFTs for 4 weeks",
                    "File SUSAR within 15 days of awareness",
                    "Update DSUR hepatotoxicity section",
                ],
                "follow_up_date": now + timedelta(days=7),
            },
            {
                "id": "CR-002",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-107",
                "patient_id": "PAT-7023",
                "review_reason": "Syncope with QTcF prolongation >500ms. Dose-response evaluation.",
                "priority": ReviewPriority.CRITICAL,
                "status": CaseReviewStatus.IN_REVIEW,
                "reviewer": "Dr. Rachel Kim",
                "review_date": None,
                "clinical_summary": (
                    "58-year-old female on 480mg dose level. Developed syncope "
                    "on Day 22 of Cycle 3. ECG showed QTcF 510ms (baseline 420ms). "
                    "No structural heart disease. Electrolytes normal."
                ),
                "findings": None,
                "recommendations": None,
                "action_items": None,
                "follow_up_date": None,
            },
            {
                "id": "CR-003",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-105",
                "patient_id": "PAT-5033",
                "review_reason": "Pregnancy reported during study. Protocol deviation assessment.",
                "priority": ReviewPriority.URGENT,
                "status": CaseReviewStatus.PENDING,
                "reviewer": None,
                "review_date": None,
                "clinical_summary": None,
                "findings": None,
                "recommendations": None,
                "action_items": None,
                "follow_up_date": None,
            },
            {
                "id": "CR-004",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "patient_id": "PAT-2015",
                "review_reason": "Lack of efficacy after 4 months. Early discontinuation review.",
                "priority": ReviewPriority.ELEVATED,
                "status": CaseReviewStatus.PENDING,
                "reviewer": "Dr. James Chen",
                "review_date": None,
                "clinical_summary": None,
                "findings": None,
                "recommendations": None,
                "action_items": None,
                "follow_up_date": None,
            },
        ]
        for cr in case_reviews_data:
            self._case_reviews[cr["id"]] = PatientCaseReview(**cr)

        # --- Safety Trends (5) ---
        trends_data = [
            {
                "id": "TRD-001",
                "trial_id": EYLEA_TRIAL,
                "event_type": "Hepatotoxicity (any grade)",
                "period_start": now - timedelta(days=90),
                "period_end": now - timedelta(days=1),
                "event_count": 12,
                "rate_per_100_patients": 4.9,
                "previous_period_rate": 2.1,
                "trend_direction": TrendDirection.INCREASING,
                "statistical_significance": True,
                "notes": "Statistically significant increase (p=0.018). Driven by SIG-001 cluster.",
            },
            {
                "id": "TRD-002",
                "trial_id": DUPIXENT_TRIAL,
                "event_type": "Injection site reaction",
                "period_start": now - timedelta(days=90),
                "period_end": now - timedelta(days=1),
                "event_count": 34,
                "rate_per_100_patients": 22.0,
                "previous_period_rate": 12.0,
                "trend_direction": TrendDirection.INCREASING,
                "statistical_significance": True,
                "notes": "Significant increase in ISR rate. Protocol amendment under consideration.",
            },
            {
                "id": "TRD-003",
                "trial_id": LIBTAYO_TRIAL,
                "event_type": "QTc prolongation (>60ms from baseline)",
                "period_start": now - timedelta(days=60),
                "period_end": now - timedelta(days=1),
                "event_count": 3,
                "rate_per_100_patients": 2.1,
                "previous_period_rate": 0.0,
                "trend_direction": TrendDirection.INCREASING,
                "statistical_significance": False,
                "notes": "Small numbers but clinically concerning. All at 480mg dose level.",
            },
            {
                "id": "TRD-004",
                "trial_id": EYLEA_TRIAL,
                "event_type": "Nasopharyngitis",
                "period_start": now - timedelta(days=90),
                "period_end": now - timedelta(days=1),
                "event_count": 15,
                "rate_per_100_patients": 6.1,
                "previous_period_rate": 6.5,
                "trend_direction": TrendDirection.STABLE,
                "statistical_significance": False,
                "notes": "Rate consistent with expected background rate.",
            },
            {
                "id": "TRD-005",
                "trial_id": DUPIXENT_TRIAL,
                "event_type": "Conjunctivitis",
                "period_start": now - timedelta(days=90),
                "period_end": now - timedelta(days=1),
                "event_count": 8,
                "rate_per_100_patients": 5.2,
                "previous_period_rate": 7.8,
                "trend_direction": TrendDirection.DECREASING,
                "statistical_significance": False,
                "notes": "Rate declining. Likely reflects improved patient counseling.",
            },
        ]
        for t in trends_data:
            self._trends[t["id"]] = SafetyTrend(**t)

        # --- Medical Monitor Notes (3) ---
        notes_data = [
            {
                "id": "MMN-001",
                "trial_id": EYLEA_TRIAL,
                "author": "Dr. Rachel Kim",
                "note_date": now - timedelta(days=8),
                "category": NoteCategory.SAFETY_REVIEW,
                "subject": "Hepatotoxicity signal - initial assessment summary",
                "content": (
                    "Completed initial assessment of hepatotoxicity cluster. "
                    "8 patients affected, predominantly in first 12 weeks of treatment. "
                    "Requesting hepatology expert panel review. Enhanced monitoring "
                    "protocol drafted for DSMB review."
                ),
                "referenced_patients": ["PAT-1001", "PAT-1018", "PAT-3042"],
                "referenced_signals": ["SIG-001"],
                "visibility": NoteVisibility.TEAM,
            },
            {
                "id": "MMN-002",
                "trial_id": LIBTAYO_TRIAL,
                "author": "Dr. Rachel Kim",
                "note_date": now - timedelta(days=3),
                "category": NoteCategory.BENEFIT_RISK,
                "subject": "QTc signal - urgent benefit-risk considerations",
                "content": (
                    "QTc prolongation signal at 480mg dose level requires immediate "
                    "attention. Benefit-risk profile shifting to neutral/unfavorable "
                    "at this dose. Recommending enrollment pause at 480mg pending "
                    "DSMB review. Lower dose cohorts maintain favorable profile."
                ),
                "referenced_patients": ["PAT-7023"],
                "referenced_signals": ["SIG-003"],
                "visibility": NoteVisibility.SPONSOR,
            },
            {
                "id": "MMN-003",
                "trial_id": DUPIXENT_TRIAL,
                "author": "Dr. James Chen",
                "note_date": now - timedelta(days=12),
                "category": NoteCategory.MEDICAL_QUERY,
                "subject": "Renal impairment dose guidance - protocol clarification",
                "content": (
                    "Issued protocol clarification letter regarding dose modifications "
                    "for patients with mild renal impairment. No dose adjustment needed "
                    "for eGFR 45-59 mL/min. Discontinue if eGFR <30 mL/min."
                ),
                "referenced_patients": None,
                "referenced_signals": None,
                "visibility": NoteVisibility.TEAM,
            },
        ]
        for n in notes_data:
            self._notes[n["id"]] = MedicalMonitorNote(**n)

    # ------------------------------------------------------------------
    # Safety Signals
    # ------------------------------------------------------------------

    def list_signals(
        self,
        *,
        trial_id: str | None = None,
        status: SignalStatus | None = None,
        risk_level: RiskLevel | None = None,
    ) -> list[SafetySignal]:
        """List safety signals with optional filters."""
        with self._lock:
            result = list(self._signals.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if status is not None:
            result = [s for s in result if s.status == status]
        if risk_level is not None:
            result = [s for s in result if s.risk_level == risk_level]

        return sorted(result, key=lambda s: s.detected_date, reverse=True)

    def get_signal(self, signal_id: str) -> SafetySignal | None:
        """Get a single safety signal by ID."""
        with self._lock:
            return self._signals.get(signal_id)

    def create_signal(self, payload: SafetySignalCreate) -> SafetySignal:
        """Create a new safety signal."""
        signal_id = f"SIG-{uuid4().hex[:8].upper()}"
        signal = SafetySignal(
            id=signal_id,
            status=SignalStatus.DETECTED,
            **payload.model_dump(),
        )
        with self._lock:
            self._signals[signal_id] = signal
        logger.info("Created safety signal %s: %s", signal_id, payload.signal_name)
        return signal

    def update_signal(self, signal_id: str, payload: SafetySignalUpdate) -> SafetySignal | None:
        """Update a safety signal."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._signals.get(signal_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            # Auto-set reviewed_date when status changes to under_review or later
            if "status" in updates and existing.reviewed_date is None:
                status_val = updates["status"]
                if isinstance(status_val, str):
                    status_val = SignalStatus(status_val)
                if status_val not in (SignalStatus.DETECTED,):
                    updates["reviewed_date"] = now
            data.update(updates)
            updated = SafetySignal(**data)
            self._signals[signal_id] = updated
        return updated

    def escalate_signal(self, signal_id: str, payload: SignalEscalation) -> SafetySignal | None:
        """Escalate a safety signal."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._signals.get(signal_id)
            if existing is None:
                return None
            if existing.status in (SignalStatus.CLOSED, SignalStatus.REFUTED):
                raise ValueError(
                    f"Cannot escalate signal '{signal_id}' with status '{existing.status.value}'"
                )
            data = existing.model_dump()
            data["status"] = SignalStatus.ESCALATED
            data["assessment_notes"] = (
                f"ESCALATED: {payload.reason}. Escalated to: {payload.escalated_to}. "
                f"{('Recommended action: ' + payload.recommended_action) if payload.recommended_action else ''}"
            ).strip()
            if data.get("reviewed_date") is None:
                data["reviewed_date"] = now
            updated = SafetySignal(**data)
            self._signals[signal_id] = updated
        logger.info("Escalated signal %s to %s", signal_id, payload.escalated_to)
        return updated

    # ------------------------------------------------------------------
    # Benefit-Risk Assessments
    # ------------------------------------------------------------------

    def list_assessments(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[BenefitRiskAssessment]:
        """List benefit-risk assessments with optional trial filter."""
        with self._lock:
            result = list(self._assessments.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]

        return sorted(result, key=lambda a: a.assessment_date, reverse=True)

    def get_assessment(self, assessment_id: str) -> BenefitRiskAssessment | None:
        """Get a single benefit-risk assessment by ID."""
        with self._lock:
            return self._assessments.get(assessment_id)

    def create_assessment(self, payload: BenefitRiskAssessmentCreate) -> BenefitRiskAssessment:
        """Create a new benefit-risk assessment."""
        now = datetime.now(timezone.utc)
        assessment_id = f"BRA-{uuid4().hex[:8].upper()}"
        assessment = BenefitRiskAssessment(
            id=assessment_id,
            assessment_date=now,
            **payload.model_dump(),
        )
        with self._lock:
            self._assessments[assessment_id] = assessment
        logger.info("Created benefit-risk assessment %s for trial %s", assessment_id, payload.trial_id)
        return assessment

    def update_assessment(
        self, assessment_id: str, payload: BenefitRiskAssessmentUpdate
    ) -> BenefitRiskAssessment | None:
        """Update a benefit-risk assessment."""
        with self._lock:
            existing = self._assessments.get(assessment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = BenefitRiskAssessment(**data)
            self._assessments[assessment_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Medical Queries
    # ------------------------------------------------------------------

    def list_queries(
        self,
        *,
        trial_id: str | None = None,
        site_id: str | None = None,
        category: QueryCategory | None = None,
        status: QueryStatus | None = None,
        priority: ReviewPriority | None = None,
    ) -> list[MedicalQuery]:
        """List medical queries with optional filters."""
        with self._lock:
            result = list(self._queries.values())

        if trial_id is not None:
            result = [q for q in result if q.trial_id == trial_id]
        if site_id is not None:
            result = [q for q in result if q.site_id == site_id]
        if category is not None:
            result = [q for q in result if q.category == category]
        if status is not None:
            result = [q for q in result if q.status == status]
        if priority is not None:
            result = [q for q in result if q.priority == priority]

        return sorted(result, key=lambda q: q.raised_date, reverse=True)

    def get_query(self, query_id: str) -> MedicalQuery | None:
        """Get a single medical query by ID."""
        with self._lock:
            return self._queries.get(query_id)

    def create_query(self, payload: MedicalQueryCreate) -> MedicalQuery:
        """Create a new medical query."""
        now = datetime.now(timezone.utc)
        query_id = f"MQ-{uuid4().hex[:8].upper()}"
        query = MedicalQuery(
            id=query_id,
            raised_date=now,
            status=QueryStatus.OPEN,
            **payload.model_dump(),
        )
        with self._lock:
            self._queries[query_id] = query
        logger.info("Created medical query %s: %s", query_id, payload.subject)
        return query

    def update_query(self, query_id: str, payload: MedicalQueryUpdate) -> MedicalQuery | None:
        """Update a medical query."""
        with self._lock:
            existing = self._queries.get(query_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = MedicalQuery(**data)
            self._queries[query_id] = updated
        return updated

    def respond_to_query(self, query_id: str, payload: MedicalQueryResponse) -> MedicalQuery | None:
        """Respond to a medical query."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._queries.get(query_id)
            if existing is None:
                return None
            if existing.status in (QueryStatus.RESOLVED, QueryStatus.CLOSED):
                raise ValueError(
                    f"Cannot respond to query '{query_id}' with status '{existing.status.value}'"
                )
            data = existing.model_dump()
            data["response_text"] = payload.response_text
            data["responded_date"] = now
            data["status"] = QueryStatus.RESPONDED
            data["follow_up_required"] = payload.follow_up_required
            updated = MedicalQuery(**data)
            self._queries[query_id] = updated
        logger.info("Responded to query %s", query_id)
        return updated

    def resolve_query(self, query_id: str) -> MedicalQuery | None:
        """Resolve a medical query (mark as resolved)."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._queries.get(query_id)
            if existing is None:
                return None
            if existing.status == QueryStatus.CLOSED:
                raise ValueError(f"Cannot resolve query '{query_id}' - already closed")
            if existing.response_text is None:
                raise ValueError(f"Cannot resolve query '{query_id}' - no response provided")
            data = existing.model_dump()
            data["status"] = QueryStatus.RESOLVED
            data["resolution_date"] = now
            updated = MedicalQuery(**data)
            self._queries[query_id] = updated
        logger.info("Resolved query %s", query_id)
        return updated

    # ------------------------------------------------------------------
    # Patient Case Reviews
    # ------------------------------------------------------------------

    def list_case_reviews(
        self,
        *,
        trial_id: str | None = None,
        status: CaseReviewStatus | None = None,
        priority: ReviewPriority | None = None,
    ) -> list[PatientCaseReview]:
        """List case reviews with optional filters."""
        with self._lock:
            result = list(self._case_reviews.values())

        if trial_id is not None:
            result = [cr for cr in result if cr.trial_id == trial_id]
        if status is not None:
            result = [cr for cr in result if cr.status == status]
        if priority is not None:
            result = [cr for cr in result if cr.priority == priority]

        return sorted(
            result,
            key=lambda cr: {
                ReviewPriority.CRITICAL: 0,
                ReviewPriority.URGENT: 1,
                ReviewPriority.ELEVATED: 2,
                ReviewPriority.ROUTINE: 3,
            }.get(cr.priority, 4),
        )

    def get_case_review(self, review_id: str) -> PatientCaseReview | None:
        """Get a single case review by ID."""
        with self._lock:
            return self._case_reviews.get(review_id)

    def create_case_review(self, payload: PatientCaseReviewCreate) -> PatientCaseReview:
        """Create a new patient case review."""
        review_id = f"CR-{uuid4().hex[:8].upper()}"
        review = PatientCaseReview(
            id=review_id,
            status=CaseReviewStatus.PENDING,
            **payload.model_dump(),
        )
        with self._lock:
            self._case_reviews[review_id] = review
        logger.info("Created case review %s for patient %s", review_id, payload.patient_id)
        return review

    def update_case_review(
        self, review_id: str, payload: PatientCaseReviewUpdate
    ) -> PatientCaseReview | None:
        """Update a patient case review."""
        with self._lock:
            existing = self._case_reviews.get(review_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = PatientCaseReview(**data)
            self._case_reviews[review_id] = updated
        return updated

    def complete_case_review(
        self, review_id: str, payload: CaseReviewCompletion
    ) -> PatientCaseReview | None:
        """Complete a patient case review with findings and recommendations."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._case_reviews.get(review_id)
            if existing is None:
                return None
            if existing.status == CaseReviewStatus.COMPLETED:
                raise ValueError(f"Case review '{review_id}' is already completed")
            data = existing.model_dump()
            data["status"] = CaseReviewStatus.COMPLETED
            data["review_date"] = now
            data["clinical_summary"] = payload.clinical_summary
            data["findings"] = payload.findings
            data["recommendations"] = payload.recommendations
            data["action_items"] = payload.action_items
            data["follow_up_date"] = payload.follow_up_date
            updated = PatientCaseReview(**data)
            self._case_reviews[review_id] = updated
        logger.info("Completed case review %s", review_id)
        return updated

    # ------------------------------------------------------------------
    # Safety Trends
    # ------------------------------------------------------------------

    def list_trends(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[SafetyTrend]:
        """List safety trends with optional trial filter."""
        with self._lock:
            result = list(self._trends.values())

        if trial_id is not None:
            result = [t for t in result if t.trial_id == trial_id]

        return sorted(result, key=lambda t: t.period_end, reverse=True)

    def get_trial_trends(self, trial_id: str) -> list[SafetyTrend]:
        """Get all safety trends for a specific trial."""
        with self._lock:
            result = [t for t in self._trends.values() if t.trial_id == trial_id]

        return sorted(result, key=lambda t: t.period_end, reverse=True)

    def analyze_trends(self, trial_id: str) -> list[SafetyTrend]:
        """Analyze and return concerning trends for a trial.

        Returns only trends that are increasing or statistically significant.
        """
        all_trends = self.get_trial_trends(trial_id)
        return [
            t for t in all_trends
            if t.trend_direction == TrendDirection.INCREASING
            or t.statistical_significance
        ]

    # ------------------------------------------------------------------
    # Medical Monitor Notes
    # ------------------------------------------------------------------

    def list_notes(
        self,
        *,
        trial_id: str | None = None,
        category: NoteCategory | None = None,
    ) -> list[MedicalMonitorNote]:
        """List medical monitor notes with optional filters."""
        with self._lock:
            result = list(self._notes.values())

        if trial_id is not None:
            result = [n for n in result if n.trial_id == trial_id]
        if category is not None:
            result = [n for n in result if n.category == category]

        return sorted(result, key=lambda n: n.note_date, reverse=True)

    def get_note(self, note_id: str) -> MedicalMonitorNote | None:
        """Get a single note by ID."""
        with self._lock:
            return self._notes.get(note_id)

    def create_note(self, payload: MedicalMonitorNoteCreate) -> MedicalMonitorNote:
        """Create a new medical monitor note."""
        now = datetime.now(timezone.utc)
        note_id = f"MMN-{uuid4().hex[:8].upper()}"
        note = MedicalMonitorNote(
            id=note_id,
            note_date=now,
            **payload.model_dump(),
        )
        with self._lock:
            self._notes[note_id] = note
        logger.info("Created medical monitor note %s", note_id)
        return note

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> MedicalMonitorMetrics:
        """Compute aggregated medical monitor operational metrics."""
        now = datetime.now(timezone.utc)

        with self._lock:
            signals = list(self._signals.values())
            assessments = list(self._assessments.values())
            queries = list(self._queries.values())
            case_reviews = list(self._case_reviews.values())
            trends = list(self._trends.values())

        # Open signals (not closed or refuted)
        open_signals = sum(
            1 for s in signals
            if s.status not in (SignalStatus.CLOSED, SignalStatus.REFUTED)
        )

        # Pending case reviews
        pending_reviews = sum(
            1 for cr in case_reviews
            if cr.status in (CaseReviewStatus.PENDING, CaseReviewStatus.IN_REVIEW)
        )

        # Overdue queries (open/assigned for more than QUERY_OVERDUE_DAYS)
        overdue_queries = sum(
            1 for q in queries
            if q.status in (QueryStatus.OPEN, QueryStatus.ASSIGNED)
            and (now - q.raised_date).days > QUERY_OVERDUE_DAYS
        )

        # Average query resolution time
        resolved_queries = [
            q for q in queries
            if q.resolution_date is not None and q.raised_date is not None
        ]
        if resolved_queries:
            total_days = sum(
                (q.resolution_date - q.raised_date).total_seconds() / 86400
                for q in resolved_queries
            )
            avg_resolution = round(total_days / len(resolved_queries), 1)
        else:
            avg_resolution = 0.0

        # Assessments due within 30 days
        assessments_due = sum(
            1 for a in assessments
            if a.next_review_date is not None
            and a.next_review_date <= now + timedelta(days=30)
        )

        # Critical cases
        critical_cases = sum(
            1 for cr in case_reviews
            if cr.priority == ReviewPriority.CRITICAL
            and cr.status not in (CaseReviewStatus.COMPLETED, CaseReviewStatus.DEFERRED)
        )

        # Active increasing trends
        active_trends = sum(
            1 for t in trends
            if t.trend_direction == TrendDirection.INCREASING
        )

        return MedicalMonitorMetrics(
            open_signals=open_signals,
            pending_reviews=pending_reviews,
            overdue_queries=overdue_queries,
            avg_query_resolution_days=avg_resolution,
            assessments_due=assessments_due,
            critical_cases=critical_cases,
            active_trends=active_trends,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: MedicalMonitorService | None = None
_lock = threading.Lock()


def get_medical_monitor_service() -> MedicalMonitorService:
    """Return the singleton MedicalMonitorService instance."""
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = MedicalMonitorService()
    return _instance


def reset_medical_monitor_service() -> MedicalMonitorService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _lock:
        _instance = MedicalMonitorService()
    return _instance
