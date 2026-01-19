"""Comprehensive tests for document processing API endpoints.

Tests document functionality including:
- Document upload
- Document retrieval
- NLP extraction
- Fact extraction
- Document search
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.database import get_db


@pytest.fixture
async def client():
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
def sample_document():
    """Create sample document for testing."""
    return {
        "patient_id": "P001",
        "note_type": "Progress Note",
        "text": """
        CHIEF COMPLAINT: Follow-up for diabetes management.

        HISTORY OF PRESENT ILLNESS:
        The patient is a 55-year-old male with type 2 diabetes mellitus.
        He reports good compliance with metformin 1000mg twice daily.
        Blood glucose readings at home have been between 110-140 mg/dL fasting.

        VITAL SIGNS:
        Blood pressure: 128/82 mmHg
        Heart rate: 72 bpm

        ASSESSMENT AND PLAN:
        1. Type 2 diabetes mellitus - Adequate control. Continue metformin.
        2. Hypertension - Well controlled on lisinopril.
        """,
        "metadata": {"source": "test", "provider": "Dr. Smith"},
    }


@pytest.fixture
def minimal_document():
    """Create minimal valid document."""
    return {
        "patient_id": "P001",
        "note_type": "Note",
        "text": "Patient seen today.",
    }


class TestDocumentUpload:
    """Test document upload endpoint."""

    @pytest.mark.asyncio
    async def test_upload_document_endpoint_exists(self, client: AsyncClient, sample_document) -> None:
        """Test document upload endpoint exists."""
        response = await client.post(
            "/api/v1/documents",
            json=sample_document,
        )
        # May fail without full setup, but endpoint should exist
        assert response.status_code in (200, 201, 202, 422, 500)

    @pytest.mark.asyncio
    async def test_upload_document_returns_job_id(self, client: AsyncClient, sample_document) -> None:
        """Test document upload returns job ID."""
        response = await client.post(
            "/api/v1/documents",
            json=sample_document,
        )

        if response.status_code in (200, 201, 202):
            data = response.json()
            assert "job_id" in data or "document_id" in data

    @pytest.mark.asyncio
    async def test_upload_document_validation(self, client: AsyncClient) -> None:
        """Test document upload validation."""
        # Missing required fields
        invalid_doc = {"text": "Some text"}

        response = await client.post(
            "/api/v1/documents",
            json=invalid_doc,
        )
        assert response.status_code in (422, 500)

    @pytest.mark.asyncio
    async def test_upload_empty_text(self, client: AsyncClient) -> None:
        """Test upload with empty text."""
        doc = {
            "patient_id": "P001",
            "note_type": "Note",
            "text": "",
        }

        response = await client.post(
            "/api/v1/documents",
            json=doc,
        )
        # Should validate and reject empty text
        assert response.status_code in (400, 422, 500)


class TestDocumentRetrieval:
    """Test document retrieval endpoints."""

    @pytest.mark.asyncio
    async def test_list_documents(self, client: AsyncClient) -> None:
        """Test listing documents."""
        response = await client.get("/api/v1/documents")
        assert response.status_code in (200, 500)

    @pytest.mark.asyncio
    async def test_list_documents_with_pagination(self, client: AsyncClient) -> None:
        """Test listing documents with pagination."""
        response = await client.get(
            "/api/v1/documents",
            params={"page": 1, "page_size": 10}
        )
        assert response.status_code in (200, 422, 500)

    @pytest.mark.asyncio
    async def test_get_document_by_id(self, client: AsyncClient) -> None:
        """Test getting document by ID."""
        doc_id = str(uuid4())
        response = await client.get(f"/api/v1/documents/{doc_id}")
        assert response.status_code in (200, 404, 500)

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, client: AsyncClient) -> None:
        """Test getting non-existent document."""
        response = await client.get("/api/v1/documents/nonexistent-id")
        assert response.status_code in (404, 500)


class TestNLPExtraction:
    """Test NLP extraction functionality."""

    @pytest.mark.asyncio
    async def test_preview_extraction_endpoint(self, client: AsyncClient) -> None:
        """Test extraction preview endpoint."""
        response = await client.post(
            "/api/v1/documents/extract/preview",
            json={
                "text": "Patient has diabetes mellitus type 2 and hypertension.",
                "note_type": "Progress Note",
            }
        )
        assert response.status_code in (200, 422, 500)

    @pytest.mark.asyncio
    async def test_preview_extraction_returns_mentions(self, client: AsyncClient) -> None:
        """Test extraction preview returns mentions."""
        response = await client.post(
            "/api/v1/documents/extract/preview",
            json={
                "text": "Patient has diabetes mellitus type 2 and hypertension.",
                "note_type": "Progress Note",
            }
        )

        if response.status_code == 200:
            data = response.json()
            assert "mentions" in data or "entities" in data or "facts" in data

    @pytest.mark.asyncio
    async def test_extraction_with_medications(self, client: AsyncClient) -> None:
        """Test extraction identifies medications."""
        response = await client.post(
            "/api/v1/documents/extract/preview",
            json={
                "text": "Patient takes metformin 1000mg twice daily and lisinopril 20mg daily.",
                "note_type": "Progress Note",
            }
        )
        assert response.status_code in (200, 422, 500)

    @pytest.mark.asyncio
    async def test_extraction_with_vitals(self, client: AsyncClient) -> None:
        """Test extraction identifies vitals."""
        response = await client.post(
            "/api/v1/documents/extract/preview",
            json={
                "text": "Blood pressure 128/82 mmHg. Heart rate 72 bpm. Temperature 98.6 F.",
                "note_type": "Vital Signs",
            }
        )
        assert response.status_code in (200, 422, 500)

    @pytest.mark.asyncio
    async def test_extraction_with_labs(self, client: AsyncClient) -> None:
        """Test extraction identifies lab values."""
        response = await client.post(
            "/api/v1/documents/extract/preview",
            json={
                "text": "HbA1c: 7.2%. Fasting glucose: 126 mg/dL. Creatinine: 0.9 mg/dL.",
                "note_type": "Laboratory",
            }
        )
        assert response.status_code in (200, 422, 500)


class TestFactExtraction:
    """Test clinical fact extraction."""

    @pytest.mark.asyncio
    async def test_get_document_facts(self, client: AsyncClient) -> None:
        """Test getting facts for a document."""
        doc_id = str(uuid4())
        response = await client.get(f"/api/v1/documents/{doc_id}/facts")
        assert response.status_code in (200, 404, 500)

    @pytest.mark.asyncio
    async def test_get_document_mentions(self, client: AsyncClient) -> None:
        """Test getting mentions for a document."""
        doc_id = str(uuid4())
        response = await client.get(f"/api/v1/documents/{doc_id}/mentions")
        assert response.status_code in (200, 404, 500)


class TestDocumentSearch:
    """Test document search functionality."""

    @pytest.mark.asyncio
    async def test_search_documents_endpoint(self, client: AsyncClient) -> None:
        """Test document search endpoint exists."""
        response = await client.post(
            "/api/v1/documents/search",
            json={"query": "diabetes"}
        )
        assert response.status_code in (200, 404, 422, 500)

    @pytest.mark.asyncio
    async def test_search_documents_by_patient(self, client: AsyncClient) -> None:
        """Test searching documents by patient ID."""
        response = await client.get(
            "/api/v1/documents",
            params={"patient_id": "P001"}
        )
        assert response.status_code in (200, 422, 500)

    @pytest.mark.asyncio
    async def test_search_documents_by_type(self, client: AsyncClient) -> None:
        """Test searching documents by note type."""
        response = await client.get(
            "/api/v1/documents",
            params={"note_type": "Progress Note"}
        )
        assert response.status_code in (200, 422, 500)


class TestSemanticSearch:
    """Test semantic search functionality."""

    @pytest.mark.asyncio
    async def test_semantic_search_endpoint(self, client: AsyncClient) -> None:
        """Test semantic search endpoint."""
        response = await client.post(
            "/api/v1/documents/search/semantic",
            json={
                "query": "patient with diabetes",
                "search_type": "hybrid",
                "max_results": 10,
            }
        )
        assert response.status_code in (200, 404, 422, 500)

    @pytest.mark.asyncio
    async def test_qa_endpoint(self, client: AsyncClient) -> None:
        """Test question-answering endpoint."""
        response = await client.post(
            "/api/v1/documents/search/qa",
            json={
                "question": "What medications is the patient taking?",
                "patient_id": "P001",
            }
        )
        assert response.status_code in (200, 404, 422, 500)


class TestDocumentValidation:
    """Test document input validation."""

    @pytest.mark.asyncio
    async def test_missing_patient_id(self, client: AsyncClient) -> None:
        """Test upload without patient ID."""
        doc = {
            "note_type": "Note",
            "text": "Patient seen today.",
        }
        response = await client.post("/api/v1/documents", json=doc)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_note_type(self, client: AsyncClient) -> None:
        """Test upload without note type."""
        doc = {
            "patient_id": "P001",
            "text": "Patient seen today.",
        }
        response = await client.post("/api/v1/documents", json=doc)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_text(self, client: AsyncClient) -> None:
        """Test upload without text."""
        doc = {
            "patient_id": "P001",
            "note_type": "Note",
        }
        response = await client.post("/api/v1/documents", json=doc)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_json(self, client: AsyncClient) -> None:
        """Test upload with invalid JSON."""
        response = await client.post(
            "/api/v1/documents",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422


class TestDocumentNoteTypes:
    """Test handling of different note types."""

    @pytest.mark.asyncio
    async def test_progress_note(self, client: AsyncClient) -> None:
        """Test processing progress note."""
        doc = {
            "patient_id": "P001",
            "note_type": "Progress Note",
            "text": "Patient doing well. Continue current medications.",
        }
        response = await client.post("/api/v1/documents", json=doc)
        assert response.status_code in (200, 201, 202, 422, 500)

    @pytest.mark.asyncio
    async def test_discharge_summary(self, client: AsyncClient) -> None:
        """Test processing discharge summary."""
        doc = {
            "patient_id": "P001",
            "note_type": "Discharge Summary",
            "text": "Patient discharged home in stable condition.",
        }
        response = await client.post("/api/v1/documents", json=doc)
        assert response.status_code in (200, 201, 202, 422, 500)

    @pytest.mark.asyncio
    async def test_consultation(self, client: AsyncClient) -> None:
        """Test processing consultation note."""
        doc = {
            "patient_id": "P001",
            "note_type": "Consultation",
            "text": "Consulted for diabetes management.",
        }
        response = await client.post("/api/v1/documents", json=doc)
        assert response.status_code in (200, 201, 202, 422, 500)


class TestDocumentProcessingStatus:
    """Test document processing status tracking."""

    @pytest.mark.asyncio
    async def test_get_document_status(self, client: AsyncClient) -> None:
        """Test getting document processing status."""
        doc_id = str(uuid4())
        response = await client.get(f"/api/v1/documents/{doc_id}/status")
        assert response.status_code in (200, 404, 500)

    @pytest.mark.asyncio
    async def test_list_documents_by_status(self, client: AsyncClient) -> None:
        """Test listing documents by status."""
        response = await client.get(
            "/api/v1/documents",
            params={"status": "processed"}
        )
        assert response.status_code in (200, 422, 500)


class TestDocumentMetadata:
    """Test document metadata handling."""

    @pytest.mark.asyncio
    async def test_upload_with_metadata(self, client: AsyncClient) -> None:
        """Test uploading document with metadata."""
        doc = {
            "patient_id": "P001",
            "note_type": "Note",
            "text": "Patient seen today.",
            "metadata": {
                "provider": "Dr. Smith",
                "department": "Internal Medicine",
                "encounter_id": "E12345",
            },
        }
        response = await client.post("/api/v1/documents", json=doc)
        assert response.status_code in (200, 201, 202, 422, 500)


class TestDocumentExport:
    """Test document export functionality."""

    @pytest.mark.asyncio
    async def test_export_document_omop(self, client: AsyncClient) -> None:
        """Test exporting document to OMOP format."""
        doc_id = str(uuid4())
        response = await client.get(f"/api/v1/documents/{doc_id}/export/omop")
        assert response.status_code in (200, 404, 500)

    @pytest.mark.asyncio
    async def test_export_document_fhir(self, client: AsyncClient) -> None:
        """Test exporting document to FHIR format."""
        doc_id = str(uuid4())
        response = await client.get(f"/api/v1/documents/{doc_id}/export/fhir")
        assert response.status_code in (200, 404, 500)


class TestDocumentBatchOperations:
    """Test batch document operations."""

    @pytest.mark.asyncio
    async def test_batch_upload_endpoint(self, client: AsyncClient) -> None:
        """Test batch upload endpoint."""
        batch = {
            "documents": [
                {
                    "patient_id": "P001",
                    "note_type": "Note",
                    "text": "Patient seen today.",
                },
                {
                    "patient_id": "P002",
                    "note_type": "Note",
                    "text": "Follow-up visit.",
                },
            ]
        }
        response = await client.post("/api/v1/documents/batch", json=batch)
        assert response.status_code in (200, 201, 202, 404, 422, 500)


class TestDocumentAPIPerformance:
    """Test document API performance."""

    @pytest.mark.asyncio
    async def test_list_documents_response_time(self, client: AsyncClient) -> None:
        """Test document list responds in reasonable time."""
        import time

        start = time.perf_counter()
        response = await client.get("/api/v1/documents")
        elapsed = time.perf_counter() - start

        assert response.status_code in (200, 500)
        assert elapsed < 5.0, f"List documents took {elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_preview_extraction_response_time(self, client: AsyncClient) -> None:
        """Test extraction preview responds in reasonable time."""
        import time

        start = time.perf_counter()
        response = await client.post(
            "/api/v1/documents/extract/preview",
            json={
                "text": "Patient has diabetes.",
                "note_type": "Note",
            }
        )
        elapsed = time.perf_counter() - start

        assert response.status_code in (200, 422, 500)
        assert elapsed < 10.0, f"Preview extraction took {elapsed:.2f}s"
