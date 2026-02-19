"""Research experiment service for NeurIPS paper data collection."""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_sync_engine
from app.models.clinical_fact import ClinicalFact
from app.models.document import Document
from app.models.knowledge_graph import KGEdge, KGNode
from app.models.mention import Mention, MentionConceptCandidate
from app.models.research_experiment import (
    ExperimentRunStatus,
    ExperimentStatus,
    MetricCategory,
    ResearchExperiment,
    ResearchExperimentMetric,
    ResearchExperimentRun,
)
from app.schemas.research import (
    AssertionAnalytics,
    ComparisonResponse,
    ExperimentCreate,
    ExperimentResponse,
    ExperimentUpdate,
    ExportResponse,
    KGMetrics,
    MappingQuality,
    MetricResponse,
    PipelineTimingMetrics,
    RunComparisonColumn,
    RunResponse,
)

logger = logging.getLogger(__name__)


class ResearchService:
    """Service for managing research experiments, runs, and metrics."""

    # ========================================================================
    # Experiment CRUD
    # ========================================================================

    def create_experiment(self, data: ExperimentCreate, created_by: str | None = None) -> ExperimentResponse:
        with Session(get_sync_engine()) as session:
            experiment = ResearchExperiment(
                id=str(uuid4()),
                name=data.name,
                description=data.description,
                hypothesis=data.hypothesis,
                config=data.config.model_dump(),
                tags=data.tags,
                created_by=created_by,
            )
            session.add(experiment)
            session.commit()
            session.refresh(experiment)
            return self._to_experiment_response(experiment, 0)

    def get_experiment(self, experiment_id: str) -> ExperimentResponse | None:
        with Session(get_sync_engine()) as session:
            experiment = session.get(ResearchExperiment, experiment_id)
            if not experiment or experiment.deleted_at is not None:
                return None
            run_count = session.scalar(
                select(func.count(ResearchExperimentRun.id)).where(
                    ResearchExperimentRun.experiment_id == experiment_id
                )
            )
            return self._to_experiment_response(experiment, run_count or 0)

    def list_experiments(
        self, status: str | None = None, offset: int = 0, limit: int = 50
    ) -> tuple[list[ExperimentResponse], int]:
        with Session(get_sync_engine()) as session:
            query = select(ResearchExperiment).where(ResearchExperiment.deleted_at.is_(None))
            count_query = select(func.count(ResearchExperiment.id)).where(
                ResearchExperiment.deleted_at.is_(None)
            )

            if status:
                query = query.where(ResearchExperiment.status == status)
                count_query = count_query.where(ResearchExperiment.status == status)

            total = session.scalar(count_query) or 0
            experiments = session.scalars(
                query.order_by(ResearchExperiment.created_at.desc()).offset(offset).limit(limit)
            ).all()

            results = []
            for exp in experiments:
                run_count = session.scalar(
                    select(func.count(ResearchExperimentRun.id)).where(
                        ResearchExperimentRun.experiment_id == exp.id
                    )
                )
                results.append(self._to_experiment_response(exp, run_count or 0))

            return results, total

    def update_experiment(self, experiment_id: str, data: ExperimentUpdate) -> ExperimentResponse | None:
        with Session(get_sync_engine()) as session:
            experiment = session.get(ResearchExperiment, experiment_id)
            if not experiment or experiment.deleted_at is not None:
                return None

            if data.name is not None:
                experiment.name = data.name
            if data.description is not None:
                experiment.description = data.description
            if data.hypothesis is not None:
                experiment.hypothesis = data.hypothesis
            if data.config is not None:
                experiment.config = data.config.model_dump()
            if data.tags is not None:
                experiment.tags = data.tags

            experiment.updated_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(experiment)

            run_count = session.scalar(
                select(func.count(ResearchExperimentRun.id)).where(
                    ResearchExperimentRun.experiment_id == experiment_id
                )
            )
            return self._to_experiment_response(experiment, run_count or 0)

    def delete_experiment(self, experiment_id: str) -> bool:
        with Session(get_sync_engine()) as session:
            experiment = session.get(ResearchExperiment, experiment_id)
            if not experiment:
                return False
            experiment.deleted_at = datetime.now(timezone.utc)
            session.commit()
            return True

    def start_experiment(self, experiment_id: str) -> ExperimentResponse | None:
        with Session(get_sync_engine()) as session:
            experiment = session.get(ResearchExperiment, experiment_id)
            if not experiment or experiment.deleted_at is not None:
                return None
            experiment.status = ExperimentStatus.RUNNING
            experiment.started_at = datetime.now(timezone.utc)
            experiment.updated_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(experiment)
            run_count = session.scalar(
                select(func.count(ResearchExperimentRun.id)).where(
                    ResearchExperimentRun.experiment_id == experiment_id
                )
            )
            return self._to_experiment_response(experiment, run_count or 0)

    def complete_experiment(self, experiment_id: str) -> ExperimentResponse | None:
        with Session(get_sync_engine()) as session:
            experiment = session.get(ResearchExperiment, experiment_id)
            if not experiment or experiment.deleted_at is not None:
                return None
            experiment.status = ExperimentStatus.COMPLETED
            experiment.completed_at = datetime.now(timezone.utc)
            experiment.updated_at = datetime.now(timezone.utc)

            # Aggregate summary metrics from all completed runs
            experiment.summary_metrics = self._aggregate_experiment_metrics(session, experiment_id)
            session.commit()
            session.refresh(experiment)
            run_count = session.scalar(
                select(func.count(ResearchExperimentRun.id)).where(
                    ResearchExperimentRun.experiment_id == experiment_id
                )
            )
            return self._to_experiment_response(experiment, run_count or 0)

    # ========================================================================
    # Run Management
    # ========================================================================

    def create_run(
        self,
        experiment_id: str,
        run_config: dict | None = None,
        mimic_batch_id: str | None = None,
    ) -> RunResponse | None:
        with Session(get_sync_engine()) as session:
            experiment = session.get(ResearchExperiment, experiment_id)
            if not experiment or experiment.deleted_at is not None:
                return None

            run = ResearchExperimentRun(
                id=str(uuid4()),
                experiment_id=experiment_id,
                mimic_batch_id=mimic_batch_id,
                run_config=run_config,
                status=ExperimentRunStatus.PENDING,
            )
            session.add(run)
            session.commit()
            session.refresh(run)
            return self._to_run_response(run, 0)

    def get_run(self, run_id: str) -> RunResponse | None:
        with Session(get_sync_engine()) as session:
            run = session.get(ResearchExperimentRun, run_id)
            if not run:
                return None
            metric_count = session.scalar(
                select(func.count(ResearchExperimentMetric.id)).where(
                    ResearchExperimentMetric.run_id == run_id
                )
            )
            return self._to_run_response(run, metric_count or 0)

    def list_runs(
        self, experiment_id: str, offset: int = 0, limit: int = 50
    ) -> tuple[list[RunResponse], int]:
        with Session(get_sync_engine()) as session:
            query = select(ResearchExperimentRun).where(
                ResearchExperimentRun.experiment_id == experiment_id
            )
            total = session.scalar(
                select(func.count(ResearchExperimentRun.id)).where(
                    ResearchExperimentRun.experiment_id == experiment_id
                )
            ) or 0

            runs = session.scalars(
                query.order_by(ResearchExperimentRun.created_at.desc()).offset(offset).limit(limit)
            ).all()

            results = []
            for run in runs:
                metric_count = session.scalar(
                    select(func.count(ResearchExperimentMetric.id)).where(
                        ResearchExperimentMetric.run_id == run.id
                    )
                )
                results.append(self._to_run_response(run, metric_count or 0))

            return results, total

    def update_run_status(
        self,
        run_id: str,
        status: ExperimentRunStatus,
        document_ids: list[str] | None = None,
        patient_ids: list[str] | None = None,
        error: str | None = None,
    ) -> None:
        with Session(get_sync_engine()) as session:
            run = session.get(ResearchExperimentRun, run_id)
            if not run:
                return
            run.status = status
            if status == ExperimentRunStatus.PROCESSING:
                run.started_at = datetime.now(timezone.utc)
            elif status in (ExperimentRunStatus.COMPLETED, ExperimentRunStatus.FAILED):
                run.completed_at = datetime.now(timezone.utc)
            if document_ids is not None:
                run.document_ids = document_ids
            if patient_ids is not None:
                run.patient_ids = patient_ids
            if error is not None:
                run.error = error
            session.commit()

    # ========================================================================
    # Metrics Computation
    # ========================================================================

    def get_assertion_analytics(self, run_id: str) -> AssertionAnalytics:
        with Session(get_sync_engine()) as session:
            run = session.get(ResearchExperimentRun, run_id)
            if not run or not run.document_ids:
                return AssertionAnalytics()

            doc_ids = run.document_ids
            mentions = session.scalars(
                select(Mention).where(Mention.document_id.in_(doc_ids))
            ).all()

            analytics = AssertionAnalytics(total_mentions=len(mentions))
            for m in mentions:
                assertion = getattr(m, "assertion", None) or "present"
                assertion_str = assertion.value if hasattr(assertion, "value") else str(assertion)
                analytics.assertion_counts[assertion_str] = (
                    analytics.assertion_counts.get(assertion_str, 0) + 1
                )

                domain = getattr(m, "domain", "unknown") or "unknown"
                if domain not in analytics.assertion_by_domain:
                    analytics.assertion_by_domain[domain] = {}
                analytics.assertion_by_domain[domain][assertion_str] = (
                    analytics.assertion_by_domain[domain].get(assertion_str, 0) + 1
                )

                temporality = getattr(m, "temporality", None)
                if temporality:
                    temp_str = temporality.value if hasattr(temporality, "value") else str(temporality)
                    analytics.temporality_counts[temp_str] = (
                        analytics.temporality_counts.get(temp_str, 0) + 1
                    )

                experiencer = getattr(m, "experiencer", None)
                if experiencer:
                    exp_str = experiencer.value if hasattr(experiencer, "value") else str(experiencer)
                    analytics.experiencer_counts[exp_str] = (
                        analytics.experiencer_counts.get(exp_str, 0) + 1
                    )

            return analytics

    def get_mapping_quality(self, run_id: str) -> MappingQuality:
        with Session(get_sync_engine()) as session:
            run = session.get(ResearchExperimentRun, run_id)
            if not run or not run.document_ids:
                return MappingQuality()

            doc_ids = run.document_ids
            mentions = session.scalars(
                select(Mention).where(Mention.document_id.in_(doc_ids))
            ).all()

            mention_ids = [m.id for m in mentions]
            if not mention_ids:
                return MappingQuality(total_mentions=0)

            candidates = session.scalars(
                select(MentionConceptCandidate).where(
                    MentionConceptCandidate.mention_id.in_(mention_ids)
                )
            ).all()

            mapped_mention_ids = {c.mention_id for c in candidates}
            total = len(mentions)
            mapped = len(mapped_mention_ids)
            unmapped = total - mapped

            confidences = [c.confidence for c in candidates if c.confidence is not None]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            # Domain coverage
            domain_stats: dict[str, dict[str, int]] = {}
            for m in mentions:
                domain = getattr(m, "domain", "unknown") or "unknown"
                if domain not in domain_stats:
                    domain_stats[domain] = {"total": 0, "mapped": 0}
                domain_stats[domain]["total"] += 1
                if m.id in mapped_mention_ids:
                    domain_stats[domain]["mapped"] += 1

            domain_coverage = {
                d: (s["mapped"] / s["total"] * 100) if s["total"] > 0 else 0.0
                for d, s in domain_stats.items()
            }

            # Top unmapped terms
            unmapped_mentions = [m for m in mentions if m.id not in mapped_mention_ids]
            term_counts: dict[str, int] = {}
            for m in unmapped_mentions:
                text = getattr(m, "text", "") or ""
                if text:
                    term_counts[text] = term_counts.get(text, 0) + 1

            top_unmapped = sorted(term_counts.items(), key=lambda x: x[1], reverse=True)[:20]

            return MappingQuality(
                total_mentions=total,
                mapped_count=mapped,
                unmapped_count=unmapped,
                coverage_percent=(mapped / total * 100) if total > 0 else 0.0,
                avg_confidence=round(avg_confidence, 4),
                domain_coverage=domain_coverage,
                top_unmapped=[{"term": t, "count": c} for t, c in top_unmapped],
            )

    def get_kg_metrics(self, run_id: str) -> KGMetrics:
        with Session(get_sync_engine()) as session:
            run = session.get(ResearchExperimentRun, run_id)
            if not run or not run.patient_ids:
                return KGMetrics()

            patient_ids = run.patient_ids

            total_nodes = session.scalar(
                select(func.count(KGNode.id)).where(KGNode.patient_id.in_(patient_ids))
            ) or 0

            total_edges = session.scalar(
                select(func.count(KGEdge.id)).where(KGEdge.patient_id.in_(patient_ids))
            ) or 0

            unique_concepts = session.scalar(
                select(func.count(func.distinct(KGNode.omop_concept_id))).where(
                    KGNode.patient_id.in_(patient_ids)
                )
            ) or 0

            patient_count = len(patient_ids)
            avg_nodes = total_nodes / patient_count if patient_count > 0 else 0.0

            return KGMetrics(
                total_nodes=total_nodes,
                total_edges=total_edges,
                unique_concepts=unique_concepts,
                patient_count=patient_count,
                avg_nodes_per_patient=round(avg_nodes, 2),
            )

    def get_pipeline_timing(self, run_id: str) -> PipelineTimingMetrics:
        """Get pipeline timing from stored metrics for a run."""
        with Session(get_sync_engine()) as session:
            metrics = session.scalars(
                select(ResearchExperimentMetric).where(
                    ResearchExperimentMetric.run_id == run_id,
                    ResearchExperimentMetric.category == MetricCategory.TIMING,
                )
            ).all()

            if not metrics:
                return PipelineTimingMetrics()

            timing_map = {m.metric_name: m.metric_value for m in metrics}
            return PipelineTimingMetrics(
                avg_nlp_ms=timing_map.get("avg_nlp_ms", 0.0),
                avg_mapping_ms=timing_map.get("avg_mapping_ms", 0.0),
                avg_fact_building_ms=timing_map.get("avg_fact_building_ms", 0.0),
                avg_kg_construction_ms=timing_map.get("avg_kg_construction_ms", 0.0),
                avg_total_ms=timing_map.get("avg_total_ms", 0.0),
                p95_total_ms=timing_map.get("p95_total_ms", 0.0),
                documents_timed=int(timing_map.get("documents_timed", 0)),
            )

    def record_metric(
        self,
        run_id: str,
        category: str,
        metric_name: str,
        metric_value: float,
        detail: dict | None = None,
    ) -> MetricResponse:
        with Session(get_sync_engine()) as session:
            metric = ResearchExperimentMetric(
                id=str(uuid4()),
                run_id=run_id,
                category=MetricCategory(category),
                metric_name=metric_name,
                metric_value=metric_value,
                detail=detail,
            )
            session.add(metric)
            session.commit()
            session.refresh(metric)
            return MetricResponse(
                id=metric.id,
                run_id=metric.run_id,
                category=metric.category.value,
                metric_name=metric.metric_name,
                metric_value=metric.metric_value,
                detail=metric.detail,
                created_at=metric.created_at,
            )

    def get_run_metrics(
        self, run_id: str, category: str | None = None
    ) -> list[MetricResponse]:
        with Session(get_sync_engine()) as session:
            query = select(ResearchExperimentMetric).where(
                ResearchExperimentMetric.run_id == run_id
            )
            if category:
                query = query.where(ResearchExperimentMetric.category == MetricCategory(category))

            metrics = session.scalars(query.order_by(ResearchExperimentMetric.created_at)).all()
            return [
                MetricResponse(
                    id=m.id,
                    run_id=m.run_id,
                    category=m.category.value,
                    metric_name=m.metric_name,
                    metric_value=m.metric_value,
                    detail=m.detail,
                    created_at=m.created_at,
                )
                for m in metrics
            ]

    # ========================================================================
    # Comparison
    # ========================================================================

    def compare_runs(
        self, run_ids: list[str], metric_categories: list[str] | None = None
    ) -> ComparisonResponse:
        with Session(get_sync_engine()) as session:
            columns = []
            all_metric_names: set[str] = set()

            for run_id in run_ids:
                run = session.get(ResearchExperimentRun, run_id)
                if not run:
                    continue

                experiment = session.get(ResearchExperiment, run.experiment_id)
                exp_name = experiment.name if experiment else "Unknown"

                query = select(ResearchExperimentMetric).where(
                    ResearchExperimentMetric.run_id == run_id
                )
                if metric_categories:
                    cats = [MetricCategory(c) for c in metric_categories]
                    query = query.where(ResearchExperimentMetric.category.in_(cats))

                metrics = session.scalars(query).all()
                metric_dict = {}
                for m in metrics:
                    key = f"{m.category.value}/{m.metric_name}"
                    metric_dict[key] = m.metric_value
                    all_metric_names.add(key)

                columns.append(
                    RunComparisonColumn(
                        run_id=run_id,
                        experiment_name=exp_name,
                        status=run.status.value,
                        metrics=metric_dict,
                    )
                )

            return ComparisonResponse(
                metric_names=sorted(all_metric_names),
                runs=columns,
            )

    # ========================================================================
    # Export
    # ========================================================================

    def export_metrics(
        self,
        run_ids: list[str],
        format: str = "csv",
        metric_categories: list[str] | None = None,
    ) -> ExportResponse:
        comparison = self.compare_runs(run_ids, metric_categories)

        if format == "csv":
            return self._export_csv(comparison)
        elif format == "latex":
            return self._export_latex(comparison)
        else:
            return self._export_json(comparison)

    def _export_csv(self, comparison: ComparisonResponse) -> ExportResponse:
        output = io.StringIO()
        writer = csv.writer(output)

        header = ["Metric"] + [r.experiment_name for r in comparison.runs]
        writer.writerow(header)

        for metric_name in comparison.metric_names:
            row = [metric_name]
            for run_col in comparison.runs:
                row.append(str(run_col.metrics.get(metric_name, "")))
            writer.writerow(row)

        return ExportResponse(
            format="csv",
            filename="research_metrics.csv",
            content=output.getvalue(),
            mime_type="text/csv",
        )

    def _export_latex(self, comparison: ComparisonResponse) -> ExportResponse:
        cols = "l" + "r" * len(comparison.runs)
        lines = [
            f"\\begin{{tabular}}{{{cols}}}",
            "\\toprule",
        ]

        header_cells = ["Metric"] + [r.experiment_name for r in comparison.runs]
        lines.append(" & ".join(header_cells) + " \\\\")
        lines.append("\\midrule")

        for metric_name in comparison.metric_names:
            cells = [metric_name.replace("_", "\\_")]
            for run_col in comparison.runs:
                val = run_col.metrics.get(metric_name)
                cells.append(f"{val:.4f}" if val is not None else "--")
            lines.append(" & ".join(cells) + " \\\\")

        lines.append("\\bottomrule")
        lines.append("\\end{tabular}")

        return ExportResponse(
            format="latex",
            filename="research_metrics.tex",
            content="\n".join(lines),
            mime_type="text/plain",
        )

    def _export_json(self, comparison: ComparisonResponse) -> ExportResponse:
        import json

        return ExportResponse(
            format="json",
            filename="research_metrics.json",
            content=json.dumps(comparison.model_dump(), indent=2, default=str),
            mime_type="application/json",
        )

    # ========================================================================
    # Private Helpers
    # ========================================================================

    def _to_experiment_response(
        self, exp: ResearchExperiment, run_count: int
    ) -> ExperimentResponse:
        return ExperimentResponse(
            id=exp.id,
            name=exp.name,
            description=exp.description,
            hypothesis=exp.hypothesis,
            config=exp.config or {},
            status=exp.status.value if hasattr(exp.status, "value") else str(exp.status),
            summary_metrics=exp.summary_metrics,
            tags=exp.tags,
            created_by=exp.created_by,
            created_at=exp.created_at,
            updated_at=exp.updated_at,
            started_at=exp.started_at,
            completed_at=exp.completed_at,
            run_count=run_count,
        )

    def _to_run_response(self, run: ResearchExperimentRun, metric_count: int) -> RunResponse:
        return RunResponse(
            id=run.id,
            experiment_id=run.experiment_id,
            mimic_batch_id=run.mimic_batch_id,
            run_config=run.run_config,
            document_ids=run.document_ids,
            patient_ids=run.patient_ids,
            status=run.status.value if hasattr(run.status, "value") else str(run.status),
            error=run.error,
            created_at=run.created_at,
            started_at=run.started_at,
            completed_at=run.completed_at,
            metric_count=metric_count,
        )

    def _aggregate_experiment_metrics(self, session: Session, experiment_id: str) -> dict:
        """Aggregate metrics across all completed runs for an experiment."""
        completed_runs = session.scalars(
            select(ResearchExperimentRun).where(
                ResearchExperimentRun.experiment_id == experiment_id,
                ResearchExperimentRun.status == ExperimentRunStatus.COMPLETED,
            )
        ).all()

        if not completed_runs:
            return {}

        run_ids = [r.id for r in completed_runs]
        metrics = session.scalars(
            select(ResearchExperimentMetric).where(
                ResearchExperimentMetric.run_id.in_(run_ids)
            )
        ).all()

        summary: dict[str, list[float]] = {}
        for m in metrics:
            key = f"{m.category.value}/{m.metric_name}"
            summary.setdefault(key, []).append(m.metric_value)

        return {
            k: {
                "mean": sum(v) / len(v),
                "min": min(v),
                "max": max(v),
                "count": len(v),
            }
            for k, v in summary.items()
        }


# Singleton accessor
_service: ResearchService | None = None


def get_research_service() -> ResearchService:
    global _service
    if _service is None:
        _service = ResearchService()
    return _service
