"""Manufacturing Operations & Batch Record Service (MFG-OPS).

Manages GMP batch records, equipment qualification, environmental monitoring,
process validation, deviation management, and batch release for clinical supply
manufacturing operations.

Usage:
    from app.services.manufacturing_ops_service import (
        get_manufacturing_ops_service,
    )

    svc = get_manufacturing_ops_service()
    batches = svc.list_batches()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.manufacturing_ops import (
    BatchRecord,
    BatchRecordCreate,
    BatchRecordUpdate,
    BatchReleaseChecklist,
    BatchReleaseRequest,
    BatchStatus,
    ChecklistItemCreate,
    ChecklistItemUpdate,
    DeviationCreate,
    DeviationStatus,
    DeviationType,
    DeviationUpdate,
    EnvironmentalMonitoring,
    EnvironmentalMonitoringCreate,
    EnvironmentalZone,
    Equipment,
    EquipmentCreate,
    EquipmentStatus,
    EquipmentUpdate,
    ManufacturingDeviation,
    ManufacturingMetrics,
    MonitoringResult,
    ProcessValidation,
    ProcessValidationCreate,
    ProcessValidationUpdate,
    ValidationStatus,
)

logger = logging.getLogger(__name__)


class ManufacturingOpsService:
    """In-memory Manufacturing Operations engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._batches: dict[str, BatchRecord] = {}
        self._equipment: dict[str, Equipment] = {}
        self._env_monitoring: dict[str, EnvironmentalMonitoring] = {}
        self._validations: dict[str, ProcessValidation] = {}
        self._deviations: dict[str, ManufacturingDeviation] = {}
        self._checklists: dict[str, BatchReleaseChecklist] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901 – seed method is intentionally long
        """Pre-populate realistic manufacturing operations data."""
        now = datetime.now(timezone.utc)

        # --- 5 Batch Records ---
        batches_data = [
            {
                "id": "BATCH-001",
                "product_name": "Dupilumab 300mg Prefilled Syringe",
                "batch_number": "DUP-2026-001",
                "lot_number": "LOT-DUP-001A",
                "manufacturing_site": "Regeneron Rensselaer Plant",
                "batch_size": 5000.0,
                "unit_of_measure": "units",
                "start_date": now - timedelta(days=45),
                "end_date": now - timedelta(days=30),
                "status": BatchStatus.RELEASED,
                "yield_actual": 4850.0,
                "yield_theoretical": 5000.0,
                "yield_pct": 97.0,
                "master_batch_record_version": "MBR-DUP-v3.2",
                "reviewed_by": "Dr. Sarah Chen",
                "released_by": "Dr. Michael Torres",
                "release_date": now - timedelta(days=25),
            },
            {
                "id": "BATCH-002",
                "product_name": "Aflibercept 2mg Intravitreal Injection",
                "batch_number": "AFL-2026-003",
                "lot_number": "LOT-AFL-003B",
                "manufacturing_site": "Regeneron Rensselaer Plant",
                "batch_size": 10000.0,
                "unit_of_measure": "vials",
                "start_date": now - timedelta(days=20),
                "end_date": now - timedelta(days=8),
                "status": BatchStatus.COMPLETED,
                "yield_actual": 9720.0,
                "yield_theoretical": 10000.0,
                "yield_pct": 97.2,
                "master_batch_record_version": "MBR-AFL-v2.8",
                "reviewed_by": "Dr. Sarah Chen",
                "released_by": None,
                "release_date": None,
            },
            {
                "id": "BATCH-003",
                "product_name": "Cemiplimab 350mg IV Solution",
                "batch_number": "CEM-2026-002",
                "lot_number": "LOT-CEM-002A",
                "manufacturing_site": "Regeneron Limerick Facility",
                "batch_size": 2000.0,
                "unit_of_measure": "vials",
                "start_date": now - timedelta(days=5),
                "end_date": None,
                "status": BatchStatus.IN_PROGRESS,
                "yield_actual": None,
                "yield_theoretical": 2000.0,
                "yield_pct": None,
                "master_batch_record_version": "MBR-CEM-v1.5",
                "reviewed_by": None,
                "released_by": None,
                "release_date": None,
            },
            {
                "id": "BATCH-004",
                "product_name": "Dupilumab 200mg Prefilled Syringe",
                "batch_number": "DUP-2026-004",
                "lot_number": "LOT-DUP-004C",
                "manufacturing_site": "Regeneron Rensselaer Plant",
                "batch_size": 8000.0,
                "unit_of_measure": "units",
                "start_date": None,
                "end_date": None,
                "status": BatchStatus.PLANNED,
                "yield_actual": None,
                "yield_theoretical": 8000.0,
                "yield_pct": None,
                "master_batch_record_version": "MBR-DUP-v3.2",
                "reviewed_by": None,
                "released_by": None,
                "release_date": None,
            },
            {
                "id": "BATCH-005",
                "product_name": "Aflibercept 8mg Intravitreal Injection",
                "batch_number": "AFL8-2026-001",
                "lot_number": "LOT-AFL8-001A",
                "manufacturing_site": "Regeneron Limerick Facility",
                "batch_size": 3000.0,
                "unit_of_measure": "vials",
                "start_date": now - timedelta(days=60),
                "end_date": now - timedelta(days=50),
                "status": BatchStatus.QUARANTINE,
                "yield_actual": 2400.0,
                "yield_theoretical": 3000.0,
                "yield_pct": 80.0,
                "master_batch_record_version": "MBR-AFL8-v1.0",
                "reviewed_by": "Dr. Karen Li",
                "released_by": None,
                "release_date": None,
            },
        ]

        for b in batches_data:
            self._batches[b["id"]] = BatchRecord(**b)

        # --- 8 Equipment Records ---
        equipment_data = [
            {
                "id": "EQ-001",
                "name": "Bioreactor BR-500",
                "equipment_type": "bioreactor",
                "serial_number": "BR500-2021-0042",
                "location": "Building A, Suite 200",
                "status": EquipmentStatus.QUALIFIED,
                "last_qualification_date": now - timedelta(days=90),
                "next_qualification_date": now + timedelta(days=275),
                "calibration_due_date": now + timedelta(days=60),
                "maintenance_schedule": "Quarterly preventive maintenance",
                "assigned_area": "Cell Culture Suite",
            },
            {
                "id": "EQ-002",
                "name": "Chromatography System AKTA-01",
                "equipment_type": "chromatography",
                "serial_number": "AKTA-2020-0187",
                "location": "Building A, Suite 210",
                "status": EquipmentStatus.QUALIFIED,
                "last_qualification_date": now - timedelta(days=60),
                "next_qualification_date": now + timedelta(days=305),
                "calibration_due_date": now + timedelta(days=90),
                "maintenance_schedule": "Semi-annual preventive maintenance",
                "assigned_area": "Purification Suite",
            },
            {
                "id": "EQ-003",
                "name": "Lyophilizer LYO-200",
                "equipment_type": "lyophilizer",
                "serial_number": "LYO200-2019-0023",
                "location": "Building B, Suite 100",
                "status": EquipmentStatus.DUE_FOR_REQUALIFICATION,
                "last_qualification_date": now - timedelta(days=380),
                "next_qualification_date": now - timedelta(days=15),
                "calibration_due_date": now - timedelta(days=10),
                "maintenance_schedule": "Annual preventive maintenance",
                "assigned_area": "Formulation Suite",
            },
            {
                "id": "EQ-004",
                "name": "Filling Line FL-100",
                "equipment_type": "filler",
                "serial_number": "FL100-2022-0056",
                "location": "Building B, Suite 110",
                "status": EquipmentStatus.QUALIFIED,
                "last_qualification_date": now - timedelta(days=120),
                "next_qualification_date": now + timedelta(days=245),
                "calibration_due_date": now + timedelta(days=45),
                "maintenance_schedule": "Monthly preventive maintenance",
                "assigned_area": "Aseptic Fill Suite",
            },
            {
                "id": "EQ-005",
                "name": "Autoclave AC-300",
                "equipment_type": "sterilizer",
                "serial_number": "AC300-2020-0089",
                "location": "Building A, Suite 220",
                "status": EquipmentStatus.UNDER_MAINTENANCE,
                "last_qualification_date": now - timedelta(days=200),
                "next_qualification_date": now + timedelta(days=165),
                "calibration_due_date": now + timedelta(days=30),
                "maintenance_schedule": "Quarterly preventive maintenance",
                "assigned_area": "Sterilization Suite",
            },
            {
                "id": "EQ-006",
                "name": "Visual Inspection System VIS-50",
                "equipment_type": "inspection",
                "serial_number": "VIS50-2023-0012",
                "location": "Building B, Suite 120",
                "status": EquipmentStatus.QUALIFIED,
                "last_qualification_date": now - timedelta(days=45),
                "next_qualification_date": now + timedelta(days=320),
                "calibration_due_date": now + timedelta(days=135),
                "maintenance_schedule": "Semi-annual preventive maintenance",
                "assigned_area": "Inspection Suite",
            },
            {
                "id": "EQ-007",
                "name": "Centrifuge CF-1000",
                "equipment_type": "centrifuge",
                "serial_number": "CF1000-2021-0034",
                "location": "Building A, Suite 205",
                "status": EquipmentStatus.OUT_OF_SERVICE,
                "last_qualification_date": now - timedelta(days=400),
                "next_qualification_date": None,
                "calibration_due_date": None,
                "maintenance_schedule": "Quarterly preventive maintenance",
                "assigned_area": "Harvest Suite",
            },
            {
                "id": "EQ-008",
                "name": "Tangential Flow Filtration TFF-200",
                "equipment_type": "filtration",
                "serial_number": "TFF200-2022-0067",
                "location": "Building A, Suite 215",
                "status": EquipmentStatus.QUALIFIED,
                "last_qualification_date": now - timedelta(days=30),
                "next_qualification_date": now + timedelta(days=335),
                "calibration_due_date": now + timedelta(days=150),
                "maintenance_schedule": "Semi-annual preventive maintenance",
                "assigned_area": "Purification Suite",
            },
        ]

        for e in equipment_data:
            self._equipment[e["id"]] = Equipment(**e)

        # --- 12 Environmental Monitoring Records ---
        env_data = [
            {
                "id": "ENV-001",
                "zone": EnvironmentalZone.GRADE_A,
                "room_name": "Aseptic Fill Room A-101",
                "monitoring_date": now - timedelta(hours=6),
                "temperature": 20.1,
                "humidity": 42.5,
                "particle_count_05um": 2800,
                "particle_count_5um": 15,
                "viable_count": 0,
                "result": MonitoringResult.PASS,
                "alert_limit": 3520.0,
                "action_limit": 3520.0,
                "monitored_by": "James Rodriguez",
            },
            {
                "id": "ENV-002",
                "zone": EnvironmentalZone.GRADE_A,
                "room_name": "Aseptic Fill Room A-101",
                "monitoring_date": now - timedelta(hours=18),
                "temperature": 20.3,
                "humidity": 43.1,
                "particle_count_05um": 3200,
                "particle_count_5um": 18,
                "viable_count": 0,
                "result": MonitoringResult.PASS,
                "alert_limit": 3520.0,
                "action_limit": 3520.0,
                "monitored_by": "James Rodriguez",
            },
            {
                "id": "ENV-003",
                "zone": EnvironmentalZone.GRADE_A,
                "room_name": "Aseptic Fill Room A-102",
                "monitoring_date": now - timedelta(hours=4),
                "temperature": 20.8,
                "humidity": 44.2,
                "particle_count_05um": 3500,
                "particle_count_5um": 20,
                "viable_count": 1,
                "result": MonitoringResult.ALERT,
                "alert_limit": 3520.0,
                "action_limit": 3520.0,
                "monitored_by": "Lisa Park",
            },
            {
                "id": "ENV-004",
                "zone": EnvironmentalZone.GRADE_B,
                "room_name": "Gowning Room B-201",
                "monitoring_date": now - timedelta(hours=8),
                "temperature": 20.5,
                "humidity": 45.0,
                "particle_count_05um": 320000,
                "particle_count_5um": 2500,
                "viable_count": 3,
                "result": MonitoringResult.PASS,
                "alert_limit": 352000.0,
                "action_limit": 352000.0,
                "monitored_by": "Lisa Park",
            },
            {
                "id": "ENV-005",
                "zone": EnvironmentalZone.GRADE_B,
                "room_name": "Background Room B-202",
                "monitoring_date": now - timedelta(hours=10),
                "temperature": 21.0,
                "humidity": 46.3,
                "particle_count_05um": 345000,
                "particle_count_5um": 2800,
                "viable_count": 4,
                "result": MonitoringResult.PASS,
                "alert_limit": 352000.0,
                "action_limit": 352000.0,
                "monitored_by": "James Rodriguez",
            },
            {
                "id": "ENV-006",
                "zone": EnvironmentalZone.GRADE_C,
                "room_name": "Formulation Room C-301",
                "monitoring_date": now - timedelta(hours=12),
                "temperature": 21.5,
                "humidity": 48.0,
                "particle_count_05um": 3400000,
                "particle_count_5um": 28000,
                "viable_count": 45,
                "result": MonitoringResult.PASS,
                "alert_limit": 3520000.0,
                "action_limit": 3520000.0,
                "monitored_by": "Maria Santos",
            },
            {
                "id": "ENV-007",
                "zone": EnvironmentalZone.GRADE_C,
                "room_name": "Compounding Room C-302",
                "monitoring_date": now - timedelta(hours=14),
                "temperature": 22.0,
                "humidity": 50.5,
                "particle_count_05um": 3480000,
                "particle_count_5um": 29500,
                "viable_count": 50,
                "result": MonitoringResult.ALERT,
                "alert_limit": 3520000.0,
                "action_limit": 3520000.0,
                "monitored_by": "Maria Santos",
            },
            {
                "id": "ENV-008",
                "zone": EnvironmentalZone.GRADE_D,
                "room_name": "Packaging Room D-401",
                "monitoring_date": now - timedelta(hours=16),
                "temperature": 22.5,
                "humidity": 52.0,
                "particle_count_05um": 3500000,
                "particle_count_5um": 29000,
                "viable_count": 90,
                "result": MonitoringResult.PASS,
                "alert_limit": None,
                "action_limit": None,
                "monitored_by": "Tom Williams",
            },
            {
                "id": "ENV-009",
                "zone": EnvironmentalZone.GRADE_A,
                "room_name": "Aseptic Fill Room A-101",
                "monitoring_date": now - timedelta(days=1),
                "temperature": 23.5,
                "humidity": 55.0,
                "particle_count_05um": 4200,
                "particle_count_5um": 35,
                "viable_count": 2,
                "result": MonitoringResult.ACTION_REQUIRED,
                "alert_limit": 3520.0,
                "action_limit": 3520.0,
                "monitored_by": "James Rodriguez",
            },
            {
                "id": "ENV-010",
                "zone": EnvironmentalZone.GRADE_B,
                "room_name": "Gowning Room B-201",
                "monitoring_date": now - timedelta(days=2),
                "temperature": 24.0,
                "humidity": 58.0,
                "particle_count_05um": 380000,
                "particle_count_5um": 3100,
                "viable_count": 8,
                "result": MonitoringResult.FAIL,
                "alert_limit": 352000.0,
                "action_limit": 352000.0,
                "monitored_by": "Lisa Park",
            },
            {
                "id": "ENV-011",
                "zone": EnvironmentalZone.GRADE_D,
                "room_name": "Warehouse Area D-501",
                "monitoring_date": now - timedelta(hours=20),
                "temperature": 21.0,
                "humidity": 45.0,
                "particle_count_05um": 3200000,
                "particle_count_5um": 25000,
                "viable_count": 70,
                "result": MonitoringResult.PASS,
                "alert_limit": None,
                "action_limit": None,
                "monitored_by": "Tom Williams",
            },
            {
                "id": "ENV-012",
                "zone": EnvironmentalZone.UNCLASSIFIED,
                "room_name": "QC Laboratory L-601",
                "monitoring_date": now - timedelta(hours=22),
                "temperature": 22.0,
                "humidity": 47.0,
                "particle_count_05um": None,
                "particle_count_5um": None,
                "viable_count": None,
                "result": MonitoringResult.PASS,
                "alert_limit": None,
                "action_limit": None,
                "monitored_by": "Tom Williams",
            },
        ]

        for e in env_data:
            self._env_monitoring[e["id"]] = EnvironmentalMonitoring(**e)

        # --- 4 Process Validations ---
        validations_data = [
            {
                "id": "PV-001",
                "product_name": "Dupilumab 300mg Prefilled Syringe",
                "process_step": "Aseptic Fill and Finish",
                "validation_protocol": "VP-DUP-AF-001",
                "status": ValidationStatus.PASSED,
                "start_date": now - timedelta(days=180),
                "completion_date": now - timedelta(days=90),
                "batches_required": 3,
                "batches_completed": 3,
                "acceptance_criteria": "Sterility assurance level <= 10^-6; Fill weight within 95-105% of target; Container closure integrity pass",
                "results_summary": "All 3 consecutive batches met acceptance criteria. Process validated.",
                "approved_by": "Dr. Michael Torres",
            },
            {
                "id": "PV-002",
                "product_name": "Aflibercept 2mg Intravitreal Injection",
                "process_step": "Viral Inactivation (Low pH Hold)",
                "validation_protocol": "VP-AFL-VI-002",
                "status": ValidationStatus.IN_PROGRESS,
                "start_date": now - timedelta(days=45),
                "completion_date": None,
                "batches_required": 3,
                "batches_completed": 2,
                "acceptance_criteria": "Log reduction value >= 4.0 for model virus; pH maintained at 3.5 +/- 0.1 for 60 min",
                "results_summary": "Batches 1 and 2 passed. Batch 3 in progress.",
                "approved_by": None,
            },
            {
                "id": "PV-003",
                "product_name": "Cemiplimab 350mg IV Solution",
                "process_step": "Upstream Cell Culture (Fed-Batch)",
                "validation_protocol": "VP-CEM-CC-001",
                "status": ValidationStatus.PLANNED,
                "start_date": None,
                "completion_date": None,
                "batches_required": 3,
                "batches_completed": 0,
                "acceptance_criteria": "Titer >= 3.0 g/L; Cell viability >= 80% at harvest; Batch-to-batch variability < 10%",
                "results_summary": None,
                "approved_by": None,
            },
            {
                "id": "PV-004",
                "product_name": "Aflibercept 8mg Intravitreal Injection",
                "process_step": "Formulation and Sterile Filtration",
                "validation_protocol": "VP-AFL8-FF-001",
                "status": ValidationStatus.FAILED,
                "start_date": now - timedelta(days=120),
                "completion_date": now - timedelta(days=70),
                "batches_required": 3,
                "batches_completed": 3,
                "acceptance_criteria": "Filter integrity test pass; Bioburden < 10 CFU/100mL pre-filtration; Sterility pass post-filtration",
                "results_summary": "Batch 2 failed filter integrity test. Process requires modification and revalidation.",
                "approved_by": None,
            },
        ]

        for v in validations_data:
            self._validations[v["id"]] = ProcessValidation(**v)

        # --- 5 Deviations ---
        deviations_data = [
            {
                "id": "DEV-001",
                "batch_id": "BATCH-005",
                "deviation_type": DeviationType.MAJOR,
                "description": "Low yield (80%) observed during fill-finish of Aflibercept 8mg batch AFL8-2026-001. Target yield was 95%.",
                "root_cause": "Syringe breakage rate higher than expected due to glass quality issue from supplier",
                "impact_assessment": "Product quality unaffected for filled units. 600 units lost, impacting supply timeline by 2 weeks.",
                "corrective_action": "Incoming QC testing enhanced for glass syringes. Supplier notified with corrective action request.",
                "preventive_action": "Dual-source supplier qualification initiated. Statistical process control limits tightened for breakage rate.",
                "reported_by": "Dr. Karen Li",
                "reported_date": now - timedelta(days=50),
                "resolved_date": now - timedelta(days=20),
                "status": DeviationStatus.CLOSED,
            },
            {
                "id": "DEV-002",
                "batch_id": "BATCH-003",
                "deviation_type": DeviationType.MINOR,
                "description": "Temperature excursion of 0.5C above upper limit for 12 minutes during cell culture incubation.",
                "root_cause": "HVAC system cycling during peak load. Controller set point drift.",
                "impact_assessment": "No impact on cell growth or product quality. Excursion within acceptable historical range.",
                "corrective_action": "HVAC controller recalibrated. Set point adjusted.",
                "preventive_action": None,
                "reported_by": "James Rodriguez",
                "reported_date": now - timedelta(days=4),
                "resolved_date": now - timedelta(days=2),
                "status": DeviationStatus.CLOSED,
            },
            {
                "id": "DEV-003",
                "batch_id": "BATCH-005",
                "deviation_type": DeviationType.CRITICAL,
                "description": "Environmental monitoring excursion in Grade A zone during fill operation. Particle count exceeded action limit.",
                "root_cause": None,
                "impact_assessment": "Batch quarantined pending investigation. Potential sterility risk for units filled during excursion window.",
                "corrective_action": None,
                "preventive_action": None,
                "reported_by": "Lisa Park",
                "reported_date": now - timedelta(days=55),
                "resolved_date": None,
                "status": DeviationStatus.UNDER_INVESTIGATION,
            },
            {
                "id": "DEV-004",
                "batch_id": None,
                "deviation_type": DeviationType.MINOR,
                "description": "Calibration of pH meter PM-042 found 0.02 pH units outside acceptance criteria during routine check.",
                "root_cause": "Probe aging. Electrode nearing end of service life.",
                "impact_assessment": "Review of batches tested with this probe shows all results well within specification. No product impact.",
                "corrective_action": "Probe replaced. New probe calibrated and verified.",
                "preventive_action": "Probe replacement frequency changed from 12 months to 9 months.",
                "reported_by": "Maria Santos",
                "reported_date": now - timedelta(days=10),
                "resolved_date": None,
                "status": DeviationStatus.CORRECTIVE_ACTION,
            },
            {
                "id": "DEV-005",
                "batch_id": "BATCH-002",
                "deviation_type": DeviationType.MINOR,
                "description": "Batch record documentation error: operator recorded wrong clock-in time on page 14.",
                "root_cause": "Human error. Operator transposed digits.",
                "impact_assessment": "No impact on product quality or process parameters. Documentation corrected with audit trail.",
                "corrective_action": "Documentation corrected, single-line strikethrough with initials and date per SOP.",
                "preventive_action": None,
                "reported_by": "Tom Williams",
                "reported_date": now - timedelta(days=12),
                "resolved_date": now - timedelta(days=11),
                "status": DeviationStatus.CLOSED,
            },
        ]

        for d in deviations_data:
            self._deviations[d["id"]] = ManufacturingDeviation(**d)

        # --- 14 Checklist Items (spread across BATCH-001, BATCH-002, BATCH-005) ---
        checklist_data = [
            # BATCH-001 (released) - all checked
            {"id": "CL-001", "batch_id": "BATCH-001", "item_description": "Batch record review complete", "required": True, "checked": True, "checked_by": "Dr. Sarah Chen", "checked_date": now - timedelta(days=26), "notes": None},
            {"id": "CL-002", "batch_id": "BATCH-001", "item_description": "In-process control results within specification", "required": True, "checked": True, "checked_by": "Dr. Sarah Chen", "checked_date": now - timedelta(days=26), "notes": None},
            {"id": "CL-003", "batch_id": "BATCH-001", "item_description": "Environmental monitoring results acceptable", "required": True, "checked": True, "checked_by": "Dr. Sarah Chen", "checked_date": now - timedelta(days=26), "notes": None},
            {"id": "CL-004", "batch_id": "BATCH-001", "item_description": "Finished product testing complete and within specification", "required": True, "checked": True, "checked_by": "Dr. Sarah Chen", "checked_date": now - timedelta(days=26), "notes": None},
            {"id": "CL-005", "batch_id": "BATCH-001", "item_description": "Stability samples placed on stability program", "required": True, "checked": True, "checked_by": "Dr. Sarah Chen", "checked_date": now - timedelta(days=26), "notes": None},
            {"id": "CL-006", "batch_id": "BATCH-001", "item_description": "All deviations closed or assessed as no impact", "required": True, "checked": True, "checked_by": "Dr. Sarah Chen", "checked_date": now - timedelta(days=26), "notes": "No deviations for this batch"},
            {"id": "CL-007", "batch_id": "BATCH-001", "item_description": "Certificate of Analysis generated", "required": True, "checked": True, "checked_by": "Dr. Michael Torres", "checked_date": now - timedelta(days=25), "notes": None},
            # BATCH-002 (completed, not yet released) - partially checked
            {"id": "CL-008", "batch_id": "BATCH-002", "item_description": "Batch record review complete", "required": True, "checked": True, "checked_by": "Dr. Sarah Chen", "checked_date": now - timedelta(days=5), "notes": None},
            {"id": "CL-009", "batch_id": "BATCH-002", "item_description": "In-process control results within specification", "required": True, "checked": True, "checked_by": "Dr. Sarah Chen", "checked_date": now - timedelta(days=5), "notes": None},
            {"id": "CL-010", "batch_id": "BATCH-002", "item_description": "Environmental monitoring results acceptable", "required": True, "checked": False, "checked_by": None, "checked_date": None, "notes": None},
            {"id": "CL-011", "batch_id": "BATCH-002", "item_description": "Finished product testing complete and within specification", "required": True, "checked": False, "checked_by": None, "checked_date": None, "notes": "Awaiting sterility test results (14-day incubation)"},
            {"id": "CL-012", "batch_id": "BATCH-002", "item_description": "Certificate of Analysis generated", "required": True, "checked": False, "checked_by": None, "checked_date": None, "notes": None},
            # BATCH-005 (quarantine) - some checked
            {"id": "CL-013", "batch_id": "BATCH-005", "item_description": "Batch record review complete", "required": True, "checked": True, "checked_by": "Dr. Karen Li", "checked_date": now - timedelta(days=48), "notes": "Low yield noted - deviation DEV-001 raised"},
            {"id": "CL-014", "batch_id": "BATCH-005", "item_description": "All deviations closed or assessed as no impact", "required": True, "checked": False, "checked_by": None, "checked_date": None, "notes": "DEV-003 still under investigation - cannot release"},
        ]

        for c in checklist_data:
            self._checklists[c["id"]] = BatchReleaseChecklist(**c)

    # ------------------------------------------------------------------
    # Batch Record Management
    # ------------------------------------------------------------------

    def list_batches(
        self,
        *,
        status: BatchStatus | None = None,
        manufacturing_site: str | None = None,
        product_name: str | None = None,
    ) -> list[BatchRecord]:
        """List batch records with optional filters."""
        with self._lock:
            result = list(self._batches.values())

        if status is not None:
            result = [b for b in result if b.status == status]
        if manufacturing_site is not None:
            result = [b for b in result if manufacturing_site.lower() in b.manufacturing_site.lower()]
        if product_name is not None:
            result = [b for b in result if product_name.lower() in b.product_name.lower()]

        return sorted(result, key=lambda b: b.id)

    def get_batch(self, batch_id: str) -> BatchRecord | None:
        """Get a single batch record by ID."""
        with self._lock:
            return self._batches.get(batch_id)

    def create_batch(self, payload: BatchRecordCreate) -> BatchRecord:
        """Create a new batch record."""
        batch_id = f"BATCH-{uuid4().hex[:8].upper()}"
        batch = BatchRecord(
            id=batch_id,
            product_name=payload.product_name,
            batch_number=payload.batch_number,
            lot_number=payload.lot_number,
            manufacturing_site=payload.manufacturing_site,
            batch_size=payload.batch_size,
            unit_of_measure=payload.unit_of_measure,
            start_date=None,
            end_date=None,
            status=BatchStatus.PLANNED,
            yield_actual=None,
            yield_theoretical=payload.yield_theoretical,
            yield_pct=None,
            master_batch_record_version=payload.master_batch_record_version,
            reviewed_by=None,
            released_by=None,
            release_date=None,
        )
        with self._lock:
            self._batches[batch_id] = batch
        logger.info("Created batch %s: %s", batch_id, payload.product_name)
        return batch

    def update_batch(self, batch_id: str, payload: BatchRecordUpdate) -> BatchRecord | None:
        """Update an existing batch record."""
        with self._lock:
            existing = self._batches.get(batch_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            # Recalculate yield_pct if both actuals and theoretical are present
            if data.get("yield_actual") is not None and data.get("yield_theoretical") and data["yield_theoretical"] > 0:
                data["yield_pct"] = round(data["yield_actual"] / data["yield_theoretical"] * 100, 1)
            updated = BatchRecord(**data)
            self._batches[batch_id] = updated
        return updated

    def delete_batch(self, batch_id: str) -> bool:
        """Delete a batch record. Returns True if deleted."""
        with self._lock:
            if batch_id in self._batches:
                del self._batches[batch_id]
                return True
            return False

    def start_batch(self, batch_id: str) -> BatchRecord | None:
        """Transition a batch from PLANNED to IN_PROGRESS."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._batches.get(batch_id)
            if existing is None:
                return None
            if existing.status != BatchStatus.PLANNED:
                raise ValueError(
                    f"Batch '{batch_id}' cannot be started: current status is '{existing.status.value}', "
                    f"expected 'planned'"
                )
            data = existing.model_dump()
            data["status"] = BatchStatus.IN_PROGRESS
            data["start_date"] = now
            updated = BatchRecord(**data)
            self._batches[batch_id] = updated
        logger.info("Started batch %s", batch_id)
        return updated

    def complete_batch(
        self,
        batch_id: str,
        yield_actual: float,
    ) -> BatchRecord | None:
        """Mark a batch as completed with actual yield data."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._batches.get(batch_id)
            if existing is None:
                return None
            if existing.status != BatchStatus.IN_PROGRESS:
                raise ValueError(
                    f"Batch '{batch_id}' cannot be completed: current status is '{existing.status.value}', "
                    f"expected 'in_progress'"
                )
            data = existing.model_dump()
            data["status"] = BatchStatus.COMPLETED
            data["end_date"] = now
            data["yield_actual"] = yield_actual
            if data.get("yield_theoretical") and data["yield_theoretical"] > 0:
                data["yield_pct"] = round(yield_actual / data["yield_theoretical"] * 100, 1)
            updated = BatchRecord(**data)
            self._batches[batch_id] = updated
        logger.info("Completed batch %s with yield %.1f", batch_id, yield_actual)
        return updated

    def release_batch(
        self,
        batch_id: str,
        payload: BatchReleaseRequest,
    ) -> BatchRecord | None:
        """Release a batch after verifying all required checklist items are complete."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._batches.get(batch_id)
            if existing is None:
                return None
            if existing.status != BatchStatus.COMPLETED:
                raise ValueError(
                    f"Batch '{batch_id}' cannot be released: current status is '{existing.status.value}', "
                    f"expected 'completed'"
                )
            # Check all required checklist items are completed
            batch_checklists = [
                c for c in self._checklists.values()
                if c.batch_id == batch_id
            ]
            required_unchecked = [
                c for c in batch_checklists
                if c.required and not c.checked
            ]
            if required_unchecked:
                descriptions = [c.item_description for c in required_unchecked]
                raise ValueError(
                    f"Cannot release batch '{batch_id}': {len(required_unchecked)} required "
                    f"checklist item(s) not completed: {descriptions}"
                )
            # Check no open critical deviations
            open_critical_devs = [
                d for d in self._deviations.values()
                if d.batch_id == batch_id
                and d.deviation_type == DeviationType.CRITICAL
                and d.status != DeviationStatus.CLOSED
            ]
            if open_critical_devs:
                raise ValueError(
                    f"Cannot release batch '{batch_id}': {len(open_critical_devs)} open "
                    f"critical deviation(s) exist"
                )

            data = existing.model_dump()
            data["status"] = BatchStatus.RELEASED
            data["released_by"] = payload.released_by
            data["reviewed_by"] = payload.reviewed_by
            data["release_date"] = now
            updated = BatchRecord(**data)
            self._batches[batch_id] = updated
        logger.info("Released batch %s by %s", batch_id, payload.released_by)
        return updated

    # ------------------------------------------------------------------
    # Equipment Management
    # ------------------------------------------------------------------

    def list_equipment(
        self,
        *,
        status: EquipmentStatus | None = None,
        equipment_type: str | None = None,
        assigned_area: str | None = None,
    ) -> list[Equipment]:
        """List equipment with optional filters."""
        with self._lock:
            result = list(self._equipment.values())

        if status is not None:
            result = [e for e in result if e.status == status]
        if equipment_type is not None:
            result = [e for e in result if equipment_type.lower() in e.equipment_type.lower()]
        if assigned_area is not None:
            result = [e for e in result if e.assigned_area and assigned_area.lower() in e.assigned_area.lower()]

        return sorted(result, key=lambda e: e.id)

    def get_equipment(self, equipment_id: str) -> Equipment | None:
        """Get a single equipment record by ID."""
        with self._lock:
            return self._equipment.get(equipment_id)

    def create_equipment(self, payload: EquipmentCreate) -> Equipment:
        """Create a new equipment record."""
        eq_id = f"EQ-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        equipment = Equipment(
            id=eq_id,
            name=payload.name,
            equipment_type=payload.equipment_type,
            serial_number=payload.serial_number,
            location=payload.location,
            status=EquipmentStatus.QUALIFIED,
            last_qualification_date=now,
            next_qualification_date=now + timedelta(days=365),
            calibration_due_date=now + timedelta(days=180),
            maintenance_schedule=payload.maintenance_schedule,
            assigned_area=payload.assigned_area,
        )
        with self._lock:
            self._equipment[eq_id] = equipment
        logger.info("Created equipment %s: %s", eq_id, payload.name)
        return equipment

    def update_equipment(self, equipment_id: str, payload: EquipmentUpdate) -> Equipment | None:
        """Update an equipment record."""
        with self._lock:
            existing = self._equipment.get(equipment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = Equipment(**data)
            self._equipment[equipment_id] = updated
        return updated

    def delete_equipment(self, equipment_id: str) -> bool:
        """Delete an equipment record. Returns True if deleted."""
        with self._lock:
            if equipment_id in self._equipment:
                del self._equipment[equipment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Environmental Monitoring
    # ------------------------------------------------------------------

    def list_environmental_monitoring(
        self,
        *,
        zone: EnvironmentalZone | None = None,
        result: MonitoringResult | None = None,
        room_name: str | None = None,
    ) -> list[EnvironmentalMonitoring]:
        """List environmental monitoring records with optional filters."""
        with self._lock:
            records = list(self._env_monitoring.values())

        if zone is not None:
            records = [r for r in records if r.zone == zone]
        if result is not None:
            records = [r for r in records if r.result == result]
        if room_name is not None:
            records = [r for r in records if room_name.lower() in r.room_name.lower()]

        return sorted(records, key=lambda r: r.monitoring_date, reverse=True)

    def get_environmental_monitoring(self, record_id: str) -> EnvironmentalMonitoring | None:
        """Get a single environmental monitoring record by ID."""
        with self._lock:
            return self._env_monitoring.get(record_id)

    def log_environmental_monitoring(
        self,
        payload: EnvironmentalMonitoringCreate,
    ) -> EnvironmentalMonitoring:
        """Log a new environmental monitoring event with automatic result evaluation."""
        now = datetime.now(timezone.utc)
        record_id = f"ENV-{uuid4().hex[:8].upper()}"

        # Determine result based on zone limits and readings
        monitoring_result = self._evaluate_environmental_result(payload)

        record = EnvironmentalMonitoring(
            id=record_id,
            zone=payload.zone,
            room_name=payload.room_name,
            monitoring_date=now,
            temperature=payload.temperature,
            humidity=payload.humidity,
            particle_count_05um=payload.particle_count_05um,
            particle_count_5um=payload.particle_count_5um,
            viable_count=payload.viable_count,
            result=monitoring_result,
            alert_limit=payload.alert_limit,
            action_limit=payload.action_limit,
            monitored_by=payload.monitored_by,
        )

        with self._lock:
            self._env_monitoring[record_id] = record
        logger.info(
            "Logged environmental monitoring %s: zone=%s room=%s result=%s",
            record_id, payload.zone.value, payload.room_name, monitoring_result.value,
        )
        return record

    @staticmethod
    def _evaluate_environmental_result(
        payload: EnvironmentalMonitoringCreate,
    ) -> MonitoringResult:
        """Evaluate environmental monitoring result based on zone limits.

        Grade A limits (at rest): 0.5um <= 3520/m3, 5um <= 20/m3, viable <= 1 CFU
        """
        if payload.zone == EnvironmentalZone.GRADE_A:
            if payload.particle_count_05um is not None and payload.particle_count_05um > 3520:
                if payload.particle_count_05um > 3520 * 1.5:
                    return MonitoringResult.FAIL
                return MonitoringResult.ACTION_REQUIRED
            if payload.particle_count_5um is not None and payload.particle_count_5um > 20:
                if payload.particle_count_5um > 30:
                    return MonitoringResult.FAIL
                return MonitoringResult.ACTION_REQUIRED
            if payload.viable_count is not None and payload.viable_count > 1:
                if payload.viable_count > 3:
                    return MonitoringResult.FAIL
                return MonitoringResult.ALERT
        elif payload.zone == EnvironmentalZone.GRADE_B:
            if payload.particle_count_05um is not None and payload.particle_count_05um > 352000:
                if payload.particle_count_05um > 352000 * 1.5:
                    return MonitoringResult.FAIL
                return MonitoringResult.ACTION_REQUIRED
            if payload.viable_count is not None and payload.viable_count > 5:
                if payload.viable_count > 10:
                    return MonitoringResult.FAIL
                return MonitoringResult.ALERT

        # Check temperature and humidity universally
        if payload.temperature is not None:
            if payload.temperature > 25.0 or payload.temperature < 15.0:
                return MonitoringResult.ACTION_REQUIRED
            if payload.temperature > 23.0 or payload.temperature < 17.0:
                return MonitoringResult.ALERT

        if payload.humidity is not None:
            if payload.humidity > 65.0 or payload.humidity < 30.0:
                return MonitoringResult.ACTION_REQUIRED
            if payload.humidity > 55.0 or payload.humidity < 35.0:
                return MonitoringResult.ALERT

        return MonitoringResult.PASS

    # ------------------------------------------------------------------
    # Process Validation
    # ------------------------------------------------------------------

    def list_validations(
        self,
        *,
        status: ValidationStatus | None = None,
        product_name: str | None = None,
    ) -> list[ProcessValidation]:
        """List process validations with optional filters."""
        with self._lock:
            result = list(self._validations.values())

        if status is not None:
            result = [v for v in result if v.status == status]
        if product_name is not None:
            result = [v for v in result if product_name.lower() in v.product_name.lower()]

        return sorted(result, key=lambda v: v.id)

    def get_validation(self, validation_id: str) -> ProcessValidation | None:
        """Get a single process validation by ID."""
        with self._lock:
            return self._validations.get(validation_id)

    def create_validation(self, payload: ProcessValidationCreate) -> ProcessValidation:
        """Create a new process validation record."""
        val_id = f"PV-{uuid4().hex[:8].upper()}"
        validation = ProcessValidation(
            id=val_id,
            product_name=payload.product_name,
            process_step=payload.process_step,
            validation_protocol=payload.validation_protocol,
            status=ValidationStatus.PLANNED,
            start_date=None,
            completion_date=None,
            batches_required=payload.batches_required,
            batches_completed=0,
            acceptance_criteria=payload.acceptance_criteria,
            results_summary=None,
            approved_by=None,
        )
        with self._lock:
            self._validations[val_id] = validation
        logger.info("Created validation %s: %s - %s", val_id, payload.product_name, payload.process_step)
        return validation

    def update_validation(self, validation_id: str, payload: ProcessValidationUpdate) -> ProcessValidation | None:
        """Update a process validation record."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._validations.get(validation_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set dates on status transitions
            if "status" in updates:
                new_status = updates["status"]
                if isinstance(new_status, str):
                    new_status = ValidationStatus(new_status)
                if new_status == ValidationStatus.IN_PROGRESS and existing.status == ValidationStatus.PLANNED:
                    data["start_date"] = now
                if new_status in (ValidationStatus.PASSED, ValidationStatus.FAILED):
                    data["completion_date"] = now

            data.update(updates)
            updated = ProcessValidation(**data)
            self._validations[validation_id] = updated
        return updated

    def delete_validation(self, validation_id: str) -> bool:
        """Delete a process validation. Returns True if deleted."""
        with self._lock:
            if validation_id in self._validations:
                del self._validations[validation_id]
                return True
            return False

    def validate_process(self, validation_id: str) -> ProcessValidation | None:
        """Mark an in-progress validation as passed if batches are complete."""
        with self._lock:
            existing = self._validations.get(validation_id)
            if existing is None:
                return None
            if existing.status != ValidationStatus.IN_PROGRESS:
                raise ValueError(
                    f"Validation '{validation_id}' is not in progress (status: {existing.status.value})"
                )
            if existing.batches_completed < existing.batches_required:
                raise ValueError(
                    f"Validation '{validation_id}' requires {existing.batches_required} batches "
                    f"but only {existing.batches_completed} completed"
                )
            now = datetime.now(timezone.utc)
            data = existing.model_dump()
            data["status"] = ValidationStatus.PASSED
            data["completion_date"] = now
            updated = ProcessValidation(**data)
            self._validations[validation_id] = updated
        logger.info("Validation %s passed", validation_id)
        return updated

    # ------------------------------------------------------------------
    # Deviation Management
    # ------------------------------------------------------------------

    def list_deviations(
        self,
        *,
        deviation_type: DeviationType | None = None,
        status: DeviationStatus | None = None,
        batch_id: str | None = None,
    ) -> list[ManufacturingDeviation]:
        """List manufacturing deviations with optional filters."""
        with self._lock:
            result = list(self._deviations.values())

        if deviation_type is not None:
            result = [d for d in result if d.deviation_type == deviation_type]
        if status is not None:
            result = [d for d in result if d.status == status]
        if batch_id is not None:
            result = [d for d in result if d.batch_id == batch_id]

        return sorted(result, key=lambda d: d.reported_date, reverse=True)

    def get_deviation(self, deviation_id: str) -> ManufacturingDeviation | None:
        """Get a single deviation by ID."""
        with self._lock:
            return self._deviations.get(deviation_id)

    def record_deviation(self, payload: DeviationCreate) -> ManufacturingDeviation:
        """Record a new manufacturing deviation."""
        now = datetime.now(timezone.utc)
        dev_id = f"DEV-{uuid4().hex[:8].upper()}"
        deviation = ManufacturingDeviation(
            id=dev_id,
            batch_id=payload.batch_id,
            deviation_type=payload.deviation_type,
            description=payload.description,
            root_cause=None,
            impact_assessment=payload.impact_assessment,
            corrective_action=None,
            preventive_action=None,
            reported_by=payload.reported_by,
            reported_date=now,
            resolved_date=None,
            status=DeviationStatus.OPEN,
        )

        with self._lock:
            self._deviations[dev_id] = deviation

            # If deviation is critical and linked to a batch, quarantine the batch
            if payload.deviation_type == DeviationType.CRITICAL and payload.batch_id:
                batch = self._batches.get(payload.batch_id)
                if batch and batch.status not in (BatchStatus.RELEASED, BatchStatus.REJECTED):
                    data = batch.model_dump()
                    data["status"] = BatchStatus.QUARANTINE
                    self._batches[payload.batch_id] = BatchRecord(**data)
                    logger.info(
                        "Batch %s quarantined due to critical deviation %s",
                        payload.batch_id, dev_id,
                    )

        logger.info("Recorded deviation %s: type=%s", dev_id, payload.deviation_type.value)
        return deviation

    def update_deviation(self, deviation_id: str, payload: DeviationUpdate) -> ManufacturingDeviation | None:
        """Update a manufacturing deviation."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._deviations.get(deviation_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set resolved_date when status goes to closed
            if "status" in updates:
                new_status = updates["status"]
                if isinstance(new_status, str):
                    new_status = DeviationStatus(new_status)
                if new_status == DeviationStatus.CLOSED and existing.status != DeviationStatus.CLOSED:
                    data["resolved_date"] = now

            data.update(updates)
            updated = ManufacturingDeviation(**data)
            self._deviations[deviation_id] = updated
        return updated

    def delete_deviation(self, deviation_id: str) -> bool:
        """Delete a deviation. Returns True if deleted."""
        with self._lock:
            if deviation_id in self._deviations:
                del self._deviations[deviation_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Batch Release Checklists
    # ------------------------------------------------------------------

    def list_checklists(
        self,
        *,
        batch_id: str | None = None,
        checked: bool | None = None,
    ) -> list[BatchReleaseChecklist]:
        """List batch release checklist items with optional filters."""
        with self._lock:
            result = list(self._checklists.values())

        if batch_id is not None:
            result = [c for c in result if c.batch_id == batch_id]
        if checked is not None:
            result = [c for c in result if c.checked == checked]

        return sorted(result, key=lambda c: c.id)

    def get_checklist_item(self, item_id: str) -> BatchReleaseChecklist | None:
        """Get a single checklist item by ID."""
        with self._lock:
            return self._checklists.get(item_id)

    def create_checklist_item(self, payload: ChecklistItemCreate) -> BatchReleaseChecklist:
        """Create a new checklist item."""
        item_id = f"CL-{uuid4().hex[:8].upper()}"
        item = BatchReleaseChecklist(
            id=item_id,
            batch_id=payload.batch_id,
            item_description=payload.item_description,
            required=payload.required,
            checked=False,
            checked_by=None,
            checked_date=None,
            notes=None,
        )
        with self._lock:
            self._checklists[item_id] = item
        logger.info("Created checklist item %s for batch %s", item_id, payload.batch_id)
        return item

    def update_checklist_item(self, item_id: str, payload: ChecklistItemUpdate) -> BatchReleaseChecklist | None:
        """Update a checklist item (e.g., mark as checked)."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._checklists.get(item_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set checked_date when marking as checked
            if updates.get("checked") is True and not existing.checked:
                data["checked_date"] = now

            data.update(updates)
            updated = BatchReleaseChecklist(**data)
            self._checklists[item_id] = updated
        return updated

    def delete_checklist_item(self, item_id: str) -> bool:
        """Delete a checklist item. Returns True if deleted."""
        with self._lock:
            if item_id in self._checklists:
                del self._checklists[item_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics & Dashboard
    # ------------------------------------------------------------------

    def get_metrics(self) -> ManufacturingMetrics:
        """Compute aggregated manufacturing operations metrics."""
        with self._lock:
            batches = list(self._batches.values())
            equipment = list(self._equipment.values())
            env_records = list(self._env_monitoring.values())
            validations = list(self._validations.values())
            deviations = list(self._deviations.values())
            checklists = list(self._checklists.values())

        # Batches by status
        batches_by_status: dict[str, int] = {}
        completed_yields: list[float] = []
        batches_released = 0
        batches_rejected = 0
        for b in batches:
            key = b.status.value
            batches_by_status[key] = batches_by_status.get(key, 0) + 1
            if b.yield_pct is not None:
                completed_yields.append(b.yield_pct)
            if b.status == BatchStatus.RELEASED:
                batches_released += 1
            elif b.status == BatchStatus.REJECTED:
                batches_rejected += 1

        avg_yield = round(sum(completed_yields) / max(1, len(completed_yields)), 1) if completed_yields else 0.0

        # Equipment by status
        equipment_by_status: dict[str, int] = {}
        eq_due_requalification = 0
        for e in equipment:
            key = e.status.value
            equipment_by_status[key] = equipment_by_status.get(key, 0) + 1
            if e.status == EquipmentStatus.DUE_FOR_REQUALIFICATION:
                eq_due_requalification += 1

        # Environmental excursions
        env_excursions = sum(
            1 for r in env_records
            if r.result in (MonitoringResult.ACTION_REQUIRED, MonitoringResult.FAIL)
        )

        # Validations in progress
        val_in_progress = sum(
            1 for v in validations if v.status == ValidationStatus.IN_PROGRESS
        )

        # Deviations
        open_devs = sum(
            1 for d in deviations if d.status != DeviationStatus.CLOSED
        )
        deviations_by_type: dict[str, int] = {}
        for d in deviations:
            key = d.deviation_type.value
            deviations_by_type[key] = deviations_by_type.get(key, 0) + 1

        # Checklists
        total_cl = len(checklists)
        checked_cl = sum(1 for c in checklists if c.checked)
        cl_pct = round(checked_cl / max(1, total_cl) * 100, 1)

        return ManufacturingMetrics(
            total_batches=len(batches),
            batches_by_status=batches_by_status,
            avg_yield_pct=avg_yield,
            total_equipment=len(equipment),
            equipment_by_status=equipment_by_status,
            equipment_due_for_requalification=eq_due_requalification,
            total_environmental_records=len(env_records),
            environmental_excursions=env_excursions,
            total_validations=len(validations),
            validations_in_progress=val_in_progress,
            total_deviations=len(deviations),
            open_deviations=open_devs,
            deviations_by_type=deviations_by_type,
            total_checklist_items=total_cl,
            checklist_completion_pct=cl_pct,
            batches_released=batches_released,
            batches_rejected=batches_rejected,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: ManufacturingOpsService | None = None
_instance_lock = threading.Lock()


def get_manufacturing_ops_service() -> ManufacturingOpsService:
    """Return the singleton ManufacturingOpsService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ManufacturingOpsService()
    return _instance


def reset_manufacturing_ops_service() -> ManufacturingOpsService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = ManufacturingOpsService()
    return _instance
