"""Tests for Clinical Data Management & Data Cleaning (CLINICAL-2).

Covers:
- Seed data verification (queries, rules, results, datasets, domains)
- Data query CRUD (create, read, update, list with all filter combinations)
- Query workflow (answer, close, requery, cancel) with transition validation
- Validation rule CRUD + batch execution
- Validation result listing with filters
- Clinical dataset CRUD + lifecycle (freeze, lock, release, archive)
- CDISC domain listing and conformance checking
- Dataset comparison
- Audit trail
- Data cleaning metrics computation
- Query resolution metrics
- Error handling (404s, 400s, invalid transitions)
- Pagination and edge cases
- API integration tests via httpx
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.clinical_data_management import (
    BatchValidationRequest,
    CDISCStandard,
    ClinicalDatasetCreate,
    ClinicalDatasetUpdate,
    DataLockLevel,
    DataQueryAnswer,
    DataQueryClose,
    DataQueryCreate,
    DataQueryRequery,
    DataQueryUpdate,
    DatasetFreezeRequest,
    DatasetLockRequest,
    DatasetReleaseRequest,
    DatasetStatus,
    QueryCategory,
    QueryStatus,
    ValidationRuleCreate,
    ValidationRuleType,
    ValidationRuleUpdate,
)
from app.services.clinical_data_management_service import (
    ClinicalDataManagementService,
    get_clinical_data_management_service,
    reset_clinical_data_management_service,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/clinical-data-management"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_clinical_data_management_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> ClinicalDataManagementService:
    """Shorthand for the fresh service."""
    return fresh_service


def _make_query_create(
    trial_id: str = EYLEA_TRIAL,
    site_id: str = "SITE-TEST",
    patient_id: str = "PAT-TEST-001",
    **kwargs,
) -> DataQueryCreate:
    """Build a DataQueryCreate with defaults."""
    defaults = dict(
        trial_id=trial_id,
        site_id=site_id,
        patient_id=patient_id,
        form_name="Demographics",
        field_name="AGE",
        query_category=QueryCategory.OUT_OF_RANGE,
        description="Test query: age out of range",
        current_value="200",
        expected_value="18-99",
        opened_by="test_user",
        auto_generated=False,
    )
    defaults.update(kwargs)
    return DataQueryCreate(**defaults)


def _make_rule_create(**kwargs) -> ValidationRuleCreate:
    """Build a ValidationRuleCreate with defaults."""
    defaults = dict(
        rule_name="TEST_RULE",
        rule_type=ValidationRuleType.RANGE_CHECK,
        description="Test range check rule",
        expression="DM.AGE >= 18 AND DM.AGE <= 99",
        domain="DM",
        fields=["AGE"],
        severity="ERROR",
        active=True,
        auto_query=False,
    )
    defaults.update(kwargs)
    return ValidationRuleCreate(**defaults)


def _make_dataset_create(**kwargs) -> ClinicalDatasetCreate:
    """Build a ClinicalDatasetCreate with defaults."""
    defaults = dict(
        trial_id=EYLEA_TRIAL,
        trial_name="Test Trial",
        name="TEST_SDTM_v1.0",
        cdisc_standard=CDISCStandard.SDTM,
        version="1.0",
        total_records=100,
        total_variables=20,
    )
    defaults.update(kwargs)
    return ClinicalDatasetCreate(**defaults)


# ===========================================================================
# Section 1: Seed data verification
# ===========================================================================


class TestSeedData:
    """Verify seed data is loaded correctly on service init."""

    def test_seed_query_count(self, svc: ClinicalDataManagementService):
        """Should have 25 seeded queries."""
        items, total = svc.list_queries(limit=100)
        assert total == 25

    def test_seed_query_status_distribution(self, svc: ClinicalDataManagementService):
        """Should have correct status distribution: 5 OPEN, 8 ANSWERED, 10 CLOSED, 2 CANCELLED."""
        items, _ = svc.list_queries(limit=100)
        counts = {}
        for q in items:
            counts[q.status] = counts.get(q.status, 0) + 1
        assert counts[QueryStatus.OPEN] == 5
        assert counts[QueryStatus.ANSWERED] == 8
        assert counts[QueryStatus.CLOSED] == 10
        assert counts[QueryStatus.CANCELLED] == 2

    def test_seed_queries_across_trials(self, svc: ClinicalDataManagementService):
        """Queries should span all 3 trials."""
        items, _ = svc.list_queries(limit=100)
        trial_ids = {q.trial_id for q in items}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_rules_count(self, svc: ClinicalDataManagementService):
        """Should have 15 seeded validation rules."""
        items, total = svc.list_rules()
        assert total == 15

    def test_seed_rules_types(self, svc: ClinicalDataManagementService):
        """Rules should cover multiple types."""
        items, _ = svc.list_rules()
        types = {r.rule_type for r in items}
        assert ValidationRuleType.RANGE_CHECK in types
        assert ValidationRuleType.CROSS_FIELD in types
        assert ValidationRuleType.TEMPORAL in types
        assert ValidationRuleType.COMPLETENESS in types

    def test_seed_results_count(self, svc: ClinicalDataManagementService):
        """Should have 40 seeded validation results."""
        items, total = svc.list_results(limit=100)
        assert total == 40

    def test_seed_datasets_count(self, svc: ClinicalDataManagementService):
        """Should have 3 seeded datasets."""
        items, total = svc.list_datasets()
        assert total == 3

    def test_seed_dataset_statuses(self, svc: ClinicalDataManagementService):
        """Datasets should have distinct statuses."""
        items, _ = svc.list_datasets()
        statuses = {d.status for d in items}
        assert DatasetStatus.IN_REVIEW in statuses
        assert DatasetStatus.FROZEN in statuses
        assert DatasetStatus.DRAFT in statuses

    def test_seed_dataset_standards(self, svc: ClinicalDataManagementService):
        """Datasets should cover SDTM and ADaM."""
        items, _ = svc.list_datasets()
        standards = {d.cdisc_standard for d in items}
        assert CDISCStandard.SDTM in standards
        assert CDISCStandard.ADAM in standards

    def test_seed_domains_count(self, svc: ClinicalDataManagementService):
        """Should have 12 CDISC domains."""
        domains = svc.list_domains()
        assert len(domains) == 12

    def test_seed_audit_trail(self, svc: ClinicalDataManagementService):
        """Audit trail should have entries for initial dataset creation."""
        entries, total = svc.get_audit_trail()
        assert total >= 3  # At least one CREATE per dataset

    def test_seed_stats(self, svc: ClinicalDataManagementService):
        """Stats should reflect seed data."""
        stats = svc.get_stats()
        assert stats["queries"] == 25
        assert stats["rules"] == 15
        assert stats["results"] == 40
        assert stats["datasets"] == 3
        assert stats["domains"] == 12


# ===========================================================================
# Section 2: Data Query CRUD
# ===========================================================================


class TestQueryCRUD:
    """Data query create, read, update, list."""

    def test_create_query(self, svc: ClinicalDataManagementService):
        q = svc.create_query(_make_query_create())
        assert q.id is not None
        assert q.status == QueryStatus.OPEN
        assert q.trial_id == EYLEA_TRIAL
        assert q.opened_at is not None

    def test_create_query_auto_generated(self, svc: ClinicalDataManagementService):
        q = svc.create_query(_make_query_create(auto_generated=True))
        assert q.auto_generated is True

    def test_get_query(self, svc: ClinicalDataManagementService):
        q = svc.create_query(_make_query_create())
        found = svc.get_query(q.id)
        assert found is not None
        assert found.id == q.id

    def test_get_query_not_found(self, svc: ClinicalDataManagementService):
        assert svc.get_query("DQ-NONEXISTENT") is None

    def test_update_query_description(self, svc: ClinicalDataManagementService):
        q = svc.create_query(_make_query_create())
        updated = svc.update_query(q.id, DataQueryUpdate(description="Updated description"))
        assert updated is not None
        assert updated.description == "Updated description"

    def test_update_query_category(self, svc: ClinicalDataManagementService):
        q = svc.create_query(_make_query_create())
        updated = svc.update_query(q.id, DataQueryUpdate(query_category=QueryCategory.MISSING_DATA))
        assert updated.query_category == QueryCategory.MISSING_DATA

    def test_update_query_not_found(self, svc: ClinicalDataManagementService):
        assert svc.update_query("NOPE", DataQueryUpdate(description="x")) is None

    def test_list_queries_all(self, svc: ClinicalDataManagementService):
        items, total = svc.list_queries(limit=100)
        assert total == 25
        assert len(items) == 25

    def test_list_queries_filter_trial(self, svc: ClinicalDataManagementService):
        items, total = svc.list_queries(trial_id=EYLEA_TRIAL, limit=100)
        assert total > 0
        assert all(q.trial_id == EYLEA_TRIAL for q in items)

    def test_list_queries_filter_status(self, svc: ClinicalDataManagementService):
        items, total = svc.list_queries(status=QueryStatus.OPEN, limit=100)
        assert total == 5
        assert all(q.status == QueryStatus.OPEN for q in items)

    def test_list_queries_filter_category(self, svc: ClinicalDataManagementService):
        items, total = svc.list_queries(category=QueryCategory.MISSING_DATA, limit=100)
        assert total > 0
        assert all(q.query_category == QueryCategory.MISSING_DATA for q in items)

    def test_list_queries_filter_auto_generated(self, svc: ClinicalDataManagementService):
        items, _ = svc.list_queries(auto_generated=True, limit=100)
        assert all(q.auto_generated is True for q in items)

    def test_list_queries_filter_site(self, svc: ClinicalDataManagementService):
        items, total = svc.list_queries(site_id="SITE-001", limit=100)
        assert total > 0
        assert all(q.site_id == "SITE-001" for q in items)

    def test_list_queries_filter_patient(self, svc: ClinicalDataManagementService):
        items, total = svc.list_queries(patient_id="PAT-E001", limit=100)
        assert total > 0
        assert all(q.patient_id == "PAT-E001" for q in items)

    def test_list_queries_pagination(self, svc: ClinicalDataManagementService):
        items_p1, _ = svc.list_queries(limit=5, offset=0)
        items_p2, _ = svc.list_queries(limit=5, offset=5)
        assert len(items_p1) == 5
        assert len(items_p2) == 5
        ids_p1 = {q.id for q in items_p1}
        ids_p2 = {q.id for q in items_p2}
        assert ids_p1.isdisjoint(ids_p2)

    def test_list_queries_sorted_by_date(self, svc: ClinicalDataManagementService):
        items, _ = svc.list_queries(limit=100)
        for i in range(len(items) - 1):
            assert items[i].opened_at >= items[i + 1].opened_at


# ===========================================================================
# Section 3: Query Workflow
# ===========================================================================


class TestQueryWorkflow:
    """Test answer, close, requery, cancel transitions."""

    def test_answer_open_query(self, svc: ClinicalDataManagementService):
        q = svc.create_query(_make_query_create())
        answered = svc.answer_query(q.id, DataQueryAnswer(answered_by="site_coord", answer_text="Fixed"))
        assert answered.status == QueryStatus.ANSWERED
        assert answered.answered_by == "site_coord"
        assert answered.answer_text == "Fixed"
        assert answered.answered_at is not None

    def test_close_answered_query(self, svc: ClinicalDataManagementService):
        q = svc.create_query(_make_query_create())
        svc.answer_query(q.id, DataQueryAnswer(answered_by="coord", answer_text="Done"))
        closed = svc.close_query(q.id, DataQueryClose(closed_by="dm"))
        assert closed.status == QueryStatus.CLOSED
        assert closed.closed_by == "dm"
        assert closed.closed_at is not None

    def test_requery_answered_query(self, svc: ClinicalDataManagementService):
        q = svc.create_query(_make_query_create())
        svc.answer_query(q.id, DataQueryAnswer(answered_by="coord", answer_text="Done"))
        requeried = svc.requery(q.id, DataQueryRequery(requeried_by="dm", reason="Insufficient detail"))
        assert requeried.status == QueryStatus.REQUERIED
        assert requeried.requery_count == 1
        assert "Requeried" in requeried.description
        assert requeried.answered_by is None
        assert requeried.answer_text is None

    def test_answer_requeried_query(self, svc: ClinicalDataManagementService):
        q = svc.create_query(_make_query_create())
        svc.answer_query(q.id, DataQueryAnswer(answered_by="coord", answer_text="First"))
        svc.requery(q.id, DataQueryRequery(requeried_by="dm", reason="Need more"))
        answered = svc.answer_query(q.id, DataQueryAnswer(answered_by="coord", answer_text="Second"))
        assert answered.status == QueryStatus.ANSWERED
        assert answered.answer_text == "Second"

    def test_cancel_open_query(self, svc: ClinicalDataManagementService):
        q = svc.create_query(_make_query_create())
        cancelled = svc.cancel_query(q.id)
        assert cancelled.status == QueryStatus.CANCELLED

    def test_cancel_requeried_query(self, svc: ClinicalDataManagementService):
        q = svc.create_query(_make_query_create())
        svc.answer_query(q.id, DataQueryAnswer(answered_by="coord", answer_text="Answer"))
        svc.requery(q.id, DataQueryRequery(requeried_by="dm", reason="Reason"))
        cancelled = svc.cancel_query(q.id)
        assert cancelled.status == QueryStatus.CANCELLED

    def test_cannot_answer_closed_query(self, svc: ClinicalDataManagementService):
        q = svc.create_query(_make_query_create())
        svc.answer_query(q.id, DataQueryAnswer(answered_by="coord", answer_text="Done"))
        svc.close_query(q.id, DataQueryClose(closed_by="dm"))
        with pytest.raises(ValueError, match="Cannot answer"):
            svc.answer_query(q.id, DataQueryAnswer(answered_by="coord", answer_text="Again"))

    def test_cannot_close_open_query(self, svc: ClinicalDataManagementService):
        q = svc.create_query(_make_query_create())
        with pytest.raises(ValueError, match="Cannot close"):
            svc.close_query(q.id, DataQueryClose(closed_by="dm"))

    def test_cannot_requery_open_query(self, svc: ClinicalDataManagementService):
        q = svc.create_query(_make_query_create())
        with pytest.raises(ValueError, match="Cannot requery"):
            svc.requery(q.id, DataQueryRequery(requeried_by="dm", reason="Reason"))

    def test_cannot_cancel_answered_query(self, svc: ClinicalDataManagementService):
        q = svc.create_query(_make_query_create())
        svc.answer_query(q.id, DataQueryAnswer(answered_by="coord", answer_text="Done"))
        with pytest.raises(ValueError, match="Cannot cancel"):
            svc.cancel_query(q.id)

    def test_cannot_cancel_closed_query(self, svc: ClinicalDataManagementService):
        q = svc.create_query(_make_query_create())
        svc.answer_query(q.id, DataQueryAnswer(answered_by="coord", answer_text="Done"))
        svc.close_query(q.id, DataQueryClose(closed_by="dm"))
        with pytest.raises(ValueError, match="Cannot cancel"):
            svc.cancel_query(q.id)

    def test_answer_nonexistent_query(self, svc: ClinicalDataManagementService):
        result = svc.answer_query("NOPE", DataQueryAnswer(answered_by="x", answer_text="y"))
        assert result is None

    def test_close_nonexistent_query(self, svc: ClinicalDataManagementService):
        result = svc.close_query("NOPE", DataQueryClose(closed_by="x"))
        assert result is None

    def test_requery_nonexistent_query(self, svc: ClinicalDataManagementService):
        result = svc.requery("NOPE", DataQueryRequery(requeried_by="x", reason="y"))
        assert result is None

    def test_cancel_nonexistent_query(self, svc: ClinicalDataManagementService):
        result = svc.cancel_query("NOPE")
        assert result is None

    def test_full_lifecycle_open_answer_close(self, svc: ClinicalDataManagementService):
        q = svc.create_query(_make_query_create())
        assert q.status == QueryStatus.OPEN
        a = svc.answer_query(q.id, DataQueryAnswer(answered_by="coord", answer_text="Fixed"))
        assert a.status == QueryStatus.ANSWERED
        c = svc.close_query(q.id, DataQueryClose(closed_by="dm"))
        assert c.status == QueryStatus.CLOSED

    def test_full_lifecycle_with_requery(self, svc: ClinicalDataManagementService):
        q = svc.create_query(_make_query_create())
        svc.answer_query(q.id, DataQueryAnswer(answered_by="c", answer_text="First"))
        svc.requery(q.id, DataQueryRequery(requeried_by="dm", reason="More detail"))
        svc.answer_query(q.id, DataQueryAnswer(answered_by="c", answer_text="Second"))
        c = svc.close_query(q.id, DataQueryClose(closed_by="dm"))
        assert c.status == QueryStatus.CLOSED
        assert c.requery_count == 1


# ===========================================================================
# Section 4: Validation Rules
# ===========================================================================


class TestValidationRules:
    """Validation rule CRUD."""

    def test_create_rule(self, svc: ClinicalDataManagementService):
        rule = svc.create_rule(_make_rule_create())
        assert rule.id is not None
        assert rule.rule_name == "TEST_RULE"
        assert rule.active is True

    def test_get_rule(self, svc: ClinicalDataManagementService):
        rule = svc.create_rule(_make_rule_create())
        found = svc.get_rule(rule.id)
        assert found is not None
        assert found.id == rule.id

    def test_get_rule_not_found(self, svc: ClinicalDataManagementService):
        assert svc.get_rule("VR-9999") is None

    def test_update_rule(self, svc: ClinicalDataManagementService):
        rule = svc.create_rule(_make_rule_create())
        updated = svc.update_rule(rule.id, ValidationRuleUpdate(description="New desc"))
        assert updated.description == "New desc"

    def test_update_rule_active(self, svc: ClinicalDataManagementService):
        rule = svc.create_rule(_make_rule_create())
        updated = svc.update_rule(rule.id, ValidationRuleUpdate(active=False))
        assert updated.active is False

    def test_update_rule_not_found(self, svc: ClinicalDataManagementService):
        assert svc.update_rule("VR-9999", ValidationRuleUpdate(description="x")) is None

    def test_delete_rule(self, svc: ClinicalDataManagementService):
        rule = svc.create_rule(_make_rule_create())
        assert svc.delete_rule(rule.id) is True
        assert svc.get_rule(rule.id) is None

    def test_delete_rule_not_found(self, svc: ClinicalDataManagementService):
        assert svc.delete_rule("VR-9999") is False

    def test_list_rules_all(self, svc: ClinicalDataManagementService):
        items, total = svc.list_rules()
        assert total == 15

    def test_list_rules_filter_domain(self, svc: ClinicalDataManagementService):
        items, total = svc.list_rules(domain="DM")
        assert total > 0
        assert all(r.domain == "DM" for r in items)

    def test_list_rules_filter_type(self, svc: ClinicalDataManagementService):
        items, total = svc.list_rules(rule_type=ValidationRuleType.RANGE_CHECK)
        assert total > 0
        assert all(r.rule_type == ValidationRuleType.RANGE_CHECK for r in items)

    def test_list_rules_filter_active(self, svc: ClinicalDataManagementService):
        items, total = svc.list_rules(active=True)
        assert all(r.active is True for r in items)

    def test_list_rules_filter_domain_ae(self, svc: ClinicalDataManagementService):
        items, total = svc.list_rules(domain="AE")
        assert total > 0
        assert all(r.domain == "AE" for r in items)


# ===========================================================================
# Section 5: Batch Validation
# ===========================================================================


class TestBatchValidation:
    """Batch validation execution."""

    def test_run_all_rules(self, svc: ClinicalDataManagementService):
        resp = svc.run_batch_validation(EYLEA_TRIAL)
        assert resp.trial_id == EYLEA_TRIAL
        assert resp.rules_executed == 15
        assert resp.total_checks > 0
        assert resp.passed + resp.failed == resp.total_checks

    def test_run_specific_rules(self, svc: ClinicalDataManagementService):
        resp = svc.run_batch_validation(EYLEA_TRIAL, rule_ids=["VR-0001", "VR-0002"])
        assert resp.rules_executed == 2

    def test_run_stores_results(self, svc: ClinicalDataManagementService):
        before_items, before_total = svc.list_results(limit=200)
        svc.run_batch_validation(EYLEA_TRIAL)
        after_items, after_total = svc.list_results(limit=200)
        assert after_total > before_total

    def test_run_returns_results(self, svc: ClinicalDataManagementService):
        resp = svc.run_batch_validation(EYLEA_TRIAL)
        assert len(resp.results) == resp.total_checks


# ===========================================================================
# Section 6: Validation Results
# ===========================================================================


class TestValidationResults:
    """Validation result listing."""

    def test_list_results_all(self, svc: ClinicalDataManagementService):
        items, total = svc.list_results(limit=100)
        assert total == 40

    def test_list_results_filter_trial(self, svc: ClinicalDataManagementService):
        items, total = svc.list_results(trial_id=EYLEA_TRIAL, limit=100)
        assert total > 0
        assert all(r.trial_id == EYLEA_TRIAL for r in items)

    def test_list_results_filter_passed(self, svc: ClinicalDataManagementService):
        items, total = svc.list_results(passed=True, limit=100)
        assert all(r.passed is True for r in items)

    def test_list_results_filter_failed(self, svc: ClinicalDataManagementService):
        items, total = svc.list_results(passed=False, limit=100)
        assert total > 0
        assert all(r.passed is False for r in items)

    def test_list_results_filter_rule_id(self, svc: ClinicalDataManagementService):
        items, total = svc.list_results(rule_id="VR-0001", limit=100)
        assert all(r.rule_id == "VR-0001" for r in items)

    def test_list_results_pagination(self, svc: ClinicalDataManagementService):
        p1, _ = svc.list_results(limit=10, offset=0)
        p2, _ = svc.list_results(limit=10, offset=10)
        assert len(p1) == 10
        assert len(p2) == 10
        ids1 = {r.id for r in p1}
        ids2 = {r.id for r in p2}
        assert ids1.isdisjoint(ids2)

    def test_get_result(self, svc: ClinicalDataManagementService):
        items, _ = svc.list_results(limit=1)
        result = svc.get_result(items[0].id)
        assert result is not None


# ===========================================================================
# Section 7: Clinical Datasets
# ===========================================================================


class TestDatasetCRUD:
    """Clinical dataset CRUD."""

    def test_create_dataset(self, svc: ClinicalDataManagementService):
        ds = svc.create_dataset(_make_dataset_create())
        assert ds.id is not None
        assert ds.status == DatasetStatus.DRAFT
        assert ds.created_at is not None

    def test_get_dataset(self, svc: ClinicalDataManagementService):
        ds = svc.create_dataset(_make_dataset_create())
        found = svc.get_dataset(ds.id)
        assert found is not None
        assert found.id == ds.id

    def test_get_dataset_not_found(self, svc: ClinicalDataManagementService):
        assert svc.get_dataset("DS-9999") is None

    def test_update_dataset(self, svc: ClinicalDataManagementService):
        ds = svc.create_dataset(_make_dataset_create())
        updated = svc.update_dataset(ds.id, ClinicalDatasetUpdate(name="UPDATED_NAME"))
        assert updated.name == "UPDATED_NAME"

    def test_update_dataset_records(self, svc: ClinicalDataManagementService):
        ds = svc.create_dataset(_make_dataset_create())
        updated = svc.update_dataset(ds.id, ClinicalDatasetUpdate(total_records=500))
        assert updated.total_records == 500

    def test_update_dataset_not_found(self, svc: ClinicalDataManagementService):
        assert svc.update_dataset("DS-9999", ClinicalDatasetUpdate(name="x")) is None

    def test_list_datasets_all(self, svc: ClinicalDataManagementService):
        items, total = svc.list_datasets()
        assert total == 3

    def test_list_datasets_filter_trial(self, svc: ClinicalDataManagementService):
        items, total = svc.list_datasets(trial_id=EYLEA_TRIAL)
        assert total > 0
        assert all(d.trial_id == EYLEA_TRIAL for d in items)

    def test_list_datasets_filter_status(self, svc: ClinicalDataManagementService):
        items, total = svc.list_datasets(status=DatasetStatus.DRAFT)
        assert total > 0
        assert all(d.status == DatasetStatus.DRAFT for d in items)

    def test_list_datasets_filter_standard(self, svc: ClinicalDataManagementService):
        items, total = svc.list_datasets(cdisc_standard=CDISCStandard.ADAM)
        assert total > 0
        assert all(d.cdisc_standard == CDISCStandard.ADAM for d in items)


# ===========================================================================
# Section 8: Dataset Lifecycle
# ===========================================================================


class TestDatasetLifecycle:
    """Freeze, lock, release, archive transitions."""

    def _get_in_review_dataset_id(self, svc: ClinicalDataManagementService) -> str:
        """Find the IN_REVIEW dataset."""
        items, _ = svc.list_datasets(status=DatasetStatus.IN_REVIEW)
        assert len(items) > 0
        return items[0].id

    def _get_frozen_dataset_id(self, svc: ClinicalDataManagementService) -> str:
        """Find the FROZEN dataset."""
        items, _ = svc.list_datasets(status=DatasetStatus.FROZEN)
        assert len(items) > 0
        return items[0].id

    def test_freeze_in_review_dataset(self, svc: ClinicalDataManagementService):
        did = self._get_in_review_dataset_id(svc)
        result = svc.freeze_dataset(did, DatasetFreezeRequest(frozen_by="dm", reason="Ready"))
        assert result.status == DatasetStatus.FROZEN
        assert result.frozen_at is not None

    def test_lock_frozen_dataset(self, svc: ClinicalDataManagementService):
        did = self._get_frozen_dataset_id(svc)
        result = svc.lock_dataset(did, DatasetLockRequest(
            locked_by="dm", lock_level=DataLockLevel.SOFT_LOCK, reason="DB lock"))
        assert result.status == DatasetStatus.LOCKED
        assert result.lock_level == DataLockLevel.SOFT_LOCK
        assert result.locked_by == "dm"

    def test_release_locked_dataset(self, svc: ClinicalDataManagementService):
        did = self._get_frozen_dataset_id(svc)
        svc.lock_dataset(did, DatasetLockRequest(locked_by="dm"))
        result = svc.release_dataset(did, DatasetReleaseRequest(
            released_by="dm", release_notes="For submission"))
        assert result.status == DatasetStatus.RELEASED
        assert result.release_notes == "For submission"

    def test_archive_released_dataset(self, svc: ClinicalDataManagementService):
        did = self._get_frozen_dataset_id(svc)
        svc.lock_dataset(did, DatasetLockRequest(locked_by="dm"))
        svc.release_dataset(did, DatasetReleaseRequest(released_by="dm", release_notes="Ready"))
        result = svc.archive_dataset(did, "dm")
        assert result.status == DatasetStatus.ARCHIVED

    def test_cannot_freeze_draft(self, svc: ClinicalDataManagementService):
        items, _ = svc.list_datasets(status=DatasetStatus.DRAFT)
        with pytest.raises(ValueError, match="Cannot freeze"):
            svc.freeze_dataset(items[0].id, DatasetFreezeRequest(frozen_by="dm"))

    def test_cannot_lock_in_review(self, svc: ClinicalDataManagementService):
        did = self._get_in_review_dataset_id(svc)
        with pytest.raises(ValueError, match="Cannot lock"):
            svc.lock_dataset(did, DatasetLockRequest(locked_by="dm"))

    def test_cannot_release_frozen(self, svc: ClinicalDataManagementService):
        did = self._get_frozen_dataset_id(svc)
        with pytest.raises(ValueError, match="Cannot release"):
            svc.release_dataset(did, DatasetReleaseRequest(released_by="dm", release_notes="x"))

    def test_cannot_archive_frozen(self, svc: ClinicalDataManagementService):
        did = self._get_frozen_dataset_id(svc)
        with pytest.raises(ValueError, match="Cannot archive"):
            svc.archive_dataset(did, "dm")

    def test_cannot_update_locked_dataset(self, svc: ClinicalDataManagementService):
        did = self._get_frozen_dataset_id(svc)
        svc.lock_dataset(did, DatasetLockRequest(locked_by="dm"))
        with pytest.raises(ValueError, match="Cannot update"):
            svc.update_dataset(did, ClinicalDatasetUpdate(name="x"))

    def test_freeze_nonexistent(self, svc: ClinicalDataManagementService):
        result = svc.freeze_dataset("DS-9999", DatasetFreezeRequest(frozen_by="dm"))
        assert result is None

    def test_lock_nonexistent(self, svc: ClinicalDataManagementService):
        result = svc.lock_dataset("DS-9999", DatasetLockRequest(locked_by="dm"))
        assert result is None

    def test_release_nonexistent(self, svc: ClinicalDataManagementService):
        result = svc.release_dataset("DS-9999", DatasetReleaseRequest(released_by="dm", release_notes="x"))
        assert result is None

    def test_archive_nonexistent(self, svc: ClinicalDataManagementService):
        result = svc.archive_dataset("DS-9999", "dm")
        assert result is None

    def test_lock_with_regulatory_level(self, svc: ClinicalDataManagementService):
        did = self._get_frozen_dataset_id(svc)
        result = svc.lock_dataset(did, DatasetLockRequest(
            locked_by="admin", lock_level=DataLockLevel.REGULATORY_LOCK))
        assert result.lock_level == DataLockLevel.REGULATORY_LOCK

    def test_full_lifecycle(self, svc: ClinicalDataManagementService):
        did = self._get_in_review_dataset_id(svc)
        ds = svc.freeze_dataset(did, DatasetFreezeRequest(frozen_by="dm"))
        assert ds.status == DatasetStatus.FROZEN
        ds = svc.lock_dataset(did, DatasetLockRequest(locked_by="dm"))
        assert ds.status == DatasetStatus.LOCKED
        ds = svc.release_dataset(did, DatasetReleaseRequest(released_by="dm", release_notes="Final"))
        assert ds.status == DatasetStatus.RELEASED
        ds = svc.archive_dataset(did, "dm")
        assert ds.status == DatasetStatus.ARCHIVED


# ===========================================================================
# Section 9: CDISC Domains & Conformance
# ===========================================================================


class TestCDISCDomains:
    """CDISC domain listing and conformance."""

    def test_list_domains(self, svc: ClinicalDataManagementService):
        domains = svc.list_domains()
        assert len(domains) == 12

    def test_get_domain_dm(self, svc: ClinicalDataManagementService):
        dm = svc.get_domain("DM")
        assert dm is not None
        assert dm.name == "DM"
        assert "USUBJID" in dm.key_variables
        assert "AGE" in dm.required_variables

    def test_get_domain_ae(self, svc: ClinicalDataManagementService):
        ae = svc.get_domain("AE")
        assert ae is not None
        assert ae.total_records > 0

    def test_get_domain_not_found(self, svc: ClinicalDataManagementService):
        assert svc.get_domain("XX") is None

    def test_conformance_check(self, svc: ClinicalDataManagementService):
        items, _ = svc.list_datasets()
        report = svc.run_conformance_check(items[0].id)
        assert report is not None
        assert report.domains_checked == 12
        assert report.conformance_percent > 0
        assert len(report.domain_results) == 12

    def test_conformance_issues_counted(self, svc: ClinicalDataManagementService):
        items, _ = svc.list_datasets()
        report = svc.run_conformance_check(items[0].id)
        assert report.total_issues > 0
        assert report.total_issues == report.critical_issues + report.warning_issues + report.info_issues

    def test_conformance_nonexistent_dataset(self, svc: ClinicalDataManagementService):
        result = svc.run_conformance_check("DS-9999")
        assert result is None

    def test_domain_has_required_variables(self, svc: ClinicalDataManagementService):
        lb = svc.get_domain("LB")
        assert "LBTESTCD" in lb.required_variables


# ===========================================================================
# Section 10: Audit Trail
# ===========================================================================


class TestAuditTrail:
    """Audit trail operations."""

    def test_initial_audit_entries(self, svc: ClinicalDataManagementService):
        entries, total = svc.get_audit_trail()
        assert total >= 3

    def test_audit_trail_on_create(self, svc: ClinicalDataManagementService):
        before, _ = svc.get_audit_trail()
        svc.create_dataset(_make_dataset_create())
        after, total_after = svc.get_audit_trail()
        assert total_after > len(before)

    def test_audit_trail_on_freeze(self, svc: ClinicalDataManagementService):
        items, _ = svc.list_datasets(status=DatasetStatus.IN_REVIEW)
        did = items[0].id
        svc.freeze_dataset(did, DatasetFreezeRequest(frozen_by="dm"))
        entries, _ = svc.get_audit_trail(dataset_id=did, action="FREEZE")
        assert len(entries) >= 1

    def test_audit_trail_on_lock(self, svc: ClinicalDataManagementService):
        items, _ = svc.list_datasets(status=DatasetStatus.FROZEN)
        did = items[0].id
        svc.lock_dataset(did, DatasetLockRequest(locked_by="dm"))
        entries, _ = svc.get_audit_trail(dataset_id=did, action="LOCK")
        assert len(entries) >= 1

    def test_audit_trail_filter_dataset(self, svc: ClinicalDataManagementService):
        items, _ = svc.list_datasets()
        did = items[0].id
        entries, total = svc.get_audit_trail(dataset_id=did)
        assert all(e.dataset_id == did for e in entries)

    def test_audit_trail_filter_action(self, svc: ClinicalDataManagementService):
        entries, total = svc.get_audit_trail(action="CREATE")
        assert all(e.action == "CREATE" for e in entries)


# ===========================================================================
# Section 11: Dataset Comparison
# ===========================================================================


class TestDatasetComparison:
    """Compare two datasets."""

    def test_compare_datasets(self, svc: ClinicalDataManagementService):
        items, _ = svc.list_datasets()
        a, b = items[0], items[1]
        result = svc.compare_datasets(a.id, b.id)
        assert result is not None
        assert result.dataset_a_id == a.id
        assert result.dataset_b_id == b.id
        assert result.summary != ""

    def test_compare_same_dataset(self, svc: ClinicalDataManagementService):
        items, _ = svc.list_datasets()
        result = svc.compare_datasets(items[0].id, items[0].id)
        assert result is not None
        assert result.records_added == 0
        assert result.records_removed == 0

    def test_compare_nonexistent(self, svc: ClinicalDataManagementService):
        result = svc.compare_datasets("DS-9999", "DS-0001")
        assert result is None


# ===========================================================================
# Section 12: Metrics
# ===========================================================================


class TestMetrics:
    """Data cleaning and resolution metrics."""

    def test_cleaning_metrics_eylea(self, svc: ClinicalDataManagementService):
        m = svc.get_cleaning_metrics(EYLEA_TRIAL)
        assert m.trial_id == EYLEA_TRIAL
        assert m.total_queries > 0
        assert m.open_queries >= 0
        assert m.query_rate_per_page > 0

    def test_cleaning_metrics_dupixent(self, svc: ClinicalDataManagementService):
        m = svc.get_cleaning_metrics(DUPIXENT_TRIAL)
        assert m.total_queries > 0
        assert m.validation_pass_rate > 0

    def test_cleaning_metrics_libtayo(self, svc: ClinicalDataManagementService):
        m = svc.get_cleaning_metrics(LIBTAYO_TRIAL)
        assert m.total_queries > 0
        assert len(m.queries_by_category) > 0

    def test_cleaning_metrics_empty_trial(self, svc: ClinicalDataManagementService):
        m = svc.get_cleaning_metrics("NONEXISTENT")
        assert m.total_queries == 0
        assert m.query_rate_per_page == 0

    def test_resolution_metrics_eylea(self, svc: ClinicalDataManagementService):
        m = svc.get_resolution_metrics(EYLEA_TRIAL)
        assert m.trial_id == EYLEA_TRIAL
        assert m.total_resolved > 0
        assert m.avg_resolution_days > 0

    def test_resolution_metrics_has_categories(self, svc: ClinicalDataManagementService):
        m = svc.get_resolution_metrics(EYLEA_TRIAL)
        assert len(m.resolution_by_category) > 0

    def test_resolution_metrics_empty(self, svc: ClinicalDataManagementService):
        m = svc.get_resolution_metrics("NONEXISTENT")
        assert m.total_resolved == 0
        assert m.avg_resolution_days == 0

    def test_auto_generated_percent(self, svc: ClinicalDataManagementService):
        m = svc.get_cleaning_metrics(EYLEA_TRIAL)
        assert 0 <= m.auto_generated_percent <= 100


# ===========================================================================
# Section 13: API Integration Tests
# ===========================================================================


@pytest.mark.anyio
class TestAPIQueries:
    """HTTP-level tests for query endpoints."""

    async def test_list_queries(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/queries")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["total"] == 25

    async def test_list_queries_filter_status(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/queries", params={"status": "OPEN"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 5

    async def test_get_query(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/queries/DQ-0001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "DQ-0001"

    async def test_get_query_404(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/queries/DQ-NOPE")
        assert resp.status_code == 404

    async def test_create_query(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"{API_PREFIX}/queries", json={
                "trial_id": EYLEA_TRIAL, "site_id": "SITE-NEW",
                "patient_id": "PAT-NEW", "form_name": "Demo",
                "field_name": "AGE", "query_category": "OUT_OF_RANGE",
                "description": "Test via API", "opened_by": "api_tester",
            })
        assert resp.status_code == 201
        assert resp.json()["status"] == "OPEN"

    async def test_answer_query(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"{API_PREFIX}/queries/DQ-0001/answer", json={
                "answered_by": "api_user", "answer_text": "Fixed via API",
            })
        assert resp.status_code == 200
        assert resp.json()["status"] == "ANSWERED"

    async def test_answer_invalid_status(self):
        # DQ-0014 is CLOSED in seed
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"{API_PREFIX}/queries/DQ-0014/answer", json={
                "answered_by": "user", "answer_text": "x",
            })
        assert resp.status_code == 400

    async def test_cancel_query(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"{API_PREFIX}/queries/DQ-0001/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "CANCELLED"


@pytest.mark.anyio
class TestAPIRules:
    """HTTP-level tests for validation rule endpoints."""

    async def test_list_rules(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/rules")
        assert resp.status_code == 200
        assert resp.json()["total"] == 15

    async def test_get_rule(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/rules/VR-0001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "VR-0001"

    async def test_get_rule_404(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/rules/VR-9999")
        assert resp.status_code == 404

    async def test_create_rule(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"{API_PREFIX}/rules", json={
                "rule_name": "API_TEST_RULE",
                "rule_type": "RANGE_CHECK",
                "description": "API test",
                "expression": "AGE >= 1",
                "domain": "DM",
            })
        assert resp.status_code == 201

    async def test_delete_rule(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.delete(f"{API_PREFIX}/rules/VR-0001")
        assert resp.status_code == 204


@pytest.mark.anyio
class TestAPIValidation:
    """HTTP-level tests for validation endpoints."""

    async def test_run_batch(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"{API_PREFIX}/validation/run", json={
                "trial_id": EYLEA_TRIAL,
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["rules_executed"] == 15
        assert data["total_checks"] > 0

    async def test_list_results(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/validation/results")
        assert resp.status_code == 200
        assert resp.json()["total"] == 40


@pytest.mark.anyio
class TestAPIDatasets:
    """HTTP-level tests for dataset endpoints."""

    async def test_list_datasets(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/datasets")
        assert resp.status_code == 200
        assert resp.json()["total"] == 3

    async def test_get_dataset(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/datasets/DS-0001")
        assert resp.status_code == 200

    async def test_get_dataset_404(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/datasets/DS-NOPE")
        assert resp.status_code == 404

    async def test_create_dataset(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"{API_PREFIX}/datasets", json={
                "trial_id": EYLEA_TRIAL, "trial_name": "API Test",
                "name": "API_SDTM", "cdisc_standard": "SDTM",
            })
        assert resp.status_code == 201
        assert resp.json()["status"] == "DRAFT"

    async def test_freeze_dataset(self):
        # DS-0001 is IN_REVIEW
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"{API_PREFIX}/datasets/DS-0001/freeze", json={
                "frozen_by": "api_user",
            })
        assert resp.status_code == 200
        assert resp.json()["status"] == "FROZEN"

    async def test_freeze_invalid_status(self):
        # DS-0003 is DRAFT
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"{API_PREFIX}/datasets/DS-0003/freeze", json={
                "frozen_by": "api_user",
            })
        assert resp.status_code == 400

    async def test_lock_dataset(self):
        # DS-0002 is FROZEN
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"{API_PREFIX}/datasets/DS-0002/lock", json={
                "locked_by": "api_user",
            })
        assert resp.status_code == 200
        assert resp.json()["status"] == "LOCKED"

    async def test_conformance_check(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/datasets/DS-0001/conformance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["domains_checked"] == 12
        assert data["conformance_percent"] > 0

    async def test_conformance_404(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/datasets/DS-NOPE/conformance")
        assert resp.status_code == 404


@pytest.mark.anyio
class TestAPICompare:
    """HTTP-level tests for dataset comparison."""

    async def test_compare_datasets(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/datasets/compare", params={
                "dataset_a_id": "DS-0001", "dataset_b_id": "DS-0002",
            })
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data

    async def test_compare_404(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/datasets/compare", params={
                "dataset_a_id": "DS-NOPE", "dataset_b_id": "DS-0001",
            })
        assert resp.status_code == 404


@pytest.mark.anyio
class TestAPIDomains:
    """HTTP-level tests for CDISC domain endpoints."""

    async def test_list_domains(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/domains")
        assert resp.status_code == 200
        assert len(resp.json()) == 12

    async def test_get_domain(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/domains/DM")
        assert resp.status_code == 200
        assert resp.json()["name"] == "DM"

    async def test_get_domain_404(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/domains/XX")
        assert resp.status_code == 404

    async def test_get_domain_case_insensitive(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/domains/dm")
        assert resp.status_code == 200
        assert resp.json()["name"] == "DM"


@pytest.mark.anyio
class TestAPIAuditTrail:
    """HTTP-level tests for audit trail endpoint."""

    async def test_list_audit_trail(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/audit-trail")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 3

    async def test_filter_by_dataset(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/audit-trail", params={"dataset_id": "DS-0001"})
        assert resp.status_code == 200

    async def test_filter_by_action(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/audit-trail", params={"action": "CREATE"})
        assert resp.status_code == 200
        for entry in resp.json()["items"]:
            assert entry["action"] == "CREATE"


@pytest.mark.anyio
class TestAPIMetrics:
    """HTTP-level tests for metrics endpoints."""

    async def test_cleaning_metrics(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/metrics/{EYLEA_TRIAL}/cleaning")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["total_queries"] > 0

    async def test_resolution_metrics(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/metrics/{EYLEA_TRIAL}/resolution")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_resolved"] > 0

    async def test_cleaning_metrics_unknown_trial(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/metrics/UNKNOWN/cleaning")
        assert resp.status_code == 200
        assert resp.json()["total_queries"] == 0


# ===========================================================================
# Section 14: Edge Cases & Additional Coverage
# ===========================================================================


class TestEdgeCases:
    """Additional edge case tests."""

    def test_multiple_creates_unique_ids(self, svc: ClinicalDataManagementService):
        ids = set()
        for _ in range(5):
            q = svc.create_query(_make_query_create())
            ids.add(q.id)
        assert len(ids) == 5

    def test_create_many_rules(self, svc: ClinicalDataManagementService):
        for i in range(5):
            svc.create_rule(_make_rule_create(rule_name=f"BATCH_RULE_{i}"))
        items, total = svc.list_rules()
        assert total >= 20

    def test_create_many_datasets(self, svc: ClinicalDataManagementService):
        for i in range(3):
            svc.create_dataset(_make_dataset_create(name=f"DS_BATCH_{i}"))
        items, total = svc.list_datasets()
        assert total >= 6

    def test_requery_increments_counter(self, svc: ClinicalDataManagementService):
        q = svc.create_query(_make_query_create())
        svc.answer_query(q.id, DataQueryAnswer(answered_by="c", answer_text="a"))
        r1 = svc.requery(q.id, DataQueryRequery(requeried_by="d", reason="r"))
        assert r1.requery_count == 1
        svc.answer_query(q.id, DataQueryAnswer(answered_by="c", answer_text="b"))
        r2 = svc.requery(q.id, DataQueryRequery(requeried_by="d", reason="r2"))
        assert r2.requery_count == 2

    def test_batch_validation_with_no_rules(self, svc: ClinicalDataManagementService):
        resp = svc.run_batch_validation(EYLEA_TRIAL, rule_ids=["VR-9999"])
        assert resp.rules_executed == 0
        assert resp.total_checks == 0

    def test_cleaning_metrics_categories(self, svc: ClinicalDataManagementService):
        m = svc.get_cleaning_metrics(EYLEA_TRIAL)
        total_cat = sum(m.queries_by_category.values())
        assert total_cat == m.total_queries

    def test_resolution_within_buckets(self, svc: ClinicalDataManagementService):
        m = svc.get_resolution_metrics(EYLEA_TRIAL)
        assert (m.queries_resolved_within_7_days +
                m.queries_resolved_within_14_days +
                m.queries_resolved_after_14_days) == m.total_resolved

    def test_dataset_update_adds_audit(self, svc: ClinicalDataManagementService):
        ds = svc.create_dataset(_make_dataset_create())
        before_entries, before_total = svc.get_audit_trail(dataset_id=ds.id)
        svc.update_dataset(ds.id, ClinicalDatasetUpdate(name="UPDATED"))
        after_entries, after_total = svc.get_audit_trail(dataset_id=ds.id)
        assert after_total > before_total

    def test_query_opened_at_set(self, svc: ClinicalDataManagementService):
        q = svc.create_query(_make_query_create())
        assert q.opened_at is not None

    def test_all_seed_queries_have_trial(self, svc: ClinicalDataManagementService):
        items, _ = svc.list_queries(limit=100)
        for q in items:
            assert q.trial_id is not None
            assert q.trial_id != ""

    def test_all_seed_rules_have_domain(self, svc: ClinicalDataManagementService):
        items, _ = svc.list_rules()
        for r in items:
            assert r.domain is not None
            assert r.domain != ""

    def test_all_domains_have_key_variables(self, svc: ClinicalDataManagementService):
        domains = svc.list_domains()
        for d in domains:
            assert len(d.key_variables) > 0

    def test_conformance_domain_results_sum(self, svc: ClinicalDataManagementService):
        items, _ = svc.list_datasets()
        report = svc.run_conformance_check(items[0].id)
        for dr in report.domain_results:
            assert dr.passed + dr.failed == dr.total_checks
