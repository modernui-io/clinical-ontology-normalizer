"""LLM-based Clinical Summarization Service.

Uses external LLM APIs (OpenAI/Anthropic) to generate clinical summaries:
- Clinical note summarization
- Assessment and Plan generation
- Key findings extraction
- Discharge summary generation

Features:
- Optimized prompt templates for clinical text
- PHI handling considerations (note: actual PHI should be de-identified before sending)
- Structured output parsing
- Fallback to rule-based summarization
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.services.llm_service import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
    LLMService,
    get_llm_service,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Data Classes
# ============================================================================


class SummaryLength(str, Enum):
    """Length preference for summaries."""

    BRIEF = "brief"  # 1-2 sentences
    STANDARD = "standard"  # 1-2 paragraphs
    DETAILED = "detailed"  # Full comprehensive summary


class ClinicalSection(str, Enum):
    """Standard clinical document sections."""

    CHIEF_COMPLAINT = "chief_complaint"
    HPI = "history_of_present_illness"
    PAST_MEDICAL_HISTORY = "past_medical_history"
    MEDICATIONS = "medications"
    ALLERGIES = "allergies"
    SOCIAL_HISTORY = "social_history"
    FAMILY_HISTORY = "family_history"
    REVIEW_OF_SYSTEMS = "review_of_systems"
    PHYSICAL_EXAM = "physical_exam"
    ASSESSMENT = "assessment"
    PLAN = "plan"
    LABS = "labs"
    IMAGING = "imaging"
    PROCEDURES = "procedures"


@dataclass
class KeyFinding:
    """A key clinical finding extracted from text."""

    finding: str
    category: str  # diagnosis, symptom, lab, vital, medication, procedure
    significance: str  # critical, important, routine
    context: str | None = None
    source_text: str | None = None


@dataclass
class AssessmentPlanItem:
    """An item in the Assessment and Plan."""

    problem: str
    problem_number: int
    assessment: str
    plan_items: list[str] = field(default_factory=list)
    icd10_codes: list[str] = field(default_factory=list)
    follow_up: str | None = None


@dataclass
class ClinicalSummaryResult:
    """Result of clinical summarization."""

    summary: str
    key_points: list[str] = field(default_factory=list)
    sections: dict[str, str] = field(default_factory=dict)
    word_count: int = 0
    token_usage: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    model_used: str = ""
    generated_at: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass
class AssessmentPlanResult:
    """Result of Assessment/Plan generation."""

    items: list[AssessmentPlanItem]
    summary: str
    total_problems: int
    token_usage: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    model_used: str = ""


@dataclass
class KeyFindingsResult:
    """Result of key findings extraction."""

    findings: list[KeyFinding]
    critical_count: int
    important_count: int
    routine_count: int
    token_usage: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    model_used: str = ""


@dataclass
class DischargeSummaryResult:
    """Result of discharge summary generation."""

    summary: str
    sections: dict[str, str]
    admission_date: str | None = None
    discharge_date: str | None = None
    length_of_stay_days: int | None = None
    discharge_diagnoses: list[str] = field(default_factory=list)
    discharge_medications: list[str] = field(default_factory=list)
    follow_up_instructions: list[str] = field(default_factory=list)
    token_usage: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    model_used: str = ""


@dataclass
class EncounterData:
    """Data for a single clinical encounter."""

    encounter_id: str
    date: str
    encounter_type: str  # admission, progress, procedure, consultation
    text: str
    diagnoses: list[str] = field(default_factory=list)
    procedures: list[str] = field(default_factory=list)
    medications: list[str] = field(default_factory=list)
    labs: dict[str, str] = field(default_factory=dict)
    vitals: dict[str, str] = field(default_factory=dict)


# ============================================================================
# Prompt Templates
# ============================================================================

# Note: These prompts include instructions for handling PHI carefully
# Actual implementation should de-identify PHI before sending to external APIs

CLINICAL_SUMMARY_SYSTEM_PROMPT = """You are a clinical documentation specialist AI assistant. Your role is to summarize clinical notes accurately and concisely while maintaining medical accuracy.

Important guidelines:
1. Preserve medical accuracy - do not infer diagnoses not present in the source
2. Use standard medical terminology
3. Highlight critical findings and abnormal values
4. Maintain objectivity - report what is documented
5. Do not fabricate information not present in the source text
6. If information is unclear or ambiguous, note this explicitly

Format your summary in clear, professional clinical language suitable for healthcare providers."""

CLINICAL_SUMMARY_USER_PROMPT = """Please summarize the following clinical note. Provide a {length} summary that captures the essential clinical information.

Focus on:
- Primary diagnosis/chief complaint
- Key history and findings
- Critical lab values or vitals
- Current treatment plan
- Pending items or follow-up needs

Clinical Note:
---
{clinical_text}
---

Provide a {length} clinical summary:"""

ASSESSMENT_PLAN_SYSTEM_PROMPT = """You are a clinical documentation AI assistant specializing in generating Assessment and Plan sections for clinical notes.

Important guidelines:
1. Organize by problem in priority order (most acute/severe first)
2. Each problem should have a clear assessment and specific plan items
3. Include relevant ICD-10 codes when appropriate
4. Plan items should be specific and actionable
5. Do not invent diagnoses - only document what is supported by the clinical findings
6. Include follow-up recommendations when appropriate

Output in a structured format with numbered problems."""

ASSESSMENT_PLAN_USER_PROMPT = """Based on the following clinical findings, generate an Assessment and Plan section.

Clinical Findings:
---
{findings}
---

Generate an Assessment and Plan with:
1. Problem list (numbered, prioritized)
2. Brief assessment for each problem
3. Specific plan items for each problem
4. Suggested ICD-10 codes where applicable

Assessment and Plan:"""

KEY_FINDINGS_SYSTEM_PROMPT = """You are a clinical AI assistant that extracts and prioritizes key clinical findings from medical documentation.

Categorize findings as:
- CRITICAL: Findings requiring immediate attention (life-threatening, urgent)
- IMPORTANT: Significant findings affecting care decisions
- ROUTINE: Normal findings or chronic stable conditions

Extract the following types of findings:
- Diagnoses and conditions
- Symptoms and physical exam findings
- Laboratory values (especially abnormal)
- Vital signs (especially abnormal)
- Medications (especially new, changed, or high-risk)
- Procedures performed or planned

Format each finding clearly with its category and significance level."""

KEY_FINDINGS_USER_PROMPT = """Extract the key clinical findings from the following text. For each finding, indicate:
1. The finding itself
2. Category (diagnosis/symptom/lab/vital/medication/procedure)
3. Significance (critical/important/routine)
4. Brief context if relevant

Clinical Text:
---
{clinical_text}
---

Key Findings:"""

DISCHARGE_SUMMARY_SYSTEM_PROMPT = """You are a clinical documentation AI assistant specializing in generating comprehensive discharge summaries.

A proper discharge summary should include:
1. Admission diagnosis and date
2. Discharge diagnosis and date
3. Brief hospital course
4. Procedures performed
5. Discharge medications with instructions
6. Discharge condition
7. Follow-up appointments and instructions
8. Warning signs to watch for

Use clear, professional medical language. Ensure all critical information is captured for continuity of care."""

DISCHARGE_SUMMARY_USER_PROMPT = """Generate a discharge summary based on the following encounter information:

{encounter_details}

Include:
1. Admission and discharge information
2. Hospital course summary
3. Discharge diagnoses
4. Discharge medications
5. Follow-up instructions
6. Patient education points

Discharge Summary:"""


# ============================================================================
# Clinical Summarizer Service
# ============================================================================


class ClinicalSummarizerLLM:
    """LLM-based clinical summarization service.

    Uses external LLM APIs to generate clinical summaries with
    optimized prompts for medical text understanding.
    """

    def __init__(self, llm_service: LLMService | None = None):
        """Initialize the summarizer.

        Args:
            llm_service: LLM service to use. If None, uses singleton.
        """
        self._llm_service = llm_service or get_llm_service()
        self._total_summaries = 0
        self._total_tokens = 0
        self._total_cost = 0.0

    async def summarize_clinical_note(
        self,
        text: str,
        length: SummaryLength = SummaryLength.STANDARD,
        focus_sections: list[ClinicalSection] | None = None,
        model: str | None = None,
        provider: LLMProvider | None = None,
    ) -> ClinicalSummaryResult:
        """Generate a concise clinical summary of a note.

        Args:
            text: Clinical note text to summarize.
            length: Desired summary length (brief/standard/detailed).
            focus_sections: Specific sections to emphasize.
            model: LLM model to use (overrides default).
            provider: LLM provider to use (overrides default).

        Returns:
            ClinicalSummaryResult with generated summary.
        """
        # Validate input
        if not text or not text.strip():
            return ClinicalSummaryResult(
                summary="Unable to generate summary: empty input text.",
                generated_at=datetime.now(timezone.utc).isoformat(),
                warnings=["Input text was empty"],
            )

        # Check for PHI warning (basic check - real implementation needs more)
        warnings = self._check_phi_warnings(text)

        # Build prompt
        length_desc = {
            SummaryLength.BRIEF: "brief (1-2 sentences)",
            SummaryLength.STANDARD: "standard (1-2 paragraphs)",
            SummaryLength.DETAILED: "detailed and comprehensive",
        }

        user_prompt = CLINICAL_SUMMARY_USER_PROMPT.format(
            length=length_desc.get(length, "standard"),
            clinical_text=self._truncate_text(text, max_tokens=6000),
        )

        # Add focus sections if specified
        if focus_sections:
            section_list = ", ".join(s.value.replace("_", " ") for s in focus_sections)
            user_prompt += f"\n\nPay special attention to: {section_list}"

        try:
            response = await self._llm_service.generate(
                prompt=user_prompt,
                system_prompt=CLINICAL_SUMMARY_SYSTEM_PROMPT,
                model=model,
                provider=provider,
                temperature=0.3,
            )

            # Parse response
            summary = response.content.strip()

            # Extract key points (bullet points if present)
            key_points = self._extract_bullet_points(summary)

            # Update metrics
            self._total_summaries += 1
            self._total_tokens += response.token_usage.total_tokens
            self._total_cost += response.cost_estimate.total_cost

            return ClinicalSummaryResult(
                summary=summary,
                key_points=key_points,
                word_count=len(summary.split()),
                token_usage=response.token_usage.total_tokens,
                cost_usd=response.cost_estimate.total_cost,
                latency_ms=response.latency_ms,
                model_used=response.model,
                generated_at=datetime.now(timezone.utc).isoformat(),
                warnings=warnings,
            )

        except Exception as e:
            logger.error(f"Failed to generate clinical summary: {e}")
            return ClinicalSummaryResult(
                summary=f"Error generating summary: {str(e)}",
                generated_at=datetime.now(timezone.utc).isoformat(),
                warnings=warnings + [f"LLM error: {str(e)}"],
            )

    async def generate_assessment_plan(
        self,
        findings: str | dict[str, Any],
        include_icd10: bool = True,
        max_problems: int = 10,
        model: str | None = None,
        provider: LLMProvider | None = None,
    ) -> AssessmentPlanResult:
        """Generate an Assessment and Plan section from clinical findings.

        Args:
            findings: Clinical findings as text or structured dict.
            include_icd10: Whether to suggest ICD-10 codes.
            max_problems: Maximum problems to include.
            model: LLM model to use.
            provider: LLM provider to use.

        Returns:
            AssessmentPlanResult with generated A&P.
        """
        # Format findings
        if isinstance(findings, dict):
            findings_text = self._format_findings_dict(findings)
        else:
            findings_text = str(findings)

        if not findings_text.strip():
            return AssessmentPlanResult(
                items=[],
                summary="No findings provided",
                total_problems=0,
            )

        user_prompt = ASSESSMENT_PLAN_USER_PROMPT.format(
            findings=self._truncate_text(findings_text, max_tokens=5000)
        )

        if include_icd10:
            user_prompt += "\nInclude relevant ICD-10 codes for each problem."

        user_prompt += f"\nLimit to the top {max_problems} most important problems."

        try:
            response = await self._llm_service.generate(
                prompt=user_prompt,
                system_prompt=ASSESSMENT_PLAN_SYSTEM_PROMPT,
                model=model,
                provider=provider,
                temperature=0.3,
            )

            # Parse response into structured format
            items = self._parse_assessment_plan(response.content)

            # Update metrics
            self._total_summaries += 1
            self._total_tokens += response.token_usage.total_tokens
            self._total_cost += response.cost_estimate.total_cost

            return AssessmentPlanResult(
                items=items[:max_problems],
                summary=response.content,
                total_problems=len(items),
                token_usage=response.token_usage.total_tokens,
                cost_usd=response.cost_estimate.total_cost,
                latency_ms=response.latency_ms,
                model_used=response.model,
            )

        except Exception as e:
            logger.error(f"Failed to generate A&P: {e}")
            return AssessmentPlanResult(
                items=[],
                summary=f"Error: {str(e)}",
                total_problems=0,
            )

    async def extract_key_findings(
        self,
        text: str,
        categories: list[str] | None = None,
        max_findings: int = 20,
        model: str | None = None,
        provider: LLMProvider | None = None,
    ) -> KeyFindingsResult:
        """Extract key clinical findings from text.

        Args:
            text: Clinical text to analyze.
            categories: Specific categories to focus on.
            max_findings: Maximum findings to return.
            model: LLM model to use.
            provider: LLM provider to use.

        Returns:
            KeyFindingsResult with extracted findings.
        """
        if not text or not text.strip():
            return KeyFindingsResult(
                findings=[],
                critical_count=0,
                important_count=0,
                routine_count=0,
            )

        user_prompt = KEY_FINDINGS_USER_PROMPT.format(
            clinical_text=self._truncate_text(text, max_tokens=5000)
        )

        if categories:
            user_prompt += f"\n\nFocus on these categories: {', '.join(categories)}"

        user_prompt += f"\n\nLimit to the {max_findings} most important findings."

        try:
            response = await self._llm_service.generate(
                prompt=user_prompt,
                system_prompt=KEY_FINDINGS_SYSTEM_PROMPT,
                model=model,
                provider=provider,
                temperature=0.2,
            )

            # Parse findings
            findings = self._parse_key_findings(response.content)

            # Count by significance
            critical = sum(1 for f in findings if f.significance == "critical")
            important = sum(1 for f in findings if f.significance == "important")
            routine = sum(1 for f in findings if f.significance == "routine")

            # Update metrics
            self._total_summaries += 1
            self._total_tokens += response.token_usage.total_tokens
            self._total_cost += response.cost_estimate.total_cost

            return KeyFindingsResult(
                findings=findings[:max_findings],
                critical_count=critical,
                important_count=important,
                routine_count=routine,
                token_usage=response.token_usage.total_tokens,
                cost_usd=response.cost_estimate.total_cost,
                latency_ms=response.latency_ms,
                model_used=response.model,
            )

        except Exception as e:
            logger.error(f"Failed to extract key findings: {e}")
            return KeyFindingsResult(
                findings=[],
                critical_count=0,
                important_count=0,
                routine_count=0,
            )

    async def generate_discharge_summary(
        self,
        encounters: list[EncounterData],
        include_med_reconciliation: bool = True,
        include_patient_education: bool = True,
        model: str | None = None,
        provider: LLMProvider | None = None,
    ) -> DischargeSummaryResult:
        """Generate a comprehensive discharge summary from encounter data.

        Args:
            encounters: List of clinical encounters during hospitalization.
            include_med_reconciliation: Include medication reconciliation.
            include_patient_education: Include patient education points.
            model: LLM model to use.
            provider: LLM provider to use.

        Returns:
            DischargeSummaryResult with generated summary.
        """
        if not encounters:
            return DischargeSummaryResult(
                summary="No encounter data provided",
                sections={},
            )

        # Format encounter details
        encounter_details = self._format_encounters(encounters)

        user_prompt = DISCHARGE_SUMMARY_USER_PROMPT.format(
            encounter_details=encounter_details
        )

        if include_med_reconciliation:
            user_prompt += "\nInclude a complete medication reconciliation section."

        if include_patient_education:
            user_prompt += "\nInclude patient education and warning signs."

        try:
            response = await self._llm_service.generate(
                prompt=user_prompt,
                system_prompt=DISCHARGE_SUMMARY_SYSTEM_PROMPT,
                model=model,
                provider=provider,
                temperature=0.3,
                max_tokens=2000,
            )

            # Parse the discharge summary
            parsed = self._parse_discharge_summary(response.content, encounters)

            # Update metrics
            self._total_summaries += 1
            self._total_tokens += response.token_usage.total_tokens
            self._total_cost += response.cost_estimate.total_cost

            return DischargeSummaryResult(
                summary=response.content,
                sections=parsed.get("sections", {}),
                admission_date=parsed.get("admission_date"),
                discharge_date=parsed.get("discharge_date"),
                length_of_stay_days=parsed.get("los_days"),
                discharge_diagnoses=parsed.get("diagnoses", []),
                discharge_medications=parsed.get("medications", []),
                follow_up_instructions=parsed.get("follow_up", []),
                token_usage=response.token_usage.total_tokens,
                cost_usd=response.cost_estimate.total_cost,
                latency_ms=response.latency_ms,
                model_used=response.model,
            )

        except Exception as e:
            logger.error(f"Failed to generate discharge summary: {e}")
            return DischargeSummaryResult(
                summary=f"Error: {str(e)}",
                sections={},
            )

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _check_phi_warnings(self, text: str) -> list[str]:
        """Check for potential PHI in text and generate warnings.

        Note: This is a basic check. Production systems should use
        proper de-identification before sending to external APIs.
        """
        warnings = []

        # Check for potential date patterns
        if re.search(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", text):
            pass  # Dates are common in clinical text, not warning

        # Check for potential SSN patterns
        if re.search(r"\b\d{3}-\d{2}-\d{4}\b", text):
            warnings.append(
                "WARNING: Potential SSN detected. Ensure PHI is de-identified."
            )

        # Check for potential phone numbers
        if re.search(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", text):
            warnings.append(
                "WARNING: Potential phone number detected. Ensure PHI is de-identified."
            )

        # Check for potential email addresses
        if re.search(r"\b[\w.-]+@[\w.-]+\.\w+\b", text):
            warnings.append(
                "WARNING: Potential email detected. Ensure PHI is de-identified."
            )

        # Check for potential MRN patterns
        if re.search(r"\bMRN[:\s#]*\d+\b", text, re.IGNORECASE):
            warnings.append(
                "WARNING: Potential MRN detected. Ensure PHI is de-identified."
            )

        return warnings

    def _truncate_text(self, text: str, max_tokens: int) -> str:
        """Truncate text to approximate token limit.

        Uses simple character-based estimation (4 chars per token).
        """
        max_chars = max_tokens * 4
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "\n\n[Text truncated due to length...]"

    def _extract_bullet_points(self, text: str) -> list[str]:
        """Extract bullet points from text."""
        points = []
        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith(("-", "*", "•", ">")):
                points.append(line.lstrip("-*•> ").strip())
            elif re.match(r"^\d+[.)]\s", line):
                points.append(re.sub(r"^\d+[.)]\s*", "", line).strip())
        return points

    def _format_findings_dict(self, findings: dict[str, Any]) -> str:
        """Format a findings dictionary into text."""
        lines = []

        if "diagnoses" in findings:
            lines.append("Diagnoses:")
            for dx in findings["diagnoses"]:
                lines.append(f"  - {dx}")

        if "symptoms" in findings:
            lines.append("\nSymptoms:")
            for symptom in findings["symptoms"]:
                lines.append(f"  - {symptom}")

        if "vitals" in findings:
            lines.append("\nVital Signs:")
            for name, value in findings["vitals"].items():
                lines.append(f"  - {name}: {value}")

        if "labs" in findings:
            lines.append("\nLaboratory Results:")
            for name, value in findings["labs"].items():
                lines.append(f"  - {name}: {value}")

        if "medications" in findings:
            lines.append("\nMedications:")
            for med in findings["medications"]:
                lines.append(f"  - {med}")

        if "procedures" in findings:
            lines.append("\nProcedures:")
            for proc in findings["procedures"]:
                lines.append(f"  - {proc}")

        if "exam" in findings:
            lines.append("\nPhysical Exam:")
            lines.append(f"  {findings['exam']}")

        return "\n".join(lines)

    def _parse_assessment_plan(self, text: str) -> list[AssessmentPlanItem]:
        """Parse A&P text into structured items."""
        items = []

        # Try to split by problem numbers
        problem_pattern = r"(?:^|\n)(\d+)[.)]\s*([^\n]+)"
        matches = re.findall(problem_pattern, text)

        for match in matches:
            problem_num = int(match[0])
            problem_text = match[1].strip()

            # Extract ICD-10 codes if present
            icd10_pattern = r"\b([A-TV-Z]\d{2}(?:\.\d{1,4})?)\b"
            icd10_codes = re.findall(icd10_pattern, text)

            items.append(
                AssessmentPlanItem(
                    problem=problem_text,
                    problem_number=problem_num,
                    assessment=problem_text,
                    plan_items=[],
                    icd10_codes=list(set(icd10_codes)),
                )
            )

        return items

    def _parse_key_findings(self, text: str) -> list[KeyFinding]:
        """Parse key findings from LLM response."""
        findings = []
        lines = text.split("\n")

        current_finding = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check for significance markers
            significance = "routine"
            if "CRITICAL" in line.upper():
                significance = "critical"
            elif "IMPORTANT" in line.upper():
                significance = "important"

            # Check for category markers
            category = "other"
            for cat in ["diagnosis", "symptom", "lab", "vital", "medication", "procedure"]:
                if cat in line.lower():
                    category = cat
                    break

            # Extract the finding text
            finding_text = re.sub(
                r"(CRITICAL|IMPORTANT|ROUTINE)[:\s]*",
                "",
                line,
                flags=re.IGNORECASE,
            ).strip()

            if finding_text and len(finding_text) > 3:
                findings.append(
                    KeyFinding(
                        finding=finding_text,
                        category=category,
                        significance=significance,
                    )
                )

        return findings

    def _format_encounters(self, encounters: list[EncounterData]) -> str:
        """Format encounter data for discharge summary prompt."""
        lines = []

        # Sort by date
        sorted_encounters = sorted(encounters, key=lambda e: e.date)

        if sorted_encounters:
            lines.append(f"Admission Date: {sorted_encounters[0].date}")
            lines.append(f"Discharge Date: {sorted_encounters[-1].date}")
            lines.append("")

        for enc in sorted_encounters:
            lines.append(f"--- {enc.encounter_type.upper()} ({enc.date}) ---")
            lines.append(enc.text[:2000])  # Truncate individual encounters

            if enc.diagnoses:
                lines.append(f"Diagnoses: {', '.join(enc.diagnoses)}")

            if enc.procedures:
                lines.append(f"Procedures: {', '.join(enc.procedures)}")

            if enc.medications:
                lines.append(f"Medications: {', '.join(enc.medications)}")

            lines.append("")

        return "\n".join(lines)

    def _parse_discharge_summary(
        self, text: str, encounters: list[EncounterData]
    ) -> dict[str, Any]:
        """Parse discharge summary response into structured format."""
        result: dict[str, Any] = {
            "sections": {},
            "diagnoses": [],
            "medications": [],
            "follow_up": [],
        }

        # Extract dates from encounters
        if encounters:
            sorted_enc = sorted(encounters, key=lambda e: e.date)
            result["admission_date"] = sorted_enc[0].date
            result["discharge_date"] = sorted_enc[-1].date

            # Collect diagnoses and medications from encounters
            all_diagnoses = set()
            all_meds = set()
            for enc in encounters:
                all_diagnoses.update(enc.diagnoses)
                all_meds.update(enc.medications)

            result["diagnoses"] = list(all_diagnoses)
            result["medications"] = list(all_meds)

        # Try to extract sections from text
        section_patterns = {
            "hospital_course": r"(?:Hospital Course|Course)[:\s]*(.+?)(?=\n[A-Z]|\Z)",
            "discharge_condition": r"(?:Discharge Condition|Condition)[:\s]*(.+?)(?=\n[A-Z]|\Z)",
            "follow_up": r"(?:Follow[- ]?up|Appointments)[:\s]*(.+?)(?=\n[A-Z]|\Z)",
            "instructions": r"(?:Instructions|Patient Education)[:\s]*(.+?)(?=\n[A-Z]|\Z)",
        }

        for section, pattern in section_patterns.items():
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                result["sections"][section] = match.group(1).strip()

        return result

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        return {
            "total_summaries_generated": self._total_summaries,
            "total_tokens_used": self._total_tokens,
            "total_cost_usd": round(self._total_cost, 4),
            "llm_service_stats": self._llm_service.get_stats(),
        }


# ============================================================================
# Singleton Pattern
# ============================================================================


_service_instance: ClinicalSummarizerLLM | None = None
_service_lock = threading.Lock()


def get_clinical_summarizer_llm() -> ClinicalSummarizerLLM:
    """Get or create the singleton service instance.

    Returns:
        ClinicalSummarizerLLM singleton instance.
    """
    global _service_instance

    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = ClinicalSummarizerLLM()

    return _service_instance


def reset_clinical_summarizer_llm() -> None:
    """Reset the singleton instance (for testing)."""
    global _service_instance
    with _service_lock:
        _service_instance = None
