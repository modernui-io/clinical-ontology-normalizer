"""Deployment Verification & API Contract Testing service.

VPE-9: Provides deployment verification with smoke tests, health checks,
schema validation, performance checks, data integrity verification, and
rollback readiness.  API contract testing with schema diffing, backward
compatibility analysis, and breaking-change detection.  Error budgets with
SLI definitions, burn-rate calculation, and deployment gate evaluation.

Usage:
    from app.services.deployment_verification_service import (
        get_deployment_verification_service,
    )

    service = get_deployment_verification_service()
    verification = service.create_verification(
        deployment_id="DEP-001",
        environment=EnvironmentName.STAGING,
        version="2.3.0",
        triggered_by="ci-pipeline",
    )
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta, timezone
from threading import Lock
from uuid import uuid4

from pydantic import BaseModel, Field

from app.schemas.deployment_verification import (
    APIContract,
    APIContractCreate,
    APIContractListResponse,
    APIContractUpdate,
    BreakingChange,
    ContractTestResult,
    ContractTestResultListResponse,
    ContractTestType,
    DeploymentGateEvaluation,
    DeploymentGateResult,
    DeploymentVerification,
    DeploymentVerificationCreate,
    DeploymentVerificationListResponse,
    DeploymentVerificationMetrics,
    EnvironmentName,
    ErrorBudget,
    ErrorBudgetCreate,
    ErrorBudgetListResponse,
    ErrorBudgetStatus,
    ErrorBudgetViolation,
    SLIDefinition,
    SLIDefinitionCreate,
    SLIDefinitionListResponse,
    VerificationCheck,
    VerificationStatus,
    VerificationTrend,
    VerificationType,
)

logger = logging.getLogger(__name__)

# Singleton instance and lock
_dv_instance: DeploymentVerificationService | None = None
_dv_lock = Lock()


# ---------------------------------------------------------------------------
# Internal record models
# ---------------------------------------------------------------------------


class VerificationCheckRecord(BaseModel):
    """Internal verification check record."""

    id: str = Field(default_factory=lambda: f"CHK-{uuid4().hex[:8].upper()}")
    name: str
    verification_type: VerificationType
    description: str | None = None
    expected_result: str | None = None
    actual_result: str | None = None
    status: VerificationStatus = VerificationStatus.PENDING
    duration_ms: float | None = None
    error_message: str | None = None
    endpoint_url: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DeploymentVerificationRecord(BaseModel):
    """Internal deployment verification record."""

    id: str = Field(default_factory=lambda: f"DV-{uuid4().hex[:8].upper()}")
    deployment_id: str
    environment: EnvironmentName = EnvironmentName.STAGING
    version: str = ""
    check_ids: list[str] = Field(default_factory=list)
    overall_status: VerificationStatus = VerificationStatus.PENDING
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    triggered_by: str = "system"
    rollback_recommended: bool = False


class APIContractRecord(BaseModel):
    """Internal API contract record."""

    id: str = Field(default_factory=lambda: f"CTR-{uuid4().hex[:8].upper()}")
    endpoint_path: str
    method: str = "GET"
    version: str = "v1"
    request_schema: dict | None = None
    response_schema: dict | None = None
    required_headers: list[str] = Field(default_factory=list)
    deprecated: bool = False
    deprecated_date: datetime | None = None
    replacement_endpoint: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ContractTestResultRecord(BaseModel):
    """Internal contract test result record."""

    id: str = Field(default_factory=lambda: f"CTX-{uuid4().hex[:8].upper()}")
    contract_id: str
    test_type: ContractTestType = ContractTestType.RESPONSE_SCHEMA
    status: VerificationStatus = VerificationStatus.PASSED
    details: str | None = None
    breaking_changes: list[BreakingChange] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ErrorBudgetRecord(BaseModel):
    """Internal error budget record."""

    id: str = Field(default_factory=lambda: f"EB-{uuid4().hex[:8].upper()}")
    service_name: str
    sli_name: str
    target_percent: float = 99.9
    current_percent: float = 99.95
    remaining_budget_percent: float = 50.0
    status: ErrorBudgetStatus = ErrorBudgetStatus.HEALTHY
    burn_rate_per_hour: float = 0.001
    time_to_exhaustion_hours: float | None = None
    window_start: datetime = Field(default_factory=lambda: datetime.now(timezone.utc) - timedelta(days=30))
    window_end: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    violations: list[ErrorBudgetViolation] = Field(default_factory=list)


class SLIDefinitionRecord(BaseModel):
    """Internal SLI definition record."""

    id: str = Field(default_factory=lambda: f"SLI-{uuid4().hex[:8].upper()}")
    service_name: str
    sli_name: str
    description: str | None = None
    target_percent: float = 99.9
    measurement_query: str | None = None
    window_hours: int = 720


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class DeploymentVerificationService:
    """In-memory deployment verification and API contract testing service."""

    def __init__(self) -> None:
        self._verifications: dict[str, DeploymentVerificationRecord] = {}
        self._checks: dict[str, VerificationCheckRecord] = {}
        self._contracts: dict[str, APIContractRecord] = {}
        self._contract_results: dict[str, ContractTestResultRecord] = {}
        self._error_budgets: dict[str, ErrorBudgetRecord] = {}
        self._sli_definitions: dict[str, SLIDefinitionRecord] = {}
        self._seed_data()

    # -------------------------------------------------------------------
    # Seed data
    # -------------------------------------------------------------------

    def _seed_data(self) -> None:  # noqa: C901 - seed data is intentionally verbose
        """Pre-populate verifications, contracts, budgets for demo."""
        now = datetime.now(timezone.utc)

        # ---- Deployment Verifications ----

        # DV-1: v2.0.0 production deployment - PASSED
        dv1_checks = self._create_check_suite(
            "DV-SEED-0001", "2.0.0", EnvironmentName.PRODUCTION, now - timedelta(days=88),
            all_pass=True,
        )
        dv1 = DeploymentVerificationRecord(
            id="DV-SEED-0001",
            deployment_id="DEP-SEED-0002",
            environment=EnvironmentName.PRODUCTION,
            version="2.0.0",
            check_ids=[c.id for c in dv1_checks],
            overall_status=VerificationStatus.PASSED,
            started_at=now - timedelta(days=88),
            completed_at=now - timedelta(days=88) + timedelta(minutes=3),
            triggered_by="Sarah Chen",
            rollback_recommended=False,
        )
        self._verifications[dv1.id] = dv1

        # DV-2: v2.1.0 staging - PASSED
        dv2_checks = self._create_check_suite(
            "DV-SEED-0002", "2.1.0", EnvironmentName.STAGING, now - timedelta(days=59),
            all_pass=True,
        )
        dv2 = DeploymentVerificationRecord(
            id="DV-SEED-0002",
            deployment_id="DEP-SEED-0003",
            environment=EnvironmentName.STAGING,
            version="2.1.0",
            check_ids=[c.id for c in dv2_checks],
            overall_status=VerificationStatus.PASSED,
            started_at=now - timedelta(days=59),
            completed_at=now - timedelta(days=59) + timedelta(minutes=4),
            triggered_by="CI Pipeline",
            rollback_recommended=False,
        )
        self._verifications[dv2.id] = dv2

        # DV-3: v2.1.0 production - PASSED
        dv3_checks = self._create_check_suite(
            "DV-SEED-0003", "2.1.0", EnvironmentName.PRODUCTION, now - timedelta(days=58),
            all_pass=True,
        )
        dv3 = DeploymentVerificationRecord(
            id="DV-SEED-0003",
            deployment_id="DEP-SEED-0004",
            environment=EnvironmentName.PRODUCTION,
            version="2.1.0",
            check_ids=[c.id for c in dv3_checks],
            overall_status=VerificationStatus.PASSED,
            started_at=now - timedelta(days=58),
            completed_at=now - timedelta(days=58) + timedelta(minutes=3),
            triggered_by="Sarah Chen",
            rollback_recommended=False,
        )
        self._verifications[dv3.id] = dv3

        # DV-4: v2.2.0 production - FAILED (led to rollback)
        dv4_checks = self._create_check_suite(
            "DV-SEED-0004", "2.2.0", EnvironmentName.PRODUCTION, now - timedelta(days=33),
            all_pass=False,
        )
        dv4 = DeploymentVerificationRecord(
            id="DV-SEED-0004",
            deployment_id="DEP-SEED-0005",
            environment=EnvironmentName.PRODUCTION,
            version="2.2.0",
            check_ids=[c.id for c in dv4_checks],
            overall_status=VerificationStatus.FAILED,
            started_at=now - timedelta(days=33),
            completed_at=now - timedelta(days=33) + timedelta(minutes=5),
            triggered_by="James Rodriguez",
            rollback_recommended=True,
        )
        self._verifications[dv4.id] = dv4

        # DV-5: v2.3.0 staging - RUNNING
        dv5_checks = self._create_check_suite_running(
            "DV-SEED-0005", "2.3.0", EnvironmentName.STAGING, now - timedelta(minutes=10),
        )
        dv5 = DeploymentVerificationRecord(
            id="DV-SEED-0005",
            deployment_id="DEP-SEED-0006",
            environment=EnvironmentName.STAGING,
            version="2.3.0",
            check_ids=[c.id for c in dv5_checks],
            overall_status=VerificationStatus.RUNNING,
            started_at=now - timedelta(minutes=10),
            completed_at=None,
            triggered_by="CI Pipeline",
            rollback_recommended=False,
        )
        self._verifications[dv5.id] = dv5

        # ---- API Contracts (15 contracts) ----
        contracts_data = [
            ("CTR-SEED-0001", "/api/v1/patients", "GET", {"type": "object", "properties": {"id": {"type": "string"}, "name": {"type": "string"}, "status": {"type": "string"}}}, False),
            ("CTR-SEED-0002", "/api/v1/patients", "POST", {"type": "object", "properties": {"id": {"type": "string"}, "message": {"type": "string"}}}, False),
            ("CTR-SEED-0003", "/api/v1/patients/{id}", "GET", {"type": "object", "properties": {"id": {"type": "string"}, "name": {"type": "string"}, "demographics": {"type": "object"}}}, False),
            ("CTR-SEED-0004", "/api/v1/trials", "GET", {"type": "object", "properties": {"trials": {"type": "array"}, "total": {"type": "integer"}}}, False),
            ("CTR-SEED-0005", "/api/v1/trials/{id}", "GET", {"type": "object", "properties": {"id": {"type": "string"}, "title": {"type": "string"}, "phase": {"type": "string"}}}, False),
            ("CTR-SEED-0006", "/api/v1/trials", "POST", {"type": "object", "properties": {"id": {"type": "string"}, "message": {"type": "string"}}}, False),
            ("CTR-SEED-0007", "/api/v1/screening/run", "POST", {"type": "object", "properties": {"screening_id": {"type": "string"}, "status": {"type": "string"}, "results": {"type": "array"}}}, False),
            ("CTR-SEED-0008", "/api/v1/screening/results/{id}", "GET", {"type": "object", "properties": {"id": {"type": "string"}, "patient_id": {"type": "string"}, "eligible": {"type": "boolean"}}}, False),
            ("CTR-SEED-0009", "/api/v1/fhir/Patient", "GET", {"type": "object", "properties": {"resourceType": {"type": "string"}, "entry": {"type": "array"}}}, False),
            ("CTR-SEED-0010", "/api/v1/fhir/Patient", "POST", {"type": "object", "properties": {"resourceType": {"type": "string"}, "id": {"type": "string"}}}, False),
            ("CTR-SEED-0011", "/api/v1/fhir/Condition", "GET", {"type": "object", "properties": {"resourceType": {"type": "string"}, "entry": {"type": "array"}}}, False),
            ("CTR-SEED-0012", "/api/v1/documents", "POST", {"type": "object", "properties": {"id": {"type": "string"}, "status": {"type": "string"}}}, False),
            ("CTR-SEED-0013", "/api/v1/documents/{id}", "GET", {"type": "object", "properties": {"id": {"type": "string"}, "text": {"type": "string"}, "patient_id": {"type": "string"}}}, False),
            ("CTR-SEED-0014", "/api/v1/documents/search", "GET", {"type": "object", "properties": {"results": {"type": "array"}, "total": {"type": "integer"}}}, True),
            ("CTR-SEED-0015", "/api/v1/screening/bulk", "POST", {"type": "object", "properties": {"batch_id": {"type": "string"}, "status": {"type": "string"}}}, False),
        ]
        for cid, path, method, resp_schema, deprecated in contracts_data:
            req_schema = None
            if method == "POST":
                if "patients" in path and "{" not in path:
                    req_schema = {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}, "demographics": {"type": "object"}}}
                elif "trials" in path and "{" not in path:
                    req_schema = {"type": "object", "required": ["title", "phase"], "properties": {"title": {"type": "string"}, "phase": {"type": "string"}}}
                elif "screening/run" in path:
                    req_schema = {"type": "object", "required": ["patient_id", "trial_id"], "properties": {"patient_id": {"type": "string"}, "trial_id": {"type": "string"}}}
                elif "documents" in path and "{" not in path:
                    req_schema = {"type": "object", "required": ["patient_id", "text"], "properties": {"patient_id": {"type": "string"}, "text": {"type": "string"}}}
                elif "fhir" in path:
                    req_schema = {"type": "object", "required": ["resourceType"], "properties": {"resourceType": {"type": "string"}}}
                elif "bulk" in path:
                    req_schema = {"type": "object", "required": ["patient_ids", "trial_id"], "properties": {"patient_ids": {"type": "array"}, "trial_id": {"type": "string"}}}
            c = APIContractRecord(
                id=cid,
                endpoint_path=path,
                method=method,
                version="v1",
                request_schema=req_schema,
                response_schema=resp_schema,
                required_headers=["Content-Type", "Authorization"] if method == "POST" else ["Authorization"],
                deprecated=deprecated,
                deprecated_date=now - timedelta(days=14) if deprecated else None,
                replacement_endpoint="/api/v1/documents/query" if deprecated else None,
                created_at=now - timedelta(days=100),
                updated_at=now - timedelta(days=5),
            )
            self._contracts[c.id] = c

        # ---- Contract Test Results (10: 8 passed, 2 failed) ----
        test_results_data = [
            ("CTX-SEED-0001", "CTR-SEED-0001", ContractTestType.RESPONSE_SCHEMA, VerificationStatus.PASSED, "Response matches schema", []),
            ("CTX-SEED-0002", "CTR-SEED-0002", ContractTestType.REQUEST_SCHEMA, VerificationStatus.PASSED, "Request schema valid", []),
            ("CTX-SEED-0003", "CTR-SEED-0003", ContractTestType.BACKWARD_COMPATIBILITY, VerificationStatus.PASSED, "Backward compatible", []),
            ("CTX-SEED-0004", "CTR-SEED-0004", ContractTestType.RESPONSE_SCHEMA, VerificationStatus.PASSED, "Response matches schema", []),
            ("CTX-SEED-0005", "CTR-SEED-0007", ContractTestType.RESPONSE_SCHEMA, VerificationStatus.PASSED, "Screening response valid", []),
            ("CTX-SEED-0006", "CTR-SEED-0009", ContractTestType.BACKWARD_COMPATIBILITY, VerificationStatus.PASSED, "FHIR response backward compatible", []),
            ("CTX-SEED-0007", "CTR-SEED-0012", ContractTestType.REQUEST_SCHEMA, VerificationStatus.PASSED, "Document upload schema valid", []),
            ("CTX-SEED-0008", "CTR-SEED-0015", ContractTestType.RESPONSE_SCHEMA, VerificationStatus.PASSED, "Bulk screening response valid", []),
            ("CTX-SEED-0009", "CTR-SEED-0005", ContractTestType.BREAKING_CHANGE, VerificationStatus.FAILED, "Breaking changes detected in trial response", [
                BreakingChange(field_path="$.phase", change_type="type_changed", old_value="string", new_value="integer", severity="HIGH"),
                BreakingChange(field_path="$.sponsor", change_type="removed", old_value="string", new_value=None, severity="MEDIUM"),
            ]),
            ("CTX-SEED-0010", "CTR-SEED-0008", ContractTestType.BREAKING_CHANGE, VerificationStatus.FAILED, "Screening result schema changed", [
                BreakingChange(field_path="$.score", change_type="required_added", old_value=None, new_value="required", severity="HIGH"),
            ]),
        ]
        for rid, cid, ttype, status, details, breaks in test_results_data:
            r = ContractTestResultRecord(
                id=rid,
                contract_id=cid,
                test_type=ttype,
                status=status,
                details=details,
                breaking_changes=breaks,
                created_at=now - timedelta(days=random.randint(1, 30)),
            )
            self._contract_results[r.id] = r

        # ---- Error Budgets (6) ----
        budgets_data = [
            ("EB-SEED-0001", "api-gateway", "availability", 99.9, 99.95, 50.0, ErrorBudgetStatus.HEALTHY, 0.001, 500.0, []),
            ("EB-SEED-0002", "nlp-pipeline", "latency_p99", 95.0, 94.2, 16.0, ErrorBudgetStatus.WARNING, 0.012, 133.3, [
                ErrorBudgetViolation(timestamp=now - timedelta(days=5), duration_minutes=45, error_rate_percent=8.3, cause="NLP model loading spike"),
            ]),
            ("EB-SEED-0003", "screening-engine", "accuracy", 98.0, 98.5, 75.0, ErrorBudgetStatus.HEALTHY, 0.0005, 1500.0, []),
            ("EB-SEED-0004", "fhir-import", "success_rate", 99.5, 99.1, 20.0, ErrorBudgetStatus.CRITICAL, 0.025, 80.0, [
                ErrorBudgetViolation(timestamp=now - timedelta(days=3), duration_minutes=120, error_rate_percent=3.2, cause="FHIR server intermittent timeout"),
                ErrorBudgetViolation(timestamp=now - timedelta(days=1), duration_minutes=30, error_rate_percent=1.5, cause="Schema validation failures on Observation resources"),
            ]),
            ("EB-SEED-0005", "data-pipeline", "freshness", 99.0, 99.8, 80.0, ErrorBudgetStatus.HEALTHY, 0.0003, 2666.7, []),
            ("EB-SEED-0006", "knowledge-graph", "query_latency_p95", 95.0, 93.5, 0.0, ErrorBudgetStatus.EXHAUSTED, 0.05, 0.0, [
                ErrorBudgetViolation(timestamp=now - timedelta(days=7), duration_minutes=240, error_rate_percent=12.0, cause="Graph traversal regression after index rebuild"),
                ErrorBudgetViolation(timestamp=now - timedelta(days=2), duration_minutes=180, error_rate_percent=9.5, cause="Concurrent query contention"),
            ]),
        ]
        for bid, svc, sli, target, current, remaining, status, burn, tte, violations in budgets_data:
            b = ErrorBudgetRecord(
                id=bid,
                service_name=svc,
                sli_name=sli,
                target_percent=target,
                current_percent=current,
                remaining_budget_percent=remaining,
                status=status,
                burn_rate_per_hour=burn,
                time_to_exhaustion_hours=tte,
                window_start=now - timedelta(days=30),
                window_end=now,
                violations=violations,
            )
            self._error_budgets[b.id] = b

        # ---- SLI Definitions (8) ----
        sli_data = [
            ("SLI-SEED-0001", "api-gateway", "availability", "Percentage of successful HTTP responses (non-5xx)", 99.9, "sum(http_status < 500) / count(*) * 100", 720),
            ("SLI-SEED-0002", "api-gateway", "latency_p99", "99th percentile response latency under 500ms", 99.0, "percentile(response_time_ms, 99) < 500", 720),
            ("SLI-SEED-0003", "nlp-pipeline", "latency_p99", "NLP processing latency 99th percentile under 2s", 95.0, "percentile(nlp_processing_ms, 99) < 2000", 720),
            ("SLI-SEED-0004", "nlp-pipeline", "throughput", "NLP pipeline throughput above 100 docs/min", 99.0, "count(processed_docs) / minutes > 100", 720),
            ("SLI-SEED-0005", "screening-engine", "accuracy", "Screening accuracy vs gold standard", 98.0, "correct_screenings / total_screenings * 100", 720),
            ("SLI-SEED-0006", "fhir-import", "success_rate", "Percentage of FHIR imports completing successfully", 99.5, "successful_imports / total_imports * 100", 720),
            ("SLI-SEED-0007", "data-pipeline", "freshness", "Data available within 5 minutes of ingestion", 99.0, "on_time_deliveries / total_deliveries * 100", 720),
            ("SLI-SEED-0008", "knowledge-graph", "query_latency_p95", "KG query 95th percentile under 1s", 95.0, "percentile(kg_query_ms, 95) < 1000", 720),
        ]
        for sid, svc, sli, desc, target, query, window in sli_data:
            s = SLIDefinitionRecord(
                id=sid,
                service_name=svc,
                sli_name=sli,
                description=desc,
                target_percent=target,
                measurement_query=query,
                window_hours=window,
            )
            self._sli_definitions[s.id] = s

    # -------------------------------------------------------------------
    # Helpers for seed check generation
    # -------------------------------------------------------------------

    def _create_check_suite(
        self,
        prefix: str,
        version: str,
        env: EnvironmentName,
        base_time: datetime,
        all_pass: bool = True,
    ) -> list[VerificationCheckRecord]:
        """Create a suite of 7 checks for a deployment verification."""
        checks_config = [
            ("API Health Check", VerificationType.HEALTH_CHECK, "/api/v1/health", "200 OK", 45.0),
            ("Database Connectivity", VerificationType.HEALTH_CHECK, "/api/v1/health/db", "connected", 120.0),
            ("Patient Endpoint Smoke", VerificationType.SMOKE_TEST, "/api/v1/patients", "200 OK", 230.0),
            ("Trial Endpoint Smoke", VerificationType.SMOKE_TEST, "/api/v1/trials", "200 OK", 180.0),
            ("Schema Validation", VerificationType.SCHEMA_VALIDATION, None, "all schemas valid", 350.0),
            ("Response Time P95", VerificationType.PERFORMANCE_CHECK, None, "< 500ms", 1200.0),
            ("Rollback Readiness", VerificationType.ROLLBACK_READINESS, None, "rollback scripts verified", 500.0),
        ]
        results: list[VerificationCheckRecord] = []
        for i, (name, vtype, url, expected, dur) in enumerate(checks_config):
            if not all_pass and i >= 4:
                status = VerificationStatus.FAILED
                actual = "FAILED - " + ("schema mismatch" if i == 4 else "p95 = 1200ms" if i == 5 else "rollback script missing")
                err = f"Check failed: {actual}"
            else:
                status = VerificationStatus.PASSED
                actual = expected
                err = None
            c = VerificationCheckRecord(
                id=f"{prefix}-CHK-{i + 1:04d}",
                name=name,
                verification_type=vtype,
                description=f"{name} for {version} in {env.value}",
                expected_result=expected,
                actual_result=actual,
                status=status,
                duration_ms=dur + random.uniform(-20, 20),
                error_message=err,
                endpoint_url=url,
                created_at=base_time + timedelta(seconds=i * 30),
            )
            self._checks[c.id] = c
            results.append(c)
        return results

    def _create_check_suite_running(
        self,
        prefix: str,
        version: str,
        env: EnvironmentName,
        base_time: datetime,
    ) -> list[VerificationCheckRecord]:
        """Create a running check suite (some passed, some running, some pending)."""
        checks_config = [
            ("API Health Check", VerificationType.HEALTH_CHECK, "/api/v1/health", "200 OK", 45.0, VerificationStatus.PASSED),
            ("Database Connectivity", VerificationType.HEALTH_CHECK, "/api/v1/health/db", "connected", 120.0, VerificationStatus.PASSED),
            ("Patient Endpoint Smoke", VerificationType.SMOKE_TEST, "/api/v1/patients", "200 OK", 230.0, VerificationStatus.PASSED),
            ("Trial Endpoint Smoke", VerificationType.SMOKE_TEST, "/api/v1/trials", "200 OK", None, VerificationStatus.RUNNING),
            ("Schema Validation", VerificationType.SCHEMA_VALIDATION, None, "all schemas valid", None, VerificationStatus.PENDING),
            ("Response Time P95", VerificationType.PERFORMANCE_CHECK, None, "< 500ms", None, VerificationStatus.PENDING),
            ("Data Integrity Check", VerificationType.DATA_INTEGRITY, None, "no orphaned records", None, VerificationStatus.PENDING),
            ("Rollback Readiness", VerificationType.ROLLBACK_READINESS, None, "rollback scripts verified", None, VerificationStatus.PENDING),
        ]
        results: list[VerificationCheckRecord] = []
        for i, (name, vtype, url, expected, dur, status) in enumerate(checks_config):
            actual = expected if status == VerificationStatus.PASSED else None
            c = VerificationCheckRecord(
                id=f"{prefix}-CHK-{i + 1:04d}",
                name=name,
                verification_type=vtype,
                description=f"{name} for {version} in {env.value}",
                expected_result=expected,
                actual_result=actual,
                status=status,
                duration_ms=dur,
                error_message=None,
                endpoint_url=url,
                created_at=base_time + timedelta(seconds=i * 30),
            )
            self._checks[c.id] = c
            results.append(c)
        return results

    # -------------------------------------------------------------------
    # Conversion helpers
    # -------------------------------------------------------------------

    def _check_to_schema(self, r: VerificationCheckRecord) -> VerificationCheck:
        return VerificationCheck(
            id=r.id, name=r.name, verification_type=r.verification_type,
            description=r.description, expected_result=r.expected_result,
            actual_result=r.actual_result, status=r.status,
            duration_ms=r.duration_ms, error_message=r.error_message,
            endpoint_url=r.endpoint_url, created_at=r.created_at,
        )

    def _verification_to_schema(self, r: DeploymentVerificationRecord) -> DeploymentVerification:
        checks = [self._check_to_schema(self._checks[cid]) for cid in r.check_ids if cid in self._checks]
        return DeploymentVerification(
            id=r.id, deployment_id=r.deployment_id, environment=r.environment,
            version=r.version, checks=checks, overall_status=r.overall_status,
            started_at=r.started_at, completed_at=r.completed_at,
            triggered_by=r.triggered_by, rollback_recommended=r.rollback_recommended,
        )

    def _contract_to_schema(self, r: APIContractRecord) -> APIContract:
        return APIContract(
            id=r.id, endpoint_path=r.endpoint_path, method=r.method,
            version=r.version, request_schema=r.request_schema,
            response_schema=r.response_schema, required_headers=r.required_headers,
            deprecated=r.deprecated, deprecated_date=r.deprecated_date,
            replacement_endpoint=r.replacement_endpoint,
            created_at=r.created_at, updated_at=r.updated_at,
        )

    def _contract_result_to_schema(self, r: ContractTestResultRecord) -> ContractTestResult:
        return ContractTestResult(
            id=r.id, contract_id=r.contract_id, test_type=r.test_type,
            status=r.status, details=r.details,
            breaking_changes=r.breaking_changes, created_at=r.created_at,
        )

    def _budget_to_schema(self, r: ErrorBudgetRecord) -> ErrorBudget:
        return ErrorBudget(
            id=r.id, service_name=r.service_name, sli_name=r.sli_name,
            target_percent=r.target_percent, current_percent=r.current_percent,
            remaining_budget_percent=r.remaining_budget_percent,
            status=r.status, burn_rate_per_hour=r.burn_rate_per_hour,
            time_to_exhaustion_hours=r.time_to_exhaustion_hours,
            window_start=r.window_start, window_end=r.window_end,
            violations=r.violations,
        )

    def _sli_to_schema(self, r: SLIDefinitionRecord) -> SLIDefinition:
        return SLIDefinition(
            id=r.id, service_name=r.service_name, sli_name=r.sli_name,
            description=r.description, target_percent=r.target_percent,
            measurement_query=r.measurement_query, window_hours=r.window_hours,
        )

    # ===================================================================
    # Deployment Verification CRUD
    # ===================================================================

    def list_verifications(
        self,
        environment: EnvironmentName | None = None,
        status: VerificationStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> DeploymentVerificationListResponse:
        """List deployment verifications with optional filters."""
        records = list(self._verifications.values())
        if environment:
            records = [r for r in records if r.environment == environment]
        if status:
            records = [r for r in records if r.overall_status == status]
        records.sort(key=lambda r: r.started_at, reverse=True)
        total = len(records)
        page = records[offset: offset + limit]
        return DeploymentVerificationListResponse(
            verifications=[self._verification_to_schema(r) for r in page],
            total=total, limit=limit, offset=offset,
        )

    def get_verification(self, verification_id: str) -> DeploymentVerification | None:
        """Get a single deployment verification by ID."""
        r = self._verifications.get(verification_id)
        return self._verification_to_schema(r) if r else None

    def create_verification(
        self,
        deployment_id: str,
        environment: EnvironmentName,
        version: str,
        triggered_by: str = "system",
    ) -> DeploymentVerification:
        """Create a new deployment verification run."""
        now = datetime.now(timezone.utc)
        rec = DeploymentVerificationRecord(
            deployment_id=deployment_id,
            environment=environment,
            version=version,
            overall_status=VerificationStatus.PENDING,
            started_at=now,
            triggered_by=triggered_by,
        )
        self._verifications[rec.id] = rec
        logger.info("Created deployment verification %s for %s in %s", rec.id, version, environment.value)
        return self._verification_to_schema(rec)

    def delete_verification(self, verification_id: str) -> bool:
        """Delete a deployment verification and its checks."""
        rec = self._verifications.pop(verification_id, None)
        if not rec:
            return False
        for cid in rec.check_ids:
            self._checks.pop(cid, None)
        return True

    # ===================================================================
    # Smoke Test Suite Execution
    # ===================================================================

    def run_smoke_tests(
        self,
        deployment_id: str,
        environment: EnvironmentName,
        version: str,
        endpoints: list[str] | None = None,
        triggered_by: str = "system",
    ) -> DeploymentVerification:
        """Run a simulated smoke test suite against known endpoints."""
        now = datetime.now(timezone.utc)

        default_endpoints = [
            "/api/v1/health",
            "/api/v1/health/db",
            "/api/v1/patients",
            "/api/v1/trials",
            "/api/v1/screening/results",
            "/api/v1/documents",
        ]
        target_endpoints = endpoints or default_endpoints

        rec = DeploymentVerificationRecord(
            deployment_id=deployment_id,
            environment=environment,
            version=version,
            overall_status=VerificationStatus.RUNNING,
            started_at=now,
            triggered_by=triggered_by,
        )

        all_passed = True
        for i, ep in enumerate(target_endpoints):
            # Simulate check
            passed = random.random() > 0.1  # 90% pass rate
            dur = random.uniform(30, 500)
            chk = VerificationCheckRecord(
                name=f"Smoke: {ep}",
                verification_type=VerificationType.SMOKE_TEST,
                description=f"Smoke test for {ep} in {environment.value}",
                expected_result="200 OK",
                actual_result="200 OK" if passed else "500 Internal Server Error",
                status=VerificationStatus.PASSED if passed else VerificationStatus.FAILED,
                duration_ms=dur,
                error_message=None if passed else f"Endpoint {ep} returned 500",
                endpoint_url=ep,
                created_at=now + timedelta(seconds=i * 2),
            )
            self._checks[chk.id] = chk
            rec.check_ids.append(chk.id)
            if not passed:
                all_passed = False

        rec.overall_status = VerificationStatus.PASSED if all_passed else VerificationStatus.FAILED
        rec.completed_at = datetime.now(timezone.utc)
        rec.rollback_recommended = not all_passed
        self._verifications[rec.id] = rec
        return self._verification_to_schema(rec)

    # ===================================================================
    # API Contract CRUD
    # ===================================================================

    def list_contracts(
        self,
        method: str | None = None,
        deprecated: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> APIContractListResponse:
        """List API contracts with optional filters."""
        records = list(self._contracts.values())
        if method:
            records = [r for r in records if r.method == method.upper()]
        if deprecated is not None:
            records = [r for r in records if r.deprecated == deprecated]
        records.sort(key=lambda r: r.endpoint_path)
        total = len(records)
        page = records[offset: offset + limit]
        return APIContractListResponse(
            contracts=[self._contract_to_schema(r) for r in page],
            total=total, limit=limit, offset=offset,
        )

    def get_contract(self, contract_id: str) -> APIContract | None:
        """Get a single API contract by ID."""
        r = self._contracts.get(contract_id)
        return self._contract_to_schema(r) if r else None

    def create_contract(self, data: APIContractCreate) -> APIContract:
        """Create a new API contract."""
        now = datetime.now(timezone.utc)
        rec = APIContractRecord(
            endpoint_path=data.endpoint_path,
            method=data.method.upper(),
            version=data.version,
            request_schema=data.request_schema,
            response_schema=data.response_schema,
            required_headers=data.required_headers,
            created_at=now,
            updated_at=now,
        )
        self._contracts[rec.id] = rec
        logger.info("Created API contract %s for %s %s", rec.id, rec.method, rec.endpoint_path)
        return self._contract_to_schema(rec)

    def update_contract(self, contract_id: str, data: APIContractUpdate) -> APIContract | None:
        """Update an existing API contract."""
        rec = self._contracts.get(contract_id)
        if not rec:
            return None
        now = datetime.now(timezone.utc)
        if data.endpoint_path is not None:
            rec.endpoint_path = data.endpoint_path
        if data.method is not None:
            rec.method = data.method.upper()
        if data.version is not None:
            rec.version = data.version
        if data.request_schema is not None:
            rec.request_schema = data.request_schema
        if data.response_schema is not None:
            rec.response_schema = data.response_schema
        if data.required_headers is not None:
            rec.required_headers = data.required_headers
        if data.deprecated is not None:
            rec.deprecated = data.deprecated
            if data.deprecated:
                rec.deprecated_date = now
        if data.replacement_endpoint is not None:
            rec.replacement_endpoint = data.replacement_endpoint
        rec.updated_at = now
        return self._contract_to_schema(rec)

    def delete_contract(self, contract_id: str) -> bool:
        """Delete an API contract."""
        return self._contracts.pop(contract_id, None) is not None

    # ===================================================================
    # Contract Testing
    # ===================================================================

    def list_contract_test_results(
        self,
        contract_id: str | None = None,
        status: VerificationStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ContractTestResultListResponse:
        """List contract test results with optional filters."""
        records = list(self._contract_results.values())
        if contract_id:
            records = [r for r in records if r.contract_id == contract_id]
        if status:
            records = [r for r in records if r.status == status]
        records.sort(key=lambda r: r.created_at, reverse=True)
        total = len(records)
        page = records[offset: offset + limit]
        return ContractTestResultListResponse(
            results=[self._contract_result_to_schema(r) for r in page],
            total=total, limit=limit, offset=offset,
        )

    def run_contract_test(
        self,
        contract_id: str,
        test_type: ContractTestType = ContractTestType.RESPONSE_SCHEMA,
    ) -> ContractTestResult | None:
        """Run a contract test against an existing contract."""
        contract = self._contracts.get(contract_id)
        if not contract:
            return None

        now = datetime.now(timezone.utc)
        breaking: list[BreakingChange] = []

        if test_type == ContractTestType.BREAKING_CHANGE:
            # Simulate schema diff - detect random breaking changes
            if random.random() > 0.6:
                breaking.append(BreakingChange(
                    field_path="$.data.new_field",
                    change_type="required_added",
                    old_value=None,
                    new_value="required",
                    severity="HIGH",
                ))
            status = VerificationStatus.FAILED if breaking else VerificationStatus.PASSED
            details = f"Breaking changes detected: {len(breaking)}" if breaking else "No breaking changes"
        elif test_type == ContractTestType.BACKWARD_COMPATIBILITY:
            passed = random.random() > 0.15
            status = VerificationStatus.PASSED if passed else VerificationStatus.FAILED
            details = "Backward compatible" if passed else "Backward compatibility broken"
        elif test_type == ContractTestType.DEPRECATION:
            status = VerificationStatus.PASSED
            details = f"Deprecated: {contract.deprecated}"
            if contract.deprecated:
                details += f", replacement: {contract.replacement_endpoint}"
        else:
            passed = random.random() > 0.1
            status = VerificationStatus.PASSED if passed else VerificationStatus.FAILED
            details = "Schema validation passed" if passed else "Schema validation failed"

        rec = ContractTestResultRecord(
            contract_id=contract_id,
            test_type=test_type,
            status=status,
            details=details,
            breaking_changes=breaking,
            created_at=now,
        )
        self._contract_results[rec.id] = rec
        return self._contract_result_to_schema(rec)

    def detect_breaking_changes(
        self,
        contract_id: str,
        new_schema: dict,
    ) -> list[BreakingChange]:
        """Detect breaking changes between current contract schema and a new schema."""
        contract = self._contracts.get(contract_id)
        if not contract or not contract.response_schema:
            return []

        changes: list[BreakingChange] = []
        old_props = contract.response_schema.get("properties", {})
        new_props = new_schema.get("properties", {})

        # Detect removed fields
        for field in old_props:
            if field not in new_props:
                changes.append(BreakingChange(
                    field_path=f"$.{field}",
                    change_type="removed",
                    old_value=old_props[field].get("type", "unknown"),
                    new_value=None,
                    severity="HIGH",
                ))

        # Detect type changes
        for field in old_props:
            if field in new_props:
                old_type = old_props[field].get("type")
                new_type = new_props[field].get("type")
                if old_type and new_type and old_type != new_type:
                    changes.append(BreakingChange(
                        field_path=f"$.{field}",
                        change_type="type_changed",
                        old_value=old_type,
                        new_value=new_type,
                        severity="HIGH",
                    ))

        # Detect new required fields
        old_required = set(contract.response_schema.get("required", []))
        new_required = set(new_schema.get("required", []))
        for field in new_required - old_required:
            changes.append(BreakingChange(
                field_path=f"$.{field}",
                change_type="required_added",
                old_value=None,
                new_value="required",
                severity="MEDIUM",
            ))

        return changes

    # ===================================================================
    # Error Budget CRUD
    # ===================================================================

    def list_error_budgets(
        self,
        service_name: str | None = None,
        status: ErrorBudgetStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ErrorBudgetListResponse:
        """List error budgets with optional filters."""
        records = list(self._error_budgets.values())
        if service_name:
            records = [r for r in records if r.service_name == service_name]
        if status:
            records = [r for r in records if r.status == status]
        records.sort(key=lambda r: r.service_name)
        total = len(records)
        page = records[offset: offset + limit]
        return ErrorBudgetListResponse(
            budgets=[self._budget_to_schema(r) for r in page],
            total=total, limit=limit, offset=offset,
        )

    def get_error_budget(self, budget_id: str) -> ErrorBudget | None:
        """Get a single error budget by ID."""
        r = self._error_budgets.get(budget_id)
        return self._budget_to_schema(r) if r else None

    def create_error_budget(self, data: ErrorBudgetCreate) -> ErrorBudget:
        """Create a new error budget."""
        now = datetime.now(timezone.utc)
        rec = ErrorBudgetRecord(
            service_name=data.service_name,
            sli_name=data.sli_name,
            target_percent=data.target_percent,
            current_percent=data.target_percent,  # starts at target
            remaining_budget_percent=100.0,
            status=ErrorBudgetStatus.HEALTHY,
            burn_rate_per_hour=0.0,
            time_to_exhaustion_hours=None,
            window_start=now,
            window_end=now + timedelta(hours=data.window_hours),
        )
        self._error_budgets[rec.id] = rec
        logger.info("Created error budget %s for %s/%s", rec.id, data.service_name, data.sli_name)
        return self._budget_to_schema(rec)

    def delete_error_budget(self, budget_id: str) -> bool:
        """Delete an error budget."""
        return self._error_budgets.pop(budget_id, None) is not None

    def calculate_burn_rate(self, budget_id: str) -> dict | None:
        """Calculate current burn rate for an error budget."""
        rec = self._error_budgets.get(budget_id)
        if not rec:
            return None

        # Simulated calculation
        allowed_error = 100.0 - rec.target_percent
        actual_error = 100.0 - rec.current_percent
        if allowed_error > 0:
            burn_rate = actual_error / allowed_error
        else:
            burn_rate = 0.0

        remaining = max(0.0, rec.remaining_budget_percent)
        if rec.burn_rate_per_hour > 0:
            tte = remaining / rec.burn_rate_per_hour
        else:
            tte = None

        return {
            "budget_id": budget_id,
            "burn_rate": round(burn_rate, 4),
            "burn_rate_per_hour": rec.burn_rate_per_hour,
            "remaining_budget_percent": remaining,
            "time_to_exhaustion_hours": round(tte, 1) if tte is not None else None,
            "status": rec.status.value,
        }

    # ===================================================================
    # SLI CRUD
    # ===================================================================

    def list_sli_definitions(
        self,
        service_name: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> SLIDefinitionListResponse:
        """List SLI definitions with optional filters."""
        records = list(self._sli_definitions.values())
        if service_name:
            records = [r for r in records if r.service_name == service_name]
        records.sort(key=lambda r: (r.service_name, r.sli_name))
        total = len(records)
        page = records[offset: offset + limit]
        return SLIDefinitionListResponse(
            definitions=[self._sli_to_schema(r) for r in page],
            total=total, limit=limit, offset=offset,
        )

    def get_sli_definition(self, sli_id: str) -> SLIDefinition | None:
        """Get a single SLI definition by ID."""
        r = self._sli_definitions.get(sli_id)
        return self._sli_to_schema(r) if r else None

    def create_sli_definition(self, data: SLIDefinitionCreate) -> SLIDefinition:
        """Create a new SLI definition."""
        rec = SLIDefinitionRecord(
            service_name=data.service_name,
            sli_name=data.sli_name,
            description=data.description,
            target_percent=data.target_percent,
            measurement_query=data.measurement_query,
            window_hours=data.window_hours,
        )
        self._sli_definitions[rec.id] = rec
        logger.info("Created SLI definition %s for %s/%s", rec.id, data.service_name, data.sli_name)
        return self._sli_to_schema(rec)

    def delete_sli_definition(self, sli_id: str) -> bool:
        """Delete an SLI definition."""
        return self._sli_definitions.pop(sli_id, None) is not None

    def measure_sli(self, sli_id: str) -> dict | None:
        """Simulate measuring an SLI and return current value."""
        rec = self._sli_definitions.get(sli_id)
        if not rec:
            return None

        # Simulated measurement
        simulated_value = rec.target_percent + random.uniform(-2.0, 1.0)
        simulated_value = min(100.0, max(0.0, simulated_value))
        meeting_target = simulated_value >= rec.target_percent

        return {
            "sli_id": sli_id,
            "service_name": rec.service_name,
            "sli_name": rec.sli_name,
            "target_percent": rec.target_percent,
            "current_value": round(simulated_value, 3),
            "meeting_target": meeting_target,
            "measured_at": datetime.now(timezone.utc).isoformat(),
        }

    # ===================================================================
    # Deployment Gate Evaluation
    # ===================================================================

    def evaluate_deployment_gate(
        self,
        deployment_id: str | None = None,
    ) -> DeploymentGateEvaluation:
        """Evaluate all deployment gates and return aggregate result."""
        now = datetime.now(timezone.utc)
        failing_checks: list[str] = []
        warnings: list[str] = []

        # 1. Latest verification status
        verifications = sorted(
            self._verifications.values(),
            key=lambda v: v.started_at,
            reverse=True,
        )
        if deployment_id:
            verifications = [v for v in verifications if v.deployment_id == deployment_id]

        latest_verification_status = VerificationStatus.PENDING
        if verifications:
            latest = verifications[0]
            latest_verification_status = latest.overall_status
            if latest.overall_status == VerificationStatus.FAILED:
                failing_checks.append(f"Verification {latest.id} FAILED")
            elif latest.overall_status == VerificationStatus.RUNNING:
                warnings.append(f"Verification {latest.id} still RUNNING")

        # 2. Contract test pass rate
        all_results = list(self._contract_results.values())
        if all_results:
            passed = sum(1 for r in all_results if r.status == VerificationStatus.PASSED)
            contract_pass_rate = (passed / len(all_results)) * 100.0
        else:
            contract_pass_rate = 100.0

        if contract_pass_rate < 90.0:
            failing_checks.append(f"Contract test pass rate {contract_pass_rate:.1f}% below 90% threshold")
        elif contract_pass_rate < 95.0:
            warnings.append(f"Contract test pass rate {contract_pass_rate:.1f}% below 95% ideal")

        # 3. Error budgets
        budgets = list(self._error_budgets.values())
        exhausted = [b for b in budgets if b.status == ErrorBudgetStatus.EXHAUSTED]
        critical = [b for b in budgets if b.status == ErrorBudgetStatus.CRITICAL]
        budgets_healthy = len(exhausted) == 0 and len(critical) == 0

        for b in exhausted:
            failing_checks.append(f"Error budget {b.service_name}/{b.sli_name} EXHAUSTED")
        for b in critical:
            warnings.append(f"Error budget {b.service_name}/{b.sli_name} CRITICAL")

        # Determine overall result
        if failing_checks:
            result = DeploymentGateResult.FAIL
        elif warnings:
            result = DeploymentGateResult.WARN
        else:
            result = DeploymentGateResult.PASS

        return DeploymentGateEvaluation(
            result=result,
            verification_status=latest_verification_status,
            contract_pass_rate=round(contract_pass_rate, 2),
            error_budgets_healthy=budgets_healthy,
            failing_checks=failing_checks,
            warnings=warnings,
            evaluated_at=now,
        )

    # ===================================================================
    # Historical Verification Trending
    # ===================================================================

    def get_verification_trends(self, days: int = 30) -> list[VerificationTrend]:
        """Get historical verification trending data."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=days)

        # Group verifications by date
        by_date: dict[str, dict] = {}
        for v in self._verifications.values():
            if v.started_at < cutoff:
                continue
            date_str = v.started_at.strftime("%Y-%m-%d")
            if date_str not in by_date:
                by_date[date_str] = {"total": 0, "passed": 0, "failed": 0}
            by_date[date_str]["total"] += 1
            if v.overall_status == VerificationStatus.PASSED:
                by_date[date_str]["passed"] += 1
            elif v.overall_status == VerificationStatus.FAILED:
                by_date[date_str]["failed"] += 1

        trends: list[VerificationTrend] = []
        for date_str in sorted(by_date.keys()):
            d = by_date[date_str]
            pass_rate = (d["passed"] / d["total"] * 100.0) if d["total"] > 0 else 0.0
            trends.append(VerificationTrend(
                date=date_str,
                total_verifications=d["total"],
                passed=d["passed"],
                failed=d["failed"],
                pass_rate=round(pass_rate, 2),
            ))
        return trends

    # ===================================================================
    # Metrics
    # ===================================================================

    def get_metrics(self) -> DeploymentVerificationMetrics:
        """Get aggregate deployment verification metrics."""
        verifications = list(self._verifications.values())
        total_v = len(verifications)
        passed_v = sum(1 for v in verifications if v.overall_status == VerificationStatus.PASSED)
        pass_rate = (passed_v / total_v * 100.0) if total_v > 0 else 0.0

        # Average verification time
        completed = [v for v in verifications if v.completed_at]
        if completed:
            total_ms = sum(
                (v.completed_at - v.started_at).total_seconds() * 1000
                for v in completed
                if v.completed_at
            )
            avg_time = total_ms / len(completed)
        else:
            avg_time = 0.0

        # Contract metrics
        total_contracts = len(self._contracts)
        all_results = list(self._contract_results.values())
        passed_results = sum(1 for r in all_results if r.status == VerificationStatus.PASSED)
        contract_pass_rate = (passed_results / len(all_results) * 100.0) if all_results else 0.0
        breaking_changes = sum(len(r.breaking_changes) for r in all_results)

        # Error budget metrics
        budgets = list(self._error_budgets.values())
        budgets_healthy = sum(1 for b in budgets if b.status == ErrorBudgetStatus.HEALTHY)
        budgets_total = len(budgets)

        trends = self.get_verification_trends(days=30)

        return DeploymentVerificationMetrics(
            total_verifications=total_v,
            pass_rate=round(pass_rate, 2),
            avg_verification_time_ms=round(avg_time, 2),
            total_contracts=total_contracts,
            contract_test_pass_rate=round(contract_pass_rate, 2),
            breaking_changes_detected=breaking_changes,
            error_budgets_healthy=budgets_healthy,
            error_budgets_total=budgets_total,
            recent_trends=trends,
        )


# ---------------------------------------------------------------------------
# Singleton accessors
# ---------------------------------------------------------------------------


def get_deployment_verification_service() -> DeploymentVerificationService:
    """Get or create the singleton DeploymentVerificationService."""
    global _dv_instance
    if _dv_instance is None:
        with _dv_lock:
            if _dv_instance is None:
                _dv_instance = DeploymentVerificationService()
                logger.info("DeploymentVerificationService singleton created")
    return _dv_instance


def reset_deployment_verification_service() -> None:
    """Reset the singleton (for testing)."""
    global _dv_instance
    with _dv_lock:
        _dv_instance = None
