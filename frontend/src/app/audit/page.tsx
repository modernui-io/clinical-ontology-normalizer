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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Shield,
  Download,
  RefreshCw,
  Search,
  Filter,
  ChevronDown,
  ChevronUp,
  Eye,
  Edit,
  Trash,
  Upload,
  FileText,
  User,
  Calendar,
  AlertTriangle,
  CheckCircle,
  XCircle,
  ChevronLeft,
  ChevronRight,
  Loader2,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types matching backend response shapes
// ---------------------------------------------------------------------------

interface AuditLogEntry {
  id: string;
  timestamp: string;
  user_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  ip_address: string | null;
  user_agent: string | null;
  request_id: string | null;
  request_method: string | null;
  request_path: string | null;
  response_status: number | null;
  details: Record<string, unknown> | null;
  phi_accessed: boolean;
  patient_id: string | null;
  session_id: string | null;
  success: boolean;
  error_message: string | null;
  created_at: string;
}

interface AuditLogListResponse {
  logs: AuditLogEntry[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

interface AuditStats {
  total_logs: number;
  phi_access_count: number;
  unique_users: number;
  action_counts: Record<string, number>;
  resource_type_counts: Record<string, number>;
  period_start: string | null;
  period_end: string | null;
}

// ---------------------------------------------------------------------------
// Helper functions
// ---------------------------------------------------------------------------

const getActionIcon = (action: string) => {
  switch (action) {
    case "read":
      return <Eye className="h-4 w-4" />;
    case "create":
      return <Upload className="h-4 w-4" />;
    case "update":
      return <Edit className="h-4 w-4" />;
    case "delete":
      return <Trash className="h-4 w-4" />;
    case "export":
      return <Download className="h-4 w-4" />;
    case "search":
      return <Search className="h-4 w-4" />;
    case "login":
    case "logout":
      return <User className="h-4 w-4" />;
    default:
      return <FileText className="h-4 w-4" />;
  }
};

const getActionColor = (action: string): string => {
  switch (action) {
    case "read":
      return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200";
    case "create":
      return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
    case "update":
      return "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200";
    case "delete":
      return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
    case "export":
      return "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200";
    case "search":
      return "bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-200";
    case "login":
    case "logout":
      return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";
    default:
      return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";
  }
};

const getResourceTypeColor = (type: string): string => {
  switch (type) {
    case "patient":
      return "bg-blue-500 text-white";
    case "document":
      return "bg-green-500 text-white";
    case "clinical_fact":
      return "bg-amber-500 text-white";
    case "billing":
      return "bg-purple-500 text-white";
    case "knowledge_graph":
      return "bg-cyan-500 text-white";
    case "session":
      return "bg-gray-500 text-white";
    default:
      return "bg-gray-500 text-white";
  }
};

const formatTimestamp = (timestamp: string): string => {
  const date = new Date(timestamp);
  return date.toLocaleString();
};

const formatTimeAgo = (timestamp: string): string => {
  const now = new Date();
  const date = new Date(timestamp);
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
};

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function AuditLogPage() {
  // Data state
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [totalLogs, setTotalLogs] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [stats, setStats] = useState<AuditStats | null>(null);

  // Loading / error
  const [isLoading, setIsLoading] = useState(true);
  const [isStatsLoading, setIsStatsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Expanded row
  const [expandedLog, setExpandedLog] = useState<string | null>(null);

  // Filters
  const [userFilter, setUserFilter] = useState("");
  const [actionFilter, setActionFilter] = useState<string>("all");
  const [resourceFilter, setResourceFilter] = useState<string>("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [phiOnlyFilter, setPhiOnlyFilter] = useState(false);
  const [failedOnlyFilter, setFailedOnlyFilter] = useState(false);

  // Pagination (offset-based to match backend)
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 10;

  const actions = [
    "all",
    "read",
    "create",
    "update",
    "delete",
    "export",
    "search",
    "login",
    "logout",
  ];
  const resourceTypes = [
    "all",
    "patient",
    "document",
    "clinical_fact",
    "billing",
    "knowledge_graph",
    "session",
  ];

  // -------------------------------------------------------------------
  // Fetch audit logs
  // -------------------------------------------------------------------
  const fetchLogs = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      params.set("limit", String(pageSize));
      params.set("offset", String((currentPage - 1) * pageSize));

      if (userFilter.trim()) {
        params.set("user_id", userFilter.trim());
      }
      if (actionFilter !== "all") {
        params.set("action", actionFilter);
      }
      if (resourceFilter !== "all") {
        params.set("resource_type", resourceFilter);
      }
      if (dateFrom) {
        // Convert date input (YYYY-MM-DD) to ISO datetime
        params.set("start_date", new Date(dateFrom).toISOString());
      }
      if (dateTo) {
        // Set to end of day
        const endDate = new Date(dateTo);
        endDate.setHours(23, 59, 59, 999);
        params.set("end_date", endDate.toISOString());
      }
      if (phiOnlyFilter) {
        params.set("phi_only", "true");
      }

      const res = await fetch(`/api/audit/logs?${params.toString()}`);
      if (!res.ok) {
        const body = await res.text();
        throw new Error(
          `Failed to fetch audit logs (${res.status}): ${body}`
        );
      }

      const data: AuditLogListResponse = await res.json();

      // Client-side filter for failed-only (backend doesn't have this param)
      let filteredLogs = data.logs;
      if (failedOnlyFilter) {
        filteredLogs = filteredLogs.filter((log) => !log.success);
      }

      setLogs(filteredLogs);
      setTotalLogs(data.total);
      setHasMore(data.has_more);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setLogs([]);
      setTotalLogs(0);
    } finally {
      setIsLoading(false);
    }
  }, [
    currentPage,
    pageSize,
    userFilter,
    actionFilter,
    resourceFilter,
    dateFrom,
    dateTo,
    phiOnlyFilter,
    failedOnlyFilter,
  ]);

  // -------------------------------------------------------------------
  // Fetch audit stats
  // -------------------------------------------------------------------
  const fetchStats = useCallback(async () => {
    setIsStatsLoading(true);
    try {
      const res = await fetch("/api/audit/stats");
      if (!res.ok) {
        // Stats are non-critical; silently ignore failures
        return;
      }
      const data: AuditStats = await res.json();
      setStats(data);
    } catch {
      // Stats failure is non-critical
    } finally {
      setIsStatsLoading(false);
    }
  }, []);

  // -------------------------------------------------------------------
  // Initial load + filter/page changes
  // -------------------------------------------------------------------
  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  // -------------------------------------------------------------------
  // Derived
  // -------------------------------------------------------------------
  const totalPages = Math.max(1, Math.ceil(totalLogs / pageSize));

  // -------------------------------------------------------------------
  // Actions
  // -------------------------------------------------------------------
  const refreshData = async () => {
    await Promise.all([fetchLogs(), fetchStats()]);
  };

  const exportToCSV = () => {
    const headers = [
      "Timestamp",
      "User ID",
      "Action",
      "Resource Type",
      "Resource ID",
      "Patient ID",
      "IP Address",
      "Status",
      "PHI Accessed",
      "Success",
      "Error",
    ];
    const rows = logs.map((log) => [
      log.timestamp,
      log.user_id || "",
      log.action,
      log.resource_type,
      log.resource_id || "",
      log.patient_id || "",
      log.ip_address || "",
      log.response_status ?? "",
      log.phi_accessed ? "Yes" : "No",
      log.success ? "Yes" : "No",
      log.error_message || "",
    ]);

    const csv = [headers, ...rows].map((row) => row.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `audit_log_${new Date().toISOString().split("T")[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const clearFilters = () => {
    setUserFilter("");
    setActionFilter("all");
    setResourceFilter("all");
    setDateFrom("");
    setDateTo("");
    setPhiOnlyFilter(false);
    setFailedOnlyFilter(false);
    setCurrentPage(1);
  };

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Shield className="h-6 w-6" />
            Audit Log
          </h1>
          <p className="text-muted-foreground">
            HIPAA-compliant audit trail for all system access and data
            modifications
          </p>
        </div>
        <div className="flex gap-2">
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
          <Button variant="outline" size="sm" onClick={exportToCSV}>
            <Download className="mr-2 h-4 w-4" />
            Export CSV
          </Button>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <Card className="border-red-300 bg-red-50 dark:bg-red-950/30">
          <CardContent className="pt-4">
            <div className="flex items-center gap-2 text-red-700 dark:text-red-400">
              <AlertTriangle className="h-5 w-5 flex-shrink-0" />
              <p className="text-sm">{error}</p>
              <Button
                variant="ghost"
                size="sm"
                className="ml-auto"
                onClick={refreshData}
              >
                Retry
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Summary Stats */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Events</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {isStatsLoading ? (
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            ) : (
              <>
                <div className="text-2xl font-bold">
                  {(stats?.total_logs ?? 0).toLocaleString()}
                </div>
                <p className="text-xs text-muted-foreground">All time</p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">PHI Access</CardTitle>
            <AlertTriangle className="h-4 w-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            {isStatsLoading ? (
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            ) : (
              <>
                <div className="text-2xl font-bold text-amber-600">
                  {(stats?.phi_access_count ?? 0).toLocaleString()}
                </div>
                <p className="text-xs text-muted-foreground">
                  {stats && stats.total_logs > 0
                    ? `${((stats.phi_access_count / stats.total_logs) * 100).toFixed(1)}% of events`
                    : "No events"}
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              Actions Breakdown
            </CardTitle>
            <XCircle className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            {isStatsLoading ? (
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            ) : (
              <>
                <div className="text-2xl font-bold text-red-600">
                  {Object.keys(stats?.action_counts ?? {}).length}
                </div>
                <p className="text-xs text-muted-foreground">
                  Distinct action types
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Unique Users</CardTitle>
            <User className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {isStatsLoading ? (
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            ) : (
              <>
                <div className="text-2xl font-bold">
                  {stats?.unique_users ?? 0}
                </div>
                <p className="text-xs text-muted-foreground">Active users</p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              Current Results
            </CardTitle>
            <Calendar className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            ) : (
              <>
                <div className="text-2xl font-bold">
                  {totalLogs.toLocaleString()}
                </div>
                <p className="text-xs text-muted-foreground">
                  Matching current filters
                </p>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Filter className="h-4 w-4" />
              Filters
            </CardTitle>
            <Button variant="ghost" size="sm" onClick={clearFilters}>
              Clear All
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
            <div className="space-y-2">
              <Label htmlFor="user-filter">User</Label>
              <Input
                id="user-filter"
                placeholder="Search by user ID..."
                value={userFilter}
                onChange={(e) => {
                  setUserFilter(e.target.value);
                  setCurrentPage(1);
                }}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="action-filter">Action</Label>
              <select
                id="action-filter"
                value={actionFilter}
                onChange={(e) => {
                  setActionFilter(e.target.value);
                  setCurrentPage(1);
                }}
                className="w-full h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
              >
                {actions.map((action) => (
                  <option key={action} value={action}>
                    {action === "all" ? "All Actions" : action}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="resource-filter">Resource Type</Label>
              <select
                id="resource-filter"
                value={resourceFilter}
                onChange={(e) => {
                  setResourceFilter(e.target.value);
                  setCurrentPage(1);
                }}
                className="w-full h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
              >
                {resourceTypes.map((type) => (
                  <option key={type} value={type}>
                    {type === "all" ? "All Resources" : type.replace("_", " ")}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="date-from">From Date</Label>
              <Input
                id="date-from"
                type="date"
                value={dateFrom}
                onChange={(e) => {
                  setDateFrom(e.target.value);
                  setCurrentPage(1);
                }}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="date-to">To Date</Label>
              <Input
                id="date-to"
                type="date"
                value={dateTo}
                onChange={(e) => {
                  setDateTo(e.target.value);
                  setCurrentPage(1);
                }}
              />
            </div>

            <div className="space-y-2">
              <Label>Quick Filters</Label>
              <div className="flex gap-2">
                <Button
                  variant={phiOnlyFilter ? "default" : "outline"}
                  size="sm"
                  onClick={() => {
                    setPhiOnlyFilter(!phiOnlyFilter);
                    setCurrentPage(1);
                  }}
                >
                  PHI Only
                </Button>
                <Button
                  variant={failedOnlyFilter ? "default" : "outline"}
                  size="sm"
                  onClick={() => {
                    setFailedOnlyFilter(!failedOnlyFilter);
                    setCurrentPage(1);
                  }}
                >
                  Failed Only
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Audit Log Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Audit Log Entries</CardTitle>
              <CardDescription>
                {totalLogs.toLocaleString()} entries found
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-16">
              <div className="flex flex-col items-center gap-3">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                <p className="text-sm text-muted-foreground">
                  Loading audit logs...
                </p>
              </div>
            </div>
          ) : logs.length === 0 ? (
            <div className="flex items-center justify-center py-16">
              <div className="flex flex-col items-center gap-3 text-muted-foreground">
                <FileText className="h-8 w-8" />
                <p className="text-sm">
                  {error
                    ? "Failed to load audit logs."
                    : "No audit log entries match the current filters."}
                </p>
              </div>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[50px]"></TableHead>
                  <TableHead>Timestamp</TableHead>
                  <TableHead>User</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Resource</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>PHI</TableHead>
                  <TableHead className="w-[50px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {logs.map((log) => (
                  <>
                    <TableRow
                      key={log.id}
                      className={`cursor-pointer hover:bg-muted/50 ${
                        !log.success ? "bg-red-50 dark:bg-red-950/20" : ""
                      }`}
                      onClick={() =>
                        setExpandedLog(
                          expandedLog === log.id ? null : log.id
                        )
                      }
                    >
                      <TableCell>
                        <div className="flex items-center justify-center">
                          {log.success ? (
                            <CheckCircle className="h-4 w-4 text-green-600" />
                          ) : (
                            <XCircle className="h-4 w-4 text-red-600" />
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div>
                          <div className="font-medium text-sm">
                            {formatTimestamp(log.timestamp)}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {formatTimeAgo(log.timestamp)}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div>
                          <div className="font-medium">
                            {log.user_id || "Unknown"}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {log.ip_address || "-"}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge
                          className={`gap-1 ${getActionColor(log.action)}`}
                        >
                          {getActionIcon(log.action)}
                          {log.action}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Badge
                            className={getResourceTypeColor(
                              log.resource_type
                            )}
                          >
                            {log.resource_type.replace("_", " ")}
                          </Badge>
                          {log.resource_id && (
                            <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                              {log.resource_id}
                            </code>
                          )}
                        </div>
                        {log.patient_id && (
                          <div className="text-xs text-muted-foreground mt-1">
                            Patient: {log.patient_id}
                          </div>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            log.response_status != null &&
                            log.response_status < 400
                              ? "outline"
                              : "destructive"
                          }
                        >
                          {log.response_status ?? "-"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {log.phi_accessed ? (
                          <Badge className="bg-amber-500 text-white">
                            PHI
                          </Badge>
                        ) : (
                          <span className="text-muted-foreground text-sm">
                            -
                          </span>
                        )}
                      </TableCell>
                      <TableCell>
                        {expandedLog === log.id ? (
                          <ChevronUp className="h-4 w-4" />
                        ) : (
                          <ChevronDown className="h-4 w-4" />
                        )}
                      </TableCell>
                    </TableRow>
                    {expandedLog === log.id && (
                      <TableRow key={`${log.id}-detail`}>
                        <TableCell colSpan={8} className="bg-muted/20">
                          <div className="p-4 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                            <div>
                              <h4 className="text-sm font-medium mb-2">
                                Request Details
                              </h4>
                              <div className="space-y-1 text-sm">
                                <div className="flex justify-between">
                                  <span className="text-muted-foreground">
                                    Method:
                                  </span>
                                  <code className="bg-muted px-1 rounded">
                                    {log.request_method || "-"}
                                  </code>
                                </div>
                                <div className="flex justify-between">
                                  <span className="text-muted-foreground">
                                    Path:
                                  </span>
                                  <code className="bg-muted px-1 rounded text-xs">
                                    {log.request_path || "-"}
                                  </code>
                                </div>
                                {log.request_id && (
                                  <div className="flex justify-between">
                                    <span className="text-muted-foreground">
                                      Request ID:
                                    </span>
                                    <code className="bg-muted px-1 rounded text-xs">
                                      {log.request_id}
                                    </code>
                                  </div>
                                )}
                              </div>
                            </div>
                            <div>
                              <h4 className="text-sm font-medium mb-2">
                                User Agent
                              </h4>
                              <p className="text-sm text-muted-foreground break-all">
                                {log.user_agent || "Not available"}
                              </p>
                            </div>
                            <div>
                              <h4 className="text-sm font-medium mb-2">
                                User Info
                              </h4>
                              <div className="space-y-1 text-sm">
                                <div className="flex justify-between">
                                  <span className="text-muted-foreground">
                                    User ID:
                                  </span>
                                  <span>{log.user_id || "-"}</span>
                                </div>
                                <div className="flex justify-between">
                                  <span className="text-muted-foreground">
                                    IP Address:
                                  </span>
                                  <span>{log.ip_address || "-"}</span>
                                </div>
                                {log.session_id && (
                                  <div className="flex justify-between">
                                    <span className="text-muted-foreground">
                                      Session:
                                    </span>
                                    <span className="text-xs">
                                      {log.session_id}
                                    </span>
                                  </div>
                                )}
                              </div>
                            </div>
                            <div>
                              <h4 className="text-sm font-medium mb-2">
                                Additional Details
                              </h4>
                              {log.error_message && (
                                <div className="text-sm text-red-600 mb-2">
                                  Error: {log.error_message}
                                </div>
                              )}
                              {log.details && (
                                <pre className="text-xs bg-muted p-2 rounded overflow-auto max-h-24">
                                  {JSON.stringify(log.details, null, 2)}
                                </pre>
                              )}
                              {!log.error_message && !log.details && (
                                <p className="text-sm text-muted-foreground">
                                  No additional details
                                </p>
                              )}
                            </div>
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                  </>
                ))}
              </TableBody>
            </Table>
          )}

          {/* Pagination */}
          {!isLoading && totalPages > 1 && (
            <div className="flex items-center justify-between mt-4">
              <p className="text-sm text-muted-foreground">
                Showing {(currentPage - 1) * pageSize + 1} to{" "}
                {Math.min(currentPage * pageSize, totalLogs)} of{" "}
                {totalLogs} entries
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage(currentPage - 1)}
                  disabled={currentPage === 1}
                >
                  <ChevronLeft className="h-4 w-4" />
                  Previous
                </Button>
                <div className="flex items-center gap-1">
                  {Array.from(
                    { length: Math.min(5, totalPages) },
                    (_, i) => {
                      let pageNum = i + 1;
                      if (totalPages > 5) {
                        if (currentPage <= 3) {
                          pageNum = i + 1;
                        } else if (currentPage >= totalPages - 2) {
                          pageNum = totalPages - 4 + i;
                        } else {
                          pageNum = currentPage - 2 + i;
                        }
                      }
                      return (
                        <Button
                          key={pageNum}
                          variant={
                            currentPage === pageNum ? "default" : "outline"
                          }
                          size="sm"
                          onClick={() => setCurrentPage(pageNum)}
                          className="w-8"
                        >
                          {pageNum}
                        </Button>
                      );
                    }
                  )}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage(currentPage + 1)}
                  disabled={currentPage === totalPages}
                >
                  Next
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
