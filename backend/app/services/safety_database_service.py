"""Safety Database & CIOMS Reporting Service (CLINICAL-23).

Manages safety database operations including individual case safety reports
(ICSRs), regulatory submissions with expedited timelines (15-day for serious
unexpected, 7-day for fatal/life-threatening), CIOMS form generation,
aggregate safety reports (DSUR, PSUR, PBRER, ASR), and safety metrics.

Usage:
    from app.services.safety_database_service import (
        get_safety_db_service,
    )

    svc = get_safety_db_service()
    cases = svc.list_cases()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.safety_database import (
    AggregateReport,
    AggregateReportCreate,
    AggregateReportStatus,
    AggregateReportType,
    AggregateReportUpdate,
    CaseType,
    CIOMSForm,
    CIOMSFormType,
    EventOutcome,
    Expectedness,
    Relatedness,
    RegulatoryAuthority,
    RegulatorySubmission,
    RegulatorySubmissionCreate,
    RegulatorySubmissionUpdate,
    ReporterType,
    ReportingStatus,
    SafetyCase,
    SafetyCaseCreate,
    SafetyCaseUpdate,
    SafetyDatabaseMetrics,
    Seriousness,
    SubmissionStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

# Expedited reporting timelines (calendar days from sponsor awareness)
EXPEDITED_FATAL_DAYS = 7
EXPEDITED_SERIOUS_DAYS = 15

# Aggregate report due threshold (days)
AGGREGATE_REPORT_DUE_THRESHOLD_DAYS = 60


class SafetyDatabaseService:
    """In-memory Safety Database engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._cases: dict[str, SafetyCase] = {}
        self._submissions: dict[str, RegulatorySubmission] = {}
        self._aggregate_reports: dict[str, AggregateReport] = {}
        self._case_counter: int = 0
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic safety database data across clinical trials."""
        now = datetime.now(timezone.utc)

        # --- 25 Safety Cases ---
        cases_data = [
            {
                "id": "SC-001",
                "case_number": "CASE-2025-0001",
                "trial_id": EYLEA_TRIAL,
                "patient_id": "PAT-E001",
                "site_id": "SITE-101",
                "case_type": CaseType.INITIAL,
                "initial_receipt_date": now - timedelta(days=180),
                "most_recent_date": now - timedelta(days=175),
                "seriousness_criteria": [Seriousness.HOSPITALIZATION],
                "expectedness": Expectedness.EXPECTED,
                "relatedness": Relatedness.POSSIBLY_RELATED,
                "reporter_type": ReporterType.PHYSICIAN,
                "narrative": "72-year-old male experienced vitreous hemorrhage 3 days after intravitreal injection. Hospitalized for observation. Resolved within 5 days.",
                "meddra_pt": "Vitreous haemorrhage",
                "meddra_soc": "Eye disorders",
                "onset_date": now - timedelta(days=183),
                "resolution_date": now - timedelta(days=178),
                "outcome": EventOutcome.RECOVERED,
                "reporting_status": ReportingStatus.CLOSED,
            },
            {
                "id": "SC-002",
                "case_number": "CASE-2025-0002",
                "trial_id": EYLEA_TRIAL,
                "patient_id": "PAT-E002",
                "site_id": "SITE-101",
                "case_type": CaseType.INITIAL,
                "initial_receipt_date": now - timedelta(days=160),
                "most_recent_date": now - timedelta(days=155),
                "seriousness_criteria": [Seriousness.LIFE_THREATENING],
                "expectedness": Expectedness.UNEXPECTED,
                "relatedness": Relatedness.RELATED,
                "reporter_type": ReporterType.PHYSICIAN,
                "narrative": "65-year-old female developed retinal detachment with vision loss 10 days post-injection. Emergency vitrectomy performed. SUSAR filed.",
                "meddra_pt": "Retinal detachment",
                "meddra_soc": "Eye disorders",
                "onset_date": now - timedelta(days=163),
                "resolution_date": now - timedelta(days=140),
                "outcome": EventOutcome.RECOVERED,
                "reporting_status": ReportingStatus.SUBMITTED_TO_AUTHORITY,
            },
            {
                "id": "SC-003",
                "case_number": "CASE-2025-0003",
                "trial_id": EYLEA_TRIAL,
                "patient_id": "PAT-E003",
                "site_id": "SITE-102",
                "case_type": CaseType.INITIAL,
                "initial_receipt_date": now - timedelta(days=140),
                "most_recent_date": now - timedelta(days=135),
                "seriousness_criteria": [Seriousness.MEDICALLY_IMPORTANT],
                "expectedness": Expectedness.EXPECTED,
                "relatedness": Relatedness.POSSIBLY_RELATED,
                "reporter_type": ReporterType.PHYSICIAN,
                "narrative": "68-year-old male developed elevated intraocular pressure (32 mmHg) after injection. Managed with topical anti-glaucoma medication.",
                "meddra_pt": "Intraocular pressure increased",
                "meddra_soc": "Eye disorders",
                "onset_date": now - timedelta(days=141),
                "resolution_date": now - timedelta(days=127),
                "outcome": EventOutcome.RECOVERED,
                "reporting_status": ReportingStatus.CLOSED,
            },
            {
                "id": "SC-004",
                "case_number": "CASE-2025-0004",
                "trial_id": DUPIXENT_TRIAL,
                "patient_id": "PAT-D001",
                "site_id": "SITE-103",
                "case_type": CaseType.INITIAL,
                "initial_receipt_date": now - timedelta(days=130),
                "most_recent_date": now - timedelta(days=125),
                "seriousness_criteria": [Seriousness.HOSPITALIZATION],
                "expectedness": Expectedness.EXPECTED,
                "relatedness": Relatedness.RELATED,
                "reporter_type": ReporterType.PHYSICIAN,
                "narrative": "45-year-old female with moderate-to-severe atopic dermatitis developed injection site reaction with cellulitis requiring IV antibiotics.",
                "meddra_pt": "Injection site cellulitis",
                "meddra_soc": "General disorders and administration site conditions",
                "onset_date": now - timedelta(days=132),
                "resolution_date": now - timedelta(days=122),
                "outcome": EventOutcome.RECOVERED,
                "reporting_status": ReportingStatus.SUBMITTED_TO_AUTHORITY,
            },
            {
                "id": "SC-005",
                "case_number": "CASE-2025-0005",
                "trial_id": DUPIXENT_TRIAL,
                "patient_id": "PAT-D002",
                "site_id": "SITE-103",
                "case_type": CaseType.INITIAL,
                "initial_receipt_date": now - timedelta(days=120),
                "most_recent_date": now - timedelta(days=115),
                "seriousness_criteria": [Seriousness.MEDICALLY_IMPORTANT],
                "expectedness": Expectedness.EXPECTED,
                "relatedness": Relatedness.POSSIBLY_RELATED,
                "reporter_type": ReporterType.NURSE,
                "narrative": "38-year-old male developed conjunctivitis 6 weeks into treatment. Known class effect of dupilumab. Managed with artificial tears.",
                "meddra_pt": "Conjunctivitis",
                "meddra_soc": "Eye disorders",
                "onset_date": now - timedelta(days=125),
                "resolution_date": now - timedelta(days=100),
                "outcome": EventOutcome.RECOVERED,
                "reporting_status": ReportingStatus.CLOSED,
            },
            {
                "id": "SC-006",
                "case_number": "CASE-2025-0006",
                "trial_id": DUPIXENT_TRIAL,
                "patient_id": "PAT-D003",
                "site_id": "SITE-104",
                "case_type": CaseType.INITIAL,
                "initial_receipt_date": now - timedelta(days=100),
                "most_recent_date": now - timedelta(days=95),
                "seriousness_criteria": [Seriousness.LIFE_THREATENING, Seriousness.HOSPITALIZATION],
                "expectedness": Expectedness.UNEXPECTED,
                "relatedness": Relatedness.POSSIBLY_RELATED,
                "reporter_type": ReporterType.PHYSICIAN,
                "narrative": "52-year-old female experienced anaphylaxis within 30 minutes of injection. Emergency epinephrine administered. SUSAR reported.",
                "meddra_pt": "Anaphylactic reaction",
                "meddra_soc": "Immune system disorders",
                "onset_date": now - timedelta(days=100),
                "resolution_date": now - timedelta(days=99),
                "outcome": EventOutcome.RECOVERED,
                "reporting_status": ReportingStatus.SUBMITTED_TO_AUTHORITY,
            },
            {
                "id": "SC-007",
                "case_number": "CASE-2025-0007",
                "trial_id": LIBTAYO_TRIAL,
                "patient_id": "PAT-L001",
                "site_id": "SITE-105",
                "case_type": CaseType.INITIAL,
                "initial_receipt_date": now - timedelta(days=90),
                "most_recent_date": now - timedelta(days=85),
                "seriousness_criteria": [Seriousness.HOSPITALIZATION],
                "expectedness": Expectedness.EXPECTED,
                "relatedness": Relatedness.RELATED,
                "reporter_type": ReporterType.PHYSICIAN,
                "narrative": "67-year-old male with advanced CSCC developed immune-related pneumonitis (Grade 3). Cemiplimab held, started IV methylprednisolone.",
                "meddra_pt": "Pneumonitis",
                "meddra_soc": "Respiratory, thoracic and mediastinal disorders",
                "onset_date": now - timedelta(days=93),
                "resolution_date": now - timedelta(days=65),
                "outcome": EventOutcome.RECOVERED,
                "reporting_status": ReportingStatus.SUBMITTED_TO_AUTHORITY,
            },
            {
                "id": "SC-008",
                "case_number": "CASE-2025-0008",
                "trial_id": LIBTAYO_TRIAL,
                "patient_id": "PAT-L002",
                "site_id": "SITE-105",
                "case_type": CaseType.INITIAL,
                "initial_receipt_date": now - timedelta(days=80),
                "most_recent_date": now - timedelta(days=75),
                "seriousness_criteria": [Seriousness.DEATH],
                "expectedness": Expectedness.UNEXPECTED,
                "relatedness": Relatedness.POSSIBLY_RELATED,
                "reporter_type": ReporterType.PHYSICIAN,
                "narrative": "73-year-old male developed fulminant myocarditis. Despite aggressive treatment including high-dose steroids and plasmapheresis, patient expired.",
                "meddra_pt": "Myocarditis",
                "meddra_soc": "Cardiac disorders",
                "onset_date": now - timedelta(days=82),
                "resolution_date": now - timedelta(days=75),
                "outcome": EventOutcome.FATAL,
                "reporting_status": ReportingStatus.SUBMITTED_TO_AUTHORITY,
            },
            {
                "id": "SC-009",
                "case_number": "CASE-2025-0009",
                "trial_id": LIBTAYO_TRIAL,
                "patient_id": "PAT-L003",
                "site_id": "SITE-106",
                "case_type": CaseType.INITIAL,
                "initial_receipt_date": now - timedelta(days=70),
                "most_recent_date": now - timedelta(days=65),
                "seriousness_criteria": [Seriousness.HOSPITALIZATION],
                "expectedness": Expectedness.EXPECTED,
                "relatedness": Relatedness.RELATED,
                "reporter_type": ReporterType.PHYSICIAN,
                "narrative": "61-year-old female developed immune-related hepatitis (Grade 3). ALT/AST elevated >5x ULN. Cemiplimab held, started corticosteroids.",
                "meddra_pt": "Hepatitis",
                "meddra_soc": "Hepatobiliary disorders",
                "onset_date": now - timedelta(days=73),
                "resolution_date": None,
                "outcome": EventOutcome.RECOVERING,
                "reporting_status": ReportingStatus.SUBMITTED_TO_AUTHORITY,
            },
            {
                "id": "SC-010",
                "case_number": "CASE-2025-0010",
                "trial_id": LIBTAYO_TRIAL,
                "patient_id": "PAT-L004",
                "site_id": "SITE-106",
                "case_type": CaseType.INITIAL,
                "initial_receipt_date": now - timedelta(days=60),
                "most_recent_date": now - timedelta(days=55),
                "seriousness_criteria": [Seriousness.MEDICALLY_IMPORTANT],
                "expectedness": Expectedness.EXPECTED,
                "relatedness": Relatedness.RELATED,
                "reporter_type": ReporterType.PHYSICIAN,
                "narrative": "58-year-old male developed Grade 2 hypothyroidism. Started levothyroxine. Cemiplimab continued.",
                "meddra_pt": "Hypothyroidism",
                "meddra_soc": "Endocrine disorders",
                "onset_date": now - timedelta(days=63),
                "resolution_date": None,
                "outcome": EventOutcome.NOT_RECOVERED,
                "reporting_status": ReportingStatus.CLOSED,
            },
            {
                "id": "SC-011",
                "case_number": "CASE-2025-0011",
                "trial_id": EYLEA_TRIAL,
                "patient_id": "PAT-E004",
                "site_id": "SITE-102",
                "case_type": CaseType.FOLLOW_UP,
                "initial_receipt_date": now - timedelta(days=155),
                "most_recent_date": now - timedelta(days=50),
                "seriousness_criteria": [Seriousness.LIFE_THREATENING],
                "expectedness": Expectedness.UNEXPECTED,
                "relatedness": Relatedness.RELATED,
                "reporter_type": ReporterType.PHYSICIAN,
                "narrative": "Follow-up report on retinal detachment case. Additional information from ophthalmology consult confirming tractional component.",
                "meddra_pt": "Retinal detachment",
                "meddra_soc": "Eye disorders",
                "onset_date": now - timedelta(days=158),
                "resolution_date": now - timedelta(days=130),
                "outcome": EventOutcome.RECOVERED,
                "reporting_status": ReportingStatus.SUBMITTED_TO_AUTHORITY,
            },
            {
                "id": "SC-012",
                "case_number": "CASE-2025-0012",
                "trial_id": DUPIXENT_TRIAL,
                "patient_id": "PAT-D004",
                "site_id": "SITE-104",
                "case_type": CaseType.INITIAL,
                "initial_receipt_date": now - timedelta(days=45),
                "most_recent_date": now - timedelta(days=40),
                "seriousness_criteria": [Seriousness.HOSPITALIZATION],
                "expectedness": Expectedness.UNEXPECTED,
                "relatedness": Relatedness.UNLIKELY_RELATED,
                "reporter_type": ReporterType.PHYSICIAN,
                "narrative": "40-year-old male hospitalized with eosinophilic pneumonia. Temporal association with dupilumab initiation. Under investigation.",
                "meddra_pt": "Eosinophilic pneumonia",
                "meddra_soc": "Respiratory, thoracic and mediastinal disorders",
                "onset_date": now - timedelta(days=47),
                "resolution_date": None,
                "outcome": EventOutcome.RECOVERING,
                "reporting_status": ReportingStatus.SUBMITTED_TO_SPONSOR,
            },
            {
                "id": "SC-013",
                "case_number": "CASE-2025-0013",
                "trial_id": LIBTAYO_TRIAL,
                "patient_id": "PAT-L005",
                "site_id": "SITE-107",
                "case_type": CaseType.INITIAL,
                "initial_receipt_date": now - timedelta(days=40),
                "most_recent_date": now - timedelta(days=35),
                "seriousness_criteria": [Seriousness.DEATH],
                "expectedness": Expectedness.EXPECTED,
                "relatedness": Relatedness.UNRELATED,
                "reporter_type": ReporterType.PHYSICIAN,
                "narrative": "78-year-old male with advanced CSCC. Disease progression with metastatic spread. Death attributed to underlying malignancy, not study drug.",
                "meddra_pt": "Malignant neoplasm progression",
                "meddra_soc": "Neoplasms benign, malignant and unspecified",
                "onset_date": now - timedelta(days=42),
                "resolution_date": now - timedelta(days=35),
                "outcome": EventOutcome.FATAL,
                "reporting_status": ReportingStatus.CLOSED,
            },
            {
                "id": "SC-014",
                "case_number": "CASE-2025-0014",
                "trial_id": EYLEA_TRIAL,
                "patient_id": "PAT-E005",
                "site_id": "SITE-108",
                "case_type": CaseType.INITIAL,
                "initial_receipt_date": now - timedelta(days=35),
                "most_recent_date": now - timedelta(days=30),
                "seriousness_criteria": [Seriousness.MEDICALLY_IMPORTANT],
                "expectedness": Expectedness.EXPECTED,
                "relatedness": Relatedness.RELATED,
                "reporter_type": ReporterType.NURSE,
                "narrative": "70-year-old female developed endophthalmitis 2 days post-injection. Treated with intravitreal antibiotics.",
                "meddra_pt": "Endophthalmitis",
                "meddra_soc": "Eye disorders",
                "onset_date": now - timedelta(days=37),
                "resolution_date": now - timedelta(days=20),
                "outcome": EventOutcome.RECOVERED,
                "reporting_status": ReportingStatus.SUBMITTED_TO_AUTHORITY,
            },
            {
                "id": "SC-015",
                "case_number": "CASE-2025-0015",
                "trial_id": DUPIXENT_TRIAL,
                "patient_id": "PAT-D005",
                "site_id": "SITE-103",
                "case_type": CaseType.INITIAL,
                "initial_receipt_date": now - timedelta(days=30),
                "most_recent_date": now - timedelta(days=25),
                "seriousness_criteria": [],
                "expectedness": Expectedness.EXPECTED,
                "relatedness": Relatedness.RELATED,
                "reporter_type": ReporterType.PATIENT,
                "narrative": "33-year-old female reported persistent injection site pain lasting >7 days. Non-serious AE. Managed with ice and OTC analgesics.",
                "meddra_pt": "Injection site pain",
                "meddra_soc": "General disorders and administration site conditions",
                "onset_date": now - timedelta(days=31),
                "resolution_date": now - timedelta(days=24),
                "outcome": EventOutcome.RECOVERED,
                "reporting_status": ReportingStatus.CLOSED,
            },
            {
                "id": "SC-016",
                "case_number": "CASE-2025-0016",
                "trial_id": LIBTAYO_TRIAL,
                "patient_id": "PAT-L006",
                "site_id": "SITE-107",
                "case_type": CaseType.INITIAL,
                "initial_receipt_date": now - timedelta(days=25),
                "most_recent_date": now - timedelta(days=20),
                "seriousness_criteria": [Seriousness.HOSPITALIZATION],
                "expectedness": Expectedness.EXPECTED,
                "relatedness": Relatedness.RELATED,
                "reporter_type": ReporterType.PHYSICIAN,
                "narrative": "64-year-old female developed immune-related colitis (Grade 3). Bloody diarrhea, 8 episodes/day. Admitted for IV steroids and infliximab.",
                "meddra_pt": "Colitis",
                "meddra_soc": "Gastrointestinal disorders",
                "onset_date": now - timedelta(days=27),
                "resolution_date": None,
                "outcome": EventOutcome.RECOVERING,
                "reporting_status": ReportingStatus.SUBMITTED_TO_AUTHORITY,
            },
            {
                "id": "SC-017",
                "case_number": "CASE-2025-0017",
                "trial_id": EYLEA_TRIAL,
                "patient_id": "PAT-E006",
                "site_id": "SITE-101",
                "case_type": CaseType.INITIAL,
                "initial_receipt_date": now - timedelta(days=20),
                "most_recent_date": now - timedelta(days=15),
                "seriousness_criteria": [Seriousness.DISABILITY],
                "expectedness": Expectedness.UNEXPECTED,
                "relatedness": Relatedness.POSSIBLY_RELATED,
                "reporter_type": ReporterType.PHYSICIAN,
                "narrative": "75-year-old male developed persistent visual field defect after injection. Significant impairment of daily activities. SUSAR evaluation ongoing.",
                "meddra_pt": "Visual field defect",
                "meddra_soc": "Eye disorders",
                "onset_date": now - timedelta(days=22),
                "resolution_date": None,
                "outcome": EventOutcome.NOT_RECOVERED,
                "reporting_status": ReportingStatus.SUBMITTED_TO_SPONSOR,
            },
            {
                "id": "SC-018",
                "case_number": "CASE-2025-0018",
                "trial_id": DUPIXENT_TRIAL,
                "patient_id": "PAT-D006",
                "site_id": "SITE-104",
                "case_type": CaseType.INITIAL,
                "initial_receipt_date": now - timedelta(days=18),
                "most_recent_date": now - timedelta(days=13),
                "seriousness_criteria": [Seriousness.MEDICALLY_IMPORTANT],
                "expectedness": Expectedness.EXPECTED,
                "relatedness": Relatedness.POSSIBLY_RELATED,
                "reporter_type": ReporterType.PHARMACIST,
                "narrative": "29-year-old female developed herpes zoster reactivation. Treated with valacyclovir. Dupilumab held temporarily.",
                "meddra_pt": "Herpes zoster",
                "meddra_soc": "Infections and infestations",
                "onset_date": now - timedelta(days=20),
                "resolution_date": None,
                "outcome": EventOutcome.RECOVERING,
                "reporting_status": ReportingStatus.SUBMITTED_TO_SPONSOR,
            },
            {
                "id": "SC-019",
                "case_number": "CASE-2025-0019",
                "trial_id": LIBTAYO_TRIAL,
                "patient_id": "PAT-L007",
                "site_id": "SITE-105",
                "case_type": CaseType.INITIAL,
                "initial_receipt_date": now - timedelta(days=15),
                "most_recent_date": now - timedelta(days=10),
                "seriousness_criteria": [Seriousness.HOSPITALIZATION, Seriousness.LIFE_THREATENING],
                "expectedness": Expectedness.UNEXPECTED,
                "relatedness": Relatedness.RELATED,
                "reporter_type": ReporterType.PHYSICIAN,
                "narrative": "70-year-old female developed immune-related nephritis with acute kidney injury (creatinine 5.2). Dialysis initiated. SUSAR expedited.",
                "meddra_pt": "Nephritis",
                "meddra_soc": "Renal and urinary disorders",
                "onset_date": now - timedelta(days=17),
                "resolution_date": None,
                "outcome": EventOutcome.NOT_RECOVERED,
                "reporting_status": ReportingStatus.SUBMITTED_TO_AUTHORITY,
            },
            {
                "id": "SC-020",
                "case_number": "CASE-2025-0020",
                "trial_id": EYLEA_TRIAL,
                "patient_id": "PAT-E007",
                "site_id": "SITE-108",
                "case_type": CaseType.INITIAL,
                "initial_receipt_date": now - timedelta(days=12),
                "most_recent_date": now - timedelta(days=7),
                "seriousness_criteria": [],
                "expectedness": Expectedness.EXPECTED,
                "relatedness": Relatedness.RELATED,
                "reporter_type": ReporterType.PHYSICIAN,
                "narrative": "66-year-old female reported transient floaters and mild eye irritation post-injection. Non-serious. Self-resolved.",
                "meddra_pt": "Vitreous floaters",
                "meddra_soc": "Eye disorders",
                "onset_date": now - timedelta(days=12),
                "resolution_date": now - timedelta(days=9),
                "outcome": EventOutcome.RECOVERED,
                "reporting_status": ReportingStatus.CLOSED,
            },
            {
                "id": "SC-021",
                "case_number": "CASE-2025-0021",
                "trial_id": DUPIXENT_TRIAL,
                "patient_id": "PAT-D007",
                "site_id": "SITE-103",
                "case_type": CaseType.AMENDMENT,
                "initial_receipt_date": now - timedelta(days=125),
                "most_recent_date": now - timedelta(days=5),
                "seriousness_criteria": [Seriousness.MEDICALLY_IMPORTANT],
                "expectedness": Expectedness.EXPECTED,
                "relatedness": Relatedness.RELATED,
                "reporter_type": ReporterType.PHYSICIAN,
                "narrative": "Amendment to case CASE-2025-0005. Updated causality assessment from possibly related to related based on rechallenge data.",
                "meddra_pt": "Conjunctivitis",
                "meddra_soc": "Eye disorders",
                "onset_date": now - timedelta(days=130),
                "resolution_date": now - timedelta(days=100),
                "outcome": EventOutcome.RECOVERED,
                "reporting_status": ReportingStatus.SUBMITTED_TO_AUTHORITY,
            },
            {
                "id": "SC-022",
                "case_number": "CASE-2026-0001",
                "trial_id": LIBTAYO_TRIAL,
                "patient_id": "PAT-L008",
                "site_id": "SITE-106",
                "case_type": CaseType.INITIAL,
                "initial_receipt_date": now - timedelta(days=8),
                "most_recent_date": now - timedelta(days=3),
                "seriousness_criteria": [Seriousness.HOSPITALIZATION],
                "expectedness": Expectedness.EXPECTED,
                "relatedness": Relatedness.RELATED,
                "reporter_type": ReporterType.PHYSICIAN,
                "narrative": "55-year-old male developed Grade 3 immune-related dermatitis. Extensive bullous eruption requiring hospitalization and systemic immunosuppression.",
                "meddra_pt": "Dermatitis bullous",
                "meddra_soc": "Skin and subcutaneous tissue disorders",
                "onset_date": now - timedelta(days=10),
                "resolution_date": None,
                "outcome": EventOutcome.RECOVERING,
                "reporting_status": ReportingStatus.SUBMITTED_TO_SPONSOR,
            },
            {
                "id": "SC-023",
                "case_number": "CASE-2026-0002",
                "trial_id": EYLEA_TRIAL,
                "patient_id": "PAT-E008",
                "site_id": "SITE-101",
                "case_type": CaseType.INITIAL,
                "initial_receipt_date": now - timedelta(days=5),
                "most_recent_date": now - timedelta(days=2),
                "seriousness_criteria": [Seriousness.CONGENITAL_ANOMALY],
                "expectedness": Expectedness.UNEXPECTED,
                "relatedness": Relatedness.NOT_ASSESSABLE,
                "reporter_type": ReporterType.PHYSICIAN,
                "narrative": "Partner of male subject (age 69) reported congenital cardiac defect in newborn. Temporal association with aflibercept treatment. Causality not assessable.",
                "meddra_pt": "Congenital cardiac defect",
                "meddra_soc": "Congenital, familial and genetic disorders",
                "onset_date": now - timedelta(days=7),
                "resolution_date": None,
                "outcome": EventOutcome.UNKNOWN,
                "reporting_status": ReportingStatus.DRAFT,
            },
            {
                "id": "SC-024",
                "case_number": "CASE-2026-0003",
                "trial_id": DUPIXENT_TRIAL,
                "patient_id": "PAT-D008",
                "site_id": "SITE-108",
                "case_type": CaseType.INITIAL,
                "initial_receipt_date": now - timedelta(days=3),
                "most_recent_date": now - timedelta(days=1),
                "seriousness_criteria": [],
                "expectedness": Expectedness.EXPECTED,
                "relatedness": Relatedness.UNLIKELY_RELATED,
                "reporter_type": ReporterType.OTHER_HCP,
                "narrative": "35-year-old male reported headache and fatigue starting 2 days after injection. Mild severity. No treatment required.",
                "meddra_pt": "Headache",
                "meddra_soc": "Nervous system disorders",
                "onset_date": now - timedelta(days=4),
                "resolution_date": now - timedelta(days=1),
                "outcome": EventOutcome.RECOVERED,
                "reporting_status": ReportingStatus.DRAFT,
            },
            {
                "id": "SC-025",
                "case_number": "CASE-2026-0004",
                "trial_id": LIBTAYO_TRIAL,
                "patient_id": "PAT-L009",
                "site_id": "SITE-107",
                "case_type": CaseType.INITIAL,
                "initial_receipt_date": now - timedelta(days=2),
                "most_recent_date": now - timedelta(days=1),
                "seriousness_criteria": [Seriousness.LIFE_THREATENING, Seriousness.HOSPITALIZATION],
                "expectedness": Expectedness.UNEXPECTED,
                "relatedness": Relatedness.RELATED,
                "reporter_type": ReporterType.PHYSICIAN,
                "narrative": "62-year-old male developed immune-related encephalitis with altered mental status and seizures. Admitted to ICU. High-dose steroids initiated.",
                "meddra_pt": "Encephalitis autoimmune",
                "meddra_soc": "Nervous system disorders",
                "onset_date": now - timedelta(days=3),
                "resolution_date": None,
                "outcome": EventOutcome.NOT_RECOVERED,
                "reporting_status": ReportingStatus.DRAFT,
            },
        ]

        self._case_counter = 25
        for c in cases_data:
            case = SafetyCase(**c, regulatory_submissions=[])
            self._cases[c["id"]] = case

        # --- 40 Regulatory Submissions ---
        submissions_data = [
            # SC-001 submissions (expected, hospitalization -> 15 day)
            {"id": "SUB-001", "case_id": "SC-001", "authority": RegulatoryAuthority.FDA, "form_type": CIOMSFormType.MEDWATCH_3500A, "submission_date": now - timedelta(days=168), "due_date": now - timedelta(days=165), "acknowledgment_date": now - timedelta(days=160), "status": SubmissionStatus.ACKNOWLEDGED},
            {"id": "SUB-002", "case_id": "SC-001", "authority": RegulatoryAuthority.EMA, "form_type": CIOMSFormType.CIOMS_I, "submission_date": now - timedelta(days=170), "due_date": now - timedelta(days=165), "acknowledgment_date": now - timedelta(days=162), "status": SubmissionStatus.ACKNOWLEDGED},
            # SC-002 submissions (unexpected life-threatening SUSAR -> 7 day initial + 15 day follow-up)
            {"id": "SUB-003", "case_id": "SC-002", "authority": RegulatoryAuthority.FDA, "form_type": CIOMSFormType.MEDWATCH_3500A, "submission_date": now - timedelta(days=155), "due_date": now - timedelta(days=153), "acknowledgment_date": now - timedelta(days=150), "status": SubmissionStatus.ACKNOWLEDGED},
            {"id": "SUB-004", "case_id": "SC-002", "authority": RegulatoryAuthority.EMA, "form_type": CIOMSFormType.CIOMS_I, "submission_date": now - timedelta(days=156), "due_date": now - timedelta(days=153), "acknowledgment_date": now - timedelta(days=148), "status": SubmissionStatus.ACKNOWLEDGED},
            {"id": "SUB-005", "case_id": "SC-002", "authority": RegulatoryAuthority.PMDA, "form_type": CIOMSFormType.CIOMS_I, "submission_date": now - timedelta(days=154), "due_date": now - timedelta(days=153), "acknowledgment_date": now - timedelta(days=149), "status": SubmissionStatus.ACKNOWLEDGED},
            # SC-004 submissions
            {"id": "SUB-006", "case_id": "SC-004", "authority": RegulatoryAuthority.FDA, "form_type": CIOMSFormType.MEDWATCH_3500A, "submission_date": now - timedelta(days=118), "due_date": now - timedelta(days=115), "acknowledgment_date": now - timedelta(days=110), "status": SubmissionStatus.ACKNOWLEDGED},
            {"id": "SUB-007", "case_id": "SC-004", "authority": RegulatoryAuthority.EMA, "form_type": CIOMSFormType.CIOMS_I, "submission_date": now - timedelta(days=120), "due_date": now - timedelta(days=115), "acknowledgment_date": now - timedelta(days=112), "status": SubmissionStatus.ACKNOWLEDGED},
            # SC-006 (SUSAR anaphylaxis -> 7 day)
            {"id": "SUB-008", "case_id": "SC-006", "authority": RegulatoryAuthority.FDA, "form_type": CIOMSFormType.MEDWATCH_3500A, "submission_date": now - timedelta(days=95), "due_date": now - timedelta(days=93), "acknowledgment_date": now - timedelta(days=88), "status": SubmissionStatus.ACKNOWLEDGED},
            {"id": "SUB-009", "case_id": "SC-006", "authority": RegulatoryAuthority.EMA, "form_type": CIOMSFormType.CIOMS_I, "submission_date": now - timedelta(days=96), "due_date": now - timedelta(days=93), "acknowledgment_date": now - timedelta(days=90), "status": SubmissionStatus.ACKNOWLEDGED},
            {"id": "SUB-010", "case_id": "SC-006", "authority": RegulatoryAuthority.MHRA, "form_type": CIOMSFormType.CIOMS_I, "submission_date": now - timedelta(days=94), "due_date": now - timedelta(days=93), "acknowledgment_date": now - timedelta(days=87), "status": SubmissionStatus.ACKNOWLEDGED},
            # SC-007 submissions
            {"id": "SUB-011", "case_id": "SC-007", "authority": RegulatoryAuthority.FDA, "form_type": CIOMSFormType.MEDWATCH_3500A, "submission_date": now - timedelta(days=78), "due_date": now - timedelta(days=75), "acknowledgment_date": now - timedelta(days=70), "status": SubmissionStatus.ACKNOWLEDGED},
            {"id": "SUB-012", "case_id": "SC-007", "authority": RegulatoryAuthority.EMA, "form_type": CIOMSFormType.CIOMS_I, "submission_date": now - timedelta(days=80), "due_date": now - timedelta(days=75), "acknowledgment_date": now - timedelta(days=72), "status": SubmissionStatus.ACKNOWLEDGED},
            # SC-008 (fatal unexpected -> 7 day)
            {"id": "SUB-013", "case_id": "SC-008", "authority": RegulatoryAuthority.FDA, "form_type": CIOMSFormType.MEDWATCH_3500A, "submission_date": now - timedelta(days=74), "due_date": now - timedelta(days=73), "acknowledgment_date": now - timedelta(days=68), "status": SubmissionStatus.ACKNOWLEDGED},
            {"id": "SUB-014", "case_id": "SC-008", "authority": RegulatoryAuthority.EMA, "form_type": CIOMSFormType.CIOMS_I, "submission_date": now - timedelta(days=75), "due_date": now - timedelta(days=73), "acknowledgment_date": now - timedelta(days=69), "status": SubmissionStatus.ACKNOWLEDGED},
            {"id": "SUB-015", "case_id": "SC-008", "authority": RegulatoryAuthority.PMDA, "form_type": CIOMSFormType.CIOMS_I, "submission_date": now - timedelta(days=74), "due_date": now - timedelta(days=73), "acknowledgment_date": now - timedelta(days=67), "status": SubmissionStatus.ACKNOWLEDGED},
            {"id": "SUB-016", "case_id": "SC-008", "authority": RegulatoryAuthority.HC, "form_type": CIOMSFormType.CIOMS_I, "submission_date": now - timedelta(days=73), "due_date": now - timedelta(days=73), "acknowledgment_date": now - timedelta(days=66), "status": SubmissionStatus.ACKNOWLEDGED},
            # SC-009 submissions
            {"id": "SUB-017", "case_id": "SC-009", "authority": RegulatoryAuthority.FDA, "form_type": CIOMSFormType.MEDWATCH_3500A, "submission_date": now - timedelta(days=58), "due_date": now - timedelta(days=55), "acknowledgment_date": now - timedelta(days=50), "status": SubmissionStatus.ACKNOWLEDGED},
            {"id": "SUB-018", "case_id": "SC-009", "authority": RegulatoryAuthority.EMA, "form_type": CIOMSFormType.CIOMS_I, "submission_date": now - timedelta(days=60), "due_date": now - timedelta(days=55), "acknowledgment_date": None, "status": SubmissionStatus.SUBMITTED},
            # SC-011 follow-up submissions
            {"id": "SUB-019", "case_id": "SC-011", "authority": RegulatoryAuthority.FDA, "form_type": CIOMSFormType.MEDWATCH_3500A, "submission_date": now - timedelta(days=45), "due_date": now - timedelta(days=43), "acknowledgment_date": now - timedelta(days=40), "status": SubmissionStatus.ACKNOWLEDGED},
            {"id": "SUB-020", "case_id": "SC-011", "authority": RegulatoryAuthority.EMA, "form_type": CIOMSFormType.E2B_R3, "submission_date": now - timedelta(days=44), "due_date": now - timedelta(days=43), "acknowledgment_date": now - timedelta(days=38), "status": SubmissionStatus.ACKNOWLEDGED},
            # SC-012 submissions
            {"id": "SUB-021", "case_id": "SC-012", "authority": RegulatoryAuthority.FDA, "form_type": CIOMSFormType.MEDWATCH_3500A, "submission_date": now - timedelta(days=33), "due_date": now - timedelta(days=30), "acknowledgment_date": now - timedelta(days=28), "status": SubmissionStatus.ACKNOWLEDGED},
            # SC-014 submissions
            {"id": "SUB-022", "case_id": "SC-014", "authority": RegulatoryAuthority.FDA, "form_type": CIOMSFormType.MEDWATCH_3500A, "submission_date": now - timedelta(days=22), "due_date": now - timedelta(days=20), "acknowledgment_date": now - timedelta(days=15), "status": SubmissionStatus.ACKNOWLEDGED},
            {"id": "SUB-023", "case_id": "SC-014", "authority": RegulatoryAuthority.EMA, "form_type": CIOMSFormType.CIOMS_I, "submission_date": now - timedelta(days=23), "due_date": now - timedelta(days=20), "acknowledgment_date": None, "status": SubmissionStatus.SUBMITTED},
            # SC-016 submissions
            {"id": "SUB-024", "case_id": "SC-016", "authority": RegulatoryAuthority.FDA, "form_type": CIOMSFormType.MEDWATCH_3500A, "submission_date": now - timedelta(days=13), "due_date": now - timedelta(days=10), "acknowledgment_date": None, "status": SubmissionStatus.SUBMITTED},
            {"id": "SUB-025", "case_id": "SC-016", "authority": RegulatoryAuthority.EMA, "form_type": CIOMSFormType.CIOMS_I, "submission_date": now - timedelta(days=14), "due_date": now - timedelta(days=10), "acknowledgment_date": None, "status": SubmissionStatus.SUBMITTED},
            # SC-017 pending submissions (SUSAR disability -> 15 day)
            {"id": "SUB-026", "case_id": "SC-017", "authority": RegulatoryAuthority.FDA, "form_type": CIOMSFormType.MEDWATCH_3500A, "submission_date": None, "due_date": now - timedelta(days=5), "acknowledgment_date": None, "status": SubmissionStatus.PENDING},
            {"id": "SUB-027", "case_id": "SC-017", "authority": RegulatoryAuthority.EMA, "form_type": CIOMSFormType.CIOMS_I, "submission_date": None, "due_date": now - timedelta(days=5), "acknowledgment_date": None, "status": SubmissionStatus.PENDING},
            # SC-019 SUSAR submissions (7-day)
            {"id": "SUB-028", "case_id": "SC-019", "authority": RegulatoryAuthority.FDA, "form_type": CIOMSFormType.MEDWATCH_3500A, "submission_date": now - timedelta(days=9), "due_date": now - timedelta(days=8), "acknowledgment_date": None, "status": SubmissionStatus.SUBMITTED},
            {"id": "SUB-029", "case_id": "SC-019", "authority": RegulatoryAuthority.EMA, "form_type": CIOMSFormType.CIOMS_I, "submission_date": now - timedelta(days=10), "due_date": now - timedelta(days=8), "acknowledgment_date": None, "status": SubmissionStatus.SUBMITTED},
            {"id": "SUB-030", "case_id": "SC-019", "authority": RegulatoryAuthority.PMDA, "form_type": CIOMSFormType.CIOMS_I, "submission_date": None, "due_date": now - timedelta(days=8), "acknowledgment_date": None, "status": SubmissionStatus.PENDING},
            # SC-021 amendment submissions
            {"id": "SUB-031", "case_id": "SC-021", "authority": RegulatoryAuthority.FDA, "form_type": CIOMSFormType.MEDWATCH_3500A, "submission_date": now - timedelta(days=2), "due_date": now + timedelta(days=10), "acknowledgment_date": None, "status": SubmissionStatus.SUBMITTED},
            {"id": "SUB-032", "case_id": "SC-021", "authority": RegulatoryAuthority.EMA, "form_type": CIOMSFormType.CIOMS_I, "submission_date": now - timedelta(days=1), "due_date": now + timedelta(days=10), "acknowledgment_date": None, "status": SubmissionStatus.SUBMITTED},
            # SC-022 pending submissions
            {"id": "SUB-033", "case_id": "SC-022", "authority": RegulatoryAuthority.FDA, "form_type": CIOMSFormType.MEDWATCH_3500A, "submission_date": None, "due_date": now + timedelta(days=7), "acknowledgment_date": None, "status": SubmissionStatus.PENDING},
            {"id": "SUB-034", "case_id": "SC-022", "authority": RegulatoryAuthority.EMA, "form_type": CIOMSFormType.CIOMS_I, "submission_date": None, "due_date": now + timedelta(days=7), "acknowledgment_date": None, "status": SubmissionStatus.PENDING},
            # SC-023 draft case pending triage
            {"id": "SUB-035", "case_id": "SC-023", "authority": RegulatoryAuthority.FDA, "form_type": CIOMSFormType.MEDWATCH_3500A, "submission_date": None, "due_date": now + timedelta(days=10), "acknowledgment_date": None, "status": SubmissionStatus.PENDING},
            # SC-025 SUSAR submissions (7-day life-threatening)
            {"id": "SUB-036", "case_id": "SC-025", "authority": RegulatoryAuthority.FDA, "form_type": CIOMSFormType.MEDWATCH_3500A, "submission_date": None, "due_date": now + timedelta(days=5), "acknowledgment_date": None, "status": SubmissionStatus.PENDING},
            {"id": "SUB-037", "case_id": "SC-025", "authority": RegulatoryAuthority.EMA, "form_type": CIOMSFormType.CIOMS_I, "submission_date": None, "due_date": now + timedelta(days=5), "acknowledgment_date": None, "status": SubmissionStatus.PENDING},
            {"id": "SUB-038", "case_id": "SC-025", "authority": RegulatoryAuthority.PMDA, "form_type": CIOMSFormType.CIOMS_I, "submission_date": None, "due_date": now + timedelta(days=5), "acknowledgment_date": None, "status": SubmissionStatus.PENDING},
            {"id": "SUB-039", "case_id": "SC-025", "authority": RegulatoryAuthority.MHRA, "form_type": CIOMSFormType.CIOMS_I, "submission_date": None, "due_date": now + timedelta(days=5), "acknowledgment_date": None, "status": SubmissionStatus.PENDING},
            {"id": "SUB-040", "case_id": "SC-025", "authority": RegulatoryAuthority.TGA, "form_type": CIOMSFormType.E2B_R3, "submission_date": None, "due_date": now + timedelta(days=5), "acknowledgment_date": None, "status": SubmissionStatus.PENDING},
        ]

        for s in submissions_data:
            sub = RegulatorySubmission(**s)
            self._submissions[s["id"]] = sub

        # Attach submissions to cases
        for case_id, case in self._cases.items():
            case_subs = [s for s in self._submissions.values() if s.case_id == case_id]
            if case_subs:
                data = case.model_dump()
                data["regulatory_submissions"] = case_subs
                self._cases[case_id] = SafetyCase(**data)

        # --- 3 Aggregate Reports (1 DSUR per trial) ---
        agg_data = [
            {
                "id": "AGG-001",
                "trial_id": EYLEA_TRIAL,
                "report_type": AggregateReportType.DSUR,
                "period_start": now - timedelta(days=365),
                "period_end": now,
                "due_date": now + timedelta(days=60),
                "submission_date": None,
                "status": AggregateReportStatus.DRAFTING,
                "total_cases": 8,
                "serious_cases": 6,
                "fatal_cases": 0,
            },
            {
                "id": "AGG-002",
                "trial_id": DUPIXENT_TRIAL,
                "report_type": AggregateReportType.DSUR,
                "period_start": now - timedelta(days=365),
                "period_end": now,
                "due_date": now + timedelta(days=45),
                "submission_date": None,
                "status": AggregateReportStatus.IN_REVIEW,
                "total_cases": 8,
                "serious_cases": 4,
                "fatal_cases": 0,
            },
            {
                "id": "AGG-003",
                "trial_id": LIBTAYO_TRIAL,
                "report_type": AggregateReportType.DSUR,
                "period_start": now - timedelta(days=365),
                "period_end": now,
                "due_date": now + timedelta(days=30),
                "submission_date": None,
                "status": AggregateReportStatus.IN_REVIEW,
                "total_cases": 9,
                "serious_cases": 8,
                "fatal_cases": 2,
            },
        ]

        for a in agg_data:
            self._aggregate_reports[a["id"]] = AggregateReport(**a)

    # ------------------------------------------------------------------
    # Case Management
    # ------------------------------------------------------------------

    def list_cases(
        self,
        *,
        trial_id: str | None = None,
        site_id: str | None = None,
        case_type: CaseType | None = None,
        reporting_status: ReportingStatus | None = None,
        seriousness: Seriousness | None = None,
        expectedness: Expectedness | None = None,
        relatedness: Relatedness | None = None,
        outcome: EventOutcome | None = None,
    ) -> list[SafetyCase]:
        """List safety cases with optional filters."""
        with self._lock:
            result = list(self._cases.values())

        if trial_id is not None:
            result = [c for c in result if c.trial_id == trial_id]
        if site_id is not None:
            result = [c for c in result if c.site_id == site_id]
        if case_type is not None:
            result = [c for c in result if c.case_type == case_type]
        if reporting_status is not None:
            result = [c for c in result if c.reporting_status == reporting_status]
        if seriousness is not None:
            result = [c for c in result if seriousness in c.seriousness_criteria]
        if expectedness is not None:
            result = [c for c in result if c.expectedness == expectedness]
        if relatedness is not None:
            result = [c for c in result if c.relatedness == relatedness]
        if outcome is not None:
            result = [c for c in result if c.outcome == outcome]

        return sorted(result, key=lambda c: c.initial_receipt_date, reverse=True)

    def get_case(self, case_id: str) -> SafetyCase | None:
        """Get a single safety case by ID."""
        with self._lock:
            return self._cases.get(case_id)

    def create_case(self, payload: SafetyCaseCreate) -> SafetyCase:
        """Create a new safety case."""
        now = datetime.now(timezone.utc)
        with self._lock:
            self._case_counter += 1
            case_id = f"SC-{uuid4().hex[:8].upper()}"
            year = now.year
            case_number = f"CASE-{year}-{self._case_counter:04d}"

            case = SafetyCase(
                id=case_id,
                case_number=case_number,
                trial_id=payload.trial_id,
                patient_id=payload.patient_id,
                site_id=payload.site_id,
                case_type=payload.case_type,
                initial_receipt_date=now,
                most_recent_date=now,
                seriousness_criteria=payload.seriousness_criteria,
                expectedness=payload.expectedness,
                relatedness=payload.relatedness,
                reporter_type=payload.reporter_type,
                narrative=payload.narrative,
                meddra_pt=payload.meddra_pt,
                meddra_soc=payload.meddra_soc,
                onset_date=payload.onset_date,
                resolution_date=payload.resolution_date,
                outcome=payload.outcome,
                reporting_status=ReportingStatus.DRAFT,
                regulatory_submissions=[],
            )
            self._cases[case_id] = case
        logger.info("Created safety case %s: %s", case_id, case_number)
        return case

    def update_case(self, case_id: str, payload: SafetyCaseUpdate) -> SafetyCase | None:
        """Update an existing safety case."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._cases.get(case_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            data["most_recent_date"] = now
            updated = SafetyCase(**data)
            self._cases[case_id] = updated
        return updated

    def delete_case(self, case_id: str) -> bool:
        """Delete a safety case. Returns True if deleted, False if not found."""
        with self._lock:
            if case_id in self._cases:
                del self._cases[case_id]
                # Remove associated submissions
                sub_ids = [s_id for s_id, s in self._submissions.items() if s.case_id == case_id]
                for s_id in sub_ids:
                    del self._submissions[s_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Regulatory Submissions
    # ------------------------------------------------------------------

    def list_submissions(
        self,
        *,
        case_id: str | None = None,
        authority: RegulatoryAuthority | None = None,
        status: SubmissionStatus | None = None,
    ) -> list[RegulatorySubmission]:
        """List regulatory submissions with optional filters."""
        with self._lock:
            result = list(self._submissions.values())

        if case_id is not None:
            result = [s for s in result if s.case_id == case_id]
        if authority is not None:
            result = [s for s in result if s.authority == authority]
        if status is not None:
            result = [s for s in result if s.status == status]

        return sorted(result, key=lambda s: s.due_date, reverse=True)

    def get_submission(self, submission_id: str) -> RegulatorySubmission | None:
        """Get a single regulatory submission by ID."""
        with self._lock:
            return self._submissions.get(submission_id)

    def create_submission(self, case_id: str, payload: RegulatorySubmissionCreate) -> RegulatorySubmission:
        """Create a regulatory submission for a case."""
        with self._lock:
            if case_id not in self._cases:
                raise ValueError(f"Case '{case_id}' not found")

            sub_id = f"SUB-{uuid4().hex[:8].upper()}"
            sub = RegulatorySubmission(
                id=sub_id,
                case_id=case_id,
                authority=payload.authority,
                form_type=payload.form_type,
                submission_date=None,
                due_date=payload.due_date,
                acknowledgment_date=None,
                status=SubmissionStatus.PENDING,
            )
            self._submissions[sub_id] = sub

            # Attach to case
            case = self._cases[case_id]
            data = case.model_dump()
            data["regulatory_submissions"].append(sub.model_dump())
            self._cases[case_id] = SafetyCase(**data)

        logger.info("Created submission %s for case %s to %s", sub_id, case_id, payload.authority.value)
        return sub

    def update_submission(self, submission_id: str, payload: RegulatorySubmissionUpdate) -> RegulatorySubmission | None:
        """Update a regulatory submission."""
        with self._lock:
            existing = self._submissions.get(submission_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = RegulatorySubmission(**data)
            self._submissions[submission_id] = updated

            # Update in case's submissions list
            case = self._cases.get(updated.case_id)
            if case:
                case_data = case.model_dump()
                case_data["regulatory_submissions"] = [
                    updated.model_dump() if s["id"] == submission_id else s
                    for s in case_data["regulatory_submissions"]
                ]
                self._cases[updated.case_id] = SafetyCase(**case_data)

        return updated

    def get_overdue_submissions(self) -> list[RegulatorySubmission]:
        """Get submissions that are past due date and not yet submitted."""
        now = datetime.now(timezone.utc)
        with self._lock:
            result = [
                s for s in self._submissions.values()
                if s.status == SubmissionStatus.PENDING
                and s.due_date < now
            ]
        return sorted(result, key=lambda s: s.due_date)

    # ------------------------------------------------------------------
    # CIOMS Form Generation
    # ------------------------------------------------------------------

    def generate_cioms_form(self, case_id: str, form_type: CIOMSFormType) -> CIOMSForm | None:
        """Generate a CIOMS/MedWatch form for a safety case."""
        with self._lock:
            case = self._cases.get(case_id)
            if case is None:
                return None

        # Generate form data from case information
        # Extract initials from patient_id as placeholder
        initials = case.patient_id[:3].upper() if case.patient_id else "UNK"

        # Map trial to drug name
        drug_map = {
            EYLEA_TRIAL: "Aflibercept (EYLEA)",
            DUPIXENT_TRIAL: "Dupilumab (DUPIXENT)",
            LIBTAYO_TRIAL: "Cemiplimab (LIBTAYO)",
        }
        suspect_drug = drug_map.get(case.trial_id, "Unknown Study Drug")

        # Dose/route based on drug
        dose_map = {
            EYLEA_TRIAL: ("2 mg/0.05 mL", "Intravitreal injection"),
            DUPIXENT_TRIAL: ("300 mg every 2 weeks", "Subcutaneous injection"),
            LIBTAYO_TRIAL: ("350 mg every 3 weeks", "Intravenous infusion"),
        }
        dose, route = dose_map.get(case.trial_id, ("Per protocol", "Per protocol"))

        indication_map = {
            EYLEA_TRIAL: "Neovascular (wet) age-related macular degeneration",
            DUPIXENT_TRIAL: "Moderate-to-severe atopic dermatitis",
            LIBTAYO_TRIAL: "Advanced cutaneous squamous cell carcinoma",
        }
        indication = indication_map.get(case.trial_id, "Per protocol indication")

        form = CIOMSForm(
            case_id=case_id,
            form_type=form_type,
            patient_initials=initials,
            age=65,  # Placeholder from case narrative
            sex="Unknown",
            reaction_terms=[case.meddra_pt],
            suspect_drug=suspect_drug,
            dose=dose,
            route=route,
            indication=indication,
            event_onset=case.onset_date,
            event_outcome=case.outcome,
            reporter_assessment=case.relatedness,
            company_assessment=case.relatedness,
        )
        return form

    def list_cioms_forms(self, case_id: str | None = None) -> list[CIOMSForm]:
        """List generated CIOMS forms for cases."""
        if case_id is not None:
            form = self.generate_cioms_form(case_id, CIOMSFormType.CIOMS_I)
            return [form] if form else []

        # Generate forms for all cases with submissions
        forms = []
        with self._lock:
            cases = list(self._cases.values())
        for case in cases:
            if case.regulatory_submissions:
                form = self.generate_cioms_form(case.id, CIOMSFormType.CIOMS_I)
                if form:
                    forms.append(form)
        return forms

    # ------------------------------------------------------------------
    # Aggregate Reports
    # ------------------------------------------------------------------

    def list_aggregate_reports(
        self,
        *,
        trial_id: str | None = None,
        report_type: AggregateReportType | None = None,
        status: AggregateReportStatus | None = None,
    ) -> list[AggregateReport]:
        """List aggregate safety reports with optional filters."""
        with self._lock:
            result = list(self._aggregate_reports.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if report_type is not None:
            result = [r for r in result if r.report_type == report_type]
        if status is not None:
            result = [r for r in result if r.status == status]

        return sorted(result, key=lambda r: r.due_date)

    def get_aggregate_report(self, report_id: str) -> AggregateReport | None:
        """Get a single aggregate report by ID."""
        with self._lock:
            return self._aggregate_reports.get(report_id)

    def create_aggregate_report(self, payload: AggregateReportCreate) -> AggregateReport:
        """Create a new aggregate safety report."""
        report_id = f"AGG-{uuid4().hex[:8].upper()}"
        report = AggregateReport(
            id=report_id,
            trial_id=payload.trial_id,
            report_type=payload.report_type,
            period_start=payload.period_start,
            period_end=payload.period_end,
            due_date=payload.due_date,
            submission_date=None,
            status=AggregateReportStatus.DRAFTING,
            total_cases=0,
            serious_cases=0,
            fatal_cases=0,
        )
        with self._lock:
            self._aggregate_reports[report_id] = report
        logger.info("Created aggregate report %s: %s for trial %s", report_id, payload.report_type.value, payload.trial_id)
        return report

    def update_aggregate_report(self, report_id: str, payload: AggregateReportUpdate) -> AggregateReport | None:
        """Update an aggregate report."""
        with self._lock:
            existing = self._aggregate_reports.get(report_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = AggregateReport(**data)
            self._aggregate_reports[report_id] = updated
        return updated

    def delete_aggregate_report(self, report_id: str) -> bool:
        """Delete an aggregate report. Returns True if deleted."""
        with self._lock:
            if report_id in self._aggregate_reports:
                del self._aggregate_reports[report_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Expedited Reporting Timeline
    # ------------------------------------------------------------------

    def calculate_reporting_deadline(self, case: SafetyCase) -> int:
        """Calculate the expedited reporting deadline in calendar days.

        ICH E2A expedited reporting:
        - Fatal or life-threatening + unexpected: 7 calendar days
        - Other serious + unexpected: 15 calendar days
        - Serious + expected: 15 calendar days (periodic)
        - Non-serious: periodic reporting only

        Returns number of days from initial_receipt_date.
        """
        if not case.seriousness_criteria:
            return 0  # Non-serious, no expedited timeline

        is_fatal_or_lt = any(
            s in (Seriousness.DEATH, Seriousness.LIFE_THREATENING)
            for s in case.seriousness_criteria
        )
        is_unexpected = case.expectedness == Expectedness.UNEXPECTED

        if is_fatal_or_lt and is_unexpected:
            return EXPEDITED_FATAL_DAYS
        elif case.seriousness_criteria:
            return EXPEDITED_SERIOUS_DAYS
        return 0

    def get_susars(self) -> list[SafetyCase]:
        """Get all Suspected Unexpected Serious Adverse Reactions (SUSARs).

        SUSAR = serious + unexpected + at least possibly related.
        """
        related_values = {Relatedness.RELATED, Relatedness.POSSIBLY_RELATED}
        with self._lock:
            result = [
                c for c in self._cases.values()
                if c.seriousness_criteria
                and c.expectedness == Expectedness.UNEXPECTED
                and c.relatedness in related_values
            ]
        return sorted(result, key=lambda c: c.initial_receipt_date, reverse=True)

    # ------------------------------------------------------------------
    # Metrics & Dashboard
    # ------------------------------------------------------------------

    def get_metrics(self) -> SafetyDatabaseMetrics:
        """Compute aggregated safety database metrics."""
        now = datetime.now(timezone.utc)

        with self._lock:
            cases = list(self._cases.values())
            submissions = list(self._submissions.values())
            agg_reports = list(self._aggregate_reports.values())

        # Cases by seriousness
        cases_by_seriousness: dict[str, int] = {}
        for case in cases:
            for s in case.seriousness_criteria:
                key = s.value
                cases_by_seriousness[key] = cases_by_seriousness.get(key, 0) + 1

        # Cases by relatedness
        cases_by_relatedness: dict[str, int] = {}
        for case in cases:
            key = case.relatedness.value
            cases_by_relatedness[key] = cases_by_relatedness.get(key, 0) + 1

        # Cases by outcome
        cases_by_outcome: dict[str, int] = {}
        for case in cases:
            key = case.outcome.value
            cases_by_outcome[key] = cases_by_outcome.get(key, 0) + 1

        # Overdue submissions
        overdue = sum(
            1 for s in submissions
            if s.status == SubmissionStatus.PENDING and s.due_date < now
        )

        # Pending submissions
        pending = sum(1 for s in submissions if s.status == SubmissionStatus.PENDING)

        # Average submission time
        submitted = [
            s for s in submissions
            if s.submission_date is not None
        ]
        if submitted:
            total_days = 0.0
            for s in submitted:
                case = next((c for c in cases if c.id == s.case_id), None)
                if case:
                    delta = (s.submission_date - case.initial_receipt_date).days
                    total_days += max(0, delta)
            avg_days = round(total_days / len(submitted), 1)
        else:
            avg_days = 0.0

        # Aggregate reports due within threshold
        agg_due = sum(
            1 for r in agg_reports
            if r.status in (AggregateReportStatus.DRAFTING, AggregateReportStatus.IN_REVIEW)
            and r.due_date <= now + timedelta(days=AGGREGATE_REPORT_DUE_THRESHOLD_DAYS)
        )

        # Fatal cases
        fatal = sum(1 for c in cases if c.outcome == EventOutcome.FATAL)

        # Unexpected serious (SUSARs)
        related_values = {Relatedness.RELATED, Relatedness.POSSIBLY_RELATED}
        susars = sum(
            1 for c in cases
            if c.seriousness_criteria
            and c.expectedness == Expectedness.UNEXPECTED
            and c.relatedness in related_values
        )

        return SafetyDatabaseMetrics(
            total_cases=len(cases),
            cases_by_seriousness=cases_by_seriousness,
            cases_by_relatedness=cases_by_relatedness,
            overdue_submissions=overdue,
            avg_submission_time_days=avg_days,
            aggregate_reports_due=agg_due,
            total_submissions=len(submissions),
            pending_submissions=pending,
            cases_by_outcome=cases_by_outcome,
            fatal_cases=fatal,
            unexpected_serious_cases=susars,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: SafetyDatabaseService | None = None
_instance_lock = threading.Lock()


def get_safety_db_service() -> SafetyDatabaseService:
    """Return the singleton SafetyDatabaseService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = SafetyDatabaseService()
    return _instance


def reset_safety_db_service() -> SafetyDatabaseService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = SafetyDatabaseService()
    return _instance
