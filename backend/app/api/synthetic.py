"""Synthetic Data Generation API endpoints.

Provides endpoints for:
- Starting synthetic data generation jobs
- Monitoring job status and progress
- Downloading generated data
- Validating synthetic data quality
- Privacy metrics and reporting
"""

from __future__ import annotations

import logging
import json
from datetime import datetime, timezone
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from app.services.synthetic_data_service import (
    AgeDistribution,
    ConditionPrevalence,
    FHIRBundle,
    GenderDistribution,
    GenerationJob,
    GenerationTemplate,
    JobStatus,
    LabCorrelation,
    MedicationPattern,
    OutputFormat,
    PrivacyConfig,
    PrivacyReport,
    RaceDistribution,
    SynthesisConfig,
    SyntheticPatient,
    ValidationReport,
    get_synthetic_data_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/synthetic", tags=["Synthetic Data"])


# ============================================================================
# Request/Response Models
# ============================================================================


class AgeDistributionRequest(BaseModel):
    """Age distribution configuration."""

    min_age: int = Field(default=0, ge=0, le=120)
    max_age: int = Field(default=100, ge=0, le=120)
    mean_age: float = Field(default=45.0, ge=0, le=120)
    std_dev: float = Field(default=20.0, ge=1, le=50)


class GenderDistributionRequest(BaseModel):
    """Gender distribution configuration."""

    male_ratio: float = Field(default=0.49, ge=0, le=1)
    female_ratio: float = Field(default=0.50, ge=0, le=1)
    other_ratio: float = Field(default=0.01, ge=0, le=1)


class RaceDistributionRequest(BaseModel):
    """Race distribution configuration."""

    white: float = Field(default=0.60, ge=0, le=1)
    black: float = Field(default=0.13, ge=0, le=1)
    asian: float = Field(default=0.06, ge=0, le=1)
    native_american: float = Field(default=0.01, ge=0, le=1)
    pacific_islander: float = Field(default=0.002, ge=0, le=1)
    two_or_more: float = Field(default=0.03, ge=0, le=1)
    other: float = Field(default=0.078, ge=0, le=1)


class ConditionPrevalenceRequest(BaseModel):
    """Condition prevalence configuration."""

    condition_code: str
    condition_name: str
    vocabulary: str = "SNOMED"
    prevalence: float = Field(ge=0, le=1)
    age_range: tuple[int, int] | None = None
    gender_modifier: dict[str, float] | None = None


class MedicationPatternRequest(BaseModel):
    """Medication pattern configuration."""

    medication_code: str
    medication_name: str
    vocabulary: str = "RxNorm"
    associated_conditions: list[str] = Field(default_factory=list)
    prescription_rate: float = Field(default=0.5, ge=0, le=1)


class LabCorrelationRequest(BaseModel):
    """Lab correlation configuration."""

    lab_code: str
    lab_name: str
    vocabulary: str = "LOINC"
    unit: str = ""
    normal_range: tuple[float, float] = (0.0, 100.0)
    abnormal_conditions: list[str] = Field(default_factory=list)
    abnormal_shift: float = 0.0


class PrivacyConfigRequest(BaseModel):
    """Privacy configuration."""

    epsilon: float = Field(default=1.0, gt=0, le=10, description="Privacy budget (smaller = more private)")
    delta: float = Field(default=1e-5, gt=0, le=0.1, description="Failure probability")
    k_anonymity: int = Field(default=5, ge=2, le=100, description="Minimum group size for k-anonymity")
    l_diversity: int = Field(default=2, ge=1, le=20, description="Minimum distinct sensitive values per group")
    t_closeness: float = Field(default=0.3, ge=0, le=1, description="Maximum distance between distributions")


class GenerateRequest(BaseModel):
    """Request to generate synthetic data."""

    patient_count: int = Field(default=100, ge=1, le=100000, description="Number of patients to generate")
    age_distribution: AgeDistributionRequest | None = None
    gender_distribution: GenderDistributionRequest | None = None
    race_distribution: RaceDistributionRequest | None = None
    condition_prevalences: list[ConditionPrevalenceRequest] | None = None
    medication_patterns: list[MedicationPatternRequest] | None = None
    lab_correlations: list[LabCorrelationRequest] | None = None
    observation_period_years: int = Field(default=5, ge=1, le=20)
    output_format: str = Field(default="fhir_json", pattern="^(fhir_json|csv|omop)$")
    template_id: str | None = Field(default=None, description="Use a predefined template")
    seed: int | None = Field(default=None, description="Random seed for reproducibility")
    privacy_config: PrivacyConfigRequest | None = None


class ValidateRequest(BaseModel):
    """Request to validate synthetic data."""

    synthetic_data: list[dict] = Field(description="Synthetic data to validate")
    real_data: list[dict] = Field(description="Real data for comparison")
    columns: list[str] | None = Field(default=None, description="Columns to validate")


class PrivacyReportRequest(BaseModel):
    """Request for privacy report."""

    synthetic_data: list[dict]
    real_data: list[dict] | None = None
    epsilon: float = Field(default=1.0)
    delta: float = Field(default=1e-5)
    k_anonymity: int = Field(default=5)
    l_diversity: int = Field(default=2)
    quasi_identifiers: list[str] | None = None
    sensitive_attributes: list[str] | None = None


class JobResponse(BaseModel):
    """Response for job operations."""

    job_id: str
    status: str
    progress_percent: float
    patients_generated: int
    created_at: str
    started_at: str | None
    completed_at: str | None
    error: str | None
    result_path: str | None


class TemplateResponse(BaseModel):
    """Response for template information."""

    template_id: str
    name: str
    description: str
    patient_count: int
    has_privacy_config: bool


class TemplateListResponse(BaseModel):
    """Response for template list."""

    templates: list[TemplateResponse]
    total: int


class ValidationReportResponse(BaseModel):
    """Response for validation report."""

    generated_at: str
    synthetic_row_count: int
    real_row_count: int
    overall_score: float
    passed: bool
    metrics: list[dict]


class PrivacyReportResponse(BaseModel):
    """Response for privacy report."""

    generated_at: str
    epsilon: float
    delta: float
    k_anonymity_satisfied: bool
    actual_k: int
    l_diversity_satisfied: bool
    actual_l: int
    t_closeness_satisfied: bool
    actual_t: float
    privacy_score: float
    utility_score: float
    recommendations: list[str]


class GenerateResponse(BaseModel):
    """Response for generation request."""

    job_id: str
    status: str
    message: str


class SyntheticStatsResponse(BaseModel):
    """Response for service statistics."""

    total_patients_generated: int
    total_jobs: int
    completed_jobs: int
    available_templates: int
    default_conditions: int
    default_medications: int
    default_labs: int


# ============================================================================
# Helper Functions
# ============================================================================


def _convert_to_synthesis_config(request: GenerateRequest) -> SynthesisConfig:
    """Convert API request to SynthesisConfig."""
    config = SynthesisConfig(
        patient_count=request.patient_count,
        observation_period_years=request.observation_period_years,
        seed=request.seed,
    )

    # Output format
    format_map = {
        "fhir_json": OutputFormat.FHIR_JSON,
        "csv": OutputFormat.CSV,
        "omop": OutputFormat.OMOP,
    }
    config.output_format = format_map.get(request.output_format, OutputFormat.FHIR_JSON)

    # Age distribution
    if request.age_distribution:
        config.age_distribution = AgeDistribution(
            min_age=request.age_distribution.min_age,
            max_age=request.age_distribution.max_age,
            mean_age=request.age_distribution.mean_age,
            std_dev=request.age_distribution.std_dev,
        )

    # Gender distribution
    if request.gender_distribution:
        config.gender_distribution = GenderDistribution(
            male_ratio=request.gender_distribution.male_ratio,
            female_ratio=request.gender_distribution.female_ratio,
            other_ratio=request.gender_distribution.other_ratio,
        )

    # Race distribution
    if request.race_distribution:
        config.race_distribution = RaceDistribution(
            white=request.race_distribution.white,
            black=request.race_distribution.black,
            asian=request.race_distribution.asian,
            native_american=request.race_distribution.native_american,
            pacific_islander=request.race_distribution.pacific_islander,
            two_or_more=request.race_distribution.two_or_more,
            other=request.race_distribution.other,
        )

    # Condition prevalences
    if request.condition_prevalences:
        config.condition_prevalences = [
            ConditionPrevalence(
                condition_code=cp.condition_code,
                condition_name=cp.condition_name,
                vocabulary=cp.vocabulary,
                prevalence=cp.prevalence,
                age_range=cp.age_range,
                gender_modifier=cp.gender_modifier,
            )
            for cp in request.condition_prevalences
        ]

    # Medication patterns
    if request.medication_patterns:
        config.medication_patterns = [
            MedicationPattern(
                medication_code=mp.medication_code,
                medication_name=mp.medication_name,
                vocabulary=mp.vocabulary,
                associated_conditions=mp.associated_conditions,
                prescription_rate=mp.prescription_rate,
            )
            for mp in request.medication_patterns
        ]

    # Lab correlations
    if request.lab_correlations:
        config.lab_correlations = [
            LabCorrelation(
                lab_code=lc.lab_code,
                lab_name=lc.lab_name,
                vocabulary=lc.vocabulary,
                unit=lc.unit,
                normal_range=lc.normal_range,
                abnormal_conditions=lc.abnormal_conditions,
                abnormal_shift=lc.abnormal_shift,
            )
            for lc in request.lab_correlations
        ]

    return config


def _convert_to_privacy_config(request: PrivacyConfigRequest | None) -> PrivacyConfig | None:
    """Convert API request to PrivacyConfig."""
    if request is None:
        return None

    return PrivacyConfig(
        epsilon=request.epsilon,
        delta=request.delta,
        k_anonymity=request.k_anonymity,
        l_diversity=request.l_diversity,
        t_closeness=request.t_closeness,
    )


def _job_to_response(job: GenerationJob) -> JobResponse:
    """Convert GenerationJob to API response."""
    return JobResponse(
        job_id=job.job_id,
        status=job.status.value,
        progress_percent=job.progress_percent,
        patients_generated=job.patients_generated,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error=job.error,
        result_path=job.result_path,
    )


# Background task for generation
def _run_generation_job(job_id: str) -> None:
    """Background task to run generation."""
    service = get_synthetic_data_service()
    job = service.get_job(job_id)

    if not job:
        logger.error(f"Job not found: {job_id}")
        return

    try:
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc).isoformat()

        # Generate patients
        patients = service.generate_patients(job.config)
        job.patients_generated = len(patients)

        # Apply privacy if configured
        if job.privacy_config:
            # Convert patients to dictionaries for privacy processing
            patient_dicts = []
            for p in patients:
                patient_dicts.append({
                    "patient_id": p.patient_id,
                    "gender": p.gender.value,
                    "race": p.race.value,
                    "ethnicity": p.ethnicity.value,
                    "age": p.age,
                    "condition_count": len(p.conditions),
                    "medication_count": len(p.medications),
                })

            # Apply differential privacy
            protected = service.apply_differential_privacy(
                patient_dicts,
                job.privacy_config.epsilon,
            )

        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now(timezone.utc).isoformat()
        job.progress_percent = 100.0

    except Exception as e:
        logger.exception(f"Generation job failed: {job_id}")
        job.status = JobStatus.FAILED
        job.error = str(e)
        job.completed_at = datetime.now(timezone.utc).isoformat()


# ============================================================================
# Endpoints
# ============================================================================


@router.post(
    "/generate",
    response_model=GenerateResponse,
    summary="Start synthetic data generation",
    description="Start a background job to generate synthetic patient data.",
)
async def generate_synthetic_data(
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
) -> GenerateResponse:
    """Start synthetic data generation job."""
    service = get_synthetic_data_service()

    # If template specified, use it as base
    if request.template_id:
        template = service.get_template(request.template_id)
        if not template:
            raise HTTPException(
                status_code=404,
                detail=f"Template not found: {request.template_id}",
            )
        config = template.config
        # Override patient count if specified
        config.patient_count = request.patient_count
        privacy_config = template.privacy_config
    else:
        config = _convert_to_synthesis_config(request)
        privacy_config = _convert_to_privacy_config(request.privacy_config)

    # Create job
    job = service.create_job(config, privacy_config)

    # Start background generation
    background_tasks.add_task(_run_generation_job, job.job_id)

    logger.info(f"Started generation job {job.job_id} for {config.patient_count} patients")

    return GenerateResponse(
        job_id=job.job_id,
        status=job.status.value,
        message=f"Generation job started for {config.patient_count} patients",
    )


@router.get(
    "/jobs/{job_id}",
    response_model=JobResponse,
    summary="Get job status",
    description="Get the current status of a generation job.",
)
async def get_job_status(job_id: str) -> JobResponse:
    """Get status of a generation job."""
    service = get_synthetic_data_service()
    job = service.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job not found: {job_id}",
        )

    return _job_to_response(job)


@router.get(
    "/jobs/{job_id}/download",
    summary="Download generated data",
    description="Download the generated synthetic data in the requested format.",
)
async def download_generated_data(
    job_id: str,
    format: str = Query(default="fhir_json", pattern="^(fhir_json|csv|omop)$"),
) -> StreamingResponse:
    """Download generated data from a completed job."""
    service = get_synthetic_data_service()
    job = service.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job not found: {job_id}",
        )

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job not completed. Current status: {job.status.value}",
        )

    # Regenerate data (in production, would retrieve from storage)
    patients = service.generate_patients(job.config)

    if format == "fhir_json":
        bundle = service.generate_fhir_bundle(len(patients))
        content = json.dumps({
            "resourceType": "Bundle",
            "id": bundle.bundle_id,
            "type": bundle.bundle_type,
            "timestamp": bundle.generated_at,
            "total": bundle.total,
            "entry": bundle.entries,
        }, indent=2)
        media_type = "application/fhir+json"
        filename = f"synthetic_patients_{job_id}.json"

    elif format == "csv":
        # Convert to CSV
        lines = ["patient_id,gender,race,ethnicity,birth_date,age,condition_count,medication_count,observation_count"]
        for p in patients:
            lines.append(
                f"{p.patient_id},{p.gender.value},{p.race.value},{p.ethnicity.value},{p.birth_date},{p.age},{len(p.conditions)},{len(p.medications)},{len(p.observations)}"
            )
        content = "\n".join(lines)
        media_type = "text/csv"
        filename = f"synthetic_patients_{job_id}.csv"

    else:  # omop
        # Convert to OMOP-style JSON
        omop_data = {
            "person": [],
            "condition_occurrence": [],
            "drug_exposure": [],
            "measurement": [],
        }

        for i, p in enumerate(patients, start=1):
            omop_data["person"].append({
                "person_id": i,
                "person_source_value": p.patient_id,
                "gender_source_value": p.gender.value,
                "race_source_value": p.race.value,
                "ethnicity_source_value": p.ethnicity.value,
                "year_of_birth": int(p.birth_date[:4]) if p.birth_date else None,
            })

            for c in p.conditions:
                omop_data["condition_occurrence"].append({
                    "person_id": i,
                    "condition_source_value": c["code"],
                    "condition_concept_id": 0,  # Would need OMOP mapping
                    "condition_start_date": c.get("onset_date"),
                })

            for m in p.medications:
                omop_data["drug_exposure"].append({
                    "person_id": i,
                    "drug_source_value": m["code"],
                    "drug_concept_id": 0,
                    "drug_exposure_start_date": m.get("start_date"),
                })

            for o in p.observations:
                omop_data["measurement"].append({
                    "person_id": i,
                    "measurement_source_value": o["code"],
                    "measurement_concept_id": 0,
                    "value_as_number": o.get("value"),
                    "unit_source_value": o.get("unit"),
                    "measurement_date": o.get("date"),
                })

        content = json.dumps(omop_data, indent=2)
        media_type = "application/json"
        filename = f"synthetic_omop_{job_id}.json"

    return StreamingResponse(
        iter([content]),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post(
    "/validate",
    response_model=ValidationReportResponse,
    summary="Validate synthetic data quality",
    description="Compare statistical properties of synthetic data against real data.",
)
async def validate_synthetic_data(request: ValidateRequest) -> ValidationReportResponse:
    """Validate synthetic data quality."""
    service = get_synthetic_data_service()

    report = service.validate_synthetic_data(
        synthetic=request.synthetic_data,
        real=request.real_data,
        columns=request.columns,
    )

    return ValidationReportResponse(
        generated_at=report.generated_at,
        synthetic_row_count=report.synthetic_row_count,
        real_row_count=report.real_row_count,
        overall_score=report.overall_score,
        passed=report.passed,
        metrics=[
            {
                "metric_name": m.metric_name,
                "column": m.column,
                "expected_value": m.expected_value,
                "actual_value": m.actual_value,
                "passed": m.passed,
                "message": m.message,
            }
            for m in report.metrics
        ],
    )


@router.post(
    "/privacy-report",
    response_model=PrivacyReportResponse,
    summary="Get privacy metrics",
    description="Generate a comprehensive privacy analysis report for synthetic data.",
)
async def get_privacy_report(request: PrivacyReportRequest) -> PrivacyReportResponse:
    """Generate privacy analysis report."""
    service = get_synthetic_data_service()

    privacy_config = PrivacyConfig(
        epsilon=request.epsilon,
        delta=request.delta,
        k_anonymity=request.k_anonymity,
        l_diversity=request.l_diversity,
    )

    report = service.generate_privacy_report(
        synthetic=request.synthetic_data,
        real=request.real_data or [],
        privacy_config=privacy_config,
        quasi_identifiers=request.quasi_identifiers,
        sensitive_attributes=request.sensitive_attributes,
    )

    return PrivacyReportResponse(
        generated_at=report.generated_at,
        epsilon=report.epsilon,
        delta=report.delta,
        k_anonymity_satisfied=report.k_anonymity_satisfied,
        actual_k=report.actual_k,
        l_diversity_satisfied=report.l_diversity_satisfied,
        actual_l=report.actual_l,
        t_closeness_satisfied=report.t_closeness_satisfied,
        actual_t=report.actual_t,
        privacy_score=report.privacy_score,
        utility_score=report.utility_score,
        recommendations=report.recommendations,
    )


@router.get(
    "/templates",
    response_model=TemplateListResponse,
    summary="List generation templates",
    description="Get all available pre-configured generation templates.",
)
async def list_templates() -> TemplateListResponse:
    """List available generation templates."""
    service = get_synthetic_data_service()
    templates = service.get_templates()

    return TemplateListResponse(
        templates=[
            TemplateResponse(
                template_id=t.template_id,
                name=t.name,
                description=t.description,
                patient_count=t.config.patient_count,
                has_privacy_config=t.privacy_config is not None,
            )
            for t in templates
        ],
        total=len(templates),
    )


@router.get(
    "/templates/{template_id}",
    summary="Get template details",
    description="Get detailed configuration for a specific template.",
)
async def get_template(template_id: str) -> dict:
    """Get template details."""
    service = get_synthetic_data_service()
    template = service.get_template(template_id)

    if not template:
        raise HTTPException(
            status_code=404,
            detail=f"Template not found: {template_id}",
        )

    config = template.config

    return {
        "template_id": template.template_id,
        "name": template.name,
        "description": template.description,
        "config": {
            "patient_count": config.patient_count,
            "observation_period_years": config.observation_period_years,
            "age_distribution": {
                "min_age": config.age_distribution.min_age,
                "max_age": config.age_distribution.max_age,
                "mean_age": config.age_distribution.mean_age,
                "std_dev": config.age_distribution.std_dev,
            },
            "gender_distribution": {
                "male_ratio": config.gender_distribution.male_ratio,
                "female_ratio": config.gender_distribution.female_ratio,
                "other_ratio": config.gender_distribution.other_ratio,
            },
            "condition_count": len(config.condition_prevalences) if config.condition_prevalences else 0,
            "medication_count": len(config.medication_patterns) if config.medication_patterns else 0,
            "lab_count": len(config.lab_correlations) if config.lab_correlations else 0,
        },
        "privacy_config": {
            "epsilon": template.privacy_config.epsilon,
            "delta": template.privacy_config.delta,
            "k_anonymity": template.privacy_config.k_anonymity,
            "l_diversity": template.privacy_config.l_diversity,
        } if template.privacy_config else None,
    }


@router.post(
    "/preview",
    summary="Preview synthetic data",
    description="Generate a small preview of synthetic data without creating a job.",
)
async def preview_synthetic_data(
    patient_count: int = Query(default=10, ge=1, le=100),
    template_id: str | None = None,
) -> dict:
    """Generate a preview of synthetic data."""
    service = get_synthetic_data_service()

    if template_id:
        template = service.get_template(template_id)
        if not template:
            raise HTTPException(
                status_code=404,
                detail=f"Template not found: {template_id}",
            )
        config = template.config
        config.patient_count = patient_count
    else:
        config = SynthesisConfig(patient_count=patient_count)

    patients = service.generate_patients(config)

    return {
        "patient_count": len(patients),
        "preview": [
            {
                "patient_id": p.patient_id,
                "gender": p.gender.value,
                "race": p.race.value,
                "ethnicity": p.ethnicity.value,
                "age": p.age,
                "birth_date": p.birth_date,
                "conditions": [
                    {"code": c["code"], "name": c["name"]}
                    for c in p.conditions[:3]  # Limit to first 3
                ],
                "medications": [
                    {"code": m["code"], "name": m["name"]}
                    for m in p.medications[:3]
                ],
                "observation_count": len(p.observations),
                "encounter_count": len(p.encounters),
            }
            for p in patients[:10]  # Limit preview to 10 patients
        ],
    }


@router.get(
    "/stats",
    response_model=SyntheticStatsResponse,
    summary="Get service statistics",
    description="Get statistics about synthetic data generation.",
)
async def get_service_stats() -> SyntheticStatsResponse:
    """Get service statistics."""
    service = get_synthetic_data_service()
    stats = service.get_stats()

    return SyntheticStatsResponse(**stats)


@router.get(
    "/default-conditions",
    summary="Get default condition prevalences",
    description="Get the list of default condition prevalences used in generation.",
)
async def get_default_conditions() -> dict:
    """Get default condition prevalences."""
    from app.services.synthetic_data_service import DEFAULT_CONDITION_PREVALENCES

    return {
        "conditions": [
            {
                "code": c.condition_code,
                "name": c.condition_name,
                "vocabulary": c.vocabulary,
                "prevalence": c.prevalence,
                "age_range": c.age_range,
                "gender_modifier": c.gender_modifier,
            }
            for c in DEFAULT_CONDITION_PREVALENCES
        ],
        "total": len(DEFAULT_CONDITION_PREVALENCES),
    }


@router.get(
    "/default-medications",
    summary="Get default medication patterns",
    description="Get the list of default medication patterns used in generation.",
)
async def get_default_medications() -> dict:
    """Get default medication patterns."""
    from app.services.synthetic_data_service import DEFAULT_MEDICATION_PATTERNS

    return {
        "medications": [
            {
                "code": m.medication_code,
                "name": m.medication_name,
                "vocabulary": m.vocabulary,
                "associated_conditions": m.associated_conditions,
                "prescription_rate": m.prescription_rate,
            }
            for m in DEFAULT_MEDICATION_PATTERNS
        ],
        "total": len(DEFAULT_MEDICATION_PATTERNS),
    }


@router.get(
    "/default-labs",
    summary="Get default lab correlations",
    description="Get the list of default lab value correlations used in generation.",
)
async def get_default_labs() -> dict:
    """Get default lab correlations."""
    from app.services.synthetic_data_service import DEFAULT_LAB_CORRELATIONS

    return {
        "labs": [
            {
                "code": l.lab_code,
                "name": l.lab_name,
                "vocabulary": l.vocabulary,
                "unit": l.unit,
                "normal_range": l.normal_range,
                "abnormal_conditions": l.abnormal_conditions,
                "abnormal_shift": l.abnormal_shift,
            }
            for l in DEFAULT_LAB_CORRELATIONS
        ],
        "total": len(DEFAULT_LAB_CORRELATIONS),
    }


@router.post(
    "/apply-privacy",
    summary="Apply differential privacy to data",
    description="Apply differential privacy to an existing dataset.",
)
async def apply_privacy(
    data: list[dict],
    epsilon: float = Query(default=1.0, gt=0, le=10),
    columns: list[str] | None = None,
) -> dict:
    """Apply differential privacy to data."""
    service = get_synthetic_data_service()

    protected = service.apply_differential_privacy(
        data=data,
        epsilon=epsilon,
        columns=columns,
    )

    return {
        "original_count": len(data),
        "protected_count": len(protected),
        "epsilon": epsilon,
        "data": protected,
    }
