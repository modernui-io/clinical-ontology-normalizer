"""Lab Proficiency Service (LAB-PROF).

Manages laboratory proficiency operations: proficiency test tracking, inter-lab
comparison results, accreditation records, lab corrective actions, and
proficiency metrics.

Usage:
    from app.services.lab_proficiency_service import (
        get_lab_proficiency_service,
    )

    svc = get_lab_proficiency_service()
    tests = svc.list_proficiency_tests()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.lab_proficiency import (
    AccreditationRecord,
    AccreditationRecordCreate,
    AccreditationRecordUpdate,
    AccreditationStatus,
    ComparisonStatus,
    CorrectiveActionPriority,
    LabComparison,
    LabComparisonCreate,
    LabComparisonUpdate,
    LabCorrectiveAction,
    LabCorrectiveActionCreate,
    LabCorrectiveActionUpdate,
    LabProficiencyMetrics,
    ProficiencyTest,
    ProficiencyTestCreate,
    ProficiencyTestUpdate,
    TestCategory,
    TestResult,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class LabProficiencyService:
    """In-memory Lab Proficiency engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._proficiency_tests: dict[str, ProficiencyTest] = {}
        self._lab_comparisons: dict[str, LabComparison] = {}
        self._accreditation_records: dict[str, AccreditationRecord] = {}
        self._corrective_actions: dict[str, LabCorrectiveAction] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic lab proficiency data."""
        now = datetime.now(timezone.utc)

        # --- 12 Proficiency Tests ---
        pt_data = [
            {
                "id": "PT-001",
                "trial_id": EYLEA_TRIAL,
                "lab_id": "LAB-NY-001",
                "lab_name": "NYC Central Lab",
                "test_category": TestCategory.CLINICAL_CHEMISTRY,
                "test_name": "Glucose Proficiency Panel",
                "test_result": TestResult.SATISFACTORY,
                "test_date": now - timedelta(days=90),
                "reporting_deadline": now - timedelta(days=75),
                "analyte_name": "Glucose",
                "reported_value": 98.5,
                "expected_value": 100.0,
                "acceptable_range_low": 90.0,
                "acceptable_range_high": 110.0,
                "z_score": -0.3,
                "pt_provider": "CAP",
                "cycle_number": "2025-C1",
                "notes": "Satisfactory performance on glucose panel.",
                "created_at": now - timedelta(days=91),
            },
            {
                "id": "PT-002",
                "trial_id": EYLEA_TRIAL,
                "lab_id": "LAB-NY-001",
                "lab_name": "NYC Central Lab",
                "test_category": TestCategory.HEMATOLOGY,
                "test_name": "CBC Proficiency Survey",
                "test_result": TestResult.SATISFACTORY,
                "test_date": now - timedelta(days=85),
                "reporting_deadline": now - timedelta(days=70),
                "analyte_name": "Hemoglobin",
                "reported_value": 14.2,
                "expected_value": 14.0,
                "acceptable_range_low": 13.0,
                "acceptable_range_high": 15.0,
                "z_score": 0.2,
                "pt_provider": "CAP",
                "cycle_number": "2025-C1",
                "notes": "All CBC parameters within expected ranges.",
                "created_at": now - timedelta(days=86),
            },
            {
                "id": "PT-003",
                "trial_id": EYLEA_TRIAL,
                "lab_id": "LAB-LA-001",
                "lab_name": "LA Reference Lab",
                "test_category": TestCategory.IMMUNOLOGY,
                "test_name": "VEGF ELISA Proficiency",
                "test_result": TestResult.UNSATISFACTORY,
                "test_date": now - timedelta(days=80),
                "reporting_deadline": now - timedelta(days=65),
                "analyte_name": "VEGF-A",
                "reported_value": 250.0,
                "expected_value": 180.0,
                "acceptable_range_low": 150.0,
                "acceptable_range_high": 210.0,
                "z_score": 3.5,
                "pt_provider": "EQAS",
                "cycle_number": "2025-Q1",
                "notes": "Unsatisfactory result. Corrective action required.",
                "created_at": now - timedelta(days=81),
            },
            {
                "id": "PT-004",
                "trial_id": EYLEA_TRIAL,
                "lab_id": "LAB-LA-001",
                "lab_name": "LA Reference Lab",
                "test_category": TestCategory.CLINICAL_CHEMISTRY,
                "test_name": "Lipid Panel Proficiency",
                "test_result": TestResult.MARGINAL,
                "test_date": now - timedelta(days=75),
                "reporting_deadline": now - timedelta(days=60),
                "analyte_name": "LDL Cholesterol",
                "reported_value": 132.0,
                "expected_value": 125.0,
                "acceptable_range_low": 112.5,
                "acceptable_range_high": 137.5,
                "z_score": 1.4,
                "pt_provider": "CAP",
                "cycle_number": "2025-C2",
                "notes": "Marginal result on LDL. Close monitoring recommended.",
                "created_at": now - timedelta(days=76),
            },
            {
                "id": "PT-005",
                "trial_id": DUPIXENT_TRIAL,
                "lab_id": "LAB-CHI-001",
                "lab_name": "Chicago Immunology Lab",
                "test_category": TestCategory.IMMUNOLOGY,
                "test_name": "IgE Quantitation Proficiency",
                "test_result": TestResult.SATISFACTORY,
                "test_date": now - timedelta(days=70),
                "reporting_deadline": now - timedelta(days=55),
                "analyte_name": "Total IgE",
                "reported_value": 450.0,
                "expected_value": 440.0,
                "acceptable_range_low": 396.0,
                "acceptable_range_high": 484.0,
                "z_score": 0.23,
                "pt_provider": "CAP",
                "cycle_number": "2025-C1",
                "notes": "Excellent IgE quantitation accuracy.",
                "created_at": now - timedelta(days=71),
            },
            {
                "id": "PT-006",
                "trial_id": DUPIXENT_TRIAL,
                "lab_id": "LAB-CHI-001",
                "lab_name": "Chicago Immunology Lab",
                "test_category": TestCategory.HEMATOLOGY,
                "test_name": "Eosinophil Count Proficiency",
                "test_result": TestResult.SATISFACTORY,
                "test_date": now - timedelta(days=65),
                "reporting_deadline": now - timedelta(days=50),
                "analyte_name": "Eosinophils",
                "reported_value": 0.35,
                "expected_value": 0.33,
                "acceptable_range_low": 0.26,
                "acceptable_range_high": 0.40,
                "z_score": 0.29,
                "pt_provider": "EQAS",
                "cycle_number": "2025-Q2",
                "notes": "Satisfactory eosinophil counting performance.",
                "created_at": now - timedelta(days=66),
            },
            {
                "id": "PT-007",
                "trial_id": DUPIXENT_TRIAL,
                "lab_id": "LAB-BOS-001",
                "lab_name": "Boston Clinical Lab",
                "test_category": TestCategory.MICROBIOLOGY,
                "test_name": "Skin Culture Identification",
                "test_result": TestResult.PENDING,
                "test_date": now - timedelta(days=10),
                "reporting_deadline": now + timedelta(days=5),
                "analyte_name": "S. aureus",
                "reported_value": None,
                "expected_value": None,
                "acceptable_range_low": None,
                "acceptable_range_high": None,
                "z_score": None,
                "pt_provider": "CAP",
                "cycle_number": "2025-C3",
                "notes": "Pending result submission.",
                "created_at": now - timedelta(days=11),
            },
            {
                "id": "PT-008",
                "trial_id": DUPIXENT_TRIAL,
                "lab_id": "LAB-BOS-001",
                "lab_name": "Boston Clinical Lab",
                "test_category": TestCategory.URINALYSIS,
                "test_name": "Urinalysis Proficiency",
                "test_result": TestResult.NOT_GRADED,
                "test_date": now - timedelta(days=60),
                "reporting_deadline": now - timedelta(days=45),
                "analyte_name": "Protein",
                "reported_value": 30.0,
                "expected_value": 30.0,
                "acceptable_range_low": 20.0,
                "acceptable_range_high": 40.0,
                "z_score": 0.0,
                "pt_provider": "EQAS",
                "cycle_number": "2025-Q1",
                "notes": "Grading waived due to insufficient participant data.",
                "created_at": now - timedelta(days=61),
            },
            {
                "id": "PT-009",
                "trial_id": LIBTAYO_TRIAL,
                "lab_id": "LAB-HOU-001",
                "lab_name": "Houston Oncology Lab",
                "test_category": TestCategory.IMMUNOLOGY,
                "test_name": "PD-L1 IHC Proficiency",
                "test_result": TestResult.SATISFACTORY,
                "test_date": now - timedelta(days=55),
                "reporting_deadline": now - timedelta(days=40),
                "analyte_name": "PD-L1",
                "reported_value": 52.0,
                "expected_value": 50.0,
                "acceptable_range_low": 40.0,
                "acceptable_range_high": 60.0,
                "z_score": 0.2,
                "pt_provider": "NordiQC",
                "cycle_number": "2025-R1",
                "notes": "PD-L1 scoring within acceptable range.",
                "created_at": now - timedelta(days=56),
            },
            {
                "id": "PT-010",
                "trial_id": LIBTAYO_TRIAL,
                "lab_id": "LAB-HOU-001",
                "lab_name": "Houston Oncology Lab",
                "test_category": TestCategory.MOLECULAR,
                "test_name": "TMB Assay Proficiency",
                "test_result": TestResult.SATISFACTORY,
                "test_date": now - timedelta(days=50),
                "reporting_deadline": now - timedelta(days=35),
                "analyte_name": "TMB",
                "reported_value": 12.5,
                "expected_value": 12.0,
                "acceptable_range_low": 9.6,
                "acceptable_range_high": 14.4,
                "z_score": 0.42,
                "pt_provider": "CAP",
                "cycle_number": "2025-C2",
                "notes": "TMB quantitation within expected range.",
                "created_at": now - timedelta(days=51),
            },
            {
                "id": "PT-011",
                "trial_id": LIBTAYO_TRIAL,
                "lab_id": "LAB-SEA-001",
                "lab_name": "Seattle Genomics Lab",
                "test_category": TestCategory.MOLECULAR,
                "test_name": "MSI Testing Proficiency",
                "test_result": TestResult.WITHDRAWN,
                "test_date": now - timedelta(days=45),
                "reporting_deadline": now - timedelta(days=30),
                "analyte_name": "MSI Status",
                "reported_value": None,
                "expected_value": None,
                "acceptable_range_low": None,
                "acceptable_range_high": None,
                "z_score": None,
                "pt_provider": "EQAS",
                "cycle_number": "2025-Q2",
                "notes": "Withdrawn due to instrument calibration issue.",
                "created_at": now - timedelta(days=46),
            },
            {
                "id": "PT-012",
                "trial_id": LIBTAYO_TRIAL,
                "lab_id": "LAB-SEA-001",
                "lab_name": "Seattle Genomics Lab",
                "test_category": TestCategory.CLINICAL_CHEMISTRY,
                "test_name": "Liver Function Panel",
                "test_result": TestResult.UNSATISFACTORY,
                "test_date": now - timedelta(days=40),
                "reporting_deadline": now - timedelta(days=25),
                "analyte_name": "ALT",
                "reported_value": 55.0,
                "expected_value": 35.0,
                "acceptable_range_low": 28.0,
                "acceptable_range_high": 42.0,
                "z_score": 4.0,
                "pt_provider": "CAP",
                "cycle_number": "2025-C2",
                "notes": "Significantly elevated ALT value. Investigation initiated.",
                "created_at": now - timedelta(days=41),
            },
        ]

        for pt in pt_data:
            self._proficiency_tests[pt["id"]] = ProficiencyTest(**pt)

        # --- 12 Lab Comparisons ---
        lc_data = [
            {
                "id": "LC-001",
                "trial_id": EYLEA_TRIAL,
                "reference_lab_id": "LAB-NY-001",
                "comparison_lab_id": "LAB-LA-001",
                "comparison_status": ComparisonStatus.COMPLETED,
                "analyte_name": "VEGF-A",
                "sample_count": 20,
                "mean_bias_pct": 2.5,
                "cv_pct": 5.3,
                "correlation_coefficient": 0.98,
                "within_tolerance": True,
                "tolerance_limit_pct": 15.0,
                "comparison_date": now - timedelta(days=80),
                "completed_date": now - timedelta(days=70),
                "reviewed_by": "Dr. Elena Voss",
                "notes": "Excellent inter-lab agreement for VEGF-A.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "LC-002",
                "trial_id": EYLEA_TRIAL,
                "reference_lab_id": "LAB-NY-001",
                "comparison_lab_id": "LAB-LA-001",
                "comparison_status": ComparisonStatus.COMPLETED,
                "analyte_name": "Anti-VEGF Antibody",
                "sample_count": 15,
                "mean_bias_pct": 8.2,
                "cv_pct": 12.1,
                "correlation_coefficient": 0.92,
                "within_tolerance": True,
                "tolerance_limit_pct": 15.0,
                "comparison_date": now - timedelta(days=75),
                "completed_date": now - timedelta(days=65),
                "reviewed_by": "Dr. Elena Voss",
                "notes": "Within tolerance but higher variability noted.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "LC-003",
                "trial_id": EYLEA_TRIAL,
                "reference_lab_id": "LAB-NY-001",
                "comparison_lab_id": "LAB-LA-001",
                "comparison_status": ComparisonStatus.FAILED,
                "analyte_name": "Serum Creatinine",
                "sample_count": 25,
                "mean_bias_pct": 18.5,
                "cv_pct": 20.3,
                "correlation_coefficient": 0.78,
                "within_tolerance": False,
                "tolerance_limit_pct": 15.0,
                "comparison_date": now - timedelta(days=70),
                "completed_date": now - timedelta(days=60),
                "reviewed_by": "Dr. Mark Phillips",
                "notes": "Failed comparison. Bias exceeds tolerance. Corrective action needed.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "LC-004",
                "trial_id": EYLEA_TRIAL,
                "reference_lab_id": "LAB-NY-001",
                "comparison_lab_id": "LAB-LA-001",
                "comparison_status": ComparisonStatus.SCHEDULED,
                "analyte_name": "HbA1c",
                "sample_count": 0,
                "mean_bias_pct": None,
                "cv_pct": None,
                "correlation_coefficient": None,
                "within_tolerance": None,
                "tolerance_limit_pct": 10.0,
                "comparison_date": now + timedelta(days=15),
                "completed_date": None,
                "reviewed_by": None,
                "notes": "Upcoming scheduled comparison.",
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "LC-005",
                "trial_id": DUPIXENT_TRIAL,
                "reference_lab_id": "LAB-CHI-001",
                "comparison_lab_id": "LAB-BOS-001",
                "comparison_status": ComparisonStatus.COMPLETED,
                "analyte_name": "Total IgE",
                "sample_count": 30,
                "mean_bias_pct": 3.1,
                "cv_pct": 6.8,
                "correlation_coefficient": 0.97,
                "within_tolerance": True,
                "tolerance_limit_pct": 15.0,
                "comparison_date": now - timedelta(days=65),
                "completed_date": now - timedelta(days=55),
                "reviewed_by": "Dr. Grace Lee",
                "notes": "Good agreement for IgE measurements.",
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "LC-006",
                "trial_id": DUPIXENT_TRIAL,
                "reference_lab_id": "LAB-CHI-001",
                "comparison_lab_id": "LAB-BOS-001",
                "comparison_status": ComparisonStatus.IN_PROGRESS,
                "analyte_name": "Eosinophil Count",
                "sample_count": 10,
                "mean_bias_pct": None,
                "cv_pct": None,
                "correlation_coefficient": None,
                "within_tolerance": None,
                "tolerance_limit_pct": 20.0,
                "comparison_date": now - timedelta(days=15),
                "completed_date": None,
                "reviewed_by": None,
                "notes": "Testing in progress. 10 of 20 samples analyzed.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "LC-007",
                "trial_id": DUPIXENT_TRIAL,
                "reference_lab_id": "LAB-CHI-001",
                "comparison_lab_id": "LAB-BOS-001",
                "comparison_status": ComparisonStatus.COMPLETED,
                "analyte_name": "TARC/CCL17",
                "sample_count": 18,
                "mean_bias_pct": 5.5,
                "cv_pct": 9.2,
                "correlation_coefficient": 0.95,
                "within_tolerance": True,
                "tolerance_limit_pct": 15.0,
                "comparison_date": now - timedelta(days=50),
                "completed_date": now - timedelta(days=40),
                "reviewed_by": "Dr. Grace Lee",
                "notes": "Acceptable TARC comparison results.",
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "LC-008",
                "trial_id": DUPIXENT_TRIAL,
                "reference_lab_id": "LAB-CHI-001",
                "comparison_lab_id": "LAB-BOS-001",
                "comparison_status": ComparisonStatus.INCONCLUSIVE,
                "analyte_name": "Periostin",
                "sample_count": 12,
                "mean_bias_pct": 14.8,
                "cv_pct": 18.5,
                "correlation_coefficient": 0.85,
                "within_tolerance": None,
                "tolerance_limit_pct": 15.0,
                "comparison_date": now - timedelta(days=45),
                "completed_date": now - timedelta(days=35),
                "reviewed_by": "Dr. Mark Phillips",
                "notes": "Inconclusive due to borderline bias. Additional samples requested.",
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "LC-009",
                "trial_id": LIBTAYO_TRIAL,
                "reference_lab_id": "LAB-HOU-001",
                "comparison_lab_id": "LAB-SEA-001",
                "comparison_status": ComparisonStatus.COMPLETED,
                "analyte_name": "PD-L1 TPS",
                "sample_count": 40,
                "mean_bias_pct": 4.2,
                "cv_pct": 8.5,
                "correlation_coefficient": 0.96,
                "within_tolerance": True,
                "tolerance_limit_pct": 15.0,
                "comparison_date": now - timedelta(days=55),
                "completed_date": now - timedelta(days=45),
                "reviewed_by": "Dr. Angela Martinez",
                "notes": "Strong inter-lab agreement for PD-L1 scoring.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "LC-010",
                "trial_id": LIBTAYO_TRIAL,
                "reference_lab_id": "LAB-HOU-001",
                "comparison_lab_id": "LAB-SEA-001",
                "comparison_status": ComparisonStatus.COMPLETED,
                "analyte_name": "TMB (mut/Mb)",
                "sample_count": 25,
                "mean_bias_pct": 6.8,
                "cv_pct": 11.2,
                "correlation_coefficient": 0.93,
                "within_tolerance": True,
                "tolerance_limit_pct": 15.0,
                "comparison_date": now - timedelta(days=50),
                "completed_date": now - timedelta(days=40),
                "reviewed_by": "Dr. Angela Martinez",
                "notes": "TMB concordance acceptable across labs.",
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "LC-011",
                "trial_id": LIBTAYO_TRIAL,
                "reference_lab_id": "LAB-HOU-001",
                "comparison_lab_id": "LAB-SEA-001",
                "comparison_status": ComparisonStatus.CANCELLED,
                "analyte_name": "ctDNA",
                "sample_count": 0,
                "mean_bias_pct": None,
                "cv_pct": None,
                "correlation_coefficient": None,
                "within_tolerance": None,
                "tolerance_limit_pct": 20.0,
                "comparison_date": now - timedelta(days=30),
                "completed_date": None,
                "reviewed_by": None,
                "notes": "Cancelled due to assay platform change at comparison lab.",
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "LC-012",
                "trial_id": LIBTAYO_TRIAL,
                "reference_lab_id": "LAB-HOU-001",
                "comparison_lab_id": "LAB-SEA-001",
                "comparison_status": ComparisonStatus.SCHEDULED,
                "analyte_name": "MSI PCR",
                "sample_count": 0,
                "mean_bias_pct": None,
                "cv_pct": None,
                "correlation_coefficient": None,
                "within_tolerance": None,
                "tolerance_limit_pct": 10.0,
                "comparison_date": now + timedelta(days=20),
                "completed_date": None,
                "reviewed_by": None,
                "notes": "Scheduled comparison pending instrument qualification.",
                "created_at": now - timedelta(days=3),
            },
        ]

        for lc in lc_data:
            self._lab_comparisons[lc["id"]] = LabComparison(**lc)

        # --- 12 Accreditation Records ---
        acc_data = [
            {
                "id": "ACC-001",
                "trial_id": EYLEA_TRIAL,
                "lab_id": "LAB-NY-001",
                "lab_name": "NYC Central Lab",
                "accrediting_body": "CAP",
                "accreditation_number": "CAP-NY-2024-0142",
                "accreditation_status": AccreditationStatus.ACTIVE,
                "scope": "Clinical Chemistry, Hematology, Immunology",
                "issue_date": now - timedelta(days=365),
                "expiry_date": now + timedelta(days=365),
                "last_inspection_date": now - timedelta(days=180),
                "next_inspection_date": now + timedelta(days=185),
                "conditions": None,
                "certificate_url": "https://cap.org/certs/NY-0142",
                "verified_by": "QA Manager Sarah Johnson",
                "notes": "Full accreditation. No deficiencies found.",
                "created_at": now - timedelta(days=366),
            },
            {
                "id": "ACC-002",
                "trial_id": EYLEA_TRIAL,
                "lab_id": "LAB-NY-001",
                "lab_name": "NYC Central Lab",
                "accrediting_body": "CLIA",
                "accreditation_number": "CLIA-33D2045678",
                "accreditation_status": AccreditationStatus.ACTIVE,
                "scope": "High Complexity Testing",
                "issue_date": now - timedelta(days=730),
                "expiry_date": now + timedelta(days=90),
                "last_inspection_date": now - timedelta(days=365),
                "next_inspection_date": now + timedelta(days=30),
                "conditions": None,
                "certificate_url": None,
                "verified_by": "QA Manager Sarah Johnson",
                "notes": "CLIA certificate approaching renewal.",
                "created_at": now - timedelta(days=731),
            },
            {
                "id": "ACC-003",
                "trial_id": EYLEA_TRIAL,
                "lab_id": "LAB-LA-001",
                "lab_name": "LA Reference Lab",
                "accrediting_body": "CAP",
                "accreditation_number": "CAP-LA-2024-0287",
                "accreditation_status": AccreditationStatus.PENDING_RENEWAL,
                "scope": "Clinical Chemistry, Immunology, Molecular",
                "issue_date": now - timedelta(days=730),
                "expiry_date": now - timedelta(days=5),
                "last_inspection_date": now - timedelta(days=30),
                "next_inspection_date": None,
                "conditions": "Awaiting renewal decision post-inspection",
                "certificate_url": "https://cap.org/certs/LA-0287",
                "verified_by": "QA Manager Robert Chen",
                "notes": "Renewal application submitted. Inspection completed.",
                "created_at": now - timedelta(days=731),
            },
            {
                "id": "ACC-004",
                "trial_id": EYLEA_TRIAL,
                "lab_id": "LAB-LA-001",
                "lab_name": "LA Reference Lab",
                "accrediting_body": "ISO 15189",
                "accreditation_number": "ISO-LA-2023-4521",
                "accreditation_status": AccreditationStatus.SUSPENDED,
                "scope": "Immunoassay Testing",
                "issue_date": now - timedelta(days=500),
                "expiry_date": now + timedelta(days=230),
                "last_inspection_date": now - timedelta(days=60),
                "next_inspection_date": now + timedelta(days=30),
                "conditions": "Suspended pending corrective actions for VEGF assay nonconformity",
                "certificate_url": None,
                "verified_by": "QA Manager Robert Chen",
                "notes": "Suspension related to PT failure on VEGF-A assay.",
                "created_at": now - timedelta(days=501),
            },
            {
                "id": "ACC-005",
                "trial_id": DUPIXENT_TRIAL,
                "lab_id": "LAB-CHI-001",
                "lab_name": "Chicago Immunology Lab",
                "accrediting_body": "CAP",
                "accreditation_number": "CAP-CHI-2024-0533",
                "accreditation_status": AccreditationStatus.ACTIVE,
                "scope": "Immunology, Allergy Testing, Flow Cytometry",
                "issue_date": now - timedelta(days=300),
                "expiry_date": now + timedelta(days=430),
                "last_inspection_date": now - timedelta(days=120),
                "next_inspection_date": now + timedelta(days=245),
                "conditions": None,
                "certificate_url": "https://cap.org/certs/CHI-0533",
                "verified_by": "QA Manager Lisa Park",
                "notes": "Excellent accreditation status. Zero deficiencies.",
                "created_at": now - timedelta(days=301),
            },
            {
                "id": "ACC-006",
                "trial_id": DUPIXENT_TRIAL,
                "lab_id": "LAB-CHI-001",
                "lab_name": "Chicago Immunology Lab",
                "accrediting_body": "CLIA",
                "accreditation_number": "CLIA-14D3056789",
                "accreditation_status": AccreditationStatus.ACTIVE,
                "scope": "High Complexity Testing, Moderate Complexity Testing",
                "issue_date": now - timedelta(days=600),
                "expiry_date": now + timedelta(days=130),
                "last_inspection_date": now - timedelta(days=200),
                "next_inspection_date": now + timedelta(days=100),
                "conditions": None,
                "certificate_url": None,
                "verified_by": "QA Manager Lisa Park",
                "notes": "CLIA certificate valid. Renewal planned.",
                "created_at": now - timedelta(days=601),
            },
            {
                "id": "ACC-007",
                "trial_id": DUPIXENT_TRIAL,
                "lab_id": "LAB-BOS-001",
                "lab_name": "Boston Clinical Lab",
                "accrediting_body": "CAP",
                "accreditation_number": "CAP-BOS-2024-0891",
                "accreditation_status": AccreditationStatus.PROVISIONAL,
                "scope": "Microbiology, Urinalysis",
                "issue_date": now - timedelta(days=60),
                "expiry_date": now + timedelta(days=120),
                "last_inspection_date": now - timedelta(days=60),
                "next_inspection_date": now + timedelta(days=60),
                "conditions": "Provisional pending completion of staff training requirements",
                "certificate_url": "https://cap.org/certs/BOS-0891",
                "verified_by": "QA Manager Tom Bradley",
                "notes": "Provisional accreditation granted. Follow-up required.",
                "created_at": now - timedelta(days=61),
            },
            {
                "id": "ACC-008",
                "trial_id": DUPIXENT_TRIAL,
                "lab_id": "LAB-BOS-001",
                "lab_name": "Boston Clinical Lab",
                "accrediting_body": "COLA",
                "accreditation_number": "COLA-BOS-2024-1122",
                "accreditation_status": AccreditationStatus.EXPIRED,
                "scope": "General Laboratory Testing",
                "issue_date": now - timedelta(days=730),
                "expiry_date": now - timedelta(days=30),
                "last_inspection_date": now - timedelta(days=400),
                "next_inspection_date": None,
                "conditions": "Expired. Renewal application required.",
                "certificate_url": None,
                "verified_by": "QA Manager Tom Bradley",
                "notes": "COLA accreditation lapsed. Transitioning to CAP.",
                "created_at": now - timedelta(days=731),
            },
            {
                "id": "ACC-009",
                "trial_id": LIBTAYO_TRIAL,
                "lab_id": "LAB-HOU-001",
                "lab_name": "Houston Oncology Lab",
                "accrediting_body": "CAP",
                "accreditation_number": "CAP-HOU-2024-0445",
                "accreditation_status": AccreditationStatus.ACTIVE,
                "scope": "Immunohistochemistry, Molecular Pathology, Flow Cytometry",
                "issue_date": now - timedelta(days=200),
                "expiry_date": now + timedelta(days=530),
                "last_inspection_date": now - timedelta(days=90),
                "next_inspection_date": now + timedelta(days=275),
                "conditions": None,
                "certificate_url": "https://cap.org/certs/HOU-0445",
                "verified_by": "QA Manager Kevin Owens",
                "notes": "Full CAP accreditation for oncology testing.",
                "created_at": now - timedelta(days=201),
            },
            {
                "id": "ACC-010",
                "trial_id": LIBTAYO_TRIAL,
                "lab_id": "LAB-HOU-001",
                "lab_name": "Houston Oncology Lab",
                "accrediting_body": "ISO 15189",
                "accreditation_number": "ISO-HOU-2024-7890",
                "accreditation_status": AccreditationStatus.ACTIVE,
                "scope": "PD-L1 Testing, TMB Analysis",
                "issue_date": now - timedelta(days=150),
                "expiry_date": now + timedelta(days=580),
                "last_inspection_date": now - timedelta(days=60),
                "next_inspection_date": now + timedelta(days=305),
                "conditions": None,
                "certificate_url": None,
                "verified_by": "QA Manager Kevin Owens",
                "notes": "ISO 15189 accredited for companion diagnostic testing.",
                "created_at": now - timedelta(days=151),
            },
            {
                "id": "ACC-011",
                "trial_id": LIBTAYO_TRIAL,
                "lab_id": "LAB-SEA-001",
                "lab_name": "Seattle Genomics Lab",
                "accrediting_body": "CAP",
                "accreditation_number": "CAP-SEA-2024-0678",
                "accreditation_status": AccreditationStatus.ACTIVE,
                "scope": "Molecular Diagnostics, NGS, Genomic Sequencing",
                "issue_date": now - timedelta(days=250),
                "expiry_date": now + timedelta(days=480),
                "last_inspection_date": now - timedelta(days=100),
                "next_inspection_date": now + timedelta(days=265),
                "conditions": None,
                "certificate_url": "https://cap.org/certs/SEA-0678",
                "verified_by": "QA Manager Amy Chen",
                "notes": "CAP accredited for genomic testing.",
                "created_at": now - timedelta(days=251),
            },
            {
                "id": "ACC-012",
                "trial_id": LIBTAYO_TRIAL,
                "lab_id": "LAB-SEA-001",
                "lab_name": "Seattle Genomics Lab",
                "accrediting_body": "CLIA",
                "accreditation_number": "CLIA-91D4067890",
                "accreditation_status": AccreditationStatus.REVOKED,
                "scope": "Clinical Chemistry",
                "issue_date": now - timedelta(days=900),
                "expiry_date": now - timedelta(days=170),
                "last_inspection_date": now - timedelta(days=180),
                "next_inspection_date": None,
                "conditions": "Revoked due to repeated proficiency testing failures",
                "certificate_url": None,
                "verified_by": "QA Manager Amy Chen",
                "notes": "CLIA revoked for clinical chemistry. Lab no longer performs chem tests.",
                "created_at": now - timedelta(days=901),
            },
        ]

        for acc in acc_data:
            self._accreditation_records[acc["id"]] = AccreditationRecord(**acc)

        # --- 12 Corrective Actions ---
        ca_data = [
            {
                "id": "LCA-001",
                "trial_id": EYLEA_TRIAL,
                "lab_id": "LAB-LA-001",
                "related_test_id": "PT-003",
                "related_comparison_id": None,
                "priority": CorrectiveActionPriority.CRITICAL,
                "finding_description": "Unsatisfactory PT result for VEGF-A ELISA",
                "root_cause": "Reagent lot variability and incorrect calibration curve",
                "corrective_action": "Replace reagent lot and recalibrate assay system",
                "preventive_action": "Implement lot-to-lot verification protocol",
                "assigned_to": "Lab Director Dr. Robert Chen",
                "due_date": now - timedelta(days=50),
                "completed_date": now - timedelta(days=55),
                "is_completed": True,
                "effectiveness_verified": True,
                "verified_by": "QA Manager Sarah Johnson",
                "notes": "Root cause confirmed. New lot validated. Re-testing passed.",
                "created_at": now - timedelta(days=79),
            },
            {
                "id": "LCA-002",
                "trial_id": EYLEA_TRIAL,
                "lab_id": "LAB-LA-001",
                "related_test_id": None,
                "related_comparison_id": "LC-003",
                "priority": CorrectiveActionPriority.HIGH,
                "finding_description": "Failed inter-lab comparison for serum creatinine",
                "root_cause": "Systematic bias in Jaffe method vs enzymatic method at reference lab",
                "corrective_action": "Transition to enzymatic creatinine method aligned with reference lab",
                "preventive_action": "Standardize method selection across trial labs",
                "assigned_to": "Chemistry Lead Dr. James Wilson",
                "due_date": now - timedelta(days=30),
                "completed_date": now - timedelta(days=35),
                "is_completed": True,
                "effectiveness_verified": False,
                "verified_by": None,
                "notes": "Method transition complete. Verification pending next comparison round.",
                "created_at": now - timedelta(days=59),
            },
            {
                "id": "LCA-003",
                "trial_id": EYLEA_TRIAL,
                "lab_id": "LAB-LA-001",
                "related_test_id": "PT-004",
                "related_comparison_id": None,
                "priority": CorrectiveActionPriority.MEDIUM,
                "finding_description": "Marginal PT result for LDL cholesterol",
                "root_cause": None,
                "corrective_action": "Review calibration procedures and run additional QC samples",
                "preventive_action": None,
                "assigned_to": "Chemistry Supervisor Maria Santos",
                "due_date": now + timedelta(days=10),
                "completed_date": None,
                "is_completed": False,
                "effectiveness_verified": False,
                "verified_by": None,
                "notes": "Investigation ongoing. Root cause analysis in progress.",
                "created_at": now - timedelta(days=74),
            },
            {
                "id": "LCA-004",
                "trial_id": EYLEA_TRIAL,
                "lab_id": "LAB-NY-001",
                "related_test_id": None,
                "related_comparison_id": None,
                "priority": CorrectiveActionPriority.LOW,
                "finding_description": "Minor documentation gap in PT record filing",
                "root_cause": "Staff unfamiliarity with new electronic filing system",
                "corrective_action": "Provide targeted training on electronic PT documentation",
                "preventive_action": "Quarterly documentation audits",
                "assigned_to": "QA Coordinator Jennifer Adams",
                "due_date": now + timedelta(days=30),
                "completed_date": None,
                "is_completed": False,
                "effectiveness_verified": False,
                "verified_by": None,
                "notes": "Training scheduled for next week.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "LCA-005",
                "trial_id": DUPIXENT_TRIAL,
                "lab_id": "LAB-BOS-001",
                "related_test_id": None,
                "related_comparison_id": None,
                "priority": CorrectiveActionPriority.HIGH,
                "finding_description": "Provisional accreditation conditions not fully addressed",
                "root_cause": "Insufficient staffing for required training completion",
                "corrective_action": "Hire additional certified technologist and complete all training",
                "preventive_action": "Maintain minimum staffing ratios with qualified personnel",
                "assigned_to": "Lab Director Dr. Tom Bradley",
                "due_date": now + timedelta(days=45),
                "completed_date": None,
                "is_completed": False,
                "effectiveness_verified": False,
                "verified_by": None,
                "notes": "Recruitment in progress. Two candidates in interview stage.",
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "LCA-006",
                "trial_id": DUPIXENT_TRIAL,
                "lab_id": "LAB-BOS-001",
                "related_test_id": None,
                "related_comparison_id": None,
                "priority": CorrectiveActionPriority.MEDIUM,
                "finding_description": "COLA accreditation expired without timely renewal",
                "root_cause": "Administrative oversight in renewal tracking",
                "corrective_action": "Submit CAP accreditation application as replacement",
                "preventive_action": "Implement automated accreditation expiry alerts at 90, 60, 30 days",
                "assigned_to": "QA Manager Tom Bradley",
                "due_date": now + timedelta(days=15),
                "completed_date": None,
                "is_completed": False,
                "effectiveness_verified": False,
                "verified_by": None,
                "notes": "CAP application submitted. Awaiting inspection scheduling.",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "LCA-007",
                "trial_id": DUPIXENT_TRIAL,
                "lab_id": "LAB-CHI-001",
                "related_test_id": None,
                "related_comparison_id": "LC-008",
                "priority": CorrectiveActionPriority.MEDIUM,
                "finding_description": "Inconclusive periostin inter-lab comparison",
                "root_cause": None,
                "corrective_action": "Collect additional comparison samples and repeat analysis",
                "preventive_action": None,
                "assigned_to": "Immunology Lead Dr. Grace Lee",
                "due_date": now + timedelta(days=25),
                "completed_date": None,
                "is_completed": False,
                "effectiveness_verified": False,
                "verified_by": None,
                "notes": "Additional 10 samples collected. Repeat analysis planned.",
                "created_at": now - timedelta(days=34),
            },
            {
                "id": "LCA-008",
                "trial_id": DUPIXENT_TRIAL,
                "lab_id": "LAB-CHI-001",
                "related_test_id": None,
                "related_comparison_id": None,
                "priority": CorrectiveActionPriority.INFORMATIONAL,
                "finding_description": "Recommendation to update IgE assay SOP to latest version",
                "root_cause": "SOP version lag behind manufacturer recommendations",
                "corrective_action": "Update SOP to incorporate latest manufacturer guidance",
                "preventive_action": "Subscribe to manufacturer SOP update notifications",
                "assigned_to": "QA Coordinator Lisa Park",
                "due_date": now + timedelta(days=60),
                "completed_date": None,
                "is_completed": False,
                "effectiveness_verified": False,
                "verified_by": None,
                "notes": "Informational finding. Low risk. SOP update drafted.",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "LCA-009",
                "trial_id": LIBTAYO_TRIAL,
                "lab_id": "LAB-SEA-001",
                "related_test_id": "PT-011",
                "related_comparison_id": None,
                "priority": CorrectiveActionPriority.HIGH,
                "finding_description": "PT withdrawn due to instrument calibration failure",
                "root_cause": "Scheduled preventive maintenance overdue by 2 weeks",
                "corrective_action": "Complete instrument PM and recalibrate. Re-enroll in next PT cycle.",
                "preventive_action": "Enforce strict PM schedule with automated lockout on overdue instruments",
                "assigned_to": "Instrument Manager David Park",
                "due_date": now - timedelta(days=10),
                "completed_date": now - timedelta(days=12),
                "is_completed": True,
                "effectiveness_verified": True,
                "verified_by": "Lab Director Dr. Angela Martinez",
                "notes": "PM completed. Calibration verified. Re-enrolled in next PT cycle.",
                "created_at": now - timedelta(days=44),
            },
            {
                "id": "LCA-010",
                "trial_id": LIBTAYO_TRIAL,
                "lab_id": "LAB-SEA-001",
                "related_test_id": "PT-012",
                "related_comparison_id": None,
                "priority": CorrectiveActionPriority.CRITICAL,
                "finding_description": "Unsatisfactory PT result for ALT - significantly elevated reported value",
                "root_cause": "Contaminated reagent water supply affecting enzyme assays",
                "corrective_action": "Replace water purification filters and revalidate all enzyme assays",
                "preventive_action": "Weekly water quality monitoring with documented acceptance criteria",
                "assigned_to": "Lab Director Dr. Angela Martinez",
                "due_date": now + timedelta(days=5),
                "completed_date": None,
                "is_completed": False,
                "effectiveness_verified": False,
                "verified_by": None,
                "notes": "Critical issue. Water purification system under repair.",
                "created_at": now - timedelta(days=39),
            },
            {
                "id": "LCA-011",
                "trial_id": LIBTAYO_TRIAL,
                "lab_id": "LAB-SEA-001",
                "related_test_id": None,
                "related_comparison_id": "LC-011",
                "priority": CorrectiveActionPriority.MEDIUM,
                "finding_description": "Lab comparison cancelled due to assay platform change",
                "root_cause": "Uncoordinated platform migration across trial labs",
                "corrective_action": "Complete new platform validation and reschedule comparison",
                "preventive_action": "Require sponsor approval before any assay platform changes during trial",
                "assigned_to": "Technical Director Amy Chen",
                "due_date": now + timedelta(days=40),
                "completed_date": None,
                "is_completed": False,
                "effectiveness_verified": False,
                "verified_by": None,
                "notes": "New platform validation 60% complete.",
                "created_at": now - timedelta(days=29),
            },
            {
                "id": "LCA-012",
                "trial_id": LIBTAYO_TRIAL,
                "lab_id": "LAB-SEA-001",
                "related_test_id": None,
                "related_comparison_id": None,
                "priority": CorrectiveActionPriority.CRITICAL,
                "finding_description": "CLIA clinical chemistry accreditation revoked",
                "root_cause": "Repeated proficiency testing failures in clinical chemistry",
                "corrective_action": "Cease clinical chemistry testing. Transfer samples to accredited lab.",
                "preventive_action": "Establish mandatory PT pass rate thresholds with auto-escalation",
                "assigned_to": "Lab Director Dr. Angela Martinez",
                "due_date": now - timedelta(days=150),
                "completed_date": now - timedelta(days=155),
                "is_completed": True,
                "effectiveness_verified": True,
                "verified_by": "Sponsor QA Director Kevin Owens",
                "notes": "All chem testing transferred to Houston lab. Verified operational.",
                "created_at": now - timedelta(days=175),
            },
        ]

        for ca in ca_data:
            self._corrective_actions[ca["id"]] = LabCorrectiveAction(**ca)

    # ------------------------------------------------------------------
    # Proficiency Tests
    # ------------------------------------------------------------------

    def list_proficiency_tests(
        self,
        *,
        trial_id: str | None = None,
        test_category: TestCategory | None = None,
        test_result: TestResult | None = None,
    ) -> list[ProficiencyTest]:
        """List proficiency tests with optional filters."""
        with self._lock:
            result = list(self._proficiency_tests.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if test_category is not None:
            result = [r for r in result if r.test_category == test_category]
        if test_result is not None:
            result = [r for r in result if r.test_result == test_result]

        return sorted(result, key=lambda r: r.test_date, reverse=True)

    def get_proficiency_test(self, test_id: str) -> ProficiencyTest | None:
        """Get a single proficiency test by ID."""
        with self._lock:
            return self._proficiency_tests.get(test_id)

    def create_proficiency_test(self, payload: ProficiencyTestCreate) -> ProficiencyTest:
        """Create a new proficiency test."""
        now = datetime.now(timezone.utc)
        test_id = f"PT-{uuid4().hex[:8].upper()}"
        record = ProficiencyTest(
            id=test_id,
            trial_id=payload.trial_id,
            lab_id=payload.lab_id,
            lab_name=payload.lab_name,
            test_category=payload.test_category,
            test_name=payload.test_name,
            test_result=TestResult.PENDING,
            test_date=payload.test_date,
            reporting_deadline=None,
            analyte_name=payload.analyte_name,
            reported_value=None,
            expected_value=None,
            acceptable_range_low=None,
            acceptable_range_high=None,
            z_score=None,
            pt_provider=payload.pt_provider,
            cycle_number=payload.cycle_number,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._proficiency_tests[test_id] = record
        logger.info("Created proficiency test %s for trial %s", test_id, payload.trial_id)
        return record

    def update_proficiency_test(
        self, test_id: str, payload: ProficiencyTestUpdate
    ) -> ProficiencyTest | None:
        """Update an existing proficiency test."""
        with self._lock:
            existing = self._proficiency_tests.get(test_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ProficiencyTest(**data)
            self._proficiency_tests[test_id] = updated
        return updated

    def delete_proficiency_test(self, test_id: str) -> bool:
        """Delete a proficiency test. Returns True if deleted."""
        with self._lock:
            if test_id in self._proficiency_tests:
                del self._proficiency_tests[test_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Lab Comparisons
    # ------------------------------------------------------------------

    def list_lab_comparisons(
        self,
        *,
        trial_id: str | None = None,
        comparison_status: ComparisonStatus | None = None,
    ) -> list[LabComparison]:
        """List lab comparisons with optional filters."""
        with self._lock:
            result = list(self._lab_comparisons.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if comparison_status is not None:
            result = [r for r in result if r.comparison_status == comparison_status]

        return sorted(result, key=lambda r: r.created_at, reverse=True)

    def get_lab_comparison(self, comparison_id: str) -> LabComparison | None:
        """Get a single lab comparison by ID."""
        with self._lock:
            return self._lab_comparisons.get(comparison_id)

    def create_lab_comparison(self, payload: LabComparisonCreate) -> LabComparison:
        """Create a new lab comparison."""
        now = datetime.now(timezone.utc)
        comparison_id = f"LC-{uuid4().hex[:8].upper()}"
        record = LabComparison(
            id=comparison_id,
            trial_id=payload.trial_id,
            reference_lab_id=payload.reference_lab_id,
            comparison_lab_id=payload.comparison_lab_id,
            comparison_status=ComparisonStatus.SCHEDULED,
            analyte_name=payload.analyte_name,
            sample_count=payload.sample_count,
            mean_bias_pct=None,
            cv_pct=None,
            correlation_coefficient=None,
            within_tolerance=None,
            tolerance_limit_pct=payload.tolerance_limit_pct,
            comparison_date=None,
            completed_date=None,
            reviewed_by=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._lab_comparisons[comparison_id] = record
        logger.info("Created lab comparison %s for trial %s", comparison_id, payload.trial_id)
        return record

    def update_lab_comparison(
        self, comparison_id: str, payload: LabComparisonUpdate
    ) -> LabComparison | None:
        """Update an existing lab comparison."""
        with self._lock:
            existing = self._lab_comparisons.get(comparison_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = LabComparison(**data)
            self._lab_comparisons[comparison_id] = updated
        return updated

    def delete_lab_comparison(self, comparison_id: str) -> bool:
        """Delete a lab comparison. Returns True if deleted."""
        with self._lock:
            if comparison_id in self._lab_comparisons:
                del self._lab_comparisons[comparison_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Accreditation Records
    # ------------------------------------------------------------------

    def list_accreditation_records(
        self,
        *,
        trial_id: str | None = None,
        accreditation_status: AccreditationStatus | None = None,
    ) -> list[AccreditationRecord]:
        """List accreditation records with optional filters."""
        with self._lock:
            result = list(self._accreditation_records.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if accreditation_status is not None:
            result = [r for r in result if r.accreditation_status == accreditation_status]

        return sorted(result, key=lambda r: r.created_at, reverse=True)

    def get_accreditation_record(self, record_id: str) -> AccreditationRecord | None:
        """Get a single accreditation record by ID."""
        with self._lock:
            return self._accreditation_records.get(record_id)

    def create_accreditation_record(
        self, payload: AccreditationRecordCreate
    ) -> AccreditationRecord:
        """Create a new accreditation record."""
        now = datetime.now(timezone.utc)
        record_id = f"ACC-{uuid4().hex[:8].upper()}"
        record = AccreditationRecord(
            id=record_id,
            trial_id=payload.trial_id,
            lab_id=payload.lab_id,
            lab_name=payload.lab_name,
            accrediting_body=payload.accrediting_body,
            accreditation_number=payload.accreditation_number,
            accreditation_status=AccreditationStatus.ACTIVE,
            scope=payload.scope,
            issue_date=payload.issue_date,
            expiry_date=payload.expiry_date,
            last_inspection_date=None,
            next_inspection_date=None,
            conditions=None,
            certificate_url=None,
            verified_by=payload.verified_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._accreditation_records[record_id] = record
        logger.info("Created accreditation record %s for trial %s", record_id, payload.trial_id)
        return record

    def update_accreditation_record(
        self, record_id: str, payload: AccreditationRecordUpdate
    ) -> AccreditationRecord | None:
        """Update an existing accreditation record."""
        with self._lock:
            existing = self._accreditation_records.get(record_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = AccreditationRecord(**data)
            self._accreditation_records[record_id] = updated
        return updated

    def delete_accreditation_record(self, record_id: str) -> bool:
        """Delete an accreditation record. Returns True if deleted."""
        with self._lock:
            if record_id in self._accreditation_records:
                del self._accreditation_records[record_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Corrective Actions
    # ------------------------------------------------------------------

    def list_corrective_actions(
        self,
        *,
        trial_id: str | None = None,
        priority: CorrectiveActionPriority | None = None,
        is_completed: bool | None = None,
    ) -> list[LabCorrectiveAction]:
        """List corrective actions with optional filters."""
        with self._lock:
            result = list(self._corrective_actions.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if priority is not None:
            result = [r for r in result if r.priority == priority]
        if is_completed is not None:
            result = [r for r in result if r.is_completed == is_completed]

        return sorted(result, key=lambda r: r.created_at, reverse=True)

    def get_corrective_action(self, action_id: str) -> LabCorrectiveAction | None:
        """Get a single corrective action by ID."""
        with self._lock:
            return self._corrective_actions.get(action_id)

    def create_corrective_action(
        self, payload: LabCorrectiveActionCreate
    ) -> LabCorrectiveAction:
        """Create a new corrective action."""
        now = datetime.now(timezone.utc)
        action_id = f"LCA-{uuid4().hex[:8].upper()}"
        record = LabCorrectiveAction(
            id=action_id,
            trial_id=payload.trial_id,
            lab_id=payload.lab_id,
            related_test_id=payload.related_test_id,
            related_comparison_id=payload.related_comparison_id,
            priority=payload.priority,
            finding_description=payload.finding_description,
            root_cause=None,
            corrective_action=payload.corrective_action,
            preventive_action=None,
            assigned_to=payload.assigned_to,
            due_date=payload.due_date,
            completed_date=None,
            is_completed=False,
            effectiveness_verified=False,
            verified_by=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._corrective_actions[action_id] = record
        logger.info("Created corrective action %s for trial %s", action_id, payload.trial_id)
        return record

    def update_corrective_action(
        self, action_id: str, payload: LabCorrectiveActionUpdate
    ) -> LabCorrectiveAction | None:
        """Update an existing corrective action."""
        with self._lock:
            existing = self._corrective_actions.get(action_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = LabCorrectiveAction(**data)
            self._corrective_actions[action_id] = updated
        return updated

    def delete_corrective_action(self, action_id: str) -> bool:
        """Delete a corrective action. Returns True if deleted."""
        with self._lock:
            if action_id in self._corrective_actions:
                del self._corrective_actions[action_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> LabProficiencyMetrics:
        """Compute aggregated lab proficiency metrics."""
        with self._lock:
            tests = list(self._proficiency_tests.values())
            comparisons = list(self._lab_comparisons.values())
            accreditations = list(self._accreditation_records.values())
            actions = list(self._corrective_actions.values())

        # Tests by category
        tests_by_category: dict[str, int] = {}
        for t in tests:
            key = t.test_category.value
            tests_by_category[key] = tests_by_category.get(key, 0) + 1

        # Tests by result
        tests_by_result: dict[str, int] = {}
        for t in tests:
            key = t.test_result.value
            tests_by_result[key] = tests_by_result.get(key, 0) + 1

        # Satisfactory rate (among graded tests)
        graded_tests = [
            t for t in tests
            if t.test_result not in (TestResult.PENDING, TestResult.NOT_GRADED, TestResult.WITHDRAWN)
        ]
        satisfactory_count = sum(
            1 for t in graded_tests if t.test_result == TestResult.SATISFACTORY
        )
        satisfactory_rate = round(
            (satisfactory_count / max(1, len(graded_tests))) * 100, 1
        )

        # Comparisons by status
        comparisons_by_status: dict[str, int] = {}
        for c in comparisons:
            key = c.comparison_status.value
            comparisons_by_status[key] = comparisons_by_status.get(key, 0) + 1

        # Within tolerance rate (among completed comparisons with a tolerance result)
        tolerance_evaluated = [
            c for c in comparisons if c.within_tolerance is not None
        ]
        within_tolerance_count = sum(
            1 for c in tolerance_evaluated if c.within_tolerance is True
        )
        within_tolerance_rate = round(
            (within_tolerance_count / max(1, len(tolerance_evaluated))) * 100, 1
        )

        # Accreditations by status
        accreditations_by_status: dict[str, int] = {}
        for a in accreditations:
            key = a.accreditation_status.value
            accreditations_by_status[key] = accreditations_by_status.get(key, 0) + 1

        # Active accreditation rate
        active_count = sum(
            1 for a in accreditations if a.accreditation_status == AccreditationStatus.ACTIVE
        )
        active_accreditation_rate = round(
            (active_count / max(1, len(accreditations))) * 100, 1
        )

        # Corrective actions by priority
        corrective_actions_by_priority: dict[str, int] = {}
        for ca in actions:
            key = ca.priority.value
            corrective_actions_by_priority[key] = corrective_actions_by_priority.get(key, 0) + 1

        # Corrective action completion rate
        completed_count = sum(1 for ca in actions if ca.is_completed)
        completion_rate = round(
            (completed_count / max(1, len(actions))) * 100, 1
        )

        return LabProficiencyMetrics(
            total_proficiency_tests=len(tests),
            tests_by_category=tests_by_category,
            tests_by_result=tests_by_result,
            satisfactory_rate=satisfactory_rate,
            total_comparisons=len(comparisons),
            comparisons_by_status=comparisons_by_status,
            within_tolerance_rate=within_tolerance_rate,
            total_accreditations=len(accreditations),
            accreditations_by_status=accreditations_by_status,
            active_accreditation_rate=active_accreditation_rate,
            total_corrective_actions=len(actions),
            corrective_actions_by_priority=corrective_actions_by_priority,
            corrective_action_completion_rate=completion_rate,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: LabProficiencyService | None = None
_instance_lock = threading.Lock()


def get_lab_proficiency_service() -> LabProficiencyService:
    """Return the singleton LabProficiencyService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = LabProficiencyService()
    return _instance


def reset_lab_proficiency_service() -> LabProficiencyService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = LabProficiencyService()
    return _instance
