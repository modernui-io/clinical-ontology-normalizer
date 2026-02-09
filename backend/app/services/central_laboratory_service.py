"""Central Laboratory Management Service (CLINICAL-8).

Manages lab test definitions, kit inventory, sample lifecycle, result
reporting with auto-flagging, critical value alerting, turnaround time
tracking, and sample shipment logistics for clinical trials.

Usage:
    from app.services.central_laboratory_service import (
        get_central_lab_service,
    )

    svc = get_central_lab_service()
    sample = svc.register_sample(request)
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import random
import statistics
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4

from app.schemas.central_laboratory import (
    AlertAcknowledgeRequest,
    CriticalValueAlert,
    KitAssignRequest,
    KitStatus,
    LabKit,
    LabMetrics,
    LabResult,
    LabTest,
    LabTestCategory,
    LabTestCreate,
    LabTestUpdate,
    ResultBatchSubmitRequest,
    ResultFlag,
    ResultStatus,
    ResultSubmitRequest,
    Sample,
    SampleReceiveRequest,
    SampleRejectRequest,
    SampleRegisterRequest,
    SampleShipment,
    SampleStatus,
    SampleType,
    ShipmentCreateRequest,
    TurnaroundTimeAnalysis,
)

logger = logging.getLogger(__name__)


class CentralLabService:
    """In-memory central laboratory management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._tests: dict[str, LabTest] = {}
        self._kits: dict[str, LabKit] = {}
        self._samples: dict[str, Sample] = {}
        self._results: dict[str, LabResult] = {}
        self._alerts: dict[str, CriticalValueAlert] = {}
        self._shipments: dict[str, SampleShipment] = {}
        self._lock = threading.RLock()
        self._rng = random.Random(42)
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data seeding
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate lab data for clinical trial demo."""
        self._seed_lab_tests()
        self._seed_lab_kits()
        self._seed_samples()
        self._seed_results()
        self._seed_critical_alerts()
        self._seed_shipments()

    def _seed_lab_tests(self) -> None:
        """Create 20 lab test definitions with realistic reference ranges."""
        tests = [
            LabTest(
                id="LT-001", name="HbA1c", category=LabTestCategory.CHEMISTRY,
                loinc_code="4548-4", specimen_type=SampleType.BLOOD_WHOLE,
                reference_range_low=4.0, reference_range_high=5.6,
                unit="%", critical_low=3.0, critical_high=15.0,
                turnaround_hours=24,
            ),
            LabTest(
                id="LT-002", name="Fasting Glucose", category=LabTestCategory.CHEMISTRY,
                loinc_code="1558-6", specimen_type=SampleType.BLOOD_SERUM,
                reference_range_low=70.0, reference_range_high=100.0,
                unit="mg/dL", critical_low=40.0, critical_high=500.0,
                turnaround_hours=6,
            ),
            LabTest(
                id="LT-003", name="VEGF-A", category=LabTestCategory.BIOMARKER,
                loinc_code="56740-8", specimen_type=SampleType.BLOOD_SERUM,
                reference_range_low=31.0, reference_range_high=86.0,
                unit="pg/mL", critical_low=None, critical_high=500.0,
                turnaround_hours=48,
            ),
            LabTest(
                id="LT-004", name="IL-4", category=LabTestCategory.IMMUNOLOGY,
                loinc_code="33445-3", specimen_type=SampleType.BLOOD_SERUM,
                reference_range_low=0.0, reference_range_high=7.1,
                unit="pg/mL", critical_low=None, critical_high=None,
                turnaround_hours=72,
            ),
            LabTest(
                id="LT-005", name="IL-13", category=LabTestCategory.IMMUNOLOGY,
                loinc_code="33446-1", specimen_type=SampleType.BLOOD_SERUM,
                reference_range_low=0.0, reference_range_high=4.5,
                unit="pg/mL", critical_low=None, critical_high=None,
                turnaround_hours=72,
            ),
            LabTest(
                id="LT-006", name="PD-L1 (CPS)", category=LabTestCategory.BIOMARKER,
                loinc_code="85147-7", specimen_type=SampleType.TISSUE,
                reference_range_low=None, reference_range_high=None,
                unit="score", critical_low=None, critical_high=None,
                turnaround_hours=120,
            ),
            LabTest(
                id="LT-007", name="Tumor Mutational Burden", category=LabTestCategory.BIOMARKER,
                loinc_code="94076-7", specimen_type=SampleType.TISSUE,
                reference_range_low=None, reference_range_high=10.0,
                unit="mut/Mb", critical_low=None, critical_high=None,
                turnaround_hours=168,
            ),
            LabTest(
                id="LT-008", name="CBC with Differential", category=LabTestCategory.HEMATOLOGY,
                loinc_code="57021-8", specimen_type=SampleType.BLOOD_WHOLE,
                reference_range_low=4.5, reference_range_high=11.0,
                unit="x10^3/uL", critical_low=2.0, critical_high=30.0,
                turnaround_hours=4,
            ),
            LabTest(
                id="LT-009", name="Comprehensive Metabolic Panel", category=LabTestCategory.CHEMISTRY,
                loinc_code="24323-8", specimen_type=SampleType.BLOOD_SERUM,
                reference_range_low=None, reference_range_high=None,
                unit="panel", critical_low=None, critical_high=None,
                turnaround_hours=6,
            ),
            LabTest(
                id="LT-010", name="Lipid Panel", category=LabTestCategory.CHEMISTRY,
                loinc_code="24331-1", specimen_type=SampleType.BLOOD_SERUM,
                reference_range_low=None, reference_range_high=200.0,
                unit="mg/dL", critical_low=None, critical_high=500.0,
                turnaround_hours=6,
            ),
            LabTest(
                id="LT-011", name="Creatinine", category=LabTestCategory.CHEMISTRY,
                loinc_code="2160-0", specimen_type=SampleType.BLOOD_SERUM,
                reference_range_low=0.6, reference_range_high=1.2,
                unit="mg/dL", critical_low=0.3, critical_high=10.0,
                turnaround_hours=6,
            ),
            LabTest(
                id="LT-012", name="ALT", category=LabTestCategory.CHEMISTRY,
                loinc_code="1742-6", specimen_type=SampleType.BLOOD_SERUM,
                reference_range_low=7.0, reference_range_high=56.0,
                unit="U/L", critical_low=None, critical_high=1000.0,
                turnaround_hours=6,
            ),
            LabTest(
                id="LT-013", name="AST", category=LabTestCategory.CHEMISTRY,
                loinc_code="1920-8", specimen_type=SampleType.BLOOD_SERUM,
                reference_range_low=10.0, reference_range_high=40.0,
                unit="U/L", critical_low=None, critical_high=1000.0,
                turnaround_hours=6,
            ),
            LabTest(
                id="LT-014", name="Total Bilirubin", category=LabTestCategory.CHEMISTRY,
                loinc_code="1975-2", specimen_type=SampleType.BLOOD_SERUM,
                reference_range_low=0.1, reference_range_high=1.2,
                unit="mg/dL", critical_low=None, critical_high=15.0,
                turnaround_hours=6,
            ),
            LabTest(
                id="LT-015", name="PT/INR", category=LabTestCategory.COAGULATION,
                loinc_code="6301-6", specimen_type=SampleType.BLOOD_PLASMA,
                reference_range_low=0.8, reference_range_high=1.2,
                unit="INR", critical_low=None, critical_high=5.0,
                turnaround_hours=4,
            ),
            LabTest(
                id="LT-016", name="Urinalysis", category=LabTestCategory.URINALYSIS,
                loinc_code="24357-6", specimen_type=SampleType.URINE,
                reference_range_low=None, reference_range_high=None,
                unit="panel", critical_low=None, critical_high=None,
                turnaround_hours=4,
            ),
            LabTest(
                id="LT-017", name="C-Reactive Protein", category=LabTestCategory.CHEMISTRY,
                loinc_code="1988-5", specimen_type=SampleType.BLOOD_SERUM,
                reference_range_low=0.0, reference_range_high=3.0,
                unit="mg/L", critical_low=None, critical_high=200.0,
                turnaround_hours=6,
            ),
            LabTest(
                id="LT-018", name="ESR", category=LabTestCategory.HEMATOLOGY,
                loinc_code="4537-7", specimen_type=SampleType.BLOOD_WHOLE,
                reference_range_low=0.0, reference_range_high=20.0,
                unit="mm/hr", critical_low=None, critical_high=100.0,
                turnaround_hours=4,
            ),
            LabTest(
                id="LT-019", name="Anti-Drug Antibodies", category=LabTestCategory.PHARMACOKINETIC,
                loinc_code="56478-5", specimen_type=SampleType.BLOOD_SERUM,
                reference_range_low=None, reference_range_high=None,
                unit="titer", critical_low=None, critical_high=None,
                turnaround_hours=120,
            ),
            LabTest(
                id="LT-020", name="Serum Albumin", category=LabTestCategory.CHEMISTRY,
                loinc_code="1751-7", specimen_type=SampleType.BLOOD_SERUM,
                reference_range_low=3.5, reference_range_high=5.5,
                unit="g/dL", critical_low=1.5, critical_high=None,
                turnaround_hours=6,
            ),
        ]
        for t in tests:
            self._tests[t.id] = t

    def _seed_lab_kits(self) -> None:
        """Create 30 lab kits across 8 sites."""
        now = datetime.now(timezone.utc)
        site_ids = [f"SITE-{i:03d}" for i in range(1, 9)]
        test_groups = [
            ["LT-001", "LT-002", "LT-008", "LT-009"],  # general panel
            ["LT-003", "LT-004", "LT-005"],  # biomarker/immunology
            ["LT-011", "LT-012", "LT-013", "LT-014"],  # liver/kidney
            ["LT-015", "LT-017", "LT-018"],  # coag/inflammatory
            ["LT-006", "LT-007"],  # oncology biomarkers
        ]
        statuses = [KitStatus.AVAILABLE] * 18 + [KitStatus.ASSIGNED] * 8 + [KitStatus.USED] * 3 + [KitStatus.EXPIRED]

        for i in range(30):
            kit_id = f"KIT-{i+1:04d}"
            site = site_ids[i % len(site_ids)] if statuses[i] != KitStatus.AVAILABLE else None
            assigned = (now - timedelta(days=self._rng.randint(1, 60))) if site else None
            expiry_days = self._rng.randint(30, 365)
            if statuses[i] == KitStatus.EXPIRED:
                expiry = now - timedelta(days=5)
            else:
                expiry = now + timedelta(days=expiry_days)

            kit = LabKit(
                id=kit_id,
                kit_number=f"KN-{2024}{i+1:04d}",
                test_ids=test_groups[i % len(test_groups)],
                site_id=site,
                status=statuses[i],
                assigned_date=assigned,
                expiry_date=expiry,
                lot_number=f"LOT-{2024}-{(i // 5) + 1:02d}",
            )
            self._kits[kit.id] = kit

    def _seed_samples(self) -> None:
        """Create 50 samples with various statuses."""
        site_ids = [f"SITE-{i:03d}" for i in range(1, 9)]
        patient_ids = [f"PAT-{i:04d}" for i in range(1, 26)]
        sample_types = list(SampleType)
        status_dist = (
            [SampleStatus.COLLECTED] * 8
            + [SampleStatus.IN_TRANSIT] * 6
            + [SampleStatus.RECEIVED] * 10
            + [SampleStatus.PROCESSING] * 5
            + [SampleStatus.RESULTED] * 16
            + [SampleStatus.REJECTED] * 3
            + [SampleStatus.REDRAWN] * 2
        )

        now = datetime.now(timezone.utc)
        for i in range(50):
            status = status_dist[i]
            collection_offset = self._rng.randint(1, 90)
            collection_date = (now - timedelta(days=collection_offset)).strftime("%Y-%m-%d")
            collection_time = f"{self._rng.randint(6, 18):02d}:{self._rng.choice(['00', '15', '30', '45'])}"
            received_date = None
            if status in (SampleStatus.RECEIVED, SampleStatus.PROCESSING, SampleStatus.RESULTED, SampleStatus.REJECTED):
                received_date = (now - timedelta(days=collection_offset - self._rng.randint(1, 3))).strftime("%Y-%m-%d")

            rejection_reason = None
            if status == SampleStatus.REJECTED:
                rejection_reason = self._rng.choice([
                    "Hemolyzed specimen",
                    "Insufficient volume",
                    "Clotted specimen",
                    "Incorrect container",
                    "Temperature excursion",
                ])

            sample = Sample(
                id=f"SMP-{i+1:05d}",
                patient_id=patient_ids[i % len(patient_ids)],
                site_id=site_ids[i % len(site_ids)],
                sample_type=sample_types[i % len(sample_types)],
                collection_date=collection_date,
                collection_time=collection_time,
                collector_initials=self._rng.choice(["JM", "KL", "RB", "AS", "DW", "TP"]),
                kit_id=f"KIT-{(i % 30) + 1:04d}",
                barcode=f"BC-{uuid4().hex[:12].upper()}",
                status=status,
                received_date=received_date,
                rejection_reason=rejection_reason,
            )
            self._samples[sample.id] = sample

    def _seed_results(self) -> None:
        """Create 80 lab results with realistic values."""
        # Map test IDs to value generators
        value_generators: dict[str, tuple[float, float]] = {
            "LT-001": (4.0, 12.0),     # HbA1c
            "LT-002": (55.0, 350.0),    # Fasting Glucose
            "LT-003": (20.0, 200.0),    # VEGF-A
            "LT-004": (0.5, 15.0),      # IL-4
            "LT-005": (0.3, 10.0),      # IL-13
            "LT-008": (2.5, 18.0),      # CBC WBC
            "LT-011": (0.4, 5.0),       # Creatinine
            "LT-012": (5.0, 300.0),     # ALT
            "LT-013": (8.0, 200.0),     # AST
            "LT-014": (0.1, 8.0),       # Bilirubin
            "LT-015": (0.7, 4.0),       # PT/INR
            "LT-017": (0.1, 100.0),     # CRP
            "LT-018": (1.0, 60.0),      # ESR
            "LT-020": (2.0, 5.8),       # Albumin
        }
        test_ids = list(value_generators.keys())

        # Only use resulted samples
        resulted_samples = [s for s in self._samples.values() if s.status == SampleStatus.RESULTED]
        now = datetime.now(timezone.utc)

        result_idx = 0
        for sample in resulted_samples:
            # Each resulted sample gets 3-6 results
            n_results = self._rng.randint(3, 6)
            chosen_tests = self._rng.sample(test_ids, min(n_results, len(test_ids)))
            for test_id in chosen_tests:
                low, high = value_generators[test_id]
                value = round(self._rng.uniform(low, high), 2)
                test = self._tests[test_id]

                flag = self._evaluate_flag(value, test)
                offset = self._rng.randint(1, 30)
                resulted_date = (now - timedelta(days=offset)).strftime("%Y-%m-%d")

                result = LabResult(
                    id=f"RES-{result_idx+1:05d}",
                    sample_id=sample.id,
                    test_id=test_id,
                    value=value,
                    unit=test.unit,
                    reference_range=self._format_reference_range(test),
                    flag=flag,
                    resulted_date=resulted_date,
                    reviewed_by=self._rng.choice(["Dr. Smith", "Dr. Johnson", "Dr. Lee", "Dr. Patel"]),
                    status=ResultStatus.FINAL,
                )
                self._results[result.id] = result
                result_idx += 1
                if result_idx >= 80:
                    return

    def _seed_critical_alerts(self) -> None:
        """Create 5 critical value alerts from existing results."""
        critical_results = [
            r for r in self._results.values()
            if r.flag in (ResultFlag.CRITICAL_LOW, ResultFlag.CRITICAL_HIGH, ResultFlag.PANIC)
        ]

        if len(critical_results) < 5:
            # Force-create some critical results
            test = self._tests["LT-002"]  # Fasting Glucose
            resulted_samples = [s for s in self._samples.values() if s.status == SampleStatus.RESULTED]
            for i in range(5 - len(critical_results)):
                if i < len(resulted_samples):
                    sample = resulted_samples[i]
                    val = self._rng.choice([35.0, 38.0, 520.0, 550.0, 600.0])
                    result = LabResult(
                        id=f"RES-CRIT-{i+1:03d}",
                        sample_id=sample.id,
                        test_id="LT-002",
                        value=val,
                        unit="mg/dL",
                        reference_range="70-100 mg/dL",
                        flag=ResultFlag.CRITICAL_LOW if val < 40 else ResultFlag.CRITICAL_HIGH,
                        resulted_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        reviewed_by="Dr. Smith",
                        status=ResultStatus.FINAL,
                    )
                    self._results[result.id] = result
                    critical_results.append(result)

        for i, result in enumerate(critical_results[:5]):
            sample = self._samples.get(result.sample_id)
            test = self._tests.get(result.test_id)
            if not sample or not test:
                continue

            threshold_desc = ""
            if result.flag == ResultFlag.CRITICAL_LOW:
                threshold_desc = f"Below critical low ({test.critical_low} {test.unit})"
            elif result.flag in (ResultFlag.CRITICAL_HIGH, ResultFlag.PANIC):
                threshold_desc = f"Above critical high ({test.critical_high} {test.unit})"

            alert = CriticalValueAlert(
                id=f"ALERT-{i+1:04d}",
                result_id=result.id,
                patient_id=sample.patient_id,
                site_id=sample.site_id,
                test_name=test.name,
                value=result.value,
                critical_threshold=threshold_desc,
                notification_sent=i < 3,  # first 3 have been notified
                acknowledged_by="Dr. Investigator" if i < 2 else None,
                acknowledged_date=datetime.now(timezone.utc).strftime("%Y-%m-%d") if i < 2 else None,
            )
            self._alerts[alert.id] = alert

    def _seed_shipments(self) -> None:
        """Create 8 sample shipments."""
        site_ids = [f"SITE-{i:03d}" for i in range(1, 9)]
        now = datetime.now(timezone.utc)
        all_sample_ids = list(self._samples.keys())

        for i in range(8):
            start = i * 5
            sample_slice = all_sample_ids[start:start + self._rng.randint(3, 7)]
            ship_offset = self._rng.randint(1, 30)
            shipped = (now - timedelta(days=ship_offset)).strftime("%Y-%m-%d")
            received = None
            condition = None
            temp_ok = None
            if i < 6:
                received = (now - timedelta(days=ship_offset - 2)).strftime("%Y-%m-%d")
                condition = self._rng.choice(["Good", "Good", "Good", "Minor condensation", "Intact"])
                temp_ok = self._rng.choice([True, True, True, True, False])

            shipment = SampleShipment(
                id=f"SHIP-{i+1:04d}",
                site_id=site_ids[i % len(site_ids)],
                tracking_number=f"1Z{self._rng.randint(100000000, 999999999)}",
                samples=sample_slice,
                shipped_date=shipped,
                received_date=received,
                condition_on_receipt=condition,
                temperature_acceptable=temp_ok,
            )
            self._shipments[shipment.id] = shipment

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    def _evaluate_flag(self, value: float, test: LabTest) -> ResultFlag:
        """Evaluate a result value against reference ranges and critical thresholds."""
        # Check critical thresholds first
        if test.critical_low is not None and value < test.critical_low:
            return ResultFlag.CRITICAL_LOW
        if test.critical_high is not None and value > test.critical_high:
            return ResultFlag.CRITICAL_HIGH

        # Check reference ranges
        if test.reference_range_low is not None and value < test.reference_range_low:
            return ResultFlag.LOW
        if test.reference_range_high is not None and value > test.reference_range_high:
            return ResultFlag.HIGH

        return ResultFlag.NORMAL

    def _format_reference_range(self, test: LabTest) -> str:
        """Format the reference range as a display string."""
        if test.reference_range_low is not None and test.reference_range_high is not None:
            return f"{test.reference_range_low}-{test.reference_range_high} {test.unit}"
        elif test.reference_range_high is not None:
            return f"<{test.reference_range_high} {test.unit}"
        elif test.reference_range_low is not None:
            return f">{test.reference_range_low} {test.unit}"
        return "N/A"

    def _generate_id(self, prefix: str) -> str:
        """Generate a unique ID with prefix."""
        return f"{prefix}-{uuid4().hex[:8].upper()}"

    # ------------------------------------------------------------------
    # Lab Test CRUD
    # ------------------------------------------------------------------

    def list_tests(
        self,
        category: Optional[LabTestCategory] = None,
        specimen_type: Optional[SampleType] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[LabTest], int]:
        """List lab tests with optional filtering."""
        with self._lock:
            items = list(self._tests.values())
            if category:
                items = [t for t in items if t.category == category]
            if specimen_type:
                items = [t for t in items if t.specimen_type == specimen_type]
            total = len(items)
            return items[offset:offset + limit], total

    def get_test(self, test_id: str) -> Optional[LabTest]:
        """Get a single lab test by ID."""
        with self._lock:
            return self._tests.get(test_id)

    def create_test(self, req: LabTestCreate) -> LabTest:
        """Create a new lab test definition."""
        with self._lock:
            test_id = self._generate_id("LT")
            test = LabTest(
                id=test_id,
                name=req.name,
                category=req.category,
                loinc_code=req.loinc_code,
                specimen_type=req.specimen_type,
                reference_range_low=req.reference_range_low,
                reference_range_high=req.reference_range_high,
                unit=req.unit,
                critical_low=req.critical_low,
                critical_high=req.critical_high,
                turnaround_hours=req.turnaround_hours,
            )
            self._tests[test.id] = test
            return test

    def update_test(self, test_id: str, req: LabTestUpdate) -> Optional[LabTest]:
        """Update a lab test definition."""
        with self._lock:
            test = self._tests.get(test_id)
            if not test:
                return None
            updates = req.model_dump(exclude_unset=True)
            updated = test.model_copy(update=updates)
            self._tests[test_id] = updated
            return updated

    def delete_test(self, test_id: str) -> bool:
        """Delete a lab test definition."""
        with self._lock:
            if test_id in self._tests:
                del self._tests[test_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Kit Management
    # ------------------------------------------------------------------

    def list_kits(
        self,
        site_id: Optional[str] = None,
        status: Optional[KitStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[LabKit], int]:
        """List lab kits with optional filtering."""
        with self._lock:
            items = list(self._kits.values())
            if site_id:
                items = [k for k in items if k.site_id == site_id]
            if status:
                items = [k for k in items if k.status == status]
            total = len(items)
            return items[offset:offset + limit], total

    def get_kit(self, kit_id: str) -> Optional[LabKit]:
        """Get a single kit by ID."""
        with self._lock:
            return self._kits.get(kit_id)

    def assign_kits(self, req: KitAssignRequest) -> list[LabKit]:
        """Assign kits to a site."""
        with self._lock:
            assigned = []
            now = datetime.now(timezone.utc)
            for kit_id in req.kit_ids:
                kit = self._kits.get(kit_id)
                if kit and kit.status == KitStatus.AVAILABLE:
                    updated = kit.model_copy(update={
                        "site_id": req.site_id,
                        "status": KitStatus.ASSIGNED,
                        "assigned_date": now,
                    })
                    self._kits[kit_id] = updated
                    assigned.append(updated)
            return assigned

    def get_kit_inventory_summary(self) -> dict[str, Any]:
        """Get summary of kit inventory by status and site."""
        with self._lock:
            by_status: dict[str, int] = {}
            by_site: dict[str, int] = {}
            now = datetime.now(timezone.utc)
            expiring_30d = 0
            for kit in self._kits.values():
                by_status[kit.status.value] = by_status.get(kit.status.value, 0) + 1
                if kit.site_id:
                    by_site[kit.site_id] = by_site.get(kit.site_id, 0) + 1
                if kit.expiry_date and kit.expiry_date <= now + timedelta(days=30):
                    expiring_30d += 1
            return {
                "total_kits": len(self._kits),
                "by_status": by_status,
                "by_site": by_site,
                "expiring_30d": expiring_30d,
            }

    # ------------------------------------------------------------------
    # Sample Management
    # ------------------------------------------------------------------

    def list_samples(
        self,
        site_id: Optional[str] = None,
        patient_id: Optional[str] = None,
        status: Optional[SampleStatus] = None,
        sample_type: Optional[SampleType] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Sample], int]:
        """List samples with optional filtering."""
        with self._lock:
            items = list(self._samples.values())
            if site_id:
                items = [s for s in items if s.site_id == site_id]
            if patient_id:
                items = [s for s in items if s.patient_id == patient_id]
            if status:
                items = [s for s in items if s.status == status]
            if sample_type:
                items = [s for s in items if s.sample_type == sample_type]
            total = len(items)
            return items[offset:offset + limit], total

    def get_sample(self, sample_id: str) -> Optional[Sample]:
        """Get a single sample by ID."""
        with self._lock:
            return self._samples.get(sample_id)

    def get_sample_with_results(self, sample_id: str) -> Optional[tuple[Sample, list[LabResult]]]:
        """Get a sample with its associated results."""
        with self._lock:
            sample = self._samples.get(sample_id)
            if not sample:
                return None
            results = [r for r in self._results.values() if r.sample_id == sample_id]
            return sample, results

    def register_sample(self, req: SampleRegisterRequest) -> Sample:
        """Register a new sample collection."""
        with self._lock:
            sample_id = self._generate_id("SMP")
            barcode = f"BC-{uuid4().hex[:12].upper()}"

            # Mark kit as used if provided
            if req.kit_id and req.kit_id in self._kits:
                kit = self._kits[req.kit_id]
                if kit.status in (KitStatus.AVAILABLE, KitStatus.ASSIGNED):
                    self._kits[req.kit_id] = kit.model_copy(update={"status": KitStatus.USED})

            sample = Sample(
                id=sample_id,
                patient_id=req.patient_id,
                site_id=req.site_id,
                sample_type=req.sample_type,
                collection_date=req.collection_date,
                collection_time=req.collection_time,
                collector_initials=req.collector_initials,
                kit_id=req.kit_id,
                barcode=barcode,
                status=SampleStatus.COLLECTED,
            )
            self._samples[sample.id] = sample
            return sample

    def receive_sample(self, sample_id: str, req: SampleReceiveRequest) -> Optional[Sample]:
        """Mark a sample as received at the central lab."""
        with self._lock:
            sample = self._samples.get(sample_id)
            if not sample:
                return None
            if sample.status not in (SampleStatus.COLLECTED, SampleStatus.IN_TRANSIT):
                return None
            updated = sample.model_copy(update={
                "status": SampleStatus.RECEIVED,
                "received_date": req.received_date,
            })
            self._samples[sample_id] = updated
            return updated

    def reject_sample(self, sample_id: str, req: SampleRejectRequest) -> Optional[Sample]:
        """Reject a sample with a reason."""
        with self._lock:
            sample = self._samples.get(sample_id)
            if not sample:
                return None
            if sample.status == SampleStatus.REJECTED:
                return None
            updated = sample.model_copy(update={
                "status": SampleStatus.REJECTED,
                "rejection_reason": req.reason,
            })
            self._samples[sample_id] = updated
            return updated

    # ------------------------------------------------------------------
    # Result Management
    # ------------------------------------------------------------------

    def list_results(
        self,
        sample_id: Optional[str] = None,
        test_id: Optional[str] = None,
        status: Optional[ResultStatus] = None,
        flag: Optional[ResultFlag] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[LabResult], int]:
        """List results with optional filtering."""
        with self._lock:
            items = list(self._results.values())
            if sample_id:
                items = [r for r in items if r.sample_id == sample_id]
            if test_id:
                items = [r for r in items if r.test_id == test_id]
            if status:
                items = [r for r in items if r.status == status]
            if flag:
                items = [r for r in items if r.flag == flag]
            total = len(items)
            return items[offset:offset + limit], total

    def get_result(self, result_id: str) -> Optional[LabResult]:
        """Get a single result by ID."""
        with self._lock:
            return self._results.get(result_id)

    def submit_results(self, req: ResultBatchSubmitRequest) -> list[LabResult]:
        """Submit a batch of lab results with auto-flagging."""
        with self._lock:
            submitted = []
            for r in req.results:
                result_id = self._generate_id("RES")
                test = self._tests.get(r.test_id)

                # Auto-flag based on reference ranges
                flag = ResultFlag.NORMAL
                ref_range = "N/A"
                if test and r.value is not None:
                    flag = self._evaluate_flag(r.value, test)
                    ref_range = self._format_reference_range(test)

                result = LabResult(
                    id=result_id,
                    sample_id=r.sample_id,
                    test_id=r.test_id,
                    value=r.value,
                    unit=r.unit or (test.unit if test else ""),
                    reference_range=ref_range,
                    flag=flag,
                    resulted_date=r.resulted_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    reviewed_by=r.reviewed_by,
                    status=r.status,
                )
                self._results[result.id] = result
                submitted.append(result)

                # Update sample status to resulted
                sample = self._samples.get(r.sample_id)
                if sample and sample.status in (SampleStatus.RECEIVED, SampleStatus.PROCESSING):
                    self._samples[r.sample_id] = sample.model_copy(
                        update={"status": SampleStatus.RESULTED}
                    )

                # Create critical value alert if needed
                if flag in (ResultFlag.CRITICAL_LOW, ResultFlag.CRITICAL_HIGH, ResultFlag.PANIC):
                    self._create_critical_alert(result, test, sample)

            return submitted

    def _create_critical_alert(
        self,
        result: LabResult,
        test: Optional[LabTest],
        sample: Optional[Sample],
    ) -> None:
        """Create a critical value alert for a result."""
        if not test or not sample or result.value is None:
            return

        threshold_desc = ""
        if result.flag == ResultFlag.CRITICAL_LOW and test.critical_low is not None:
            threshold_desc = f"Below critical low ({test.critical_low} {test.unit})"
        elif result.flag in (ResultFlag.CRITICAL_HIGH, ResultFlag.PANIC) and test.critical_high is not None:
            threshold_desc = f"Above critical high ({test.critical_high} {test.unit})"

        alert = CriticalValueAlert(
            id=self._generate_id("ALERT"),
            result_id=result.id,
            patient_id=sample.patient_id,
            site_id=sample.site_id,
            test_name=test.name,
            value=result.value,
            critical_threshold=threshold_desc,
            notification_sent=True,  # Auto-send notification
        )
        self._alerts[alert.id] = alert

    def get_patient_results(
        self,
        patient_id: str,
        test_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[LabResult], int]:
        """Get all results for a patient."""
        with self._lock:
            patient_samples = {
                s.id for s in self._samples.values() if s.patient_id == patient_id
            }
            items = [r for r in self._results.values() if r.sample_id in patient_samples]
            if test_id:
                items = [r for r in items if r.test_id == test_id]
            total = len(items)
            return items[offset:offset + limit], total

    def get_critical_results(
        self,
        acknowledged: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[CriticalValueAlert], int]:
        """Get critical value alerts."""
        with self._lock:
            items = list(self._alerts.values())
            if acknowledged is True:
                items = [a for a in items if a.acknowledged_by is not None]
            elif acknowledged is False:
                items = [a for a in items if a.acknowledged_by is None]
            total = len(items)
            return items[offset:offset + limit], total

    def acknowledge_alert(
        self, alert_id: str, req: AlertAcknowledgeRequest
    ) -> Optional[CriticalValueAlert]:
        """Acknowledge a critical value alert."""
        with self._lock:
            alert = self._alerts.get(alert_id)
            if not alert:
                return None
            if alert.acknowledged_by:
                return alert  # Already acknowledged
            updated = alert.model_copy(update={
                "acknowledged_by": req.acknowledged_by,
                "acknowledged_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            })
            self._alerts[alert_id] = updated
            return updated

    # ------------------------------------------------------------------
    # Shipment Management
    # ------------------------------------------------------------------

    def list_shipments(
        self,
        site_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[SampleShipment], int]:
        """List sample shipments."""
        with self._lock:
            items = list(self._shipments.values())
            if site_id:
                items = [s for s in items if s.site_id == site_id]
            total = len(items)
            return items[offset:offset + limit], total

    def get_shipment(self, shipment_id: str) -> Optional[SampleShipment]:
        """Get a single shipment by ID."""
        with self._lock:
            return self._shipments.get(shipment_id)

    def create_shipment(self, req: ShipmentCreateRequest) -> SampleShipment:
        """Create a new sample shipment and update sample statuses."""
        with self._lock:
            shipment_id = self._generate_id("SHIP")

            # Update sample statuses to in_transit
            for sid in req.sample_ids:
                sample = self._samples.get(sid)
                if sample and sample.status == SampleStatus.COLLECTED:
                    self._samples[sid] = sample.model_copy(
                        update={"status": SampleStatus.IN_TRANSIT}
                    )

            shipment = SampleShipment(
                id=shipment_id,
                site_id=req.site_id,
                tracking_number=req.tracking_number,
                samples=req.sample_ids,
                shipped_date=req.shipped_date,
            )
            self._shipments[shipment.id] = shipment
            return shipment

    # ------------------------------------------------------------------
    # Metrics & Analytics
    # ------------------------------------------------------------------

    def get_metrics(self) -> LabMetrics:
        """Calculate aggregated lab metrics."""
        with self._lock:
            total_samples = len(self._samples)
            samples_by_status: dict[str, int] = {}
            for s in self._samples.values():
                samples_by_status[s.status.value] = samples_by_status.get(s.status.value, 0) + 1

            # Rejection rate
            rejected = samples_by_status.get(SampleStatus.REJECTED.value, 0)
            rejection_rate = rejected / total_samples if total_samples > 0 else 0.0

            # Pending results
            pending = sum(1 for r in self._results.values() if r.status == ResultStatus.PENDING)

            # Critical values in last 30 days
            critical_30d = len(self._alerts)

            # Average turnaround hours (simulated)
            tat_values = []
            for r in self._results.values():
                if r.status == ResultStatus.FINAL and r.sample_id in self._samples:
                    # Simulate TAT based on test definition
                    test = self._tests.get(r.test_id)
                    if test:
                        tat_values.append(float(test.turnaround_hours) * self._rng.uniform(0.5, 1.5))
            avg_tat = statistics.mean(tat_values) if tat_values else 0.0

            # Kits expiring in 30 days
            now = datetime.now(timezone.utc)
            kits_expiring = sum(
                1 for k in self._kits.values()
                if k.expiry_date and k.expiry_date <= now + timedelta(days=30)
                and k.status not in (KitStatus.USED, KitStatus.EXPIRED)
            )

            return LabMetrics(
                total_samples=total_samples,
                samples_by_status=samples_by_status,
                avg_turnaround_hours=round(avg_tat, 1),
                critical_values_30d=critical_30d,
                rejection_rate=round(rejection_rate, 4),
                pending_results=pending,
                kits_expiring_30d=kits_expiring,
            )

    def get_turnaround_analysis(self) -> list[TurnaroundTimeAnalysis]:
        """Analyze turnaround times by test category."""
        with self._lock:
            category_tats: dict[str, list[float]] = {}
            category_targets: dict[str, int] = {}

            for r in self._results.values():
                if r.status != ResultStatus.FINAL:
                    continue
                test = self._tests.get(r.test_id)
                if not test:
                    continue
                cat = test.category.value
                if cat not in category_tats:
                    category_tats[cat] = []
                    category_targets[cat] = test.turnaround_hours
                # Simulated TAT
                simulated_tat = float(test.turnaround_hours) * self._rng.uniform(0.5, 1.5)
                category_tats[cat].append(simulated_tat)

            analyses = []
            for cat, tats in category_tats.items():
                if not tats:
                    continue
                sorted_tats = sorted(tats)
                target = category_targets.get(cat, 24)
                within = sum(1 for t in tats if t <= target)
                p95_idx = int(len(sorted_tats) * 0.95)

                analyses.append(TurnaroundTimeAnalysis(
                    category=cat,
                    avg_hours=round(statistics.mean(tats), 1),
                    median_hours=round(statistics.median(tats), 1),
                    p95_hours=round(sorted_tats[min(p95_idx, len(sorted_tats) - 1)], 1),
                    total_resulted=len(tats),
                    within_target=within,
                    target_hours=target,
                ))

            return analyses

    def get_rejection_analysis(self) -> dict[str, Any]:
        """Analyze sample rejections by site and reason."""
        with self._lock:
            by_site: dict[str, int] = {}
            by_reason: dict[str, int] = {}
            total_rejected = 0

            for s in self._samples.values():
                if s.status == SampleStatus.REJECTED:
                    total_rejected += 1
                    by_site[s.site_id] = by_site.get(s.site_id, 0) + 1
                    reason = s.rejection_reason or "Unknown"
                    by_reason[reason] = by_reason.get(reason, 0) + 1

            return {
                "total_rejected": total_rejected,
                "total_samples": len(self._samples),
                "rejection_rate": round(total_rejected / len(self._samples), 4) if self._samples else 0.0,
                "by_site": by_site,
                "by_reason": by_reason,
            }

    def get_query_suggestions(self) -> list[dict[str, str]]:
        """Generate auto-query suggestions for missing/inconsistent results."""
        with self._lock:
            queries = []

            # Find samples without results
            resulted_sample_ids = {r.sample_id for r in self._results.values()}
            for s in self._samples.values():
                if s.status in (SampleStatus.RECEIVED, SampleStatus.PROCESSING):
                    if s.id not in resulted_sample_ids:
                        queries.append({
                            "type": "missing_result",
                            "sample_id": s.id,
                            "patient_id": s.patient_id,
                            "site_id": s.site_id,
                            "message": f"Sample {s.id} received but no results recorded",
                        })

            # Find overdue results based on TAT
            # (simplified: flag any processing sample older than 7 days)
            for s in self._samples.values():
                if s.status == SampleStatus.PROCESSING and s.received_date:
                    queries.append({
                        "type": "overdue",
                        "sample_id": s.id,
                        "patient_id": s.patient_id,
                        "site_id": s.site_id,
                        "message": f"Sample {s.id} still processing, may be overdue",
                    })

            return queries

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics for health checks."""
        with self._lock:
            return {
                "lab_tests": len(self._tests),
                "lab_kits": len(self._kits),
                "samples": len(self._samples),
                "results": len(self._results),
                "critical_alerts": len(self._alerts),
                "shipments": len(self._shipments),
            }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: CentralLabService | None = None
_instance_lock = threading.Lock()


def get_central_lab_service() -> CentralLabService:
    """Get or create the singleton central laboratory service."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = CentralLabService()
    return _instance


def reset_central_lab_service() -> CentralLabService:
    """Reset the singleton with fresh seed data. Used by tests."""
    global _instance
    with _instance_lock:
        _instance = CentralLabService()
    return _instance
