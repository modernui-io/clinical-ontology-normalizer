"""Patient Insurance Verification (PIV-VER) Service.

Manages patient insurance verification operations: eligibility checks,
pre-authorization requests, coverage determinations, and reimbursement
tracking with metrics across clinical trials.

Usage:
    from app.services.patient_insurance_verification_service import (
        get_patient_insurance_verification_service,
    )

    svc = get_patient_insurance_verification_service()
    checks = svc.list_eligibility_checks()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.patient_insurance_verification import (
    CoverageDetermination,
    CoverageDeterminationCreate,
    CoverageDeterminationUpdate,
    CoverageType,
    DenialReason,
    EligibilityCheck,
    EligibilityCheckCreate,
    EligibilityCheckUpdate,
    EligibilityStatus,
    PatientInsuranceVerificationMetrics,
    PreAuthorizationRequest,
    PreAuthorizationRequestCreate,
    PreAuthorizationRequestUpdate,
    PreAuthStatus,
    ReimbursementStatus,
    ReimbursementTracking,
    ReimbursementTrackingCreate,
    ReimbursementTrackingUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class PatientInsuranceVerificationService:
    """In-memory Patient Insurance Verification engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._eligibility_checks: dict[str, EligibilityCheck] = {}
        self._pre_authorization_requests: dict[str, PreAuthorizationRequest] = {}
        self._coverage_determinations: dict[str, CoverageDetermination] = {}
        self._reimbursement_trackings: dict[str, ReimbursementTracking] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic insurance verification data across 3 trials."""
        now = datetime.now(timezone.utc)

        # --- 12 Eligibility Checks (4 per trial) ---
        eligibility_data = [
            # EYLEA trial
            {
                "id": "ELC-00000001",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1001",
                "site_id": "SITE-101",
                "eligibility_status": EligibilityStatus.ELIGIBLE,
                "coverage_type": CoverageType.PRIVATE,
                "insurance_provider": "Aetna",
                "policy_number": "AET-990012345",
                "group_number": "GRP-8800",
                "coverage_start_date": now - timedelta(days=365),
                "coverage_end_date": now + timedelta(days=180),
                "verification_date": now - timedelta(days=90),
                "verified_by": "Sarah Mitchell",
                "verification_method": "Electronic eligibility inquiry (270/271)",
                "copay_amount": 30.0,
                "deductible_remaining": 500.0,
                "notes": "Active coverage confirmed. Specialty drug benefits verified.",
                "created_at": now - timedelta(days=95),
            },
            {
                "id": "ELC-00000002",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1002",
                "site_id": "SITE-101",
                "eligibility_status": EligibilityStatus.ELIGIBLE,
                "coverage_type": CoverageType.MEDICARE,
                "insurance_provider": "Medicare Part B",
                "policy_number": "1EG4-TE5-MK72",
                "group_number": None,
                "coverage_start_date": now - timedelta(days=730),
                "coverage_end_date": None,
                "verification_date": now - timedelta(days=60),
                "verified_by": "Sarah Mitchell",
                "verification_method": "CMS HETS inquiry",
                "copay_amount": 0.0,
                "deductible_remaining": 226.0,
                "notes": "Medicare Part B active. 80/20 coinsurance after deductible.",
                "created_at": now - timedelta(days=65),
            },
            {
                "id": "ELC-00000003",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1003",
                "site_id": "SITE-102",
                "eligibility_status": EligibilityStatus.PENDING_VERIFICATION,
                "coverage_type": CoverageType.PRIVATE,
                "insurance_provider": "UnitedHealthcare",
                "policy_number": None,
                "group_number": None,
                "coverage_start_date": None,
                "coverage_end_date": None,
                "verification_date": now - timedelta(days=5),
                "verified_by": "David Park",
                "verification_method": "Phone verification pending",
                "copay_amount": 0.0,
                "deductible_remaining": 0.0,
                "notes": "Awaiting callback from UHC provider services.",
                "created_at": now - timedelta(days=7),
            },
            {
                "id": "ELC-00000004",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1004",
                "site_id": "SITE-102",
                "eligibility_status": EligibilityStatus.EXPIRED,
                "coverage_type": CoverageType.PRIVATE,
                "insurance_provider": "Cigna",
                "policy_number": "CIG-55001234",
                "group_number": "GRP-4400",
                "coverage_start_date": now - timedelta(days=730),
                "coverage_end_date": now - timedelta(days=30),
                "verification_date": now - timedelta(days=45),
                "verified_by": "David Park",
                "verification_method": "Electronic eligibility inquiry (270/271)",
                "copay_amount": 50.0,
                "deductible_remaining": 1200.0,
                "notes": "Coverage expired. Patient transitioning to new plan.",
                "created_at": now - timedelta(days=50),
            },
            # DUPIXENT trial
            {
                "id": "ELC-00000005",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2001",
                "site_id": "SITE-103",
                "eligibility_status": EligibilityStatus.ELIGIBLE,
                "coverage_type": CoverageType.PRIVATE,
                "insurance_provider": "Blue Cross Blue Shield",
                "policy_number": "BCBS-77008899",
                "group_number": "GRP-1122",
                "coverage_start_date": now - timedelta(days=200),
                "coverage_end_date": now + timedelta(days=165),
                "verification_date": now - timedelta(days=30),
                "verified_by": "Jennifer Lee",
                "verification_method": "Real-time eligibility portal",
                "copay_amount": 40.0,
                "deductible_remaining": 750.0,
                "notes": "Specialty pharmacy benefits confirmed. Step therapy requirement met.",
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "ELC-00000006",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2002",
                "site_id": "SITE-103",
                "eligibility_status": EligibilityStatus.CONDITIONAL,
                "coverage_type": CoverageType.MEDICAID,
                "insurance_provider": "NY State Medicaid",
                "policy_number": "NYM-33445566",
                "group_number": None,
                "coverage_start_date": now - timedelta(days=400),
                "coverage_end_date": now + timedelta(days=60),
                "verification_date": now - timedelta(days=20),
                "verified_by": "Jennifer Lee",
                "verification_method": "State Medicaid portal inquiry",
                "copay_amount": 0.0,
                "deductible_remaining": 0.0,
                "notes": "Eligible pending prior authorization for biologic therapy.",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "ELC-00000007",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2003",
                "site_id": "SITE-104",
                "eligibility_status": EligibilityStatus.INELIGIBLE,
                "coverage_type": CoverageType.UNINSURED,
                "insurance_provider": "N/A",
                "policy_number": None,
                "group_number": None,
                "coverage_start_date": None,
                "coverage_end_date": None,
                "verification_date": now - timedelta(days=15),
                "verified_by": "David Park",
                "verification_method": "Patient self-report confirmed",
                "copay_amount": 0.0,
                "deductible_remaining": 0.0,
                "notes": "Patient uninsured. Referred to patient assistance program.",
                "created_at": now - timedelta(days=18),
            },
            {
                "id": "ELC-00000008",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2004",
                "site_id": "SITE-104",
                "eligibility_status": EligibilityStatus.ELIGIBLE,
                "coverage_type": CoverageType.TRICARE,
                "insurance_provider": "TRICARE Prime",
                "policy_number": "TC-88776655",
                "group_number": None,
                "coverage_start_date": now - timedelta(days=500),
                "coverage_end_date": now + timedelta(days=230),
                "verification_date": now - timedelta(days=10),
                "verified_by": "David Park",
                "verification_method": "TRICARE online portal verification",
                "copay_amount": 15.0,
                "deductible_remaining": 150.0,
                "notes": "Active duty dependent. TRICARE Prime coverage active.",
                "created_at": now - timedelta(days=12),
            },
            # LIBTAYO trial
            {
                "id": "ELC-00000009",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3001",
                "site_id": "SITE-105",
                "eligibility_status": EligibilityStatus.ELIGIBLE,
                "coverage_type": CoverageType.MEDICARE,
                "insurance_provider": "Medicare Advantage (Humana)",
                "policy_number": "HUM-MA-44556677",
                "group_number": None,
                "coverage_start_date": now - timedelta(days=300),
                "coverage_end_date": now + timedelta(days=65),
                "verification_date": now - timedelta(days=25),
                "verified_by": "Jennifer Lee",
                "verification_method": "Humana provider portal",
                "copay_amount": 20.0,
                "deductible_remaining": 0.0,
                "notes": "Medicare Advantage plan. Oncology benefits verified.",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "ELC-00000010",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3002",
                "site_id": "SITE-105",
                "eligibility_status": EligibilityStatus.ELIGIBLE,
                "coverage_type": CoverageType.VA,
                "insurance_provider": "Veterans Affairs",
                "policy_number": "VA-11223344",
                "group_number": None,
                "coverage_start_date": now - timedelta(days=1000),
                "coverage_end_date": None,
                "verification_date": now - timedelta(days=14),
                "verified_by": "Jennifer Lee",
                "verification_method": "VA eligibility system",
                "copay_amount": 0.0,
                "deductible_remaining": 0.0,
                "notes": "Service-connected disability. Full VA benefits.",
                "created_at": now - timedelta(days=16),
            },
            {
                "id": "ELC-00000011",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3003",
                "site_id": "SITE-106",
                "eligibility_status": EligibilityStatus.UNKNOWN,
                "coverage_type": CoverageType.PRIVATE,
                "insurance_provider": "Anthem",
                "policy_number": None,
                "group_number": None,
                "coverage_start_date": None,
                "coverage_end_date": None,
                "verification_date": now - timedelta(days=3),
                "verified_by": "Sarah Mitchell",
                "verification_method": "Pending provider callback",
                "copay_amount": 0.0,
                "deductible_remaining": 0.0,
                "notes": "Unable to verify. Patient provided incorrect member ID.",
                "created_at": now - timedelta(days=4),
            },
            {
                "id": "ELC-00000012",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3004",
                "site_id": "SITE-106",
                "eligibility_status": EligibilityStatus.ELIGIBLE,
                "coverage_type": CoverageType.PRIVATE,
                "insurance_provider": "Kaiser Permanente",
                "policy_number": "KP-99887766",
                "group_number": "GRP-5500",
                "coverage_start_date": now - timedelta(days=180),
                "coverage_end_date": now + timedelta(days=185),
                "verification_date": now - timedelta(days=7),
                "verified_by": "Sarah Mitchell",
                "verification_method": "Electronic eligibility inquiry (270/271)",
                "copay_amount": 25.0,
                "deductible_remaining": 300.0,
                "notes": "HMO plan. In-network oncology center confirmed.",
                "created_at": now - timedelta(days=8),
            },
        ]

        for e in eligibility_data:
            self._eligibility_checks[e["id"]] = EligibilityCheck(**e)

        # --- 12 Pre-Authorization Requests (4 per trial) ---
        pre_auth_data = [
            # EYLEA trial
            {
                "id": "PAR-00000001",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1001",
                "site_id": "SITE-101",
                "pre_auth_status": PreAuthStatus.APPROVED,
                "procedure_code": "J0178",
                "procedure_description": "Aflibercept intravitreal injection",
                "requesting_provider": "Dr. James Wilson",
                "insurance_provider": "Aetna",
                "request_date": now - timedelta(days=85),
                "decision_date": now - timedelta(days=78),
                "authorization_number": "AUTH-AET-001234",
                "approved_units": 12,
                "expiration_date": now + timedelta(days=90),
                "denial_reason": None,
                "appeal_deadline": None,
                "notes": "Approved for 12 monthly injections.",
                "created_at": now - timedelta(days=88),
            },
            {
                "id": "PAR-00000002",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1002",
                "site_id": "SITE-101",
                "pre_auth_status": PreAuthStatus.APPROVED,
                "procedure_code": "J0178",
                "procedure_description": "Aflibercept intravitreal injection",
                "requesting_provider": "Dr. James Wilson",
                "insurance_provider": "Medicare Part B",
                "request_date": now - timedelta(days=55),
                "decision_date": now - timedelta(days=50),
                "authorization_number": "AUTH-MED-005678",
                "approved_units": 6,
                "expiration_date": now + timedelta(days=120),
                "denial_reason": None,
                "appeal_deadline": None,
                "notes": "Medicare prior auth approved. ABN on file.",
                "created_at": now - timedelta(days=58),
            },
            {
                "id": "PAR-00000003",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1003",
                "site_id": "SITE-102",
                "pre_auth_status": PreAuthStatus.PENDING_REVIEW,
                "procedure_code": "J0178",
                "procedure_description": "Aflibercept intravitreal injection",
                "requesting_provider": "Dr. Emily Chen",
                "insurance_provider": "UnitedHealthcare",
                "request_date": now - timedelta(days=5),
                "decision_date": None,
                "authorization_number": None,
                "approved_units": 0,
                "expiration_date": None,
                "denial_reason": None,
                "appeal_deadline": None,
                "notes": "Submitted to UHC. Expected turnaround 5-7 business days.",
                "created_at": now - timedelta(days=6),
            },
            {
                "id": "PAR-00000004",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1004",
                "site_id": "SITE-102",
                "pre_auth_status": PreAuthStatus.DENIED,
                "procedure_code": "J0178",
                "procedure_description": "Aflibercept intravitreal injection",
                "requesting_provider": "Dr. Emily Chen",
                "insurance_provider": "Cigna",
                "request_date": now - timedelta(days=40),
                "decision_date": now - timedelta(days=33),
                "authorization_number": None,
                "approved_units": 0,
                "expiration_date": None,
                "denial_reason": DenialReason.COVERAGE_LAPSED,
                "appeal_deadline": now - timedelta(days=3),
                "notes": "Denied due to lapsed coverage. Patient notified.",
                "created_at": now - timedelta(days=42),
            },
            # DUPIXENT trial
            {
                "id": "PAR-00000005",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2001",
                "site_id": "SITE-103",
                "pre_auth_status": PreAuthStatus.APPROVED,
                "procedure_code": "J0593",
                "procedure_description": "Dupilumab subcutaneous injection",
                "requesting_provider": "Dr. Maria Santos",
                "insurance_provider": "Blue Cross Blue Shield",
                "request_date": now - timedelta(days=28),
                "decision_date": now - timedelta(days=21),
                "authorization_number": "AUTH-BCBS-009876",
                "approved_units": 24,
                "expiration_date": now + timedelta(days=150),
                "denial_reason": None,
                "appeal_deadline": None,
                "notes": "Approved after step therapy documentation submitted.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "PAR-00000006",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2002",
                "site_id": "SITE-103",
                "pre_auth_status": PreAuthStatus.REQUESTED,
                "procedure_code": "J0593",
                "procedure_description": "Dupilumab subcutaneous injection",
                "requesting_provider": "Dr. Maria Santos",
                "insurance_provider": "NY State Medicaid",
                "request_date": now - timedelta(days=3),
                "decision_date": None,
                "authorization_number": None,
                "approved_units": 0,
                "expiration_date": None,
                "denial_reason": None,
                "appeal_deadline": None,
                "notes": "Medicaid prior auth submitted. Requires clinical documentation.",
                "created_at": now - timedelta(days=4),
            },
            {
                "id": "PAR-00000007",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2003",
                "site_id": "SITE-104",
                "pre_auth_status": PreAuthStatus.DENIED,
                "procedure_code": "J0593",
                "procedure_description": "Dupilumab subcutaneous injection",
                "requesting_provider": "Dr. Robert Kim",
                "insurance_provider": "N/A",
                "request_date": now - timedelta(days=14),
                "decision_date": now - timedelta(days=14),
                "authorization_number": None,
                "approved_units": 0,
                "expiration_date": None,
                "denial_reason": DenialReason.OTHER,
                "appeal_deadline": None,
                "notes": "Patient uninsured. N/A for pre-auth. Sponsor to cover.",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "PAR-00000008",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2004",
                "site_id": "SITE-104",
                "pre_auth_status": PreAuthStatus.PARTIALLY_APPROVED,
                "procedure_code": "J0593",
                "procedure_description": "Dupilumab subcutaneous injection",
                "requesting_provider": "Dr. Robert Kim",
                "insurance_provider": "TRICARE Prime",
                "request_date": now - timedelta(days=10),
                "decision_date": now - timedelta(days=7),
                "authorization_number": "AUTH-TC-003456",
                "approved_units": 6,
                "expiration_date": now + timedelta(days=90),
                "denial_reason": None,
                "appeal_deadline": None,
                "notes": "Partially approved for 6 units. Renewal required after 3 months.",
                "created_at": now - timedelta(days=11),
            },
            # LIBTAYO trial
            {
                "id": "PAR-00000009",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3001",
                "site_id": "SITE-105",
                "pre_auth_status": PreAuthStatus.APPROVED,
                "procedure_code": "J9119",
                "procedure_description": "Cemiplimab-rwlc IV infusion",
                "requesting_provider": "Dr. Angela Torres",
                "insurance_provider": "Medicare Advantage (Humana)",
                "request_date": now - timedelta(days=22),
                "decision_date": now - timedelta(days=18),
                "authorization_number": "AUTH-HUM-007890",
                "approved_units": 8,
                "expiration_date": now + timedelta(days=120),
                "denial_reason": None,
                "appeal_deadline": None,
                "notes": "Approved for 8 infusion cycles.",
                "created_at": now - timedelta(days=24),
            },
            {
                "id": "PAR-00000010",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3002",
                "site_id": "SITE-105",
                "pre_auth_status": PreAuthStatus.APPROVED,
                "procedure_code": "J9119",
                "procedure_description": "Cemiplimab-rwlc IV infusion",
                "requesting_provider": "Dr. Angela Torres",
                "insurance_provider": "Veterans Affairs",
                "request_date": now - timedelta(days=12),
                "decision_date": now - timedelta(days=10),
                "authorization_number": "AUTH-VA-004567",
                "approved_units": 12,
                "expiration_date": now + timedelta(days=180),
                "denial_reason": None,
                "appeal_deadline": None,
                "notes": "VA pre-authorization approved. No copay for service-connected.",
                "created_at": now - timedelta(days=13),
            },
            {
                "id": "PAR-00000011",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3003",
                "site_id": "SITE-106",
                "pre_auth_status": PreAuthStatus.DENIED,
                "procedure_code": "J9119",
                "procedure_description": "Cemiplimab-rwlc IV infusion",
                "requesting_provider": "Dr. Michael Brown",
                "insurance_provider": "Anthem",
                "request_date": now - timedelta(days=20),
                "decision_date": now - timedelta(days=14),
                "authorization_number": None,
                "approved_units": 0,
                "expiration_date": None,
                "denial_reason": DenialReason.EXPERIMENTAL,
                "appeal_deadline": now + timedelta(days=16),
                "notes": "Denied as experimental. Appeal being prepared with clinical evidence.",
                "created_at": now - timedelta(days=22),
            },
            {
                "id": "PAR-00000012",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3004",
                "site_id": "SITE-106",
                "pre_auth_status": PreAuthStatus.EXPIRED,
                "procedure_code": "J9119",
                "procedure_description": "Cemiplimab-rwlc IV infusion",
                "requesting_provider": "Dr. Michael Brown",
                "insurance_provider": "Kaiser Permanente",
                "request_date": now - timedelta(days=120),
                "decision_date": now - timedelta(days=115),
                "authorization_number": "AUTH-KP-001122",
                "approved_units": 4,
                "expiration_date": now - timedelta(days=10),
                "denial_reason": None,
                "appeal_deadline": None,
                "notes": "Authorization expired. Renewal request to be submitted.",
                "created_at": now - timedelta(days=125),
            },
        ]

        for p in pre_auth_data:
            self._pre_authorization_requests[p["id"]] = PreAuthorizationRequest(**p)

        # --- 12 Coverage Determinations (4 per trial) ---
        coverage_data = [
            # EYLEA trial
            {
                "id": "CVD-00000001",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1001",
                "site_id": "SITE-101",
                "coverage_type": CoverageType.PRIVATE,
                "procedure_category": "Intravitreal injection",
                "is_covered": True,
                "sponsor_responsibility": False,
                "patient_responsibility_pct": 20.0,
                "determination_date": now - timedelta(days=80),
                "determined_by": "Insurance Coordinator A",
                "policy_reference": "Aetna SPD Section 4.2",
                "qualifying_criteria": "FDA-approved indication for wet AMD",
                "exclusion_criteria": None,
                "effective_date": now - timedelta(days=80),
                "review_date": now + timedelta(days=100),
                "notes": "Standard medical benefit. Patient responsible for 20% coinsurance.",
                "created_at": now - timedelta(days=82),
            },
            {
                "id": "CVD-00000002",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1002",
                "site_id": "SITE-101",
                "coverage_type": CoverageType.MEDICARE,
                "procedure_category": "Intravitreal injection",
                "is_covered": True,
                "sponsor_responsibility": False,
                "patient_responsibility_pct": 20.0,
                "determination_date": now - timedelta(days=50),
                "determined_by": "Insurance Coordinator A",
                "policy_reference": "Medicare NCD 80.11",
                "qualifying_criteria": "Medically necessary for diagnosed condition",
                "exclusion_criteria": None,
                "effective_date": now - timedelta(days=50),
                "review_date": now + timedelta(days=130),
                "notes": "Medicare Part B covers 80%. Medigap secondary may cover remainder.",
                "created_at": now - timedelta(days=52),
            },
            {
                "id": "CVD-00000003",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1003",
                "site_id": "SITE-102",
                "coverage_type": CoverageType.PRIVATE,
                "procedure_category": "Intravitreal injection",
                "is_covered": False,
                "sponsor_responsibility": True,
                "patient_responsibility_pct": 0.0,
                "determination_date": now - timedelta(days=4),
                "determined_by": "Insurance Coordinator B",
                "policy_reference": None,
                "qualifying_criteria": None,
                "exclusion_criteria": "Coverage not yet verified",
                "effective_date": None,
                "review_date": now + timedelta(days=14),
                "notes": "Pending verification. Sponsor assumes responsibility until confirmed.",
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "CVD-00000004",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1004",
                "site_id": "SITE-102",
                "coverage_type": CoverageType.PRIVATE,
                "procedure_category": "Intravitreal injection",
                "is_covered": False,
                "sponsor_responsibility": True,
                "patient_responsibility_pct": 0.0,
                "determination_date": now - timedelta(days=35),
                "determined_by": "Insurance Coordinator B",
                "policy_reference": None,
                "qualifying_criteria": None,
                "exclusion_criteria": "Coverage lapsed",
                "effective_date": now - timedelta(days=35),
                "review_date": None,
                "notes": "No active coverage. Sponsor responsibility per protocol.",
                "created_at": now - timedelta(days=37),
            },
            # DUPIXENT trial
            {
                "id": "CVD-00000005",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2001",
                "site_id": "SITE-103",
                "coverage_type": CoverageType.PRIVATE,
                "procedure_category": "Biologic subcutaneous injection",
                "is_covered": True,
                "sponsor_responsibility": False,
                "patient_responsibility_pct": 15.0,
                "determination_date": now - timedelta(days=25),
                "determined_by": "Insurance Coordinator C",
                "policy_reference": "BCBS Specialty Pharmacy Formulary T3",
                "qualifying_criteria": "Prior authorization approved; step therapy completed",
                "exclusion_criteria": None,
                "effective_date": now - timedelta(days=25),
                "review_date": now + timedelta(days=155),
                "notes": "Covered under specialty pharmacy benefit. Copay assistance enrolled.",
                "created_at": now - timedelta(days=27),
            },
            {
                "id": "CVD-00000006",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2002",
                "site_id": "SITE-103",
                "coverage_type": CoverageType.MEDICAID,
                "procedure_category": "Biologic subcutaneous injection",
                "is_covered": True,
                "sponsor_responsibility": False,
                "patient_responsibility_pct": 0.0,
                "determination_date": now - timedelta(days=18),
                "determined_by": "Insurance Coordinator C",
                "policy_reference": "NY Medicaid Preferred Drug List",
                "qualifying_criteria": "Meets Medicaid prior auth criteria for atopic dermatitis",
                "exclusion_criteria": None,
                "effective_date": now - timedelta(days=18),
                "review_date": now + timedelta(days=62),
                "notes": "Medicaid covers at 100%. No patient cost share.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "CVD-00000007",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2003",
                "site_id": "SITE-104",
                "coverage_type": CoverageType.UNINSURED,
                "procedure_category": "Biologic subcutaneous injection",
                "is_covered": False,
                "sponsor_responsibility": True,
                "patient_responsibility_pct": 0.0,
                "determination_date": now - timedelta(days=13),
                "determined_by": "Insurance Coordinator D",
                "policy_reference": None,
                "qualifying_criteria": None,
                "exclusion_criteria": "No insurance coverage",
                "effective_date": now - timedelta(days=13),
                "review_date": None,
                "notes": "Sponsor covers all costs. Patient enrolled in assistance program.",
                "created_at": now - timedelta(days=14),
            },
            {
                "id": "CVD-00000008",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2004",
                "site_id": "SITE-104",
                "coverage_type": CoverageType.TRICARE,
                "procedure_category": "Biologic subcutaneous injection",
                "is_covered": True,
                "sponsor_responsibility": False,
                "patient_responsibility_pct": 10.0,
                "determination_date": now - timedelta(days=8),
                "determined_by": "Insurance Coordinator D",
                "policy_reference": "TRICARE Formulary Tier 3",
                "qualifying_criteria": "TRICARE-authorized specialty medication",
                "exclusion_criteria": None,
                "effective_date": now - timedelta(days=8),
                "review_date": now + timedelta(days=82),
                "notes": "TRICARE covers 90% of specialty pharmacy cost.",
                "created_at": now - timedelta(days=9),
            },
            # LIBTAYO trial
            {
                "id": "CVD-00000009",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3001",
                "site_id": "SITE-105",
                "coverage_type": CoverageType.MEDICARE,
                "procedure_category": "IV immunotherapy infusion",
                "is_covered": True,
                "sponsor_responsibility": False,
                "patient_responsibility_pct": 20.0,
                "determination_date": now - timedelta(days=20),
                "determined_by": "Insurance Coordinator E",
                "policy_reference": "Humana MA Oncology Benefit",
                "qualifying_criteria": "FDA-approved for advanced CSCC",
                "exclusion_criteria": None,
                "effective_date": now - timedelta(days=20),
                "review_date": now + timedelta(days=70),
                "notes": "Medicare Advantage covers under medical benefit.",
                "created_at": now - timedelta(days=22),
            },
            {
                "id": "CVD-00000010",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3002",
                "site_id": "SITE-105",
                "coverage_type": CoverageType.VA,
                "procedure_category": "IV immunotherapy infusion",
                "is_covered": True,
                "sponsor_responsibility": False,
                "patient_responsibility_pct": 0.0,
                "determination_date": now - timedelta(days=11),
                "determined_by": "Insurance Coordinator E",
                "policy_reference": "VA National Formulary",
                "qualifying_criteria": "Service-connected condition; VA-approved treatment",
                "exclusion_criteria": None,
                "effective_date": now - timedelta(days=11),
                "review_date": now + timedelta(days=169),
                "notes": "VA covers at 100% for service-connected condition.",
                "created_at": now - timedelta(days=12),
            },
            {
                "id": "CVD-00000011",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3003",
                "site_id": "SITE-106",
                "coverage_type": CoverageType.PRIVATE,
                "procedure_category": "IV immunotherapy infusion",
                "is_covered": False,
                "sponsor_responsibility": True,
                "patient_responsibility_pct": 0.0,
                "determination_date": now - timedelta(days=2),
                "determined_by": "Insurance Coordinator F",
                "policy_reference": None,
                "qualifying_criteria": None,
                "exclusion_criteria": "Denied as experimental by Anthem",
                "effective_date": now - timedelta(days=2),
                "review_date": now + timedelta(days=28),
                "notes": "Insurer denied. Sponsor covers pending appeal outcome.",
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "CVD-00000012",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3004",
                "site_id": "SITE-106",
                "coverage_type": CoverageType.PRIVATE,
                "procedure_category": "IV immunotherapy infusion",
                "is_covered": True,
                "sponsor_responsibility": False,
                "patient_responsibility_pct": 25.0,
                "determination_date": now - timedelta(days=6),
                "determined_by": "Insurance Coordinator F",
                "policy_reference": "Kaiser Oncology Treatment Policy",
                "qualifying_criteria": "In-network oncology benefit; approved indication",
                "exclusion_criteria": None,
                "effective_date": now - timedelta(days=6),
                "review_date": now + timedelta(days=174),
                "notes": "HMO in-network oncology benefit. 25% coinsurance applies.",
                "created_at": now - timedelta(days=7),
            },
        ]

        for c in coverage_data:
            self._coverage_determinations[c["id"]] = CoverageDetermination(**c)

        # --- 12 Reimbursement Trackings (4 per trial) ---
        reimbursement_data = [
            # EYLEA trial
            {
                "id": "RMB-00000001",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1001",
                "site_id": "SITE-101",
                "reimbursement_status": ReimbursementStatus.APPROVED,
                "claim_number": "CLM-AET-2026-001",
                "procedure_code": "J0178",
                "billed_amount": 1850.0,
                "approved_amount": 1480.0,
                "paid_amount": 1480.0,
                "patient_responsibility": 370.0,
                "submission_date": now - timedelta(days=75),
                "payment_date": now - timedelta(days=45),
                "denial_reason": None,
                "appeal_filed": False,
                "appeal_date": None,
                "processed_by": "Revenue Cycle Analyst A",
                "notes": "Claim paid in full per contracted rate. Patient billed for 20%.",
                "created_at": now - timedelta(days=78),
            },
            {
                "id": "RMB-00000002",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1002",
                "site_id": "SITE-101",
                "reimbursement_status": ReimbursementStatus.PARTIALLY_PAID,
                "claim_number": "CLM-MED-2026-002",
                "procedure_code": "J0178",
                "billed_amount": 1850.0,
                "approved_amount": 1480.0,
                "paid_amount": 1184.0,
                "patient_responsibility": 296.0,
                "submission_date": now - timedelta(days=50),
                "payment_date": now - timedelta(days=30),
                "denial_reason": None,
                "appeal_filed": False,
                "appeal_date": None,
                "processed_by": "Revenue Cycle Analyst A",
                "notes": "Medicare 80% paid. Awaiting Medigap secondary payment.",
                "created_at": now - timedelta(days=53),
            },
            {
                "id": "RMB-00000003",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1003",
                "site_id": "SITE-102",
                "reimbursement_status": ReimbursementStatus.SUBMITTED,
                "claim_number": "CLM-UHC-2026-003",
                "procedure_code": "J0178",
                "billed_amount": 1850.0,
                "approved_amount": 0.0,
                "paid_amount": 0.0,
                "patient_responsibility": 0.0,
                "submission_date": now - timedelta(days=3),
                "payment_date": None,
                "denial_reason": None,
                "appeal_filed": False,
                "appeal_date": None,
                "processed_by": "Revenue Cycle Analyst B",
                "notes": "Claim submitted pending pre-auth confirmation.",
                "created_at": now - timedelta(days=4),
            },
            {
                "id": "RMB-00000004",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1004",
                "site_id": "SITE-102",
                "reimbursement_status": ReimbursementStatus.DENIED,
                "claim_number": "CLM-CIG-2026-004",
                "procedure_code": "J0178",
                "billed_amount": 1850.0,
                "approved_amount": 0.0,
                "paid_amount": 0.0,
                "patient_responsibility": 0.0,
                "submission_date": now - timedelta(days=38),
                "payment_date": None,
                "denial_reason": DenialReason.COVERAGE_LAPSED,
                "appeal_filed": True,
                "appeal_date": now - timedelta(days=25),
                "processed_by": "Revenue Cycle Analyst B",
                "notes": "Denied - coverage lapsed. Appeal filed. Sponsor backup coverage.",
                "created_at": now - timedelta(days=40),
            },
            # DUPIXENT trial
            {
                "id": "RMB-00000005",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2001",
                "site_id": "SITE-103",
                "reimbursement_status": ReimbursementStatus.APPROVED,
                "claim_number": "CLM-BCBS-2026-005",
                "procedure_code": "J0593",
                "billed_amount": 3200.0,
                "approved_amount": 2720.0,
                "paid_amount": 2720.0,
                "patient_responsibility": 480.0,
                "submission_date": now - timedelta(days=22),
                "payment_date": now - timedelta(days=10),
                "denial_reason": None,
                "appeal_filed": False,
                "appeal_date": None,
                "processed_by": "Revenue Cycle Analyst C",
                "notes": "Specialty pharmacy claim paid. 15% patient coinsurance.",
                "created_at": now - timedelta(days=24),
            },
            {
                "id": "RMB-00000006",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2002",
                "site_id": "SITE-103",
                "reimbursement_status": ReimbursementStatus.IN_REVIEW,
                "claim_number": "CLM-NYMED-2026-006",
                "procedure_code": "J0593",
                "billed_amount": 3200.0,
                "approved_amount": 0.0,
                "paid_amount": 0.0,
                "patient_responsibility": 0.0,
                "submission_date": now - timedelta(days=15),
                "payment_date": None,
                "denial_reason": None,
                "appeal_filed": False,
                "appeal_date": None,
                "processed_by": "Revenue Cycle Analyst C",
                "notes": "Medicaid claim under review. Expected 30-day adjudication.",
                "created_at": now - timedelta(days=16),
            },
            {
                "id": "RMB-00000007",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2003",
                "site_id": "SITE-104",
                "reimbursement_status": ReimbursementStatus.DENIED,
                "claim_number": None,
                "procedure_code": "J0593",
                "billed_amount": 3200.0,
                "approved_amount": 0.0,
                "paid_amount": 0.0,
                "patient_responsibility": 0.0,
                "submission_date": now - timedelta(days=12),
                "payment_date": None,
                "denial_reason": DenialReason.OTHER,
                "appeal_filed": False,
                "appeal_date": None,
                "processed_by": "Revenue Cycle Analyst D",
                "notes": "No insurance. Sponsor invoiced directly per protocol budget.",
                "created_at": now - timedelta(days=13),
            },
            {
                "id": "RMB-00000008",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2004",
                "site_id": "SITE-104",
                "reimbursement_status": ReimbursementStatus.SUBMITTED,
                "claim_number": "CLM-TC-2026-008",
                "procedure_code": "J0593",
                "billed_amount": 3200.0,
                "approved_amount": 0.0,
                "paid_amount": 0.0,
                "patient_responsibility": 0.0,
                "submission_date": now - timedelta(days=5),
                "payment_date": None,
                "denial_reason": None,
                "appeal_filed": False,
                "appeal_date": None,
                "processed_by": "Revenue Cycle Analyst D",
                "notes": "TRICARE claim submitted via DHA portal.",
                "created_at": now - timedelta(days=6),
            },
            # LIBTAYO trial
            {
                "id": "RMB-00000009",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3001",
                "site_id": "SITE-105",
                "reimbursement_status": ReimbursementStatus.APPROVED,
                "claim_number": "CLM-HUM-2026-009",
                "procedure_code": "J9119",
                "billed_amount": 9800.0,
                "approved_amount": 7840.0,
                "paid_amount": 7840.0,
                "patient_responsibility": 1960.0,
                "submission_date": now - timedelta(days=18),
                "payment_date": now - timedelta(days=8),
                "denial_reason": None,
                "appeal_filed": False,
                "appeal_date": None,
                "processed_by": "Revenue Cycle Analyst E",
                "notes": "Medicare Advantage claim paid. 20% patient responsibility.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "RMB-00000010",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3002",
                "site_id": "SITE-105",
                "reimbursement_status": ReimbursementStatus.APPROVED,
                "claim_number": "CLM-VA-2026-010",
                "procedure_code": "J9119",
                "billed_amount": 9800.0,
                "approved_amount": 9800.0,
                "paid_amount": 9800.0,
                "patient_responsibility": 0.0,
                "submission_date": now - timedelta(days=9),
                "payment_date": now - timedelta(days=4),
                "denial_reason": None,
                "appeal_filed": False,
                "appeal_date": None,
                "processed_by": "Revenue Cycle Analyst E",
                "notes": "VA claim paid at 100%. No patient cost share.",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "RMB-00000011",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3003",
                "site_id": "SITE-106",
                "reimbursement_status": ReimbursementStatus.APPEALED,
                "claim_number": "CLM-ANT-2026-011",
                "procedure_code": "J9119",
                "billed_amount": 9800.0,
                "approved_amount": 0.0,
                "paid_amount": 0.0,
                "patient_responsibility": 0.0,
                "submission_date": now - timedelta(days=16),
                "payment_date": None,
                "denial_reason": DenialReason.EXPERIMENTAL,
                "appeal_filed": True,
                "appeal_date": now - timedelta(days=6),
                "processed_by": "Revenue Cycle Analyst F",
                "notes": "Denied as experimental. Level 1 appeal filed with clinical evidence.",
                "created_at": now - timedelta(days=18),
            },
            {
                "id": "RMB-00000012",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3004",
                "site_id": "SITE-106",
                "reimbursement_status": ReimbursementStatus.PARTIALLY_PAID,
                "claim_number": "CLM-KP-2026-012",
                "procedure_code": "J9119",
                "billed_amount": 9800.0,
                "approved_amount": 7350.0,
                "paid_amount": 5512.50,
                "patient_responsibility": 1837.50,
                "submission_date": now - timedelta(days=7),
                "payment_date": now - timedelta(days=2),
                "denial_reason": None,
                "appeal_filed": False,
                "appeal_date": None,
                "processed_by": "Revenue Cycle Analyst F",
                "notes": "Kaiser partial payment. 25% coinsurance. Awaiting secondary.",
                "created_at": now - timedelta(days=8),
            },
        ]

        for r in reimbursement_data:
            self._reimbursement_trackings[r["id"]] = ReimbursementTracking(**r)

    # ------------------------------------------------------------------
    # Eligibility Checks
    # ------------------------------------------------------------------

    def list_eligibility_checks(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[EligibilityCheck]:
        """List eligibility checks with optional trial_id filter."""
        with self._lock:
            result = list(self._eligibility_checks.values())
        if trial_id is not None:
            result = [e for e in result if e.trial_id == trial_id]
        return sorted(result, key=lambda e: e.created_at, reverse=True)

    def get_eligibility_check(self, check_id: str) -> EligibilityCheck | None:
        """Get a single eligibility check by ID."""
        with self._lock:
            return self._eligibility_checks.get(check_id)

    def create_eligibility_check(self, payload: EligibilityCheckCreate) -> EligibilityCheck:
        """Create a new eligibility check."""
        now = datetime.now(timezone.utc)
        check_id = f"ELC-{uuid4().hex[:8].upper()}"
        check = EligibilityCheck(
            id=check_id,
            **payload.model_dump(),
            created_at=now,
        )
        with self._lock:
            self._eligibility_checks[check_id] = check
        logger.info("Created eligibility check %s for subject %s", check_id, payload.subject_id)
        return check

    def update_eligibility_check(
        self, check_id: str, payload: EligibilityCheckUpdate
    ) -> EligibilityCheck | None:
        """Update an existing eligibility check."""
        with self._lock:
            existing = self._eligibility_checks.get(check_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = EligibilityCheck(**data)
            self._eligibility_checks[check_id] = updated
        return updated

    def delete_eligibility_check(self, check_id: str) -> bool:
        """Delete an eligibility check. Returns True if deleted."""
        with self._lock:
            if check_id in self._eligibility_checks:
                del self._eligibility_checks[check_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Pre-Authorization Requests
    # ------------------------------------------------------------------

    def list_pre_authorization_requests(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[PreAuthorizationRequest]:
        """List pre-authorization requests with optional trial_id filter."""
        with self._lock:
            result = list(self._pre_authorization_requests.values())
        if trial_id is not None:
            result = [p for p in result if p.trial_id == trial_id]
        return sorted(result, key=lambda p: p.created_at, reverse=True)

    def get_pre_authorization_request(self, request_id: str) -> PreAuthorizationRequest | None:
        """Get a single pre-authorization request by ID."""
        with self._lock:
            return self._pre_authorization_requests.get(request_id)

    def create_pre_authorization_request(
        self, payload: PreAuthorizationRequestCreate
    ) -> PreAuthorizationRequest:
        """Create a new pre-authorization request."""
        now = datetime.now(timezone.utc)
        request_id = f"PAR-{uuid4().hex[:8].upper()}"
        request = PreAuthorizationRequest(
            id=request_id,
            **payload.model_dump(),
            created_at=now,
        )
        with self._lock:
            self._pre_authorization_requests[request_id] = request
        logger.info("Created pre-auth request %s for subject %s", request_id, payload.subject_id)
        return request

    def update_pre_authorization_request(
        self, request_id: str, payload: PreAuthorizationRequestUpdate
    ) -> PreAuthorizationRequest | None:
        """Update an existing pre-authorization request."""
        with self._lock:
            existing = self._pre_authorization_requests.get(request_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = PreAuthorizationRequest(**data)
            self._pre_authorization_requests[request_id] = updated
        return updated

    def delete_pre_authorization_request(self, request_id: str) -> bool:
        """Delete a pre-authorization request. Returns True if deleted."""
        with self._lock:
            if request_id in self._pre_authorization_requests:
                del self._pre_authorization_requests[request_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Coverage Determinations
    # ------------------------------------------------------------------

    def list_coverage_determinations(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[CoverageDetermination]:
        """List coverage determinations with optional trial_id filter."""
        with self._lock:
            result = list(self._coverage_determinations.values())
        if trial_id is not None:
            result = [c for c in result if c.trial_id == trial_id]
        return sorted(result, key=lambda c: c.created_at, reverse=True)

    def get_coverage_determination(self, determination_id: str) -> CoverageDetermination | None:
        """Get a single coverage determination by ID."""
        with self._lock:
            return self._coverage_determinations.get(determination_id)

    def create_coverage_determination(
        self, payload: CoverageDeterminationCreate
    ) -> CoverageDetermination:
        """Create a new coverage determination."""
        now = datetime.now(timezone.utc)
        determination_id = f"CVD-{uuid4().hex[:8].upper()}"
        determination = CoverageDetermination(
            id=determination_id,
            **payload.model_dump(),
            created_at=now,
        )
        with self._lock:
            self._coverage_determinations[determination_id] = determination
        logger.info(
            "Created coverage determination %s for subject %s",
            determination_id,
            payload.subject_id,
        )
        return determination

    def update_coverage_determination(
        self, determination_id: str, payload: CoverageDeterminationUpdate
    ) -> CoverageDetermination | None:
        """Update an existing coverage determination."""
        with self._lock:
            existing = self._coverage_determinations.get(determination_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CoverageDetermination(**data)
            self._coverage_determinations[determination_id] = updated
        return updated

    def delete_coverage_determination(self, determination_id: str) -> bool:
        """Delete a coverage determination. Returns True if deleted."""
        with self._lock:
            if determination_id in self._coverage_determinations:
                del self._coverage_determinations[determination_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Reimbursement Tracking
    # ------------------------------------------------------------------

    def list_reimbursement_trackings(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[ReimbursementTracking]:
        """List reimbursement trackings with optional trial_id filter."""
        with self._lock:
            result = list(self._reimbursement_trackings.values())
        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        return sorted(result, key=lambda r: r.created_at, reverse=True)

    def get_reimbursement_tracking(self, tracking_id: str) -> ReimbursementTracking | None:
        """Get a single reimbursement tracking by ID."""
        with self._lock:
            return self._reimbursement_trackings.get(tracking_id)

    def create_reimbursement_tracking(
        self, payload: ReimbursementTrackingCreate
    ) -> ReimbursementTracking:
        """Create a new reimbursement tracking."""
        now = datetime.now(timezone.utc)
        tracking_id = f"RMB-{uuid4().hex[:8].upper()}"
        tracking = ReimbursementTracking(
            id=tracking_id,
            **payload.model_dump(),
            created_at=now,
        )
        with self._lock:
            self._reimbursement_trackings[tracking_id] = tracking
        logger.info(
            "Created reimbursement tracking %s for subject %s",
            tracking_id,
            payload.subject_id,
        )
        return tracking

    def update_reimbursement_tracking(
        self, tracking_id: str, payload: ReimbursementTrackingUpdate
    ) -> ReimbursementTracking | None:
        """Update an existing reimbursement tracking."""
        with self._lock:
            existing = self._reimbursement_trackings.get(tracking_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ReimbursementTracking(**data)
            self._reimbursement_trackings[tracking_id] = updated
        return updated

    def delete_reimbursement_tracking(self, tracking_id: str) -> bool:
        """Delete a reimbursement tracking. Returns True if deleted."""
        with self._lock:
            if tracking_id in self._reimbursement_trackings:
                del self._reimbursement_trackings[tracking_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(
        self,
        *,
        trial_id: str | None = None,
    ) -> PatientInsuranceVerificationMetrics:
        """Compute aggregated insurance verification metrics."""
        with self._lock:
            checks = list(self._eligibility_checks.values())
            pre_auths = list(self._pre_authorization_requests.values())
            determinations = list(self._coverage_determinations.values())
            reimbursements = list(self._reimbursement_trackings.values())

        if trial_id is not None:
            checks = [c for c in checks if c.trial_id == trial_id]
            pre_auths = [p for p in pre_auths if p.trial_id == trial_id]
            determinations = [d for d in determinations if d.trial_id == trial_id]
            reimbursements = [r for r in reimbursements if r.trial_id == trial_id]

        # Eligibility checks by status
        checks_by_status: dict[str, int] = {}
        for c in checks:
            key = c.eligibility_status.value
            checks_by_status[key] = checks_by_status.get(key, 0) + 1

        # Eligibility checks by coverage type
        checks_by_coverage_type: dict[str, int] = {}
        for c in checks:
            key = c.coverage_type.value
            checks_by_coverage_type[key] = checks_by_coverage_type.get(key, 0) + 1

        # Pre-auth by status
        pre_auths_by_status: dict[str, int] = {}
        for p in pre_auths:
            key = p.pre_auth_status.value
            pre_auths_by_status[key] = pre_auths_by_status.get(key, 0) + 1

        # Pre-auth approval rate
        approved_count = sum(
            1 for p in pre_auths
            if p.pre_auth_status in (PreAuthStatus.APPROVED, PreAuthStatus.PARTIALLY_APPROVED)
        )
        decided_count = sum(
            1 for p in pre_auths
            if p.pre_auth_status not in (PreAuthStatus.REQUESTED, PreAuthStatus.PENDING_REVIEW)
        )
        pre_auth_approval_rate = (
            round(approved_count / decided_count * 100, 1) if decided_count > 0 else 0.0
        )

        # Coverage rate
        covered_count = sum(1 for d in determinations if d.is_covered)
        coverage_rate = (
            round(covered_count / len(determinations) * 100, 1)
            if determinations
            else 0.0
        )

        # Reimbursement by status
        reimbursements_by_status: dict[str, int] = {}
        for r in reimbursements:
            key = r.reimbursement_status.value
            reimbursements_by_status[key] = reimbursements_by_status.get(key, 0) + 1

        total_billed = sum(r.billed_amount for r in reimbursements)
        total_paid = sum(r.paid_amount for r in reimbursements)

        return PatientInsuranceVerificationMetrics(
            total_eligibility_checks=len(checks),
            checks_by_status=checks_by_status,
            checks_by_coverage_type=checks_by_coverage_type,
            total_pre_authorizations=len(pre_auths),
            pre_auths_by_status=pre_auths_by_status,
            pre_auth_approval_rate=pre_auth_approval_rate,
            total_coverage_determinations=len(determinations),
            coverage_rate=coverage_rate,
            total_reimbursements=len(reimbursements),
            reimbursements_by_status=reimbursements_by_status,
            total_billed_amount=round(total_billed, 2),
            total_paid_amount=round(total_paid, 2),
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: PatientInsuranceVerificationService | None = None
_instance_lock = threading.Lock()


def get_patient_insurance_verification_service() -> PatientInsuranceVerificationService:
    """Return the singleton PatientInsuranceVerificationService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = PatientInsuranceVerificationService()
    return _instance


def reset_patient_insurance_verification_service() -> PatientInsuranceVerificationService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = PatientInsuranceVerificationService()
    return _instance
