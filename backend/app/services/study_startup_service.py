"""Study Startup & Feasibility Assessment Service (CLINICAL-15).

Manages study startup operations including site feasibility assessments with
weighted scoring, country feasibility evaluation, startup timeline tracking
with critical path analysis, protocol feasibility assessment, site ranking,
country optimization, bottleneck analysis, and screen failure prediction.

Usage:
    from app.services.study_startup_service import (
        get_study_startup_service,
    )

    svc = get_study_startup_service()
    sites = svc.list_site_feasibilities()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.study_startup import (
    BottleneckAnalysis,
    CountryFeasibility,
    CountryFeasibilityCreate,
    CountryFeasibilityUpdate,
    CountryOptimization,
    CriticalPath,
    FeasibilityScore,
    FeasibilityStatus,
    ProtocolFeasibility,
    ProtocolFeasibilityCreate,
    ScreenFailurePrediction,
    SiteFeasibility,
    SiteFeasibilityCreate,
    SiteFeasibilityUpdate,
    SiteRanking,
    StartupBlocker,
    StartupMetrics,
    StartupPhase,
    StartupTimeline,
    StartupTimelineCreate,
    StartupTimelineUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

# Weighted scoring factors for site feasibility
WEIGHT_PATIENT_POOL = 0.30
WEIGHT_EXPERIENCE = 0.25
WEIGHT_INFRASTRUCTURE = 0.20
WEIGHT_STAFF = 0.15
WEIGHT_COMPETING_STUDIES = 0.10

# Feasibility score thresholds
SCORE_EXCELLENT = 85.0
SCORE_GOOD = 70.0
SCORE_ADEQUATE = 55.0
SCORE_MARGINAL = 40.0


class StudyStartupService:
    """In-memory Study Startup & Feasibility engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._site_feasibilities: dict[str, SiteFeasibility] = {}
        self._country_feasibilities: dict[str, CountryFeasibility] = {}
        self._startup_timelines: dict[str, StartupTimeline] = {}
        self._protocol_feasibilities: dict[str, ProtocolFeasibility] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic study startup data across clinical trials."""
        now = datetime.now(timezone.utc)

        # --- 15 Site Feasibility Assessments ---
        sites_data = [
            {
                "id": "SF-001",
                "site_id": "SITE-101",
                "site_name": "Memorial Hermann Hospital",
                "trial_id": EYLEA_TRIAL,
                "investigator_name": "Dr. Sarah Chen",
                "specialty": "Ophthalmology",
                "status": FeasibilityStatus.SELECTED,
                "patient_pool_estimate": 450,
                "competing_studies": 1,
                "staff_available": 8,
                "experience_score": 92.0,
                "infrastructure_score": 88.0,
                "geographic_region": "US-South",
                "assessment_date": now - timedelta(days=60),
                "assessor": "Dr. James Wilson",
            },
            {
                "id": "SF-002",
                "site_id": "SITE-102",
                "site_name": "Cleveland Clinic Foundation",
                "trial_id": EYLEA_TRIAL,
                "investigator_name": "Dr. Michael Torres",
                "specialty": "Ophthalmology",
                "status": FeasibilityStatus.SELECTED,
                "patient_pool_estimate": 380,
                "competing_studies": 2,
                "staff_available": 6,
                "experience_score": 88.0,
                "infrastructure_score": 95.0,
                "geographic_region": "US-Midwest",
                "assessment_date": now - timedelta(days=58),
                "assessor": "Dr. James Wilson",
            },
            {
                "id": "SF-003",
                "site_id": "SITE-103",
                "site_name": "Johns Hopkins Research Center",
                "trial_id": EYLEA_TRIAL,
                "investigator_name": "Dr. Emily Park",
                "specialty": "Ophthalmology",
                "status": FeasibilityStatus.SELECTED,
                "patient_pool_estimate": 520,
                "competing_studies": 3,
                "staff_available": 10,
                "experience_score": 95.0,
                "infrastructure_score": 92.0,
                "geographic_region": "US-East",
                "assessment_date": now - timedelta(days=55),
                "assessor": "Dr. James Wilson",
            },
            {
                "id": "SF-004",
                "site_id": "SITE-104",
                "site_name": "Mayo Clinic Jacksonville",
                "trial_id": EYLEA_TRIAL,
                "investigator_name": "Dr. Robert Kim",
                "specialty": "Ophthalmology",
                "status": FeasibilityStatus.SHORTLISTED,
                "patient_pool_estimate": 280,
                "competing_studies": 1,
                "staff_available": 5,
                "experience_score": 78.0,
                "infrastructure_score": 90.0,
                "geographic_region": "US-South",
                "assessment_date": now - timedelta(days=52),
                "assessor": "Dr. Lisa Nguyen",
            },
            {
                "id": "SF-005",
                "site_id": "SITE-105",
                "site_name": "Duke Clinical Research Institute",
                "trial_id": EYLEA_TRIAL,
                "investigator_name": "Dr. Amanda Foster",
                "specialty": "Ophthalmology",
                "status": FeasibilityStatus.BACKUP,
                "patient_pool_estimate": 200,
                "competing_studies": 4,
                "staff_available": 4,
                "experience_score": 72.0,
                "infrastructure_score": 80.0,
                "geographic_region": "US-East",
                "assessment_date": now - timedelta(days=50),
                "assessor": "Dr. Lisa Nguyen",
            },
            {
                "id": "SF-006",
                "site_id": "SITE-201",
                "site_name": "Kings College Hospital",
                "trial_id": DUPIXENT_TRIAL,
                "investigator_name": "Prof. David Hughes",
                "specialty": "Dermatology",
                "status": FeasibilityStatus.SELECTED,
                "patient_pool_estimate": 600,
                "competing_studies": 2,
                "staff_available": 12,
                "experience_score": 90.0,
                "infrastructure_score": 85.0,
                "geographic_region": "UK-London",
                "assessment_date": now - timedelta(days=45),
                "assessor": "Dr. Anna Schmidt",
            },
            {
                "id": "SF-007",
                "site_id": "SITE-202",
                "site_name": "Charite Universitaetsmedizin Berlin",
                "trial_id": DUPIXENT_TRIAL,
                "investigator_name": "Prof. Klaus Weber",
                "specialty": "Dermatology",
                "status": FeasibilityStatus.SELECTED,
                "patient_pool_estimate": 480,
                "competing_studies": 1,
                "staff_available": 9,
                "experience_score": 85.0,
                "infrastructure_score": 92.0,
                "geographic_region": "DE-Berlin",
                "assessment_date": now - timedelta(days=43),
                "assessor": "Dr. Anna Schmidt",
            },
            {
                "id": "SF-008",
                "site_id": "SITE-203",
                "site_name": "Tokyo University Hospital",
                "trial_id": DUPIXENT_TRIAL,
                "investigator_name": "Dr. Yuki Tanaka",
                "specialty": "Dermatology",
                "status": FeasibilityStatus.SHORTLISTED,
                "patient_pool_estimate": 350,
                "competing_studies": 3,
                "staff_available": 7,
                "experience_score": 80.0,
                "infrastructure_score": 88.0,
                "geographic_region": "JP-Tokyo",
                "assessment_date": now - timedelta(days=40),
                "assessor": "Dr. Anna Schmidt",
            },
            {
                "id": "SF-009",
                "site_id": "SITE-204",
                "site_name": "Royal Melbourne Hospital",
                "trial_id": DUPIXENT_TRIAL,
                "investigator_name": "Dr. Catherine Brooks",
                "specialty": "Dermatology",
                "status": FeasibilityStatus.SCREENING,
                "patient_pool_estimate": 250,
                "competing_studies": 0,
                "staff_available": 5,
                "experience_score": 68.0,
                "infrastructure_score": 75.0,
                "geographic_region": "AU-Victoria",
                "assessment_date": now - timedelta(days=38),
                "assessor": "Dr. Lisa Nguyen",
            },
            {
                "id": "SF-010",
                "site_id": "SITE-205",
                "site_name": "Toronto General Hospital",
                "trial_id": DUPIXENT_TRIAL,
                "investigator_name": "Dr. Mark Thompson",
                "specialty": "Dermatology",
                "status": FeasibilityStatus.DECLINED,
                "patient_pool_estimate": 180,
                "competing_studies": 5,
                "staff_available": 3,
                "experience_score": 60.0,
                "infrastructure_score": 70.0,
                "geographic_region": "CA-Ontario",
                "assessment_date": now - timedelta(days=35),
                "assessor": "Dr. Lisa Nguyen",
            },
            {
                "id": "SF-011",
                "site_id": "SITE-301",
                "site_name": "MD Anderson Cancer Center",
                "trial_id": LIBTAYO_TRIAL,
                "investigator_name": "Dr. Patricia Gonzalez",
                "specialty": "Oncology",
                "status": FeasibilityStatus.SELECTED,
                "patient_pool_estimate": 700,
                "competing_studies": 2,
                "staff_available": 15,
                "experience_score": 98.0,
                "infrastructure_score": 96.0,
                "geographic_region": "US-South",
                "assessment_date": now - timedelta(days=30),
                "assessor": "Dr. James Wilson",
            },
            {
                "id": "SF-012",
                "site_id": "SITE-302",
                "site_name": "Memorial Sloan Kettering",
                "trial_id": LIBTAYO_TRIAL,
                "investigator_name": "Dr. Jonathan Lee",
                "specialty": "Oncology",
                "status": FeasibilityStatus.SELECTED,
                "patient_pool_estimate": 650,
                "competing_studies": 3,
                "staff_available": 14,
                "experience_score": 96.0,
                "infrastructure_score": 94.0,
                "geographic_region": "US-East",
                "assessment_date": now - timedelta(days=28),
                "assessor": "Dr. James Wilson",
            },
            {
                "id": "SF-013",
                "site_id": "SITE-303",
                "site_name": "University College London Hospital",
                "trial_id": LIBTAYO_TRIAL,
                "investigator_name": "Prof. Simon Clarke",
                "specialty": "Oncology",
                "status": FeasibilityStatus.SHORTLISTED,
                "patient_pool_estimate": 400,
                "competing_studies": 2,
                "staff_available": 8,
                "experience_score": 82.0,
                "infrastructure_score": 86.0,
                "geographic_region": "UK-London",
                "assessment_date": now - timedelta(days=25),
                "assessor": "Dr. Anna Schmidt",
            },
            {
                "id": "SF-014",
                "site_id": "SITE-304",
                "site_name": "Heidelberg University Hospital",
                "trial_id": LIBTAYO_TRIAL,
                "investigator_name": "Prof. Martin Becker",
                "specialty": "Oncology",
                "status": FeasibilityStatus.SCREENING,
                "patient_pool_estimate": 320,
                "competing_studies": 1,
                "staff_available": 6,
                "experience_score": 75.0,
                "infrastructure_score": 82.0,
                "geographic_region": "DE-Baden",
                "assessment_date": now - timedelta(days=20),
                "assessor": "Dr. Anna Schmidt",
            },
            {
                "id": "SF-015",
                "site_id": "SITE-305",
                "site_name": "National Cancer Center Japan",
                "trial_id": LIBTAYO_TRIAL,
                "investigator_name": "Dr. Kenji Yamamoto",
                "specialty": "Oncology",
                "status": FeasibilityStatus.BACKUP,
                "patient_pool_estimate": 280,
                "competing_studies": 4,
                "staff_available": 5,
                "experience_score": 78.0,
                "infrastructure_score": 80.0,
                "geographic_region": "JP-Tokyo",
                "assessment_date": now - timedelta(days=18),
                "assessor": "Dr. Anna Schmidt",
            },
        ]

        for s in sites_data:
            # Calculate weighted composite score and enrollment potential
            sf = self._build_site_feasibility(**s)
            self._site_feasibilities[sf.id] = sf

        # --- 6 Country Feasibility Assessments ---
        countries_data = [
            {
                "id": "CF-001",
                "country_code": "US",
                "country_name": "United States",
                "trial_id": EYLEA_TRIAL,
                "regulatory_complexity": 3,
                "approval_timeline_months": 6.0,
                "import_requirements": "FDA IND required; no special import license for domestic trials",
                "data_privacy_requirements": "HIPAA compliance; 21 CFR Part 11 for electronic records",
                "local_representation_required": False,
                "estimated_sites": 8,
                "estimated_patients": 2400,
                "cost_index": 1.0,
            },
            {
                "id": "CF-002",
                "country_code": "GB",
                "country_name": "United Kingdom",
                "trial_id": DUPIXENT_TRIAL,
                "regulatory_complexity": 3,
                "approval_timeline_months": 5.0,
                "import_requirements": "MHRA CTA required; import license via DHSC",
                "data_privacy_requirements": "UK GDPR; ICO registration required",
                "local_representation_required": False,
                "estimated_sites": 5,
                "estimated_patients": 1500,
                "cost_index": 1.15,
            },
            {
                "id": "CF-003",
                "country_code": "DE",
                "country_name": "Germany",
                "trial_id": DUPIXENT_TRIAL,
                "regulatory_complexity": 4,
                "approval_timeline_months": 7.0,
                "import_requirements": "BfArM/PEI approval; EU import license; QP release required",
                "data_privacy_requirements": "EU GDPR with German BDSG supplement; DPO mandatory",
                "local_representation_required": True,
                "estimated_sites": 6,
                "estimated_patients": 1800,
                "cost_index": 1.1,
            },
            {
                "id": "CF-004",
                "country_code": "JP",
                "country_name": "Japan",
                "trial_id": LIBTAYO_TRIAL,
                "regulatory_complexity": 5,
                "approval_timeline_months": 10.0,
                "import_requirements": "PMDA notification; customs clearance via licensed importer",
                "data_privacy_requirements": "APPI compliance; cross-border data transfer restrictions",
                "local_representation_required": True,
                "estimated_sites": 4,
                "estimated_patients": 1200,
                "cost_index": 1.35,
            },
            {
                "id": "CF-005",
                "country_code": "AU",
                "country_name": "Australia",
                "trial_id": DUPIXENT_TRIAL,
                "regulatory_complexity": 2,
                "approval_timeline_months": 3.5,
                "import_requirements": "TGA CTN/CTX scheme; import permit via ODC",
                "data_privacy_requirements": "Privacy Act 1988; APPs compliance",
                "local_representation_required": False,
                "estimated_sites": 3,
                "estimated_patients": 800,
                "cost_index": 0.95,
            },
            {
                "id": "CF-006",
                "country_code": "CA",
                "country_name": "Canada",
                "trial_id": LIBTAYO_TRIAL,
                "regulatory_complexity": 3,
                "approval_timeline_months": 5.5,
                "import_requirements": "Health Canada CTA; no special import license",
                "data_privacy_requirements": "PIPEDA compliance; provincial privacy laws apply",
                "local_representation_required": False,
                "estimated_sites": 4,
                "estimated_patients": 1000,
                "cost_index": 0.9,
            },
        ]

        for c in countries_data:
            self._country_feasibilities[c["id"]] = CountryFeasibility(**c)

        # --- 20 Startup Timelines ---
        timelines_data = [
            # SITE-101: Fully active
            {"id": "ST-001", "trial_id": EYLEA_TRIAL, "site_id": "SITE-101", "phase": StartupPhase.FEASIBILITY, "planned_start": now - timedelta(days=120), "planned_end": now - timedelta(days=100), "actual_start": now - timedelta(days=120), "actual_end": now - timedelta(days=98), "blockers": [], "milestone_notes": "Feasibility completed on schedule"},
            {"id": "ST-002", "trial_id": EYLEA_TRIAL, "site_id": "SITE-101", "phase": StartupPhase.SITE_SELECTION, "planned_start": now - timedelta(days=100), "planned_end": now - timedelta(days=85), "actual_start": now - timedelta(days=98), "actual_end": now - timedelta(days=84), "blockers": [], "milestone_notes": "Site selected after evaluation"},
            {"id": "ST-003", "trial_id": EYLEA_TRIAL, "site_id": "SITE-101", "phase": StartupPhase.REGULATORY_PREP, "planned_start": now - timedelta(days=85), "planned_end": now - timedelta(days=60), "actual_start": now - timedelta(days=84), "actual_end": now - timedelta(days=58), "blockers": [], "milestone_notes": "Regulatory package prepared"},
            {"id": "ST-004", "trial_id": EYLEA_TRIAL, "site_id": "SITE-101", "phase": StartupPhase.IRB_SUBMISSION, "planned_start": now - timedelta(days=60), "planned_end": now - timedelta(days=35), "actual_start": now - timedelta(days=58), "actual_end": now - timedelta(days=32), "blockers": [], "milestone_notes": "IRB approved without queries"},
            {"id": "ST-005", "trial_id": EYLEA_TRIAL, "site_id": "SITE-101", "phase": StartupPhase.CONTRACT_NEGOTIATION, "planned_start": now - timedelta(days=35), "planned_end": now - timedelta(days=20), "actual_start": now - timedelta(days=32), "actual_end": now - timedelta(days=18), "blockers": [], "milestone_notes": "Contract executed"},
            {"id": "ST-006", "trial_id": EYLEA_TRIAL, "site_id": "SITE-101", "phase": StartupPhase.SITE_INITIATION_VISIT, "planned_start": now - timedelta(days=20), "planned_end": now - timedelta(days=10), "actual_start": now - timedelta(days=18), "actual_end": now - timedelta(days=9), "blockers": [], "milestone_notes": "SIV completed successfully"},
            {"id": "ST-007", "trial_id": EYLEA_TRIAL, "site_id": "SITE-101", "phase": StartupPhase.ACTIVE, "planned_start": now - timedelta(days=10), "planned_end": now + timedelta(days=365), "actual_start": now - timedelta(days=9), "actual_end": None, "blockers": [], "milestone_notes": "Site activated and enrolling"},
            # SITE-102: In contract negotiation with delay
            {"id": "ST-008", "trial_id": EYLEA_TRIAL, "site_id": "SITE-102", "phase": StartupPhase.FEASIBILITY, "planned_start": now - timedelta(days=100), "planned_end": now - timedelta(days=80), "actual_start": now - timedelta(days=100), "actual_end": now - timedelta(days=78), "blockers": [], "milestone_notes": "Feasibility complete"},
            {"id": "ST-009", "trial_id": EYLEA_TRIAL, "site_id": "SITE-102", "phase": StartupPhase.SITE_SELECTION, "planned_start": now - timedelta(days=80), "planned_end": now - timedelta(days=65), "actual_start": now - timedelta(days=78), "actual_end": now - timedelta(days=63), "blockers": [], "milestone_notes": "Site selected"},
            {"id": "ST-010", "trial_id": EYLEA_TRIAL, "site_id": "SITE-102", "phase": StartupPhase.REGULATORY_PREP, "planned_start": now - timedelta(days=65), "planned_end": now - timedelta(days=40), "actual_start": now - timedelta(days=63), "actual_end": now - timedelta(days=38), "blockers": [], "milestone_notes": None},
            {"id": "ST-011", "trial_id": EYLEA_TRIAL, "site_id": "SITE-102", "phase": StartupPhase.IRB_SUBMISSION, "planned_start": now - timedelta(days=40), "planned_end": now - timedelta(days=15), "actual_start": now - timedelta(days=38), "actual_end": now - timedelta(days=10), "blockers": [StartupBlocker.IRB_QUERY], "milestone_notes": "IRB raised queries; 5-day delay"},
            {"id": "ST-012", "trial_id": EYLEA_TRIAL, "site_id": "SITE-102", "phase": StartupPhase.CONTRACT_NEGOTIATION, "planned_start": now - timedelta(days=15), "planned_end": now - timedelta(days=5), "actual_start": now - timedelta(days=10), "actual_end": None, "blockers": [StartupBlocker.CONTRACT_DELAY], "milestone_notes": "Contract under legal review"},
            # SITE-201: In IRB submission with regulatory delay
            {"id": "ST-013", "trial_id": DUPIXENT_TRIAL, "site_id": "SITE-201", "phase": StartupPhase.FEASIBILITY, "planned_start": now - timedelta(days=90), "planned_end": now - timedelta(days=70), "actual_start": now - timedelta(days=90), "actual_end": now - timedelta(days=68), "blockers": [], "milestone_notes": "Feasibility completed"},
            {"id": "ST-014", "trial_id": DUPIXENT_TRIAL, "site_id": "SITE-201", "phase": StartupPhase.SITE_SELECTION, "planned_start": now - timedelta(days=70), "planned_end": now - timedelta(days=55), "actual_start": now - timedelta(days=68), "actual_end": now - timedelta(days=53), "blockers": [], "milestone_notes": "Site selected"},
            {"id": "ST-015", "trial_id": DUPIXENT_TRIAL, "site_id": "SITE-201", "phase": StartupPhase.REGULATORY_PREP, "planned_start": now - timedelta(days=55), "planned_end": now - timedelta(days=30), "actual_start": now - timedelta(days=53), "actual_end": now - timedelta(days=25), "blockers": [StartupBlocker.REGULATORY_DELAY], "milestone_notes": "Regulatory delay: additional docs requested"},
            {"id": "ST-016", "trial_id": DUPIXENT_TRIAL, "site_id": "SITE-201", "phase": StartupPhase.IRB_SUBMISSION, "planned_start": now - timedelta(days=30), "planned_end": now - timedelta(days=5), "actual_start": now - timedelta(days=25), "actual_end": None, "blockers": [StartupBlocker.IRB_QUERY], "milestone_notes": "Awaiting IRB response"},
            # SITE-301: In budget finalization with dispute
            {"id": "ST-017", "trial_id": LIBTAYO_TRIAL, "site_id": "SITE-301", "phase": StartupPhase.FEASIBILITY, "planned_start": now - timedelta(days=75), "planned_end": now - timedelta(days=55), "actual_start": now - timedelta(days=75), "actual_end": now - timedelta(days=54), "blockers": [], "milestone_notes": "Feasibility completed"},
            {"id": "ST-018", "trial_id": LIBTAYO_TRIAL, "site_id": "SITE-301", "phase": StartupPhase.SITE_SELECTION, "planned_start": now - timedelta(days=55), "planned_end": now - timedelta(days=40), "actual_start": now - timedelta(days=54), "actual_end": now - timedelta(days=38), "blockers": [], "milestone_notes": "Site selected"},
            {"id": "ST-019", "trial_id": LIBTAYO_TRIAL, "site_id": "SITE-301", "phase": StartupPhase.BUDGET_FINALIZATION, "planned_start": now - timedelta(days=40), "planned_end": now - timedelta(days=20), "actual_start": now - timedelta(days=38), "actual_end": None, "blockers": [StartupBlocker.BUDGET_DISPUTE, StartupBlocker.STAFF_SHORTAGE], "milestone_notes": "Budget dispute with site finance; also awaiting CRA hire"},
            # SITE-302: Early feasibility
            {"id": "ST-020", "trial_id": LIBTAYO_TRIAL, "site_id": "SITE-302", "phase": StartupPhase.FEASIBILITY, "planned_start": now - timedelta(days=30), "planned_end": now - timedelta(days=10), "actual_start": now - timedelta(days=30), "actual_end": None, "blockers": [StartupBlocker.EQUIPMENT_PENDING], "milestone_notes": "Feasibility in progress; awaiting lab equipment assessment"},
        ]

        for t in timelines_data:
            self._startup_timelines[t["id"]] = StartupTimeline(**t)

        # --- 3 Protocol Feasibility Assessments ---
        protocols_data = [
            {
                "id": "PF-001",
                "trial_id": EYLEA_TRIAL,
                "protocol_version": "v3.2",
                "inclusion_criteria_count": 8,
                "exclusion_criteria_count": 12,
                "visit_schedule_complexity": 45.0,
                "estimated_screen_failure_rate": 35.0,
                "estimated_enrollment_rate_per_site_month": 2.5,
                "recommended_modifications": [
                    "Consider relaxing exclusion criterion #4 (prior anti-VEGF treatment)",
                    "Simplify visit 6 assessments to reduce patient burden",
                ],
            },
            {
                "id": "PF-002",
                "trial_id": DUPIXENT_TRIAL,
                "protocol_version": "v2.1",
                "inclusion_criteria_count": 6,
                "exclusion_criteria_count": 9,
                "visit_schedule_complexity": 38.0,
                "estimated_screen_failure_rate": 28.0,
                "estimated_enrollment_rate_per_site_month": 3.0,
                "recommended_modifications": [
                    "Consider wider age range for inclusion",
                    "Reduce biomarker sample volume at screening visit",
                ],
            },
            {
                "id": "PF-003",
                "trial_id": LIBTAYO_TRIAL,
                "protocol_version": "v1.4",
                "inclusion_criteria_count": 10,
                "exclusion_criteria_count": 18,
                "visit_schedule_complexity": 72.0,
                "estimated_screen_failure_rate": 55.0,
                "estimated_enrollment_rate_per_site_month": 1.2,
                "recommended_modifications": [
                    "Consider broadening histology types in inclusion criteria",
                    "Reduce exclusion criteria count - currently 18, industry avg is 12",
                    "Simplify PK sampling schedule in treatment phase",
                    "Add remote/telemedicine visits where possible to reduce burden",
                ],
            },
        ]

        for p in protocols_data:
            self._protocol_feasibilities[p["id"]] = ProtocolFeasibility(**p)

    def _build_site_feasibility(self, **kwargs) -> SiteFeasibility:
        """Build a SiteFeasibility with computed scores."""
        patient_pool = kwargs["patient_pool_estimate"]
        competing = kwargs["competing_studies"]
        staff = kwargs["staff_available"]
        experience = kwargs["experience_score"]
        infrastructure = kwargs["infrastructure_score"]

        # Compute enrollment potential
        enrollment_potential = self._compute_enrollment_potential(
            patient_pool, competing, staff
        )

        # Compute composite score using weighted algorithm
        overall_score = self._compute_composite_score(
            patient_pool=patient_pool,
            competing_studies=competing,
            staff_available=staff,
            experience_score=experience,
            infrastructure_score=infrastructure,
        )

        kwargs["overall_score"] = round(overall_score, 1)
        kwargs["enrollment_potential"] = round(enrollment_potential, 1)
        return SiteFeasibility(**kwargs)

    @staticmethod
    def _compute_enrollment_potential(
        patient_pool: int, competing_studies: int, staff_available: int
    ) -> float:
        """Compute enrollment potential from patient pool, competition, and staff."""
        # Base from patient pool (normalize to 0-100 scale; 500 = 100%)
        pool_score = min(100.0, (patient_pool / 500.0) * 100.0)
        # Competition penalty: each competing study reduces by 8%
        competition_penalty = min(40.0, competing_studies * 8.0)
        # Staff bonus: each staff member adds 3%, capped at 30%
        staff_bonus = min(30.0, staff_available * 3.0)
        return max(0.0, min(100.0, pool_score - competition_penalty + staff_bonus))

    @staticmethod
    def _compute_composite_score(
        *,
        patient_pool: int,
        competing_studies: int,
        staff_available: int,
        experience_score: float,
        infrastructure_score: float,
    ) -> float:
        """Compute weighted composite feasibility score.

        Weights:
        - Patient pool: 30%
        - Experience: 25%
        - Infrastructure: 20%
        - Staff: 15%
        - Competing studies (inverse): 10%
        """
        # Normalize patient pool (500 patients = 100)
        pool_normalized = min(100.0, (patient_pool / 500.0) * 100.0)

        # Normalize staff (10 staff = 100)
        staff_normalized = min(100.0, (staff_available / 10.0) * 100.0)

        # Competing studies: inverse scoring (0 competing = 100, 5+ = 0)
        competing_normalized = max(0.0, 100.0 - competing_studies * 20.0)

        score = (
            pool_normalized * WEIGHT_PATIENT_POOL
            + experience_score * WEIGHT_EXPERIENCE
            + infrastructure_score * WEIGHT_INFRASTRUCTURE
            + staff_normalized * WEIGHT_STAFF
            + competing_normalized * WEIGHT_COMPETING_STUDIES
        )
        return min(100.0, max(0.0, score))

    @staticmethod
    def _score_to_grade(score: float) -> FeasibilityScore:
        """Classify a numeric score into a feasibility grade."""
        if score >= SCORE_EXCELLENT:
            return FeasibilityScore.EXCELLENT
        elif score >= SCORE_GOOD:
            return FeasibilityScore.GOOD
        elif score >= SCORE_ADEQUATE:
            return FeasibilityScore.ADEQUATE
        elif score >= SCORE_MARGINAL:
            return FeasibilityScore.MARGINAL
        else:
            return FeasibilityScore.POOR

    # ------------------------------------------------------------------
    # Site Feasibility
    # ------------------------------------------------------------------

    def list_site_feasibilities(
        self,
        *,
        trial_id: str | None = None,
        status: FeasibilityStatus | None = None,
        region: str | None = None,
    ) -> list[SiteFeasibility]:
        """List site feasibility assessments with optional filters."""
        with self._lock:
            result = list(self._site_feasibilities.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if status is not None:
            result = [s for s in result if s.status == status]
        if region is not None:
            result = [s for s in result if s.geographic_region == region]

        return sorted(result, key=lambda s: s.overall_score, reverse=True)

    def get_site_feasibility(self, assessment_id: str) -> SiteFeasibility | None:
        """Get a single site feasibility assessment by ID."""
        with self._lock:
            return self._site_feasibilities.get(assessment_id)

    def create_site_feasibility(self, payload: SiteFeasibilityCreate) -> SiteFeasibility:
        """Create a new site feasibility assessment."""
        now = datetime.now(timezone.utc)
        assessment_id = f"SF-{uuid4().hex[:8].upper()}"

        enrollment_potential = self._compute_enrollment_potential(
            payload.patient_pool_estimate, payload.competing_studies, payload.staff_available
        )
        overall_score = self._compute_composite_score(
            patient_pool=payload.patient_pool_estimate,
            competing_studies=payload.competing_studies,
            staff_available=payload.staff_available,
            experience_score=payload.experience_score,
            infrastructure_score=payload.infrastructure_score,
        )

        sf = SiteFeasibility(
            id=assessment_id,
            site_id=payload.site_id,
            site_name=payload.site_name,
            trial_id=payload.trial_id,
            investigator_name=payload.investigator_name,
            specialty=payload.specialty,
            status=FeasibilityStatus.SCREENING,
            overall_score=round(overall_score, 1),
            patient_pool_estimate=payload.patient_pool_estimate,
            competing_studies=payload.competing_studies,
            staff_available=payload.staff_available,
            experience_score=payload.experience_score,
            infrastructure_score=payload.infrastructure_score,
            enrollment_potential=round(enrollment_potential, 1),
            geographic_region=payload.geographic_region,
            assessment_date=now,
            assessor=payload.assessor,
        )
        with self._lock:
            self._site_feasibilities[assessment_id] = sf
        logger.info("Created site feasibility %s for site %s", assessment_id, payload.site_id)
        return sf

    def update_site_feasibility(
        self, assessment_id: str, payload: SiteFeasibilityUpdate
    ) -> SiteFeasibility | None:
        """Update a site feasibility assessment and recalculate scores."""
        with self._lock:
            existing = self._site_feasibilities.get(assessment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)

            # Recalculate composite score if any scoring inputs changed
            scoring_fields = {
                "patient_pool_estimate", "competing_studies",
                "staff_available", "experience_score", "infrastructure_score",
            }
            if scoring_fields & set(updates.keys()):
                data["overall_score"] = round(self._compute_composite_score(
                    patient_pool=data["patient_pool_estimate"],
                    competing_studies=data["competing_studies"],
                    staff_available=data["staff_available"],
                    experience_score=data["experience_score"],
                    infrastructure_score=data["infrastructure_score"],
                ), 1)
                data["enrollment_potential"] = round(self._compute_enrollment_potential(
                    data["patient_pool_estimate"],
                    data["competing_studies"],
                    data["staff_available"],
                ), 1)

            updated = SiteFeasibility(**data)
            self._site_feasibilities[assessment_id] = updated
        return updated

    def delete_site_feasibility(self, assessment_id: str) -> bool:
        """Delete a site feasibility assessment. Returns True if deleted."""
        with self._lock:
            if assessment_id in self._site_feasibilities:
                del self._site_feasibilities[assessment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Site Ranking
    # ------------------------------------------------------------------

    def get_site_rankings(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[SiteRanking]:
        """Rank sites by composite feasibility score."""
        with self._lock:
            assessments = list(self._site_feasibilities.values())

        if trial_id is not None:
            assessments = [a for a in assessments if a.trial_id == trial_id]

        # Sort by overall_score descending
        assessments.sort(key=lambda a: a.overall_score, reverse=True)

        rankings: list[SiteRanking] = []
        for rank, a in enumerate(assessments, start=1):
            # Compute score breakdown
            pool_normalized = min(100.0, (a.patient_pool_estimate / 500.0) * 100.0)
            staff_normalized = min(100.0, (a.staff_available / 10.0) * 100.0)
            competing_normalized = max(0.0, 100.0 - a.competing_studies * 20.0)

            rankings.append(SiteRanking(
                site_id=a.site_id,
                site_name=a.site_name,
                trial_id=a.trial_id,
                composite_score=a.overall_score,
                score_breakdown={
                    "patient_pool": round(pool_normalized * WEIGHT_PATIENT_POOL, 1),
                    "experience": round(a.experience_score * WEIGHT_EXPERIENCE, 1),
                    "infrastructure": round(a.infrastructure_score * WEIGHT_INFRASTRUCTURE, 1),
                    "staff": round(staff_normalized * WEIGHT_STAFF, 1),
                    "competing_studies": round(competing_normalized * WEIGHT_COMPETING_STUDIES, 1),
                },
                rank=rank,
                feasibility_grade=self._score_to_grade(a.overall_score),
            ))

        return rankings

    # ------------------------------------------------------------------
    # Country Feasibility
    # ------------------------------------------------------------------

    def list_country_feasibilities(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[CountryFeasibility]:
        """List country feasibility assessments with optional filter."""
        with self._lock:
            result = list(self._country_feasibilities.values())

        if trial_id is not None:
            result = [c for c in result if c.trial_id == trial_id]

        return sorted(result, key=lambda c: c.country_name)

    def get_country_feasibility(self, assessment_id: str) -> CountryFeasibility | None:
        """Get a single country feasibility assessment by ID."""
        with self._lock:
            return self._country_feasibilities.get(assessment_id)

    def create_country_feasibility(
        self, payload: CountryFeasibilityCreate
    ) -> CountryFeasibility:
        """Create a new country feasibility assessment."""
        assessment_id = f"CF-{uuid4().hex[:8].upper()}"
        cf = CountryFeasibility(
            id=assessment_id,
            **payload.model_dump(),
        )
        with self._lock:
            self._country_feasibilities[assessment_id] = cf
        logger.info("Created country feasibility %s for %s", assessment_id, payload.country_name)
        return cf

    def update_country_feasibility(
        self, assessment_id: str, payload: CountryFeasibilityUpdate
    ) -> CountryFeasibility | None:
        """Update a country feasibility assessment."""
        with self._lock:
            existing = self._country_feasibilities.get(assessment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CountryFeasibility(**data)
            self._country_feasibilities[assessment_id] = updated
        return updated

    def delete_country_feasibility(self, assessment_id: str) -> bool:
        """Delete a country feasibility assessment."""
        with self._lock:
            if assessment_id in self._country_feasibilities:
                del self._country_feasibilities[assessment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Country Optimization
    # ------------------------------------------------------------------

    def get_country_optimization(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[CountryOptimization]:
        """Optimize country selection based on cost, timeline, and patient pool.

        Scoring:
        - Cost score: lower cost_index = higher score
        - Timeline score: shorter approval timeline = higher score
        - Patient pool score: more patients = higher score
        """
        with self._lock:
            countries = list(self._country_feasibilities.values())

        if trial_id is not None:
            countries = [c for c in countries if c.trial_id == trial_id]

        if not countries:
            return []

        # Find ranges for normalization
        max_patients = max(c.estimated_patients for c in countries) or 1
        max_timeline = max(c.approval_timeline_months for c in countries) or 1
        max_cost = max(c.cost_index for c in countries) or 1

        optimizations: list[CountryOptimization] = []
        for c in countries:
            # Cost: lower = better (invert)
            cost_score = max(0.0, (1.0 - c.cost_index / max_cost) * 100.0) if max_cost > 0 else 50.0
            # Timeline: shorter = better (invert)
            timeline_score = max(0.0, (1.0 - c.approval_timeline_months / max_timeline) * 100.0) if max_timeline > 0 else 50.0
            # Patients: more = better
            patient_pool_score = min(100.0, (c.estimated_patients / max_patients) * 100.0) if max_patients > 0 else 50.0

            # Composite: equal weights
            optimization_score = (cost_score + timeline_score + patient_pool_score) / 3.0

            # Build recommendation
            pros: list[str] = []
            cons: list[str] = []
            if cost_score >= 60:
                pros.append("competitive cost")
            elif cost_score < 30:
                cons.append("high cost")
            if timeline_score >= 60:
                pros.append("fast regulatory approval")
            elif timeline_score < 30:
                cons.append("long approval timeline")
            if patient_pool_score >= 60:
                pros.append("large patient pool")
            elif patient_pool_score < 30:
                cons.append("limited patient pool")

            rec_parts = []
            if pros:
                rec_parts.append(f"Strengths: {', '.join(pros)}")
            if cons:
                rec_parts.append(f"Challenges: {', '.join(cons)}")
            recommendation = ". ".join(rec_parts) if rec_parts else "Average across all dimensions"

            optimizations.append(CountryOptimization(
                country_code=c.country_code,
                country_name=c.country_name,
                optimization_score=round(optimization_score, 1),
                cost_score=round(cost_score, 1),
                timeline_score=round(timeline_score, 1),
                patient_pool_score=round(patient_pool_score, 1),
                recommendation=recommendation,
            ))

        return sorted(optimizations, key=lambda o: o.optimization_score, reverse=True)

    # ------------------------------------------------------------------
    # Startup Timelines
    # ------------------------------------------------------------------

    def list_startup_timelines(
        self,
        *,
        trial_id: str | None = None,
        site_id: str | None = None,
        phase: StartupPhase | None = None,
    ) -> list[StartupTimeline]:
        """List startup timelines with optional filters."""
        with self._lock:
            result = list(self._startup_timelines.values())

        if trial_id is not None:
            result = [t for t in result if t.trial_id == trial_id]
        if site_id is not None:
            result = [t for t in result if t.site_id == site_id]
        if phase is not None:
            result = [t for t in result if t.phase == phase]

        return sorted(result, key=lambda t: t.planned_start)

    def get_startup_timeline(self, timeline_id: str) -> StartupTimeline | None:
        """Get a single startup timeline entry by ID."""
        with self._lock:
            return self._startup_timelines.get(timeline_id)

    def create_startup_timeline(self, payload: StartupTimelineCreate) -> StartupTimeline:
        """Create a new startup timeline entry."""
        timeline_id = f"ST-{uuid4().hex[:8].upper()}"
        st = StartupTimeline(
            id=timeline_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            phase=payload.phase,
            planned_start=payload.planned_start,
            planned_end=payload.planned_end,
            actual_start=None,
            actual_end=None,
            blockers=[],
            milestone_notes=None,
        )
        with self._lock:
            self._startup_timelines[timeline_id] = st
        logger.info("Created startup timeline %s for site %s phase %s", timeline_id, payload.site_id, payload.phase.value)
        return st

    def update_startup_timeline(
        self, timeline_id: str, payload: StartupTimelineUpdate
    ) -> StartupTimeline | None:
        """Update a startup timeline entry."""
        with self._lock:
            existing = self._startup_timelines.get(timeline_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = StartupTimeline(**data)
            self._startup_timelines[timeline_id] = updated
        return updated

    def delete_startup_timeline(self, timeline_id: str) -> bool:
        """Delete a startup timeline entry."""
        with self._lock:
            if timeline_id in self._startup_timelines:
                del self._startup_timelines[timeline_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Critical Path Analysis
    # ------------------------------------------------------------------

    def get_critical_path(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[CriticalPath]:
        """Compute critical path analysis for each site's startup.

        Identifies the longest-delayed phase and whether the site is on track.
        """
        now = datetime.now(timezone.utc)

        with self._lock:
            timelines = list(self._startup_timelines.values())
            sites = list(self._site_feasibilities.values())

        if trial_id is not None:
            timelines = [t for t in timelines if t.trial_id == trial_id]

        # Group timelines by site
        site_timelines: dict[str, list[StartupTimeline]] = {}
        for t in timelines:
            site_timelines.setdefault(t.site_id, []).append(t)

        # Build site name lookup
        site_names = {s.site_id: s.site_name for s in sites}

        results: list[CriticalPath] = []
        for site_id, tls in site_timelines.items():
            tls.sort(key=lambda t: t.planned_start)

            # Total planned days
            if tls:
                first_planned = min(t.planned_start for t in tls)
                last_planned = max(t.planned_end for t in tls)
                total_planned = (last_planned - first_planned).days
            else:
                total_planned = 0

            # Total actual days
            actual_starts = [t.actual_start for t in tls if t.actual_start is not None]
            actual_ends = [t.actual_end for t in tls if t.actual_end is not None]

            total_actual = None
            if actual_starts:
                first_actual = min(actual_starts)
                if actual_ends:
                    last_actual = max(actual_ends)
                    total_actual = (last_actual - first_actual).days
                else:
                    total_actual = (now - first_actual).days

            # Find critical phase (largest delay)
            critical_phase = None
            max_delay = 0
            total_delay = 0
            for t in tls:
                if t.actual_end is not None:
                    phase_delay = (t.actual_end - t.planned_end).days
                elif t.actual_start is not None and t.actual_end is None:
                    # Still in progress - check if overdue
                    phase_delay = max(0, (now - t.planned_end).days)
                else:
                    phase_delay = 0

                if phase_delay > max_delay:
                    max_delay = phase_delay
                    critical_phase = t.phase
                total_delay += max(0, phase_delay)

            on_track = total_delay <= 5  # 5-day tolerance

            results.append(CriticalPath(
                site_id=site_id,
                site_name=site_names.get(site_id, site_id),
                total_planned_days=total_planned,
                total_actual_days=total_actual,
                critical_phase=critical_phase,
                delay_days=total_delay,
                on_track=on_track,
            ))

        return sorted(results, key=lambda r: r.delay_days, reverse=True)

    # ------------------------------------------------------------------
    # Bottleneck Analysis
    # ------------------------------------------------------------------

    def get_bottleneck_analysis(self) -> list[BottleneckAnalysis]:
        """Analyze which startup phase causes the most delays.

        Computes average delay and common blockers per phase.
        """
        now = datetime.now(timezone.utc)

        with self._lock:
            timelines = list(self._startup_timelines.values())

        # Group by phase
        phase_delays: dict[StartupPhase, list[float]] = {}
        phase_blockers: dict[StartupPhase, list[str]] = {}
        phase_sites: dict[StartupPhase, set[str]] = {}

        for t in timelines:
            if t.actual_end is not None:
                delay = max(0.0, (t.actual_end - t.planned_end).days)
            elif t.actual_start is not None and t.actual_end is None:
                delay = max(0.0, (now - t.planned_end).days)
            else:
                continue  # Not started yet

            phase_delays.setdefault(t.phase, []).append(delay)
            phase_sites.setdefault(t.phase, set()).add(t.site_id)
            for b in t.blockers:
                phase_blockers.setdefault(t.phase, []).append(b.value)

        results: list[BottleneckAnalysis] = []
        for phase in StartupPhase:
            delays = phase_delays.get(phase, [])
            if not delays:
                continue

            avg_delay = sum(delays) / len(delays)
            blockers = phase_blockers.get(phase, [])
            # Count blocker frequency
            blocker_counts: dict[str, int] = {}
            for b in blockers:
                blocker_counts[b] = blocker_counts.get(b, 0) + 1
            common_blockers = sorted(
                blocker_counts.keys(), key=lambda b: blocker_counts[b], reverse=True
            )[:3]

            results.append(BottleneckAnalysis(
                phase=phase,
                avg_delay_days=round(avg_delay, 1),
                sites_affected=len(phase_sites.get(phase, set())),
                common_blockers=common_blockers,
            ))

        return sorted(results, key=lambda b: b.avg_delay_days, reverse=True)

    # ------------------------------------------------------------------
    # Protocol Feasibility
    # ------------------------------------------------------------------

    def list_protocol_feasibilities(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[ProtocolFeasibility]:
        """List protocol feasibility assessments."""
        with self._lock:
            result = list(self._protocol_feasibilities.values())

        if trial_id is not None:
            result = [p for p in result if p.trial_id == trial_id]

        return sorted(result, key=lambda p: p.id)

    def get_protocol_feasibility(self, assessment_id: str) -> ProtocolFeasibility | None:
        """Get a single protocol feasibility assessment."""
        with self._lock:
            return self._protocol_feasibilities.get(assessment_id)

    def create_protocol_feasibility(
        self, payload: ProtocolFeasibilityCreate
    ) -> ProtocolFeasibility:
        """Create a new protocol feasibility assessment."""
        assessment_id = f"PF-{uuid4().hex[:8].upper()}"
        pf = ProtocolFeasibility(
            id=assessment_id,
            **payload.model_dump(),
        )
        with self._lock:
            self._protocol_feasibilities[assessment_id] = pf
        logger.info("Created protocol feasibility %s for trial %s", assessment_id, payload.trial_id)
        return pf

    # ------------------------------------------------------------------
    # Screen Failure Prediction
    # ------------------------------------------------------------------

    def predict_screen_failure_rate(self, trial_id: str) -> ScreenFailurePrediction | None:
        """Predict screen failure rate based on protocol criteria complexity.

        Formula:
        - Base rate: 20%
        - Each inclusion criterion adds 0.5%
        - Each exclusion criterion adds 1.5%
        - Visit complexity adds 0.2% per point
        - Capped at 90%
        """
        with self._lock:
            protocols = [
                p for p in self._protocol_feasibilities.values()
                if p.trial_id == trial_id
            ]

        if not protocols:
            return None

        # Use latest protocol version
        protocol = sorted(protocols, key=lambda p: p.protocol_version, reverse=True)[0]

        base_rate = 20.0
        criteria_factor = (
            protocol.inclusion_criteria_count * 0.5
            + protocol.exclusion_criteria_count * 1.5
        )
        visit_factor = protocol.visit_schedule_complexity * 0.2

        predicted = min(90.0, base_rate + criteria_factor + visit_factor)

        # Confidence based on how close predicted is to protocol's own estimate
        diff = abs(predicted - protocol.estimated_screen_failure_rate)
        if diff < 5:
            confidence = "high"
        elif diff < 15:
            confidence = "medium"
        else:
            confidence = "low"

        return ScreenFailurePrediction(
            trial_id=trial_id,
            protocol_version=protocol.protocol_version,
            predicted_rate=round(predicted, 1),
            criteria_complexity_factor=round(criteria_factor, 1),
            visit_complexity_factor=round(visit_factor, 1),
            confidence=confidence,
        )

    # ------------------------------------------------------------------
    # Metrics & Dashboard
    # ------------------------------------------------------------------

    def get_metrics(self) -> StartupMetrics:
        """Compute aggregated study startup operational metrics."""
        with self._lock:
            sites = list(self._site_feasibilities.values())
            countries = list(self._country_feasibilities.values())
            timelines = list(self._startup_timelines.values())
            protocols = list(self._protocol_feasibilities.values())

        # Sites by status
        sites_selected = sum(1 for s in sites if s.status == FeasibilityStatus.SELECTED)

        # Average feasibility score
        avg_score = 0.0
        if sites:
            avg_score = round(sum(s.overall_score for s in sites) / len(sites), 1)

        # Average startup time (for fully activated sites)
        startup_times: list[float] = []
        # Group timelines by site and compute total startup time for active sites
        site_tls: dict[str, list[StartupTimeline]] = {}
        for t in timelines:
            site_tls.setdefault(t.site_id, []).append(t)

        for site_id, tls in site_tls.items():
            # Check if site has active phase
            active_phases = [t for t in tls if t.phase == StartupPhase.ACTIVE and t.actual_start]
            if active_phases:
                first_start = min(
                    t.actual_start for t in tls if t.actual_start is not None
                )
                active_start = active_phases[0].actual_start
                if active_start:
                    days = (active_start - first_start).days
                    startup_times.append(days)

        avg_startup = round(sum(startup_times) / max(1, len(startup_times)), 1) if startup_times else 0.0

        # Sites by phase (current phase = last phase with actual_start but no actual_end, or last completed)
        sites_by_phase: dict[str, int] = {}
        for site_id, tls in site_tls.items():
            tls.sort(key=lambda t: t.planned_start)
            current_phase = tls[-1].phase if tls else StartupPhase.FEASIBILITY
            # Find the last in-progress or latest completed phase
            for t in reversed(tls):
                if t.actual_start is not None and t.actual_end is None:
                    current_phase = t.phase
                    break
                elif t.actual_end is not None:
                    current_phase = t.phase
                    break
            key = current_phase.value
            sites_by_phase[key] = sites_by_phase.get(key, 0) + 1

        # Bottleneck analysis
        bottlenecks = self.get_bottleneck_analysis()

        return StartupMetrics(
            total_sites_assessed=len(sites),
            sites_selected=sites_selected,
            avg_startup_time_days=avg_startup,
            sites_by_phase=sites_by_phase,
            countries_assessed=len(countries),
            protocol_amendments=len(protocols),
            avg_feasibility_score=avg_score,
            bottleneck_analysis=bottlenecks,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: StudyStartupService | None = None
_instance_lock = threading.Lock()


def get_study_startup_service() -> StudyStartupService:
    """Return the singleton StudyStartupService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = StudyStartupService()
    return _instance


def reset_study_startup_service() -> StudyStartupService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = StudyStartupService()
    return _instance
