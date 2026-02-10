"""Tests for Clinical Data Transfer Management (DATA-XFER).

Covers:
- Seed data verification (agreements, executions, validations, reconciliations)
- Agreement CRUD (create, read, update, delete, list, filter by trial/direction/method/status/frequency)
- Execution CRUD (create, read, update, delete, list, filter by trial/agreement/direction/status)
- Validation CRUD (create, read, delete, list, filter by execution/result)
- Reconciliation CRUD (create, read, update, delete, list, filter by execution/reconciled)
- Auto-reconciliation logic (matched == source_count == target_count)
- Execution status transitions with auto-timestamps
- Transfer metrics computation
- Error handling (404s, 400s, invalid references)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.data_transfer import (
    AgreementStatus,
    TransferDirection,
    TransferFrequency,
    TransferMethod,
    TransferStatus,
    ValidationResult,
)
from app.services.data_transfer_service import (
    DataTransferService,
    get_data_transfer_service,
    reset_data_transfer_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/data-transfer"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_data_transfer_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> DataTransferService:
    """Shorthand for the fresh service."""
    return fresh_service


@pytest.fixture
async def client():
    """Async HTTP client for API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=True) as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agreement_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "partner_name": "Test Partner CRO",
        "partner_type": "cro",
        "direction": "outbound",
        "transfer_method": "sftp",
        "frequency": "daily",
        "data_types": ["edc_data", "lab_results"],
        "encryption_required": True,
        "responsible_person": "Dr. Test Person",
        "technical_contact": "test@partner.com",
    }
    defaults.update(overrides)
    return defaults


def _make_execution_create(**overrides) -> dict:
    defaults = {
        "agreement_id": "DTA-001",
        "trial_id": EYLEA_TRIAL,
        "direction": "inbound",
        "records_expected": 100,
        "file_count": 2,
        "initiated_by": "test_user",
    }
    defaults.update(overrides)
    return defaults


def _make_validation_create(**overrides) -> dict:
    defaults = {
        "execution_id": "DTE-001",
        "validation_type": "schema_validation",
        "validated_by": "test_validator",
        "records_checked": 100,
        "records_passed": 95,
        "records_failed": 5,
        "issues": ["5 records had invalid date format"],
        "result": "warnings",
    }
    defaults.update(overrides)
    return defaults


def _make_reconciliation_create(**overrides) -> dict:
    defaults = {
        "execution_id": "DTE-001",
        "source_record_count": 100,
        "target_record_count": 100,
        "matched_records": 100,
        "unmatched_records": 0,
        "reconciled_by": "test_reconciler",
        "discrepancy_notes": None,
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_agreements_count(self, svc: DataTransferService):
        agreements = svc.list_agreements()
        assert len(agreements) == 12

    def test_seed_agreements_all_trials(self, svc: DataTransferService):
        trials = {a.trial_id for a in svc.list_agreements()}
        assert EYLEA_TRIAL in trials
        assert DUPIXENT_TRIAL in trials
        assert LIBTAYO_TRIAL in trials

    def test_seed_eylea_agreements_count(self, svc: DataTransferService):
        agreements = svc.list_agreements(trial_id=EYLEA_TRIAL)
        assert len(agreements) == 4

    def test_seed_dupixent_agreements_count(self, svc: DataTransferService):
        agreements = svc.list_agreements(trial_id=DUPIXENT_TRIAL)
        assert len(agreements) == 4

    def test_seed_libtayo_agreements_count(self, svc: DataTransferService):
        agreements = svc.list_agreements(trial_id=LIBTAYO_TRIAL)
        assert len(agreements) == 4

    def test_seed_executions_count(self, svc: DataTransferService):
        executions = svc.list_executions()
        assert len(executions) == 15

    def test_seed_validations_count(self, svc: DataTransferService):
        validations = svc.list_validations()
        assert len(validations) == 12

    def test_seed_reconciliations_count(self, svc: DataTransferService):
        reconciliations = svc.list_reconciliations()
        assert len(reconciliations) == 10

    def test_seed_agreement_statuses_present(self, svc: DataTransferService):
        statuses = {a.status for a in svc.list_agreements()}
        assert AgreementStatus.ACTIVE in statuses
        assert AgreementStatus.SUSPENDED in statuses
        assert AgreementStatus.DRAFT in statuses

    def test_seed_execution_statuses_present(self, svc: DataTransferService):
        statuses = {e.status for e in svc.list_executions()}
        assert TransferStatus.COMPLETED in statuses
        assert TransferStatus.FAILED in statuses
        assert TransferStatus.IN_PROGRESS in statuses
        assert TransferStatus.SCHEDULED in statuses
        assert TransferStatus.CANCELLED in statuses
        assert TransferStatus.PARTIALLY_COMPLETED in statuses

    def test_seed_validation_results_present(self, svc: DataTransferService):
        results = {v.result for v in svc.list_validations()}
        assert ValidationResult.PASSED in results
        assert ValidationResult.FAILED in results
        assert ValidationResult.WARNINGS in results
        assert ValidationResult.PENDING in results

    def test_seed_directions_present(self, svc: DataTransferService):
        directions = {a.direction for a in svc.list_agreements()}
        assert TransferDirection.INBOUND in directions
        assert TransferDirection.OUTBOUND in directions
        assert TransferDirection.BIDIRECTIONAL in directions

    def test_seed_methods_present(self, svc: DataTransferService):
        methods = {a.transfer_method for a in svc.list_agreements()}
        assert TransferMethod.SFTP in methods
        assert TransferMethod.API in methods
        assert TransferMethod.ENCRYPTED_EMAIL in methods
        assert TransferMethod.CLOUD_SHARE in methods
        assert TransferMethod.PHYSICAL_MEDIA in methods
        assert TransferMethod.DIRECT_DATABASE in methods

    def test_seed_frequencies_present(self, svc: DataTransferService):
        frequencies = {a.frequency for a in svc.list_agreements()}
        assert TransferFrequency.REAL_TIME in frequencies
        assert TransferFrequency.DAILY in frequencies
        assert TransferFrequency.WEEKLY in frequencies
        assert TransferFrequency.MONTHLY in frequencies
        assert TransferFrequency.ON_DEMAND in frequencies
        assert TransferFrequency.MILESTONE_BASED in frequencies

    def test_seed_reconciled_and_unreconciled(self, svc: DataTransferService):
        reconciliations = svc.list_reconciliations()
        reconciled_flags = {r.reconciled for r in reconciliations}
        assert True in reconciled_flags
        assert False in reconciled_flags

    def test_seed_agreement_has_data_types(self, svc: DataTransferService):
        agreement = svc.get_agreement("DTA-001")
        assert agreement is not None
        assert len(agreement.data_types) > 0

    def test_seed_failed_execution_has_error(self, svc: DataTransferService):
        execution = svc.get_execution("DTE-005")
        assert execution is not None
        assert execution.status == TransferStatus.FAILED
        assert execution.error_message is not None
        assert len(execution.error_message) > 0

    def test_seed_failed_validation_has_issues(self, svc: DataTransferService):
        validation = svc.get_validation("DTV-005")
        assert validation is not None
        assert validation.result == ValidationResult.FAILED
        assert len(validation.issues) > 0


# =====================================================================
# AGREEMENT CRUD
# =====================================================================


class TestAgreementCrud:
    """Test agreement create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_agreements(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agreements")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_agreements_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agreements", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_agreements_filter_direction(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agreements", params={"direction": "inbound"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["direction"] == "inbound"

    @pytest.mark.anyio
    async def test_list_agreements_filter_method(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agreements", params={"method": "sftp"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["transfer_method"] == "sftp"

    @pytest.mark.anyio
    async def test_list_agreements_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agreements", params={"status": "active"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "active"

    @pytest.mark.anyio
    async def test_list_agreements_filter_frequency(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agreements", params={"frequency": "daily"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["frequency"] == "daily"

    @pytest.mark.anyio
    async def test_get_agreement(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agreements/DTA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DTA-001"
        assert data["partner_name"] == "Covance Central Lab"

    @pytest.mark.anyio
    async def test_get_agreement_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agreements/DTA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_agreement(self, client: AsyncClient):
        payload = _make_agreement_create()
        resp = await client.post(f"{API_PREFIX}/agreements", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["partner_name"] == "Test Partner CRO"
        assert data["id"].startswith("DTA-")
        assert data["status"] == "draft"

    @pytest.mark.anyio
    async def test_create_agreement_has_created_at(self, client: AsyncClient):
        payload = _make_agreement_create()
        resp = await client.post(f"{API_PREFIX}/agreements", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["created_at"] is not None

    @pytest.mark.anyio
    async def test_update_agreement(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/agreements/DTA-001",
            json={"status": "suspended", "frequency": "weekly"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "suspended"
        assert data["frequency"] == "weekly"

    @pytest.mark.anyio
    async def test_update_agreement_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/agreements/DTA-NONEXISTENT",
            json={"status": "suspended"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_agreement_effective_date(self, client: AsyncClient):
        now = datetime.now(timezone.utc).isoformat()
        resp = await client.put(
            f"{API_PREFIX}/agreements/DTA-012",
            json={"effective_date": now, "status": "active"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["effective_date"] is not None
        assert data["status"] == "active"

    @pytest.mark.anyio
    async def test_delete_agreement(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/agreements/DTA-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/agreements/DTA-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_agreement_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/agreements/DTA-NONEXISTENT")
        assert resp.status_code == 404

    def test_agreement_has_required_fields(self, svc: DataTransferService):
        agreement = svc.get_agreement("DTA-001")
        assert agreement is not None
        assert agreement.id
        assert agreement.trial_id
        assert agreement.partner_name
        assert agreement.partner_type
        assert agreement.direction is not None
        assert agreement.transfer_method is not None
        assert agreement.frequency is not None
        assert agreement.responsible_person
        assert agreement.technical_contact


# =====================================================================
# EXECUTION CRUD
# =====================================================================


class TestExecutionCrud:
    """Test execution create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_executions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/executions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 15

    @pytest.mark.anyio
    async def test_list_executions_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/executions", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_executions_filter_agreement(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/executions", params={"agreement_id": "DTA-001"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["agreement_id"] == "DTA-001"

    @pytest.mark.anyio
    async def test_list_executions_filter_direction(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/executions", params={"direction": "inbound"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["direction"] == "inbound"

    @pytest.mark.anyio
    async def test_list_executions_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/executions", params={"status": "completed"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_list_executions_sorted_by_date_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/executions")
        data = resp.json()
        dates = [item["transfer_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_get_execution(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/executions/DTE-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DTE-001"
        assert data["status"] == "completed"

    @pytest.mark.anyio
    async def test_get_execution_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/executions/DTE-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_execution(self, client: AsyncClient):
        payload = _make_execution_create()
        resp = await client.post(f"{API_PREFIX}/executions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["agreement_id"] == "DTA-001"
        assert data["status"] == "scheduled"
        assert data["id"].startswith("DTE-")

    @pytest.mark.anyio
    async def test_create_execution_invalid_agreement(self, client: AsyncClient):
        payload = _make_execution_create(agreement_id="DTA-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/executions", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_execution(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/executions/DTE-013",
            json={"status": "in_progress"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"

    @pytest.mark.anyio
    async def test_update_execution_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/executions/DTE-NONEXISTENT",
            json={"status": "completed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_execution_records(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/executions/DTE-009",
            json={"records_transferred": 500, "status": "completed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["records_transferred"] == 500
        assert data["status"] == "completed"

    @pytest.mark.anyio
    async def test_update_execution_error_message(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/executions/DTE-009",
            json={"status": "failed", "error_message": "Connection refused"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failed"
        assert data["error_message"] == "Connection refused"

    @pytest.mark.anyio
    async def test_delete_execution(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/executions/DTE-014")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/executions/DTE-014")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_execution_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/executions/DTE-NONEXISTENT")
        assert resp.status_code == 404

    def test_completed_execution_has_duration(self, svc: DataTransferService):
        execution = svc.get_execution("DTE-001")
        assert execution is not None
        assert execution.duration_seconds is not None
        assert execution.duration_seconds > 0

    def test_scheduled_execution_has_no_timestamps(self, svc: DataTransferService):
        execution = svc.get_execution("DTE-013")
        assert execution is not None
        assert execution.started_at is None
        assert execution.completed_at is None
        assert execution.duration_seconds is None

    def test_execution_links_to_agreement(self, svc: DataTransferService):
        execution = svc.get_execution("DTE-001")
        assert execution is not None
        agreement = svc.get_agreement(execution.agreement_id)
        assert agreement is not None


# =====================================================================
# VALIDATION CRUD
# =====================================================================


class TestValidationCrud:
    """Test validation create, read, delete operations."""

    @pytest.mark.anyio
    async def test_list_validations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_validations_filter_execution(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations", params={"execution_id": "DTE-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["execution_id"] == "DTE-001"

    @pytest.mark.anyio
    async def test_list_validations_filter_result(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations", params={"result": "passed"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["result"] == "passed"

    @pytest.mark.anyio
    async def test_list_validations_filter_failed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations", params={"result": "failed"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["result"] == "failed"

    @pytest.mark.anyio
    async def test_get_validation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations/DTV-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DTV-001"
        assert data["result"] == "passed"

    @pytest.mark.anyio
    async def test_get_validation_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations/DTV-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_validation(self, client: AsyncClient):
        payload = _make_validation_create()
        resp = await client.post(f"{API_PREFIX}/validations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["execution_id"] == "DTE-001"
        assert data["result"] == "warnings"
        assert data["id"].startswith("DTV-")

    @pytest.mark.anyio
    async def test_create_validation_invalid_execution(self, client: AsyncClient):
        payload = _make_validation_create(execution_id="DTE-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/validations", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_create_validation_with_issues(self, client: AsyncClient):
        payload = _make_validation_create(
            issues=["Issue 1", "Issue 2", "Issue 3"],
            result="failed",
            records_failed=15,
        )
        resp = await client.post(f"{API_PREFIX}/validations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["issues"]) == 3
        assert data["result"] == "failed"

    @pytest.mark.anyio
    async def test_delete_validation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/validations/DTV-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/validations/DTV-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_validation_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/validations/DTV-NONEXISTENT")
        assert resp.status_code == 404

    def test_validation_has_required_fields(self, svc: DataTransferService):
        validation = svc.get_validation("DTV-001")
        assert validation is not None
        assert validation.id
        assert validation.execution_id
        assert validation.validation_type
        assert validation.result is not None
        assert validation.validated_by
        assert validation.validated_date is not None

    def test_validation_links_to_execution(self, svc: DataTransferService):
        validation = svc.get_validation("DTV-001")
        assert validation is not None
        execution = svc.get_execution(validation.execution_id)
        assert execution is not None


# =====================================================================
# RECONCILIATION CRUD
# =====================================================================


class TestReconciliationCrud:
    """Test reconciliation create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_reconciliations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reconciliations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_reconciliations_filter_execution(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reconciliations", params={"execution_id": "DTE-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["execution_id"] == "DTE-001"

    @pytest.mark.anyio
    async def test_list_reconciliations_filter_reconciled_true(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reconciliations", params={"reconciled": True})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["reconciled"] is True

    @pytest.mark.anyio
    async def test_list_reconciliations_filter_reconciled_false(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reconciliations", params={"reconciled": False})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["reconciled"] is False

    @pytest.mark.anyio
    async def test_get_reconciliation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reconciliations/DTR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DTR-001"
        assert data["reconciled"] is True

    @pytest.mark.anyio
    async def test_get_reconciliation_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reconciliations/DTR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_reconciliation_auto_reconciled(self, client: AsyncClient):
        payload = _make_reconciliation_create()
        resp = await client.post(f"{API_PREFIX}/reconciliations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["reconciled"] is True
        assert data["reconciled_date"] is not None
        assert data["id"].startswith("DTR-")

    @pytest.mark.anyio
    async def test_create_reconciliation_not_reconciled(self, client: AsyncClient):
        payload = _make_reconciliation_create(
            source_record_count=200,
            target_record_count=180,
            matched_records=180,
            unmatched_records=20,
            discrepancy_notes="20 records missing from target",
        )
        resp = await client.post(f"{API_PREFIX}/reconciliations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["reconciled"] is False
        assert data["reconciled_date"] is None

    @pytest.mark.anyio
    async def test_create_reconciliation_invalid_execution(self, client: AsyncClient):
        payload = _make_reconciliation_create(execution_id="DTE-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/reconciliations", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_reconciliation(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reconciliations/DTR-004",
            json={"reconciled": True, "reconciled_by": "Dr. Manual Review"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["reconciled"] is True
        assert data["reconciled_by"] == "Dr. Manual Review"
        assert data["reconciled_date"] is not None

    @pytest.mark.anyio
    async def test_update_reconciliation_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reconciliations/DTR-NONEXISTENT",
            json={"reconciled": True},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_reconciliation_discrepancy_notes(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reconciliations/DTR-004",
            json={"discrepancy_notes": "Updated: files re-transferred successfully"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "re-transferred" in data["discrepancy_notes"]

    @pytest.mark.anyio
    async def test_delete_reconciliation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/reconciliations/DTR-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/reconciliations/DTR-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_reconciliation_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/reconciliations/DTR-NONEXISTENT")
        assert resp.status_code == 404

    def test_reconciliation_links_to_execution(self, svc: DataTransferService):
        reconciliation = svc.get_reconciliation("DTR-001")
        assert reconciliation is not None
        execution = svc.get_execution(reconciliation.execution_id)
        assert execution is not None

    def test_reconciled_records_match_counts(self, svc: DataTransferService):
        reconciliation = svc.get_reconciliation("DTR-001")
        assert reconciliation is not None
        assert reconciliation.reconciled is True
        assert reconciliation.matched_records == reconciliation.source_record_count
        assert reconciliation.matched_records == reconciliation.target_record_count

    def test_unreconciled_has_discrepancy_notes(self, svc: DataTransferService):
        reconciliation = svc.get_reconciliation("DTR-004")
        assert reconciliation is not None
        assert reconciliation.reconciled is False
        assert reconciliation.discrepancy_notes is not None
        assert len(reconciliation.discrepancy_notes) > 0


# =====================================================================
# RECONCILIATION LOGIC
# =====================================================================


class TestReconciliationLogic:
    """Test auto-reconciliation logic."""

    def test_auto_reconcile_when_all_match(self, svc: DataTransferService):
        from app.schemas.data_transfer import TransferReconciliationCreate
        rec = svc.create_reconciliation(TransferReconciliationCreate(
            execution_id="DTE-002",
            source_record_count=100,
            target_record_count=100,
            matched_records=100,
            unmatched_records=0,
            reconciled_by="test",
        ))
        assert rec.reconciled is True
        assert rec.reconciled_date is not None

    def test_not_reconciled_when_source_mismatch(self, svc: DataTransferService):
        from app.schemas.data_transfer import TransferReconciliationCreate
        rec = svc.create_reconciliation(TransferReconciliationCreate(
            execution_id="DTE-002",
            source_record_count=100,
            target_record_count=90,
            matched_records=90,
            unmatched_records=10,
        ))
        assert rec.reconciled is False

    def test_not_reconciled_when_matched_less_than_source(self, svc: DataTransferService):
        from app.schemas.data_transfer import TransferReconciliationCreate
        rec = svc.create_reconciliation(TransferReconciliationCreate(
            execution_id="DTE-002",
            source_record_count=100,
            target_record_count=100,
            matched_records=95,
            unmatched_records=5,
        ))
        assert rec.reconciled is False


# =====================================================================
# METRICS
# =====================================================================


class TestMetrics:
    """Test data transfer metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_agreements"] == 12
        assert data["total_executions"] == 15
        assert data["total_validations"] == 12
        assert data["total_reconciliations"] == 10

    @pytest.mark.anyio
    async def test_get_metrics_by_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_agreements"] == 4
        assert data["total_executions"] == 5

    @pytest.mark.anyio
    async def test_metrics_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": "NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_agreements"] == 0
        assert data["total_executions"] == 0

    def test_metrics_agreements_by_status(self, svc: DataTransferService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.agreements_by_status.values())
        assert total_by_status == metrics.total_agreements

    def test_metrics_agreements_by_method(self, svc: DataTransferService):
        metrics = svc.get_metrics()
        total_by_method = sum(metrics.agreements_by_method.values())
        assert total_by_method == metrics.total_agreements

    def test_metrics_executions_by_status(self, svc: DataTransferService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.executions_by_status.values())
        assert total_by_status == metrics.total_executions

    def test_metrics_successful_transfers(self, svc: DataTransferService):
        metrics = svc.get_metrics()
        completed = [
            e for e in svc.list_executions()
            if e.status == TransferStatus.COMPLETED
        ]
        assert metrics.successful_transfers == len(completed)

    def test_metrics_failed_transfers(self, svc: DataTransferService):
        metrics = svc.get_metrics()
        failed = [
            e for e in svc.list_executions()
            if e.status == TransferStatus.FAILED
        ]
        assert metrics.failed_transfers == len(failed)

    def test_metrics_total_records_transferred(self, svc: DataTransferService):
        metrics = svc.get_metrics()
        expected = sum(e.records_transferred for e in svc.list_executions())
        assert metrics.total_records_transferred == expected

    def test_metrics_validations_passed(self, svc: DataTransferService):
        metrics = svc.get_metrics()
        passed = [
            v for v in svc.list_validations()
            if v.result == ValidationResult.PASSED
        ]
        assert metrics.validations_passed == len(passed)

    def test_metrics_validations_failed(self, svc: DataTransferService):
        metrics = svc.get_metrics()
        failed = [
            v for v in svc.list_validations()
            if v.result == ValidationResult.FAILED
        ]
        assert metrics.validations_failed == len(failed)

    def test_metrics_reconciled_count(self, svc: DataTransferService):
        metrics = svc.get_metrics()
        reconciled = [
            r for r in svc.list_reconciliations()
            if r.reconciled
        ]
        assert metrics.reconciled_count == len(reconciled)

    def test_metrics_avg_duration_positive(self, svc: DataTransferService):
        metrics = svc.get_metrics()
        assert metrics.avg_transfer_duration_seconds > 0

    def test_metrics_avg_duration_from_completed(self, svc: DataTransferService):
        metrics = svc.get_metrics()
        completed = [
            e for e in svc.list_executions()
            if e.status == TransferStatus.COMPLETED and e.duration_seconds is not None
        ]
        if completed:
            expected_avg = sum(e.duration_seconds for e in completed) / len(completed)  # type: ignore[misc]
            assert abs(metrics.avg_transfer_duration_seconds - round(expected_avg, 1)) < 0.2

    @pytest.mark.anyio
    async def test_metrics_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "total_agreements" in data
        assert "agreements_by_status" in data
        assert "agreements_by_method" in data
        assert "total_executions" in data
        assert "executions_by_status" in data
        assert "successful_transfers" in data
        assert "failed_transfers" in data
        assert "total_records_transferred" in data
        assert "total_validations" in data
        assert "validations_passed" in data
        assert "validations_failed" in data
        assert "total_reconciliations" in data
        assert "reconciled_count" in data
        assert "avg_transfer_duration_seconds" in data


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_data_transfer_service()
        svc2 = get_data_transfer_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_data_transfer_service()
        svc2 = reset_data_transfer_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_data_transfer_service()
        svc.delete_agreement("DTA-001")
        assert svc.get_agreement("DTA-001") is None
        svc2 = reset_data_transfer_service()
        assert svc2.get_agreement("DTA-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_agreements_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agreements")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_executions_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/executions")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_validations_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_reconciliations_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reconciliations")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_agreement_all_directions(self, client: AsyncClient):
        for direction in ["inbound", "outbound", "bidirectional"]:
            payload = _make_agreement_create(direction=direction)
            resp = await client.post(f"{API_PREFIX}/agreements", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["direction"] == direction

    @pytest.mark.anyio
    async def test_create_agreement_all_methods(self, client: AsyncClient):
        for method in ["sftp", "api", "encrypted_email", "physical_media", "cloud_share", "direct_database"]:
            payload = _make_agreement_create(transfer_method=method)
            resp = await client.post(f"{API_PREFIX}/agreements", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["transfer_method"] == method

    @pytest.mark.anyio
    async def test_create_agreement_all_frequencies(self, client: AsyncClient):
        for freq in ["real_time", "daily", "weekly", "monthly", "on_demand", "milestone_based"]:
            payload = _make_agreement_create(frequency=freq)
            resp = await client.post(f"{API_PREFIX}/agreements", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["frequency"] == freq

    @pytest.mark.anyio
    async def test_create_validation_all_results(self, client: AsyncClient):
        for result in ["passed", "failed", "warnings", "pending"]:
            payload = _make_validation_create(result=result)
            resp = await client.post(f"{API_PREFIX}/validations", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["result"] == result

    @pytest.mark.anyio
    async def test_agreement_encryption_required_default(self, client: AsyncClient):
        payload = _make_agreement_create()
        resp = await client.post(f"{API_PREFIX}/agreements", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["encryption_required"] is True

    @pytest.mark.anyio
    async def test_create_agreement_empty_data_types(self, client: AsyncClient):
        payload = _make_agreement_create(data_types=[])
        resp = await client.post(f"{API_PREFIX}/agreements", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["data_types"] == []

    @pytest.mark.anyio
    async def test_create_execution_zero_records(self, client: AsyncClient):
        payload = _make_execution_create(records_expected=0, file_count=0)
        resp = await client.post(f"{API_PREFIX}/executions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["records_expected"] == 0

    @pytest.mark.anyio
    async def test_create_validation_no_issues(self, client: AsyncClient):
        payload = _make_validation_create(
            issues=[],
            result="passed",
            records_failed=0,
            records_passed=100,
        )
        resp = await client.post(f"{API_PREFIX}/validations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["issues"] == []


# =====================================================================
# DATA STRUCTURE VALIDATION
# =====================================================================


class TestDataStructure:
    """Test data structure correctness across entities."""

    @pytest.mark.anyio
    async def test_agreement_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agreements/DTA-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "partner_name" in data
        assert "partner_type" in data
        assert "direction" in data
        assert "transfer_method" in data
        assert "frequency" in data
        assert "data_types" in data
        assert "encryption_required" in data
        assert "status" in data
        assert "responsible_person" in data
        assert "technical_contact" in data
        assert "created_at" in data

    @pytest.mark.anyio
    async def test_execution_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/executions/DTE-001")
        data = resp.json()
        assert "id" in data
        assert "agreement_id" in data
        assert "trial_id" in data
        assert "transfer_date" in data
        assert "direction" in data
        assert "status" in data
        assert "records_expected" in data
        assert "records_transferred" in data
        assert "records_failed" in data
        assert "file_count" in data
        assert "total_size_bytes" in data
        assert "initiated_by" in data

    @pytest.mark.anyio
    async def test_validation_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations/DTV-001")
        data = resp.json()
        assert "id" in data
        assert "execution_id" in data
        assert "validation_type" in data
        assert "result" in data
        assert "records_checked" in data
        assert "records_passed" in data
        assert "records_failed" in data
        assert "issues" in data
        assert "validated_by" in data
        assert "validated_date" in data

    @pytest.mark.anyio
    async def test_reconciliation_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reconciliations/DTR-001")
        data = resp.json()
        assert "id" in data
        assert "execution_id" in data
        assert "source_record_count" in data
        assert "target_record_count" in data
        assert "matched_records" in data
        assert "unmatched_records" in data
        assert "reconciled" in data

    def test_active_agreements_have_dates(self, svc: DataTransferService):
        agreements = svc.list_agreements(status=AgreementStatus.ACTIVE)
        for a in agreements:
            assert a.effective_date is not None
            assert a.expiry_date is not None

    def test_draft_agreement_no_dates(self, svc: DataTransferService):
        agreement = svc.get_agreement("DTA-012")
        assert agreement is not None
        assert agreement.status == AgreementStatus.DRAFT
        assert agreement.effective_date is None
        assert agreement.expiry_date is None

    def test_cancelled_execution_no_timestamps(self, svc: DataTransferService):
        execution = svc.get_execution("DTE-014")
        assert execution is not None
        assert execution.status == TransferStatus.CANCELLED
        assert execution.started_at is None
        assert execution.completed_at is None

    def test_in_progress_execution_no_completed_at(self, svc: DataTransferService):
        execution = svc.get_execution("DTE-009")
        assert execution is not None
        assert execution.status == TransferStatus.IN_PROGRESS
        assert execution.started_at is not None
        assert execution.completed_at is None

    def test_partially_completed_has_failed_records(self, svc: DataTransferService):
        execution = svc.get_execution("DTE-010")
        assert execution is not None
        assert execution.status == TransferStatus.PARTIALLY_COMPLETED
        assert execution.records_failed > 0

    def test_completed_executions_no_failed_records(self, svc: DataTransferService):
        """Most completed executions should have zero failed records."""
        execution = svc.get_execution("DTE-001")
        assert execution is not None
        assert execution.status == TransferStatus.COMPLETED
        assert execution.records_failed == 0
        assert execution.records_transferred == execution.records_expected


# =====================================================================
# CROSS-ENTITY RELATIONSHIPS
# =====================================================================


class TestCrossEntityRelationships:
    """Test relationships between entities."""

    def test_execution_references_valid_agreement(self, svc: DataTransferService):
        for e in svc.list_executions():
            agreement = svc.get_agreement(e.agreement_id)
            assert agreement is not None, f"Execution {e.id} references invalid agreement {e.agreement_id}"

    def test_validation_references_valid_execution(self, svc: DataTransferService):
        for v in svc.list_validations():
            execution = svc.get_execution(v.execution_id)
            assert execution is not None, f"Validation {v.id} references invalid execution {v.execution_id}"

    def test_reconciliation_references_valid_execution(self, svc: DataTransferService):
        for r in svc.list_reconciliations():
            execution = svc.get_execution(r.execution_id)
            assert execution is not None, f"Reconciliation {r.id} references invalid execution {r.execution_id}"

    def test_execution_trial_matches_agreement_trial(self, svc: DataTransferService):
        for e in svc.list_executions():
            agreement = svc.get_agreement(e.agreement_id)
            assert agreement is not None
            assert e.trial_id == agreement.trial_id, (
                f"Execution {e.id} trial {e.trial_id} does not match "
                f"agreement {agreement.id} trial {agreement.trial_id}"
            )

    def test_multiple_validations_per_execution(self, svc: DataTransferService):
        """DTE-001 should have multiple validations."""
        validations = svc.list_validations(execution_id="DTE-001")
        assert len(validations) >= 2

    def test_multiple_executions_per_agreement(self, svc: DataTransferService):
        """DTA-001 should have multiple executions."""
        executions = svc.list_executions(agreement_id="DTA-001")
        assert len(executions) >= 2


# =====================================================================
# ENUMERATION VALUES
# =====================================================================


class TestEnumerations:
    """Test enum values are correctly used throughout the system."""

    @pytest.mark.anyio
    async def test_all_directions_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agreements")
        data = resp.json()
        directions = {item["direction"] for item in data["items"]}
        assert "inbound" in directions
        assert "outbound" in directions
        assert "bidirectional" in directions

    @pytest.mark.anyio
    async def test_all_methods_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agreements")
        data = resp.json()
        methods = {item["transfer_method"] for item in data["items"]}
        assert "sftp" in methods
        assert "api" in methods
        assert "encrypted_email" in methods

    @pytest.mark.anyio
    async def test_all_execution_statuses_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/executions")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "completed" in statuses
        assert "failed" in statuses
        assert "in_progress" in statuses
        assert "scheduled" in statuses

    @pytest.mark.anyio
    async def test_all_validation_results_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations")
        data = resp.json()
        results = {item["result"] for item in data["items"]}
        assert "passed" in results
        assert "failed" in results
        assert "warnings" in results
        assert "pending" in results

    @pytest.mark.anyio
    async def test_all_agreement_statuses_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agreements")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "active" in statuses
        assert "suspended" in statuses
        assert "draft" in statuses


# =====================================================================
# UPDATE STATUS TRANSITIONS
# =====================================================================


class TestStatusTransitions:
    """Test status update transitions and auto-timestamps."""

    @pytest.mark.anyio
    async def test_agreement_status_to_active(self, client: AsyncClient):
        now = datetime.now(timezone.utc).isoformat()
        resp = await client.put(
            f"{API_PREFIX}/agreements/DTA-012",
            json={"status": "active", "effective_date": now},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "active"

    @pytest.mark.anyio
    async def test_agreement_status_to_terminated(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/agreements/DTA-001",
            json={"status": "terminated"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "terminated"

    @pytest.mark.anyio
    async def test_agreement_status_to_expired(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/agreements/DTA-001",
            json={"status": "expired"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "expired"

    @pytest.mark.anyio
    async def test_execution_status_to_in_progress(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/executions/DTE-013",
            json={"status": "in_progress"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"
        assert data["started_at"] is not None

    @pytest.mark.anyio
    async def test_update_agreement_method(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/agreements/DTA-001",
            json={"transfer_method": "api"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["transfer_method"] == "api"

    @pytest.mark.anyio
    async def test_update_agreement_data_types(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/agreements/DTA-001",
            json={"data_types": ["new_type_1", "new_type_2"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data_types"] == ["new_type_1", "new_type_2"]

    @pytest.mark.anyio
    async def test_update_execution_total_size(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/executions/DTE-009",
            json={"total_size_bytes": 33554432},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_size_bytes"] == 33554432
