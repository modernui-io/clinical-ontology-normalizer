#!/usr/bin/env python3
"""Standalone test runner for batch API."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types

# Add path first
sys.path.insert(0, ".")

# Create mock modules to avoid import chain issues
mock_app = types.ModuleType("app")
mock_app.__path__ = ["."]
sys.modules["app"] = mock_app

mock_api = types.ModuleType("app.api")
mock_api.__path__ = ["app/api"]
sys.modules["app.api"] = mock_api

passed = 0
failed = 0


def test(name: str, condition: bool) -> None:
    global passed, failed
    if condition:
        print(f"✓ {name}")
        passed += 1
    else:
        print(f"✗ {name}")
        failed += 1


async def async_test(name: str, test_fn) -> None:
    global passed, failed
    try:
        await test_fn()
        print(f"✓ {name}")
        passed += 1
    except AssertionError as e:
        print(f"✗ {name}: {e}")
        failed += 1
    except Exception as e:
        print(f"✗ {name}: {type(e).__name__}: {e}")
        failed += 1


# Load batch module using importlib to avoid import chain
spec = importlib.util.spec_from_file_location(
    "app.api.batch",
    "app/api/batch.py",
    submodule_search_locations=[]
)
batch_module = importlib.util.module_from_spec(spec)
batch_module.__package__ = "app.api"
sys.modules["app.api.batch"] = batch_module
spec.loader.exec_module(batch_module)

# Import from loaded module
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
    _process_concept_lookup_batch,
    _process_path_batch,
    _process_relationship_batch,
    _process_search_batch,
    _process_similarity_batch,
    batch_concept_lookup,
    batch_concept_search,
    batch_path_finding,
    batch_patient_similarity,
    batch_relationship_query,
    cancel_batch_job,
    delete_batch_job,
    get_batch_job_results,
    get_batch_job_status,
    list_batch_jobs,
)


def clear_jobs():
    """Clear job storage."""
    _batch_jobs.clear()
    _batch_results.clear()


async def run_tests():
    print("=" * 60)
    print("Batch API Tests")
    print("=" * 60)

    # ==========================================================================
    # Request Model Tests
    # ==========================================================================

    print("\n--- Request Model Tests ---")

    # BatchConceptLookupRequest tests
    try:
        request = BatchConceptLookupRequest(
            concept_ids=[1, 2, 3],
            include_relationships=True,
            include_ancestors=True,
            max_ancestor_depth=5,
        )
        test("valid_concept_lookup_request", len(request.concept_ids) == 3)
    except Exception as e:
        test("valid_concept_lookup_request", False)

    try:
        BatchConceptLookupRequest(concept_ids=[])
        test("empty_concept_ids_fails", False)
    except ValueError:
        test("empty_concept_ids_fails", True)

    try:
        BatchConceptLookupRequest(concept_ids=[1, -2, 3])
        test("negative_concept_id_fails", False)
    except ValueError:
        test("negative_concept_id_fails", True)

    try:
        BatchConceptLookupRequest(concept_ids=[1, 0, 3])
        test("zero_concept_id_fails", False)
    except ValueError:
        test("zero_concept_id_fails", True)

    request = BatchConceptLookupRequest(concept_ids=[1])
    test("default_failure_mode", request.failure_mode == BatchFailureMode.CONTINUE_ON_ERROR)

    # BatchRelationshipRequest tests
    try:
        request = BatchRelationshipRequest(
            source_concept_ids=[100, 200, 300],
            relationship_types=["IS_A", "PART_OF"],
            include_reverse=True,
        )
        test("valid_relationship_request", len(request.source_concept_ids) == 3)
    except Exception as e:
        test("valid_relationship_request", False)

    # BatchPathRequest tests
    try:
        request = BatchPathRequest(
            pairs=[(1, 2), (3, 4)],
            max_path_length=7,
        )
        test("valid_path_request", len(request.pairs) == 2)
    except Exception as e:
        test("valid_path_request", False)

    # BatchConceptSearchRequest tests
    try:
        request = BatchConceptSearchRequest(
            queries=["diabetes", "hypertension"],
            vocabulary_ids=["SNOMED", "ICD10CM"],
            max_results_per_query=50,
        )
        test("valid_search_request", len(request.queries) == 2)
    except Exception as e:
        test("valid_search_request", False)

    # BatchPatientSimilarityRequest tests
    try:
        request = BatchPatientSimilarityRequest(
            patient_ids=["P001", "P002"],
            similarity_metric="jaccard",
            top_k=20,
        )
        test("valid_similarity_request", len(request.patient_ids) == 2)
    except Exception as e:
        test("valid_similarity_request", False)

    # ==========================================================================
    # Enum Tests
    # ==========================================================================

    print("\n--- Enum Tests ---")

    test("operation_type_concept_lookup", BatchOperationType.CONCEPT_LOOKUP.value == "concept_lookup")
    test("operation_type_relationship", BatchOperationType.RELATIONSHIP_QUERY.value == "relationship_query")
    test("operation_type_path_finding", BatchOperationType.PATH_FINDING.value == "path_finding")
    test("operation_type_search", BatchOperationType.CONCEPT_SEARCH.value == "concept_search")
    test("operation_type_similarity", BatchOperationType.PATIENT_SIMILARITY.value == "patient_similarity")

    test("status_pending", BatchJobStatus.PENDING.value == "pending")
    test("status_running", BatchJobStatus.RUNNING.value == "running")
    test("status_completed", BatchJobStatus.COMPLETED.value == "completed")
    test("status_failed", BatchJobStatus.FAILED.value == "failed")
    test("status_cancelled", BatchJobStatus.CANCELLED.value == "cancelled")
    test("status_partial", BatchJobStatus.PARTIAL.value == "partial")

    test("failure_mode_fail_fast", BatchFailureMode.FAIL_FAST.value == "fail_fast")
    test("failure_mode_continue", BatchFailureMode.CONTINUE_ON_ERROR.value == "continue_on_error")
    test("failure_mode_retry", BatchFailureMode.RETRY_FAILURES.value == "retry_failures")

    # ==========================================================================
    # Progress Model Tests
    # ==========================================================================

    print("\n--- Progress Model Tests ---")

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
    test("progress_percentage", progress.percentage == 50.0)
    test("progress_failed_items", progress.failed_items == 2)

    # ==========================================================================
    # API Submit Tests
    # ==========================================================================

    print("\n--- API Submit Tests ---")

    from fastapi import BackgroundTasks

    async def test_submit_concept_lookup():
        clear_jobs()
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

    await async_test("submit_concept_lookup", test_submit_concept_lookup)

    async def test_submit_relationship_query():
        clear_jobs()
        bg_tasks = BackgroundTasks()
        request = BatchRelationshipRequest(
            source_concept_ids=[100, 200, 300],
            relationship_types=["IS_A"],
        )
        response = await batch_relationship_query(request, bg_tasks)
        assert response.job_id is not None
        assert response.operation_type == BatchOperationType.RELATIONSHIP_QUERY
        assert response.total_items == 3

    await async_test("submit_relationship_query", test_submit_relationship_query)

    async def test_submit_path_finding():
        clear_jobs()
        bg_tasks = BackgroundTasks()
        request = BatchPathRequest(
            pairs=[(1, 100), (2, 200)],
            max_path_length=5,
        )
        response = await batch_path_finding(request, bg_tasks)
        assert response.job_id is not None
        assert response.operation_type == BatchOperationType.PATH_FINDING
        assert response.total_items == 2

    await async_test("submit_path_finding", test_submit_path_finding)

    async def test_submit_concept_search():
        clear_jobs()
        bg_tasks = BackgroundTasks()
        request = BatchConceptSearchRequest(
            queries=["diabetes", "hypertension", "asthma"],
        )
        response = await batch_concept_search(request, bg_tasks)
        assert response.job_id is not None
        assert response.operation_type == BatchOperationType.CONCEPT_SEARCH
        assert response.total_items == 3

    await async_test("submit_concept_search", test_submit_concept_search)

    async def test_submit_patient_similarity():
        clear_jobs()
        bg_tasks = BackgroundTasks()
        request = BatchPatientSimilarityRequest(
            patient_ids=["P001", "P002"],
            similarity_metric="jaccard",
        )
        response = await batch_patient_similarity(request, bg_tasks)
        assert response.job_id is not None
        assert response.operation_type == BatchOperationType.PATIENT_SIMILARITY
        assert response.total_items == 2

    await async_test("submit_patient_similarity", test_submit_patient_similarity)

    # ==========================================================================
    # Job Management Tests
    # ==========================================================================

    print("\n--- Job Management Tests ---")

    async def test_get_job_status():
        clear_jobs()
        bg_tasks = BackgroundTasks()
        request = BatchConceptLookupRequest(concept_ids=[1, 2, 3])
        submit_response = await batch_concept_lookup(request, bg_tasks)
        status = await get_batch_job_status(submit_response.job_id)
        assert status.job_id == submit_response.job_id
        assert status.operation_type == BatchOperationType.CONCEPT_LOOKUP
        assert status.progress.total_items == 3

    await async_test("get_job_status", test_get_job_status)

    async def test_get_nonexistent_job():
        clear_jobs()
        from fastapi import HTTPException
        try:
            await get_batch_job_status("nonexistent-job-id")
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 404

    await async_test("get_nonexistent_job", test_get_nonexistent_job)

    async def test_cancel_job():
        clear_jobs()
        bg_tasks = BackgroundTasks()
        request = BatchConceptLookupRequest(concept_ids=[1, 2, 3])
        submit_response = await batch_concept_lookup(request, bg_tasks)
        result = await cancel_batch_job(submit_response.job_id)
        assert result["status"] == "cancelled"
        assert _batch_jobs[submit_response.job_id]["status"] == BatchJobStatus.CANCELLED

    await async_test("cancel_job", test_cancel_job)

    async def test_list_jobs():
        clear_jobs()
        bg_tasks = BackgroundTasks()
        for i in range(3):
            request = BatchConceptLookupRequest(concept_ids=[i + 1])
            await batch_concept_lookup(request, bg_tasks)
        result = await list_batch_jobs(status=None, operation_type=None, limit=50, offset=0)
        assert result.total_jobs == 3
        assert len(result.jobs) == 3

    await async_test("list_jobs", test_list_jobs)

    async def test_list_jobs_with_filter():
        clear_jobs()
        bg_tasks = BackgroundTasks()
        request1 = BatchConceptLookupRequest(concept_ids=[1])
        response1 = await batch_concept_lookup(request1, bg_tasks)
        await cancel_batch_job(response1.job_id)
        request2 = BatchConceptLookupRequest(concept_ids=[2])
        await batch_concept_lookup(request2, bg_tasks)
        cancelled_jobs = await list_batch_jobs(status=BatchJobStatus.CANCELLED, operation_type=None, limit=50, offset=0)
        pending_jobs = await list_batch_jobs(status=BatchJobStatus.PENDING, operation_type=None, limit=50, offset=0)
        assert cancelled_jobs.total_jobs == 1
        assert pending_jobs.total_jobs == 1

    await async_test("list_jobs_with_filter", test_list_jobs_with_filter)

    async def test_delete_job():
        clear_jobs()
        bg_tasks = BackgroundTasks()
        request = BatchConceptLookupRequest(concept_ids=[1])
        response = await batch_concept_lookup(request, bg_tasks)
        await cancel_batch_job(response.job_id)
        result = await delete_batch_job(response.job_id)
        assert result["deleted"] is True
        assert response.job_id not in _batch_jobs

    await async_test("delete_job", test_delete_job)

    # ==========================================================================
    # Background Processing Tests
    # ==========================================================================

    print("\n--- Background Processing Tests ---")

    async def test_concept_lookup_processing():
        clear_jobs()
        bg_tasks = BackgroundTasks()
        request = BatchConceptLookupRequest(concept_ids=[1, 2, 3])
        response = await batch_concept_lookup(request, bg_tasks)
        await _process_concept_lookup_batch(response.job_id)
        job = _batch_jobs[response.job_id]
        assert job["status"] == BatchJobStatus.COMPLETED
        assert job["processed_items"] == 3
        assert job["successful_items"] == 3
        assert len(_batch_results[response.job_id]) == 3

    await async_test("concept_lookup_processing", test_concept_lookup_processing)

    async def test_relationship_processing():
        clear_jobs()
        bg_tasks = BackgroundTasks()
        request = BatchRelationshipRequest(source_concept_ids=[100, 200])
        response = await batch_relationship_query(request, bg_tasks)
        await _process_relationship_batch(response.job_id)
        job = _batch_jobs[response.job_id]
        assert job["status"] == BatchJobStatus.COMPLETED
        assert job["successful_items"] == 2

    await async_test("relationship_processing", test_relationship_processing)

    async def test_path_finding_processing():
        clear_jobs()
        bg_tasks = BackgroundTasks()
        request = BatchPathRequest(pairs=[(1, 10), (2, 20)])
        response = await batch_path_finding(request, bg_tasks)
        await _process_path_batch(response.job_id)
        job = _batch_jobs[response.job_id]
        assert job["status"] == BatchJobStatus.COMPLETED
        assert job["successful_items"] == 2

    await async_test("path_finding_processing", test_path_finding_processing)

    async def test_search_processing():
        clear_jobs()
        bg_tasks = BackgroundTasks()
        request = BatchConceptSearchRequest(queries=["test1", "test2"])
        response = await batch_concept_search(request, bg_tasks)
        await _process_search_batch(response.job_id)
        job = _batch_jobs[response.job_id]
        assert job["status"] == BatchJobStatus.COMPLETED

    await async_test("search_processing", test_search_processing)

    async def test_similarity_processing():
        clear_jobs()
        bg_tasks = BackgroundTasks()
        request = BatchPatientSimilarityRequest(patient_ids=["P1", "P2"])
        response = await batch_patient_similarity(request, bg_tasks)
        await _process_similarity_batch(response.job_id)
        job = _batch_jobs[response.job_id]
        assert job["status"] == BatchJobStatus.COMPLETED

    await async_test("similarity_processing", test_similarity_processing)

    async def test_job_cancellation_during_processing():
        clear_jobs()
        bg_tasks = BackgroundTasks()
        request = BatchConceptLookupRequest(concept_ids=list(range(1, 101)))
        response = await batch_concept_lookup(request, bg_tasks)
        _batch_jobs[response.job_id]["cancel_event"].set()
        await _process_concept_lookup_batch(response.job_id)
        job = _batch_jobs[response.job_id]
        assert job["status"] == BatchJobStatus.CANCELLED
        assert job["processed_items"] < 100

    await async_test("job_cancellation_during_processing", test_job_cancellation_during_processing)

    # ==========================================================================
    # Results Tests
    # ==========================================================================

    print("\n--- Results Tests ---")

    async def test_get_results_after_completion():
        clear_jobs()
        bg_tasks = BackgroundTasks()
        request = BatchConceptLookupRequest(concept_ids=[1, 2, 3])
        response = await batch_concept_lookup(request, bg_tasks)
        await _process_concept_lookup_batch(response.job_id)
        results = await get_batch_job_results(response.job_id, offset=0, limit=100)
        assert results.job_id == response.job_id
        assert results.status == BatchJobStatus.COMPLETED
        assert results.total_items == 3
        assert len(results.results) == 3
        assert all(r.success for r in results.results)

    await async_test("get_results_after_completion", test_get_results_after_completion)

    async def test_results_pagination():
        clear_jobs()
        bg_tasks = BackgroundTasks()
        request = BatchConceptLookupRequest(concept_ids=list(range(1, 21)))
        response = await batch_concept_lookup(request, bg_tasks)
        await _process_concept_lookup_batch(response.job_id)
        page1 = await get_batch_job_results(response.job_id, offset=0, limit=10)
        assert len(page1.results) == 10
        assert page1.results[0].item_index == 0
        page2 = await get_batch_job_results(response.job_id, offset=10, limit=10)
        assert len(page2.results) == 10
        assert page2.results[0].item_index == 10

    await async_test("results_pagination", test_results_pagination)

    # ==========================================================================
    # Edge Case Tests
    # ==========================================================================

    print("\n--- Edge Case Tests ---")

    async def test_single_item_batch():
        clear_jobs()
        bg_tasks = BackgroundTasks()
        request = BatchConceptLookupRequest(concept_ids=[42])
        response = await batch_concept_lookup(request, bg_tasks)
        await _process_concept_lookup_batch(response.job_id)
        job = _batch_jobs[response.job_id]
        assert job["status"] == BatchJobStatus.COMPLETED
        assert job["successful_items"] == 1

    await async_test("single_item_batch", test_single_item_batch)

    async def test_large_batch():
        clear_jobs()
        bg_tasks = BackgroundTasks()
        request = BatchConceptLookupRequest(concept_ids=list(range(1, 1001)))
        response = await batch_concept_lookup(request, bg_tasks)
        assert response.total_items == 1000
        assert response.estimated_duration_seconds is not None

    await async_test("large_batch", test_large_batch)

    async def test_duplicate_concept_ids():
        clear_jobs()
        bg_tasks = BackgroundTasks()
        request = BatchConceptLookupRequest(concept_ids=[1, 1, 2, 2, 3])
        response = await batch_concept_lookup(request, bg_tasks)
        await _process_concept_lookup_batch(response.job_id)
        job = _batch_jobs[response.job_id]
        assert job["status"] == BatchJobStatus.COMPLETED
        assert job["processed_items"] == 5

    await async_test("duplicate_concept_ids", test_duplicate_concept_ids)

    # Print summary
    print(f"\n{'=' * 60}")
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    if failed == 0:
        print("All tests passed!")
    else:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_tests())
