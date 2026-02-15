"""Answer Explanation Template Service (P3-004).

Provides structured answer templates tuned by question class for clinical
decision support responses. Each template organizes output into consistent
sections: summary, evidence, confidence_note, limitations, and next_steps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import logging
from typing import Any

logger = logging.getLogger(__name__)


class QuestionClass(str, Enum):
    """Classification of clinical question types."""

    MEDICATION_QUERY = "medication_query"
    CONDITION_QUERY = "condition_query"
    LAB_QUERY = "lab_query"
    PROCEDURE_QUERY = "procedure_query"
    GENERAL_QUERY = "general_query"
    DIFFERENTIAL_DIAGNOSIS = "differential_diagnosis"


@dataclass
class AnswerSection:
    """A single section in a formatted answer."""

    heading: str
    content: str


@dataclass
class FormattedAnswer:
    """A fully formatted clinical answer with structured sections."""

    question_class: QuestionClass
    summary: str
    evidence: str
    confidence_note: str
    limitations: str
    next_steps: str
    raw_answer: str
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "question_class": self.question_class.value,
            "summary": self.summary,
            "evidence": self.evidence,
            "confidence_note": self.confidence_note,
            "limitations": self.limitations,
            "next_steps": self.next_steps,
            "raw_answer": self.raw_answer,
            "confidence": self.confidence,
        }

    def to_text(self) -> str:
        """Render as plain text with section headers."""
        sections = [
            ("Summary", self.summary),
            ("Evidence", self.evidence),
            ("Confidence", self.confidence_note),
            ("Limitations", self.limitations),
            ("Recommended Next Steps", self.next_steps),
        ]
        parts: list[str] = []
        for heading, body in sections:
            if body:
                parts.append(f"## {heading}\n{body}")
        return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Template definitions per question class
# ---------------------------------------------------------------------------

@dataclass
class AnswerTemplate:
    """Template describing how to build each section for a question class."""

    question_class: QuestionClass
    summary_prefix: str
    evidence_heading: str
    confidence_bands: dict[str, str]  # "high"/"medium"/"low" -> note text
    default_limitations: list[str]
    next_steps_suggestions: list[str]


_TEMPLATES: dict[QuestionClass, AnswerTemplate] = {
    QuestionClass.MEDICATION_QUERY: AnswerTemplate(
        question_class=QuestionClass.MEDICATION_QUERY,
        summary_prefix="Medication Review:",
        evidence_heading="Pharmacological Evidence",
        confidence_bands={
            "high": "This assessment is supported by well-established pharmacological data.",
            "medium": "This assessment is based on available clinical evidence; individual patient factors may alter applicability.",
            "low": "Limited evidence is available for this specific scenario. Clinical judgment should take precedence.",
        },
        default_limitations=[
            "Drug interaction databases may not cover all possible combinations.",
            "Patient-specific pharmacogenomic factors are not accounted for.",
            "Off-label uses may not be fully represented.",
        ],
        next_steps_suggestions=[
            "Verify against current prescribing information.",
            "Review patient allergy and medication history.",
            "Consider pharmacist consultation for complex regimens.",
        ],
    ),
    QuestionClass.CONDITION_QUERY: AnswerTemplate(
        question_class=QuestionClass.CONDITION_QUERY,
        summary_prefix="Clinical Condition Assessment:",
        evidence_heading="Clinical Evidence",
        confidence_bands={
            "high": "This assessment aligns with established clinical guidelines and diagnostic criteria.",
            "medium": "This assessment is supported by clinical evidence but may require further evaluation.",
            "low": "The evidence base for this specific presentation is limited. Further workup is recommended.",
        },
        default_limitations=[
            "Assessment is based on provided information and may not capture the full clinical picture.",
            "Comorbidities and patient-specific factors may modify the assessment.",
            "Guideline recommendations may vary by institution and region.",
        ],
        next_steps_suggestions=[
            "Correlate with full patient history and physical examination.",
            "Review relevant diagnostic studies.",
            "Consider specialist referral if indicated.",
        ],
    ),
    QuestionClass.LAB_QUERY: AnswerTemplate(
        question_class=QuestionClass.LAB_QUERY,
        summary_prefix="Laboratory Interpretation:",
        evidence_heading="Reference Data and Interpretation",
        confidence_bands={
            "high": "Interpretation is based on well-established reference ranges and clinical significance thresholds.",
            "medium": "Interpretation is supported by standard references; clinical context should guide management.",
            "low": "Reference ranges may vary by assay and population. Confirmatory testing may be warranted.",
        },
        default_limitations=[
            "Reference ranges may differ by laboratory method and patient demographics.",
            "Single values should be interpreted in clinical context and trended over time.",
            "Pre-analytical variables (e.g., fasting status, timing) may affect results.",
        ],
        next_steps_suggestions=[
            "Correlate with clinical presentation.",
            "Consider repeat testing if results are unexpected.",
            "Review trending data for pattern recognition.",
        ],
    ),
    QuestionClass.PROCEDURE_QUERY: AnswerTemplate(
        question_class=QuestionClass.PROCEDURE_QUERY,
        summary_prefix="Procedure Information:",
        evidence_heading="Procedural Evidence and Guidelines",
        confidence_bands={
            "high": "Information is based on established procedural guidelines and evidence-based protocols.",
            "medium": "Information is supported by clinical practice standards; institutional protocols may vary.",
            "low": "Evidence for this specific procedural scenario is limited. Consult procedural specialists.",
        },
        default_limitations=[
            "Procedural risks vary by patient factors and institutional capabilities.",
            "Coding and billing requirements may differ by payer.",
            "Emerging techniques may not yet have long-term outcome data.",
        ],
        next_steps_suggestions=[
            "Review institutional protocols and consent requirements.",
            "Assess patient-specific risk factors.",
            "Verify procedural coding for accuracy.",
        ],
    ),
    QuestionClass.GENERAL_QUERY: AnswerTemplate(
        question_class=QuestionClass.GENERAL_QUERY,
        summary_prefix="Clinical Information:",
        evidence_heading="Supporting Evidence",
        confidence_bands={
            "high": "This information is well-supported by current clinical knowledge.",
            "medium": "This information is based on available evidence; further review may be appropriate.",
            "low": "Limited information is available for this specific query. Exercise clinical judgment.",
        },
        default_limitations=[
            "This is a general informational response and should not replace clinical judgment.",
            "Individual patient circumstances may alter the applicability of this information.",
        ],
        next_steps_suggestions=[
            "Review in the context of the specific clinical scenario.",
            "Consult relevant clinical guidelines or references.",
        ],
    ),
    QuestionClass.DIFFERENTIAL_DIAGNOSIS: AnswerTemplate(
        question_class=QuestionClass.DIFFERENTIAL_DIAGNOSIS,
        summary_prefix="Differential Diagnosis Assessment:",
        evidence_heading="Diagnostic Evidence and Reasoning",
        confidence_bands={
            "high": "The differential is based on well-characterized clinical presentations and diagnostic criteria.",
            "medium": "The differential is informed by clinical evidence but the presentation has overlapping features.",
            "low": "The presentation is atypical or data is insufficient to narrow the differential confidently.",
        },
        default_limitations=[
            "Differential diagnosis is based on provided clinical data and may not be exhaustive.",
            "Rare diagnoses may not be represented without specific suggestive features.",
            "Pre-test probability depends on local epidemiology and patient demographics.",
        ],
        next_steps_suggestions=[
            "Obtain targeted diagnostic studies to narrow the differential.",
            "Reassess if new symptoms or data emerge.",
            "Consider multidisciplinary input for complex presentations.",
        ],
    ),
}


def _confidence_band(confidence: float) -> str:
    """Map a 0-1 confidence score to a band label."""
    if confidence >= 0.8:
        return "high"
    if confidence >= 0.5:
        return "medium"
    return "low"


def get_template(question_class: QuestionClass) -> AnswerTemplate:
    """Return the answer template for a given question class.

    Falls back to GENERAL_QUERY if the class is unknown.
    """
    return _TEMPLATES.get(question_class, _TEMPLATES[QuestionClass.GENERAL_QUERY])


def format_answer(
    question_class: QuestionClass,
    raw_answer: str,
    evidence: str | None = None,
    confidence: float = 0.5,
) -> FormattedAnswer:
    """Format a raw answer into a structured clinical response.

    Args:
        question_class: The classification of the clinical question.
        raw_answer: The unformatted answer text.
        evidence: Optional evidence text. Defaults to restating the raw answer.
        confidence: Confidence score between 0 and 1.

    Returns:
        A FormattedAnswer with all structured sections populated.
    """
    confidence = max(0.0, min(1.0, confidence))
    template = get_template(question_class)
    band = _confidence_band(confidence)

    summary = f"{template.summary_prefix} {raw_answer}"
    evidence_text = evidence if evidence else raw_answer
    confidence_note = template.confidence_bands.get(band, template.confidence_bands["medium"])
    limitations = " ".join(template.default_limitations)
    next_steps = " ".join(template.next_steps_suggestions)

    return FormattedAnswer(
        question_class=question_class,
        summary=summary,
        evidence=f"{template.evidence_heading}: {evidence_text}",
        confidence_note=f"Confidence {confidence:.0%} ({band}): {confidence_note}",
        limitations=limitations,
        next_steps=next_steps,
        raw_answer=raw_answer,
        confidence=confidence,
    )
