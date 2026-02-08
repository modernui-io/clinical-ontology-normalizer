"""Consent Management Service for HIPAA compliance.

Provides in-memory consent tracking with full audit trail for the
clinical trial patient recruitment platform. Every access to patient
PHI should verify consent via this service.

Usage:
    from app.services.consent_service import get_consent_service

    svc = get_consent_service()
    record = svc.record_consent("patient-1", ConsentType.SCREENING_CONSENT, ...)
    status = svc.check_consent("patient-1", ConsentType.SCREENING_CONSENT)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from threading import Lock

from app.schemas.consent import (
    ConsentAuditEntry,
    ConsentAuditTrail,
    ConsentCheck,
    ConsentRecord,
    ConsentStatus,
    ConsentStatusValue,
    ConsentType,
    DataUsePurpose,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Purpose-to-consent-type mapping
# ---------------------------------------------------------------------------

# Which consent types authorize which purposes.
# A purpose is authorized if the patient has an active consent of any of
# the mapped types.
PURPOSE_CONSENT_MAP: dict[DataUsePurpose, list[ConsentType]] = {
    DataUsePurpose.TREATMENT: [
        ConsentType.HIPAA_AUTHORIZATION,
    ],
    DataUsePurpose.PAYMENT: [
        ConsentType.HIPAA_AUTHORIZATION,
    ],
    DataUsePurpose.OPERATIONS: [
        ConsentType.HIPAA_AUTHORIZATION,
    ],
    DataUsePurpose.RESEARCH: [
        ConsentType.RESEARCH_PARTICIPATION,
        ConsentType.HIPAA_AUTHORIZATION,
    ],
    DataUsePurpose.SCREENING: [
        ConsentType.SCREENING_CONSENT,
        ConsentType.HIPAA_AUTHORIZATION,
    ],
    DataUsePurpose.MARKETING: [
        # Marketing requires explicit HIPAA authorization with
        # marketing-specific scope -- handled by scope check
        ConsentType.HIPAA_AUTHORIZATION,
    ],
}


class ConsentService:
    """In-memory consent management with audit trail.

    Thread-safe via a reentrant lock. Designed for fast consent
    checks on every patient data access.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        # patient_id -> consent_type -> ConsentRecord
        self._consents: dict[str, dict[ConsentType, ConsentRecord]] = {}
        # patient_id -> list of audit entries
        self._audit_trail: dict[str, list[ConsentAuditEntry]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_consent(
        self,
        patient_id: str,
        consent_type: ConsentType,
        scope: dict | None = None,
        granted_by: str = "system",
        expires_at: datetime | None = None,
    ) -> ConsentRecord:
        """Record a new consent for a patient.

        If a consent of the same type already exists, it is superseded
        (the old record is kept in the audit trail but replaced in the
        active consent map).

        Args:
            patient_id: Patient identifier.
            consent_type: Type of consent being recorded.
            scope: Optional scope dict (purposes, data elements, etc.).
            granted_by: Who captured/recorded the consent.
            expires_at: Optional expiration timestamp.

        Returns:
            The created ConsentRecord.
        """
        now = datetime.now(timezone.utc)
        record = ConsentRecord(
            id=str(uuid.uuid4()),
            patient_id=patient_id,
            consent_type=consent_type,
            scope=scope,
            status=ConsentStatusValue.ACTIVE,
            granted_at=now,
            granted_by=granted_by,
            expires_at=expires_at,
        )

        with self._lock:
            if patient_id not in self._consents:
                self._consents[patient_id] = {}
            self._consents[patient_id][consent_type] = record

            self._add_audit_entry(
                patient_id=patient_id,
                consent_type=consent_type,
                action="GRANTED",
                actor=granted_by,
                details=f"Consent recorded. Scope: {scope}. Expires: {expires_at}",
                timestamp=now,
            )

        logger.info(
            "Consent recorded: patient=%s type=%s granted_by=%s",
            patient_id,
            consent_type.value,
            granted_by,
        )
        return record

    def check_consent(
        self,
        patient_id: str,
        consent_type: ConsentType,
    ) -> ConsentStatus:
        """Check the current consent status for a patient and consent type.

        Automatically detects expired consents and updates their status.

        Args:
            patient_id: Patient identifier.
            consent_type: Type of consent to check.

        Returns:
            ConsentStatus with the current status and record (if found).
        """
        now = datetime.now(timezone.utc)

        with self._lock:
            patient_consents = self._consents.get(patient_id, {})
            record = patient_consents.get(consent_type)

            if record is None:
                status = ConsentStatusValue.NOT_FOUND
                result_record = None
            elif record.status == ConsentStatusValue.REVOKED:
                status = ConsentStatusValue.REVOKED
                result_record = record
            elif record.expires_at is not None and record.expires_at <= now:
                # Mark as expired
                record = record.model_copy(
                    update={"status": ConsentStatusValue.EXPIRED}
                )
                self._consents[patient_id][consent_type] = record
                self._add_audit_entry(
                    patient_id=patient_id,
                    consent_type=consent_type,
                    action="EXPIRED",
                    actor="system",
                    details=f"Consent expired at {record.expires_at.isoformat()}",
                    timestamp=now,
                )
                status = ConsentStatusValue.EXPIRED
                result_record = record
            else:
                status = ConsentStatusValue.ACTIVE
                result_record = record

            # Log the check in audit trail
            self._add_audit_entry(
                patient_id=patient_id,
                consent_type=consent_type,
                action="CHECKED",
                actor="system",
                details=f"Consent check result: {status.value}",
                timestamp=now,
            )

        return ConsentStatus(
            patient_id=patient_id,
            consent_type=consent_type,
            status=status,
            consent_record=result_record,
        )

    def revoke_consent(
        self,
        patient_id: str,
        consent_type: ConsentType,
        revoked_by: str = "system",
        reason: str = "",
    ) -> ConsentRecord:
        """Revoke an existing consent.

        Revocation is effective immediately and prospective only.

        Args:
            patient_id: Patient identifier.
            consent_type: Type of consent to revoke.
            revoked_by: Who is revoking the consent.
            reason: Reason for revocation.

        Returns:
            The updated ConsentRecord with revoked status.

        Raises:
            ValueError: If no consent of this type exists for the patient.
        """
        now = datetime.now(timezone.utc)

        with self._lock:
            patient_consents = self._consents.get(patient_id, {})
            record = patient_consents.get(consent_type)

            if record is None:
                raise ValueError(
                    f"No {consent_type.value} consent found for patient {patient_id}"
                )

            if record.status == ConsentStatusValue.REVOKED:
                raise ValueError(
                    f"{consent_type.value} consent for patient {patient_id} "
                    f"is already revoked"
                )

            updated = record.model_copy(
                update={
                    "status": ConsentStatusValue.REVOKED,
                    "revoked_at": now,
                    "revoked_by": revoked_by,
                    "revocation_reason": reason,
                }
            )
            self._consents[patient_id][consent_type] = updated

            self._add_audit_entry(
                patient_id=patient_id,
                consent_type=consent_type,
                action="REVOKED",
                actor=revoked_by,
                details=f"Consent revoked. Reason: {reason}",
                timestamp=now,
            )

        logger.info(
            "Consent revoked: patient=%s type=%s revoked_by=%s reason=%s",
            patient_id,
            consent_type.value,
            revoked_by,
            reason,
        )
        return updated

    def get_patient_consents(self, patient_id: str) -> list[ConsentRecord]:
        """Get all consent records for a patient.

        Returns both active and inactive (revoked/expired) consents.

        Args:
            patient_id: Patient identifier.

        Returns:
            List of ConsentRecord objects.
        """
        with self._lock:
            patient_consents = self._consents.get(patient_id, {})
            return list(patient_consents.values())

    def check_data_use_authorization(
        self,
        patient_id: str,
        purpose: DataUsePurpose,
    ) -> bool:
        """Check whether a specific data use is authorized for a patient.

        Looks up which consent types can authorize the requested purpose,
        then checks if any of those consents are active.

        For MARKETING purpose, additionally checks that the consent scope
        includes marketing authorization.

        Args:
            patient_id: Patient identifier.
            purpose: The intended purpose of the data use.

        Returns:
            True if the use is authorized, False otherwise.
        """
        required_consent_types = PURPOSE_CONSENT_MAP.get(purpose, [])

        if not required_consent_types:
            logger.warning(
                "No consent types mapped for purpose=%s", purpose.value
            )
            return False

        for consent_type in required_consent_types:
            status = self.check_consent(patient_id, consent_type)
            if status.status == ConsentStatusValue.ACTIVE:
                # For marketing, check scope includes marketing
                if purpose == DataUsePurpose.MARKETING:
                    record = status.consent_record
                    if record and record.scope:
                        purposes = record.scope.get("purposes", [])
                        if "MARKETING" in purposes:
                            return True
                    # Marketing requires explicit scope
                    continue
                return True

        return False

    def get_consent_audit_trail(self, patient_id: str) -> ConsentAuditTrail:
        """Get the full consent audit trail for a patient.

        Args:
            patient_id: Patient identifier.

        Returns:
            ConsentAuditTrail with all logged events.
        """
        with self._lock:
            entries = self._audit_trail.get(patient_id, [])
            return ConsentAuditTrail(
                patient_id=patient_id,
                entries=list(entries),
                total_entries=len(entries),
            )

    def get_data_use_check(
        self,
        patient_id: str,
        purpose: DataUsePurpose,
    ) -> ConsentCheck:
        """Get a detailed data use authorization check result.

        Args:
            patient_id: Patient identifier.
            purpose: Intended purpose.

        Returns:
            ConsentCheck with authorization decision and reasoning.
        """
        required_consent_types = PURPOSE_CONSENT_MAP.get(purpose, [])
        is_authorized = self.check_data_use_authorization(patient_id, purpose)

        authorizing_type = None
        reason = ""

        if is_authorized:
            # Find which consent type authorized it
            for ct in required_consent_types:
                status = self.check_consent(patient_id, ct)
                if status.status == ConsentStatusValue.ACTIVE:
                    authorizing_type = ct
                    reason = (
                        f"Authorized by active {ct.value} consent"
                    )
                    break
        else:
            if not required_consent_types:
                reason = f"No consent types are mapped for purpose {purpose.value}"
            else:
                type_names = ", ".join(ct.value for ct in required_consent_types)
                reason = (
                    f"No active consent found. Required consent types: {type_names}"
                )

        return ConsentCheck(
            patient_id=patient_id,
            consent_type=authorizing_type,
            purpose=purpose,
            is_authorized=is_authorized,
            reason=reason,
        )

    def get_stats(self) -> dict:
        """Return service statistics for health checks."""
        with self._lock:
            total_patients = len(self._consents)
            total_records = sum(
                len(consents) for consents in self._consents.values()
            )
            total_audit_entries = sum(
                len(entries) for entries in self._audit_trail.values()
            )
            active_count = sum(
                1
                for consents in self._consents.values()
                for record in consents.values()
                if record.status == ConsentStatusValue.ACTIVE
            )
        return {
            "total_patients": total_patients,
            "total_consent_records": total_records,
            "active_consents": active_count,
            "total_audit_entries": total_audit_entries,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _add_audit_entry(
        self,
        patient_id: str,
        consent_type: ConsentType,
        action: str,
        actor: str,
        details: str = "",
        timestamp: datetime | None = None,
    ) -> None:
        """Add an entry to the consent audit trail.

        Must be called with self._lock held.
        """
        if patient_id not in self._audit_trail:
            self._audit_trail[patient_id] = []

        entry = ConsentAuditEntry(
            event_id=str(uuid.uuid4()),
            timestamp=timestamp or datetime.now(timezone.utc),
            patient_id=patient_id,
            consent_type=consent_type,
            action=action,
            actor=actor,
            details=details,
        )
        self._audit_trail[patient_id].append(entry)


# ---------------------------------------------------------------------------
# Singleton access
# ---------------------------------------------------------------------------

_consent_service: ConsentService | None = None


def get_consent_service() -> ConsentService:
    """Get or create the singleton ConsentService instance."""
    global _consent_service
    if _consent_service is None:
        _consent_service = ConsentService()
    return _consent_service


def reset_consent_service() -> None:
    """Reset the singleton for testing."""
    global _consent_service
    _consent_service = None
