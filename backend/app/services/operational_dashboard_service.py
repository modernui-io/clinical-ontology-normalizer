"""Operational Dashboard & SLA Management Service (COO-5).

In-memory service providing SLA management, system health monitoring,
trial operations summaries, automated process tracking, alerts, and
a unified operational dashboard for clinical trial recruitment.

Usage:
    from app.services.operational_dashboard_service import (
        get_operational_dashboard_service,
    )

    svc = get_operational_dashboard_service()
    dashboard = svc.get_full_dashboard()
"""

from __future__ import annotations

import logging
import random
import threading
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from app.schemas.operational_dashboard import (
    AlertCreateRequest,
    AlertSeverity,
    AutomatedProcess,
    CapacityAssessment,
    DashboardResponse,
    OperationalAlert,
    OperationalDashboard,
    OperationalMetric,
    OperationalStatus,
    ProcessCreateRequest,
    ProcessListResponse,
    ProcessStatus,
    ProcessUpdateRequest,
    SLACategory,
    SLAComplianceTrend,
    SLACreateRequest,
    SLADefinition,
    SLAListResponse,
    SLAMeasurement,
    SLAMeasurementCreateRequest,
    SLAStatus,
    SLASummary,
    SLAUpdateRequest,
    SystemHealthStatus,
    TrialOperationsSummary,
)

logger = logging.getLogger(__name__)

_NOW = datetime.now(timezone.utc)


def _ts(hours_ago: float = 0) -> datetime:
    """Helper to create timestamps relative to now."""
    return _NOW - timedelta(hours=hours_ago)


class OperationalDashboardService:
    """In-memory operational dashboard and SLA management service."""

    def __init__(self) -> None:
        self._sla_definitions: dict[str, SLADefinition] = {}
        self._sla_measurements: dict[str, list[SLAMeasurement]] = {}
        self._trial_summaries: dict[str, TrialOperationsSummary] = {}
        self._system_health: dict[str, SystemHealthStatus] = {}
        self._automated_processes: dict[str, AutomatedProcess] = {}
        self._alerts: dict[str, OperationalAlert] = {}
        self._seed()

    # -----------------------------------------------------------------------
    # Seed data
    # -----------------------------------------------------------------------

    def _seed(self) -> None:
        """Populate with realistic demo data."""
        self._seed_sla_definitions()
        self._seed_sla_measurements()
        self._seed_trial_summaries()
        self._seed_system_health()
        self._seed_automated_processes()
        self._seed_alerts()

    def _seed_sla_definitions(self) -> None:
        slas = [
            SLADefinition(
                id="SLA-001",
                name="API Uptime",
                category=SLACategory.API_UPTIME,
                target_value=99.9,
                unit="%",
                measurement_period_hours=24,
                current_value=99.95,
                status=SLAStatus.MEETING,
                breach_count_30d=0,
                last_measured=_ts(1),
                client_id="REGENERON",
                penalty_amount=10000.0,
            ),
            SLADefinition(
                id="SLA-002",
                name="NLP Processing Turnaround",
                category=SLACategory.NLP_TURNAROUND,
                target_value=5.0,
                unit="seconds",
                measurement_period_hours=1,
                current_value=3.2,
                status=SLAStatus.MEETING,
                breach_count_30d=2,
                last_measured=_ts(0.5),
                client_id="REGENERON",
                penalty_amount=5000.0,
            ),
            SLADefinition(
                id="SLA-003",
                name="Data Freshness - Patient Records",
                category=SLACategory.DATA_FRESHNESS,
                target_value=4.0,
                unit="hours",
                measurement_period_hours=4,
                current_value=2.8,
                status=SLAStatus.MEETING,
                breach_count_30d=1,
                last_measured=_ts(0.25),
                client_id="REGENERON",
                penalty_amount=7500.0,
            ),
            SLADefinition(
                id="SLA-004",
                name="Screening Accuracy",
                category=SLACategory.SCREENING_ACCURACY,
                target_value=95.0,
                unit="%",
                measurement_period_hours=24,
                current_value=97.2,
                status=SLAStatus.MEETING,
                breach_count_30d=0,
                last_measured=_ts(2),
                client_id="REGENERON",
                penalty_amount=15000.0,
            ),
            SLADefinition(
                id="SLA-005",
                name="API Response Time (p95)",
                category=SLACategory.RESPONSE_TIME,
                target_value=500.0,
                unit="ms",
                measurement_period_hours=1,
                current_value=480.0,
                status=SLAStatus.AT_RISK,
                breach_count_30d=4,
                last_measured=_ts(0.1),
                client_id="REGENERON",
                penalty_amount=3000.0,
            ),
            SLADefinition(
                id="SLA-006",
                name="Monthly Compliance Report Delivery",
                category=SLACategory.COMPLIANCE_REPORTING,
                target_value=5.0,
                unit="business_days",
                measurement_period_hours=720,
                current_value=3.0,
                status=SLAStatus.MEETING,
                breach_count_30d=0,
                last_measured=_ts(48),
                client_id="REGENERON",
                penalty_amount=20000.0,
            ),
            SLADefinition(
                id="SLA-007",
                name="Data Freshness - Lab Results",
                category=SLACategory.DATA_FRESHNESS,
                target_value=6.0,
                unit="hours",
                measurement_period_hours=6,
                current_value=7.1,
                status=SLAStatus.BREACHED,
                breach_count_30d=3,
                last_measured=_ts(0.5),
                client_id="REGENERON",
                penalty_amount=5000.0,
            ),
            SLADefinition(
                id="SLA-008",
                name="Screening Volume Throughput",
                category=SLACategory.NLP_TURNAROUND,
                target_value=1000.0,
                unit="patients/day",
                measurement_period_hours=24,
                current_value=1150.0,
                status=SLAStatus.MEETING,
                breach_count_30d=0,
                last_measured=_ts(3),
                penalty_amount=8000.0,
            ),
        ]
        for sla in slas:
            self._sla_definitions[sla.id] = sla

    def _seed_sla_measurements(self) -> None:
        """Create 30+ measurements spread across SLAs over the past 30 days."""
        random.seed(42)
        for sla in self._sla_definitions.values():
            measurements: list[SLAMeasurement] = []
            # Create 4-6 measurements per SLA
            count = random.randint(4, 6)
            for i in range(count):
                hours_ago = random.uniform(1, 720)
                # Vary around current value
                base = sla.current_value if sla.current_value is not None else sla.target_value
                value = base * random.uniform(0.92, 1.08)
                value = round(value, 2)

                # Determine if meets target based on category
                if sla.unit in ("%", "patients/day"):
                    meets = value >= sla.target_value
                else:
                    meets = value <= sla.target_value

                m = SLAMeasurement(
                    id=f"MEAS-{sla.id}-{i:03d}",
                    sla_id=sla.id,
                    value=value,
                    measured_at=_ts(hours_ago),
                    meets_target=meets,
                )
                measurements.append(m)
            self._sla_measurements[sla.id] = measurements

    def _seed_trial_summaries(self) -> None:
        trials = [
            TrialOperationsSummary(
                trial_id="TRIAL-EYLEA-HD-001",
                trial_name="EYLEA HD Phase III - Diabetic Macular Edema",
                status="active",
                patients_screened=847,
                patients_enrolled=312,
                enrollment_rate_per_week=18.5,
                site_count=24,
                active_sites=22,
                screen_failure_rate=0.632,
            ),
            TrialOperationsSummary(
                trial_id="TRIAL-DUPIXENT-AD-002",
                trial_name="Dupixent Pediatric Atopic Dermatitis Extension",
                status="active",
                patients_screened=423,
                patients_enrolled=198,
                enrollment_rate_per_week=12.3,
                site_count=18,
                active_sites=18,
                screen_failure_rate=0.532,
            ),
            TrialOperationsSummary(
                trial_id="TRIAL-LIBTAYO-CSCC-003",
                trial_name="Libtayo Adjuvant CSCC Phase III",
                status="active",
                patients_screened=256,
                patients_enrolled=89,
                enrollment_rate_per_week=6.8,
                site_count=15,
                active_sites=12,
                screen_failure_rate=0.652,
            ),
        ]
        for t in trials:
            self._trial_summaries[t.trial_id] = t

    def _seed_system_health(self) -> None:
        services = [
            SystemHealthStatus(
                service_name="API Gateway",
                status=OperationalStatus.HEALTHY,
                uptime_percent_30d=99.95,
                last_incident=_ts(168),
                response_time_p99_ms=245.0,
                error_rate_percent=0.02,
            ),
            SystemHealthStatus(
                service_name="NLP Pipeline",
                status=OperationalStatus.HEALTHY,
                uptime_percent_30d=99.8,
                last_incident=_ts(72),
                response_time_p99_ms=3200.0,
                error_rate_percent=0.15,
            ),
            SystemHealthStatus(
                service_name="Database (PostgreSQL)",
                status=OperationalStatus.HEALTHY,
                uptime_percent_30d=99.99,
                last_incident=_ts(720),
                response_time_p99_ms=45.0,
                error_rate_percent=0.001,
            ),
            SystemHealthStatus(
                service_name="Redis (Job Queue)",
                status=OperationalStatus.HEALTHY,
                uptime_percent_30d=99.98,
                last_incident=_ts(480),
                response_time_p99_ms=12.0,
                error_rate_percent=0.005,
            ),
            SystemHealthStatus(
                service_name="FHIR Import Service",
                status=OperationalStatus.DEGRADED,
                uptime_percent_30d=98.5,
                last_incident=_ts(4),
                response_time_p99_ms=1800.0,
                error_rate_percent=1.2,
            ),
            SystemHealthStatus(
                service_name="Knowledge Graph Builder",
                status=OperationalStatus.HEALTHY,
                uptime_percent_30d=99.7,
                last_incident=_ts(120),
                response_time_p99_ms=890.0,
                error_rate_percent=0.08,
            ),
        ]
        for s in services:
            self._system_health[s.service_name] = s

    def _seed_automated_processes(self) -> None:
        processes = [
            AutomatedProcess(
                id="PROC-001",
                name="Daily Patient Screening",
                process_type="batch_screening",
                status=ProcessStatus.COMPLETED,
                schedule_cron="0 6 * * *",
                last_run=_ts(2),
                next_run=_ts(-22),
                success_rate_30d=98.5,
                avg_duration_seconds=1845.0,
            ),
            AutomatedProcess(
                id="PROC-002",
                name="FHIR Data Sync",
                process_type="data_sync",
                status=ProcessStatus.RUNNING,
                schedule_cron="*/30 * * * *",
                last_run=_ts(0.5),
                next_run=_ts(-0.5),
                success_rate_30d=97.2,
                avg_duration_seconds=320.0,
            ),
            AutomatedProcess(
                id="PROC-003",
                name="Database Backup",
                process_type="backup",
                status=ProcessStatus.COMPLETED,
                schedule_cron="0 2 * * *",
                last_run=_ts(6),
                next_run=_ts(-18),
                success_rate_30d=100.0,
                avg_duration_seconds=540.0,
            ),
            AutomatedProcess(
                id="PROC-004",
                name="Weekly Compliance Report",
                process_type="report_generation",
                status=ProcessStatus.SCHEDULED,
                schedule_cron="0 8 * * 1",
                last_run=_ts(120),
                next_run=_ts(-48),
                success_rate_30d=100.0,
                avg_duration_seconds=125.0,
            ),
            AutomatedProcess(
                id="PROC-005",
                name="SLA Measurement Collection",
                process_type="monitoring",
                status=ProcessStatus.COMPLETED,
                schedule_cron="0 * * * *",
                last_run=_ts(0.1),
                next_run=_ts(-0.9),
                success_rate_30d=99.8,
                avg_duration_seconds=45.0,
            ),
            AutomatedProcess(
                id="PROC-006",
                name="Lab Results Import",
                process_type="data_sync",
                status=ProcessStatus.FAILED,
                schedule_cron="0 */4 * * *",
                last_run=_ts(1),
                next_run=_ts(-3),
                success_rate_30d=92.0,
                avg_duration_seconds=680.0,
                last_error="Connection timeout to lab partner SFTP server",
            ),
            AutomatedProcess(
                id="PROC-007",
                name="Knowledge Graph Refresh",
                process_type="batch_processing",
                status=ProcessStatus.COMPLETED,
                schedule_cron="0 3 * * *",
                last_run=_ts(5),
                next_run=_ts(-19),
                success_rate_30d=99.0,
                avg_duration_seconds=2400.0,
            ),
            AutomatedProcess(
                id="PROC-008",
                name="Screening Accuracy Audit",
                process_type="audit",
                status=ProcessStatus.PAUSED,
                schedule_cron="0 10 * * 5",
                last_run=_ts(168),
                next_run=None,
                success_rate_30d=100.0,
                avg_duration_seconds=3600.0,
            ),
        ]
        for p in processes:
            self._automated_processes[p.id] = p

    def _seed_alerts(self) -> None:
        alerts = [
            OperationalAlert(
                id="ALERT-001",
                severity=AlertSeverity.CRITICAL,
                title="Lab Results Data Freshness SLA Breached",
                message="SLA-007 (Data Freshness - Lab Results) has exceeded the 6-hour threshold. Current value: 7.1 hours.",
                source="sla_monitor",
                created_at=_ts(0.5),
            ),
            OperationalAlert(
                id="ALERT-002",
                severity=AlertSeverity.WARNING,
                title="API Response Time Approaching SLA Limit",
                message="SLA-005 (API Response Time p95) is at 480ms, within 4% of the 500ms target.",
                source="sla_monitor",
                created_at=_ts(1),
            ),
            OperationalAlert(
                id="ALERT-003",
                severity=AlertSeverity.WARNING,
                title="FHIR Import Service Degraded",
                message="FHIR Import Service error rate has increased to 1.2%. Investigating connection issues.",
                source="health_monitor",
                created_at=_ts(4),
            ),
            OperationalAlert(
                id="ALERT-004",
                severity=AlertSeverity.INFO,
                title="Daily Screening Batch Completed",
                message="Processed 1,150 patients across 3 active trials. 312 new eligible candidates identified.",
                source="batch_processor",
                created_at=_ts(2),
                acknowledged=True,
                acknowledged_by="ops_team",
            ),
            OperationalAlert(
                id="ALERT-005",
                severity=AlertSeverity.CRITICAL,
                title="Lab Import Process Failed",
                message="PROC-006 (Lab Results Import) failed: Connection timeout to lab partner SFTP server.",
                source="process_monitor",
                created_at=_ts(1),
            ),
        ]
        for a in alerts:
            self._alerts[a.id] = a

    def clear(self) -> None:
        """Reset all data and re-seed."""
        self._sla_definitions.clear()
        self._sla_measurements.clear()
        self._trial_summaries.clear()
        self._system_health.clear()
        self._automated_processes.clear()
        self._alerts.clear()
        self._seed()

    # -----------------------------------------------------------------------
    # Full dashboard
    # -----------------------------------------------------------------------

    def get_full_dashboard(self) -> DashboardResponse:
        """Build the complete operational dashboard snapshot."""
        sla_summary = self._build_sla_summary()
        system_health = list(self._system_health.values())
        trial_summaries = list(self._trial_summaries.values())
        processes = list(self._automated_processes.values())
        alerts = sorted(
            self._alerts.values(), key=lambda a: a.created_at, reverse=True
        )
        key_metrics = self._calculate_key_metrics()
        overall_status = self._determine_overall_status()

        total_patients = sum(t.patients_screened for t in trial_summaries)
        total_sites = sum(t.site_count for t in trial_summaries)

        dashboard = OperationalDashboard(
            timestamp=datetime.now(timezone.utc),
            overall_status=overall_status,
            active_trials=len(trial_summaries),
            total_patients_pipeline=total_patients,
            total_sites=total_sites,
            system_health=system_health,
            trial_summaries=trial_summaries,
            sla_summary=sla_summary,
            automated_processes=processes,
            alerts=list(alerts),
            key_metrics=key_metrics,
        )
        return DashboardResponse(dashboard=dashboard)

    def _determine_overall_status(self) -> OperationalStatus:
        """Derive overall platform status from component health and SLAs."""
        # Check for any DOWN services
        statuses = [s.status for s in self._system_health.values()]
        if OperationalStatus.DOWN in statuses:
            return OperationalStatus.DOWN

        # Check for breached SLAs
        breached = sum(
            1
            for s in self._sla_definitions.values()
            if s.status == SLAStatus.BREACHED
        )
        if breached >= 2:
            return OperationalStatus.IMPAIRED
        if breached >= 1 or OperationalStatus.DEGRADED in statuses:
            return OperationalStatus.DEGRADED

        # Check at-risk SLAs
        at_risk = sum(
            1
            for s in self._sla_definitions.values()
            if s.status == SLAStatus.AT_RISK
        )
        if at_risk >= 3:
            return OperationalStatus.DEGRADED

        return OperationalStatus.HEALTHY

    def _build_sla_summary(self) -> SLASummary:
        """Aggregate SLA statuses into summary counts."""
        slas = list(self._sla_definitions.values())
        total = len(slas)
        meeting = sum(1 for s in slas if s.status == SLAStatus.MEETING)
        at_risk = sum(1 for s in slas if s.status == SLAStatus.AT_RISK)
        breached = sum(1 for s in slas if s.status == SLAStatus.BREACHED)
        not_measured = sum(1 for s in slas if s.status == SLAStatus.NOT_MEASURED)
        compliance_rate = round(meeting / total * 100, 1) if total > 0 else 0.0

        return SLASummary(
            total_slas=total,
            meeting=meeting,
            at_risk=at_risk,
            breached=breached,
            not_measured=not_measured,
            overall_compliance_rate=compliance_rate,
        )

    # -----------------------------------------------------------------------
    # SLA CRUD
    # -----------------------------------------------------------------------

    def list_slas(self, category: SLACategory | None = None) -> SLAListResponse:
        """List SLA definitions, optionally filtered by category."""
        slas = list(self._sla_definitions.values())
        if category is not None:
            slas = [s for s in slas if s.category == category]
        return SLAListResponse(items=slas, total=len(slas))

    def get_sla(self, sla_id: str) -> SLADefinition | None:
        """Return an SLA definition by ID."""
        return self._sla_definitions.get(sla_id)

    def create_sla(self, req: SLACreateRequest) -> SLADefinition:
        """Create a new SLA definition."""
        sla_id = f"SLA-{uuid4().hex[:8].upper()}"
        sla = SLADefinition(
            id=sla_id,
            name=req.name,
            category=req.category,
            target_value=req.target_value,
            unit=req.unit,
            measurement_period_hours=req.measurement_period_hours,
            client_id=req.client_id,
            penalty_amount=req.penalty_amount,
            status=SLAStatus.NOT_MEASURED,
        )
        self._sla_definitions[sla_id] = sla
        self._sla_measurements[sla_id] = []
        return sla

    def update_sla(self, sla_id: str, req: SLAUpdateRequest) -> SLADefinition | None:
        """Update an existing SLA definition."""
        sla = self._sla_definitions.get(sla_id)
        if sla is None:
            return None

        if req.name is not None:
            sla.name = req.name
        if req.target_value is not None:
            sla.target_value = req.target_value
        if req.unit is not None:
            sla.unit = req.unit
        if req.measurement_period_hours is not None:
            sla.measurement_period_hours = req.measurement_period_hours
        if req.client_id is not None:
            sla.client_id = req.client_id
        if req.penalty_amount is not None:
            sla.penalty_amount = req.penalty_amount

        self._sla_definitions[sla_id] = sla
        return sla

    def delete_sla(self, sla_id: str) -> bool:
        """Delete an SLA definition and its measurements."""
        if sla_id not in self._sla_definitions:
            return False
        del self._sla_definitions[sla_id]
        self._sla_measurements.pop(sla_id, None)
        return True

    # -----------------------------------------------------------------------
    # SLA Measurements
    # -----------------------------------------------------------------------

    def record_measurement(self, req: SLAMeasurementCreateRequest) -> SLAMeasurement | None:
        """Record a new SLA measurement and update breach detection."""
        sla = self._sla_definitions.get(req.sla_id)
        if sla is None:
            return None

        measured_at = req.measured_at or datetime.now(timezone.utc)

        # Determine if target is met
        if sla.unit in ("%", "patients/day"):
            meets_target = req.value >= sla.target_value
        else:
            meets_target = req.value <= sla.target_value

        measurement = SLAMeasurement(
            id=f"MEAS-{uuid4().hex[:8].upper()}",
            sla_id=req.sla_id,
            value=req.value,
            measured_at=measured_at,
            meets_target=meets_target,
        )

        if req.sla_id not in self._sla_measurements:
            self._sla_measurements[req.sla_id] = []
        self._sla_measurements[req.sla_id].append(measurement)

        # Update SLA current value and status
        sla.current_value = req.value
        sla.last_measured = measured_at
        if meets_target:
            sla.status = SLAStatus.MEETING
        else:
            sla.status = SLAStatus.BREACHED
            sla.breach_count_30d += 1

        return measurement

    def get_measurements(
        self, sla_id: str, limit: int = 50
    ) -> list[SLAMeasurement]:
        """Return measurements for an SLA, newest first."""
        measurements = self._sla_measurements.get(sla_id, [])
        sorted_m = sorted(measurements, key=lambda m: m.measured_at, reverse=True)
        return sorted_m[:limit]

    def detect_breaches(self) -> list[SLADefinition]:
        """Return all SLAs currently in breached status."""
        return [
            sla
            for sla in self._sla_definitions.values()
            if sla.status == SLAStatus.BREACHED
        ]

    # -----------------------------------------------------------------------
    # System health
    # -----------------------------------------------------------------------

    def get_system_health(self) -> list[SystemHealthStatus]:
        """Return health status for all monitored services."""
        return list(self._system_health.values())

    def get_service_health(self, service_name: str) -> SystemHealthStatus | None:
        """Return health status for a specific service."""
        return self._system_health.get(service_name)

    def update_service_health(
        self, service_name: str, status: OperationalStatus
    ) -> SystemHealthStatus | None:
        """Update the status of a specific service."""
        svc = self._system_health.get(service_name)
        if svc is None:
            return None
        svc.status = status
        if status != OperationalStatus.HEALTHY:
            svc.last_incident = datetime.now(timezone.utc)
        return svc

    # -----------------------------------------------------------------------
    # Trial operations summaries
    # -----------------------------------------------------------------------

    def get_trial_summaries(self) -> list[TrialOperationsSummary]:
        """Return operations summaries for all active trials."""
        return list(self._trial_summaries.values())

    def get_trial_summary(self, trial_id: str) -> TrialOperationsSummary | None:
        """Return operations summary for a specific trial."""
        return self._trial_summaries.get(trial_id)

    # -----------------------------------------------------------------------
    # Automated processes
    # -----------------------------------------------------------------------

    def list_processes(
        self, status: ProcessStatus | None = None
    ) -> ProcessListResponse:
        """List automated processes, optionally filtered by status."""
        processes = list(self._automated_processes.values())
        if status is not None:
            processes = [p for p in processes if p.status == status]
        return ProcessListResponse(items=processes, total=len(processes))

    def get_process(self, process_id: str) -> AutomatedProcess | None:
        """Return an automated process by ID."""
        return self._automated_processes.get(process_id)

    def create_process(self, req: ProcessCreateRequest) -> AutomatedProcess:
        """Create a new automated process."""
        proc_id = f"PROC-{uuid4().hex[:8].upper()}"
        proc = AutomatedProcess(
            id=proc_id,
            name=req.name,
            process_type=req.process_type,
            status=req.status,
            schedule_cron=req.schedule_cron,
        )
        self._automated_processes[proc_id] = proc
        return proc

    def update_process(
        self, process_id: str, req: ProcessUpdateRequest
    ) -> AutomatedProcess | None:
        """Update an existing automated process."""
        proc = self._automated_processes.get(process_id)
        if proc is None:
            return None

        if req.name is not None:
            proc.name = req.name
        if req.status is not None:
            proc.status = req.status
        if req.schedule_cron is not None:
            proc.schedule_cron = req.schedule_cron
        if req.last_error is not None:
            proc.last_error = req.last_error

        return proc

    def trigger_process(self, process_id: str) -> AutomatedProcess | None:
        """Trigger immediate execution of an automated process."""
        proc = self._automated_processes.get(process_id)
        if proc is None:
            return None

        proc.status = ProcessStatus.RUNNING
        proc.last_run = datetime.now(timezone.utc)
        proc.last_error = None
        return proc

    def delete_process(self, process_id: str) -> bool:
        """Delete an automated process."""
        if process_id not in self._automated_processes:
            return False
        del self._automated_processes[process_id]
        return True

    # -----------------------------------------------------------------------
    # Alerts
    # -----------------------------------------------------------------------

    def list_alerts(
        self,
        severity: AlertSeverity | None = None,
        acknowledged: bool | None = None,
        limit: int = 50,
    ) -> list[OperationalAlert]:
        """List alerts, optionally filtered by severity and/or acknowledgment."""
        alerts = list(self._alerts.values())
        if severity is not None:
            alerts = [a for a in alerts if a.severity == severity]
        if acknowledged is not None:
            alerts = [a for a in alerts if a.acknowledged == acknowledged]
        alerts.sort(key=lambda a: a.created_at, reverse=True)
        return alerts[:limit]

    def get_alert(self, alert_id: str) -> OperationalAlert | None:
        """Return an alert by ID."""
        return self._alerts.get(alert_id)

    def create_alert(self, req: AlertCreateRequest) -> OperationalAlert:
        """Create a new operational alert."""
        alert_id = f"ALERT-{uuid4().hex[:8].upper()}"
        alert = OperationalAlert(
            id=alert_id,
            severity=req.severity,
            title=req.title,
            message=req.message,
            source=req.source,
            created_at=datetime.now(timezone.utc),
        )
        self._alerts[alert_id] = alert
        return alert

    def acknowledge_alert(
        self, alert_id: str, acknowledged_by: str = "system"
    ) -> OperationalAlert | None:
        """Acknowledge an alert."""
        alert = self._alerts.get(alert_id)
        if alert is None:
            return None
        alert.acknowledged = True
        alert.acknowledged_by = acknowledged_by
        return alert

    def delete_alert(self, alert_id: str) -> bool:
        """Delete an alert."""
        if alert_id not in self._alerts:
            return False
        del self._alerts[alert_id]
        return True

    # -----------------------------------------------------------------------
    # Key metrics
    # -----------------------------------------------------------------------

    def _calculate_key_metrics(self) -> list[OperationalMetric]:
        """Calculate high-level operational KPIs."""
        trials = list(self._trial_summaries.values())
        total_screened = sum(t.patients_screened for t in trials)
        total_enrolled = sum(t.patients_enrolled for t in trials)

        # Cost per patient screened (hypothetical)
        cost_per_patient = 42.50
        prev_cost = 48.00
        cost_change = round((cost_per_patient - prev_cost) / prev_cost * 100, 1)

        # Time to match (hypothetical, in hours)
        time_to_match = 2.3
        prev_time = 3.1
        time_change = round((time_to_match - prev_time) / prev_time * 100, 1)

        # Enrollment velocity
        total_rate = sum(t.enrollment_rate_per_week for t in trials)
        prev_rate = 34.0
        rate_change = round((total_rate - prev_rate) / prev_rate * 100, 1) if prev_rate > 0 else 0

        # Screen-to-enroll conversion
        conversion = round(total_enrolled / total_screened * 100, 1) if total_screened > 0 else 0.0
        prev_conversion = 35.0
        conversion_change = round((conversion - prev_conversion) / prev_conversion * 100, 1) if prev_conversion > 0 else 0

        # Active sites utilization
        total_sites = sum(t.site_count for t in trials)
        active_sites = sum(t.active_sites for t in trials)
        site_utilization = round(active_sites / total_sites * 100, 1) if total_sites > 0 else 0
        prev_site_util = 88.0
        site_util_change = round((site_utilization - prev_site_util) / prev_site_util * 100, 1) if prev_site_util > 0 else 0

        return [
            OperationalMetric(
                name="Cost per Patient Screened",
                value=cost_per_patient,
                unit="USD",
                trend="down",
                previous_value=prev_cost,
                change_percent=cost_change,
            ),
            OperationalMetric(
                name="Average Time to Match",
                value=time_to_match,
                unit="hours",
                trend="down",
                previous_value=prev_time,
                change_percent=time_change,
            ),
            OperationalMetric(
                name="Enrollment Velocity",
                value=total_rate,
                unit="patients/week",
                trend="up" if rate_change > 0 else "down",
                previous_value=prev_rate,
                change_percent=rate_change,
            ),
            OperationalMetric(
                name="Screen-to-Enroll Conversion",
                value=conversion,
                unit="%",
                trend="up" if conversion_change > 0 else "down",
                previous_value=prev_conversion,
                change_percent=conversion_change,
            ),
            OperationalMetric(
                name="Site Utilization",
                value=site_utilization,
                unit="%",
                trend="up" if site_util_change > 0 else "down",
                previous_value=prev_site_util,
                change_percent=site_util_change,
            ),
        ]

    def get_key_metrics(self) -> list[OperationalMetric]:
        """Public access to key metrics."""
        return self._calculate_key_metrics()

    # -----------------------------------------------------------------------
    # Historical SLA compliance trending
    # -----------------------------------------------------------------------

    def get_sla_compliance_trend(
        self, sla_id: str, periods: int = 7
    ) -> list[SLAComplianceTrend]:
        """Return historical compliance trend for an SLA.

        Groups measurements into daily buckets going back *periods* days.
        """
        measurements = self._sla_measurements.get(sla_id, [])
        if not measurements:
            return []

        now = datetime.now(timezone.utc)
        trends: list[SLAComplianceTrend] = []

        for i in range(periods):
            day_start = now - timedelta(days=i + 1)
            day_end = now - timedelta(days=i)
            day_measurements = [
                m
                for m in measurements
                if day_start <= m.measured_at < day_end
            ]
            total = len(day_measurements)
            breaches = sum(1 for m in day_measurements if not m.meets_target)
            compliance = (
                round((total - breaches) / total * 100, 1) if total > 0 else 100.0
            )
            trends.append(
                SLAComplianceTrend(
                    period=day_start.strftime("%Y-%m-%d"),
                    compliance_rate=compliance,
                    measurements_count=total,
                    breaches=breaches,
                )
            )

        trends.reverse()
        return trends

    # -----------------------------------------------------------------------
    # Capacity assessment
    # -----------------------------------------------------------------------

    def get_capacity_assessment(self) -> CapacityAssessment:
        """Compute current operational capacity utilization."""
        # Simulated metrics based on system health
        health = list(self._system_health.values())
        avg_response = (
            sum(s.response_time_p99_ms for s in health) / len(health)
            if health
            else 0
        )
        avg_error = (
            sum(s.error_rate_percent for s in health) / len(health)
            if health
            else 0
        )

        # Synthetic capacity figures
        cpu = min(100.0, max(0.0, 35.0 + avg_response / 100.0))
        memory = 62.5
        storage = 41.2
        active_conns = 247
        max_conns = 1000

        overall = round((cpu + memory + storage) / 3, 1)
        if overall > 85:
            recommendation = "scale_up"
        elif overall > 70:
            recommendation = "monitor"
        else:
            recommendation = "normal"

        return CapacityAssessment(
            overall_capacity_percent=overall,
            cpu_utilization=round(cpu, 1),
            memory_utilization=memory,
            storage_utilization=storage,
            active_connections=active_conns,
            max_connections=max_conns,
            recommendation=recommendation,
        )

    # -----------------------------------------------------------------------
    # Stats
    # -----------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Return internal service statistics."""
        total_measurements = sum(
            len(ms) for ms in self._sla_measurements.values()
        )
        return {
            "sla_definitions": len(self._sla_definitions),
            "sla_measurements": total_measurements,
            "trial_summaries": len(self._trial_summaries),
            "system_health_entries": len(self._system_health),
            "automated_processes": len(self._automated_processes),
            "alerts": len(self._alerts),
            "unacknowledged_alerts": sum(
                1 for a in self._alerts.values() if not a.acknowledged
            ),
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: OperationalDashboardService | None = None
_instance_lock = threading.Lock()


def get_operational_dashboard_service() -> OperationalDashboardService:
    """Return the singleton OperationalDashboardService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = OperationalDashboardService()
    return _instance


def reset_operational_dashboard_service() -> None:
    """Reset the singleton (for testing)."""
    global _instance
    with _instance_lock:
        _instance = None
