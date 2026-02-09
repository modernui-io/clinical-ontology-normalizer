"""Deployment Verification & API Contract Testing API endpoints (VPE-9).

Provides deployment verification with smoke tests, health checks,
schema validation, performance checks, API contract management,
contract testing with breaking-change detection, error budgets
with SLI definitions, burn-rate calculation, and deployment gate
evaluation.

Endpoints:
    GET    /deployment-verification/verifications                       - List verifications
    GET    /deployment-verification/verifications/{id}                  - Get verification detail
    POST   /deployment-verification/verifications                       - Create verification
    DELETE /deployment-verification/verifications/{id}                  - Delete verification
    POST   /deployment-verification/smoke-tests                         - Run smoke tests
    GET    /deployment-verification/contracts                            - List contracts
    GET    /deployment-verification/contracts/{id}                       - Get contract detail
    POST   /deployment-verification/contracts                            - Create contract
    PUT    /deployment-verification/contracts/{id}                       - Update contract
    DELETE /deployment-verification/contracts/{id}                       - Delete contract
    GET    /deployment-verification/contract-tests                       - List contract test results
    POST   /deployment-verification/contracts/{id}/test                  - Run contract test
    POST   /deployment-verification/contracts/{id}/breaking-changes      - Detect breaking changes
    GET    /deployment-verification/error-budgets                        - List error budgets
    GET    /deployment-verification/error-budgets/{id}                   - Get error budget detail
    POST   /deployment-verification/error-budgets                        - Create error budget
    DELETE /deployment-verification/error-budgets/{id}                   - Delete error budget
    GET    /deployment-verification/error-budgets/{id}/burn-rate         - Get burn rate
    GET    /deployment-verification/sli-definitions                      - List SLI definitions
    GET    /deployment-verification/sli-definitions/{id}                 - Get SLI definition
    POST   /deployment-verification/sli-definitions                      - Create SLI definition
    DELETE /deployment-verification/sli-definitions/{id}                 - Delete SLI definition
    GET    /deployment-verification/sli-definitions/{id}/measure         - Measure SLI
    GET    /deployment-verification/gate                                  - Evaluate deployment gate
    GET    /deployment-verification/trends                               - Verification trends
    GET    /deployment-verification/metrics                              - Aggregate metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.deployment_verification import (
    APIContract,
    APIContractCreate,
    APIContractListResponse,
    APIContractUpdate,
    BreakingChange,
    ContractTestResult,
    ContractTestResultListResponse,
    ContractTestType,
    DeploymentGateEvaluation,
    DeploymentVerification,
    DeploymentVerificationCreate,
    DeploymentVerificationListResponse,
    DeploymentVerificationMetrics,
    EnvironmentName,
    ErrorBudget,
    ErrorBudgetCreate,
    ErrorBudgetListResponse,
    ErrorBudgetStatus,
    RunSmokeTestRequest,
    SLIDefinition,
    SLIDefinitionCreate,
    SLIDefinitionListResponse,
    VerificationStatus,
    VerificationTrend,
)
from app.services.deployment_verification_service import (
    get_deployment_verification_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/deployment-verification",
    tags=["Deployment Verification"],
)


# ===========================================================================
# Deployment Verifications
# ===========================================================================


@router.get("/verifications", response_model=DeploymentVerificationListResponse)
async def list_verifications(
    environment: Optional[EnvironmentName] = Query(None, description="Filter by environment"),
    status: Optional[VerificationStatus] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
):
    """List all deployment verifications with optional filters."""
    svc = get_deployment_verification_service()
    return svc.list_verifications(environment=environment, status=status, limit=limit, offset=offset)


@router.get("/verifications/{verification_id}", response_model=DeploymentVerification)
async def get_verification(verification_id: str):
    """Get a specific deployment verification by ID."""
    svc = get_deployment_verification_service()
    result = svc.get_verification(verification_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Verification {verification_id} not found")
    return result


@router.post("/verifications", response_model=DeploymentVerification, status_code=201)
async def create_verification(body: DeploymentVerificationCreate):
    """Create a new deployment verification run."""
    svc = get_deployment_verification_service()
    return svc.create_verification(
        deployment_id=body.deployment_id,
        environment=body.environment,
        version=body.version,
        triggered_by=body.triggered_by,
    )


@router.delete("/verifications/{verification_id}", status_code=204)
async def delete_verification(verification_id: str):
    """Delete a deployment verification."""
    svc = get_deployment_verification_service()
    if not svc.delete_verification(verification_id):
        raise HTTPException(status_code=404, detail=f"Verification {verification_id} not found")


# ===========================================================================
# Smoke Tests
# ===========================================================================


@router.post("/smoke-tests", response_model=DeploymentVerification, status_code=201)
async def run_smoke_tests(body: RunSmokeTestRequest):
    """Run a smoke test suite against a deployment."""
    svc = get_deployment_verification_service()
    return svc.run_smoke_tests(
        deployment_id=body.deployment_id,
        environment=body.environment,
        version=body.version,
        endpoints=body.endpoints,
        triggered_by=body.triggered_by,
    )


# ===========================================================================
# API Contracts
# ===========================================================================


@router.get("/contracts", response_model=APIContractListResponse)
async def list_contracts(
    method: Optional[str] = Query(None, description="Filter by HTTP method"),
    deprecated: Optional[bool] = Query(None, description="Filter by deprecation status"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
):
    """List all API contracts with optional filters."""
    svc = get_deployment_verification_service()
    return svc.list_contracts(method=method, deprecated=deprecated, limit=limit, offset=offset)


@router.get("/contracts/{contract_id}", response_model=APIContract)
async def get_contract(contract_id: str):
    """Get a specific API contract by ID."""
    svc = get_deployment_verification_service()
    result = svc.get_contract(contract_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found")
    return result


@router.post("/contracts", response_model=APIContract, status_code=201)
async def create_contract(body: APIContractCreate):
    """Create a new API contract."""
    svc = get_deployment_verification_service()
    return svc.create_contract(body)


@router.put("/contracts/{contract_id}", response_model=APIContract)
async def update_contract(contract_id: str, body: APIContractUpdate):
    """Update an existing API contract."""
    svc = get_deployment_verification_service()
    result = svc.update_contract(contract_id, body)
    if not result:
        raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found")
    return result


@router.delete("/contracts/{contract_id}", status_code=204)
async def delete_contract(contract_id: str):
    """Delete an API contract."""
    svc = get_deployment_verification_service()
    if not svc.delete_contract(contract_id):
        raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found")


# ===========================================================================
# Contract Tests
# ===========================================================================


@router.get("/contract-tests", response_model=ContractTestResultListResponse)
async def list_contract_tests(
    contract_id: Optional[str] = Query(None, description="Filter by contract ID"),
    status: Optional[VerificationStatus] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
):
    """List all contract test results."""
    svc = get_deployment_verification_service()
    return svc.list_contract_test_results(
        contract_id=contract_id, status=status, limit=limit, offset=offset,
    )


@router.post("/contracts/{contract_id}/test", response_model=ContractTestResult, status_code=201)
async def run_contract_test(
    contract_id: str,
    test_type: ContractTestType = Query(
        ContractTestType.RESPONSE_SCHEMA, description="Type of contract test"
    ),
):
    """Run a contract test against an existing contract."""
    svc = get_deployment_verification_service()
    result = svc.run_contract_test(contract_id, test_type)
    if not result:
        raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found")
    return result


@router.post(
    "/contracts/{contract_id}/breaking-changes",
    response_model=list[BreakingChange],
)
async def detect_breaking_changes(contract_id: str, new_schema: dict):
    """Detect breaking changes between the current contract and a new schema."""
    svc = get_deployment_verification_service()
    contract = svc.get_contract(contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found")
    return svc.detect_breaking_changes(contract_id, new_schema)


# ===========================================================================
# Error Budgets
# ===========================================================================


@router.get("/error-budgets", response_model=ErrorBudgetListResponse)
async def list_error_budgets(
    service_name: Optional[str] = Query(None, description="Filter by service"),
    status: Optional[ErrorBudgetStatus] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
):
    """List all error budgets with optional filters."""
    svc = get_deployment_verification_service()
    return svc.list_error_budgets(
        service_name=service_name, status=status, limit=limit, offset=offset,
    )


@router.get("/error-budgets/{budget_id}", response_model=ErrorBudget)
async def get_error_budget(budget_id: str):
    """Get a specific error budget by ID."""
    svc = get_deployment_verification_service()
    result = svc.get_error_budget(budget_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Error budget {budget_id} not found")
    return result


@router.post("/error-budgets", response_model=ErrorBudget, status_code=201)
async def create_error_budget(body: ErrorBudgetCreate):
    """Create a new error budget."""
    svc = get_deployment_verification_service()
    return svc.create_error_budget(body)


@router.delete("/error-budgets/{budget_id}", status_code=204)
async def delete_error_budget(budget_id: str):
    """Delete an error budget."""
    svc = get_deployment_verification_service()
    if not svc.delete_error_budget(budget_id):
        raise HTTPException(status_code=404, detail=f"Error budget {budget_id} not found")


@router.get("/error-budgets/{budget_id}/burn-rate")
async def get_burn_rate(budget_id: str):
    """Calculate and return the current burn rate for an error budget."""
    svc = get_deployment_verification_service()
    result = svc.calculate_burn_rate(budget_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Error budget {budget_id} not found")
    return result


# ===========================================================================
# SLI Definitions
# ===========================================================================


@router.get("/sli-definitions", response_model=SLIDefinitionListResponse)
async def list_sli_definitions(
    service_name: Optional[str] = Query(None, description="Filter by service"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
):
    """List all SLI definitions."""
    svc = get_deployment_verification_service()
    return svc.list_sli_definitions(
        service_name=service_name, limit=limit, offset=offset,
    )


@router.get("/sli-definitions/{sli_id}", response_model=SLIDefinition)
async def get_sli_definition(sli_id: str):
    """Get a specific SLI definition by ID."""
    svc = get_deployment_verification_service()
    result = svc.get_sli_definition(sli_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"SLI definition {sli_id} not found")
    return result


@router.post("/sli-definitions", response_model=SLIDefinition, status_code=201)
async def create_sli_definition(body: SLIDefinitionCreate):
    """Create a new SLI definition."""
    svc = get_deployment_verification_service()
    return svc.create_sli_definition(body)


@router.delete("/sli-definitions/{sli_id}", status_code=204)
async def delete_sli_definition(sli_id: str):
    """Delete an SLI definition."""
    svc = get_deployment_verification_service()
    if not svc.delete_sli_definition(sli_id):
        raise HTTPException(status_code=404, detail=f"SLI definition {sli_id} not found")


@router.get("/sli-definitions/{sli_id}/measure")
async def measure_sli(sli_id: str):
    """Simulate measuring an SLI and return current value."""
    svc = get_deployment_verification_service()
    result = svc.measure_sli(sli_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"SLI definition {sli_id} not found")
    return result


# ===========================================================================
# Deployment Gate & Trends & Metrics
# ===========================================================================


@router.get("/gate", response_model=DeploymentGateEvaluation)
async def evaluate_deployment_gate(
    deployment_id: Optional[str] = Query(None, description="Filter by deployment ID"),
):
    """Evaluate all deployment gates and return aggregate result."""
    svc = get_deployment_verification_service()
    return svc.evaluate_deployment_gate(deployment_id=deployment_id)


@router.get("/trends", response_model=list[VerificationTrend])
async def get_verification_trends(
    days: int = Query(30, ge=1, le=365, description="Number of days to trend"),
):
    """Get historical verification trending data."""
    svc = get_deployment_verification_service()
    return svc.get_verification_trends(days=days)


@router.get("/metrics", response_model=DeploymentVerificationMetrics)
async def get_metrics():
    """Get aggregate deployment verification metrics."""
    svc = get_deployment_verification_service()
    return svc.get_metrics()
