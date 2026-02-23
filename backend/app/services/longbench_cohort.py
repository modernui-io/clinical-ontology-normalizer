"""Longitudinal Clinical Benchmark — cohort selection + question generation.

Selects MIMIC-IV patients stratified by encounter count (longitudinal depth)
and generates HealthBench-style questions with rubric criteria.

Usage:
    selector = LongBenchCohortSelector(session)
    cohort = selector.select_cohort(
        tier_sizes={"A": 20, "B": 20, "C": 20},
        min_note_chars=500,
    )
    generator = LongBenchQuestionGenerator()
    cohort = await generator.generate_questions(cohort, questions_per_patient=5)
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
from datetime import datetime
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models.clinical_fact import ClinicalFact
from app.models.document import Document
from app.models.knowledge_graph import KGEdge, KGNode
from app.services.llm_service import LLMConfig, LLMProvider, get_llm_service
from app.services.longbench_schemas import (
    CriterionType,
    CriterionWeight,
    LongBenchCohort,
    LongBenchCriterion,
    LongBenchQuestion,
    LongitudinalTier,
    PatientCohortEntry,
    QuestionDomain,
    QuestionSlice,
    ExpectedMechanism,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Tier boundaries
# ============================================================================

TIER_BOUNDS: dict[LongitudinalTier, tuple[int, int]] = {
    LongitudinalTier.A: (1, 2),
    LongitudinalTier.B: (5, 10),
    LongitudinalTier.C: (15, 999),
}


# ============================================================================
# Cohort Selector
# ============================================================================


class LongBenchCohortSelector:
    """Selects patients from the database stratified by encounter count."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def select_cohort(
        self,
        tier_sizes: dict[str, int] | None = None,
        min_note_chars: int = 500,
        random_seed: int = 42,
    ) -> LongBenchCohort:
        """Select patients stratified by longitudinal depth.

        Args:
            tier_sizes: Number of patients per tier. Defaults to 20 each.
            min_note_chars: Minimum total note text length to qualify.
            random_seed: For reproducible patient selection.

        Returns:
            LongBenchCohort with selected patients (no questions yet).
        """
        if tier_sizes is None:
            tier_sizes = {"A": 20, "B": 20, "C": 20}

        rng = random.Random(random_seed)
        patients: list[PatientCohortEntry] = []

        for tier in LongitudinalTier:
            size = tier_sizes.get(tier.value, 20)
            lo, hi = TIER_BOUNDS[tier]
            candidates = self._find_candidates(lo, hi, min_note_chars)

            # Shuffle and take requested size
            rng.shuffle(candidates)
            selected = candidates[:size]

            if len(selected) < size:
                logger.warning(
                    "Tier %s: only %d patients available (requested %d)",
                    tier.value, len(selected), size,
                )

            for entry in selected:
                entry.tier = tier
                patients.append(entry)

        cohort_id = f"longbench_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        return LongBenchCohort(
            cohort_id=cohort_id,
            patients=patients,
            version="1.0.0",
            metadata={
                "tier_sizes": tier_sizes,
                "min_note_chars": min_note_chars,
                "random_seed": random_seed,
                "selection_date": datetime.utcnow().isoformat(),
            },
        )

    def _find_candidates(
        self,
        min_encounters: int,
        max_encounters: int,
        min_note_chars: int,
    ) -> list[PatientCohortEntry]:
        """Query DB for patients in the given encounter-count range."""
        # Subquery: count documents per patient
        doc_stats = (
            select(
                Document.patient_id,
                func.count(Document.id).label("doc_count"),
                func.sum(func.length(Document.text)).label("total_chars"),
                func.min(Document.note_date).label("earliest"),
                func.max(Document.note_date).label("latest"),
            )
            .where(Document.text.isnot(None))
            .group_by(Document.patient_id)
            .having(func.count(Document.id) >= min_encounters)
            .having(func.count(Document.id) <= max_encounters)
            .having(func.sum(func.length(Document.text)) >= min_note_chars)
            .subquery()
        )

        rows = self._session.execute(
            select(doc_stats)
        ).fetchall()

        candidates: list[PatientCohortEntry] = []
        for row in rows:
            pid = row.patient_id
            # Enrich with clinical fact counts
            fact_counts = self._get_fact_counts(pid)
            candidates.append(PatientCohortEntry(
                patient_id=pid,
                tier=LongitudinalTier.A,  # Will be overwritten
                encounter_count=row.doc_count,
                total_note_length=row.total_chars or 0,
                earliest_date=str(row.earliest) if row.earliest else "",
                latest_date=str(row.latest) if row.latest else "",
                condition_count=fact_counts.get("condition", 0),
                medication_count=fact_counts.get("medication", 0),
                has_family_history=fact_counts.get("family", 0) > 0,
            ))

        return candidates

    def _get_fact_counts(self, patient_id: str) -> dict[str, int]:
        """Get clinical fact counts by domain for a patient."""
        try:
            stmt = (
                select(
                    ClinicalFact.domain,
                    func.count(ClinicalFact.id),
                )
                .where(ClinicalFact.patient_id == patient_id)
                .group_by(ClinicalFact.domain)
            )
            rows = self._session.execute(stmt).fetchall()
            counts: dict[str, int] = {}
            for domain, count in rows:
                d = str(domain).lower() if domain else "unknown"
                counts[d] = count
                if "family" in d:
                    counts["family"] = counts.get("family", 0) + count
            return counts
        except Exception:
            return {}

    def get_patient_notes(
        self,
        patient_id: str,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get all clinical notes for a patient, ordered by date."""
        stmt = (
            select(Document)
            .where(Document.patient_id == patient_id)
            .where(Document.text.isnot(None))
            .order_by(Document.note_date.asc().nullslast())
        )
        if limit:
            stmt = stmt.limit(limit)
        docs = list(self._session.execute(stmt).scalars().all())
        return [
            {
                "doc_id": str(d.id),
                "note_type": d.note_type,
                "note_date": str(d.note_date) if d.note_date else None,
                "text": d.text[:5000],  # Truncate for LLM context
                "char_count": len(d.text) if d.text else 0,
            }
            for d in docs
        ]

    def get_patient_kg_summary(self, patient_id: str) -> dict[str, Any]:
        """Get a summary of the patient's knowledge graph."""
        try:
            node_count = self._session.execute(
                select(func.count(KGNode.id))
                .where(KGNode.patient_id == patient_id)
            ).scalar() or 0

            edge_count = self._session.execute(
                select(func.count(KGEdge.id))
                .where(KGEdge.patient_id == patient_id)
            ).scalar() or 0

            # Count family-history edges specifically
            family_edges = self._session.execute(
                select(func.count(KGEdge.id))
                .where(KGEdge.patient_id == patient_id)
                .where(
                    (KGEdge.experiencer == "family")
                    | (KGEdge.assertion == "family_history")
                )
            ).scalar() or 0

            return {
                "node_count": node_count,
                "edge_count": edge_count,
                "family_history_edges": family_edges,
            }
        except Exception:
            return {"node_count": 0, "edge_count": 0, "family_history_edges": 0}


# ============================================================================
# Question Generator
# ============================================================================

# Template questions by domain — used as seeds for LLM generation
QUESTION_TEMPLATES: dict[QuestionDomain, list[str]] = {
    QuestionDomain.MEDICATION_RECONCILIATION: [
        "What medications is this patient currently taking with dosages, what medications were changed during their care, and what were the documented reasons for each change?",
        "Has this patient's medication regimen changed over time? For each change, cite the encounter and reason.",
        "Are there any medications that were started and then discontinued? Cite specific encounters and reasons.",
    ],
    QuestionDomain.PROBLEM_LIST: [
        "Summarize this patient's active medical conditions and their current status.",
        "Which conditions have been resolved and which remain active?",
        "What are the most clinically significant findings across all encounters?",
    ],
    QuestionDomain.FAMILY_HISTORY: [
        "What family history is documented for this patient, and how does it relate to their risk profile?",
        "Are there any conditions documented that belong to family members rather than the patient?",
        "What hereditary risk factors should be considered based on the family history?",
    ],
    QuestionDomain.TEMPORAL_REASONING: [
        "Create a detailed timeline of this patient's clinical events across all encounters, citing specific dates and noting any changes in diagnosis status or treatment.",
        "What is the chronological sequence of major clinical events with specific encounter dates?",
        "Which conditions changed status (uncertain to confirmed, active to resolved) across encounters, and when did each change occur?",
    ],
    QuestionDomain.RISK_ASSESSMENT: [
        "What are the key risk factors for this patient based on all available data?",
        "Are there any unaddressed risk factors that should be monitored?",
        "What preventive measures would be appropriate given this patient's history?",
    ],
}


QUESTION_GENERATION_PROMPT = """\
You are a clinical QA benchmark designer. Given a patient's clinical notes and \
knowledge graph summary, generate exactly {n_questions} clinical questions that \
test whether a system can accurately reason about this patient.

PATIENT NOTES (chronological):
{notes_text}

KNOWLEDGE GRAPH SUMMARY:
- Nodes: {kg_nodes}, Edges: {kg_edges}, Family history edges: {family_edges}
- Encounter count: {encounter_count}, Tier: {tier}

QUESTION DOMAINS TO COVER (generate at least 1 per domain):
{domains}

For EACH question, output a JSON object with:
{{
  "question_text": "...",
  "domain": "medication_reconciliation|problem_list|family_history|temporal_reasoning|risk_assessment",
  "criteria": [
    {{
      "text": "Descriptive rubric criterion that can be scored as true/false",
      "criterion_type": "chronology|causal|medication|experiencer|assertion|uncertainty|synthesis|risk",
      "weight": "critical|important|nice",
      "evidence_source": "Which encounter/note supports this"
    }}
  ]
}}

RULES:
1. Each question MUST have 3-7 criteria
2. At least 1 criterion must be "critical" weight
3. For family_history questions: include at least 1 "experiencer" criterion that checks \
   whether the system correctly attributes findings to family vs patient
4. For temporal_reasoning questions: include at least 1 "chronology" criterion
5. Criteria must be derivable from the provided notes (no external knowledge)
6. Make questions progressively harder — some should require multi-note synthesis

Output a JSON array of question objects. No markdown, no explanation — just the JSON array.
"""


# Slice-based micro-benchmark templates designed for clinician-style chart review.
# The questions are intentionally phrased as real clinical questions; graph concepts
# are only used in internal analysis annotations.
SLICE_QUESTION_TEMPLATES: list[dict[str, Any]] = [
    # A: Temporal reconciliation
    {
        "id": "A1",
        "slice_id": QuestionSlice.A_TEMPORAL,
        "expected_mechanism": ExpectedMechanism.SINGLE_NOTE,
        "domain": QuestionDomain.MEDICATION_RECONCILIATION,
        "question_text": (
            "What medications was this patient prescribed at their most recent discharge, "
            "and at what dosages?"
        ),
        "kg_edge_types_needed": ["takes_drug"],
    },
    {
        "id": "A2",
        "slice_id": QuestionSlice.A_TEMPORAL,
        "expected_mechanism": ExpectedMechanism.CROSS_ENCOUNTER,
        "domain": QuestionDomain.TEMPORAL_REASONING,
        "question_text": (
            "How did this patient's medication regimen change between their first and most "
            "recent encounters? For each change, identify when it occurred and what prompted it."
        ),
        "kg_edge_types_needed": ["takes_drug", "condition_treated_by", "precedes", "occurred_on"],
    },
    {
        "id": "A3",
        "slice_id": QuestionSlice.A_TEMPORAL,
        "expected_mechanism": ExpectedMechanism.CROSS_ENCOUNTER,
        "domain": QuestionDomain.TEMPORAL_REASONING,
        "question_text": (
            "Which diagnoses changed status over the course of care — suspected to confirmed, "
            "or active to resolved? Cite the encounters where each change is documented."
        ),
        "kg_edge_types_needed": ["has_condition", "precedes", "occurred_on"],
    },
    {
        "id": "A4",
        "slice_id": QuestionSlice.A_TEMPORAL,
        "expected_mechanism": ExpectedMechanism.SINGLE_NOTE,
        "domain": QuestionDomain.TEMPORAL_REASONING,
        "question_text": (
            "What were the key clinical events during this patient's most recent "
            "hospitalization, in chronological order?"
        ),
        "kg_edge_types_needed": ["precedes", "follows"],
    },
    # B: Assertion and attribution
    {
        "id": "B1",
        "slice_id": QuestionSlice.B_ASSERTION,
        "expected_mechanism": ExpectedMechanism.ASSERTION_REASONING,
        "domain": QuestionDomain.PROBLEM_LIST,
        "question_text": (
            "Were any diagnoses considered but ultimately ruled out? Which ones, and what "
            "evidence led to their exclusion?"
        ),
        "kg_edge_types_needed": ["has_condition"],
    },
    {
        "id": "B2",
        "slice_id": QuestionSlice.B_ASSERTION,
        "expected_mechanism": ExpectedMechanism.ASSERTION_REASONING,
        "domain": QuestionDomain.FAMILY_HISTORY,
        "question_text": (
            "What conditions are documented in family history, and are any also present "
            "in the patient? Be precise about which belong to relatives."
        ),
        "kg_edge_types_needed": ["has_condition"],
    },
    {
        "id": "B3",
        "slice_id": QuestionSlice.B_ASSERTION,
        "expected_mechanism": ExpectedMechanism.SINGLE_NOTE,
        "domain": QuestionDomain.PROBLEM_LIST,
        "question_text": (
            "What are this patient's currently active medical problems as documented in "
            "their most recent encounter?"
        ),
        "kg_edge_types_needed": ["has_condition"],
    },
    {
        "id": "B4",
        "slice_id": QuestionSlice.B_ASSERTION,
        "expected_mechanism": ExpectedMechanism.ASSERTION_REASONING,
        "domain": QuestionDomain.PROBLEM_LIST,
        "question_text": (
            "Which conditions are currently active versus historical or resolved? For resolved ones, "
            "indicate when resolution was documented."
        ),
        "kg_edge_types_needed": ["has_condition"],
    },
    # C: Causal chains
    {
        "id": "C1",
        "slice_id": QuestionSlice.C_CAUSAL,
        "expected_mechanism": ExpectedMechanism.CAUSAL_CHAIN,
        "domain": QuestionDomain.TEMPORAL_REASONING,
        "question_text": (
            "What clinical finding prompted the most significant treatment change? "
            "Describe the chain from triggering finding to treatment decision."
        ),
        "kg_edge_types_needed": ["caused_by", "resulted_in", "condition_treated_by"],
    },
    {
        "id": "C2",
        "slice_id": QuestionSlice.C_CAUSAL,
        "expected_mechanism": ExpectedMechanism.CAUSAL_CHAIN,
        "domain": QuestionDomain.TEMPORAL_REASONING,
        "question_text": (
            "Did this patient experience any adverse effects from treatment? Trace: what treatment, "
            "what complication, and how was it managed?"
        ),
        "kg_edge_types_needed": ["may_cause", "resulted_in", "condition_treated_by"],
    },
    {
        "id": "C3",
        "slice_id": QuestionSlice.C_CAUSAL,
        "expected_mechanism": ExpectedMechanism.SINGLE_NOTE,
        "domain": QuestionDomain.PROBLEM_LIST,
        "question_text": (
            "What was the primary reason for admission, and what was the principal diagnosis at discharge?"
        ),
        "kg_edge_types_needed": ["has_condition"],
    },
    # D: Safety and monitoring
    {
        "id": "D1",
        "slice_id": QuestionSlice.D_SAFETY,
        "expected_mechanism": ExpectedMechanism.SAFETY_CHECK,
        "domain": QuestionDomain.MEDICATION_RECONCILIATION,
        "question_text": (
            "Given the complete medication list across all encounters, are there any drug-drug "
            "interactions or contraindications that should be flagged?"
        ),
        "kg_edge_types_needed": ["takes_drug", "drug_interaction", "contraindicated_with"],
    },
    {
        "id": "D2",
        "slice_id": QuestionSlice.D_SAFETY,
        "expected_mechanism": ExpectedMechanism.SAFETY_CHECK,
        "domain": QuestionDomain.RISK_ASSESSMENT,
        "question_text": (
            "Are any current medications potentially inappropriate given documented conditions or "
            "recent labs? Explain the clinical concern."
        ),
        "kg_edge_types_needed": ["takes_drug", "has_condition", "contraindicated_with", "has_measurement"],
    },
    {
        "id": "D3",
        "slice_id": QuestionSlice.D_SAFETY,
        "expected_mechanism": ExpectedMechanism.SINGLE_NOTE,
        "domain": QuestionDomain.FAMILY_HISTORY,
        "question_text": (
            "Does this patient have documented medication allergies, and are any current medications "
            "in the same drug class?"
        ),
        "kg_edge_types_needed": ["has_observation", "takes_drug"],
    },
    # E: Guideline triggers
    {
        "id": "E1",
        "slice_id": QuestionSlice.E_GUIDELINE,
        "expected_mechanism": ExpectedMechanism.GUIDELINE_TRIGGER,
        "domain": QuestionDomain.RISK_ASSESSMENT,
        "question_text": (
            "Based on risk factors, comorbidities, and lab values, does this patient meet criteria for "
            "statin therapy? Cite the specific data points."
        ),
        "kg_edge_types_needed": ["has_condition", "has_measurement", "takes_drug"],
    },
    {
        "id": "E2",
        "slice_id": QuestionSlice.E_GUIDELINE,
        "expected_mechanism": ExpectedMechanism.GUIDELINE_TRIGGER,
        "domain": QuestionDomain.MEDICATION_RECONCILIATION,
        "question_text": (
            "Given the current medication list, are any monitoring labs or follow-up assessments "
            "overdue or missing?"
        ),
        "kg_edge_types_needed": ["takes_drug", "monitors", "has_measurement", "occurred_on"],
    },
    {
        "id": "E3",
        "slice_id": QuestionSlice.E_GUIDELINE,
        "expected_mechanism": ExpectedMechanism.SINGLE_NOTE,
        "domain": QuestionDomain.RISK_ASSESSMENT,
        "question_text": (
            "What modifiable risk factors are documented that could be addressed through "
            "lifestyle changes or preventive treatment?"
        ),
        "kg_edge_types_needed": ["has_condition", "has_observation"],
    },
    {
        "id": "E4",
        "slice_id": QuestionSlice.E_GUIDELINE,
        "expected_mechanism": ExpectedMechanism.CROSS_ENCOUNTER,
        "domain": QuestionDomain.TEMPORAL_REASONING,
        "question_text": (
            "Looking at lab trends over time, are any values trending in a clinically concerning direction? "
            "Cite specific values and dates."
        ),
        "kg_edge_types_needed": ["has_measurement", "monitors", "occurred_on"],
    },
    # F: Hard longitudinal questions requiring cross-encounter synthesis
    {
        "id": "F1",
        "slice_id": QuestionSlice.A_TEMPORAL,
        "expected_mechanism": ExpectedMechanism.CROSS_ENCOUNTER,
        "domain": QuestionDomain.MEDICATION_RECONCILIATION,
        "question_text": (
            "This patient has records spanning multiple years. Reconstruct the complete medication "
            "timeline: for each medication started, changed, or stopped, identify the encounter date "
            "and the documented reason for the change."
        ),
        "kg_edge_types_needed": ["takes_drug", "condition_treated_by", "precedes", "occurred_on"],
    },
    {
        "id": "F2",
        "slice_id": QuestionSlice.B_ASSERTION,
        "expected_mechanism": ExpectedMechanism.ASSERTION_REASONING,
        "domain": QuestionDomain.PROBLEM_LIST,
        "question_text": (
            "Multiple notes contain different problem lists. Reconcile any contradictions: which "
            "conditions appear in some notes but not others, and what is the most current accurate "
            "problem list?"
        ),
        "kg_edge_types_needed": ["has_condition", "precedes", "occurred_on"],
    },
    {
        "id": "F3",
        "slice_id": QuestionSlice.C_CAUSAL,
        "expected_mechanism": ExpectedMechanism.CAUSAL_CHAIN,
        "domain": QuestionDomain.TEMPORAL_REASONING,
        "question_text": (
            "Trace the longest causal chain you can identify: starting from an initial clinical "
            "finding, follow each subsequent diagnosis, treatment, complication, and intervention "
            "that followed from it."
        ),
        "kg_edge_types_needed": ["caused_by", "resulted_in", "condition_treated_by", "may_cause"],
    },
    {
        "id": "F4",
        "slice_id": QuestionSlice.A_TEMPORAL,
        "expected_mechanism": ExpectedMechanism.CROSS_ENCOUNTER,
        "domain": QuestionDomain.TEMPORAL_REASONING,
        "question_text": (
            "Compare the earliest and most recent encounters. What clinically significant changes "
            "occurred between them? For each change, identify the encounter where it was first "
            "documented."
        ),
        "kg_edge_types_needed": ["has_condition", "takes_drug", "precedes", "occurred_on"],
    },
    {
        "id": "F5",
        "slice_id": QuestionSlice.D_SAFETY,
        "expected_mechanism": ExpectedMechanism.SAFETY_CHECK,
        "domain": QuestionDomain.MEDICATION_RECONCILIATION,
        "question_text": (
            "Considering the complete medication history across all encounters, identify any period "
            "where the patient was on medications that interact with each other. When were they "
            "co-prescribed, and was the interaction addressed?"
        ),
        "kg_edge_types_needed": ["takes_drug", "drug_interaction", "occurred_on", "precedes"],
    },
    {
        "id": "F6",
        "slice_id": QuestionSlice.E_GUIDELINE,
        "expected_mechanism": ExpectedMechanism.GUIDELINE_TRIGGER,
        "domain": QuestionDomain.RISK_ASSESSMENT,
        "question_text": (
            "Based on the full clinical trajectory, were there any points where standard-of-care "
            "guidelines suggest an intervention that doesn't appear in the record? Cite the specific "
            "data supporting your assessment."
        ),
        "kg_edge_types_needed": ["has_condition", "has_measurement", "takes_drug", "monitors"],
    },
]


class LongBenchQuestionGenerator:
    """Generates HealthBench-style questions for each patient in the cohort."""

    def __init__(
        self,
        llm_model: str = "claude-sonnet-4-5-20250929",
        llm_provider: str = "anthropic",
    ) -> None:
        self.llm_config = LLMConfig(
            provider=LLMProvider(llm_provider),
            model=llm_model,
            max_tokens=4096,
            temperature=0.3,  # Some creativity for diverse questions
        )

    async def generate_questions(
        self,
        cohort: LongBenchCohort,
        session: Session,
        questions_per_patient: int = 5,
    ) -> LongBenchCohort:
        """Generate questions for all patients in the cohort.

        Args:
            cohort: Cohort with patients selected (no questions yet).
            session: DB session for fetching patient data.
            questions_per_patient: Target number of questions per patient.

        Returns:
            Updated cohort with questions populated.
        """
        selector = LongBenchCohortSelector(session)
        llm = get_llm_service(self.llm_config)

        for patient in cohort.patients:
            logger.info(
                "Generating %d questions for patient %s (tier=%s, encounters=%d)",
                questions_per_patient, patient.patient_id,
                patient.tier.value, patient.encounter_count,
            )

            notes = selector.get_patient_notes(patient.patient_id)
            kg_summary = selector.get_patient_kg_summary(patient.patient_id)

            questions = await self._generate_for_patient(
                patient=patient,
                notes=notes,
                kg_summary=kg_summary,
                n_questions=questions_per_patient,
                llm=llm,
            )
            cohort.questions.extend(questions)

        logger.info(
            "Generated %d total questions for %d patients",
            len(cohort.questions), len(cohort.patients),
        )
        return cohort

    async def _generate_for_patient(
        self,
        patient: PatientCohortEntry,
        notes: list[dict],
        kg_summary: dict,
        n_questions: int,
        llm: Any,
    ) -> list[LongBenchQuestion]:
        """Generate questions for a single patient using LLM."""
        # Format notes for prompt
        notes_text = "\n\n---\n\n".join(
            f"[{n.get('note_type', 'note')} | {n.get('note_date', 'undated')}]\n{n['text']}"
            for n in notes
        )

        domains = "\n".join(
            f"- {d.value}: {QUESTION_TEMPLATES[d][0]}"
            for d in QuestionDomain
        )

        prompt = QUESTION_GENERATION_PROMPT.format(
            n_questions=n_questions,
            notes_text=notes_text[:12000],  # Cap context
            kg_nodes=kg_summary.get("node_count", 0),
            kg_edges=kg_summary.get("edge_count", 0),
            family_edges=kg_summary.get("family_history_edges", 0),
            encounter_count=patient.encounter_count,
            tier=patient.tier.value,
            domains=domains,
        )

        try:
            response = await llm.generate(
                prompt=prompt,
                system_prompt="You are a clinical QA benchmark designer. Output valid JSON only.",
            )
            raw = response.content.strip()
            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            question_data = json.loads(raw)
            if not isinstance(question_data, list):
                question_data = [question_data]

            return [
                self._parse_question(q, patient, idx)
                for idx, q in enumerate(question_data)
            ]
        except Exception as exc:
            logger.warning(
                "Question generation failed for %s: %s — using templates",
                patient.patient_id, exc,
            )
            return self._fallback_template_questions(patient, n_questions)

    def _parse_question(
        self,
        data: dict,
        patient: PatientCohortEntry,
        idx: int,
    ) -> LongBenchQuestion:
        """Parse an LLM-generated question dict into LongBenchQuestion."""
        qid_hash = hashlib.md5(
            f"{patient.patient_id}_{idx}_{data.get('question_text', '')}".encode()
        ).hexdigest()[:8]

        question_id = f"lb_{patient.tier.value}_{qid_hash}"

        criteria = []
        for ci, c in enumerate(data.get("criteria", [])):
            crit_type = c.get("criterion_type", "synthesis")
            try:
                ct = CriterionType(crit_type)
            except ValueError:
                ct = CriterionType.SYNTHESIS

            weight_str = c.get("weight", "important")
            try:
                cw = CriterionWeight(weight_str)
            except ValueError:
                cw = CriterionWeight.IMPORTANT

            criteria.append(LongBenchCriterion(
                criterion_id=f"{question_id}_c{ci}",
                text=c.get("text", ""),
                criterion_type=ct,
                weight=cw,
                evidence_source=c.get("evidence_source", ""),
            ))

        domain_str = data.get("domain", "problem_list")
        try:
            domain = QuestionDomain(domain_str)
        except ValueError:
            domain = QuestionDomain.PROBLEM_LIST

        return LongBenchQuestion(
            question_id=question_id,
            patient_id=patient.patient_id,
            question_text=data.get("question_text", ""),
            domain=domain,
            tier=patient.tier,
            criteria=criteria,
            encounter_count=patient.encounter_count,
            generated_by="llm",
            slice_id=_optional_slice_id(data.get("slice_id")),
            expected_mechanism=_optional_expected_mechanism(data.get("expected_mechanism")),
            kg_edge_types_needed=_normalize_edge_types(
                data.get("kg_edge_types_needed"),
            ),
        )

    def _fallback_template_questions(
        self,
        patient: PatientCohortEntry,
        n: int,
    ) -> list[LongBenchQuestion]:
        """Generate template-based questions as fallback.

        Criteria are designed to be evaluable across ALL conditions (B0-B3).
        Each question gets domain-specific criteria that test reasoning
        quality regardless of whether patient data was provided.
        """
        questions: list[LongBenchQuestion] = []
        domains = list(QuestionDomain)
        for i in range(min(n, len(domains))):
            domain = domains[i]
            template = QUESTION_TEMPLATES[domain][0]
            qid = f"lb_{patient.tier.value}_tmpl_{i}"
            criteria = _DOMAIN_CRITERIA_TEMPLATES[domain](qid)
            questions.append(LongBenchQuestion(
                question_id=qid,
                patient_id=patient.patient_id,
                question_text=template,
                domain=domain,
                tier=patient.tier,
                criteria=criteria,
                encounter_count=patient.encounter_count,
                generated_by="template",
            ))
        return questions


class SliceBenchQuestionGenerator:
    """Generate the clinical reasoning micro-benchmark question set."""

    def generate(self, patient: PatientCohortEntry) -> list[LongBenchQuestion]:
        """Generate all 18 slice-specific questions for a patient."""
        pid_hash = hashlib.md5(patient.patient_id.encode("utf-8")).hexdigest()[:8]
        questions: list[LongBenchQuestion] = []

        for spec in SLICE_QUESTION_TEMPLATES:
            qid = f"lb_{patient.tier.value}_{spec['id']}_{pid_hash}"
            criterion_builder = _SLICE_CRITERIA_TEMPLATES[spec["id"]]
            questions.append(LongBenchQuestion(
                question_id=qid,
                patient_id=patient.patient_id,
                question_text=spec["question_text"],
                domain=spec["domain"],
                tier=patient.tier,
                criteria=criterion_builder(qid),
                encounter_count=patient.encounter_count,
                generated_by="slice_template",
                slice_id=spec["slice_id"],
                expected_mechanism=spec["expected_mechanism"],
                kg_edge_types_needed=list(spec["kg_edge_types_needed"]),
            ))

        return questions


def _optional_slice_id(value: str | None) -> QuestionSlice | None:
    if isinstance(value, str):
        try:
            return QuestionSlice(value)
        except ValueError:
            return None
    return None


def _optional_expected_mechanism(value: str | None) -> ExpectedMechanism | None:
    if isinstance(value, str):
        try:
            return ExpectedMechanism(value)
        except ValueError:
            return None
    return None


def _normalize_edge_types(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(v) for v in value if isinstance(v, str)]


# Domain-specific criteria templates.  Each question gets 3-5 criteria
# spanning multiple CriterionTypes and weights.  Criteria are written to be
# evaluable for ALL conditions — including B0 (no patient data) where the LLM
# should get credit for sound clinical reasoning and appropriate uncertainty.

def _medication_criteria(qid: str) -> list[LongBenchCriterion]:
    return [
        LongBenchCriterion(
            criterion_id=f"{qid}_c0",
            text="Identifies specific medications WITH dosages from the clinical record",
            criterion_type=CriterionType.MEDICATION,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c1",
            text="Does not fabricate medications, dosages, or medication changes not documented in the record",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c2",
            text="Identifies potential drug interactions or contraindications based on the ACTUAL medication list",
            criterion_type=CriterionType.CAUSAL,
            weight=CriterionWeight.IMPORTANT,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c3",
            text="Distinguishes current medications from discontinued ones with approximate dates or encounter references for changes",
            criterion_type=CriterionType.CHRONOLOGY,
            weight=CriterionWeight.IMPORTANT,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c4",
            text="Correctly attributes medication changes to specific encounters or clinical events that triggered the change",
            criterion_type=CriterionType.CHRONOLOGY,
            weight=CriterionWeight.IMPORTANT,
        ),
    ]


def _problem_list_criteria(qid: str) -> list[LongBenchCriterion]:
    return [
        LongBenchCriterion(
            criterion_id=f"{qid}_c0",
            text="Lists specific active medical conditions documented in the clinical record",
            criterion_type=CriterionType.SYNTHESIS,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c1",
            text="Does not fabricate conditions or diagnoses not documented in the record",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c2",
            text="References specific clinical data (labs, vitals, imaging) that support each condition",
            criterion_type=CriterionType.SYNTHESIS,
            weight=CriterionWeight.IMPORTANT,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c3",
            text="Distinguishes active conditions from resolved or historical ones",
            criterion_type=CriterionType.CHRONOLOGY,
            weight=CriterionWeight.IMPORTANT,
        ),
    ]


def _family_history_criteria(qid: str) -> list[LongBenchCriterion]:
    return [
        LongBenchCriterion(
            criterion_id=f"{qid}_c0",
            text="Correctly identifies family history entries documented in the record",
            criterion_type=CriterionType.EXPERIENCER,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c1",
            text="Does not attribute family member conditions to the patient themselves",
            criterion_type=CriterionType.EXPERIENCER,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c2",
            text="Does not fabricate family history details not documented in the record",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.IMPORTANT,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c3",
            text="Identifies the clinical relevance of the family history to the patient's risk profile",
            criterion_type=CriterionType.CAUSAL,
            weight=CriterionWeight.NICE,
        ),
    ]


def _temporal_reasoning_criteria(qid: str) -> list[LongBenchCriterion]:
    return [
        LongBenchCriterion(
            criterion_id=f"{qid}_c0",
            text="Cites specific dates or encounter references for at least 3 clinical events from the patient record",
            criterion_type=CriterionType.CHRONOLOGY,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c1",
            text="Correctly identifies which encounter a key diagnosis or finding first appeared versus when it changed status",
            criterion_type=CriterionType.CHRONOLOGY,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c2",
            text="Does not misattribute clinical events to incorrect encounters or fabricate dates not in the record",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c3",
            text="Identifies conditions whose status changed across encounters (uncertain to confirmed, active to resolved) with correct temporal ordering",
            criterion_type=CriterionType.CHRONOLOGY,
            weight=CriterionWeight.IMPORTANT,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c4",
            text="Distinguishes between findings documented in different encounters rather than conflating them into a single narrative",
            criterion_type=CriterionType.CHRONOLOGY,
            weight=CriterionWeight.IMPORTANT,
        ),
    ]


def _risk_assessment_criteria(qid: str) -> list[LongBenchCriterion]:
    return [
        LongBenchCriterion(
            criterion_id=f"{qid}_c0",
            text="Identifies specific risk factors present in the patient's clinical record",
            criterion_type=CriterionType.SYNTHESIS,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c1",
            text="Does not fabricate risk factors or clinical findings not documented in the record",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c2",
            text="Connects identified risk factors to specific clinical outcomes or recommendations",
            criterion_type=CriterionType.CAUSAL,
            weight=CriterionWeight.IMPORTANT,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c3",
            text="References specific clinical data (labs, vitals, history) to support the risk assessment",
            criterion_type=CriterionType.SYNTHESIS,
            weight=CriterionWeight.NICE,
        ),
    ]


def _slice_a1_criteria(qid: str) -> list[LongBenchCriterion]:
    return [
        LongBenchCriterion(
            criterion_id=f"{qid}_c0",
            text="Lists each current medication and dosage from the most recent discharge",
            criterion_type=CriterionType.MEDICATION,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c1",
            text="Distinguishes current medication orders from historical or discontinued ones",
            criterion_type=CriterionType.CHRONOLOGY,
            weight=CriterionWeight.IMPORTANT,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c2",
            text="Does not introduce medications or doses not documented in chart",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.IMPORTANT,
        ),
    ]


def _slice_a2_criteria(qid: str) -> list[LongBenchCriterion]:
    return [
        LongBenchCriterion(
            criterion_id=f"{qid}_c0",
            text="Identifies at least two medication changes across encounters",
            criterion_type=CriterionType.CHRONOLOGY,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c1",
            text="Attaches each change to a specific encounter date or event",
            criterion_type=CriterionType.CHRONOLOGY,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c2",
            text="Does not attribute a change to an incorrect time window",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.IMPORTANT,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c3",
            text="Notes the trigger that led to the medication change (symptom, test result, or clinical event)",
            criterion_type=CriterionType.CAUSAL,
            weight=CriterionWeight.IMPORTANT,
        ),
    ]


def _slice_a3_criteria(qid: str) -> list[LongBenchCriterion]:
    return [
        LongBenchCriterion(
            criterion_id=f"{qid}_c0",
            text="Identifies diagnoses that changed from suspected to confirmed status",
            criterion_type=CriterionType.CHRONOLOGY,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c1",
            text="Identifies diagnoses that changed from active to resolved status",
            criterion_type=CriterionType.CHRONOLOGY,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c2",
            text="Reports the encounters where status changes were first documented",
            criterion_type=CriterionType.CHRONOLOGY,
            weight=CriterionWeight.IMPORTANT,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c3",
            text="Does not confuse uncertainty language as a confirmed diagnosis",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.IMPORTANT,
        ),
    ]


def _slice_a4_criteria(qid: str) -> list[LongBenchCriterion]:
    return [
        LongBenchCriterion(
            criterion_id=f"{qid}_c0",
            text="Lists at least three key events from the most recent hospitalization",
            criterion_type=CriterionType.SYNTHESIS,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c1",
            text="Preserves event order for that admission",
            criterion_type=CriterionType.CHRONOLOGY,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c2",
            text="Avoids fabricating encounter-level events not in the chart",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.IMPORTANT,
        ),
    ]


def _slice_b1_criteria(qid: str) -> list[LongBenchCriterion]:
    return [
        LongBenchCriterion(
            criterion_id=f"{qid}_c0",
            text="Identifies at least one ruled-out diagnosis",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c1",
            text="Does not report ruled-out findings as confirmed active problems",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c2",
            text="Cites evidence language or testing that supported exclusion",
            criterion_type=CriterionType.CHRONOLOGY,
            weight=CriterionWeight.IMPORTANT,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c3",
            text="Separates exclusion rationale from active plan items",
            criterion_type=CriterionType.SYNTHESIS,
            weight=CriterionWeight.NICE,
        ),
    ]


def _slice_b2_criteria(qid: str) -> list[LongBenchCriterion]:
    return [
        LongBenchCriterion(
            criterion_id=f"{qid}_c0",
            text="Identifies which historical findings belong to family members",
            criterion_type=CriterionType.EXPERIENCER,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c1",
            text="Separately identifies conditions documented for the patient",
            criterion_type=CriterionType.EXPERIENCER,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c2",
            text="Does not merge family history and patient findings into one list",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.IMPORTANT,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c3",
            text="Cites at least one specific evidence snippet location for the attribution",
            criterion_type=CriterionType.CHRONOLOGY,
            weight=CriterionWeight.NICE,
        ),
    ]


def _slice_b3_criteria(qid: str) -> list[LongBenchCriterion]:
    return [
        LongBenchCriterion(
            criterion_id=f"{qid}_c0",
            text="Lists current active conditions from the latest encounter",
            criterion_type=CriterionType.SYNTHESIS,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c1",
            text="Includes only active/ongoing problems for the latest encounter",
            criterion_type=CriterionType.CHRONOLOGY,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c2",
            text="Does not include unrelated historical or family findings",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.IMPORTANT,
        ),
    ]


def _slice_b4_criteria(qid: str) -> list[LongBenchCriterion]:
    return [
        LongBenchCriterion(
            criterion_id=f"{qid}_c0",
            text="Separates active and resolved conditions",
            criterion_type=CriterionType.CHRONOLOGY,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c1",
            text="Provides a documented resolution date or encounter window for each resolved condition",
            criterion_type=CriterionType.CHRONOLOGY,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c2",
            text="Does not represent unresolved conditions as resolved",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.IMPORTANT,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c3",
            text="Avoids listing active findings without status support",
            criterion_type=CriterionType.CHRONOLOGY,
            weight=CriterionWeight.NICE,
        ),
    ]


def _slice_c1_criteria(qid: str) -> list[LongBenchCriterion]:
    return [
        LongBenchCriterion(
            criterion_id=f"{qid}_c0",
            text="Identifies the triggering clinical finding preceding treatment change",
            criterion_type=CriterionType.CAUSAL,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c1",
            text="Connects the trigger to the medication action in the same causal chain",
            criterion_type=CriterionType.CAUSAL,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c2",
            text="Uses timeline or encounter order to justify sequence",
            criterion_type=CriterionType.CHRONOLOGY,
            weight=CriterionWeight.IMPORTANT,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c3",
            text="Does not infer causality without chart support",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.IMPORTANT,
        ),
    ]


def _slice_c2_criteria(qid: str) -> list[LongBenchCriterion]:
    return [
        LongBenchCriterion(
            criterion_id=f"{qid}_c0",
            text="Identifies if any treatment-related adverse effects are documented",
            criterion_type=CriterionType.CAUSAL,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c1",
            text="Maps each adverse effect to a likely treatment or medication",
            criterion_type=CriterionType.CAUSAL,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c2",
            text="Describes how the care team managed the complication",
            criterion_type=CriterionType.CHRONOLOGY,
            weight=CriterionWeight.IMPORTANT,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c3",
            text="Does not state a complication without encounter-level support",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.IMPORTANT,
        ),
    ]


def _slice_c3_criteria(qid: str) -> list[LongBenchCriterion]:
    return [
        LongBenchCriterion(
            criterion_id=f"{qid}_c0",
            text="States the documented reason for admission",
            criterion_type=CriterionType.SYNTHESIS,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c1",
            text="States the principal discharge diagnosis",
            criterion_type=CriterionType.SYNTHESIS,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c2",
            text="Maintains consistency between admission reason and discharge diagnosis",
            criterion_type=CriterionType.CHRONOLOGY,
            weight=CriterionWeight.IMPORTANT,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c3",
            text="Does not add diagnoses not appearing in either admission or discharge narrative",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.IMPORTANT,
        ),
    ]


def _slice_d1_criteria(qid: str) -> list[LongBenchCriterion]:
    return [
        LongBenchCriterion(
            criterion_id=f"{qid}_c0",
            text="Flags at least one interaction or contraindication that is explicitly plausible from chart evidence",
            criterion_type=CriterionType.CAUSAL,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c1",
            text="Cites the medication pairing and its potential risk",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c2",
            text="Includes appropriate caution language instead of absolute certainty when evidence is limited",
            criterion_type=CriterionType.UNCERTAINTY,
            weight=CriterionWeight.IMPORTANT,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c3",
            text="Avoids fabricating interactions not implied by the medication history",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.IMPORTANT,
        ),
    ]


def _slice_d2_criteria(qid: str) -> list[LongBenchCriterion]:
    return [
        LongBenchCriterion(
            criterion_id=f"{qid}_c0",
            text="Identifies at least one medication-condition or medication-lab mismatch",
            criterion_type=CriterionType.RISK,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c1",
            text="Explains the clinical concern with context from documented conditions or labs",
            criterion_type=CriterionType.CAUSAL,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c2",
            text="Does not overstate risk absent supporting data",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.IMPORTANT,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c3",
            text="Provides encounter-level specificity for the concern",
            criterion_type=CriterionType.CHRONOLOGY,
            weight=CriterionWeight.NICE,
        ),
    ]


def _slice_d3_criteria(qid: str) -> list[LongBenchCriterion]:
    return [
        LongBenchCriterion(
            criterion_id=f"{qid}_c0",
            text="Identifies documented medication allergies",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c1",
            text="Assesses whether a current medication shares a high-risk class overlap concern",
            criterion_type=CriterionType.MEDICATION,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c2",
            text="Does not add allergies or class relationships not documented",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.IMPORTANT,
        ),
    ]


def _slice_e1_criteria(qid: str) -> list[LongBenchCriterion]:
    return [
        LongBenchCriterion(
            criterion_id=f"{qid}_c0",
            text="Reviews the chart for risk factors relevant to statin eligibility",
            criterion_type=CriterionType.RISK,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c1",
            text="Cites specific age, lipid, diagnosis, or comorbidity evidence if available",
            criterion_type=CriterionType.CHRONOLOGY,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c2",
            text="Reports uncertainty if required threshold data are missing",
            criterion_type=CriterionType.UNCERTAINTY,
            weight=CriterionWeight.IMPORTANT,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c3",
            text="Does not recommend therapy solely from general guideline recall",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.IMPORTANT,
        ),
    ]


def _slice_e2_criteria(qid: str) -> list[LongBenchCriterion]:
    return [
        LongBenchCriterion(
            criterion_id=f"{qid}_c0",
            text="Identifies at least one monitoring or follow-up item that is missing or overdue",
            criterion_type=CriterionType.RISK,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c1",
            text="Supports each identified gap with medication, condition, or timeline context",
            criterion_type=CriterionType.CHRONOLOGY,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c2",
            text="Does not claim monitoring is missing when it is documented",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.IMPORTANT,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c3",
            text="Avoids suggesting incorrect lab targets for the given clinical context",
            criterion_type=CriterionType.CAUSAL,
            weight=CriterionWeight.NICE,
        ),
    ]


def _slice_e3_criteria(qid: str) -> list[LongBenchCriterion]:
    return [
        LongBenchCriterion(
            criterion_id=f"{qid}_c0",
            text="Identifies at least two modifiable risk factors in the chart",
            criterion_type=CriterionType.SYNTHESIS,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c1",
            text="Uses chart evidence (conditions, labs, vitals, social data) to justify each factor",
            criterion_type=CriterionType.SYNTHESIS,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c2",
            text="Does not invent preventive opportunities not documented",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.IMPORTANT,
        ),
    ]


def _slice_e4_criteria(qid: str) -> list[LongBenchCriterion]:
    return [
        LongBenchCriterion(
            criterion_id=f"{qid}_c0",
            text="Identifies trend direction (improving, worsening, unstable) for at least two serial labs",
            criterion_type=CriterionType.CHRONOLOGY,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c1",
            text="Cites values and dates supporting the observed trend",
            criterion_type=CriterionType.SYNTHESIS,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c2",
            text="Identifies whether a concerning threshold was newly crossed",
            criterion_type=CriterionType.RISK,
            weight=CriterionWeight.IMPORTANT,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c3",
            text="Avoids drawing trend conclusions from single data points",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.IMPORTANT,
        ),
    ]


def _slice_f1_criteria(qid: str) -> list[LongBenchCriterion]:
    return [
        LongBenchCriterion(
            criterion_id=f"{qid}_c0",
            text="Lists at least three medication changes with encounter dates",
            criterion_type=CriterionType.CHRONOLOGY,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c1",
            text="Identifies the documented reason for each medication change",
            criterion_type=CriterionType.CAUSAL,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c2",
            text="Correctly distinguishes starts, dose changes, and discontinuations",
            criterion_type=CriterionType.SYNTHESIS,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c3",
            text="Timeline is internally consistent with no contradictory ordering",
            criterion_type=CriterionType.CHRONOLOGY,
            weight=CriterionWeight.IMPORTANT,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c4",
            text="Does not attribute medication changes to encounters where they are not documented",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.IMPORTANT,
        ),
    ]


def _slice_f2_criteria(qid: str) -> list[LongBenchCriterion]:
    return [
        LongBenchCriterion(
            criterion_id=f"{qid}_c0",
            text="Identifies at least one condition that appears in some notes but not others",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c1",
            text="Provides a reconciled current problem list based on the most recent evidence",
            criterion_type=CriterionType.SYNTHESIS,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c2",
            text="Distinguishes active from resolved conditions in the reconciled list",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c3",
            text="Does not include family history conditions as patient conditions",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.IMPORTANT,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c4",
            text="Cites which notes support or contradict each condition's status",
            criterion_type=CriterionType.SYNTHESIS,
            weight=CriterionWeight.IMPORTANT,
        ),
    ]


def _slice_f3_criteria(qid: str) -> list[LongBenchCriterion]:
    return [
        LongBenchCriterion(
            criterion_id=f"{qid}_c0",
            text="Identifies a plausible causal chain spanning at least three clinical events",
            criterion_type=CriterionType.CAUSAL,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c1",
            text="Each link in the chain is supported by documented clinical evidence",
            criterion_type=CriterionType.CAUSAL,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c2",
            text="Chain follows correct temporal ordering (causes precede effects)",
            criterion_type=CriterionType.CHRONOLOGY,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c3",
            text="Does not assert causal relationships not supported by the clinical record",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.IMPORTANT,
        ),
    ]


def _slice_f4_criteria(qid: str) -> list[LongBenchCriterion]:
    return [
        LongBenchCriterion(
            criterion_id=f"{qid}_c0",
            text="Correctly identifies content from both the earliest and most recent encounters",
            criterion_type=CriterionType.CHRONOLOGY,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c1",
            text="Lists at least two clinically significant changes between the encounters",
            criterion_type=CriterionType.SYNTHESIS,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c2",
            text="For each change, identifies the encounter where it was first documented",
            criterion_type=CriterionType.CHRONOLOGY,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c3",
            text="Does not confuse intermediate encounters with the earliest or most recent",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.IMPORTANT,
        ),
    ]


def _slice_f5_criteria(qid: str) -> list[LongBenchCriterion]:
    return [
        LongBenchCriterion(
            criterion_id=f"{qid}_c0",
            text="Identifies any documented or potential drug-drug interactions across the medication history",
            criterion_type=CriterionType.RISK,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c1",
            text="Specifies the time period when interacting medications were co-prescribed",
            criterion_type=CriterionType.CHRONOLOGY,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c2",
            text="Notes whether the interaction was addressed or recognized in the record",
            criterion_type=CriterionType.SYNTHESIS,
            weight=CriterionWeight.IMPORTANT,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c3",
            text="Does not claim interactions without evidence of concurrent prescriptions",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.IMPORTANT,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c4",
            text="If no interactions found, explicitly states this rather than fabricating one",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.CRITICAL,
        ),
    ]


def _slice_f6_criteria(qid: str) -> list[LongBenchCriterion]:
    return [
        LongBenchCriterion(
            criterion_id=f"{qid}_c0",
            text="Identifies at least one guideline-recommended intervention relevant to the patient's conditions",
            criterion_type=CriterionType.RISK,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c1",
            text="Cites specific patient data (labs, conditions, risk factors) supporting the assessment",
            criterion_type=CriterionType.SYNTHESIS,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c2",
            text="Correctly identifies whether the recommended intervention appears in the record",
            criterion_type=CriterionType.SYNTHESIS,
            weight=CriterionWeight.CRITICAL,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c3",
            text="Does not recommend interventions that are already documented in the patient's care",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.IMPORTANT,
        ),
        LongBenchCriterion(
            criterion_id=f"{qid}_c4",
            text="Assessment is based on documented clinical trajectory, not hypothetical scenarios",
            criterion_type=CriterionType.ASSERTION,
            weight=CriterionWeight.IMPORTANT,
        ),
    ]


_SLICE_CRITERIA_TEMPLATES: dict[str, Any] = {
    "A1": _slice_a1_criteria,
    "A2": _slice_a2_criteria,
    "A3": _slice_a3_criteria,
    "A4": _slice_a4_criteria,
    "B1": _slice_b1_criteria,
    "B2": _slice_b2_criteria,
    "B3": _slice_b3_criteria,
    "B4": _slice_b4_criteria,
    "C1": _slice_c1_criteria,
    "C2": _slice_c2_criteria,
    "C3": _slice_c3_criteria,
    "D1": _slice_d1_criteria,
    "D2": _slice_d2_criteria,
    "D3": _slice_d3_criteria,
    "E1": _slice_e1_criteria,
    "E2": _slice_e2_criteria,
    "E3": _slice_e3_criteria,
    "E4": _slice_e4_criteria,
    "F1": _slice_f1_criteria,
    "F2": _slice_f2_criteria,
    "F3": _slice_f3_criteria,
    "F4": _slice_f4_criteria,
    "F5": _slice_f5_criteria,
    "F6": _slice_f6_criteria,
}


_DOMAIN_CRITERIA_TEMPLATES: dict[QuestionDomain, Any] = {
    QuestionDomain.MEDICATION_RECONCILIATION: _medication_criteria,
    QuestionDomain.PROBLEM_LIST: _problem_list_criteria,
    QuestionDomain.FAMILY_HISTORY: _family_history_criteria,
    QuestionDomain.TEMPORAL_REASONING: _temporal_reasoning_criteria,
    QuestionDomain.RISK_ASSESSMENT: _risk_assessment_criteria,
}


# ============================================================================
# Serialization
# ============================================================================


def cohort_to_json(cohort: LongBenchCohort) -> dict:
    """Serialize a cohort to JSON-compatible dict."""
    return {
        "cohort_id": cohort.cohort_id,
        "version": cohort.version,
        "metadata": cohort.metadata,
        "tier_summary": cohort.tier_summary,
        "patients": [
            {
                "patient_id": p.patient_id,
                "tier": p.tier.value,
                "encounter_count": p.encounter_count,
                "total_note_length": p.total_note_length,
                "earliest_date": p.earliest_date,
                "latest_date": p.latest_date,
                "condition_count": p.condition_count,
                "medication_count": p.medication_count,
                "has_family_history": p.has_family_history,
            }
            for p in cohort.patients
        ],
        "questions": [
            {
                "question_id": q.question_id,
                "patient_id": q.patient_id,
                "question_text": q.question_text,
                "domain": q.domain.value,
                "tier": q.tier.value,
                "encounter_count": q.encounter_count,
                "generated_by": q.generated_by,
                "validated_by": q.validated_by,
                "slice_id": q.slice_id.value if q.slice_id else None,
                "expected_mechanism": (
                    q.expected_mechanism.value if q.expected_mechanism else None
                ),
                "kg_edge_types_needed": q.kg_edge_types_needed,
                "criteria": [
                    {
                        "criterion_id": c.criterion_id,
                        "text": c.text,
                        "criterion_type": c.criterion_type.value,
                        "weight": c.weight.value,
                        "evidence_source": c.evidence_source,
                    }
                    for c in q.criteria
                ],
            }
            for q in cohort.questions
        ],
    }


def cohort_from_json(data: dict) -> LongBenchCohort:
    """Deserialize a cohort from JSON dict."""
    patients = [
        PatientCohortEntry(
            patient_id=p["patient_id"],
            tier=LongitudinalTier(p["tier"]),
            encounter_count=p["encounter_count"],
            total_note_length=p.get("total_note_length", 0),
            earliest_date=p.get("earliest_date", ""),
            latest_date=p.get("latest_date", ""),
            condition_count=p.get("condition_count", 0),
            medication_count=p.get("medication_count", 0),
            has_family_history=p.get("has_family_history", False),
        )
        for p in data.get("patients", [])
    ]

    questions = []
    for q in data.get("questions", []):
        criteria = [
            LongBenchCriterion(
                criterion_id=c["criterion_id"],
                text=c["text"],
                criterion_type=CriterionType(c["criterion_type"]),
                weight=CriterionWeight(c.get("weight", "important")),
                evidence_source=c.get("evidence_source", ""),
            )
            for c in q.get("criteria", [])
        ]
        questions.append(LongBenchQuestion(
            question_id=q["question_id"],
            patient_id=q["patient_id"],
            question_text=q["question_text"],
            domain=QuestionDomain(q["domain"]),
            tier=LongitudinalTier(q["tier"]),
            criteria=criteria,
            encounter_count=q.get("encounter_count", 0),
            generated_by=q.get("generated_by", "unknown"),
            validated_by=q.get("validated_by"),
            slice_id=_optional_slice_id(q.get("slice_id")),
            expected_mechanism=_optional_expected_mechanism(q.get("expected_mechanism")),
            kg_edge_types_needed=q.get("kg_edge_types_needed", []),
        ))

    return LongBenchCohort(
        cohort_id=data["cohort_id"],
        patients=patients,
        questions=questions,
        version=data.get("version", "1.0.0"),
        metadata=data.get("metadata", {}),
    )
