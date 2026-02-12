"""Patient Registry & Long-Term Follow-Up Service (PAT-REG).

Manages disease registries, patient enrollment, long-term follow-up visit
tracking, outcome reporting, registry milestones, and operational metrics.

Usage:
    from app.services.patient_registry_service import (
        get_patient_registry_service,
    )

    svc = get_patient_registry_service()
    registries = svc.list_registries()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.patient_registry import (
    EnrollmentStatus,
    FollowUpStatus,
    FollowUpType,
    FollowUpVisit,
    FollowUpVisitCreate,
    FollowUpVisitUpdate,
    OutcomeCategory,
    OutcomeReport,
    OutcomeReportCreate,
    PatientRegistryMetrics,
    Registry,
    RegistryCreate,
    RegistryMilestone,
    RegistryMilestoneCreate,
    RegistryMilestoneUpdate,
    RegistryPatient,
    RegistryPatientCreate,
    RegistryPatientUpdate,
    RegistryStatus,
    RegistryType,
    RegistryUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class PatientRegistryService:
    """In-memory Patient Registry & Long-Term Follow-Up engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._registries: dict[str, Registry] = {}
        self._patients: dict[str, RegistryPatient] = {}
        self._visits: dict[str, FollowUpVisit] = {}
        self._outcomes: dict[str, OutcomeReport] = {}
        self._milestones: dict[str, RegistryMilestone] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic registry data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 10 Registries ---
        registries_data = [
            {
                "id": "REG-001",
                "trial_id": EYLEA_TRIAL,
                "name": "EYLEA DME Disease Registry",
                "registry_type": RegistryType.DISEASE_REGISTRY,
                "disease_area": "Diabetic Macular Edema",
                "description": "Long-term outcomes registry for patients with DME treated with aflibercept",
                "status": RegistryStatus.ACTIVE,
                "sponsor": "Regeneron Pharmaceuticals",
                "target_enrollment": 500,
                "current_enrollment": 342,
                "follow_up_duration_months": 60,
                "countries": ["US", "UK", "DE", "FR", "JP"],
                "sites_count": 45,
                "irb_approved": True,
                "start_date": now - timedelta(days=900),
                "end_date": None,
                "created_at": now - timedelta(days=950),
            },
            {
                "id": "REG-002",
                "trial_id": DUPIXENT_TRIAL,
                "name": "DUPIXENT Atopic Dermatitis Natural History Study",
                "registry_type": RegistryType.NATURAL_HISTORY,
                "disease_area": "Atopic Dermatitis",
                "description": "Natural history study tracking long-term disease progression and treatment patterns in moderate-to-severe AD",
                "status": RegistryStatus.ACTIVE,
                "sponsor": "Regeneron Pharmaceuticals",
                "target_enrollment": 750,
                "current_enrollment": 618,
                "follow_up_duration_months": 48,
                "countries": ["US", "CA", "UK", "DE", "AU"],
                "sites_count": 62,
                "irb_approved": True,
                "start_date": now - timedelta(days=730),
                "end_date": None,
                "created_at": now - timedelta(days=780),
            },
            {
                "id": "REG-003",
                "trial_id": LIBTAYO_TRIAL,
                "name": "LIBTAYO Post-Marketing CSCC Registry",
                "registry_type": RegistryType.POST_MARKETING,
                "disease_area": "Cutaneous Squamous Cell Carcinoma",
                "description": "Post-marketing surveillance registry for cemiplimab in advanced CSCC",
                "status": RegistryStatus.ENROLLING,
                "sponsor": "Regeneron Pharmaceuticals",
                "target_enrollment": 400,
                "current_enrollment": 156,
                "follow_up_duration_months": 36,
                "countries": ["US", "UK", "DE", "IT", "ES"],
                "sites_count": 38,
                "irb_approved": True,
                "start_date": now - timedelta(days=540),
                "end_date": None,
                "created_at": now - timedelta(days=600),
            },
            {
                "id": "REG-004",
                "trial_id": EYLEA_TRIAL,
                "name": "EYLEA Pregnancy Exposure Registry",
                "registry_type": RegistryType.PREGNANCY_REGISTRY,
                "disease_area": "Retinal Diseases",
                "description": "Registry tracking pregnancy outcomes in women exposed to aflibercept",
                "status": RegistryStatus.ACTIVE,
                "sponsor": "Regeneron Pharmaceuticals",
                "target_enrollment": 200,
                "current_enrollment": 87,
                "follow_up_duration_months": 18,
                "countries": ["US", "CA"],
                "sites_count": 28,
                "irb_approved": True,
                "start_date": now - timedelta(days=600),
                "end_date": None,
                "created_at": now - timedelta(days=650),
            },
            {
                "id": "REG-005",
                "trial_id": DUPIXENT_TRIAL,
                "name": "DUPIXENT Asthma Product Registry",
                "registry_type": RegistryType.PRODUCT_REGISTRY,
                "disease_area": "Asthma",
                "description": "Real-world evidence registry for dupilumab in moderate-to-severe asthma",
                "status": RegistryStatus.ACTIVE,
                "sponsor": "Regeneron Pharmaceuticals",
                "target_enrollment": 600,
                "current_enrollment": 445,
                "follow_up_duration_months": 36,
                "countries": ["US", "UK", "FR", "JP"],
                "sites_count": 55,
                "irb_approved": True,
                "start_date": now - timedelta(days=480),
                "end_date": None,
                "created_at": now - timedelta(days=520),
            },
            {
                "id": "REG-006",
                "trial_id": LIBTAYO_TRIAL,
                "name": "LIBTAYO Expanded Access Program Registry",
                "registry_type": RegistryType.EXPANDED_ACCESS,
                "disease_area": "Advanced Solid Tumors",
                "description": "Registry for patients receiving cemiplimab through expanded access",
                "status": RegistryStatus.FOLLOW_UP_ONLY,
                "sponsor": "Regeneron Pharmaceuticals",
                "target_enrollment": 100,
                "current_enrollment": 94,
                "follow_up_duration_months": 24,
                "countries": ["US"],
                "sites_count": 15,
                "irb_approved": True,
                "start_date": now - timedelta(days=800),
                "end_date": now - timedelta(days=200),
                "created_at": now - timedelta(days=850),
            },
            {
                "id": "REG-007",
                "trial_id": EYLEA_TRIAL,
                "name": "Wet AMD Long-Term Outcomes Registry",
                "registry_type": RegistryType.DISEASE_REGISTRY,
                "disease_area": "Wet Age-Related Macular Degeneration",
                "description": "10-year follow-up registry for wet AMD patients treated with anti-VEGF",
                "status": RegistryStatus.ACTIVE,
                "sponsor": "Regeneron Pharmaceuticals",
                "target_enrollment": 800,
                "current_enrollment": 723,
                "follow_up_duration_months": 120,
                "countries": ["US", "UK", "DE", "FR", "JP", "AU"],
                "sites_count": 72,
                "irb_approved": True,
                "start_date": now - timedelta(days=1500),
                "end_date": None,
                "created_at": now - timedelta(days=1550),
            },
            {
                "id": "REG-008",
                "trial_id": DUPIXENT_TRIAL,
                "name": "DUPIXENT CRSwNP Disease Registry",
                "registry_type": RegistryType.DISEASE_REGISTRY,
                "disease_area": "Chronic Rhinosinusitis with Nasal Polyps",
                "description": "Registry for long-term outcomes in CRSwNP patients treated with dupilumab",
                "status": RegistryStatus.ENROLLING,
                "sponsor": "Regeneron Pharmaceuticals",
                "target_enrollment": 350,
                "current_enrollment": 198,
                "follow_up_duration_months": 36,
                "countries": ["US", "UK", "DE"],
                "sites_count": 34,
                "irb_approved": True,
                "start_date": now - timedelta(days=365),
                "end_date": None,
                "created_at": now - timedelta(days=400),
            },
            {
                "id": "REG-009",
                "trial_id": LIBTAYO_TRIAL,
                "name": "LIBTAYO BCC Post-Marketing Registry",
                "registry_type": RegistryType.POST_MARKETING,
                "disease_area": "Basal Cell Carcinoma",
                "description": "Post-marketing registry for cemiplimab in locally advanced BCC",
                "status": RegistryStatus.PLANNING,
                "sponsor": "Regeneron Pharmaceuticals",
                "target_enrollment": 300,
                "current_enrollment": 0,
                "follow_up_duration_months": 36,
                "countries": ["US", "UK"],
                "sites_count": 0,
                "irb_approved": False,
                "start_date": None,
                "end_date": None,
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "REG-010",
                "trial_id": EYLEA_TRIAL,
                "name": "Retinal Vein Occlusion Closed Registry",
                "registry_type": RegistryType.DISEASE_REGISTRY,
                "disease_area": "Retinal Vein Occlusion",
                "description": "Completed registry for RVO patients treated with aflibercept",
                "status": RegistryStatus.CLOSED,
                "sponsor": "Regeneron Pharmaceuticals",
                "target_enrollment": 250,
                "current_enrollment": 248,
                "follow_up_duration_months": 36,
                "countries": ["US", "UK", "DE"],
                "sites_count": 30,
                "irb_approved": True,
                "start_date": now - timedelta(days=1800),
                "end_date": now - timedelta(days=100),
                "created_at": now - timedelta(days=1850),
            },
        ]

        for r in registries_data:
            self._registries[r["id"]] = Registry(**r)

        # --- 12 Registry Patients ---
        patients_data = [
            {
                "id": "RPAT-001",
                "registry_id": "REG-001",
                "patient_id": "PAT-10001",
                "site_id": "SITE-101",
                "enrollment_status": EnrollmentStatus.ACTIVE,
                "consent_date": now - timedelta(days=850),
                "enrollment_date": now - timedelta(days=845),
                "last_follow_up_date": now - timedelta(days=30),
                "next_follow_up_date": now + timedelta(days=60),
                "follow_up_visits_completed": 8,
                "follow_up_visits_missed": 0,
                "notes": "Stable visual acuity improvement maintained",
            },
            {
                "id": "RPAT-002",
                "registry_id": "REG-001",
                "patient_id": "PAT-10002",
                "site_id": "SITE-102",
                "enrollment_status": EnrollmentStatus.ACTIVE,
                "consent_date": now - timedelta(days=800),
                "enrollment_date": now - timedelta(days=795),
                "last_follow_up_date": now - timedelta(days=45),
                "next_follow_up_date": now + timedelta(days=45),
                "follow_up_visits_completed": 7,
                "follow_up_visits_missed": 1,
                "notes": "Missed Month-18 visit, rescheduled",
            },
            {
                "id": "RPAT-003",
                "registry_id": "REG-001",
                "patient_id": "PAT-10003",
                "site_id": "SITE-103",
                "enrollment_status": EnrollmentStatus.LOST_TO_FOLLOW_UP,
                "consent_date": now - timedelta(days=700),
                "enrollment_date": now - timedelta(days=695),
                "last_follow_up_date": now - timedelta(days=180),
                "next_follow_up_date": None,
                "follow_up_visits_completed": 4,
                "follow_up_visits_missed": 3,
                "notes": "Unreachable since Month-12 visit",
            },
            {
                "id": "RPAT-004",
                "registry_id": "REG-002",
                "patient_id": "PAT-20001",
                "site_id": "SITE-104",
                "enrollment_status": EnrollmentStatus.ACTIVE,
                "consent_date": now - timedelta(days=700),
                "enrollment_date": now - timedelta(days=695),
                "last_follow_up_date": now - timedelta(days=20),
                "next_follow_up_date": now + timedelta(days=70),
                "follow_up_visits_completed": 6,
                "follow_up_visits_missed": 0,
                "notes": "EASI-75 response maintained through Month-24",
            },
            {
                "id": "RPAT-005",
                "registry_id": "REG-002",
                "patient_id": "PAT-20002",
                "site_id": "SITE-105",
                "enrollment_status": EnrollmentStatus.WITHDRAWN,
                "consent_date": now - timedelta(days=600),
                "enrollment_date": now - timedelta(days=595),
                "last_follow_up_date": now - timedelta(days=200),
                "next_follow_up_date": None,
                "follow_up_visits_completed": 3,
                "follow_up_visits_missed": 0,
                "withdrawal_reason": "Relocated to different city",
                "withdrawal_date": now - timedelta(days=200),
                "notes": "Patient withdrew voluntarily after relocation",
            },
            {
                "id": "RPAT-006",
                "registry_id": "REG-002",
                "patient_id": "PAT-20003",
                "site_id": "SITE-106",
                "enrollment_status": EnrollmentStatus.COMPLETED,
                "consent_date": now - timedelta(days=730),
                "enrollment_date": now - timedelta(days=725),
                "last_follow_up_date": now - timedelta(days=5),
                "next_follow_up_date": None,
                "follow_up_visits_completed": 8,
                "follow_up_visits_missed": 0,
                "notes": "Completed all 48-month follow-up visits",
            },
            {
                "id": "RPAT-007",
                "registry_id": "REG-003",
                "patient_id": "PAT-30001",
                "site_id": "SITE-101",
                "enrollment_status": EnrollmentStatus.ACTIVE,
                "consent_date": now - timedelta(days=400),
                "enrollment_date": now - timedelta(days=395),
                "last_follow_up_date": now - timedelta(days=15),
                "next_follow_up_date": now + timedelta(days=75),
                "follow_up_visits_completed": 4,
                "follow_up_visits_missed": 0,
                "notes": "Partial response, ongoing monitoring",
            },
            {
                "id": "RPAT-008",
                "registry_id": "REG-003",
                "patient_id": "PAT-30002",
                "site_id": "SITE-107",
                "enrollment_status": EnrollmentStatus.DECEASED,
                "consent_date": now - timedelta(days=350),
                "enrollment_date": now - timedelta(days=345),
                "last_follow_up_date": now - timedelta(days=60),
                "next_follow_up_date": None,
                "follow_up_visits_completed": 3,
                "follow_up_visits_missed": 0,
                "notes": "Disease progression; death recorded at Month-10",
            },
            {
                "id": "RPAT-009",
                "registry_id": "REG-003",
                "patient_id": "PAT-30003",
                "site_id": "SITE-108",
                "enrollment_status": EnrollmentStatus.ENROLLED,
                "consent_date": now - timedelta(days=30),
                "enrollment_date": now - timedelta(days=25),
                "last_follow_up_date": None,
                "next_follow_up_date": now + timedelta(days=65),
                "follow_up_visits_completed": 0,
                "follow_up_visits_missed": 0,
                "notes": "Recently enrolled, baseline visit pending",
            },
            {
                "id": "RPAT-010",
                "registry_id": "REG-001",
                "patient_id": "PAT-10004",
                "site_id": "SITE-101",
                "enrollment_status": EnrollmentStatus.SCREENED,
                "consent_date": None,
                "enrollment_date": None,
                "last_follow_up_date": None,
                "next_follow_up_date": None,
                "follow_up_visits_completed": 0,
                "follow_up_visits_missed": 0,
                "notes": "Screening in progress",
            },
            {
                "id": "RPAT-011",
                "registry_id": "REG-005",
                "patient_id": "PAT-50001",
                "site_id": "SITE-102",
                "enrollment_status": EnrollmentStatus.ACTIVE,
                "consent_date": now - timedelta(days=400),
                "enrollment_date": now - timedelta(days=395),
                "last_follow_up_date": now - timedelta(days=10),
                "next_follow_up_date": now + timedelta(days=80),
                "follow_up_visits_completed": 5,
                "follow_up_visits_missed": 0,
                "notes": "Significant improvement in FEV1",
            },
            {
                "id": "RPAT-012",
                "registry_id": "REG-007",
                "patient_id": "PAT-70001",
                "site_id": "SITE-103",
                "enrollment_status": EnrollmentStatus.CONSENTED,
                "consent_date": now - timedelta(days=10),
                "enrollment_date": None,
                "last_follow_up_date": None,
                "next_follow_up_date": None,
                "follow_up_visits_completed": 0,
                "follow_up_visits_missed": 0,
                "notes": "Consent obtained, pending enrollment",
            },
        ]

        for p in patients_data:
            self._patients[p["id"]] = RegistryPatient(**p)

        # --- 14 Follow-Up Visits ---
        visits_data = [
            {
                "id": "FUV-001",
                "registry_patient_id": "RPAT-001",
                "visit_type": FollowUpType.SCHEDULED,
                "visit_number": 1,
                "scheduled_date": now - timedelta(days=750),
                "actual_date": now - timedelta(days=749),
                "status": FollowUpStatus.COMPLETED,
                "assessments_completed": ["BCVA", "OCT", "Fundoscopy"],
                "adverse_events_reported": 0,
                "data_complete": True,
                "conducted_by": "Dr. Sarah Chen",
                "notes": "Baseline visit completed successfully",
            },
            {
                "id": "FUV-002",
                "registry_patient_id": "RPAT-001",
                "visit_type": FollowUpType.SCHEDULED,
                "visit_number": 2,
                "scheduled_date": now - timedelta(days=660),
                "actual_date": now - timedelta(days=658),
                "status": FollowUpStatus.COMPLETED,
                "assessments_completed": ["BCVA", "OCT"],
                "adverse_events_reported": 0,
                "data_complete": True,
                "conducted_by": "Dr. Sarah Chen",
                "notes": "Month-3 visit, visual acuity improved",
            },
            {
                "id": "FUV-003",
                "registry_patient_id": "RPAT-001",
                "visit_type": FollowUpType.ANNUAL_REVIEW,
                "visit_number": 3,
                "scheduled_date": now - timedelta(days=390),
                "actual_date": now - timedelta(days=388),
                "status": FollowUpStatus.COMPLETED,
                "assessments_completed": ["BCVA", "OCT", "Fundoscopy", "FA"],
                "adverse_events_reported": 1,
                "data_complete": True,
                "conducted_by": "Dr. Sarah Chen",
                "notes": "Year-1 comprehensive review",
            },
            {
                "id": "FUV-004",
                "registry_patient_id": "RPAT-001",
                "visit_type": FollowUpType.SCHEDULED,
                "visit_number": 4,
                "scheduled_date": now + timedelta(days=60),
                "actual_date": None,
                "status": FollowUpStatus.SCHEDULED,
                "assessments_completed": [],
                "adverse_events_reported": 0,
                "data_complete": False,
                "conducted_by": None,
                "notes": None,
            },
            {
                "id": "FUV-005",
                "registry_patient_id": "RPAT-002",
                "visit_type": FollowUpType.SCHEDULED,
                "visit_number": 1,
                "scheduled_date": now - timedelta(days=700),
                "actual_date": now - timedelta(days=698),
                "status": FollowUpStatus.COMPLETED,
                "assessments_completed": ["BCVA", "OCT"],
                "adverse_events_reported": 0,
                "data_complete": True,
                "conducted_by": "Dr. Michael Park",
                "notes": "Baseline visit",
            },
            {
                "id": "FUV-006",
                "registry_patient_id": "RPAT-002",
                "visit_type": FollowUpType.SCHEDULED,
                "visit_number": 2,
                "scheduled_date": now - timedelta(days=520),
                "actual_date": None,
                "status": FollowUpStatus.MISSED,
                "assessments_completed": [],
                "adverse_events_reported": 0,
                "data_complete": False,
                "conducted_by": None,
                "notes": "Patient did not attend Month-18 visit",
            },
            {
                "id": "FUV-007",
                "registry_patient_id": "RPAT-004",
                "visit_type": FollowUpType.SCHEDULED,
                "visit_number": 1,
                "scheduled_date": now - timedelta(days=600),
                "actual_date": now - timedelta(days=598),
                "status": FollowUpStatus.COMPLETED,
                "assessments_completed": ["EASI", "SCORAD", "DLQI", "IGA"],
                "adverse_events_reported": 0,
                "data_complete": True,
                "conducted_by": "Dr. Lisa Yamamoto",
                "notes": "Baseline AD assessment completed",
            },
            {
                "id": "FUV-008",
                "registry_patient_id": "RPAT-004",
                "visit_type": FollowUpType.SAFETY,
                "visit_number": 2,
                "scheduled_date": now - timedelta(days=450),
                "actual_date": now - timedelta(days=448),
                "status": FollowUpStatus.COMPLETED,
                "assessments_completed": ["EASI", "Safety Labs"],
                "adverse_events_reported": 1,
                "data_complete": True,
                "conducted_by": "Dr. Lisa Yamamoto",
                "notes": "Safety visit following mild injection site reaction",
            },
            {
                "id": "FUV-009",
                "registry_patient_id": "RPAT-007",
                "visit_type": FollowUpType.SCHEDULED,
                "visit_number": 1,
                "scheduled_date": now - timedelta(days=300),
                "actual_date": now - timedelta(days=298),
                "status": FollowUpStatus.COMPLETED,
                "assessments_completed": ["CT scan", "Blood panel", "Physical exam"],
                "adverse_events_reported": 2,
                "data_complete": True,
                "conducted_by": "Dr. James Wilson",
                "notes": "Baseline CSCC assessment",
            },
            {
                "id": "FUV-010",
                "registry_patient_id": "RPAT-007",
                "visit_type": FollowUpType.MILESTONE,
                "visit_number": 2,
                "scheduled_date": now - timedelta(days=210),
                "actual_date": now - timedelta(days=208),
                "status": FollowUpStatus.COMPLETED,
                "assessments_completed": ["CT scan", "Tumor measurement"],
                "adverse_events_reported": 0,
                "data_complete": True,
                "conducted_by": "Dr. James Wilson",
                "notes": "Month-3 tumor response assessment",
            },
            {
                "id": "FUV-011",
                "registry_patient_id": "RPAT-003",
                "visit_type": FollowUpType.SCHEDULED,
                "visit_number": 1,
                "scheduled_date": now - timedelta(days=600),
                "actual_date": now - timedelta(days=598),
                "status": FollowUpStatus.COMPLETED,
                "assessments_completed": ["BCVA", "OCT"],
                "adverse_events_reported": 0,
                "data_complete": True,
                "conducted_by": "Dr. Sarah Chen",
                "notes": "Initial follow-up",
            },
            {
                "id": "FUV-012",
                "registry_patient_id": "RPAT-003",
                "visit_type": FollowUpType.SCHEDULED,
                "visit_number": 2,
                "scheduled_date": now - timedelta(days=350),
                "actual_date": None,
                "status": FollowUpStatus.OVERDUE,
                "assessments_completed": [],
                "adverse_events_reported": 0,
                "data_complete": False,
                "conducted_by": None,
                "notes": "Patient unreachable",
            },
            {
                "id": "FUV-013",
                "registry_patient_id": "RPAT-006",
                "visit_type": FollowUpType.END_OF_STUDY,
                "visit_number": 8,
                "scheduled_date": now - timedelta(days=10),
                "actual_date": now - timedelta(days=5),
                "status": FollowUpStatus.COMPLETED,
                "assessments_completed": ["EASI", "SCORAD", "DLQI", "IGA", "Safety Labs", "Physical Exam"],
                "adverse_events_reported": 0,
                "data_complete": True,
                "conducted_by": "Dr. Maria Gonzalez",
                "notes": "End-of-study visit, all assessments complete",
            },
            {
                "id": "FUV-014",
                "registry_patient_id": "RPAT-011",
                "visit_type": FollowUpType.UNSCHEDULED,
                "visit_number": 6,
                "scheduled_date": now - timedelta(days=15),
                "actual_date": now - timedelta(days=10),
                "status": FollowUpStatus.COMPLETED,
                "assessments_completed": ["Spirometry", "FeNO"],
                "adverse_events_reported": 1,
                "data_complete": False,
                "conducted_by": "Dr. Robert Kim",
                "notes": "Unscheduled visit for asthma exacerbation",
            },
        ]

        for v in visits_data:
            self._visits[v["id"]] = FollowUpVisit(**v)

        # --- 12 Outcome Reports ---
        outcomes_data = [
            {
                "id": "OUT-001",
                "registry_patient_id": "RPAT-001",
                "visit_id": "FUV-001",
                "category": OutcomeCategory.PRIMARY,
                "outcome_name": "Best Corrected Visual Acuity (BCVA)",
                "value": "68",
                "unit": "ETDRS letters",
                "baseline_value": "55",
                "change_from_baseline": "+13",
                "clinically_significant": True,
                "reported_date": now - timedelta(days=749),
                "reported_by": "Dr. Sarah Chen",
            },
            {
                "id": "OUT-002",
                "registry_patient_id": "RPAT-001",
                "visit_id": "FUV-003",
                "category": OutcomeCategory.PRIMARY,
                "outcome_name": "Best Corrected Visual Acuity (BCVA)",
                "value": "72",
                "unit": "ETDRS letters",
                "baseline_value": "55",
                "change_from_baseline": "+17",
                "clinically_significant": True,
                "reported_date": now - timedelta(days=388),
                "reported_by": "Dr. Sarah Chen",
            },
            {
                "id": "OUT-003",
                "registry_patient_id": "RPAT-001",
                "visit_id": "FUV-003",
                "category": OutcomeCategory.SECONDARY,
                "outcome_name": "Central Subfield Thickness (CST)",
                "value": "285",
                "unit": "microns",
                "baseline_value": "410",
                "change_from_baseline": "-125",
                "clinically_significant": True,
                "reported_date": now - timedelta(days=388),
                "reported_by": "Dr. Sarah Chen",
            },
            {
                "id": "OUT-004",
                "registry_patient_id": "RPAT-004",
                "visit_id": "FUV-007",
                "category": OutcomeCategory.PRIMARY,
                "outcome_name": "EASI Score",
                "value": "8.2",
                "unit": "points",
                "baseline_value": "28.5",
                "change_from_baseline": "-20.3",
                "clinically_significant": True,
                "reported_date": now - timedelta(days=598),
                "reported_by": "Dr. Lisa Yamamoto",
            },
            {
                "id": "OUT-005",
                "registry_patient_id": "RPAT-004",
                "visit_id": "FUV-007",
                "category": OutcomeCategory.PATIENT_REPORTED,
                "outcome_name": "DLQI Score",
                "value": "5",
                "unit": "points",
                "baseline_value": "18",
                "change_from_baseline": "-13",
                "clinically_significant": True,
                "reported_date": now - timedelta(days=598),
                "reported_by": "Dr. Lisa Yamamoto",
            },
            {
                "id": "OUT-006",
                "registry_patient_id": "RPAT-004",
                "visit_id": "FUV-008",
                "category": OutcomeCategory.SAFETY,
                "outcome_name": "Injection Site Reaction",
                "value": "Mild",
                "unit": None,
                "baseline_value": None,
                "change_from_baseline": None,
                "clinically_significant": False,
                "reported_date": now - timedelta(days=448),
                "reported_by": "Dr. Lisa Yamamoto",
            },
            {
                "id": "OUT-007",
                "registry_patient_id": "RPAT-007",
                "visit_id": "FUV-009",
                "category": OutcomeCategory.PRIMARY,
                "outcome_name": "Tumor Response (RECIST 1.1)",
                "value": "Partial Response",
                "unit": None,
                "baseline_value": "Target lesion 45mm",
                "change_from_baseline": "-35%",
                "clinically_significant": True,
                "reported_date": now - timedelta(days=298),
                "reported_by": "Dr. James Wilson",
            },
            {
                "id": "OUT-008",
                "registry_patient_id": "RPAT-007",
                "visit_id": "FUV-009",
                "category": OutcomeCategory.BIOMARKER,
                "outcome_name": "PD-L1 Expression (CPS)",
                "value": "42",
                "unit": "CPS",
                "baseline_value": "38",
                "change_from_baseline": "+4",
                "clinically_significant": False,
                "reported_date": now - timedelta(days=298),
                "reported_by": "Dr. James Wilson",
            },
            {
                "id": "OUT-009",
                "registry_patient_id": "RPAT-008",
                "visit_id": None,
                "category": OutcomeCategory.SURVIVAL,
                "outcome_name": "Overall Survival",
                "value": "10 months",
                "unit": "months",
                "baseline_value": None,
                "change_from_baseline": None,
                "clinically_significant": True,
                "reported_date": now - timedelta(days=60),
                "reported_by": "Dr. James Wilson",
            },
            {
                "id": "OUT-010",
                "registry_patient_id": "RPAT-006",
                "visit_id": "FUV-013",
                "category": OutcomeCategory.PRIMARY,
                "outcome_name": "EASI Score",
                "value": "3.1",
                "unit": "points",
                "baseline_value": "32.0",
                "change_from_baseline": "-28.9",
                "clinically_significant": True,
                "reported_date": now - timedelta(days=5),
                "reported_by": "Dr. Maria Gonzalez",
            },
            {
                "id": "OUT-011",
                "registry_patient_id": "RPAT-011",
                "visit_id": "FUV-014",
                "category": OutcomeCategory.SECONDARY,
                "outcome_name": "FEV1 % Predicted",
                "value": "78",
                "unit": "%",
                "baseline_value": "62",
                "change_from_baseline": "+16",
                "clinically_significant": True,
                "reported_date": now - timedelta(days=10),
                "reported_by": "Dr. Robert Kim",
            },
            {
                "id": "OUT-012",
                "registry_patient_id": "RPAT-011",
                "visit_id": "FUV-014",
                "category": OutcomeCategory.BIOMARKER,
                "outcome_name": "Blood Eosinophil Count",
                "value": "180",
                "unit": "cells/uL",
                "baseline_value": "520",
                "change_from_baseline": "-340",
                "clinically_significant": True,
                "reported_date": now - timedelta(days=10),
                "reported_by": "Dr. Robert Kim",
            },
        ]

        for o in outcomes_data:
            self._outcomes[o["id"]] = OutcomeReport(**o)

        # --- 10 Registry Milestones ---
        milestones_data = [
            {
                "id": "RMS-001",
                "registry_id": "REG-001",
                "milestone_name": "IRB Approval",
                "description": "Obtain central IRB approval for the DME registry protocol",
                "target_date": now - timedelta(days=960),
                "actual_date": now - timedelta(days=955),
                "achieved": True,
                "responsible_person": "Dr. Emily Watson",
                "notes": "Approved with minor protocol amendments",
            },
            {
                "id": "RMS-002",
                "registry_id": "REG-001",
                "milestone_name": "First Patient Enrolled",
                "description": "Enroll the first patient in the DME disease registry",
                "target_date": now - timedelta(days=880),
                "actual_date": now - timedelta(days=850),
                "achieved": True,
                "responsible_person": "Dr. Emily Watson",
                "notes": "First patient enrolled at SITE-101",
            },
            {
                "id": "RMS-003",
                "registry_id": "REG-001",
                "milestone_name": "50% Enrollment Target",
                "description": "Reach 250 enrolled patients (50% of target)",
                "target_date": now - timedelta(days=450),
                "actual_date": now - timedelta(days=420),
                "achieved": True,
                "responsible_person": "Clinical Operations Team",
                "notes": "250 patients enrolled across 38 sites",
            },
            {
                "id": "RMS-004",
                "registry_id": "REG-001",
                "milestone_name": "Target Enrollment Complete",
                "description": "Reach 500 enrolled patients (100% of target)",
                "target_date": now + timedelta(days=180),
                "actual_date": None,
                "achieved": False,
                "responsible_person": "Clinical Operations Team",
                "notes": "Currently at 342/500 (68.4%)",
            },
            {
                "id": "RMS-005",
                "registry_id": "REG-002",
                "milestone_name": "First Patient Enrolled",
                "description": "Enroll the first patient in the AD natural history study",
                "target_date": now - timedelta(days=720),
                "actual_date": now - timedelta(days=725),
                "achieved": True,
                "responsible_person": "Dr. Mark Thompson",
                "notes": "Enrolled ahead of schedule",
            },
            {
                "id": "RMS-006",
                "registry_id": "REG-002",
                "milestone_name": "Interim Analysis",
                "description": "Complete interim analysis at 50% enrollment with 12-month follow-up",
                "target_date": now - timedelta(days=180),
                "actual_date": now - timedelta(days=175),
                "achieved": True,
                "responsible_person": "Biostatistics Team",
                "notes": "Interim results presented at AAD 2025",
            },
            {
                "id": "RMS-007",
                "registry_id": "REG-003",
                "milestone_name": "First Patient Enrolled",
                "description": "Enroll the first patient in the CSCC post-marketing registry",
                "target_date": now - timedelta(days=520),
                "actual_date": now - timedelta(days=510),
                "achieved": True,
                "responsible_person": "Dr. Anne Richards",
                "notes": "First patient at major oncology center",
            },
            {
                "id": "RMS-008",
                "registry_id": "REG-003",
                "milestone_name": "Safety Database Lock",
                "description": "Complete first annual safety database lock",
                "target_date": now + timedelta(days=60),
                "actual_date": None,
                "achieved": False,
                "responsible_person": "Pharmacovigilance Team",
                "notes": "On track for completion",
            },
            {
                "id": "RMS-009",
                "registry_id": "REG-005",
                "milestone_name": "Real-World Data Report",
                "description": "Publish first real-world evidence report for dupilumab asthma",
                "target_date": now - timedelta(days=60),
                "actual_date": now - timedelta(days=45),
                "achieved": True,
                "responsible_person": "Medical Affairs Team",
                "notes": "Published in JAMA",
            },
            {
                "id": "RMS-010",
                "registry_id": "REG-007",
                "milestone_name": "5-Year Follow-Up Complete",
                "description": "Complete 5-year follow-up data collection for initial cohort",
                "target_date": now - timedelta(days=200),
                "actual_date": now - timedelta(days=190),
                "achieved": True,
                "responsible_person": "Dr. Emily Watson",
                "notes": "5-year data available for 412 patients",
            },
        ]

        for m in milestones_data:
            self._milestones[m["id"]] = RegistryMilestone(**m)

    # ------------------------------------------------------------------
    # Registry CRUD
    # ------------------------------------------------------------------

    def list_registries(
        self,
        *,
        trial_id: str | None = None,
        registry_type: RegistryType | None = None,
        status: RegistryStatus | None = None,
    ) -> list[Registry]:
        """List registries with optional filters."""
        with self._lock:
            result = list(self._registries.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if registry_type is not None:
            result = [r for r in result if r.registry_type == registry_type]
        if status is not None:
            result = [r for r in result if r.status == status]

        return sorted(result, key=lambda r: r.created_at, reverse=True)

    def get_registry(self, registry_id: str) -> Registry | None:
        """Get a single registry by ID."""
        with self._lock:
            return self._registries.get(registry_id)

    def create_registry(self, payload: RegistryCreate) -> Registry:
        """Create a new registry."""
        now = datetime.now(timezone.utc)
        registry_id = f"REG-{uuid4().hex[:8].upper()}"
        registry = Registry(
            id=registry_id,
            trial_id=payload.trial_id,
            name=payload.name,
            registry_type=payload.registry_type,
            disease_area=payload.disease_area,
            description=payload.description,
            status=RegistryStatus.PLANNING,
            sponsor=payload.sponsor,
            target_enrollment=payload.target_enrollment,
            current_enrollment=0,
            follow_up_duration_months=payload.follow_up_duration_months,
            countries=payload.countries,
            sites_count=0,
            irb_approved=False,
            start_date=None,
            end_date=None,
            created_at=now,
        )
        with self._lock:
            self._registries[registry_id] = registry
        logger.info("Created registry %s: %s", registry_id, payload.name)
        return registry

    def update_registry(self, registry_id: str, payload: RegistryUpdate) -> Registry | None:
        """Update an existing registry."""
        with self._lock:
            existing = self._registries.get(registry_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = Registry(**data)
            self._registries[registry_id] = updated
        return updated

    def delete_registry(self, registry_id: str) -> bool:
        """Delete a registry. Returns True if deleted, False if not found."""
        with self._lock:
            if registry_id in self._registries:
                del self._registries[registry_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Registry Patient CRUD
    # ------------------------------------------------------------------

    def list_patients(
        self,
        *,
        registry_id: str | None = None,
        enrollment_status: EnrollmentStatus | None = None,
        patient_id: str | None = None,
    ) -> list[RegistryPatient]:
        """List registry patients with optional filters."""
        with self._lock:
            result = list(self._patients.values())

        if registry_id is not None:
            result = [p for p in result if p.registry_id == registry_id]
        if enrollment_status is not None:
            result = [p for p in result if p.enrollment_status == enrollment_status]
        if patient_id is not None:
            result = [p for p in result if p.patient_id == patient_id]

        return sorted(result, key=lambda p: p.id)

    def get_patient(self, patient_id: str) -> RegistryPatient | None:
        """Get a single registry patient by ID."""
        with self._lock:
            return self._patients.get(patient_id)

    def create_patient(self, payload: RegistryPatientCreate) -> RegistryPatient:
        """Enroll a patient in a registry. Validates registry_id exists."""
        with self._lock:
            if payload.registry_id not in self._registries:
                raise ValueError(f"Registry '{payload.registry_id}' not found")

        patient_id = f"RPAT-{uuid4().hex[:8].upper()}"
        patient = RegistryPatient(
            id=patient_id,
            registry_id=payload.registry_id,
            patient_id=payload.patient_id,
            site_id=payload.site_id,
            enrollment_status=EnrollmentStatus.SCREENED,
        )
        with self._lock:
            self._patients[patient_id] = patient
        logger.info("Created registry patient %s in registry %s", patient_id, payload.registry_id)
        return patient

    def update_patient(self, patient_id: str, payload: RegistryPatientUpdate) -> RegistryPatient | None:
        """Update a registry patient."""
        with self._lock:
            existing = self._patients.get(patient_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = RegistryPatient(**data)
            self._patients[patient_id] = updated
        return updated

    def delete_patient(self, patient_id: str) -> bool:
        """Delete a registry patient. Returns True if deleted."""
        with self._lock:
            if patient_id in self._patients:
                del self._patients[patient_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Follow-Up Visit CRUD
    # ------------------------------------------------------------------

    def list_visits(
        self,
        *,
        registry_patient_id: str | None = None,
        visit_type: FollowUpType | None = None,
        visit_status: FollowUpStatus | None = None,
    ) -> list[FollowUpVisit]:
        """List follow-up visits with optional filters."""
        with self._lock:
            result = list(self._visits.values())

        if registry_patient_id is not None:
            result = [v for v in result if v.registry_patient_id == registry_patient_id]
        if visit_type is not None:
            result = [v for v in result if v.visit_type == visit_type]
        if visit_status is not None:
            result = [v for v in result if v.status == visit_status]

        return sorted(result, key=lambda v: v.scheduled_date, reverse=True)

    def get_visit(self, visit_id: str) -> FollowUpVisit | None:
        """Get a single follow-up visit by ID."""
        with self._lock:
            return self._visits.get(visit_id)

    def create_visit(self, payload: FollowUpVisitCreate) -> FollowUpVisit:
        """Create a follow-up visit. Validates registry_patient_id exists."""
        with self._lock:
            if payload.registry_patient_id not in self._patients:
                raise ValueError(f"Registry patient '{payload.registry_patient_id}' not found")

        visit_id = f"FUV-{uuid4().hex[:8].upper()}"
        visit = FollowUpVisit(
            id=visit_id,
            registry_patient_id=payload.registry_patient_id,
            visit_type=payload.visit_type,
            visit_number=payload.visit_number,
            scheduled_date=payload.scheduled_date,
            status=FollowUpStatus.SCHEDULED,
        )
        with self._lock:
            self._visits[visit_id] = visit
        logger.info("Created follow-up visit %s for patient %s", visit_id, payload.registry_patient_id)
        return visit

    def update_visit(self, visit_id: str, payload: FollowUpVisitUpdate) -> FollowUpVisit | None:
        """Update a follow-up visit."""
        with self._lock:
            existing = self._visits.get(visit_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = FollowUpVisit(**data)
            self._visits[visit_id] = updated
        return updated

    def delete_visit(self, visit_id: str) -> bool:
        """Delete a follow-up visit. Returns True if deleted."""
        with self._lock:
            if visit_id in self._visits:
                del self._visits[visit_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Outcome Report CRUD
    # ------------------------------------------------------------------

    def list_outcomes(
        self,
        *,
        registry_patient_id: str | None = None,
        category: OutcomeCategory | None = None,
    ) -> list[OutcomeReport]:
        """List outcome reports with optional filters."""
        with self._lock:
            result = list(self._outcomes.values())

        if registry_patient_id is not None:
            result = [o for o in result if o.registry_patient_id == registry_patient_id]
        if category is not None:
            result = [o for o in result if o.category == category]

        return sorted(result, key=lambda o: o.reported_date, reverse=True)

    def get_outcome(self, outcome_id: str) -> OutcomeReport | None:
        """Get a single outcome report by ID."""
        with self._lock:
            return self._outcomes.get(outcome_id)

    def create_outcome(self, payload: OutcomeReportCreate) -> OutcomeReport:
        """Create an outcome report. Validates registry_patient_id exists."""
        with self._lock:
            if payload.registry_patient_id not in self._patients:
                raise ValueError(f"Registry patient '{payload.registry_patient_id}' not found")

        now = datetime.now(timezone.utc)
        outcome_id = f"OUT-{uuid4().hex[:8].upper()}"
        outcome = OutcomeReport(
            id=outcome_id,
            registry_patient_id=payload.registry_patient_id,
            visit_id=payload.visit_id,
            category=payload.category,
            outcome_name=payload.outcome_name,
            value=payload.value,
            unit=payload.unit,
            baseline_value=payload.baseline_value,
            change_from_baseline=payload.change_from_baseline,
            clinically_significant=payload.clinically_significant,
            reported_date=now,
            reported_by=payload.reported_by,
        )
        with self._lock:
            self._outcomes[outcome_id] = outcome
        logger.info("Created outcome report %s for patient %s", outcome_id, payload.registry_patient_id)
        return outcome

    def delete_outcome(self, outcome_id: str) -> bool:
        """Delete an outcome report. Returns True if deleted."""
        with self._lock:
            if outcome_id in self._outcomes:
                del self._outcomes[outcome_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Registry Milestone CRUD
    # ------------------------------------------------------------------

    def list_milestones(
        self,
        *,
        registry_id: str | None = None,
    ) -> list[RegistryMilestone]:
        """List registry milestones with optional filters."""
        with self._lock:
            result = list(self._milestones.values())

        if registry_id is not None:
            result = [m for m in result if m.registry_id == registry_id]

        return sorted(result, key=lambda m: m.target_date)

    def get_milestone(self, milestone_id: str) -> RegistryMilestone | None:
        """Get a single milestone by ID."""
        with self._lock:
            return self._milestones.get(milestone_id)

    def create_milestone(self, payload: RegistryMilestoneCreate) -> RegistryMilestone:
        """Create a registry milestone. Validates registry_id exists."""
        with self._lock:
            if payload.registry_id not in self._registries:
                raise ValueError(f"Registry '{payload.registry_id}' not found")

        milestone_id = f"RMS-{uuid4().hex[:8].upper()}"
        milestone = RegistryMilestone(
            id=milestone_id,
            registry_id=payload.registry_id,
            milestone_name=payload.milestone_name,
            description=payload.description,
            target_date=payload.target_date,
            actual_date=None,
            achieved=False,
            responsible_person=payload.responsible_person,
            notes=None,
        )
        with self._lock:
            self._milestones[milestone_id] = milestone
        logger.info("Created milestone %s for registry %s", milestone_id, payload.registry_id)
        return milestone

    def update_milestone(self, milestone_id: str, payload: RegistryMilestoneUpdate) -> RegistryMilestone | None:
        """Update a registry milestone."""
        with self._lock:
            existing = self._milestones.get(milestone_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = RegistryMilestone(**data)
            self._milestones[milestone_id] = updated
        return updated

    def delete_milestone(self, milestone_id: str) -> bool:
        """Delete a registry milestone. Returns True if deleted."""
        with self._lock:
            if milestone_id in self._milestones:
                del self._milestones[milestone_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> PatientRegistryMetrics:
        """Compute aggregated patient registry operational metrics."""
        with self._lock:
            registries = list(self._registries.values())
            patients = list(self._patients.values())
            visits = list(self._visits.values())
            outcomes = list(self._outcomes.values())
            milestones = list(self._milestones.values())

        # Registries by type and status
        registries_by_type: dict[str, int] = {}
        registries_by_status: dict[str, int] = {}
        for r in registries:
            key_type = r.registry_type.value
            registries_by_type[key_type] = registries_by_type.get(key_type, 0) + 1
            key_status = r.status.value
            registries_by_status[key_status] = registries_by_status.get(key_status, 0) + 1

        # Patients by status
        patients_by_status: dict[str, int] = {}
        active_patients = 0
        lost_to_follow_up = 0
        for p in patients:
            key = p.enrollment_status.value
            patients_by_status[key] = patients_by_status.get(key, 0) + 1
            if p.enrollment_status == EnrollmentStatus.ACTIVE:
                active_patients += 1
            if p.enrollment_status == EnrollmentStatus.LOST_TO_FOLLOW_UP:
                lost_to_follow_up += 1

        # Visits by status
        visits_by_status: dict[str, int] = {}
        completed_visits = 0
        for v in visits:
            key = v.status.value
            visits_by_status[key] = visits_by_status.get(key, 0) + 1
            if v.status == FollowUpStatus.COMPLETED:
                completed_visits += 1

        # Visit completion rate = (completed / total) * 100
        total_visits = len(visits)
        visit_completion_rate = (completed_visits / total_visits * 100) if total_visits > 0 else 0.0

        # Outcomes by category
        outcomes_by_category: dict[str, int] = {}
        for o in outcomes:
            key = o.category.value
            outcomes_by_category[key] = outcomes_by_category.get(key, 0) + 1

        # Milestones
        milestones_achieved = sum(1 for m in milestones if m.achieved)

        # Retention rate = (active + completed) / (total - screened) * 100
        screened_count = sum(1 for p in patients if p.enrollment_status == EnrollmentStatus.SCREENED)
        completed_count = sum(1 for p in patients if p.enrollment_status == EnrollmentStatus.COMPLETED)
        denominator = len(patients) - screened_count
        retention_rate = ((active_patients + completed_count) / denominator * 100) if denominator > 0 else 0.0

        return PatientRegistryMetrics(
            total_registries=len(registries),
            registries_by_type=registries_by_type,
            registries_by_status=registries_by_status,
            total_patients=len(patients),
            patients_by_status=patients_by_status,
            active_patients=active_patients,
            lost_to_follow_up=lost_to_follow_up,
            total_follow_up_visits=total_visits,
            visits_by_status=visits_by_status,
            visit_completion_rate=round(visit_completion_rate, 1),
            total_outcomes=len(outcomes),
            outcomes_by_category=outcomes_by_category,
            total_milestones=len(milestones),
            milestones_achieved=milestones_achieved,
            retention_rate=round(retention_rate, 1),
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: PatientRegistryService | None = None
_instance_lock = threading.Lock()


def get_patient_registry_service() -> PatientRegistryService:
    """Return the singleton PatientRegistryService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = PatientRegistryService()
    return _instance


def reset_patient_registry_service() -> PatientRegistryService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = PatientRegistryService()
    return _instance
