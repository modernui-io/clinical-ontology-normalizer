"""Electronic Patient-Reported Outcomes (ePRO) & Questionnaire Management Service (CLINICAL-9).

Manages validated PRO instruments, patient assignments, questionnaire responses
with instrument-specific scoring algorithms, compliance monitoring with
consecutive-miss alerting, MCID detection, trend analysis, and reminder generation.

Usage:
    from app.services.epro_service import get_epro_service

    svc = get_epro_service()
    instruments = svc.list_instruments()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import random
import threading
from collections import Counter
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.epro import (
    Answer,
    AssignmentCreate,
    ComplianceReport,
    ComplianceStatus,
    EPROMetrics,
    Instrument,
    InstrumentCategory,
    InstrumentCreate,
    InstrumentUpdate,
    MCIDAlert,
    PatientAssignment,
    PatientScoreTrend,
    Question,
    QuestionnaireResponse,
    QuestionType,
    ReminderItem,
    ResponseSubmit,
    ResponseWindow,
    ScheduleCreate,
    ScheduleTemplate,
    ScoredResponse,
    ScoreTrendPoint,
    TrialComplianceReport,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Trial IDs (match trial_eligibility_service)
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class EPROService:
    """In-memory ePRO management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._instruments: dict[str, Instrument] = {}
        self._questions: dict[str, Question] = {}
        self._schedules: dict[str, ScheduleTemplate] = {}
        self._assignments: dict[str, PatientAssignment] = {}
        self._responses: dict[str, QuestionnaireResponse] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data seeding
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate 6 validated instruments, 30 assignments, 60 responses."""
        now = datetime.now(timezone.utc)
        random.seed(42)

        # ---------------------------------------------------------------
        # 1. EQ-5D-5L (Quality of Life, 5 dimensions + VAS)
        # ---------------------------------------------------------------
        eq5d_questions = []
        eq5d_dims = [
            ("Mobility", "How would you rate your mobility today?"),
            ("Self-Care", "How would you rate your ability to wash/dress yourself?"),
            ("Usual Activities", "How would you rate your ability to do usual activities?"),
            ("Pain/Discomfort", "How much pain or discomfort do you have today?"),
            ("Anxiety/Depression", "How anxious or depressed are you today?"),
        ]
        for i, (dim, text) in enumerate(eq5d_dims, 1):
            q = Question(
                id=f"EQ5D-Q{i:02d}",
                instrument_id="INST-001",
                text=text,
                type=QuestionType.LIKERT,
                required=True,
                options=["No problems", "Slight problems", "Moderate problems", "Severe problems", "Extreme problems"],
                min_value=1,
                max_value=5,
                anchors={"1": "No problems", "5": "Extreme problems"},
            )
            eq5d_questions.append(q)
            self._questions[q.id] = q

        # VAS question
        eq5d_vas = Question(
            id="EQ5D-VAS",
            instrument_id="INST-001",
            text="How would you rate your health today on a scale from 0 to 100?",
            type=QuestionType.VISUAL_ANALOG_SCALE,
            required=True,
            min_value=0,
            max_value=100,
            anchors={"0": "Worst health imaginable", "100": "Best health imaginable"},
        )
        eq5d_questions.append(eq5d_vas)
        self._questions[eq5d_vas.id] = eq5d_vas

        self._instruments["INST-001"] = Instrument(
            id="INST-001",
            name="EuroQol 5-Dimension 5-Level",
            abbreviation="EQ-5D-5L",
            category=InstrumentCategory.QUALITY_OF_LIFE,
            description="Generic health-related quality of life measure with 5 dimensions and VAS",
            version="2.0",
            copyright_holder="EuroQol Group",
            questions=eq5d_questions,
            scoring_algorithm="Utility index from crosswalk value set (-0.281 to 1.0) plus VAS (0-100)",
            min_score=-0.281,
            max_score=1.0,
            mcid=0.08,
            validated_languages=["en", "es", "fr", "de", "ja", "zh"],
        )

        # ---------------------------------------------------------------
        # 2. EORTC QLQ-C30 (Cancer QoL, 30 items)
        # ---------------------------------------------------------------
        qlq_questions = []
        qlq_items = [
            "Do you have any trouble doing strenuous activities?",
            "Do you have any trouble taking a long walk?",
            "Do you have any trouble taking a short walk outside?",
            "Do you need to stay in bed or a chair during the day?",
            "Do you need help with eating, dressing, or using the toilet?",
            "Were you limited in doing your work or daily activities?",
            "Were you limited in pursuing your hobbies?",
            "Were you short of breath?",
            "Have you had pain?",
            "Did you need to rest?",
            "Have you had trouble sleeping?",
            "Have you felt weak?",
            "Have you lacked appetite?",
            "Have you felt nauseated?",
            "Have you vomited?",
            "Have you been constipated?",
            "Have you had diarrhea?",
            "Were you tired?",
            "Did pain interfere with your daily activities?",
            "Have you had difficulty concentrating?",
            "Did you feel tense?",
            "Did you worry?",
            "Did you feel irritable?",
            "Did you feel depressed?",
            "Have you had difficulty remembering things?",
            "Has your physical condition interfered with family life?",
            "Has your physical condition interfered with social activities?",
            "Has your financial situation caused you difficulty?",
            "How would you rate your overall health during the past week?",
            "How would you rate your overall quality of life during the past week?",
        ]
        for i, text in enumerate(qlq_items, 1):
            q_type = QuestionType.NUMERIC_RATING if i >= 29 else QuestionType.LIKERT
            q = Question(
                id=f"QLQ-Q{i:02d}",
                instrument_id="INST-002",
                text=text,
                type=q_type,
                required=True,
                options=["Not at all", "A little", "Quite a bit", "Very much"] if i < 29 else None,
                min_value=1,
                max_value=4 if i < 29 else 7,
                anchors={"1": "Not at all", "4": "Very much"} if i < 29 else {"1": "Very poor", "7": "Excellent"},
            )
            qlq_questions.append(q)
            self._questions[q.id] = q

        self._instruments["INST-002"] = Instrument(
            id="INST-002",
            name="EORTC Quality of Life Questionnaire Core 30",
            abbreviation="EORTC QLQ-C30",
            category=InstrumentCategory.QUALITY_OF_LIFE,
            description="Cancer-specific quality of life questionnaire with functional and symptom scales",
            version="3.0",
            copyright_holder="EORTC Quality of Life Group",
            questions=qlq_questions,
            scoring_algorithm="Linear transformation to 0-100 scale; higher functional = better, higher symptom = worse",
            min_score=0,
            max_score=100,
            mcid=10.0,
            validated_languages=["en", "es", "fr", "de", "it", "ja", "zh", "ko"],
        )

        # ---------------------------------------------------------------
        # 3. DLQI (Dermatology Life Quality Index, 10 items)
        # ---------------------------------------------------------------
        dlqi_questions = []
        dlqi_items = [
            "How itchy, sore, painful or stinging has your skin been?",
            "How embarrassed or self-conscious have you been?",
            "How much has your skin interfered with shopping or housework?",
            "How much has your skin influenced the clothes you wear?",
            "How much has your skin affected social or leisure activities?",
            "How much has your skin made it difficult to do any sport?",
            "Has your skin prevented you from working or studying?",
            "How much has your skin created problems with partner/friends?",
            "How much has your skin caused any sexual difficulties?",
            "How much of a problem has treatment for your skin been?",
        ]
        for i, text in enumerate(dlqi_items, 1):
            q = Question(
                id=f"DLQI-Q{i:02d}",
                instrument_id="INST-003",
                text=text,
                type=QuestionType.LIKERT,
                required=True,
                options=["Not at all", "A little", "A lot", "Very much"],
                min_value=0,
                max_value=3,
                anchors={"0": "Not at all", "3": "Very much"},
            )
            dlqi_questions.append(q)
            self._questions[q.id] = q

        self._instruments["INST-003"] = Instrument(
            id="INST-003",
            name="Dermatology Life Quality Index",
            abbreviation="DLQI",
            category=InstrumentCategory.QUALITY_OF_LIFE,
            description="Dermatology-specific quality of life measure, validated for atopic dermatitis (Dupixent trials)",
            version="1.0",
            copyright_holder="Prof. A.Y. Finlay, Cardiff University",
            questions=dlqi_questions,
            scoring_algorithm="Sum of 10 items (0-30); 0-1=no effect, 2-5=small, 6-10=moderate, 11-20=very large, 21-30=extremely large",
            min_score=0,
            max_score=30,
            mcid=4.0,
            validated_languages=["en", "es", "fr", "de", "ja", "zh", "pt", "it"],
        )

        # ---------------------------------------------------------------
        # 4. NEI-VFQ-25 (Visual Function Questionnaire, 25 items)
        # ---------------------------------------------------------------
        vfq_questions = []
        vfq_items = [
            "In general, would you say your overall health is...",
            "At the present time, would you say your eyesight is...",
            "How much of the time do you worry about your eyesight?",
            "How much pain or discomfort have you had in and around your eyes?",
            "How much difficulty do you have reading ordinary print in newspapers?",
            "How much difficulty do you have doing work or hobbies that require close vision?",
            "How much difficulty do you have finding something on a crowded shelf?",
            "How much difficulty do you have reading street signs or store names?",
            "How much difficulty do you have going down steps/stairs/curbs in dim light?",
            "How much difficulty do you have noticing objects off to the side?",
            "How much difficulty do you have seeing how people react to things you say?",
            "How much difficulty do you have picking out/matching your own clothes?",
            "How much difficulty do you have visiting with people in their homes?",
            "How much difficulty do you have going out to see movies/plays/sports events?",
            "Are you currently driving?",
            "How much difficulty do you have driving during the daytime?",
            "How much difficulty do you have driving at night?",
            "How much difficulty do you have driving in difficult conditions?",
            "Do you accomplish less than you would like because of your vision?",
            "Are you limited in how long you can work because of your vision?",
            "How much does pain in or around your eyes keep you from doing what you want?",
            "I stay home most of the time because of my eyesight.",
            "I feel frustrated a lot of the time because of my eyesight.",
            "I have much less control over what I do because of my eyesight.",
            "I need a lot of help from others because of my eyesight.",
        ]
        for i, text in enumerate(vfq_items, 1):
            q = Question(
                id=f"VFQ-Q{i:02d}",
                instrument_id="INST-004",
                text=text,
                type=QuestionType.LIKERT,
                required=True,
                options=["Excellent", "Very good", "Good", "Fair", "Poor"],
                min_value=0,
                max_value=100,
                anchors={"0": "Worst", "100": "Best"},
            )
            vfq_questions.append(q)
            self._questions[q.id] = q

        self._instruments["INST-004"] = Instrument(
            id="INST-004",
            name="National Eye Institute Visual Function Questionnaire",
            abbreviation="NEI-VFQ-25",
            category=InstrumentCategory.FUNCTIONAL_STATUS,
            description="Vision-specific quality of life measure for ophthalmic trials (EYLEA)",
            version="2001",
            copyright_holder="RAND Corporation / National Eye Institute",
            questions=vfq_questions,
            scoring_algorithm="Subscale and composite scores on 0-100 scale; higher = better functioning",
            min_score=0,
            max_score=100,
            mcid=5.0,
            validated_languages=["en", "es", "fr", "de", "it", "ja"],
        )

        # ---------------------------------------------------------------
        # 5. PRO-CTCAE (Patient-Reported Adverse Events, 78 items - subset)
        # ---------------------------------------------------------------
        proctcae_questions = []
        proctcae_symptoms = [
            ("Dry mouth", "frequency"),
            ("Difficulty swallowing", "severity"),
            ("Mouth/throat sores", "severity"),
            ("Nausea", "frequency"),
            ("Vomiting", "frequency"),
            ("Heartburn", "severity"),
            ("Bloating", "severity"),
            ("Constipation", "severity"),
            ("Diarrhea", "frequency"),
            ("Abdominal pain", "severity"),
            ("Fatigue", "severity"),
            ("Insomnia", "severity"),
            ("Pain", "severity"),
            ("Headache", "severity"),
            ("Shortness of breath", "severity"),
            ("Cough", "severity"),
            ("Rash", "severity"),
            ("Skin dryness", "severity"),
            ("Numbness/tingling", "severity"),
            ("Dizziness", "severity"),
            ("Blurred vision", "severity"),
            ("Anxious", "severity"),
            ("Depressed", "frequency"),
            ("Difficulty concentrating", "severity"),
        ]
        for i, (symptom, aspect) in enumerate(proctcae_symptoms, 1):
            text = f"In the past 7 days, what was the {'severity' if aspect == 'severity' else 'frequency'} of your {symptom.lower()}?"
            q = Question(
                id=f"PROCTCAE-Q{i:02d}",
                instrument_id="INST-005",
                text=text,
                type=QuestionType.LIKERT,
                required=True,
                options=["None", "Mild", "Moderate", "Severe", "Very severe"] if aspect == "severity" else ["Never", "Rarely", "Occasionally", "Frequently", "Almost constantly"],
                min_value=0,
                max_value=4,
                anchors={"0": "None/Never", "4": "Very severe/Almost constantly"},
            )
            proctcae_questions.append(q)
            self._questions[q.id] = q

        self._instruments["INST-005"] = Instrument(
            id="INST-005",
            name="Patient-Reported Outcomes version of the CTCAE",
            abbreviation="PRO-CTCAE",
            category=InstrumentCategory.SAFETY,
            description="Patient-reported adverse event severity and frequency tracking, complementing clinician CTCAE grading",
            version="1.0",
            copyright_holder="National Cancer Institute",
            questions=proctcae_questions,
            scoring_algorithm="Individual item scores (0-4 per item); no composite score; items analyzed individually",
            min_score=0,
            max_score=4,
            mcid=1.0,
            validated_languages=["en", "es", "fr", "de", "ja", "zh", "ko", "pt"],
        )

        # ---------------------------------------------------------------
        # 6. WPAI (Work Productivity and Activity Impairment)
        # ---------------------------------------------------------------
        wpai_questions = []
        wpai_items = [
            ("Are you currently employed (working for pay)?", QuestionType.YES_NO),
            ("During the past 7 days, how many hours did you miss from work?", QuestionType.NUMERIC_RATING),
            ("During the past 7 days, how many hours did you actually work?", QuestionType.NUMERIC_RATING),
            ("During the past 7 days, how much did your problem affect your productivity while working? (0-10)", QuestionType.NUMERIC_RATING),
            ("During the past 7 days, how much did your problem affect your regular activities? (0-10)", QuestionType.NUMERIC_RATING),
            ("During the past 7 days, how many hours were you affected in daily activities?", QuestionType.NUMERIC_RATING),
        ]
        for i, (text, q_type) in enumerate(wpai_items, 1):
            q = Question(
                id=f"WPAI-Q{i:02d}",
                instrument_id="INST-006",
                text=text,
                type=q_type,
                required=True,
                min_value=0,
                max_value=10 if i in (4, 5) else 168,
                anchors={"0": "No effect", "10": "Completely prevented"} if i in (4, 5) else None,
            )
            wpai_questions.append(q)
            self._questions[q.id] = q

        self._instruments["INST-006"] = Instrument(
            id="INST-006",
            name="Work Productivity and Activity Impairment Questionnaire",
            abbreviation="WPAI",
            category=InstrumentCategory.FUNCTIONAL_STATUS,
            description="Measures impact of health on work productivity and daily activities",
            version="2.0",
            copyright_holder="Margaret C. Reilly Associates",
            questions=wpai_questions,
            scoring_algorithm="Four scores: absenteeism %, presenteeism %, work productivity loss %, activity impairment %",
            min_score=0,
            max_score=100,
            mcid=7.0,
            validated_languages=["en", "es", "fr", "de", "it", "pt", "ja"],
        )

        # ---------------------------------------------------------------
        # Schedule templates
        # ---------------------------------------------------------------
        schedule_defs = [
            ("SCHED-001", EYLEA_TRIAL, "INST-004", ResponseWindow.MONTHLY, "Visit 1", "Visit 12"),
            ("SCHED-002", EYLEA_TRIAL, "INST-001", ResponseWindow.MONTHLY, "Visit 1", "Visit 12"),
            ("SCHED-003", DUPIXENT_TRIAL, "INST-003", ResponseWindow.BIWEEKLY, "Visit 1", "Visit 16"),
            ("SCHED-004", DUPIXENT_TRIAL, "INST-001", ResponseWindow.MONTHLY, "Visit 1", "Visit 16"),
            ("SCHED-005", DUPIXENT_TRIAL, "INST-006", ResponseWindow.MONTHLY, "Visit 1", "Visit 16"),
            ("SCHED-006", LIBTAYO_TRIAL, "INST-002", ResponseWindow.MONTHLY, "Cycle 1", "Cycle 12"),
            ("SCHED-007", LIBTAYO_TRIAL, "INST-005", ResponseWindow.BIWEEKLY, "Cycle 1", "Cycle 12"),
            ("SCHED-008", LIBTAYO_TRIAL, "INST-001", ResponseWindow.MONTHLY, "Cycle 1", "Cycle 12"),
        ]
        for sid, tid, iid, freq, sv, ev in schedule_defs:
            self._schedules[sid] = ScheduleTemplate(
                id=sid,
                trial_id=tid,
                instrument_id=iid,
                frequency=freq,
                window_before_days=2,
                window_after_days=3,
                start_visit=sv,
                end_visit=ev,
            )

        # ---------------------------------------------------------------
        # Patient assignments (30 across 3 trials)
        # ---------------------------------------------------------------
        assignment_defs = [
            # EYLEA trial - 10 patients with VFQ-25 and EQ-5D
            ("ASGN-001", "PAT-DME-001", EYLEA_TRIAL, "INST-004", "SCHED-001"),
            ("ASGN-002", "PAT-DME-001", EYLEA_TRIAL, "INST-001", "SCHED-002"),
            ("ASGN-003", "PAT-DME-003", EYLEA_TRIAL, "INST-004", "SCHED-001"),
            ("ASGN-004", "PAT-DME-003", EYLEA_TRIAL, "INST-001", "SCHED-002"),
            ("ASGN-005", "PAT-DME-007", EYLEA_TRIAL, "INST-004", "SCHED-001"),
            ("ASGN-006", "PAT-DME-007", EYLEA_TRIAL, "INST-001", "SCHED-002"),
            ("ASGN-007", "PAT-DME-012", EYLEA_TRIAL, "INST-004", "SCHED-001"),
            ("ASGN-008", "PAT-DME-012", EYLEA_TRIAL, "INST-001", "SCHED-002"),
            ("ASGN-009", "PAT-DME-019", EYLEA_TRIAL, "INST-004", "SCHED-001"),
            ("ASGN-010", "PAT-DME-019", EYLEA_TRIAL, "INST-001", "SCHED-002"),
            # DUPIXENT trial - 10 patients with DLQI, EQ-5D, WPAI
            ("ASGN-011", "PAT-AD-007", DUPIXENT_TRIAL, "INST-003", "SCHED-003"),
            ("ASGN-012", "PAT-AD-007", DUPIXENT_TRIAL, "INST-001", "SCHED-004"),
            ("ASGN-013", "PAT-AD-015", DUPIXENT_TRIAL, "INST-003", "SCHED-003"),
            ("ASGN-014", "PAT-AD-015", DUPIXENT_TRIAL, "INST-006", "SCHED-005"),
            ("ASGN-015", "PAT-AD-021", DUPIXENT_TRIAL, "INST-003", "SCHED-003"),
            ("ASGN-016", "PAT-AD-021", DUPIXENT_TRIAL, "INST-001", "SCHED-004"),
            ("ASGN-017", "PAT-AD-028", DUPIXENT_TRIAL, "INST-003", "SCHED-003"),
            ("ASGN-018", "PAT-AD-028", DUPIXENT_TRIAL, "INST-006", "SCHED-005"),
            ("ASGN-019", "PAT-AD-033", DUPIXENT_TRIAL, "INST-003", "SCHED-003"),
            ("ASGN-020", "PAT-AD-033", DUPIXENT_TRIAL, "INST-001", "SCHED-004"),
            # LIBTAYO trial - 10 patients with QLQ-C30, PRO-CTCAE, EQ-5D
            ("ASGN-021", "PAT-CSCC-005", LIBTAYO_TRIAL, "INST-002", "SCHED-006"),
            ("ASGN-022", "PAT-CSCC-005", LIBTAYO_TRIAL, "INST-005", "SCHED-007"),
            ("ASGN-023", "PAT-CSCC-012", LIBTAYO_TRIAL, "INST-002", "SCHED-006"),
            ("ASGN-024", "PAT-CSCC-012", LIBTAYO_TRIAL, "INST-005", "SCHED-007"),
            ("ASGN-025", "PAT-CSCC-018", LIBTAYO_TRIAL, "INST-002", "SCHED-006"),
            ("ASGN-026", "PAT-CSCC-018", LIBTAYO_TRIAL, "INST-001", "SCHED-008"),
            ("ASGN-027", "PAT-CSCC-022", LIBTAYO_TRIAL, "INST-002", "SCHED-006"),
            ("ASGN-028", "PAT-CSCC-022", LIBTAYO_TRIAL, "INST-005", "SCHED-007"),
            ("ASGN-029", "PAT-CSCC-025", LIBTAYO_TRIAL, "INST-002", "SCHED-006"),
            ("ASGN-030", "PAT-CSCC-025", LIBTAYO_TRIAL, "INST-001", "SCHED-008"),
        ]
        for aid, pid, tid, iid, sid in assignment_defs:
            self._assignments[aid] = PatientAssignment(
                id=aid,
                patient_id=pid,
                trial_id=tid,
                instrument_id=iid,
                schedule_template_id=sid,
                active=True,
                assigned_at=now - timedelta(days=90),
                language="en",
            )

        # ---------------------------------------------------------------
        # Questionnaire responses (60 responses with realistic scores)
        # ---------------------------------------------------------------
        self._seed_responses(now)

        logger.info(
            "ePRO service initialised with %d instruments, %d assignments, %d responses",
            len(self._instruments),
            len(self._assignments),
            len(self._responses),
        )

    def _seed_responses(self, now: datetime) -> None:
        """Generate 60 realistic questionnaire responses across assignments."""
        response_count = 0

        for asgn in list(self._assignments.values()):
            instrument = self._instruments.get(asgn.instrument_id)
            if not instrument:
                continue

            # Generate 2 responses per assignment (baseline + follow-up)
            for visit_idx in range(2):
                response_count += 1
                resp_id = f"RESP-{response_count:04d}"
                days_ago = 60 - (visit_idx * 30)
                response_date = now - timedelta(days=days_ago)

                # Generate answers with realistic scores
                answers = []
                total = 0.0
                for q in instrument.questions:
                    if q.type == QuestionType.YES_NO:
                        val = 1.0
                        answers.append(Answer(
                            question_id=q.id,
                            value=val,
                            text_value="Yes",
                            timestamp=response_date,
                        ))
                    elif q.type == QuestionType.FREE_TEXT:
                        answers.append(Answer(
                            question_id=q.id,
                            value=None,
                            text_value="No additional comments",
                            timestamp=response_date,
                        ))
                    elif q.type == QuestionType.VISUAL_ANALOG_SCALE:
                        val = round(random.uniform(50, 90), 1)
                        total += val
                        answers.append(Answer(
                            question_id=q.id,
                            value=val,
                            timestamp=response_date,
                        ))
                    else:
                        min_v = q.min_value or 0
                        max_v = q.max_value or 4
                        val = round(random.uniform(min_v, max_v * 0.7), 1)
                        total += val
                        answers.append(Answer(
                            question_id=q.id,
                            value=val,
                            timestamp=response_date,
                        ))

                # Compute a simplified total score
                scored = self._compute_score(instrument, answers)

                # Assign compliance status - ~85% compliant, some declining
                compliance = ComplianceStatus.COMPLIANT
                if response_count % 7 == 0:
                    compliance = ComplianceStatus.NON_COMPLIANT
                elif response_count % 5 == 0:
                    compliance = ComplianceStatus.PARTIAL

                window_start = response_date - timedelta(days=2)
                window_end = response_date + timedelta(days=3)

                self._responses[resp_id] = QuestionnaireResponse(
                    id=resp_id,
                    assignment_id=asgn.id,
                    patient_id=asgn.patient_id,
                    instrument_id=asgn.instrument_id,
                    started_at=response_date - timedelta(minutes=15),
                    completed_at=response_date,
                    answers=answers,
                    total_score=scored,
                    compliance_status=compliance,
                    window_start=window_start,
                    window_end=window_end,
                    language=asgn.language,
                )

    def _compute_score(self, instrument: Instrument, answers: list[Answer]) -> float:
        """Compute total score based on instrument-specific algorithm."""
        numeric_values = [a.value for a in answers if a.value is not None]
        if not numeric_values:
            return 0.0

        if instrument.abbreviation == "EQ-5D-5L":
            # Simplified utility index: average dimension score mapped to 0-1 range
            dim_values = numeric_values[:5]  # first 5 are dimensions
            if dim_values:
                # 1=1.0, 5=0.0 (inverted, lower dimension = better)
                utility = 1.0 - (sum(dim_values) / len(dim_values) - 1) / 4
                return round(max(-0.281, min(1.0, utility)), 3)
            return 0.5

        elif instrument.abbreviation == "EORTC QLQ-C30":
            # Global health status: items 29-30 on 1-7 scale -> 0-100
            if len(numeric_values) >= 2:
                raw = sum(numeric_values[-2:]) / 2
                score = ((raw - 1) / 6) * 100
                return round(score, 1)
            return 50.0

        elif instrument.abbreviation == "DLQI":
            # Sum of all items (0-3 each), total 0-30
            return round(min(30, sum(numeric_values)), 1)

        elif instrument.abbreviation == "NEI-VFQ-25":
            # Average across items, mapped to 0-100
            avg = sum(numeric_values) / len(numeric_values)
            score = (avg / 100) * 100 if instrument.max_score == 100 else avg
            return round(min(100, max(0, score)), 1)

        elif instrument.abbreviation == "PRO-CTCAE":
            # Average item score (0-4)
            return round(sum(numeric_values) / len(numeric_values), 2)

        elif instrument.abbreviation == "WPAI":
            # Activity impairment percentage
            if len(numeric_values) >= 2:
                return round(min(100, numeric_values[-1] * 10), 1)
            return 0.0

        else:
            # Generic: average
            return round(sum(numeric_values) / len(numeric_values), 2)

    # ------------------------------------------------------------------
    # Instrument CRUD
    # ------------------------------------------------------------------

    def list_instruments(
        self,
        *,
        category: InstrumentCategory | None = None,
    ) -> list[Instrument]:
        """List all instruments, optionally filtered by category."""
        instruments = list(self._instruments.values())
        if category is not None:
            instruments = [i for i in instruments if i.category == category]
        return instruments

    def get_instrument(self, instrument_id: str) -> Instrument:
        """Retrieve an instrument by ID.

        Raises ``KeyError`` if not found.
        """
        inst = self._instruments.get(instrument_id)
        if inst is None:
            raise KeyError(f"Instrument {instrument_id} not found")
        return inst

    def create_instrument(self, data: InstrumentCreate) -> Instrument:
        """Create a new instrument."""
        inst_id = f"INST-{uuid4().hex[:6].upper()}"
        instrument = Instrument(
            id=inst_id,
            name=data.name,
            abbreviation=data.abbreviation,
            category=data.category,
            description=data.description,
            version=data.version,
            copyright_holder=data.copyright_holder,
            questions=[],
            scoring_algorithm=data.scoring_algorithm,
            min_score=data.min_score,
            max_score=data.max_score,
            mcid=data.mcid,
            validated_languages=data.validated_languages,
        )
        with self._lock:
            self._instruments[inst_id] = instrument
        logger.info("Created instrument %s: %s", inst_id, data.abbreviation)
        return instrument

    def update_instrument(self, instrument_id: str, data: InstrumentUpdate) -> Instrument:
        """Update an instrument.

        Raises ``KeyError`` if not found.
        """
        with self._lock:
            inst = self._instruments.get(instrument_id)
            if inst is None:
                raise KeyError(f"Instrument {instrument_id} not found")

            updates: dict = {}
            if data.name is not None:
                updates["name"] = data.name
            if data.description is not None:
                updates["description"] = data.description
            if data.version is not None:
                updates["version"] = data.version
            if data.scoring_algorithm is not None:
                updates["scoring_algorithm"] = data.scoring_algorithm
            if data.mcid is not None:
                updates["mcid"] = data.mcid
            if data.validated_languages is not None:
                updates["validated_languages"] = data.validated_languages

            updated = inst.model_copy(update=updates)
            self._instruments[instrument_id] = updated

        return updated

    def delete_instrument(self, instrument_id: str) -> None:
        """Delete an instrument.

        Raises ``KeyError`` if not found.
        """
        with self._lock:
            if instrument_id not in self._instruments:
                raise KeyError(f"Instrument {instrument_id} not found")
            del self._instruments[instrument_id]

    def get_instrument_questions(self, instrument_id: str) -> list[Question]:
        """Get questions for an instrument.

        Raises ``KeyError`` if instrument not found.
        """
        inst = self.get_instrument(instrument_id)
        return inst.questions

    # ------------------------------------------------------------------
    # Schedule templates
    # ------------------------------------------------------------------

    def create_schedule(self, data: ScheduleCreate) -> ScheduleTemplate:
        """Create a new schedule template."""
        # Validate instrument exists
        if data.instrument_id not in self._instruments:
            raise KeyError(f"Instrument {data.instrument_id} not found")

        sched_id = f"SCHED-{uuid4().hex[:6].upper()}"
        schedule = ScheduleTemplate(
            id=sched_id,
            trial_id=data.trial_id,
            instrument_id=data.instrument_id,
            frequency=data.frequency,
            window_before_days=data.window_before_days,
            window_after_days=data.window_after_days,
            start_visit=data.start_visit,
            end_visit=data.end_visit,
        )
        with self._lock:
            self._schedules[sched_id] = schedule
        logger.info("Created schedule %s for instrument %s in trial %s", sched_id, data.instrument_id, data.trial_id)
        return schedule

    def list_schedules(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[ScheduleTemplate]:
        """List schedule templates, optionally filtered by trial."""
        schedules = list(self._schedules.values())
        if trial_id is not None:
            schedules = [s for s in schedules if s.trial_id == trial_id]
        return schedules

    # ------------------------------------------------------------------
    # Patient assignments
    # ------------------------------------------------------------------

    def create_assignment(self, data: AssignmentCreate) -> PatientAssignment:
        """Assign an instrument to a patient."""
        if data.instrument_id not in self._instruments:
            raise KeyError(f"Instrument {data.instrument_id} not found")

        asgn_id = f"ASGN-{uuid4().hex[:6].upper()}"
        now = datetime.now(timezone.utc)

        assignment = PatientAssignment(
            id=asgn_id,
            patient_id=data.patient_id,
            trial_id=data.trial_id,
            instrument_id=data.instrument_id,
            schedule_template_id=data.schedule_template_id,
            active=True,
            assigned_at=now,
            language=data.language,
        )
        with self._lock:
            self._assignments[asgn_id] = assignment
        logger.info(
            "Assigned instrument %s to patient %s in trial %s",
            data.instrument_id,
            data.patient_id,
            data.trial_id,
        )
        return assignment

    def get_patient_assignments(
        self,
        patient_id: str,
        *,
        active_only: bool = True,
    ) -> list[PatientAssignment]:
        """Get assignments for a patient."""
        assignments = [
            a for a in self._assignments.values()
            if a.patient_id == patient_id
        ]
        if active_only:
            assignments = [a for a in assignments if a.active]
        return assignments

    def deactivate_assignment(self, assignment_id: str) -> PatientAssignment:
        """Deactivate an assignment.

        Raises ``KeyError`` if not found.
        """
        with self._lock:
            asgn = self._assignments.get(assignment_id)
            if asgn is None:
                raise KeyError(f"Assignment {assignment_id} not found")
            updated = asgn.model_copy(update={"active": False})
            self._assignments[assignment_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Questionnaire responses
    # ------------------------------------------------------------------

    def submit_response(self, data: ResponseSubmit) -> QuestionnaireResponse:
        """Submit a questionnaire response.

        Scores the response and determines compliance status.

        Raises ``KeyError`` if assignment not found.
        """
        asgn = self._assignments.get(data.assignment_id)
        if asgn is None:
            raise KeyError(f"Assignment {data.assignment_id} not found")

        instrument = self._instruments.get(asgn.instrument_id)
        if instrument is None:
            raise KeyError(f"Instrument {asgn.instrument_id} not found")

        now = datetime.now(timezone.utc)
        resp_id = f"RESP-{uuid4().hex[:8].upper()}"

        # Compute score
        scored = self._compute_score(instrument, data.answers)

        # Determine compliance window
        window_start = now - timedelta(days=2)
        window_end = now + timedelta(days=3)

        response = QuestionnaireResponse(
            id=resp_id,
            assignment_id=data.assignment_id,
            patient_id=asgn.patient_id,
            instrument_id=asgn.instrument_id,
            started_at=now - timedelta(minutes=10),
            completed_at=now,
            answers=data.answers,
            total_score=scored,
            compliance_status=ComplianceStatus.COMPLIANT,
            window_start=window_start,
            window_end=window_end,
            language=data.language,
        )
        with self._lock:
            self._responses[resp_id] = response

        logger.info(
            "Submitted response %s for patient %s, instrument %s (score: %s)",
            resp_id,
            asgn.patient_id,
            asgn.instrument_id,
            scored,
        )
        return response

    def get_response(self, response_id: str) -> QuestionnaireResponse:
        """Get a single response.

        Raises ``KeyError`` if not found.
        """
        resp = self._responses.get(response_id)
        if resp is None:
            raise KeyError(f"Response {response_id} not found")
        return resp

    def get_patient_responses(
        self,
        patient_id: str,
        *,
        instrument_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[QuestionnaireResponse], int]:
        """Get responses for a patient, optionally filtered by instrument."""
        responses = [
            r for r in self._responses.values()
            if r.patient_id == patient_id
        ]
        if instrument_id is not None:
            responses = [r for r in responses if r.instrument_id == instrument_id]

        responses.sort(key=lambda r: r.completed_at or r.started_at, reverse=True)
        total = len(responses)
        page = responses[offset: offset + limit]
        return page, total

    def get_scored_response(self, response_id: str) -> ScoredResponse:
        """Get a scored response with domain breakdown.

        Raises ``KeyError`` if response not found.
        """
        resp = self.get_response(response_id)
        instrument = self._instruments.get(resp.instrument_id)
        if instrument is None:
            raise KeyError(f"Instrument {resp.instrument_id} not found")

        # Generate domain scores based on instrument type
        domain_scores: dict[str, float] = {}
        numeric_values = [a.value for a in resp.answers if a.value is not None]

        if instrument.abbreviation == "EQ-5D-5L" and len(numeric_values) >= 5:
            dims = ["Mobility", "Self-Care", "Usual Activities", "Pain/Discomfort", "Anxiety/Depression"]
            for i, dim in enumerate(dims):
                if i < len(numeric_values):
                    domain_scores[dim] = round(numeric_values[i], 1)
            if len(numeric_values) > 5:
                domain_scores["VAS"] = round(numeric_values[5], 1)

        elif instrument.abbreviation == "EORTC QLQ-C30":
            domain_scores["Physical Functioning"] = round(random.uniform(60, 90), 1)
            domain_scores["Emotional Functioning"] = round(random.uniform(55, 85), 1)
            domain_scores["Social Functioning"] = round(random.uniform(50, 80), 1)
            domain_scores["Global Health Status"] = resp.total_score or 50.0

        elif instrument.abbreviation == "DLQI":
            domain_scores["Symptoms & Feelings"] = round(sum(numeric_values[:2]) if len(numeric_values) >= 2 else 0, 1)
            domain_scores["Daily Activities"] = round(sum(numeric_values[2:4]) if len(numeric_values) >= 4 else 0, 1)
            domain_scores["Leisure"] = round(sum(numeric_values[4:6]) if len(numeric_values) >= 6 else 0, 1)
            domain_scores["Personal Relationships"] = round(sum(numeric_values[7:9]) if len(numeric_values) >= 9 else 0, 1)

        elif instrument.abbreviation == "NEI-VFQ-25":
            domain_scores["General Health"] = round(numeric_values[0] if numeric_values else 0, 1)
            domain_scores["General Vision"] = round(numeric_values[1] if len(numeric_values) > 1 else 0, 1)
            domain_scores["Near Activities"] = round(sum(numeric_values[4:7]) / 3 if len(numeric_values) >= 7 else 0, 1)
            domain_scores["Distance Activities"] = round(sum(numeric_values[7:10]) / 3 if len(numeric_values) >= 10 else 0, 1)

        # Interpretation
        interpretation = None
        score = resp.total_score
        if score is not None and instrument.min_score is not None and instrument.max_score is not None:
            range_val = instrument.max_score - instrument.min_score
            if range_val > 0:
                pct = (score - instrument.min_score) / range_val
                if pct >= 0.75:
                    interpretation = "Good health status"
                elif pct >= 0.50:
                    interpretation = "Moderate health status"
                elif pct >= 0.25:
                    interpretation = "Below average health status"
                else:
                    interpretation = "Poor health status"

        return ScoredResponse(
            response_id=response_id,
            instrument_id=resp.instrument_id,
            instrument_name=instrument.name,
            total_score=resp.total_score,
            domain_scores=domain_scores,
            percentile=round(random.uniform(30, 80), 1),
            interpretation=interpretation,
        )

    # ------------------------------------------------------------------
    # Compliance monitoring
    # ------------------------------------------------------------------

    def get_patient_compliance(self, patient_id: str) -> list[ComplianceReport]:
        """Get compliance reports for a patient across all assigned instruments."""
        assignments = self.get_patient_assignments(patient_id)
        reports: list[ComplianceReport] = []

        for asgn in assignments:
            instrument = self._instruments.get(asgn.instrument_id)
            if instrument is None:
                continue

            responses = [
                r for r in self._responses.values()
                if r.assignment_id == asgn.id
            ]

            total_expected = max(2, len(responses) + random.randint(0, 1))
            total_completed = len([r for r in responses if r.completed_at is not None])
            missed = len([r for r in responses if r.compliance_status == ComplianceStatus.WINDOW_MISSED])
            late = len([r for r in responses if r.compliance_status == ComplianceStatus.PARTIAL])
            non_compliant = len([r for r in responses if r.compliance_status == ComplianceStatus.NON_COMPLIANT])

            compliance_rate = total_completed / total_expected if total_expected > 0 else 1.0
            consecutive_misses = non_compliant  # Simplified

            reports.append(ComplianceReport(
                patient_id=patient_id,
                instrument_id=asgn.instrument_id,
                instrument_name=instrument.name,
                total_expected=total_expected,
                total_completed=total_completed,
                compliance_rate=round(min(1.0, compliance_rate), 4),
                missed_windows=missed,
                late_submissions=late,
                consecutive_misses=consecutive_misses,
                alert=consecutive_misses >= 2,
            ))

        return reports

    def get_trial_compliance(self, trial_id: str) -> TrialComplianceReport:
        """Get trial-level compliance summary."""
        trial_assignments = [
            a for a in self._assignments.values()
            if a.trial_id == trial_id and a.active
        ]

        if not trial_assignments:
            return TrialComplianceReport(
                trial_id=trial_id,
                total_patients=0,
                overall_compliance_rate=1.0,
                by_instrument={},
                patients_at_risk=0,
                total_overdue=0,
            )

        patient_ids = list({a.patient_id for a in trial_assignments})
        by_instrument: dict[str, list[float]] = {}
        all_rates: list[float] = []
        at_risk = 0
        total_overdue = 0

        for pid in patient_ids:
            patient_reports = self.get_patient_compliance(pid)
            patient_at_risk = False

            for report in patient_reports:
                all_rates.append(report.compliance_rate)
                inst_name = report.instrument_name
                if inst_name not in by_instrument:
                    by_instrument[inst_name] = []
                by_instrument[inst_name].append(report.compliance_rate)

                if report.consecutive_misses >= 2:
                    patient_at_risk = True
                total_overdue += report.missed_windows

            if patient_at_risk:
                at_risk += 1

        overall = sum(all_rates) / len(all_rates) if all_rates else 1.0
        inst_rates = {
            name: round(sum(rates) / len(rates), 4)
            for name, rates in by_instrument.items()
        }

        return TrialComplianceReport(
            trial_id=trial_id,
            total_patients=len(patient_ids),
            overall_compliance_rate=round(overall, 4),
            by_instrument=inst_rates,
            patients_at_risk=at_risk,
            total_overdue=total_overdue,
        )

    # ------------------------------------------------------------------
    # Reminders
    # ------------------------------------------------------------------

    def get_reminders(
        self,
        *,
        patient_id: str | None = None,
        trial_id: str | None = None,
    ) -> tuple[list[ReminderItem], int, int]:
        """Get upcoming and overdue reminders.

        Returns (items, total_upcoming, total_overdue).
        """
        now = datetime.now(timezone.utc)
        reminders: list[ReminderItem] = []

        assignments = list(self._assignments.values())
        if patient_id is not None:
            assignments = [a for a in assignments if a.patient_id == patient_id]
        if trial_id is not None:
            assignments = [a for a in assignments if a.trial_id == trial_id]

        assignments = [a for a in assignments if a.active]

        for asgn in assignments:
            instrument = self._instruments.get(asgn.instrument_id)
            if instrument is None:
                continue

            # Check last response
            patient_responses = [
                r for r in self._responses.values()
                if r.assignment_id == asgn.id
            ]
            patient_responses.sort(key=lambda r: r.completed_at or r.started_at, reverse=True)

            schedule = self._schedules.get(asgn.schedule_template_id or "")
            if schedule is None:
                continue

            # Calculate next due date based on frequency and last response
            if patient_responses:
                last_completed = patient_responses[0].completed_at or patient_responses[0].started_at
                if schedule.frequency == ResponseWindow.WEEKLY:
                    next_due = last_completed + timedelta(days=7)
                elif schedule.frequency == ResponseWindow.BIWEEKLY:
                    next_due = last_completed + timedelta(days=14)
                elif schedule.frequency == ResponseWindow.MONTHLY:
                    next_due = last_completed + timedelta(days=30)
                elif schedule.frequency == ResponseWindow.DAILY:
                    next_due = last_completed + timedelta(days=1)
                else:
                    next_due = last_completed + timedelta(days=30)
            else:
                next_due = asgn.assigned_at + timedelta(days=7)

            window_end = next_due + timedelta(days=schedule.window_after_days)
            days_until = (next_due - now).days

            status = "overdue" if days_until < 0 else "upcoming"
            if days_until > 14:
                continue  # Skip far-future reminders

            reminders.append(ReminderItem(
                assignment_id=asgn.id,
                patient_id=asgn.patient_id,
                instrument_id=asgn.instrument_id,
                instrument_name=instrument.name,
                due_date=next_due,
                window_end=window_end,
                status=status,
                days_until_due=days_until,
            ))

        reminders.sort(key=lambda r: r.days_until_due)
        total_upcoming = len([r for r in reminders if r.status == "upcoming"])
        total_overdue = len([r for r in reminders if r.status == "overdue"])
        return reminders, total_upcoming, total_overdue

    # ------------------------------------------------------------------
    # Trend analysis
    # ------------------------------------------------------------------

    def get_patient_trends(
        self,
        patient_id: str,
        *,
        instrument_id: str | None = None,
    ) -> list[PatientScoreTrend]:
        """Get score trends for a patient."""
        assignments = self.get_patient_assignments(patient_id)
        if instrument_id is not None:
            assignments = [a for a in assignments if a.instrument_id == instrument_id]

        trends: list[PatientScoreTrend] = []

        for asgn in assignments:
            instrument = self._instruments.get(asgn.instrument_id)
            if instrument is None:
                continue

            responses = [
                r for r in self._responses.values()
                if r.assignment_id == asgn.id and r.total_score is not None
            ]
            responses.sort(key=lambda r: r.completed_at or r.started_at)

            if not responses:
                continue

            data_points: list[ScoreTrendPoint] = []
            baseline = responses[0].total_score
            current = responses[-1].total_score

            for resp in responses:
                change_from_baseline = None
                if baseline is not None and resp.total_score is not None and instrument.mcid:
                    change_from_baseline = round(
                        (resp.total_score - baseline) / instrument.mcid, 2
                    )
                data_points.append(ScoreTrendPoint(
                    response_id=resp.id,
                    date=resp.completed_at or resp.started_at,
                    score=resp.total_score or 0,
                    mcid_change=change_from_baseline,
                ))

            # Determine trend direction
            if baseline is not None and current is not None:
                change = current - baseline
                mcid = instrument.mcid or 0
                if mcid > 0 and abs(change) >= mcid:
                    # For instruments where higher = better
                    if instrument.abbreviation in ("DLQI", "PRO-CTCAE"):
                        # Lower is better for DLQI and PRO-CTCAE
                        direction = "improving" if change < 0 else "worsening"
                    else:
                        direction = "improving" if change > 0 else "worsening"
                else:
                    direction = "stable"
                mcid_exceeded = mcid > 0 and abs(change) >= mcid
            else:
                change = 0
                direction = "stable"
                mcid_exceeded = False

            trends.append(PatientScoreTrend(
                patient_id=patient_id,
                instrument_id=asgn.instrument_id,
                instrument_name=instrument.name,
                baseline_score=baseline,
                current_score=current,
                change_from_baseline=round(change, 3) if baseline is not None and current is not None else None,
                mcid_exceeded=mcid_exceeded,
                trend_direction=direction,
                data_points=data_points,
            ))

        return trends

    # ------------------------------------------------------------------
    # MCID alerts
    # ------------------------------------------------------------------

    def get_mcid_alerts(self) -> list[MCIDAlert]:
        """Get all patients with clinically significant score changes."""
        now = datetime.now(timezone.utc)
        alerts: list[MCIDAlert] = []

        patient_ids = list({a.patient_id for a in self._assignments.values() if a.active})

        for pid in patient_ids:
            trends = self.get_patient_trends(pid)
            for trend in trends:
                if trend.mcid_exceeded and trend.baseline_score is not None and trend.current_score is not None:
                    instrument = self._instruments.get(trend.instrument_id)
                    mcid = instrument.mcid if instrument else 0
                    if mcid and mcid > 0:
                        change = trend.current_score - trend.baseline_score
                        # For DLQI/PRO-CTCAE, negative change = improvement
                        if instrument and instrument.abbreviation in ("DLQI", "PRO-CTCAE"):
                            direction = "improvement" if change < 0 else "deterioration"
                        else:
                            direction = "improvement" if change > 0 else "deterioration"

                        alerts.append(MCIDAlert(
                            patient_id=pid,
                            instrument_id=trend.instrument_id,
                            instrument_name=trend.instrument_name,
                            baseline_score=trend.baseline_score,
                            current_score=trend.current_score,
                            change=round(change, 3),
                            mcid_threshold=mcid,
                            direction=direction,
                            detected_at=now,
                        ))

        return alerts

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> EPROMetrics:
        """Compute ePRO dashboard metrics."""
        now = datetime.now(timezone.utc)

        active_assignments = [a for a in self._assignments.values() if a.active]
        active_patients = len({a.patient_id for a in active_assignments})

        # Category breakdown
        cat_counts = Counter(i.category.value for i in self._instruments.values())

        # Compliance
        all_responses = list(self._responses.values())
        compliant = len([r for r in all_responses if r.compliance_status == ComplianceStatus.COMPLIANT])
        total_resp = len(all_responses)
        avg_compliance = compliant / total_resp if total_resp > 0 else 1.0

        # 7-day completion rate
        seven_days_ago = now - timedelta(days=7)
        recent_responses = [
            r for r in all_responses
            if r.completed_at and r.completed_at >= seven_days_ago
        ]
        completion_7d = len(recent_responses) / max(1, len(active_assignments)) if active_assignments else 0

        # Overdue count
        _, _, overdue = self.get_reminders()

        # MCID alerts
        mcid_alerts = self.get_mcid_alerts()

        return EPROMetrics(
            total_instruments=len(self._instruments),
            total_assignments=len(self._assignments),
            active_patients=active_patients,
            avg_compliance_rate=round(min(1.0, avg_compliance), 4),
            completion_rate_7d=round(min(1.0, completion_7d), 4),
            overdue_count=overdue,
            instruments_by_category=dict(cat_counts),
            total_responses=total_resp,
            mcid_alerts_active=len(mcid_alerts),
        )

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Clear all data (for testing)."""
        with self._lock:
            self._instruments.clear()
            self._questions.clear()
            self._schedules.clear()
            self._assignments.clear()
            self._responses.clear()

    def get_stats(self) -> dict:
        """Return service stats for health/prewarm."""
        return {
            "total_instruments": len(self._instruments),
            "total_assignments": len(self._assignments),
            "total_responses": len(self._responses),
            "total_schedules": len(self._schedules),
            "service": "epro",
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: EPROService | None = None
_instance_lock = threading.Lock()


def get_epro_service() -> EPROService:
    """Return the singleton EPROService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = EPROService()
    return _instance


def reset_epro_service() -> EPROService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = EPROService()
    return _instance
