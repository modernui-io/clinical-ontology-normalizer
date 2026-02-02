from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.api.clinical_agent import BuildGraphFromEntitiesRequest, ExtractedEntity


def test_build_graph_requires_entities_or_text() -> None:
    with pytest.raises(ValidationError):
        BuildGraphFromEntitiesRequest(patient_id="P001", entities=[])


def test_build_graph_accepts_clinical_text_only() -> None:
    request = BuildGraphFromEntitiesRequest(
        patient_id="P002",
        clinical_text="Patient has hypertension.",
        entities=[],
    )
    assert request.clinical_text


def test_build_graph_accepts_entities_only() -> None:
    entity = ExtractedEntity(
        text="hypertension",
        entity_type="CONDITION",
        confidence=0.9,
        assertion="PRESENT",
    )
    request = BuildGraphFromEntitiesRequest(
        patient_id="P003",
        entities=[entity],
    )
    assert request.entities
