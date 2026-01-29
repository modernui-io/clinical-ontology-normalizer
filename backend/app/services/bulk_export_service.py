"""FHIR Bulk Data Export Service.

Implements FHIR Bulk Data Access (Flat FHIR) specification for large-scale
data export in NDJSON format.

See: https://hl7.org/fhir/uv/bulkdata/
"""

from __future__ import annotations

import asyncio
import gzip
import json
import logging
import os
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Any, AsyncGenerator

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================


class ExportStatus(str, Enum):
    """Status of a bulk export job."""

    PENDING = "pending"  # Job created, not yet started
    IN_PROGRESS = "in-progress"  # Export is running
    COMPLETED = "completed"  # Export finished successfully
    FAILED = "failed"  # Export failed
    CANCELLED = "cancelled"  # Export was cancelled
    EXPIRED = "expired"  # Export files have been cleaned up


class ExportType(str, Enum):
    """Type of bulk export."""

    SYSTEM = "system"  # Export all data ($export)
    PATIENT = "patient"  # Export patient-related data (Patient/$export)
    GROUP = "group"  # Export group members (Group/{id}/$export)


class ResourceType(str, Enum):
    """FHIR resource types that can be exported."""

    PATIENT = "Patient"
    CONDITION = "Condition"
    MEDICATION_REQUEST = "MedicationRequest"
    OBSERVATION = "Observation"
    PROCEDURE = "Procedure"
    ALLERGY_INTOLERANCE = "AllergyIntolerance"
    DIAGNOSTIC_REPORT = "DiagnosticReport"
    ENCOUNTER = "Encounter"
    IMMUNIZATION = "Immunization"
    CARE_PLAN = "CarePlan"
    DOCUMENT_REFERENCE = "DocumentReference"
    PRACTITIONER = "Practitioner"
    ORGANIZATION = "Organization"
    LOCATION = "Location"


# Default resource types to export
DEFAULT_RESOURCE_TYPES = [
    ResourceType.PATIENT,
    ResourceType.CONDITION,
    ResourceType.MEDICATION_REQUEST,
    ResourceType.OBSERVATION,
    ResourceType.PROCEDURE,
    ResourceType.ALLERGY_INTOLERANCE,
    ResourceType.ENCOUNTER,
]


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class ExportFile:
    """Information about an exported file."""

    resource_type: str
    url: str  # Download URL
    count: int  # Number of resources in file
    size_bytes: int  # File size
    file_path: str  # Local file path


@dataclass
class ExportError:
    """Error that occurred during export."""

    resource_type: str
    record_id: str | None
    error_type: str
    error_message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ExportProgress:
    """Progress tracking for export job."""

    total_resources: int = 0
    exported_resources: int = 0
    current_resource_type: str | None = None
    percent_complete: float = 0.0
    estimated_time_remaining_seconds: float | None = None


@dataclass
class ExportJob:
    """A bulk export job."""

    job_id: str
    status: ExportStatus
    export_type: ExportType
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    expires_at: datetime | None = None

    # Configuration
    resource_types: list[str] = field(default_factory=list)
    since: datetime | None = None  # _since parameter
    type_filter: str | None = None  # _typeFilter parameter
    patient_ids: list[str] | None = None  # For patient-level export
    group_id: str | None = None  # For group-level export
    output_format: str = "application/fhir+ndjson"

    # Results
    output_files: list[ExportFile] = field(default_factory=list)
    errors: list[ExportError] = field(default_factory=list)
    progress: ExportProgress = field(default_factory=ExportProgress)

    # Internal
    export_dir: str | None = None
    request_url: str | None = None
    transactionTime: str | None = None  # FHIR instant for the export

    def to_status_response(self, base_url: str) -> dict[str, Any]:
        """Convert to FHIR Bulk Data status response.

        See: https://hl7.org/fhir/uv/bulkdata/export.html#response---complete-status
        """
        if self.status == ExportStatus.COMPLETED:
            return {
                "transactionTime": self.transactionTime or self.created_at.isoformat(),
                "request": self.request_url or f"{base_url}/fhir/$export",
                "requiresAccessToken": False,
                "output": [
                    {
                        "type": f.resource_type,
                        "url": f"{base_url}/fhir/$export/{self.job_id}/download/{f.resource_type}.ndjson",
                        "count": f.count,
                    }
                    for f in self.output_files
                    if f.count > 0
                ],
                "error": [
                    {
                        "type": "OperationOutcome",
                        "url": f"{base_url}/fhir/$export/{self.job_id}/errors",
                    }
                ]
                if self.errors
                else [],
            }
        elif self.status == ExportStatus.IN_PROGRESS:
            return {
                "status": "in-progress",
                "progress": {
                    "percent_complete": self.progress.percent_complete,
                    "exported_resources": self.progress.exported_resources,
                    "total_resources": self.progress.total_resources,
                    "current_resource_type": self.progress.current_resource_type,
                },
            }
        elif self.status == ExportStatus.FAILED:
            return {
                "status": "failed",
                "errors": [
                    {
                        "resource_type": e.resource_type,
                        "error_type": e.error_type,
                        "error_message": e.error_message,
                    }
                    for e in self.errors
                ],
            }
        else:
            return {
                "status": self.status.value,
            }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "export_type": self.export_type.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "resource_types": self.resource_types,
            "since": self.since.isoformat() if self.since else None,
            "output_files": [
                {
                    "resource_type": f.resource_type,
                    "url": f.url,
                    "count": f.count,
                    "size_bytes": f.size_bytes,
                }
                for f in self.output_files
            ],
            "errors_count": len(self.errors),
            "progress": {
                "total_resources": self.progress.total_resources,
                "exported_resources": self.progress.exported_resources,
                "percent_complete": self.progress.percent_complete,
                "current_resource_type": self.progress.current_resource_type,
            },
        }


# =============================================================================
# Mock Data Generators (In production, these would query the database)
# =============================================================================


def _generate_mock_patient(patient_id: str) -> dict[str, Any]:
    """Generate a mock FHIR Patient resource."""
    return {
        "resourceType": "Patient",
        "id": patient_id,
        "meta": {
            "versionId": "1",
            "lastUpdated": datetime.now(timezone.utc).isoformat(),
        },
        "identifier": [
            {
                "system": "http://hospital.example.org/patients",
                "value": patient_id,
            }
        ],
        "active": True,
        "name": [
            {
                "use": "official",
                "family": f"Patient{patient_id[-3:]}",
                "given": ["Test"],
            }
        ],
        "gender": "unknown",
        "birthDate": "1970-01-01",
    }


def _generate_mock_condition(condition_id: str, patient_id: str) -> dict[str, Any]:
    """Generate a mock FHIR Condition resource."""
    conditions = [
        ("38341003", "Hypertension"),
        ("44054006", "Type 2 Diabetes Mellitus"),
        ("195967001", "Asthma"),
        ("84114007", "Heart Failure"),
        ("13645005", "COPD"),
    ]
    import random

    code, display = random.choice(conditions)

    return {
        "resourceType": "Condition",
        "id": condition_id,
        "meta": {
            "versionId": "1",
            "lastUpdated": datetime.now(timezone.utc).isoformat(),
        },
        "clinicalStatus": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                    "code": "active",
                }
            ]
        },
        "verificationStatus": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                    "code": "confirmed",
                }
            ]
        },
        "code": {
            "coding": [
                {
                    "system": "http://snomed.info/sct",
                    "code": code,
                    "display": display,
                }
            ],
            "text": display,
        },
        "subject": {
            "reference": f"Patient/{patient_id}",
        },
        "recordedDate": (datetime.now(timezone.utc) - timedelta(days=random.randint(1, 365))).isoformat(),
    }


def _generate_mock_medication_request(
    med_id: str, patient_id: str
) -> dict[str, Any]:
    """Generate a mock FHIR MedicationRequest resource."""
    medications = [
        ("197361", "Lisinopril 10 MG"),
        ("311671", "Metformin 500 MG"),
        ("197380", "Atorvastatin 20 MG"),
        ("310798", "Omeprazole 20 MG"),
        ("197318", "Amlodipine 5 MG"),
    ]
    import random

    code, display = random.choice(medications)

    return {
        "resourceType": "MedicationRequest",
        "id": med_id,
        "meta": {
            "versionId": "1",
            "lastUpdated": datetime.now(timezone.utc).isoformat(),
        },
        "status": "active",
        "intent": "order",
        "medicationCodeableConcept": {
            "coding": [
                {
                    "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                    "code": code,
                    "display": display,
                }
            ],
            "text": display,
        },
        "subject": {
            "reference": f"Patient/{patient_id}",
        },
        "authoredOn": (datetime.now(timezone.utc) - timedelta(days=random.randint(1, 180))).isoformat(),
    }


def _generate_mock_observation(obs_id: str, patient_id: str) -> dict[str, Any]:
    """Generate a mock FHIR Observation resource."""
    observations = [
        ("8480-6", "Systolic blood pressure", 120, "mmHg"),
        ("8462-4", "Diastolic blood pressure", 80, "mmHg"),
        ("8867-4", "Heart rate", 72, "/min"),
        ("2339-0", "Glucose", 95, "mg/dL"),
        ("2093-3", "Total cholesterol", 180, "mg/dL"),
    ]
    import random

    code, display, value, unit = random.choice(observations)
    value = value + random.randint(-10, 10)

    return {
        "resourceType": "Observation",
        "id": obs_id,
        "meta": {
            "versionId": "1",
            "lastUpdated": datetime.now(timezone.utc).isoformat(),
        },
        "status": "final",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "vital-signs",
                    }
                ]
            }
        ],
        "code": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": code,
                    "display": display,
                }
            ],
            "text": display,
        },
        "subject": {
            "reference": f"Patient/{patient_id}",
        },
        "effectiveDateTime": (datetime.now(timezone.utc) - timedelta(days=random.randint(1, 30))).isoformat(),
        "valueQuantity": {
            "value": value,
            "unit": unit,
            "system": "http://unitsofmeasure.org",
            "code": unit,
        },
    }


# =============================================================================
# Bulk Export Service
# =============================================================================


class BulkExportService:
    """FHIR Bulk Data Export Service.

    Implements async export of FHIR resources to NDJSON files.

    Usage:
        service = BulkExportService()

        # Start an export
        job = await service.start_export(
            export_type=ExportType.SYSTEM,
            resource_types=["Patient", "Condition"],
        )

        # Check status
        job = service.get_job(job.job_id)

        # Download files when complete
        content = service.get_export_file(job.job_id, "Patient.ndjson")
    """

    def __init__(
        self,
        export_base_dir: str | None = None,
        file_retention_hours: int = 24,
        max_concurrent_exports: int = 3,
    ) -> None:
        """Initialize the bulk export service.

        Args:
            export_base_dir: Base directory for export files.
            file_retention_hours: How long to keep export files.
            max_concurrent_exports: Maximum concurrent export jobs.
        """
        self._export_base_dir = Path(
            export_base_dir or os.path.join(os.getcwd(), "exports")
        )
        self._export_base_dir.mkdir(parents=True, exist_ok=True)

        self._file_retention_hours = file_retention_hours
        self._max_concurrent_exports = max_concurrent_exports

        self._jobs: dict[str, ExportJob] = {}
        self._lock = Lock()
        self._running_exports: set[str] = set()

        logger.info(
            "Bulk export service initialized: export_dir=%s, retention=%dh",
            self._export_base_dir,
            self._file_retention_hours,
        )

    async def start_export(
        self,
        export_type: ExportType = ExportType.SYSTEM,
        resource_types: list[str] | None = None,
        since: datetime | None = None,
        type_filter: str | None = None,
        patient_ids: list[str] | None = None,
        group_id: str | None = None,
        output_format: str = "application/fhir+ndjson",
        request_url: str | None = None,
    ) -> ExportJob:
        """Start a new bulk export job.

        Args:
            export_type: Type of export (system, patient, group).
            resource_types: Resource types to export (default: all supported).
            since: Only include resources modified since this time.
            type_filter: Type-specific filter (FHIR search parameter).
            patient_ids: Patient IDs for patient-level export.
            group_id: Group ID for group-level export.
            output_format: Output format (only NDJSON supported).
            request_url: Original request URL for status response.

        Returns:
            Created export job.
        """
        # Validate resource types
        if resource_types is None:
            resource_types = [rt.value for rt in DEFAULT_RESOURCE_TYPES]
        else:
            # Validate all types are supported
            supported = {rt.value for rt in ResourceType}
            for rt in resource_types:
                if rt not in supported:
                    logger.warning("Unsupported resource type: %s", rt)

        # Check concurrent export limit
        with self._lock:
            if len(self._running_exports) >= self._max_concurrent_exports:
                raise RuntimeError(
                    f"Maximum concurrent exports ({self._max_concurrent_exports}) reached"
                )

        # Create job
        job_id = str(uuid.uuid4())
        export_dir = self._export_base_dir / job_id

        job = ExportJob(
            job_id=job_id,
            status=ExportStatus.PENDING,
            export_type=export_type,
            created_at=datetime.now(timezone.utc),
            resource_types=resource_types,
            since=since,
            type_filter=type_filter,
            patient_ids=patient_ids,
            group_id=group_id,
            output_format=output_format,
            export_dir=str(export_dir),
            request_url=request_url,
            transactionTime=datetime.now(timezone.utc).isoformat(),
        )

        with self._lock:
            self._jobs[job_id] = job
            self._running_exports.add(job_id)

        # Start export in background
        asyncio.create_task(self._run_export(job))

        logger.info(
            "Started bulk export: job_id=%s, type=%s, resources=%s",
            job_id,
            export_type.value,
            resource_types,
        )

        return job

    async def _run_export(self, job: ExportJob) -> None:
        """Run the export job (background task)."""
        try:
            job.status = ExportStatus.IN_PROGRESS
            job.started_at = datetime.now(timezone.utc)

            # Create export directory
            export_dir = Path(job.export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)

            # Generate mock data for each resource type
            # In production, this would query the database
            total_resources = 0
            exported_resources = 0

            # First pass: count total resources
            for resource_type in job.resource_types:
                # Mock: assume 100 resources per type
                total_resources += 100

            job.progress.total_resources = total_resources

            # Second pass: export resources
            for resource_type in job.resource_types:
                job.progress.current_resource_type = resource_type

                file_path = export_dir / f"{resource_type}.ndjson"
                resources_in_file = 0

                async with _async_file_writer(file_path) as writer:
                    async for resource in self._generate_resources(
                        resource_type, job.patient_ids, job.since
                    ):
                        # Write NDJSON line
                        line = json.dumps(resource, separators=(",", ":")) + "\n"
                        await writer.write(line)
                        resources_in_file += 1
                        exported_resources += 1

                        # Update progress
                        job.progress.exported_resources = exported_resources
                        job.progress.percent_complete = (
                            exported_resources / total_resources * 100
                            if total_resources > 0
                            else 0
                        )

                # Record output file
                if resources_in_file > 0:
                    file_size = file_path.stat().st_size
                    job.output_files.append(
                        ExportFile(
                            resource_type=resource_type,
                            url=f"{resource_type}.ndjson",
                            count=resources_in_file,
                            size_bytes=file_size,
                            file_path=str(file_path),
                        )
                    )

            # Mark complete
            job.status = ExportStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            job.expires_at = datetime.now(timezone.utc) + timedelta(
                hours=self._file_retention_hours
            )
            job.progress.percent_complete = 100.0

            logger.info(
                "Export completed: job_id=%s, files=%d, resources=%d",
                job.job_id,
                len(job.output_files),
                exported_resources,
            )

        except Exception as e:
            logger.exception("Export failed: job_id=%s", job.job_id)
            job.status = ExportStatus.FAILED
            job.errors.append(
                ExportError(
                    resource_type="*",
                    record_id=None,
                    error_type="ExportError",
                    error_message=str(e),
                )
            )

        finally:
            with self._lock:
                self._running_exports.discard(job.job_id)

    async def _generate_resources(
        self,
        resource_type: str,
        patient_ids: list[str] | None,
        since: datetime | None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Generate mock FHIR resources for export.

        In production, this would query the database.
        """
        # Generate mock data
        mock_patient_ids = patient_ids or [f"patient-{i:03d}" for i in range(10)]

        if resource_type == "Patient":
            for patient_id in mock_patient_ids:
                yield _generate_mock_patient(patient_id)
                await asyncio.sleep(0.01)  # Simulate DB query

        elif resource_type == "Condition":
            for patient_id in mock_patient_ids:
                # 2-3 conditions per patient
                import random

                for i in range(random.randint(2, 3)):
                    yield _generate_mock_condition(
                        f"cond-{patient_id}-{i}", patient_id
                    )
                    await asyncio.sleep(0.01)

        elif resource_type == "MedicationRequest":
            for patient_id in mock_patient_ids:
                # 1-4 medications per patient
                import random

                for i in range(random.randint(1, 4)):
                    yield _generate_mock_medication_request(
                        f"med-{patient_id}-{i}", patient_id
                    )
                    await asyncio.sleep(0.01)

        elif resource_type == "Observation":
            for patient_id in mock_patient_ids:
                # 3-5 observations per patient
                import random

                for i in range(random.randint(3, 5)):
                    yield _generate_mock_observation(
                        f"obs-{patient_id}-{i}", patient_id
                    )
                    await asyncio.sleep(0.01)

        else:
            # For other types, generate empty list
            logger.debug("No mock data generator for resource type: %s", resource_type)

    def get_job(self, job_id: str) -> ExportJob | None:
        """Get an export job by ID.

        Args:
            job_id: The job ID.

        Returns:
            The export job, or None if not found.
        """
        return self._jobs.get(job_id)

    def get_jobs(
        self,
        status: ExportStatus | None = None,
        limit: int = 100,
    ) -> list[ExportJob]:
        """Get export jobs.

        Args:
            status: Filter by status.
            limit: Maximum number of jobs to return.

        Returns:
            List of export jobs.
        """
        jobs = list(self._jobs.values())

        if status:
            jobs = [j for j in jobs if j.status == status]

        # Sort by created_at descending
        jobs.sort(key=lambda j: j.created_at, reverse=True)

        return jobs[:limit]

    def cancel_job(self, job_id: str) -> bool:
        """Cancel an export job.

        Args:
            job_id: The job ID to cancel.

        Returns:
            True if cancelled, False if not found or not cancellable.
        """
        job = self._jobs.get(job_id)
        if not job:
            return False

        if job.status not in [ExportStatus.PENDING, ExportStatus.IN_PROGRESS]:
            return False

        job.status = ExportStatus.CANCELLED
        job.completed_at = datetime.now(timezone.utc)

        with self._lock:
            self._running_exports.discard(job_id)

        logger.info("Export cancelled: job_id=%s", job_id)
        return True

    def delete_job(self, job_id: str) -> bool:
        """Delete an export job and its files.

        Args:
            job_id: The job ID to delete.

        Returns:
            True if deleted, False if not found or still running.
        """
        job = self._jobs.get(job_id)
        if not job:
            return False

        if job.status in [ExportStatus.PENDING, ExportStatus.IN_PROGRESS]:
            return False  # Cannot delete running jobs

        # Remove export files
        if job.export_dir:
            export_dir = Path(job.export_dir)
            if export_dir.exists():
                shutil.rmtree(export_dir)

        # Remove job from memory
        with self._lock:
            del self._jobs[job_id]

        logger.info("Export deleted: job_id=%s", job_id)
        return True

    def get_export_file(
        self, job_id: str, filename: str
    ) -> tuple[Path, str] | None:
        """Get the path to an export file.

        Args:
            job_id: The job ID.
            filename: The file name (e.g., "Patient.ndjson").

        Returns:
            Tuple of (file_path, content_type), or None if not found.
        """
        job = self._jobs.get(job_id)
        if not job:
            return None

        if job.status != ExportStatus.COMPLETED:
            return None

        file_path = Path(job.export_dir) / filename
        if not file_path.exists():
            return None

        return file_path, "application/fhir+ndjson"

    async def cleanup_expired_exports(self) -> int:
        """Clean up expired export files.

        Returns:
            Number of exports cleaned up.
        """
        cleaned = 0
        now = datetime.now(timezone.utc)

        for job_id, job in list(self._jobs.items()):
            if job.expires_at and job.expires_at < now:
                if self.delete_job(job_id):
                    cleaned += 1

        if cleaned > 0:
            logger.info("Cleaned up %d expired exports", cleaned)

        return cleaned

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics.

        Returns:
            Dictionary with service statistics.
        """
        jobs = list(self._jobs.values())

        return {
            "total_jobs": len(jobs),
            "running_jobs": len(self._running_exports),
            "jobs_by_status": {
                status.value: sum(1 for j in jobs if j.status == status)
                for status in ExportStatus
            },
            "total_files_exported": sum(len(j.output_files) for j in jobs),
            "export_base_dir": str(self._export_base_dir),
            "file_retention_hours": self._file_retention_hours,
        }


# =============================================================================
# Async File Writer Context Manager
# =============================================================================


class _async_file_writer:
    """Async context manager for writing to a file."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.file = None

    async def __aenter__(self):
        self.file = open(self.file_path, "w", encoding="utf-8")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.file:
            self.file.close()
        return False

    async def write(self, data: str):
        if self.file:
            self.file.write(data)


# =============================================================================
# Singleton Management
# =============================================================================

_bulk_export_service: BulkExportService | None = None
_bulk_export_lock = Lock()


def get_bulk_export_service() -> BulkExportService:
    """Get the singleton BulkExportService instance.

    Returns:
        The singleton BulkExportService instance.
    """
    global _bulk_export_service

    if _bulk_export_service is None:
        with _bulk_export_lock:
            if _bulk_export_service is None:
                logger.info("Creating singleton BulkExportService instance")
                _bulk_export_service = BulkExportService()

    return _bulk_export_service


def reset_bulk_export_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _bulk_export_service
    with _bulk_export_lock:
        _bulk_export_service = None
