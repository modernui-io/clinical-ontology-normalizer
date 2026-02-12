"""Site Qualification Management Service (SITE-QUAL).

Manages site qualification operations: capability assessments,
equipment verification, staff credentialing, infrastructure audits,
and qualification records with compliance metrics.

Usage:
    from app.services.site_qualification_service import (
        get_site_qualification_service,
    )

    svc = get_site_qualification_service()
    assessments = svc.list_capability_assessments()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.site_qualification import (
    AuditRating,
    AssessmentCategory,
    CapabilityAssessment,
    CapabilityAssessmentCreate,
    CapabilityAssessmentUpdate,
    CredentialType,
    EquipmentStatus,
    EquipmentVerification,
    EquipmentVerificationCreate,
    EquipmentVerificationUpdate,
    InfrastructureAudit,
    InfrastructureAuditCreate,
    InfrastructureAuditUpdate,
    QualificationRecord,
    QualificationRecordCreate,
    QualificationRecordUpdate,
    QualificationStatus,
    SiteQualificationMetrics,
    StaffCredential,
    StaffCredentialCreate,
    StaffCredentialUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class SiteQualificationService:
    """In-memory Site Qualification Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._capability_assessments: dict[str, CapabilityAssessment] = {}
        self._equipment_verifications: dict[str, EquipmentVerification] = {}
        self._staff_credentials: dict[str, StaffCredential] = {}
        self._infrastructure_audits: dict[str, InfrastructureAudit] = {}
        self._qualification_records: dict[str, QualificationRecord] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic site qualification data."""
        now = datetime.now(timezone.utc)

        # --- 12 Capability Assessments ---
        assessments_data = [
            {
                "id": "CA-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "category": AssessmentCategory.THERAPEUTIC_EXPERIENCE,
                "assessment_date": now - timedelta(days=180),
                "score": 88.0,
                "max_score": 100.0,
                "pass_threshold": 70.0,
                "passed": True,
                "prior_trial_count": 12,
                "therapeutic_area_experience": True,
                "patient_pool_estimate": 450,
                "competing_trials": 2,
                "findings": ["Strong retinal disease experience", "Published investigator"],
                "assessor": "Dr. Rachel Green",
                "reviewer": "Dr. Michael Torres",
                "notes": "Excellent ophthalmology trial track record.",
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "CA-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "category": AssessmentCategory.PATIENT_POPULATION,
                "assessment_date": now - timedelta(days=178),
                "score": 75.0,
                "max_score": 100.0,
                "pass_threshold": 70.0,
                "passed": True,
                "prior_trial_count": 12,
                "therapeutic_area_experience": True,
                "patient_pool_estimate": 450,
                "competing_trials": 2,
                "findings": ["Adequate AMD patient pool", "Two competing enrollment studies"],
                "assessor": "Dr. Rachel Green",
                "reviewer": "Dr. Michael Torres",
                "notes": "Competing trials may affect enrollment rates.",
                "created_at": now - timedelta(days=178),
            },
            {
                "id": "CA-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "category": AssessmentCategory.INFRASTRUCTURE,
                "assessment_date": now - timedelta(days=170),
                "score": 92.0,
                "max_score": 100.0,
                "pass_threshold": 70.0,
                "passed": True,
                "prior_trial_count": 8,
                "therapeutic_area_experience": True,
                "patient_pool_estimate": 320,
                "competing_trials": 1,
                "findings": ["State-of-the-art imaging suite", "Dedicated research pharmacy"],
                "assessor": "Dr. Rachel Green",
                "reviewer": None,
                "notes": "Exceptional infrastructure for ophthalmic trials.",
                "created_at": now - timedelta(days=170),
            },
            {
                "id": "CA-004",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-201",
                "category": AssessmentCategory.THERAPEUTIC_EXPERIENCE,
                "assessment_date": now - timedelta(days=150),
                "score": 82.0,
                "max_score": 100.0,
                "pass_threshold": 70.0,
                "passed": True,
                "prior_trial_count": 6,
                "therapeutic_area_experience": True,
                "patient_pool_estimate": 280,
                "competing_trials": 3,
                "findings": ["Experienced in atopic dermatitis trials", "Good retention rates"],
                "assessor": "Dr. Lisa Chang",
                "reviewer": "Dr. David Patel",
                "notes": "Strong dermatology department.",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "CA-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-202",
                "category": AssessmentCategory.STAFF_CAPABILITY,
                "assessment_date": now - timedelta(days=145),
                "score": 65.0,
                "max_score": 100.0,
                "pass_threshold": 70.0,
                "passed": False,
                "prior_trial_count": 3,
                "therapeutic_area_experience": False,
                "patient_pool_estimate": 180,
                "competing_trials": 1,
                "findings": ["Insufficient GCP-trained coordinators", "No dedicated research nurse"],
                "assessor": "Dr. Lisa Chang",
                "reviewer": "Dr. David Patel",
                "notes": "Staff training required before qualification.",
                "created_at": now - timedelta(days=145),
            },
            {
                "id": "CA-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-201",
                "category": AssessmentCategory.DATA_MANAGEMENT,
                "assessment_date": now - timedelta(days=140),
                "score": 78.0,
                "max_score": 100.0,
                "pass_threshold": 70.0,
                "passed": True,
                "prior_trial_count": 6,
                "therapeutic_area_experience": True,
                "patient_pool_estimate": 280,
                "competing_trials": 3,
                "findings": ["EDC experience with Medidata", "Good query response time"],
                "assessor": "Dr. Lisa Chang",
                "reviewer": None,
                "notes": None,
                "created_at": now - timedelta(days=140),
            },
            {
                "id": "CA-007",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-301",
                "category": AssessmentCategory.REGULATORY_HISTORY,
                "assessment_date": now - timedelta(days=120),
                "score": 95.0,
                "max_score": 100.0,
                "pass_threshold": 70.0,
                "passed": True,
                "prior_trial_count": 20,
                "therapeutic_area_experience": True,
                "patient_pool_estimate": 550,
                "competing_trials": 4,
                "findings": ["Clean FDA inspection history", "No 483 observations in 5 years"],
                "assessor": "Dr. Angela Park",
                "reviewer": "Dr. William Torres",
                "notes": "Top-tier regulatory compliance record.",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "CA-008",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-302",
                "category": AssessmentCategory.THERAPEUTIC_EXPERIENCE,
                "assessment_date": now - timedelta(days=115),
                "score": 70.0,
                "max_score": 100.0,
                "pass_threshold": 70.0,
                "passed": True,
                "prior_trial_count": 5,
                "therapeutic_area_experience": True,
                "patient_pool_estimate": 200,
                "competing_trials": 2,
                "findings": ["Growing oncology program", "Recently hired experienced PI"],
                "assessor": "Dr. Angela Park",
                "reviewer": None,
                "notes": "Borderline pass; monitor closely during trial.",
                "created_at": now - timedelta(days=115),
            },
            {
                "id": "CA-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-301",
                "category": AssessmentCategory.INFRASTRUCTURE,
                "assessment_date": now - timedelta(days=110),
                "score": 90.0,
                "max_score": 100.0,
                "pass_threshold": 70.0,
                "passed": True,
                "prior_trial_count": 20,
                "therapeutic_area_experience": True,
                "patient_pool_estimate": 550,
                "competing_trials": 4,
                "findings": ["Full infusion center", "On-site pharmacy with hazardous drug handling"],
                "assessor": "Dr. Angela Park",
                "reviewer": "Dr. William Torres",
                "notes": "Infrastructure well suited for IO trials.",
                "created_at": now - timedelta(days=110),
            },
            {
                "id": "CA-010",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-103",
                "category": AssessmentCategory.STAFF_CAPABILITY,
                "assessment_date": now - timedelta(days=90),
                "score": 55.0,
                "max_score": 100.0,
                "pass_threshold": 70.0,
                "passed": False,
                "prior_trial_count": 2,
                "therapeutic_area_experience": False,
                "patient_pool_estimate": 150,
                "competing_trials": 0,
                "findings": ["PI lacks retinal subspecialty", "No certified ophthalmic technician"],
                "assessor": "Dr. Rachel Green",
                "reviewer": "Dr. Michael Torres",
                "notes": "Site does not meet minimum capability requirements.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "CA-011",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-203",
                "category": AssessmentCategory.PATIENT_POPULATION,
                "assessment_date": now - timedelta(days=60),
                "score": 85.0,
                "max_score": 100.0,
                "pass_threshold": 70.0,
                "passed": True,
                "prior_trial_count": 9,
                "therapeutic_area_experience": True,
                "patient_pool_estimate": 400,
                "competing_trials": 1,
                "findings": ["Large dermatology clinic", "Strong referral network"],
                "assessor": "Dr. Lisa Chang",
                "reviewer": None,
                "notes": "Excellent patient access.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "CA-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-303",
                "category": AssessmentCategory.DATA_MANAGEMENT,
                "assessment_date": now - timedelta(days=30),
                "score": 72.0,
                "max_score": 100.0,
                "pass_threshold": 70.0,
                "passed": True,
                "prior_trial_count": 4,
                "therapeutic_area_experience": False,
                "patient_pool_estimate": 170,
                "competing_trials": 0,
                "findings": ["Basic EDC capability", "Needs additional data manager training"],
                "assessor": "Dr. Angela Park",
                "reviewer": None,
                "notes": "Conditionally passes with training plan.",
                "created_at": now - timedelta(days=30),
            },
        ]

        for a in assessments_data:
            self._capability_assessments[a["id"]] = CapabilityAssessment(**a)

        # --- 12 Equipment Verifications ---
        equipment_data = [
            {
                "id": "EV-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "equipment_name": "Heidelberg Spectralis OCT",
                "equipment_type": "Imaging",
                "serial_number": "HSP-2021-4478",
                "manufacturer": "Heidelberg Engineering",
                "status": EquipmentStatus.OPERATIONAL,
                "last_calibration_date": now - timedelta(days=45),
                "next_calibration_date": now + timedelta(days=135),
                "calibration_certificate_on_file": True,
                "maintenance_contract_active": True,
                "meets_protocol_requirements": True,
                "verified_by": "Tech. James Wilson",
                "verification_date": now - timedelta(days=160),
                "notes": "Primary OCT device for retinal imaging.",
                "created_at": now - timedelta(days=160),
            },
            {
                "id": "EV-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "equipment_name": "ETDRS Visual Acuity Chart",
                "equipment_type": "Visual Assessment",
                "serial_number": "ETDRS-101-A",
                "manufacturer": "Precision Vision",
                "status": EquipmentStatus.OPERATIONAL,
                "last_calibration_date": now - timedelta(days=30),
                "next_calibration_date": now + timedelta(days=150),
                "calibration_certificate_on_file": True,
                "maintenance_contract_active": False,
                "meets_protocol_requirements": True,
                "verified_by": "Tech. James Wilson",
                "verification_date": now - timedelta(days=158),
                "notes": None,
                "created_at": now - timedelta(days=158),
            },
            {
                "id": "EV-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "equipment_name": "Zeiss Cirrus HD-OCT 6000",
                "equipment_type": "Imaging",
                "serial_number": "ZC6K-2022-1193",
                "manufacturer": "Carl Zeiss Meditec",
                "status": EquipmentStatus.NEEDS_CALIBRATION,
                "last_calibration_date": now - timedelta(days=200),
                "next_calibration_date": now - timedelta(days=20),
                "calibration_certificate_on_file": True,
                "maintenance_contract_active": True,
                "meets_protocol_requirements": False,
                "verified_by": "Tech. Maria Santos",
                "verification_date": now - timedelta(days=155),
                "notes": "Calibration overdue. Service call scheduled.",
                "created_at": now - timedelta(days=155),
            },
            {
                "id": "EV-004",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-201",
                "equipment_name": "Fotofinder VISIA Complexion Analysis",
                "equipment_type": "Dermatology Imaging",
                "serial_number": "FF-VISIA-8821",
                "manufacturer": "FotoFinder Systems",
                "status": EquipmentStatus.OPERATIONAL,
                "last_calibration_date": now - timedelta(days=60),
                "next_calibration_date": now + timedelta(days=120),
                "calibration_certificate_on_file": True,
                "maintenance_contract_active": True,
                "meets_protocol_requirements": True,
                "verified_by": "Tech. Anna Kowalski",
                "verification_date": now - timedelta(days=140),
                "notes": "Used for EASI scoring photography.",
                "created_at": now - timedelta(days=140),
            },
            {
                "id": "EV-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-201",
                "equipment_name": "Tewameter TM 300",
                "equipment_type": "Skin Measurement",
                "serial_number": "TW300-5567",
                "manufacturer": "Courage + Khazaka",
                "status": EquipmentStatus.OPERATIONAL,
                "last_calibration_date": now - timedelta(days=90),
                "next_calibration_date": now + timedelta(days=90),
                "calibration_certificate_on_file": True,
                "maintenance_contract_active": False,
                "meets_protocol_requirements": True,
                "verified_by": "Tech. Anna Kowalski",
                "verification_date": now - timedelta(days=138),
                "notes": "Transepidermal water loss measurement.",
                "created_at": now - timedelta(days=138),
            },
            {
                "id": "EV-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-202",
                "equipment_name": "Medical Refrigerator",
                "equipment_type": "Storage",
                "serial_number": "MR-LGS-2019-442",
                "manufacturer": "Helmer Scientific",
                "status": EquipmentStatus.UNDER_MAINTENANCE,
                "last_calibration_date": now - timedelta(days=100),
                "next_calibration_date": now + timedelta(days=80),
                "calibration_certificate_on_file": False,
                "maintenance_contract_active": True,
                "meets_protocol_requirements": False,
                "verified_by": "Tech. Anna Kowalski",
                "verification_date": now - timedelta(days=130),
                "notes": "Temperature excursion reported. Under repair.",
                "created_at": now - timedelta(days=130),
            },
            {
                "id": "EV-007",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-301",
                "equipment_name": "Baxter Colleague Infusion Pump",
                "equipment_type": "Infusion",
                "serial_number": "BXC-INF-7834",
                "manufacturer": "Baxter International",
                "status": EquipmentStatus.OPERATIONAL,
                "last_calibration_date": now - timedelta(days=40),
                "next_calibration_date": now + timedelta(days=140),
                "calibration_certificate_on_file": True,
                "maintenance_contract_active": True,
                "meets_protocol_requirements": True,
                "verified_by": "Tech. Robert Chen",
                "verification_date": now - timedelta(days=110),
                "notes": "Programmable for weight-based dosing.",
                "created_at": now - timedelta(days=110),
            },
            {
                "id": "EV-008",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-301",
                "equipment_name": "Emergency Crash Cart",
                "equipment_type": "Emergency",
                "serial_number": "EC-301-001",
                "manufacturer": "Harloff",
                "status": EquipmentStatus.OPERATIONAL,
                "last_calibration_date": now - timedelta(days=15),
                "next_calibration_date": now + timedelta(days=75),
                "calibration_certificate_on_file": True,
                "maintenance_contract_active": True,
                "meets_protocol_requirements": True,
                "verified_by": "Tech. Robert Chen",
                "verification_date": now - timedelta(days=108),
                "notes": "Monthly inspection schedule in place.",
                "created_at": now - timedelta(days=108),
            },
            {
                "id": "EV-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-302",
                "equipment_name": "B. Braun Infusomat Space",
                "equipment_type": "Infusion",
                "serial_number": "BB-ISP-3321",
                "manufacturer": "B. Braun",
                "status": EquipmentStatus.OUT_OF_SERVICE,
                "last_calibration_date": now - timedelta(days=250),
                "next_calibration_date": now - timedelta(days=70),
                "calibration_certificate_on_file": False,
                "maintenance_contract_active": False,
                "meets_protocol_requirements": False,
                "verified_by": "Tech. Robert Chen",
                "verification_date": now - timedelta(days=100),
                "notes": "Out of service. Replacement ordered.",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "EV-010",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-103",
                "equipment_name": "Topcon 3D OCT-1 Maestro2",
                "equipment_type": "Imaging",
                "serial_number": "TP-M2-6690",
                "manufacturer": "Topcon",
                "status": EquipmentStatus.DECOMMISSIONED,
                "last_calibration_date": now - timedelta(days=400),
                "next_calibration_date": None,
                "calibration_certificate_on_file": False,
                "maintenance_contract_active": False,
                "meets_protocol_requirements": False,
                "verified_by": "Tech. James Wilson",
                "verification_date": now - timedelta(days=85),
                "notes": "Decommissioned. Site acquiring replacement.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "EV-011",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-203",
                "equipment_name": "Dermatoscope DermLite DL4",
                "equipment_type": "Dermatology Assessment",
                "serial_number": "DL4-2023-112",
                "manufacturer": "DermLite",
                "status": EquipmentStatus.OPERATIONAL,
                "last_calibration_date": now - timedelta(days=20),
                "next_calibration_date": now + timedelta(days=160),
                "calibration_certificate_on_file": True,
                "maintenance_contract_active": True,
                "meets_protocol_requirements": True,
                "verified_by": "Tech. Anna Kowalski",
                "verification_date": now - timedelta(days=55),
                "notes": None,
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "EV-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-303",
                "equipment_name": "Hospira Plum A+ Infusion System",
                "equipment_type": "Infusion",
                "serial_number": "HPA-8891",
                "manufacturer": "ICU Medical",
                "status": EquipmentStatus.NEEDS_CALIBRATION,
                "last_calibration_date": now - timedelta(days=185),
                "next_calibration_date": now - timedelta(days=5),
                "calibration_certificate_on_file": True,
                "maintenance_contract_active": True,
                "meets_protocol_requirements": False,
                "verified_by": "Tech. Robert Chen",
                "verification_date": now - timedelta(days=25),
                "notes": "Calibration overdue by 5 days. Scheduled for next week.",
                "created_at": now - timedelta(days=25),
            },
        ]

        for e in equipment_data:
            self._equipment_verifications[e["id"]] = EquipmentVerification(**e)

        # --- 12 Staff Credentials ---
        credentials_data = [
            {
                "id": "SC-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "staff_name": "Dr. Jonathan Blake",
                "role": "Principal Investigator",
                "credential_type": CredentialType.MEDICAL_LICENSE,
                "credential_number": "MD-NY-2015-44892",
                "issuing_authority": "New York State Medical Board",
                "issue_date": now - timedelta(days=3650),
                "expiry_date": now + timedelta(days=400),
                "is_current": True,
                "verified": True,
                "verified_by": "Compliance Team",
                "verification_date": now - timedelta(days=170),
                "delegation_log_entry": True,
                "cv_on_file": True,
                "managed_by": "Dr. Rachel Green",
                "notes": "Board-certified ophthalmologist.",
                "created_at": now - timedelta(days=175),
            },
            {
                "id": "SC-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "staff_name": "Dr. Jonathan Blake",
                "role": "Principal Investigator",
                "credential_type": CredentialType.GCP_CERTIFICATION,
                "credential_number": "GCP-2024-BLK-001",
                "issuing_authority": "CITI Program",
                "issue_date": now - timedelta(days=365),
                "expiry_date": now + timedelta(days=365),
                "is_current": True,
                "verified": True,
                "verified_by": "Compliance Team",
                "verification_date": now - timedelta(days=170),
                "delegation_log_entry": True,
                "cv_on_file": True,
                "managed_by": "Dr. Rachel Green",
                "notes": None,
                "created_at": now - timedelta(days=175),
            },
            {
                "id": "SC-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "staff_name": "Dr. Emily Watson",
                "role": "Sub-Investigator",
                "credential_type": CredentialType.SPECIALTY_BOARD,
                "credential_number": "ABO-RET-2018-7721",
                "issuing_authority": "American Board of Ophthalmology",
                "issue_date": now - timedelta(days=2000),
                "expiry_date": now + timedelta(days=200),
                "is_current": True,
                "verified": True,
                "verified_by": "Compliance Team",
                "verification_date": now - timedelta(days=160),
                "delegation_log_entry": True,
                "cv_on_file": True,
                "managed_by": "Dr. Rachel Green",
                "notes": "Retinal specialist.",
                "created_at": now - timedelta(days=165),
            },
            {
                "id": "SC-004",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-201",
                "staff_name": "Dr. Patricia Nguyen",
                "role": "Principal Investigator",
                "credential_type": CredentialType.MEDICAL_LICENSE,
                "credential_number": "MD-CA-2012-33561",
                "issuing_authority": "California Medical Board",
                "issue_date": now - timedelta(days=4500),
                "expiry_date": now + timedelta(days=250),
                "is_current": True,
                "verified": True,
                "verified_by": "Compliance Team",
                "verification_date": now - timedelta(days=145),
                "delegation_log_entry": True,
                "cv_on_file": True,
                "managed_by": "Dr. Lisa Chang",
                "notes": "Board-certified dermatologist.",
                "created_at": now - timedelta(days=148),
            },
            {
                "id": "SC-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-201",
                "staff_name": "Sarah Mitchell, RN",
                "role": "Research Coordinator",
                "credential_type": CredentialType.RESEARCH_TRAINING,
                "credential_number": "ACRP-CCRC-2023-SM",
                "issuing_authority": "ACRP",
                "issue_date": now - timedelta(days=500),
                "expiry_date": now + timedelta(days=230),
                "is_current": True,
                "verified": True,
                "verified_by": "Compliance Team",
                "verification_date": now - timedelta(days=142),
                "delegation_log_entry": True,
                "cv_on_file": True,
                "managed_by": "Dr. Lisa Chang",
                "notes": "Certified Clinical Research Coordinator.",
                "created_at": now - timedelta(days=148),
            },
            {
                "id": "SC-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-202",
                "staff_name": "Dr. Kevin O'Brien",
                "role": "Principal Investigator",
                "credential_type": CredentialType.GCP_CERTIFICATION,
                "credential_number": "GCP-2022-KOB-003",
                "issuing_authority": "Barnett International",
                "issue_date": now - timedelta(days=800),
                "expiry_date": now - timedelta(days=70),
                "is_current": False,
                "verified": True,
                "verified_by": "Compliance Team",
                "verification_date": now - timedelta(days=135),
                "delegation_log_entry": True,
                "cv_on_file": True,
                "managed_by": "Dr. Lisa Chang",
                "notes": "GCP certification expired. Renewal pending.",
                "created_at": now - timedelta(days=140),
            },
            {
                "id": "SC-007",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-301",
                "staff_name": "Dr. Marcus Reed",
                "role": "Principal Investigator",
                "credential_type": CredentialType.MEDICAL_LICENSE,
                "credential_number": "MD-TX-2010-22190",
                "issuing_authority": "Texas Medical Board",
                "issue_date": now - timedelta(days=5000),
                "expiry_date": now + timedelta(days=600),
                "is_current": True,
                "verified": True,
                "verified_by": "Compliance Team",
                "verification_date": now - timedelta(days=108),
                "delegation_log_entry": True,
                "cv_on_file": True,
                "managed_by": "Dr. Angela Park",
                "notes": "Medical oncologist, 15+ years IO experience.",
                "created_at": now - timedelta(days=115),
            },
            {
                "id": "SC-008",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-301",
                "staff_name": "Dr. Marcus Reed",
                "role": "Principal Investigator",
                "credential_type": CredentialType.DEA_REGISTRATION,
                "credential_number": "DEA-MR-5544321",
                "issuing_authority": "US DEA",
                "issue_date": now - timedelta(days=700),
                "expiry_date": now + timedelta(days=400),
                "is_current": True,
                "verified": True,
                "verified_by": "Compliance Team",
                "verification_date": now - timedelta(days=108),
                "delegation_log_entry": False,
                "cv_on_file": True,
                "managed_by": "Dr. Angela Park",
                "notes": None,
                "created_at": now - timedelta(days=115),
            },
            {
                "id": "SC-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-302",
                "staff_name": "Dr. Helen Cho",
                "role": "Sub-Investigator",
                "credential_type": CredentialType.INSTITUTIONAL_APPROVAL,
                "credential_number": "IRB-302-2024-HC",
                "issuing_authority": "Site 302 IRB",
                "issue_date": now - timedelta(days=100),
                "expiry_date": now + timedelta(days=265),
                "is_current": True,
                "verified": True,
                "verified_by": "Compliance Team",
                "verification_date": now - timedelta(days=95),
                "delegation_log_entry": True,
                "cv_on_file": True,
                "managed_by": "Dr. Angela Park",
                "notes": "IRB approval for sub-investigator role.",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "SC-010",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-103",
                "staff_name": "Dr. Alan Foster",
                "role": "Principal Investigator",
                "credential_type": CredentialType.GCP_CERTIFICATION,
                "credential_number": "GCP-2023-AF-009",
                "issuing_authority": "CITI Program",
                "issue_date": now - timedelta(days=600),
                "expiry_date": now - timedelta(days=235),
                "is_current": False,
                "verified": False,
                "verified_by": None,
                "verification_date": None,
                "delegation_log_entry": False,
                "cv_on_file": False,
                "managed_by": "Dr. Rachel Green",
                "notes": "GCP expired. CV not yet received. Pending.",
                "created_at": now - timedelta(days=88),
            },
            {
                "id": "SC-011",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-203",
                "staff_name": "Dr. Jennifer Lee",
                "role": "Principal Investigator",
                "credential_type": CredentialType.SPECIALTY_BOARD,
                "credential_number": "ABD-2019-JL-441",
                "issuing_authority": "American Board of Dermatology",
                "issue_date": now - timedelta(days=1800),
                "expiry_date": now + timedelta(days=700),
                "is_current": True,
                "verified": True,
                "verified_by": "Compliance Team",
                "verification_date": now - timedelta(days=50),
                "delegation_log_entry": True,
                "cv_on_file": True,
                "managed_by": "Dr. Lisa Chang",
                "notes": None,
                "created_at": now - timedelta(days=58),
            },
            {
                "id": "SC-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-303",
                "staff_name": "John Park, PharmD",
                "role": "Research Pharmacist",
                "credential_type": CredentialType.INSTITUTIONAL_APPROVAL,
                "credential_number": "PHARM-303-2024-JP",
                "issuing_authority": "Site 303 Pharmacy Board",
                "issue_date": now - timedelta(days=80),
                "expiry_date": now + timedelta(days=285),
                "is_current": True,
                "verified": True,
                "verified_by": "Compliance Team",
                "verification_date": now - timedelta(days=22),
                "delegation_log_entry": True,
                "cv_on_file": True,
                "managed_by": "Dr. Angela Park",
                "notes": "Approved for hazardous drug handling.",
                "created_at": now - timedelta(days=28),
            },
        ]

        for c in credentials_data:
            self._staff_credentials[c["id"]] = StaffCredential(**c)

        # --- 12 Infrastructure Audits ---
        audits_data = [
            {
                "id": "IA-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "audit_date": now - timedelta(days=165),
                "audit_type": "pre_study",
                "rating": AuditRating.EXCELLENT,
                "pharmacy_adequate": True,
                "storage_adequate": True,
                "temperature_monitoring": True,
                "emergency_equipment": True,
                "source_document_storage": True,
                "patient_privacy_adequate": True,
                "it_infrastructure_adequate": True,
                "findings_count": 1,
                "critical_findings": 0,
                "corrective_actions_required": 1,
                "corrective_actions_completed": 1,
                "auditor": "Jane Smith, CQIA",
                "follow_up_date": None,
                "notes": "Minor labeling finding corrected on-site.",
                "created_at": now - timedelta(days=165),
            },
            {
                "id": "IA-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "audit_date": now - timedelta(days=155),
                "audit_type": "pre_study",
                "rating": AuditRating.SATISFACTORY,
                "pharmacy_adequate": True,
                "storage_adequate": True,
                "temperature_monitoring": True,
                "emergency_equipment": True,
                "source_document_storage": True,
                "patient_privacy_adequate": True,
                "it_infrastructure_adequate": False,
                "findings_count": 3,
                "critical_findings": 0,
                "corrective_actions_required": 2,
                "corrective_actions_completed": 2,
                "auditor": "Jane Smith, CQIA",
                "follow_up_date": now - timedelta(days=120),
                "notes": "IT network upgrade needed for EDC access.",
                "created_at": now - timedelta(days=155),
            },
            {
                "id": "IA-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-103",
                "audit_date": now - timedelta(days=80),
                "audit_type": "pre_study",
                "rating": AuditRating.UNSATISFACTORY,
                "pharmacy_adequate": False,
                "storage_adequate": False,
                "temperature_monitoring": False,
                "emergency_equipment": True,
                "source_document_storage": True,
                "patient_privacy_adequate": True,
                "it_infrastructure_adequate": True,
                "findings_count": 8,
                "critical_findings": 3,
                "corrective_actions_required": 6,
                "corrective_actions_completed": 1,
                "auditor": "Jane Smith, CQIA",
                "follow_up_date": now + timedelta(days=15),
                "notes": "No dedicated research pharmacy. Temp monitoring gaps.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "IA-004",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-201",
                "audit_date": now - timedelta(days=135),
                "audit_type": "pre_study",
                "rating": AuditRating.EXCELLENT,
                "pharmacy_adequate": True,
                "storage_adequate": True,
                "temperature_monitoring": True,
                "emergency_equipment": True,
                "source_document_storage": True,
                "patient_privacy_adequate": True,
                "it_infrastructure_adequate": True,
                "findings_count": 0,
                "critical_findings": 0,
                "corrective_actions_required": 0,
                "corrective_actions_completed": 0,
                "auditor": "Mark Thompson, CQA",
                "follow_up_date": None,
                "notes": "No findings. Exemplary site.",
                "created_at": now - timedelta(days=135),
            },
            {
                "id": "IA-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-202",
                "audit_date": now - timedelta(days=125),
                "audit_type": "pre_study",
                "rating": AuditRating.NEEDS_IMPROVEMENT,
                "pharmacy_adequate": True,
                "storage_adequate": True,
                "temperature_monitoring": True,
                "emergency_equipment": False,
                "source_document_storage": False,
                "patient_privacy_adequate": True,
                "it_infrastructure_adequate": True,
                "findings_count": 5,
                "critical_findings": 1,
                "corrective_actions_required": 4,
                "corrective_actions_completed": 2,
                "auditor": "Mark Thompson, CQA",
                "follow_up_date": now - timedelta(days=60),
                "notes": "Emergency equipment expired. Source doc storage inadequate.",
                "created_at": now - timedelta(days=125),
            },
            {
                "id": "IA-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-202",
                "audit_date": now - timedelta(days=55),
                "audit_type": "follow_up",
                "rating": AuditRating.SATISFACTORY,
                "pharmacy_adequate": True,
                "storage_adequate": True,
                "temperature_monitoring": True,
                "emergency_equipment": True,
                "source_document_storage": True,
                "patient_privacy_adequate": True,
                "it_infrastructure_adequate": True,
                "findings_count": 1,
                "critical_findings": 0,
                "corrective_actions_required": 0,
                "corrective_actions_completed": 0,
                "auditor": "Mark Thompson, CQA",
                "follow_up_date": None,
                "notes": "Follow-up audit. Previous findings resolved.",
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "IA-007",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-301",
                "audit_date": now - timedelta(days=105),
                "audit_type": "pre_study",
                "rating": AuditRating.EXCELLENT,
                "pharmacy_adequate": True,
                "storage_adequate": True,
                "temperature_monitoring": True,
                "emergency_equipment": True,
                "source_document_storage": True,
                "patient_privacy_adequate": True,
                "it_infrastructure_adequate": True,
                "findings_count": 0,
                "critical_findings": 0,
                "corrective_actions_required": 0,
                "corrective_actions_completed": 0,
                "auditor": "Laura Kim, Senior Auditor",
                "follow_up_date": None,
                "notes": "NCI-designated cancer center. Exemplary facilities.",
                "created_at": now - timedelta(days=105),
            },
            {
                "id": "IA-008",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-302",
                "audit_date": now - timedelta(days=95),
                "audit_type": "pre_study",
                "rating": AuditRating.SATISFACTORY,
                "pharmacy_adequate": True,
                "storage_adequate": True,
                "temperature_monitoring": True,
                "emergency_equipment": True,
                "source_document_storage": True,
                "patient_privacy_adequate": False,
                "it_infrastructure_adequate": True,
                "findings_count": 2,
                "critical_findings": 0,
                "corrective_actions_required": 1,
                "corrective_actions_completed": 1,
                "auditor": "Laura Kim, Senior Auditor",
                "follow_up_date": None,
                "notes": "Privacy curtain installation required in infusion area.",
                "created_at": now - timedelta(days=95),
            },
            {
                "id": "IA-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-303",
                "audit_date": now - timedelta(days=20),
                "audit_type": "pre_study",
                "rating": AuditRating.NEEDS_IMPROVEMENT,
                "pharmacy_adequate": True,
                "storage_adequate": False,
                "temperature_monitoring": True,
                "emergency_equipment": True,
                "source_document_storage": True,
                "patient_privacy_adequate": True,
                "it_infrastructure_adequate": False,
                "findings_count": 4,
                "critical_findings": 1,
                "corrective_actions_required": 3,
                "corrective_actions_completed": 0,
                "auditor": "Laura Kim, Senior Auditor",
                "follow_up_date": now + timedelta(days=40),
                "notes": "Inadequate drug storage capacity. Network bandwidth insufficient.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "IA-010",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "audit_date": now - timedelta(days=40),
                "audit_type": "routine",
                "rating": AuditRating.EXCELLENT,
                "pharmacy_adequate": True,
                "storage_adequate": True,
                "temperature_monitoring": True,
                "emergency_equipment": True,
                "source_document_storage": True,
                "patient_privacy_adequate": True,
                "it_infrastructure_adequate": True,
                "findings_count": 0,
                "critical_findings": 0,
                "corrective_actions_required": 0,
                "corrective_actions_completed": 0,
                "auditor": "Jane Smith, CQIA",
                "follow_up_date": None,
                "notes": "Routine monitoring visit. No findings.",
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "IA-011",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-203",
                "audit_date": now - timedelta(days=50),
                "audit_type": "pre_study",
                "rating": AuditRating.SATISFACTORY,
                "pharmacy_adequate": True,
                "storage_adequate": True,
                "temperature_monitoring": True,
                "emergency_equipment": True,
                "source_document_storage": True,
                "patient_privacy_adequate": True,
                "it_infrastructure_adequate": True,
                "findings_count": 2,
                "critical_findings": 0,
                "corrective_actions_required": 1,
                "corrective_actions_completed": 1,
                "auditor": "Mark Thompson, CQA",
                "follow_up_date": None,
                "notes": "Minor documentation filing issue. Corrected.",
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "IA-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-301",
                "audit_date": now - timedelta(days=10),
                "audit_type": "for_cause",
                "rating": AuditRating.CRITICAL,
                "pharmacy_adequate": True,
                "storage_adequate": True,
                "temperature_monitoring": False,
                "emergency_equipment": True,
                "source_document_storage": True,
                "patient_privacy_adequate": True,
                "it_infrastructure_adequate": True,
                "findings_count": 3,
                "critical_findings": 2,
                "corrective_actions_required": 2,
                "corrective_actions_completed": 0,
                "auditor": "Laura Kim, Senior Auditor",
                "follow_up_date": now + timedelta(days=20),
                "notes": "Temperature excursion event in IP storage. Immediate remediation required.",
                "created_at": now - timedelta(days=10),
            },
        ]

        for au in audits_data:
            self._infrastructure_audits[au["id"]] = InfrastructureAudit(**au)

        # --- 12 Qualification Records ---
        qualifications_data = [
            {
                "id": "QR-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "qualification_status": QualificationStatus.QUALIFIED,
                "overall_score": 85.0,
                "capability_score": 88.0,
                "equipment_score": 92.0,
                "staff_score": 90.0,
                "infrastructure_score": 95.0,
                "qualification_date": now - timedelta(days=150),
                "expiry_date": now + timedelta(days=215),
                "conditions": [],
                "conditions_met": 0,
                "risk_tier": "low",
                "qualified_by": "Dr. Rachel Green",
                "approved_by": "Dr. Michael Torres",
                "notes": "Fully qualified. Top-performing site.",
                "created_at": now - timedelta(days=155),
            },
            {
                "id": "QR-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "qualification_status": QualificationStatus.CONDITIONALLY_QUALIFIED,
                "overall_score": 78.0,
                "capability_score": 92.0,
                "equipment_score": 65.0,
                "staff_score": 80.0,
                "infrastructure_score": 75.0,
                "qualification_date": now - timedelta(days=140),
                "expiry_date": now + timedelta(days=225),
                "conditions": ["Complete OCT calibration", "IT network upgrade"],
                "conditions_met": 1,
                "risk_tier": "medium",
                "qualified_by": "Dr. Rachel Green",
                "approved_by": "Dr. Michael Torres",
                "notes": "Conditional on equipment calibration completion.",
                "created_at": now - timedelta(days=145),
            },
            {
                "id": "QR-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-103",
                "qualification_status": QualificationStatus.NOT_QUALIFIED,
                "overall_score": 48.0,
                "capability_score": 55.0,
                "equipment_score": 30.0,
                "staff_score": 40.0,
                "infrastructure_score": 45.0,
                "qualification_date": None,
                "expiry_date": None,
                "conditions": [],
                "conditions_met": 0,
                "risk_tier": "high",
                "qualified_by": None,
                "approved_by": None,
                "notes": "Does not meet minimum requirements. Re-assess in 6 months.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "QR-004",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-201",
                "qualification_status": QualificationStatus.QUALIFIED,
                "overall_score": 88.0,
                "capability_score": 82.0,
                "equipment_score": 95.0,
                "staff_score": 88.0,
                "infrastructure_score": 98.0,
                "qualification_date": now - timedelta(days=125),
                "expiry_date": now + timedelta(days=240),
                "conditions": [],
                "conditions_met": 0,
                "risk_tier": "low",
                "qualified_by": "Dr. Lisa Chang",
                "approved_by": "Dr. David Patel",
                "notes": "Exemplary site. No conditions.",
                "created_at": now - timedelta(days=130),
            },
            {
                "id": "QR-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-202",
                "qualification_status": QualificationStatus.IN_ASSESSMENT,
                "overall_score": 60.0,
                "capability_score": 65.0,
                "equipment_score": 50.0,
                "staff_score": 55.0,
                "infrastructure_score": 70.0,
                "qualification_date": None,
                "expiry_date": None,
                "conditions": ["PI GCP renewal", "Equipment repair", "Staff training", "Emergency equipment update"],
                "conditions_met": 2,
                "risk_tier": "high",
                "qualified_by": None,
                "approved_by": None,
                "notes": "Multiple remediation items in progress.",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "QR-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-203",
                "qualification_status": QualificationStatus.QUALIFIED,
                "overall_score": 83.0,
                "capability_score": 85.0,
                "equipment_score": 90.0,
                "staff_score": 82.0,
                "infrastructure_score": 80.0,
                "qualification_date": now - timedelta(days=45),
                "expiry_date": now + timedelta(days=320),
                "conditions": [],
                "conditions_met": 0,
                "risk_tier": "low",
                "qualified_by": "Dr. Lisa Chang",
                "approved_by": "Dr. David Patel",
                "notes": None,
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "QR-007",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-301",
                "qualification_status": QualificationStatus.QUALIFIED,
                "overall_score": 94.0,
                "capability_score": 95.0,
                "equipment_score": 98.0,
                "staff_score": 92.0,
                "infrastructure_score": 98.0,
                "qualification_date": now - timedelta(days=100),
                "expiry_date": now + timedelta(days=265),
                "conditions": [],
                "conditions_met": 0,
                "risk_tier": "low",
                "qualified_by": "Dr. Angela Park",
                "approved_by": "Dr. William Torres",
                "notes": "NCI-designated center. Highest qualification score.",
                "created_at": now - timedelta(days=105),
            },
            {
                "id": "QR-008",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-302",
                "qualification_status": QualificationStatus.CONDITIONALLY_QUALIFIED,
                "overall_score": 74.0,
                "capability_score": 70.0,
                "equipment_score": 60.0,
                "staff_score": 78.0,
                "infrastructure_score": 80.0,
                "qualification_date": now - timedelta(days=85),
                "expiry_date": now + timedelta(days=280),
                "conditions": ["Replace out-of-service infusion pump", "Privacy curtain installation"],
                "conditions_met": 1,
                "risk_tier": "medium",
                "qualified_by": "Dr. Angela Park",
                "approved_by": "Dr. William Torres",
                "notes": "Conditional on equipment replacement.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "QR-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-303",
                "qualification_status": QualificationStatus.PENDING_ASSESSMENT,
                "overall_score": 0.0,
                "capability_score": 0.0,
                "equipment_score": 0.0,
                "staff_score": 0.0,
                "infrastructure_score": 0.0,
                "qualification_date": None,
                "expiry_date": None,
                "conditions": [],
                "conditions_met": 0,
                "risk_tier": "medium",
                "qualified_by": None,
                "approved_by": None,
                "notes": "New site. Assessment not yet started.",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "QR-010",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-104",
                "qualification_status": QualificationStatus.SUSPENDED,
                "overall_score": 72.0,
                "capability_score": 75.0,
                "equipment_score": 68.0,
                "staff_score": 70.0,
                "infrastructure_score": 75.0,
                "qualification_date": now - timedelta(days=200),
                "expiry_date": now + timedelta(days=165),
                "conditions": ["Resolve protocol deviation", "Retrain study staff"],
                "conditions_met": 0,
                "risk_tier": "high",
                "qualified_by": "Dr. Rachel Green",
                "approved_by": "Dr. Michael Torres",
                "notes": "Suspended due to repeated protocol deviations.",
                "created_at": now - timedelta(days=205),
            },
            {
                "id": "QR-011",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-204",
                "qualification_status": QualificationStatus.PENDING_ASSESSMENT,
                "overall_score": 0.0,
                "capability_score": 0.0,
                "equipment_score": 0.0,
                "staff_score": 0.0,
                "infrastructure_score": 0.0,
                "qualification_date": None,
                "expiry_date": None,
                "conditions": [],
                "conditions_met": 0,
                "risk_tier": "medium",
                "qualified_by": None,
                "approved_by": None,
                "notes": "Prospective site. Screening visit planned.",
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "QR-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-304",
                "qualification_status": QualificationStatus.IN_ASSESSMENT,
                "overall_score": 45.0,
                "capability_score": 50.0,
                "equipment_score": 40.0,
                "staff_score": 45.0,
                "infrastructure_score": 42.0,
                "qualification_date": None,
                "expiry_date": None,
                "conditions": [],
                "conditions_met": 0,
                "risk_tier": "high",
                "qualified_by": None,
                "approved_by": None,
                "notes": "Early assessment. Low scores across categories.",
                "created_at": now - timedelta(days=8),
            },
        ]

        for q in qualifications_data:
            self._qualification_records[q["id"]] = QualificationRecord(**q)

    # ------------------------------------------------------------------
    # Capability Assessments
    # ------------------------------------------------------------------

    def list_capability_assessments(
        self,
        *,
        trial_id: str | None = None,
        site_id: str | None = None,
        category: AssessmentCategory | None = None,
    ) -> list[CapabilityAssessment]:
        """List capability assessments with optional filters."""
        with self._lock:
            result = list(self._capability_assessments.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if site_id is not None:
            result = [a for a in result if a.site_id == site_id]
        if category is not None:
            result = [a for a in result if a.category == category]

        return sorted(result, key=lambda a: a.assessment_date, reverse=True)

    def get_capability_assessment(self, assessment_id: str) -> CapabilityAssessment | None:
        """Get a single capability assessment by ID."""
        with self._lock:
            return self._capability_assessments.get(assessment_id)

    def create_capability_assessment(self, payload: CapabilityAssessmentCreate) -> CapabilityAssessment:
        """Create a new capability assessment."""
        now = datetime.now(timezone.utc)
        assessment_id = f"CA-{uuid4().hex[:8].upper()}"
        assessment = CapabilityAssessment(
            id=assessment_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            category=payload.category,
            assessment_date=now,
            score=payload.score,
            max_score=100.0,
            pass_threshold=payload.pass_threshold,
            passed=payload.score >= payload.pass_threshold,
            prior_trial_count=0,
            therapeutic_area_experience=False,
            patient_pool_estimate=0,
            competing_trials=0,
            findings=[],
            assessor=payload.assessor,
            reviewer=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._capability_assessments[assessment_id] = assessment
        logger.info("Created capability assessment %s for trial %s", assessment_id, payload.trial_id)
        return assessment

    def update_capability_assessment(
        self, assessment_id: str, payload: CapabilityAssessmentUpdate
    ) -> CapabilityAssessment | None:
        """Update an existing capability assessment."""
        with self._lock:
            existing = self._capability_assessments.get(assessment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CapabilityAssessment(**data)
            self._capability_assessments[assessment_id] = updated
        return updated

    def delete_capability_assessment(self, assessment_id: str) -> bool:
        """Delete a capability assessment. Returns True if deleted."""
        with self._lock:
            if assessment_id in self._capability_assessments:
                del self._capability_assessments[assessment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Equipment Verifications
    # ------------------------------------------------------------------

    def list_equipment_verifications(
        self,
        *,
        trial_id: str | None = None,
        site_id: str | None = None,
        status: EquipmentStatus | None = None,
    ) -> list[EquipmentVerification]:
        """List equipment verifications with optional filters."""
        with self._lock:
            result = list(self._equipment_verifications.values())

        if trial_id is not None:
            result = [e for e in result if e.trial_id == trial_id]
        if site_id is not None:
            result = [e for e in result if e.site_id == site_id]
        if status is not None:
            result = [e for e in result if e.status == status]

        return sorted(result, key=lambda e: e.verification_date, reverse=True)

    def get_equipment_verification(self, verification_id: str) -> EquipmentVerification | None:
        """Get a single equipment verification by ID."""
        with self._lock:
            return self._equipment_verifications.get(verification_id)

    def create_equipment_verification(self, payload: EquipmentVerificationCreate) -> EquipmentVerification:
        """Create a new equipment verification."""
        now = datetime.now(timezone.utc)
        verification_id = f"EV-{uuid4().hex[:8].upper()}"
        verification = EquipmentVerification(
            id=verification_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            equipment_name=payload.equipment_name,
            equipment_type=payload.equipment_type,
            serial_number=None,
            manufacturer=None,
            status=payload.status,
            last_calibration_date=None,
            next_calibration_date=None,
            calibration_certificate_on_file=False,
            maintenance_contract_active=False,
            meets_protocol_requirements=True,
            verified_by=payload.verified_by,
            verification_date=now,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._equipment_verifications[verification_id] = verification
        logger.info("Created equipment verification %s for trial %s", verification_id, payload.trial_id)
        return verification

    def update_equipment_verification(
        self, verification_id: str, payload: EquipmentVerificationUpdate
    ) -> EquipmentVerification | None:
        """Update an existing equipment verification."""
        with self._lock:
            existing = self._equipment_verifications.get(verification_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = EquipmentVerification(**data)
            self._equipment_verifications[verification_id] = updated
        return updated

    def delete_equipment_verification(self, verification_id: str) -> bool:
        """Delete an equipment verification. Returns True if deleted."""
        with self._lock:
            if verification_id in self._equipment_verifications:
                del self._equipment_verifications[verification_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Staff Credentials
    # ------------------------------------------------------------------

    def list_staff_credentials(
        self,
        *,
        trial_id: str | None = None,
        site_id: str | None = None,
        credential_type: CredentialType | None = None,
    ) -> list[StaffCredential]:
        """List staff credentials with optional filters."""
        with self._lock:
            result = list(self._staff_credentials.values())

        if trial_id is not None:
            result = [c for c in result if c.trial_id == trial_id]
        if site_id is not None:
            result = [c for c in result if c.site_id == site_id]
        if credential_type is not None:
            result = [c for c in result if c.credential_type == credential_type]

        return sorted(result, key=lambda c: c.created_at, reverse=True)

    def get_staff_credential(self, credential_id: str) -> StaffCredential | None:
        """Get a single staff credential by ID."""
        with self._lock:
            return self._staff_credentials.get(credential_id)

    def create_staff_credential(self, payload: StaffCredentialCreate) -> StaffCredential:
        """Create a new staff credential."""
        now = datetime.now(timezone.utc)
        credential_id = f"SC-{uuid4().hex[:8].upper()}"
        credential = StaffCredential(
            id=credential_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            staff_name=payload.staff_name,
            role=payload.role,
            credential_type=payload.credential_type,
            credential_number=None,
            issuing_authority=payload.issuing_authority,
            issue_date=now,
            expiry_date=None,
            is_current=True,
            verified=False,
            verified_by=None,
            verification_date=None,
            delegation_log_entry=False,
            cv_on_file=False,
            managed_by=payload.managed_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._staff_credentials[credential_id] = credential
        logger.info("Created staff credential %s for trial %s", credential_id, payload.trial_id)
        return credential

    def update_staff_credential(
        self, credential_id: str, payload: StaffCredentialUpdate
    ) -> StaffCredential | None:
        """Update an existing staff credential."""
        with self._lock:
            existing = self._staff_credentials.get(credential_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = StaffCredential(**data)
            self._staff_credentials[credential_id] = updated
        return updated

    def delete_staff_credential(self, credential_id: str) -> bool:
        """Delete a staff credential. Returns True if deleted."""
        with self._lock:
            if credential_id in self._staff_credentials:
                del self._staff_credentials[credential_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Infrastructure Audits
    # ------------------------------------------------------------------

    def list_infrastructure_audits(
        self,
        *,
        trial_id: str | None = None,
        site_id: str | None = None,
        rating: AuditRating | None = None,
    ) -> list[InfrastructureAudit]:
        """List infrastructure audits with optional filters."""
        with self._lock:
            result = list(self._infrastructure_audits.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if site_id is not None:
            result = [a for a in result if a.site_id == site_id]
        if rating is not None:
            result = [a for a in result if a.rating == rating]

        return sorted(result, key=lambda a: a.audit_date, reverse=True)

    def get_infrastructure_audit(self, audit_id: str) -> InfrastructureAudit | None:
        """Get a single infrastructure audit by ID."""
        with self._lock:
            return self._infrastructure_audits.get(audit_id)

    def create_infrastructure_audit(self, payload: InfrastructureAuditCreate) -> InfrastructureAudit:
        """Create a new infrastructure audit."""
        now = datetime.now(timezone.utc)
        audit_id = f"IA-{uuid4().hex[:8].upper()}"
        audit = InfrastructureAudit(
            id=audit_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            audit_date=now,
            audit_type=payload.audit_type,
            rating=payload.rating,
            pharmacy_adequate=True,
            storage_adequate=True,
            temperature_monitoring=True,
            emergency_equipment=True,
            source_document_storage=True,
            patient_privacy_adequate=True,
            it_infrastructure_adequate=True,
            findings_count=0,
            critical_findings=0,
            corrective_actions_required=0,
            corrective_actions_completed=0,
            auditor=payload.auditor,
            follow_up_date=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._infrastructure_audits[audit_id] = audit
        logger.info("Created infrastructure audit %s for trial %s", audit_id, payload.trial_id)
        return audit

    def update_infrastructure_audit(
        self, audit_id: str, payload: InfrastructureAuditUpdate
    ) -> InfrastructureAudit | None:
        """Update an existing infrastructure audit."""
        with self._lock:
            existing = self._infrastructure_audits.get(audit_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = InfrastructureAudit(**data)
            self._infrastructure_audits[audit_id] = updated
        return updated

    def delete_infrastructure_audit(self, audit_id: str) -> bool:
        """Delete an infrastructure audit. Returns True if deleted."""
        with self._lock:
            if audit_id in self._infrastructure_audits:
                del self._infrastructure_audits[audit_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Qualification Records
    # ------------------------------------------------------------------

    def list_qualification_records(
        self,
        *,
        trial_id: str | None = None,
        site_id: str | None = None,
        qualification_status: QualificationStatus | None = None,
    ) -> list[QualificationRecord]:
        """List qualification records with optional filters."""
        with self._lock:
            result = list(self._qualification_records.values())

        if trial_id is not None:
            result = [q for q in result if q.trial_id == trial_id]
        if site_id is not None:
            result = [q for q in result if q.site_id == site_id]
        if qualification_status is not None:
            result = [q for q in result if q.qualification_status == qualification_status]

        return sorted(result, key=lambda q: q.created_at, reverse=True)

    def get_qualification_record(self, record_id: str) -> QualificationRecord | None:
        """Get a single qualification record by ID."""
        with self._lock:
            return self._qualification_records.get(record_id)

    def create_qualification_record(self, payload: QualificationRecordCreate) -> QualificationRecord:
        """Create a new qualification record."""
        now = datetime.now(timezone.utc)
        record_id = f"QR-{uuid4().hex[:8].upper()}"
        record = QualificationRecord(
            id=record_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            qualification_status=QualificationStatus.PENDING_ASSESSMENT,
            overall_score=0.0,
            capability_score=0.0,
            equipment_score=0.0,
            staff_score=0.0,
            infrastructure_score=0.0,
            qualification_date=None,
            expiry_date=None,
            conditions=payload.conditions,
            conditions_met=0,
            risk_tier=payload.risk_tier,
            qualified_by=payload.qualified_by,
            approved_by=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._qualification_records[record_id] = record
        logger.info("Created qualification record %s for trial %s", record_id, payload.trial_id)
        return record

    def update_qualification_record(
        self, record_id: str, payload: QualificationRecordUpdate
    ) -> QualificationRecord | None:
        """Update an existing qualification record."""
        with self._lock:
            existing = self._qualification_records.get(record_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = QualificationRecord(**data)
            self._qualification_records[record_id] = updated
        return updated

    def delete_qualification_record(self, record_id: str) -> bool:
        """Delete a qualification record. Returns True if deleted."""
        with self._lock:
            if record_id in self._qualification_records:
                del self._qualification_records[record_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> SiteQualificationMetrics:
        """Compute aggregated site qualification metrics."""
        with self._lock:
            assessments = list(self._capability_assessments.values())
            equipment = list(self._equipment_verifications.values())
            credentials = list(self._staff_credentials.values())
            audits = list(self._infrastructure_audits.values())
            qualifications = list(self._qualification_records.values())

        now = datetime.now(timezone.utc)

        # Assessments by category
        assessments_by_category: dict[str, int] = {}
        for a in assessments:
            key = a.category.value
            assessments_by_category[key] = assessments_by_category.get(key, 0) + 1

        # Average assessment score
        scores = [a.score for a in assessments]
        avg_score = round(sum(scores) / max(1, len(scores)), 1) if scores else 0.0

        # Equipment by status
        equipment_by_status: dict[str, int] = {}
        for e in equipment:
            key = e.status.value
            equipment_by_status[key] = equipment_by_status.get(key, 0) + 1

        # Credentials by type
        credentials_by_type: dict[str, int] = {}
        for c in credentials:
            key = c.credential_type.value
            credentials_by_type[key] = credentials_by_type.get(key, 0) + 1

        # Expired credentials
        expired = sum(
            1
            for c in credentials
            if c.expiry_date is not None and c.expiry_date < now
        )

        # Audits by rating
        audits_by_rating: dict[str, int] = {}
        for a in audits:
            key = a.rating.value
            audits_by_rating[key] = audits_by_rating.get(key, 0) + 1

        # Qualifications by status
        qualifications_by_status: dict[str, int] = {}
        for q in qualifications:
            key = q.qualification_status.value
            qualifications_by_status[key] = qualifications_by_status.get(key, 0) + 1

        # Sites qualified
        sites_qualified = sum(
            1
            for q in qualifications
            if q.qualification_status == QualificationStatus.QUALIFIED
        )

        return SiteQualificationMetrics(
            total_assessments=len(assessments),
            assessments_by_category=assessments_by_category,
            avg_assessment_score=avg_score,
            total_equipment=len(equipment),
            equipment_by_status=equipment_by_status,
            total_credentials=len(credentials),
            credentials_by_type=credentials_by_type,
            expired_credentials=expired,
            total_audits=len(audits),
            audits_by_rating=audits_by_rating,
            total_qualifications=len(qualifications),
            qualifications_by_status=qualifications_by_status,
            sites_qualified=sites_qualified,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: SiteQualificationService | None = None
_instance_lock = threading.Lock()


def get_site_qualification_service() -> SiteQualificationService:
    """Return the singleton SiteQualificationService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = SiteQualificationService()
    return _instance


def reset_site_qualification_service() -> SiteQualificationService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = SiteQualificationService()
    return _instance
