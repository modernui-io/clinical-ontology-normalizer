"""Data Use Agreement (DUA) Service.

Manages the lifecycle of Data Use Agreements, compliance checking,
access logging, and expiration monitoring for the clinical trial
patient recruitment platform.

CLO-2: Data Use Agreements and Right-to-Deletion

Usage:
    from app.services.data_use_agreement_service import get_dua_service

    svc = get_dua_service()
    dua = svc.create_dua(DUACreate(...))
    result = svc.check_compliance(DUAComplianceCheck(...))
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from threading import Lock

from app.schemas.data_governance import (
    AccessLogCreate,
    AccessLogEntry,
    AccessLogQuery,
    ComplianceDecision,
    DataCategory,
    DUAAmendment,
    DUAComplianceCheck,
    DUAComplianceResult,
    DUACreate,
    DUAResponse,
    DUAStatus,
    DUATemplate,
    DUAType,
    DUAUpdate,
    SuspiciousAccessReport,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Valid state transitions
# ---------------------------------------------------------------------------

VALID_TRANSITIONS: dict[DUAStatus, list[DUAStatus]] = {
    DUAStatus.DRAFT: [DUAStatus.PENDING_REVIEW, DUAStatus.TERMINATED],
    DUAStatus.PENDING_REVIEW: [DUAStatus.ACTIVE, DUAStatus.DRAFT, DUAStatus.TERMINATED],
    DUAStatus.ACTIVE: [DUAStatus.EXPIRED, DUAStatus.TERMINATED],
    DUAStatus.EXPIRED: [],
    DUAStatus.TERMINATED: [],
}


# ---------------------------------------------------------------------------
# Pre-populated DUA templates
# ---------------------------------------------------------------------------

DUA_TEMPLATES: dict[DUAType, DUATemplate] = {
    DUAType.SITE_DUA: DUATemplate(
        dua_type=DUAType.SITE_DUA,
        title="Clinical Trial Site Data Use Agreement",
        parties=["[Platform Name]", "[Site Name]"],
        data_categories=[DataCategory.PHI, DataCategory.LIMITED_DATASET],
        permitted_uses=[
            "Patient screening for clinical trial eligibility",
            "De-identified data analysis for recruitment optimization",
            "Clinical trial enrollment workflows",
        ],
        prohibited_uses=[
            "Direct marketing to patients",
            "Sale of patient data to third parties",
            "Use of data for purposes unrelated to clinical trials",
        ],
        retention_period_days=2190,  # ~6 years per 21 CFR Part 11
    ),
    DUAType.SPONSOR_DUA: DUATemplate(
        dua_type=DUAType.SPONSOR_DUA,
        title="Trial Sponsor Data Use Agreement",
        parties=["[Platform Name]", "[Sponsor Name]"],
        data_categories=[DataCategory.DE_IDENTIFIED, DataCategory.AGGREGATE],
        permitted_uses=[
            "Aggregate screening metrics reporting",
            "De-identified patient cohort analysis",
            "Trial feasibility assessments",
        ],
        prohibited_uses=[
            "Re-identification of patients",
            "Sharing data with non-authorized third parties",
            "Use of data beyond agreed trial scope",
        ],
        retention_period_days=2190,
    ),
    DUAType.RESEARCH_DUA: DUATemplate(
        dua_type=DUAType.RESEARCH_DUA,
        title="Secondary Research Data Use Agreement",
        parties=["[Platform Name]", "[Research Institution]"],
        data_categories=[DataCategory.DE_IDENTIFIED, DataCategory.LIMITED_DATASET],
        permitted_uses=[
            "Secondary analysis of de-identified clinical data",
            "Publication of aggregate research findings",
            "Development of clinical prediction models",
        ],
        prohibited_uses=[
            "Re-identification attempts",
            "Commercial use without separate agreement",
            "Sharing raw data outside research team",
        ],
        retention_period_days=3650,  # ~10 years for research
    ),
    DUAType.VENDOR_DUA: DUATemplate(
        dua_type=DUAType.VENDOR_DUA,
        title="Third-Party Vendor Data Use Agreement",
        parties=["[Platform Name]", "[Vendor Name]"],
        data_categories=[DataCategory.PHI, DataCategory.DE_IDENTIFIED],
        permitted_uses=[
            "Data processing as specified in service agreement",
            "Technical support requiring data access",
            "System integration and interoperability",
        ],
        prohibited_uses=[
            "Independent use of data for vendor's own purposes",
            "Subcontracting data processing without authorization",
            "Retaining data beyond contract termination",
        ],
        retention_period_days=1095,  # ~3 years
    ),
}


class DataUseAgreementService:
    """In-memory DUA management with compliance checking and access logging.

    Thread-safe via a reentrant lock. Provides DUA lifecycle management,
    compliance checking against active DUAs, data access logging, and
    expiration monitoring.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        # dua_id -> DUAResponse
        self._duas: dict[str, DUAResponse] = {}
        # Access log entries
        self._access_log: list[AccessLogEntry] = []

    # ------------------------------------------------------------------
    # DUA CRUD
    # ------------------------------------------------------------------

    def create_dua(self, request: DUACreate) -> DUAResponse:
        """Create a new Data Use Agreement.

        Args:
            request: DUA creation request with agreement details.

        Returns:
            The created DUAResponse in DRAFT status.
        """
        now = datetime.now(timezone.utc)
        dua_id = str(uuid.uuid4())

        dua = DUAResponse(
            id=dua_id,
            title=request.title,
            dua_type=request.dua_type,
            parties=request.parties,
            data_categories=request.data_categories,
            permitted_uses=request.permitted_uses,
            prohibited_uses=request.prohibited_uses,
            retention_period_days=request.retention_period_days,
            start_date=request.start_date,
            end_date=request.end_date,
            status=DUAStatus.DRAFT,
            amendment_history=[],
            created_at=now,
            updated_at=now,
        )

        with self._lock:
            self._duas[dua_id] = dua

        logger.info(
            "DUA created: id=%s title=%s type=%s",
            dua_id,
            request.title,
            request.dua_type.value,
        )
        return dua

    def get_dua(self, dua_id: str) -> DUAResponse | None:
        """Get a DUA by ID.

        Args:
            dua_id: Unique DUA identifier.

        Returns:
            DUAResponse if found, None otherwise.
        """
        with self._lock:
            return self._duas.get(dua_id)

    def list_duas(self, status_filter: DUAStatus | None = None) -> list[DUAResponse]:
        """List all DUAs, optionally filtered by status.

        Args:
            status_filter: Optional status to filter by.

        Returns:
            List of DUAResponse objects.
        """
        with self._lock:
            duas = list(self._duas.values())

        if status_filter is not None:
            duas = [d for d in duas if d.status == status_filter]

        return duas

    def update_dua(self, dua_id: str, update: DUAUpdate) -> DUAResponse:
        """Update a DUA with state transitions and amendment tracking.

        For active DUAs, changes to substantive fields are tracked
        as amendments.

        Args:
            dua_id: DUA to update.
            update: Fields to update.

        Returns:
            Updated DUAResponse.

        Raises:
            ValueError: If the DUA is not found or the state transition is invalid.
        """
        now = datetime.now(timezone.utc)

        with self._lock:
            dua = self._duas.get(dua_id)
            if dua is None:
                raise ValueError(f"DUA {dua_id} not found")

            # Build update dict
            changes: dict = {"updated_at": now}
            amendments = list(dua.amendment_history)

            # Handle status transition
            if update.status is not None and update.status != dua.status:
                valid_next = VALID_TRANSITIONS.get(dua.status, [])
                if update.status not in valid_next:
                    raise ValueError(
                        f"Invalid state transition: {dua.status.value} -> {update.status.value}. "
                        f"Valid transitions: {[s.value for s in valid_next]}"
                    )
                changes["status"] = update.status

                # If activating, require signed_by
                if update.status == DUAStatus.ACTIVE:
                    if update.signed_by:
                        changes["signed_by"] = update.signed_by
                        changes["signed_date"] = update.signed_date or now
                    elif dua.signed_by is None:
                        raise ValueError("DUA must be signed before activation (provide signed_by)")

            # Track amendments for active DUAs
            is_active = dua.status == DUAStatus.ACTIVE
            amendment_fields = {
                "title": update.title,
                "parties": update.parties,
                "data_categories": update.data_categories,
                "permitted_uses": update.permitted_uses,
                "prohibited_uses": update.prohibited_uses,
                "retention_period_days": update.retention_period_days,
            }

            for field_name, new_value in amendment_fields.items():
                if new_value is not None:
                    old_value = getattr(dua, field_name)
                    if new_value != old_value:
                        changes[field_name] = new_value
                        if is_active:
                            if not update.amendment_reason:
                                raise ValueError(
                                    f"Amendment reason required when modifying active DUA field '{field_name}'"
                                )
                            amendments.append(
                                DUAAmendment(
                                    amendment_id=str(uuid.uuid4()),
                                    timestamp=now,
                                    field_changed=field_name,
                                    old_value=str(old_value),
                                    new_value=str(new_value),
                                    reason=update.amendment_reason or "",
                                    approved_by=update.amendment_approved_by or "system",
                                )
                            )

            # Handle non-amendment fields
            if update.start_date is not None:
                changes["start_date"] = update.start_date
            if update.end_date is not None:
                changes["end_date"] = update.end_date
            if update.signed_by is not None and "signed_by" not in changes:
                changes["signed_by"] = update.signed_by
            if update.signed_date is not None and "signed_date" not in changes:
                changes["signed_date"] = update.signed_date

            changes["amendment_history"] = amendments

            updated_dua = dua.model_copy(update=changes)
            self._duas[dua_id] = updated_dua

        logger.info("DUA updated: id=%s changes=%s", dua_id, list(changes.keys()))
        return updated_dua

    # ------------------------------------------------------------------
    # Compliance Checking
    # ------------------------------------------------------------------

    def check_compliance(self, check: DUAComplianceCheck) -> DUAComplianceResult:
        """Check if a data access is covered by an active DUA.

        Searches for active DUAs that:
        1. Cover the requested data category
        2. Include the stated purpose in permitted uses
        3. Do not list the purpose in prohibited uses

        Args:
            check: The compliance check request.

        Returns:
            DUAComplianceResult with ALLOWED or DENIED decision.
        """
        with self._lock:
            active_duas = [
                d for d in self._duas.values()
                if d.status == DUAStatus.ACTIVE
            ]

        for dua in active_duas:
            # Check data category is covered
            if check.data_category not in dua.data_categories:
                continue

            # Check purpose is not prohibited
            purpose_lower = check.purpose.lower()
            is_prohibited = any(
                purpose_lower in prohibited.lower()
                for prohibited in dua.prohibited_uses
            )
            if is_prohibited:
                continue

            # Check purpose is permitted (if permitted_uses is specified)
            if dua.permitted_uses:
                is_permitted = any(
                    purpose_lower in permitted.lower()
                    for permitted in dua.permitted_uses
                )
                if not is_permitted:
                    continue

            # Check DUA is not expired by end_date
            now = datetime.now(timezone.utc)
            if dua.end_date is not None and dua.end_date <= now:
                continue

            return DUAComplianceResult(
                decision=ComplianceDecision.ALLOWED,
                dua_id=dua.id,
                dua_title=dua.title,
                reason=f"Access authorized under DUA '{dua.title}'",
            )

        return DUAComplianceResult(
            decision=ComplianceDecision.DENIED,
            reason=(
                f"No active DUA covers {check.data_category.value} data "
                f"for purpose: {check.purpose}"
            ),
        )

    # ------------------------------------------------------------------
    # Expiration Monitoring
    # ------------------------------------------------------------------

    def get_expiring_duas(self, within_days: int = 30) -> list[DUAResponse]:
        """List DUAs expiring within the specified number of days.

        Args:
            within_days: Number of days to look ahead (default 30).

        Returns:
            List of DUAs expiring within the window.
        """
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=within_days)

        with self._lock:
            expiring = []
            for dua in self._duas.values():
                if dua.status == DUAStatus.ACTIVE and dua.end_date is not None:
                    if dua.end_date <= cutoff:
                        expiring.append(dua)
            return expiring

    # ------------------------------------------------------------------
    # DUA Templates
    # ------------------------------------------------------------------

    def get_template(self, dua_type: DUAType) -> DUATemplate:
        """Get the pre-populated DUA template for a given type.

        Args:
            dua_type: The type of DUA template to retrieve.

        Returns:
            DUATemplate with default values.

        Raises:
            ValueError: If no template exists for the given type.
        """
        template = DUA_TEMPLATES.get(dua_type)
        if template is None:
            raise ValueError(f"No template available for DUA type: {dua_type.value}")
        return template

    # ------------------------------------------------------------------
    # Data Access Logging
    # ------------------------------------------------------------------

    def record_access(self, request: AccessLogCreate) -> AccessLogEntry:
        """Record a data access event.

        Args:
            request: Access log creation request.

        Returns:
            The created AccessLogEntry.
        """
        now = datetime.now(timezone.utc)
        entry = AccessLogEntry(
            id=str(uuid.uuid4()),
            user_id=request.user_id,
            patient_id=request.patient_id,
            data_category=request.data_category,
            purpose=request.purpose,
            timestamp=now,
            dua_id=request.dua_id,
        )

        with self._lock:
            self._access_log.append(entry)

        logger.info(
            "Data access logged: user=%s category=%s purpose=%s dua=%s",
            request.user_id,
            request.data_category.value,
            request.purpose,
            request.dua_id,
        )
        return entry

    def query_access_log(self, query: AccessLogQuery) -> list[AccessLogEntry]:
        """Query access logs with filters.

        Args:
            query: Filter criteria.

        Returns:
            Filtered list of AccessLogEntry objects.
        """
        with self._lock:
            entries = list(self._access_log)

        if query.user_id is not None:
            entries = [e for e in entries if e.user_id == query.user_id]
        if query.patient_id is not None:
            entries = [e for e in entries if e.patient_id == query.patient_id]
        if query.data_category is not None:
            entries = [e for e in entries if e.data_category == query.data_category]
        if query.dua_id is not None:
            entries = [e for e in entries if e.dua_id == query.dua_id]
        if query.start_date is not None:
            entries = [e for e in entries if e.timestamp >= query.start_date]
        if query.end_date is not None:
            entries = [e for e in entries if e.timestamp <= query.end_date]

        return entries

    def get_suspicious_accesses(self) -> SuspiciousAccessReport:
        """Find data accesses not covered by any active DUA.

        Returns:
            SuspiciousAccessReport with uncovered access entries.
        """
        now = datetime.now(timezone.utc)

        with self._lock:
            active_dua_ids = {
                d.id for d in self._duas.values()
                if d.status == DUAStatus.ACTIVE
            }
            uncovered = [
                entry for entry in self._access_log
                if entry.dua_id is None or entry.dua_id not in active_dua_ids
            ]

        return SuspiciousAccessReport(
            total_uncovered=len(uncovered),
            entries=uncovered,
            generated_at=now,
        )

    def get_dua_accesses(self, dua_id: str) -> list[AccessLogEntry]:
        """List all data accesses made under a specific DUA.

        Args:
            dua_id: The DUA to query.

        Returns:
            List of AccessLogEntry objects linked to this DUA.
        """
        with self._lock:
            return [e for e in self._access_log if e.dua_id == dua_id]

    # ------------------------------------------------------------------
    # Service Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return service statistics for health checks."""
        with self._lock:
            total_duas = len(self._duas)
            active_duas = sum(
                1 for d in self._duas.values()
                if d.status == DUAStatus.ACTIVE
            )
            total_access_log = len(self._access_log)
        return {
            "total_duas": total_duas,
            "active_duas": active_duas,
            "total_access_log_entries": total_access_log,
        }


# ---------------------------------------------------------------------------
# Singleton access
# ---------------------------------------------------------------------------

_dua_service: DataUseAgreementService | None = None


def get_dua_service() -> DataUseAgreementService:
    """Get or create the singleton DataUseAgreementService instance."""
    global _dua_service
    if _dua_service is None:
        _dua_service = DataUseAgreementService()
    return _dua_service


def reset_dua_service() -> None:
    """Reset the singleton for testing."""
    global _dua_service
    _dua_service = None
