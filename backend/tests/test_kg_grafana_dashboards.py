"""Tests for KG Grafana Dashboard Generator."""

import pytest
import json
import tempfile
import os

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


class TestGrafanaPanel:
    """Tests for GrafanaPanel."""

    def test_create_panel(self):
        """Create a basic panel."""
        panel = GrafanaPanel(
            title="Test Panel",
            type=PanelType.STAT,
            queries=[{"expr": "test_metric"}],
            grid_pos={"h": 4, "w": 6, "x": 0, "y": 0},
        )

        assert panel.title == "Test Panel"
        assert panel.type == PanelType.STAT

    def test_panel_to_dict(self):
        """Convert panel to dictionary."""
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
        assert result["gridPos"] == {"h": 4, "w": 6, "x": 0, "y": 0}
        assert result["description"] == "Test description"
        assert "targets" in result

    def test_panel_with_thresholds(self):
        """Panel with threshold configuration."""
        panel = GrafanaPanel(
            title="Test Panel",
            type=PanelType.GAUGE,
            queries=[{"expr": "test_metric"}],
            grid_pos={"h": 4, "w": 6, "x": 0, "y": 0},
            thresholds=[
                {"value": None, "color": "red"},
                {"value": 50, "color": "yellow"},
                {"value": 80, "color": "green"},
            ],
        )

        result = panel.to_dict()

        assert "fieldConfig" in result
        assert "thresholds" in result["fieldConfig"]["defaults"]

    def test_panel_with_options(self):
        """Panel with custom options."""
        panel = GrafanaPanel(
            title="Test Panel",
            type=PanelType.STAT,
            queries=[{"expr": "test_metric"}],
            grid_pos={"h": 4, "w": 6, "x": 0, "y": 0},
            options={"colorMode": "background"},
        )

        result = panel.to_dict()

        assert result["options"]["colorMode"] == "background"


class TestGrafanaVariable:
    """Tests for GrafanaVariable."""

    def test_create_variable(self):
        """Create a variable."""
        var = GrafanaVariable(
            name="instance",
            label="Instance",
            query="label_values(up, instance)",
        )

        assert var.name == "instance"
        assert var.label == "Instance"

    def test_variable_to_dict(self):
        """Convert variable to dictionary."""
        var = GrafanaVariable(
            name="instance",
            label="Instance",
            query="label_values(up, instance)",
            multi=True,
            include_all=True,
        )

        result = var.to_dict()

        assert result["name"] == "instance"
        assert result["label"] == "Instance"
        assert result["query"] == "label_values(up, instance)"
        assert result["multi"] is True
        assert result["includeAll"] is True


class TestGrafanaAlert:
    """Tests for GrafanaAlert."""

    def test_create_alert(self):
        """Create an alert rule."""
        alert = GrafanaAlert(
            name="High CPU",
            condition="cpu_usage > 90",
            threshold=90,
            for_duration="5m",
            severity="critical",
        )

        assert alert.name == "High CPU"
        assert alert.threshold == 90

    def test_alert_to_dict(self):
        """Convert alert to dictionary."""
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
        assert result["condition"] == "cpu_usage > 90"
        assert result["threshold"] == 90
        assert result["for"] == "5m"
        assert result["labels"]["severity"] == "critical"
        assert result["annotations"]["message"] == "CPU usage is too high"


class TestGrafanaDashboardGenerator:
    """Tests for GrafanaDashboardGenerator."""

    @pytest.fixture
    def generator(self):
        return GrafanaDashboardGenerator()

    def test_create_generator(self, generator):
        """Create a dashboard generator."""
        assert generator.datasource_uid == "${DS_PROMETHEUS}"
        assert generator.metrics_prefix == "kg_"

    def test_create_generator_custom_prefix(self):
        """Create generator with custom prefix."""
        gen = GrafanaDashboardGenerator(metrics_prefix="custom_")
        assert gen.metrics_prefix == "custom_"

    def test_generate_overview_dashboard(self, generator):
        """Generate overview dashboard."""
        dashboard = generator.generate_overview_dashboard()

        assert "uid" in dashboard
        assert dashboard["title"] == "Knowledge Graph - Overview"
        assert "knowledge-graph" in dashboard["tags"]
        assert "panels" in dashboard
        assert len(dashboard["panels"]) > 0

    def test_generate_health_dashboard(self, generator):
        """Generate health dashboard."""
        dashboard = generator.generate_health_dashboard()

        assert dashboard["title"] == "Knowledge Graph - Health"
        assert "panels" in dashboard
        assert len(dashboard["panels"]) > 0

    def test_generate_performance_dashboard(self, generator):
        """Generate performance dashboard."""
        dashboard = generator.generate_performance_dashboard()

        assert dashboard["title"] == "Knowledge Graph - Performance"
        assert "panels" in dashboard

    def test_generate_cache_dashboard(self, generator):
        """Generate cache dashboard."""
        dashboard = generator.generate_cache_dashboard()

        assert dashboard["title"] == "Knowledge Graph - Cache"
        assert "panels" in dashboard

    def test_generate_benchmark_dashboard(self, generator):
        """Generate benchmark dashboard."""
        dashboard = generator.generate_benchmark_dashboard()

        assert dashboard["title"] == "Knowledge Graph - Benchmarks"
        assert "panels" in dashboard

    def test_generate_query_dashboard(self, generator):
        """Generate query dashboard."""
        dashboard = generator.generate_query_dashboard()

        assert dashboard["title"] == "Knowledge Graph - Query Analysis"
        assert "panels" in dashboard

    def test_dashboard_has_variables(self, generator):
        """Dashboard includes variables."""
        dashboard = generator.generate_overview_dashboard()

        assert "templating" in dashboard
        assert "list" in dashboard["templating"]
        assert len(dashboard["templating"]["list"]) > 0

    def test_dashboard_has_inputs(self, generator):
        """Dashboard includes input definitions."""
        dashboard = generator.generate_overview_dashboard()

        assert "__inputs" in dashboard
        assert len(dashboard["__inputs"]) > 0
        assert dashboard["__inputs"][0]["name"] == "DS_PROMETHEUS"

    def test_dashboard_has_refresh(self, generator):
        """Dashboard has refresh setting."""
        dashboard = generator.generate_overview_dashboard()

        assert "refresh" in dashboard

    def test_dashboard_has_time_range(self, generator):
        """Dashboard has time range."""
        dashboard = generator.generate_overview_dashboard()

        assert "time" in dashboard
        assert "from" in dashboard["time"]
        assert "to" in dashboard["time"]

    def test_generate_all_dashboards(self, generator):
        """Generate all dashboards."""
        dashboards = generator.generate_all_dashboards()

        assert "overview" in dashboards
        assert "health" in dashboards
        assert "performance" in dashboards
        assert "cache" in dashboards
        assert "benchmark" in dashboards
        assert "query" in dashboards

    def test_export_dashboard_overview(self, generator):
        """Export overview dashboard to JSON."""
        json_str = generator.export_dashboard(DashboardType.OVERVIEW)

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["title"] == "Knowledge Graph - Overview"

    def test_export_dashboard_health(self, generator):
        """Export health dashboard to JSON."""
        json_str = generator.export_dashboard(DashboardType.HEALTH)
        parsed = json.loads(json_str)
        assert parsed["title"] == "Knowledge Graph - Health"

    def test_export_dashboard_performance(self, generator):
        """Export performance dashboard to JSON."""
        json_str = generator.export_dashboard(DashboardType.PERFORMANCE)
        parsed = json.loads(json_str)
        assert parsed["title"] == "Knowledge Graph - Performance"

    def test_export_dashboard_cache(self, generator):
        """Export cache dashboard to JSON."""
        json_str = generator.export_dashboard(DashboardType.CACHE)
        parsed = json.loads(json_str)
        assert parsed["title"] == "Knowledge Graph - Cache"

    def test_export_dashboard_benchmark(self, generator):
        """Export benchmark dashboard to JSON."""
        json_str = generator.export_dashboard(DashboardType.BENCHMARK)
        parsed = json.loads(json_str)
        assert parsed["title"] == "Knowledge Graph - Benchmarks"

    def test_export_dashboard_query(self, generator):
        """Export query dashboard to JSON."""
        json_str = generator.export_dashboard(DashboardType.QUERY)
        parsed = json.loads(json_str)
        assert parsed["title"] == "Knowledge Graph - Query Analysis"

    def test_export_dashboard_to_file(self, generator):
        """Export dashboard to file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            filename = f.name

        try:
            generator.export_dashboard(DashboardType.OVERVIEW, filename)

            # File should exist and contain valid JSON
            assert os.path.exists(filename)
            with open(filename) as f:
                parsed = json.load(f)
                assert parsed["title"] == "Knowledge Graph - Overview"
        finally:
            os.unlink(filename)

    def test_export_dashboard_invalid_type(self, generator):
        """Export with invalid dashboard type raises error."""
        with pytest.raises(ValueError) as exc:
            generator.export_dashboard("invalid_type")
        assert "Unknown dashboard type" in str(exc.value)

    def test_generate_alert_rules(self, generator):
        """Generate alert rules."""
        alerts = generator.generate_alert_rules()

        assert len(alerts) > 0

        # Check specific alerts
        alert_names = [a["name"] for a in alerts]
        assert "KG Service Down" in alert_names
        assert "High Error Rate" in alert_names
        assert "High Latency" in alert_names
        assert "Low Cache Hit Rate" in alert_names
        assert "Circuit Breaker Open" in alert_names

    def test_alert_has_required_fields(self, generator):
        """Alert rules have required fields."""
        alerts = generator.generate_alert_rules()

        for alert in alerts:
            assert "name" in alert
            assert "condition" in alert
            assert "threshold" in alert
            assert "for" in alert
            assert "labels" in alert
            assert "severity" in alert["labels"]

    def test_overview_panels_have_queries(self, generator):
        """Overview panels have queries."""
        dashboard = generator.generate_overview_dashboard()

        for panel in dashboard["panels"]:
            assert "targets" in panel
            assert len(panel["targets"]) > 0

    def test_health_panels_have_queries(self, generator):
        """Health panels have queries."""
        dashboard = generator.generate_health_dashboard()

        for panel in dashboard["panels"]:
            assert "targets" in panel

    def test_metrics_prefix_in_queries(self, generator):
        """Metrics prefix is used in queries."""
        dashboard = generator.generate_overview_dashboard()

        for panel in dashboard["panels"]:
            for target in panel.get("targets", []):
                if "expr" in target:
                    assert "kg_" in target["expr"]

    def test_custom_metrics_prefix_in_queries(self):
        """Custom metrics prefix is used in queries."""
        gen = GrafanaDashboardGenerator(metrics_prefix="myapp_")
        dashboard = gen.generate_overview_dashboard()

        for panel in dashboard["panels"]:
            for target in panel.get("targets", []):
                if "expr" in target:
                    assert "myapp_" in target["expr"]


class TestPanelTypes:
    """Tests for panel type coverage."""

    def test_stat_panel_type(self):
        """STAT panel type value."""
        assert PanelType.STAT.value == "stat"

    def test_gauge_panel_type(self):
        """GAUGE panel type value."""
        assert PanelType.GAUGE.value == "gauge"

    def test_graph_panel_type(self):
        """GRAPH panel type value."""
        assert PanelType.GRAPH.value == "graph"

    def test_table_panel_type(self):
        """TABLE panel type value."""
        assert PanelType.TABLE.value == "table"

    def test_heatmap_panel_type(self):
        """HEATMAP panel type value."""
        assert PanelType.HEATMAP.value == "heatmap"

    def test_timeseries_panel_type(self):
        """TIMESERIES panel type value."""
        assert PanelType.TIMESERIES.value == "timeseries"


class TestDashboardTypes:
    """Tests for dashboard type coverage."""

    def test_health_dashboard_type(self):
        """HEALTH dashboard type value."""
        assert DashboardType.HEALTH.value == "health"

    def test_performance_dashboard_type(self):
        """PERFORMANCE dashboard type value."""
        assert DashboardType.PERFORMANCE.value == "performance"

    def test_benchmark_dashboard_type(self):
        """BENCHMARK dashboard type value."""
        assert DashboardType.BENCHMARK.value == "benchmark"

    def test_cache_dashboard_type(self):
        """CACHE dashboard type value."""
        assert DashboardType.CACHE.value == "cache"

    def test_query_dashboard_type(self):
        """QUERY dashboard type value."""
        assert DashboardType.QUERY.value == "query"

    def test_overview_dashboard_type(self):
        """OVERVIEW dashboard type value."""
        assert DashboardType.OVERVIEW.value == "overview"


class TestSingletonInstance:
    """Tests for singleton pattern."""

    def test_get_dashboard_generator_returns_same_instance(self):
        """Singleton returns same instance."""
        gen1 = get_dashboard_generator()
        gen2 = get_dashboard_generator()
        assert gen1 is gen2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
