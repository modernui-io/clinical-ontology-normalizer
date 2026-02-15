"""P2-027: OpenEHR profile validation suite for generated payloads.

Validates that generated OpenEHR compositions match expected archetypes,
required fields, archetype ID format, and OpenEHR Reference Model data types.

The system does not currently have an OpenEHR export service, so these tests
define the expected structure of OpenEHR compositions and validate helper
functions that generate them. The helpers are defined inline since there is
no existing OpenEHR connector in the codebase.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Minimal OpenEHR composition builder (no existing service in codebase)
# ---------------------------------------------------------------------------

VALID_RM_DATA_TYPES = {
    "DV_TEXT",
    "DV_CODED_TEXT",
    "DV_QUANTITY",
    "DV_DATE_TIME",
    "DV_BOOLEAN",
    "DV_COUNT",
    "DV_PROPORTION",
    "DV_ORDINAL",
    "DV_DURATION",
    "DV_IDENTIFIER",
    "DV_URI",
    "DV_MULTIMEDIA",
}

ARCHETYPE_ID_PATTERN = re.compile(
    r"^openEHR-EHR-[A-Z_]+\.[a-z][a-z0-9_]*(-[a-z][a-z0-9_]*)?\.(v\d+(\.\d+(\.\d+)?)?)$"
)


def build_openehr_composition(
    *,
    archetype_id: str = "openEHR-EHR-COMPOSITION.encounter.v1",
    composer_name: str = "Dr. Smith",
    territory: str = "US",
    language: str = "en",
    content: list[dict[str, Any]] | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a minimal valid OpenEHR composition.

    Args:
        archetype_id: OpenEHR archetype ID for the composition.
        composer_name: Name of the composer (required by RM).
        territory: ISO 3166-1 territory code.
        language: ISO 639-1 language code.
        content: List of content items (SECTION, OBSERVATION, etc.).
        context: EVENT_CONTEXT with start_time, setting, etc.

    Returns:
        Dict representing an OpenEHR COMPOSITION.
    """
    if context is None:
        context = {
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
        }

    composition: dict[str, Any] = {
        "_type": "COMPOSITION",
        "archetype_node_id": archetype_id,
        "name": {"_type": "DV_TEXT", "value": "Clinical Encounter"},
        "language": {
            "_type": "CODE_PHRASE",
            "terminology_id": {"value": "ISO_639-1"},
            "code_string": language,
        },
        "territory": {
            "_type": "CODE_PHRASE",
            "terminology_id": {"value": "ISO_3166-1"},
            "code_string": territory,
        },
        "category": {
            "_type": "DV_CODED_TEXT",
            "value": "event",
            "defining_code": {
                "terminology_id": {"value": "openehr"},
                "code_string": "433",
            },
        },
        "composer": {
            "_type": "PARTY_IDENTIFIED",
            "name": composer_name,
        },
        "context": context,
        "content": content or [],
    }

    return composition


def build_observation_entry(
    *,
    archetype_id: str = "openEHR-EHR-OBSERVATION.blood_pressure.v2",
    systolic: float = 120.0,
    diastolic: float = 80.0,
) -> dict[str, Any]:
    """Build a minimal OBSERVATION entry for a composition."""
    return {
        "_type": "OBSERVATION",
        "archetype_node_id": archetype_id,
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


def _collect_types(obj: Any) -> set[str]:
    """Recursively collect all _type values from an OpenEHR structure."""
    types: set[str] = set()
    if isinstance(obj, dict):
        t = obj.get("_type")
        if t:
            types.add(t)
        for v in obj.values():
            types.update(_collect_types(v))
    elif isinstance(obj, list):
        for item in obj:
            types.update(_collect_types(item))
    return types


# ===========================================================================
# Test Suite: OpenEHR Composition Validation (15+ tests)
# ===========================================================================


class TestOpenEHRCompositionRequiredFields:
    """Test that compositions have required fields: composer, context, content."""

    def test_composition_has_composer(self) -> None:
        """Composition must include a composer element."""
        comp = build_openehr_composition()
        assert "composer" in comp
        assert comp["composer"]["_type"] == "PARTY_IDENTIFIED"
        assert "name" in comp["composer"]

    def test_composition_has_context(self) -> None:
        """Composition must include a context element."""
        comp = build_openehr_composition()
        assert "context" in comp
        assert comp["context"]["_type"] == "EVENT_CONTEXT"

    def test_composition_has_content(self) -> None:
        """Composition must include a content element (list)."""
        comp = build_openehr_composition()
        assert "content" in comp
        assert isinstance(comp["content"], list)

    def test_composition_has_language(self) -> None:
        """Composition must include language."""
        comp = build_openehr_composition()
        assert "language" in comp
        assert comp["language"]["code_string"] == "en"

    def test_composition_has_territory(self) -> None:
        """Composition must include territory."""
        comp = build_openehr_composition()
        assert "territory" in comp
        assert comp["territory"]["code_string"] == "US"

    def test_composition_has_category(self) -> None:
        """Composition must include category."""
        comp = build_openehr_composition()
        assert "category" in comp
        assert comp["category"]["_type"] == "DV_CODED_TEXT"

    def test_composition_has_name(self) -> None:
        """Composition must include name as DV_TEXT."""
        comp = build_openehr_composition()
        assert "name" in comp
        assert comp["name"]["_type"] == "DV_TEXT"


class TestOpenEHRArchetypeIDs:
    """Test that archetype IDs are valid format."""

    def test_valid_composition_archetype_id(self) -> None:
        """Default composition archetype ID matches expected pattern."""
        comp = build_openehr_composition()
        archetype_id = comp["archetype_node_id"]
        assert ARCHETYPE_ID_PATTERN.match(archetype_id), f"Invalid archetype ID: {archetype_id}"

    def test_valid_observation_archetype_id(self) -> None:
        """Observation archetype ID matches expected pattern."""
        obs = build_observation_entry()
        archetype_id = obs["archetype_node_id"]
        assert ARCHETYPE_ID_PATTERN.match(archetype_id), f"Invalid archetype ID: {archetype_id}"

    def test_invalid_archetype_id_rejected(self) -> None:
        """Archetype IDs not matching pattern are detected."""
        invalid_ids = [
            "not-an-archetype",
            "openEHR-EHR-COMPOSITION.v1",  # missing concept
            "openEHR-EHR-OBSERVATION.Blood_Pressure.v1",  # uppercase in concept
            "COMPOSITION.encounter.v1",  # missing prefix
            "openEHR-EHR-COMPOSITION.encounter",  # missing version
        ]
        for bad_id in invalid_ids:
            assert not ARCHETYPE_ID_PATTERN.match(bad_id), f"Should be invalid: {bad_id}"

    def test_versioned_archetype_ids_valid(self) -> None:
        """Archetype IDs with different version formats are accepted."""
        valid_ids = [
            "openEHR-EHR-COMPOSITION.encounter.v1",
            "openEHR-EHR-OBSERVATION.blood_pressure.v2",
            "openEHR-EHR-EVALUATION.problem_diagnosis.v1",
            "openEHR-EHR-INSTRUCTION.medication_order.v3",
            "openEHR-EHR-CLUSTER.dosage.v2",
        ]
        for valid_id in valid_ids:
            assert ARCHETYPE_ID_PATTERN.match(valid_id), f"Should be valid: {valid_id}"


class TestOpenEHRDataTypes:
    """Test that data types match OpenEHR Reference Model."""

    def test_dv_text_structure(self) -> None:
        """DV_TEXT has _type and value fields."""
        comp = build_openehr_composition()
        name = comp["name"]
        assert name["_type"] == "DV_TEXT"
        assert "value" in name
        assert isinstance(name["value"], str)

    def test_dv_coded_text_structure(self) -> None:
        """DV_CODED_TEXT has _type, value, and defining_code."""
        comp = build_openehr_composition()
        category = comp["category"]
        assert category["_type"] == "DV_CODED_TEXT"
        assert "value" in category
        assert "defining_code" in category
        defining_code = category["defining_code"]
        assert "terminology_id" in defining_code
        assert "code_string" in defining_code

    def test_dv_quantity_structure(self) -> None:
        """DV_QUANTITY has _type, magnitude, and units."""
        obs = build_observation_entry(systolic=130.0)
        items = obs["data"]["events"][0]["data"]["items"]
        systolic = items[0]["value"]
        assert systolic["_type"] == "DV_QUANTITY"
        assert "magnitude" in systolic
        assert "units" in systolic
        assert isinstance(systolic["magnitude"], (int, float))
        assert systolic["magnitude"] == 130.0

    def test_dv_date_time_structure(self) -> None:
        """DV_DATE_TIME has _type and value (ISO 8601)."""
        comp = build_openehr_composition()
        start_time = comp["context"]["start_time"]
        assert start_time["_type"] == "DV_DATE_TIME"
        assert "value" in start_time
        # Should be parseable as ISO datetime
        datetime.fromisoformat(start_time["value"])

    def test_all_data_types_are_known_rm_types(self) -> None:
        """All _type values in a composition are known RM types."""
        obs = build_observation_entry()
        comp = build_openehr_composition(content=[obs])
        all_types = _collect_types(comp)

        # These are known OpenEHR RM types (not just data types)
        known_rm_types = VALID_RM_DATA_TYPES | {
            "COMPOSITION",
            "EVENT_CONTEXT",
            "PARTY_IDENTIFIED",
            "CODE_PHRASE",
            "OBSERVATION",
            "HISTORY",
            "POINT_EVENT",
            "ITEM_TREE",
            "ELEMENT",
        }
        unknown = all_types - known_rm_types
        assert not unknown, f"Unknown RM types found: {unknown}"


class TestOpenEHRCompositionWithContent:
    """Test compositions with content entries."""

    def test_composition_with_observation(self) -> None:
        """Composition with an OBSERVATION entry is structurally valid."""
        obs = build_observation_entry()
        comp = build_openehr_composition(content=[obs])
        assert len(comp["content"]) == 1
        assert comp["content"][0]["_type"] == "OBSERVATION"

    def test_observation_has_data_history(self) -> None:
        """OBSERVATION entries contain data with HISTORY type."""
        obs = build_observation_entry()
        assert "data" in obs
        assert obs["data"]["_type"] == "HISTORY"
        assert "events" in obs["data"]
        assert len(obs["data"]["events"]) > 0

    def test_context_has_start_time_and_setting(self) -> None:
        """EVENT_CONTEXT has start_time (DV_DATE_TIME) and setting (DV_CODED_TEXT)."""
        comp = build_openehr_composition()
        ctx = comp["context"]
        assert "start_time" in ctx
        assert ctx["start_time"]["_type"] == "DV_DATE_TIME"
        assert "setting" in ctx
        assert ctx["setting"]["_type"] == "DV_CODED_TEXT"

    def test_custom_composer_name(self) -> None:
        """Composition with custom composer name stores it correctly."""
        comp = build_openehr_composition(composer_name="Dr. Jones")
        assert comp["composer"]["name"] == "Dr. Jones"
