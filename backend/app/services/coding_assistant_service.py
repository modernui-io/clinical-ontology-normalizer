"""AI Coding Assistant Service for Clinical Ontology Platform.

Provides intelligent, context-aware assistance for clinical coding:
- Natural language query processing
- Code lookup and suggestions
- Context-aware responses (current patient/document)
- Citations from vocabulary services
- Conversation history tracking
- Audit logging of all interactions

Uses the LLM service for AI-powered responses while integrating
with existing vocabulary services (SNOMED, ICD-10, CPT, RxNorm).
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from app.core.config import settings

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Types
# ============================================================================


class MessageRole(str, Enum):
    """Role in a conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class SuggestionType(str, Enum):
    """Type of code suggestion."""

    ICD10 = "icd10"
    CPT = "cpt"
    SNOMED = "snomed"
    RXNORM = "rxnorm"
    HCPCS = "hcpcs"


class ConfidenceLevel(str, Enum):
    """Confidence level for suggestions."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class QueryIntent(str, Enum):
    """Detected intent from user query."""

    CODE_LOOKUP = "code_lookup"
    CODE_SUGGESTION = "code_suggestion"
    CODE_EXPLANATION = "code_explanation"
    DOCUMENTATION_HELP = "documentation_help"
    GUIDELINE_QUERY = "guideline_query"
    GENERAL_QUESTION = "general_question"
    CONVERSATION = "conversation"


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class CodeSuggestion:
    """A suggested clinical code."""

    code: str
    display_name: str
    system: SuggestionType
    confidence: ConfidenceLevel
    score: float
    description: str | None = None
    parent_code: str | None = None
    related_codes: list[str] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    reasoning: str | None = None


@dataclass
class Citation:
    """A citation from a vocabulary source."""

    source: str
    code: str | None = None
    display: str | None = None
    url: str | None = None
    excerpt: str | None = None


@dataclass
class ConversationMessage:
    """A message in the conversation."""

    id: str
    role: MessageRole
    content: str
    timestamp: datetime
    code_suggestions: list[CodeSuggestion] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationContext:
    """Context for a conversation session."""

    session_id: str
    user_id: str
    patient_id: str | None = None
    document_id: str | None = None
    patient_name: str | None = None
    document_name: str | None = None
    encounter_type: str | None = None
    clinical_context: str | None = None


@dataclass
class ConversationSession:
    """A conversation session with history."""

    id: str
    user_id: str
    context: ConversationContext
    messages: list[ConversationMessage]
    created_at: datetime
    updated_at: datetime


@dataclass
class AssistantResponse:
    """Response from the assistant."""

    message: ConversationMessage
    suggestions: list[CodeSuggestion]
    citations: list[Citation]
    intent: QueryIntent
    processing_time_ms: float
    tokens_used: int = 0
    cost_usd: float = 0.0


@dataclass
class AuditLogEntry:
    """Audit log entry for assistant interactions."""

    id: str
    timestamp: datetime
    user_id: str
    session_id: str
    query: str
    response_summary: str
    intent: QueryIntent
    suggestions_count: int
    patient_id: str | None = None
    document_id: str | None = None
    processing_time_ms: float = 0.0


# ============================================================================
# System Prompts
# ============================================================================


SYSTEM_PROMPT = """You are a clinical coding assistant for a healthcare informatics platform. Your role is to help clinicians and coders with:

1. **Code Lookup**: Find and explain medical codes (ICD-10, CPT, SNOMED, RxNorm, HCPCS)
2. **Code Suggestions**: Recommend appropriate codes based on clinical descriptions
3. **Documentation Help**: Assist with clinical documentation requirements
4. **Coding Guidelines**: Explain coding rules and best practices

IMPORTANT GUIDELINES:
- Always be accurate and cite authoritative sources when possible
- If you're uncertain about a code, indicate your confidence level
- For ambiguous cases, suggest multiple options with explanations
- Never make up codes - if you don't know, say so
- Consider the clinical context when making suggestions
- Be concise but thorough

When suggesting codes:
- Provide the code, description, and confidence level
- Explain WHY you're suggesting each code
- Note any documentation requirements or exclusions
- Mention related or alternative codes when relevant

FORMAT:
- Use markdown for clarity
- Present codes in a structured format
- Cite sources where applicable
"""

CONTEXT_TEMPLATE = """
CURRENT CONTEXT:
{context_details}

Use this context to provide more relevant and specific assistance.
"""


# ============================================================================
# Mock LLM Response Generator (for when LLM service is unavailable)
# ============================================================================


class MockLLMGenerator:
    """Generates mock responses when LLM service is unavailable."""

    def __init__(self):
        """Initialize mock generator."""
        self._common_codes = {
            "diabetes": [
                ("E11.9", "Type 2 diabetes mellitus without complications", "icd10"),
                ("E11.65", "Type 2 diabetes mellitus with hyperglycemia", "icd10"),
                ("E10.9", "Type 1 diabetes mellitus without complications", "icd10"),
            ],
            "hypertension": [
                ("I10", "Essential (primary) hypertension", "icd10"),
                ("I11.9", "Hypertensive heart disease without heart failure", "icd10"),
                ("I12.9", "Hypertensive chronic kidney disease with stage 1-4 CKD", "icd10"),
            ],
            "chest pain": [
                ("R07.9", "Chest pain, unspecified", "icd10"),
                ("R07.89", "Other chest pain", "icd10"),
                ("I20.9", "Angina pectoris, unspecified", "icd10"),
            ],
            "office visit": [
                ("99213", "Office visit, established patient, low complexity", "cpt"),
                ("99214", "Office visit, established patient, moderate complexity", "cpt"),
                ("99215", "Office visit, established patient, high complexity", "cpt"),
            ],
        }

    def generate_response(self, query: str, context: ConversationContext | None) -> tuple[str, list[CodeSuggestion]]:
        """Generate a mock response.

        Args:
            query: User query
            context: Conversation context

        Returns:
            Tuple of (response_text, suggestions)
        """
        query_lower = query.lower()
        suggestions = []

        # Check for common code queries
        for keyword, codes in self._common_codes.items():
            if keyword in query_lower:
                response = f"Based on your query about '{keyword}', here are some relevant codes:\n\n"
                for code, description, system in codes:
                    response += f"- **{code}**: {description} ({system.upper()})\n"
                    suggestions.append(CodeSuggestion(
                        code=code,
                        display_name=description,
                        system=SuggestionType(system),
                        confidence=ConfidenceLevel.MEDIUM,
                        score=0.85,
                        reasoning=f"Common code for {keyword}",
                    ))
                response += "\nPlease review the clinical documentation to select the most specific code."
                return response, suggestions

        # Generic response
        response = (
            "I understand you're asking about clinical coding. "
            "I can help you with:\n\n"
            "- Looking up specific codes (ICD-10, CPT, SNOMED, RxNorm)\n"
            "- Suggesting codes based on clinical descriptions\n"
            "- Explaining coding guidelines\n"
            "- Documentation requirements\n\n"
            "Could you provide more specific details about what you're looking for?"
        )
        return response, suggestions


# ============================================================================
# Query Analyzer
# ============================================================================


class QueryAnalyzer:
    """Analyzes user queries to detect intent and extract information."""

    def __init__(self):
        """Initialize query analyzer."""
        self._intent_keywords = {
            QueryIntent.CODE_LOOKUP: [
                "what is", "look up", "find code", "search for", "meaning of",
                "define", "definition", "what does", "explain code",
            ],
            QueryIntent.CODE_SUGGESTION: [
                "suggest", "recommend", "what code", "which code", "code for",
                "how to code", "assign code", "appropriate code",
            ],
            QueryIntent.CODE_EXPLANATION: [
                "explain", "why", "when to use", "difference between",
                "guidelines for", "rules for", "criteria",
            ],
            QueryIntent.DOCUMENTATION_HELP: [
                "document", "documentation", "support", "justify",
                "medical necessity", "requirement",
            ],
            QueryIntent.GUIDELINE_QUERY: [
                "guideline", "policy", "regulation", "cms", "aha",
                "coding clinic", "rule",
            ],
        }

        self._code_patterns = {
            "icd10": r"[A-TV-Z]\d{2}(?:\.\d{1,4})?",
            "cpt": r"(?<!\d)\d{5}(?!\d)",
            "snomed": r"\d{6,18}",
            "rxnorm": r"(?:RxNorm|rxnorm|RXNORM)?\s*\d{5,7}",
        }

    def analyze(self, query: str) -> tuple[QueryIntent, dict[str, Any]]:
        """Analyze a query for intent and extracted information.

        Args:
            query: User query text

        Returns:
            Tuple of (intent, extracted_info)
        """
        query_lower = query.lower()
        extracted = {}

        # Detect intent
        intent = QueryIntent.GENERAL_QUESTION
        max_matches = 0

        for intent_type, keywords in self._intent_keywords.items():
            matches = sum(1 for kw in keywords if kw in query_lower)
            if matches > max_matches:
                max_matches = matches
                intent = intent_type

        # Extract mentioned codes
        import re
        for code_type, pattern in self._code_patterns.items():
            matches = re.findall(pattern, query, re.IGNORECASE)
            if matches:
                extracted[f"{code_type}_codes"] = matches

        # Extract clinical terms
        clinical_terms = self._extract_clinical_terms(query)
        if clinical_terms:
            extracted["clinical_terms"] = clinical_terms

        return intent, extracted

    def _extract_clinical_terms(self, query: str) -> list[str]:
        """Extract potential clinical terms from query."""
        # Simple extraction - in production, use NLP
        terms = []
        clinical_indicators = [
            "diabetes", "hypertension", "pneumonia", "fracture", "infection",
            "surgery", "procedure", "diagnosis", "condition", "symptom",
            "pain", "fever", "cough", "injury", "disease",
        ]
        query_lower = query.lower()
        for term in clinical_indicators:
            if term in query_lower:
                terms.append(term)
        return terms


# ============================================================================
# Vocabulary Integration
# ============================================================================


class VocabularyIntegration:
    """Integrates with vocabulary services for code lookups."""

    def __init__(self):
        """Initialize vocabulary integration."""
        self._services_available = {}

    def _get_icd10_service(self) -> Any:
        """Get ICD-10 suggester service."""
        try:
            from app.services.icd10_suggester import get_icd10_suggester_service
            return get_icd10_suggester_service()
        except Exception:
            return None

    def _get_cpt_service(self) -> Any:
        """Get CPT suggester service."""
        try:
            from app.services.cpt_suggester import get_cpt_suggester_service
            return get_cpt_suggester_service()
        except Exception:
            return None

    def _get_snomed_service(self) -> Any:
        """Get SNOMED service."""
        try:
            from app.services.snomed_service import get_snomed_service
            return get_snomed_service()
        except Exception:
            return None

    def _get_rxnorm_service(self) -> Any:
        """Get RxNorm service."""
        try:
            from app.services.rxnorm_service import get_rxnorm_service
            return get_rxnorm_service()
        except Exception:
            return None

    def lookup_code(self, code: str, system: SuggestionType | None = None) -> CodeSuggestion | None:
        """Look up a code in vocabulary services.

        Args:
            code: Code to look up
            system: Code system (auto-detected if None)

        Returns:
            CodeSuggestion if found, None otherwise
        """
        # Auto-detect system if not specified
        if system is None:
            system = self._detect_code_system(code)

        if system == SuggestionType.ICD10:
            return self._lookup_icd10(code)
        elif system == SuggestionType.CPT:
            return self._lookup_cpt(code)
        elif system == SuggestionType.SNOMED:
            return self._lookup_snomed(code)
        elif system == SuggestionType.RXNORM:
            return self._lookup_rxnorm(code)

        return None

    def _detect_code_system(self, code: str) -> SuggestionType | None:
        """Detect code system from code format."""
        import re

        if re.match(r"^[A-TV-Z]\d{2}", code, re.IGNORECASE):
            return SuggestionType.ICD10
        elif re.match(r"^\d{5}$", code):
            return SuggestionType.CPT
        elif re.match(r"^\d{6,18}$", code):
            # Could be SNOMED or RxNorm - default to SNOMED
            return SuggestionType.SNOMED

        return None

    def _lookup_icd10(self, code: str) -> CodeSuggestion | None:
        """Look up ICD-10 code."""
        service = self._get_icd10_service()
        if not service:
            return None

        try:
            concept = service.get_code(code)
            if concept:
                return CodeSuggestion(
                    code=concept.code,
                    display_name=concept.description,
                    system=SuggestionType.ICD10,
                    confidence=ConfidenceLevel.HIGH,
                    score=1.0,
                    description=concept.long_description if hasattr(concept, "long_description") else None,
                    citations=[Citation(source="ICD-10-CM", code=concept.code, display=concept.description)],
                )
        except Exception as e:
            logger.warning(f"ICD-10 lookup failed for {code}: {e}")

        return None

    def _lookup_cpt(self, code: str) -> CodeSuggestion | None:
        """Look up CPT code."""
        service = self._get_cpt_service()
        if not service:
            return None

        try:
            concept = service.get_code(code)
            if concept:
                return CodeSuggestion(
                    code=concept.code,
                    display_name=concept.description,
                    system=SuggestionType.CPT,
                    confidence=ConfidenceLevel.HIGH,
                    score=1.0,
                    citations=[Citation(source="CPT", code=concept.code, display=concept.description)],
                )
        except Exception as e:
            logger.warning(f"CPT lookup failed for {code}: {e}")

        return None

    def _lookup_snomed(self, code: str) -> CodeSuggestion | None:
        """Look up SNOMED code."""
        service = self._get_snomed_service()
        if not service:
            return None

        try:
            concept = service.get_concept(code)
            if concept:
                return CodeSuggestion(
                    code=concept.concept_code,
                    display_name=concept.concept_name,
                    system=SuggestionType.SNOMED,
                    confidence=ConfidenceLevel.HIGH,
                    score=1.0,
                    description=f"Semantic type: {concept.semantic_type.value}",
                    citations=[Citation(source="SNOMED CT", code=concept.concept_code, display=concept.concept_name)],
                )
        except Exception as e:
            logger.warning(f"SNOMED lookup failed for {code}: {e}")

        return None

    def _lookup_rxnorm(self, code: str) -> CodeSuggestion | None:
        """Look up RxNorm code."""
        service = self._get_rxnorm_service()
        if not service:
            return None

        try:
            result = service.lookup_by_rxcui(code)
            if result and result.drug:
                return CodeSuggestion(
                    code=result.drug.rxcui,
                    display_name=result.drug.name,
                    system=SuggestionType.RXNORM,
                    confidence=ConfidenceLevel.HIGH,
                    score=1.0,
                    description=f"Term type: {result.drug.term_type.value}",
                    citations=[Citation(source="RxNorm", code=result.drug.rxcui, display=result.drug.name)],
                )
        except Exception as e:
            logger.warning(f"RxNorm lookup failed for {code}: {e}")

        return None

    def suggest_codes(
        self,
        clinical_text: str,
        systems: list[SuggestionType] | None = None,
        max_per_system: int = 5,
    ) -> list[CodeSuggestion]:
        """Suggest codes based on clinical text.

        Args:
            clinical_text: Clinical description
            systems: Code systems to search (all if None)
            max_per_system: Maximum suggestions per system

        Returns:
            List of code suggestions
        """
        if systems is None:
            systems = [SuggestionType.ICD10, SuggestionType.CPT, SuggestionType.SNOMED]

        suggestions = []

        if SuggestionType.ICD10 in systems:
            suggestions.extend(self._suggest_icd10(clinical_text, max_per_system))

        if SuggestionType.CPT in systems:
            suggestions.extend(self._suggest_cpt(clinical_text, max_per_system))

        if SuggestionType.SNOMED in systems:
            suggestions.extend(self._suggest_snomed(clinical_text, max_per_system))

        return suggestions

    def _suggest_icd10(self, text: str, limit: int) -> list[CodeSuggestion]:
        """Get ICD-10 suggestions for text."""
        service = self._get_icd10_service()
        if not service:
            return []

        try:
            result = service.suggest_codes(text, max_suggestions=limit)
            suggestions = []
            for s in result.suggestions:
                confidence = ConfidenceLevel.HIGH if s.confidence.value == "high" else (
                    ConfidenceLevel.MEDIUM if s.confidence.value == "medium" else ConfidenceLevel.LOW
                )
                suggestions.append(CodeSuggestion(
                    code=s.code.code,
                    display_name=s.code.description,
                    system=SuggestionType.ICD10,
                    confidence=confidence,
                    score=s.score,
                    reasoning=s.reasoning,
                    citations=[Citation(source="ICD-10-CM", code=s.code.code)],
                ))
            return suggestions
        except Exception as e:
            logger.warning(f"ICD-10 suggestion failed: {e}")
            return []

    def _suggest_cpt(self, text: str, limit: int) -> list[CodeSuggestion]:
        """Get CPT suggestions for text."""
        service = self._get_cpt_service()
        if not service:
            return []

        try:
            result = service.suggest_codes(text, max_suggestions=limit)
            suggestions = []
            for s in result.suggestions:
                confidence = ConfidenceLevel.HIGH if s.confidence.value == "high" else (
                    ConfidenceLevel.MEDIUM if s.confidence.value == "medium" else ConfidenceLevel.LOW
                )
                suggestions.append(CodeSuggestion(
                    code=s.code.code,
                    display_name=s.code.description,
                    system=SuggestionType.CPT,
                    confidence=confidence,
                    score=s.score,
                    reasoning=s.reasoning,
                    citations=[Citation(source="CPT", code=s.code.code)],
                ))
            return suggestions
        except Exception as e:
            logger.warning(f"CPT suggestion failed: {e}")
            return []

    def _suggest_snomed(self, text: str, limit: int) -> list[CodeSuggestion]:
        """Get SNOMED suggestions for text."""
        service = self._get_snomed_service()
        if not service:
            return []

        try:
            matches = service.match_concept(text, max_results=limit)
            suggestions = []
            for m in matches:
                confidence = (
                    ConfidenceLevel.HIGH if m.confidence.value == "exact" else
                    (ConfidenceLevel.MEDIUM if m.confidence.value == "high" else ConfidenceLevel.LOW)
                )
                suggestions.append(CodeSuggestion(
                    code=m.concept.concept_code,
                    display_name=m.concept.concept_name,
                    system=SuggestionType.SNOMED,
                    confidence=confidence,
                    score=m.score,
                    reasoning=f"Match type: {m.match_type}",
                    citations=[Citation(source="SNOMED CT", code=m.concept.concept_code)],
                ))
            return suggestions
        except Exception as e:
            logger.warning(f"SNOMED suggestion failed: {e}")
            return []


# ============================================================================
# Coding Assistant Service
# ============================================================================


class CodingAssistantService:
    """AI-powered clinical coding assistant.

    Provides:
    - Natural language query processing
    - Context-aware code suggestions
    - Integration with vocabulary services
    - Conversation history management
    - Audit logging
    """

    def __init__(self):
        """Initialize the coding assistant service."""
        self._sessions: dict[str, ConversationSession] = {}
        self._audit_logs: list[AuditLogEntry] = []
        self._lock = threading.Lock()

        # Components
        self._query_analyzer = QueryAnalyzer()
        self._vocabulary = VocabularyIntegration()
        self._mock_generator = MockLLMGenerator()

        # Statistics
        self._total_queries = 0
        self._total_suggestions = 0

        logger.info("CodingAssistantService initialized")

    def _get_llm_service(self) -> Any:
        """Get LLM service if available."""
        try:
            from app.services.llm_service import get_llm_service
            service = get_llm_service()
            if service.get_available_providers():
                return service
        except Exception:
            pass
        return None

    # ========================================================================
    # Session Management
    # ========================================================================

    def create_session(
        self,
        user_id: str,
        patient_id: str | None = None,
        document_id: str | None = None,
        patient_name: str | None = None,
        document_name: str | None = None,
        encounter_type: str | None = None,
        clinical_context: str | None = None,
    ) -> ConversationSession:
        """Create a new conversation session.

        Args:
            user_id: User ID
            patient_id: Optional patient context
            document_id: Optional document context
            patient_name: Optional patient name
            document_name: Optional document name
            encounter_type: Optional encounter type
            clinical_context: Optional clinical context text

        Returns:
            New conversation session
        """
        session_id = str(uuid4())
        now = datetime.now(timezone.utc)

        context = ConversationContext(
            session_id=session_id,
            user_id=user_id,
            patient_id=patient_id,
            document_id=document_id,
            patient_name=patient_name,
            document_name=document_name,
            encounter_type=encounter_type,
            clinical_context=clinical_context,
        )

        session = ConversationSession(
            id=session_id,
            user_id=user_id,
            context=context,
            messages=[],
            created_at=now,
            updated_at=now,
        )

        with self._lock:
            self._sessions[session_id] = session

        logger.info(f"Created coding assistant session {session_id} for user {user_id}")
        return session

    def get_session(self, session_id: str) -> ConversationSession | None:
        """Get a conversation session by ID."""
        with self._lock:
            return self._sessions.get(session_id)

    def get_user_sessions(self, user_id: str, limit: int = 10) -> list[ConversationSession]:
        """Get recent sessions for a user."""
        with self._lock:
            sessions = [s for s in self._sessions.values() if s.user_id == user_id]
            sessions.sort(key=lambda s: s.updated_at, reverse=True)
            return sessions[:limit]

    def delete_session(self, session_id: str) -> bool:
        """Delete a conversation session."""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    def clear_session_history(self, session_id: str) -> bool:
        """Clear conversation history for a session."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.messages = []
                session.updated_at = datetime.now(timezone.utc)
                return True
            return False

    # ========================================================================
    # Chat Interface
    # ========================================================================

    async def chat(
        self,
        session_id: str,
        message: str,
    ) -> AssistantResponse:
        """Send a message and get a response.

        Args:
            session_id: Session ID
            message: User message

        Returns:
            AssistantResponse with response and suggestions
        """
        start_time = time.perf_counter()

        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        # Analyze query
        intent, extracted = self._query_analyzer.analyze(message)

        # Create user message
        user_message = ConversationMessage(
            id=str(uuid4()),
            role=MessageRole.USER,
            content=message,
            timestamp=datetime.now(timezone.utc),
        )

        # Add to history
        with self._lock:
            session.messages.append(user_message)
            session.updated_at = datetime.now(timezone.utc)

        # Process based on intent
        response_text = ""
        suggestions = []
        citations = []
        tokens_used = 0
        cost_usd = 0.0

        # Try to use LLM if available
        llm_service = self._get_llm_service()

        if llm_service:
            try:
                response_text, suggestions, citations, tokens_used, cost_usd = await asyncio.wait_for(
                    self._process_with_llm(
                        session, message, intent, extracted, llm_service
                    ),
                    timeout=30.0,
                )
            except asyncio.TimeoutError:
                logger.warning("LLM processing timed out after 30s, using mock")
                response_text, suggestions = self._mock_generator.generate_response(message, session.context)
            except Exception as e:
                logger.warning(f"LLM processing failed, using mock: {e}")
                response_text, suggestions = self._mock_generator.generate_response(message, session.context)
        else:
            # Use mock generator
            response_text, suggestions = self._mock_generator.generate_response(message, session.context)

        # Enrich with vocabulary lookups
        if not suggestions and extracted.get("clinical_terms"):
            vocabulary_suggestions = self._vocabulary.suggest_codes(
                " ".join(extracted["clinical_terms"]),
                max_per_system=3,
            )
            suggestions.extend(vocabulary_suggestions)

        # Look up any mentioned codes
        for code_type in ["icd10_codes", "cpt_codes", "snomed_codes"]:
            if code_type in extracted:
                for code in extracted[code_type]:
                    lookup_result = self._vocabulary.lookup_code(code)
                    if lookup_result and lookup_result not in suggestions:
                        suggestions.append(lookup_result)
                        citations.append(Citation(
                            source=lookup_result.system.value.upper(),
                            code=lookup_result.code,
                            display=lookup_result.display_name,
                        ))

        # Create assistant message
        assistant_message = ConversationMessage(
            id=str(uuid4()),
            role=MessageRole.ASSISTANT,
            content=response_text,
            timestamp=datetime.now(timezone.utc),
            code_suggestions=suggestions,
            citations=citations,
        )

        # Add to history
        with self._lock:
            session.messages.append(assistant_message)
            session.updated_at = datetime.now(timezone.utc)

        processing_time_ms = (time.perf_counter() - start_time) * 1000

        # Update statistics
        self._total_queries += 1
        self._total_suggestions += len(suggestions)

        # Log audit entry
        self._log_interaction(
            session=session,
            query=message,
            response_summary=response_text[:200],
            intent=intent,
            suggestions_count=len(suggestions),
            processing_time_ms=processing_time_ms,
        )

        return AssistantResponse(
            message=assistant_message,
            suggestions=suggestions,
            citations=citations,
            intent=intent,
            processing_time_ms=round(processing_time_ms, 2),
            tokens_used=tokens_used,
            cost_usd=cost_usd,
        )

    async def _process_with_llm(
        self,
        session: ConversationSession,
        message: str,
        intent: QueryIntent,
        extracted: dict[str, Any],
        llm_service: Any,
    ) -> tuple[str, list[CodeSuggestion], list[Citation], int, float]:
        """Process query using LLM service.

        Args:
            session: Conversation session
            message: User message
            intent: Detected intent
            extracted: Extracted information
            llm_service: LLM service instance

        Returns:
            Tuple of (response_text, suggestions, citations, tokens_used, cost_usd)
        """
        from app.services.llm_service import LLMMessage

        # Build messages for LLM
        messages = [
            LLMMessage(role="system", content=SYSTEM_PROMPT),
        ]

        # Add context if available
        if session.context.patient_id or session.context.document_id:
            context_details = []
            if session.context.patient_name:
                context_details.append(f"Patient: {session.context.patient_name}")
            if session.context.document_name:
                context_details.append(f"Document: {session.context.document_name}")
            if session.context.encounter_type:
                context_details.append(f"Encounter Type: {session.context.encounter_type}")
            if session.context.clinical_context:
                context_details.append(f"Clinical Context: {session.context.clinical_context[:500]}")

            if context_details:
                context_prompt = CONTEXT_TEMPLATE.format(
                    context_details="\n".join(context_details)
                )
                messages.append(LLMMessage(role="system", content=context_prompt))

        # Add conversation history (last 10 messages)
        for msg in session.messages[-10:]:
            if msg.role in [MessageRole.USER, MessageRole.ASSISTANT]:
                messages.append(LLMMessage(
                    role=msg.role.value,
                    content=msg.content,
                ))

        # Add current message
        messages.append(LLMMessage(role="user", content=message))

        # Call LLM
        response = await llm_service.generate_chat(
            messages=messages,
            max_tokens=2048,
            temperature=0.3,
        )

        # Extract code suggestions from response
        suggestions = []
        citations = []

        # The LLM response is text - we parse any code references
        # In a production system, you might use structured output
        response_text = response.content

        return (
            response_text,
            suggestions,
            citations,
            response.token_usage.total_tokens,
            response.cost_estimate.total_cost,
        )

    # ========================================================================
    # Suggestions API
    # ========================================================================

    def get_suggestions_for_context(
        self,
        session_id: str | None = None,
        clinical_text: str | None = None,
        systems: list[SuggestionType] | None = None,
        max_suggestions: int = 10,
    ) -> list[CodeSuggestion]:
        """Get code suggestions for current context.

        Args:
            session_id: Session ID for context
            clinical_text: Clinical text to analyze
            systems: Code systems to search
            max_suggestions: Maximum suggestions

        Returns:
            List of code suggestions
        """
        context_text = clinical_text or ""

        # Add context from session
        if session_id:
            session = self.get_session(session_id)
            if session and session.context.clinical_context:
                context_text = session.context.clinical_context + " " + context_text

        if not context_text.strip():
            return []

        suggestions = self._vocabulary.suggest_codes(
            context_text,
            systems=systems,
            max_per_system=max_suggestions // len(systems or [SuggestionType.ICD10, SuggestionType.CPT]),
        )

        return suggestions[:max_suggestions]

    def lookup_code(self, code: str, system: SuggestionType | None = None) -> CodeSuggestion | None:
        """Look up a specific code.

        Args:
            code: Code to look up
            system: Code system (auto-detected if None)

        Returns:
            CodeSuggestion if found
        """
        return self._vocabulary.lookup_code(code, system)

    # ========================================================================
    # History and Audit
    # ========================================================================

    def get_conversation_history(
        self,
        session_id: str,
        limit: int = 50,
    ) -> list[ConversationMessage]:
        """Get conversation history for a session.

        Args:
            session_id: Session ID
            limit: Maximum messages to return

        Returns:
            List of conversation messages
        """
        session = self.get_session(session_id)
        if not session:
            return []
        return list(session.messages[-limit:])

    def _log_interaction(
        self,
        session: ConversationSession,
        query: str,
        response_summary: str,
        intent: QueryIntent,
        suggestions_count: int,
        processing_time_ms: float,
    ) -> None:
        """Log an interaction for audit purposes."""
        entry = AuditLogEntry(
            id=str(uuid4()),
            timestamp=datetime.now(timezone.utc),
            user_id=session.user_id,
            session_id=session.id,
            query=query,
            response_summary=response_summary,
            intent=intent,
            suggestions_count=suggestions_count,
            patient_id=session.context.patient_id,
            document_id=session.context.document_id,
            processing_time_ms=processing_time_ms,
        )

        with self._lock:
            self._audit_logs.append(entry)
            # Keep only last 10000 entries
            if len(self._audit_logs) > 10000:
                self._audit_logs = self._audit_logs[-5000:]

    def get_audit_logs(
        self,
        user_id: str | None = None,
        session_id: str | None = None,
        limit: int = 100,
    ) -> list[AuditLogEntry]:
        """Get audit logs with optional filters.

        Args:
            user_id: Filter by user ID
            session_id: Filter by session ID
            limit: Maximum entries to return

        Returns:
            List of audit log entries
        """
        with self._lock:
            logs = self._audit_logs.copy()

        if user_id:
            logs = [l for l in logs if l.user_id == user_id]
        if session_id:
            logs = [l for l in logs if l.session_id == session_id]

        return list(reversed(logs[-limit:]))

    # ========================================================================
    # Statistics
    # ========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        with self._lock:
            session_count = len(self._sessions)
            audit_log_count = len(self._audit_logs)

        return {
            "service": "CodingAssistantService",
            "total_queries": self._total_queries,
            "total_suggestions": self._total_suggestions,
            "active_sessions": session_count,
            "audit_log_entries": audit_log_count,
            "llm_available": self._get_llm_service() is not None,
        }


# ============================================================================
# Singleton Pattern
# ============================================================================


_service_instance: CodingAssistantService | None = None
_service_lock = threading.Lock()


def get_coding_assistant_service() -> CodingAssistantService:
    """Get or create the singleton coding assistant service instance.

    Returns:
        CodingAssistantService singleton instance
    """
    global _service_instance

    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = CodingAssistantService()

    return _service_instance


def reset_coding_assistant_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _service_instance
    with _service_lock:
        _service_instance = None
