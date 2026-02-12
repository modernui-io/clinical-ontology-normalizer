"""Unblinding Management Service (CLINICAL-UBM).

Manages unblinding operations for clinical trials including request lifecycle
(request -> approve -> execute, or deny/cancel), policy management per trial,
emergency unblinding procedures, and operational metrics.

Usage:
    from app.services.unblinding_management_service import (
        get_unblinding_management_service,
    )

    svc = get_unblinding_management_service()
    requests = svc.list_requests()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.unblinding_management import (
    ApprovalAuthority,
    BlindingLevel,
    UnblindingMetrics,
    UnblindingPolicy,
    UnblindingPolicyCreate,
    UnblindingPolicyUpdate,
    UnblindingRequest,
    UnblindingRequestCreate,
    UnblindingRequestUpdate,
    UnblindingStatus,
    UnblindingType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class UnblindingManagementService:
    """In-memory Unblinding Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._requests: dict[str, UnblindingRequest] = {}
        self._policies: dict[str, UnblindingPolicy] = {}
        self._request_counter: int = 0
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic unblinding data across clinical trials."""
        now = datetime.now(timezone.utc)

        # --- Unblinding Requests ---
        requests_data = [
            {
                "id": "UBR-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-105",
                "patient_id": "PAT-10532",
                "request_number": "UBR-001",
                "unblinding_type": UnblindingType.EMERGENCY,
                "status": UnblindingStatus.EXECUTED,
                "blinding_level": BlindingLevel.DOUBLE_BLIND,
                "reason": "Patient experienced life-threatening anaphylactic reaction requiring immediate treatment decision",
                "clinical_justification": "Grade 4 anaphylaxis per CTCAE v5.0. Patient in ICU requiring vasopressor support. Treatment assignment needed to guide emergency medical management and determine if reaction is drug-related.",
                "requested_by": "Dr. Sarah Chen",
                "requested_date": now - timedelta(days=45),
                "approved_by": "Dr. Michael Torres",
                "approval_authority": ApprovalAuthority.SPONSOR_MEDICAL_OFFICER,
                "approved_date": now - timedelta(days=45, hours=-1),
                "executed_by": "Dr. Jennifer Walsh",
                "executed_date": now - timedelta(days=45, hours=-2),
                "treatment_assignment": "Active Drug (Aflibercept 8mg)",
                "was_emergency": True,
                "notification_list": [
                    "Sponsor Medical Monitor",
                    "DSMB Chair",
                    "Site Principal Investigator",
                    "IRB",
                    "Regulatory Affairs",
                ],
                "impact_on_study": "Single patient unblinded. Patient withdrawn from study per protocol. No impact on overall study integrity. DSMB notified and confirmed continuation.",
            },
            {
                "id": "UBR-002",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "patient_id": None,
                "request_number": "UBR-002",
                "unblinding_type": UnblindingType.DSMB_REQUEST,
                "status": UnblindingStatus.EXECUTED,
                "blinding_level": BlindingLevel.DOUBLE_BLIND,
                "reason": "DSMB interim efficacy analysis at 50% enrollment milestone",
                "clinical_justification": "Pre-planned interim analysis per statistical analysis plan. DSMB charter mandates unblinded review of primary endpoint data at 50% information fraction.",
                "requested_by": "Prof. James Richardson (DSMB Chair)",
                "requested_date": now - timedelta(days=30),
                "approved_by": "Prof. James Richardson",
                "approval_authority": ApprovalAuthority.DSMB,
                "approved_date": now - timedelta(days=28),
                "executed_by": "Independent Statistical Center",
                "executed_date": now - timedelta(days=25),
                "treatment_assignment": None,
                "was_emergency": False,
                "notification_list": [
                    "DSMB Members",
                    "Independent Statistician",
                    "Sponsor (notification only, no data access)",
                ],
                "impact_on_study": "DSMB-only unblinding for interim analysis. Firewalled from sponsor and sites. DSMB recommended study continuation without modification.",
            },
            {
                "id": "UBR-003",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-107",
                "patient_id": None,
                "request_number": "UBR-003",
                "unblinding_type": UnblindingType.FINAL,
                "status": UnblindingStatus.APPROVED,
                "blinding_level": BlindingLevel.DOUBLE_BLIND,
                "reason": "Final database lock and study unblinding for primary analysis",
                "clinical_justification": "Study has reached completion. All patients have completed the treatment period. Database has been locked and validated. Final unblinding required for primary efficacy analysis per protocol.",
                "requested_by": "Dr. Lisa Park (Clinical Program Lead)",
                "requested_date": now - timedelta(days=10),
                "approved_by": "Dr. Robert Kraft (VP Clinical Development)",
                "approval_authority": ApprovalAuthority.SPONSOR_MEDICAL_OFFICER,
                "approved_date": now - timedelta(days=7),
                "executed_by": None,
                "executed_date": None,
                "treatment_assignment": None,
                "was_emergency": False,
                "notification_list": [
                    "All investigators",
                    "DSMB",
                    "Regulatory Affairs",
                    "Biostatistics Team",
                    "Medical Writing Team",
                ],
                "impact_on_study": "Full study unblinding. Marks transition from blinded to open-label phase for analysis and reporting.",
            },
            {
                "id": "UBR-004",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "patient_id": "PAT-10148",
                "request_number": "UBR-004",
                "unblinding_type": UnblindingType.INDIVIDUAL_PATIENT,
                "status": UnblindingStatus.DENIED,
                "blinding_level": BlindingLevel.DOUBLE_BLIND,
                "reason": "Treating physician requests unblinding to guide concomitant medication selection",
                "clinical_justification": "Patient requires new concomitant medication. Treating physician believes knowledge of treatment assignment would help selection. No safety concern identified.",
                "requested_by": "Dr. William Hayes",
                "requested_date": now - timedelta(days=20),
                "approved_by": None,
                "approval_authority": None,
                "approved_date": None,
                "executed_by": None,
                "executed_date": None,
                "treatment_assignment": None,
                "was_emergency": False,
                "notification_list": [
                    "Site Principal Investigator",
                    "Medical Monitor",
                ],
                "impact_on_study": None,
            },
            {
                "id": "UBR-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "patient_id": "PAT-10401",
                "request_number": "UBR-005",
                "unblinding_type": UnblindingType.REGULATORY_REQUEST,
                "status": UnblindingStatus.REQUESTED,
                "blinding_level": BlindingLevel.DOUBLE_BLIND,
                "reason": "FDA request for individual patient treatment assignment in response to IND safety report",
                "clinical_justification": "FDA has requested treatment assignment for a specific SUSAR (Suspected Unexpected Serious Adverse Reaction) as part of IND safety evaluation.",
                "requested_by": "Dr. Amanda Foster (Regulatory Affairs Director)",
                "requested_date": now - timedelta(days=3),
                "approved_by": None,
                "approval_authority": None,
                "approved_date": None,
                "executed_by": None,
                "executed_date": None,
                "treatment_assignment": None,
                "was_emergency": False,
                "notification_list": [],
                "impact_on_study": None,
            },
            {
                "id": "UBR-006",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "patient_id": "PAT-10215",
                "request_number": "UBR-006",
                "unblinding_type": UnblindingType.EMERGENCY,
                "status": UnblindingStatus.CANCELLED,
                "blinding_level": BlindingLevel.DOUBLE_BLIND,
                "reason": "Initial report of severe adverse event, pending clinical assessment",
                "clinical_justification": "Patient presented with acute symptoms initially suspected to be drug-related.",
                "requested_by": "Dr. Karen Mitchell",
                "requested_date": now - timedelta(days=15),
                "approved_by": None,
                "approval_authority": None,
                "approved_date": None,
                "executed_by": None,
                "executed_date": None,
                "treatment_assignment": None,
                "was_emergency": True,
                "notification_list": [
                    "Site Principal Investigator",
                    "Medical Monitor",
                ],
                "impact_on_study": "Request cancelled after clinical assessment determined symptoms were unrelated to study treatment. Blinding maintained.",
            },
        ]

        self._request_counter = len(requests_data)
        for r in requests_data:
            self._requests[r["id"]] = UnblindingRequest(**r)

        # --- Unblinding Policies ---
        policies_data = [
            {
                "id": "UBP-001",
                "trial_id": EYLEA_TRIAL,
                "blinding_level": BlindingLevel.DOUBLE_BLIND,
                "emergency_procedure": "Emergency unblinding may be performed 24/7 by contacting the Interactive Response Technology (IRT) system. The site investigator must document the clinical rationale in the patient's source documents and notify the sponsor medical monitor within 4 hours. Emergency unblinding should only occur when knowledge of treatment assignment is essential for patient safety management.",
                "interim_unblinding_plan": "One planned interim analysis at 60% information fraction by DSMB. Unblinding conducted by independent statistical center with firewall from sponsor and sites.",
                "final_unblinding_plan": "Final unblinding after database lock, data validation, and statistical analysis plan finalization. Requires written approval from VP Clinical Development.",
                "authorized_unblinders": [
                    "IRT System (emergency)",
                    "Independent Statistical Center (interim)",
                    "Sponsor Biostatistics Lead (final)",
                ],
                "code_break_instructions": "Randomization codes are maintained in the IRT system (Medidata RTSM). Emergency code break: call IRT hotline at +1-800-555-0199. Non-emergency code break: submit formal request through the Clinical Trial Management System with appropriate approvals.",
                "notification_requirements": [
                    "Sponsor Medical Monitor (within 4 hours for emergency)",
                    "DSMB Chair (within 24 hours for any unblinding)",
                    "IRB/EC (within 72 hours if individual patient unblinded)",
                    "Regulatory Affairs (if regulatory submission impacted)",
                ],
            },
            {
                "id": "UBP-002",
                "trial_id": DUPIXENT_TRIAL,
                "blinding_level": BlindingLevel.DOUBLE_BLIND,
                "emergency_procedure": "Emergency unblinding via IRT system available 24/7. Requires two-factor authentication. PI must provide clinical justification and attempt to consult medical monitor before executing if patient condition allows.",
                "interim_unblinding_plan": "Two planned interim analyses at 50% and 75% information fractions. DSMB reviews unblinded data with pre-specified stopping boundaries (O'Brien-Fleming alpha-spending function).",
                "final_unblinding_plan": "Staged unblinding: (1) Independent statistician first, (2) Sponsor biostatistics after SAP execution confirmed, (3) Clinical team after primary analysis complete.",
                "authorized_unblinders": [
                    "IRT System (emergency)",
                    "DSMB Independent Statistician (interim)",
                    "Lead Biostatistician (final, stage 1)",
                    "Clinical Program Lead (final, stage 3)",
                ],
                "code_break_instructions": "Randomization codes stored in validated IRT system (Oracle Inform RTSM). Emergency access: IRT hotline +1-800-555-0200. Backup sealed code-break envelopes stored in site pharmacy under dual lock. Non-emergency: formal request through eTMF with electronic approval workflow.",
                "notification_requirements": [
                    "Medical Monitor (immediately for emergency)",
                    "DSMB (within 24 hours)",
                    "Ethics Committee (within regulatory timelines)",
                    "All investigators (for final unblinding notification)",
                ],
            },
            {
                "id": "UBP-003",
                "trial_id": LIBTAYO_TRIAL,
                "blinding_level": BlindingLevel.DOUBLE_BLIND,
                "emergency_procedure": "Emergency unblinding through centralized IRT system. PI enters patient ID and clinical justification. System generates audit trail. Medical monitor automatically notified via SMS and email.",
                "interim_unblinding_plan": None,
                "final_unblinding_plan": "Final unblinding conducted after database lock certification. Two-step process: biostatistics team receives codes first for analysis, then clinical team after primary results validated.",
                "authorized_unblinders": [
                    "IRT System (emergency)",
                    "Senior Biostatistician (final)",
                    "Clinical Development Director (final)",
                ],
                "code_break_instructions": "Randomization codes in Medidata Balance. Emergency code break: call +1-800-555-0201. All code breaks are logged with timestamp, requester identity, and reason. Non-emergency requests require email approval from medical monitor and regulatory affairs.",
                "notification_requirements": [
                    "Medical Monitor (within 2 hours for emergency)",
                    "DSMB Chair (within 24 hours)",
                    "Regulatory Affairs (within 48 hours)",
                    "Quality Assurance (for audit trail review)",
                ],
            },
        ]

        for p in policies_data:
            self._policies[p["id"]] = UnblindingPolicy(**p)

    # ------------------------------------------------------------------
    # Unblinding Requests
    # ------------------------------------------------------------------

    def list_requests(
        self,
        *,
        trial_id: str | None = None,
        site_id: str | None = None,
        status: UnblindingStatus | None = None,
        unblinding_type: UnblindingType | None = None,
    ) -> list[UnblindingRequest]:
        """List unblinding requests with optional filters."""
        with self._lock:
            result = list(self._requests.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if site_id is not None:
            result = [r for r in result if r.site_id == site_id]
        if status is not None:
            result = [r for r in result if r.status == status]
        if unblinding_type is not None:
            result = [r for r in result if r.unblinding_type == unblinding_type]

        return sorted(result, key=lambda r: r.requested_date, reverse=True)

    def get_request(self, request_id: str) -> UnblindingRequest | None:
        """Get a single unblinding request by ID."""
        with self._lock:
            return self._requests.get(request_id)

    def create_request(self, payload: UnblindingRequestCreate) -> UnblindingRequest:
        """Create a new unblinding request."""
        now = datetime.now(timezone.utc)
        with self._lock:
            self._request_counter += 1
            request_id = f"UBR-{self._request_counter:03d}"

        req = UnblindingRequest(
            id=request_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            patient_id=payload.patient_id,
            request_number=request_id,
            unblinding_type=payload.unblinding_type,
            status=UnblindingStatus.REQUESTED,
            blinding_level=payload.blinding_level,
            reason=payload.reason,
            clinical_justification=payload.clinical_justification,
            requested_by=payload.requested_by,
            requested_date=now,
            was_emergency=payload.was_emergency,
        )

        with self._lock:
            self._requests[request_id] = req

        logger.info(
            "Created unblinding request %s: type=%s trial=%s",
            request_id, payload.unblinding_type.value, payload.trial_id,
        )
        return req

    def update_request(
        self, request_id: str, payload: UnblindingRequestUpdate
    ) -> UnblindingRequest | None:
        """Update an existing unblinding request."""
        with self._lock:
            existing = self._requests.get(request_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = UnblindingRequest(**data)
            self._requests[request_id] = updated
        return updated

    def approve_request(
        self,
        request_id: str,
        *,
        approved_by: str,
        approval_authority: ApprovalAuthority,
    ) -> UnblindingRequest | None:
        """Approve an unblinding request.

        Only requests in 'requested' status can be approved.
        """
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._requests.get(request_id)
            if existing is None:
                return None

            if existing.status != UnblindingStatus.REQUESTED:
                raise ValueError(
                    f"Cannot approve request '{request_id}' with status '{existing.status.value}'. "
                    f"Only requests in 'requested' status can be approved."
                )

            data = existing.model_dump()
            data["status"] = UnblindingStatus.APPROVED
            data["approved_by"] = approved_by
            data["approval_authority"] = approval_authority
            data["approved_date"] = now
            updated = UnblindingRequest(**data)
            self._requests[request_id] = updated

        logger.info(
            "Approved unblinding request %s by %s (%s)",
            request_id, approved_by, approval_authority.value,
        )
        return updated

    def deny_request(
        self,
        request_id: str,
        *,
        denied_by: str,
        denial_reason: str,
    ) -> UnblindingRequest | None:
        """Deny an unblinding request.

        Only requests in 'requested' status can be denied.
        """
        with self._lock:
            existing = self._requests.get(request_id)
            if existing is None:
                return None

            if existing.status != UnblindingStatus.REQUESTED:
                raise ValueError(
                    f"Cannot deny request '{request_id}' with status '{existing.status.value}'. "
                    f"Only requests in 'requested' status can be denied."
                )

            data = existing.model_dump()
            data["status"] = UnblindingStatus.DENIED
            data["impact_on_study"] = f"Denied by {denied_by}: {denial_reason}"
            updated = UnblindingRequest(**data)
            self._requests[request_id] = updated

        logger.info("Denied unblinding request %s by %s", request_id, denied_by)
        return updated

    def execute_request(
        self,
        request_id: str,
        *,
        executed_by: str,
        treatment_assignment: str,
    ) -> UnblindingRequest | None:
        """Execute an approved unblinding request.

        Only requests in 'approved' status can be executed.
        """
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._requests.get(request_id)
            if existing is None:
                return None

            if existing.status != UnblindingStatus.APPROVED:
                raise ValueError(
                    f"Cannot execute request '{request_id}' with status '{existing.status.value}'. "
                    f"Only requests in 'approved' status can be executed."
                )

            data = existing.model_dump()
            data["status"] = UnblindingStatus.EXECUTED
            data["executed_by"] = executed_by
            data["executed_date"] = now
            data["treatment_assignment"] = treatment_assignment
            updated = UnblindingRequest(**data)
            self._requests[request_id] = updated

        logger.info(
            "Executed unblinding request %s by %s: assignment=%s",
            request_id, executed_by, treatment_assignment,
        )
        return updated

    def cancel_request(
        self,
        request_id: str,
        *,
        cancelled_by: str,
        cancellation_reason: str,
    ) -> UnblindingRequest | None:
        """Cancel an unblinding request.

        Only requests in 'requested' or 'approved' status can be cancelled.
        """
        with self._lock:
            existing = self._requests.get(request_id)
            if existing is None:
                return None

            if existing.status not in (
                UnblindingStatus.REQUESTED,
                UnblindingStatus.APPROVED,
            ):
                raise ValueError(
                    f"Cannot cancel request '{request_id}' with status '{existing.status.value}'. "
                    f"Only requests in 'requested' or 'approved' status can be cancelled."
                )

            data = existing.model_dump()
            data["status"] = UnblindingStatus.CANCELLED
            data["impact_on_study"] = (
                f"Cancelled by {cancelled_by}: {cancellation_reason}"
            )
            updated = UnblindingRequest(**data)
            self._requests[request_id] = updated

        logger.info("Cancelled unblinding request %s by %s", request_id, cancelled_by)
        return updated

    # ------------------------------------------------------------------
    # Unblinding Policies
    # ------------------------------------------------------------------

    def list_policies(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[UnblindingPolicy]:
        """List unblinding policies with optional trial filter."""
        with self._lock:
            result = list(self._policies.values())

        if trial_id is not None:
            result = [p for p in result if p.trial_id == trial_id]

        return sorted(result, key=lambda p: p.id)

    def get_policy(self, policy_id: str) -> UnblindingPolicy | None:
        """Get a single unblinding policy by ID."""
        with self._lock:
            return self._policies.get(policy_id)

    def create_policy(self, payload: UnblindingPolicyCreate) -> UnblindingPolicy:
        """Create a new unblinding policy."""
        policy_id = f"UBP-{uuid4().hex[:8].upper()}"
        policy = UnblindingPolicy(
            id=policy_id,
            **payload.model_dump(),
        )
        with self._lock:
            self._policies[policy_id] = policy
        logger.info(
            "Created unblinding policy %s for trial %s",
            policy_id, payload.trial_id,
        )
        return policy

    def update_policy(
        self, policy_id: str, payload: UnblindingPolicyUpdate
    ) -> UnblindingPolicy | None:
        """Update an existing unblinding policy."""
        with self._lock:
            existing = self._policies.get(policy_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = UnblindingPolicy(**data)
            self._policies[policy_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> UnblindingMetrics:
        """Compute aggregated unblinding management metrics."""
        with self._lock:
            requests = list(self._requests.values())
            policies = list(self._policies.values())

        # Requests by status
        by_status: dict[str, int] = {}
        for req in requests:
            key = req.status.value
            by_status[key] = by_status.get(key, 0) + 1

        # Requests by type
        by_type: dict[str, int] = {}
        for req in requests:
            key = req.unblinding_type.value
            by_type[key] = by_type.get(key, 0) + 1

        # Emergency count
        emergency_count = sum(1 for r in requests if r.was_emergency)

        # Executed, denied, cancelled counts
        executed_count = sum(
            1 for r in requests if r.status == UnblindingStatus.EXECUTED
        )
        denied_count = sum(
            1 for r in requests if r.status == UnblindingStatus.DENIED
        )
        cancelled_count = sum(
            1 for r in requests if r.status == UnblindingStatus.CANCELLED
        )
        pending_count = sum(
            1 for r in requests
            if r.status in (UnblindingStatus.REQUESTED, UnblindingStatus.APPROVED)
        )

        # Average approval time for approved/executed requests
        approval_deltas: list[float] = []
        for req in requests:
            if req.approved_date and req.requested_date:
                delta = (req.approved_date - req.requested_date).total_seconds() / 3600.0
                approval_deltas.append(delta)

        avg_approval_time = (
            round(sum(approval_deltas) / len(approval_deltas), 1)
            if approval_deltas
            else None
        )

        return UnblindingMetrics(
            total_requests=len(requests),
            requests_by_status=by_status,
            requests_by_type=by_type,
            emergency_unblinding_count=emergency_count,
            average_approval_time_hours=avg_approval_time,
            total_policies=len(policies),
            executed_count=executed_count,
            denied_count=denied_count,
            cancelled_count=cancelled_count,
            pending_requests=pending_count,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: UnblindingManagementService | None = None
_lock = threading.Lock()


def get_unblinding_management_service() -> UnblindingManagementService:
    """Return the singleton UnblindingManagementService instance."""
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = UnblindingManagementService()
    return _instance


def reset_unblinding_management_service() -> UnblindingManagementService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _lock:
        _instance = UnblindingManagementService()
    return _instance
