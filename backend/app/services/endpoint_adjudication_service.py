"""Clinical Endpoint Adjudication Committee (CEAC) Management Service (CLINICAL-20).

Manages endpoint adjudication operations including committee definitions, member
management, dual-reviewer event assignment, blinded review workflow, reviewer
assessments with confidence levels, consensus tracking, inter-rater agreement
(Cohen's kappa), committee meetings, turnaround time tracking, and metrics.

Usage:
    from app.services.endpoint_adjudication_service import (
        get_adjudication_service,
    )

    svc = get_adjudication_service()
    events = svc.list_events()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import math
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.endpoint_adjudication import (
    AdjudicationCommittee,
    AdjudicationEvent,
    AdjudicationMeeting,
    AdjudicationMetrics,
    AdjudicationStatus,
    AdjudicatorRole,
    AssessmentCreate,
    BlindingStatus,
    CommitteeCreate,
    CommitteeMember,
    CommitteeUpdate,
    ConfidenceLevel,
    EndpointType,
    EventClassification,
    EventCreate,
    EventUpdate,
    MeetingCreate,
    MemberCreate,
    MemberUpdate,
    ReviewerAssessment,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class AdjudicationService:
    """In-memory Clinical Endpoint Adjudication Committee engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._committees: dict[str, AdjudicationCommittee] = {}
        self._members: dict[str, CommitteeMember] = {}
        self._events: dict[str, AdjudicationEvent] = {}
        self._assessments: dict[str, ReviewerAssessment] = {}
        self._meetings: dict[str, AdjudicationMeeting] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic adjudication data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 15 Committee Members ---
        members_data = [
            {"id": "MBR-001", "name": "Dr. Elizabeth Chen", "specialty": "Ophthalmology", "institution": "Bascom Palmer Eye Institute", "role": AdjudicatorRole.CHAIR, "conflict_of_interest_disclosed": True, "training_completed": True},
            {"id": "MBR-002", "name": "Dr. James Rodriguez", "specialty": "Retinal Surgery", "institution": "Wills Eye Hospital", "role": AdjudicatorRole.PRIMARY_REVIEWER, "conflict_of_interest_disclosed": True, "training_completed": True},
            {"id": "MBR-003", "name": "Dr. Sarah Thompson", "specialty": "Ophthalmology", "institution": "Moorfields Eye Hospital", "role": AdjudicatorRole.SECONDARY_REVIEWER, "conflict_of_interest_disclosed": True, "training_completed": True},
            {"id": "MBR-004", "name": "Dr. Michael Patel", "specialty": "Retinal Medicine", "institution": "Mass Eye and Ear", "role": AdjudicatorRole.TIEBREAKER, "conflict_of_interest_disclosed": True, "training_completed": True},
            {"id": "MBR-005", "name": "Dr. Laura Kim", "specialty": "Vitreoretinal Surgery", "institution": "Cole Eye Institute", "role": AdjudicatorRole.PRIMARY_REVIEWER, "conflict_of_interest_disclosed": True, "training_completed": True},
            {"id": "MBR-006", "name": "Dr. Robert Williams", "specialty": "Dermatology", "institution": "NYU Langone Dermatology", "role": AdjudicatorRole.CHAIR, "conflict_of_interest_disclosed": True, "training_completed": True},
            {"id": "MBR-007", "name": "Dr. Angela Martinez", "specialty": "Immunology", "institution": "National Jewish Health", "role": AdjudicatorRole.PRIMARY_REVIEWER, "conflict_of_interest_disclosed": True, "training_completed": True},
            {"id": "MBR-008", "name": "Dr. David Nakamura", "specialty": "Dermatology", "institution": "Oregon Health & Science University", "role": AdjudicatorRole.SECONDARY_REVIEWER, "conflict_of_interest_disclosed": True, "training_completed": True},
            {"id": "MBR-009", "name": "Dr. Patricia Sullivan", "specialty": "Allergology", "institution": "Northwestern Medicine", "role": AdjudicatorRole.TIEBREAKER, "conflict_of_interest_disclosed": True, "training_completed": True},
            {"id": "MBR-010", "name": "Dr. Thomas Berg", "specialty": "Clinical Immunology", "institution": "Johns Hopkins Allergy Center", "role": AdjudicatorRole.PRIMARY_REVIEWER, "conflict_of_interest_disclosed": True, "training_completed": True},
            {"id": "MBR-011", "name": "Dr. Catherine Liu", "specialty": "Oncology", "institution": "Memorial Sloan Kettering", "role": AdjudicatorRole.CHAIR, "conflict_of_interest_disclosed": True, "training_completed": True},
            {"id": "MBR-012", "name": "Dr. Andrew Foster", "specialty": "Medical Oncology", "institution": "MD Anderson Cancer Center", "role": AdjudicatorRole.PRIMARY_REVIEWER, "conflict_of_interest_disclosed": True, "training_completed": True},
            {"id": "MBR-013", "name": "Dr. Natalie Wong", "specialty": "Radiation Oncology", "institution": "Dana-Farber Cancer Institute", "role": AdjudicatorRole.SECONDARY_REVIEWER, "conflict_of_interest_disclosed": True, "training_completed": True},
            {"id": "MBR-014", "name": "Dr. Gregory Harris", "specialty": "Pathology", "institution": "Cleveland Clinic Pathology", "role": AdjudicatorRole.TIEBREAKER, "conflict_of_interest_disclosed": True, "training_completed": True},
            {"id": "MBR-015", "name": "Dr. Maria Santos", "specialty": "Immuno-Oncology", "institution": "Fred Hutchinson Cancer Center", "role": AdjudicatorRole.PRIMARY_REVIEWER, "conflict_of_interest_disclosed": False, "training_completed": False},
        ]

        for m in members_data:
            self._members[m["id"]] = CommitteeMember(**m)

        # --- 3 Adjudication Committees ---
        committees_data = [
            {
                "id": "CEAC-001",
                "trial_id": EYLEA_TRIAL,
                "name": "EYLEA HD BCVA Endpoint Adjudication Committee",
                "charter_version": "2.1",
                "members": [self._members[mid] for mid in ["MBR-001", "MBR-002", "MBR-003", "MBR-004", "MBR-005"]],
                "blinding_status": BlindingStatus.BLINDED,
                "meeting_frequency": "monthly",
            },
            {
                "id": "CEAC-002",
                "trial_id": DUPIXENT_TRIAL,
                "name": "Dupixent EASI/IGA Outcome Adjudication Committee",
                "charter_version": "1.3",
                "members": [self._members[mid] for mid in ["MBR-006", "MBR-007", "MBR-008", "MBR-009", "MBR-010"]],
                "blinding_status": BlindingStatus.BLINDED,
                "meeting_frequency": "biweekly",
            },
            {
                "id": "CEAC-003",
                "trial_id": LIBTAYO_TRIAL,
                "name": "Libtayo ORR/PFS Endpoint Adjudication Committee",
                "charter_version": "3.0",
                "members": [self._members[mid] for mid in ["MBR-011", "MBR-012", "MBR-013", "MBR-014", "MBR-015"]],
                "blinding_status": BlindingStatus.PARTIALLY_UNBLINDED,
                "meeting_frequency": "monthly",
            },
        ]

        for c in committees_data:
            self._committees[c["id"]] = AdjudicationCommittee(**c)

        # --- 30 Adjudication Events ---
        events_data = [
            # EYLEA trial events (BCVA outcomes)
            {"id": "AEV-001", "trial_id": EYLEA_TRIAL, "patient_id": "PT-1001", "event_type": EndpointType.PRIMARY, "event_date": now - timedelta(days=90), "reported_by_site": "SITE-101", "source_documents": ["OCT-1001-V6", "BCVA-1001-V6"], "status": AdjudicationStatus.FINAL, "assigned_reviewers": ["MBR-002", "MBR-003"], "classification": EventClassification.CONFIRMED, "classification_date": now - timedelta(days=75), "consensus_required": False},
            {"id": "AEV-002", "trial_id": EYLEA_TRIAL, "patient_id": "PT-1002", "event_type": EndpointType.PRIMARY, "event_date": now - timedelta(days=85), "reported_by_site": "SITE-101", "source_documents": ["OCT-1002-V6", "BCVA-1002-V6"], "status": AdjudicationStatus.FINAL, "assigned_reviewers": ["MBR-002", "MBR-005"], "classification": EventClassification.CONFIRMED, "classification_date": now - timedelta(days=70), "consensus_required": False},
            {"id": "AEV-003", "trial_id": EYLEA_TRIAL, "patient_id": "PT-1003", "event_type": EndpointType.PRIMARY, "event_date": now - timedelta(days=80), "reported_by_site": "SITE-102", "source_documents": ["OCT-1003-V6", "BCVA-1003-V6"], "status": AdjudicationStatus.FINAL, "assigned_reviewers": ["MBR-003", "MBR-005"], "classification": EventClassification.NOT_CONFIRMED, "classification_date": now - timedelta(days=65), "consensus_required": True},
            {"id": "AEV-004", "trial_id": EYLEA_TRIAL, "patient_id": "PT-1004", "event_type": EndpointType.SECONDARY, "event_date": now - timedelta(days=75), "reported_by_site": "SITE-102", "source_documents": ["CRT-1004-V6"], "status": AdjudicationStatus.FINAL, "assigned_reviewers": ["MBR-002", "MBR-003"], "classification": EventClassification.CONFIRMED, "classification_date": now - timedelta(days=60), "consensus_required": False},
            {"id": "AEV-005", "trial_id": EYLEA_TRIAL, "patient_id": "PT-1005", "event_type": EndpointType.SAFETY, "event_date": now - timedelta(days=70), "reported_by_site": "SITE-103", "source_documents": ["SAE-1005-001", "MRI-1005"], "status": AdjudicationStatus.FINAL, "assigned_reviewers": ["MBR-002", "MBR-005"], "classification": EventClassification.CONFIRMED, "classification_date": now - timedelta(days=55), "consensus_required": False},
            {"id": "AEV-006", "trial_id": EYLEA_TRIAL, "patient_id": "PT-1006", "event_type": EndpointType.PRIMARY, "event_date": now - timedelta(days=45), "reported_by_site": "SITE-103", "source_documents": ["OCT-1006-V8", "BCVA-1006-V8"], "status": AdjudicationStatus.ADJUDICATED, "assigned_reviewers": ["MBR-003", "MBR-005"], "classification": EventClassification.INDETERMINATE, "classification_date": now - timedelta(days=30), "consensus_required": True},
            {"id": "AEV-007", "trial_id": EYLEA_TRIAL, "patient_id": "PT-1007", "event_type": EndpointType.PRIMARY, "event_date": now - timedelta(days=30), "reported_by_site": "SITE-101", "source_documents": ["OCT-1007-V10", "BCVA-1007-V10"], "status": AdjudicationStatus.IN_REVIEW, "assigned_reviewers": ["MBR-002", "MBR-003"], "classification": None, "classification_date": None, "consensus_required": False},
            {"id": "AEV-008", "trial_id": EYLEA_TRIAL, "patient_id": "PT-1008", "event_type": EndpointType.SECONDARY, "event_date": now - timedelta(days=25), "reported_by_site": "SITE-102", "source_documents": ["CRT-1008-V10"], "status": AdjudicationStatus.IN_REVIEW, "assigned_reviewers": ["MBR-005", "MBR-002"], "classification": None, "classification_date": None, "consensus_required": False},
            {"id": "AEV-009", "trial_id": EYLEA_TRIAL, "patient_id": "PT-1009", "event_type": EndpointType.PRIMARY, "event_date": now - timedelta(days=15), "reported_by_site": "SITE-103", "source_documents": ["OCT-1009-V12"], "status": AdjudicationStatus.PENDING, "assigned_reviewers": [], "classification": None, "classification_date": None, "consensus_required": False},
            {"id": "AEV-010", "trial_id": EYLEA_TRIAL, "patient_id": "PT-1010", "event_type": EndpointType.COMPOSITE, "event_date": now - timedelta(days=10), "reported_by_site": "SITE-101", "source_documents": ["OCT-1010-V12", "BCVA-1010-V12", "FA-1010"], "status": AdjudicationStatus.PENDING, "assigned_reviewers": [], "classification": None, "classification_date": None, "consensus_required": False},

            # Dupixent trial events (EASI/IGA outcomes)
            {"id": "AEV-011", "trial_id": DUPIXENT_TRIAL, "patient_id": "PT-2001", "event_type": EndpointType.PRIMARY, "event_date": now - timedelta(days=100), "reported_by_site": "SITE-104", "source_documents": ["EASI-2001-W16", "IGA-2001-W16"], "status": AdjudicationStatus.FINAL, "assigned_reviewers": ["MBR-007", "MBR-008"], "classification": EventClassification.CONFIRMED, "classification_date": now - timedelta(days=85), "consensus_required": False},
            {"id": "AEV-012", "trial_id": DUPIXENT_TRIAL, "patient_id": "PT-2002", "event_type": EndpointType.PRIMARY, "event_date": now - timedelta(days=95), "reported_by_site": "SITE-104", "source_documents": ["EASI-2002-W16", "IGA-2002-W16", "PHOTO-2002"], "status": AdjudicationStatus.FINAL, "assigned_reviewers": ["MBR-007", "MBR-010"], "classification": EventClassification.CONFIRMED, "classification_date": now - timedelta(days=80), "consensus_required": False},
            {"id": "AEV-013", "trial_id": DUPIXENT_TRIAL, "patient_id": "PT-2003", "event_type": EndpointType.PRIMARY, "event_date": now - timedelta(days=88), "reported_by_site": "SITE-105", "source_documents": ["EASI-2003-W16", "IGA-2003-W16"], "status": AdjudicationStatus.FINAL, "assigned_reviewers": ["MBR-008", "MBR-010"], "classification": EventClassification.NOT_CONFIRMED, "classification_date": now - timedelta(days=72), "consensus_required": True},
            {"id": "AEV-014", "trial_id": DUPIXENT_TRIAL, "patient_id": "PT-2004", "event_type": EndpointType.SECONDARY, "event_date": now - timedelta(days=82), "reported_by_site": "SITE-105", "source_documents": ["NRS-2004-W16", "DLQI-2004-W16"], "status": AdjudicationStatus.FINAL, "assigned_reviewers": ["MBR-007", "MBR-008"], "classification": EventClassification.CONFIRMED, "classification_date": now - timedelta(days=68), "consensus_required": False},
            {"id": "AEV-015", "trial_id": DUPIXENT_TRIAL, "patient_id": "PT-2005", "event_type": EndpointType.SAFETY, "event_date": now - timedelta(days=60), "reported_by_site": "SITE-106", "source_documents": ["SAE-2005-001", "LABS-2005"], "status": AdjudicationStatus.FINAL, "assigned_reviewers": ["MBR-007", "MBR-010"], "classification": EventClassification.CONFIRMED, "classification_date": now - timedelta(days=45), "consensus_required": False},
            {"id": "AEV-016", "trial_id": DUPIXENT_TRIAL, "patient_id": "PT-2006", "event_type": EndpointType.PRIMARY, "event_date": now - timedelta(days=50), "reported_by_site": "SITE-106", "source_documents": ["EASI-2006-W24"], "status": AdjudicationStatus.ADJUDICATED, "assigned_reviewers": ["MBR-008", "MBR-010"], "classification": EventClassification.MISSING_DATA, "classification_date": now - timedelta(days=35), "consensus_required": True},
            {"id": "AEV-017", "trial_id": DUPIXENT_TRIAL, "patient_id": "PT-2007", "event_type": EndpointType.PRIMARY, "event_date": now - timedelta(days=35), "reported_by_site": "SITE-104", "source_documents": ["EASI-2007-W24", "IGA-2007-W24"], "status": AdjudicationStatus.IN_REVIEW, "assigned_reviewers": ["MBR-007", "MBR-008"], "classification": None, "classification_date": None, "consensus_required": False},
            {"id": "AEV-018", "trial_id": DUPIXENT_TRIAL, "patient_id": "PT-2008", "event_type": EndpointType.EXPLORATORY, "event_date": now - timedelta(days=28), "reported_by_site": "SITE-105", "source_documents": ["BIOMARKER-2008"], "status": AdjudicationStatus.IN_REVIEW, "assigned_reviewers": ["MBR-010", "MBR-007"], "classification": None, "classification_date": None, "consensus_required": False},
            {"id": "AEV-019", "trial_id": DUPIXENT_TRIAL, "patient_id": "PT-2009", "event_type": EndpointType.PRIMARY, "event_date": now - timedelta(days=12), "reported_by_site": "SITE-106", "source_documents": ["EASI-2009-W32"], "status": AdjudicationStatus.PENDING, "assigned_reviewers": [], "classification": None, "classification_date": None, "consensus_required": False},
            {"id": "AEV-020", "trial_id": DUPIXENT_TRIAL, "patient_id": "PT-2010", "event_type": EndpointType.PRIMARY, "event_date": now - timedelta(days=8), "reported_by_site": "SITE-104", "source_documents": ["EASI-2010-W32", "IGA-2010-W32"], "status": AdjudicationStatus.PENDING, "assigned_reviewers": [], "classification": None, "classification_date": None, "consensus_required": False},

            # Libtayo trial events (ORR/PFS outcomes)
            {"id": "AEV-021", "trial_id": LIBTAYO_TRIAL, "patient_id": "PT-3001", "event_type": EndpointType.PRIMARY, "event_date": now - timedelta(days=110), "reported_by_site": "SITE-107", "source_documents": ["CT-3001-C4", "RECIST-3001"], "status": AdjudicationStatus.FINAL, "assigned_reviewers": ["MBR-012", "MBR-013"], "classification": EventClassification.CONFIRMED, "classification_date": now - timedelta(days=95), "consensus_required": False},
            {"id": "AEV-022", "trial_id": LIBTAYO_TRIAL, "patient_id": "PT-3002", "event_type": EndpointType.PRIMARY, "event_date": now - timedelta(days=105), "reported_by_site": "SITE-107", "source_documents": ["CT-3002-C4", "RECIST-3002"], "status": AdjudicationStatus.FINAL, "assigned_reviewers": ["MBR-012", "MBR-015"], "classification": EventClassification.NOT_CONFIRMED, "classification_date": now - timedelta(days=90), "consensus_required": True},
            {"id": "AEV-023", "trial_id": LIBTAYO_TRIAL, "patient_id": "PT-3003", "event_type": EndpointType.SECONDARY, "event_date": now - timedelta(days=95), "reported_by_site": "SITE-108", "source_documents": ["PFS-3003-C6"], "status": AdjudicationStatus.FINAL, "assigned_reviewers": ["MBR-013", "MBR-015"], "classification": EventClassification.CONFIRMED, "classification_date": now - timedelta(days=80), "consensus_required": False},
            {"id": "AEV-024", "trial_id": LIBTAYO_TRIAL, "patient_id": "PT-3004", "event_type": EndpointType.SAFETY, "event_date": now - timedelta(days=80), "reported_by_site": "SITE-108", "source_documents": ["SAE-3004-001", "BIOPSY-3004"], "status": AdjudicationStatus.FINAL, "assigned_reviewers": ["MBR-012", "MBR-013"], "classification": EventClassification.CONFIRMED, "classification_date": now - timedelta(days=65), "consensus_required": False},
            {"id": "AEV-025", "trial_id": LIBTAYO_TRIAL, "patient_id": "PT-3005", "event_type": EndpointType.PRIMARY, "event_date": now - timedelta(days=55), "reported_by_site": "SITE-107", "source_documents": ["CT-3005-C8", "RECIST-3005"], "status": AdjudicationStatus.ADJUDICATED, "assigned_reviewers": ["MBR-012", "MBR-015"], "classification": EventClassification.CONFIRMED, "classification_date": now - timedelta(days=40), "consensus_required": False},
            {"id": "AEV-026", "trial_id": LIBTAYO_TRIAL, "patient_id": "PT-3006", "event_type": EndpointType.PRIMARY, "event_date": now - timedelta(days=42), "reported_by_site": "SITE-108", "source_documents": ["CT-3006-C8", "RECIST-3006"], "status": AdjudicationStatus.APPEALED, "assigned_reviewers": ["MBR-013", "MBR-015"], "classification": EventClassification.NOT_CONFIRMED, "classification_date": now - timedelta(days=28), "consensus_required": True},
            {"id": "AEV-027", "trial_id": LIBTAYO_TRIAL, "patient_id": "PT-3007", "event_type": EndpointType.PRIMARY, "event_date": now - timedelta(days=32), "reported_by_site": "SITE-107", "source_documents": ["CT-3007-C10", "RECIST-3007"], "status": AdjudicationStatus.IN_REVIEW, "assigned_reviewers": ["MBR-012", "MBR-013"], "classification": None, "classification_date": None, "consensus_required": False},
            {"id": "AEV-028", "trial_id": LIBTAYO_TRIAL, "patient_id": "PT-3008", "event_type": EndpointType.COMPOSITE, "event_date": now - timedelta(days=22), "reported_by_site": "SITE-108", "source_documents": ["CT-3008-C10", "PFS-3008", "OS-3008"], "status": AdjudicationStatus.IN_REVIEW, "assigned_reviewers": ["MBR-015", "MBR-012"], "classification": None, "classification_date": None, "consensus_required": False},
            {"id": "AEV-029", "trial_id": LIBTAYO_TRIAL, "patient_id": "PT-3009", "event_type": EndpointType.PRIMARY, "event_date": now - timedelta(days=7), "reported_by_site": "SITE-107", "source_documents": ["CT-3009-C12"], "status": AdjudicationStatus.PENDING, "assigned_reviewers": [], "classification": None, "classification_date": None, "consensus_required": False},
            {"id": "AEV-030", "trial_id": LIBTAYO_TRIAL, "patient_id": "PT-3010", "event_type": EndpointType.SAFETY, "event_date": now - timedelta(days=3), "reported_by_site": "SITE-108", "source_documents": ["SAE-3010-001"], "status": AdjudicationStatus.PENDING, "assigned_reviewers": [], "classification": None, "classification_date": None, "consensus_required": False},
        ]

        for e in events_data:
            self._events[e["id"]] = AdjudicationEvent(**e)

        # --- 40 Reviewer Assessments ---
        assessments_data = [
            # EYLEA events - dual reviewer assessments
            {"id": "ASS-001", "event_id": "AEV-001", "reviewer_id": "MBR-002", "classification": EventClassification.CONFIRMED, "confidence_level": ConfidenceLevel.HIGH, "rationale": "BCVA gain of 15 letters confirmed on OCT. Clear evidence of improvement.", "reviewed_date": now - timedelta(days=80)},
            {"id": "ASS-002", "event_id": "AEV-001", "reviewer_id": "MBR-003", "classification": EventClassification.CONFIRMED, "confidence_level": ConfidenceLevel.HIGH, "rationale": "Concordant OCT findings support BCVA improvement. Endpoint met.", "reviewed_date": now - timedelta(days=78)},
            {"id": "ASS-003", "event_id": "AEV-002", "reviewer_id": "MBR-002", "classification": EventClassification.CONFIRMED, "confidence_level": ConfidenceLevel.HIGH, "rationale": "Robust BCVA improvement with supporting imaging.", "reviewed_date": now - timedelta(days=75)},
            {"id": "ASS-004", "event_id": "AEV-002", "reviewer_id": "MBR-005", "classification": EventClassification.CONFIRMED, "confidence_level": ConfidenceLevel.MEDIUM, "rationale": "BCVA improvement noted; minor discrepancy in visit window but acceptable.", "reviewed_date": now - timedelta(days=73)},
            {"id": "ASS-005", "event_id": "AEV-003", "reviewer_id": "MBR-003", "classification": EventClassification.NOT_CONFIRMED, "confidence_level": ConfidenceLevel.MEDIUM, "rationale": "BCVA change does not meet minimum threshold for endpoint.", "reviewed_date": now - timedelta(days=70)},
            {"id": "ASS-006", "event_id": "AEV-003", "reviewer_id": "MBR-005", "classification": EventClassification.CONFIRMED, "confidence_level": ConfidenceLevel.LOW, "rationale": "Borderline case. OCT suggests improvement but BCVA is marginal.", "reviewed_date": now - timedelta(days=69)},
            {"id": "ASS-007", "event_id": "AEV-003", "reviewer_id": "MBR-004", "classification": EventClassification.NOT_CONFIRMED, "confidence_level": ConfidenceLevel.HIGH, "rationale": "Tiebreaker review: BCVA change insufficient. Agree with not confirmed.", "reviewed_date": now - timedelta(days=67)},
            {"id": "ASS-008", "event_id": "AEV-004", "reviewer_id": "MBR-002", "classification": EventClassification.CONFIRMED, "confidence_level": ConfidenceLevel.HIGH, "rationale": "CRT reduction exceeds threshold. Secondary endpoint confirmed.", "reviewed_date": now - timedelta(days=65)},
            {"id": "ASS-009", "event_id": "AEV-004", "reviewer_id": "MBR-003", "classification": EventClassification.CONFIRMED, "confidence_level": ConfidenceLevel.HIGH, "rationale": "Clear CRT improvement on OCT. Endpoint confirmed.", "reviewed_date": now - timedelta(days=63)},
            {"id": "ASS-010", "event_id": "AEV-005", "reviewer_id": "MBR-002", "classification": EventClassification.CONFIRMED, "confidence_level": ConfidenceLevel.HIGH, "rationale": "SAE clearly related to treatment. Endophthalmitis confirmed.", "reviewed_date": now - timedelta(days=60)},
            {"id": "ASS-011", "event_id": "AEV-005", "reviewer_id": "MBR-005", "classification": EventClassification.CONFIRMED, "confidence_level": ConfidenceLevel.HIGH, "rationale": "Imaging and clinical findings consistent with endophthalmitis.", "reviewed_date": now - timedelta(days=58)},
            {"id": "ASS-012", "event_id": "AEV-006", "reviewer_id": "MBR-003", "classification": EventClassification.INDETERMINATE, "confidence_level": ConfidenceLevel.LOW, "rationale": "OCT quality poor. Cannot definitively assess BCVA endpoint.", "reviewed_date": now - timedelta(days=35)},
            {"id": "ASS-013", "event_id": "AEV-006", "reviewer_id": "MBR-005", "classification": EventClassification.CONFIRMED, "confidence_level": ConfidenceLevel.LOW, "rationale": "Marginal evidence suggests improvement but image quality limits confidence.", "reviewed_date": now - timedelta(days=33)},

            # Dupixent events - dual reviewer assessments
            {"id": "ASS-014", "event_id": "AEV-011", "reviewer_id": "MBR-007", "classification": EventClassification.CONFIRMED, "confidence_level": ConfidenceLevel.HIGH, "rationale": "EASI-75 achieved. IGA 0/1 confirmed. Clear responder.", "reviewed_date": now - timedelta(days=90)},
            {"id": "ASS-015", "event_id": "AEV-011", "reviewer_id": "MBR-008", "classification": EventClassification.CONFIRMED, "confidence_level": ConfidenceLevel.HIGH, "rationale": "Photographic evidence supports EASI-75 and IGA response.", "reviewed_date": now - timedelta(days=88)},
            {"id": "ASS-016", "event_id": "AEV-012", "reviewer_id": "MBR-007", "classification": EventClassification.CONFIRMED, "confidence_level": ConfidenceLevel.HIGH, "rationale": "EASI score reduction >75%. IGA improved to clear/almost clear.", "reviewed_date": now - timedelta(days=85)},
            {"id": "ASS-017", "event_id": "AEV-012", "reviewer_id": "MBR-010", "classification": EventClassification.CONFIRMED, "confidence_level": ConfidenceLevel.MEDIUM, "rationale": "EASI improvement confirmed. Minor scoring discrepancy but within tolerance.", "reviewed_date": now - timedelta(days=83)},
            {"id": "ASS-018", "event_id": "AEV-013", "reviewer_id": "MBR-008", "classification": EventClassification.NOT_CONFIRMED, "confidence_level": ConfidenceLevel.MEDIUM, "rationale": "EASI improvement below 75% threshold. IGA not achieved.", "reviewed_date": now - timedelta(days=78)},
            {"id": "ASS-019", "event_id": "AEV-013", "reviewer_id": "MBR-010", "classification": EventClassification.CONFIRMED, "confidence_level": ConfidenceLevel.LOW, "rationale": "Borderline EASI response. Scorer disagreement noted.", "reviewed_date": now - timedelta(days=76)},
            {"id": "ASS-020", "event_id": "AEV-013", "reviewer_id": "MBR-009", "classification": EventClassification.NOT_CONFIRMED, "confidence_level": ConfidenceLevel.HIGH, "rationale": "Tiebreaker: EASI change insufficient for 75% threshold.", "reviewed_date": now - timedelta(days=74)},
            {"id": "ASS-021", "event_id": "AEV-014", "reviewer_id": "MBR-007", "classification": EventClassification.CONFIRMED, "confidence_level": ConfidenceLevel.HIGH, "rationale": "NRS itch improvement of 4+ points. DLQI significant improvement.", "reviewed_date": now - timedelta(days=72)},
            {"id": "ASS-022", "event_id": "AEV-014", "reviewer_id": "MBR-008", "classification": EventClassification.CONFIRMED, "confidence_level": ConfidenceLevel.HIGH, "rationale": "Secondary endpoints clearly met. Pruritus reduction sustained.", "reviewed_date": now - timedelta(days=70)},
            {"id": "ASS-023", "event_id": "AEV-015", "reviewer_id": "MBR-007", "classification": EventClassification.CONFIRMED, "confidence_level": ConfidenceLevel.HIGH, "rationale": "Injection site reaction confirmed. Consistent with known safety profile.", "reviewed_date": now - timedelta(days=50)},
            {"id": "ASS-024", "event_id": "AEV-015", "reviewer_id": "MBR-010", "classification": EventClassification.CONFIRMED, "confidence_level": ConfidenceLevel.HIGH, "rationale": "SAE adjudicated as treatment-related. Safety endpoint confirmed.", "reviewed_date": now - timedelta(days=48)},
            {"id": "ASS-025", "event_id": "AEV-016", "reviewer_id": "MBR-008", "classification": EventClassification.MISSING_DATA, "confidence_level": ConfidenceLevel.LOW, "rationale": "EASI score at W24 not available. Visit missed by patient.", "reviewed_date": now - timedelta(days=40)},
            {"id": "ASS-026", "event_id": "AEV-016", "reviewer_id": "MBR-010", "classification": EventClassification.INDETERMINATE, "confidence_level": ConfidenceLevel.LOW, "rationale": "Partial data available but insufficient for definitive classification.", "reviewed_date": now - timedelta(days=38)},

            # Libtayo events - dual reviewer assessments
            {"id": "ASS-027", "event_id": "AEV-021", "reviewer_id": "MBR-012", "classification": EventClassification.CONFIRMED, "confidence_level": ConfidenceLevel.HIGH, "rationale": "RECIST 1.1 criteria met. Partial response confirmed on CT.", "reviewed_date": now - timedelta(days=100)},
            {"id": "ASS-028", "event_id": "AEV-021", "reviewer_id": "MBR-013", "classification": EventClassification.CONFIRMED, "confidence_level": ConfidenceLevel.HIGH, "rationale": "Target lesion reduction >30%. Confirmed partial response.", "reviewed_date": now - timedelta(days=98)},
            {"id": "ASS-029", "event_id": "AEV-022", "reviewer_id": "MBR-012", "classification": EventClassification.NOT_CONFIRMED, "confidence_level": ConfidenceLevel.MEDIUM, "rationale": "New lesion identified. Progressive disease per RECIST.", "reviewed_date": now - timedelta(days=95)},
            {"id": "ASS-030", "event_id": "AEV-022", "reviewer_id": "MBR-015", "classification": EventClassification.CONFIRMED, "confidence_level": ConfidenceLevel.LOW, "rationale": "Questionable new lesion. May be artifact. Target lesions improved.", "reviewed_date": now - timedelta(days=94)},
            {"id": "ASS-031", "event_id": "AEV-022", "reviewer_id": "MBR-014", "classification": EventClassification.NOT_CONFIRMED, "confidence_level": ConfidenceLevel.HIGH, "rationale": "Tiebreaker: pathology confirms new lesion is metastatic.", "reviewed_date": now - timedelta(days=92)},
            {"id": "ASS-032", "event_id": "AEV-023", "reviewer_id": "MBR-013", "classification": EventClassification.CONFIRMED, "confidence_level": ConfidenceLevel.HIGH, "rationale": "PFS event confirmed. Progression documented per RECIST.", "reviewed_date": now - timedelta(days=85)},
            {"id": "ASS-033", "event_id": "AEV-023", "reviewer_id": "MBR-015", "classification": EventClassification.CONFIRMED, "confidence_level": ConfidenceLevel.HIGH, "rationale": "Clear disease progression at cycle 6. PFS endpoint met.", "reviewed_date": now - timedelta(days=83)},
            {"id": "ASS-034", "event_id": "AEV-024", "reviewer_id": "MBR-012", "classification": EventClassification.CONFIRMED, "confidence_level": ConfidenceLevel.HIGH, "rationale": "Immune-related adverse event confirmed by biopsy.", "reviewed_date": now - timedelta(days=70)},
            {"id": "ASS-035", "event_id": "AEV-024", "reviewer_id": "MBR-013", "classification": EventClassification.CONFIRMED, "confidence_level": ConfidenceLevel.HIGH, "rationale": "Pathology consistent with immune-mediated colitis.", "reviewed_date": now - timedelta(days=68)},
            {"id": "ASS-036", "event_id": "AEV-025", "reviewer_id": "MBR-012", "classification": EventClassification.CONFIRMED, "confidence_level": ConfidenceLevel.HIGH, "rationale": "Complete response per RECIST 1.1. All target lesions resolved.", "reviewed_date": now - timedelta(days=45)},
            {"id": "ASS-037", "event_id": "AEV-025", "reviewer_id": "MBR-015", "classification": EventClassification.CONFIRMED, "confidence_level": ConfidenceLevel.MEDIUM, "rationale": "Near complete response. Small residual lesion may be scar tissue.", "reviewed_date": now - timedelta(days=43)},
            {"id": "ASS-038", "event_id": "AEV-026", "reviewer_id": "MBR-013", "classification": EventClassification.NOT_CONFIRMED, "confidence_level": ConfidenceLevel.MEDIUM, "rationale": "Pseudoprogression suspected. Recommend confirmatory scan.", "reviewed_date": now - timedelta(days=32)},
            {"id": "ASS-039", "event_id": "AEV-026", "reviewer_id": "MBR-015", "classification": EventClassification.CONFIRMED, "confidence_level": ConfidenceLevel.LOW, "rationale": "Tumor size increased >20% but immune context unclear.", "reviewed_date": now - timedelta(days=30)},
            {"id": "ASS-040", "event_id": "AEV-026", "reviewer_id": "MBR-014", "classification": EventClassification.NOT_CONFIRMED, "confidence_level": ConfidenceLevel.MEDIUM, "rationale": "Tiebreaker: clinical context supports pseudoprogression. Not confirmed.", "reviewed_date": now - timedelta(days=29)},
        ]

        for a in assessments_data:
            self._assessments[a["id"]] = ReviewerAssessment(**a)

        # --- 5 Committee Meetings ---
        meetings_data = [
            {
                "id": "MTG-001",
                "committee_id": "CEAC-001",
                "meeting_date": now - timedelta(days=60),
                "events_reviewed": ["AEV-001", "AEV-002", "AEV-003", "AEV-004", "AEV-005"],
                "events_adjudicated": 5,
                "disagreements_resolved": 1,
                "minutes_summary": "Reviewed 5 BCVA endpoint events. One disagreement on AEV-003 resolved by tiebreaker Dr. Patel. All events classified per charter v2.1 criteria.",
            },
            {
                "id": "MTG-002",
                "committee_id": "CEAC-001",
                "meeting_date": now - timedelta(days=25),
                "events_reviewed": ["AEV-006"],
                "events_adjudicated": 1,
                "disagreements_resolved": 1,
                "minutes_summary": "Reviewed AEV-006 indeterminate case. Poor OCT quality discussed. Committee agreed on indeterminate classification pending re-imaging.",
            },
            {
                "id": "MTG-003",
                "committee_id": "CEAC-002",
                "meeting_date": now - timedelta(days=65),
                "events_reviewed": ["AEV-011", "AEV-012", "AEV-013", "AEV-014", "AEV-015"],
                "events_adjudicated": 5,
                "disagreements_resolved": 1,
                "minutes_summary": "Reviewed 5 EASI/IGA events. Disagreement on AEV-013 resolved by tiebreaker. Training reminder on EASI scoring consistency issued.",
            },
            {
                "id": "MTG-004",
                "committee_id": "CEAC-002",
                "meeting_date": now - timedelta(days=30),
                "events_reviewed": ["AEV-016"],
                "events_adjudicated": 1,
                "disagreements_resolved": 1,
                "minutes_summary": "Discussed AEV-016 missing data case. Committee agreed that missing W24 EASI constitutes missing data classification. Site contacted for data retrieval.",
            },
            {
                "id": "MTG-005",
                "committee_id": "CEAC-003",
                "meeting_date": now - timedelta(days=20),
                "events_reviewed": ["AEV-021", "AEV-022", "AEV-023", "AEV-024", "AEV-025", "AEV-026"],
                "events_adjudicated": 6,
                "disagreements_resolved": 2,
                "minutes_summary": "Reviewed 6 ORR/PFS events. Two disagreements resolved. AEV-026 appealed by site - pseudoprogression vs true progression debated. AEV-022 confirmed as PD after pathology review.",
            },
        ]

        for mtg in meetings_data:
            self._meetings[mtg["id"]] = AdjudicationMeeting(**mtg)

    # ------------------------------------------------------------------
    # Committee Management
    # ------------------------------------------------------------------

    def list_committees(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[AdjudicationCommittee]:
        """List adjudication committees with optional trial filter."""
        with self._lock:
            result = list(self._committees.values())

        if trial_id is not None:
            result = [c for c in result if c.trial_id == trial_id]

        return sorted(result, key=lambda c: c.id)

    def get_committee(self, committee_id: str) -> AdjudicationCommittee | None:
        """Get a single committee by ID."""
        with self._lock:
            return self._committees.get(committee_id)

    def create_committee(self, payload: CommitteeCreate) -> AdjudicationCommittee:
        """Create a new adjudication committee."""
        committee_id = f"CEAC-{uuid4().hex[:8].upper()}"
        committee = AdjudicationCommittee(
            id=committee_id,
            trial_id=payload.trial_id,
            name=payload.name,
            charter_version=payload.charter_version,
            members=[],
            blinding_status=payload.blinding_status,
            meeting_frequency=payload.meeting_frequency,
        )
        with self._lock:
            self._committees[committee_id] = committee
        logger.info("Created adjudication committee %s: %s", committee_id, payload.name)
        return committee

    def update_committee(
        self, committee_id: str, payload: CommitteeUpdate
    ) -> AdjudicationCommittee | None:
        """Update an existing committee."""
        with self._lock:
            existing = self._committees.get(committee_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = AdjudicationCommittee(**data)
            self._committees[committee_id] = updated
        return updated

    def delete_committee(self, committee_id: str) -> bool:
        """Delete a committee. Returns True if deleted."""
        with self._lock:
            if committee_id in self._committees:
                del self._committees[committee_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Member Management
    # ------------------------------------------------------------------

    def list_members(
        self,
        *,
        committee_id: str | None = None,
        role: AdjudicatorRole | None = None,
    ) -> list[CommitteeMember]:
        """List committee members with optional filters."""
        if committee_id is not None:
            committee = self.get_committee(committee_id)
            if committee is None:
                return []
            result = list(committee.members)
        else:
            with self._lock:
                result = list(self._members.values())

        if role is not None:
            result = [m for m in result if m.role == role]

        return sorted(result, key=lambda m: m.id)

    def get_member(self, member_id: str) -> CommitteeMember | None:
        """Get a single member by ID."""
        with self._lock:
            return self._members.get(member_id)

    def add_member_to_committee(
        self, committee_id: str, payload: MemberCreate
    ) -> CommitteeMember | None:
        """Add a new member to a committee."""
        member_id = f"MBR-{uuid4().hex[:8].upper()}"
        member = CommitteeMember(
            id=member_id,
            **payload.model_dump(),
        )
        with self._lock:
            committee = self._committees.get(committee_id)
            if committee is None:
                return None
            data = committee.model_dump()
            data["members"].append(member.model_dump())
            self._committees[committee_id] = AdjudicationCommittee(**data)
            self._members[member_id] = member
        logger.info("Added member %s to committee %s", member_id, committee_id)
        return member

    def update_member(
        self, member_id: str, payload: MemberUpdate
    ) -> CommitteeMember | None:
        """Update a committee member."""
        with self._lock:
            existing = self._members.get(member_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CommitteeMember(**data)
            self._members[member_id] = updated

            # Update member in all committees that contain them
            for cid, committee in self._committees.items():
                cdata = committee.model_dump()
                for i, m in enumerate(cdata["members"]):
                    if m["id"] == member_id:
                        cdata["members"][i] = updated.model_dump()
                self._committees[cid] = AdjudicationCommittee(**cdata)

        return updated

    def remove_member_from_committee(
        self, committee_id: str, member_id: str
    ) -> bool:
        """Remove a member from a committee."""
        with self._lock:
            committee = self._committees.get(committee_id)
            if committee is None:
                return False
            data = committee.model_dump()
            original_len = len(data["members"])
            data["members"] = [
                m for m in data["members"] if m["id"] != member_id
            ]
            if len(data["members"]) == original_len:
                return False
            self._committees[committee_id] = AdjudicationCommittee(**data)
        return True

    # ------------------------------------------------------------------
    # Event Management
    # ------------------------------------------------------------------

    def list_events(
        self,
        *,
        trial_id: str | None = None,
        status: AdjudicationStatus | None = None,
        event_type: EndpointType | None = None,
        classification: EventClassification | None = None,
    ) -> list[AdjudicationEvent]:
        """List adjudication events with optional filters."""
        with self._lock:
            result = list(self._events.values())

        if trial_id is not None:
            result = [e for e in result if e.trial_id == trial_id]
        if status is not None:
            result = [e for e in result if e.status == status]
        if event_type is not None:
            result = [e for e in result if e.event_type == event_type]
        if classification is not None:
            result = [e for e in result if e.classification == classification]

        return sorted(result, key=lambda e: e.event_date, reverse=True)

    def get_event(self, event_id: str) -> AdjudicationEvent | None:
        """Get a single event by ID."""
        with self._lock:
            return self._events.get(event_id)

    def create_event(self, payload: EventCreate) -> AdjudicationEvent:
        """Create a new adjudication event."""
        event_id = f"AEV-{uuid4().hex[:8].upper()}"
        event = AdjudicationEvent(
            id=event_id,
            trial_id=payload.trial_id,
            patient_id=payload.patient_id,
            event_type=payload.event_type,
            event_date=payload.event_date,
            reported_by_site=payload.reported_by_site,
            source_documents=payload.source_documents,
            status=AdjudicationStatus.PENDING,
            assigned_reviewers=[],
            classification=None,
            classification_date=None,
            consensus_required=False,
        )
        with self._lock:
            self._events[event_id] = event
        logger.info(
            "Created adjudication event %s: trial=%s patient=%s type=%s",
            event_id, payload.trial_id, payload.patient_id, payload.event_type.value,
        )
        return event

    def update_event(
        self, event_id: str, payload: EventUpdate
    ) -> AdjudicationEvent | None:
        """Update an adjudication event."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._events.get(event_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set classification_date when classification is set
            if "classification" in updates and updates["classification"] is not None:
                if existing.classification is None:
                    updates["classification_date"] = now

            data.update(updates)
            updated = AdjudicationEvent(**data)
            self._events[event_id] = updated
        return updated

    def assign_reviewers(
        self, event_id: str, reviewer_ids: list[str]
    ) -> AdjudicationEvent | None:
        """Assign reviewers to an event and move to in_review status."""
        with self._lock:
            existing = self._events.get(event_id)
            if existing is None:
                return None

            # Validate reviewer IDs
            for rid in reviewer_ids:
                if rid not in self._members:
                    raise ValueError(f"Reviewer '{rid}' not found")

            data = existing.model_dump()
            data["assigned_reviewers"] = reviewer_ids
            data["status"] = AdjudicationStatus.IN_REVIEW
            updated = AdjudicationEvent(**data)
            self._events[event_id] = updated
        logger.info("Assigned reviewers %s to event %s", reviewer_ids, event_id)
        return updated

    def adjudicate_event(self, event_id: str) -> AdjudicationEvent | None:
        """Adjudicate an event based on reviewer assessments.

        Uses dual-reviewer workflow:
        - If both reviewers agree -> classification is consensus
        - If they disagree -> marks consensus_required, assigns tiebreaker
        """
        now = datetime.now(timezone.utc)
        with self._lock:
            event = self._events.get(event_id)
            if event is None:
                return None

            if event.status not in (AdjudicationStatus.IN_REVIEW, AdjudicationStatus.PENDING):
                raise ValueError(
                    f"Event '{event_id}' cannot be adjudicated in status '{event.status.value}'"
                )

            # Get assessments for this event
            event_assessments = [
                a for a in self._assessments.values()
                if a.event_id == event_id
            ]

            if len(event_assessments) < 2:
                raise ValueError(
                    f"Event '{event_id}' requires at least 2 reviewer assessments"
                )

            # Check for consensus
            classifications = [a.classification for a in event_assessments]
            primary_reviewers = event_assessments[:2]

            if primary_reviewers[0].classification == primary_reviewers[1].classification:
                # Agreement - adjudicate
                data = event.model_dump()
                data["status"] = AdjudicationStatus.ADJUDICATED
                data["classification"] = primary_reviewers[0].classification
                data["classification_date"] = now
                data["consensus_required"] = False
                updated = AdjudicationEvent(**data)
                self._events[event_id] = updated
            else:
                # Disagreement
                if len(event_assessments) >= 3:
                    # Tiebreaker has voted - use majority
                    from collections import Counter
                    counts = Counter(classifications)
                    majority = counts.most_common(1)[0][0]
                    data = event.model_dump()
                    data["status"] = AdjudicationStatus.ADJUDICATED
                    data["classification"] = majority
                    data["classification_date"] = now
                    data["consensus_required"] = True
                    updated = AdjudicationEvent(**data)
                    self._events[event_id] = updated
                else:
                    # Need tiebreaker
                    data = event.model_dump()
                    data["consensus_required"] = True
                    updated = AdjudicationEvent(**data)
                    self._events[event_id] = updated

        return updated

    # ------------------------------------------------------------------
    # Reviewer Assessments
    # ------------------------------------------------------------------

    def list_assessments(
        self,
        *,
        event_id: str | None = None,
        reviewer_id: str | None = None,
    ) -> list[ReviewerAssessment]:
        """List reviewer assessments with optional filters."""
        with self._lock:
            result = list(self._assessments.values())

        if event_id is not None:
            result = [a for a in result if a.event_id == event_id]
        if reviewer_id is not None:
            result = [a for a in result if a.reviewer_id == reviewer_id]

        return sorted(result, key=lambda a: a.reviewed_date, reverse=True)

    def get_assessment(self, assessment_id: str) -> ReviewerAssessment | None:
        """Get a single assessment by ID."""
        with self._lock:
            return self._assessments.get(assessment_id)

    def submit_assessment(self, payload: AssessmentCreate) -> ReviewerAssessment:
        """Submit a reviewer assessment for an event."""
        now = datetime.now(timezone.utc)
        assessment_id = f"ASS-{uuid4().hex[:8].upper()}"

        # Validate event exists
        with self._lock:
            event = self._events.get(payload.event_id)
            if event is None:
                raise ValueError(f"Event '{payload.event_id}' not found")
            member = self._members.get(payload.reviewer_id)
            if member is None:
                raise ValueError(f"Reviewer '{payload.reviewer_id}' not found")

        assessment = ReviewerAssessment(
            id=assessment_id,
            event_id=payload.event_id,
            reviewer_id=payload.reviewer_id,
            classification=payload.classification,
            confidence_level=payload.confidence_level,
            rationale=payload.rationale,
            reviewed_date=now,
        )

        with self._lock:
            self._assessments[assessment_id] = assessment

        logger.info(
            "Submitted assessment %s: event=%s reviewer=%s classification=%s",
            assessment_id, payload.event_id, payload.reviewer_id,
            payload.classification.value,
        )
        return assessment

    # ------------------------------------------------------------------
    # Meetings
    # ------------------------------------------------------------------

    def list_meetings(
        self,
        *,
        committee_id: str | None = None,
    ) -> list[AdjudicationMeeting]:
        """List committee meetings with optional filter."""
        with self._lock:
            result = list(self._meetings.values())

        if committee_id is not None:
            result = [m for m in result if m.committee_id == committee_id]

        return sorted(result, key=lambda m: m.meeting_date, reverse=True)

    def get_meeting(self, meeting_id: str) -> AdjudicationMeeting | None:
        """Get a single meeting by ID."""
        with self._lock:
            return self._meetings.get(meeting_id)

    def create_meeting(self, payload: MeetingCreate) -> AdjudicationMeeting:
        """Create a new committee meeting."""
        meeting_id = f"MTG-{uuid4().hex[:8].upper()}"
        meeting = AdjudicationMeeting(
            id=meeting_id,
            committee_id=payload.committee_id,
            meeting_date=payload.meeting_date,
            events_reviewed=payload.events_reviewed,
            events_adjudicated=payload.events_adjudicated,
            disagreements_resolved=payload.disagreements_resolved,
            minutes_summary=payload.minutes_summary,
        )
        with self._lock:
            self._meetings[meeting_id] = meeting
        logger.info("Created meeting %s for committee %s", meeting_id, payload.committee_id)
        return meeting

    # ------------------------------------------------------------------
    # Inter-Rater Agreement (Cohen's Kappa)
    # ------------------------------------------------------------------

    def calculate_inter_rater_agreement(
        self, trial_id: str | None = None
    ) -> float:
        """Calculate Cohen's kappa for inter-rater agreement.

        Compares the primary and secondary reviewer classifications for
        events that have at least two assessments.

        Returns:
            Cohen's kappa coefficient (-1 to 1).
        """
        with self._lock:
            events = list(self._events.values())
            assessments = list(self._assessments.values())

        if trial_id is not None:
            event_ids = {e.id for e in events if e.trial_id == trial_id}
        else:
            event_ids = {e.id for e in events}

        # Build paired ratings (first two assessments per event)
        assessments_by_event: dict[str, list[ReviewerAssessment]] = {}
        for a in sorted(assessments, key=lambda x: x.reviewed_date):
            if a.event_id in event_ids:
                assessments_by_event.setdefault(a.event_id, []).append(a)

        rater1_ratings: list[str] = []
        rater2_ratings: list[str] = []
        for eid, asses in assessments_by_event.items():
            if len(asses) >= 2:
                rater1_ratings.append(asses[0].classification.value)
                rater2_ratings.append(asses[1].classification.value)

        if len(rater1_ratings) < 2:
            return 0.0

        return self._cohens_kappa(rater1_ratings, rater2_ratings)

    @staticmethod
    def _cohens_kappa(rater1: list[str], rater2: list[str]) -> float:
        """Calculate Cohen's kappa for two lists of categorical ratings."""
        n = len(rater1)
        if n == 0:
            return 0.0

        categories = sorted(set(rater1) | set(rater2))
        if len(categories) < 2:
            return 1.0  # Perfect agreement if only one category

        # Build confusion matrix
        matrix: dict[tuple[str, str], int] = {}
        for c1 in categories:
            for c2 in categories:
                matrix[(c1, c2)] = 0

        for r1, r2 in zip(rater1, rater2):
            matrix[(r1, r2)] += 1

        # Observed agreement
        po = sum(matrix[(c, c)] for c in categories) / n

        # Expected agreement
        pe = 0.0
        for c in categories:
            row_sum = sum(matrix[(c, c2)] for c2 in categories) / n
            col_sum = sum(matrix[(c1, c)] for c1 in categories) / n
            pe += row_sum * col_sum

        if pe >= 1.0:
            return 1.0

        kappa = (po - pe) / (1.0 - pe)
        return round(kappa, 4)

    # ------------------------------------------------------------------
    # Turnaround Time
    # ------------------------------------------------------------------

    def calculate_avg_turnaround_days(
        self, trial_id: str | None = None
    ) -> float:
        """Calculate average days from event date to classification date."""
        with self._lock:
            events = list(self._events.values())

        if trial_id is not None:
            events = [e for e in events if e.trial_id == trial_id]

        classified_events = [
            e for e in events
            if e.classification_date is not None and e.event_date is not None
        ]

        if not classified_events:
            return 0.0

        total_days = 0.0
        for e in classified_events:
            delta = e.classification_date - e.event_date
            total_days += delta.total_seconds() / 86400.0

        return round(total_days / len(classified_events), 1)

    # ------------------------------------------------------------------
    # Disagreement Rate
    # ------------------------------------------------------------------

    def calculate_disagreement_rate(
        self, trial_id: str | None = None
    ) -> float:
        """Calculate the percentage of events where reviewers disagreed."""
        with self._lock:
            events = list(self._events.values())

        if trial_id is not None:
            events = [e for e in events if e.trial_id == trial_id]

        events_with_consensus_data = [
            e for e in events
            if e.status in (
                AdjudicationStatus.ADJUDICATED,
                AdjudicationStatus.FINAL,
                AdjudicationStatus.APPEALED,
            )
        ]

        if not events_with_consensus_data:
            return 0.0

        disagreements = sum(1 for e in events_with_consensus_data if e.consensus_required)
        return round(disagreements / len(events_with_consensus_data) * 100.0, 1)

    # ------------------------------------------------------------------
    # Blinded Review Workflow
    # ------------------------------------------------------------------

    def get_blinded_event(self, event_id: str) -> dict | None:
        """Get event data with treatment-arm information redacted for blinded review."""
        with self._lock:
            event = self._events.get(event_id)
            if event is None:
                return None

        # Return event with patient ID anonymized for blinded review
        data = event.model_dump()
        data["patient_id"] = f"BLINDED-{event.patient_id[-4:]}"
        # Remove any treatment arm information from source documents
        data["source_documents"] = [
            doc for doc in data["source_documents"]
            if "treatment" not in doc.lower() and "arm" not in doc.lower()
        ]
        return data

    # ------------------------------------------------------------------
    # Consensus Tracking
    # ------------------------------------------------------------------

    def get_events_requiring_consensus(
        self, trial_id: str | None = None
    ) -> list[AdjudicationEvent]:
        """Get events that require consensus (reviewer disagreement)."""
        with self._lock:
            result = [
                e for e in self._events.values()
                if e.consensus_required
            ]

        if trial_id is not None:
            result = [e for e in result if e.trial_id == trial_id]

        return sorted(result, key=lambda e: e.event_date, reverse=True)

    # ------------------------------------------------------------------
    # Metrics & Dashboard
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> AdjudicationMetrics:
        """Compute aggregated adjudication metrics."""
        with self._lock:
            events = list(self._events.values())

        if trial_id is not None:
            events = [e for e in events if e.trial_id == trial_id]

        # Events by status
        events_by_status: dict[str, int] = {}
        for e in events:
            key = e.status.value
            events_by_status[key] = events_by_status.get(key, 0) + 1

        # Events by classification (only classified events)
        events_by_classification: dict[str, int] = {}
        for e in events:
            if e.classification is not None:
                key = e.classification.value
                events_by_classification[key] = events_by_classification.get(key, 0) + 1

        # Pending events
        events_pending = sum(
            1 for e in events
            if e.status in (AdjudicationStatus.PENDING, AdjudicationStatus.IN_REVIEW)
        )

        # Inter-rater agreement
        kappa = self.calculate_inter_rater_agreement(trial_id=trial_id)

        # Average turnaround
        avg_days = self.calculate_avg_turnaround_days(trial_id=trial_id)

        # Disagreement rate
        disagreement_rate = self.calculate_disagreement_rate(trial_id=trial_id)

        return AdjudicationMetrics(
            total_events=len(events),
            events_by_status=events_by_status,
            events_by_classification=events_by_classification,
            inter_rater_agreement_kappa=kappa,
            avg_adjudication_days=avg_days,
            disagreement_rate=disagreement_rate,
            events_pending=events_pending,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: AdjudicationService | None = None
_instance_lock = threading.Lock()


def get_adjudication_service() -> AdjudicationService:
    """Return the singleton AdjudicationService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = AdjudicationService()
    return _instance


def reset_adjudication_service() -> AdjudicationService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = AdjudicationService()
    return _instance
