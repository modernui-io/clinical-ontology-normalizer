"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  Calendar,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Clock,
  Copy,
  Database,
  Download,
  ExternalLink,
  FileText,
  Loader2,
  MoreHorizontal,
  Play,
  RefreshCw,
  RotateCcw,
  Search,
  Server,
  StopCircle,
  Terminal,
  Timer,
  Trash2,
  User,
  XCircle,
  Activity,
  Zap,
  FileWarning,
  Ban,
} from "lucide-react";

// =============================================================================
// Types
// =============================================================================

type JobStatus = "pending" | "running" | "completed" | "failed" | "cancelled";
type LogLevel = "info" | "warning" | "error" | "debug";

interface JobPhase {
  name: string;
  status: "pending" | "running" | "completed" | "failed" | "skipped";
  startedAt: string | null;
  completedAt: string | null;
  duration: number | null;
  recordsProcessed: number;
  recordsFailed: number;
}

interface LogEntry {
  timestamp: string;
  level: LogLevel;
  message: string;
  phase?: string;
  recordId?: string;
  details?: string;
}

interface JobError {
  id: string;
  timestamp: string;
  phase: string;
  recordId: string | null;
  errorType: string;
  errorMessage: string;
  stackTrace?: string;
  isRetryable: boolean;
  retryCount: number;
}

interface JobDetail {
  id: string;
  name: string;
  description?: string;
  source: {
    id: string;
    name: string;
    type: "fhir" | "hl7v2" | "ccda" | "csv" | "database";
  };
  status: JobStatus;
  progress: number;
  currentPhase: string;
  phases: JobPhase[];
  recordsProcessed: number;
  recordsFailed: number;
  recordsSkipped: number;
  recordsTotal: number;
  startedAt: string | null;
  completedAt: string | null;
  duration: number | null;
  createdAt: string;
  createdBy: string;
  config: {
    batchSize: number;
    maxRecords: number | null;
    skipOnError: boolean;
    maxErrors: number;
  };
  errors: JobError[];
  warnings: string[];
  logs: LogEntry[];
}

// =============================================================================
// Mock Data
// =============================================================================

const MOCK_JOB: JobDetail = {
  id: "job-001",
  name: "Hospital EHR FHIR Sync",
  description: "Daily synchronization of patient data from Epic FHIR server to OMOP CDM",
  source: { id: "src-1", name: "Epic FHIR Server", type: "fhir" },
  status: "running",
  progress: 67,
  currentPhase: "Transforming records",
  phases: [
    {
      name: "Initialization",
      status: "completed",
      startedAt: "2024-01-19T08:30:00Z",
      completedAt: "2024-01-19T08:30:05Z",
      duration: 5,
      recordsProcessed: 0,
      recordsFailed: 0,
    },
    {
      name: "Connection Test",
      status: "completed",
      startedAt: "2024-01-19T08:30:05Z",
      completedAt: "2024-01-19T08:30:08Z",
      duration: 3,
      recordsProcessed: 0,
      recordsFailed: 0,
    },
    {
      name: "Extracting Records",
      status: "completed",
      startedAt: "2024-01-19T08:30:08Z",
      completedAt: "2024-01-19T08:45:32Z",
      duration: 924,
      recordsProcessed: 23000,
      recordsFailed: 0,
    },
    {
      name: "Transforming Records",
      status: "running",
      startedAt: "2024-01-19T08:45:32Z",
      completedAt: null,
      duration: null,
      recordsProcessed: 15420,
      recordsFailed: 23,
    },
    {
      name: "Loading to CDM",
      status: "pending",
      startedAt: null,
      completedAt: null,
      duration: null,
      recordsProcessed: 0,
      recordsFailed: 0,
    },
    {
      name: "Validation",
      status: "pending",
      startedAt: null,
      completedAt: null,
      duration: null,
      recordsProcessed: 0,
      recordsFailed: 0,
    },
  ],
  recordsProcessed: 15420,
  recordsFailed: 23,
  recordsSkipped: 45,
  recordsTotal: 23000,
  startedAt: "2024-01-19T08:30:00Z",
  completedAt: null,
  duration: null,
  createdAt: "2024-01-19T08:29:45Z",
  createdBy: "admin@hospital.org",
  config: {
    batchSize: 1000,
    maxRecords: null,
    skipOnError: true,
    maxErrors: 100,
  },
  errors: [
    {
      id: "err-001",
      timestamp: "2024-01-19T08:52:15Z",
      phase: "Transforming Records",
      recordId: "Patient/12345",
      errorType: "ValidationError",
      errorMessage: "Invalid date format in birth_datetime field",
      stackTrace: "ValidationError: Invalid date format\n  at validateDate (transform.js:45)\n  at processPatient (transform.js:120)\n  at BatchProcessor.process (batch.js:89)",
      isRetryable: false,
      retryCount: 0,
    },
    {
      id: "err-002",
      timestamp: "2024-01-19T08:55:32Z",
      phase: "Transforming Records",
      recordId: "Observation/67890",
      errorType: "MappingError",
      errorMessage: "Unable to map LOINC code 12345-6 to OMOP concept",
      isRetryable: false,
      retryCount: 0,
    },
    {
      id: "err-003",
      timestamp: "2024-01-19T09:02:18Z",
      phase: "Transforming Records",
      recordId: "MedicationRequest/11111",
      errorType: "NetworkError",
      errorMessage: "Connection timeout when fetching medication details",
      stackTrace: "NetworkError: Connection timeout after 30000ms\n  at FetchClient.get (client.js:78)\n  at getMedicationDetails (medication.js:34)",
      isRetryable: true,
      retryCount: 3,
    },
  ],
  warnings: [
    "23 records have missing optional demographic fields",
    "5 medication codes could not be mapped - using generic fallback",
    "Encounter dates for 12 records are in the future - flagged for review",
  ],
  logs: [
    { timestamp: "2024-01-19T08:30:00Z", level: "info", message: "Job started", phase: "Initialization" },
    { timestamp: "2024-01-19T08:30:01Z", level: "info", message: "Loading configuration", phase: "Initialization" },
    { timestamp: "2024-01-19T08:30:03Z", level: "debug", message: "Config loaded: batch_size=1000, max_errors=100", phase: "Initialization" },
    { timestamp: "2024-01-19T08:30:05Z", level: "info", message: "Testing connection to FHIR server", phase: "Connection Test" },
    { timestamp: "2024-01-19T08:30:07Z", level: "info", message: "Connection successful (latency: 145ms)", phase: "Connection Test" },
    { timestamp: "2024-01-19T08:30:08Z", level: "info", message: "Starting record extraction", phase: "Extracting Records" },
    { timestamp: "2024-01-19T08:30:15Z", level: "info", message: "Fetched batch 1/23 (1000 records)", phase: "Extracting Records" },
    { timestamp: "2024-01-19T08:35:22Z", level: "info", message: "Fetched batch 10/23 (10000 records total)", phase: "Extracting Records" },
    { timestamp: "2024-01-19T08:45:32Z", level: "info", message: "Extraction complete: 23000 records", phase: "Extracting Records" },
    { timestamp: "2024-01-19T08:45:33Z", level: "info", message: "Starting transformation phase", phase: "Transforming Records" },
    { timestamp: "2024-01-19T08:52:15Z", level: "error", message: "Validation error for Patient/12345: Invalid date format", phase: "Transforming Records", recordId: "Patient/12345" },
    { timestamp: "2024-01-19T08:55:32Z", level: "warning", message: "Unable to map LOINC code 12345-6", phase: "Transforming Records", recordId: "Observation/67890" },
    { timestamp: "2024-01-19T09:00:00Z", level: "info", message: "Transformed 15000 records (65%)", phase: "Transforming Records" },
    { timestamp: "2024-01-19T09:02:18Z", level: "error", message: "Network timeout for MedicationRequest/11111", phase: "Transforming Records", recordId: "MedicationRequest/11111" },
    { timestamp: "2024-01-19T09:05:00Z", level: "info", message: "Transformed 15420 records (67%)", phase: "Transforming Records" },
  ],
};

// =============================================================================
// Helper Functions
// =============================================================================

const getStatusIcon = (status: JobStatus) => {
  switch (status) {
    case "pending":
      return <Clock className="h-5 w-5 text-muted-foreground" />;
    case "running":
      return <Loader2 className="h-5 w-5 animate-spin text-blue-500" />;
    case "completed":
      return <CheckCircle className="h-5 w-5 text-green-500" />;
    case "failed":
      return <XCircle className="h-5 w-5 text-red-500" />;
    case "cancelled":
      return <StopCircle className="h-5 w-5 text-muted-foreground" />;
  }
};

const getStatusBadge = (status: JobStatus) => {
  switch (status) {
    case "pending":
      return <Badge variant="secondary">Pending</Badge>;
    case "running":
      return <Badge className="bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">Running</Badge>;
    case "completed":
      return <Badge className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">Completed</Badge>;
    case "failed":
      return <Badge variant="destructive">Failed</Badge>;
    case "cancelled":
      return <Badge variant="outline">Cancelled</Badge>;
  }
};

const getPhaseStatusIcon = (status: JobPhase["status"]) => {
  switch (status) {
    case "pending":
      return <div className="h-4 w-4 rounded-full border-2 border-muted" />;
    case "running":
      return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />;
    case "completed":
      return <CheckCircle className="h-4 w-4 text-green-500" />;
    case "failed":
      return <XCircle className="h-4 w-4 text-red-500" />;
    case "skipped":
      return <Ban className="h-4 w-4 text-muted-foreground" />;
  }
};

const getLogLevelIcon = (level: LogLevel) => {
  switch (level) {
    case "info":
      return <Activity className="h-4 w-4 text-blue-500" />;
    case "warning":
      return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
    case "error":
      return <AlertCircle className="h-4 w-4 text-red-500" />;
    case "debug":
      return <Terminal className="h-4 w-4 text-muted-foreground" />;
  }
};

const getLogLevelBadge = (level: LogLevel) => {
  switch (level) {
    case "info":
      return <Badge variant="outline" className="text-blue-600 border-blue-600">INFO</Badge>;
    case "warning":
      return <Badge variant="outline" className="text-yellow-600 border-yellow-600">WARN</Badge>;
    case "error":
      return <Badge variant="destructive">ERROR</Badge>;
    case "debug":
      return <Badge variant="secondary">DEBUG</Badge>;
  }
};

const getSourceIcon = (type: string) => {
  switch (type) {
    case "fhir":
      return <Server className="h-4 w-4" />;
    case "hl7v2":
      return <FileText className="h-4 w-4" />;
    case "ccda":
      return <FileText className="h-4 w-4" />;
    case "csv":
      return <FileText className="h-4 w-4" />;
    case "database":
      return <Database className="h-4 w-4" />;
    default:
      return <Database className="h-4 w-4" />;
  }
};

const formatDuration = (seconds: number | null): string => {
  if (seconds === null) return "-";
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${mins}m`;
};

const formatDateTime = (dateString: string | null): string => {
  if (!dateString) return "-";
  const date = new Date(dateString);
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
};

const formatTime = (dateString: string): string => {
  const date = new Date(dateString);
  return date.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
};

const formatNumber = (num: number): string => {
  return num.toLocaleString();
};

// =============================================================================
// Progress Timeline Component
// =============================================================================

function ProgressTimeline({ phases }: { phases: JobPhase[] }) {
  return (
    <div className="space-y-4">
      {phases.map((phase, index) => {
        const isLast = index === phases.length - 1;
        return (
          <div key={phase.name} className="flex gap-4">
            <div className="flex flex-col items-center">
              {getPhaseStatusIcon(phase.status)}
              {!isLast && (
                <div
                  className={`w-0.5 flex-1 mt-2 ${
                    phase.status === "completed" ? "bg-green-500" : "bg-muted"
                  }`}
                />
              )}
            </div>
            <div className="flex-1 pb-4">
              <div className="flex items-center justify-between">
                <span
                  className={`font-medium ${
                    phase.status === "running" ? "text-blue-600" : ""
                  }`}
                >
                  {phase.name}
                </span>
                {phase.duration !== null && (
                  <span className="text-sm text-muted-foreground">
                    {formatDuration(phase.duration)}
                  </span>
                )}
              </div>
              {phase.status !== "pending" && phase.status !== "skipped" && (
                <div className="mt-1 flex items-center gap-4 text-sm text-muted-foreground">
                  {phase.startedAt && (
                    <span>Started: {formatTime(phase.startedAt)}</span>
                  )}
                  {phase.status === "running" && phase.recordsProcessed > 0 && (
                    <span className="text-green-600">
                      {formatNumber(phase.recordsProcessed)} records
                    </span>
                  )}
                  {phase.recordsFailed > 0 && (
                    <span className="text-red-500">
                      {formatNumber(phase.recordsFailed)} failed
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// =============================================================================
// Log Viewer Component
// =============================================================================

interface LogViewerProps {
  logs: LogEntry[];
}

function LogViewer({ logs }: LogViewerProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [levelFilter, setLevelFilter] = useState<string>("all");

  const filteredLogs = logs.filter((log) => {
    if (searchQuery && !log.message.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }
    if (levelFilter !== "all" && log.level !== levelFilter) {
      return false;
    }
    return true;
  });

  const copyLogs = () => {
    const logText = filteredLogs
      .map((log) => `[${log.timestamp}] [${log.level.toUpperCase()}] ${log.message}`)
      .join("\n");
    navigator.clipboard.writeText(logText);
    toast.success("Logs copied to clipboard");
  };

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search logs..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>
        <select
          value={levelFilter}
          onChange={(e) => setLevelFilter(e.target.value)}
          className="rounded-md border border-input bg-background px-3 py-2 text-sm"
        >
          <option value="all">All Levels</option>
          <option value="info">Info</option>
          <option value="warning">Warning</option>
          <option value="error">Error</option>
          <option value="debug">Debug</option>
        </select>
        <Button variant="outline" size="icon" onClick={copyLogs}>
          <Copy className="h-4 w-4" />
        </Button>
        <Button variant="outline" size="icon">
          <Download className="h-4 w-4" />
        </Button>
      </div>

      <ScrollArea className="h-[400px] rounded-lg border bg-muted/30">
        <div className="p-4 font-mono text-sm space-y-2">
          {filteredLogs.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">
              No logs matching the current filter
            </p>
          ) : (
            filteredLogs.map((log, idx) => (
              <div
                key={idx}
                className={`flex items-start gap-3 p-2 rounded ${
                  log.level === "error"
                    ? "bg-red-500/10"
                    : log.level === "warning"
                    ? "bg-yellow-500/10"
                    : ""
                }`}
              >
                {getLogLevelIcon(log.level)}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs text-muted-foreground">
                      {formatTime(log.timestamp)}
                    </span>
                    {getLogLevelBadge(log.level)}
                    {log.phase && (
                      <Badge variant="secondary" className="text-xs">
                        {log.phase}
                      </Badge>
                    )}
                    {log.recordId && (
                      <span className="text-xs text-muted-foreground">
                        {log.recordId}
                      </span>
                    )}
                  </div>
                  <p className="mt-1 break-words">{log.message}</p>
                </div>
              </div>
            ))
          )}
        </div>
      </ScrollArea>
    </div>
  );
}

// =============================================================================
// Error Details Component
// =============================================================================

interface ErrorDetailsProps {
  errors: JobError[];
  onRetry?: (errorId: string) => void;
}

function ErrorDetails({ errors, onRetry }: ErrorDetailsProps) {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const toggleExpanded = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  if (errors.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <CheckCircle className="h-12 w-12 text-green-500/50" />
        <h3 className="mt-4 text-lg font-medium">No Errors</h3>
        <p className="mt-2 text-muted-foreground">
          This job has not encountered any errors
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {errors.map((error) => (
        <Collapsible
          key={error.id}
          open={expandedIds.has(error.id)}
          onOpenChange={() => toggleExpanded(error.id)}
        >
          <Card className="border-red-500/20">
            <CardHeader className="pb-3">
              <CollapsibleTrigger className="flex items-center justify-between w-full text-left">
                <div className="flex items-center gap-3">
                  <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0" />
                  <div>
                    <p className="font-medium">{error.errorType}</p>
                    <p className="text-sm text-muted-foreground line-clamp-1">
                      {error.errorMessage}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {error.isRetryable && (
                    <Badge variant="outline" className="text-yellow-600 border-yellow-600">
                      Retryable
                    </Badge>
                  )}
                  {expandedIds.has(error.id) ? (
                    <ChevronDown className="h-4 w-4" />
                  ) : (
                    <ChevronRight className="h-4 w-4" />
                  )}
                </div>
              </CollapsibleTrigger>
            </CardHeader>
            <CollapsibleContent>
              <CardContent className="pt-0 space-y-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <p className="text-xs font-medium text-muted-foreground">Timestamp</p>
                    <p className="text-sm">{formatDateTime(error.timestamp)}</p>
                  </div>
                  <div>
                    <p className="text-xs font-medium text-muted-foreground">Phase</p>
                    <p className="text-sm">{error.phase}</p>
                  </div>
                  {error.recordId && (
                    <div>
                      <p className="text-xs font-medium text-muted-foreground">Record ID</p>
                      <p className="text-sm font-mono">{error.recordId}</p>
                    </div>
                  )}
                  {error.retryCount > 0 && (
                    <div>
                      <p className="text-xs font-medium text-muted-foreground">Retry Count</p>
                      <p className="text-sm">{error.retryCount}</p>
                    </div>
                  )}
                </div>

                <div>
                  <p className="text-xs font-medium text-muted-foreground mb-1">Error Message</p>
                  <p className="text-sm rounded-lg bg-red-500/10 p-3">{error.errorMessage}</p>
                </div>

                {error.stackTrace && (
                  <div>
                    <p className="text-xs font-medium text-muted-foreground mb-1">Stack Trace</p>
                    <pre className="text-xs rounded-lg bg-muted p-3 overflow-x-auto">
                      {error.stackTrace}
                    </pre>
                  </div>
                )}

                {error.isRetryable && onRetry && (
                  <div className="flex justify-end">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onRetry(error.id)}
                    >
                      <RotateCcw className="mr-2 h-4 w-4" />
                      Retry Record
                    </Button>
                  </div>
                )}
              </CardContent>
            </CollapsibleContent>
          </Card>
        </Collapsible>
      ))}
    </div>
  );
}

// =============================================================================
// Main Job Detail Page Component
// =============================================================================

export default function JobDetailPage() {
  const params = useParams();
  const router = useRouter();
  const jobId = params.jobId as string;

  const [job, setJob] = useState<JobDetail | null>(MOCK_JOB);
  const [isLoading, setIsLoading] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [isRetrying, setIsRetrying] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  // Auto-refresh for running jobs
  useEffect(() => {
    if (!job || job.status !== "running") return;

    const interval = setInterval(() => {
      setJob((prev) => {
        if (!prev || prev.status !== "running") return prev;
        const newProgress = Math.min(prev.progress + Math.random() * 2, 99);
        const newRecordsProcessed = Math.floor((newProgress / 100) * prev.recordsTotal);

        return {
          ...prev,
          progress: Math.round(newProgress),
          recordsProcessed: newRecordsProcessed,
          phases: prev.phases.map((phase) =>
            phase.status === "running"
              ? { ...phase, recordsProcessed: newRecordsProcessed }
              : phase
          ),
        };
      });
    }, 3000);

    return () => clearInterval(interval);
  }, [job?.status]);

  const handleCancel = async () => {
    setIsCancelling(true);
    await new Promise((resolve) => setTimeout(resolve, 1000));
    setJob((prev) =>
      prev
        ? {
            ...prev,
            status: "cancelled",
            currentPhase: "Cancelled by user",
            completedAt: new Date().toISOString(),
          }
        : null
    );
    setIsCancelling(false);
    toast.success("Job cancelled successfully");
  };

  const handleRetry = async () => {
    setIsRetrying(true);
    await new Promise((resolve) => setTimeout(resolve, 1000));
    toast.success("Job requeued successfully");
    setIsRetrying(false);
    router.push("/etl/jobs");
  };

  const handleDelete = async () => {
    setIsDeleting(true);
    await new Promise((resolve) => setTimeout(resolve, 1000));
    toast.success("Job deleted successfully");
    setIsDeleting(false);
    router.push("/etl/jobs");
  };

  if (!job) {
    return (
      <div className="p-6">
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <FileWarning className="mx-auto h-12 w-12 text-muted-foreground" />
            <h2 className="mt-4 text-lg font-semibold">Job Not Found</h2>
            <p className="mt-2 text-muted-foreground">
              The job you&apos;re looking for doesn&apos;t exist or has been deleted.
            </p>
            <Link href="/etl/jobs">
              <Button className="mt-4">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Jobs
              </Button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const successRate =
    job.recordsProcessed > 0
      ? Math.round(
          ((job.recordsProcessed - job.recordsFailed) / job.recordsProcessed) * 100
        )
      : 0;

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <Link
            href="/etl/jobs"
            className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground mb-2"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Jobs
          </Link>
          <div className="flex items-center gap-3">
            {getStatusIcon(job.status)}
            <div>
              <h1 className="text-2xl font-bold tracking-tight">{job.name}</h1>
              <p className="text-muted-foreground">{job.description}</p>
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          {(job.status === "running" || job.status === "pending") && (
            <Button
              variant="outline"
              onClick={handleCancel}
              disabled={isCancelling}
            >
              {isCancelling ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <StopCircle className="mr-2 h-4 w-4" />
              )}
              Cancel Job
            </Button>
          )}
          {job.status === "failed" && (
            <Button
              variant="outline"
              onClick={handleRetry}
              disabled={isRetrying}
            >
              {isRetrying ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <RotateCcw className="mr-2 h-4 w-4" />
              )}
              Retry Job
            </Button>
          )}
          <Button
            variant="destructive"
            onClick={() => setShowDeleteDialog(true)}
            disabled={job.status === "running"}
          >
            <Trash2 className="mr-2 h-4 w-4" />
            Delete
          </Button>
        </div>
      </div>

      {/* Status and Progress */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Job Status</CardTitle>
              {getStatusBadge(job.status)}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Progress</span>
              <span className="font-medium">{job.progress}%</span>
            </div>
            <Progress value={job.progress} className="h-3" />
            <p className="text-sm text-muted-foreground">
              Current Phase: <span className="font-medium">{job.currentPhase}</span>
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Records Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-2xl font-bold text-green-600">
                  {formatNumber(job.recordsProcessed)}
                </p>
                <p className="text-xs text-muted-foreground">Processed</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-red-500">
                  {formatNumber(job.recordsFailed)}
                </p>
                <p className="text-xs text-muted-foreground">Failed</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-muted-foreground">
                  {formatNumber(job.recordsSkipped)}
                </p>
                <p className="text-xs text-muted-foreground">Skipped</p>
              </div>
              <div>
                <p className="text-2xl font-bold">
                  {successRate}%
                </p>
                <p className="text-xs text-muted-foreground">Success Rate</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Job Metadata */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Job Details</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">Source</p>
              <div className="flex items-center gap-2">
                {getSourceIcon(job.source.type)}
                <span className="text-sm">{job.source.name}</span>
              </div>
            </div>
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">Created By</p>
              <div className="flex items-center gap-2">
                <User className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm">{job.createdBy}</span>
              </div>
            </div>
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">Started At</p>
              <div className="flex items-center gap-2">
                <Calendar className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm">{formatDateTime(job.startedAt)}</span>
              </div>
            </div>
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">Duration</p>
              <div className="flex items-center gap-2">
                <Timer className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm">
                  {job.duration !== null
                    ? formatDuration(job.duration)
                    : job.startedAt
                    ? "Running..."
                    : "-"}
                </span>
              </div>
            </div>
          </div>
          <Separator className="my-4" />
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">Batch Size</p>
              <span className="text-sm">{formatNumber(job.config.batchSize)}</span>
            </div>
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">Max Records</p>
              <span className="text-sm">{job.config.maxRecords ? formatNumber(job.config.maxRecords) : "Unlimited"}</span>
            </div>
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">Skip On Error</p>
              <span className="text-sm">{job.config.skipOnError ? "Yes" : "No"}</span>
            </div>
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">Max Errors</p>
              <span className="text-sm">{formatNumber(job.config.maxErrors)}</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Warnings */}
      {job.warnings.length > 0 && (
        <Card className="border-yellow-500/30">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-yellow-500" />
              Warnings ({job.warnings.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {job.warnings.map((warning, idx) => (
                <li
                  key={idx}
                  className="flex items-start gap-2 text-sm text-yellow-700 dark:text-yellow-400"
                >
                  <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                  {warning}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Tabs: Timeline, Logs, Errors */}
      <Tabs defaultValue="timeline">
        <TabsList>
          <TabsTrigger value="timeline">
            <Activity className="mr-2 h-4 w-4" />
            Timeline
          </TabsTrigger>
          <TabsTrigger value="logs">
            <Terminal className="mr-2 h-4 w-4" />
            Logs ({job.logs.length})
          </TabsTrigger>
          <TabsTrigger value="errors">
            <AlertCircle className="mr-2 h-4 w-4" />
            Errors ({job.errors.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="timeline" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Progress Timeline</CardTitle>
              <CardDescription>
                Track the progress of each phase in the ETL pipeline
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ProgressTimeline phases={job.phases} />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="logs" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Job Logs</CardTitle>
              <CardDescription>
                Real-time execution logs with search and filtering
              </CardDescription>
            </CardHeader>
            <CardContent>
              <LogViewer logs={job.logs} />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="errors" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Error Details</CardTitle>
              <CardDescription>
                Detailed information about errors encountered during execution
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ErrorDetails errors={job.errors} />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Delete Confirmation Dialog */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Job</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this job? This will also delete all
              associated logs and history. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowDeleteDialog(false)}
              disabled={isDeleting}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={isDeleting}
            >
              {isDeleting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Deleting...
                </>
              ) : (
                <>
                  <Trash2 className="mr-2 h-4 w-4" />
                  Delete Job
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
