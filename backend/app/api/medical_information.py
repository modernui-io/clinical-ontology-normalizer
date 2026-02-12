"""Medical Information Services (MED-INFO) API endpoints.

Manages medical information operations: inquiry management, standard response
documents, product FAQ libraries, field medical insights, scientific
communication tracking, and medical information operational metrics.

Endpoints:
    GET    /medical-information/inquiries                          - List inquiries
    GET    /medical-information/inquiries/{inquiry_id}             - Get single inquiry
    POST   /medical-information/inquiries                          - Create inquiry
    PUT    /medical-information/inquiries/{inquiry_id}             - Update inquiry
    DELETE /medical-information/inquiries/{inquiry_id}             - Delete inquiry
    GET    /medical-information/standard-responses                 - List standard responses
    GET    /medical-information/standard-responses/{doc_id}        - Get single standard response
    POST   /medical-information/standard-responses                 - Create standard response
    PUT    /medical-information/standard-responses/{doc_id}        - Update standard response
    DELETE /medical-information/standard-responses/{doc_id}        - Delete standard response
    GET    /medical-information/faqs                               - List product FAQs
    GET    /medical-information/faqs/{faq_id}                      - Get single FAQ
    POST   /medical-information/faqs                               - Create FAQ
    PUT    /medical-information/faqs/{faq_id}                      - Update FAQ
    DELETE /medical-information/faqs/{faq_id}                      - Delete FAQ
    GET    /medical-information/insights                           - List field medical insights
    GET    /medical-information/insights/{insight_id}              - Get single insight
    POST   /medical-information/insights                           - Create insight
    PUT    /medical-information/insights/{insight_id}              - Update insight
    DELETE /medical-information/insights/{insight_id}              - Delete insight
    GET    /medical-information/communications                     - List scientific communications
    GET    /medical-information/communications/{comm_id}           - Get single communication
    POST   /medical-information/communications                     - Create communication
    PUT    /medical-information/communications/{comm_id}           - Update communication
    DELETE /medical-information/communications/{comm_id}           - Delete communication
    GET    /medical-information/metrics                            - Medical information metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.medical_information import (
    FieldMedicalInsight,
    FieldMedicalInsightCreate,
    FieldMedicalInsightListResponse,
    FieldMedicalInsightUpdate,
    MedicalInformationMetrics,
    MedicalInquiry,
    MedicalInquiryCreate,
    MedicalInquiryListResponse,
    MedicalInquiryUpdate,
    ProductFAQ,
    ProductFAQCreate,
    ProductFAQListResponse,
    ProductFAQUpdate,
    ScientificCommunication,
    ScientificCommunicationCreate,
    ScientificCommunicationListResponse,
    ScientificCommunicationUpdate,
    StandardResponseDoc,
    StandardResponseDocCreate,
    StandardResponseDocListResponse,
    StandardResponseDocUpdate,
)
from app.services.medical_information_service import get_medical_information_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/medical-information",
    tags=["Medical Information Services"],
)


# ---------------------------------------------------------------------------
# Medical Inquiries
# ---------------------------------------------------------------------------


@router.get(
    "/inquiries",
    response_model=MedicalInquiryListResponse,
    summary="List medical inquiries",
    description="Retrieve medical inquiries with optional filtering by trial and product.",
)
async def list_inquiries(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    product_name: Optional[str] = Query(None, description="Filter by product name"),
) -> MedicalInquiryListResponse:
    svc = get_medical_information_service()
    items = svc.list_inquiries(trial_id=trial_id, product_name=product_name)
    return MedicalInquiryListResponse(items=items, total=len(items))


@router.get(
    "/inquiries/{inquiry_id}",
    response_model=MedicalInquiry,
    summary="Get a medical inquiry",
)
async def get_inquiry(inquiry_id: str) -> MedicalInquiry:
    svc = get_medical_information_service()
    inquiry = svc.get_inquiry(inquiry_id)
    if inquiry is None:
        raise HTTPException(status_code=404, detail=f"Inquiry '{inquiry_id}' not found")
    return inquiry


@router.post(
    "/inquiries",
    response_model=MedicalInquiry,
    status_code=201,
    summary="Create a medical inquiry",
)
async def create_inquiry(payload: MedicalInquiryCreate) -> MedicalInquiry:
    svc = get_medical_information_service()
    return svc.create_inquiry(payload)


@router.put(
    "/inquiries/{inquiry_id}",
    response_model=MedicalInquiry,
    summary="Update a medical inquiry",
)
async def update_inquiry(
    inquiry_id: str, payload: MedicalInquiryUpdate
) -> MedicalInquiry:
    svc = get_medical_information_service()
    updated = svc.update_inquiry(inquiry_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Inquiry '{inquiry_id}' not found")
    return updated


@router.delete(
    "/inquiries/{inquiry_id}",
    status_code=204,
    summary="Delete a medical inquiry",
)
async def delete_inquiry(inquiry_id: str) -> None:
    svc = get_medical_information_service()
    deleted = svc.delete_inquiry(inquiry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Inquiry '{inquiry_id}' not found")


# ---------------------------------------------------------------------------
# Standard Response Documents
# ---------------------------------------------------------------------------


@router.get(
    "/standard-responses",
    response_model=StandardResponseDocListResponse,
    summary="List standard response documents",
    description="Retrieve standard response documents with optional filtering by product.",
)
async def list_standard_responses(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    product_name: Optional[str] = Query(None, description="Filter by product name"),
) -> StandardResponseDocListResponse:
    svc = get_medical_information_service()
    items = svc.list_standard_responses(trial_id=trial_id, product_name=product_name)
    return StandardResponseDocListResponse(items=items, total=len(items))


@router.get(
    "/standard-responses/{doc_id}",
    response_model=StandardResponseDoc,
    summary="Get a standard response document",
)
async def get_standard_response(doc_id: str) -> StandardResponseDoc:
    svc = get_medical_information_service()
    doc = svc.get_standard_response(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Standard response '{doc_id}' not found")
    return doc


@router.post(
    "/standard-responses",
    response_model=StandardResponseDoc,
    status_code=201,
    summary="Create a standard response document",
)
async def create_standard_response(payload: StandardResponseDocCreate) -> StandardResponseDoc:
    svc = get_medical_information_service()
    return svc.create_standard_response(payload)


@router.put(
    "/standard-responses/{doc_id}",
    response_model=StandardResponseDoc,
    summary="Update a standard response document",
)
async def update_standard_response(
    doc_id: str, payload: StandardResponseDocUpdate
) -> StandardResponseDoc:
    svc = get_medical_information_service()
    updated = svc.update_standard_response(doc_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Standard response '{doc_id}' not found")
    return updated


@router.delete(
    "/standard-responses/{doc_id}",
    status_code=204,
    summary="Delete a standard response document",
)
async def delete_standard_response(doc_id: str) -> None:
    svc = get_medical_information_service()
    deleted = svc.delete_standard_response(doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Standard response '{doc_id}' not found")


# ---------------------------------------------------------------------------
# Product FAQs
# ---------------------------------------------------------------------------


@router.get(
    "/faqs",
    response_model=ProductFAQListResponse,
    summary="List product FAQs",
    description="Retrieve product FAQs with optional filtering by product.",
)
async def list_faqs(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    product_name: Optional[str] = Query(None, description="Filter by product name"),
) -> ProductFAQListResponse:
    svc = get_medical_information_service()
    items = svc.list_faqs(trial_id=trial_id, product_name=product_name)
    return ProductFAQListResponse(items=items, total=len(items))


@router.get(
    "/faqs/{faq_id}",
    response_model=ProductFAQ,
    summary="Get a product FAQ",
)
async def get_faq(faq_id: str) -> ProductFAQ:
    svc = get_medical_information_service()
    faq = svc.get_faq(faq_id)
    if faq is None:
        raise HTTPException(status_code=404, detail=f"FAQ '{faq_id}' not found")
    return faq


@router.post(
    "/faqs",
    response_model=ProductFAQ,
    status_code=201,
    summary="Create a product FAQ",
)
async def create_faq(payload: ProductFAQCreate) -> ProductFAQ:
    svc = get_medical_information_service()
    return svc.create_faq(payload)


@router.put(
    "/faqs/{faq_id}",
    response_model=ProductFAQ,
    summary="Update a product FAQ",
)
async def update_faq(faq_id: str, payload: ProductFAQUpdate) -> ProductFAQ:
    svc = get_medical_information_service()
    updated = svc.update_faq(faq_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"FAQ '{faq_id}' not found")
    return updated


@router.delete(
    "/faqs/{faq_id}",
    status_code=204,
    summary="Delete a product FAQ",
)
async def delete_faq(faq_id: str) -> None:
    svc = get_medical_information_service()
    deleted = svc.delete_faq(faq_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"FAQ '{faq_id}' not found")


# ---------------------------------------------------------------------------
# Field Medical Insights
# ---------------------------------------------------------------------------


@router.get(
    "/insights",
    response_model=FieldMedicalInsightListResponse,
    summary="List field medical insights",
    description="Retrieve field medical insights with optional filtering by trial and product.",
)
async def list_insights(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    product_name: Optional[str] = Query(None, description="Filter by product name"),
) -> FieldMedicalInsightListResponse:
    svc = get_medical_information_service()
    items = svc.list_insights(trial_id=trial_id, product_name=product_name)
    return FieldMedicalInsightListResponse(items=items, total=len(items))


@router.get(
    "/insights/{insight_id}",
    response_model=FieldMedicalInsight,
    summary="Get a field medical insight",
)
async def get_insight(insight_id: str) -> FieldMedicalInsight:
    svc = get_medical_information_service()
    insight = svc.get_insight(insight_id)
    if insight is None:
        raise HTTPException(status_code=404, detail=f"Insight '{insight_id}' not found")
    return insight


@router.post(
    "/insights",
    response_model=FieldMedicalInsight,
    status_code=201,
    summary="Create a field medical insight",
)
async def create_insight(payload: FieldMedicalInsightCreate) -> FieldMedicalInsight:
    svc = get_medical_information_service()
    return svc.create_insight(payload)


@router.put(
    "/insights/{insight_id}",
    response_model=FieldMedicalInsight,
    summary="Update a field medical insight",
)
async def update_insight(
    insight_id: str, payload: FieldMedicalInsightUpdate
) -> FieldMedicalInsight:
    svc = get_medical_information_service()
    updated = svc.update_insight(insight_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Insight '{insight_id}' not found")
    return updated


@router.delete(
    "/insights/{insight_id}",
    status_code=204,
    summary="Delete a field medical insight",
)
async def delete_insight(insight_id: str) -> None:
    svc = get_medical_information_service()
    deleted = svc.delete_insight(insight_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Insight '{insight_id}' not found")


# ---------------------------------------------------------------------------
# Scientific Communications
# ---------------------------------------------------------------------------


@router.get(
    "/communications",
    response_model=ScientificCommunicationListResponse,
    summary="List scientific communications",
    description="Retrieve scientific communications with optional filtering by product.",
)
async def list_communications(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    product_name: Optional[str] = Query(None, description="Filter by product name"),
) -> ScientificCommunicationListResponse:
    svc = get_medical_information_service()
    items = svc.list_communications(trial_id=trial_id, product_name=product_name)
    return ScientificCommunicationListResponse(items=items, total=len(items))


@router.get(
    "/communications/{comm_id}",
    response_model=ScientificCommunication,
    summary="Get a scientific communication",
)
async def get_communication(comm_id: str) -> ScientificCommunication:
    svc = get_medical_information_service()
    comm = svc.get_communication(comm_id)
    if comm is None:
        raise HTTPException(status_code=404, detail=f"Communication '{comm_id}' not found")
    return comm


@router.post(
    "/communications",
    response_model=ScientificCommunication,
    status_code=201,
    summary="Create a scientific communication",
)
async def create_communication(payload: ScientificCommunicationCreate) -> ScientificCommunication:
    svc = get_medical_information_service()
    return svc.create_communication(payload)


@router.put(
    "/communications/{comm_id}",
    response_model=ScientificCommunication,
    summary="Update a scientific communication",
)
async def update_communication(
    comm_id: str, payload: ScientificCommunicationUpdate
) -> ScientificCommunication:
    svc = get_medical_information_service()
    updated = svc.update_communication(comm_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Communication '{comm_id}' not found")
    return updated


@router.delete(
    "/communications/{comm_id}",
    status_code=204,
    summary="Delete a scientific communication",
)
async def delete_communication(comm_id: str) -> None:
    svc = get_medical_information_service()
    deleted = svc.delete_communication(comm_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Communication '{comm_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=MedicalInformationMetrics,
    summary="Get medical information metrics",
    description="Aggregated medical information metrics including inquiry volumes, "
                "turnaround times, response document counts, and communication statistics.",
)
async def get_metrics() -> MedicalInformationMetrics:
    svc = get_medical_information_service()
    return svc.get_metrics()
