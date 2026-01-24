#!/usr/bin/env python3
"""Standalone test runner for KG Configuration Service tests."""

import sys
import os
import importlib.util
import traceback
import json
import tempfile
import time
from datetime import datetime

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
    "app.services.kg_config_service",
    "app/services/kg_config_service.py",
    submodule_search_locations=[]
)
config_module = importlib.util.module_from_spec(spec)
config_module.__package__ = "app.services"
sys.modules["app.services.kg_config_service"] = config_module
spec.loader.exec_module(config_module)

# Import the module under test
from app.services.kg_config_service import (
    ConfigValueType,
    ConfigSchema,
    ConfigChange,
    ConfigVersion,
    KGConfigService,
    get_config_service,
    reset_config_service,
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


# ConfigSchema tests
def test_create_schema():
    schema = ConfigSchema(
        key="test.setting",
        value_type=ConfigValueType.STRING,
        default="default_value",
        description="A test setting",
    )
    assert schema.key == "test.setting"
    assert schema.default == "default_value"


def test_validate_string():
    schema = ConfigSchema(key="test", value_type=ConfigValueType.STRING)
    is_valid, error = schema.validate("hello")
    assert is_valid is True


def test_validate_integer():
    schema = ConfigSchema(key="test", value_type=ConfigValueType.INTEGER)
    is_valid, error = schema.validate(42)
    assert is_valid is True


def test_validate_integer_wrong_type():
    schema = ConfigSchema(key="test", value_type=ConfigValueType.INTEGER)
    is_valid, error = schema.validate("not an int")
    assert is_valid is False
    assert "expected integer" in error


def test_validate_float():
    schema = ConfigSchema(key="test", value_type=ConfigValueType.FLOAT)
    is_valid, error = schema.validate(3.14)
    assert is_valid is True


def test_validate_boolean():
    schema = ConfigSchema(key="test", value_type=ConfigValueType.BOOLEAN)
    is_valid, error = schema.validate(True)
    assert is_valid is True


def test_validate_list():
    schema = ConfigSchema(key="test", value_type=ConfigValueType.LIST)
    is_valid, error = schema.validate([1, 2, 3])
    assert is_valid is True


def test_validate_dict():
    schema = ConfigSchema(key="test", value_type=ConfigValueType.DICT)
    is_valid, error = schema.validate({"key": "value"})
    assert is_valid is True


def test_validate_min_value():
    schema = ConfigSchema(key="test", value_type=ConfigValueType.INTEGER, min_value=10)
    is_valid, error = schema.validate(5)
    assert is_valid is False
    assert "below minimum" in error


def test_validate_max_value():
    schema = ConfigSchema(key="test", value_type=ConfigValueType.INTEGER, max_value=100)
    is_valid, error = schema.validate(150)
    assert is_valid is False
    assert "above maximum" in error


def test_validate_allowed_values():
    schema = ConfigSchema(key="test", value_type=ConfigValueType.STRING, allowed_values=["a", "b", "c"])
    is_valid, error = schema.validate("d")
    assert is_valid is False
    assert "not in allowed values" in error


def test_validate_required():
    schema = ConfigSchema(key="test", value_type=ConfigValueType.STRING, required=True)
    is_valid, error = schema.validate(None)
    assert is_valid is False
    assert "Required" in error


# ConfigChange tests
def test_create_change():
    change = ConfigChange(
        key="test.setting",
        old_value="old",
        new_value="new",
        timestamp=datetime.utcnow(),
        source="api",
    )
    assert change.key == "test.setting"
    assert change.old_value == "old"


def test_change_to_dict():
    change = ConfigChange(
        key="test",
        old_value=1,
        new_value=2,
        timestamp=datetime.utcnow(),
        source="file",
        user="admin",
    )
    result = change.to_dict()
    assert result["key"] == "test"
    assert result["source"] == "file"


# ConfigVersion tests
def test_compute_hash():
    config = {"a": 1, "b": 2}
    hash1 = ConfigVersion.compute_hash(config)
    hash2 = ConfigVersion.compute_hash(config)
    assert hash1 == hash2
    assert len(hash1) == 16


def test_different_configs_different_hash():
    config1 = {"a": 1}
    config2 = {"a": 2}
    hash1 = ConfigVersion.compute_hash(config1)
    hash2 = ConfigVersion.compute_hash(config2)
    assert hash1 != hash2


# KGConfigService tests
def test_get_default_value():
    service = KGConfigService()
    value = service.get("neo4j.uri")
    assert value == "bolt://localhost:7687"


def test_get_unknown_key():
    service = KGConfigService()
    value = service.get("unknown.key", default="fallback")
    assert value == "fallback"


def test_get_all():
    service = KGConfigService()
    config = service.get_all()
    assert "neo4j.uri" in config
    assert "cache.enabled" in config


def test_set_value():
    service = KGConfigService()
    success, error = service.set("cache.ttl_seconds", 7200)
    assert success is True
    assert service.get("cache.ttl_seconds") == 7200


def test_set_invalid_value():
    service = KGConfigService()
    success, error = service.set("cache.ttl_seconds", -100)
    assert success is False
    assert "below minimum" in error


def test_set_many():
    service = KGConfigService()
    success, errors = service.set_many({
        "cache.ttl_seconds": 1800,
        "reasoning.max_hops": 3,
    })
    assert success is True
    assert service.get("cache.ttl_seconds") == 1800
    assert service.get("reasoning.max_hops") == 3


def test_set_many_with_errors():
    service = KGConfigService()
    success, errors = service.set_many({
        "cache.ttl_seconds": 1800,
        "reasoning.max_hops": 100,  # Invalid: max is 10
    })
    assert success is False
    assert "reasoning.max_hops" in errors


def test_non_hot_reloadable():
    service = KGConfigService()
    initial = service.get("neo4j.max_pool_size")
    success, error = service.set("neo4j.max_pool_size", 100)
    assert success is False
    assert "cannot be changed" in error


def test_add_listener():
    service = KGConfigService()
    changes = []

    def listener(key, old_val, new_val):
        changes.append((key, old_val, new_val))

    service.add_listener("cache.ttl_seconds", listener)
    service.set("cache.ttl_seconds", 1000)

    assert len(changes) == 1
    assert changes[0][0] == "cache.ttl_seconds"


def test_wildcard_listener():
    service = KGConfigService()
    changes = []

    def listener(key, old_val, new_val):
        changes.append(key)

    service.add_listener("cache.*", listener)
    service.set("cache.ttl_seconds", 1000)
    service.set("cache.max_size", 5000)

    assert len(changes) == 2


def test_remove_listener():
    service = KGConfigService()
    changes = []

    def listener(key, old_val, new_val):
        changes.append(key)

    service.add_listener("cache.ttl_seconds", listener)
    service.set("cache.ttl_seconds", 1000)
    service.remove_listener("cache.ttl_seconds", listener)
    service.set("cache.ttl_seconds", 2000)

    assert len(changes) == 1


def test_global_listener():
    service = KGConfigService()
    changes = []

    def listener(change):
        changes.append(change)

    service.add_global_listener(listener)
    service.set("cache.ttl_seconds", 1000)
    service.set("reasoning.max_hops", 3)

    assert len(changes) == 2


def test_get_changes():
    service = KGConfigService()
    service.set("cache.ttl_seconds", 1000)
    service.set("cache.ttl_seconds", 2000)

    changes = service.get_changes()
    assert len(changes) >= 2


def test_sensitive_value_masked():
    service = KGConfigService()
    service.set("neo4j.password", "secret123")
    changes = service.get_changes()

    password_change = next(c for c in changes if c.key == "neo4j.password")
    assert password_change.new_value == "***"


def test_register_custom_schema():
    service = KGConfigService()
    schema = ConfigSchema(
        key="custom.setting",
        value_type=ConfigValueType.INTEGER,
        default=42,
    )
    service.register_schema(schema)
    assert service.get_schema("custom.setting") is not None


def test_load_from_file():
    config_data = {
        "cache": {
            "ttl_seconds": 1800,
            "max_size": 5000,
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_data, f)
        filepath = f.name

    try:
        service = KGConfigService()
        success, error = service.load_from_file(filepath)
        assert success is True
        assert service.get("cache.ttl_seconds") == 1800
    finally:
        os.unlink(filepath)


def test_load_from_file_not_found():
    service = KGConfigService()
    success, error = service.load_from_file("/nonexistent/file.json")
    assert success is False
    assert "not found" in error


def test_load_from_file_invalid_json():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("not valid json")
        filepath = f.name

    try:
        service = KGConfigService()
        success, error = service.load_from_file(filepath)
        assert success is False
        assert "Invalid JSON" in error
    finally:
        os.unlink(filepath)


def test_export_config():
    service = KGConfigService()
    config = service.export_config()
    assert "neo4j.uri" in config
    assert config["neo4j.password"] == "***"


def test_export_config_include_sensitive():
    service = KGConfigService()
    config = service.export_config(include_sensitive=True)
    assert config["neo4j.password"] != "***"


def test_export_to_file():
    service = KGConfigService()
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        filepath = f.name

    try:
        success, error = service.export_to_file(filepath)
        assert success is True

        with open(filepath) as f:
            data = json.load(f)
            assert "neo4j" in data
    finally:
        os.unlink(filepath)


def test_version_created():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"cache": {"ttl_seconds": 1800}}, f)
        filepath = f.name

    try:
        service = KGConfigService()
        service.load_from_file(filepath)
        versions = service.get_versions()
        assert len(versions) >= 1
    finally:
        os.unlink(filepath)


def test_rollback():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"cache": {"ttl_seconds": 1800}}, f)
        filepath = f.name

    try:
        service = KGConfigService()
        service.load_from_file(filepath)
        v1 = service.get_versions()[0].version

        service.set("cache.ttl_seconds", 3600)
        assert service.get("cache.ttl_seconds") == 3600

        success, error = service.rollback(v1)
        assert success is True
        assert service.get("cache.ttl_seconds") == 1800
    finally:
        os.unlink(filepath)


def test_rollback_invalid_version():
    service = KGConfigService()
    success, error = service.rollback(99999)
    assert success is False
    assert "not found" in error


def test_validate_all():
    service = KGConfigService()
    errors = service.validate_all()
    assert len(errors) == 0


def test_env_override():
    os.environ["KG_CACHE_ENABLED"] = "false"
    try:
        service = KGConfigService()
        assert service.get("cache.enabled") is False
    finally:
        del os.environ["KG_CACHE_ENABLED"]


def test_watch_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"cache": {"ttl_seconds": 1800}}, f)
        filepath = f.name

    try:
        service = KGConfigService(config_file=filepath, watch_interval=0.1)
        service.start_watching()
        assert service.is_watching() is True

        time.sleep(0.2)
        service.stop_watching()
        assert service.is_watching() is False
    finally:
        os.unlink(filepath)


def test_singleton_returns_same_instance():
    reset_config_service()
    c1 = get_config_service()
    c2 = get_config_service()
    assert c1 is c2
    reset_config_service()


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("KG Configuration Service Tests")
    print("=" * 60 + "\n")

    tests = [
        # ConfigSchema tests
        ("create_schema", test_create_schema),
        ("validate_string", test_validate_string),
        ("validate_integer", test_validate_integer),
        ("validate_integer_wrong_type", test_validate_integer_wrong_type),
        ("validate_float", test_validate_float),
        ("validate_boolean", test_validate_boolean),
        ("validate_list", test_validate_list),
        ("validate_dict", test_validate_dict),
        ("validate_min_value", test_validate_min_value),
        ("validate_max_value", test_validate_max_value),
        ("validate_allowed_values", test_validate_allowed_values),
        ("validate_required", test_validate_required),

        # ConfigChange tests
        ("create_change", test_create_change),
        ("change_to_dict", test_change_to_dict),

        # ConfigVersion tests
        ("compute_hash", test_compute_hash),
        ("different_configs_different_hash", test_different_configs_different_hash),

        # KGConfigService tests
        ("get_default_value", test_get_default_value),
        ("get_unknown_key", test_get_unknown_key),
        ("get_all", test_get_all),
        ("set_value", test_set_value),
        ("set_invalid_value", test_set_invalid_value),
        ("set_many", test_set_many),
        ("set_many_with_errors", test_set_many_with_errors),
        ("non_hot_reloadable", test_non_hot_reloadable),
        ("add_listener", test_add_listener),
        ("wildcard_listener", test_wildcard_listener),
        ("remove_listener", test_remove_listener),
        ("global_listener", test_global_listener),
        ("get_changes", test_get_changes),
        ("sensitive_value_masked", test_sensitive_value_masked),
        ("register_custom_schema", test_register_custom_schema),
        ("load_from_file", test_load_from_file),
        ("load_from_file_not_found", test_load_from_file_not_found),
        ("load_from_file_invalid_json", test_load_from_file_invalid_json),
        ("export_config", test_export_config),
        ("export_config_include_sensitive", test_export_config_include_sensitive),
        ("export_to_file", test_export_to_file),
        ("version_created", test_version_created),
        ("rollback", test_rollback),
        ("rollback_invalid_version", test_rollback_invalid_version),
        ("validate_all", test_validate_all),
        ("env_override", test_env_override),
        ("watch_file", test_watch_file),
        ("singleton_returns_same_instance", test_singleton_returns_same_instance),
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
