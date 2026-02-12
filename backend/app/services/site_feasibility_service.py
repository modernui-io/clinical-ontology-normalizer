"""Site Feasibility Management Service (SITE-FEAS).

Manages site feasibility operations: site assessments, investigator qualification,
patient pool analysis, capability evaluations, feasibility surveys, and
site feasibility operational metrics.

Usage:
    from app.services.site_feasibility_service import (
        get_site_feasibility_service,
    )

    svc = get_site_feasibility_service()
    assessments = svc.list_site_assessments()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.site_feasibility import (
    AssessmentStatus,
    CapabilityArea,
    CapabilityEvaluation,
    CapabilityEvaluationCreate,
    CapabilityEvaluationUpdate,
    FeasibilityResult,
    FeasibilitySurvey,
    FeasibilitySurveyCreate,
    FeasibilitySurveyUpdate,
    InvestigatorQualification,
    InvestigatorQualificationCreate,
    InvestigatorQualificationUpdate,
    PatientPoolAnalysis,
    PatientPoolAnalysisCreate,
    PatientPoolAnalysisUpdate,
    QualificationStatus,
    SiteAssessment,
    SiteAssessmentCreate,
    SiteAssessmentUpdate,
    SiteFeasibilityMetrics,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class SiteFeasibilityService:
    """In-memory Site Feasibility engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._site_assessments: dict[str, SiteAssessment] = {}
        self._investigator_qualifications: dict[str, InvestigatorQualification] = {}
        self._patient_pool_analyses: dict[str, PatientPoolAnalysis] = {}
        self._capability_evaluations: dict[str, CapabilityEvaluation] = {}
        self._feasibility_surveys: dict[str, FeasibilitySurvey] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic site feasibility data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 12 Site Assessments ---
        assessments_data = [
            {
                "id": "SA-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "site_name": "Memorial Hermann Hospital",
                "country": "United States",
                "region": "South Central",
                "assessment_date": now - timedelta(days=120),
                "status": AssessmentStatus.COMPLETED,
                "result": FeasibilityResult.HIGHLY_FEASIBLE,
                "overall_score": 92.5,
                "enrollment_potential": 45,
                "competitive_trials": 1,
                "estimated_activation_weeks": 8,
                "irb_type": "central",
                "previous_trial_experience": 12,
                "therapeutic_area_experience": True,
                "assessor": "Dr. Sarah Mitchell",
                "comments": "Excellent ophthalmology department with strong enrollment history.",
                "created_at": now - timedelta(days=130),
            },
            {
                "id": "SA-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "site_name": "Cleveland Clinic Foundation",
                "country": "United States",
                "region": "Midwest",
                "assessment_date": now - timedelta(days=115),
                "status": AssessmentStatus.COMPLETED,
                "result": FeasibilityResult.FEASIBLE,
                "overall_score": 84.0,
                "enrollment_potential": 30,
                "competitive_trials": 2,
                "estimated_activation_weeks": 10,
                "irb_type": "central",
                "previous_trial_experience": 8,
                "therapeutic_area_experience": True,
                "assessor": "Dr. Sarah Mitchell",
                "comments": "Strong research infrastructure. Moderate competition from other retinal trials.",
                "created_at": now - timedelta(days=125),
            },
            {
                "id": "SA-003",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "site_name": "Johns Hopkins Research Center",
                "country": "United States",
                "region": "Mid-Atlantic",
                "assessment_date": now - timedelta(days=90),
                "status": AssessmentStatus.COMPLETED,
                "result": FeasibilityResult.HIGHLY_FEASIBLE,
                "overall_score": 95.0,
                "enrollment_potential": 60,
                "competitive_trials": 1,
                "estimated_activation_weeks": 6,
                "irb_type": "local",
                "previous_trial_experience": 20,
                "therapeutic_area_experience": True,
                "assessor": "David Park",
                "comments": "Leading dermatology and immunology programs. Outstanding patient access.",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "SA-004",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "site_name": "Mayo Clinic Jacksonville",
                "country": "United States",
                "region": "Southeast",
                "assessment_date": now - timedelta(days=85),
                "status": AssessmentStatus.COMPLETED,
                "result": FeasibilityResult.CONDITIONALLY_FEASIBLE,
                "overall_score": 68.0,
                "enrollment_potential": 20,
                "competitive_trials": 3,
                "estimated_activation_weeks": 14,
                "irb_type": "central",
                "previous_trial_experience": 5,
                "therapeutic_area_experience": False,
                "assessor": "David Park",
                "comments": "Good infrastructure but limited dermatology trial experience. Additional training needed.",
                "created_at": now - timedelta(days=95),
            },
            {
                "id": "SA-005",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "site_name": "Duke Clinical Research Institute",
                "country": "United States",
                "region": "Southeast",
                "assessment_date": now - timedelta(days=75),
                "status": AssessmentStatus.COMPLETED,
                "result": FeasibilityResult.FEASIBLE,
                "overall_score": 80.5,
                "enrollment_potential": 35,
                "competitive_trials": 2,
                "estimated_activation_weeks": 10,
                "irb_type": "central",
                "previous_trial_experience": 15,
                "therapeutic_area_experience": True,
                "assessor": "Jennifer Lee",
                "comments": "Strong oncology program with established checkpoint inhibitor trial experience.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "SA-006",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "site_name": "Cedars-Sinai Medical Center",
                "country": "United States",
                "region": "West",
                "assessment_date": now - timedelta(days=70),
                "status": AssessmentStatus.COMPLETED,
                "result": FeasibilityResult.FEASIBLE,
                "overall_score": 78.0,
                "enrollment_potential": 25,
                "competitive_trials": 4,
                "estimated_activation_weeks": 12,
                "irb_type": "local",
                "previous_trial_experience": 10,
                "therapeutic_area_experience": True,
                "assessor": "Jennifer Lee",
                "comments": "Good oncology department but high competitive trial burden in LA area.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "SA-007",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-107",
                "site_name": "Mass General Brigham",
                "country": "United States",
                "region": "Northeast",
                "assessment_date": now - timedelta(days=60),
                "status": AssessmentStatus.COMPLETED,
                "result": FeasibilityResult.NOT_FEASIBLE,
                "overall_score": 35.0,
                "enrollment_potential": 10,
                "competitive_trials": 6,
                "estimated_activation_weeks": 20,
                "irb_type": "local",
                "previous_trial_experience": 3,
                "therapeutic_area_experience": False,
                "assessor": "Dr. Sarah Mitchell",
                "comments": "Excessive competitive trial burden and limited retinal specialist availability.",
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "SA-008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-108",
                "site_name": "Stanford Health Care",
                "country": "United States",
                "region": "West",
                "assessment_date": now - timedelta(days=45),
                "status": AssessmentStatus.COMPLETED,
                "result": FeasibilityResult.HIGHLY_FEASIBLE,
                "overall_score": 91.0,
                "enrollment_potential": 50,
                "competitive_trials": 1,
                "estimated_activation_weeks": 8,
                "irb_type": "central",
                "previous_trial_experience": 18,
                "therapeutic_area_experience": True,
                "assessor": "David Park",
                "comments": "Top-tier allergy and immunology department with excellent patient pipeline.",
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "SA-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-201",
                "site_name": "Charite Universitatsmedizin Berlin",
                "country": "Germany",
                "region": "Europe",
                "assessment_date": now - timedelta(days=30),
                "status": AssessmentStatus.IN_PROGRESS,
                "result": FeasibilityResult.PENDING,
                "overall_score": 0.0,
                "enrollment_potential": 40,
                "competitive_trials": 2,
                "estimated_activation_weeks": 16,
                "irb_type": "local",
                "previous_trial_experience": 14,
                "therapeutic_area_experience": True,
                "assessor": "Jennifer Lee",
                "comments": "European site assessment in progress. Regulatory review pending.",
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "SA-010",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-202",
                "site_name": "Moorfields Eye Hospital",
                "country": "United Kingdom",
                "region": "Europe",
                "assessment_date": now - timedelta(days=20),
                "status": AssessmentStatus.PLANNED,
                "result": FeasibilityResult.PENDING,
                "overall_score": 0.0,
                "enrollment_potential": 55,
                "competitive_trials": 1,
                "estimated_activation_weeks": 12,
                "irb_type": "local",
                "previous_trial_experience": 25,
                "therapeutic_area_experience": True,
                "assessor": "Dr. Sarah Mitchell",
                "comments": "World-leading ophthalmology center. Assessment scheduled.",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "SA-011",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-203",
                "site_name": "University of Tokyo Hospital",
                "country": "Japan",
                "region": "Asia-Pacific",
                "assessment_date": now - timedelta(days=15),
                "status": AssessmentStatus.PLANNED,
                "result": FeasibilityResult.PENDING,
                "overall_score": 0.0,
                "enrollment_potential": 35,
                "competitive_trials": 2,
                "estimated_activation_weeks": 18,
                "irb_type": "local",
                "previous_trial_experience": 10,
                "therapeutic_area_experience": True,
                "assessor": "David Park",
                "comments": "Key APAC site. Regulatory pathway assessment needed.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "SA-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-109",
                "site_name": "MD Anderson Cancer Center",
                "country": "United States",
                "region": "South Central",
                "assessment_date": now - timedelta(days=10),
                "status": AssessmentStatus.ON_HOLD,
                "result": FeasibilityResult.PENDING,
                "overall_score": 0.0,
                "enrollment_potential": 70,
                "competitive_trials": 5,
                "estimated_activation_weeks": 10,
                "irb_type": "local",
                "previous_trial_experience": 30,
                "therapeutic_area_experience": True,
                "assessor": "Jennifer Lee",
                "comments": "Premier oncology center. On hold pending budget negotiation.",
                "created_at": now - timedelta(days=15),
            },
        ]

        for a in assessments_data:
            self._site_assessments[a["id"]] = SiteAssessment(**a)

        # --- 12 Investigator Qualifications ---
        investigators_data = [
            {
                "id": "IQ-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "investigator_name": "Dr. Robert Chen",
                "medical_license_number": "TX-ML-445892",
                "specialty": "Ophthalmology - Retinal Surgery",
                "years_experience": 18,
                "gcp_certified": True,
                "gcp_expiry_date": now + timedelta(days=365),
                "cv_on_file": True,
                "financial_disclosure_complete": True,
                "previous_studies_count": 12,
                "enrollment_track_record": 95.0,
                "qualification_status": QualificationStatus.QUALIFIED,
                "debarment_checked": True,
                "sanctions_checked": True,
                "reviewed_by": "Dr. Sarah Mitchell",
                "review_date": now - timedelta(days=100),
                "notes": "Excellent track record. PI for 3 prior Regeneron retinal studies.",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "IQ-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "investigator_name": "Dr. Angela Vasquez",
                "medical_license_number": "OH-ML-331057",
                "specialty": "Ophthalmology - Medical Retina",
                "years_experience": 14,
                "gcp_certified": True,
                "gcp_expiry_date": now + timedelta(days=200),
                "cv_on_file": True,
                "financial_disclosure_complete": True,
                "previous_studies_count": 8,
                "enrollment_track_record": 88.0,
                "qualification_status": QualificationStatus.QUALIFIED,
                "debarment_checked": True,
                "sanctions_checked": True,
                "reviewed_by": "Dr. Sarah Mitchell",
                "review_date": now - timedelta(days=95),
                "notes": "Strong enrollment history at Cleveland Clinic.",
                "created_at": now - timedelta(days=115),
            },
            {
                "id": "IQ-003",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "investigator_name": "Dr. Michael Takahashi",
                "medical_license_number": "MD-ML-778234",
                "specialty": "Dermatology - Atopic Dermatitis",
                "years_experience": 22,
                "gcp_certified": True,
                "gcp_expiry_date": now + timedelta(days=500),
                "cv_on_file": True,
                "financial_disclosure_complete": True,
                "previous_studies_count": 20,
                "enrollment_track_record": 97.0,
                "qualification_status": QualificationStatus.QUALIFIED,
                "debarment_checked": True,
                "sanctions_checked": True,
                "reviewed_by": "David Park",
                "review_date": now - timedelta(days=80),
                "notes": "KOL in atopic dermatitis. Outstanding enrollment track record.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "IQ-004",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "investigator_name": "Dr. Patricia Bowman",
                "medical_license_number": "FL-ML-556901",
                "specialty": "Allergy & Immunology",
                "years_experience": 7,
                "gcp_certified": True,
                "gcp_expiry_date": now + timedelta(days=150),
                "cv_on_file": True,
                "financial_disclosure_complete": False,
                "previous_studies_count": 3,
                "enrollment_track_record": 72.0,
                "qualification_status": QualificationStatus.CONDITIONALLY_QUALIFIED,
                "debarment_checked": True,
                "sanctions_checked": True,
                "reviewed_by": "David Park",
                "review_date": now - timedelta(days=75),
                "notes": "Financial disclosure pending. Limited but growing experience.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "IQ-005",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "investigator_name": "Dr. James Okafor",
                "medical_license_number": "NC-ML-892145",
                "specialty": "Medical Oncology - Immuno-Oncology",
                "years_experience": 16,
                "gcp_certified": True,
                "gcp_expiry_date": now + timedelta(days=300),
                "cv_on_file": True,
                "financial_disclosure_complete": True,
                "previous_studies_count": 15,
                "enrollment_track_record": 90.0,
                "qualification_status": QualificationStatus.QUALIFIED,
                "debarment_checked": True,
                "sanctions_checked": True,
                "reviewed_by": "Jennifer Lee",
                "review_date": now - timedelta(days=65),
                "notes": "Extensive checkpoint inhibitor experience. Leads IO program at Duke.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "IQ-006",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "investigator_name": "Dr. Lisa Fernandez",
                "medical_license_number": "CA-ML-667823",
                "specialty": "Medical Oncology",
                "years_experience": 11,
                "gcp_certified": True,
                "gcp_expiry_date": now + timedelta(days=180),
                "cv_on_file": True,
                "financial_disclosure_complete": True,
                "previous_studies_count": 10,
                "enrollment_track_record": 82.0,
                "qualification_status": QualificationStatus.QUALIFIED,
                "debarment_checked": True,
                "sanctions_checked": True,
                "reviewed_by": "Jennifer Lee",
                "review_date": now - timedelta(days=60),
                "notes": "Solid oncology background with growing IO portfolio.",
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "IQ-007",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-107",
                "investigator_name": "Dr. William Patel",
                "medical_license_number": "MA-ML-224556",
                "specialty": "Ophthalmology",
                "years_experience": 5,
                "gcp_certified": False,
                "gcp_expiry_date": None,
                "cv_on_file": False,
                "financial_disclosure_complete": False,
                "previous_studies_count": 2,
                "enrollment_track_record": 55.0,
                "qualification_status": QualificationStatus.NOT_QUALIFIED,
                "debarment_checked": True,
                "sanctions_checked": False,
                "reviewed_by": "Dr. Sarah Mitchell",
                "review_date": now - timedelta(days=50),
                "notes": "Insufficient GCP certification and limited trial experience. GCP training required.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "IQ-008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-108",
                "investigator_name": "Dr. Karen Nguyen",
                "medical_license_number": "CA-ML-889012",
                "specialty": "Dermatology - Clinical Research",
                "years_experience": 19,
                "gcp_certified": True,
                "gcp_expiry_date": now + timedelta(days=400),
                "cv_on_file": True,
                "financial_disclosure_complete": True,
                "previous_studies_count": 18,
                "enrollment_track_record": 93.0,
                "qualification_status": QualificationStatus.QUALIFIED,
                "debarment_checked": True,
                "sanctions_checked": True,
                "reviewed_by": "David Park",
                "review_date": now - timedelta(days=35),
                "notes": "Highly experienced dermatology PI. Stanford research leader.",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "IQ-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-201",
                "investigator_name": "Prof. Dr. Hans Weber",
                "medical_license_number": "DE-ML-445123",
                "specialty": "Medical Oncology",
                "years_experience": 25,
                "gcp_certified": True,
                "gcp_expiry_date": now + timedelta(days=600),
                "cv_on_file": True,
                "financial_disclosure_complete": False,
                "previous_studies_count": 22,
                "enrollment_track_record": 91.0,
                "qualification_status": QualificationStatus.PENDING_REVIEW,
                "debarment_checked": False,
                "sanctions_checked": False,
                "reviewed_by": None,
                "review_date": None,
                "notes": "Awaiting EU financial disclosure and debarment verification.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "IQ-010",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-202",
                "investigator_name": "Prof. Andrew Blackwood",
                "medical_license_number": "UK-GMC-7789001",
                "specialty": "Ophthalmology - Vitreoretinal Surgery",
                "years_experience": 28,
                "gcp_certified": True,
                "gcp_expiry_date": now + timedelta(days=450),
                "cv_on_file": True,
                "financial_disclosure_complete": True,
                "previous_studies_count": 30,
                "enrollment_track_record": 96.0,
                "qualification_status": QualificationStatus.PENDING_REVIEW,
                "debarment_checked": False,
                "sanctions_checked": False,
                "reviewed_by": None,
                "review_date": None,
                "notes": "World-renowned vitreoretinal surgeon. Pending regulatory verification.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "IQ-011",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-203",
                "investigator_name": "Dr. Yuki Tanaka",
                "medical_license_number": "JP-ML-334567",
                "specialty": "Dermatology - Atopic Dermatitis",
                "years_experience": 15,
                "gcp_certified": True,
                "gcp_expiry_date": now + timedelta(days=250),
                "cv_on_file": False,
                "financial_disclosure_complete": False,
                "previous_studies_count": 8,
                "enrollment_track_record": 85.0,
                "qualification_status": QualificationStatus.DEFERRED,
                "debarment_checked": False,
                "sanctions_checked": False,
                "reviewed_by": "David Park",
                "review_date": now - timedelta(days=10),
                "notes": "Deferred pending CV submission and PMDA regulatory alignment.",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "IQ-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-109",
                "investigator_name": "Dr. Richard Chang",
                "medical_license_number": "TX-ML-990234",
                "specialty": "Medical Oncology - Thoracic",
                "years_experience": 20,
                "gcp_certified": True,
                "gcp_expiry_date": now + timedelta(days=350),
                "cv_on_file": True,
                "financial_disclosure_complete": True,
                "previous_studies_count": 25,
                "enrollment_track_record": 94.0,
                "qualification_status": QualificationStatus.PENDING_REVIEW,
                "debarment_checked": True,
                "sanctions_checked": True,
                "reviewed_by": None,
                "review_date": None,
                "notes": "MD Anderson PI. On hold pending site budget finalization.",
                "created_at": now - timedelta(days=10),
            },
        ]

        for iq in investigators_data:
            self._investigator_qualifications[iq["id"]] = InvestigatorQualification(**iq)

        # --- 12 Patient Pool Analyses ---
        patient_pool_data = [
            {
                "id": "PPA-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "analysis_date": now - timedelta(days=110),
                "indication": "Wet Age-Related Macular Degeneration (wAMD)",
                "estimated_prevalence": 8500,
                "estimated_eligible": 420,
                "screen_failure_rate_pct": 25.0,
                "expected_enrollment": 45,
                "enrollment_rate_per_month": 4.5,
                "data_source": "medical_records",
                "competing_study_impact_pct": 5.0,
                "seasonal_variation": False,
                "referral_network_available": True,
                "patient_database_size": 12000,
                "analyst": "Emily Rodriguez",
                "methodology_notes": "EMR query + referral network analysis. Strong retinal patient base.",
                "created_at": now - timedelta(days=115),
            },
            {
                "id": "PPA-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "analysis_date": now - timedelta(days=105),
                "indication": "Wet Age-Related Macular Degeneration (wAMD)",
                "estimated_prevalence": 6200,
                "estimated_eligible": 310,
                "screen_failure_rate_pct": 28.0,
                "expected_enrollment": 30,
                "enrollment_rate_per_month": 3.0,
                "data_source": "medical_records",
                "competing_study_impact_pct": 12.0,
                "seasonal_variation": False,
                "referral_network_available": True,
                "patient_database_size": 9500,
                "analyst": "Emily Rodriguez",
                "methodology_notes": "Cross-referenced with competing study enrollment data.",
                "created_at": now - timedelta(days=110),
            },
            {
                "id": "PPA-003",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "analysis_date": now - timedelta(days=80),
                "indication": "Moderate-to-Severe Atopic Dermatitis",
                "estimated_prevalence": 15000,
                "estimated_eligible": 1200,
                "screen_failure_rate_pct": 20.0,
                "expected_enrollment": 60,
                "enrollment_rate_per_month": 6.0,
                "data_source": "medical_records",
                "competing_study_impact_pct": 8.0,
                "seasonal_variation": True,
                "referral_network_available": True,
                "patient_database_size": 22000,
                "analyst": "Marcus Thompson",
                "methodology_notes": "Large dermatology patient base. Seasonal flare pattern analyzed.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "PPA-004",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "analysis_date": now - timedelta(days=75),
                "indication": "Moderate-to-Severe Atopic Dermatitis",
                "estimated_prevalence": 4800,
                "estimated_eligible": 280,
                "screen_failure_rate_pct": 35.0,
                "expected_enrollment": 20,
                "enrollment_rate_per_month": 2.0,
                "data_source": "claims_data",
                "competing_study_impact_pct": 18.0,
                "seasonal_variation": True,
                "referral_network_available": False,
                "patient_database_size": 7200,
                "analyst": "Marcus Thompson",
                "methodology_notes": "Limited local referral network. Claims data analysis supplemented.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "PPA-005",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "analysis_date": now - timedelta(days=65),
                "indication": "Advanced Cutaneous Squamous Cell Carcinoma (CSCC)",
                "estimated_prevalence": 3200,
                "estimated_eligible": 180,
                "screen_failure_rate_pct": 30.0,
                "expected_enrollment": 35,
                "enrollment_rate_per_month": 3.5,
                "data_source": "tumor_registry",
                "competing_study_impact_pct": 10.0,
                "seasonal_variation": False,
                "referral_network_available": True,
                "patient_database_size": 5800,
                "analyst": "Dr. Alicia Foster",
                "methodology_notes": "Tumor registry + referral from community oncology network.",
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "PPA-006",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "analysis_date": now - timedelta(days=60),
                "indication": "Advanced Cutaneous Squamous Cell Carcinoma (CSCC)",
                "estimated_prevalence": 2800,
                "estimated_eligible": 140,
                "screen_failure_rate_pct": 32.0,
                "expected_enrollment": 25,
                "enrollment_rate_per_month": 2.5,
                "data_source": "tumor_registry",
                "competing_study_impact_pct": 20.0,
                "seasonal_variation": False,
                "referral_network_available": True,
                "patient_database_size": 4500,
                "analyst": "Dr. Alicia Foster",
                "methodology_notes": "LA area has significant competing trial burden reducing eligible pool.",
                "created_at": now - timedelta(days=65),
            },
            {
                "id": "PPA-007",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-107",
                "analysis_date": now - timedelta(days=50),
                "indication": "Wet Age-Related Macular Degeneration (wAMD)",
                "estimated_prevalence": 5500,
                "estimated_eligible": 150,
                "screen_failure_rate_pct": 40.0,
                "expected_enrollment": 10,
                "enrollment_rate_per_month": 1.0,
                "data_source": "medical_records",
                "competing_study_impact_pct": 35.0,
                "seasonal_variation": False,
                "referral_network_available": False,
                "patient_database_size": 8000,
                "analyst": "Emily Rodriguez",
                "methodology_notes": "High competing study impact severely limits available patient pool.",
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "PPA-008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-108",
                "analysis_date": now - timedelta(days=35),
                "indication": "Moderate-to-Severe Atopic Dermatitis",
                "estimated_prevalence": 11000,
                "estimated_eligible": 900,
                "screen_failure_rate_pct": 22.0,
                "expected_enrollment": 50,
                "enrollment_rate_per_month": 5.0,
                "data_source": "medical_records",
                "competing_study_impact_pct": 5.0,
                "seasonal_variation": True,
                "referral_network_available": True,
                "patient_database_size": 18000,
                "analyst": "Marcus Thompson",
                "methodology_notes": "Stanford dermatology network provides excellent patient access.",
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "PPA-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-201",
                "analysis_date": now - timedelta(days=25),
                "indication": "Advanced Cutaneous Squamous Cell Carcinoma (CSCC)",
                "estimated_prevalence": 4100,
                "estimated_eligible": 220,
                "screen_failure_rate_pct": 28.0,
                "expected_enrollment": 40,
                "enrollment_rate_per_month": 4.0,
                "data_source": "tumor_registry",
                "competing_study_impact_pct": 12.0,
                "seasonal_variation": False,
                "referral_network_available": True,
                "patient_database_size": 7500,
                "analyst": "Dr. Alicia Foster",
                "methodology_notes": "Charite tumor registry analysis. Strong Berlin referral network.",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "PPA-010",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-202",
                "analysis_date": now - timedelta(days=18),
                "indication": "Wet Age-Related Macular Degeneration (wAMD)",
                "estimated_prevalence": 9200,
                "estimated_eligible": 680,
                "screen_failure_rate_pct": 22.0,
                "expected_enrollment": 55,
                "enrollment_rate_per_month": 5.5,
                "data_source": "medical_records",
                "competing_study_impact_pct": 4.0,
                "seasonal_variation": False,
                "referral_network_available": True,
                "patient_database_size": 15000,
                "analyst": "Emily Rodriguez",
                "methodology_notes": "Moorfields has the largest retinal patient database in Europe.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "PPA-011",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-203",
                "analysis_date": now - timedelta(days=12),
                "indication": "Moderate-to-Severe Atopic Dermatitis",
                "estimated_prevalence": 7500,
                "estimated_eligible": 500,
                "screen_failure_rate_pct": 30.0,
                "expected_enrollment": 35,
                "enrollment_rate_per_month": 3.5,
                "data_source": "medical_records",
                "competing_study_impact_pct": 10.0,
                "seasonal_variation": True,
                "referral_network_available": True,
                "patient_database_size": 10500,
                "analyst": "Marcus Thompson",
                "methodology_notes": "University of Tokyo dermatology department patient records.",
                "created_at": now - timedelta(days=14),
            },
            {
                "id": "PPA-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-109",
                "analysis_date": now - timedelta(days=8),
                "indication": "Advanced Cutaneous Squamous Cell Carcinoma (CSCC)",
                "estimated_prevalence": 6000,
                "estimated_eligible": 450,
                "screen_failure_rate_pct": 25.0,
                "expected_enrollment": 70,
                "enrollment_rate_per_month": 7.0,
                "data_source": "tumor_registry",
                "competing_study_impact_pct": 15.0,
                "seasonal_variation": False,
                "referral_network_available": True,
                "patient_database_size": 25000,
                "analyst": "Dr. Alicia Foster",
                "methodology_notes": "MD Anderson has the largest cancer patient database in the US.",
                "created_at": now - timedelta(days=10),
            },
        ]

        for pp in patient_pool_data:
            self._patient_pool_analyses[pp["id"]] = PatientPoolAnalysis(**pp)

        # --- 12 Capability Evaluations ---
        capability_data = [
            {
                "id": "CE-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "capability_area": CapabilityArea.IMAGING,
                "evaluation_date": now - timedelta(days=115),
                "score": 95.0,
                "meets_requirements": True,
                "gap_description": None,
                "remediation_plan": None,
                "remediation_timeline_weeks": None,
                "equipment_available": True,
                "staff_trained": True,
                "certification_current": True,
                "evaluator": "Technical Assessment Team",
                "notes": "OCT and fluorescein angiography equipment meets all protocol requirements.",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "CE-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "capability_area": CapabilityArea.PHARMACY,
                "evaluation_date": now - timedelta(days=115),
                "score": 90.0,
                "meets_requirements": True,
                "gap_description": None,
                "remediation_plan": None,
                "remediation_timeline_weeks": None,
                "equipment_available": True,
                "staff_trained": True,
                "certification_current": True,
                "evaluator": "Technical Assessment Team",
                "notes": "Dedicated research pharmacy with IMP storage capacity.",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "CE-003",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "capability_area": CapabilityArea.LABORATORY,
                "evaluation_date": now - timedelta(days=85),
                "score": 98.0,
                "meets_requirements": True,
                "gap_description": None,
                "remediation_plan": None,
                "remediation_timeline_weeks": None,
                "equipment_available": True,
                "staff_trained": True,
                "certification_current": True,
                "evaluator": "Lab Qualification Team",
                "notes": "CAP-accredited central lab. All biomarker assays validated.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "CE-004",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "capability_area": CapabilityArea.STAFF,
                "evaluation_date": now - timedelta(days=80),
                "score": 55.0,
                "meets_requirements": False,
                "gap_description": "Insufficient trained research coordinators for expected enrollment volume.",
                "remediation_plan": "Hire 2 additional research coordinators and complete protocol-specific training.",
                "remediation_timeline_weeks": 8,
                "equipment_available": True,
                "staff_trained": False,
                "certification_current": True,
                "evaluator": "Site Readiness Team",
                "notes": "Staff augmentation required before site can activate.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "CE-005",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "capability_area": CapabilityArea.REGULATORY,
                "evaluation_date": now - timedelta(days=70),
                "score": 88.0,
                "meets_requirements": True,
                "gap_description": None,
                "remediation_plan": None,
                "remediation_timeline_weeks": None,
                "equipment_available": True,
                "staff_trained": True,
                "certification_current": True,
                "evaluator": "Regulatory Affairs Team",
                "notes": "Experienced IRB liaison. Central IRB process well-established.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "CE-006",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "capability_area": CapabilityArea.IT_SYSTEMS,
                "evaluation_date": now - timedelta(days=65),
                "score": 72.0,
                "meets_requirements": False,
                "gap_description": "EDC system integration incomplete. No direct HL7 feed from EHR.",
                "remediation_plan": "Complete EDC-EHR integration and validate data transfer protocols.",
                "remediation_timeline_weeks": 6,
                "equipment_available": True,
                "staff_trained": True,
                "certification_current": True,
                "evaluator": "IT Assessment Team",
                "notes": "IT remediation in progress. Expected completion in 6 weeks.",
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "CE-007",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-107",
                "capability_area": CapabilityArea.FACILITIES,
                "evaluation_date": now - timedelta(days=55),
                "score": 45.0,
                "meets_requirements": False,
                "gap_description": "Inadequate dedicated research clinic space. Shared with general ophthalmology.",
                "remediation_plan": "Requires facility renovation to create dedicated research area.",
                "remediation_timeline_weeks": 16,
                "equipment_available": False,
                "staff_trained": False,
                "certification_current": True,
                "evaluator": "Site Readiness Team",
                "notes": "Major facility limitations. Renovation timeline exceeds acceptable activation window.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "CE-008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-108",
                "capability_area": CapabilityArea.PATIENT_ACCESS,
                "evaluation_date": now - timedelta(days=40),
                "score": 92.0,
                "meets_requirements": True,
                "gap_description": None,
                "remediation_plan": None,
                "remediation_timeline_weeks": None,
                "equipment_available": True,
                "staff_trained": True,
                "certification_current": True,
                "evaluator": "Patient Access Team",
                "notes": "Excellent patient recruitment infrastructure. Digital advertising platform in place.",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "CE-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-201",
                "capability_area": CapabilityArea.LABORATORY,
                "evaluation_date": now - timedelta(days=25),
                "score": 85.0,
                "meets_requirements": True,
                "gap_description": None,
                "remediation_plan": None,
                "remediation_timeline_weeks": None,
                "equipment_available": True,
                "staff_trained": True,
                "certification_current": True,
                "evaluator": "Lab Qualification Team",
                "notes": "EU-accredited laboratory. Biomarker assay validation complete.",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "CE-010",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-202",
                "capability_area": CapabilityArea.IMAGING,
                "evaluation_date": now - timedelta(days=18),
                "score": 97.0,
                "meets_requirements": True,
                "gap_description": None,
                "remediation_plan": None,
                "remediation_timeline_weeks": None,
                "equipment_available": True,
                "staff_trained": True,
                "certification_current": True,
                "evaluator": "Technical Assessment Team",
                "notes": "State-of-the-art retinal imaging suite. Exceeds protocol requirements.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "CE-011",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-203",
                "capability_area": CapabilityArea.REGULATORY,
                "evaluation_date": now - timedelta(days=10),
                "score": 65.0,
                "meets_requirements": False,
                "gap_description": "PMDA regulatory submission process requires local CRO support.",
                "remediation_plan": "Engage local CRO for PMDA submission support and translation services.",
                "remediation_timeline_weeks": 10,
                "equipment_available": True,
                "staff_trained": True,
                "certification_current": True,
                "evaluator": "Regulatory Affairs Team",
                "notes": "Japan regulatory pathway requires specialized local support.",
                "created_at": now - timedelta(days=12),
            },
            {
                "id": "CE-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-109",
                "capability_area": CapabilityArea.PHARMACY,
                "evaluation_date": now - timedelta(days=5),
                "score": 94.0,
                "meets_requirements": True,
                "gap_description": None,
                "remediation_plan": None,
                "remediation_timeline_weeks": None,
                "equipment_available": True,
                "staff_trained": True,
                "certification_current": True,
                "evaluator": "Technical Assessment Team",
                "notes": "MD Anderson research pharmacy is fully equipped for IO drug management.",
                "created_at": now - timedelta(days=8),
            },
        ]

        for ce in capability_data:
            self._capability_evaluations[ce["id"]] = CapabilityEvaluation(**ce)

        # --- 12 Feasibility Surveys ---
        surveys_data = [
            {
                "id": "FS-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "survey_name": "EYLEA Phase III wAMD Feasibility Questionnaire",
                "sent_date": now - timedelta(days=140),
                "response_date": now - timedelta(days=132),
                "respondent": "Dr. Robert Chen",
                "total_questions": 45,
                "answered_questions": 45,
                "interest_level": "high",
                "estimated_enrollment": 45,
                "timeline_acceptable": True,
                "budget_acceptable": True,
                "additional_comments": "Very interested. Strong patient base for wAMD studies.",
                "follow_up_required": False,
                "created_at": now - timedelta(days=145),
            },
            {
                "id": "FS-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "survey_name": "EYLEA Phase III wAMD Feasibility Questionnaire",
                "sent_date": now - timedelta(days=140),
                "response_date": now - timedelta(days=128),
                "respondent": "Dr. Angela Vasquez",
                "total_questions": 45,
                "answered_questions": 42,
                "interest_level": "high",
                "estimated_enrollment": 30,
                "timeline_acceptable": True,
                "budget_acceptable": True,
                "additional_comments": "Interested but competing studies may limit enrollment capacity.",
                "follow_up_required": False,
                "created_at": now - timedelta(days=145),
            },
            {
                "id": "FS-003",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "survey_name": "DUPIXENT AD Phase III Feasibility Survey",
                "sent_date": now - timedelta(days=100),
                "response_date": now - timedelta(days=93),
                "respondent": "Dr. Michael Takahashi",
                "total_questions": 50,
                "answered_questions": 50,
                "interest_level": "very_high",
                "estimated_enrollment": 65,
                "timeline_acceptable": True,
                "budget_acceptable": True,
                "additional_comments": "Highly enthusiastic. Large AD patient cohort available.",
                "follow_up_required": False,
                "created_at": now - timedelta(days=105),
            },
            {
                "id": "FS-004",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "survey_name": "DUPIXENT AD Phase III Feasibility Survey",
                "sent_date": now - timedelta(days=100),
                "response_date": now - timedelta(days=88),
                "respondent": "Dr. Patricia Bowman",
                "total_questions": 50,
                "answered_questions": 38,
                "interest_level": "moderate",
                "estimated_enrollment": 15,
                "timeline_acceptable": False,
                "budget_acceptable": True,
                "additional_comments": "Timeline concerns regarding staff training. May need extension.",
                "follow_up_required": True,
                "created_at": now - timedelta(days=105),
            },
            {
                "id": "FS-005",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "survey_name": "LIBTAYO CSCC Phase III Site Feasibility",
                "sent_date": now - timedelta(days=80),
                "response_date": now - timedelta(days=72),
                "respondent": "Dr. James Okafor",
                "total_questions": 48,
                "answered_questions": 48,
                "interest_level": "high",
                "estimated_enrollment": 35,
                "timeline_acceptable": True,
                "budget_acceptable": True,
                "additional_comments": "Duke IO program well-positioned for this study.",
                "follow_up_required": False,
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "FS-006",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "survey_name": "LIBTAYO CSCC Phase III Site Feasibility",
                "sent_date": now - timedelta(days=80),
                "response_date": now - timedelta(days=70),
                "respondent": "Dr. Lisa Fernandez",
                "total_questions": 48,
                "answered_questions": 44,
                "interest_level": "moderate",
                "estimated_enrollment": 22,
                "timeline_acceptable": True,
                "budget_acceptable": False,
                "additional_comments": "Budget concerns regarding imaging costs. Need renegotiation.",
                "follow_up_required": True,
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "FS-007",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-107",
                "survey_name": "EYLEA Phase III wAMD Feasibility Questionnaire",
                "sent_date": now - timedelta(days=70),
                "response_date": now - timedelta(days=55),
                "respondent": "Dr. William Patel",
                "total_questions": 45,
                "answered_questions": 30,
                "interest_level": "low",
                "estimated_enrollment": 8,
                "timeline_acceptable": False,
                "budget_acceptable": False,
                "additional_comments": "Significant resource constraints. Unable to commit to timeline.",
                "follow_up_required": False,
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "FS-008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-108",
                "survey_name": "DUPIXENT AD Phase III Feasibility Survey",
                "sent_date": now - timedelta(days=50),
                "response_date": now - timedelta(days=43),
                "respondent": "Dr. Karen Nguyen",
                "total_questions": 50,
                "answered_questions": 50,
                "interest_level": "very_high",
                "estimated_enrollment": 55,
                "timeline_acceptable": True,
                "budget_acceptable": True,
                "additional_comments": "Stanford fully committed. Dedicated research team ready.",
                "follow_up_required": False,
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "FS-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-201",
                "survey_name": "LIBTAYO CSCC Phase III International Feasibility",
                "sent_date": now - timedelta(days=35),
                "response_date": now - timedelta(days=28),
                "respondent": "Prof. Dr. Hans Weber",
                "total_questions": 52,
                "answered_questions": 48,
                "interest_level": "high",
                "estimated_enrollment": 40,
                "timeline_acceptable": True,
                "budget_acceptable": True,
                "additional_comments": "Strong interest from Charite oncology department.",
                "follow_up_required": True,
                "created_at": now - timedelta(days=38),
            },
            {
                "id": "FS-010",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-202",
                "survey_name": "EYLEA Phase III wAMD International Feasibility",
                "sent_date": now - timedelta(days=22),
                "response_date": None,
                "respondent": None,
                "total_questions": 45,
                "answered_questions": 0,
                "interest_level": None,
                "estimated_enrollment": None,
                "timeline_acceptable": None,
                "budget_acceptable": None,
                "additional_comments": None,
                "follow_up_required": True,
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "FS-011",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-203",
                "survey_name": "DUPIXENT AD Phase III APAC Feasibility",
                "sent_date": now - timedelta(days=18),
                "response_date": None,
                "respondent": None,
                "total_questions": 50,
                "answered_questions": 0,
                "interest_level": None,
                "estimated_enrollment": None,
                "timeline_acceptable": None,
                "budget_acceptable": None,
                "additional_comments": None,
                "follow_up_required": True,
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "FS-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-109",
                "survey_name": "LIBTAYO CSCC Phase III Site Feasibility",
                "sent_date": now - timedelta(days=12),
                "response_date": now - timedelta(days=8),
                "respondent": "Dr. Richard Chang",
                "total_questions": 48,
                "answered_questions": 46,
                "interest_level": "very_high",
                "estimated_enrollment": 70,
                "timeline_acceptable": True,
                "budget_acceptable": True,
                "additional_comments": "MD Anderson fully capable. Budget discussion in progress.",
                "follow_up_required": True,
                "created_at": now - timedelta(days=14),
            },
        ]

        for fs in surveys_data:
            self._feasibility_surveys[fs["id"]] = FeasibilitySurvey(**fs)

    # ------------------------------------------------------------------
    # Site Assessments
    # ------------------------------------------------------------------

    def list_site_assessments(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[SiteAssessment]:
        """List site assessments with optional trial_id filter."""
        with self._lock:
            result = list(self._site_assessments.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]

        return sorted(result, key=lambda a: a.created_at, reverse=True)

    def get_site_assessment(self, assessment_id: str) -> SiteAssessment | None:
        """Get a single site assessment by ID."""
        with self._lock:
            return self._site_assessments.get(assessment_id)

    def create_site_assessment(self, payload: SiteAssessmentCreate) -> SiteAssessment:
        """Create a new site assessment."""
        now = datetime.now(timezone.utc)
        assessment_id = f"SA-{uuid4().hex[:8].upper()}"
        assessment = SiteAssessment(
            id=assessment_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            site_name=payload.site_name,
            country=payload.country,
            region=payload.region,
            assessment_date=now,
            status=AssessmentStatus.PLANNED,
            result=FeasibilityResult.PENDING,
            overall_score=0.0,
            enrollment_potential=payload.enrollment_potential,
            competitive_trials=0,
            estimated_activation_weeks=0,
            irb_type=None,
            previous_trial_experience=0,
            therapeutic_area_experience=False,
            assessor=payload.assessor,
            comments=None,
            created_at=now,
        )
        with self._lock:
            self._site_assessments[assessment_id] = assessment
        logger.info("Created site assessment %s for site %s", assessment_id, payload.site_id)
        return assessment

    def update_site_assessment(
        self, assessment_id: str, payload: SiteAssessmentUpdate
    ) -> SiteAssessment | None:
        """Update an existing site assessment."""
        with self._lock:
            existing = self._site_assessments.get(assessment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = SiteAssessment(**data)
            self._site_assessments[assessment_id] = updated
        return updated

    def delete_site_assessment(self, assessment_id: str) -> bool:
        """Delete a site assessment. Returns True if deleted."""
        with self._lock:
            if assessment_id in self._site_assessments:
                del self._site_assessments[assessment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Investigator Qualifications
    # ------------------------------------------------------------------

    def list_investigator_qualifications(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[InvestigatorQualification]:
        """List investigator qualifications with optional trial_id filter."""
        with self._lock:
            result = list(self._investigator_qualifications.values())

        if trial_id is not None:
            result = [iq for iq in result if iq.trial_id == trial_id]

        return sorted(result, key=lambda iq: iq.created_at, reverse=True)

    def get_investigator_qualification(
        self, qualification_id: str
    ) -> InvestigatorQualification | None:
        """Get a single investigator qualification by ID."""
        with self._lock:
            return self._investigator_qualifications.get(qualification_id)

    def create_investigator_qualification(
        self, payload: InvestigatorQualificationCreate
    ) -> InvestigatorQualification:
        """Create a new investigator qualification."""
        now = datetime.now(timezone.utc)
        qual_id = f"IQ-{uuid4().hex[:8].upper()}"
        qualification = InvestigatorQualification(
            id=qual_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            investigator_name=payload.investigator_name,
            medical_license_number=None,
            specialty=payload.specialty,
            years_experience=payload.years_experience,
            gcp_certified=payload.gcp_certified,
            gcp_expiry_date=None,
            cv_on_file=False,
            financial_disclosure_complete=False,
            previous_studies_count=0,
            enrollment_track_record=None,
            qualification_status=QualificationStatus.PENDING_REVIEW,
            debarment_checked=False,
            sanctions_checked=False,
            reviewed_by=None,
            review_date=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._investigator_qualifications[qual_id] = qualification
        logger.info(
            "Created investigator qualification %s for %s",
            qual_id,
            payload.investigator_name,
        )
        return qualification

    def update_investigator_qualification(
        self, qualification_id: str, payload: InvestigatorQualificationUpdate
    ) -> InvestigatorQualification | None:
        """Update an existing investigator qualification."""
        with self._lock:
            existing = self._investigator_qualifications.get(qualification_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = InvestigatorQualification(**data)
            self._investigator_qualifications[qualification_id] = updated
        return updated

    def delete_investigator_qualification(self, qualification_id: str) -> bool:
        """Delete an investigator qualification. Returns True if deleted."""
        with self._lock:
            if qualification_id in self._investigator_qualifications:
                del self._investigator_qualifications[qualification_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Patient Pool Analyses
    # ------------------------------------------------------------------

    def list_patient_pool_analyses(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[PatientPoolAnalysis]:
        """List patient pool analyses with optional trial_id filter."""
        with self._lock:
            result = list(self._patient_pool_analyses.values())

        if trial_id is not None:
            result = [pp for pp in result if pp.trial_id == trial_id]

        return sorted(result, key=lambda pp: pp.created_at, reverse=True)

    def get_patient_pool_analysis(self, analysis_id: str) -> PatientPoolAnalysis | None:
        """Get a single patient pool analysis by ID."""
        with self._lock:
            return self._patient_pool_analyses.get(analysis_id)

    def create_patient_pool_analysis(
        self, payload: PatientPoolAnalysisCreate
    ) -> PatientPoolAnalysis:
        """Create a new patient pool analysis."""
        now = datetime.now(timezone.utc)
        analysis_id = f"PPA-{uuid4().hex[:8].upper()}"
        analysis = PatientPoolAnalysis(
            id=analysis_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            analysis_date=now,
            indication=payload.indication,
            estimated_prevalence=payload.estimated_prevalence,
            estimated_eligible=payload.estimated_eligible,
            screen_failure_rate_pct=30.0,
            expected_enrollment=0,
            enrollment_rate_per_month=0.0,
            data_source="medical_records",
            competing_study_impact_pct=0.0,
            seasonal_variation=False,
            referral_network_available=False,
            patient_database_size=0,
            analyst=payload.analyst,
            methodology_notes=None,
            created_at=now,
        )
        with self._lock:
            self._patient_pool_analyses[analysis_id] = analysis
        logger.info("Created patient pool analysis %s for site %s", analysis_id, payload.site_id)
        return analysis

    def update_patient_pool_analysis(
        self, analysis_id: str, payload: PatientPoolAnalysisUpdate
    ) -> PatientPoolAnalysis | None:
        """Update an existing patient pool analysis."""
        with self._lock:
            existing = self._patient_pool_analyses.get(analysis_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = PatientPoolAnalysis(**data)
            self._patient_pool_analyses[analysis_id] = updated
        return updated

    def delete_patient_pool_analysis(self, analysis_id: str) -> bool:
        """Delete a patient pool analysis. Returns True if deleted."""
        with self._lock:
            if analysis_id in self._patient_pool_analyses:
                del self._patient_pool_analyses[analysis_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Capability Evaluations
    # ------------------------------------------------------------------

    def list_capability_evaluations(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[CapabilityEvaluation]:
        """List capability evaluations with optional trial_id filter."""
        with self._lock:
            result = list(self._capability_evaluations.values())

        if trial_id is not None:
            result = [ce for ce in result if ce.trial_id == trial_id]

        return sorted(result, key=lambda ce: ce.created_at, reverse=True)

    def get_capability_evaluation(self, evaluation_id: str) -> CapabilityEvaluation | None:
        """Get a single capability evaluation by ID."""
        with self._lock:
            return self._capability_evaluations.get(evaluation_id)

    def create_capability_evaluation(
        self, payload: CapabilityEvaluationCreate
    ) -> CapabilityEvaluation:
        """Create a new capability evaluation."""
        now = datetime.now(timezone.utc)
        eval_id = f"CE-{uuid4().hex[:8].upper()}"
        evaluation = CapabilityEvaluation(
            id=eval_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            capability_area=payload.capability_area,
            evaluation_date=now,
            score=payload.score,
            meets_requirements=payload.meets_requirements,
            gap_description=None,
            remediation_plan=None,
            remediation_timeline_weeks=None,
            equipment_available=True,
            staff_trained=True,
            certification_current=True,
            evaluator=payload.evaluator,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._capability_evaluations[eval_id] = evaluation
        logger.info(
            "Created capability evaluation %s for site %s area %s",
            eval_id,
            payload.site_id,
            payload.capability_area.value,
        )
        return evaluation

    def update_capability_evaluation(
        self, evaluation_id: str, payload: CapabilityEvaluationUpdate
    ) -> CapabilityEvaluation | None:
        """Update an existing capability evaluation."""
        with self._lock:
            existing = self._capability_evaluations.get(evaluation_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CapabilityEvaluation(**data)
            self._capability_evaluations[evaluation_id] = updated
        return updated

    def delete_capability_evaluation(self, evaluation_id: str) -> bool:
        """Delete a capability evaluation. Returns True if deleted."""
        with self._lock:
            if evaluation_id in self._capability_evaluations:
                del self._capability_evaluations[evaluation_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Feasibility Surveys
    # ------------------------------------------------------------------

    def list_feasibility_surveys(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[FeasibilitySurvey]:
        """List feasibility surveys with optional trial_id filter."""
        with self._lock:
            result = list(self._feasibility_surveys.values())

        if trial_id is not None:
            result = [fs for fs in result if fs.trial_id == trial_id]

        return sorted(result, key=lambda fs: fs.created_at, reverse=True)

    def get_feasibility_survey(self, survey_id: str) -> FeasibilitySurvey | None:
        """Get a single feasibility survey by ID."""
        with self._lock:
            return self._feasibility_surveys.get(survey_id)

    def create_feasibility_survey(self, payload: FeasibilitySurveyCreate) -> FeasibilitySurvey:
        """Create a new feasibility survey."""
        now = datetime.now(timezone.utc)
        survey_id = f"FS-{uuid4().hex[:8].upper()}"
        survey = FeasibilitySurvey(
            id=survey_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            survey_name=payload.survey_name,
            sent_date=now,
            response_date=None,
            respondent=None,
            total_questions=payload.total_questions,
            answered_questions=0,
            interest_level=None,
            estimated_enrollment=None,
            timeline_acceptable=None,
            budget_acceptable=None,
            additional_comments=None,
            follow_up_required=False,
            created_at=now,
        )
        with self._lock:
            self._feasibility_surveys[survey_id] = survey
        logger.info("Created feasibility survey %s for site %s", survey_id, payload.site_id)
        return survey

    def update_feasibility_survey(
        self, survey_id: str, payload: FeasibilitySurveyUpdate
    ) -> FeasibilitySurvey | None:
        """Update an existing feasibility survey."""
        with self._lock:
            existing = self._feasibility_surveys.get(survey_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = FeasibilitySurvey(**data)
            self._feasibility_surveys[survey_id] = updated
        return updated

    def delete_feasibility_survey(self, survey_id: str) -> bool:
        """Delete a feasibility survey. Returns True if deleted."""
        with self._lock:
            if survey_id in self._feasibility_surveys:
                del self._feasibility_surveys[survey_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> SiteFeasibilityMetrics:
        """Compute aggregated site feasibility operational metrics."""
        with self._lock:
            assessments = list(self._site_assessments.values())
            investigators = list(self._investigator_qualifications.values())
            pool_analyses = list(self._patient_pool_analyses.values())
            evaluations = list(self._capability_evaluations.values())
            surveys = list(self._feasibility_surveys.values())

        # Assessments by status
        assessments_by_status: dict[str, int] = {}
        for a in assessments:
            key = a.status.value
            assessments_by_status[key] = assessments_by_status.get(key, 0) + 1

        # Assessments by result
        assessments_by_result: dict[str, int] = {}
        for a in assessments:
            key = a.result.value
            assessments_by_result[key] = assessments_by_result.get(key, 0) + 1

        # Average feasibility score (only completed assessments with score > 0)
        scored_assessments = [a for a in assessments if a.overall_score > 0]
        avg_score = (
            round(sum(a.overall_score for a in scored_assessments) / len(scored_assessments), 1)
            if scored_assessments
            else 0.0
        )

        # Investigators by status
        investigators_by_status: dict[str, int] = {}
        for iq in investigators:
            key = iq.qualification_status.value
            investigators_by_status[key] = investigators_by_status.get(key, 0) + 1

        qualified_investigators = sum(
            1
            for iq in investigators
            if iq.qualification_status == QualificationStatus.QUALIFIED
        )

        # Patient pool totals
        total_estimated_eligible = sum(pp.estimated_eligible for pp in pool_analyses)

        # Evaluations by area
        evaluations_by_area: dict[str, int] = {}
        for ce in evaluations:
            key = ce.capability_area.value
            evaluations_by_area[key] = evaluations_by_area.get(key, 0) + 1

        capabilities_meeting = sum(1 for ce in evaluations if ce.meets_requirements)

        # Surveys responded
        surveys_responded = sum(1 for fs in surveys if fs.response_date is not None)

        return SiteFeasibilityMetrics(
            total_assessments=len(assessments),
            assessments_by_status=assessments_by_status,
            assessments_by_result=assessments_by_result,
            avg_feasibility_score=avg_score,
            total_investigators=len(investigators),
            investigators_by_status=investigators_by_status,
            qualified_investigators=qualified_investigators,
            total_pool_analyses=len(pool_analyses),
            total_estimated_eligible=total_estimated_eligible,
            total_evaluations=len(evaluations),
            evaluations_by_area=evaluations_by_area,
            capabilities_meeting_requirements=capabilities_meeting,
            total_surveys=len(surveys),
            surveys_responded=surveys_responded,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: SiteFeasibilityService | None = None
_instance_lock = threading.Lock()


def get_site_feasibility_service() -> SiteFeasibilityService:
    """Return the singleton SiteFeasibilityService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = SiteFeasibilityService()
    return _instance


def reset_site_feasibility_service() -> SiteFeasibilityService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = SiteFeasibilityService()
    return _instance
