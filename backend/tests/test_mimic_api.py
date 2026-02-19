"""Integration tests for MIMIC-IV-Note API endpoints."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

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

API_PREFIX = "/api/v1"


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
            f"{API_PREFIX}/documents/mimic/validate",
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
            f"{API_PREFIX}/documents/mimic/validate",
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
            f"{API_PREFIX}/documents/mimic/validate",
            files={"file": ("data.txt", file, "text/plain")},
        )
        assert response.status_code == 400
        body = response.json()
        assert "CSV" in body.get("detail", "") or "CSV" in body.get("message", "")


class TestMimicProgressEndpoint:
    """Tests for GET /documents/mimic/import/{batch_id}/progress."""

    def test_progress_not_found(self) -> None:
        client = _get_client()
        response = client.get(f"{API_PREFIX}/documents/mimic/import/nonexistent-batch/progress")
        assert response.status_code == 404


class TestMimicMetricsEndpoint:
    """Tests for GET /documents/mimic/metrics."""

    @patch("app.services.mimic_ingestion.MimicIngestionService")
    def test_metrics_returns_structure(self, mock_cls: MagicMock) -> None:
        mock_cls.return_value.get_mimic_metrics.return_value = {
            "total_documents": 0,
            "total_mentions": 0,
            "total_facts": 0,
            "concept_coverage_percent": 0.0,
            "avg_confidence": 0.0,
            "status_breakdown": {},
            "domain_distribution": [],
            "top_unmapped_terms": [],
            "avg_processing_time_ms": 0.0,
            "p50_processing_time_ms": 0.0,
            "p95_processing_time_ms": 0.0,
            "recent_documents": [],
        }
        client = _get_client()
        response = client.get(f"{API_PREFIX}/documents/mimic/metrics")
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
            f"{API_PREFIX}/documents/mimic/upload",
            files={"file": ("data.txt", file, "text/plain")},
        )
        assert response.status_code == 400

    def test_upload_rejects_invalid_csv(self) -> None:
        client = _get_client()
        file = io.BytesIO(INVALID_CSV_CONTENT.encode("utf-8"))
        response = client.post(
            f"{API_PREFIX}/documents/mimic/upload",
            files={"file": ("bad.csv", file, "text/csv")},
        )
        assert response.status_code == 422


class TestMimicRouteRegistration:
    """Regression guard: all MIMIC routes must be under /api/v1."""

    def test_mimic_routes_under_api_v1(self) -> None:
        from app.main import app

        mimic_paths = [
            r.path for r in app.routes
            if hasattr(r, "path") and "/documents/mimic" in r.path
        ]
        assert len(mimic_paths) > 0, "No MIMIC routes found"
        for path in mimic_paths:
            assert path.startswith("/api/v1/"), (
                f"MIMIC route {path} not under /api/v1/ prefix"
            )
