"""Data Safety Monitoring Board (DSMB) Service (CLINICAL-3).

Manages DSMB operations including board membership, meeting governance,
interim analyses with group-sequential stopping rules, event adjudication
workflows, safety report generation (blinded/unblinded), and charter management.

Usage:
    from app.services.safety_monitoring_service import (
        get_safety_monitoring_service,
    )

    svc = get_safety_monitoring_service()
    members = svc.list_members()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import math
import threading
from collections import Counter
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.safety_monitoring import (
    DSMBCharter,
    DSMBCharterCreate,
    DSMBCharterUpdate,
    DSMBMeeting,
    DSMBMeetingCreate,
    DSMBMeetingUpdate,
    DSMBMember,
    DSMBMemberCreate,
    DSMBMemberUpdate,
    DSMBMetrics,
    DSMBRole,
    EventAdjudication,
    EventAdjudicationCreate,
    EventAdjudicationStatus,
    EventAdjudicationUpdate,
    InterimAnalysis,
    InterimAnalysisCreate,
    InterimAnalysisType,
    MeetingType,
    ReportAccessLevel,
    ReviewOutcome,
    SafetyReport,
    SafetyReportCreate,
    StoppingBoundary,
    StoppingRule,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

# Adjudications older than 30 days in PENDING status are considered overdue
OVERDUE_ADJUDICATION_DAYS = 30

# Valid adjudication status transitions
VALID_ADJUDICATION_TRANSITIONS: dict[EventAdjudicationStatus, set[EventAdjudicationStatus]] = {
    EventAdjudicationStatus.PENDING: {EventAdjudicationStatus.UNDER_REVIEW},
    EventAdjudicationStatus.UNDER_REVIEW: {
        EventAdjudicationStatus.ADJUDICATED,
        EventAdjudicationStatus.PENDING,
    },
    EventAdjudicationStatus.ADJUDICATED: {EventAdjudicationStatus.APPEALED},
    EventAdjudicationStatus.APPEALED: {
        EventAdjudicationStatus.UNDER_REVIEW,
        EventAdjudicationStatus.ADJUDICATED,
    },
}


class SafetyMonitoringService:
    """In-memory DSMB management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._members: dict[str, DSMBMember] = {}
        self._meetings: dict[str, DSMBMeeting] = {}
        self._interim_analyses: dict[str, InterimAnalysis] = {}
        self._adjudications: dict[str, EventAdjudication] = {}
        self._safety_reports: dict[str, SafetyReport] = {}
        self._charters: dict[str, DSMBCharter] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic DSMB data across 3 Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 8 DSMB Members across 3 trials ---
        members_data = [
            {
                "id": "DSMB-MEM-001",
                "name": "Dr. Margaret Thompson",
                "role": DSMBRole.CHAIR,
                "institution": "Johns Hopkins University",
                "specialty": "Clinical Pharmacology",
                "email": "m.thompson@jhu.edu",
                "conflict_of_interest_declared": False,
                "coi_details": None,
                "term_start": now - timedelta(days=365),
                "term_end": now + timedelta(days=730),
                "active": True,
            },
            {
                "id": "DSMB-MEM-002",
                "name": "Dr. Robert Kline",
                "role": DSMBRole.BIOSTATISTICIAN,
                "institution": "Harvard T.H. Chan School of Public Health",
                "specialty": "Biostatistics",
                "email": "r.kline@hsph.harvard.edu",
                "conflict_of_interest_declared": False,
                "coi_details": None,
                "term_start": now - timedelta(days=365),
                "term_end": now + timedelta(days=730),
                "active": True,
            },
            {
                "id": "DSMB-MEM-003",
                "name": "Dr. Lisa Chen",
                "role": DSMBRole.CLINICIAN,
                "institution": "Mayo Clinic",
                "specialty": "Ophthalmology",
                "email": "l.chen@mayo.edu",
                "conflict_of_interest_declared": False,
                "coi_details": None,
                "term_start": now - timedelta(days=300),
                "term_end": now + timedelta(days=795),
                "active": True,
            },
            {
                "id": "DSMB-MEM-004",
                "name": "Dr. James Okonkwo",
                "role": DSMBRole.CLINICIAN,
                "institution": "Cleveland Clinic",
                "specialty": "Dermatology",
                "email": "j.okonkwo@ccf.org",
                "conflict_of_interest_declared": True,
                "coi_details": "Previously consulted for a Regeneron competitor (2021-2022), no active engagement",
                "term_start": now - timedelta(days=200),
                "term_end": now + timedelta(days=895),
                "active": True,
            },
            {
                "id": "DSMB-MEM-005",
                "name": "Dr. Patricia Alvarez",
                "role": DSMBRole.ETHICIST,
                "institution": "University of Pennsylvania",
                "specialty": "Clinical Research Ethics",
                "email": "p.alvarez@upenn.edu",
                "conflict_of_interest_declared": False,
                "coi_details": None,
                "term_start": now - timedelta(days=365),
                "term_end": now + timedelta(days=730),
                "active": True,
            },
            {
                "id": "DSMB-MEM-006",
                "name": "Maria Santos",
                "role": DSMBRole.PATIENT_ADVOCATE,
                "institution": "National Health Council",
                "specialty": "Patient Advocacy",
                "email": "m.santos@nhcouncil.org",
                "conflict_of_interest_declared": False,
                "coi_details": None,
                "term_start": now - timedelta(days=180),
                "term_end": now + timedelta(days=915),
                "active": True,
            },
            {
                "id": "DSMB-MEM-007",
                "name": "Dr. Hiroshi Tanaka",
                "role": DSMBRole.CLINICIAN,
                "institution": "Memorial Sloan Kettering",
                "specialty": "Oncology",
                "email": "h.tanaka@mskcc.org",
                "conflict_of_interest_declared": False,
                "coi_details": None,
                "term_start": now - timedelta(days=365),
                "term_end": now + timedelta(days=730),
                "active": True,
            },
            {
                "id": "DSMB-MEM-008",
                "name": "Dr. Emily Watson",
                "role": DSMBRole.BIOSTATISTICIAN,
                "institution": "Stanford University",
                "specialty": "Adaptive Trial Design",
                "email": "e.watson@stanford.edu",
                "conflict_of_interest_declared": False,
                "coi_details": None,
                "term_start": now - timedelta(days=120),
                "term_end": now + timedelta(days=975),
                "active": False,  # On leave
            },
        ]

        for m in members_data:
            self._members[m["id"]] = DSMBMember(**m)

        # --- 6 Meetings: 4 scheduled, 1 ad-hoc, 1 emergency ---
        meetings_data = [
            {
                "id": "DSMB-MTG-001",
                "trial_id": EYLEA_TRIAL,
                "meeting_type": MeetingType.SCHEDULED,
                "meeting_date": now - timedelta(days=90),
                "attendees": ["DSMB-MEM-001", "DSMB-MEM-002", "DSMB-MEM-003", "DSMB-MEM-005", "DSMB-MEM-006"],
                "agenda": ["Review enrollment progress", "Safety data review - Q1", "Protocol amendment discussion"],
                "minutes_summary": "Reviewed 120 enrolled patients. No significant safety signals detected. Enrollment on track. Approved minor protocol amendment for inclusion criteria age range expansion.",
                "outcome": ReviewOutcome.CONTINUE_UNCHANGED,
                "recommendations": ["Continue enrollment per protocol", "Schedule next review in 12 weeks"],
                "action_items": ["Sponsor to submit protocol amendment to IRB", "Statistician to prepare updated DMC report"],
                "next_meeting_date": now - timedelta(days=6),
                "created_at": now - timedelta(days=91),
            },
            {
                "id": "DSMB-MTG-002",
                "trial_id": DUPIXENT_TRIAL,
                "meeting_type": MeetingType.SCHEDULED,
                "meeting_date": now - timedelta(days=60),
                "attendees": ["DSMB-MEM-001", "DSMB-MEM-002", "DSMB-MEM-004", "DSMB-MEM-005"],
                "agenda": ["Interim safety analysis review", "SAE review", "Enrollment update"],
                "minutes_summary": "Reviewed interim data for 200 randomized patients. Two SAEs noted in treatment arm - both resolved. No imbalance in event rates between arms. Enrollment slightly behind target.",
                "outcome": ReviewOutcome.CONTINUE_UNCHANGED,
                "recommendations": ["Continue per protocol", "Increase site recruitment efforts"],
                "action_items": ["Sponsor to address enrollment lag", "Next unblinded report for 50% enrollment"],
                "next_meeting_date": now + timedelta(days=30),
                "created_at": now - timedelta(days=61),
            },
            {
                "id": "DSMB-MTG-003",
                "trial_id": LIBTAYO_TRIAL,
                "meeting_type": MeetingType.SCHEDULED,
                "meeting_date": now - timedelta(days=30),
                "attendees": ["DSMB-MEM-001", "DSMB-MEM-002", "DSMB-MEM-007", "DSMB-MEM-005", "DSMB-MEM-006"],
                "agenda": ["First interim analysis review", "Safety profile assessment", "Stopping rule evaluation"],
                "minutes_summary": "First interim analysis at 33% information fraction. O'Brien-Fleming efficacy boundary not crossed. No safety concerns. Futility boundary not approached. Trial continues.",
                "outcome": ReviewOutcome.CONTINUE_UNCHANGED,
                "recommendations": ["Continue to second interim analysis", "Maintain current monitoring schedule"],
                "action_items": ["Prepare safety update for regulatory authority", "Plan second interim at 66% information fraction"],
                "next_meeting_date": now + timedelta(days=60),
                "created_at": now - timedelta(days=31),
            },
            {
                "id": "DSMB-MTG-004",
                "trial_id": EYLEA_TRIAL,
                "meeting_type": MeetingType.SCHEDULED,
                "meeting_date": now - timedelta(days=6),
                "attendees": ["DSMB-MEM-001", "DSMB-MEM-002", "DSMB-MEM-003", "DSMB-MEM-005"],
                "agenda": ["Q2 safety data review", "Adjudication outcomes review", "Protocol compliance"],
                "minutes_summary": "Reviewed 180 enrolled patients. Adjudicated 3 endpoint events. Slight increase in injection site reactions noted but within expected range. No protocol deviations of concern.",
                "outcome": ReviewOutcome.CONTINUE_WITH_MODIFICATIONS,
                "recommendations": ["Continue enrollment", "Add injection site monitoring to CRF", "Increase follow-up frequency for patients with prior reactions"],
                "action_items": ["Update CRF for injection site monitoring", "Amend informed consent to reflect new monitoring"],
                "next_meeting_date": now + timedelta(days=78),
                "created_at": now - timedelta(days=7),
            },
            {
                "id": "DSMB-MTG-005",
                "trial_id": DUPIXENT_TRIAL,
                "meeting_type": MeetingType.AD_HOC,
                "meeting_date": now - timedelta(days=15),
                "attendees": ["DSMB-MEM-001", "DSMB-MEM-002", "DSMB-MEM-004"],
                "agenda": ["Review cluster of SAEs at single site", "Site audit recommendation"],
                "minutes_summary": "Reviewed 3 SAEs reported within 2 weeks at Site 205. Determined events are consistent with underlying disease severity at that site. No causal relationship to study drug established. Recommended enhanced monitoring.",
                "outcome": ReviewOutcome.CONTINUE_WITH_MODIFICATIONS,
                "recommendations": ["Enhanced monitoring at Site 205", "Triggered site audit", "No enrollment suspension needed"],
                "action_items": ["Initiate site audit at Site 205 within 2 weeks", "Implement enhanced AE reporting at Site 205"],
                "next_meeting_date": None,
                "created_at": now - timedelta(days=16),
            },
            {
                "id": "DSMB-MTG-006",
                "trial_id": LIBTAYO_TRIAL,
                "meeting_type": MeetingType.EMERGENCY,
                "meeting_date": now - timedelta(days=5),
                "attendees": ["DSMB-MEM-001", "DSMB-MEM-002", "DSMB-MEM-007", "DSMB-MEM-005"],
                "agenda": ["Urgent review: unexpected fatal SAE", "Causality assessment", "Enrollment suspension consideration"],
                "minutes_summary": "Reviewed fatal SAE in LIBTAYO trial patient. Event was Grade 5 pneumonitis. After thorough review, determined event is possibly related to study drug. Requested additional data from site and pathology review before making enrollment decision.",
                "outcome": ReviewOutcome.REQUEST_ADDITIONAL_DATA,
                "recommendations": ["Obtain complete pathology report", "Review all pneumonitis events across trial", "Reconvene within 7 days"],
                "action_items": ["Sponsor to obtain pathology report within 48 hours", "Biostatistician to run updated safety analysis for pneumonitis", "Schedule follow-up emergency meeting"],
                "next_meeting_date": now + timedelta(days=2),
                "created_at": now - timedelta(days=5),
            },
        ]

        for mtg in meetings_data:
            self._meetings[mtg["id"]] = DSMBMeeting(**mtg)

        # --- 3 Interim Analyses ---
        analyses_data = [
            {
                "id": "DSMB-IA-001",
                "trial_id": LIBTAYO_TRIAL,
                "analysis_type": InterimAnalysisType.COMBINED,
                "analysis_date": now - timedelta(days=32),
                "planned_sample_size": 450,
                "actual_sample_size": 150,
                "information_fraction": 0.333,
                "stopping_rules_evaluated": [
                    StoppingBoundary(
                        rule_type=StoppingRule.EFFICACY_BOUNDARY,
                        boundary_value=3.471,
                        alpha_spent=0.0005,
                        information_fraction=0.333,
                        crossed=False,
                        method="OBF",
                    ),
                    StoppingBoundary(
                        rule_type=StoppingRule.FUTILITY_BOUNDARY,
                        boundary_value=-0.5,
                        alpha_spent=0.0,
                        information_fraction=0.333,
                        crossed=False,
                        method="OBF",
                    ),
                    StoppingBoundary(
                        rule_type=StoppingRule.SAFETY_BOUNDARY,
                        boundary_value=2.576,
                        alpha_spent=0.005,
                        information_fraction=0.333,
                        crossed=False,
                        method="OBF",
                    ),
                ],
                "boundaries_crossed": [],
                "recommendation": ReviewOutcome.CONTINUE_UNCHANGED,
                "report_access_level": ReportAccessLevel.UNBLINDED,
                "performed_by": "Dr. Robert Kline",
                "reviewed_at": now - timedelta(days=30),
                "created_at": now - timedelta(days=33),
            },
            {
                "id": "DSMB-IA-002",
                "trial_id": EYLEA_TRIAL,
                "analysis_type": InterimAnalysisType.SAFETY_ONLY,
                "analysis_date": now - timedelta(days=10),
                "planned_sample_size": 300,
                "actual_sample_size": 180,
                "information_fraction": 0.6,
                "stopping_rules_evaluated": [
                    StoppingBoundary(
                        rule_type=StoppingRule.SAFETY_BOUNDARY,
                        boundary_value=2.289,
                        alpha_spent=0.011,
                        information_fraction=0.6,
                        crossed=False,
                        method="Lan-DeMets",
                    ),
                    StoppingBoundary(
                        rule_type=StoppingRule.HARM_BOUNDARY,
                        boundary_value=2.576,
                        alpha_spent=0.005,
                        information_fraction=0.6,
                        crossed=False,
                        method="Lan-DeMets",
                    ),
                ],
                "boundaries_crossed": [],
                "recommendation": ReviewOutcome.CONTINUE_UNCHANGED,
                "report_access_level": ReportAccessLevel.BLINDED,
                "performed_by": "Dr. Emily Watson",
                "reviewed_at": now - timedelta(days=6),
                "created_at": now - timedelta(days=11),
            },
            {
                "id": "DSMB-IA-003",
                "trial_id": DUPIXENT_TRIAL,
                "analysis_type": InterimAnalysisType.EFFICACY_FUTILITY,
                "analysis_date": now - timedelta(days=62),
                "planned_sample_size": 500,
                "actual_sample_size": 200,
                "information_fraction": 0.4,
                "stopping_rules_evaluated": [
                    StoppingBoundary(
                        rule_type=StoppingRule.EFFICACY_BOUNDARY,
                        boundary_value=2.963,
                        alpha_spent=0.003,
                        information_fraction=0.4,
                        crossed=False,
                        method="Pocock",
                    ),
                    StoppingBoundary(
                        rule_type=StoppingRule.FUTILITY_BOUNDARY,
                        boundary_value=0.0,
                        alpha_spent=0.0,
                        information_fraction=0.4,
                        crossed=False,
                        method="Pocock",
                    ),
                ],
                "boundaries_crossed": [],
                "recommendation": ReviewOutcome.CONTINUE_UNCHANGED,
                "report_access_level": ReportAccessLevel.UNBLINDED,
                "performed_by": "Dr. Robert Kline",
                "reviewed_at": now - timedelta(days=60),
                "created_at": now - timedelta(days=63),
            },
        ]

        for ia in analyses_data:
            self._interim_analyses[ia["id"]] = InterimAnalysis(**ia)

        # --- 10 Event Adjudications ---
        adjudications_data = [
            {
                "id": "DSMB-ADJ-001",
                "trial_id": EYLEA_TRIAL,
                "patient_id": "PAT-DME-003",
                "event_type": "Retinal detachment",
                "event_date": now - timedelta(days=80),
                "submitted_by": "Dr. Sarah Chen",
                "adjudicator": "DSMB-MEM-003",
                "status": EventAdjudicationStatus.ADJUDICATED,
                "original_classification": "Serious Adverse Event",
                "adjudicated_classification": "Serious Adverse Event - Not Related",
                "rationale": "Retinal detachment occurred in fellow eye not receiving treatment. Pre-existing condition documented.",
                "adjudicated_at": now - timedelta(days=70),
                "created_at": now - timedelta(days=81),
            },
            {
                "id": "DSMB-ADJ-002",
                "trial_id": EYLEA_TRIAL,
                "patient_id": "PAT-DME-007",
                "event_type": "Endophthalmitis",
                "event_date": now - timedelta(days=50),
                "submitted_by": "Dr. Michael Park",
                "adjudicator": "DSMB-MEM-003",
                "status": EventAdjudicationStatus.ADJUDICATED,
                "original_classification": "Serious Adverse Event",
                "adjudicated_classification": "Serious Adverse Event - Possibly Related",
                "rationale": "Post-injection endophthalmitis is a known risk of intravitreal injection procedure.",
                "adjudicated_at": now - timedelta(days=40),
                "created_at": now - timedelta(days=51),
            },
            {
                "id": "DSMB-ADJ-003",
                "trial_id": DUPIXENT_TRIAL,
                "patient_id": "PAT-AD-012",
                "event_type": "Anaphylaxis",
                "event_date": now - timedelta(days=45),
                "submitted_by": "Dr. Amanda Rhodes",
                "adjudicator": "DSMB-MEM-004",
                "status": EventAdjudicationStatus.ADJUDICATED,
                "original_classification": "Serious Adverse Event",
                "adjudicated_classification": "Serious Adverse Event - Probably Related",
                "rationale": "Occurred within 30 minutes of dupilumab injection. No other concurrent medications. Resolved with epinephrine.",
                "adjudicated_at": now - timedelta(days=38),
                "created_at": now - timedelta(days=46),
            },
            {
                "id": "DSMB-ADJ-004",
                "trial_id": DUPIXENT_TRIAL,
                "patient_id": "PAT-AD-015",
                "event_type": "Conjunctivitis",
                "event_date": now - timedelta(days=35),
                "submitted_by": "Dr. Amanda Rhodes",
                "adjudicator": "DSMB-MEM-004",
                "status": EventAdjudicationStatus.ADJUDICATED,
                "original_classification": "Adverse Event",
                "adjudicated_classification": "Adverse Event - Related",
                "rationale": "Conjunctivitis is a known class effect of anti-IL-4R antibodies. Consistent with published literature.",
                "adjudicated_at": now - timedelta(days=28),
                "created_at": now - timedelta(days=36),
            },
            {
                "id": "DSMB-ADJ-005",
                "trial_id": LIBTAYO_TRIAL,
                "patient_id": "PAT-CSCC-001",
                "event_type": "Pneumonitis",
                "event_date": now - timedelta(days=8),
                "submitted_by": "Dr. Thomas Wright",
                "adjudicator": "DSMB-MEM-007",
                "status": EventAdjudicationStatus.UNDER_REVIEW,
                "original_classification": "Serious Adverse Event - Fatal",
                "adjudicated_classification": None,
                "rationale": None,
                "adjudicated_at": None,
                "created_at": now - timedelta(days=7),
            },
            {
                "id": "DSMB-ADJ-006",
                "trial_id": LIBTAYO_TRIAL,
                "patient_id": "PAT-CSCC-005",
                "event_type": "Immune-mediated hepatitis",
                "event_date": now - timedelta(days=20),
                "submitted_by": "Dr. Thomas Wright",
                "adjudicator": "DSMB-MEM-007",
                "status": EventAdjudicationStatus.ADJUDICATED,
                "original_classification": "Serious Adverse Event",
                "adjudicated_classification": "Serious Adverse Event - Related",
                "rationale": "Grade 3 hepatitis with ALT >10x ULN. Consistent with immune-mediated mechanism of checkpoint inhibitors.",
                "adjudicated_at": now - timedelta(days=12),
                "created_at": now - timedelta(days=21),
            },
            {
                "id": "DSMB-ADJ-007",
                "trial_id": EYLEA_TRIAL,
                "patient_id": "PAT-DME-010",
                "event_type": "Myocardial infarction",
                "event_date": now - timedelta(days=25),
                "submitted_by": "Dr. Sarah Chen",
                "adjudicator": None,
                "status": EventAdjudicationStatus.PENDING,
                "original_classification": "Serious Adverse Event",
                "adjudicated_classification": None,
                "rationale": None,
                "adjudicated_at": None,
                "created_at": now - timedelta(days=24),
            },
            {
                "id": "DSMB-ADJ-008",
                "trial_id": DUPIXENT_TRIAL,
                "patient_id": "PAT-AD-020",
                "event_type": "Eczema herpeticum",
                "event_date": now - timedelta(days=12),
                "submitted_by": "Dr. Amanda Rhodes",
                "adjudicator": None,
                "status": EventAdjudicationStatus.PENDING,
                "original_classification": "Serious Adverse Event",
                "adjudicated_classification": None,
                "rationale": None,
                "adjudicated_at": None,
                "created_at": now - timedelta(days=11),
            },
            {
                "id": "DSMB-ADJ-009",
                "trial_id": LIBTAYO_TRIAL,
                "patient_id": "PAT-CSCC-008",
                "event_type": "Immune-mediated colitis",
                "event_date": now - timedelta(days=18),
                "submitted_by": "Dr. Thomas Wright",
                "adjudicator": "DSMB-MEM-007",
                "status": EventAdjudicationStatus.APPEALED,
                "original_classification": "Adverse Event",
                "adjudicated_classification": "Adverse Event - Not Related",
                "rationale": "Initial adjudication: colitis preceded study drug start by 3 days. Site appealing based on new endoscopy data.",
                "adjudicated_at": now - timedelta(days=10),
                "created_at": now - timedelta(days=19),
            },
            {
                "id": "DSMB-ADJ-010",
                "trial_id": EYLEA_TRIAL,
                "patient_id": "PAT-DME-015",
                "event_type": "Cerebrovascular accident",
                "event_date": now - timedelta(days=55),
                "submitted_by": "Dr. Michael Park",
                "adjudicator": "DSMB-MEM-003",
                "status": EventAdjudicationStatus.ADJUDICATED,
                "original_classification": "Serious Adverse Event",
                "adjudicated_classification": "Serious Adverse Event - Unlikely Related",
                "rationale": "Patient had multiple pre-existing cardiovascular risk factors. Temporal relationship not suggestive of causal association.",
                "adjudicated_at": now - timedelta(days=42),
                "created_at": now - timedelta(days=54),
            },
        ]

        for adj in adjudications_data:
            self._adjudications[adj["id"]] = EventAdjudication(**adj)

        # --- 4 Safety Reports ---
        reports_data = [
            {
                "id": "DSMB-RPT-001",
                "trial_id": EYLEA_TRIAL,
                "report_date": now - timedelta(days=90),
                "report_type": "periodic",
                "total_enrolled": 120,
                "total_events": 28,
                "serious_events": 4,
                "fatal_events": 0,
                "event_rates_by_arm": {"treatment": 0.15, "control": 0.08, "pooled": 0.12},
                "safety_signals": [],
                "generated_by": "Clinical Data Management",
                "access_level": ReportAccessLevel.BLINDED,
            },
            {
                "id": "DSMB-RPT-002",
                "trial_id": EYLEA_TRIAL,
                "report_date": now - timedelta(days=7),
                "report_type": "periodic",
                "total_enrolled": 180,
                "total_events": 42,
                "serious_events": 7,
                "fatal_events": 0,
                "event_rates_by_arm": {"treatment": 0.16, "control": 0.09, "pooled": 0.13},
                "safety_signals": ["Injection site reaction rate trending above expected"],
                "generated_by": "Clinical Data Management",
                "access_level": ReportAccessLevel.UNBLINDED,
            },
            {
                "id": "DSMB-RPT-003",
                "trial_id": DUPIXENT_TRIAL,
                "report_date": now - timedelta(days=60),
                "report_type": "periodic",
                "total_enrolled": 200,
                "total_events": 35,
                "serious_events": 5,
                "fatal_events": 0,
                "event_rates_by_arm": {"treatment": 0.12, "control": 0.07, "pooled": 0.10},
                "safety_signals": [],
                "generated_by": "Clinical Data Management",
                "access_level": ReportAccessLevel.UNBLINDED,
            },
            {
                "id": "DSMB-RPT-004",
                "trial_id": LIBTAYO_TRIAL,
                "report_date": now - timedelta(days=5),
                "report_type": "ad-hoc",
                "total_enrolled": 150,
                "total_events": 22,
                "serious_events": 6,
                "fatal_events": 1,
                "event_rates_by_arm": {"treatment": 0.18, "control": 0.05, "pooled": 0.12},
                "safety_signals": ["Fatal pneumonitis under investigation", "Immune-mediated hepatitis signal"],
                "generated_by": "Safety Monitoring Team",
                "access_level": ReportAccessLevel.UNBLINDED,
            },
        ]

        for rpt in reports_data:
            self._safety_reports[rpt["id"]] = SafetyReport(**rpt)

        # --- 2 DSMB Charters ---
        charters_data = [
            {
                "id": "DSMB-CHR-001",
                "trial_id": EYLEA_TRIAL,
                "version": "2.0",
                "approved_date": now - timedelta(days=350),
                "review_frequency_weeks": 12,
                "stopping_rules": [
                    "O'Brien-Fleming efficacy boundary at 3 planned interim analyses",
                    "Safety stopping for >2x excess mortality in treatment arm",
                    "Futility stopping if conditional power <10% at 50% information",
                ],
                "reporting_requirements": [
                    "Blinded safety report every 12 weeks",
                    "Unblinded report at each interim analysis",
                    "Ad-hoc reports for SAE clusters",
                ],
                "access_policies": [
                    "Unblinded data accessible only to DSMB statistician and chair",
                    "Sponsor receives blinded summary only",
                    "Full unblinded report stored in secure DSMB repository",
                ],
                "approved_by": ["DSMB-MEM-001", "DSMB-MEM-002", "DSMB-MEM-003", "DSMB-MEM-005"],
            },
            {
                "id": "DSMB-CHR-002",
                "trial_id": LIBTAYO_TRIAL,
                "version": "1.0",
                "approved_date": now - timedelta(days=365),
                "review_frequency_weeks": 8,
                "stopping_rules": [
                    "Lan-DeMets alpha spending with O'Brien-Fleming approximation",
                    "Harm boundary: immediate suspension if treatment mortality >3x control",
                    "Futility: conditional power <5% at any look",
                ],
                "reporting_requirements": [
                    "Blinded safety report every 8 weeks",
                    "Unblinded interim analysis reports",
                    "IND Safety Reports within 24 hours of DSMB recommendation",
                ],
                "access_policies": [
                    "Firewall between DSMB and sponsor for unblinded data",
                    "Independent statistician prepares all unblinded reports",
                    "DSMB recommendations communicated to sponsor within 48 hours",
                ],
                "approved_by": ["DSMB-MEM-001", "DSMB-MEM-002", "DSMB-MEM-007", "DSMB-MEM-005"],
            },
        ]

        for ch in charters_data:
            self._charters[ch["id"]] = DSMBCharter(**ch)

    # ------------------------------------------------------------------
    # Member management
    # ------------------------------------------------------------------

    def list_members(
        self,
        *,
        role: DSMBRole | None = None,
        active: bool | None = None,
    ) -> list[DSMBMember]:
        """List DSMB members with optional filters."""
        with self._lock:
            result = list(self._members.values())

        if role is not None:
            result = [m for m in result if m.role == role]
        if active is not None:
            result = [m for m in result if m.active == active]

        return sorted(result, key=lambda m: m.name)

    def get_member(self, member_id: str) -> DSMBMember | None:
        """Get a single member by ID."""
        with self._lock:
            return self._members.get(member_id)

    def create_member(self, payload: DSMBMemberCreate) -> DSMBMember:
        """Create a new DSMB member."""
        member_id = f"DSMB-MEM-{uuid4().hex[:8].upper()}"
        member = DSMBMember(
            id=member_id,
            **payload.model_dump(),
        )
        with self._lock:
            self._members[member_id] = member
        logger.info("Created DSMB member %s: %s", member_id, payload.name)
        return member

    def update_member(self, member_id: str, payload: DSMBMemberUpdate) -> DSMBMember | None:
        """Update an existing DSMB member."""
        with self._lock:
            existing = self._members.get(member_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DSMBMember(**data)
            self._members[member_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Meeting management
    # ------------------------------------------------------------------

    def list_meetings(
        self,
        *,
        trial_id: str | None = None,
        meeting_type: MeetingType | None = None,
    ) -> list[DSMBMeeting]:
        """List DSMB meetings with optional filters."""
        with self._lock:
            result = list(self._meetings.values())

        if trial_id is not None:
            result = [m for m in result if m.trial_id == trial_id]
        if meeting_type is not None:
            result = [m for m in result if m.meeting_type == meeting_type]

        return sorted(result, key=lambda m: m.meeting_date, reverse=True)

    def get_meeting(self, meeting_id: str) -> DSMBMeeting | None:
        """Get a single meeting by ID."""
        with self._lock:
            return self._meetings.get(meeting_id)

    def create_meeting(self, payload: DSMBMeetingCreate) -> DSMBMeeting:
        """Schedule a new DSMB meeting."""
        now = datetime.now(timezone.utc)
        meeting_id = f"DSMB-MTG-{uuid4().hex[:8].upper()}"
        meeting = DSMBMeeting(
            id=meeting_id,
            trial_id=payload.trial_id,
            meeting_type=payload.meeting_type,
            meeting_date=payload.meeting_date,
            attendees=payload.attendees,
            agenda=payload.agenda,
            created_at=now,
        )
        with self._lock:
            self._meetings[meeting_id] = meeting
        logger.info("Scheduled DSMB meeting %s for trial %s", meeting_id, payload.trial_id)
        return meeting

    def update_meeting(self, meeting_id: str, payload: DSMBMeetingUpdate) -> DSMBMeeting | None:
        """Update meeting details (add minutes, outcome, etc.)."""
        with self._lock:
            existing = self._meetings.get(meeting_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DSMBMeeting(**data)
            self._meetings[meeting_id] = updated
        return updated

    def get_upcoming_meetings(self, days: int = 30) -> list[DSMBMeeting]:
        """Get meetings scheduled within the next N days."""
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=days)
        with self._lock:
            result = [
                m for m in self._meetings.values()
                if m.meeting_date > now and m.meeting_date <= cutoff
            ]
        return sorted(result, key=lambda m: m.meeting_date)

    # ------------------------------------------------------------------
    # Interim analysis
    # ------------------------------------------------------------------

    def list_interim_analyses(
        self,
        *,
        trial_id: str | None = None,
        analysis_type: InterimAnalysisType | None = None,
    ) -> list[InterimAnalysis]:
        """List interim analyses with optional filters."""
        with self._lock:
            result = list(self._interim_analyses.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if analysis_type is not None:
            result = [a for a in result if a.analysis_type == analysis_type]

        return sorted(result, key=lambda a: a.analysis_date, reverse=True)

    def get_interim_analysis(self, analysis_id: str) -> InterimAnalysis | None:
        """Get a single interim analysis by ID."""
        with self._lock:
            return self._interim_analyses.get(analysis_id)

    def create_interim_analysis(self, payload: InterimAnalysisCreate) -> InterimAnalysis:
        """Create a new interim analysis with stopping rule evaluation.

        Evaluates stopping boundaries using the specified method:
        - OBF (O'Brien-Fleming): Conservative early, liberal late
        - Pocock: Equal alpha spending at each look
        - Lan-DeMets: Alpha spending function approach
        """
        now = datetime.now(timezone.utc)
        analysis_id = f"DSMB-IA-{uuid4().hex[:8].upper()}"

        info_fraction = payload.actual_sample_size / payload.planned_sample_size
        info_fraction = min(info_fraction, 1.0)

        # Evaluate stopping boundaries
        boundaries = self._evaluate_stopping_rules(
            method=payload.method,
            overall_alpha=payload.overall_alpha,
            information_fraction=info_fraction,
            number_of_looks=payload.number_of_looks,
            current_look=payload.current_look,
            analysis_type=payload.analysis_type,
        )

        crossed = [b.rule_type.value for b in boundaries if b.crossed]

        # Determine recommendation based on boundaries crossed
        recommendation = self._determine_recommendation(crossed, boundaries)

        analysis = InterimAnalysis(
            id=analysis_id,
            trial_id=payload.trial_id,
            analysis_type=payload.analysis_type,
            analysis_date=now,
            planned_sample_size=payload.planned_sample_size,
            actual_sample_size=payload.actual_sample_size,
            information_fraction=round(info_fraction, 4),
            stopping_rules_evaluated=boundaries,
            boundaries_crossed=crossed,
            recommendation=recommendation,
            report_access_level=ReportAccessLevel.UNBLINDED,
            performed_by=payload.performed_by,
            reviewed_at=None,
            created_at=now,
        )

        with self._lock:
            self._interim_analyses[analysis_id] = analysis
        logger.info(
            "Created interim analysis %s for trial %s (IF=%.3f, method=%s)",
            analysis_id, payload.trial_id, info_fraction, payload.method,
        )
        return analysis

    def _evaluate_stopping_rules(
        self,
        *,
        method: str,
        overall_alpha: float,
        information_fraction: float,
        number_of_looks: int,
        current_look: int,
        analysis_type: InterimAnalysisType,
    ) -> list[StoppingBoundary]:
        """Evaluate stopping boundaries using group-sequential methods."""
        boundaries: list[StoppingBoundary] = []

        if analysis_type in (
            InterimAnalysisType.COMBINED,
            InterimAnalysisType.EFFICACY_FUTILITY,
        ):
            # Efficacy boundary
            eff_boundary, eff_alpha = self._compute_boundary(
                method=method,
                overall_alpha=overall_alpha,
                information_fraction=information_fraction,
                number_of_looks=number_of_looks,
                current_look=current_look,
                boundary_type="efficacy",
            )
            boundaries.append(
                StoppingBoundary(
                    rule_type=StoppingRule.EFFICACY_BOUNDARY,
                    boundary_value=round(eff_boundary, 4),
                    alpha_spent=round(eff_alpha, 6),
                    information_fraction=round(information_fraction, 4),
                    crossed=False,  # Would need actual test statistic to determine
                    method=method,
                )
            )

            # Futility boundary
            fut_boundary = self._compute_futility_boundary(
                information_fraction=information_fraction,
                method=method,
            )
            boundaries.append(
                StoppingBoundary(
                    rule_type=StoppingRule.FUTILITY_BOUNDARY,
                    boundary_value=round(fut_boundary, 4),
                    alpha_spent=0.0,
                    information_fraction=round(information_fraction, 4),
                    crossed=False,
                    method=method,
                )
            )

        if analysis_type in (
            InterimAnalysisType.COMBINED,
            InterimAnalysisType.SAFETY_ONLY,
        ):
            # Safety boundary
            safety_boundary, safety_alpha = self._compute_boundary(
                method=method,
                overall_alpha=overall_alpha,
                information_fraction=information_fraction,
                number_of_looks=number_of_looks,
                current_look=current_look,
                boundary_type="safety",
            )
            boundaries.append(
                StoppingBoundary(
                    rule_type=StoppingRule.SAFETY_BOUNDARY,
                    boundary_value=round(safety_boundary, 4),
                    alpha_spent=round(safety_alpha, 6),
                    information_fraction=round(information_fraction, 4),
                    crossed=False,
                    method=method,
                )
            )

        return boundaries

    def _compute_boundary(
        self,
        *,
        method: str,
        overall_alpha: float,
        information_fraction: float,
        number_of_looks: int,
        current_look: int,
        boundary_type: str,
    ) -> tuple[float, float]:
        """Compute critical boundary value and cumulative alpha spent.

        Returns (boundary_value, alpha_spent).
        """
        t = information_fraction

        if method == "OBF" or method == "O'Brien-Fleming":
            # O'Brien-Fleming: boundary = C / sqrt(t)
            # Alpha spending: alpha * (2 - 2*Phi(z_alpha/2 / sqrt(t)))
            # Simplified: very conservative early, liberal late
            if t <= 0:
                return (8.0, 0.0)
            base_z = 1.96  # z for alpha=0.05
            boundary = base_z / math.sqrt(t)
            # Approximate alpha spending
            alpha_spent = overall_alpha * 2.0 * (1.0 - self._phi(base_z / math.sqrt(t)))
            alpha_spent = min(alpha_spent, overall_alpha)
            return (boundary, alpha_spent)

        elif method == "Pocock":
            # Pocock: constant boundary at each look
            # boundary = adjusted critical value
            # Equal alpha spending at each look
            alpha_per_look = overall_alpha / number_of_looks
            alpha_spent = alpha_per_look * current_look
            alpha_spent = min(alpha_spent, overall_alpha)
            # Pocock boundary is approximately constant
            boundary = self._z_from_alpha(alpha_per_look)
            return (boundary, alpha_spent)

        else:  # Lan-DeMets (default)
            # Lan-DeMets alpha spending with OBF-type spending function
            # alpha*(t) = 2 - 2*Phi(z_alpha/2 / sqrt(t))
            if t <= 0:
                return (8.0, 0.0)
            z_half = self._z_from_alpha(overall_alpha / 2.0)
            alpha_spent = 2.0 * (1.0 - self._phi(z_half / math.sqrt(t)))
            alpha_spent = min(alpha_spent, overall_alpha)
            # Incremental alpha at this look
            boundary = self._z_from_alpha(max(alpha_spent / 2.0, 1e-12))
            return (boundary, alpha_spent)

    def _compute_futility_boundary(
        self,
        *,
        information_fraction: float,
        method: str,
    ) -> float:
        """Compute futility boundary (beta spending)."""
        if method == "OBF" or method == "O'Brien-Fleming":
            # OBF futility: starts very negative, approaches 0
            if information_fraction <= 0:
                return -8.0
            return -1.0 * (1.0 - information_fraction) / math.sqrt(information_fraction)
        elif method == "Pocock":
            # Pocock futility: constant
            return 0.0
        else:
            # Lan-DeMets: similar to OBF
            if information_fraction <= 0:
                return -8.0
            return -0.5 * (1.0 - information_fraction) / math.sqrt(max(information_fraction, 0.01))

    @staticmethod
    def _phi(z: float) -> float:
        """Standard normal CDF (approximation)."""
        return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))

    @staticmethod
    def _z_from_alpha(alpha: float) -> float:
        """Inverse normal (approximate z-score for a given alpha)."""
        if alpha <= 0:
            return 8.0
        if alpha >= 1:
            return 0.0
        # Rational approximation for probit function
        p = alpha
        if p > 0.5:
            p = 1.0 - p
        t = math.sqrt(-2.0 * math.log(p))
        # Abramowitz and Stegun approximation 26.2.23
        c0, c1, c2 = 2.515517, 0.802853, 0.010328
        d1, d2, d3 = 1.432788, 0.189269, 0.001308
        z = t - (c0 + c1 * t + c2 * t * t) / (1.0 + d1 * t + d2 * t * t + d3 * t * t * t)
        if alpha > 0.5:
            z = -z
        return z

    @staticmethod
    def _determine_recommendation(
        crossed: list[str],
        boundaries: list[StoppingBoundary],
    ) -> ReviewOutcome:
        """Determine recommendation based on which boundaries were crossed."""
        if not crossed:
            return ReviewOutcome.CONTINUE_UNCHANGED

        crossed_set = set(crossed)

        if StoppingRule.HARM_BOUNDARY.value in crossed_set:
            return ReviewOutcome.TERMINATE_EARLY
        if StoppingRule.SAFETY_BOUNDARY.value in crossed_set:
            return ReviewOutcome.SUSPEND_ENROLLMENT
        if StoppingRule.EFFICACY_BOUNDARY.value in crossed_set:
            return ReviewOutcome.TERMINATE_EARLY  # Efficacy demonstrated
        if StoppingRule.FUTILITY_BOUNDARY.value in crossed_set:
            return ReviewOutcome.TERMINATE_EARLY  # Futile to continue

        return ReviewOutcome.CONTINUE_WITH_MODIFICATIONS

    # ------------------------------------------------------------------
    # Event adjudication
    # ------------------------------------------------------------------

    def list_adjudications(
        self,
        *,
        trial_id: str | None = None,
        status: EventAdjudicationStatus | None = None,
        patient_id: str | None = None,
    ) -> list[EventAdjudication]:
        """List event adjudications with optional filters."""
        with self._lock:
            result = list(self._adjudications.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if status is not None:
            result = [a for a in result if a.status == status]
        if patient_id is not None:
            result = [a for a in result if a.patient_id == patient_id]

        return sorted(result, key=lambda a: a.created_at, reverse=True)

    def get_adjudication(self, adjudication_id: str) -> EventAdjudication | None:
        """Get a single adjudication by ID."""
        with self._lock:
            return self._adjudications.get(adjudication_id)

    def create_adjudication(self, payload: EventAdjudicationCreate) -> EventAdjudication:
        """Submit a new event for adjudication."""
        now = datetime.now(timezone.utc)
        adj_id = f"DSMB-ADJ-{uuid4().hex[:8].upper()}"
        adj = EventAdjudication(
            id=adj_id,
            trial_id=payload.trial_id,
            patient_id=payload.patient_id,
            event_type=payload.event_type,
            event_date=payload.event_date,
            submitted_by=payload.submitted_by,
            original_classification=payload.original_classification,
            created_at=now,
        )
        with self._lock:
            self._adjudications[adj_id] = adj
        logger.info("Created adjudication %s for event %s", adj_id, payload.event_type)
        return adj

    def update_adjudication(
        self,
        adjudication_id: str,
        payload: EventAdjudicationUpdate,
    ) -> EventAdjudication | None:
        """Update an adjudication (assign, adjudicate, or appeal).

        Enforces valid status transitions.
        Returns None if adjudication not found.
        Raises ValueError for invalid status transitions.
        """
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._adjudications.get(adjudication_id)
            if existing is None:
                return None

            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Validate status transition
            if "status" in updates and updates["status"] is not None:
                new_status = updates["status"]
                if isinstance(new_status, str):
                    new_status = EventAdjudicationStatus(new_status)
                current_status = existing.status
                valid_next = VALID_ADJUDICATION_TRANSITIONS.get(current_status, set())
                if new_status not in valid_next:
                    raise ValueError(
                        f"Invalid status transition: {current_status.value} -> {new_status.value}. "
                        f"Valid transitions: {[s.value for s in valid_next]}"
                    )

                # Auto-set adjudicated_at when transitioning to ADJUDICATED
                if new_status == EventAdjudicationStatus.ADJUDICATED:
                    updates["adjudicated_at"] = now

            data.update(updates)
            updated = EventAdjudication(**data)
            self._adjudications[adjudication_id] = updated
        return updated

    def get_overdue_adjudications(self) -> list[EventAdjudication]:
        """Get adjudications that have been PENDING for more than 30 days."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=OVERDUE_ADJUDICATION_DAYS)
        with self._lock:
            result = [
                a for a in self._adjudications.values()
                if a.status == EventAdjudicationStatus.PENDING and a.created_at < cutoff
            ]
        return sorted(result, key=lambda a: a.created_at)

    # ------------------------------------------------------------------
    # Safety reports
    # ------------------------------------------------------------------

    def list_safety_reports(
        self,
        *,
        trial_id: str | None = None,
        access_level: ReportAccessLevel | None = None,
    ) -> list[SafetyReport]:
        """List safety reports with optional filters."""
        with self._lock:
            result = list(self._safety_reports.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if access_level is not None:
            result = [r for r in result if r.access_level == access_level]

        return sorted(result, key=lambda r: r.report_date, reverse=True)

    def get_safety_report(self, report_id: str) -> SafetyReport | None:
        """Get a single safety report by ID."""
        with self._lock:
            return self._safety_reports.get(report_id)

    def generate_safety_report(self, payload: SafetyReportCreate) -> SafetyReport:
        """Generate a new safety report for a trial.

        Aggregates event data from adjudications and produces blinded or
        unblinded views depending on the requested access level.
        """
        now = datetime.now(timezone.utc)
        report_id = f"DSMB-RPT-{uuid4().hex[:8].upper()}"

        # Aggregate data from adjudications for this trial
        with self._lock:
            trial_adjs = [
                a for a in self._adjudications.values()
                if a.trial_id == payload.trial_id
            ]

        total_events = len(trial_adjs)
        serious_events = sum(
            1 for a in trial_adjs
            if "serious" in a.original_classification.lower()
        )
        fatal_events = sum(
            1 for a in trial_adjs
            if "fatal" in a.original_classification.lower()
        )

        # Build event rates - blinded vs unblinded
        if payload.access_level == ReportAccessLevel.BLINDED:
            event_rates = {"pooled": round(total_events / max(1, total_events * 5), 4)}
        elif payload.access_level == ReportAccessLevel.SUMMARY_ONLY:
            event_rates = {}
        else:
            event_rates = {
                "treatment": round(total_events * 0.6 / max(1, total_events * 3), 4),
                "control": round(total_events * 0.4 / max(1, total_events * 3), 4),
                "pooled": round(total_events / max(1, total_events * 5), 4),
            }

        # Identify safety signals
        safety_signals: list[str] = []
        event_type_counts = Counter(a.event_type for a in trial_adjs)
        for event_type, count in event_type_counts.most_common(5):
            if count >= 2:
                safety_signals.append(f"{event_type}: {count} events reported")

        # Estimated enrollment (rough heuristic)
        total_enrolled = total_events * 5  # assume ~20% event rate

        report = SafetyReport(
            id=report_id,
            trial_id=payload.trial_id,
            report_date=now,
            report_type=payload.report_type,
            total_enrolled=total_enrolled,
            total_events=total_events,
            serious_events=serious_events,
            fatal_events=fatal_events,
            event_rates_by_arm=event_rates,
            safety_signals=safety_signals,
            generated_by=payload.generated_by,
            access_level=payload.access_level,
        )

        with self._lock:
            self._safety_reports[report_id] = report
        logger.info(
            "Generated safety report %s for trial %s (access=%s)",
            report_id, payload.trial_id, payload.access_level.value,
        )
        return report

    # ------------------------------------------------------------------
    # Charter management
    # ------------------------------------------------------------------

    def list_charters(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[DSMBCharter]:
        """List DSMB charters with optional filters."""
        with self._lock:
            result = list(self._charters.values())

        if trial_id is not None:
            result = [c for c in result if c.trial_id == trial_id]

        return sorted(result, key=lambda c: c.approved_date, reverse=True)

    def get_charter(self, charter_id: str) -> DSMBCharter | None:
        """Get a single charter by ID."""
        with self._lock:
            return self._charters.get(charter_id)

    def create_charter(self, payload: DSMBCharterCreate) -> DSMBCharter:
        """Create a new DSMB charter."""
        now = datetime.now(timezone.utc)
        charter_id = f"DSMB-CHR-{uuid4().hex[:8].upper()}"
        charter = DSMBCharter(
            id=charter_id,
            trial_id=payload.trial_id,
            version=payload.version,
            approved_date=now,
            review_frequency_weeks=payload.review_frequency_weeks,
            stopping_rules=payload.stopping_rules,
            reporting_requirements=payload.reporting_requirements,
            access_policies=payload.access_policies,
            approved_by=payload.approved_by,
        )
        with self._lock:
            self._charters[charter_id] = charter
        logger.info("Created DSMB charter %s for trial %s", charter_id, payload.trial_id)
        return charter

    def update_charter(self, charter_id: str, payload: DSMBCharterUpdate) -> DSMBCharter | None:
        """Update an existing DSMB charter."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._charters.get(charter_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            # Update approved_date on version change
            if "version" in updates:
                data["approved_date"] = now
            updated = DSMBCharter(**data)
            self._charters[charter_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Metrics & dashboard
    # ------------------------------------------------------------------

    def get_metrics(self) -> DSMBMetrics:
        """Compute aggregated DSMB operational metrics."""
        now = datetime.now(timezone.utc)
        cutoff_30d = now + timedelta(days=30)
        overdue_cutoff = now - timedelta(days=OVERDUE_ADJUDICATION_DAYS)

        with self._lock:
            members = list(self._members.values())
            meetings = list(self._meetings.values())
            analyses = list(self._interim_analyses.values())
            adjs = list(self._adjudications.values())
            reports = list(self._safety_reports.values())
            charters = list(self._charters.values())

        # Members
        total_members = len(members)
        active_members = sum(1 for m in members if m.active)

        # Meetings
        total_meetings = len(meetings)
        meetings_by_type: dict[str, int] = {}
        for mtg in meetings:
            key = mtg.meeting_type.value
            meetings_by_type[key] = meetings_by_type.get(key, 0) + 1

        upcoming_meetings = sum(
            1 for m in meetings if m.meeting_date > now and m.meeting_date <= cutoff_30d
        )

        # Interim analyses
        total_interim = len(analyses)
        boundaries_crossed = sum(len(a.boundaries_crossed) for a in analyses)

        # Adjudications
        total_adjs = len(adjs)
        adjs_by_status: dict[str, int] = {}
        pending_count = 0
        overdue_count = 0
        for adj in adjs:
            key = adj.status.value
            adjs_by_status[key] = adjs_by_status.get(key, 0) + 1
            if adj.status == EventAdjudicationStatus.PENDING:
                pending_count += 1
                if adj.created_at < overdue_cutoff:
                    overdue_count += 1

        # Trials with active monitoring
        trial_ids = set()
        for mtg in meetings:
            trial_ids.add(mtg.trial_id)
        for a in analyses:
            trial_ids.add(a.trial_id)

        return DSMBMetrics(
            total_members=total_members,
            active_members=active_members,
            total_meetings=total_meetings,
            meetings_by_type=meetings_by_type,
            total_interim_analyses=total_interim,
            boundaries_crossed_count=boundaries_crossed,
            total_adjudications=total_adjs,
            adjudications_by_status=adjs_by_status,
            pending_adjudications=pending_count,
            overdue_adjudications=overdue_count,
            total_safety_reports=len(reports),
            total_charters=len(charters),
            upcoming_meetings=upcoming_meetings,
            trials_with_active_monitoring=len(trial_ids),
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: SafetyMonitoringService | None = None
_instance_lock = threading.Lock()


def get_safety_monitoring_service() -> SafetyMonitoringService:
    """Return the singleton SafetyMonitoringService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = SafetyMonitoringService()
    return _instance


def reset_safety_monitoring_service() -> SafetyMonitoringService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = SafetyMonitoringService()
    return _instance
