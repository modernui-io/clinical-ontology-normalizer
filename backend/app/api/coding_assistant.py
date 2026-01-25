"""Coding Assistant API endpoints.

Provides AI-powered assistance for medical coding questions.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any

from app.services.coding_assistant_service import (
    get_coding_assistant_service,
    SuggestionType,
    ConfidenceLevel,
)


router = APIRouter(prefix="/coding-assistant", tags=["Coding Assistant"])


class ChatRequest(BaseModel):
    """Request to send a message to the coding assistant."""

    message: str = Field(..., description="The question or message to send")
    session_id: str | None = Field(
        default=None,
        description="Optional session ID to continue a conversation"
    )
    context: dict[str, Any] | None = Field(
        default=None,
        description="Optional context (patient_id, document_id, etc.)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "What is the correct ICD-10 code for type 2 diabetes?",
                "session_id": None,
                "context": {"specialty": "internal medicine"}
            }
        }


class CodeSuggestionResponse(BaseModel):
    """A suggested code from the assistant."""

    code: str = Field(..., description="The code value")
    display: str = Field(..., description="Display text for the code")
    system: str = Field(..., description="Code system (ICD-10, CPT, etc.)")
    confidence: str = Field(..., description="Confidence level: high, medium, low")

    class Config:
        json_schema_extra = {
            "example": {
                "code": "E11.9",
                "display": "Type 2 diabetes mellitus without complications",
                "system": "ICD-10",
                "confidence": "high"
            }
        }


class CitationResponse(BaseModel):
    """A citation from the assistant's response."""

    source: str = Field(..., description="Source of the citation")
    section: str | None = Field(default=None, description="Section reference")
    text: str | None = Field(default=None, description="Cited text")


class ChatResponse(BaseModel):
    """Response from the coding assistant."""

    session_id: str = Field(..., description="Session ID for continuing conversation")
    response: str = Field(..., description="The assistant's response text")
    suggestions: list[CodeSuggestionResponse] = Field(
        default_factory=list,
        description="Suggested codes"
    )
    citations: list[CitationResponse] = Field(
        default_factory=list,
        description="Citations for the response"
    )
    follow_up_questions: list[str] = Field(
        default_factory=list,
        description="Suggested follow-up questions"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session-abc123",
                "response": "For type 2 diabetes, the primary ICD-10-CM code is E11 (Type 2 diabetes mellitus). The most common code is E11.9 for type 2 diabetes without complications.",
                "suggestions": [
                    {
                        "code": "E11.9",
                        "display": "Type 2 diabetes mellitus without complications",
                        "system": "ICD-10",
                        "confidence": "high"
                    }
                ],
                "citations": [
                    {
                        "source": "ICD-10-CM Guidelines",
                        "section": "Chapter 4",
                        "text": "Diabetes mellitus codes are combination codes..."
                    }
                ],
                "follow_up_questions": [
                    "Does the patient have any diabetic complications?",
                    "What medications is the patient on for diabetes?"
                ]
            }
        }


class SessionInfoResponse(BaseModel):
    """Information about a conversation session."""

    session_id: str = Field(..., description="Session identifier")
    created_at: str = Field(..., description="Session creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    message_count: int = Field(..., description="Number of messages in session")
    context: dict[str, Any] = Field(default_factory=dict, description="Session context")


class SessionListResponse(BaseModel):
    """List of conversation sessions."""

    sessions: list[SessionInfoResponse] = Field(..., description="List of sessions")
    total: int = Field(..., description="Total number of sessions")


class CodeLookupResponse(BaseModel):
    """Response for code lookup."""

    code: str = Field(..., description="The code value")
    display: str = Field(..., description="Display text")
    system: str = Field(..., description="Code system")
    definition: str | None = Field(default=None, description="Code definition")
    found: bool = Field(..., description="Whether the code was found")


class StatsResponse(BaseModel):
    """Service statistics."""

    total_sessions: int = Field(..., description="Total conversation sessions")
    total_queries: int = Field(..., description="Total queries processed")
    cache_hits: int = Field(..., description="Number of cache hits")
    cache_misses: int = Field(..., description="Number of cache misses")


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Chat with the coding assistant",
    description="Send a message to the AI coding assistant and receive guidance with code suggestions.",
)
async def chat(
    request: ChatRequest,
) -> ChatResponse:
    """Send a message to the coding assistant."""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    service = get_coding_assistant_service()

    # Extract context parameters
    ctx = request.context or {}

    # Get or create session
    session_id = request.session_id
    if session_id:
        session = service.get_session(session_id)
        if not session:
            # Create new session if not found
            session = service.create_session(
                user_id="anonymous",  # Would come from auth in production
                patient_id=ctx.get("patient_id"),
                document_id=ctx.get("document_id"),
                encounter_type=ctx.get("encounter_type"),
                clinical_context=ctx.get("clinical_context"),
            )
            session_id = session.id
    else:
        session = service.create_session(
            user_id="anonymous",
            patient_id=ctx.get("patient_id"),
            document_id=ctx.get("document_id"),
            encounter_type=ctx.get("encounter_type"),
            clinical_context=ctx.get("clinical_context"),
        )
        session_id = session.id

    # Get response from assistant
    response = await service.chat(session_id, request.message)

    # Build response
    suggestions = []
    for suggestion in response.suggestions:
        suggestions.append(CodeSuggestionResponse(
            code=suggestion.code,
            display=suggestion.display_name,
            system=suggestion.system.value if suggestion.system else "Unknown",
            confidence=suggestion.confidence.value if suggestion.confidence else "medium",
        ))

    citations = []
    for citation in response.citations:
        citations.append(CitationResponse(
            source=citation.source,
            section=citation.code,  # Use code as section identifier
            text=citation.excerpt or citation.display,
        ))

    # Extract follow-up questions from message metadata if available
    follow_ups = response.message.metadata.get("follow_up_questions", [])

    return ChatResponse(
        session_id=session_id,
        response=response.message.content,
        suggestions=suggestions,
        citations=citations,
        follow_up_questions=follow_ups,
    )


@router.get(
    "/sessions",
    response_model=SessionListResponse,
    summary="List conversation sessions",
    description="Get a list of conversation sessions for the current user.",
)
async def list_sessions(
    user_id: str = Query(default="anonymous", description="User ID to filter sessions"),
    limit: int = Query(default=10, ge=1, le=100, description="Maximum sessions to return"),
) -> SessionListResponse:
    """List conversation sessions."""
    service = get_coding_assistant_service()
    sessions = service.get_user_sessions(user_id, limit=limit)

    session_infos = []
    for session in sessions:
        session_infos.append(SessionInfoResponse(
            session_id=session.id,
            created_at=session.created_at.isoformat(),
            updated_at=session.updated_at.isoformat(),
            message_count=len(session.messages),
            context=session.context.__dict__ if session.context else {},
        ))

    return SessionListResponse(
        sessions=session_infos,
        total=len(sessions),
    )


@router.get(
    "/sessions/{session_id}",
    response_model=SessionInfoResponse,
    summary="Get session details",
    description="Get details of a specific conversation session.",
)
async def get_session(
    session_id: str,
) -> SessionInfoResponse:
    """Get session details."""
    service = get_coding_assistant_service()
    session = service.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionInfoResponse(
        session_id=session.id,
        created_at=session.created_at.isoformat(),
        updated_at=session.updated_at.isoformat(),
        message_count=len(session.messages),
        context=session.context.__dict__ if session.context else {},
    )


@router.delete(
    "/sessions/{session_id}",
    summary="Delete a session",
    description="Delete a conversation session.",
)
async def delete_session(
    session_id: str,
) -> dict[str, bool]:
    """Delete a session."""
    service = get_coding_assistant_service()
    success = service.delete_session(session_id)

    if not success:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"deleted": True}


@router.get(
    "/lookup/{code}",
    response_model=CodeLookupResponse,
    summary="Look up a code",
    description="Look up information about a specific medical code.",
)
async def lookup_code(
    code: str,
    system: str | None = Query(
        default=None,
        description="Code system: ICD-10, CPT, SNOMED, RxNorm"
    ),
) -> CodeLookupResponse:
    """Look up a code."""
    service = get_coding_assistant_service()

    # Map string to enum
    system_enum = None
    if system:
        system_map = {
            "icd-10": SuggestionType.ICD10,
            "icd10": SuggestionType.ICD10,
            "cpt": SuggestionType.CPT,
            "snomed": SuggestionType.SNOMED,
            "rxnorm": SuggestionType.RXNORM,
        }
        system_enum = system_map.get(system.lower())

    result = service.lookup_code(code, system_enum)

    if not result:
        return CodeLookupResponse(
            code=code,
            display="",
            system=system or "Unknown",
            definition=None,
            found=False,
        )

    return CodeLookupResponse(
        code=result.code,
        display=result.display_name,
        system=result.system.value if result.system else "Unknown",
        definition=result.description,
        found=True,
    )


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Get service statistics",
    description="Get statistics about the coding assistant service.",
)
async def get_stats() -> StatsResponse:
    """Get service statistics."""
    service = get_coding_assistant_service()
    stats = service.get_stats()

    return StatsResponse(
        total_sessions=stats.get("total_sessions", 0),
        total_queries=stats.get("total_queries", 0),
        cache_hits=stats.get("cache_hits", 0),
        cache_misses=stats.get("cache_misses", 0),
    )
