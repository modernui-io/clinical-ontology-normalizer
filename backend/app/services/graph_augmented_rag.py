"""Graph-Augmented RAG Service.

Enhances retrieval-augmented generation with knowledge graph traversal.
Combines document retrieval with graph paths for richer LLM context.

Architecture:
1. Extract concepts from query via NLP + OMOP lookup + label fallback
2. Traverse patient KG to find relevant paths (2-3 hops, bidirectional)
3. Query temporal context for time-aware evidence (batch-optimized)
4. Retrieve applicable clinical guidelines via GuidelineRAGService
5. Serialize graph paths as structured context
6. Combine with document retrieval for comprehensive context

Supports both sync and async SQLAlchemy sessions.
"""
# MODULE: graph_rag
# MATURITY: pilot

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Union
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.knowledge_graph import KGEdge, KGNode
from app.schemas.knowledge_graph import EdgeType, NodeType

from app.services.section_parser import ClinicalSection, SectionSpan, get_section_parser

from app.services.kg_cache_service import (
    invalidate_traversal_cache,
    traversal_cache_get as _traversal_cache_get,
    traversal_cache_key as _traversal_cache_key,
    traversal_cache_put as _traversal_cache_put,
)

logger = logging.getLogger(__name__)

# Per-document content limit for RAG context (chars)
# Section-aware extraction makes this budget more efficient than blind truncation
MAX_DOC_CONTENT_CHARS = 6000
# Max documents to include in LLM prompt
MAX_RETRIEVED_DOCS = 2

# Minimum edge confidence for traversal inclusion (Step 4)
MIN_TRAVERSAL_CONFIDENCE = 0.3

# Causal language patterns that trigger causal reasoning integration
_CAUSAL_PATTERNS = re.compile(
    r"\b(caused?\s+by|leads?\s+to|side\s+effects?|adverse\s+effects?|"
    r"treatment\s+for|treats?|exacerbat|complicat|progression|"
    r"contraindic|result(?:s|ed|ing)?\s+in)\b",
    re.IGNORECASE,
)

# Map NLP EntityType values to OMOP domain hints for concept lookup
_ENTITY_TYPE_TO_DOMAIN: dict[str, str] = {
    "diagnosis": "Condition",
    "medication": "Drug",
    "procedure": "Procedure",
    "lab_result": "Measurement",
    "vital_sign": "Measurement",
    "symptom": "Condition",
    "allergy": "Observation",
}

# Map NLP EntityType values to preferred KGEdge types for traversal scoring
_ENTITY_TYPE_TO_PREFERRED_EDGES: dict[str, set[str]] = {
    "diagnosis": {EdgeType.HAS_CONDITION.value, EdgeType.CONDITION_TREATED_BY.value, EdgeType.SYMPTOM_OF.value},
    "medication": {EdgeType.TAKES_DRUG.value, EdgeType.DRUG_TREATS.value, EdgeType.DRUG_INTERACTION.value},
    "lab_result": {EdgeType.HAS_MEASUREMENT.value, EdgeType.MONITORS.value},
    "vital_sign": {EdgeType.HAS_MEASUREMENT.value, EdgeType.MONITORS.value},
    "procedure": {EdgeType.HAS_PROCEDURE.value},
    "symptom": {EdgeType.HAS_CONDITION.value, EdgeType.SYMPTOM_OF.value},
}

# Domain → relevant clinical sections, ordered by priority
DOMAIN_SECTION_MAP: dict[str, list[ClinicalSection]] = {
    "medication_reconciliation": [
        ClinicalSection.DISCHARGE_MEDICATIONS,
        ClinicalSection.HOME_MEDICATIONS,
        ClinicalSection.MEDICATIONS,
        ClinicalSection.ALLERGIES,
    ],
    "problem_list": [
        ClinicalSection.DISCHARGE_DIAGNOSIS,
        ClinicalSection.DIAGNOSIS,
        ClinicalSection.ASSESSMENT_PLAN,
        ClinicalSection.ASSESSMENT,
        ClinicalSection.PAST_MEDICAL_HISTORY,
        ClinicalSection.HPI,
    ],
    "family_history": [
        ClinicalSection.FAMILY_HISTORY,
        ClinicalSection.SOCIAL_HISTORY,
    ],
    "temporal_reasoning": [
        ClinicalSection.HOSPITAL_COURSE,
        ClinicalSection.HPI,
        ClinicalSection.ASSESSMENT_PLAN,
        ClinicalSection.PROCEDURES,
    ],
    "risk_assessment": [
        ClinicalSection.PAST_MEDICAL_HISTORY,
        ClinicalSection.ASSESSMENT_PLAN,
        ClinicalSection.HOSPITAL_COURSE,
        ClinicalSection.FAMILY_HISTORY,
        ClinicalSection.SOCIAL_HISTORY,
        ClinicalSection.LABS,
    ],
}

# Fallback sections when domain is unknown or no sections match
DEFAULT_SECTIONS = [
    ClinicalSection.ASSESSMENT_PLAN,
    ClinicalSection.HOSPITAL_COURSE,
    ClinicalSection.HPI,
    ClinicalSection.DISCHARGE_DIAGNOSIS,
]


def extract_relevant_sections(
    text: str,
    domain: str | None = None,
    budget: int = MAX_DOC_CONTENT_CHARS,
) -> str:
    """Extract the most relevant sections from a clinical note for a given domain.

    Uses SectionParser to identify section boundaries, then selects sections
    by domain priority until the character budget is filled.

    If no sections are found (unstructured note), falls back to first `budget` chars.
    """
    parser = get_section_parser()
    spans = parser.parse(text)

    if not spans:
        return text[:budget]

    priority_sections = DOMAIN_SECTION_MAP.get(domain, DEFAULT_SECTIONS) if domain else DEFAULT_SECTIONS

    # Build section text map: ClinicalSection → text content
    section_texts: dict[ClinicalSection, str] = {}
    for span in spans:
        section_text = text[span.start:span.end].strip()
        if section_text:
            section_texts[span.section] = section_text

    collected: list[str] = []
    chars_used = 0

    # Phase 1: Priority sections for this domain
    for section in priority_sections:
        if section in section_texts and chars_used < budget:
            chunk = section_texts.pop(section)
            remaining = budget - chars_used
            if len(chunk) > remaining:
                chunk = chunk[:remaining]
            collected.append(chunk)
            chars_used += len(chunk)

    # Phase 2: Fill remaining budget with other sections (by document order)
    if chars_used < budget:
        for span in spans:
            if span.section in section_texts and chars_used < budget:
                chunk = section_texts.pop(span.section)
                remaining = budget - chars_used
                if len(chunk) > remaining:
                    chunk = chunk[:remaining]
                collected.append(chunk)
                chars_used += len(chunk)

    return "\n\n".join(collected) if collected else text[:budget]


@dataclass
class QueryConcept:
    """A concept extracted from a user query with optional OMOP resolution."""

    text: str
    entity_type: str | None = None  # e.g. "diagnosis", "medication"
    omop_concept_id: int | None = None
    confidence: float = 1.0


@dataclass
class GraphPath:
    """A traversal path through the knowledge graph."""

    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    path_type: str  # "condition_treatment", "temporal_sequence", "comorbidity"
    confidence: float = 1.0

    def to_prompt_format(self, assertion_mode: str = "full") -> str:
        """Format path for LLM prompt.

        Args:
            assertion_mode: "full" | "extracted_only" | "none".
                When "none", assertion labels are omitted from the prompt.
        """
        if not self.nodes or len(self.nodes) < 2:
            return ""

        parts = []
        for i, node in enumerate(self.nodes):
            node_str = node.get("label", "?")
            parts.append(node_str)

            if i < len(self.edges):
                edge = self.edges[i]
                edge_type = edge.get("edge_type", "relates_to")
                confidence = edge.get("confidence", 1.0)
                temporal = ""
                if edge.get("temporality"):
                    temporal = f", {edge['temporality']}"
                assertion_str = ""
                if assertion_mode != "none":
                    assertion = edge.get("assertion", "present")
                    if assertion != "present":
                        assertion_str = f", {assertion.upper()}"
                parts.append(f" --[{edge_type} (conf: {confidence:.2f}{temporal}{assertion_str})]--> ")

        return "".join(parts)


@dataclass
class TemporalContext:
    """Temporal context extracted from the graph."""

    event_timeline: list[dict[str, Any]]  # Events in chronological order
    temporal_conflicts: list[str]  # Any detected conflicts
    current_state: dict[str, Any]  # What's true now
    historical_state: dict[str, Any]  # What was true in the past


class SourceRetrievalStatus:
    """Status constants for document source retrieval (P1-011)."""

    FULL = "full"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


@dataclass
class GraphAugmentedContext:
    """Context combining graph traversal with documents."""

    query: str
    patient_id: str
    graph_paths: list[GraphPath]
    temporal_context: TemporalContext | None
    retrieved_documents: list[dict[str, Any]]
    policy_constraints: list[dict[str, Any]]
    total_evidence_pieces: int = 0
    source_retrieval_status: str = field(default=SourceRetrievalStatus.UNAVAILABLE)

    def to_llm_prompt(self, assertion_mode: str = "full") -> str:
        """Format all context for LLM consumption.

        Args:
            assertion_mode: "full" | "extracted_only" | "none".
                Controls whether assertion labels appear in graph evidence
                and whether the Assertion Notes section is included.
        """
        sections = []

        # Assertion Notes Section FIRST (only in full or extracted_only mode)
        # Placed at the top so the model sees critical assertion status before evidence
        if assertion_mode != "none" and self.graph_paths:
            negated_findings = []
            uncertain_findings = []
            family_findings = []
            historical_findings = []
            for path in self.graph_paths:
                for idx, edge in enumerate(path.edges):
                    assertion = edge.get("assertion", "present")
                    # Use the target node (idx+1) for this edge, not just the last node
                    target_label = (
                        path.nodes[idx + 1].get("label", "?")
                        if idx + 1 < len(path.nodes)
                        else path.nodes[-1].get("label", "?") if path.nodes else "?"
                    )
                    experiencer = edge.get("experiencer", "patient")
                    if experiencer == "family" or assertion == "family_history":
                        family_findings.append(target_label)
                    elif assertion == "absent":
                        negated_findings.append(target_label)
                    elif assertion == "possible":
                        uncertain_findings.append(target_label)
                    elif assertion == "historical":
                        historical_findings.append(target_label)

            if negated_findings or uncertain_findings or family_findings or historical_findings:
                sections.append("=== IMPORTANT: Clinical Assertion Status ===")
                sections.append("The following findings have NON-PRESENT assertion status.")
                sections.append("You MUST use this information when answering.")
                if negated_findings:
                    sections.append(
                        f">>> NEGATED (patient does NOT have): {', '.join(set(negated_findings))}"
                    )
                if uncertain_findings:
                    sections.append(
                        f">>> UNCERTAIN (suspected, NOT confirmed): {', '.join(set(uncertain_findings))}"
                    )
                if family_findings:
                    sections.append(
                        f">>> FAMILY HISTORY ONLY (relative's condition, NOT patient's): "
                        f"{', '.join(set(family_findings))}"
                    )
                if historical_findings:
                    sections.append(
                        f">>> HISTORICAL (past/resolved, NOT current): {', '.join(set(historical_findings))}"
                    )
                sections.append("")

        # Graph Evidence Section
        if self.graph_paths:
            sections.append("=== Graph Evidence ===")
            for i, path in enumerate(self.graph_paths, 1):
                path_str = path.to_prompt_format(assertion_mode=assertion_mode)
                if path_str:
                    sections.append(f"Path {i} ({path.path_type}): {path_str}")
            sections.append("")

        # Temporal Context Section
        if self.temporal_context:
            sections.append("=== Temporal Context ===")
            if self.temporal_context.current_state:
                sections.append("Current State:")
                for key, value in self.temporal_context.current_state.items():
                    sections.append(f"  - {key}: {value}")

            if self.temporal_context.event_timeline:
                sections.append("Timeline:")
                for event in self.temporal_context.event_timeline[:10]:
                    date_str = event.get("date", "unknown")
                    desc = event.get("description", "")
                    sections.append(f"  - {date_str}: {desc}")

            if self.temporal_context.temporal_conflicts:
                sections.append("Temporal Concerns:")
                for conflict in self.temporal_context.temporal_conflicts:
                    sections.append(f"  - {conflict}")
            sections.append("")

        # Policy Constraints Section
        if self.policy_constraints:
            sections.append("=== Applicable Policy Rules ===")
            for policy in self.policy_constraints[:5]:
                rule_id = policy.get("rule_id", "")
                description = policy.get("description", "")
                strength = policy.get("strength", "")
                sections.append(f"Rule {rule_id} ({strength}): {description}")
            sections.append("")

        # Retrieved Documents Section
        if self.retrieved_documents:
            sections.append("=== Retrieved Document Context ===")
            for doc in self.retrieved_documents[:MAX_RETRIEVED_DOCS]:
                source = doc.get("source", "document")
                content = doc.get("content", "")[:MAX_DOC_CONTENT_CHARS]
                sections.append(f"[{source}]: {content}")
            sections.append("")

        return "\n".join(sections)

    def to_llm_prompt_v5(self, question_text: str) -> str:
        """C4's proven evidence format + question-subject callout prepended.

        V5 strategy: minimal intervention.  Keep traversal-ordered evidence,
        assertion notes, temporal context and simple prompt from C4.  Only add
        a short callout identifying the finding the question asks about and its
        assertion status so the model doesn't have to hunt for it.

        Args:
            question_text: The question being asked (used for subject extraction).
        """
        # Build the question-subject callout (same extraction as v4)
        callout = self._question_subject_callout(question_text)

        # Reuse C4's proven evidence formatter (traversal-ordered, assertion notes)
        base = self.to_llm_prompt(assertion_mode="full")

        if callout:
            return callout + "\n" + base
        return base

    def _question_subject_callout(self, question_text: str) -> str:
        """Return a short callout identifying the question-relevant finding."""
        if not self.graph_paths:
            return ""

        q_lower = question_text.lower()
        best_match_len = 0
        matched_label: str | None = None
        matched_assertion: str | None = None
        matched_experiencer: str | None = None

        for path in self.graph_paths:
            for idx, edge in enumerate(path.edges):
                target_label = (
                    path.nodes[idx + 1].get("label", "")
                    if idx + 1 < len(path.nodes)
                    else path.nodes[-1].get("label", "") if path.nodes else ""
                )
                if target_label and target_label.lower() in q_lower:
                    if len(target_label) > best_match_len:
                        best_match_len = len(target_label)
                        matched_label = target_label
                        matched_assertion = edge.get("assertion", "present")
                        matched_experiencer = edge.get("experiencer", "patient")

        if not matched_label:
            return ""

        lines = ["=== FINDING RELEVANT TO YOUR QUESTION ==="]
        lines.append(f"The question asks about: {matched_label}")

        if matched_experiencer == "family" or matched_assertion == "family_history":
            lines.append(
                "Clinical status: FAMILY HISTORY — this is a RELATIVE's condition, NOT the patient's own"
            )
        elif matched_assertion == "absent":
            lines.append(
                "Clinical status: NEGATED — the patient does NOT have this condition"
            )
        elif matched_assertion == "possible":
            lines.append(
                "Clinical status: UNCERTAIN — suspected but NOT confirmed"
            )
        elif matched_assertion == "historical":
            lines.append(
                "Clinical status: HISTORICAL/RESOLVED — the patient HAD this in the past but it is no longer active"
            )
        elif matched_assertion in ("hypothetical", "conditional"):
            lines.append(
                "Clinical status: CONDITIONAL — this depends on specific circumstances"
            )
        else:
            lines.append(
                "Clinical status: CURRENT/ACTIVE — the patient currently has this"
            )
        lines.append("")
        return "\n".join(lines)

    def to_llm_prompt_v4(self, question_text: str, assertion_mode: str = "full_v4") -> str:
        """Format context with question-subject extraction and assertion-grouped evidence.

        V4 strategy: highlight the question-relevant finding's assertion status upfront,
        group evidence by assertion type, and preserve the Assertion Notes section that
        drives high negation accuracy.

        Args:
            question_text: The question being asked (used for subject extraction).
            assertion_mode: Assertion mode (should be "full_v4").
        """
        sections: list[str] = []

        # ------------------------------------------------------------------
        # 1. Question-subject extraction: match question against node labels
        # ------------------------------------------------------------------
        matched_label: str | None = None
        matched_assertion: str | None = None
        matched_experiencer: str | None = None

        if self.graph_paths:
            q_lower = question_text.lower()
            best_match_len = 0
            for path in self.graph_paths:
                for idx, edge in enumerate(path.edges):
                    target_label = (
                        path.nodes[idx + 1].get("label", "")
                        if idx + 1 < len(path.nodes)
                        else path.nodes[-1].get("label", "") if path.nodes else ""
                    )
                    if target_label and target_label.lower() in q_lower:
                        if len(target_label) > best_match_len:
                            best_match_len = len(target_label)
                            matched_label = target_label
                            matched_assertion = edge.get("assertion", "present")
                            matched_experiencer = edge.get(
                                "experiencer",
                                edge.get("experiencer", "patient"),
                            )

            if matched_label:
                sections.append("=== FINDING RELEVANT TO YOUR QUESTION ===")
                sections.append(f"The question asks about: {matched_label}")

                if matched_experiencer == "family":
                    sections.append(
                        "Clinical status: FAMILY HISTORY — this is a RELATIVE's condition, NOT the patient's own"
                    )
                elif matched_assertion == "absent":
                    sections.append(
                        "Clinical status: NEGATED — the patient does NOT have this condition"
                    )
                elif matched_assertion == "possible":
                    sections.append(
                        "Clinical status: UNCERTAIN — suspected but NOT confirmed"
                    )
                elif matched_assertion == "historical":
                    sections.append(
                        "Clinical status: HISTORICAL/RESOLVED — the patient HAD this in the past but it is no longer active"
                    )
                elif matched_assertion == "family_history":
                    sections.append(
                        "Clinical status: FAMILY HISTORY — this is a RELATIVE's condition, NOT the patient's own"
                    )
                elif matched_assertion in ("hypothetical", "conditional"):
                    sections.append(
                        "Clinical status: CONDITIONAL — this depends on specific circumstances"
                    )
                else:
                    sections.append(
                        "Clinical status: CURRENT/ACTIVE — the patient currently has this"
                    )
                sections.append("")

        # ------------------------------------------------------------------
        # 2. Assertion Notes (preserved from v1 — drives 94.5% negation accuracy)
        # ------------------------------------------------------------------
        if self.graph_paths:
            negated_findings: list[str] = []
            uncertain_findings: list[str] = []
            family_findings: list[str] = []
            historical_findings: list[str] = []
            for path in self.graph_paths:
                for idx, edge in enumerate(path.edges):
                    assertion = edge.get("assertion", "present")
                    target_label = (
                        path.nodes[idx + 1].get("label", "?")
                        if idx + 1 < len(path.nodes)
                        else path.nodes[-1].get("label", "?") if path.nodes else "?"
                    )
                    experiencer = edge.get("experiencer", "patient")
                    if experiencer == "family" or assertion == "family_history":
                        family_findings.append(target_label)
                    elif assertion == "absent":
                        negated_findings.append(target_label)
                    elif assertion == "possible":
                        uncertain_findings.append(target_label)
                    elif assertion == "historical":
                        historical_findings.append(target_label)

            if negated_findings or uncertain_findings or family_findings or historical_findings:
                sections.append("=== IMPORTANT: Clinical Assertion Status ===")
                sections.append("The following findings have NON-PRESENT assertion status.")
                sections.append("You MUST use this information when answering.")
                if negated_findings:
                    sections.append(
                        f">>> NEGATED (patient does NOT have): {', '.join(set(negated_findings))}"
                    )
                if uncertain_findings:
                    sections.append(
                        f">>> UNCERTAIN (suspected, NOT confirmed): {', '.join(set(uncertain_findings))}"
                    )
                if family_findings:
                    sections.append(
                        f">>> FAMILY HISTORY ONLY (relative's condition, NOT patient's): "
                        f"{', '.join(set(family_findings))}"
                    )
                if historical_findings:
                    sections.append(
                        f">>> HISTORICAL (past/resolved, NOT current): {', '.join(set(historical_findings))}"
                    )
                sections.append("")

        # ------------------------------------------------------------------
        # 3. Evidence grouped by assertion status
        # ------------------------------------------------------------------
        if self.graph_paths:
            # Categorize edges by assertion
            groups: dict[str, list[str]] = {
                "CURRENT": [],
                "HISTORICAL": [],
                "NEGATED": [],
                "UNCERTAIN": [],
                "FAMILY": [],
                "OTHER": [],
            }
            row = 0
            for path in self.graph_paths:
                for idx, edge in enumerate(path.edges):
                    if idx + 1 >= len(path.nodes):
                        continue
                    src = path.nodes[idx].get("label", "?")
                    tgt = path.nodes[idx + 1].get("label", "?")
                    edge_type = edge.get("edge_type", "relates_to")
                    conf = edge.get("confidence", 1.0)
                    assertion = edge.get("assertion", "present")
                    experiencer = edge.get("experiencer", "patient")
                    row += 1

                    line = f"  {row}. {src} --[{edge_type}]--> {tgt} (conf: {conf:.2f})"

                    if experiencer == "family" or assertion == "family_history":
                        groups["FAMILY"].append(line)
                    elif assertion == "absent":
                        groups["NEGATED"].append(line)
                    elif assertion == "possible":
                        groups["UNCERTAIN"].append(line)
                    elif assertion == "historical":
                        groups["HISTORICAL"].append(line)
                    elif assertion in ("hypothetical", "conditional"):
                        groups["OTHER"].append(line)
                    else:
                        groups["CURRENT"].append(line)

            # Emit groups in priority order: current first, then historical
            group_labels = [
                ("CURRENT", "=== CURRENT CLINICAL FINDINGS (active) ==="),
                ("HISTORICAL", "=== HISTORICAL FINDINGS (past/resolved, NOT current) ==="),
                ("NEGATED", "=== NEGATED FINDINGS (patient does NOT have) ==="),
                ("UNCERTAIN", "=== UNCERTAIN FINDINGS (suspected, not confirmed) ==="),
                ("FAMILY", "=== FAMILY HISTORY (relative's condition, NOT patient's) ==="),
                ("OTHER", "=== OTHER FINDINGS ==="),
            ]
            for key, header in group_labels:
                if groups[key]:
                    sections.append(header)
                    sections.extend(groups[key])
            sections.append("")

        # ------------------------------------------------------------------
        # 4. Temporal Context (unchanged from v1)
        # ------------------------------------------------------------------
        if self.temporal_context:
            sections.append("=== Temporal Context ===")
            if self.temporal_context.current_state:
                sections.append("Current State:")
                for key, value in self.temporal_context.current_state.items():
                    sections.append(f"  - {key}: {value}")
            if self.temporal_context.event_timeline:
                sections.append("Timeline:")
                for event in self.temporal_context.event_timeline[:10]:
                    date_str = event.get("date", "unknown")
                    desc = event.get("description", "")
                    sections.append(f"  - {date_str}: {desc}")
            if self.temporal_context.temporal_conflicts:
                sections.append("Temporal Concerns:")
                for conflict in self.temporal_context.temporal_conflicts:
                    sections.append(f"  - {conflict}")
            sections.append("")

        # ------------------------------------------------------------------
        # 5. Retrieved Documents (unchanged from v1)
        # ------------------------------------------------------------------
        if self.retrieved_documents:
            sections.append("=== Retrieved Document Context ===")
            for doc in self.retrieved_documents[:MAX_RETRIEVED_DOCS]:
                source = doc.get("source", "document")
                content = doc.get("content", "")[:MAX_DOC_CONTENT_CHARS]
                sections.append(f"[{source}]: {content}")
            sections.append("")

        return "\n".join(sections)

    def to_structured_llm_prompt(self, assertion_mode: str = "full") -> str:
        """Format context with visually distinct structured sections.

        Uses box-drawing characters and tables so the LLM treats
        structured KG data as authoritative, distinct from raw documents.
        """
        sections: list[str] = []

        # 1. Authoritative Clinical Status (assertion table)
        if assertion_mode != "none" and self.graph_paths:
            negated: set[str] = set()
            uncertain: set[str] = set()
            family: set[str] = set()
            historical: set[str] = set()

            for path in self.graph_paths:
                for idx, edge in enumerate(path.edges):
                    assertion = edge.get("assertion", "present")
                    target_label = (
                        path.nodes[idx + 1].get("label", "?")
                        if idx + 1 < len(path.nodes)
                        else path.nodes[-1].get("label", "?") if path.nodes else "?"
                    )
                    experiencer = edge.get("experiencer", "patient")
                    if experiencer == "family" or assertion == "family_history":
                        family.add(target_label)
                    elif assertion == "absent":
                        negated.add(target_label)
                    elif assertion == "possible":
                        uncertain.add(target_label)
                    elif assertion == "historical":
                        historical.add(target_label)

            if negated or uncertain or family or historical:
                lines = [
                    "╔══ AUTHORITATIVE CLINICAL STATUS (from structured medical record) ══╗",
                ]
                if negated:
                    lines.append(f"║ RULED OUT:    {', '.join(sorted(negated))}")
                if uncertain:
                    lines.append(f"║ UNCERTAIN:    {', '.join(sorted(uncertain))} (suspected, not confirmed)")
                if family:
                    lines.append(f"║ FAMILY ONLY:  {', '.join(sorted(family))} (relative, NOT patient)")
                if historical:
                    lines.append(f"║ RESOLVED:     {', '.join(sorted(historical))} (past, no longer active)")
                lines.append(
                    "╚═══════════════════════════════════════════════════════════════════════╝"
                )
                sections.append("\n".join(lines))
                sections.append("")

        # 2. Structured Clinical Relationships (graph paths as table)
        if self.graph_paths:
            rel_lines = ["=== STRUCTURED CLINICAL RELATIONSHIPS ==="]
            rel_lines.append("┌─────────────────────────────────────────────────────────────┐")
            row_num = 0
            for path in self.graph_paths:
                for idx, edge in enumerate(path.edges):
                    if idx + 1 >= len(path.nodes):
                        continue
                    src = path.nodes[idx].get("label", "?")
                    tgt = path.nodes[idx + 1].get("label", "?")
                    rel = edge.get("type", edge.get("relationship", "RELATED_TO"))
                    assertion = edge.get("assertion", "present")
                    conf = edge.get("confidence", "")
                    status = assertion.upper() if assertion != "present" else "ACTIVE"
                    conf_str = f", conf:{conf:.2f}" if isinstance(conf, (int, float)) else ""
                    row_num += 1
                    rel_lines.append(
                        f"│ {row_num}. {src} {rel} → {tgt} [{status}{conf_str}]"
                    )
            rel_lines.append("└─────────────────────────────────────────────────────────────┘")
            if row_num > 0:
                sections.append("\n".join(rel_lines))
                sections.append("")

        # 3. Patient Timeline (temporal context as table)
        if self.temporal_context:
            tl_lines = ["=== PATIENT TIMELINE (structured, verified dates) ==="]
            tl_lines.append("| Date       | Event                              | Status    |")
            tl_lines.append("|------------|-------------------------------------|-----------|")
            if self.temporal_context.event_timeline:
                for event in self.temporal_context.event_timeline[:15]:
                    date_str = str(event.get("date", "unknown"))[:10]
                    desc = str(event.get("description", ""))[:37]
                    status = str(event.get("status", event.get("assertion", "ACTIVE"))).upper()[:9]
                    tl_lines.append(f"| {date_str:<10} | {desc:<37} | {status:<9} |")

            if self.temporal_context.current_state:
                tl_lines.append("")
                tl_lines.append("Current clinical state:")
                for key, value in self.temporal_context.current_state.items():
                    tl_lines.append(f"  {key}: {value}")

            if self.temporal_context.temporal_conflicts:
                tl_lines.append("")
                tl_lines.append("Temporal concerns:")
                for conflict in self.temporal_context.temporal_conflicts:
                    tl_lines.append(f"  - {conflict}")

            sections.append("\n".join(tl_lines))
            sections.append("")

        # 4. Policy Constraints (if any)
        if self.policy_constraints:
            sections.append("=== Applicable Policy Rules ===")
            for policy in self.policy_constraints[:5]:
                rule_id = policy.get("rule_id", "")
                description = policy.get("description", "")
                strength = policy.get("strength", "")
                sections.append(f"Rule {rule_id} ({strength}): {description}")
            sections.append("")

        # 5. Supporting Documents (explicitly labelled as supplementary)
        if self.retrieved_documents:
            sections.append(
                "=== SUPPORTING DOCUMENTS (raw clinical notes — may contain ambiguity) ==="
            )
            for doc in self.retrieved_documents[:MAX_RETRIEVED_DOCS]:
                source = doc.get("source", "document")
                content = doc.get("content", "")[:MAX_DOC_CONTENT_CHARS]
                sections.append(f"[{source}]: {content}")
            sections.append("")

        return "\n".join(sections)


class GraphAugmentedRAGService:
    """Service for graph-augmented retrieval-augmented generation.

    Enhances LLM context with knowledge graph traversal paths
    and temporal reasoning for richer, more accurate responses.

    Supports both sync and async SQLAlchemy sessions.

    Usage (sync):
        service = GraphAugmentedRAGService(session)
        context = service.retrieve_context(
            query="What medications is this patient on for diabetes?",
            patient_id="P001",
        )
        llm_prompt = context.to_llm_prompt()

    Usage (async):
        service = GraphAugmentedRAGService(async_session)
        context = await service.retrieve_context_async(
            query="What medications is this patient on for diabetes?",
            patient_id="P001",
        )
        llm_prompt = context.to_llm_prompt()
    """

    def __init__(self, session: Union[Session, AsyncSession]) -> None:
        """Initialize the service.

        Args:
            session: SQLAlchemy database session (sync or async).
        """
        self._session = session
        self._is_async = isinstance(session, AsyncSession)

    async def retrieve_context_async(
        self,
        query: str,
        patient_id: str,
        max_hops: int = 3,
        max_paths: int = 10,
        include_temporal: bool = True,
        include_policies: bool = True,
        time_point: datetime | None = None,
        query_domain: str | None = None,
    ) -> GraphAugmentedContext:
        """Retrieve graph-augmented context for a query (async version).

        Args:
            query: The user's question or query.
            patient_id: Patient to query graph for.
            max_hops: Maximum hops in graph traversal.
            max_paths: Maximum paths to return.
            include_temporal: Include temporal context.
            include_policies: Include policy constraints.
            time_point: Optional time point for temporal queries.

        Returns:
            GraphAugmentedContext with paths, temporal info, and documents.
        """
        # Scale-safety: clamp unbounded parameters
        max_hops = min(max_hops, 10)
        max_paths = min(max_paths, 100)

        # Step 1: Extract concepts from query (NLP + quoted terms)
        query_concepts = self._extract_query_concepts(query)

        # Step 1 Tier 2: Enrich with OMOP concept IDs (async only)
        query_concepts = await self._enrich_concepts_with_omop_async(query_concepts)

        # Find relevant starting nodes in patient's graph
        start_nodes = await self._find_matching_nodes_async(patient_id, query_concepts)

        # Traverse graph from starting nodes
        graph_paths = await self._traverse_graph_async(
            patient_id=patient_id,
            start_nodes=start_nodes,
            query_concepts=query_concepts,
            max_hops=max_hops,
            max_paths=max_paths,
        )

        # Get temporal context if requested
        temporal_context = None
        if include_temporal:
            temporal_context = await self._get_temporal_context_async(
                patient_id=patient_id,
                time_point=time_point,
            )

        # Get applicable policy constraints if requested
        policy_constraints: list[dict[str, Any]] = []
        if include_policies:
            policy_constraints = await self._get_policy_constraints_async(
                patient_id=patient_id,
                query_concepts=query_concepts,
            )

        # P1-011: Real document retrieval with status tracking
        retrieved_documents, source_status = await self._retrieve_documents_async(
            query=query,
            patient_id=patient_id,
            query_concepts=query_concepts,
            query_domain=query_domain,
        )

        return GraphAugmentedContext(
            query=query,
            patient_id=patient_id,
            graph_paths=graph_paths,
            temporal_context=temporal_context,
            retrieved_documents=retrieved_documents,
            policy_constraints=policy_constraints,
            total_evidence_pieces=(
                len(graph_paths)
                + len(retrieved_documents)
                + len(policy_constraints)
            ),
            source_retrieval_status=source_status,
        )

    def retrieve_context(
        self,
        query: str,
        patient_id: str,
        max_hops: int = 3,
        max_paths: int = 10,
        include_temporal: bool = True,
        include_policies: bool = True,
        time_point: datetime | None = None,
        assertion_mode: str = "full",
        temporal_mode: str = "full_bitemporal",
        retrieval_mode: str = "graph_plus_doc",
        query_domain: str | None = None,
    ) -> GraphAugmentedContext:
        """Retrieve graph-augmented context for a query (sync version).

        Args:
            query: The user's question or query.
            patient_id: Patient to query graph for.
            max_hops: Maximum hops in graph traversal.
            max_paths: Maximum paths to return.
            include_temporal: Include temporal context.
            include_policies: Include policy constraints.
            time_point: Optional time point for temporal queries.
            assertion_mode: "full" | "extracted_only" | "none".
            temporal_mode: "full_bitemporal" | "timestamps_only" | "no_temporal".
            retrieval_mode: "doc_only" | "graph_only" | "graph_plus_doc" | "graph_plus_doc_plus_guidelines".

        Returns:
            GraphAugmentedContext with paths, temporal info, and documents.
        """
        # Scale-safety: clamp unbounded parameters
        max_hops = min(max_hops, 10)
        max_paths = min(max_paths, 100)

        # Step 1: Extract concepts from query (NLP + quoted terms)
        # Note: OMOP enrichment skipped in sync path (requires async DB)
        query_concepts = self._extract_query_concepts(query)

        # Find relevant starting nodes in patient's graph (skip for doc_only)
        # Each SQL-touching step is wrapped in try/except with rollback to
        # prevent InFailedSqlTransaction cascading between steps.
        start_nodes: list[Any] = []
        if retrieval_mode != "doc_only":
            try:
                start_nodes = self._find_matching_nodes(patient_id, query_concepts)
            except Exception as exc:
                logger.warning("_find_matching_nodes failed: %s", exc)
                try:
                    self._session.rollback()
                except Exception:
                    pass

        # Traverse graph from starting nodes (skip if doc_only mode)
        graph_paths: list[GraphPath] = []
        if retrieval_mode != "doc_only" and start_nodes:
            try:
                # Compute query-aware assertion hints for v2/v3 modes
                # NOTE: full_v4 intentionally excluded — uses fixed penalties like original "full"
                query_hints = (
                    _detect_query_assertion_focus(query)
                    if assertion_mode in ("full_v2", "full_v3")
                    else None
                )
                graph_paths = self._traverse_graph(
                    patient_id=patient_id,
                    start_nodes=start_nodes,
                    query_concepts=query_concepts,
                    max_hops=max_hops,
                    max_paths=max_paths,
                    assertion_mode=assertion_mode,
                    temporal_mode=temporal_mode,
                    query_hint_assertions=query_hints,
                )
            except Exception as exc:
                logger.warning("_traverse_graph failed: %s", exc)
                try:
                    self._session.rollback()
                except Exception:
                    pass

        # Causal reasoning: augment paths for causal queries
        if retrieval_mode != "doc_only":
            try:
                causal_paths = self._get_causal_context(query, query_concepts)
                if causal_paths:
                    graph_paths = graph_paths + causal_paths
            except Exception as exc:
                logger.warning("_get_causal_context failed: %s", exc)
                try:
                    self._session.rollback()
                except Exception:
                    pass

        # Get temporal context if requested (skip if no_temporal mode)
        temporal_context = None
        if include_temporal and temporal_mode != "no_temporal":
            try:
                temporal_context = self._get_temporal_context(
                    patient_id=patient_id,
                    time_point=time_point,
                )
            except Exception as exc:
                logger.warning("_get_temporal_context failed: %s", exc)
                try:
                    self._session.rollback()
                except Exception:
                    pass

        # Get applicable policy constraints if requested
        policy_constraints: list[dict[str, Any]] = []
        if include_policies and retrieval_mode == "graph_plus_doc_plus_guidelines":
            try:
                policy_constraints = self._get_policy_constraints(
                    patient_id=patient_id,
                    query_concepts=query_concepts,
                )
            except Exception as exc:
                logger.warning("_get_policy_constraints failed: %s", exc)
                try:
                    self._session.rollback()
                except Exception:
                    pass

        # P1-011: Real document retrieval with status tracking (skip if graph_only mode)
        retrieved_documents: list[dict[str, Any]] = []
        source_status = SourceRetrievalStatus.UNAVAILABLE
        if retrieval_mode != "graph_only":
            try:
                retrieved_documents, source_status = self._retrieve_documents_sync(
                    query=query,
                    patient_id=patient_id,
                    query_concepts=query_concepts,
                    query_domain=query_domain,
                )
            except Exception as exc:
                logger.warning("_retrieve_documents_sync failed: %s", exc)
                try:
                    self._session.rollback()
                except Exception:
                    pass

        return GraphAugmentedContext(
            query=query,
            patient_id=patient_id,
            graph_paths=graph_paths,
            temporal_context=temporal_context,
            retrieved_documents=retrieved_documents,
            policy_constraints=policy_constraints,
            total_evidence_pieces=(
                len(graph_paths)
                + len(retrieved_documents)
                + len(policy_constraints)
            ),
            source_retrieval_status=source_status,
        )

    # ------------------------------------------------------------------
    # Step 1: Hybrid concept extraction (NLP + OMOP + label fallback)
    # ------------------------------------------------------------------

    def _extract_query_concepts(self, query: str) -> list[QueryConcept]:
        """Extract clinical concepts from query text via hybrid pipeline.

        Tier 1: NLP entity extraction using ClinicalNLPEntityService
        Tier 3: Quoted-term extraction (always applied)
        Note: Tier 2 (OMOP lookup) is applied asynchronously via
              _enrich_concepts_with_omop_async in the async path.
        """
        concepts: list[QueryConcept] = []
        seen_texts: set[str] = set()

        # Tier 1: NLP entity extraction
        try:
            from app.services.nlp_entity import get_nlp_entity_service

            nlp_service = get_nlp_entity_service()
            result = nlp_service.extract_entities(query)
            for entity in result.entities:
                text_lower = entity.text.lower()
                if text_lower not in seen_texts:
                    seen_texts.add(text_lower)
                    concepts.append(QueryConcept(
                        text=entity.text,
                        entity_type=entity.entity_type.value,
                        confidence=entity.confidence,
                    ))
        except Exception as exc:
            logger.debug("NLP entity extraction unavailable, falling back: %s", exc)

        # Tier 3: Quoted-term extraction
        quoted = re.findall(r'"([^"]+)"', query)
        for term in quoted:
            term_lower = term.lower()
            if term_lower not in seen_texts:
                seen_texts.add(term_lower)
                concepts.append(QueryConcept(text=term, confidence=0.9))

        return concepts

    async def _enrich_concepts_with_omop_async(
        self,
        concepts: list[QueryConcept],
    ) -> list[QueryConcept]:
        """Tier 2: Enrich QueryConcepts with OMOP concept IDs via async DB lookup."""
        if not concepts:
            return concepts

        try:
            from app.services.concept_lookup import lookup_concept_cached

            for concept in concepts:
                if concept.omop_concept_id is not None:
                    continue
                domain = _ENTITY_TYPE_TO_DOMAIN.get(concept.entity_type or "")
                match = await lookup_concept_cached(
                    self._session, concept.text, domain
                )
                if match:
                    concept.omop_concept_id = match.concept_id
        except Exception as exc:
            logger.debug("OMOP concept enrichment failed: %s", exc)

        return concepts

    # ------------------------------------------------------------------
    # Node matching (updated for QueryConcept)
    # ------------------------------------------------------------------

    def _find_matching_nodes(
        self,
        patient_id: str,
        concepts: list[QueryConcept],
    ) -> list[KGNode]:
        """Find nodes in patient's graph matching query concepts.

        Patient nodes still have patient_id set, so we query directly.
        Shared concept nodes (patient_id=NULL) are found via edge-join
        since edges always carry patient_id.

        When a QueryConcept has omop_concept_id, match directly on
        KGNode.omop_concept_id for exact hits.
        """
        if not concepts:
            # Return patient node as starting point (patient nodes still have patient_id)
            stmt = (
                select(KGNode)
                .where(KGNode.patient_id == patient_id)
                .where(KGNode.node_type == NodeType.PATIENT)
            )
            result = self._session.execute(stmt)
            patient_node = result.scalar_one_or_none()
            return [patient_node] if patient_node else []

        # Try OMOP ID exact matching first
        omop_ids = [c.omop_concept_id for c in concepts if c.omop_concept_id]
        omop_matched_nodes: list[KGNode] = []
        omop_matched_ids: set = set()
        if omop_ids:
            stmt = (
                select(KGNode)
                .join(KGEdge, or_(KGEdge.target_node_id == KGNode.id, KGEdge.source_node_id == KGNode.id))
                .where(KGEdge.patient_id == patient_id)
                .where(KGNode.omop_concept_id.in_(omop_ids))
                .distinct()
            )
            result = self._session.execute(stmt)
            omop_matched_nodes = list(result.scalars().all())
            omop_matched_ids = {n.id for n in omop_matched_nodes}

        # Fall back to label matching for concepts without OMOP IDs
        label_concepts = [c for c in concepts if not c.omop_concept_id]
        label_matched_nodes: list[KGNode] = []
        if label_concepts:
            stmt = (
                select(KGNode)
                .join(KGEdge, or_(KGEdge.target_node_id == KGNode.id, KGEdge.source_node_id == KGNode.id))
                .where(KGEdge.patient_id == patient_id)
                .distinct()
            )
            result = self._session.execute(stmt)
            nodes = result.scalars().all()

            for node in nodes:
                if node.id in omop_matched_ids:
                    continue
                label_lower = node.label.lower()
                for concept in label_concepts:
                    if concept.text.lower() in label_lower:
                        label_matched_nodes.append(node)
                        break

        # OMOP matches first (higher precision), then label matches
        return (omop_matched_nodes + label_matched_nodes)[:20]

    async def _find_matching_nodes_async(
        self,
        patient_id: str,
        concepts: list[QueryConcept],
    ) -> list[KGNode]:
        """Find nodes in patient's graph matching query concepts (async version).

        Patient nodes still have patient_id set, so we query directly.
        Shared concept nodes (patient_id=NULL) are found via edge-join
        since edges always carry patient_id.

        When a QueryConcept has omop_concept_id, match directly on
        KGNode.omop_concept_id for exact hits.
        """
        if not concepts:
            # Return patient node as starting point (patient nodes still have patient_id)
            stmt = (
                select(KGNode)
                .where(KGNode.patient_id == patient_id)
                .where(KGNode.node_type == NodeType.PATIENT)
            )
            result = await self._session.execute(stmt)
            patient_node = result.scalar_one_or_none()
            return [patient_node] if patient_node else []

        # Try OMOP ID exact matching first
        omop_ids = [c.omop_concept_id for c in concepts if c.omop_concept_id]
        omop_matched_nodes: list[KGNode] = []
        omop_matched_ids: set = set()
        if omop_ids:
            stmt = (
                select(KGNode)
                .join(KGEdge, or_(KGEdge.target_node_id == KGNode.id, KGEdge.source_node_id == KGNode.id))
                .where(KGEdge.patient_id == patient_id)
                .where(KGNode.omop_concept_id.in_(omop_ids))
                .distinct()
            )
            result = await self._session.execute(stmt)
            omop_matched_nodes = list(result.scalars().all())
            omop_matched_ids = {n.id for n in omop_matched_nodes}

        # Fall back to label matching for concepts without OMOP IDs
        label_concepts = [c for c in concepts if not c.omop_concept_id]
        label_matched_nodes: list[KGNode] = []
        if label_concepts:
            stmt = (
                select(KGNode)
                .join(KGEdge, or_(KGEdge.target_node_id == KGNode.id, KGEdge.source_node_id == KGNode.id))
                .where(KGEdge.patient_id == patient_id)
                .distinct()
            )
            result = await self._session.execute(stmt)
            nodes = result.scalars().all()

            for node in nodes:
                if node.id in omop_matched_ids:
                    continue
                label_lower = node.label.lower()
                for concept in label_concepts:
                    if concept.text.lower() in label_lower:
                        label_matched_nodes.append(node)
                        break

        # OMOP matches first (higher precision), then label matches
        return (omop_matched_nodes + label_matched_nodes)[:20]

    # ------------------------------------------------------------------
    # Graph traversal (Steps 4+5: confidence scoring + bidirectional)
    # ------------------------------------------------------------------

    async def _traverse_graph_async(
        self,
        patient_id: str,
        start_nodes: list[KGNode],
        query_concepts: list[QueryConcept],
        max_hops: int,
        max_paths: int,
        assertion_mode: str = "full",
        temporal_mode: str = "full_bitemporal",
        query_hint_assertions: set[str] | None = None,
    ) -> list[GraphPath]:
        """Traverse graph from starting nodes to find relevant paths (async version)."""
        # Check traversal cache
        start_node_ids = [str(n.id) for n in start_nodes]
        concept_ids = [c.omop_concept_id for c in query_concepts if c.omop_concept_id]
        cache_key = _traversal_cache_key(
            patient_id, start_node_ids, concept_ids, max_hops, assertion_mode, temporal_mode,
        )
        cached = _traversal_cache_get(cache_key)
        if cached is not None:
            return cached[:max_paths]

        paths = []

        for start_node in start_nodes[:5]:  # Limit starting points
            node_paths = await self._bfs_traverse_async(
                patient_id=patient_id,
                start_node=start_node,
                query_concepts=query_concepts,
                max_hops=max_hops,
                assertion_mode=assertion_mode,
                temporal_mode=temporal_mode,
                query_hint_assertions=query_hint_assertions,
            )
            paths.extend(node_paths)

            if len(paths) >= max_paths:
                break

        _traversal_cache_put(cache_key, paths[:max_paths])
        return paths[:max_paths]

    async def _bfs_traverse_async(
        self,
        patient_id: str,
        start_node: KGNode,
        query_concepts: list[QueryConcept],
        max_hops: int,
        assertion_mode: str = "full",
        temporal_mode: str = "full_bitemporal",
        query_hint_assertions: set[str] | None = None,
    ) -> list[GraphPath]:
        """BFS traversal from a starting node (async, bidirectional, confidence-weighted)."""
        paths = []

        # Step 5: Get both outgoing and incoming edges
        outgoing_stmt = (
            select(KGEdge)
            .where(KGEdge.source_node_id == start_node.id)
            .where(KGEdge.patient_id == patient_id)
        )
        incoming_stmt = (
            select(KGEdge)
            .where(KGEdge.target_node_id == start_node.id)
            .where(KGEdge.patient_id == patient_id)
        )
        out_result = await self._session.execute(outgoing_stmt)
        in_result = await self._session.execute(incoming_stmt)

        outgoing_edges = list(out_result.scalars().all())
        incoming_edges = list(in_result.scalars().all())

        # Step 4: Filter and score edges (with mode parameters for ablation)
        all_edges = _score_and_filter_edges(
            outgoing_edges + incoming_edges, query_concepts,
            assertion_mode=assertion_mode, temporal_mode=temporal_mode,
            query_hint_assertions=query_hint_assertions,
        )
        all_edges = all_edges[:10]

        # Batch-fetch all neighbor nodes in one query (avoids N+1)
        neighbor_ids = set()
        for edge in all_edges:
            if edge.source_node_id != start_node.id:
                neighbor_ids.add(edge.source_node_id)
            if edge.target_node_id != start_node.id:
                neighbor_ids.add(edge.target_node_id)

        neighbor_map: dict = {}
        if neighbor_ids:
            neighbor_stmt = select(KGNode).where(KGNode.id.in_(list(neighbor_ids)))
            neighbor_result = await self._session.execute(neighbor_stmt)
            neighbor_map = {n.id: n for n in neighbor_result.scalars().all()}

        for edge in all_edges:
            # Determine the "other" node (neighbor)
            if edge.source_node_id == start_node.id:
                neighbor_node = neighbor_map.get(edge.target_node_id)
            else:
                neighbor_node = neighbor_map.get(edge.source_node_id)

            if neighbor_node:
                edge_props = edge.properties or {}
                path = GraphPath(
                    nodes=[
                        {"id": str(start_node.id), "label": start_node.label, "type": start_node.node_type.value},
                        {"id": str(neighbor_node.id), "label": neighbor_node.label, "type": neighbor_node.node_type.value},
                    ],
                    edges=[
                        {
                            "edge_type": edge.edge_type.value,
                            "confidence": edge.temporal_confidence or 1.0,
                            "temporality": edge.temporality,
                            "assertion": edge_props.get("assertion", "present"),
                            "is_negated": edge_props.get("is_negated", False),
                            "is_uncertain": edge_props.get("is_uncertain", False),
                            "event_date": edge.event_date.isoformat() if edge.event_date else None,
                            "experiencer": edge.experiencer or edge_props.get("experiencer", "patient"),
                        }
                    ],
                    path_type=self._classify_path_type(start_node, edge, neighbor_node),
                    confidence=edge.temporal_confidence or 1.0,
                )
                paths.append(path)

                # Continue traversal if more hops allowed
                if max_hops > 1:
                    deeper_paths = await self._bfs_traverse_async(
                        patient_id=patient_id,
                        start_node=neighbor_node,
                        query_concepts=query_concepts,
                        max_hops=max_hops - 1,
                        assertion_mode=assertion_mode,
                        temporal_mode=temporal_mode,
                    )
                    for deeper_path in deeper_paths[:3]:
                        combined = GraphPath(
                            nodes=path.nodes + deeper_path.nodes[1:],
                            edges=path.edges + deeper_path.edges,
                            path_type=path.path_type,
                            confidence=min(path.confidence, deeper_path.confidence),
                        )
                        paths.append(combined)

        return paths

    def _traverse_graph(
        self,
        patient_id: str,
        start_nodes: list[KGNode],
        query_concepts: list[QueryConcept],
        max_hops: int,
        max_paths: int,
        assertion_mode: str = "full",
        temporal_mode: str = "full_bitemporal",
        query_hint_assertions: set[str] | None = None,
    ) -> list[GraphPath]:
        """Traverse graph from starting nodes to find relevant paths.

        For 2+ hop queries, uses the PG-native query router which traverses
        both kg_edges and concept_relationships (20M+ vocabulary relationships)
        in a single CTE. Falls back to PG BFS on failure.
        """
        # Check traversal cache
        start_node_ids = [str(n.id) for n in start_nodes]
        concept_ids = [c.omop_concept_id for c in query_concepts if c.omop_concept_id]
        cache_key = _traversal_cache_key(
            patient_id, start_node_ids, concept_ids, max_hops, assertion_mode, temporal_mode,
        )
        cached = _traversal_cache_get(cache_key)
        if cached is not None:
            return cached[:max_paths]

        if max_hops >= 2:
            try:
                from app.services.neo4j_query_router import GraphQueryRouter, MultiHopQuery

                start_concept_ids = [
                    n.omop_concept_id for n in start_nodes
                    if n.omop_concept_id
                ]
                if start_concept_ids:
                    router = GraphQueryRouter(self._session)
                    query = MultiHopQuery(
                        patient_id=patient_id,
                        start_concept_ids=start_concept_ids,
                        max_hops=max_hops,
                        max_paths=max_paths,
                        min_confidence=MIN_TRAVERSAL_CONFIDENCE,
                    )
                    router_paths = router.execute_multi_hop(query)
                    result = [
                        GraphPath(
                            nodes=[
                                {"id": n.node_id, "label": n.label, "type": n.node_type}
                                for n in rp.nodes
                            ],
                            edges=[
                                {
                                    "edge_type": e.edge_type,
                                    "confidence": e.confidence,
                                    "temporality": e.temporality,
                                    "assertion": getattr(e, "assertion", None) or "present",
                                    "is_negated": getattr(e, "is_negated", False),
                                    "is_uncertain": getattr(e, "is_uncertain", False),
                                    "event_date": e.event_date,
                                    "experiencer": getattr(e, "experiencer", None) or "patient",
                                }
                                for e in rp.edges
                            ],
                            path_type="multi_hop",
                            confidence=rp.path_confidence,
                        )
                        for rp in router_paths
                    ][:max_paths]
                    _traversal_cache_put(cache_key, result)
                    return result
            except Exception as e:
                logger.debug("Query router failed, using PG BFS: %s", e)
                try:
                    self._session.rollback()
                except Exception:
                    pass

        paths = []

        for start_node in start_nodes[:5]:  # Limit starting points
            node_paths = self._bfs_traverse(
                patient_id=patient_id,
                start_node=start_node,
                query_concepts=query_concepts,
                max_hops=max_hops,
                assertion_mode=assertion_mode,
                temporal_mode=temporal_mode,
                query_hint_assertions=query_hint_assertions,
            )
            paths.extend(node_paths)

            if len(paths) >= max_paths:
                break

        _traversal_cache_put(cache_key, paths[:max_paths])
        return paths[:max_paths]

    def _bfs_traverse(
        self,
        patient_id: str,
        start_node: KGNode,
        query_concepts: list[QueryConcept],
        max_hops: int,
        assertion_mode: str = "full",
        temporal_mode: str = "full_bitemporal",
        query_hint_assertions: set[str] | None = None,
    ) -> list[GraphPath]:
        """BFS traversal from a starting node (sync, bidirectional, confidence-weighted)."""
        paths = []

        # Step 5: Get both outgoing and incoming edges
        outgoing_stmt = (
            select(KGEdge)
            .where(KGEdge.source_node_id == start_node.id)
            .where(KGEdge.patient_id == patient_id)
        )
        incoming_stmt = (
            select(KGEdge)
            .where(KGEdge.target_node_id == start_node.id)
            .where(KGEdge.patient_id == patient_id)
        )
        out_result = self._session.execute(outgoing_stmt)
        in_result = self._session.execute(incoming_stmt)

        outgoing_edges = list(out_result.scalars().all())
        incoming_edges = list(in_result.scalars().all())

        # Step 4: Filter and score edges (with mode parameters for ablation)
        all_edges = _score_and_filter_edges(
            outgoing_edges + incoming_edges, query_concepts,
            assertion_mode=assertion_mode, temporal_mode=temporal_mode,
            query_hint_assertions=query_hint_assertions,
        )
        all_edges = all_edges[:10]

        # Batch-fetch all neighbor nodes in one query (avoids N+1)
        neighbor_ids = set()
        for edge in all_edges:
            if edge.source_node_id != start_node.id:
                neighbor_ids.add(edge.source_node_id)
            if edge.target_node_id != start_node.id:
                neighbor_ids.add(edge.target_node_id)

        neighbor_map: dict = {}
        if neighbor_ids:
            neighbor_stmt = select(KGNode).where(KGNode.id.in_(list(neighbor_ids)))
            neighbor_result = self._session.execute(neighbor_stmt)
            neighbor_map = {n.id: n for n in neighbor_result.scalars().all()}

        for edge in all_edges:
            # Determine the "other" node (neighbor)
            if edge.source_node_id == start_node.id:
                neighbor_node = neighbor_map.get(edge.target_node_id)
            else:
                neighbor_node = neighbor_map.get(edge.source_node_id)

            if neighbor_node:
                edge_props = edge.properties or {}
                path = GraphPath(
                    nodes=[
                        {"id": str(start_node.id), "label": start_node.label, "type": start_node.node_type.value},
                        {"id": str(neighbor_node.id), "label": neighbor_node.label, "type": neighbor_node.node_type.value},
                    ],
                    edges=[
                        {
                            "edge_type": edge.edge_type.value,
                            "confidence": edge.temporal_confidence or 1.0,
                            "temporality": edge.temporality,
                            "assertion": edge_props.get("assertion", "present"),
                            "is_negated": edge_props.get("is_negated", False),
                            "is_uncertain": edge_props.get("is_uncertain", False),
                            "event_date": edge.event_date.isoformat() if edge.event_date else None,
                            "experiencer": edge.experiencer or edge_props.get("experiencer", "patient"),
                        }
                    ],
                    path_type=self._classify_path_type(start_node, edge, neighbor_node),
                    confidence=edge.temporal_confidence or 1.0,
                )
                paths.append(path)

                # Continue traversal if more hops allowed
                if max_hops > 1:
                    deeper_paths = self._bfs_traverse(
                        patient_id=patient_id,
                        start_node=neighbor_node,
                        query_concepts=query_concepts,
                        max_hops=max_hops - 1,
                        assertion_mode=assertion_mode,
                        temporal_mode=temporal_mode,
                    )
                    for deeper_path in deeper_paths[:3]:
                        combined = GraphPath(
                            nodes=path.nodes + deeper_path.nodes[1:],
                            edges=path.edges + deeper_path.edges,
                            path_type=path.path_type,
                            confidence=min(path.confidence, deeper_path.confidence),
                        )
                        paths.append(combined)

        return paths

    def _get_causal_context(
        self,
        query: str,
        query_concepts: list[QueryConcept],
    ) -> list[GraphPath]:
        """Get causal reasoning context when query contains causal language.

        Only invoked when query contains causal language (e.g., "caused by",
        "side effect", "treatment for"). Results are converted to GraphPath
        for uniform context assembly.
        """
        if not _CAUSAL_PATTERNS.search(query):
            return []

        try:
            from app.services.causal_reasoning_service import (
                CausalQuery,
                get_causal_reasoning_service,
            )

            causal_service = get_causal_reasoning_service()

            # Use first concept as start, second as end (if available)
            concept_texts = [c.text for c in query_concepts if c.text]
            if not concept_texts:
                return []

            causal_query = CausalQuery(
                start_concept=concept_texts[0],
                end_concept=concept_texts[1] if len(concept_texts) > 1 else None,
                max_chain_length=4,
                min_confidence=MIN_TRAVERSAL_CONFIDENCE,
            )

            # CausalReasoningService is async; use mock data path synchronously
            chains = causal_service._mock_causal_chains(causal_query)

            # Convert CausalChain -> GraphPath
            causal_paths: list[GraphPath] = []
            for chain in chains:
                if not chain.links:
                    continue
                nodes = [
                    {"id": chain.links[0].source_cui, "label": chain.links[0].source_name, "type": "concept"}
                ]
                edges_list = []
                for link in chain.links:
                    nodes.append({"id": link.target_cui, "label": link.target_name, "type": "concept"})
                    edges_list.append({
                        "edge_type": link.relation_type.value,
                        "confidence": link.confidence,
                        "temporality": None,
                        "event_date": None,
                    })

                causal_paths.append(GraphPath(
                    nodes=nodes,
                    edges=edges_list,
                    path_type="causal_chain",
                    confidence=chain.total_confidence,
                ))

            return causal_paths

        except Exception as e:
            logger.debug("Causal reasoning integration failed: %s", e)
            return []

    def _classify_path_type(
        self,
        source: KGNode,
        edge: KGEdge,
        target: KGNode,
    ) -> str:
        """Classify the type of path for better context."""
        if source.node_type == NodeType.PATIENT:
            if target.node_type == NodeType.CONDITION:
                return "patient_condition"
            elif target.node_type == NodeType.DRUG:
                return "patient_medication"
            elif target.node_type == NodeType.MEASUREMENT:
                return "patient_measurement"

        if source.node_type == NodeType.CONDITION:
            if target.node_type == NodeType.DRUG:
                return "condition_treatment"
            elif target.node_type == NodeType.CONDITION:
                return "comorbidity"

        if edge.edge_type == EdgeType.DRUG_TREATS:
            return "treatment_relationship"

        return "general_relationship"

    # ------------------------------------------------------------------
    # Step 2: Temporal context (N+1 fix — batch node fetch)
    # ------------------------------------------------------------------

    async def _get_temporal_context_async(
        self,
        patient_id: str,
        time_point: datetime | None,
    ) -> TemporalContext:
        """Get temporal context from patient's graph (async, batch-optimized)."""
        # Get all edges with temporal data
        stmt = (
            select(KGEdge)
            .where(KGEdge.patient_id == patient_id)
            .where(KGEdge.event_date.isnot(None))
            .order_by(KGEdge.event_date.desc())
        )
        result = await self._session.execute(stmt)
        edges = result.scalars().all()
        edges = edges[:50]

        # Batch-fetch all target nodes in one query (fixes N+1)
        target_ids = [e.target_node_id for e in edges]
        if target_ids:
            target_stmt = select(KGNode).where(KGNode.id.in_(target_ids))
            target_result = await self._session.execute(target_stmt)
            target_map = {n.id: n for n in target_result.scalars().all()}
        else:
            target_map = {}

        # Build timeline
        timeline = []
        current_state = {}
        historical_state = {}

        for edge in edges:
            target = target_map.get(edge.target_node_id)

            if target:
                event = {
                    "date": edge.event_date.isoformat() if edge.event_date else None,
                    "description": f"{edge.edge_type.value}: {target.label}",
                    "temporality": edge.temporality,
                    "is_current": edge.temporality == "current",
                }
                timeline.append(event)

                # Track current vs historical
                if edge.temporality == "current":
                    current_state[target.label] = "active"
                elif edge.temporality == "past":
                    historical_state[target.label] = "resolved"

        # Detect temporal conflicts (simplified)
        conflicts: list[str] = []

        return TemporalContext(
            event_timeline=timeline,
            temporal_conflicts=conflicts,
            current_state=current_state,
            historical_state=historical_state,
        )

    def _get_temporal_context(
        self,
        patient_id: str,
        time_point: datetime | None,
    ) -> TemporalContext:
        """Get temporal context from patient's graph (sync, batch-optimized)."""
        # Get all edges with temporal data
        stmt = (
            select(KGEdge)
            .where(KGEdge.patient_id == patient_id)
            .where(KGEdge.event_date.isnot(None))
            .order_by(KGEdge.event_date.desc())
        )
        result = self._session.execute(stmt)
        edges = result.scalars().all()
        edges = edges[:50]

        # Batch-fetch all target nodes in one query (fixes N+1)
        target_ids = [e.target_node_id for e in edges]
        if target_ids:
            target_stmt = select(KGNode).where(KGNode.id.in_(target_ids))
            target_result = self._session.execute(target_stmt)
            target_map = {n.id: n for n in target_result.scalars().all()}
        else:
            target_map = {}

        # Build timeline
        timeline = []
        current_state = {}
        historical_state = {}

        for edge in edges:
            target = target_map.get(edge.target_node_id)

            if target:
                event = {
                    "date": edge.event_date.isoformat() if edge.event_date else None,
                    "description": f"{edge.edge_type.value}: {target.label}",
                    "temporality": edge.temporality,
                    "is_current": edge.temporality == "current",
                }
                timeline.append(event)

                # Track current vs historical
                if edge.temporality == "current":
                    current_state[target.label] = "active"
                elif edge.temporality == "past":
                    historical_state[target.label] = "resolved"

        # Detect temporal conflicts (simplified)
        conflicts: list[str] = []

        return TemporalContext(
            event_timeline=timeline,
            temporal_conflicts=conflicts,
            current_state=current_state,
            historical_state=historical_state,
        )

    # ------------------------------------------------------------------
    # Step 3: Policy constraints via GuidelineRAGService
    # ------------------------------------------------------------------

    def _get_policy_constraints(
        self,
        patient_id: str,
        query_concepts: list[QueryConcept],
    ) -> list[dict[str, Any]]:
        """Get applicable policy constraints from clinical guidelines (sync)."""
        return self._build_policy_constraints(patient_id, query_concepts)

    async def _get_policy_constraints_async(
        self,
        patient_id: str,
        query_concepts: list[QueryConcept],
    ) -> list[dict[str, Any]]:
        """Get applicable policy constraints from clinical guidelines (async)."""
        return self._build_policy_constraints(patient_id, query_concepts)

    def _build_policy_constraints(
        self,
        patient_id: str,
        query_concepts: list[QueryConcept],
    ) -> list[dict[str, Any]]:
        """Core policy constraint logic shared by sync/async paths.

        Uses GuidelineRAGService (which is synchronous) to retrieve
        applicable clinical guidelines based on query concepts.
        """
        if not query_concepts:
            return []

        try:
            from app.services.guideline_rag_service import get_guideline_rag_service

            guideline_service = get_guideline_rag_service()
            if not guideline_service.is_loaded:
                return []

            # Separate concepts by type for patient context
            patient_conditions = [
                c.text for c in query_concepts
                if c.entity_type in ("diagnosis", "symptom")
            ]
            patient_medications = [
                c.text for c in query_concepts
                if c.entity_type == "medication"
            ]

            query_text = " ".join(c.text for c in query_concepts)
            citations = guideline_service.search(
                query=query_text,
                patient_conditions=patient_conditions or None,
                patient_medications=patient_medications or None,
                top_k=2,
                min_score=0.5,
            )

            constraints: list[dict[str, Any]] = []
            for citation in citations:
                section = citation.section
                constraints.append({
                    "rule_id": section.section_id,
                    "description": (
                        f"[{section.guideline}] {section.recommendation_text}"
                    ),
                    "strength": (
                        section.recommendation_level or section.evidence_grade
                    ),
                    "relevance_score": citation.score,
                })

            return constraints

        except Exception as exc:
            logger.debug("Guideline RAG lookup failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Document retrieval (unchanged logic, updated type hints)
    # ------------------------------------------------------------------

    async def _retrieve_documents_async(
        self,
        query: str,
        patient_id: str,
        query_concepts: list[QueryConcept] | None = None,
        query_domain: str | None = None,
    ) -> tuple[list[dict[str, Any]], str]:
        """Retrieve real patient documents using FTS with Python fallback (async)."""
        try:
            # Build search terms from query + concepts
            search_terms = query
            if query_concepts:
                concept_texts = [
                    c.text if isinstance(c, QueryConcept) else str(c)
                    for c in query_concepts
                ]
                search_terms = " ".join([query] + [t for t in concept_texts if t])

            # Try FTS query first
            try:
                from sqlalchemy import func as sa_func, text as sa_text
                fts_query = sa_func.plainto_tsquery("english", search_terms)
                stmt = (
                    select(
                        Document,
                        sa_func.ts_rank(Document.search_vector, fts_query).label("rank"),
                    )
                    .where(Document.patient_id == patient_id)
                    .where(Document.search_vector.op("@@")(fts_query))
                    .order_by(sa_text("rank DESC"))
                    .limit(MAX_RETRIEVED_DOCS)
                )
                result = await self._session.execute(stmt)
                rows = result.all()
                if rows:
                    formatted = []
                    for doc, rank in rows:
                        content = extract_relevant_sections(doc.text, domain=query_domain, budget=MAX_DOC_CONTENT_CHARS) if doc.text else ""
                        formatted.append({
                            "source": f"document:{doc.id}",
                            "source_available": True,
                            "note_type": doc.note_type,
                            "patient_id": doc.patient_id,
                            "content": content,
                            "relevance_score": round(float(rank), 4),
                        })
                    return formatted, SourceRetrievalStatus.FULL
            except Exception as fts_exc:
                logger.debug("FTS query failed, falling back to Python scoring: %s", fts_exc)
                try:
                    await self._session.rollback()
                except Exception:
                    pass

            # Fallback: load all docs and score in Python
            stmt = select(Document).where(Document.patient_id == patient_id)
            result = await self._session.execute(stmt)
            docs = list(result.scalars().all())

            if not docs:
                return [], SourceRetrievalStatus.UNAVAILABLE

            return self._score_and_format_docs(docs, query, query_concepts, query_domain=query_domain)

        except Exception as exc:
            logger.warning("Document retrieval failed for patient %s: %s", patient_id, exc)
            try:
                await self._session.rollback()
            except Exception:
                pass
            return [], SourceRetrievalStatus.UNAVAILABLE

    def _retrieve_documents_sync(
        self,
        query: str,
        patient_id: str,
        query_concepts: list[QueryConcept] | None = None,
        query_domain: str | None = None,
    ) -> tuple[list[dict[str, Any]], str]:
        """Retrieve real patient documents using FTS with Python fallback (sync)."""
        try:
            # Build search terms from query + concepts
            search_terms = query
            if query_concepts:
                concept_texts = [
                    c.text if isinstance(c, QueryConcept) else str(c)
                    for c in query_concepts
                ]
                search_terms = " ".join([query] + [t for t in concept_texts if t])

            # Try FTS query first
            try:
                from sqlalchemy import func as sa_func, text as sa_text
                fts_query = sa_func.plainto_tsquery("english", search_terms)
                stmt = (
                    select(
                        Document,
                        sa_func.ts_rank(Document.search_vector, fts_query).label("rank"),
                    )
                    .where(Document.patient_id == patient_id)
                    .where(Document.search_vector.op("@@")(fts_query))
                    .order_by(sa_text("rank DESC"))
                    .limit(MAX_RETRIEVED_DOCS)
                )
                result = self._session.execute(stmt)
                rows = result.all()
                if rows:
                    formatted = []
                    for doc, rank in rows:
                        content = extract_relevant_sections(doc.text, domain=query_domain, budget=MAX_DOC_CONTENT_CHARS) if doc.text else ""
                        formatted.append({
                            "source": f"document:{doc.id}",
                            "source_available": True,
                            "note_type": doc.note_type,
                            "patient_id": doc.patient_id,
                            "content": content,
                            "relevance_score": round(float(rank), 4),
                        })
                    return formatted, SourceRetrievalStatus.FULL
            except Exception as fts_exc:
                logger.debug("FTS query failed, falling back to Python scoring: %s", fts_exc)
                try:
                    self._session.rollback()
                except Exception:
                    pass

            # Fallback: load all docs and score in Python
            stmt = select(Document).where(Document.patient_id == patient_id)
            result = self._session.execute(stmt)
            docs = list(result.scalars().all())

            if not docs:
                return [], SourceRetrievalStatus.UNAVAILABLE

            return self._score_and_format_docs(docs, query, query_concepts, query_domain=query_domain)

        except Exception as exc:
            logger.warning("Document retrieval failed for patient %s: %s", patient_id, exc)
            try:
                self._session.rollback()
            except Exception:
                pass
            return [], SourceRetrievalStatus.UNAVAILABLE

    def _score_and_format_docs(
        self,
        docs: list[Any],
        query: str,
        query_concepts: list[QueryConcept] | None = None,
        query_domain: str | None = None,
    ) -> tuple[list[dict[str, Any]], str]:
        """Score documents by relevance and return with retrieval status.

        Returns:
            Tuple of (formatted docs, source_retrieval_status).
        """
        concept_texts: list[str] = []
        if query_concepts:
            for c in query_concepts:
                concept_texts.append(c.text if isinstance(c, QueryConcept) else str(c))
        query_lower = query.lower()
        scored: list[tuple[float, Any]] = []

        for doc in docs:
            try:
                text_lower = doc.text.lower() if doc.text else ""
                # Score: keyword overlap + concept overlap
                score = 0.0
                query_words = set(query_lower.split())
                for word in query_words:
                    if len(word) > 2 and word in text_lower:
                        score += 1.0
                for concept in concept_texts:
                    if concept.lower() in text_lower:
                        score += 2.0
                scored.append((score, doc))
            except Exception:
                # Individual doc scoring failure doesn't invalidate batch
                continue

        if not scored:
            return [], SourceRetrievalStatus.UNAVAILABLE

        # Sort by score descending, take top docs
        scored.sort(key=lambda x: x[0], reverse=True)
        top_docs = scored[:MAX_RETRIEVED_DOCS]

        formatted: list[dict[str, Any]] = []
        any_failed = False
        for score, doc in top_docs:
            if score <= 0:
                continue
            try:
                content = extract_relevant_sections(doc.text, domain=query_domain, budget=MAX_DOC_CONTENT_CHARS) if doc.text else ""
                formatted.append({
                    "source": f"document:{doc.id}",
                    "source_available": True,
                    "note_type": doc.note_type,
                    "patient_id": doc.patient_id,
                    "content": content,
                    "relevance_score": round(score, 2),
                })
            except Exception as exc:
                try:
                    doc_id = doc.id
                except Exception:
                    doc_id = "unknown"
                logger.warning("P1-011: Failed to format doc %s: %s", doc_id, exc)
                formatted.append({
                    "source": f"document:{doc_id}",
                    "source_available": False,
                    "content": "",
                    "relevance_score": 0.0,
                })
                any_failed = True

        if not formatted:
            return [], SourceRetrievalStatus.UNAVAILABLE

        if any_failed:
            return formatted, SourceRetrievalStatus.PARTIAL

        return formatted, SourceRetrievalStatus.FULL


# ------------------------------------------------------------------
# Step 4: Edge scoring and filtering (module-level helper)
# ------------------------------------------------------------------

def _detect_query_assertion_focus(query: str) -> set[str]:
    """Detect which assertion types a question is specifically asking about.

    Returns a set of assertion type strings that should NOT be penalized
    during edge scoring because the question targets them directly.
    """
    q = query.lower()
    focus: set[str] = set()

    historical_keywords = (
        "currently", "still", "active", "former", "previous", "history of",
        "used to", "resolved", "was ", "had ", "past ", "no longer",
    )
    conditional_keywords = (
        "should", "would", "could", "if ", "whether", "recommend",
        "management", "indicated", "need", "appropriate",
    )
    duration_keywords = (
        "how long", "chronic", "new ", "duration", "since ", "onset",
        "when did", "how recent",
    )

    if any(kw in q for kw in historical_keywords):
        focus.add("historical")
    if any(kw in q for kw in conditional_keywords):
        focus.update({"hypothetical", "conditional"})
    if any(kw in q for kw in duration_keywords):
        focus.add("historical")  # duration questions need historical context too

    return focus


def _score_and_filter_edges(
    edges: list[KGEdge],
    query_concepts: list[QueryConcept],
    assertion_mode: str = "full",
    temporal_mode: str = "full_bitemporal",
    query_hint_assertions: set[str] | None = None,
) -> list[KGEdge]:
    """Score edges by confidence and query relevance, filter low-confidence.

    Scoring criteria:
    1. Base confidence (temporal_confidence)
    2. Query-relevant edge types get a boost
    3. Current temporality preferred over historical (unless temporal_mode="no_temporal")
    4. Assertion-based scoring (unless assertion_mode="none")
    5. Edges below MIN_TRAVERSAL_CONFIDENCE are pruned

    Args:
        edges: Edges to score.
        query_concepts: Query concepts for relevance boosting.
        assertion_mode: "full" | "extracted_only" | "none".
            - "full": Apply assertion-based score modifiers.
            - "extracted_only": Include assertion in metadata but don't modify scores.
            - "none": Ignore assertion entirely.
        temporal_mode: "full_bitemporal" | "timestamps_only" | "no_temporal".
            - "full_bitemporal": Full temporal scoring including temporality boost.
            - "timestamps_only": Use event_date but skip temporality enum boost.
            - "no_temporal": No temporal scoring at all.
    """
    # Collect preferred edge types from all query concepts
    preferred_types: set[str] = set()
    for concept in query_concepts:
        if concept.entity_type:
            preferred_types.update(
                _ENTITY_TYPE_TO_PREFERRED_EDGES.get(concept.entity_type, set())
            )

    scored: list[tuple[float, KGEdge]] = []
    for edge in edges:
        confidence = edge.temporal_confidence or 1.0

        # Prune low-confidence edges
        if confidence < MIN_TRAVERSAL_CONFIDENCE:
            continue

        score = confidence

        # Boost query-relevant edge types
        if preferred_types and edge.edge_type.value in preferred_types:
            score += 0.2

        # Temporal scoring (skip if no_temporal mode)
        if temporal_mode != "no_temporal":
            if edge.temporality == "current":
                score += 0.1

        # Assertion-based scoring (only in "full" or "full_v2" mode)
        if assertion_mode in ("full", "full_v2", "full_v3", "full_v4", "full_v5", "full_v6"):
            edge_props = edge.properties or {}
            assertion = edge_props.get("assertion", "present")
            hints = query_hint_assertions or set()
            if assertion == "absent":
                score *= 0.5  # Negated conditions significantly less relevant
            elif assertion == "possible":
                score *= 0.75  # Uncertain conditions moderately less relevant
            elif assertion in ("hypothetical", "conditional"):
                if assertion not in hints:
                    score *= 0.6  # Penalize only when query isn't about conditionals
            elif assertion == "family_history":
                score *= 0.7  # Family history, not patient's own
            elif assertion == "historical":
                if "historical" not in hints:
                    score *= 0.8  # Penalize only when query isn't about history
            # "present" gets no penalty (default)

            # Experiencer-based scoring — takes priority over assertion penalty
            experiencer = getattr(edge, "experiencer", None) or edge_props.get("experiencer", "patient")
            if experiencer == "family":
                # Family history much less relevant than patient's own.
                # Apply the lower of assertion and experiencer penalties.
                family_score = score / max(
                    (0.7 if assertion == "family_history" else 1.0), 1e-9
                ) * 0.4
                score = min(score, family_score)
            elif experiencer == "other":
                score *= 0.3  # Other person's condition rarely relevant

        scored.append((score, edge))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)
    return [edge for _, edge in scored]


def get_graph_augmented_rag_service(
    session: Union[Session, AsyncSession]
) -> GraphAugmentedRAGService:
    """Factory function to create GraphAugmentedRAGService.

    Args:
        session: SQLAlchemy database session (sync or async).

    Returns:
        GraphAugmentedRAGService instance configured for the session type.
    """
    return GraphAugmentedRAGService(session)
