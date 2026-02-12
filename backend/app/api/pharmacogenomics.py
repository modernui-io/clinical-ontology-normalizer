"""Pharmacogenomics Management (PGx-MGT) API endpoints.

Provides comprehensive pharmacogenomics operations: drug-gene interaction tracking,
genotype-phenotype mapping, PGx test order management, variant result interpretation,
dosing recommendation generation, and pharmacogenomics operational metrics.

Endpoints:
    GET    /pharmacogenomics/drug-gene-interactions                         - List interactions
    GET    /pharmacogenomics/drug-gene-interactions/{interaction_id}        - Get interaction
    POST   /pharmacogenomics/drug-gene-interactions                         - Create interaction
    PUT    /pharmacogenomics/drug-gene-interactions/{interaction_id}        - Update interaction
    DELETE /pharmacogenomics/drug-gene-interactions/{interaction_id}        - Delete interaction
    GET    /pharmacogenomics/genotype-phenotypes                            - List genotype-phenotypes
    GET    /pharmacogenomics/genotype-phenotypes/{gp_id}                   - Get genotype-phenotype
    POST   /pharmacogenomics/genotype-phenotypes                            - Create genotype-phenotype
    PUT    /pharmacogenomics/genotype-phenotypes/{gp_id}                   - Update genotype-phenotype
    DELETE /pharmacogenomics/genotype-phenotypes/{gp_id}                   - Delete genotype-phenotype
    GET    /pharmacogenomics/test-orders                                    - List test orders
    GET    /pharmacogenomics/test-orders/{order_id}                        - Get test order
    POST   /pharmacogenomics/test-orders                                    - Create test order
    PUT    /pharmacogenomics/test-orders/{order_id}                        - Update test order
    DELETE /pharmacogenomics/test-orders/{order_id}                        - Delete test order
    GET    /pharmacogenomics/variant-results                                - List variant results
    GET    /pharmacogenomics/variant-results/{result_id}                   - Get variant result
    POST   /pharmacogenomics/variant-results                                - Create variant result
    PUT    /pharmacogenomics/variant-results/{result_id}                   - Update variant result
    DELETE /pharmacogenomics/variant-results/{result_id}                   - Delete variant result
    GET    /pharmacogenomics/dosing-recommendations                         - List dosing recommendations
    GET    /pharmacogenomics/dosing-recommendations/{rec_id}               - Get dosing recommendation
    POST   /pharmacogenomics/dosing-recommendations                         - Create dosing recommendation
    PUT    /pharmacogenomics/dosing-recommendations/{rec_id}               - Update dosing recommendation
    DELETE /pharmacogenomics/dosing-recommendations/{rec_id}               - Delete dosing recommendation
    GET    /pharmacogenomics/metrics                                        - Pharmacogenomics metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.pharmacogenomics import (
    DosingRecommendation,
    DosingRecommendationCreate,
    DosingRecommendationListResponse,
    DosingRecommendationUpdate,
    DrugGeneInteraction,
    DrugGeneInteractionCreate,
    DrugGeneInteractionListResponse,
    DrugGeneInteractionUpdate,
    GenotypePhenotype,
    GenotypePhenotypeCreate,
    GenotypePhenotypeListResponse,
    GenotypePhenotypeUpdate,
    PGxTestOrder,
    PGxTestOrderCreate,
    PGxTestOrderListResponse,
    PGxTestOrderUpdate,
    PharmacogenomicsMetrics,
    VariantResult,
    VariantResultCreate,
    VariantResultListResponse,
    VariantResultUpdate,
)
from app.services.pharmacogenomics_service import get_pharmacogenomics_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/pharmacogenomics",
    tags=["Pharmacogenomics Management"],
)


# ---------------------------------------------------------------------------
# Drug-Gene Interactions
# ---------------------------------------------------------------------------


@router.get(
    "/drug-gene-interactions",
    response_model=DrugGeneInteractionListResponse,
    summary="List drug-gene interactions",
    description="Retrieve drug-gene interactions with optional filtering.",
)
async def list_drug_gene_interactions(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> DrugGeneInteractionListResponse:
    svc = get_pharmacogenomics_service()
    items = svc.list_drug_gene_interactions(trial_id=trial_id)
    return DrugGeneInteractionListResponse(items=items, total=len(items))


@router.get(
    "/drug-gene-interactions/{interaction_id}",
    response_model=DrugGeneInteraction,
    summary="Get a drug-gene interaction",
)
async def get_drug_gene_interaction(interaction_id: str) -> DrugGeneInteraction:
    svc = get_pharmacogenomics_service()
    interaction = svc.get_drug_gene_interaction(interaction_id)
    if interaction is None:
        raise HTTPException(status_code=404, detail=f"Interaction '{interaction_id}' not found")
    return interaction


@router.post(
    "/drug-gene-interactions",
    response_model=DrugGeneInteraction,
    status_code=201,
    summary="Create a drug-gene interaction",
)
async def create_drug_gene_interaction(payload: DrugGeneInteractionCreate) -> DrugGeneInteraction:
    svc = get_pharmacogenomics_service()
    return svc.create_drug_gene_interaction(payload)


@router.put(
    "/drug-gene-interactions/{interaction_id}",
    response_model=DrugGeneInteraction,
    summary="Update a drug-gene interaction",
)
async def update_drug_gene_interaction(
    interaction_id: str, payload: DrugGeneInteractionUpdate,
) -> DrugGeneInteraction:
    svc = get_pharmacogenomics_service()
    updated = svc.update_drug_gene_interaction(interaction_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Interaction '{interaction_id}' not found")
    return updated


@router.delete(
    "/drug-gene-interactions/{interaction_id}",
    status_code=204,
    summary="Delete a drug-gene interaction",
)
async def delete_drug_gene_interaction(interaction_id: str) -> None:
    svc = get_pharmacogenomics_service()
    deleted = svc.delete_drug_gene_interaction(interaction_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Interaction '{interaction_id}' not found")


# ---------------------------------------------------------------------------
# Genotype-Phenotype Mappings
# ---------------------------------------------------------------------------


@router.get(
    "/genotype-phenotypes",
    response_model=GenotypePhenotypeListResponse,
    summary="List genotype-phenotype mappings",
    description="Retrieve genotype-phenotype mappings with optional filtering.",
)
async def list_genotype_phenotypes(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> GenotypePhenotypeListResponse:
    svc = get_pharmacogenomics_service()
    items = svc.list_genotype_phenotypes(trial_id=trial_id)
    return GenotypePhenotypeListResponse(items=items, total=len(items))


@router.get(
    "/genotype-phenotypes/{gp_id}",
    response_model=GenotypePhenotype,
    summary="Get a genotype-phenotype mapping",
)
async def get_genotype_phenotype(gp_id: str) -> GenotypePhenotype:
    svc = get_pharmacogenomics_service()
    gp = svc.get_genotype_phenotype(gp_id)
    if gp is None:
        raise HTTPException(status_code=404, detail=f"Genotype-phenotype '{gp_id}' not found")
    return gp


@router.post(
    "/genotype-phenotypes",
    response_model=GenotypePhenotype,
    status_code=201,
    summary="Create a genotype-phenotype mapping",
)
async def create_genotype_phenotype(payload: GenotypePhenotypeCreate) -> GenotypePhenotype:
    svc = get_pharmacogenomics_service()
    return svc.create_genotype_phenotype(payload)


@router.put(
    "/genotype-phenotypes/{gp_id}",
    response_model=GenotypePhenotype,
    summary="Update a genotype-phenotype mapping",
)
async def update_genotype_phenotype(
    gp_id: str, payload: GenotypePhenotypeUpdate,
) -> GenotypePhenotype:
    svc = get_pharmacogenomics_service()
    updated = svc.update_genotype_phenotype(gp_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Genotype-phenotype '{gp_id}' not found")
    return updated


@router.delete(
    "/genotype-phenotypes/{gp_id}",
    status_code=204,
    summary="Delete a genotype-phenotype mapping",
)
async def delete_genotype_phenotype(gp_id: str) -> None:
    svc = get_pharmacogenomics_service()
    deleted = svc.delete_genotype_phenotype(gp_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Genotype-phenotype '{gp_id}' not found")


# ---------------------------------------------------------------------------
# PGx Test Orders
# ---------------------------------------------------------------------------


@router.get(
    "/test-orders",
    response_model=PGxTestOrderListResponse,
    summary="List PGx test orders",
    description="Retrieve PGx test orders with optional filtering by trial.",
)
async def list_test_orders(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> PGxTestOrderListResponse:
    svc = get_pharmacogenomics_service()
    items = svc.list_test_orders(trial_id=trial_id)
    return PGxTestOrderListResponse(items=items, total=len(items))


@router.get(
    "/test-orders/{order_id}",
    response_model=PGxTestOrder,
    summary="Get a PGx test order",
)
async def get_test_order(order_id: str) -> PGxTestOrder:
    svc = get_pharmacogenomics_service()
    order = svc.get_test_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail=f"Test order '{order_id}' not found")
    return order


@router.post(
    "/test-orders",
    response_model=PGxTestOrder,
    status_code=201,
    summary="Create a PGx test order",
)
async def create_test_order(payload: PGxTestOrderCreate) -> PGxTestOrder:
    svc = get_pharmacogenomics_service()
    return svc.create_test_order(payload)


@router.put(
    "/test-orders/{order_id}",
    response_model=PGxTestOrder,
    summary="Update a PGx test order",
)
async def update_test_order(
    order_id: str, payload: PGxTestOrderUpdate,
) -> PGxTestOrder:
    svc = get_pharmacogenomics_service()
    updated = svc.update_test_order(order_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Test order '{order_id}' not found")
    return updated


@router.delete(
    "/test-orders/{order_id}",
    status_code=204,
    summary="Delete a PGx test order",
)
async def delete_test_order(order_id: str) -> None:
    svc = get_pharmacogenomics_service()
    deleted = svc.delete_test_order(order_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Test order '{order_id}' not found")


# ---------------------------------------------------------------------------
# Variant Results
# ---------------------------------------------------------------------------


@router.get(
    "/variant-results",
    response_model=VariantResultListResponse,
    summary="List variant results",
    description="Retrieve variant results with optional filtering by trial.",
)
async def list_variant_results(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> VariantResultListResponse:
    svc = get_pharmacogenomics_service()
    items = svc.list_variant_results(trial_id=trial_id)
    return VariantResultListResponse(items=items, total=len(items))


@router.get(
    "/variant-results/{result_id}",
    response_model=VariantResult,
    summary="Get a variant result",
)
async def get_variant_result(result_id: str) -> VariantResult:
    svc = get_pharmacogenomics_service()
    result = svc.get_variant_result(result_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Variant result '{result_id}' not found")
    return result


@router.post(
    "/variant-results",
    response_model=VariantResult,
    status_code=201,
    summary="Create a variant result",
)
async def create_variant_result(payload: VariantResultCreate) -> VariantResult:
    svc = get_pharmacogenomics_service()
    return svc.create_variant_result(payload)


@router.put(
    "/variant-results/{result_id}",
    response_model=VariantResult,
    summary="Update a variant result",
)
async def update_variant_result(
    result_id: str, payload: VariantResultUpdate,
) -> VariantResult:
    svc = get_pharmacogenomics_service()
    updated = svc.update_variant_result(result_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Variant result '{result_id}' not found")
    return updated


@router.delete(
    "/variant-results/{result_id}",
    status_code=204,
    summary="Delete a variant result",
)
async def delete_variant_result(result_id: str) -> None:
    svc = get_pharmacogenomics_service()
    deleted = svc.delete_variant_result(result_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Variant result '{result_id}' not found")


# ---------------------------------------------------------------------------
# Dosing Recommendations
# ---------------------------------------------------------------------------


@router.get(
    "/dosing-recommendations",
    response_model=DosingRecommendationListResponse,
    summary="List dosing recommendations",
    description="Retrieve dosing recommendations with optional filtering by trial.",
)
async def list_dosing_recommendations(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> DosingRecommendationListResponse:
    svc = get_pharmacogenomics_service()
    items = svc.list_dosing_recommendations(trial_id=trial_id)
    return DosingRecommendationListResponse(items=items, total=len(items))


@router.get(
    "/dosing-recommendations/{rec_id}",
    response_model=DosingRecommendation,
    summary="Get a dosing recommendation",
)
async def get_dosing_recommendation(rec_id: str) -> DosingRecommendation:
    svc = get_pharmacogenomics_service()
    rec = svc.get_dosing_recommendation(rec_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"Dosing recommendation '{rec_id}' not found")
    return rec


@router.post(
    "/dosing-recommendations",
    response_model=DosingRecommendation,
    status_code=201,
    summary="Create a dosing recommendation",
)
async def create_dosing_recommendation(payload: DosingRecommendationCreate) -> DosingRecommendation:
    svc = get_pharmacogenomics_service()
    return svc.create_dosing_recommendation(payload)


@router.put(
    "/dosing-recommendations/{rec_id}",
    response_model=DosingRecommendation,
    summary="Update a dosing recommendation",
)
async def update_dosing_recommendation(
    rec_id: str, payload: DosingRecommendationUpdate,
) -> DosingRecommendation:
    svc = get_pharmacogenomics_service()
    updated = svc.update_dosing_recommendation(rec_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Dosing recommendation '{rec_id}' not found")
    return updated


@router.delete(
    "/dosing-recommendations/{rec_id}",
    status_code=204,
    summary="Delete a dosing recommendation",
)
async def delete_dosing_recommendation(rec_id: str) -> None:
    svc = get_pharmacogenomics_service()
    deleted = svc.delete_dosing_recommendation(rec_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Dosing recommendation '{rec_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=PharmacogenomicsMetrics,
    summary="Get pharmacogenomics metrics",
    description="Aggregated pharmacogenomics metrics including interaction counts, "
                "test order status, variant significance breakdown, dosing recommendation "
                "action distribution, and recommendation acceptance rate.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter metrics by trial ID"),
) -> PharmacogenomicsMetrics:
    svc = get_pharmacogenomics_service()
    return svc.get_metrics(trial_id=trial_id)
