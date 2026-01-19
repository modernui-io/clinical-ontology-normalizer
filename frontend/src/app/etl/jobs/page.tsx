"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { toast } from "sonner";
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
import { Progress } from "@/components/ui/progress";
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  AlertCircle,
  ArrowRight,
  Calendar,
  CheckCircle,
  Clock,
  Database,
  ExternalLink,
  FileText,
  Loader2,
  MoreHorizontal,
  Pause,
  Play,
  RefreshCw,
  RotateCcw,
  Search,
  Server,
  StopCircle,
  Trash2,
  XCircle,
  Activity,
  BarChart3,
  Timer,
  Zap,
} from "lucide-react";

// =============================================================================
// Types
// =============================================================================

type JobStatus = "pending" | "running" | "completed" | "failed" | "cancelled";

interface ETLJob {
  id: string;
  name: string;
  source: {
    id: string;
    name: string;
    type: "fhir" | "hl7v2" | "ccda" | "csv" | "database";
  };
  status: JobStatus;
  progress: number;
  currentPhase: string;
  recordsProcessed: number;
  recordsFailed: number;
  recordsTotal: number;
  startedAt: string | null;
  completedAt: string | null;
  duration: number | null; // in seconds
  createdAt: string;
  createdBy: string;
  errorMessage?: string;
}

interface JobStatistics {
  totalJobs: number;
  completedToday: number;
  failedToday: number;
  avgDuration: number; // in seconds
  recordsProcessedToday: number;
  activeJobs: number;
}

// =============================================================================
// Mock Data
// =============================================================================

const MOCK_JOBS: ETLJob[] = [
  {
    id: "job-001",
    name: "Hospital EHR FHIR Sync",
    source: { id: "src-1", name: "Epic FHIR Server", type: "fhir" },
    status: "running",
    progress: 67,
    currentPhase: "Transforming records",
    recordsProcessed: 15420,
    recordsFailed: 23,
    recordsTotal: 23000,
    startedAt: "2024-01-19T08:30:00Z",
    completedAt: null,
    duration: null,
    createdAt: "2024-01-19T08:29:45Z",
    createdBy: "admin@hospital.org",
  },
  {
    id: "job-002",
    name: "Lab Results Daily Import",
    source: { id: "src-2", name: "Lab CSV Export", type: "csv" },
    status: "completed",
    progress: 100,
    currentPhase: "Completed",
    recordsProcessed: 8542,
    recordsFailed: 12,
    recordsTotal: 8554,
    startedAt: "2024-01-19T06:00:00Z",
    completedAt: "2024-01-19T06:45:32Z",
    duration: 2732,
    createdAt: "2024-01-19T05:59:00Z",
    createdBy: "scheduler",
  },
  {
    id: "job-003",
    name: "Medication Reconciliation",
    source: { id: "src-3", name: "Pharmacy Database", type: "database" },
    status: "pending",
    progress: 0,
    currentPhase: "Queued",
    recordsProcessed: 0,
    recordsFailed: 0,
    recordsTotal: 12500,
    startedAt: null,
    completedAt: null,
    duration: null,
    createdAt: "2024-01-19T09:15:00Z",
    createdBy: "admin@hospital.org",
  },
  {
    id: "job-004",
    name: "Patient Demographics Sync",
    source: { id: "src-1", name: "Epic FHIR Server", type: "fhir" },
    status: "failed",
    progress: 34,
    currentPhase: "Failed - Connection timeout",
    recordsProcessed: 3421,
    recordsFailed: 156,
    recordsTotal: 10000,
    startedAt: "2024-01-19T02:00:00Z",
    completedAt: "2024-01-19T02:23:45Z",
    duration: 1425,
    createdAt: "2024-01-19T01:59:00Z",
    createdBy: "scheduler",
    errorMessage: "Connection to FHIR server timed out after 3 retries",
  },
  {
    id: "job-005",
    name: "HL7 ADT Message Processing",
    source: { id: "src-4", name: "HL7 Interface Engine", type: "hl7v2" },
    status: "running",
    progress: 89,
    currentPhase: "Loading to CDM",
    recordsProcessed: 4450,
    recordsFailed: 8,
    recordsTotal: 5000,
    startedAt: "2024-01-19T09:00:00Z",
    completedAt: null,
    duration: null,
    createdAt: "2024-01-19T08:59:30Z",
    createdBy: "integration@hospital.org",
  },
  {
    id: "job-006",
    name: "Clinical Notes C-CDA Import",
    source: { id: "src-5", name: "Document Repository", type: "ccda" },
    status: "cancelled",
    progress: 45,
    currentPhase: "Cancelled by user",
    recordsProcessed: 2250,
    recordsFailed: 34,
    recordsTotal: 5000,
    startedAt: "2024-01-18T14:00:00Z",
    completedAt: "2024-01-18T14:45:00Z",
    duration: 2700,
    createdAt: "2024-01-18T13:59:00Z",
    createdBy: "admin@hospital.org",
  },
  {
    id: "job-007",
    name: "Insurance Claims Import",
    source: { id: "src-6", name: "Claims Database", type: "database" },
    status: "completed",
    progress: 100,
    currentPhase: "Completed",
    recordsProcessed: 45000,
    recordsFailed: 89,
    recordsTotal: 45089,
    startedAt: "2024-01-18T00:00:00Z",
    completedAt: "2024-01-18T02:15:45Z",
    duration: 8145,
    createdAt: "2024-01-17T23:59:00Z",
    createdBy: "scheduler",
  },
  {
    id: "job-008",
    name: "Vitals Data Sync",
    source: { id: "src-1", name: "Epic FHIR Server", type: "fhir" },
    status: "completed",
    progress: 100,
    currentPhase: "Completed",
    recordsProcessed: 125000,
    recordsFailed: 234,
    recordsTotal: 125234,
    startedAt: "2024-01-17T22:00:00Z",
    completedAt: "2024-01-18T00:30:00Z",
    duration: 9000,
    createdAt: "2024-01-17T21:59:00Z",
    createdBy: "scheduler",
  },
];

const MOCK_STATISTICS: JobStatistics = {
  totalJobs: 156,
  completedToday: 12,
  failedToday: 2,
  avgDuration: 2845,
  recordsProcessedToday: 245000,
  activeJobs: 2,
};

// =============================================================================
// Helper Functions
// =============================================================================

const getStatusIcon = (status: JobStatus) => {
  switch (status) {
    case "pending":
      return <Clock className="h-4 w-4 text-muted-foreground" />;
    case "running":
      return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />;
    case "completed":
      return <CheckCircle className="h-4 w-4 text-green-500" />;
    case "failed":
      return <XCircle className="h-4 w-4 text-red-500" />;
    case "cancelled":
      return <StopCircle className="h-4 w-4 text-muted-foreground" />;
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
  });
};

const formatNumber = (num: number): string => {
  return num.toLocaleString();
};

// =============================================================================
// Statistics Cards Component
// =============================================================================

function StatisticsCards({ stats }: { stats: JobStatistics }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-blue-500/10 p-2">
              <Activity className="h-5 w-5 text-blue-500" />
            </div>
            <div>
              <p className="text-2xl font-bold">{stats.activeJobs}</p>
              <p className="text-xs text-muted-foreground">Active Jobs</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-green-500/10 p-2">
              <CheckCircle className="h-5 w-5 text-green-500" />
            </div>
            <div>
              <p className="text-2xl font-bold">{stats.completedToday}</p>
              <p className="text-xs text-muted-foreground">Completed Today</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-red-500/10 p-2">
              <XCircle className="h-5 w-5 text-red-500" />
            </div>
            <div>
              <p className="text-2xl font-bold">{stats.failedToday}</p>
              <p className="text-xs text-muted-foreground">Failed Today</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-purple-500/10 p-2">
              <Timer className="h-5 w-5 text-purple-500" />
            </div>
            <div>
              <p className="text-2xl font-bold">{formatDuration(stats.avgDuration)}</p>
              <p className="text-xs text-muted-foreground">Avg Duration</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-orange-500/10 p-2">
              <Zap className="h-5 w-5 text-orange-500" />
            </div>
            <div>
              <p className="text-2xl font-bold">{formatNumber(stats.recordsProcessedToday)}</p>
              <p className="text-xs text-muted-foreground">Records Today</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-indigo-500/10 p-2">
              <BarChart3 className="h-5 w-5 text-indigo-500" />
            </div>
            <div>
              <p className="text-2xl font-bold">{stats.totalJobs}</p>
              <p className="text-xs text-muted-foreground">Total Jobs</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// =============================================================================
// Job Row Component
// =============================================================================

interface JobRowProps {
  job: ETLJob;
  onCancel: (jobId: string) => void;
  onRetry: (jobId: string) => void;
  onDelete: (jobId: string) => void;
  isCancelling: boolean;
}

function JobRow({ job, onCancel, onRetry, onDelete, isCancelling }: JobRowProps) {
  const successRate = job.recordsProcessed > 0
    ? Math.round(((job.recordsProcessed - job.recordsFailed) / job.recordsProcessed) * 100)
    : 0;

  return (
    <TableRow>
      <TableCell>
        <div className="flex items-center gap-3">
          {getStatusIcon(job.status)}
          <div>
            <Link
              href={`/etl/jobs/${job.id}`}
              className="font-medium hover:underline"
            >
              {job.name}
            </Link>
            <p className="text-xs text-muted-foreground">
              {job.currentPhase}
            </p>
          </div>
        </div>
      </TableCell>
      <TableCell>
        <div className="flex items-center gap-2">
          {getSourceIcon(job.source.type)}
          <span className="text-sm">{job.source.name}</span>
        </div>
      </TableCell>
      <TableCell>
        {getStatusBadge(job.status)}
      </TableCell>
      <TableCell>
        {job.status === "running" || job.status === "pending" ? (
          <div className="space-y-1 min-w-[120px]">
            <Progress value={job.progress} className="h-2" />
            <p className="text-xs text-muted-foreground text-right">
              {job.progress}%
            </p>
          </div>
        ) : (
          <span className="text-sm text-muted-foreground">
            {job.status === "completed" ? "100%" : `${job.progress}%`}
          </span>
        )}
      </TableCell>
      <TableCell className="text-sm">
        <div>
          <span className="text-green-600">{formatNumber(job.recordsProcessed)}</span>
          {job.recordsFailed > 0 && (
            <span className="text-red-500 ml-1">
              (-{formatNumber(job.recordsFailed)})
            </span>
          )}
        </div>
        <p className="text-xs text-muted-foreground">
          of {formatNumber(job.recordsTotal)}
        </p>
      </TableCell>
      <TableCell className="text-sm text-muted-foreground">
        {formatDateTime(job.startedAt)}
      </TableCell>
      <TableCell className="text-sm text-muted-foreground">
        {formatDuration(job.duration)}
      </TableCell>
      <TableCell>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon">
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem asChild>
              <Link href={`/etl/jobs/${job.id}`}>
                <ExternalLink className="mr-2 h-4 w-4" />
                View Details
              </Link>
            </DropdownMenuItem>
            {(job.status === "running" || job.status === "pending") && (
              <DropdownMenuItem
                onClick={() => onCancel(job.id)}
                disabled={isCancelling}
              >
                <StopCircle className="mr-2 h-4 w-4" />
                Cancel Job
              </DropdownMenuItem>
            )}
            {job.status === "failed" && (
              <DropdownMenuItem onClick={() => onRetry(job.id)}>
                <RotateCcw className="mr-2 h-4 w-4" />
                Retry Job
              </DropdownMenuItem>
            )}
            <DropdownMenuSeparator />
            <DropdownMenuItem
              className="text-destructive"
              onClick={() => onDelete(job.id)}
              disabled={job.status === "running"}
            >
              <Trash2 className="mr-2 h-4 w-4" />
              Delete Job
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </TableCell>
    </TableRow>
  );
}

// =============================================================================
// Delete Confirmation Dialog
// =============================================================================

interface DeleteDialogProps {
  job: ETLJob | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  isDeleting: boolean;
}

function DeleteDialog({ job, open, onOpenChange, onConfirm, isDeleting }: DeleteDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete Job</DialogTitle>
          <DialogDescription>
            Are you sure you want to delete the job &quot;{job?.name}&quot;? This will also delete
            all associated logs and history. This action cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isDeleting}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={onConfirm} disabled={isDeleting}>
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
  );
}

// =============================================================================
// Main Jobs Page Component
// =============================================================================

export default function JobsPage() {
  const [jobs, setJobs] = useState<ETLJob[]>(MOCK_JOBS);
  const [statistics] = useState<JobStatistics>(MOCK_STATISTICS);

  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [sourceFilter, setSourceFilter] = useState<string>("all");
  const [dateFilter, setDateFilter] = useState<string>("all");

  const [isRefreshing, setIsRefreshing] = useState(false);
  const [cancellingJobId, setCancellingJobId] = useState<string | null>(null);
  const [deleteJob, setDeleteJob] = useState<ETLJob | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Get unique sources for filter
  const uniqueSources = Array.from(new Set(jobs.map((j) => j.source.name)));

  // Filter jobs
  const filteredJobs = jobs.filter((job) => {
    if (searchQuery && !job.name.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }
    if (statusFilter !== "all" && job.status !== statusFilter) {
      return false;
    }
    if (sourceFilter !== "all" && job.source.name !== sourceFilter) {
      return false;
    }
    // Date filter logic would go here
    return true;
  });

  // Sort jobs: running first, then pending, then by createdAt
  const sortedJobs = [...filteredJobs].sort((a, b) => {
    const statusOrder: Record<JobStatus, number> = {
      running: 0,
      pending: 1,
      failed: 2,
      completed: 3,
      cancelled: 4,
    };
    if (statusOrder[a.status] !== statusOrder[b.status]) {
      return statusOrder[a.status] - statusOrder[b.status];
    }
    return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
  });

  // Refresh jobs
  const handleRefresh = async () => {
    setIsRefreshing(true);
    await new Promise((resolve) => setTimeout(resolve, 1000));
    setIsRefreshing(false);
    toast.success("Jobs refreshed");
  };

  // Cancel job
  const handleCancel = async (jobId: string) => {
    setCancellingJobId(jobId);
    await new Promise((resolve) => setTimeout(resolve, 1000));
    setJobs((prev) =>
      prev.map((job) =>
        job.id === jobId
          ? { ...job, status: "cancelled" as const, currentPhase: "Cancelled by user" }
          : job
      )
    );
    setCancellingJobId(null);
    toast.success("Job cancelled successfully");
  };

  // Retry job
  const handleRetry = async (jobId: string) => {
    const job = jobs.find((j) => j.id === jobId);
    if (!job) return;

    // Create a new job based on the failed one
    const newJob: ETLJob = {
      ...job,
      id: `job-${Date.now()}`,
      status: "pending",
      progress: 0,
      currentPhase: "Queued",
      recordsProcessed: 0,
      recordsFailed: 0,
      startedAt: null,
      completedAt: null,
      duration: null,
      createdAt: new Date().toISOString(),
      errorMessage: undefined,
    };

    setJobs((prev) => [newJob, ...prev]);
    toast.success("Job requeued successfully");
  };

  // Delete job
  const handleDeleteConfirm = async () => {
    if (!deleteJob) return;

    setIsDeleting(true);
    await new Promise((resolve) => setTimeout(resolve, 1000));
    setJobs((prev) => prev.filter((job) => job.id !== deleteJob.id));
    setIsDeleting(false);
    setDeleteJob(null);
    toast.success("Job deleted successfully");
  };

  // Auto-refresh running jobs
  useEffect(() => {
    const hasRunningJobs = jobs.some((job) => job.status === "running");
    if (!hasRunningJobs) return;

    const interval = setInterval(() => {
      setJobs((prev) =>
        prev.map((job) => {
          if (job.status !== "running") return job;
          const newProgress = Math.min(job.progress + Math.random() * 5, 100);
          const newRecordsProcessed = Math.floor((newProgress / 100) * job.recordsTotal);

          if (newProgress >= 100) {
            return {
              ...job,
              status: "completed" as const,
              progress: 100,
              currentPhase: "Completed",
              recordsProcessed: job.recordsTotal - job.recordsFailed,
              completedAt: new Date().toISOString(),
              duration: Math.floor((Date.now() - new Date(job.startedAt!).getTime()) / 1000),
            };
          }

          return {
            ...job,
            progress: Math.round(newProgress),
            recordsProcessed: newRecordsProcessed,
          };
        })
      );
    }, 3000);

    return () => clearInterval(interval);
  }, [jobs]);

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">ETL Jobs</h1>
          <p className="text-muted-foreground">
            Monitor and manage batch ETL job executions
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={isRefreshing}
          >
            <RefreshCw
              className={`mr-2 h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
          <Link href="/etl/wizard">
            <Button size="sm">
              <Play className="mr-2 h-4 w-4" />
              New Job
            </Button>
          </Link>
        </div>
      </div>

      {/* Statistics */}
      <StatisticsCards stats={statistics} />

      {/* Filters */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Filter Jobs</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-4">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search jobs..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[150px]">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="running">Running</SelectItem>
                <SelectItem value="completed">Completed</SelectItem>
                <SelectItem value="failed">Failed</SelectItem>
                <SelectItem value="cancelled">Cancelled</SelectItem>
              </SelectContent>
            </Select>
            <Select value={sourceFilter} onValueChange={setSourceFilter}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Source" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Sources</SelectItem>
                {uniqueSources.map((source) => (
                  <SelectItem key={source} value={source}>
                    {source}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={dateFilter} onValueChange={setDateFilter}>
              <SelectTrigger className="w-[150px]">
                <SelectValue placeholder="Date" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Time</SelectItem>
                <SelectItem value="today">Today</SelectItem>
                <SelectItem value="yesterday">Yesterday</SelectItem>
                <SelectItem value="week">This Week</SelectItem>
                <SelectItem value="month">This Month</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Jobs Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            Jobs ({sortedJobs.length})
          </CardTitle>
          <CardDescription>
            {jobs.filter((j) => j.status === "running").length} running,{" "}
            {jobs.filter((j) => j.status === "pending").length} pending
          </CardDescription>
        </CardHeader>
        <CardContent>
          {sortedJobs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Database className="h-12 w-12 text-muted-foreground/50" />
              <h3 className="mt-4 text-lg font-medium">No jobs found</h3>
              <p className="mt-2 text-muted-foreground">
                {searchQuery || statusFilter !== "all" || sourceFilter !== "all"
                  ? "Try adjusting your filters"
                  : "Create your first ETL job to get started"}
              </p>
              {!searchQuery && statusFilter === "all" && sourceFilter === "all" && (
                <Link href="/etl/wizard">
                  <Button className="mt-4">
                    <Play className="mr-2 h-4 w-4" />
                    Create Job
                  </Button>
                </Link>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="min-w-[200px]">Job</TableHead>
                    <TableHead>Source</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Progress</TableHead>
                    <TableHead>Records</TableHead>
                    <TableHead>Started</TableHead>
                    <TableHead>Duration</TableHead>
                    <TableHead className="w-[60px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sortedJobs.map((job) => (
                    <JobRow
                      key={job.id}
                      job={job}
                      onCancel={handleCancel}
                      onRetry={handleRetry}
                      onDelete={(jobId) => {
                        const jobToDelete = jobs.find((j) => j.id === jobId);
                        if (jobToDelete) setDeleteJob(jobToDelete);
                      }}
                      isCancelling={cancellingJobId === job.id}
                    />
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <DeleteDialog
        job={deleteJob}
        open={!!deleteJob}
        onOpenChange={(open) => !open && setDeleteJob(null)}
        onConfirm={handleDeleteConfirm}
        isDeleting={isDeleting}
      />
    </div>
  );
}
