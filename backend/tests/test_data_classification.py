"""Tests for Data Classification Policy and Handling Procedures.

CLO-3: Data Classification Policy and Handling Procedures

Tests verify:
- Classification level definitions (4 levels, ordering, colors)
- Handling rules per level (storage, access, transmission, retention, incident, sharing)
- Pre-populated data assets (30+ assets correctly mapped)
- Asset registration and retrieval (CRUD operations)
- Asset filtering by level, tag, owner
- Asset update and partial update
- Overdue review detection
- Mark reviewed resets review clock
- Reclassification request workflow
- Reclassification approval and asset update
- Reclassification rejection
- Reclassification validation (level mismatch, same level)
- Summary statistics
- Encryption requirements per level
- Access control requirements (MFA, DUA, RBAC)
- Data governance roles
- Audit trail recording
- API endpoints (via TestClient)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.data_classification import router as data_classification_router
from app.schemas.data_classification import (
    ClassificationLevel,
    DataAssetCreate,
    DataAssetUpdate,
    ReclassificationRequest,
    ReclassificationStatus,
)
from app.services.data_classification_service import (
    CLASSIFICATION_LEVELS,
    HANDLING_RULES,
    DataClassificationService,
    get_data_classification_service,
    reset_data_classification_service,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset():
    """Reset singleton between tests."""
    reset_data_classification_service()
    yield
    reset_data_classification_service()


@pytest.fixture
def svc() -> DataClassificationService:
    """Return a fresh DataClassificationService."""
    return get_data_classification_service()


@pytest.fixture
def client() -> TestClient:
    """Return a TestClient wired to the data classification router."""
    app = FastAPI()
    app.include_router(data_classification_router)
    return TestClient(app)


def _make_asset_create(**overrides) -> DataAssetCreate:
    """Helper to build a DataAssetCreate with defaults."""
    defaults = {
        "name": "test_asset",
        "description": "A test data asset for unit tests.",
        "classification_level": ClassificationLevel.INTERNAL,
        "data_owner": "Test Owner",
        "data_steward": "Test Steward",
        "storage_location": "PostgreSQL: test_table",
        "retention_period_days": 365,
        "encryption_required": False,
        "access_restrictions": ["engineer"],
        "review_frequency_days": 365,
        "tags": ["test"],
    }
    defaults.update(overrides)
    return DataAssetCreate(**defaults)


# ===================================================================
# Classification Level Definitions
# ===================================================================


class TestClassificationLevels:
    """Tests for classification level definitions."""

    def test_four_levels_exist(self, svc: DataClassificationService):
        """There are exactly 4 classification levels."""
        levels = svc.get_classification_levels()
        assert len(levels) == 4

    def test_levels_ordered_by_severity(self, svc: DataClassificationService):
        """Levels are returned in ascending severity order."""
        levels = svc.get_classification_levels()
        orders = [l.severity_order for l in levels]
        assert orders == sorted(orders)
        assert levels[0].level == ClassificationLevel.PUBLIC
        assert levels[3].level == ClassificationLevel.RESTRICTED

    def test_public_level_definition(self, svc: DataClassificationService):
        """PUBLIC level has correct attributes."""
        level = svc.get_classification_level(ClassificationLevel.PUBLIC)
        assert level.name == "Public"
        assert level.severity_order == 0
        assert level.color == "#22c55e"
        assert len(level.examples) > 0

    def test_restricted_level_definition(self, svc: DataClassificationService):
        """RESTRICTED level has correct attributes."""
        level = svc.get_classification_level(ClassificationLevel.RESTRICTED)
        assert level.name == "Restricted"
        assert level.severity_order == 3
        assert level.color == "#ef4444"
        assert "PHI" in level.description

    def test_each_level_has_examples(self, svc: DataClassificationService):
        """Every level has at least one example."""
        for level in svc.get_classification_levels():
            assert len(level.examples) >= 1, f"{level.level.value} has no examples"


# ===================================================================
# Handling Rules
# ===================================================================


class TestHandlingRules:
    """Tests for handling procedures per classification level."""

    def test_all_levels_have_rules(self, svc: DataClassificationService):
        """Every classification level has handling rules defined."""
        rules = svc.get_handling_rules()
        assert len(rules) == 4

    def test_public_no_encryption(self, svc: DataClassificationService):
        """PUBLIC data does not require encryption."""
        rules = svc.get_handling_rules_for_level(ClassificationLevel.PUBLIC)
        assert rules.storage.encryption_at_rest is False
        assert rules.transmission.encryption_in_transit is False

    def test_internal_authenticated_access(self, svc: DataClassificationService):
        """INTERNAL data requires authenticated access."""
        rules = svc.get_handling_rules_for_level(ClassificationLevel.INTERNAL)
        assert rules.access_control.authentication_required is True
        assert rules.access_control.mfa_required is False
        assert rules.access_control.access_logging == "standard"

    def test_confidential_encryption_and_rbac(self, svc: DataClassificationService):
        """CONFIDENTIAL data requires encryption at rest and RBAC."""
        rules = svc.get_handling_rules_for_level(ClassificationLevel.CONFIDENTIAL)
        assert rules.storage.encryption_at_rest is True
        assert rules.storage.encryption_algorithm == "AES-256"
        assert rules.access_control.rbac_required is True
        assert rules.access_control.access_logging == "full"

    def test_restricted_maximum_controls(self, svc: DataClassificationService):
        """RESTRICTED data requires all maximum security controls."""
        rules = svc.get_handling_rules_for_level(ClassificationLevel.RESTRICTED)
        assert rules.storage.encryption_at_rest is True
        assert rules.storage.encryption_algorithm == "AES-256-GCM"
        assert rules.storage.isolated_storage is True
        assert rules.access_control.mfa_required is True
        assert rules.access_control.dua_required is True
        assert rules.access_control.need_to_know is True
        assert rules.transmission.vpn_required is True
        assert rules.transmission.minimum_tls_version == "1.3"
        assert rules.retention.disposal_method == "crypto_shred"
        assert rules.incident_response.hhs_notification is True
        assert rules.incident_response.patient_notification is True
        assert rules.sharing.external_sharing == "prohibited"

    def test_filter_rules_by_level(self, svc: DataClassificationService):
        """Filtering handling rules by level returns exactly one."""
        rules = svc.get_handling_rules(level=ClassificationLevel.CONFIDENTIAL)
        assert len(rules) == 1
        assert rules[0].classification_level == ClassificationLevel.CONFIDENTIAL

    def test_incident_response_escalation(self, svc: DataClassificationService):
        """Higher classifications have faster incident response timelines."""
        conf_rules = svc.get_handling_rules_for_level(ClassificationLevel.CONFIDENTIAL)
        rest_rules = svc.get_handling_rules_for_level(ClassificationLevel.RESTRICTED)
        assert conf_rules.incident_response.notification_timeline_hours == 72
        assert rest_rules.incident_response.notification_timeline_hours == 24

    def test_sharing_restrictions_escalate(self, svc: DataClassificationService):
        """Sharing restrictions escalate with classification level."""
        pub = svc.get_handling_rules_for_level(ClassificationLevel.PUBLIC)
        rest = svc.get_handling_rules_for_level(ClassificationLevel.RESTRICTED)
        assert pub.sharing.external_sharing == "unrestricted"
        assert rest.sharing.external_sharing == "prohibited"


# ===================================================================
# Pre-populated Data Assets
# ===================================================================


class TestPrePopulatedAssets:
    """Tests for the 30+ pre-populated data assets."""

    def test_minimum_30_assets(self, svc: DataClassificationService):
        """At least 30 assets are pre-populated."""
        assets = svc.list_assets()
        assert len(assets) >= 30

    def test_clinical_facts_is_restricted(self, svc: DataClassificationService):
        """clinical_facts is classified as RESTRICTED."""
        asset = svc.get_asset_by_name("clinical_facts")
        assert asset is not None
        assert asset.classification_level == ClassificationLevel.RESTRICTED
        assert asset.encryption_required is True

    def test_kg_nodes_is_restricted(self, svc: DataClassificationService):
        """kg_nodes is classified as RESTRICTED."""
        asset = svc.get_asset_by_name("kg_nodes")
        assert asset is not None
        assert asset.classification_level == ClassificationLevel.RESTRICTED

    def test_screening_results_is_restricted(self, svc: DataClassificationService):
        """screening_results is classified as RESTRICTED."""
        asset = svc.get_asset_by_name("screening_results")
        assert asset is not None
        assert asset.classification_level == ClassificationLevel.RESTRICTED

    def test_audit_logs_system_is_confidential(self, svc: DataClassificationService):
        """System audit logs are classified as CONFIDENTIAL."""
        asset = svc.get_asset_by_name("audit_logs_system")
        assert asset is not None
        assert asset.classification_level == ClassificationLevel.CONFIDENTIAL

    def test_trial_definitions_is_confidential(self, svc: DataClassificationService):
        """Trial definitions are classified as CONFIDENTIAL."""
        asset = svc.get_asset_by_name("trial_definitions")
        assert asset is not None
        assert asset.classification_level == ClassificationLevel.CONFIDENTIAL

    def test_api_metrics_is_internal(self, svc: DataClassificationService):
        """API metrics are classified as INTERNAL."""
        asset = svc.get_asset_by_name("api_metrics")
        assert asset is not None
        assert asset.classification_level == ClassificationLevel.INTERNAL

    def test_omop_vocabulary_is_internal(self, svc: DataClassificationService):
        """OMOP vocabulary is classified as INTERNAL."""
        asset = svc.get_asset_by_name("omop_vocabulary")
        assert asset is not None
        assert asset.classification_level == ClassificationLevel.INTERNAL

    def test_landing_page_is_public(self, svc: DataClassificationService):
        """Landing page content is classified as PUBLIC."""
        asset = svc.get_asset_by_name("landing_page_content")
        assert asset is not None
        assert asset.classification_level == ClassificationLevel.PUBLIC
        assert asset.encryption_required is False

    def test_all_restricted_have_encryption(self, svc: DataClassificationService):
        """All RESTRICTED assets require encryption."""
        restricted = svc.list_assets(classification_level=ClassificationLevel.RESTRICTED)
        for asset in restricted:
            assert asset.encryption_required is True, (
                f"RESTRICTED asset {asset.name} missing encryption_required"
            )

    def test_assets_have_handling_rules(self, svc: DataClassificationService):
        """All pre-populated assets have handling rules attached."""
        for asset in svc.list_assets():
            assert asset.handling_rules is not None, (
                f"Asset {asset.name} missing handling_rules"
            )
            assert asset.handling_rules.classification_level == asset.classification_level


# ===================================================================
# Asset Registration and CRUD
# ===================================================================


class TestAssetCRUD:
    """Tests for asset registration, retrieval, and update."""

    def test_register_asset(self, svc: DataClassificationService):
        """Registering an asset returns it with an ID and timestamps."""
        create = _make_asset_create(name="new_test_asset")
        asset = svc.register_asset(create)
        assert asset.asset_id.startswith("asset-")
        assert asset.name == "new_test_asset"
        assert asset.classification_level == ClassificationLevel.INTERNAL
        assert asset.created_at is not None
        assert asset.updated_at is not None

    def test_get_asset_by_id(self, svc: DataClassificationService):
        """Get asset by ID returns the correct asset."""
        create = _make_asset_create(name="lookup_test")
        registered = svc.register_asset(create)
        found = svc.get_asset(registered.asset_id)
        assert found is not None
        assert found.name == "lookup_test"

    def test_get_asset_not_found(self, svc: DataClassificationService):
        """Getting a non-existent asset returns None."""
        assert svc.get_asset("nonexistent-id") is None

    def test_get_asset_by_name(self, svc: DataClassificationService):
        """Get asset by name returns the correct asset."""
        create = _make_asset_create(name="named_asset")
        svc.register_asset(create)
        found = svc.get_asset_by_name("named_asset")
        assert found is not None
        assert found.name == "named_asset"

    def test_update_asset_classification(self, svc: DataClassificationService):
        """Updating classification level also updates handling rules."""
        create = _make_asset_create(
            name="upgradable",
            classification_level=ClassificationLevel.INTERNAL,
        )
        asset = svc.register_asset(create)
        updated = svc.update_asset(
            asset.asset_id,
            DataAssetUpdate(classification_level=ClassificationLevel.CONFIDENTIAL),
        )
        assert updated is not None
        assert updated.classification_level == ClassificationLevel.CONFIDENTIAL
        assert updated.handling_rules is not None
        assert updated.handling_rules.classification_level == ClassificationLevel.CONFIDENTIAL

    def test_update_asset_partial(self, svc: DataClassificationService):
        """Partial update only changes specified fields."""
        create = _make_asset_create(name="partial_update_test", data_owner="Original Owner")
        asset = svc.register_asset(create)
        updated = svc.update_asset(
            asset.asset_id,
            DataAssetUpdate(data_owner="New Owner"),
        )
        assert updated is not None
        assert updated.data_owner == "New Owner"
        assert updated.name == "partial_update_test"  # unchanged

    def test_update_nonexistent_asset(self, svc: DataClassificationService):
        """Updating a non-existent asset returns None."""
        result = svc.update_asset("fake-id", DataAssetUpdate(name="x"))
        assert result is None

    def test_filter_assets_by_level(self, svc: DataClassificationService):
        """Filtering by classification level returns only matching assets."""
        public_assets = svc.list_assets(classification_level=ClassificationLevel.PUBLIC)
        for asset in public_assets:
            assert asset.classification_level == ClassificationLevel.PUBLIC

    def test_filter_assets_by_tag(self, svc: DataClassificationService):
        """Filtering by tag returns only matching assets."""
        phi_assets = svc.list_assets(tag="phi")
        for asset in phi_assets:
            assert "phi" in asset.tags

    def test_filter_assets_by_owner(self, svc: DataClassificationService):
        """Filtering by owner returns only matching assets."""
        cto_assets = svc.list_assets(owner="CTO")
        for asset in cto_assets:
            assert asset.data_owner == "CTO"

    def test_new_asset_has_review_dates(self, svc: DataClassificationService):
        """Newly registered assets have review dates set."""
        create = _make_asset_create(name="review_dates_test", review_frequency_days=90)
        asset = svc.register_asset(create)
        assert asset.last_reviewed is not None
        assert asset.next_review_due is not None
        assert asset.is_overdue is False


# ===================================================================
# Overdue Reviews
# ===================================================================


class TestOverdueReviews:
    """Tests for overdue review detection."""

    def test_no_overdue_initially(self, svc: DataClassificationService):
        """Pre-populated assets start with no overdue reviews."""
        overdue = svc.get_overdue_reviews()
        assert len(overdue) == 0

    def test_detect_overdue_asset(self, svc: DataClassificationService):
        """An asset with review date in the past is flagged overdue."""
        create = _make_asset_create(name="overdue_test", review_frequency_days=1)
        asset = svc.register_asset(create)

        # Manually backdate the review
        asset_data = asset.model_dump()
        past = datetime.now(timezone.utc) - timedelta(days=10)
        asset_data["last_reviewed"] = past
        asset_data["next_review_due"] = past + timedelta(days=1)
        from app.schemas.data_classification import DataAssetResponse
        svc._assets[asset.asset_id] = DataAssetResponse(**asset_data)

        overdue = svc.get_overdue_reviews()
        assert any(a.asset_id == asset.asset_id for a in overdue)

    def test_mark_reviewed_clears_overdue(self, svc: DataClassificationService):
        """Marking an asset as reviewed resets the review clock."""
        create = _make_asset_create(name="mark_reviewed_test", review_frequency_days=1)
        asset = svc.register_asset(create)

        # Backdate to make overdue
        asset_data = asset.model_dump()
        past = datetime.now(timezone.utc) - timedelta(days=10)
        asset_data["last_reviewed"] = past
        asset_data["next_review_due"] = past + timedelta(days=1)
        from app.schemas.data_classification import DataAssetResponse
        svc._assets[asset.asset_id] = DataAssetResponse(**asset_data)

        # Verify overdue
        overdue = svc.get_overdue_reviews()
        assert any(a.asset_id == asset.asset_id for a in overdue)

        # Mark reviewed
        updated = svc.mark_reviewed(asset.asset_id, reviewer="Test Reviewer")
        assert updated is not None
        assert updated.is_overdue is False
        assert updated.last_reviewed is not None


# ===================================================================
# Reclassification Workflow
# ===================================================================


class TestReclassification:
    """Tests for the reclassification request workflow."""

    def _get_first_internal_asset(self, svc):
        """Helper to get an INTERNAL asset for reclassification tests."""
        assets = svc.list_assets(classification_level=ClassificationLevel.INTERNAL)
        assert len(assets) > 0
        return assets[0]

    def test_request_reclassification(self, svc: DataClassificationService):
        """Submit a reclassification request and get pending response."""
        asset = self._get_first_internal_asset(svc)
        req = ReclassificationRequest(
            asset_id=asset.asset_id,
            current_level=ClassificationLevel.INTERNAL,
            requested_level=ClassificationLevel.CONFIDENTIAL,
            justification="Data now contains trial protocol details requiring higher protection.",
            requested_by="Data Steward",
        )
        resp = svc.request_reclassification(req)
        assert resp.request_id.startswith("reclass-")
        assert resp.status == ReclassificationStatus.PENDING
        assert resp.asset_name == asset.name

    def test_approve_reclassification(self, svc: DataClassificationService):
        """Approving reclassification updates the asset classification."""
        asset = self._get_first_internal_asset(svc)
        req = ReclassificationRequest(
            asset_id=asset.asset_id,
            current_level=ClassificationLevel.INTERNAL,
            requested_level=ClassificationLevel.CONFIDENTIAL,
            justification="Upgrading due to sensitive content identified in review.",
            requested_by="Data Steward",
        )
        resp = svc.request_reclassification(req)

        reviewed = svc.review_reclassification(
            resp.request_id,
            approve=True,
            reviewer="Data Owner",
            notes="Approved after review of data content.",
        )
        assert reviewed is not None
        assert reviewed.status == ReclassificationStatus.APPROVED

        # Verify asset was updated
        updated_asset = svc.get_asset(asset.asset_id)
        assert updated_asset is not None
        assert updated_asset.classification_level == ClassificationLevel.CONFIDENTIAL

    def test_reject_reclassification(self, svc: DataClassificationService):
        """Rejecting reclassification does not change the asset."""
        asset = self._get_first_internal_asset(svc)
        req = ReclassificationRequest(
            asset_id=asset.asset_id,
            current_level=ClassificationLevel.INTERNAL,
            requested_level=ClassificationLevel.PUBLIC,
            justification="Data seems low risk and could be public.",
            requested_by="Junior Analyst",
        )
        resp = svc.request_reclassification(req)

        reviewed = svc.review_reclassification(
            resp.request_id,
            approve=False,
            reviewer="Data Owner",
            notes="Data contains internal operational metrics, not suitable for public.",
        )
        assert reviewed is not None
        assert reviewed.status == ReclassificationStatus.REJECTED

        # Asset should still be INTERNAL
        unchanged = svc.get_asset(asset.asset_id)
        assert unchanged is not None
        assert unchanged.classification_level == ClassificationLevel.INTERNAL

    def test_reclassify_same_level_raises(self, svc: DataClassificationService):
        """Requesting reclassification to same level raises ValueError."""
        asset = self._get_first_internal_asset(svc)
        req = ReclassificationRequest(
            asset_id=asset.asset_id,
            current_level=ClassificationLevel.INTERNAL,
            requested_level=ClassificationLevel.INTERNAL,
            justification="No change requested.",
            requested_by="Data Steward",
        )
        with pytest.raises(ValueError, match="same as current"):
            svc.request_reclassification(req)

    def test_reclassify_level_mismatch_raises(self, svc: DataClassificationService):
        """Mismatched current_level in request raises ValueError."""
        asset = self._get_first_internal_asset(svc)
        req = ReclassificationRequest(
            asset_id=asset.asset_id,
            current_level=ClassificationLevel.RESTRICTED,  # wrong
            requested_level=ClassificationLevel.PUBLIC,
            justification="Testing mismatch.",
            requested_by="Data Steward",
        )
        with pytest.raises(ValueError, match="mismatch"):
            svc.request_reclassification(req)

    def test_reclassify_nonexistent_asset_raises(self, svc: DataClassificationService):
        """Reclassification request for non-existent asset raises ValueError."""
        req = ReclassificationRequest(
            asset_id="nonexistent-asset-id",
            current_level=ClassificationLevel.INTERNAL,
            requested_level=ClassificationLevel.PUBLIC,
            justification="Testing missing asset.",
            requested_by="Data Steward",
        )
        with pytest.raises(ValueError, match="not found"):
            svc.request_reclassification(req)

    def test_list_reclassification_requests(self, svc: DataClassificationService):
        """List reclassification requests with status filter."""
        asset = self._get_first_internal_asset(svc)
        req = ReclassificationRequest(
            asset_id=asset.asset_id,
            current_level=ClassificationLevel.INTERNAL,
            requested_level=ClassificationLevel.CONFIDENTIAL,
            justification="Test listing.",
            requested_by="Steward",
        )
        svc.request_reclassification(req)

        pending = svc.list_reclassification_requests(
            status=ReclassificationStatus.PENDING
        )
        assert len(pending) >= 1

        approved = svc.list_reclassification_requests(
            status=ReclassificationStatus.APPROVED
        )
        assert len(approved) == 0

    def test_double_review_raises(self, svc: DataClassificationService):
        """Reviewing an already-reviewed request raises ValueError."""
        asset = self._get_first_internal_asset(svc)
        req = ReclassificationRequest(
            asset_id=asset.asset_id,
            current_level=ClassificationLevel.INTERNAL,
            requested_level=ClassificationLevel.CONFIDENTIAL,
            justification="Test double review.",
            requested_by="Steward",
        )
        resp = svc.request_reclassification(req)
        svc.review_reclassification(resp.request_id, approve=True, reviewer="Owner")

        with pytest.raises(ValueError, match="not pending"):
            svc.review_reclassification(resp.request_id, approve=False, reviewer="Owner")


# ===================================================================
# Summary Statistics
# ===================================================================


class TestSummaryStatistics:
    """Tests for classification summary stats."""

    def test_summary_total_assets(self, svc: DataClassificationService):
        """Summary reports correct total asset count."""
        summary = svc.get_summary()
        assets = svc.list_assets()
        assert summary.total_assets == len(assets)

    def test_summary_by_level(self, svc: DataClassificationService):
        """Summary correctly breaks down assets by level."""
        summary = svc.get_summary()
        for level in ClassificationLevel:
            expected = len(svc.list_assets(classification_level=level))
            assert summary.by_level[level.value] == expected

    def test_summary_encryption_coverage(self, svc: DataClassificationService):
        """Summary reports encryption coverage percentage."""
        summary = svc.get_summary()
        assert 0 <= summary.encryption_coverage <= 100

    def test_summary_dua_requirements(self, svc: DataClassificationService):
        """Summary counts assets requiring DUA."""
        summary = svc.get_summary()
        # RESTRICTED assets require DUA
        restricted_count = len(svc.list_assets(classification_level=ClassificationLevel.RESTRICTED))
        assert summary.assets_with_dua_requirement == restricted_count


# ===================================================================
# Data Governance Roles
# ===================================================================


class TestDataRoles:
    """Tests for data governance role definitions."""

    def test_four_roles_defined(self, svc: DataClassificationService):
        """There are 4 governance roles defined."""
        roles = svc.get_data_roles()
        assert len(roles) == 4

    def test_privacy_officer_for_restricted(self, svc: DataClassificationService):
        """Privacy Officer role is required for RESTRICTED data."""
        roles = svc.get_data_roles()
        po = [r for r in roles if r.role_name == "Privacy Officer"][0]
        assert ClassificationLevel.RESTRICTED in po.required_for_levels


# ===================================================================
# Audit Trail
# ===================================================================


class TestAuditTrail:
    """Tests for audit trail recording."""

    def test_registration_creates_audit_entry(self, svc: DataClassificationService):
        """Registering an asset creates an audit trail entry."""
        initial_count = len(svc.get_audit_trail())
        svc.register_asset(_make_asset_create(name="audit_test"))
        trail = svc.get_audit_trail()
        assert len(trail) > initial_count
        last = trail[-1]
        assert last["action"] == "asset_registered"
        assert last["asset_name"] == "audit_test"

    def test_reclassification_creates_audit_entries(self, svc: DataClassificationService):
        """Reclassification creates audit entries for request and review."""
        asset = svc.list_assets(classification_level=ClassificationLevel.INTERNAL)[0]
        req = ReclassificationRequest(
            asset_id=asset.asset_id,
            current_level=ClassificationLevel.INTERNAL,
            requested_level=ClassificationLevel.CONFIDENTIAL,
            justification="Audit trail test.",
            requested_by="Tester",
        )
        resp = svc.request_reclassification(req)
        svc.review_reclassification(resp.request_id, approve=True, reviewer="Reviewer")

        trail = svc.get_audit_trail()
        actions = [e["action"] for e in trail]
        assert "reclassification_requested" in actions
        assert "reclassification_reviewed" in actions


# ===================================================================
# API Endpoint Tests
# ===================================================================


class TestAPIEndpoints:
    """Tests for API endpoints via TestClient."""

    def test_get_levels(self, client: TestClient):
        """GET /governance/classification/levels returns 4 levels."""
        resp = client.get("/governance/classification/levels")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 4

    def test_get_handling_rules(self, client: TestClient):
        """GET /governance/classification/handling-rules returns rules."""
        resp = client.get("/governance/classification/handling-rules")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 4

    def test_get_handling_rules_filtered(self, client: TestClient):
        """GET /governance/classification/handling-rules?level=RESTRICTED returns 1."""
        resp = client.get("/governance/classification/handling-rules?level=RESTRICTED")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["classification_level"] == "RESTRICTED"

    def test_list_assets(self, client: TestClient):
        """GET /governance/classification/assets returns 30+ assets."""
        resp = client.get("/governance/classification/assets")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 30

    def test_list_assets_filtered(self, client: TestClient):
        """GET /governance/classification/assets?classification_level=PUBLIC."""
        resp = client.get("/governance/classification/assets?classification_level=PUBLIC")
        assert resp.status_code == 200
        data = resp.json()
        for asset in data:
            assert asset["classification_level"] == "PUBLIC"

    def test_register_asset_api(self, client: TestClient):
        """POST /governance/classification/assets creates a new asset."""
        resp = client.post(
            "/governance/classification/assets",
            json={
                "name": "api_test_asset",
                "description": "Created via API test.",
                "classification_level": "CONFIDENTIAL",
                "data_owner": "API Tester",
                "storage_location": "test_db",
                "review_frequency_days": 180,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "api_test_asset"
        assert data["classification_level"] == "CONFIDENTIAL"

    def test_get_asset_detail(self, client: TestClient):
        """GET /governance/classification/assets/{id} returns asset detail."""
        # First create an asset
        create_resp = client.post(
            "/governance/classification/assets",
            json={
                "name": "detail_test",
                "description": "Detail test asset.",
                "classification_level": "INTERNAL",
                "data_owner": "Tester",
                "storage_location": "test_location",
            },
        )
        asset_id = create_resp.json()["asset_id"]

        resp = client.get(f"/governance/classification/assets/{asset_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "detail_test"

    def test_get_asset_not_found_api(self, client: TestClient):
        """GET /governance/classification/assets/{id} returns 404 for unknown."""
        resp = client.get("/governance/classification/assets/nonexistent")
        assert resp.status_code == 404

    def test_update_asset_api(self, client: TestClient):
        """PUT /governance/classification/assets/{id} updates asset."""
        create_resp = client.post(
            "/governance/classification/assets",
            json={
                "name": "update_api_test",
                "description": "Will be updated.",
                "classification_level": "INTERNAL",
                "data_owner": "Tester",
                "storage_location": "test_location",
            },
        )
        asset_id = create_resp.json()["asset_id"]

        resp = client.put(
            f"/governance/classification/assets/{asset_id}",
            json={"data_owner": "Updated Owner"},
        )
        assert resp.status_code == 200
        assert resp.json()["data_owner"] == "Updated Owner"

    def test_overdue_reviews_api(self, client: TestClient):
        """GET /governance/classification/overdue-reviews returns list."""
        resp = client.get("/governance/classification/overdue-reviews")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_reclassify_api(self, client: TestClient):
        """POST /governance/classification/reclassify creates request."""
        # Get an asset to reclassify
        assets_resp = client.get("/governance/classification/assets?classification_level=INTERNAL")
        assets = assets_resp.json()
        assert len(assets) > 0
        asset = assets[0]

        resp = client.post(
            "/governance/classification/reclassify",
            json={
                "asset_id": asset["asset_id"],
                "current_level": "INTERNAL",
                "requested_level": "CONFIDENTIAL",
                "justification": "API test reclassification request.",
                "requested_by": "API Tester",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "PENDING"

    def test_reclassify_api_bad_request(self, client: TestClient):
        """POST /governance/classification/reclassify returns 400 for bad data."""
        resp = client.post(
            "/governance/classification/reclassify",
            json={
                "asset_id": "nonexistent",
                "current_level": "INTERNAL",
                "requested_level": "PUBLIC",
                "justification": "This should fail because asset does not exist.",
                "requested_by": "Tester",
            },
        )
        assert resp.status_code == 400

    def test_summary_api(self, client: TestClient):
        """GET /governance/classification/summary returns stats."""
        resp = client.get("/governance/classification/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_assets"] >= 30
        assert "by_level" in data
        assert "RESTRICTED" in data["by_level"]
        assert "encryption_coverage" in data
