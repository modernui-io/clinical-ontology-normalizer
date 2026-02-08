"""Tests for CDO-3: OHDSI Data Quality Dashboard (DQD) checks.

Tests verify:
- Each completeness check (COMP-001 through COMP-004)
- Each conformance check (CONF-001 through CONF-004)
- Each plausibility check (PLAUS-001 through PLAUS-004)
- Overall report generation
- Threshold pass/warn/fail logic
- Behavior with empty data
- API endpoints
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool

if sys.version_info < (3, 10):
    pytest.skip("Tests require Python 3.10+", allow_module_level=True)

from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


@compiles(PG_ARRAY, "sqlite")
def _compile_array_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(PG_JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(PG_UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):
    return "VARCHAR(36)"


from app.core.database import Base, get_db
from app.models.clinical_fact import ClinicalFact
from app.models.vocabulary import Concept
from app.schemas.base import Assertion, Domain, Experiencer, Temporality
from app.schemas.dqd import DQDCategory, DQDStatus
from app.services.dqd_check_service import DQDCheckService, _determine_status


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
async def async_engine():
    """Create async SQLite engine for testing.

    Only creates the tables needed for DQD tests (clinical_facts, concepts)
    to avoid issues with OMOP tables that have composite primary keys
    incompatible with SQLite autoincrement.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    # Only create the tables we actually need for DQD tests
    tables_needed = [
        ClinicalFact.__table__,
        Concept.__table__,
    ]
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(
                sync_conn, tables=tables_needed
            )
        )
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.drop_all(
                sync_conn, tables=tables_needed
            )
        )
    await engine.dispose()


@pytest.fixture
async def session(async_engine):
    """Create async session for testing."""
    factory = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with factory() as sess:
        yield sess
        await sess.rollback()


@pytest.fixture
def service():
    """Create DQDCheckService instance."""
    return DQDCheckService()


def _make_fact(
    patient_id: str = "P001",
    domain: Domain = Domain.CONDITION,
    omop_concept_id: int = 12345,
    concept_name: str = "Type 2 Diabetes",
    assertion: Assertion = Assertion.PRESENT,
    temporality: Temporality = Temporality.CURRENT,
    experiencer: Experiencer = Experiencer.PATIENT,
    confidence: float = 1.0,
    value: str | None = None,
    unit: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> ClinicalFact:
    """Create a ClinicalFact for testing."""
    return ClinicalFact(
        id=str(uuid4()),
        patient_id=patient_id,
        domain=domain,
        omop_concept_id=omop_concept_id,
        concept_name=concept_name,
        assertion=assertion,
        temporality=temporality,
        experiencer=experiencer,
        confidence=confidence,
        value=value,
        unit=unit,
        start_date=start_date,
        end_date=end_date,
    )


def _make_concept(concept_id: int, concept_name: str, domain_id: str = "Condition") -> Concept:
    """Create a Concept for testing."""
    return Concept(
        id=str(uuid4()),
        concept_id=concept_id,
        concept_name=concept_name,
        domain_id=domain_id,
        vocabulary_id="SNOMED",
        concept_class_id="Clinical Finding",
    )


# =============================================================================
# Test _determine_status helper
# =============================================================================


class TestDetermineStatus:
    """Tests for the threshold status determination logic."""

    def test_pass_when_above_threshold(self):
        assert _determine_status(0.96, 0.95, 0.85) == DQDStatus.PASS

    def test_pass_when_equal_to_threshold(self):
        assert _determine_status(0.95, 0.95, 0.85) == DQDStatus.PASS

    def test_warn_when_between_thresholds(self):
        assert _determine_status(0.90, 0.95, 0.85) == DQDStatus.WARN

    def test_warn_when_equal_to_warn_threshold(self):
        assert _determine_status(0.85, 0.95, 0.85) == DQDStatus.WARN

    def test_fail_when_below_warn_threshold(self):
        assert _determine_status(0.50, 0.95, 0.85) == DQDStatus.FAIL

    def test_fail_at_zero(self):
        assert _determine_status(0.0, 0.95, 0.85) == DQDStatus.FAIL


# =============================================================================
# Test Check Definitions
# =============================================================================


class TestCheckDefinitions:
    """Tests for get_check_definitions."""

    def test_returns_all_definitions(self, service: DQDCheckService):
        defs = service.get_check_definitions()
        assert len(defs) == 12  # 4 completeness + 4 conformance + 4 plausibility

    def test_definitions_have_unique_ids(self, service: DQDCheckService):
        defs = service.get_check_definitions()
        ids = [d.check_id for d in defs]
        assert len(ids) == len(set(ids)), "Check IDs must be unique"

    def test_definitions_cover_all_categories(self, service: DQDCheckService):
        defs = service.get_check_definitions()
        categories = {d.category for d in defs}
        assert DQDCategory.COMPLETENESS in categories
        assert DQDCategory.CONFORMANCE in categories
        assert DQDCategory.PLAUSIBILITY in categories


# =============================================================================
# Test Completeness Checks
# =============================================================================


class TestCompletenessChecks:
    """Tests for COMP-001 through COMP-004."""

    @pytest.mark.asyncio
    async def test_comp001_all_patients_have_conditions(self, session, service):
        """All patients have condition facts -> PASS."""
        session.add(_make_fact("P001", Domain.CONDITION))
        session.add(_make_fact("P002", Domain.CONDITION))
        await session.flush()

        result = await service.run_check("COMP-001", session)
        assert result.check_id == "COMP-001"
        assert result.passed == 2
        assert result.failed == 0
        assert result.pass_rate == 1.0
        assert result.status == DQDStatus.PASS

    @pytest.mark.asyncio
    async def test_comp001_some_patients_without_conditions(self, session, service):
        """One patient has conditions, one has only measurements -> pass_rate = 0.5."""
        session.add(_make_fact("P001", Domain.CONDITION))
        session.add(_make_fact("P002", Domain.MEASUREMENT, concept_name="Glucose"))
        await session.flush()

        result = await service.run_check("COMP-001", session)
        assert result.passed == 1
        assert result.failed == 1
        assert result.total == 2
        assert result.pass_rate == 0.5
        # 0.5 < 0.6 (warn threshold) -> FAIL
        assert result.status == DQDStatus.FAIL

    @pytest.mark.asyncio
    async def test_comp002_patients_with_measurements(self, session, service):
        """All patients have measurements -> PASS."""
        session.add(_make_fact("P001", Domain.MEASUREMENT, concept_name="HbA1c"))
        session.add(_make_fact("P002", Domain.MEASUREMENT, concept_name="Glucose"))
        await session.flush()

        result = await service.run_check("COMP-002", session)
        assert result.passed == 2
        assert result.pass_rate == 1.0
        assert result.status == DQDStatus.PASS

    @pytest.mark.asyncio
    async def test_comp003_patients_with_demographics(self, session, service):
        """Patient with age observation -> counted as having demographics."""
        session.add(_make_fact("P001", Domain.CONDITION))
        session.add(
            _make_fact("P001", Domain.OBSERVATION, concept_name="Age", value="45")
        )
        await session.flush()

        result = await service.run_check("COMP-003", session)
        assert result.passed == 1
        assert result.total == 1
        assert result.status == DQDStatus.PASS

    @pytest.mark.asyncio
    async def test_comp003_no_demographics(self, session, service):
        """Patient without any demographic observations -> FAIL."""
        session.add(_make_fact("P001", Domain.CONDITION))
        session.add(_make_fact("P002", Domain.CONDITION))
        await session.flush()

        result = await service.run_check("COMP-003", session)
        assert result.passed == 0
        assert result.failed == 2
        assert result.status == DQDStatus.FAIL

    @pytest.mark.asyncio
    async def test_comp004_valid_concept_ids(self, session, service):
        """All facts have non-zero concept IDs -> PASS."""
        session.add(_make_fact("P001", omop_concept_id=12345))
        session.add(_make_fact("P002", omop_concept_id=67890))
        await session.flush()

        result = await service.run_check("COMP-004", session)
        assert result.passed == 2
        assert result.failed == 0
        assert result.status == DQDStatus.PASS

    @pytest.mark.asyncio
    async def test_comp004_zero_concept_id(self, session, service):
        """Fact with concept_id=0 -> counted as failure."""
        session.add(_make_fact("P001", omop_concept_id=12345))
        session.add(_make_fact("P002", omop_concept_id=0))
        await session.flush()

        result = await service.run_check("COMP-004", session)
        assert result.passed == 1
        assert result.failed == 1
        assert result.pass_rate == 0.5
        assert len(result.failing_examples) == 1
        assert result.failing_examples[0].value == "0"


# =============================================================================
# Test Conformance Checks
# =============================================================================


class TestConformanceChecks:
    """Tests for CONF-001 through CONF-004."""

    @pytest.mark.asyncio
    async def test_conf001_valid_concept_references(self, session, service):
        """Concept IDs that exist in concepts table -> PASS."""
        session.add(_make_concept(12345, "Type 2 Diabetes"))
        session.add(_make_fact("P001", omop_concept_id=12345))
        await session.flush()

        result = await service.run_check("CONF-001", session)
        assert result.passed == 1
        assert result.failed == 0
        assert result.status == DQDStatus.PASS

    @pytest.mark.asyncio
    async def test_conf001_invalid_concept_reference(self, session, service):
        """Concept ID not in concepts table -> failure."""
        session.add(_make_concept(12345, "Type 2 Diabetes"))
        session.add(_make_fact("P001", omop_concept_id=12345))
        session.add(_make_fact("P002", omop_concept_id=99999))  # Not in concepts table
        await session.flush()

        result = await service.run_check("CONF-001", session)
        assert result.passed == 1
        assert result.failed == 1
        assert len(result.failing_examples) == 1

    @pytest.mark.asyncio
    async def test_conf002_valid_date_range(self, session, service):
        """start_date <= end_date -> PASS."""
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 6, 1, tzinfo=timezone.utc)
        session.add(_make_fact("P001", start_date=start, end_date=end))
        await session.flush()

        result = await service.run_check("CONF-002", session)
        assert result.passed == 1
        assert result.failed == 0
        assert result.status == DQDStatus.PASS

    @pytest.mark.asyncio
    async def test_conf002_invalid_date_range(self, session, service):
        """start_date > end_date -> failure."""
        start = datetime(2024, 6, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, tzinfo=timezone.utc)
        session.add(_make_fact("P001", start_date=start, end_date=end))
        await session.flush()

        result = await service.run_check("CONF-002", session)
        assert result.passed == 0
        assert result.failed == 1
        assert result.status == DQDStatus.FAIL

    @pytest.mark.asyncio
    async def test_conf003_all_required_fields(self, session, service):
        """All required fields populated -> PASS."""
        session.add(_make_fact("P001", concept_name="Diabetes"))
        await session.flush()

        result = await service.run_check("CONF-003", session)
        assert result.passed == 1
        assert result.failed == 0
        assert result.status == DQDStatus.PASS

    @pytest.mark.asyncio
    async def test_conf003_empty_concept_name(self, session, service):
        """Empty concept_name -> failure."""
        session.add(_make_fact("P001", concept_name=""))
        await session.flush()

        result = await service.run_check("CONF-003", session)
        assert result.passed == 0
        assert result.failed == 1

    @pytest.mark.asyncio
    async def test_conf004_value_in_range(self, session, service):
        """HbA1c value within plausible range -> PASS."""
        session.add(
            _make_fact(
                "P001",
                domain=Domain.MEASUREMENT,
                concept_name="HbA1c",
                value="7.5",
            )
        )
        await session.flush()

        result = await service.run_check("CONF-004", session)
        assert result.passed == 1
        assert result.failed == 0
        assert result.status == DQDStatus.PASS

    @pytest.mark.asyncio
    async def test_conf004_value_out_of_range(self, session, service):
        """HbA1c value of 50% is implausible -> failure."""
        session.add(
            _make_fact(
                "P001",
                domain=Domain.MEASUREMENT,
                concept_name="HbA1c",
                value="50.0",
            )
        )
        await session.flush()

        result = await service.run_check("CONF-004", session)
        assert result.passed == 0
        assert result.failed == 1
        assert len(result.failing_examples) == 1

    @pytest.mark.asyncio
    async def test_conf004_non_numeric_value(self, session, service):
        """Non-numeric measurement value -> failure."""
        session.add(
            _make_fact(
                "P001",
                domain=Domain.MEASUREMENT,
                concept_name="Glucose",
                value="high",
            )
        )
        await session.flush()

        result = await service.run_check("CONF-004", session)
        assert result.failed == 1
        assert "Non-numeric" in result.failing_examples[0].reason


# =============================================================================
# Test Plausibility Checks
# =============================================================================


class TestPlausibilityChecks:
    """Tests for PLAUS-001 through PLAUS-004."""

    @pytest.mark.asyncio
    async def test_plaus001_no_future_dates(self, session, service):
        """All start_dates in the past -> PASS."""
        past = datetime(2024, 1, 1, tzinfo=timezone.utc)
        session.add(_make_fact("P001", start_date=past))
        await session.flush()

        result = await service.run_check("PLAUS-001", session)
        assert result.passed == 1
        assert result.failed == 0
        assert result.status == DQDStatus.PASS

    @pytest.mark.asyncio
    async def test_plaus001_future_date(self, session, service):
        """start_date in the future -> failure."""
        future = datetime.now(timezone.utc) + timedelta(days=365)
        session.add(_make_fact("P001", start_date=future))
        await session.flush()

        result = await service.run_check("PLAUS-001", session)
        assert result.passed == 0
        assert result.failed == 1
        assert result.status == DQDStatus.FAIL

    @pytest.mark.asyncio
    async def test_plaus002_correct_temporal_ordering(self, session, service):
        """Condition start before end -> PASS."""
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 6, 1, tzinfo=timezone.utc)
        session.add(
            _make_fact("P001", domain=Domain.CONDITION, start_date=start, end_date=end)
        )
        await session.flush()

        result = await service.run_check("PLAUS-002", session)
        assert result.passed == 1
        assert result.failed == 0
        assert result.status == DQDStatus.PASS

    @pytest.mark.asyncio
    async def test_plaus002_wrong_temporal_ordering(self, session, service):
        """Condition resolved before it started -> failure."""
        start = datetime(2024, 6, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, tzinfo=timezone.utc)
        session.add(
            _make_fact("P001", domain=Domain.CONDITION, start_date=start, end_date=end)
        )
        await session.flush()

        result = await service.run_check("PLAUS-002", session)
        assert result.passed == 0
        assert result.failed == 1

    @pytest.mark.asyncio
    async def test_plaus003_pediatric_condition_in_child(self, session, service):
        """Pediatric condition in patient with age < 18 -> PASS."""
        session.add(
            _make_fact(
                "P001",
                domain=Domain.CONDITION,
                concept_name="Neonatal jaundice",
            )
        )
        session.add(
            _make_fact(
                "P001",
                domain=Domain.OBSERVATION,
                concept_name="Age",
                value="0.5",
            )
        )
        await session.flush()

        result = await service.run_check("PLAUS-003", session)
        assert result.passed == 1
        assert result.failed == 0
        assert result.status == DQDStatus.PASS

    @pytest.mark.asyncio
    async def test_plaus003_pediatric_condition_in_adult(self, session, service):
        """Pediatric condition in patient with age >= 18 -> failure."""
        session.add(
            _make_fact(
                "P001",
                domain=Domain.CONDITION,
                concept_name="Neonatal jaundice",
            )
        )
        session.add(
            _make_fact(
                "P001",
                domain=Domain.OBSERVATION,
                concept_name="Age",
                value="45",
            )
        )
        await session.flush()

        result = await service.run_check("PLAUS-003", session)
        assert result.passed == 0
        assert result.failed == 1
        assert "Pediatric condition" in result.failing_examples[0].reason

    @pytest.mark.asyncio
    async def test_plaus004_male_condition_in_male(self, session, service):
        """Prostate condition in male patient -> PASS."""
        session.add(
            _make_fact(
                "P001",
                domain=Domain.CONDITION,
                concept_name="Benign prostatic hyperplasia",
            )
        )
        session.add(
            _make_fact(
                "P001",
                domain=Domain.OBSERVATION,
                concept_name="Sex",
                value="Male",
            )
        )
        await session.flush()

        result = await service.run_check("PLAUS-004", session)
        assert result.passed == 1
        assert result.failed == 0

    @pytest.mark.asyncio
    async def test_plaus004_male_condition_in_female(self, session, service):
        """Prostate condition in female patient -> failure."""
        session.add(
            _make_fact(
                "P001",
                domain=Domain.CONDITION,
                concept_name="Prostate cancer",
            )
        )
        session.add(
            _make_fact(
                "P001",
                domain=Domain.OBSERVATION,
                concept_name="Gender",
                value="Female",
            )
        )
        await session.flush()

        result = await service.run_check("PLAUS-004", session)
        assert result.passed == 0
        assert result.failed == 1
        assert "Male-specific" in result.failing_examples[0].reason


# =============================================================================
# Test Report Generation
# =============================================================================


class TestReportGeneration:
    """Tests for run_all_checks / DQDReport."""

    @pytest.mark.asyncio
    async def test_report_with_data(self, session, service):
        """Report generates successfully with some clinical data."""
        # Add patient with condition, measurement, and demographics
        session.add(_make_fact("P001", Domain.CONDITION, concept_name="Diabetes"))
        session.add(
            _make_fact("P001", Domain.MEASUREMENT, concept_name="HbA1c", value="7.0")
        )
        session.add(
            _make_fact("P001", Domain.OBSERVATION, concept_name="Age", value="55")
        )
        session.add(
            _make_fact("P001", Domain.OBSERVATION, concept_name="Sex", value="Male")
        )
        await session.flush()

        report = await service.run_all_checks(session)
        assert report.total_checks == 12
        assert report.passed + report.warned + report.failed == report.total_checks
        assert 0.0 <= report.overall_score <= 1.0
        assert len(report.results) == 12
        assert report.timestamp is not None

    @pytest.mark.asyncio
    async def test_report_empty_data(self, session, service):
        """Report with no data should return all checks with pass (empty = vacuously true)."""
        report = await service.run_all_checks(session)
        assert report.total_checks == 12
        # With no data, all checks return pass_rate=1.0 (vacuously true)
        for result in report.results:
            assert result.total == 0
            assert result.pass_rate == 1.0
            assert result.status == DQDStatus.PASS

    @pytest.mark.asyncio
    async def test_report_overall_score(self, session, service):
        """Overall score is fraction of checks that pass."""
        report = await service.run_all_checks(session)
        expected_score = report.passed / report.total_checks if report.total_checks > 0 else 0.0
        assert abs(report.overall_score - round(expected_score, 4)) < 0.001


# =============================================================================
# Test Unknown Check
# =============================================================================


class TestUnknownCheck:
    """Test error handling for unknown check IDs."""

    @pytest.mark.asyncio
    async def test_unknown_check_id_raises(self, session, service):
        """Running a non-existent check ID raises ValueError."""
        with pytest.raises(ValueError, match="Unknown check ID"):
            await service.run_check("INVALID-999", session)


# =============================================================================
# Test API Endpoints
# =============================================================================


class TestDQDAPIEndpoints:
    """Tests for the DQD REST API endpoints."""

    @pytest.fixture
    def app_and_client(self, async_engine):
        """Create test app with DQD router and override DB dependency."""
        from app.api.data_quality_dqd import router

        test_app = FastAPI()
        test_app.include_router(router)

        async def _override_db():
            factory = async_sessionmaker(
                async_engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            async with factory() as sess:
                yield sess

        test_app.dependency_overrides[get_db] = _override_db
        client = TestClient(test_app, raise_server_exceptions=False)
        return test_app, client

    def test_get_definitions(self, app_and_client):
        """GET /data-quality/dqd/definitions returns check definitions."""
        _, client = app_and_client
        resp = client.get("/data-quality/dqd/definitions")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 12
        assert all("check_id" in d for d in data)
        assert all("category" in d for d in data)

    def test_run_all_checks(self, app_and_client):
        """GET /data-quality/dqd returns a full report."""
        _, client = app_and_client
        resp = client.get("/data-quality/dqd")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_checks" in data
        assert "results" in data
        assert "overall_score" in data
        assert data["total_checks"] == 12

    def test_run_single_check(self, app_and_client):
        """GET /data-quality/dqd/COMP-001 returns a single check result."""
        _, client = app_and_client
        resp = client.get("/data-quality/dqd/COMP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["check_id"] == "COMP-001"
        assert "status" in data
        assert "pass_rate" in data

    def test_run_unknown_check(self, app_and_client):
        """GET /data-quality/dqd/INVALID-999 returns 404."""
        _, client = app_and_client
        resp = client.get("/data-quality/dqd/INVALID-999")
        assert resp.status_code == 404
