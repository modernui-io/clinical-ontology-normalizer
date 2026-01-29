"""AI Interaction Audit Service.

Logs and queries AI model interactions for:
- Compliance auditing (what AI was asked, by whom)
- Performance monitoring (latency, token usage)
- User feedback collection (thumbs up/down)
- Usage analytics (model distribution, prompt patterns)
"""

from __future__ import annotations

import hashlib
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AiAuditEntry:
    """Record of a single AI interaction."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    model_name: str = ""
    prompt_hash: str = ""
    prompt_tokens: int = 0
    response_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    status: str = "success"  # success, error, timeout
    feedback: str | None = None  # thumbs_up, thumbs_down, None
    feedback_comment: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AiAuditStats:
    """Aggregate statistics for AI interactions."""

    total_interactions: int = 0
    total_tokens: int = 0
    avg_latency_ms: float = 0.0
    success_rate: float = 0.0
    feedback_positive: int = 0
    feedback_negative: int = 0
    model_distribution: dict[str, int] = field(default_factory=dict)
    user_distribution: dict[str, int] = field(default_factory=dict)


class AiAuditService:
    """Service for logging and querying AI interactions."""

    def __init__(self):
        """Initialize AI audit service."""
        self._entries: list[AiAuditEntry] = []
        self._lock = threading.Lock()
        self._max_entries = 10000
        logger.info("AiAuditService initialized")

    def log_interaction(
        self,
        user_id: str,
        model_name: str,
        prompt_text: str | None = None,
        prompt_tokens: int = 0,
        response_tokens: int = 0,
        latency_ms: float = 0.0,
        status: str = "success",
        metadata: dict[str, Any] | None = None,
    ) -> AiAuditEntry:
        """Log an AI interaction.

        Args:
            user_id: ID of the user making the request.
            model_name: Name of the AI model used.
            prompt_text: Optional prompt text (hashed, not stored directly).
            prompt_tokens: Number of tokens in the prompt.
            response_tokens: Number of tokens in the response.
            latency_ms: Request latency in milliseconds.
            status: Interaction status (success, error, timeout).
            metadata: Additional metadata.

        Returns:
            The created audit entry.
        """
        prompt_hash = ""
        if prompt_text:
            prompt_hash = hashlib.sha256(prompt_text.encode()).hexdigest()[:16]

        entry = AiAuditEntry(
            user_id=user_id,
            model_name=model_name,
            prompt_hash=prompt_hash,
            prompt_tokens=prompt_tokens,
            response_tokens=response_tokens,
            total_tokens=prompt_tokens + response_tokens,
            latency_ms=latency_ms,
            status=status,
            metadata=metadata or {},
        )

        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self._max_entries:
                self._entries = self._entries[-self._max_entries:]

        return entry

    def get_entries(
        self,
        user_id: str | None = None,
        model_name: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AiAuditEntry], int]:
        """Query audit entries with optional filters.

        Returns:
            Tuple of (entries, total_count).
        """
        with self._lock:
            filtered = self._entries[:]

        if user_id:
            filtered = [e for e in filtered if e.user_id == user_id]
        if model_name:
            filtered = [e for e in filtered if e.model_name == model_name]
        if status:
            filtered = [e for e in filtered if e.status == status]

        # Sort by created_at descending
        filtered.sort(key=lambda e: e.created_at, reverse=True)
        total = len(filtered)

        return filtered[offset:offset + limit], total

    def submit_feedback(
        self,
        entry_id: str,
        feedback: str,
        comment: str | None = None,
    ) -> AiAuditEntry | None:
        """Submit feedback for an AI interaction.

        Args:
            entry_id: ID of the audit entry.
            feedback: Feedback type (thumbs_up or thumbs_down).
            comment: Optional feedback comment.

        Returns:
            Updated entry or None if not found.
        """
        with self._lock:
            for entry in self._entries:
                if entry.id == entry_id:
                    entry.feedback = feedback
                    entry.feedback_comment = comment
                    return entry

        return None

    def get_stats(
        self,
        user_id: str | None = None,
    ) -> AiAuditStats:
        """Get aggregate statistics.

        Args:
            user_id: Optional user filter.

        Returns:
            AiAuditStats with aggregated data.
        """
        with self._lock:
            entries = self._entries[:]

        if user_id:
            entries = [e for e in entries if e.user_id == user_id]

        if not entries:
            return AiAuditStats()

        total = len(entries)
        total_tokens = sum(e.total_tokens for e in entries)
        avg_latency = sum(e.latency_ms for e in entries) / total
        successes = sum(1 for e in entries if e.status == "success")
        positive = sum(1 for e in entries if e.feedback == "thumbs_up")
        negative = sum(1 for e in entries if e.feedback == "thumbs_down")

        model_dist: dict[str, int] = {}
        user_dist: dict[str, int] = {}
        for e in entries:
            model_dist[e.model_name] = model_dist.get(e.model_name, 0) + 1
            user_dist[e.user_id] = user_dist.get(e.user_id, 0) + 1

        return AiAuditStats(
            total_interactions=total,
            total_tokens=total_tokens,
            avg_latency_ms=round(avg_latency, 2),
            success_rate=round(successes / total, 4) if total > 0 else 0.0,
            feedback_positive=positive,
            feedback_negative=negative,
            model_distribution=model_dist,
            user_distribution=user_dist,
        )


# Singleton
_service_instance: AiAuditService | None = None
_instance_lock = threading.Lock()


def get_ai_audit_service() -> AiAuditService:
    """Get singleton instance of AiAuditService."""
    global _service_instance
    if _service_instance is None:
        with _instance_lock:
            if _service_instance is None:
                _service_instance = AiAuditService()
    return _service_instance


def reset_ai_audit_service() -> None:
    """Reset the service singleton (for testing)."""
    global _service_instance
    _service_instance = None
