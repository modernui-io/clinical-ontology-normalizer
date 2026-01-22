"""Integration tests for Knowledge Graph services.

These tests verify that KG services work together correctly,
testing the full data flow from API to database.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import services
from app.services.kg_cache_service import (
    CacheType,
    KGCacheService,
    get_kg_cache_service,
    reset_kg_cache_service,
)
from app.services.kg_tracing_service import (
    KGTracingService,
    SpanStatus,
    get_kg_tracing_service,
    reset_kg_tracing_service,
)


class TestCacheTracingIntegration:
    """Test cache and tracing service integration."""

    @pytest.fixture(autouse=True)
    def reset_services(self) -> None:
        """Reset singleton services before each test."""
        reset_kg_cache_service()
        reset_kg_tracing_service()

    def test_traced_cache_operations(self) -> None:
        """Test that cache operations can be traced."""
        cache = get_kg_cache_service()
        tracer = get_kg_tracing_service()

        with tracer.span("cache_operation") as span:
            # Put value in cache
            cache.put_concept("C0004096", {"name": "Aspirin", "cui": "C0004096"})
            span.set_attribute("operation", "put")

            # Get value from cache
            result = cache.get_concept("C0004096")
            span.set_attribute("cache_hit", result is not None)

        assert span.status == SpanStatus.OK
        assert span.attributes["cache_hit"] is True
        assert span.duration_ms is not None

    def test_cache_miss_tracing(self) -> None:
        """Test tracing of cache misses."""
        cache = get_kg_cache_service()
        tracer = get_kg_tracing_service()

        with tracer.span("cache_lookup") as span:
            result = cache.get_concept("NONEXISTENT")
            span.set_attribute("cache_hit", result is not None)
            span.set_attribute("cui", "NONEXISTENT")

        assert span.attributes["cache_hit"] is False
        assert span.status == SpanStatus.OK

    def test_batch_operations_tracing(self) -> None:
        """Test tracing of batch cache operations."""
        cache = get_kg_cache_service()
        tracer = get_kg_tracing_service()

        concepts = {
            "C0004096": {"name": "Aspirin"},
            "C0007785": {"name": "Cerebral Infarction"},
            "C0011849": {"name": "Diabetes Mellitus"},
        }

        with tracer.span("batch_cache_put") as span:
            for cui, data in concepts.items():
                cache.put_concept(cui, data)
            span.set_attribute("count", len(concepts))

        with tracer.span("batch_cache_get") as span:
            results = [cache.get_concept(cui) for cui in concepts.keys()]
            hits = sum(1 for r in results if r is not None)
            span.set_attribute("hits", hits)
            span.set_attribute("misses", len(concepts) - hits)

        metrics = tracer.get_metrics()
        assert metrics.total_spans >= 2


class TestServiceOrchestration:
    """Test orchestration of multiple services."""

    @pytest.fixture(autouse=True)
    def reset_services(self) -> None:
        """Reset singleton services before each test."""
        reset_kg_cache_service()
        reset_kg_tracing_service()

    def test_cached_graph_query_simulation(self) -> None:
        """Test simulated graph query with caching."""
        cache = get_kg_cache_service()
        tracer = get_kg_tracing_service()

        # Simulate a graph query with caching
        def execute_query(query: str, params: dict) -> dict:
            """Simulate a graph database query with caching."""
            cache_key = f"{query}:{params}"

            with tracer.span("graph_query") as span:
                span.set_attribute("query", query[:50])
                span.set_attribute("params", str(params))

                # Check cache first
                cached = cache.get(CacheType.QUERY_RESULT, cache_key)
                if cached is not None:
                    span.set_attribute("cache_hit", True)
                    return cached

                span.set_attribute("cache_hit", False)

                # Simulate query execution
                result = {
                    "nodes": [
                        {"cui": "C0004096", "name": "Aspirin"},
                        {"cui": "C0007785", "name": "Cerebral Infarction"},
                    ],
                    "relationships": [
                        {"type": "TREATS", "source": "C0004096", "target": "C0007785"}
                    ],
                }

                # Cache the result
                cache.put(CacheType.QUERY_RESULT, cache_key, result)

                return result

        # First query - cache miss
        result1 = execute_query(
            "MATCH (c:Concept)-[r:TREATS]->(d:Disease) RETURN c, r, d",
            {"limit": 10}
        )
        assert len(result1["nodes"]) == 2

        # Second query - cache hit
        result2 = execute_query(
            "MATCH (c:Concept)-[r:TREATS]->(d:Disease) RETURN c, r, d",
            {"limit": 10}
        )
        assert result2 == result1

        # Verify tracing
        recent = tracer.get_recent_spans(2)
        assert len(recent) == 2

        # First span should be cache miss
        assert recent[0].attributes["cache_hit"] is False
        # Second span should be cache hit
        assert recent[1].attributes["cache_hit"] is True

    def test_patient_graph_retrieval(self) -> None:
        """Test patient graph retrieval with caching and tracing."""
        cache = get_kg_cache_service()
        tracer = get_kg_tracing_service()

        patient_id = "P12345"

        def get_patient_graph(pid: str) -> dict:
            """Get patient graph with caching."""
            with tracer.span("get_patient_graph") as span:
                span.set_attribute("patient_id", pid)

                # Check cache
                cached = cache.get_patient_graph(pid)
                if cached:
                    span.add_event("cache_hit")
                    return cached

                span.add_event("cache_miss")

                # Build patient graph
                with tracer.span("build_patient_graph") as build_span:
                    build_span.set_attribute("patient_id", pid)

                    graph = {
                        "patient_id": pid,
                        "nodes": [
                            {"id": "1", "type": "Patient", "name": "John Doe"},
                            {"id": "2", "type": "Condition", "name": "Hypertension"},
                            {"id": "3", "type": "Medication", "name": "Lisinopril"},
                        ],
                        "edges": [
                            {"source": "1", "target": "2", "type": "HAS_CONDITION"},
                            {"source": "1", "target": "3", "type": "TAKES"},
                            {"source": "3", "target": "2", "type": "TREATS"},
                        ],
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                    }

                    # Cache the graph
                    cache.put_patient_graph(pid, graph)

                    return graph

        # First retrieval - builds graph
        graph1 = get_patient_graph(patient_id)
        assert graph1["patient_id"] == patient_id
        assert len(graph1["nodes"]) == 3

        # Second retrieval - uses cache
        graph2 = get_patient_graph(patient_id)
        assert graph2["patient_id"] == patient_id

        # Verify spans
        recent = tracer.get_recent_spans(10)
        span_names = [s.name for s in recent]

        # Should have parent and child spans for first call
        assert "get_patient_graph" in span_names
        assert "build_patient_graph" in span_names


class TestReasoningPathIntegration:
    """Test reasoning path with caching and tracing."""

    @pytest.fixture(autouse=True)
    def reset_services(self) -> None:
        """Reset singleton services before each test."""
        reset_kg_cache_service()
        reset_kg_tracing_service()

    def test_multi_hop_reasoning_path(self) -> None:
        """Test multi-hop reasoning with caching at each hop."""
        cache = get_kg_cache_service()
        tracer = get_kg_tracing_service()

        def find_path(start_cui: str, end_cui: str, max_hops: int = 3) -> dict:
            """Find reasoning path between concepts."""
            with tracer.span("find_reasoning_path") as span:
                span.set_attribute("start", start_cui)
                span.set_attribute("end", end_cui)
                span.set_attribute("max_hops", max_hops)

                # Check path cache
                path_key = f"{start_cui}:{end_cui}:{max_hops}"
                cached_path = cache.get(CacheType.PATH, path_key)
                if cached_path:
                    span.set_attribute("path_cached", True)
                    return cached_path

                span.set_attribute("path_cached", False)

                # Simulate path finding
                path = {
                    "start": start_cui,
                    "end": end_cui,
                    "hops": [
                        {"cui": start_cui, "name": "Aspirin", "step": 0},
                        {"cui": "C0023946", "name": "Liver", "step": 1},
                        {"cui": end_cui, "name": "Hepatotoxicity", "step": 2},
                    ],
                    "relationships": [
                        {"type": "METABOLIZED_BY", "from_step": 0, "to_step": 1},
                        {"type": "MAY_CAUSE", "from_step": 1, "to_step": 2},
                    ],
                    "confidence": 0.85,
                    "evidence_count": 42,
                }

                # Cache the path
                cache.put(CacheType.PATH, path_key, path)

                return path

        # Find path
        path1 = find_path("C0004096", "C0019187", max_hops=3)
        assert path1["confidence"] == 0.85
        assert len(path1["hops"]) == 3

        # Second call should use cache
        path2 = find_path("C0004096", "C0019187", max_hops=3)
        assert path2 == path1

        # Check tracing
        metrics = tracer.get_metrics()
        assert metrics.total_spans == 2

    def test_causal_chain_discovery(self) -> None:
        """Test causal chain discovery with tracing."""
        tracer = get_kg_tracing_service()
        cache = get_kg_cache_service()

        def discover_causal_chains(
            source_cui: str,
            target_cui: str,
            max_depth: int = 5
        ) -> list[dict]:
            """Discover causal chains between concepts."""
            with tracer.span("discover_causal_chains") as span:
                span.set_attribute("source", source_cui)
                span.set_attribute("target", target_cui)
                span.set_attribute("max_depth", max_depth)

                chains = []

                # Simulate chain discovery at each depth
                for depth in range(1, max_depth + 1):
                    with tracer.span(f"search_depth_{depth}") as depth_span:
                        depth_span.set_attribute("depth", depth)

                        # Check cache for this depth
                        cache_key = f"chain:{source_cui}:{target_cui}:{depth}"
                        cached = cache.get(CacheType.QUERY_RESULT, cache_key)

                        if cached:
                            depth_span.add_event("cache_hit", {"depth": depth})
                            chains.extend(cached)
                        else:
                            depth_span.add_event("cache_miss", {"depth": depth})

                            # Simulate finding chains at this depth
                            if depth == 2:
                                new_chains = [{
                                    "depth": depth,
                                    "links": [
                                        {"type": "CAUSES", "confidence": 0.9},
                                        {"type": "LEADS_TO", "confidence": 0.85},
                                    ],
                                    "overall_confidence": 0.765,
                                }]
                                chains.extend(new_chains)
                                cache.put(CacheType.QUERY_RESULT, cache_key, new_chains)

                span.set_attribute("chains_found", len(chains))
                return chains

        chains = discover_causal_chains("C0011849", "C0007785", max_depth=3)
        assert len(chains) > 0

        # Verify nested tracing
        recent = tracer.get_recent_spans(10)
        depth_spans = [s for s in recent if s.name.startswith("search_depth")]
        assert len(depth_spans) == 3


class TestHealthCheckIntegration:
    """Test health check integration across services."""

    @pytest.fixture(autouse=True)
    def reset_services(self) -> None:
        """Reset singleton services before each test."""
        reset_kg_cache_service()
        reset_kg_tracing_service()

    def test_comprehensive_health_check(self) -> None:
        """Test health check that includes all services."""
        cache = get_kg_cache_service()
        tracer = get_kg_tracing_service()

        def check_system_health() -> dict:
            """Check health of all KG services."""
            with tracer.span("health_check") as span:
                health = {
                    "status": "healthy",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "components": {},
                }

                # Check cache health
                with tracer.span("check_cache") as cache_span:
                    try:
                        cache_stats = cache.get_stats()
                        health["components"]["cache"] = {
                            "status": "healthy",
                            "hits": cache_stats.hits,
                            "misses": cache_stats.misses,
                            "hit_rate": cache_stats.hit_rate,
                        }
                        cache_span.set_attribute("status", "healthy")
                    except Exception as e:
                        health["components"]["cache"] = {
                            "status": "unhealthy",
                            "error": str(e),
                        }
                        cache_span.record_exception(e)
                        health["status"] = "degraded"

                # Check tracing health
                with tracer.span("check_tracing") as trace_span:
                    try:
                        trace_metrics = tracer.get_metrics()
                        health["components"]["tracing"] = {
                            "status": "healthy",
                            "total_spans": trace_metrics.total_spans,
                            "error_rate": trace_metrics.to_dict()["error_rate"],
                        }
                        trace_span.set_attribute("status", "healthy")
                    except Exception as e:
                        health["components"]["tracing"] = {
                            "status": "unhealthy",
                            "error": str(e),
                        }
                        trace_span.record_exception(e)
                        health["status"] = "degraded"

                span.set_attribute("overall_status", health["status"])
                return health

        health = check_system_health()
        assert health["status"] == "healthy"
        assert "cache" in health["components"]
        assert "tracing" in health["components"]
        assert health["components"]["cache"]["status"] == "healthy"


class TestConcurrentOperations:
    """Test concurrent operations across services."""

    @pytest.fixture(autouse=True)
    def reset_services(self) -> None:
        """Reset singleton services before each test."""
        reset_kg_cache_service()
        reset_kg_tracing_service()

    def test_concurrent_cache_operations(self) -> None:
        """Test thread-safe cache operations."""
        import concurrent.futures

        cache = get_kg_cache_service()
        tracer = get_kg_tracing_service()

        def worker(worker_id: int) -> dict:
            """Worker that performs cache operations."""
            with tracer.span(f"worker_{worker_id}") as span:
                span.set_attribute("worker_id", worker_id)

                # Put a concept
                cui = f"C{worker_id:07d}"
                cache.put_concept(cui, {"name": f"Concept_{worker_id}", "cui": cui})

                # Get it back
                result = cache.get_concept(cui)

                span.set_attribute("success", result is not None)
                return {"worker_id": worker_id, "success": result is not None}

        # Run concurrent workers
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker, i) for i in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All workers should succeed
        assert all(r["success"] for r in results)

        # Verify all spans were recorded
        metrics = tracer.get_metrics()
        assert metrics.total_spans == 10

    @pytest.mark.asyncio
    async def test_async_operations(self) -> None:
        """Test async operations with tracing."""
        tracer = get_kg_tracing_service()
        cache = get_kg_cache_service()

        @tracer.trace_async("async_concept_lookup")
        async def async_lookup(cui: str) -> dict | None:
            """Async concept lookup."""
            await asyncio.sleep(0.001)  # Simulate async I/O
            return cache.get_concept(cui)

        @tracer.trace_async("async_concept_store")
        async def async_store(cui: str, data: dict) -> None:
            """Async concept store."""
            await asyncio.sleep(0.001)  # Simulate async I/O
            cache.put_concept(cui, data)

        # Store and retrieve concepts concurrently
        cuis = [f"C{i:07d}" for i in range(5)]

        # Store all
        await asyncio.gather(*[
            async_store(cui, {"name": f"Concept_{cui}", "cui": cui})
            for cui in cuis
        ])

        # Retrieve all
        results = await asyncio.gather(*[
            async_lookup(cui) for cui in cuis
        ])

        # All should be found
        assert all(r is not None for r in results)

        # Verify tracing
        metrics = tracer.get_metrics()
        assert metrics.total_spans == 10  # 5 stores + 5 lookups


class TestErrorHandling:
    """Test error handling across services."""

    @pytest.fixture(autouse=True)
    def reset_services(self) -> None:
        """Reset singleton services before each test."""
        reset_kg_cache_service()
        reset_kg_tracing_service()

    def test_traced_error_propagation(self) -> None:
        """Test that errors are properly traced."""
        tracer = get_kg_tracing_service()

        def operation_that_fails() -> None:
            """Operation that raises an error."""
            with tracer.span("failing_operation") as span:
                span.set_attribute("attempt", 1)
                raise ValueError("Simulated failure")

        with pytest.raises(ValueError):
            operation_that_fails()

        # Verify error was recorded
        recent = tracer.get_recent_spans(1)
        assert len(recent) == 1
        assert recent[0].status == SpanStatus.ERROR
        assert "Simulated failure" in recent[0].error

    def test_error_recovery_with_retry(self) -> None:
        """Test error recovery pattern with tracing."""
        tracer = get_kg_tracing_service()
        cache = get_kg_cache_service()

        attempt_count = 0

        def operation_with_retry(max_retries: int = 3) -> dict:
            """Operation that retries on failure."""
            nonlocal attempt_count

            with tracer.span("operation_with_retry") as span:
                span.set_attribute("max_retries", max_retries)

                for attempt in range(max_retries):
                    with tracer.span(f"attempt_{attempt}") as attempt_span:
                        attempt_span.set_attribute("attempt", attempt)
                        attempt_count += 1

                        try:
                            # Fail on first two attempts
                            if attempt < 2:
                                raise ConnectionError(f"Attempt {attempt} failed")

                            # Succeed on third attempt
                            result = {"status": "success", "attempt": attempt}
                            attempt_span.set_attribute("success", True)
                            return result

                        except ConnectionError as e:
                            attempt_span.record_exception(e)
                            if attempt == max_retries - 1:
                                raise

                return {"status": "failed"}

        result = operation_with_retry()
        assert result["status"] == "success"
        assert result["attempt"] == 2
        assert attempt_count == 3

        # Verify spans
        metrics = tracer.get_metrics()
        # 1 parent span + 3 attempt spans
        assert metrics.total_spans == 4
        # 2 error spans (first two attempts)
        assert metrics.error_spans == 2


class TestMetricsCollection:
    """Test metrics collection across services."""

    @pytest.fixture(autouse=True)
    def reset_services(self) -> None:
        """Reset singleton services before each test."""
        reset_kg_cache_service()
        reset_kg_tracing_service()

    def test_combined_metrics(self) -> None:
        """Test combined metrics from cache and tracing."""
        cache = get_kg_cache_service()
        tracer = get_kg_tracing_service()

        # Perform operations
        for i in range(10):
            with tracer.span(f"operation_{i}"):
                cache.put_concept(f"C{i:07d}", {"name": f"Concept_{i}"})
                cache.get_concept(f"C{i:07d}")
                # Simulate some misses
                cache.get_concept(f"C{i+100:07d}")

        # Get combined metrics
        cache_stats = cache.get_stats()
        trace_metrics = tracer.get_metrics()

        # Verify cache stats
        assert cache_stats.hits == 10
        assert cache_stats.misses == 10
        assert cache_stats.hit_rate == 0.5

        # Verify trace metrics
        assert trace_metrics.total_spans == 10
        assert trace_metrics.error_spans == 0

    def test_performance_metrics(self) -> None:
        """Test performance metrics collection."""
        tracer = get_kg_tracing_service()

        # Perform operations with varying durations
        for i in range(5):
            with tracer.span("timed_operation"):
                time.sleep(0.01 * (i + 1))  # 10ms, 20ms, 30ms, 40ms, 50ms

        # Get operation stats
        stats = tracer.get_operation_stats("timed_operation")

        assert stats["operation"] == "timed_operation"
        assert stats["count"] == 5
        assert stats["avg_duration_ms"] >= 30  # Average should be ~30ms
        assert stats["min_duration_ms"] >= 10  # Min should be ~10ms
        assert stats["max_duration_ms"] >= 50  # Max should be ~50ms


class TestDataFlow:
    """Test data flow through the system."""

    @pytest.fixture(autouse=True)
    def reset_services(self) -> None:
        """Reset singleton services before each test."""
        reset_kg_cache_service()
        reset_kg_tracing_service()

    def test_concept_enrichment_flow(self) -> None:
        """Test concept enrichment data flow."""
        cache = get_kg_cache_service()
        tracer = get_kg_tracing_service()

        def enrich_concept(cui: str) -> dict:
            """Enrich a concept with additional data."""
            with tracer.span("enrich_concept") as span:
                span.set_attribute("cui", cui)

                # Step 1: Get base concept
                with tracer.span("get_base_concept"):
                    base = cache.get_concept(cui)
                    if not base:
                        base = {"cui": cui, "name": f"Concept_{cui}"}
                        cache.put_concept(cui, base)

                # Step 2: Get semantic types
                with tracer.span("get_semantic_types"):
                    semantic_types = ["T121", "T109"]  # Drug, Organic Chemical

                # Step 3: Get relationships
                with tracer.span("get_relationships"):
                    relationships = [
                        {"type": "TREATS", "target": "C0011849"},
                        {"type": "MAY_CAUSE", "target": "C0019187"},
                    ]

                # Step 4: Build enriched concept
                enriched = {
                    **base,
                    "semantic_types": semantic_types,
                    "relationships": relationships,
                    "enriched_at": datetime.now(timezone.utc).isoformat(),
                }

                span.set_attribute("relationship_count", len(relationships))
                return enriched

        enriched = enrich_concept("C0004096")
        assert enriched["cui"] == "C0004096"
        assert len(enriched["semantic_types"]) == 2
        assert len(enriched["relationships"]) == 2

        # Verify span hierarchy
        spans = tracer.get_recent_spans(10)
        span_names = [s.name for s in spans]

        assert "enrich_concept" in span_names
        assert "get_base_concept" in span_names
        assert "get_semantic_types" in span_names
        assert "get_relationships" in span_names

    def test_patient_timeline_flow(self) -> None:
        """Test patient timeline data flow."""
        cache = get_kg_cache_service()
        tracer = get_kg_tracing_service()

        def build_patient_timeline(patient_id: str) -> dict:
            """Build patient timeline with events."""
            with tracer.span("build_timeline") as span:
                span.set_attribute("patient_id", patient_id)

                # Get cached timeline
                cached = cache.get_patient_graph(patient_id)
                if cached and "timeline" in cached:
                    span.add_event("cache_hit")
                    return cached["timeline"]

                span.add_event("cache_miss")

                # Build timeline
                events = []

                # Get conditions
                with tracer.span("get_conditions"):
                    events.append({
                        "type": "condition",
                        "date": "2024-01-15",
                        "code": "I10",
                        "description": "Hypertension",
                    })

                # Get medications
                with tracer.span("get_medications"):
                    events.append({
                        "type": "medication",
                        "date": "2024-01-15",
                        "code": "C0023870",
                        "description": "Lisinopril started",
                    })

                # Get labs
                with tracer.span("get_labs"):
                    events.append({
                        "type": "lab",
                        "date": "2024-02-01",
                        "code": "2345-7",
                        "description": "Blood pressure check",
                        "value": "125/80 mmHg",
                    })

                # Sort by date
                events.sort(key=lambda e: e["date"])

                timeline = {
                    "patient_id": patient_id,
                    "events": events,
                    "event_count": len(events),
                }

                # Cache the result
                cache.put_patient_graph(patient_id, {"timeline": timeline})

                span.set_attribute("event_count", len(events))
                return timeline

        timeline = build_patient_timeline("P12345")
        assert timeline["patient_id"] == "P12345"
        assert timeline["event_count"] == 3

        # Verify full trace
        recent = tracer.get_recent_spans(10)
        assert any(s.name == "build_timeline" for s in recent)
        assert any(s.name == "get_conditions" for s in recent)
        assert any(s.name == "get_medications" for s in recent)
        assert any(s.name == "get_labs" for s in recent)
