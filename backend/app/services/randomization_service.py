"""Randomization & Blinding Service (CLINICAL-1).

Manages treatment arm randomization across clinical trials using block,
stratified, and adaptive algorithms. Enforces blinding levels, handles
unblinding requests with approval workflow, performs balance checking,
and maintains a complete audit trail.

Usage:
    from app.services.randomization_service import (
        get_randomization_service,
    )

    svc = get_randomization_service()
    assignment = svc.randomize_patient("SCHEME-001", request)
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import hashlib
import logging
import math
import random
import threading
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4

from app.schemas.randomization import (
    AllocationRatio,
    ArmType,
    BalanceCheck,
    BalanceReport,
    BlindedAssignment,
    BlindingLevel,
    RandomizationAssignment,
    RandomizationAuditEntry,
    RandomizationMetrics,
    RandomizationMethod,
    RandomizationScheme,
    RandomizationStatus,
    RandomizePatientRequest,
    SchemeCreate,
    SchemeUpdate,
    StratificationFactor,
    TreatmentArm,
    UnblindingApproval,
    UnblindingReason,
    UnblindingRequest,
    UnblindingRequestCreate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Valid status transitions
# ---------------------------------------------------------------------------

VALID_STATUS_TRANSITIONS: dict[RandomizationStatus, set[RandomizationStatus]] = {
    RandomizationStatus.DRAFT: {RandomizationStatus.VALIDATED},
    RandomizationStatus.VALIDATED: {RandomizationStatus.ACTIVE, RandomizationStatus.DRAFT},
    RandomizationStatus.ACTIVE: {RandomizationStatus.LOCKED, RandomizationStatus.COMPLETED},
    RandomizationStatus.LOCKED: {RandomizationStatus.COMPLETED},
    RandomizationStatus.COMPLETED: set(),  # terminal
}

# Imbalance threshold for acceptability
IMBALANCE_THRESHOLD = 5.0


class RandomizationService:
    """In-memory randomization and blinding engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._schemes: dict[str, RandomizationScheme] = {}
        self._assignments: dict[str, RandomizationAssignment] = {}
        self._unblinding_requests: dict[str, UnblindingRequest] = {}
        self._audit_trail: list[RandomizationAuditEntry] = []
        self._sequence_counters: dict[str, int] = {}  # scheme_id -> next seq
        self._block_positions: dict[str, list[str]] = {}  # scheme_id -> remaining block
        self._lock = threading.RLock()
        self._rng = random.Random(42)
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate randomization data for the 3 Regeneron trials."""
        now = datetime.now(timezone.utc)

        # Stable trial IDs matching trial_eligibility_service
        eylea_id = "00000000-de00-0001-0000-000000000001"
        dupixent_id = "00000000-de00-0002-0000-000000000002"
        libtayo_id = "00000000-de00-0003-0000-000000000003"

        # ----- Scheme 1: EYLEA HD (2:1 treatment:sham, block, double-blind) -----
        eylea_arms = [
            TreatmentArm(
                id="ARM-EYLEA-TX",
                name="EYLEA HD 8mg",
                arm_type=ArmType.TREATMENT,
                description="Aflibercept 8mg intravitreal injection",
                allocation_weight=2.0,
                current_count=0,
                target_count=200,
            ),
            TreatmentArm(
                id="ARM-EYLEA-SHAM",
                name="Sham Procedure",
                arm_type=ArmType.SHAM,
                description="Sham intravitreal injection procedure",
                allocation_weight=1.0,
                current_count=0,
                target_count=100,
            ),
        ]

        eylea_strat = [
            StratificationFactor(
                id="SF-EYLEA-BCVA",
                name="Baseline BCVA",
                description="Best-corrected visual acuity at baseline",
                levels=["<=55 letters", "56-70 letters", ">70 letters"],
            ),
            StratificationFactor(
                id="SF-EYLEA-DM",
                name="Diabetes Type",
                description="Type of diabetes",
                levels=["Type 1", "Type 2"],
            ),
        ]

        eylea_scheme = RandomizationScheme(
            id="RAND-EYLEA-001",
            trial_id=eylea_id,
            trial_name="EYLEA HD Phase III - Diabetic Macular Edema",
            method=RandomizationMethod.BLOCK,
            blinding_level=BlindingLevel.DOUBLE_BLIND,
            allocation_ratio=AllocationRatio.RATIO_2_1,
            status=RandomizationStatus.ACTIVE,
            arms=eylea_arms,
            stratification_factors=eylea_strat,
            block_sizes=[3, 6, 9],
            seed=42,
            total_randomized=0,
            created_at=now - timedelta(days=120),
            updated_at=now - timedelta(days=5),
            validated_by="Dr. Protocol Officer",
        )

        # ----- Scheme 2: Dupixent (1:1 stratified by severity, double-blind) -----
        dupixent_arms = [
            TreatmentArm(
                id="ARM-DUP-TX",
                name="Dupixent 300mg",
                arm_type=ArmType.TREATMENT,
                description="Dupilumab 300mg subcutaneous every 2 weeks",
                allocation_weight=1.0,
                current_count=0,
                target_count=150,
            ),
            TreatmentArm(
                id="ARM-DUP-PBO",
                name="Placebo",
                arm_type=ArmType.PLACEBO,
                description="Matching placebo subcutaneous injection",
                allocation_weight=1.0,
                current_count=0,
                target_count=150,
            ),
        ]

        dupixent_strat = [
            StratificationFactor(
                id="SF-DUP-SEV",
                name="Disease Severity",
                description="Baseline eczema severity (IGA score)",
                levels=["Moderate (IGA 3)", "Severe (IGA 4)"],
            ),
            StratificationFactor(
                id="SF-DUP-PRIOR",
                name="Prior Systemic Therapy",
                description="Previous systemic immunosuppressant use",
                levels=["Yes", "No"],
            ),
        ]

        dupixent_scheme = RandomizationScheme(
            id="RAND-DUP-001",
            trial_id=dupixent_id,
            trial_name="Dupixent Phase III - Atopic Dermatitis",
            method=RandomizationMethod.STRATIFIED,
            blinding_level=BlindingLevel.DOUBLE_BLIND,
            allocation_ratio=AllocationRatio.EQUAL_1_1,
            status=RandomizationStatus.ACTIVE,
            arms=dupixent_arms,
            stratification_factors=dupixent_strat,
            block_sizes=[4, 6],
            seed=123,
            total_randomized=0,
            created_at=now - timedelta(days=90),
            updated_at=now - timedelta(days=3),
            validated_by="Dr. Biostatistician Lead",
        )

        # ----- Scheme 3: Libtayo (3:2 treatment:placebo, adaptive) -----
        libtayo_arms = [
            TreatmentArm(
                id="ARM-LIB-TX",
                name="Libtayo 350mg",
                arm_type=ArmType.TREATMENT,
                description="Cemiplimab 350mg IV every 3 weeks",
                allocation_weight=3.0,
                current_count=0,
                target_count=180,
            ),
            TreatmentArm(
                id="ARM-LIB-PBO",
                name="Placebo",
                arm_type=ArmType.PLACEBO,
                description="Matching IV placebo infusion",
                allocation_weight=2.0,
                current_count=0,
                target_count=120,
            ),
        ]

        libtayo_strat = [
            StratificationFactor(
                id="SF-LIB-PDSTAGE",
                name="PD-L1 Expression",
                description="PD-L1 combined positive score",
                levels=["CPS >= 50", "CPS 1-49", "CPS < 1"],
            ),
        ]

        libtayo_scheme = RandomizationScheme(
            id="RAND-LIB-001",
            trial_id=libtayo_id,
            trial_name="Libtayo Phase III - NSCLC First-Line",
            method=RandomizationMethod.ADAPTIVE,
            blinding_level=BlindingLevel.DOUBLE_BLIND,
            allocation_ratio=AllocationRatio.RATIO_3_2,
            status=RandomizationStatus.ACTIVE,
            arms=libtayo_arms,
            stratification_factors=libtayo_strat,
            block_sizes=[5, 10],
            seed=999,
            total_randomized=0,
            created_at=now - timedelta(days=60),
            updated_at=now - timedelta(days=1),
            validated_by="Dr. Statistical Lead",
        )

        self._schemes = {
            eylea_scheme.id: eylea_scheme,
            dupixent_scheme.id: dupixent_scheme,
            libtayo_scheme.id: libtayo_scheme,
        }

        self._sequence_counters = {
            eylea_scheme.id: 1,
            dupixent_scheme.id: 1,
            libtayo_scheme.id: 1,
        }

        # Seed 30 randomization assignments (10 per scheme)
        self._seed_assignments(eylea_scheme, dupixent_scheme, libtayo_scheme, now)

        # Seed 2 unblinding requests
        self._seed_unblinding_requests(now)

        # Record seed audit entries
        for scheme in [eylea_scheme, dupixent_scheme, libtayo_scheme]:
            self._audit_trail.append(
                RandomizationAuditEntry(
                    id=f"AUDIT-SEED-{scheme.id}",
                    scheme_id=scheme.id,
                    action="SCHEME_CREATED",
                    actor="system",
                    timestamp=scheme.created_at,
                    details={"method": scheme.method.value, "blinding": scheme.blinding_level.value},
                )
            )

    def _seed_assignments(
        self,
        eylea: RandomizationScheme,
        dupixent: RandomizationScheme,
        libtayo: RandomizationScheme,
        now: datetime,
    ) -> None:
        """Create 30 seed assignments (10 per scheme)."""
        schemes = [eylea, dupixent, libtayo]
        prefixes = ["EYLEA", "DUP", "LIB"]
        patient_prefixes = ["PAT-DME", "PAT-AD", "PAT-NSCLC"]
        strata_options = [
            [
                {"Baseline BCVA": "<=55 letters", "Diabetes Type": "Type 2"},
                {"Baseline BCVA": "56-70 letters", "Diabetes Type": "Type 1"},
                {"Baseline BCVA": ">70 letters", "Diabetes Type": "Type 2"},
            ],
            [
                {"Disease Severity": "Moderate (IGA 3)", "Prior Systemic Therapy": "No"},
                {"Disease Severity": "Severe (IGA 4)", "Prior Systemic Therapy": "Yes"},
                {"Disease Severity": "Moderate (IGA 3)", "Prior Systemic Therapy": "Yes"},
            ],
            [
                {"PD-L1 Expression": "CPS >= 50"},
                {"PD-L1 Expression": "CPS 1-49"},
                {"PD-L1 Expression": "CPS < 1"},
            ],
        ]

        rng = random.Random(42)

        for idx, scheme in enumerate(schemes):
            for i in range(1, 11):
                # Determine arm based on allocation ratio
                weights = [a.allocation_weight for a in scheme.arms]
                arm = rng.choices(scheme.arms, weights=weights, k=1)[0]

                stratum_values = strata_options[idx][i % len(strata_options[idx])]
                stratum_key = "|".join(f"{k}={v}" for k, v in sorted(stratum_values.items()))

                # Generate blinding code
                blinding_code = self._generate_blinding_code(scheme.id, i)

                assignment = RandomizationAssignment(
                    id=f"ASSIGN-{prefixes[idx]}-{i:03d}",
                    scheme_id=scheme.id,
                    patient_id=f"{patient_prefixes[idx]}-{i:03d}",
                    arm_id=arm.id,
                    arm_name=arm.name,
                    stratum=stratum_key,
                    sequence_number=i,
                    randomized_at=now - timedelta(days=90 - i * 3),
                    randomized_by="system_seed",
                    blinding_code=blinding_code,
                    is_unblinded=False,
                )
                self._assignments[assignment.id] = assignment

                # Update arm count
                for a in scheme.arms:
                    if a.id == arm.id:
                        a.current_count += 1

                scheme.total_randomized += 1
                self._sequence_counters[scheme.id] = i + 1

    def _seed_unblinding_requests(self, now: datetime) -> None:
        """Create 2 seed unblinding requests."""
        # Request 1: pending emergency unblinding for EYLEA patient
        req1 = UnblindingRequest(
            id="UNBLIND-001",
            assignment_id="ASSIGN-EYLEA-003",
            patient_id="PAT-DME-003",
            requestor="Dr. Sarah Chen",
            reason=UnblindingReason.MEDICAL_EMERGENCY,
            urgency="emergency",
            approved=None,
            created_at=now - timedelta(hours=6),
        )

        # Request 2: approved SAE assessment for Libtayo patient
        req2 = UnblindingRequest(
            id="UNBLIND-002",
            assignment_id="ASSIGN-LIB-005",
            patient_id="PAT-NSCLC-005",
            requestor="Dr. James Park",
            reason=UnblindingReason.SAE_ASSESSMENT,
            urgency="urgent",
            approved=True,
            approved_by="Dr. DSMB Chair",
            approved_at=now - timedelta(hours=2),
            created_at=now - timedelta(hours=12),
        )

        self._unblinding_requests = {
            req1.id: req1,
            req2.id: req2,
        }

        # Mark the approved unblinding as executed
        assign = self._assignments.get("ASSIGN-LIB-005")
        if assign:
            assign.is_unblinded = True
            assign.unblinding_reason = UnblindingReason.SAE_ASSESSMENT
            assign.unblinded_at = now - timedelta(hours=2)
            assign.unblinded_by = "Dr. DSMB Chair"

    # ------------------------------------------------------------------
    # Blinding code generation
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_blinding_code(scheme_id: str, sequence: int) -> str:
        """Generate a deterministic blinding code that masks arm identity."""
        raw = f"{scheme_id}:{sequence}:blind"
        h = hashlib.sha256(raw.encode()).hexdigest()[:8].upper()
        return f"BL-{h}"

    # ------------------------------------------------------------------
    # Scheme CRUD
    # ------------------------------------------------------------------

    def list_schemes(
        self,
        trial_id: Optional[str] = None,
        status: Optional[RandomizationStatus] = None,
        method: Optional[RandomizationMethod] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[RandomizationScheme], int]:
        """List schemes with optional filters."""
        with self._lock:
            items = list(self._schemes.values())
            if trial_id:
                items = [s for s in items if s.trial_id == trial_id]
            if status:
                items = [s for s in items if s.status == status]
            if method:
                items = [s for s in items if s.method == method]
            total = len(items)
            items.sort(key=lambda s: s.created_at, reverse=True)
            return items[offset : offset + limit], total

    def get_scheme(self, scheme_id: str) -> Optional[RandomizationScheme]:
        """Get a single scheme by ID."""
        return self._schemes.get(scheme_id)

    def create_scheme(self, req: SchemeCreate) -> RandomizationScheme:
        """Create a new randomization scheme."""
        now = datetime.now(timezone.utc)
        scheme_id = f"RAND-{uuid4().hex[:8].upper()}"

        scheme = RandomizationScheme(
            id=scheme_id,
            trial_id=req.trial_id,
            trial_name=req.trial_name,
            method=req.method,
            blinding_level=req.blinding_level,
            allocation_ratio=req.allocation_ratio,
            status=RandomizationStatus.DRAFT,
            arms=req.arms,
            stratification_factors=req.stratification_factors,
            block_sizes=req.block_sizes,
            seed=req.seed,
            total_randomized=0,
            created_at=now,
            updated_at=now,
        )

        with self._lock:
            self._schemes[scheme_id] = scheme
            self._sequence_counters[scheme_id] = 1
            self._record_audit(scheme_id, "SCHEME_CREATED", "system", {
                "method": req.method.value,
                "blinding": req.blinding_level.value,
                "arms": len(req.arms),
            })

        return scheme

    def update_scheme(self, scheme_id: str, req: SchemeUpdate) -> Optional[RandomizationScheme]:
        """Update a scheme (only DRAFT/VALIDATED)."""
        with self._lock:
            scheme = self._schemes.get(scheme_id)
            if not scheme:
                return None
            if scheme.status not in (RandomizationStatus.DRAFT, RandomizationStatus.VALIDATED):
                raise ValueError(f"Cannot update scheme in status {scheme.status.value}")

            if req.trial_name is not None:
                scheme.trial_name = req.trial_name
            if req.method is not None:
                scheme.method = req.method
            if req.blinding_level is not None:
                scheme.blinding_level = req.blinding_level
            if req.allocation_ratio is not None:
                scheme.allocation_ratio = req.allocation_ratio
            if req.block_sizes is not None:
                scheme.block_sizes = req.block_sizes
            if req.seed is not None:
                scheme.seed = req.seed

            scheme.updated_at = datetime.now(timezone.utc)
            self._record_audit(scheme_id, "SCHEME_UPDATED", "system", {
                "fields_updated": [f for f in req.model_fields_set],
            })
            return scheme

    def delete_scheme(self, scheme_id: str) -> bool:
        """Delete a scheme (only DRAFT)."""
        with self._lock:
            scheme = self._schemes.get(scheme_id)
            if not scheme:
                return False
            if scheme.status != RandomizationStatus.DRAFT:
                raise ValueError("Can only delete DRAFT schemes")
            del self._schemes[scheme_id]
            self._record_audit(scheme_id, "SCHEME_DELETED", "system", {})
            return True

    # ------------------------------------------------------------------
    # Scheme lifecycle (validate, activate, lock, complete)
    # ------------------------------------------------------------------

    def validate_scheme(self, scheme_id: str, validated_by: str) -> Optional[RandomizationScheme]:
        """Validate a scheme (DRAFT -> VALIDATED)."""
        with self._lock:
            scheme = self._schemes.get(scheme_id)
            if not scheme:
                return None
            if scheme.status != RandomizationStatus.DRAFT:
                raise ValueError(f"Cannot validate scheme in status {scheme.status.value}")
            # Validation checks
            if len(scheme.arms) < 2:
                raise ValueError("Scheme must have at least 2 arms")
            if scheme.method == RandomizationMethod.BLOCK and not scheme.block_sizes:
                raise ValueError("Block randomization requires block_sizes")
            if scheme.method == RandomizationMethod.STRATIFIED and not scheme.stratification_factors:
                raise ValueError("Stratified randomization requires stratification_factors")

            scheme.status = RandomizationStatus.VALIDATED
            scheme.validated_by = validated_by
            scheme.updated_at = datetime.now(timezone.utc)
            self._record_audit(scheme_id, "SCHEME_VALIDATED", validated_by, {})
            return scheme

    def activate_scheme(self, scheme_id: str) -> Optional[RandomizationScheme]:
        """Activate a validated scheme (VALIDATED -> ACTIVE)."""
        with self._lock:
            scheme = self._schemes.get(scheme_id)
            if not scheme:
                return None
            if scheme.status != RandomizationStatus.VALIDATED:
                raise ValueError(f"Cannot activate scheme in status {scheme.status.value}")
            scheme.status = RandomizationStatus.ACTIVE
            scheme.updated_at = datetime.now(timezone.utc)
            self._record_audit(scheme_id, "SCHEME_ACTIVATED", "system", {})
            return scheme

    def lock_scheme(self, scheme_id: str, locked_by: str = "system") -> Optional[RandomizationScheme]:
        """Lock a scheme (ACTIVE -> LOCKED). No more randomizations allowed."""
        with self._lock:
            scheme = self._schemes.get(scheme_id)
            if not scheme:
                return None
            if scheme.status != RandomizationStatus.ACTIVE:
                raise ValueError(f"Cannot lock scheme in status {scheme.status.value}")
            scheme.status = RandomizationStatus.LOCKED
            scheme.locked_at = datetime.now(timezone.utc)
            scheme.updated_at = scheme.locked_at
            self._record_audit(scheme_id, "SCHEME_LOCKED", locked_by, {
                "total_randomized": scheme.total_randomized,
            })
            return scheme

    def complete_scheme(self, scheme_id: str) -> Optional[RandomizationScheme]:
        """Complete a scheme (ACTIVE or LOCKED -> COMPLETED)."""
        with self._lock:
            scheme = self._schemes.get(scheme_id)
            if not scheme:
                return None
            if scheme.status not in (RandomizationStatus.ACTIVE, RandomizationStatus.LOCKED):
                raise ValueError(f"Cannot complete scheme in status {scheme.status.value}")
            scheme.status = RandomizationStatus.COMPLETED
            scheme.updated_at = datetime.now(timezone.utc)
            self._record_audit(scheme_id, "SCHEME_COMPLETED", "system", {
                "total_randomized": scheme.total_randomized,
            })
            return scheme

    # ------------------------------------------------------------------
    # Randomization algorithms
    # ------------------------------------------------------------------

    def randomize_patient(
        self, scheme_id: str, req: RandomizePatientRequest
    ) -> RandomizationAssignment:
        """Randomize a patient to a treatment arm."""
        with self._lock:
            scheme = self._schemes.get(scheme_id)
            if not scheme:
                raise ValueError(f"Scheme {scheme_id} not found")
            if scheme.status != RandomizationStatus.ACTIVE:
                raise ValueError(f"Scheme is not active (status: {scheme.status.value})")

            # Check for duplicate randomization
            for a in self._assignments.values():
                if a.scheme_id == scheme_id and a.patient_id == req.patient_id:
                    raise ValueError(f"Patient {req.patient_id} already randomized in scheme {scheme_id}")

            # Build stratum key
            stratum_key = None
            if req.stratum:
                stratum_key = "|".join(f"{k}={v}" for k, v in sorted(req.stratum.items()))

            # Select arm based on method
            arm = self._select_arm(scheme, stratum_key)

            seq = self._sequence_counters.get(scheme_id, 1)
            blinding_code = self._generate_blinding_code(scheme_id, seq)

            assignment = RandomizationAssignment(
                id=f"ASSIGN-{uuid4().hex[:8].upper()}",
                scheme_id=scheme_id,
                patient_id=req.patient_id,
                arm_id=arm.id,
                arm_name=arm.name,
                stratum=stratum_key,
                sequence_number=seq,
                randomized_at=datetime.now(timezone.utc),
                randomized_by=req.randomized_by,
                blinding_code=blinding_code,
            )

            self._assignments[assignment.id] = assignment
            self._sequence_counters[scheme_id] = seq + 1

            # Update scheme counts
            for a in scheme.arms:
                if a.id == arm.id:
                    a.current_count += 1
            scheme.total_randomized += 1
            scheme.updated_at = datetime.now(timezone.utc)

            self._record_audit(scheme_id, "PATIENT_RANDOMIZED", req.randomized_by, {
                "patient_id": req.patient_id,
                "assignment_id": assignment.id,
                "sequence_number": seq,
                "stratum": stratum_key,
            })

            return assignment

    def _select_arm(self, scheme: RandomizationScheme, stratum_key: Optional[str]) -> TreatmentArm:
        """Select a treatment arm based on the randomization method."""
        if scheme.method == RandomizationMethod.BLOCK:
            return self._block_randomize(scheme)
        elif scheme.method == RandomizationMethod.STRATIFIED:
            return self._stratified_randomize(scheme, stratum_key)
        elif scheme.method in (RandomizationMethod.ADAPTIVE, RandomizationMethod.RESPONSE_ADAPTIVE):
            return self._adaptive_randomize(scheme)
        elif scheme.method == RandomizationMethod.MINIMIZATION:
            return self._minimization_randomize(scheme, stratum_key)
        else:
            # Simple randomization
            return self._simple_randomize(scheme)

    def _simple_randomize(self, scheme: RandomizationScheme) -> TreatmentArm:
        """Simple random allocation based on weights."""
        weights = [arm.allocation_weight for arm in scheme.arms]
        return self._rng.choices(scheme.arms, weights=weights, k=1)[0]

    def _block_randomize(self, scheme: RandomizationScheme) -> TreatmentArm:
        """Block randomization to ensure balanced allocation within blocks."""
        block_key = scheme.id

        # Check if we have a current block with remaining slots
        if block_key not in self._block_positions or not self._block_positions[block_key]:
            # Generate new block
            block_size = self._rng.choice(scheme.block_sizes) if scheme.block_sizes else 6
            block = self._generate_block(scheme, block_size)
            self._rng.shuffle(block)
            self._block_positions[block_key] = block

        arm_id = self._block_positions[block_key].pop(0)
        for arm in scheme.arms:
            if arm.id == arm_id:
                return arm

        # Fallback
        return scheme.arms[0]

    def _generate_block(self, scheme: RandomizationScheme, block_size: int) -> list[str]:
        """Generate a randomization block respecting allocation weights."""
        total_weight = sum(arm.allocation_weight for arm in scheme.arms)
        block: list[str] = []
        for arm in scheme.arms:
            count = max(1, round(block_size * arm.allocation_weight / total_weight))
            block.extend([arm.id] * count)
        return block

    def _stratified_randomize(
        self, scheme: RandomizationScheme, stratum_key: Optional[str]
    ) -> TreatmentArm:
        """Stratified block randomization within strata."""
        # Use stratum-specific block key
        block_key = f"{scheme.id}:{stratum_key or 'default'}"

        if block_key not in self._block_positions or not self._block_positions[block_key]:
            block_size = self._rng.choice(scheme.block_sizes) if scheme.block_sizes else 4
            block = self._generate_block(scheme, block_size)
            self._rng.shuffle(block)
            self._block_positions[block_key] = block

        arm_id = self._block_positions[block_key].pop(0)
        for arm in scheme.arms:
            if arm.id == arm_id:
                return arm

        return scheme.arms[0]

    def _adaptive_randomize(self, scheme: RandomizationScheme) -> TreatmentArm:
        """Adaptive randomization: bias allocation toward underrepresented arms."""
        total_weight = sum(arm.allocation_weight for arm in scheme.arms)
        total_assigned = sum(arm.current_count for arm in scheme.arms)

        if total_assigned == 0:
            return self._simple_randomize(scheme)

        # Calculate adjusted weights based on current imbalance
        adjusted_weights = []
        for arm in scheme.arms:
            expected_ratio = arm.allocation_weight / total_weight
            actual_ratio = arm.current_count / max(1, total_assigned)
            # Increase weight for underrepresented arms
            deficit = expected_ratio - actual_ratio
            adjusted = arm.allocation_weight * (1.0 + 2.0 * deficit)
            adjusted_weights.append(max(0.1, adjusted))

        return self._rng.choices(scheme.arms, weights=adjusted_weights, k=1)[0]

    def _minimization_randomize(
        self, scheme: RandomizationScheme, stratum_key: Optional[str]
    ) -> TreatmentArm:
        """Minimization: deterministically assign to minimize imbalance."""
        # Count assignments per arm for the current stratum
        stratum_counts: dict[str, int] = {arm.id: 0 for arm in scheme.arms}
        for a in self._assignments.values():
            if a.scheme_id == scheme.id and a.stratum == stratum_key:
                stratum_counts[a.arm_id] = stratum_counts.get(a.arm_id, 0) + 1

        # Find arm with minimum count, weighted by allocation
        total_weight = sum(arm.allocation_weight for arm in scheme.arms)
        best_arm = scheme.arms[0]
        best_score = float("inf")
        for arm in scheme.arms:
            expected_ratio = arm.allocation_weight / total_weight
            score = stratum_counts.get(arm.id, 0) / max(0.01, expected_ratio)
            if score < best_score:
                best_score = score
                best_arm = arm

        # Add randomization element (80% deterministic, 20% random)
        if self._rng.random() < 0.2:
            return self._simple_randomize(scheme)
        return best_arm

    # ------------------------------------------------------------------
    # Assignment lookup
    # ------------------------------------------------------------------

    def get_assignment(self, assignment_id: str) -> Optional[RandomizationAssignment]:
        """Get a full (unblinded) assignment by ID."""
        return self._assignments.get(assignment_id)

    def get_blinded_assignment(self, assignment_id: str) -> Optional[BlindedAssignment]:
        """Get a blinded view of an assignment (no arm details)."""
        a = self._assignments.get(assignment_id)
        if not a:
            return None
        return BlindedAssignment(
            id=a.id,
            scheme_id=a.scheme_id,
            patient_id=a.patient_id,
            blinding_code=a.blinding_code,
            sequence_number=a.sequence_number,
            randomized_at=a.randomized_at,
            is_unblinded=a.is_unblinded,
        )

    def list_assignments(
        self,
        scheme_id: Optional[str] = None,
        patient_id: Optional[str] = None,
        arm_id: Optional[str] = None,
        is_unblinded: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[RandomizationAssignment], int]:
        """List assignments with optional filters."""
        with self._lock:
            items = list(self._assignments.values())
            if scheme_id:
                items = [a for a in items if a.scheme_id == scheme_id]
            if patient_id:
                items = [a for a in items if a.patient_id == patient_id]
            if arm_id:
                items = [a for a in items if a.arm_id == arm_id]
            if is_unblinded is not None:
                items = [a for a in items if a.is_unblinded == is_unblinded]
            total = len(items)
            items.sort(key=lambda a: a.sequence_number)
            return items[offset : offset + limit], total

    def list_blinded_assignments(
        self,
        scheme_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[BlindedAssignment], int]:
        """List blinded views of assignments."""
        with self._lock:
            items = list(self._assignments.values())
            if scheme_id:
                items = [a for a in items if a.scheme_id == scheme_id]
            total = len(items)
            items.sort(key=lambda a: a.sequence_number)
            blinded = [
                BlindedAssignment(
                    id=a.id,
                    scheme_id=a.scheme_id,
                    patient_id=a.patient_id,
                    blinding_code=a.blinding_code,
                    sequence_number=a.sequence_number,
                    randomized_at=a.randomized_at,
                    is_unblinded=a.is_unblinded,
                )
                for a in items[offset : offset + limit]
            ]
            return blinded, total

    def get_patient_assignment(self, scheme_id: str, patient_id: str) -> Optional[RandomizationAssignment]:
        """Look up a patient's assignment within a scheme."""
        for a in self._assignments.values():
            if a.scheme_id == scheme_id and a.patient_id == patient_id:
                return a
        return None

    # ------------------------------------------------------------------
    # Unblinding workflow
    # ------------------------------------------------------------------

    def create_unblinding_request(self, req: UnblindingRequestCreate) -> UnblindingRequest:
        """Create a new unblinding request."""
        with self._lock:
            assignment = self._assignments.get(req.assignment_id)
            if not assignment:
                raise ValueError(f"Assignment {req.assignment_id} not found")
            if assignment.is_unblinded:
                raise ValueError(f"Assignment {req.assignment_id} is already unblinded")

            # Check scheme blinding level
            scheme = self._schemes.get(assignment.scheme_id)
            if scheme and scheme.blinding_level == BlindingLevel.OPEN_LABEL:
                raise ValueError("Cannot request unblinding for open-label study")

            request_id = f"UNBLIND-{uuid4().hex[:6].upper()}"
            unblinding_req = UnblindingRequest(
                id=request_id,
                assignment_id=req.assignment_id,
                patient_id=req.patient_id,
                requestor=req.requestor,
                reason=req.reason,
                urgency=req.urgency,
                created_at=datetime.now(timezone.utc),
            )
            self._unblinding_requests[request_id] = unblinding_req

            self._record_audit(
                assignment.scheme_id,
                "UNBLINDING_REQUESTED",
                req.requestor,
                {
                    "request_id": request_id,
                    "assignment_id": req.assignment_id,
                    "patient_id": req.patient_id,
                    "reason": req.reason.value,
                    "urgency": req.urgency,
                },
            )

            return unblinding_req

    def approve_unblinding(self, request_id: str, approval: UnblindingApproval) -> Optional[UnblindingRequest]:
        """Approve or reject an unblinding request."""
        with self._lock:
            req = self._unblinding_requests.get(request_id)
            if not req:
                return None
            if req.approved is not None:
                raise ValueError(f"Request {request_id} has already been decided")

            now = datetime.now(timezone.utc)
            req.approved = approval.approved
            req.approved_by = approval.approved_by
            req.approved_at = now

            if approval.approved:
                # Execute unblinding
                assignment = self._assignments.get(req.assignment_id)
                if assignment:
                    assignment.is_unblinded = True
                    assignment.unblinding_reason = req.reason
                    assignment.unblinded_at = now
                    assignment.unblinded_by = approval.approved_by

                    self._record_audit(
                        assignment.scheme_id,
                        "PATIENT_UNBLINDED",
                        approval.approved_by,
                        {
                            "request_id": request_id,
                            "assignment_id": req.assignment_id,
                            "patient_id": req.patient_id,
                            "reason": req.reason.value,
                            "arm_revealed": assignment.arm_name,
                        },
                    )
            else:
                assignment = self._assignments.get(req.assignment_id)
                scheme_id = assignment.scheme_id if assignment else "UNKNOWN"
                self._record_audit(
                    scheme_id,
                    "UNBLINDING_REJECTED",
                    approval.approved_by,
                    {
                        "request_id": request_id,
                        "patient_id": req.patient_id,
                    },
                )

            return req

    def list_unblinding_requests(
        self,
        scheme_id: Optional[str] = None,
        pending_only: bool = False,
    ) -> list[UnblindingRequest]:
        """List unblinding requests with optional filters."""
        items = list(self._unblinding_requests.values())
        if scheme_id:
            # Filter by scheme through assignment lookup
            items = [
                r for r in items
                if self._assignments.get(r.assignment_id, None)
                and self._assignments[r.assignment_id].scheme_id == scheme_id
            ]
        if pending_only:
            items = [r for r in items if r.approved is None]
        items.sort(key=lambda r: r.created_at, reverse=True)
        return items

    def get_unblinding_request(self, request_id: str) -> Optional[UnblindingRequest]:
        """Get a single unblinding request."""
        return self._unblinding_requests.get(request_id)

    # ------------------------------------------------------------------
    # Balance checking
    # ------------------------------------------------------------------

    def check_balance(self, scheme_id: str) -> Optional[BalanceReport]:
        """Check randomization balance across stratification factors."""
        with self._lock:
            scheme = self._schemes.get(scheme_id)
            if not scheme:
                return None

            # Get all assignments for this scheme
            assignments = [
                a for a in self._assignments.values() if a.scheme_id == scheme_id
            ]

            arm_totals: dict[str, int] = {}
            for arm in scheme.arms:
                arm_totals[arm.id] = sum(1 for a in assignments if a.arm_id == arm.id)

            factor_checks: list[BalanceCheck] = []
            total_imbalance = 0.0

            if scheme.stratification_factors:
                for factor in scheme.stratification_factors:
                    check = self._check_factor_balance(
                        assignments, scheme.arms, factor
                    )
                    factor_checks.append(check)
                    total_imbalance += check.imbalance_score
            else:
                # Check overall arm balance
                check = self._check_overall_balance(assignments, scheme.arms)
                factor_checks.append(check)
                total_imbalance = check.imbalance_score

            n_factors = max(1, len(factor_checks))
            avg_imbalance = total_imbalance / n_factors

            return BalanceReport(
                scheme_id=scheme_id,
                overall_imbalance=round(avg_imbalance, 4),
                acceptable=avg_imbalance < IMBALANCE_THRESHOLD,
                factors=factor_checks,
                arm_totals=arm_totals,
            )

    def _check_factor_balance(
        self,
        assignments: list[RandomizationAssignment],
        arms: list[TreatmentArm],
        factor: StratificationFactor,
    ) -> BalanceCheck:
        """Check balance for a single stratification factor."""
        counts_per_arm: dict[str, dict[str, int]] = {}
        for arm in arms:
            counts_per_arm[arm.id] = {level: 0 for level in factor.levels}

        for a in assignments:
            if a.stratum:
                # Parse stratum key
                parts = dict(kv.split("=", 1) for kv in a.stratum.split("|") if "=" in kv)
                level = parts.get(factor.name)
                if level and level in counts_per_arm.get(a.arm_id, {}):
                    counts_per_arm[a.arm_id][level] += 1

        # Calculate chi-square imbalance score
        imbalance = self._chi_square_imbalance(counts_per_arm, arms)

        return BalanceCheck(
            factor=factor.name,
            levels=factor.levels,
            counts_per_arm=counts_per_arm,
            imbalance_score=round(imbalance, 4),
            acceptable=imbalance < IMBALANCE_THRESHOLD,
        )

    def _check_overall_balance(
        self,
        assignments: list[RandomizationAssignment],
        arms: list[TreatmentArm],
    ) -> BalanceCheck:
        """Check overall arm balance without stratification."""
        counts_per_arm: dict[str, dict[str, int]] = {}
        for arm in arms:
            count = sum(1 for a in assignments if a.arm_id == arm.id)
            counts_per_arm[arm.id] = {"total": count}

        # Simple imbalance: deviation from expected ratio
        total = len(assignments)
        if total == 0:
            return BalanceCheck(
                factor="Overall",
                levels=["total"],
                counts_per_arm=counts_per_arm,
                imbalance_score=0.0,
                acceptable=True,
            )

        total_weight = sum(arm.allocation_weight for arm in arms)
        imbalance = 0.0
        for arm in arms:
            expected = total * (arm.allocation_weight / total_weight)
            observed = counts_per_arm[arm.id]["total"]
            if expected > 0:
                imbalance += (observed - expected) ** 2 / expected

        return BalanceCheck(
            factor="Overall",
            levels=["total"],
            counts_per_arm=counts_per_arm,
            imbalance_score=round(imbalance, 4),
            acceptable=imbalance < IMBALANCE_THRESHOLD,
        )

    @staticmethod
    def _chi_square_imbalance(
        counts_per_arm: dict[str, dict[str, int]],
        arms: list[TreatmentArm],
    ) -> float:
        """Calculate chi-square-based imbalance across arms and levels."""
        total_weight = sum(arm.allocation_weight for arm in arms)
        chi_sq = 0.0

        # Gather all levels
        all_levels = set()
        for arm_counts in counts_per_arm.values():
            all_levels.update(arm_counts.keys())

        for level in all_levels:
            level_total = sum(
                counts_per_arm.get(arm.id, {}).get(level, 0) for arm in arms
            )
            if level_total == 0:
                continue
            for arm in arms:
                expected = level_total * (arm.allocation_weight / total_weight)
                observed = counts_per_arm.get(arm.id, {}).get(level, 0)
                if expected > 0:
                    chi_sq += (observed - expected) ** 2 / expected

        return chi_sq

    # ------------------------------------------------------------------
    # Randomization list generation
    # ------------------------------------------------------------------

    def generate_randomization_list(
        self, scheme_id: str, count: int = 50
    ) -> list[dict[str, Any]]:
        """Generate a pre-computed randomization list for a scheme."""
        scheme = self._schemes.get(scheme_id)
        if not scheme:
            raise ValueError(f"Scheme {scheme_id} not found")

        rng = random.Random(scheme.seed or 42)
        result: list[dict[str, Any]] = []

        for i in range(1, count + 1):
            weights = [arm.allocation_weight for arm in scheme.arms]
            arm = rng.choices(scheme.arms, weights=weights, k=1)[0]
            result.append({
                "sequence": i,
                "arm_id": arm.id,
                "arm_name": arm.name,
                "blinding_code": self._generate_blinding_code(scheme_id, i),
            })

        return result

    # ------------------------------------------------------------------
    # Audit trail
    # ------------------------------------------------------------------

    def get_audit_trail(
        self,
        scheme_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[RandomizationAuditEntry], int]:
        """Get audit trail entries with optional filters."""
        items = list(self._audit_trail)
        if scheme_id:
            items = [e for e in items if e.scheme_id == scheme_id]
        if action:
            items = [e for e in items if e.action == action]
        total = len(items)
        items.sort(key=lambda e: e.timestamp, reverse=True)
        return items[offset : offset + limit], total

    def _record_audit(
        self, scheme_id: str, action: str, actor: str, details: dict[str, Any]
    ) -> None:
        """Record an audit trail entry (must be called within _lock)."""
        entry = RandomizationAuditEntry(
            id=f"AUDIT-{uuid4().hex[:8].upper()}",
            scheme_id=scheme_id,
            action=action,
            actor=actor,
            timestamp=datetime.now(timezone.utc),
            details=details,
        )
        self._audit_trail.append(entry)

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> RandomizationMetrics:
        """Compute aggregated randomization metrics."""
        with self._lock:
            schemes = list(self._schemes.values())
            assignments = list(self._assignments.values())
            requests = list(self._unblinding_requests.values())

            active = [s for s in schemes if s.status == RandomizationStatus.ACTIVE]

            schemes_by_method: dict[str, int] = Counter(
                s.method.value for s in schemes
            )
            schemes_by_blinding: dict[str, int] = Counter(
                s.blinding_level.value for s in schemes
            )
            schemes_by_status: dict[str, int] = Counter(
                s.status.value for s in schemes
            )

            randomizations_by_scheme: dict[str, int] = Counter(
                a.scheme_id for a in assignments
            )

            total_unblinded = sum(1 for a in assignments if a.is_unblinded)
            pending_requests = sum(1 for r in requests if r.approved is None)

            # Average imbalance across active schemes
            imbalance_scores: list[float] = []
            for scheme in active:
                report = self.check_balance(scheme.id)
                if report:
                    imbalance_scores.append(report.overall_imbalance)

            avg_imbalance = (
                sum(imbalance_scores) / len(imbalance_scores) if imbalance_scores else 0.0
            )

            return RandomizationMetrics(
                total_schemes=len(schemes),
                active_schemes=len(active),
                total_randomized=len(assignments),
                total_unblinded=total_unblinded,
                pending_unblinding_requests=pending_requests,
                schemes_by_method=dict(schemes_by_method),
                schemes_by_blinding=dict(schemes_by_blinding),
                schemes_by_status=dict(schemes_by_status),
                average_imbalance_score=round(avg_imbalance, 4),
                randomizations_by_scheme=dict(randomizations_by_scheme),
            )

    # ------------------------------------------------------------------
    # Stats (for prewarm)
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Return service statistics."""
        return {
            "total_schemes": len(self._schemes),
            "total_assignments": len(self._assignments),
            "total_unblinding_requests": len(self._unblinding_requests),
            "audit_entries": len(self._audit_trail),
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: RandomizationService | None = None
_instance_lock = threading.Lock()


def get_randomization_service() -> RandomizationService:
    """Get or create the singleton randomization service."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = RandomizationService()
    return _instance


def reset_randomization_service() -> RandomizationService:
    """Reset the singleton with fresh seed data. Used by tests."""
    global _instance
    with _instance_lock:
        _instance = RandomizationService()
    return _instance
