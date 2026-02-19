"""API routes for research experiment tracking."""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.api.middleware import get_current_user
from app.schemas.research import (
    AssertionAnalytics,
    ComparisonRequest,
    ComparisonResponse,
    ExperimentConfig,
    ExperimentCreate,
    ExperimentListResponse,
    ExperimentResponse,
    ExperimentUpdate,
    ExportRequest,
    ExportResponse,
    KGMetrics,
    MappingQuality,
    MetricListResponse,
    PipelineTimingMetrics,
    RunCreate,
    RunListResponse,
    RunProgressResponse,
    RunResponse,
)
from app.services.research_service import get_research_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/research", tags=["Research"])


# ============================================================================
# Experiment Endpoints
# ============================================================================


@router.post("/experiments", response_model=ExperimentResponse)
async def create_experiment(
    data: ExperimentCreate,
    current_user: dict = Depends(get_current_user),
) -> ExperimentResponse:
    """Create a new research experiment."""
    service = get_research_service()
    user_id = current_user.get("sub") or current_user.get("user_id")
    return service.create_experiment(data, created_by=user_id)


@router.get("/experiments", response_model=ExperimentListResponse)
async def list_experiments(
    status: str | None = Query(None, description="Filter by status"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
) -> ExperimentListResponse:
    """List all research experiments."""
    service = get_research_service()
    experiments, total = service.list_experiments(status=status, offset=offset, limit=limit)
    return ExperimentListResponse(experiments=experiments, total=total)


@router.get("/experiments/{experiment_id}", response_model=ExperimentResponse)
async def get_experiment(
    experiment_id: str,
    current_user: dict = Depends(get_current_user),
) -> ExperimentResponse:
    """Get a research experiment by ID."""
    service = get_research_service()
    result = service.get_experiment(experiment_id)
    if not result:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return result


@router.patch("/experiments/{experiment_id}", response_model=ExperimentResponse)
async def update_experiment(
    experiment_id: str,
    data: ExperimentUpdate,
    current_user: dict = Depends(get_current_user),
) -> ExperimentResponse:
    """Update a research experiment."""
    service = get_research_service()
    result = service.update_experiment(experiment_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return result


@router.delete("/experiments/{experiment_id}")
async def delete_experiment(
    experiment_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Soft-delete a research experiment."""
    service = get_research_service()
    if not service.delete_experiment(experiment_id):
        raise HTTPException(status_code=404, detail="Experiment not found")
    return {"status": "deleted", "id": experiment_id}


@router.post("/experiments/{experiment_id}/start", response_model=ExperimentResponse)
async def start_experiment(
    experiment_id: str,
    current_user: dict = Depends(get_current_user),
) -> ExperimentResponse:
    """Mark an experiment as running."""
    service = get_research_service()
    result = service.start_experiment(experiment_id)
    if not result:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return result


@router.post("/experiments/{experiment_id}/complete", response_model=ExperimentResponse)
async def complete_experiment(
    experiment_id: str,
    current_user: dict = Depends(get_current_user),
) -> ExperimentResponse:
    """Mark an experiment as completed and aggregate metrics."""
    service = get_research_service()
    result = service.complete_experiment(experiment_id)
    if not result:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return result


# ============================================================================
# Run Endpoints
# ============================================================================


@router.post("/runs", response_model=RunResponse)
async def create_run(
    data: RunCreate,
    current_user: dict = Depends(get_current_user),
) -> RunResponse:
    """Create a new experiment run and optionally start MIMIC ingestion."""
    service = get_research_service()

    run = service.create_run(
        experiment_id=data.experiment_id,
        run_config=data.run_config,
    )
    if not run:
        raise HTTPException(status_code=404, detail="Experiment not found")

    # Enqueue background job if CSV path provided
    if data.mimic_csv_path:
        try:
            from app.core.queue import enqueue_job
            from app.jobs.research_run import run_research_experiment

            enqueue_job(
                run_research_experiment,
                run.id,
                data.experiment_id,
                data.mimic_csv_path,
                data.max_rows,
                data.chunk_size,
                data.run_config,
                queue_name="research",
            )
        except Exception as e:
            logger.warning(f"Failed to enqueue research run job: {e}")
            # Still return the run - can be processed manually

    return run


@router.get("/runs", response_model=RunListResponse)
async def list_runs(
    experiment_id: str = Query(..., description="Filter by experiment ID"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
) -> RunListResponse:
    """List runs for an experiment."""
    service = get_research_service()
    runs, total = service.list_runs(experiment_id=experiment_id, offset=offset, limit=limit)
    return RunListResponse(runs=runs, total=total)


@router.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: str,
    current_user: dict = Depends(get_current_user),
) -> RunResponse:
    """Get a run by ID."""
    service = get_research_service()
    result = service.get_run(run_id)
    if not result:
        raise HTTPException(status_code=404, detail="Run not found")
    return result


@router.get("/runs/{run_id}/progress", response_model=RunProgressResponse)
async def get_run_progress(
    run_id: str,
    current_user: dict = Depends(get_current_user),
) -> RunProgressResponse:
    """Poll run progress including MIMIC import status."""
    service = get_research_service()
    run = service.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    mimic_progress = None
    if run.mimic_batch_id:
        try:
            from app.core.redis import get_redis

            redis = get_redis()
            key = f"mimic_import:{run.mimic_batch_id}"
            progress_data = redis.hgetall(key)
            if progress_data:
                mimic_progress = {
                    k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v
                    for k, v in progress_data.items()
                }
        except Exception:
            pass

    docs_total = len(run.document_ids) if run.document_ids else 0
    progress_pct = 100.0 if run.status == "completed" else 0.0
    if mimic_progress:
        try:
            total = int(mimic_progress.get("total_rows", 0))
            processed = int(mimic_progress.get("processed", 0))
            if total > 0:
                progress_pct = min((processed / total) * 100, 100.0)
        except (ValueError, TypeError):
            pass

    return RunProgressResponse(
        run_id=run.id,
        experiment_id=run.experiment_id,
        status=run.status,
        mimic_batch_id=run.mimic_batch_id,
        mimic_progress=mimic_progress,
        documents_total=docs_total,
        progress_percent=round(progress_pct, 1),
    )


# ============================================================================
# Metrics Endpoints
# ============================================================================


@router.get("/runs/{run_id}/metrics", response_model=MetricListResponse)
async def get_run_metrics(
    run_id: str,
    category: str | None = Query(None, description="Filter by category"),
    current_user: dict = Depends(get_current_user),
) -> MetricListResponse:
    """Get all metrics for a run."""
    service = get_research_service()
    metrics = service.get_run_metrics(run_id, category=category)
    return MetricListResponse(metrics=metrics, total=len(metrics))


@router.get("/runs/{run_id}/assertions", response_model=AssertionAnalytics)
async def get_assertion_analytics(
    run_id: str,
    current_user: dict = Depends(get_current_user),
) -> AssertionAnalytics:
    """Get assertion type analytics for a run."""
    service = get_research_service()
    return service.get_assertion_analytics(run_id)


@router.get("/runs/{run_id}/mapping-quality", response_model=MappingQuality)
async def get_mapping_quality(
    run_id: str,
    current_user: dict = Depends(get_current_user),
) -> MappingQuality:
    """Get OMOP mapping quality metrics for a run."""
    service = get_research_service()
    return service.get_mapping_quality(run_id)


@router.get("/runs/{run_id}/kg-metrics", response_model=KGMetrics)
async def get_kg_metrics(
    run_id: str,
    current_user: dict = Depends(get_current_user),
) -> KGMetrics:
    """Get knowledge graph metrics for a run."""
    service = get_research_service()
    return service.get_kg_metrics(run_id)


@router.get("/runs/{run_id}/timing", response_model=PipelineTimingMetrics)
async def get_pipeline_timing(
    run_id: str,
    current_user: dict = Depends(get_current_user),
) -> PipelineTimingMetrics:
    """Get pipeline timing metrics for a run."""
    service = get_research_service()
    return service.get_pipeline_timing(run_id)


# ============================================================================
# Comparison & Export Endpoints
# ============================================================================


@router.post("/compare", response_model=ComparisonResponse)
async def compare_runs(
    data: ComparisonRequest,
    current_user: dict = Depends(get_current_user),
) -> ComparisonResponse:
    """Compare metrics across multiple runs."""
    service = get_research_service()
    return service.compare_runs(data.run_ids, data.metric_categories)


@router.post("/export", response_model=ExportResponse)
async def export_metrics(
    data: ExportRequest,
    current_user: dict = Depends(get_current_user),
) -> ExportResponse:
    """Export metrics as CSV, JSON, or LaTeX."""
    service = get_research_service()
    return service.export_metrics(data.run_ids, data.format, data.metric_categories)


@router.post("/export/download")
async def download_export(
    data: ExportRequest,
    current_user: dict = Depends(get_current_user),
) -> Response:
    """Download exported metrics as a file."""
    service = get_research_service()
    export = service.export_metrics(data.run_ids, data.format, data.metric_categories)
    return Response(
        content=export.content,
        media_type=export.mime_type,
        headers={"Content-Disposition": f'attachment; filename="{export.filename}"'},
    )


# ============================================================================
# NeurIPS 2026 Experiment Endpoints
# ============================================================================


@router.get("/datasets")
async def list_available_datasets(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """List available datasets and document counts for experiments."""
    from app.services.experiment_runner import get_all_datasets

    datasets = get_all_datasets()
    return {
        "datasets": {
            source: {
                "doc_count": ds.doc_count,
                "patient_count": len(ds.patient_ids),
            }
            for source, ds in datasets.items()
        },
        "total_documents": sum(ds.doc_count for ds in datasets.values()),
        "total_patients": sum(len(ds.patient_ids) for ds in datasets.values()),
    }


@router.post("/experiments/neurips/create-all")
async def create_all_neurips_experiments(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Create all 6 NeurIPS 2026 experiment definitions."""
    from app.services.experiment_runner import ExperimentRunner

    runner = ExperimentRunner()
    experiment_ids = runner.create_all_experiments()
    return {"experiment_ids": experiment_ids, "count": len(experiment_ids)}


@router.post("/experiments/neurips/run/{experiment_number}")
async def run_neurips_experiment(
    experiment_number: int,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Run a specific NeurIPS experiment by number (1-6).

    Creates the experiment if it doesn't exist, then executes it
    on available datasets.
    """
    from app.services.experiment_runner import ExperimentRunner, EXPERIMENT_DEFINITIONS

    runner = ExperimentRunner()

    exp_key_map = {
        1: "exp1_pipeline_eval",
        2: "exp2_assertion_ablation",
        3: "exp3_temporal_ablation",
        4: "exp4_graphrag_comparison",
        5: "exp5_benchmark",
        6: "exp6_scalability",
    }

    if experiment_number not in exp_key_map:
        raise HTTPException(status_code=400, detail=f"Invalid experiment number: {experiment_number}. Must be 1-6.")

    key = exp_key_map[experiment_number]

    # Create the experiment
    defn = EXPERIMENT_DEFINITIONS[key]
    config = ExperimentConfig(**defn["config"])
    service = get_research_service()
    exp = service.create_experiment(
        ExperimentCreate(
            name=defn["name"],
            description=defn["description"],
            hypothesis=defn["hypothesis"],
            config=config,
            tags=defn["tags"],
        ),
        created_by="neurips2026_api",
    )
    experiment_id = exp.id

    # Run the experiment
    runner_map = {
        1: runner.run_pipeline_evaluation,
        2: runner.run_assertion_ablation,
        3: runner.run_temporal_ablation,
        4: runner.run_graphrag_comparison,
        6: runner.run_scalability_analysis,
    }

    runner_fn = runner_map.get(experiment_number)
    if runner_fn is None:
        return {
            "experiment_id": experiment_id,
            "status": "created",
            "note": "Experiment 5 (Benchmarks) requires LLM evaluation and must be run separately.",
        }

    service.start_experiment(experiment_id)
    run_ids = runner_fn(experiment_id)

    if run_ids:
        service.complete_experiment(experiment_id)

    return {
        "experiment_id": experiment_id,
        "experiment_number": experiment_number,
        "run_count": len(run_ids),
        "run_ids": run_ids,
        "status": "completed" if run_ids else "no_data",
    }


@router.post("/experiments/neurips/run-all")
async def run_all_neurips_experiments(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Run all 6 NeurIPS 2026 experiments."""
    from app.services.experiment_runner import ExperimentRunner

    runner = ExperimentRunner()
    results = runner.run_all()

    return {
        "experiments": {
            key: {
                "experiment_id": val["experiment_id"],
                "run_count": len(val.get("run_ids", [])),
                "run_ids": val.get("run_ids", []),
                "note": val.get("note", ""),
            }
            for key, val in results.items()
        },
        "total_runs": sum(len(v.get("run_ids", [])) for v in results.values()),
    }


@router.get("/qa-questions/{experiment_number}")
async def get_qa_questions(
    experiment_number: int,
    category: str | None = Query(None, description="Filter by question category"),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Get QA evaluation questions for an experiment."""
    from app.services.qa_evaluation import QAEvaluationService

    qa_service = QAEvaluationService()

    if experiment_number == 2:
        questions = qa_service.get_assertion_questions()
    elif experiment_number == 3:
        questions = qa_service.get_temporal_questions()
    elif experiment_number == 4:
        questions = qa_service.get_rag_questions()
    else:
        raise HTTPException(status_code=400, detail="QA questions only available for experiments 2, 3, 4.")

    if category:
        questions = qa_service.get_questions_by_category(questions, category)

    return {
        "experiment_number": experiment_number,
        "total_questions": len(questions),
        "questions": [
            {
                "question_id": q.question_id,
                "question": q.question,
                "category": q.category,
                "expected_answer": q.expected_answer,
                "assertion_sensitive": q.assertion_sensitive,
                "temporal_sensitive": q.temporal_sensitive,
                "clinical_context": q.clinical_context,
            }
            for q in questions
        ],
    }


# ============================================================================
# MIMIC Note Browser Endpoints
# ============================================================================

MIMIC_DB_PATH = os.environ.get(
    "MIMIC_NOTES_DB",
    str(Path(__file__).resolve().parents[3] / "tools" / "mimic_notes.db"),
)


def _get_notes_db() -> sqlite3.Connection:
    """Get a read-only connection to the MIMIC notes SQLite database."""
    if not os.path.exists(MIMIC_DB_PATH):
        raise HTTPException(
            status_code=503,
            detail="MIMIC notes database not found. Run tools/mimic_loader.py first.",
        )
    conn = sqlite3.connect(f"file:{MIMIC_DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


@router.get("/notes/stats")
async def get_notes_stats(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Get MIMIC note database statistics."""
    conn = _get_notes_db()
    try:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM notes")
        total = c.fetchone()[0]
        c.execute("SELECT note_category, COUNT(*) FROM notes GROUP BY note_category")
        categories = {row[0]: row[1] for row in c.fetchall()}
        c.execute("SELECT COUNT(DISTINCT subject_id) FROM notes")
        unique_patients = c.fetchone()[0]
        return {
            "total": total,
            "categories": categories,
            "unique_patients": unique_patients,
        }
    finally:
        conn.close()


@router.get("/notes/search")
async def search_notes(
    q: str = Query("", description="Full-text search query"),
    category: str = Query("all", description="Note category filter"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Search MIMIC clinical notes with full-text search."""
    conn = _get_notes_db()
    try:
        c = conn.cursor()
        q = q.strip()

        if q:
            # FTS5 search
            fts_query = " ".join(f'"{w}"' for w in q.split() if w)
            cat_clause = ""
            cat_params: list = []
            if category != "all":
                cat_clause = "AND n.note_category = ?"
                cat_params = [category]

            c.execute(
                f"SELECT COUNT(*) FROM notes_fts f JOIN notes n ON n.id = f.rowid WHERE notes_fts MATCH ? {cat_clause}",
                [fts_query] + cat_params,
            )
            total = c.fetchone()[0]

            c.execute(
                f"SELECT n.* FROM notes_fts f JOIN notes n ON n.id = f.rowid WHERE notes_fts MATCH ? {cat_clause} ORDER BY rank LIMIT ? OFFSET ?",
                [fts_query] + cat_params + [limit, offset],
            )
        else:
            cat_clause = ""
            cat_params = []
            if category != "all":
                cat_clause = "WHERE note_category = ?"
                cat_params = [category]

            c.execute(f"SELECT COUNT(*) FROM notes {cat_clause}", cat_params)
            total = c.fetchone()[0]

            c.execute(
                f"SELECT * FROM notes {cat_clause} ORDER BY id LIMIT ? OFFSET ?",
                cat_params + [limit, offset],
            )

        rows = c.fetchall()
        notes = []
        for r in rows:
            d = dict(r)
            text = d.get("text", "")
            if len(text) > 50000:
                d["text"] = text[:50000] + "\n\n... [truncated at 50,000 chars]"
            notes.append(d)

        return {"notes": notes, "total": total}
    finally:
        conn.close()


@router.get("/notes/{note_id}")
async def get_note(
    note_id: int,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Get a single MIMIC note by database ID."""
    conn = _get_notes_db()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM notes WHERE id = ?", [note_id])
        row = c.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Note not found")
        return dict(row)
    finally:
        conn.close()
