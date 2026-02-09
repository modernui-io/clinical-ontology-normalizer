"""Tests for Electronic Trial Master File (CLINICAL-5).

Covers:
- Schema enum validation (TMFZone, DocumentStatus, ComplianceStatus, ArtifactType,
  InspectionReadiness, SignatureType)
- TMFDocument model validation and serialization
- DocumentSignature model
- TMFSection, InspectionChecklist, InspectionFinding models
- TMFMetrics, ComplianceRule models
- Request/response model validation
- Service singleton pattern
- Seed data verification (40 documents, 20 rules, 2 checklists)
- Document CRUD (create, read, update, delete, list with all filter combinations)
- Document version management
- Approval workflow (review, approve, make-effective)
- Signature management
- Zone completeness analysis
- Compliance rule CRUD
- Inspection readiness assessment
- Document expiry tracking
- Part 11 compliance checking
- GDPR compliance verification
- TMF metrics computation
- Inspection checklist management (CRUD, findings, resolution)
- Missing document identification
- Bulk document import
- Status transition validation
- API endpoint integration tests (all 28+ endpoints)
- Edge cases (not found, invalid transitions, pagination, empty results)
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.etmf import (
    ArtifactType,
    BulkImportRequest,
    ComplianceRule,
    ComplianceRuleCreate,
    ComplianceRuleUpdate,
    ComplianceStatus,
    DocumentApprovalRequest,
    DocumentReviewRequest,
    DocumentSignature,
    DocumentStatus,
    ExpiringDocumentsResponse,
    InspectionChecklist,
    InspectionChecklistCreate,
    InspectionFinding,
    InspectionFindingCreate,
    InspectionReadiness,
    MissingDocumentsResponse,
    SignatureRequest,
    SignatureType,
    TMFDocument,
    TMFDocumentCreate,
    TMFDocumentListResponse,
    TMFDocumentUpdate,
    TMFMetrics,
    TMFSection,
    TMFZone,
)
from app.services.etmf_service import (
    ETMFService,
    VALID_STATUS_TRANSITIONS,
    get_etmf_service,
    reset_etmf_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"
BASE = "http://test/api/v1/etmf"

# Reset singleton at module load to guarantee fresh seed data
reset_etmf_service()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def svc() -> ETMFService:
    """Get the service (singleton, seeded at module load)."""
    return get_etmf_service()


@pytest.fixture()
async def client():
    """Async HTTP client for API tests."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ===========================================================================
# 1. ENUM VALIDATION TESTS
# ===========================================================================


class TestEnums:
    """Enum coverage tests."""

    def test_tmf_zone_has_11_values(self):
        assert len(TMFZone) == 11

    def test_tmf_zone_values(self):
        assert TMFZone.ZONE_01_TRIAL_MANAGEMENT.value == "ZONE_01_TRIAL_MANAGEMENT"
        assert TMFZone.ZONE_11_STATISTICS.value == "ZONE_11_STATISTICS"

    def test_document_status_values(self):
        statuses = [s.value for s in DocumentStatus]
        assert "DRAFT" in statuses
        assert "EFFECTIVE" in statuses
        assert "ARCHIVED" in statuses
        assert "WITHDRAWN" in statuses
        assert len(DocumentStatus) == 7

    def test_compliance_status_values(self):
        assert len(ComplianceStatus) == 4
        assert ComplianceStatus.COMPLIANT.value == "COMPLIANT"

    def test_artifact_type_values(self):
        assert len(ArtifactType) == 15
        assert ArtifactType.PROTOCOL.value == "PROTOCOL"
        assert ArtifactType.DRUG_ACCOUNTABILITY.value == "DRUG_ACCOUNTABILITY"

    def test_inspection_readiness_values(self):
        assert len(InspectionReadiness) == 4
        assert InspectionReadiness.READY.value == "READY"

    def test_signature_type_values(self):
        assert len(SignatureType) == 3
        assert SignatureType.ELECTRONIC.value == "ELECTRONIC"
        assert SignatureType.WET_INK.value == "WET_INK"
        assert SignatureType.DIGITAL_CERTIFICATE.value == "DIGITAL_CERTIFICATE"


# ===========================================================================
# 2. MODEL VALIDATION TESTS
# ===========================================================================


class TestModels:
    """Pydantic model tests."""

    def test_document_signature_model(self):
        sig = DocumentSignature(
            signer_name="Dr. Test",
            signer_role="PI",
            signature_type=SignatureType.ELECTRONIC,
            signed_at=datetime.now(timezone.utc),
            reason="approval",
        )
        assert sig.signer_name == "Dr. Test"
        assert sig.signature_type == SignatureType.ELECTRONIC

    def test_tmf_document_defaults(self):
        doc = TMFDocument(
            id="test-1",
            trial_id="trial-1",
            zone=TMFZone.ZONE_01_TRIAL_MANAGEMENT,
            artifact_type=ArtifactType.PROTOCOL,
            title="Test Protocol",
            uploaded_at=datetime.now(timezone.utc),
        )
        assert doc.status == DocumentStatus.DRAFT
        assert doc.compliance_status == ComplianceStatus.NOT_ASSESSED
        assert doc.part11_compliant is False
        assert doc.signatures == []
        assert doc.metadata_tags == {}

    def test_tmf_document_full(self):
        now = datetime.now(timezone.utc)
        doc = TMFDocument(
            id="test-2",
            trial_id="trial-1",
            zone=TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS,
            artifact_type=ArtifactType.ICF,
            title="Informed Consent",
            description="Patient consent form",
            version="2.0",
            status=DocumentStatus.EFFECTIVE,
            file_path="/docs/icf.pdf",
            file_size_bytes=100000,
            mime_type="application/pdf",
            uploaded_by="admin",
            uploaded_at=now,
            reviewed_by="reviewer",
            reviewed_at=now,
            approved_by="approver",
            approved_at=now,
            effective_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
            site_id="SITE-001",
            country="US",
            signatures=[],
            metadata_tags={"version": "2.0"},
            compliance_status=ComplianceStatus.COMPLIANT,
            part11_compliant=True,
            gdpr_compliant=True,
        )
        assert doc.version == "2.0"
        assert doc.part11_compliant is True

    def test_inspection_finding_model(self):
        finding = InspectionFinding(
            zone=TMFZone.ZONE_05_SITE_MANAGEMENT,
            description="Missing CV",
            severity="major",
            corrective_action="Request CV",
            due_date=date.today() + timedelta(days=14),
            resolved=False,
        )
        assert finding.severity == "major"
        assert finding.resolved is False

    def test_tmf_section_model(self):
        section = TMFSection(
            zone=TMFZone.ZONE_01_TRIAL_MANAGEMENT,
            expected_documents=5,
            actual_documents=3,
            completeness_percent=60.0,
            compliance_status=ComplianceStatus.PARTIALLY_COMPLIANT,
        )
        assert section.completeness_percent == 60.0

    def test_inspection_checklist_model(self):
        chk = InspectionChecklist(
            id="chk-test",
            trial_id="trial-1",
            created_at=datetime.now(timezone.utc),
        )
        assert chk.overall_readiness == InspectionReadiness.IN_PREPARATION
        assert chk.findings == []

    def test_tmf_metrics_model(self):
        m = TMFMetrics(total_documents=100, completeness_percent=85.5)
        assert m.total_documents == 100
        assert m.documents_expiring_30d == 0

    def test_compliance_rule_model(self):
        rule = ComplianceRule(
            id="rule-test",
            name="Test Rule",
            zone=TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS,
            artifact_type=ArtifactType.PROTOCOL,
        )
        assert rule.required is True
        assert rule.retention_years == 15

    def test_document_create_model(self):
        req = TMFDocumentCreate(
            trial_id="trial-1",
            zone=TMFZone.ZONE_01_TRIAL_MANAGEMENT,
            artifact_type=ArtifactType.PROTOCOL,
            title="New Protocol",
        )
        assert req.version == "1.0"
        assert req.uploaded_by == "system"

    def test_document_update_model_optional(self):
        req = TMFDocumentUpdate()
        assert req.title is None
        assert req.status is None

    def test_approval_request_model(self):
        req = DocumentApprovalRequest(approved_by="Dr. Approver")
        assert req.comment == ""

    def test_signature_request_model(self):
        req = SignatureRequest(
            signer_name="Dr. Test",
            signer_role="PI",
        )
        assert req.signature_type == SignatureType.ELECTRONIC

    def test_bulk_import_response_defaults(self):
        from app.schemas.etmf import BulkImportResponse
        resp = BulkImportResponse()
        assert resp.imported == 0
        assert resp.errors == []


# ===========================================================================
# 3. SERVICE SINGLETON TESTS
# ===========================================================================


class TestServiceSingleton:
    """Service singleton and initialization tests."""

    def test_singleton_returns_same_instance(self):
        svc1 = get_etmf_service()
        svc2 = get_etmf_service()
        assert svc1 is svc2

    def test_service_has_stats(self, svc: ETMFService):
        stats = svc.get_stats()
        assert stats["total_documents"] >= 40
        assert stats["total_compliance_rules"] >= 20
        assert stats["total_inspection_checklists"] >= 2


# ===========================================================================
# 4. SEED DATA VERIFICATION TESTS
# ===========================================================================


class TestSeedData:
    """Verify seed data integrity."""

    def test_seed_document_count(self, svc: ETMFService):
        docs, total = svc.list_documents(limit=100)
        assert total >= 40

    def test_seed_documents_across_all_zones(self, svc: ETMFService):
        docs, _ = svc.list_documents(limit=100)
        zones_present = {d.zone for d in docs}
        assert len(zones_present) == 11

    def test_seed_documents_across_three_trials(self, svc: ETMFService):
        docs, _ = svc.list_documents(limit=100)
        trial_ids = {d.trial_id for d in docs}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_eylea_documents(self, svc: ETMFService):
        docs, total = svc.list_documents(trial_id=EYLEA_TRIAL, limit=100)
        assert total >= 15

    def test_seed_dupixent_documents(self, svc: ETMFService):
        docs, total = svc.list_documents(trial_id=DUPIXENT_TRIAL, limit=100)
        assert total >= 10

    def test_seed_libtayo_documents(self, svc: ETMFService):
        docs, total = svc.list_documents(trial_id=LIBTAYO_TRIAL, limit=100)
        assert total >= 5

    def test_seed_compliance_rules_count(self, svc: ETMFService):
        rules = svc.list_compliance_rules()
        assert len(rules) >= 20

    def test_seed_inspection_checklists(self, svc: ETMFService):
        checklists = svc.list_inspection_checklists()
        assert len(checklists) >= 2

    def test_seed_checklist_001_has_findings(self, svc: ETMFService):
        chk = svc.get_inspection_checklist("chk-001")
        assert chk is not None
        assert len(chk.findings) >= 2

    def test_seed_checklist_002_has_findings(self, svc: ETMFService):
        chk = svc.get_inspection_checklist("chk-002")
        assert chk is not None
        assert len(chk.findings) >= 1

    def test_seed_documents_have_signatures(self, svc: ETMFService):
        docs, _ = svc.list_documents(limit=100)
        signed_docs = [d for d in docs if d.signatures]
        assert len(signed_docs) >= 5

    def test_seed_documents_have_various_statuses(self, svc: ETMFService):
        docs, _ = svc.list_documents(limit=100)
        statuses = {d.status for d in docs}
        assert DocumentStatus.DRAFT in statuses
        assert DocumentStatus.EFFECTIVE in statuses
        assert DocumentStatus.APPROVED in statuses
        assert DocumentStatus.UNDER_REVIEW in statuses


# ===========================================================================
# 5. DOCUMENT CRUD TESTS
# ===========================================================================


class TestDocumentCRUD:
    """Document CRUD operations."""

    def test_create_document(self, svc: ETMFService):
        doc = svc.create_document(TMFDocumentCreate(
            trial_id=EYLEA_TRIAL,
            zone=TMFZone.ZONE_01_TRIAL_MANAGEMENT,
            artifact_type=ArtifactType.PROTOCOL,
            title="Test Protocol Creation",
        ))
        assert doc.id.startswith("tmf-doc-")
        assert doc.status == DocumentStatus.DRAFT
        assert doc.trial_id == EYLEA_TRIAL

    def test_get_document(self, svc: ETMFService):
        doc = svc.get_document("tmf-doc-001")
        assert doc is not None
        assert doc.id == "tmf-doc-001"

    def test_get_document_not_found(self, svc: ETMFService):
        doc = svc.get_document("nonexistent")
        assert doc is None

    def test_update_document_title(self, svc: ETMFService):
        doc = svc.create_document(TMFDocumentCreate(
            trial_id=EYLEA_TRIAL,
            zone=TMFZone.ZONE_01_TRIAL_MANAGEMENT,
            artifact_type=ArtifactType.PROTOCOL,
            title="Original Title",
        ))
        updated = svc.update_document(doc.id, TMFDocumentUpdate(title="Updated Title"))
        assert updated is not None
        assert updated.title == "Updated Title"

    def test_update_document_not_found(self, svc: ETMFService):
        result = svc.update_document("nonexistent", TMFDocumentUpdate(title="X"))
        assert result is None

    def test_delete_document(self, svc: ETMFService):
        doc = svc.create_document(TMFDocumentCreate(
            trial_id=EYLEA_TRIAL,
            zone=TMFZone.ZONE_01_TRIAL_MANAGEMENT,
            artifact_type=ArtifactType.PROTOCOL,
            title="To Delete",
        ))
        assert svc.delete_document(doc.id) is True
        assert svc.get_document(doc.id) is None

    def test_delete_document_not_found(self, svc: ETMFService):
        assert svc.delete_document("nonexistent") is False

    def test_list_documents_no_filter(self, svc: ETMFService):
        docs, total = svc.list_documents()
        assert total >= 40
        assert len(docs) <= 50

    def test_list_documents_by_trial(self, svc: ETMFService):
        docs, total = svc.list_documents(trial_id=EYLEA_TRIAL)
        assert all(d.trial_id == EYLEA_TRIAL for d in docs)

    def test_list_documents_by_zone(self, svc: ETMFService):
        docs, total = svc.list_documents(zone=TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS)
        assert all(d.zone == TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS for d in docs)

    def test_list_documents_by_artifact_type(self, svc: ETMFService):
        docs, total = svc.list_documents(artifact_type=ArtifactType.PROTOCOL)
        assert all(d.artifact_type == ArtifactType.PROTOCOL for d in docs)

    def test_list_documents_by_status(self, svc: ETMFService):
        docs, total = svc.list_documents(status=DocumentStatus.EFFECTIVE)
        assert all(d.status == DocumentStatus.EFFECTIVE for d in docs)

    def test_list_documents_by_country(self, svc: ETMFService):
        docs, _ = svc.list_documents(country="US")
        assert all(d.country == "US" for d in docs)

    def test_list_documents_pagination(self, svc: ETMFService):
        page1, total = svc.list_documents(limit=5, offset=0)
        page2, _ = svc.list_documents(limit=5, offset=5)
        assert len(page1) == 5
        assert len(page2) == 5
        ids1 = {d.id for d in page1}
        ids2 = {d.id for d in page2}
        assert ids1.isdisjoint(ids2)

    def test_list_documents_combined_filters(self, svc: ETMFService):
        docs, _ = svc.list_documents(
            trial_id=EYLEA_TRIAL,
            zone=TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS,
            status=DocumentStatus.EFFECTIVE,
        )
        for d in docs:
            assert d.trial_id == EYLEA_TRIAL
            assert d.zone == TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS
            assert d.status == DocumentStatus.EFFECTIVE


# ===========================================================================
# 6. STATUS TRANSITION TESTS
# ===========================================================================


class TestStatusTransitions:
    """Status transition validation."""

    def test_valid_transitions_defined(self):
        assert len(VALID_STATUS_TRANSITIONS) == 7

    def test_draft_to_under_review_allowed(self):
        assert DocumentStatus.UNDER_REVIEW in VALID_STATUS_TRANSITIONS[DocumentStatus.DRAFT]

    def test_draft_to_approved_not_allowed(self):
        assert DocumentStatus.APPROVED not in VALID_STATUS_TRANSITIONS[DocumentStatus.DRAFT]

    def test_archived_is_terminal(self):
        assert len(VALID_STATUS_TRANSITIONS[DocumentStatus.ARCHIVED]) == 0

    def test_withdrawn_is_terminal(self):
        assert len(VALID_STATUS_TRANSITIONS[DocumentStatus.WITHDRAWN]) == 0

    def test_invalid_transition_raises(self, svc: ETMFService):
        doc = svc.create_document(TMFDocumentCreate(
            trial_id=EYLEA_TRIAL,
            zone=TMFZone.ZONE_01_TRIAL_MANAGEMENT,
            artifact_type=ArtifactType.PROTOCOL,
            title="Transition Test",
        ))
        with pytest.raises(ValueError, match="Invalid status transition"):
            svc.update_document(doc.id, TMFDocumentUpdate(status=DocumentStatus.EFFECTIVE))

    def test_update_status_valid_transition(self, svc: ETMFService):
        doc = svc.create_document(TMFDocumentCreate(
            trial_id=EYLEA_TRIAL,
            zone=TMFZone.ZONE_01_TRIAL_MANAGEMENT,
            artifact_type=ArtifactType.PROTOCOL,
            title="Valid Transition",
        ))
        updated = svc.update_document(doc.id, TMFDocumentUpdate(status=DocumentStatus.UNDER_REVIEW))
        assert updated is not None
        assert updated.status == DocumentStatus.UNDER_REVIEW


# ===========================================================================
# 7. APPROVAL WORKFLOW TESTS
# ===========================================================================


class TestApprovalWorkflow:
    """Document approval workflow."""

    def test_submit_for_review(self, svc: ETMFService):
        doc = svc.create_document(TMFDocumentCreate(
            trial_id=EYLEA_TRIAL,
            zone=TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS,
            artifact_type=ArtifactType.PROTOCOL,
            title="Review Workflow Test",
        ))
        reviewed = svc.submit_for_review(doc.id, DocumentReviewRequest(reviewed_by="Dr. Reviewer"))
        assert reviewed is not None
        assert reviewed.status == DocumentStatus.UNDER_REVIEW
        assert reviewed.reviewed_by == "Dr. Reviewer"

    def test_submit_for_review_wrong_status(self, svc: ETMFService):
        # Find an effective doc
        doc = svc.get_document("tmf-doc-001")
        assert doc is not None
        assert doc.status == DocumentStatus.EFFECTIVE
        with pytest.raises(ValueError, match="must be DRAFT"):
            svc.submit_for_review(doc.id, DocumentReviewRequest(reviewed_by="Dr. X"))

    def test_submit_for_review_not_found(self, svc: ETMFService):
        result = svc.submit_for_review("nonexistent", DocumentReviewRequest(reviewed_by="Dr. X"))
        assert result is None

    def test_approve_document(self, svc: ETMFService):
        doc = svc.create_document(TMFDocumentCreate(
            trial_id=EYLEA_TRIAL,
            zone=TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS,
            artifact_type=ArtifactType.PROTOCOL,
            title="Approval Test",
        ))
        svc.submit_for_review(doc.id, DocumentReviewRequest(reviewed_by="Dr. R"))
        approved = svc.approve_document(doc.id, DocumentApprovalRequest(approved_by="Dr. A"))
        assert approved is not None
        assert approved.status == DocumentStatus.APPROVED
        assert approved.approved_by == "Dr. A"

    def test_approve_document_wrong_status(self, svc: ETMFService):
        doc = svc.create_document(TMFDocumentCreate(
            trial_id=EYLEA_TRIAL,
            zone=TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS,
            artifact_type=ArtifactType.PROTOCOL,
            title="Wrong Status Approve",
        ))
        with pytest.raises(ValueError, match="must be UNDER_REVIEW"):
            svc.approve_document(doc.id, DocumentApprovalRequest(approved_by="Dr. A"))

    def test_approve_document_not_found(self, svc: ETMFService):
        result = svc.approve_document("nonexistent", DocumentApprovalRequest(approved_by="Dr. A"))
        assert result is None

    def test_make_effective(self, svc: ETMFService):
        doc = svc.create_document(TMFDocumentCreate(
            trial_id=EYLEA_TRIAL,
            zone=TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS,
            artifact_type=ArtifactType.PROTOCOL,
            title="Effective Test",
        ))
        svc.submit_for_review(doc.id, DocumentReviewRequest(reviewed_by="Dr. R"))
        svc.approve_document(doc.id, DocumentApprovalRequest(approved_by="Dr. A"))
        effective = svc.make_effective(doc.id)
        assert effective is not None
        assert effective.status == DocumentStatus.EFFECTIVE
        assert effective.effective_date is not None

    def test_make_effective_wrong_status(self, svc: ETMFService):
        doc = svc.create_document(TMFDocumentCreate(
            trial_id=EYLEA_TRIAL,
            zone=TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS,
            artifact_type=ArtifactType.PROTOCOL,
            title="Wrong Effective",
        ))
        with pytest.raises(ValueError, match="must be APPROVED"):
            svc.make_effective(doc.id)

    def test_make_effective_not_found(self, svc: ETMFService):
        result = svc.make_effective("nonexistent")
        assert result is None

    def test_full_workflow_draft_to_effective(self, svc: ETMFService):
        doc = svc.create_document(TMFDocumentCreate(
            trial_id=EYLEA_TRIAL,
            zone=TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS,
            artifact_type=ArtifactType.ICF,
            title="Full Workflow Test",
        ))
        assert doc.status == DocumentStatus.DRAFT
        doc = svc.submit_for_review(doc.id, DocumentReviewRequest(reviewed_by="Dr. R"))
        assert doc.status == DocumentStatus.UNDER_REVIEW
        doc = svc.approve_document(doc.id, DocumentApprovalRequest(approved_by="Dr. A", effective_date=date.today()))
        assert doc.status == DocumentStatus.APPROVED
        doc = svc.make_effective(doc.id)
        assert doc.status == DocumentStatus.EFFECTIVE

    def test_approve_with_effective_date(self, svc: ETMFService):
        doc = svc.create_document(TMFDocumentCreate(
            trial_id=EYLEA_TRIAL,
            zone=TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS,
            artifact_type=ArtifactType.PROTOCOL,
            title="Effective Date Override",
        ))
        svc.submit_for_review(doc.id, DocumentReviewRequest(reviewed_by="Dr. R"))
        future = date.today() + timedelta(days=30)
        approved = svc.approve_document(
            doc.id, DocumentApprovalRequest(approved_by="Dr. A", effective_date=future)
        )
        assert approved.effective_date == future


# ===========================================================================
# 8. SIGNATURE TESTS
# ===========================================================================


class TestSignatures:
    """Document signature tests."""

    def test_add_signature(self, svc: ETMFService):
        doc = svc.create_document(TMFDocumentCreate(
            trial_id=EYLEA_TRIAL,
            zone=TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS,
            artifact_type=ArtifactType.PROTOCOL,
            title="Signature Test",
        ))
        updated = svc.add_signature(doc.id, SignatureRequest(
            signer_name="Dr. Signer",
            signer_role="PI",
            reason="I approve",
        ))
        assert updated is not None
        assert len(updated.signatures) == 1
        assert updated.signatures[0].signer_name == "Dr. Signer"

    def test_add_multiple_signatures(self, svc: ETMFService):
        doc = svc.create_document(TMFDocumentCreate(
            trial_id=EYLEA_TRIAL,
            zone=TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS,
            artifact_type=ArtifactType.ICF,
            title="Multi-Sig Test",
        ))
        svc.add_signature(doc.id, SignatureRequest(signer_name="Dr. A", signer_role="PI"))
        updated = svc.add_signature(doc.id, SignatureRequest(signer_name="Dr. B", signer_role="CRA"))
        assert len(updated.signatures) == 2

    def test_add_signature_not_found(self, svc: ETMFService):
        result = svc.add_signature("nonexistent", SignatureRequest(signer_name="Dr. X", signer_role="PI"))
        assert result is None


# ===========================================================================
# 9. VERSION MANAGEMENT TESTS
# ===========================================================================


class TestVersionManagement:
    """Document versioning tests."""

    def test_create_new_version(self, svc: ETMFService):
        # Use an effective seed doc
        doc = svc.get_document("tmf-doc-005")
        assert doc is not None
        assert doc.status == DocumentStatus.EFFECTIVE

        new_doc = svc.create_new_version("tmf-doc-005", "4.0")
        assert new_doc is not None
        assert new_doc.version == "4.0"
        assert new_doc.status == DocumentStatus.DRAFT

        # Original should be superseded
        original = svc.get_document("tmf-doc-005")
        assert original.status == DocumentStatus.SUPERSEDED

    def test_create_new_version_from_draft(self, svc: ETMFService):
        doc = svc.create_document(TMFDocumentCreate(
            trial_id=EYLEA_TRIAL,
            zone=TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS,
            artifact_type=ArtifactType.PROTOCOL,
            title="Draft Version Test",
        ))
        new_doc = svc.create_new_version(doc.id, "2.0")
        assert new_doc is not None
        # Original stays DRAFT (not effective, so not superseded)
        original = svc.get_document(doc.id)
        assert original.status == DocumentStatus.DRAFT

    def test_create_new_version_not_found(self, svc: ETMFService):
        result = svc.create_new_version("nonexistent", "2.0")
        assert result is None

    def test_new_version_preserves_metadata(self, svc: ETMFService):
        doc = svc.create_document(TMFDocumentCreate(
            trial_id=EYLEA_TRIAL,
            zone=TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS,
            artifact_type=ArtifactType.PROTOCOL,
            title="Metadata Version Test",
            metadata_tags={"key": "value"},
        ))
        new_doc = svc.create_new_version(doc.id, "2.0")
        assert "previous_version" in new_doc.metadata_tags


# ===========================================================================
# 10. ZONE COMPLETENESS TESTS
# ===========================================================================


class TestZoneCompleteness:
    """Zone completeness analysis."""

    def test_zone_completeness_eylea(self, svc: ETMFService):
        sections = svc.get_zone_completeness(EYLEA_TRIAL)
        assert len(sections) == 11
        assert all(isinstance(s, TMFSection) for s in sections)

    def test_zone_completeness_has_expected_fields(self, svc: ETMFService):
        sections = svc.get_zone_completeness(EYLEA_TRIAL)
        for s in sections:
            assert s.expected_documents >= 0
            assert 0 <= s.completeness_percent <= 100.0

    def test_zone_completeness_empty_trial(self, svc: ETMFService):
        sections = svc.get_zone_completeness("nonexistent-trial")
        assert len(sections) == 11
        # All zones should show 0 actual documents
        for s in sections:
            assert s.actual_documents == 0


# ===========================================================================
# 11. COMPLIANCE RULE TESTS
# ===========================================================================


class TestComplianceRules:
    """Compliance rule CRUD tests."""

    def test_list_all_rules(self, svc: ETMFService):
        rules = svc.list_compliance_rules()
        assert len(rules) >= 20

    def test_list_rules_by_zone(self, svc: ETMFService):
        rules = svc.list_compliance_rules(zone=TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS)
        assert all(r.zone == TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS for r in rules)
        assert len(rules) >= 3

    def test_list_rules_by_artifact_type(self, svc: ETMFService):
        rules = svc.list_compliance_rules(artifact_type=ArtifactType.PROTOCOL)
        assert all(r.artifact_type == ArtifactType.PROTOCOL for r in rules)

    def test_get_compliance_rule(self, svc: ETMFService):
        rule = svc.get_compliance_rule("rule-001")
        assert rule is not None
        assert rule.id == "rule-001"

    def test_get_compliance_rule_not_found(self, svc: ETMFService):
        assert svc.get_compliance_rule("nonexistent") is None

    def test_create_compliance_rule(self, svc: ETMFService):
        rule = svc.create_compliance_rule(ComplianceRuleCreate(
            name="Custom Test Rule",
            zone=TMFZone.ZONE_01_TRIAL_MANAGEMENT,
            artifact_type=ArtifactType.PROTOCOL,
            description="Test rule",
            review_frequency_days=90,
        ))
        assert rule.id.startswith("rule-")
        assert rule.name == "Custom Test Rule"

    def test_update_compliance_rule(self, svc: ETMFService):
        rule = svc.create_compliance_rule(ComplianceRuleCreate(
            name="Update Test Rule",
            zone=TMFZone.ZONE_01_TRIAL_MANAGEMENT,
            artifact_type=ArtifactType.PROTOCOL,
        ))
        updated = svc.update_compliance_rule(rule.id, ComplianceRuleUpdate(name="Updated Name"))
        assert updated is not None
        assert updated.name == "Updated Name"

    def test_update_compliance_rule_not_found(self, svc: ETMFService):
        result = svc.update_compliance_rule("nonexistent", ComplianceRuleUpdate(name="X"))
        assert result is None

    def test_delete_compliance_rule(self, svc: ETMFService):
        rule = svc.create_compliance_rule(ComplianceRuleCreate(
            name="Delete Test Rule",
            zone=TMFZone.ZONE_01_TRIAL_MANAGEMENT,
            artifact_type=ArtifactType.PROTOCOL,
        ))
        assert svc.delete_compliance_rule(rule.id) is True
        assert svc.get_compliance_rule(rule.id) is None

    def test_delete_compliance_rule_not_found(self, svc: ETMFService):
        assert svc.delete_compliance_rule("nonexistent") is False


# ===========================================================================
# 12. INSPECTION READINESS TESTS
# ===========================================================================


class TestInspectionReadiness:
    """Inspection readiness assessment."""

    def test_assess_eylea_readiness(self, svc: ETMFService):
        readiness = svc.assess_inspection_readiness(EYLEA_TRIAL)
        assert isinstance(readiness, InspectionReadiness)

    def test_assess_empty_trial_readiness(self, svc: ETMFService):
        readiness = svc.assess_inspection_readiness("empty-trial")
        assert readiness == InspectionReadiness.NOT_READY


# ===========================================================================
# 13. EXPIRY TRACKING TESTS
# ===========================================================================


class TestExpiryTracking:
    """Document expiry tracking."""

    def test_get_expiring_documents(self, svc: ETMFService):
        expiring = svc.get_expiring_documents(days_ahead=30)
        assert isinstance(expiring, list)
        for d in expiring:
            assert d.expiry_date is not None

    def test_get_expiring_documents_by_trial(self, svc: ETMFService):
        expiring = svc.get_expiring_documents(days_ahead=60, trial_id=EYLEA_TRIAL)
        assert all(d.trial_id == EYLEA_TRIAL for d in expiring)

    def test_get_expiring_documents_large_window(self, svc: ETMFService):
        exp_30 = svc.get_expiring_documents(days_ahead=30)
        exp_365 = svc.get_expiring_documents(days_ahead=365)
        assert len(exp_365) >= len(exp_30)

    def test_expired_documents_excluded(self, svc: ETMFService):
        """Documents already expired should still show if within window."""
        expiring = svc.get_expiring_documents(days_ahead=365)
        today = date.today()
        for d in expiring:
            assert d.expiry_date >= today


# ===========================================================================
# 14. COMPLIANCE CHECKING TESTS
# ===========================================================================


class TestComplianceChecking:
    """Part 11 and GDPR compliance checks."""

    def test_part11_compliance_all(self, svc: ETMFService):
        result = svc.check_part11_compliance()
        assert "total" in result
        assert "compliant" in result
        assert "non_compliant" in result
        assert "rate" in result
        assert "issues" in result

    def test_part11_compliance_by_trial(self, svc: ETMFService):
        result = svc.check_part11_compliance(trial_id=EYLEA_TRIAL)
        assert result["total"] >= 0

    def test_gdpr_compliance_all(self, svc: ETMFService):
        result = svc.check_gdpr_compliance()
        assert "total" in result
        assert "rate" in result

    def test_gdpr_compliance_by_trial(self, svc: ETMFService):
        result = svc.check_gdpr_compliance(trial_id=DUPIXENT_TRIAL)
        assert result["total"] >= 0

    def test_part11_compliance_empty_trial(self, svc: ETMFService):
        result = svc.check_part11_compliance(trial_id="empty-trial")
        assert result["total"] == 0

    def test_gdpr_compliance_empty_trial(self, svc: ETMFService):
        result = svc.check_gdpr_compliance(trial_id="empty-trial")
        assert result["total"] == 0


# ===========================================================================
# 15. TMF METRICS TESTS
# ===========================================================================


class TestTMFMetrics:
    """TMF metrics computation."""

    def test_get_metrics_global(self, svc: ETMFService):
        metrics = svc.get_metrics()
        assert isinstance(metrics, TMFMetrics)
        assert metrics.total_documents >= 40
        assert len(metrics.by_zone) > 0
        assert len(metrics.by_status) > 0

    def test_get_metrics_by_trial(self, svc: ETMFService):
        metrics = svc.get_metrics(trial_id=EYLEA_TRIAL)
        assert metrics.total_documents >= 15

    def test_metrics_completeness_range(self, svc: ETMFService):
        metrics = svc.get_metrics(trial_id=EYLEA_TRIAL)
        assert 0 <= metrics.completeness_percent <= 100

    def test_metrics_compliance_range(self, svc: ETMFService):
        metrics = svc.get_metrics()
        assert 0 <= metrics.compliance_percent <= 100

    def test_metrics_part11_rate(self, svc: ETMFService):
        metrics = svc.get_metrics()
        assert 0 <= metrics.part11_compliance_rate <= 100


# ===========================================================================
# 16. INSPECTION CHECKLIST TESTS
# ===========================================================================


class TestInspectionChecklists:
    """Inspection checklist management."""

    def test_list_checklists(self, svc: ETMFService):
        checklists = svc.list_inspection_checklists()
        assert len(checklists) >= 2

    def test_list_checklists_by_trial(self, svc: ETMFService):
        checklists = svc.list_inspection_checklists(trial_id=EYLEA_TRIAL)
        assert all(c.trial_id == EYLEA_TRIAL for c in checklists)

    def test_get_checklist(self, svc: ETMFService):
        chk = svc.get_inspection_checklist("chk-001")
        assert chk is not None
        assert chk.trial_id == EYLEA_TRIAL

    def test_get_checklist_not_found(self, svc: ETMFService):
        assert svc.get_inspection_checklist("nonexistent") is None

    def test_create_checklist(self, svc: ETMFService):
        chk = svc.create_inspection_checklist(InspectionChecklistCreate(
            trial_id=LIBTAYO_TRIAL,
            inspector_name="Test Inspector",
            inspection_type="for-cause",
            zones_reviewed=[TMFZone.ZONE_01_TRIAL_MANAGEMENT],
        ))
        assert chk.id.startswith("chk-")
        assert chk.overall_readiness == InspectionReadiness.IN_PREPARATION

    def test_delete_checklist(self, svc: ETMFService):
        chk = svc.create_inspection_checklist(InspectionChecklistCreate(
            trial_id=LIBTAYO_TRIAL,
        ))
        assert svc.delete_inspection_checklist(chk.id) is True
        assert svc.get_inspection_checklist(chk.id) is None

    def test_delete_checklist_not_found(self, svc: ETMFService):
        assert svc.delete_inspection_checklist("nonexistent") is False

    def test_add_finding(self, svc: ETMFService):
        chk = svc.create_inspection_checklist(InspectionChecklistCreate(trial_id=EYLEA_TRIAL))
        updated = svc.add_inspection_finding(chk.id, InspectionFindingCreate(
            zone=TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS,
            description="Missing protocol amendment",
            severity="major",
        ))
        assert updated is not None
        assert len(updated.findings) == 1
        assert updated.overall_readiness == InspectionReadiness.AT_RISK

    def test_add_critical_finding(self, svc: ETMFService):
        chk = svc.create_inspection_checklist(InspectionChecklistCreate(trial_id=EYLEA_TRIAL))
        updated = svc.add_inspection_finding(chk.id, InspectionFindingCreate(
            zone=TMFZone.ZONE_07_SAFETY_REPORTING,
            description="Missing SAE report",
            severity="critical",
        ))
        assert updated.overall_readiness == InspectionReadiness.NOT_READY

    def test_add_finding_not_found(self, svc: ETMFService):
        result = svc.add_inspection_finding("nonexistent", InspectionFindingCreate(
            zone=TMFZone.ZONE_01_TRIAL_MANAGEMENT,
            description="Test",
        ))
        assert result is None

    def test_resolve_finding(self, svc: ETMFService):
        chk = svc.create_inspection_checklist(InspectionChecklistCreate(trial_id=EYLEA_TRIAL))
        svc.add_inspection_finding(chk.id, InspectionFindingCreate(
            zone=TMFZone.ZONE_01_TRIAL_MANAGEMENT,
            description="Minor issue",
            severity="minor",
        ))
        resolved = svc.resolve_inspection_finding(chk.id, 0)
        assert resolved is not None
        assert resolved.findings[0].resolved is True
        assert resolved.overall_readiness == InspectionReadiness.READY

    def test_resolve_finding_invalid_index(self, svc: ETMFService):
        chk = svc.create_inspection_checklist(InspectionChecklistCreate(trial_id=EYLEA_TRIAL))
        with pytest.raises(ValueError, match="out of range"):
            svc.resolve_inspection_finding(chk.id, 0)

    def test_resolve_finding_not_found(self, svc: ETMFService):
        result = svc.resolve_inspection_finding("nonexistent", 0)
        assert result is None


# ===========================================================================
# 17. MISSING DOCUMENT TESTS
# ===========================================================================


class TestMissingDocuments:
    """Missing document identification."""

    def test_missing_documents_eylea(self, svc: ETMFService):
        result = svc.get_missing_documents(EYLEA_TRIAL)
        assert isinstance(result, MissingDocumentsResponse)
        assert result.trial_id == EYLEA_TRIAL

    def test_missing_documents_empty_trial(self, svc: ETMFService):
        result = svc.get_missing_documents("empty-trial")
        assert result.total_missing > 0  # No docs means all required docs are missing


# ===========================================================================
# 18. BULK IMPORT TESTS
# ===========================================================================


class TestBulkImport:
    """Bulk document import."""

    def test_bulk_import_success(self, svc: ETMFService):
        req = BulkImportRequest(documents=[
            TMFDocumentCreate(
                trial_id=EYLEA_TRIAL,
                zone=TMFZone.ZONE_01_TRIAL_MANAGEMENT,
                artifact_type=ArtifactType.PROTOCOL,
                title=f"Bulk Doc {i}",
            )
            for i in range(5)
        ])
        result = svc.bulk_import(req)
        assert result.imported == 5
        assert result.failed == 0
        assert len(result.document_ids) == 5


# ===========================================================================
# 19. API ENDPOINT INTEGRATION TESTS
# ===========================================================================


@pytest.mark.anyio
class TestAPIEndpoints:
    """API integration tests."""

    async def test_list_documents_api(self, client):
        resp = await client.get(f"{BASE}/documents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 40
        assert len(data["items"]) > 0

    async def test_list_documents_with_filters(self, client):
        resp = await client.get(f"{BASE}/documents", params={
            "trial_id": EYLEA_TRIAL,
            "zone": TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS.value,
            "limit": 10,
        })
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["zone"] == TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS.value

    async def test_get_document_api(self, client):
        resp = await client.get(f"{BASE}/documents/tmf-doc-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "tmf-doc-001"

    async def test_get_document_not_found_api(self, client):
        resp = await client.get(f"{BASE}/documents/nonexistent")
        assert resp.status_code == 404

    async def test_create_document_api(self, client):
        resp = await client.post(f"{BASE}/documents", json={
            "trial_id": EYLEA_TRIAL,
            "zone": TMFZone.ZONE_01_TRIAL_MANAGEMENT.value,
            "artifact_type": ArtifactType.PROTOCOL.value,
            "title": "API Created Doc",
        })
        assert resp.status_code == 201
        assert resp.json()["title"] == "API Created Doc"
        assert resp.json()["status"] == DocumentStatus.DRAFT.value

    async def test_update_document_api(self, client):
        # Create first
        create_resp = await client.post(f"{BASE}/documents", json={
            "trial_id": EYLEA_TRIAL,
            "zone": TMFZone.ZONE_01_TRIAL_MANAGEMENT.value,
            "artifact_type": ArtifactType.PROTOCOL.value,
            "title": "To Update via API",
        })
        doc_id = create_resp.json()["id"]

        resp = await client.put(f"{BASE}/documents/{doc_id}", json={
            "title": "Updated via API",
        })
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated via API"

    async def test_update_document_invalid_transition_api(self, client):
        create_resp = await client.post(f"{BASE}/documents", json={
            "trial_id": EYLEA_TRIAL,
            "zone": TMFZone.ZONE_01_TRIAL_MANAGEMENT.value,
            "artifact_type": ArtifactType.PROTOCOL.value,
            "title": "Bad Transition API",
        })
        doc_id = create_resp.json()["id"]

        resp = await client.put(f"{BASE}/documents/{doc_id}", json={
            "status": DocumentStatus.EFFECTIVE.value,
        })
        assert resp.status_code == 400

    async def test_delete_document_api(self, client):
        create_resp = await client.post(f"{BASE}/documents", json={
            "trial_id": EYLEA_TRIAL,
            "zone": TMFZone.ZONE_01_TRIAL_MANAGEMENT.value,
            "artifact_type": ArtifactType.PROTOCOL.value,
            "title": "To Delete via API",
        })
        doc_id = create_resp.json()["id"]

        resp = await client.delete(f"{BASE}/documents/{doc_id}")
        assert resp.status_code == 204

    async def test_delete_document_not_found_api(self, client):
        resp = await client.delete(f"{BASE}/documents/nonexistent")
        assert resp.status_code == 404

    async def test_submit_for_review_api(self, client):
        create_resp = await client.post(f"{BASE}/documents", json={
            "trial_id": EYLEA_TRIAL,
            "zone": TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS.value,
            "artifact_type": ArtifactType.PROTOCOL.value,
            "title": "Review API Test",
        })
        doc_id = create_resp.json()["id"]

        resp = await client.post(f"{BASE}/documents/{doc_id}/review", json={
            "reviewed_by": "API Reviewer",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == DocumentStatus.UNDER_REVIEW.value

    async def test_approve_document_api(self, client):
        create_resp = await client.post(f"{BASE}/documents", json={
            "trial_id": EYLEA_TRIAL,
            "zone": TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS.value,
            "artifact_type": ArtifactType.PROTOCOL.value,
            "title": "Approve API Test",
        })
        doc_id = create_resp.json()["id"]

        await client.post(f"{BASE}/documents/{doc_id}/review", json={
            "reviewed_by": "Reviewer",
        })
        resp = await client.post(f"{BASE}/documents/{doc_id}/approve", json={
            "approved_by": "Approver",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == DocumentStatus.APPROVED.value

    async def test_make_effective_api(self, client):
        create_resp = await client.post(f"{BASE}/documents", json={
            "trial_id": EYLEA_TRIAL,
            "zone": TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS.value,
            "artifact_type": ArtifactType.PROTOCOL.value,
            "title": "Effective API Test",
        })
        doc_id = create_resp.json()["id"]

        await client.post(f"{BASE}/documents/{doc_id}/review", json={"reviewed_by": "R"})
        await client.post(f"{BASE}/documents/{doc_id}/approve", json={"approved_by": "A"})
        resp = await client.post(f"{BASE}/documents/{doc_id}/make-effective")
        assert resp.status_code == 200
        assert resp.json()["status"] == DocumentStatus.EFFECTIVE.value

    async def test_add_signature_api(self, client):
        create_resp = await client.post(f"{BASE}/documents", json={
            "trial_id": EYLEA_TRIAL,
            "zone": TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS.value,
            "artifact_type": ArtifactType.PROTOCOL.value,
            "title": "Signature API Test",
        })
        doc_id = create_resp.json()["id"]

        resp = await client.post(f"{BASE}/documents/{doc_id}/sign", json={
            "signer_name": "Dr. API Signer",
            "signer_role": "Sponsor",
            "reason": "approval",
        })
        assert resp.status_code == 200
        assert len(resp.json()["signatures"]) == 1

    async def test_create_new_version_api(self, client):
        resp = await client.post(
            f"{BASE}/documents/tmf-doc-006/new-version",
            params={"new_version": "3.0"},
        )
        assert resp.status_code == 200
        assert resp.json()["version"] == "3.0"

    async def test_bulk_import_api(self, client):
        resp = await client.post(f"{BASE}/documents/bulk-import", json={
            "documents": [
                {
                    "trial_id": EYLEA_TRIAL,
                    "zone": TMFZone.ZONE_01_TRIAL_MANAGEMENT.value,
                    "artifact_type": ArtifactType.PROTOCOL.value,
                    "title": f"Bulk API Doc {i}",
                }
                for i in range(3)
            ]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["imported"] == 3

    async def test_expiring_documents_api(self, client):
        resp = await client.get(f"{BASE}/documents/expiring", params={"days_ahead": 60})
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    async def test_zone_completeness_api(self, client):
        resp = await client.get(f"{BASE}/zones/{EYLEA_TRIAL}/completeness")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 11

    async def test_missing_documents_api(self, client):
        resp = await client.get(f"{BASE}/zones/{EYLEA_TRIAL}/missing")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL

    async def test_inspection_readiness_api(self, client):
        resp = await client.get(f"{BASE}/zones/{EYLEA_TRIAL}/readiness")
        assert resp.status_code == 200
        data = resp.json()
        assert "inspection_readiness" in data

    async def test_list_compliance_rules_api(self, client):
        resp = await client.get(f"{BASE}/compliance-rules")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 20

    async def test_list_compliance_rules_with_zone_filter(self, client):
        resp = await client.get(f"{BASE}/compliance-rules", params={
            "zone": TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS.value,
        })
        assert resp.status_code == 200

    async def test_get_compliance_rule_api(self, client):
        resp = await client.get(f"{BASE}/compliance-rules/rule-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "rule-001"

    async def test_get_compliance_rule_not_found_api(self, client):
        resp = await client.get(f"{BASE}/compliance-rules/nonexistent")
        assert resp.status_code == 404

    async def test_create_compliance_rule_api(self, client):
        resp = await client.post(f"{BASE}/compliance-rules", json={
            "name": "API Test Rule",
            "zone": TMFZone.ZONE_01_TRIAL_MANAGEMENT.value,
            "artifact_type": ArtifactType.PROTOCOL.value,
        })
        assert resp.status_code == 201
        assert resp.json()["name"] == "API Test Rule"

    async def test_update_compliance_rule_api(self, client):
        create_resp = await client.post(f"{BASE}/compliance-rules", json={
            "name": "To Update Rule",
            "zone": TMFZone.ZONE_01_TRIAL_MANAGEMENT.value,
            "artifact_type": ArtifactType.PROTOCOL.value,
        })
        rule_id = create_resp.json()["id"]

        resp = await client.put(f"{BASE}/compliance-rules/{rule_id}", json={
            "name": "Updated Rule",
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Rule"

    async def test_delete_compliance_rule_api(self, client):
        create_resp = await client.post(f"{BASE}/compliance-rules", json={
            "name": "To Delete Rule",
            "zone": TMFZone.ZONE_01_TRIAL_MANAGEMENT.value,
            "artifact_type": ArtifactType.PROTOCOL.value,
        })
        rule_id = create_resp.json()["id"]

        resp = await client.delete(f"{BASE}/compliance-rules/{rule_id}")
        assert resp.status_code == 204

    async def test_part11_compliance_api(self, client):
        resp = await client.get(f"{BASE}/compliance/part11")
        assert resp.status_code == 200
        data = resp.json()
        assert "rate" in data

    async def test_part11_compliance_by_trial_api(self, client):
        resp = await client.get(f"{BASE}/compliance/part11", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200

    async def test_gdpr_compliance_api(self, client):
        resp = await client.get(f"{BASE}/compliance/gdpr")
        assert resp.status_code == 200
        data = resp.json()
        assert "rate" in data

    async def test_metrics_api(self, client):
        resp = await client.get(f"{BASE}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_documents"] >= 40

    async def test_metrics_by_trial_api(self, client):
        resp = await client.get(f"{BASE}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200

    async def test_list_inspection_checklists_api(self, client):
        resp = await client.get(f"{BASE}/inspection-checklists")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2

    async def test_list_checklists_by_trial_api(self, client):
        resp = await client.get(f"{BASE}/inspection-checklists", params={
            "trial_id": EYLEA_TRIAL,
        })
        assert resp.status_code == 200

    async def test_get_inspection_checklist_api(self, client):
        resp = await client.get(f"{BASE}/inspection-checklists/chk-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "chk-001"

    async def test_get_checklist_not_found_api(self, client):
        resp = await client.get(f"{BASE}/inspection-checklists/nonexistent")
        assert resp.status_code == 404

    async def test_create_inspection_checklist_api(self, client):
        resp = await client.post(f"{BASE}/inspection-checklists", json={
            "trial_id": LIBTAYO_TRIAL,
            "inspector_name": "API Inspector",
            "inspection_type": "routine",
        })
        assert resp.status_code == 201
        assert resp.json()["trial_id"] == LIBTAYO_TRIAL

    async def test_delete_inspection_checklist_api(self, client):
        create_resp = await client.post(f"{BASE}/inspection-checklists", json={
            "trial_id": LIBTAYO_TRIAL,
        })
        chk_id = create_resp.json()["id"]

        resp = await client.delete(f"{BASE}/inspection-checklists/{chk_id}")
        assert resp.status_code == 204

    async def test_add_finding_api(self, client):
        create_resp = await client.post(f"{BASE}/inspection-checklists", json={
            "trial_id": EYLEA_TRIAL,
        })
        chk_id = create_resp.json()["id"]

        resp = await client.post(f"{BASE}/inspection-checklists/{chk_id}/findings", json={
            "zone": TMFZone.ZONE_02_CENTRAL_TRIAL_DOCS.value,
            "description": "API Finding Test",
            "severity": "minor",
        })
        assert resp.status_code == 200
        assert len(resp.json()["findings"]) == 1

    async def test_resolve_finding_api(self, client):
        create_resp = await client.post(f"{BASE}/inspection-checklists", json={
            "trial_id": EYLEA_TRIAL,
        })
        chk_id = create_resp.json()["id"]

        await client.post(f"{BASE}/inspection-checklists/{chk_id}/findings", json={
            "zone": TMFZone.ZONE_01_TRIAL_MANAGEMENT.value,
            "description": "Resolvable Finding",
            "severity": "minor",
        })

        resp = await client.post(f"{BASE}/inspection-checklists/{chk_id}/findings/0/resolve")
        assert resp.status_code == 200
        assert resp.json()["findings"][0]["resolved"] is True

    async def test_resolve_finding_invalid_index_api(self, client):
        create_resp = await client.post(f"{BASE}/inspection-checklists", json={
            "trial_id": EYLEA_TRIAL,
        })
        chk_id = create_resp.json()["id"]

        resp = await client.post(f"{BASE}/inspection-checklists/{chk_id}/findings/99/resolve")
        assert resp.status_code == 400
