"""Tests for Data Privacy Management (DATA-PRIV).

Covers:
- Seed data verification (consent records, anonymization records, DSRs, PIAs, retention policies)
- Consent record CRUD (create, read, update, delete, list, filter by trial/type/status)
- Anonymization record CRUD (create, read, update, delete, list, filter by trial/method/validated)
- DSR CRUD (create, read, update, delete, list, filter by trial/type/status)
- PIA CRUD (create, read, update, delete, list, filter by trial/status/risk_level)
- Retention policy CRUD (create, read, update, delete, list, filter by trial/active/category)
- Metrics computation
- Consent withdrawal sets withdrawal_date
- DSR completion sets completed_date and days_to_complete
- Error handling (404s for missing records)
- Edge cases (empty filters, no matching results)
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.data_privacy import (
    AnonymizationMethod,
    ConsentStatus,
    ConsentType,
    DSRStatus,
    DSRType,
    PIAStatus,
)
from app.services.data_privacy_service import (
    DataPrivacyService,
    get_data_privacy_service,
    reset_data_privacy_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/data-privacy"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_data_privacy_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> DataPrivacyService:
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


def _make_consent_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "subject_id": "SUBJ-TEST-001",
        "consent_type": "broad",
        "purpose": "Test consent for unit testing",
        "collected_by": "Test Collector",
        "data_categories": ["demographics", "clinical"],
        "retention_period_months": 60,
    }
    defaults.update(overrides)
    return defaults


def _make_anon_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "dataset_name": "Test Dataset",
        "method": "k_anonymity",
        "performed_by": "Test Engineer",
        "records_processed": 100,
        "fields_anonymized": ["name", "dob"],
    }
    defaults.update(overrides)
    return defaults


def _make_dsr_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "subject_id": "SUBJ-TEST-001",
        "request_type": "access",
        "request_details": "Test DSR for unit testing",
        "handled_by": "Test Handler",
        "data_categories_affected": ["demographics"],
    }
    defaults.update(overrides)
    return defaults


def _make_pia_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "assessment_name": "Test PIA Assessment",
        "assessor": "Test Assessor",
        "data_types_assessed": ["clinical", "demographics"],
        "risk_level": "low",
    }
    defaults.update(overrides)
    return defaults


def _make_retention_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "policy_name": "Test Retention Policy",
        "data_category": "clinical",
        "legal_basis": "Test legal basis",
        "created_by": "Test Creator",
        "retention_period_months": 60,
    }
    defaults.update(overrides)
    return defaults


# ===========================================================================
# Seed Data Verification
# ===========================================================================


class TestSeedData:
    """Verify seed data is present and well-formed."""

    def test_consent_records_seeded(self, svc: DataPrivacyService):
        items = svc.list_consent_records()
        assert len(items) == 12

    def test_anonymization_records_seeded(self, svc: DataPrivacyService):
        items = svc.list_anonymization_records()
        assert len(items) == 10

    def test_dsr_seeded(self, svc: DataPrivacyService):
        items = svc.list_dsr()
        assert len(items) == 12

    def test_pia_seeded(self, svc: DataPrivacyService):
        items = svc.list_pia()
        assert len(items) == 10

    def test_retention_policies_seeded(self, svc: DataPrivacyService):
        items = svc.list_retention_policies()
        assert len(items) == 10

    def test_consent_record_fields(self, svc: DataPrivacyService):
        rec = svc.get_consent_record("CONSENT-001")
        assert rec is not None
        assert rec.trial_id == EYLEA_TRIAL
        assert rec.consent_type == ConsentType.BROAD
        assert rec.consent_status == ConsentStatus.ACTIVE
        assert rec.collected_by == "Dr. Sarah Chen"
        assert "genomic" in rec.data_categories

    def test_anonymization_record_fields(self, svc: DataPrivacyService):
        rec = svc.get_anonymization_record("ANON-001")
        assert rec is not None
        assert rec.trial_id == EYLEA_TRIAL
        assert rec.method == AnonymizationMethod.K_ANONYMITY
        assert rec.k_value == 5
        assert rec.validated is True

    def test_dsr_fields(self, svc: DataPrivacyService):
        rec = svc.get_dsr("DSR-001")
        assert rec is not None
        assert rec.trial_id == EYLEA_TRIAL
        assert rec.request_type == DSRType.ACCESS
        assert rec.status == DSRStatus.COMPLETED
        assert rec.days_to_complete == 25

    def test_pia_fields(self, svc: DataPrivacyService):
        rec = svc.get_pia("PIA-001")
        assert rec is not None
        assert rec.trial_id == EYLEA_TRIAL
        assert rec.status == PIAStatus.APPROVED
        assert rec.risk_level == "high"
        assert rec.dpo_approved is True

    def test_retention_policy_fields(self, svc: DataPrivacyService):
        rec = svc.get_retention_policy("RET-001")
        assert rec is not None
        assert rec.trial_id == EYLEA_TRIAL
        assert rec.data_category == "clinical"
        assert rec.retention_period_months == 180
        assert rec.is_active is True

    def test_all_trials_represented_in_consents(self, svc: DataPrivacyService):
        trial_ids = {c.trial_id for c in svc.list_consent_records()}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids


# ===========================================================================
# Consent Record CRUD
# ===========================================================================


class TestConsentRecordCRUD:
    """Test consent record create/read/update/delete via service layer."""

    def test_create_consent_record(self, svc: DataPrivacyService):
        from app.schemas.data_privacy import ConsentRecordCreate
        payload = ConsentRecordCreate(**_make_consent_create())
        rec = svc.create_consent_record(payload)
        assert rec.id.startswith("CONSENT-")
        assert rec.consent_status == ConsentStatus.PENDING
        assert rec.subject_id == "SUBJ-TEST-001"
        assert rec.created_at is not None

    def test_get_consent_record(self, svc: DataPrivacyService):
        rec = svc.get_consent_record("CONSENT-001")
        assert rec is not None
        assert rec.id == "CONSENT-001"

    def test_get_consent_record_not_found(self, svc: DataPrivacyService):
        assert svc.get_consent_record("NONEXISTENT") is None

    def test_update_consent_record(self, svc: DataPrivacyService):
        from app.schemas.data_privacy import ConsentRecordUpdate
        payload = ConsentRecordUpdate(notes="Updated via test")
        updated = svc.update_consent_record("CONSENT-001", payload)
        assert updated is not None
        assert updated.notes == "Updated via test"

    def test_update_consent_record_not_found(self, svc: DataPrivacyService):
        from app.schemas.data_privacy import ConsentRecordUpdate
        payload = ConsentRecordUpdate(notes="Should fail")
        assert svc.update_consent_record("NONEXISTENT", payload) is None

    def test_update_consent_withdrawal_sets_date(self, svc: DataPrivacyService):
        from app.schemas.data_privacy import ConsentRecordUpdate
        payload = ConsentRecordUpdate(consent_status=ConsentStatus.WITHDRAWN)
        updated = svc.update_consent_record("CONSENT-001", payload)
        assert updated is not None
        assert updated.consent_status == ConsentStatus.WITHDRAWN
        assert updated.withdrawal_date is not None

    def test_update_consent_active_sets_consent_date(self, svc: DataPrivacyService):
        from app.schemas.data_privacy import ConsentRecordUpdate
        # Set pending consent to active
        payload = ConsentRecordUpdate(consent_status=ConsentStatus.ACTIVE)
        updated = svc.update_consent_record("CONSENT-008", payload)
        assert updated is not None
        assert updated.consent_status == ConsentStatus.ACTIVE
        assert updated.consent_date is not None

    def test_delete_consent_record(self, svc: DataPrivacyService):
        assert svc.delete_consent_record("CONSENT-001") is True
        assert svc.get_consent_record("CONSENT-001") is None

    def test_delete_consent_record_not_found(self, svc: DataPrivacyService):
        assert svc.delete_consent_record("NONEXISTENT") is False

    def test_filter_consents_by_trial(self, svc: DataPrivacyService):
        items = svc.list_consent_records(trial_id=EYLEA_TRIAL)
        assert all(c.trial_id == EYLEA_TRIAL for c in items)
        assert len(items) >= 3

    def test_filter_consents_by_type(self, svc: DataPrivacyService):
        items = svc.list_consent_records(consent_type=ConsentType.BROAD)
        assert all(c.consent_type == ConsentType.BROAD for c in items)
        assert len(items) >= 3

    def test_filter_consents_by_status(self, svc: DataPrivacyService):
        items = svc.list_consent_records(consent_status=ConsentStatus.ACTIVE)
        assert all(c.consent_status == ConsentStatus.ACTIVE for c in items)

    def test_filter_consents_no_match(self, svc: DataPrivacyService):
        items = svc.list_consent_records(trial_id="nonexistent-trial")
        assert len(items) == 0


# ===========================================================================
# Anonymization Record CRUD
# ===========================================================================


class TestAnonymizationRecordCRUD:
    """Test anonymization record create/read/update/delete via service layer."""

    def test_create_anonymization_record(self, svc: DataPrivacyService):
        from app.schemas.data_privacy import AnonymizationRecordCreate
        payload = AnonymizationRecordCreate(**_make_anon_create())
        rec = svc.create_anonymization_record(payload)
        assert rec.id.startswith("ANON-")
        assert rec.dataset_name == "Test Dataset"
        assert rec.method == AnonymizationMethod.K_ANONYMITY

    def test_get_anonymization_record(self, svc: DataPrivacyService):
        rec = svc.get_anonymization_record("ANON-001")
        assert rec is not None

    def test_get_anonymization_record_not_found(self, svc: DataPrivacyService):
        assert svc.get_anonymization_record("NONEXISTENT") is None

    def test_update_anonymization_record(self, svc: DataPrivacyService):
        from app.schemas.data_privacy import AnonymizationRecordUpdate
        payload = AnonymizationRecordUpdate(validated=True, validated_by="Test Validator")
        updated = svc.update_anonymization_record("ANON-004", payload)
        assert updated is not None
        assert updated.validated is True
        assert updated.validated_by == "Test Validator"

    def test_update_anonymization_record_not_found(self, svc: DataPrivacyService):
        from app.schemas.data_privacy import AnonymizationRecordUpdate
        payload = AnonymizationRecordUpdate(notes="Should fail")
        assert svc.update_anonymization_record("NONEXISTENT", payload) is None

    def test_delete_anonymization_record(self, svc: DataPrivacyService):
        assert svc.delete_anonymization_record("ANON-001") is True
        assert svc.get_anonymization_record("ANON-001") is None

    def test_delete_anonymization_record_not_found(self, svc: DataPrivacyService):
        assert svc.delete_anonymization_record("NONEXISTENT") is False

    def test_filter_anon_by_trial(self, svc: DataPrivacyService):
        items = svc.list_anonymization_records(trial_id=EYLEA_TRIAL)
        assert all(a.trial_id == EYLEA_TRIAL for a in items)
        assert len(items) >= 3

    def test_filter_anon_by_method(self, svc: DataPrivacyService):
        items = svc.list_anonymization_records(method=AnonymizationMethod.K_ANONYMITY)
        assert all(a.method == AnonymizationMethod.K_ANONYMITY for a in items)

    def test_filter_anon_by_validated(self, svc: DataPrivacyService):
        items = svc.list_anonymization_records(validated=True)
        assert all(a.validated is True for a in items)
        items_false = svc.list_anonymization_records(validated=False)
        assert all(a.validated is False for a in items_false)

    def test_filter_anon_no_match(self, svc: DataPrivacyService):
        items = svc.list_anonymization_records(trial_id="nonexistent-trial")
        assert len(items) == 0


# ===========================================================================
# Data Subject Request CRUD
# ===========================================================================


class TestDSRCRUD:
    """Test data subject request create/read/update/delete via service layer."""

    def test_create_dsr(self, svc: DataPrivacyService):
        from app.schemas.data_privacy import DataSubjectRequestCreate
        payload = DataSubjectRequestCreate(**_make_dsr_create())
        rec = svc.create_dsr(payload)
        assert rec.id.startswith("DSR-")
        assert rec.status == DSRStatus.RECEIVED
        assert rec.received_date is not None

    def test_get_dsr(self, svc: DataPrivacyService):
        rec = svc.get_dsr("DSR-001")
        assert rec is not None

    def test_get_dsr_not_found(self, svc: DataPrivacyService):
        assert svc.get_dsr("NONEXISTENT") is None

    def test_update_dsr(self, svc: DataPrivacyService):
        from app.schemas.data_privacy import DataSubjectRequestUpdate
        payload = DataSubjectRequestUpdate(response_details="Updated response")
        updated = svc.update_dsr("DSR-001", payload)
        assert updated is not None
        assert updated.response_details == "Updated response"

    def test_update_dsr_acknowledge_sets_date(self, svc: DataPrivacyService):
        from app.schemas.data_privacy import DataSubjectRequestUpdate
        payload = DataSubjectRequestUpdate(status=DSRStatus.ACKNOWLEDGED)
        updated = svc.update_dsr("DSR-009", payload)
        assert updated is not None
        assert updated.status == DSRStatus.ACKNOWLEDGED
        assert updated.acknowledged_date is not None

    def test_update_dsr_complete_sets_dates(self, svc: DataPrivacyService):
        from app.schemas.data_privacy import DataSubjectRequestUpdate
        payload = DataSubjectRequestUpdate(status=DSRStatus.COMPLETED)
        updated = svc.update_dsr("DSR-005", payload)
        assert updated is not None
        assert updated.status == DSRStatus.COMPLETED
        assert updated.completed_date is not None
        assert updated.days_to_complete is not None

    def test_update_dsr_not_found(self, svc: DataPrivacyService):
        from app.schemas.data_privacy import DataSubjectRequestUpdate
        payload = DataSubjectRequestUpdate(status=DSRStatus.COMPLETED)
        assert svc.update_dsr("NONEXISTENT", payload) is None

    def test_delete_dsr(self, svc: DataPrivacyService):
        assert svc.delete_dsr("DSR-001") is True
        assert svc.get_dsr("DSR-001") is None

    def test_delete_dsr_not_found(self, svc: DataPrivacyService):
        assert svc.delete_dsr("NONEXISTENT") is False

    def test_filter_dsr_by_trial(self, svc: DataPrivacyService):
        items = svc.list_dsr(trial_id=EYLEA_TRIAL)
        assert all(d.trial_id == EYLEA_TRIAL for d in items)
        assert len(items) >= 3

    def test_filter_dsr_by_type(self, svc: DataPrivacyService):
        items = svc.list_dsr(request_type=DSRType.ACCESS)
        assert all(d.request_type == DSRType.ACCESS for d in items)

    def test_filter_dsr_by_status(self, svc: DataPrivacyService):
        items = svc.list_dsr(status=DSRStatus.COMPLETED)
        assert all(d.status == DSRStatus.COMPLETED for d in items)

    def test_filter_dsr_no_match(self, svc: DataPrivacyService):
        items = svc.list_dsr(trial_id="nonexistent-trial")
        assert len(items) == 0


# ===========================================================================
# Privacy Impact Assessment CRUD
# ===========================================================================


class TestPIACRUD:
    """Test PIA create/read/update/delete via service layer."""

    def test_create_pia(self, svc: DataPrivacyService):
        from app.schemas.data_privacy import PrivacyImpactAssessmentCreate
        payload = PrivacyImpactAssessmentCreate(**_make_pia_create())
        rec = svc.create_pia(payload)
        assert rec.id.startswith("PIA-")
        assert rec.status == PIAStatus.PLANNED
        assert rec.assessment_date is not None

    def test_get_pia(self, svc: DataPrivacyService):
        rec = svc.get_pia("PIA-001")
        assert rec is not None

    def test_get_pia_not_found(self, svc: DataPrivacyService):
        assert svc.get_pia("NONEXISTENT") is None

    def test_update_pia(self, svc: DataPrivacyService):
        from app.schemas.data_privacy import PrivacyImpactAssessmentUpdate
        payload = PrivacyImpactAssessmentUpdate(
            status=PIAStatus.COMPLETED,
            reviewer="Test Reviewer",
        )
        updated = svc.update_pia("PIA-005", payload)
        assert updated is not None
        assert updated.status == PIAStatus.COMPLETED
        assert updated.reviewer == "Test Reviewer"

    def test_update_pia_not_found(self, svc: DataPrivacyService):
        from app.schemas.data_privacy import PrivacyImpactAssessmentUpdate
        payload = PrivacyImpactAssessmentUpdate(notes="Should fail")
        assert svc.update_pia("NONEXISTENT", payload) is None

    def test_delete_pia(self, svc: DataPrivacyService):
        assert svc.delete_pia("PIA-001") is True
        assert svc.get_pia("PIA-001") is None

    def test_delete_pia_not_found(self, svc: DataPrivacyService):
        assert svc.delete_pia("NONEXISTENT") is False

    def test_filter_pia_by_trial(self, svc: DataPrivacyService):
        items = svc.list_pia(trial_id=EYLEA_TRIAL)
        assert all(p.trial_id == EYLEA_TRIAL for p in items)
        assert len(items) >= 2

    def test_filter_pia_by_status(self, svc: DataPrivacyService):
        items = svc.list_pia(status=PIAStatus.APPROVED)
        assert all(p.status == PIAStatus.APPROVED for p in items)

    def test_filter_pia_by_risk_level(self, svc: DataPrivacyService):
        items = svc.list_pia(risk_level="high")
        assert all(p.risk_level == "high" for p in items)
        assert len(items) >= 3

    def test_filter_pia_no_match(self, svc: DataPrivacyService):
        items = svc.list_pia(trial_id="nonexistent-trial")
        assert len(items) == 0


# ===========================================================================
# Data Retention Policy CRUD
# ===========================================================================


class TestRetentionPolicyCRUD:
    """Test retention policy create/read/update/delete via service layer."""

    def test_create_retention_policy(self, svc: DataPrivacyService):
        from app.schemas.data_privacy import DataRetentionPolicyCreate
        payload = DataRetentionPolicyCreate(**_make_retention_create())
        rec = svc.create_retention_policy(payload)
        assert rec.id.startswith("RET-")
        assert rec.is_active is True
        assert rec.policy_name == "Test Retention Policy"

    def test_get_retention_policy(self, svc: DataPrivacyService):
        rec = svc.get_retention_policy("RET-001")
        assert rec is not None

    def test_get_retention_policy_not_found(self, svc: DataPrivacyService):
        assert svc.get_retention_policy("NONEXISTENT") is None

    def test_update_retention_policy(self, svc: DataPrivacyService):
        from app.schemas.data_privacy import DataRetentionPolicyUpdate
        payload = DataRetentionPolicyUpdate(
            approved_by="New Approver",
            retention_period_months=240,
        )
        updated = svc.update_retention_policy("RET-001", payload)
        assert updated is not None
        assert updated.approved_by == "New Approver"
        assert updated.retention_period_months == 240

    def test_update_retention_policy_not_found(self, svc: DataPrivacyService):
        from app.schemas.data_privacy import DataRetentionPolicyUpdate
        payload = DataRetentionPolicyUpdate(is_active=False)
        assert svc.update_retention_policy("NONEXISTENT", payload) is None

    def test_delete_retention_policy(self, svc: DataPrivacyService):
        assert svc.delete_retention_policy("RET-001") is True
        assert svc.get_retention_policy("RET-001") is None

    def test_delete_retention_policy_not_found(self, svc: DataPrivacyService):
        assert svc.delete_retention_policy("NONEXISTENT") is False

    def test_filter_retention_by_trial(self, svc: DataPrivacyService):
        items = svc.list_retention_policies(trial_id=EYLEA_TRIAL)
        assert all(p.trial_id == EYLEA_TRIAL for p in items)
        assert len(items) >= 3

    def test_filter_retention_by_active(self, svc: DataPrivacyService):
        items = svc.list_retention_policies(is_active=True)
        assert all(p.is_active is True for p in items)
        items_inactive = svc.list_retention_policies(is_active=False)
        assert all(p.is_active is False for p in items_inactive)
        assert len(items_inactive) >= 1

    def test_filter_retention_by_category(self, svc: DataPrivacyService):
        items = svc.list_retention_policies(data_category="clinical")
        assert all(p.data_category == "clinical" for p in items)

    def test_filter_retention_no_match(self, svc: DataPrivacyService):
        items = svc.list_retention_policies(trial_id="nonexistent-trial")
        assert len(items) == 0


# ===========================================================================
# Metrics
# ===========================================================================


class TestMetrics:
    """Test privacy compliance metrics computation."""

    def test_metrics_consent_totals(self, svc: DataPrivacyService):
        m = svc.get_metrics()
        assert m.total_consent_records == 12
        assert m.active_consents >= 5
        assert m.withdrawn_consents >= 2
        assert sum(m.consents_by_type.values()) == 12
        assert sum(m.consents_by_status.values()) == 12

    def test_metrics_anonymization(self, svc: DataPrivacyService):
        m = svc.get_metrics()
        assert m.total_anonymization_records == 10
        assert sum(m.records_by_method.values()) == 10
        assert m.avg_re_identification_risk > 0

    def test_metrics_dsr(self, svc: DataPrivacyService):
        m = svc.get_metrics()
        assert m.total_dsr == 12
        assert sum(m.dsr_by_type.values()) == 12
        assert sum(m.dsr_by_status.values()) == 12
        assert m.avg_dsr_completion_days > 0

    def test_metrics_pia(self, svc: DataPrivacyService):
        m = svc.get_metrics()
        assert m.total_pia == 10
        assert sum(m.pia_by_status.values()) == 10

    def test_metrics_retention(self, svc: DataPrivacyService):
        m = svc.get_metrics()
        assert m.total_retention_policies == 10
        assert m.active_policies >= 9
        assert m.records_due_deletion > 0


# ===========================================================================
# API Endpoint Tests - Consent Records
# ===========================================================================


class TestConsentRecordAPI:
    """Test consent record API endpoints."""

    @pytest.mark.anyio
    async def test_list_consent_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/consent-records")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_consent_records_filter_by_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/consent-records", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert all(c["trial_id"] == EYLEA_TRIAL for c in data["items"])

    @pytest.mark.anyio
    async def test_list_consent_records_filter_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/consent-records", params={"consent_type": "broad"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(c["consent_type"] == "broad" for c in data["items"])

    @pytest.mark.anyio
    async def test_list_consent_records_filter_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/consent-records", params={"consent_status": "active"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(c["consent_status"] == "active" for c in data["items"])

    @pytest.mark.anyio
    async def test_get_consent_record(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/consent-records/CONSENT-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CONSENT-001"

    @pytest.mark.anyio
    async def test_get_consent_record_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/consent-records/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_consent_record(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/consent-records", json=_make_consent_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("CONSENT-")
        assert data["consent_status"] == "pending"

    @pytest.mark.anyio
    async def test_update_consent_record(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/consent-records/CONSENT-001",
            json={"notes": "API updated"},
        )
        assert resp.status_code == 200
        assert resp.json()["notes"] == "API updated"

    @pytest.mark.anyio
    async def test_update_consent_record_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/consent-records/NONEXISTENT",
            json={"notes": "Should fail"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_consent_record(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/consent-records/CONSENT-001")
        assert resp.status_code == 204
        # Verify deletion
        resp2 = await client.get(f"{API_PREFIX}/consent-records/CONSENT-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_consent_record_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/consent-records/NONEXISTENT")
        assert resp.status_code == 404


# ===========================================================================
# API Endpoint Tests - Anonymization Records
# ===========================================================================


class TestAnonymizationRecordAPI:
    """Test anonymization record API endpoints."""

    @pytest.mark.anyio
    async def test_list_anonymization_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/anonymization-records")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_anonymization_records_filter_by_method(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/anonymization-records",
            params={"method": "k_anonymity"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert all(a["method"] == "k_anonymity" for a in data["items"])

    @pytest.mark.anyio
    async def test_list_anonymization_records_filter_by_validated(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/anonymization-records",
            params={"validated": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert all(a["validated"] is True for a in data["items"])

    @pytest.mark.anyio
    async def test_get_anonymization_record(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/anonymization-records/ANON-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "ANON-001"

    @pytest.mark.anyio
    async def test_get_anonymization_record_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/anonymization-records/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_anonymization_record(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/anonymization-records", json=_make_anon_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("ANON-")

    @pytest.mark.anyio
    async def test_update_anonymization_record(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/anonymization-records/ANON-004",
            json={"validated": True, "validated_by": "API Test Validator"},
        )
        assert resp.status_code == 200
        assert resp.json()["validated"] is True

    @pytest.mark.anyio
    async def test_update_anonymization_record_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/anonymization-records/NONEXISTENT",
            json={"notes": "Should fail"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_anonymization_record(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/anonymization-records/ANON-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_anonymization_record_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/anonymization-records/NONEXISTENT")
        assert resp.status_code == 404


# ===========================================================================
# API Endpoint Tests - Data Subject Requests
# ===========================================================================


class TestDSRAPI:
    """Test DSR API endpoints."""

    @pytest.mark.anyio
    async def test_list_dsr(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dsr")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_dsr_filter_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dsr", params={"request_type": "access"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(d["request_type"] == "access" for d in data["items"])

    @pytest.mark.anyio
    async def test_list_dsr_filter_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dsr", params={"status": "completed"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(d["status"] == "completed" for d in data["items"])

    @pytest.mark.anyio
    async def test_get_dsr(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dsr/DSR-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "DSR-001"

    @pytest.mark.anyio
    async def test_get_dsr_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dsr/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_dsr(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/dsr", json=_make_dsr_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("DSR-")
        assert data["status"] == "received"

    @pytest.mark.anyio
    async def test_update_dsr(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/dsr/DSR-005",
            json={"status": "completed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["completed_date"] is not None

    @pytest.mark.anyio
    async def test_update_dsr_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/dsr/NONEXISTENT",
            json={"status": "completed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_dsr(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/dsr/DSR-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_dsr_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/dsr/NONEXISTENT")
        assert resp.status_code == 404


# ===========================================================================
# API Endpoint Tests - Privacy Impact Assessments
# ===========================================================================


class TestPIAAPI:
    """Test PIA API endpoints."""

    @pytest.mark.anyio
    async def test_list_pia(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pia")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_pia_filter_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pia", params={"status": "approved"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(p["status"] == "approved" for p in data["items"])

    @pytest.mark.anyio
    async def test_list_pia_filter_by_risk_level(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pia", params={"risk_level": "high"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(p["risk_level"] == "high" for p in data["items"])

    @pytest.mark.anyio
    async def test_get_pia(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pia/PIA-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "PIA-001"

    @pytest.mark.anyio
    async def test_get_pia_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pia/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_pia(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/pia", json=_make_pia_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("PIA-")
        assert data["status"] == "planned"

    @pytest.mark.anyio
    async def test_update_pia(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/pia/PIA-005",
            json={"status": "completed", "reviewer": "API Reviewer"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["reviewer"] == "API Reviewer"

    @pytest.mark.anyio
    async def test_update_pia_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/pia/NONEXISTENT",
            json={"notes": "Should fail"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_pia(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/pia/PIA-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_pia_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/pia/NONEXISTENT")
        assert resp.status_code == 404


# ===========================================================================
# API Endpoint Tests - Retention Policies
# ===========================================================================


class TestRetentionPolicyAPI:
    """Test retention policy API endpoints."""

    @pytest.mark.anyio
    async def test_list_retention_policies(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/retention-policies")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_retention_policies_filter_by_active(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/retention-policies",
            params={"is_active": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert all(p["is_active"] is True for p in data["items"])

    @pytest.mark.anyio
    async def test_list_retention_policies_filter_by_category(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/retention-policies",
            params={"data_category": "clinical"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert all(p["data_category"] == "clinical" for p in data["items"])

    @pytest.mark.anyio
    async def test_get_retention_policy(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/retention-policies/RET-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "RET-001"

    @pytest.mark.anyio
    async def test_get_retention_policy_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/retention-policies/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_retention_policy(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/retention-policies", json=_make_retention_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("RET-")

    @pytest.mark.anyio
    async def test_update_retention_policy(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/retention-policies/RET-001",
            json={"approved_by": "API Approver", "retention_period_months": 240},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["approved_by"] == "API Approver"
        assert data["retention_period_months"] == 240

    @pytest.mark.anyio
    async def test_update_retention_policy_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/retention-policies/NONEXISTENT",
            json={"is_active": False},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_retention_policy(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/retention-policies/RET-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_retention_policy_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/retention-policies/NONEXISTENT")
        assert resp.status_code == 404


# ===========================================================================
# API Endpoint Tests - Metrics
# ===========================================================================


class TestMetricsAPI:
    """Test metrics API endpoint."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_consent_records"] == 12
        assert data["total_anonymization_records"] == 10
        assert data["total_dsr"] == 12
        assert data["total_pia"] == 10
        assert data["total_retention_policies"] == 10
        assert data["active_consents"] >= 5
        assert data["withdrawn_consents"] >= 2
        assert data["avg_re_identification_risk"] > 0
        assert data["avg_dsr_completion_days"] > 0
        assert data["active_policies"] >= 9
        assert data["records_due_deletion"] > 0
