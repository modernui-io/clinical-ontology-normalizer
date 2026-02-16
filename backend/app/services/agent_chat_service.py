"""Agentic chat service using Claude tool-use for clinical data queries.

Implements a loop:
  1. Send user messages + tool schemas to Claude
  2. If stop_reason="tool_use", execute tool handlers against DB
  3. Send tool_results back to Claude
  4. Repeat until stop_reason="end_turn" (max 10 rounds)
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.schemas.agent_chat import (
    AgentChatResponse,
    ChatMessage,
    TokenUsage,
    ToolCallInfo,
)
from app.services.agent_tools import TOOL_HANDLERS, TOOL_SCHEMAS

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 10

SYSTEM_PROMPT = """\
You are a clinical data assistant with tool-use access to a patient database \
containing clinical facts (conditions, medications, labs, procedures, visits), \
a knowledge graph, and clinical trial eligibility screening.

Guidelines:
- Always call the appropriate tool(s) to retrieve data before answering.
- Cite specific data points (concept names, values, dates) from tool results.
- Never fabricate clinical information.  If data is missing, say so explicitly.
- When discussing findings, note that all results require clinician review.
- Be concise but thorough.  Prefer structured output (lists, tables) when \
  presenting multiple items.
- If a patient_id is provided in the conversation context, use it for tool calls.
"""


class ClinicalAgentChatService:
    """Agentic chat service backed by Claude with clinical data tools."""

    def __init__(self) -> None:
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
            except ImportError:
                raise ImportError(
                    "anthropic package required. Install with: pip install anthropic"
                )
            api_key = settings.anthropic_api_key
            if not api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY not configured. "
                    "Set the anthropic_api_key environment variable."
                )
            self._client = AsyncAnthropic(api_key=api_key)
        return self._client

    async def chat(
        self,
        messages: list[ChatMessage],
        session: AsyncSession,
        *,
        model: str | None = None,
        patient_id: str | None = None,
    ) -> AgentChatResponse:
        client = self._get_client()
        model = model or settings.llm_model

        # Build Anthropic message list
        anthropic_messages: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role != "system":
                anthropic_messages.append({"role": msg.role, "content": msg.content})

        tool_calls_log: list[ToolCallInfo] = []
        total_input = 0
        total_output = 0

        for _round in range(MAX_TOOL_ROUNDS):
            response = await client.messages.create(
                model=model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=anthropic_messages,
                tools=TOOL_SCHEMAS,
            )

            total_input += response.usage.input_tokens
            total_output += response.usage.output_tokens

            # If the model produced end_turn, extract text and return
            if response.stop_reason == "end_turn":
                text_parts = [
                    block.text
                    for block in response.content
                    if block.type == "text"
                ]
                return AgentChatResponse(
                    response="\n".join(text_parts),
                    tool_calls=tool_calls_log,
                    token_usage=TokenUsage(
                        input_tokens=total_input,
                        output_tokens=total_output,
                    ),
                    model=model,
                )

            # Process tool_use blocks
            # First, append the full assistant message (text + tool_use blocks)
            anthropic_messages.append({"role": "assistant", "content": response.content})

            tool_result_blocks: list[dict[str, Any]] = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                tool_name = block.name
                tool_input = block.input
                tool_use_id = block.id

                logger.info(f"Agent calling tool: {tool_name} with input: {json.dumps(tool_input)[:200]}")

                handler = TOOL_HANDLERS.get(tool_name)
                if handler is None:
                    result_data = {"error": f"Unknown tool: {tool_name}"}
                else:
                    try:
                        result_data = await handler(tool_input, session)
                    except Exception as e:
                        logger.exception(f"Tool handler {tool_name} failed")
                        result_data = {"error": f"Tool execution failed: {str(e)[:200]}"}

                result_json = json.dumps(result_data, default=str)

                # Log the tool call
                tool_calls_log.append(
                    ToolCallInfo(
                        tool_name=tool_name,
                        tool_input=tool_input,
                        result_summary=result_json[:300],
                    )
                )

                tool_result_blocks.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": result_json,
                })

            # Append tool results as user message
            anthropic_messages.append({"role": "user", "content": tool_result_blocks})

        # Max rounds exceeded — extract whatever text the model produced
        text_parts = [
            block.text
            for block in response.content
            if block.type == "text"
        ]
        return AgentChatResponse(
            response="\n".join(text_parts) if text_parts else "(Max tool rounds reached without final response.)",
            tool_calls=tool_calls_log,
            token_usage=TokenUsage(
                input_tokens=total_input,
                output_tokens=total_output,
            ),
            model=model,
        )


# Singleton
_agent_chat_service: ClinicalAgentChatService | None = None


def get_agent_chat_service() -> ClinicalAgentChatService:
    global _agent_chat_service
    if _agent_chat_service is None:
        _agent_chat_service = ClinicalAgentChatService()
    return _agent_chat_service
