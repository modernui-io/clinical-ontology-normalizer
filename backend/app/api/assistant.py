"""AI Coding Assistant API Endpoints.

Provides endpoints for AI-powered coding assistance:
- POST /assistant/chat - Send message, get response
- POST /assistant/sessions - Create a new session
- GET /assistant/sessions - List user sessions
- GET /assistant/sessions/{id}/history - Get conversation history
- DELETE /assistant/sessions/{id}/history - Clear history
- GET /assistant/suggestions - Get coding suggestions for context
- GET /assistant/lookup/{code} - Look up a specific code
"""

from __future__ import annotations

import logging
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assistant", tags=["AI Coding Assistant"])


# ============================================================================
# Request/Response Models
# ============================================================================


class CodeSystemParam(str, Enum):
    """Code system options."""

    ICD10 = "icd10"
    CPT = "cpt"
    SNOMED = "snomed"
    RXNORM = "rxnorm"
    HCPCS = "hcpcs"


class ConfidenceLevelParam(str, Enum):
    """Confidence level options."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class QueryIntentParam(str, Enum):
    """Query intent options."""

    CODE_LOOKUP = "code_lookup"
    CODE_SUGGESTION = "code_suggestion"
    CODE_EXPLANATION = "code_explanation"
    DOCUMENTATION_HELP = "documentation_help"
    GUIDELINE_QUERY = "guideline_query"
    GENERAL_QUESTION = "general_question"
    CONVERSATION = "conversation"


class MessageRoleParam(str, Enum):
    """Message role options."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class CodeSuggestionItem(BaseModel):
    """A suggested clinical code."""

    code: str = Field(..., description="Code value")
    display_name: str = Field(..., description="Display name/description")
    system: str = Field(..., description="Code system (icd10, cpt, snomed, rxnorm)")
    confidence: str = Field(..., description="Confidence level (high, medium, low)")
    score: float = Field(..., description="Relevance score (0-1)")
    description: str | None = Field(None, description="Extended description")
    reasoning: str | None = Field(None, description="Reasoning for suggestion")
    related_codes: list[str] = Field(default_factory=list, description="Related codes")


class CitationItem(BaseModel):
    """A citation from a vocabulary source."""

    source: str = Field(..., description="Source name")
    code: str | None = Field(None, description="Code if applicable")
    display: str | None = Field(None, description="Display text")
    url: str | None = Field(None, description="URL if available")
    excerpt: str | None = Field(None, description="Excerpt from source")


class ConversationMessageItem(BaseModel):
    """A message in the conversation."""

    id: str = Field(..., description="Message ID")
    role: str = Field(..., description="Message role (user, assistant, system)")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(..., description="Message timestamp")
    code_suggestions: list[CodeSuggestionItem] = Field(
        default_factory=list, description="Code suggestions in this message"
    )
    citations: list[CitationItem] = Field(default_factory=list, description="Citations")


class SessionContextItem(BaseModel):
    """Context for a session."""

    session_id: str = Field(..., description="Session ID")
    user_id: str = Field(..., description="User ID")
    patient_id: str | None = Field(None, description="Patient ID if in patient context")
    document_id: str | None = Field(None, description="Document ID if in document context")
    patient_name: str | None = Field(None, description="Patient name")
    document_name: str | None = Field(None, description="Document name")
    encounter_type: str | None = Field(None, description="Encounter type")


class SessionItem(BaseModel):
    """A conversation session."""

    id: str = Field(..., description="Session ID")
    user_id: str = Field(..., description="User ID")
    context: SessionContextItem = Field(..., description="Session context")
    message_count: int = Field(..., description="Number of messages")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class CreateSessionRequest(BaseModel):
    """Request to create a session."""

    patient_id: str | None = Field(None, description="Patient ID for context")
    document_id: str | None = Field(None, description="Document ID for context")
    patient_name: str | None = Field(None, description="Patient name for context")
    document_name: str | None = Field(None, description="Document name for context")
    encounter_type: str | None = Field(None, description="Encounter type")
    clinical_context: str | None = Field(None, max_length=5000, description="Clinical context text")


class ChatRequest(BaseModel):
    """Request to send a chat message."""

    session_id: str = Field(..., description="Session ID")
    message: str = Field(..., min_length=1, max_length=10000, description="User message")


class ChatResponse(BaseModel):
    """Response from chat."""

    message: ConversationMessageItem = Field(..., description="Assistant response message")
    suggestions: list[CodeSuggestionItem] = Field(..., description="Code suggestions")
    citations: list[CitationItem] = Field(..., description="Citations")
    intent: str = Field(..., description="Detected query intent")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")
    tokens_used: int = Field(default=0, description="Tokens used")
    cost_usd: float = Field(default=0.0, description="Estimated cost in USD")


class SessionListResponse(BaseModel):
    """Response for session list."""

    sessions: list[SessionItem] = Field(..., description="List of sessions")
    total: int = Field(..., description="Total session count")


class HistoryResponse(BaseModel):
    """Response for conversation history."""

    messages: list[ConversationMessageItem] = Field(..., description="Conversation messages")
    total: int = Field(..., description="Total message count")
    session_context: SessionContextItem = Field(..., description="Session context")


class SuggestionsRequest(BaseModel):
    """Request for code suggestions."""

    clinical_text: str = Field(..., min_length=1, max_length=10000, description="Clinical text to analyze")
    session_id: str | None = Field(None, description="Session ID for additional context")
    systems: list[CodeSystemParam] | None = Field(None, description="Code systems to search")
    max_suggestions: int = Field(default=10, ge=1, le=50, description="Maximum suggestions")


class SuggestionsResponse(BaseModel):
    """Response with code suggestions."""

    suggestions: list[CodeSuggestionItem] = Field(..., description="Code suggestions")
    total: int = Field(..., description="Total suggestions returned")
    clinical_text: str = Field(..., description="Input clinical text")


class CodeLookupResponse(BaseModel):
    """Response from code lookup."""

    found: bool = Field(..., description="Whether code was found")
    code: CodeSuggestionItem | None = Field(None, description="Code details if found")
    message: str = Field(..., description="Status message")


# ============================================================================
# Helper Functions
# ============================================================================


def _convert_suggestion(suggestion: Any) -> CodeSuggestionItem:
    """Convert a service suggestion to API model."""
    return CodeSuggestionItem(
        code=suggestion.code,
        display_name=suggestion.display_name,
        system=suggestion.system.value,
        confidence=suggestion.confidence.value,
        score=suggestion.score,
        description=suggestion.description,
        reasoning=suggestion.reasoning,
        related_codes=suggestion.related_codes,
    )


def _convert_citation(citation: Any) -> CitationItem:
    """Convert a service citation to API model."""
    return CitationItem(
        source=citation.source,
        code=citation.code,
        display=citation.display,
        url=citation.url,
        excerpt=citation.excerpt,
    )


def _convert_message(message: Any) -> ConversationMessageItem:
    """Convert a service message to API model."""
    return ConversationMessageItem(
        id=message.id,
        role=message.role.value,
        content=message.content,
        timestamp=message.timestamp,
        code_suggestions=[_convert_suggestion(s) for s in message.code_suggestions],
        citations=[_convert_citation(c) for c in message.citations],
    )


def _convert_context(context: Any) -> SessionContextItem:
    """Convert a service context to API model."""
    return SessionContextItem(
        session_id=context.session_id,
        user_id=context.user_id,
        patient_id=context.patient_id,
        document_id=context.document_id,
        patient_name=context.patient_name,
        document_name=context.document_name,
        encounter_type=context.encounter_type,
    )


def _convert_session(session: Any) -> SessionItem:
    """Convert a service session to API model."""
    return SessionItem(
        id=session.id,
        user_id=session.user_id,
        context=_convert_context(session.context),
        message_count=len(session.messages),
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


# ============================================================================
# Endpoints
# ============================================================================


@router.post(
    "/sessions",
    response_model=SessionItem,
    summary="Create a session",
    description="Create a new conversation session with optional context.",
)
async def create_session(
    request: CreateSessionRequest,
    user_id: str = Query("demo-user", description="User ID"),
) -> SessionItem:
    """Create a new conversation session.

    Args:
        request: Session creation request
        user_id: User ID

    Returns:
        Created SessionItem
    """
    try:
        from app.services.coding_assistant_service import get_coding_assistant_service

        service = get_coding_assistant_service()

        session = service.create_session(
            user_id=user_id,
            patient_id=request.patient_id,
            document_id=request.document_id,
            patient_name=request.patient_name,
            document_name=request.document_name,
            encounter_type=request.encounter_type,
            clinical_context=request.clinical_context,
        )

        return _convert_session(session)

    except Exception as e:
        # VP-Security-1: Log full error, return sanitized message
        logger.error(f"Failed to create session: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create session. Please try again.")


@router.get(
    "/sessions",
    response_model=SessionListResponse,
    summary="List sessions",
    description="List conversation sessions for the current user.",
)
async def list_sessions(
    user_id: str = Query("demo-user", description="User ID"),
    limit: int = Query(10, ge=1, le=50, description="Maximum sessions to return"),
) -> SessionListResponse:
    """List conversation sessions for a user.

    Args:
        user_id: User ID
        limit: Maximum sessions to return

    Returns:
        SessionListResponse with sessions
    """
    try:
        from app.services.coding_assistant_service import get_coding_assistant_service

        service = get_coding_assistant_service()
        sessions = service.get_user_sessions(user_id, limit)

        items = [_convert_session(s) for s in sessions]

        return SessionListResponse(
            sessions=items,
            total=len(items),
        )

    except Exception as e:
        # VP-Security-1: Log full error, return sanitized message
        logger.error(f"Failed to list sessions for user {user_id}: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list sessions. Please try again.")


@router.get(
    "/sessions/{session_id}",
    response_model=SessionItem,
    summary="Get session",
    description="Get a specific conversation session.",
)
async def get_session(
    session_id: str,
) -> SessionItem:
    """Get a conversation session by ID.

    Args:
        session_id: Session ID

    Returns:
        SessionItem
    """
    try:
        from app.services.coding_assistant_service import get_coding_assistant_service

        service = get_coding_assistant_service()
        session = service.get_session(session_id)

        if not session:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

        return _convert_session(session)

    except HTTPException:
        raise
    except Exception as e:
        # VP-Security-1: Log full error, return sanitized message
        logger.error(f"Failed to get session {session_id}: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get session. Please try again.")


@router.delete(
    "/sessions/{session_id}",
    summary="Delete session",
    description="Delete a conversation session.",
)
async def delete_session(
    session_id: str,
) -> dict[str, str]:
    """Delete a conversation session.

    Args:
        session_id: Session ID

    Returns:
        Success message
    """
    try:
        from app.services.coding_assistant_service import get_coding_assistant_service

        service = get_coding_assistant_service()
        deleted = service.delete_session(session_id)

        if not deleted:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

        return {"message": f"Session {session_id} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        # VP-Security-1: Log full error, return sanitized message
        logger.error(f"Failed to delete session {session_id}: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete session. Please try again.")


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Send chat message",
    description="Send a message to the assistant and get a response.",
)
async def chat(
    request: ChatRequest,
) -> ChatResponse:
    """Send a message and get an AI response.

    Args:
        request: Chat request with session ID and message

    Returns:
        ChatResponse with assistant response and suggestions
    """
    try:
        from app.services.coding_assistant_service import get_coding_assistant_service

        service = get_coding_assistant_service()
        response = await service.chat(request.session_id, request.message)

        return ChatResponse(
            message=_convert_message(response.message),
            suggestions=[_convert_suggestion(s) for s in response.suggestions],
            citations=[_convert_citation(c) for c in response.citations],
            intent=response.intent.value,
            processing_time_ms=response.processing_time_ms,
            tokens_used=response.tokens_used,
            cost_usd=response.cost_usd,
        )

    except ValueError as e:
        # ValueError typically means session not found - safe to expose
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        # VP-Security-1: Log full error, return sanitized message
        logger.error(f"Failed to process chat for session {request.session_id}: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Failed to process message. Please try again.")


@router.get(
    "/sessions/{session_id}/history",
    response_model=HistoryResponse,
    summary="Get conversation history",
    description="Get conversation history for a session.",
)
async def get_history(
    session_id: str,
    limit: int = Query(50, ge=1, le=200, description="Maximum messages to return"),
) -> HistoryResponse:
    """Get conversation history for a session.

    Args:
        session_id: Session ID
        limit: Maximum messages to return

    Returns:
        HistoryResponse with messages
    """
    try:
        from app.services.coding_assistant_service import get_coding_assistant_service

        service = get_coding_assistant_service()

        session = service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

        messages = service.get_conversation_history(session_id, limit)

        return HistoryResponse(
            messages=[_convert_message(m) for m in messages],
            total=len(messages),
            session_context=_convert_context(session.context),
        )

    except HTTPException:
        raise
    except Exception as e:
        # VP-Security-1: Log full error, return sanitized message
        logger.error(f"Failed to get history for session {session_id}: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get history. Please try again.")


@router.delete(
    "/sessions/{session_id}/history",
    summary="Clear conversation history",
    description="Clear conversation history for a session.",
)
async def clear_history(
    session_id: str,
) -> dict[str, str]:
    """Clear conversation history for a session.

    Args:
        session_id: Session ID

    Returns:
        Success message
    """
    try:
        from app.services.coding_assistant_service import get_coding_assistant_service

        service = get_coding_assistant_service()
        cleared = service.clear_session_history(session_id)

        if not cleared:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

        return {"message": f"History cleared for session {session_id}"}

    except HTTPException:
        raise
    except Exception as e:
        # VP-Security-1: Log full error, return sanitized message
        logger.error(f"Failed to clear history for session {session_id}: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear history. Please try again.")


@router.post(
    "/suggestions",
    response_model=SuggestionsResponse,
    summary="Get code suggestions",
    description="Get code suggestions for clinical text.",
)
async def get_suggestions(
    request: SuggestionsRequest,
) -> SuggestionsResponse:
    """Get code suggestions for clinical text.

    Args:
        request: Suggestions request with clinical text

    Returns:
        SuggestionsResponse with code suggestions
    """
    try:
        from app.services.coding_assistant_service import SuggestionType, get_coding_assistant_service

        service = get_coding_assistant_service()

        systems = None
        if request.systems:
            systems = [SuggestionType(s.value) for s in request.systems]

        suggestions = service.get_suggestions_for_context(
            session_id=request.session_id,
            clinical_text=request.clinical_text,
            systems=systems,
            max_suggestions=request.max_suggestions,
        )

        return SuggestionsResponse(
            suggestions=[_convert_suggestion(s) for s in suggestions],
            total=len(suggestions),
            clinical_text=request.clinical_text,
        )

    except Exception as e:
        # VP-Security-1: Log full error, return sanitized message
        logger.error(f"Failed to get suggestions: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get suggestions. Please try again.")


@router.get(
    "/lookup/{code}",
    response_model=CodeLookupResponse,
    summary="Look up a code",
    description="Look up a specific clinical code.",
)
async def lookup_code(
    code: str,
    system: CodeSystemParam | None = Query(None, description="Code system (auto-detected if not specified)"),
) -> CodeLookupResponse:
    """Look up a specific clinical code.

    Args:
        code: Code to look up
        system: Code system (auto-detected if not specified)

    Returns:
        CodeLookupResponse with code details
    """
    try:
        from app.services.coding_assistant_service import SuggestionType, get_coding_assistant_service

        service = get_coding_assistant_service()

        code_system = None
        if system:
            code_system = SuggestionType(system.value)

        result = service.lookup_code(code, code_system)

        if result:
            return CodeLookupResponse(
                found=True,
                code=_convert_suggestion(result),
                message=f"Code {code} found in {result.system.value.upper()}",
            )
        else:
            return CodeLookupResponse(
                found=False,
                code=None,
                message=f"Code {code} not found",
            )

    except Exception as e:
        # VP-Security-1: Log full error, return sanitized message
        logger.error(f"Failed to lookup code {code}: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Failed to lookup code. Please try again.")


@router.get(
    "/stats",
    summary="Get assistant service stats",
    description="Get statistics for the coding assistant service.",
)
async def get_assistant_stats() -> dict:
    """Get coding assistant service statistics.

    Returns:
        Statistics dictionary
    """
    try:
        from app.services.coding_assistant_service import get_coding_assistant_service

        service = get_coding_assistant_service()
        return service.get_stats()

    except Exception as e:
        # VP-Security-1: Log full error, return sanitized message
        logger.error(f"Failed to get assistant stats: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get stats. Please try again.")
