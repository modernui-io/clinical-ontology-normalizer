"""DSMB (Data Safety Monitoring Board) Management Service.

Manages DSMB operations including charter governance, member tracking, meeting
lifecycle, safety review workflows, recommendation voting, unblinding request
processing, quorum validation, and operational metrics.

Usage:
    from app.services.dsmb_management_service import (
        get_dsmb_management_service,
    )

    svc = get_dsmb_management_service()
    meetings = svc.list_meetings()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.dsmb_management import (
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
    DSMBRecommendation,
    DSMBRecommendationCreate,
    DSMBRecommendationUpdate,
    MeetingStatus,
    MeetingType,
    MemberRole,
    QuorumCheckResult,
    RecommendationType,
    SafetyReview,
    SafetyReviewCreate,
    SafetyReviewUpdate,
    UnblindingRequest,
    UnblindingRequestCreate,
    UnblindingRequestUpdate,
    UnblindingScope,
    UnblindingStatus,
    VoteOutcome,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

# Roles that must be represented for a valid quorum
REQUIRED_QUORUM_ROLES = {MemberRole.CHAIR, MemberRole.STATISTICIAN, MemberRole.CLINICIAN}


class DSMBManagementService:
    """In-memory DSMB Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._charters: dict[str, DSMBCharter] = {}
        self._members: dict[str, DSMBMember] = {}
        self._meetings: dict[str, DSMBMeeting] = {}
        self._safety_reviews: dict[str, SafetyReview] = {}
        self._recommendations: dict[str, DSMBRecommendation] = {}
        self._unblinding_requests: dict[str, UnblindingRequest] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic DSMB management data."""
        now = datetime.now(timezone.utc)

        # --- 3 DSMB Charters ---
        charters_data = [
            {
                "id": "DSMB-CHR-001",
                "trial_id": EYLEA_TRIAL,
                "version": "2.0",
                "effective_date": now - timedelta(days=365),
                "approved_date": now - timedelta(days=370),
                "approved_by": "Dr. Robert Chen",
                "review_frequency": "quarterly",
                "stopping_rules": "O'Brien-Fleming alpha-spending function with 3 planned interim analyses. Efficacy boundary: one-sided p < 0.001 at first interim, p < 0.005 at second. Futility boundary: conditional power < 20%.",
                "unblinding_procedures": "Unblinding requires written request to independent statistician. Individual patient unblinding permitted for safety only. Full treatment-arm unblinding requires DSMB majority vote.",
                "membership_criteria": "Minimum 5 members: chair (senior clinician), 2 clinicians in ophthalmology, 1 biostatistician, 1 ethicist. No member may have financial interest in sponsor.",
                "conflict_of_interest_policy": "All members must disclose financial interests, consulting arrangements, and research funding from sponsor or competitors. Annual COI renewal required. Conflicted members recuse from relevant discussions.",
                "created_at": now - timedelta(days=400),
            },
            {
                "id": "DSMB-CHR-002",
                "trial_id": DUPIXENT_TRIAL,
                "version": "1.0",
                "effective_date": now - timedelta(days=200),
                "approved_date": now - timedelta(days=205),
                "approved_by": "Dr. Susan Park",
                "review_frequency": "semi-annual",
                "stopping_rules": "Lan-DeMets alpha-spending with Pocock-type boundaries. Single interim analysis at 50% enrollment. Futility: predictive probability of success < 10%.",
                "unblinding_procedures": "Treatment-arm level unblinding at scheduled interim only. Emergency individual unblinding requires chair and statistician approval. All unblinding events documented.",
                "membership_criteria": "Minimum 4 members: chair, 1 dermatologist, 1 immunologist, 1 biostatistician. Patient advocate recommended. No employees of sponsor or CRO.",
                "conflict_of_interest_policy": "Members must have no financial relationship with Regeneron or direct competitors in the same therapeutic area. COI forms collected at appointment and annually thereafter.",
                "created_at": now - timedelta(days=220),
            },
            {
                "id": "DSMB-CHR-003",
                "trial_id": LIBTAYO_TRIAL,
                "version": "1.1",
                "effective_date": now - timedelta(days=150),
                "approved_date": now - timedelta(days=155),
                "approved_by": "Dr. Maria Gonzalez",
                "review_frequency": "quarterly",
                "stopping_rules": "Group sequential design with Haybittle-Peto boundary for efficacy (p < 0.001 at interims). Safety monitoring: if treatment-related mortality exceeds 5% in any arm, immediate review triggered.",
                "unblinding_procedures": "Planned interim analyses performed by independent statistical center. DSMB reviews unblinded data in closed session. Sponsor receives only recommendation (not unblinded data).",
                "membership_criteria": "Minimum 5 members: chair (oncologist), 2 medical oncologists, 1 biostatistician, 1 patient advocate. At least one member with immunotherapy expertise.",
                "conflict_of_interest_policy": "No member may hold equity in sponsor. Consulting fees from sponsor within past 2 years are disqualifying. All potential conflicts reviewed by independent ethics committee.",
                "created_at": now - timedelta(days=170),
            },
        ]

        for c in charters_data:
            self._charters[c["id"]] = DSMBCharter(**c)

        # --- 7 DSMB Members ---
        members_data = [
            {
                "id": "DSMB-MEM-001",
                "charter_id": "DSMB-CHR-001",
                "name": "Dr. Elizabeth Warren",
                "role": MemberRole.CHAIR,
                "institution": "Harvard Medical School",
                "specialty": "Ophthalmology",
                "email": "e.warren@hms.harvard.edu",
                "term_start": now - timedelta(days=365),
                "term_end": now + timedelta(days=365),
                "active": True,
                "conflict_declarations": [],
            },
            {
                "id": "DSMB-MEM-002",
                "charter_id": "DSMB-CHR-001",
                "name": "Dr. James Liu",
                "role": MemberRole.STATISTICIAN,
                "institution": "Johns Hopkins Bloomberg School of Public Health",
                "specialty": "Biostatistics",
                "email": "j.liu@jhsph.edu",
                "term_start": now - timedelta(days=365),
                "term_end": now + timedelta(days=365),
                "active": True,
                "conflict_declarations": ["Consulting for AbbVie (non-ophthalmic indications)"],
            },
            {
                "id": "DSMB-MEM-003",
                "charter_id": "DSMB-CHR-001",
                "name": "Dr. Priya Sharma",
                "role": MemberRole.CLINICIAN,
                "institution": "Bascom Palmer Eye Institute",
                "specialty": "Retinal Surgery",
                "email": "p.sharma@med.miami.edu",
                "term_start": now - timedelta(days=300),
                "term_end": now + timedelta(days=430),
                "active": True,
                "conflict_declarations": [],
            },
            {
                "id": "DSMB-MEM-004",
                "charter_id": "DSMB-CHR-001",
                "name": "Prof. Thomas Reed",
                "role": MemberRole.ETHICIST,
                "institution": "Georgetown University",
                "specialty": "Bioethics",
                "email": "t.reed@georgetown.edu",
                "term_start": now - timedelta(days=365),
                "term_end": now + timedelta(days=365),
                "active": True,
                "conflict_declarations": [],
            },
            {
                "id": "DSMB-MEM-005",
                "charter_id": "DSMB-CHR-001",
                "name": "Margaret Collins",
                "role": MemberRole.PATIENT_ADVOCATE,
                "institution": "American Macular Degeneration Foundation",
                "specialty": "Patient Advocacy",
                "email": "m.collins@amdf.org",
                "term_start": now - timedelta(days=200),
                "term_end": now + timedelta(days=530),
                "active": True,
                "conflict_declarations": [],
            },
            {
                "id": "DSMB-MEM-006",
                "charter_id": "DSMB-CHR-002",
                "name": "Dr. Angela Torres",
                "role": MemberRole.CHAIR,
                "institution": "Stanford University School of Medicine",
                "specialty": "Dermatology",
                "email": "a.torres@stanford.edu",
                "term_start": now - timedelta(days=200),
                "term_end": now + timedelta(days=530),
                "active": True,
                "conflict_declarations": [],
            },
            {
                "id": "DSMB-MEM-007",
                "charter_id": "DSMB-CHR-002",
                "name": "Dr. Kevin Nakamura",
                "role": MemberRole.STATISTICIAN,
                "institution": "University of Washington",
                "specialty": "Clinical Trials Biostatistics",
                "email": "k.nakamura@uw.edu",
                "term_start": now - timedelta(days=200),
                "term_end": now + timedelta(days=530),
                "active": False,
                "conflict_declarations": ["Advisory board member for Sanofi (competitor)"],
            },
        ]

        for m in members_data:
            self._members[m["id"]] = DSMBMember(**m)

        # --- 6 DSMB Meetings ---
        meetings_data = [
            {
                "id": "DSMB-MTG-001",
                "charter_id": "DSMB-CHR-001",
                "trial_id": EYLEA_TRIAL,
                "meeting_type": MeetingType.ORGANIZATIONAL,
                "meeting_number": 1,
                "scheduled_date": now - timedelta(days=350),
                "actual_date": now - timedelta(days=350),
                "status": MeetingStatus.COMPLETED,
                "location": "Virtual (Zoom)",
                "agenda": "1. Charter review and approval\n2. Member introductions\n3. Review of protocol synopsis\n4. Discussion of monitoring plan\n5. Set meeting schedule",
                "quorum_required": 3,
                "quorum_met": True,
                "attendees": ["DSMB-MEM-001", "DSMB-MEM-002", "DSMB-MEM-003", "DSMB-MEM-004", "DSMB-MEM-005"],
                "open_session_minutes": "Sponsor presented protocol synopsis. DSMB reviewed charter draft. All members introduced and COI forms collected.",
                "closed_session_minutes": "Charter approved unanimously. Monitoring plan discussed. Quarterly review schedule confirmed.",
                "created_at": now - timedelta(days=360),
            },
            {
                "id": "DSMB-MTG-002",
                "charter_id": "DSMB-CHR-001",
                "trial_id": EYLEA_TRIAL,
                "meeting_type": MeetingType.SCHEDULED_REVIEW,
                "meeting_number": 2,
                "scheduled_date": now - timedelta(days=260),
                "actual_date": now - timedelta(days=260),
                "status": MeetingStatus.COMPLETED,
                "location": "Virtual (Zoom)",
                "agenda": "1. Enrollment update\n2. Safety review (AEs, SAEs)\n3. Interim efficacy data\n4. Protocol amendments\n5. DSMB recommendation",
                "quorum_required": 3,
                "quorum_met": True,
                "attendees": ["DSMB-MEM-001", "DSMB-MEM-002", "DSMB-MEM-003", "DSMB-MEM-004"],
                "open_session_minutes": "Sponsor reviewed enrollment progress (42% of target). 3 protocol amendments discussed. No new safety signals identified by sponsor.",
                "closed_session_minutes": "Independent statistician presented unblinded safety data. No imbalance in AE rates. One SAE under review. DSMB recommends continuation.",
                "created_at": now - timedelta(days=270),
            },
            {
                "id": "DSMB-MTG-003",
                "charter_id": "DSMB-CHR-001",
                "trial_id": EYLEA_TRIAL,
                "meeting_type": MeetingType.SCHEDULED_REVIEW,
                "meeting_number": 3,
                "scheduled_date": now - timedelta(days=170),
                "actual_date": now - timedelta(days=170),
                "status": MeetingStatus.COMPLETED,
                "location": "In-person, Bethesda MD",
                "agenda": "1. Enrollment update\n2. Safety data review (cumulative)\n3. First interim analysis\n4. Stopping rule evaluation\n5. DSMB recommendation",
                "quorum_required": 3,
                "quorum_met": True,
                "attendees": ["DSMB-MEM-001", "DSMB-MEM-002", "DSMB-MEM-003", "DSMB-MEM-005"],
                "open_session_minutes": "Enrollment at 65% of target. Sponsor reported 12 SAEs total, none unexpected. Protocol compliance at 94%.",
                "closed_session_minutes": "First interim analysis reviewed. Efficacy boundary not crossed. No futility concern. Safety profile acceptable. Recommend continuation with minor protocol clarification on AE grading.",
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "DSMB-MTG-004",
                "charter_id": "DSMB-CHR-001",
                "trial_id": EYLEA_TRIAL,
                "meeting_type": MeetingType.EMERGENCY,
                "meeting_number": 4,
                "scheduled_date": now - timedelta(days=90),
                "actual_date": now - timedelta(days=90),
                "status": MeetingStatus.COMPLETED,
                "location": "Virtual (Zoom) - Emergency Call",
                "agenda": "1. Review of SUSAR cluster\n2. Causality assessment\n3. Risk-benefit evaluation\n4. Immediate recommendation",
                "quorum_required": 3,
                "quorum_met": True,
                "attendees": ["DSMB-MEM-001", "DSMB-MEM-002", "DSMB-MEM-003"],
                "open_session_minutes": "Sponsor reported 3 SUSARs of hepatotoxicity within 2-week period. All in high-dose arm. One patient hospitalized.",
                "closed_session_minutes": "DSMB reviewed detailed case narratives. Determined events possibly related. Recommended temporary enrollment pause in high-dose arm pending hepatic safety review.",
                "created_at": now - timedelta(days=92),
            },
            {
                "id": "DSMB-MTG-005",
                "charter_id": "DSMB-CHR-002",
                "trial_id": DUPIXENT_TRIAL,
                "meeting_type": MeetingType.SCHEDULED_REVIEW,
                "meeting_number": 2,
                "scheduled_date": now - timedelta(days=45),
                "actual_date": now - timedelta(days=45),
                "status": MeetingStatus.COMPLETED,
                "location": "Virtual (Microsoft Teams)",
                "agenda": "1. Enrollment update\n2. Safety review\n3. Efficacy trends\n4. Protocol deviations\n5. Recommendation",
                "quorum_required": 2,
                "quorum_met": True,
                "attendees": ["DSMB-MEM-006", "DSMB-MEM-007"],
                "open_session_minutes": "Enrollment at 78%. Safety profile consistent with known drug profile. 2 protocol deviations reviewed.",
                "closed_session_minutes": "Unblinded data reviewed. No safety concerns. Efficacy trends favorable. Recommend continuation unchanged.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "DSMB-MTG-006",
                "charter_id": "DSMB-CHR-001",
                "trial_id": EYLEA_TRIAL,
                "meeting_type": MeetingType.SCHEDULED_REVIEW,
                "meeting_number": 5,
                "scheduled_date": now + timedelta(days=20),
                "actual_date": None,
                "status": MeetingStatus.SCHEDULED,
                "location": "Virtual (Zoom)",
                "agenda": "1. Enrollment update\n2. Follow-up on enrollment pause resolution\n3. Cumulative safety data\n4. Second interim analysis\n5. Recommendation",
                "quorum_required": 3,
                "quorum_met": None,
                "attendees": [],
                "open_session_minutes": None,
                "closed_session_minutes": None,
                "created_at": now - timedelta(days=10),
            },
        ]

        for mtg in meetings_data:
            self._meetings[mtg["id"]] = DSMBMeeting(**mtg)

        # --- 4 Safety Reviews ---
        reviews_data = [
            {
                "id": "DSMB-SR-001",
                "meeting_id": "DSMB-MTG-002",
                "data_cutoff_date": now - timedelta(days=270),
                "enrollment_at_review": 126,
                "ae_summary": "Total AEs: 89 (treatment: 52, control: 37). Most common: headache (18%), injection site reaction (12%), nausea (8%). No unexpected AEs.",
                "sae_summary": "Total SAEs: 3 (treatment: 2, control: 1). Treatment SAEs: 1 retinal detachment (unrelated), 1 endophthalmitis (possibly related). Control SAE: 1 MI (unrelated).",
                "mortality_summary": "No deaths reported in either arm.",
                "efficacy_summary": "Not yet evaluable at this interim. Primary endpoint assessment pending.",
                "dmc_statistician_report": "Blinded safety analysis shows no imbalance in overall AE rates between arms. SAE rate within expected range for population.",
                "independent_statistician_report": "Unblinded analysis: treatment arm AE rate 41.3% vs control 29.6%. Difference driven by injection site reactions. No concerning safety signals.",
                "created_at": now - timedelta(days=260),
            },
            {
                "id": "DSMB-SR-002",
                "meeting_id": "DSMB-MTG-003",
                "data_cutoff_date": now - timedelta(days=180),
                "enrollment_at_review": 195,
                "ae_summary": "Total AEs: 156 (treatment: 91, control: 65). Cumulative rates consistent with prior review. New signal: 3 cases of elevated IOP in treatment arm.",
                "sae_summary": "Total SAEs: 8 (treatment: 5, control: 3). New treatment SAEs: 1 vitreous hemorrhage (possibly related), 1 stroke (unrelated). Cumulative SAE rate 4.1%.",
                "mortality_summary": "1 death in control arm (cardiac arrest, unrelated to study). No treatment-arm deaths.",
                "efficacy_summary": "First interim analysis: treatment effect estimate positive but efficacy boundary not crossed (Z-statistic 1.82 vs boundary 3.47). Conditional power 72%.",
                "dmc_statistician_report": "IOP elevation signal requires monitoring. Overall safety profile remains acceptable. Bayesian predictive probability of trial success: 68%.",
                "independent_statistician_report": "Unblinded efficacy: treatment arm shows 23% improvement vs control on primary endpoint. O'Brien-Fleming boundary not crossed. Futility boundary not approached.",
                "created_at": now - timedelta(days=170),
            },
            {
                "id": "DSMB-SR-003",
                "meeting_id": "DSMB-MTG-004",
                "data_cutoff_date": now - timedelta(days=95),
                "enrollment_at_review": 245,
                "ae_summary": "Emergency review focused on hepatotoxicity cluster. 3 cases of Grade 3+ ALT elevation in high-dose arm within 14-day window. Background rate in trial: 1.2%.",
                "sae_summary": "3 SUSARs of hepatotoxicity: Patient 1 (ALT 8x ULN, hospitalized), Patient 2 (ALT 5x ULN, outpatient), Patient 3 (ALT 6x ULN, outpatient). All in high-dose arm.",
                "mortality_summary": "No deaths related to hepatotoxicity. 1 additional death in control arm (unrelated, metastatic cancer).",
                "efficacy_summary": None,
                "dmc_statistician_report": "Hepatotoxicity rate in high-dose arm: 3.7% vs 0.8% in low-dose and 0.4% in control. Fisher exact p = 0.03 for high-dose vs control comparison.",
                "independent_statistician_report": "Clear dose-response relationship for hepatotoxicity. High-dose arm signal is statistically significant. Recommend enhanced hepatic monitoring if enrollment resumes.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "DSMB-SR-004",
                "meeting_id": "DSMB-MTG-005",
                "data_cutoff_date": now - timedelta(days=55),
                "enrollment_at_review": 312,
                "ae_summary": "Total AEs: 198 (treatment: 108, control: 90). AE profile consistent with known dupilumab safety. Most common: injection site reactions (15%), nasopharyngitis (9%).",
                "sae_summary": "Total SAEs: 6 (treatment: 3, control: 3). No new safety signals. All SAEs assessed as unrelated to study drug.",
                "mortality_summary": "No deaths in either arm.",
                "efficacy_summary": "Interim efficacy analysis shows favorable trends. EASI-75 response rate numerically higher in treatment arm.",
                "dmc_statistician_report": "Safety profile consistent with extensive post-marketing data. No new signals detected. Benefit-risk remains favorable.",
                "independent_statistician_report": "Unblinded efficacy data supports continued enrollment. Treatment effect consistent with prior dupilumab trials.",
                "created_at": now - timedelta(days=45),
            },
        ]

        for sr in reviews_data:
            self._safety_reviews[sr["id"]] = SafetyReview(**sr)

        # --- 4 DSMB Recommendations ---
        recommendations_data = [
            {
                "id": "DSMB-REC-001",
                "meeting_id": "DSMB-MTG-002",
                "recommendation_type": RecommendationType.CONTINUE_UNCHANGED,
                "rationale": "Safety profile acceptable. No efficacy concerns at this interim. Enrollment progressing adequately.",
                "conditions": None,
                "vote_outcome": VoteOutcome.UNANIMOUS,
                "votes_for": 4,
                "votes_against": 0,
                "votes_abstain": 0,
                "communicated_to_sponsor": True,
                "communicated_date": now - timedelta(days=258),
                "sponsor_response": "Acknowledged. Will continue trial as planned.",
                "created_at": now - timedelta(days=260),
            },
            {
                "id": "DSMB-REC-002",
                "meeting_id": "DSMB-MTG-003",
                "recommendation_type": RecommendationType.CONTINUE_WITH_MODIFICATIONS,
                "rationale": "Efficacy trends encouraging but boundary not crossed. IOP elevation signal in treatment arm requires enhanced monitoring.",
                "conditions": "Add IOP measurement at weeks 4, 8, and 12 for all subjects. Implement IOP > 25 mmHg as stopping criterion for individual subjects.",
                "vote_outcome": VoteOutcome.MAJORITY,
                "votes_for": 3,
                "votes_against": 1,
                "votes_abstain": 0,
                "communicated_to_sponsor": True,
                "communicated_date": now - timedelta(days=168),
                "sponsor_response": "Protocol amendment submitted to add IOP monitoring. Will implement within 2 weeks.",
                "created_at": now - timedelta(days=170),
            },
            {
                "id": "DSMB-REC-003",
                "meeting_id": "DSMB-MTG-004",
                "recommendation_type": RecommendationType.PAUSE_ENROLLMENT,
                "rationale": "Cluster of 3 hepatotoxicity SUSARs in high-dose arm within 14 days. Statistically significant dose-response. Individual patient safety concern warrants temporary pause.",
                "conditions": "Pause enrollment in high-dose arm only. Continue low-dose and control arms. Sponsor to conduct hepatic safety review within 30 days. Enhanced liver monitoring for enrolled subjects.",
                "vote_outcome": VoteOutcome.UNANIMOUS,
                "votes_for": 3,
                "votes_against": 0,
                "votes_abstain": 0,
                "communicated_to_sponsor": True,
                "communicated_date": now - timedelta(days=89),
                "sponsor_response": "Enrollment in high-dose arm suspended immediately. Independent hepatic safety review committee convened. Enhanced monitoring implemented.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "DSMB-REC-004",
                "meeting_id": "DSMB-MTG-005",
                "recommendation_type": RecommendationType.CONTINUE_UNCHANGED,
                "rationale": "Safety profile consistent with known drug profile. No new signals. Efficacy trends favorable. Enrollment on track.",
                "conditions": None,
                "vote_outcome": VoteOutcome.UNANIMOUS,
                "votes_for": 2,
                "votes_against": 0,
                "votes_abstain": 0,
                "communicated_to_sponsor": True,
                "communicated_date": now - timedelta(days=43),
                "sponsor_response": "Acknowledged. Trial continues as planned.",
                "created_at": now - timedelta(days=45),
            },
        ]

        for rec in recommendations_data:
            self._recommendations[rec["id"]] = DSMBRecommendation(**rec)

        # --- 3 Unblinding Requests ---
        unblinding_data = [
            {
                "id": "DSMB-UBR-001",
                "meeting_id": "DSMB-MTG-003",
                "trial_id": EYLEA_TRIAL,
                "requested_by": "Dr. Elizabeth Warren (DSMB Chair)",
                "request_date": now - timedelta(days=175),
                "justification": "First planned interim analysis requires treatment-arm level unblinding to evaluate efficacy boundaries per charter-defined stopping rules.",
                "scope": UnblindingScope.INTERIM_ANALYSIS,
                "status": UnblindingStatus.COMPLETED,
                "approved": True,
                "approved_by": "Independent Statistical Center",
                "approval_date": now - timedelta(days=173),
                "unblinding_date": now - timedelta(days=171),
                "results_summary": "Interim analysis completed. Treatment effect positive (Z=1.82) but O'Brien-Fleming boundary not crossed. No futility concern. Results presented to DSMB in closed session.",
                "created_at": now - timedelta(days=175),
            },
            {
                "id": "DSMB-UBR-002",
                "meeting_id": "DSMB-MTG-004",
                "trial_id": EYLEA_TRIAL,
                "requested_by": "Dr. James Liu (DSMB Statistician)",
                "request_date": now - timedelta(days=92),
                "justification": "Emergency unblinding to assess treatment-arm specific hepatotoxicity rates following SUSAR cluster. Required to determine if signal is dose-dependent.",
                "scope": UnblindingScope.TREATMENT_ARM,
                "status": UnblindingStatus.COMPLETED,
                "approved": True,
                "approved_by": "Dr. Elizabeth Warren (DSMB Chair)",
                "approval_date": now - timedelta(days=91),
                "unblinding_date": now - timedelta(days=90),
                "results_summary": "Confirmed dose-response: high-dose 3.7%, low-dose 0.8%, control 0.4%. Clear signal in high-dose arm. DSMB recommended enrollment pause for high-dose.",
                "created_at": now - timedelta(days=92),
            },
            {
                "id": "DSMB-UBR-003",
                "meeting_id": None,
                "trial_id": DUPIXENT_TRIAL,
                "requested_by": "Site PI (Dr. Michael Harris)",
                "request_date": now - timedelta(days=20),
                "justification": "Individual patient unblinding requested for patient DUP-0147 who developed severe anaphylaxis requiring ICU admission. Treating physicians need to know treatment assignment for ongoing management.",
                "scope": UnblindingScope.INDIVIDUAL_PATIENT,
                "status": UnblindingStatus.PENDING,
                "approved": None,
                "approved_by": None,
                "approval_date": None,
                "unblinding_date": None,
                "results_summary": None,
                "created_at": now - timedelta(days=20),
            },
        ]

        for ubr in unblinding_data:
            self._unblinding_requests[ubr["id"]] = UnblindingRequest(**ubr)

    # ------------------------------------------------------------------
    # Charter Management
    # ------------------------------------------------------------------

    def list_charters(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[DSMBCharter]:
        """List DSMB charters with optional trial filter."""
        with self._lock:
            result = list(self._charters.values())

        if trial_id is not None:
            result = [c for c in result if c.trial_id == trial_id]

        return sorted(result, key=lambda c: c.effective_date, reverse=True)

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
            created_at=now,
            **payload.model_dump(),
        )
        with self._lock:
            self._charters[charter_id] = charter
        logger.info("Created DSMB charter %s for trial %s", charter_id, payload.trial_id)
        return charter

    def update_charter(self, charter_id: str, payload: DSMBCharterUpdate) -> DSMBCharter | None:
        """Update an existing DSMB charter."""
        with self._lock:
            existing = self._charters.get(charter_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DSMBCharter(**data)
            self._charters[charter_id] = updated
        return updated

    def delete_charter(self, charter_id: str) -> bool:
        """Delete a charter. Returns True if deleted."""
        with self._lock:
            if charter_id in self._charters:
                del self._charters[charter_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Member Management
    # ------------------------------------------------------------------

    def list_members(
        self,
        *,
        charter_id: str | None = None,
        role: MemberRole | None = None,
        active: bool | None = None,
    ) -> list[DSMBMember]:
        """List DSMB members with optional filters."""
        with self._lock:
            result = list(self._members.values())

        if charter_id is not None:
            result = [m for m in result if m.charter_id == charter_id]
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
            active=True,
            **payload.model_dump(),
        )
        with self._lock:
            # Verify charter exists
            if payload.charter_id not in self._charters:
                raise ValueError(f"Charter '{payload.charter_id}' not found")
            self._members[member_id] = member
        logger.info("Created DSMB member %s: %s (%s)", member_id, payload.name, payload.role.value)
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

    def delete_member(self, member_id: str) -> bool:
        """Delete a member. Returns True if deleted."""
        with self._lock:
            if member_id in self._members:
                del self._members[member_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Meeting Management
    # ------------------------------------------------------------------

    def list_meetings(
        self,
        *,
        charter_id: str | None = None,
        trial_id: str | None = None,
        status: MeetingStatus | None = None,
        meeting_type: MeetingType | None = None,
    ) -> list[DSMBMeeting]:
        """List DSMB meetings with optional filters."""
        with self._lock:
            result = list(self._meetings.values())

        if charter_id is not None:
            result = [m for m in result if m.charter_id == charter_id]
        if trial_id is not None:
            result = [m for m in result if m.trial_id == trial_id]
        if status is not None:
            result = [m for m in result if m.status == status]
        if meeting_type is not None:
            result = [m for m in result if m.meeting_type == meeting_type]

        return sorted(result, key=lambda m: m.scheduled_date, reverse=True)

    def get_meeting(self, meeting_id: str) -> DSMBMeeting | None:
        """Get a single meeting by ID."""
        with self._lock:
            return self._meetings.get(meeting_id)

    def schedule_meeting(self, payload: DSMBMeetingCreate) -> DSMBMeeting:
        """Schedule a new DSMB meeting."""
        now = datetime.now(timezone.utc)
        meeting_id = f"DSMB-MTG-{uuid4().hex[:8].upper()}"

        with self._lock:
            if payload.charter_id not in self._charters:
                raise ValueError(f"Charter '{payload.charter_id}' not found")

        meeting = DSMBMeeting(
            id=meeting_id,
            charter_id=payload.charter_id,
            trial_id=payload.trial_id,
            meeting_type=payload.meeting_type,
            meeting_number=payload.meeting_number,
            scheduled_date=payload.scheduled_date,
            actual_date=None,
            status=MeetingStatus.SCHEDULED,
            location=payload.location,
            agenda=payload.agenda,
            quorum_required=payload.quorum_required,
            quorum_met=None,
            attendees=[],
            open_session_minutes=None,
            closed_session_minutes=None,
            created_at=now,
        )
        with self._lock:
            self._meetings[meeting_id] = meeting
        logger.info(
            "Scheduled DSMB meeting %s (type: %s) for %s",
            meeting_id, payload.meeting_type.value, payload.scheduled_date.isoformat(),
        )
        return meeting

    def update_meeting(self, meeting_id: str, payload: DSMBMeetingUpdate) -> DSMBMeeting | None:
        """Update an existing DSMB meeting."""
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

    def delete_meeting(self, meeting_id: str) -> bool:
        """Delete a meeting. Returns True if deleted."""
        with self._lock:
            if meeting_id in self._meetings:
                del self._meetings[meeting_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Quorum Check
    # ------------------------------------------------------------------

    def check_quorum(self, meeting_id: str) -> QuorumCheckResult | None:
        """Check whether quorum is met for a DSMB meeting.

        Quorum requires:
        1. Minimum number of attendees (per charter)
        2. Chair, Statistician, and Clinician roles must be represented
        """
        with self._lock:
            meeting = self._meetings.get(meeting_id)
            if meeting is None:
                return None

            attendees = meeting.attendees
            quorum_required = meeting.quorum_required

            # Get roles of attendees
            attendee_roles: set[MemberRole] = set()
            for member_id in attendees:
                member = self._members.get(member_id)
                if member is not None and member.active:
                    attendee_roles.add(member.role)

        missing_roles = [
            role.value for role in REQUIRED_QUORUM_ROLES
            if role not in attendee_roles
        ]

        attendees_count = len(attendees)
        quorum_met = attendees_count >= quorum_required and len(missing_roles) == 0

        return QuorumCheckResult(
            meeting_id=meeting_id,
            quorum_required=quorum_required,
            attendees_count=attendees_count,
            quorum_met=quorum_met,
            missing_roles=sorted(missing_roles),
        )

    # ------------------------------------------------------------------
    # Safety Reviews
    # ------------------------------------------------------------------

    def list_safety_reviews(
        self,
        *,
        meeting_id: str | None = None,
    ) -> list[SafetyReview]:
        """List safety reviews with optional meeting filter."""
        with self._lock:
            result = list(self._safety_reviews.values())

        if meeting_id is not None:
            result = [sr for sr in result if sr.meeting_id == meeting_id]

        return sorted(result, key=lambda sr: sr.data_cutoff_date, reverse=True)

    def get_safety_review(self, review_id: str) -> SafetyReview | None:
        """Get a single safety review by ID."""
        with self._lock:
            return self._safety_reviews.get(review_id)

    def conduct_safety_review(self, payload: SafetyReviewCreate) -> SafetyReview:
        """Create a new safety review for a DSMB meeting."""
        now = datetime.now(timezone.utc)
        review_id = f"DSMB-SR-{uuid4().hex[:8].upper()}"

        with self._lock:
            if payload.meeting_id not in self._meetings:
                raise ValueError(f"Meeting '{payload.meeting_id}' not found")

        review = SafetyReview(
            id=review_id,
            created_at=now,
            **payload.model_dump(),
        )
        with self._lock:
            self._safety_reviews[review_id] = review
        logger.info("Created safety review %s for meeting %s", review_id, payload.meeting_id)
        return review

    def update_safety_review(self, review_id: str, payload: SafetyReviewUpdate) -> SafetyReview | None:
        """Update an existing safety review."""
        with self._lock:
            existing = self._safety_reviews.get(review_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = SafetyReview(**data)
            self._safety_reviews[review_id] = updated
        return updated

    def delete_safety_review(self, review_id: str) -> bool:
        """Delete a safety review. Returns True if deleted."""
        with self._lock:
            if review_id in self._safety_reviews:
                del self._safety_reviews[review_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------

    def list_recommendations(
        self,
        *,
        meeting_id: str | None = None,
        recommendation_type: RecommendationType | None = None,
    ) -> list[DSMBRecommendation]:
        """List DSMB recommendations with optional filters."""
        with self._lock:
            result = list(self._recommendations.values())

        if meeting_id is not None:
            result = [r for r in result if r.meeting_id == meeting_id]
        if recommendation_type is not None:
            result = [r for r in result if r.recommendation_type == recommendation_type]

        return sorted(result, key=lambda r: r.created_at, reverse=True)

    def get_recommendation(self, recommendation_id: str) -> DSMBRecommendation | None:
        """Get a single recommendation by ID."""
        with self._lock:
            return self._recommendations.get(recommendation_id)

    def record_recommendation(self, payload: DSMBRecommendationCreate) -> DSMBRecommendation:
        """Record a new DSMB recommendation."""
        now = datetime.now(timezone.utc)
        rec_id = f"DSMB-REC-{uuid4().hex[:8].upper()}"

        with self._lock:
            if payload.meeting_id not in self._meetings:
                raise ValueError(f"Meeting '{payload.meeting_id}' not found")

        rec = DSMBRecommendation(
            id=rec_id,
            communicated_to_sponsor=False,
            communicated_date=None,
            sponsor_response=None,
            created_at=now,
            **payload.model_dump(),
        )
        with self._lock:
            self._recommendations[rec_id] = rec
        logger.info(
            "Recorded DSMB recommendation %s (%s) for meeting %s",
            rec_id, payload.recommendation_type.value, payload.meeting_id,
        )
        return rec

    def update_recommendation(
        self, recommendation_id: str, payload: DSMBRecommendationUpdate
    ) -> DSMBRecommendation | None:
        """Update a DSMB recommendation."""
        with self._lock:
            existing = self._recommendations.get(recommendation_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DSMBRecommendation(**data)
            self._recommendations[recommendation_id] = updated
        return updated

    def delete_recommendation(self, recommendation_id: str) -> bool:
        """Delete a recommendation. Returns True if deleted."""
        with self._lock:
            if recommendation_id in self._recommendations:
                del self._recommendations[recommendation_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Unblinding Requests
    # ------------------------------------------------------------------

    def list_unblinding_requests(
        self,
        *,
        trial_id: str | None = None,
        status: UnblindingStatus | None = None,
    ) -> list[UnblindingRequest]:
        """List unblinding requests with optional filters."""
        with self._lock:
            result = list(self._unblinding_requests.values())

        if trial_id is not None:
            result = [u for u in result if u.trial_id == trial_id]
        if status is not None:
            result = [u for u in result if u.status == status]

        return sorted(result, key=lambda u: u.request_date, reverse=True)

    def get_unblinding_request(self, request_id: str) -> UnblindingRequest | None:
        """Get a single unblinding request by ID."""
        with self._lock:
            return self._unblinding_requests.get(request_id)

    def request_unblinding(self, payload: UnblindingRequestCreate) -> UnblindingRequest:
        """Create a new unblinding request."""
        now = datetime.now(timezone.utc)
        req_id = f"DSMB-UBR-{uuid4().hex[:8].upper()}"

        request = UnblindingRequest(
            id=req_id,
            meeting_id=payload.meeting_id,
            trial_id=payload.trial_id,
            requested_by=payload.requested_by,
            request_date=now,
            justification=payload.justification,
            scope=payload.scope,
            status=UnblindingStatus.PENDING,
            approved=None,
            approved_by=None,
            approval_date=None,
            unblinding_date=None,
            results_summary=None,
            created_at=now,
        )
        with self._lock:
            self._unblinding_requests[req_id] = request
        logger.info(
            "Created unblinding request %s for trial %s (scope: %s)",
            req_id, payload.trial_id, payload.scope.value,
        )
        return request

    def update_unblinding_request(
        self, request_id: str, payload: UnblindingRequestUpdate
    ) -> UnblindingRequest | None:
        """Update an unblinding request (approve/deny/complete)."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._unblinding_requests.get(request_id)
            if existing is None:
                return None

            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set approval_date when approved is set
            if "approved" in updates and updates["approved"] is not None:
                if existing.approved is None:
                    updates.setdefault("approval_date", now)
                    if updates["approved"]:
                        updates.setdefault("status", UnblindingStatus.APPROVED)
                    else:
                        updates.setdefault("status", UnblindingStatus.DENIED)

            # Auto-set status to completed when unblinding_date is provided
            if "unblinding_date" in updates and updates["unblinding_date"] is not None:
                updates.setdefault("status", UnblindingStatus.COMPLETED)

            data.update(updates)
            updated = UnblindingRequest(**data)
            self._unblinding_requests[request_id] = updated
        return updated

    def delete_unblinding_request(self, request_id: str) -> bool:
        """Delete an unblinding request. Returns True if deleted."""
        with self._lock:
            if request_id in self._unblinding_requests:
                del self._unblinding_requests[request_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics & Dashboard
    # ------------------------------------------------------------------

    def get_metrics(self) -> DSMBMetrics:
        """Compute aggregated DSMB operational metrics."""
        with self._lock:
            charters = list(self._charters.values())
            members = list(self._members.values())
            meetings = list(self._meetings.values())
            safety_reviews = list(self._safety_reviews.values())
            recommendations = list(self._recommendations.values())
            unblinding_requests = list(self._unblinding_requests.values())

        active_members = sum(1 for m in members if m.active)

        completed_meetings = sum(
            1 for m in meetings if m.status == MeetingStatus.COMPLETED
        )
        planned_meetings = sum(
            1 for m in meetings
            if m.status in (MeetingStatus.PLANNED, MeetingStatus.SCHEDULED)
        )

        rec_by_type: dict[str, int] = {}
        for rec in recommendations:
            key = rec.recommendation_type.value
            rec_by_type[key] = rec_by_type.get(key, 0) + 1

        pending_unblinding = sum(
            1 for u in unblinding_requests if u.status == UnblindingStatus.PENDING
        )

        communicated = sum(
            1 for r in recommendations if r.communicated_to_sponsor
        )

        meetings_with_quorum = sum(
            1 for m in meetings
            if m.status == MeetingStatus.COMPLETED and m.quorum_met is True
        )

        return DSMBMetrics(
            total_charters=len(charters),
            total_members=len(members),
            active_members=active_members,
            total_meetings=len(meetings),
            completed_meetings=completed_meetings,
            planned_meetings=planned_meetings,
            total_safety_reviews=len(safety_reviews),
            total_recommendations=len(recommendations),
            recommendations_by_type=rec_by_type,
            total_unblinding_requests=len(unblinding_requests),
            pending_unblinding_requests=pending_unblinding,
            recommendations_communicated=communicated,
            meetings_with_quorum=meetings_with_quorum,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: DSMBManagementService | None = None
_instance_lock = threading.Lock()


def get_dsmb_management_service() -> DSMBManagementService:
    """Return the singleton DSMBManagementService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = DSMBManagementService()
    return _instance


def reset_dsmb_management_service() -> DSMBManagementService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = DSMBManagementService()
    return _instance
