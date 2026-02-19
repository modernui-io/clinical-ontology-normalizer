"""Tests for document API endpoints."""

from datetime import timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.main import app
from app.schemas import JobStatus


class TestDocumentUpload:
    """Test document upload endpoint."""

    @pytest.fixture
    def valid_document_payload(self) -> dict:
        """Valid document upload payload."""
        return {
            "patient_id": "patient-123",
            "note_type": "progress_note",
            "text": "Patient presents with fever and cough for 3 days.",
            "metadata": {"encounter_date": "2026-01-14"},
        }

    @pytest.mark.asyncio
    async def test_upload_document_returns_201(
        self,
        client_with_mock_db: AsyncClient,
        mock_db_session: MagicMock,
        valid_document_payload: dict,
    ) -> None:
        """Test document upload returns 201 Created."""
        # Mock the document ID that would be assigned by the database
        mock_db_session.add = MagicMock(side_effect=lambda doc: setattr(doc, "id", str(uuid4())))

        response = await client_with_mock_db.post(
            "/documents",
            json=valid_document_payload,
        )
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_upload_document_returns_document_id(
        self,
        client_with_mock_db: AsyncClient,
        mock_db_session: MagicMock,
        valid_document_payload: dict,
    ) -> None:
        """Test upload response contains document_id."""
        mock_db_session.add = MagicMock(side_effect=lambda doc: setattr(doc, "id", str(uuid4())))

        response = await client_with_mock_db.post(
            "/documents",
            json=valid_document_payload,
        )
        data = response.json()
        assert "document_id" in data
        # Should be a valid UUID string
        assert len(data["document_id"]) == 36

    @pytest.mark.asyncio
    async def test_upload_document_returns_job_id(
        self,
        client_with_mock_db: AsyncClient,
        mock_db_session: MagicMock,
        valid_document_payload: dict,
    ) -> None:
        """Test upload response contains job_id."""
        mock_db_session.add = MagicMock(side_effect=lambda doc: setattr(doc, "id", str(uuid4())))

        response = await client_with_mock_db.post(
            "/documents",
            json=valid_document_payload,
        )
        data = response.json()
        assert "job_id" in data
        # Should be a valid UUID string
        assert len(data["job_id"]) == 36

    @pytest.mark.asyncio
    async def test_upload_document_returns_queued_status(
        self,
        client_with_mock_db: AsyncClient,
        mock_db_session: MagicMock,
        valid_document_payload: dict,
    ) -> None:
        """Test upload response has QUEUED status."""
        mock_db_session.add = MagicMock(side_effect=lambda doc: setattr(doc, "id", str(uuid4())))

        response = await client_with_mock_db.post(
            "/documents",
            json=valid_document_payload,
        )
        data = response.json()
        assert data["status"] == JobStatus.QUEUED.value

    @pytest.mark.asyncio
    async def test_upload_document_calls_db_add(
        self,
        client_with_mock_db: AsyncClient,
        mock_db_session: MagicMock,
        valid_document_payload: dict,
    ) -> None:
        """Test that document is added to database session."""
        mock_db_session.add = MagicMock(side_effect=lambda doc: setattr(doc, "id", str(uuid4())))

        await client_with_mock_db.post(
            "/documents",
            json=valid_document_payload,
        )
        assert mock_db_session.add.called

    @pytest.mark.asyncio
    async def test_upload_document_calls_db_flush(
        self,
        client_with_mock_db: AsyncClient,
        mock_db_session: MagicMock,
        valid_document_payload: dict,
    ) -> None:
        """Test that database flush is called to get document ID."""
        mock_db_session.add = MagicMock(side_effect=lambda doc: setattr(doc, "id", str(uuid4())))

        await client_with_mock_db.post(
            "/documents",
            json=valid_document_payload,
        )
        assert mock_db_session.flush.called

    @pytest.mark.asyncio
    async def test_upload_document_missing_patient_id_returns_422(
        self,
        client_with_mock_db: AsyncClient,
    ) -> None:
        """Test upload without patient_id returns validation error."""
        payload = {
            "note_type": "progress_note",
            "text": "Patient presents with fever.",
        }
        response = await client_with_mock_db.post("/documents", json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_upload_document_missing_note_type_returns_422(
        self,
        client_with_mock_db: AsyncClient,
    ) -> None:
        """Test upload without note_type returns validation error."""
        payload = {
            "patient_id": "patient-123",
            "text": "Patient presents with fever.",
        }
        response = await client_with_mock_db.post("/documents", json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_upload_document_missing_text_returns_422(
        self,
        client_with_mock_db: AsyncClient,
    ) -> None:
        """Test upload without text returns validation error."""
        payload = {
            "patient_id": "patient-123",
            "note_type": "progress_note",
        }
        response = await client_with_mock_db.post("/documents", json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_upload_document_empty_text_allowed(
        self,
        client_with_mock_db: AsyncClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test upload with empty text is allowed (edge case)."""
        mock_db_session.add = MagicMock(side_effect=lambda doc: setattr(doc, "id", str(uuid4())))

        payload = {
            "patient_id": "patient-123",
            "note_type": "progress_note",
            "text": "",
        }
        response = await client_with_mock_db.post("/documents", json=payload)
        # Empty string is technically valid
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_upload_document_without_metadata_uses_default(
        self,
        client_with_mock_db: AsyncClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test upload without metadata uses empty dict default."""
        mock_db_session.add = MagicMock(side_effect=lambda doc: setattr(doc, "id", str(uuid4())))

        payload = {
            "patient_id": "patient-123",
            "note_type": "progress_note",
            "text": "Patient presents with fever.",
        }
        response = await client_with_mock_db.post("/documents", json=payload)
        assert response.status_code == 201


class TestDocumentUploadWithSyntheticNotes:
    """Test document upload with synthetic clinical notes."""

    @pytest.mark.asyncio
    async def test_upload_pneumonia_note(
        self,
        client_with_mock_db: AsyncClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test uploading a pneumonia clinical note."""
        mock_db_session.add = MagicMock(side_effect=lambda doc: setattr(doc, "id", str(uuid4())))

        payload = {
            "patient_id": "patient-001",
            "note_type": "progress_note",
            "text": """
            Chief Complaint: Fever and productive cough for 3 days.

            History of Present Illness:
            68-year-old male presents with fever, productive cough with yellowish
            sputum, and shortness of breath. No hemoptysis. Denies chest pain.

            Assessment:
            Community-acquired pneumonia.

            Plan:
            Start azithromycin 500mg PO daily for 5 days.
            """,
            "metadata": {"encounter_type": "outpatient"},
        }
        response = await client_with_mock_db.post("/documents", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "queued"

    @pytest.mark.asyncio
    async def test_upload_discharge_summary(
        self,
        client_with_mock_db: AsyncClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test uploading a discharge summary note."""
        mock_db_session.add = MagicMock(side_effect=lambda doc: setattr(doc, "id", str(uuid4())))

        payload = {
            "patient_id": "patient-002",
            "note_type": "discharge_summary",
            "text": """
            Discharge Summary

            Admission Diagnosis: Acute exacerbation of congestive heart failure
            Discharge Diagnosis: Congestive heart failure, compensated

            Hospital Course:
            Patient was admitted with dyspnea and lower extremity edema.
            Treated with IV furosemide with good diuresis.
            BNP improved from 1500 to 400.

            Discharge Medications:
            - Furosemide 40mg PO BID
            - Lisinopril 10mg PO daily
            - Metoprolol 25mg PO BID
            """,
            "metadata": {"admission_date": "2026-01-10", "discharge_date": "2026-01-14"},
        }
        response = await client_with_mock_db.post("/documents", json=payload)
        assert response.status_code == 201


class TestDocumentUploadJobEnqueue:
    """Test job enqueueing on document upload."""

    @pytest.fixture
    def valid_document_payload(self) -> dict:
        """Valid document upload payload."""
        return {
            "patient_id": "patient-123",
            "note_type": "progress_note",
            "text": "Patient presents with fever and cough for 3 days.",
            "metadata": {"encounter_date": "2026-01-14"},
        }

    @pytest.mark.asyncio
    async def test_upload_enqueues_job(
        self,
        mock_db_session: MagicMock,
        mock_enqueue_job: MagicMock,
        valid_document_payload: dict,
    ) -> None:
        """Test that document upload enqueues a processing job."""
        mock_db_session.add = MagicMock(side_effect=lambda doc: setattr(doc, "id", str(uuid4())))

        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db

        with patch("app.api.documents.documents_core.enqueue_job", mock_enqueue_job):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test/api/v1",
            ) as ac:
                await ac.post("/documents", json=valid_document_payload)

        app.dependency_overrides.clear()
        assert mock_enqueue_job.called

    @pytest.mark.asyncio
    async def test_upload_enqueues_to_document_queue(
        self,
        mock_db_session: MagicMock,
        mock_enqueue_job: MagicMock,
        valid_document_payload: dict,
    ) -> None:
        """Test that job is enqueued to the document processing queue."""
        mock_db_session.add = MagicMock(side_effect=lambda doc: setattr(doc, "id", str(uuid4())))

        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db

        with patch("app.api.documents.documents_core.enqueue_job", mock_enqueue_job):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test/api/v1",
            ) as ac:
                await ac.post("/documents", json=valid_document_payload)

        app.dependency_overrides.clear()
        # Check that enqueue_job was called with the correct queue name
        call_kwargs = mock_enqueue_job.call_args
        assert call_kwargs.kwargs.get("queue_name") == "document_processing"

    @pytest.mark.asyncio
    async def test_upload_enqueues_with_job_id(
        self,
        mock_db_session: MagicMock,
        mock_enqueue_job: MagicMock,
        valid_document_payload: dict,
    ) -> None:
        """Test that job_id in response matches the enqueued job."""
        mock_db_session.add = MagicMock(side_effect=lambda doc: setattr(doc, "id", str(uuid4())))

        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db

        with patch("app.api.documents.documents_core.enqueue_job", mock_enqueue_job):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test/api/v1",
            ) as ac:
                response = await ac.post("/documents", json=valid_document_payload)

        app.dependency_overrides.clear()
        data = response.json()
        # The job_id in response should match what was passed to enqueue_job
        call_kwargs = mock_enqueue_job.call_args
        assert str(call_kwargs.kwargs.get("job_id")) == data["job_id"]

    @pytest.mark.asyncio
    async def test_upload_succeeds_when_redis_unavailable(
        self,
        mock_db_session: MagicMock,
        valid_document_payload: dict,
    ) -> None:
        """Test that upload succeeds even when Redis is unavailable."""
        mock_db_session.add = MagicMock(side_effect=lambda doc: setattr(doc, "id", str(uuid4())))

        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db

        # Mock enqueue_job to raise a connection error
        mock_enqueue = MagicMock(side_effect=ConnectionError("Redis unavailable"))

        with patch("app.api.documents.documents_core.enqueue_job", mock_enqueue):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test/api/v1",
            ) as ac:
                response = await ac.post("/documents", json=valid_document_payload)

        app.dependency_overrides.clear()
        # Upload should still succeed
        assert response.status_code == 201
        data = response.json()
        assert "document_id" in data
        assert data["status"] == "queued"

    @pytest.mark.asyncio
    async def test_upload_succeeds_when_rq_not_installed(
        self,
        mock_db_session: MagicMock,
        valid_document_payload: dict,
    ) -> None:
        """Test that upload succeeds even when RQ is not installed."""
        mock_db_session.add = MagicMock(side_effect=lambda doc: setattr(doc, "id", str(uuid4())))

        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db

        # Mock enqueue_job to raise ImportError (RQ not installed)
        mock_enqueue = MagicMock(side_effect=ImportError("No module named 'rq'"))

        with patch("app.api.documents.documents_core.enqueue_job", mock_enqueue):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test/api/v1",
            ) as ac:
                response = await ac.post("/documents", json=valid_document_payload)

        app.dependency_overrides.clear()
        # Upload should still succeed
        assert response.status_code == 201


class TestDocumentRetrieval:
    """Test document retrieval endpoint."""

    @pytest.mark.asyncio
    async def test_get_document_returns_200(
        self,
        mock_db_session: MagicMock,
        mock_enqueue_job: MagicMock,
    ) -> None:
        """Test that GET /documents/{doc_id} returns 200 for existing document."""
        from datetime import datetime

        doc_id = str(uuid4())
        job_id = uuid4()

        # Create a mock document object
        mock_doc = MagicMock()
        mock_doc.id = doc_id
        mock_doc.patient_id = "patient-123"
        mock_doc.note_type = "progress_note"
        mock_doc.text = "Test clinical note."
        mock_doc.extra_metadata = {"encounter_date": "2026-01-14"}
        mock_doc.status = JobStatus.QUEUED
        mock_doc.job_id = job_id
        mock_doc.created_at = datetime.now(timezone.utc)
        mock_doc.processed_at = None
        mock_doc.owner_id = None

        # Mock the execute method to return a result with our mock document
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_doc
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db

        with patch("app.api.documents.documents_core.enqueue_job", mock_enqueue_job):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test/api/v1",
            ) as ac:
                response = await ac.get(f"/documents/{doc_id}")

        app.dependency_overrides.clear()
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_document_returns_document_data(
        self,
        mock_db_session: MagicMock,
        mock_enqueue_job: MagicMock,
    ) -> None:
        """Test that GET /documents/{doc_id} returns correct document data."""
        from datetime import datetime

        doc_id = str(uuid4())
        job_id = uuid4()

        mock_doc = MagicMock()
        mock_doc.id = doc_id
        mock_doc.patient_id = "patient-456"
        mock_doc.note_type = "discharge_summary"
        mock_doc.text = "Patient discharged in good condition."
        mock_doc.extra_metadata = {"admission_date": "2026-01-10"}
        mock_doc.status = JobStatus.COMPLETED
        mock_doc.job_id = job_id
        mock_doc.created_at = datetime.now(timezone.utc)
        mock_doc.processed_at = datetime.now(timezone.utc)
        mock_doc.owner_id = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_doc
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db

        with patch("app.api.documents.documents_core.enqueue_job", mock_enqueue_job):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test/api/v1",
            ) as ac:
                response = await ac.get(f"/documents/{doc_id}")

        app.dependency_overrides.clear()
        data = response.json()
        assert data["id"] == doc_id
        assert data["patient_id"] == "patient-456"
        assert data["note_type"] == "discharge_summary"
        assert data["text"] == "Patient discharged in good condition."
        assert data["metadata"]["admission_date"] == "2026-01-10"
        assert data["status"] == "completed"
        assert data["job_id"] == str(job_id)

    @pytest.mark.asyncio
    async def test_get_document_returns_404_when_not_found(
        self,
        mock_db_session: MagicMock,
        mock_enqueue_job: MagicMock,
    ) -> None:
        """Test that GET /documents/{doc_id} returns 404 for non-existent document."""
        doc_id = str(uuid4())

        # Mock execute to return None (document not found)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db

        with patch("app.api.documents.documents_core.enqueue_job", mock_enqueue_job):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test/api/v1",
            ) as ac:
                response = await ac.get(f"/documents/{doc_id}")

        app.dependency_overrides.clear()
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_get_document_invalid_uuid_returns_422(
        self,
        mock_db_session: MagicMock,
        mock_enqueue_job: MagicMock,
    ) -> None:
        """Test that GET /documents/{doc_id} returns 422 for invalid UUID."""

        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db

        with patch("app.api.documents.documents_core.enqueue_job", mock_enqueue_job):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test/api/v1",
            ) as ac:
                response = await ac.get("/documents/not-a-valid-uuid")

        app.dependency_overrides.clear()
        assert response.status_code == 422
