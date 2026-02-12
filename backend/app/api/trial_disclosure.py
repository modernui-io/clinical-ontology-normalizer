"""Trial Disclosure Management API endpoints (TRIAL-DISC).

Provides comprehensive trial disclosure operations: results disclosure
tracking, registry submission records, publication mandates, lay summaries,
and compliance timeline management with disclosure metrics.

Endpoints:
    GET    /trial-disclosure/results-disclosures                          - List disclosures
    GET    /trial-disclosure/results-disclosures/{disclosure_id}          - Get single disclosure
    POST   /trial-disclosure/results-disclosures                          - Create disclosure
    PUT    /trial-disclosure/results-disclosures/{disclosure_id}          - Update disclosure
    DELETE /trial-disclosure/results-disclosures/{disclosure_id}          - Delete disclosure
    GET    /trial-disclosure/registry-submissions                         - List submissions
    GET    /trial-disclosure/registry-submissions/{submission_id}         - Get single submission
    POST   /trial-disclosure/registry-submissions                         - Create submission
    PUT    /trial-disclosure/registry-submissions/{submission_id}         - Update submission
    DELETE /trial-disclosure/registry-submissions/{submission_id}         - Delete submission
    GET    /trial-disclosure/publication-mandates                         - List mandates
    GET    /trial-disclosure/publication-mandates/{mandate_id}            - Get single mandate
    POST   /trial-disclosure/publication-mandates                         - Create mandate
    PUT    /trial-disclosure/publication-mandates/{mandate_id}            - Update mandate
    DELETE /trial-disclosure/publication-mandates/{mandate_id}            - Delete mandate
    GET    /trial-disclosure/lay-summaries                                - List summaries
    GET    /trial-disclosure/lay-summaries/{summary_id}                   - Get single summary
    POST   /trial-disclosure/lay-summaries                                - Create summary
    PUT    /trial-disclosure/lay-summaries/{summary_id}                   - Update summary
    DELETE /trial-disclosure/lay-summaries/{summary_id}                   - Delete summary
    GET    /trial-disclosure/compliance-timelines                         - List timelines
    GET    /trial-disclosure/compliance-timelines/{timeline_id}           - Get single timeline
    POST   /trial-disclosure/compliance-timelines                         - Create timeline
    PUT    /trial-disclosure/compliance-timelines/{timeline_id}           - Update timeline
    DELETE /trial-disclosure/compliance-timelines/{timeline_id}           - Delete timeline
    GET    /trial-disclosure/metrics                                      - Disclosure metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.trial_disclosure import (
    ComplianceTimeline,
    ComplianceTimelineCreate,
    ComplianceTimelineListResponse,
    ComplianceTimelineUpdate,
    DisclosureStatus,
    DisclosureType,
    LaySummary,
    LaySummaryCreate,
    LaySummaryListResponse,
    LaySummaryUpdate,
    MandateType,
    PublicationMandate,
    PublicationMandateCreate,
    PublicationMandateListResponse,
    PublicationMandateUpdate,
    RegistryName,
    RegistrySubmission,
    RegistrySubmissionCreate,
    RegistrySubmissionListResponse,
    RegistrySubmissionUpdate,
    ResultsDisclosure,
    ResultsDisclosureCreate,
    ResultsDisclosureListResponse,
    ResultsDisclosureUpdate,
    SummaryAudience,
    TrialDisclosureMetrics,
)
from app.services.trial_disclosure_service import get_trial_disclosure_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/trial-disclosure",
    tags=["Trial Disclosure"],
)


# ---------------------------------------------------------------------------
# Results Disclosures
# ---------------------------------------------------------------------------


@router.get(
    "/results-disclosures",
    response_model=ResultsDisclosureListResponse,
    summary="List results disclosures",
    description="Retrieve results disclosures with optional filtering by trial, type, and status.",
)
async def list_results_disclosures(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    disclosure_type: Optional[DisclosureType] = Query(None, description="Filter by disclosure type"),
    status: Optional[DisclosureStatus] = Query(None, description="Filter by disclosure status"),
) -> ResultsDisclosureListResponse:
    svc = get_trial_disclosure_service()
    items = svc.list_results_disclosures(
        trial_id=trial_id, disclosure_type=disclosure_type, status=status
    )
    return ResultsDisclosureListResponse(items=items, total=len(items))


@router.get(
    "/results-disclosures/{disclosure_id}",
    response_model=ResultsDisclosure,
    summary="Get a results disclosure",
)
async def get_results_disclosure(disclosure_id: str) -> ResultsDisclosure:
    svc = get_trial_disclosure_service()
    disclosure = svc.get_results_disclosure(disclosure_id)
    if disclosure is None:
        raise HTTPException(
            status_code=404, detail=f"Results disclosure '{disclosure_id}' not found"
        )
    return disclosure


@router.post(
    "/results-disclosures",
    response_model=ResultsDisclosure,
    status_code=201,
    summary="Create a results disclosure",
)
async def create_results_disclosure(payload: ResultsDisclosureCreate) -> ResultsDisclosure:
    svc = get_trial_disclosure_service()
    return svc.create_results_disclosure(payload)


@router.put(
    "/results-disclosures/{disclosure_id}",
    response_model=ResultsDisclosure,
    summary="Update a results disclosure",
)
async def update_results_disclosure(
    disclosure_id: str, payload: ResultsDisclosureUpdate
) -> ResultsDisclosure:
    svc = get_trial_disclosure_service()
    updated = svc.update_results_disclosure(disclosure_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Results disclosure '{disclosure_id}' not found"
        )
    return updated


@router.delete(
    "/results-disclosures/{disclosure_id}",
    status_code=204,
    summary="Delete a results disclosure",
)
async def delete_results_disclosure(disclosure_id: str) -> None:
    svc = get_trial_disclosure_service()
    deleted = svc.delete_results_disclosure(disclosure_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Results disclosure '{disclosure_id}' not found"
        )


# ---------------------------------------------------------------------------
# Registry Submissions
# ---------------------------------------------------------------------------


@router.get(
    "/registry-submissions",
    response_model=RegistrySubmissionListResponse,
    summary="List registry submissions",
    description="Retrieve registry submissions with optional filtering by trial and registry.",
)
async def list_registry_submissions(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    registry_name: Optional[RegistryName] = Query(None, description="Filter by registry name"),
) -> RegistrySubmissionListResponse:
    svc = get_trial_disclosure_service()
    items = svc.list_registry_submissions(trial_id=trial_id, registry_name=registry_name)
    return RegistrySubmissionListResponse(items=items, total=len(items))


@router.get(
    "/registry-submissions/{submission_id}",
    response_model=RegistrySubmission,
    summary="Get a registry submission",
)
async def get_registry_submission(submission_id: str) -> RegistrySubmission:
    svc = get_trial_disclosure_service()
    submission = svc.get_registry_submission(submission_id)
    if submission is None:
        raise HTTPException(
            status_code=404, detail=f"Registry submission '{submission_id}' not found"
        )
    return submission


@router.post(
    "/registry-submissions",
    response_model=RegistrySubmission,
    status_code=201,
    summary="Create a registry submission",
)
async def create_registry_submission(payload: RegistrySubmissionCreate) -> RegistrySubmission:
    svc = get_trial_disclosure_service()
    return svc.create_registry_submission(payload)


@router.put(
    "/registry-submissions/{submission_id}",
    response_model=RegistrySubmission,
    summary="Update a registry submission",
)
async def update_registry_submission(
    submission_id: str, payload: RegistrySubmissionUpdate
) -> RegistrySubmission:
    svc = get_trial_disclosure_service()
    updated = svc.update_registry_submission(submission_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Registry submission '{submission_id}' not found"
        )
    return updated


@router.delete(
    "/registry-submissions/{submission_id}",
    status_code=204,
    summary="Delete a registry submission",
)
async def delete_registry_submission(submission_id: str) -> None:
    svc = get_trial_disclosure_service()
    deleted = svc.delete_registry_submission(submission_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Registry submission '{submission_id}' not found"
        )


# ---------------------------------------------------------------------------
# Publication Mandates
# ---------------------------------------------------------------------------


@router.get(
    "/publication-mandates",
    response_model=PublicationMandateListResponse,
    summary="List publication mandates",
    description="Retrieve publication mandates with optional filtering by trial and type.",
)
async def list_publication_mandates(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    mandate_type: Optional[MandateType] = Query(None, description="Filter by mandate type"),
) -> PublicationMandateListResponse:
    svc = get_trial_disclosure_service()
    items = svc.list_publication_mandates(trial_id=trial_id, mandate_type=mandate_type)
    return PublicationMandateListResponse(items=items, total=len(items))


@router.get(
    "/publication-mandates/{mandate_id}",
    response_model=PublicationMandate,
    summary="Get a publication mandate",
)
async def get_publication_mandate(mandate_id: str) -> PublicationMandate:
    svc = get_trial_disclosure_service()
    mandate = svc.get_publication_mandate(mandate_id)
    if mandate is None:
        raise HTTPException(
            status_code=404, detail=f"Publication mandate '{mandate_id}' not found"
        )
    return mandate


@router.post(
    "/publication-mandates",
    response_model=PublicationMandate,
    status_code=201,
    summary="Create a publication mandate",
)
async def create_publication_mandate(payload: PublicationMandateCreate) -> PublicationMandate:
    svc = get_trial_disclosure_service()
    return svc.create_publication_mandate(payload)


@router.put(
    "/publication-mandates/{mandate_id}",
    response_model=PublicationMandate,
    summary="Update a publication mandate",
)
async def update_publication_mandate(
    mandate_id: str, payload: PublicationMandateUpdate
) -> PublicationMandate:
    svc = get_trial_disclosure_service()
    updated = svc.update_publication_mandate(mandate_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Publication mandate '{mandate_id}' not found"
        )
    return updated


@router.delete(
    "/publication-mandates/{mandate_id}",
    status_code=204,
    summary="Delete a publication mandate",
)
async def delete_publication_mandate(mandate_id: str) -> None:
    svc = get_trial_disclosure_service()
    deleted = svc.delete_publication_mandate(mandate_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Publication mandate '{mandate_id}' not found"
        )


# ---------------------------------------------------------------------------
# Lay Summaries
# ---------------------------------------------------------------------------


@router.get(
    "/lay-summaries",
    response_model=LaySummaryListResponse,
    summary="List lay summaries",
    description="Retrieve lay summaries with optional filtering by trial, audience, and status.",
)
async def list_lay_summaries(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    target_audience: Optional[SummaryAudience] = Query(None, description="Filter by audience"),
    status: Optional[DisclosureStatus] = Query(None, description="Filter by status"),
) -> LaySummaryListResponse:
    svc = get_trial_disclosure_service()
    items = svc.list_lay_summaries(
        trial_id=trial_id, target_audience=target_audience, status=status
    )
    return LaySummaryListResponse(items=items, total=len(items))


@router.get(
    "/lay-summaries/{summary_id}",
    response_model=LaySummary,
    summary="Get a lay summary",
)
async def get_lay_summary(summary_id: str) -> LaySummary:
    svc = get_trial_disclosure_service()
    summary = svc.get_lay_summary(summary_id)
    if summary is None:
        raise HTTPException(
            status_code=404, detail=f"Lay summary '{summary_id}' not found"
        )
    return summary


@router.post(
    "/lay-summaries",
    response_model=LaySummary,
    status_code=201,
    summary="Create a lay summary",
)
async def create_lay_summary(payload: LaySummaryCreate) -> LaySummary:
    svc = get_trial_disclosure_service()
    return svc.create_lay_summary(payload)


@router.put(
    "/lay-summaries/{summary_id}",
    response_model=LaySummary,
    summary="Update a lay summary",
)
async def update_lay_summary(
    summary_id: str, payload: LaySummaryUpdate
) -> LaySummary:
    svc = get_trial_disclosure_service()
    updated = svc.update_lay_summary(summary_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Lay summary '{summary_id}' not found"
        )
    return updated


@router.delete(
    "/lay-summaries/{summary_id}",
    status_code=204,
    summary="Delete a lay summary",
)
async def delete_lay_summary(summary_id: str) -> None:
    svc = get_trial_disclosure_service()
    deleted = svc.delete_lay_summary(summary_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Lay summary '{summary_id}' not found"
        )


# ---------------------------------------------------------------------------
# Compliance Timelines
# ---------------------------------------------------------------------------


@router.get(
    "/compliance-timelines",
    response_model=ComplianceTimelineListResponse,
    summary="List compliance timelines",
    description="Retrieve compliance timelines with optional filtering by trial and status.",
)
async def list_compliance_timelines(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[str] = Query(None, description="Filter by milestone status"),
) -> ComplianceTimelineListResponse:
    svc = get_trial_disclosure_service()
    items = svc.list_compliance_timelines(trial_id=trial_id, status=status)
    return ComplianceTimelineListResponse(items=items, total=len(items))


@router.get(
    "/compliance-timelines/{timeline_id}",
    response_model=ComplianceTimeline,
    summary="Get a compliance timeline",
)
async def get_compliance_timeline(timeline_id: str) -> ComplianceTimeline:
    svc = get_trial_disclosure_service()
    timeline = svc.get_compliance_timeline(timeline_id)
    if timeline is None:
        raise HTTPException(
            status_code=404, detail=f"Compliance timeline '{timeline_id}' not found"
        )
    return timeline


@router.post(
    "/compliance-timelines",
    response_model=ComplianceTimeline,
    status_code=201,
    summary="Create a compliance timeline",
)
async def create_compliance_timeline(payload: ComplianceTimelineCreate) -> ComplianceTimeline:
    svc = get_trial_disclosure_service()
    return svc.create_compliance_timeline(payload)


@router.put(
    "/compliance-timelines/{timeline_id}",
    response_model=ComplianceTimeline,
    summary="Update a compliance timeline",
)
async def update_compliance_timeline(
    timeline_id: str, payload: ComplianceTimelineUpdate
) -> ComplianceTimeline:
    svc = get_trial_disclosure_service()
    updated = svc.update_compliance_timeline(timeline_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Compliance timeline '{timeline_id}' not found"
        )
    return updated


@router.delete(
    "/compliance-timelines/{timeline_id}",
    status_code=204,
    summary="Delete a compliance timeline",
)
async def delete_compliance_timeline(timeline_id: str) -> None:
    svc = get_trial_disclosure_service()
    deleted = svc.delete_compliance_timeline(timeline_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Compliance timeline '{timeline_id}' not found"
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=TrialDisclosureMetrics,
    summary="Get trial disclosure metrics",
    description="Aggregated metrics across all trial disclosure operations.",
)
async def get_metrics() -> TrialDisclosureMetrics:
    svc = get_trial_disclosure_service()
    return svc.get_metrics()
