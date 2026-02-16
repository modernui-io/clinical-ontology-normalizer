"""Comprehensive tests for OpenEHR import, export, and API endpoints.

Covers:
- Import: each archetype type -> correct ClinicalFact domain/values/assertion
- Import: Patient KGNode creation with demographics
- Import: lineage recording
- Export: each domain -> correct archetype structure
- Export: round-trip (import -> export -> validate structure matches)
- API: endpoint integration tests
- Edge cases: missing fields, unknown archetypes, empty compositions
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.openehr_import import (
    ARCHETYPE_DOMAIN_MAP,
    OpenEHRImportService,
    _find_element_by_name,
    _get_archetype_key,
    _parse_dv_coded_text,
    _parse_dv_date_time,
    _parse_dv_quantity,
)
from app.services.openehr_exporter import (
    DOMAIN_ARCHETYPE_MAP,
    MEASUREMENT_ARCHETYPE_MAP,
    OpenEHRExporterService,
    build_dv_coded_text,
    build_dv_date_time,
    build_dv_quantity,
    build_dv_text,
    build_element,
)
from app.connectors.meditech_openehr_contract import (
    MEDITECH_OPENEHR_CONTRACT_ID,
    MEDITECH_CANONICAL_CONTRACT_SIGNATURE,
)
from app.models.data_lineage import SourceType
from app.schemas.base import Domain


# ===========================================================================
# Test Fixtures: OpenEHR composition builders
# ===========================================================================


def _build_composition(content: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Build a minimal valid OpenEHR COMPOSITION."""
    return {
        "_type": "COMPOSITION",
        "archetype_node_id": "openEHR-EHR-COMPOSITION.encounter.v1",
        "name": {"_type": "DV_TEXT", "value": "Clinical Encounter"},
        "language": {
            "_type": "CODE_PHRASE",
            "terminology_id": {"value": "ISO_639-1"},
            "code_string": "en",
        },
        "territory": {
            "_type": "CODE_PHRASE",
            "terminology_id": {"value": "ISO_3166-1"},
            "code_string": "US",
        },
        "category": {
            "_type": "DV_CODED_TEXT",
            "value": "event",
            "defining_code": {
                "terminology_id": {"value": "openehr"},
                "code_string": "433",
            },
        },
        "composer": {"_type": "PARTY_IDENTIFIED", "name": "Dr. Test"},
        "context": {
            "_type": "EVENT_CONTEXT",
            "start_time": {
                "_type": "DV_DATE_TIME",
                "value": datetime.now(timezone.utc).isoformat(),
            },
            "setting": {
                "_type": "DV_CODED_TEXT",
                "value": "primary medical care",
                "defining_code": {
                    "terminology_id": {"value": "openehr"},
                    "code_string": "228",
                },
            },
        },
        "content": content or [],
    }


def _build_condition_entry(
    name: str = "Hypertension",
    code: str = "38341003",
    system: str = "SNOMED-CT",
    onset: str | None = "2024-01-15T10:00:00Z",
) -> dict[str, Any]:
    """Build an EVALUATION.problem_diagnosis.v1 entry."""
    items: list[dict[str, Any]] = [
        {
            "_type": "ELEMENT",
            "name": {"_type": "DV_TEXT", "value": "Problem/Diagnosis name"},
            "value": {
                "_type": "DV_CODED_TEXT",
                "value": name,
                "defining_code": {
                    "terminology_id": {"value": system},
                    "code_string": code,
                },
            },
        },
    ]
    if onset:
        items.append({
            "_type": "ELEMENT",
            "name": {"_type": "DV_TEXT", "value": "Date/time of onset"},
            "value": {"_type": "DV_DATE_TIME", "value": onset},
        })
    return {
        "_type": "EVALUATION",
        "archetype_node_id": "openEHR-EHR-EVALUATION.problem_diagnosis.v1",
        "name": {"_type": "DV_TEXT", "value": "Problem/Diagnosis"},
        "data": {"_type": "ITEM_TREE", "items": items},
    }


def _build_medication_entry(
    name: str = "Metformin",
    code: str = "6809",
    system: str = "RxNorm",
    dose: float | None = 500.0,
    dose_unit: str | None = "mg",
) -> dict[str, Any]:
    """Build an INSTRUCTION.medication_order.v3 entry."""
    items: list[dict[str, Any]] = [
        {
            "_type": "ELEMENT",
            "name": {"_type": "DV_TEXT", "value": "Medication item"},
            "value": {
                "_type": "DV_CODED_TEXT",
                "value": name,
                "defining_code": {
                    "terminology_id": {"value": system},
                    "code_string": code,
                },
            },
        },
    ]
    if dose is not None and dose_unit:
        items.append({
            "_type": "ELEMENT",
            "name": {"_type": "DV_TEXT", "value": "Dose amount"},
            "value": {"_type": "DV_QUANTITY", "magnitude": dose, "units": dose_unit},
        })
    return {
        "_type": "INSTRUCTION",
        "archetype_node_id": "openEHR-EHR-INSTRUCTION.medication_order.v3",
        "name": {"_type": "DV_TEXT", "value": "Medication order"},
        "activities": [
            {
                "_type": "ACTIVITY",
                "description": {"_type": "ITEM_TREE", "items": items},
            }
        ],
    }


def _build_bp_entry(systolic: float = 120.0, diastolic: float = 80.0) -> dict[str, Any]:
    """Build an OBSERVATION.blood_pressure.v2 entry."""
    return {
        "_type": "OBSERVATION",
        "archetype_node_id": "openEHR-EHR-OBSERVATION.blood_pressure.v2",
        "name": {"_type": "DV_TEXT", "value": "Blood Pressure"},
        "data": {
            "_type": "HISTORY",
            "events": [
                {
                    "_type": "POINT_EVENT",
                    "time": {
                        "_type": "DV_DATE_TIME",
                        "value": datetime.now(timezone.utc).isoformat(),
                    },
                    "data": {
                        "_type": "ITEM_TREE",
                        "items": [
                            {
                                "_type": "ELEMENT",
                                "name": {"_type": "DV_TEXT", "value": "Systolic"},
                                "value": {
                                    "_type": "DV_QUANTITY",
                                    "magnitude": systolic,
                                    "units": "mm[Hg]",
                                },
                            },
                            {
                                "_type": "ELEMENT",
                                "name": {"_type": "DV_TEXT", "value": "Diastolic"},
                                "value": {
                                    "_type": "DV_QUANTITY",
                                    "magnitude": diastolic,
                                    "units": "mm[Hg]",
                                },
                            },
                        ],
                    },
                }
            ],
        },
    }


def _build_vital_entry(
    archetype_suffix: str = "body_temperature.v2",
    name: str = "Temperature",
    value: float = 37.0,
    unit: str = "Cel",
) -> dict[str, Any]:
    """Build a single-value OBSERVATION entry (temp, weight, height, pulse, SpO2)."""
    return {
        "_type": "OBSERVATION",
        "archetype_node_id": f"openEHR-EHR-OBSERVATION.{archetype_suffix}",
        "name": {"_type": "DV_TEXT", "value": name},
        "data": {
            "_type": "HISTORY",
            "events": [
                {
                    "_type": "POINT_EVENT",
                    "time": {
                        "_type": "DV_DATE_TIME",
                        "value": datetime.now(timezone.utc).isoformat(),
                    },
                    "data": {
                        "_type": "ITEM_TREE",
                        "items": [
                            {
                                "_type": "ELEMENT",
                                "name": {"_type": "DV_TEXT", "value": name},
                                "value": {
                                    "_type": "DV_QUANTITY",
                                    "magnitude": value,
                                    "units": unit,
                                },
                            },
                        ],
                    },
                }
            ],
        },
    }


def _build_procedure_entry(
    name: str = "Appendectomy",
    code: str = "80146002",
    system: str = "SNOMED-CT",
) -> dict[str, Any]:
    """Build an ACTION.procedure.v1 entry."""
    return {
        "_type": "ACTION",
        "archetype_node_id": "openEHR-EHR-ACTION.procedure.v1",
        "name": {"_type": "DV_TEXT", "value": "Procedure"},
        "description": {
            "_type": "ITEM_TREE",
            "items": [
                {
                    "_type": "ELEMENT",
                    "name": {"_type": "DV_TEXT", "value": "Procedure name"},
                    "value": {
                        "_type": "DV_CODED_TEXT",
                        "value": name,
                        "defining_code": {
                            "terminology_id": {"value": system},
                            "code_string": code,
                        },
                    },
                },
            ],
        },
        "time": {
            "_type": "DV_DATE_TIME",
            "value": "2024-06-15T14:00:00Z",
        },
    }


def _build_allergy_entry(
    substance: str = "Penicillin",
    code: str = "764146007",
    system: str = "SNOMED-CT",
    reaction: str | None = "Anaphylaxis",
) -> dict[str, Any]:
    """Build an EVALUATION.adverse_reaction_risk.v1 entry."""
    items: list[dict[str, Any]] = [
        {
            "_type": "ELEMENT",
            "name": {"_type": "DV_TEXT", "value": "Substance"},
            "value": {
                "_type": "DV_CODED_TEXT",
                "value": substance,
                "defining_code": {
                    "terminology_id": {"value": system},
                    "code_string": code,
                },
            },
        },
    ]
    if reaction:
        items.append({
            "_type": "CLUSTER",
            "name": {"_type": "DV_TEXT", "value": "Reaction event"},
            "items": [
                {
                    "_type": "ELEMENT",
                    "name": {"_type": "DV_TEXT", "value": "Manifestation"},
                    "value": {
                        "_type": "DV_CODED_TEXT",
                        "value": reaction,
                    },
                },
            ],
        })
    return {
        "_type": "EVALUATION",
        "archetype_node_id": "openEHR-EHR-EVALUATION.adverse_reaction_risk.v1",
        "name": {"_type": "DV_TEXT", "value": "Adverse reaction risk"},
        "data": {"_type": "ITEM_TREE", "items": items},
    }


# ===========================================================================
# Tests: RM Data Type Parsers
# ===========================================================================


class TestRMDataTypeParsers:
    """Test OpenEHR RM data type parsing helpers."""

    def test_parse_dv_coded_text(self) -> None:
        dv = {
            "_type": "DV_CODED_TEXT",
            "value": "Hypertension",
            "defining_code": {
                "terminology_id": {"value": "SNOMED-CT"},
                "code_string": "38341003",
            },
        }
        code, system, display = _parse_dv_coded_text(dv)
        assert code == "38341003"
        assert system == "SNOMED-CT"
        assert display == "Hypertension"

    def test_parse_dv_coded_text_none(self) -> None:
        code, system, display = _parse_dv_coded_text(None)
        assert code is None
        assert system is None
        assert display is None

    def test_parse_dv_quantity(self) -> None:
        dv = {"_type": "DV_QUANTITY", "magnitude": 120.0, "units": "mm[Hg]"}
        mag, unit = _parse_dv_quantity(dv)
        assert mag == 120.0
        assert unit == "mm[Hg]"

    def test_parse_dv_quantity_none(self) -> None:
        mag, unit = _parse_dv_quantity(None)
        assert mag is None
        assert unit is None

    def test_parse_dv_date_time(self) -> None:
        dv = {"_type": "DV_DATE_TIME", "value": "2024-01-15T10:00:00+00:00"}
        dt = _parse_dv_date_time(dv)
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 15

    def test_parse_dv_date_time_z_suffix(self) -> None:
        dv = {"_type": "DV_DATE_TIME", "value": "2024-01-15T10:00:00Z"}
        dt = _parse_dv_date_time(dv)
        assert dt is not None
        assert dt.year == 2024

    def test_parse_dv_date_time_none(self) -> None:
        assert _parse_dv_date_time(None) is None

    def test_parse_dv_date_time_invalid(self) -> None:
        dv = {"_type": "DV_DATE_TIME", "value": "not-a-date"}
        assert _parse_dv_date_time(dv) is None


class TestHelperFunctions:
    """Test utility helper functions."""

    def test_get_archetype_key_full_id(self) -> None:
        result = _get_archetype_key("openEHR-EHR-EVALUATION.problem_diagnosis.v1")
        assert result == "EVALUATION.problem_diagnosis.v1"

    def test_get_archetype_key_short_id(self) -> None:
        result = _get_archetype_key("EVALUATION.problem_diagnosis.v1")
        assert result == "EVALUATION.problem_diagnosis.v1"

    def test_find_element_by_name(self) -> None:
        items = [
            {"name": {"value": "Foo"}, "value": 1},
            {"name": {"value": "Bar"}, "value": 2},
        ]
        found = _find_element_by_name(items, "bar")
        assert found is not None
        assert found["value"] == 2

    def test_find_element_by_name_not_found(self) -> None:
        items = [{"name": {"value": "Foo"}, "value": 1}]
        assert _find_element_by_name(items, "Missing") is None


# ===========================================================================
# Tests: OpenEHR Import Service
# ===========================================================================


class TestOpenEHRImportService:
    """Test OpenEHRImportService.import_composition with mocked DB."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock async session."""
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        return session

    @pytest.fixture
    def service(self) -> OpenEHRImportService:
        return OpenEHRImportService()

    @pytest.mark.asyncio
    async def test_import_empty_composition(
        self, service: OpenEHRImportService, mock_session: AsyncMock
    ) -> None:
        result = await service.import_composition(
            mock_session, _build_composition([]), "patient-1"
        )
        assert result["success"] is False
        assert "Empty" in result["error"]

    @pytest.mark.asyncio
    async def test_import_not_composition(
        self, service: OpenEHRImportService, mock_session: AsyncMock
    ) -> None:
        result = await service.import_composition(
            mock_session, {"_type": "OBSERVATION"}, "patient-1"
        )
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_import_condition(
        self, service: OpenEHRImportService, mock_session: AsyncMock
    ) -> None:
        comp = _build_composition([_build_condition_entry()])
        result = await service.import_composition(
            mock_session, comp, "patient-1"
        )
        assert result["success"] is True
        assert result["conditions"] == 1
        assert result["nodes"] >= 2  # patient + condition

    @pytest.mark.asyncio
    async def test_import_medication(
        self, service: OpenEHRImportService, mock_session: AsyncMock
    ) -> None:
        comp = _build_composition([_build_medication_entry()])
        result = await service.import_composition(
            mock_session, comp, "patient-1"
        )
        assert result["success"] is True
        assert result["medications"] == 1

    @pytest.mark.asyncio
    async def test_import_blood_pressure(
        self, service: OpenEHRImportService, mock_session: AsyncMock
    ) -> None:
        comp = _build_composition([_build_bp_entry(130.0, 85.0)])
        result = await service.import_composition(
            mock_session, comp, "patient-1"
        )
        assert result["success"] is True
        assert result["measurements"] == 2  # systolic + diastolic

    @pytest.mark.asyncio
    async def test_import_temperature(
        self, service: OpenEHRImportService, mock_session: AsyncMock
    ) -> None:
        comp = _build_composition([
            _build_vital_entry("body_temperature.v2", "Temperature", 37.5, "Cel")
        ])
        result = await service.import_composition(
            mock_session, comp, "patient-1"
        )
        assert result["success"] is True
        assert result["measurements"] == 1

    @pytest.mark.asyncio
    async def test_import_body_weight(
        self, service: OpenEHRImportService, mock_session: AsyncMock
    ) -> None:
        comp = _build_composition([
            _build_vital_entry("body_weight.v2", "Weight", 75.0, "kg")
        ])
        result = await service.import_composition(
            mock_session, comp, "patient-1"
        )
        assert result["success"] is True
        assert result["measurements"] == 1

    @pytest.mark.asyncio
    async def test_import_height(
        self, service: OpenEHRImportService, mock_session: AsyncMock
    ) -> None:
        comp = _build_composition([
            _build_vital_entry("height.v2", "Height", 175.0, "cm")
        ])
        result = await service.import_composition(
            mock_session, comp, "patient-1"
        )
        assert result["success"] is True
        assert result["measurements"] == 1

    @pytest.mark.asyncio
    async def test_import_pulse(
        self, service: OpenEHRImportService, mock_session: AsyncMock
    ) -> None:
        comp = _build_composition([
            _build_vital_entry("pulse.v1", "Heart rate", 72.0, "/min")
        ])
        result = await service.import_composition(
            mock_session, comp, "patient-1"
        )
        assert result["success"] is True
        assert result["measurements"] == 1

    @pytest.mark.asyncio
    async def test_import_pulse_oximetry(
        self, service: OpenEHRImportService, mock_session: AsyncMock
    ) -> None:
        comp = _build_composition([
            _build_vital_entry("pulse_oximetry.v1", "SpO2", 98.0, "%")
        ])
        result = await service.import_composition(
            mock_session, comp, "patient-1"
        )
        assert result["success"] is True
        assert result["measurements"] == 1

    @pytest.mark.asyncio
    async def test_import_procedure(
        self, service: OpenEHRImportService, mock_session: AsyncMock
    ) -> None:
        comp = _build_composition([_build_procedure_entry()])
        result = await service.import_composition(
            mock_session, comp, "patient-1"
        )
        assert result["success"] is True
        assert result["procedures"] == 1

    @pytest.mark.asyncio
    async def test_import_allergy(
        self, service: OpenEHRImportService, mock_session: AsyncMock
    ) -> None:
        comp = _build_composition([_build_allergy_entry()])
        result = await service.import_composition(
            mock_session, comp, "patient-1"
        )
        assert result["success"] is True
        assert result["allergies"] == 1

    @pytest.mark.asyncio
    async def test_import_patient_node_created(
        self, service: OpenEHRImportService, mock_session: AsyncMock
    ) -> None:
        """Verify patient KGNode is created."""
        comp = _build_composition([_build_condition_entry()])
        result = await service.import_composition(
            mock_session, comp, "patient-1"
        )
        assert result["success"] is True
        # First session.add call should be the patient node
        first_add = mock_session.add.call_args_list[0][0][0]
        assert hasattr(first_add, "node_type") or hasattr(first_add, "patient_id")

    @pytest.mark.asyncio
    async def test_import_lineage_recorded(
        self, service: OpenEHRImportService, mock_session: AsyncMock
    ) -> None:
        """Verify lineage is recorded via record_lineage call."""
        comp = _build_composition([_build_condition_entry()])
        with patch(
            "app.services.openehr_import.record_lineage",
            new_callable=AsyncMock,
        ) as mock_lineage:
            await service.import_composition(mock_session, comp, "patient-1")
            assert mock_lineage.called
            call_kwargs = mock_lineage.call_args
            assert call_kwargs.kwargs["source_type"] == SourceType.OPENEHR_IMPORT

    @pytest.mark.asyncio
    async def test_import_meditech_lineage_contract_step(
        self, service: OpenEHRImportService, mock_session: AsyncMock
    ) -> None:
        """Meditech metadata should add contract lineage step."""
        metadata = {
            "source_system": "meditech",
            "source_record_id": "rec-007",
            "encounter_id": "enc-009",
            "pipeline_id": "pipeline-aus",
            "source_record_type": "encounter",
        }
        comp = _build_composition([_build_condition_entry()])

        with patch(
            "app.services.openehr_import.record_lineage",
            new_callable=AsyncMock,
        ) as mock_lineage:
            await service.import_composition(
                mock_session, comp, "patient-1", source_metadata=metadata
            )

            assert mock_lineage.called
            call_kwargs = mock_lineage.call_args.kwargs
            chain = call_kwargs["transformation_chain"]

            assert isinstance(chain, list)
            assert chain[0]["step"] == "meditech_to_openehr_adapter"
            assert chain[1]["step"] == "openehr_composition_import"

            contract_step = chain[0]
            assert contract_step["source_system"] == "meditech"
            assert contract_step["source_record_id"] == "rec-007"
            assert contract_step["source_encounter_id"] == "enc-009"
            assert contract_step["contract_id"] == MEDITECH_OPENEHR_CONTRACT_ID
            assert contract_step["contract_signature"] == MEDITECH_CANONICAL_CONTRACT_SIGNATURE

    @pytest.mark.asyncio
    async def test_import_unknown_archetype_skipped(
        self, service: OpenEHRImportService, mock_session: AsyncMock
    ) -> None:
        """Unknown archetypes should be counted as skipped."""
        unknown_entry = {
            "_type": "EVALUATION",
            "archetype_node_id": "openEHR-EHR-EVALUATION.unknown_thing.v1",
            "name": {"_type": "DV_TEXT", "value": "Unknown"},
            "data": {"_type": "ITEM_TREE", "items": []},
        }
        comp = _build_composition([unknown_entry])
        result = await service.import_composition(mock_session, comp, "patient-1")
        assert result["success"] is True
        assert result["skipped"] == 1

    @pytest.mark.asyncio
    async def test_import_condition_missing_name(
        self, service: OpenEHRImportService, mock_session: AsyncMock
    ) -> None:
        """Condition without Problem/Diagnosis name should produce 0 conditions."""
        entry = {
            "_type": "EVALUATION",
            "archetype_node_id": "openEHR-EHR-EVALUATION.problem_diagnosis.v1",
            "name": {"_type": "DV_TEXT", "value": "Problem/Diagnosis"},
            "data": {"_type": "ITEM_TREE", "items": []},
        }
        comp = _build_composition([entry])
        result = await service.import_composition(mock_session, comp, "patient-1")
        assert result["conditions"] == 0

    @pytest.mark.asyncio
    async def test_import_mixed_composition(
        self, service: OpenEHRImportService, mock_session: AsyncMock
    ) -> None:
        """Composition with multiple entry types."""
        comp = _build_composition([
            _build_condition_entry(),
            _build_medication_entry(),
            _build_bp_entry(),
            _build_procedure_entry(),
            _build_allergy_entry(),
        ])
        result = await service.import_composition(mock_session, comp, "patient-1")
        assert result["success"] is True
        assert result["conditions"] == 1
        assert result["medications"] == 1
        assert result["measurements"] == 2  # BP: systolic + diastolic
        assert result["procedures"] == 1
        assert result["allergies"] == 1


# ===========================================================================
# Tests: OpenEHR Export Service
# ===========================================================================


class TestOpenEHRExporterService:
    """Test OpenEHRExporterService."""

    @pytest.fixture
    def exporter(self) -> OpenEHRExporterService:
        return OpenEHRExporterService()

    def test_export_condition(self, exporter: OpenEHRExporterService) -> None:
        fact = {"domain": "condition", "concept_name": "Hypertension", "omop_concept_id": 38341003}
        entry = exporter.export_fact(fact)
        assert entry["_type"] == "EVALUATION"
        assert "problem_diagnosis" in entry["archetype_node_id"]
        items = entry["data"]["items"]
        assert any("Problem/Diagnosis name" in str(i) for i in items)

    def test_export_drug(self, exporter: OpenEHRExporterService) -> None:
        fact = {"domain": "drug", "concept_name": "Metformin", "omop_concept_id": 6809}
        entry = exporter.export_fact(fact)
        assert entry["_type"] == "INSTRUCTION"
        assert "medication_order" in entry["archetype_node_id"]
        items = entry["activities"][0]["description"]["items"]
        assert any("Medication item" in str(i) for i in items)

    def test_export_measurement(self, exporter: OpenEHRExporterService) -> None:
        fact = {"domain": "measurement", "concept_name": "Lab Result"}
        entry = exporter.export_fact(fact)
        assert entry["_type"] == "OBSERVATION"
        assert "laboratory_test_result" in entry["archetype_node_id"]

    def test_export_measurement_blood_pressure(self, exporter: OpenEHRExporterService) -> None:
        fact = {"domain": "measurement", "concept_name": "Blood Pressure - Systolic"}
        entry = exporter.export_fact(fact)
        assert entry["_type"] == "OBSERVATION"
        assert "blood_pressure" in entry["archetype_node_id"]

    def test_export_measurement_temperature(self, exporter: OpenEHRExporterService) -> None:
        fact = {"domain": "measurement", "concept_name": "Body Temperature"}
        entry = exporter.export_fact(fact)
        assert "body_temperature" in entry["archetype_node_id"]

    def test_export_measurement_weight(self, exporter: OpenEHRExporterService) -> None:
        fact = {"domain": "measurement", "concept_name": "Body Weight"}
        entry = exporter.export_fact(fact)
        assert "body_weight" in entry["archetype_node_id"]

    def test_export_measurement_height(self, exporter: OpenEHRExporterService) -> None:
        fact = {"domain": "measurement", "concept_name": "Body Height"}
        entry = exporter.export_fact(fact)
        assert "height" in entry["archetype_node_id"]

    def test_export_measurement_pulse(self, exporter: OpenEHRExporterService) -> None:
        fact = {"domain": "measurement", "concept_name": "Heart rate"}
        entry = exporter.export_fact(fact)
        assert "pulse" in entry["archetype_node_id"]

    def test_export_measurement_spo2(self, exporter: OpenEHRExporterService) -> None:
        fact = {"domain": "measurement", "concept_name": "SpO2"}
        entry = exporter.export_fact(fact)
        assert "pulse_oximetry" in entry["archetype_node_id"]

    def test_export_procedure(self, exporter: OpenEHRExporterService) -> None:
        fact = {"domain": "procedure", "concept_name": "Appendectomy", "omop_concept_id": 80146002}
        entry = exporter.export_fact(fact)
        assert entry["_type"] == "ACTION"
        assert "procedure" in entry["archetype_node_id"]
        items = entry["description"]["items"]
        assert any("Procedure name" in str(i) for i in items)

    def test_export_allergy(self, exporter: OpenEHRExporterService) -> None:
        fact = {"domain": "observation", "concept_name": "Penicillin"}
        entry = exporter.export_fact(fact)
        assert entry["_type"] == "EVALUATION"
        assert "adverse_reaction_risk" in entry["archetype_node_id"]

    def test_export_facts_full_composition(self, exporter: OpenEHRExporterService) -> None:
        """Export multiple facts as a full COMPOSITION."""
        facts = [
            {"domain": "condition", "concept_name": "Diabetes"},
            {"domain": "drug", "concept_name": "Insulin"},
            {"domain": "measurement", "concept_name": "HbA1c"},
        ]
        comp = exporter.export_facts(facts, "patient-1")
        assert comp["_type"] == "COMPOSITION"
        assert comp["archetype_node_id"] == "openEHR-EHR-COMPOSITION.encounter.v1"
        assert len(comp["content"]) == 3
        assert comp["composer"]["name"] == "System"
        assert comp["territory"]["code_string"] == "US"
        assert comp["language"]["code_string"] == "en"

    def test_export_facts_custom_composer(self, exporter: OpenEHRExporterService) -> None:
        facts = [{"domain": "condition", "concept_name": "Test"}]
        comp = exporter.export_facts(
            facts, "p1", composer_name="Dr. Jones", territory="GB", language="de"
        )
        assert comp["composer"]["name"] == "Dr. Jones"
        assert comp["territory"]["code_string"] == "GB"
        assert comp["language"]["code_string"] == "de"


# ===========================================================================
# Tests: RM Type Builders
# ===========================================================================


class TestRMTypeBuilders:
    """Test RM data type builder functions."""

    def test_build_dv_text(self) -> None:
        result = build_dv_text("Hello")
        assert result["_type"] == "DV_TEXT"
        assert result["value"] == "Hello"

    def test_build_dv_coded_text_with_code(self) -> None:
        result = build_dv_coded_text("Test", "123", "SNOMED")
        assert result["_type"] == "DV_CODED_TEXT"
        assert result["value"] == "Test"
        assert result["defining_code"]["code_string"] == "123"
        assert result["defining_code"]["terminology_id"]["value"] == "SNOMED"

    def test_build_dv_coded_text_without_code(self) -> None:
        result = build_dv_coded_text("Test Only")
        assert result["_type"] == "DV_CODED_TEXT"
        assert result["value"] == "Test Only"
        assert "defining_code" not in result

    def test_build_dv_quantity(self) -> None:
        result = build_dv_quantity(120.5, "mm[Hg]")
        assert result["_type"] == "DV_QUANTITY"
        assert result["magnitude"] == 120.5
        assert result["units"] == "mm[Hg]"

    def test_build_dv_date_time_now(self) -> None:
        result = build_dv_date_time()
        assert result["_type"] == "DV_DATE_TIME"
        assert "value" in result
        datetime.fromisoformat(result["value"])  # Should parse

    def test_build_dv_date_time_string(self) -> None:
        result = build_dv_date_time("2024-01-15T10:00:00Z")
        assert result["value"] == "2024-01-15T10:00:00Z"

    def test_build_element(self) -> None:
        value = build_dv_text("test")
        result = build_element("My Element", value)
        assert result["_type"] == "ELEMENT"
        assert result["name"]["value"] == "My Element"
        assert result["value"] == value


# ===========================================================================
# Tests: Round-trip (import -> export -> validate)
# ===========================================================================


class TestRoundTrip:
    """Test import -> export round-trip integrity."""

    def test_condition_round_trip(self) -> None:
        """Import a condition composition, export it, verify structure."""
        exporter = OpenEHRExporterService()

        # Simulate an imported fact
        fact = {
            "domain": "condition",
            "concept_name": "Hypertension",
            "omop_concept_id": 38341003,
        }
        entry = exporter.export_fact(fact)
        assert entry["_type"] == "EVALUATION"
        assert "problem_diagnosis" in entry["archetype_node_id"]

        # Verify we can find the name in the exported structure
        items = entry["data"]["items"]
        name_item = None
        for item in items:
            if item["name"]["value"] == "Problem/Diagnosis name":
                name_item = item
                break
        assert name_item is not None
        assert name_item["value"]["value"] == "Hypertension"

    def test_medication_round_trip(self) -> None:
        exporter = OpenEHRExporterService()
        fact = {"domain": "drug", "concept_name": "Metformin"}
        entry = exporter.export_fact(fact)

        items = entry["activities"][0]["description"]["items"]
        med_item = None
        for item in items:
            if item["name"]["value"] == "Medication item":
                med_item = item
                break
        assert med_item is not None
        assert med_item["value"]["value"] == "Metformin"

    def test_procedure_round_trip(self) -> None:
        exporter = OpenEHRExporterService()
        fact = {"domain": "procedure", "concept_name": "Appendectomy"}
        entry = exporter.export_fact(fact)

        items = entry["description"]["items"]
        proc_item = None
        for item in items:
            if item["name"]["value"] == "Procedure name":
                proc_item = item
                break
        assert proc_item is not None
        assert proc_item["value"]["value"] == "Appendectomy"

    def test_full_round_trip_composition_structure(self) -> None:
        """Export facts then validate the full composition structure."""
        exporter = OpenEHRExporterService()
        facts = [
            {"domain": "condition", "concept_name": "Diabetes"},
            {"domain": "drug", "concept_name": "Insulin"},
            {"domain": "procedure", "concept_name": "Lab draw"},
        ]
        comp = exporter.export_facts(facts, "patient-round-trip")

        # Validate required COMPOSITION fields
        assert comp["_type"] == "COMPOSITION"
        assert "composer" in comp
        assert "context" in comp
        assert "content" in comp
        assert "language" in comp
        assert "territory" in comp
        assert "category" in comp
        assert len(comp["content"]) == 3


# ===========================================================================
# Tests: Archetype Mapping Coverage
# ===========================================================================


class TestArchetypeMappingCoverage:
    """Verify all declared archetypes have proper mappings."""

    def test_all_archetypes_have_domain(self) -> None:
        for key, (domain, node_type, edge_type) in ARCHETYPE_DOMAIN_MAP.items():
            assert domain is not None, f"Missing domain for {key}"
            assert node_type is not None, f"Missing node_type for {key}"
            assert edge_type is not None, f"Missing edge_type for {key}"

    def test_all_export_domains_have_archetypes(self) -> None:
        for domain in DOMAIN_ARCHETYPE_MAP:
            archetype = DOMAIN_ARCHETYPE_MAP[domain]
            assert archetype.startswith("openEHR-EHR-"), f"Invalid archetype for domain {domain}"

    def test_source_type_enum_has_openehr(self) -> None:
        assert hasattr(SourceType, "OPENEHR_IMPORT")
        assert SourceType.OPENEHR_IMPORT.value == "openehr_import"


# ===========================================================================
# Tests: API Endpoint Models
# ===========================================================================


class TestAPIModels:
    """Test API request/response model validation."""

    def test_import_request_valid(self) -> None:
        from app.api.openehr import OpenEHRCompositionImportRequest
        req = OpenEHRCompositionImportRequest(
            composition=_build_composition([_build_condition_entry()]),
            patient_id="test-patient",
        )
        assert req.patient_id == "test-patient"
        assert req.composition["_type"] == "COMPOSITION"

    def test_import_request_with_source_metadata(self) -> None:
        from app.api.openehr import OpenEHRCompositionImportRequest

        req = OpenEHRCompositionImportRequest(
            composition=_build_composition([_build_condition_entry()]),
            patient_id="test-patient",
            source_metadata={"source_system": "meditech", "pipeline_id": "pipeline-aus"},
        )
        assert req.source_metadata is not None
        assert req.source_metadata["source_system"] == "meditech"

    def test_export_request_defaults(self) -> None:
        from app.api.openehr import OpenEHRExportRequest
        req = OpenEHRExportRequest()
        assert req.composer_name == "System"
        assert req.territory == "US"
        assert req.language == "en"

    def test_archetype_list_response(self) -> None:
        from app.api.openehr import ArchetypeInfo, ArchetypeListResponse
        info = ArchetypeInfo(
            archetype_id="openEHR-EHR-EVALUATION.problem_diagnosis.v1",
            domain="condition",
            node_type="condition",
            edge_type="has_condition",
        )
        resp = ArchetypeListResponse(archetypes=[info], count=1)
        assert resp.count == 1
        assert resp.archetypes[0].domain == "condition"


# ===========================================================================
# Tests: SSRF Protection
# ===========================================================================


class TestSSRFProtection:
    """Test URL validation for SSRF prevention."""

    def test_valid_https_url(self) -> None:
        from app.api.openehr import validate_openehr_url
        url = validate_openehr_url("https://openehr.example.com/rest")
        assert url == "https://openehr.example.com/rest"

    def test_private_ip_blocked(self) -> None:
        from app.api.openehr import validate_openehr_url
        with pytest.raises(ValueError, match="private"):
            validate_openehr_url("https://192.168.1.1/rest")

    def test_metadata_ip_blocked(self) -> None:
        from app.api.openehr import validate_openehr_url
        with pytest.raises(ValueError, match="private"):
            validate_openehr_url("http://169.254.169.254/latest")

    def test_empty_url_rejected(self) -> None:
        from app.api.openehr import validate_openehr_url
        with pytest.raises(ValueError, match="required"):
            validate_openehr_url("")

    def test_invalid_scheme_rejected(self) -> None:
        from app.api.openehr import validate_openehr_url
        with pytest.raises(ValueError, match="scheme"):
            validate_openehr_url("ftp://openehr.example.com/rest")
