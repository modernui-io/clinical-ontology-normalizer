"""KG Structured Logging Service.

This module provides structured logging with correlation ID tracking,
context propagation, and multiple output formats for the Knowledge Graph API.
"""

import json
import logging
import os
import sys
import threading
import time
import traceback
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TextIO, Union


class LogLevel(str, Enum):
    """Log levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# Map to Python logging levels
LEVEL_MAP = {
    LogLevel.DEBUG: logging.DEBUG,
    LogLevel.INFO: logging.INFO,
    LogLevel.WARNING: logging.WARNING,
    LogLevel.ERROR: logging.ERROR,
    LogLevel.CRITICAL: logging.CRITICAL,
}


class LogCategory(str, Enum):
    """Log categories for filtering."""

    REQUEST = "request"
    RESPONSE = "response"
    DATABASE = "database"
    CACHE = "cache"
    REASONING = "reasoning"
    SECURITY = "security"
    PERFORMANCE = "performance"
    AUDIT = "audit"
    SYSTEM = "system"
    API = "api"
    WEBHOOK = "webhook"
    BATCH = "batch"
    ERROR = "error"


# Context variable for correlation ID
_correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)
_request_context: ContextVar[Dict[str, Any]] = ContextVar("request_context", default={})


def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID."""
    return _correlation_id.get()


def set_correlation_id(correlation_id: str) -> None:
    """Set the correlation ID for the current context."""
    _correlation_id.set(correlation_id)


def generate_correlation_id() -> str:
    """Generate a new correlation ID."""
    return f"corr_{uuid.uuid4().hex[:16]}"


def get_request_context() -> Dict[str, Any]:
    """Get the current request context."""
    return _request_context.get()


def set_request_context(context: Dict[str, Any]) -> None:
    """Set the request context."""
    _request_context.set(context)


def update_request_context(**kwargs) -> None:
    """Update the request context with additional fields."""
    current = _request_context.get().copy()
    current.update(kwargs)
    _request_context.set(current)


@dataclass
class LogEntry:
    """Structured log entry."""

    timestamp: str
    level: LogLevel
    message: str
    correlation_id: Optional[str] = None
    category: Optional[LogCategory] = None
    logger_name: str = "kg"
    service: str = "kg-api"
    environment: str = "development"

    # Request context
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None
    status_code: Optional[int] = None

    # Performance
    duration_ms: Optional[float] = None

    # Error information
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None

    # Additional context
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        result = {}
        for key, value in asdict(self).items():
            if value is not None and value != {}:
                if isinstance(value, Enum):
                    result[key] = value.value
                else:
                    result[key] = value
        return result

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class LogFormatter:
    """Base class for log formatters."""

    def format(self, entry: LogEntry) -> str:
        """Format a log entry."""
        raise NotImplementedError


class JSONFormatter(LogFormatter):
    """JSON log formatter."""

    def __init__(self, pretty: bool = False):
        """Initialize the formatter.

        Args:
            pretty: Whether to pretty-print JSON
        """
        self.pretty = pretty

    def format(self, entry: LogEntry) -> str:
        """Format as JSON."""
        if self.pretty:
            return json.dumps(entry.to_dict(), indent=2, default=str)
        return entry.to_json()


class TextFormatter(LogFormatter):
    """Human-readable text formatter."""

    def __init__(
        self,
        include_timestamp: bool = True,
        include_correlation: bool = True,
        include_extra: bool = False,
    ):
        """Initialize the formatter."""
        self.include_timestamp = include_timestamp
        self.include_correlation = include_correlation
        self.include_extra = include_extra

    def format(self, entry: LogEntry) -> str:
        """Format as human-readable text."""
        parts = []

        if self.include_timestamp:
            parts.append(entry.timestamp)

        parts.append(f"[{entry.level.value}]")

        if self.include_correlation and entry.correlation_id:
            parts.append(f"[{entry.correlation_id}]")

        if entry.category:
            parts.append(f"[{entry.category.value}]")

        parts.append(entry.message)

        if entry.duration_ms is not None:
            parts.append(f"({entry.duration_ms:.2f}ms)")

        if entry.error_type:
            parts.append(f"- {entry.error_type}: {entry.error_message}")

        if self.include_extra and entry.extra:
            parts.append(f"| {entry.extra}")

        return " ".join(parts)


class LogHandler:
    """Base class for log handlers."""

    def __init__(
        self,
        formatter: LogFormatter,
        min_level: LogLevel = LogLevel.DEBUG,
        categories: Optional[List[LogCategory]] = None,
    ):
        """Initialize the handler.

        Args:
            formatter: Log formatter to use
            min_level: Minimum log level to handle
            categories: Categories to filter (None = all)
        """
        self.formatter = formatter
        self.min_level = min_level
        self.categories = set(categories) if categories else None

    def should_handle(self, entry: LogEntry) -> bool:
        """Check if this handler should process the entry."""
        # Check level
        if LEVEL_MAP[entry.level] < LEVEL_MAP[self.min_level]:
            return False

        # Check category filter
        if self.categories and entry.category and entry.category not in self.categories:
            return False

        return True

    def emit(self, entry: LogEntry) -> None:
        """Emit a log entry."""
        raise NotImplementedError


class StreamHandler(LogHandler):
    """Handler that writes to a stream (stdout/stderr)."""

    def __init__(
        self,
        stream: TextIO = sys.stdout,
        formatter: Optional[LogFormatter] = None,
        min_level: LogLevel = LogLevel.DEBUG,
        categories: Optional[List[LogCategory]] = None,
    ):
        """Initialize the stream handler."""
        super().__init__(
            formatter=formatter or TextFormatter(),
            min_level=min_level,
            categories=categories,
        )
        self.stream = stream
        self._lock = threading.Lock()

    def emit(self, entry: LogEntry) -> None:
        """Emit to stream."""
        if not self.should_handle(entry):
            return

        message = self.formatter.format(entry)
        with self._lock:
            self.stream.write(message + "\n")
            self.stream.flush()


class FileHandler(LogHandler):
    """Handler that writes to a file."""

    def __init__(
        self,
        filepath: str,
        formatter: Optional[LogFormatter] = None,
        min_level: LogLevel = LogLevel.DEBUG,
        categories: Optional[List[LogCategory]] = None,
        max_size_mb: int = 100,
        backup_count: int = 5,
    ):
        """Initialize the file handler.

        Args:
            filepath: Path to log file
            formatter: Log formatter
            min_level: Minimum log level
            categories: Category filter
            max_size_mb: Max file size before rotation
            backup_count: Number of backup files to keep
        """
        super().__init__(
            formatter=formatter or JSONFormatter(),
            min_level=min_level,
            categories=categories,
        )
        self.filepath = filepath
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.backup_count = backup_count
        self._lock = threading.Lock()
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        """Ensure the log directory exists."""
        directory = os.path.dirname(self.filepath)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

    def _should_rotate(self) -> bool:
        """Check if the log file should be rotated."""
        if not os.path.exists(self.filepath):
            return False
        return os.path.getsize(self.filepath) >= self.max_size_bytes

    def _rotate(self) -> None:
        """Rotate log files."""
        # Remove oldest backup
        oldest = f"{self.filepath}.{self.backup_count}"
        if os.path.exists(oldest):
            os.remove(oldest)

        # Shift existing backups
        for i in range(self.backup_count - 1, 0, -1):
            src = f"{self.filepath}.{i}"
            dst = f"{self.filepath}.{i + 1}"
            if os.path.exists(src):
                os.rename(src, dst)

        # Move current to .1
        if os.path.exists(self.filepath):
            os.rename(self.filepath, f"{self.filepath}.1")

    def emit(self, entry: LogEntry) -> None:
        """Emit to file."""
        if not self.should_handle(entry):
            return

        message = self.formatter.format(entry)

        with self._lock:
            if self._should_rotate():
                self._rotate()

            with open(self.filepath, "a") as f:
                f.write(message + "\n")


class MemoryHandler(LogHandler):
    """Handler that keeps logs in memory (for testing)."""

    def __init__(
        self,
        max_entries: int = 1000,
        formatter: Optional[LogFormatter] = None,
        min_level: LogLevel = LogLevel.DEBUG,
        categories: Optional[List[LogCategory]] = None,
    ):
        """Initialize the memory handler."""
        super().__init__(
            formatter=formatter or JSONFormatter(),
            min_level=min_level,
            categories=categories,
        )
        self.max_entries = max_entries
        self._entries: List[LogEntry] = []
        self._lock = threading.Lock()

    def emit(self, entry: LogEntry) -> None:
        """Emit to memory."""
        if not self.should_handle(entry):
            return

        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self.max_entries:
                self._entries = self._entries[-self.max_entries:]

    def get_entries(
        self,
        level: Optional[LogLevel] = None,
        category: Optional[LogCategory] = None,
        correlation_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[LogEntry]:
        """Get logged entries with optional filters."""
        with self._lock:
            entries = list(self._entries)

        if level:
            entries = [e for e in entries if e.level == level]

        if category:
            entries = [e for e in entries if e.category == category]

        if correlation_id:
            entries = [e for e in entries if e.correlation_id == correlation_id]

        return entries[-limit:]

    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self._entries.clear()


class KGLogger:
    """Structured logger for Knowledge Graph API."""

    def __init__(
        self,
        name: str = "kg",
        service: str = "kg-api",
        environment: Optional[str] = None,
    ):
        """Initialize the logger.

        Args:
            name: Logger name
            service: Service name for logs
            environment: Environment (default: from KG_ENV or "development")
        """
        self.name = name
        self.service = service
        self.environment = environment or os.environ.get("KG_ENV", "development")
        self._handlers: List[LogHandler] = []
        self._lock = threading.Lock()

    def add_handler(self, handler: LogHandler) -> None:
        """Add a log handler."""
        with self._lock:
            self._handlers.append(handler)

    def remove_handler(self, handler: LogHandler) -> None:
        """Remove a log handler."""
        with self._lock:
            if handler in self._handlers:
                self._handlers.remove(handler)

    def _create_entry(
        self,
        level: LogLevel,
        message: str,
        category: Optional[LogCategory] = None,
        error: Optional[Exception] = None,
        duration_ms: Optional[float] = None,
        **extra,
    ) -> LogEntry:
        """Create a log entry with context."""
        # Get current context
        correlation_id = get_correlation_id()
        request_context = get_request_context()

        # Build entry
        entry = LogEntry(
            timestamp=datetime.utcnow().isoformat() + "Z",
            level=level,
            message=message,
            correlation_id=correlation_id,
            category=category,
            logger_name=self.name,
            service=self.service,
            environment=self.environment,
            request_id=request_context.get("request_id"),
            user_id=request_context.get("user_id"),
            session_id=request_context.get("session_id"),
            endpoint=request_context.get("endpoint"),
            method=request_context.get("method"),
            status_code=request_context.get("status_code"),
            duration_ms=duration_ms,
            extra=extra if extra else {},
        )

        # Add error info
        if error:
            entry.error_type = type(error).__name__
            entry.error_message = str(error)
            entry.stack_trace = traceback.format_exc()

        return entry

    def _emit(self, entry: LogEntry) -> None:
        """Emit entry to all handlers."""
        with self._lock:
            handlers = list(self._handlers)

        for handler in handlers:
            try:
                handler.emit(entry)
            except Exception:
                pass  # Don't let handler errors break logging

    def log(
        self,
        level: LogLevel,
        message: str,
        category: Optional[LogCategory] = None,
        error: Optional[Exception] = None,
        duration_ms: Optional[float] = None,
        **extra,
    ) -> LogEntry:
        """Log a message at the specified level."""
        entry = self._create_entry(
            level=level,
            message=message,
            category=category,
            error=error,
            duration_ms=duration_ms,
            **extra,
        )
        self._emit(entry)
        return entry

    def debug(
        self,
        message: str,
        category: Optional[LogCategory] = None,
        **extra,
    ) -> LogEntry:
        """Log a debug message."""
        return self.log(LogLevel.DEBUG, message, category=category, **extra)

    def info(
        self,
        message: str,
        category: Optional[LogCategory] = None,
        **extra,
    ) -> LogEntry:
        """Log an info message."""
        return self.log(LogLevel.INFO, message, category=category, **extra)

    def warning(
        self,
        message: str,
        category: Optional[LogCategory] = None,
        **extra,
    ) -> LogEntry:
        """Log a warning message."""
        return self.log(LogLevel.WARNING, message, category=category, **extra)

    def error(
        self,
        message: str,
        category: Optional[LogCategory] = None,
        error: Optional[Exception] = None,
        **extra,
    ) -> LogEntry:
        """Log an error message."""
        return self.log(
            LogLevel.ERROR,
            message,
            category=category or LogCategory.ERROR,
            error=error,
            **extra,
        )

    def critical(
        self,
        message: str,
        category: Optional[LogCategory] = None,
        error: Optional[Exception] = None,
        **extra,
    ) -> LogEntry:
        """Log a critical message."""
        return self.log(
            LogLevel.CRITICAL,
            message,
            category=category or LogCategory.ERROR,
            error=error,
            **extra,
        )

    # Convenience methods for common log patterns

    def log_request(
        self,
        method: str,
        endpoint: str,
        **extra,
    ) -> LogEntry:
        """Log an incoming request."""
        return self.info(
            f"{method} {endpoint}",
            category=LogCategory.REQUEST,
            **extra,
        )

    def log_response(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        duration_ms: float,
        **extra,
    ) -> LogEntry:
        """Log a response."""
        level = LogLevel.INFO if status_code < 400 else LogLevel.WARNING
        return self.log(
            level,
            f"{method} {endpoint} -> {status_code}",
            category=LogCategory.RESPONSE,
            duration_ms=duration_ms,
            **extra,
        )

    def log_database_query(
        self,
        query_type: str,
        duration_ms: float,
        success: bool = True,
        **extra,
    ) -> LogEntry:
        """Log a database query."""
        level = LogLevel.DEBUG if success else LogLevel.ERROR
        status = "completed" if success else "failed"
        return self.log(
            level,
            f"Database query {query_type} {status}",
            category=LogCategory.DATABASE,
            duration_ms=duration_ms,
            **extra,
        )

    def log_cache_operation(
        self,
        operation: str,
        hit: bool = True,
        **extra,
    ) -> LogEntry:
        """Log a cache operation."""
        return self.debug(
            f"Cache {operation}: {'hit' if hit else 'miss'}",
            category=LogCategory.CACHE,
            **extra,
        )

    def log_security_event(
        self,
        event: str,
        success: bool = True,
        **extra,
    ) -> LogEntry:
        """Log a security event."""
        level = LogLevel.INFO if success else LogLevel.WARNING
        return self.log(
            level,
            f"Security: {event}",
            category=LogCategory.SECURITY,
            **extra,
        )


def with_correlation_id(func: Callable) -> Callable:
    """Decorator to ensure a correlation ID is set for the function call."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not get_correlation_id():
            set_correlation_id(generate_correlation_id())
        return func(*args, **kwargs)
    return wrapper


def with_correlation_id_async(func: Callable) -> Callable:
    """Async decorator to ensure a correlation ID is set."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        if not get_correlation_id():
            set_correlation_id(generate_correlation_id())
        return await func(*args, **kwargs)
    return wrapper


class LogContext:
    """Context manager for setting logging context."""

    def __init__(
        self,
        correlation_id: Optional[str] = None,
        **context,
    ):
        """Initialize the context.

        Args:
            correlation_id: Correlation ID to set (generates if None)
            **context: Additional context fields
        """
        self.correlation_id = correlation_id or generate_correlation_id()
        self.context = context
        self._old_correlation_id: Optional[str] = None
        self._old_context: Dict[str, Any] = {}

    def __enter__(self) -> "LogContext":
        """Enter the context."""
        self._old_correlation_id = get_correlation_id()
        self._old_context = get_request_context()

        set_correlation_id(self.correlation_id)
        set_request_context({**self._old_context, **self.context})

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the context."""
        if self._old_correlation_id:
            set_correlation_id(self._old_correlation_id)
        else:
            _correlation_id.set(None)
        set_request_context(self._old_context)


class TimedLogContext:
    """Context manager that logs duration on exit."""

    def __init__(
        self,
        logger: KGLogger,
        message: str,
        level: LogLevel = LogLevel.INFO,
        category: Optional[LogCategory] = None,
        **extra,
    ):
        """Initialize the timed context.

        Args:
            logger: Logger to use
            message: Log message
            level: Log level
            category: Log category
            **extra: Additional context
        """
        self.logger = logger
        self.message = message
        self.level = level
        self.category = category
        self.extra = extra
        self._start_time: float = 0

    def __enter__(self) -> "TimedLogContext":
        """Enter the context."""
        self._start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the context and log duration."""
        duration_ms = (time.time() - self._start_time) * 1000

        if exc_type:
            self.logger.error(
                f"{self.message} failed",
                category=self.category,
                error=exc_val,
                duration_ms=duration_ms,
                **self.extra,
            )
        else:
            self.logger.log(
                self.level,
                f"{self.message} completed",
                category=self.category,
                duration_ms=duration_ms,
                **self.extra,
            )


# Singleton logger instance
_logger: Optional[KGLogger] = None
_logger_lock = threading.Lock()


def get_logger() -> KGLogger:
    """Get the singleton logger instance."""
    global _logger
    if _logger is None:
        with _logger_lock:
            if _logger is None:
                _logger = KGLogger()
                # Add default console handler
                _logger.add_handler(StreamHandler(
                    formatter=TextFormatter(),
                    min_level=LogLevel.INFO,
                ))
    return _logger


def reset_logger() -> None:
    """Reset the singleton logger (for testing)."""
    global _logger
    with _logger_lock:
        _logger = None


def configure_logger(
    name: str = "kg",
    service: str = "kg-api",
    environment: Optional[str] = None,
    console_level: LogLevel = LogLevel.INFO,
    console_format: str = "text",
    file_path: Optional[str] = None,
    file_level: LogLevel = LogLevel.DEBUG,
    file_format: str = "json",
) -> KGLogger:
    """Configure and return the singleton logger.

    Args:
        name: Logger name
        service: Service name
        environment: Environment name
        console_level: Minimum level for console output
        console_format: Console format ("text" or "json")
        file_path: Optional file path for file logging
        file_level: Minimum level for file output
        file_format: File format ("text" or "json")

    Returns:
        Configured KGLogger instance
    """
    global _logger

    with _logger_lock:
        _logger = KGLogger(
            name=name,
            service=service,
            environment=environment,
        )

        # Configure console handler
        console_formatter = (
            TextFormatter() if console_format == "text" else JSONFormatter()
        )
        _logger.add_handler(StreamHandler(
            formatter=console_formatter,
            min_level=console_level,
        ))

        # Configure file handler if path provided
        if file_path:
            file_formatter = (
                TextFormatter() if file_format == "text" else JSONFormatter()
            )
            _logger.add_handler(FileHandler(
                filepath=file_path,
                formatter=file_formatter,
                min_level=file_level,
            ))

        return _logger
