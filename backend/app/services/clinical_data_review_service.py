"""Clinical Data Review Management Service (DATA-REV).

Manages clinical data review operations: data review listings, data query
resolution tracking, data cleaning tasks, edit check management, reviewer
assignments, and data review operational metrics.

Usage:
    from app.services.clinical_data_review_service import (
        get_clinical_data_review_service,
    )

    svc = get_clinical_data_review_service()
    listings = svc.list_data_review_listings()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.clinical_data_review import (
    ClinicalDataReviewMetrics,
    DataCleaningTask,
    DataCleaningTaskCreate,
    DataCleaningTaskUpdate,
    DataQuery,
    DataQueryCreate,
    DataQueryUpdate,
    DataReviewListing,
    DataReviewListingCreate,
    DataReviewListingUpdate,
    EditCheck,
    EditCheckCreate,
    EditCheckSeverity,
    EditCheckUpdate,
    ListingType,
    QueryPriority,
    QueryStatus,
    ReviewerAssignment,
    ReviewerAssignmentCreate,
    ReviewerAssignmentUpdate,
    ReviewStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class ClinicalDataReviewService:
    """In-memory Clinical Data Review engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._data_review_listings: dict[str, DataReviewListing] = {}
        self._data_queries: dict[str, DataQuery] = {}
        self._data_cleaning_tasks: dict[str, DataCleaningTask] = {}
        self._edit_checks: dict[str, EditCheck] = {}
        self._reviewer_assignments: dict[str, ReviewerAssignment] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic clinical data review records."""
        now = datetime.now(timezone.utc)

        # --- 12 Data Review Listings ---
        listings_data: list[dict] = [
            {
                "id": "DRL-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "listing_type": ListingType.PATIENT,
                "listing_name": "EYLEA Patient Demographics Listing",
                "review_status": ReviewStatus.CLEAN,
                "total_records": 245,
                "reviewed_records": 245,
                "clean_records": 240,
                "records_with_queries": 5,
                "completion_pct": 100.0,
                "data_cutoff_date": now - timedelta(days=14),
                "assigned_reviewer": "Dr. Sarah Chen",
                "review_start_date": now - timedelta(days=30),
                "review_end_date": now - timedelta(days=7),
                "locked_by": "Dr. Sarah Chen",
                "locked_date": now - timedelta(days=5),
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "DRL-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "listing_type": ListingType.ADVERSE_EVENT,
                "listing_name": "EYLEA Adverse Events Listing",
                "review_status": ReviewStatus.QUERIES_ISSUED,
                "total_records": 187,
                "reviewed_records": 150,
                "clean_records": 130,
                "records_with_queries": 20,
                "completion_pct": 80.2,
                "data_cutoff_date": now - timedelta(days=14),
                "assigned_reviewer": "Dr. Michael Park",
                "review_start_date": now - timedelta(days=21),
                "review_end_date": None,
                "locked_by": None,
                "locked_date": None,
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "DRL-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-103",
                "listing_type": ListingType.LABORATORY,
                "listing_name": "EYLEA Central Lab Results Listing",
                "review_status": ReviewStatus.IN_REVIEW,
                "total_records": 1520,
                "reviewed_records": 890,
                "clean_records": 850,
                "records_with_queries": 40,
                "completion_pct": 58.6,
                "data_cutoff_date": now - timedelta(days=7),
                "assigned_reviewer": "Jennifer Liu",
                "review_start_date": now - timedelta(days=14),
                "review_end_date": None,
                "locked_by": None,
                "locked_date": None,
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "DRL-004",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "listing_type": ListingType.VITAL_SIGNS,
                "listing_name": "DUPIXENT Vital Signs Listing",
                "review_status": ReviewStatus.REVIEWED,
                "total_records": 960,
                "reviewed_records": 960,
                "clean_records": 920,
                "records_with_queries": 40,
                "completion_pct": 100.0,
                "data_cutoff_date": now - timedelta(days=21),
                "assigned_reviewer": "Dr. Sarah Chen",
                "review_start_date": now - timedelta(days=35),
                "review_end_date": now - timedelta(days=10),
                "locked_by": None,
                "locked_date": None,
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "DRL-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-105",
                "listing_type": ListingType.CONCOMITANT_MEDICATION,
                "listing_name": "DUPIXENT Concomitant Medications Listing",
                "review_status": ReviewStatus.PENDING,
                "total_records": 430,
                "reviewed_records": 0,
                "clean_records": 0,
                "records_with_queries": 0,
                "completion_pct": 0.0,
                "data_cutoff_date": now - timedelta(days=3),
                "assigned_reviewer": None,
                "review_start_date": None,
                "review_end_date": None,
                "locked_by": None,
                "locked_date": None,
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "DRL-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-101",
                "listing_type": ListingType.EFFICACY,
                "listing_name": "DUPIXENT Primary Efficacy Listing",
                "review_status": ReviewStatus.IN_REVIEW,
                "total_records": 312,
                "reviewed_records": 200,
                "clean_records": 185,
                "records_with_queries": 15,
                "completion_pct": 64.1,
                "data_cutoff_date": now - timedelta(days=7),
                "assigned_reviewer": "Dr. Michael Park",
                "review_start_date": now - timedelta(days=10),
                "review_end_date": None,
                "locked_by": None,
                "locked_date": None,
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "DRL-007",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "listing_type": ListingType.VISIT,
                "listing_name": "LIBTAYO Visit Schedule Compliance Listing",
                "review_status": ReviewStatus.QUERIES_ISSUED,
                "total_records": 578,
                "reviewed_records": 450,
                "clean_records": 400,
                "records_with_queries": 50,
                "completion_pct": 77.9,
                "data_cutoff_date": now - timedelta(days=10),
                "assigned_reviewer": "Jennifer Liu",
                "review_start_date": now - timedelta(days=18),
                "review_end_date": None,
                "locked_by": None,
                "locked_date": None,
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "DRL-008",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-107",
                "listing_type": ListingType.PROTOCOL_DEVIATION,
                "listing_name": "LIBTAYO Protocol Deviation Listing",
                "review_status": ReviewStatus.IN_REVIEW,
                "total_records": 89,
                "reviewed_records": 45,
                "clean_records": 30,
                "records_with_queries": 15,
                "completion_pct": 50.6,
                "data_cutoff_date": now - timedelta(days=7),
                "assigned_reviewer": "Dr. Sarah Chen",
                "review_start_date": now - timedelta(days=12),
                "review_end_date": None,
                "locked_by": None,
                "locked_date": None,
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "DRL-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-108",
                "listing_type": ListingType.ADVERSE_EVENT,
                "listing_name": "LIBTAYO Serious Adverse Events Listing",
                "review_status": ReviewStatus.LOCKED,
                "total_records": 67,
                "reviewed_records": 67,
                "clean_records": 65,
                "records_with_queries": 2,
                "completion_pct": 100.0,
                "data_cutoff_date": now - timedelta(days=28),
                "assigned_reviewer": "Dr. Michael Park",
                "review_start_date": now - timedelta(days=42),
                "review_end_date": now - timedelta(days=21),
                "locked_by": "Dr. Michael Park",
                "locked_date": now - timedelta(days=18),
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "DRL-010",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-104",
                "listing_type": ListingType.LABORATORY,
                "listing_name": "EYLEA Immunogenicity Lab Listing",
                "review_status": ReviewStatus.PENDING,
                "total_records": 350,
                "reviewed_records": 0,
                "clean_records": 0,
                "records_with_queries": 0,
                "completion_pct": 0.0,
                "data_cutoff_date": now - timedelta(days=1),
                "assigned_reviewer": None,
                "review_start_date": None,
                "review_end_date": None,
                "locked_by": None,
                "locked_date": None,
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "DRL-011",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-106",
                "listing_type": ListingType.PATIENT,
                "listing_name": "DUPIXENT Disposition Listing",
                "review_status": ReviewStatus.REVIEWED,
                "total_records": 198,
                "reviewed_records": 198,
                "clean_records": 190,
                "records_with_queries": 8,
                "completion_pct": 100.0,
                "data_cutoff_date": now - timedelta(days=14),
                "assigned_reviewer": "Jennifer Liu",
                "review_start_date": now - timedelta(days=28),
                "review_end_date": now - timedelta(days=8),
                "locked_by": None,
                "locked_date": None,
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "DRL-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-103",
                "listing_type": ListingType.VITAL_SIGNS,
                "listing_name": "LIBTAYO Vital Signs Listing",
                "review_status": ReviewStatus.CLEAN,
                "total_records": 720,
                "reviewed_records": 720,
                "clean_records": 715,
                "records_with_queries": 5,
                "completion_pct": 100.0,
                "data_cutoff_date": now - timedelta(days=21),
                "assigned_reviewer": "Dr. Sarah Chen",
                "review_start_date": now - timedelta(days=40),
                "review_end_date": now - timedelta(days=14),
                "locked_by": "Dr. Sarah Chen",
                "locked_date": now - timedelta(days=12),
                "created_at": now - timedelta(days=50),
            },
        ]

        for item in listings_data:
            self._data_review_listings[item["id"]] = DataReviewListing(**item)

        # --- 14 Data Queries ---
        queries_data: list[dict] = [
            {
                "id": "DQ-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "subject_id": "SUBJ-1021",
                "listing_id": "DRL-002",
                "form_name": "Adverse Events",
                "field_name": "ae_onset_date",
                "visit_name": "Visit 4 (Week 8)",
                "query_text": "AE onset date is after the AE resolution date. Please verify.",
                "query_status": QueryStatus.OPEN,
                "priority": QueryPriority.HIGH,
                "query_type": "auto",
                "current_value": "2025-12-15",
                "expected_value": "Before 2025-12-10",
                "response_text": None,
                "response_date": None,
                "responded_by": None,
                "issued_by": "Edit Check EC-003",
                "issued_date": now - timedelta(days=12),
                "closed_by": None,
                "closed_date": None,
                "days_open": 12,
                "requery_count": 0,
                "created_at": now - timedelta(days=12),
            },
            {
                "id": "DQ-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "subject_id": "SUBJ-1022",
                "listing_id": "DRL-002",
                "form_name": "Adverse Events",
                "field_name": "ae_severity",
                "visit_name": "Visit 6 (Week 16)",
                "query_text": "AE severity grade changed from 3 to 1 without documentation. Please clarify.",
                "query_status": QueryStatus.ANSWERED,
                "priority": QueryPriority.MEDIUM,
                "query_type": "manual",
                "current_value": "Grade 1",
                "expected_value": "Documented reason for downgrade",
                "response_text": "Severity was corrected after re-assessment by PI. Documentation uploaded.",
                "response_date": now - timedelta(days=5),
                "responded_by": "Site Coordinator Jones",
                "issued_by": "Dr. Michael Park",
                "issued_date": now - timedelta(days=15),
                "closed_by": None,
                "closed_date": None,
                "days_open": 15,
                "requery_count": 0,
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "DQ-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-103",
                "subject_id": "SUBJ-1035",
                "listing_id": "DRL-003",
                "form_name": "Laboratory Results",
                "field_name": "creatinine_value",
                "visit_name": "Visit 3 (Week 4)",
                "query_text": "Creatinine value of 15.2 mg/dL appears implausible. Please verify.",
                "query_status": QueryStatus.OPEN,
                "priority": QueryPriority.CRITICAL,
                "query_type": "auto",
                "current_value": "15.2",
                "expected_value": "0.5-1.5",
                "response_text": None,
                "response_date": None,
                "responded_by": None,
                "issued_by": "Edit Check EC-001",
                "issued_date": now - timedelta(days=8),
                "closed_by": None,
                "closed_date": None,
                "days_open": 8,
                "requery_count": 0,
                "created_at": now - timedelta(days=8),
            },
            {
                "id": "DQ-004",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "subject_id": "SUBJ-1041",
                "listing_id": "DRL-004",
                "form_name": "Vital Signs",
                "field_name": "systolic_bp",
                "visit_name": "Visit 5 (Week 12)",
                "query_text": "Systolic BP of 250 mmHg is outside expected range. Please confirm or correct.",
                "query_status": QueryStatus.CLOSED,
                "priority": QueryPriority.HIGH,
                "query_type": "auto",
                "current_value": "250",
                "expected_value": "80-200",
                "response_text": "Value corrected to 150 mmHg. Data entry error.",
                "response_date": now - timedelta(days=18),
                "responded_by": "Site Coordinator Smith",
                "issued_by": "Edit Check EC-002",
                "issued_date": now - timedelta(days=25),
                "closed_by": "Dr. Sarah Chen",
                "closed_date": now - timedelta(days=16),
                "days_open": 9,
                "requery_count": 0,
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "DQ-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-105",
                "subject_id": "SUBJ-1053",
                "listing_id": None,
                "form_name": "Concomitant Medications",
                "field_name": "medication_start_date",
                "visit_name": "Visit 2 (Week 2)",
                "query_text": "Medication start date precedes study consent date. Please verify.",
                "query_status": QueryStatus.REQUERIED,
                "priority": QueryPriority.HIGH,
                "query_type": "auto",
                "current_value": "2025-08-01",
                "expected_value": "After 2025-09-15",
                "response_text": "Medication was started before study. Will update start date.",
                "response_date": now - timedelta(days=10),
                "responded_by": "Site Coordinator Adams",
                "issued_by": "Edit Check EC-005",
                "issued_date": now - timedelta(days=20),
                "closed_by": None,
                "closed_date": None,
                "days_open": 20,
                "requery_count": 1,
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "DQ-006",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "subject_id": "SUBJ-1061",
                "listing_id": "DRL-007",
                "form_name": "Visit Schedule",
                "field_name": "visit_date",
                "visit_name": "Visit 7 (Week 20)",
                "query_text": "Visit date is outside the protocol-specified visit window. Please provide explanation.",
                "query_status": QueryStatus.OPEN,
                "priority": QueryPriority.MEDIUM,
                "query_type": "manual",
                "current_value": "2026-01-05",
                "expected_value": "2025-12-20 to 2025-12-30",
                "response_text": None,
                "response_date": None,
                "responded_by": None,
                "issued_by": "Jennifer Liu",
                "issued_date": now - timedelta(days=6),
                "closed_by": None,
                "closed_date": None,
                "days_open": 6,
                "requery_count": 0,
                "created_at": now - timedelta(days=6),
            },
            {
                "id": "DQ-007",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-107",
                "subject_id": "SUBJ-1072",
                "listing_id": "DRL-008",
                "form_name": "Protocol Deviations",
                "field_name": "deviation_description",
                "visit_name": None,
                "query_text": "Protocol deviation description is incomplete. Please provide full details.",
                "query_status": QueryStatus.OPEN,
                "priority": QueryPriority.HIGH,
                "query_type": "manual",
                "current_value": "Missed dose",
                "expected_value": "Complete description with dates and impact assessment",
                "response_text": None,
                "response_date": None,
                "responded_by": None,
                "issued_by": "Dr. Sarah Chen",
                "issued_date": now - timedelta(days=9),
                "closed_by": None,
                "closed_date": None,
                "days_open": 9,
                "requery_count": 0,
                "created_at": now - timedelta(days=9),
            },
            {
                "id": "DQ-008",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "subject_id": "SUBJ-1015",
                "listing_id": "DRL-001",
                "form_name": "Demographics",
                "field_name": "date_of_birth",
                "visit_name": "Screening",
                "query_text": "Date of birth results in age of 12 years, below inclusion criteria of 18+.",
                "query_status": QueryStatus.CLOSED,
                "priority": QueryPriority.CRITICAL,
                "query_type": "auto",
                "current_value": "2013-05-10",
                "expected_value": "Before 2008-01-01",
                "response_text": "Date of birth corrected to 1963-05-10. Transcription error.",
                "response_date": now - timedelta(days=22),
                "responded_by": "Site Coordinator Williams",
                "issued_by": "Edit Check EC-006",
                "issued_date": now - timedelta(days=28),
                "closed_by": "Dr. Sarah Chen",
                "closed_date": now - timedelta(days=20),
                "days_open": 8,
                "requery_count": 0,
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "DQ-009",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-101",
                "subject_id": "SUBJ-1018",
                "listing_id": "DRL-006",
                "form_name": "Efficacy Assessment",
                "field_name": "easi_score",
                "visit_name": "Visit 8 (Week 24)",
                "query_text": "EASI score decreased by 85% from baseline which is unusual. Please verify assessment.",
                "query_status": QueryStatus.ANSWERED,
                "priority": QueryPriority.MEDIUM,
                "query_type": "manual",
                "current_value": "3.2",
                "expected_value": "Expected gradual improvement",
                "response_text": "Score verified. Patient showed exceptional response to treatment.",
                "response_date": now - timedelta(days=3),
                "responded_by": "Dr. Investigator Zhang",
                "issued_by": "Dr. Michael Park",
                "issued_date": now - timedelta(days=7),
                "closed_by": None,
                "closed_date": None,
                "days_open": 7,
                "requery_count": 0,
                "created_at": now - timedelta(days=7),
            },
            {
                "id": "DQ-010",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-108",
                "subject_id": "SUBJ-1083",
                "listing_id": "DRL-009",
                "form_name": "Serious Adverse Events",
                "field_name": "sae_outcome",
                "visit_name": "Visit 3 (Week 6)",
                "query_text": "SAE outcome is 'Ongoing' but end date is entered. Please reconcile.",
                "query_status": QueryStatus.CLOSED,
                "priority": QueryPriority.HIGH,
                "query_type": "auto",
                "current_value": "Ongoing",
                "expected_value": "Resolved/Recovered if end date present",
                "response_text": "Outcome updated to 'Resolved'. End date is correct.",
                "response_date": now - timedelta(days=30),
                "responded_by": "Site Coordinator Brown",
                "issued_by": "Edit Check EC-004",
                "issued_date": now - timedelta(days=38),
                "closed_by": "Dr. Michael Park",
                "closed_date": now - timedelta(days=28),
                "days_open": 10,
                "requery_count": 0,
                "created_at": now - timedelta(days=38),
            },
            {
                "id": "DQ-011",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-103",
                "subject_id": "SUBJ-1038",
                "listing_id": "DRL-003",
                "form_name": "Laboratory Results",
                "field_name": "hemoglobin_value",
                "visit_name": "Visit 5 (Week 12)",
                "query_text": "Hemoglobin value changed from 14.2 to 6.1 between visits. Please verify.",
                "query_status": QueryStatus.OPEN,
                "priority": QueryPriority.CRITICAL,
                "query_type": "auto",
                "current_value": "6.1",
                "expected_value": "Expected within +/- 20% of previous",
                "response_text": None,
                "response_date": None,
                "responded_by": None,
                "issued_by": "Edit Check EC-001",
                "issued_date": now - timedelta(days=4),
                "closed_by": None,
                "closed_date": None,
                "days_open": 4,
                "requery_count": 0,
                "created_at": now - timedelta(days=4),
            },
            {
                "id": "DQ-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "subject_id": "SUBJ-1065",
                "listing_id": "DRL-007",
                "form_name": "Visit Schedule",
                "field_name": "visit_performed",
                "visit_name": "Visit 9 (Week 28)",
                "query_text": "Visit marked as performed but no assessments have been entered.",
                "query_status": QueryStatus.CANCELLED,
                "priority": QueryPriority.LOW,
                "query_type": "manual",
                "current_value": "Yes",
                "expected_value": "At least one assessment form completed",
                "response_text": None,
                "response_date": None,
                "responded_by": None,
                "issued_by": "Jennifer Liu",
                "issued_date": now - timedelta(days=14),
                "closed_by": "Jennifer Liu",
                "closed_date": now - timedelta(days=13),
                "days_open": 1,
                "requery_count": 0,
                "created_at": now - timedelta(days=14),
            },
            {
                "id": "DQ-013",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "subject_id": "SUBJ-1045",
                "listing_id": "DRL-004",
                "form_name": "Vital Signs",
                "field_name": "heart_rate",
                "visit_name": "Visit 6 (Week 16)",
                "query_text": "Heart rate of 210 bpm exceeds physiological range. Please verify.",
                "query_status": QueryStatus.OPEN,
                "priority": QueryPriority.HIGH,
                "query_type": "auto",
                "current_value": "210",
                "expected_value": "40-180",
                "response_text": None,
                "response_date": None,
                "responded_by": None,
                "issued_by": "Edit Check EC-002",
                "issued_date": now - timedelta(days=2),
                "closed_by": None,
                "closed_date": None,
                "days_open": 2,
                "requery_count": 0,
                "created_at": now - timedelta(days=2),
            },
            {
                "id": "DQ-014",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "subject_id": "SUBJ-1012",
                "listing_id": "DRL-001",
                "form_name": "Demographics",
                "field_name": "gender",
                "visit_name": "Screening",
                "query_text": "Gender field is blank. This is a required field.",
                "query_status": QueryStatus.CLOSED,
                "priority": QueryPriority.MEDIUM,
                "query_type": "auto",
                "current_value": "",
                "expected_value": "Male or Female",
                "response_text": "Gender updated to Female.",
                "response_date": now - timedelta(days=40),
                "responded_by": "Site Coordinator Williams",
                "issued_by": "Edit Check EC-007",
                "issued_date": now - timedelta(days=45),
                "closed_by": "Dr. Sarah Chen",
                "closed_date": now - timedelta(days=38),
                "days_open": 7,
                "requery_count": 0,
                "created_at": now - timedelta(days=45),
            },
        ]

        for item in queries_data:
            self._data_queries[item["id"]] = DataQuery(**item)

        # --- 11 Data Cleaning Tasks ---
        cleaning_tasks_data: list[dict] = [
            {
                "id": "DCT-001",
                "trial_id": EYLEA_TRIAL,
                "task_name": "EYLEA Lab Range Check Review",
                "description": "Review all lab values flagged outside reference ranges for EYLEA trial",
                "listing_id": "DRL-003",
                "assigned_to": "Jennifer Liu",
                "status": "in_progress",
                "priority": QueryPriority.HIGH,
                "records_to_review": 120,
                "records_cleaned": 75,
                "queries_generated": 18,
                "due_date": now + timedelta(days=7),
                "completed_date": None,
                "verification_required": True,
                "verified_by": None,
                "notes": "Focus on creatinine and hemoglobin outliers",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "DCT-002",
                "trial_id": EYLEA_TRIAL,
                "task_name": "EYLEA AE Coding Verification",
                "description": "Verify MedDRA coding for all adverse events in EYLEA trial",
                "listing_id": "DRL-002",
                "assigned_to": "Dr. Michael Park",
                "status": "completed",
                "priority": QueryPriority.MEDIUM,
                "records_to_review": 187,
                "records_cleaned": 187,
                "queries_generated": 12,
                "due_date": now - timedelta(days=5),
                "completed_date": now - timedelta(days=7),
                "verification_required": True,
                "verified_by": "Dr. Sarah Chen",
                "notes": "All AE terms coded and verified against MedDRA v27.0",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "DCT-003",
                "trial_id": DUPIXENT_TRIAL,
                "task_name": "DUPIXENT Vital Signs Outlier Review",
                "description": "Review vital sign values exceeding 3 standard deviations from mean",
                "listing_id": "DRL-004",
                "assigned_to": "Dr. Sarah Chen",
                "status": "completed",
                "priority": QueryPriority.HIGH,
                "records_to_review": 45,
                "records_cleaned": 45,
                "queries_generated": 8,
                "due_date": now - timedelta(days=12),
                "completed_date": now - timedelta(days=14),
                "verification_required": False,
                "verified_by": None,
                "notes": "All outliers verified or corrected",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "DCT-004",
                "trial_id": DUPIXENT_TRIAL,
                "task_name": "DUPIXENT Concomitant Med Date Alignment",
                "description": "Align concomitant medication dates with study visit dates for DUPIXENT",
                "listing_id": "DRL-005",
                "assigned_to": "Jennifer Liu",
                "status": "pending",
                "priority": QueryPriority.MEDIUM,
                "records_to_review": 430,
                "records_cleaned": 0,
                "queries_generated": 0,
                "due_date": now + timedelta(days=21),
                "completed_date": None,
                "verification_required": True,
                "verified_by": None,
                "notes": None,
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "DCT-005",
                "trial_id": LIBTAYO_TRIAL,
                "task_name": "LIBTAYO Visit Window Compliance Check",
                "description": "Identify and resolve all visit window violations for LIBTAYO trial",
                "listing_id": "DRL-007",
                "assigned_to": "Jennifer Liu",
                "status": "in_progress",
                "priority": QueryPriority.HIGH,
                "records_to_review": 78,
                "records_cleaned": 30,
                "queries_generated": 15,
                "due_date": now + timedelta(days=10),
                "completed_date": None,
                "verification_required": True,
                "verified_by": None,
                "notes": "Multiple visit window violations at SITE-106",
                "created_at": now - timedelta(days=14),
            },
            {
                "id": "DCT-006",
                "trial_id": LIBTAYO_TRIAL,
                "task_name": "LIBTAYO Protocol Deviation Classification Review",
                "description": "Review and classify all protocol deviations for LIBTAYO by severity",
                "listing_id": "DRL-008",
                "assigned_to": "Dr. Sarah Chen",
                "status": "in_progress",
                "priority": QueryPriority.CRITICAL,
                "records_to_review": 89,
                "records_cleaned": 45,
                "queries_generated": 22,
                "due_date": now + timedelta(days=5),
                "completed_date": None,
                "verification_required": True,
                "verified_by": None,
                "notes": "High deviation rate at SITE-107 requires immediate attention",
                "created_at": now - timedelta(days=12),
            },
            {
                "id": "DCT-007",
                "trial_id": EYLEA_TRIAL,
                "task_name": "EYLEA Demographics Consistency Check",
                "description": "Cross-reference demographics with screening data for consistency",
                "listing_id": "DRL-001",
                "assigned_to": "Dr. Michael Park",
                "status": "completed",
                "priority": QueryPriority.LOW,
                "records_to_review": 245,
                "records_cleaned": 245,
                "queries_generated": 5,
                "due_date": now - timedelta(days=20),
                "completed_date": now - timedelta(days=22),
                "verification_required": False,
                "verified_by": None,
                "notes": "Minor discrepancies resolved",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "DCT-008",
                "trial_id": DUPIXENT_TRIAL,
                "task_name": "DUPIXENT Efficacy Data Validation",
                "description": "Validate all EASI and IGA scores against source documents",
                "listing_id": "DRL-006",
                "assigned_to": "Dr. Michael Park",
                "status": "in_progress",
                "priority": QueryPriority.HIGH,
                "records_to_review": 200,
                "records_cleaned": 110,
                "queries_generated": 9,
                "due_date": now + timedelta(days=14),
                "completed_date": None,
                "verification_required": True,
                "verified_by": None,
                "notes": "SDV for primary efficacy endpoints in progress",
                "created_at": now - timedelta(days=8),
            },
            {
                "id": "DCT-009",
                "trial_id": LIBTAYO_TRIAL,
                "task_name": "LIBTAYO SAE Narrative Review",
                "description": "Review and quality-check all SAE narratives for LIBTAYO",
                "listing_id": "DRL-009",
                "assigned_to": "Dr. Michael Park",
                "status": "completed",
                "priority": QueryPriority.CRITICAL,
                "records_to_review": 67,
                "records_cleaned": 67,
                "queries_generated": 4,
                "due_date": now - timedelta(days=25),
                "completed_date": now - timedelta(days=28),
                "verification_required": True,
                "verified_by": "Dr. Sarah Chen",
                "notes": "All SAE narratives reviewed and finalized",
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "DCT-010",
                "trial_id": EYLEA_TRIAL,
                "task_name": "EYLEA Immunogenicity Data Review",
                "description": "Review immunogenicity lab data for EYLEA prior to database lock",
                "listing_id": "DRL-010",
                "assigned_to": "Jennifer Liu",
                "status": "pending",
                "priority": QueryPriority.MEDIUM,
                "records_to_review": 350,
                "records_cleaned": 0,
                "queries_generated": 0,
                "due_date": now + timedelta(days=30),
                "completed_date": None,
                "verification_required": True,
                "verified_by": None,
                "notes": None,
                "created_at": now - timedelta(days=2),
            },
            {
                "id": "DCT-011",
                "trial_id": LIBTAYO_TRIAL,
                "task_name": "LIBTAYO Vital Signs Cross-Check",
                "description": "Cross-check vital signs against adverse event reports for consistency",
                "listing_id": "DRL-012",
                "assigned_to": "Dr. Sarah Chen",
                "status": "completed",
                "priority": QueryPriority.MEDIUM,
                "records_to_review": 720,
                "records_cleaned": 720,
                "queries_generated": 3,
                "due_date": now - timedelta(days=18),
                "completed_date": now - timedelta(days=20),
                "verification_required": False,
                "verified_by": None,
                "notes": "No significant discrepancies found",
                "created_at": now - timedelta(days=40),
            },
        ]

        for item in cleaning_tasks_data:
            self._data_cleaning_tasks[item["id"]] = DataCleaningTask(**item)

        # --- 10 Edit Checks ---
        edit_checks_data: list[dict] = [
            {
                "id": "EC-001",
                "trial_id": EYLEA_TRIAL,
                "check_name": "Lab Value Range Check",
                "check_description": "Validates laboratory values against clinically plausible ranges",
                "form_name": "Laboratory Results",
                "field_name": "lab_value",
                "severity": EditCheckSeverity.ERROR,
                "check_logic": "IF lab_value < reference_low * 0.1 OR lab_value > reference_high * 10 THEN FIRE",
                "is_active": True,
                "auto_query": True,
                "total_firings": 342,
                "false_positive_count": 28,
                "false_positive_rate": 8.2,
                "last_run_date": now - timedelta(days=1),
                "created_by": "Data Management Lead",
                "approved_by": "Medical Monitor",
                "version": "2.1",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "EC-002",
                "trial_id": DUPIXENT_TRIAL,
                "check_name": "Vital Signs Range Check",
                "check_description": "Validates vital sign measurements against physiological ranges",
                "form_name": "Vital Signs",
                "field_name": "vital_value",
                "severity": EditCheckSeverity.ERROR,
                "check_logic": "IF systolic_bp > 250 OR systolic_bp < 60 OR heart_rate > 200 OR heart_rate < 30 THEN FIRE",
                "is_active": True,
                "auto_query": True,
                "total_firings": 156,
                "false_positive_count": 12,
                "false_positive_rate": 7.7,
                "last_run_date": now - timedelta(days=1),
                "created_by": "Data Management Lead",
                "approved_by": "Medical Monitor",
                "version": "1.5",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "EC-003",
                "trial_id": EYLEA_TRIAL,
                "check_name": "AE Date Consistency",
                "check_description": "Ensures AE onset date is before or equal to AE resolution date",
                "form_name": "Adverse Events",
                "field_name": "ae_onset_date",
                "severity": EditCheckSeverity.HARD_STOP,
                "check_logic": "IF ae_onset_date > ae_resolution_date AND ae_resolution_date IS NOT NULL THEN FIRE",
                "is_active": True,
                "auto_query": True,
                "total_firings": 45,
                "false_positive_count": 2,
                "false_positive_rate": 4.4,
                "last_run_date": now - timedelta(days=1),
                "created_by": "Data Management Lead",
                "approved_by": "Biostatistician",
                "version": "1.0",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "EC-004",
                "trial_id": LIBTAYO_TRIAL,
                "check_name": "SAE Outcome Consistency",
                "check_description": "Validates SAE outcome is consistent with resolution date presence",
                "form_name": "Serious Adverse Events",
                "field_name": "sae_outcome",
                "severity": EditCheckSeverity.ERROR,
                "check_logic": "IF sae_outcome = 'Ongoing' AND sae_end_date IS NOT NULL THEN FIRE",
                "is_active": True,
                "auto_query": True,
                "total_firings": 23,
                "false_positive_count": 1,
                "false_positive_rate": 4.3,
                "last_run_date": now - timedelta(days=2),
                "created_by": "Safety Data Manager",
                "approved_by": "Medical Monitor",
                "version": "1.2",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "EC-005",
                "trial_id": DUPIXENT_TRIAL,
                "check_name": "ConMed Date vs Consent Check",
                "check_description": "Ensures concomitant medication start date is after or on consent date",
                "form_name": "Concomitant Medications",
                "field_name": "medication_start_date",
                "severity": EditCheckSeverity.WARNING,
                "check_logic": "IF medication_start_date < consent_date AND medication_category = 'New' THEN FIRE",
                "is_active": True,
                "auto_query": False,
                "total_firings": 89,
                "false_positive_count": 35,
                "false_positive_rate": 39.3,
                "last_run_date": now - timedelta(days=1),
                "created_by": "Data Management Lead",
                "approved_by": None,
                "version": "1.0",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "EC-006",
                "trial_id": EYLEA_TRIAL,
                "check_name": "Age Eligibility Check",
                "check_description": "Validates subject age meets inclusion criteria (18+)",
                "form_name": "Demographics",
                "field_name": "date_of_birth",
                "severity": EditCheckSeverity.HARD_STOP,
                "check_logic": "IF DATEDIFF(YEAR, date_of_birth, consent_date) < 18 THEN FIRE",
                "is_active": True,
                "auto_query": True,
                "total_firings": 8,
                "false_positive_count": 5,
                "false_positive_rate": 62.5,
                "last_run_date": now - timedelta(days=3),
                "created_by": "Data Management Lead",
                "approved_by": "Medical Monitor",
                "version": "1.0",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "EC-007",
                "trial_id": EYLEA_TRIAL,
                "check_name": "Required Field Check - Demographics",
                "check_description": "Ensures all required demographic fields are populated",
                "form_name": "Demographics",
                "field_name": "gender",
                "severity": EditCheckSeverity.ERROR,
                "check_logic": "IF gender IS NULL OR gender = '' THEN FIRE",
                "is_active": True,
                "auto_query": True,
                "total_firings": 15,
                "false_positive_count": 0,
                "false_positive_rate": 0.0,
                "last_run_date": now - timedelta(days=1),
                "created_by": "Data Management Lead",
                "approved_by": "Data Management Lead",
                "version": "1.0",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "EC-008",
                "trial_id": LIBTAYO_TRIAL,
                "check_name": "Visit Window Compliance Check",
                "check_description": "Flags visits performed outside protocol-specified windows",
                "form_name": "Visit Schedule",
                "field_name": "visit_date",
                "severity": EditCheckSeverity.WARNING,
                "check_logic": "IF visit_date < window_open OR visit_date > window_close THEN FIRE",
                "is_active": True,
                "auto_query": False,
                "total_firings": 210,
                "false_positive_count": 45,
                "false_positive_rate": 21.4,
                "last_run_date": now - timedelta(days=1),
                "created_by": "Clinical Data Manager",
                "approved_by": None,
                "version": "1.3",
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "EC-009",
                "trial_id": DUPIXENT_TRIAL,
                "check_name": "EASI Score Range Check",
                "check_description": "Validates EASI score is within 0-72 range",
                "form_name": "Efficacy Assessment",
                "field_name": "easi_score",
                "severity": EditCheckSeverity.ERROR,
                "check_logic": "IF easi_score < 0 OR easi_score > 72 THEN FIRE",
                "is_active": True,
                "auto_query": True,
                "total_firings": 12,
                "false_positive_count": 0,
                "false_positive_rate": 0.0,
                "last_run_date": now - timedelta(days=2),
                "created_by": "Biostatistician",
                "approved_by": "Medical Monitor",
                "version": "1.0",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "EC-010",
                "trial_id": LIBTAYO_TRIAL,
                "check_name": "Duplicate Record Detection",
                "check_description": "Detects potential duplicate records based on subject, visit, and form",
                "form_name": "All Forms",
                "field_name": "record_id",
                "severity": EditCheckSeverity.INFORMATIONAL,
                "check_logic": "IF COUNT(subject_id, visit_name, form_name) > 1 THEN FIRE",
                "is_active": False,
                "auto_query": False,
                "total_firings": 567,
                "false_positive_count": 480,
                "false_positive_rate": 84.7,
                "last_run_date": now - timedelta(days=30),
                "created_by": "Data Management Lead",
                "approved_by": None,
                "version": "1.0",
                "created_at": now - timedelta(days=65),
            },
        ]

        for item in edit_checks_data:
            self._edit_checks[item["id"]] = EditCheck(**item)

        # --- 10 Reviewer Assignments ---
        reviewer_assignments_data: list[dict] = [
            {
                "id": "RA-001",
                "trial_id": EYLEA_TRIAL,
                "reviewer_name": "Dr. Sarah Chen",
                "reviewer_role": "Lead Data Reviewer",
                "assigned_sites": ["SITE-101", "SITE-103"],
                "assigned_listings": ["DRL-001", "DRL-008", "DRL-012"],
                "assignment_date": now - timedelta(days=60),
                "workload_records": 1054,
                "completed_records": 1010,
                "queries_issued": 32,
                "avg_review_time_minutes": 4.2,
                "is_active": True,
                "last_review_date": now - timedelta(days=1),
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "RA-002",
                "trial_id": EYLEA_TRIAL,
                "reviewer_name": "Dr. Michael Park",
                "reviewer_role": "Senior Data Reviewer",
                "assigned_sites": ["SITE-102", "SITE-104"],
                "assigned_listings": ["DRL-002", "DRL-009"],
                "assignment_date": now - timedelta(days=55),
                "workload_records": 254,
                "completed_records": 217,
                "queries_issued": 25,
                "avg_review_time_minutes": 5.1,
                "is_active": True,
                "last_review_date": now - timedelta(days=2),
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "RA-003",
                "trial_id": EYLEA_TRIAL,
                "reviewer_name": "Jennifer Liu",
                "reviewer_role": "Data Reviewer",
                "assigned_sites": ["SITE-103", "SITE-106"],
                "assigned_listings": ["DRL-003", "DRL-007"],
                "assignment_date": now - timedelta(days=45),
                "workload_records": 2098,
                "completed_records": 1340,
                "queries_issued": 55,
                "avg_review_time_minutes": 3.8,
                "is_active": True,
                "last_review_date": now - timedelta(days=1),
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "RA-004",
                "trial_id": DUPIXENT_TRIAL,
                "reviewer_name": "Dr. Sarah Chen",
                "reviewer_role": "Lead Data Reviewer",
                "assigned_sites": ["SITE-104", "SITE-105"],
                "assigned_listings": ["DRL-004"],
                "assignment_date": now - timedelta(days=50),
                "workload_records": 960,
                "completed_records": 960,
                "queries_issued": 40,
                "avg_review_time_minutes": 4.5,
                "is_active": True,
                "last_review_date": now - timedelta(days=10),
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "RA-005",
                "trial_id": DUPIXENT_TRIAL,
                "reviewer_name": "Dr. Michael Park",
                "reviewer_role": "Senior Data Reviewer",
                "assigned_sites": ["SITE-101"],
                "assigned_listings": ["DRL-006"],
                "assignment_date": now - timedelta(days=20),
                "workload_records": 312,
                "completed_records": 200,
                "queries_issued": 15,
                "avg_review_time_minutes": 6.2,
                "is_active": True,
                "last_review_date": now - timedelta(days=1),
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "RA-006",
                "trial_id": DUPIXENT_TRIAL,
                "reviewer_name": "Jennifer Liu",
                "reviewer_role": "Data Reviewer",
                "assigned_sites": ["SITE-106"],
                "assigned_listings": ["DRL-011"],
                "assignment_date": now - timedelta(days=40),
                "workload_records": 198,
                "completed_records": 198,
                "queries_issued": 8,
                "avg_review_time_minutes": 3.5,
                "is_active": True,
                "last_review_date": now - timedelta(days=8),
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "RA-007",
                "trial_id": LIBTAYO_TRIAL,
                "reviewer_name": "Dr. Sarah Chen",
                "reviewer_role": "Lead Data Reviewer",
                "assigned_sites": ["SITE-107", "SITE-108"],
                "assigned_listings": ["DRL-008"],
                "assignment_date": now - timedelta(days=30),
                "workload_records": 89,
                "completed_records": 45,
                "queries_issued": 15,
                "avg_review_time_minutes": 7.3,
                "is_active": True,
                "last_review_date": now - timedelta(days=1),
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "RA-008",
                "trial_id": LIBTAYO_TRIAL,
                "reviewer_name": "Dr. Michael Park",
                "reviewer_role": "Senior Data Reviewer",
                "assigned_sites": ["SITE-108"],
                "assigned_listings": ["DRL-009"],
                "assignment_date": now - timedelta(days=55),
                "workload_records": 67,
                "completed_records": 67,
                "queries_issued": 2,
                "avg_review_time_minutes": 8.1,
                "is_active": True,
                "last_review_date": now - timedelta(days=18),
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "RA-009",
                "trial_id": LIBTAYO_TRIAL,
                "reviewer_name": "Jennifer Liu",
                "reviewer_role": "Data Reviewer",
                "assigned_sites": ["SITE-106", "SITE-103"],
                "assigned_listings": ["DRL-007", "DRL-012"],
                "assignment_date": now - timedelta(days=35),
                "workload_records": 1298,
                "completed_records": 1170,
                "queries_issued": 55,
                "avg_review_time_minutes": 3.2,
                "is_active": True,
                "last_review_date": now - timedelta(days=1),
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "RA-010",
                "trial_id": EYLEA_TRIAL,
                "reviewer_name": "David Kim",
                "reviewer_role": "Junior Data Reviewer",
                "assigned_sites": ["SITE-104"],
                "assigned_listings": ["DRL-010"],
                "assignment_date": now - timedelta(days=5),
                "workload_records": 350,
                "completed_records": 0,
                "queries_issued": 0,
                "avg_review_time_minutes": None,
                "is_active": False,
                "last_review_date": None,
                "created_at": now - timedelta(days=5),
            },
        ]

        for item in reviewer_assignments_data:
            self._reviewer_assignments[item["id"]] = ReviewerAssignment(**item)

    # ------------------------------------------------------------------
    # Data Review Listings
    # ------------------------------------------------------------------

    def list_data_review_listings(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[DataReviewListing]:
        """List data review listings with optional trial_id filter."""
        with self._lock:
            result = list(self._data_review_listings.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]

        return sorted(result, key=lambda r: r.created_at, reverse=True)

    def get_data_review_listing(self, listing_id: str) -> DataReviewListing | None:
        """Get a single data review listing by ID."""
        with self._lock:
            return self._data_review_listings.get(listing_id)

    def create_data_review_listing(self, payload: DataReviewListingCreate) -> DataReviewListing:
        """Create a new data review listing."""
        now = datetime.now(timezone.utc)
        listing_id = f"DRL-{uuid4().hex[:8].upper()}"
        listing = DataReviewListing(
            id=listing_id,
            trial_id=payload.trial_id,
            listing_type=payload.listing_type,
            listing_name=payload.listing_name,
            site_id=payload.site_id,
            total_records=payload.total_records,
            review_status=ReviewStatus.PENDING,
            reviewed_records=0,
            clean_records=0,
            records_with_queries=0,
            completion_pct=0.0,
            created_at=now,
        )
        with self._lock:
            self._data_review_listings[listing_id] = listing
        logger.info("Created data review listing %s: %s", listing_id, payload.listing_name)
        return listing

    def update_data_review_listing(
        self, listing_id: str, payload: DataReviewListingUpdate
    ) -> DataReviewListing | None:
        """Update an existing data review listing."""
        with self._lock:
            existing = self._data_review_listings.get(listing_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DataReviewListing(**data)
            self._data_review_listings[listing_id] = updated
        return updated

    def delete_data_review_listing(self, listing_id: str) -> bool:
        """Delete a data review listing. Returns True if deleted."""
        with self._lock:
            if listing_id in self._data_review_listings:
                del self._data_review_listings[listing_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Data Queries
    # ------------------------------------------------------------------

    def list_data_queries(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[DataQuery]:
        """List data queries with optional trial_id filter."""
        with self._lock:
            result = list(self._data_queries.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]

        return sorted(result, key=lambda r: r.created_at, reverse=True)

    def get_data_query(self, query_id: str) -> DataQuery | None:
        """Get a single data query by ID."""
        with self._lock:
            return self._data_queries.get(query_id)

    def create_data_query(self, payload: DataQueryCreate) -> DataQuery:
        """Create a new data query."""
        now = datetime.now(timezone.utc)
        query_id = f"DQ-{uuid4().hex[:8].upper()}"
        query = DataQuery(
            id=query_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            subject_id=payload.subject_id,
            form_name=payload.form_name,
            field_name=payload.field_name,
            query_text=payload.query_text,
            issued_by=payload.issued_by,
            listing_id=payload.listing_id,
            priority=payload.priority,
            query_status=QueryStatus.OPEN,
            issued_date=now,
            days_open=0,
            requery_count=0,
            created_at=now,
        )
        with self._lock:
            self._data_queries[query_id] = query
        logger.info("Created data query %s for subject %s", query_id, payload.subject_id)
        return query

    def update_data_query(self, query_id: str, payload: DataQueryUpdate) -> DataQuery | None:
        """Update an existing data query."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._data_queries.get(query_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set response_date when response_text is provided
            if "response_text" in updates and updates["response_text"] and existing.response_date is None:
                updates["response_date"] = now

            # Auto-set closed_date when status goes to closed
            if "query_status" in updates:
                new_status = updates["query_status"]
                if isinstance(new_status, str):
                    new_status = QueryStatus(new_status)
                if new_status == QueryStatus.CLOSED and existing.query_status != QueryStatus.CLOSED:
                    updates["closed_date"] = now

            data.update(updates)
            updated = DataQuery(**data)
            self._data_queries[query_id] = updated
        return updated

    def delete_data_query(self, query_id: str) -> bool:
        """Delete a data query. Returns True if deleted."""
        with self._lock:
            if query_id in self._data_queries:
                del self._data_queries[query_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Data Cleaning Tasks
    # ------------------------------------------------------------------

    def list_data_cleaning_tasks(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[DataCleaningTask]:
        """List data cleaning tasks with optional trial_id filter."""
        with self._lock:
            result = list(self._data_cleaning_tasks.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]

        return sorted(result, key=lambda r: r.created_at, reverse=True)

    def get_data_cleaning_task(self, task_id: str) -> DataCleaningTask | None:
        """Get a single data cleaning task by ID."""
        with self._lock:
            return self._data_cleaning_tasks.get(task_id)

    def create_data_cleaning_task(self, payload: DataCleaningTaskCreate) -> DataCleaningTask:
        """Create a new data cleaning task."""
        now = datetime.now(timezone.utc)
        task_id = f"DCT-{uuid4().hex[:8].upper()}"
        task = DataCleaningTask(
            id=task_id,
            trial_id=payload.trial_id,
            task_name=payload.task_name,
            description=payload.description,
            assigned_to=payload.assigned_to,
            listing_id=payload.listing_id,
            records_to_review=payload.records_to_review,
            due_date=payload.due_date,
            status="pending",
            priority=QueryPriority.MEDIUM,
            records_cleaned=0,
            queries_generated=0,
            created_at=now,
        )
        with self._lock:
            self._data_cleaning_tasks[task_id] = task
        logger.info("Created data cleaning task %s: %s", task_id, payload.task_name)
        return task

    def update_data_cleaning_task(
        self, task_id: str, payload: DataCleaningTaskUpdate
    ) -> DataCleaningTask | None:
        """Update an existing data cleaning task."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._data_cleaning_tasks.get(task_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set completed_date when status goes to completed
            if "status" in updates and updates["status"] == "completed" and existing.status != "completed":
                updates["completed_date"] = now

            data.update(updates)
            updated = DataCleaningTask(**data)
            self._data_cleaning_tasks[task_id] = updated
        return updated

    def delete_data_cleaning_task(self, task_id: str) -> bool:
        """Delete a data cleaning task. Returns True if deleted."""
        with self._lock:
            if task_id in self._data_cleaning_tasks:
                del self._data_cleaning_tasks[task_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Edit Checks
    # ------------------------------------------------------------------

    def list_edit_checks(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[EditCheck]:
        """List edit checks with optional trial_id filter."""
        with self._lock:
            result = list(self._edit_checks.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]

        return sorted(result, key=lambda r: r.id)

    def get_edit_check(self, check_id: str) -> EditCheck | None:
        """Get a single edit check by ID."""
        with self._lock:
            return self._edit_checks.get(check_id)

    def create_edit_check(self, payload: EditCheckCreate) -> EditCheck:
        """Create a new edit check."""
        now = datetime.now(timezone.utc)
        check_id = f"EC-{uuid4().hex[:8].upper()}"
        check = EditCheck(
            id=check_id,
            trial_id=payload.trial_id,
            check_name=payload.check_name,
            check_description=payload.check_description,
            form_name=payload.form_name,
            field_name=payload.field_name,
            check_logic=payload.check_logic,
            created_by=payload.created_by,
            severity=payload.severity,
            is_active=True,
            auto_query=False,
            total_firings=0,
            false_positive_count=0,
            false_positive_rate=0.0,
            version="1.0",
            created_at=now,
        )
        with self._lock:
            self._edit_checks[check_id] = check
        logger.info("Created edit check %s: %s", check_id, payload.check_name)
        return check

    def update_edit_check(self, check_id: str, payload: EditCheckUpdate) -> EditCheck | None:
        """Update an existing edit check."""
        with self._lock:
            existing = self._edit_checks.get(check_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = EditCheck(**data)
            self._edit_checks[check_id] = updated
        return updated

    def delete_edit_check(self, check_id: str) -> bool:
        """Delete an edit check. Returns True if deleted."""
        with self._lock:
            if check_id in self._edit_checks:
                del self._edit_checks[check_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Reviewer Assignments
    # ------------------------------------------------------------------

    def list_reviewer_assignments(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[ReviewerAssignment]:
        """List reviewer assignments with optional trial_id filter."""
        with self._lock:
            result = list(self._reviewer_assignments.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]

        return sorted(result, key=lambda r: r.assignment_date, reverse=True)

    def get_reviewer_assignment(self, assignment_id: str) -> ReviewerAssignment | None:
        """Get a single reviewer assignment by ID."""
        with self._lock:
            return self._reviewer_assignments.get(assignment_id)

    def create_reviewer_assignment(self, payload: ReviewerAssignmentCreate) -> ReviewerAssignment:
        """Create a new reviewer assignment."""
        now = datetime.now(timezone.utc)
        assignment_id = f"RA-{uuid4().hex[:8].upper()}"
        assignment = ReviewerAssignment(
            id=assignment_id,
            trial_id=payload.trial_id,
            reviewer_name=payload.reviewer_name,
            reviewer_role=payload.reviewer_role,
            assigned_sites=payload.assigned_sites,
            assignment_date=now,
            workload_records=0,
            completed_records=0,
            queries_issued=0,
            is_active=True,
            created_at=now,
        )
        with self._lock:
            self._reviewer_assignments[assignment_id] = assignment
        logger.info("Created reviewer assignment %s: %s", assignment_id, payload.reviewer_name)
        return assignment

    def update_reviewer_assignment(
        self, assignment_id: str, payload: ReviewerAssignmentUpdate
    ) -> ReviewerAssignment | None:
        """Update an existing reviewer assignment."""
        with self._lock:
            existing = self._reviewer_assignments.get(assignment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ReviewerAssignment(**data)
            self._reviewer_assignments[assignment_id] = updated
        return updated

    def delete_reviewer_assignment(self, assignment_id: str) -> bool:
        """Delete a reviewer assignment. Returns True if deleted."""
        with self._lock:
            if assignment_id in self._reviewer_assignments:
                del self._reviewer_assignments[assignment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> ClinicalDataReviewMetrics:
        """Compute aggregated clinical data review metrics."""
        with self._lock:
            listings = list(self._data_review_listings.values())
            queries = list(self._data_queries.values())
            cleaning_tasks = list(self._data_cleaning_tasks.values())
            edit_checks = list(self._edit_checks.values())
            reviewers = list(self._reviewer_assignments.values())

        # Listings by type
        listings_by_type: dict[str, int] = {}
        for listing in listings:
            key = listing.listing_type.value
            listings_by_type[key] = listings_by_type.get(key, 0) + 1

        # Listings by status
        listings_by_status: dict[str, int] = {}
        for listing in listings:
            key = listing.review_status.value
            listings_by_status[key] = listings_by_status.get(key, 0) + 1

        # Overall review completion
        total_records = sum(l.total_records for l in listings)
        reviewed_records = sum(l.reviewed_records for l in listings)
        overall_completion = round(
            (reviewed_records / max(1, total_records)) * 100.0, 1
        )

        # Queries by status
        queries_by_status: dict[str, int] = {}
        for query in queries:
            key = query.query_status.value
            queries_by_status[key] = queries_by_status.get(key, 0) + 1

        # Queries by priority
        queries_by_priority: dict[str, int] = {}
        for query in queries:
            key = query.priority.value
            queries_by_priority[key] = queries_by_priority.get(key, 0) + 1

        # Average query resolution days (for closed queries)
        closed_queries = [q for q in queries if q.query_status == QueryStatus.CLOSED]
        if closed_queries:
            avg_resolution = round(
                sum(q.days_open for q in closed_queries) / len(closed_queries), 1
            )
        else:
            avg_resolution = 0.0

        # Cleaning tasks completed
        cleaning_completed = sum(1 for t in cleaning_tasks if t.status == "completed")

        # Edit checks
        active_edit_checks = sum(1 for ec in edit_checks if ec.is_active)
        fp_rates = [ec.false_positive_rate for ec in edit_checks if ec.is_active]
        avg_fp_rate = round(sum(fp_rates) / max(1, len(fp_rates)), 1)

        # Reviewers
        active_reviewers = sum(1 for r in reviewers if r.is_active)

        return ClinicalDataReviewMetrics(
            total_listings=len(listings),
            listings_by_type=listings_by_type,
            listings_by_status=listings_by_status,
            overall_review_completion_pct=overall_completion,
            total_queries=len(queries),
            queries_by_status=queries_by_status,
            queries_by_priority=queries_by_priority,
            avg_query_resolution_days=avg_resolution,
            total_cleaning_tasks=len(cleaning_tasks),
            cleaning_tasks_completed=cleaning_completed,
            total_edit_checks=len(edit_checks),
            active_edit_checks=active_edit_checks,
            avg_false_positive_rate=avg_fp_rate,
            total_reviewers=len(reviewers),
            active_reviewers=active_reviewers,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: ClinicalDataReviewService | None = None
_instance_lock = threading.Lock()


def get_clinical_data_review_service() -> ClinicalDataReviewService:
    """Return the singleton ClinicalDataReviewService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ClinicalDataReviewService()
    return _instance


def reset_clinical_data_review_service() -> ClinicalDataReviewService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = ClinicalDataReviewService()
    return _instance
