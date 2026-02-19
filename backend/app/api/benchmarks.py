"""API endpoints for ClinicalIntelligenceBench — NeurIPS 2026.

Provides endpoints for:
- Generating benchmark questions from MIMIC data
- Running benchmark evaluations across ablation conditions
- Retrieving benchmark results and comparison tables
- Exporting results in LaTeX/JSON formats
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.schemas.benchmark import (
    AblationCondition,
    BenchmarkRunResult,
    BenchmarkStatusResponse,
    BenchmarkTask,
    GenerateQuestionsRequest,
    GenerateQuestionsResponse,
    RunBenchmarkRequest,
    RunBenchmarkResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])

# In-memory store for running/completed benchmarks
_benchmark_runs: dict[str, dict[str, Any]] = {}


@router.post("/generate", response_model=GenerateQuestionsResponse)
def generate_questions(
    request: GenerateQuestionsRequest,
    db: Session = Depends(get_db),
) -> GenerateQuestionsResponse:
    """Generate benchmark questions from ingested MIMIC data.

    Queries the KG for assertion-rich, temporal, calculator-relevant,
    and multi-source patient data to create gold-standard questions.
    """
    from app.services.benchmark_generator import BenchmarkGenerator

    generator = BenchmarkGenerator(db)

    if request.task == BenchmarkTask.TASK_A_NEGATION:
        question_set = generator.generate_task_a(request.count)
    elif request.task == BenchmarkTask.TASK_B_TEMPORAL:
        question_set = generator.generate_task_b(request.count)
    elif request.task == BenchmarkTask.TASK_C_CALCULATOR:
        question_set = generator.generate_task_c(request.count)
    elif request.task == BenchmarkTask.TASK_D_FUSION:
        question_set = generator.generate_task_d(request.count)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown task: {request.task}")

    return GenerateQuestionsResponse(
        task=request.task,
        generated_count=question_set.total_count,
        question_set=question_set,
    )


@router.post("/run", response_model=RunBenchmarkResponse)
async def run_benchmark(
    request: RunBenchmarkRequest,
    background_tasks: BackgroundTasks,
) -> RunBenchmarkResponse:
    """Start a benchmark evaluation run.

    Runs the specified tasks and conditions in the background.
    Use GET /benchmarks/{run_id}/status to check progress.
    """
    from datetime import datetime, timezone

    run_id = f"bench_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    # Estimate cost
    total_qs = 0
    if request.tasks:
        task_counts = {
            BenchmarkTask.TASK_A_NEGATION: 200,
            BenchmarkTask.TASK_B_TEMPORAL: 200,
            BenchmarkTask.TASK_C_CALCULATOR: 100,
            BenchmarkTask.TASK_D_FUSION: 100,
        }
        for t in request.tasks:
            total_qs += task_counts.get(t, 100)
    else:
        total_qs = 600

    if request.question_limit:
        total_qs = min(total_qs, request.question_limit * (len(request.tasks or []) or 4))

    n_conditions = len(request.conditions or []) or 5
    total_calls = total_qs * n_conditions
    estimated_cost = total_calls * 0.003  # ~$0.003 per Sonnet call

    _benchmark_runs[run_id] = {
        "status": "started",
        "request": request.model_dump(),
        "progress": 0.0,
        "result": None,
    }

    # Run in background
    background_tasks.add_task(
        _run_benchmark_background, run_id, request,
    )

    return RunBenchmarkResponse(
        run_id=run_id,
        status="started",
        total_questions=total_qs,
        estimated_cost_usd=round(estimated_cost, 2),
    )


async def _run_benchmark_background(
    run_id: str,
    request: RunBenchmarkRequest,
) -> None:
    """Background task to run a benchmark evaluation."""
    try:
        from app.services.benchmark_evaluator import BenchmarkEvaluator

        _benchmark_runs[run_id]["status"] = "running"

        evaluator = BenchmarkEvaluator()
        evaluator.load_questions()

        condition_ids = [c.value for c in request.conditions] if request.conditions else None
        tasks = [t.value for t in request.tasks] if request.tasks else None

        # Run for first patient (multi-patient support is a future extension)
        result = await evaluator.run(
            patient_id=request.patient_ids[0],
            llm_model=request.llm_model,
            llm_provider=request.llm_provider,
            use_llm_judge=request.use_llm_judge,
            tasks=tasks,
            condition_ids=condition_ids,
            question_limit=request.question_limit,
        )

        _benchmark_runs[run_id]["status"] = "completed"
        _benchmark_runs[run_id]["result"] = result
        _benchmark_runs[run_id]["progress"] = 1.0

    except Exception as exc:
        logger.error("Benchmark run %s failed: %s", run_id, exc)
        _benchmark_runs[run_id]["status"] = "failed"
        _benchmark_runs[run_id]["error"] = str(exc)


@router.get("/{run_id}/status", response_model=BenchmarkStatusResponse)
def get_benchmark_status(run_id: str) -> BenchmarkStatusResponse:
    """Get the status of a benchmark run."""
    run = _benchmark_runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Benchmark run {run_id} not found")

    return BenchmarkStatusResponse(
        run_id=run_id,
        status=run["status"],
        progress=run.get("progress", 0.0),
    )


@router.get("/{run_id}/results")
def get_benchmark_results(run_id: str, format: str = "json") -> dict[str, Any]:
    """Get the results of a completed benchmark run.

    Args:
        run_id: The benchmark run ID.
        format: Output format — "json", "markdown", or "latex".
    """
    run = _benchmark_runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Benchmark run {run_id} not found")

    if run["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Run {run_id} is {run['status']}")

    result: BenchmarkRunResult = run["result"]

    if format == "markdown":
        return {"format": "markdown", "table": "TODO: markdown table export"}
    elif format == "latex":
        return {"format": "latex", "table": "TODO: latex table export"}
    else:
        return result.model_dump(mode="json")


@router.get("/conditions", response_model=list[dict[str, str]])
def list_ablation_conditions() -> list[dict[str, str]]:
    """List available ablation conditions."""
    from app.services.ablation_harness import ABLATION_CONDITIONS

    return [
        {
            "id": cond_id,
            "label": cond_def["label"],
            "description": cond_def["description"],
        }
        for cond_id, cond_def in ABLATION_CONDITIONS.items()
    ]


@router.get("/tasks", response_model=list[dict[str, str]])
def list_benchmark_tasks() -> list[dict[str, str]]:
    """List available benchmark tasks."""
    return [
        {"id": t.value, "label": t.name.replace("_", " ").title()}
        for t in BenchmarkTask
    ]
