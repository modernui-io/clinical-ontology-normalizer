"""Integration tests for MIMIC-IV-Note API endpoints."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

VALID_CSV_CONTENT = """note_id,subject_id,hadm_id,note_type,text
10001,100,200001,Discharge Summary,"Patient admitted with chest pain."
10002,101,200002,Discharge Summary,"Follow-up: hypertension controlled."
"""

INVALID_CSV_CONTENT = """note_id,subject_id
10001,100
"""

EMPTY_TEXT_CSV = """note_id,subject_id,hadm_id,note_type,text
10001,100,200001,Discharge Summary,""
"""


def _get_client() -> TestClient:
    """Create a test client. Imports lazily to avoid import issues in CI."""
    from app.main import app
    return TestClient(app)


class TestMimicValidateEndpoint:
    """Tests for POST /documents/mimic/validate."""

    def test_validate_valid_csv(self) -> None:
        client = _get_client()
        file = io.BytesIO(VALID_CSV_CONTENT.encode("utf-8"))
        response = client.post(
            "/documents/mimic/validate",
            files={"file": ("discharge.csv", file, "text/csv")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["total_rows"] == 2

    def test_validate_invalid_csv(self) -> None:
        client = _get_client()
        file = io.BytesIO(INVALID_CSV_CONTENT.encode("utf-8"))
        response = client.post(
            "/documents/mimic/validate",
            files={"file": ("bad.csv", file, "text/csv")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert len(data["columns_missing"]) > 0

    def test_validate_non_csv_rejected(self) -> None:
        client = _get_client()
        file = io.BytesIO(b"not csv content")
        response = client.post(
            "/documents/mimic/validate",
            files={"file": ("data.txt", file, "text/plain")},
        )
        assert response.status_code == 400
        assert "CSV" in response.json()["detail"]


class TestMimicProgressEndpoint:
    """Tests for GET /documents/mimic/import/{batch_id}/progress."""

    def test_progress_not_found(self) -> None:
        client = _get_client()
        response = client.get("/documents/mimic/import/nonexistent-batch/progress")
        assert response.status_code == 404


class TestMimicMetricsEndpoint:
    """Tests for GET /documents/mimic/metrics."""

    def test_metrics_returns_structure(self) -> None:
        client = _get_client()
        response = client.get("/documents/mimic/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "total_documents" in data
        assert "total_mentions" in data
        assert "concept_coverage_percent" in data
        assert "domain_distribution" in data
        assert "top_unmapped_terms" in data
        assert "avg_processing_time_ms" in data
        assert "recent_documents" in data


class TestMimicUploadEndpoint:
    """Tests for POST /documents/mimic/upload."""

    def test_upload_rejects_non_csv(self) -> None:
        client = _get_client()
        file = io.BytesIO(b"not csv")
        response = client.post(
            "/documents/mimic/upload",
            files={"file": ("data.txt", file, "text/plain")},
        )
        assert response.status_code == 400

    def test_upload_rejects_invalid_csv(self) -> None:
        client = _get_client()
        file = io.BytesIO(INVALID_CSV_CONTENT.encode("utf-8"))
        response = client.post(
            "/documents/mimic/upload",
            files={"file": ("bad.csv", file, "text/csv")},
        )
        assert response.status_code == 422
