"""Canonical Meditech-to-OpenEHR contract and lineage helpers.

The contract is intentionally explicit and deterministic for auditability:
- contract ID, version, and effective date
- source-to-target field mapping and identifier fields
- code-system normalization policy
- deterministic contract fingerprint
- lineage step builder for OpenEHR import pipeline
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.connectors.concept_mappings import normalize_code_system

MEDITECH_OPENEHR_CONTRACT_ID = "P0-018-MEDITECH-OPENEHR-CNX"
MEDITECH_OPENEHR_CONTRACT_VERSION = "1.0.0"
MEDITECH_OPENEHR_CONTRACT_EFFECTIVE_DATE = "2026-02-16"

MEDITECH_TO_OPENEHR_MAP: dict[str, str] = {
    "problem": "EVALUATION.problem_diagnosis.v1",
    "condition": "EVALUATION.problem_diagnosis.v1",
    "medication": "INSTRUCTION.medication_order.v3",
    "drug": "INSTRUCTION.medication_order.v3",
    "vital_sign": "OBSERVATION.blood_pressure.v2",
    "measurement": "OBSERVATION.laboratory_test_result.v1",
    "procedure": "ACTION.procedure.v1",
    "allergy": "EVALUATION.adverse_reaction_risk.v1",
}

MEDITECH_CODE_SYSTEM_NORMALIZATION: dict[str, str] = {
    "SNOMED CT": "SNOMED",
    "SCT": "SNOMED",
    "SNM": "SNOMED",
    "SNOMEDCT": "SNOMED",
    "SNOMEDCT-US": "SNOMED",
    "RXN": "RxNorm",
    "RXNORM": "RxNorm",
    "RXNORM-ND": "RxNorm",
    "LOINC": "LOINC",
    "LOCAL": "LOCAL",
}

MEDITECH_SOURCE_IDENTIFIERS = {
    "patient_id": "meditech_patient_id",
    "encounter_id": "meditech_encounter_id",
    "visit_id": "meditech_visit_id",
    "record_id": "meditech_record_id",
}

MEDITECH_EXCEPTION_POLICY = {
    "missing_required_field": "reject_entry_with_lineage",
    "missing_code_system": "normalize_or_mark_unknown",
    "unsupported_code_system": "route_to_manual_review",
}

MEDITECH_CANONICAL_CONTRACT: dict[str, Any] = {
    "contract_id": MEDITECH_OPENEHR_CONTRACT_ID,
    "contract_version": MEDITECH_OPENEHR_CONTRACT_VERSION,
    "effective_date": MEDITECH_OPENEHR_CONTRACT_EFFECTIVE_DATE,
    "source_profile": "meditech-raw",
    "target_profile": "openehr-canonical",
    "source_vendor": "meditech",
    "target_archetype_map": MEDITECH_TO_OPENEHR_MAP,
    "code_system_policy": {
        "normalization_aliases": MEDITECH_CODE_SYSTEM_NORMALIZATION,
        "default": "UNKNOWN",
        "exception_strategy": MEDITECH_EXCEPTION_POLICY,
    },
    "required_identifiers": list(MEDITECH_SOURCE_IDENTIFIERS.values()),
}



def _contract_signature(contract: dict[str, Any]) -> str:
    """Return a stable sha256 hash for a canonical contract payload."""
    payload = json.dumps(contract, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


MEDITECH_CANONICAL_CONTRACT_SIGNATURE = _contract_signature(MEDITECH_CANONICAL_CONTRACT)

_MEDITECH_SOURCE_HINTS = {
    "meditech",
    "meditech-au",
    "meditech-australia",
    "meditech_australia",
    "meditech australia",
    "meditech-aus",
    "meditech_aus",
    "meditech aus",
}


def normalize_meditech_code_system(code_system: str | None) -> str | None:
    """Normalize Meditech source terminology identifiers to standard vocab names."""
    if not code_system:
        return None

    normalized = MEDITECH_CODE_SYSTEM_NORMALIZATION.get(code_system, None)
    if normalized:
        return normalized

    fallback = normalize_code_system(code_system)
    return MEDITECH_CODE_SYSTEM_NORMALIZATION.get(fallback.upper(), fallback)


def _as_source_system(raw_system: str | None) -> str | None:
    if not raw_system:
        return None

    normalized = raw_system.strip().lower()
    if normalized in _MEDITECH_SOURCE_HINTS:
        return "meditech"

    if normalized.startswith("meditech"):
        return "meditech"

    if normalized == "meditech\n":
        return "meditech"

    return None


def _extract_source_system(
    source_metadata: dict[str, Any] | None,
    composition: dict[str, Any] | None = None,
    entry: dict[str, Any] | None = None,
) -> str | None:
    if source_metadata:
        for key in ("source_system", "source_vendor", "vendor", "vendor_id", "source"):
            resolved = _as_source_system(source_metadata.get(key))
            if resolved:
                return resolved

    if composition:
        meta = composition.get("_meta", {}) or {}
        for key in ("source_system", "source_vendor", "vendor", "source"):
            resolved = _as_source_system(meta.get(key))
            if resolved:
                return resolved

    if entry:
        for key in ("source_system", "source_vendor", "vendor", "source"):
            resolved = _as_source_system(entry.get(key))
            if resolved:
                return resolved

    if composition and composition.get("source"):
        return _as_source_system(composition.get("source"))

    return None


def _extract_record_id(
    source_metadata: dict[str, Any] | None,
    composition: dict[str, Any] | None = None,
    entry: dict[str, Any] | None = None,
) -> str | None:
    def _extract(container: dict[str, Any] | None, keys: list[str]) -> str | None:
        if not container:
            return None
        for key in keys:
            value = container.get(key)
            if value:
                return str(value)

        uid = container.get("uid")
        if isinstance(uid, dict):
            value = uid.get("value")
            if value:
                return str(value)

        return None

    value = _extract(source_metadata, ["source_record_id", "record_id", "entry_id", "id"])
    if value:
        return value

    value = _extract(entry, ["source_record_id", "record_id", "entry_id", "uid"])
    if value:
        return value

    return _extract(composition, ["source_record_id", "record_id", "composition_id", "uid"])


def build_meditech_contract_lineage_step(
    *,
    source_metadata: dict[str, Any] | None,
    composition: dict[str, Any] | None = None,
    entry: dict[str, Any] | None = None,
    archetype_key: str | None = None,
) -> dict[str, Any] | None:
    """Build deterministic contract lineage step if source is Meditech."""
    source_system = _extract_source_system(
        source_metadata=source_metadata,
        composition=composition,
        entry=entry,
    )
    if source_system != "meditech":
        return None

    source_record_id = _extract_record_id(
        source_metadata=source_metadata,
        composition=composition,
        entry=entry,
    )

    step: dict[str, Any] = {
        "step": "meditech_to_openehr_adapter",
        "contract_id": MEDITECH_OPENEHR_CONTRACT_ID,
        "contract_version": MEDITECH_OPENEHR_CONTRACT_VERSION,
        "contract_effective_date": MEDITECH_OPENEHR_CONTRACT_EFFECTIVE_DATE,
        "contract_signature": MEDITECH_CANONICAL_CONTRACT_SIGNATURE,
        "source_system": source_system,
        "source_record_type": source_metadata.get("source_record_type") if source_metadata else None,
        "source_record_id": source_record_id,
        "archetype": archetype_key,
        "mapping_profile": MEDITECH_CANONICAL_CONTRACT["target_profile"],
    }

    if source_metadata and isinstance(source_metadata.get("encounter_id"), str):
        step["source_encounter_id"] = source_metadata["encounter_id"]

    if source_metadata and source_metadata.get("pipeline_id"):
        step["pipeline_id"] = source_metadata["pipeline_id"]

    return {key: value for key, value in step.items() if value is not None}


__all__ = [
    "MEDITECH_CANONICAL_CONTRACT",
    "MEDITECH_CANONICAL_CONTRACT_SIGNATURE",
    "MEDITECH_CODE_SYSTEM_NORMALIZATION",
    "MEDITECH_EXCEPTION_POLICY",
    "MEDITECH_OPENEHR_CONTRACT_EFFECTIVE_DATE",
    "MEDITECH_OPENEHR_CONTRACT_ID",
    "MEDITECH_OPENEHR_CONTRACT_VERSION",
    "MEDITECH_SOURCE_IDENTIFIERS",
    "MEDITECH_TO_OPENEHR_MAP",
    "build_meditech_contract_lineage_step",
    "normalize_meditech_code_system",
]
