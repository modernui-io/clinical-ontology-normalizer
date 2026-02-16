"""LLM-based Clinical NLP Extraction Service.

Uses Ollama local models or Anthropic Claude API for clinical entity extraction.
Advantages over local ML models:
- No model loading time
- Handles very long documents
- Better understanding of clinical context
- Works with medical-specific models (MedGemma, BioMistral, Meditron)
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import httpx

logger = logging.getLogger(__name__)

# Entity type mapping
ENTITY_TYPE_MAP = {
    "diagnosis": "diagnosis",
    "condition": "diagnosis",
    "medication": "medication",
    "drug": "medication",
    "procedure": "procedure",
    "lab_result": "lab_result",
    "laboratory": "lab_result",
    "vital_sign": "vital_sign",
    "vitals": "vital_sign",
    "anatomical_location": "anatomical_location",
    "anatomy": "anatomical_location",
    "temporal": "temporal",
    "symptom": "symptom",
    "allergy": "allergy",
    "social_history": "social_history",
}

ASSERTION_MAP = {
    "present": "present",
    "affirmed": "present",
    "positive": "present",
    "absent": "absent",
    "negated": "absent",
    "negative": "absent",
    "denied": "absent",
    "possible": "possible",
    "uncertain": "possible",
    "suspected": "possible",
    "conditional": "conditional",
    "hypothetical": "hypothetical",
    "family_history": "family_history",
    "family": "family_history",
}

EXTRACTION_PROMPT = '''You are a clinical NLP system. Extract medical entities from the following clinical text.

For each entity found, provide:
- text: the exact text span from the document
- type: one of [diagnosis, medication, procedure, lab_result, vital_sign, symptom, allergy, anatomical_location, temporal]
- assertion: one of [present, absent, possible, conditional, hypothetical, family_history]
  - "present" = confirmed/affirmed finding
  - "absent" = negated (e.g., "denies", "no evidence of", "ruled out")
  - "possible" = uncertain (e.g., "possible", "likely", "cannot rule out")
  - "family_history" = refers to family member, not patient
- confidence: 0.0-1.0 score
- start: character offset where entity starts
- end: character offset where entity ends
- normalized_text: standardized form of the entity
- value: for labs/vitals, the numeric value (if present)
- unit: for labs/vitals, the unit (if present)

IMPORTANT:
- Extract ALL clinical entities, not just a few
- Pay attention to negation: "denies chest pain" = assertion "absent"
- Pay attention to uncertainty: "possible pneumonia" = assertion "possible"
- Include medications with dosages when present
- Include lab values with their numeric results
- Include vital signs with their measurements

Return JSON array of entities. Example:
[
  {{"text": "type 2 diabetes", "type": "diagnosis", "assertion": "present", "confidence": 0.95, "start": 45, "end": 60, "normalized_text": "Type 2 Diabetes Mellitus"}},
  {{"text": "denies chest pain", "type": "symptom", "assertion": "absent", "confidence": 0.92, "start": 120, "end": 137, "normalized_text": "Chest Pain"}},
  {{"text": "metformin 1000mg", "type": "medication", "assertion": "present", "confidence": 0.98, "start": 200, "end": 216, "normalized_text": "Metformin", "value": "1000", "unit": "mg"}},
  {{"text": "BP 140/90", "type": "vital_sign", "assertion": "present", "confidence": 0.99, "start": 300, "end": 309, "normalized_text": "Blood Pressure", "value": "140/90", "unit": "mmHg"}}
]

Clinical text to analyze:
"""
{text}
"""

Return ONLY the JSON array, no other text.'''


@dataclass
class LLMExtractedEntity:
    """Entity extracted by LLM."""

    id: str
    entity_type: str
    text: str
    normalized_text: str
    start: int
    end: int
    assertion: str
    confidence: float
    value: str | None = None
    unit: str | None = None
    normalized_codes: list[dict] = field(default_factory=list)


# Backwards compatibility alias
ClaudeExtractedEntity = LLMExtractedEntity


@dataclass
class LLMNLPConfig:
    """Configuration for LLM NLP service."""

    # Ollama settings (primary - no API key needed)
    ollama_base_url: str = "http://host.docker.internal:11434"  # Docker -> host
    ollama_model: str = "cniongolo/biomistral:latest"  # Medical model, fast

    # Claude API settings (fallback)
    claude_model: str = "claude-opus-4-6"
    anthropic_api_key: str | None = None

    max_tokens: int = 8192
    temperature: float = 0.0  # Deterministic for extraction
    timeout: float = 180.0  # 3 minute timeout for long docs


# Backwards compatibility alias
ClaudeNLPConfig = LLMNLPConfig


class LLMNLPService:
    """Clinical NLP service using Ollama or Claude API."""

    def __init__(self, config: LLMNLPConfig | None = None):
        self.config = config or LLMNLPConfig()
        self._ollama_available = False
        self._claude_available = False
        self._claude_client: Any = None
        self._init_services()

    def _init_services(self) -> None:
        """Initialize available LLM services."""
        # Try Ollama first (no API key needed)
        try:
            # Check if Ollama is reachable
            with httpx.Client(timeout=5.0) as client:
                # Try Docker internal URL first
                urls_to_try = [
                    self.config.ollama_base_url,
                    "http://localhost:11434",
                    "http://127.0.0.1:11434",
                ]
                for url in urls_to_try:
                    try:
                        response = client.get(f"{url}/api/tags")
                        if response.status_code == 200:
                            self.config.ollama_base_url = url
                            models = response.json().get("models", [])
                            model_names = [m.get("name", "") for m in models]

                            # Check if our preferred model is available (MedGemma 27B is best)
                            preferred_models = [
                                "alibayram/medgemma:27b",  # Best medical model
                                "cniongolo/biomistral:latest",
                                "meditron:7b",
                                "medllama2:latest",
                                "mistral:7b",
                                "llama3.1:latest",
                            ]
                            for model in preferred_models:
                                if model in model_names:
                                    self.config.ollama_model = model
                                    break

                            self._ollama_available = True
                            logger.info(f"Ollama available at {url} with model {self.config.ollama_model}")
                            break
                    except Exception:
                        continue
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")

        # Try Claude API as fallback — check BYOK override first
        try:
            import anthropic

            api_key = self.config.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")

            # Check BYOK override
            try:
                from app.api.llm_settings import get_byok_config
                byok = get_byok_config()
                if byok and byok.get("api_key") and byok.get("provider") == "anthropic":
                    api_key = byok["api_key"]
                    logger.info("NLP Claude API: using BYOK API key")
            except ImportError:
                pass

            if api_key:
                self._claude_client = anthropic.Anthropic(api_key=api_key)
                self._claude_available = True
                logger.info("Claude API available as fallback")
        except ImportError:
            logger.debug("anthropic package not installed")
        except Exception as e:
            logger.debug(f"Claude API not available: {e}")

    @property
    def is_available(self) -> bool:
        """Check if any LLM service is available."""
        return self._ollama_available or self._claude_available

    def extract_entities(
        self,
        text: str,
        entity_types: list[str] | None = None,
    ) -> tuple[list[LLMExtractedEntity], float]:
        """
        Extract clinical entities from text using available LLM.

        Args:
            text: Clinical text to analyze
            entity_types: Optional filter for entity types

        Returns:
            Tuple of (entities list, processing time in ms)
        """
        if not self.is_available:
            logger.error("No LLM service available")
            return [], 0.0

        start_time = time.perf_counter()
        prompt = EXTRACTION_PROMPT.format(text=text)

        # Try Ollama first
        if self._ollama_available:
            try:
                logger.info(f"Calling Ollama at {self.config.ollama_base_url} with model {self.config.ollama_model}")
                content = self._call_ollama(prompt)
                logger.info(f"Ollama response (first 500 chars): {content[:500]}")
                entities = self._parse_response(content, entity_types)
                processing_time = (time.perf_counter() - start_time) * 1000
                logger.info(f"Ollama extracted {len(entities)} entities in {processing_time:.1f}ms")
                return entities, processing_time
            except Exception as e:
                import traceback
                logger.warning(f"Ollama extraction failed: {e}\n{traceback.format_exc()}")

        # Fallback to Claude
        if self._claude_available:
            try:
                content = self._call_claude(prompt)
                entities = self._parse_response(content, entity_types)
                processing_time = (time.perf_counter() - start_time) * 1000
                logger.info(f"Claude extracted {len(entities)} entities in {processing_time:.1f}ms")
                return entities, processing_time
            except Exception as e:
                logger.error(f"Claude extraction failed: {e}")

        processing_time = (time.perf_counter() - start_time) * 1000
        return [], processing_time

    def _call_ollama(self, prompt: str) -> str:
        """Call Ollama API."""
        with httpx.Client(timeout=self.config.timeout) as client:
            response = client.post(
                f"{self.config.ollama_base_url}/api/generate",
                json={
                    "model": self.config.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": self.config.temperature,
                        "num_predict": self.config.max_tokens,
                    },
                },
            )
            response.raise_for_status()
            return response.json().get("response", "")

    def _call_claude(self, prompt: str) -> str:
        """Call Claude API."""
        response = self._claude_client.messages.create(
            model=self.config.claude_model,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    def _parse_response(
        self,
        content: str,
        entity_types: list[str] | None = None,
    ) -> list[LLMExtractedEntity]:
        """Parse LLM JSON response into entities."""
        entities = []

        try:
            # Try to parse as JSON first (handles {"entities": [...]} or [...])
            raw_entities = None
            try:
                parsed = json.loads(content.strip())
                if isinstance(parsed, list):
                    raw_entities = parsed
                elif isinstance(parsed, dict) and "entities" in parsed:
                    raw_entities = parsed["entities"]
            except json.JSONDecodeError:
                pass

            # Fallback: extract JSON array from response (handle markdown code blocks)
            if raw_entities is None:
                json_match = re.search(r'\[[\s\S]*?\]', content)
                if not json_match:
                    logger.warning(f"No JSON array found in response: {content[:200]}...")
                    return []
                raw_entities = json.loads(json_match.group())

            for raw in raw_entities:
                # Normalize entity type
                raw_type = raw.get("type", "").lower()
                entity_type = ENTITY_TYPE_MAP.get(raw_type, raw_type)

                # Filter by requested types
                if entity_types and entity_type not in entity_types:
                    continue

                # Normalize assertion
                raw_assertion = raw.get("assertion", "present").lower()
                assertion = ASSERTION_MAP.get(raw_assertion, "present")

                entity = LLMExtractedEntity(
                    id=str(uuid4()),
                    entity_type=entity_type,
                    text=raw.get("text", ""),
                    normalized_text=raw.get("normalized_text", raw.get("text", "")),
                    start=raw.get("start", 0),
                    end=raw.get("end", 0),
                    assertion=assertion,
                    confidence=float(raw.get("confidence", 0.9)),
                    value=raw.get("value"),
                    unit=raw.get("unit"),
                )
                entities.append(entity)

            return entities

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse response as JSON: {e}")
            logger.debug(f"Response content: {content[:500]}...")
            return []
        except Exception as e:
            logger.error(f"Error parsing response: {e}")
            return []

    def get_model_info(self) -> dict:
        """Get information about this model."""
        if self._ollama_available:
            # Map Ollama model names to friendly display names
            model_display_names = {
                "alibayram/medgemma:27b": "MedGemma 27B",
                "alibayram/medgemma": "MedGemma",
                "cniongolo/biomistral:latest": "BioMistral",
                "cniongolo/biomistral": "BioMistral",
                "meditron:7b": "Meditron 7B",
                "medllama2:latest": "MedLlama2",
                "mistral:7b": "Mistral 7B",
                "llama3.1:latest": "Llama 3.1",
            }
            display_name = model_display_names.get(
                self.config.ollama_model,
                self.config.ollama_model.split("/")[-1].split(":")[0].title()
            )
            return {
                "model_id": "llm_api",
                "name": f"LLM ({display_name})",
                "description": "Local Ollama model for clinical NER - takes 30-60s",
                "entity_types": [
                    "diagnosis", "medication", "procedure", "lab_result",
                    "vital_sign", "anatomical_location", "temporal",
                    "symptom", "allergy", "social_history"
                ],
                "is_available": True,
                "requires_gpu": False,
                "version": "1.0.0",
            }
        else:
            return {
                "model_id": "llm_api",
                "name": "LLM API",
                "description": "LLM-based clinical NER - requires Ollama or ANTHROPIC_API_KEY",
                "entity_types": [
                    "diagnosis", "medication", "procedure", "lab_result",
                    "vital_sign", "anatomical_location", "temporal",
                    "symptom", "allergy", "social_history"
                ],
                "is_available": self._claude_available,
                "requires_gpu": False,
                "version": "1.0.0",
            }


# Backwards compatibility aliases
ClaudeNLPService = LLMNLPService

# Singleton instance
_llm_nlp_service: LLMNLPService | None = None


def get_claude_nlp_service(config: LLMNLPConfig | None = None) -> LLMNLPService:
    """Get or create the LLM NLP service singleton."""
    global _llm_nlp_service
    if _llm_nlp_service is None:
        _llm_nlp_service = LLMNLPService(config)
    return _llm_nlp_service


def get_llm_nlp_service(config: LLMNLPConfig | None = None) -> LLMNLPService:
    """Get or create the LLM NLP service singleton."""
    return get_claude_nlp_service(config)


def reset_claude_nlp_service() -> None:
    """Reset the singleton (for testing)."""
    global _llm_nlp_service
    _llm_nlp_service = None


def reset_llm_nlp_service() -> None:
    """Reset the singleton (for testing)."""
    reset_claude_nlp_service()
