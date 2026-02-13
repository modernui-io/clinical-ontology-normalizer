"""Site Resource Planning (SRP-PLN) Service.

Manages site resource planning operations: staff allocations, equipment
inventories, capacity assessments, and workload distributions with metrics.

Usage:
    from app.services.site_resource_planning_service import (
        get_site_resource_planning_service,
    )

    svc = get_site_resource_planning_service()
    allocations = svc.list_staff_allocations()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.site_resource_planning import (
    AllocationStatus,
    CapacityAssessment,
    CapacityAssessmentCreate,
    CapacityAssessmentUpdate,
    CapacityLevel,
    EquipmentInventory,
    EquipmentInventoryCreate,
    EquipmentInventoryUpdate,
    EquipmentStatus,
    SiteResourcePlanningMetrics,
    StaffAllocation,
    StaffAllocationCreate,
    StaffAllocationUpdate,
    StaffRole,
    WorkloadDistribution,
    WorkloadDistributionCreate,
    WorkloadDistributionUpdate,
    WorkloadPriority,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class SiteResourcePlanningService:
    """In-memory Site Resource Planning engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._staff_allocations: dict[str, StaffAllocation] = {}
        self._equipment_inventories: dict[str, EquipmentInventory] = {}
        self._capacity_assessments: dict[str, CapacityAssessment] = {}
        self._workload_distributions: dict[str, WorkloadDistribution] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic site resource planning data across trials."""
        now = datetime.now(timezone.utc)

        # --- 12 Staff Allocations (4 per trial) ---
        staff_data = [
            {
                "id": "STA-00000001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "allocation_status": AllocationStatus.ALLOCATED,
                "staff_name": "Dr. Sarah Chen",
                "staff_role": StaffRole.PRINCIPAL_INVESTIGATOR,
                "fte_percentage": 40.0,
                "start_date": now - timedelta(days=180),
                "end_date": None,
                "supervisor_name": None,
                "certification_verified": True,
                "training_completed": True,
                "delegation_log_entry": "DL-001",
                "allocated_by": "Clinical Ops Manager",
                "notes": "Lead PI for EYLEA Phase III",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "STA-00000002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "allocation_status": AllocationStatus.ALLOCATED,
                "staff_name": "Dr. James Park",
                "staff_role": StaffRole.SUB_INVESTIGATOR,
                "fte_percentage": 60.0,
                "start_date": now - timedelta(days=170),
                "end_date": None,
                "supervisor_name": "Dr. Sarah Chen",
                "certification_verified": True,
                "training_completed": True,
                "delegation_log_entry": "DL-002",
                "allocated_by": "Clinical Ops Manager",
                "notes": None,
                "created_at": now - timedelta(days=190),
            },
            {
                "id": "STA-00000003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "allocation_status": AllocationStatus.PENDING,
                "staff_name": "Maria Santos",
                "staff_role": StaffRole.STUDY_COORDINATOR,
                "fte_percentage": 80.0,
                "start_date": now - timedelta(days=30),
                "end_date": None,
                "supervisor_name": "Dr. Sarah Chen",
                "certification_verified": False,
                "training_completed": False,
                "delegation_log_entry": None,
                "allocated_by": "Site Manager",
                "notes": "Awaiting GCP certification",
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "STA-00000004",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "allocation_status": AllocationStatus.ALLOCATED,
                "staff_name": "Rachel Kim",
                "staff_role": StaffRole.RESEARCH_NURSE,
                "fte_percentage": 100.0,
                "start_date": now - timedelta(days=160),
                "end_date": None,
                "supervisor_name": "Dr. James Park",
                "certification_verified": True,
                "training_completed": True,
                "delegation_log_entry": "DL-003",
                "allocated_by": "Clinical Ops Manager",
                "notes": None,
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "STA-00000005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "allocation_status": AllocationStatus.ALLOCATED,
                "staff_name": "Dr. Michael Torres",
                "staff_role": StaffRole.PRINCIPAL_INVESTIGATOR,
                "fte_percentage": 50.0,
                "start_date": now - timedelta(days=120),
                "end_date": None,
                "supervisor_name": None,
                "certification_verified": True,
                "training_completed": True,
                "delegation_log_entry": "DL-010",
                "allocated_by": "Regional Director",
                "notes": "Lead PI for DUPIXENT atopic dermatitis study",
                "created_at": now - timedelta(days=140),
            },
            {
                "id": "STA-00000006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "allocation_status": AllocationStatus.ALLOCATED,
                "staff_name": "Lisa Anderson",
                "staff_role": StaffRole.PHARMACIST,
                "fte_percentage": 30.0,
                "start_date": now - timedelta(days=100),
                "end_date": None,
                "supervisor_name": "Dr. Michael Torres",
                "certification_verified": True,
                "training_completed": True,
                "delegation_log_entry": "DL-011",
                "allocated_by": "Regional Director",
                "notes": "IP management and dispensing",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "STA-00000007",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "allocation_status": AllocationStatus.ON_HOLD,
                "staff_name": "Kevin Wright",
                "staff_role": StaffRole.DATA_ENTRY,
                "fte_percentage": 50.0,
                "start_date": now - timedelta(days=90),
                "end_date": None,
                "supervisor_name": "Lisa Anderson",
                "certification_verified": True,
                "training_completed": False,
                "delegation_log_entry": None,
                "allocated_by": "Site Manager",
                "notes": "On hold pending EDC training completion",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "STA-00000008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "allocation_status": AllocationStatus.RELEASED,
                "staff_name": "Amy Nguyen",
                "staff_role": StaffRole.RESEARCH_NURSE,
                "fte_percentage": 75.0,
                "start_date": now - timedelta(days=150),
                "end_date": now - timedelta(days=20),
                "supervisor_name": "Dr. Michael Torres",
                "certification_verified": True,
                "training_completed": True,
                "delegation_log_entry": "DL-012",
                "allocated_by": "Regional Director",
                "notes": "Released due to site closure for renovation",
                "created_at": now - timedelta(days=160),
            },
            {
                "id": "STA-00000009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "allocation_status": AllocationStatus.ALLOCATED,
                "staff_name": "Dr. Emily Watson",
                "staff_role": StaffRole.PRINCIPAL_INVESTIGATOR,
                "fte_percentage": 35.0,
                "start_date": now - timedelta(days=90),
                "end_date": None,
                "supervisor_name": None,
                "certification_verified": True,
                "training_completed": True,
                "delegation_log_entry": "DL-020",
                "allocated_by": "Clinical Ops Director",
                "notes": "Oncology specialist for LIBTAYO trial",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "STA-00000010",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "allocation_status": AllocationStatus.REQUESTED,
                "staff_name": "Thomas Garcia",
                "staff_role": StaffRole.STUDY_COORDINATOR,
                "fte_percentage": 100.0,
                "start_date": now + timedelta(days=14),
                "end_date": None,
                "supervisor_name": "Dr. Emily Watson",
                "certification_verified": False,
                "training_completed": False,
                "delegation_log_entry": None,
                "allocated_by": "Site Manager",
                "notes": "Requested for new site activation",
                "created_at": now - timedelta(days=7),
            },
            {
                "id": "STA-00000011",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "allocation_status": AllocationStatus.ALLOCATED,
                "staff_name": "Jennifer Liu",
                "staff_role": StaffRole.RESEARCH_NURSE,
                "fte_percentage": 80.0,
                "start_date": now - timedelta(days=80),
                "end_date": None,
                "supervisor_name": "Dr. Emily Watson",
                "certification_verified": True,
                "training_completed": True,
                "delegation_log_entry": "DL-021",
                "allocated_by": "Clinical Ops Director",
                "notes": None,
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "STA-00000012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "allocation_status": AllocationStatus.DENIED,
                "staff_name": "Robert Brown",
                "staff_role": StaffRole.SUB_INVESTIGATOR,
                "fte_percentage": 25.0,
                "start_date": now - timedelta(days=10),
                "end_date": None,
                "supervisor_name": "Dr. Emily Watson",
                "certification_verified": False,
                "training_completed": False,
                "delegation_log_entry": None,
                "allocated_by": "Clinical Ops Director",
                "notes": "Denied - conflict of interest with competing trial",
                "created_at": now - timedelta(days=15),
            },
        ]

        for s in staff_data:
            self._staff_allocations[s["id"]] = StaffAllocation(**s)

        # --- 12 Equipment Inventories (4 per trial) ---
        equipment_data = [
            {
                "id": "EQI-00000001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "equipment_status": EquipmentStatus.AVAILABLE,
                "equipment_name": "OCT Scanner",
                "equipment_type": "Imaging",
                "serial_number": "OCT-2024-0451",
                "manufacturer": "Heidelberg Engineering",
                "calibration_date": now - timedelta(days=30),
                "next_calibration_date": now + timedelta(days=150),
                "location": "Ophthalmology Suite A",
                "assigned_to_trial": True,
                "maintenance_contract": True,
                "acquisition_date": now - timedelta(days=365),
                "managed_by": "Biomedical Engineering",
                "notes": "Primary OCT for EYLEA endpoints",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "EQI-00000002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "equipment_status": EquipmentStatus.IN_USE,
                "equipment_name": "Fundus Camera",
                "equipment_type": "Imaging",
                "serial_number": "FC-2023-8823",
                "manufacturer": "Topcon",
                "calibration_date": now - timedelta(days=60),
                "next_calibration_date": now + timedelta(days=120),
                "location": "Ophthalmology Suite A",
                "assigned_to_trial": True,
                "maintenance_contract": True,
                "acquisition_date": now - timedelta(days=500),
                "managed_by": "Biomedical Engineering",
                "notes": None,
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "EQI-00000003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "equipment_status": EquipmentStatus.CALIBRATION_DUE,
                "equipment_name": "Visual Acuity Chart (ETDRS)",
                "equipment_type": "Assessment",
                "serial_number": "VA-2024-1102",
                "manufacturer": "Precision Vision",
                "calibration_date": now - timedelta(days=200),
                "next_calibration_date": now - timedelta(days=15),
                "location": "Exam Room 3",
                "assigned_to_trial": True,
                "maintenance_contract": False,
                "acquisition_date": now - timedelta(days=300),
                "managed_by": "Site Coordinator",
                "notes": "Calibration overdue - schedule immediately",
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "EQI-00000004",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "equipment_status": EquipmentStatus.MAINTENANCE,
                "equipment_name": "Refrigerated Storage Unit",
                "equipment_type": "Storage",
                "serial_number": "RSU-2023-5567",
                "manufacturer": "Thermo Fisher",
                "calibration_date": now - timedelta(days=45),
                "next_calibration_date": now + timedelta(days=135),
                "location": "Pharmacy Storage",
                "assigned_to_trial": True,
                "maintenance_contract": True,
                "acquisition_date": now - timedelta(days=400),
                "managed_by": "Pharmacy Director",
                "notes": "Compressor replacement in progress",
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "EQI-00000005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "equipment_status": EquipmentStatus.AVAILABLE,
                "equipment_name": "Spirometer",
                "equipment_type": "Respiratory",
                "serial_number": "SPR-2024-3301",
                "manufacturer": "NDD Medical",
                "calibration_date": now - timedelta(days=15),
                "next_calibration_date": now + timedelta(days=165),
                "location": "Pulmonary Function Lab",
                "assigned_to_trial": True,
                "maintenance_contract": True,
                "acquisition_date": now - timedelta(days=200),
                "managed_by": "Respiratory Department",
                "notes": None,
                "created_at": now - timedelta(days=140),
            },
            {
                "id": "EQI-00000006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "equipment_status": EquipmentStatus.IN_USE,
                "equipment_name": "SCORAD Assessment Kit",
                "equipment_type": "Dermatology",
                "serial_number": "SCK-2024-0078",
                "manufacturer": "DermaTech",
                "calibration_date": None,
                "next_calibration_date": None,
                "location": "Dermatology Clinic",
                "assigned_to_trial": True,
                "maintenance_contract": False,
                "acquisition_date": now - timedelta(days=150),
                "managed_by": "Study Coordinator",
                "notes": "Digital assessment tool",
                "created_at": now - timedelta(days=140),
            },
            {
                "id": "EQI-00000007",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "equipment_status": EquipmentStatus.ON_ORDER,
                "equipment_name": "Digital Dermatoscope",
                "equipment_type": "Imaging",
                "serial_number": None,
                "manufacturer": "FotoFinder",
                "calibration_date": None,
                "next_calibration_date": None,
                "location": None,
                "assigned_to_trial": False,
                "maintenance_contract": False,
                "acquisition_date": None,
                "managed_by": "Procurement",
                "notes": "On order - expected delivery in 3 weeks",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "EQI-00000008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "equipment_status": EquipmentStatus.DECOMMISSIONED,
                "equipment_name": "Peak Flow Meter (Old Model)",
                "equipment_type": "Respiratory",
                "serial_number": "PFM-2020-1234",
                "manufacturer": "Vitalograph",
                "calibration_date": now - timedelta(days=400),
                "next_calibration_date": None,
                "location": "Storage Room B",
                "assigned_to_trial": False,
                "maintenance_contract": False,
                "acquisition_date": now - timedelta(days=800),
                "managed_by": "Biomedical Engineering",
                "notes": "Decommissioned - replaced by newer spirometer",
                "created_at": now - timedelta(days=500),
            },
            {
                "id": "EQI-00000009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "equipment_status": EquipmentStatus.AVAILABLE,
                "equipment_name": "Infusion Pump",
                "equipment_type": "Infusion",
                "serial_number": "INF-2024-7701",
                "manufacturer": "Baxter",
                "calibration_date": now - timedelta(days=20),
                "next_calibration_date": now + timedelta(days=160),
                "location": "Infusion Center Bay 4",
                "assigned_to_trial": True,
                "maintenance_contract": True,
                "acquisition_date": now - timedelta(days=180),
                "managed_by": "Nursing Department",
                "notes": "Dedicated to LIBTAYO infusions",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "EQI-00000010",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "equipment_status": EquipmentStatus.IN_USE,
                "equipment_name": "CT Scanner (Shared)",
                "equipment_type": "Imaging",
                "serial_number": "CT-2022-9900",
                "manufacturer": "Siemens Healthineers",
                "calibration_date": now - timedelta(days=10),
                "next_calibration_date": now + timedelta(days=80),
                "location": "Radiology Department",
                "assigned_to_trial": False,
                "maintenance_contract": True,
                "acquisition_date": now - timedelta(days=700),
                "managed_by": "Radiology Department",
                "notes": "Shared resource - RECIST assessments",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "EQI-00000011",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "equipment_status": EquipmentStatus.AVAILABLE,
                "equipment_name": "ECG Machine",
                "equipment_type": "Cardiac",
                "serial_number": "ECG-2024-2200",
                "manufacturer": "GE Healthcare",
                "calibration_date": now - timedelta(days=25),
                "next_calibration_date": now + timedelta(days=155),
                "location": "Cardiology Suite",
                "assigned_to_trial": True,
                "maintenance_contract": True,
                "acquisition_date": now - timedelta(days=250),
                "managed_by": "Cardiology Department",
                "notes": None,
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "EQI-00000012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "equipment_status": EquipmentStatus.CALIBRATION_DUE,
                "equipment_name": "Blood Pressure Monitor",
                "equipment_type": "Vital Signs",
                "serial_number": "BPM-2023-4455",
                "manufacturer": "Omron",
                "calibration_date": now - timedelta(days=190),
                "next_calibration_date": now - timedelta(days=5),
                "location": "Exam Room 1",
                "assigned_to_trial": True,
                "maintenance_contract": False,
                "acquisition_date": now - timedelta(days=350),
                "managed_by": "Nursing Department",
                "notes": "Calibration overdue",
                "created_at": now - timedelta(days=90),
            },
        ]

        for e in equipment_data:
            self._equipment_inventories[e["id"]] = EquipmentInventory(**e)

        # --- 12 Capacity Assessments (4 per trial) ---
        capacity_data = [
            {
                "id": "CPA-00000001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "capacity_level": CapacityLevel.OPTIMAL,
                "assessment_date": now - timedelta(days=14),
                "max_subjects": 40,
                "current_subjects": 28,
                "available_staff_fte": 3.2,
                "required_staff_fte": 3.0,
                "available_exam_rooms": 3,
                "storage_capacity_adequate": True,
                "pharmacy_capacity_adequate": True,
                "assessed_by": "Site Qualification Team",
                "recommendations": "Site performing well within capacity",
                "next_assessment_date": now + timedelta(days=76),
                "notes": None,
                "created_at": now - timedelta(days=14),
            },
            {
                "id": "CPA-00000002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "capacity_level": CapacityLevel.NEAR_CAPACITY,
                "assessment_date": now - timedelta(days=10),
                "max_subjects": 25,
                "current_subjects": 22,
                "available_staff_fte": 2.0,
                "required_staff_fte": 2.5,
                "available_exam_rooms": 2,
                "storage_capacity_adequate": True,
                "pharmacy_capacity_adequate": False,
                "assessed_by": "Site Qualification Team",
                "recommendations": "Consider additional pharmacist FTE; pharmacy at limit",
                "next_assessment_date": now + timedelta(days=30),
                "notes": "Pharmacy storage upgrade planned",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "CPA-00000003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "capacity_level": CapacityLevel.OPTIMAL,
                "assessment_date": now - timedelta(days=100),
                "max_subjects": 40,
                "current_subjects": 15,
                "available_staff_fte": 3.0,
                "required_staff_fte": 2.5,
                "available_exam_rooms": 3,
                "storage_capacity_adequate": True,
                "pharmacy_capacity_adequate": True,
                "assessed_by": "Site Qualification Team",
                "recommendations": None,
                "next_assessment_date": now - timedelta(days=14),
                "notes": "Initial capacity assessment",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "CPA-00000004",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "capacity_level": CapacityLevel.UNDER_CAPACITY,
                "assessment_date": now - timedelta(days=90),
                "max_subjects": 25,
                "current_subjects": 5,
                "available_staff_fte": 2.5,
                "required_staff_fte": 1.5,
                "available_exam_rooms": 2,
                "storage_capacity_adequate": True,
                "pharmacy_capacity_adequate": True,
                "assessed_by": "Site Qualification Team",
                "recommendations": "Enrollment ramp-up phase - monitor weekly",
                "next_assessment_date": now - timedelta(days=10),
                "notes": None,
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "CPA-00000005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "capacity_level": CapacityLevel.AT_CAPACITY,
                "assessment_date": now - timedelta(days=7),
                "max_subjects": 30,
                "current_subjects": 30,
                "available_staff_fte": 2.5,
                "required_staff_fte": 3.0,
                "available_exam_rooms": 2,
                "storage_capacity_adequate": True,
                "pharmacy_capacity_adequate": True,
                "assessed_by": "Regional Monitor",
                "recommendations": "Stop enrollment; redistribute to SITE-104",
                "next_assessment_date": now + timedelta(days=14),
                "notes": "Site has reached enrollment cap",
                "created_at": now - timedelta(days=7),
            },
            {
                "id": "CPA-00000006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "capacity_level": CapacityLevel.OPTIMAL,
                "assessment_date": now - timedelta(days=5),
                "max_subjects": 35,
                "current_subjects": 18,
                "available_staff_fte": 3.5,
                "required_staff_fte": 2.8,
                "available_exam_rooms": 4,
                "storage_capacity_adequate": True,
                "pharmacy_capacity_adequate": True,
                "assessed_by": "Regional Monitor",
                "recommendations": "Good capacity to absorb overflow from SITE-103",
                "next_assessment_date": now + timedelta(days=60),
                "notes": None,
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "CPA-00000007",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "capacity_level": CapacityLevel.OPTIMAL,
                "assessment_date": now - timedelta(days=60),
                "max_subjects": 30,
                "current_subjects": 20,
                "available_staff_fte": 3.0,
                "required_staff_fte": 2.5,
                "available_exam_rooms": 2,
                "storage_capacity_adequate": True,
                "pharmacy_capacity_adequate": True,
                "assessed_by": "Regional Monitor",
                "recommendations": None,
                "next_assessment_date": now - timedelta(days=7),
                "notes": None,
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "CPA-00000008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "capacity_level": CapacityLevel.UNDER_CAPACITY,
                "assessment_date": now - timedelta(days=50),
                "max_subjects": 35,
                "current_subjects": 8,
                "available_staff_fte": 3.5,
                "required_staff_fte": 2.0,
                "available_exam_rooms": 4,
                "storage_capacity_adequate": True,
                "pharmacy_capacity_adequate": True,
                "assessed_by": "Regional Monitor",
                "recommendations": "Accelerate recruitment at this site",
                "next_assessment_date": now - timedelta(days=5),
                "notes": None,
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "CPA-00000009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "capacity_level": CapacityLevel.OVER_CAPACITY,
                "assessment_date": now - timedelta(days=3),
                "max_subjects": 20,
                "current_subjects": 24,
                "available_staff_fte": 1.8,
                "required_staff_fte": 3.0,
                "available_exam_rooms": 1,
                "storage_capacity_adequate": False,
                "pharmacy_capacity_adequate": False,
                "assessed_by": "Clinical Ops Director",
                "recommendations": "Urgent: reduce patient load; transfer 4 subjects to SITE-106",
                "next_assessment_date": now + timedelta(days=7),
                "notes": "Critical staffing shortage identified",
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "CPA-00000010",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "capacity_level": CapacityLevel.OPTIMAL,
                "assessment_date": now - timedelta(days=2),
                "max_subjects": 25,
                "current_subjects": 12,
                "available_staff_fte": 2.8,
                "required_staff_fte": 2.0,
                "available_exam_rooms": 3,
                "storage_capacity_adequate": True,
                "pharmacy_capacity_adequate": True,
                "assessed_by": "Clinical Ops Director",
                "recommendations": "Can accept additional subjects from SITE-105",
                "next_assessment_date": now + timedelta(days=45),
                "notes": None,
                "created_at": now - timedelta(days=2),
            },
            {
                "id": "CPA-00000011",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "capacity_level": CapacityLevel.NEAR_CAPACITY,
                "assessment_date": now - timedelta(days=45),
                "max_subjects": 20,
                "current_subjects": 18,
                "available_staff_fte": 2.2,
                "required_staff_fte": 2.5,
                "available_exam_rooms": 2,
                "storage_capacity_adequate": True,
                "pharmacy_capacity_adequate": True,
                "assessed_by": "Clinical Ops Director",
                "recommendations": "Approaching capacity; monitor enrollment",
                "next_assessment_date": now - timedelta(days=3),
                "notes": None,
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "CPA-00000012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "capacity_level": CapacityLevel.UNKNOWN,
                "assessment_date": now - timedelta(days=80),
                "max_subjects": 25,
                "current_subjects": 0,
                "available_staff_fte": 0.0,
                "required_staff_fte": 2.0,
                "available_exam_rooms": 3,
                "storage_capacity_adequate": True,
                "pharmacy_capacity_adequate": True,
                "assessed_by": "Site Qualification Team",
                "recommendations": "Pre-activation assessment; staff not yet assigned",
                "next_assessment_date": now - timedelta(days=2),
                "notes": "Initial site qualification visit",
                "created_at": now - timedelta(days=80),
            },
        ]

        for c in capacity_data:
            self._capacity_assessments[c["id"]] = CapacityAssessment(**c)

        # --- 12 Workload Distributions (4 per trial) ---
        week_start = now - timedelta(days=now.weekday())  # This Monday
        workload_data = [
            {
                "id": "WLD-00000001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "workload_priority": WorkloadPriority.HIGH,
                "task_category": "Subject Visits",
                "assigned_staff": "Rachel Kim",
                "estimated_hours": 32.0,
                "actual_hours": 28.5,
                "week_start_date": week_start - timedelta(weeks=1),
                "week_end_date": week_start - timedelta(days=1),
                "tasks_assigned": 12,
                "tasks_completed": 11,
                "overdue_tasks": 1,
                "utilization_pct": 89.1,
                "distributed_by": "Dr. Sarah Chen",
                "notes": None,
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "WLD-00000002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "workload_priority": WorkloadPriority.MEDIUM,
                "task_category": "Data Entry & Queries",
                "assigned_staff": "Maria Santos",
                "estimated_hours": 20.0,
                "actual_hours": 22.0,
                "week_start_date": week_start - timedelta(weeks=1),
                "week_end_date": week_start - timedelta(days=1),
                "tasks_assigned": 45,
                "tasks_completed": 40,
                "overdue_tasks": 5,
                "utilization_pct": 88.9,
                "distributed_by": "Dr. Sarah Chen",
                "notes": "Query backlog from previous week",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "WLD-00000003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "workload_priority": WorkloadPriority.CRITICAL,
                "task_category": "SAE Documentation",
                "assigned_staff": "Dr. James Park",
                "estimated_hours": 8.0,
                "actual_hours": 12.0,
                "week_start_date": week_start,
                "week_end_date": week_start + timedelta(days=6),
                "tasks_assigned": 3,
                "tasks_completed": 1,
                "overdue_tasks": 0,
                "utilization_pct": 66.7,
                "distributed_by": "Dr. Sarah Chen",
                "notes": "Priority SAE follow-up required",
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "WLD-00000004",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "workload_priority": WorkloadPriority.LOW,
                "task_category": "Training & Compliance",
                "assigned_staff": "Maria Santos",
                "estimated_hours": 4.0,
                "actual_hours": 0.0,
                "week_start_date": week_start,
                "week_end_date": week_start + timedelta(days=6),
                "tasks_assigned": 2,
                "tasks_completed": 0,
                "overdue_tasks": 0,
                "utilization_pct": 0.0,
                "distributed_by": "Site Manager",
                "notes": "GCP refresher training scheduled",
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "WLD-00000005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "workload_priority": WorkloadPriority.HIGH,
                "task_category": "Subject Visits",
                "assigned_staff": "Dr. Michael Torres",
                "estimated_hours": 24.0,
                "actual_hours": 26.0,
                "week_start_date": week_start - timedelta(weeks=1),
                "week_end_date": week_start - timedelta(days=1),
                "tasks_assigned": 10,
                "tasks_completed": 10,
                "overdue_tasks": 0,
                "utilization_pct": 92.3,
                "distributed_by": "Regional Director",
                "notes": None,
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "WLD-00000006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "workload_priority": WorkloadPriority.MEDIUM,
                "task_category": "IP Management",
                "assigned_staff": "Lisa Anderson",
                "estimated_hours": 10.0,
                "actual_hours": 9.5,
                "week_start_date": week_start - timedelta(weeks=1),
                "week_end_date": week_start - timedelta(days=1),
                "tasks_assigned": 8,
                "tasks_completed": 7,
                "overdue_tasks": 1,
                "utilization_pct": 87.5,
                "distributed_by": "Regional Director",
                "notes": "One accountability log pending",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "WLD-00000007",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "workload_priority": WorkloadPriority.DEFERRED,
                "task_category": "Site File Maintenance",
                "assigned_staff": "Kevin Wright",
                "estimated_hours": 6.0,
                "actual_hours": 0.0,
                "week_start_date": week_start,
                "week_end_date": week_start + timedelta(days=6),
                "tasks_assigned": 5,
                "tasks_completed": 0,
                "overdue_tasks": 0,
                "utilization_pct": 0.0,
                "distributed_by": "Site Manager",
                "notes": "Deferred until EDC training complete",
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "WLD-00000008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "workload_priority": WorkloadPriority.ROUTINE,
                "task_category": "Monitoring Preparation",
                "assigned_staff": "Lisa Anderson",
                "estimated_hours": 8.0,
                "actual_hours": 4.0,
                "week_start_date": week_start,
                "week_end_date": week_start + timedelta(days=6),
                "tasks_assigned": 6,
                "tasks_completed": 3,
                "overdue_tasks": 0,
                "utilization_pct": 50.0,
                "distributed_by": "Regional Director",
                "notes": "Preparing for interim monitoring visit",
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "WLD-00000009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "workload_priority": WorkloadPriority.CRITICAL,
                "task_category": "Infusion Administration",
                "assigned_staff": "Jennifer Liu",
                "estimated_hours": 36.0,
                "actual_hours": 38.0,
                "week_start_date": week_start - timedelta(weeks=1),
                "week_end_date": week_start - timedelta(days=1),
                "tasks_assigned": 15,
                "tasks_completed": 14,
                "overdue_tasks": 1,
                "utilization_pct": 93.3,
                "distributed_by": "Dr. Emily Watson",
                "notes": "Overtime required due to staffing shortage",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "WLD-00000010",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "workload_priority": WorkloadPriority.HIGH,
                "task_category": "Tumor Assessments",
                "assigned_staff": "Dr. Emily Watson",
                "estimated_hours": 16.0,
                "actual_hours": 18.0,
                "week_start_date": week_start,
                "week_end_date": week_start + timedelta(days=6),
                "tasks_assigned": 8,
                "tasks_completed": 3,
                "overdue_tasks": 0,
                "utilization_pct": 37.5,
                "distributed_by": "Clinical Ops Director",
                "notes": "RECIST evaluations for Week 12 visits",
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "WLD-00000011",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "workload_priority": WorkloadPriority.MEDIUM,
                "task_category": "Subject Visits",
                "assigned_staff": "Thomas Garcia",
                "estimated_hours": 20.0,
                "actual_hours": 15.0,
                "week_start_date": week_start - timedelta(weeks=1),
                "week_end_date": week_start - timedelta(days=1),
                "tasks_assigned": 8,
                "tasks_completed": 6,
                "overdue_tasks": 2,
                "utilization_pct": 75.0,
                "distributed_by": "Dr. Emily Watson",
                "notes": None,
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "WLD-00000012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "workload_priority": WorkloadPriority.LOW,
                "task_category": "Regulatory Document Updates",
                "assigned_staff": "Thomas Garcia",
                "estimated_hours": 4.0,
                "actual_hours": 2.0,
                "week_start_date": week_start,
                "week_end_date": week_start + timedelta(days=6),
                "tasks_assigned": 3,
                "tasks_completed": 1,
                "overdue_tasks": 0,
                "utilization_pct": 33.3,
                "distributed_by": "Dr. Emily Watson",
                "notes": "IRB annual report update",
                "created_at": now - timedelta(days=3),
            },
        ]

        for w in workload_data:
            self._workload_distributions[w["id"]] = WorkloadDistribution(**w)

    # ------------------------------------------------------------------
    # Staff Allocations
    # ------------------------------------------------------------------

    def list_staff_allocations(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[StaffAllocation]:
        """List staff allocations with optional trial filter."""
        with self._lock:
            result = list(self._staff_allocations.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]

        return sorted(result, key=lambda s: s.created_at, reverse=True)

    def get_staff_allocation(self, allocation_id: str) -> StaffAllocation | None:
        """Get a single staff allocation by ID."""
        with self._lock:
            return self._staff_allocations.get(allocation_id)

    def create_staff_allocation(self, payload: StaffAllocationCreate) -> StaffAllocation:
        """Create a new staff allocation."""
        now = datetime.now(timezone.utc)
        alloc_id = f"STA-{uuid4().hex[:8].upper()}"
        allocation = StaffAllocation(
            id=alloc_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            allocation_status=payload.allocation_status,
            staff_name=payload.staff_name,
            staff_role=payload.staff_role,
            fte_percentage=payload.fte_percentage,
            start_date=payload.start_date,
            end_date=None,
            supervisor_name=None,
            certification_verified=False,
            training_completed=False,
            delegation_log_entry=None,
            allocated_by=payload.allocated_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._staff_allocations[alloc_id] = allocation
        logger.info("Created staff allocation %s: %s", alloc_id, payload.staff_name)
        return allocation

    def update_staff_allocation(
        self, allocation_id: str, payload: StaffAllocationUpdate
    ) -> StaffAllocation | None:
        """Update an existing staff allocation."""
        with self._lock:
            existing = self._staff_allocations.get(allocation_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = StaffAllocation(**data)
            self._staff_allocations[allocation_id] = updated
        return updated

    def delete_staff_allocation(self, allocation_id: str) -> bool:
        """Delete a staff allocation. Returns True if deleted."""
        with self._lock:
            if allocation_id in self._staff_allocations:
                del self._staff_allocations[allocation_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Equipment Inventories
    # ------------------------------------------------------------------

    def list_equipment_inventories(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[EquipmentInventory]:
        """List equipment inventories with optional trial filter."""
        with self._lock:
            result = list(self._equipment_inventories.values())

        if trial_id is not None:
            result = [e for e in result if e.trial_id == trial_id]

        return sorted(result, key=lambda e: e.created_at, reverse=True)

    def get_equipment_inventory(self, equipment_id: str) -> EquipmentInventory | None:
        """Get a single equipment inventory by ID."""
        with self._lock:
            return self._equipment_inventories.get(equipment_id)

    def create_equipment_inventory(self, payload: EquipmentInventoryCreate) -> EquipmentInventory:
        """Create a new equipment inventory entry."""
        now = datetime.now(timezone.utc)
        equip_id = f"EQI-{uuid4().hex[:8].upper()}"
        equipment = EquipmentInventory(
            id=equip_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            equipment_status=payload.equipment_status,
            equipment_name=payload.equipment_name,
            equipment_type=payload.equipment_type,
            serial_number=None,
            manufacturer=None,
            calibration_date=None,
            next_calibration_date=None,
            location=None,
            assigned_to_trial=False,
            maintenance_contract=False,
            acquisition_date=None,
            managed_by=payload.managed_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._equipment_inventories[equip_id] = equipment
        logger.info("Created equipment inventory %s: %s", equip_id, payload.equipment_name)
        return equipment

    def update_equipment_inventory(
        self, equipment_id: str, payload: EquipmentInventoryUpdate
    ) -> EquipmentInventory | None:
        """Update an existing equipment inventory entry."""
        with self._lock:
            existing = self._equipment_inventories.get(equipment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = EquipmentInventory(**data)
            self._equipment_inventories[equipment_id] = updated
        return updated

    def delete_equipment_inventory(self, equipment_id: str) -> bool:
        """Delete an equipment inventory entry. Returns True if deleted."""
        with self._lock:
            if equipment_id in self._equipment_inventories:
                del self._equipment_inventories[equipment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Capacity Assessments
    # ------------------------------------------------------------------

    def list_capacity_assessments(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[CapacityAssessment]:
        """List capacity assessments with optional trial filter."""
        with self._lock:
            result = list(self._capacity_assessments.values())

        if trial_id is not None:
            result = [c for c in result if c.trial_id == trial_id]

        return sorted(result, key=lambda c: c.assessment_date, reverse=True)

    def get_capacity_assessment(self, assessment_id: str) -> CapacityAssessment | None:
        """Get a single capacity assessment by ID."""
        with self._lock:
            return self._capacity_assessments.get(assessment_id)

    def create_capacity_assessment(self, payload: CapacityAssessmentCreate) -> CapacityAssessment:
        """Create a new capacity assessment."""
        now = datetime.now(timezone.utc)
        assess_id = f"CPA-{uuid4().hex[:8].upper()}"
        assessment = CapacityAssessment(
            id=assess_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            capacity_level=payload.capacity_level,
            assessment_date=payload.assessment_date,
            max_subjects=payload.max_subjects,
            current_subjects=0,
            available_staff_fte=0.0,
            required_staff_fte=0.0,
            available_exam_rooms=0,
            storage_capacity_adequate=True,
            pharmacy_capacity_adequate=True,
            assessed_by=payload.assessed_by,
            recommendations=None,
            next_assessment_date=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._capacity_assessments[assess_id] = assessment
        logger.info("Created capacity assessment %s for site %s", assess_id, payload.site_id)
        return assessment

    def update_capacity_assessment(
        self, assessment_id: str, payload: CapacityAssessmentUpdate
    ) -> CapacityAssessment | None:
        """Update an existing capacity assessment."""
        with self._lock:
            existing = self._capacity_assessments.get(assessment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CapacityAssessment(**data)
            self._capacity_assessments[assessment_id] = updated
        return updated

    def delete_capacity_assessment(self, assessment_id: str) -> bool:
        """Delete a capacity assessment. Returns True if deleted."""
        with self._lock:
            if assessment_id in self._capacity_assessments:
                del self._capacity_assessments[assessment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Workload Distributions
    # ------------------------------------------------------------------

    def list_workload_distributions(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[WorkloadDistribution]:
        """List workload distributions with optional trial filter."""
        with self._lock:
            result = list(self._workload_distributions.values())

        if trial_id is not None:
            result = [w for w in result if w.trial_id == trial_id]

        return sorted(result, key=lambda w: w.week_start_date, reverse=True)

    def get_workload_distribution(self, workload_id: str) -> WorkloadDistribution | None:
        """Get a single workload distribution by ID."""
        with self._lock:
            return self._workload_distributions.get(workload_id)

    def create_workload_distribution(
        self, payload: WorkloadDistributionCreate
    ) -> WorkloadDistribution:
        """Create a new workload distribution entry."""
        now = datetime.now(timezone.utc)
        wl_id = f"WLD-{uuid4().hex[:8].upper()}"
        workload = WorkloadDistribution(
            id=wl_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            workload_priority=payload.workload_priority,
            task_category=payload.task_category,
            assigned_staff=payload.assigned_staff,
            estimated_hours=0.0,
            actual_hours=0.0,
            week_start_date=payload.week_start_date,
            week_end_date=payload.week_end_date,
            tasks_assigned=0,
            tasks_completed=0,
            overdue_tasks=0,
            utilization_pct=0.0,
            distributed_by=payload.distributed_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._workload_distributions[wl_id] = workload
        logger.info("Created workload distribution %s: %s", wl_id, payload.task_category)
        return workload

    def update_workload_distribution(
        self, workload_id: str, payload: WorkloadDistributionUpdate
    ) -> WorkloadDistribution | None:
        """Update an existing workload distribution entry."""
        with self._lock:
            existing = self._workload_distributions.get(workload_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = WorkloadDistribution(**data)
            self._workload_distributions[workload_id] = updated
        return updated

    def delete_workload_distribution(self, workload_id: str) -> bool:
        """Delete a workload distribution entry. Returns True if deleted."""
        with self._lock:
            if workload_id in self._workload_distributions:
                del self._workload_distributions[workload_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> SiteResourcePlanningMetrics:
        """Compute aggregated site resource planning metrics."""
        with self._lock:
            staff = list(self._staff_allocations.values())
            equipment = list(self._equipment_inventories.values())
            assessments = list(self._capacity_assessments.values())
            workloads = list(self._workload_distributions.values())

        if trial_id is not None:
            staff = [s for s in staff if s.trial_id == trial_id]
            equipment = [e for e in equipment if e.trial_id == trial_id]
            assessments = [c for c in assessments if c.trial_id == trial_id]
            workloads = [w for w in workloads if w.trial_id == trial_id]

        # Allocations by status
        allocations_by_status: dict[str, int] = {}
        for s in staff:
            key = s.allocation_status.value
            allocations_by_status[key] = allocations_by_status.get(key, 0) + 1

        # Allocations by role
        allocations_by_role: dict[str, int] = {}
        for s in staff:
            key = s.staff_role.value
            allocations_by_role[key] = allocations_by_role.get(key, 0) + 1

        # Average FTE utilization
        fte_values = [s.fte_percentage for s in staff]
        avg_fte = round(sum(fte_values) / max(1, len(fte_values)), 1)

        # Equipment by status
        equipment_by_status: dict[str, int] = {}
        for e in equipment:
            key = e.equipment_status.value
            equipment_by_status[key] = equipment_by_status.get(key, 0) + 1

        # Assessments by level
        assessments_by_level: dict[str, int] = {}
        for c in assessments:
            key = c.capacity_level.value
            assessments_by_level[key] = assessments_by_level.get(key, 0) + 1

        # Workloads by priority
        workloads_by_priority: dict[str, int] = {}
        for w in workloads:
            key = w.workload_priority.value
            workloads_by_priority[key] = workloads_by_priority.get(key, 0) + 1

        # Average utilization percentage
        util_values = [w.utilization_pct for w in workloads]
        avg_util = round(sum(util_values) / max(1, len(util_values)), 1)

        return SiteResourcePlanningMetrics(
            total_staff_allocations=len(staff),
            allocations_by_status=allocations_by_status,
            allocations_by_role=allocations_by_role,
            avg_fte_utilization=avg_fte,
            total_equipment=len(equipment),
            equipment_by_status=equipment_by_status,
            total_capacity_assessments=len(assessments),
            assessments_by_level=assessments_by_level,
            total_workload_entries=len(workloads),
            workloads_by_priority=workloads_by_priority,
            avg_utilization_pct=avg_util,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: SiteResourcePlanningService | None = None
_instance_lock = threading.Lock()


def get_site_resource_planning_service() -> SiteResourcePlanningService:
    """Return the singleton SiteResourcePlanningService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = SiteResourcePlanningService()
    return _instance


def reset_site_resource_planning_service() -> SiteResourcePlanningService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = SiteResourcePlanningService()
    return _instance
