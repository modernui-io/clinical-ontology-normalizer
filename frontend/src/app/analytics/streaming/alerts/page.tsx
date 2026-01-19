"use client";

import { useState, useEffect, useCallback } from "react";
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
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  Bell,
  Check,
  CheckCheck,
  Clock,
  Filter,
  Info,
  Loader2,
  RefreshCw,
  Search,
  XCircle,
} from "lucide-react";

// =============================================================================
// Types
// =============================================================================

interface StreamingAlert {
  alert_id: string;
  alert_type: string;
  severity: "critical" | "warning" | "info";
  title: string;
  message: string;
  source: string;
  metric_value: number | null;
  threshold_value: number | null;
  created_at: string;
  acknowledged: boolean;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  resolved: boolean;
  resolved_at: string | null;
  metadata: Record<string, unknown>;
}

interface AlertsResponse {
  alerts: StreamingAlert[];
  total_alerts: number;
  active_alerts: number;
  critical_count: number;
}

// =============================================================================
// Mock Data
// =============================================================================

function generateMockAlerts(): StreamingAlert[] {
  const alertTypes = [
    { type: "high_latency", title: "High Processing Latency", severity: "warning" as const },
    { type: "high_error_rate", title: "High Error Rate", severity: "critical" as const },
    { type: "consumer_lag", title: "Consumer Lag Increasing", severity: "info" as const },
    { type: "schema_drift", title: "Schema Drift Detected", severity: "warning" as const },
    { type: "validation_error", title: "Validation Errors Spike", severity: "warning" as const },
    { type: "throughput_drop", title: "Throughput Drop", severity: "critical" as const },
    { type: "dead_letter_spike", title: "Dead Letter Queue Growing", severity: "warning" as const },
    { type: "connection_lost", title: "Kafka Connection Lost", severity: "critical" as const },
  ];

  const now = Date.now();
  return Array.from({ length: 15 }, (_, i) => {
    const alertConfig = alertTypes[i % alertTypes.length];
    const createdAt = new Date(now - i * 300000 - Math.random() * 300000);
    const acknowledged = i > 5 ? Math.random() > 0.5 : false;
    const resolved = acknowledged && Math.random() > 0.7;

    return {
      alert_id: `alert-${i + 1}-${Date.now()}`,
      alert_type: alertConfig.type,
      severity: alertConfig.severity,
      title: alertConfig.title,
      message: `${alertConfig.title} - Current value exceeds threshold by ${(Math.random() * 50 + 10).toFixed(1)}%`,
      source: "streaming_aggregation",
      metric_value: Math.random() * 100,
      threshold_value: Math.random() * 50,
      created_at: createdAt.toISOString(),
      acknowledged,
      acknowledged_at: acknowledged ? new Date(createdAt.getTime() + 60000).toISOString() : null,
      acknowledged_by: acknowledged ? "demo-user" : null,
      resolved,
      resolved_at: resolved ? new Date(createdAt.getTime() + 120000).toISOString() : null,
      metadata: {},
    };
  });
}

// =============================================================================
// Components
// =============================================================================

function SeverityBadge({ severity }: { severity: string }) {
  switch (severity) {
    case "critical":
      return (
        <Badge variant="destructive" className="gap-1">
          <AlertCircle className="h-3 w-3" />
          Critical
        </Badge>
      );
    case "warning":
      return (
        <Badge variant="secondary" className="gap-1 bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
          <AlertTriangle className="h-3 w-3" />
          Warning
        </Badge>
      );
    case "info":
    default:
      return (
        <Badge variant="outline" className="gap-1">
          <Info className="h-3 w-3" />
          Info
        </Badge>
      );
  }
}

function AlertStatusBadge({ alert }: { alert: StreamingAlert }) {
  if (alert.resolved) {
    return (
      <Badge variant="outline" className="gap-1 text-green-600 border-green-300">
        <Check className="h-3 w-3" />
        Resolved
      </Badge>
    );
  }
  if (alert.acknowledged) {
    return (
      <Badge variant="outline" className="gap-1 text-blue-600 border-blue-300">
        <CheckCheck className="h-3 w-3" />
        Acknowledged
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="gap-1 text-orange-600 border-orange-300">
      <Clock className="h-3 w-3" />
      Active
    </Badge>
  );
}

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins} min ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? "s" : ""} ago`;
  if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? "s" : ""} ago`;
  return date.toLocaleDateString();
}

// =============================================================================
// Main Page Component
// =============================================================================

export default function StreamingAlertsPage() {
  const [alerts, setAlerts] = useState<StreamingAlert[]>([]);
  const [filteredAlerts, setFilteredAlerts] = useState<StreamingAlert[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isAcknowledging, setIsAcknowledging] = useState<string | null>(null);
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("active");
  const [searchQuery, setSearchQuery] = useState("");
  const [stats, setStats] = useState({
    total: 0,
    active: 0,
    critical: 0,
  });

  // Fetch alerts
  const fetchAlerts = useCallback(async () => {
    try {
      setIsLoading(true);
      const response = await fetch(
        `http://localhost:8000/api/v1/streaming/alerts?include_acknowledged=${statusFilter !== "active"}&limit=100`
      );

      if (response.ok) {
        const data: AlertsResponse = await response.json();
        setAlerts(data.alerts);
        setStats({
          total: data.total_alerts,
          active: data.active_alerts,
          critical: data.critical_count,
        });
      } else {
        throw new Error("Failed to fetch alerts");
      }
    } catch (error) {
      console.error("Failed to fetch alerts:", error);
      // Use mock data
      const mockAlerts = generateMockAlerts();
      setAlerts(mockAlerts);
      setStats({
        total: mockAlerts.length,
        active: mockAlerts.filter((a) => !a.acknowledged).length,
        critical: mockAlerts.filter((a) => a.severity === "critical" && !a.acknowledged).length,
      });
    } finally {
      setIsLoading(false);
    }
  }, [statusFilter]);

  // Apply filters
  useEffect(() => {
    let filtered = [...alerts];

    // Severity filter
    if (severityFilter !== "all") {
      filtered = filtered.filter((a) => a.severity === severityFilter);
    }

    // Status filter
    if (statusFilter === "active") {
      filtered = filtered.filter((a) => !a.acknowledged && !a.resolved);
    } else if (statusFilter === "acknowledged") {
      filtered = filtered.filter((a) => a.acknowledged && !a.resolved);
    } else if (statusFilter === "resolved") {
      filtered = filtered.filter((a) => a.resolved);
    }

    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (a) =>
          a.title.toLowerCase().includes(query) ||
          a.message.toLowerCase().includes(query) ||
          a.alert_type.toLowerCase().includes(query)
      );
    }

    // Sort by created_at descending
    filtered.sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );

    setFilteredAlerts(filtered);
  }, [alerts, severityFilter, statusFilter, searchQuery]);

  // Initial fetch
  useEffect(() => {
    fetchAlerts();

    // Refresh every 30 seconds
    const interval = setInterval(fetchAlerts, 30000);
    return () => clearInterval(interval);
  }, [fetchAlerts]);

  // Acknowledge alert
  const acknowledgeAlert = async (alertId: string) => {
    setIsAcknowledging(alertId);
    try {
      const response = await fetch(
        `http://localhost:8000/api/v1/streaming/alerts/${alertId}/acknowledge`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ acknowledged_by: "demo-user" }),
        }
      );

      if (response.ok) {
        // Update local state
        setAlerts((prev) =>
          prev.map((a) =>
            a.alert_id === alertId
              ? {
                  ...a,
                  acknowledged: true,
                  acknowledged_at: new Date().toISOString(),
                  acknowledged_by: "demo-user",
                }
              : a
          )
        );
        setStats((prev) => ({
          ...prev,
          active: Math.max(0, prev.active - 1),
        }));
      }
    } catch (error) {
      console.error("Failed to acknowledge alert:", error);
      // Update locally anyway for demo
      setAlerts((prev) =>
        prev.map((a) =>
          a.alert_id === alertId
            ? {
                ...a,
                acknowledged: true,
                acknowledged_at: new Date().toISOString(),
                acknowledged_by: "demo-user",
              }
            : a
        )
      );
    } finally {
      setIsAcknowledging(null);
    }
  };

  // Acknowledge all active alerts
  const acknowledgeAllActive = async () => {
    const activeAlerts = alerts.filter((a) => !a.acknowledged && !a.resolved);
    for (const alert of activeAlerts) {
      await acknowledgeAlert(alert.alert_id);
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <Link href="/analytics/streaming">
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <ArrowLeft className="h-4 w-4" />
              </Button>
            </Link>
            <h1 className="text-2xl font-bold tracking-tight">
              Streaming Alert Console
            </h1>
          </div>
          <p className="text-muted-foreground">
            Monitor and manage real-time pipeline alerts
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchAlerts}
            disabled={isLoading}
          >
            <RefreshCw
              className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
          {stats.active > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={acknowledgeAllActive}
            >
              <CheckCheck className="mr-2 h-4 w-4" />
              Acknowledge All
            </Button>
          )}
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Active Alerts</CardTitle>
            <Bell className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.active}</div>
            <p className="text-xs text-muted-foreground">
              Requiring attention
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Critical</CardTitle>
            <AlertCircle className="h-4 w-4 text-destructive" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-destructive">
              {stats.critical}
            </div>
            <p className="text-xs text-muted-foreground">
              High priority issues
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Alerts</CardTitle>
            <AlertTriangle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total}</div>
            <p className="text-xs text-muted-foreground">
              In the last 24 hours
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Filter className="h-4 w-4" />
            Filters
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-4">
            {/* Search */}
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search alerts..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>

            {/* Severity Filter */}
            <Select value={severityFilter} onValueChange={setSeverityFilter}>
              <SelectTrigger className="w-[150px]">
                <SelectValue placeholder="Severity" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Severities</SelectItem>
                <SelectItem value="critical">Critical</SelectItem>
                <SelectItem value="warning">Warning</SelectItem>
                <SelectItem value="info">Info</SelectItem>
              </SelectContent>
            </Select>

            {/* Status Filter */}
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[150px]">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="acknowledged">Acknowledged</SelectItem>
                <SelectItem value="resolved">Resolved</SelectItem>
                <SelectItem value="all">All</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Alerts Table */}
      <Card>
        <CardHeader>
          <CardTitle>Alerts</CardTitle>
          <CardDescription>
            {filteredAlerts.length} alert{filteredAlerts.length !== 1 ? "s" : ""}{" "}
            matching filters
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : filteredAlerts.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Bell className="h-12 w-12 text-muted-foreground/50" />
              <p className="mt-4 text-lg font-medium">No alerts found</p>
              <p className="text-sm text-muted-foreground">
                {statusFilter === "active"
                  ? "No active alerts at this time"
                  : "No alerts match your current filters"}
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[100px]">Severity</TableHead>
                  <TableHead>Alert</TableHead>
                  <TableHead className="w-[120px]">Status</TableHead>
                  <TableHead className="w-[140px]">Time</TableHead>
                  <TableHead className="w-[100px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredAlerts.map((alert) => (
                  <TableRow key={alert.alert_id}>
                    <TableCell>
                      <SeverityBadge severity={alert.severity} />
                    </TableCell>
                    <TableCell>
                      <div className="space-y-1">
                        <p className="font-medium">{alert.title}</p>
                        <p className="text-sm text-muted-foreground line-clamp-1">
                          {alert.message}
                        </p>
                        {alert.metric_value !== null && (
                          <p className="text-xs text-muted-foreground">
                            Value: {alert.metric_value.toFixed(1)}
                            {alert.threshold_value !== null &&
                              ` (threshold: ${alert.threshold_value.toFixed(1)})`}
                          </p>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <AlertStatusBadge alert={alert} />
                      {alert.acknowledged_by && (
                        <p className="text-xs text-muted-foreground mt-1">
                          by {alert.acknowledged_by}
                        </p>
                      )}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatRelativeTime(alert.created_at)}
                    </TableCell>
                    <TableCell>
                      {!alert.acknowledged && !alert.resolved && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => acknowledgeAlert(alert.alert_id)}
                          disabled={isAcknowledging === alert.alert_id}
                        >
                          {isAcknowledging === alert.alert_id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <>
                              <Check className="h-4 w-4 mr-1" />
                              Ack
                            </>
                          )}
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Alert History Summary */}
      <Card>
        <CardHeader>
          <CardTitle>Alert History Summary</CardTitle>
          <CardDescription>
            Distribution of alerts by type
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-4">
            {[
              { type: "high_latency", label: "High Latency", icon: Clock },
              { type: "high_error_rate", label: "High Error Rate", icon: AlertCircle },
              { type: "consumer_lag", label: "Consumer Lag", icon: AlertTriangle },
              { type: "schema_drift", label: "Schema Drift", icon: XCircle },
            ].map((alertType) => {
              const count = alerts.filter(
                (a) => a.alert_type === alertType.type
              ).length;
              const Icon = alertType.icon;

              return (
                <div
                  key={alertType.type}
                  className="flex items-center gap-3 p-3 rounded-lg border"
                >
                  <Icon className="h-5 w-5 text-muted-foreground" />
                  <div>
                    <p className="text-lg font-bold">{count}</p>
                    <p className="text-xs text-muted-foreground">
                      {alertType.label}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
