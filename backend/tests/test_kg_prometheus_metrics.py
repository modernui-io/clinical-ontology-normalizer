"""Tests for KG Prometheus Metrics Service."""

import pytest
import time
import threading
import asyncio

from app.services.kg_prometheus_metrics import (
    MetricType,
    MetricDefinition,
    LabelSet,
    Counter,
    Gauge,
    Histogram,
    Summary,
    KGPrometheusRegistry,
    KGMetricsService,
    get_metrics_service,
    reset_metrics_service,
    metrics_request,
    metrics_neo4j,
)


class TestMetricDefinition:
    """Tests for MetricDefinition."""

    def test_create_counter_definition(self):
        """Create counter definition."""
        defn = MetricDefinition(
            name="test_counter",
            type=MetricType.COUNTER,
            help="Test counter"
        )
        assert defn.name == "test_counter"
        assert defn.type == MetricType.COUNTER

    def test_create_histogram_with_buckets(self):
        """Create histogram with custom buckets."""
        defn = MetricDefinition(
            name="test_histogram",
            type=MetricType.HISTOGRAM,
            help="Test histogram",
            buckets=[0.1, 0.5, 1.0]
        )
        assert defn.buckets == [0.1, 0.5, 1.0]

    def test_create_summary_with_quantiles(self):
        """Create summary with custom quantiles."""
        defn = MetricDefinition(
            name="test_summary",
            type=MetricType.SUMMARY,
            help="Test summary",
            quantiles=[0.5, 0.9, 0.99]
        )
        assert defn.quantiles == [0.5, 0.9, 0.99]

    def test_invalid_metric_name(self):
        """Invalid metric name raises error."""
        with pytest.raises(ValueError):
            MetricDefinition(
                name="invalid-name",
                type=MetricType.COUNTER,
                help="Test"
            )

    def test_invalid_label_name(self):
        """Invalid label name raises error."""
        with pytest.raises(ValueError):
            MetricDefinition(
                name="test_metric",
                type=MetricType.COUNTER,
                help="Test",
                labels=["invalid-label"]
            )

    def test_valid_metric_with_labels(self):
        """Create metric with valid labels."""
        defn = MetricDefinition(
            name="test_metric",
            type=MetricType.COUNTER,
            help="Test",
            labels=["status", "method", "endpoint_type"]
        )
        assert defn.labels == ["status", "method", "endpoint_type"]


class TestLabelSet:
    """Tests for LabelSet."""

    def test_label_set_hash(self):
        """LabelSet is hashable."""
        ls1 = LabelSet({"a": "1", "b": "2"})
        ls2 = LabelSet({"a": "1", "b": "2"})
        assert hash(ls1) == hash(ls2)

    def test_label_set_equality(self):
        """LabelSet equality."""
        ls1 = LabelSet({"a": "1"})
        ls2 = LabelSet({"a": "1"})
        ls3 = LabelSet({"a": "2"})
        assert ls1 == ls2
        assert ls1 != ls3

    def test_empty_label_set(self):
        """Empty label set."""
        ls = LabelSet({})
        assert hash(ls) == hash(LabelSet({}))


class TestCounter:
    """Tests for Counter metric."""

    @pytest.fixture
    def counter(self):
        defn = MetricDefinition(
            name="test_counter",
            type=MetricType.COUNTER,
            help="Test counter",
            labels=["status"]
        )
        return Counter(defn)

    def test_increment(self, counter):
        """Increment counter."""
        counter.inc()
        assert counter.get() == 1.0

    def test_increment_with_value(self, counter):
        """Increment counter with specific value."""
        counter.inc(5.0)
        assert counter.get() == 5.0

    def test_increment_with_labels(self, counter):
        """Increment counter with labels."""
        counter.inc(labels={"status": "success"})
        counter.inc(labels={"status": "error"})
        assert counter.get({"status": "success"}) == 1.0
        assert counter.get({"status": "error"}) == 1.0

    def test_negative_increment_raises(self, counter):
        """Negative increment raises error."""
        with pytest.raises(ValueError):
            counter.inc(-1.0)

    def test_get_all(self, counter):
        """Get all counter values."""
        counter.inc(labels={"status": "success"})
        counter.inc(2.0, labels={"status": "error"})
        all_values = counter.get_all()
        assert len(all_values) == 2

    def test_thread_safety(self, counter):
        """Counter is thread-safe."""
        def increment():
            for _ in range(1000):
                counter.inc()

        threads = [threading.Thread(target=increment) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert counter.get() == 10000.0


class TestGauge:
    """Tests for Gauge metric."""

    @pytest.fixture
    def gauge(self):
        defn = MetricDefinition(
            name="test_gauge",
            type=MetricType.GAUGE,
            help="Test gauge",
            labels=["host"]
        )
        return Gauge(defn)

    def test_set(self, gauge):
        """Set gauge value."""
        gauge.set(42.0)
        assert gauge.get() == 42.0

    def test_increment(self, gauge):
        """Increment gauge."""
        gauge.set(10.0)
        gauge.inc(5.0)
        assert gauge.get() == 15.0

    def test_decrement(self, gauge):
        """Decrement gauge."""
        gauge.set(10.0)
        gauge.dec(3.0)
        assert gauge.get() == 7.0

    def test_set_to_current_time(self, gauge):
        """Set gauge to current time."""
        before = time.time()
        gauge.set_to_current_time()
        after = time.time()
        assert before <= gauge.get() <= after

    def test_gauge_with_labels(self, gauge):
        """Gauge with labels."""
        gauge.set(100.0, labels={"host": "server1"})
        gauge.set(200.0, labels={"host": "server2"})
        assert gauge.get({"host": "server1"}) == 100.0
        assert gauge.get({"host": "server2"}) == 200.0

    def test_get_all(self, gauge):
        """Get all gauge values."""
        gauge.set(1.0, labels={"host": "a"})
        gauge.set(2.0, labels={"host": "b"})
        all_values = gauge.get_all()
        assert len(all_values) == 2


class TestHistogram:
    """Tests for Histogram metric."""

    @pytest.fixture
    def histogram(self):
        defn = MetricDefinition(
            name="test_histogram",
            type=MetricType.HISTOGRAM,
            help="Test histogram",
            labels=["method"],
            buckets=[0.1, 0.5, 1.0, 5.0, float('inf')]
        )
        return Histogram(defn)

    def test_observe(self, histogram):
        """Observe value."""
        histogram.observe(0.25)
        buckets, total, count = histogram.get()
        assert count == 1
        assert total == 0.25

    def test_bucket_counts(self, histogram):
        """Bucket counts are correct."""
        histogram.observe(0.05)  # <= 0.1
        histogram.observe(0.3)   # <= 0.5
        histogram.observe(0.7)   # <= 1.0
        histogram.observe(2.5)   # <= 5.0
        histogram.observe(10.0)  # <= inf

        buckets, total, count = histogram.get()
        assert count == 5
        # Buckets are cumulative in Prometheus format
        assert buckets[0.1] == 1
        assert buckets[0.5] == 2
        assert buckets[1.0] == 3
        assert buckets[5.0] == 4
        assert buckets[float('inf')] == 5

    def test_histogram_with_labels(self, histogram):
        """Histogram with labels."""
        histogram.observe(0.1, labels={"method": "GET"})
        histogram.observe(0.5, labels={"method": "POST"})

        get_buckets, get_sum, get_count = histogram.get({"method": "GET"})
        post_buckets, post_sum, post_count = histogram.get({"method": "POST"})

        assert get_count == 1
        assert post_count == 1

    def test_timer_context_manager(self, histogram):
        """Timer context manager."""
        with histogram.time():
            time.sleep(0.01)

        buckets, total, count = histogram.get()
        assert count == 1
        assert total >= 0.01


class TestSummary:
    """Tests for Summary metric."""

    @pytest.fixture
    def summary(self):
        defn = MetricDefinition(
            name="test_summary",
            type=MetricType.SUMMARY,
            help="Test summary",
            quantiles=[0.5, 0.9, 0.99]
        )
        return Summary(defn, max_observations=100)

    def test_observe(self, summary):
        """Observe value."""
        summary.observe(1.0)
        quantiles, total, count = summary.get()
        assert count == 1
        assert total == 1.0

    def test_quantiles(self, summary):
        """Quantile calculations."""
        for i in range(1, 101):
            summary.observe(float(i))

        quantiles, total, count = summary.get()
        assert count == 100
        assert quantiles[0.5] == 50.0  # median
        assert quantiles[0.9] == 90.0  # 90th percentile

    def test_max_observations(self, summary):
        """Max observations limit."""
        for i in range(200):
            summary.observe(1.0)

        # Should only keep last 100
        quantiles, total, count = summary.get()
        assert count == 200  # Count is total observed

    def test_timer_context_manager(self, summary):
        """Timer context manager."""
        with summary.time():
            time.sleep(0.01)

        quantiles, total, count = summary.get()
        assert count == 1
        assert total >= 0.01


class TestKGPrometheusRegistry:
    """Tests for KGPrometheusRegistry."""

    @pytest.fixture
    def registry(self):
        return KGPrometheusRegistry(prefix="test")

    def test_create_counter(self, registry):
        """Create counter in registry."""
        counter = registry.counter("requests_total", "Total requests")
        assert counter is not None
        counter.inc()
        assert counter.get() == 1.0

    def test_create_gauge(self, registry):
        """Create gauge in registry."""
        gauge = registry.gauge("temperature", "Temperature")
        gauge.set(72.5)
        assert gauge.get() == 72.5

    def test_create_histogram(self, registry):
        """Create histogram in registry."""
        hist = registry.histogram(
            "duration_seconds",
            "Duration",
            buckets=[0.1, 0.5, 1.0]
        )
        hist.observe(0.3)
        buckets, total, count = hist.get()
        assert count == 1

    def test_create_summary(self, registry):
        """Create summary in registry."""
        summary = registry.summary(
            "response_size",
            "Response size",
            quantiles=[0.5, 0.9]
        )
        summary.observe(1024)
        quantiles, total, count = summary.get()
        assert count == 1

    def test_get_metric(self, registry):
        """Get metric by name."""
        registry.counter("my_counter", "My counter")
        metric = registry.get_metric("my_counter")
        assert metric is not None

    def test_get_all_metrics(self, registry):
        """Get all metrics."""
        registry.counter("c1", "Counter 1")
        registry.gauge("g1", "Gauge 1")
        metrics = registry.get_all_metrics()
        assert len(metrics) == 2

    def test_export_counter(self, registry):
        """Export counter in Prometheus format."""
        counter = registry.counter("requests", "Requests", labels=["status"])
        counter.inc(labels={"status": "200"})
        counter.inc(3.0, labels={"status": "500"})

        output = registry.export()
        assert "# HELP test_requests Requests" in output
        assert "# TYPE test_requests counter" in output
        assert 'test_requests{status="200"} 1' in output
        assert 'test_requests{status="500"} 3' in output

    def test_export_gauge(self, registry):
        """Export gauge in Prometheus format."""
        gauge = registry.gauge("temperature", "Temperature")
        gauge.set(72.5)

        output = registry.export()
        assert "# HELP test_temperature Temperature" in output
        assert "# TYPE test_temperature gauge" in output
        assert "test_temperature 72.5" in output

    def test_export_histogram(self, registry):
        """Export histogram in Prometheus format."""
        hist = registry.histogram(
            "duration",
            "Duration",
            buckets=[0.1, 0.5, 1.0, float('inf')]
        )
        hist.observe(0.3)
        hist.observe(0.7)

        output = registry.export()
        assert "# HELP test_duration Duration" in output
        assert "# TYPE test_duration histogram" in output
        assert 'test_duration_bucket{le="0.1"} 0' in output
        assert 'test_duration_bucket{le="0.5"} 1' in output
        assert 'test_duration_bucket{le="1.0"} 2' in output
        assert "test_duration_sum" in output
        assert "test_duration_count" in output


class TestKGMetricsService:
    """Tests for KGMetricsService."""

    @pytest.fixture
    def metrics(self):
        return KGMetricsService(prefix="kg")

    def test_request_metrics_exist(self, metrics):
        """Request metrics are defined."""
        assert metrics.requests_total is not None
        assert metrics.request_duration_seconds is not None
        assert metrics.requests_in_progress is not None

    def test_neo4j_metrics_exist(self, metrics):
        """Neo4j metrics are defined."""
        assert metrics.neo4j_queries_total is not None
        assert metrics.neo4j_query_duration_seconds is not None
        assert metrics.neo4j_pool_connections is not None

    def test_reasoning_metrics_exist(self, metrics):
        """Reasoning metrics are defined."""
        assert metrics.reasoning_queries_total is not None
        assert metrics.reasoning_duration_seconds is not None
        assert metrics.reasoning_paths_found is not None

    def test_cache_metrics_exist(self, metrics):
        """Cache metrics are defined."""
        assert metrics.cache_hits_total is not None
        assert metrics.cache_misses_total is not None
        assert metrics.cache_evictions_total is not None

    def test_umls_metrics_exist(self, metrics):
        """UMLS metrics are defined."""
        assert metrics.umls_concepts_total is not None
        assert metrics.umls_relationships_total is not None
        assert metrics.umls_lookups_total is not None

    def test_embedding_metrics_exist(self, metrics):
        """Embedding metrics are defined."""
        assert metrics.embeddings_generated_total is not None
        assert metrics.embedding_generation_duration_seconds is not None
        assert metrics.similarity_searches_total is not None

    def test_mdt_metrics_exist(self, metrics):
        """MDT metrics are defined."""
        assert metrics.mdt_sessions_total is not None
        assert metrics.mdt_session_duration_seconds is not None
        assert metrics.mdt_agent_recommendations is not None

    def test_batch_metrics_exist(self, metrics):
        """Batch processing metrics are defined."""
        assert metrics.batch_jobs_total is not None
        assert metrics.batch_job_duration_seconds is not None
        assert metrics.batch_items_processed is not None

    def test_circuit_breaker_metrics_exist(self, metrics):
        """Circuit breaker metrics are defined."""
        assert metrics.circuit_breaker_state is not None
        assert metrics.circuit_breaker_failures is not None
        assert metrics.circuit_breaker_opens is not None

    def test_webhook_metrics_exist(self, metrics):
        """Webhook metrics are defined."""
        assert metrics.webhook_deliveries_total is not None
        assert metrics.webhook_delivery_duration_seconds is not None
        assert metrics.webhook_retries is not None

    def test_data_export_metrics_exist(self, metrics):
        """Data export metrics are defined."""
        assert metrics.data_exports_total is not None
        assert metrics.data_export_duration_seconds is not None
        assert metrics.data_export_records is not None

    def test_benchmark_metrics_exist(self, metrics):
        """Benchmark metrics are defined."""
        assert metrics.benchmark_runs_total is not None
        assert metrics.benchmark_score is not None
        assert metrics.benchmark_duration_seconds is not None

    def test_system_metrics_exist(self, metrics):
        """System metrics are defined."""
        assert metrics.memory_usage_bytes is not None
        assert metrics.cpu_usage_percent is not None
        assert metrics.active_threads is not None
        assert metrics.uptime_seconds is not None

    def test_record_request(self, metrics):
        """Record request helper."""
        metrics.record_request("/api/test", "GET", 200, 0.1)
        assert metrics.requests_total.get({
            "endpoint": "/api/test",
            "method": "GET",
            "status": "200"
        }) == 1.0

    def test_record_neo4j_query(self, metrics):
        """Record Neo4j query helper."""
        metrics.record_neo4j_query("path_finding", 0.5, success=True)
        assert metrics.neo4j_queries_total.get({
            "query_type": "path_finding",
            "status": "success"
        }) == 1.0

    def test_record_reasoning_query(self, metrics):
        """Record reasoning query helper."""
        metrics.record_reasoning_query(
            strategy="multi_hop",
            duration=1.5,
            paths_found=10,
            avg_hops=3.2,
            success=True
        )
        assert metrics.reasoning_queries_total.get({
            "strategy": "multi_hop",
            "status": "success"
        }) == 1.0

    def test_record_cache_hit(self, metrics):
        """Record cache hit helper."""
        metrics.record_cache_hit("concept")
        assert metrics.cache_hits_total.get({"cache_type": "concept"}) == 1.0

    def test_record_cache_miss(self, metrics):
        """Record cache miss helper."""
        metrics.record_cache_miss("concept")
        assert metrics.cache_misses_total.get({"cache_type": "concept"}) == 1.0

    def test_update_cache_stats(self, metrics):
        """Update cache stats helper."""
        metrics.update_cache_stats("concept", 1024000, 500)
        assert metrics.cache_size.get({"cache_type": "concept"}) == 1024000
        assert metrics.cache_entries.get({"cache_type": "concept"}) == 500

    def test_record_webhook_delivery(self, metrics):
        """Record webhook delivery helper."""
        metrics.record_webhook_delivery(
            event_type="concept_created",
            duration=0.3,
            success=True,
            retry_count=2
        )
        assert metrics.webhook_deliveries_total.get({
            "event_type": "concept_created",
            "status": "success"
        }) == 1.0
        assert metrics.webhook_retries.get({"event_type": "concept_created"}) == 2.0

    def test_record_data_export(self, metrics):
        """Record data export helper."""
        metrics.record_data_export("csv", 5.0, 10000, success=True)
        assert metrics.data_exports_total.get({
            "format": "csv",
            "status": "success"
        }) == 1.0
        assert metrics.data_export_records.get({"format": "csv"}) == 10000

    def test_update_system_metrics(self, metrics):
        """Update system metrics helper."""
        metrics.update_system_metrics(
            memory_bytes=512000000,
            cpu_percent=35.5,
            threads=8
        )
        assert metrics.memory_usage_bytes.get({"type": "rss"}) == 512000000
        assert metrics.cpu_usage_percent.get() == 35.5
        assert metrics.active_threads.get() == 8

    def test_export(self, metrics):
        """Export all metrics."""
        metrics.record_request("/api/test", "GET", 200, 0.1)
        output = metrics.export()
        assert "kg_requests_total" in output
        assert "# HELP" in output
        assert "# TYPE" in output


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_metrics_service_returns_same_instance(self):
        """Singleton returns same instance."""
        reset_metrics_service()
        m1 = get_metrics_service()
        m2 = get_metrics_service()
        assert m1 is m2
        reset_metrics_service()


class TestDecorators:
    """Tests for metric decorators."""

    def test_metrics_request_decorator(self):
        """Request metrics decorator."""
        metrics = KGMetricsService()

        @metrics_request(metrics, "/api/test")
        def handler(method="GET"):
            return {"status": "ok"}

        result = handler(method="GET")
        assert result == {"status": "ok"}
        assert metrics.requests_total.get({
            "endpoint": "/api/test",
            "method": "GET",
            "status": "200"
        }) == 1.0

    def test_metrics_request_decorator_async(self):
        """Request metrics decorator for async functions."""
        metrics = KGMetricsService()

        @metrics_request(metrics, "/api/async")
        async def async_handler(method="POST"):
            await asyncio.sleep(0.01)
            return {"status": "ok"}

        result = asyncio.run(async_handler(method="POST"))
        assert result == {"status": "ok"}
        assert metrics.requests_total.get({
            "endpoint": "/api/async",
            "method": "POST",
            "status": "200"
        }) == 1.0

    def test_metrics_neo4j_decorator(self):
        """Neo4j metrics decorator."""
        metrics = KGMetricsService()

        @metrics_neo4j(metrics, "concept_lookup")
        def lookup_concept(cui: str):
            return {"cui": cui}

        result = lookup_concept("C0001234")
        assert result == {"cui": "C0001234"}
        assert metrics.neo4j_queries_total.get({
            "query_type": "concept_lookup",
            "status": "success"
        }) == 1.0

    def test_metrics_neo4j_decorator_failure(self):
        """Neo4j metrics decorator on failure."""
        metrics = KGMetricsService()

        @metrics_neo4j(metrics, "failing_query")
        def failing_query():
            raise RuntimeError("Query failed")

        with pytest.raises(RuntimeError):
            failing_query()

        assert metrics.neo4j_queries_total.get({
            "query_type": "failing_query",
            "status": "error"
        }) == 1.0


class TestPrometheusFormat:
    """Tests for Prometheus text format compliance."""

    def test_format_labels_empty(self):
        """Empty labels format correctly."""
        registry = KGPrometheusRegistry()
        assert registry._format_labels({}) == ""

    def test_format_labels_single(self):
        """Single label formats correctly."""
        registry = KGPrometheusRegistry()
        result = registry._format_labels({"method": "GET"})
        assert result == '{method="GET"}'

    def test_format_labels_multiple(self):
        """Multiple labels format correctly."""
        registry = KGPrometheusRegistry()
        result = registry._format_labels({"method": "GET", "status": "200"})
        # Labels should be sorted
        assert result == '{method="GET",status="200"}'

    def test_histogram_bucket_cumulative(self):
        """Histogram buckets are cumulative."""
        registry = KGPrometheusRegistry()
        hist = registry.histogram("test", "Test", buckets=[1, 5, 10, float('inf')])
        hist.observe(2)  # <= 5
        hist.observe(7)  # <= 10
        hist.observe(3)  # <= 5

        output = registry.export()
        lines = output.split("\n")

        # Find bucket lines
        bucket_lines = [l for l in lines if "test_bucket" in l]

        # Verify cumulative counts
        assert 'le="1"} 0' in output  # 0 values <= 1
        assert 'le="5"} 2' in output  # 2 values <= 5
        assert 'le="10"} 3' in output  # 3 values <= 10
        assert 'le="+Inf"} 3' in output  # 3 total values


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
