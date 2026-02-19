"""Benchmark Question Generator — ClinicalIntelligenceBench (NeurIPS 2026).

Generates 600 gold-standard QA questions from MIMIC-IV clinical data by:
1. Mining clinical_facts and mentions for assertion/temporal/experiencer patterns
2. Extracting source context from discharge summaries via fact_evidence provenance
3. Creating diverse question templates grounded in real patient data
4. Cross-referencing admissions for temporal and fusion questions

Tasks:
  A (200): Negation-aware fact retrieval — negation, uncertainty, family_history, conditional
  B (200): Temporal clinical reasoning — current_state, historical, sequence, duration, change
  C (100): Calculator-grounded decisions — HEART, Wells, SOFA, CKD-EPI, ASCVD, MELD
  D (100): Multi-source fusion — lab-note, vital-note, temporal_fusion, cross-note discordance
"""

from __future__ import annotations

import json
import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func as sa_func, select, text
from sqlalchemy.orm import Session

from app.models.clinical_fact import ClinicalFact, FactEvidence
from app.models.document import Document
from app.models.mention import Mention
from app.schemas.benchmark import (
    AssertionType,
    BenchmarkQuestion,
    BenchmarkQuestionSet,
    BenchmarkTask,
    CalculatorType,
    FusionType,
    QuestionDifficulty,
    TemporalType,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Question templates — rotated for diversity
# ============================================================================

_NEGATION_TEMPLATES = [
    {
        "q": "Does the patient have {condition}?",
        "a": "No. {condition} is negated/absent in the clinical record. The {section} section indicates the patient does not have this condition.",
        "difficulty": QuestionDifficulty.MEDIUM,
    },
    {
        "q": "Is there evidence of {condition} in this patient's chart?",
        "a": "No. {condition} was specifically ruled out or denied in the {section}.",
        "difficulty": QuestionDifficulty.MEDIUM,
    },
    {
        "q": "Has {condition} been diagnosed in this patient?",
        "a": "No. {condition} is absent — the patient has not been diagnosed with this condition.",
        "difficulty": QuestionDifficulty.EASY,
    },
    {
        "q": "What is this patient's status regarding {condition}?",
        "a": "{condition} is absent/not present. The clinical documentation explicitly negates this finding.",
        "difficulty": QuestionDifficulty.HARD,
    },
    {
        "q": "Should {condition} be included on this patient's active problem list?",
        "a": "No. {condition} is negated in the clinical record and should not appear on the active problem list.",
        "difficulty": QuestionDifficulty.HARD,
    },
    {
        "q": "Based on the clinical notes, does this patient suffer from {condition}?",
        "a": "No. The documentation explicitly states the patient does not have {condition}.",
        "difficulty": QuestionDifficulty.EASY,
    },
]

_UNCERTAINTY_TEMPLATES = [
    {
        "q": "Is {condition} confirmed in this patient?",
        "a": "Not confirmed. {condition} is documented as possible/suspected, not definitively diagnosed.",
        "difficulty": QuestionDifficulty.MEDIUM,
    },
    {
        "q": "What is the diagnostic certainty for {condition}?",
        "a": "Uncertain. {condition} is suspected but not confirmed. Further workup may be needed.",
        "difficulty": QuestionDifficulty.HARD,
    },
    {
        "q": "Has {condition} been definitively diagnosed in this patient?",
        "a": "No definitive diagnosis. {condition} is listed as possible/suspected in the {section}.",
        "difficulty": QuestionDifficulty.MEDIUM,
    },
    {
        "q": "Is {condition} an established diagnosis for this patient?",
        "a": "No — {condition} is documented with uncertainty. It is possible but not confirmed.",
        "difficulty": QuestionDifficulty.MEDIUM,
    },
]

_FAMILY_HISTORY_TEMPLATES = [
    {
        "q": "Does the patient have {condition}?",
        "a": "Not the patient personally. {condition} is documented as a family history finding only, not the patient's own diagnosis.",
        "difficulty": QuestionDifficulty.MEDIUM,
    },
    {
        "q": "Is {condition} in this patient's medical history?",
        "a": "{condition} is in the family history section, not the patient's personal medical history. A family member has this condition.",
        "difficulty": QuestionDifficulty.HARD,
    },
    {
        "q": "Should the patient be treated for {condition}?",
        "a": "{condition} is a family history finding — the patient does not have this condition. Treatment is not indicated based on family history alone.",
        "difficulty": QuestionDifficulty.HARD,
    },
]

_CONDITIONAL_TEMPLATES = [
    {
        "q": "Should the patient receive treatment for {condition}?",
        "a": "Treatment is conditional. {condition} management depends on specific clinical criteria being met, as documented in the {section}.",
        "difficulty": QuestionDifficulty.HARD,
    },
    {
        "q": "Is {condition} an active concern for this patient?",
        "a": "{condition} is conditional — action depends on additional clinical factors that need to be evaluated.",
        "difficulty": QuestionDifficulty.HARD,
    },
    {
        "q": "Does the patient need management for {condition}?",
        "a": "{condition} is conditional. The clinical note indicates management is contingent on specific conditions being met.",
        "difficulty": QuestionDifficulty.MEDIUM,
    },
]

_CURRENT_STATE_TEMPLATES = [
    {
        "q": "What is the patient's current status for {condition}?",
        "a": "{condition} is currently active/present as of the most recent admission.",
    },
    {
        "q": "Is {condition} an active problem for this patient?",
        "a": "Yes. {condition} is documented as a current/active problem.",
    },
    {
        "q": "Does the patient currently have {condition}?",
        "a": "Yes. {condition} is documented as current in the clinical record.",
    },
]

_HISTORICAL_TEMPLATES = [
    {
        "q": "Does the patient currently have {condition}?",
        "a": "No. {condition} is historical/resolved. It was present in the past but is no longer active.",
    },
    {
        "q": "Is {condition} an active problem for this patient?",
        "a": "No. {condition} is documented as a past/historical finding, not currently active.",
    },
    {
        "q": "Should {condition} be on the patient's active problem list?",
        "a": "No. {condition} is historical — it should be in past medical history, not the active list.",
    },
]

_SEQUENCE_TEMPLATES = [
    {
        "q": "Which was documented first: {condition_a} or {condition_b}?",
        "a": "{first} was documented before {second}, based on the admission timeline.",
    },
    {
        "q": "In what order were {condition_a} and {condition_b} identified?",
        "a": "{first} was identified first, followed by {second}.",
    },
]

_CHANGE_TEMPLATES = [
    {
        "q": "How has the patient's {domain} management changed between admissions?",
        "a": "Between admissions, {changes}.",
    },
    {
        "q": "What differences are noted in the patient's {domain} between the two visits?",
        "a": "Key changes: {changes}.",
    },
]

# Calculator question templates
_CALC_TEMPLATES: dict[str, dict[str, Any]] = {
    CalculatorType.HEART.value: {
        "question": "What is this patient's HEART score for chest pain evaluation, and what risk category does it indicate?",
        "required_labs": ["troponin"],
        "relevant_concepts": ["chest pain", "troponin", "ecg", "ekg", "age", "coronary artery disease"],
        "answer_template": "Based on the patient's data: {details}. The HEART score should be computed from History, ECG, Age, Risk factors, and Troponin.",
    },
    CalculatorType.WELLS_PE.value: {
        "question": "What is this patient's Wells score for pulmonary embolism probability?",
        "required_labs": [],
        "relevant_concepts": ["dvt", "deep venous thrombosis", "hemoptysis", "heart rate", "tachycardia", "immobilization", "surgery", "pulmonary embolism"],
        "answer_template": "Based on the patient's clinical features: {details}. The Wells PE score is computed from clinical signs, heart rate, immobilization, prior DVT/PE, hemoptysis, and cancer history.",
    },
    CalculatorType.SOFA.value: {
        "question": "What is this patient's SOFA score, and what does it indicate about organ dysfunction?",
        "required_labs": ["creatinine", "bilirubin", "platelets"],
        "relevant_concepts": ["pao2", "fio2", "platelets", "bilirubin", "creatinine", "gcs", "hypotension", "vasopressor"],
        "answer_template": "Based on the patient's lab values and clinical status: {details}. SOFA score assesses PaO2/FiO2, platelets, bilirubin, cardiovascular status (MAP/vasopressors), GCS, and creatinine.",
    },
    CalculatorType.CKD_EPI.value: {
        "question": "What is this patient's estimated GFR using the CKD-EPI equation, and what CKD stage does it indicate?",
        "required_labs": ["creatinine"],
        "relevant_concepts": ["creatinine", "creat", "gfr", "kidney", "renal"],
        "answer_template": "Based on the patient's serum creatinine: {details}. CKD-EPI requires creatinine, age, and sex.",
    },
    CalculatorType.ASCVD.value: {
        "question": "What is this patient's 10-year ASCVD risk score?",
        "required_labs": ["cholesterol"],
        "relevant_concepts": ["cholesterol", "hdl", "ldl", "blood pressure", "hypertension", "diabetes", "smoking"],
        "answer_template": "Based on the patient's cardiovascular risk factors: {details}. ASCVD risk requires total cholesterol, HDL, systolic BP, diabetes status, and smoking history.",
    },
    CalculatorType.MELD.value: {
        "question": "What is this patient's MELD score, and what does it indicate for liver disease severity?",
        "required_labs": ["bilirubin", "inr"],
        "relevant_concepts": ["bilirubin", "tbili", "inr", "creatinine", "sodium", "cirrhosis", "liver"],
        "answer_template": "Based on the patient's liver function labs: {details}. MELD score requires bilirubin, INR, creatinine, and sodium.",
    },
}

# Fusion question templates
_FUSION_TEMPLATES = {
    FusionType.LAB_NOTE.value: [
        "Are the laboratory results consistent with the clinical narrative for this patient?",
        "Do the lab values mentioned in the note align with the clinical assessment?",
        "What lab results are relevant to the clinical findings described in the note?",
    ],
    FusionType.VITAL_NOTE.value: [
        "Are the vital signs consistent with the clinical picture described in the note?",
        "What vital sign abnormalities are documented, and how do they relate to the clinical findings?",
    ],
    FusionType.TEMPORAL_FUSION.value: [
        "How do the findings from both admissions combine to tell the patient's clinical story?",
        "What is the clinical trajectory across the patient's two hospital admissions?",
    ],
    FusionType.CROSS_NOTE_DISCORDANCE.value: [
        "Are there any discrepancies between the two discharge summaries for this patient?",
        "What information changed or differs between the patient's two admission records?",
    ],
}


class BenchmarkGenerator:
    """Generates gold-standard benchmark questions from MIMIC-IV clinical data.

    Queries clinical_facts, mentions, and documents tables to find
    assertion-rich, temporal, and measurement patterns in MIMIC
    discharge summaries.

    Usage:
        generator = BenchmarkGenerator(db_session)
        task_a = generator.generate_task_a(count=200)
        generator.export_to_json({"task_a": task_a})
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self._rng = random.Random(42)  # Reproducible

    def generate_all(
        self,
        task_a_count: int = 200,
        task_b_count: int = 200,
        task_c_count: int = 100,
        task_d_count: int = 100,
    ) -> dict[str, BenchmarkQuestionSet]:
        """Generate all four task question sets."""
        results = {}
        for name, gen_fn, count in [
            ("task_a", self.generate_task_a, task_a_count),
            ("task_b", self.generate_task_b, task_b_count),
            ("task_c", self.generate_task_c, task_c_count),
            ("task_d", self.generate_task_d, task_d_count),
        ]:
            logger.info("Generating %s (%d target)...", name, count)
            try:
                results[name] = gen_fn(count)
            except Exception as exc:
                logger.error("Generation of %s failed: %s", name, exc)
                # Rollback and create empty set
                self._session.rollback()
                results[name] = BenchmarkQuestionSet(
                    task=BenchmarkTask.TASK_A_NEGATION,
                    questions=[],
                    created_at=datetime.now(timezone.utc),
                )
            logger.info(
                "  %s: %d questions generated (subtypes: %s)",
                name, results[name].total_count, results[name].subtype_distribution,
            )
        return results

    # ========================================================================
    # Shared helpers
    # ========================================================================

    def _extract_context(
        self,
        fact_id: str,
        window: int = 150,
    ) -> tuple[str, str, str | None]:
        """Extract source context for a clinical fact via provenance chain.

        Returns (context_excerpt, section, mimic_hadm_id).
        """
        try:
            stmt = (
                select(Mention.text, Mention.section, Mention.start_offset,
                       Document.text, Document.extra_metadata)
                .join(FactEvidence, FactEvidence.source_id == Mention.id)
                .join(Document, Mention.document_id == Document.id)
                .where(FactEvidence.fact_id == fact_id)
                .where(FactEvidence.source_table == "mentions")
                .limit(1)
            )
            row = self._session.execute(stmt).first()
            if row:
                mention_text, section, offset, doc_text, metadata = row
                # Extract context window around the mention
                start = max(0, offset - window)
                end = min(len(doc_text), offset + len(mention_text) + window)
                excerpt = doc_text[start:end].replace("\n", " ").strip()
                hadm_id = (metadata or {}).get("mimic_hadm_id")
                return excerpt, section or "Unknown", hadm_id
        except Exception as exc:
            logger.debug("Context extraction failed for fact %s: %s", fact_id, exc)
        return "", "Unknown", None

    def _mimic_subject_id(self, patient_id: str) -> int | None:
        """Extract numeric MIMIC subject_id from 'MIMIC-XXXXXXXX' format."""
        if patient_id.startswith("MIMIC-"):
            try:
                return int(patient_id[6:])
            except ValueError:
                pass
        return None

    def _qid(self, prefix: str) -> str:
        """Generate a unique question ID."""
        return f"bench_{prefix}_{uuid.uuid4().hex[:8]}"

    # ========================================================================
    # Task A: Negation-Aware Fact Retrieval (200 questions)
    # ========================================================================

    def generate_task_a(self, count: int = 200) -> BenchmarkQuestionSet:
        """Generate Task A questions from assertion-annotated clinical facts.

        Distribution target: 100 negation, 40 uncertainty, 30 family_history, 30 conditional.
        Falls back to additional negation questions if subtypes are under-populated.
        """
        questions: list[BenchmarkQuestion] = []

        # 1. Negation (target: 100)
        neg_qs = self._gen_assertion_questions(
            assertion_value="absent",
            subtype=AssertionType.NEGATION.value,
            templates=_NEGATION_TEMPLATES,
            target=100,
        )
        questions.extend(neg_qs)
        logger.info("  Task A negation: %d questions", len(neg_qs))

        # 2. Uncertainty (target: 40)
        unc_qs = self._gen_assertion_questions(
            assertion_value="possible",
            subtype=AssertionType.UNCERTAINTY.value,
            templates=_UNCERTAINTY_TEMPLATES,
            target=40,
        )
        questions.extend(unc_qs)
        logger.info("  Task A uncertainty: %d questions", len(unc_qs))

        # 3. Family history (target: 30)
        fam_qs = self._gen_family_history_questions(target=30)
        questions.extend(fam_qs)
        logger.info("  Task A family_history: %d questions", len(fam_qs))

        # 4. Conditional (target: 30)
        cond_qs = self._gen_assertion_questions(
            assertion_value="conditional",
            subtype=AssertionType.CONDITIONAL.value,
            templates=_CONDITIONAL_TEMPLATES,
            target=30,
        )
        questions.extend(cond_qs)
        logger.info("  Task A conditional: %d questions", len(cond_qs))

        # Backfill with additional negation if under count
        shortfall = count - len(questions)
        if shortfall > 0:
            logger.info("  Backfilling %d additional negation questions", shortfall)
            extra = self._gen_assertion_questions(
                assertion_value="absent",
                subtype=AssertionType.NEGATION.value,
                templates=_NEGATION_TEMPLATES,
                target=shortfall,
                offset=len(neg_qs),
            )
            questions.extend(extra)

        self._rng.shuffle(questions)
        return BenchmarkQuestionSet(
            task=BenchmarkTask.TASK_A_NEGATION,
            questions=questions[:count],
            created_at=datetime.now(timezone.utc),
        )

    def _gen_assertion_questions(
        self,
        assertion_value: str,
        subtype: str,
        templates: list[dict[str, Any]],
        target: int,
        offset: int = 0,
    ) -> list[BenchmarkQuestion]:
        """Generate questions for a specific assertion type from clinical_facts."""
        questions: list[BenchmarkQuestion] = []
        seen_concepts: set[tuple[str, str]] = set()  # (patient_id, concept_name)

        try:
            stmt = (
                select(ClinicalFact)
                .where(ClinicalFact.patient_id.like("MIMIC-%"))
                .where(ClinicalFact.assertion == assertion_value)
                .where(ClinicalFact.deleted_at.is_(None))
                .order_by(ClinicalFact.confidence.desc())
                .offset(offset)
                .limit(target * 3)  # Over-fetch to allow dedup
            )
            facts = list(self._session.execute(stmt).scalars().all())

            for fact in facts:
                if len(questions) >= target:
                    break

                # Deduplicate: skip same concept for same patient
                key = (fact.patient_id, fact.concept_name.lower())
                if key in seen_concepts:
                    continue
                seen_concepts.add(key)

                # Skip generic/unhelpful concepts
                if fact.concept_name.lower() in ("allergies", "nkda", "none", "na", "n/a"):
                    continue

                # Extract source context
                context_excerpt, section, hadm_id = self._extract_context(str(fact.id))

                # Select template (rotate)
                tmpl = templates[len(questions) % len(templates)]

                question_text = tmpl["q"].format(
                    condition=fact.concept_name,
                    section=section,
                )
                expected_answer = tmpl["a"].format(
                    condition=fact.concept_name,
                    section=section,
                )

                questions.append(BenchmarkQuestion(
                    question_id=self._qid(f"a_{subtype}"),
                    task=BenchmarkTask.TASK_A_NEGATION,
                    subtype=subtype,
                    question=question_text,
                    expected_answer=expected_answer,
                    mimic_subject_id=self._mimic_subject_id(fact.patient_id),
                    mimic_hadm_id=int(hadm_id) if hadm_id else None,
                    clinical_context=context_excerpt[:500] if context_excerpt else f"Patient {fact.patient_id}",
                    difficulty=tmpl.get("difficulty", QuestionDifficulty.MEDIUM),
                    scoring_rubric=(
                        {"correct_assertion": 1.0, "false_positive_penalty": -2.0}
                        if assertion_value == "absent"
                        else {"correct_assertion": 1.0}
                    ),
                    metadata={
                        "source_fact_id": str(fact.id),
                        "assertion": assertion_value,
                        "domain": str(fact.domain.value) if fact.domain else "",
                        "section": section,
                        "confidence": round(fact.confidence, 4),
                    },
                ))

        except Exception as exc:
            logger.warning("Task A %s generation failed: %s", subtype, exc)
            self._session.rollback()

        return questions

    def _gen_family_history_questions(self, target: int = 30) -> list[BenchmarkQuestion]:
        """Generate family history questions from mentions with experiencer=family."""
        questions: list[BenchmarkQuestion] = []
        seen: set[tuple[str, str]] = set()

        try:
            stmt = (
                select(Mention, Document.patient_id, Document.extra_metadata)
                .join(Document, Mention.document_id == Document.id)
                .where(Document.patient_id.like("MIMIC-%"))
                .where(Mention.experiencer == "family")
                .where(Mention.assertion == "present")
                .order_by(Mention.confidence.desc())
                .limit(target * 3)
            )
            rows = list(self._session.execute(stmt).all())

            for mention, patient_id, metadata in rows:
                if len(questions) >= target:
                    break

                key = (patient_id, mention.text.lower())
                if key in seen:
                    continue
                seen.add(key)

                # Skip very short or generic mentions
                if len(mention.text) < 2:
                    continue

                tmpl = _FAMILY_HISTORY_TEMPLATES[len(questions) % len(_FAMILY_HISTORY_TEMPLATES)]
                condition = mention.text
                hadm_id = (metadata or {}).get("mimic_hadm_id")

                questions.append(BenchmarkQuestion(
                    question_id=self._qid("a_family"),
                    task=BenchmarkTask.TASK_A_NEGATION,
                    subtype=AssertionType.FAMILY_HISTORY.value,
                    question=tmpl["q"].format(condition=condition),
                    expected_answer=tmpl["a"].format(condition=condition),
                    mimic_subject_id=self._mimic_subject_id(patient_id),
                    mimic_hadm_id=int(hadm_id) if hadm_id else None,
                    clinical_context=f"Section: {mention.section or 'Unknown'}. Mention: '{mention.text}' with experiencer=family.",
                    difficulty=tmpl["difficulty"],
                    scoring_rubric={"correct_experiencer": 1.0, "false_positive_penalty": -1.5},
                    metadata={
                        "source_mention_id": str(mention.id),
                        "section": mention.section,
                        "experiencer": "family",
                    },
                ))

        except Exception as exc:
            logger.warning("Task A family_history generation failed: %s", exc)
            self._session.rollback()

        return questions

    # ========================================================================
    # Task B: Temporal Clinical Reasoning (200 questions)
    # ========================================================================

    def generate_task_b(self, count: int = 200) -> BenchmarkQuestionSet:
        """Generate Task B questions requiring temporal reasoning.

        Uses clinical_facts with temporality data and cross-admission comparisons.
        Distribution target: 50 current_state, 50 historical, 40 sequence, 30 duration, 30 change.
        """
        questions: list[BenchmarkQuestion] = []

        # 1. Current state (target: 50)
        cs_qs = self._gen_temporal_subtype(
            temporality="current",
            subtype=TemporalType.CURRENT_STATE.value,
            templates=_CURRENT_STATE_TEMPLATES,
            target=50,
        )
        questions.extend(cs_qs)
        logger.info("  Task B current_state: %d questions", len(cs_qs))

        # 2. Historical (target: 50)
        hist_qs = self._gen_temporal_subtype(
            temporality="past",
            subtype=TemporalType.HISTORICAL.value,
            templates=_HISTORICAL_TEMPLATES,
            target=50,
        )
        questions.extend(hist_qs)
        logger.info("  Task B historical: %d questions", len(hist_qs))

        # 3. Sequence (target: 40) — requires cross-fact comparison
        seq_qs = self._gen_sequence_questions(target=40)
        questions.extend(seq_qs)
        logger.info("  Task B sequence: %d questions", len(seq_qs))

        # 4. Duration (target: 30) — conditions present across admissions
        dur_qs = self._gen_duration_questions(target=30)
        questions.extend(dur_qs)
        logger.info("  Task B duration: %d questions", len(dur_qs))

        # 5. Change (target: 30) — medication/condition changes
        chg_qs = self._gen_change_questions(target=30)
        questions.extend(chg_qs)
        logger.info("  Task B change: %d questions", len(chg_qs))

        # Backfill with additional current_state if under count
        shortfall = count - len(questions)
        if shortfall > 0:
            extra = self._gen_temporal_subtype(
                temporality="current",
                subtype=TemporalType.CURRENT_STATE.value,
                templates=_CURRENT_STATE_TEMPLATES,
                target=shortfall,
                offset=len(cs_qs),
            )
            questions.extend(extra)

        self._rng.shuffle(questions)
        return BenchmarkQuestionSet(
            task=BenchmarkTask.TASK_B_TEMPORAL,
            questions=questions[:count],
            created_at=datetime.now(timezone.utc),
        )

    def _gen_temporal_subtype(
        self,
        temporality: str,
        subtype: str,
        templates: list[dict[str, str]],
        target: int,
        offset: int = 0,
    ) -> list[BenchmarkQuestion]:
        """Generate temporal questions from facts with a specific temporality."""
        questions: list[BenchmarkQuestion] = []
        seen: set[tuple[str, str]] = set()

        try:
            stmt = (
                select(ClinicalFact)
                .where(ClinicalFact.patient_id.like("MIMIC-%"))
                .where(ClinicalFact.temporality == temporality)
                .where(ClinicalFact.assertion == "present")
                .where(ClinicalFact.domain.in_(["condition", "observation"]))
                .where(ClinicalFact.deleted_at.is_(None))
                .order_by(ClinicalFact.confidence.desc())
                .offset(offset)
                .limit(target * 4)
            )
            facts = list(self._session.execute(stmt).scalars().all())

            for fact in facts:
                if len(questions) >= target:
                    break

                key = (fact.patient_id, fact.concept_name.lower())
                if key in seen:
                    continue
                seen.add(key)

                if len(fact.concept_name) < 3:
                    continue

                tmpl = templates[len(questions) % len(templates)]
                context_excerpt, section, hadm_id = self._extract_context(str(fact.id))

                questions.append(BenchmarkQuestion(
                    question_id=self._qid(f"b_{subtype}"),
                    task=BenchmarkTask.TASK_B_TEMPORAL,
                    subtype=subtype,
                    question=tmpl["q"].format(condition=fact.concept_name),
                    expected_answer=tmpl["a"].format(condition=fact.concept_name),
                    mimic_subject_id=self._mimic_subject_id(fact.patient_id),
                    mimic_hadm_id=int(hadm_id) if hadm_id else None,
                    clinical_context=context_excerpt[:500] if context_excerpt else "",
                    difficulty=QuestionDifficulty.MEDIUM,
                    scoring_rubric={"temporal_correctness": 1.0},
                    metadata={
                        "temporality": temporality,
                        "section": section,
                        "domain": str(fact.domain.value) if fact.domain else "",
                    },
                ))

        except Exception as exc:
            logger.warning("Task B %s generation failed: %s", subtype, exc)
            self._session.rollback()

        return questions

    def _gen_sequence_questions(self, target: int = 40) -> list[BenchmarkQuestion]:
        """Generate sequence questions by finding patients with multiple dated facts."""
        questions: list[BenchmarkQuestion] = []

        try:
            # Find MIMIC patients with multiple conditions
            stmt = (
                select(ClinicalFact.patient_id)
                .where(ClinicalFact.patient_id.like("MIMIC-%"))
                .where(ClinicalFact.domain == "condition")
                .where(ClinicalFact.assertion == "present")
                .where(ClinicalFact.deleted_at.is_(None))
                .group_by(ClinicalFact.patient_id)
                .having(sa_func.count(ClinicalFact.id) >= 4)
            )
            patient_ids = [r[0] for r in self._session.execute(stmt).all()]

            for pid in patient_ids:
                if len(questions) >= target:
                    break

                # Get this patient's conditions with their source documents
                fact_stmt = (
                    select(ClinicalFact.concept_name, ClinicalFact.temporality,
                           Document.created_at, Document.extra_metadata)
                    .join(FactEvidence, FactEvidence.fact_id == ClinicalFact.id)
                    .join(Mention, FactEvidence.source_id == Mention.id)
                    .join(Document, Mention.document_id == Document.id)
                    .where(ClinicalFact.patient_id == pid)
                    .where(ClinicalFact.domain == "condition")
                    .where(ClinicalFact.assertion == "present")
                    .where(ClinicalFact.deleted_at.is_(None))
                    .where(FactEvidence.source_table == "mentions")
                    .order_by(Document.created_at)
                    .distinct()
                )
                rows = list(self._session.execute(fact_stmt).all())

                if len(rows) < 2:
                    continue

                # Group by document (admission)
                admissions: dict[str, list[str]] = {}
                for concept_name, temporality, doc_created, doc_meta in rows:
                    hadm = (doc_meta or {}).get("mimic_hadm_id", "unknown")
                    admissions.setdefault(hadm, []).append(concept_name)

                if len(admissions) < 2:
                    continue

                # Take first two admissions
                adm_list = list(admissions.items())[:2]
                hadm_1, conds_1 = adm_list[0]
                hadm_2, conds_2 = adm_list[1]

                # Find conditions unique to each admission
                set_1 = set(c.lower() for c in conds_1)
                set_2 = set(c.lower() for c in conds_2)
                only_1 = [c for c in conds_1 if c.lower() in (set_1 - set_2)]
                only_2 = [c for c in conds_2 if c.lower() in (set_2 - set_1)]

                if only_1 and only_2:
                    cond_a = self._rng.choice(only_1)
                    cond_b = self._rng.choice(only_2)
                    tmpl = _SEQUENCE_TEMPLATES[len(questions) % len(_SEQUENCE_TEMPLATES)]

                    questions.append(BenchmarkQuestion(
                        question_id=self._qid("b_seq"),
                        task=BenchmarkTask.TASK_B_TEMPORAL,
                        subtype=TemporalType.SEQUENCE.value,
                        question=tmpl["q"].format(condition_a=cond_a, condition_b=cond_b),
                        expected_answer=tmpl["a"].format(
                            first=cond_a, second=cond_b,
                        ),
                        mimic_subject_id=self._mimic_subject_id(pid),
                        clinical_context=f"Admission 1 ({hadm_1}): {', '.join(conds_1[:5])}. Admission 2 ({hadm_2}): {', '.join(conds_2[:5])}.",
                        difficulty=QuestionDifficulty.HARD,
                        scoring_rubric={"temporal_ordering": 1.0},
                        metadata={"hadm_1": hadm_1, "hadm_2": hadm_2},
                    ))

        except Exception as exc:
            logger.warning("Task B sequence generation failed: %s", exc)
            self._session.rollback()

        return questions

    def _gen_duration_questions(self, target: int = 30) -> list[BenchmarkQuestion]:
        """Generate duration questions — conditions present across multiple admissions."""
        questions: list[BenchmarkQuestion] = []

        try:
            # Find conditions present in multiple documents for same patient
            stmt = text("""
                SELECT cf.patient_id, cf.concept_name, COUNT(DISTINCT d.id) as doc_count
                FROM clinical_facts cf
                JOIN fact_evidence fe ON fe.fact_id = cf.id
                JOIN mentions m ON fe.source_id = m.id AND fe.source_table = 'mentions'
                JOIN documents d ON m.document_id = d.id
                WHERE cf.patient_id LIKE 'MIMIC-%%'
                  AND cf.assertion = 'present'
                  AND cf.domain = 'condition'
                  AND cf.deleted_at IS NULL
                GROUP BY cf.patient_id, cf.concept_name
                HAVING COUNT(DISTINCT d.id) >= 2
                LIMIT :limit
            """)
            rows = list(self._session.execute(stmt, {"limit": target * 2}).all())

            for patient_id, concept_name, doc_count in rows:
                if len(questions) >= target:
                    break

                if len(concept_name) < 3:
                    continue

                questions.append(BenchmarkQuestion(
                    question_id=self._qid("b_dur"),
                    task=BenchmarkTask.TASK_B_TEMPORAL,
                    subtype=TemporalType.DURATION.value,
                    question=f"How long has this patient had {concept_name}? Is it a chronic or new condition?",
                    expected_answer=f"{concept_name} appears in {doc_count} separate admissions, indicating it is a chronic/ongoing condition rather than a new finding.",
                    mimic_subject_id=self._mimic_subject_id(patient_id),
                    clinical_context=f"Patient {patient_id}: {concept_name} documented across {doc_count} admissions.",
                    difficulty=QuestionDifficulty.HARD,
                    scoring_rubric={"duration_assessment": 1.0},
                    metadata={"doc_count": doc_count},
                ))

        except Exception as exc:
            logger.warning("Task B duration generation failed: %s", exc)
            self._session.rollback()

        return questions

    def _gen_change_questions(self, target: int = 30) -> list[BenchmarkQuestion]:
        """Generate change questions — medications or conditions that differ between admissions."""
        questions: list[BenchmarkQuestion] = []

        try:
            # Find patients with 2 documents
            pat_stmt = (
                select(Document.patient_id)
                .where(Document.patient_id.like("MIMIC-%"))
                .where(Document.deleted_at.is_(None))
                .group_by(Document.patient_id)
                .having(sa_func.count(Document.id) >= 2)
            )
            patient_ids = [r[0] for r in self._session.execute(pat_stmt).all()]

            for pid in patient_ids:
                if len(questions) >= target:
                    break

                # Get drugs per document
                drug_stmt = text("""
                    SELECT d.metadata->>'mimic_hadm_id' as hadm_id,
                           ARRAY_AGG(DISTINCT cf.concept_name) as drugs
                    FROM clinical_facts cf
                    JOIN fact_evidence fe ON fe.fact_id = cf.id
                    JOIN mentions m ON fe.source_id = m.id AND fe.source_table = 'mentions'
                    JOIN documents d ON m.document_id = d.id
                    WHERE cf.patient_id = :pid
                      AND cf.domain = 'drug'
                      AND cf.assertion = 'present'
                      AND cf.deleted_at IS NULL
                    GROUP BY d.metadata->>'mimic_hadm_id'
                    ORDER BY d.metadata->>'mimic_hadm_id'
                """)
                rows = list(self._session.execute(drug_stmt, {"pid": pid}).all())

                if len(rows) < 2:
                    continue

                hadm_1, drugs_1 = rows[0]
                hadm_2, drugs_2 = rows[1]
                set_1 = set(d.lower() for d in (drugs_1 or []))
                set_2 = set(d.lower() for d in (drugs_2 or []))
                added = set_2 - set_1
                removed = set_1 - set_2

                if not added and not removed:
                    continue

                changes_parts = []
                if added:
                    changes_parts.append(f"new medications: {', '.join(list(added)[:3])}")
                if removed:
                    changes_parts.append(f"discontinued: {', '.join(list(removed)[:3])}")
                changes = "; ".join(changes_parts)

                tmpl = _CHANGE_TEMPLATES[len(questions) % len(_CHANGE_TEMPLATES)]
                questions.append(BenchmarkQuestion(
                    question_id=self._qid("b_chg"),
                    task=BenchmarkTask.TASK_B_TEMPORAL,
                    subtype=TemporalType.CHANGE.value,
                    question=tmpl["q"].format(domain="medication"),
                    expected_answer=tmpl["a"].format(changes=changes),
                    mimic_subject_id=self._mimic_subject_id(pid),
                    clinical_context=f"Admission 1 ({hadm_1}): {', '.join((drugs_1 or [])[:5])}. Admission 2 ({hadm_2}): {', '.join((drugs_2 or [])[:5])}.",
                    difficulty=QuestionDifficulty.HARD,
                    scoring_rubric={"change_detection": 1.0},
                    metadata={"hadm_1": hadm_1, "hadm_2": hadm_2, "added": list(added)[:5], "removed": list(removed)[:5]},
                ))

        except Exception as exc:
            logger.warning("Task B change generation failed: %s", exc)
            self._session.rollback()

        return questions

    # ========================================================================
    # Task C: Calculator-Grounded Decisions (100 questions)
    # ========================================================================

    def generate_task_c(self, count: int = 100) -> BenchmarkQuestionSet:
        """Generate Task C questions requiring clinical calculator computation.

        Finds patients with measurement mentions relevant to each calculator type.
        Distribution target: 20 HEART, 15 Wells, 15 SOFA, 15 CKD-EPI, 10 ASCVD, 10 MELD, 15 other.
        """
        questions: list[BenchmarkQuestion] = []

        calc_targets = {
            CalculatorType.HEART.value: 20,
            CalculatorType.WELLS_PE.value: 15,
            CalculatorType.SOFA.value: 15,
            CalculatorType.CKD_EPI.value: 15,
            CalculatorType.ASCVD.value: 10,
            CalculatorType.MELD.value: 10,
        }

        for calc_type, target_n in calc_targets.items():
            calc_qs = self._gen_calculator_questions(calc_type, min(target_n, count // 6))
            questions.extend(calc_qs)
            logger.info("  Task C %s: %d questions", calc_type, len(calc_qs))

        # Fill remaining with "other" calculator questions (generic measurement questions)
        remaining = count - len(questions)
        if remaining > 0:
            other_qs = self._gen_generic_measurement_questions(remaining)
            questions.extend(other_qs)
            logger.info("  Task C other: %d questions", len(other_qs))

        self._rng.shuffle(questions)
        return BenchmarkQuestionSet(
            task=BenchmarkTask.TASK_C_CALCULATOR,
            questions=questions[:count],
            created_at=datetime.now(timezone.utc),
        )

    def _gen_calculator_questions(
        self, calc_type: str, target: int,
    ) -> list[BenchmarkQuestion]:
        """Generate questions for a specific calculator type."""
        questions: list[BenchmarkQuestion] = []
        template = _CALC_TEMPLATES.get(calc_type)
        if not template:
            return questions

        seen_patients: set[str] = set()

        try:
            # Find patients with relevant measurement mentions
            concepts = template["relevant_concepts"]
            conditions = " OR ".join(
                f"LOWER(m.text) LIKE '%{c}%'" for c in concepts
            )
            stmt = text(f"""
                SELECT DISTINCT d.patient_id,
                       ARRAY_AGG(DISTINCT m.text) as measurements,
                       ARRAY_AGG(DISTINCT m.section) as sections
                FROM mentions m
                JOIN documents d ON m.document_id = d.id
                WHERE d.patient_id LIKE 'MIMIC-%%'
                  AND ({conditions})
                GROUP BY d.patient_id
                HAVING COUNT(DISTINCT m.text) >= 2
                LIMIT :limit
            """)
            rows = list(self._session.execute(stmt, {"limit": target * 3}).all())

            for patient_id, measurements, sections in rows:
                if len(questions) >= target:
                    break
                if patient_id in seen_patients:
                    continue
                seen_patients.add(patient_id)

                details = f"Relevant findings: {', '.join(measurements[:5])}. Sections: {', '.join(set(s for s in sections if s))}."

                questions.append(BenchmarkQuestion(
                    question_id=self._qid(f"c_{calc_type}"),
                    task=BenchmarkTask.TASK_C_CALCULATOR,
                    subtype=calc_type,
                    question=template["question"],
                    expected_answer=template["answer_template"].format(details=details),
                    mimic_subject_id=self._mimic_subject_id(patient_id),
                    clinical_context=details,
                    difficulty=QuestionDifficulty.HARD,
                    scoring_rubric={"calculator_correct": 0.5, "decision_correct": 0.5},
                    metadata={"calculator_type": calc_type, "measurements_found": measurements[:10]},
                ))

        except Exception as exc:
            logger.warning("Task C %s generation failed: %s", calc_type, exc)
            self._session.rollback()

        return questions

    def _gen_generic_measurement_questions(self, target: int) -> list[BenchmarkQuestion]:
        """Generate generic measurement interpretation questions."""
        questions: list[BenchmarkQuestion] = []
        seen: set[tuple[str, str]] = set()

        try:
            stmt = (
                select(ClinicalFact)
                .where(ClinicalFact.patient_id.like("MIMIC-%"))
                .where(ClinicalFact.domain == "measurement")
                .where(ClinicalFact.assertion == "present")
                .where(ClinicalFact.deleted_at.is_(None))
                .order_by(ClinicalFact.confidence.desc())
                .limit(target * 3)
            )
            facts = list(self._session.execute(stmt).scalars().all())

            for fact in facts:
                if len(questions) >= target:
                    break

                key = (fact.patient_id, fact.concept_name.lower())
                if key in seen:
                    continue
                seen.add(key)

                if len(fact.concept_name) < 2:
                    continue

                questions.append(BenchmarkQuestion(
                    question_id=self._qid("c_other"),
                    task=BenchmarkTask.TASK_C_CALCULATOR,
                    subtype=CalculatorType.OTHER.value,
                    question=f"What is this patient's {fact.concept_name} value, and is it within normal range?",
                    expected_answer=f"The patient's {fact.concept_name} should be retrieved from the clinical record and interpreted in clinical context.",
                    mimic_subject_id=self._mimic_subject_id(fact.patient_id),
                    clinical_context=f"Patient {fact.patient_id}, measurement: {fact.concept_name}",
                    difficulty=QuestionDifficulty.MEDIUM,
                    scoring_rubric={"value_correct": 0.5, "interpretation_correct": 0.5},
                ))

        except Exception as exc:
            logger.warning("Task C generic generation failed: %s", exc)
            self._session.rollback()

        return questions

    # ========================================================================
    # Task D: Multi-Source Fusion (100 questions)
    # ========================================================================

    def generate_task_d(self, count: int = 100) -> BenchmarkQuestionSet:
        """Generate Task D questions requiring multi-source data fusion.

        Uses patients with both lab mentions and narrative conditions, and
        patients with multiple admissions for cross-document analysis.

        Distribution target: 30 lab-note, 30 vital-note, 20 temporal_fusion, 20 cross-note.
        Extends with additional section pairings if under target.
        """
        questions: list[BenchmarkQuestion] = []

        # 1. Lab-note fusion (target: 30)
        lab_qs = self._gen_fusion_questions(
            mention_section="Labs",
            subtype=FusionType.LAB_NOTE.value,
            target=30,
        )
        questions.extend(lab_qs)
        logger.info("  Task D lab_note: %d questions", len(lab_qs))

        # 1b. If under target, try Medications as additional lab-note proxy
        if len(lab_qs) < 30:
            extra = self._gen_fusion_questions(
                mention_section="Medications",
                subtype=FusionType.LAB_NOTE.value,
                target=30 - len(lab_qs),
            )
            questions.extend(extra)
            logger.info("  Task D lab_note (medications supplement): %d questions", len(extra))

        # 2. Vital-note fusion (target: 30)
        vital_qs = self._gen_fusion_questions(
            mention_section="Vital Signs",
            subtype=FusionType.VITAL_NOTE.value,
            target=30,
        )
        questions.extend(vital_qs)
        logger.info("  Task D vital_note: %d questions", len(vital_qs))

        # 2b. If under target, try Physical Exam as additional vital-note proxy
        if len(vital_qs) < 30:
            extra = self._gen_fusion_questions(
                mention_section="Physical Exam",
                subtype=FusionType.VITAL_NOTE.value,
                target=30 - len(vital_qs),
            )
            questions.extend(extra)
            logger.info("  Task D vital_note (PE supplement): %d questions", len(extra))

        # 3. Temporal fusion across admissions (target: 20)
        temp_qs = self._gen_temporal_fusion_questions(target=20)
        questions.extend(temp_qs)
        logger.info("  Task D temporal_fusion: %d questions", len(temp_qs))

        # 4. Cross-note discordance (target: 20)
        disc_qs = self._gen_discordance_questions(target=20)
        questions.extend(disc_qs)
        logger.info("  Task D cross_note: %d questions", len(disc_qs))

        self._rng.shuffle(questions)
        return BenchmarkQuestionSet(
            task=BenchmarkTask.TASK_D_FUSION,
            questions=questions[:count],
            created_at=datetime.now(timezone.utc),
        )

    def _gen_fusion_questions(
        self,
        mention_section: str,
        subtype: str,
        target: int,
    ) -> list[BenchmarkQuestion]:
        """Generate fusion questions for a specific section (Labs / Vital Signs)."""
        questions: list[BenchmarkQuestion] = []
        seen_patients: set[str] = set()
        templates = _FUSION_TEMPLATES.get(subtype, [])
        if not templates:
            return questions

        try:
            # Find patients with mentions in both the target section AND Hospital Course
            stmt = text("""
                SELECT d.patient_id,
                       COUNT(DISTINCT CASE WHEN m.section = :target_section THEN m.id END) as target_mentions,
                       COUNT(DISTINCT CASE WHEN m.section = 'Hospital Course' THEN m.id END) as narrative_mentions
                FROM mentions m
                JOIN documents d ON m.document_id = d.id
                WHERE d.patient_id LIKE 'MIMIC-%%'
                GROUP BY d.patient_id
                HAVING COUNT(DISTINCT CASE WHEN m.section = :target_section THEN m.id END) >= 1
                   AND COUNT(DISTINCT CASE WHEN m.section = 'Hospital Course' THEN m.id END) >= 1
                LIMIT :limit
            """)
            rows = list(self._session.execute(
                stmt, {"target_section": mention_section, "limit": target * 2},
            ).all())

            for patient_id, target_count, narrative_count in rows:
                if len(questions) >= target:
                    break
                if patient_id in seen_patients:
                    continue
                seen_patients.add(patient_id)

                template_text = templates[len(questions) % len(templates)]

                questions.append(BenchmarkQuestion(
                    question_id=self._qid(f"d_{subtype}"),
                    task=BenchmarkTask.TASK_D_FUSION,
                    subtype=subtype,
                    question=template_text,
                    expected_answer=f"Multi-source analysis required. Patient has {target_count} {mention_section} mentions and {narrative_count} Hospital Course mentions that need to be compared and integrated.",
                    mimic_subject_id=self._mimic_subject_id(patient_id),
                    clinical_context=f"Patient {patient_id}: {target_count} {mention_section} mentions, {narrative_count} narrative mentions.",
                    difficulty=QuestionDifficulty.HARD,
                    scoring_rubric={"source_integration": 0.5, "accuracy": 0.5},
                    metadata={
                        "sections_compared": [mention_section, "Hospital Course"],
                        "target_mentions": target_count,
                        "narrative_mentions": narrative_count,
                    },
                ))

        except Exception as exc:
            logger.warning("Task D %s generation failed: %s", subtype, exc)
            self._session.rollback()

        return questions

    def _gen_temporal_fusion_questions(self, target: int = 20) -> list[BenchmarkQuestion]:
        """Generate temporal fusion questions using patients with 2 admissions."""
        questions: list[BenchmarkQuestion] = []
        templates = _FUSION_TEMPLATES.get(FusionType.TEMPORAL_FUSION.value, [])

        try:
            stmt = (
                select(Document.patient_id, sa_func.count(Document.id))
                .where(Document.patient_id.like("MIMIC-%"))
                .where(Document.deleted_at.is_(None))
                .group_by(Document.patient_id)
                .having(sa_func.count(Document.id) >= 2)
                .limit(target)
            )
            rows = list(self._session.execute(stmt).all())

            for patient_id, doc_count in rows:
                if len(questions) >= target:
                    break

                tmpl = templates[len(questions) % len(templates)] if templates else ""
                if not tmpl:
                    continue

                questions.append(BenchmarkQuestion(
                    question_id=self._qid("d_temporal"),
                    task=BenchmarkTask.TASK_D_FUSION,
                    subtype=FusionType.TEMPORAL_FUSION.value,
                    question=tmpl,
                    expected_answer=f"Temporal fusion required across {doc_count} admissions. Compare diagnoses, medications, and clinical trajectory.",
                    mimic_subject_id=self._mimic_subject_id(patient_id),
                    clinical_context=f"Patient {patient_id}: {doc_count} admission documents.",
                    difficulty=QuestionDifficulty.HARD,
                    scoring_rubric={"temporal_integration": 0.6, "accuracy": 0.4},
                ))

        except Exception as exc:
            logger.warning("Task D temporal_fusion generation failed: %s", exc)
            self._session.rollback()

        return questions

    def _gen_discordance_questions(self, target: int = 20) -> list[BenchmarkQuestion]:
        """Generate cross-note discordance questions."""
        questions: list[BenchmarkQuestion] = []
        templates = _FUSION_TEMPLATES.get(FusionType.CROSS_NOTE_DISCORDANCE.value, [])

        try:
            # Find patients with conditions that have different assertions across documents
            stmt = text("""
                SELECT cf.patient_id, cf.concept_name,
                       ARRAY_AGG(DISTINCT cf.assertion) as assertions,
                       COUNT(DISTINCT d.id) as doc_count
                FROM clinical_facts cf
                JOIN fact_evidence fe ON fe.fact_id = cf.id
                JOIN mentions m ON fe.source_id = m.id AND fe.source_table = 'mentions'
                JOIN documents d ON m.document_id = d.id
                WHERE cf.patient_id LIKE 'MIMIC-%%'
                  AND cf.domain = 'condition'
                  AND cf.deleted_at IS NULL
                GROUP BY cf.patient_id, cf.concept_name
                HAVING COUNT(DISTINCT d.id) >= 2
                LIMIT :limit
            """)
            rows = list(self._session.execute(stmt, {"limit": target * 3}).all())

            seen: set[tuple[str, str]] = set()
            for patient_id, concept_name, assertions, doc_count in rows:
                if len(questions) >= target:
                    break
                key = (patient_id, concept_name.lower())
                if key in seen:
                    continue
                seen.add(key)

                tmpl = templates[len(questions) % len(templates)] if templates else ""
                if not tmpl:
                    continue

                assertion_list = list(assertions) if assertions else []

                questions.append(BenchmarkQuestion(
                    question_id=self._qid("d_disc"),
                    task=BenchmarkTask.TASK_D_FUSION,
                    subtype=FusionType.CROSS_NOTE_DISCORDANCE.value,
                    question=tmpl,
                    expected_answer=f"Discordance detected for {concept_name}: assertions vary ({', '.join(assertion_list)}) across {doc_count} documents. The system should identify and explain this discrepancy.",
                    mimic_subject_id=self._mimic_subject_id(patient_id),
                    clinical_context=f"Patient {patient_id}: {concept_name} has varying assertions ({', '.join(assertion_list)}) across {doc_count} documents.",
                    difficulty=QuestionDifficulty.HARD,
                    scoring_rubric={"discordance_detection": 0.5, "explanation": 0.5},
                    metadata={"discordant_concept": concept_name, "assertions": assertion_list},
                ))

        except Exception as exc:
            logger.warning("Task D discordance generation failed: %s", exc)
            self._session.rollback()

        return questions

    # ========================================================================
    # Export
    # ========================================================================

    def export_to_json(
        self,
        question_sets: dict[str, BenchmarkQuestionSet],
        output_dir: str = "data/benchmarks",
    ) -> list[str]:
        """Export generated question sets to JSON files.

        Returns list of file paths written.
        """
        import os

        os.makedirs(output_dir, exist_ok=True)
        paths = []

        for name, qs in question_sets.items():
            path = os.path.join(output_dir, f"{name}.json")
            with open(path, "w") as f:
                json.dump(qs.model_dump(mode="json"), f, indent=2, default=str)
            paths.append(path)
            logger.info("Exported %d questions to %s", qs.total_count, path)

        return paths
