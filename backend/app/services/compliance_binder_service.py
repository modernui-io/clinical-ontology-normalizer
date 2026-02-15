"""Compliance Evidence Binder Automation Service (P3-024).

Automates the collection and organization of compliance evidence for audits.
Produces a structured binder with categorized evidence items, tracks collection
status, and reports overall completeness.

Categories:
- security_controls
- access_management
- audit_logs
- data_protection
- incident_response
- change_management
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


# ============================================================================
# Enums
# ============================================================================


class EvidenceCategory(str, Enum):
    """Categories of compliance evidence."""

    SECURITY_CONTROLS = "security_controls"
    ACCESS_MANAGEMENT = "access_management"
    AUDIT_LOGS = "audit_logs"
    DATA_PROTECTION = "data_protection"
    INCIDENT_RESPONSE = "incident_response"
    CHANGE_MANAGEMENT = "change_management"


class EvidenceStatus(str, Enum):
    """Collection status of an evidence item."""

    COLLECTED = "collected"
    PENDING = "pending"
    MISSING = "missing"


# ============================================================================
# Data Models
# ============================================================================


@dataclass
class EvidenceItem:
    """A single piece of compliance evidence."""

    category: EvidenceCategory
    title: str
    description: str
    artifact_path: str
    collected_at: str  # ISO datetime or empty
    status: EvidenceStatus


@dataclass
class ComplianceBinder:
    """A compliance evidence binder for audit."""

    binder_id: str
    created_at: str
    items: list[EvidenceItem] = field(default_factory=list)
    completeness_percent: float = 0.0


@dataclass
class BinderSummary:
    """Summary of a compliance binder."""

    binder_id: str
    created_at: str
    total_items: int
    collected: int
    pending: int
    missing: int
    completeness_percent: float
    by_category: dict[str, dict[str, int]] = field(default_factory=dict)


# ============================================================================
# Evidence Collectors
# ============================================================================


def _check_file_exists(path: str) -> bool:
    """Check if an artifact file or directory exists."""
    return os.path.exists(path)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _collect_security_controls() -> list[EvidenceItem]:
    """Collect evidence for security controls."""
    items = []

    # TLS / HTTPS configuration
    nginx_conf = "nginx/nginx.conf"
    items.append(EvidenceItem(
        category=EvidenceCategory.SECURITY_CONTROLS,
        title="TLS/HTTPS Configuration",
        description="NGINX configuration showing TLS termination and HTTPS enforcement.",
        artifact_path=nginx_conf,
        collected_at=_now_iso() if _check_file_exists(nginx_conf) else "",
        status=EvidenceStatus.COLLECTED if _check_file_exists(nginx_conf) else EvidenceStatus.MISSING,
    ))

    # CORS policy
    config_path = "backend/app/core/config.py"
    items.append(EvidenceItem(
        category=EvidenceCategory.SECURITY_CONTROLS,
        title="CORS Policy Configuration",
        description="Application config showing CORS origin restrictions.",
        artifact_path=config_path,
        collected_at=_now_iso() if _check_file_exists(config_path) else "",
        status=EvidenceStatus.COLLECTED if _check_file_exists(config_path) else EvidenceStatus.MISSING,
    ))

    # Input validation service
    validation_path = "backend/app/services/input_validation.py"
    items.append(EvidenceItem(
        category=EvidenceCategory.SECURITY_CONTROLS,
        title="Input Validation Service",
        description="Service implementing input validation and sanitization.",
        artifact_path=validation_path,
        collected_at=_now_iso() if _check_file_exists(validation_path) else "",
        status=EvidenceStatus.COLLECTED if _check_file_exists(validation_path) else EvidenceStatus.MISSING,
    ))

    return items


def _collect_access_management() -> list[EvidenceItem]:
    """Collect evidence for access management controls."""
    items = []

    # RBAC service
    rbac_path = "backend/app/services/rbac_service.py"
    items.append(EvidenceItem(
        category=EvidenceCategory.ACCESS_MANAGEMENT,
        title="RBAC Service Implementation",
        description="Role-based access control service with permission management.",
        artifact_path=rbac_path,
        collected_at=_now_iso() if _check_file_exists(rbac_path) else "",
        status=EvidenceStatus.COLLECTED if _check_file_exists(rbac_path) else EvidenceStatus.MISSING,
    ))

    # Tenant isolation
    tenant_path = "backend/app/core/tenant.py"
    items.append(EvidenceItem(
        category=EvidenceCategory.ACCESS_MANAGEMENT,
        title="Multi-Tenant Isolation",
        description="Tenant isolation enforcing patient-level access boundaries.",
        artifact_path=tenant_path,
        collected_at=_now_iso() if _check_file_exists(tenant_path) else "",
        status=EvidenceStatus.COLLECTED if _check_file_exists(tenant_path) else EvidenceStatus.MISSING,
    ))

    # RBAC tests
    rbac_test_path = "backend/tests/test_rbac.py"
    items.append(EvidenceItem(
        category=EvidenceCategory.ACCESS_MANAGEMENT,
        title="RBAC Test Results",
        description="Test suite verifying role-based access control enforcement.",
        artifact_path=rbac_test_path,
        collected_at=_now_iso() if _check_file_exists(rbac_test_path) else "",
        status=EvidenceStatus.COLLECTED if _check_file_exists(rbac_test_path) else EvidenceStatus.PENDING,
    ))

    return items


def _collect_audit_logs() -> list[EvidenceItem]:
    """Collect evidence for audit logging."""
    items = []

    # Audit service
    audit_path = "backend/app/core/audit.py"
    items.append(EvidenceItem(
        category=EvidenceCategory.AUDIT_LOGS,
        title="Audit Logging Framework",
        description="Core audit logging service recording access and mutation events.",
        artifact_path=audit_path,
        collected_at=_now_iso() if _check_file_exists(audit_path) else "",
        status=EvidenceStatus.COLLECTED if _check_file_exists(audit_path) else EvidenceStatus.MISSING,
    ))

    # KG audit service
    kg_audit_path = "backend/app/services/kg_audit_service.py"
    items.append(EvidenceItem(
        category=EvidenceCategory.AUDIT_LOGS,
        title="Knowledge Graph Audit Trail",
        description="Audit trail for knowledge graph mutations and queries.",
        artifact_path=kg_audit_path,
        collected_at=_now_iso() if _check_file_exists(kg_audit_path) else "",
        status=EvidenceStatus.COLLECTED if _check_file_exists(kg_audit_path) else EvidenceStatus.MISSING,
    ))

    # AI audit service
    ai_audit_path = "backend/app/services/ai_audit_service.py"
    items.append(EvidenceItem(
        category=EvidenceCategory.AUDIT_LOGS,
        title="AI Decision Audit Service",
        description="Audit service tracking AI/ML model decisions for explainability.",
        artifact_path=ai_audit_path,
        collected_at=_now_iso() if _check_file_exists(ai_audit_path) else "",
        status=EvidenceStatus.COLLECTED if _check_file_exists(ai_audit_path) else EvidenceStatus.MISSING,
    ))

    return items


def _collect_data_protection() -> list[EvidenceItem]:
    """Collect evidence for data protection controls."""
    items = []

    # Database encryption (config)
    db_config = "backend/app/core/database.py"
    items.append(EvidenceItem(
        category=EvidenceCategory.DATA_PROTECTION,
        title="Database Connection Security",
        description="Database configuration showing encrypted connections.",
        artifact_path=db_config,
        collected_at=_now_iso() if _check_file_exists(db_config) else "",
        status=EvidenceStatus.COLLECTED if _check_file_exists(db_config) else EvidenceStatus.MISSING,
    ))

    # Backup verification (k8s PVC)
    backup_path = "k8s/postgres/pvc.yaml"
    items.append(EvidenceItem(
        category=EvidenceCategory.DATA_PROTECTION,
        title="Backup Storage Configuration",
        description="Kubernetes PVC configuration for database backups.",
        artifact_path=backup_path,
        collected_at=_now_iso() if _check_file_exists(backup_path) else "",
        status=EvidenceStatus.COLLECTED if _check_file_exists(backup_path) else EvidenceStatus.MISSING,
    ))

    # Consent management
    consent_path = "backend/app/schemas/base.py"
    items.append(EvidenceItem(
        category=EvidenceCategory.DATA_PROTECTION,
        title="Consent Status Tracking",
        description="Schema defining consent status tracking for data processing.",
        artifact_path=consent_path,
        collected_at=_now_iso() if _check_file_exists(consent_path) else "",
        status=EvidenceStatus.COLLECTED if _check_file_exists(consent_path) else EvidenceStatus.MISSING,
    ))

    return items


def _collect_incident_response() -> list[EvidenceItem]:
    """Collect evidence for incident response readiness."""
    items = []

    # Circuit breaker
    cb_path = "backend/app/services/circuit_breaker.py"
    items.append(EvidenceItem(
        category=EvidenceCategory.INCIDENT_RESPONSE,
        title="Circuit Breaker Pattern",
        description="Circuit breaker implementation for fault isolation.",
        artifact_path=cb_path,
        collected_at=_now_iso() if _check_file_exists(cb_path) else "",
        status=EvidenceStatus.COLLECTED if _check_file_exists(cb_path) else EvidenceStatus.MISSING,
    ))

    # Alert rules
    alert_path = "backend/app/services/alert_rules_service.py"
    items.append(EvidenceItem(
        category=EvidenceCategory.INCIDENT_RESPONSE,
        title="Alert Rules Configuration",
        description="Alerting rules for incident detection and notification.",
        artifact_path=alert_path,
        collected_at=_now_iso() if _check_file_exists(alert_path) else "",
        status=EvidenceStatus.COLLECTED if _check_file_exists(alert_path) else EvidenceStatus.MISSING,
    ))

    # Health check
    health_path = "backend/app/api/health.py"
    items.append(EvidenceItem(
        category=EvidenceCategory.INCIDENT_RESPONSE,
        title="Health Check Endpoints",
        description="Health check endpoints for monitoring system availability.",
        artifact_path=health_path,
        collected_at=_now_iso() if _check_file_exists(health_path) else "",
        status=EvidenceStatus.COLLECTED if _check_file_exists(health_path) else EvidenceStatus.MISSING,
    ))

    return items


def _collect_change_management() -> list[EvidenceItem]:
    """Collect evidence for change management controls."""
    items = []

    # Docker compose prod
    dc_path = "docker-compose.prod.yml"
    items.append(EvidenceItem(
        category=EvidenceCategory.CHANGE_MANAGEMENT,
        title="Production Deployment Configuration",
        description="Docker Compose configuration defining production deployment.",
        artifact_path=dc_path,
        collected_at=_now_iso() if _check_file_exists(dc_path) else "",
        status=EvidenceStatus.COLLECTED if _check_file_exists(dc_path) else EvidenceStatus.MISSING,
    ))

    # K8s manifests
    k8s_path = "k8s/postgres/statefulset.yaml"
    items.append(EvidenceItem(
        category=EvidenceCategory.CHANGE_MANAGEMENT,
        title="Kubernetes StatefulSet Configuration",
        description="Kubernetes manifests for stateful service deployment.",
        artifact_path=k8s_path,
        collected_at=_now_iso() if _check_file_exists(k8s_path) else "",
        status=EvidenceStatus.COLLECTED if _check_file_exists(k8s_path) else EvidenceStatus.MISSING,
    ))

    # API maturity controls
    maturity_path = "backend/app/core/api_maturity.py"
    items.append(EvidenceItem(
        category=EvidenceCategory.CHANGE_MANAGEMENT,
        title="API Maturity Lifecycle Controls",
        description="API maturity labeling and lifecycle gate enforcement.",
        artifact_path=maturity_path,
        collected_at=_now_iso() if _check_file_exists(maturity_path) else "",
        status=EvidenceStatus.COLLECTED if _check_file_exists(maturity_path) else EvidenceStatus.MISSING,
    ))

    return items


# ============================================================================
# Main Service
# ============================================================================


class ComplianceBinderService:
    """Service for generating compliance evidence binders.

    Collects evidence artifacts from the codebase and infrastructure,
    organizes them by compliance category, and tracks collection status.
    """

    def __init__(self) -> None:
        self._last_binder: ComplianceBinder | None = None
        logger.info("ComplianceBinderService initialized")

    def generate_binder(self) -> ComplianceBinder:
        """Generate a new compliance evidence binder.

        Scans the project for compliance artifacts across all categories
        and produces a structured binder.

        Returns:
            ComplianceBinder with collected evidence items.
        """
        binder_id = f"BINDER-{uuid4().hex[:12].upper()}"
        created_at = _now_iso()

        items: list[EvidenceItem] = []
        items.extend(_collect_security_controls())
        items.extend(_collect_access_management())
        items.extend(_collect_audit_logs())
        items.extend(_collect_data_protection())
        items.extend(_collect_incident_response())
        items.extend(_collect_change_management())

        # Calculate completeness
        total = len(items)
        collected = sum(1 for i in items if i.status == EvidenceStatus.COLLECTED)
        completeness = (collected / total * 100.0) if total > 0 else 0.0

        binder = ComplianceBinder(
            binder_id=binder_id,
            created_at=created_at,
            items=items,
            completeness_percent=round(completeness, 1),
        )

        self._last_binder = binder
        logger.info(
            f"Generated compliance binder {binder_id}: "
            f"{collected}/{total} items collected ({completeness:.1f}%)"
        )
        return binder

    def get_binder_summary(self) -> BinderSummary | None:
        """Get a summary of the most recently generated binder.

        Returns:
            BinderSummary or None if no binder has been generated.
        """
        binder = self._last_binder
        if binder is None:
            return None

        collected = sum(1 for i in binder.items if i.status == EvidenceStatus.COLLECTED)
        pending = sum(1 for i in binder.items if i.status == EvidenceStatus.PENDING)
        missing = sum(1 for i in binder.items if i.status == EvidenceStatus.MISSING)

        # Breakdown by category
        by_category: dict[str, dict[str, int]] = {}
        for cat in EvidenceCategory:
            cat_items = [i for i in binder.items if i.category == cat]
            by_category[cat.value] = {
                "total": len(cat_items),
                "collected": sum(1 for i in cat_items if i.status == EvidenceStatus.COLLECTED),
                "pending": sum(1 for i in cat_items if i.status == EvidenceStatus.PENDING),
                "missing": sum(1 for i in cat_items if i.status == EvidenceStatus.MISSING),
            }

        return BinderSummary(
            binder_id=binder.binder_id,
            created_at=binder.created_at,
            total_items=len(binder.items),
            collected=collected,
            pending=pending,
            missing=missing,
            completeness_percent=binder.completeness_percent,
            by_category=by_category,
        )


# ============================================================================
# Singleton
# ============================================================================

_instance: ComplianceBinderService | None = None
_instance_lock = threading.Lock()


def get_compliance_binder_service() -> ComplianceBinderService:
    """Get or create the singleton ComplianceBinderService."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ComplianceBinderService()
    return _instance


def reset_compliance_binder_service() -> None:
    """Reset the singleton (for testing)."""
    global _instance
    with _instance_lock:
        _instance = None
