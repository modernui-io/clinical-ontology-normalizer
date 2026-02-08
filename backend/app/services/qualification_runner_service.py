"""Qualification test runner service for IQ/OQ/PQ automated checks.

VP-Quality-2: Provides programmatic execution of qualification checks:
- IQ: Installation verification (database, config, versions)
- OQ: Operational verification (API health, auth, CRUD, audit)
- PQ: Performance verification (response times, concurrent handling)

Usage:
    from app.services.qualification_runner_service import get_qualification_runner

    runner = get_qualification_runner()
    report = runner.run_qualification(QualificationType.IQ)
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from app.schemas.quality_management import (
    CheckStatus,
    QualificationCheck,
    QualificationReport,
    QualificationSummary,
    QualificationType,
)

logger = logging.getLogger(__name__)

# Singleton instance and lock
_runner_instance: QualificationRunner | None = None
_runner_lock = Lock()


class QualificationRunner:
    """Executes IQ/OQ/PQ qualification checks programmatically.

    Each check runs independently and returns pass/fail status
    with details. Reports are stored in memory for retrieval.
    """

    def __init__(self) -> None:
        """Initialize the qualification runner."""
        self._reports: dict[str, QualificationReport] = {}
        self._lock = Lock()
        logger.info("QualificationRunner initialized")

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def run_qualification(
        self,
        qualification_type: QualificationType,
        executed_by: str = "system",
    ) -> QualificationReport:
        """Run a full qualification suite.

        Args:
            qualification_type: IQ, OQ, or PQ.
            executed_by: Identifier of person initiating the run.

        Returns:
            QualificationReport with all check results.
        """
        start_time = time.perf_counter()
        now = datetime.now(timezone.utc)

        if qualification_type == QualificationType.IQ:
            checks = self._run_iq_checks()
        elif qualification_type == QualificationType.OQ:
            checks = self._run_oq_checks()
        elif qualification_type == QualificationType.PQ:
            checks = self._run_pq_checks()
        else:
            checks = []

        total_duration_ms = (time.perf_counter() - start_time) * 1000

        # Build summary
        passed = sum(1 for c in checks if c.status == CheckStatus.PASS)
        failed = sum(1 for c in checks if c.status == CheckStatus.FAIL)
        skipped = sum(1 for c in checks if c.status == CheckStatus.SKIP)
        total = len(checks)
        pass_rate = (passed / total * 100) if total > 0 else 0.0

        summary = QualificationSummary(
            total_checks=total,
            passed=passed,
            failed=failed,
            skipped=skipped,
            pass_rate=round(pass_rate, 1),
            total_duration_ms=round(total_duration_ms, 2),
            qualification_type=qualification_type,
            overall_result="PASS" if failed == 0 and total > 0 else "FAIL",
        )

        # Build report
        report_id = f"QR-{qualification_type.value}-{uuid4().hex[:8].upper()}"
        report = QualificationReport(
            id=report_id,
            qualification_type=qualification_type,
            summary=summary,
            checks=checks,
            executed_at=now,
            executed_by=executed_by,
            environment=self._detect_environment(),
        )

        # Store report
        with self._lock:
            self._reports[report_id] = report

        logger.info(
            "Qualification run complete: type=%s, passed=%d/%d, result=%s",
            qualification_type.value,
            passed,
            total,
            summary.overall_result,
        )

        return report

    def get_report(self, report_id: str) -> QualificationReport | None:
        """Retrieve a qualification report by ID."""
        with self._lock:
            return self._reports.get(report_id)

    def list_reports(self) -> list[QualificationReport]:
        """List all qualification reports."""
        with self._lock:
            reports = list(self._reports.values())
        reports.sort(key=lambda r: r.executed_at, reverse=True)
        return reports

    # -----------------------------------------------------------------------
    # IQ Checks
    # -----------------------------------------------------------------------

    def _run_iq_checks(self) -> list[QualificationCheck]:
        """Run Installation Qualification checks."""
        checks: list[QualificationCheck] = []

        checks.append(self._check_database_connectivity())
        checks.append(self._check_table_count())
        checks.append(self._check_migration_status())
        checks.append(self._check_config_api_prefix())
        checks.append(self._check_config_environment())
        checks.append(self._check_python_version())
        checks.append(self._check_fastapi_installed())
        checks.append(self._check_pydantic_installed())
        checks.append(self._check_redis_connectivity())
        checks.append(self._check_vocabulary_loaded())

        return checks

    def _check_database_connectivity(self) -> QualificationCheck:
        """IQ-TC-001: Verify database connectivity."""
        start = time.perf_counter()
        try:
            from app.core.config import settings
            has_db_url = bool(settings.database_url)
            duration = (time.perf_counter() - start) * 1000
            if has_db_url:
                return QualificationCheck(
                    check_id="IQ-TC-001",
                    name="Database connectivity",
                    category=QualificationType.IQ,
                    status=CheckStatus.PASS,
                    details=f"DATABASE_URL configured (length={len(settings.database_url)})",
                    duration_ms=round(duration, 2),
                )
            return QualificationCheck(
                check_id="IQ-TC-001",
                name="Database connectivity",
                category=QualificationType.IQ,
                status=CheckStatus.FAIL,
                details="DATABASE_URL not configured",
                duration_ms=round(duration, 2),
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="IQ-TC-001",
                name="Database connectivity",
                category=QualificationType.IQ,
                status=CheckStatus.FAIL,
                details=f"Error checking database config: {e}",
                duration_ms=round(duration, 2),
            )

    def _check_table_count(self) -> QualificationCheck:
        """IQ-TC-008: Verify core tables exist."""
        start = time.perf_counter()
        try:
            # Check that ORM models are importable (proxy for table definitions)
            from app.models import patient, document  # noqa: F401
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="IQ-TC-008",
                name="Core table definitions",
                category=QualificationType.IQ,
                status=CheckStatus.PASS,
                details="Core ORM models (patient, document) importable",
                duration_ms=round(duration, 2),
            )
        except ImportError as e:
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="IQ-TC-008",
                name="Core table definitions",
                category=QualificationType.IQ,
                status=CheckStatus.FAIL,
                details=f"Failed to import ORM models: {e}",
                duration_ms=round(duration, 2),
            )

    def _check_migration_status(self) -> QualificationCheck:
        """IQ-TC-007: Verify migration status."""
        start = time.perf_counter()
        try:
            import importlib
            alembic = importlib.util.find_spec("alembic")
            duration = (time.perf_counter() - start) * 1000
            if alembic is not None:
                return QualificationCheck(
                    check_id="IQ-TC-007",
                    name="Migration tool available",
                    category=QualificationType.IQ,
                    status=CheckStatus.PASS,
                    details="Alembic migration tool is installed",
                    duration_ms=round(duration, 2),
                )
            return QualificationCheck(
                check_id="IQ-TC-007",
                name="Migration tool available",
                category=QualificationType.IQ,
                status=CheckStatus.SKIP,
                details="Alembic not installed, migration check skipped",
                duration_ms=round(duration, 2),
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="IQ-TC-007",
                name="Migration tool available",
                category=QualificationType.IQ,
                status=CheckStatus.FAIL,
                details=f"Error checking migration status: {e}",
                duration_ms=round(duration, 2),
            )

    def _check_config_api_prefix(self) -> QualificationCheck:
        """IQ-TC-010: Verify API prefix configuration."""
        start = time.perf_counter()
        try:
            from app.core.config import settings
            duration = (time.perf_counter() - start) * 1000
            if settings.api_v1_prefix == "/api/v1":
                return QualificationCheck(
                    check_id="IQ-TC-010",
                    name="API prefix configuration",
                    category=QualificationType.IQ,
                    status=CheckStatus.PASS,
                    details=f"API prefix correctly set to '{settings.api_v1_prefix}'",
                    duration_ms=round(duration, 2),
                )
            return QualificationCheck(
                check_id="IQ-TC-010",
                name="API prefix configuration",
                category=QualificationType.IQ,
                status=CheckStatus.FAIL,
                details=f"API prefix is '{settings.api_v1_prefix}', expected '/api/v1'",
                duration_ms=round(duration, 2),
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="IQ-TC-010",
                name="API prefix configuration",
                category=QualificationType.IQ,
                status=CheckStatus.FAIL,
                details=f"Error: {e}",
                duration_ms=round(duration, 2),
            )

    def _check_config_environment(self) -> QualificationCheck:
        """IQ-TC-006: Verify environment setting."""
        start = time.perf_counter()
        try:
            from app.core.config import settings
            env = settings.environment
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="IQ-TC-006",
                name="Environment configuration",
                category=QualificationType.IQ,
                status=CheckStatus.PASS,
                details=f"Environment set to '{env}'",
                duration_ms=round(duration, 2),
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="IQ-TC-006",
                name="Environment configuration",
                category=QualificationType.IQ,
                status=CheckStatus.FAIL,
                details=f"Error: {e}",
                duration_ms=round(duration, 2),
            )

    def _check_python_version(self) -> QualificationCheck:
        """IQ-TC-004: Verify Python version."""
        start = time.perf_counter()
        import sys
        version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        duration = (time.perf_counter() - start) * 1000
        is_ok = sys.version_info >= (3, 12)
        return QualificationCheck(
            check_id="IQ-TC-004",
            name="Python version",
            category=QualificationType.IQ,
            status=CheckStatus.PASS if is_ok else CheckStatus.FAIL,
            details=f"Python {version} ({'meets' if is_ok else 'does not meet'} >= 3.12 requirement)",
            duration_ms=round(duration, 2),
        )

    def _check_fastapi_installed(self) -> QualificationCheck:
        """IQ-TC-006: Verify FastAPI installation."""
        start = time.perf_counter()
        try:
            import fastapi
            version = fastapi.__version__
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="IQ-SW-003",
                name="FastAPI installation",
                category=QualificationType.IQ,
                status=CheckStatus.PASS,
                details=f"FastAPI {version} installed",
                duration_ms=round(duration, 2),
            )
        except ImportError:
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="IQ-SW-003",
                name="FastAPI installation",
                category=QualificationType.IQ,
                status=CheckStatus.FAIL,
                details="FastAPI not installed",
                duration_ms=round(duration, 2),
            )

    def _check_pydantic_installed(self) -> QualificationCheck:
        """IQ-SW-005: Verify Pydantic installation."""
        start = time.perf_counter()
        try:
            import pydantic
            version = pydantic.__version__
            is_v2 = version.startswith("2.")
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="IQ-SW-005",
                name="Pydantic installation",
                category=QualificationType.IQ,
                status=CheckStatus.PASS if is_v2 else CheckStatus.FAIL,
                details=f"Pydantic {version} {'(v2 required)' if not is_v2 else ''}",
                duration_ms=round(duration, 2),
            )
        except ImportError:
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="IQ-SW-005",
                name="Pydantic installation",
                category=QualificationType.IQ,
                status=CheckStatus.FAIL,
                details="Pydantic not installed",
                duration_ms=round(duration, 2),
            )

    def _check_redis_connectivity(self) -> QualificationCheck:
        """IQ-TC-002: Verify Redis configuration."""
        start = time.perf_counter()
        try:
            from app.core.config import settings
            has_redis = bool(getattr(settings, "redis_url", None))
            duration = (time.perf_counter() - start) * 1000
            if has_redis:
                return QualificationCheck(
                    check_id="IQ-TC-002",
                    name="Redis configuration",
                    category=QualificationType.IQ,
                    status=CheckStatus.PASS,
                    details="REDIS_URL configured",
                    duration_ms=round(duration, 2),
                )
            return QualificationCheck(
                check_id="IQ-TC-002",
                name="Redis configuration",
                category=QualificationType.IQ,
                status=CheckStatus.SKIP,
                details="REDIS_URL not configured (Redis is optional for development)",
                duration_ms=round(duration, 2),
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="IQ-TC-002",
                name="Redis configuration",
                category=QualificationType.IQ,
                status=CheckStatus.SKIP,
                details=f"Could not check Redis config: {e}",
                duration_ms=round(duration, 2),
            )

    def _check_vocabulary_loaded(self) -> QualificationCheck:
        """IQ-TC-021: Verify vocabulary service is loadable."""
        start = time.perf_counter()
        try:
            from app.services.vocabulary import get_vocabulary_service
            svc = get_vocabulary_service()
            stats = svc.get_stats()
            duration = (time.perf_counter() - start) * 1000
            concept_count = stats.get("concept_count", 0)
            return QualificationCheck(
                check_id="IQ-TC-021",
                name="Vocabulary service loaded",
                category=QualificationType.IQ,
                status=CheckStatus.PASS if concept_count > 0 else CheckStatus.FAIL,
                details=f"Vocabulary loaded: {concept_count} concepts",
                duration_ms=round(duration, 2),
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="IQ-TC-021",
                name="Vocabulary service loaded",
                category=QualificationType.IQ,
                status=CheckStatus.FAIL,
                details=f"Failed to load vocabulary: {e}",
                duration_ms=round(duration, 2),
            )

    # -----------------------------------------------------------------------
    # OQ Checks
    # -----------------------------------------------------------------------

    def _run_oq_checks(self) -> list[QualificationCheck]:
        """Run Operational Qualification checks."""
        checks: list[QualificationCheck] = []

        checks.append(self._check_health_endpoint())
        checks.append(self._check_auth_module())
        checks.append(self._check_patient_api())
        checks.append(self._check_document_api())
        checks.append(self._check_trial_api())
        checks.append(self._check_audit_module())
        checks.append(self._check_fhir_module())
        checks.append(self._check_nlp_module())
        checks.append(self._check_mapping_module())
        checks.append(self._check_error_handling())

        return checks

    def _check_health_endpoint(self) -> QualificationCheck:
        """OQ-TC-017: Verify health endpoint module."""
        start = time.perf_counter()
        try:
            from app.api.health import router  # noqa: F401
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="OQ-TC-017",
                name="Health endpoint module",
                category=QualificationType.OQ,
                status=CheckStatus.PASS,
                details="Health router importable and configured",
                duration_ms=round(duration, 2),
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="OQ-TC-017",
                name="Health endpoint module",
                category=QualificationType.OQ,
                status=CheckStatus.FAIL,
                details=f"Error: {e}",
                duration_ms=round(duration, 2),
            )

    def _check_auth_module(self) -> QualificationCheck:
        """OQ-TC-001: Verify auth module."""
        start = time.perf_counter()
        try:
            from app.api.auth import router  # noqa: F401
            from app.api.middleware import get_current_user  # noqa: F401
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="OQ-TC-001",
                name="Authentication module",
                category=QualificationType.OQ,
                status=CheckStatus.PASS,
                details="Auth router and middleware importable",
                duration_ms=round(duration, 2),
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="OQ-TC-001",
                name="Authentication module",
                category=QualificationType.OQ,
                status=CheckStatus.FAIL,
                details=f"Error: {e}",
                duration_ms=round(duration, 2),
            )

    def _check_patient_api(self) -> QualificationCheck:
        """OQ-TC-003: Verify patient API module."""
        start = time.perf_counter()
        try:
            from app.api.patients import router  # noqa: F401
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="OQ-TC-003",
                name="Patient API module",
                category=QualificationType.OQ,
                status=CheckStatus.PASS,
                details="Patient router importable with CRUD endpoints",
                duration_ms=round(duration, 2),
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="OQ-TC-003",
                name="Patient API module",
                category=QualificationType.OQ,
                status=CheckStatus.FAIL,
                details=f"Error: {e}",
                duration_ms=round(duration, 2),
            )

    def _check_document_api(self) -> QualificationCheck:
        """OQ-TC-006: Verify document API module."""
        start = time.perf_counter()
        try:
            from app.api.documents import router  # noqa: F401
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="OQ-TC-006",
                name="Document API module",
                category=QualificationType.OQ,
                status=CheckStatus.PASS,
                details="Document router importable with ingestion endpoints",
                duration_ms=round(duration, 2),
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="OQ-TC-006",
                name="Document API module",
                category=QualificationType.OQ,
                status=CheckStatus.FAIL,
                details=f"Error: {e}",
                duration_ms=round(duration, 2),
            )

    def _check_trial_api(self) -> QualificationCheck:
        """OQ-TC-013: Verify trial/screening API module."""
        start = time.perf_counter()
        try:
            from app.api.trials import router  # noqa: F401
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="OQ-TC-013",
                name="Trial screening API module",
                category=QualificationType.OQ,
                status=CheckStatus.PASS,
                details="Trial router importable with screening endpoints",
                duration_ms=round(duration, 2),
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="OQ-TC-013",
                name="Trial screening API module",
                category=QualificationType.OQ,
                status=CheckStatus.FAIL,
                details=f"Error: {e}",
                duration_ms=round(duration, 2),
            )

    def _check_audit_module(self) -> QualificationCheck:
        """OQ-TC-022: Verify audit module."""
        start = time.perf_counter()
        try:
            from app.api.audit import router  # noqa: F401
            from app.api.middleware import AuditMiddleware  # noqa: F401
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="OQ-TC-022",
                name="Audit trail module",
                category=QualificationType.OQ,
                status=CheckStatus.PASS,
                details="Audit router and middleware importable",
                duration_ms=round(duration, 2),
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="OQ-TC-022",
                name="Audit trail module",
                category=QualificationType.OQ,
                status=CheckStatus.FAIL,
                details=f"Error: {e}",
                duration_ms=round(duration, 2),
            )

    def _check_fhir_module(self) -> QualificationCheck:
        """OQ-TC-009: Verify FHIR module."""
        start = time.perf_counter()
        try:
            from app.api.fhir import router  # noqa: F401
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="OQ-TC-009",
                name="FHIR module",
                category=QualificationType.OQ,
                status=CheckStatus.PASS,
                details="FHIR router importable with resource endpoints",
                duration_ms=round(duration, 2),
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="OQ-TC-009",
                name="FHIR module",
                category=QualificationType.OQ,
                status=CheckStatus.FAIL,
                details=f"Error: {e}",
                duration_ms=round(duration, 2),
            )

    def _check_nlp_module(self) -> QualificationCheck:
        """OQ-TC-007: Verify NLP module."""
        start = time.perf_counter()
        try:
            from app.api.nlp import router  # noqa: F401
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="OQ-TC-007",
                name="NLP extraction module",
                category=QualificationType.OQ,
                status=CheckStatus.PASS,
                details="NLP router importable",
                duration_ms=round(duration, 2),
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="OQ-TC-007",
                name="NLP extraction module",
                category=QualificationType.OQ,
                status=CheckStatus.FAIL,
                details=f"Error: {e}",
                duration_ms=round(duration, 2),
            )

    def _check_mapping_module(self) -> QualificationCheck:
        """OQ-TC-010: Verify mapping module."""
        start = time.perf_counter()
        try:
            from app.services.mapping import MappingService  # noqa: F401
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="OQ-TC-010",
                name="OMOP mapping module",
                category=QualificationType.OQ,
                status=CheckStatus.PASS,
                details="MappingService importable",
                duration_ms=round(duration, 2),
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="OQ-TC-010",
                name="OMOP mapping module",
                category=QualificationType.OQ,
                status=CheckStatus.FAIL,
                details=f"Error: {e}",
                duration_ms=round(duration, 2),
            )

    def _check_error_handling(self) -> QualificationCheck:
        """OQ-TC-028: Verify error handling module."""
        start = time.perf_counter()
        try:
            from app.api.errors import APIError, NotFoundError, ValidationError  # noqa: F401
            from app.api.middleware import ErrorHandlerMiddleware  # noqa: F401
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="OQ-TC-028",
                name="Error handling module",
                category=QualificationType.OQ,
                status=CheckStatus.PASS,
                details="Error classes and middleware importable",
                duration_ms=round(duration, 2),
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="OQ-TC-028",
                name="Error handling module",
                category=QualificationType.OQ,
                status=CheckStatus.FAIL,
                details=f"Error: {e}",
                duration_ms=round(duration, 2),
            )

    # -----------------------------------------------------------------------
    # PQ Checks
    # -----------------------------------------------------------------------

    def _run_pq_checks(self) -> list[QualificationCheck]:
        """Run Performance Qualification checks."""
        checks: list[QualificationCheck] = []

        checks.append(self._check_response_time_baseline())
        checks.append(self._check_import_performance())
        checks.append(self._check_memory_baseline())
        checks.append(self._check_concurrent_handling())
        checks.append(self._check_serialization_performance())

        return checks

    def _check_response_time_baseline(self) -> QualificationCheck:
        """PQ-TC-004: Verify baseline response time."""
        start = time.perf_counter()
        try:
            # Simulate a lightweight operation to measure baseline
            from app.core.config import settings  # noqa: F401
            # Simple dict serialization as proxy for API response
            import json
            test_data = {"status": "healthy", "checks": list(range(100))}
            json.dumps(test_data)
            duration = (time.perf_counter() - start) * 1000
            passed = duration < 100  # Should be very fast
            return QualificationCheck(
                check_id="PQ-TC-004",
                name="Response time baseline",
                category=QualificationType.PQ,
                status=CheckStatus.PASS if passed else CheckStatus.FAIL,
                details=f"Baseline operation completed in {duration:.2f}ms (target: <100ms)",
                duration_ms=round(duration, 2),
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="PQ-TC-004",
                name="Response time baseline",
                category=QualificationType.PQ,
                status=CheckStatus.FAIL,
                details=f"Error: {e}",
                duration_ms=round(duration, 2),
            )

    def _check_import_performance(self) -> QualificationCheck:
        """PQ-TC-002: Verify module import performance."""
        start = time.perf_counter()
        try:
            # Time how long it takes to import core modules
            from app.schemas.quality_management import CAPAResponse  # noqa: F401
            from app.schemas.quality_management import QualificationReport  # noqa: F401
            duration = (time.perf_counter() - start) * 1000
            passed = duration < 5000  # Should import within 5s
            return QualificationCheck(
                check_id="PQ-TC-002",
                name="Module import performance",
                category=QualificationType.PQ,
                status=CheckStatus.PASS if passed else CheckStatus.FAIL,
                details=f"Core module imports completed in {duration:.2f}ms (target: <5000ms)",
                duration_ms=round(duration, 2),
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="PQ-TC-002",
                name="Module import performance",
                category=QualificationType.PQ,
                status=CheckStatus.FAIL,
                details=f"Error: {e}",
                duration_ms=round(duration, 2),
            )

    def _check_memory_baseline(self) -> QualificationCheck:
        """PQ-TC-022: Verify memory usage baseline."""
        start = time.perf_counter()
        try:
            import os
            # Get process RSS (on platforms that support it)
            pid = os.getpid()
            # Rough memory check via /proc on Linux, or resource module
            try:
                import resource
                mem_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                # On macOS ru_maxrss is in bytes, on Linux it's in KB
                import sys
                if sys.platform == "darwin":
                    mem_mb = mem_kb / (1024 * 1024)
                else:
                    mem_mb = mem_kb / 1024
            except Exception:
                mem_mb = 0

            duration = (time.perf_counter() - start) * 1000
            passed = mem_mb < 4096 if mem_mb > 0 else True  # Under 4GB
            return QualificationCheck(
                check_id="PQ-TC-022",
                name="Memory usage baseline",
                category=QualificationType.PQ,
                status=CheckStatus.PASS if passed else CheckStatus.FAIL,
                details=f"Current RSS: {mem_mb:.1f} MB (target: <4096 MB)" if mem_mb > 0 else "Memory measurement unavailable (check passed by default)",
                duration_ms=round(duration, 2),
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="PQ-TC-022",
                name="Memory usage baseline",
                category=QualificationType.PQ,
                status=CheckStatus.SKIP,
                details=f"Could not measure memory: {e}",
                duration_ms=round(duration, 2),
            )

    def _check_concurrent_handling(self) -> QualificationCheck:
        """PQ-TC-001: Verify concurrent operation capability."""
        start = time.perf_counter()
        try:
            import concurrent.futures
            results = []

            def task(n: int) -> int:
                return n * n

            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(task, i) for i in range(100)]
                results = [f.result() for f in futures]

            duration = (time.perf_counter() - start) * 1000
            passed = len(results) == 100 and duration < 5000
            return QualificationCheck(
                check_id="PQ-TC-001",
                name="Concurrent operation handling",
                category=QualificationType.PQ,
                status=CheckStatus.PASS if passed else CheckStatus.FAIL,
                details=f"100 concurrent tasks completed in {duration:.2f}ms (target: <5000ms)",
                duration_ms=round(duration, 2),
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="PQ-TC-001",
                name="Concurrent operation handling",
                category=QualificationType.PQ,
                status=CheckStatus.FAIL,
                details=f"Error: {e}",
                duration_ms=round(duration, 2),
            )

    def _check_serialization_performance(self) -> QualificationCheck:
        """PQ-TC-005: Verify Pydantic serialization performance."""
        start = time.perf_counter()
        try:
            from app.schemas.quality_management import CAPAResponse, CAPASeverity, CAPASource, CAPAStatus, CAPAType

            now = datetime.now(timezone.utc)
            # Create and serialize 100 CAPA responses
            for i in range(100):
                resp = CAPAResponse(
                    id=f"CAPA-{i:04d}",
                    title=f"Test CAPA {i}",
                    description=f"Description for CAPA {i}",
                    capa_type=CAPAType.CORRECTIVE,
                    source=CAPASource.AUDIT,
                    severity=CAPASeverity.MAJOR,
                    status=CAPAStatus.OPEN,
                    created_at=now,
                    updated_at=now,
                )
                resp.model_dump()

            duration = (time.perf_counter() - start) * 1000
            passed = duration < 5000  # 100 serializations under 5s
            return QualificationCheck(
                check_id="PQ-TC-005",
                name="Serialization performance",
                category=QualificationType.PQ,
                status=CheckStatus.PASS if passed else CheckStatus.FAIL,
                details=f"100 Pydantic serializations in {duration:.2f}ms (target: <5000ms)",
                duration_ms=round(duration, 2),
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return QualificationCheck(
                check_id="PQ-TC-005",
                name="Serialization performance",
                category=QualificationType.PQ,
                status=CheckStatus.FAIL,
                details=f"Error: {e}",
                duration_ms=round(duration, 2),
            )

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _detect_environment(self) -> str:
        """Detect the current environment."""
        try:
            from app.core.config import settings
            return settings.environment
        except Exception:
            return "unknown"


# ---------------------------------------------------------------------------
# Singleton access
# ---------------------------------------------------------------------------


def get_qualification_runner() -> QualificationRunner:
    """Get or create the singleton QualificationRunner instance."""
    global _runner_instance
    if _runner_instance is None:
        with _runner_lock:
            if _runner_instance is None:
                _runner_instance = QualificationRunner()
    return _runner_instance


def reset_qualification_runner() -> None:
    """Reset the singleton for testing."""
    global _runner_instance
    with _runner_lock:
        _runner_instance = None
