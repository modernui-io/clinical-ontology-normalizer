"""Pipeline version tracking for reproducibility.

CSO-1: Same input document must produce identical extraction + mapping
results across pipeline versions. This module captures the versions of
all components in the NLP / mapping pipeline so that every ClinicalFact
can be traced back to the exact configuration that produced it.

The version info is assembled lazily and cached for the lifetime of the
process.  It is stamped onto every ClinicalFact at creation time by the
fact builder.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Bump this whenever the pipeline logic changes in a way that could
# alter extraction or mapping output for the same input document.
PIPELINE_VERSION = "1.0.0"

# Component versions -- updated when the underlying rules, models, or
# vocabularies are changed.
NLP_RULE_BASED_VERSION = "1.0.0"
NLP_ENSEMBLE_VERSION = "1.0.0"
EXTRACTION_PIPELINE_VERSION = "1.0.0"
MAPPING_SERVICE_VERSION = "1.0.0"


@dataclass(frozen=True)
class PipelineVersionInfo:
    """Immutable snapshot of every component version in the pipeline.

    Fields
    ------
    pipeline_version : str
        Overall pipeline semver.  Bump the patch for config-only changes,
        minor for new extraction rules, major for breaking changes.
    nlp_engine_version : str
        Which NLP variant is active and its version.  Format is
        ``"<variant>/<semver>"`` e.g. ``"rule_based/1.0.0"``.
    extraction_pipeline_version : str
        Version of the multi-stage extraction pipeline.
    mapping_service_version : str
        Version of the OMOP mapping service.
    omop_vocabulary_version : str
        Vocabulary release identifier (e.g. ``"v5.0 2024-01-01"``).
        Populated at runtime from the vocabulary service when available.
    extraction_config_hash : str
        SHA-256 hex digest of the serialised extraction configuration so
        that two identical configs always produce the same hash.
    timestamp : str
        ISO-8601 timestamp of when this version info was assembled.
    """

    pipeline_version: str
    nlp_engine_version: str
    extraction_pipeline_version: str
    mapping_service_version: str
    omop_vocabulary_version: str
    extraction_config_hash: str
    timestamp: str

    # ---- helpers ----

    def to_dict(self) -> dict[str, str]:
        """Serialise to a plain dictionary."""
        return asdict(self)

    @property
    def version_string(self) -> str:
        """Short label suitable for stamping on a ClinicalFact.

        Format: ``"pipeline/<pipeline_version>"``
        """
        return f"pipeline/{self.pipeline_version}"


def _compute_config_hash() -> str:
    """Compute a deterministic SHA-256 hash of the extraction config.

    The hash covers the component versions and any tunable parameters
    that would change pipeline output.  If nothing config-related has
    changed, the hash stays the same regardless of the timestamp.
    """
    config_payload = {
        "pipeline_version": PIPELINE_VERSION,
        "nlp_rule_based_version": NLP_RULE_BASED_VERSION,
        "nlp_ensemble_version": NLP_ENSEMBLE_VERSION,
        "extraction_pipeline_version": EXTRACTION_PIPELINE_VERSION,
        "mapping_service_version": MAPPING_SERVICE_VERSION,
    }
    serialized = json.dumps(config_payload, sort_keys=True)
    return hashlib.sha256(serialized.encode()).hexdigest()


def _get_vocabulary_version() -> str:
    """Best-effort retrieval of the OMOP vocabulary version string.

    Falls back to ``"unknown"`` when the vocabulary service is not
    available (e.g. during tests or CLI scripts).
    """
    try:
        from app.services.vocabulary import get_vocabulary_service

        svc = get_vocabulary_service()
        stats = svc.get_stats()
        concept_count = stats.get("concept_count", 0)
        return f"omop-v5/{concept_count}-concepts"
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# Cached singleton
# ---------------------------------------------------------------------------

_cached_version: PipelineVersionInfo | None = None
_version_lock = threading.Lock()


def get_current_pipeline_version() -> PipelineVersionInfo:
    """Return the current pipeline version info (cached per process).

    Thread-safe via double-checked locking.
    """
    global _cached_version

    if _cached_version is None:
        with _version_lock:
            if _cached_version is None:
                _cached_version = PipelineVersionInfo(
                    pipeline_version=PIPELINE_VERSION,
                    nlp_engine_version=f"ensemble/{NLP_ENSEMBLE_VERSION}",
                    extraction_pipeline_version=EXTRACTION_PIPELINE_VERSION,
                    mapping_service_version=MAPPING_SERVICE_VERSION,
                    omop_vocabulary_version=_get_vocabulary_version(),
                    extraction_config_hash=_compute_config_hash(),
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
                logger.info(
                    "Pipeline version info initialised: %s (config hash: %s)",
                    _cached_version.version_string,
                    _cached_version.extraction_config_hash[:12],
                )

    return _cached_version


def reset_pipeline_version_cache() -> None:
    """Reset the cached version info (mainly for testing)."""
    global _cached_version
    with _version_lock:
        _cached_version = None
