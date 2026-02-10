"""Clinical Trial Insurance API endpoints.

Provides comprehensive insurance management for clinical trials: policy CRUD,
certificate issuance and tracking, claims management, coverage requirements,
renewal workflows, compliance checking, expiring policy alerts, and metrics.

Endpoints:
    GET    /trial-insurance/policies                              - List policies
    GET    /trial-insurance/policies/{policy_id}                  - Get single policy
    POST   /trial-insurance/policies                              - Create policy
    PUT    /trial-insurance/policies/{policy_id}                  - Update policy
    DELETE /trial-insurance/policies/{policy_id}                  - Delete policy
    GET    /trial-insurance/certificates                          - List certificates
    GET    /trial-insurance/certificates/{certificate_id}         - Get single certificate
    POST   /trial-insurance/certificates                          - Issue certificate
    PUT    /trial-insurance/certificates/{certificate_id}         - Update certificate
    DELETE /trial-insurance/certificates/{certificate_id}         - Delete certificate
    GET    /trial-insurance/claims                                - List claims
    GET    /trial-insurance/claims/{claim_id}                     - Get single claim
    POST   /trial-insurance/claims                                - File claim
    PUT    /trial-insurance/claims/{claim_id}                     - Update claim
    DELETE /trial-insurance/claims/{claim_id}                     - Delete claim
    GET    /trial-insurance/requirements                          - List requirements
    GET    /trial-insurance/requirements/{requirement_id}         - Get single requirement
    POST   /trial-insurance/requirements                          - Create requirement
    PUT    /trial-insurance/requirements/{requirement_id}         - Update requirement
    DELETE /trial-insurance/requirements/{requirement_id}         - Delete requirement
    GET    /trial-insurance/compliance/{trial_id}                 - Check coverage compliance
    GET    /trial-insurance/renewals                              - List renewals
    GET    /trial-insurance/renewals/{renewal_id}                 - Get single renewal
    POST   /trial-insurance/renewals                              - Initiate renewal
    PUT    /trial-insurance/renewals/{renewal_id}                 - Update renewal
    DELETE /trial-insurance/renewals/{renewal_id}                 - Delete renewal
    GET    /trial-insurance/expiring                              - Get expiring policies
    GET    /trial-insurance/metrics                               - Get insurance metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.trial_insurance import (
    CertificateStatus,
    ClaimStatus,
    CoverageComplianceResult,
    CoverageRequirement,
    CoverageRequirementCreate,
    CoverageRequirementListResponse,
    CoverageRequirementUpdate,
    InsuranceCertificate,
    InsuranceCertificateCreate,
    InsuranceCertificateListResponse,
    InsuranceCertificateUpdate,
    InsuranceClaim,
    InsuranceClaimCreate,
    InsuranceClaimListResponse,
    InsuranceClaimUpdate,
    InsuranceMetrics,
    InsurancePolicy,
    InsurancePolicyCreate,
    InsurancePolicyListResponse,
    InsurancePolicyUpdate,
    InsuranceRenewal,
    InsuranceRenewalCreate,
    InsuranceRenewalListResponse,
    InsuranceRenewalUpdate,
    PolicyStatus,
    PolicyType,
    RenewalStatus,
)
from app.services.trial_insurance_service import get_trial_insurance_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/trial-insurance",
    tags=["Trial Insurance"],
)


# ---------------------------------------------------------------------------
# Policy Management
# ---------------------------------------------------------------------------


@router.get(
    "/policies",
    response_model=InsurancePolicyListResponse,
    summary="List insurance policies",
    description="Retrieve insurance policies with optional filtering by trial, type, and status.",
)
async def list_policies(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    policy_type: Optional[PolicyType] = Query(None, description="Filter by policy type"),
    status: Optional[PolicyStatus] = Query(None, description="Filter by policy status"),
) -> InsurancePolicyListResponse:
    svc = get_trial_insurance_service()
    items = svc.list_policies(trial_id=trial_id, policy_type=policy_type, status=status)
    return InsurancePolicyListResponse(items=items, total=len(items))


@router.get(
    "/policies/{policy_id}",
    response_model=InsurancePolicy,
    summary="Get an insurance policy",
)
async def get_policy(policy_id: str) -> InsurancePolicy:
    svc = get_trial_insurance_service()
    policy = svc.get_policy(policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail=f"Policy '{policy_id}' not found")
    return policy


@router.post(
    "/policies",
    response_model=InsurancePolicy,
    status_code=201,
    summary="Create an insurance policy",
)
async def create_policy(payload: InsurancePolicyCreate) -> InsurancePolicy:
    svc = get_trial_insurance_service()
    return svc.create_policy(payload)


@router.put(
    "/policies/{policy_id}",
    response_model=InsurancePolicy,
    summary="Update an insurance policy",
)
async def update_policy(
    policy_id: str, payload: InsurancePolicyUpdate
) -> InsurancePolicy:
    svc = get_trial_insurance_service()
    updated = svc.update_policy(policy_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Policy '{policy_id}' not found")
    return updated


@router.delete(
    "/policies/{policy_id}",
    status_code=204,
    summary="Delete an insurance policy",
)
async def delete_policy(policy_id: str) -> None:
    svc = get_trial_insurance_service()
    deleted = svc.delete_policy(policy_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Policy '{policy_id}' not found")


# ---------------------------------------------------------------------------
# Certificate Management
# ---------------------------------------------------------------------------


@router.get(
    "/certificates",
    response_model=InsuranceCertificateListResponse,
    summary="List insurance certificates",
    description="Retrieve certificates with optional filtering by policy, trial, site, status, and country.",
)
async def list_certificates(
    policy_id: Optional[str] = Query(None, description="Filter by policy ID"),
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    status: Optional[CertificateStatus] = Query(None, description="Filter by status"),
    country: Optional[str] = Query(None, description="Filter by country code"),
) -> InsuranceCertificateListResponse:
    svc = get_trial_insurance_service()
    items = svc.list_certificates(
        policy_id=policy_id, trial_id=trial_id, site_id=site_id,
        status=status, country=country,
    )
    return InsuranceCertificateListResponse(items=items, total=len(items))


@router.get(
    "/certificates/{certificate_id}",
    response_model=InsuranceCertificate,
    summary="Get an insurance certificate",
)
async def get_certificate(certificate_id: str) -> InsuranceCertificate:
    svc = get_trial_insurance_service()
    cert = svc.get_certificate(certificate_id)
    if cert is None:
        raise HTTPException(
            status_code=404, detail=f"Certificate '{certificate_id}' not found"
        )
    return cert


@router.post(
    "/certificates",
    response_model=InsuranceCertificate,
    status_code=201,
    summary="Issue an insurance certificate",
    description="Issue a new certificate of insurance for a site. Validates the referenced policy is active.",
)
async def issue_certificate(
    payload: InsuranceCertificateCreate,
) -> InsuranceCertificate:
    svc = get_trial_insurance_service()
    try:
        return svc.issue_certificate(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/certificates/{certificate_id}",
    response_model=InsuranceCertificate,
    summary="Update an insurance certificate",
)
async def update_certificate(
    certificate_id: str, payload: InsuranceCertificateUpdate
) -> InsuranceCertificate:
    svc = get_trial_insurance_service()
    updated = svc.update_certificate(certificate_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Certificate '{certificate_id}' not found"
        )
    return updated


@router.delete(
    "/certificates/{certificate_id}",
    status_code=204,
    summary="Delete an insurance certificate",
)
async def delete_certificate(certificate_id: str) -> None:
    svc = get_trial_insurance_service()
    deleted = svc.delete_certificate(certificate_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Certificate '{certificate_id}' not found"
        )


# ---------------------------------------------------------------------------
# Claims Management
# ---------------------------------------------------------------------------


@router.get(
    "/claims",
    response_model=InsuranceClaimListResponse,
    summary="List insurance claims",
    description="Retrieve claims with optional filtering by policy, trial, site, and status.",
)
async def list_claims(
    policy_id: Optional[str] = Query(None, description="Filter by policy ID"),
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    status: Optional[ClaimStatus] = Query(None, description="Filter by claim status"),
) -> InsuranceClaimListResponse:
    svc = get_trial_insurance_service()
    items = svc.list_claims(
        policy_id=policy_id, trial_id=trial_id, site_id=site_id, status=status,
    )
    return InsuranceClaimListResponse(items=items, total=len(items))


@router.get(
    "/claims/{claim_id}",
    response_model=InsuranceClaim,
    summary="Get an insurance claim",
)
async def get_claim(claim_id: str) -> InsuranceClaim:
    svc = get_trial_insurance_service()
    claim = svc.get_claim(claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail=f"Claim '{claim_id}' not found")
    return claim


@router.post(
    "/claims",
    response_model=InsuranceClaim,
    status_code=201,
    summary="File an insurance claim",
    description="File a new insurance claim against a policy. Validates the referenced policy is active.",
)
async def file_claim(payload: InsuranceClaimCreate) -> InsuranceClaim:
    svc = get_trial_insurance_service()
    try:
        return svc.file_claim(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/claims/{claim_id}",
    response_model=InsuranceClaim,
    summary="Update an insurance claim",
    description="Update claim details including status, settled amount, and investigation notes.",
)
async def update_claim(
    claim_id: str, payload: InsuranceClaimUpdate
) -> InsuranceClaim:
    svc = get_trial_insurance_service()
    updated = svc.update_claim(claim_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Claim '{claim_id}' not found")
    return updated


@router.delete(
    "/claims/{claim_id}",
    status_code=204,
    summary="Delete an insurance claim",
)
async def delete_claim(claim_id: str) -> None:
    svc = get_trial_insurance_service()
    deleted = svc.delete_claim(claim_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Claim '{claim_id}' not found")


# ---------------------------------------------------------------------------
# Coverage Requirements
# ---------------------------------------------------------------------------


@router.get(
    "/requirements",
    response_model=CoverageRequirementListResponse,
    summary="List coverage requirements",
    description="Retrieve coverage requirements with optional filtering by trial, country, and met status.",
)
async def list_requirements(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    country: Optional[str] = Query(None, description="Filter by country code"),
    met: Optional[bool] = Query(None, description="Filter by met/unmet status"),
) -> CoverageRequirementListResponse:
    svc = get_trial_insurance_service()
    items = svc.list_requirements(trial_id=trial_id, country=country, met=met)
    return CoverageRequirementListResponse(items=items, total=len(items))


@router.get(
    "/requirements/{requirement_id}",
    response_model=CoverageRequirement,
    summary="Get a coverage requirement",
)
async def get_requirement(requirement_id: str) -> CoverageRequirement:
    svc = get_trial_insurance_service()
    req = svc.get_requirement(requirement_id)
    if req is None:
        raise HTTPException(
            status_code=404, detail=f"Requirement '{requirement_id}' not found"
        )
    return req


@router.post(
    "/requirements",
    response_model=CoverageRequirement,
    status_code=201,
    summary="Create a coverage requirement",
)
async def create_requirement(
    payload: CoverageRequirementCreate,
) -> CoverageRequirement:
    svc = get_trial_insurance_service()
    return svc.create_requirement(payload)


@router.put(
    "/requirements/{requirement_id}",
    response_model=CoverageRequirement,
    summary="Update a coverage requirement",
)
async def update_requirement(
    requirement_id: str, payload: CoverageRequirementUpdate
) -> CoverageRequirement:
    svc = get_trial_insurance_service()
    updated = svc.update_requirement(requirement_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Requirement '{requirement_id}' not found"
        )
    return updated


@router.delete(
    "/requirements/{requirement_id}",
    status_code=204,
    summary="Delete a coverage requirement",
)
async def delete_requirement(requirement_id: str) -> None:
    svc = get_trial_insurance_service()
    deleted = svc.delete_requirement(requirement_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Requirement '{requirement_id}' not found"
        )


# ---------------------------------------------------------------------------
# Coverage Compliance
# ---------------------------------------------------------------------------


@router.get(
    "/compliance/{trial_id}",
    response_model=CoverageComplianceResult,
    summary="Check coverage compliance for a trial",
    description="Evaluate all coverage requirements for a trial and determine compliance status.",
)
async def check_coverage_compliance(trial_id: str) -> CoverageComplianceResult:
    svc = get_trial_insurance_service()
    return svc.check_coverage_compliance(trial_id)


# ---------------------------------------------------------------------------
# Renewal Management
# ---------------------------------------------------------------------------


@router.get(
    "/renewals",
    response_model=InsuranceRenewalListResponse,
    summary="List insurance renewals",
    description="Retrieve renewals with optional filtering by policy and status.",
)
async def list_renewals(
    policy_id: Optional[str] = Query(None, description="Filter by policy ID"),
    status: Optional[RenewalStatus] = Query(None, description="Filter by renewal status"),
) -> InsuranceRenewalListResponse:
    svc = get_trial_insurance_service()
    items = svc.list_renewals(policy_id=policy_id, status=status)
    return InsuranceRenewalListResponse(items=items, total=len(items))


@router.get(
    "/renewals/{renewal_id}",
    response_model=InsuranceRenewal,
    summary="Get an insurance renewal",
)
async def get_renewal(renewal_id: str) -> InsuranceRenewal:
    svc = get_trial_insurance_service()
    renewal = svc.get_renewal(renewal_id)
    if renewal is None:
        raise HTTPException(
            status_code=404, detail=f"Renewal '{renewal_id}' not found"
        )
    return renewal


@router.post(
    "/renewals",
    response_model=InsuranceRenewal,
    status_code=201,
    summary="Initiate a policy renewal",
    description="Initiate a renewal for an existing policy. Updates the policy status to pending_renewal.",
)
async def initiate_renewal(payload: InsuranceRenewalCreate) -> InsuranceRenewal:
    svc = get_trial_insurance_service()
    try:
        return svc.initiate_renewal(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/renewals/{renewal_id}",
    response_model=InsuranceRenewal,
    summary="Update an insurance renewal",
)
async def update_renewal(
    renewal_id: str, payload: InsuranceRenewalUpdate
) -> InsuranceRenewal:
    svc = get_trial_insurance_service()
    updated = svc.update_renewal(renewal_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Renewal '{renewal_id}' not found"
        )
    return updated


@router.delete(
    "/renewals/{renewal_id}",
    status_code=204,
    summary="Delete an insurance renewal",
)
async def delete_renewal(renewal_id: str) -> None:
    svc = get_trial_insurance_service()
    deleted = svc.delete_renewal(renewal_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Renewal '{renewal_id}' not found"
        )


# ---------------------------------------------------------------------------
# Expiring Policies & Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/expiring",
    response_model=InsurancePolicyListResponse,
    summary="Get expiring policies",
    description="Retrieve active policies expiring within the specified number of days.",
)
async def get_expiring_policies(
    days: int = Query(90, ge=1, le=365, description="Number of days to look ahead"),
) -> InsurancePolicyListResponse:
    svc = get_trial_insurance_service()
    items = svc.get_expiring_policies(days=days)
    return InsurancePolicyListResponse(items=items, total=len(items))


@router.get(
    "/metrics",
    response_model=InsuranceMetrics,
    summary="Get insurance metrics",
    description="Aggregated insurance operational metrics across all policies, certificates, claims, and requirements.",
)
async def get_metrics() -> InsuranceMetrics:
    svc = get_trial_insurance_service()
    return svc.get_metrics()
