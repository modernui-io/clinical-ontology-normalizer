"""Country-Level Regulatory Requirements API endpoints (REG-COUNTRY).

Provides comprehensive country regulatory operations: requirements management,
ethics committee submissions, import/export licenses, local regulatory agent
assignments, country activation tracking, and regulatory compliance metrics.

Endpoints:
    GET    /country-regulatory/requirements                          - List requirements
    GET    /country-regulatory/requirements/{requirement_id}         - Get single requirement
    POST   /country-regulatory/requirements                          - Create requirement
    PUT    /country-regulatory/requirements/{requirement_id}         - Update requirement
    DELETE /country-regulatory/requirements/{requirement_id}         - Delete requirement
    GET    /country-regulatory/ethics                                - List ethics submissions
    GET    /country-regulatory/ethics/{ethics_id}                    - Get single ethics submission
    POST   /country-regulatory/ethics                                - Create ethics submission
    PUT    /country-regulatory/ethics/{ethics_id}                    - Update ethics submission
    DELETE /country-regulatory/ethics/{ethics_id}                    - Delete ethics submission
    GET    /country-regulatory/licenses                              - List licenses
    GET    /country-regulatory/licenses/{license_id}                 - Get single license
    POST   /country-regulatory/licenses                              - Create license
    PUT    /country-regulatory/licenses/{license_id}                 - Update license
    DELETE /country-regulatory/licenses/{license_id}                 - Delete license
    GET    /country-regulatory/agents                                - List local agents
    GET    /country-regulatory/agents/{agent_id}                     - Get single agent
    POST   /country-regulatory/agents                                - Create agent
    PUT    /country-regulatory/agents/{agent_id}                     - Update agent
    DELETE /country-regulatory/agents/{agent_id}                     - Delete agent
    GET    /country-regulatory/activations                           - List activations
    GET    /country-regulatory/activations/{activation_id}           - Get single activation
    POST   /country-regulatory/activations                           - Create activation
    PUT    /country-regulatory/activations/{activation_id}           - Update activation
    DELETE /country-regulatory/activations/{activation_id}           - Delete activation
    GET    /country-regulatory/metrics                               - Regulatory metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.country_regulatory import (
    ActivationStatus,
    AgentRole,
    ApprovalStatus,
    CountryActivation,
    CountryActivationCreate,
    CountryActivationListResponse,
    CountryActivationUpdate,
    CountryRegulatoryMetrics,
    CountryRequirement,
    CountryRequirementCreate,
    CountryRequirementListResponse,
    CountryRequirementUpdate,
    EthicsSubmission,
    EthicsSubmissionCreate,
    EthicsSubmissionListResponse,
    EthicsSubmissionUpdate,
    ImportExportLicense,
    ImportExportLicenseCreate,
    ImportExportLicenseListResponse,
    ImportExportLicenseUpdate,
    LocalAgent,
    LocalAgentCreate,
    LocalAgentListResponse,
    LocalAgentUpdate,
    SubmissionType,
)
from app.services.country_regulatory_service import get_country_regulatory_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/country-regulatory",
    tags=["Country Regulatory"],
)


# ---------------------------------------------------------------------------
# Country Requirements
# ---------------------------------------------------------------------------


@router.get(
    "/requirements",
    response_model=CountryRequirementListResponse,
    summary="List country requirements",
    description="Retrieve country-specific regulatory requirements with optional filtering.",
)
async def list_requirements(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    country: Optional[str] = Query(None, description="Filter by country name"),
    approval_status: Optional[ApprovalStatus] = Query(None, description="Filter by approval status"),
    requirement_type: Optional[SubmissionType] = Query(None, description="Filter by requirement type"),
) -> CountryRequirementListResponse:
    svc = get_country_regulatory_service()
    items = svc.list_requirements(
        trial_id=trial_id, country=country,
        approval_status=approval_status, requirement_type=requirement_type,
    )
    return CountryRequirementListResponse(items=items, total=len(items))


@router.get(
    "/requirements/{requirement_id}",
    response_model=CountryRequirement,
    summary="Get a country requirement",
)
async def get_requirement(requirement_id: str) -> CountryRequirement:
    svc = get_country_regulatory_service()
    requirement = svc.get_requirement(requirement_id)
    if requirement is None:
        raise HTTPException(status_code=404, detail=f"Requirement '{requirement_id}' not found")
    return requirement


@router.post(
    "/requirements",
    response_model=CountryRequirement,
    status_code=201,
    summary="Create a country requirement",
)
async def create_requirement(payload: CountryRequirementCreate) -> CountryRequirement:
    svc = get_country_regulatory_service()
    return svc.create_requirement(payload)


@router.put(
    "/requirements/{requirement_id}",
    response_model=CountryRequirement,
    summary="Update a country requirement",
)
async def update_requirement(
    requirement_id: str, payload: CountryRequirementUpdate
) -> CountryRequirement:
    svc = get_country_regulatory_service()
    updated = svc.update_requirement(requirement_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Requirement '{requirement_id}' not found")
    return updated


@router.delete(
    "/requirements/{requirement_id}",
    status_code=204,
    summary="Delete a country requirement",
)
async def delete_requirement(requirement_id: str) -> None:
    svc = get_country_regulatory_service()
    deleted = svc.delete_requirement(requirement_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Requirement '{requirement_id}' not found")


# ---------------------------------------------------------------------------
# Ethics Submissions
# ---------------------------------------------------------------------------


@router.get(
    "/ethics",
    response_model=EthicsSubmissionListResponse,
    summary="List ethics submissions",
    description="Retrieve ethics committee submissions with optional filtering.",
)
async def list_ethics(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    country: Optional[str] = Query(None, description="Filter by country name"),
    approval_status: Optional[ApprovalStatus] = Query(None, description="Filter by approval status"),
) -> EthicsSubmissionListResponse:
    svc = get_country_regulatory_service()
    items = svc.list_ethics(
        trial_id=trial_id, country=country, approval_status=approval_status,
    )
    return EthicsSubmissionListResponse(items=items, total=len(items))


@router.get(
    "/ethics/{ethics_id}",
    response_model=EthicsSubmission,
    summary="Get an ethics submission",
)
async def get_ethics(ethics_id: str) -> EthicsSubmission:
    svc = get_country_regulatory_service()
    ethics = svc.get_ethics(ethics_id)
    if ethics is None:
        raise HTTPException(status_code=404, detail=f"Ethics submission '{ethics_id}' not found")
    return ethics


@router.post(
    "/ethics",
    response_model=EthicsSubmission,
    status_code=201,
    summary="Create an ethics submission",
)
async def create_ethics(payload: EthicsSubmissionCreate) -> EthicsSubmission:
    svc = get_country_regulatory_service()
    return svc.create_ethics(payload)


@router.put(
    "/ethics/{ethics_id}",
    response_model=EthicsSubmission,
    summary="Update an ethics submission",
)
async def update_ethics(
    ethics_id: str, payload: EthicsSubmissionUpdate
) -> EthicsSubmission:
    svc = get_country_regulatory_service()
    updated = svc.update_ethics(ethics_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Ethics submission '{ethics_id}' not found")
    return updated


@router.delete(
    "/ethics/{ethics_id}",
    status_code=204,
    summary="Delete an ethics submission",
)
async def delete_ethics(ethics_id: str) -> None:
    svc = get_country_regulatory_service()
    deleted = svc.delete_ethics(ethics_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Ethics submission '{ethics_id}' not found")


# ---------------------------------------------------------------------------
# Import/Export Licenses
# ---------------------------------------------------------------------------


@router.get(
    "/licenses",
    response_model=ImportExportLicenseListResponse,
    summary="List import/export licenses",
    description="Retrieve import/export licenses with optional filtering.",
)
async def list_licenses(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    country: Optional[str] = Query(None, description="Filter by country name"),
    status: Optional[ApprovalStatus] = Query(None, description="Filter by license status"),
    license_type: Optional[str] = Query(None, description="Filter by license type (import/export)"),
) -> ImportExportLicenseListResponse:
    svc = get_country_regulatory_service()
    items = svc.list_licenses(
        trial_id=trial_id, country=country, status=status, license_type=license_type,
    )
    return ImportExportLicenseListResponse(items=items, total=len(items))


@router.get(
    "/licenses/{license_id}",
    response_model=ImportExportLicense,
    summary="Get an import/export license",
)
async def get_license(license_id: str) -> ImportExportLicense:
    svc = get_country_regulatory_service()
    license_obj = svc.get_license(license_id)
    if license_obj is None:
        raise HTTPException(status_code=404, detail=f"License '{license_id}' not found")
    return license_obj


@router.post(
    "/licenses",
    response_model=ImportExportLicense,
    status_code=201,
    summary="Create an import/export license",
)
async def create_license(payload: ImportExportLicenseCreate) -> ImportExportLicense:
    svc = get_country_regulatory_service()
    return svc.create_license(payload)


@router.put(
    "/licenses/{license_id}",
    response_model=ImportExportLicense,
    summary="Update an import/export license",
)
async def update_license(
    license_id: str, payload: ImportExportLicenseUpdate
) -> ImportExportLicense:
    svc = get_country_regulatory_service()
    updated = svc.update_license(license_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"License '{license_id}' not found")
    return updated


@router.delete(
    "/licenses/{license_id}",
    status_code=204,
    summary="Delete an import/export license",
)
async def delete_license(license_id: str) -> None:
    svc = get_country_regulatory_service()
    deleted = svc.delete_license(license_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"License '{license_id}' not found")


# ---------------------------------------------------------------------------
# Local Agents
# ---------------------------------------------------------------------------


@router.get(
    "/agents",
    response_model=LocalAgentListResponse,
    summary="List local agents",
    description="Retrieve local regulatory agents with optional filtering.",
)
async def list_agents(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    country: Optional[str] = Query(None, description="Filter by country name"),
    role: Optional[AgentRole] = Query(None, description="Filter by agent role"),
    active: Optional[bool] = Query(None, description="Filter by active status"),
) -> LocalAgentListResponse:
    svc = get_country_regulatory_service()
    items = svc.list_agents(
        trial_id=trial_id, country=country, role=role, active=active,
    )
    return LocalAgentListResponse(items=items, total=len(items))


@router.get(
    "/agents/{agent_id}",
    response_model=LocalAgent,
    summary="Get a local agent",
)
async def get_agent(agent_id: str) -> LocalAgent:
    svc = get_country_regulatory_service()
    agent = svc.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return agent


@router.post(
    "/agents",
    response_model=LocalAgent,
    status_code=201,
    summary="Create a local agent",
)
async def create_agent(payload: LocalAgentCreate) -> LocalAgent:
    svc = get_country_regulatory_service()
    return svc.create_agent(payload)


@router.put(
    "/agents/{agent_id}",
    response_model=LocalAgent,
    summary="Update a local agent",
)
async def update_agent(
    agent_id: str, payload: LocalAgentUpdate
) -> LocalAgent:
    svc = get_country_regulatory_service()
    updated = svc.update_agent(agent_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return updated


@router.delete(
    "/agents/{agent_id}",
    status_code=204,
    summary="Delete a local agent",
)
async def delete_agent(agent_id: str) -> None:
    svc = get_country_regulatory_service()
    deleted = svc.delete_agent(agent_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")


# ---------------------------------------------------------------------------
# Country Activations
# ---------------------------------------------------------------------------


@router.get(
    "/activations",
    response_model=CountryActivationListResponse,
    summary="List country activations",
    description="Retrieve country activations with optional filtering.",
)
async def list_activations(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    country: Optional[str] = Query(None, description="Filter by country name"),
    status: Optional[ActivationStatus] = Query(None, description="Filter by activation status"),
) -> CountryActivationListResponse:
    svc = get_country_regulatory_service()
    items = svc.list_activations(
        trial_id=trial_id, country=country, status=status,
    )
    return CountryActivationListResponse(items=items, total=len(items))


@router.get(
    "/activations/{activation_id}",
    response_model=CountryActivation,
    summary="Get a country activation",
)
async def get_activation(activation_id: str) -> CountryActivation:
    svc = get_country_regulatory_service()
    activation = svc.get_activation(activation_id)
    if activation is None:
        raise HTTPException(status_code=404, detail=f"Activation '{activation_id}' not found")
    return activation


@router.post(
    "/activations",
    response_model=CountryActivation,
    status_code=201,
    summary="Create a country activation",
)
async def create_activation(payload: CountryActivationCreate) -> CountryActivation:
    svc = get_country_regulatory_service()
    return svc.create_activation(payload)


@router.put(
    "/activations/{activation_id}",
    response_model=CountryActivation,
    summary="Update a country activation",
)
async def update_activation(
    activation_id: str, payload: CountryActivationUpdate
) -> CountryActivation:
    svc = get_country_regulatory_service()
    updated = svc.update_activation(activation_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Activation '{activation_id}' not found")
    return updated


@router.delete(
    "/activations/{activation_id}",
    status_code=204,
    summary="Delete a country activation",
)
async def delete_activation(activation_id: str) -> None:
    svc = get_country_regulatory_service()
    deleted = svc.delete_activation(activation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Activation '{activation_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=CountryRegulatoryMetrics,
    summary="Get country regulatory metrics",
    description="Aggregated regulatory metrics including requirements status, ethics approvals, "
                "license status, agent counts, country activation progress, and overall activation percentage.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter metrics by trial ID"),
) -> CountryRegulatoryMetrics:
    svc = get_country_regulatory_service()
    return svc.get_metrics(trial_id=trial_id)
