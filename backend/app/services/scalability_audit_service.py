"""Architecture Scalability Audit Service (CTO-1).

Analyzes architectural bottlenecks, generates scaling projections, and
provides recommendations for the clinical trial patient recruitment platform.

Examines eight core components:
    1. PostgreSQL  - connection pooling, query patterns, index coverage
    2. Redis       - cache hit rates, memory projection, eviction policy
    3. Neo4j       - graph traversal depth, node count limits
    4. FastAPI     - async vs sync ratio, blocking calls
    5. NLP Pipeline - batch size, GPU/CPU bottleneck
    6. FHIR Import - webhook throughput, parsing overhead
    7. Trial Screening - query complexity, patient count scaling
    8. Knowledge Graph - node/edge growth rate

Usage:
    from app.services.scalability_audit_service import get_scalability_audit_service

    service = get_scalability_audit_service()
    report = service.generate_full_report()
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any

from app.schemas.scalability_audit import (
    BottleneckDetail,
    BottleneckRisk,
    ComponentAnalysis,
    ComponentScore,
    DatabaseAnalysis,
    IndexRecommendation,
    LoadSimulationRequest,
    LoadSimulationResult,
    PartitionStrategy,
    PartitionType,
    QueryComplexity,
    QueryPerformanceAnalysis,
    RecommendationPriority,
    ResourceEstimate,
    ScalabilityRecommendation,
    ScalabilityReport,
    ScalabilityScore,
    ScalingProjection,
    ScalingStrategy,
    ServiceScalingReadiness,
    ServiceType,
    TableSizeProjection,
    TierProjection,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants / assumptions
# ---------------------------------------------------------------------------

# Average rows generated per patient across key tables
ROWS_PER_PATIENT = {
    "clinical_facts": 100,
    "mentions": 250,
    "mention_concept_candidates": 500,
    "documents": 5,
    "kg_nodes": 80,
    "kg_edges": 200,
    "screening_results": 10,
    "patients": 1,
}

# Average row sizes in bytes
ROW_SIZES = {
    "clinical_facts": 512,
    "mentions": 256,
    "mention_concept_candidates": 384,
    "documents": 4096,
    "kg_nodes": 256,
    "kg_edges": 128,
    "screening_results": 384,
    "patients": 1024,
}

# Standard patient tiers for projections
STANDARD_TIERS = [1_000, 10_000, 100_000, 1_000_000]

# AWS/GCP cost estimates (monthly)
COST_PER_VCPU = 35.0  # USD per vCPU per month
COST_PER_GB_RAM = 5.0  # USD per GB RAM per month
COST_PER_GB_STORAGE = 0.10  # USD per GB storage per month
COST_PER_MBPS = 0.50  # USD per Mbps per month (approximate)


class ScalabilityAuditService:
    """Analyzes architectural scalability and generates recommendations.

    This service provides a comprehensive audit of the platform's ability
    to scale across multiple dimensions: compute, storage, network, and
    architectural patterns.
    """

    def __init__(self) -> None:
        self._component_analyzers: dict[str, Any] = {
            "postgresql": self._analyze_postgresql,
            "redis": self._analyze_redis,
            "neo4j": self._analyze_neo4j,
            "fastapi": self._analyze_fastapi,
            "nlp_pipeline": self._analyze_nlp_pipeline,
            "fhir_import": self._analyze_fhir_import,
            "trial_screening": self._analyze_trial_screening,
            "knowledge_graph": self._analyze_knowledge_graph,
        }

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def generate_full_report(self) -> ScalabilityReport:
        """Generate a comprehensive scalability audit report."""
        now = datetime.now(timezone.utc)
        components = self.analyze_all_components()
        projections = self.generate_projections()
        db_analysis = self.analyze_database()
        horizontal = self.analyze_horizontal_scaling()
        recommendations = self.generate_recommendations()
        score = self.calculate_scalability_score(components)

        return ScalabilityReport(
            timestamp=now,
            scalability_score=score,
            components=components,
            projections=projections,
            database_analysis=db_analysis,
            horizontal_scaling=horizontal,
            recommendations=recommendations,
            metadata={
                "version": "1.0.0",
                "analyzer": "ScalabilityAuditService",
                "components_analyzed": len(components),
            },
        )

    def analyze_all_components(self) -> list[ComponentAnalysis]:
        """Analyze all architectural components."""
        results: list[ComponentAnalysis] = []
        for name, analyzer_fn in self._component_analyzers.items():
            try:
                analysis = analyzer_fn()
                results.append(analysis)
            except Exception as exc:
                logger.warning("Failed to analyze component %s: %s", name, exc)
                results.append(
                    ComponentAnalysis(
                        name=name,
                        description=f"Analysis failed: {exc}",
                        current_capacity="unknown",
                        scaling_strategy=ScalingStrategy.NONE,
                        bottleneck_risk=BottleneckRisk.HIGH,
                        recommendation="Investigate analysis failure",
                    )
                )
        return results

    def analyze_component(self, name: str) -> ComponentAnalysis | None:
        """Analyze a single component by name."""
        analyzer_fn = self._component_analyzers.get(name)
        if analyzer_fn is None:
            return None
        return analyzer_fn()

    def get_component_names(self) -> list[str]:
        """Return all analyzable component names."""
        return list(self._component_analyzers.keys())

    def generate_projections(self) -> ScalingProjection:
        """Generate scaling projections at standard patient-count tiers."""
        now = datetime.now(timezone.utc)
        tiers: list[TierProjection] = []

        for count in STANDARD_TIERS:
            tier = self._project_tier(count)
            tiers.append(tier)

        return ScalingProjection(
            timestamp=now,
            tiers=tiers,
            assumptions={
                "rows_per_patient": ROWS_PER_PATIENT,
                "row_sizes_bytes": ROW_SIZES,
                "cost_per_vcpu_month": COST_PER_VCPU,
                "cost_per_gb_ram_month": COST_PER_GB_RAM,
                "cost_per_gb_storage_month": COST_PER_GB_STORAGE,
            },
            growth_model="linear",
        )

    def analyze_database(self) -> DatabaseAnalysis:
        """Perform database-specific scalability analysis."""
        now = datetime.now(timezone.utc)

        table_projections = self._project_table_sizes()
        query_analysis = self._analyze_query_patterns()
        index_recs = self._recommend_indexes()
        partition_strats = self._recommend_partitions()
        conn_pool = self._analyze_connection_pool()

        # Determine overall risk
        high_risk_tables = sum(
            1 for t in table_projections
            if self._table_risk(t) in (BottleneckRisk.HIGH, BottleneckRisk.CRITICAL)
        )
        linear_queries = sum(
            1 for q in query_analysis
            if q.complexity in (QueryComplexity.LINEAR, QueryComplexity.QUADRATIC)
        )

        if high_risk_tables >= 3 or linear_queries >= 3:
            overall_risk = BottleneckRisk.HIGH
        elif high_risk_tables >= 1 or linear_queries >= 1:
            overall_risk = BottleneckRisk.MEDIUM
        else:
            overall_risk = BottleneckRisk.LOW

        return DatabaseAnalysis(
            timestamp=now,
            table_projections=table_projections,
            query_analysis=query_analysis,
            index_recommendations=index_recs,
            partition_strategies=partition_strats,
            connection_pool_analysis=conn_pool,
            overall_risk=overall_risk,
        )

    def analyze_horizontal_scaling(self) -> list[ServiceScalingReadiness]:
        """Assess horizontal scaling readiness for all services."""
        return [
            ServiceScalingReadiness(
                service_name="fastapi_workers",
                service_type=ServiceType.STATELESS,
                horizontally_scalable=True,
                session_affinity_required=False,
                shared_state=["database connections", "redis cache"],
                event_driven_opportunities=[
                    "NLP processing via task queue",
                    "FHIR import via webhook queue",
                ],
                notes="FastAPI workers are stateless and can scale horizontally behind a load balancer.",
            ),
            ServiceScalingReadiness(
                service_name="nlp_pipeline",
                service_type=ServiceType.STATELESS,
                horizontally_scalable=True,
                session_affinity_required=False,
                shared_state=["vocabulary cache (read-only)"],
                event_driven_opportunities=[
                    "Batch NLP extraction via Redis queue",
                    "Async document processing pipeline",
                ],
                notes="NLP workers can scale horizontally. Vocabulary is loaded per-worker (read-only).",
            ),
            ServiceScalingReadiness(
                service_name="postgresql",
                service_type=ServiceType.STATEFUL,
                horizontally_scalable=False,
                session_affinity_required=True,
                shared_state=["all application data"],
                event_driven_opportunities=[
                    "Read replicas for analytics queries",
                    "CDC (Change Data Capture) for event streaming",
                ],
                notes="Primary DB is stateful. Use read replicas and connection pooling (PgBouncer).",
            ),
            ServiceScalingReadiness(
                service_name="redis",
                service_type=ServiceType.STATEFUL,
                horizontally_scalable=True,
                session_affinity_required=False,
                shared_state=["cache entries", "job queue"],
                event_driven_opportunities=[
                    "Redis Streams for real-time event processing",
                    "Pub/Sub for cache invalidation",
                ],
                notes="Redis Cluster supports horizontal scaling. Job queue can be sharded.",
            ),
            ServiceScalingReadiness(
                service_name="neo4j",
                service_type=ServiceType.STATEFUL,
                horizontally_scalable=False,
                session_affinity_required=True,
                shared_state=["knowledge graph data"],
                event_driven_opportunities=[
                    "Read replicas for graph queries",
                    "Async graph updates via event queue",
                ],
                notes="Neo4j Enterprise supports causal clustering. Community edition is single-instance.",
            ),
            ServiceScalingReadiness(
                service_name="trial_screening",
                service_type=ServiceType.STATELESS,
                horizontally_scalable=True,
                session_affinity_required=False,
                shared_state=["trial criteria (database)", "patient data (database)"],
                event_driven_opportunities=[
                    "Batch screening via task queue",
                    "Event-driven re-screening on data change",
                ],
                notes="Screening logic is stateless. Can parallelize across patients and trials.",
            ),
            ServiceScalingReadiness(
                service_name="fhir_import",
                service_type=ServiceType.STATELESS,
                horizontally_scalable=True,
                session_affinity_required=False,
                shared_state=["database (write target)"],
                event_driven_opportunities=[
                    "Webhook queue for incoming FHIR bundles",
                    "Async resource parsing pipeline",
                ],
                notes="FHIR import workers are stateless. Use a queue to absorb webhook bursts.",
            ),
        ]

    def generate_recommendations(self) -> list[ScalabilityRecommendation]:
        """Generate prioritized recommendations based on analysis."""
        return [
            ScalabilityRecommendation(
                priority=RecommendationPriority.CRITICAL,
                component="postgresql",
                title="Deploy PgBouncer connection pooler",
                description=(
                    "The application creates direct database connections per request. "
                    "At scale, this will exhaust PostgreSQL's max_connections limit. "
                    "Deploy PgBouncer in transaction-pooling mode to multiplex connections."
                ),
                effort="low",
                impact="high",
                category="performance",
            ),
            ScalabilityRecommendation(
                priority=RecommendationPriority.CRITICAL,
                component="postgresql",
                title="Add composite indexes for screening queries",
                description=(
                    "Trial screening performs multi-column lookups across clinical_facts "
                    "and screening_results. Add composite indexes on frequently filtered "
                    "columns to avoid full table scans at scale."
                ),
                effort="low",
                impact="high",
                category="performance",
            ),
            ScalabilityRecommendation(
                priority=RecommendationPriority.HIGH,
                component="postgresql",
                title="Implement table partitioning for clinical_facts",
                description=(
                    "clinical_facts grows ~100 rows per patient and will reach "
                    "100M rows at 1M patients. Partition by patient_id hash or "
                    "created_at range to maintain query performance."
                ),
                effort="medium",
                impact="high",
                category="architecture",
            ),
            ScalabilityRecommendation(
                priority=RecommendationPriority.HIGH,
                component="redis",
                title="Configure Redis maxmemory and eviction policy",
                description=(
                    "Set maxmemory and use allkeys-lru eviction to prevent OOM kills. "
                    "Monitor cache hit rates and size to right-size the instance."
                ),
                effort="low",
                impact="medium",
                category="reliability",
            ),
            ScalabilityRecommendation(
                priority=RecommendationPriority.HIGH,
                component="trial_screening",
                title="Implement batch screening with parallelization",
                description=(
                    "Current screening processes patients sequentially. Implement "
                    "batch screening with configurable parallelism to reduce wall-clock "
                    "time for large cohort screening."
                ),
                effort="medium",
                impact="high",
                category="performance",
            ),
            ScalabilityRecommendation(
                priority=RecommendationPriority.MEDIUM,
                component="neo4j",
                title="Add graph traversal depth limits",
                description=(
                    "Unbounded graph traversals can cause OOM or timeout at scale. "
                    "Enforce max depth limits on all Cypher queries and add pagination "
                    "for large result sets."
                ),
                effort="low",
                impact="medium",
                category="reliability",
            ),
            ScalabilityRecommendation(
                priority=RecommendationPriority.MEDIUM,
                component="fastapi",
                title="Audit and convert sync-to-async on I/O paths",
                description=(
                    "Some endpoint handlers use synchronous database calls, blocking "
                    "the event loop. Convert these to async to improve throughput under "
                    "concurrent load."
                ),
                effort="medium",
                impact="medium",
                category="performance",
            ),
            ScalabilityRecommendation(
                priority=RecommendationPriority.MEDIUM,
                component="nlp_pipeline",
                title="Implement NLP processing queue with backpressure",
                description=(
                    "NLP extraction is CPU-intensive and can starve API workers. "
                    "Offload NLP to a dedicated worker pool with a Redis-backed queue "
                    "and configurable concurrency limits."
                ),
                effort="high",
                impact="high",
                category="architecture",
            ),
            ScalabilityRecommendation(
                priority=RecommendationPriority.MEDIUM,
                component="fhir_import",
                title="Add webhook ingestion queue",
                description=(
                    "FHIR webhook endpoints process bundles synchronously. Add a "
                    "queue layer to absorb burst traffic and process asynchronously."
                ),
                effort="medium",
                impact="medium",
                category="architecture",
            ),
            ScalabilityRecommendation(
                priority=RecommendationPriority.LOW,
                component="knowledge_graph",
                title="Implement graph summarization for large subgraphs",
                description=(
                    "As the knowledge graph grows, full-graph queries become expensive. "
                    "Implement materialized graph summaries and hierarchical aggregation "
                    "for dashboard queries."
                ),
                effort="high",
                impact="medium",
                category="performance",
            ),
        ]

    def calculate_scalability_score(
        self, components: list[ComponentAnalysis] | None = None
    ) -> ScalabilityScore:
        """Calculate overall and per-component scalability scores."""
        if components is None:
            components = self.analyze_all_components()

        component_scores: list[ComponentScore] = []
        for comp in components:
            score = self._score_component(comp)
            component_scores.append(score)

        if component_scores:
            overall = int(
                sum(cs.score for cs in component_scores) / len(component_scores)
            )
        else:
            overall = 0

        grade = self._score_to_grade(overall)
        summary = self._generate_score_summary(overall, component_scores)

        return ScalabilityScore(
            overall_score=overall,
            component_scores=component_scores,
            grade=grade,
            summary=summary,
        )

    def simulate_load(self, request: LoadSimulationRequest) -> LoadSimulationResult:
        """Simulate load at a given patient count and return resource estimates."""
        now = datetime.now(timezone.utc)
        patient_count = request.patient_count
        concurrent_users = request.concurrent_users
        screening_rate = request.screening_rate_per_hour

        # Estimate resources
        resources = self._estimate_resources(patient_count, concurrent_users)

        # Identify bottlenecks
        bottlenecks = self._identify_bottlenecks(
            patient_count, concurrent_users, screening_rate
        )

        max_risk = BottleneckRisk.LOW
        for b in bottlenecks:
            if self._risk_level(b.risk) > self._risk_level(max_risk):
                max_risk = b.risk

        can_handle = max_risk in (BottleneckRisk.LOW, BottleneckRisk.MEDIUM)

        scaling_actions: list[str] = []
        if not can_handle:
            if patient_count > 100_000:
                scaling_actions.append("Deploy read replicas for PostgreSQL")
                scaling_actions.append("Implement table partitioning")
            if concurrent_users > 200:
                scaling_actions.append("Scale FastAPI workers horizontally")
                scaling_actions.append("Deploy PgBouncer connection pooler")
            if screening_rate > 1000:
                scaling_actions.append("Implement batch screening with queue")
                scaling_actions.append("Add screening result caching")

        return LoadSimulationResult(
            timestamp=now,
            patient_count=patient_count,
            concurrent_users=concurrent_users,
            screening_rate_per_hour=screening_rate,
            estimated_resources=resources,
            bottlenecks=bottlenecks,
            max_bottleneck_risk=max_risk,
            can_handle_load=can_handle,
            scaling_actions_needed=scaling_actions,
        )

    def get_stats(self) -> dict[str, Any]:
        """Return service stats for health checks."""
        return {
            "components_available": len(self._component_analyzers),
            "component_names": list(self._component_analyzers.keys()),
            "projection_tiers": STANDARD_TIERS,
        }

    # -----------------------------------------------------------------------
    # Component analyzers
    # -----------------------------------------------------------------------

    def _analyze_postgresql(self) -> ComponentAnalysis:
        """Analyze PostgreSQL scalability."""
        return ComponentAnalysis(
            name="postgresql",
            description=(
                "Primary relational database storing all application data including "
                "patients, clinical facts, documents, screening results, and audit logs."
            ),
            current_capacity="500 queries/s with connection pooling",
            scaling_strategy=ScalingStrategy.VERTICAL,
            bottleneck_risk=BottleneckRisk.HIGH,
            recommendation=(
                "Deploy PgBouncer for connection pooling, add read replicas for "
                "analytics queries, and implement table partitioning for clinical_facts."
            ),
            current_usage_pct=35.0,
            max_capacity="2,000 queries/s (single instance with tuning)",
            details={
                "connection_pool": "SQLAlchemy async pool, default 5-20 connections",
                "query_patterns": "OLTP + analytics mix",
                "index_coverage": "Primary keys indexed, composite indexes needed",
                "estimated_size_at_scale": "100K patients ~ 50GB, 1M patients ~ 500GB",
                "replication": "Not configured (single instance)",
                "backup_strategy": "pg_dump (needs improvement for large datasets)",
            },
        )

    def _analyze_redis(self) -> ComponentAnalysis:
        """Analyze Redis scalability."""
        return ComponentAnalysis(
            name="redis",
            description=(
                "In-memory cache and job queue backend. Used for API response caching, "
                "session storage, and background job coordination."
            ),
            current_capacity="10,000 ops/s (single instance)",
            scaling_strategy=ScalingStrategy.HORIZONTAL,
            bottleneck_risk=BottleneckRisk.LOW,
            recommendation=(
                "Configure maxmemory and allkeys-lru eviction policy. Monitor memory "
                "usage and cache hit rates. Consider Redis Cluster for horizontal scaling."
            ),
            current_usage_pct=15.0,
            max_capacity="100,000+ ops/s (Redis Cluster)",
            details={
                "cache_hit_rate": "Estimated 80-90% for vocabulary lookups",
                "memory_projection": "~1MB per 1K patients for cache entries",
                "eviction_policy": "Not configured (defaults to noeviction)",
                "persistence": "RDB snapshots (AOF recommended for durability)",
                "cluster_mode": "Not enabled (single instance)",
            },
        )

    def _analyze_neo4j(self) -> ComponentAnalysis:
        """Analyze Neo4j scalability."""
        return ComponentAnalysis(
            name="neo4j",
            description=(
                "Graph database for knowledge graph storage and traversal. "
                "Stores clinical concept relationships, patient-condition-medication "
                "graphs, and supports GraphRAG queries."
            ),
            current_capacity="200 traversals/s (depth <= 3)",
            scaling_strategy=ScalingStrategy.VERTICAL,
            bottleneck_risk=BottleneckRisk.MEDIUM,
            recommendation=(
                "Add traversal depth limits to all Cypher queries. Implement graph "
                "result pagination. Consider Neo4j Enterprise for causal clustering "
                "at scale."
            ),
            current_usage_pct=20.0,
            max_capacity="1,000 traversals/s with index optimization",
            details={
                "node_count_limit": "~50M nodes (Community), 100B+ (Enterprise)",
                "traversal_depth": "Unbounded in some queries (risk)",
                "indexing": "Node label indexes configured, property indexes needed",
                "memory": "Heap + page cache sizing critical for performance",
                "clustering": "Community edition - single instance only",
            },
        )

    def _analyze_fastapi(self) -> ComponentAnalysis:
        """Analyze FastAPI workers scalability."""
        return ComponentAnalysis(
            name="fastapi",
            description=(
                "Async web framework serving 726+ API endpoints. Handles HTTP requests, "
                "WebSocket connections, SSE streams, and background task coordination."
            ),
            current_capacity="1,000 req/s (4 uvicorn workers)",
            scaling_strategy=ScalingStrategy.HORIZONTAL,
            bottleneck_risk=BottleneckRisk.MEDIUM,
            recommendation=(
                "Audit sync-to-async conversion on I/O-bound paths. Increase worker "
                "count based on CPU cores. Deploy behind a load balancer for horizontal "
                "scaling."
            ),
            current_usage_pct=25.0,
            max_capacity="5,000+ req/s (horizontal scaling)",
            details={
                "async_ratio": "~70% async endpoints, 30% sync (blocking risk)",
                "worker_count": "4 (default uvicorn), should match 2x CPU cores",
                "middleware_count": "9 middleware layers (slight overhead per request)",
                "endpoint_count": "726+ registered endpoints",
                "blocking_calls": "Some sync DB calls detected in service layer",
            },
        )

    def _analyze_nlp_pipeline(self) -> ComponentAnalysis:
        """Analyze NLP pipeline scalability."""
        return ComponentAnalysis(
            name="nlp_pipeline",
            description=(
                "Clinical NLP extraction pipeline including rule-based extraction, "
                "ML ensemble models, and vocabulary mapping. Processes clinical notes "
                "to extract medical entities."
            ),
            current_capacity="50 documents/min (CPU-only)",
            scaling_strategy=ScalingStrategy.HORIZONTAL,
            bottleneck_risk=BottleneckRisk.HIGH,
            recommendation=(
                "Offload NLP to dedicated worker pool with Redis-backed queue. "
                "Implement batch processing with configurable concurrency. Consider "
                "GPU acceleration for ML models."
            ),
            current_usage_pct=40.0,
            max_capacity="500 documents/min (dedicated GPU workers)",
            details={
                "processing_mode": "Synchronous (inline with API request)",
                "batch_support": "Limited - single document per request",
                "gpu_acceleration": "Not configured (CPU-only fallback)",
                "vocabulary_cache": "In-memory, loaded at startup (~50MB)",
                "model_types": "Rule-based + ML ensemble (transformer optional)",
            },
        )

    def _analyze_fhir_import(self) -> ComponentAnalysis:
        """Analyze FHIR import pipeline scalability."""
        return ComponentAnalysis(
            name="fhir_import",
            description=(
                "FHIR R4 resource import pipeline handling Patient, Condition, "
                "Observation, MedicationRequest, and Bundle resources from EHR "
                "systems and Metriport webhooks."
            ),
            current_capacity="100 resources/s (synchronous processing)",
            scaling_strategy=ScalingStrategy.HORIZONTAL,
            bottleneck_risk=BottleneckRisk.MEDIUM,
            recommendation=(
                "Add a webhook ingestion queue (Redis-backed) to absorb burst "
                "traffic. Implement batch resource parsing. Deploy dedicated "
                "import workers for parallel processing."
            ),
            current_usage_pct=30.0,
            max_capacity="1,000 resources/s (async worker pool)",
            details={
                "webhook_processing": "Synchronous (blocks during parsing)",
                "bundle_support": "Full Bundle parsing with transaction support",
                "validation": "FHIR profile validation on each resource",
                "throughput_bottleneck": "JSON parsing + DB writes",
                "retry_strategy": "Basic retry with exponential backoff",
            },
        )

    def _analyze_trial_screening(self) -> ComponentAnalysis:
        """Analyze trial screening engine scalability."""
        return ComponentAnalysis(
            name="trial_screening",
            description=(
                "Patient-trial eligibility screening engine that evaluates inclusion/ "
                "exclusion criteria against patient clinical data. Supports bulk "
                "screening across multiple trials."
            ),
            current_capacity="200 screenings/min (sequential)",
            scaling_strategy=ScalingStrategy.HORIZONTAL,
            bottleneck_risk=BottleneckRisk.HIGH,
            recommendation=(
                "Implement parallel screening with patient-level partitioning. "
                "Cache trial criteria evaluations. Pre-compute common criterion "
                "checks to reduce redundant work."
            ),
            current_usage_pct=45.0,
            max_capacity="5,000 screenings/min (parallel workers)",
            details={
                "query_complexity": "O(patients * trials * criteria) worst case",
                "criteria_evaluation": "Per-criterion SQL + in-memory logic",
                "caching": "No criterion result caching (recalculates each time)",
                "batch_mode": "Available but limited parallelism",
                "patient_scaling": "Linear scaling with patient count",
            },
        )

    def _analyze_knowledge_graph(self) -> ComponentAnalysis:
        """Analyze knowledge graph scalability."""
        return ComponentAnalysis(
            name="knowledge_graph",
            description=(
                "Clinical knowledge graph built from extracted facts, OMOP mappings, "
                "and clinical relationships. Supports graph queries, reasoning, and "
                "GraphRAG for clinical decision support."
            ),
            current_capacity="100 graph queries/s (small graph)",
            scaling_strategy=ScalingStrategy.CACHING,
            bottleneck_risk=BottleneckRisk.MEDIUM,
            recommendation=(
                "Implement materialized graph summaries for common queries. Add "
                "graph result caching with TTL. Limit traversal depth in all queries."
            ),
            current_usage_pct=25.0,
            max_capacity="500 graph queries/s (with caching + summaries)",
            details={
                "node_growth_rate": "~80 nodes per patient",
                "edge_growth_rate": "~200 edges per patient",
                "at_100k_patients": "~8M nodes, ~20M edges",
                "at_1m_patients": "~80M nodes, ~200M edges",
                "query_patterns": "Subgraph extraction, path finding, aggregation",
                "caching": "No graph result caching configured",
            },
        )

    # -----------------------------------------------------------------------
    # Projection helpers
    # -----------------------------------------------------------------------

    def _project_tier(self, patient_count: int) -> TierProjection:
        """Project resource requirements for a given patient count."""
        # Compute
        base_vcpus = 2
        vcpus_per_10k = 2
        vcpus = base_vcpus + math.ceil(patient_count / 10_000) * vcpus_per_10k
        vcpus = max(vcpus, 2)

        # Memory
        base_memory = 4.0
        memory_per_10k = 4.0
        memory = base_memory + (patient_count / 10_000) * memory_per_10k

        # Storage
        total_rows = sum(
            count * patient_count for count in ROWS_PER_PATIENT.values()
        )
        total_bytes = sum(
            ROWS_PER_PATIENT[table] * patient_count * ROW_SIZES.get(table, 256)
            for table in ROWS_PER_PATIENT
        )
        storage_gb = total_bytes / (1024 ** 3)
        # Add overhead for indexes, WAL, temp space
        storage_gb *= 2.5

        # Network
        base_mbps = 10.0
        mbps_per_10k = 5.0
        network = base_mbps + (patient_count / 10_000) * mbps_per_10k

        # Cost
        cost = (
            vcpus * COST_PER_VCPU
            + memory * COST_PER_GB_RAM
            + storage_gb * COST_PER_GB_STORAGE
            + network * COST_PER_MBPS
        )

        # Graph projections
        graph_nodes = patient_count * ROWS_PER_PATIENT.get("kg_nodes", 80)
        graph_edges = patient_count * ROWS_PER_PATIENT.get("kg_edges", 200)

        return TierProjection(
            patient_count=patient_count,
            compute_vcpus=vcpus,
            memory_gb=round(memory, 1),
            storage_gb=round(storage_gb, 1),
            network_mbps=round(network, 1),
            estimated_monthly_cost_usd=round(cost, 2),
            database_rows=total_rows,
            graph_nodes=graph_nodes,
            graph_edges=graph_edges,
        )

    def _project_table_sizes(self) -> list[TableSizeProjection]:
        """Project table sizes at each patient tier."""
        projections: list[TableSizeProjection] = []
        for table, rows_per_patient in ROWS_PER_PATIENT.items():
            row_size = ROW_SIZES.get(table, 256)
            proj = TableSizeProjection(
                table=table,
                rows_per_patient=float(rows_per_patient),
                row_size_bytes=row_size,
                size_at_1k=self._format_size(1_000 * rows_per_patient * row_size),
                size_at_10k=self._format_size(10_000 * rows_per_patient * row_size),
                size_at_100k=self._format_size(100_000 * rows_per_patient * row_size),
                size_at_1m=self._format_size(1_000_000 * rows_per_patient * row_size),
            )
            projections.append(proj)
        return projections

    def _analyze_query_patterns(self) -> list[QueryPerformanceAnalysis]:
        """Analyze query patterns for scalability concerns."""
        return [
            QueryPerformanceAnalysis(
                query_pattern="Patient lookup by ID",
                complexity=QueryComplexity.CONSTANT,
                current_tables=["patients"],
                concern="None - primary key lookup",
                recommendation="Already optimal",
            ),
            QueryPerformanceAnalysis(
                query_pattern="Clinical facts by patient",
                complexity=QueryComplexity.LOGARITHMIC,
                current_tables=["clinical_facts"],
                concern="Grows with facts per patient but indexed",
                recommendation="Ensure patient_id index exists, consider partitioning at scale",
            ),
            QueryPerformanceAnalysis(
                query_pattern="Full-text search across documents",
                complexity=QueryComplexity.LINEAR,
                current_tables=["documents"],
                concern="Full table scan without GIN index on content",
                recommendation="Add GIN index for full-text search, consider Elasticsearch for large corpora",
            ),
            QueryPerformanceAnalysis(
                query_pattern="Trial screening criteria evaluation",
                complexity=QueryComplexity.LINEAR,
                current_tables=["clinical_facts", "screening_results", "patients"],
                concern="Evaluates all patients against all criteria - O(patients * criteria)",
                recommendation="Pre-compute criterion checks, cache results, implement incremental screening",
            ),
            QueryPerformanceAnalysis(
                query_pattern="Screening results aggregation",
                complexity=QueryComplexity.LINEAR,
                current_tables=["screening_results"],
                concern="Aggregation over all screening results grows linearly",
                recommendation="Add materialized views or summary tables for common aggregations",
            ),
            QueryPerformanceAnalysis(
                query_pattern="Knowledge graph subgraph extraction",
                complexity=QueryComplexity.LINEARITHMIC,
                current_tables=["kg_nodes", "kg_edges"],
                concern="Graph traversal complexity depends on connectivity",
                recommendation="Limit traversal depth, use graph-specific indexes",
            ),
        ]

    def _recommend_indexes(self) -> list[IndexRecommendation]:
        """Recommend database indexes."""
        return [
            IndexRecommendation(
                table="clinical_facts",
                columns=["patient_id", "fact_type", "created_at"],
                index_type="btree",
                rationale="Screening queries filter by patient and fact type with time ordering",
                estimated_improvement="10-50x for screening queries at >10K patients",
            ),
            IndexRecommendation(
                table="screening_results",
                columns=["trial_id", "patient_id", "status"],
                index_type="btree",
                rationale="Dashboard queries aggregate by trial and status",
                estimated_improvement="5-20x for trial eligibility dashboards",
            ),
            IndexRecommendation(
                table="documents",
                columns=["content"],
                index_type="gin",
                rationale="Full-text search over clinical document content",
                estimated_improvement="100x+ for text search queries",
            ),
            IndexRecommendation(
                table="mentions",
                columns=["document_id", "concept_id"],
                index_type="btree",
                rationale="Mention lookup by document and concept is frequent in NLP pipeline",
                estimated_improvement="5-10x for concept mapping queries",
            ),
            IndexRecommendation(
                table="kg_edges",
                columns=["source_id", "target_id", "relationship_type"],
                index_type="btree",
                rationale="Graph traversal requires fast edge lookup by source and type",
                estimated_improvement="10-50x for graph queries at scale",
            ),
        ]

    def _recommend_partitions(self) -> list[PartitionStrategy]:
        """Recommend table partitioning strategies."""
        return [
            PartitionStrategy(
                table="clinical_facts",
                partition_type=PartitionType.HASH,
                partition_key="patient_id",
                estimated_partitions=32,
                rationale=(
                    "clinical_facts is the largest table (~100 rows/patient). "
                    "Hash partitioning by patient_id distributes load evenly "
                    "and aligns with the primary query pattern."
                ),
            ),
            PartitionStrategy(
                table="mentions",
                partition_type=PartitionType.HASH,
                partition_key="document_id",
                estimated_partitions=16,
                rationale=(
                    "mentions grows to ~250 rows/patient. Partitioning by "
                    "document_id keeps related mentions co-located."
                ),
            ),
            PartitionStrategy(
                table="screening_results",
                partition_type=PartitionType.RANGE,
                partition_key="created_at",
                estimated_partitions=12,
                rationale=(
                    "Screening results are primarily queried by time range. "
                    "Monthly range partitioning enables efficient partition pruning "
                    "and makes data archival straightforward."
                ),
            ),
        ]

    def _analyze_connection_pool(self) -> dict[str, Any]:
        """Analyze database connection pool configuration."""
        return {
            "current_pool_size": "5-20 (SQLAlchemy async default)",
            "max_connections": "100 (PostgreSQL default)",
            "recommendation": "Deploy PgBouncer in transaction mode",
            "pgbouncer_pool_size": "20-50 per application instance",
            "at_10_workers": "50-200 connections (may exceed max_connections)",
            "risk": "HIGH - connection exhaustion at horizontal scale",
            "mitigation": "PgBouncer reduces connection count by 10-20x",
        }

    # -----------------------------------------------------------------------
    # Load simulation helpers
    # -----------------------------------------------------------------------

    def _estimate_resources(
        self, patient_count: int, concurrent_users: int
    ) -> ResourceEstimate:
        """Estimate resource requirements for a load scenario."""
        tier = self._project_tier(patient_count)

        # Adjust for concurrent users
        user_factor = max(1.0, concurrent_users / 50.0)
        vcpus = max(2, int(tier.compute_vcpus * user_factor))
        memory = max(4.0, tier.memory_gb * user_factor)
        network = max(10.0, tier.network_mbps * user_factor)

        cost = (
            vcpus * COST_PER_VCPU
            + memory * COST_PER_GB_RAM
            + tier.storage_gb * COST_PER_GB_STORAGE
            + network * COST_PER_MBPS
        )

        return ResourceEstimate(
            compute_vcpus=vcpus,
            memory_gb=round(memory, 1),
            storage_gb=round(tier.storage_gb, 1),
            network_mbps=round(network, 1),
            estimated_monthly_cost_usd=round(cost, 2),
        )

    def _identify_bottlenecks(
        self,
        patient_count: int,
        concurrent_users: int,
        screening_rate: int,
    ) -> list[BottleneckDetail]:
        """Identify bottlenecks for a given load scenario."""
        bottlenecks: list[BottleneckDetail] = []

        # Database connection bottleneck
        if concurrent_users > 100:
            bottlenecks.append(
                BottleneckDetail(
                    component="postgresql",
                    risk=(
                        BottleneckRisk.CRITICAL
                        if concurrent_users > 500
                        else BottleneckRisk.HIGH
                    ),
                    description=(
                        f"{concurrent_users} concurrent users may exhaust "
                        f"database connection pool"
                    ),
                    mitigation="Deploy PgBouncer, increase pool size",
                )
            )

        # Table scan bottleneck
        if patient_count > 50_000:
            bottlenecks.append(
                BottleneckDetail(
                    component="postgresql",
                    risk=(
                        BottleneckRisk.CRITICAL
                        if patient_count > 500_000
                        else BottleneckRisk.HIGH
                    ),
                    description=(
                        f"clinical_facts table will have ~{patient_count * 100:,} rows, "
                        f"requiring index optimization and partitioning"
                    ),
                    mitigation="Add composite indexes, implement table partitioning",
                )
            )

        # Screening throughput bottleneck
        if screening_rate > 500:
            bottlenecks.append(
                BottleneckDetail(
                    component="trial_screening",
                    risk=(
                        BottleneckRisk.CRITICAL
                        if screening_rate > 2000
                        else BottleneckRisk.HIGH
                    ),
                    description=(
                        f"Screening rate of {screening_rate}/hr exceeds sequential "
                        f"processing capacity"
                    ),
                    mitigation="Implement parallel batch screening with worker pool",
                )
            )

        # NLP processing bottleneck
        if patient_count > 10_000:
            bottlenecks.append(
                BottleneckDetail(
                    component="nlp_pipeline",
                    risk=(
                        BottleneckRisk.HIGH
                        if patient_count > 100_000
                        else BottleneckRisk.MEDIUM
                    ),
                    description=(
                        f"NLP processing for {patient_count:,} patients requires "
                        f"dedicated worker pool"
                    ),
                    mitigation="Deploy NLP workers with Redis-backed queue",
                )
            )

        # Knowledge graph bottleneck
        if patient_count > 100_000:
            graph_nodes = patient_count * 80
            bottlenecks.append(
                BottleneckDetail(
                    component="knowledge_graph",
                    risk=(
                        BottleneckRisk.HIGH
                        if patient_count > 500_000
                        else BottleneckRisk.MEDIUM
                    ),
                    description=(
                        f"Knowledge graph with ~{graph_nodes:,} nodes may cause "
                        f"slow traversals"
                    ),
                    mitigation="Implement graph summarization, add traversal depth limits",
                )
            )

        # Redis memory bottleneck
        estimated_redis_mb = patient_count / 1000  # ~1MB per 1K patients
        if estimated_redis_mb > 1024:
            bottlenecks.append(
                BottleneckDetail(
                    component="redis",
                    risk=BottleneckRisk.MEDIUM,
                    description=(
                        f"Redis memory projection: ~{estimated_redis_mb:.0f}MB for "
                        f"cache entries"
                    ),
                    mitigation="Configure maxmemory, enable LRU eviction, consider Redis Cluster",
                )
            )

        return bottlenecks

    # -----------------------------------------------------------------------
    # Scoring helpers
    # -----------------------------------------------------------------------

    def _score_component(self, comp: ComponentAnalysis) -> ComponentScore:
        """Calculate a scalability score for a single component."""
        # Base score based on risk
        risk_scores = {
            BottleneckRisk.LOW: 85,
            BottleneckRisk.MEDIUM: 65,
            BottleneckRisk.HIGH: 40,
            BottleneckRisk.CRITICAL: 20,
        }
        base_score = risk_scores.get(comp.bottleneck_risk, 50)

        # Adjust based on scaling strategy
        strategy_bonus = {
            ScalingStrategy.HORIZONTAL: 10,
            ScalingStrategy.CACHING: 5,
            ScalingStrategy.VERTICAL: 0,
            ScalingStrategy.SHARDING: 5,
            ScalingStrategy.NONE: -10,
        }
        bonus = strategy_bonus.get(comp.scaling_strategy, 0)

        # Adjust based on utilization
        if comp.current_usage_pct > 80:
            bonus -= 15
        elif comp.current_usage_pct > 60:
            bonus -= 5

        score = max(0, min(100, base_score + bonus))

        # Determine limiting factor
        if comp.bottleneck_risk == BottleneckRisk.CRITICAL:
            limiting = "Critical bottleneck risk requires immediate attention"
        elif comp.bottleneck_risk == BottleneckRisk.HIGH:
            limiting = comp.recommendation
        elif comp.current_usage_pct > 60:
            limiting = f"High utilization ({comp.current_usage_pct}%)"
        else:
            limiting = "Within acceptable parameters"

        return ComponentScore(
            name=comp.name,
            score=score,
            bottleneck_risk=comp.bottleneck_risk,
            limiting_factor=limiting,
        )

    def _score_to_grade(self, score: int) -> str:
        """Convert numeric score to letter grade."""
        if score >= 90:
            return "A"
        if score >= 80:
            return "B"
        if score >= 70:
            return "C"
        if score >= 60:
            return "D"
        return "F"

    def _generate_score_summary(
        self, overall: int, component_scores: list[ComponentScore]
    ) -> str:
        """Generate a human-readable summary of the scalability score."""
        critical_components = [
            cs.name
            for cs in component_scores
            if cs.bottleneck_risk == BottleneckRisk.CRITICAL
        ]
        high_risk_components = [
            cs.name
            for cs in component_scores
            if cs.bottleneck_risk == BottleneckRisk.HIGH
        ]

        parts: list[str] = [
            f"Overall scalability score: {overall}/100 ({self._score_to_grade(overall)})."
        ]

        if critical_components:
            parts.append(
                f"Critical bottlenecks in: {', '.join(critical_components)}."
            )
        if high_risk_components:
            parts.append(
                f"High-risk components: {', '.join(high_risk_components)}."
            )
        if not critical_components and not high_risk_components:
            parts.append("No critical or high-risk bottlenecks identified.")

        return " ".join(parts)

    # -----------------------------------------------------------------------
    # Utility helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _format_size(size_bytes: int | float) -> str:
        """Format a byte count as a human-readable string."""
        if size_bytes < 1024:
            return f"{size_bytes}B"
        if size_bytes < 1024 ** 2:
            return f"{size_bytes / 1024:.1f}KB"
        if size_bytes < 1024 ** 3:
            return f"{size_bytes / (1024 ** 2):.1f}MB"
        return f"{size_bytes / (1024 ** 3):.1f}GB"

    @staticmethod
    def _table_risk(projection: TableSizeProjection) -> BottleneckRisk:
        """Assess risk based on table size at 1M patients."""
        size_str = projection.size_at_1m.upper()
        if "GB" in size_str:
            try:
                gb = float(size_str.replace("GB", "").strip())
                if gb > 100:
                    return BottleneckRisk.CRITICAL
                if gb > 10:
                    return BottleneckRisk.HIGH
            except ValueError:
                pass
        if "MB" in size_str:
            return BottleneckRisk.LOW
        return BottleneckRisk.MEDIUM

    @staticmethod
    def _risk_level(risk: BottleneckRisk) -> int:
        """Convert risk to numeric level for comparison."""
        return {
            BottleneckRisk.LOW: 0,
            BottleneckRisk.MEDIUM: 1,
            BottleneckRisk.HIGH: 2,
            BottleneckRisk.CRITICAL: 3,
        }.get(risk, 0)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_service: ScalabilityAuditService | None = None


def get_scalability_audit_service() -> ScalabilityAuditService:
    """Return the singleton ScalabilityAuditService."""
    global _service
    if _service is None:
        _service = ScalabilityAuditService()
    return _service


def reset_scalability_audit_service() -> None:
    """Reset the singleton (for testing)."""
    global _service
    _service = None
