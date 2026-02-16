"""Tests for CDO-1: Data Lineage Tracking.

Tests cover:
- DataLineageRecord model (table structure, columns, indexes)
- Lineage schemas (Pydantic validation)
- Lineage service (record_lineage, get_fact_lineage, get_patient_lineage, get_lineage_summary)
- Lineage API router (endpoint structure)
- FHIR import lineage integration
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import pytest

from app.models.data_lineage import DataLineageRecord, SourceType


# =============================================================================
# 1. Model Tests
# =============================================================================


class TestDataLineageRecordModel:
    """Test DataLineageRecord SQLAlchemy model."""

    def test_model_inherits_base(self) -> None:
        """DataLineageRecord inherits from Base."""
        from app.core.database import Base

        assert issubclass(DataLineageRecord, Base)

    def test_tablename(self) -> None:
        """DataLineageRecord has correct table name."""
        assert DataLineageRecord.__tablename__ == "data_lineage"

    def test_has_required_columns(self) -> None:
        """DataLineageRecord has all required columns."""
        columns = DataLineageRecord.__table__.c
        required = [
            "id",
            "created_at",
            "clinical_fact_id",
            "source_type",
            "source_document_id",
            "source_resource_type",
            "source_resource_id",
            "extraction_method",
            "extraction_confidence",
            "transformation_chain",
        ]
        for col in required:
            assert col in columns, f"Missing column: {col}"

    def test_clinical_fact_id_is_foreign_key(self) -> None:
        """clinical_fact_id is a foreign key to clinical_facts."""
        col = DataLineageRecord.__table__.c.clinical_fact_id
        fk_targets = [fk.target_fullname for fk in col.foreign_keys]
        assert "clinical_facts.id" in fk_targets

    def test_source_document_id_is_nullable_foreign_key(self) -> None:
        """source_document_id is a nullable FK to documents."""
        col = DataLineageRecord.__table__.c.source_document_id
        assert col.nullable is True
        fk_targets = [fk.target_fullname for fk in col.foreign_keys]
        assert "documents.id" in fk_targets

    def test_clinical_fact_id_indexed(self) -> None:
        """clinical_fact_id column is indexed."""
        col = DataLineageRecord.__table__.c.clinical_fact_id
        assert col.index is True

    def test_source_type_not_nullable(self) -> None:
        """source_type column is not nullable."""
        col = DataLineageRecord.__table__.c.source_type
        assert col.nullable is False

    def test_extraction_confidence_nullable(self) -> None:
        """extraction_confidence is nullable (not all sources have confidence)."""
        col = DataLineageRecord.__table__.c.extraction_confidence
        assert col.nullable is True


# =============================================================================
# 2. SourceType Enum Tests
# =============================================================================


class TestSourceTypeEnum:
    """Test SourceType enum values."""

    def test_all_source_types_exist(self) -> None:
        """All expected source types are present."""
        expected = {"fhir_import", "nlp_extraction", "manual_entry", "derived", "external_api", "openehr_import"}
        actual = {st.value for st in SourceType}
        assert actual == expected

    def test_source_type_is_string_enum(self) -> None:
        """SourceType values are strings."""
        for st in SourceType:
            assert isinstance(st.value, str)


# =============================================================================
# 3. Schema Tests
# =============================================================================


class TestLineageSchemas:
    """Test Pydantic schemas for lineage."""

    def test_create_schema_minimal(self) -> None:
        """DataLineageRecordCreate with minimal fields."""
        from app.schemas.lineage import DataLineageRecordCreate, SourceType as SchemaSourceType

        record = DataLineageRecordCreate(
            clinical_fact_id=uuid4(),
            source_type=SchemaSourceType.FHIR_IMPORT,
        )
        assert record.source_type == SchemaSourceType.FHIR_IMPORT
        assert record.source_document_id is None
        assert record.extraction_method is None

    def test_create_schema_full(self) -> None:
        """DataLineageRecordCreate with all fields."""
        from app.schemas.lineage import DataLineageRecordCreate, SourceType as SchemaSourceType

        fact_id = uuid4()
        doc_id = uuid4()
        record = DataLineageRecordCreate(
            clinical_fact_id=fact_id,
            source_type=SchemaSourceType.NLP_EXTRACTION,
            source_document_id=doc_id,
            source_resource_type="Condition",
            source_resource_id="cond-123",
            extraction_method="nlp_transformer",
            extraction_confidence=0.87,
            transformation_chain=[{"step": "tokenize"}, {"step": "ner_extract"}],
        )
        assert record.clinical_fact_id == fact_id
        assert record.extraction_confidence == 0.87
        assert len(record.transformation_chain) == 2

    def test_response_schema_from_attributes(self) -> None:
        """DataLineageRecordResponse supports from_attributes."""
        from app.schemas.lineage import DataLineageRecordResponse

        assert DataLineageRecordResponse.model_config.get("from_attributes") is True

    def test_lineage_summary_schema(self) -> None:
        """LineageSummary can be constructed with valid data."""
        from app.schemas.lineage import LineageSourceDistribution, LineageSummary, SourceType as SchemaSourceType

        summary = LineageSummary(
            patient_id="P001",
            total_facts=10,
            source_distribution=[
                LineageSourceDistribution(
                    source_type=SchemaSourceType.FHIR_IMPORT,
                    count=7,
                    percentage=70.0,
                ),
                LineageSourceDistribution(
                    source_type=SchemaSourceType.NLP_EXTRACTION,
                    count=3,
                    percentage=30.0,
                ),
            ],
            avg_confidence=0.92,
            extraction_methods=["fhir_direct_mapping", "nlp_rule_based"],
        )
        assert summary.total_facts == 10
        assert len(summary.source_distribution) == 2
        assert summary.avg_confidence == 0.92

    def test_confidence_validation(self) -> None:
        """extraction_confidence must be between 0 and 1."""
        from app.schemas.lineage import DataLineageRecordCreate, SourceType as SchemaSourceType

        with pytest.raises(Exception):
            DataLineageRecordCreate(
                clinical_fact_id=uuid4(),
                source_type=SchemaSourceType.FHIR_IMPORT,
                extraction_confidence=1.5,
            )


# =============================================================================
# 4. API Router Tests
# =============================================================================


class TestLineageAPIRouter:
    """Test lineage API router registration and structure."""

    def test_router_exists(self) -> None:
        """Lineage router can be imported."""
        from app.api.lineage import router

        assert router is not None

    def test_router_prefix(self) -> None:
        """Lineage router has correct prefix."""
        from app.api.lineage import router

        assert router.prefix == "/lineage"

    def test_router_tags(self) -> None:
        """Lineage router has correct tags."""
        from app.api.lineage import router

        assert "lineage" in router.tags

    def test_router_has_fact_lineage_endpoint(self) -> None:
        """Router has GET /lineage/facts/{fact_id} endpoint."""
        from app.api.lineage import router

        paths = [route.path for route in router.routes]
        assert "/lineage/facts/{fact_id}" in paths

    def test_router_has_patient_lineage_endpoint(self) -> None:
        """Router has GET /lineage/patients/{patient_id} endpoint."""
        from app.api.lineage import router

        paths = [route.path for route in router.routes]
        assert "/lineage/patients/{patient_id}" in paths

    def test_router_has_patient_summary_endpoint(self) -> None:
        """Router has GET /lineage/patients/{patient_id}/summary endpoint."""
        from app.api.lineage import router

        paths = [route.path for route in router.routes]
        assert "/lineage/patients/{patient_id}/summary" in paths

    def test_router_registered_in_api_init(self) -> None:
        """Lineage router is exported from app.api."""
        from app.api import lineage_router

        assert lineage_router is not None


# =============================================================================
# 5. Migration Tests
# =============================================================================


class TestDataLineageMigration:
    """Test that the migration file is structurally correct."""

    def test_migration_revision_chain(self) -> None:
        """Migration 039 correctly follows 038."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "migration_039",
            "/Users/alexstinard/projects/brainstorm/jan-14-2026/backend/alembic/versions/039_add_data_lineage.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert module.revision == "039"
        assert module.down_revision == "038"

    def test_migration_has_upgrade_and_downgrade(self) -> None:
        """Migration has both upgrade() and downgrade() functions."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "migration_039",
            "/Users/alexstinard/projects/brainstorm/jan-14-2026/backend/alembic/versions/039_add_data_lineage.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert hasattr(module, "upgrade") and callable(module.upgrade)
        assert hasattr(module, "downgrade") and callable(module.downgrade)


# =============================================================================
# 6. Service Function Tests (unit-level, no DB)
# =============================================================================


class TestLineageServiceImports:
    """Test that lineage service functions can be imported and have correct signatures."""

    def test_record_lineage_importable(self) -> None:
        """record_lineage function exists and is async."""
        from app.services.lineage_service import record_lineage
        import asyncio

        assert asyncio.iscoroutinefunction(record_lineage)

    def test_get_fact_lineage_importable(self) -> None:
        """get_fact_lineage function exists and is async."""
        from app.services.lineage_service import get_fact_lineage
        import asyncio

        assert asyncio.iscoroutinefunction(get_fact_lineage)

    def test_get_patient_lineage_importable(self) -> None:
        """get_patient_lineage function exists and is async."""
        from app.services.lineage_service import get_patient_lineage
        import asyncio

        assert asyncio.iscoroutinefunction(get_patient_lineage)

    def test_get_lineage_summary_importable(self) -> None:
        """get_lineage_summary function exists and is async."""
        from app.services.lineage_service import get_lineage_summary
        import asyncio

        assert asyncio.iscoroutinefunction(get_lineage_summary)


# =============================================================================
# 7. FHIR Import Integration Tests
# =============================================================================


class TestFHIRImportLineageIntegration:
    """Test that FHIR import service is wired with lineage recording."""

    def test_fhir_import_has_lineage_helper(self) -> None:
        """FHIRImportService has _record_fhir_lineage method."""
        from app.services.fhir_import import FHIRImportService

        assert hasattr(FHIRImportService, "_record_fhir_lineage")
        import asyncio

        assert asyncio.iscoroutinefunction(FHIRImportService._record_fhir_lineage)

    def test_fhir_import_imports_lineage(self) -> None:
        """fhir_import module imports lineage dependencies."""
        import app.services.fhir_import as fhir_mod

        assert hasattr(fhir_mod, "record_lineage")
        assert hasattr(fhir_mod, "SourceType")


# =============================================================================
# 8. Model Registration Tests
# =============================================================================


class TestModelRegistration:
    """Test that DataLineageRecord is registered in models.__init__."""

    def test_model_in_models_init(self) -> None:
        """DataLineageRecord is importable from app.models."""
        from app.models import DataLineageRecord as DLR

        assert DLR is DataLineageRecord

    def test_source_type_in_models_init(self) -> None:
        """LineageSourceType is importable from app.models."""
        from app.models import LineageSourceType

        assert LineageSourceType is SourceType
