"use client";

import { useState } from "react";
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
  Clock,
  AlertTriangle,
  CheckCircle,
  XCircle,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

// Types
interface AuditLogEntry {
  id: string;
  timestamp: string;
  userId: string;
  userName: string;
  action: "read" | "create" | "update" | "delete" | "export" | "search" | "login" | "logout";
  resourceType: string;
  resourceId: string | null;
  patientId: string | null;
  ipAddress: string;
  userAgent: string;
  requestMethod: string;
  requestPath: string;
  responseStatus: number;
  phiAccessed: boolean;
  success: boolean;
  errorMessage: string | null;
  details: Record<string, unknown> | null;
}

interface AuditStats {
  totalEvents: number;
  phiAccessEvents: number;
  failedEvents: number;
  uniqueUsers: number;
  eventsToday: number;
}

// Mock Data
const mockAuditLogs: AuditLogEntry[] = [
  {
    id: "audit-001",
    timestamp: "2026-01-19T14:32:15Z",
    userId: "user-001",
    userName: "Dr. John Smith",
    action: "read",
    resourceType: "patient",
    resourceId: "P001",
    patientId: "P001",
    ipAddress: "192.168.1.100",
    userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    requestMethod: "GET",
    requestPath: "/api/patients/P001",
    responseStatus: 200,
    phiAccessed: true,
    success: true,
    errorMessage: null,
    details: { fields_accessed: ["name", "dob", "mrn", "diagnoses"] },
  },
  {
    id: "audit-002",
    timestamp: "2026-01-19T14:28:45Z",
    userId: "user-002",
    userName: "Mary Johnson",
    action: "export",
    resourceType: "document",
    resourceId: null,
    patientId: "P003",
    ipAddress: "192.168.1.105",
    userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    requestMethod: "POST",
    requestPath: "/api/documents/export",
    responseStatus: 200,
    phiAccessed: true,
    success: true,
    errorMessage: null,
    details: { export_format: "pdf", document_count: 5 },
  },
  {
    id: "audit-003",
    timestamp: "2026-01-19T14:25:10Z",
    userId: "user-001",
    userName: "Dr. John Smith",
    action: "update",
    resourceType: "clinical_fact",
    resourceId: "fact-123",
    patientId: "P001",
    ipAddress: "192.168.1.100",
    userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    requestMethod: "PUT",
    requestPath: "/api/facts/fact-123",
    responseStatus: 200,
    phiAccessed: true,
    success: true,
    errorMessage: null,
    details: { changed_fields: ["assertion", "confidence"] },
  },
  {
    id: "audit-004",
    timestamp: "2026-01-19T14:20:30Z",
    userId: "user-003",
    userName: "Bob Williams",
    action: "delete",
    resourceType: "document",
    resourceId: "doc-456",
    patientId: "P008",
    ipAddress: "192.168.1.110",
    userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    requestMethod: "DELETE",
    requestPath: "/api/documents/doc-456",
    responseStatus: 403,
    phiAccessed: false,
    success: false,
    errorMessage: "Permission denied: insufficient privileges",
    details: null,
  },
  {
    id: "audit-005",
    timestamp: "2026-01-19T14:15:00Z",
    userId: "user-004",
    userName: "Sarah Davis",
    action: "search",
    resourceType: "patient",
    resourceId: null,
    patientId: null,
    ipAddress: "192.168.1.115",
    userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    requestMethod: "POST",
    requestPath: "/api/patients/search",
    responseStatus: 200,
    phiAccessed: true,
    success: true,
    errorMessage: null,
    details: { search_query: "diabetes medication", result_count: 45 },
  },
  {
    id: "audit-006",
    timestamp: "2026-01-19T14:10:22Z",
    userId: "user-005",
    userName: "Admin User",
    action: "login",
    resourceType: "session",
    resourceId: "session-789",
    patientId: null,
    ipAddress: "192.168.1.120",
    userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    requestMethod: "POST",
    requestPath: "/api/auth/login",
    responseStatus: 200,
    phiAccessed: false,
    success: true,
    errorMessage: null,
    details: { auth_method: "password", mfa_used: true },
  },
  {
    id: "audit-007",
    timestamp: "2026-01-19T14:05:15Z",
    userId: "user-002",
    userName: "Mary Johnson",
    action: "create",
    resourceType: "document",
    resourceId: "doc-789",
    patientId: "P012",
    ipAddress: "192.168.1.105",
    userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    requestMethod: "POST",
    requestPath: "/api/documents",
    responseStatus: 201,
    phiAccessed: true,
    success: true,
    errorMessage: null,
    details: { note_type: "progress_note", size_bytes: 4520 },
  },
  {
    id: "audit-008",
    timestamp: "2026-01-19T13:55:40Z",
    userId: "user-006",
    userName: "Unknown",
    action: "login",
    resourceType: "session",
    resourceId: null,
    patientId: null,
    ipAddress: "203.45.67.89",
    userAgent: "curl/7.68.0",
    requestMethod: "POST",
    requestPath: "/api/auth/login",
    responseStatus: 401,
    phiAccessed: false,
    success: false,
    errorMessage: "Invalid credentials",
    details: { attempts: 3, username: "admin@test.com" },
  },
  {
    id: "audit-009",
    timestamp: "2026-01-19T13:50:10Z",
    userId: "user-001",
    userName: "Dr. John Smith",
    action: "read",
    resourceType: "knowledge_graph",
    resourceId: "graph-P001",
    patientId: "P001",
    ipAddress: "192.168.1.100",
    userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    requestMethod: "GET",
    requestPath: "/api/patients/P001/graph",
    responseStatus: 200,
    phiAccessed: true,
    success: true,
    errorMessage: null,
    details: { node_count: 45, edge_count: 78 },
  },
  {
    id: "audit-010",
    timestamp: "2026-01-19T13:45:30Z",
    userId: "user-002",
    userName: "Mary Johnson",
    action: "read",
    resourceType: "billing",
    resourceId: "hcc-analysis-001",
    patientId: "P003",
    ipAddress: "192.168.1.105",
    userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    requestMethod: "GET",
    requestPath: "/api/billing/hcc/P003",
    responseStatus: 200,
    phiAccessed: true,
    success: true,
    errorMessage: null,
    details: { hcc_codes: ["HCC85", "HCC37"], estimated_raf: 0.625 },
  },
];

const mockStats: AuditStats = {
  totalEvents: 15482,
  phiAccessEvents: 8956,
  failedEvents: 234,
  uniqueUsers: 42,
  eventsToday: 1256,
};

// Helper functions
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

export default function AuditLogPage() {
  const [logs] = useState<AuditLogEntry[]>(mockAuditLogs);
  const [stats] = useState<AuditStats>(mockStats);
  const [isLoading, setIsLoading] = useState(false);
  const [expandedLog, setExpandedLog] = useState<string | null>(null);

  // Filters
  const [userFilter, setUserFilter] = useState("");
  const [actionFilter, setActionFilter] = useState<string>("all");
  const [resourceFilter, setResourceFilter] = useState<string>("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [phiOnlyFilter, setPhiOnlyFilter] = useState(false);
  const [failedOnlyFilter, setFailedOnlyFilter] = useState(false);

  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 10;

  const actions = ["all", "read", "create", "update", "delete", "export", "search", "login", "logout"];
  const resourceTypes = [
    "all",
    "patient",
    "document",
    "clinical_fact",
    "billing",
    "knowledge_graph",
    "session",
  ];

  // Filter logs
  const filteredLogs = logs.filter((log) => {
    const matchesUser =
      userFilter === "" ||
      log.userName.toLowerCase().includes(userFilter.toLowerCase()) ||
      log.userId.toLowerCase().includes(userFilter.toLowerCase());
    const matchesAction = actionFilter === "all" || log.action === actionFilter;
    const matchesResource =
      resourceFilter === "all" || log.resourceType === resourceFilter;
    const matchesPhi = !phiOnlyFilter || log.phiAccessed;
    const matchesFailed = !failedOnlyFilter || !log.success;

    let matchesDateRange = true;
    if (dateFrom) {
      matchesDateRange =
        matchesDateRange && new Date(log.timestamp) >= new Date(dateFrom);
    }
    if (dateTo) {
      matchesDateRange =
        matchesDateRange && new Date(log.timestamp) <= new Date(dateTo);
    }

    return (
      matchesUser &&
      matchesAction &&
      matchesResource &&
      matchesPhi &&
      matchesFailed &&
      matchesDateRange
    );
  });

  // Pagination
  const totalPages = Math.ceil(filteredLogs.length / pageSize);
  const paginatedLogs = filteredLogs.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize
  );

  const refreshData = async () => {
    setIsLoading(true);
    await new Promise((resolve) => setTimeout(resolve, 1000));
    setIsLoading(false);
  };

  const exportToCSV = () => {
    const headers = [
      "Timestamp",
      "User",
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
    const rows = filteredLogs.map((log) => [
      log.timestamp,
      log.userName,
      log.action,
      log.resourceType,
      log.resourceId || "",
      log.patientId || "",
      log.ipAddress,
      log.responseStatus,
      log.phiAccessed ? "Yes" : "No",
      log.success ? "Yes" : "No",
      log.errorMessage || "",
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
            HIPAA-compliant audit trail for all system access and data modifications
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

      {/* Summary Stats */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Events</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats.totalEvents.toLocaleString()}
            </div>
            <p className="text-xs text-muted-foreground">All time</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">PHI Access</CardTitle>
            <AlertTriangle className="h-4 w-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-amber-600">
              {stats.phiAccessEvents.toLocaleString()}
            </div>
            <p className="text-xs text-muted-foreground">
              {((stats.phiAccessEvents / stats.totalEvents) * 100).toFixed(1)}% of
              events
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Failed Events</CardTitle>
            <XCircle className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">
              {stats.failedEvents.toLocaleString()}
            </div>
            <p className="text-xs text-muted-foreground">
              {((stats.failedEvents / stats.totalEvents) * 100).toFixed(2)}% failure
              rate
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Unique Users</CardTitle>
            <User className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.uniqueUsers}</div>
            <p className="text-xs text-muted-foreground">Active users</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Today</CardTitle>
            <Calendar className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats.eventsToday.toLocaleString()}
            </div>
            <p className="text-xs text-muted-foreground">Events today</p>
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
                placeholder="Search by user..."
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
                    {type === "all"
                      ? "All Resources"
                      : type.replace("_", " ")}
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
                {filteredLogs.length.toLocaleString()} entries found
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
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
              {paginatedLogs.map((log) => (
                <>
                  <TableRow
                    key={log.id}
                    className={`cursor-pointer hover:bg-muted/50 ${
                      !log.success ? "bg-red-50 dark:bg-red-950/20" : ""
                    }`}
                    onClick={() =>
                      setExpandedLog(expandedLog === log.id ? null : log.id)
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
                        <div className="font-medium">{log.userName}</div>
                        <div className="text-xs text-muted-foreground">
                          {log.ipAddress}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge className={`gap-1 ${getActionColor(log.action)}`}>
                        {getActionIcon(log.action)}
                        {log.action}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Badge className={getResourceTypeColor(log.resourceType)}>
                          {log.resourceType.replace("_", " ")}
                        </Badge>
                        {log.resourceId && (
                          <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                            {log.resourceId}
                          </code>
                        )}
                      </div>
                      {log.patientId && (
                        <div className="text-xs text-muted-foreground mt-1">
                          Patient: {log.patientId}
                        </div>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={log.responseStatus < 400 ? "outline" : "destructive"}
                      >
                        {log.responseStatus}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {log.phiAccessed ? (
                        <Badge className="bg-amber-500 text-white">PHI</Badge>
                      ) : (
                        <span className="text-muted-foreground text-sm">-</span>
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
                    <TableRow>
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
                                  {log.requestMethod}
                                </code>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-muted-foreground">Path:</span>
                                <code className="bg-muted px-1 rounded text-xs">
                                  {log.requestPath}
                                </code>
                              </div>
                            </div>
                          </div>
                          <div>
                            <h4 className="text-sm font-medium mb-2">
                              User Agent
                            </h4>
                            <p className="text-sm text-muted-foreground break-all">
                              {log.userAgent}
                            </p>
                          </div>
                          <div>
                            <h4 className="text-sm font-medium mb-2">User Info</h4>
                            <div className="space-y-1 text-sm">
                              <div className="flex justify-between">
                                <span className="text-muted-foreground">
                                  User ID:
                                </span>
                                <span>{log.userId}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-muted-foreground">
                                  IP Address:
                                </span>
                                <span>{log.ipAddress}</span>
                              </div>
                            </div>
                          </div>
                          <div>
                            <h4 className="text-sm font-medium mb-2">
                              Additional Details
                            </h4>
                            {log.errorMessage && (
                              <div className="text-sm text-red-600 mb-2">
                                Error: {log.errorMessage}
                              </div>
                            )}
                            {log.details && (
                              <pre className="text-xs bg-muted p-2 rounded overflow-auto max-h-24">
                                {JSON.stringify(log.details, null, 2)}
                              </pre>
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

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4">
              <p className="text-sm text-muted-foreground">
                Showing {(currentPage - 1) * pageSize + 1} to{" "}
                {Math.min(currentPage * pageSize, filteredLogs.length)} of{" "}
                {filteredLogs.length} entries
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
                  {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
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
                        variant={currentPage === pageNum ? "default" : "outline"}
                        size="sm"
                        onClick={() => setCurrentPage(pageNum)}
                        className="w-8"
                      >
                        {pageNum}
                      </Button>
                    );
                  })}
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
