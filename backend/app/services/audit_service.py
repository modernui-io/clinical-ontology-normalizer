"""HIPAA-compliant audit service for logging all PHI access.

Provides centralized audit logging with automatic PHI detection,
supporting HIPAA and 21 CFR Part 11 compliance requirements:
- Tamper-evident hash chain (SHA-256 linking each record to predecessor)
- Automatic PHI detection
- Structured audit fields (actor_id, actor_role, action, resource, patient)

This module uses a singleton pattern to ensure consistent audit logging
across all services and API endpoints.

Usage:
    from app.services.audit_service import get_audit_service

    audit = get_audit_service()
    await audit.log_access(
        user_id="user123",
        resource_type="document",
        resource_id="doc-abc",
        action="read",
        phi_accessed=True,
    )
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import (
    AuditAction,
    AuditExport,
    AuditExportFormat,
    AuditExportStatus,
    AuditLog,
    AuditResourceType,
)

logger = logging.getLogger(__name__)

# Singleton instance and lock for thread-safe initialization
_audit_instance: "AuditService | None" = None
_audit_lock = Lock()


# Patterns for PHI detection
PHI_PATTERNS = {
    # Social Security Numbers (SSN)
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    # Medical Record Numbers (MRN) - common formats
    "mrn": re.compile(r"\b(?:MRN|mrn)[:\s]*([A-Z0-9]{6,12})\b", re.IGNORECASE),
    # Phone numbers
    "phone": re.compile(r"\b(?:\+1[-.]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    # Email addresses
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    # Dates of birth (various formats)
    "dob": re.compile(
        r"\b(?:DOB|dob|date of birth|birth date)[:\s]*\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b",
        re.IGNORECASE,
    ),
    # Patient names preceded by common labels
    "patient_name": re.compile(
        r"\b(?:patient|pt|name)[:\s]+([A-Z][a-z]+\s+[A-Z][a-z]+)\b", re.IGNORECASE
    ),
    # Address patterns
    "address": re.compile(
        r"\b\d{1,5}\s+\w+\s+(?:street|st|avenue|ave|road|rd|drive|dr|lane|ln|way|court|ct)\b",
        re.IGNORECASE,
    ),
    # Insurance/Member IDs
    "insurance_id": re.compile(
        r"\b(?:member|insurance|policy|subscriber)[:\s]*(?:id|#|number)?[:\s]*([A-Z0-9]{8,15})\b",
        re.IGNORECASE,
    ),
}

# Resource types that typically contain PHI
PHI_RESOURCE_TYPES = {
    AuditResourceType.DOCUMENT.value,
    AuditResourceType.PATIENT.value,
    AuditResourceType.CLINICAL_FACT.value,
    AuditResourceType.FHIR_RESOURCE.value,
    AuditResourceType.MENTION.value,
    AuditResourceType.KNOWLEDGE_GRAPH.value,
    AuditResourceType.STRUCTURED_RESOURCE.value,
}

# API paths that typically access PHI
PHI_API_PATHS = [
    "/documents",
    "/patients",
    "/facts",
    "/mentions",
    "/fhir",
    "/export",
    "/search",
    "/coding",
    "/vocabulary",
]


class AuditService:
    """Service for HIPAA-compliant audit trail logging.

    Provides methods for logging all types of data access and modifications,
    with automatic PHI detection and support for compliance reporting.

    Features:
    - Automatic PHI detection in request/response data
    - Tamper-evident hash chain (CISO-8, 21 CFR Part 11)
    - Configurable logging levels
    - Export to JSON, CSV, and HIPAA-required formats
    - Query interface for compliance audits
    """

    # VP-Validation-1: Maximum records for single export to prevent memory issues
    MAX_EXPORT_RECORDS = 10000

    # CISO-8: Genesis hash used as previous_hash for the very first audit record
    GENESIS_HASH = "0" * 64

    def __init__(self) -> None:
        """Initialize the audit service."""
        self._initialized = True
        self._log_count = 0
        logger.info("AuditService initialized")

    @staticmethod
    def _compute_record_hash(
        previous_hash: str,
        record_id: str,
        timestamp_iso: str,
        user_id: str | None,
        action: str,
        resource_type: str,
        resource_id: str | None,
        patient_id: str | None,
    ) -> str:
        """Compute SHA-256 hash for a tamper-evident audit chain.

        The hash is computed over a canonical string representation of the
        record's key fields concatenated with the previous record's hash.
        This creates a chain where modifying any record breaks all subsequent
        hashes, making tampering detectable.

        Args:
            previous_hash: Hash of the previous audit record (or GENESIS_HASH)
            record_id: UUID of this record
            timestamp_iso: ISO-format timestamp string
            user_id: Actor who performed the action
            action: The action performed
            resource_type: Type of resource accessed
            resource_id: ID of the specific resource
            patient_id: Patient ID if applicable

        Returns:
            64-character hex SHA-256 digest
        """
        # Build canonical string with pipe delimiters for unambiguous parsing.
        # None values are represented as empty strings.
        canonical = "|".join([
            previous_hash,
            record_id,
            timestamp_iso,
            user_id or "",
            action,
            resource_type,
            resource_id or "",
            patient_id or "",
        ])
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    async def _get_latest_hash(self, db: AsyncSession) -> str:
        """Retrieve the hash of the most recent audit log record.

        Used to chain new records to the existing audit trail.

        Args:
            db: Database session

        Returns:
            The record_hash of the latest audit log, or GENESIS_HASH if
            no records exist or the latest record has no hash.
        """
        stmt = (
            select(AuditLog.record_hash)
            .where(AuditLog.record_hash.isnot(None))
            .order_by(AuditLog.timestamp.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        latest_hash = result.scalar_one_or_none()
        return latest_hash if latest_hash else self.GENESIS_HASH

    def detect_phi_in_content(self, content: str | dict | list | None) -> bool:
        """Detect if content contains PHI patterns.

        Args:
            content: Text or structured data to analyze

        Returns:
            True if PHI patterns are detected
        """
        if content is None:
            return False

        # Convert to string for pattern matching
        if isinstance(content, dict | list):
            text = json.dumps(content)
        else:
            text = str(content)

        # Check all PHI patterns
        for pattern_name, pattern in PHI_PATTERNS.items():
            if pattern.search(text):
                logger.debug(f"PHI detected: {pattern_name} pattern match")
                return True

        return False

    def detect_phi_in_path(self, path: str) -> bool:
        """Detect if API path typically accesses PHI.

        Args:
            path: API request path

        Returns:
            True if path typically involves PHI access
        """
        if not path:
            return False

        path_lower = path.lower()
        return any(phi_path in path_lower for phi_path in PHI_API_PATHS)

    def detect_phi_in_resource(self, resource_type: str) -> bool:
        """Detect if resource type typically contains PHI.

        Args:
            resource_type: Type of resource being accessed

        Returns:
            True if resource type typically contains PHI
        """
        return resource_type in PHI_RESOURCE_TYPES

    def auto_detect_phi(
        self,
        resource_type: str | None = None,
        request_path: str | None = None,
        request_body: str | dict | None = None,
        response_body: str | dict | None = None,
    ) -> bool:
        """Automatically detect if PHI is being accessed.

        Combines multiple detection methods to determine PHI access.

        Args:
            resource_type: Type of resource being accessed
            request_path: API request path
            request_body: Request body content
            response_body: Response body content

        Returns:
            True if PHI access is detected
        """
        # Check resource type
        if resource_type and self.detect_phi_in_resource(resource_type):
            return True

        # Check request path
        if request_path and self.detect_phi_in_path(request_path):
            return True

        # Check request body for PHI patterns
        if request_body and self.detect_phi_in_content(request_body):
            return True

        # Check response body for PHI patterns
        if response_body and self.detect_phi_in_content(response_body):
            return True

        return False

    async def log_event(
        self,
        db: AsyncSession,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        user_id: str | None = None,
        actor_role: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None,
        request_method: str | None = None,
        request_path: str | None = None,
        response_status: int | None = None,
        details: dict[str, Any] | None = None,
        phi_accessed: bool | None = None,
        patient_id: str | None = None,
        session_id: str | None = None,
        success: bool = True,
        error_message: str | None = None,
    ) -> AuditLog:
        """Log an audit event with tamper-evident hash chain.

        This is the core logging method that all other log methods use.
        Each record is chained to the previous via SHA-256 hash, creating
        a tamper-evident audit trail per HIPAA and 21 CFR Part 11.

        Args:
            db: Database session
            action: The action being performed
            resource_type: Type of resource being accessed
            resource_id: ID of specific resource (if applicable)
            user_id: ID of user performing action (actor_id)
            actor_role: Role of the user performing the action
            ip_address: Client IP address
            user_agent: Client user agent string
            request_id: Unique request identifier
            request_method: HTTP method
            request_path: API path
            response_status: HTTP response status code
            details: Additional context as JSON
            phi_accessed: Whether PHI was accessed (auto-detected if None)
            patient_id: Patient ID if applicable
            session_id: Session identifier
            success: Whether operation succeeded
            error_message: Error message if failed

        Returns:
            The created AuditLog entry
        """
        # Auto-detect PHI if not explicitly specified
        if phi_accessed is None:
            phi_accessed = self.auto_detect_phi(
                resource_type=resource_type,
                request_path=request_path,
                request_body=details.get("request_body") if details else None,
                response_body=details.get("response_body") if details else None,
            )

        # CISO-8: Compute hash chain
        record_id = str(uuid4())
        record_timestamp = datetime.now(timezone.utc)
        timestamp_iso = record_timestamp.isoformat()

        try:
            previous_hash = await self._get_latest_hash(db)
        except Exception:
            # If we cannot read the chain (e.g., empty table, connection issue),
            # use genesis hash so the record is still written.
            logger.warning("Could not retrieve latest audit hash; using genesis hash")
            previous_hash = self.GENESIS_HASH

        record_hash = self._compute_record_hash(
            previous_hash=previous_hash,
            record_id=record_id,
            timestamp_iso=timestamp_iso,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            patient_id=patient_id,
        )

        # Create audit log entry
        audit_log = AuditLog(
            id=record_id,
            timestamp=record_timestamp,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            request_method=request_method,
            request_path=request_path,
            response_status=response_status,
            details=details,
            phi_accessed=phi_accessed,
            patient_id=patient_id,
            session_id=session_id,
            success=success,
            error_message=error_message,
            actor_role=actor_role,
            record_hash=record_hash,
            previous_hash=previous_hash,
        )

        db.add(audit_log)
        await db.flush()

        self._log_count += 1

        if phi_accessed:
            logger.info(
                f"PHI ACCESS LOGGED: user={user_id}, action={action}, "
                f"resource={resource_type}/{resource_id}, patient={patient_id}"
            )

        return audit_log

    async def log_access(
        self,
        db: AsyncSession,
        user_id: str | None,
        resource_type: str,
        resource_id: str | None = None,
        patient_id: str | None = None,
        phi_accessed: bool | None = None,
        ip_address: str | None = None,
        request_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Log a data access (read) event.

        Args:
            db: Database session
            user_id: ID of user accessing data
            resource_type: Type of resource being accessed
            resource_id: ID of specific resource
            patient_id: Patient ID if applicable
            phi_accessed: Whether PHI was accessed
            ip_address: Client IP address
            request_id: Unique request identifier
            details: Additional context

        Returns:
            The created AuditLog entry
        """
        return await self.log_event(
            db=db,
            action=AuditAction.READ.value,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            patient_id=patient_id,
            phi_accessed=phi_accessed,
            ip_address=ip_address,
            request_id=request_id,
            details=details,
        )

    async def log_create(
        self,
        db: AsyncSession,
        user_id: str | None,
        resource_type: str,
        resource_id: str,
        patient_id: str | None = None,
        phi_accessed: bool | None = None,
        ip_address: str | None = None,
        request_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Log a data creation event.

        Args:
            db: Database session
            user_id: ID of user creating data
            resource_type: Type of resource being created
            resource_id: ID of created resource
            patient_id: Patient ID if applicable
            phi_accessed: Whether PHI was involved
            ip_address: Client IP address
            request_id: Unique request identifier
            details: Additional context

        Returns:
            The created AuditLog entry
        """
        return await self.log_event(
            db=db,
            action=AuditAction.CREATE.value,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            patient_id=patient_id,
            phi_accessed=phi_accessed,
            ip_address=ip_address,
            request_id=request_id,
            details=details,
        )

    async def log_update(
        self,
        db: AsyncSession,
        user_id: str | None,
        resource_type: str,
        resource_id: str,
        patient_id: str | None = None,
        phi_accessed: bool | None = None,
        ip_address: str | None = None,
        request_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Log a data update event.

        Args:
            db: Database session
            user_id: ID of user updating data
            resource_type: Type of resource being updated
            resource_id: ID of updated resource
            patient_id: Patient ID if applicable
            phi_accessed: Whether PHI was involved
            ip_address: Client IP address
            request_id: Unique request identifier
            details: Additional context (should include changed fields)

        Returns:
            The created AuditLog entry
        """
        return await self.log_event(
            db=db,
            action=AuditAction.UPDATE.value,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            patient_id=patient_id,
            phi_accessed=phi_accessed,
            ip_address=ip_address,
            request_id=request_id,
            details=details,
        )

    async def log_delete(
        self,
        db: AsyncSession,
        user_id: str | None,
        resource_type: str,
        resource_id: str,
        patient_id: str | None = None,
        phi_accessed: bool | None = None,
        ip_address: str | None = None,
        request_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Log a data deletion event.

        Args:
            db: Database session
            user_id: ID of user deleting data
            resource_type: Type of resource being deleted
            resource_id: ID of deleted resource
            patient_id: Patient ID if applicable
            phi_accessed: Whether PHI was involved
            ip_address: Client IP address
            request_id: Unique request identifier
            details: Additional context

        Returns:
            The created AuditLog entry
        """
        return await self.log_event(
            db=db,
            action=AuditAction.DELETE.value,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            patient_id=patient_id,
            phi_accessed=phi_accessed,
            ip_address=ip_address,
            request_id=request_id,
            details=details,
        )

    async def log_export(
        self,
        db: AsyncSession,
        user_id: str | None,
        resource_type: str,
        resource_ids: list[str] | None = None,
        patient_ids: list[str] | None = None,
        export_format: str = "json",
        ip_address: str | None = None,
        request_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Log a data export event.

        Args:
            db: Database session
            user_id: ID of user exporting data
            resource_type: Type of resource being exported
            resource_ids: IDs of exported resources
            patient_ids: Patient IDs if applicable
            export_format: Export file format
            ip_address: Client IP address
            request_id: Unique request identifier
            details: Additional context

        Returns:
            The created AuditLog entry
        """
        export_details = details or {}
        export_details["export_format"] = export_format
        if resource_ids:
            export_details["resource_count"] = len(resource_ids)
            export_details["resource_ids"] = resource_ids[:10]  # Limit for storage
        if patient_ids:
            export_details["patient_count"] = len(patient_ids)
            export_details["patient_ids"] = patient_ids[:10]  # Limit for storage

        return await self.log_event(
            db=db,
            action=AuditAction.EXPORT.value,
            resource_type=resource_type,
            resource_id=None,
            user_id=user_id,
            patient_id=patient_ids[0] if patient_ids else None,
            phi_accessed=True,  # Exports always involve PHI
            ip_address=ip_address,
            request_id=request_id,
            details=export_details,
        )

    async def log_search(
        self,
        db: AsyncSession,
        user_id: str | None,
        resource_type: str,
        search_query: str | dict,
        result_count: int = 0,
        patient_id: str | None = None,
        phi_accessed: bool | None = None,
        ip_address: str | None = None,
        request_id: str | None = None,
    ) -> AuditLog:
        """Log a search event.

        Args:
            db: Database session
            user_id: ID of user performing search
            resource_type: Type of resource being searched
            search_query: Search query string or parameters
            result_count: Number of results returned
            patient_id: Patient ID if search is patient-specific
            phi_accessed: Whether PHI was accessed
            ip_address: Client IP address
            request_id: Unique request identifier

        Returns:
            The created AuditLog entry
        """
        details = {
            "search_query": search_query if isinstance(search_query, str) else json.dumps(search_query),
            "result_count": result_count,
        }

        return await self.log_event(
            db=db,
            action=AuditAction.SEARCH.value,
            resource_type=resource_type,
            resource_id=None,
            user_id=user_id,
            patient_id=patient_id,
            phi_accessed=phi_accessed,
            ip_address=ip_address,
            request_id=request_id,
            details=details,
        )

    async def query_logs(
        self,
        db: AsyncSession,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        user_id: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        patient_id: str | None = None,
        phi_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AuditLog], int]:
        """Query audit logs with filters.

        Args:
            db: Database session
            start_date: Filter by start timestamp
            end_date: Filter by end timestamp
            user_id: Filter by user ID
            action: Filter by action type
            resource_type: Filter by resource type
            resource_id: Filter by resource ID
            patient_id: Filter by patient ID
            phi_only: Only return PHI access events
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            Tuple of (audit log entries, total count)
        """
        # Build query conditions
        conditions = []

        if start_date:
            conditions.append(AuditLog.timestamp >= start_date)
        if end_date:
            conditions.append(AuditLog.timestamp <= end_date)
        if user_id:
            conditions.append(AuditLog.user_id == user_id)
        if action:
            conditions.append(AuditLog.action == action)
        if resource_type:
            conditions.append(AuditLog.resource_type == resource_type)
        if resource_id:
            conditions.append(AuditLog.resource_id == resource_id)
        if patient_id:
            conditions.append(AuditLog.patient_id == patient_id)
        if phi_only:
            conditions.append(AuditLog.phi_accessed == True)  # noqa: E712

        # Get total count
        count_stmt = select(func.count(AuditLog.id))
        if conditions:
            count_stmt = count_stmt.where(and_(*conditions))
        count_result = await db.execute(count_stmt)
        total_count = count_result.scalar() or 0

        # Get paginated results
        query = select(AuditLog).order_by(AuditLog.timestamp.desc())
        if conditions:
            query = query.where(and_(*conditions))
        query = query.limit(limit).offset(offset)

        result = await db.execute(query)
        logs = list(result.scalars().all())

        return logs, total_count

    async def create_export(
        self,
        db: AsyncSession,
        start_date: datetime,
        end_date: datetime,
        requested_by: str | None = None,
        export_format: str = "json",
        filters: dict[str, Any] | None = None,
    ) -> AuditExport:
        """Create an audit export record.

        Args:
            db: Database session
            start_date: Export start date
            end_date: Export end date
            requested_by: User requesting export
            export_format: Export format (json, csv, hipaa)
            filters: Additional query filters

        Returns:
            The created AuditExport entry
        """
        export_record = AuditExport(
            id=str(uuid4()),
            export_date=datetime.now(timezone.utc),
            start_date=start_date,
            end_date=end_date,
            status=AuditExportStatus.PENDING.value,
            requested_by=requested_by,
            format=export_format,
            filters=filters,
        )

        db.add(export_record)
        await db.flush()

        return export_record

    async def process_export(
        self,
        db: AsyncSession,
        export_id: str,
        output_dir: str | Path = "exports/audit",
    ) -> AuditExport:
        """Process an audit export request.

        Generates the export file and updates the export record.

        Args:
            db: Database session
            export_id: ID of export to process
            output_dir: Directory for export files

        Returns:
            The updated AuditExport entry
        """
        # Get export record
        stmt = select(AuditExport).where(AuditExport.id == export_id)
        result = await db.execute(stmt)
        export_record = result.scalar_one_or_none()

        if not export_record:
            raise ValueError(f"Export record not found: {export_id}")

        # Update status to processing
        export_record.status = AuditExportStatus.PROCESSING.value
        export_record.started_at = datetime.now(timezone.utc)
        await db.flush()

        try:
            # Build query filters
            filters = export_record.filters or {}

            # Query logs for the date range
            logs, total_count = await self.query_logs(
                db=db,
                start_date=export_record.start_date,
                end_date=export_record.end_date,
                user_id=filters.get("user_id"),
                action=filters.get("action"),
                resource_type=filters.get("resource_type"),
                patient_id=filters.get("patient_id"),
                phi_only=filters.get("phi_only", False),
                limit=self.MAX_EXPORT_RECORDS,  # VP-Validation-1: Capped for memory safety
                offset=0,
            )

            # Generate export content
            export_format = export_record.format
            if export_format == AuditExportFormat.JSON.value:
                content, filename = self._export_to_json(logs, export_id)
            elif export_format == AuditExportFormat.CSV.value:
                content, filename = self._export_to_csv(logs, export_id)
            elif export_format == AuditExportFormat.HIPAA.value:
                content, filename = self._export_to_hipaa(logs, export_id)
            else:
                content, filename = self._export_to_json(logs, export_id)

            # Create output directory
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            # Write file
            file_path = output_path / filename
            if isinstance(content, str):
                file_path.write_text(content)
            else:
                file_path.write_bytes(content)

            # Calculate checksum
            content_bytes = content.encode() if isinstance(content, str) else content
            checksum = hashlib.sha256(content_bytes).hexdigest()

            # Update export record
            export_record.file_path = str(file_path)
            export_record.file_size_bytes = len(content_bytes)
            export_record.record_count = len(logs)
            export_record.checksum = checksum
            export_record.status = AuditExportStatus.COMPLETED.value
            export_record.completed_at = datetime.now(timezone.utc)

        except Exception as e:
            logger.error(f"Export processing failed: {e}")
            export_record.status = AuditExportStatus.FAILED.value
            export_record.error_message = str(e)
            export_record.completed_at = datetime.now(timezone.utc)

        await db.flush()
        return export_record

    def _export_to_json(
        self, logs: list[AuditLog], export_id: str
    ) -> tuple[str, str]:
        """Export logs to JSON format.

        Args:
            logs: Audit log entries to export
            export_id: Export ID for filename

        Returns:
            Tuple of (JSON content, filename)
        """
        data = {
            "export_id": export_id,
            "export_timestamp": datetime.now(timezone.utc).isoformat(),
            "record_count": len(logs),
            "records": [self._log_to_dict(log) for log in logs],
        }
        content = json.dumps(data, indent=2, default=str)
        filename = f"audit_export_{export_id}.json"
        return content, filename

    def _export_to_csv(
        self, logs: list[AuditLog], export_id: str
    ) -> tuple[str, str]:
        """Export logs to CSV format.

        Args:
            logs: Audit log entries to export
            export_id: Export ID for filename

        Returns:
            Tuple of (CSV content, filename)
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # Header row
        headers = [
            "id",
            "timestamp",
            "user_id",
            "actor_role",
            "action",
            "resource_type",
            "resource_id",
            "patient_id",
            "ip_address",
            "user_agent",
            "request_method",
            "request_path",
            "response_status",
            "phi_accessed",
            "success",
            "error_message",
            "record_hash",
            "previous_hash",
        ]
        writer.writerow(headers)

        # Data rows
        for log in logs:
            writer.writerow([
                log.id,
                log.timestamp.isoformat() if log.timestamp else "",
                log.user_id or "",
                log.actor_role or "",
                log.action,
                log.resource_type,
                log.resource_id or "",
                log.patient_id or "",
                log.ip_address or "",
                log.user_agent or "",
                log.request_method or "",
                log.request_path or "",
                log.response_status or "",
                log.phi_accessed,
                log.success,
                log.error_message or "",
                log.record_hash or "",
                log.previous_hash or "",
            ])

        content = output.getvalue()
        filename = f"audit_export_{export_id}.csv"
        return content, filename

    def _export_to_hipaa(
        self, logs: list[AuditLog], export_id: str
    ) -> tuple[str, str]:
        """Export logs to HIPAA-required format.

        HIPAA requires specific fields for audit trails:
        - Date and time of access
        - User identification
        - Type of action
        - Identification of patient whose information was accessed
        - Identification of the information accessed

        Args:
            logs: Audit log entries to export
            export_id: Export ID for filename

        Returns:
            Tuple of (JSON content, filename)
        """
        hipaa_records = []
        for log in logs:
            hipaa_record = {
                # Required HIPAA fields
                "access_datetime": log.timestamp.isoformat() if log.timestamp else None,
                "user_identification": log.user_id,
                "user_role": log.actor_role,
                "action_type": log.action,
                "patient_identification": log.patient_id,
                "information_accessed": {
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                },
                "access_location": log.ip_address,
                "access_outcome": "success" if log.success else "failure",
                # Additional recommended fields
                "phi_involved": log.phi_accessed,
                "session_id": log.session_id,
                "request_id": log.request_id,
                "error_details": log.error_message,
                # 21 CFR Part 11 integrity fields
                "record_hash": log.record_hash,
                "previous_hash": log.previous_hash,
            }
            hipaa_records.append(hipaa_record)

        data = {
            "hipaa_audit_report": {
                "export_id": export_id,
                "export_timestamp": datetime.now(timezone.utc).isoformat(),
                "report_type": "HIPAA Audit Trail",
                "record_count": len(logs),
                "covered_entity": "Clinical Ontology Normalizer",
                "records": hipaa_records,
            }
        }

        content = json.dumps(data, indent=2, default=str)
        filename = f"hipaa_audit_{export_id}.json"
        return content, filename

    def _log_to_dict(self, log: AuditLog) -> dict[str, Any]:
        """Convert AuditLog to dictionary.

        Args:
            log: Audit log entry

        Returns:
            Dictionary representation
        """
        return {
            "id": log.id,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            "user_id": log.user_id,
            "actor_role": log.actor_role,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "ip_address": log.ip_address,
            "user_agent": log.user_agent,
            "request_id": log.request_id,
            "request_method": log.request_method,
            "request_path": log.request_path,
            "response_status": log.response_status,
            "details": log.details,
            "phi_accessed": log.phi_accessed,
            "patient_id": log.patient_id,
            "session_id": log.session_id,
            "success": log.success,
            "error_message": log.error_message,
            "record_hash": log.record_hash,
            "previous_hash": log.previous_hash,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }

    def get_stats(self) -> dict[str, Any]:
        """Get audit service statistics.

        Returns:
            Dictionary with service stats
        """
        return {
            "service": "AuditService",
            "initialized": self._initialized,
            "log_count": self._log_count,
            "phi_patterns": len(PHI_PATTERNS),
            "phi_resource_types": len(PHI_RESOURCE_TYPES),
        }


def get_audit_service() -> AuditService:
    """Get the singleton AuditService instance.

    Uses double-checked locking for thread-safe initialization.

    Returns:
        The singleton AuditService instance
    """
    global _audit_instance

    if _audit_instance is None:
        with _audit_lock:
            if _audit_instance is None:
                _audit_instance = AuditService()
                logger.info("AuditService singleton created")

    return _audit_instance
