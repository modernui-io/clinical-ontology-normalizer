"""
Neo4j Schema Migration Service for Knowledge Graph.

This service provides versioned schema migrations for Neo4j, including:
- Constraint management (unique, exists, node key)
- Index management (composite, fulltext, vector)
- Data migrations
- Rollback capabilities
- Migration history tracking
"""

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


class MigrationStatus(str, Enum):
    """Status of a migration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    SKIPPED = "skipped"


class MigrationType(str, Enum):
    """Type of migration operation."""
    CREATE_CONSTRAINT = "create_constraint"
    DROP_CONSTRAINT = "drop_constraint"
    CREATE_INDEX = "create_index"
    DROP_INDEX = "drop_index"
    CREATE_NODE_LABEL = "create_node_label"
    CREATE_RELATIONSHIP_TYPE = "create_relationship_type"
    ADD_PROPERTY = "add_property"
    REMOVE_PROPERTY = "remove_property"
    RENAME_PROPERTY = "rename_property"
    DATA_MIGRATION = "data_migration"
    CYPHER_SCRIPT = "cypher_script"
    CUSTOM = "custom"


class ConstraintType(str, Enum):
    """Types of Neo4j constraints."""
    UNIQUE = "unique"
    EXISTS = "exists"
    NODE_KEY = "node_key"


class IndexType(str, Enum):
    """Types of Neo4j indexes."""
    BTREE = "btree"
    FULLTEXT = "fulltext"
    VECTOR = "vector"
    POINT = "point"
    RANGE = "range"
    TEXT = "text"
    LOOKUP = "lookup"


@dataclass
class MigrationOperation:
    """A single migration operation."""
    operation_type: MigrationType
    description: str
    up_cypher: str
    down_cypher: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    idempotent: bool = True
    timeout_seconds: int = 300


@dataclass
class Migration:
    """A schema migration definition."""
    version: str
    name: str
    description: str
    operations: List[MigrationOperation] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    checksum: Optional[str] = None

    def __post_init__(self):
        if not self.checksum:
            self.checksum = self._calculate_checksum()

    def _calculate_checksum(self) -> str:
        """Calculate checksum of migration content."""
        content = json.dumps({
            "version": self.version,
            "name": self.name,
            "operations": [
                {"type": op.operation_type.value, "up": op.up_cypher, "down": op.down_cypher}
                for op in self.operations
            ]
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class MigrationResult:
    """Result of executing a migration."""
    version: str
    name: str
    status: MigrationStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None
    operations_executed: int = 0
    error_message: Optional[str] = None
    error_operation: Optional[int] = None


@dataclass
class MigrationHistory:
    """Record of an applied migration."""
    version: str
    name: str
    checksum: str
    applied_at: datetime
    applied_by: str = "system"
    execution_time_ms: float = 0
    status: MigrationStatus = MigrationStatus.COMPLETED


class MigrationBuilder:
    """Builder for creating migrations fluently."""

    def __init__(self, version: str, name: str) -> None:
        self.version = version
        self.name = name
        self.description = ""
        self.operations: List[MigrationOperation] = []
        self.dependencies: List[str] = []

    def with_description(self, description: str) -> "MigrationBuilder":
        """Set migration description."""
        self.description = description
        return self

    def depends_on(self, *versions: str) -> "MigrationBuilder":
        """Add dependency on other migrations."""
        self.dependencies.extend(versions)
        return self

    def create_unique_constraint(
        self,
        label: str,
        property: str,
        name: Optional[str] = None
    ) -> "MigrationBuilder":
        """Add unique constraint creation."""
        constraint_name = name or f"{label.lower()}_{property.lower()}_unique"

        self.operations.append(MigrationOperation(
            operation_type=MigrationType.CREATE_CONSTRAINT,
            description=f"Create unique constraint on {label}.{property}",
            up_cypher=f"CREATE CONSTRAINT {constraint_name} IF NOT EXISTS FOR (n:{label}) REQUIRE n.{property} IS UNIQUE",
            down_cypher=f"DROP CONSTRAINT {constraint_name} IF EXISTS"
        ))
        return self

    def create_exists_constraint(
        self,
        label: str,
        property: str,
        name: Optional[str] = None
    ) -> "MigrationBuilder":
        """Add exists constraint creation."""
        constraint_name = name or f"{label.lower()}_{property.lower()}_exists"

        self.operations.append(MigrationOperation(
            operation_type=MigrationType.CREATE_CONSTRAINT,
            description=f"Create exists constraint on {label}.{property}",
            up_cypher=f"CREATE CONSTRAINT {constraint_name} IF NOT EXISTS FOR (n:{label}) REQUIRE n.{property} IS NOT NULL",
            down_cypher=f"DROP CONSTRAINT {constraint_name} IF EXISTS"
        ))
        return self

    def create_node_key_constraint(
        self,
        label: str,
        properties: List[str],
        name: Optional[str] = None
    ) -> "MigrationBuilder":
        """Add node key constraint creation."""
        props_str = ", ".join([f"n.{p}" for p in properties])
        constraint_name = name or f"{label.lower()}_{'_'.join(properties)}_key"

        self.operations.append(MigrationOperation(
            operation_type=MigrationType.CREATE_CONSTRAINT,
            description=f"Create node key constraint on {label}({', '.join(properties)})",
            up_cypher=f"CREATE CONSTRAINT {constraint_name} IF NOT EXISTS FOR (n:{label}) REQUIRE ({props_str}) IS NODE KEY",
            down_cypher=f"DROP CONSTRAINT {constraint_name} IF EXISTS"
        ))
        return self

    def create_index(
        self,
        label: str,
        properties: List[str],
        index_type: IndexType = IndexType.BTREE,
        name: Optional[str] = None
    ) -> "MigrationBuilder":
        """Add index creation."""
        props_str = ", ".join([f"n.{p}" for p in properties])
        index_name = name or f"{label.lower()}_{'_'.join(properties)}_idx"

        if index_type == IndexType.BTREE:
            up = f"CREATE INDEX {index_name} IF NOT EXISTS FOR (n:{label}) ON ({props_str})"
        elif index_type == IndexType.RANGE:
            up = f"CREATE RANGE INDEX {index_name} IF NOT EXISTS FOR (n:{label}) ON ({props_str})"
        elif index_type == IndexType.TEXT:
            up = f"CREATE TEXT INDEX {index_name} IF NOT EXISTS FOR (n:{label}) ON ({props_str})"
        else:
            up = f"CREATE INDEX {index_name} IF NOT EXISTS FOR (n:{label}) ON ({props_str})"

        self.operations.append(MigrationOperation(
            operation_type=MigrationType.CREATE_INDEX,
            description=f"Create {index_type.value} index on {label}({', '.join(properties)})",
            up_cypher=up,
            down_cypher=f"DROP INDEX {index_name} IF EXISTS"
        ))
        return self

    def create_fulltext_index(
        self,
        name: str,
        labels: List[str],
        properties: List[str]
    ) -> "MigrationBuilder":
        """Add fulltext index creation."""
        labels_str = ", ".join(labels)
        props_str = ", ".join([f"n.{p}" for p in properties])

        self.operations.append(MigrationOperation(
            operation_type=MigrationType.CREATE_INDEX,
            description=f"Create fulltext index {name} on {labels_str}({', '.join(properties)})",
            up_cypher=f"CREATE FULLTEXT INDEX {name} IF NOT EXISTS FOR (n:{labels_str}) ON EACH [{props_str}]",
            down_cypher=f"DROP INDEX {name} IF EXISTS"
        ))
        return self

    def create_vector_index(
        self,
        label: str,
        property: str,
        dimensions: int,
        similarity: str = "cosine",
        name: Optional[str] = None
    ) -> "MigrationBuilder":
        """Add vector index creation."""
        index_name = name or f"{label.lower()}_{property.lower()}_vector"

        self.operations.append(MigrationOperation(
            operation_type=MigrationType.CREATE_INDEX,
            description=f"Create vector index on {label}.{property} ({dimensions} dimensions)",
            up_cypher=f"""
                CREATE VECTOR INDEX {index_name} IF NOT EXISTS
                FOR (n:{label}) ON (n.{property})
                OPTIONS {{
                    indexConfig: {{
                        `vector.dimensions`: {dimensions},
                        `vector.similarity_function`: '{similarity}'
                    }}
                }}
            """,
            down_cypher=f"DROP INDEX {index_name} IF EXISTS"
        ))
        return self

    def add_property_with_default(
        self,
        label: str,
        property: str,
        default_value: Any,
        batch_size: int = 10000
    ) -> "MigrationBuilder":
        """Add property to all nodes with default value."""
        value_str = json.dumps(default_value) if isinstance(default_value, (dict, list)) else repr(default_value)

        self.operations.append(MigrationOperation(
            operation_type=MigrationType.ADD_PROPERTY,
            description=f"Add property {property} to {label} with default {default_value}",
            up_cypher=f"""
                CALL apoc.periodic.iterate(
                    'MATCH (n:{label}) WHERE n.{property} IS NULL RETURN n',
                    'SET n.{property} = {value_str}',
                    {{batchSize: {batch_size}, parallel: false}}
                )
            """,
            down_cypher=f"""
                CALL apoc.periodic.iterate(
                    'MATCH (n:{label}) RETURN n',
                    'REMOVE n.{property}',
                    {{batchSize: {batch_size}, parallel: false}}
                )
            """,
            idempotent=True,
            timeout_seconds=600
        ))
        return self

    def rename_property(
        self,
        label: str,
        old_name: str,
        new_name: str,
        batch_size: int = 10000
    ) -> "MigrationBuilder":
        """Rename a property on all nodes."""
        self.operations.append(MigrationOperation(
            operation_type=MigrationType.RENAME_PROPERTY,
            description=f"Rename property {old_name} to {new_name} on {label}",
            up_cypher=f"""
                CALL apoc.periodic.iterate(
                    'MATCH (n:{label}) WHERE n.{old_name} IS NOT NULL RETURN n',
                    'SET n.{new_name} = n.{old_name} REMOVE n.{old_name}',
                    {{batchSize: {batch_size}, parallel: false}}
                )
            """,
            down_cypher=f"""
                CALL apoc.periodic.iterate(
                    'MATCH (n:{label}) WHERE n.{new_name} IS NOT NULL RETURN n',
                    'SET n.{old_name} = n.{new_name} REMOVE n.{new_name}',
                    {{batchSize: {batch_size}, parallel: false}}
                )
            """,
            idempotent=False,
            timeout_seconds=600
        ))
        return self

    def run_cypher(
        self,
        description: str,
        up_cypher: str,
        down_cypher: Optional[str] = None,
        idempotent: bool = True,
        timeout_seconds: int = 300
    ) -> "MigrationBuilder":
        """Add custom Cypher script."""
        self.operations.append(MigrationOperation(
            operation_type=MigrationType.CYPHER_SCRIPT,
            description=description,
            up_cypher=up_cypher,
            down_cypher=down_cypher,
            idempotent=idempotent,
            timeout_seconds=timeout_seconds
        ))
        return self

    def data_migration(
        self,
        description: str,
        up_cypher: str,
        down_cypher: Optional[str] = None,
        batch_size: int = 10000,
        timeout_seconds: int = 600
    ) -> "MigrationBuilder":
        """Add data migration using APOC periodic iterate."""
        self.operations.append(MigrationOperation(
            operation_type=MigrationType.DATA_MIGRATION,
            description=description,
            up_cypher=up_cypher,
            down_cypher=down_cypher,
            idempotent=True,
            timeout_seconds=timeout_seconds
        ))
        return self

    def build(self) -> Migration:
        """Build the migration."""
        return Migration(
            version=self.version,
            name=self.name,
            description=self.description,
            operations=self.operations,
            dependencies=self.dependencies
        )


class MockNeo4jDriver:
    """
    Mock Neo4j driver for testing migrations without a real database.
    """

    def __init__(self) -> None:
        self._executed_queries: List[Tuple[str, Dict]] = []
        self._constraints: Dict[str, Dict] = {}
        self._indexes: Dict[str, Dict] = {}
        self._migration_history: Dict[str, MigrationHistory] = {}
        self._should_fail: bool = False
        self._fail_on_query: Optional[str] = None

    def execute_query(self, cypher: str, params: Optional[Dict] = None) -> List[Dict]:
        """Execute a Cypher query (mock)."""
        self._executed_queries.append((cypher, params or {}))

        if self._should_fail:
            raise Exception("Simulated database error")

        if self._fail_on_query and self._fail_on_query in cypher:
            raise Exception(f"Simulated failure on query: {self._fail_on_query}")

        # Parse and handle specific queries
        cypher_lower = cypher.lower().strip()

        # Handle constraint creation
        if "create constraint" in cypher_lower:
            match = re.search(r'constraint\s+(\w+)', cypher_lower)
            if match:
                name = match.group(1)
                self._constraints[name] = {"cypher": cypher}
            return []

        # Handle constraint drop
        if "drop constraint" in cypher_lower:
            match = re.search(r'constraint\s+(\w+)', cypher_lower)
            if match:
                name = match.group(1)
                self._constraints.pop(name, None)
            return []

        # Handle index creation
        if "create" in cypher_lower and "index" in cypher_lower:
            match = re.search(r'index\s+(\w+)', cypher_lower)
            if match:
                name = match.group(1)
                self._indexes[name] = {"cypher": cypher}
            return []

        # Handle index drop
        if "drop index" in cypher_lower:
            match = re.search(r'index\s+(\w+)', cypher_lower)
            if match:
                name = match.group(1)
                self._indexes.pop(name, None)
            return []

        return []

    def get_migration_history(self) -> List[MigrationHistory]:
        """Get all migration history."""
        return list(self._migration_history.values())

    def record_migration(self, history: MigrationHistory) -> None:
        """Record a completed migration."""
        self._migration_history[history.version] = history

    def remove_migration_record(self, version: str) -> None:
        """Remove migration from history (for rollback)."""
        self._migration_history.pop(version, None)

    def set_fail(self, should_fail: bool) -> None:
        """Set whether queries should fail."""
        self._should_fail = should_fail

    def set_fail_on_query(self, query_substring: Optional[str]) -> None:
        """Set a query substring that should cause failure."""
        self._fail_on_query = query_substring


class KGSchemaMigrationService:
    """
    Service for managing Neo4j schema migrations.
    """

    HISTORY_LABEL = "_SchemaMigration"

    def __init__(self, driver: Optional[MockNeo4jDriver] = None) -> None:
        self.driver = driver or MockNeo4jDriver()
        self._migrations: Dict[str, Migration] = {}
        self._listeners: List[Callable] = []

    def register_migration(self, migration: Migration) -> None:
        """Register a migration."""
        self._migrations[migration.version] = migration

    def register_migrations(self, migrations: List[Migration]) -> None:
        """Register multiple migrations."""
        for migration in migrations:
            self.register_migration(migration)

    def add_listener(self, listener: Callable) -> None:
        """Add migration event listener."""
        self._listeners.append(listener)

    def _emit_event(self, event_type: str, **kwargs: Any) -> None:
        """Emit event to listeners."""
        for listener in self._listeners:
            try:
                listener(event_type, **kwargs)
            except Exception:
                pass  # Don't let listener errors break migration

    def get_pending_migrations(self) -> List[Migration]:
        """Get list of pending migrations in order."""
        applied = {h.version for h in self.driver.get_migration_history()}
        pending = []
        pending_versions = set()

        for version in sorted(self._migrations.keys()):
            if version not in applied:
                migration = self._migrations[version]
                # Check dependencies - they must be either applied or already in pending
                deps_satisfied = True
                for dep in migration.dependencies:
                    if dep not in applied and dep not in pending_versions:
                        deps_satisfied = False
                        break

                if deps_satisfied:
                    pending.append(migration)
                    pending_versions.add(version)

        return pending

    def get_applied_migrations(self) -> List[MigrationHistory]:
        """Get list of applied migrations."""
        return self.driver.get_migration_history()

    def get_migration_status(self) -> Dict[str, Any]:
        """Get current migration status."""
        applied = self.driver.get_migration_history()
        pending = self.get_pending_migrations()

        return {
            "total_registered": len(self._migrations),
            "total_applied": len(applied),
            "total_pending": len(pending),
            "applied_versions": [h.version for h in applied],
            "pending_versions": [m.version for m in pending],
            "last_applied": applied[-1].version if applied else None,
            "last_applied_at": applied[-1].applied_at.isoformat() if applied else None
        }

    def run_migration(self, migration: Migration) -> MigrationResult:
        """Run a single migration."""
        start_time = datetime.now(UTC)
        self._emit_event("migration_started", version=migration.version, name=migration.name)

        result = MigrationResult(
            version=migration.version,
            name=migration.name,
            status=MigrationStatus.RUNNING,
            started_at=start_time
        )

        try:
            for i, operation in enumerate(migration.operations):
                self._emit_event(
                    "operation_started",
                    version=migration.version,
                    operation_index=i,
                    description=operation.description
                )

                try:
                    self.driver.execute_query(
                        operation.up_cypher,
                        operation.params
                    )
                    result.operations_executed += 1

                    self._emit_event(
                        "operation_completed",
                        version=migration.version,
                        operation_index=i
                    )
                except Exception as e:
                    result.status = MigrationStatus.FAILED
                    result.error_message = str(e)
                    result.error_operation = i

                    self._emit_event(
                        "operation_failed",
                        version=migration.version,
                        operation_index=i,
                        error=str(e)
                    )

                    # Attempt rollback of completed operations
                    self._rollback_operations(migration, i - 1)
                    raise

            # Record success
            result.status = MigrationStatus.COMPLETED
            result.completed_at = datetime.now(UTC)
            result.duration_ms = (result.completed_at - start_time).total_seconds() * 1000

            history = MigrationHistory(
                version=migration.version,
                name=migration.name,
                checksum=migration.checksum,
                applied_at=result.completed_at,
                execution_time_ms=result.duration_ms
            )
            self.driver.record_migration(history)

            self._emit_event(
                "migration_completed",
                version=migration.version,
                duration_ms=result.duration_ms
            )

        except Exception as e:
            result.completed_at = datetime.now(UTC)
            result.duration_ms = (result.completed_at - start_time).total_seconds() * 1000

            self._emit_event(
                "migration_failed",
                version=migration.version,
                error=str(e)
            )

        return result

    def _rollback_operations(self, migration: Migration, up_to_index: int) -> None:
        """Rollback operations from index down to 0."""
        for i in range(up_to_index, -1, -1):
            operation = migration.operations[i]
            if operation.down_cypher:
                try:
                    self.driver.execute_query(operation.down_cypher)
                except Exception:
                    pass  # Best effort rollback

    def run_pending_migrations(self) -> List[MigrationResult]:
        """Run all pending migrations in order."""
        results = []
        pending = self.get_pending_migrations()

        for migration in pending:
            result = self.run_migration(migration)
            results.append(result)

            if result.status == MigrationStatus.FAILED:
                break  # Stop on first failure

        return results

    def rollback_migration(self, version: str) -> MigrationResult:
        """Rollback a specific migration."""
        if version not in self._migrations:
            return MigrationResult(
                version=version,
                name="unknown",
                status=MigrationStatus.FAILED,
                started_at=datetime.now(UTC),
                error_message=f"Migration {version} not found"
            )

        migration = self._migrations[version]
        start_time = datetime.now(UTC)

        result = MigrationResult(
            version=version,
            name=migration.name,
            status=MigrationStatus.RUNNING,
            started_at=start_time
        )

        try:
            # Run down migrations in reverse order
            for i in range(len(migration.operations) - 1, -1, -1):
                operation = migration.operations[i]
                if operation.down_cypher:
                    self.driver.execute_query(operation.down_cypher)
                    result.operations_executed += 1

            # Remove from history
            self.driver.remove_migration_record(version)

            result.status = MigrationStatus.ROLLED_BACK
            result.completed_at = datetime.now(UTC)
            result.duration_ms = (result.completed_at - start_time).total_seconds() * 1000

        except Exception as e:
            result.status = MigrationStatus.FAILED
            result.error_message = str(e)
            result.completed_at = datetime.now(UTC)
            result.duration_ms = (result.completed_at - start_time).total_seconds() * 1000

        return result

    def validate_migrations(self) -> List[Dict[str, Any]]:
        """Validate all registered migrations."""
        issues = []

        # Check for duplicate versions
        versions = list(self._migrations.keys())
        if len(versions) != len(set(versions)):
            issues.append({
                "type": "duplicate_version",
                "message": "Duplicate migration versions detected"
            })

        # Check dependencies
        for version, migration in self._migrations.items():
            for dep in migration.dependencies:
                if dep not in self._migrations:
                    issues.append({
                        "type": "missing_dependency",
                        "version": version,
                        "dependency": dep,
                        "message": f"Migration {version} depends on {dep} which is not registered"
                    })

        # Check for circular dependencies
        try:
            self._topological_sort()
        except ValueError as e:
            issues.append({
                "type": "circular_dependency",
                "message": str(e)
            })

        # Check checksum integrity
        applied = {h.version: h.checksum for h in self.driver.get_migration_history()}
        for version, checksum in applied.items():
            if version in self._migrations:
                current = self._migrations[version].checksum
                if current != checksum:
                    issues.append({
                        "type": "checksum_mismatch",
                        "version": version,
                        "expected": checksum,
                        "actual": current,
                        "message": f"Migration {version} has been modified after being applied"
                    })

        return issues

    def _topological_sort(self) -> List[str]:
        """Sort migrations by dependencies."""
        # Build dependency graph
        in_degree = {v: 0 for v in self._migrations}
        graph = {v: [] for v in self._migrations}

        for version, migration in self._migrations.items():
            for dep in migration.dependencies:
                if dep in graph:
                    graph[dep].append(version)
                    in_degree[version] += 1

        # Kahn's algorithm
        queue = [v for v, d in in_degree.items() if d == 0]
        result = []

        while queue:
            v = queue.pop(0)
            result.append(v)

            for neighbor in graph[v]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(self._migrations):
            raise ValueError("Circular dependency detected in migrations")

        return result

    def generate_schema_report(self) -> Dict[str, Any]:
        """Generate a report of the current schema state."""
        constraints = list(self.driver._constraints.keys())
        indexes = list(self.driver._indexes.keys())
        applied = self.driver.get_migration_history()

        return {
            "constraints": constraints,
            "indexes": indexes,
            "migrations_applied": len(applied),
            "last_migration": applied[-1].version if applied else None,
            "schema_version": applied[-1].version if applied else "0.0.0"
        }


# Pre-built KG schema migrations

def create_kg_base_migrations() -> List[Migration]:
    """Create base migrations for KG schema."""
    migrations = []

    # V001: Base concept schema
    migrations.append(
        MigrationBuilder("001", "base_concept_schema")
        .with_description("Create base schema for UMLS concepts")
        .create_unique_constraint("Concept", "cui")
        .create_index("Concept", ["name"], IndexType.BTREE)
        .create_fulltext_index("concept_search", ["Concept"], ["name", "description"])
        .build()
    )

    # V002: Semantic types
    migrations.append(
        MigrationBuilder("002", "semantic_types")
        .with_description("Create schema for UMLS semantic types")
        .depends_on("001")
        .create_unique_constraint("SemanticType", "tui")
        .create_index("SemanticType", ["name"], IndexType.BTREE)
        .build()
    )

    # V003: Relationships
    migrations.append(
        MigrationBuilder("003", "relationships")
        .with_description("Create indexes for relationship traversal")
        .depends_on("001")
        .run_cypher(
            "Create relationship type index",
            "CREATE INDEX rel_type_idx IF NOT EXISTS FOR ()-[r:RELATED_TO]-() ON (r.type)",
            "DROP INDEX rel_type_idx IF EXISTS"
        )
        .build()
    )

    # V004: Temporal properties
    migrations.append(
        MigrationBuilder("004", "temporal_properties")
        .with_description("Add temporal tracking to concepts")
        .depends_on("001")
        .add_property_with_default("Concept", "valid_from", "1970-01-01")
        .create_index("Concept", ["valid_from", "valid_to"], IndexType.RANGE)
        .build()
    )

    # V005: Vector embeddings
    migrations.append(
        MigrationBuilder("005", "vector_embeddings")
        .with_description("Add vector index for semantic search")
        .depends_on("001")
        .create_vector_index("Concept", "embedding", 384, "cosine")
        .build()
    )

    # V006: Patient nodes
    migrations.append(
        MigrationBuilder("006", "patient_schema")
        .with_description("Create schema for patient nodes")
        .create_unique_constraint("Patient", "patient_id")
        .create_index("Patient", ["created_at"], IndexType.RANGE)
        .build()
    )

    return migrations


# Singleton accessor
_migration_service: Optional[KGSchemaMigrationService] = None


def get_migration_service() -> KGSchemaMigrationService:
    """Get or create the migration service singleton."""
    global _migration_service
    if _migration_service is None:
        _migration_service = KGSchemaMigrationService()
        # Register base migrations
        _migration_service.register_migrations(create_kg_base_migrations())
    return _migration_service


def reset_migration_service() -> None:
    """Reset the migration service (for testing)."""
    global _migration_service
    _migration_service = None
