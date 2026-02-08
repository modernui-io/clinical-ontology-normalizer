"""Tests for ETL Validation Service (Dir-CI-3.4).

Validates the FHIR-to-OMOP ETL pipeline through:
- Round-trip validation (FHIR resource <-> ClinicalFact)
- Batch validation with mixed pass/fail
- Concept mapping accuracy checks
- Domain mismatch detection
- Duplicate fact detection
- Orphaned fact detection
- Missing field detection
- Value range violation detection
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.clinical_fact import ClinicalFact, FactEvidence
from app.schemas.base import Assertion, Domain, Experiencer, Temporality
from app.schemas.clinical_fact import EvidenceType
from app.schemas.etl_validation import ComparisonType
from app.services.etl_validation_service import ETLValidationService


# =============================================================================
# Custom DB fixtures -- create only the tables we need (avoids OMOP
# composite-primary-key issues with SQLite).
# =============================================================================


@pytest.fixture(scope="function")
async def _etl_engine():
    """Async SQLite engine that only creates ClinicalFact/FactEvidence tables."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    tables = [
        ClinicalFact.__table__,
        FactEvidence.__table__,
    ]

    async with engine.begin() as conn:
        for table in tables:
            await conn.run_sync(table.create)

    yield engine

    async with engine.begin() as conn:
        for table in reversed(tables):
            await conn.run_sync(table.drop)

    await engine.dispose()


@pytest.fixture(scope="function")
async def async_session(_etl_engine) -> AsyncGenerator[AsyncSession, None]:
    """Async session scoped to just the ETL validation tables."""
    factory = async_sessionmaker(
        _etl_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with factory() as session:
        yield session
        await session.rollback()


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def service() -> ETLValidationService:
    """Create an ETLValidationService instance."""
    return ETLValidationService()


@pytest.fixture
def fhir_condition() -> dict:
    """A FHIR Condition resource for Type 2 diabetes."""
    return {
        "resourceType": "Condition",
        "id": "cond-001",
        "subject": {"reference": "Patient/pat-001"},
        "code": {
            "coding": [
                {
                    "system": "http://snomed.info/sct",
                    "code": "44054006",
                    "display": "Type 2 diabetes mellitus",
                }
            ]
        },
        "clinicalStatus": {
            "coding": [{"code": "active"}]
        },
        "onsetDateTime": "2023-06-15",
    }


@pytest.fixture
def fact_from_condition() -> dict:
    """ClinicalFact corresponding to the fhir_condition fixture."""
    return {
        "id": str(uuid4()),
        "patient_id": "fhir-pat-001",
        "domain": "condition",
        "omop_concept_id": 44054006,
        "concept_name": "Type 2 diabetes mellitus",
        "assertion": "present",
        "temporality": "past",
        "experiencer": "patient",
        "confidence": 1.0,
        "value": None,
        "unit": None,
        "start_date": "2023-06-15T00:00:00+00:00",
        "end_date": None,
        "pipeline_version": "1.0.0-test",
    }


@pytest.fixture
def fhir_observation() -> dict:
    """A FHIR Observation resource for HbA1c."""
    return {
        "resourceType": "Observation",
        "id": "obs-001",
        "subject": {"reference": "Patient/pat-001"},
        "code": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": "4548-4",
                    "display": "Hemoglobin A1c",
                }
            ]
        },
        "status": "final",
        "effectiveDateTime": "2024-01-10",
        "valueQuantity": {
            "value": 7.2,
            "unit": "%",
        },
        "category": [
            {
                "coding": [{"code": "laboratory"}]
            }
        ],
    }


@pytest.fixture
def fact_from_observation() -> dict:
    """ClinicalFact corresponding to the fhir_observation fixture."""
    return {
        "id": str(uuid4()),
        "patient_id": "fhir-pat-001",
        "domain": "measurement",
        "omop_concept_id": 0,
        "concept_name": "Hemoglobin A1c",
        "assertion": "present",
        "temporality": "current",
        "experiencer": "patient",
        "confidence": 1.0,
        "value": "7.2",
        "unit": "%",
        "start_date": "2024-01-10T00:00:00+00:00",
        "end_date": None,
        "pipeline_version": "1.0.0-test",
    }


@pytest.fixture
def fhir_medication_request() -> dict:
    """A FHIR MedicationRequest resource for Metformin."""
    return {
        "resourceType": "MedicationRequest",
        "id": "med-001",
        "subject": {"reference": "Patient/pat-001"},
        "medicationCodeableConcept": {
            "coding": [
                {
                    "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                    "code": "860975",
                    "display": "Metformin 1000 MG",
                }
            ]
        },
        "status": "active",
        "authoredOn": "2023-06-15",
        "dosageInstruction": [{"text": "1000mg twice daily"}],
    }


@pytest.fixture
def fact_from_medication() -> dict:
    """ClinicalFact corresponding to the fhir_medication_request fixture."""
    return {
        "id": str(uuid4()),
        "patient_id": "fhir-pat-001",
        "domain": "drug",
        "omop_concept_id": 860975,
        "concept_name": "Metformin 1000 MG",
        "assertion": "present",
        "temporality": "current",
        "experiencer": "patient",
        "confidence": 1.0,
        "value": None,
        "unit": None,
        "start_date": "2023-06-15T00:00:00+00:00",
        "end_date": None,
        "pipeline_version": "1.0.0-test",
    }


@pytest.fixture
def fhir_procedure() -> dict:
    """A FHIR Procedure resource."""
    return {
        "resourceType": "Procedure",
        "id": "proc-001",
        "subject": {"reference": "Patient/pat-001"},
        "code": {
            "coding": [
                {
                    "system": "http://snomed.info/sct",
                    "code": "29303009",
                    "display": "Electrocardiogram",
                }
            ]
        },
        "status": "completed",
        "performedDateTime": "2024-02-20",
    }


@pytest.fixture
def fact_from_procedure() -> dict:
    """ClinicalFact corresponding to the fhir_procedure fixture."""
    return {
        "id": str(uuid4()),
        "patient_id": "fhir-pat-001",
        "domain": "procedure",
        "omop_concept_id": 29303009,
        "concept_name": "Electrocardiogram",
        "assertion": "present",
        "temporality": "past",
        "experiencer": "patient",
        "confidence": 1.0,
        "value": None,
        "unit": None,
        "start_date": "2024-02-20T00:00:00+00:00",
        "end_date": None,
        "pipeline_version": "1.0.0-test",
    }


@pytest.fixture
def fhir_allergy() -> dict:
    """A FHIR AllergyIntolerance resource."""
    return {
        "resourceType": "AllergyIntolerance",
        "id": "allergy-001",
        "patient": {"reference": "Patient/pat-001"},
        "code": {
            "coding": [
                {
                    "system": "http://snomed.info/sct",
                    "code": "7980",
                    "display": "Penicillin",
                }
            ]
        },
        "clinicalStatus": {
            "coding": [{"code": "active"}]
        },
        "criticality": "high",
        "category": ["medication"],
        "recordedDate": "2022-03-10",
    }


@pytest.fixture
def fact_from_allergy() -> dict:
    """ClinicalFact corresponding to the fhir_allergy fixture."""
    return {
        "id": str(uuid4()),
        "patient_id": "fhir-pat-001",
        "domain": "observation",
        "omop_concept_id": 7980,
        "concept_name": "Allergy to Penicillin",
        "assertion": "present",
        "temporality": "current",
        "experiencer": "patient",
        "confidence": 1.0,
        "value": None,
        "unit": None,
        "start_date": "2022-03-10T00:00:00+00:00",
        "end_date": None,
        "pipeline_version": "1.0.0-test",
    }


# =============================================================================
# Round-trip validation tests
# =============================================================================


class TestRoundTripValidation:
    """Test single resource round-trip validation."""

    def test_condition_round_trip_passes(
        self, service: ETLValidationService, fhir_condition: dict, fact_from_condition: dict
    ):
        """FHIR Condition -> ClinicalFact round-trip preserves all fields."""
        result = service.validate_etl_round_trip(fhir_condition, fact_from_condition)

        assert result.resource_type == "Condition"
        assert result.resource_id == "cond-001"
        assert result.overall_match is True
        assert len(result.issues) == 0

    def test_observation_round_trip_passes(
        self, service: ETLValidationService, fhir_observation: dict, fact_from_observation: dict
    ):
        """FHIR Observation -> ClinicalFact round-trip preserves value and unit."""
        result = service.validate_etl_round_trip(fhir_observation, fact_from_observation)

        assert result.resource_type == "Observation"
        assert result.overall_match is True

        # Verify value_quantity comparison exists and passes
        value_comp = next(
            (c for c in result.field_comparisons if c.field_name == "value_quantity"),
            None,
        )
        assert value_comp is not None
        assert value_comp.match is True

    def test_medication_round_trip_passes(
        self,
        service: ETLValidationService,
        fhir_medication_request: dict,
        fact_from_medication: dict,
    ):
        """FHIR MedicationRequest -> ClinicalFact round-trip passes."""
        result = service.validate_etl_round_trip(fhir_medication_request, fact_from_medication)

        assert result.resource_type == "MedicationRequest"
        assert result.overall_match is True

    def test_procedure_round_trip_passes(
        self,
        service: ETLValidationService,
        fhir_procedure: dict,
        fact_from_procedure: dict,
    ):
        """FHIR Procedure -> ClinicalFact round-trip passes."""
        result = service.validate_etl_round_trip(fhir_procedure, fact_from_procedure)

        assert result.resource_type == "Procedure"
        assert result.overall_match is True

    def test_allergy_round_trip_passes(
        self,
        service: ETLValidationService,
        fhir_allergy: dict,
        fact_from_allergy: dict,
    ):
        """FHIR AllergyIntolerance -> ClinicalFact preserves allergy with name prefix."""
        result = service.validate_etl_round_trip(fhir_allergy, fact_from_allergy)

        assert result.resource_type == "AllergyIntolerance"
        assert result.overall_match is True

    def test_concept_mapping_mismatch_detected(
        self, service: ETLValidationService, fhir_condition: dict
    ):
        """Detect concept mapping mismatch when OMOP concept_id doesn't match FHIR code."""
        bad_fact = {
            "patient_id": "fhir-pat-001",
            "domain": "condition",
            "omop_concept_id": 999999,  # Wrong concept ID
            "concept_name": "Type 2 diabetes mellitus",
            "assertion": "present",
            "start_date": "2023-06-15T00:00:00+00:00",
            "pipeline_version": "1.0.0",
        }
        result = service.validate_etl_round_trip(fhir_condition, bad_fact)

        assert result.overall_match is False
        concept_comp = next(
            c for c in result.field_comparisons if c.field_name == "concept_mapping"
        )
        assert concept_comp.match is False
        assert concept_comp.comparison_type == ComparisonType.MAPPED

    def test_date_mismatch_detected(
        self, service: ETLValidationService, fhir_condition: dict
    ):
        """Detect date mismatch when start_date doesn't match onsetDateTime."""
        bad_fact = {
            "patient_id": "fhir-pat-001",
            "domain": "condition",
            "omop_concept_id": 44054006,
            "concept_name": "Type 2 diabetes mellitus",
            "assertion": "present",
            "start_date": "2020-01-01T00:00:00+00:00",  # Wrong date
            "pipeline_version": "1.0.0",
        }
        result = service.validate_etl_round_trip(fhir_condition, bad_fact)

        assert result.overall_match is False
        date_comp = next(
            c for c in result.field_comparisons if c.field_name == "date"
        )
        assert date_comp.match is False

    def test_patient_reference_mismatch_detected(
        self, service: ETLValidationService, fhir_condition: dict
    ):
        """Detect patient reference mismatch."""
        bad_fact = {
            "patient_id": "wrong-patient",  # Doesn't match fhir-pat-001
            "domain": "condition",
            "omop_concept_id": 44054006,
            "concept_name": "Type 2 diabetes mellitus",
            "assertion": "present",
            "start_date": "2023-06-15T00:00:00+00:00",
            "pipeline_version": "1.0.0",
        }
        result = service.validate_etl_round_trip(fhir_condition, bad_fact)

        patient_comp = next(
            c for c in result.field_comparisons if c.field_name == "patient_reference"
        )
        assert patient_comp.match is False

    def test_value_quantity_mismatch_detected(
        self, service: ETLValidationService, fhir_observation: dict
    ):
        """Detect value mismatch when observation value differs."""
        bad_fact = {
            "patient_id": "fhir-pat-001",
            "domain": "measurement",
            "omop_concept_id": 0,
            "concept_name": "Hemoglobin A1c",
            "assertion": "present",
            "value": "9.5",  # Wrong value (source is 7.2)
            "unit": "%",
            "start_date": "2024-01-10T00:00:00+00:00",
            "pipeline_version": "1.0.0",
        }
        result = service.validate_etl_round_trip(fhir_observation, bad_fact)

        value_comp = next(
            c for c in result.field_comparisons if c.field_name == "value_quantity"
        )
        assert value_comp.match is False

    def test_domain_mismatch_detected(
        self, service: ETLValidationService, fhir_condition: dict
    ):
        """Detect domain mismatch when fact domain doesn't match resource type."""
        bad_fact = {
            "patient_id": "fhir-pat-001",
            "domain": "drug",  # Should be "condition"
            "omop_concept_id": 44054006,
            "concept_name": "Type 2 diabetes mellitus",
            "assertion": "present",
            "start_date": "2023-06-15T00:00:00+00:00",
            "pipeline_version": "1.0.0",
        }
        result = service.validate_etl_round_trip(fhir_condition, bad_fact)

        domain_comp = next(
            c for c in result.field_comparisons if c.field_name == "domain"
        )
        assert domain_comp.match is False

    def test_missing_provenance_detected(
        self, service: ETLValidationService, fhir_condition: dict
    ):
        """Detect missing pipeline_version provenance."""
        bad_fact = {
            "patient_id": "fhir-pat-001",
            "domain": "condition",
            "omop_concept_id": 44054006,
            "concept_name": "Type 2 diabetes mellitus",
            "assertion": "present",
            "start_date": "2023-06-15T00:00:00+00:00",
            "pipeline_version": None,  # Missing provenance
        }
        result = service.validate_etl_round_trip(fhir_condition, bad_fact)

        prov_comp = next(
            c for c in result.field_comparisons if c.field_name == "provenance"
        )
        assert prov_comp.match is False

    def test_observation_domain_allows_measurement(
        self, service: ETLValidationService, fhir_observation: dict, fact_from_observation: dict
    ):
        """Observation resource type should accept both observation and measurement domains."""
        # fact_from_observation has domain="measurement" -- should be accepted
        result = service.validate_etl_round_trip(fhir_observation, fact_from_observation)

        domain_comp = next(
            c for c in result.field_comparisons if c.field_name == "domain"
        )
        assert domain_comp.match is True


# =============================================================================
# Batch validation tests
# =============================================================================


class TestBatchValidation:
    """Test batch FHIR bundle validation."""

    def test_batch_all_pass(
        self,
        service: ETLValidationService,
        fhir_condition: dict,
        fact_from_condition: dict,
        fhir_observation: dict,
        fact_from_observation: dict,
    ):
        """Batch validation with all resources passing."""
        bundle = {
            "resourceType": "Bundle",
            "entry": [
                {"resource": {"resourceType": "Patient", "id": "pat-001"}},
                {"resource": fhir_condition},
                {"resource": fhir_observation},
            ],
        }
        facts = [fact_from_condition, fact_from_observation]

        result = service.validate_batch_etl(bundle, facts)

        assert result.total == 2  # Excludes Patient
        assert result.validated == 2
        assert result.passed == 2
        assert result.failed == 0
        assert result.success_rate == 1.0
        assert len(result.data_loss_fields) == 0

    def test_batch_mixed_pass_fail(
        self,
        service: ETLValidationService,
        fhir_condition: dict,
        fact_from_condition: dict,
        fhir_observation: dict,
    ):
        """Batch validation with some resources failing."""
        # Create a bad fact for the observation (wrong value)
        bad_obs_fact = {
            "patient_id": "fhir-pat-001",
            "domain": "measurement",
            "omop_concept_id": 0,
            "concept_name": "Hemoglobin A1c",
            "assertion": "present",
            "value": "99.9",  # Wrong value
            "unit": "mg/dL",  # Wrong unit
            "start_date": "2024-01-10T00:00:00+00:00",
            "pipeline_version": "1.0.0",
        }

        bundle = {
            "resourceType": "Bundle",
            "entry": [
                {"resource": {"resourceType": "Patient", "id": "pat-001"}},
                {"resource": fhir_condition},
                {"resource": fhir_observation},
            ],
        }
        facts = [fact_from_condition, bad_obs_fact]

        result = service.validate_batch_etl(bundle, facts)

        assert result.total == 2
        assert result.passed == 1
        assert result.failed == 1
        assert result.success_rate == 0.5
        assert "value_quantity" in result.data_loss_fields

    def test_batch_with_skipped_resources(
        self,
        service: ETLValidationService,
        fhir_condition: dict,
        fact_from_condition: dict,
    ):
        """Resources with no matching fact are skipped."""
        unmatched_obs = {
            "resourceType": "Observation",
            "id": "obs-999",
            "code": {
                "coding": [{"code": "12345", "display": "Some Unknown Lab"}]
            },
            "status": "final",
        }

        bundle = {
            "resourceType": "Bundle",
            "entry": [
                {"resource": {"resourceType": "Patient", "id": "pat-001"}},
                {"resource": fhir_condition},
                {"resource": unmatched_obs},
            ],
        }
        facts = [fact_from_condition]  # No fact for unmatched_obs

        result = service.validate_batch_etl(bundle, facts)

        assert result.total == 2
        assert result.validated == 1
        assert result.skipped == 1

    def test_batch_empty_bundle(self, service: ETLValidationService):
        """Empty bundle produces zero results."""
        bundle = {
            "resourceType": "Bundle",
            "entry": [
                {"resource": {"resourceType": "Patient", "id": "pat-001"}},
            ],
        }
        result = service.validate_batch_etl(bundle, [])

        assert result.total == 0
        assert result.validated == 0
        assert result.success_rate == 0.0


# =============================================================================
# Database-backed tests: concept mapping accuracy
# =============================================================================


class TestConceptMappingAccuracy:
    """Test concept mapping accuracy report using a real (test) database."""

    @pytest.mark.asyncio
    async def test_all_mapped(self, async_session: AsyncSession):
        """All facts with valid concept IDs should report 100% mapping rate."""
        # Create test facts
        for i in range(3):
            fact = ClinicalFact(
                patient_id="test-pat-001",
                domain=Domain.CONDITION,
                omop_concept_id=201826 + i,  # All valid (non-zero)
                concept_name=f"Test condition {i}",
                assertion=Assertion.PRESENT,
                temporality=Temporality.CURRENT,
                experiencer=Experiencer.PATIENT,
                confidence=1.0,
                pipeline_version="1.0.0",
            )
            async_session.add(fact)
        await async_session.flush()

        service = ETLValidationService()
        report = await service.validate_concept_mapping_accuracy(async_session)

        assert report.total_facts == 3
        assert report.mapped == 3
        assert report.unmapped == 0
        assert report.mapping_rate == 1.0

    @pytest.mark.asyncio
    async def test_some_unmapped(self, async_session: AsyncSession):
        """Mix of mapped and unmapped facts should report correct rate."""
        # 2 mapped
        for i in range(2):
            fact = ClinicalFact(
                patient_id="test-pat-001",
                domain=Domain.CONDITION,
                omop_concept_id=201826 + i,
                concept_name=f"Mapped condition {i}",
                assertion=Assertion.PRESENT,
                temporality=Temporality.CURRENT,
                experiencer=Experiencer.PATIENT,
                confidence=1.0,
                pipeline_version="1.0.0",
            )
            async_session.add(fact)

        # 1 unmapped (concept_id = 0)
        unmapped = ClinicalFact(
            patient_id="test-pat-001",
            domain=Domain.CONDITION,
            omop_concept_id=0,
            concept_name="Unmapped condition",
            assertion=Assertion.PRESENT,
            temporality=Temporality.CURRENT,
            experiencer=Experiencer.PATIENT,
            confidence=1.0,
            pipeline_version="1.0.0",
        )
        async_session.add(unmapped)
        await async_session.flush()

        service = ETLValidationService()
        report = await service.validate_concept_mapping_accuracy(async_session)

        assert report.total_facts == 3
        assert report.mapped == 2
        assert report.unmapped == 1
        assert abs(report.mapping_rate - 2 / 3) < 0.01

    @pytest.mark.asyncio
    async def test_empty_database(self, async_session: AsyncSession):
        """Empty database reports zero facts with 0.0 mapping rate."""
        service = ETLValidationService()
        report = await service.validate_concept_mapping_accuracy(async_session)

        assert report.total_facts == 0
        assert report.mapped == 0
        assert report.unmapped == 0
        assert report.mapping_rate == 0.0


# =============================================================================
# Database-backed tests: ETL quality checks
# =============================================================================


class TestETLQualityChecks:
    """Test ETL quality checks using a real (test) database."""

    @pytest.mark.asyncio
    async def test_detects_orphaned_facts(self, async_session: AsyncSession):
        """Facts without evidence records should be counted as orphaned."""
        # Create a fact with no evidence
        orphan = ClinicalFact(
            patient_id="test-pat-001",
            domain=Domain.CONDITION,
            omop_concept_id=201826,
            concept_name="Orphaned condition",
            assertion=Assertion.PRESENT,
            temporality=Temporality.CURRENT,
            experiencer=Experiencer.PATIENT,
            confidence=1.0,
            pipeline_version="1.0.0",
        )
        async_session.add(orphan)
        await async_session.flush()

        service = ETLValidationService()
        report = await service.run_etl_quality_checks(async_session)

        assert report.orphaned_count >= 1
        assert report.total_facts >= 1

    @pytest.mark.asyncio
    async def test_detects_duplicate_facts(self, async_session: AsyncSession):
        """Duplicate facts (same patient + concept + date) should be detected."""
        date = datetime(2024, 1, 15, tzinfo=timezone.utc)
        for _ in range(3):
            dup = ClinicalFact(
                patient_id="test-pat-dup",
                domain=Domain.CONDITION,
                omop_concept_id=201826,
                concept_name="Duplicate condition",
                assertion=Assertion.PRESENT,
                temporality=Temporality.CURRENT,
                experiencer=Experiencer.PATIENT,
                confidence=1.0,
                start_date=date,
                pipeline_version="1.0.0",
            )
            async_session.add(dup)
        await async_session.flush()

        service = ETLValidationService()
        report = await service.run_etl_quality_checks(async_session)

        assert report.duplicate_count >= 1
        # Find the specific duplicate group
        dup_group = next(
            (g for g in report.duplicate_groups if g.patient_id == "test-pat-dup"),
            None,
        )
        assert dup_group is not None
        assert dup_group.count == 3
        assert len(dup_group.fact_ids) == 3

    @pytest.mark.asyncio
    async def test_detects_missing_fields(self, async_session: AsyncSession):
        """Facts with empty concept_name should be detected as missing fields."""
        bad_fact = ClinicalFact(
            patient_id="test-pat-missing",
            domain=Domain.CONDITION,
            omop_concept_id=0,
            concept_name="",  # Missing required field
            assertion=Assertion.PRESENT,
            temporality=Temporality.CURRENT,
            experiencer=Experiencer.PATIENT,
            confidence=1.0,
            pipeline_version="1.0.0",
        )
        async_session.add(bad_fact)
        await async_session.flush()

        service = ETLValidationService()
        report = await service.run_etl_quality_checks(async_session)

        assert report.missing_fields_count >= 1
        entry = next(
            (e for e in report.missing_field_entries if e.patient_id == "test-pat-missing"),
            None,
        )
        assert entry is not None
        assert "concept_name" in entry.missing_fields

    @pytest.mark.asyncio
    async def test_detects_range_violations(self, async_session: AsyncSession):
        """Measurement values outside expected ranges should be flagged."""
        out_of_range = ClinicalFact(
            patient_id="test-pat-range",
            domain=Domain.MEASUREMENT,
            omop_concept_id=3004410,
            concept_name="Hemoglobin A1c",
            assertion=Assertion.PRESENT,
            temporality=Temporality.CURRENT,
            experiencer=Experiencer.PATIENT,
            confidence=1.0,
            value="50.0",  # Way outside [2.0, 20.0] range
            unit="%",
            pipeline_version="1.0.0",
        )
        async_session.add(out_of_range)
        await async_session.flush()

        service = ETLValidationService()
        report = await service.run_etl_quality_checks(async_session)

        assert report.range_violation_count >= 1
        violation = next(
            (v for v in report.range_violations if v.patient_id == "test-pat-range"),
            None,
        )
        assert violation is not None
        assert "50.0" in violation.reason or violation.value == "50.0"

    @pytest.mark.asyncio
    async def test_no_range_violation_for_valid_value(self, async_session: AsyncSession):
        """Values within expected ranges should not be flagged."""
        valid = ClinicalFact(
            patient_id="test-pat-valid",
            domain=Domain.MEASUREMENT,
            omop_concept_id=3004410,
            concept_name="Hemoglobin A1c",
            assertion=Assertion.PRESENT,
            temporality=Temporality.CURRENT,
            experiencer=Experiencer.PATIENT,
            confidence=1.0,
            value="7.2",  # Within [2.0, 20.0] range
            unit="%",
            pipeline_version="1.0.0",
        )
        async_session.add(valid)
        await async_session.flush()

        service = ETLValidationService()
        report = await service.run_etl_quality_checks(async_session)

        # This specific patient's values should not appear in violations
        violation = next(
            (v for v in report.range_violations if v.patient_id == "test-pat-valid"),
            None,
        )
        assert violation is None

    @pytest.mark.asyncio
    async def test_overall_quality_score(self, async_session: AsyncSession):
        """Quality score should be 1.0 when there are no issues."""
        # Create a clean fact with evidence
        fact = ClinicalFact(
            patient_id="test-pat-clean",
            domain=Domain.CONDITION,
            omop_concept_id=201826,
            concept_name="Clean condition",
            assertion=Assertion.PRESENT,
            temporality=Temporality.CURRENT,
            experiencer=Experiencer.PATIENT,
            confidence=1.0,
            pipeline_version="1.0.0",
        )
        async_session.add(fact)
        await async_session.flush()

        # Add evidence so it's not orphaned
        evidence = FactEvidence(
            fact_id=fact.id,
            evidence_type=EvidenceType.STRUCTURED,
            source_id=str(uuid4()),
            source_table="test_source",
            weight=1.0,
        )
        async_session.add(evidence)
        await async_session.flush()

        service = ETLValidationService()
        report = await service.run_etl_quality_checks(async_session)

        # With one clean fact and no issues, score should be 1.0
        assert report.overall_score == 1.0

    @pytest.mark.asyncio
    async def test_quality_score_degrades_with_issues(self, async_session: AsyncSession):
        """Quality score should decrease as issues accumulate."""
        # Create 10 clean facts
        fact_ids = []
        for i in range(10):
            fact = ClinicalFact(
                patient_id=f"test-pat-score-{i}",
                domain=Domain.CONDITION,
                omop_concept_id=201826 + i,
                concept_name=f"Score condition {i}",
                assertion=Assertion.PRESENT,
                temporality=Temporality.CURRENT,
                experiencer=Experiencer.PATIENT,
                confidence=1.0,
                pipeline_version="1.0.0",
            )
            async_session.add(fact)
            await async_session.flush()
            fact_ids.append(fact.id)

            evidence = FactEvidence(
                fact_id=fact.id,
                evidence_type=EvidenceType.STRUCTURED,
                source_id=str(uuid4()),
                source_table="test_source",
                weight=1.0,
            )
            async_session.add(evidence)

        # Add 2 orphaned facts (no evidence) to degrade score
        for i in range(2):
            orphan = ClinicalFact(
                patient_id=f"test-pat-orphan-{i}",
                domain=Domain.CONDITION,
                omop_concept_id=999990 + i,
                concept_name=f"Orphan {i}",
                assertion=Assertion.PRESENT,
                temporality=Temporality.CURRENT,
                experiencer=Experiencer.PATIENT,
                confidence=1.0,
                pipeline_version="1.0.0",
            )
            async_session.add(orphan)

        await async_session.flush()

        service = ETLValidationService()
        report = await service.run_etl_quality_checks(async_session)

        # 12 total facts, 2 orphaned -> score should be < 1.0
        assert report.total_facts == 12
        assert report.orphaned_count >= 2
        assert report.overall_score < 1.0


# =============================================================================
# API endpoint tests
# =============================================================================


class TestETLValidationAPI:
    """Test ETL validation API endpoints via test client."""

    def test_validate_resource_endpoint(self, sync_client, fhir_condition, fact_from_condition):
        """POST /data-quality/etl/validate-resource returns validation result."""
        response = sync_client.post(
            "/api/v1/data-quality/etl/validate-resource",
            json={
                "fhir_resource": fhir_condition,
                "clinical_fact": fact_from_condition,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["resource_type"] == "Condition"
        assert data["overall_match"] is True
        assert isinstance(data["field_comparisons"], list)

    def test_validate_batch_endpoint(
        self,
        sync_client,
        fhir_condition,
        fact_from_condition,
    ):
        """POST /data-quality/etl/validate-batch returns batch result."""
        bundle = {
            "resourceType": "Bundle",
            "entry": [
                {"resource": {"resourceType": "Patient", "id": "pat-001"}},
                {"resource": fhir_condition},
            ],
        }
        response = sync_client.post(
            "/api/v1/data-quality/etl/validate-batch",
            json={
                "fhir_bundle": bundle,
                "clinical_facts": [fact_from_condition],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["passed"] == 1

    def test_concept_accuracy_endpoint(self, sync_client):
        """GET /data-quality/etl/concept-accuracy returns mapping report."""
        response = sync_client.get("/api/v1/data-quality/etl/concept-accuracy")
        assert response.status_code == 200
        data = response.json()
        assert "total_facts" in data
        assert "mapping_rate" in data
        assert "mapped" in data
        assert "unmapped" in data

    def test_quality_checks_endpoint(self, sync_client):
        """GET /data-quality/etl/quality-checks returns quality report."""
        response = sync_client.get("/api/v1/data-quality/etl/quality-checks")
        assert response.status_code == 200
        data = response.json()
        assert "orphaned_count" in data
        assert "duplicate_count" in data
        assert "missing_fields_count" in data
        assert "overall_score" in data
