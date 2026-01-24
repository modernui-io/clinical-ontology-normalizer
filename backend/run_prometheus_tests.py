#!/usr/bin/env python3
"""Standalone test runner for KG Prometheus Metrics tests."""

import sys
import os
import importlib.util
import traceback
import time
import threading
import asyncio

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Create comprehensive mocks for dependencies
class MockModule:
    def __getattr__(self, name):
        return MockModule()
    def __call__(self, *args, **kwargs):
        return MockModule()

# Mock the problematic modules before any imports
sys.modules["sentence_transformers"] = MockModule()
sys.modules["sentence_transformers"].SentenceTransformer = MockModule()
sys.modules["neo4j"] = MockModule()
sys.modules["neo4j"].GraphDatabase = MockModule()

# Load the module directly
spec = importlib.util.spec_from_file_location(
    "app.services.kg_prometheus_metrics",
    "app/services/kg_prometheus_metrics.py",
    submodule_search_locations=[]
)
metrics_module = importlib.util.module_from_spec(spec)
metrics_module.__package__ = "app.services"
sys.modules["app.services.kg_prometheus_metrics"] = metrics_module
spec.loader.exec_module(metrics_module)

# Import the module under test
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


def run_test(name, test_func):
    """Run a single test."""
    try:
        test_func()
        print(f"  ✓ {name}")
        return True
    except AssertionError as e:
        print(f"  ✗ {name}: {e}")
        return False
    except Exception as e:
        print(f"  ✗ {name}: {type(e).__name__}: {e}")
        traceback.print_exc()
        return False


# MetricDefinition tests
def test_create_counter_definition():
    defn = MetricDefinition(
        name="test_counter",
        type=MetricType.COUNTER,
        help="Test counter"
    )
    assert defn.name == "test_counter"
    assert defn.type == MetricType.COUNTER


def test_create_histogram_with_buckets():
    defn = MetricDefinition(
        name="test_histogram",
        type=MetricType.HISTOGRAM,
        help="Test histogram",
        buckets=[0.1, 0.5, 1.0]
    )
    assert defn.buckets == [0.1, 0.5, 1.0]


def test_create_summary_with_quantiles():
    defn = MetricDefinition(
        name="test_summary",
        type=MetricType.SUMMARY,
        help="Test summary",
        quantiles=[0.5, 0.9, 0.99]
    )
    assert defn.quantiles == [0.5, 0.9, 0.99]


def test_invalid_metric_name():
    try:
        MetricDefinition(
            name="invalid-name",
            type=MetricType.COUNTER,
            help="Test"
        )
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_invalid_label_name():
    try:
        MetricDefinition(
            name="test_metric",
            type=MetricType.COUNTER,
            help="Test",
            labels=["invalid-label"]
        )
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_valid_metric_with_labels():
    defn = MetricDefinition(
        name="test_metric",
        type=MetricType.COUNTER,
        help="Test",
        labels=["status", "method", "endpoint_type"]
    )
    assert defn.labels == ["status", "method", "endpoint_type"]


# LabelSet tests
def test_label_set_hash():
    ls1 = LabelSet({"a": "1", "b": "2"})
    ls2 = LabelSet({"a": "1", "b": "2"})
    assert hash(ls1) == hash(ls2)


def test_label_set_equality():
    ls1 = LabelSet({"a": "1"})
    ls2 = LabelSet({"a": "1"})
    ls3 = LabelSet({"a": "2"})
    assert ls1 == ls2
    assert ls1 != ls3


def test_empty_label_set():
    ls = LabelSet({})
    assert hash(ls) == hash(LabelSet({}))


# Counter tests
def test_counter_increment():
    defn = MetricDefinition(name="test_counter", type=MetricType.COUNTER, help="Test")
    counter = Counter(defn)
    counter.inc()
    assert counter.get() == 1.0


def test_counter_increment_with_value():
    defn = MetricDefinition(name="test_counter", type=MetricType.COUNTER, help="Test")
    counter = Counter(defn)
    counter.inc(5.0)
    assert counter.get() == 5.0


def test_counter_increment_with_labels():
    defn = MetricDefinition(name="test_counter", type=MetricType.COUNTER, help="Test", labels=["status"])
    counter = Counter(defn)
    counter.inc(labels={"status": "success"})
    counter.inc(labels={"status": "error"})
    assert counter.get({"status": "success"}) == 1.0
    assert counter.get({"status": "error"}) == 1.0


def test_counter_negative_increment_raises():
    defn = MetricDefinition(name="test_counter", type=MetricType.COUNTER, help="Test")
    counter = Counter(defn)
    try:
        counter.inc(-1.0)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_counter_get_all():
    defn = MetricDefinition(name="test_counter", type=MetricType.COUNTER, help="Test", labels=["status"])
    counter = Counter(defn)
    counter.inc(labels={"status": "success"})
    counter.inc(2.0, labels={"status": "error"})
    all_values = counter.get_all()
    assert len(all_values) == 2


def test_counter_thread_safety():
    defn = MetricDefinition(name="test_counter", type=MetricType.COUNTER, help="Test")
    counter = Counter(defn)

    def increment():
        for _ in range(1000):
            counter.inc()

    threads = [threading.Thread(target=increment) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert counter.get() == 10000.0


# Gauge tests
def test_gauge_set():
    defn = MetricDefinition(name="test_gauge", type=MetricType.GAUGE, help="Test")
    gauge = Gauge(defn)
    gauge.set(42.0)
    assert gauge.get() == 42.0


def test_gauge_increment():
    defn = MetricDefinition(name="test_gauge", type=MetricType.GAUGE, help="Test")
    gauge = Gauge(defn)
    gauge.set(10.0)
    gauge.inc(5.0)
    assert gauge.get() == 15.0


def test_gauge_decrement():
    defn = MetricDefinition(name="test_gauge", type=MetricType.GAUGE, help="Test")
    gauge = Gauge(defn)
    gauge.set(10.0)
    gauge.dec(3.0)
    assert gauge.get() == 7.0


def test_gauge_set_to_current_time():
    defn = MetricDefinition(name="test_gauge", type=MetricType.GAUGE, help="Test")
    gauge = Gauge(defn)
    before = time.time()
    gauge.set_to_current_time()
    after = time.time()
    assert before <= gauge.get() <= after


def test_gauge_with_labels():
    defn = MetricDefinition(name="test_gauge", type=MetricType.GAUGE, help="Test", labels=["host"])
    gauge = Gauge(defn)
    gauge.set(100.0, labels={"host": "server1"})
    gauge.set(200.0, labels={"host": "server2"})
    assert gauge.get({"host": "server1"}) == 100.0
    assert gauge.get({"host": "server2"}) == 200.0


# Histogram tests
def test_histogram_observe():
    defn = MetricDefinition(name="test_histogram", type=MetricType.HISTOGRAM, help="Test",
                           buckets=[0.1, 0.5, 1.0, 5.0, float('inf')])
    histogram = Histogram(defn)
    histogram.observe(0.25)
    buckets, total, count = histogram.get()
    assert count == 1
    assert total == 0.25


def test_histogram_bucket_counts():
    defn = MetricDefinition(name="test_histogram", type=MetricType.HISTOGRAM, help="Test",
                           buckets=[0.1, 0.5, 1.0, 5.0, float('inf')])
    histogram = Histogram(defn)
    histogram.observe(0.05)
    histogram.observe(0.3)
    histogram.observe(0.7)
    histogram.observe(2.5)
    histogram.observe(10.0)

    buckets, total, count = histogram.get()
    assert count == 5
    assert buckets[0.1] == 1
    assert buckets[0.5] == 2
    assert buckets[1.0] == 3
    assert buckets[5.0] == 4
    assert buckets[float('inf')] == 5


def test_histogram_timer():
    defn = MetricDefinition(name="test_histogram", type=MetricType.HISTOGRAM, help="Test")
    histogram = Histogram(defn)
    with histogram.time():
        time.sleep(0.01)

    buckets, total, count = histogram.get()
    assert count == 1
    assert total >= 0.01


# Summary tests
def test_summary_observe():
    defn = MetricDefinition(name="test_summary", type=MetricType.SUMMARY, help="Test")
    summary = Summary(defn, max_observations=100)
    summary.observe(1.0)
    quantiles, total, count = summary.get()
    assert count == 1
    assert total == 1.0


def test_summary_quantiles():
    defn = MetricDefinition(name="test_summary", type=MetricType.SUMMARY, help="Test",
                           quantiles=[0.5, 0.9, 0.99])
    summary = Summary(defn, max_observations=100)
    for i in range(1, 101):
        summary.observe(float(i))

    quantiles, total, count = summary.get()
    assert count == 100
    assert quantiles[0.5] == 50.0


# Registry tests
def test_registry_create_counter():
    registry = KGPrometheusRegistry(prefix="test")
    counter = registry.counter("requests_total", "Total requests")
    assert counter is not None
    counter.inc()
    assert counter.get() == 1.0


def test_registry_create_gauge():
    registry = KGPrometheusRegistry(prefix="test")
    gauge = registry.gauge("temperature", "Temperature")
    gauge.set(72.5)
    assert gauge.get() == 72.5


def test_registry_create_histogram():
    registry = KGPrometheusRegistry(prefix="test")
    hist = registry.histogram("duration_seconds", "Duration", buckets=[0.1, 0.5, 1.0])
    hist.observe(0.3)
    buckets, total, count = hist.get()
    assert count == 1


def test_registry_create_summary():
    registry = KGPrometheusRegistry(prefix="test")
    summary = registry.summary("response_size", "Response size", quantiles=[0.5, 0.9])
    summary.observe(1024)
    quantiles, total, count = summary.get()
    assert count == 1


def test_registry_get_metric():
    registry = KGPrometheusRegistry(prefix="test")
    registry.counter("my_counter", "My counter")
    metric = registry.get_metric("my_counter")
    assert metric is not None


def test_registry_get_all_metrics():
    registry = KGPrometheusRegistry(prefix="test")
    registry.counter("c1", "Counter 1")
    registry.gauge("g1", "Gauge 1")
    metrics = registry.get_all_metrics()
    assert len(metrics) == 2


def test_registry_export_counter():
    registry = KGPrometheusRegistry(prefix="test")
    counter = registry.counter("requests", "Requests", labels=["status"])
    counter.inc(labels={"status": "200"})
    counter.inc(3.0, labels={"status": "500"})

    output = registry.export()
    assert "# HELP test_requests Requests" in output
    assert "# TYPE test_requests counter" in output
    assert 'test_requests{status="200"} 1' in output
    assert 'test_requests{status="500"} 3' in output


def test_registry_export_gauge():
    registry = KGPrometheusRegistry(prefix="test")
    gauge = registry.gauge("temperature", "Temperature")
    gauge.set(72.5)

    output = registry.export()
    assert "# HELP test_temperature Temperature" in output
    assert "# TYPE test_temperature gauge" in output
    assert "test_temperature 72.5" in output


def test_registry_export_histogram():
    registry = KGPrometheusRegistry(prefix="test")
    hist = registry.histogram("duration", "Duration", buckets=[0.1, 0.5, 1.0, float('inf')])
    hist.observe(0.3)
    hist.observe(0.7)

    output = registry.export()
    assert "# HELP test_duration Duration" in output
    assert "# TYPE test_duration histogram" in output
    assert "test_duration_sum" in output
    assert "test_duration_count" in output


# KGMetricsService tests
def test_metrics_service_request_metrics_exist():
    metrics = KGMetricsService(prefix="kg")
    assert metrics.requests_total is not None
    assert metrics.request_duration_seconds is not None
    assert metrics.requests_in_progress is not None


def test_metrics_service_neo4j_metrics_exist():
    metrics = KGMetricsService(prefix="kg")
    assert metrics.neo4j_queries_total is not None
    assert metrics.neo4j_query_duration_seconds is not None
    assert metrics.neo4j_pool_connections is not None


def test_metrics_service_reasoning_metrics_exist():
    metrics = KGMetricsService(prefix="kg")
    assert metrics.reasoning_queries_total is not None
    assert metrics.reasoning_duration_seconds is not None
    assert metrics.reasoning_paths_found is not None


def test_metrics_service_cache_metrics_exist():
    metrics = KGMetricsService(prefix="kg")
    assert metrics.cache_hits_total is not None
    assert metrics.cache_misses_total is not None
    assert metrics.cache_evictions_total is not None


def test_metrics_service_umls_metrics_exist():
    metrics = KGMetricsService(prefix="kg")
    assert metrics.umls_concepts_total is not None
    assert metrics.umls_relationships_total is not None
    assert metrics.umls_lookups_total is not None


def test_metrics_service_embedding_metrics_exist():
    metrics = KGMetricsService(prefix="kg")
    assert metrics.embeddings_generated_total is not None
    assert metrics.embedding_generation_duration_seconds is not None
    assert metrics.similarity_searches_total is not None


def test_metrics_service_mdt_metrics_exist():
    metrics = KGMetricsService(prefix="kg")
    assert metrics.mdt_sessions_total is not None
    assert metrics.mdt_session_duration_seconds is not None
    assert metrics.mdt_agent_recommendations is not None


def test_metrics_service_batch_metrics_exist():
    metrics = KGMetricsService(prefix="kg")
    assert metrics.batch_jobs_total is not None
    assert metrics.batch_job_duration_seconds is not None
    assert metrics.batch_items_processed is not None


def test_metrics_service_circuit_breaker_metrics_exist():
    metrics = KGMetricsService(prefix="kg")
    assert metrics.circuit_breaker_state is not None
    assert metrics.circuit_breaker_failures is not None
    assert metrics.circuit_breaker_opens is not None


def test_metrics_service_webhook_metrics_exist():
    metrics = KGMetricsService(prefix="kg")
    assert metrics.webhook_deliveries_total is not None
    assert metrics.webhook_delivery_duration_seconds is not None
    assert metrics.webhook_retries is not None


def test_metrics_service_data_export_metrics_exist():
    metrics = KGMetricsService(prefix="kg")
    assert metrics.data_exports_total is not None
    assert metrics.data_export_duration_seconds is not None
    assert metrics.data_export_records is not None


def test_metrics_service_benchmark_metrics_exist():
    metrics = KGMetricsService(prefix="kg")
    assert metrics.benchmark_runs_total is not None
    assert metrics.benchmark_score is not None
    assert metrics.benchmark_duration_seconds is not None


def test_metrics_service_system_metrics_exist():
    metrics = KGMetricsService(prefix="kg")
    assert metrics.memory_usage_bytes is not None
    assert metrics.cpu_usage_percent is not None
    assert metrics.active_threads is not None
    assert metrics.uptime_seconds is not None


def test_metrics_service_record_request():
    metrics = KGMetricsService(prefix="kg")
    metrics.record_request("/api/test", "GET", 200, 0.1)
    assert metrics.requests_total.get({
        "endpoint": "/api/test",
        "method": "GET",
        "status": "200"
    }) == 1.0


def test_metrics_service_record_neo4j_query():
    metrics = KGMetricsService(prefix="kg")
    metrics.record_neo4j_query("path_finding", 0.5, success=True)
    assert metrics.neo4j_queries_total.get({
        "query_type": "path_finding",
        "status": "success"
    }) == 1.0


def test_metrics_service_record_reasoning_query():
    metrics = KGMetricsService(prefix="kg")
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


def test_metrics_service_record_cache_hit():
    metrics = KGMetricsService(prefix="kg")
    metrics.record_cache_hit("concept")
    assert metrics.cache_hits_total.get({"cache_type": "concept"}) == 1.0


def test_metrics_service_record_cache_miss():
    metrics = KGMetricsService(prefix="kg")
    metrics.record_cache_miss("concept")
    assert metrics.cache_misses_total.get({"cache_type": "concept"}) == 1.0


def test_metrics_service_update_cache_stats():
    metrics = KGMetricsService(prefix="kg")
    metrics.update_cache_stats("concept", 1024000, 500)
    assert metrics.cache_size.get({"cache_type": "concept"}) == 1024000
    assert metrics.cache_entries.get({"cache_type": "concept"}) == 500


def test_metrics_service_record_webhook_delivery():
    metrics = KGMetricsService(prefix="kg")
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


def test_metrics_service_record_data_export():
    metrics = KGMetricsService(prefix="kg")
    metrics.record_data_export("csv", 5.0, 10000, success=True)
    assert metrics.data_exports_total.get({
        "format": "csv",
        "status": "success"
    }) == 1.0
    assert metrics.data_export_records.get({"format": "csv"}) == 10000


def test_metrics_service_update_system_metrics():
    metrics = KGMetricsService(prefix="kg")
    metrics.update_system_metrics(
        memory_bytes=512000000,
        cpu_percent=35.5,
        threads=8
    )
    assert metrics.memory_usage_bytes.get({"type": "rss"}) == 512000000
    assert metrics.cpu_usage_percent.get() == 35.5
    assert metrics.active_threads.get() == 8


def test_metrics_service_export():
    metrics = KGMetricsService(prefix="kg")
    metrics.record_request("/api/test", "GET", 200, 0.1)
    output = metrics.export()
    assert "kg_requests_total" in output
    assert "# HELP" in output
    assert "# TYPE" in output


def test_singleton_returns_same_instance():
    reset_metrics_service()
    m1 = get_metrics_service()
    m2 = get_metrics_service()
    assert m1 is m2
    reset_metrics_service()


def test_metrics_request_decorator():
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


def test_metrics_neo4j_decorator():
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


def test_metrics_neo4j_decorator_failure():
    metrics = KGMetricsService()

    @metrics_neo4j(metrics, "failing_query")
    def failing_query():
        raise RuntimeError("Query failed")

    try:
        failing_query()
        assert False, "Should have raised"
    except RuntimeError:
        pass

    assert metrics.neo4j_queries_total.get({
        "query_type": "failing_query",
        "status": "error"
    }) == 1.0


def test_format_labels_empty():
    registry = KGPrometheusRegistry()
    assert registry._format_labels({}) == ""


def test_format_labels_single():
    registry = KGPrometheusRegistry()
    result = registry._format_labels({"method": "GET"})
    assert result == '{method="GET"}'


def test_format_labels_multiple():
    registry = KGPrometheusRegistry()
    result = registry._format_labels({"method": "GET", "status": "200"})
    assert result == '{method="GET",status="200"}'


def test_histogram_bucket_cumulative():
    registry = KGPrometheusRegistry()
    hist = registry.histogram("test", "Test", buckets=[1, 5, 10, float('inf')])
    hist.observe(2)
    hist.observe(7)
    hist.observe(3)

    output = registry.export()
    assert 'le="1"} 0' in output
    assert 'le="5"} 2' in output
    assert 'le="10"} 3' in output
    assert 'le="+Inf"} 3' in output


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("KG Prometheus Metrics Tests")
    print("=" * 60 + "\n")

    tests = [
        # MetricDefinition tests
        ("create_counter_definition", test_create_counter_definition),
        ("create_histogram_with_buckets", test_create_histogram_with_buckets),
        ("create_summary_with_quantiles", test_create_summary_with_quantiles),
        ("invalid_metric_name", test_invalid_metric_name),
        ("invalid_label_name", test_invalid_label_name),
        ("valid_metric_with_labels", test_valid_metric_with_labels),

        # LabelSet tests
        ("label_set_hash", test_label_set_hash),
        ("label_set_equality", test_label_set_equality),
        ("empty_label_set", test_empty_label_set),

        # Counter tests
        ("counter_increment", test_counter_increment),
        ("counter_increment_with_value", test_counter_increment_with_value),
        ("counter_increment_with_labels", test_counter_increment_with_labels),
        ("counter_negative_increment_raises", test_counter_negative_increment_raises),
        ("counter_get_all", test_counter_get_all),
        ("counter_thread_safety", test_counter_thread_safety),

        # Gauge tests
        ("gauge_set", test_gauge_set),
        ("gauge_increment", test_gauge_increment),
        ("gauge_decrement", test_gauge_decrement),
        ("gauge_set_to_current_time", test_gauge_set_to_current_time),
        ("gauge_with_labels", test_gauge_with_labels),

        # Histogram tests
        ("histogram_observe", test_histogram_observe),
        ("histogram_bucket_counts", test_histogram_bucket_counts),
        ("histogram_timer", test_histogram_timer),

        # Summary tests
        ("summary_observe", test_summary_observe),
        ("summary_quantiles", test_summary_quantiles),

        # Registry tests
        ("registry_create_counter", test_registry_create_counter),
        ("registry_create_gauge", test_registry_create_gauge),
        ("registry_create_histogram", test_registry_create_histogram),
        ("registry_create_summary", test_registry_create_summary),
        ("registry_get_metric", test_registry_get_metric),
        ("registry_get_all_metrics", test_registry_get_all_metrics),
        ("registry_export_counter", test_registry_export_counter),
        ("registry_export_gauge", test_registry_export_gauge),
        ("registry_export_histogram", test_registry_export_histogram),

        # KGMetricsService tests
        ("metrics_service_request_metrics_exist", test_metrics_service_request_metrics_exist),
        ("metrics_service_neo4j_metrics_exist", test_metrics_service_neo4j_metrics_exist),
        ("metrics_service_reasoning_metrics_exist", test_metrics_service_reasoning_metrics_exist),
        ("metrics_service_cache_metrics_exist", test_metrics_service_cache_metrics_exist),
        ("metrics_service_umls_metrics_exist", test_metrics_service_umls_metrics_exist),
        ("metrics_service_embedding_metrics_exist", test_metrics_service_embedding_metrics_exist),
        ("metrics_service_mdt_metrics_exist", test_metrics_service_mdt_metrics_exist),
        ("metrics_service_batch_metrics_exist", test_metrics_service_batch_metrics_exist),
        ("metrics_service_circuit_breaker_metrics_exist", test_metrics_service_circuit_breaker_metrics_exist),
        ("metrics_service_webhook_metrics_exist", test_metrics_service_webhook_metrics_exist),
        ("metrics_service_data_export_metrics_exist", test_metrics_service_data_export_metrics_exist),
        ("metrics_service_benchmark_metrics_exist", test_metrics_service_benchmark_metrics_exist),
        ("metrics_service_system_metrics_exist", test_metrics_service_system_metrics_exist),
        ("metrics_service_record_request", test_metrics_service_record_request),
        ("metrics_service_record_neo4j_query", test_metrics_service_record_neo4j_query),
        ("metrics_service_record_reasoning_query", test_metrics_service_record_reasoning_query),
        ("metrics_service_record_cache_hit", test_metrics_service_record_cache_hit),
        ("metrics_service_record_cache_miss", test_metrics_service_record_cache_miss),
        ("metrics_service_update_cache_stats", test_metrics_service_update_cache_stats),
        ("metrics_service_record_webhook_delivery", test_metrics_service_record_webhook_delivery),
        ("metrics_service_record_data_export", test_metrics_service_record_data_export),
        ("metrics_service_update_system_metrics", test_metrics_service_update_system_metrics),
        ("metrics_service_export", test_metrics_service_export),

        # Singleton tests
        ("singleton_returns_same_instance", test_singleton_returns_same_instance),

        # Decorator tests
        ("metrics_request_decorator", test_metrics_request_decorator),
        ("metrics_neo4j_decorator", test_metrics_neo4j_decorator),
        ("metrics_neo4j_decorator_failure", test_metrics_neo4j_decorator_failure),

        # Format tests
        ("format_labels_empty", test_format_labels_empty),
        ("format_labels_single", test_format_labels_single),
        ("format_labels_multiple", test_format_labels_multiple),
        ("histogram_bucket_cumulative", test_histogram_bucket_cumulative),
    ]

    passed = 0
    failed = 0

    for name, test in tests:
        if run_test(name, test):
            passed += 1
        else:
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
