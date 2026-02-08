"""Structured JSON Logging Configuration (CTO-6).

Production-grade structured logging with:
- JSON output for log aggregation (ELK, Datadog, CloudWatch, etc.)
- Colored human-readable output for development
- PHI redaction filter (SSN, MRN patterns)
- Contextvar-based request_id/user_id/trace_id injection
- Proper exception/traceback serialization in JSON

Usage:
    from app.core.logging_config import setup_logging
    setup_logging()  # Call once at app startup, before any log calls
"""

from __future__ import annotations

import json
import logging
import re
import sys
import traceback
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# PHI Redaction Filter
# ---------------------------------------------------------------------------

# Patterns that look like protected health information
_PHI_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # US Social Security Numbers: 123-45-6789, 123456789
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "***-**-****"),
    (re.compile(r"\b\d{9}\b(?=\s|$|[,;.])"), "*********"),
    # Medical Record Numbers (common formats: MRN-123456, MRN123456, MRN: 123456)
    (re.compile(r"\bMRN[-:\s]?\d{4,10}\b", re.IGNORECASE), "MRN-REDACTED"),
    # Patient account numbers (common hospital pattern)
    (re.compile(r"\bACCT[-:\s]?\d{6,12}\b", re.IGNORECASE), "ACCT-REDACTED"),
]


def _redact_phi(text: str) -> str:
    """Replace PHI patterns in *text* with redacted placeholders."""
    for pattern, replacement in _PHI_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class PHIRedactionFilter(logging.Filter):
    """Logging filter that redacts PHI patterns from log messages.

    Scans the formatted message for SSN, MRN, and account-number patterns
    and replaces them with safe placeholders.  Operates on ``record.msg``
    *before* formatting so that both the message string and any ``%s``
    arguments are covered.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # Redact the main message
        if isinstance(record.msg, str):
            record.msg = _redact_phi(record.msg)

        # Redact positional args that are strings
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: _redact_phi(v) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    _redact_phi(a) if isinstance(a, str) else a for a in record.args
                )

        return True  # Always allow the record through


# ---------------------------------------------------------------------------
# Context-Injecting Filter
# ---------------------------------------------------------------------------


class ContextInjectFilter(logging.Filter):
    """Inject request_id, user_id, and trace_id from contextvars.

    This ensures that *every* log record carries the current request
    context regardless of whether the caller remembered to pass ``extra``.
    Explicit ``extra`` values take precedence over contextvar values.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # Import here to avoid circular imports at module load time
        from app.api.middleware.request_id import get_request_id

        # request_id
        if not getattr(record, "request_id", None):
            record.request_id = get_request_id()  # type: ignore[attr-defined]

        # user_id - from database request context
        if not getattr(record, "user_id", None):
            try:
                from app.core.database import get_db_request_context

                ctx = get_db_request_context()
                if ctx and ctx.user_id:
                    record.user_id = ctx.user_id  # type: ignore[attr-defined]
            except Exception:
                pass

        # trace_id - some callers may set it via extra; default to None
        if not hasattr(record, "trace_id"):
            record.trace_id = None  # type: ignore[attr-defined]

        return True


# ---------------------------------------------------------------------------
# JSON Formatter
# ---------------------------------------------------------------------------

# Standard LogRecord attributes that should NOT be forwarded as extras.
_BUILTIN_LOG_ATTRS: frozenset[str] = frozenset(
    {
        "name",
        "msg",
        "args",
        "created",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "exc_info",
        "exc_text",
        "thread",
        "threadName",
        "taskName",
        "message",
        # Our injected fields are handled explicitly
        "request_id",
        "user_id",
        "trace_id",
    }
)


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter.

    Every log line is a single JSON object with:
    - timestamp (ISO-8601 UTC)
    - level
    - logger
    - message
    - module, function, line
    - request_id, user_id, trace_id (from context)
    - exception + traceback (when present)
    - any additional ``extra`` fields from the caller
    """

    def format(self, record: logging.LogRecord) -> str:
        # Build the message via the standard mechanism so %-formatting works
        message = record.getMessage()

        log_entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": message,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Context fields (injected by ContextInjectFilter)
        request_id = getattr(record, "request_id", None)
        if request_id:
            log_entry["request_id"] = request_id

        user_id = getattr(record, "user_id", None)
        if user_id:
            log_entry["user_id"] = user_id

        trace_id = getattr(record, "trace_id", None)
        if trace_id:
            log_entry["trace_id"] = trace_id

        # Exception handling - include full traceback
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }

        if record.stack_info:
            log_entry["stack_info"] = record.stack_info

        # Forward any extra fields the caller passed
        for key, value in record.__dict__.items():
            if key not in _BUILTIN_LOG_ATTRS and not key.startswith("_"):
                try:
                    json.dumps(value, default=str)  # ensure serializable
                    log_entry[key] = value
                except (TypeError, ValueError):
                    log_entry[key] = str(value)

        return json.dumps(log_entry, default=str, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Colored Console Formatter (development)
# ---------------------------------------------------------------------------


class ColoredFormatter(logging.Formatter):
    """Human-readable colored console formatter for development.

    Color-codes the log level and includes request_id when available.
    """

    COLORS: dict[str, str] = {
        "DEBUG": "\033[36m",      # Cyan
        "INFO": "\033[32m",       # Green
        "WARNING": "\033[33m",    # Yellow
        "ERROR": "\033[31m",      # Red
        "CRITICAL": "\033[1;31m", # Bold Red
    }
    RESET = "\033[0m"
    DIM = "\033[2m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)

        # Build a request_id tag if available
        request_id = getattr(record, "request_id", None)
        rid_tag = f" [{request_id}]" if request_id else ""

        # Format: TIME | LEVEL | logger | [request_id] message
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%H:%M:%S.%f")[:-3]
        level = f"{color}{record.levelname:<8}{self.RESET}"
        name = f"{self.DIM}{record.name}{self.RESET}"
        msg = record.getMessage()

        line = f"{ts} | {level} | {name}{rid_tag} | {msg}"

        # Append exception info
        if record.exc_info and record.exc_info[0] is not None:
            line += "\n" + self.formatException(record.exc_info)

        if record.stack_info:
            line += "\n" + record.stack_info

        return line


# ---------------------------------------------------------------------------
# Public Setup Function
# ---------------------------------------------------------------------------


def setup_logging(json_mode: bool | None = None) -> None:
    """Configure the root logger for the application.

    Call this **once** at startup, before the FastAPI app begins serving.

    Args:
        json_mode: Force JSON (``True``) or colored (``False``) output.
                   When ``None`` (the default), the mode is chosen automatically:
                   JSON for non-debug environments, colored for debug.
    """
    from app.core.config import settings

    # Resolve log level from settings
    level_name: str = getattr(settings, "log_level", "INFO").upper()
    log_level: int = getattr(logging, level_name, logging.INFO)

    # Resolve output mode
    if json_mode is None:
        json_mode = not settings.debug

    # Build the handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    if json_mode:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(ColoredFormatter())

    # Attach filters (order matters: context first, then redaction)
    handler.addFilter(ContextInjectFilter())
    handler.addFilter(PHIRedactionFilter())

    # Configure root logger
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.debug else logging.WARNING
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("watchfiles").setLevel(logging.WARNING)

    # Emit a startup confirmation so operators can verify the format
    logger = logging.getLogger("app.core.logging_config")
    logger.info(
        "Logging configured",
        extra={
            "log_level": level_name,
            "format": "json" if json_mode else "colored",
            "environment": settings.environment,
            "phi_redaction": True,
        },
    )
