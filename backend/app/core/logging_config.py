"""Structured Logging Configuration.

VP-DevOps: Provides JSON-formatted structured logging for production environments.
Enables log aggregation with ELK, Datadog, CloudWatch, etc.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging.

    Outputs logs in JSON format for easy parsing by log aggregation systems.
    Includes standard fields: timestamp, level, logger, message, and extras.
    """

    def format(self, record: logging.LogRecord) -> str:
        import json

        log_record: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        # Add extra fields (e.g., request_id, patient_id)
        if hasattr(record, "request_id"):
            log_record["request_id"] = record.request_id
        if hasattr(record, "user_id"):
            log_record["user_id"] = record.user_id
        if hasattr(record, "patient_id"):
            log_record["patient_id"] = record.patient_id
        if hasattr(record, "duration_ms"):
            log_record["duration_ms"] = record.duration_ms

        # Include any other extra attributes
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "exc_info", "exc_text", "thread", "threadName",
                "request_id", "user_id", "patient_id", "duration_ms", "message",
            }:
                log_record[key] = value

        return json.dumps(log_record, default=str)


class ColoredFormatter(logging.Formatter):
    """Colored console formatter for development environments."""

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def configure_logging() -> None:
    """Configure application logging based on environment.

    - Development: Colored console output with DEBUG level
    - Production: JSON structured output with INFO level

    Call this function early in application startup (before FastAPI app creation).
    """
    # Determine log level from settings
    log_level = logging.DEBUG if settings.debug else logging.INFO

    # Create handler
    handler = logging.StreamHandler(sys.stdout)

    # Use JSON format in production, colored format in development
    if settings.debug:
        formatter = ColoredFormatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )
    else:
        formatter = JSONFormatter()

    handler.setFormatter(formatter)
    handler.setLevel(log_level)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Configure specific loggers
    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.debug else logging.WARNING
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info(
        "Logging configured",
        extra={
            "environment": "development" if settings.debug else "production",
            "log_level": logging.getLevelName(log_level),
            "format": "colored" if settings.debug else "json",
        },
    )


class LoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that includes request context in all log messages.

    Usage:
        logger = LoggerAdapter(logging.getLogger(__name__), {"request_id": "abc123"})
        logger.info("Processing request")  # Includes request_id in output
    """

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        # Merge extra context
        extra = kwargs.get("extra", {})
        extra.update(self.extra)
        kwargs["extra"] = extra
        return msg, kwargs
