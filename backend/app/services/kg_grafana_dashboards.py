"""
Knowledge Graph Grafana Dashboard Generator.

Generates Grafana dashboard JSON configurations for monitoring KG services:
- Health monitoring dashboard
- Performance metrics dashboard
- Benchmark results dashboard
- Cache statistics dashboard
- Query analysis dashboard

Features:
- Pre-configured panels and queries
- Prometheus datasource integration
- Alert rule templates
- Variable templates for filtering
"""
# MODULE: graph_support
# MATURITY: pilot

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
import uuid


class DashboardType(str, Enum):
    """Types of dashboards."""

    HEALTH = "health"
    PERFORMANCE = "performance"
    BENCHMARK = "benchmark"
    CACHE = "cache"
    QUERY = "query"
    OVERVIEW = "overview"


class PanelType(str, Enum):
    """Types of Grafana panels."""

    STAT = "stat"
    GAUGE = "gauge"
    GRAPH = "graph"
    TABLE = "table"
    HEATMAP = "heatmap"
    TEXT = "text"
    LOGS = "logs"
    PIE = "piechart"
    BAR = "barchart"
    TIMESERIES = "timeseries"


@dataclass
class GrafanaPanel:
    """A Grafana dashboard panel."""

    title: str
    type: PanelType
    queries: list[dict[str, Any]]
    grid_pos: dict[str, int]
    description: str = ""
    thresholds: list[dict[str, Any]] = field(default_factory=list)
    options: dict[str, Any] = field(default_factory=dict)
    field_config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to Grafana panel JSON."""
        panel = {
            "id": hash(self.title) % 10000,
            "title": self.title,
            "type": self.type.value,
            "gridPos": self.grid_pos,
            "datasource": {"type": "prometheus", "uid": "${DS_PROMETHEUS}"},
            "targets": self.queries,
        }

        if self.description:
            panel["description"] = self.description

        if self.thresholds:
            panel["fieldConfig"] = {
                "defaults": {
                    "thresholds": {
                        "mode": "absolute",
                        "steps": self.thresholds,
                    }
                }
            }

        if self.options:
            panel["options"] = self.options

        if self.field_config:
            panel["fieldConfig"] = self.field_config

        return panel


@dataclass
class GrafanaRow:
    """A Grafana dashboard row."""

    title: str
    collapsed: bool = False
    panels: list[GrafanaPanel] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to Grafana row JSON."""
        return {
            "type": "row",
            "title": self.title,
            "collapsed": self.collapsed,
            "panels": [p.to_dict() for p in self.panels],
        }


@dataclass
class GrafanaVariable:
    """A Grafana dashboard variable."""

    name: str
    label: str
    query: str
    type: str = "query"
    multi: bool = False
    include_all: bool = True
    refresh: int = 1

    def to_dict(self) -> dict[str, Any]:
        """Convert to Grafana variable JSON."""
        return {
            "name": self.name,
            "label": self.label,
            "type": self.type,
            "query": self.query,
            "multi": self.multi,
            "includeAll": self.include_all,
            "refresh": self.refresh,
            "datasource": {"type": "prometheus", "uid": "${DS_PROMETHEUS}"},
        }


@dataclass
class GrafanaAlert:
    """A Grafana alert rule."""

    name: str
    condition: str
    threshold: float
    for_duration: str = "5m"
    severity: str = "warning"
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to Grafana alert JSON."""
        return {
            "name": self.name,
            "condition": self.condition,
            "threshold": self.threshold,
            "for": self.for_duration,
            "labels": {"severity": self.severity},
            "annotations": {"message": self.message or self.name},
        }


class GrafanaDashboardGenerator:
    """
    Generator for Grafana dashboard configurations.

    Creates JSON dashboard definitions that can be imported into Grafana
    for monitoring knowledge graph services.
    """

    def __init__(
        self,
        datasource_uid: str = "${DS_PROMETHEUS}",
        metrics_prefix: str = "kg_",
    ):
        """
        Initialize the dashboard generator.

        Args:
            datasource_uid: Grafana datasource UID
            metrics_prefix: Prefix for all metrics
        """
        self.datasource_uid = datasource_uid
        self.metrics_prefix = metrics_prefix

    def generate_overview_dashboard(self) -> dict[str, Any]:
        """Generate overview dashboard with key metrics."""
        return {
            "uid": f"kg-overview-{uuid.uuid4().hex[:8]}",
            "title": "Knowledge Graph - Overview",
            "description": "High-level overview of Knowledge Graph service health and performance",
            "tags": ["knowledge-graph", "overview"],
            "timezone": "browser",
            "refresh": "30s",
            "time": {"from": "now-1h", "to": "now"},
            "templating": {
                "list": [
                    GrafanaVariable(
                        name="instance",
                        label="Instance",
                        query=f'label_values({self.metrics_prefix}health_status, instance)',
                    ).to_dict(),
                ]
            },
            "panels": self._get_overview_panels(),
            "__inputs": [
                {
                    "name": "DS_PROMETHEUS",
                    "label": "Prometheus",
                    "type": "datasource",
                    "pluginId": "prometheus",
                }
            ],
        }

    def generate_health_dashboard(self) -> dict[str, Any]:
        """Generate health monitoring dashboard."""
        return {
            "uid": f"kg-health-{uuid.uuid4().hex[:8]}",
            "title": "Knowledge Graph - Health",
            "description": "Component health monitoring for Knowledge Graph services",
            "tags": ["knowledge-graph", "health"],
            "timezone": "browser",
            "refresh": "10s",
            "time": {"from": "now-30m", "to": "now"},
            "templating": {
                "list": [
                    GrafanaVariable(
                        name="component",
                        label="Component",
                        query=f'label_values({self.metrics_prefix}component_health, component)',
                        multi=True,
                    ).to_dict(),
                ]
            },
            "panels": self._get_health_panels(),
            "__inputs": [
                {
                    "name": "DS_PROMETHEUS",
                    "label": "Prometheus",
                    "type": "datasource",
                    "pluginId": "prometheus",
                }
            ],
        }

    def generate_performance_dashboard(self) -> dict[str, Any]:
        """Generate performance metrics dashboard."""
        return {
            "uid": f"kg-performance-{uuid.uuid4().hex[:8]}",
            "title": "Knowledge Graph - Performance",
            "description": "Performance metrics for Knowledge Graph operations",
            "tags": ["knowledge-graph", "performance"],
            "timezone": "browser",
            "refresh": "30s",
            "time": {"from": "now-1h", "to": "now"},
            "templating": {
                "list": [
                    GrafanaVariable(
                        name="operation",
                        label="Operation",
                        query=f'label_values({self.metrics_prefix}operation_duration_seconds, operation)',
                        multi=True,
                    ).to_dict(),
                ]
            },
            "panels": self._get_performance_panels(),
            "__inputs": [
                {
                    "name": "DS_PROMETHEUS",
                    "label": "Prometheus",
                    "type": "datasource",
                    "pluginId": "prometheus",
                }
            ],
        }

    def generate_cache_dashboard(self) -> dict[str, Any]:
        """Generate cache statistics dashboard."""
        return {
            "uid": f"kg-cache-{uuid.uuid4().hex[:8]}",
            "title": "Knowledge Graph - Cache",
            "description": "Cache performance and statistics for Knowledge Graph",
            "tags": ["knowledge-graph", "cache"],
            "timezone": "browser",
            "refresh": "30s",
            "time": {"from": "now-1h", "to": "now"},
            "templating": {
                "list": [
                    GrafanaVariable(
                        name="cache_type",
                        label="Cache Type",
                        query=f'label_values({self.metrics_prefix}cache_hits_total, cache_type)',
                        multi=True,
                    ).to_dict(),
                ]
            },
            "panels": self._get_cache_panels(),
            "__inputs": [
                {
                    "name": "DS_PROMETHEUS",
                    "label": "Prometheus",
                    "type": "datasource",
                    "pluginId": "prometheus",
                }
            ],
        }

    def generate_benchmark_dashboard(self) -> dict[str, Any]:
        """Generate benchmark results dashboard."""
        return {
            "uid": f"kg-benchmark-{uuid.uuid4().hex[:8]}",
            "title": "Knowledge Graph - Benchmarks",
            "description": "Benchmark results and accuracy metrics",
            "tags": ["knowledge-graph", "benchmark"],
            "timezone": "browser",
            "refresh": "5m",
            "time": {"from": "now-24h", "to": "now"},
            "templating": {
                "list": [
                    GrafanaVariable(
                        name="benchmark_suite",
                        label="Suite",
                        query=f'label_values({self.metrics_prefix}benchmark_score, suite)',
                        multi=True,
                    ).to_dict(),
                ]
            },
            "panels": self._get_benchmark_panels(),
            "__inputs": [
                {
                    "name": "DS_PROMETHEUS",
                    "label": "Prometheus",
                    "type": "datasource",
                    "pluginId": "prometheus",
                }
            ],
        }

    def generate_query_dashboard(self) -> dict[str, Any]:
        """Generate query analysis dashboard."""
        return {
            "uid": f"kg-query-{uuid.uuid4().hex[:8]}",
            "title": "Knowledge Graph - Query Analysis",
            "description": "Query performance and patterns analysis",
            "tags": ["knowledge-graph", "query"],
            "timezone": "browser",
            "refresh": "30s",
            "time": {"from": "now-1h", "to": "now"},
            "templating": {
                "list": [
                    GrafanaVariable(
                        name="query_type",
                        label="Query Type",
                        query=f'label_values({self.metrics_prefix}query_duration_seconds, query_type)',
                        multi=True,
                    ).to_dict(),
                ]
            },
            "panels": self._get_query_panels(),
            "__inputs": [
                {
                    "name": "DS_PROMETHEUS",
                    "label": "Prometheus",
                    "type": "datasource",
                    "pluginId": "prometheus",
                }
            ],
        }

    def _get_overview_panels(self) -> list[dict[str, Any]]:
        """Get overview dashboard panels."""
        return [
            # Row 1: Status indicators
            GrafanaPanel(
                title="Service Status",
                type=PanelType.STAT,
                queries=[{
                    "expr": f'{self.metrics_prefix}health_status{{instance=~"$instance"}}',
                    "legendFormat": "{{instance}}",
                }],
                grid_pos={"h": 4, "w": 6, "x": 0, "y": 0},
                thresholds=[
                    {"value": None, "color": "red"},
                    {"value": 1, "color": "green"},
                ],
                options={"colorMode": "background", "graphMode": "none"},
            ).to_dict(),
            GrafanaPanel(
                title="Active Connections",
                type=PanelType.STAT,
                queries=[{
                    "expr": f'{self.metrics_prefix}active_connections',
                    "legendFormat": "Connections",
                }],
                grid_pos={"h": 4, "w": 6, "x": 6, "y": 0},
                options={"colorMode": "value"},
            ).to_dict(),
            GrafanaPanel(
                title="Total Concepts",
                type=PanelType.STAT,
                queries=[{
                    "expr": f'{self.metrics_prefix}concepts_total',
                    "legendFormat": "Concepts",
                }],
                grid_pos={"h": 4, "w": 6, "x": 12, "y": 0},
                options={"colorMode": "value"},
            ).to_dict(),
            GrafanaPanel(
                title="Total Relationships",
                type=PanelType.STAT,
                queries=[{
                    "expr": f'{self.metrics_prefix}relationships_total',
                    "legendFormat": "Relationships",
                }],
                grid_pos={"h": 4, "w": 6, "x": 18, "y": 0},
                options={"colorMode": "value"},
            ).to_dict(),
            # Row 2: Request rates
            GrafanaPanel(
                title="Request Rate",
                type=PanelType.TIMESERIES,
                queries=[{
                    "expr": f'rate({self.metrics_prefix}requests_total[5m])',
                    "legendFormat": "{{endpoint}}",
                }],
                grid_pos={"h": 8, "w": 12, "x": 0, "y": 4},
            ).to_dict(),
            GrafanaPanel(
                title="Error Rate",
                type=PanelType.TIMESERIES,
                queries=[{
                    "expr": f'rate({self.metrics_prefix}errors_total[5m])',
                    "legendFormat": "{{error_type}}",
                }],
                grid_pos={"h": 8, "w": 12, "x": 12, "y": 4},
            ).to_dict(),
            # Row 3: Latency
            GrafanaPanel(
                title="Request Latency (p95)",
                type=PanelType.TIMESERIES,
                queries=[{
                    "expr": f'histogram_quantile(0.95, rate({self.metrics_prefix}request_duration_seconds_bucket[5m]))',
                    "legendFormat": "p95",
                }],
                grid_pos={"h": 8, "w": 24, "x": 0, "y": 12},
            ).to_dict(),
        ]

    def _get_health_panels(self) -> list[dict[str, Any]]:
        """Get health dashboard panels."""
        return [
            # Component health matrix
            GrafanaPanel(
                title="Component Health",
                type=PanelType.TABLE,
                queries=[{
                    "expr": f'{self.metrics_prefix}component_health{{component=~"$component"}}',
                    "format": "table",
                    "instant": True,
                }],
                grid_pos={"h": 8, "w": 24, "x": 0, "y": 0},
            ).to_dict(),
            # Neo4j health
            GrafanaPanel(
                title="Neo4j Connection Pool",
                type=PanelType.GAUGE,
                queries=[{
                    "expr": f'{self.metrics_prefix}neo4j_pool_available',
                    "legendFormat": "Available",
                }],
                grid_pos={"h": 6, "w": 8, "x": 0, "y": 8},
                thresholds=[
                    {"value": None, "color": "red"},
                    {"value": 5, "color": "yellow"},
                    {"value": 10, "color": "green"},
                ],
            ).to_dict(),
            # Redis health
            GrafanaPanel(
                title="Redis Connection",
                type=PanelType.STAT,
                queries=[{
                    "expr": f'{self.metrics_prefix}redis_connected',
                    "legendFormat": "Status",
                }],
                grid_pos={"h": 6, "w": 8, "x": 8, "y": 8},
                thresholds=[
                    {"value": None, "color": "red"},
                    {"value": 1, "color": "green"},
                ],
            ).to_dict(),
            # Memory usage
            GrafanaPanel(
                title="Memory Usage",
                type=PanelType.GAUGE,
                queries=[{
                    "expr": f'{self.metrics_prefix}memory_usage_bytes / 1024 / 1024 / 1024',
                    "legendFormat": "GB",
                }],
                grid_pos={"h": 6, "w": 8, "x": 16, "y": 8},
                options={"unit": "GB"},
            ).to_dict(),
            # Health history
            GrafanaPanel(
                title="Health History",
                type=PanelType.TIMESERIES,
                queries=[{
                    "expr": f'{self.metrics_prefix}component_health{{component=~"$component"}}',
                    "legendFormat": "{{component}}",
                }],
                grid_pos={"h": 8, "w": 24, "x": 0, "y": 14},
            ).to_dict(),
        ]

    def _get_performance_panels(self) -> list[dict[str, Any]]:
        """Get performance dashboard panels."""
        return [
            # Operation latency distribution
            GrafanaPanel(
                title="Operation Latency Distribution",
                type=PanelType.HEATMAP,
                queries=[{
                    "expr": f'rate({self.metrics_prefix}operation_duration_seconds_bucket{{operation=~"$operation"}}[5m])',
                    "format": "heatmap",
                }],
                grid_pos={"h": 10, "w": 24, "x": 0, "y": 0},
            ).to_dict(),
            # Throughput
            GrafanaPanel(
                title="Operations per Second",
                type=PanelType.TIMESERIES,
                queries=[{
                    "expr": f'rate({self.metrics_prefix}operations_total{{operation=~"$operation"}}[5m])',
                    "legendFormat": "{{operation}}",
                }],
                grid_pos={"h": 8, "w": 12, "x": 0, "y": 10},
            ).to_dict(),
            # Latency percentiles
            GrafanaPanel(
                title="Latency Percentiles",
                type=PanelType.TIMESERIES,
                queries=[
                    {
                        "expr": f'histogram_quantile(0.50, rate({self.metrics_prefix}operation_duration_seconds_bucket[5m]))',
                        "legendFormat": "p50",
                    },
                    {
                        "expr": f'histogram_quantile(0.95, rate({self.metrics_prefix}operation_duration_seconds_bucket[5m]))',
                        "legendFormat": "p95",
                    },
                    {
                        "expr": f'histogram_quantile(0.99, rate({self.metrics_prefix}operation_duration_seconds_bucket[5m]))',
                        "legendFormat": "p99",
                    },
                ],
                grid_pos={"h": 8, "w": 12, "x": 12, "y": 10},
            ).to_dict(),
            # Circuit breaker status
            GrafanaPanel(
                title="Circuit Breaker Status",
                type=PanelType.TABLE,
                queries=[{
                    "expr": f'{self.metrics_prefix}circuit_breaker_state',
                    "format": "table",
                    "instant": True,
                }],
                grid_pos={"h": 6, "w": 12, "x": 0, "y": 18},
            ).to_dict(),
            # Retry statistics
            GrafanaPanel(
                title="Retry Rate",
                type=PanelType.TIMESERIES,
                queries=[{
                    "expr": f'rate({self.metrics_prefix}retry_attempts_total[5m])',
                    "legendFormat": "{{operation}}",
                }],
                grid_pos={"h": 6, "w": 12, "x": 12, "y": 18},
            ).to_dict(),
        ]

    def _get_cache_panels(self) -> list[dict[str, Any]]:
        """Get cache dashboard panels."""
        return [
            # Hit rate
            GrafanaPanel(
                title="Cache Hit Rate",
                type=PanelType.GAUGE,
                queries=[{
                    "expr": f'{self.metrics_prefix}cache_hits_total / ({self.metrics_prefix}cache_hits_total + {self.metrics_prefix}cache_misses_total)',
                    "legendFormat": "{{cache_type}}",
                }],
                grid_pos={"h": 6, "w": 8, "x": 0, "y": 0},
                thresholds=[
                    {"value": None, "color": "red"},
                    {"value": 0.5, "color": "yellow"},
                    {"value": 0.8, "color": "green"},
                ],
                options={"unit": "percentunit"},
            ).to_dict(),
            # Cache size
            GrafanaPanel(
                title="Cache Size",
                type=PanelType.STAT,
                queries=[{
                    "expr": f'{self.metrics_prefix}cache_size_bytes{{cache_type=~"$cache_type"}}',
                    "legendFormat": "{{cache_type}}",
                }],
                grid_pos={"h": 6, "w": 8, "x": 8, "y": 0},
                options={"unit": "bytes"},
            ).to_dict(),
            # Cache entries
            GrafanaPanel(
                title="Cache Entries",
                type=PanelType.STAT,
                queries=[{
                    "expr": f'{self.metrics_prefix}cache_entries{{cache_type=~"$cache_type"}}',
                    "legendFormat": "{{cache_type}}",
                }],
                grid_pos={"h": 6, "w": 8, "x": 16, "y": 0},
            ).to_dict(),
            # Hits/Misses over time
            GrafanaPanel(
                title="Cache Operations",
                type=PanelType.TIMESERIES,
                queries=[
                    {
                        "expr": f'rate({self.metrics_prefix}cache_hits_total{{cache_type=~"$cache_type"}}[5m])',
                        "legendFormat": "{{cache_type}} hits",
                    },
                    {
                        "expr": f'rate({self.metrics_prefix}cache_misses_total{{cache_type=~"$cache_type"}}[5m])',
                        "legendFormat": "{{cache_type}} misses",
                    },
                ],
                grid_pos={"h": 8, "w": 24, "x": 0, "y": 6},
            ).to_dict(),
            # Evictions
            GrafanaPanel(
                title="Cache Evictions",
                type=PanelType.TIMESERIES,
                queries=[{
                    "expr": f'rate({self.metrics_prefix}cache_evictions_total{{cache_type=~"$cache_type"}}[5m])',
                    "legendFormat": "{{cache_type}}",
                }],
                grid_pos={"h": 6, "w": 12, "x": 0, "y": 14},
            ).to_dict(),
            # TTL distribution
            GrafanaPanel(
                title="Cache TTL by Type",
                type=PanelType.BAR,
                queries=[{
                    "expr": f'{self.metrics_prefix}cache_ttl_seconds',
                    "legendFormat": "{{cache_type}}",
                }],
                grid_pos={"h": 6, "w": 12, "x": 12, "y": 14},
            ).to_dict(),
        ]

    def _get_benchmark_panels(self) -> list[dict[str, Any]]:
        """Get benchmark dashboard panels."""
        return [
            # Overall score
            GrafanaPanel(
                title="Benchmark Score",
                type=PanelType.GAUGE,
                queries=[{
                    "expr": f'{self.metrics_prefix}benchmark_score{{suite=~"$benchmark_suite"}}',
                    "legendFormat": "{{suite}}",
                }],
                grid_pos={"h": 8, "w": 8, "x": 0, "y": 0},
                thresholds=[
                    {"value": None, "color": "red"},
                    {"value": 0.6, "color": "yellow"},
                    {"value": 0.8, "color": "green"},
                ],
                options={"unit": "percentunit"},
            ).to_dict(),
            # Accuracy by category
            GrafanaPanel(
                title="Accuracy by Category",
                type=PanelType.BAR,
                queries=[{
                    "expr": f'{self.metrics_prefix}benchmark_accuracy{{suite=~"$benchmark_suite"}}',
                    "legendFormat": "{{category}}",
                }],
                grid_pos={"h": 8, "w": 16, "x": 8, "y": 0},
            ).to_dict(),
            # Multi-hop accuracy
            GrafanaPanel(
                title="Multi-hop Reasoning Accuracy",
                type=PanelType.TIMESERIES,
                queries=[
                    {
                        "expr": f'{self.metrics_prefix}multihop_accuracy{{hops="1"}}',
                        "legendFormat": "1 hop",
                    },
                    {
                        "expr": f'{self.metrics_prefix}multihop_accuracy{{hops="2"}}',
                        "legendFormat": "2 hops",
                    },
                    {
                        "expr": f'{self.metrics_prefix}multihop_accuracy{{hops="3"}}',
                        "legendFormat": "3 hops",
                    },
                    {
                        "expr": f'{self.metrics_prefix}multihop_accuracy{{hops="4"}}',
                        "legendFormat": "4 hops",
                    },
                    {
                        "expr": f'{self.metrics_prefix}multihop_accuracy{{hops="5"}}',
                        "legendFormat": "5 hops",
                    },
                ],
                grid_pos={"h": 8, "w": 12, "x": 0, "y": 8},
            ).to_dict(),
            # Benchmark history
            GrafanaPanel(
                title="Benchmark Score History",
                type=PanelType.TIMESERIES,
                queries=[{
                    "expr": f'{self.metrics_prefix}benchmark_score{{suite=~"$benchmark_suite"}}',
                    "legendFormat": "{{suite}}",
                }],
                grid_pos={"h": 8, "w": 12, "x": 12, "y": 8},
            ).to_dict(),
            # Comparison with baselines
            GrafanaPanel(
                title="Comparison with Baselines",
                type=PanelType.TABLE,
                queries=[{
                    "expr": f'{self.metrics_prefix}benchmark_comparison',
                    "format": "table",
                    "instant": True,
                }],
                grid_pos={"h": 8, "w": 24, "x": 0, "y": 16},
            ).to_dict(),
        ]

    def _get_query_panels(self) -> list[dict[str, Any]]:
        """Get query analysis dashboard panels."""
        return [
            # Query rate by type
            GrafanaPanel(
                title="Queries per Second",
                type=PanelType.TIMESERIES,
                queries=[{
                    "expr": f'rate({self.metrics_prefix}queries_total{{query_type=~"$query_type"}}[5m])',
                    "legendFormat": "{{query_type}}",
                }],
                grid_pos={"h": 8, "w": 12, "x": 0, "y": 0},
            ).to_dict(),
            # Query latency by type
            GrafanaPanel(
                title="Query Latency by Type",
                type=PanelType.TIMESERIES,
                queries=[{
                    "expr": f'histogram_quantile(0.95, rate({self.metrics_prefix}query_duration_seconds_bucket{{query_type=~"$query_type"}}[5m]))',
                    "legendFormat": "{{query_type}} p95",
                }],
                grid_pos={"h": 8, "w": 12, "x": 12, "y": 0},
            ).to_dict(),
            # Query result sizes
            GrafanaPanel(
                title="Query Result Sizes",
                type=PanelType.HEATMAP,
                queries=[{
                    "expr": f'rate({self.metrics_prefix}query_result_size_bucket[5m])',
                    "format": "heatmap",
                }],
                grid_pos={"h": 8, "w": 24, "x": 0, "y": 8},
            ).to_dict(),
            # Path finding stats
            GrafanaPanel(
                title="Path Finding - Avg Hops",
                type=PanelType.STAT,
                queries=[{
                    "expr": f'{self.metrics_prefix}path_finding_avg_hops',
                    "legendFormat": "Avg Hops",
                }],
                grid_pos={"h": 6, "w": 8, "x": 0, "y": 16},
            ).to_dict(),
            GrafanaPanel(
                title="Path Finding - Success Rate",
                type=PanelType.GAUGE,
                queries=[{
                    "expr": f'{self.metrics_prefix}path_finding_success_rate',
                    "legendFormat": "Success Rate",
                }],
                grid_pos={"h": 6, "w": 8, "x": 8, "y": 16},
                thresholds=[
                    {"value": None, "color": "red"},
                    {"value": 0.7, "color": "yellow"},
                    {"value": 0.9, "color": "green"},
                ],
                options={"unit": "percentunit"},
            ).to_dict(),
            # Concurrent queries
            GrafanaPanel(
                title="Concurrent Queries",
                type=PanelType.TIMESERIES,
                queries=[{
                    "expr": f'{self.metrics_prefix}concurrent_queries',
                    "legendFormat": "Active Queries",
                }],
                grid_pos={"h": 6, "w": 8, "x": 16, "y": 16},
            ).to_dict(),
        ]

    def generate_all_dashboards(self) -> dict[str, dict[str, Any]]:
        """Generate all dashboard configurations."""
        return {
            "overview": self.generate_overview_dashboard(),
            "health": self.generate_health_dashboard(),
            "performance": self.generate_performance_dashboard(),
            "cache": self.generate_cache_dashboard(),
            "benchmark": self.generate_benchmark_dashboard(),
            "query": self.generate_query_dashboard(),
        }

    def export_dashboard(
        self,
        dashboard_type: DashboardType,
        filename: str | None = None,
    ) -> str:
        """
        Export a dashboard to JSON.

        Args:
            dashboard_type: Type of dashboard to export
            filename: Optional filename to write to

        Returns:
            JSON string of dashboard
        """
        generators = {
            DashboardType.OVERVIEW: self.generate_overview_dashboard,
            DashboardType.HEALTH: self.generate_health_dashboard,
            DashboardType.PERFORMANCE: self.generate_performance_dashboard,
            DashboardType.CACHE: self.generate_cache_dashboard,
            DashboardType.BENCHMARK: self.generate_benchmark_dashboard,
            DashboardType.QUERY: self.generate_query_dashboard,
        }

        if dashboard_type not in generators:
            raise ValueError(f"Unknown dashboard type: {dashboard_type}")

        dashboard = generators[dashboard_type]()
        json_str = json.dumps(dashboard, indent=2)

        if filename:
            with open(filename, "w") as f:
                f.write(json_str)

        return json_str

    def generate_alert_rules(self) -> list[dict[str, Any]]:
        """Generate Grafana alert rules."""
        return [
            GrafanaAlert(
                name="KG Service Down",
                condition=f'{self.metrics_prefix}health_status == 0',
                threshold=0,
                for_duration="1m",
                severity="critical",
                message="Knowledge Graph service is down",
            ).to_dict(),
            GrafanaAlert(
                name="High Error Rate",
                condition=f'rate({self.metrics_prefix}errors_total[5m]) > 10',
                threshold=10,
                for_duration="5m",
                severity="warning",
                message="High error rate detected in KG service",
            ).to_dict(),
            GrafanaAlert(
                name="High Latency",
                condition=f'histogram_quantile(0.95, rate({self.metrics_prefix}request_duration_seconds_bucket[5m])) > 2',
                threshold=2,
                for_duration="5m",
                severity="warning",
                message="KG service latency is above threshold",
            ).to_dict(),
            GrafanaAlert(
                name="Low Cache Hit Rate",
                condition=f'{self.metrics_prefix}cache_hits_total / ({self.metrics_prefix}cache_hits_total + {self.metrics_prefix}cache_misses_total) < 0.5',
                threshold=0.5,
                for_duration="10m",
                severity="warning",
                message="Cache hit rate is below 50%",
            ).to_dict(),
            GrafanaAlert(
                name="Circuit Breaker Open",
                condition=f'{self.metrics_prefix}circuit_breaker_state == 1',
                threshold=1,
                for_duration="1m",
                severity="critical",
                message="Circuit breaker is open",
            ).to_dict(),
            GrafanaAlert(
                name="Neo4j Connection Pool Exhausted",
                condition=f'{self.metrics_prefix}neo4j_pool_available < 2',
                threshold=2,
                for_duration="2m",
                severity="critical",
                message="Neo4j connection pool is nearly exhausted",
            ).to_dict(),
        ]


# Singleton instance
_dashboard_generator: GrafanaDashboardGenerator | None = None
_dashboard_lock = threading.Lock()


def get_dashboard_generator() -> GrafanaDashboardGenerator:
    """Get or create dashboard generator singleton."""
    global _dashboard_generator
    # VP-ThreadSafety: Double-checked locking for thread safety
    if _dashboard_generator is None:
        with _dashboard_lock:
            if _dashboard_generator is None:
                _dashboard_generator = GrafanaDashboardGenerator()
    return _dashboard_generator
