"""Protocol Design & Optimization (PROTO-DESIGN) API endpoints.

Provides protocol development lifecycle management: protocol elements, endpoint
definitions, sample size calculations, schedule of assessments, protocol
simulations, and protocol design metrics.

Endpoints:
    GET    /protocol-design/protocols                             - List protocols
    GET    /protocol-design/protocols/{protocol_id}               - Get single protocol
    POST   /protocol-design/protocols                             - Create protocol
    PUT    /protocol-design/protocols/{protocol_id}               - Update protocol
    DELETE /protocol-design/protocols/{protocol_id}               - Delete protocol
    GET    /protocol-design/endpoints                             - List endpoints
    GET    /protocol-design/endpoints/{endpoint_id}               - Get single endpoint
    POST   /protocol-design/endpoints                             - Create endpoint
    PUT    /protocol-design/endpoints/{endpoint_id}               - Update endpoint
    DELETE /protocol-design/endpoints/{endpoint_id}               - Delete endpoint
    GET    /protocol-design/sample-calcs                          - List sample size calcs
    GET    /protocol-design/sample-calcs/{calc_id}                - Get single calc
    POST   /protocol-design/sample-calcs                          - Create calc
    PUT    /protocol-design/sample-calcs/{calc_id}                - Update calc
    DELETE /protocol-design/sample-calcs/{calc_id}                - Delete calc
    GET    /protocol-design/schedules                             - List schedules
    GET    /protocol-design/schedules/{schedule_id}               - Get single schedule
    POST   /protocol-design/schedules                             - Create schedule
    PUT    /protocol-design/schedules/{schedule_id}               - Update schedule
    DELETE /protocol-design/schedules/{schedule_id}               - Delete schedule
    GET    /protocol-design/simulations                           - List simulations
    GET    /protocol-design/simulations/{simulation_id}           - Get single simulation
    POST   /protocol-design/simulations                           - Create simulation
    PUT    /protocol-design/simulations/{simulation_id}           - Update simulation
    DELETE /protocol-design/simulations/{simulation_id}           - Delete simulation
    GET    /protocol-design/metrics                               - Design metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.protocol_design import (
    DesignStatus,
    EndpointCategory,
    EndpointDefinition,
    EndpointDefinitionCreate,
    EndpointDefinitionListResponse,
    ProtocolDesignMetrics,
    ProtocolElement,
    ProtocolElementCreate,
    ProtocolElementListResponse,
    ProtocolElementUpdate,
    ProtocolPhase,
    ProtocolSimulation,
    ProtocolSimulationCreate,
    ProtocolSimulationListResponse,
    ProtocolSimulationUpdate,
    SampleSizeCalc,
    SampleSizeCalcCreate,
    SampleSizeCalcListResponse,
    ScheduleOfAssessments,
    ScheduleOfAssessmentsCreate,
    ScheduleOfAssessmentsListResponse,
    SimulationStatus,
)
from app.services.protocol_design_service import get_protocol_design_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/protocol-design",
    tags=["Protocol Design"],
)


# ---------------------------------------------------------------------------
# Protocol Element Management
# ---------------------------------------------------------------------------


@router.get(
    "/protocols",
    response_model=ProtocolElementListResponse,
    summary="List protocol elements",
    description="Retrieve protocol elements with optional filtering by trial, phase, and status.",
)
async def list_protocols(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    phase: Optional[ProtocolPhase] = Query(None, description="Filter by phase"),
    status: Optional[DesignStatus] = Query(None, description="Filter by status"),
) -> ProtocolElementListResponse:
    svc = get_protocol_design_service()
    items = svc.list_protocols(trial_id=trial_id, phase=phase, status=status)
    return ProtocolElementListResponse(items=items, total=len(items))


@router.get(
    "/protocols/{protocol_id}",
    response_model=ProtocolElement,
    summary="Get a protocol element",
)
async def get_protocol(protocol_id: str) -> ProtocolElement:
    svc = get_protocol_design_service()
    protocol = svc.get_protocol(protocol_id)
    if protocol is None:
        raise HTTPException(status_code=404, detail=f"Protocol '{protocol_id}' not found")
    return protocol


@router.post(
    "/protocols",
    response_model=ProtocolElement,
    status_code=201,
    summary="Create a protocol element",
)
async def create_protocol(payload: ProtocolElementCreate) -> ProtocolElement:
    svc = get_protocol_design_service()
    return svc.create_protocol(payload)


@router.put(
    "/protocols/{protocol_id}",
    response_model=ProtocolElement,
    summary="Update a protocol element",
)
async def update_protocol(
    protocol_id: str, payload: ProtocolElementUpdate
) -> ProtocolElement:
    svc = get_protocol_design_service()
    updated = svc.update_protocol(protocol_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Protocol '{protocol_id}' not found")
    return updated


@router.delete(
    "/protocols/{protocol_id}",
    status_code=204,
    summary="Delete a protocol element",
)
async def delete_protocol(protocol_id: str) -> None:
    svc = get_protocol_design_service()
    deleted = svc.delete_protocol(protocol_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Protocol '{protocol_id}' not found")


# ---------------------------------------------------------------------------
# Endpoint Definition Management
# ---------------------------------------------------------------------------


@router.get(
    "/endpoints",
    response_model=EndpointDefinitionListResponse,
    summary="List endpoint definitions",
    description="Retrieve endpoint definitions with optional filtering by protocol and category.",
)
async def list_endpoints(
    protocol_id: Optional[str] = Query(None, description="Filter by protocol ID"),
    category: Optional[EndpointCategory] = Query(None, description="Filter by category"),
) -> EndpointDefinitionListResponse:
    svc = get_protocol_design_service()
    items = svc.list_endpoints(protocol_id=protocol_id, category=category)
    return EndpointDefinitionListResponse(items=items, total=len(items))


@router.get(
    "/endpoints/{endpoint_id}",
    response_model=EndpointDefinition,
    summary="Get an endpoint definition",
)
async def get_endpoint(endpoint_id: str) -> EndpointDefinition:
    svc = get_protocol_design_service()
    endpoint = svc.get_endpoint(endpoint_id)
    if endpoint is None:
        raise HTTPException(status_code=404, detail=f"Endpoint '{endpoint_id}' not found")
    return endpoint


@router.post(
    "/endpoints",
    response_model=EndpointDefinition,
    status_code=201,
    summary="Create an endpoint definition",
)
async def create_endpoint(payload: EndpointDefinitionCreate) -> EndpointDefinition:
    svc = get_protocol_design_service()
    return svc.create_endpoint(payload)


@router.put(
    "/endpoints/{endpoint_id}",
    response_model=EndpointDefinition,
    summary="Update an endpoint definition",
)
async def update_endpoint(endpoint_id: str, payload: dict) -> EndpointDefinition:
    svc = get_protocol_design_service()
    updated = svc.update_endpoint(endpoint_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Endpoint '{endpoint_id}' not found")
    return updated


@router.delete(
    "/endpoints/{endpoint_id}",
    status_code=204,
    summary="Delete an endpoint definition",
)
async def delete_endpoint(endpoint_id: str) -> None:
    svc = get_protocol_design_service()
    deleted = svc.delete_endpoint(endpoint_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Endpoint '{endpoint_id}' not found")


# ---------------------------------------------------------------------------
# Sample Size Calculation Management
# ---------------------------------------------------------------------------


@router.get(
    "/sample-calcs",
    response_model=SampleSizeCalcListResponse,
    summary="List sample size calculations",
    description="Retrieve sample size calculations with optional filtering by protocol.",
)
async def list_sample_calcs(
    protocol_id: Optional[str] = Query(None, description="Filter by protocol ID"),
) -> SampleSizeCalcListResponse:
    svc = get_protocol_design_service()
    items = svc.list_sample_calcs(protocol_id=protocol_id)
    return SampleSizeCalcListResponse(items=items, total=len(items))


@router.get(
    "/sample-calcs/{calc_id}",
    response_model=SampleSizeCalc,
    summary="Get a sample size calculation",
)
async def get_sample_calc(calc_id: str) -> SampleSizeCalc:
    svc = get_protocol_design_service()
    calc = svc.get_sample_calc(calc_id)
    if calc is None:
        raise HTTPException(status_code=404, detail=f"Sample size calc '{calc_id}' not found")
    return calc


@router.post(
    "/sample-calcs",
    response_model=SampleSizeCalc,
    status_code=201,
    summary="Create a sample size calculation",
)
async def create_sample_calc(payload: SampleSizeCalcCreate) -> SampleSizeCalc:
    svc = get_protocol_design_service()
    return svc.create_sample_calc(payload)


@router.put(
    "/sample-calcs/{calc_id}",
    response_model=SampleSizeCalc,
    summary="Update a sample size calculation",
)
async def update_sample_calc(calc_id: str, payload: dict) -> SampleSizeCalc:
    svc = get_protocol_design_service()
    updated = svc.update_sample_calc(calc_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Sample size calc '{calc_id}' not found")
    return updated


@router.delete(
    "/sample-calcs/{calc_id}",
    status_code=204,
    summary="Delete a sample size calculation",
)
async def delete_sample_calc(calc_id: str) -> None:
    svc = get_protocol_design_service()
    deleted = svc.delete_sample_calc(calc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Sample size calc '{calc_id}' not found")


# ---------------------------------------------------------------------------
# Schedule of Assessments Management
# ---------------------------------------------------------------------------


@router.get(
    "/schedules",
    response_model=ScheduleOfAssessmentsListResponse,
    summary="List schedule of assessments",
    description="Retrieve schedule of assessments with optional filtering by protocol.",
)
async def list_schedules(
    protocol_id: Optional[str] = Query(None, description="Filter by protocol ID"),
) -> ScheduleOfAssessmentsListResponse:
    svc = get_protocol_design_service()
    items = svc.list_schedules(protocol_id=protocol_id)
    return ScheduleOfAssessmentsListResponse(items=items, total=len(items))


@router.get(
    "/schedules/{schedule_id}",
    response_model=ScheduleOfAssessments,
    summary="Get a schedule of assessments entry",
)
async def get_schedule(schedule_id: str) -> ScheduleOfAssessments:
    svc = get_protocol_design_service()
    schedule = svc.get_schedule(schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail=f"Schedule '{schedule_id}' not found")
    return schedule


@router.post(
    "/schedules",
    response_model=ScheduleOfAssessments,
    status_code=201,
    summary="Create a schedule of assessments entry",
)
async def create_schedule(payload: ScheduleOfAssessmentsCreate) -> ScheduleOfAssessments:
    svc = get_protocol_design_service()
    return svc.create_schedule(payload)


@router.put(
    "/schedules/{schedule_id}",
    response_model=ScheduleOfAssessments,
    summary="Update a schedule of assessments entry",
)
async def update_schedule(schedule_id: str, payload: dict) -> ScheduleOfAssessments:
    svc = get_protocol_design_service()
    updated = svc.update_schedule(schedule_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Schedule '{schedule_id}' not found")
    return updated


@router.delete(
    "/schedules/{schedule_id}",
    status_code=204,
    summary="Delete a schedule of assessments entry",
)
async def delete_schedule(schedule_id: str) -> None:
    svc = get_protocol_design_service()
    deleted = svc.delete_schedule(schedule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Schedule '{schedule_id}' not found")


# ---------------------------------------------------------------------------
# Protocol Simulation Management
# ---------------------------------------------------------------------------


@router.get(
    "/simulations",
    response_model=ProtocolSimulationListResponse,
    summary="List protocol simulations",
    description="Retrieve protocol simulations with optional filtering by protocol and status.",
)
async def list_simulations(
    protocol_id: Optional[str] = Query(None, description="Filter by protocol ID"),
    status: Optional[SimulationStatus] = Query(None, description="Filter by status"),
) -> ProtocolSimulationListResponse:
    svc = get_protocol_design_service()
    items = svc.list_simulations(protocol_id=protocol_id, status=status)
    return ProtocolSimulationListResponse(items=items, total=len(items))


@router.get(
    "/simulations/{simulation_id}",
    response_model=ProtocolSimulation,
    summary="Get a protocol simulation",
)
async def get_simulation(simulation_id: str) -> ProtocolSimulation:
    svc = get_protocol_design_service()
    simulation = svc.get_simulation(simulation_id)
    if simulation is None:
        raise HTTPException(status_code=404, detail=f"Simulation '{simulation_id}' not found")
    return simulation


@router.post(
    "/simulations",
    response_model=ProtocolSimulation,
    status_code=201,
    summary="Create a protocol simulation",
)
async def create_simulation(payload: ProtocolSimulationCreate) -> ProtocolSimulation:
    svc = get_protocol_design_service()
    return svc.create_simulation(payload)


@router.put(
    "/simulations/{simulation_id}",
    response_model=ProtocolSimulation,
    summary="Update a protocol simulation",
)
async def update_simulation(
    simulation_id: str, payload: ProtocolSimulationUpdate
) -> ProtocolSimulation:
    svc = get_protocol_design_service()
    updated = svc.update_simulation(simulation_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Simulation '{simulation_id}' not found")
    return updated


@router.delete(
    "/simulations/{simulation_id}",
    status_code=204,
    summary="Delete a protocol simulation",
)
async def delete_simulation(simulation_id: str) -> None:
    svc = get_protocol_design_service()
    deleted = svc.delete_simulation(simulation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Simulation '{simulation_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=ProtocolDesignMetrics,
    summary="Get protocol design metrics",
    description="Aggregated protocol design metrics including protocol counts by phase/design/status, "
                "endpoint counts by category, sample size calculations, visit schedules, "
                "and simulation statistics.",
)
async def get_metrics() -> ProtocolDesignMetrics:
    svc = get_protocol_design_service()
    return svc.get_metrics()
