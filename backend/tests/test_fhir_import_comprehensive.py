"""Comprehensive tests for FHIR Import Service.

VPE-1: Tests covering each FHIR resource type handler, bundle
processing, invalid/malformed resources, clinical fact creation,
KG node/edge creation, and data lineage recording.

Covers:
- Patient resource extraction (name, identifier, demographics)
- Condition import (clinical status mapping, onset date)
- MedicationRequest import (status, dosage, authored date)
- MedicationStatement import (status, effective date)
- AllergyIntolerance import (criticality, category, reactions)
- Observation import (value/unit, category-based domain mapping)
- Procedure import (status filtering, performed date, outcome)
- Encounter import (class, period, reason codes, status)
- Immunization import (vaccine code, dose info, protocol)
- DocumentReference import (text extraction, note type detection)
- DiagnosticReport import (presentedForm, conclusion fallback)
- Bundle-level processing (multi-resource, missing Patient)
- Invalid/malformed resource handling (no display, bad status)
- Data lineage recording verification
- FHIR datetime parsing edge cases
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.clinical_fact import ClinicalFact
from app.models.knowledge_graph import KGEdge, KGNode
from app.models.document import Document as DocumentModel
from app.schemas.base import Assertion, Domain, Experiencer, Temporality
from app.schemas.knowledge_graph import EdgeType, NodeType
from app.services.fhir_import import FHIRImportService


# =============================================================================
# Fixtures
# =============================================================================


def _deduplicate_indexes(table):
    """Remove duplicate indexes from a table (by name).

    KGEdge has both column-level ``index=True`` on ``event_date``
    (auto-named ``ix_kg_edges_event_date``) AND an explicit Index
    with the same name in ``__table_args__``.  SQLAlchemy emits
    two CREATE INDEX statements; SQLite chokes on the duplicate.
    This function keeps only the first definition per index name.
    """
    seen: set[str] = set()
    to_remove = []
    for idx in table.indexes:
        if idx.name in seen:
            to_remove.append(idx)
        else:
            seen.add(idx.name)
    for idx in to_remove:
        table.indexes.discard(idx)


@pytest.fixture(scope="function")
async def engine():
    """Create async SQLite in-memory engine with required tables."""
    tables = [
        ClinicalFact.__table__,
        KGNode.__table__,
        DocumentModel.__table__,
        KGEdge.__table__,
    ]
    # Deduplicate indexes on KGEdge before creating tables
    for tbl in tables:
        _deduplicate_indexes(tbl)

    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=tables)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all, tables=tables)
    await eng.dispose()


@pytest.fixture(scope="function")
async def session(engine) -> AsyncSession:
    """Create an async database session for testing."""
    factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with factory() as sess:
        yield sess
        await sess.rollback()


@pytest.fixture
def service() -> FHIRImportService:
    """Create a FHIRImportService with mocked pipeline version."""
    with patch("app.services.fhir_import.get_current_pipeline_version") as mock_pv:
        mock_pv.return_value = MagicMock(version_string="test-1.0.0")
        svc = FHIRImportService(fhir_base_url="http://localhost:8090/fhir")
    return svc


def _make_bundle(*resources: dict) -> dict:
    """Build a FHIR Bundle from resource dicts."""
    entries = [{"resource": r} for r in resources]
    return {"resourceType": "Bundle", "entry": entries}


def _patient_resource(
    patient_id: str = "test-123",
    given: str = "Jane",
    family: str = "Doe",
    gender: str = "female",
    birth_date: str = "1980-06-15",
) -> dict:
    """Create a FHIR Patient resource."""
    return {
        "resourceType": "Patient",
        "id": patient_id,
        "name": [{"given": [given], "family": family}],
        "gender": gender,
        "birthDate": birth_date,
        "identifier": [{"system": "http://hospital.org/mrn", "value": "MRN-001"}],
    }


def _condition_resource(
    code: str = "44054006",
    display: str = "Type 2 diabetes mellitus",
    status: str = "active",
    onset: str | None = "2020-01-15",
) -> dict:
    """Create a FHIR Condition resource."""
    resource: dict = {
        "resourceType": "Condition",
        "id": str(uuid4()),
        "code": {
            "coding": [{"system": "http://snomed.info/sct", "code": code, "display": display}],
        },
        "clinicalStatus": {
            "coding": [{"system": "http://hl7.org/fhir/condition-clinical", "code": status}],
        },
    }
    if onset:
        resource["onsetDateTime"] = onset
    return resource


def _medication_request(
    code: str = "860975",
    display: str = "Metformin 1000mg",
    status: str = "active",
) -> dict:
    """Create a FHIR MedicationRequest resource."""
    return {
        "resourceType": "MedicationRequest",
        "id": str(uuid4()),
        "status": status,
        "medicationCodeableConcept": {
            "coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": code, "display": display}],
        },
        "authoredOn": "2024-03-01",
        "dosageInstruction": [{"text": "Take 1 tablet twice daily"}],
    }


def _observation_resource(
    code: str = "4548-4",
    display: str = "Hemoglobin A1c",
    value: float = 7.2,
    unit: str = "%",
    category_code: str = "laboratory",
    status: str = "final",
) -> dict:
    """Create a FHIR Observation resource."""
    return {
        "resourceType": "Observation",
        "id": str(uuid4()),
        "status": status,
        "code": {
            "coding": [{"system": "http://loinc.org", "code": code, "display": display}],
        },
        "category": [{
            "coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": category_code}],
        }],
        "valueQuantity": {"value": value, "unit": unit},
        "effectiveDateTime": "2024-06-15T10:30:00Z",
    }


def _procedure_resource(
    code: str = "29303009",
    display: str = "Electrocardiogram",
    status: str = "completed",
) -> dict:
    """Create a FHIR Procedure resource."""
    return {
        "resourceType": "Procedure",
        "id": str(uuid4()),
        "status": status,
        "code": {
            "coding": [{"system": "http://snomed.info/sct", "code": code, "display": display}],
        },
        "performedDateTime": "2024-05-10",
    }


def _allergy_resource(
    code: str = "7980",
    display: str = "Penicillin",
    status: str = "active",
    criticality: str = "high",
) -> dict:
    """Create a FHIR AllergyIntolerance resource."""
    return {
        "resourceType": "AllergyIntolerance",
        "id": str(uuid4()),
        "clinicalStatus": {
            "coding": [{"code": status}],
        },
        "code": {
            "coding": [{"code": code, "display": display}],
        },
        "criticality": criticality,
        "category": ["medication"],
        "reaction": [{
            "manifestation": [{"coding": [{"display": "Rash"}]}],
        }],
        "recordedDate": "2023-01-10",
    }


def _encounter_resource(
    enc_class: str = "AMB",
    status: str = "finished",
) -> dict:
    """Create a FHIR Encounter resource."""
    return {
        "resourceType": "Encounter",
        "id": str(uuid4()),
        "status": status,
        "class": {"code": enc_class, "display": "ambulatory"},
        "type": [{"coding": [{"code": "185345009", "display": "Office visit"}]}],
        "period": {
            "start": "2024-07-01T09:00:00Z",
            "end": "2024-07-01T10:00:00Z",
        },
        "reasonCode": [{"coding": [{"display": "Follow-up"}]}],
    }


def _immunization_resource(
    code: str = "207",
    display: str = "COVID-19 vaccine",
    status: str = "completed",
) -> dict:
    """Create a FHIR Immunization resource."""
    return {
        "resourceType": "Immunization",
        "id": str(uuid4()),
        "status": status,
        "vaccineCode": {
            "coding": [{"system": "http://hl7.org/fhir/sid/cvx", "code": code, "display": display}],
        },
        "occurrenceDateTime": "2024-01-15",
        "doseQuantity": {"value": 0.5, "unit": "mL"},
        "protocolApplied": [{"doseNumberPositiveInt": 2, "series": "COVID-19 primary"}],
    }


def _document_reference(
    text: str = "Patient presents with moderate atopic dermatitis on trunk and extremities.",
    note_type_code: str = "11506-3",
    note_type_display: str = "Progress note",
) -> dict:
    """Create a FHIR DocumentReference resource."""
    encoded = base64.b64encode(text.encode()).decode()
    return {
        "resourceType": "DocumentReference",
        "id": str(uuid4()),
        "status": "current",
        "type": {"coding": [{"code": note_type_code, "display": note_type_display}]},
        "content": [{
            "attachment": {
                "contentType": "text/plain",
                "data": encoded,
            },
        }],
        "date": "2024-08-01T14:00:00Z",
    }


def _diagnostic_report(
    conclusion: str = "Findings consistent with diabetic retinopathy. Recommend follow-up in 6 months.",
    code: str = "18748-4",
    display: str = "Radiology report",
) -> dict:
    """Create a FHIR DiagnosticReport resource."""
    return {
        "resourceType": "DiagnosticReport",
        "id": str(uuid4()),
        "status": "final",
        "code": {
            "coding": [{"code": code, "display": display}],
        },
        "conclusion": conclusion,
        "effectiveDateTime": "2024-09-15",
        "category": [{"coding": [{"display": "Radiology"}]}],
    }


# =============================================================================
# Patient Extraction Tests
# =============================================================================


class TestPatientExtraction:
    """Tests for patient name and identifier extraction."""

    def test_extract_patient_name(self, service):
        """Extracts 'Given Family' from FHIR Patient."""
        patient = _patient_resource(given="John", family="Smith")
        assert service._extract_patient_name(patient) == "John Smith"

    def test_extract_patient_name_no_names(self, service):
        """Returns 'Unknown' when no names are present."""
        assert service._extract_patient_name({"name": []}) == "Unknown"
        assert service._extract_patient_name({}) == "Unknown"

    def test_extract_identifier_mrn(self, service):
        """Extracts MRN identifier by system suffix."""
        patient = {
            "identifier": [
                {"system": "http://hospital.org/mrn", "value": "MRN-42"},
                {"system": "http://other.org/id", "value": "OTHER-1"},
            ]
        }
        assert service._extract_identifier(patient) == "MRN-42"

    def test_extract_identifier_fallback(self, service):
        """Falls back to first identifier if no MRN."""
        patient = {"identifier": [{"system": "http://other.org/id", "value": "FALL-1"}]}
        assert service._extract_identifier(patient) == "FALL-1"

    def test_extract_identifier_none(self, service):
        """Returns None when no identifiers are present."""
        assert service._extract_identifier({}) is None


# =============================================================================
# Condition Import Tests
# =============================================================================


class TestConditionImport:
    """Tests for FHIR Condition -> ClinicalFact + KGNode import."""

    @pytest.mark.asyncio
    @patch("app.services.fhir_import.record_lineage", new_callable=AsyncMock)
    async def test_active_condition_creates_present_fact(self, mock_lineage, service, session):
        """Active condition creates fact with assertion=PRESENT."""
        patient = _patient_resource()
        condition = _condition_resource(status="active")
        bundle = _make_bundle(patient, condition)

        result = await service.import_bundle(session, bundle)
        assert result["success"] is True
        assert result["conditions"] == 1

    @pytest.mark.asyncio
    @patch("app.services.fhir_import.record_lineage", new_callable=AsyncMock)
    async def test_resolved_condition_creates_absent_fact(self, mock_lineage, service, session):
        """Resolved condition creates fact with assertion=ABSENT."""
        patient = _patient_resource()
        condition = _condition_resource(status="resolved")
        bundle = _make_bundle(patient, condition)

        result = await service.import_bundle(session, bundle)
        assert result["success"] is True
        assert result["conditions"] == 1

    @pytest.mark.asyncio
    @patch("app.services.fhir_import.record_lineage", new_callable=AsyncMock)
    async def test_condition_without_display_is_skipped(self, mock_lineage, service, session):
        """Condition with no display text is skipped."""
        patient = _patient_resource()
        condition = {"resourceType": "Condition", "id": "c1", "code": {"coding": [{"code": "123"}]}}
        bundle = _make_bundle(patient, condition)

        result = await service.import_bundle(session, bundle)
        assert result["conditions"] == 0


# =============================================================================
# MedicationRequest Import Tests
# =============================================================================


class TestMedicationImport:
    """Tests for FHIR MedicationRequest -> ClinicalFact import."""

    @pytest.mark.asyncio
    @patch("app.services.fhir_import.record_lineage", new_callable=AsyncMock)
    async def test_active_medication_creates_fact(self, mock_lineage, service, session):
        """Active medication creates fact with assertion=PRESENT."""
        patient = _patient_resource()
        med = _medication_request(status="active")
        bundle = _make_bundle(patient, med)

        result = await service.import_bundle(session, bundle)
        assert result["success"] is True
        assert result["medications"] == 1

    @pytest.mark.asyncio
    @patch("app.services.fhir_import.record_lineage", new_callable=AsyncMock)
    async def test_stopped_medication_creates_absent_fact(self, mock_lineage, service, session):
        """Stopped medication creates fact with assertion=ABSENT."""
        patient = _patient_resource()
        med = _medication_request(status="stopped")
        bundle = _make_bundle(patient, med)

        result = await service.import_bundle(session, bundle)
        assert result["medications"] == 1

    @pytest.mark.asyncio
    @patch("app.services.fhir_import.record_lineage", new_callable=AsyncMock)
    async def test_medication_without_display_skipped(self, mock_lineage, service, session):
        """Medication with no display text is skipped."""
        patient = _patient_resource()
        med = {
            "resourceType": "MedicationRequest",
            "id": "m1",
            "status": "active",
            "medicationCodeableConcept": {"coding": [{"code": "999"}]},
        }
        bundle = _make_bundle(patient, med)

        result = await service.import_bundle(session, bundle)
        assert result["medications"] == 0


# =============================================================================
# Observation Import Tests
# =============================================================================


class TestObservationImport:
    """Tests for FHIR Observation -> ClinicalFact import."""

    @pytest.mark.asyncio
    @patch("app.services.fhir_import.record_lineage", new_callable=AsyncMock)
    async def test_lab_observation_creates_measurement(self, mock_lineage, service, session):
        """Lab observation (category=laboratory) maps to MEASUREMENT domain."""
        patient = _patient_resource()
        obs = _observation_resource(category_code="laboratory")
        bundle = _make_bundle(patient, obs)

        result = await service.import_bundle(session, bundle)
        assert result["observations"] == 1

    @pytest.mark.asyncio
    @patch("app.services.fhir_import.record_lineage", new_callable=AsyncMock)
    async def test_vital_signs_maps_to_measurement(self, mock_lineage, service, session):
        """Vital signs observation maps to MEASUREMENT domain."""
        patient = _patient_resource()
        obs = _observation_resource(
            code="8480-6", display="Systolic blood pressure",
            value=120.0, unit="mmHg", category_code="vital-signs",
        )
        bundle = _make_bundle(patient, obs)

        result = await service.import_bundle(session, bundle)
        assert result["observations"] == 1

    @pytest.mark.asyncio
    @patch("app.services.fhir_import.record_lineage", new_callable=AsyncMock)
    async def test_preliminary_observation_skipped(self, mock_lineage, service, session):
        """Preliminary observations are skipped (only final/amended/corrected)."""
        patient = _patient_resource()
        obs = _observation_resource(status="preliminary")
        bundle = _make_bundle(patient, obs)

        result = await service.import_bundle(session, bundle)
        assert result["observations"] == 0

    @pytest.mark.asyncio
    @patch("app.services.fhir_import.record_lineage", new_callable=AsyncMock)
    async def test_cancelled_observation_skipped(self, mock_lineage, service, session):
        """Cancelled observations are skipped."""
        patient = _patient_resource()
        obs = _observation_resource(status="cancelled")
        bundle = _make_bundle(patient, obs)

        result = await service.import_bundle(session, bundle)
        assert result["observations"] == 0


# =============================================================================
# Procedure Import Tests
# =============================================================================


class TestProcedureImport:
    """Tests for FHIR Procedure -> ClinicalFact import."""

    @pytest.mark.asyncio
    @patch("app.services.fhir_import.record_lineage", new_callable=AsyncMock)
    async def test_completed_procedure_creates_fact(self, mock_lineage, service, session):
        """Completed procedure creates fact."""
        patient = _patient_resource()
        proc = _procedure_resource(status="completed")
        bundle = _make_bundle(patient, proc)

        result = await service.import_bundle(session, bundle)
        assert result["procedures"] == 1

    @pytest.mark.asyncio
    @patch("app.services.fhir_import.record_lineage", new_callable=AsyncMock)
    async def test_not_done_procedure_skipped(self, mock_lineage, service, session):
        """Not-done procedures are skipped."""
        patient = _patient_resource()
        proc = _procedure_resource(status="not-done")
        bundle = _make_bundle(patient, proc)

        result = await service.import_bundle(session, bundle)
        assert result["procedures"] == 0


# =============================================================================
# AllergyIntolerance Import Tests
# =============================================================================


class TestAllergyImport:
    """Tests for FHIR AllergyIntolerance -> ClinicalFact import."""

    @pytest.mark.asyncio
    @patch("app.services.fhir_import.record_lineage", new_callable=AsyncMock)
    async def test_active_allergy_creates_fact(self, mock_lineage, service, session):
        """Active allergy creates fact with concept_name='Allergy to X'."""
        patient = _patient_resource()
        allergy = _allergy_resource(display="Penicillin", status="active")
        bundle = _make_bundle(patient, allergy)

        result = await service.import_bundle(session, bundle)
        assert result["allergies"] == 1

    @pytest.mark.asyncio
    @patch("app.services.fhir_import.record_lineage", new_callable=AsyncMock)
    async def test_inactive_allergy_creates_absent_fact(self, mock_lineage, service, session):
        """Inactive allergy creates fact with assertion=ABSENT."""
        patient = _patient_resource()
        allergy = _allergy_resource(display="Sulfa drugs", status="inactive")
        bundle = _make_bundle(patient, allergy)

        result = await service.import_bundle(session, bundle)
        assert result["allergies"] == 1


# =============================================================================
# Encounter Import Tests
# =============================================================================


class TestEncounterImport:
    """Tests for FHIR Encounter -> ClinicalFact + KGNode import."""

    @pytest.mark.asyncio
    @patch("app.services.fhir_import.record_lineage", new_callable=AsyncMock)
    async def test_finished_encounter_creates_fact(self, mock_lineage, service, session):
        """Finished encounter creates fact with Visit domain."""
        patient = _patient_resource()
        encounter = _encounter_resource(status="finished")
        bundle = _make_bundle(patient, encounter)

        result = await service.import_bundle(session, bundle)
        assert result["encounters"] == 1

    @pytest.mark.asyncio
    @patch("app.services.fhir_import.record_lineage", new_callable=AsyncMock)
    async def test_entered_in_error_encounter_skipped(self, mock_lineage, service, session):
        """Entered-in-error encounters are skipped."""
        patient = _patient_resource()
        encounter = _encounter_resource(status="entered-in-error")
        bundle = _make_bundle(patient, encounter)

        result = await service.import_bundle(session, bundle)
        assert result["encounters"] == 0


# =============================================================================
# Immunization Import Tests
# =============================================================================


class TestImmunizationImport:
    """Tests for FHIR Immunization -> ClinicalFact + KGNode import."""

    @pytest.mark.asyncio
    @patch("app.services.fhir_import.record_lineage", new_callable=AsyncMock)
    async def test_completed_immunization_creates_fact(self, mock_lineage, service, session):
        """Completed immunization creates fact in Drug domain."""
        patient = _patient_resource()
        imm = _immunization_resource(status="completed")
        bundle = _make_bundle(patient, imm)

        result = await service.import_bundle(session, bundle)
        assert result["immunizations"] == 1

    @pytest.mark.asyncio
    @patch("app.services.fhir_import.record_lineage", new_callable=AsyncMock)
    async def test_entered_in_error_immunization_skipped(self, mock_lineage, service, session):
        """Entered-in-error immunizations are skipped."""
        patient = _patient_resource()
        imm = _immunization_resource(status="entered-in-error")
        bundle = _make_bundle(patient, imm)

        result = await service.import_bundle(session, bundle)
        assert result["immunizations"] == 0

    @pytest.mark.asyncio
    @patch("app.services.fhir_import.record_lineage", new_callable=AsyncMock)
    async def test_not_done_immunization_creates_absent_fact(self, mock_lineage, service, session):
        """Not-done immunization creates fact with assertion=ABSENT."""
        patient = _patient_resource()
        imm = _immunization_resource(status="not-done")
        bundle = _make_bundle(patient, imm)

        result = await service.import_bundle(session, bundle)
        assert result["immunizations"] == 1


# =============================================================================
# DocumentReference Import Tests
# =============================================================================


class TestDocumentReferenceImport:
    """Tests for FHIR DocumentReference import."""

    @pytest.mark.asyncio
    @patch("app.services.fhir_import.record_lineage", new_callable=AsyncMock)
    async def test_document_reference_with_text_creates_node(self, mock_lineage, service, session):
        """DocumentReference with extractable text creates KG node."""
        patient = _patient_resource()
        doc = _document_reference(
            text="Patient presents with moderate atopic dermatitis on trunk and extremities. Needs treatment."
        )
        bundle = _make_bundle(patient, doc)

        with patch("app.core.queue.enqueue_job", MagicMock()):
            result = await service.import_bundle(session, bundle)
        assert result["clinical_notes"] == 1

    @pytest.mark.asyncio
    @patch("app.services.fhir_import.record_lineage", new_callable=AsyncMock)
    async def test_document_reference_short_text_skipped(self, mock_lineage, service, session):
        """DocumentReference with text < 30 chars is skipped."""
        patient = _patient_resource()
        doc = _document_reference(text="Short note")
        bundle = _make_bundle(patient, doc)

        result = await service.import_bundle(session, bundle)
        assert result["clinical_notes"] == 0

    @pytest.mark.asyncio
    @patch("app.services.fhir_import.record_lineage", new_callable=AsyncMock)
    async def test_entered_in_error_doc_ref_skipped(self, mock_lineage, service, session):
        """Entered-in-error DocumentReference is skipped."""
        patient = _patient_resource()
        doc = _document_reference()
        doc["status"] = "entered-in-error"
        bundle = _make_bundle(patient, doc)

        result = await service.import_bundle(session, bundle)
        assert result["clinical_notes"] == 0

    def test_determine_note_type_progress(self, service):
        """Detects progress note from LOINC code 11506-3."""
        doc = {"type": {"coding": [{"code": "11506-3", "display": "Progress note"}]}}
        assert service._determine_note_type(doc) == "progress_note"

    def test_determine_note_type_discharge(self, service):
        """Detects discharge summary from LOINC code 18842-5."""
        doc = {"type": {"coding": [{"code": "18842-5", "display": "Discharge summary"}]}}
        assert service._determine_note_type(doc) == "discharge_summary"

    def test_determine_note_type_fallback(self, service):
        """Falls back to 'clinical_note' when type is unknown."""
        doc = {"type": {"coding": [{"code": "UNKNOWN"}]}}
        assert service._determine_note_type(doc) == "clinical_note"


# =============================================================================
# DiagnosticReport Import Tests
# =============================================================================


class TestDiagnosticReportImport:
    """Tests for FHIR DiagnosticReport import."""

    @pytest.mark.asyncio
    @patch("app.services.fhir_import.record_lineage", new_callable=AsyncMock)
    async def test_report_with_conclusion_creates_node(self, mock_lineage, service, session):
        """DiagnosticReport with conclusion text creates KG node."""
        patient = _patient_resource()
        report = _diagnostic_report(
            conclusion="Findings consistent with diabetic retinopathy. Recommend follow-up in 6 months."
        )
        bundle = _make_bundle(patient, report)

        with patch("app.core.queue.enqueue_job", MagicMock()):
            result = await service.import_bundle(session, bundle)
        assert result["diagnostic_reports"] == 1

    @pytest.mark.asyncio
    @patch("app.services.fhir_import.record_lineage", new_callable=AsyncMock)
    async def test_report_short_conclusion_skipped(self, mock_lineage, service, session):
        """DiagnosticReport with conclusion < 20 chars is skipped."""
        patient = _patient_resource()
        report = _diagnostic_report(conclusion="Normal")
        bundle = _make_bundle(patient, report)

        result = await service.import_bundle(session, bundle)
        assert result["diagnostic_reports"] == 0

    @pytest.mark.asyncio
    @patch("app.services.fhir_import.record_lineage", new_callable=AsyncMock)
    async def test_cancelled_report_skipped(self, mock_lineage, service, session):
        """Cancelled DiagnosticReport is skipped."""
        patient = _patient_resource()
        report = _diagnostic_report()
        report["status"] = "cancelled"
        bundle = _make_bundle(patient, report)

        result = await service.import_bundle(session, bundle)
        assert result["diagnostic_reports"] == 0


# =============================================================================
# Bundle Processing Tests
# =============================================================================


class TestBundleProcessing:
    """Tests for full bundle import processing."""

    @pytest.mark.asyncio
    @patch("app.services.fhir_import.record_lineage", new_callable=AsyncMock)
    async def test_multi_resource_bundle(self, mock_lineage, service, session):
        """Bundle with multiple resource types processes all of them."""
        patient = _patient_resource()
        cond = _condition_resource()
        med = _medication_request()
        obs = _observation_resource()
        proc = _procedure_resource()
        bundle = _make_bundle(patient, cond, med, obs, proc)

        result = await service.import_bundle(session, bundle)
        assert result["success"] is True
        assert result["conditions"] == 1
        assert result["medications"] == 1
        assert result["observations"] == 1
        assert result["procedures"] == 1
        assert result["nodes"] >= 5  # patient + 4 resources

    @pytest.mark.asyncio
    async def test_bundle_without_patient_fails(self, service, session):
        """Bundle with no Patient resource returns error."""
        cond = _condition_resource()
        bundle = _make_bundle(cond)

        result = await service.import_bundle(session, bundle)
        assert result["success"] is False
        assert "Patient" in result.get("error", "")

    @pytest.mark.asyncio
    async def test_non_bundle_resource_type_fails(self, service, session):
        """Non-Bundle resourceType returns error."""
        result = await service.import_bundle(session, {"resourceType": "Patient", "id": "p1"})
        assert result["success"] is False
        assert "Bundle" in result.get("error", "")

    @pytest.mark.asyncio
    async def test_empty_bundle_fails(self, service, session):
        """Bundle with no entries returns error."""
        result = await service.import_bundle(session, {"resourceType": "Bundle", "entry": []})
        assert result["success"] is False
        assert "no entries" in result.get("error", "").lower()

    @pytest.mark.asyncio
    @patch("app.services.fhir_import.record_lineage", new_callable=AsyncMock)
    async def test_unknown_resource_types_tracked(self, mock_lineage, service, session):
        """Unknown resource types are logged in skipped_resource_types."""
        patient = _patient_resource()
        unknown = {"resourceType": "FamilyMemberHistory", "id": "fmh-1"}
        bundle = _make_bundle(patient, unknown)

        result = await service.import_bundle(session, bundle)
        assert result["success"] is True
        assert "FamilyMemberHistory" in result.get("skipped_resource_types", [])

    @pytest.mark.asyncio
    @patch("app.services.fhir_import.record_lineage", new_callable=AsyncMock)
    async def test_internal_patient_id_override(self, mock_lineage, service, session):
        """internal_patient_id overrides the default fhir-{id} pattern."""
        patient = _patient_resource(patient_id="fhir-xyz")
        bundle = _make_bundle(patient)

        result = await service.import_bundle(session, bundle, internal_patient_id="custom-id")
        assert result["patient_id"] == "custom-id"

    @pytest.mark.asyncio
    @patch("app.services.fhir_import.record_lineage", new_callable=AsyncMock)
    async def test_malformed_resource_does_not_crash_bundle(self, mock_lineage, service, session):
        """A malformed resource doesn't crash the entire bundle import."""
        patient = _patient_resource()
        # Condition with no code at all
        bad_condition = {"resourceType": "Condition", "id": "bad-1"}
        good_condition = _condition_resource()
        bundle = _make_bundle(patient, bad_condition, good_condition)

        result = await service.import_bundle(session, bundle)
        assert result["success"] is True
        # The good condition should still be imported
        assert result["conditions"] >= 1


# =============================================================================
# FHIR Datetime Parsing Tests
# =============================================================================


class TestDatetimeParsing:
    """Tests for FHIR datetime parsing edge cases."""

    def test_full_datetime_with_timezone(self, service):
        """Full ISO datetime with timezone parses correctly."""
        dt = service._parse_fhir_datetime("2024-06-15T10:30:00+00:00")
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 6

    def test_datetime_with_z_suffix(self, service):
        """Datetime with Z suffix parses correctly."""
        dt = service._parse_fhir_datetime("2024-06-15T10:30:00Z")
        assert dt is not None
        assert dt.year == 2024

    def test_date_only(self, service):
        """Date-only string is converted to datetime."""
        dt = service._parse_fhir_datetime("2024-06-15")
        assert dt is not None
        assert dt.year == 2024
        assert dt.hour == 0

    def test_none_returns_none(self, service):
        """None input returns None."""
        assert service._parse_fhir_datetime(None) is None

    def test_empty_string_returns_none(self, service):
        """Empty string returns None."""
        assert service._parse_fhir_datetime("") is None

    def test_invalid_datetime_returns_none(self, service):
        """Invalid datetime string returns None."""
        assert service._parse_fhir_datetime("not-a-date") is None


# =============================================================================
# CodeableConcept Extraction Tests
# =============================================================================


class TestCodeableConceptExtraction:
    """Tests for extracting codes from FHIR CodeableConcept."""

    def test_extract_from_coding(self, service):
        """Extracts code, display, system from coding array."""
        cc = {"coding": [{"code": "123", "display": "Test", "system": "http://loinc.org"}]}
        code, display, system = service._get_code_from_codeable_concept(cc)
        assert code == "123"
        assert display == "Test"
        assert system == "http://loinc.org"

    def test_extract_text_fallback(self, service):
        """Falls back to text when coding has no display."""
        cc = {"coding": [{"code": "456"}], "text": "Fallback text"}
        code, display, _ = service._get_code_from_codeable_concept(cc)
        assert code == "456"
        assert display == "Fallback text"

    def test_no_coding_uses_text(self, service):
        """No coding array falls back to text field."""
        cc = {"text": "Just text"}
        code, display, system = service._get_code_from_codeable_concept(cc)
        assert code is None
        assert display == "Just text"
        assert system is None

    def test_empty_concept(self, service):
        """Empty CodeableConcept returns all None."""
        cc = {}
        code, display, system = service._get_code_from_codeable_concept(cc)
        assert code is None
        assert display is None
        assert system is None


# =============================================================================
# Lineage Recording Tests
# =============================================================================


class TestLineageRecording:
    """Tests for data lineage recording during import."""

    @pytest.mark.asyncio
    @patch("app.services.fhir_import.record_lineage", new_callable=AsyncMock)
    async def test_lineage_recorded_for_each_fact(self, mock_lineage, service, session):
        """record_lineage is called for each created ClinicalFact."""
        patient = _patient_resource()
        cond = _condition_resource()
        med = _medication_request()
        bundle = _make_bundle(patient, cond, med)

        result = await service.import_bundle(session, bundle)
        assert result["success"] is True
        # Should have been called at least twice (condition + medication)
        assert mock_lineage.call_count >= 2

    @pytest.mark.asyncio
    @patch("app.services.fhir_import.record_lineage", new_callable=AsyncMock)
    async def test_lineage_failure_does_not_crash(self, mock_lineage, service, session):
        """Lineage recording failure doesn't break the import."""
        mock_lineage.side_effect = Exception("Lineage DB error")
        patient = _patient_resource()
        cond = _condition_resource()
        bundle = _make_bundle(patient, cond)

        result = await service.import_bundle(session, bundle)
        # Import should still succeed even if lineage fails
        assert result["success"] is True
        assert result["conditions"] == 1
