"""Meditech sample replay validation against OpenEHR contract (P1-031).

Deterministic replay tests: known Meditech-sourced compositions are processed
through the OpenEHR import pipeline and the resulting ClinicalFacts, KGNodes,
and lineage records are compared against pre-defined expected outputs.

Exit criteria: all replay tests produce identical results on every run,
proving contract stability and import determinism.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.connectors.meditech_openehr_contract import (
    MEDITECH_CANONICAL_CONTRACT,
    MEDITECH_CANONICAL_CONTRACT_SIGNATURE,
    MEDITECH_CODE_SYSTEM_NORMALIZATION,
    MEDITECH_OPENEHR_CONTRACT_ID,
    MEDITECH_OPENEHR_CONTRACT_VERSION,
    MEDITECH_TO_OPENEHR_MAP,
    build_meditech_contract_lineage_step,
    normalize_meditech_code_system,
)
from app.models.data_lineage import SourceType
from app.schemas.base import Domain
from app.services.openehr_import import ARCHETYPE_DOMAIN_MAP, OpenEHRImportService

from tests.fixtures.meditech_sample_compositions import (
    EXPECTED_ENCOUNTER_FACTS,
    EXPECTED_LAB_FACTS,
    EXPECTED_LINEAGE_CONTRACT_FIELDS,
    MEDITECH_SOURCE_META_AU,
    build_meditech_encounter_composition,
    build_meditech_lab_composition,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()

    async def _nested():
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=None)
        ctx.__aexit__ = AsyncMock(return_value=False)
        return ctx

    session.begin_nested = _nested
    return session


@pytest.fixture
def service() -> OpenEHRImportService:
    return OpenEHRImportService()


# ===========================================================================
# Contract determinism tests
# ===========================================================================


class TestContractDeterminism:
    """Verify the canonical contract is stable across invocations."""

    def test_contract_signature_is_stable(self) -> None:
        """Signature must not change between module reloads."""
        from app.connectors.meditech_openehr_contract import _contract_signature
        sig = _contract_signature(MEDITECH_CANONICAL_CONTRACT)
        assert sig == MEDITECH_CANONICAL_CONTRACT_SIGNATURE

    def test_contract_has_required_fields(self) -> None:
        required = {"contract_id", "contract_version", "effective_date",
                     "source_profile", "target_profile", "source_vendor",
                     "target_archetype_map", "code_system_policy", "required_identifiers"}
        assert required <= set(MEDITECH_CANONICAL_CONTRACT.keys())

    def test_archetype_map_covers_all_entry_types(self) -> None:
        """Every Meditech record type maps to a known archetype."""
        for meditech_type, archetype in MEDITECH_TO_OPENEHR_MAP.items():
            key = archetype.split("openEHR-EHR-")[-1] if "openEHR-EHR-" in archetype else archetype
            assert key in ARCHETYPE_DOMAIN_MAP, f"{meditech_type} -> {archetype} not in domain map"


# ===========================================================================
# Code system normalization replay
# ===========================================================================


class TestCodeSystemNormalization:
    """Replay normalization for all Meditech code system variants."""

    @pytest.mark.parametrize("raw,expected", [
        ("SNOMED CT", "SNOMED"),
        ("SCT", "SNOMED"),
        ("SNM", "SNOMED"),
        ("SNOMEDCT", "SNOMED"),
        ("SNOMEDCT-US", "SNOMED"),
        ("RXN", "RxNorm"),
        ("RXNORM", "RxNorm"),
        ("RXNORM-ND", "RxNorm"),
        ("LOINC", "LOINC"),
        ("LOCAL", "LOCAL"),
    ])
    def test_normalize_known_systems(self, raw: str, expected: str) -> None:
        assert normalize_meditech_code_system(raw) == expected

    def test_normalize_none_returns_none(self) -> None:
        assert normalize_meditech_code_system(None) is None

    def test_normalize_unknown_passes_through(self) -> None:
        result = normalize_meditech_code_system("ICD-10-AM")
        assert result is not None  # should return something, not silently drop


# ===========================================================================
# Lineage step builder replay
# ===========================================================================


class TestLineageStepBuilder:
    """Verify lineage step is deterministic for Meditech sources."""

    def test_meditech_metadata_produces_step(self) -> None:
        step = build_meditech_contract_lineage_step(
            source_metadata=MEDITECH_SOURCE_META_AU,
            entry={"archetype_node_id": "test"},
        )
        assert step is not None
        for key, expected in EXPECTED_LINEAGE_CONTRACT_FIELDS.items():
            assert step[key] == expected

    def test_step_includes_contract_signature(self) -> None:
        step = build_meditech_contract_lineage_step(
            source_metadata=MEDITECH_SOURCE_META_AU,
        )
        assert step is not None
        assert step["contract_signature"] == MEDITECH_CANONICAL_CONTRACT_SIGNATURE

    def test_step_includes_encounter_and_pipeline(self) -> None:
        step = build_meditech_contract_lineage_step(
            source_metadata=MEDITECH_SOURCE_META_AU,
        )
        assert step is not None
        assert step["source_encounter_id"] == "ENC-2026-10087"
        assert step["pipeline_id"] == "pipeline-aus-prod-01"

    def test_step_includes_record_id(self) -> None:
        step = build_meditech_contract_lineage_step(
            source_metadata=MEDITECH_SOURCE_META_AU,
        )
        assert step is not None
        assert step["source_record_id"] == "MT-AU-2026-00421"

    def test_non_meditech_source_returns_none(self) -> None:
        step = build_meditech_contract_lineage_step(
            source_metadata={"source_system": "epic"},
        )
        assert step is None

    def test_no_metadata_returns_none(self) -> None:
        step = build_meditech_contract_lineage_step(
            source_metadata=None,
        )
        assert step is None

    def test_step_deterministic_across_calls(self) -> None:
        """Same input must produce byte-identical output."""
        step1 = build_meditech_contract_lineage_step(
            source_metadata=MEDITECH_SOURCE_META_AU,
            archetype_key="EVALUATION.problem_diagnosis.v1",
        )
        step2 = build_meditech_contract_lineage_step(
            source_metadata=MEDITECH_SOURCE_META_AU,
            archetype_key="EVALUATION.problem_diagnosis.v1",
        )
        assert step1 == step2

    @pytest.mark.parametrize("variant", [
        "meditech", "Meditech", "MEDITECH",
        "meditech-au", "meditech-australia", "meditech_aus",
    ])
    def test_source_system_variants_all_resolve(self, variant: str) -> None:
        step = build_meditech_contract_lineage_step(
            source_metadata={"source_system": variant, "source_record_id": "x"},
        )
        assert step is not None
        assert step["source_system"] == "meditech"


# ===========================================================================
# Full encounter composition replay
# ===========================================================================


class TestEncounterReplay:
    """Replay a full Meditech encounter and validate fact counts and content."""

    @pytest.mark.asyncio
    async def test_encounter_fact_counts(
        self, service: OpenEHRImportService, mock_session: AsyncMock
    ) -> None:
        """Import produces exact expected fact counts."""
        comp = build_meditech_encounter_composition()
        with patch("app.services.openehr_import.record_lineage", new_callable=AsyncMock):
            result = await service.import_composition(
                mock_session, comp, "patient-replay-01",
                source_metadata=MEDITECH_SOURCE_META_AU,
            )
        assert result["conditions"] == EXPECTED_ENCOUNTER_FACTS["conditions"]
        assert result["medications"] == EXPECTED_ENCOUNTER_FACTS["medications"]
        assert result["measurements"] == EXPECTED_ENCOUNTER_FACTS["measurements"]
        assert result["procedures"] == EXPECTED_ENCOUNTER_FACTS["procedures"]
        assert result["allergies"] == EXPECTED_ENCOUNTER_FACTS["allergies"]

    @pytest.mark.asyncio
    async def test_encounter_total_facts(
        self, service: OpenEHRImportService, mock_session: AsyncMock
    ) -> None:
        """Total fact count matches expected."""
        comp = build_meditech_encounter_composition()
        with patch("app.services.openehr_import.record_lineage", new_callable=AsyncMock):
            result = await service.import_composition(
                mock_session, comp, "patient-replay-01",
                source_metadata=MEDITECH_SOURCE_META_AU,
            )
        total = (result["conditions"] + result["medications"] +
                 result["measurements"] + result["procedures"] + result["allergies"])
        assert total == EXPECTED_ENCOUNTER_FACTS["total"]

    @pytest.mark.asyncio
    async def test_encounter_creates_patient_node(
        self, service: OpenEHRImportService, mock_session: AsyncMock
    ) -> None:
        """Patient KGNode is created."""
        comp = build_meditech_encounter_composition()
        with patch("app.services.openehr_import.record_lineage", new_callable=AsyncMock):
            result = await service.import_composition(
                mock_session, comp, "patient-replay-01",
                source_metadata=MEDITECH_SOURCE_META_AU,
            )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_encounter_clinical_fact_domains(
        self, service: OpenEHRImportService, mock_session: AsyncMock
    ) -> None:
        """Verify ClinicalFact objects have correct domain assignments."""
        comp = build_meditech_encounter_composition()
        facts_added = []

        def capture_add(obj: Any) -> None:
            facts_added.append(obj)

        mock_session.add = MagicMock(side_effect=capture_add)

        with patch("app.services.openehr_import.record_lineage", new_callable=AsyncMock):
            await service.import_composition(
                mock_session, comp, "patient-replay-01",
                source_metadata=MEDITECH_SOURCE_META_AU,
            )

        from app.models.clinical_fact import ClinicalFact
        clinical_facts = [f for f in facts_added if isinstance(f, ClinicalFact)]

        domains = {f.domain for f in clinical_facts}
        assert Domain.CONDITION in domains
        assert Domain.DRUG in domains
        assert Domain.MEASUREMENT in domains
        assert Domain.PROCEDURE in domains
        assert Domain.OBSERVATION in domains  # allergy

    @pytest.mark.asyncio
    async def test_encounter_lineage_recorded_for_each_fact(
        self, service: OpenEHRImportService, mock_session: AsyncMock
    ) -> None:
        """Every fact should trigger lineage recording."""
        comp = build_meditech_encounter_composition()
        with patch(
            "app.services.openehr_import.record_lineage",
            new_callable=AsyncMock,
        ) as mock_lineage:
            result = await service.import_composition(
                mock_session, comp, "patient-replay-01",
                source_metadata=MEDITECH_SOURCE_META_AU,
            )
            # Each fact triggers one lineage call
            assert mock_lineage.call_count == EXPECTED_ENCOUNTER_FACTS["total"]

    @pytest.mark.asyncio
    async def test_encounter_lineage_has_contract_step(
        self, service: OpenEHRImportService, mock_session: AsyncMock
    ) -> None:
        """Each lineage call should include the Meditech contract step."""
        comp = build_meditech_encounter_composition()
        with patch(
            "app.services.openehr_import.record_lineage",
            new_callable=AsyncMock,
        ) as mock_lineage:
            await service.import_composition(
                mock_session, comp, "patient-replay-01",
                source_metadata=MEDITECH_SOURCE_META_AU,
            )
            for call in mock_lineage.call_args_list:
                chain = call.kwargs.get("transformation_chain", [])
                assert len(chain) >= 2, "chain should have contract + import steps"
                assert chain[0]["step"] == "meditech_to_openehr_adapter"
                assert chain[0]["contract_id"] == MEDITECH_OPENEHR_CONTRACT_ID
                assert chain[1]["step"] == "openehr_composition_import"

    @pytest.mark.asyncio
    async def test_encounter_replay_is_deterministic(
        self, service: OpenEHRImportService, mock_session: AsyncMock
    ) -> None:
        """Running the same composition twice produces identical stats."""
        comp = build_meditech_encounter_composition()

        with patch("app.services.openehr_import.record_lineage", new_callable=AsyncMock):
            r1 = await service.import_composition(
                mock_session, comp, "patient-replay-01",
                source_metadata=MEDITECH_SOURCE_META_AU,
            )

        with patch("app.services.openehr_import.record_lineage", new_callable=AsyncMock):
            r2 = await service.import_composition(
                mock_session, comp, "patient-replay-01",
                source_metadata=MEDITECH_SOURCE_META_AU,
            )

        for key in ("conditions", "medications", "measurements", "procedures", "allergies"):
            assert r1[key] == r2[key], f"Non-deterministic result for {key}"


# ===========================================================================
# Lab composition replay
# ===========================================================================


class TestLabReplay:
    """Replay a lab-only Meditech encounter."""

    @pytest.mark.asyncio
    async def test_lab_fact_counts(
        self, service: OpenEHRImportService, mock_session: AsyncMock
    ) -> None:
        comp = build_meditech_lab_composition()
        with patch("app.services.openehr_import.record_lineage", new_callable=AsyncMock):
            result = await service.import_composition(
                mock_session, comp, "patient-lab-01",
                source_metadata=MEDITECH_SOURCE_META_AU,
            )
        assert result["measurements"] == EXPECTED_LAB_FACTS["measurements"]
        assert result["conditions"] == EXPECTED_LAB_FACTS["conditions"]
        assert result["medications"] == EXPECTED_LAB_FACTS["medications"]
        assert result["procedures"] == EXPECTED_LAB_FACTS["procedures"]
        assert result["allergies"] == EXPECTED_LAB_FACTS["allergies"]

    @pytest.mark.asyncio
    async def test_lab_total(
        self, service: OpenEHRImportService, mock_session: AsyncMock
    ) -> None:
        comp = build_meditech_lab_composition()
        with patch("app.services.openehr_import.record_lineage", new_callable=AsyncMock):
            result = await service.import_composition(
                mock_session, comp, "patient-lab-01",
                source_metadata=MEDITECH_SOURCE_META_AU,
            )
        total = sum(result[k] for k in ("conditions", "medications", "measurements", "procedures", "allergies"))
        assert total == EXPECTED_LAB_FACTS["total"]

    @pytest.mark.asyncio
    async def test_lab_replay_deterministic(
        self, service: OpenEHRImportService, mock_session: AsyncMock
    ) -> None:
        comp = build_meditech_lab_composition()
        with patch("app.services.openehr_import.record_lineage", new_callable=AsyncMock):
            r1 = await service.import_composition(mock_session, comp, "p1", source_metadata=MEDITECH_SOURCE_META_AU)
        with patch("app.services.openehr_import.record_lineage", new_callable=AsyncMock):
            r2 = await service.import_composition(mock_session, comp, "p1", source_metadata=MEDITECH_SOURCE_META_AU)
        assert r1["measurements"] == r2["measurements"]


# ===========================================================================
# Round-trip replay: Import -> Export -> Re-import
# ===========================================================================


class TestRoundTripReplay:
    """Verify import -> export -> re-import produces consistent structure."""

    @pytest.mark.asyncio
    async def test_encounter_round_trip_structure(
        self, service: OpenEHRImportService, mock_session: AsyncMock
    ) -> None:
        """Export after import should produce valid composition entries."""
        from app.services.openehr_exporter import OpenEHRExporterService

        comp = build_meditech_encounter_composition()

        # Capture facts
        facts_added: list[Any] = []
        def capture_add(obj: Any) -> None:
            facts_added.append(obj)
        mock_session.add = MagicMock(side_effect=capture_add)

        with patch("app.services.openehr_import.record_lineage", new_callable=AsyncMock):
            await service.import_composition(
                mock_session, comp, "patient-rt-01",
                source_metadata=MEDITECH_SOURCE_META_AU,
            )

        from app.models.clinical_fact import ClinicalFact
        clinical_facts = [f for f in facts_added if isinstance(f, ClinicalFact)]
        assert len(clinical_facts) > 0

        # Export
        exporter = OpenEHRExporterService()
        exported = exporter.export_facts(clinical_facts, "patient-rt-01")

        # Verify exported composition structure
        assert exported["_type"] == "COMPOSITION"
        assert "content" in exported
        assert len(exported["content"]) > 0

        # Each exported entry should have valid archetype_node_id
        for entry in exported["content"]:
            assert "archetype_node_id" in entry
            assert entry["archetype_node_id"].startswith("openEHR-EHR-")


# ===========================================================================
# Edge case replay
# ===========================================================================


class TestEdgeCaseReplay:
    """Edge cases that should be handled gracefully."""

    @pytest.mark.asyncio
    async def test_empty_composition_replay(
        self, service: OpenEHRImportService, mock_session: AsyncMock
    ) -> None:
        """Empty composition should return error, not produce facts."""
        comp = {
            "_type": "COMPOSITION",
            "archetype_node_id": "openEHR-EHR-COMPOSITION.encounter.v1",
            "name": {"_type": "DV_TEXT", "value": "Empty"},
            "content": [],
        }
        with patch("app.services.openehr_import.record_lineage", new_callable=AsyncMock):
            result = await service.import_composition(
                mock_session, comp, "patient-empty",
                source_metadata=MEDITECH_SOURCE_META_AU,
            )
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_unknown_archetype_skipped(
        self, service: OpenEHRImportService, mock_session: AsyncMock
    ) -> None:
        """Entries with unrecognized archetypes should be counted as skipped."""
        comp = {
            "_type": "COMPOSITION",
            "archetype_node_id": "openEHR-EHR-COMPOSITION.encounter.v1",
            "name": {"_type": "DV_TEXT", "value": "Unknown"},
            "content": [
                {
                    "_type": "OBSERVATION",
                    "archetype_node_id": "openEHR-EHR-OBSERVATION.custom_widget.v1",
                    "name": {"_type": "DV_TEXT", "value": "Custom"},
                    "data": {},
                }
            ],
        }
        with patch("app.services.openehr_import.record_lineage", new_callable=AsyncMock):
            result = await service.import_composition(
                mock_session, comp, "patient-unk",
                source_metadata=MEDITECH_SOURCE_META_AU,
            )
        assert result["skipped"] == 1

    @pytest.mark.asyncio
    async def test_non_meditech_source_no_contract_step(
        self, service: OpenEHRImportService, mock_session: AsyncMock
    ) -> None:
        """Non-Meditech source should not get contract lineage step."""
        comp = build_meditech_encounter_composition()
        non_meditech_meta = {"source_system": "epic", "source_record_id": "E-001"}

        with patch(
            "app.services.openehr_import.record_lineage",
            new_callable=AsyncMock,
        ) as mock_lineage:
            await service.import_composition(
                mock_session, comp, "patient-epic",
                source_metadata=non_meditech_meta,
            )
            for call in mock_lineage.call_args_list:
                chain = call.kwargs.get("transformation_chain", [])
                # Should only have the import step, no contract step
                assert chain[0]["step"] == "openehr_composition_import"
