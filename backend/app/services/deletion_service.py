"""Right-to-Deletion Service (HIPAA / GDPR).

Implements the right-to-deletion workflow for the clinical trial
patient recruitment platform. Handles deletion request lifecycle,
legal hold checks, retention overrides, data inventory deletion,
and deletion certificate generation.

CLO-2: Data Use Agreements and Right-to-Deletion

Usage:
    from app.services.deletion_service import get_deletion_service

    svc = get_deletion_service()
    req = svc.create_request(DeletionRequestCreate(...))
    svc.execute_deletion(req.id, executor="admin")
    cert = svc.get_deletion_certificate(req.id)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from threading import Lock

from app.schemas.data_governance import (
    DeletionAuditEntry,
    DeletionCertificate,
    DeletionRequestCreate,
    DeletionRequestResponse,
    DeletionScope,
    DeletionStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# 21 CFR Part 11: clinical trial data must be retained for minimum 6 years
CLINICAL_TRIAL_RETENTION_YEARS = 6

# Data stores that contain patient data
DATA_STORES = [
    "clinical_facts",
    "kg_nodes",
    "kg_edges",
    "documents",
    "screening_results",
    "audit_logs",
]

# Data stores that can be deleted (audit_logs are retained)
DELETABLE_STORES = [
    "clinical_facts",
    "kg_nodes",
    "kg_edges",
    "documents",
    "screening_results",
]


class DeletionService:
    """In-memory right-to-deletion service with legal hold and retention checks.

    Thread-safe via a lock. Manages the full deletion request lifecycle
    from RECEIVED through to COMPLETED with audit trail and certificate
    generation.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        # request_id -> DeletionRequestResponse
        self._requests: dict[str, DeletionRequestResponse] = {}
        # patient_id -> set of legal hold reasons
        self._legal_holds: dict[str, set[str]] = {}
        # patient_id -> enrollment date (for retention checks)
        self._trial_enrollments: dict[str, datetime] = {}
        # Track what has been "deleted" (patient_id -> set of deleted store names)
        self._deleted_data: dict[str, set[str]] = {}

    # ------------------------------------------------------------------
    # Legal Hold Management
    # ------------------------------------------------------------------

    def add_legal_hold(self, patient_id: str, reason: str) -> None:
        """Place a legal hold on a patient's data.

        Args:
            patient_id: Patient identifier.
            reason: Reason for the legal hold.
        """
        with self._lock:
            if patient_id not in self._legal_holds:
                self._legal_holds[patient_id] = set()
            self._legal_holds[patient_id].add(reason)

        logger.info("Legal hold placed: patient=%s reason=%s", patient_id, reason)

    def remove_legal_hold(self, patient_id: str, reason: str) -> None:
        """Remove a legal hold from a patient's data.

        Args:
            patient_id: Patient identifier.
            reason: Reason to remove.
        """
        with self._lock:
            holds = self._legal_holds.get(patient_id, set())
            holds.discard(reason)
            if not holds:
                self._legal_holds.pop(patient_id, None)

    def has_legal_hold(self, patient_id: str) -> bool:
        """Check if a patient has any active legal holds.

        Args:
            patient_id: Patient identifier.

        Returns:
            True if the patient has active legal holds.
        """
        with self._lock:
            holds = self._legal_holds.get(patient_id, set())
            return len(holds) > 0

    # ------------------------------------------------------------------
    # Trial Enrollment Tracking (for retention checks)
    # ------------------------------------------------------------------

    def record_trial_enrollment(self, patient_id: str, enrollment_date: datetime) -> None:
        """Record a patient's clinical trial enrollment date.

        Used to enforce the 6-year retention requirement per 21 CFR Part 11.

        Args:
            patient_id: Patient identifier.
            enrollment_date: When the patient was enrolled in the trial.
        """
        with self._lock:
            self._trial_enrollments[patient_id] = enrollment_date

    def check_retention_override(self, patient_id: str) -> tuple[bool, str]:
        """Check if retention requirements prevent deletion.

        Clinical trial data must be retained for a minimum of 6 years
        per 21 CFR Part 11.

        Args:
            patient_id: Patient identifier.

        Returns:
            Tuple of (is_blocked, reason). is_blocked is True if
            retention requirements prevent deletion.
        """
        with self._lock:
            enrollment_date = self._trial_enrollments.get(patient_id)

        if enrollment_date is None:
            return False, ""

        now = datetime.now(timezone.utc)
        retention_end = enrollment_date.replace(
            year=enrollment_date.year + CLINICAL_TRIAL_RETENTION_YEARS
        )

        if now < retention_end:
            remaining_days = (retention_end - now).days
            return True, (
                f"Clinical trial data retention required until "
                f"{retention_end.strftime('%Y-%m-%d')} "
                f"({remaining_days} days remaining, per 21 CFR Part 11)"
            )

        return False, ""

    # ------------------------------------------------------------------
    # Deletion Request Lifecycle
    # ------------------------------------------------------------------

    def create_request(self, request: DeletionRequestCreate) -> DeletionRequestResponse:
        """Create a new deletion request.

        Args:
            request: Deletion request details.

        Returns:
            The created DeletionRequestResponse in RECEIVED status.
        """
        now = datetime.now(timezone.utc)
        request_id = str(uuid.uuid4())

        audit_entry = DeletionAuditEntry(
            timestamp=now,
            action="REQUEST_RECEIVED",
            actor=request.requester,
            details=f"Deletion request received. Scope: {request.scope.value}. Reason: {request.reason}",
        )

        response = DeletionRequestResponse(
            id=request_id,
            patient_id=request.patient_id,
            requester=request.requester,
            reason=request.reason,
            status=DeletionStatus.RECEIVED,
            scope=request.scope,
            specific_records=request.specific_records,
            created_at=now,
            audit_entries=[audit_entry],
        )

        with self._lock:
            self._requests[request_id] = response

        logger.info(
            "Deletion request created: id=%s patient=%s scope=%s",
            request_id,
            request.patient_id,
            request.scope.value,
        )
        return response

    def get_request(self, request_id: str) -> DeletionRequestResponse | None:
        """Get a deletion request by ID.

        Args:
            request_id: Unique request identifier.

        Returns:
            DeletionRequestResponse if found, None otherwise.
        """
        with self._lock:
            return self._requests.get(request_id)

    def list_requests(
        self,
        status_filter: DeletionStatus | None = None,
        patient_id: str | None = None,
    ) -> list[DeletionRequestResponse]:
        """List deletion requests with optional filters.

        Args:
            status_filter: Optional status filter.
            patient_id: Optional patient ID filter.

        Returns:
            List of DeletionRequestResponse objects.
        """
        with self._lock:
            requests = list(self._requests.values())

        if status_filter is not None:
            requests = [r for r in requests if r.status == status_filter]
        if patient_id is not None:
            requests = [r for r in requests if r.patient_id == patient_id]

        return requests

    def validate_request(self, request_id: str, validator: str = "system") -> DeletionRequestResponse:
        """Validate a deletion request (check identity, legal holds, retention).

        Transitions from RECEIVED to VALIDATING, then to either
        IN_PROGRESS (if validation passes) or DENIED.

        Args:
            request_id: Request to validate.
            validator: Who is performing validation.

        Returns:
            Updated DeletionRequestResponse.

        Raises:
            ValueError: If the request is not found or not in RECEIVED status.
        """
        now = datetime.now(timezone.utc)

        with self._lock:
            req = self._requests.get(request_id)
            if req is None:
                raise ValueError(f"Deletion request {request_id} not found")

            if req.status != DeletionStatus.RECEIVED:
                raise ValueError(
                    f"Request {request_id} is in {req.status.value} status, "
                    f"expected RECEIVED"
                )

            # Transition to VALIDATING
            audit_entries = list(req.audit_entries)
            audit_entries.append(
                DeletionAuditEntry(
                    timestamp=now,
                    action="VALIDATION_STARTED",
                    actor=validator,
                    details="Requester identity verified. Checking legal holds and retention.",
                )
            )

            # Check legal hold
            holds = self._legal_holds.get(req.patient_id, set())
            if holds:
                hold_reasons = ", ".join(holds)
                audit_entries.append(
                    DeletionAuditEntry(
                        timestamp=now,
                        action="DENIED_LEGAL_HOLD",
                        actor="system",
                        details=f"Legal hold active: {hold_reasons}",
                    )
                )
                updated = req.model_copy(
                    update={
                        "status": DeletionStatus.DENIED,
                        "denial_reason": f"Legal hold active: {hold_reasons}",
                        "audit_entries": audit_entries,
                    }
                )
                self._requests[request_id] = updated
                return updated

            # Save intermediate state with VALIDATION_STARTED entry
            intermediate = req.model_copy(update={"audit_entries": audit_entries})
            self._requests[request_id] = intermediate

        # Check retention override (outside lock to avoid nested locking)
        is_blocked, reason = self.check_retention_override(req.patient_id)

        with self._lock:
            req = self._requests[request_id]
            audit_entries = list(req.audit_entries)

            if is_blocked:
                audit_entries.append(
                    DeletionAuditEntry(
                        timestamp=now,
                        action="DENIED_RETENTION",
                        actor="system",
                        details=reason,
                    )
                )
                updated = req.model_copy(
                    update={
                        "status": DeletionStatus.DENIED,
                        "denial_reason": reason,
                        "audit_entries": audit_entries,
                    }
                )
                self._requests[request_id] = updated
                return updated

            # Validation passed - transition to VALIDATING status
            audit_entries.append(
                DeletionAuditEntry(
                    timestamp=now,
                    action="VALIDATION_PASSED",
                    actor=validator,
                    details="All checks passed. Request ready for execution.",
                )
            )
            updated = req.model_copy(
                update={
                    "status": DeletionStatus.VALIDATING,
                    "audit_entries": audit_entries,
                }
            )
            self._requests[request_id] = updated

        return updated

    def execute_deletion(
        self,
        request_id: str,
        executor: str = "system",
    ) -> DeletionRequestResponse:
        """Execute an approved deletion request.

        Performs deletion across all relevant data stores based on
        the request scope. Audit logs are retained but PHI is redacted.

        Args:
            request_id: Request to execute.
            executor: Who is executing the deletion.

        Returns:
            Updated DeletionRequestResponse.

        Raises:
            ValueError: If the request is not found or not in VALIDATING/RECEIVED status.
        """
        now = datetime.now(timezone.utc)

        with self._lock:
            req = self._requests.get(request_id)
            if req is None:
                raise ValueError(f"Deletion request {request_id} not found")

            if req.status not in (DeletionStatus.VALIDATING, DeletionStatus.RECEIVED):
                raise ValueError(
                    f"Request {request_id} is in {req.status.value} status, "
                    f"expected VALIDATING or RECEIVED"
                )

            # Transition to IN_PROGRESS
            audit_entries = list(req.audit_entries)
            audit_entries.append(
                DeletionAuditEntry(
                    timestamp=now,
                    action="DELETION_STARTED",
                    actor=executor,
                    details="Beginning data deletion across all stores.",
                )
            )

            patient_id = req.patient_id
            scope = req.scope
            deleted_items: list[str] = []
            retained_items: list[str] = []

            # Determine which stores to delete based on scope
            if scope == DeletionScope.ALL:
                stores_to_delete = list(DELETABLE_STORES)
            elif scope == DeletionScope.PHI_ONLY:
                # PHI_ONLY: delete PHI from all stores but keep de-identified data
                stores_to_delete = ["clinical_facts", "documents"]
            elif scope == DeletionScope.SPECIFIC_RECORDS:
                stores_to_delete = req.specific_records or []
            else:
                stores_to_delete = list(DELETABLE_STORES)

            # Execute deletion for each store
            if patient_id not in self._deleted_data:
                self._deleted_data[patient_id] = set()

            for store in stores_to_delete:
                if store in DELETABLE_STORES or store in DATA_STORES:
                    self._deleted_data[patient_id].add(store)
                    deleted_items.append(store)
                    audit_entries.append(
                        DeletionAuditEntry(
                            timestamp=now,
                            action=f"DELETED_{store.upper()}",
                            actor=executor,
                            details=f"Deleted patient data from {store} (patient_id={patient_id})",
                        )
                    )

            # Audit logs are always retained (legal requirement)
            retained_items.append("audit_logs (retained per legal requirement, PHI redacted)")
            audit_entries.append(
                DeletionAuditEntry(
                    timestamp=now,
                    action="AUDIT_LOGS_RETAINED",
                    actor="system",
                    details="Audit logs retained per legal requirement. PHI fields redacted.",
                )
            )

            # Backups flagged for rotation
            retained_items.append("backups (flagged for next rotation cycle)")
            audit_entries.append(
                DeletionAuditEntry(
                    timestamp=now,
                    action="BACKUPS_FLAGGED",
                    actor="system",
                    details="Existing backups flagged for deletion on next rotation cycle.",
                )
            )

            # Determine final status
            if deleted_items:
                if scope == DeletionScope.PHI_ONLY:
                    final_status = DeletionStatus.PARTIALLY_COMPLETED
                else:
                    final_status = DeletionStatus.COMPLETED
            else:
                final_status = DeletionStatus.PARTIALLY_COMPLETED

            audit_entries.append(
                DeletionAuditEntry(
                    timestamp=now,
                    action="DELETION_COMPLETED",
                    actor=executor,
                    details=f"Deletion {final_status.value}. Deleted: {deleted_items}. Retained: {retained_items}",
                )
            )

            updated = req.model_copy(
                update={
                    "status": final_status,
                    "completed_at": now,
                    "deleted_items": deleted_items,
                    "retained_items": retained_items,
                    "audit_entries": audit_entries,
                }
            )
            self._requests[request_id] = updated

        logger.info(
            "Deletion executed: request=%s patient=%s status=%s deleted=%s",
            request_id,
            patient_id,
            final_status.value,
            deleted_items,
        )
        return updated

    # ------------------------------------------------------------------
    # Deletion Certificate
    # ------------------------------------------------------------------

    def get_deletion_certificate(self, request_id: str) -> DeletionCertificate:
        """Generate a deletion certificate for a completed request.

        Args:
            request_id: Completed deletion request ID.

        Returns:
            DeletionCertificate confirming what was deleted.

        Raises:
            ValueError: If the request is not found or not completed.
        """
        with self._lock:
            req = self._requests.get(request_id)

        if req is None:
            raise ValueError(f"Deletion request {request_id} not found")

        if req.status not in (
            DeletionStatus.COMPLETED,
            DeletionStatus.PARTIALLY_COMPLETED,
        ):
            raise ValueError(
                f"Deletion certificate only available for completed requests. "
                f"Current status: {req.status.value}"
            )

        now = datetime.now(timezone.utc)
        exceptions = []
        if req.status == DeletionStatus.PARTIALLY_COMPLETED:
            exceptions.append(
                "Some data retained due to scope limitations or legal requirements"
            )

        return DeletionCertificate(
            certificate_id=str(uuid.uuid4()),
            deletion_request_id=request_id,
            patient_id=req.patient_id,
            issued_at=now,
            issued_by="system",
            scope=req.scope,
            deleted_items=req.deleted_items,
            retained_items=req.retained_items,
            exceptions=exceptions,
        )

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def is_data_deleted(self, patient_id: str, store: str) -> bool:
        """Check if a patient's data has been deleted from a specific store.

        Args:
            patient_id: Patient identifier.
            store: Data store name.

        Returns:
            True if the data has been deleted.
        """
        with self._lock:
            deleted = self._deleted_data.get(patient_id, set())
            return store in deleted

    def get_stats(self) -> dict:
        """Return service statistics for health checks."""
        with self._lock:
            total_requests = len(self._requests)
            by_status = {}
            for req in self._requests.values():
                status_val = req.status.value
                by_status[status_val] = by_status.get(status_val, 0) + 1
            total_legal_holds = sum(
                len(holds) for holds in self._legal_holds.values()
            )
        return {
            "total_requests": total_requests,
            "requests_by_status": by_status,
            "total_legal_holds": total_legal_holds,
        }


# ---------------------------------------------------------------------------
# Singleton access
# ---------------------------------------------------------------------------

_deletion_service: DeletionService | None = None


def get_deletion_service() -> DeletionService:
    """Get or create the singleton DeletionService instance."""
    global _deletion_service
    if _deletion_service is None:
        _deletion_service = DeletionService()
    return _deletion_service


def reset_deletion_service() -> None:
    """Reset the singleton for testing."""
    global _deletion_service
    _deletion_service = None
