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
        ))

    return LongBenchCohort(
        cohort_id=data["cohort_id"],
        patients=patients,
        questions=questions,
        version=data.get("version", "1.0.0"),
        metadata=data.get("metadata", {}),
    )
