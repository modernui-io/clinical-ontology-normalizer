"""Tests for batch processing API."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.batch import (
    BatchConceptLookupRequest,
    BatchConceptSearchRequest,
    BatchFailureMode,
    BatchJobStatus,
    BatchOperationType,
    BatchPathRequest,
    BatchPatientSimilarityRequest,
    BatchProgress,
    BatchRelationshipRequest,
    _batch_jobs,
    _batch_results,
    router,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def clear_jobs():
    """Clear job storage before and after tests."""
    _batch_jobs.clear()
    _batch_results.clear()
    yield
    _batch_jobs.clear()
    _batch_results.clear()


# =============================================================================
# Request Model Tests
# =============================================================================


class TestBatchConceptLookupRequest:
    """Test BatchConceptLookupRequest validation."""

    def test_valid_request(self) -> None:
        """Test valid request creation."""
        request = BatchConceptLookupRequest(
            concept_ids=[1, 2, 3],
            include_relationships=True,
            include_ancestors=True,
            max_ancestor_depth=5,
        )
        assert len(request.concept_ids) == 3
        assert request.include_relationships is True

    def test_empty_concept_ids(self) -> None:
        """Test empty concept IDs fails validation."""
        with pytest.raises(ValueError):
            BatchConceptLookupRequest(concept_ids=[])

    def test_too_many_concept_ids(self) -> None:
        """Test too many concept IDs fails validation."""
        with pytest.raises(ValueError):
            BatchConceptLookupRequest(concept_ids=list(range(1001)))

    def test_negative_concept_id(self) -> None:
        """Test negative concept ID fails validation."""
        with pytest.raises(ValueError):
            BatchConceptLookupRequest(concept_ids=[1, -2, 3])

    def test_zero_concept_id(self) -> None:
        """Test zero concept ID fails validation."""
        with pytest.raises(ValueError):
            BatchConceptLookupRequest(concept_ids=[1, 0, 3])

    def test_default_failure_mode(self) -> None:
        """Test default failure mode is continue_on_error."""
        request = BatchConceptLookupRequest(concept_ids=[1])
        assert request.failure_mode == BatchFailureMode.CONTINUE_ON_ERROR


class TestBatchRelationshipRequest:
    """Test BatchRelationshipRequest validation."""

    def test_valid_request(self) -> None:
        """Test valid request creation."""
        request = BatchRelationshipRequest(
            source_concept_ids=[100, 200, 300],
            relationship_types=["IS_A", "PART_OF"],
            include_reverse=True,
        )
        assert len(request.source_concept_ids) == 3
        assert request.include_reverse is True

    def test_empty_source_ids(self) -> None:
        """Test empty source IDs fails validation."""
        with pytest.raises(ValueError):
            BatchRelationshipRequest(source_concept_ids=[])


class TestBatchPathRequest:
    """Test BatchPathRequest validation."""

    def test_valid_request(self) -> None:
        """Test valid request creation."""
        request = BatchPathRequest(
            pairs=[(1, 2), (3, 4)],
            max_path_length=7,
        )
        assert len(request.pairs) == 2
        assert request.max_path_length == 7

    def test_empty_pairs(self) -> None:
        """Test empty pairs fails validation."""
        with pytest.raises(ValueError):
            BatchPathRequest(pairs=[])

    def test_too_many_pairs(self) -> None:
        """Test too many pairs fails validation."""
        pairs = [(i, i + 1) for i in range(101)]
        with pytest.raises(ValueError):
            BatchPathRequest(pairs=pairs)


class TestBatchConceptSearchRequest:
    """Test BatchConceptSearchRequest validation."""

    def test_valid_request(self) -> None:
        """Test valid request creation."""
        request = BatchConceptSearchRequest(
            queries=["diabetes", "hypertension"],
            vocabulary_ids=["SNOMED", "ICD10CM"],
            max_results_per_query=50,
        )
        assert len(request.queries) == 2
        assert request.max_results_per_query == 50

    def test_empty_queries(self) -> None:
        """Test empty queries fails validation."""
        with pytest.raises(ValueError):
            BatchConceptSearchRequest(queries=[])


class TestBatchPatientSimilarityRequest:
    """Test BatchPatientSimilarityRequest validation."""

    def test_valid_request(self) -> None:
        """Test valid request creation."""
        request = BatchPatientSimilarityRequest(
            patient_ids=["P001", "P002"],
            similarity_metric="jaccard",
            top_k=20,
        )
        assert len(request.patient_ids) == 2
        assert request.top_k == 20

    def test_min_similarity_bounds(self) -> None:
        """Test min_similarity bounds validation."""
        request = BatchPatientSimilarityRequest(
            patient_ids=["P001"],
            min_similarity=0.5,
        )
        assert request.min_similarity == 0.5

        with pytest.raises(ValueError):
            BatchPatientSimilarityRequest(
                patient_ids=["P001"],
                min_similarity=1.5,
            )


# =============================================================================
# Enum Tests
# =============================================================================


class TestBatchOperationType:
    """Test BatchOperationType enum."""

    def test_all_types(self) -> None:
        """Test all operation types exist."""
        assert BatchOperationType.CONCEPT_LOOKUP.value == "concept_lookup"
        assert BatchOperationType.RELATIONSHIP_QUERY.value == "relationship_query"
        assert BatchOperationType.PATH_FINDING.value == "path_finding"
        assert BatchOperationType.CONCEPT_SEARCH.value == "concept_search"
        assert BatchOperationType.PATIENT_SIMILARITY.value == "patient_similarity"
        assert BatchOperationType.GRAPH_TRAVERSAL.value == "graph_traversal"


class TestBatchJobStatus:
    """Test BatchJobStatus enum."""

    def test_all_statuses(self) -> None:
        """Test all status values exist."""
        assert BatchJobStatus.PENDING.value == "pending"
        assert BatchJobStatus.RUNNING.value == "running"
        assert BatchJobStatus.COMPLETED.value == "completed"
        assert BatchJobStatus.FAILED.value == "failed"
        assert BatchJobStatus.CANCELLED.value == "cancelled"
        assert BatchJobStatus.PARTIAL.value == "partial"


class TestBatchFailureMode:
    """Test BatchFailureMode enum."""

    def test_all_modes(self) -> None:
        """Test all failure modes exist."""
        assert BatchFailureMode.FAIL_FAST.value == "fail_fast"
        assert BatchFailureMode.CONTINUE_ON_ERROR.value == "continue_on_error"
        assert BatchFailureMode.RETRY_FAILURES.value == "retry_failures"


# =============================================================================
# Progress Tests
# =============================================================================


class TestBatchProgress:
    """Test BatchProgress model."""

    def test_progress_creation(self) -> None:
        """Test progress model creation."""
        progress = BatchProgress(
            job_id="test-job",
            status=BatchJobStatus.RUNNING,
            total_items=100,
            processed_items=50,
            successful_items=48,
            failed_items=2,
            percentage=50.0,
            elapsed_seconds=10.5,
            estimated_remaining_seconds=10.0,
        )
        assert progress.percentage == 50.0
        assert progress.failed_items == 2

    def test_progress_with_errors(self) -> None:
        """Test progress with error messages."""
        progress = BatchProgress(
            job_id="test-job",
            status=BatchJobStatus.PARTIAL,
            total_items=10,
            processed_items=10,
            successful_items=8,
            failed_items=2,
            percentage=100.0,
            elapsed_seconds=5.0,
            errors=["Error 1", "Error 2"],
        )
        assert len(progress.errors) == 2


# =============================================================================
# API Integration Tests (using direct function calls)
# =============================================================================


class TestBatchConceptLookupAPI:
    """Test batch concept lookup API."""

    @pytest.mark.asyncio
    async def test_submit_concept_lookup(self, clear_jobs) -> None:
        """Test submitting a concept lookup job."""
        from app.api.batch import batch_concept_lookup
        from fastapi import BackgroundTasks

        bg_tasks = BackgroundTasks()
        request = BatchConceptLookupRequest(
            concept_ids=[1, 2, 3, 4, 5],
            include_relationships=True,
        )

        response = await batch_concept_lookup(request, bg_tasks)

        assert response.job_id is not None
        assert response.operation_type == BatchOperationType.CONCEPT_LOOKUP
        assert response.total_items == 5
        assert response.status == BatchJobStatus.PENDING
        assert "progress" in response.progress_url
        assert "cancel" in response.cancel_url


class TestBatchRelationshipAPI:
    """Test batch relationship query API."""

    @pytest.mark.asyncio
    async def test_submit_relationship_query(self, clear_jobs) -> None:
        """Test submitting a relationship query job."""
        from app.api.batch import batch_relationship_query
        from fastapi import BackgroundTasks

        bg_tasks = BackgroundTasks()
        request = BatchRelationshipRequest(
            source_concept_ids=[100, 200, 300],
            relationship_types=["IS_A"],
        )

        response = await batch_relationship_query(request, bg_tasks)

        assert response.job_id is not None
        assert response.operation_type == BatchOperationType.RELATIONSHIP_QUERY
        assert response.total_items == 3


class TestBatchPathAPI:
    """Test batch path finding API."""

    @pytest.mark.asyncio
    async def test_submit_path_finding(self, clear_jobs) -> None:
        """Test submitting a path finding job."""
        from app.api.batch import batch_path_finding
        from fastapi import BackgroundTasks

        bg_tasks = BackgroundTasks()
        request = BatchPathRequest(
            pairs=[(1, 100), (2, 200)],
            max_path_length=5,
        )

        response = await batch_path_finding(request, bg_tasks)

        assert response.job_id is not None
        assert response.operation_type == BatchOperationType.PATH_FINDING
        assert response.total_items == 2


class TestBatchSearchAPI:
    """Test batch concept search API."""

    @pytest.mark.asyncio
    async def test_submit_concept_search(self, clear_jobs) -> None:
        """Test submitting a concept search job."""
        from app.api.batch import batch_concept_search
        from fastapi import BackgroundTasks

        bg_tasks = BackgroundTasks()
        request = BatchConceptSearchRequest(
            queries=["diabetes", "hypertension", "asthma"],
        )

        response = await batch_concept_search(request, bg_tasks)

        assert response.job_id is not None
        assert response.operation_type == BatchOperationType.CONCEPT_SEARCH
        assert response.total_items == 3


class TestBatchSimilarityAPI:
    """Test batch patient similarity API."""

    @pytest.mark.asyncio
    async def test_submit_patient_similarity(self, clear_jobs) -> None:
        """Test submitting a patient similarity job."""
        from app.api.batch import batch_patient_similarity
        from fastapi import BackgroundTasks

        bg_tasks = BackgroundTasks()
        request = BatchPatientSimilarityRequest(
            patient_ids=["P001", "P002"],
            similarity_metric="jaccard",
        )

        response = await batch_patient_similarity(request, bg_tasks)

        assert response.job_id is not None
        assert response.operation_type == BatchOperationType.PATIENT_SIMILARITY
        assert response.total_items == 2


# =============================================================================
# Job Management Tests
# =============================================================================


class TestJobManagement:
    """Test job management endpoints."""

    @pytest.mark.asyncio
    async def test_get_job_status(self, clear_jobs) -> None:
        """Test getting job status."""
        from app.api.batch import batch_concept_lookup, get_batch_job_status
        from fastapi import BackgroundTasks

        # Create a job
        bg_tasks = BackgroundTasks()
        request = BatchConceptLookupRequest(concept_ids=[1, 2, 3])
        submit_response = await batch_concept_lookup(request, bg_tasks)

        # Get status
        status = await get_batch_job_status(submit_response.job_id)

        assert status.job_id == submit_response.job_id
        assert status.operation_type == BatchOperationType.CONCEPT_LOOKUP
        assert status.progress.total_items == 3

    @pytest.mark.asyncio
    async def test_get_nonexistent_job(self, clear_jobs) -> None:
        """Test getting non-existent job raises 404."""
        from app.api.batch import get_batch_job_status
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_batch_job_status("nonexistent-job-id")

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_job(self, clear_jobs) -> None:
        """Test cancelling a job."""
        from app.api.batch import batch_concept_lookup, cancel_batch_job
        from fastapi import BackgroundTasks

        # Create a job
        bg_tasks = BackgroundTasks()
        request = BatchConceptLookupRequest(concept_ids=[1, 2, 3])
        submit_response = await batch_concept_lookup(request, bg_tasks)

        # Cancel it
        result = await cancel_batch_job(submit_response.job_id)

        assert result["status"] == "cancelled"
        assert _batch_jobs[submit_response.job_id]["status"] == BatchJobStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_job(self, clear_jobs) -> None:
        """Test cancelling non-existent job raises 404."""
        from app.api.batch import cancel_batch_job
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await cancel_batch_job("nonexistent-job-id")

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_list_jobs(self, clear_jobs) -> None:
        """Test listing jobs."""
        from app.api.batch import batch_concept_lookup, list_batch_jobs
        from fastapi import BackgroundTasks

        # Create multiple jobs
        bg_tasks = BackgroundTasks()
        for i in range(3):
            request = BatchConceptLookupRequest(concept_ids=[i + 1])
            await batch_concept_lookup(request, bg_tasks)

        # List jobs
        result = await list_batch_jobs()

        assert result.total_jobs == 3
        assert len(result.jobs) == 3

    @pytest.mark.asyncio
    async def test_list_jobs_with_filter(self, clear_jobs) -> None:
        """Test listing jobs with status filter."""
        from app.api.batch import (
            batch_concept_lookup,
            cancel_batch_job,
            list_batch_jobs,
        )
        from fastapi import BackgroundTasks

        bg_tasks = BackgroundTasks()

        # Create and cancel one job
        request1 = BatchConceptLookupRequest(concept_ids=[1])
        response1 = await batch_concept_lookup(request1, bg_tasks)
        await cancel_batch_job(response1.job_id)

        # Create pending job
        request2 = BatchConceptLookupRequest(concept_ids=[2])
        await batch_concept_lookup(request2, bg_tasks)

        # Filter by status
        cancelled_jobs = await list_batch_jobs(status=BatchJobStatus.CANCELLED)
        pending_jobs = await list_batch_jobs(status=BatchJobStatus.PENDING)

        assert cancelled_jobs.total_jobs == 1
        assert pending_jobs.total_jobs == 1

    @pytest.mark.asyncio
    async def test_delete_job(self, clear_jobs) -> None:
        """Test deleting a completed job."""
        from app.api.batch import (
            batch_concept_lookup,
            cancel_batch_job,
            delete_batch_job,
        )
        from fastapi import BackgroundTasks

        # Create and cancel a job
        bg_tasks = BackgroundTasks()
        request = BatchConceptLookupRequest(concept_ids=[1])
        response = await batch_concept_lookup(request, bg_tasks)
        await cancel_batch_job(response.job_id)

        # Delete it
        result = await delete_batch_job(response.job_id)

        assert result["deleted"] is True
        assert response.job_id not in _batch_jobs

    @pytest.mark.asyncio
    async def test_delete_running_job_fails(self, clear_jobs) -> None:
        """Test deleting a running job fails."""
        from app.api.batch import batch_concept_lookup, delete_batch_job
        from fastapi import BackgroundTasks, HTTPException

        bg_tasks = BackgroundTasks()
        request = BatchConceptLookupRequest(concept_ids=[1])
        response = await batch_concept_lookup(request, bg_tasks)

        with pytest.raises(HTTPException) as exc_info:
            await delete_batch_job(response.job_id)

        assert exc_info.value.status_code == 400


# =============================================================================
# Background Processing Tests
# =============================================================================


class TestBackgroundProcessing:
    """Test background job processing."""

    @pytest.mark.asyncio
    async def test_concept_lookup_processing(self, clear_jobs) -> None:
        """Test concept lookup job processes correctly."""
        from app.api.batch import (
            _process_concept_lookup_batch,
            batch_concept_lookup,
        )
        from fastapi import BackgroundTasks

        bg_tasks = BackgroundTasks()
        request = BatchConceptLookupRequest(concept_ids=[1, 2, 3])
        response = await batch_concept_lookup(request, bg_tasks)

        # Process the job directly
        await _process_concept_lookup_batch(response.job_id)

        job = _batch_jobs[response.job_id]
        assert job["status"] == BatchJobStatus.COMPLETED
        assert job["processed_items"] == 3
        assert job["successful_items"] == 3
        assert len(_batch_results[response.job_id]) == 3

    @pytest.mark.asyncio
    async def test_relationship_processing(self, clear_jobs) -> None:
        """Test relationship query job processes correctly."""
        from app.api.batch import (
            _process_relationship_batch,
            batch_relationship_query,
        )
        from fastapi import BackgroundTasks

        bg_tasks = BackgroundTasks()
        request = BatchRelationshipRequest(source_concept_ids=[100, 200])
        response = await batch_relationship_query(request, bg_tasks)

        await _process_relationship_batch(response.job_id)

        job = _batch_jobs[response.job_id]
        assert job["status"] == BatchJobStatus.COMPLETED
        assert job["successful_items"] == 2

    @pytest.mark.asyncio
    async def test_path_finding_processing(self, clear_jobs) -> None:
        """Test path finding job processes correctly."""
        from app.api.batch import _process_path_batch, batch_path_finding
        from fastapi import BackgroundTasks

        bg_tasks = BackgroundTasks()
        request = BatchPathRequest(pairs=[(1, 10), (2, 20)])
        response = await batch_path_finding(request, bg_tasks)

        await _process_path_batch(response.job_id)

        job = _batch_jobs[response.job_id]
        assert job["status"] == BatchJobStatus.COMPLETED
        assert job["successful_items"] == 2

    @pytest.mark.asyncio
    async def test_search_processing(self, clear_jobs) -> None:
        """Test search job processes correctly."""
        from app.api.batch import _process_search_batch, batch_concept_search
        from fastapi import BackgroundTasks

        bg_tasks = BackgroundTasks()
        request = BatchConceptSearchRequest(queries=["test1", "test2"])
        response = await batch_concept_search(request, bg_tasks)

        await _process_search_batch(response.job_id)

        job = _batch_jobs[response.job_id]
        assert job["status"] == BatchJobStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_similarity_processing(self, clear_jobs) -> None:
        """Test similarity job processes correctly."""
        from app.api.batch import (
            _process_similarity_batch,
            batch_patient_similarity,
        )
        from fastapi import BackgroundTasks

        bg_tasks = BackgroundTasks()
        request = BatchPatientSimilarityRequest(patient_ids=["P1", "P2"])
        response = await batch_patient_similarity(request, bg_tasks)

        await _process_similarity_batch(response.job_id)

        job = _batch_jobs[response.job_id]
        assert job["status"] == BatchJobStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_job_cancellation_during_processing(self, clear_jobs) -> None:
        """Test job can be cancelled during processing."""
        from app.api.batch import (
            _process_concept_lookup_batch,
            batch_concept_lookup,
        )
        from fastapi import BackgroundTasks

        bg_tasks = BackgroundTasks()
        # Create job with many items
        request = BatchConceptLookupRequest(concept_ids=list(range(1, 101)))
        response = await batch_concept_lookup(request, bg_tasks)

        # Set cancel event before processing
        _batch_jobs[response.job_id]["cancel_event"].set()

        await _process_concept_lookup_batch(response.job_id)

        job = _batch_jobs[response.job_id]
        assert job["status"] == BatchJobStatus.CANCELLED
        # Should have stopped early
        assert job["processed_items"] < 100


# =============================================================================
# Results Tests
# =============================================================================


class TestJobResults:
    """Test job results retrieval."""

    @pytest.mark.asyncio
    async def test_get_results_after_completion(self, clear_jobs) -> None:
        """Test getting results after job completes."""
        from app.api.batch import (
            _process_concept_lookup_batch,
            batch_concept_lookup,
            get_batch_job_results,
        )
        from fastapi import BackgroundTasks

        bg_tasks = BackgroundTasks()
        request = BatchConceptLookupRequest(concept_ids=[1, 2, 3])
        response = await batch_concept_lookup(request, bg_tasks)

        # Process the job
        await _process_concept_lookup_batch(response.job_id)

        # Get results
        results = await get_batch_job_results(response.job_id)

        assert results.job_id == response.job_id
        assert results.status == BatchJobStatus.COMPLETED
        assert results.total_items == 3
        assert len(results.results) == 3
        assert all(r.success for r in results.results)

    @pytest.mark.asyncio
    async def test_get_results_pending_job_fails(self, clear_jobs) -> None:
        """Test getting results from pending job fails."""
        from app.api.batch import batch_concept_lookup, get_batch_job_results
        from fastapi import BackgroundTasks, HTTPException

        bg_tasks = BackgroundTasks()
        request = BatchConceptLookupRequest(concept_ids=[1])
        response = await batch_concept_lookup(request, bg_tasks)

        with pytest.raises(HTTPException) as exc_info:
            await get_batch_job_results(response.job_id)

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_results_pagination(self, clear_jobs) -> None:
        """Test results pagination."""
        from app.api.batch import (
            _process_concept_lookup_batch,
            batch_concept_lookup,
            get_batch_job_results,
        )
        from fastapi import BackgroundTasks

        bg_tasks = BackgroundTasks()
        request = BatchConceptLookupRequest(concept_ids=list(range(1, 21)))
        response = await batch_concept_lookup(request, bg_tasks)

        await _process_concept_lookup_batch(response.job_id)

        # Get first page
        page1 = await get_batch_job_results(response.job_id, offset=0, limit=10)
        assert len(page1.results) == 10
        assert page1.results[0].item_index == 0

        # Get second page
        page2 = await get_batch_job_results(response.job_id, offset=10, limit=10)
        assert len(page2.results) == 10
        assert page2.results[0].item_index == 10


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_single_item_batch(self, clear_jobs) -> None:
        """Test batch with single item."""
        from app.api.batch import (
            _process_concept_lookup_batch,
            batch_concept_lookup,
        )
        from fastapi import BackgroundTasks

        bg_tasks = BackgroundTasks()
        request = BatchConceptLookupRequest(concept_ids=[42])
        response = await batch_concept_lookup(request, bg_tasks)

        await _process_concept_lookup_batch(response.job_id)

        job = _batch_jobs[response.job_id]
        assert job["status"] == BatchJobStatus.COMPLETED
        assert job["successful_items"] == 1

    @pytest.mark.asyncio
    async def test_large_batch(self, clear_jobs) -> None:
        """Test batch with maximum items."""
        from app.api.batch import batch_concept_lookup
        from fastapi import BackgroundTasks

        bg_tasks = BackgroundTasks()
        request = BatchConceptLookupRequest(concept_ids=list(range(1, 1001)))
        response = await batch_concept_lookup(request, bg_tasks)

        assert response.total_items == 1000
        assert response.estimated_duration_seconds is not None

    @pytest.mark.asyncio
    async def test_cancel_already_cancelled_job(self, clear_jobs) -> None:
        """Test cancelling already cancelled job fails."""
        from app.api.batch import batch_concept_lookup, cancel_batch_job
        from fastapi import BackgroundTasks, HTTPException

        bg_tasks = BackgroundTasks()
        request = BatchConceptLookupRequest(concept_ids=[1])
        response = await batch_concept_lookup(request, bg_tasks)

        # Cancel once
        await cancel_batch_job(response.job_id)

        # Try to cancel again
        with pytest.raises(HTTPException) as exc_info:
            await cancel_batch_job(response.job_id)

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_duplicate_concept_ids(self, clear_jobs) -> None:
        """Test batch with duplicate concept IDs."""
        from app.api.batch import (
            _process_concept_lookup_batch,
            batch_concept_lookup,
        )
        from fastapi import BackgroundTasks

        bg_tasks = BackgroundTasks()
        request = BatchConceptLookupRequest(concept_ids=[1, 1, 2, 2, 3])
        response = await batch_concept_lookup(request, bg_tasks)

        await _process_concept_lookup_batch(response.job_id)

        job = _batch_jobs[response.job_id]
        assert job["status"] == BatchJobStatus.COMPLETED
        # Should process all items including duplicates
        assert job["processed_items"] == 5
