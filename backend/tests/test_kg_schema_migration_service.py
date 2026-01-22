"""
Tests for KG Schema Migration Service.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.kg_schema_migration_service import (
    MigrationStatus,
    MigrationType,
    ConstraintType,
    IndexType,
    MigrationOperation,
    Migration,
    MigrationResult,
    MigrationHistory,
    MigrationBuilder,
    MockNeo4jDriver,
    KGSchemaMigrationService,
    create_kg_base_migrations,
    get_migration_service,
    reset_migration_service,
)


# ============================================================
# MigrationOperation Tests
# ============================================================

class TestMigrationOperation:
    """Tests for MigrationOperation dataclass."""

    def test_create_operation(self):
        """Test creating a migration operation."""
        op = MigrationOperation(
            operation_type=MigrationType.CREATE_CONSTRAINT,
            description="Create unique constraint",
            up_cypher="CREATE CONSTRAINT test FOR (n:Node) REQUIRE n.id IS UNIQUE",
            down_cypher="DROP CONSTRAINT test"
        )

        assert op.operation_type == MigrationType.CREATE_CONSTRAINT
        assert op.description == "Create unique constraint"
        assert "CREATE CONSTRAINT" in op.up_cypher
        assert op.idempotent is True
        assert op.timeout_seconds == 300

    def test_operation_with_params(self):
        """Test operation with parameters."""
        op = MigrationOperation(
            operation_type=MigrationType.DATA_MIGRATION,
            description="Migrate data",
            up_cypher="MATCH (n) SET n.prop = $value",
            params={"value": "test"}
        )

        assert op.params["value"] == "test"

    def test_non_idempotent_operation(self):
        """Test non-idempotent operation."""
        op = MigrationOperation(
            operation_type=MigrationType.RENAME_PROPERTY,
            description="Rename property",
            up_cypher="...",
            idempotent=False,
            timeout_seconds=600
        )

        assert op.idempotent is False
        assert op.timeout_seconds == 600


# ============================================================
# Migration Tests
# ============================================================

class TestMigration:
    """Tests for Migration dataclass."""

    def test_create_migration(self):
        """Test creating a migration."""
        migration = Migration(
            version="001",
            name="test_migration",
            description="Test migration",
            operations=[]
        )

        assert migration.version == "001"
        assert migration.name == "test_migration"
        assert migration.checksum is not None

    def test_checksum_calculation(self):
        """Test checksum is calculated consistently."""
        migration1 = Migration(
            version="001",
            name="test",
            description="Test",
            operations=[
                MigrationOperation(
                    operation_type=MigrationType.CREATE_INDEX,
                    description="Create index",
                    up_cypher="CREATE INDEX idx"
                )
            ]
        )

        migration2 = Migration(
            version="001",
            name="test",
            description="Test",
            operations=[
                MigrationOperation(
                    operation_type=MigrationType.CREATE_INDEX,
                    description="Create index",
                    up_cypher="CREATE INDEX idx"
                )
            ]
        )

        assert migration1.checksum == migration2.checksum

    def test_different_operations_different_checksum(self):
        """Test different operations produce different checksums."""
        migration1 = Migration(
            version="001",
            name="test",
            description="Test",
            operations=[
                MigrationOperation(
                    operation_type=MigrationType.CREATE_INDEX,
                    description="Create index",
                    up_cypher="CREATE INDEX idx1"
                )
            ]
        )

        migration2 = Migration(
            version="001",
            name="test",
            description="Test",
            operations=[
                MigrationOperation(
                    operation_type=MigrationType.CREATE_INDEX,
                    description="Create index",
                    up_cypher="CREATE INDEX idx2"
                )
            ]
        )

        assert migration1.checksum != migration2.checksum

    def test_migration_with_dependencies(self):
        """Test migration with dependencies."""
        migration = Migration(
            version="002",
            name="dependent",
            description="Depends on 001",
            dependencies=["001"],
            operations=[]
        )

        assert migration.dependencies == ["001"]


# ============================================================
# MigrationBuilder Tests
# ============================================================

class TestMigrationBuilder:
    """Tests for MigrationBuilder."""

    def test_basic_builder(self):
        """Test basic builder usage."""
        migration = (
            MigrationBuilder("001", "test_migration")
            .with_description("Test migration")
            .build()
        )

        assert migration.version == "001"
        assert migration.name == "test_migration"
        assert migration.description == "Test migration"

    def test_unique_constraint(self):
        """Test creating unique constraint."""
        migration = (
            MigrationBuilder("001", "test")
            .create_unique_constraint("User", "email")
            .build()
        )

        assert len(migration.operations) == 1
        op = migration.operations[0]
        assert op.operation_type == MigrationType.CREATE_CONSTRAINT
        assert "UNIQUE" in op.up_cypher
        assert "DROP CONSTRAINT" in op.down_cypher

    def test_exists_constraint(self):
        """Test creating exists constraint."""
        migration = (
            MigrationBuilder("001", "test")
            .create_exists_constraint("User", "name")
            .build()
        )

        op = migration.operations[0]
        assert "IS NOT NULL" in op.up_cypher

    def test_node_key_constraint(self):
        """Test creating node key constraint."""
        migration = (
            MigrationBuilder("001", "test")
            .create_node_key_constraint("Order", ["customer_id", "order_number"])
            .build()
        )

        op = migration.operations[0]
        assert "IS NODE KEY" in op.up_cypher
        assert "customer_id" in op.up_cypher
        assert "order_number" in op.up_cypher

    def test_create_index(self):
        """Test creating index."""
        migration = (
            MigrationBuilder("001", "test")
            .create_index("User", ["email", "name"])
            .build()
        )

        op = migration.operations[0]
        assert op.operation_type == MigrationType.CREATE_INDEX
        assert "CREATE INDEX" in op.up_cypher

    def test_create_range_index(self):
        """Test creating range index."""
        migration = (
            MigrationBuilder("001", "test")
            .create_index("Event", ["timestamp"], IndexType.RANGE)
            .build()
        )

        op = migration.operations[0]
        assert "RANGE INDEX" in op.up_cypher

    def test_create_fulltext_index(self):
        """Test creating fulltext index."""
        migration = (
            MigrationBuilder("001", "test")
            .create_fulltext_index("search_idx", ["Article", "Post"], ["title", "content"])
            .build()
        )

        op = migration.operations[0]
        assert "FULLTEXT INDEX" in op.up_cypher
        assert "Article" in op.up_cypher
        assert "title" in op.up_cypher

    def test_create_vector_index(self):
        """Test creating vector index."""
        migration = (
            MigrationBuilder("001", "test")
            .create_vector_index("Document", "embedding", 768, "cosine")
            .build()
        )

        op = migration.operations[0]
        assert "VECTOR INDEX" in op.up_cypher
        assert "768" in op.up_cypher
        assert "cosine" in op.up_cypher

    def test_add_property_with_default(self):
        """Test adding property with default value."""
        migration = (
            MigrationBuilder("001", "test")
            .add_property_with_default("User", "status", "active")
            .build()
        )

        op = migration.operations[0]
        assert op.operation_type == MigrationType.ADD_PROPERTY
        assert "status" in op.up_cypher
        assert "active" in op.up_cypher

    def test_rename_property(self):
        """Test renaming property."""
        migration = (
            MigrationBuilder("001", "test")
            .rename_property("User", "fullName", "full_name")
            .build()
        )

        op = migration.operations[0]
        assert op.operation_type == MigrationType.RENAME_PROPERTY
        assert op.idempotent is False
        assert "fullName" in op.up_cypher
        assert "full_name" in op.up_cypher

    def test_custom_cypher(self):
        """Test custom Cypher script."""
        migration = (
            MigrationBuilder("001", "test")
            .run_cypher(
                "Custom operation",
                "MATCH (n) SET n.updated = true",
                "MATCH (n) REMOVE n.updated"
            )
            .build()
        )

        op = migration.operations[0]
        assert op.operation_type == MigrationType.CYPHER_SCRIPT
        assert "SET n.updated = true" in op.up_cypher

    def test_depends_on(self):
        """Test setting dependencies."""
        migration = (
            MigrationBuilder("002", "test")
            .depends_on("001", "001a")
            .build()
        )

        assert migration.dependencies == ["001", "001a"]

    def test_chained_operations(self):
        """Test chaining multiple operations."""
        migration = (
            MigrationBuilder("001", "comprehensive")
            .with_description("Multiple operations")
            .create_unique_constraint("User", "id")
            .create_index("User", ["email"])
            .add_property_with_default("User", "created_at", "2024-01-01")
            .build()
        )

        assert len(migration.operations) == 3


# ============================================================
# MockNeo4jDriver Tests
# ============================================================

class TestMockNeo4jDriver:
    """Tests for MockNeo4jDriver."""

    def test_execute_query(self):
        """Test basic query execution."""
        driver = MockNeo4jDriver()

        result = driver.execute_query("MATCH (n) RETURN n")

        assert len(driver._executed_queries) == 1
        assert driver._executed_queries[0][0] == "MATCH (n) RETURN n"

    def test_create_constraint_tracked(self):
        """Test constraint creation is tracked."""
        driver = MockNeo4jDriver()

        driver.execute_query("CREATE CONSTRAINT test_constraint FOR (n:Node) REQUIRE n.id IS UNIQUE")

        assert "test_constraint" in driver._constraints

    def test_drop_constraint_tracked(self):
        """Test constraint drop is tracked."""
        driver = MockNeo4jDriver()

        driver.execute_query("CREATE CONSTRAINT my_constraint FOR (n:Node) REQUIRE n.id IS UNIQUE")
        driver.execute_query("DROP CONSTRAINT my_constraint")

        assert "my_constraint" not in driver._constraints

    def test_create_index_tracked(self):
        """Test index creation is tracked."""
        driver = MockNeo4jDriver()

        driver.execute_query("CREATE INDEX test_index FOR (n:Node) ON (n.name)")

        assert "test_index" in driver._indexes

    def test_drop_index_tracked(self):
        """Test index drop is tracked."""
        driver = MockNeo4jDriver()

        driver.execute_query("CREATE INDEX my_index FOR (n:Node) ON (n.name)")
        driver.execute_query("DROP INDEX my_index")

        assert "my_index" not in driver._indexes

    def test_simulate_failure(self):
        """Test simulating database failure."""
        driver = MockNeo4jDriver()
        driver.set_fail(True)

        with pytest.raises(Exception) as exc_info:
            driver.execute_query("MATCH (n) RETURN n")

        assert "Simulated database error" in str(exc_info.value)

    def test_fail_on_specific_query(self):
        """Test failing on specific query."""
        driver = MockNeo4jDriver()
        driver.set_fail_on_query("CREATE INDEX")

        # This should succeed
        driver.execute_query("MATCH (n) RETURN n")

        # This should fail
        with pytest.raises(Exception):
            driver.execute_query("CREATE INDEX test FOR (n:Node) ON (n.name)")

    def test_migration_history(self):
        """Test migration history tracking."""
        driver = MockNeo4jDriver()

        history = MigrationHistory(
            version="001",
            name="test",
            checksum="abc123",
            applied_at=datetime.now()
        )
        driver.record_migration(history)

        records = driver.get_migration_history()
        assert len(records) == 1
        assert records[0].version == "001"

    def test_remove_migration_record(self):
        """Test removing migration record."""
        driver = MockNeo4jDriver()

        history = MigrationHistory(
            version="001",
            name="test",
            checksum="abc123",
            applied_at=datetime.now()
        )
        driver.record_migration(history)
        driver.remove_migration_record("001")

        records = driver.get_migration_history()
        assert len(records) == 0


# ============================================================
# KGSchemaMigrationService Tests
# ============================================================

class TestKGSchemaMigrationService:
    """Tests for KGSchemaMigrationService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.driver = MockNeo4jDriver()
        self.service = KGSchemaMigrationService(driver=self.driver)

    def test_register_migration(self):
        """Test registering a migration."""
        migration = Migration(
            version="001",
            name="test",
            description="Test",
            operations=[]
        )

        self.service.register_migration(migration)

        assert "001" in self.service._migrations

    def test_register_multiple_migrations(self):
        """Test registering multiple migrations."""
        migrations = [
            Migration(version="001", name="first", description="", operations=[]),
            Migration(version="002", name="second", description="", operations=[]),
        ]

        self.service.register_migrations(migrations)

        assert len(self.service._migrations) == 2

    def test_get_pending_migrations(self):
        """Test getting pending migrations."""
        self.service.register_migrations([
            Migration(version="001", name="first", description="", operations=[]),
            Migration(version="002", name="second", description="", operations=[]),
        ])

        pending = self.service.get_pending_migrations()

        assert len(pending) == 2
        assert pending[0].version == "001"

    def test_get_pending_respects_applied(self):
        """Test pending migrations excludes applied."""
        self.service.register_migrations([
            Migration(version="001", name="first", description="", operations=[]),
            Migration(version="002", name="second", description="", operations=[]),
        ])

        # Mark 001 as applied
        self.driver.record_migration(MigrationHistory(
            version="001",
            name="first",
            checksum="abc",
            applied_at=datetime.now()
        ))

        pending = self.service.get_pending_migrations()

        assert len(pending) == 1
        assert pending[0].version == "002"

    def test_get_pending_respects_dependencies(self):
        """Test pending migrations respects dependencies."""
        self.service.register_migrations([
            Migration(version="001", name="first", description="", operations=[]),
            Migration(version="002", name="second", description="", operations=[], dependencies=["001"]),
        ])

        pending = self.service.get_pending_migrations()

        # Both should be pending, in order
        assert len(pending) == 2
        assert pending[0].version == "001"

    def test_run_migration_success(self):
        """Test running a migration successfully."""
        migration = (
            MigrationBuilder("001", "test")
            .create_unique_constraint("User", "id")
            .build()
        )
        self.service.register_migration(migration)

        result = self.service.run_migration(migration)

        assert result.status == MigrationStatus.COMPLETED
        assert result.operations_executed == 1
        assert result.duration_ms > 0

        # Check history was recorded
        history = self.driver.get_migration_history()
        assert len(history) == 1

    def test_run_migration_failure(self):
        """Test migration failure handling."""
        migration = (
            MigrationBuilder("001", "test")
            .run_cypher("Fail", "FAIL_QUERY", "UNDO")
            .build()
        )
        self.service.register_migration(migration)

        self.driver.set_fail_on_query("FAIL_QUERY")

        result = self.service.run_migration(migration)

        assert result.status == MigrationStatus.FAILED
        assert result.error_message is not None

    def test_run_pending_migrations(self):
        """Test running all pending migrations."""
        self.service.register_migrations([
            MigrationBuilder("001", "first")
            .create_unique_constraint("User", "id")
            .build(),
            MigrationBuilder("002", "second")
            .create_index("User", ["email"])
            .build(),
        ])

        results = self.service.run_pending_migrations()

        assert len(results) == 2
        assert all(r.status == MigrationStatus.COMPLETED for r in results)

    def test_run_pending_stops_on_failure(self):
        """Test pending migrations stop on first failure."""
        self.service.register_migrations([
            MigrationBuilder("001", "first")
            .run_cypher("Fail", "FAIL_QUERY", None)
            .build(),
            MigrationBuilder("002", "second")
            .create_index("User", ["email"])
            .build(),
        ])

        self.driver.set_fail_on_query("FAIL_QUERY")

        results = self.service.run_pending_migrations()

        assert len(results) == 1
        assert results[0].status == MigrationStatus.FAILED

    def test_rollback_migration(self):
        """Test rolling back a migration."""
        migration = (
            MigrationBuilder("001", "test")
            .create_unique_constraint("User", "id")
            .build()
        )
        self.service.register_migration(migration)
        self.service.run_migration(migration)

        result = self.service.rollback_migration("001")

        assert result.status == MigrationStatus.ROLLED_BACK

        # History should be removed
        history = self.driver.get_migration_history()
        assert len(history) == 0

    def test_rollback_unknown_migration(self):
        """Test rolling back unknown migration."""
        result = self.service.rollback_migration("unknown")

        assert result.status == MigrationStatus.FAILED
        assert "not found" in result.error_message

    def test_get_migration_status(self):
        """Test getting migration status."""
        self.service.register_migrations([
            Migration(version="001", name="first", description="", operations=[]),
            Migration(version="002", name="second", description="", operations=[]),
        ])

        self.driver.record_migration(MigrationHistory(
            version="001",
            name="first",
            checksum="abc",
            applied_at=datetime.now()
        ))

        status = self.service.get_migration_status()

        assert status["total_registered"] == 2
        assert status["total_applied"] == 1
        assert status["total_pending"] == 1
        assert status["last_applied"] == "001"

    def test_event_listener(self):
        """Test migration event listener."""
        events = []

        def listener(event_type, **kwargs):
            events.append((event_type, kwargs))

        self.service.add_listener(listener)

        migration = (
            MigrationBuilder("001", "test")
            .create_unique_constraint("User", "id")
            .build()
        )
        self.service.register_migration(migration)
        self.service.run_migration(migration)

        event_types = [e[0] for e in events]
        assert "migration_started" in event_types
        assert "operation_started" in event_types
        assert "operation_completed" in event_types
        assert "migration_completed" in event_types


# ============================================================
# Validation Tests
# ============================================================

class TestMigrationValidation:
    """Tests for migration validation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.driver = MockNeo4jDriver()
        self.service = KGSchemaMigrationService(driver=self.driver)

    def test_validate_missing_dependency(self):
        """Test validation catches missing dependencies."""
        self.service.register_migration(
            Migration(version="002", name="test", description="", operations=[], dependencies=["001"])
        )

        issues = self.service.validate_migrations()

        assert len(issues) == 1
        assert issues[0]["type"] == "missing_dependency"

    def test_validate_checksum_mismatch(self):
        """Test validation catches checksum mismatch."""
        migration = Migration(version="001", name="test", description="", operations=[
            MigrationOperation(
                operation_type=MigrationType.CREATE_INDEX,
                description="Index",
                up_cypher="CREATE INDEX original"
            )
        ])
        self.service.register_migration(migration)

        # Record with different checksum
        self.driver.record_migration(MigrationHistory(
            version="001",
            name="test",
            checksum="different_checksum",
            applied_at=datetime.now()
        ))

        issues = self.service.validate_migrations()

        assert any(i["type"] == "checksum_mismatch" for i in issues)

    def test_validate_circular_dependency(self):
        """Test validation catches circular dependencies."""
        self.service.register_migrations([
            Migration(version="001", name="a", description="", operations=[], dependencies=["002"]),
            Migration(version="002", name="b", description="", operations=[], dependencies=["001"]),
        ])

        issues = self.service.validate_migrations()

        assert any(i["type"] == "circular_dependency" for i in issues)

    def test_validate_no_issues(self):
        """Test validation with no issues."""
        self.service.register_migrations([
            Migration(version="001", name="first", description="", operations=[]),
            Migration(version="002", name="second", description="", operations=[], dependencies=["001"]),
        ])

        issues = self.service.validate_migrations()

        assert len(issues) == 0


# ============================================================
# Pre-built Migrations Tests
# ============================================================

class TestPrebuiltMigrations:
    """Tests for pre-built KG migrations."""

    def test_base_migrations_created(self):
        """Test base migrations are created."""
        migrations = create_kg_base_migrations()

        assert len(migrations) >= 6
        versions = [m.version for m in migrations]
        assert "001" in versions
        assert "002" in versions

    def test_base_migrations_have_valid_structure(self):
        """Test base migrations have valid structure."""
        migrations = create_kg_base_migrations()

        for migration in migrations:
            assert migration.version
            assert migration.name
            assert migration.checksum

    def test_base_migrations_dependencies_valid(self):
        """Test base migration dependencies are valid."""
        migrations = create_kg_base_migrations()
        versions = {m.version for m in migrations}

        for migration in migrations:
            for dep in migration.dependencies:
                assert dep in versions, f"Migration {migration.version} depends on unknown {dep}"


# ============================================================
# Singleton Tests
# ============================================================

class TestSingleton:
    """Tests for singleton accessor."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_migration_service()

    def test_get_migration_service(self):
        """Test getting migration service singleton."""
        service1 = get_migration_service()
        service2 = get_migration_service()

        assert service1 is service2

    def test_service_has_base_migrations(self):
        """Test service comes with base migrations."""
        service = get_migration_service()

        assert len(service._migrations) >= 6

    def test_reset_service(self):
        """Test resetting service creates new instance."""
        service1 = get_migration_service()
        reset_migration_service()
        service2 = get_migration_service()

        assert service1 is not service2


# ============================================================
# Schema Report Tests
# ============================================================

class TestSchemaReport:
    """Tests for schema report generation."""

    def test_generate_schema_report(self):
        """Test generating schema report."""
        driver = MockNeo4jDriver()
        service = KGSchemaMigrationService(driver=driver)

        # Apply a migration
        migration = (
            MigrationBuilder("001", "test")
            .create_unique_constraint("User", "id")
            .create_index("User", ["email"])
            .build()
        )
        service.register_migration(migration)
        service.run_migration(migration)

        report = service.generate_schema_report()

        assert "constraints" in report
        assert "indexes" in report
        assert report["migrations_applied"] == 1
        assert report["schema_version"] == "001"


# ============================================================
# Run Tests
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
