"""Pipeline version API endpoint.

CSO-1: Exposes the current NLP / mapping pipeline version info so that
consumers (researchers, downstream systems, audit) can determine which
pipeline version produced a given set of ClinicalFacts.

Endpoint:
    GET /api/v1/pipeline/version
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.pipeline_version import PipelineVersionInfo, get_current_pipeline_version

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


@router.get(
    "/version",
    response_model=dict[str, str],
    summary="Get current pipeline version info",
    description=(
        "Returns the version identifiers for every component in the "
        "clinical extraction and mapping pipeline. This enables "
        "reproducibility audits: every ClinicalFact records the "
        "pipeline version that produced it."
    ),
)
async def get_pipeline_version() -> dict[str, str]:
    """Return the current pipeline version information.

    The response includes:
    - ``pipeline_version``: overall semver
    - ``nlp_engine_version``: active NLP variant and version
    - ``extraction_pipeline_version``: multi-stage extraction version
    - ``mapping_service_version``: OMOP mapping service version
    - ``omop_vocabulary_version``: loaded vocabulary identifier
    - ``extraction_config_hash``: SHA-256 of the pipeline config
    - ``timestamp``: when the version info was assembled
    """
    version_info = get_current_pipeline_version()
    return version_info.to_dict()
