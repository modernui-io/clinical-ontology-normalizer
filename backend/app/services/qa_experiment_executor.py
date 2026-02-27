"""QA Experiment Executor — runs QA questions through GraphRAG + LLM.

Bridges the experiment runner (which collects structural metrics) with
the QA evaluation service (which scores answers) by actually querying
the GraphRAG pipeline and an LLM for each question.

Usage:
    executor = QAExperimentExecutor()
    report = await executor.run_assertion_ablation(
        patient_id="P001",
        condition="full_epistemic",
        run_id="...",
    )
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field

import httpx
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_sync_engine
from app.services.graph_augmented_rag import GraphAugmentedRAGService
from app.services.llm_service import (
    LLMConfig,
    LLMProvider,
    LLMResponse,
    TokenUsage,
    CostEstimate,
    get_llm_service,
)
from app.services.qa_evaluation import (
    ASSERTION_QUESTIONS,
    RAG_QUESTIONS,
    TEMPORAL_QUESTIONS,
    QAEvaluationReport,
    QAEvaluationService,
    QAQuestion,
    QAResult,
)
from app.services.research_service import get_research_service

logger = logging.getLogger(__name__)


# ============================================================================
# System prompts for clinical QA
# ============================================================================

CLINICAL_QA_SYSTEM_PROMPT_BASE = """\
You are a clinical reasoning assistant answering questions about a specific patient.
Use ONLY the provided evidence to answer. Be precise and concise.
If the evidence is insufficient, say so rather than guessing.
Answer in 1-3 sentences. Do not hedge unnecessarily when the evidence is clear."""

CLINICAL_QA_SYSTEM_PROMPT_EPISTEMIC = """\
You are a clinical reasoning assistant answering questions about a specific patient.
Use ONLY the provided evidence to answer. Be precise and concise.

CRITICAL — The evidence includes ASSERTION STATUS metadata that you MUST use:

1. **NEGATED / ABSENT**: If a finding is marked NEGATED or listed under "NEGATED (patient does NOT have)",
   the patient definitively DOES NOT have that condition. Answer "No" to questions about negated conditions.
2. **UNCERTAIN / POSSIBLE**: If marked UNCERTAIN, the condition is suspected but NOT confirmed.
   Answer with "uncertain" or "suspected but not confirmed."
3. **FAMILY HISTORY**: If marked FAMILY_HISTORY, this is a relative's condition, NOT the patient's own.
   Answer "No, this is family history only" for questions about the patient having it.
4. **HISTORICAL / RESOLVED**: If marked HISTORICAL, the condition existed in the past but is resolved.
   Answer "Previously, but no longer" or similar.
5. **CONDITIONAL**: If marked CONDITIONAL, the recommendation depends on specific conditions being met.

The "Assertion Notes" section summarizes these statuses. Always check it FIRST before answering.
For temporal questions, use the timeline and note any changes over time.
If the evidence is insufficient, say so rather than guessing.
Answer in 1-3 sentences. Do not hedge unnecessarily when the evidence is clear."""


CLINICAL_QA_SYSTEM_PROMPT_EPISTEMIC_V2 = """\
You are a clinical reasoning assistant answering questions about a specific patient.
Use ONLY the provided evidence to answer. Be precise and concise.

The evidence includes ASSERTION STATUS labels on clinical findings:
- NEGATED/ABSENT = patient does NOT have this condition
- UNCERTAIN/POSSIBLE = suspected, not confirmed
- FAMILY_HISTORY = a relative's condition, not the patient's
- HISTORICAL = past/resolved condition
- CONDITIONAL = depends on specific circumstances

Use these labels to inform your reasoning, but answer the question directly.
If the evidence is insufficient, say so rather than guessing.
Answer in 1-3 sentences. Do not hedge unnecessarily when the evidence is clear."""


CLINICAL_QA_SYSTEM_PROMPT_EPISTEMIC_V4 = """\
You are a clinical reasoning assistant answering questions about a specific patient.
Use ONLY the provided evidence to answer. Be precise and concise.

CRITICAL — Match your answer to the ASSERTION STATUS of the finding asked about.

The evidence starts with a "FINDING RELEVANT TO YOUR QUESTION" section that tells you
the clinical status of the finding the question asks about. Use this to guide your answer:

For HISTORICAL/RESOLVED findings, use past-tense temporal language:
  - "was", "previously", "formerly", "had", "resolved", "no longer active"
For CURRENT/ACTIVE findings, use present-tense language:
  - "has", "currently", "is", "active", "ongoing"
For NEGATED findings:
  - "does not have", "no evidence of", "ruled out"
For FAMILY HISTORY findings:
  - "family history of", "relative has/had", not the patient's own condition
For UNCERTAIN findings:
  - "suspected", "possible", "not confirmed"
For CONDITIONAL findings:
  - "if", "would", "depending on", "when indicated"

Always check the "IMPORTANT: Clinical Assertion Status" section for a full list of
non-present findings. Answer in 1-3 sentences. Do not hedge when the evidence is clear."""


CLINICAL_QA_SYSTEM_PROMPT_EPISTEMIC_V6 = """\
You are a clinical reasoning assistant. Answer using ONLY the provided evidence.

Before answering, check three things:
1. SUBJECT — Is this about the patient or a family member?
2. TIME — Is the finding current/active or historical/resolved?
3. ASSERTION — Is it present, absent, possible, or conditional?

If evidence is insufficient or contradictory, say "insufficient evidence."
Answer in 1-3 sentences."""


CLINICAL_QA_SYSTEM_PROMPT_INTENT_AWARE = """\
You are a clinical reasoning assistant answering questions about a specific patient.
Use ONLY the provided evidence to answer. Be precise and concise.

EVIDENCE FORMAT — KNOWLEDGE GRAPH:
The evidence comes from a structured clinical knowledge graph (KG), NOT raw clinical notes.
Each finding is a verified EDGE connecting a patient node to a concept node (condition, drug, etc.).
Every edge has metadata fields that were extracted and validated by clinical NLP:

  - ASSERTION: present | negated | uncertain | conditional
  - TEMPORALITY: current | historical/past
  - EXPERIENCER: patient | family_member

These metadata labels are the GROUND TRUTH for clinical status. They override any impression
you might form from reading the surrounding text. If a finding is labeled NEGATED, the patient
does NOT have it — even if the word appears in the notes. If labeled UNCERTAIN, it is NOT
confirmed — even if the text describes symptoms.

CRITICAL RULES — MATCH YOUR ANSWER TO THE METADATA:

1. NEGATED/ABSENT: Patient does NOT have this. Answer "No."
2. UNCERTAIN/POSSIBLE: NOT confirmed. Answer "suspected but not confirmed" or "uncertain."
   Do NOT say "yes, confirmed" when the assertion is uncertain.
3. FAMILY_HISTORY: A relative's condition. Answer "family history only, not the patient's."
4. HISTORICAL/RESOLVED: Past condition. Answer "previously, but no longer active."
   Do NOT say "yes, currently active" when temporality is historical/past.
5. CONDITIONAL: Depends on circumstances. Use "if/when" language.
6. PRESENT/CURRENT: Patient has this. Answer "Yes."

Always check "Assertion Notes" and "IMPORTANT: Clinical Assertion Status" sections FIRST.

GUIDANCE FOR TEMPORAL QUESTIONS:
- CHANGES between visits: Look at the KEY CHANGES section.
  Focus on items listed as NEW (added) or DISCONTINUED (removed). Be specific about names.
- CURRENT STATUS: Check the CURRENT STATUS section.
  If ACTIVE, answer "Yes, currently active." If NOT FOUND, it is not in current records.
  If RESOLVED, answer "No, resolved."
- HISTORICAL findings: Check both historical and current evidence.
  If found only in historical records, answer that it is a past/resolved finding.
  If marked STILL ACTIVE, it was historical but remains active now.
- DURATION/CHRONICITY: Check the CHRONICITY ASSESSMENT section.
  State how many admissions the condition appears in. Multiple admissions = chronic/ongoing.

Answer in 1-3 sentences. Do not hedge when the evidence is clear."""


# ── Category-specific prompts for C4h (short, focused) ──────────────────

_SYSTEM_PROMPT_ASSERTION = """\
You are a clinical reasoning assistant. Answer using ONLY the provided evidence.

The evidence comes from a structured knowledge graph. Each finding has a verified
ASSERTION STATUS (present, negated, uncertain, conditional) and EXPERIENCER (patient, family).
These metadata labels are ground truth — they override any impression from surrounding text.

RULES:
- NEGATED → patient does NOT have this. Answer "No."
- UNCERTAIN/POSSIBLE → NOT confirmed. Answer "suspected but not confirmed."
- FAMILY HISTORY → relative's condition, not the patient's.
- CONDITIONAL → depends on circumstances.
- PRESENT → patient has this. Answer "Yes."

Answer in 1-3 sentences."""

_SYSTEM_PROMPT_TEMPORAL = """\
You are a clinical reasoning assistant. Answer using ONLY the provided evidence.

The evidence comes from a structured knowledge graph with verified temporal metadata.
Focus on the structured sections (KEY CHANGES, CURRENT STATUS, TEMPORAL STATUS,
CHRONICITY ASSESSMENT) — these are the authoritative source.

RULES:
- CHANGES: List specific items NEW (added) or DISCONTINUED (removed).
- CURRENT STATUS: ACTIVE means yes. NOT FOUND means not in records. RESOLVED means no.
- HISTORICAL: If only in past records, it is resolved/no longer active.
  If marked STILL ACTIVE, it remains active.
- DURATION: Count admissions. Multiple admissions = chronic/ongoing.

Answer in 1-3 sentences. Be specific about names."""


def _get_system_prompt(
    assertion_mode: str,
    intent_aware: bool = False,
    prompt_optimized: bool = False,
    question_intent: str | None = None,
    question_category: str | None = None,
) -> str:
    """Return the appropriate system prompt based on assertion mode."""
    if prompt_optimized:
        # C4h: short, category-specific prompts
        if question_intent in ("change", "current_state", "historical", "duration"):
            return _SYSTEM_PROMPT_TEMPORAL
        return _SYSTEM_PROMPT_ASSERTION
    if intent_aware:
        return CLINICAL_QA_SYSTEM_PROMPT_INTENT_AWARE
    if assertion_mode == "full_v6":
        return CLINICAL_QA_SYSTEM_PROMPT_EPISTEMIC_V6
    if assertion_mode == "full_v4":
        return CLINICAL_QA_SYSTEM_PROMPT_EPISTEMIC_V4
    if assertion_mode == "full_v2":
        return CLINICAL_QA_SYSTEM_PROMPT_EPISTEMIC_V2
    if assertion_mode in ("full", "full_v3", "full_v5"):
        return CLINICAL_QA_SYSTEM_PROMPT_EPISTEMIC
    return CLINICAL_QA_SYSTEM_PROMPT_BASE


# ============================================================================
# QA Experiment Executor
# ============================================================================


# Keywords indicating a question is about calculable clinical scores
_CALCULATOR_KEYWORDS = re.compile(
    r"\b(score|risk|calculate|calculator|wells|heart\s+score|cha2ds2|chads|"
    r"has-bled|hasbled|meld|child-pugh|apache|sofa|curb-65|ascvd|"
    r"framingham|gfr|ckd-epi|mdrd|bmi|corrected\s+calcium|anion\s+gap|"
    r"glasgow|nihss|timi|grace)\b",
    re.IGNORECASE,
)


def _is_calculator_question(question: str) -> bool:
    """Return True if the question is about a calculable clinical score."""
    return bool(_CALCULATOR_KEYWORDS.search(question))


@dataclass
class QARunConfig:
    """Configuration for a QA experiment run.

    Fields map to the 5-condition ablation (NeurIPS 2026):
      C1: LLM alone       — raw_note_only=True
      C2: LLM+vanilla RAG — retrieval_mode="doc_only", assertion_mode="none", temporal_mode="no_temporal"
      C3: LLM+KG-RAG      — retrieval_mode="graph_plus_doc", assertion_mode="none", temporal_mode="no_temporal"
      C4: LLM+epistemic    — retrieval_mode="graph_plus_doc", assertion_mode="full", temporal_mode="full_bitemporal"
      C5: Full system      — retrieval_mode="graph_plus_doc_plus_guidelines", assertion="full",
                             temporal="full_bitemporal", calculator_enabled=True, guidelines_enabled=True
    """

    patient_id: str
    condition: str
    assertion_mode: str = "full"
    temporal_mode: str = "full_bitemporal"
    retrieval_mode: str = "graph_plus_doc"
    llm_model: str = "claude-sonnet-4-5-20250929"
    llm_provider: str = "anthropic"  # "anthropic", "openai", or "ollama"
    ollama_base_url: str = "http://localhost:11434"
    max_hops: int = 2
    max_paths: int = 10
    # NeurIPS ablation extensions
    raw_note_only: bool = False  # C1: bypass RAG, send raw note text to LLM
    long_context: bool = False  # C6: dump ALL patient notes into prompt (no retrieval, no KG)
    deterministic_only: bool = False  # C7: structured KG queries only, no LLM
    calculator_enabled: bool = False  # C5: run clinical calculators on KG data
    guidelines_enabled: bool = False  # C5: include guideline retrieval
    use_llm_judge: bool = False  # Use LLM judge for scoring instead of keyword matching
    intent_aware: bool = False  # C4g: intent-specific graph retrieval for temporal categories
    prompt_optimized: bool = False  # C4h: category-specific prompts + assertion injection
    # Reproducibility
    random_seed: int = 42


# ============================================================================
# Ollama client (local models — free, no API key needed)
# ============================================================================


async def _call_ollama(
    prompt: str,
    system_prompt: str,
    model: str,
    base_url: str = "http://localhost:11434",
    temperature: float = 0.0,
    seed: int = 42,
) -> LLMResponse:
    """Call a local Ollama model.

    Args:
        prompt: User prompt.
        system_prompt: System prompt.
        model: Ollama model name (e.g., "alibayram/medgemma:27b").
        base_url: Ollama server URL.
        temperature: Sampling temperature (0.0 for deterministic).
        seed: Random seed for reproducibility.

    Returns:
        LLMResponse with generated content.
    """
    t0 = time.perf_counter()

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "options": {
            "temperature": temperature,
            "seed": seed,
            "num_predict": 512,
        },
    }

    max_retries = 3
    data = {}
    async with httpx.AsyncClient(timeout=180.0) as client:
        for attempt in range(max_retries):
            try:
                resp = await client.post(f"{base_url}/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
                break
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.HTTPStatusError) as exc:
                if attempt < max_retries - 1:
                    wait = 2 ** attempt
                    logger.warning("Ollama call failed (attempt %d/%d): %s — retrying in %ds", attempt + 1, max_retries, exc, wait)
                    await asyncio.sleep(wait)
                else:
                    raise

    content = data.get("message", {}).get("content", "")
    eval_count = data.get("eval_count", 0)
    prompt_eval_count = data.get("prompt_eval_count", 0)
    latency_ms = (time.perf_counter() - t0) * 1000

    return LLMResponse(
        content=content,
        model=model,
        provider=LLMProvider.OPENAI,  # Placeholder — not billed
        token_usage=TokenUsage(
            prompt_tokens=prompt_eval_count,
            completion_tokens=eval_count,
            total_tokens=prompt_eval_count + eval_count,
        ),
        cost_estimate=CostEstimate(),  # $0 — local model
        latency_ms=latency_ms,
    )


def _load_checkpoint(checkpoint_path: str, condition: str) -> dict[str, dict]:
    """Load checkpoint file and return dict of question_id -> result for a condition."""
    completed: dict[str, dict] = {}
    try:
        with open(checkpoint_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if entry.get("condition") == condition:
                    completed[entry["question_id"]] = entry
    except FileNotFoundError:
        pass
    return completed


def _append_checkpoint(checkpoint_path: str, entry: dict) -> None:
    """Append a single result entry to the checkpoint JSONL file."""
    import os
    os.makedirs(os.path.dirname(checkpoint_path), exist_ok=True)
    with open(checkpoint_path, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


class QAExperimentExecutor:
    """Executes QA experiments by querying GraphRAG + LLM and scoring results."""

    def __init__(self) -> None:
        self.qa_service = QAEvaluationService()
        self.research_service = get_research_service()

    async def _ask_question(
        self,
        question: QAQuestion,
        config: QARunConfig,
        rag_service: GraphAugmentedRAGService,
    ) -> QAResult:
        """Ask a single question through GraphRAG + LLM and score the answer.

        Supports all 5 ablation conditions:
        - C1 (raw_note_only=True): bypass RAG entirely, send raw clinical context
        - C2-C4: standard RAG with varying assertion/temporal/retrieval modes
        - C5: full system with calculators + guidelines
        """
        t0 = time.perf_counter()

        try:
            # Use question-specific patient_id if available (multi-patient benchmarks)
            effective_patient_id = (
                question.metadata.get("patient_id") or config.patient_id
            )

            # === C7: Deterministic KG queries only — no LLM ===
            if config.deterministic_only:
                evidence = self._get_deterministic_kg_answer(
                    effective_patient_id, question, rag_service,
                )
                latency_ms = (time.perf_counter() - t0) * 1000
                # Score directly — no LLM call
                result = self.qa_service.score_answer(
                    question, evidence, config.condition,
                )
                result.latency_ms = latency_ms
                result.reasoning_trace = "Deterministic KG query — no LLM"
                return result

            # === C6: Long context — dump ALL notes into prompt ===
            if config.long_context:
                evidence = self._get_all_notes_context(effective_patient_id, rag_service)
                user_prompt = (
                    f"Below are ALL clinical notes for this patient, in chronological order.\n"
                    f"There are multiple admission records spanning their full history.\n\n"
                    f"{evidence}\n\n"
                    f"Question: {question.question}\n\n"
                    f"Answer concisely based on ALL the notes above. Synthesize information "
                    f"across multiple admissions if needed."
                )
                evidence_pieces = evidence.count("---")
                graph_path_count = 0

            # === C1 bypass: raw note → LLM, no RAG ===
            elif config.raw_note_only:
                evidence = self._get_raw_note_context(effective_patient_id, rag_service)
                user_prompt = (
                    f"Clinical note:\n{evidence}\n\n"
                    f"Question: {question.question}\n\n"
                    f"Answer concisely based on the note above."
                )
                evidence_pieces = 1
                graph_path_count = 0
            else:
                # Detect question intent for targeted retrieval (C4g)
                question_intent = None
                if config.intent_aware:
                    from app.services.graph_augmented_rag import _classify_question_intent
                    question_intent = _classify_question_intent(
                        question.question,
                        question.metadata,
                    )

                # Step 1: Retrieve graph-augmented context
                context = rag_service.retrieve_context(
                    query=question.question,
                    patient_id=effective_patient_id,
                    max_hops=config.max_hops,
                    max_paths=config.max_paths,
                    assertion_mode=config.assertion_mode,
                    temporal_mode=config.temporal_mode,
                    retrieval_mode=config.retrieval_mode,
                    question_intent=question_intent,
                    question_metadata=question.metadata if question_intent else None,
                )

                # Step 2: Build LLM prompt
                if config.prompt_optimized:
                    # C4h: optimized evidence formatting
                    # - Suppress raw doc context for assertion questions (it contradicts metadata)
                    # - Always include assertion callout at question level
                    suppress_docs = question_intent is None  # Task A assertion questions
                    if question_intent:
                        evidence = context.to_llm_prompt_intent_aware(
                            question_text=question.question,
                            question_intent=question_intent,
                        )
                    else:
                        evidence = context.to_llm_prompt_optimized(
                            question_text=question.question,
                            suppress_doc_context=suppress_docs,
                        )
                    # Build assertion callout for injection at question level
                    assertion_hint = context._question_subject_callout(question.question)
                    q_section = f"Question: {question.question}"
                    if assertion_hint:
                        q_section += f"\n\n{assertion_hint}"
                    user_prompt = (
                        f"Patient evidence:\n{evidence}\n\n"
                        f"{q_section}\n\n"
                        f"Before answering, identify the finding's assertion status in the metadata.\n"
                        f"Your answer MUST be consistent with that status.\n"
                        f"Answer concisely."
                    )
                elif question_intent:
                    # Intent-aware formatting for C4g
                    evidence = context.to_llm_prompt_intent_aware(
                        question_text=question.question,
                        question_intent=question_intent,
                    )
                    user_prompt = (
                        f"Patient evidence:\n{evidence}\n\n"
                        f"Question: {question.question}\n\n"
                        f"Answer concisely based on the evidence above."
                    )
                elif config.assertion_mode == "full_v5":
                    evidence = context.to_llm_prompt_v5(question_text=question.question)
                    user_prompt = (
                        f"Patient evidence:\n{evidence}\n\n"
                        f"Question: {question.question}\n\n"
                        f"Answer concisely based on the evidence above."
                    )
                elif config.assertion_mode == "full_v4":
                    evidence = context.to_llm_prompt_v4(question_text=question.question)
                    user_prompt = (
                        f"Patient evidence:\n{evidence}\n\n"
                        f"Question: {question.question}\n\n"
                        f"IMPORTANT: Check the assertion status of the relevant finding before answering.\n"
                        f"Use temporal language (was, previously, former, resolved) for historical findings.\n"
                        f"Use present language (has, current, active, ongoing) for current findings.\n\n"
                        f"Answer concisely based on the evidence above."
                    )
                else:
                    evidence = context.to_llm_prompt(assertion_mode=config.assertion_mode)
                    user_prompt = (
                        f"Patient evidence:\n{evidence}\n\n"
                        f"Question: {question.question}\n\n"
                        f"Answer concisely based on the evidence above."
                    )

                # C5: Conditionally inject calculator results (only for calculator questions)
                calculator_context = ""
                if config.calculator_enabled and _is_calculator_question(question.question):
                    calculator_context = self._get_calculator_context(
                        effective_patient_id, question.question,
                    )
                if calculator_context:
                    user_prompt += (
                        f"\n\n--- Supplementary: Calculator Results ---\n"
                        f"{calculator_context}\n"
                        f"Use these calculator results only if directly relevant to the question."
                    )
                evidence_pieces = context.total_evidence_pieces
                graph_path_count = len(context.graph_paths)

            # Step 3: Call LLM (local Ollama or cloud API)
            system_prompt = _get_system_prompt(
                config.assertion_mode,
                intent_aware=bool(question_intent),
                prompt_optimized=config.prompt_optimized,
                question_intent=question_intent,
                question_category=question.category,
            )
            if config.llm_provider == "ollama":
                response = await _call_ollama(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    model=config.llm_model,
                    base_url=config.ollama_base_url,
                    temperature=0.0,
                    seed=config.random_seed,
                )
            else:
                llm = get_llm_service(LLMConfig(
                    provider=LLMProvider(config.llm_provider),
                    model=config.llm_model,
                    max_tokens=512,
                    temperature=0.0,
                ))
                response = await llm.generate(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                )

            predicted_answer = response.content.strip()
            latency_ms = (time.perf_counter() - t0) * 1000

            # Step 4: Score the answer (keyword or LLM judge)
            if config.use_llm_judge:
                result = await self._score_with_llm_judge(
                    question, predicted_answer, config,
                )
            else:
                result = self.qa_service.score_answer(
                    question, predicted_answer, config.condition,
                )
            result.latency_ms = latency_ms
            result.reasoning_trace = (
                f"Evidence pieces: {evidence_pieces}, "
                f"Graph paths: {graph_path_count}, "
                f"Tokens: {response.token_usage.total_tokens}"
            )

            return result

        except Exception as exc:
            latency_ms = (time.perf_counter() - t0) * 1000
            logger.warning(
                "QA question %s failed: %s", question.question_id, exc,
            )
            # Rollback session on DB errors to prevent cascade failures
            try:
                rag_service._session.rollback()
            except Exception:
                pass
            return QAResult(
                question_id=question.question_id,
                predicted_answer="",
                expected_answer=question.expected_answer,
                correct=False,
                score=0.0,
                category=question.category,
                condition=config.condition,
                latency_ms=latency_ms,
                error=str(exc)[:200],
            )

    def _get_raw_note_context(
        self,
        patient_id: str,
        rag_service: GraphAugmentedRAGService,
    ) -> str:
        """Get raw clinical note text for C1 condition (no RAG).

        Retrieves the most recent document for the patient and returns
        raw text — no graph traversal, no assertion enrichment.
        """
        try:
            from sqlalchemy import select
            from app.models.document import Document

            stmt = (
                select(Document)
                .where(Document.patient_id == patient_id)
                .order_by(Document.created_at.desc())
                .limit(3)
            )
            result = rag_service._session.execute(stmt)
            docs = list(result.scalars().all())
            if docs:
                return "\n\n---\n\n".join(
                    (d.text[:2000] if d.text else "") for d in docs
                )
            return "No clinical notes available for this patient."
        except (SQLAlchemyError, OperationalError) as exc:
            logger.warning("Raw note retrieval failed: %s", exc)
            return "No clinical notes available for this patient."

    def _get_all_notes_context(
        self,
        patient_id: str,
        rag_service: GraphAugmentedRAGService,
        max_chars: int = 180_000,
    ) -> str:
        """Get ALL clinical notes for a patient (C6 long-context condition).

        Retrieves every document for the patient, sorted chronologically,
        concatenated up to max_chars. This simulates the "dump everything into
        a 200K context window" approach.
        """
        try:
            from sqlalchemy import select
            from app.models.document import Document

            stmt = (
                select(Document)
                .where(Document.patient_id == patient_id)
                .order_by(Document.note_date.asc().nulls_last(), Document.created_at.asc())
            )
            result = rag_service._session.execute(stmt)
            docs = list(result.scalars().all())

            if not docs:
                return "No clinical notes available for this patient."

            parts = []
            total_chars = 0
            for i, doc in enumerate(docs):
                text = doc.text or ""
                note_type = doc.note_type or "Unknown"
                note_date = str(doc.note_date) if doc.note_date else "Unknown date"
                header = f"--- Note {i+1}/{len(docs)} | {note_type} | {note_date} ---"
                entry = f"{header}\n{text}"

                if total_chars + len(entry) > max_chars:
                    # Truncate last note to fit
                    remaining = max_chars - total_chars
                    if remaining > 200:
                        parts.append(f"{header}\n{text[:remaining]}...[TRUNCATED]")
                        omitted = len(docs) - i - 1
                    else:
                        omitted = len(docs) - i
                    if omitted > 0:
                        parts.append(f"\n[{omitted} additional notes omitted due to context limit]")
                    break

                parts.append(entry)
                total_chars += len(entry)

            return "\n\n".join(parts)

        except (SQLAlchemyError, OperationalError) as exc:
            logger.warning("All-notes retrieval failed for %s: %s", patient_id, exc)
            return "No clinical notes available for this patient."

    def _get_deterministic_kg_answer(
        self,
        patient_id: str,
        question: QAQuestion,
        rag_service: GraphAugmentedRAGService,
    ) -> str:
        """Generate a deterministic answer from KG data only (C7 — no LLM).

        Queries the knowledge graph for relevant edges and formats a structured
        answer from raw facts. No language model reasoning.
        """
        try:
            # Retrieve KG context with full assertion + temporal
            context = rag_service.retrieve_context(
                query=question.question,
                patient_id=patient_id,
                max_hops=2,
                max_paths=15,
                assertion_mode="full",
                temporal_mode="full_bitemporal",
                retrieval_mode="graph_plus_doc",
            )

            # Format as structured facts (no prose)
            facts = []
            for path in context.graph_paths:
                for edge in path.edges:
                    assertion = ""
                    if hasattr(edge, "assertion") and edge.assertion:
                        assertion = f" [{edge.assertion}]"
                    temporality = ""
                    if hasattr(edge, "temporality") and edge.temporality:
                        temporality = f" ({edge.temporality})"
                    facts.append(
                        f"{edge.source_label} --{edge.edge_type}--> "
                        f"{edge.target_label}{assertion}{temporality}"
                    )

            if not facts:
                return "No relevant knowledge graph edges found for this patient."

            # Return raw facts — the scorer will check if they match expected answer
            return "KG Facts:\n" + "\n".join(facts[:30])

        except (SQLAlchemyError, OperationalError, ValueError) as exc:
            logger.warning("Deterministic KG query failed for %s: %s", patient_id, exc)
            return "No relevant knowledge graph data found."

    def _get_calculator_context(
        self,
        patient_id: str,
        question: str,
    ) -> str:
        """Get calculator results for C5 condition.

        Identifies applicable calculators from the question context,
        runs them against patient KG data, and returns formatted results.
        """
        try:
            from app.services.calculator_reasoning_service import CalculatorReasoningService

            calc_service = CalculatorReasoningService()
            applicable = calc_service.identify_applicable_calculators(
                conditions=[],
                measurements=[],
                clinical_question=question,
            )

            if not applicable:
                return ""

            results = []
            for calc_type in applicable[:3]:  # Limit to 3 calculators per question
                try:
                    calc_result = calc_service.calculate_for_patient(
                        patient_id=patient_id,
                        calculator_type=calc_type,
                    )
                    if calc_result and calc_result.get("score") is not None:
                        name = calc_result.get("calculator_name", calc_type)
                        score = calc_result["score"]
                        interpretation = calc_result.get("interpretation", "")
                        results.append(f"{name}: {score} — {interpretation}")
                except Exception:
                    continue

            return "\n".join(results) if results else ""
        except Exception as exc:
            logger.debug("Calculator context failed: %s", exc)
            return ""

    async def _score_with_llm_judge(
        self,
        question: QAQuestion,
        predicted_answer: str,
        config: QARunConfig,
    ) -> QAResult:
        """Score using LLM judge (delegates to llm_judge module)."""
        try:
            from app.services.llm_judge import LLMJudge

            judge = LLMJudge()
            verdict = await judge.score(
                question=question.question,
                expected_answer=question.expected_answer,
                predicted_answer=predicted_answer,
                category=question.category,
                scoring_rubric=question.scoring_rubric,
            )
            return QAResult(
                question_id=question.question_id,
                predicted_answer=predicted_answer,
                expected_answer=question.expected_answer,
                correct=verdict.overall_correct,
                score=verdict.overall_score,
                category=question.category,
                condition=config.condition,
                reasoning_trace=verdict.reasoning,
            )
        except Exception as exc:
            logger.warning("LLM judge failed, falling back to keyword: %s", exc)
            return self.qa_service.score_answer(
                question, predicted_answer, config.condition,
            )

    async def run_question_set(
        self,
        questions: list[QAQuestion],
        config: QARunConfig,
        experiment_name: str,
        run_id: str | None = None,
        checkpoint_path: str | None = None,
    ) -> QAEvaluationReport:
        """Run a full question set through GraphRAG + LLM.

        Args:
            questions: Questions to evaluate.
            config: QA run configuration.
            experiment_name: Name for the report.
            run_id: Optional research run ID for metric recording.
            checkpoint_path: Optional JSONL file for per-question checkpointing.
                If set, completed questions are skipped on resume.

        Returns:
            QAEvaluationReport with per-question results.
        """
        # Load checkpoint for resume
        checkpoint: dict[str, dict] = {}
        if checkpoint_path:
            checkpoint = _load_checkpoint(checkpoint_path, config.condition)
            if checkpoint:
                logger.info(
                    "Resuming %s: %d questions already checkpointed",
                    config.condition, len(checkpoint),
                )

        engine = get_sync_engine()
        session = Session(engine)
        rag_service = GraphAugmentedRAGService(session)

        results: list[QAResult] = []
        try:
            for i, question in enumerate(questions):
                # Check if already completed in checkpoint
                cached = checkpoint.get(question.question_id)
                if cached and not cached.get("error"):
                    result = QAResult(
                        question_id=cached["question_id"],
                        predicted_answer=cached.get("predicted_answer", ""),
                        expected_answer=cached.get("expected_answer", ""),
                        correct=cached.get("correct", False),
                        score=cached.get("score", 0.0),
                        category=cached.get("category", question.category),
                        condition=config.condition,
                        latency_ms=cached.get("latency_ms", 0.0),
                    )
                    results.append(result)
                    continue

                logger.info(
                    "QA [%s/%s] %s | %s | %s",
                    i + 1, len(questions),
                    config.condition,
                    question.category,
                    question.question_id,
                )
                result = await self._ask_question(question, config, rag_service)
                results.append(result)

                # If error occurred, reset session to prevent cascade
                if result.error:
                    try:
                        session.close()
                    except Exception:
                        pass
                    session = Session(engine)
                    rag_service = GraphAugmentedRAGService(session)

                # Save to checkpoint
                if checkpoint_path:
                    _append_checkpoint(checkpoint_path, {
                        "condition": config.condition,
                        "question_id": result.question_id,
                        "predicted_answer": result.predicted_answer[:500],
                        "expected_answer": result.expected_answer[:500],
                        "correct": result.correct,
                        "score": result.score,
                        "category": result.category,
                        "latency_ms": result.latency_ms,
                        "error": result.error,
                        "random_seed": config.random_seed,
                    })
        finally:
            try:
                session.close()
            except Exception:
                pass

        # Build aggregate report
        total = len(results)
        correct = sum(1 for r in results if r.correct)
        accuracy = correct / total if total > 0 else 0.0

        category_correct: dict[str, int] = {}
        category_total: dict[str, int] = {}
        for r in results:
            category_total[r.category] = category_total.get(r.category, 0) + 1
            if r.correct:
                category_correct[r.category] = category_correct.get(r.category, 0) + 1

        category_accuracies = {
            cat: category_correct.get(cat, 0) / category_total[cat]
            for cat in category_total
        }

        avg_latency = (
            sum(r.latency_ms for r in results) / total if total > 0 else 0.0
        )

        report = QAEvaluationReport(
            experiment_name=experiment_name,
            condition=config.condition,
            total_questions=total,
            correct=correct,
            accuracy=accuracy,
            category_accuracies=category_accuracies,
            avg_latency_ms=avg_latency,
            results=results,
        )

        # Record metrics to research service if run_id provided
        if run_id:
            self._record_report_metrics(run_id, report, config)

        return report

    def _record_report_metrics(
        self,
        run_id: str,
        report: QAEvaluationReport,
        config: QARunConfig,
    ) -> None:
        """Record QA evaluation metrics to the research service."""
        svc = self.research_service

        # Overall accuracy
        svc.record_metric(
            run_id, "rag", "qa_accuracy", report.accuracy,
            detail={
                "condition": config.condition,
                "assertion_mode": config.assertion_mode,
                "temporal_mode": config.temporal_mode,
                "retrieval_mode": config.retrieval_mode,
                "total_questions": report.total_questions,
                "correct": report.correct,
            },
        )

        # Per-category accuracy
        for cat, acc in report.category_accuracies.items():
            svc.record_metric(
                run_id, "rag", f"qa_accuracy_{cat}", acc,
                detail={"category": cat, "condition": config.condition},
            )

        # Clinical safety score
        safety_score = self.qa_service.compute_clinical_safety_score(report.results)
        svc.record_metric(
            run_id, "rag", "clinical_safety_score", safety_score,
            detail={"condition": config.condition},
        )

        # Latency
        svc.record_metric(
            run_id, "rag", "avg_qa_latency_ms", report.avg_latency_ms,
        )

        # Error count
        errors = sum(1 for r in report.results if r.error)
        svc.record_metric(run_id, "rag", "qa_errors", float(errors))

    # ========================================================================
    # Convenience methods for each experiment
    # ========================================================================

    async def run_assertion_ablation(
        self,
        patient_id: str,
        run_id: str | None = None,
        llm_provider: str = "anthropic",
        llm_model: str = "claude-sonnet-4-5-20250929",
    ) -> dict[str, QAEvaluationReport]:
        """Run Experiment 2: Assertion ablation across all 3 conditions.

        Returns dict mapping condition name to evaluation report.
        """
        conditions = {
            "no_assertion": "none",
            "assertion_extracted_only": "extracted_only",
            "full_epistemic": "full",
        }

        reports = {}
        for condition, assertion_mode in conditions.items():
            config = QARunConfig(
                patient_id=patient_id,
                condition=condition,
                assertion_mode=assertion_mode,
                llm_provider=llm_provider,
                llm_model=llm_model,
            )
            report = await self.run_question_set(
                questions=ASSERTION_QUESTIONS,
                config=config,
                experiment_name=f"Exp2: Assertion Ablation ({condition})",
                run_id=run_id,
            )
            reports[condition] = report
            logger.info(
                "Exp2 [%s]: accuracy=%.1f%%, safety=%.3f",
                condition,
                report.accuracy * 100,
                self.qa_service.compute_clinical_safety_score(report.results),
            )

        return reports

    async def run_temporal_ablation(
        self,
        patient_id: str,
        run_id: str | None = None,
        llm_provider: str = "anthropic",
        llm_model: str = "claude-sonnet-4-5-20250929",
    ) -> dict[str, QAEvaluationReport]:
        """Run Experiment 3: Temporal ablation across all 3 conditions."""
        conditions = {
            "no_temporal": "no_temporal",
            "timestamps_only": "timestamps_only",
            "full_bitemporal": "full_bitemporal",
        }

        reports = {}
        for condition, temporal_mode in conditions.items():
            config = QARunConfig(
                patient_id=patient_id,
                condition=condition,
                temporal_mode=temporal_mode,
                llm_provider=llm_provider,
                llm_model=llm_model,
            )
            report = await self.run_question_set(
                questions=TEMPORAL_QUESTIONS,
                config=config,
                experiment_name=f"Exp3: Temporal Ablation ({condition})",
                run_id=run_id,
            )
            reports[condition] = report
            logger.info(
                "Exp3 [%s]: accuracy=%.1f%%", condition, report.accuracy * 100,
            )

        return reports

    async def run_graphrag_comparison(
        self,
        patient_id: str,
        run_id: str | None = None,
        llm_provider: str = "anthropic",
        llm_model: str = "claude-sonnet-4-5-20250929",
    ) -> dict[str, QAEvaluationReport]:
        """Run Experiment 4: Graph-RAG vs Document-RAG across 4 conditions."""
        conditions = {
            "doc_only": "doc_only",
            "graph_only": "graph_only",
            "graph_plus_doc": "graph_plus_doc",
            "graph_plus_doc_plus_guidelines": "graph_plus_doc_plus_guidelines",
        }

        reports = {}
        for condition, retrieval_mode in conditions.items():
            config = QARunConfig(
                patient_id=patient_id,
                condition=condition,
                retrieval_mode=retrieval_mode,
                llm_provider=llm_provider,
                llm_model=llm_model,
            )
            report = await self.run_question_set(
                questions=RAG_QUESTIONS,
                config=config,
                experiment_name=f"Exp4: GraphRAG Comparison ({condition})",
                run_id=run_id,
            )
            reports[condition] = report
            logger.info(
                "Exp4 [%s]: accuracy=%.1f%%", condition, report.accuracy * 100,
            )

        return reports

    async def run_all_qa_experiments(
        self,
        patient_id: str,
        llm_provider: str = "anthropic",
        llm_model: str = "claude-sonnet-4-5-20250929",
    ) -> dict[str, dict[str, QAEvaluationReport]]:
        """Run all QA experiments (2, 3, 4) for a patient.

        Returns nested dict: {experiment: {condition: report}}.
        """
        logger.info("=" * 60)
        logger.info("Running all QA experiments for patient %s (model=%s)", patient_id, llm_model)
        logger.info("=" * 60)

        results = {}

        logger.info("--- Experiment 2: Assertion Ablation ---")
        results["exp2_assertion"] = await self.run_assertion_ablation(
            patient_id, llm_provider=llm_provider, llm_model=llm_model,
        )

        logger.info("--- Experiment 3: Temporal Ablation ---")
        results["exp3_temporal"] = await self.run_temporal_ablation(
            patient_id, llm_provider=llm_provider, llm_model=llm_model,
        )

        logger.info("--- Experiment 4: GraphRAG Comparison ---")
        results["exp4_graphrag"] = await self.run_graphrag_comparison(
            patient_id, llm_provider=llm_provider, llm_model=llm_model,
        )

        # Print summary
        logger.info("=" * 60)
        logger.info("QA EXPERIMENT SUMMARY")
        logger.info("=" * 60)
        for exp_name, reports in results.items():
            for condition, report in reports.items():
                safety = self.qa_service.compute_clinical_safety_score(report.results)
                logger.info(
                    "  %s | %s: accuracy=%.1f%% safety=%.3f (%d/%d correct)",
                    exp_name, condition,
                    report.accuracy * 100, safety,
                    report.correct, report.total_questions,
                )

        return results


def print_ablation_table(reports: dict[str, QAEvaluationReport]) -> str:
    """Format ablation results as a markdown table for paper/logging."""
    lines = [
        "| Condition | Overall Acc | " +
        " | ".join(sorted({cat for r in reports.values() for cat in r.category_accuracies})) +
        " | Safety |",
        "|---|---|" +
        "|".join("---" for _ in sorted({cat for r in reports.values() for cat in r.category_accuracies})) +
        "|---|",
    ]

    qa_svc = QAEvaluationService()
    all_cats = sorted({cat for r in reports.values() for cat in r.category_accuracies})

    for condition, report in reports.items():
        safety = qa_svc.compute_clinical_safety_score(report.results)
        cat_values = " | ".join(
            f"{report.category_accuracies.get(cat, 0.0):.1%}" for cat in all_cats
        )
        lines.append(
            f"| {condition} | {report.accuracy:.1%} | {cat_values} | {safety:.3f} |"
        )

    return "\n".join(lines)
