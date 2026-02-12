"""Clinical Outcome Assessment Management (COA-MGT) Service.

Manages COA instruments (PROs, ClinROs, ObsROs, PerfOs), assessments,
instrument validation studies, translation/adaptation workflows,
compliance reports, and operational metrics.

Usage:
    from app.services.clinical_outcome_assessment_service import (
        get_clinical_outcome_assessment_service,
    )

    svc = get_clinical_outcome_assessment_service()
    instruments = svc.list_instruments()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.clinical_outcome_assessment import (
    AssessmentFrequency,
    COAAssessment,
    COAAssessmentCreate,
    COAAssessmentUpdate,
    COAComplianceReport,
    COAComplianceReportCreate,
    COAComplianceReportUpdate,
    COAInstrument,
    COAInstrumentCreate,
    COAInstrumentUpdate,
    COAMetrics,
    COAType,
    CompletionStatus,
    InstrumentStatus,
    InstrumentValidation,
    InstrumentValidationCreate,
    InstrumentValidationUpdate,
    TranslationAdaptation,
    TranslationAdaptationCreate,
    TranslationAdaptationUpdate,
    ValidationLevel,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class ClinicalOutcomeAssessmentService:
    """In-memory Clinical Outcome Assessment Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._instruments: dict[str, COAInstrument] = {}
        self._assessments: dict[str, COAAssessment] = {}
        self._validations: dict[str, InstrumentValidation] = {}
        self._translations: dict[str, TranslationAdaptation] = {}
        self._compliance_reports: dict[str, COAComplianceReport] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic COA data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 12 COA Instruments ---
        instruments_data = [
            # EYLEA instruments
            {"id": "COA-INST-001", "trial_id": EYLEA_TRIAL, "instrument_name": "NEI VFQ-25", "coa_type": COAType.PRO, "description": "National Eye Institute Visual Function Questionnaire 25-item", "version": "2.0", "domains": ["general_vision", "near_activities", "distance_activities", "driving", "peripheral_vision", "color_vision", "ocular_pain", "role_limitations", "dependency", "social_functioning", "mental_health"], "total_items": 25, "scoring_algorithm": "Item-level weighted composite", "score_range_min": 0.0, "score_range_max": 100.0, "mcid": 4.0, "recall_period": "past_week", "administration_mode": "electronic", "language": "en", "status": InstrumentStatus.VALIDATED, "license_holder": "RAND Corporation", "regulatory_reference": "FDA PRO Guidance 2009", "created_by": "Dr. Sarah Chen", "created_at": now - timedelta(days=180)},
            {"id": "COA-INST-002", "trial_id": EYLEA_TRIAL, "instrument_name": "BCVA ETDRS Chart", "coa_type": COAType.PERFO, "description": "Best Corrected Visual Acuity using Early Treatment Diabetic Retinopathy Study chart", "version": "1.0", "domains": ["visual_acuity"], "total_items": 1, "scoring_algorithm": "Letter count at 4m", "score_range_min": 0.0, "score_range_max": 100.0, "mcid": 5.0, "recall_period": None, "administration_mode": "in_clinic", "language": "en", "status": InstrumentStatus.REGULATORY_QUALIFIED, "license_holder": "Public Domain", "regulatory_reference": "FDA Ophthalmology Endpoints Guidance 2023", "created_by": "Dr. James Rodriguez", "created_at": now - timedelta(days=200)},
            {"id": "COA-INST-003", "trial_id": EYLEA_TRIAL, "instrument_name": "OCT Central Subfield Thickness", "coa_type": COAType.CLINRO, "description": "Optical coherence tomography central retinal thickness measurement", "version": "3.1", "domains": ["retinal_morphology"], "total_items": 1, "scoring_algorithm": "Micron measurement", "score_range_min": 100.0, "score_range_max": 800.0, "mcid": 50.0, "recall_period": None, "administration_mode": "device", "language": "en", "status": InstrumentStatus.VALIDATED, "license_holder": None, "regulatory_reference": None, "created_by": "Dr. Laura Kim", "created_at": now - timedelta(days=175)},
            {"id": "COA-INST-004", "trial_id": EYLEA_TRIAL, "instrument_name": "EQ-5D-5L", "coa_type": COAType.PRO, "description": "EuroQol 5-Dimension 5-Level health utility instrument", "version": "2.1", "domains": ["mobility", "self_care", "usual_activities", "pain_discomfort", "anxiety_depression"], "total_items": 6, "scoring_algorithm": "Value set based utility", "score_range_min": -0.5, "score_range_max": 1.0, "mcid": 0.05, "recall_period": "today", "administration_mode": "electronic", "language": "en", "status": InstrumentStatus.VALIDATED, "license_holder": "EuroQol Research Foundation", "regulatory_reference": "EMA HTA Guidance", "created_by": "Dr. Sarah Chen", "created_at": now - timedelta(days=170)},
            # DUPIXENT instruments
            {"id": "COA-INST-005", "trial_id": DUPIXENT_TRIAL, "instrument_name": "EASI Score", "coa_type": COAType.CLINRO, "description": "Eczema Area and Severity Index clinician assessment", "version": "1.2", "domains": ["erythema", "induration", "excoriation", "lichenification"], "total_items": 4, "scoring_algorithm": "Area-weighted severity composite", "score_range_min": 0.0, "score_range_max": 72.0, "mcid": 6.6, "recall_period": None, "administration_mode": "in_clinic", "language": "en", "status": InstrumentStatus.REGULATORY_QUALIFIED, "license_holder": "Public Domain", "regulatory_reference": "FDA Dermatology Guidance 2016", "created_by": "Dr. Robert Williams", "created_at": now - timedelta(days=190)},
            {"id": "COA-INST-006", "trial_id": DUPIXENT_TRIAL, "instrument_name": "Peak Pruritus NRS", "coa_type": COAType.PRO, "description": "Peak Pruritus Numerical Rating Scale for itch severity", "version": "1.0", "domains": ["pruritus_severity"], "total_items": 1, "scoring_algorithm": "Single item NRS", "score_range_min": 0.0, "score_range_max": 10.0, "mcid": 4.0, "recall_period": "past_24h", "administration_mode": "electronic_diary", "language": "en", "status": InstrumentStatus.VALIDATED, "license_holder": "Regeneron Pharmaceuticals", "regulatory_reference": "FDA PRO Guidance 2009", "created_by": "Dr. Angela Martinez", "created_at": now - timedelta(days=185)},
            {"id": "COA-INST-007", "trial_id": DUPIXENT_TRIAL, "instrument_name": "DLQI", "coa_type": COAType.PRO, "description": "Dermatology Life Quality Index patient questionnaire", "version": "1.0", "domains": ["symptoms_feelings", "daily_activities", "leisure", "work_school", "personal_relationships", "treatment"], "total_items": 10, "scoring_algorithm": "Sum of item scores", "score_range_min": 0.0, "score_range_max": 30.0, "mcid": 4.0, "recall_period": "past_week", "administration_mode": "electronic", "language": "en", "status": InstrumentStatus.VALIDATED, "license_holder": "Cardiff University", "regulatory_reference": None, "created_by": "Dr. David Nakamura", "created_at": now - timedelta(days=180)},
            {"id": "COA-INST-008", "trial_id": DUPIXENT_TRIAL, "instrument_name": "IGA Score", "coa_type": COAType.CLINRO, "description": "Investigator Global Assessment for atopic dermatitis severity", "version": "2.0", "domains": ["overall_severity"], "total_items": 1, "scoring_algorithm": "5-point ordinal scale", "score_range_min": 0.0, "score_range_max": 4.0, "mcid": 1.0, "recall_period": None, "administration_mode": "in_clinic", "language": "en", "status": InstrumentStatus.REGULATORY_QUALIFIED, "license_holder": "Public Domain", "regulatory_reference": "FDA Dermatology Guidance 2016", "created_by": "Dr. Robert Williams", "created_at": now - timedelta(days=195)},
            # LIBTAYO instruments
            {"id": "COA-INST-009", "trial_id": LIBTAYO_TRIAL, "instrument_name": "EORTC QLQ-C30", "coa_type": COAType.PRO, "description": "European Organisation for Research and Treatment of Cancer Quality of Life Questionnaire Core 30", "version": "3.0", "domains": ["global_health", "physical", "role", "emotional", "cognitive", "social", "fatigue", "nausea", "pain"], "total_items": 30, "scoring_algorithm": "Linear transformation 0-100", "score_range_min": 0.0, "score_range_max": 100.0, "mcid": 10.0, "recall_period": "past_week", "administration_mode": "electronic", "language": "en", "status": InstrumentStatus.VALIDATED, "license_holder": "EORTC Quality of Life Group", "regulatory_reference": "EMA Oncology PRO Guidance 2016", "created_by": "Dr. Catherine Liu", "created_at": now - timedelta(days=210)},
            {"id": "COA-INST-010", "trial_id": LIBTAYO_TRIAL, "instrument_name": "RECIST 1.1 Tumor Assessment", "coa_type": COAType.CLINRO, "description": "Response Evaluation Criteria in Solid Tumors imaging assessment", "version": "1.1", "domains": ["tumor_response"], "total_items": 1, "scoring_algorithm": "Categorical: CR/PR/SD/PD", "score_range_min": 0.0, "score_range_max": 4.0, "mcid": 1.0, "recall_period": None, "administration_mode": "imaging_review", "language": "en", "status": InstrumentStatus.REGULATORY_QUALIFIED, "license_holder": "Public Domain", "regulatory_reference": "FDA Oncology Endpoints Guidance 2023", "created_by": "Dr. Andrew Foster", "created_at": now - timedelta(days=220)},
            {"id": "COA-INST-011", "trial_id": LIBTAYO_TRIAL, "instrument_name": "ECOG Performance Status", "coa_type": COAType.OBSRO, "description": "Eastern Cooperative Oncology Group observer-rated performance status", "version": "1.0", "domains": ["functional_status"], "total_items": 1, "scoring_algorithm": "5-point ordinal scale", "score_range_min": 0.0, "score_range_max": 5.0, "mcid": 1.0, "recall_period": None, "administration_mode": "in_clinic", "language": "en", "status": InstrumentStatus.VALIDATED, "license_holder": "ECOG-ACRIN", "regulatory_reference": None, "created_by": "Dr. Natalie Wong", "created_at": now - timedelta(days=215)},
            {"id": "COA-INST-012", "trial_id": LIBTAYO_TRIAL, "instrument_name": "EQ-5D-5L Oncology", "coa_type": COAType.PRO, "description": "EuroQol 5-Dimension for oncology health utility assessment", "version": "2.1", "domains": ["mobility", "self_care", "usual_activities", "pain_discomfort", "anxiety_depression"], "total_items": 6, "scoring_algorithm": "Value set based utility", "score_range_min": -0.5, "score_range_max": 1.0, "mcid": 0.08, "recall_period": "today", "administration_mode": "electronic", "language": "en", "status": InstrumentStatus.VALIDATED, "license_holder": "EuroQol Research Foundation", "regulatory_reference": "EMA HTA Guidance", "created_by": "Dr. Catherine Liu", "created_at": now - timedelta(days=205)},
        ]

        for inst in instruments_data:
            self._instruments[inst["id"]] = COAInstrument(**inst)

        # --- 15 COA Assessments ---
        assessments_data = [
            # EYLEA assessments
            {"id": "COA-ASM-001", "instrument_id": "COA-INST-001", "trial_id": EYLEA_TRIAL, "subject_id": "PT-1001", "site_id": "SITE-101", "visit": "Week 16", "frequency": AssessmentFrequency.MONTHLY, "scheduled_date": now - timedelta(days=90), "completed_date": now - timedelta(days=90), "completion_status": CompletionStatus.COMPLETED, "total_score": 78.5, "domain_scores": {"general_vision": 80.0, "near_activities": 75.0, "distance_activities": 70.0, "ocular_pain": 90.0}, "completion_time_minutes": 12, "missing_items": 0, "data_quality_flag": None, "administered_by": None, "created_at": now - timedelta(days=90)},
            {"id": "COA-ASM-002", "instrument_id": "COA-INST-002", "trial_id": EYLEA_TRIAL, "subject_id": "PT-1001", "site_id": "SITE-101", "visit": "Week 16", "frequency": AssessmentFrequency.MONTHLY, "scheduled_date": now - timedelta(days=90), "completed_date": now - timedelta(days=90), "completion_status": CompletionStatus.COMPLETED, "total_score": 72.0, "domain_scores": {"visual_acuity": 72.0}, "completion_time_minutes": 5, "missing_items": 0, "data_quality_flag": None, "administered_by": "Dr. Rodriguez", "created_at": now - timedelta(days=90)},
            {"id": "COA-ASM-003", "instrument_id": "COA-INST-001", "trial_id": EYLEA_TRIAL, "subject_id": "PT-1002", "site_id": "SITE-101", "visit": "Week 16", "frequency": AssessmentFrequency.MONTHLY, "scheduled_date": now - timedelta(days=85), "completed_date": now - timedelta(days=84), "completion_status": CompletionStatus.COMPLETED, "total_score": 65.2, "domain_scores": {"general_vision": 60.0, "near_activities": 55.0, "distance_activities": 68.0, "ocular_pain": 85.0}, "completion_time_minutes": 15, "missing_items": 1, "data_quality_flag": "one_item_missing", "administered_by": None, "created_at": now - timedelta(days=84)},
            {"id": "COA-ASM-004", "instrument_id": "COA-INST-004", "trial_id": EYLEA_TRIAL, "subject_id": "PT-1003", "site_id": "SITE-102", "visit": "Baseline", "frequency": AssessmentFrequency.BASELINE, "scheduled_date": now - timedelta(days=120), "completed_date": None, "completion_status": CompletionStatus.MISSED, "total_score": None, "domain_scores": {}, "completion_time_minutes": None, "missing_items": 6, "data_quality_flag": "visit_missed", "administered_by": None, "created_at": now - timedelta(days=120)},
            {"id": "COA-ASM-005", "instrument_id": "COA-INST-001", "trial_id": EYLEA_TRIAL, "subject_id": "PT-1004", "site_id": "SITE-103", "visit": "Week 32", "frequency": AssessmentFrequency.MONTHLY, "scheduled_date": now - timedelta(days=45), "completed_date": now - timedelta(days=45), "completion_status": CompletionStatus.PARTIALLY_COMPLETED, "total_score": 55.0, "domain_scores": {"general_vision": 50.0, "near_activities": 60.0}, "completion_time_minutes": 8, "missing_items": 5, "data_quality_flag": "partial_completion", "administered_by": None, "created_at": now - timedelta(days=45)},
            # DUPIXENT assessments
            {"id": "COA-ASM-006", "instrument_id": "COA-INST-005", "trial_id": DUPIXENT_TRIAL, "subject_id": "PT-2001", "site_id": "SITE-104", "visit": "Week 16", "frequency": AssessmentFrequency.BIWEEKLY, "scheduled_date": now - timedelta(days=100), "completed_date": now - timedelta(days=100), "completion_status": CompletionStatus.COMPLETED, "total_score": 8.4, "domain_scores": {"erythema": 1.5, "induration": 2.0, "excoriation": 2.4, "lichenification": 2.5}, "completion_time_minutes": 10, "missing_items": 0, "data_quality_flag": None, "administered_by": "Dr. Williams", "created_at": now - timedelta(days=100)},
            {"id": "COA-ASM-007", "instrument_id": "COA-INST-006", "trial_id": DUPIXENT_TRIAL, "subject_id": "PT-2001", "site_id": "SITE-104", "visit": "Week 16", "frequency": AssessmentFrequency.WEEKLY, "scheduled_date": now - timedelta(days=100), "completed_date": now - timedelta(days=100), "completion_status": CompletionStatus.COMPLETED, "total_score": 3.0, "domain_scores": {"pruritus_severity": 3.0}, "completion_time_minutes": 2, "missing_items": 0, "data_quality_flag": None, "administered_by": None, "created_at": now - timedelta(days=100)},
            {"id": "COA-ASM-008", "instrument_id": "COA-INST-007", "trial_id": DUPIXENT_TRIAL, "subject_id": "PT-2002", "site_id": "SITE-105", "visit": "Week 16", "frequency": AssessmentFrequency.MONTHLY, "scheduled_date": now - timedelta(days=95), "completed_date": now - timedelta(days=95), "completion_status": CompletionStatus.COMPLETED, "total_score": 8.0, "domain_scores": {"symptoms_feelings": 2.0, "daily_activities": 1.0, "leisure": 1.5, "work_school": 1.0, "personal_relationships": 1.5, "treatment": 1.0}, "completion_time_minutes": 7, "missing_items": 0, "data_quality_flag": None, "administered_by": None, "created_at": now - timedelta(days=95)},
            {"id": "COA-ASM-009", "instrument_id": "COA-INST-008", "trial_id": DUPIXENT_TRIAL, "subject_id": "PT-2003", "site_id": "SITE-106", "visit": "Week 24", "frequency": AssessmentFrequency.MONTHLY, "scheduled_date": now - timedelta(days=60), "completed_date": now - timedelta(days=60), "completion_status": CompletionStatus.COMPLETED, "total_score": 1.0, "domain_scores": {"overall_severity": 1.0}, "completion_time_minutes": 3, "missing_items": 0, "data_quality_flag": None, "administered_by": "Dr. Nakamura", "created_at": now - timedelta(days=60)},
            {"id": "COA-ASM-010", "instrument_id": "COA-INST-006", "trial_id": DUPIXENT_TRIAL, "subject_id": "PT-2004", "site_id": "SITE-106", "visit": "Week 24", "frequency": AssessmentFrequency.WEEKLY, "scheduled_date": now - timedelta(days=55), "completed_date": None, "completion_status": CompletionStatus.MISSED, "total_score": None, "domain_scores": {}, "completion_time_minutes": None, "missing_items": 1, "data_quality_flag": "diary_not_completed", "administered_by": None, "created_at": now - timedelta(days=55)},
            # LIBTAYO assessments
            {"id": "COA-ASM-011", "instrument_id": "COA-INST-009", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3001", "site_id": "SITE-107", "visit": "Cycle 4", "frequency": AssessmentFrequency.QUARTERLY, "scheduled_date": now - timedelta(days=110), "completed_date": now - timedelta(days=110), "completion_status": CompletionStatus.COMPLETED, "total_score": 62.5, "domain_scores": {"global_health": 58.3, "physical": 73.3, "role": 50.0, "emotional": 66.7, "fatigue": 44.4, "pain": 33.3}, "completion_time_minutes": 18, "missing_items": 0, "data_quality_flag": None, "administered_by": None, "created_at": now - timedelta(days=110)},
            {"id": "COA-ASM-012", "instrument_id": "COA-INST-010", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3001", "site_id": "SITE-107", "visit": "Cycle 4", "frequency": AssessmentFrequency.QUARTERLY, "scheduled_date": now - timedelta(days=110), "completed_date": now - timedelta(days=110), "completion_status": CompletionStatus.COMPLETED, "total_score": 2.0, "domain_scores": {"tumor_response": 2.0}, "completion_time_minutes": 30, "missing_items": 0, "data_quality_flag": None, "administered_by": "Dr. Foster", "created_at": now - timedelta(days=110)},
            {"id": "COA-ASM-013", "instrument_id": "COA-INST-011", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3002", "site_id": "SITE-108", "visit": "Cycle 6", "frequency": AssessmentFrequency.QUARTERLY, "scheduled_date": now - timedelta(days=80), "completed_date": now - timedelta(days=80), "completion_status": CompletionStatus.COMPLETED, "total_score": 1.0, "domain_scores": {"functional_status": 1.0}, "completion_time_minutes": 2, "missing_items": 0, "data_quality_flag": None, "administered_by": "Dr. Wong", "created_at": now - timedelta(days=80)},
            {"id": "COA-ASM-014", "instrument_id": "COA-INST-012", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3003", "site_id": "SITE-107", "visit": "Cycle 8", "frequency": AssessmentFrequency.QUARTERLY, "scheduled_date": now - timedelta(days=50), "completed_date": now - timedelta(days=50), "completion_status": CompletionStatus.COMPLETED, "total_score": 0.72, "domain_scores": {"mobility": 1, "self_care": 1, "usual_activities": 2, "pain_discomfort": 2, "anxiety_depression": 2}, "completion_time_minutes": 5, "missing_items": 0, "data_quality_flag": None, "administered_by": None, "created_at": now - timedelta(days=50)},
            {"id": "COA-ASM-015", "instrument_id": "COA-INST-009", "trial_id": LIBTAYO_TRIAL, "subject_id": "PT-3004", "site_id": "SITE-108", "visit": "End of Treatment", "frequency": AssessmentFrequency.END_OF_TREATMENT, "scheduled_date": now - timedelta(days=20), "completed_date": now - timedelta(days=20), "completion_status": CompletionStatus.COMPLETED, "total_score": 45.0, "domain_scores": {"global_health": 41.7, "physical": 53.3, "role": 33.3, "emotional": 50.0, "fatigue": 55.6, "pain": 50.0}, "completion_time_minutes": 20, "missing_items": 2, "data_quality_flag": "two_items_missing", "administered_by": None, "created_at": now - timedelta(days=20)},
        ]

        for asm in assessments_data:
            self._assessments[asm["id"]] = COAAssessment(**asm)

        # --- 10 Instrument Validations ---
        validations_data = [
            {"id": "COA-VAL-001", "instrument_id": "COA-INST-001", "validation_level": ValidationLevel.FULL_PSYCHOMETRIC, "study_name": "NEI VFQ-25 Validation in wAMD", "sample_size": 420, "population": "Wet AMD patients receiving anti-VEGF therapy", "cronbach_alpha": 0.93, "test_retest_icc": 0.88, "convergent_correlation": 0.72, "known_groups_p_value": 0.001, "responsiveness_es": 0.65, "mcid_estimate": 4.0, "mcid_method": "anchor-based", "conclusion": "NEI VFQ-25 demonstrates strong psychometric properties in wAMD population", "validated_by": "Dr. Elizabeth Chen", "validation_date": now - timedelta(days=365), "publication_reference": "Ophthalmology 2024;131(4):412-421", "created_at": now - timedelta(days=365)},
            {"id": "COA-VAL-002", "instrument_id": "COA-INST-002", "validation_level": ValidationLevel.RELIABILITY, "study_name": "ETDRS Chart Reliability in Clinical Trials", "sample_size": 850, "population": "Retinal disease patients across 12 sites", "cronbach_alpha": None, "test_retest_icc": 0.95, "convergent_correlation": None, "known_groups_p_value": None, "responsiveness_es": None, "mcid_estimate": 5.0, "mcid_method": "distribution-based", "conclusion": "ETDRS BCVA testing shows excellent inter-visit reliability", "validated_by": "Dr. James Rodriguez", "validation_date": now - timedelta(days=400), "publication_reference": "IOVS 2023;64(12):28", "created_at": now - timedelta(days=400)},
            {"id": "COA-VAL-003", "instrument_id": "COA-INST-005", "validation_level": ValidationLevel.CONSTRUCT_VALIDITY, "study_name": "EASI Construct Validation in Moderate-to-Severe AD", "sample_size": 680, "population": "Adult moderate-to-severe atopic dermatitis patients", "cronbach_alpha": 0.89, "test_retest_icc": 0.91, "convergent_correlation": 0.78, "known_groups_p_value": 0.0001, "responsiveness_es": 0.82, "mcid_estimate": 6.6, "mcid_method": "anchor-based", "conclusion": "EASI demonstrates strong construct validity and responsiveness in moderate-to-severe AD", "validated_by": "Dr. Robert Williams", "validation_date": now - timedelta(days=330), "publication_reference": "JAAD 2024;90(2):298-307", "created_at": now - timedelta(days=330)},
            {"id": "COA-VAL-004", "instrument_id": "COA-INST-006", "validation_level": ValidationLevel.CONTENT_VALIDITY, "study_name": "Peak Pruritus NRS Content Validity in AD", "sample_size": 45, "population": "Adult AD patients with moderate-to-severe pruritus", "cronbach_alpha": None, "test_retest_icc": 0.84, "convergent_correlation": 0.68, "known_groups_p_value": 0.005, "responsiveness_es": None, "mcid_estimate": 4.0, "mcid_method": "anchor-based", "conclusion": "Content validity confirmed through patient interviews. Item reflects meaningful itch experience.", "validated_by": "Dr. Angela Martinez", "validation_date": now - timedelta(days=350), "publication_reference": "Br J Dermatol 2024;190(1):45-52", "created_at": now - timedelta(days=350)},
            {"id": "COA-VAL-005", "instrument_id": "COA-INST-007", "validation_level": ValidationLevel.CRITERION_VALIDITY, "study_name": "DLQI Criterion Validity Against SF-36", "sample_size": 310, "population": "Dermatology patients with various skin conditions", "cronbach_alpha": 0.91, "test_retest_icc": 0.87, "convergent_correlation": 0.74, "known_groups_p_value": 0.002, "responsiveness_es": 0.71, "mcid_estimate": 4.0, "mcid_method": "distribution-based", "conclusion": "DLQI shows good criterion validity against SF-36 domains", "validated_by": "Dr. David Nakamura", "validation_date": now - timedelta(days=290), "publication_reference": "Qual Life Res 2024;33(5):1201-1210", "created_at": now - timedelta(days=290)},
            {"id": "COA-VAL-006", "instrument_id": "COA-INST-009", "validation_level": ValidationLevel.FULL_PSYCHOMETRIC, "study_name": "EORTC QLQ-C30 Validation in Advanced CSCC", "sample_size": 280, "population": "Advanced cutaneous squamous cell carcinoma patients", "cronbach_alpha": 0.90, "test_retest_icc": 0.85, "convergent_correlation": 0.69, "known_groups_p_value": 0.001, "responsiveness_es": 0.58, "mcid_estimate": 10.0, "mcid_method": "anchor-based", "conclusion": "QLQ-C30 is valid and responsive in advanced CSCC population", "validated_by": "Dr. Catherine Liu", "validation_date": now - timedelta(days=270), "publication_reference": "Eur J Cancer 2024;198:113-122", "created_at": now - timedelta(days=270)},
            {"id": "COA-VAL-007", "instrument_id": "COA-INST-010", "validation_level": ValidationLevel.RELIABILITY, "study_name": "RECIST 1.1 Inter-Reader Reliability in CSCC", "sample_size": 156, "population": "CSCC tumor imaging datasets reviewed by independent radiologists", "cronbach_alpha": None, "test_retest_icc": 0.92, "convergent_correlation": None, "known_groups_p_value": None, "responsiveness_es": None, "mcid_estimate": None, "mcid_method": None, "conclusion": "Excellent inter-reader agreement for RECIST 1.1 in CSCC", "validated_by": "Dr. Andrew Foster", "validation_date": now - timedelta(days=250), "publication_reference": "Radiology 2024;310(3):e232145", "created_at": now - timedelta(days=250)},
            {"id": "COA-VAL-008", "instrument_id": "COA-INST-004", "validation_level": ValidationLevel.RESPONSIVENESS, "study_name": "EQ-5D-5L Responsiveness in Ophthalmic Interventions", "sample_size": 520, "population": "Patients undergoing anti-VEGF treatment for retinal diseases", "cronbach_alpha": 0.78, "test_retest_icc": 0.82, "convergent_correlation": 0.61, "known_groups_p_value": 0.01, "responsiveness_es": 0.45, "mcid_estimate": 0.05, "mcid_method": "anchor-based", "conclusion": "EQ-5D-5L shows moderate responsiveness in ophthalmic populations", "validated_by": "Dr. Sarah Chen", "validation_date": now - timedelta(days=200), "publication_reference": "Value Health 2024;27(8):1085-1092", "created_at": now - timedelta(days=200)},
            {"id": "COA-VAL-009", "instrument_id": "COA-INST-011", "validation_level": ValidationLevel.CONSTRUCT_VALIDITY, "study_name": "ECOG PS Validity in Immunotherapy Trials", "sample_size": 1200, "population": "Solid tumor patients receiving immune checkpoint inhibitors", "cronbach_alpha": None, "test_retest_icc": 0.79, "convergent_correlation": 0.65, "known_groups_p_value": 0.0001, "responsiveness_es": 0.52, "mcid_estimate": 1.0, "mcid_method": "anchor-based", "conclusion": "ECOG PS remains a valid measure of functional status in immunotherapy setting", "validated_by": "Dr. Natalie Wong", "validation_date": now - timedelta(days=180), "publication_reference": "J Clin Oncol 2024;42(15):1789-1797", "created_at": now - timedelta(days=180)},
            {"id": "COA-VAL-010", "instrument_id": "COA-INST-008", "validation_level": ValidationLevel.CONTENT_VALIDITY, "study_name": "IGA Content Validity Study in Pediatric AD", "sample_size": 35, "population": "Pediatric patients aged 6-17 with atopic dermatitis", "cronbach_alpha": None, "test_retest_icc": 0.76, "convergent_correlation": 0.58, "known_groups_p_value": 0.02, "responsiveness_es": None, "mcid_estimate": 1.0, "mcid_method": "distribution-based", "conclusion": "IGA demonstrates content validity in pediatric AD population", "validated_by": "Dr. Patricia Sullivan", "validation_date": now - timedelta(days=160), "publication_reference": "Pediatr Dermatol 2024;41(3):412-418", "created_at": now - timedelta(days=160)},
        ]

        for val in validations_data:
            self._validations[val["id"]] = InstrumentValidation(**val)

        # --- 10 Translations ---
        translations_data = [
            {"id": "COA-TRN-001", "instrument_id": "COA-INST-001", "target_language": "es", "target_country": "Spain", "translation_method": "forward_backward", "forward_translators": 2, "back_translators": 2, "cognitive_interviews": 10, "harmonized": True, "status": "completed", "completed_date": now - timedelta(days=120), "certified_by": "ICON Language Services", "created_at": now - timedelta(days=200)},
            {"id": "COA-TRN-002", "instrument_id": "COA-INST-001", "target_language": "ja", "target_country": "Japan", "translation_method": "forward_backward", "forward_translators": 2, "back_translators": 2, "cognitive_interviews": 8, "harmonized": True, "status": "completed", "completed_date": now - timedelta(days=100), "certified_by": "Transperfect", "created_at": now - timedelta(days=190)},
            {"id": "COA-TRN-003", "instrument_id": "COA-INST-005", "target_language": "de", "target_country": "Germany", "translation_method": "forward_backward", "forward_translators": 2, "back_translators": 1, "cognitive_interviews": 6, "harmonized": True, "status": "completed", "completed_date": now - timedelta(days=90), "certified_by": "ICON Language Services", "created_at": now - timedelta(days=180)},
            {"id": "COA-TRN-004", "instrument_id": "COA-INST-006", "target_language": "fr", "target_country": "France", "translation_method": "forward_backward", "forward_translators": 2, "back_translators": 2, "cognitive_interviews": 8, "harmonized": True, "status": "completed", "completed_date": now - timedelta(days=80), "certified_by": "Transperfect", "created_at": now - timedelta(days=170)},
            {"id": "COA-TRN-005", "instrument_id": "COA-INST-007", "target_language": "zh", "target_country": "China", "translation_method": "forward_backward", "forward_translators": 2, "back_translators": 2, "cognitive_interviews": 12, "harmonized": False, "status": "in_review", "completed_date": None, "certified_by": None, "created_at": now - timedelta(days=160)},
            {"id": "COA-TRN-006", "instrument_id": "COA-INST-009", "target_language": "pt", "target_country": "Brazil", "translation_method": "forward_backward", "forward_translators": 2, "back_translators": 2, "cognitive_interviews": 10, "harmonized": True, "status": "completed", "completed_date": now - timedelta(days=60), "certified_by": "Clinipace Worldwide", "created_at": now - timedelta(days=150)},
            {"id": "COA-TRN-007", "instrument_id": "COA-INST-009", "target_language": "ko", "target_country": "South Korea", "translation_method": "forward_backward", "forward_translators": 2, "back_translators": 1, "cognitive_interviews": 5, "harmonized": False, "status": "in_progress", "completed_date": None, "certified_by": None, "created_at": now - timedelta(days=90)},
            {"id": "COA-TRN-008", "instrument_id": "COA-INST-006", "target_language": "it", "target_country": "Italy", "translation_method": "dual_panel", "forward_translators": 3, "back_translators": 0, "cognitive_interviews": 8, "harmonized": True, "status": "completed", "completed_date": now - timedelta(days=40), "certified_by": "ICON Language Services", "created_at": now - timedelta(days=130)},
            {"id": "COA-TRN-009", "instrument_id": "COA-INST-012", "target_language": "es", "target_country": "Mexico", "translation_method": "forward_backward", "forward_translators": 2, "back_translators": 2, "cognitive_interviews": 6, "harmonized": False, "status": "in_progress", "completed_date": None, "certified_by": None, "created_at": now - timedelta(days=60)},
            {"id": "COA-TRN-010", "instrument_id": "COA-INST-004", "target_language": "de", "target_country": "Austria", "translation_method": "forward_backward", "forward_translators": 2, "back_translators": 2, "cognitive_interviews": 7, "harmonized": True, "status": "completed", "completed_date": now - timedelta(days=30), "certified_by": "Transperfect", "created_at": now - timedelta(days=140)},
        ]

        for trn in translations_data:
            self._translations[trn["id"]] = TranslationAdaptation(**trn)

        # --- 10 Compliance Reports ---
        compliance_reports_data = [
            {"id": "COA-CMP-001", "trial_id": EYLEA_TRIAL, "instrument_id": "COA-INST-001", "reporting_period_start": now - timedelta(days=120), "reporting_period_end": now - timedelta(days=90), "total_expected": 150, "total_completed": 138, "total_missed": 12, "compliance_pct": 92.0, "by_site": {"SITE-101": 95.0, "SITE-102": 90.0, "SITE-103": 88.0}, "by_visit": {"Baseline": 98.0, "Week 4": 95.0, "Week 8": 92.0, "Week 16": 88.0}, "average_completion_time_min": 14.2, "data_quality_issues": 3, "generated_by": "COA Operations Team", "generated_date": now - timedelta(days=85)},
            {"id": "COA-CMP-002", "trial_id": EYLEA_TRIAL, "instrument_id": "COA-INST-002", "reporting_period_start": now - timedelta(days=120), "reporting_period_end": now - timedelta(days=90), "total_expected": 150, "total_completed": 148, "total_missed": 2, "compliance_pct": 98.7, "by_site": {"SITE-101": 100.0, "SITE-102": 98.0, "SITE-103": 96.0}, "by_visit": {"Baseline": 100.0, "Week 4": 99.0, "Week 8": 98.0, "Week 16": 97.0}, "average_completion_time_min": 5.1, "data_quality_issues": 0, "generated_by": "COA Operations Team", "generated_date": now - timedelta(days=85)},
            {"id": "COA-CMP-003", "trial_id": DUPIXENT_TRIAL, "instrument_id": "COA-INST-005", "reporting_period_start": now - timedelta(days=120), "reporting_period_end": now - timedelta(days=90), "total_expected": 200, "total_completed": 182, "total_missed": 18, "compliance_pct": 91.0, "by_site": {"SITE-104": 93.0, "SITE-105": 90.0, "SITE-106": 88.0}, "by_visit": {"Baseline": 97.0, "Week 4": 94.0, "Week 8": 91.0, "Week 16": 85.0}, "average_completion_time_min": 11.5, "data_quality_issues": 5, "generated_by": "Dupixent COA Lead", "generated_date": now - timedelta(days=84)},
            {"id": "COA-CMP-004", "trial_id": DUPIXENT_TRIAL, "instrument_id": "COA-INST-006", "reporting_period_start": now - timedelta(days=120), "reporting_period_end": now - timedelta(days=90), "total_expected": 400, "total_completed": 352, "total_missed": 48, "compliance_pct": 88.0, "by_site": {"SITE-104": 90.0, "SITE-105": 87.0, "SITE-106": 85.0}, "by_visit": {"Week 1": 92.0, "Week 2": 90.0, "Week 4": 88.0, "Week 8": 85.0}, "average_completion_time_min": 1.8, "data_quality_issues": 2, "generated_by": "Dupixent COA Lead", "generated_date": now - timedelta(days=84)},
            {"id": "COA-CMP-005", "trial_id": DUPIXENT_TRIAL, "instrument_id": "COA-INST-007", "reporting_period_start": now - timedelta(days=90), "reporting_period_end": now - timedelta(days=60), "total_expected": 180, "total_completed": 165, "total_missed": 15, "compliance_pct": 91.7, "by_site": {"SITE-104": 94.0, "SITE-105": 91.0, "SITE-106": 88.0}, "by_visit": {"Week 16": 93.0, "Week 20": 91.0, "Week 24": 89.0}, "average_completion_time_min": 7.3, "data_quality_issues": 1, "generated_by": "Dupixent COA Lead", "generated_date": now - timedelta(days=55)},
            {"id": "COA-CMP-006", "trial_id": LIBTAYO_TRIAL, "instrument_id": "COA-INST-009", "reporting_period_start": now - timedelta(days=120), "reporting_period_end": now - timedelta(days=90), "total_expected": 120, "total_completed": 108, "total_missed": 12, "compliance_pct": 90.0, "by_site": {"SITE-107": 92.0, "SITE-108": 87.0}, "by_visit": {"Cycle 2": 95.0, "Cycle 4": 90.0, "Cycle 6": 85.0}, "average_completion_time_min": 19.5, "data_quality_issues": 4, "generated_by": "Libtayo COA Operations", "generated_date": now - timedelta(days=85)},
            {"id": "COA-CMP-007", "trial_id": LIBTAYO_TRIAL, "instrument_id": "COA-INST-010", "reporting_period_start": now - timedelta(days=120), "reporting_period_end": now - timedelta(days=90), "total_expected": 120, "total_completed": 118, "total_missed": 2, "compliance_pct": 98.3, "by_site": {"SITE-107": 99.0, "SITE-108": 97.0}, "by_visit": {"Cycle 2": 100.0, "Cycle 4": 98.0, "Cycle 6": 97.0}, "average_completion_time_min": 28.0, "data_quality_issues": 1, "generated_by": "Libtayo COA Operations", "generated_date": now - timedelta(days=85)},
            {"id": "COA-CMP-008", "trial_id": EYLEA_TRIAL, "instrument_id": "COA-INST-004", "reporting_period_start": now - timedelta(days=90), "reporting_period_end": now - timedelta(days=60), "total_expected": 140, "total_completed": 126, "total_missed": 14, "compliance_pct": 90.0, "by_site": {"SITE-101": 93.0, "SITE-102": 89.0, "SITE-103": 86.0}, "by_visit": {"Week 16": 94.0, "Week 24": 90.0, "Week 32": 85.0}, "average_completion_time_min": 4.5, "data_quality_issues": 2, "generated_by": "COA Operations Team", "generated_date": now - timedelta(days=55)},
            {"id": "COA-CMP-009", "trial_id": LIBTAYO_TRIAL, "instrument_id": "COA-INST-011", "reporting_period_start": now - timedelta(days=90), "reporting_period_end": now - timedelta(days=60), "total_expected": 100, "total_completed": 96, "total_missed": 4, "compliance_pct": 96.0, "by_site": {"SITE-107": 97.0, "SITE-108": 94.0}, "by_visit": {"Cycle 4": 98.0, "Cycle 6": 95.0, "Cycle 8": 94.0}, "average_completion_time_min": 2.1, "data_quality_issues": 0, "generated_by": "Libtayo COA Operations", "generated_date": now - timedelta(days=55)},
            {"id": "COA-CMP-010", "trial_id": DUPIXENT_TRIAL, "instrument_id": "COA-INST-008", "reporting_period_start": now - timedelta(days=60), "reporting_period_end": now - timedelta(days=30), "total_expected": 160, "total_completed": 152, "total_missed": 8, "compliance_pct": 95.0, "by_site": {"SITE-104": 97.0, "SITE-105": 94.0, "SITE-106": 92.0}, "by_visit": {"Week 24": 96.0, "Week 28": 95.0, "Week 32": 93.0}, "average_completion_time_min": 3.2, "data_quality_issues": 1, "generated_by": "Dupixent COA Lead", "generated_date": now - timedelta(days=25)},
        ]

        for cmp in compliance_reports_data:
            self._compliance_reports[cmp["id"]] = COAComplianceReport(**cmp)

    # ------------------------------------------------------------------
    # Instrument Management
    # ------------------------------------------------------------------

    def list_instruments(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[COAInstrument]:
        """List COA instruments with optional trial filter."""
        with self._lock:
            result = list(self._instruments.values())

        if trial_id is not None:
            result = [i for i in result if i.trial_id == trial_id]

        return sorted(result, key=lambda i: i.id)

    def get_instrument(self, instrument_id: str) -> COAInstrument | None:
        """Get a single instrument by ID."""
        with self._lock:
            return self._instruments.get(instrument_id)

    def create_instrument(self, payload: COAInstrumentCreate) -> COAInstrument:
        """Create a new COA instrument."""
        instrument_id = f"COA-INST-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        instrument = COAInstrument(
            id=instrument_id,
            trial_id=payload.trial_id,
            instrument_name=payload.instrument_name,
            coa_type=payload.coa_type,
            description=payload.description,
            version=payload.version,
            created_by=payload.created_by,
            created_at=now,
            domains=payload.domains,
            total_items=payload.total_items,
            recall_period=payload.recall_period,
        )
        with self._lock:
            self._instruments[instrument_id] = instrument
        logger.info("Created COA instrument %s: %s", instrument_id, payload.instrument_name)
        return instrument

    def update_instrument(
        self, instrument_id: str, payload: COAInstrumentUpdate
    ) -> COAInstrument | None:
        """Update an existing COA instrument."""
        with self._lock:
            existing = self._instruments.get(instrument_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = COAInstrument(**data)
            self._instruments[instrument_id] = updated
        return updated

    def delete_instrument(self, instrument_id: str) -> bool:
        """Delete an instrument. Returns True if deleted."""
        with self._lock:
            if instrument_id in self._instruments:
                del self._instruments[instrument_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Assessment Management
    # ------------------------------------------------------------------

    def list_assessments(
        self,
        *,
        trial_id: str | None = None,
        instrument_id: str | None = None,
    ) -> list[COAAssessment]:
        """List COA assessments with optional filters."""
        with self._lock:
            result = list(self._assessments.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if instrument_id is not None:
            result = [a for a in result if a.instrument_id == instrument_id]

        return sorted(result, key=lambda a: a.scheduled_date, reverse=True)

    def get_assessment(self, assessment_id: str) -> COAAssessment | None:
        """Get a single assessment by ID."""
        with self._lock:
            return self._assessments.get(assessment_id)

    def create_assessment(self, payload: COAAssessmentCreate) -> COAAssessment:
        """Create a new COA assessment."""
        assessment_id = f"COA-ASM-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        assessment = COAAssessment(
            id=assessment_id,
            instrument_id=payload.instrument_id,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            site_id=payload.site_id,
            visit=payload.visit,
            frequency=payload.frequency,
            scheduled_date=payload.scheduled_date,
            created_at=now,
        )
        with self._lock:
            self._assessments[assessment_id] = assessment
        logger.info("Created COA assessment %s: subject=%s visit=%s", assessment_id, payload.subject_id, payload.visit)
        return assessment

    def update_assessment(
        self, assessment_id: str, payload: COAAssessmentUpdate
    ) -> COAAssessment | None:
        """Update an existing COA assessment."""
        with self._lock:
            existing = self._assessments.get(assessment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = COAAssessment(**data)
            self._assessments[assessment_id] = updated
        return updated

    def delete_assessment(self, assessment_id: str) -> bool:
        """Delete an assessment. Returns True if deleted."""
        with self._lock:
            if assessment_id in self._assessments:
                del self._assessments[assessment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Instrument Validation Management
    # ------------------------------------------------------------------

    def list_validations(
        self,
        *,
        instrument_id: str | None = None,
    ) -> list[InstrumentValidation]:
        """List instrument validations with optional filter."""
        with self._lock:
            result = list(self._validations.values())

        if instrument_id is not None:
            result = [v for v in result if v.instrument_id == instrument_id]

        return sorted(result, key=lambda v: v.validation_date, reverse=True)

    def get_validation(self, validation_id: str) -> InstrumentValidation | None:
        """Get a single validation by ID."""
        with self._lock:
            return self._validations.get(validation_id)

    def create_validation(self, payload: InstrumentValidationCreate) -> InstrumentValidation:
        """Create a new instrument validation."""
        validation_id = f"COA-VAL-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        validation = InstrumentValidation(
            id=validation_id,
            instrument_id=payload.instrument_id,
            validation_level=payload.validation_level,
            study_name=payload.study_name,
            population=payload.population,
            validated_by=payload.validated_by,
            sample_size=payload.sample_size,
            validation_date=now,
            created_at=now,
        )
        with self._lock:
            self._validations[validation_id] = validation
        logger.info("Created instrument validation %s: %s", validation_id, payload.study_name)
        return validation

    def update_validation(
        self, validation_id: str, payload: InstrumentValidationUpdate
    ) -> InstrumentValidation | None:
        """Update an existing instrument validation."""
        with self._lock:
            existing = self._validations.get(validation_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = InstrumentValidation(**data)
            self._validations[validation_id] = updated
        return updated

    def delete_validation(self, validation_id: str) -> bool:
        """Delete a validation. Returns True if deleted."""
        with self._lock:
            if validation_id in self._validations:
                del self._validations[validation_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Translation/Adaptation Management
    # ------------------------------------------------------------------

    def list_translations(
        self,
        *,
        instrument_id: str | None = None,
    ) -> list[TranslationAdaptation]:
        """List translation adaptations with optional filter."""
        with self._lock:
            result = list(self._translations.values())

        if instrument_id is not None:
            result = [t for t in result if t.instrument_id == instrument_id]

        return sorted(result, key=lambda t: t.id)

    def get_translation(self, translation_id: str) -> TranslationAdaptation | None:
        """Get a single translation by ID."""
        with self._lock:
            return self._translations.get(translation_id)

    def create_translation(self, payload: TranslationAdaptationCreate) -> TranslationAdaptation:
        """Create a new translation adaptation."""
        translation_id = f"COA-TRN-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        translation = TranslationAdaptation(
            id=translation_id,
            instrument_id=payload.instrument_id,
            target_language=payload.target_language,
            target_country=payload.target_country,
            translation_method=payload.translation_method,
            created_at=now,
        )
        with self._lock:
            self._translations[translation_id] = translation
        logger.info(
            "Created translation %s: instrument=%s language=%s",
            translation_id, payload.instrument_id, payload.target_language,
        )
        return translation

    def update_translation(
        self, translation_id: str, payload: TranslationAdaptationUpdate
    ) -> TranslationAdaptation | None:
        """Update an existing translation."""
        with self._lock:
            existing = self._translations.get(translation_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = TranslationAdaptation(**data)
            self._translations[translation_id] = updated
        return updated

    def delete_translation(self, translation_id: str) -> bool:
        """Delete a translation. Returns True if deleted."""
        with self._lock:
            if translation_id in self._translations:
                del self._translations[translation_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Compliance Report Management
    # ------------------------------------------------------------------

    def list_compliance_reports(
        self,
        *,
        trial_id: str | None = None,
        instrument_id: str | None = None,
    ) -> list[COAComplianceReport]:
        """List compliance reports with optional filters."""
        with self._lock:
            result = list(self._compliance_reports.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if instrument_id is not None:
            result = [r for r in result if r.instrument_id == instrument_id]

        return sorted(result, key=lambda r: r.generated_date, reverse=True)

    def get_compliance_report(self, report_id: str) -> COAComplianceReport | None:
        """Get a single compliance report by ID."""
        with self._lock:
            return self._compliance_reports.get(report_id)

    def create_compliance_report(self, payload: COAComplianceReportCreate) -> COAComplianceReport:
        """Create a new compliance report."""
        report_id = f"COA-CMP-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        report = COAComplianceReport(
            id=report_id,
            trial_id=payload.trial_id,
            instrument_id=payload.instrument_id,
            reporting_period_start=payload.reporting_period_start,
            reporting_period_end=payload.reporting_period_end,
            generated_by=payload.generated_by,
            generated_date=now,
        )
        with self._lock:
            self._compliance_reports[report_id] = report
        logger.info("Created compliance report %s: trial=%s", report_id, payload.trial_id)
        return report

    def update_compliance_report(
        self, report_id: str, payload: COAComplianceReportUpdate
    ) -> COAComplianceReport | None:
        """Update an existing compliance report."""
        with self._lock:
            existing = self._compliance_reports.get(report_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = COAComplianceReport(**data)
            self._compliance_reports[report_id] = updated
        return updated

    def delete_compliance_report(self, report_id: str) -> bool:
        """Delete a compliance report. Returns True if deleted."""
        with self._lock:
            if report_id in self._compliance_reports:
                del self._compliance_reports[report_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> COAMetrics:
        """Compute aggregated COA metrics."""
        with self._lock:
            instruments = list(self._instruments.values())
            assessments = list(self._assessments.values())
            validations = list(self._validations.values())
            translations = list(self._translations.values())
            compliance_reports = list(self._compliance_reports.values())

        if trial_id is not None:
            instruments = [i for i in instruments if i.trial_id == trial_id]
            assessments = [a for a in assessments if a.trial_id == trial_id]
            # Validations and translations filter by instrument_id in this trial
            trial_instrument_ids = {i.id for i in instruments}
            validations = [v for v in validations if v.instrument_id in trial_instrument_ids]
            translations = [t for t in translations if t.instrument_id in trial_instrument_ids]
            compliance_reports = [r for r in compliance_reports if r.trial_id == trial_id]

        # Instruments by type
        instruments_by_type: dict[str, int] = {}
        for i in instruments:
            key = i.coa_type.value
            instruments_by_type[key] = instruments_by_type.get(key, 0) + 1

        # Instruments by status
        instruments_by_status: dict[str, int] = {}
        for i in instruments:
            key = i.status.value
            instruments_by_status[key] = instruments_by_status.get(key, 0) + 1

        # Assessments by status
        assessments_by_status: dict[str, int] = {}
        for a in assessments:
            key = a.completion_status.value
            assessments_by_status[key] = assessments_by_status.get(key, 0) + 1

        # Overall compliance percentage
        total_expected = sum(r.total_expected for r in compliance_reports)
        total_completed = sum(r.total_completed for r in compliance_reports)
        overall_compliance = round(
            (total_completed / total_expected * 100.0) if total_expected > 0 else 0.0, 1
        )

        # Validations by level
        validations_by_level: dict[str, int] = {}
        for v in validations:
            key = v.validation_level.value
            validations_by_level[key] = validations_by_level.get(key, 0) + 1

        # Translations completed
        translations_completed = sum(1 for t in translations if t.status == "completed")

        # Average data quality issues
        avg_dq_issues = round(
            (sum(r.data_quality_issues for r in compliance_reports) / len(compliance_reports))
            if compliance_reports else 0.0,
            1,
        )

        return COAMetrics(
            total_instruments=len(instruments),
            instruments_by_type=instruments_by_type,
            instruments_by_status=instruments_by_status,
            total_assessments=len(assessments),
            assessments_by_status=assessments_by_status,
            overall_compliance_pct=overall_compliance,
            total_validations=len(validations),
            validations_by_level=validations_by_level,
            total_translations=len(translations),
            translations_completed=translations_completed,
            total_compliance_reports=len(compliance_reports),
            avg_data_quality_issues=avg_dq_issues,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: ClinicalOutcomeAssessmentService | None = None
_instance_lock = threading.Lock()


def get_clinical_outcome_assessment_service() -> ClinicalOutcomeAssessmentService:
    """Return the singleton ClinicalOutcomeAssessmentService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ClinicalOutcomeAssessmentService()
    return _instance


def reset_clinical_outcome_assessment_service() -> ClinicalOutcomeAssessmentService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = ClinicalOutcomeAssessmentService()
    return _instance
