"""API endpoints for Claude-powered agent chat with clinical data tools."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware import get_current_user, CurrentUser
from app.core.database import get_db
from app.schemas.agent_chat import AgentChatRequest, AgentChatResponse
from app.services.agent_chat_service import get_agent_chat_service
from app.services.agent_tools import TOOL_SCHEMAS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent-chat", tags=["Agent Chat"])


@router.post(
    "/chat",
    response_model=AgentChatResponse,
    summary="Chat with clinical data agent",
    description=(
        "Send a message to the clinical data agent.  The agent has tool-use "
        "access to query patient data (conditions, medications, labs, "
        "procedures, encounters), search clinical concepts, check trial "
        "eligibility, and explore the knowledge graph."
    ),
)
async def agent_chat(
    request: AgentChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> AgentChatResponse:
    svc = get_agent_chat_service()
    return await svc.chat(
        messages=request.messages,
        session=db,
        model=request.model,
        patient_id=request.patient_id,
    )


@router.get(
    "/tools",
    response_model=list[dict[str, Any]],
    summary="List available agent tools",
    description="Returns the tool schemas available to the clinical data agent.",
)
async def list_agent_tools(
    current_user: CurrentUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    return TOOL_SCHEMAS
