"""Quality Management Service stub (VP-Quality-2).

Minimal implementation to support app startup. Full implementation pending.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.quality_management import (
    CAPACreate,
    CAPAMetrics,
    CAPAResponse,
    CAPASeverity,
    CAPASource,
    CAPAStatus,
    CAPAType,
    CAPAUpdate,
    QualificationReport,
    QualificationRunRequest,
)


class QualityManagementService:
    """In-memory Quality Management stub."""

    def __init__(self) -> None:
        self._capas: dict[str, CAPAResponse] = {}
        self._reports: dict[str, QualificationReport] = {}
        self._lock = threading.Lock()

    def get_metrics(self) -> CAPAMetrics:
        with self._lock:
            capas = list(self._capas.values())
        return CAPAMetrics(
            total_capas=len(capas),
            open_capas=sum(1 for c in capas if c.status != CAPAStatus.CLOSED),
            by_severity={},
            by_status={},
            by_type={},
            overdue_count=0,
            avg_days_to_close=0.0,
            recurrence_rate=0.0,
        )

    def list_capas(self, **kwargs) -> tuple[list[CAPAResponse], int]:
        with self._lock:
            items = list(self._capas.values())
        return items, len(items)

    def get_capa(self, capa_id: str) -> CAPAResponse | None:
        with self._lock:
            return self._capas.get(capa_id)

    def create_capa(self, payload: CAPACreate) -> CAPAResponse:
        now = datetime.now(timezone.utc)
        capa_id = f"CAPA-{uuid4().hex[:8].upper()}"
        capa = CAPAResponse(
            id=capa_id,
            title=payload.title,
            description=payload.description,
            capa_type=payload.capa_type,
            source=payload.source,
            severity=payload.severity,
            status=CAPAStatus.OPEN,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._capas[capa_id] = capa
        return capa

    def update_capa(self, capa_id: str, payload: CAPAUpdate) -> CAPAResponse | None:
        with self._lock:
            existing = self._capas.get(capa_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            data["updated_at"] = datetime.now(timezone.utc)
            updated = CAPAResponse(**data)
            self._capas[capa_id] = updated
        return updated

    def delete_capa(self, capa_id: str) -> bool:
        with self._lock:
            if capa_id in self._capas:
                del self._capas[capa_id]
                return True
            return False

    def run_qualification(self, payload: QualificationRunRequest) -> QualificationReport:
        from app.schemas.quality_management import QualificationSummary
        now = datetime.now(timezone.utc)
        report_id = f"QR-{uuid4().hex[:8].upper()}"
        report = QualificationReport(
            id=report_id,
            qualification_type=payload.qualification_type,
            summary=QualificationSummary(
                total_checks=0,
                passed=0,
                failed=0,
                skipped=0,
                pass_rate=100.0,
                total_duration_ms=0.0,
                qualification_type=payload.qualification_type,
                overall_result="PASS",
            ),
            checks=[],
            executed_at=now,
            executed_by=payload.executed_by,
        )
        with self._lock:
            self._reports[report_id] = report
        return report

    def list_qualification_reports(self) -> list[QualificationReport]:
        with self._lock:
            return list(self._reports.values())

    def get_qualification_report(self, report_id: str) -> QualificationReport | None:
        with self._lock:
            return self._reports.get(report_id)

    def delete_qualification_report(self, report_id: str) -> bool:
        with self._lock:
            if report_id in self._reports:
                del self._reports[report_id]
                return True
            return False


_instance: QualityManagementService | None = None
_instance_lock = threading.Lock()


def get_quality_management_service() -> QualityManagementService:
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = QualityManagementService()
    return _instance


def reset_quality_management_service() -> QualityManagementService:
    global _instance
    with _instance_lock:
        _instance = QualityManagementService()
    return _instance
