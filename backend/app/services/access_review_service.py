"""Access Review & Certification Management service (CISO-11).

Manages periodic access review cycles, entitlement tracking, review decisions,
excessive-access detection, and compliance metrics for the clinical trial
patient recruitment platform.

Usage:
    from app.services.access_review_service import get_access_review_service

    service = get_access_review_service()
    cycles = service.list_cycles()
    metrics = service.get_metrics()
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from threading import Lock
from uuid import uuid4

from app.schemas.access_review import (
    AccessEntitlement,
    AccessLevel,
    AccessReviewMetrics,
    CycleStatus,
    CycleType,
    DecisionSubmitRequest,
    EntitlementCreateRequest,
    ExcessiveAccessEntry,
    ExcessiveAccessResponse,
    ReviewCycle,
    ReviewCycleCreateRequest,
    ReviewCycleUpdateRequest,
    ReviewDecision,
    ReviewDecisionType,
)

logger = logging.getLogger(__name__)

# Singleton instance and lock
_ar_instance: AccessReviewService | None = None
_ar_lock = Lock()

# Excessive-access thresholds
ADMIN_RESOURCE_THRESHOLD = 3  # ADMIN on N+ resources triggers flag
UNUSED_DAYS_THRESHOLD = 90  # days without use triggers flag


class AccessReviewService:
    """Manages access review cycles, entitlements, decisions, and metrics."""

    def __init__(self) -> None:
        self._cycles: dict[str, ReviewCycle] = {}
        self._entitlements: dict[str, AccessEntitlement] = {}
        self._decisions: dict[str, ReviewDecision] = {}
        self._populate_seed_data()

    # -----------------------------------------------------------------------
    # Seed data
    # -----------------------------------------------------------------------

    def _populate_seed_data(self) -> None:  # noqa: C901
        """Pre-populate entitlements, cycles, and decisions."""
        now = datetime.now(timezone.utc)

        # ------------------------------------------------------------------
        # 8 users, 20+ entitlements across varied roles
        # ------------------------------------------------------------------
        users = [
            ("USR-001", "Dr. Sarah Chen", "clinician"),
            ("USR-002", "James Rodriguez", "admin"),
            ("USR-003", "Emily Watson", "data_analyst"),
            ("USR-004", "Michael Park", "developer"),
            ("USR-005", "Lisa Thompson", "auditor"),
            ("USR-006", "David Kim", "operations"),
            ("USR-007", "Rachel Green", "clinician"),
            ("USR-008", "Alex Turner", "admin"),
        ]

        resources = [
            "patient_records",
            "trial_management",
            "screening_engine",
            "analytics_dashboard",
            "audit_logs",
            "system_config",
            "user_management",
            "fhir_api",
            "reporting_module",
            "data_exports",
        ]

        entitlement_specs: list[tuple[str, str, str, str, AccessLevel, str, int | None, str]] = [
            # user_id, user_name, user_role, resource, access_level, granted_by, days_since_use, justification
            ("USR-001", "Dr. Sarah Chen", "clinician", "patient_records", AccessLevel.WRITE, "James Rodriguez", 2, "Primary clinician role"),
            ("USR-001", "Dr. Sarah Chen", "clinician", "trial_management", AccessLevel.READ, "James Rodriguez", 5, "Trial participation"),
            ("USR-001", "Dr. Sarah Chen", "clinician", "screening_engine", AccessLevel.READ, "James Rodriguez", 1, "Patient screening"),
            ("USR-002", "James Rodriguez", "admin", "patient_records", AccessLevel.ADMIN, "Alex Turner", 1, "System administration"),
            ("USR-002", "James Rodriguez", "admin", "trial_management", AccessLevel.ADMIN, "Alex Turner", 0, "System administration"),
            ("USR-002", "James Rodriguez", "admin", "system_config", AccessLevel.ADMIN, "Alex Turner", 3, "System administration"),
            ("USR-002", "James Rodriguez", "admin", "user_management", AccessLevel.ADMIN, "Alex Turner", 0, "User provisioning"),
            ("USR-003", "Emily Watson", "data_analyst", "analytics_dashboard", AccessLevel.WRITE, "James Rodriguez", 1, "Reporting duties"),
            ("USR-003", "Emily Watson", "data_analyst", "reporting_module", AccessLevel.WRITE, "James Rodriguez", 4, "Reporting duties"),
            ("USR-003", "Emily Watson", "data_analyst", "data_exports", AccessLevel.WRITE, "James Rodriguez", 10, "Data export needs"),
            ("USR-004", "Michael Park", "developer", "screening_engine", AccessLevel.ADMIN, "James Rodriguez", 7, "Development access"),
            ("USR-004", "Michael Park", "developer", "fhir_api", AccessLevel.ADMIN, "James Rodriguez", 3, "API development"),
            ("USR-004", "Michael Park", "developer", "system_config", AccessLevel.READ, "James Rodriguez", 30, "Configuration review"),
            ("USR-005", "Lisa Thompson", "auditor", "audit_logs", AccessLevel.READ, "James Rodriguez", 2, "Compliance auditing"),
            ("USR-005", "Lisa Thompson", "auditor", "patient_records", AccessLevel.READ, "James Rodriguez", 14, "Audit review"),
            ("USR-005", "Lisa Thompson", "auditor", "data_exports", AccessLevel.READ, "James Rodriguez", 120, "Historical audit"),
            ("USR-006", "David Kim", "operations", "system_config", AccessLevel.WRITE, "James Rodriguez", 5, "Operations management"),
            ("USR-006", "David Kim", "operations", "analytics_dashboard", AccessLevel.READ, "James Rodriguez", 200, "Dashboard monitoring"),
            ("USR-006", "David Kim", "operations", "reporting_module", AccessLevel.READ, "James Rodriguez", 150, "Operational reports"),
            ("USR-007", "Rachel Green", "clinician", "patient_records", AccessLevel.WRITE, "James Rodriguez", 1, "Clinical duties"),
            ("USR-007", "Rachel Green", "clinician", "trial_management", AccessLevel.READ, "James Rodriguez", 3, "Trial enrollment"),
            ("USR-008", "Alex Turner", "admin", "patient_records", AccessLevel.ADMIN, "James Rodriguez", 0, "System administration"),
            ("USR-008", "Alex Turner", "admin", "user_management", AccessLevel.ADMIN, "James Rodriguez", 1, "User management"),
            ("USR-008", "Alex Turner", "admin", "system_config", AccessLevel.ADMIN, "James Rodriguez", 2, "Configuration management"),
            ("USR-008", "Alex Turner", "admin", "trial_management", AccessLevel.ADMIN, "James Rodriguez", 10, "Trial oversight"),
        ]

        for idx, (uid, uname, urole, res, level, gby, days_since, justification) in enumerate(entitlement_specs, start=1):
            eid = f"ENT-{idx:03d}"
            last_used = now - timedelta(days=days_since) if days_since is not None else None
            self._entitlements[eid] = AccessEntitlement(
                id=eid,
                user_id=uid,
                user_name=uname,
                user_role=urole,
                resource=res,
                access_level=level,
                granted_date=now - timedelta(days=180 + idx * 5),
                granted_by=gby,
                last_used=last_used,
                justification=justification,
            )

        # ------------------------------------------------------------------
        # 2 completed cycles + 1 in-progress
        # ------------------------------------------------------------------
        self._cycles["CYC-001"] = ReviewCycle(
            id="CYC-001",
            name="Q3 2025 Quarterly Access Review",
            cycle_type=CycleType.QUARTERLY,
            status=CycleStatus.COMPLETED,
            start_date=now - timedelta(days=180),
            end_date=now - timedelta(days=150),
            reviewer="Lisa Thompson",
            created_at=now - timedelta(days=185),
        )
        self._cycles["CYC-002"] = ReviewCycle(
            id="CYC-002",
            name="Q4 2025 Quarterly Access Review",
            cycle_type=CycleType.QUARTERLY,
            status=CycleStatus.COMPLETED,
            start_date=now - timedelta(days=90),
            end_date=now - timedelta(days=60),
            reviewer="Lisa Thompson",
            created_at=now - timedelta(days=95),
        )
        self._cycles["CYC-003"] = ReviewCycle(
            id="CYC-003",
            name="Q1 2026 Quarterly Access Review",
            cycle_type=CycleType.QUARTERLY,
            status=CycleStatus.IN_PROGRESS,
            start_date=now - timedelta(days=10),
            end_date=now + timedelta(days=20),
            reviewer="Lisa Thompson",
            created_at=now - timedelta(days=12),
        )

        # ------------------------------------------------------------------
        # Pre-populate decisions for the two completed cycles
        # ------------------------------------------------------------------
        completed_decisions: list[tuple[str, str, ReviewDecisionType, str, AccessLevel | None]] = [
            # cycle_id, entitlement_id, decision, comments, new_access_level
            ("CYC-001", "ENT-001", ReviewDecisionType.CERTIFY, "Clinician needs patient access", None),
            ("CYC-001", "ENT-004", ReviewDecisionType.CERTIFY, "Admin role requires full access", None),
            ("CYC-001", "ENT-008", ReviewDecisionType.CERTIFY, "Active analyst", None),
            ("CYC-001", "ENT-011", ReviewDecisionType.MODIFY, "Reduced from ADMIN to WRITE", AccessLevel.WRITE),
            ("CYC-001", "ENT-014", ReviewDecisionType.CERTIFY, "Audit function required", None),
            ("CYC-001", "ENT-016", ReviewDecisionType.REVOKE, "Access unused for 90+ days", None),
            ("CYC-001", "ENT-018", ReviewDecisionType.REVOKE, "Dashboard access not needed", None),
            ("CYC-002", "ENT-001", ReviewDecisionType.CERTIFY, "Continued clinical need", None),
            ("CYC-002", "ENT-002", ReviewDecisionType.CERTIFY, "Trial participation ongoing", None),
            ("CYC-002", "ENT-005", ReviewDecisionType.CERTIFY, "Admin duties confirmed", None),
            ("CYC-002", "ENT-009", ReviewDecisionType.CERTIFY, "Active reporting", None),
            ("CYC-002", "ENT-012", ReviewDecisionType.ESCALATE, "Needs manager review of API access scope", None),
            ("CYC-002", "ENT-015", ReviewDecisionType.REVOKE, "Audit period ended", None),
            ("CYC-002", "ENT-019", ReviewDecisionType.MODIFY, "Reduced scope for operations", AccessLevel.READ),
        ]

        for idx, (cyc_id, ent_id, decision, comments, new_level) in enumerate(completed_decisions, start=1):
            did = f"DEC-{idx:03d}"
            cycle = self._cycles[cyc_id]
            self._decisions[did] = ReviewDecision(
                id=did,
                cycle_id=cyc_id,
                entitlement_id=ent_id,
                decision=decision,
                reviewer=cycle.reviewer,
                decided_at=cycle.end_date - timedelta(days=idx % 5),
                comments=comments,
                new_access_level=new_level,
            )

    # -----------------------------------------------------------------------
    # Cycle CRUD
    # -----------------------------------------------------------------------

    def list_cycles(
        self,
        *,
        cycle_type: CycleType | None = None,
        status: CycleStatus | None = None,
    ) -> list[ReviewCycle]:
        """List review cycles with optional filters."""
        cycles = list(self._cycles.values())
        if cycle_type is not None:
            cycles = [c for c in cycles if c.cycle_type == cycle_type]
        if status is not None:
            cycles = [c for c in cycles if c.status == status]
        return sorted(cycles, key=lambda c: c.start_date, reverse=True)

    def get_cycle(self, cycle_id: str) -> ReviewCycle | None:
        """Get a single cycle by ID."""
        return self._cycles.get(cycle_id)

    def create_cycle(self, req: ReviewCycleCreateRequest) -> ReviewCycle:
        """Create a new review cycle."""
        cycle_id = f"CYC-{uuid4().hex[:8].upper()}"
        cycle = ReviewCycle(
            id=cycle_id,
            name=req.name,
            cycle_type=req.cycle_type,
            status=CycleStatus.PLANNED,
            start_date=req.start_date,
            end_date=req.end_date,
            reviewer=req.reviewer,
            created_at=datetime.now(timezone.utc),
        )
        self._cycles[cycle_id] = cycle
        logger.info("Created review cycle %s: %s", cycle_id, req.name)
        return cycle

    def update_cycle(self, cycle_id: str, req: ReviewCycleUpdateRequest) -> ReviewCycle | None:
        """Update an existing review cycle."""
        cycle = self._cycles.get(cycle_id)
        if cycle is None:
            return None
        data = cycle.model_dump()
        updates = req.model_dump(exclude_none=True)
        data.update(updates)
        updated = ReviewCycle(**data)
        self._cycles[cycle_id] = updated
        logger.info("Updated review cycle %s", cycle_id)
        return updated

    def delete_cycle(self, cycle_id: str) -> bool:
        """Delete a review cycle and its decisions."""
        if cycle_id not in self._cycles:
            return False
        del self._cycles[cycle_id]
        # Remove associated decisions
        to_remove = [d_id for d_id, d in self._decisions.items() if d.cycle_id == cycle_id]
        for d_id in to_remove:
            del self._decisions[d_id]
        logger.info("Deleted review cycle %s and %d decisions", cycle_id, len(to_remove))
        return True

    def start_cycle(self, cycle_id: str) -> ReviewCycle | None:
        """Transition a PLANNED cycle to IN_PROGRESS."""
        cycle = self._cycles.get(cycle_id)
        if cycle is None:
            return None
        if cycle.status != CycleStatus.PLANNED:
            return None
        data = cycle.model_dump()
        data["status"] = CycleStatus.IN_PROGRESS
        data["start_date"] = datetime.now(timezone.utc)
        updated = ReviewCycle(**data)
        self._cycles[cycle_id] = updated
        logger.info("Started review cycle %s", cycle_id)
        return updated

    def complete_cycle(self, cycle_id: str) -> ReviewCycle | None:
        """Transition an IN_PROGRESS cycle to COMPLETED."""
        cycle = self._cycles.get(cycle_id)
        if cycle is None:
            return None
        if cycle.status != CycleStatus.IN_PROGRESS:
            return None
        data = cycle.model_dump()
        data["status"] = CycleStatus.COMPLETED
        data["end_date"] = datetime.now(timezone.utc)
        updated = ReviewCycle(**data)
        self._cycles[cycle_id] = updated
        logger.info("Completed review cycle %s", cycle_id)
        return updated

    # -----------------------------------------------------------------------
    # Entitlement CRUD
    # -----------------------------------------------------------------------

    def list_entitlements(
        self,
        *,
        user_id: str | None = None,
        resource: str | None = None,
        access_level: AccessLevel | None = None,
    ) -> list[AccessEntitlement]:
        """List entitlements with optional filters."""
        ents = list(self._entitlements.values())
        if user_id is not None:
            ents = [e for e in ents if e.user_id == user_id]
        if resource is not None:
            ents = [e for e in ents if e.resource == resource]
        if access_level is not None:
            ents = [e for e in ents if e.access_level == access_level]
        return sorted(ents, key=lambda e: e.granted_date, reverse=True)

    def get_entitlement(self, entitlement_id: str) -> AccessEntitlement | None:
        """Get a single entitlement by ID."""
        return self._entitlements.get(entitlement_id)

    def create_entitlement(self, req: EntitlementCreateRequest) -> AccessEntitlement:
        """Create a new access entitlement."""
        ent_id = f"ENT-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        ent = AccessEntitlement(
            id=ent_id,
            user_id=req.user_id,
            user_name=req.user_name,
            user_role=req.user_role,
            resource=req.resource,
            access_level=req.access_level,
            granted_date=now,
            granted_by=req.granted_by,
            last_used=None,
            justification=req.justification,
        )
        self._entitlements[ent_id] = ent
        logger.info("Created entitlement %s for user %s on %s", ent_id, req.user_id, req.resource)
        return ent

    def delete_entitlement(self, entitlement_id: str) -> bool:
        """Delete an entitlement."""
        if entitlement_id not in self._entitlements:
            return False
        del self._entitlements[entitlement_id]
        logger.info("Deleted entitlement %s", entitlement_id)
        return True

    # -----------------------------------------------------------------------
    # Decision management
    # -----------------------------------------------------------------------

    def get_pending_reviews(self, cycle_id: str) -> list[AccessEntitlement] | None:
        """Get entitlements not yet reviewed in a given cycle.

        Returns None if the cycle does not exist.
        """
        if cycle_id not in self._cycles:
            return None
        reviewed_ent_ids = {
            d.entitlement_id
            for d in self._decisions.values()
            if d.cycle_id == cycle_id
        }
        pending = [
            e for e in self._entitlements.values()
            if e.id not in reviewed_ent_ids
        ]
        return sorted(pending, key=lambda e: e.user_name)

    def submit_decision(self, cycle_id: str, req: DecisionSubmitRequest) -> ReviewDecision | None:
        """Submit a review decision for an entitlement within a cycle.

        Returns None if cycle or entitlement does not exist.
        """
        if cycle_id not in self._cycles:
            return None
        if req.entitlement_id not in self._entitlements:
            return None
        dec_id = f"DEC-{uuid4().hex[:8].upper()}"
        decision = ReviewDecision(
            id=dec_id,
            cycle_id=cycle_id,
            entitlement_id=req.entitlement_id,
            decision=req.decision,
            reviewer=req.reviewer,
            decided_at=datetime.now(timezone.utc),
            comments=req.comments,
            new_access_level=req.new_access_level,
        )
        self._decisions[dec_id] = decision

        # Apply side-effects
        if req.decision == ReviewDecisionType.REVOKE:
            self.delete_entitlement(req.entitlement_id)
        elif req.decision == ReviewDecisionType.MODIFY and req.new_access_level is not None:
            ent = self._entitlements.get(req.entitlement_id)
            if ent:
                data = ent.model_dump()
                data["access_level"] = req.new_access_level
                self._entitlements[req.entitlement_id] = AccessEntitlement(**data)

        logger.info(
            "Decision %s submitted for entitlement %s in cycle %s: %s",
            dec_id, req.entitlement_id, cycle_id, req.decision.value,
        )
        return decision

    def list_decisions(
        self,
        *,
        cycle_id: str | None = None,
        decision_type: ReviewDecisionType | None = None,
    ) -> list[ReviewDecision]:
        """List decisions with optional filters."""
        decs = list(self._decisions.values())
        if cycle_id is not None:
            decs = [d for d in decs if d.cycle_id == cycle_id]
        if decision_type is not None:
            decs = [d for d in decs if d.decision == decision_type]
        return sorted(decs, key=lambda d: d.decided_at, reverse=True)

    # -----------------------------------------------------------------------
    # Excessive access detection
    # -----------------------------------------------------------------------

    def detect_excessive_access(self) -> ExcessiveAccessResponse:
        """Flag users with ADMIN on 3+ resources or unused access > 90 days."""
        now = datetime.now(timezone.utc)
        flagged: dict[str, ExcessiveAccessEntry] = {}

        # Group entitlements by user
        by_user: dict[str, list[AccessEntitlement]] = {}
        for ent in self._entitlements.values():
            by_user.setdefault(ent.user_id, []).append(ent)

        for uid, ents in by_user.items():
            reasons: list[str] = []
            flagged_ents: list[AccessEntitlement] = []

            # Check ADMIN on 3+ resources
            admin_ents = [e for e in ents if e.access_level in (AccessLevel.ADMIN, AccessLevel.OWNER)]
            if len(admin_ents) >= ADMIN_RESOURCE_THRESHOLD:
                reasons.append(
                    f"ADMIN/OWNER access on {len(admin_ents)} resources "
                    f"(threshold: {ADMIN_RESOURCE_THRESHOLD})"
                )
                flagged_ents.extend(admin_ents)

            # Check unused access > 90 days
            for ent in ents:
                if ent.last_used is not None:
                    days_unused = (now - ent.last_used).days
                    if days_unused > UNUSED_DAYS_THRESHOLD:
                        reasons.append(
                            f"Access to '{ent.resource}' unused for {days_unused} days "
                            f"(threshold: {UNUSED_DAYS_THRESHOLD})"
                        )
                        if ent not in flagged_ents:
                            flagged_ents.append(ent)

            if reasons:
                first_ent = ents[0]
                flagged[uid] = ExcessiveAccessEntry(
                    user_id=uid,
                    user_name=first_ent.user_name,
                    user_role=first_ent.user_role,
                    reasons=reasons,
                    entitlements=flagged_ents,
                )

        items = sorted(flagged.values(), key=lambda e: len(e.reasons), reverse=True)
        return ExcessiveAccessResponse(items=items, total=len(items))

    # -----------------------------------------------------------------------
    # Metrics
    # -----------------------------------------------------------------------

    def get_metrics(self) -> AccessReviewMetrics:
        """Compute aggregate access review metrics."""
        total_cycles = len(self._cycles)
        total_entitlements = len(self._entitlements)
        decisions = list(self._decisions.values())
        total_decisions = len(decisions)

        by_decision: dict[str, int] = {}
        for d in decisions:
            by_decision[d.decision.value] = by_decision.get(d.decision.value, 0) + 1

        certification_rate = 0.0
        revocation_rate = 0.0
        if total_decisions > 0:
            certification_rate = round(
                by_decision.get(ReviewDecisionType.CERTIFY.value, 0) / total_decisions * 100, 1
            )
            revocation_rate = round(
                by_decision.get(ReviewDecisionType.REVOKE.value, 0) / total_decisions * 100, 1
            )

        # Average review time for completed cycles
        completed = [c for c in self._cycles.values() if c.status == CycleStatus.COMPLETED]
        avg_review_time_days = 0.0
        if completed:
            total_days = sum((c.end_date - c.start_date).days for c in completed)
            avg_review_time_days = round(total_days / len(completed), 1)

        # Overdue cycles
        now = datetime.now(timezone.utc)
        overdue = sum(
            1 for c in self._cycles.values()
            if c.status == CycleStatus.IN_PROGRESS and c.end_date < now
        )
        overdue += sum(
            1 for c in self._cycles.values()
            if c.status == CycleStatus.OVERDUE
        )

        # Excessive access count
        excessive = self.detect_excessive_access()
        excessive_access_count = excessive.total

        return AccessReviewMetrics(
            total_cycles=total_cycles,
            total_entitlements=total_entitlements,
            certification_rate=certification_rate,
            revocation_rate=revocation_rate,
            avg_review_time_days=avg_review_time_days,
            overdue_reviews=overdue,
            by_decision=by_decision,
            excessive_access_count=excessive_access_count,
        )

    # -----------------------------------------------------------------------
    # Overdue cycles
    # -----------------------------------------------------------------------

    def get_overdue_cycles(self) -> list[ReviewCycle]:
        """Get cycles that are IN_PROGRESS past their end date or marked OVERDUE."""
        now = datetime.now(timezone.utc)
        overdue = []
        for c in self._cycles.values():
            if c.status == CycleStatus.OVERDUE:
                overdue.append(c)
            elif c.status == CycleStatus.IN_PROGRESS and c.end_date < now:
                overdue.append(c)
        return sorted(overdue, key=lambda c: c.end_date)

    # -----------------------------------------------------------------------
    # Stats (for prewarm reporting)
    # -----------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return summary stats for service health reporting."""
        return {
            "cycles": len(self._cycles),
            "entitlements": len(self._entitlements),
            "decisions": len(self._decisions),
        }


# ---------------------------------------------------------------------------
# Singleton access
# ---------------------------------------------------------------------------


def get_access_review_service() -> AccessReviewService:
    """Get or create the singleton AccessReviewService instance."""
    global _ar_instance
    if _ar_instance is None:
        with _ar_lock:
            if _ar_instance is None:
                _ar_instance = AccessReviewService()
                logger.info(
                    "AccessReviewService initialized: %d cycles, %d entitlements, %d decisions",
                    len(_ar_instance._cycles),
                    len(_ar_instance._entitlements),
                    len(_ar_instance._decisions),
                )
    return _ar_instance


def reset_access_review_service() -> None:
    """Reset the singleton (for testing)."""
    global _ar_instance
    with _ar_lock:
        _ar_instance = None
