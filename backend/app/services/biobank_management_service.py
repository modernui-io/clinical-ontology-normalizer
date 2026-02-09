"""Biospecimen & Biobank Management Service (CLINICAL-17).

Manages biospecimen collection, aliquot tracking with chain of custody,
biorepository storage with capacity monitoring, consent scope validation,
quality scoring based on freeze-thaw cycles and processing time, specimen
genealogy (parent -> child aliquots), and shipment manifests.

Usage:
    from app.services.biobank_management_service import (
        get_biobank_service,
    )

    svc = get_biobank_service()
    specimens = svc.list_specimens()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.biobank_management import (
    Aliquot,
    AliquotCreate,
    AliquotReserve,
    AliquotStatus,
    AliquotUpdate,
    BiobankMetrics,
    Biorepository,
    BiorepositoryCreate,
    BiorepositoryType,
    BiorepositoryUpdate,
    BiospecimenCollection,
    ConsentCreate,
    ConsentRecord,
    ConsentScope,
    ConsentWithdraw,
    ShipmentCreate,
    ShipmentManifest,
    ShipmentReceive,
    SpecimenCreate,
    SpecimenGenealogy,
    SpecimenType,
    SpecimenUpdate,
    StorageCapacityAlert,
    StorageType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

# Storage capacity alert thresholds
CAPACITY_WARNING_PCT = 80.0
CAPACITY_CRITICAL_PCT = 95.0

# Quality score deductions
FREEZE_THAW_PENALTY = 5.0  # Points lost per freeze-thaw cycle
PROCESSING_TIME_PENALTY_THRESHOLD = 120  # Minutes before penalty kicks in
PROCESSING_TIME_PENALTY_PER_HOUR = 10.0  # Points lost per hour over threshold


class BiobankService:
    """In-memory Biospecimen & Biobank Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._specimens: dict[str, BiospecimenCollection] = {}
        self._aliquots: dict[str, Aliquot] = {}
        self._repositories: dict[str, Biorepository] = {}
        self._consents: dict[str, ConsentRecord] = {}
        self._shipments: dict[str, ShipmentManifest] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic biobank data across clinical trial sites."""
        now = datetime.now(timezone.utc)

        # --- 4 Biorepositories ---
        repos_data = [
            {
                "id": "REPO-001",
                "name": "Central Biobank Facility",
                "type": BiorepositoryType.CENTRAL,
                "location": "Tarrytown, NY",
                "capacity_total": 50000,
                "capacity_used": 38500,
                "temperature_monitored": True,
                "backup_power": True,
                "certifications": ["CAP", "CLIA", "ISO 20387"],
            },
            {
                "id": "REPO-002",
                "name": "Southeast Regional Repository",
                "type": BiorepositoryType.REGIONAL,
                "location": "Research Triangle Park, NC",
                "capacity_total": 20000,
                "capacity_used": 16800,
                "temperature_monitored": True,
                "backup_power": True,
                "certifications": ["CAP", "CLIA"],
            },
            {
                "id": "REPO-003",
                "name": "West Coast Regional Repository",
                "type": BiorepositoryType.REGIONAL,
                "location": "San Francisco, CA",
                "capacity_total": 15000,
                "capacity_used": 9200,
                "temperature_monitored": True,
                "backup_power": True,
                "certifications": ["CAP", "CLIA", "ISO 20387"],
            },
            {
                "id": "REPO-004",
                "name": "Memorial Hermann Site Lab",
                "type": BiorepositoryType.SITE_LEVEL,
                "location": "Houston, TX",
                "capacity_total": 5000,
                "capacity_used": 4200,
                "temperature_monitored": True,
                "backup_power": False,
                "certifications": ["CLIA"],
            },
        ]

        for r in repos_data:
            self._repositories[r["id"]] = Biorepository(**r)

        # --- 30 Specimens from 15 patients across 3 trials ---
        patients = [f"PAT-{i:03d}" for i in range(1, 16)]
        sites = ["SITE-101", "SITE-102", "SITE-103", "SITE-104", "SITE-105"]
        trials = [EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL]
        visits = ["Screening", "Visit 1", "Visit 2", "Week 4", "Week 8", "Week 12"]
        collectors = [
            "Dr. Sarah Chen", "Nurse Maria Lopez", "Tech James Wilson",
            "Dr. Robert Kim", "Nurse Emily Davis",
        ]

        specimen_types_cycle = [
            SpecimenType.SERUM, SpecimenType.PLASMA, SpecimenType.WHOLE_BLOOD,
            SpecimenType.PBMC, SpecimenType.DNA, SpecimenType.RNA,
            SpecimenType.TISSUE_FFPE, SpecimenType.TISSUE_FROZEN,
            SpecimenType.URINE, SpecimenType.CSF, SpecimenType.SALIVA,
            SpecimenType.STOOL,
        ]

        specimens_data: list[dict] = []
        for i in range(30):
            patient_idx = i % 15
            spec_type = specimen_types_cycle[i % len(specimen_types_cycle)]
            parent_id = None
            if i >= 20:
                parent_id = f"SPEC-{(i - 20) + 1:04d}"

            specimens_data.append({
                "id": f"SPEC-{i + 1:04d}",
                "patient_id": patients[patient_idx],
                "trial_id": trials[i % 3],
                "site_id": sites[i % 5],
                "specimen_type": spec_type,
                "collection_date": now - timedelta(days=180 - i * 5),
                "collection_time": f"{8 + (i % 10):02d}:{(i * 7) % 60:02d}",
                "collector": collectors[i % len(collectors)],
                "protocol_visit": visits[i % len(visits)],
                "fasting_status": i % 3 == 0,
                "processing_time_minutes": 30 + (i * 7) % 150,
                "parent_specimen_id": parent_id,
            })

        for s in specimens_data:
            self._specimens[s["id"]] = BiospecimenCollection(**s)

        # --- 80 Aliquots with barcodes, storage positions ---
        storage_types_cycle = [
            StorageType.MINUS80_FREEZER, StorageType.MINUS80_FREEZER,
            StorageType.MINUS20_FREEZER, StorageType.LIQUID_NITROGEN,
            StorageType.REFRIGERATOR_4C,
        ]
        freezers = ["FRZ-80-A01", "FRZ-80-A02", "FRZ-80-B01", "FRZ-20-A01", "LN2-T01"]
        repos_for_aliquots = ["REPO-001", "REPO-001", "REPO-002", "REPO-003", "REPO-004"]

        statuses_cycle = [
            AliquotStatus.AVAILABLE, AliquotStatus.AVAILABLE, AliquotStatus.AVAILABLE,
            AliquotStatus.RESERVED, AliquotStatus.SHIPPED, AliquotStatus.USED,
            AliquotStatus.DEPLETED, AliquotStatus.QC_FAILED,
        ]

        for i in range(80):
            spec_idx = i % 30
            specimen_id = f"SPEC-{spec_idx + 1:04d}"
            aliquot_num = (i // 30) + 1
            rack_num = (i // 20) + 1
            box_num = (i // 10) % 5 + 1
            row = chr(65 + (i % 8))
            col = (i % 12) + 1
            freeze_thaw = (i % 6)
            status = statuses_cycle[i % len(statuses_cycle)]

            concentration = None
            spec_type = specimens_data[spec_idx]["specimen_type"]
            if spec_type in (SpecimenType.DNA, SpecimenType.RNA):
                concentration = round(50.0 + (i * 3.7) % 200.0, 1)

            quality = self._calculate_quality_score(
                freeze_thaw,
                specimens_data[spec_idx]["processing_time_minutes"],
            )

            repo_id = repos_for_aliquots[i % len(repos_for_aliquots)]

            aliquot = Aliquot(
                id=f"ALQ-{i + 1:04d}",
                specimen_id=specimen_id,
                aliquot_number=aliquot_num,
                barcode=f"BB-{uuid4().hex[:8].upper()}",
                volume_ul=round(100.0 + (i * 13.3) % 900.0, 1),
                concentration=concentration,
                storage_type=storage_types_cycle[i % len(storage_types_cycle)],
                freezer_id=freezers[i % len(freezers)],
                rack=f"R{rack_num:02d}",
                box=f"B{box_num:02d}",
                position=f"{row}{col:02d}",
                status=status,
                freeze_thaw_cycles=freeze_thaw,
                quality_score=quality,
            )
            self._aliquots[aliquot.id] = aliquot

        # --- 25 Consent Records ---
        for i in range(25):
            patient_idx = i % 15
            specimen_idx = i % 30
            scopes: list[ConsentScope] = [ConsentScope.PRIMARY_STUDY]
            if i % 2 == 0:
                scopes.append(ConsentScope.FUTURE_RESEARCH)
            if i % 3 == 0:
                scopes.append(ConsentScope.GENETIC_ANALYSIS)
            if i % 5 == 0:
                scopes.append(ConsentScope.INDEFINITE_STORAGE)
            if i % 7 == 0:
                scopes.append(ConsentScope.COMMERCIAL_USE)

            withdrawal_date = None
            if i in (5, 18):  # 2 consents withdrawn
                withdrawal_date = now - timedelta(days=30 - i)

            consent = ConsentRecord(
                id=f"CNS-{i + 1:04d}",
                patient_id=patients[patient_idx],
                specimen_id=f"SPEC-{specimen_idx + 1:04d}",
                scope=scopes,
                consent_date=now - timedelta(days=200 - i * 7),
                withdrawal_date=withdrawal_date,
                consent_version=f"v{1 + i // 10}.{i % 10}",
            )
            self._consents[consent.id] = consent

        # --- 5 Shipment Manifests ---
        shipments_data = [
            {
                "id": "SHP-001",
                "from_repository": "REPO-004",
                "to_repository": "REPO-001",
                "aliquot_ids": ["ALQ-0001", "ALQ-0002", "ALQ-0003"],
                "shipped_date": now - timedelta(days=60),
                "received_date": now - timedelta(days=58),
                "temperature_log": [-78.5, -79.0, -78.8, -79.2, -78.6],
                "condition_on_arrival": "Good - all vials intact, temperature maintained",
            },
            {
                "id": "SHP-002",
                "from_repository": "REPO-002",
                "to_repository": "REPO-001",
                "aliquot_ids": ["ALQ-0010", "ALQ-0011", "ALQ-0012", "ALQ-0013"],
                "shipped_date": now - timedelta(days=30),
                "received_date": now - timedelta(days=28),
                "temperature_log": [-79.1, -79.3, -78.9, -79.0],
                "condition_on_arrival": "Good - no issues observed",
            },
            {
                "id": "SHP-003",
                "from_repository": "REPO-001",
                "to_repository": "REPO-003",
                "aliquot_ids": ["ALQ-0020", "ALQ-0021"],
                "shipped_date": now - timedelta(days=14),
                "received_date": now - timedelta(days=12),
                "temperature_log": [-78.0, -77.5, -76.8, -77.2, -78.1],
                "condition_on_arrival": "Acceptable - minor temperature excursion noted",
            },
            {
                "id": "SHP-004",
                "from_repository": "REPO-004",
                "to_repository": "REPO-002",
                "aliquot_ids": ["ALQ-0030", "ALQ-0031", "ALQ-0032", "ALQ-0033", "ALQ-0034"],
                "shipped_date": now - timedelta(days=3),
                "received_date": None,
                "temperature_log": [],
                "condition_on_arrival": None,
            },
            {
                "id": "SHP-005",
                "from_repository": "REPO-003",
                "to_repository": "REPO-001",
                "aliquot_ids": ["ALQ-0040", "ALQ-0041", "ALQ-0042"],
                "shipped_date": now - timedelta(days=1),
                "received_date": None,
                "temperature_log": [],
                "condition_on_arrival": None,
            },
        ]

        for sh in shipments_data:
            self._shipments[sh["id"]] = ShipmentManifest(**sh)

    # ------------------------------------------------------------------
    # Quality Scoring
    # ------------------------------------------------------------------

    @staticmethod
    def _calculate_quality_score(
        freeze_thaw_cycles: int,
        processing_time_minutes: int,
    ) -> float:
        """Calculate quality score based on freeze-thaw cycles and processing time.

        Starts at 100 and deducts:
        - 5 points per freeze-thaw cycle
        - 10 points per hour of processing time over 2 hours
        """
        score = 100.0

        # Freeze-thaw penalty
        score -= freeze_thaw_cycles * FREEZE_THAW_PENALTY

        # Processing time penalty
        if processing_time_minutes > PROCESSING_TIME_PENALTY_THRESHOLD:
            excess_hours = (processing_time_minutes - PROCESSING_TIME_PENALTY_THRESHOLD) / 60.0
            score -= excess_hours * PROCESSING_TIME_PENALTY_PER_HOUR

        return round(max(0.0, min(100.0, score)), 1)

    # ------------------------------------------------------------------
    # Specimen Management
    # ------------------------------------------------------------------

    def list_specimens(
        self,
        *,
        patient_id: str | None = None,
        trial_id: str | None = None,
        site_id: str | None = None,
        specimen_type: SpecimenType | None = None,
    ) -> list[BiospecimenCollection]:
        """List specimens with optional filters."""
        with self._lock:
            result = list(self._specimens.values())

        if patient_id is not None:
            result = [s for s in result if s.patient_id == patient_id]
        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if site_id is not None:
            result = [s for s in result if s.site_id == site_id]
        if specimen_type is not None:
            result = [s for s in result if s.specimen_type == specimen_type]

        return sorted(result, key=lambda s: s.collection_date, reverse=True)

    def get_specimen(self, specimen_id: str) -> BiospecimenCollection | None:
        """Get a single specimen by ID."""
        with self._lock:
            return self._specimens.get(specimen_id)

    def create_specimen(self, payload: SpecimenCreate) -> BiospecimenCollection:
        """Register a new biospecimen collection."""
        spec_id = f"SPEC-{uuid4().hex[:8].upper()}"
        specimen = BiospecimenCollection(
            id=spec_id,
            **payload.model_dump(),
        )
        with self._lock:
            self._specimens[spec_id] = specimen
        logger.info("Created specimen %s for patient %s", spec_id, payload.patient_id)
        return specimen

    def update_specimen(
        self, specimen_id: str, payload: SpecimenUpdate
    ) -> BiospecimenCollection | None:
        """Update a specimen record."""
        with self._lock:
            existing = self._specimens.get(specimen_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = BiospecimenCollection(**data)
            self._specimens[specimen_id] = updated
        return updated

    def delete_specimen(self, specimen_id: str) -> bool:
        """Delete a specimen. Returns True if deleted."""
        with self._lock:
            if specimen_id in self._specimens:
                del self._specimens[specimen_id]
                return True
            return False

    def get_specimen_genealogy(self, specimen_id: str) -> SpecimenGenealogy | None:
        """Get the genealogy tree for a specimen (parent -> aliquots + children)."""
        with self._lock:
            specimen = self._specimens.get(specimen_id)
            if specimen is None:
                return None

            aliquots = [
                a for a in self._aliquots.values()
                if a.specimen_id == specimen_id
            ]

            children = [
                s for s in self._specimens.values()
                if s.parent_specimen_id == specimen_id
            ]

        return SpecimenGenealogy(
            specimen=specimen,
            aliquots=sorted(aliquots, key=lambda a: a.aliquot_number),
            child_specimens=sorted(children, key=lambda s: s.collection_date),
        )

    # ------------------------------------------------------------------
    # Aliquot Management
    # ------------------------------------------------------------------

    def list_aliquots(
        self,
        *,
        specimen_id: str | None = None,
        status: AliquotStatus | None = None,
        storage_type: StorageType | None = None,
        repository_id: str | None = None,
    ) -> list[Aliquot]:
        """List aliquots with optional filters."""
        with self._lock:
            result = list(self._aliquots.values())

        if specimen_id is not None:
            result = [a for a in result if a.specimen_id == specimen_id]
        if status is not None:
            result = [a for a in result if a.status == status]
        if storage_type is not None:
            result = [a for a in result if a.storage_type == storage_type]
        if repository_id is not None:
            # Filter by freezer_id prefix matching repo
            repo = self._repositories.get(repository_id)
            if repo:
                repo_freezers = self._get_repo_freezers(repository_id)
                result = [a for a in result if a.freezer_id in repo_freezers]

        return sorted(result, key=lambda a: a.id)

    def get_aliquot(self, aliquot_id: str) -> Aliquot | None:
        """Get a single aliquot by ID."""
        with self._lock:
            return self._aliquots.get(aliquot_id)

    def create_aliquot(self, payload: AliquotCreate) -> Aliquot:
        """Create an aliquot from a specimen."""
        with self._lock:
            specimen = self._specimens.get(payload.specimen_id)
            if specimen is None:
                raise ValueError(f"Specimen '{payload.specimen_id}' not found")

            # Determine aliquot number
            existing = [
                a for a in self._aliquots.values()
                if a.specimen_id == payload.specimen_id
            ]
            aliquot_num = len(existing) + 1

        alq_id = f"ALQ-{uuid4().hex[:8].upper()}"
        barcode = f"BB-{uuid4().hex[:8].upper()}"

        quality = self._calculate_quality_score(0, specimen.processing_time_minutes)

        aliquot = Aliquot(
            id=alq_id,
            specimen_id=payload.specimen_id,
            aliquot_number=aliquot_num,
            barcode=barcode,
            volume_ul=payload.volume_ul,
            concentration=payload.concentration,
            storage_type=payload.storage_type,
            freezer_id=payload.freezer_id,
            rack=payload.rack,
            box=payload.box,
            position=payload.position,
            status=AliquotStatus.AVAILABLE,
            freeze_thaw_cycles=0,
            quality_score=quality,
        )

        with self._lock:
            self._aliquots[alq_id] = aliquot
        logger.info(
            "Created aliquot %s from specimen %s", alq_id, payload.specimen_id
        )
        return aliquot

    def update_aliquot(self, aliquot_id: str, payload: AliquotUpdate) -> Aliquot | None:
        """Update an aliquot."""
        with self._lock:
            existing = self._aliquots.get(aliquot_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Recalculate quality if freeze-thaw cycles changed
            if "freeze_thaw_cycles" in updates:
                specimen = self._specimens.get(existing.specimen_id)
                proc_time = specimen.processing_time_minutes if specimen else 0
                data["quality_score"] = self._calculate_quality_score(
                    updates["freeze_thaw_cycles"], proc_time
                )

            data.update(updates)
            updated = Aliquot(**data)
            self._aliquots[aliquot_id] = updated
        return updated

    def reserve_aliquot(
        self, aliquot_id: str, payload: AliquotReserve
    ) -> Aliquot | None:
        """Reserve an aliquot after validating consent scopes.

        Returns None if aliquot not found.
        Raises ValueError if consent validation fails or aliquot not available.
        """
        with self._lock:
            aliquot = self._aliquots.get(aliquot_id)
            if aliquot is None:
                return None

            if aliquot.status != AliquotStatus.AVAILABLE:
                raise ValueError(
                    f"Aliquot '{aliquot_id}' is not available (status: {aliquot.status.value})"
                )

            # Find the specimen to get the patient
            specimen = self._specimens.get(aliquot.specimen_id)
            if specimen is None:
                raise ValueError(f"Specimen '{aliquot.specimen_id}' not found")

            # Validate consent scopes
            patient_consents = [
                c for c in self._consents.values()
                if c.patient_id == specimen.patient_id
                and c.specimen_id == aliquot.specimen_id
                and c.withdrawal_date is None  # Active consent only
            ]

            if not patient_consents:
                raise ValueError(
                    f"No active consent found for patient '{specimen.patient_id}' "
                    f"specimen '{aliquot.specimen_id}'"
                )

            # Check all required scopes are covered
            granted_scopes: set[ConsentScope] = set()
            for consent in patient_consents:
                granted_scopes.update(consent.scope)

            missing_scopes = set(payload.required_scopes) - granted_scopes
            if missing_scopes:
                raise ValueError(
                    f"Missing consent scopes: {[s.value for s in missing_scopes]}. "
                    f"Granted: {[s.value for s in granted_scopes]}"
                )

            # Reserve the aliquot
            data = aliquot.model_dump()
            data["status"] = AliquotStatus.RESERVED
            updated = Aliquot(**data)
            self._aliquots[aliquot_id] = updated

        logger.info(
            "Reserved aliquot %s for purpose: %s", aliquot_id, payload.purpose
        )
        return updated

    def record_freeze_thaw(self, aliquot_id: str) -> Aliquot | None:
        """Record a freeze-thaw cycle for an aliquot and update quality."""
        with self._lock:
            aliquot = self._aliquots.get(aliquot_id)
            if aliquot is None:
                return None

            data = aliquot.model_dump()
            data["freeze_thaw_cycles"] = aliquot.freeze_thaw_cycles + 1

            specimen = self._specimens.get(aliquot.specimen_id)
            proc_time = specimen.processing_time_minutes if specimen else 0
            data["quality_score"] = self._calculate_quality_score(
                data["freeze_thaw_cycles"], proc_time
            )

            updated = Aliquot(**data)
            self._aliquots[aliquot_id] = updated

        logger.info(
            "Recorded freeze-thaw for aliquot %s (cycle %d, quality %.1f)",
            aliquot_id, updated.freeze_thaw_cycles, updated.quality_score,
        )
        return updated

    def _get_repo_freezers(self, repository_id: str) -> set[str]:
        """Get freezer IDs associated with a repository (simplified mapping)."""
        repo_freezer_map = {
            "REPO-001": {"FRZ-80-A01", "FRZ-80-A02", "FRZ-80-B01"},
            "REPO-002": {"FRZ-20-A01"},
            "REPO-003": {"LN2-T01"},
            "REPO-004": {"FRZ-80-A01"},
        }
        return repo_freezer_map.get(repository_id, set())

    # ------------------------------------------------------------------
    # Biorepository Management
    # ------------------------------------------------------------------

    def list_repositories(
        self,
        *,
        repo_type: BiorepositoryType | None = None,
    ) -> list[Biorepository]:
        """List biorepositories with optional type filter."""
        with self._lock:
            result = list(self._repositories.values())

        if repo_type is not None:
            result = [r for r in result if r.type == repo_type]

        return sorted(result, key=lambda r: r.id)

    def get_repository(self, repository_id: str) -> Biorepository | None:
        """Get a single biorepository by ID."""
        with self._lock:
            return self._repositories.get(repository_id)

    def create_repository(self, payload: BiorepositoryCreate) -> Biorepository:
        """Register a new biorepository."""
        repo_id = f"REPO-{uuid4().hex[:8].upper()}"
        repo = Biorepository(
            id=repo_id,
            capacity_used=0,
            **payload.model_dump(),
        )
        with self._lock:
            self._repositories[repo_id] = repo
        logger.info("Created biorepository %s: %s", repo_id, payload.name)
        return repo

    def update_repository(
        self, repository_id: str, payload: BiorepositoryUpdate
    ) -> Biorepository | None:
        """Update a biorepository."""
        with self._lock:
            existing = self._repositories.get(repository_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = Biorepository(**data)
            self._repositories[repository_id] = updated
        return updated

    def delete_repository(self, repository_id: str) -> bool:
        """Delete a biorepository. Returns True if deleted."""
        with self._lock:
            if repository_id in self._repositories:
                del self._repositories[repository_id]
                return True
            return False

    def get_storage_alerts(self) -> list[StorageCapacityAlert]:
        """Get storage capacity alerts for repositories at 80%+ utilization."""
        alerts: list[StorageCapacityAlert] = []

        with self._lock:
            repos = list(self._repositories.values())

        for repo in repos:
            if repo.capacity_total == 0:
                continue

            utilization = (repo.capacity_used / repo.capacity_total) * 100.0

            if utilization >= CAPACITY_WARNING_PCT:
                alert_level = (
                    "critical" if utilization >= CAPACITY_CRITICAL_PCT else "warning"
                )
                alerts.append(StorageCapacityAlert(
                    repository_id=repo.id,
                    repository_name=repo.name,
                    utilization_pct=round(utilization, 1),
                    capacity_total=repo.capacity_total,
                    capacity_used=repo.capacity_used,
                    capacity_remaining=repo.capacity_total - repo.capacity_used,
                    alert_level=alert_level,
                ))

        return sorted(alerts, key=lambda a: a.utilization_pct, reverse=True)

    # ------------------------------------------------------------------
    # Consent Management
    # ------------------------------------------------------------------

    def list_consents(
        self,
        *,
        patient_id: str | None = None,
        specimen_id: str | None = None,
        active_only: bool = False,
    ) -> list[ConsentRecord]:
        """List consent records with optional filters."""
        with self._lock:
            result = list(self._consents.values())

        if patient_id is not None:
            result = [c for c in result if c.patient_id == patient_id]
        if specimen_id is not None:
            result = [c for c in result if c.specimen_id == specimen_id]
        if active_only:
            result = [c for c in result if c.withdrawal_date is None]

        return sorted(result, key=lambda c: c.consent_date, reverse=True)

    def get_consent(self, consent_id: str) -> ConsentRecord | None:
        """Get a single consent record by ID."""
        with self._lock:
            return self._consents.get(consent_id)

    def create_consent(self, payload: ConsentCreate) -> ConsentRecord:
        """Create a new consent record."""
        consent_id = f"CNS-{uuid4().hex[:8].upper()}"
        consent = ConsentRecord(
            id=consent_id,
            withdrawal_date=None,
            **payload.model_dump(),
        )
        with self._lock:
            self._consents[consent_id] = consent
        logger.info(
            "Created consent %s for patient %s specimen %s",
            consent_id, payload.patient_id, payload.specimen_id,
        )
        return consent

    def withdraw_consent(
        self, consent_id: str, payload: ConsentWithdraw
    ) -> ConsentRecord | None:
        """Withdraw a consent record."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._consents.get(consent_id)
            if existing is None:
                return None

            if existing.withdrawal_date is not None:
                raise ValueError(f"Consent '{consent_id}' is already withdrawn")

            data = existing.model_dump()
            data["withdrawal_date"] = now
            updated = ConsentRecord(**data)
            self._consents[consent_id] = updated

        logger.info(
            "Withdrew consent %s (reason: %s)", consent_id, payload.reason
        )
        return updated

    def validate_consent_scopes(
        self,
        patient_id: str,
        specimen_id: str,
        required_scopes: list[ConsentScope],
    ) -> dict:
        """Validate whether a patient has required consent scopes for a specimen.

        Returns a dict with 'valid' bool and details.
        """
        with self._lock:
            consents = [
                c for c in self._consents.values()
                if c.patient_id == patient_id
                and c.specimen_id == specimen_id
                and c.withdrawal_date is None
            ]

        if not consents:
            return {
                "valid": False,
                "reason": "No active consent found",
                "granted_scopes": [],
                "missing_scopes": [s.value for s in required_scopes],
            }

        granted: set[ConsentScope] = set()
        for c in consents:
            granted.update(c.scope)

        missing = set(required_scopes) - granted
        return {
            "valid": len(missing) == 0,
            "reason": "All required scopes granted" if not missing else "Missing required scopes",
            "granted_scopes": [s.value for s in granted],
            "missing_scopes": [s.value for s in missing],
        }

    # ------------------------------------------------------------------
    # Shipment Management
    # ------------------------------------------------------------------

    def list_shipments(
        self,
        *,
        in_transit_only: bool = False,
    ) -> list[ShipmentManifest]:
        """List shipments with optional in-transit filter."""
        with self._lock:
            result = list(self._shipments.values())

        if in_transit_only:
            result = [s for s in result if s.received_date is None]

        return sorted(result, key=lambda s: s.shipped_date, reverse=True)

    def get_shipment(self, shipment_id: str) -> ShipmentManifest | None:
        """Get a single shipment by ID."""
        with self._lock:
            return self._shipments.get(shipment_id)

    def create_shipment(self, payload: ShipmentCreate) -> ShipmentManifest:
        """Create a new shipment manifest and mark aliquots as shipped."""
        now = datetime.now(timezone.utc)
        ship_id = f"SHP-{uuid4().hex[:8].upper()}"

        with self._lock:
            # Validate repositories exist
            if payload.from_repository not in self._repositories:
                raise ValueError(
                    f"Source repository '{payload.from_repository}' not found"
                )
            if payload.to_repository not in self._repositories:
                raise ValueError(
                    f"Destination repository '{payload.to_repository}' not found"
                )

            # Validate and update aliquot statuses
            for alq_id in payload.aliquot_ids:
                aliquot = self._aliquots.get(alq_id)
                if aliquot is None:
                    raise ValueError(f"Aliquot '{alq_id}' not found")
                if aliquot.status not in (
                    AliquotStatus.AVAILABLE, AliquotStatus.RESERVED
                ):
                    raise ValueError(
                        f"Aliquot '{alq_id}' cannot be shipped "
                        f"(status: {aliquot.status.value})"
                    )

            # Mark aliquots as shipped
            for alq_id in payload.aliquot_ids:
                aliquot = self._aliquots[alq_id]
                data = aliquot.model_dump()
                data["status"] = AliquotStatus.SHIPPED
                self._aliquots[alq_id] = Aliquot(**data)

            shipment = ShipmentManifest(
                id=ship_id,
                from_repository=payload.from_repository,
                to_repository=payload.to_repository,
                aliquot_ids=payload.aliquot_ids,
                shipped_date=now,
                received_date=None,
                temperature_log=[],
                condition_on_arrival=None,
            )
            self._shipments[ship_id] = shipment

        logger.info(
            "Created shipment %s: %d aliquots from %s to %s",
            ship_id, len(payload.aliquot_ids),
            payload.from_repository, payload.to_repository,
        )
        return shipment

    def receive_shipment(
        self, shipment_id: str, payload: ShipmentReceive
    ) -> ShipmentManifest | None:
        """Mark a shipment as received."""
        now = datetime.now(timezone.utc)

        with self._lock:
            existing = self._shipments.get(shipment_id)
            if existing is None:
                return None

            if existing.received_date is not None:
                raise ValueError(f"Shipment '{shipment_id}' is already received")

            data = existing.model_dump()
            data["received_date"] = now
            data["condition_on_arrival"] = payload.condition_on_arrival
            data["temperature_log"] = payload.temperature_log

            # Mark aliquots as available at new location
            for alq_id in existing.aliquot_ids:
                aliquot = self._aliquots.get(alq_id)
                if aliquot and aliquot.status == AliquotStatus.SHIPPED:
                    alq_data = aliquot.model_dump()
                    alq_data["status"] = AliquotStatus.AVAILABLE
                    self._aliquots[alq_id] = Aliquot(**alq_data)

            updated = ShipmentManifest(**data)
            self._shipments[shipment_id] = updated

        logger.info(
            "Received shipment %s: condition=%s",
            shipment_id, payload.condition_on_arrival,
        )
        return updated

    # ------------------------------------------------------------------
    # Metrics & Dashboard
    # ------------------------------------------------------------------

    def get_metrics(self) -> BiobankMetrics:
        """Compute aggregated biobank operational metrics."""
        with self._lock:
            specimens = list(self._specimens.values())
            aliquots = list(self._aliquots.values())
            repos = list(self._repositories.values())
            consents = list(self._consents.values())
            shipments = list(self._shipments.values())

        # Aliquots by status
        status_counts: dict[str, int] = {}
        total_quality = 0.0
        for a in aliquots:
            key = a.status.value
            status_counts[key] = status_counts.get(key, 0) + 1
            total_quality += a.quality_score

        avg_quality = round(total_quality / max(1, len(aliquots)), 1)

        # Storage utilization
        total_capacity = sum(r.capacity_total for r in repos)
        total_used = sum(r.capacity_used for r in repos)
        utilization = round(
            (total_used / max(1, total_capacity)) * 100.0, 1
        )

        # Consent withdrawal rate
        total_consents = len(consents)
        withdrawn_consents = sum(1 for c in consents if c.withdrawal_date is not None)
        withdrawal_rate = round(
            (withdrawn_consents / max(1, total_consents)) * 100.0, 1
        )

        # Shipments in transit
        in_transit = sum(1 for s in shipments if s.received_date is None)

        return BiobankMetrics(
            total_specimens=len(specimens),
            total_aliquots=len(aliquots),
            aliquots_by_status=status_counts,
            storage_utilization_pct=utilization,
            avg_quality_score=avg_quality,
            consent_withdrawal_rate=withdrawal_rate,
            shipments_in_transit=in_transit,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: BiobankService | None = None
_instance_lock = threading.Lock()


def get_biobank_service() -> BiobankService:
    """Return the singleton BiobankService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = BiobankService()
    return _instance


def reset_biobank_service() -> BiobankService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = BiobankService()
    return _instance
