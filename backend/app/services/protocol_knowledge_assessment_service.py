"""Protocol Knowledge Assessment Service (PKA-ASM).

Manages protocol knowledge assessment operations: assessment questionnaires,
assessment responses, competency records, remediation plans, and assessment
metrics.

Usage:
    from app.services.protocol_knowledge_assessment_service import (
        get_protocol_knowledge_assessment_service,
    )

    svc = get_protocol_knowledge_assessment_service()
    questionnaires = svc.list_assessment_questionnaires()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.protocol_knowledge_assessment import (
    AssessmentQuestionnaire,
    AssessmentQuestionnaireCreate,
    AssessmentQuestionnaireUpdate,
    AssessmentResponse,
    AssessmentResponseCreate,
    AssessmentResponseUpdate,
    AssessmentResult,
    CompetencyLevel,
    CompetencyRecord,
    CompetencyRecordCreate,
    CompetencyRecordUpdate,
    ProtocolKnowledgeMetrics,
    QuestionnaireStatus,
    RemediationPlan,
    RemediationPlanCreate,
    RemediationPlanUpdate,
    RemediationStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class ProtocolKnowledgeAssessmentService:
    """In-memory Protocol Knowledge Assessment engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._assessment_questionnaires: dict[str, AssessmentQuestionnaire] = {}
        self._assessment_responses: dict[str, AssessmentResponse] = {}
        self._competency_records: dict[str, CompetencyRecord] = {}
        self._remediation_plans: dict[str, RemediationPlan] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic protocol knowledge assessment data."""
        now = datetime.now(timezone.utc)

        # --- 12 Assessment Questionnaires ---
        questionnaires_data = [
            {
                "id": "AQ-001",
                "trial_id": EYLEA_TRIAL,
                "questionnaire_title": "EYLEA Protocol v3.0 Fundamentals",
                "version": "3.0",
                "questionnaire_status": QuestionnaireStatus.ACTIVE,
                "total_questions": 25,
                "passing_score_pct": 80.0,
                "time_limit_minutes": 45,
                "max_attempts": 3,
                "protocol_version": "v3.0",
                "target_roles": "CRA, Sub-Investigator, Study Coordinator",
                "authored_by": "Dr. Sarah Mitchell",
                "approved_by": "Dr. James Chen",
                "effective_date": now - timedelta(days=120),
                "notes": "Covers primary endpoints, dosing schedule, and visit windows.",
                "created_at": now - timedelta(days=130),
            },
            {
                "id": "AQ-002",
                "trial_id": EYLEA_TRIAL,
                "questionnaire_title": "EYLEA Safety Monitoring Knowledge",
                "version": "2.1",
                "questionnaire_status": QuestionnaireStatus.ACTIVE,
                "total_questions": 30,
                "passing_score_pct": 85.0,
                "time_limit_minutes": 60,
                "max_attempts": 3,
                "protocol_version": "v3.0",
                "target_roles": "Investigator, Sub-Investigator",
                "authored_by": "Dr. Emily Watson",
                "approved_by": "Dr. James Chen",
                "effective_date": now - timedelta(days=100),
                "notes": "Focuses on AE reporting, SAE timelines, and safety assessments.",
                "created_at": now - timedelta(days=110),
            },
            {
                "id": "AQ-003",
                "trial_id": EYLEA_TRIAL,
                "questionnaire_title": "EYLEA Informed Consent Process",
                "version": "1.0",
                "questionnaire_status": QuestionnaireStatus.DRAFT,
                "total_questions": 15,
                "passing_score_pct": 90.0,
                "time_limit_minutes": 30,
                "max_attempts": 2,
                "protocol_version": "v3.0",
                "target_roles": "Study Coordinator, Research Nurse",
                "authored_by": "Dr. Sarah Mitchell",
                "approved_by": None,
                "effective_date": None,
                "notes": "Draft questionnaire on ICF process and documentation requirements.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "AQ-004",
                "trial_id": EYLEA_TRIAL,
                "questionnaire_title": "EYLEA Protocol Amendment v3.1 Update",
                "version": "3.1",
                "questionnaire_status": QuestionnaireStatus.UNDER_REVIEW,
                "total_questions": 10,
                "passing_score_pct": 80.0,
                "time_limit_minutes": 20,
                "max_attempts": 3,
                "protocol_version": "v3.1",
                "target_roles": "All Site Staff",
                "authored_by": "Dr. Emily Watson",
                "approved_by": None,
                "effective_date": None,
                "notes": "Covers changes introduced in protocol amendment 3.1.",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "AQ-005",
                "trial_id": DUPIXENT_TRIAL,
                "questionnaire_title": "DUPIXENT Protocol Essentials",
                "version": "2.0",
                "questionnaire_status": QuestionnaireStatus.ACTIVE,
                "total_questions": 20,
                "passing_score_pct": 80.0,
                "time_limit_minutes": 40,
                "max_attempts": 3,
                "protocol_version": "v2.0",
                "target_roles": "CRA, Study Coordinator, Investigator",
                "authored_by": "Dr. Mark Phillips",
                "approved_by": "Dr. Lisa Park",
                "effective_date": now - timedelta(days=90),
                "notes": "Core protocol knowledge for all site personnel.",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "AQ-006",
                "trial_id": DUPIXENT_TRIAL,
                "questionnaire_title": "DUPIXENT Biomarker Sampling Procedures",
                "version": "1.5",
                "questionnaire_status": QuestionnaireStatus.ACTIVE,
                "total_questions": 18,
                "passing_score_pct": 85.0,
                "time_limit_minutes": 35,
                "max_attempts": 2,
                "protocol_version": "v2.0",
                "target_roles": "Lab Technician, Research Nurse",
                "authored_by": "Dr. Rachel Kim",
                "approved_by": "Dr. Mark Phillips",
                "effective_date": now - timedelta(days=80),
                "notes": "Specimen collection, handling, and processing per protocol.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "AQ-007",
                "trial_id": DUPIXENT_TRIAL,
                "questionnaire_title": "DUPIXENT eCRF Completion Guide",
                "version": "1.0",
                "questionnaire_status": QuestionnaireStatus.RETIRED,
                "total_questions": 22,
                "passing_score_pct": 75.0,
                "time_limit_minutes": 50,
                "max_attempts": 3,
                "protocol_version": "v1.0",
                "target_roles": "Data Entry, Study Coordinator",
                "authored_by": "Dr. Rachel Kim",
                "approved_by": "Dr. Lisa Park",
                "effective_date": now - timedelta(days=200),
                "notes": "Retired after protocol v2.0 eCRF redesign.",
                "created_at": now - timedelta(days=210),
            },
            {
                "id": "AQ-008",
                "trial_id": DUPIXENT_TRIAL,
                "questionnaire_title": "DUPIXENT Eligibility Criteria Mastery",
                "version": "2.0",
                "questionnaire_status": QuestionnaireStatus.PILOT,
                "total_questions": 12,
                "passing_score_pct": 90.0,
                "time_limit_minutes": 25,
                "max_attempts": 2,
                "protocol_version": "v2.0",
                "target_roles": "Investigator, Sub-Investigator",
                "authored_by": "Dr. Mark Phillips",
                "approved_by": None,
                "effective_date": None,
                "notes": "Pilot phase. Testing with select sites before full rollout.",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "AQ-009",
                "trial_id": LIBTAYO_TRIAL,
                "questionnaire_title": "LIBTAYO Immunotherapy Protocol Knowledge",
                "version": "1.0",
                "questionnaire_status": QuestionnaireStatus.ACTIVE,
                "total_questions": 28,
                "passing_score_pct": 85.0,
                "time_limit_minutes": 55,
                "max_attempts": 3,
                "protocol_version": "v1.0",
                "target_roles": "Oncologist, Sub-Investigator, CRA",
                "authored_by": "Dr. Angela Martinez",
                "approved_by": "Dr. Grace Lee",
                "effective_date": now - timedelta(days=70),
                "notes": "Comprehensive immunotherapy protocol assessment.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "AQ-010",
                "trial_id": LIBTAYO_TRIAL,
                "questionnaire_title": "LIBTAYO irAE Management Knowledge",
                "version": "1.0",
                "questionnaire_status": QuestionnaireStatus.ACTIVE,
                "total_questions": 35,
                "passing_score_pct": 90.0,
                "time_limit_minutes": 60,
                "max_attempts": 2,
                "protocol_version": "v1.0",
                "target_roles": "Oncologist, Sub-Investigator, Research Nurse",
                "authored_by": "Dr. Grace Lee",
                "approved_by": "Dr. Angela Martinez",
                "effective_date": now - timedelta(days=65),
                "notes": "Immune-related adverse event identification and management.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "AQ-011",
                "trial_id": LIBTAYO_TRIAL,
                "questionnaire_title": "LIBTAYO Tumor Assessment RECIST 1.1",
                "version": "1.0",
                "questionnaire_status": QuestionnaireStatus.ACTIVE,
                "total_questions": 20,
                "passing_score_pct": 85.0,
                "time_limit_minutes": 40,
                "max_attempts": 3,
                "protocol_version": "v1.0",
                "target_roles": "Radiologist, Oncologist",
                "authored_by": "Dr. Angela Martinez",
                "approved_by": "Dr. Grace Lee",
                "effective_date": now - timedelta(days=60),
                "notes": "RECIST 1.1 criteria application specific to LIBTAYO protocol.",
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "AQ-012",
                "trial_id": LIBTAYO_TRIAL,
                "questionnaire_title": "LIBTAYO Specimen Handling for IO Trials",
                "version": "1.0",
                "questionnaire_status": QuestionnaireStatus.ARCHIVED,
                "total_questions": 16,
                "passing_score_pct": 80.0,
                "time_limit_minutes": 30,
                "max_attempts": 3,
                "protocol_version": "v0.9",
                "target_roles": "Lab Technician, Research Nurse",
                "authored_by": "Dr. Grace Lee",
                "approved_by": "Dr. Angela Martinez",
                "effective_date": now - timedelta(days=150),
                "notes": "Archived. Replaced by updated specimen handling assessment.",
                "created_at": now - timedelta(days=160),
            },
        ]

        for q in questionnaires_data:
            self._assessment_questionnaires[q["id"]] = AssessmentQuestionnaire(**q)

        # --- 12 Assessment Responses ---
        responses_data = [
            {
                "id": "AR-001",
                "trial_id": EYLEA_TRIAL,
                "questionnaire_id": "AQ-001",
                "respondent_name": "Dr. Robert Hayes",
                "respondent_role": "Sub-Investigator",
                "site_id": "SITE-NY-001",
                "attempt_number": 1,
                "assessment_result": AssessmentResult.PASS,
                "score_pct": 92.0,
                "questions_answered": 25,
                "correct_answers": 23,
                "time_taken_minutes": 38,
                "started_at": now - timedelta(days=95),
                "completed_at": now - timedelta(days=95),
                "reviewed_by": "Dr. Sarah Mitchell",
                "notes": "Excellent understanding of protocol fundamentals.",
                "created_at": now - timedelta(days=95),
            },
            {
                "id": "AR-002",
                "trial_id": EYLEA_TRIAL,
                "questionnaire_id": "AQ-001",
                "respondent_name": "Nurse Maria Lopez",
                "respondent_role": "Study Coordinator",
                "site_id": "SITE-NY-001",
                "attempt_number": 1,
                "assessment_result": AssessmentResult.FAIL,
                "score_pct": 64.0,
                "questions_answered": 25,
                "correct_answers": 16,
                "time_taken_minutes": 44,
                "started_at": now - timedelta(days=90),
                "completed_at": now - timedelta(days=90),
                "reviewed_by": "Dr. Sarah Mitchell",
                "notes": "Below passing threshold. Remediation recommended.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "AR-003",
                "trial_id": EYLEA_TRIAL,
                "questionnaire_id": "AQ-001",
                "respondent_name": "Nurse Maria Lopez",
                "respondent_role": "Study Coordinator",
                "site_id": "SITE-NY-001",
                "attempt_number": 2,
                "assessment_result": AssessmentResult.PASS,
                "score_pct": 88.0,
                "questions_answered": 25,
                "correct_answers": 22,
                "time_taken_minutes": 40,
                "started_at": now - timedelta(days=75),
                "completed_at": now - timedelta(days=75),
                "reviewed_by": "Dr. Sarah Mitchell",
                "notes": "Significant improvement after remediation training.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "AR-004",
                "trial_id": EYLEA_TRIAL,
                "questionnaire_id": "AQ-002",
                "respondent_name": "Dr. Robert Hayes",
                "respondent_role": "Sub-Investigator",
                "site_id": "SITE-NY-001",
                "attempt_number": 1,
                "assessment_result": AssessmentResult.PASS,
                "score_pct": 96.7,
                "questions_answered": 30,
                "correct_answers": 29,
                "time_taken_minutes": 52,
                "started_at": now - timedelta(days=85),
                "completed_at": now - timedelta(days=85),
                "reviewed_by": "Dr. Emily Watson",
                "notes": "Near-perfect score on safety monitoring assessment.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "AR-005",
                "trial_id": DUPIXENT_TRIAL,
                "questionnaire_id": "AQ-005",
                "respondent_name": "Dr. Kevin Patel",
                "respondent_role": "Investigator",
                "site_id": "SITE-CHI-001",
                "attempt_number": 1,
                "assessment_result": AssessmentResult.PASS,
                "score_pct": 85.0,
                "questions_answered": 20,
                "correct_answers": 17,
                "time_taken_minutes": 35,
                "started_at": now - timedelta(days=80),
                "completed_at": now - timedelta(days=80),
                "reviewed_by": "Dr. Mark Phillips",
                "notes": "Meets competency threshold for protocol essentials.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "AR-006",
                "trial_id": DUPIXENT_TRIAL,
                "questionnaire_id": "AQ-005",
                "respondent_name": "Nurse Karen Liu",
                "respondent_role": "Study Coordinator",
                "site_id": "SITE-CHI-001",
                "attempt_number": 1,
                "assessment_result": AssessmentResult.CONDITIONAL_PASS,
                "score_pct": 80.0,
                "questions_answered": 20,
                "correct_answers": 16,
                "time_taken_minutes": 39,
                "started_at": now - timedelta(days=78),
                "completed_at": now - timedelta(days=78),
                "reviewed_by": "Dr. Mark Phillips",
                "notes": "Borderline pass. Additional training on eligibility criteria recommended.",
                "created_at": now - timedelta(days=78),
            },
            {
                "id": "AR-007",
                "trial_id": DUPIXENT_TRIAL,
                "questionnaire_id": "AQ-006",
                "respondent_name": "Lab Tech Rachel Green",
                "respondent_role": "Lab Technician",
                "site_id": "SITE-CHI-001",
                "attempt_number": 1,
                "assessment_result": AssessmentResult.PASS,
                "score_pct": 94.4,
                "questions_answered": 18,
                "correct_answers": 17,
                "time_taken_minutes": 28,
                "started_at": now - timedelta(days=70),
                "completed_at": now - timedelta(days=70),
                "reviewed_by": "Dr. Rachel Kim",
                "notes": "Strong knowledge of biomarker sampling procedures.",
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "AR-008",
                "trial_id": DUPIXENT_TRIAL,
                "questionnaire_id": "AQ-005",
                "respondent_name": "Dr. Alex Yun",
                "respondent_role": "Sub-Investigator",
                "site_id": "SITE-BOS-001",
                "attempt_number": 1,
                "assessment_result": AssessmentResult.INCOMPLETE,
                "score_pct": 0.0,
                "questions_answered": 8,
                "correct_answers": 7,
                "time_taken_minutes": 15,
                "started_at": now - timedelta(days=60),
                "completed_at": None,
                "reviewed_by": None,
                "notes": "Assessment interrupted. Respondent had to leave for patient emergency.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "AR-009",
                "trial_id": LIBTAYO_TRIAL,
                "questionnaire_id": "AQ-009",
                "respondent_name": "Dr. Thomas Reed",
                "respondent_role": "Oncologist",
                "site_id": "SITE-HOU-001",
                "attempt_number": 1,
                "assessment_result": AssessmentResult.PASS,
                "score_pct": 89.3,
                "questions_answered": 28,
                "correct_answers": 25,
                "time_taken_minutes": 48,
                "started_at": now - timedelta(days=55),
                "completed_at": now - timedelta(days=55),
                "reviewed_by": "Dr. Angela Martinez",
                "notes": "Solid immunotherapy protocol knowledge demonstrated.",
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "AR-010",
                "trial_id": LIBTAYO_TRIAL,
                "questionnaire_id": "AQ-010",
                "respondent_name": "Dr. Thomas Reed",
                "respondent_role": "Oncologist",
                "site_id": "SITE-HOU-001",
                "attempt_number": 1,
                "assessment_result": AssessmentResult.FAIL,
                "score_pct": 77.1,
                "questions_answered": 35,
                "correct_answers": 27,
                "time_taken_minutes": 58,
                "started_at": now - timedelta(days=50),
                "completed_at": now - timedelta(days=50),
                "reviewed_by": "Dr. Grace Lee",
                "notes": "Below 90% threshold for irAE management. Gaps in hepatotoxicity grading.",
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "AR-011",
                "trial_id": LIBTAYO_TRIAL,
                "questionnaire_id": "AQ-009",
                "respondent_name": "Nurse David Park",
                "respondent_role": "Research Nurse",
                "site_id": "SITE-HOU-001",
                "attempt_number": 1,
                "assessment_result": AssessmentResult.PENDING_REVIEW,
                "score_pct": 82.1,
                "questions_answered": 28,
                "correct_answers": 23,
                "time_taken_minutes": 53,
                "started_at": now - timedelta(days=30),
                "completed_at": now - timedelta(days=30),
                "reviewed_by": None,
                "notes": "Awaiting reviewer sign-off.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "AR-012",
                "trial_id": LIBTAYO_TRIAL,
                "questionnaire_id": "AQ-011",
                "respondent_name": "Dr. Samantha Wells",
                "respondent_role": "Radiologist",
                "site_id": "SITE-SEA-001",
                "attempt_number": 1,
                "assessment_result": AssessmentResult.VOIDED,
                "score_pct": 0.0,
                "questions_answered": 20,
                "correct_answers": 18,
                "time_taken_minutes": 32,
                "started_at": now - timedelta(days=25),
                "completed_at": now - timedelta(days=25),
                "reviewed_by": "Dr. Angela Martinez",
                "notes": "Assessment voided due to technical issue with testing platform.",
                "created_at": now - timedelta(days=25),
            },
        ]

        for r in responses_data:
            self._assessment_responses[r["id"]] = AssessmentResponse(**r)

        # --- 12 Competency Records ---
        competency_data = [
            {
                "id": "CR-001",
                "trial_id": EYLEA_TRIAL,
                "staff_name": "Dr. Robert Hayes",
                "staff_role": "Sub-Investigator",
                "site_id": "SITE-NY-001",
                "competency_level": CompetencyLevel.EXPERT,
                "latest_assessment_id": "AR-004",
                "latest_score_pct": 96.7,
                "assessments_completed": 2,
                "last_assessment_date": now - timedelta(days=85),
                "next_reassessment_date": now + timedelta(days=95),
                "certification_valid": True,
                "certification_expiry": now + timedelta(days=280),
                "approved_for_delegation": True,
                "notes": "Fully certified. Approved for protocol-specific delegation.",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "CR-002",
                "trial_id": EYLEA_TRIAL,
                "staff_name": "Nurse Maria Lopez",
                "staff_role": "Study Coordinator",
                "site_id": "SITE-NY-001",
                "competency_level": CompetencyLevel.COMPETENT,
                "latest_assessment_id": "AR-003",
                "latest_score_pct": 88.0,
                "assessments_completed": 2,
                "last_assessment_date": now - timedelta(days=75),
                "next_reassessment_date": now + timedelta(days=105),
                "certification_valid": True,
                "certification_expiry": now + timedelta(days=290),
                "approved_for_delegation": False,
                "notes": "Passed on second attempt after remediation.",
                "created_at": now - timedelta(days=95),
            },
            {
                "id": "CR-003",
                "trial_id": EYLEA_TRIAL,
                "staff_name": "Dr. Patricia Wells",
                "staff_role": "Investigator",
                "site_id": "SITE-LA-001",
                "competency_level": CompetencyLevel.NOT_ASSESSED,
                "latest_assessment_id": None,
                "latest_score_pct": 0.0,
                "assessments_completed": 0,
                "last_assessment_date": None,
                "next_reassessment_date": now + timedelta(days=15),
                "certification_valid": False,
                "certification_expiry": None,
                "approved_for_delegation": False,
                "notes": "Assessment pending. New to site.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "CR-004",
                "trial_id": EYLEA_TRIAL,
                "staff_name": "Nurse James Rodriguez",
                "staff_role": "Research Nurse",
                "site_id": "SITE-NY-001",
                "competency_level": CompetencyLevel.PROFICIENT,
                "latest_assessment_id": None,
                "latest_score_pct": 84.0,
                "assessments_completed": 1,
                "last_assessment_date": now - timedelta(days=110),
                "next_reassessment_date": now + timedelta(days=70),
                "certification_valid": True,
                "certification_expiry": now + timedelta(days=255),
                "approved_for_delegation": True,
                "notes": "Proficient in protocol procedures. Annual reassessment upcoming.",
                "created_at": now - timedelta(days=115),
            },
            {
                "id": "CR-005",
                "trial_id": DUPIXENT_TRIAL,
                "staff_name": "Dr. Kevin Patel",
                "staff_role": "Investigator",
                "site_id": "SITE-CHI-001",
                "competency_level": CompetencyLevel.PROFICIENT,
                "latest_assessment_id": "AR-005",
                "latest_score_pct": 85.0,
                "assessments_completed": 1,
                "last_assessment_date": now - timedelta(days=80),
                "next_reassessment_date": now + timedelta(days=100),
                "certification_valid": True,
                "certification_expiry": now + timedelta(days=285),
                "approved_for_delegation": True,
                "notes": "Principal Investigator certified for DUPIXENT protocol.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "CR-006",
                "trial_id": DUPIXENT_TRIAL,
                "staff_name": "Nurse Karen Liu",
                "staff_role": "Study Coordinator",
                "site_id": "SITE-CHI-001",
                "competency_level": CompetencyLevel.DEVELOPING,
                "latest_assessment_id": "AR-006",
                "latest_score_pct": 80.0,
                "assessments_completed": 1,
                "last_assessment_date": now - timedelta(days=78),
                "next_reassessment_date": now + timedelta(days=12),
                "certification_valid": False,
                "certification_expiry": None,
                "approved_for_delegation": False,
                "notes": "Conditional pass. Developing competency. Follow-up training scheduled.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "CR-007",
                "trial_id": DUPIXENT_TRIAL,
                "staff_name": "Lab Tech Rachel Green",
                "staff_role": "Lab Technician",
                "site_id": "SITE-CHI-001",
                "competency_level": CompetencyLevel.EXPERT,
                "latest_assessment_id": "AR-007",
                "latest_score_pct": 94.4,
                "assessments_completed": 1,
                "last_assessment_date": now - timedelta(days=70),
                "next_reassessment_date": now + timedelta(days=110),
                "certification_valid": True,
                "certification_expiry": now + timedelta(days=295),
                "approved_for_delegation": True,
                "notes": "Expert in biomarker sampling. Can train other lab staff.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "CR-008",
                "trial_id": DUPIXENT_TRIAL,
                "staff_name": "Dr. Alex Yun",
                "staff_role": "Sub-Investigator",
                "site_id": "SITE-BOS-001",
                "competency_level": CompetencyLevel.NOVICE,
                "latest_assessment_id": "AR-008",
                "latest_score_pct": 0.0,
                "assessments_completed": 0,
                "last_assessment_date": None,
                "next_reassessment_date": now + timedelta(days=5),
                "certification_valid": False,
                "certification_expiry": None,
                "approved_for_delegation": False,
                "notes": "Incomplete assessment. Rescheduled for completion.",
                "created_at": now - timedelta(days=65),
            },
            {
                "id": "CR-009",
                "trial_id": LIBTAYO_TRIAL,
                "staff_name": "Dr. Thomas Reed",
                "staff_role": "Oncologist",
                "site_id": "SITE-HOU-001",
                "competency_level": CompetencyLevel.COMPETENT,
                "latest_assessment_id": "AR-010",
                "latest_score_pct": 77.1,
                "assessments_completed": 2,
                "last_assessment_date": now - timedelta(days=50),
                "next_reassessment_date": now + timedelta(days=10),
                "certification_valid": True,
                "certification_expiry": now + timedelta(days=130),
                "approved_for_delegation": True,
                "notes": "Passed protocol knowledge but needs remediation on irAE management.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "CR-010",
                "trial_id": LIBTAYO_TRIAL,
                "staff_name": "Nurse David Park",
                "staff_role": "Research Nurse",
                "site_id": "SITE-HOU-001",
                "competency_level": CompetencyLevel.DEVELOPING,
                "latest_assessment_id": "AR-011",
                "latest_score_pct": 82.1,
                "assessments_completed": 1,
                "last_assessment_date": now - timedelta(days=30),
                "next_reassessment_date": now + timedelta(days=60),
                "certification_valid": False,
                "certification_expiry": None,
                "approved_for_delegation": False,
                "notes": "Pending review of assessment results.",
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "CR-011",
                "trial_id": LIBTAYO_TRIAL,
                "staff_name": "Dr. Samantha Wells",
                "staff_role": "Radiologist",
                "site_id": "SITE-SEA-001",
                "competency_level": CompetencyLevel.NOT_ASSESSED,
                "latest_assessment_id": "AR-012",
                "latest_score_pct": 0.0,
                "assessments_completed": 0,
                "last_assessment_date": None,
                "next_reassessment_date": now + timedelta(days=7),
                "certification_valid": False,
                "certification_expiry": None,
                "approved_for_delegation": False,
                "notes": "Previous assessment voided. Reassessment scheduled.",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "CR-012",
                "trial_id": LIBTAYO_TRIAL,
                "staff_name": "Dr. Angela Martinez",
                "staff_role": "Sub-Investigator",
                "site_id": "SITE-HOU-001",
                "competency_level": CompetencyLevel.EXPERT,
                "latest_assessment_id": None,
                "latest_score_pct": 97.0,
                "assessments_completed": 3,
                "last_assessment_date": now - timedelta(days=40),
                "next_reassessment_date": now + timedelta(days=140),
                "certification_valid": True,
                "certification_expiry": now + timedelta(days=325),
                "approved_for_delegation": True,
                "notes": "Protocol expert. Serves as site-level training lead.",
                "created_at": now - timedelta(days=80),
            },
        ]

        for cr in competency_data:
            self._competency_records[cr["id"]] = CompetencyRecord(**cr)

        # --- 12 Remediation Plans ---
        remediation_data = [
            {
                "id": "RP-001",
                "trial_id": EYLEA_TRIAL,
                "staff_name": "Nurse Maria Lopez",
                "site_id": "SITE-NY-001",
                "assessment_response_id": "AR-002",
                "remediation_status": RemediationStatus.COMPLETED,
                "knowledge_gaps": "Visit window calculations, dosing schedule deviations",
                "remediation_activities": "Self-study module on protocol visit windows; 1:1 mentoring session with study coordinator lead",
                "assigned_by": "Dr. Sarah Mitchell",
                "due_date": now - timedelta(days=80),
                "completed_date": now - timedelta(days=78),
                "reassessment_required": True,
                "reassessment_date": now - timedelta(days=75),
                "reassessment_score_pct": 88.0,
                "mentor_assigned": "Dr. Robert Hayes",
                "notes": "Remediation completed. Reassessment passed with 88%.",
                "created_at": now - timedelta(days=89),
            },
            {
                "id": "RP-002",
                "trial_id": EYLEA_TRIAL,
                "staff_name": "Dr. Patricia Wells",
                "site_id": "SITE-LA-001",
                "assessment_response_id": None,
                "remediation_status": RemediationStatus.ASSIGNED,
                "knowledge_gaps": "Overall protocol knowledge (not yet assessed)",
                "remediation_activities": "Complete pre-assessment training module; Review protocol synopsis and study reference guide",
                "assigned_by": "Dr. James Chen",
                "due_date": now + timedelta(days=10),
                "completed_date": None,
                "reassessment_required": True,
                "reassessment_date": None,
                "reassessment_score_pct": None,
                "mentor_assigned": "Dr. Sarah Mitchell",
                "notes": "Pre-assessment preparation for newly onboarded investigator.",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "RP-003",
                "trial_id": EYLEA_TRIAL,
                "staff_name": "Nurse James Rodriguez",
                "site_id": "SITE-NY-001",
                "assessment_response_id": None,
                "remediation_status": RemediationStatus.IN_PROGRESS,
                "knowledge_gaps": "AE grading and SAE reporting timelines",
                "remediation_activities": "Complete safety reporting e-learning; Attend mock SAE walkthrough session",
                "assigned_by": "Dr. Emily Watson",
                "due_date": now + timedelta(days=20),
                "completed_date": None,
                "reassessment_required": True,
                "reassessment_date": None,
                "reassessment_score_pct": None,
                "mentor_assigned": "Dr. Robert Hayes",
                "notes": "In progress. E-learning module 50% completed.",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "RP-004",
                "trial_id": EYLEA_TRIAL,
                "staff_name": "Tech John Reeves",
                "site_id": "SITE-NY-001",
                "assessment_response_id": None,
                "remediation_status": RemediationStatus.WAIVED,
                "knowledge_gaps": "Protocol amendment 3.1 changes",
                "remediation_activities": "Review amendment summary document",
                "assigned_by": "Dr. Sarah Mitchell",
                "due_date": now - timedelta(days=5),
                "completed_date": None,
                "reassessment_required": False,
                "reassessment_date": None,
                "reassessment_score_pct": None,
                "mentor_assigned": None,
                "notes": "Waived. Staff member transferred to different study before due date.",
                "created_at": now - timedelta(days=12),
            },
            {
                "id": "RP-005",
                "trial_id": DUPIXENT_TRIAL,
                "staff_name": "Nurse Karen Liu",
                "site_id": "SITE-CHI-001",
                "assessment_response_id": "AR-006",
                "remediation_status": RemediationStatus.IN_PROGRESS,
                "knowledge_gaps": "Eligibility criteria nuances, concomitant medication restrictions",
                "remediation_activities": "Eligibility criteria review workshop; Case study exercises on inclusion/exclusion criteria",
                "assigned_by": "Dr. Mark Phillips",
                "due_date": now + timedelta(days=7),
                "completed_date": None,
                "reassessment_required": True,
                "reassessment_date": None,
                "reassessment_score_pct": None,
                "mentor_assigned": "Dr. Kevin Patel",
                "notes": "Ongoing. Workshop completed, case studies pending.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "RP-006",
                "trial_id": DUPIXENT_TRIAL,
                "staff_name": "Dr. Alex Yun",
                "site_id": "SITE-BOS-001",
                "assessment_response_id": "AR-008",
                "remediation_status": RemediationStatus.ASSIGNED,
                "knowledge_gaps": "Full protocol knowledge (incomplete assessment)",
                "remediation_activities": "Complete protocol training module; Schedule and complete full assessment",
                "assigned_by": "Dr. Lisa Park",
                "due_date": now + timedelta(days=14),
                "completed_date": None,
                "reassessment_required": True,
                "reassessment_date": None,
                "reassessment_score_pct": None,
                "mentor_assigned": "Dr. Kevin Patel",
                "notes": "Assessment was interrupted. Full re-take required.",
                "created_at": now - timedelta(days=58),
            },
            {
                "id": "RP-007",
                "trial_id": DUPIXENT_TRIAL,
                "staff_name": "Lab Tech Alex Yun",
                "site_id": "SITE-BOS-001",
                "assessment_response_id": None,
                "remediation_status": RemediationStatus.COMPLETED,
                "knowledge_gaps": "Specimen labeling requirements, cold chain documentation",
                "remediation_activities": "Hands-on specimen handling practicum; SOP review session",
                "assigned_by": "Dr. Rachel Kim",
                "due_date": now - timedelta(days=40),
                "completed_date": now - timedelta(days=42),
                "reassessment_required": True,
                "reassessment_date": now - timedelta(days=38),
                "reassessment_score_pct": 91.0,
                "mentor_assigned": "Lab Tech Rachel Green",
                "notes": "Completed early. Excellent performance on reassessment.",
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "RP-008",
                "trial_id": DUPIXENT_TRIAL,
                "staff_name": "Nurse Karen Liu",
                "site_id": "SITE-CHI-001",
                "assessment_response_id": None,
                "remediation_status": RemediationStatus.OVERDUE,
                "knowledge_gaps": "eCRF completion guidelines for protocol v2.0",
                "remediation_activities": "eCRF data entry training; Review of common query types and resolution",
                "assigned_by": "Dr. Rachel Kim",
                "due_date": now - timedelta(days=10),
                "completed_date": None,
                "reassessment_required": True,
                "reassessment_date": None,
                "reassessment_score_pct": None,
                "mentor_assigned": None,
                "notes": "Overdue. Staff member on medical leave. Extension requested.",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "RP-009",
                "trial_id": LIBTAYO_TRIAL,
                "staff_name": "Dr. Thomas Reed",
                "site_id": "SITE-HOU-001",
                "assessment_response_id": "AR-010",
                "remediation_status": RemediationStatus.IN_PROGRESS,
                "knowledge_gaps": "irAE hepatotoxicity grading, corticosteroid taper protocols",
                "remediation_activities": "Complete irAE management training module; Review published irAE management guidelines; Case-based discussion with Dr. Martinez",
                "assigned_by": "Dr. Grace Lee",
                "due_date": now + timedelta(days=5),
                "completed_date": None,
                "reassessment_required": True,
                "reassessment_date": None,
                "reassessment_score_pct": None,
                "mentor_assigned": "Dr. Angela Martinez",
                "notes": "Training module completed. Case discussion scheduled.",
                "created_at": now - timedelta(days=48),
            },
            {
                "id": "RP-010",
                "trial_id": LIBTAYO_TRIAL,
                "staff_name": "Nurse David Park",
                "site_id": "SITE-HOU-001",
                "assessment_response_id": "AR-011",
                "remediation_status": RemediationStatus.ASSIGNED,
                "knowledge_gaps": "Infusion management, pre-medication protocols",
                "remediation_activities": "Infusion suite SOP review; Shadow experienced IO nurse for 2 infusion visits",
                "assigned_by": "Dr. Angela Martinez",
                "due_date": now + timedelta(days=25),
                "completed_date": None,
                "reassessment_required": True,
                "reassessment_date": None,
                "reassessment_score_pct": None,
                "mentor_assigned": "Nurse Senior IO Specialist",
                "notes": "Remediation plan pending review approval.",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "RP-011",
                "trial_id": LIBTAYO_TRIAL,
                "staff_name": "Dr. Samantha Wells",
                "site_id": "SITE-SEA-001",
                "assessment_response_id": "AR-012",
                "remediation_status": RemediationStatus.REASSESSED,
                "knowledge_gaps": "RECIST 1.1 target lesion selection, confirmation of progression",
                "remediation_activities": "RECIST 1.1 refresher course; Reviewed 5 practice imaging cases",
                "assigned_by": "Dr. Angela Martinez",
                "due_date": now - timedelta(days=15),
                "completed_date": now - timedelta(days=18),
                "reassessment_required": True,
                "reassessment_date": now - timedelta(days=12),
                "reassessment_score_pct": 95.0,
                "mentor_assigned": "Dr. Angela Martinez",
                "notes": "Reassessed after voided assessment. Passed with excellent score.",
                "created_at": now - timedelta(days=24),
            },
            {
                "id": "RP-012",
                "trial_id": LIBTAYO_TRIAL,
                "staff_name": "Lab Tech Amy Chen",
                "site_id": "SITE-SEA-001",
                "assessment_response_id": None,
                "remediation_status": RemediationStatus.COMPLETED,
                "knowledge_gaps": "IO specimen handling, PBMC processing timing",
                "remediation_activities": "PBMC processing training with central lab team; Reviewed updated specimen handling SOP",
                "assigned_by": "Dr. Grace Lee",
                "due_date": now - timedelta(days=30),
                "completed_date": now - timedelta(days=32),
                "reassessment_required": False,
                "reassessment_date": None,
                "reassessment_score_pct": None,
                "mentor_assigned": "Lab Tech Kevin Owens",
                "notes": "Competency verified through observed practice. No formal reassessment needed.",
                "created_at": now - timedelta(days=50),
            },
        ]

        for rp in remediation_data:
            self._remediation_plans[rp["id"]] = RemediationPlan(**rp)

    # ------------------------------------------------------------------
    # Assessment Questionnaires
    # ------------------------------------------------------------------

    def list_assessment_questionnaires(
        self,
        *,
        trial_id: str | None = None,
        questionnaire_status: QuestionnaireStatus | None = None,
    ) -> list[AssessmentQuestionnaire]:
        """List assessment questionnaires with optional filters."""
        with self._lock:
            result = list(self._assessment_questionnaires.values())

        if trial_id is not None:
            result = [q for q in result if q.trial_id == trial_id]
        if questionnaire_status is not None:
            result = [q for q in result if q.questionnaire_status == questionnaire_status]

        return sorted(result, key=lambda q: q.created_at, reverse=True)

    def get_assessment_questionnaire(self, questionnaire_id: str) -> AssessmentQuestionnaire | None:
        """Get a single assessment questionnaire by ID."""
        with self._lock:
            return self._assessment_questionnaires.get(questionnaire_id)

    def create_assessment_questionnaire(
        self, payload: AssessmentQuestionnaireCreate
    ) -> AssessmentQuestionnaire:
        """Create a new assessment questionnaire."""
        now = datetime.now(timezone.utc)
        questionnaire_id = f"AQ-{uuid4().hex[:8].upper()}"
        record = AssessmentQuestionnaire(
            id=questionnaire_id,
            trial_id=payload.trial_id,
            questionnaire_title=payload.questionnaire_title,
            version=payload.version,
            questionnaire_status=QuestionnaireStatus.DRAFT,
            total_questions=payload.total_questions,
            passing_score_pct=payload.passing_score_pct,
            time_limit_minutes=60,
            max_attempts=3,
            protocol_version=None,
            target_roles=None,
            authored_by=payload.authored_by,
            approved_by=None,
            effective_date=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._assessment_questionnaires[questionnaire_id] = record
        logger.info(
            "Created assessment questionnaire %s for trial %s",
            questionnaire_id,
            payload.trial_id,
        )
        return record

    def update_assessment_questionnaire(
        self, questionnaire_id: str, payload: AssessmentQuestionnaireUpdate
    ) -> AssessmentQuestionnaire | None:
        """Update an existing assessment questionnaire."""
        with self._lock:
            existing = self._assessment_questionnaires.get(questionnaire_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = AssessmentQuestionnaire(**data)
            self._assessment_questionnaires[questionnaire_id] = updated
        return updated

    def delete_assessment_questionnaire(self, questionnaire_id: str) -> bool:
        """Delete an assessment questionnaire. Returns True if deleted."""
        with self._lock:
            if questionnaire_id in self._assessment_questionnaires:
                del self._assessment_questionnaires[questionnaire_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Assessment Responses
    # ------------------------------------------------------------------

    def list_assessment_responses(
        self,
        *,
        trial_id: str | None = None,
        assessment_result: AssessmentResult | None = None,
        questionnaire_id: str | None = None,
    ) -> list[AssessmentResponse]:
        """List assessment responses with optional filters."""
        with self._lock:
            result = list(self._assessment_responses.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if assessment_result is not None:
            result = [r for r in result if r.assessment_result == assessment_result]
        if questionnaire_id is not None:
            result = [r for r in result if r.questionnaire_id == questionnaire_id]

        return sorted(result, key=lambda r: r.created_at, reverse=True)

    def get_assessment_response(self, response_id: str) -> AssessmentResponse | None:
        """Get a single assessment response by ID."""
        with self._lock:
            return self._assessment_responses.get(response_id)

    def create_assessment_response(self, payload: AssessmentResponseCreate) -> AssessmentResponse:
        """Create a new assessment response."""
        now = datetime.now(timezone.utc)
        response_id = f"AR-{uuid4().hex[:8].upper()}"
        record = AssessmentResponse(
            id=response_id,
            trial_id=payload.trial_id,
            questionnaire_id=payload.questionnaire_id,
            respondent_name=payload.respondent_name,
            respondent_role=payload.respondent_role,
            site_id=payload.site_id,
            attempt_number=payload.attempt_number,
            assessment_result=AssessmentResult.PENDING_REVIEW,
            score_pct=0.0,
            questions_answered=0,
            correct_answers=0,
            time_taken_minutes=0,
            started_at=payload.started_at,
            completed_at=None,
            reviewed_by=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._assessment_responses[response_id] = record
        logger.info(
            "Created assessment response %s for trial %s",
            response_id,
            payload.trial_id,
        )
        return record

    def update_assessment_response(
        self, response_id: str, payload: AssessmentResponseUpdate
    ) -> AssessmentResponse | None:
        """Update an existing assessment response."""
        with self._lock:
            existing = self._assessment_responses.get(response_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = AssessmentResponse(**data)
            self._assessment_responses[response_id] = updated
        return updated

    def delete_assessment_response(self, response_id: str) -> bool:
        """Delete an assessment response. Returns True if deleted."""
        with self._lock:
            if response_id in self._assessment_responses:
                del self._assessment_responses[response_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Competency Records
    # ------------------------------------------------------------------

    def list_competency_records(
        self,
        *,
        trial_id: str | None = None,
        competency_level: CompetencyLevel | None = None,
        site_id: str | None = None,
    ) -> list[CompetencyRecord]:
        """List competency records with optional filters."""
        with self._lock:
            result = list(self._competency_records.values())

        if trial_id is not None:
            result = [c for c in result if c.trial_id == trial_id]
        if competency_level is not None:
            result = [c for c in result if c.competency_level == competency_level]
        if site_id is not None:
            result = [c for c in result if c.site_id == site_id]

        return sorted(result, key=lambda c: c.created_at, reverse=True)

    def get_competency_record(self, record_id: str) -> CompetencyRecord | None:
        """Get a single competency record by ID."""
        with self._lock:
            return self._competency_records.get(record_id)

    def create_competency_record(self, payload: CompetencyRecordCreate) -> CompetencyRecord:
        """Create a new competency record."""
        now = datetime.now(timezone.utc)
        record_id = f"CR-{uuid4().hex[:8].upper()}"
        record = CompetencyRecord(
            id=record_id,
            trial_id=payload.trial_id,
            staff_name=payload.staff_name,
            staff_role=payload.staff_role,
            site_id=payload.site_id,
            competency_level=CompetencyLevel.NOT_ASSESSED,
            latest_assessment_id=None,
            latest_score_pct=0.0,
            assessments_completed=0,
            last_assessment_date=None,
            next_reassessment_date=None,
            certification_valid=False,
            certification_expiry=None,
            approved_for_delegation=False,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._competency_records[record_id] = record
        logger.info(
            "Created competency record %s for trial %s",
            record_id,
            payload.trial_id,
        )
        return record

    def update_competency_record(
        self, record_id: str, payload: CompetencyRecordUpdate
    ) -> CompetencyRecord | None:
        """Update an existing competency record."""
        with self._lock:
            existing = self._competency_records.get(record_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CompetencyRecord(**data)
            self._competency_records[record_id] = updated
        return updated

    def delete_competency_record(self, record_id: str) -> bool:
        """Delete a competency record. Returns True if deleted."""
        with self._lock:
            if record_id in self._competency_records:
                del self._competency_records[record_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Remediation Plans
    # ------------------------------------------------------------------

    def list_remediation_plans(
        self,
        *,
        trial_id: str | None = None,
        remediation_status: RemediationStatus | None = None,
    ) -> list[RemediationPlan]:
        """List remediation plans with optional filters."""
        with self._lock:
            result = list(self._remediation_plans.values())

        if trial_id is not None:
            result = [p for p in result if p.trial_id == trial_id]
        if remediation_status is not None:
            result = [p for p in result if p.remediation_status == remediation_status]

        return sorted(result, key=lambda p: p.created_at, reverse=True)

    def get_remediation_plan(self, plan_id: str) -> RemediationPlan | None:
        """Get a single remediation plan by ID."""
        with self._lock:
            return self._remediation_plans.get(plan_id)

    def create_remediation_plan(self, payload: RemediationPlanCreate) -> RemediationPlan:
        """Create a new remediation plan."""
        now = datetime.now(timezone.utc)
        plan_id = f"RP-{uuid4().hex[:8].upper()}"
        record = RemediationPlan(
            id=plan_id,
            trial_id=payload.trial_id,
            staff_name=payload.staff_name,
            site_id=payload.site_id,
            assessment_response_id=payload.assessment_response_id,
            remediation_status=RemediationStatus.ASSIGNED,
            knowledge_gaps=payload.knowledge_gaps,
            remediation_activities=payload.remediation_activities,
            assigned_by=payload.assigned_by,
            due_date=payload.due_date,
            completed_date=None,
            reassessment_required=True,
            reassessment_date=None,
            reassessment_score_pct=None,
            mentor_assigned=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._remediation_plans[plan_id] = record
        logger.info(
            "Created remediation plan %s for trial %s",
            plan_id,
            payload.trial_id,
        )
        return record

    def update_remediation_plan(
        self, plan_id: str, payload: RemediationPlanUpdate
    ) -> RemediationPlan | None:
        """Update an existing remediation plan."""
        with self._lock:
            existing = self._remediation_plans.get(plan_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = RemediationPlan(**data)
            self._remediation_plans[plan_id] = updated
        return updated

    def delete_remediation_plan(self, plan_id: str) -> bool:
        """Delete a remediation plan. Returns True if deleted."""
        with self._lock:
            if plan_id in self._remediation_plans:
                del self._remediation_plans[plan_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> ProtocolKnowledgeMetrics:
        """Compute aggregated protocol knowledge assessment metrics."""
        with self._lock:
            questionnaires = list(self._assessment_questionnaires.values())
            responses = list(self._assessment_responses.values())
            competency = list(self._competency_records.values())
            plans = list(self._remediation_plans.values())

        # Apply trial filter if provided
        if trial_id is not None:
            questionnaires = [q for q in questionnaires if q.trial_id == trial_id]
            responses = [r for r in responses if r.trial_id == trial_id]
            competency = [c for c in competency if c.trial_id == trial_id]
            plans = [p for p in plans if p.trial_id == trial_id]

        # Questionnaires by status
        questionnaires_by_status: dict[str, int] = {}
        for q in questionnaires:
            key = q.questionnaire_status.value
            questionnaires_by_status[key] = questionnaires_by_status.get(key, 0) + 1

        # Responses by result
        responses_by_result: dict[str, int] = {}
        for r in responses:
            key = r.assessment_result.value
            responses_by_result[key] = responses_by_result.get(key, 0) + 1

        # Average score (only for completed responses with score > 0)
        scored_responses = [r for r in responses if r.score_pct > 0]
        average_score = round(
            sum(r.score_pct for r in scored_responses) / max(1, len(scored_responses)),
            1,
        )

        # Pass rate
        gradeable = [
            r for r in responses
            if r.assessment_result in (
                AssessmentResult.PASS,
                AssessmentResult.FAIL,
                AssessmentResult.CONDITIONAL_PASS,
            )
        ]
        pass_count = sum(
            1 for r in gradeable
            if r.assessment_result in (AssessmentResult.PASS, AssessmentResult.CONDITIONAL_PASS)
        )
        pass_rate = round((pass_count / max(1, len(gradeable))) * 100, 1)

        # Competency records by level
        records_by_level: dict[str, int] = {}
        for c in competency:
            key = c.competency_level.value
            records_by_level[key] = records_by_level.get(key, 0) + 1

        # Certification rate
        certified_count = sum(1 for c in competency if c.certification_valid)
        certification_rate = round(
            (certified_count / max(1, len(competency))) * 100, 1
        )

        # Remediation plans by status
        plans_by_status: dict[str, int] = {}
        for p in plans:
            key = p.remediation_status.value
            plans_by_status[key] = plans_by_status.get(key, 0) + 1

        # Remediation completion rate
        completed_plans = sum(
            1 for p in plans
            if p.remediation_status in (
                RemediationStatus.COMPLETED,
                RemediationStatus.REASSESSED,
            )
        )
        remediation_completion_rate = round(
            (completed_plans / max(1, len(plans))) * 100, 1
        )

        return ProtocolKnowledgeMetrics(
            total_questionnaires=len(questionnaires),
            questionnaires_by_status=questionnaires_by_status,
            total_responses=len(responses),
            responses_by_result=responses_by_result,
            average_score_pct=average_score,
            pass_rate=pass_rate,
            total_competency_records=len(competency),
            records_by_level=records_by_level,
            certification_rate=certification_rate,
            total_remediation_plans=len(plans),
            plans_by_status=plans_by_status,
            remediation_completion_rate=remediation_completion_rate,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: ProtocolKnowledgeAssessmentService | None = None
_instance_lock = threading.Lock()


def get_protocol_knowledge_assessment_service() -> ProtocolKnowledgeAssessmentService:
    """Return the singleton ProtocolKnowledgeAssessmentService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ProtocolKnowledgeAssessmentService()
    return _instance


def reset_protocol_knowledge_assessment_service() -> ProtocolKnowledgeAssessmentService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = ProtocolKnowledgeAssessmentService()
    return _instance
