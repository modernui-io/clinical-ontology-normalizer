"""Tests for API Contract Stability framework (CTO-5).

Covers:
- Contract capture from a mock FastAPI app
- Breaking change detection (removed endpoint, removed field, type change,
  added required field, removed parameter)
- Non-breaking change detection (new endpoint, new optional field,
  new optional parameter)
- Report generation
- Snapshot serialization / deserialization
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI, Query
from pydantic import BaseModel, Field

from app.schemas.api_contract import (
    ChangeType,
    ContractChange,
    ContractComparison,
    ContractSnapshot,
    EndpointContract,
)
from app.services.api_contract_service import (
    ApiContractService,
    _compare_params,
    _compare_schemas,
)


# ======================================================================
# Helpers: tiny Pydantic models & mock FastAPI apps for testing
# ======================================================================


class PatientResponse(BaseModel):
    id: int
    name: str
    active: bool = True


class PatientCreate(BaseModel):
    name: str
    age: int


class PatientResponseV2(BaseModel):
    """V2: removed `active`, changed `id` type, added required `email`."""

    id: str  # type change: int -> str
    name: str
    email: str  # new required field
    # `active` removed


class DocumentResponse(BaseModel):
    doc_id: str
    text: str
    status: str = "pending"


def _build_app_v1() -> FastAPI:
    """Build a minimal FastAPI app representing the 'baseline' contract."""
    app = FastAPI(title="TestApp", version="1.0.0")

    @app.get("/api/v1/patients", response_model=list[PatientResponse], tags=["Patients"])
    def list_patients(
        skip: int = Query(0),
        limit: int = Query(100),
    ) -> Any:
        return []

    @app.get("/api/v1/patients/{patient_id}", response_model=PatientResponse, tags=["Patients"])
    def get_patient(patient_id: int) -> Any:
        return {}

    @app.post("/api/v1/patients", response_model=PatientResponse, tags=["Patients"])
    def create_patient(body: PatientCreate) -> Any:
        return {}

    @app.get("/api/v1/documents", response_model=list[DocumentResponse], tags=["Documents"])
    def list_documents() -> Any:
        return []

    @app.get("/api/v1/health", tags=["Health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


def _build_app_v2() -> FastAPI:
    """Build a FastAPI app with several breaking and non-breaking changes.

    Changes vs v1:
      - GET /patients response: id int->str, active removed, email added (required)
      - GET /patients/{patient_id}: REMOVED
      - GET /documents: new optional query param `status`
      - GET /health: unchanged
      - GET /api/v1/stats: NEW endpoint
    """
    app = FastAPI(title="TestApp", version="2.0.0")

    @app.get("/api/v1/patients", response_model=list[PatientResponseV2], tags=["Patients"])
    def list_patients(
        skip: int = Query(0),
        limit: int = Query(100),
    ) -> Any:
        return []

    # patient_id endpoint REMOVED

    @app.post("/api/v1/patients", response_model=PatientResponseV2, tags=["Patients"])
    def create_patient(body: PatientCreate) -> Any:
        return {}

    @app.get("/api/v1/documents", response_model=list[DocumentResponse], tags=["Documents"])
    def list_documents(status: str | None = Query(None)) -> Any:
        return []

    @app.get("/api/v1/health", tags=["Health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/stats", tags=["Stats"])
    def stats() -> dict[str, int]:
        return {"total": 0}

    return app


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def app_v1() -> FastAPI:
    return _build_app_v1()


@pytest.fixture
def app_v2() -> FastAPI:
    return _build_app_v2()


@pytest.fixture
def service_v1(app_v1: FastAPI) -> ApiContractService:
    return ApiContractService(app_v1)


@pytest.fixture
def service_v2(app_v2: FastAPI) -> ApiContractService:
    return ApiContractService(app_v2)


@pytest.fixture
def snapshot_v1(service_v1: ApiContractService) -> ContractSnapshot:
    return service_v1.capture_contract_snapshot("v1.0", app_version="1.0.0")


@pytest.fixture
def snapshot_v2(service_v2: ApiContractService) -> ContractSnapshot:
    return service_v2.capture_contract_snapshot("v2.0", app_version="2.0.0")


@pytest.fixture
def comparison(
    service_v1: ApiContractService,
    snapshot_v1: ContractSnapshot,
    snapshot_v2: ContractSnapshot,
) -> ContractComparison:
    return service_v1.compare_contracts(snapshot_v1, snapshot_v2)


# ======================================================================
# Tests: Contract Capture
# ======================================================================


class TestContractCapture:
    """Test that contract snapshots are captured correctly."""

    def test_capture_returns_snapshot(self, snapshot_v1: ContractSnapshot) -> None:
        assert snapshot_v1.version == "v1.0"
        assert snapshot_v1.app_version == "1.0.0"
        assert isinstance(snapshot_v1.timestamp, datetime)

    def test_capture_finds_all_endpoints(self, snapshot_v1: ContractSnapshot) -> None:
        # v1 has: GET /patients, GET /patients/{id}, POST /patients,
        #         GET /documents, GET /health = 5 endpoints
        assert snapshot_v1.endpoint_count == 5
        assert len(snapshot_v1.endpoints) == 5

    def test_capture_endpoint_methods(self, snapshot_v1: ContractSnapshot) -> None:
        keys = {ep.contract_key() for ep in snapshot_v1.endpoints}
        assert "GET /api/v1/patients" in keys
        assert "POST /api/v1/patients" in keys
        assert "GET /api/v1/patients/{patient_id}" in keys
        assert "GET /api/v1/documents" in keys
        assert "GET /api/v1/health" in keys

    def test_capture_response_schema(self, snapshot_v1: ContractSnapshot) -> None:
        ep_map = snapshot_v1.endpoints_by_key()
        patient_ep = ep_map.get("GET /api/v1/patients/{patient_id}")
        assert patient_ep is not None
        assert patient_ep.response_schema is not None
        # PatientResponse has id, name, active
        props = patient_ep.response_schema.get("properties", {})
        assert "id" in props
        assert "name" in props
        assert "active" in props

    def test_capture_request_schema(self, snapshot_v1: ContractSnapshot) -> None:
        ep_map = snapshot_v1.endpoints_by_key()
        create_ep = ep_map.get("POST /api/v1/patients")
        assert create_ep is not None
        assert create_ep.request_schema is not None
        props = create_ep.request_schema.get("properties", {})
        assert "name" in props
        assert "age" in props

    def test_capture_query_params(self, snapshot_v1: ContractSnapshot) -> None:
        ep_map = snapshot_v1.endpoints_by_key()
        list_ep = ep_map.get("GET /api/v1/patients")
        assert list_ep is not None
        param_names = {p["name"] for p in list_ep.query_params}
        assert "skip" in param_names
        assert "limit" in param_names

    def test_capture_path_params(self, snapshot_v1: ContractSnapshot) -> None:
        ep_map = snapshot_v1.endpoints_by_key()
        get_ep = ep_map.get("GET /api/v1/patients/{patient_id}")
        assert get_ep is not None
        param_names = {p["name"] for p in get_ep.path_params}
        assert "patient_id" in param_names

    def test_capture_tags(self, snapshot_v1: ContractSnapshot) -> None:
        ep_map = snapshot_v1.endpoints_by_key()
        ep = ep_map["GET /api/v1/patients"]
        assert "Patients" in ep.tags


# ======================================================================
# Tests: Breaking Change Detection
# ======================================================================


class TestBreakingChanges:
    """Test that breaking changes are correctly detected."""

    def test_removed_endpoint_is_breaking(self, comparison: ContractComparison) -> None:
        assert "GET /api/v1/patients/{patient_id}" in comparison.removed_endpoints
        breaking_descs = [c.description for c in comparison.breaking_changes]
        assert any("Endpoint removed" in d for d in breaking_descs)

    def test_removed_field_is_breaking(self, comparison: ContractComparison) -> None:
        # `active` field was removed from PatientResponse
        breaking = [
            c for c in comparison.breaking_changes
            if "active" in c.field and "removed" in c.description.lower()
        ]
        assert len(breaking) >= 1

    def test_type_change_is_breaking(self, comparison: ContractComparison) -> None:
        # `id` changed from integer to string
        breaking = [
            c for c in comparison.breaking_changes
            if "id" in c.field and "type changed" in c.description.lower()
        ]
        assert len(breaking) >= 1

    def test_added_required_field_is_breaking(self, comparison: ContractComparison) -> None:
        # `email` is a new required field in V2
        breaking = [
            c for c in comparison.breaking_changes
            if "email" in c.field and "required" in c.description.lower()
        ]
        assert len(breaking) >= 1

    def test_has_breaking_changes_property(self, comparison: ContractComparison) -> None:
        assert comparison.has_breaking_changes is True


# ======================================================================
# Tests: Non-Breaking Change Detection
# ======================================================================


class TestNonBreakingChanges:
    """Test that non-breaking changes are correctly detected."""

    def test_new_endpoint_is_non_breaking(self, comparison: ContractComparison) -> None:
        assert "GET /api/v1/stats" in comparison.added_endpoints
        non_breaking_descs = [c.description for c in comparison.non_breaking_changes]
        assert any("New endpoint added" in d for d in non_breaking_descs)

    def test_new_optional_param_is_non_breaking(self, comparison: ContractComparison) -> None:
        # `status` was added as optional query param on GET /documents
        non_breaking = [
            c for c in comparison.non_breaking_changes
            if "status" in c.field and "optional" in c.description.lower()
        ]
        assert len(non_breaking) >= 1


# ======================================================================
# Tests: Schema Comparison Helpers
# ======================================================================


class TestSchemaComparison:
    """Test the low-level schema comparison functions."""

    def test_identical_schemas_no_changes(self) -> None:
        schema = {
            "type": "object",
            "properties": {"id": {"type": "integer"}, "name": {"type": "string"}},
            "required": ["id", "name"],
        }
        changes = _compare_schemas(schema, schema, "GET /test", "response")
        assert len(changes) == 0

    def test_new_optional_field(self) -> None:
        base = {
            "type": "object",
            "properties": {"id": {"type": "integer"}},
            "required": ["id"],
        }
        current = {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "nickname": {"type": "string"},
            },
            "required": ["id"],
        }
        changes = _compare_schemas(base, current, "GET /test", "response")
        assert len(changes) == 1
        assert changes[0].change_type == ChangeType.NON_BREAKING
        assert "nickname" in changes[0].field

    def test_nested_object_field_removal(self) -> None:
        base = {
            "type": "object",
            "properties": {
                "address": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string"},
                        "zip": {"type": "string"},
                    },
                },
            },
        }
        current = {
            "type": "object",
            "properties": {
                "address": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string"},
                        # zip removed
                    },
                },
            },
        }
        changes = _compare_schemas(base, current, "GET /test", "response")
        breaking = [c for c in changes if c.change_type == ChangeType.BREAKING]
        assert len(breaking) == 1
        assert "address.zip" in breaking[0].field

    def test_optional_to_required_is_breaking(self) -> None:
        base = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["name"],
        }
        current = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["name", "age"],
        }
        changes = _compare_schemas(base, current, "POST /test", "request")
        breaking = [c for c in changes if c.change_type == ChangeType.BREAKING]
        assert len(breaking) == 1
        assert "age" in breaking[0].field
        assert "optional to required" in breaking[0].description.lower()


class TestParamComparison:
    """Test the parameter comparison helper."""

    def test_removed_param_is_breaking(self) -> None:
        base = [{"name": "page", "required": False}]
        current: list[dict[str, Any]] = []
        changes = _compare_params(base, current, "GET /test", "query")
        assert len(changes) == 1
        assert changes[0].change_type == ChangeType.BREAKING

    def test_added_required_param_is_breaking(self) -> None:
        base: list[dict[str, Any]] = []
        current = [{"name": "api_key", "required": True}]
        changes = _compare_params(base, current, "GET /test", "query")
        assert len(changes) == 1
        assert changes[0].change_type == ChangeType.BREAKING

    def test_added_optional_param_is_non_breaking(self) -> None:
        base: list[dict[str, Any]] = []
        current = [{"name": "sort", "required": False}]
        changes = _compare_params(base, current, "GET /test", "query")
        assert len(changes) == 1
        assert changes[0].change_type == ChangeType.NON_BREAKING


# ======================================================================
# Tests: Report Generation
# ======================================================================


class TestReportGeneration:
    """Test Markdown report generation."""

    def test_report_contains_status_fail(
        self, service_v1: ApiContractService, comparison: ContractComparison
    ) -> None:
        report = service_v1.generate_contract_report(comparison)
        assert "FAIL" in report
        assert "Breaking changes detected" in report

    def test_report_contains_breaking_section(
        self, service_v1: ApiContractService, comparison: ContractComparison
    ) -> None:
        report = service_v1.generate_contract_report(comparison)
        assert "## Breaking Changes" in report

    def test_report_contains_added_endpoints(
        self, service_v1: ApiContractService, comparison: ContractComparison
    ) -> None:
        report = service_v1.generate_contract_report(comparison)
        assert "## Added Endpoints" in report
        assert "/api/v1/stats" in report

    def test_report_pass_when_no_breaking(self, service_v1: ApiContractService) -> None:
        comparison = ContractComparison(
            baseline_version="v1",
            current_version="v2",
            breaking_changes=[],
            non_breaking_changes=[
                ContractChange(
                    change_type=ChangeType.NON_BREAKING,
                    endpoint="GET /test",
                    description="New optional field",
                )
            ],
        )
        report = service_v1.generate_contract_report(comparison)
        assert "PASS" in report
        assert "FAIL" not in report


# ======================================================================
# Tests: Serialization / Deserialization
# ======================================================================


class TestSerialization:
    """Test contract snapshot serialization and persistence."""

    def test_snapshot_roundtrip_json(self, snapshot_v1: ContractSnapshot) -> None:
        """Serialize to JSON and deserialize back."""
        json_str = snapshot_v1.model_dump_json(indent=2)
        restored = ContractSnapshot.model_validate_json(json_str)
        assert restored.version == snapshot_v1.version
        assert restored.endpoint_count == snapshot_v1.endpoint_count
        assert len(restored.endpoints) == len(snapshot_v1.endpoints)

    def test_snapshot_save_and_load(
        self,
        service_v1: ApiContractService,
        snapshot_v1: ContractSnapshot,
        tmp_path: Path,
    ) -> None:
        """Save to disk and load back."""
        saved = service_v1.save_snapshot(snapshot_v1, directory=tmp_path)
        assert saved.exists()

        loaded = ApiContractService.load_snapshot(saved)
        assert loaded.version == snapshot_v1.version
        assert loaded.endpoint_count == snapshot_v1.endpoint_count

    def test_endpoint_contract_key(self) -> None:
        ep = EndpointContract(
            path="/api/v1/patients",
            method="get",
        )
        assert ep.contract_key() == "GET /api/v1/patients"

    def test_comparison_model_serialization(self, comparison: ContractComparison) -> None:
        data = comparison.model_dump()
        assert "breaking_changes" in data
        assert "non_breaking_changes" in data
        assert "removed_endpoints" in data
        assert "added_endpoints" in data
        # Roundtrip
        restored = ContractComparison.model_validate(data)
        assert restored.has_breaking_changes == comparison.has_breaking_changes

    def test_contract_change_model(self) -> None:
        change = ContractChange(
            change_type=ChangeType.BREAKING,
            endpoint="DELETE /api/v1/users/{id}",
            field="response.status",
            description="Field removed",
        )
        assert change.change_type == ChangeType.BREAKING
        data = change.model_dump()
        assert data["change_type"] == "BREAKING"
