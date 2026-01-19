"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  CheckCircle,
  Clock,
  Database,
  Gauge,
  Loader2,
  Radio,
  RefreshCw,
  Server,
  Wifi,
  WifiOff,
  Zap,
} from "lucide-react";

// =============================================================================
// Types
// =============================================================================

interface StreamingHealth {
  status: "healthy" | "degraded" | "unhealthy";
  kafka: {
    connected: boolean;
    broker_count: number;
    topic_count: number;
    error_message: string | null;
  };
  etl: {
    messages_processed: number;
    success_rate: number;
    dead_letter_count: number;
  };
  aggregation: {
    current_throughput: number;
    current_latency_ms: number;
    active_alerts: number;
  };
  timestamp: string;
}

interface StreamingMetrics {
  throughput: {
    current: number;
    peak: number;
    average: number;
    history: Array<{
      timestamp: string;
      messages_per_second: number;
    }>;
  };
  latency: {
    current_ms: number;
    average_ms: number;
    p99_ms: number;
    history: Array<{
      timestamp: string;
      avg_ms: number;
      p99_ms: number;
    }>;
  };
  quality: {
    error_rate_1min: number;
    error_rate_5min: number;
    dead_letter_count: number;
  };
  windows: {
    messages_1min: number;
    messages_5min: number;
    messages_1hr: number;
  };
  timestamp: string;
}

interface TopicStats {
  name: string;
  partitions: number;
  total_messages: number;
  messages_per_second: number;
  consumer_lag: number;
  last_message_time: string | null;
}

interface StreamingEvent {
  type: string;
  timestamp: string;
  data?: Record<string, unknown>;
}

// =============================================================================
// Mock Data Generator
// =============================================================================

function generateMockMetrics(): StreamingMetrics {
  const now = new Date();
  const history = Array.from({ length: 60 }, (_, i) => {
    const time = new Date(now.getTime() - (60 - i) * 1000);
    return {
      timestamp: time.toISOString(),
      messages_per_second: 40 + Math.random() * 30,
      avg_ms: 15 + Math.random() * 10,
      p99_ms: 30 + Math.random() * 20,
    };
  });

  return {
    throughput: {
      current: 45 + Math.random() * 20,
      peak: 85 + Math.random() * 15,
      average: 52 + Math.random() * 10,
      history: history.map((h) => ({
        timestamp: h.timestamp,
        messages_per_second: h.messages_per_second,
      })),
    },
    latency: {
      current_ms: 18 + Math.random() * 8,
      average_ms: 20 + Math.random() * 5,
      p99_ms: 45 + Math.random() * 15,
      history: history.map((h) => ({
        timestamp: h.timestamp,
        avg_ms: h.avg_ms,
        p99_ms: h.p99_ms,
      })),
    },
    quality: {
      error_rate_1min: Math.random() * 2,
      error_rate_5min: Math.random() * 1.5,
      dead_letter_count: Math.floor(Math.random() * 10),
    },
    windows: {
      messages_1min: Math.floor(2500 + Math.random() * 500),
      messages_5min: Math.floor(12000 + Math.random() * 3000),
      messages_1hr: Math.floor(140000 + Math.random() * 20000),
    },
    timestamp: now.toISOString(),
  };
}

// =============================================================================
// Components
// =============================================================================

function StatusIndicator({ status }: { status: string }) {
  if (status === "healthy") {
    return (
      <div className="flex items-center gap-2">
        <div className="h-3 w-3 rounded-full bg-green-500 animate-pulse" />
        <span className="text-sm text-green-600 dark:text-green-400">
          Healthy
        </span>
      </div>
    );
  }
  if (status === "degraded") {
    return (
      <div className="flex items-center gap-2">
        <div className="h-3 w-3 rounded-full bg-yellow-500 animate-pulse" />
        <span className="text-sm text-yellow-600 dark:text-yellow-400">
          Degraded (Mock Mode)
        </span>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-2">
      <div className="h-3 w-3 rounded-full bg-red-500" />
      <span className="text-sm text-red-600 dark:text-red-400">Unhealthy</span>
    </div>
  );
}

function ThroughputChart({ history }: { history: Array<{ timestamp: string; messages_per_second: number }> }) {
  const maxValue = Math.max(...history.map((h) => h.messages_per_second), 1);
  const chartHeight = 120;

  return (
    <div className="relative h-[120px] w-full">
      <svg className="w-full h-full" preserveAspectRatio="none">
        {/* Grid lines */}
        <line
          x1="0"
          y1={chartHeight / 3}
          x2="100%"
          y2={chartHeight / 3}
          stroke="currentColor"
          className="text-muted-foreground/20"
          strokeDasharray="4 4"
        />
        <line
          x1="0"
          y1={(chartHeight * 2) / 3}
          x2="100%"
          y2={(chartHeight * 2) / 3}
          stroke="currentColor"
          className="text-muted-foreground/20"
          strokeDasharray="4 4"
        />

        {/* Area chart */}
        <defs>
          <linearGradient id="throughputGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity="0.3" />
            <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path
          d={`M 0 ${chartHeight} ${history
            .map(
              (h, i) =>
                `L ${(i / (history.length - 1)) * 100}% ${
                  chartHeight - (h.messages_per_second / maxValue) * chartHeight
                }`
            )
            .join(" ")} L 100% ${chartHeight} Z`}
          fill="url(#throughputGradient)"
        />
        <path
          d={`M 0 ${chartHeight - (history[0]?.messages_per_second || 0) / maxValue * chartHeight} ${history
            .map(
              (h, i) =>
                `L ${(i / (history.length - 1)) * 100}% ${
                  chartHeight - (h.messages_per_second / maxValue) * chartHeight
                }`
            )
            .join(" ")}`}
          fill="none"
          stroke="hsl(var(--primary))"
          strokeWidth="2"
        />
      </svg>

      {/* Y-axis labels */}
      <div className="absolute left-0 top-0 text-[10px] text-muted-foreground">
        {Math.round(maxValue)}
      </div>
      <div className="absolute left-0 bottom-0 text-[10px] text-muted-foreground">
        0
      </div>
    </div>
  );
}

function LatencyHistogram({ history }: { history: Array<{ timestamp: string; avg_ms: number; p99_ms: number }> }) {
  const maxValue = Math.max(...history.map((h) => h.p99_ms), 1);
  const barWidth = 100 / history.length;

  return (
    <div className="relative h-[100px] w-full flex items-end gap-[1px]">
      {history.slice(-30).map((h, i) => {
        const avgHeight = (h.avg_ms / maxValue) * 100;
        const p99Height = (h.p99_ms / maxValue) * 100;

        return (
          <div
            key={i}
            className="flex-1 relative"
            title={`Avg: ${h.avg_ms.toFixed(1)}ms, P99: ${h.p99_ms.toFixed(1)}ms`}
          >
            {/* P99 bar (background) */}
            <div
              className="absolute bottom-0 left-0 right-0 bg-primary/20 rounded-t"
              style={{ height: `${p99Height}%` }}
            />
            {/* Avg bar (foreground) */}
            <div
              className="absolute bottom-0 left-0 right-0 bg-primary rounded-t"
              style={{ height: `${avgHeight}%` }}
            />
          </div>
        );
      })}
    </div>
  );
}

function EventFeed({ events }: { events: StreamingEvent[] }) {
  return (
    <div className="space-y-2 max-h-[300px] overflow-y-auto">
      {events.length === 0 ? (
        <p className="text-sm text-muted-foreground text-center py-4">
          No recent events
        </p>
      ) : (
        events.map((event, i) => (
          <div
            key={i}
            className="flex items-start gap-3 p-2 rounded-lg bg-muted/30 text-sm"
          >
            <div className="mt-0.5">
              {event.type === "metrics" ? (
                <Gauge className="h-4 w-4 text-blue-500" />
              ) : event.type === "alert" ? (
                <AlertTriangle className="h-4 w-4 text-yellow-500" />
              ) : event.type === "error" ? (
                <AlertCircle className="h-4 w-4 text-red-500" />
              ) : (
                <Radio className="h-4 w-4 text-green-500" />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-medium truncate">
                {event.type === "connected"
                  ? "Connected to streaming"
                  : event.type === "metrics"
                  ? `Throughput: ${(event.data?.throughput as number)?.toFixed(1) || 0} msg/s`
                  : event.type === "alert"
                  ? (event.data?.title as string) || "New Alert"
                  : event.type}
              </p>
              <p className="text-xs text-muted-foreground">
                {new Date(event.timestamp).toLocaleTimeString()}
              </p>
            </div>
          </div>
        ))
      )}
    </div>
  );
}

// =============================================================================
// Main Page Component
// =============================================================================

export default function StreamingDashboardPage() {
  const [health, setHealth] = useState<StreamingHealth | null>(null);
  const [metrics, setMetrics] = useState<StreamingMetrics | null>(null);
  const [topics, setTopics] = useState<TopicStats[]>([]);
  const [events, setEvents] = useState<StreamingEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isConnected, setIsConnected] = useState(false);
  const [mockMode, setMockMode] = useState(true);
  const wsRef = useRef<WebSocket | null>(null);

  // Fetch health and metrics
  const fetchData = useCallback(async () => {
    try {
      const [healthRes, metricsRes, topicsRes] = await Promise.all([
        fetch("http://localhost:8000/api/v1/streaming/health"),
        fetch("http://localhost:8000/api/v1/streaming/metrics?minutes=5"),
        fetch("http://localhost:8000/api/v1/streaming/topics"),
      ]);

      if (healthRes.ok) {
        const healthData = await healthRes.json();
        setHealth(healthData);
        setMockMode(healthData.kafka?.error_message?.includes("mock") || false);
      }

      if (metricsRes.ok) {
        const metricsData = await metricsRes.json();
        setMetrics(metricsData);
      }

      if (topicsRes.ok) {
        const topicsData = await topicsRes.json();
        setTopics(topicsData.topics || []);
        setMockMode(topicsData.mock_mode);
      }
    } catch (error) {
      console.error("Failed to fetch streaming data:", error);
      // Use mock data
      setMetrics(generateMockMetrics());
      setMockMode(true);
      setHealth({
        status: "degraded",
        kafka: {
          connected: false,
          broker_count: 0,
          topic_count: 7,
          error_message: "Using mock mode - Kafka not available",
        },
        etl: {
          messages_processed: 15420,
          success_rate: 98.5,
          dead_letter_count: 5,
        },
        aggregation: {
          current_throughput: 52.3,
          current_latency_ms: 22.1,
          active_alerts: 2,
        },
        timestamp: new Date().toISOString(),
      });
      setTopics([
        { name: "clinical.hl7v2.inbound", partitions: 6, total_messages: 54230, messages_per_second: 23.5, consumer_lag: 120, last_message_time: new Date().toISOString() },
        { name: "clinical.fhir.inbound", partitions: 6, total_messages: 32150, messages_per_second: 15.2, consumer_lag: 45, last_message_time: new Date().toISOString() },
        { name: "clinical.omop.outbound", partitions: 3, total_messages: 78420, messages_per_second: 35.8, consumer_lag: 200, last_message_time: new Date().toISOString() },
        { name: "clinical.alerts", partitions: 1, total_messages: 1240, messages_per_second: 0.5, consumer_lag: 0, last_message_time: new Date().toISOString() },
        { name: "clinical.dlq", partitions: 1, total_messages: 52, messages_per_second: 0.1, consumer_lag: 0, last_message_time: new Date().toISOString() },
      ]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // WebSocket connection
  useEffect(() => {
    fetchData();

    // Try to connect to WebSocket
    const connectWebSocket = () => {
      try {
        const ws = new WebSocket("ws://localhost:8000/api/v1/streaming/ws");

        ws.onopen = () => {
          setIsConnected(true);
          setEvents((prev) => [
            {
              type: "connected",
              timestamp: new Date().toISOString(),
            },
            ...prev.slice(0, 49),
          ]);
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            setEvents((prev) => [
              {
                type: data.type,
                timestamp: data.timestamp || new Date().toISOString(),
                data: data.data,
              },
              ...prev.slice(0, 49),
            ]);

            // Update metrics from WebSocket
            if (data.type === "metrics" && data.data) {
              setMetrics((prev) => {
                if (!prev) return prev;
                return {
                  ...prev,
                  throughput: {
                    ...prev.throughput,
                    current: data.data.throughput || prev.throughput.current,
                  },
                  latency: {
                    ...prev.latency,
                    current_ms: data.data.latency_ms || prev.latency.current_ms,
                  },
                  quality: {
                    ...prev.quality,
                    error_rate_1min: data.data.error_rate || prev.quality.error_rate_1min,
                  },
                };
              });
            }
          } catch (e) {
            console.error("Failed to parse WebSocket message:", e);
          }
        };

        ws.onclose = () => {
          setIsConnected(false);
        };

        ws.onerror = () => {
          setIsConnected(false);
        };

        wsRef.current = ws;
      } catch (error) {
        console.error("Failed to connect WebSocket:", error);
      }
    };

    connectWebSocket();

    // Fallback: simulate updates if WebSocket fails
    const interval = setInterval(() => {
      if (!isConnected) {
        setMetrics(generateMockMetrics());
      }
    }, 2000);

    return () => {
      clearInterval(interval);
      wsRef.current?.close();
    };
  }, [fetchData, isConnected]);

  const refreshData = () => {
    setIsLoading(true);
    fetchData();
  };

  if (isLoading && !metrics) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Real-time Streaming
          </h1>
          <p className="text-muted-foreground">
            Monitor Kafka pipeline throughput, latency, and health
          </p>
        </div>
        <div className="flex items-center gap-4">
          {/* Connection Status */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-muted">
            {isConnected ? (
              <>
                <Wifi className="h-4 w-4 text-green-500" />
                <span className="text-sm">Connected</span>
              </>
            ) : (
              <>
                <WifiOff className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">
                  {mockMode ? "Mock Mode" : "Disconnected"}
                </span>
              </>
            )}
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={refreshData}
            disabled={isLoading}
          >
            <RefreshCw
              className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
        </div>
      </div>

      {/* Mock Mode Banner */}
      {mockMode && (
        <div className="flex items-center gap-3 p-3 rounded-lg bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800">
          <AlertTriangle className="h-5 w-5 text-yellow-600 dark:text-yellow-400" />
          <div className="flex-1">
            <p className="text-sm font-medium text-yellow-800 dark:text-yellow-200">
              Running in Mock Mode
            </p>
            <p className="text-xs text-yellow-700 dark:text-yellow-300">
              Kafka is not available. Displaying simulated streaming data for
              development.
            </p>
          </div>
        </div>
      )}

      {/* Status Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* Pipeline Status */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Pipeline Status</CardTitle>
            <Server className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <StatusIndicator status={health?.status || "degraded"} />
            <p className="text-xs text-muted-foreground mt-2">
              {health?.kafka?.broker_count || 0} brokers,{" "}
              {health?.kafka?.topic_count || 0} topics
            </p>
          </CardContent>
        </Card>

        {/* Throughput */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Throughput</CardTitle>
            <Zap className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {metrics?.throughput?.current?.toFixed(1) || 0}
              <span className="text-sm font-normal text-muted-foreground">
                {" "}
                msg/s
              </span>
            </div>
            <p className="text-xs text-muted-foreground">
              Peak: {metrics?.throughput?.peak?.toFixed(1) || 0} msg/s
            </p>
          </CardContent>
        </Card>

        {/* Latency */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Latency</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {metrics?.latency?.current_ms?.toFixed(1) || 0}
              <span className="text-sm font-normal text-muted-foreground">
                {" "}
                ms
              </span>
            </div>
            <p className="text-xs text-muted-foreground">
              P99: {metrics?.latency?.p99_ms?.toFixed(1) || 0} ms
            </p>
          </CardContent>
        </Card>

        {/* Active Alerts */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Active Alerts</CardTitle>
            <AlertTriangle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {health?.aggregation?.active_alerts || 0}
            </div>
            <Link href="/analytics/streaming/alerts">
              <Button variant="ghost" size="sm" className="p-0 h-auto text-xs">
                View alerts
                <ArrowRight className="ml-1 h-3 w-3" />
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>

      {/* Charts Section */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Throughput Chart */}
        <Card>
          <CardHeader>
            <CardTitle>Throughput (messages/sec)</CardTitle>
            <CardDescription>Last 60 seconds of message throughput</CardDescription>
          </CardHeader>
          <CardContent>
            {metrics?.throughput?.history && (
              <ThroughputChart history={metrics.throughput.history} />
            )}
            <div className="flex items-center justify-between mt-4 text-sm">
              <div>
                <span className="text-muted-foreground">Current: </span>
                <span className="font-medium">
                  {metrics?.throughput?.current?.toFixed(1)} msg/s
                </span>
              </div>
              <div>
                <span className="text-muted-foreground">Average: </span>
                <span className="font-medium">
                  {metrics?.throughput?.average?.toFixed(1)} msg/s
                </span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Latency Histogram */}
        <Card>
          <CardHeader>
            <CardTitle>Processing Latency</CardTitle>
            <CardDescription>
              Average and P99 latency distribution
            </CardDescription>
          </CardHeader>
          <CardContent>
            {metrics?.latency?.history && (
              <LatencyHistogram history={metrics.latency.history} />
            )}
            <div className="flex items-center justify-between mt-4 text-sm">
              <div className="flex items-center gap-2">
                <div className="h-3 w-3 rounded bg-primary" />
                <span className="text-muted-foreground">
                  Avg: {metrics?.latency?.average_ms?.toFixed(1)} ms
                </span>
              </div>
              <div className="flex items-center gap-2">
                <div className="h-3 w-3 rounded bg-primary/20" />
                <span className="text-muted-foreground">
                  P99: {metrics?.latency?.p99_ms?.toFixed(1)} ms
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Topics and Events */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Topic Health */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Topic Health</CardTitle>
            <CardDescription>
              Kafka topics with partition and lag information
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {topics.map((topic) => (
                <div
                  key={topic.name}
                  className="flex items-center justify-between p-3 rounded-lg border"
                >
                  <div className="flex items-center gap-3">
                    <Database className="h-4 w-4 text-muted-foreground" />
                    <div>
                      <p className="font-medium text-sm">{topic.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {topic.partitions} partitions
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-6 text-sm">
                    <div className="text-right">
                      <p className="font-medium">
                        {topic.messages_per_second?.toFixed(1)} msg/s
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {topic.total_messages?.toLocaleString()} total
                      </p>
                    </div>
                    <div className="text-right min-w-[60px]">
                      <Badge
                        variant={
                          topic.consumer_lag > 1000
                            ? "destructive"
                            : topic.consumer_lag > 100
                            ? "secondary"
                            : "outline"
                        }
                      >
                        Lag: {topic.consumer_lag}
                      </Badge>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Recent Events */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Events</CardTitle>
            <CardDescription>Live updating event feed</CardDescription>
          </CardHeader>
          <CardContent>
            <EventFeed events={events} />
          </CardContent>
        </Card>
      </div>

      {/* Window Statistics */}
      <Card>
        <CardHeader>
          <CardTitle>Window Statistics</CardTitle>
          <CardDescription>
            Message counts in tumbling time windows
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="p-4 rounded-lg bg-muted/50">
              <p className="text-sm text-muted-foreground">1 Minute Window</p>
              <p className="text-2xl font-bold">
                {metrics?.windows?.messages_1min?.toLocaleString() || 0}
              </p>
              <p className="text-xs text-muted-foreground">messages</p>
            </div>
            <div className="p-4 rounded-lg bg-muted/50">
              <p className="text-sm text-muted-foreground">5 Minute Window</p>
              <p className="text-2xl font-bold">
                {metrics?.windows?.messages_5min?.toLocaleString() || 0}
              </p>
              <p className="text-xs text-muted-foreground">messages</p>
            </div>
            <div className="p-4 rounded-lg bg-muted/50">
              <p className="text-sm text-muted-foreground">1 Hour Window</p>
              <p className="text-2xl font-bold">
                {metrics?.windows?.messages_1hr?.toLocaleString() || 0}
              </p>
              <p className="text-xs text-muted-foreground">messages</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Quick Links */}
      <div className="grid gap-4 sm:grid-cols-2">
        <Link href="/analytics/streaming/alerts">
          <Card className="hover:bg-muted/50 transition-colors cursor-pointer">
            <CardContent className="flex items-center gap-4 p-6">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-yellow-100 dark:bg-yellow-900">
                <AlertTriangle className="h-6 w-6 text-yellow-600 dark:text-yellow-400" />
              </div>
              <div>
                <h3 className="font-semibold">Alert Console</h3>
                <p className="text-sm text-muted-foreground">
                  View and acknowledge streaming alerts
                </p>
              </div>
              <ArrowRight className="h-5 w-5 ml-auto text-muted-foreground" />
            </CardContent>
          </Card>
        </Link>

        <Link href="/analytics/streaming/quality">
          <Card className="hover:bg-muted/50 transition-colors cursor-pointer">
            <CardContent className="flex items-center gap-4 p-6">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-blue-100 dark:bg-blue-900">
                <Activity className="h-6 w-6 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <h3 className="font-semibold">Data Quality Monitor</h3>
                <p className="text-sm text-muted-foreground">
                  View validation errors and schema drift
                </p>
              </div>
              <ArrowRight className="h-5 w-5 ml-auto text-muted-foreground" />
            </CardContent>
          </Card>
        </Link>
      </div>
    </div>
  );
}
