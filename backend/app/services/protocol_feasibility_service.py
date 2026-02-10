"""Protocol Feasibility Assessment Service.

Manages feasibility studies for clinical trial protocols including site evaluation,
competitive landscape analysis, enrollment projections, feasibility scoring,
questionnaire management, and operational metrics.

Usage:
    from app.services.protocol_feasibility_service import (
        get_protocol_feasibility_service,
    )

    svc = get_protocol_feasibility_service()
    studies = svc.list_studies()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import math
import threading
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.protocol_feasibility import (
    CompetitiveLandscape,
    CompetitiveLandscapeCreate,
    CompetitiveLandscapeUpdate,
    CompetitiveThreatLevel,
    EnrollmentProjection,
    EnrollmentProjectionCreate,
    EnrollmentRisk,
    FeasibilityMetrics,
    FeasibilityQuestion,
    FeasibilityQuestionCreate,
    FeasibilityStatus,
    FeasibilityStudy,
    FeasibilityStudyCreate,
    FeasibilityStudyUpdate,
    FeasibilitySummary,
    QuestionnaireResponseCreate,
    SiteAssessment,
    SiteAssessmentCreate,
    SiteAssessmentUpdate,
    SiteQuestionnaireResponse,
    SiteRating,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

# Site rating score thresholds (average of sub-scores)
RATING_EXCELLENT = 85.0
RATING_GOOD = 70.0
RATING_ACCEPTABLE = 55.0
RATING_MARGINAL = 40.0


class ProtocolFeasibilityService:
    """In-memory protocol feasibility assessment engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._studies: dict[str, FeasibilityStudy] = {}
        self._site_assessments: dict[str, SiteAssessment] = {}
        self._competitive_entries: dict[str, CompetitiveLandscape] = {}
        self._enrollment_projections: dict[str, EnrollmentProjection] = {}
        self._questions: dict[str, FeasibilityQuestion] = {}
        self._questionnaire_responses: dict[str, SiteQuestionnaireResponse] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic feasibility data."""
        now = datetime.now(timezone.utc)

        # --- 3 Feasibility Studies ---
        studies_data = [
            {
                "id": "FS-001",
                "trial_id": EYLEA_TRIAL,
                "protocol_id": "PROT-EYLEA-301",
                "protocol_version": "3.0",
                "therapeutic_area": "Ophthalmology",
                "indication": "Wet Age-Related Macular Degeneration",
                "phase": "Phase III",
                "status": FeasibilityStatus.IN_PROGRESS,
                "initiated_date": now - timedelta(days=90),
                "completed_date": None,
                "lead_analyst": "Dr. Sarah Chen",
                "target_enrollment": 480,
                "enrollment_duration_months": 18,
                "target_countries": ["United States", "Germany", "Japan", "United Kingdom", "Canada"],
                "target_sites_count": 60,
                "overall_feasibility_score": 72.5,
            },
            {
                "id": "FS-002",
                "trial_id": DUPIXENT_TRIAL,
                "protocol_id": "PROT-DUP-201",
                "protocol_version": "2.1",
                "therapeutic_area": "Immunology",
                "indication": "Atopic Dermatitis",
                "phase": "Phase II",
                "status": FeasibilityStatus.COMPLETED,
                "initiated_date": now - timedelta(days=180),
                "completed_date": now - timedelta(days=30),
                "lead_analyst": "Dr. James Rodriguez",
                "target_enrollment": 300,
                "enrollment_duration_months": 12,
                "target_countries": ["United States", "France", "Australia"],
                "target_sites_count": 40,
                "overall_feasibility_score": 81.3,
            },
            {
                "id": "FS-003",
                "trial_id": LIBTAYO_TRIAL,
                "protocol_id": "PROT-LIB-102",
                "protocol_version": "1.0",
                "therapeutic_area": "Oncology",
                "indication": "Non-Small Cell Lung Cancer",
                "phase": "Phase I/II",
                "status": FeasibilityStatus.DRAFT,
                "initiated_date": now - timedelta(days=14),
                "completed_date": None,
                "lead_analyst": "Dr. Michelle Park",
                "target_enrollment": 150,
                "enrollment_duration_months": 24,
                "target_countries": ["United States", "South Korea", "Spain"],
                "target_sites_count": 25,
                "overall_feasibility_score": None,
            },
        ]

        for s in studies_data:
            self._studies[s["id"]] = FeasibilityStudy(**s)

        # --- 10 Site Assessments ---
        sites_data = [
            {
                "id": "SA-001",
                "study_id": "FS-001",
                "site_id": "SITE-101",
                "site_name": "Memorial Hermann Eye Institute",
                "country": "United States",
                "investigator_name": "Dr. Robert Kim",
                "investigator_experience_years": 18,
                "competing_studies_count": 1,
                "patient_pool_estimate": 350,
                "annual_enrollment_estimate": 24,
                "site_rating": SiteRating.EXCELLENT,
                "infrastructure_score": 92.0,
                "regulatory_readiness": 95.0,
                "staff_availability": 88.0,
                "lab_capabilities": 90.0,
                "pharmacy_capabilities": 85.0,
                "notes": "Excellent ophthalmology research center with dedicated retina clinic.",
                "assessed_date": now - timedelta(days=75),
                "assessed_by": "Dr. Sarah Chen",
            },
            {
                "id": "SA-002",
                "study_id": "FS-001",
                "site_id": "SITE-102",
                "site_name": "Cleveland Clinic Cole Eye Institute",
                "country": "United States",
                "investigator_name": "Dr. Alan Foster",
                "investigator_experience_years": 22,
                "competing_studies_count": 2,
                "patient_pool_estimate": 280,
                "annual_enrollment_estimate": 18,
                "site_rating": SiteRating.GOOD,
                "infrastructure_score": 88.0,
                "regulatory_readiness": 90.0,
                "staff_availability": 75.0,
                "lab_capabilities": 85.0,
                "pharmacy_capabilities": 80.0,
                "notes": "Strong capabilities but moderate staff constraints.",
                "assessed_date": now - timedelta(days=70),
                "assessed_by": "Dr. Sarah Chen",
            },
            {
                "id": "SA-003",
                "study_id": "FS-001",
                "site_id": "SITE-201",
                "site_name": "Charite Universitatsmedizin Berlin",
                "country": "Germany",
                "investigator_name": "Prof. Hans Mueller",
                "investigator_experience_years": 25,
                "competing_studies_count": 3,
                "patient_pool_estimate": 200,
                "annual_enrollment_estimate": 12,
                "site_rating": SiteRating.GOOD,
                "infrastructure_score": 85.0,
                "regulatory_readiness": 82.0,
                "staff_availability": 78.0,
                "lab_capabilities": 88.0,
                "pharmacy_capabilities": 75.0,
                "notes": "Top EU center but regulatory timeline may be longer.",
                "assessed_date": now - timedelta(days=65),
                "assessed_by": "Dr. Sarah Chen",
            },
            {
                "id": "SA-004",
                "study_id": "FS-001",
                "site_id": "SITE-301",
                "site_name": "Tokyo University Hospital",
                "country": "Japan",
                "investigator_name": "Dr. Yuki Tanaka",
                "investigator_experience_years": 15,
                "competing_studies_count": 4,
                "patient_pool_estimate": 180,
                "annual_enrollment_estimate": 10,
                "site_rating": SiteRating.ACCEPTABLE,
                "infrastructure_score": 80.0,
                "regulatory_readiness": 65.0,
                "staff_availability": 70.0,
                "lab_capabilities": 82.0,
                "pharmacy_capabilities": 72.0,
                "notes": "PMDA regulatory requirements add complexity. High competing studies.",
                "assessed_date": now - timedelta(days=60),
                "assessed_by": "Dr. Sarah Chen",
            },
            {
                "id": "SA-005",
                "study_id": "FS-001",
                "site_id": "SITE-401",
                "site_name": "Moorfields Eye Hospital",
                "country": "United Kingdom",
                "investigator_name": "Dr. Eleanor Walsh",
                "investigator_experience_years": 12,
                "competing_studies_count": 2,
                "patient_pool_estimate": 220,
                "annual_enrollment_estimate": 14,
                "site_rating": SiteRating.GOOD,
                "infrastructure_score": 86.0,
                "regulatory_readiness": 88.0,
                "staff_availability": 80.0,
                "lab_capabilities": 84.0,
                "pharmacy_capabilities": 78.0,
                "notes": "World-renowned eye hospital with strong research track record.",
                "assessed_date": now - timedelta(days=55),
                "assessed_by": "Dr. Sarah Chen",
            },
            {
                "id": "SA-006",
                "study_id": "FS-002",
                "site_id": "SITE-103",
                "site_name": "Johns Hopkins Dermatology Clinic",
                "country": "United States",
                "investigator_name": "Dr. Patricia Williams",
                "investigator_experience_years": 20,
                "competing_studies_count": 1,
                "patient_pool_estimate": 500,
                "annual_enrollment_estimate": 30,
                "site_rating": SiteRating.EXCELLENT,
                "infrastructure_score": 95.0,
                "regulatory_readiness": 92.0,
                "staff_availability": 90.0,
                "lab_capabilities": 88.0,
                "pharmacy_capabilities": 85.0,
                "notes": "Premier dermatology research site with large patient base.",
                "assessed_date": now - timedelta(days=160),
                "assessed_by": "Dr. James Rodriguez",
            },
            {
                "id": "SA-007",
                "study_id": "FS-002",
                "site_id": "SITE-104",
                "site_name": "Mayo Clinic Dermatology",
                "country": "United States",
                "investigator_name": "Dr. David Chen",
                "investigator_experience_years": 16,
                "competing_studies_count": 0,
                "patient_pool_estimate": 420,
                "annual_enrollment_estimate": 28,
                "site_rating": SiteRating.EXCELLENT,
                "infrastructure_score": 93.0,
                "regulatory_readiness": 94.0,
                "staff_availability": 85.0,
                "lab_capabilities": 92.0,
                "pharmacy_capabilities": 90.0,
                "notes": "No competing studies. Excellent infrastructure.",
                "assessed_date": now - timedelta(days=155),
                "assessed_by": "Dr. James Rodriguez",
            },
            {
                "id": "SA-008",
                "study_id": "FS-002",
                "site_id": "SITE-501",
                "site_name": "Hopital Saint-Louis Paris",
                "country": "France",
                "investigator_name": "Dr. Marie Dubois",
                "investigator_experience_years": 14,
                "competing_studies_count": 3,
                "patient_pool_estimate": 300,
                "annual_enrollment_estimate": 16,
                "site_rating": SiteRating.ACCEPTABLE,
                "infrastructure_score": 78.0,
                "regulatory_readiness": 72.0,
                "staff_availability": 65.0,
                "lab_capabilities": 80.0,
                "pharmacy_capabilities": 70.0,
                "notes": "Good patient pool but staff turnover is a concern.",
                "assessed_date": now - timedelta(days=150),
                "assessed_by": "Dr. James Rodriguez",
            },
            {
                "id": "SA-009",
                "study_id": "FS-001",
                "site_id": "SITE-601",
                "site_name": "Riverside Community Clinic",
                "country": "United States",
                "investigator_name": "Dr. Thomas Green",
                "investigator_experience_years": 5,
                "competing_studies_count": 0,
                "patient_pool_estimate": 60,
                "annual_enrollment_estimate": 4,
                "site_rating": SiteRating.MARGINAL,
                "infrastructure_score": 50.0,
                "regulatory_readiness": 45.0,
                "staff_availability": 40.0,
                "lab_capabilities": 35.0,
                "pharmacy_capabilities": 30.0,
                "notes": "Limited research experience. May need significant support.",
                "assessed_date": now - timedelta(days=50),
                "assessed_by": "Dr. Sarah Chen",
            },
            {
                "id": "SA-010",
                "study_id": "FS-001",
                "site_id": "SITE-602",
                "site_name": "Rural Health Center",
                "country": "United States",
                "investigator_name": "Dr. Nancy Smith",
                "investigator_experience_years": 2,
                "competing_studies_count": 0,
                "patient_pool_estimate": 30,
                "annual_enrollment_estimate": 2,
                "site_rating": SiteRating.NOT_SUITABLE,
                "infrastructure_score": 25.0,
                "regulatory_readiness": 20.0,
                "staff_availability": 30.0,
                "lab_capabilities": 15.0,
                "pharmacy_capabilities": 20.0,
                "notes": "Insufficient infrastructure for Phase III ophthalmic trial.",
                "assessed_date": now - timedelta(days=48),
                "assessed_by": "Dr. Sarah Chen",
            },
        ]

        for sa in sites_data:
            self._site_assessments[sa["id"]] = SiteAssessment(**sa)

        # --- 5 Competitive Landscape Entries ---
        comp_data = [
            {
                "id": "CL-001",
                "study_id": "FS-001",
                "competitor_trial_id": "NCT04912345",
                "sponsor_name": "Roche/Genentech",
                "phase": "Phase III",
                "indication": "Wet AMD",
                "estimated_enrollment": 600,
                "enrollment_start_date": date(2025, 6, 1),
                "competing_sites_overlap": 12,
                "threat_level": CompetitiveThreatLevel.HIGH,
                "notes": "Faricimab direct competitor with similar endpoints.",
            },
            {
                "id": "CL-002",
                "study_id": "FS-001",
                "competitor_trial_id": "NCT05123456",
                "sponsor_name": "Novartis",
                "phase": "Phase III",
                "indication": "Wet AMD",
                "estimated_enrollment": 450,
                "enrollment_start_date": date(2025, 9, 1),
                "competing_sites_overlap": 8,
                "threat_level": CompetitiveThreatLevel.MODERATE,
                "notes": "Brolucizumab extension study. Moderate overlap.",
            },
            {
                "id": "CL-003",
                "study_id": "FS-001",
                "competitor_trial_id": "NCT05234567",
                "sponsor_name": "Kodiak Sciences",
                "phase": "Phase II/III",
                "indication": "Wet AMD",
                "estimated_enrollment": 300,
                "enrollment_start_date": date(2026, 1, 15),
                "competing_sites_overlap": 5,
                "threat_level": CompetitiveThreatLevel.LOW,
                "notes": "Early phase, less overlap. Monitoring required.",
            },
            {
                "id": "CL-004",
                "study_id": "FS-002",
                "competitor_trial_id": "NCT05345678",
                "sponsor_name": "AbbVie",
                "phase": "Phase III",
                "indication": "Atopic Dermatitis",
                "estimated_enrollment": 800,
                "enrollment_start_date": date(2025, 3, 1),
                "competing_sites_overlap": 15,
                "threat_level": CompetitiveThreatLevel.CRITICAL,
                "notes": "Upadacitinib head-to-head. Heavy site overlap.",
            },
            {
                "id": "CL-005",
                "study_id": "FS-002",
                "competitor_trial_id": "NCT05456789",
                "sponsor_name": "Pfizer",
                "phase": "Phase II",
                "indication": "Atopic Dermatitis",
                "estimated_enrollment": 200,
                "enrollment_start_date": date(2025, 11, 1),
                "competing_sites_overlap": 6,
                "threat_level": CompetitiveThreatLevel.MODERATE,
                "notes": "JAK inhibitor competitor. Moderate threat.",
            },
        ]

        for cl in comp_data:
            self._competitive_entries[cl["id"]] = CompetitiveLandscape(**cl)

        # --- 6 Enrollment Projections ---
        proj_data = [
            {
                "id": "EP-001",
                "study_id": "FS-001",
                "scenario_name": "Base Case",
                "sites_count": 60,
                "patients_per_site_per_month": 0.5,
                "screen_failure_rate": 0.25,
                "dropout_rate": 0.10,
                "enrollment_start_date": date(2026, 6, 1),
                "projected_enrollment_months": 18,
                "projected_total_enrolled": 486,
                "confidence_level": 70.0,
                "risk_level": EnrollmentRisk.MEDIUM,
                "assumptions": "60 sites active by month 3. Average enrollment rate from similar trials.",
            },
            {
                "id": "EP-002",
                "study_id": "FS-001",
                "scenario_name": "Optimistic",
                "sites_count": 65,
                "patients_per_site_per_month": 0.6,
                "screen_failure_rate": 0.20,
                "dropout_rate": 0.08,
                "enrollment_start_date": date(2026, 5, 1),
                "projected_enrollment_months": 14,
                "projected_total_enrolled": 530,
                "confidence_level": 45.0,
                "risk_level": EnrollmentRisk.LOW,
                "assumptions": "Fast site activation. Lower screen failure based on revised criteria.",
            },
            {
                "id": "EP-003",
                "study_id": "FS-001",
                "scenario_name": "Conservative",
                "sites_count": 50,
                "patients_per_site_per_month": 0.35,
                "screen_failure_rate": 0.35,
                "dropout_rate": 0.15,
                "enrollment_start_date": date(2026, 8, 1),
                "projected_enrollment_months": 24,
                "projected_total_enrolled": 355,
                "confidence_level": 85.0,
                "risk_level": EnrollmentRisk.HIGH,
                "assumptions": "Delayed activation. Higher screen failure. Competition impact.",
            },
            {
                "id": "EP-004",
                "study_id": "FS-001",
                "scenario_name": "Worst Case",
                "sites_count": 40,
                "patients_per_site_per_month": 0.25,
                "screen_failure_rate": 0.40,
                "dropout_rate": 0.20,
                "enrollment_start_date": date(2026, 10, 1),
                "projected_enrollment_months": 30,
                "projected_total_enrolled": 240,
                "confidence_level": 90.0,
                "risk_level": EnrollmentRisk.VERY_HIGH,
                "assumptions": "Significant delays. High competition. Restrictive criteria.",
            },
            {
                "id": "EP-005",
                "study_id": "FS-002",
                "scenario_name": "Base Case",
                "sites_count": 40,
                "patients_per_site_per_month": 0.7,
                "screen_failure_rate": 0.20,
                "dropout_rate": 0.10,
                "enrollment_start_date": date(2025, 6, 1),
                "projected_enrollment_months": 12,
                "projected_total_enrolled": 310,
                "confidence_level": 75.0,
                "risk_level": EnrollmentRisk.LOW,
                "assumptions": "AD prevalence supports faster enrollment.",
            },
            {
                "id": "EP-006",
                "study_id": "FS-002",
                "scenario_name": "Conservative",
                "sites_count": 35,
                "patients_per_site_per_month": 0.5,
                "screen_failure_rate": 0.30,
                "dropout_rate": 0.15,
                "enrollment_start_date": date(2025, 8, 1),
                "projected_enrollment_months": 16,
                "projected_total_enrolled": 245,
                "confidence_level": 85.0,
                "risk_level": EnrollmentRisk.MEDIUM,
                "assumptions": "AbbVie competition reduces available patients.",
            },
        ]

        for ep in proj_data:
            self._enrollment_projections[ep["id"]] = EnrollmentProjection(**ep)

        # --- 6 Questionnaire Questions (for FS-001) ---
        questions_data = [
            {
                "id": "FQ-001",
                "study_id": "FS-001",
                "category": "regulatory",
                "question_text": "Does the site have an active IRB/EC approval for ophthalmic studies?",
                "response_type": "yes_no",
                "required": True,
                "display_order": 1,
            },
            {
                "id": "FQ-002",
                "study_id": "FS-001",
                "category": "logistics",
                "question_text": "How many retina-qualified ophthalmologists are available on-site?",
                "response_type": "number",
                "required": True,
                "display_order": 2,
            },
            {
                "id": "FQ-003",
                "study_id": "FS-001",
                "category": "experience",
                "question_text": "How many intravitreal injection trials has the site completed in the past 5 years?",
                "response_type": "number",
                "required": True,
                "display_order": 3,
            },
            {
                "id": "FQ-004",
                "study_id": "FS-001",
                "category": "infrastructure",
                "question_text": "Does the site have access to OCT and fluorescein angiography equipment?",
                "response_type": "yes_no",
                "required": True,
                "display_order": 4,
            },
            {
                "id": "FQ-005",
                "study_id": "FS-001",
                "category": "competition",
                "question_text": "List any competing wet AMD trials currently enrolling at your site.",
                "response_type": "text",
                "required": False,
                "display_order": 5,
            },
            {
                "id": "FQ-006",
                "study_id": "FS-001",
                "category": "capacity",
                "question_text": "What is your estimated monthly capacity for screening and enrolling wet AMD patients?",
                "response_type": "number",
                "required": True,
                "display_order": 6,
            },
        ]

        for q in questions_data:
            self._questions[q["id"]] = FeasibilityQuestion(**q)

        # --- 4 Questionnaire Responses ---
        responses_data = [
            {
                "id": "QR-001",
                "study_id": "FS-001",
                "site_id": "SITE-101",
                "question_id": "FQ-001",
                "response_value": "Yes",
                "responded_date": now - timedelta(days=70),
                "responded_by": "Dr. Robert Kim",
            },
            {
                "id": "QR-002",
                "study_id": "FS-001",
                "site_id": "SITE-101",
                "question_id": "FQ-002",
                "response_value": "4",
                "responded_date": now - timedelta(days=70),
                "responded_by": "Dr. Robert Kim",
            },
            {
                "id": "QR-003",
                "study_id": "FS-001",
                "site_id": "SITE-101",
                "question_id": "FQ-003",
                "response_value": "8",
                "responded_date": now - timedelta(days=70),
                "responded_by": "Dr. Robert Kim",
            },
            {
                "id": "QR-004",
                "study_id": "FS-001",
                "site_id": "SITE-102",
                "question_id": "FQ-001",
                "response_value": "Yes",
                "responded_date": now - timedelta(days=65),
                "responded_by": "Dr. Alan Foster",
            },
        ]

        for qr in responses_data:
            self._questionnaire_responses[qr["id"]] = SiteQuestionnaireResponse(**qr)

    # ------------------------------------------------------------------
    # Feasibility Study CRUD
    # ------------------------------------------------------------------

    def list_studies(
        self,
        *,
        status: FeasibilityStatus | None = None,
        therapeutic_area: str | None = None,
    ) -> list[FeasibilityStudy]:
        """List feasibility studies with optional filters."""
        with self._lock:
            result = list(self._studies.values())

        if status is not None:
            result = [s for s in result if s.status == status]
        if therapeutic_area is not None:
            result = [s for s in result if s.therapeutic_area.lower() == therapeutic_area.lower()]

        return sorted(result, key=lambda s: s.initiated_date, reverse=True)

    def get_study(self, study_id: str) -> FeasibilityStudy | None:
        """Get a single feasibility study by ID."""
        with self._lock:
            return self._studies.get(study_id)

    def create_study(self, payload: FeasibilityStudyCreate) -> FeasibilityStudy:
        """Create a new feasibility study."""
        now = datetime.now(timezone.utc)
        study_id = f"FS-{uuid4().hex[:8].upper()}"
        study = FeasibilityStudy(
            id=study_id,
            trial_id=payload.trial_id,
            protocol_id=payload.protocol_id,
            protocol_version=payload.protocol_version,
            therapeutic_area=payload.therapeutic_area,
            indication=payload.indication,
            phase=payload.phase,
            status=FeasibilityStatus.DRAFT,
            initiated_date=now,
            completed_date=None,
            lead_analyst=payload.lead_analyst,
            target_enrollment=payload.target_enrollment,
            enrollment_duration_months=payload.enrollment_duration_months,
            target_countries=payload.target_countries,
            target_sites_count=payload.target_sites_count,
            overall_feasibility_score=None,
        )
        with self._lock:
            self._studies[study_id] = study
        logger.info("Created feasibility study %s for protocol %s", study_id, payload.protocol_id)
        return study

    def update_study(self, study_id: str, payload: FeasibilityStudyUpdate) -> FeasibilityStudy | None:
        """Update an existing feasibility study."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._studies.get(study_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set completed_date when status transitions to completed
            if "status" in updates:
                new_status = updates["status"]
                if isinstance(new_status, str):
                    new_status = FeasibilityStatus(new_status)
                if new_status == FeasibilityStatus.COMPLETED and existing.status != FeasibilityStatus.COMPLETED:
                    data["completed_date"] = now

            data.update(updates)
            updated = FeasibilityStudy(**data)
            self._studies[study_id] = updated
        return updated

    def delete_study(self, study_id: str) -> bool:
        """Delete a feasibility study. Returns True if deleted."""
        with self._lock:
            if study_id in self._studies:
                del self._studies[study_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Site Assessments
    # ------------------------------------------------------------------

    def list_site_assessments(
        self,
        study_id: str,
        *,
        country: str | None = None,
        site_rating: SiteRating | None = None,
    ) -> list[SiteAssessment]:
        """List site assessments for a study."""
        with self._lock:
            result = [
                sa for sa in self._site_assessments.values()
                if sa.study_id == study_id
            ]

        if country is not None:
            result = [sa for sa in result if sa.country.lower() == country.lower()]
        if site_rating is not None:
            result = [sa for sa in result if sa.site_rating == site_rating]

        return sorted(result, key=lambda sa: sa.assessed_date, reverse=True)

    def get_site_assessment(self, assessment_id: str) -> SiteAssessment | None:
        """Get a single site assessment by ID."""
        with self._lock:
            return self._site_assessments.get(assessment_id)

    def create_site_assessment(
        self, study_id: str, payload: SiteAssessmentCreate
    ) -> SiteAssessment:
        """Create a new site assessment and auto-compute its rating."""
        now = datetime.now(timezone.utc)
        assessment_id = f"SA-{uuid4().hex[:8].upper()}"

        # Compute site rating from sub-scores
        site_rating = self._compute_site_rating(
            payload.infrastructure_score,
            payload.regulatory_readiness,
            payload.staff_availability,
            payload.lab_capabilities,
            payload.pharmacy_capabilities,
        )

        assessment = SiteAssessment(
            id=assessment_id,
            study_id=study_id,
            site_id=payload.site_id,
            site_name=payload.site_name,
            country=payload.country,
            investigator_name=payload.investigator_name,
            investigator_experience_years=payload.investigator_experience_years,
            competing_studies_count=payload.competing_studies_count,
            patient_pool_estimate=payload.patient_pool_estimate,
            annual_enrollment_estimate=payload.annual_enrollment_estimate,
            site_rating=site_rating,
            infrastructure_score=payload.infrastructure_score,
            regulatory_readiness=payload.regulatory_readiness,
            staff_availability=payload.staff_availability,
            lab_capabilities=payload.lab_capabilities,
            pharmacy_capabilities=payload.pharmacy_capabilities,
            notes=payload.notes,
            assessed_date=now,
            assessed_by=payload.assessed_by,
        )
        with self._lock:
            self._site_assessments[assessment_id] = assessment
        logger.info("Created site assessment %s for study %s", assessment_id, study_id)
        return assessment

    def update_site_assessment(
        self, assessment_id: str, payload: SiteAssessmentUpdate
    ) -> SiteAssessment | None:
        """Update a site assessment and recompute rating if scores changed."""
        with self._lock:
            existing = self._site_assessments.get(assessment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)

            # Recompute rating if any score was updated
            score_fields = {
                "infrastructure_score", "regulatory_readiness",
                "staff_availability", "lab_capabilities", "pharmacy_capabilities",
            }
            if score_fields & set(updates.keys()):
                data["site_rating"] = self._compute_site_rating(
                    data["infrastructure_score"],
                    data["regulatory_readiness"],
                    data["staff_availability"],
                    data["lab_capabilities"],
                    data["pharmacy_capabilities"],
                )

            updated = SiteAssessment(**data)
            self._site_assessments[assessment_id] = updated
        return updated

    def score_site(self, assessment_id: str) -> SiteAssessment | None:
        """Recompute the site rating for an existing assessment."""
        with self._lock:
            existing = self._site_assessments.get(assessment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            data["site_rating"] = self._compute_site_rating(
                data["infrastructure_score"],
                data["regulatory_readiness"],
                data["staff_availability"],
                data["lab_capabilities"],
                data["pharmacy_capabilities"],
            )
            updated = SiteAssessment(**data)
            self._site_assessments[assessment_id] = updated
        return updated

    @staticmethod
    def _compute_site_rating(
        infrastructure: float,
        regulatory: float,
        staff: float,
        lab: float,
        pharmacy: float,
    ) -> SiteRating:
        """Compute site rating from weighted sub-scores."""
        avg = (infrastructure * 0.25 + regulatory * 0.25 + staff * 0.20
               + lab * 0.15 + pharmacy * 0.15)
        if avg >= RATING_EXCELLENT:
            return SiteRating.EXCELLENT
        elif avg >= RATING_GOOD:
            return SiteRating.GOOD
        elif avg >= RATING_ACCEPTABLE:
            return SiteRating.ACCEPTABLE
        elif avg >= RATING_MARGINAL:
            return SiteRating.MARGINAL
        else:
            return SiteRating.NOT_SUITABLE

    # ------------------------------------------------------------------
    # Competitive Landscape
    # ------------------------------------------------------------------

    def list_competitive_landscape(
        self,
        study_id: str,
        *,
        threat_level: CompetitiveThreatLevel | None = None,
    ) -> list[CompetitiveLandscape]:
        """List competitive landscape entries for a study."""
        with self._lock:
            result = [
                cl for cl in self._competitive_entries.values()
                if cl.study_id == study_id
            ]

        if threat_level is not None:
            result = [cl for cl in result if cl.threat_level == threat_level]

        return sorted(result, key=lambda cl: {
            CompetitiveThreatLevel.CRITICAL: 0,
            CompetitiveThreatLevel.HIGH: 1,
            CompetitiveThreatLevel.MODERATE: 2,
            CompetitiveThreatLevel.LOW: 3,
        }.get(cl.threat_level, 4))

    def get_competitive_entry(self, entry_id: str) -> CompetitiveLandscape | None:
        """Get a single competitive landscape entry."""
        with self._lock:
            return self._competitive_entries.get(entry_id)

    def create_competitive_entry(
        self, study_id: str, payload: CompetitiveLandscapeCreate
    ) -> CompetitiveLandscape:
        """Add a competitive landscape entry."""
        entry_id = f"CL-{uuid4().hex[:8].upper()}"
        entry = CompetitiveLandscape(
            id=entry_id,
            study_id=study_id,
            competitor_trial_id=payload.competitor_trial_id,
            sponsor_name=payload.sponsor_name,
            phase=payload.phase,
            indication=payload.indication,
            estimated_enrollment=payload.estimated_enrollment,
            enrollment_start_date=payload.enrollment_start_date,
            competing_sites_overlap=payload.competing_sites_overlap,
            threat_level=payload.threat_level,
            notes=payload.notes,
        )
        with self._lock:
            self._competitive_entries[entry_id] = entry
        logger.info("Created competitive entry %s for study %s", entry_id, study_id)
        return entry

    def update_competitive_entry(
        self, entry_id: str, payload: CompetitiveLandscapeUpdate
    ) -> CompetitiveLandscape | None:
        """Update a competitive landscape entry."""
        with self._lock:
            existing = self._competitive_entries.get(entry_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CompetitiveLandscape(**data)
            self._competitive_entries[entry_id] = updated
        return updated

    def get_competitive_landscape(self, study_id: str) -> list[CompetitiveLandscape]:
        """Get complete competitive landscape for a study (alias for list)."""
        return self.list_competitive_landscape(study_id)

    # ------------------------------------------------------------------
    # Enrollment Projections
    # ------------------------------------------------------------------

    def list_enrollment_projections(
        self, study_id: str
    ) -> list[EnrollmentProjection]:
        """List enrollment projection scenarios for a study."""
        with self._lock:
            result = [
                ep for ep in self._enrollment_projections.values()
                if ep.study_id == study_id
            ]
        return sorted(result, key=lambda ep: ep.confidence_level, reverse=True)

    def get_enrollment_projection(self, projection_id: str) -> EnrollmentProjection | None:
        """Get a single enrollment projection."""
        with self._lock:
            return self._enrollment_projections.get(projection_id)

    def create_enrollment_projection(
        self, study_id: str, payload: EnrollmentProjectionCreate
    ) -> EnrollmentProjection:
        """Create an enrollment projection by computing projections from inputs."""
        proj_id = f"EP-{uuid4().hex[:8].upper()}"

        # Compute projected values
        gross_monthly = payload.sites_count * payload.patients_per_site_per_month
        net_monthly = gross_monthly * (1.0 - payload.screen_failure_rate)

        # Get study target
        study = self._studies.get(study_id)
        target = study.target_enrollment if study else 300

        if net_monthly > 0:
            months_needed = math.ceil(target / net_monthly)
        else:
            months_needed = 36  # fallback

        total_screened = int(gross_monthly * months_needed)
        total_enrolled = int(total_screened * (1.0 - payload.screen_failure_rate))
        total_completing = int(total_enrolled * (1.0 - payload.dropout_rate))

        # Determine risk level based on enrollment rate vs target
        ratio = total_completing / max(1, target)
        if ratio >= 1.2:
            risk_level = EnrollmentRisk.LOW
            confidence = 80.0
        elif ratio >= 1.0:
            risk_level = EnrollmentRisk.MEDIUM
            confidence = 65.0
        elif ratio >= 0.8:
            risk_level = EnrollmentRisk.HIGH
            confidence = 45.0
        else:
            risk_level = EnrollmentRisk.VERY_HIGH
            confidence = 25.0

        projection = EnrollmentProjection(
            id=proj_id,
            study_id=study_id,
            scenario_name=payload.scenario_name,
            sites_count=payload.sites_count,
            patients_per_site_per_month=payload.patients_per_site_per_month,
            screen_failure_rate=payload.screen_failure_rate,
            dropout_rate=payload.dropout_rate,
            enrollment_start_date=payload.enrollment_start_date,
            projected_enrollment_months=months_needed,
            projected_total_enrolled=total_completing,
            confidence_level=confidence,
            risk_level=risk_level,
            assumptions=payload.assumptions,
        )
        with self._lock:
            self._enrollment_projections[proj_id] = projection
        logger.info("Created enrollment projection %s for study %s", proj_id, study_id)
        return projection

    def generate_enrollment_projections(
        self, study_id: str
    ) -> list[EnrollmentProjection]:
        """Auto-generate standard projection scenarios for a study."""
        study = self._studies.get(study_id)
        if study is None:
            return []

        scenarios = [
            EnrollmentProjectionCreate(
                scenario_name="Auto - Optimistic",
                sites_count=int(study.target_sites_count * 1.1),
                patients_per_site_per_month=0.6,
                screen_failure_rate=0.20,
                dropout_rate=0.08,
                assumptions="Optimistic: fast activation, low screen failure.",
            ),
            EnrollmentProjectionCreate(
                scenario_name="Auto - Base Case",
                sites_count=study.target_sites_count,
                patients_per_site_per_month=0.45,
                screen_failure_rate=0.28,
                dropout_rate=0.12,
                assumptions="Base case: industry-average rates.",
            ),
            EnrollmentProjectionCreate(
                scenario_name="Auto - Conservative",
                sites_count=int(study.target_sites_count * 0.8),
                patients_per_site_per_month=0.3,
                screen_failure_rate=0.35,
                dropout_rate=0.18,
                assumptions="Conservative: competition impact, delays.",
            ),
        ]

        created = []
        for sc in scenarios:
            proj = self.create_enrollment_projection(study_id, sc)
            created.append(proj)

        return created

    # ------------------------------------------------------------------
    # Questionnaire
    # ------------------------------------------------------------------

    def list_questions(self, study_id: str) -> list[FeasibilityQuestion]:
        """List questionnaire questions for a study."""
        with self._lock:
            result = [
                q for q in self._questions.values()
                if q.study_id == study_id
            ]
        return sorted(result, key=lambda q: q.display_order)

    def create_question(
        self, study_id: str, payload: FeasibilityQuestionCreate
    ) -> FeasibilityQuestion:
        """Create a questionnaire question."""
        question_id = f"FQ-{uuid4().hex[:8].upper()}"
        question = FeasibilityQuestion(
            id=question_id,
            study_id=study_id,
            category=payload.category,
            question_text=payload.question_text,
            response_type=payload.response_type,
            required=payload.required,
            display_order=payload.display_order,
        )
        with self._lock:
            self._questions[question_id] = question
        logger.info("Created question %s for study %s", question_id, study_id)
        return question

    def submit_questionnaire_response(
        self, study_id: str, payload: QuestionnaireResponseCreate
    ) -> SiteQuestionnaireResponse:
        """Submit a questionnaire response from a site."""
        now = datetime.now(timezone.utc)
        response_id = f"QR-{uuid4().hex[:8].upper()}"

        # Validate question exists
        question = self._questions.get(payload.question_id)
        if question is None:
            raise ValueError(f"Question '{payload.question_id}' not found")
        if question.study_id != study_id:
            raise ValueError(f"Question '{payload.question_id}' does not belong to study '{study_id}'")

        response = SiteQuestionnaireResponse(
            id=response_id,
            study_id=study_id,
            site_id=payload.site_id,
            question_id=payload.question_id,
            response_value=payload.response_value,
            responded_date=now,
            responded_by=payload.responded_by,
        )
        with self._lock:
            self._questionnaire_responses[response_id] = response
        logger.info("Submitted response %s for study %s", response_id, study_id)
        return response

    def list_questionnaire_responses(
        self, study_id: str, *, site_id: str | None = None
    ) -> list[SiteQuestionnaireResponse]:
        """List questionnaire responses for a study."""
        with self._lock:
            result = [
                r for r in self._questionnaire_responses.values()
                if r.study_id == study_id
            ]
        if site_id is not None:
            result = [r for r in result if r.site_id == site_id]
        return sorted(result, key=lambda r: r.responded_date, reverse=True)

    # ------------------------------------------------------------------
    # Feasibility Summary
    # ------------------------------------------------------------------

    def get_feasibility_summary(self, study_id: str) -> FeasibilitySummary | None:
        """Compute a comprehensive feasibility summary for a study."""
        study = self._studies.get(study_id)
        if study is None:
            return None

        # Site assessments
        assessments = self.list_site_assessments(study_id)
        total_sites = len(assessments)

        sites_by_rating: dict[str, int] = {}
        total_score = 0.0
        for sa in assessments:
            key = sa.site_rating.value
            sites_by_rating[key] = sites_by_rating.get(key, 0) + 1
            avg_sub = (sa.infrastructure_score + sa.regulatory_readiness
                       + sa.staff_availability + sa.lab_capabilities
                       + sa.pharmacy_capabilities) / 5.0
            total_score += avg_sub

        avg_score = round(total_score / max(1, total_sites), 1)

        # Enrollment projections
        projections = self.list_enrollment_projections(study_id)
        if projections:
            enrollments = [p.projected_total_enrolled for p in projections]
            enrollment_range = {"min": min(enrollments), "max": max(enrollments)}
        else:
            enrollment_range = {"min": 0, "max": 0}

        # Competitive landscape
        competitors = self.list_competitive_landscape(study_id)

        # Risk identification
        risks: list[str] = []
        critical_competitors = [c for c in competitors if c.threat_level == CompetitiveThreatLevel.CRITICAL]
        if critical_competitors:
            risks.append(f"{len(critical_competitors)} critical competitive threat(s) identified")

        not_suitable = sites_by_rating.get("not_suitable", 0)
        marginal = sites_by_rating.get("marginal", 0)
        if not_suitable + marginal > total_sites * 0.3 and total_sites > 0:
            risks.append("Over 30% of assessed sites rated marginal or not suitable")

        if projections:
            high_risk_projections = [
                p for p in projections
                if p.risk_level in (EnrollmentRisk.HIGH, EnrollmentRisk.VERY_HIGH)
            ]
            if high_risk_projections:
                risks.append(f"{len(high_risk_projections)} enrollment scenario(s) at high/very-high risk")

        overlap_total = sum(c.competing_sites_overlap for c in competitors)
        if overlap_total > 20:
            risks.append(f"High site overlap with competitors ({overlap_total} total)")

        if not risks:
            risks.append("No major risks identified")

        # Recommendations
        recommendations: list[str] = []
        excellent = sites_by_rating.get("excellent", 0)
        good = sites_by_rating.get("good", 0)
        if excellent + good < study.target_sites_count:
            recommendations.append(
                f"Assess additional sites: {excellent + good} suitable sites vs {study.target_sites_count} target"
            )

        if critical_competitors:
            recommendations.append("Develop competitive enrollment strategy for overlapping sites")

        if avg_score < 60:
            recommendations.append("Consider revising eligibility criteria to expand patient pool")
        elif avg_score >= 80:
            recommendations.append("Strong feasibility profile supports proceeding to site selection")

        if not recommendations:
            recommendations.append("Continue monitoring competitive landscape")

        # Update study feasibility score
        with self._lock:
            if study_id in self._studies:
                data = self._studies[study_id].model_dump()
                data["overall_feasibility_score"] = avg_score
                self._studies[study_id] = FeasibilityStudy(**data)

        return FeasibilitySummary(
            study_id=study_id,
            total_sites_assessed=total_sites,
            sites_by_rating=sites_by_rating,
            avg_feasibility_score=avg_score,
            projected_enrollment_range=enrollment_range,
            top_risks=risks,
            recommendations=recommendations,
        )

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> FeasibilityMetrics:
        """Compute aggregated feasibility operational metrics."""
        with self._lock:
            studies = list(self._studies.values())
            assessments = list(self._site_assessments.values())
            projections = list(self._enrollment_projections.values())

        total_studies = len(studies)
        active_studies = sum(
            1 for s in studies
            if s.status in (FeasibilityStatus.DRAFT, FeasibilityStatus.IN_PROGRESS)
        )

        sites_total = len(assessments)

        # Average sites per study
        if total_studies > 0:
            study_ids_with_sites = set()
            sites_per_study: dict[str, int] = {}
            for sa in assessments:
                sites_per_study[sa.study_id] = sites_per_study.get(sa.study_id, 0) + 1
                study_ids_with_sites.add(sa.study_id)
            avg_sites = round(sum(sites_per_study.values()) / max(1, len(sites_per_study)), 1)
        else:
            avg_sites = 0.0

        # Average feasibility score across studies that have one
        scored_studies = [s for s in studies if s.overall_feasibility_score is not None]
        if scored_studies:
            avg_feas_score = round(
                sum(s.overall_feasibility_score for s in scored_studies) / len(scored_studies), 1
            )
        else:
            avg_feas_score = 0.0

        # Average enrollment projection
        if projections:
            avg_enrollment = round(
                sum(p.projected_total_enrolled for p in projections) / len(projections), 1
            )
        else:
            avg_enrollment = 0.0

        return FeasibilityMetrics(
            total_studies=total_studies,
            active_studies=active_studies,
            avg_sites_per_study=avg_sites,
            avg_feasibility_score=avg_feas_score,
            sites_assessed_total=sites_total,
            avg_enrollment_projection=avg_enrollment,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: ProtocolFeasibilityService | None = None
_lock = threading.Lock()


def get_protocol_feasibility_service() -> ProtocolFeasibilityService:
    """Return the singleton ProtocolFeasibilityService instance."""
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = ProtocolFeasibilityService()
    return _instance


def reset_protocol_feasibility_service() -> None:
    """Reset the singleton (for testing)."""
    global _instance
    with _lock:
        _instance = None
