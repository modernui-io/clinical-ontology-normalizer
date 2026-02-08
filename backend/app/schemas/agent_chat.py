"""Pydantic schemas for Agent Chat (Claude tool-use)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """A single message in the conversation."""

    role: str = Field(..., description="Message role: user, assistant, or system")
    content: str = Field(..., description="Message content")


class AgentChatRequest(BaseModel):
    """Request body for the agent chat endpoint."""

    messages: list[ChatMessage] = Field(..., min_length=1, description="Conversation messages")
    patient_id: str | None = Field(None, description="Optional patient ID to scope tools")
    model: str | None = Field(None, description="Override default model")


class ToolCallInfo(BaseModel):
    """Metadata about a single tool call made during the response."""

    tool_name: str
    tool_input: dict[str, Any]
    result_summary: str = Field("", description="Truncated preview of tool result")


class TokenUsage(BaseModel):
    """Token usage from Anthropic API."""

    input_tokens: int = 0
    output_tokens: int = 0


class AgentChatResponse(BaseModel):
    """Response from the agent chat endpoint."""

    response: str = Field(..., description="Final assistant response text")
    tool_calls: list[ToolCallInfo] = Field(default_factory=list)
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    model: str = ""
