"""Tests for P1-010/027/029 compliance features.

P1-010: OMOP acceptance corpus structure validation
P1-027: Consent metadata on Document model and schemas
P1-029: Purpose-of-use tagging in audit middleware
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.datastructures import Headers
from starlette.requests import Request

from app.schemas.base import ConsentStatus, PurposeOfUse


# =========================================================================
# P1-010: Acceptance corpus tests
# =========================================================================


class TestOMOPCorpusStructure:
    """Validate the OMOP acceptance corpus data integrity."""

    def test_import_positive_pairs(self) -> None:
        from tests.fixtures.omop_acceptance_corpus import POSITIVE_PAIRS

        assert len(POSITIVE_PAIRS) >= 20

    def test_import_negative_pairs(self) -> None:
        from tests.fixtures.omop_acceptance_corpus import NEGATIVE_PAIRS

        assert len(NEGATIVE_PAIRS) >= 10

    def test_positive_pairs_unique_texts(self) -> None:
        from tests.fixtures.omop_acceptance_corpus import POSITIVE_PAIRS

        texts = [t.lower() for t, _, _ in POSITIVE_PAIRS]
        assert len(texts) == len(set(texts)), "Duplicate input texts in POSITIVE_PAIRS"

    def test_positive_pairs_have_valid_ids(self) -> None:
        from tests.fixtures.omop_acceptance_corpus import POSITIVE_PAIRS

        for text, cid, cname in POSITIVE_PAIRS:
            assert cid > 0, f"Invalid concept ID for '{text}': {cid}"

    def test_negative_pairs_have_valid_ids(self) -> None:
        from tests.fixtures.omop_acceptance_corpus import NEGATIVE_PAIRS

        for text, bad_id in NEGATIVE_PAIRS:
            assert bad_id > 0, f"Invalid concept ID for '{text}': {bad_id}"

    def test_corpus_covers_four_domains(self) -> None:
        """Corpus must cover meds, conditions, procedures, labs."""
        from tests.fixtures.omop_acceptance_corpus import POSITIVE_PAIRS

        texts = {t.lower() for t, _, _ in POSITIVE_PAIRS}
        assert "aspirin" in texts, "Missing medication domain"
        assert "pneumonia" in texts, "Missing condition domain"
        assert "hemoglobin a1c" in texts, "Missing lab test domain"
        assert "colonoscopy" in texts, "Missing procedure domain"


# =========================================================================
# P1-027: Consent metadata tests
# =========================================================================


class TestConsentStatusEnum:
    """Test the ConsentStatus enum values."""

    def test_all_values_present(self) -> None:
        assert ConsentStatus.OBTAINED == "obtained"
        assert ConsentStatus.PENDING == "pending"
        assert ConsentStatus.DECLINED == "declined"
        assert ConsentStatus.NOT_REQUIRED == "not_required"

    def test_enum_count(self) -> None:
        assert len(ConsentStatus) == 4


class TestDocumentConsentFields:
    """Test consent fields on Document model."""

    def test_document_model_has_consent_fields(self) -> None:
        from app.models.document import Document

        mapper = Document.__table__
        column_names = {c.name for c in mapper.columns}
        assert "residency_country" in column_names
        assert "consent_status" in column_names
        assert "consent_date" in column_names
        assert "consent_reference" in column_names

    def test_residency_country_is_nullable(self) -> None:
        from app.models.document import Document

        col = Document.__table__.c.residency_country
        assert col.nullable is True

    def test_consent_status_is_indexed(self) -> None:
        from app.models.document import Document

        col = Document.__table__.c.consent_status
        assert col.index is True


class TestDocumentCreateSchema:
    """Test DocumentCreate schema with consent fields."""

    def test_create_without_consent(self) -> None:
        from app.schemas.document import DocumentCreate

        doc = DocumentCreate(
            patient_id="P001",
            note_type="progress_note",
            text="Patient presents with cough.",
        )
        assert doc.consent_status is None
        assert doc.residency_country is None

    def test_create_with_consent(self) -> None:
        from app.schemas.document import DocumentCreate

        doc = DocumentCreate(
            patient_id="P001",
            note_type="progress_note",
            text="Patient presents with cough.",
            residency_country="AU",
            consent_status=ConsentStatus.OBTAINED,
            consent_date=datetime(2026, 1, 15, tzinfo=timezone.utc),
            consent_reference="urn:consent:abc-123",
        )
        assert doc.consent_status == ConsentStatus.OBTAINED
        assert doc.residency_country == "AU"
        assert doc.consent_reference == "urn:consent:abc-123"

    def test_country_code_uppercased(self) -> None:
        from app.schemas.document import DocumentCreate

        doc = DocumentCreate(
            patient_id="P001",
            note_type="progress_note",
            text="text",
            residency_country="au",
        )
        assert doc.residency_country == "AU"

    def test_invalid_country_code_too_long(self) -> None:
        from app.schemas.document import DocumentCreate

        with pytest.raises(Exception):
            DocumentCreate(
                patient_id="P001",
                note_type="progress_note",
                text="text",
                residency_country="AUS",  # 3 chars, max is 2
            )


class TestIngestionConsentMetadata:
    """Test the IngestionConsentMetadata schema."""

    def test_schema_creation(self) -> None:
        from app.schemas.consent import IngestionConsentMetadata

        meta = IngestionConsentMetadata(
            residency_country="US",
            consent_status="obtained",
            consent_date=datetime(2026, 2, 1, tzinfo=timezone.utc),
            consent_reference="https://consent.example.com/rec/123",
        )
        assert meta.residency_country == "US"
        assert meta.consent_status == "obtained"

    def test_all_fields_optional(self) -> None:
        from app.schemas.consent import IngestionConsentMetadata

        meta = IngestionConsentMetadata()
        assert meta.residency_country is None
        assert meta.consent_status is None
        assert meta.consent_date is None
        assert meta.consent_reference is None


# =========================================================================
# P1-029: Purpose-of-use tests
# =========================================================================


class TestPurposeOfUseEnum:
    """Test the PurposeOfUse enum values."""

    def test_all_values_present(self) -> None:
        assert PurposeOfUse.TREATMENT == "treatment"
        assert PurposeOfUse.PAYMENT == "payment"
        assert PurposeOfUse.OPERATIONS == "operations"
        assert PurposeOfUse.RESEARCH == "research"
        assert PurposeOfUse.PUBLIC_HEALTH == "public_health"
        assert PurposeOfUse.QUALITY_ASSURANCE == "quality_assurance"

    def test_enum_count(self) -> None:
        assert len(PurposeOfUse) == 6


class TestAuditLogPurposeField:
    """Test purpose_of_use field on AuditLog model."""

    def test_auditlog_has_purpose_of_use_column(self) -> None:
        from app.models.audit import AuditLog

        col_names = {c.name for c in AuditLog.__table__.columns}
        assert "purpose_of_use" in col_names

    def test_purpose_of_use_is_indexed(self) -> None:
        from app.models.audit import AuditLog

        col = AuditLog.__table__.c.purpose_of_use
        assert col.index is True

    def test_purpose_of_use_is_nullable(self) -> None:
        from app.models.audit import AuditLog

        col = AuditLog.__table__.c.purpose_of_use
        assert col.nullable is True


class TestPurposeOfUseMiddleware:
    """Test purpose-of-use detection in audit middleware."""

    def _make_middleware(self):
        from app.api.middleware.audit_middleware import AuditMiddleware

        return AuditMiddleware(app=MagicMock())

    def _make_request(self, path: str, headers: dict | None = None) -> MagicMock:
        """Create a mock request with the given path and headers."""
        req = MagicMock(spec=Request)
        req.url = MagicMock()
        req.url.path = path
        _headers = headers or {}
        req.headers = Headers(headers=_headers)
        req.state = MagicMock()
        return req

    def test_clinical_route_returns_treatment(self) -> None:
        mw = self._make_middleware()
        req = self._make_request("/api/v1/clinical/facts")
        assert mw._determine_purpose_of_use(req) == "treatment"

    def test_billing_route_returns_payment(self) -> None:
        mw = self._make_middleware()
        req = self._make_request("/api/v1/billing/claims")
        assert mw._determine_purpose_of_use(req) == "payment"

    def test_admin_route_returns_operations(self) -> None:
        mw = self._make_middleware()
        req = self._make_request("/api/v1/admin/users")
        assert mw._determine_purpose_of_use(req) == "operations"

    def test_analytics_route_returns_quality_assurance(self) -> None:
        mw = self._make_middleware()
        req = self._make_request("/api/v1/analytics/dashboard")
        assert mw._determine_purpose_of_use(req) == "quality_assurance"

    def test_unknown_route_returns_none(self) -> None:
        mw = self._make_middleware()
        req = self._make_request("/api/v1/documents")
        assert mw._determine_purpose_of_use(req) is None

    def test_header_override(self) -> None:
        mw = self._make_middleware()
        req = self._make_request(
            "/api/v1/clinical/facts",
            headers={"X-Purpose-Of-Use": "research"},
        )
        # Header takes priority over route auto-detection
        assert mw._determine_purpose_of_use(req) == "research"

    def test_header_override_normalized(self) -> None:
        mw = self._make_middleware()
        req = self._make_request(
            "/api/v1/documents",
            headers={"X-Purpose-Of-Use": "Public-Health"},
        )
        assert mw._determine_purpose_of_use(req) == "public_health"

    def test_invalid_header_falls_through_to_route(self) -> None:
        mw = self._make_middleware()
        req = self._make_request(
            "/api/v1/billing/invoices",
            headers={"X-Purpose-Of-Use": "invalid_purpose"},
        )
        # Invalid header value is ignored, falls back to route detection
        assert mw._determine_purpose_of_use(req) == "payment"

    def test_case_insensitive_route_matching(self) -> None:
        mw = self._make_middleware()
        req = self._make_request("/API/V1/Clinical/Patients")
        assert mw._determine_purpose_of_use(req) == "treatment"
