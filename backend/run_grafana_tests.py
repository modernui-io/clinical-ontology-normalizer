#!/usr/bin/env python3
"""Standalone test runner for KG Grafana Dashboard Generator tests."""

import sys
import os
import importlib.util

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

# Now import and run tests
import traceback
import json
import tempfile

# Load the Grafana dashboard module directly
spec = importlib.util.spec_from_file_location(
    "app.services.kg_grafana_dashboards",
    "app/services/kg_grafana_dashboards.py",
    submodule_search_locations=[]
)
grafana_module = importlib.util.module_from_spec(spec)
grafana_module.__package__ = "app.services"
sys.modules["app.services.kg_grafana_dashboards"] = grafana_module
spec.loader.exec_module(grafana_module)

# Import the module under test
from app.services.kg_grafana_dashboards import (
    GrafanaDashboardGenerator,
    DashboardType,
    PanelType,
    GrafanaPanel,
    GrafanaRow,
    GrafanaVariable,
    GrafanaAlert,
    get_dashboard_generator,
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


# GrafanaPanel tests
def test_create_panel():
    panel = GrafanaPanel(
        title="Test Panel",
        type=PanelType.STAT,
        queries=[{"expr": "test_metric"}],
        grid_pos={"h": 4, "w": 6, "x": 0, "y": 0},
    )
    assert panel.title == "Test Panel"
    assert panel.type == PanelType.STAT


def test_panel_to_dict():
    panel = GrafanaPanel(
        title="Test Panel",
        type=PanelType.STAT,
        queries=[{"expr": "test_metric"}],
        grid_pos={"h": 4, "w": 6, "x": 0, "y": 0},
        description="Test description",
    )
    result = panel.to_dict()
    assert result["title"] == "Test Panel"
    assert result["type"] == "stat"
    assert result["description"] == "Test description"


def test_panel_with_thresholds():
    panel = GrafanaPanel(
        title="Test Panel",
        type=PanelType.GAUGE,
        queries=[{"expr": "test_metric"}],
        grid_pos={"h": 4, "w": 6, "x": 0, "y": 0},
        thresholds=[
            {"value": None, "color": "red"},
            {"value": 50, "color": "yellow"},
        ],
    )
    result = panel.to_dict()
    assert "fieldConfig" in result
    assert "thresholds" in result["fieldConfig"]["defaults"]


def test_panel_with_options():
    panel = GrafanaPanel(
        title="Test Panel",
        type=PanelType.STAT,
        queries=[{"expr": "test_metric"}],
        grid_pos={"h": 4, "w": 6, "x": 0, "y": 0},
        options={"colorMode": "background"},
    )
    result = panel.to_dict()
    assert result["options"]["colorMode"] == "background"


# GrafanaVariable tests
def test_create_variable():
    var = GrafanaVariable(
        name="instance",
        label="Instance",
        query="label_values(up, instance)",
    )
    assert var.name == "instance"
    assert var.label == "Instance"


def test_variable_to_dict():
    var = GrafanaVariable(
        name="instance",
        label="Instance",
        query="label_values(up, instance)",
        multi=True,
        include_all=True,
    )
    result = var.to_dict()
    assert result["name"] == "instance"
    assert result["multi"] is True
    assert result["includeAll"] is True


# GrafanaAlert tests
def test_create_alert():
    alert = GrafanaAlert(
        name="High CPU",
        condition="cpu_usage > 90",
        threshold=90,
        for_duration="5m",
        severity="critical",
    )
    assert alert.name == "High CPU"
    assert alert.threshold == 90


def test_alert_to_dict():
    alert = GrafanaAlert(
        name="High CPU",
        condition="cpu_usage > 90",
        threshold=90,
        for_duration="5m",
        severity="critical",
        message="CPU usage is too high",
    )
    result = alert.to_dict()
    assert result["name"] == "High CPU"
    assert result["labels"]["severity"] == "critical"


# GrafanaDashboardGenerator tests
def test_create_generator():
    gen = GrafanaDashboardGenerator()
    assert gen.datasource_uid == "${DS_PROMETHEUS}"
    assert gen.metrics_prefix == "kg_"


def test_create_generator_custom_prefix():
    gen = GrafanaDashboardGenerator(metrics_prefix="custom_")
    assert gen.metrics_prefix == "custom_"


def test_generate_overview_dashboard():
    gen = GrafanaDashboardGenerator()
    dashboard = gen.generate_overview_dashboard()
    assert "uid" in dashboard
    assert dashboard["title"] == "Knowledge Graph - Overview"
    assert "panels" in dashboard
    assert len(dashboard["panels"]) > 0


def test_generate_health_dashboard():
    gen = GrafanaDashboardGenerator()
    dashboard = gen.generate_health_dashboard()
    assert dashboard["title"] == "Knowledge Graph - Health"
    assert "panels" in dashboard


def test_generate_performance_dashboard():
    gen = GrafanaDashboardGenerator()
    dashboard = gen.generate_performance_dashboard()
    assert dashboard["title"] == "Knowledge Graph - Performance"


def test_generate_cache_dashboard():
    gen = GrafanaDashboardGenerator()
    dashboard = gen.generate_cache_dashboard()
    assert dashboard["title"] == "Knowledge Graph - Cache"


def test_generate_benchmark_dashboard():
    gen = GrafanaDashboardGenerator()
    dashboard = gen.generate_benchmark_dashboard()
    assert dashboard["title"] == "Knowledge Graph - Benchmarks"


def test_generate_query_dashboard():
    gen = GrafanaDashboardGenerator()
    dashboard = gen.generate_query_dashboard()
    assert dashboard["title"] == "Knowledge Graph - Query Analysis"


def test_dashboard_has_variables():
    gen = GrafanaDashboardGenerator()
    dashboard = gen.generate_overview_dashboard()
    assert "templating" in dashboard
    assert "list" in dashboard["templating"]


def test_dashboard_has_inputs():
    gen = GrafanaDashboardGenerator()
    dashboard = gen.generate_overview_dashboard()
    assert "__inputs" in dashboard
    assert dashboard["__inputs"][0]["name"] == "DS_PROMETHEUS"


def test_dashboard_has_refresh():
    gen = GrafanaDashboardGenerator()
    dashboard = gen.generate_overview_dashboard()
    assert "refresh" in dashboard


def test_dashboard_has_time_range():
    gen = GrafanaDashboardGenerator()
    dashboard = gen.generate_overview_dashboard()
    assert "time" in dashboard
    assert "from" in dashboard["time"]


def test_generate_all_dashboards():
    gen = GrafanaDashboardGenerator()
    dashboards = gen.generate_all_dashboards()
    assert "overview" in dashboards
    assert "health" in dashboards
    assert "performance" in dashboards
    assert "cache" in dashboards
    assert "benchmark" in dashboards
    assert "query" in dashboards


def test_export_dashboard_overview():
    gen = GrafanaDashboardGenerator()
    json_str = gen.export_dashboard(DashboardType.OVERVIEW)
    parsed = json.loads(json_str)
    assert parsed["title"] == "Knowledge Graph - Overview"


def test_export_dashboard_health():
    gen = GrafanaDashboardGenerator()
    json_str = gen.export_dashboard(DashboardType.HEALTH)
    parsed = json.loads(json_str)
    assert parsed["title"] == "Knowledge Graph - Health"


def test_export_dashboard_performance():
    gen = GrafanaDashboardGenerator()
    json_str = gen.export_dashboard(DashboardType.PERFORMANCE)
    parsed = json.loads(json_str)
    assert parsed["title"] == "Knowledge Graph - Performance"


def test_export_dashboard_cache():
    gen = GrafanaDashboardGenerator()
    json_str = gen.export_dashboard(DashboardType.CACHE)
    parsed = json.loads(json_str)
    assert parsed["title"] == "Knowledge Graph - Cache"


def test_export_dashboard_benchmark():
    gen = GrafanaDashboardGenerator()
    json_str = gen.export_dashboard(DashboardType.BENCHMARK)
    parsed = json.loads(json_str)
    assert parsed["title"] == "Knowledge Graph - Benchmarks"


def test_export_dashboard_query():
    gen = GrafanaDashboardGenerator()
    json_str = gen.export_dashboard(DashboardType.QUERY)
    parsed = json.loads(json_str)
    assert parsed["title"] == "Knowledge Graph - Query Analysis"


def test_export_dashboard_to_file():
    gen = GrafanaDashboardGenerator()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        filename = f.name
    try:
        gen.export_dashboard(DashboardType.OVERVIEW, filename)
        with open(filename) as f:
            parsed = json.load(f)
            assert parsed["title"] == "Knowledge Graph - Overview"
    finally:
        os.unlink(filename)


def test_export_dashboard_invalid_type():
    gen = GrafanaDashboardGenerator()
    try:
        gen.export_dashboard("invalid_type")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Unknown dashboard type" in str(e)


def test_generate_alert_rules():
    gen = GrafanaDashboardGenerator()
    alerts = gen.generate_alert_rules()
    assert len(alerts) > 0
    alert_names = [a["name"] for a in alerts]
    assert "KG Service Down" in alert_names
    assert "High Error Rate" in alert_names


def test_alert_has_required_fields():
    gen = GrafanaDashboardGenerator()
    alerts = gen.generate_alert_rules()
    for alert in alerts:
        assert "name" in alert
        assert "condition" in alert
        assert "threshold" in alert
        assert "for" in alert
        assert "labels" in alert


def test_overview_panels_have_queries():
    gen = GrafanaDashboardGenerator()
    dashboard = gen.generate_overview_dashboard()
    for panel in dashboard["panels"]:
        assert "targets" in panel
        assert len(panel["targets"]) > 0


def test_metrics_prefix_in_queries():
    gen = GrafanaDashboardGenerator()
    dashboard = gen.generate_overview_dashboard()
    for panel in dashboard["panels"]:
        for target in panel.get("targets", []):
            if "expr" in target:
                assert "kg_" in target["expr"]


def test_custom_metrics_prefix_in_queries():
    gen = GrafanaDashboardGenerator(metrics_prefix="myapp_")
    dashboard = gen.generate_overview_dashboard()
    for panel in dashboard["panels"]:
        for target in panel.get("targets", []):
            if "expr" in target:
                assert "myapp_" in target["expr"]


# Panel type tests
def test_stat_panel_type():
    assert PanelType.STAT.value == "stat"


def test_gauge_panel_type():
    assert PanelType.GAUGE.value == "gauge"


def test_graph_panel_type():
    assert PanelType.GRAPH.value == "graph"


def test_table_panel_type():
    assert PanelType.TABLE.value == "table"


def test_heatmap_panel_type():
    assert PanelType.HEATMAP.value == "heatmap"


def test_timeseries_panel_type():
    assert PanelType.TIMESERIES.value == "timeseries"


# Dashboard type tests
def test_health_dashboard_type():
    assert DashboardType.HEALTH.value == "health"


def test_performance_dashboard_type():
    assert DashboardType.PERFORMANCE.value == "performance"


def test_benchmark_dashboard_type():
    assert DashboardType.BENCHMARK.value == "benchmark"


def test_cache_dashboard_type():
    assert DashboardType.CACHE.value == "cache"


def test_query_dashboard_type():
    assert DashboardType.QUERY.value == "query"


def test_overview_dashboard_type():
    assert DashboardType.OVERVIEW.value == "overview"


# Singleton test
def test_singleton():
    gen1 = get_dashboard_generator()
    gen2 = get_dashboard_generator()
    assert gen1 is gen2


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("KG Grafana Dashboard Generator Tests")
    print("=" * 60 + "\n")

    tests = [
        # Panel tests
        ("create_panel", test_create_panel),
        ("panel_to_dict", test_panel_to_dict),
        ("panel_with_thresholds", test_panel_with_thresholds),
        ("panel_with_options", test_panel_with_options),

        # Variable tests
        ("create_variable", test_create_variable),
        ("variable_to_dict", test_variable_to_dict),

        # Alert tests
        ("create_alert", test_create_alert),
        ("alert_to_dict", test_alert_to_dict),

        # Generator tests
        ("create_generator", test_create_generator),
        ("create_generator_custom_prefix", test_create_generator_custom_prefix),
        ("generate_overview_dashboard", test_generate_overview_dashboard),
        ("generate_health_dashboard", test_generate_health_dashboard),
        ("generate_performance_dashboard", test_generate_performance_dashboard),
        ("generate_cache_dashboard", test_generate_cache_dashboard),
        ("generate_benchmark_dashboard", test_generate_benchmark_dashboard),
        ("generate_query_dashboard", test_generate_query_dashboard),
        ("dashboard_has_variables", test_dashboard_has_variables),
        ("dashboard_has_inputs", test_dashboard_has_inputs),
        ("dashboard_has_refresh", test_dashboard_has_refresh),
        ("dashboard_has_time_range", test_dashboard_has_time_range),
        ("generate_all_dashboards", test_generate_all_dashboards),

        # Export tests
        ("export_dashboard_overview", test_export_dashboard_overview),
        ("export_dashboard_health", test_export_dashboard_health),
        ("export_dashboard_performance", test_export_dashboard_performance),
        ("export_dashboard_cache", test_export_dashboard_cache),
        ("export_dashboard_benchmark", test_export_dashboard_benchmark),
        ("export_dashboard_query", test_export_dashboard_query),
        ("export_dashboard_to_file", test_export_dashboard_to_file),
        ("export_dashboard_invalid_type", test_export_dashboard_invalid_type),

        # Alert tests
        ("generate_alert_rules", test_generate_alert_rules),
        ("alert_has_required_fields", test_alert_has_required_fields),

        # Query tests
        ("overview_panels_have_queries", test_overview_panels_have_queries),
        ("metrics_prefix_in_queries", test_metrics_prefix_in_queries),
        ("custom_metrics_prefix_in_queries", test_custom_metrics_prefix_in_queries),

        # Panel type tests
        ("stat_panel_type", test_stat_panel_type),
        ("gauge_panel_type", test_gauge_panel_type),
        ("graph_panel_type", test_graph_panel_type),
        ("table_panel_type", test_table_panel_type),
        ("heatmap_panel_type", test_heatmap_panel_type),
        ("timeseries_panel_type", test_timeseries_panel_type),

        # Dashboard type tests
        ("health_dashboard_type", test_health_dashboard_type),
        ("performance_dashboard_type", test_performance_dashboard_type),
        ("benchmark_dashboard_type", test_benchmark_dashboard_type),
        ("cache_dashboard_type", test_cache_dashboard_type),
        ("query_dashboard_type", test_query_dashboard_type),
        ("overview_dashboard_type", test_overview_dashboard_type),

        # Singleton test
        ("singleton", test_singleton),
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
