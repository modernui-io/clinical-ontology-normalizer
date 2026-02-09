"""Electronic Trial Master File (eTMF) API endpoints (CLINICAL-5).

Provides comprehensive eTMF management: document lifecycle, compliance rules,
inspection readiness, zone completeness, Part 11 / GDPR compliance, metrics,
and bulk import per the DIA TMF Reference Model.

Endpoints:
    GET    /etmf/documents                                - List documents with filters
    GET    /etmf/documents/{id}                           - Get document detail
    POST   /etmf/documents                                - Create document
    PUT    /etmf/documents/{id}                           - Update document
    DELETE /etmf/documents/{id}                           - Delete document
    POST   /etmf/documents/{id}/review                    - Submit for review
    POST   /etmf/documents/{id}/approve                   - Approve document
    POST   /etmf/documents/{id}/make-effective             - Make effective
    POST   /etmf/documents/{id}/sign                      - Add signature
    POST   /etmf/documents/{id}/new-version               - Create new version
    POST   /etmf/documents/bulk-import                    - Bulk import
    GET    /etmf/documents/expiring                       - Expiring documents
    GET    /etmf/zones/{trial_id}/completeness            - Zone completeness
    GET    /etmf/zones/{trial_id}/missing                 - Missing documents
    GET    /etmf/zones/{trial_id}/readiness               - Inspection readiness
    GET    /etmf/compliance-rules                         - List compliance rules
    GET    /etmf/compliance-rules/{id}                    - Get compliance rule
    POST   /etmf/compliance-rules                         - Create compliance rule
    PUT    /etmf/compliance-rules/{id}                    - Update compliance rule
    DELETE /etmf/compliance-rules/{id}                    - Delete compliance rule
    GET    /etmf/compliance/part11                        - Part 11 compliance
    GET    /etmf/compliance/gdpr                          - GDPR compliance
    GET    /etmf/metrics                                  - TMF metrics
    GET    /etmf/inspection-checklists                    - List checklists
    GET    /etmf/inspection-checklists/{id}               - Get checklist
    POST   /etmf/inspection-checklists                    - Create checklist
    DELETE /etmf/inspection-checklists/{id}               - Delete checklist
    POST   /etmf/inspection-checklists/{id}/findings      - Add finding
    POST   /etmf/inspection-checklists/{id}/findings/{idx}/resolve - Resolve finding
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.etmf import (
    ArtifactType,
    BulkImportRequest,
    BulkImportResponse,
    ComplianceRule,
    ComplianceRuleCreate,
    ComplianceRuleListResponse,
    ComplianceRuleUpdate,
    ComplianceStatus,
    DocumentApprovalRequest,
    DocumentReviewRequest,
    DocumentStatus,
    ExpiringDocumentsResponse,
    InspectionChecklist,
    InspectionChecklistCreate,
    InspectionChecklistListResponse,
    InspectionFindingCreate,
    InspectionReadiness,
    MissingDocumentsResponse,
    SignatureRequest,
    TMFDocument,
    TMFDocumentCreate,
    TMFDocumentListResponse,
    TMFDocumentUpdate,
    TMFMetrics,
    TMFSectionListResponse,
    TMFZone,
)
from app.services.etmf_service import get_etmf_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/etmf",
    tags=["Electronic Trial Master File"],
)


# ---------------------------------------------------------------------------
# Document CRUD
# ---------------------------------------------------------------------------


@router.get("/documents", response_model=TMFDocumentListResponse)
async def list_documents(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    zone: Optional[TMFZone] = Query(None, description="Filter by TMF zone"),
    artifact_type: Optional[ArtifactType] = Query(None, description="Filter by artifact type"),
    status: Optional[DocumentStatus] = Query(None, description="Filter by status"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    country: Optional[str] = Query(None, description="Filter by country"),
    limit: int = Query(50, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset"),
) -> TMFDocumentListResponse:
    """List TMF documents with optional filters."""
    svc = get_etmf_service()
    items, total = svc.list_documents(
        trial_id=trial_id,
        zone=zone,
        artifact_type=artifact_type,
        status=status,
        site_id=site_id,
        country=country,
        limit=limit,
        offset=offset,
    )
    return TMFDocumentListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/documents/expiring", response_model=ExpiringDocumentsResponse)
async def get_expiring_documents(
    days_ahead: int = Query(30, ge=1, le=365, description="Look-ahead window in days"),
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> ExpiringDocumentsResponse:
    """Get documents expiring within the specified window."""
    svc = get_etmf_service()
    items = svc.get_expiring_documents(days_ahead=days_ahead, trial_id=trial_id)
    return ExpiringDocumentsResponse(items=items, total=len(items), days_ahead=days_ahead)


@router.get("/documents/{document_id}", response_model=TMFDocument)
async def get_document(document_id: str) -> TMFDocument:
    """Get a specific TMF document."""
    svc = get_etmf_service()
    doc = svc.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    return doc


@router.post("/documents", response_model=TMFDocument, status_code=201)
async def create_document(req: TMFDocumentCreate) -> TMFDocument:
    """Create a new TMF document."""
    svc = get_etmf_service()
    return svc.create_document(req)


@router.put("/documents/{document_id}", response_model=TMFDocument)
async def update_document(document_id: str, req: TMFDocumentUpdate) -> TMFDocument:
    """Update a TMF document."""
    svc = get_etmf_service()
    try:
        doc = svc.update_document(document_id, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    return doc


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(document_id: str) -> None:
    """Delete a TMF document."""
    svc = get_etmf_service()
    if not svc.delete_document(document_id):
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")


# ---------------------------------------------------------------------------
# Approval Workflow
# ---------------------------------------------------------------------------


@router.post("/documents/{document_id}/review", response_model=TMFDocument)
async def submit_for_review(document_id: str, req: DocumentReviewRequest) -> TMFDocument:
    """Submit a document for review (DRAFT -> UNDER_REVIEW)."""
    svc = get_etmf_service()
    try:
        doc = svc.submit_for_review(document_id, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    return doc


@router.post("/documents/{document_id}/approve", response_model=TMFDocument)
async def approve_document(document_id: str, req: DocumentApprovalRequest) -> TMFDocument:
    """Approve a document (UNDER_REVIEW -> APPROVED)."""
    svc = get_etmf_service()
    try:
        doc = svc.approve_document(document_id, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    return doc


@router.post("/documents/{document_id}/make-effective", response_model=TMFDocument)
async def make_effective(document_id: str) -> TMFDocument:
    """Make an approved document effective (APPROVED -> EFFECTIVE)."""
    svc = get_etmf_service()
    try:
        doc = svc.make_effective(document_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    return doc


@router.post("/documents/{document_id}/sign", response_model=TMFDocument)
async def add_signature(document_id: str, req: SignatureRequest) -> TMFDocument:
    """Add a signature to a document."""
    svc = get_etmf_service()
    doc = svc.add_signature(document_id, req)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    return doc


@router.post("/documents/{document_id}/new-version", response_model=TMFDocument)
async def create_new_version(
    document_id: str,
    new_version: str = Query(..., description="New version string"),
) -> TMFDocument:
    """Create a new version of a document (supersedes the original)."""
    svc = get_etmf_service()
    doc = svc.create_new_version(document_id, new_version)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    return doc


@router.post("/documents/bulk-import", response_model=BulkImportResponse)
async def bulk_import(req: BulkImportRequest) -> BulkImportResponse:
    """Bulk import TMF documents."""
    svc = get_etmf_service()
    return svc.bulk_import(req)


# ---------------------------------------------------------------------------
# Zone Completeness & Missing Documents
# ---------------------------------------------------------------------------


@router.get("/zones/{trial_id}/completeness", response_model=TMFSectionListResponse)
async def get_zone_completeness(trial_id: str) -> TMFSectionListResponse:
    """Get zone completeness analysis for a trial."""
    svc = get_etmf_service()
    sections = svc.get_zone_completeness(trial_id)
    return TMFSectionListResponse(items=sections, total=len(sections))


@router.get("/zones/{trial_id}/missing", response_model=MissingDocumentsResponse)
async def get_missing_documents(trial_id: str) -> MissingDocumentsResponse:
    """Identify missing documents for a trial."""
    svc = get_etmf_service()
    return svc.get_missing_documents(trial_id)


@router.get("/zones/{trial_id}/readiness", response_model=dict)
async def get_inspection_readiness(trial_id: str) -> dict:
    """Assess inspection readiness for a trial."""
    svc = get_etmf_service()
    readiness = svc.assess_inspection_readiness(trial_id)
    return {"trial_id": trial_id, "inspection_readiness": readiness.value}


# ---------------------------------------------------------------------------
# Compliance Rules
# ---------------------------------------------------------------------------


@router.get("/compliance-rules", response_model=ComplianceRuleListResponse)
async def list_compliance_rules(
    zone: Optional[TMFZone] = Query(None, description="Filter by zone"),
    artifact_type: Optional[ArtifactType] = Query(None, description="Filter by artifact type"),
) -> ComplianceRuleListResponse:
    """List compliance rules."""
    svc = get_etmf_service()
    rules = svc.list_compliance_rules(zone=zone, artifact_type=artifact_type)
    return ComplianceRuleListResponse(items=rules, total=len(rules))


@router.get("/compliance-rules/{rule_id}", response_model=ComplianceRule)
async def get_compliance_rule(rule_id: str) -> ComplianceRule:
    """Get a specific compliance rule."""
    svc = get_etmf_service()
    rule = svc.get_compliance_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Compliance rule {rule_id} not found")
    return rule


@router.post("/compliance-rules", response_model=ComplianceRule, status_code=201)
async def create_compliance_rule(req: ComplianceRuleCreate) -> ComplianceRule:
    """Create a new compliance rule."""
    svc = get_etmf_service()
    return svc.create_compliance_rule(req)


@router.put("/compliance-rules/{rule_id}", response_model=ComplianceRule)
async def update_compliance_rule(rule_id: str, req: ComplianceRuleUpdate) -> ComplianceRule:
    """Update a compliance rule."""
    svc = get_etmf_service()
    rule = svc.update_compliance_rule(rule_id, req)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Compliance rule {rule_id} not found")
    return rule


@router.delete("/compliance-rules/{rule_id}", status_code=204)
async def delete_compliance_rule(rule_id: str) -> None:
    """Delete a compliance rule."""
    svc = get_etmf_service()
    if not svc.delete_compliance_rule(rule_id):
        raise HTTPException(status_code=404, detail=f"Compliance rule {rule_id} not found")


# ---------------------------------------------------------------------------
# Part 11 / GDPR Compliance
# ---------------------------------------------------------------------------


@router.get("/compliance/part11", response_model=dict)
async def check_part11_compliance(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> dict:
    """Check 21 CFR Part 11 compliance."""
    svc = get_etmf_service()
    return svc.check_part11_compliance(trial_id)


@router.get("/compliance/gdpr", response_model=dict)
async def check_gdpr_compliance(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> dict:
    """Check GDPR compliance."""
    svc = get_etmf_service()
    return svc.check_gdpr_compliance(trial_id)


# ---------------------------------------------------------------------------
# TMF Metrics
# ---------------------------------------------------------------------------


@router.get("/metrics", response_model=TMFMetrics)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> TMFMetrics:
    """Get aggregated eTMF metrics."""
    svc = get_etmf_service()
    return svc.get_metrics(trial_id)


# ---------------------------------------------------------------------------
# Inspection Checklists
# ---------------------------------------------------------------------------


@router.get("/inspection-checklists", response_model=InspectionChecklistListResponse)
async def list_inspection_checklists(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> InspectionChecklistListResponse:
    """List inspection checklists."""
    svc = get_etmf_service()
    items = svc.list_inspection_checklists(trial_id=trial_id)
    return InspectionChecklistListResponse(items=items, total=len(items))


@router.get("/inspection-checklists/{checklist_id}", response_model=InspectionChecklist)
async def get_inspection_checklist(checklist_id: str) -> InspectionChecklist:
    """Get a specific inspection checklist."""
    svc = get_etmf_service()
    chk = svc.get_inspection_checklist(checklist_id)
    if not chk:
        raise HTTPException(status_code=404, detail=f"Checklist {checklist_id} not found")
    return chk


@router.post("/inspection-checklists", response_model=InspectionChecklist, status_code=201)
async def create_inspection_checklist(req: InspectionChecklistCreate) -> InspectionChecklist:
    """Create a new inspection checklist."""
    svc = get_etmf_service()
    return svc.create_inspection_checklist(req)


@router.delete("/inspection-checklists/{checklist_id}", status_code=204)
async def delete_inspection_checklist(checklist_id: str) -> None:
    """Delete an inspection checklist."""
    svc = get_etmf_service()
    if not svc.delete_inspection_checklist(checklist_id):
        raise HTTPException(status_code=404, detail=f"Checklist {checklist_id} not found")


@router.post(
    "/inspection-checklists/{checklist_id}/findings",
    response_model=InspectionChecklist,
)
async def add_inspection_finding(
    checklist_id: str, req: InspectionFindingCreate
) -> InspectionChecklist:
    """Add a finding to an inspection checklist."""
    svc = get_etmf_service()
    chk = svc.add_inspection_finding(checklist_id, req)
    if not chk:
        raise HTTPException(status_code=404, detail=f"Checklist {checklist_id} not found")
    return chk


@router.post(
    "/inspection-checklists/{checklist_id}/findings/{finding_index}/resolve",
    response_model=InspectionChecklist,
)
async def resolve_inspection_finding(
    checklist_id: str, finding_index: int
) -> InspectionChecklist:
    """Resolve a finding in an inspection checklist."""
    svc = get_etmf_service()
    try:
        chk = svc.resolve_inspection_finding(checklist_id, finding_index)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not chk:
        raise HTTPException(status_code=404, detail=f"Checklist {checklist_id} not found")
    return chk
