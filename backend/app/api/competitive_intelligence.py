"""Competitive Intelligence (CI-INTEL) API endpoints.

Provides comprehensive competitive intelligence operations: competitor program
tracking, market intelligence gathering, patent landscape monitoring, conference
intelligence, competitive alerts with acknowledgment, and positioning metrics.

Endpoints:
    GET    /competitive-intelligence/programs                          - List competitor programs
    GET    /competitive-intelligence/programs/{program_id}             - Get single program
    POST   /competitive-intelligence/programs                          - Create program
    PUT    /competitive-intelligence/programs/{program_id}             - Update program
    DELETE /competitive-intelligence/programs/{program_id}             - Delete program
    GET    /competitive-intelligence/market-intel                      - List market intelligence
    GET    /competitive-intelligence/market-intel/{intel_id}           - Get single market intel
    POST   /competitive-intelligence/market-intel                      - Create market intel
    PUT    /competitive-intelligence/market-intel/{intel_id}           - Update market intel
    DELETE /competitive-intelligence/market-intel/{intel_id}           - Delete market intel
    GET    /competitive-intelligence/patents                           - List patents
    GET    /competitive-intelligence/patents/{patent_id}               - Get single patent
    POST   /competitive-intelligence/patents                           - Create patent
    PUT    /competitive-intelligence/patents/{patent_id}               - Update patent
    DELETE /competitive-intelligence/patents/{patent_id}               - Delete patent
    GET    /competitive-intelligence/conference-intel                   - List conference intel
    GET    /competitive-intelligence/conference-intel/{intel_id}        - Get single conference intel
    POST   /competitive-intelligence/conference-intel                   - Create conference intel
    PUT    /competitive-intelligence/conference-intel/{intel_id}        - Update conference intel
    DELETE /competitive-intelligence/conference-intel/{intel_id}        - Delete conference intel
    GET    /competitive-intelligence/alerts                             - List alerts
    GET    /competitive-intelligence/alerts/{alert_id}                  - Get single alert
    POST   /competitive-intelligence/alerts                             - Create alert
    PUT    /competitive-intelligence/alerts/{alert_id}                  - Update alert
    POST   /competitive-intelligence/alerts/{alert_id}/acknowledge      - Acknowledge alert
    DELETE /competitive-intelligence/alerts/{alert_id}                  - Delete alert
    GET    /competitive-intelligence/metrics                            - CI metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.competitive_intelligence import (
    AlertPriority,
    CompetitiveAlert,
    CompetitiveAlertCreate,
    CompetitiveAlertListResponse,
    CompetitiveAlertUpdate,
    CompetitiveIntelligenceMetrics,
    CompetitorProgram,
    CompetitorProgramCreate,
    CompetitorProgramListResponse,
    CompetitorProgramUpdate,
    CompetitorStatus,
    ConferenceIntelligence,
    ConferenceIntelligenceCreate,
    ConferenceIntelligenceListResponse,
    ConferenceIntelligenceUpdate,
    ConferenceType,
    IntelligenceSource,
    MarketIntelligence,
    MarketIntelligenceCreate,
    MarketIntelligenceListResponse,
    MarketIntelligenceUpdate,
    PatentLandscape,
    PatentLandscapeCreate,
    PatentLandscapeListResponse,
    PatentLandscapeUpdate,
    PatentStatus,
    ThreatLevel,
)
from app.services.competitive_intelligence_service import (
    get_competitive_intelligence_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/competitive-intelligence",
    tags=["Competitive Intelligence"],
)


# ---------------------------------------------------------------------------
# Competitor Programs
# ---------------------------------------------------------------------------


@router.get(
    "/programs",
    response_model=CompetitorProgramListResponse,
    summary="List competitor programs",
    description="Retrieve competitor programs with optional filtering by therapeutic area, status, and threat level.",
)
async def list_competitor_programs(
    therapeutic_area: Optional[str] = Query(None, description="Filter by therapeutic area"),
    status: Optional[CompetitorStatus] = Query(None, description="Filter by status"),
    threat_level: Optional[ThreatLevel] = Query(None, description="Filter by threat level"),
) -> CompetitorProgramListResponse:
    svc = get_competitive_intelligence_service()
    items = svc.list_competitor_programs(
        therapeutic_area=therapeutic_area, status=status, threat_level=threat_level,
    )
    return CompetitorProgramListResponse(items=items, total=len(items))


@router.get(
    "/programs/{program_id}",
    response_model=CompetitorProgram,
    summary="Get a competitor program",
)
async def get_competitor_program(program_id: str) -> CompetitorProgram:
    svc = get_competitive_intelligence_service()
    program = svc.get_competitor_program(program_id)
    if program is None:
        raise HTTPException(status_code=404, detail=f"Program '{program_id}' not found")
    return program


@router.post(
    "/programs",
    response_model=CompetitorProgram,
    status_code=201,
    summary="Create a competitor program",
)
async def create_competitor_program(payload: CompetitorProgramCreate) -> CompetitorProgram:
    svc = get_competitive_intelligence_service()
    return svc.create_competitor_program(payload)


@router.put(
    "/programs/{program_id}",
    response_model=CompetitorProgram,
    summary="Update a competitor program",
)
async def update_competitor_program(
    program_id: str, payload: CompetitorProgramUpdate
) -> CompetitorProgram:
    svc = get_competitive_intelligence_service()
    updated = svc.update_competitor_program(program_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Program '{program_id}' not found")
    return updated


@router.delete(
    "/programs/{program_id}",
    status_code=204,
    summary="Delete a competitor program",
)
async def delete_competitor_program(program_id: str) -> None:
    svc = get_competitive_intelligence_service()
    deleted = svc.delete_competitor_program(program_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Program '{program_id}' not found")


# ---------------------------------------------------------------------------
# Market Intelligence
# ---------------------------------------------------------------------------


@router.get(
    "/market-intel",
    response_model=MarketIntelligenceListResponse,
    summary="List market intelligence",
    description="Retrieve market intelligence items with optional filtering by source, therapeutic area, and threat level.",
)
async def list_market_intelligence(
    source: Optional[IntelligenceSource] = Query(None, description="Filter by source"),
    therapeutic_area: Optional[str] = Query(None, description="Filter by therapeutic area"),
    threat_level: Optional[ThreatLevel] = Query(None, description="Filter by threat level"),
) -> MarketIntelligenceListResponse:
    svc = get_competitive_intelligence_service()
    items = svc.list_market_intelligence(
        source=source, therapeutic_area=therapeutic_area, threat_level=threat_level,
    )
    return MarketIntelligenceListResponse(items=items, total=len(items))


@router.get(
    "/market-intel/{intel_id}",
    response_model=MarketIntelligence,
    summary="Get a market intelligence item",
)
async def get_market_intelligence(intel_id: str) -> MarketIntelligence:
    svc = get_competitive_intelligence_service()
    intel = svc.get_market_intelligence(intel_id)
    if intel is None:
        raise HTTPException(status_code=404, detail=f"Market intelligence '{intel_id}' not found")
    return intel


@router.post(
    "/market-intel",
    response_model=MarketIntelligence,
    status_code=201,
    summary="Create a market intelligence item",
)
async def create_market_intelligence(payload: MarketIntelligenceCreate) -> MarketIntelligence:
    svc = get_competitive_intelligence_service()
    return svc.create_market_intelligence(payload)


@router.put(
    "/market-intel/{intel_id}",
    response_model=MarketIntelligence,
    summary="Update a market intelligence item",
)
async def update_market_intelligence(
    intel_id: str, payload: MarketIntelligenceUpdate
) -> MarketIntelligence:
    svc = get_competitive_intelligence_service()
    updated = svc.update_market_intelligence(intel_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Market intelligence '{intel_id}' not found")
    return updated


@router.delete(
    "/market-intel/{intel_id}",
    status_code=204,
    summary="Delete a market intelligence item",
)
async def delete_market_intelligence(intel_id: str) -> None:
    svc = get_competitive_intelligence_service()
    deleted = svc.delete_market_intelligence(intel_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Market intelligence '{intel_id}' not found")


# ---------------------------------------------------------------------------
# Patent Landscape
# ---------------------------------------------------------------------------


@router.get(
    "/patents",
    response_model=PatentLandscapeListResponse,
    summary="List patents",
    description="Retrieve patent landscape items with optional filtering by status and therapeutic area.",
)
async def list_patents(
    status: Optional[PatentStatus] = Query(None, description="Filter by patent status"),
    therapeutic_area: Optional[str] = Query(None, description="Filter by therapeutic area"),
) -> PatentLandscapeListResponse:
    svc = get_competitive_intelligence_service()
    items = svc.list_patents(status=status, therapeutic_area=therapeutic_area)
    return PatentLandscapeListResponse(items=items, total=len(items))


@router.get(
    "/patents/{patent_id}",
    response_model=PatentLandscape,
    summary="Get a patent record",
)
async def get_patent(patent_id: str) -> PatentLandscape:
    svc = get_competitive_intelligence_service()
    patent = svc.get_patent(patent_id)
    if patent is None:
        raise HTTPException(status_code=404, detail=f"Patent '{patent_id}' not found")
    return patent


@router.post(
    "/patents",
    response_model=PatentLandscape,
    status_code=201,
    summary="Create a patent record",
)
async def create_patent(payload: PatentLandscapeCreate) -> PatentLandscape:
    svc = get_competitive_intelligence_service()
    return svc.create_patent(payload)


@router.put(
    "/patents/{patent_id}",
    response_model=PatentLandscape,
    summary="Update a patent record",
)
async def update_patent(
    patent_id: str, payload: PatentLandscapeUpdate
) -> PatentLandscape:
    svc = get_competitive_intelligence_service()
    updated = svc.update_patent(patent_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Patent '{patent_id}' not found")
    return updated


@router.delete(
    "/patents/{patent_id}",
    status_code=204,
    summary="Delete a patent record",
)
async def delete_patent(patent_id: str) -> None:
    svc = get_competitive_intelligence_service()
    deleted = svc.delete_patent(patent_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Patent '{patent_id}' not found")


# ---------------------------------------------------------------------------
# Conference Intelligence
# ---------------------------------------------------------------------------


@router.get(
    "/conference-intel",
    response_model=ConferenceIntelligenceListResponse,
    summary="List conference intelligence",
    description="Retrieve conference intelligence items with optional filtering by type, therapeutic area, and threat level.",
)
async def list_conference_intelligence(
    conference_type: Optional[ConferenceType] = Query(None, description="Filter by conference type"),
    therapeutic_area: Optional[str] = Query(None, description="Filter by therapeutic area"),
    threat_level: Optional[ThreatLevel] = Query(None, description="Filter by threat level"),
) -> ConferenceIntelligenceListResponse:
    svc = get_competitive_intelligence_service()
    items = svc.list_conference_intelligence(
        conference_type=conference_type, therapeutic_area=therapeutic_area,
        threat_level=threat_level,
    )
    return ConferenceIntelligenceListResponse(items=items, total=len(items))


@router.get(
    "/conference-intel/{intel_id}",
    response_model=ConferenceIntelligence,
    summary="Get a conference intelligence item",
)
async def get_conference_intelligence(intel_id: str) -> ConferenceIntelligence:
    svc = get_competitive_intelligence_service()
    intel = svc.get_conference_intelligence(intel_id)
    if intel is None:
        raise HTTPException(status_code=404, detail=f"Conference intelligence '{intel_id}' not found")
    return intel


@router.post(
    "/conference-intel",
    response_model=ConferenceIntelligence,
    status_code=201,
    summary="Create a conference intelligence item",
)
async def create_conference_intelligence(
    payload: ConferenceIntelligenceCreate,
) -> ConferenceIntelligence:
    svc = get_competitive_intelligence_service()
    return svc.create_conference_intelligence(payload)


@router.put(
    "/conference-intel/{intel_id}",
    response_model=ConferenceIntelligence,
    summary="Update a conference intelligence item",
)
async def update_conference_intelligence(
    intel_id: str, payload: ConferenceIntelligenceUpdate
) -> ConferenceIntelligence:
    svc = get_competitive_intelligence_service()
    updated = svc.update_conference_intelligence(intel_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Conference intelligence '{intel_id}' not found")
    return updated


@router.delete(
    "/conference-intel/{intel_id}",
    status_code=204,
    summary="Delete a conference intelligence item",
)
async def delete_conference_intelligence(intel_id: str) -> None:
    svc = get_competitive_intelligence_service()
    deleted = svc.delete_conference_intelligence(intel_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Conference intelligence '{intel_id}' not found")


# ---------------------------------------------------------------------------
# Competitive Alerts
# ---------------------------------------------------------------------------


@router.get(
    "/alerts",
    response_model=CompetitiveAlertListResponse,
    summary="List competitive alerts",
    description="Retrieve competitive alerts with optional filtering by priority, acknowledged status, and therapeutic area.",
)
async def list_alerts(
    priority: Optional[AlertPriority] = Query(None, description="Filter by priority"),
    acknowledged: Optional[bool] = Query(None, description="Filter by acknowledged status"),
    therapeutic_area: Optional[str] = Query(None, description="Filter by therapeutic area"),
) -> CompetitiveAlertListResponse:
    svc = get_competitive_intelligence_service()
    items = svc.list_alerts(
        priority=priority, acknowledged=acknowledged, therapeutic_area=therapeutic_area,
    )
    return CompetitiveAlertListResponse(items=items, total=len(items))


@router.get(
    "/alerts/{alert_id}",
    response_model=CompetitiveAlert,
    summary="Get a competitive alert",
)
async def get_alert(alert_id: str) -> CompetitiveAlert:
    svc = get_competitive_intelligence_service()
    alert = svc.get_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")
    return alert


@router.post(
    "/alerts",
    response_model=CompetitiveAlert,
    status_code=201,
    summary="Create a competitive alert",
)
async def create_alert(payload: CompetitiveAlertCreate) -> CompetitiveAlert:
    svc = get_competitive_intelligence_service()
    return svc.create_alert(payload)


@router.put(
    "/alerts/{alert_id}",
    response_model=CompetitiveAlert,
    summary="Update a competitive alert",
)
async def update_alert(
    alert_id: str, payload: CompetitiveAlertUpdate
) -> CompetitiveAlert:
    svc = get_competitive_intelligence_service()
    updated = svc.update_alert(alert_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")
    return updated


@router.post(
    "/alerts/{alert_id}/acknowledge",
    response_model=CompetitiveAlert,
    summary="Acknowledge a competitive alert",
    description="Mark an alert as acknowledged by a specific person.",
)
async def acknowledge_alert(alert_id: str, acknowledged_by: str) -> CompetitiveAlert:
    svc = get_competitive_intelligence_service()
    result = svc.acknowledge_alert(alert_id, acknowledged_by)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")
    return result


@router.delete(
    "/alerts/{alert_id}",
    status_code=204,
    summary="Delete a competitive alert",
)
async def delete_alert(alert_id: str) -> None:
    svc = get_competitive_intelligence_service()
    deleted = svc.delete_alert(alert_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=CompetitiveIntelligenceMetrics,
    summary="Get competitive intelligence metrics",
    description="Aggregated competitive intelligence metrics including program counts, "
                "threat levels, alert status, and patent landscape overview.",
)
async def get_metrics() -> CompetitiveIntelligenceMetrics:
    svc = get_competitive_intelligence_service()
    return svc.get_metrics()
