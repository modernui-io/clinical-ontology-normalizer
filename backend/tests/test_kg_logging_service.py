"""Tests for KG Structured Logging Service."""

import pytest
import json
import os
import tempfile
import time

from app.services.kg_logging_service import (
    LogLevel,
    LogCategory,
    LogEntry,
    JSONFormatter,
    TextFormatter,
    StreamHandler,
    FileHandler,
    MemoryHandler,
    KGLogger,
    LogContext,
    TimedLogContext,
    get_correlation_id,
    set_correlation_id,
    generate_correlation_id,
    get_request_context,
    set_request_context,
    update_request_context,
    with_correlation_id,
    get_logger,
    reset_logger,
    configure_logger,
)


class TestLogLevel:
    """Tests for LogLevel enum."""

    def test_log_levels(self):
        """Verify log levels."""
        assert LogLevel.DEBUG.value == "DEBUG"
        assert LogLevel.INFO.value == "INFO"
        assert LogLevel.WARNING.value == "WARNING"
        assert LogLevel.ERROR.value == "ERROR"
        assert LogLevel.CRITICAL.value == "CRITICAL"


class TestLogCategory:
    """Tests for LogCategory enum."""

    def test_log_categories(self):
        """Verify log categories."""
        assert LogCategory.REQUEST.value == "request"
        assert LogCategory.DATABASE.value == "database"
        assert LogCategory.SECURITY.value == "security"


class TestCorrelationId:
    """Tests for correlation ID management."""

    def test_generate_correlation_id(self):
        """Test correlation ID generation."""
        corr_id = generate_correlation_id()
        assert corr_id.startswith("corr_")
        assert len(corr_id) == 21  # corr_ + 16 hex chars

    def test_set_and_get_correlation_id(self):
        """Test setting and getting correlation ID."""
        set_correlation_id("test_corr_123")
        assert get_correlation_id() == "test_corr_123"
        set_correlation_id(None)  # Clean up

    def test_with_correlation_id_decorator(self):
        """Test correlation ID decorator."""
        @with_correlation_id
        def test_func():
            return get_correlation_id()

        result = test_func()
        assert result is not None
        assert result.startswith("corr_")


class TestRequestContext:
    """Tests for request context management."""

    def test_set_and_get_context(self):
        """Test setting and getting request context."""
        context = {"user_id": "user123", "endpoint": "/api/test"}
        set_request_context(context)
        assert get_request_context() == context
        set_request_context({})  # Clean up

    def test_update_context(self):
        """Test updating request context."""
        set_request_context({"user_id": "user123"})
        update_request_context(endpoint="/api/test")
        context = get_request_context()
        assert context["user_id"] == "user123"
        assert context["endpoint"] == "/api/test"
        set_request_context({})  # Clean up


class TestLogEntry:
    """Tests for LogEntry dataclass."""

    def test_create_entry(self):
        """Test log entry creation."""
        entry = LogEntry(
            timestamp="2024-01-15T10:30:00Z",
            level=LogLevel.INFO,
            message="Test message",
            correlation_id="corr_123",
            category=LogCategory.REQUEST,
        )
        assert entry.level == LogLevel.INFO
        assert entry.message == "Test message"

    def test_to_dict(self):
        """Test conversion to dictionary."""
        entry = LogEntry(
            timestamp="2024-01-15T10:30:00Z",
            level=LogLevel.INFO,
            message="Test message",
        )
        result = entry.to_dict()
        assert result["level"] == "INFO"
        assert result["message"] == "Test message"
        assert "correlation_id" not in result  # None values excluded

    def test_to_json(self):
        """Test conversion to JSON."""
        entry = LogEntry(
            timestamp="2024-01-15T10:30:00Z",
            level=LogLevel.INFO,
            message="Test message",
        )
        result = entry.to_json()
        parsed = json.loads(result)
        assert parsed["level"] == "INFO"


class TestJSONFormatter:
    """Tests for JSONFormatter."""

    def test_format(self):
        """Test JSON formatting."""
        formatter = JSONFormatter()
        entry = LogEntry(
            timestamp="2024-01-15T10:30:00Z",
            level=LogLevel.INFO,
            message="Test",
        )
        result = formatter.format(entry)
        parsed = json.loads(result)
        assert parsed["level"] == "INFO"

    def test_format_pretty(self):
        """Test pretty JSON formatting."""
        formatter = JSONFormatter(pretty=True)
        entry = LogEntry(
            timestamp="2024-01-15T10:30:00Z",
            level=LogLevel.INFO,
            message="Test",
        )
        result = formatter.format(entry)
        assert "\n" in result  # Pretty printed has newlines


class TestTextFormatter:
    """Tests for TextFormatter."""

    def test_format_basic(self):
        """Test basic text formatting."""
        formatter = TextFormatter()
        entry = LogEntry(
            timestamp="2024-01-15T10:30:00Z",
            level=LogLevel.INFO,
            message="Test message",
        )
        result = formatter.format(entry)
        assert "[INFO]" in result
        assert "Test message" in result

    def test_format_with_correlation(self):
        """Test formatting with correlation ID."""
        formatter = TextFormatter(include_correlation=True)
        entry = LogEntry(
            timestamp="2024-01-15T10:30:00Z",
            level=LogLevel.INFO,
            message="Test",
            correlation_id="corr_123",
        )
        result = formatter.format(entry)
        assert "[corr_123]" in result

    def test_format_with_duration(self):
        """Test formatting with duration."""
        formatter = TextFormatter()
        entry = LogEntry(
            timestamp="2024-01-15T10:30:00Z",
            level=LogLevel.INFO,
            message="Test",
            duration_ms=150.5,
        )
        result = formatter.format(entry)
        assert "150.50ms" in result

    def test_format_with_category(self):
        """Test formatting with category."""
        formatter = TextFormatter()
        entry = LogEntry(
            timestamp="2024-01-15T10:30:00Z",
            level=LogLevel.INFO,
            message="Test",
            category=LogCategory.DATABASE,
        )
        result = formatter.format(entry)
        assert "[database]" in result


class TestMemoryHandler:
    """Tests for MemoryHandler."""

    def test_emit(self):
        """Test emitting to memory."""
        handler = MemoryHandler()
        entry = LogEntry(
            timestamp="2024-01-15T10:30:00Z",
            level=LogLevel.INFO,
            message="Test",
        )
        handler.emit(entry)
        entries = handler.get_entries()
        assert len(entries) == 1

    def test_level_filtering(self):
        """Test level filtering."""
        handler = MemoryHandler(min_level=LogLevel.WARNING)
        info_entry = LogEntry(
            timestamp="2024-01-15T10:30:00Z",
            level=LogLevel.INFO,
            message="Info",
        )
        warning_entry = LogEntry(
            timestamp="2024-01-15T10:30:01Z",
            level=LogLevel.WARNING,
            message="Warning",
        )
        handler.emit(info_entry)
        handler.emit(warning_entry)
        entries = handler.get_entries()
        assert len(entries) == 1
        assert entries[0].level == LogLevel.WARNING

    def test_category_filtering(self):
        """Test category filtering."""
        handler = MemoryHandler(categories=[LogCategory.DATABASE])
        db_entry = LogEntry(
            timestamp="2024-01-15T10:30:00Z",
            level=LogLevel.INFO,
            message="DB",
            category=LogCategory.DATABASE,
        )
        api_entry = LogEntry(
            timestamp="2024-01-15T10:30:01Z",
            level=LogLevel.INFO,
            message="API",
            category=LogCategory.API,
        )
        handler.emit(db_entry)
        handler.emit(api_entry)
        entries = handler.get_entries()
        assert len(entries) == 1
        assert entries[0].category == LogCategory.DATABASE

    def test_max_entries(self):
        """Test max entries limit."""
        handler = MemoryHandler(max_entries=5)
        for i in range(10):
            entry = LogEntry(
                timestamp=f"2024-01-15T10:30:{i:02d}Z",
                level=LogLevel.INFO,
                message=f"Message {i}",
            )
            handler.emit(entry)
        entries = handler.get_entries()
        assert len(entries) == 5

    def test_get_entries_with_filters(self):
        """Test getting entries with filters."""
        handler = MemoryHandler()
        for level in [LogLevel.INFO, LogLevel.WARNING, LogLevel.ERROR]:
            entry = LogEntry(
                timestamp="2024-01-15T10:30:00Z",
                level=level,
                message=f"{level.value} message",
            )
            handler.emit(entry)

        error_entries = handler.get_entries(level=LogLevel.ERROR)
        assert len(error_entries) == 1

    def test_get_entries_by_correlation_id(self):
        """Test filtering by correlation ID."""
        handler = MemoryHandler()
        handler.emit(LogEntry(
            timestamp="2024-01-15T10:30:00Z",
            level=LogLevel.INFO,
            message="Message 1",
            correlation_id="corr_1",
        ))
        handler.emit(LogEntry(
            timestamp="2024-01-15T10:30:01Z",
            level=LogLevel.INFO,
            message="Message 2",
            correlation_id="corr_2",
        ))

        entries = handler.get_entries(correlation_id="corr_1")
        assert len(entries) == 1
        assert entries[0].correlation_id == "corr_1"

    def test_clear(self):
        """Test clearing entries."""
        handler = MemoryHandler()
        handler.emit(LogEntry(
            timestamp="2024-01-15T10:30:00Z",
            level=LogLevel.INFO,
            message="Test",
        ))
        handler.clear()
        assert len(handler.get_entries()) == 0


class TestFileHandler:
    """Tests for FileHandler."""

    def test_emit_to_file(self):
        """Test emitting to file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            filepath = f.name

        try:
            handler = FileHandler(filepath)
            entry = LogEntry(
                timestamp="2024-01-15T10:30:00Z",
                level=LogLevel.INFO,
                message="Test message",
            )
            handler.emit(entry)

            with open(filepath) as f:
                content = f.read()
                assert "Test message" in content
        finally:
            os.unlink(filepath)

    def test_creates_directory(self):
        """Test that handler creates directory if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "subdir", "test.log")
            handler = FileHandler(filepath)
            entry = LogEntry(
                timestamp="2024-01-15T10:30:00Z",
                level=LogLevel.INFO,
                message="Test",
            )
            handler.emit(entry)
            assert os.path.exists(filepath)


class TestKGLogger:
    """Tests for KGLogger."""

    @pytest.fixture
    def logger(self):
        """Create a logger with memory handler for testing."""
        logger = KGLogger(name="test", service="test-service")
        handler = MemoryHandler()
        logger.add_handler(handler)
        return logger, handler

    def test_log_info(self, logger):
        """Test info logging."""
        log, handler = logger
        log.info("Test message")
        entries = handler.get_entries()
        assert len(entries) == 1
        assert entries[0].level == LogLevel.INFO

    def test_log_debug(self, logger):
        """Test debug logging."""
        log, handler = logger
        log.debug("Debug message")
        entries = handler.get_entries()
        assert len(entries) == 1
        assert entries[0].level == LogLevel.DEBUG

    def test_log_warning(self, logger):
        """Test warning logging."""
        log, handler = logger
        log.warning("Warning message")
        entries = handler.get_entries()
        assert entries[0].level == LogLevel.WARNING

    def test_log_error(self, logger):
        """Test error logging."""
        log, handler = logger
        log.error("Error message")
        entries = handler.get_entries()
        assert entries[0].level == LogLevel.ERROR

    def test_log_critical(self, logger):
        """Test critical logging."""
        log, handler = logger
        log.critical("Critical message")
        entries = handler.get_entries()
        assert entries[0].level == LogLevel.CRITICAL

    def test_log_with_category(self, logger):
        """Test logging with category."""
        log, handler = logger
        log.info("Database query", category=LogCategory.DATABASE)
        entries = handler.get_entries()
        assert entries[0].category == LogCategory.DATABASE

    def test_log_with_extra(self, logger):
        """Test logging with extra fields."""
        log, handler = logger
        log.info("Test", query="SELECT *", rows=100)
        entries = handler.get_entries()
        assert entries[0].extra["query"] == "SELECT *"
        assert entries[0].extra["rows"] == 100

    def test_log_with_error(self, logger):
        """Test logging with exception."""
        log, handler = logger
        try:
            raise ValueError("Test error")
        except ValueError as e:
            log.error("An error occurred", error=e)

        entries = handler.get_entries()
        assert entries[0].error_type == "ValueError"
        assert entries[0].error_message == "Test error"
        assert entries[0].stack_trace is not None

    def test_log_with_duration(self, logger):
        """Test logging with duration."""
        log, handler = logger
        log.log(LogLevel.INFO, "Completed", duration_ms=150.5)
        entries = handler.get_entries()
        assert entries[0].duration_ms == 150.5

    def test_log_request(self, logger):
        """Test request logging convenience method."""
        log, handler = logger
        log.log_request("GET", "/api/test")
        entries = handler.get_entries()
        assert entries[0].category == LogCategory.REQUEST
        assert "GET /api/test" in entries[0].message

    def test_log_response(self, logger):
        """Test response logging convenience method."""
        log, handler = logger
        log.log_response("GET", "/api/test", 200, 50.0)
        entries = handler.get_entries()
        assert entries[0].category == LogCategory.RESPONSE
        assert "200" in entries[0].message

    def test_log_database_query(self, logger):
        """Test database query logging."""
        log, handler = logger
        log.log_database_query("SELECT", 25.5, success=True)
        entries = handler.get_entries()
        assert entries[0].category == LogCategory.DATABASE

    def test_log_cache_operation(self, logger):
        """Test cache operation logging."""
        log, handler = logger
        log.log_cache_operation("get", hit=True)
        entries = handler.get_entries()
        assert entries[0].category == LogCategory.CACHE
        assert "hit" in entries[0].message

    def test_log_security_event(self, logger):
        """Test security event logging."""
        log, handler = logger
        log.log_security_event("Login attempt", success=True)
        entries = handler.get_entries()
        assert entries[0].category == LogCategory.SECURITY

    def test_includes_correlation_id(self, logger):
        """Test that correlation ID is included."""
        log, handler = logger
        set_correlation_id("test_corr")
        log.info("Test message")
        entries = handler.get_entries()
        assert entries[0].correlation_id == "test_corr"
        set_correlation_id(None)  # Clean up

    def test_includes_request_context(self, logger):
        """Test that request context is included."""
        log, handler = logger
        set_request_context({
            "user_id": "user123",
            "endpoint": "/api/test",
        })
        log.info("Test message")
        entries = handler.get_entries()
        assert entries[0].user_id == "user123"
        assert entries[0].endpoint == "/api/test"
        set_request_context({})  # Clean up

    def test_remove_handler(self, logger):
        """Test removing a handler."""
        log, handler = logger
        log.remove_handler(handler)
        log.info("Test message")
        # Handler removed, so no entries
        assert len(handler.get_entries()) == 0


class TestLogContext:
    """Tests for LogContext context manager."""

    def test_sets_correlation_id(self):
        """Test that LogContext sets correlation ID."""
        with LogContext(correlation_id="ctx_123"):
            assert get_correlation_id() == "ctx_123"
        assert get_correlation_id() is None

    def test_generates_correlation_id(self):
        """Test that LogContext generates ID if not provided."""
        with LogContext():
            corr_id = get_correlation_id()
            assert corr_id is not None
            assert corr_id.startswith("corr_")

    def test_sets_context(self):
        """Test that LogContext sets request context."""
        with LogContext(user_id="user123"):
            ctx = get_request_context()
            assert ctx["user_id"] == "user123"

    def test_restores_previous_state(self):
        """Test that LogContext restores previous state."""
        set_correlation_id("original")
        set_request_context({"key": "value"})

        with LogContext(correlation_id="new"):
            pass

        assert get_correlation_id() == "original"
        assert get_request_context()["key"] == "value"

        set_correlation_id(None)
        set_request_context({})


class TestTimedLogContext:
    """Tests for TimedLogContext context manager."""

    def test_logs_duration(self):
        """Test that TimedLogContext logs duration."""
        logger = KGLogger()
        handler = MemoryHandler()
        logger.add_handler(handler)

        with TimedLogContext(logger, "Operation"):
            time.sleep(0.01)

        entries = handler.get_entries()
        assert len(entries) == 1
        assert "completed" in entries[0].message
        assert entries[0].duration_ms > 0

    def test_logs_error_on_exception(self):
        """Test that TimedLogContext logs errors."""
        logger = KGLogger()
        handler = MemoryHandler()
        logger.add_handler(handler)

        with pytest.raises(ValueError):
            with TimedLogContext(logger, "Operation"):
                raise ValueError("Test error")

        entries = handler.get_entries()
        assert entries[0].level == LogLevel.ERROR
        assert "failed" in entries[0].message


class TestSingleton:
    """Tests for singleton logger."""

    def test_get_logger_returns_same_instance(self):
        """Test singleton returns same instance."""
        reset_logger()
        l1 = get_logger()
        l2 = get_logger()
        assert l1 is l2
        reset_logger()

    def test_configure_logger(self):
        """Test logger configuration."""
        reset_logger()
        logger = configure_logger(
            name="custom",
            service="custom-service",
            console_level=LogLevel.WARNING,
        )
        assert logger.name == "custom"
        assert logger.service == "custom-service"
        reset_logger()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
