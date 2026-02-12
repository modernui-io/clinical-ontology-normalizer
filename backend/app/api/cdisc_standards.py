"""CDISC Standards Management API endpoints (CDISC-STD).

Provides comprehensive CDISC compliance operations: SDTM domain mapping,
ADaM dataset definitions, controlled terminology management, define.xml
generation, conformance validation, and CDISC operational metrics.

Endpoints:
    GET    /cdisc-standards/sdtm-domains                     - List SDTM domains
    GET    /cdisc-standards/sdtm-domains/{domain_id}         - Get single SDTM domain
    POST   /cdisc-standards/sdtm-domains                     - Create SDTM domain
    PUT    /cdisc-standards/sdtm-domains/{domain_id}         - Update SDTM domain
    DELETE /cdisc-standards/sdtm-domains/{domain_id}         - Delete SDTM domain
    GET    /cdisc-standards/adam-datasets                     - List ADaM datasets
    GET    /cdisc-standards/adam-datasets/{dataset_id}        - Get single ADaM dataset
    POST   /cdisc-standards/adam-datasets                     - Create ADaM dataset
    PUT    /cdisc-standards/adam-datasets/{dataset_id}        - Update ADaM dataset
    DELETE /cdisc-standards/adam-datasets/{dataset_id}        - Delete ADaM dataset
    GET    /cdisc-standards/controlled-terms                  - List controlled terms
    GET    /cdisc-standards/controlled-terms/{term_id}        - Get single controlled term
    POST   /cdisc-standards/controlled-terms                  - Create controlled term
    DELETE /cdisc-standards/controlled-terms/{term_id}        - Delete controlled term
    GET    /cdisc-standards/define-xmls                       - List Define XMLs
    GET    /cdisc-standards/define-xmls/{define_id}           - Get single Define XML
    POST   /cdisc-standards/define-xmls                       - Create Define XML
    PUT    /cdisc-standards/define-xmls/{define_id}           - Update Define XML
    DELETE /cdisc-standards/define-xmls/{define_id}           - Delete Define XML
    GET    /cdisc-standards/conformance-results               - List conformance results
    GET    /cdisc-standards/conformance-results/{result_id}   - Get single conformance result
    POST   /cdisc-standards/conformance-results               - Create conformance result
    PUT    /cdisc-standards/conformance-results/{result_id}   - Update conformance result
    DELETE /cdisc-standards/conformance-results/{result_id}   - Delete conformance result
    GET    /cdisc-standards/metrics                           - CDISC metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.cdisc_standards import (
    ADaMDataset,
    ADaMDatasetCreate,
    ADaMDatasetListResponse,
    ADaMDatasetUpdate,
    CDISCMetrics,
    ConformanceResult,
    ConformanceResultCreate,
    ConformanceResultListResponse,
    ConformanceResultUpdate,
    ControlledTerm,
    ControlledTermCreate,
    ControlledTermListResponse,
    DefineXML,
    DefineXMLCreate,
    DefineXMLListResponse,
    DefineXMLUpdate,
    SDTMDomain,
    SDTMDomainCreate,
    SDTMDomainListResponse,
    SDTMDomainUpdate,
)
from app.services.cdisc_standards_service import get_cdisc_standards_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/cdisc-standards",
    tags=["CDISC Standards Management"],
)


# ---------------------------------------------------------------------------
# SDTM Domains
# ---------------------------------------------------------------------------


@router.get(
    "/sdtm-domains",
    response_model=SDTMDomainListResponse,
    summary="List SDTM domains",
    description="Retrieve SDTM domains with optional filtering by trial.",
)
async def list_sdtm_domains(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> SDTMDomainListResponse:
    svc = get_cdisc_standards_service()
    items = svc.list_sdtm_domains(trial_id=trial_id)
    return SDTMDomainListResponse(items=items, total=len(items))


@router.get(
    "/sdtm-domains/{domain_id}",
    response_model=SDTMDomain,
    summary="Get an SDTM domain",
)
async def get_sdtm_domain(domain_id: str) -> SDTMDomain:
    svc = get_cdisc_standards_service()
    domain = svc.get_sdtm_domain(domain_id)
    if domain is None:
        raise HTTPException(status_code=404, detail=f"SDTM domain '{domain_id}' not found")
    return domain


@router.post(
    "/sdtm-domains",
    response_model=SDTMDomain,
    status_code=201,
    summary="Create an SDTM domain",
)
async def create_sdtm_domain(payload: SDTMDomainCreate) -> SDTMDomain:
    svc = get_cdisc_standards_service()
    return svc.create_sdtm_domain(payload)


@router.put(
    "/sdtm-domains/{domain_id}",
    response_model=SDTMDomain,
    summary="Update an SDTM domain",
)
async def update_sdtm_domain(
    domain_id: str, payload: SDTMDomainUpdate
) -> SDTMDomain:
    svc = get_cdisc_standards_service()
    updated = svc.update_sdtm_domain(domain_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"SDTM domain '{domain_id}' not found")
    return updated


@router.delete(
    "/sdtm-domains/{domain_id}",
    status_code=204,
    summary="Delete an SDTM domain",
)
async def delete_sdtm_domain(domain_id: str) -> None:
    svc = get_cdisc_standards_service()
    deleted = svc.delete_sdtm_domain(domain_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"SDTM domain '{domain_id}' not found")


# ---------------------------------------------------------------------------
# ADaM Datasets
# ---------------------------------------------------------------------------


@router.get(
    "/adam-datasets",
    response_model=ADaMDatasetListResponse,
    summary="List ADaM datasets",
    description="Retrieve ADaM datasets with optional filtering by trial.",
)
async def list_adam_datasets(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> ADaMDatasetListResponse:
    svc = get_cdisc_standards_service()
    items = svc.list_adam_datasets(trial_id=trial_id)
    return ADaMDatasetListResponse(items=items, total=len(items))


@router.get(
    "/adam-datasets/{dataset_id}",
    response_model=ADaMDataset,
    summary="Get an ADaM dataset",
)
async def get_adam_dataset(dataset_id: str) -> ADaMDataset:
    svc = get_cdisc_standards_service()
    dataset = svc.get_adam_dataset(dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail=f"ADaM dataset '{dataset_id}' not found")
    return dataset


@router.post(
    "/adam-datasets",
    response_model=ADaMDataset,
    status_code=201,
    summary="Create an ADaM dataset",
)
async def create_adam_dataset(payload: ADaMDatasetCreate) -> ADaMDataset:
    svc = get_cdisc_standards_service()
    return svc.create_adam_dataset(payload)


@router.put(
    "/adam-datasets/{dataset_id}",
    response_model=ADaMDataset,
    summary="Update an ADaM dataset",
)
async def update_adam_dataset(
    dataset_id: str, payload: ADaMDatasetUpdate
) -> ADaMDataset:
    svc = get_cdisc_standards_service()
    updated = svc.update_adam_dataset(dataset_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"ADaM dataset '{dataset_id}' not found")
    return updated


@router.delete(
    "/adam-datasets/{dataset_id}",
    status_code=204,
    summary="Delete an ADaM dataset",
)
async def delete_adam_dataset(dataset_id: str) -> None:
    svc = get_cdisc_standards_service()
    deleted = svc.delete_adam_dataset(dataset_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"ADaM dataset '{dataset_id}' not found")


# ---------------------------------------------------------------------------
# Controlled Terms
# ---------------------------------------------------------------------------


@router.get(
    "/controlled-terms",
    response_model=ControlledTermListResponse,
    summary="List controlled terms",
    description="Retrieve controlled terms with optional filtering by trial.",
)
async def list_controlled_terms(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> ControlledTermListResponse:
    svc = get_cdisc_standards_service()
    items = svc.list_controlled_terms(trial_id=trial_id)
    return ControlledTermListResponse(items=items, total=len(items))


@router.get(
    "/controlled-terms/{term_id}",
    response_model=ControlledTerm,
    summary="Get a controlled term",
)
async def get_controlled_term(term_id: str) -> ControlledTerm:
    svc = get_cdisc_standards_service()
    term = svc.get_controlled_term(term_id)
    if term is None:
        raise HTTPException(status_code=404, detail=f"Controlled term '{term_id}' not found")
    return term


@router.post(
    "/controlled-terms",
    response_model=ControlledTerm,
    status_code=201,
    summary="Create a controlled term",
)
async def create_controlled_term(payload: ControlledTermCreate) -> ControlledTerm:
    svc = get_cdisc_standards_service()
    return svc.create_controlled_term(payload)


@router.delete(
    "/controlled-terms/{term_id}",
    status_code=204,
    summary="Delete a controlled term",
)
async def delete_controlled_term(term_id: str) -> None:
    svc = get_cdisc_standards_service()
    deleted = svc.delete_controlled_term(term_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Controlled term '{term_id}' not found")


# ---------------------------------------------------------------------------
# Define XMLs
# ---------------------------------------------------------------------------


@router.get(
    "/define-xmls",
    response_model=DefineXMLListResponse,
    summary="List Define XMLs",
    description="Retrieve Define XML documents with optional filtering by trial.",
)
async def list_define_xmls(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> DefineXMLListResponse:
    svc = get_cdisc_standards_service()
    items = svc.list_define_xmls(trial_id=trial_id)
    return DefineXMLListResponse(items=items, total=len(items))


@router.get(
    "/define-xmls/{define_id}",
    response_model=DefineXML,
    summary="Get a Define XML",
)
async def get_define_xml(define_id: str) -> DefineXML:
    svc = get_cdisc_standards_service()
    define = svc.get_define_xml(define_id)
    if define is None:
        raise HTTPException(status_code=404, detail=f"Define XML '{define_id}' not found")
    return define


@router.post(
    "/define-xmls",
    response_model=DefineXML,
    status_code=201,
    summary="Create a Define XML",
)
async def create_define_xml(payload: DefineXMLCreate) -> DefineXML:
    svc = get_cdisc_standards_service()
    return svc.create_define_xml(payload)


@router.put(
    "/define-xmls/{define_id}",
    response_model=DefineXML,
    summary="Update a Define XML",
)
async def update_define_xml(
    define_id: str, payload: DefineXMLUpdate
) -> DefineXML:
    svc = get_cdisc_standards_service()
    updated = svc.update_define_xml(define_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Define XML '{define_id}' not found")
    return updated


@router.delete(
    "/define-xmls/{define_id}",
    status_code=204,
    summary="Delete a Define XML",
)
async def delete_define_xml(define_id: str) -> None:
    svc = get_cdisc_standards_service()
    deleted = svc.delete_define_xml(define_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Define XML '{define_id}' not found")


# ---------------------------------------------------------------------------
# Conformance Results
# ---------------------------------------------------------------------------


@router.get(
    "/conformance-results",
    response_model=ConformanceResultListResponse,
    summary="List conformance results",
    description="Retrieve conformance validation results with optional filtering by trial.",
)
async def list_conformance_results(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> ConformanceResultListResponse:
    svc = get_cdisc_standards_service()
    items = svc.list_conformance_results(trial_id=trial_id)
    return ConformanceResultListResponse(items=items, total=len(items))


@router.get(
    "/conformance-results/{result_id}",
    response_model=ConformanceResult,
    summary="Get a conformance result",
)
async def get_conformance_result(result_id: str) -> ConformanceResult:
    svc = get_cdisc_standards_service()
    result = svc.get_conformance_result(result_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Conformance result '{result_id}' not found")
    return result


@router.post(
    "/conformance-results",
    response_model=ConformanceResult,
    status_code=201,
    summary="Create a conformance result",
)
async def create_conformance_result(payload: ConformanceResultCreate) -> ConformanceResult:
    svc = get_cdisc_standards_service()
    return svc.create_conformance_result(payload)


@router.put(
    "/conformance-results/{result_id}",
    response_model=ConformanceResult,
    summary="Update a conformance result",
)
async def update_conformance_result(
    result_id: str, payload: ConformanceResultUpdate
) -> ConformanceResult:
    svc = get_cdisc_standards_service()
    updated = svc.update_conformance_result(result_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Conformance result '{result_id}' not found")
    return updated


@router.delete(
    "/conformance-results/{result_id}",
    status_code=204,
    summary="Delete a conformance result",
)
async def delete_conformance_result(result_id: str) -> None:
    svc = get_cdisc_standards_service()
    deleted = svc.delete_conformance_result(result_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Conformance result '{result_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=CDISCMetrics,
    summary="Get CDISC standards metrics",
    description="Aggregated CDISC metrics including SDTM mapping progress, ADaM status, "
                "controlled terminology counts, Define XML validation, and conformance results.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter metrics by trial ID"),
) -> CDISCMetrics:
    svc = get_cdisc_standards_service()
    return svc.get_metrics(trial_id=trial_id)
