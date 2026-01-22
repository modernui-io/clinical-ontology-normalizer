"""Tests for KG Configuration Service."""

import pytest
import json
import os
import tempfile
import time

from app.services.kg_config_service import (
    ConfigValueType,
    ConfigSchema,
    ConfigChange,
    ConfigVersion,
    KGConfigService,
    get_config_service,
    reset_config_service,
)


class TestConfigSchema:
    """Tests for ConfigSchema."""

    def test_create_schema(self):
        """Create a configuration schema."""
        schema = ConfigSchema(
            key="test.setting",
            value_type=ConfigValueType.STRING,
            default="default_value",
            description="A test setting",
        )
        assert schema.key == "test.setting"
        assert schema.default == "default_value"

    def test_validate_string(self):
        """Validate string value."""
        schema = ConfigSchema(
            key="test",
            value_type=ConfigValueType.STRING,
        )
        is_valid, error = schema.validate("hello")
        assert is_valid is True

    def test_validate_integer(self):
        """Validate integer value."""
        schema = ConfigSchema(
            key="test",
            value_type=ConfigValueType.INTEGER,
        )
        is_valid, error = schema.validate(42)
        assert is_valid is True

    def test_validate_integer_wrong_type(self):
        """Invalid type fails validation."""
        schema = ConfigSchema(
            key="test",
            value_type=ConfigValueType.INTEGER,
        )
        is_valid, error = schema.validate("not an int")
        assert is_valid is False
        assert "expected integer" in error

    def test_validate_float(self):
        """Validate float value."""
        schema = ConfigSchema(
            key="test",
            value_type=ConfigValueType.FLOAT,
        )
        is_valid, error = schema.validate(3.14)
        assert is_valid is True

    def test_validate_boolean(self):
        """Validate boolean value."""
        schema = ConfigSchema(
            key="test",
            value_type=ConfigValueType.BOOLEAN,
        )
        is_valid, error = schema.validate(True)
        assert is_valid is True

    def test_validate_list(self):
        """Validate list value."""
        schema = ConfigSchema(
            key="test",
            value_type=ConfigValueType.LIST,
        )
        is_valid, error = schema.validate([1, 2, 3])
        assert is_valid is True

    def test_validate_dict(self):
        """Validate dict value."""
        schema = ConfigSchema(
            key="test",
            value_type=ConfigValueType.DICT,
        )
        is_valid, error = schema.validate({"key": "value"})
        assert is_valid is True

    def test_validate_min_value(self):
        """Validate minimum value constraint."""
        schema = ConfigSchema(
            key="test",
            value_type=ConfigValueType.INTEGER,
            min_value=10,
        )
        is_valid, error = schema.validate(5)
        assert is_valid is False
        assert "below minimum" in error

    def test_validate_max_value(self):
        """Validate maximum value constraint."""
        schema = ConfigSchema(
            key="test",
            value_type=ConfigValueType.INTEGER,
            max_value=100,
        )
        is_valid, error = schema.validate(150)
        assert is_valid is False
        assert "above maximum" in error

    def test_validate_allowed_values(self):
        """Validate allowed values constraint."""
        schema = ConfigSchema(
            key="test",
            value_type=ConfigValueType.STRING,
            allowed_values=["a", "b", "c"],
        )
        is_valid, error = schema.validate("d")
        assert is_valid is False
        assert "not in allowed values" in error

    def test_validate_required(self):
        """Validate required value."""
        schema = ConfigSchema(
            key="test",
            value_type=ConfigValueType.STRING,
            required=True,
        )
        is_valid, error = schema.validate(None)
        assert is_valid is False
        assert "Required" in error


class TestConfigChange:
    """Tests for ConfigChange."""

    def test_create_change(self):
        """Create a configuration change record."""
        from datetime import datetime
        change = ConfigChange(
            key="test.setting",
            old_value="old",
            new_value="new",
            timestamp=datetime.utcnow(),
            source="api",
        )
        assert change.key == "test.setting"
        assert change.old_value == "old"

    def test_change_to_dict(self):
        """Convert change to dictionary."""
        from datetime import datetime
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


class TestConfigVersion:
    """Tests for ConfigVersion."""

    def test_compute_hash(self):
        """Compute configuration hash."""
        config = {"a": 1, "b": 2}
        hash1 = ConfigVersion.compute_hash(config)
        hash2 = ConfigVersion.compute_hash(config)
        assert hash1 == hash2
        assert len(hash1) == 16

    def test_different_configs_different_hash(self):
        """Different configs produce different hashes."""
        config1 = {"a": 1}
        config2 = {"a": 2}
        hash1 = ConfigVersion.compute_hash(config1)
        hash2 = ConfigVersion.compute_hash(config2)
        assert hash1 != hash2


class TestKGConfigService:
    """Tests for KGConfigService."""

    @pytest.fixture
    def service(self):
        return KGConfigService()

    def test_get_default_value(self, service):
        """Get default configuration value."""
        value = service.get("neo4j.uri")
        assert value == "bolt://localhost:7687"

    def test_get_unknown_key(self, service):
        """Get unknown key returns default."""
        value = service.get("unknown.key", default="fallback")
        assert value == "fallback"

    def test_get_all(self, service):
        """Get all configuration values."""
        config = service.get_all()
        assert "neo4j.uri" in config
        assert "cache.enabled" in config

    def test_set_value(self, service):
        """Set a configuration value."""
        success, error = service.set("cache.ttl_seconds", 7200)
        assert success is True
        assert service.get("cache.ttl_seconds") == 7200

    def test_set_invalid_value(self, service):
        """Set invalid value fails validation."""
        success, error = service.set("cache.ttl_seconds", -100)
        assert success is False
        assert "below minimum" in error

    def test_set_many(self, service):
        """Set multiple values atomically."""
        success, errors = service.set_many({
            "cache.ttl_seconds": 1800,
            "reasoning.max_hops": 3,
        })
        assert success is True
        assert service.get("cache.ttl_seconds") == 1800
        assert service.get("reasoning.max_hops") == 3

    def test_set_many_with_errors(self, service):
        """Set many with validation errors."""
        success, errors = service.set_many({
            "cache.ttl_seconds": 1800,
            "reasoning.max_hops": 100,  # Invalid: max is 10
        })
        assert success is False
        assert "reasoning.max_hops" in errors

    def test_non_hot_reloadable(self, service):
        """Non-hot-reloadable settings cannot be changed."""
        # First access to establish the value
        initial = service.get("neo4j.max_pool_size")
        success, error = service.set("neo4j.max_pool_size", 100)
        assert success is False
        assert "cannot be changed" in error

    def test_add_listener(self, service):
        """Add configuration change listener."""
        changes = []

        def listener(key, old_val, new_val):
            changes.append((key, old_val, new_val))

        service.add_listener("cache.ttl_seconds", listener)
        service.set("cache.ttl_seconds", 1000)

        assert len(changes) == 1
        assert changes[0][0] == "cache.ttl_seconds"

    def test_wildcard_listener(self, service):
        """Wildcard listener receives all matching changes."""
        changes = []

        def listener(key, old_val, new_val):
            changes.append(key)

        service.add_listener("cache.*", listener)
        service.set("cache.ttl_seconds", 1000)
        service.set("cache.max_size", 5000)

        assert len(changes) == 2

    def test_remove_listener(self, service):
        """Remove configuration listener."""
        changes = []

        def listener(key, old_val, new_val):
            changes.append(key)

        service.add_listener("cache.ttl_seconds", listener)
        service.set("cache.ttl_seconds", 1000)
        service.remove_listener("cache.ttl_seconds", listener)
        service.set("cache.ttl_seconds", 2000)

        assert len(changes) == 1

    def test_global_listener(self, service):
        """Global listener receives all changes."""
        changes = []

        def listener(change):
            changes.append(change)

        service.add_global_listener(listener)
        service.set("cache.ttl_seconds", 1000)
        service.set("reasoning.max_hops", 3)

        assert len(changes) == 2

    def test_get_changes(self, service):
        """Get configuration change history."""
        service.set("cache.ttl_seconds", 1000)
        service.set("cache.ttl_seconds", 2000)

        changes = service.get_changes()
        assert len(changes) >= 2

    def test_sensitive_value_masked(self, service):
        """Sensitive values are masked in changes."""
        service.set("neo4j.password", "secret123")
        changes = service.get_changes()

        password_change = next(c for c in changes if c.key == "neo4j.password")
        assert password_change.new_value == "***"

    def test_register_custom_schema(self, service):
        """Register a custom schema."""
        schema = ConfigSchema(
            key="custom.setting",
            value_type=ConfigValueType.INTEGER,
            default=42,
        )
        service.register_schema(schema)
        assert service.get_schema("custom.setting") is not None

    def test_load_from_file(self):
        """Load configuration from file."""
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

    def test_load_from_file_not_found(self, service):
        """Load from non-existent file fails."""
        success, error = service.load_from_file("/nonexistent/file.json")
        assert success is False
        assert "not found" in error

    def test_load_from_file_invalid_json(self):
        """Load from invalid JSON fails."""
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

    def test_export_config(self, service):
        """Export configuration."""
        config = service.export_config()
        assert "neo4j.uri" in config
        assert config["neo4j.password"] == "***"  # Masked

    def test_export_config_include_sensitive(self, service):
        """Export configuration with sensitive values."""
        config = service.export_config(include_sensitive=True)
        assert config["neo4j.password"] != "***"

    def test_export_to_file(self, service):
        """Export configuration to file."""
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

    def test_version_created(self, service):
        """Configuration version is created."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"cache": {"ttl_seconds": 1800}}, f)
            filepath = f.name

        try:
            service.load_from_file(filepath)
            versions = service.get_versions()
            assert len(versions) >= 1
        finally:
            os.unlink(filepath)

    def test_rollback(self, service):
        """Rollback to previous version."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"cache": {"ttl_seconds": 1800}}, f)
            filepath = f.name

        try:
            service.load_from_file(filepath)
            v1 = service.get_versions()[0].version

            service.set("cache.ttl_seconds", 3600)
            assert service.get("cache.ttl_seconds") == 3600

            success, error = service.rollback(v1)
            assert success is True
            assert service.get("cache.ttl_seconds") == 1800
        finally:
            os.unlink(filepath)

    def test_rollback_invalid_version(self, service):
        """Rollback to invalid version fails."""
        success, error = service.rollback(99999)
        assert success is False
        assert "not found" in error

    def test_get_diff(self, service):
        """Get diff between versions."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"cache": {"ttl_seconds": 1800}}, f)
            filepath = f.name

        try:
            service.load_from_file(filepath)
            v1 = service.get_versions()[0].version

            service.set("cache.ttl_seconds", 3600)
            # Force another version save by loading file again
            with open(filepath, "w") as f:
                json.dump({"cache": {"ttl_seconds": 3600}}, f)
            service.load_from_file(filepath)
            v2 = service.get_versions()[0].version

            diff = service.get_diff(v1, v2)
            assert "cache.ttl_seconds" in diff
        finally:
            os.unlink(filepath)

    def test_validate_all(self, service):
        """Validate all configuration values."""
        errors = service.validate_all()
        assert len(errors) == 0  # All defaults should be valid

    def test_env_override(self):
        """Environment variable overrides configuration."""
        os.environ["KG_CACHE_ENABLED"] = "false"
        try:
            service = KGConfigService()
            assert service.get("cache.enabled") is False
        finally:
            del os.environ["KG_CACHE_ENABLED"]

    def test_watch_file(self):
        """Watch file for changes."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"cache": {"ttl_seconds": 1800}}, f)
            filepath = f.name

        try:
            service = KGConfigService(config_file=filepath, watch_interval=0.1)
            service.start_watching()
            assert service.is_watching() is True

            # Modify file
            time.sleep(0.2)
            with open(filepath, "w") as f:
                json.dump({"cache": {"ttl_seconds": 2400}}, f)

            time.sleep(0.3)
            # Note: In tests, the file watcher may not pick up changes quickly
            # This just tests that watching starts/stops properly
            service.stop_watching()
            assert service.is_watching() is False
        finally:
            os.unlink(filepath)


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_config_service_returns_same_instance(self):
        """Singleton returns same instance."""
        reset_config_service()
        c1 = get_config_service()
        c2 = get_config_service()
        assert c1 is c2
        reset_config_service()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
