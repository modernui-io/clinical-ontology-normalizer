"""OpenEHR Reconciliation Service — dry-run imports, round-trip validation, fingerprinting.

P0-019: Provides programmatic validation of OpenEHR import/export integrity
without persisting data (dry-run mode) and deterministic content hashing
for round-trip reconciliation.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinical_fact import ClinicalFact
from app.services.openehr_exporter import OpenEHRExporterService
from app.services.openehr_import import OpenEHRImportService

logger = logging.getLogger(__name__)


@dataclass
class DryRunResult:
    """Result of a dry-run import — stats collected without persisting."""

    success: bool
    patient_id: str | None = None
    conditions: int = 0
    medications: int = 0
    measurements: int = 0
    procedures: int = 0
    allergies: int = 0
    nodes: int = 0
    edges: int = 0
    skipped: int = 0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "patient_id": self.patient_id,
            "conditions": self.conditions,
            "medications": self.medications,
            "measurements": self.measurements,
            "procedures": self.procedures,
            "allergies": self.allergies,
            "nodes": self.nodes,
            "edges": self.edges,
            "skipped": self.skipped,
            "error": self.error,
        }


@dataclass
class ReconciliationReport:
    """Result of a round-trip reconciliation check."""

    patient_id: str
    match: bool
    import_fingerprint: str
    export_reimport_fingerprint: str
    import_row_counts: dict[str, int] = field(default_factory=dict)
    reimport_row_counts: dict[str, int] = field(default_factory=dict)
    mismatches: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "patient_id": self.patient_id,
            "match": self.match,
            "import_fingerprint": self.import_fingerprint,
            "export_reimport_fingerprint": self.export_reimport_fingerprint,
            "import_row_counts": self.import_row_counts,
            "reimport_row_counts": self.reimport_row_counts,
            "mismatches": self.mismatches,
        }


def compute_import_fingerprint(stats: dict[str, Any], facts: list[Any]) -> str:
    """Compute a deterministic SHA-256 hash over sorted fact domains/concept_names.

    The fingerprint is independent of DB-generated fields (id, created_at) so
    that two imports producing the same clinical content yield the same hash.
    """
    entries: list[str] = []
    for f in facts:
        if isinstance(f, dict):
            domain = f.get("domain", "")
            name = f.get("concept_name", "")
        else:
            domain = getattr(f, "domain", "")
            name = getattr(f, "concept_name", "")
        if hasattr(domain, "value"):
            domain = domain.value
        entries.append(f"{domain}::{name}")

    entries.sort()

    row_summary = "|".join(
        f"{k}={stats.get(k, 0)}"
        for k in sorted(["conditions", "medications", "measurements", "procedures", "allergies"])
    )
    payload = row_summary + "||" + "||".join(entries)
    return hashlib.sha256(payload.encode()).hexdigest()


class OpenEHRReconciliationService:
    """Orchestrates dry-run imports, round-trip validation, and hash-based diffing."""

    async def dry_run_import(
        self,
        session: AsyncSession,
        composition: dict[str, Any],
        patient_id: str,
        source_metadata: dict[str, Any] | None = None,
    ) -> DryRunResult:
        """Run the full import pipeline inside a savepoint, collect stats, then roll back.

        Returns stats + validation report without persisting anything.
        """
        savepoint = await session.begin_nested()
        try:
            service = OpenEHRImportService()
            stats = await service.import_composition(
                session, composition, patient_id, source_metadata=source_metadata,
            )
            if not stats.get("success"):
                await savepoint.rollback()
                return DryRunResult(
                    success=False,
                    patient_id=patient_id,
                    error=stats.get("error", "Import failed"),
                )

            result = DryRunResult(
                success=True,
                patient_id=patient_id,
                conditions=stats.get("conditions", 0),
                medications=stats.get("medications", 0),
                measurements=stats.get("measurements", 0),
                procedures=stats.get("procedures", 0),
                allergies=stats.get("allergies", 0),
                nodes=stats.get("nodes", 0),
                edges=stats.get("edges", 0),
                skipped=stats.get("skipped", 0),
            )
        except Exception as e:
            logger.error(f"Dry-run import failed: {e}")
            try:
                await savepoint.rollback()
            except Exception:
                pass
            return DryRunResult(success=False, patient_id=patient_id, error=str(e))
        else:
            await savepoint.rollback()

        return result

    async def reconcile_round_trip(
        self,
        session: AsyncSession,
        patient_id: str,
    ) -> ReconciliationReport:
        """Import facts, export them back to COMPOSITION, re-import the export,
        and compare row counts + content hashes.
        """
        # Step 1: Read existing facts for the patient
        result = await session.execute(
            select(ClinicalFact).where(
                ClinicalFact.patient_id == patient_id,
                ClinicalFact.deleted_at.is_(None),
            )
        )
        facts = list(result.scalars().all())

        if not facts:
            return ReconciliationReport(
                patient_id=patient_id,
                match=False,
                import_fingerprint="",
                export_reimport_fingerprint="",
                mismatches=["No facts found for patient"],
            )

        # Step 2: Compute fingerprint of current facts
        import_counts = _count_domains(facts)
        import_fp = compute_import_fingerprint(import_counts, facts)

        # Step 3: Export facts to a COMPOSITION
        exporter = OpenEHRExporterService()
        composition = exporter.export_facts(facts, patient_id)

        # Step 4: Re-import the exported COMPOSITION via dry-run
        reimport_result = await self.dry_run_import(session, composition, f"{patient_id}__recon")

        if not reimport_result.success:
            return ReconciliationReport(
                patient_id=patient_id,
                match=False,
                import_fingerprint=import_fp,
                export_reimport_fingerprint="",
                mismatches=[f"Re-import failed: {reimport_result.error}"],
            )

        # Step 5: Build fake fact list from reimport stats for fingerprinting
        reimport_counts = {
            "conditions": reimport_result.conditions,
            "medications": reimport_result.medications,
            "measurements": reimport_result.measurements,
            "procedures": reimport_result.procedures,
            "allergies": reimport_result.allergies,
        }

        # Reconstruct concept names from the composition content for fingerprinting
        reimport_facts = _extract_concept_list_from_composition(composition)
        reimport_fp = compute_import_fingerprint(reimport_counts, reimport_facts)

        # Step 6: Compare
        mismatches: list[str] = []
        for key in ["conditions", "medications", "measurements", "procedures", "allergies"]:
            orig = import_counts.get(key, 0)
            re = reimport_counts.get(key, 0)
            if orig != re:
                mismatches.append(f"{key}: original={orig}, reimport={re}")

        if import_fp != reimport_fp:
            mismatches.append(f"Fingerprint mismatch: {import_fp[:16]}... vs {reimport_fp[:16]}...")

        return ReconciliationReport(
            patient_id=patient_id,
            match=len(mismatches) == 0,
            import_fingerprint=import_fp,
            export_reimport_fingerprint=reimport_fp,
            import_row_counts=import_counts,
            reimport_row_counts=reimport_counts,
            mismatches=mismatches,
        )


def _count_domains(facts: list[Any]) -> dict[str, int]:
    """Count facts by domain."""
    counts: dict[str, int] = {
        "conditions": 0,
        "medications": 0,
        "measurements": 0,
        "procedures": 0,
        "allergies": 0,
    }
    for f in facts:
        domain = getattr(f, "domain", None)
        if domain is None:
            continue
        d = domain.value if hasattr(domain, "value") else str(domain)
        if d == "condition":
            counts["conditions"] += 1
        elif d == "drug":
            counts["medications"] += 1
        elif d == "measurement":
            counts["measurements"] += 1
        elif d == "procedure":
            counts["procedures"] += 1
        elif d == "observation":
            counts["allergies"] += 1
    return counts


def _extract_concept_list_from_composition(composition: dict[str, Any]) -> list[dict[str, str]]:
    """Extract a list of {domain, concept_name} from a COMPOSITION for fingerprinting.

    This mirrors what the import service would produce, giving us a basis to
    compute a fingerprint without actually re-importing.
    """
    from app.services.openehr_import import ARCHETYPE_DOMAIN_MAP, _get_archetype_key

    facts: list[dict[str, str]] = []
    for entry in composition.get("content", []):
        node_id = entry.get("archetype_node_id", "")
        archetype_key = _get_archetype_key(node_id)
        if not archetype_key or archetype_key not in ARCHETYPE_DOMAIN_MAP:
            continue

        domain, _, _ = ARCHETYPE_DOMAIN_MAP[archetype_key]
        domain_str = domain.value

        # Extract concept names based on domain
        if domain_str == "condition":
            items = entry.get("data", {}).get("items", [])
            for item in items:
                if item.get("name", {}).get("value") == "Problem/Diagnosis name":
                    name = item.get("value", {}).get("value", "")
                    if name:
                        facts.append({"domain": domain_str, "concept_name": name})
        elif domain_str == "drug":
            activities = entry.get("activities", [])
            if activities:
                items = activities[0].get("description", {}).get("items", [])
                for item in items:
                    if item.get("name", {}).get("value") == "Medication item":
                        name = item.get("value", {}).get("value", "")
                        if name:
                            facts.append({"domain": domain_str, "concept_name": name})
        elif domain_str == "measurement":
            data = entry.get("data", {})
            events = data.get("events", [])
            if events:
                items = events[0].get("data", {}).get("items", [])
                if "blood_pressure" in archetype_key:
                    # Handle both formats:
                    # 1. Original import: items named "Systolic" / "Diastolic"
                    # 2. Export round-trip: items named "Blood Pressure - Systolic" etc.
                    for item in items:
                        item_name = item.get("name", {}).get("value", "")
                        if item_name in ("Systolic", "Diastolic"):
                            facts.append({
                                "domain": domain_str,
                                "concept_name": f"Blood Pressure - {item_name}",
                            })
                        elif item_name.startswith("Blood Pressure - "):
                            facts.append({
                                "domain": domain_str,
                                "concept_name": item_name,
                            })
                else:
                    for item in items:
                        name = item.get("name", {}).get("value", "")
                        if name:
                            facts.append({"domain": domain_str, "concept_name": name})
                            break
        elif domain_str == "procedure":
            items = entry.get("description", {}).get("items", [])
            for item in items:
                if item.get("name", {}).get("value") == "Procedure name":
                    name = item.get("value", {}).get("value", "")
                    if name:
                        facts.append({"domain": domain_str, "concept_name": name})
        elif domain_str == "observation":
            items = entry.get("data", {}).get("items", [])
            for item in items:
                if item.get("name", {}).get("value") == "Substance":
                    name = item.get("value", {}).get("value", "")
                    if name:
                        facts.append({"domain": domain_str, "concept_name": name})

    return facts
