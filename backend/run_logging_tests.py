#!/usr/bin/env python3
"""Standalone test runner for KG Logging Service tests."""

import sys
import os
import importlib.util
import traceback
import json
import tempfile
import time

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Create comprehensive mocks for dependencies
class MockModule:
    def __getattr__(self, name):
        return MockModule()
    def __call__(self, *args, **kwargs):
        return MockModule()

# Mock the problematic modules before any imports
sys.modules["sentence_transformers"] = MockModule()
sys.modules["sentence_transformers"].SentenceTransformer = MockModule()
sys.modules["neo4j"] = MockModule()
sys.modules["neo4j"].GraphDatabase = MockModule()

# Load the module directly
spec = importlib.util.spec_from_file_location(
    "app.services.kg_logging_service",
    "app/services/kg_logging_service.py",
    submodule_search_locations=[]
)
logging_module = importlib.util.module_from_spec(spec)
logging_module.__package__ = "app.services"
sys.modules["app.services.kg_logging_service"] = logging_module
spec.loader.exec_module(logging_module)

# Import the module under test
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


def run_test(name, test_func):
    """Run a single test."""
    try:
        test_func()
        print(f"  ✓ {name}")
        return True
    except AssertionError as e:
        print(f"  ✗ {name}: {e}")
        return False
    except Exception as e:
        print(f"  ✗ {name}: {type(e).__name__}: {e}")
        traceback.print_exc()
        return False


# LogLevel tests
def test_log_levels():
    assert LogLevel.DEBUG.value == "DEBUG"
    assert LogLevel.INFO.value == "INFO"
    assert LogLevel.WARNING.value == "WARNING"
    assert LogLevel.ERROR.value == "ERROR"
    assert LogLevel.CRITICAL.value == "CRITICAL"


def test_log_categories():
    assert LogCategory.REQUEST.value == "request"
    assert LogCategory.DATABASE.value == "database"
    assert LogCategory.SECURITY.value == "security"


# Correlation ID tests
def test_generate_correlation_id():
    corr_id = generate_correlation_id()
    assert corr_id.startswith("corr_")
    assert len(corr_id) == 21


def test_set_and_get_correlation_id():
    set_correlation_id("test_corr_123")
    assert get_correlation_id() == "test_corr_123"
    set_correlation_id(None)


def test_with_correlation_id_decorator():
    @with_correlation_id
    def test_func():
        return get_correlation_id()

    result = test_func()
    assert result is not None
    assert result.startswith("corr_")


# Request context tests
def test_set_and_get_context():
    context = {"user_id": "user123", "endpoint": "/api/test"}
    set_request_context(context)
    assert get_request_context() == context
    set_request_context({})


def test_update_context():
    set_request_context({"user_id": "user123"})
    update_request_context(endpoint="/api/test")
    context = get_request_context()
    assert context["user_id"] == "user123"
    assert context["endpoint"] == "/api/test"
    set_request_context({})


# LogEntry tests
def test_create_entry():
    entry = LogEntry(
        timestamp="2024-01-15T10:30:00Z",
        level=LogLevel.INFO,
        message="Test message",
        correlation_id="corr_123",
        category=LogCategory.REQUEST,
    )
    assert entry.level == LogLevel.INFO
    assert entry.message == "Test message"


def test_entry_to_dict():
    entry = LogEntry(
        timestamp="2024-01-15T10:30:00Z",
        level=LogLevel.INFO,
        message="Test message",
    )
    result = entry.to_dict()
    assert result["level"] == "INFO"
    assert result["message"] == "Test message"
    assert "correlation_id" not in result


def test_entry_to_json():
    entry = LogEntry(
        timestamp="2024-01-15T10:30:00Z",
        level=LogLevel.INFO,
        message="Test message",
    )
    result = entry.to_json()
    parsed = json.loads(result)
    assert parsed["level"] == "INFO"


# Formatter tests
def test_json_formatter():
    formatter = JSONFormatter()
    entry = LogEntry(
        timestamp="2024-01-15T10:30:00Z",
        level=LogLevel.INFO,
        message="Test",
    )
    result = formatter.format(entry)
    parsed = json.loads(result)
    assert parsed["level"] == "INFO"


def test_json_formatter_pretty():
    formatter = JSONFormatter(pretty=True)
    entry = LogEntry(
        timestamp="2024-01-15T10:30:00Z",
        level=LogLevel.INFO,
        message="Test",
    )
    result = formatter.format(entry)
    assert "\n" in result


def test_text_formatter_basic():
    formatter = TextFormatter()
    entry = LogEntry(
        timestamp="2024-01-15T10:30:00Z",
        level=LogLevel.INFO,
        message="Test message",
    )
    result = formatter.format(entry)
    assert "[INFO]" in result
    assert "Test message" in result


def test_text_formatter_with_correlation():
    formatter = TextFormatter(include_correlation=True)
    entry = LogEntry(
        timestamp="2024-01-15T10:30:00Z",
        level=LogLevel.INFO,
        message="Test",
        correlation_id="corr_123",
    )
    result = formatter.format(entry)
    assert "[corr_123]" in result


def test_text_formatter_with_duration():
    formatter = TextFormatter()
    entry = LogEntry(
        timestamp="2024-01-15T10:30:00Z",
        level=LogLevel.INFO,
        message="Test",
        duration_ms=150.5,
    )
    result = formatter.format(entry)
    assert "150.50ms" in result


def test_text_formatter_with_category():
    formatter = TextFormatter()
    entry = LogEntry(
        timestamp="2024-01-15T10:30:00Z",
        level=LogLevel.INFO,
        message="Test",
        category=LogCategory.DATABASE,
    )
    result = formatter.format(entry)
    assert "[database]" in result


# MemoryHandler tests
def test_memory_handler_emit():
    handler = MemoryHandler()
    entry = LogEntry(
        timestamp="2024-01-15T10:30:00Z",
        level=LogLevel.INFO,
        message="Test",
    )
    handler.emit(entry)
    entries = handler.get_entries()
    assert len(entries) == 1


def test_memory_handler_level_filtering():
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


def test_memory_handler_category_filtering():
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


def test_memory_handler_max_entries():
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


def test_memory_handler_filter_by_level():
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


def test_memory_handler_filter_by_correlation():
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


def test_memory_handler_clear():
    handler = MemoryHandler()
    handler.emit(LogEntry(
        timestamp="2024-01-15T10:30:00Z",
        level=LogLevel.INFO,
        message="Test",
    ))
    handler.clear()
    assert len(handler.get_entries()) == 0


# FileHandler tests
def test_file_handler_emit():
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


def test_file_handler_creates_directory():
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


# KGLogger tests
def test_logger_info():
    logger = KGLogger(name="test", service="test-service")
    handler = MemoryHandler()
    logger.add_handler(handler)
    logger.info("Test message")
    entries = handler.get_entries()
    assert len(entries) == 1
    assert entries[0].level == LogLevel.INFO


def test_logger_debug():
    logger = KGLogger()
    handler = MemoryHandler()
    logger.add_handler(handler)
    logger.debug("Debug message")
    entries = handler.get_entries()
    assert entries[0].level == LogLevel.DEBUG


def test_logger_warning():
    logger = KGLogger()
    handler = MemoryHandler()
    logger.add_handler(handler)
    logger.warning("Warning message")
    entries = handler.get_entries()
    assert entries[0].level == LogLevel.WARNING


def test_logger_error():
    logger = KGLogger()
    handler = MemoryHandler()
    logger.add_handler(handler)
    logger.error("Error message")
    entries = handler.get_entries()
    assert entries[0].level == LogLevel.ERROR


def test_logger_critical():
    logger = KGLogger()
    handler = MemoryHandler()
    logger.add_handler(handler)
    logger.critical("Critical message")
    entries = handler.get_entries()
    assert entries[0].level == LogLevel.CRITICAL


def test_logger_with_category():
    logger = KGLogger()
    handler = MemoryHandler()
    logger.add_handler(handler)
    logger.info("Database query", category=LogCategory.DATABASE)
    entries = handler.get_entries()
    assert entries[0].category == LogCategory.DATABASE


def test_logger_with_extra():
    logger = KGLogger()
    handler = MemoryHandler()
    logger.add_handler(handler)
    logger.info("Test", query="SELECT *", rows=100)
    entries = handler.get_entries()
    assert entries[0].extra["query"] == "SELECT *"
    assert entries[0].extra["rows"] == 100


def test_logger_with_error():
    logger = KGLogger()
    handler = MemoryHandler()
    logger.add_handler(handler)
    try:
        raise ValueError("Test error")
    except ValueError as e:
        logger.error("An error occurred", error=e)
    entries = handler.get_entries()
    assert entries[0].error_type == "ValueError"
    assert entries[0].error_message == "Test error"
    assert entries[0].stack_trace is not None


def test_logger_with_duration():
    logger = KGLogger()
    handler = MemoryHandler()
    logger.add_handler(handler)
    logger.log(LogLevel.INFO, "Completed", duration_ms=150.5)
    entries = handler.get_entries()
    assert entries[0].duration_ms == 150.5


def test_logger_log_request():
    logger = KGLogger()
    handler = MemoryHandler()
    logger.add_handler(handler)
    logger.log_request("GET", "/api/test")
    entries = handler.get_entries()
    assert entries[0].category == LogCategory.REQUEST
    assert "GET /api/test" in entries[0].message


def test_logger_log_response():
    logger = KGLogger()
    handler = MemoryHandler()
    logger.add_handler(handler)
    logger.log_response("GET", "/api/test", 200, 50.0)
    entries = handler.get_entries()
    assert entries[0].category == LogCategory.RESPONSE
    assert "200" in entries[0].message


def test_logger_log_database_query():
    logger = KGLogger()
    handler = MemoryHandler()
    logger.add_handler(handler)
    logger.log_database_query("SELECT", 25.5, success=True)
    entries = handler.get_entries()
    assert entries[0].category == LogCategory.DATABASE


def test_logger_log_cache_operation():
    logger = KGLogger()
    handler = MemoryHandler()
    logger.add_handler(handler)
    logger.log_cache_operation("get", hit=True)
    entries = handler.get_entries()
    assert entries[0].category == LogCategory.CACHE
    assert "hit" in entries[0].message


def test_logger_log_security_event():
    logger = KGLogger()
    handler = MemoryHandler()
    logger.add_handler(handler)
    logger.log_security_event("Login attempt", success=True)
    entries = handler.get_entries()
    assert entries[0].category == LogCategory.SECURITY


def test_logger_includes_correlation_id():
    logger = KGLogger()
    handler = MemoryHandler()
    logger.add_handler(handler)
    set_correlation_id("test_corr")
    logger.info("Test message")
    entries = handler.get_entries()
    assert entries[0].correlation_id == "test_corr"
    set_correlation_id(None)


def test_logger_includes_request_context():
    logger = KGLogger()
    handler = MemoryHandler()
    logger.add_handler(handler)
    set_request_context({"user_id": "user123", "endpoint": "/api/test"})
    logger.info("Test message")
    entries = handler.get_entries()
    assert entries[0].user_id == "user123"
    assert entries[0].endpoint == "/api/test"
    set_request_context({})


def test_logger_remove_handler():
    logger = KGLogger()
    handler = MemoryHandler()
    logger.add_handler(handler)
    logger.remove_handler(handler)
    logger.info("Test message")
    assert len(handler.get_entries()) == 0


# LogContext tests
def test_log_context_sets_correlation_id():
    with LogContext(correlation_id="ctx_123"):
        assert get_correlation_id() == "ctx_123"
    assert get_correlation_id() is None


def test_log_context_generates_id():
    with LogContext():
        corr_id = get_correlation_id()
        assert corr_id is not None
        assert corr_id.startswith("corr_")


def test_log_context_sets_context():
    with LogContext(user_id="user123"):
        ctx = get_request_context()
        assert ctx["user_id"] == "user123"


def test_log_context_restores_state():
    set_correlation_id("original")
    set_request_context({"key": "value"})
    with LogContext(correlation_id="new"):
        pass
    assert get_correlation_id() == "original"
    assert get_request_context()["key"] == "value"
    set_correlation_id(None)
    set_request_context({})


# TimedLogContext tests
def test_timed_context_logs_duration():
    logger = KGLogger()
    handler = MemoryHandler()
    logger.add_handler(handler)
    with TimedLogContext(logger, "Operation"):
        time.sleep(0.01)
    entries = handler.get_entries()
    assert len(entries) == 1
    assert "completed" in entries[0].message
    assert entries[0].duration_ms > 0


def test_timed_context_logs_error():
    logger = KGLogger()
    handler = MemoryHandler()
    logger.add_handler(handler)
    try:
        with TimedLogContext(logger, "Operation"):
            raise ValueError("Test error")
    except ValueError:
        pass
    entries = handler.get_entries()
    assert entries[0].level == LogLevel.ERROR
    assert "failed" in entries[0].message


# Singleton tests
def test_get_logger_singleton():
    reset_logger()
    l1 = get_logger()
    l2 = get_logger()
    assert l1 is l2
    reset_logger()


def test_configure_logger():
    reset_logger()
    logger = configure_logger(
        name="custom",
        service="custom-service",
        console_level=LogLevel.WARNING,
    )
    assert logger.name == "custom"
    assert logger.service == "custom-service"
    reset_logger()


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("KG Logging Service Tests")
    print("=" * 60 + "\n")

    tests = [
        # LogLevel and LogCategory tests
        ("log_levels", test_log_levels),
        ("log_categories", test_log_categories),

        # Correlation ID tests
        ("generate_correlation_id", test_generate_correlation_id),
        ("set_and_get_correlation_id", test_set_and_get_correlation_id),
        ("with_correlation_id_decorator", test_with_correlation_id_decorator),

        # Request context tests
        ("set_and_get_context", test_set_and_get_context),
        ("update_context", test_update_context),

        # LogEntry tests
        ("create_entry", test_create_entry),
        ("entry_to_dict", test_entry_to_dict),
        ("entry_to_json", test_entry_to_json),

        # Formatter tests
        ("json_formatter", test_json_formatter),
        ("json_formatter_pretty", test_json_formatter_pretty),
        ("text_formatter_basic", test_text_formatter_basic),
        ("text_formatter_with_correlation", test_text_formatter_with_correlation),
        ("text_formatter_with_duration", test_text_formatter_with_duration),
        ("text_formatter_with_category", test_text_formatter_with_category),

        # MemoryHandler tests
        ("memory_handler_emit", test_memory_handler_emit),
        ("memory_handler_level_filtering", test_memory_handler_level_filtering),
        ("memory_handler_category_filtering", test_memory_handler_category_filtering),
        ("memory_handler_max_entries", test_memory_handler_max_entries),
        ("memory_handler_filter_by_level", test_memory_handler_filter_by_level),
        ("memory_handler_filter_by_correlation", test_memory_handler_filter_by_correlation),
        ("memory_handler_clear", test_memory_handler_clear),

        # FileHandler tests
        ("file_handler_emit", test_file_handler_emit),
        ("file_handler_creates_directory", test_file_handler_creates_directory),

        # KGLogger tests
        ("logger_info", test_logger_info),
        ("logger_debug", test_logger_debug),
        ("logger_warning", test_logger_warning),
        ("logger_error", test_logger_error),
        ("logger_critical", test_logger_critical),
        ("logger_with_category", test_logger_with_category),
        ("logger_with_extra", test_logger_with_extra),
        ("logger_with_error", test_logger_with_error),
        ("logger_with_duration", test_logger_with_duration),
        ("logger_log_request", test_logger_log_request),
        ("logger_log_response", test_logger_log_response),
        ("logger_log_database_query", test_logger_log_database_query),
        ("logger_log_cache_operation", test_logger_log_cache_operation),
        ("logger_log_security_event", test_logger_log_security_event),
        ("logger_includes_correlation_id", test_logger_includes_correlation_id),
        ("logger_includes_request_context", test_logger_includes_request_context),
        ("logger_remove_handler", test_logger_remove_handler),

        # LogContext tests
        ("log_context_sets_correlation_id", test_log_context_sets_correlation_id),
        ("log_context_generates_id", test_log_context_generates_id),
        ("log_context_sets_context", test_log_context_sets_context),
        ("log_context_restores_state", test_log_context_restores_state),

        # TimedLogContext tests
        ("timed_context_logs_duration", test_timed_context_logs_duration),
        ("timed_context_logs_error", test_timed_context_logs_error),

        # Singleton tests
        ("get_logger_singleton", test_get_logger_singleton),
        ("configure_logger", test_configure_logger),
    ]

    passed = 0
    failed = 0

    for name, test in tests:
        if run_test(name, test):
            passed += 1
        else:
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
