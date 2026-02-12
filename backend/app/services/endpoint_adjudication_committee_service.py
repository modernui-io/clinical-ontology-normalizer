"""Endpoint Adjudication Committee Service (EAC-MGMT).

Manages endpoint adjudication committee operations: committee member
management, case review tracking, adjudication outcomes, charter
management, and blinding compliance with committee metrics.

Usage:
    from app.services.endpoint_adjudication_committee_service import (
        get_endpoint_adjudication_committee_service,
    )

    svc = get_endpoint_adjudication_committee_service()
    members = svc.list_committee_members()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.endpoint_adjudication_committee import (
    AdjudicationOutcome,
    AdjudicationResult,
    AdjudicationResultCreate,
    AdjudicationResultUpdate,
    BlindingCompliance,
    BlindingComplianceCreate,
    BlindingComplianceUpdate,
    BlindingStatus,
    CaseReview,
    CaseReviewCreate,
    CaseReviewUpdate,
    CaseStatus,
    CharterRecord,
    CharterRecordCreate,
    CharterRecordUpdate,
    CharterStatus,
    CommitteeMember,
    CommitteeMemberCreate,
    CommitteeMemberUpdate,
    EndpointAdjudicationMetrics,
    MemberRole,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class EndpointAdjudicationCommitteeService:
    """In-memory Endpoint Adjudication Committee engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._committee_members: dict[str, CommitteeMember] = {}
        self._case_reviews: dict[str, CaseReview] = {}
        self._adjudication_results: dict[str, AdjudicationResult] = {}
        self._charter_records: dict[str, CharterRecord] = {}
        self._blinding_compliance: dict[str, BlindingCompliance] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic endpoint adjudication committee data."""
        now = datetime.now(timezone.utc)

        # --- 12 Committee Members ---
        members_data = [
            {
                "id": "CM-001",
                "trial_id": EYLEA_TRIAL,
                "member_name": "Dr. Eleanor Hartfield",
                "role": MemberRole.CHAIR,
                "specialty": "Retinal Surgery",
                "institution": "Johns Hopkins Wilmer Eye Institute",
                "is_active": True,
                "appointment_date": now - timedelta(days=540),
                "term_end_date": now + timedelta(days=365),
                "conflict_of_interest_declared": True,
                "coi_details": "Advisory board member for competitor; recused from relevant cases.",
                "training_completed": True,
                "training_date": now - timedelta(days=535),
                "cases_reviewed": 48,
                "agreement_rate_pct": 94.2,
                "appointed_by": "Sponsor Medical Director",
                "notes": "Founding EAC chair. Expert in OCT interpretation.",
                "created_at": now - timedelta(days=540),
            },
            {
                "id": "CM-002",
                "trial_id": EYLEA_TRIAL,
                "member_name": "Dr. Marcus Chen",
                "role": MemberRole.VOTING_MEMBER,
                "specialty": "Medical Retina",
                "institution": "Bascom Palmer Eye Institute",
                "is_active": True,
                "appointment_date": now - timedelta(days=530),
                "term_end_date": now + timedelta(days=375),
                "conflict_of_interest_declared": True,
                "coi_details": None,
                "training_completed": True,
                "training_date": now - timedelta(days=525),
                "cases_reviewed": 45,
                "agreement_rate_pct": 91.0,
                "appointed_by": "Sponsor Medical Director",
                "notes": None,
                "created_at": now - timedelta(days=530),
            },
            {
                "id": "CM-003",
                "trial_id": EYLEA_TRIAL,
                "member_name": "Dr. Priya Sharma",
                "role": MemberRole.VOTING_MEMBER,
                "specialty": "Vitreoretinal Disease",
                "institution": "Moorfields Eye Hospital",
                "is_active": True,
                "appointment_date": now - timedelta(days=520),
                "term_end_date": now + timedelta(days=385),
                "conflict_of_interest_declared": True,
                "coi_details": None,
                "training_completed": True,
                "training_date": now - timedelta(days=515),
                "cases_reviewed": 42,
                "agreement_rate_pct": 88.5,
                "appointed_by": "Sponsor Medical Director",
                "notes": "International member providing EU clinical perspective.",
                "created_at": now - timedelta(days=520),
            },
            {
                "id": "CM-004",
                "trial_id": EYLEA_TRIAL,
                "member_name": "Dr. James O'Brien",
                "role": MemberRole.ALTERNATE,
                "specialty": "Ophthalmology",
                "institution": "Wills Eye Hospital",
                "is_active": True,
                "appointment_date": now - timedelta(days=400),
                "term_end_date": now + timedelta(days=500),
                "conflict_of_interest_declared": True,
                "coi_details": None,
                "training_completed": True,
                "training_date": now - timedelta(days=395),
                "cases_reviewed": 12,
                "agreement_rate_pct": 92.0,
                "appointed_by": "EAC Chair",
                "notes": "Serves when primary members unavailable.",
                "created_at": now - timedelta(days=400),
            },
            {
                "id": "CM-005",
                "trial_id": DUPIXENT_TRIAL,
                "member_name": "Dr. Katherine Wells",
                "role": MemberRole.CHAIR,
                "specialty": "Dermatology",
                "institution": "Massachusetts General Hospital",
                "is_active": True,
                "appointment_date": now - timedelta(days=480),
                "term_end_date": now + timedelta(days=425),
                "conflict_of_interest_declared": True,
                "coi_details": "Prior consulting for sponsor; disclosed and approved.",
                "training_completed": True,
                "training_date": now - timedelta(days=475),
                "cases_reviewed": 36,
                "agreement_rate_pct": 95.0,
                "appointed_by": "Sponsor Medical Director",
                "notes": "Leads atopic dermatitis endpoint adjudication.",
                "created_at": now - timedelta(days=480),
            },
            {
                "id": "CM-006",
                "trial_id": DUPIXENT_TRIAL,
                "member_name": "Dr. Robert Tanaka",
                "role": MemberRole.VOTING_MEMBER,
                "specialty": "Allergology & Immunology",
                "institution": "Cleveland Clinic",
                "is_active": True,
                "appointment_date": now - timedelta(days=470),
                "term_end_date": now + timedelta(days=435),
                "conflict_of_interest_declared": True,
                "coi_details": None,
                "training_completed": True,
                "training_date": now - timedelta(days=465),
                "cases_reviewed": 34,
                "agreement_rate_pct": 90.5,
                "appointed_by": "Sponsor Medical Director",
                "notes": None,
                "created_at": now - timedelta(days=470),
            },
            {
                "id": "CM-007",
                "trial_id": DUPIXENT_TRIAL,
                "member_name": "Prof. Isabelle Fournier",
                "role": MemberRole.NON_VOTING_ADVISOR,
                "specialty": "Biostatistics",
                "institution": "INSERM, Paris",
                "is_active": True,
                "appointment_date": now - timedelta(days=460),
                "term_end_date": None,
                "conflict_of_interest_declared": True,
                "coi_details": None,
                "training_completed": True,
                "training_date": now - timedelta(days=455),
                "cases_reviewed": 30,
                "agreement_rate_pct": 0.0,
                "appointed_by": "Sponsor Biostatistics Lead",
                "notes": "Non-voting statistical advisor. Reviews case classification methodology.",
                "created_at": now - timedelta(days=460),
            },
            {
                "id": "CM-008",
                "trial_id": LIBTAYO_TRIAL,
                "member_name": "Dr. Samuel Okonkwo",
                "role": MemberRole.CHAIR,
                "specialty": "Medical Oncology",
                "institution": "Memorial Sloan Kettering",
                "is_active": True,
                "appointment_date": now - timedelta(days=420),
                "term_end_date": now + timedelta(days=485),
                "conflict_of_interest_declared": True,
                "coi_details": "Research grant from sponsor; disclosed per policy.",
                "training_completed": True,
                "training_date": now - timedelta(days=415),
                "cases_reviewed": 52,
                "agreement_rate_pct": 96.0,
                "appointed_by": "Sponsor Medical Director",
                "notes": "Oncology EAC chair. RECIST/iRECIST expert.",
                "created_at": now - timedelta(days=420),
            },
            {
                "id": "CM-009",
                "trial_id": LIBTAYO_TRIAL,
                "member_name": "Dr. Lisa Nakamura",
                "role": MemberRole.VOTING_MEMBER,
                "specialty": "Thoracic Oncology",
                "institution": "MD Anderson Cancer Center",
                "is_active": True,
                "appointment_date": now - timedelta(days=410),
                "term_end_date": now + timedelta(days=495),
                "conflict_of_interest_declared": True,
                "coi_details": None,
                "training_completed": True,
                "training_date": now - timedelta(days=405),
                "cases_reviewed": 49,
                "agreement_rate_pct": 93.5,
                "appointed_by": "Sponsor Medical Director",
                "notes": None,
                "created_at": now - timedelta(days=410),
            },
            {
                "id": "CM-010",
                "trial_id": LIBTAYO_TRIAL,
                "member_name": "Dr. Peter Johansson",
                "role": MemberRole.STATISTICIAN,
                "specialty": "Clinical Biostatistics",
                "institution": "Karolinska Institute",
                "is_active": True,
                "appointment_date": now - timedelta(days=400),
                "term_end_date": now + timedelta(days=505),
                "conflict_of_interest_declared": True,
                "coi_details": None,
                "training_completed": True,
                "training_date": now - timedelta(days=395),
                "cases_reviewed": 50,
                "agreement_rate_pct": 0.0,
                "appointed_by": "EAC Chair",
                "notes": "Provides statistical review of inter-rater agreement metrics.",
                "created_at": now - timedelta(days=400),
            },
            {
                "id": "CM-011",
                "trial_id": LIBTAYO_TRIAL,
                "member_name": "Dr. Angela Rossi",
                "role": MemberRole.COORDINATOR,
                "specialty": "Clinical Operations",
                "institution": "CRO - Parexel International",
                "is_active": True,
                "appointment_date": now - timedelta(days=390),
                "term_end_date": None,
                "conflict_of_interest_declared": True,
                "coi_details": None,
                "training_completed": True,
                "training_date": now - timedelta(days=385),
                "cases_reviewed": 0,
                "agreement_rate_pct": 0.0,
                "appointed_by": "Sponsor Clinical Operations",
                "notes": "Coordinates case package preparation and meeting logistics.",
                "created_at": now - timedelta(days=390),
            },
            {
                "id": "CM-012",
                "trial_id": DUPIXENT_TRIAL,
                "member_name": "Dr. William Park",
                "role": MemberRole.ALTERNATE,
                "specialty": "Pulmonology",
                "institution": "Mayo Clinic",
                "is_active": False,
                "appointment_date": now - timedelta(days=450),
                "term_end_date": now - timedelta(days=30),
                "conflict_of_interest_declared": True,
                "coi_details": None,
                "training_completed": True,
                "training_date": now - timedelta(days=445),
                "cases_reviewed": 8,
                "agreement_rate_pct": 87.5,
                "appointed_by": "EAC Chair",
                "notes": "Term expired. Not renewed due to scheduling conflicts.",
                "created_at": now - timedelta(days=450),
            },
        ]

        for m in members_data:
            self._committee_members[m["id"]] = CommitteeMember(**m)

        # --- 12 Case Reviews ---
        cases_data = [
            {
                "id": "CR-001",
                "trial_id": EYLEA_TRIAL,
                "case_number": "EYL-2025-001",
                "subject_id": "SUBJ-0042",
                "event_type": "Choroidal Neovascularization (CNV)",
                "event_date": now - timedelta(days=200),
                "status": CaseStatus.ADJUDICATED,
                "assigned_reviewers": ["CM-001", "CM-002", "CM-003"],
                "review_deadline": now - timedelta(days=180),
                "source_documents_received": True,
                "documents_adequate": True,
                "additional_info_requested": False,
                "meeting_id": "MTG-001",
                "review_round": 1,
                "submitted_by": "Site Investigator - Site 101",
                "notes": "Clear CNV on FA/OCT. Unanimously adjudicated.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "CR-002",
                "trial_id": EYLEA_TRIAL,
                "case_number": "EYL-2025-002",
                "subject_id": "SUBJ-0087",
                "event_type": "Geographic Atrophy Progression",
                "event_date": now - timedelta(days=180),
                "status": CaseStatus.ADJUDICATED,
                "assigned_reviewers": ["CM-001", "CM-002"],
                "review_deadline": now - timedelta(days=160),
                "source_documents_received": True,
                "documents_adequate": True,
                "additional_info_requested": True,
                "meeting_id": "MTG-002",
                "review_round": 2,
                "submitted_by": "Site Investigator - Site 103",
                "notes": "Additional OCT measurements requested. Confirmed on second review.",
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "CR-003",
                "trial_id": EYLEA_TRIAL,
                "case_number": "EYL-2025-003",
                "subject_id": "SUBJ-0121",
                "event_type": "Visual Acuity Loss >= 15 Letters",
                "event_date": now - timedelta(days=150),
                "status": CaseStatus.UNDER_REVIEW,
                "assigned_reviewers": ["CM-002", "CM-003"],
                "review_deadline": now - timedelta(days=130),
                "source_documents_received": True,
                "documents_adequate": False,
                "additional_info_requested": True,
                "meeting_id": None,
                "review_round": 1,
                "submitted_by": "Site Investigator - Site 107",
                "notes": "Awaiting BCVA re-test results. Potential measurement artifact.",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "CR-004",
                "trial_id": DUPIXENT_TRIAL,
                "case_number": "DUP-2025-001",
                "subject_id": "SUBJ-0205",
                "event_type": "EASI-75 Response Assessment",
                "event_date": now - timedelta(days=170),
                "status": CaseStatus.ADJUDICATED,
                "assigned_reviewers": ["CM-005", "CM-006"],
                "review_deadline": now - timedelta(days=150),
                "source_documents_received": True,
                "documents_adequate": True,
                "additional_info_requested": False,
                "meeting_id": "MTG-003",
                "review_round": 1,
                "submitted_by": "Site Investigator - Site 202",
                "notes": "Borderline EASI score. Photographic evidence reviewed.",
                "created_at": now - timedelta(days=170),
            },
            {
                "id": "CR-005",
                "trial_id": DUPIXENT_TRIAL,
                "case_number": "DUP-2025-002",
                "subject_id": "SUBJ-0218",
                "event_type": "IGA Response (0/1)",
                "event_date": now - timedelta(days=140),
                "status": CaseStatus.DEFERRED,
                "assigned_reviewers": ["CM-005", "CM-006"],
                "review_deadline": now - timedelta(days=120),
                "source_documents_received": True,
                "documents_adequate": False,
                "additional_info_requested": True,
                "meeting_id": None,
                "review_round": 1,
                "submitted_by": "Site Investigator - Site 205",
                "notes": "IGA scoring discrepancy between site and central reader. Deferred pending additional photographs.",
                "created_at": now - timedelta(days=140),
            },
            {
                "id": "CR-006",
                "trial_id": DUPIXENT_TRIAL,
                "case_number": "DUP-2025-003",
                "subject_id": "SUBJ-0234",
                "event_type": "Pruritus NRS Reduction >= 4",
                "event_date": now - timedelta(days=110),
                "status": CaseStatus.PENDING_REVIEW,
                "assigned_reviewers": ["CM-005"],
                "review_deadline": now - timedelta(days=90),
                "source_documents_received": True,
                "documents_adequate": True,
                "additional_info_requested": False,
                "meeting_id": None,
                "review_round": 1,
                "submitted_by": "Site Investigator - Site 208",
                "notes": "NRS diary data submitted. Awaiting committee meeting.",
                "created_at": now - timedelta(days=110),
            },
            {
                "id": "CR-007",
                "trial_id": LIBTAYO_TRIAL,
                "case_number": "LIB-2025-001",
                "subject_id": "SUBJ-0301",
                "event_type": "RECIST 1.1 Progression",
                "event_date": now - timedelta(days=160),
                "status": CaseStatus.ADJUDICATED,
                "assigned_reviewers": ["CM-008", "CM-009"],
                "review_deadline": now - timedelta(days=140),
                "source_documents_received": True,
                "documents_adequate": True,
                "additional_info_requested": False,
                "meeting_id": "MTG-004",
                "review_round": 1,
                "submitted_by": "Site Investigator - Site 301",
                "notes": "New lesion identified on CT. Confirmed progressive disease.",
                "created_at": now - timedelta(days=160),
            },
            {
                "id": "CR-008",
                "trial_id": LIBTAYO_TRIAL,
                "case_number": "LIB-2025-002",
                "subject_id": "SUBJ-0315",
                "event_type": "iRECIST Pseudoprogression",
                "event_date": now - timedelta(days=130),
                "status": CaseStatus.ADJUDICATED,
                "assigned_reviewers": ["CM-008", "CM-009"],
                "review_deadline": now - timedelta(days=110),
                "source_documents_received": True,
                "documents_adequate": True,
                "additional_info_requested": True,
                "meeting_id": "MTG-005",
                "review_round": 2,
                "submitted_by": "Site Investigator - Site 304",
                "notes": "Initial increase followed by regression. Confirmed pseudoprogression per iRECIST.",
                "created_at": now - timedelta(days=130),
            },
            {
                "id": "CR-009",
                "trial_id": LIBTAYO_TRIAL,
                "case_number": "LIB-2025-003",
                "subject_id": "SUBJ-0328",
                "event_type": "Complete Response (CR)",
                "event_date": now - timedelta(days=90),
                "status": CaseStatus.RETURNED_FOR_INFO,
                "assigned_reviewers": ["CM-008", "CM-009"],
                "review_deadline": now - timedelta(days=70),
                "source_documents_received": True,
                "documents_adequate": False,
                "additional_info_requested": True,
                "meeting_id": None,
                "review_round": 1,
                "submitted_by": "Site Investigator - Site 308",
                "notes": "Possible CR but baseline scan quality insufficient for comparison.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "CR-010",
                "trial_id": LIBTAYO_TRIAL,
                "case_number": "LIB-2025-004",
                "subject_id": "SUBJ-0342",
                "event_type": "Duration of Response Assessment",
                "event_date": now - timedelta(days=60),
                "status": CaseStatus.PENDING_REVIEW,
                "assigned_reviewers": [],
                "review_deadline": now - timedelta(days=40),
                "source_documents_received": False,
                "documents_adequate": False,
                "additional_info_requested": False,
                "meeting_id": None,
                "review_round": 1,
                "submitted_by": "Site Investigator - Site 310",
                "notes": "Awaiting source documents from site.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "CR-011",
                "trial_id": EYLEA_TRIAL,
                "case_number": "EYL-2025-004",
                "subject_id": "SUBJ-0155",
                "event_type": "Retinal Fluid Recurrence",
                "event_date": now - timedelta(days=45),
                "status": CaseStatus.CLOSED,
                "assigned_reviewers": ["CM-001", "CM-003"],
                "review_deadline": now - timedelta(days=25),
                "source_documents_received": True,
                "documents_adequate": True,
                "additional_info_requested": False,
                "meeting_id": "MTG-006",
                "review_round": 1,
                "submitted_by": "Site Investigator - Site 105",
                "notes": "Case closed. Not a primary endpoint event per charter definition.",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "CR-012",
                "trial_id": DUPIXENT_TRIAL,
                "case_number": "DUP-2025-004",
                "subject_id": "SUBJ-0251",
                "event_type": "Asthma Exacerbation (Severe)",
                "event_date": now - timedelta(days=20),
                "status": CaseStatus.UNDER_REVIEW,
                "assigned_reviewers": ["CM-005", "CM-006"],
                "review_deadline": now + timedelta(days=10),
                "source_documents_received": True,
                "documents_adequate": True,
                "additional_info_requested": False,
                "meeting_id": None,
                "review_round": 1,
                "submitted_by": "Site Investigator - Site 210",
                "notes": "Emergency department visit with systemic corticosteroid use. Under active review.",
                "created_at": now - timedelta(days=20),
            },
        ]

        for c in cases_data:
            self._case_reviews[c["id"]] = CaseReview(**c)

        # --- 12 Adjudication Results ---
        results_data = [
            {
                "id": "AR-001",
                "trial_id": EYLEA_TRIAL,
                "case_id": "CR-001",
                "outcome": AdjudicationOutcome.CONFIRMED,
                "adjudication_date": now - timedelta(days=185),
                "original_classification": "CNV - Active",
                "final_classification": "CNV - Active, Treatment Required",
                "votes_for": 3,
                "votes_against": 0,
                "votes_abstain": 0,
                "unanimous": True,
                "dissenting_opinions": [],
                "rationale": "FA demonstrates classic CNV with subretinal fluid. OCT confirms intraretinal fluid and subretinal hyperreflective material.",
                "supporting_evidence": ["FA imaging", "SD-OCT B-scans", "BCVA records"],
                "reviewed_by_chair": True,
                "finalized": True,
                "adjudicated_by": "EAC Panel (CM-001, CM-002, CM-003)",
                "notes": None,
                "created_at": now - timedelta(days=185),
            },
            {
                "id": "AR-002",
                "trial_id": EYLEA_TRIAL,
                "case_id": "CR-002",
                "outcome": AdjudicationOutcome.CONFIRMED,
                "adjudication_date": now - timedelta(days=155),
                "original_classification": "GA Progression",
                "final_classification": "GA Progression - Confirmed",
                "votes_for": 2,
                "votes_against": 0,
                "votes_abstain": 0,
                "unanimous": True,
                "dissenting_opinions": [],
                "rationale": "FAF imaging shows enlargement of atrophic area exceeding predefined threshold of 0.5 mm2 over 6 months.",
                "supporting_evidence": ["FAF imaging", "OCT en-face maps", "Area measurements"],
                "reviewed_by_chair": True,
                "finalized": True,
                "adjudicated_by": "EAC Panel (CM-001, CM-002)",
                "notes": "Required second round after additional OCT data.",
                "created_at": now - timedelta(days=155),
            },
            {
                "id": "AR-003",
                "trial_id": DUPIXENT_TRIAL,
                "case_id": "CR-004",
                "outcome": AdjudicationOutcome.NOT_CONFIRMED,
                "adjudication_date": now - timedelta(days=145),
                "original_classification": "EASI-75 Responder",
                "final_classification": "EASI-75 Non-Responder",
                "votes_for": 0,
                "votes_against": 2,
                "votes_abstain": 0,
                "unanimous": True,
                "dissenting_opinions": [],
                "rationale": "Re-scoring of EASI components using standardized photographs yields total EASI of 8.2, representing 72% improvement (below 75% threshold).",
                "supporting_evidence": ["Standardized photographs", "EASI worksheets", "Central reader assessment"],
                "reviewed_by_chair": True,
                "finalized": True,
                "adjudicated_by": "EAC Panel (CM-005, CM-006)",
                "notes": "Borderline case. Site scoring slightly overestimated improvement.",
                "created_at": now - timedelta(days=145),
            },
            {
                "id": "AR-004",
                "trial_id": LIBTAYO_TRIAL,
                "case_id": "CR-007",
                "outcome": AdjudicationOutcome.CONFIRMED,
                "adjudication_date": now - timedelta(days=135),
                "original_classification": "Progressive Disease (PD)",
                "final_classification": "Progressive Disease (PD) per RECIST 1.1",
                "votes_for": 2,
                "votes_against": 0,
                "votes_abstain": 0,
                "unanimous": True,
                "dissenting_opinions": [],
                "rationale": "New non-target lesion identified in liver. Target lesion sum increased by 22% from nadir.",
                "supporting_evidence": ["CT chest/abdomen/pelvis", "RECIST measurement worksheets", "Central radiology review"],
                "reviewed_by_chair": True,
                "finalized": True,
                "adjudicated_by": "EAC Panel (CM-008, CM-009)",
                "notes": None,
                "created_at": now - timedelta(days=135),
            },
            {
                "id": "AR-005",
                "trial_id": LIBTAYO_TRIAL,
                "case_id": "CR-008",
                "outcome": AdjudicationOutcome.RECLASSIFIED,
                "adjudication_date": now - timedelta(days=105),
                "original_classification": "Progressive Disease (PD)",
                "final_classification": "Pseudoprogression - Unconfirmed PD per iRECIST",
                "votes_for": 2,
                "votes_against": 0,
                "votes_abstain": 0,
                "unanimous": True,
                "dissenting_opinions": [],
                "rationale": "Initial target lesion increase followed by subsequent decrease at confirmatory scan. Pattern consistent with immunotherapy-related pseudoprogression.",
                "supporting_evidence": ["Serial CT imaging", "iRECIST worksheets", "Tumor kinetics analysis"],
                "reviewed_by_chair": True,
                "finalized": True,
                "adjudicated_by": "EAC Panel (CM-008, CM-009)",
                "notes": "Important for sensitivity analysis excluding pseudoprogression events.",
                "created_at": now - timedelta(days=105),
            },
            {
                "id": "AR-006",
                "trial_id": EYLEA_TRIAL,
                "case_id": "CR-011",
                "outcome": AdjudicationOutcome.NOT_CONFIRMED,
                "adjudication_date": now - timedelta(days=22),
                "original_classification": "Retinal Fluid Recurrence - Primary Endpoint",
                "final_classification": "Retinal Fluid Recurrence - Non-qualifying per Charter",
                "votes_for": 0,
                "votes_against": 2,
                "votes_abstain": 0,
                "unanimous": True,
                "dissenting_opinions": [],
                "rationale": "Fluid recurrence present but does not meet charter-defined threshold for primary endpoint (central subfield thickness increase < 50 microns).",
                "supporting_evidence": ["OCT central subfield measurements", "Charter section 4.2 criteria"],
                "reviewed_by_chair": True,
                "finalized": True,
                "adjudicated_by": "EAC Panel (CM-001, CM-003)",
                "notes": "Classified as secondary endpoint event per protocol.",
                "created_at": now - timedelta(days=22),
            },
            {
                "id": "AR-007",
                "trial_id": DUPIXENT_TRIAL,
                "case_id": "CR-005",
                "outcome": AdjudicationOutcome.INDETERMINATE,
                "adjudication_date": now - timedelta(days=100),
                "original_classification": "IGA 0/1 Responder",
                "final_classification": "Indeterminate - Insufficient Evidence",
                "votes_for": 1,
                "votes_against": 1,
                "votes_abstain": 0,
                "unanimous": False,
                "dissenting_opinions": ["Photographs insufficient quality for reliable IGA scoring at this visit."],
                "rationale": "Split decision due to photograph quality limitations. IGA scoring not reliable without standardized imaging conditions.",
                "supporting_evidence": ["Clinical photographs (suboptimal)", "IGA score sheets"],
                "reviewed_by_chair": True,
                "finalized": False,
                "adjudicated_by": "EAC Panel (CM-005, CM-006)",
                "notes": "Case deferred for re-photography. Will re-adjudicate at next meeting.",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "AR-008",
                "trial_id": LIBTAYO_TRIAL,
                "case_id": "CR-009",
                "outcome": AdjudicationOutcome.SPLIT_DECISION,
                "adjudication_date": now - timedelta(days=65),
                "original_classification": "Complete Response (CR)",
                "final_classification": "Partial Response (PR) - Split Decision",
                "votes_for": 1,
                "votes_against": 1,
                "votes_abstain": 0,
                "unanimous": False,
                "dissenting_opinions": ["Residual lymph node may represent post-treatment fibrosis rather than viable tumor. Should be classified as CR."],
                "rationale": "Majority view: residual lymph node > 10mm short axis precludes CR classification per RECIST 1.1. Classified as PR pending confirmatory scan.",
                "supporting_evidence": ["CT imaging", "RECIST worksheets", "PET-CT (requested)"],
                "reviewed_by_chair": True,
                "finalized": False,
                "adjudicated_by": "EAC Panel (CM-008, CM-009)",
                "notes": "PET-CT ordered for resolution. Third reviewer to be consulted if discordance persists.",
                "created_at": now - timedelta(days=65),
            },
            {
                "id": "AR-009",
                "trial_id": EYLEA_TRIAL,
                "case_id": "CR-003",
                "outcome": AdjudicationOutcome.INDETERMINATE,
                "adjudication_date": now - timedelta(days=120),
                "original_classification": "VA Loss >= 15 Letters",
                "final_classification": "Indeterminate - Awaiting Retest",
                "votes_for": 0,
                "votes_against": 0,
                "votes_abstain": 2,
                "unanimous": True,
                "dissenting_opinions": [],
                "rationale": "Both reviewers abstained due to suspected measurement artifact. Patient was unwell at time of BCVA assessment. Retest scheduled.",
                "supporting_evidence": ["BCVA refraction records", "Site investigator report"],
                "reviewed_by_chair": True,
                "finalized": False,
                "adjudicated_by": "EAC Panel (CM-002, CM-003)",
                "notes": "Retest appointment scheduled. Both reviewers will re-evaluate.",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "AR-010",
                "trial_id": LIBTAYO_TRIAL,
                "case_id": "CR-010",
                "outcome": AdjudicationOutcome.CONFIRMED,
                "adjudication_date": now - timedelta(days=35),
                "original_classification": "Durable Response >= 6 Months",
                "final_classification": "Durable Response - Confirmed",
                "votes_for": 2,
                "votes_against": 0,
                "votes_abstain": 0,
                "unanimous": True,
                "dissenting_opinions": [],
                "rationale": "Serial imaging confirms sustained PR for > 6 months from initial response date. Meets duration of response endpoint.",
                "supporting_evidence": ["Serial CT scans (4 timepoints)", "RECIST measurement history"],
                "reviewed_by_chair": True,
                "finalized": True,
                "adjudicated_by": "EAC Panel (CM-008, CM-009)",
                "notes": None,
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "AR-011",
                "trial_id": DUPIXENT_TRIAL,
                "case_id": "CR-006",
                "outcome": AdjudicationOutcome.CONFIRMED,
                "adjudication_date": now - timedelta(days=80),
                "original_classification": "Pruritus NRS Reduction >= 4",
                "final_classification": "Pruritus NRS Reduction >= 4 - Confirmed",
                "votes_for": 1,
                "votes_against": 0,
                "votes_abstain": 0,
                "unanimous": True,
                "dissenting_opinions": [],
                "rationale": "NRS diary data shows consistent 5-point reduction from baseline over 4-week assessment period.",
                "supporting_evidence": ["ePRO diary exports", "Baseline NRS scores"],
                "reviewed_by_chair": True,
                "finalized": True,
                "adjudicated_by": "EAC Panel (CM-005)",
                "notes": "Single reviewer per charter for ePRO-based endpoints.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "AR-012",
                "trial_id": LIBTAYO_TRIAL,
                "case_id": "CR-007",
                "outcome": AdjudicationOutcome.CONFIRMED,
                "adjudication_date": now - timedelta(days=10),
                "original_classification": "Overall Survival Event",
                "final_classification": "Overall Survival Event - Confirmed",
                "votes_for": 2,
                "votes_against": 0,
                "votes_abstain": 0,
                "unanimous": True,
                "dissenting_opinions": [],
                "rationale": "Death certificate and medical records confirm death due to disease progression.",
                "supporting_evidence": ["Death certificate", "Hospital discharge summary", "Investigator SAE report"],
                "reviewed_by_chair": True,
                "finalized": True,
                "adjudicated_by": "EAC Panel (CM-008, CM-009)",
                "notes": "Cause of death classification: disease-related.",
                "created_at": now - timedelta(days=10),
            },
        ]

        for r in results_data:
            self._adjudication_results[r["id"]] = AdjudicationResult(**r)

        # --- 10 Charter Records ---
        charters_data = [
            {
                "id": "CH-001",
                "trial_id": EYLEA_TRIAL,
                "version": "1.0",
                "status": CharterStatus.SUPERSEDED,
                "effective_date": now - timedelta(days=540),
                "review_date": now - timedelta(days=360),
                "endpoint_definitions": [
                    "CNV confirmed by FA and OCT",
                    "GA progression >= 0.5mm2 over 6 months",
                    "VA loss >= 15 ETDRS letters from baseline",
                ],
                "adjudication_criteria": [
                    "Independent review by >= 2 masked reviewers",
                    "Discordance resolved by chair",
                    "Majority vote for final classification",
                ],
                "quorum_requirement": 2,
                "voting_threshold_pct": 66.7,
                "blinding_procedures": "All case materials de-identified. Treatment arm and randomization code removed.",
                "document_requirements": ["FA images", "OCT scans", "BCVA records", "Site narrative"],
                "authored_by": "Dr. Eleanor Hartfield",
                "approved_by": "Sponsor Medical Director",
                "approval_date": now - timedelta(days=538),
                "notes": "Original charter. Superseded by v2.0.",
                "created_at": now - timedelta(days=540),
            },
            {
                "id": "CH-002",
                "trial_id": EYLEA_TRIAL,
                "version": "2.0",
                "status": CharterStatus.APPROVED,
                "effective_date": now - timedelta(days=360),
                "review_date": now - timedelta(days=180),
                "endpoint_definitions": [
                    "CNV confirmed by FA and OCT",
                    "GA progression >= 0.5mm2 over 6 months by FAF",
                    "VA loss >= 15 ETDRS letters (confirmed at 2 consecutive visits)",
                    "Retinal fluid recurrence (CST increase >= 50 microns)",
                ],
                "adjudication_criteria": [
                    "Independent review by >= 2 masked reviewers",
                    "Discordance resolved by chair casting vote",
                    "Simple majority for final classification",
                    "All cases reviewed within 20 business days",
                ],
                "quorum_requirement": 2,
                "voting_threshold_pct": 50.0,
                "blinding_procedures": "All case materials de-identified. Treatment arm, randomization code, and site identifier removed.",
                "document_requirements": ["FA images", "OCT scans", "FAF images", "BCVA records with refraction", "Site narrative"],
                "authored_by": "Dr. Eleanor Hartfield",
                "approved_by": "Sponsor Medical Director",
                "approval_date": now - timedelta(days=358),
                "notes": "Added FAF for GA endpoints. Strengthened VA endpoint with confirmatory visit.",
                "created_at": now - timedelta(days=360),
            },
            {
                "id": "CH-003",
                "trial_id": DUPIXENT_TRIAL,
                "version": "1.0",
                "status": CharterStatus.APPROVED,
                "effective_date": now - timedelta(days=480),
                "review_date": now - timedelta(days=240),
                "endpoint_definitions": [
                    "EASI-75 response (>= 75% improvement from baseline)",
                    "IGA 0/1 with >= 2-point improvement",
                    "Pruritus NRS reduction >= 4 from baseline",
                ],
                "adjudication_criteria": [
                    "Standardized photographs required for EASI/IGA",
                    "Central reader adjudicates photographic endpoints",
                    "ePRO-based endpoints reviewed by single committee member",
                    "Discordance between site and central: committee decides",
                ],
                "quorum_requirement": 2,
                "voting_threshold_pct": 66.7,
                "blinding_procedures": "De-identified case packages. No treatment allocation or visit-level dosing visible.",
                "document_requirements": ["Standardized photographs", "EASI worksheets", "IGA score sheets", "ePRO diary data", "Site narrative"],
                "authored_by": "Dr. Katherine Wells",
                "approved_by": "Sponsor Dermatology Lead",
                "approval_date": now - timedelta(days=478),
                "notes": None,
                "created_at": now - timedelta(days=480),
            },
            {
                "id": "CH-004",
                "trial_id": LIBTAYO_TRIAL,
                "version": "1.0",
                "status": CharterStatus.SUPERSEDED,
                "effective_date": now - timedelta(days=420),
                "review_date": now - timedelta(days=270),
                "endpoint_definitions": [
                    "RECIST 1.1 response assessment (CR, PR, SD, PD)",
                    "iRECIST for immune-related response",
                    "Duration of response (time from first response to PD/death)",
                ],
                "adjudication_criteria": [
                    "Blinded independent central review (BICR)",
                    "Two independent radiologists per scan",
                    "Discordance adjudicated by third reader",
                ],
                "quorum_requirement": 2,
                "voting_threshold_pct": 66.7,
                "blinding_procedures": "BICR readers masked to treatment, clinical data, and prior scan assessments.",
                "document_requirements": ["CT/MRI imaging (DICOM)", "RECIST measurement worksheets", "Prior scan data"],
                "authored_by": "Dr. Samuel Okonkwo",
                "approved_by": "Sponsor Oncology Director",
                "approval_date": now - timedelta(days=418),
                "notes": "Initial BICR charter for NSCLC trial.",
                "created_at": now - timedelta(days=420),
            },
            {
                "id": "CH-005",
                "trial_id": LIBTAYO_TRIAL,
                "version": "2.0",
                "status": CharterStatus.APPROVED,
                "effective_date": now - timedelta(days=270),
                "review_date": now - timedelta(days=90),
                "endpoint_definitions": [
                    "RECIST 1.1 response assessment (CR, PR, SD, PD)",
                    "iRECIST for immune-related response including pseudoprogression",
                    "Duration of response (time from first response to confirmed PD/death)",
                    "Overall survival event (death from any cause)",
                ],
                "adjudication_criteria": [
                    "BICR with two independent radiologists",
                    "Third reader for discordance (binding vote)",
                    "Pseudoprogression requires confirmatory scan at >= 4 weeks",
                    "OS events verified against source documents",
                ],
                "quorum_requirement": 2,
                "voting_threshold_pct": 66.7,
                "blinding_procedures": "Full BICR blinding. Readers masked to treatment, clinical outcomes, and prior reader assessments.",
                "document_requirements": ["CT/MRI (DICOM)", "RECIST/iRECIST worksheets", "Death certificates (OS events)", "SAE reports"],
                "authored_by": "Dr. Samuel Okonkwo",
                "approved_by": "Sponsor Oncology Director",
                "approval_date": now - timedelta(days=268),
                "notes": "Added iRECIST pseudoprogression criteria and OS event verification.",
                "created_at": now - timedelta(days=270),
            },
            {
                "id": "CH-006",
                "trial_id": EYLEA_TRIAL,
                "version": "2.1",
                "status": CharterStatus.UNDER_REVIEW,
                "effective_date": None,
                "review_date": now - timedelta(days=10),
                "endpoint_definitions": [
                    "CNV confirmed by FA and OCT",
                    "GA progression >= 0.5mm2 over 6 months by FAF",
                    "VA loss >= 15 ETDRS letters (confirmed at 2 consecutive visits)",
                    "Retinal fluid recurrence (CST increase >= 50 microns)",
                    "AI-assisted OCT fluid quantification (exploratory)",
                ],
                "adjudication_criteria": [
                    "Independent review by >= 2 masked reviewers",
                    "AI-assisted measurements as supportive data only",
                    "Discordance resolved by chair casting vote",
                ],
                "quorum_requirement": 2,
                "voting_threshold_pct": 50.0,
                "blinding_procedures": "All case materials de-identified. AI outputs blinded to treatment assignment.",
                "document_requirements": ["FA images", "OCT scans", "FAF images", "BCVA records", "AI quantification report"],
                "authored_by": "Dr. Eleanor Hartfield",
                "approved_by": None,
                "approval_date": None,
                "notes": "Amendment to add AI-assisted OCT fluid quantification as exploratory endpoint.",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "CH-007",
                "trial_id": DUPIXENT_TRIAL,
                "version": "1.1",
                "status": CharterStatus.AMENDED,
                "effective_date": now - timedelta(days=240),
                "review_date": now - timedelta(days=60),
                "endpoint_definitions": [
                    "EASI-75 response (>= 75% improvement from baseline)",
                    "IGA 0/1 with >= 2-point improvement",
                    "Pruritus NRS reduction >= 4 from baseline",
                    "Asthma exacerbation (severe, requiring systemic corticosteroids or ED visit)",
                ],
                "adjudication_criteria": [
                    "Standardized photographs required for EASI/IGA",
                    "Central reader adjudicates photographic endpoints",
                    "ePRO-based endpoints reviewed by single committee member",
                    "Asthma exacerbations reviewed by pulmonary specialist",
                ],
                "quorum_requirement": 2,
                "voting_threshold_pct": 66.7,
                "blinding_procedures": "De-identified case packages with all treatment identifiers removed.",
                "document_requirements": ["Standardized photographs", "EASI/IGA worksheets", "ePRO diary data", "ED records (exacerbations)", "Site narrative"],
                "authored_by": "Dr. Katherine Wells",
                "approved_by": "Sponsor Dermatology Lead",
                "approval_date": now - timedelta(days=238),
                "notes": "Amendment to add asthma exacerbation endpoint adjudication.",
                "created_at": now - timedelta(days=240),
            },
            {
                "id": "CH-008",
                "trial_id": LIBTAYO_TRIAL,
                "version": "2.1",
                "status": CharterStatus.DRAFT,
                "effective_date": None,
                "review_date": None,
                "endpoint_definitions": [
                    "RECIST 1.1 response assessment",
                    "iRECIST for immune-related response",
                    "Duration of response",
                    "Overall survival event",
                    "Circulating tumor DNA (ctDNA) molecular response (exploratory)",
                ],
                "adjudication_criteria": [
                    "BICR with two independent radiologists",
                    "ctDNA results reviewed by molecular tumor board",
                ],
                "quorum_requirement": 3,
                "voting_threshold_pct": 66.7,
                "blinding_procedures": "Full BICR blinding. ctDNA results compartmentalized from imaging data.",
                "document_requirements": ["CT/MRI (DICOM)", "RECIST/iRECIST worksheets", "ctDNA assay reports", "Death certificates"],
                "authored_by": "Dr. Samuel Okonkwo",
                "approved_by": None,
                "approval_date": None,
                "notes": "Draft amendment for ctDNA molecular response exploratory endpoint.",
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "CH-009",
                "trial_id": EYLEA_TRIAL,
                "version": "1.1",
                "status": CharterStatus.SUPERSEDED,
                "effective_date": now - timedelta(days=450),
                "review_date": now - timedelta(days=360),
                "endpoint_definitions": [
                    "CNV confirmed by FA and OCT",
                    "GA progression >= 0.5mm2 over 6 months",
                    "VA loss >= 15 ETDRS letters from baseline",
                ],
                "adjudication_criteria": [
                    "Independent review by >= 2 masked reviewers",
                    "Discordance resolved by chair",
                ],
                "quorum_requirement": 2,
                "voting_threshold_pct": 66.7,
                "blinding_procedures": "All case materials de-identified.",
                "document_requirements": ["FA images", "OCT scans", "BCVA records", "Site narrative"],
                "authored_by": "Dr. Eleanor Hartfield",
                "approved_by": "Sponsor Medical Director",
                "approval_date": now - timedelta(days=448),
                "notes": "Minor amendment clarifying discordance resolution process. Superseded by v2.0.",
                "created_at": now - timedelta(days=450),
            },
            {
                "id": "CH-010",
                "trial_id": DUPIXENT_TRIAL,
                "version": "2.0",
                "status": CharterStatus.DRAFT,
                "effective_date": None,
                "review_date": None,
                "endpoint_definitions": [
                    "EASI-75 response",
                    "EASI-90 response (new)",
                    "IGA 0/1 with >= 2-point improvement",
                    "Pruritus NRS reduction >= 4",
                    "DLQI improvement >= 4 (new)",
                ],
                "adjudication_criteria": [
                    "Standardized photographs for EASI/IGA",
                    "DLQI reviewed against source ePRO data",
                    "Central reader for photographic endpoints",
                ],
                "quorum_requirement": 2,
                "voting_threshold_pct": 66.7,
                "blinding_procedures": "De-identified case packages.",
                "document_requirements": ["Photographs", "EASI/IGA worksheets", "ePRO data", "DLQI questionnaires"],
                "authored_by": "Dr. Katherine Wells",
                "approved_by": None,
                "approval_date": None,
                "notes": "Draft for v2.0 adding EASI-90 and DLQI endpoints.",
                "created_at": now - timedelta(days=3),
            },
        ]

        for ch in charters_data:
            self._charter_records[ch["id"]] = CharterRecord(**ch)

        # --- 12 Blinding Compliance Records ---
        blinding_data = [
            {
                "id": "BC-001",
                "trial_id": EYLEA_TRIAL,
                "assessment_date": now - timedelta(days=500),
                "blinding_status": BlindingStatus.MAINTAINED,
                "case_id": None,
                "member_id": None,
                "breach_type": None,
                "breach_description": None,
                "breach_source": None,
                "impact_assessment": None,
                "corrective_action": None,
                "reported_to_sponsor": False,
                "reported_to_irb": False,
                "resolution_date": None,
                "assessed_by": "EAC Coordinator",
                "notes": "Quarterly blinding assessment. No concerns identified.",
                "created_at": now - timedelta(days=500),
            },
            {
                "id": "BC-002",
                "trial_id": EYLEA_TRIAL,
                "assessment_date": now - timedelta(days=400),
                "blinding_status": BlindingStatus.MAINTAINED,
                "case_id": None,
                "member_id": None,
                "breach_type": None,
                "breach_description": None,
                "breach_source": None,
                "impact_assessment": None,
                "corrective_action": None,
                "reported_to_sponsor": False,
                "reported_to_irb": False,
                "resolution_date": None,
                "assessed_by": "EAC Coordinator",
                "notes": "Quarterly blinding assessment. All procedures compliant.",
                "created_at": now - timedelta(days=400),
            },
            {
                "id": "BC-003",
                "trial_id": EYLEA_TRIAL,
                "assessment_date": now - timedelta(days=300),
                "blinding_status": BlindingStatus.POTENTIAL_BREACH,
                "case_id": "CR-002",
                "member_id": "CM-002",
                "breach_type": "Document Redaction Failure",
                "breach_description": "Case package for CR-002 contained an unredacted lab report with treatment-specific monitoring values.",
                "breach_source": "Case package preparation",
                "impact_assessment": "Low impact. Lab values non-specific to treatment allocation. Member reports no unblinding.",
                "corrective_action": "Enhanced QC process for document redaction. Second reviewer added for all case packages.",
                "reported_to_sponsor": True,
                "reported_to_irb": False,
                "resolution_date": now - timedelta(days=290),
                "assessed_by": "Dr. Eleanor Hartfield",
                "notes": "Member confirmed no treatment identification was possible from the lab report.",
                "created_at": now - timedelta(days=300),
            },
            {
                "id": "BC-004",
                "trial_id": DUPIXENT_TRIAL,
                "assessment_date": now - timedelta(days=350),
                "blinding_status": BlindingStatus.MAINTAINED,
                "case_id": None,
                "member_id": None,
                "breach_type": None,
                "breach_description": None,
                "breach_source": None,
                "impact_assessment": None,
                "corrective_action": None,
                "reported_to_sponsor": False,
                "reported_to_irb": False,
                "resolution_date": None,
                "assessed_by": "EAC Coordinator",
                "notes": "Semi-annual blinding review. All procedures compliant.",
                "created_at": now - timedelta(days=350),
            },
            {
                "id": "BC-005",
                "trial_id": DUPIXENT_TRIAL,
                "assessment_date": now - timedelta(days=200),
                "blinding_status": BlindingStatus.CONFIRMED_BREACH,
                "case_id": "CR-004",
                "member_id": "CM-006",
                "breach_type": "Verbal Disclosure",
                "breach_description": "During a case discussion, site investigator inadvertently mentioned patient was on active treatment during a query call.",
                "breach_source": "Site investigator query call",
                "impact_assessment": "Moderate impact. One committee member (CM-006) potentially unblinded for case CR-004.",
                "corrective_action": "CM-006 recused from CR-004 adjudication. Alternate reviewer assigned. Training reinforced with site.",
                "reported_to_sponsor": True,
                "reported_to_irb": True,
                "resolution_date": now - timedelta(days=190),
                "assessed_by": "Dr. Katherine Wells",
                "notes": "Alternate reviewer completed adjudication. Original assessment by CM-006 excluded from analysis.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "BC-006",
                "trial_id": DUPIXENT_TRIAL,
                "assessment_date": now - timedelta(days=100),
                "blinding_status": BlindingStatus.MAINTAINED,
                "case_id": None,
                "member_id": None,
                "breach_type": None,
                "breach_description": None,
                "breach_source": None,
                "impact_assessment": None,
                "corrective_action": None,
                "reported_to_sponsor": False,
                "reported_to_irb": False,
                "resolution_date": None,
                "assessed_by": "EAC Coordinator",
                "notes": "Post-breach quarterly assessment. Enhanced procedures verified effective.",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "BC-007",
                "trial_id": LIBTAYO_TRIAL,
                "assessment_date": now - timedelta(days=380),
                "blinding_status": BlindingStatus.MAINTAINED,
                "case_id": None,
                "member_id": None,
                "breach_type": None,
                "breach_description": None,
                "breach_source": None,
                "impact_assessment": None,
                "corrective_action": None,
                "reported_to_sponsor": False,
                "reported_to_irb": False,
                "resolution_date": None,
                "assessed_by": "EAC Coordinator",
                "notes": "Quarterly BICR blinding verification. All readers confirmed blinded.",
                "created_at": now - timedelta(days=380),
            },
            {
                "id": "BC-008",
                "trial_id": LIBTAYO_TRIAL,
                "assessment_date": now - timedelta(days=250),
                "blinding_status": BlindingStatus.UNDER_INVESTIGATION,
                "case_id": "CR-007",
                "member_id": "CM-009",
                "breach_type": "Imaging Metadata",
                "breach_description": "DICOM header contained institution name that could identify treatment center type (cancer center vs. community).",
                "breach_source": "DICOM imaging metadata",
                "impact_assessment": "Under investigation. Assessing whether institution type correlates with treatment arm allocation.",
                "corrective_action": "DICOM scrubbing enhanced to remove all institutional identifiers. Retroactive audit of all prior cases initiated.",
                "reported_to_sponsor": True,
                "reported_to_irb": False,
                "resolution_date": None,
                "assessed_by": "Dr. Samuel Okonkwo",
                "notes": "Investigation pending completion of retroactive DICOM audit.",
                "created_at": now - timedelta(days=250),
            },
            {
                "id": "BC-009",
                "trial_id": LIBTAYO_TRIAL,
                "assessment_date": now - timedelta(days=180),
                "blinding_status": BlindingStatus.MAINTAINED,
                "case_id": None,
                "member_id": None,
                "breach_type": None,
                "breach_description": None,
                "breach_source": None,
                "impact_assessment": "DICOM audit completed. No systematic correlation between institution and treatment arm.",
                "corrective_action": None,
                "reported_to_sponsor": True,
                "reported_to_irb": False,
                "resolution_date": now - timedelta(days=180),
                "assessed_by": "Dr. Samuel Okonkwo",
                "notes": "DICOM metadata issue resolved. No actual unblinding confirmed. Enhanced scrubbing in place.",
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "BC-010",
                "trial_id": LIBTAYO_TRIAL,
                "assessment_date": now - timedelta(days=60),
                "blinding_status": BlindingStatus.NOT_APPLICABLE,
                "case_id": "CR-010",
                "member_id": None,
                "breach_type": None,
                "breach_description": None,
                "breach_source": None,
                "impact_assessment": "OS events do not require blinded review per charter v2.0.",
                "corrective_action": None,
                "reported_to_sponsor": False,
                "reported_to_irb": False,
                "resolution_date": None,
                "assessed_by": "EAC Coordinator",
                "notes": "Duration of response assessment based on confirmed imaging timepoints. Blinding N/A for this endpoint.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "BC-011",
                "trial_id": EYLEA_TRIAL,
                "assessment_date": now - timedelta(days=30),
                "blinding_status": BlindingStatus.MAINTAINED,
                "case_id": None,
                "member_id": None,
                "breach_type": None,
                "breach_description": None,
                "breach_source": None,
                "impact_assessment": None,
                "corrective_action": None,
                "reported_to_sponsor": False,
                "reported_to_irb": False,
                "resolution_date": None,
                "assessed_by": "EAC Coordinator",
                "notes": "Most recent quarterly assessment. All procedures compliant.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "BC-012",
                "trial_id": DUPIXENT_TRIAL,
                "assessment_date": now - timedelta(days=15),
                "blinding_status": BlindingStatus.POTENTIAL_BREACH,
                "case_id": "CR-012",
                "member_id": "CM-005",
                "breach_type": "Clinical Context",
                "breach_description": "Asthma exacerbation case materials include details about concomitant biologic therapy modification that could suggest treatment arm.",
                "breach_source": "Case narrative from site",
                "impact_assessment": "Under review. Assessing whether concomitant therapy changes correlate with treatment allocation.",
                "corrective_action": "Case narrative to be re-redacted. CM-005 assessment suspended pending review.",
                "reported_to_sponsor": True,
                "reported_to_irb": False,
                "resolution_date": None,
                "assessed_by": "Dr. Katherine Wells",
                "notes": "Pending resolution. Enhanced redaction guidance issued to sites.",
                "created_at": now - timedelta(days=15),
            },
        ]

        for b in blinding_data:
            self._blinding_compliance[b["id"]] = BlindingCompliance(**b)

    # ------------------------------------------------------------------
    # Committee Members
    # ------------------------------------------------------------------

    def list_committee_members(
        self,
        *,
        trial_id: str | None = None,
        role: MemberRole | None = None,
        is_active: bool | None = None,
    ) -> list[CommitteeMember]:
        """List committee members with optional filters."""
        with self._lock:
            result = list(self._committee_members.values())

        if trial_id is not None:
            result = [m for m in result if m.trial_id == trial_id]
        if role is not None:
            result = [m for m in result if m.role == role]
        if is_active is not None:
            result = [m for m in result if m.is_active == is_active]

        return sorted(result, key=lambda m: m.appointment_date, reverse=True)

    def get_committee_member(self, member_id: str) -> CommitteeMember | None:
        """Get a single committee member by ID."""
        with self._lock:
            return self._committee_members.get(member_id)

    def create_committee_member(self, payload: CommitteeMemberCreate) -> CommitteeMember:
        """Create a new committee member."""
        now = datetime.now(timezone.utc)
        member_id = f"CM-{uuid4().hex[:8].upper()}"
        member = CommitteeMember(
            id=member_id,
            trial_id=payload.trial_id,
            member_name=payload.member_name,
            role=payload.role,
            specialty=payload.specialty,
            institution=payload.institution,
            is_active=True,
            appointment_date=now,
            term_end_date=None,
            conflict_of_interest_declared=True,
            coi_details=None,
            training_completed=False,
            training_date=None,
            cases_reviewed=0,
            agreement_rate_pct=0.0,
            appointed_by=payload.appointed_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._committee_members[member_id] = member
        logger.info("Created committee member %s for trial %s", member_id, payload.trial_id)
        return member

    def update_committee_member(
        self, member_id: str, payload: CommitteeMemberUpdate
    ) -> CommitteeMember | None:
        """Update an existing committee member."""
        with self._lock:
            existing = self._committee_members.get(member_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CommitteeMember(**data)
            self._committee_members[member_id] = updated
        return updated

    def delete_committee_member(self, member_id: str) -> bool:
        """Delete a committee member. Returns True if deleted."""
        with self._lock:
            if member_id in self._committee_members:
                del self._committee_members[member_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Case Reviews
    # ------------------------------------------------------------------

    def list_case_reviews(
        self,
        *,
        trial_id: str | None = None,
        status: CaseStatus | None = None,
    ) -> list[CaseReview]:
        """List case reviews with optional filters."""
        with self._lock:
            result = list(self._case_reviews.values())

        if trial_id is not None:
            result = [c for c in result if c.trial_id == trial_id]
        if status is not None:
            result = [c for c in result if c.status == status]

        return sorted(result, key=lambda c: c.event_date, reverse=True)

    def get_case_review(self, case_id: str) -> CaseReview | None:
        """Get a single case review by ID."""
        with self._lock:
            return self._case_reviews.get(case_id)

    def create_case_review(self, payload: CaseReviewCreate) -> CaseReview:
        """Create a new case review."""
        now = datetime.now(timezone.utc)
        case_id = f"CR-{uuid4().hex[:8].upper()}"
        case = CaseReview(
            id=case_id,
            trial_id=payload.trial_id,
            case_number=payload.case_number,
            subject_id=payload.subject_id,
            event_type=payload.event_type,
            event_date=payload.event_date,
            status=CaseStatus.PENDING_REVIEW,
            assigned_reviewers=payload.assigned_reviewers,
            review_deadline=None,
            source_documents_received=False,
            documents_adequate=False,
            additional_info_requested=False,
            meeting_id=None,
            review_round=1,
            submitted_by=payload.submitted_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._case_reviews[case_id] = case
        logger.info("Created case review %s for trial %s", case_id, payload.trial_id)
        return case

    def update_case_review(
        self, case_id: str, payload: CaseReviewUpdate
    ) -> CaseReview | None:
        """Update an existing case review."""
        with self._lock:
            existing = self._case_reviews.get(case_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CaseReview(**data)
            self._case_reviews[case_id] = updated
        return updated

    def delete_case_review(self, case_id: str) -> bool:
        """Delete a case review. Returns True if deleted."""
        with self._lock:
            if case_id in self._case_reviews:
                del self._case_reviews[case_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Adjudication Results
    # ------------------------------------------------------------------

    def list_adjudication_results(
        self,
        *,
        trial_id: str | None = None,
        outcome: AdjudicationOutcome | None = None,
    ) -> list[AdjudicationResult]:
        """List adjudication results with optional filters."""
        with self._lock:
            result = list(self._adjudication_results.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if outcome is not None:
            result = [r for r in result if r.outcome == outcome]

        return sorted(result, key=lambda r: r.adjudication_date, reverse=True)

    def get_adjudication_result(self, result_id: str) -> AdjudicationResult | None:
        """Get a single adjudication result by ID."""
        with self._lock:
            return self._adjudication_results.get(result_id)

    def create_adjudication_result(self, payload: AdjudicationResultCreate) -> AdjudicationResult:
        """Create a new adjudication result."""
        now = datetime.now(timezone.utc)
        result_id = f"AR-{uuid4().hex[:8].upper()}"
        adj_result = AdjudicationResult(
            id=result_id,
            trial_id=payload.trial_id,
            case_id=payload.case_id,
            outcome=payload.outcome,
            adjudication_date=now,
            original_classification=payload.original_classification,
            final_classification=payload.final_classification,
            votes_for=0,
            votes_against=0,
            votes_abstain=0,
            unanimous=False,
            dissenting_opinions=[],
            rationale=payload.rationale,
            supporting_evidence=[],
            reviewed_by_chair=False,
            finalized=False,
            adjudicated_by=payload.adjudicated_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._adjudication_results[result_id] = adj_result
        logger.info("Created adjudication result %s for trial %s", result_id, payload.trial_id)
        return adj_result

    def update_adjudication_result(
        self, result_id: str, payload: AdjudicationResultUpdate
    ) -> AdjudicationResult | None:
        """Update an existing adjudication result."""
        with self._lock:
            existing = self._adjudication_results.get(result_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = AdjudicationResult(**data)
            self._adjudication_results[result_id] = updated
        return updated

    def delete_adjudication_result(self, result_id: str) -> bool:
        """Delete an adjudication result. Returns True if deleted."""
        with self._lock:
            if result_id in self._adjudication_results:
                del self._adjudication_results[result_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Charter Records
    # ------------------------------------------------------------------

    def list_charter_records(
        self,
        *,
        trial_id: str | None = None,
        status: CharterStatus | None = None,
    ) -> list[CharterRecord]:
        """List charter records with optional filters."""
        with self._lock:
            result = list(self._charter_records.values())

        if trial_id is not None:
            result = [ch for ch in result if ch.trial_id == trial_id]
        if status is not None:
            result = [ch for ch in result if ch.status == status]

        return sorted(result, key=lambda ch: ch.created_at, reverse=True)

    def get_charter_record(self, charter_id: str) -> CharterRecord | None:
        """Get a single charter record by ID."""
        with self._lock:
            return self._charter_records.get(charter_id)

    def create_charter_record(self, payload: CharterRecordCreate) -> CharterRecord:
        """Create a new charter record."""
        now = datetime.now(timezone.utc)
        charter_id = f"CH-{uuid4().hex[:8].upper()}"
        charter = CharterRecord(
            id=charter_id,
            trial_id=payload.trial_id,
            version=payload.version,
            status=CharterStatus.DRAFT,
            effective_date=None,
            review_date=None,
            endpoint_definitions=payload.endpoint_definitions,
            adjudication_criteria=[],
            quorum_requirement=payload.quorum_requirement,
            voting_threshold_pct=66.7,
            blinding_procedures=None,
            document_requirements=[],
            authored_by=payload.authored_by,
            approved_by=None,
            approval_date=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._charter_records[charter_id] = charter
        logger.info("Created charter record %s for trial %s", charter_id, payload.trial_id)
        return charter

    def update_charter_record(
        self, charter_id: str, payload: CharterRecordUpdate
    ) -> CharterRecord | None:
        """Update an existing charter record."""
        with self._lock:
            existing = self._charter_records.get(charter_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CharterRecord(**data)
            self._charter_records[charter_id] = updated
        return updated

    def delete_charter_record(self, charter_id: str) -> bool:
        """Delete a charter record. Returns True if deleted."""
        with self._lock:
            if charter_id in self._charter_records:
                del self._charter_records[charter_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Blinding Compliance
    # ------------------------------------------------------------------

    def list_blinding_compliance(
        self,
        *,
        trial_id: str | None = None,
        blinding_status: BlindingStatus | None = None,
    ) -> list[BlindingCompliance]:
        """List blinding compliance records with optional filters."""
        with self._lock:
            result = list(self._blinding_compliance.values())

        if trial_id is not None:
            result = [b for b in result if b.trial_id == trial_id]
        if blinding_status is not None:
            result = [b for b in result if b.blinding_status == blinding_status]

        return sorted(result, key=lambda b: b.assessment_date, reverse=True)

    def get_blinding_compliance(self, compliance_id: str) -> BlindingCompliance | None:
        """Get a single blinding compliance record by ID."""
        with self._lock:
            return self._blinding_compliance.get(compliance_id)

    def create_blinding_compliance(self, payload: BlindingComplianceCreate) -> BlindingCompliance:
        """Create a new blinding compliance record."""
        now = datetime.now(timezone.utc)
        compliance_id = f"BC-{uuid4().hex[:8].upper()}"
        compliance = BlindingCompliance(
            id=compliance_id,
            trial_id=payload.trial_id,
            assessment_date=now,
            blinding_status=payload.blinding_status,
            case_id=payload.case_id,
            member_id=payload.member_id,
            breach_type=None,
            breach_description=None,
            breach_source=None,
            impact_assessment=None,
            corrective_action=None,
            reported_to_sponsor=False,
            reported_to_irb=False,
            resolution_date=None,
            assessed_by=payload.assessed_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._blinding_compliance[compliance_id] = compliance
        logger.info("Created blinding compliance %s for trial %s", compliance_id, payload.trial_id)
        return compliance

    def update_blinding_compliance(
        self, compliance_id: str, payload: BlindingComplianceUpdate
    ) -> BlindingCompliance | None:
        """Update an existing blinding compliance record."""
        with self._lock:
            existing = self._blinding_compliance.get(compliance_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = BlindingCompliance(**data)
            self._blinding_compliance[compliance_id] = updated
        return updated

    def delete_blinding_compliance(self, compliance_id: str) -> bool:
        """Delete a blinding compliance record. Returns True if deleted."""
        with self._lock:
            if compliance_id in self._blinding_compliance:
                del self._blinding_compliance[compliance_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> EndpointAdjudicationMetrics:
        """Compute aggregated endpoint adjudication committee metrics."""
        with self._lock:
            members = list(self._committee_members.values())
            cases = list(self._case_reviews.values())
            adjudications = list(self._adjudication_results.values())
            charters = list(self._charter_records.values())
            blinding = list(self._blinding_compliance.values())

        # Members by role
        members_by_role: dict[str, int] = {}
        for m in members:
            key = m.role.value
            members_by_role[key] = members_by_role.get(key, 0) + 1

        # Active members
        active_members = sum(1 for m in members if m.is_active)

        # Cases by status
        cases_by_status: dict[str, int] = {}
        for c in cases:
            key = c.status.value
            cases_by_status[key] = cases_by_status.get(key, 0) + 1

        # Adjudications by outcome
        adjudications_by_outcome: dict[str, int] = {}
        for a in adjudications:
            key = a.outcome.value
            adjudications_by_outcome[key] = adjudications_by_outcome.get(key, 0) + 1

        # Unanimous decisions
        unanimous_decisions = sum(1 for a in adjudications if a.unanimous)

        # Charters by status
        charters_by_status: dict[str, int] = {}
        for ch in charters:
            key = ch.status.value
            charters_by_status[key] = charters_by_status.get(key, 0) + 1

        # Blinding by status
        blinding_by_status: dict[str, int] = {}
        for b in blinding:
            key = b.blinding_status.value
            blinding_by_status[key] = blinding_by_status.get(key, 0) + 1

        # Confirmed breaches
        confirmed_breaches = sum(
            1 for b in blinding if b.blinding_status == BlindingStatus.CONFIRMED_BREACH
        )

        return EndpointAdjudicationMetrics(
            total_members=len(members),
            active_members=active_members,
            members_by_role=members_by_role,
            total_cases=len(cases),
            cases_by_status=cases_by_status,
            total_adjudications=len(adjudications),
            adjudications_by_outcome=adjudications_by_outcome,
            unanimous_decisions=unanimous_decisions,
            total_charters=len(charters),
            charters_by_status=charters_by_status,
            total_blinding_records=len(blinding),
            blinding_by_status=blinding_by_status,
            confirmed_breaches=confirmed_breaches,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: EndpointAdjudicationCommitteeService | None = None
_instance_lock = threading.Lock()


def get_endpoint_adjudication_committee_service() -> EndpointAdjudicationCommitteeService:
    """Return the singleton EndpointAdjudicationCommitteeService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = EndpointAdjudicationCommitteeService()
    return _instance


def reset_endpoint_adjudication_committee_service() -> EndpointAdjudicationCommitteeService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = EndpointAdjudicationCommitteeService()
    return _instance
