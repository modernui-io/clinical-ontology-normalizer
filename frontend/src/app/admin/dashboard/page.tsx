"use client";

import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  LayoutDashboard,
  Server,
  Database,
  HardDrive,
  Activity,
  Users,
  AlertTriangle,
  CheckCircle,
  XCircle,
  RefreshCw,
  Trash2,
  RotateCcw,
  Cpu,
  MemoryStick,
  Wifi,
  WifiOff,
  Clock,
  TrendingUp,
  TrendingDown,
  BarChart3,
  Zap,
  Loader2,
  FileText,
  Stethoscope,
} from "lucide-react";
import DataSourceModeBanner from "@/components/readiness/DataSourceModeBanner";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
} from "recharts";

// ==============================================================================
// Types matching backend AdminDashboardResponse
// ==============================================================================

interface DashboardMetadata {
  generated_at: string;
  patient_id: string | null;
  time_window: string;
}

interface SystemStatsSummary {
  total_patients: number;
  total_documents: number;
  total_extractions: number;
  documents_today: number;
  documents_this_week: number;
}

interface ServiceHealthSummary {
  service_name: string;
  status: string; // "healthy" | "unhealthy" | "degraded"
  stats: Record<string, unknown>;
}

interface ActionItem {
  priority: string;
  title: string;
  description: string;
  category: string;
  patient_id?: string | null;
  estimated_impact?: string | null;
}

interface AdminDashboardResponse {
  metadata: DashboardMetadata;
  system_stats: SystemStatsSummary;
  service_health: ServiceHealthSummary[];
  provider_summary: Record<string, unknown>;
  biller_summary: Record<string, unknown>;
  quality_summary: Record<string, unknown>;
  all_action_items: ActionItem[];
}

// ==============================================================================
// Types for UI-only data (no backend endpoint)
// ==============================================================================

interface SystemMetrics {
  cpuUsage: number;
  memoryUsage: number;
  diskUsage: number;
  activeConnections: number;
}

interface RequestVolumeData {
  time: string;
  requests: number;
  errors: number;
}

// ==============================================================================
// Simulated data for sections without a backend endpoint
// ==============================================================================

const defaultMetrics: SystemMetrics = {
  cpuUsage: 42,
  memoryUsage: 68,
  diskUsage: 54,
  activeConnections: 127,
};

const generateRequestVolumeData = (): RequestVolumeData[] => {
  const data: RequestVolumeData[] = [];
  const now = new Date();
  for (let i = 23; i >= 0; i--) {
    const time = new Date(now.getTime() - i * 60 * 60 * 1000);
    const hour = time.getHours();
    const baseRequests = hour >= 8 && hour <= 18 ? 1500 : 300;
    const requests = Math.floor(baseRequests + Math.random() * 500);
    const errors = Math.floor(requests * (Math.random() * 0.02));
    data.push({
      time: time.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      requests,
      errors,
    });
  }
  return data;
};

// ==============================================================================
// Helper functions
// ==============================================================================

const getStatusIcon = (status: string) => {
  switch (status) {
    case "healthy":
      return <CheckCircle className="h-5 w-5 text-green-600" />;
    case "degraded":
      return <AlertTriangle className="h-5 w-5 text-amber-500" />;
    case "unhealthy":
    case "down":
      return <XCircle className="h-5 w-5 text-red-600" />;
    default:
      return <WifiOff className="h-5 w-5 text-gray-400" />;
  }
};

const getStatusColor = (status: string): string => {
  switch (status) {
    case "healthy":
      return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
    case "degraded":
      return "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200";
    case "unhealthy":
    case "down":
      return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
    default:
      return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";
  }
};

/** Map backend service names to display names. */
const formatServiceName = (name: string): string => {
  const map: Record<string, string> = {
    differential_diagnosis: "Differential Diagnosis",
    clinical_calculator: "Clinical Calculator",
    drug_interaction: "Drug Interaction",
    drug_safety: "Drug Safety",
    lab_reference: "Lab Reference",
    icd10_suggester: "ICD-10 Suggester",
    cpt_suggester: "CPT Suggester",
    billing_optimizer: "Billing Optimizer",
    hcc_analyzer: "HCC Analyzer",
    coding_query_generator: "Coding Query Generator",
    quality_metrics: "Quality Metrics",
  };
  return map[name] ?? name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
};

const getServiceIcon = (name: string) => {
  if (name.includes("database") || name.includes("postgres")) return <Database className="h-4 w-4" />;
  if (name.includes("redis") || name.includes("cache")) return <Zap className="h-4 w-4" />;
  if (name.includes("graph") || name.includes("neo4j")) return <HardDrive className="h-4 w-4" />;
  if (name.includes("quality") || name.includes("metric")) return <Activity className="h-4 w-4" />;
  if (name.includes("clinical") || name.includes("differential") || name.includes("drug") || name.includes("lab")) return <Stethoscope className="h-4 w-4" />;
  if (name.includes("icd") || name.includes("cpt") || name.includes("billing") || name.includes("hcc") || name.includes("coding")) return <FileText className="h-4 w-4" />;
  return <Server className="h-4 w-4" />;
};

const formatTimeAgo = (timestamp: string): string => {
  const now = new Date();
  const date = new Date(timestamp);
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${Math.floor(diffHours / 24)}d ago`;
};

const getProgressColor = (value: number): string => {
  if (value < 50) return "bg-green-500";
  if (value < 75) return "bg-amber-500";
  return "bg-red-500";
};

const getPriorityColor = (priority: string): string => {
  switch (priority) {
    case "high":
      return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
    case "medium":
      return "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200";
    case "low":
      return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
    default:
      return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";
  }
};

// ==============================================================================
// Component
// ==============================================================================

export default function AdminDashboardPage() {
  // API data
  const [dashboardData, setDashboardData] = useState<AdminDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // UI-only state (no backend endpoint for these)
  const [metrics, setMetrics] = useState<SystemMetrics>(defaultMetrics);
  const [requestVolume] = useState<RequestVolumeData[]>(() => generateRequestVolumeData());
  const [isClearing, setIsClearing] = useState(false);
  const [isRestarting, setIsRestarting] = useState(false);

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/dashboard/admin");
      if (!res.ok) {
        throw new Error(`Dashboard API returned ${res.status}: ${res.statusText}`);
      }
      const data: AdminDashboardResponse = await res.json();
      setDashboardData(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to fetch dashboard data";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch on mount
  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  // Simulate resource gauge updates (no backend endpoint for CPU/memory)
  useEffect(() => {
    const interval = setInterval(() => {
      setMetrics((prev) => ({
        cpuUsage: Math.max(0, Math.min(100, prev.cpuUsage + (Math.random() - 0.5) * 5)),
        memoryUsage: Math.max(0, Math.min(100, prev.memoryUsage + (Math.random() - 0.5) * 2)),
        diskUsage: prev.diskUsage,
        activeConnections: Math.max(0, prev.activeConnections + Math.floor((Math.random() - 0.5) * 10)),
      }));
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleClearCache = async () => {
    setIsClearing(true);
    await new Promise((resolve) => setTimeout(resolve, 2000));
    setIsClearing(false);
  };

  const handleRestartServices = async () => {
    setIsRestarting(true);
    await new Promise((resolve) => setTimeout(resolve, 3000));
    setIsRestarting(false);
  };

  // Derived values from API data
  const services = dashboardData?.service_health ?? [];
  const systemStats = dashboardData?.system_stats;
  const qualitySummary = dashboardData?.quality_summary ?? {};
  const actionItems = dashboardData?.all_action_items ?? [];
  const healthyServices = services.filter((s) => s.status === "healthy").length;
  const errorRate = typeof qualitySummary.error_rate === "number" ? (qualitySummary.error_rate * 100).toFixed(2) : "0.00";
  const totalRequests = requestVolume.reduce((sum, d) => sum + d.requests, 0);

  // ============================================================================
  // Loading state
  // ============================================================================

  if (loading) {
    return (
      <div className="p-6 flex flex-col items-center justify-center min-h-[400px] gap-4">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <p className="text-muted-foreground">Loading dashboard...</p>
      </div>
    );
  }

  // ============================================================================
  // Error state
  // ============================================================================

  if (error) {
    return (
      <div className="p-6 space-y-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
              <LayoutDashboard className="h-6 w-6" />
              Admin Dashboard
            </h1>
            <p className="text-muted-foreground">
              System health monitoring and administration
            </p>
          </div>
        </div>
        <Card className="border-destructive">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-destructive">
              <XCircle className="h-5 w-5" />
              Failed to Load Dashboard
            </CardTitle>
            <CardDescription>{error}</CardDescription>
          </CardHeader>
          <CardContent>
            <Button variant="outline" onClick={fetchDashboard}>
              <RefreshCw className="mr-2 h-4 w-4" />
              Retry
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // ============================================================================
  // Main dashboard
  // ============================================================================

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <LayoutDashboard className="h-6 w-6" />
            Admin Dashboard
          </h1>
          <p className="text-muted-foreground">
            System health monitoring and administration
            {dashboardData?.metadata.generated_at && (
              <span className="ml-2 text-xs">
                (generated {formatTimeAgo(dashboardData.metadata.generated_at)})
              </span>
            )}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchDashboard}
            disabled={loading}
          >
            <RefreshCw
              className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
        </div>
      </div>

      <DataSourceModeBanner
        mode="mixed"
        title="Data source mode"
        description="Service health and metadata are loaded from /api/dashboard/admin (live). Request volume and CPU/memory gauges are simulated until a streaming metrics endpoint is wired."
        evidencePath="frontend/src/app/admin/dashboard/page.tsx"
        lastUpdatedAt="2026-02-16"
        signoffText="Simulation only — resource gauges and request volumes are seeded demonstration data. Connect to metrics API for live telemetry."
        backendEndpoints={["/api/v1/health", "/api/v1/metrics"]}
      />

      {/* Service Health Status Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5">
        {services.slice(0, 10).map((service) => (
          <Card key={service.service_name}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                {getServiceIcon(service.service_name)}
                <span className="truncate">{formatServiceName(service.service_name)}</span>
              </CardTitle>
              {getStatusIcon(service.status)}
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <Badge className={getStatusColor(service.status)}>
                  {service.status}
                </Badge>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Key Metrics Row */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Documents</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {(systemStats?.total_documents ?? 0).toLocaleString()}
            </div>
            <div className="flex items-center text-xs text-muted-foreground">
              <TrendingUp className="h-3 w-3 mr-1 text-green-600" />
              <span className="text-green-600">
                {systemStats?.documents_today ?? 0} today
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Extractions</CardTitle>
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {(systemStats?.total_extractions ?? 0).toLocaleString()}
            </div>
            <div className="flex items-center text-xs text-muted-foreground">
              <span>NLP-extracted entities</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Error Rate</CardTitle>
            <AlertTriangle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{errorRate}%</div>
            <div className="flex items-center text-xs text-muted-foreground">
              <span>Processing error rate ({dashboardData?.metadata.time_window ?? "24h"})</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">System Health</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {healthyServices}/{services.length}
            </div>
            <p className="text-xs text-muted-foreground">Services healthy</p>
          </CardContent>
        </Card>
      </div>

      {/* Charts and Gauges Row */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Request Volume Chart (simulated -- no backend time-series endpoint) */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Request Volume (Last 24 Hours)</CardTitle>
            <CardDescription>
              API requests and error counts over time (simulated)
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={requestVolume}>
                  <defs>
                    <linearGradient id="colorRequests" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="colorErrors" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis
                    dataKey="time"
                    tick={{ fontSize: 12 }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 12 }}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(value) => `${value}`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--popover))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "6px",
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="requests"
                    stroke="#3b82f6"
                    fill="url(#colorRequests)"
                    strokeWidth={2}
                    name="Requests"
                  />
                  <Area
                    type="monotone"
                    dataKey="errors"
                    stroke="#ef4444"
                    fill="url(#colorErrors)"
                    strokeWidth={2}
                    name="Errors"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* CPU/Memory Gauges (simulated -- no backend endpoint) */}
        <Card>
          <CardHeader>
            <CardTitle>System Resources</CardTitle>
            <CardDescription>Current resource utilization (simulated)</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Cpu className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-medium">CPU Usage</span>
                </div>
                <span className="text-sm font-bold">{Math.round(metrics.cpuUsage)}%</span>
              </div>
              <div className="relative h-3 w-full overflow-hidden rounded-full bg-secondary">
                <div
                  className={`h-full transition-all duration-500 ${getProgressColor(metrics.cpuUsage)}`}
                  style={{ width: `${metrics.cpuUsage}%` }}
                />
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <MemoryStick className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-medium">Memory Usage</span>
                </div>
                <span className="text-sm font-bold">{Math.round(metrics.memoryUsage)}%</span>
              </div>
              <div className="relative h-3 w-full overflow-hidden rounded-full bg-secondary">
                <div
                  className={`h-full transition-all duration-500 ${getProgressColor(metrics.memoryUsage)}`}
                  style={{ width: `${metrics.memoryUsage}%` }}
                />
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <HardDrive className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-medium">Disk Usage</span>
                </div>
                <span className="text-sm font-bold">{Math.round(metrics.diskUsage)}%</span>
              </div>
              <div className="relative h-3 w-full overflow-hidden rounded-full bg-secondary">
                <div
                  className={`h-full transition-all duration-500 ${getProgressColor(metrics.diskUsage)}`}
                  style={{ width: `${metrics.diskUsage}%` }}
                />
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Wifi className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-medium">Active Connections</span>
                </div>
                <span className="text-sm font-bold">{metrics.activeConnections}</span>
              </div>
              <p className="text-xs text-muted-foreground">
                Max capacity: 500 connections
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Evidence Gallery — Sprint-1 Operational Drill Results */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Sprint-1 Evidence Gallery
          </CardTitle>
          <CardDescription>
            Operational drill results and evidence documentation from P0 closure
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Ticket</TableHead>
                <TableHead>Drill</TableHead>
                <TableHead>Key Metric</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Timestamp (UTC)</TableHead>
                <TableHead>Evidence Path</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {[
                {
                  ticket: "P0-019",
                  drill: "OpenEHR Reconciliation & Rollback",
                  metric: "10/10 scenarios",
                  status: "PASS",
                  timestamp: "2026-02-16T16:27Z",
                  evidence: "docs/evidence/p0-019/",
                },
                {
                  ticket: "P0-025",
                  drill: "Incident Escalation Drill",
                  metric: "SEV-1 to SEV-4 exercised",
                  status: "PASS",
                  timestamp: "2026-02-16T16:34Z",
                  evidence: "docs/evidence/p0-025/",
                },
                {
                  ticket: "P0-026",
                  drill: "Backup Restore (PostgreSQL)",
                  metric: "RTO: 30.42s",
                  status: "PASS",
                  timestamp: "2026-02-16T16:31Z",
                  evidence: "docs/evidence/p0-026/",
                },
                {
                  ticket: "P0-027",
                  drill: "Failover Simulation (PostgreSQL)",
                  metric: "MTTR: 15.2s",
                  status: "PASS",
                  timestamp: "2026-02-16T16:33Z",
                  evidence: "docs/evidence/p0-027/",
                },
                {
                  ticket: "P0-028",
                  drill: "Pre-Pilot Signoff Matrix",
                  metric: "CONDITIONAL GO (6 signoffs)",
                  status: "PASS",
                  timestamp: "2026-02-16T17:00Z",
                  evidence: "docs/evidence/p0-028/",
                },
              ].map((row) => (
                <TableRow key={row.ticket}>
                  <TableCell>
                    <Badge variant="outline" className="font-mono text-xs">
                      {row.ticket}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-medium">{row.drill}</TableCell>
                  <TableCell className="text-sm">{row.metric}</TableCell>
                  <TableCell>
                    <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                      {row.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {row.timestamp}
                  </TableCell>
                  <TableCell className="text-xs font-mono text-muted-foreground max-w-[200px] truncate" title={row.evidence}>
                    {row.evidence}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <div className="mt-4 flex items-center gap-4 text-xs text-muted-foreground">
            <div className="flex items-center gap-1.5">
              <CheckCircle className="h-3.5 w-3.5 text-green-600" />
              <span>All 28 P0 items closed</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5" />
              <span>Signoff expiry: 2026-03-16</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Activity className="h-3.5 w-3.5" />
              <span>Posture: CONDITIONAL GO</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Action Items and Quick Actions */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Action Items Table (from API) */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Action Items</CardTitle>
            <CardDescription>
              Priority actions aggregated from all services
            </CardDescription>
          </CardHeader>
          <CardContent>
            {actionItems.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <CheckCircle className="h-8 w-8 mx-auto mb-2 text-green-500" />
                <p>No action items -- all systems nominal</p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Priority</TableHead>
                    <TableHead>Title</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead>Category</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {actionItems.map((item, idx) => (
                    <TableRow key={`${item.category}-${item.title}-${idx}`}>
                      <TableCell>
                        <Badge className={getPriorityColor(item.priority)}>
                          {item.priority}
                        </Badge>
                      </TableCell>
                      <TableCell className="font-medium">{item.title}</TableCell>
                      <TableCell className="max-w-[300px]">
                        <p className="text-sm truncate" title={item.description}>
                          {item.description}
                        </p>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{item.category}</Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* Quick Actions */}
        <Card>
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
            <CardDescription>Administrative operations</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Button
              variant="outline"
              className="w-full justify-start"
              onClick={handleClearCache}
              disabled={isClearing}
            >
              <Trash2 className={`mr-2 h-4 w-4 ${isClearing ? "animate-pulse" : ""}`} />
              {isClearing ? "Clearing Cache..." : "Clear All Caches"}
            </Button>

            <Button
              variant="outline"
              className="w-full justify-start"
              onClick={handleRestartServices}
              disabled={isRestarting}
            >
              <RotateCcw className={`mr-2 h-4 w-4 ${isRestarting ? "animate-spin" : ""}`} />
              {isRestarting ? "Restarting Services..." : "Restart Services"}
            </Button>

            <Button
              variant="outline"
              className="w-full justify-start"
              onClick={fetchDashboard}
              disabled={loading}
            >
              <RefreshCw className="mr-2 h-4 w-4" />
              Refresh Health Checks
            </Button>

            <Button variant="outline" className="w-full justify-start">
              <Activity className="mr-2 h-4 w-4" />
              View Full Metrics
            </Button>

            <div className="pt-4 border-t">
              {dashboardData?.metadata.generated_at && (
                <p className="text-xs text-muted-foreground mb-2">
                  Last refresh: {formatTimeAgo(dashboardData.metadata.generated_at)}
                </p>
              )}
              <p className="text-xs text-muted-foreground flex items-center">
                <Clock className="h-3 w-3 mr-1" />
                Time window: {dashboardData?.metadata.time_window ?? "24h"}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
