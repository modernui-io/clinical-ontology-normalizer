"""Tests for FHIR Terminology Pagination.

Tests verify:
- _count limits results
- _offset skips correctly
- Pagination metadata in response
- Max page size enforcement
- Empty results at end of dataset
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.terminology import router


def create_test_app(mock_service):
    """Create minimal test app with terminology router."""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def mock_service():
    """Create mock FHIR terminology service."""
    mock = MagicMock()

    mock.get_stats.return_value = {
        "code_systems": {
            "snomed-ct": {"concept_count": 100},
            "icd-10-cm": {"concept_count": 50},
            "rxnorm": {"concept_count": 75},
            "cpt": {"concept_count": 30},
            "loinc": {"concept_count": 60},
        }
    }

    def mock_get_code_system(system_id):
        systems = {
            "snomed-ct": {"resourceType": "CodeSystem", "id": "snomed-ct", "name": "SNOMED CT"},
            "icd-10-cm": {"resourceType": "CodeSystem", "id": "icd-10-cm", "name": "ICD-10-CM"},
            "rxnorm": {"resourceType": "CodeSystem", "id": "rxnorm", "name": "RxNorm"},
            "cpt": {"resourceType": "CodeSystem", "id": "cpt", "name": "CPT"},
            "loinc": {"resourceType": "CodeSystem", "id": "loinc", "name": "LOINC"},
        }
        return systems.get(system_id)

    mock.get_code_system.side_effect = mock_get_code_system

    def mock_get_value_set(vs_id):
        value_sets = {
            "common-conditions": {"resourceType": "ValueSet", "id": "common-conditions"},
            "common-medications": {"resourceType": "ValueSet", "id": "common-medications"},
            "common-procedures": {"resourceType": "ValueSet", "id": "common-procedures"},
            "common-lab-tests": {"resourceType": "ValueSet", "id": "common-lab-tests"},
        }
        return value_sets.get(vs_id)

    mock.get_value_set.side_effect = mock_get_value_set
    return mock


@pytest.fixture
def client(mock_service):
    with patch("app.api.terminology.get_fhir_terminology_service", return_value=mock_service):
        test_app = create_test_app(mock_service)
        yield TestClient(test_app)


class TestCountLimitsResults:
    """Test _count limits results."""

    def test_count_limits_code_systems(self, client):
        response = client.get("/fhir/CodeSystem?_count=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["entry"]) == 2

    def test_count_limits_value_sets(self, client):
        response = client.get("/fhir/ValueSet?_count=1")
        assert response.status_code == 200
        data = response.json()
        assert len(data["entry"]) == 1

    def test_default_count_returns_all_when_less_than_default(self, client):
        response = client.get("/fhir/CodeSystem")
        assert response.status_code == 200
        data = response.json()
        assert len(data["entry"]) == 5

    def test_count_larger_than_total_returns_all(self, client):
        response = client.get("/fhir/CodeSystem?_count=100")
        assert response.status_code == 200
        data = response.json()
        assert len(data["entry"]) == 5


class TestOffsetSkipsCorrectly:
    """Test _offset skips correctly."""

    def test_offset_skips_entries(self, client):
        response = client.get("/fhir/CodeSystem?_offset=2&_count=10")
        data = response.json()
        assert len(data["entry"]) == 3  # 5 total - 2 skipped

    def test_offset_zero_returns_from_beginning(self, client):
        response = client.get("/fhir/CodeSystem?_offset=0&_count=2")
        data = response.json()
        assert len(data["entry"]) == 2

    def test_offset_with_count(self, client):
        response = client.get("/fhir/ValueSet?_offset=1&_count=2")
        data = response.json()
        assert len(data["entry"]) == 2  # 4 total, skip 1, take 2


class TestPaginationMetadata:
    """Test pagination metadata in response."""

    def test_total_is_correct(self, client):
        response = client.get("/fhir/CodeSystem?_count=2")
        data = response.json()
        assert data["total"] == 5

    def test_has_link_array(self, client):
        response = client.get("/fhir/CodeSystem?_count=2")
        data = response.json()
        assert "link" in data

    def test_self_link_present(self, client):
        response = client.get("/fhir/CodeSystem?_count=2&_offset=0")
        data = response.json()
        self_links = [l for l in data["link"] if l["relation"] == "self"]
        assert len(self_links) == 1

    def test_next_link_when_more_results(self, client):
        response = client.get("/fhir/CodeSystem?_count=2&_offset=0")
        data = response.json()
        next_links = [l for l in data["link"] if l["relation"] == "next"]
        assert len(next_links) == 1
        assert "_offset=2" in next_links[0]["url"]

    def test_previous_link_when_offset_positive(self, client):
        response = client.get("/fhir/CodeSystem?_count=2&_offset=2")
        data = response.json()
        prev_links = [l for l in data["link"] if l["relation"] == "previous"]
        assert len(prev_links) == 1
        assert "_offset=0" in prev_links[0]["url"]

    def test_no_next_link_at_end(self, client):
        response = client.get("/fhir/CodeSystem?_count=10&_offset=0")
        data = response.json()
        next_links = [l for l in data["link"] if l["relation"] == "next"]
        assert len(next_links) == 0

    def test_no_previous_link_at_start(self, client):
        response = client.get("/fhir/CodeSystem?_count=2&_offset=0")
        data = response.json()
        prev_links = [l for l in data["link"] if l["relation"] == "previous"]
        assert len(prev_links) == 0


class TestMaxPageSizeEnforcement:
    """Test max page size enforcement."""

    def test_count_over_100_rejected(self, client):
        response = client.get("/fhir/CodeSystem?_count=101")
        assert response.status_code == 422

    def test_count_exactly_100_accepted(self, client):
        response = client.get("/fhir/CodeSystem?_count=100")
        assert response.status_code == 200

    def test_count_zero_rejected(self, client):
        response = client.get("/fhir/CodeSystem?_count=0")
        assert response.status_code == 422

    def test_negative_offset_rejected(self, client):
        response = client.get("/fhir/CodeSystem?_offset=-1")
        assert response.status_code == 422


class TestEmptyResultsAtEnd:
    """Test empty results at end of dataset."""

    def test_offset_beyond_total_returns_empty(self, client):
        response = client.get("/fhir/CodeSystem?_offset=100&_count=10")
        data = response.json()
        assert len(data["entry"]) == 0
        assert data["total"] == 5

    def test_offset_at_exact_end_returns_empty(self, client):
        response = client.get("/fhir/CodeSystem?_offset=5&_count=10")
        data = response.json()
        assert len(data["entry"]) == 0

    def test_value_sets_offset_beyond_returns_empty(self, client):
        response = client.get("/fhir/ValueSet?_offset=10&_count=5")
        data = response.json()
        assert len(data["entry"]) == 0
        assert data["total"] == 4
