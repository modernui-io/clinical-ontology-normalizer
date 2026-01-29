"""Configuration Hot Reload Service for Knowledge Graph.

This module provides dynamic configuration management with support for:
- Hot reload without service restart
- File-based configuration with change detection
- Environment variable overrides
- Validation and schema enforcement
- Configuration versioning and rollback
- Listener notifications on changes
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Type, TypeVar, Union

logger = logging.getLogger(__name__)


class ConfigValueType(str, Enum):
    """Types of configuration values."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    LIST = "list"
    DICT = "dict"


@dataclass
class ConfigSchema:
    """Schema definition for a configuration value."""

    key: str
    value_type: ConfigValueType
    default: Any = None
    description: str = ""
    required: bool = False
    min_value: float | None = None
    max_value: float | None = None
    allowed_values: list[Any | None] = None
    env_var: str | None = None  # Environment variable override
    sensitive: bool = False  # Don't log value changes
    hot_reloadable: bool = True  # Can be changed without restart

    def validate(self, value: Any) -> tuple[bool, str | None]:
        """Validate a value against this schema.

        Returns (is_valid, error_message).
        """
        if value is None:
            if self.required and self.default is None:
                return False, f"Required configuration '{self.key}' is missing"
            return True, None

        # Type validation
        expected_types = {
            ConfigValueType.STRING: str,
            ConfigValueType.INTEGER: int,
            ConfigValueType.FLOAT: (int, float),
            ConfigValueType.BOOLEAN: bool,
            ConfigValueType.LIST: list,
            ConfigValueType.DICT: dict,
        }

        expected = expected_types.get(self.value_type)
        if expected and not isinstance(value, expected):
            return False, f"'{self.key}' expected {self.value_type.value}, got {type(value).__name__}"

        # Range validation
        if self.min_value is not None and value < self.min_value:
            return False, f"'{self.key}' value {value} is below minimum {self.min_value}"
        if self.max_value is not None and value > self.max_value:
            return False, f"'{self.key}' value {value} is above maximum {self.max_value}"

        # Allowed values validation
        if self.allowed_values is not None and value not in self.allowed_values:
            return False, f"'{self.key}' value {value} not in allowed values: {self.allowed_values}"

        return True, None


@dataclass
class ConfigChange:
    """Record of a configuration change."""

    key: str
    old_value: Any
    new_value: Any
    timestamp: datetime
    source: str  # file, env, api, rollback
    user: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "old_value": self.old_value if not isinstance(self.old_value, Exception) else str(self.old_value),
            "new_value": self.new_value if not isinstance(self.new_value, Exception) else str(self.new_value),
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "user": self.user,
        }


@dataclass
class ConfigVersion:
    """A snapshot of configuration at a point in time."""

    version: int
    timestamp: datetime
    config: dict[str, Any]
    hash: str
    source: str

    @staticmethod
    def compute_hash(config: dict[str, Any]) -> str:
        """Compute hash of configuration."""
        json_str = json.dumps(config, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()[:16]


class KGConfigService:
    """Configuration service with hot reload support.

    Provides dynamic configuration management for Knowledge Graph services.
    """

    # Default KG configuration schemas
    DEFAULT_SCHEMAS = [
        # Neo4j settings
        ConfigSchema(
            key="neo4j.uri",
            value_type=ConfigValueType.STRING,
            default="bolt://localhost:7687",
            description="Neo4j database URI",
            env_var="NEO4J_URI",
        ),
        ConfigSchema(
            key="neo4j.user",
            value_type=ConfigValueType.STRING,
            default="neo4j",
            description="Neo4j username",
            env_var="NEO4J_USER",
        ),
        ConfigSchema(
            key="neo4j.password",
            value_type=ConfigValueType.STRING,
            default="password",
            description="Neo4j password",
            env_var="NEO4J_PASSWORD",
            sensitive=True,
        ),
        ConfigSchema(
            key="neo4j.max_pool_size",
            value_type=ConfigValueType.INTEGER,
            default=50,
            description="Maximum connection pool size",
            min_value=1,
            max_value=500,
            hot_reloadable=False,  # Requires restart
        ),

        # Cache settings
        ConfigSchema(
            key="cache.enabled",
            value_type=ConfigValueType.BOOLEAN,
            default=True,
            description="Enable caching",
            env_var="KG_CACHE_ENABLED",
        ),
        ConfigSchema(
            key="cache.ttl_seconds",
            value_type=ConfigValueType.INTEGER,
            default=3600,
            description="Cache TTL in seconds",
            min_value=0,
            max_value=86400 * 7,
        ),
        ConfigSchema(
            key="cache.max_size",
            value_type=ConfigValueType.INTEGER,
            default=10000,
            description="Maximum cache entries",
            min_value=100,
            max_value=1000000,
        ),

        # Reasoning settings
        ConfigSchema(
            key="reasoning.max_hops",
            value_type=ConfigValueType.INTEGER,
            default=5,
            description="Maximum reasoning path hops",
            min_value=1,
            max_value=10,
        ),
        ConfigSchema(
            key="reasoning.max_paths",
            value_type=ConfigValueType.INTEGER,
            default=100,
            description="Maximum paths to return",
            min_value=1,
            max_value=1000,
        ),
        ConfigSchema(
            key="reasoning.confidence_threshold",
            value_type=ConfigValueType.FLOAT,
            default=0.5,
            description="Minimum confidence score",
            min_value=0.0,
            max_value=1.0,
        ),

        # Embedding settings
        ConfigSchema(
            key="embedding.model",
            value_type=ConfigValueType.STRING,
            default="all-MiniLM-L6-v2",
            description="Sentence transformer model",
            allowed_values=["all-MiniLM-L6-v2", "all-mpnet-base-v2", "paraphrase-multilingual-MiniLM-L12-v2"],
            hot_reloadable=False,
        ),
        ConfigSchema(
            key="embedding.dimension",
            value_type=ConfigValueType.INTEGER,
            default=384,
            description="Embedding dimension",
            allowed_values=[384, 768, 1024],
            hot_reloadable=False,
        ),
        ConfigSchema(
            key="embedding.batch_size",
            value_type=ConfigValueType.INTEGER,
            default=32,
            description="Batch size for embedding generation",
            min_value=1,
            max_value=256,
        ),

        # Rate limiting
        ConfigSchema(
            key="rate_limit.enabled",
            value_type=ConfigValueType.BOOLEAN,
            default=True,
            description="Enable rate limiting",
        ),
        ConfigSchema(
            key="rate_limit.requests_per_minute",
            value_type=ConfigValueType.INTEGER,
            default=100,
            description="Requests per minute per client",
            min_value=1,
            max_value=10000,
        ),

        # Circuit breaker
        ConfigSchema(
            key="circuit_breaker.enabled",
            value_type=ConfigValueType.BOOLEAN,
            default=True,
            description="Enable circuit breaker",
        ),
        ConfigSchema(
            key="circuit_breaker.failure_threshold",
            value_type=ConfigValueType.INTEGER,
            default=5,
            description="Failures before opening circuit",
            min_value=1,
            max_value=100,
        ),
        ConfigSchema(
            key="circuit_breaker.recovery_timeout",
            value_type=ConfigValueType.INTEGER,
            default=30,
            description="Seconds before half-open",
            min_value=1,
            max_value=300,
        ),

        # Logging
        ConfigSchema(
            key="logging.level",
            value_type=ConfigValueType.STRING,
            default="INFO",
            description="Logging level",
            allowed_values=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        ),
        ConfigSchema(
            key="logging.format",
            value_type=ConfigValueType.STRING,
            default="json",
            description="Log format",
            allowed_values=["json", "text"],
        ),

        # Feature flags
        ConfigSchema(
            key="features.multi_agent",
            value_type=ConfigValueType.BOOLEAN,
            default=True,
            description="Enable multi-agent orchestration",
        ),
        ConfigSchema(
            key="features.webhooks",
            value_type=ConfigValueType.BOOLEAN,
            default=True,
            description="Enable webhook support",
        ),
        ConfigSchema(
            key="features.streaming",
            value_type=ConfigValueType.BOOLEAN,
            default=True,
            description="Enable Kafka streaming",
        ),
    ]

    def __init__(
        self,
        config_file: str | None = None,
        watch_interval: float = 5.0,
        max_versions: int = 100,
    ):
        self.config_file = config_file
        self.watch_interval = watch_interval
        self.max_versions = max_versions

        self._config: dict[str, Any] = {}
        self._schemas: dict[str, ConfigSchema] = {}
        self._versions: list[ConfigVersion] = []
        self._current_version = 0
        self._changes: list[ConfigChange] = []
        self._listeners: dict[str, list[Callable[[str, Any, Any], None]]] = defaultdict(list)
        self._global_listeners: list[Callable[[ConfigChange], None]] = []
        self._lock = threading.RLock()

        self._watching = False
        self._watch_thread: threading.Thread | None = None
        self._last_file_hash: str | None = None

        # Register default schemas
        for schema in self.DEFAULT_SCHEMAS:
            self.register_schema(schema)

        # Load initial config
        self._load_defaults()
        if config_file:
            self.load_from_file(config_file)
        self._apply_env_overrides()

    def register_schema(self, schema: ConfigSchema) -> None:
        """Register a configuration schema."""
        with self._lock:
            self._schemas[schema.key] = schema

    def get_schema(self, key: str) -> ConfigSchema | None:
        """Get schema for a configuration key."""
        return self._schemas.get(key)

    def _load_defaults(self) -> None:
        """Load default values from schemas."""
        for key, schema in self._schemas.items():
            if schema.default is not None:
                self._config[key] = schema.default

    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides."""
        for key, schema in self._schemas.items():
            if schema.env_var:
                env_value = os.environ.get(schema.env_var)
                if env_value is not None:
                    try:
                        # Convert string to appropriate type
                        converted = self._convert_value(env_value, schema.value_type)
                        is_valid, error = schema.validate(converted)
                        if is_valid:
                            old_value = self._config.get(key)
                            self._config[key] = converted
                            self._record_change(key, old_value, converted, "env")
                    except ValueError:
                        pass  # Skip invalid env values

    def _convert_value(self, value: str, value_type: ConfigValueType) -> Any:
        """Convert string value to appropriate type."""
        if value_type == ConfigValueType.STRING:
            return value
        elif value_type == ConfigValueType.INTEGER:
            return int(value)
        elif value_type == ConfigValueType.FLOAT:
            return float(value)
        elif value_type == ConfigValueType.BOOLEAN:
            return value.lower() in ("true", "1", "yes", "on")
        elif value_type == ConfigValueType.LIST:
            return json.loads(value)
        elif value_type == ConfigValueType.DICT:
            return json.loads(value)
        return value

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        with self._lock:
            return self._config.get(key, default)

    def get_all(self) -> dict[str, Any]:
        """Get all configuration values."""
        with self._lock:
            return self._config.copy()

    def set(
        self,
        key: str,
        value: Any,
        source: str = "api",
        user: str | None = None,
    ) -> tuple[bool, str | None]:
        """Set a configuration value.

        Returns (success, error_message).
        """
        with self._lock:
            schema = self._schemas.get(key)

            if schema:
                # Validate against schema
                is_valid, error = schema.validate(value)
                if not is_valid:
                    return False, error

                # Check if hot reloadable
                if not schema.hot_reloadable and key in self._config:
                    return False, f"'{key}' cannot be changed without restart"

            old_value = self._config.get(key)
            if old_value == value:
                return True, None  # No change

            self._config[key] = value
            self._record_change(key, old_value, value, source, user)
            self._notify_listeners(key, old_value, value)

            return True, None

    def set_many(
        self,
        values: dict[str, Any],
        source: str = "api",
        user: str | None = None,
    ) -> tuple[bool, dict[str, str]]:
        """Set multiple configuration values atomically.

        Returns (all_success, errors_dict).
        """
        errors: dict[str, str] = {}

        with self._lock:
            # Validate all first
            for key, value in values.items():
                schema = self._schemas.get(key)
                if schema:
                    is_valid, error = schema.validate(value)
                    if not is_valid:
                        errors[key] = error
                        continue
                    if not schema.hot_reloadable and key in self._config:
                        errors[key] = f"'{key}' cannot be changed without restart"

            if errors:
                return False, errors

            # Apply all changes
            for key, value in values.items():
                old_value = self._config.get(key)
                if old_value != value:
                    self._config[key] = value
                    self._record_change(key, old_value, value, source, user)
                    self._notify_listeners(key, old_value, value)

            return True, {}

    def _record_change(
        self,
        key: str,
        old_value: Any,
        new_value: Any,
        source: str,
        user: str | None = None,
    ) -> None:
        """Record a configuration change."""
        # Mask sensitive values
        schema = self._schemas.get(key)
        if schema and schema.sensitive:
            old_value = "***" if old_value else None
            new_value = "***" if new_value else None

        change = ConfigChange(
            key=key,
            old_value=old_value,
            new_value=new_value,
            timestamp=datetime.utcnow(),
            source=source,
            user=user,
        )
        self._changes.append(change)

        # Notify global listeners
        for listener in self._global_listeners:
            try:
                listener(change)
            except Exception:
                pass

    def _notify_listeners(self, key: str, old_value: Any, new_value: Any) -> None:
        """Notify listeners of a configuration change."""
        # Key-specific listeners
        for listener in self._listeners.get(key, []):
            try:
                listener(key, old_value, new_value)
            except Exception:
                pass

        # Wildcard listeners (e.g., "cache.*")
        parts = key.split(".")
        for i in range(len(parts)):
            pattern = ".".join(parts[:i + 1]) + ".*"
            for listener in self._listeners.get(pattern, []):
                try:
                    listener(key, old_value, new_value)
                except Exception:
                    pass

    def add_listener(
        self,
        key: str,
        listener: Callable[[str, Any, Any], None],
    ) -> None:
        """Add a listener for configuration changes.

        Key can be specific ("cache.ttl_seconds") or pattern ("cache.*").
        """
        with self._lock:
            self._listeners[key].append(listener)

    def remove_listener(
        self,
        key: str,
        listener: Callable[[str, Any, Any], None],
    ) -> None:
        """Remove a configuration listener."""
        with self._lock:
            if listener in self._listeners.get(key, []):
                self._listeners[key].remove(listener)

    def add_global_listener(self, listener: Callable[[ConfigChange], None]) -> None:
        """Add a global listener for all configuration changes."""
        self._global_listeners.append(listener)

    def remove_global_listener(self, listener: Callable[[ConfigChange], None]) -> None:
        """Remove a global listener."""
        if listener in self._global_listeners:
            self._global_listeners.remove(listener)

    def load_from_file(self, filepath: str) -> tuple[bool, str | None]:
        """Load configuration from a JSON file.

        Returns (success, error_message).
        """
        try:
            path = Path(filepath)
            if not path.exists():
                return False, f"Configuration file not found: {filepath}"

            with open(path) as f:
                data = json.load(f)

            # Flatten nested dict
            flat_config = self._flatten_dict(data)

            # Apply all values
            success, errors = self.set_many(flat_config, source="file")
            if errors:
                return False, f"Validation errors: {errors}"

            self._config_file = filepath
            self._last_file_hash = self._compute_file_hash(filepath)
            self._save_version("file")

            return True, None
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON: {e}"
        except Exception as e:
            return False, str(e)

    def _flatten_dict(self, d: dict[str, Any], prefix: str = "") -> dict[str, Any]:
        """Flatten a nested dictionary."""
        result = {}
        for key, value in d.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict) and not any(full_key.startswith(k) for k in self._schemas):
                result.update(self._flatten_dict(value, full_key))
            else:
                result[full_key] = value
        return result

    def _compute_file_hash(self, filepath: str) -> str:
        """Compute hash of a file."""
        with open(filepath, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    def _save_version(self, source: str) -> None:
        """Save a configuration version snapshot."""
        with self._lock:
            self._current_version += 1
            version = ConfigVersion(
                version=self._current_version,
                timestamp=datetime.utcnow(),
                config=copy.deepcopy(self._config),
                hash=ConfigVersion.compute_hash(self._config),
                source=source,
            )
            self._versions.append(version)

            # Limit versions
            if len(self._versions) > self.max_versions:
                self._versions = self._versions[-self.max_versions:]

    def get_version(self, version: int) -> ConfigVersion | None:
        """Get a specific configuration version."""
        with self._lock:
            for v in self._versions:
                if v.version == version:
                    return v
            return None

    def get_versions(self, limit: int = 10) -> list[ConfigVersion]:
        """Get recent configuration versions."""
        with self._lock:
            return list(reversed(self._versions[-limit:]))

    def rollback(self, version: int, user: str | None = None) -> tuple[bool, str | None]:
        """Rollback to a previous configuration version.

        Returns (success, error_message).
        """
        with self._lock:
            target = self.get_version(version)
            if not target:
                return False, f"Version {version} not found"

            # Check for non-hot-reloadable changes
            for key, value in target.config.items():
                schema = self._schemas.get(key)
                if schema and not schema.hot_reloadable:
                    current = self._config.get(key)
                    if current != value:
                        return False, f"Cannot rollback: '{key}' requires restart"

            # Apply rollback
            for key, value in target.config.items():
                old_value = self._config.get(key)
                if old_value != value:
                    self._config[key] = value
                    self._record_change(key, old_value, value, "rollback", user)
                    self._notify_listeners(key, old_value, value)

            self._save_version("rollback")
            return True, None

    def get_changes(self, limit: int = 100) -> list[ConfigChange]:
        """Get recent configuration changes."""
        with self._lock:
            return list(reversed(self._changes[-limit:]))

    def start_watching(self) -> None:
        """Start watching configuration file for changes."""
        if not self.config_file:
            return

        with self._lock:
            if self._watching:
                return

            self._watching = True
            self._watch_thread = threading.Thread(
                target=self._watch_file,
                daemon=True,
            )
            self._watch_thread.start()

    def stop_watching(self) -> None:
        """Stop watching configuration file."""
        with self._lock:
            self._watching = False
            if self._watch_thread:
                self._watch_thread.join(timeout=self.watch_interval + 1)
                self._watch_thread = None

    def _watch_file(self) -> None:
        """Watch configuration file for changes."""
        while self._watching:
            try:
                if self.config_file and Path(self.config_file).exists():
                    current_hash = self._compute_file_hash(self.config_file)
                    if current_hash != self._last_file_hash:
                        self.load_from_file(self.config_file)
            except Exception:
                pass

            time.sleep(self.watch_interval)

    def export_config(self, include_sensitive: bool = False) -> dict[str, Any]:
        """Export configuration as a dictionary."""
        with self._lock:
            result = {}
            for key, value in self._config.items():
                schema = self._schemas.get(key)
                if schema and schema.sensitive and not include_sensitive:
                    result[key] = "***"
                else:
                    result[key] = value
            return result

    def export_to_file(self, filepath: str, include_sensitive: bool = False) -> tuple[bool, str | None]:
        """Export configuration to a JSON file.

        Returns (success, error_message).
        """
        try:
            config = self.export_config(include_sensitive=include_sensitive)

            # Convert flat keys to nested dict
            nested = {}
            for key, value in config.items():
                parts = key.split(".")
                current = nested
                for part in parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                current[parts[-1]] = value

            with open(filepath, "w") as f:
                json.dump(nested, f, indent=2, default=str)

            return True, None
        except Exception as e:
            return False, str(e)

    def validate_all(self) -> dict[str, str]:
        """Validate all current configuration values.

        Returns dict of key -> error message for invalid values.
        """
        errors: dict[str, str] = {}
        with self._lock:
            for key, schema in self._schemas.items():
                value = self._config.get(key)
                is_valid, error = schema.validate(value)
                if not is_valid:
                    errors[key] = error
        return errors

    def get_diff(self, version1: int, version2: int) -> dict[str, tuple[Any, Any]]:
        """Get differences between two configuration versions.

        Returns dict of key -> (old_value, new_value).
        """
        v1 = self.get_version(version1)
        v2 = self.get_version(version2)

        if not v1 or not v2:
            return {}

        diff: dict[str, tuple[Any, Any]] = {}
        all_keys = set(v1.config.keys()) | set(v2.config.keys())

        for key in all_keys:
            val1 = v1.config.get(key)
            val2 = v2.config.get(key)
            if val1 != val2:
                diff[key] = (val1, val2)

        return diff

    def is_watching(self) -> bool:
        """Check if file watching is active."""
        return self._watching


# Singleton instance
_config_service: KGConfigService | None = None


def get_config_service() -> KGConfigService:
    """Get the singleton config service instance."""
    global _config_service
    if _config_service is None:
        _config_service = KGConfigService()
    return _config_service


def reset_config_service() -> None:
    """Reset the config service (for testing)."""
    global _config_service
    if _config_service:
        _config_service.stop_watching()
    _config_service = None
