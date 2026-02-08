"""Tests for Dir-CI-3.3: Clinical Trial Value Set Management.

Tests cover:
- Value set creation and retrieval
- Code membership checking (exact and hierarchical)
- Value set expansion
- ICD-10 hierarchical prefix matching
- Pre-loaded clinical value sets
- Value set updates (add/remove codes)
- API endpoints for clinical value sets
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services.value_set_service import (
    ClinicalValueSetService,
    reset_clinical_value_set_service,
)
from app.api.valuesets import clinical_router


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def service():
    """Create a fresh ClinicalValueSetService for each test."""
    return ClinicalValueSetService()


@pytest.fixture
def empty_service():
    """Create a ClinicalValueSetService without pre-loaded data."""
    svc = ClinicalValueSetService.__new__(ClinicalValueSetService)
    svc._value_sets = {}
    return svc


@pytest.fixture
def client():
    """Create a test client with the clinical value sets router."""
    reset_clinical_value_set_service()
    app = FastAPI()
    app.include_router(clinical_router)
    return TestClient(app, raise_server_exceptions=False)


# =============================================================================
# Test: Value Set Creation
# =============================================================================


class TestValueSetCreation:
    """Test creating value sets."""

    def test_create_basic_value_set(self, empty_service):
        vs = empty_service.create_value_set(
            name="test_vs",
            code_system="ICD10CM",
            codes=[("E11", "Type 2 diabetes mellitus")],
            description="Test value set",
        )
        assert vs.name == "test_vs"
        assert len(vs.codes) == 1
        assert vs.codes[0].code == "E11"

    def test_create_value_set_with_oid(self, empty_service):
        vs = empty_service.create_value_set(
            name="test_vs",
            oid="2.16.840.1.113883.3.464.1003.103.12.1001",
            code_system="ICD10CM",
            codes=[("E11", "Type 2 DM")],
        )
        assert vs.oid == "2.16.840.1.113883.3.464.1003.103.12.1001"

    def test_create_value_set_with_version(self, empty_service):
        vs = empty_service.create_value_set(
            name="test_vs",
            code_system="ICD10CM",
            codes=[],
            version="2.0.0",
        )
        assert vs.version == "2.0.0"

    def test_create_duplicate_raises_error(self, empty_service):
        empty_service.create_value_set(
            name="test_vs", code_system="ICD10CM", codes=[]
        )
        with pytest.raises(ValueError, match="already exists"):
            empty_service.create_value_set(
                name="test_vs", code_system="ICD10CM", codes=[]
            )

    def test_create_value_set_with_domain(self, empty_service):
        vs = empty_service.create_value_set(
            name="test_vs",
            code_system="ICD10CM",
            codes=[],
            domain="Endocrinology",
        )
        assert vs.domain == "Endocrinology"

    def test_create_value_set_sets_timestamps(self, empty_service):
        vs = empty_service.create_value_set(
            name="test_vs", code_system="ICD10CM", codes=[]
        )
        assert vs.created_at is not None
        assert vs.updated_at is not None


# =============================================================================
# Test: Code Membership Checking
# =============================================================================


class TestCodeMembership:
    """Test code membership checking, including hierarchical matches."""

    def test_exact_match(self, empty_service):
        empty_service.create_value_set(
            name="dm",
            code_system="ICD10CM",
            codes=[("E11.9", "Type 2 DM without complications")],
        )
        assert empty_service.check_membership("E11.9", "ICD10CM", "dm") is True

    def test_exact_match_case_insensitive(self, empty_service):
        empty_service.create_value_set(
            name="dm",
            code_system="ICD10CM",
            codes=[("E11.9", "Type 2 DM")],
        )
        assert empty_service.check_membership("e11.9", "ICD10CM", "dm") is True

    def test_no_match(self, empty_service):
        empty_service.create_value_set(
            name="dm",
            code_system="ICD10CM",
            codes=[("E11.9", "Type 2 DM")],
        )
        assert empty_service.check_membership("J45.0", "ICD10CM", "dm") is False

    def test_nonexistent_value_set(self, empty_service):
        assert (
            empty_service.check_membership("E11.9", "ICD10CM", "nonexistent")
            is False
        )

    def test_hierarchical_icd10_parent_matches_child(self, empty_service):
        """ICD-10 prefix matching: E11 in VS matches E11.9 input."""
        empty_service.create_value_set(
            name="dm",
            code_system="ICD10CM",
            codes=[("E11", "Type 2 diabetes mellitus")],
        )
        assert empty_service.check_membership("E11.9", "ICD10CM", "dm") is True

    def test_hierarchical_icd10_deep_child(self, empty_service):
        """E11 matches E11.3211 (deep hierarchy)."""
        empty_service.create_value_set(
            name="dm",
            code_system="ICD10CM",
            codes=[("E11", "Type 2 diabetes mellitus")],
        )
        assert empty_service.check_membership("E11.3211", "ICD10CM", "dm") is True

    def test_hierarchical_icd10_c44_matches_c44_92(self, empty_service):
        """C44 matches C44.92 (CSCC use case)."""
        empty_service.create_value_set(
            name="cscc",
            code_system="ICD10CM",
            codes=[("C44", "Malignant neoplasm of skin")],
        )
        assert empty_service.check_membership("C44.92", "ICD10CM", "cscc") is True

    def test_hierarchical_no_false_positive(self, empty_service):
        """E11 should NOT match E13 (different category)."""
        empty_service.create_value_set(
            name="dm",
            code_system="ICD10CM",
            codes=[("E11", "Type 2 diabetes mellitus")],
        )
        assert empty_service.check_membership("E13", "ICD10CM", "dm") is False

    def test_snomed_exact_match_only(self, empty_service):
        """SNOMED codes use exact match, not hierarchical."""
        empty_service.create_value_set(
            name="dm",
            code_system="SNOMED",
            codes=[("73211009", "Diabetes mellitus")],
        )
        assert empty_service.check_membership("73211009", "SNOMED", "dm") is True
        assert empty_service.check_membership("732110090", "SNOMED", "dm") is False

    def test_cross_system_no_match(self, empty_service):
        """SNOMED code should not match ICD10CM entry."""
        empty_service.create_value_set(
            name="dm",
            code_system="ICD10CM",
            codes=[("E11", "Type 2 diabetes mellitus")],
        )
        assert empty_service.check_membership("E11", "SNOMED", "dm") is False

    def test_membership_detailed_returns_matched_code(self, empty_service):
        """check_membership_detailed returns the parent code for hierarchical match."""
        empty_service.create_value_set(
            name="dm",
            code_system="ICD10CM",
            codes=[("E11", "Type 2 diabetes mellitus")],
        )
        is_member, matched = empty_service.check_membership_detailed(
            "E11.65", "ICD10CM", "dm"
        )
        assert is_member is True
        assert matched == "E11"


# =============================================================================
# Test: Value Set Expansion
# =============================================================================


class TestValueSetExpansion:
    """Test expanding value sets to their codes."""

    def test_expand_returns_all_codes(self, empty_service):
        empty_service.create_value_set(
            name="dm",
            code_system="ICD10CM",
            codes=[
                ("E11", "Type 2 diabetes mellitus"),
                ("E11.9", "Type 2 DM without complications"),
            ],
        )
        codes = empty_service.expand_value_set("dm")
        assert len(codes) == 2

    def test_expand_nonexistent_returns_empty(self, empty_service):
        codes = empty_service.expand_value_set("nonexistent")
        assert codes == []

    def test_expand_empty_value_set(self, empty_service):
        empty_service.create_value_set(
            name="empty", code_system="ICD10CM", codes=[]
        )
        codes = empty_service.expand_value_set("empty")
        assert codes == []


# =============================================================================
# Test: Pre-loaded Clinical Value Sets
# =============================================================================


class TestPreloadedValueSets:
    """Test that pre-loaded clinical value sets are correct."""

    def test_diabetes_value_set_exists(self, service):
        vs = service.get_value_set("diabetes_mellitus")
        assert vs is not None
        assert vs.name == "diabetes_mellitus"
        assert vs.domain == "Endocrinology"

    def test_diabetes_contains_icd10_codes(self, service):
        vs = service.get_value_set("diabetes_mellitus")
        icd_codes = [c.code for c in vs.codes if c.code_system == "ICD10CM"]
        assert "E10" in icd_codes
        assert "E11" in icd_codes
        assert "E13" in icd_codes

    def test_diabetes_contains_snomed_codes(self, service):
        vs = service.get_value_set("diabetes_mellitus")
        snomed_codes = [c.code for c in vs.codes if c.code_system == "SNOMED"]
        assert "73211009" in snomed_codes
        assert "44054006" in snomed_codes

    def test_dme_value_set_exists(self, service):
        vs = service.get_value_set("diabetic_macular_edema")
        assert vs is not None
        assert vs.domain == "Ophthalmology"
        icd_codes = [c.code for c in vs.codes if c.code_system == "ICD10CM"]
        assert "H35.81" in icd_codes
        assert "E11.311" in icd_codes

    def test_atopic_dermatitis_value_set_exists(self, service):
        vs = service.get_value_set("atopic_dermatitis")
        assert vs is not None
        assert vs.domain == "Dermatology"
        icd_codes = [c.code for c in vs.codes if c.code_system == "ICD10CM"]
        assert "L20" in icd_codes
        assert "L20.9" in icd_codes

    def test_cscc_value_set_exists(self, service):
        vs = service.get_value_set("cutaneous_scc")
        assert vs is not None
        assert vs.domain == "Oncology"
        icd_codes = [c.code for c in vs.codes if c.code_system == "ICD10CM"]
        assert "C44.9" in icd_codes
        assert "C44.92" in icd_codes

    def test_hba1c_value_set_exists(self, service):
        vs = service.get_value_set("hba1c")
        assert vs is not None
        assert vs.domain == "Laboratory"
        loinc_codes = [c.code for c in vs.codes if c.code_system == "LOINC"]
        assert "4548-4" in loinc_codes
        assert "17856-6" in loinc_codes

    def test_list_all_preloaded(self, service):
        all_vs = service.list_value_sets()
        names = [vs.name for vs in all_vs]
        assert "diabetes_mellitus" in names
        assert "diabetic_macular_edema" in names
        assert "atopic_dermatitis" in names
        assert "cutaneous_scc" in names
        assert "hba1c" in names

    def test_list_by_domain(self, service):
        onc = service.list_value_sets(domain="Oncology")
        assert len(onc) >= 1
        assert all(vs.domain == "Oncology" for vs in onc)

    def test_diabetes_hierarchical_membership(self, service):
        """E11.65 should be a member of diabetes_mellitus via E11 parent."""
        assert service.check_membership("E11.65", "ICD10CM", "diabetes_mellitus")

    def test_cscc_hierarchical_membership(self, service):
        """C44.12 should match via C44.1 parent in CSCC value set."""
        assert service.check_membership("C44.12", "ICD10CM", "cutaneous_scc")


# =============================================================================
# Test: Value Set Update
# =============================================================================


class TestValueSetUpdate:
    """Test adding/removing codes from value sets."""

    def test_add_codes(self, empty_service):
        empty_service.create_value_set(
            name="test_vs",
            code_system="ICD10CM",
            codes=[("E11", "Type 2 DM")],
        )
        result = empty_service.update_value_set(
            name="test_vs",
            codes_to_add=[("E13", "ICD10CM", "Other specified DM")],
        )
        assert result is not None
        assert len(result.codes) == 2

    def test_remove_codes(self, empty_service):
        empty_service.create_value_set(
            name="test_vs",
            code_system="ICD10CM",
            codes=[("E11", "Type 2 DM"), ("E13", "Other DM")],
        )
        result = empty_service.update_value_set(
            name="test_vs",
            codes_to_remove=[("E13", "ICD10CM")],
        )
        assert result is not None
        assert len(result.codes) == 1
        assert result.codes[0].code == "E11"

    def test_update_nonexistent_returns_none(self, empty_service):
        result = empty_service.update_value_set(
            name="nonexistent",
            codes_to_add=[("E11", "ICD10CM", "DM")],
        )
        assert result is None

    def test_update_version(self, empty_service):
        empty_service.create_value_set(
            name="test_vs",
            code_system="ICD10CM",
            codes=[("E11", "Type 2 DM")],
            version="1.0.0",
        )
        result = empty_service.update_value_set(
            name="test_vs",
            codes_to_add=[("E13", "ICD10CM", "Other DM")],
            new_version="1.1.0",
        )
        assert result.version == "1.1.0"

    def test_add_duplicate_code_is_idempotent(self, empty_service):
        empty_service.create_value_set(
            name="test_vs",
            code_system="ICD10CM",
            codes=[("E11", "Type 2 DM")],
        )
        result = empty_service.update_value_set(
            name="test_vs",
            codes_to_add=[("E11", "ICD10CM", "Type 2 DM duplicate")],
        )
        # Should not add duplicate
        assert len(result.codes) == 1


# =============================================================================
# Test: Bulk Membership
# =============================================================================


class TestBulkMembership:
    """Test check_any_membership for screening pipelines."""

    def test_any_membership_with_match(self, service):
        """One of the codes should match diabetes value set."""
        codes = [("J45.0", "ICD10CM"), ("E11.9", "ICD10CM")]
        matched, matched_code = service.check_any_membership(
            codes, "diabetes_mellitus"
        )
        assert matched is True
        assert matched_code is not None

    def test_any_membership_no_match(self, service):
        codes = [("J45.0", "ICD10CM"), ("Z00.0", "ICD10CM")]
        matched, matched_code = service.check_any_membership(
            codes, "diabetes_mellitus"
        )
        assert matched is False
        assert matched_code is None

    def test_any_membership_nonexistent_vs(self, service):
        codes = [("E11", "ICD10CM")]
        matched, matched_code = service.check_any_membership(
            codes, "nonexistent"
        )
        assert matched is False


# =============================================================================
# Test: API Endpoints
# =============================================================================


class TestClinicalValueSetAPI:
    """Test the clinical value set REST endpoints."""

    def test_list_endpoint(self, client):
        response = client.get("/clinical-valuesets")
        assert response.status_code == 200
        data = response.json()
        assert "value_sets" in data
        assert "total" in data
        assert data["total"] >= 5  # Pre-loaded sets

    def test_list_with_domain_filter(self, client):
        response = client.get(
            "/clinical-valuesets", params={"domain": "Oncology"}
        )
        assert response.status_code == 200
        data = response.json()
        for vs in data["value_sets"]:
            assert vs["domain"] == "Oncology"

    def test_get_specific_value_set(self, client):
        response = client.get("/clinical-valuesets/diabetes_mellitus")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "diabetes_mellitus"
        assert len(data["codes"]) > 0

    def test_get_not_found(self, client):
        response = client.get("/clinical-valuesets/nonexistent")
        assert response.status_code == 404

    def test_expand_endpoint(self, client):
        response = client.get(
            "/clinical-valuesets/diabetes_mellitus/expand"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["value_set_name"] == "diabetes_mellitus"
        assert data["total_codes"] > 0
        assert len(data["codes"]) == data["total_codes"]

    def test_expand_not_found(self, client):
        response = client.get("/clinical-valuesets/nonexistent/expand")
        assert response.status_code == 404

    def test_check_membership_positive(self, client):
        response = client.get(
            "/clinical-valuesets/diabetes_mellitus/check/ICD10CM/E11.9"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_member"] is True
        assert data["matched_code"] is not None

    def test_check_membership_hierarchical(self, client):
        response = client.get(
            "/clinical-valuesets/diabetes_mellitus/check/ICD10CM/E11.65"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_member"] is True
        assert data["matched_code"] == "E11"

    def test_check_membership_negative(self, client):
        response = client.get(
            "/clinical-valuesets/diabetes_mellitus/check/ICD10CM/J45.0"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_member"] is False
        assert data["matched_code"] is None

    def test_check_membership_vs_not_found(self, client):
        response = client.get(
            "/clinical-valuesets/nonexistent/check/ICD10CM/E11"
        )
        assert response.status_code == 404

    def test_create_endpoint(self, client):
        response = client.post(
            "/clinical-valuesets",
            json={
                "name": "custom_vs",
                "code_system": "ICD10CM",
                "codes": [
                    {
                        "code": "Z00",
                        "code_system": "ICD10CM",
                        "display_name": "General examination",
                        "is_active": True,
                    }
                ],
                "description": "Custom value set",
                "version": "1.0.0",
                "domain": "General",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "custom_vs"
        assert len(data["codes"]) == 1

    def test_create_duplicate_returns_400(self, client):
        response = client.post(
            "/clinical-valuesets",
            json={
                "name": "diabetes_mellitus",  # Already exists
                "code_system": "ICD10CM",
                "codes": [],
            },
        )
        assert response.status_code == 400
