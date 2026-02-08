"""Tests for HIPAA Consent Management Service.

Tests verify:
- Consent recording
- Consent checking (active, expired, revoked, not_found)
- Revocation workflow
- Data use authorization check
- Audit trail integrity
- API endpoints (via TestClient)
- Edge cases and error handling
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.consent import router as consent_router
from app.schemas.consent import (
    ConsentStatusValue,
    ConsentType,
    DataUsePurpose,
)
from app.services.consent_service import (
    ConsentService,
    get_consent_service,
    reset_consent_service,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset():
    """Reset singleton between tests."""
    reset_consent_service()
    yield
    reset_consent_service()


@pytest.fixture
def service() -> ConsentService:
    """Fresh ConsentService instance."""
    return ConsentService()


@pytest.fixture
def client() -> TestClient:
    """FastAPI TestClient with consent router mounted."""
    app = FastAPI()
    app.include_router(consent_router, prefix="/api/v1")
    return TestClient(app)


# ===========================================================================
# 1. Consent Recording Tests
# ===========================================================================


class TestConsentRecording:
    """Test recording new consents."""

    def test_record_consent_basic(self, service: ConsentService):
        """Record a basic consent and verify fields."""
        record = service.record_consent(
            patient_id="patient-1",
            consent_type=ConsentType.SCREENING_CONSENT,
            granted_by="coordinator-1",
        )
        assert record.patient_id == "patient-1"
        assert record.consent_type == ConsentType.SCREENING_CONSENT
        assert record.status == ConsentStatusValue.ACTIVE
        assert record.granted_by == "coordinator-1"
        assert record.id is not None
        assert record.granted_at is not None
        assert record.revoked_at is None

    def test_record_consent_with_scope(self, service: ConsentService):
        """Record a consent with scope and expiration."""
        expires = datetime.now(timezone.utc) + timedelta(days=365)
        scope = {"purposes": ["SCREENING", "RESEARCH"], "data_elements": ["demographics", "labs"]}
        record = service.record_consent(
            patient_id="patient-2",
            consent_type=ConsentType.HIPAA_AUTHORIZATION,
            scope=scope,
            granted_by="provider-1",
            expires_at=expires,
        )
        assert record.scope == scope
        assert record.expires_at == expires

    def test_record_consent_supersedes_existing(self, service: ConsentService):
        """Recording the same consent type replaces the previous one."""
        service.record_consent(
            patient_id="patient-1",
            consent_type=ConsentType.SCREENING_CONSENT,
            granted_by="coordinator-1",
        )
        new_record = service.record_consent(
            patient_id="patient-1",
            consent_type=ConsentType.SCREENING_CONSENT,
            granted_by="coordinator-2",
        )
        # Should only have one consent of this type
        consents = service.get_patient_consents("patient-1")
        screening = [c for c in consents if c.consent_type == ConsentType.SCREENING_CONSENT]
        assert len(screening) == 1
        assert screening[0].granted_by == "coordinator-2"
        assert screening[0].id == new_record.id

    def test_record_multiple_consent_types(self, service: ConsentService):
        """Record different consent types for the same patient."""
        service.record_consent(
            patient_id="patient-1",
            consent_type=ConsentType.SCREENING_CONSENT,
            granted_by="coordinator-1",
        )
        service.record_consent(
            patient_id="patient-1",
            consent_type=ConsentType.HIPAA_AUTHORIZATION,
            granted_by="provider-1",
        )
        service.record_consent(
            patient_id="patient-1",
            consent_type=ConsentType.RESEARCH_PARTICIPATION,
            granted_by="investigator-1",
        )
        consents = service.get_patient_consents("patient-1")
        assert len(consents) == 3
        types = {c.consent_type for c in consents}
        assert types == {
            ConsentType.SCREENING_CONSENT,
            ConsentType.HIPAA_AUTHORIZATION,
            ConsentType.RESEARCH_PARTICIPATION,
        }


# ===========================================================================
# 2. Consent Checking Tests
# ===========================================================================


class TestConsentChecking:
    """Test checking consent status (active, expired, revoked, not_found)."""

    def test_check_active_consent(self, service: ConsentService):
        """Active consent returns ACTIVE status."""
        service.record_consent(
            patient_id="patient-1",
            consent_type=ConsentType.SCREENING_CONSENT,
            granted_by="coordinator-1",
        )
        status = service.check_consent("patient-1", ConsentType.SCREENING_CONSENT)
        assert status.status == ConsentStatusValue.ACTIVE
        assert status.consent_record is not None

    def test_check_not_found_consent(self, service: ConsentService):
        """Non-existent consent returns NOT_FOUND."""
        status = service.check_consent("patient-999", ConsentType.SCREENING_CONSENT)
        assert status.status == ConsentStatusValue.NOT_FOUND
        assert status.consent_record is None

    def test_check_expired_consent(self, service: ConsentService):
        """Expired consent is detected and marked."""
        past = datetime.now(timezone.utc) - timedelta(days=1)
        service.record_consent(
            patient_id="patient-1",
            consent_type=ConsentType.HIPAA_AUTHORIZATION,
            granted_by="provider-1",
            expires_at=past,
        )
        status = service.check_consent("patient-1", ConsentType.HIPAA_AUTHORIZATION)
        assert status.status == ConsentStatusValue.EXPIRED
        assert status.consent_record is not None
        assert status.consent_record.status == ConsentStatusValue.EXPIRED

    def test_check_revoked_consent(self, service: ConsentService):
        """Revoked consent returns REVOKED status."""
        service.record_consent(
            patient_id="patient-1",
            consent_type=ConsentType.DATA_SHARING,
            granted_by="coordinator-1",
        )
        service.revoke_consent(
            patient_id="patient-1",
            consent_type=ConsentType.DATA_SHARING,
            revoked_by="patient-1",
            reason="Patient withdrew",
        )
        status = service.check_consent("patient-1", ConsentType.DATA_SHARING)
        assert status.status == ConsentStatusValue.REVOKED

    def test_check_consent_not_expired_yet(self, service: ConsentService):
        """Consent with future expiration is still active."""
        future = datetime.now(timezone.utc) + timedelta(days=365)
        service.record_consent(
            patient_id="patient-1",
            consent_type=ConsentType.HIPAA_AUTHORIZATION,
            granted_by="provider-1",
            expires_at=future,
        )
        status = service.check_consent("patient-1", ConsentType.HIPAA_AUTHORIZATION)
        assert status.status == ConsentStatusValue.ACTIVE


# ===========================================================================
# 3. Revocation Workflow Tests
# ===========================================================================


class TestRevocationWorkflow:
    """Test consent revocation workflow."""

    def test_revoke_active_consent(self, service: ConsentService):
        """Revoking an active consent succeeds."""
        service.record_consent(
            patient_id="patient-1",
            consent_type=ConsentType.SCREENING_CONSENT,
            granted_by="coordinator-1",
        )
        revoked = service.revoke_consent(
            patient_id="patient-1",
            consent_type=ConsentType.SCREENING_CONSENT,
            revoked_by="patient-1",
            reason="Changed mind",
        )
        assert revoked.status == ConsentStatusValue.REVOKED
        assert revoked.revoked_by == "patient-1"
        assert revoked.revocation_reason == "Changed mind"
        assert revoked.revoked_at is not None

    def test_revoke_nonexistent_consent_raises(self, service: ConsentService):
        """Revoking a non-existent consent raises ValueError."""
        with pytest.raises(ValueError, match="No SCREENING_CONSENT consent found"):
            service.revoke_consent(
                patient_id="patient-999",
                consent_type=ConsentType.SCREENING_CONSENT,
                revoked_by="admin",
            )

    def test_revoke_already_revoked_raises(self, service: ConsentService):
        """Revoking an already-revoked consent raises ValueError."""
        service.record_consent(
            patient_id="patient-1",
            consent_type=ConsentType.SCREENING_CONSENT,
            granted_by="coordinator-1",
        )
        service.revoke_consent(
            patient_id="patient-1",
            consent_type=ConsentType.SCREENING_CONSENT,
            revoked_by="patient-1",
        )
        with pytest.raises(ValueError, match="already revoked"):
            service.revoke_consent(
                patient_id="patient-1",
                consent_type=ConsentType.SCREENING_CONSENT,
                revoked_by="patient-1",
            )


# ===========================================================================
# 4. Data Use Authorization Tests
# ===========================================================================


class TestDataUseAuthorization:
    """Test data use authorization checks."""

    def test_screening_authorized_with_screening_consent(self, service: ConsentService):
        """SCREENING purpose is authorized by SCREENING_CONSENT."""
        service.record_consent(
            patient_id="patient-1",
            consent_type=ConsentType.SCREENING_CONSENT,
            granted_by="coordinator-1",
        )
        assert service.check_data_use_authorization("patient-1", DataUsePurpose.SCREENING) is True

    def test_screening_authorized_with_hipaa_auth(self, service: ConsentService):
        """SCREENING purpose is also authorized by HIPAA_AUTHORIZATION."""
        service.record_consent(
            patient_id="patient-1",
            consent_type=ConsentType.HIPAA_AUTHORIZATION,
            granted_by="provider-1",
        )
        assert service.check_data_use_authorization("patient-1", DataUsePurpose.SCREENING) is True

    def test_research_not_authorized_without_consent(self, service: ConsentService):
        """RESEARCH purpose is denied without appropriate consent."""
        assert service.check_data_use_authorization("patient-1", DataUsePurpose.RESEARCH) is False

    def test_research_authorized_with_research_consent(self, service: ConsentService):
        """RESEARCH purpose is authorized by RESEARCH_PARTICIPATION."""
        service.record_consent(
            patient_id="patient-1",
            consent_type=ConsentType.RESEARCH_PARTICIPATION,
            granted_by="investigator-1",
        )
        assert service.check_data_use_authorization("patient-1", DataUsePurpose.RESEARCH) is True

    def test_marketing_requires_explicit_scope(self, service: ConsentService):
        """MARKETING requires HIPAA_AUTHORIZATION with marketing in scope."""
        # HIPAA auth without marketing scope
        service.record_consent(
            patient_id="patient-1",
            consent_type=ConsentType.HIPAA_AUTHORIZATION,
            scope={"purposes": ["TREATMENT"]},
            granted_by="provider-1",
        )
        assert service.check_data_use_authorization("patient-1", DataUsePurpose.MARKETING) is False

    def test_marketing_authorized_with_scope(self, service: ConsentService):
        """MARKETING is authorized when HIPAA auth scope includes MARKETING."""
        service.record_consent(
            patient_id="patient-1",
            consent_type=ConsentType.HIPAA_AUTHORIZATION,
            scope={"purposes": ["TREATMENT", "MARKETING"]},
            granted_by="provider-1",
        )
        assert service.check_data_use_authorization("patient-1", DataUsePurpose.MARKETING) is True

    def test_authorization_denied_after_revocation(self, service: ConsentService):
        """Authorization is denied after consent is revoked."""
        service.record_consent(
            patient_id="patient-1",
            consent_type=ConsentType.SCREENING_CONSENT,
            granted_by="coordinator-1",
        )
        assert service.check_data_use_authorization("patient-1", DataUsePurpose.SCREENING) is True

        service.revoke_consent(
            patient_id="patient-1",
            consent_type=ConsentType.SCREENING_CONSENT,
            revoked_by="patient-1",
        )
        assert service.check_data_use_authorization("patient-1", DataUsePurpose.SCREENING) is False

    def test_get_data_use_check_returns_details(self, service: ConsentService):
        """get_data_use_check returns a ConsentCheck with reason."""
        service.record_consent(
            patient_id="patient-1",
            consent_type=ConsentType.SCREENING_CONSENT,
            granted_by="coordinator-1",
        )
        check = service.get_data_use_check("patient-1", DataUsePurpose.SCREENING)
        assert check.is_authorized is True
        assert check.consent_type == ConsentType.SCREENING_CONSENT
        assert "Authorized" in check.reason

    def test_get_data_use_check_denied_details(self, service: ConsentService):
        """get_data_use_check returns denial reason when not authorized."""
        check = service.get_data_use_check("patient-999", DataUsePurpose.RESEARCH)
        assert check.is_authorized is False
        assert "No active consent" in check.reason


# ===========================================================================
# 5. Audit Trail Tests
# ===========================================================================


class TestAuditTrail:
    """Test consent audit trail integrity."""

    def test_audit_trail_records_grant(self, service: ConsentService):
        """Recording consent creates a GRANTED audit entry."""
        service.record_consent(
            patient_id="patient-1",
            consent_type=ConsentType.SCREENING_CONSENT,
            granted_by="coordinator-1",
        )
        trail = service.get_consent_audit_trail("patient-1")
        granted_entries = [e for e in trail.entries if e.action == "GRANTED"]
        assert len(granted_entries) == 1
        assert granted_entries[0].actor == "coordinator-1"
        assert granted_entries[0].consent_type == ConsentType.SCREENING_CONSENT

    def test_audit_trail_records_revocation(self, service: ConsentService):
        """Revoking consent creates a REVOKED audit entry."""
        service.record_consent(
            patient_id="patient-1",
            consent_type=ConsentType.SCREENING_CONSENT,
            granted_by="coordinator-1",
        )
        service.revoke_consent(
            patient_id="patient-1",
            consent_type=ConsentType.SCREENING_CONSENT,
            revoked_by="patient-1",
            reason="Withdrew",
        )
        trail = service.get_consent_audit_trail("patient-1")
        revoked_entries = [e for e in trail.entries if e.action == "REVOKED"]
        assert len(revoked_entries) == 1
        assert revoked_entries[0].actor == "patient-1"
        assert "Withdrew" in revoked_entries[0].details

    def test_audit_trail_records_checks(self, service: ConsentService):
        """Checking consent creates CHECKED audit entries."""
        service.record_consent(
            patient_id="patient-1",
            consent_type=ConsentType.SCREENING_CONSENT,
            granted_by="coordinator-1",
        )
        service.check_consent("patient-1", ConsentType.SCREENING_CONSENT)
        trail = service.get_consent_audit_trail("patient-1")
        checked_entries = [e for e in trail.entries if e.action == "CHECKED"]
        assert len(checked_entries) >= 1

    def test_audit_trail_records_expiration(self, service: ConsentService):
        """Checking an expired consent creates an EXPIRED audit entry."""
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        service.record_consent(
            patient_id="patient-1",
            consent_type=ConsentType.HIPAA_AUTHORIZATION,
            granted_by="provider-1",
            expires_at=past,
        )
        service.check_consent("patient-1", ConsentType.HIPAA_AUTHORIZATION)
        trail = service.get_consent_audit_trail("patient-1")
        expired_entries = [e for e in trail.entries if e.action == "EXPIRED"]
        assert len(expired_entries) == 1

    def test_audit_trail_total_entries(self, service: ConsentService):
        """Audit trail total_entries matches entries list length."""
        service.record_consent(
            patient_id="patient-1",
            consent_type=ConsentType.SCREENING_CONSENT,
            granted_by="coordinator-1",
        )
        service.check_consent("patient-1", ConsentType.SCREENING_CONSENT)
        trail = service.get_consent_audit_trail("patient-1")
        assert trail.total_entries == len(trail.entries)
        assert trail.total_entries >= 2  # At least GRANTED + CHECKED

    def test_empty_audit_trail(self, service: ConsentService):
        """Non-existent patient returns empty audit trail."""
        trail = service.get_consent_audit_trail("patient-999")
        assert trail.patient_id == "patient-999"
        assert trail.total_entries == 0
        assert trail.entries == []


# ===========================================================================
# 6. API Endpoint Tests
# ===========================================================================


class TestAPIEndpoints:
    """Test consent management API endpoints via TestClient."""

    def test_api_record_consent(self, client: TestClient):
        """POST /api/v1/consent records a new consent."""
        resp = client.post(
            "/api/v1/consent",
            json={
                "patient_id": "patient-1",
                "consent_type": "SCREENING_CONSENT",
                "granted_by": "coordinator-1",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["patient_id"] == "patient-1"
        assert data["consent_type"] == "SCREENING_CONSENT"
        assert data["status"] == "active"

    def test_api_get_patient_consents(self, client: TestClient):
        """GET /api/v1/consent/patients/{id} returns all consents."""
        client.post(
            "/api/v1/consent",
            json={
                "patient_id": "patient-1",
                "consent_type": "SCREENING_CONSENT",
                "granted_by": "coordinator-1",
            },
        )
        resp = client.get("/api/v1/consent/patients/patient-1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["consent_type"] == "SCREENING_CONSENT"

    def test_api_check_consent(self, client: TestClient):
        """GET /api/v1/consent/check/{id}/{type} returns consent status."""
        client.post(
            "/api/v1/consent",
            json={
                "patient_id": "patient-1",
                "consent_type": "HIPAA_AUTHORIZATION",
                "granted_by": "provider-1",
            },
        )
        resp = client.get("/api/v1/consent/check/patient-1/HIPAA_AUTHORIZATION")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "active"

    def test_api_revoke_consent(self, client: TestClient):
        """POST /api/v1/consent/revoke revokes a consent."""
        client.post(
            "/api/v1/consent",
            json={
                "patient_id": "patient-1",
                "consent_type": "SCREENING_CONSENT",
                "granted_by": "coordinator-1",
            },
        )
        resp = client.post(
            "/api/v1/consent/revoke",
            json={
                "patient_id": "patient-1",
                "consent_type": "SCREENING_CONSENT",
                "revoked_by": "patient-1",
                "reason": "Patient request",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "revoked"
        assert data["revoked_by"] == "patient-1"

    def test_api_revoke_nonexistent_returns_404(self, client: TestClient):
        """POST /api/v1/consent/revoke returns 404 for non-existent consent."""
        resp = client.post(
            "/api/v1/consent/revoke",
            json={
                "patient_id": "patient-999",
                "consent_type": "SCREENING_CONSENT",
                "revoked_by": "admin",
                "reason": "cleanup",
            },
        )
        assert resp.status_code == 404

    def test_api_audit_trail(self, client: TestClient):
        """GET /api/v1/consent/audit/{id} returns audit trail."""
        client.post(
            "/api/v1/consent",
            json={
                "patient_id": "patient-1",
                "consent_type": "SCREENING_CONSENT",
                "granted_by": "coordinator-1",
            },
        )
        resp = client.get("/api/v1/consent/audit/patient-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["patient_id"] == "patient-1"
        assert data["total_entries"] >= 1
        assert len(data["entries"]) >= 1

    def test_api_data_use_authorization(self, client: TestClient):
        """GET /api/v1/consent/authorize/{id}/{purpose} checks authorization."""
        client.post(
            "/api/v1/consent",
            json={
                "patient_id": "patient-1",
                "consent_type": "SCREENING_CONSENT",
                "granted_by": "coordinator-1",
            },
        )
        resp = client.get("/api/v1/consent/authorize/patient-1/SCREENING")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_authorized"] is True


# ===========================================================================
# 7. Service Stats & Edge Cases
# ===========================================================================


class TestServiceStats:
    """Test service statistics and edge cases."""

    def test_get_stats(self, service: ConsentService):
        """get_stats returns correct counts."""
        service.record_consent("p1", ConsentType.SCREENING_CONSENT, granted_by="c1")
        service.record_consent("p1", ConsentType.HIPAA_AUTHORIZATION, granted_by="c1")
        service.record_consent("p2", ConsentType.SCREENING_CONSENT, granted_by="c1")
        stats = service.get_stats()
        assert stats["total_patients"] == 2
        assert stats["total_consent_records"] == 3
        assert stats["active_consents"] == 3

    def test_get_stats_after_revocation(self, service: ConsentService):
        """Stats reflect revoked consents."""
        service.record_consent("p1", ConsentType.SCREENING_CONSENT, granted_by="c1")
        service.revoke_consent("p1", ConsentType.SCREENING_CONSENT, revoked_by="p1")
        stats = service.get_stats()
        assert stats["active_consents"] == 0
        assert stats["total_consent_records"] == 1

    def test_get_patient_consents_empty(self, service: ConsentService):
        """Get consents for non-existent patient returns empty list."""
        consents = service.get_patient_consents("patient-999")
        assert consents == []
