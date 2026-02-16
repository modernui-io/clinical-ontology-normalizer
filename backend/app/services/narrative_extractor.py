"""Clinical Narrative Extraction Service.

Extracts structured clinical narratives from clinical text using LLM:
- Admission reason (primary problem, contributing factors)
- Hospital course (summary, key events with temporal ordering)
- Discharge plan (disposition, follow-up, restrictions)

The extraction is grounded in pre-extracted entities to prevent hallucination.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class AdmissionReason:
    """Structured admission reason."""

    primary_problem: str
    contributing_factors: list[str] = field(default_factory=list)
    presenting_symptoms: list[str] = field(default_factory=list)
    linked_condition_texts: list[str] = field(default_factory=list)
    admission_date: str | None = None
    admission_source: str | None = None  # ER, transfer, elective, etc.

    def to_dict(self) -> dict:
        return {
            "primary_problem": self.primary_problem,
            "contributing_factors": self.contributing_factors,
            "presenting_symptoms": self.presenting_symptoms,
            "linked_condition_texts": self.linked_condition_texts,
            "admission_date": self.admission_date,
            "admission_source": self.admission_source,
        }


@dataclass
class ClinicalEvent:
    """A key event during hospitalization."""

    event_text: str
    event_type: str  # intervention, complication, finding, procedure, etc.
    event_date: str | None = None
    relative_day: int | None = None  # Day of hospitalization (1, 2, 3, etc.)
    caused_by: str | None = None  # What caused this event
    resulted_in: str | None = None  # What this event caused
    linked_entity_texts: list[str] = field(default_factory=list)
    severity: str | None = None  # mild, moderate, severe

    def to_dict(self) -> dict:
        return {
            "event_text": self.event_text,
            "event_type": self.event_type,
            "event_date": self.event_date,
            "relative_day": self.relative_day,
            "caused_by": self.caused_by,
            "resulted_in": self.resulted_in,
            "linked_entity_texts": self.linked_entity_texts,
            "severity": self.severity,
        }


@dataclass
class HospitalCourse:
    """Structured hospital course summary."""

    summary: str
    key_events: list[ClinicalEvent] = field(default_factory=list)
    interventions: list[str] = field(default_factory=list)
    complications: list[str] = field(default_factory=list)
    response_to_treatment: str | None = None
    length_of_stay_days: int | None = None

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "key_events": [e.to_dict() for e in self.key_events],
            "interventions": self.interventions,
            "complications": self.complications,
            "response_to_treatment": self.response_to_treatment,
            "length_of_stay_days": self.length_of_stay_days,
        }


@dataclass
class DischargePlan:
    """Structured discharge plan."""

    disposition: str  # home, SNF, rehab, hospice, etc.
    discharge_date: str | None = None
    follow_up_appointments: list[str] = field(default_factory=list)
    discharge_medications: list[str] = field(default_factory=list)
    activity_restrictions: list[str] = field(default_factory=list)
    diet_instructions: str | None = None
    wound_care: str | None = None
    return_precautions: list[str] = field(default_factory=list)
    pending_results: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "disposition": self.disposition,
            "discharge_date": self.discharge_date,
            "follow_up_appointments": self.follow_up_appointments,
            "discharge_medications": self.discharge_medications,
            "activity_restrictions": self.activity_restrictions,
            "diet_instructions": self.diet_instructions,
            "wound_care": self.wound_care,
            "return_precautions": self.return_precautions,
            "pending_results": self.pending_results,
        }


@dataclass
class ClinicalEpisode:
    """A single clinical encounter/episode (e.g., one hospitalization)."""

    episode_label: str = ""  # e.g., "AFib with RVR", "Fall with Subdural Hematoma"
    episode_date: str | None = None
    admission_reason: AdmissionReason | None = None
    hospital_course: HospitalCourse | None = None
    discharge_plan: DischargePlan | None = None

    def to_dict(self) -> dict:
        return {
            "episode_label": self.episode_label,
            "episode_date": self.episode_date,
            "admission_reason": self.admission_reason.to_dict() if self.admission_reason else None,
            "hospital_course": self.hospital_course.to_dict() if self.hospital_course else None,
            "discharge_plan": self.discharge_plan.to_dict() if self.discharge_plan else None,
        }


@dataclass
class ClinicalNarrative:
    """Complete clinical narrative extraction result."""

    admission_reason: AdmissionReason | None = None
    hospital_course: HospitalCourse | None = None
    discharge_plan: DischargePlan | None = None
    episodes: list[ClinicalEpisode] = field(default_factory=list)
    extraction_confidence: float = 0.0
    extraction_method: str = "llm"

    def to_dict(self) -> dict:
        return {
            "admission_reason": self.admission_reason.to_dict() if self.admission_reason else None,
            "hospital_course": self.hospital_course.to_dict() if self.hospital_course else None,
            "discharge_plan": self.discharge_plan.to_dict() if self.discharge_plan else None,
            "episodes": [e.to_dict() for e in self.episodes],
            "extraction_confidence": self.extraction_confidence,
            "extraction_method": self.extraction_method,
        }


NARRATIVE_EXTRACTION_PROMPT = '''You are a clinical documentation specialist. Extract structured narrative information from the following clinical text.

The patient has the following pre-extracted entities (use these to ground your extraction - do not hallucinate new conditions/medications):
{entities_context}

This text may contain MULTIPLE hospital encounters/admissions. Extract ALL distinct admissions/encounters as separate episodes.

For EACH episode/encounter found in the text, extract:

1. EPISODE IDENTIFICATION:
   - episode_label: Short descriptive label (e.g., "AFib with RVR", "Fall with Subdural Hematoma", "Annual Wellness Visit")
   - episode_date: Approximate date of this encounter if mentioned

2. ADMISSION_REASON:
   - primary_problem: The main reason for this admission/encounter
   - contributing_factors: Other factors that led to admission
   - presenting_symptoms: Symptoms at presentation
   - linked_condition_texts: Which of the pre-extracted conditions are related (use exact text from entities)
   - admission_date: Date of admission if mentioned
   - admission_source: How they arrived (ER, transfer, elective, etc.)

3. HOSPITAL_COURSE:
   - summary: Brief summary of what happened during this encounter (2-3 sentences)
   - key_events: List of significant events in chronological order, each with:
     - event_text: Description of the event
     - event_type: One of [intervention, complication, finding, procedure, improvement, decline]
     - relative_day: Day of hospitalization (1, 2, 3, etc.) if determinable
     - caused_by: What caused this event (if clear causal link)
     - resulted_in: What this event led to (if clear causal link)
     - linked_entity_texts: Related pre-extracted entities (exact text)
     - severity: mild, moderate, or severe (if applicable)
   - interventions: List of treatments/procedures performed
   - complications: List of complications that occurred
   - response_to_treatment: How patient responded (improving, stable, declining, etc.)
   - length_of_stay_days: Number of days if determinable

4. DISCHARGE_PLAN:
   - disposition: Where patient is going (home, SNF, rehab, hospice, etc.)
   - discharge_date: Date of discharge if mentioned
   - follow_up_appointments: List of follow-up appointments
   - discharge_medications: Medications at discharge (use pre-extracted medication names)
   - activity_restrictions: Any activity limitations
   - diet_instructions: Dietary guidance
   - wound_care: Wound care instructions if applicable
   - return_precautions: Signs/symptoms to return for
   - pending_results: Any pending test results

IMPORTANT:
- Extract ALL distinct hospital admissions/encounters as separate episodes
- Order episodes chronologically (earliest first)
- Only extract information that is explicitly stated in the text
- Link entities using the EXACT text from the pre-extracted entities list
- If a component is not present for an episode, set it to null
- For key_events, maintain chronological order within each episode
- Be precise with causal relationships (caused_by, resulted_in) - only include if clearly stated
- Outpatient visits (wellness checks, follow-ups) can be episodes too if they have clinical narrative

Return JSON in this exact format:
{{
  "episodes": [
    {{
      "episode_label": "Short label for this encounter",
      "episode_date": "date or null",
      "admission_reason": {{ ... }} or null,
      "hospital_course": {{ ... }} or null,
      "discharge_plan": {{ ... }} or null
    }}
  ],
  "confidence": 0.0-1.0
}}

Clinical text to analyze:
"""
{text}
"""

Return ONLY the JSON object, no other text.'''


class NarrativeExtractorService:
    """Service for extracting clinical narratives using LLM."""

    def __init__(self):
        self._ollama_available = False
        self._claude_available = False
        self._ollama_url = "http://host.docker.internal:11434"
        self._ollama_model = "cniongolo/biomistral:latest"
        self._claude_client: Any = None
        self._init_services()

    def _init_services(self) -> None:
        """Initialize available LLM services."""
        # Try Ollama first
        try:
            urls_to_try = [
                "http://host.docker.internal:11434",
                "http://localhost:11434",
                "http://127.0.0.1:11434",
            ]
            with httpx.Client(timeout=5.0) as client:
                for url in urls_to_try:
                    try:
                        response = client.get(f"{url}/api/tags")
                        if response.status_code == 200:
                            self._ollama_url = url
                            models = response.json().get("models", [])
                            model_names = [m.get("name", "") for m in models]

                            # Prefer medical models for narrative extraction
                            preferred_models = [
                                "alibayram/medgemma:27b",
                                "cniongolo/biomistral:latest",
                                "meditron:7b",
                                "mistral:7b",
                                "llama3.1:latest",
                            ]
                            for model in preferred_models:
                                if model in model_names:
                                    self._ollama_model = model
                                    break

                            self._ollama_available = True
                            logger.info(f"Narrative extractor: Ollama available at {url}")
                            break
                    except Exception:
                        continue
        except Exception as e:
            logger.warning(f"Ollama not available for narrative extraction: {e}")

        # Try Claude API — check BYOK override first, then system default
        api_key = settings.anthropic_api_key
        try:
            from app.api.llm_settings import get_byok_config
            byok = get_byok_config()
            if byok and byok.get("api_key") and byok.get("provider") == "anthropic":
                api_key = byok["api_key"]
                logger.info("Narrative extractor: using BYOK API key")
        except ImportError:
            pass  # llm_settings not available yet during early init

        if api_key:
            try:
                import anthropic
                self._claude_client = anthropic.Anthropic(api_key=api_key)
                self._claude_available = True
                logger.info("Narrative extractor: Claude API available")
            except Exception as e:
                logger.warning(f"Claude API not available: {e}")

    @property
    def is_available(self) -> bool:
        """Check if any LLM service is available."""
        return self._ollama_available or self._claude_available

    def _format_entities_context(self, entities: list[dict]) -> str:
        """Format pre-extracted entities for the prompt."""
        if not entities:
            return "No pre-extracted entities available."

        lines = ["Pre-extracted entities:"]
        by_type: dict[str, list[str]] = {}

        for entity in entities:
            etype = entity.get("entity_type", entity.get("type", "unknown"))
            text = entity.get("text", "")
            assertion = entity.get("assertion", "present")

            if etype not in by_type:
                by_type[etype] = []
            by_type[etype].append(f"{text} ({assertion})")

        for etype, items in sorted(by_type.items()):
            lines.append(f"- {etype.upper()}: {', '.join(items[:20])}")

        return "\n".join(lines)

    def _call_ollama(self, prompt: str) -> str | None:
        """Call Ollama API for narrative extraction."""
        try:
            with httpx.Client(timeout=180.0) as client:
                response = client.post(
                    f"{self._ollama_url}/api/generate",
                    json={
                        "model": self._ollama_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.0,
                            "num_predict": 4096,
                        },
                    },
                )
                response.raise_for_status()
                return response.json().get("response", "")
        except Exception as e:
            logger.error(f"Ollama narrative extraction failed: {e}")
            return None

    def _call_claude(self, prompt: str) -> str | None:
        """Call Claude API for narrative extraction."""
        if not self._claude_client:
            return None

        # Check for BYOK model override
        model = settings.llm_model
        try:
            from app.api.llm_settings import get_byok_config
            byok = get_byok_config()
            if byok and byok.get("model") and byok.get("provider") == "anthropic":
                model = byok["model"]
        except ImportError:
            pass

        try:
            message = self._claude_client.messages.create(
                model=model,
                max_tokens=16384,
                temperature=0.0,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text if message.content else None
        except Exception as e:
            logger.error(f"Claude narrative extraction failed: {e}")
            return None

    def _parse_llm_response(self, response: str) -> dict | None:
        """Parse LLM JSON response."""
        if not response:
            return None

        # Try to extract JSON from response
        try:
            # First try direct parse
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Strip markdown code fences (```json ... ``` or ``` ... ```)
        stripped = response.strip()
        if stripped.startswith("```"):
            # Remove opening fence (```json or ```)
            first_newline = stripped.find("\n")
            if first_newline > 0:
                stripped = stripped[first_newline + 1:]
            # Remove closing fence
            if stripped.rstrip().endswith("```"):
                stripped = stripped.rstrip()[:-3].rstrip()
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                pass

        # Try to find JSON object in response (greedy match)
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        logger.warning(
            "Failed to parse LLM response as JSON (length=%d, first 200 chars: %s)",
            len(response), response[:200]
        )
        return None

    def extract_narrative(
        self,
        text: str,
        entities: list[dict] | None = None,
        prefer_model: str | None = None,
    ) -> ClinicalNarrative:
        """Extract clinical narrative from text.

        Args:
            text: Clinical note text
            entities: Pre-extracted entities to ground the extraction
            prefer_model: Preferred model ("claude" or "ollama")

        Returns:
            ClinicalNarrative with extracted components
        """
        if not self.is_available:
            logger.warning("No LLM service available for narrative extraction")
            return ClinicalNarrative()

        # Build prompt with entities context
        entities_context = self._format_entities_context(entities or [])
        prompt = NARRATIVE_EXTRACTION_PROMPT.format(
            entities_context=entities_context,
            text=text[:80000],  # Limit text length (supports ~50 clinical notes)
        )

        # Determine which service to use
        prefer = prefer_model or settings.narrative_extraction_model
        response = None

        if prefer == "claude" and self._claude_available:
            response = self._call_claude(prompt)
            extraction_method = "claude"
        elif self._ollama_available:
            response = self._call_ollama(prompt)
            extraction_method = "ollama"
        elif self._claude_available:
            response = self._call_claude(prompt)
            extraction_method = "claude"
        else:
            return ClinicalNarrative()

        # Parse response
        parsed = self._parse_llm_response(response) if response else None
        if not parsed:
            return ClinicalNarrative(extraction_method=extraction_method)

        def _ensure_list(val: Any) -> list:
            """Normalize LLM output to list (handles null, string, or list)."""
            if val is None:
                return []
            if isinstance(val, str):
                return [val] if val.strip() else []
            if isinstance(val, list):
                return val
            return []

        # Build narrative object
        narrative = ClinicalNarrative(
            extraction_confidence=parsed.get("confidence", 0.7),
            extraction_method=extraction_method,
        )

        # Parse episodes (new multi-episode format)
        episodes_data = parsed.get("episodes", [])
        if episodes_data:
            for ep_data in episodes_data:
                episode = ClinicalEpisode(
                    episode_label=ep_data.get("episode_label", ""),
                    episode_date=ep_data.get("episode_date"),
                )

                # Parse admission reason for this episode
                if ar := ep_data.get("admission_reason"):
                    episode.admission_reason = AdmissionReason(
                        primary_problem=ar.get("primary_problem", ""),
                        contributing_factors=_ensure_list(ar.get("contributing_factors")),
                        presenting_symptoms=_ensure_list(ar.get("presenting_symptoms")),
                        linked_condition_texts=_ensure_list(ar.get("linked_condition_texts")),
                        admission_date=ar.get("admission_date"),
                        admission_source=ar.get("admission_source"),
                    )

                # Parse hospital course for this episode
                if hc := ep_data.get("hospital_course"):
                    key_events = []
                    for event_data in _ensure_list(hc.get("key_events")):
                        key_events.append(ClinicalEvent(
                            event_text=event_data.get("event_text", ""),
                            event_type=event_data.get("event_type", "finding"),
                            event_date=event_data.get("event_date"),
                            relative_day=event_data.get("relative_day"),
                            caused_by=event_data.get("caused_by"),
                            resulted_in=event_data.get("resulted_in"),
                            linked_entity_texts=_ensure_list(event_data.get("linked_entity_texts")),
                            severity=event_data.get("severity"),
                        ))

                    episode.hospital_course = HospitalCourse(
                        summary=hc.get("summary", ""),
                        key_events=key_events,
                        interventions=_ensure_list(hc.get("interventions")),
                        complications=_ensure_list(hc.get("complications")),
                        response_to_treatment=hc.get("response_to_treatment"),
                        length_of_stay_days=hc.get("length_of_stay_days"),
                    )

                # Parse discharge plan for this episode
                if dp := ep_data.get("discharge_plan"):
                    episode.discharge_plan = DischargePlan(
                        disposition=dp.get("disposition", ""),
                        discharge_date=dp.get("discharge_date"),
                        follow_up_appointments=_ensure_list(dp.get("follow_up_appointments")),
                        discharge_medications=_ensure_list(dp.get("discharge_medications")),
                        activity_restrictions=_ensure_list(dp.get("activity_restrictions")),
                        diet_instructions=dp.get("diet_instructions"),
                        wound_care=dp.get("wound_care"),
                        return_precautions=_ensure_list(dp.get("return_precautions")),
                        pending_results=_ensure_list(dp.get("pending_results")),
                    )

                narrative.episodes.append(episode)

            # Set top-level fields from the last (most recent) episode for backward compat
            if narrative.episodes:
                last_episode = narrative.episodes[-1]
                narrative.admission_reason = last_episode.admission_reason
                narrative.hospital_course = last_episode.hospital_course
                narrative.discharge_plan = last_episode.discharge_plan

        else:
            # Fallback: parse old single-episode format for backward compatibility
            if ar := parsed.get("admission_reason"):
                narrative.admission_reason = AdmissionReason(
                    primary_problem=ar.get("primary_problem", ""),
                    contributing_factors=_ensure_list(ar.get("contributing_factors")),
                    presenting_symptoms=_ensure_list(ar.get("presenting_symptoms")),
                    linked_condition_texts=_ensure_list(ar.get("linked_condition_texts")),
                    admission_date=ar.get("admission_date"),
                    admission_source=ar.get("admission_source"),
                )

            if hc := parsed.get("hospital_course"):
                key_events = []
                for event_data in _ensure_list(hc.get("key_events")):
                    key_events.append(ClinicalEvent(
                        event_text=event_data.get("event_text", ""),
                        event_type=event_data.get("event_type", "finding"),
                        event_date=event_data.get("event_date"),
                        relative_day=event_data.get("relative_day"),
                        caused_by=event_data.get("caused_by"),
                        resulted_in=event_data.get("resulted_in"),
                        linked_entity_texts=_ensure_list(event_data.get("linked_entity_texts")),
                        severity=event_data.get("severity"),
                    ))

                narrative.hospital_course = HospitalCourse(
                    summary=hc.get("summary", ""),
                    key_events=key_events,
                    interventions=_ensure_list(hc.get("interventions")),
                    complications=_ensure_list(hc.get("complications")),
                    response_to_treatment=hc.get("response_to_treatment"),
                    length_of_stay_days=hc.get("length_of_stay_days"),
                )

            if dp := parsed.get("discharge_plan"):
                narrative.discharge_plan = DischargePlan(
                    disposition=dp.get("disposition", ""),
                    discharge_date=dp.get("discharge_date"),
                    follow_up_appointments=_ensure_list(dp.get("follow_up_appointments")),
                    discharge_medications=_ensure_list(dp.get("discharge_medications")),
                    activity_restrictions=_ensure_list(dp.get("activity_restrictions")),
                    diet_instructions=dp.get("diet_instructions"),
                    wound_care=dp.get("wound_care"),
                    return_precautions=_ensure_list(dp.get("return_precautions")),
                    pending_results=_ensure_list(dp.get("pending_results")),
                )

        return narrative


# Singleton instance
_narrative_extractor: NarrativeExtractorService | None = None


def get_narrative_extractor() -> NarrativeExtractorService:
    """Get or create the narrative extractor service singleton."""
    global _narrative_extractor
    if _narrative_extractor is None:
        _narrative_extractor = NarrativeExtractorService()
    return _narrative_extractor
