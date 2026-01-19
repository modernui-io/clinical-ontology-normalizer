"use client";

import { useState } from "react";
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
import { Label } from "@/components/ui/label";
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
  Database,
  FileText,
  Loader2,
  Play,
  Plus,
  RefreshCw,
  Server,
  Square,
  Trash2,
  X,
  CheckCircle,
  AlertCircle,
  Clock,
  XCircle,
} from "lucide-react";
import {
  useETLJobs,
  useETLConnectors,
  useCreateETLJob,
  useCancelETLJob,
  useDeleteETLJob,
  useETLJobPolling,
} from "@/hooks/use-api";
import type {
  ETLJob,
  ConnectorInfo,
  CreateETLJobRequest,
} from "@/lib/api";

// =============================================================================
// Status Badge Component
// =============================================================================

const STATUS_CONFIG: Record<
  ETLJob["state"],
  { label: string; variant: "default" | "secondary" | "destructive" | "outline"; icon: React.ReactNode }
> = {
  pending: {
    label: "Pending",
    variant: "secondary",
    icon: <Clock className="h-3 w-3" />,
  },
  running: {
    label: "Running",
    variant: "default",
    icon: <Loader2 className="h-3 w-3 animate-spin" />,
  },
  completed: {
    label: "Completed",
    variant: "outline",
    icon: <CheckCircle className="h-3 w-3 text-green-500" />,
  },
  failed: {
    label: "Failed",
    variant: "destructive",
    icon: <AlertCircle className="h-3 w-3" />,
  },
  cancelled: {
    label: "Cancelled",
    variant: "secondary",
    icon: <XCircle className="h-3 w-3" />,
  },
};

function StatusBadge({ state }: { state: ETLJob["state"] }) {
  const config = STATUS_CONFIG[state];
  return (
    <Badge variant={config.variant} className="gap-1">
      {config.icon}
      {config.label}
    </Badge>
  );
}

// =============================================================================
// Connector Icon Component
// =============================================================================

const CONNECTOR_ICONS: Record<string, React.ReactNode> = {
  fhir: <Server className="h-4 w-4" />,
  csv: <FileText className="h-4 w-4" />,
  hl7v2: <FileText className="h-4 w-4" />,
  ccda: <FileText className="h-4 w-4" />,
  database: <Database className="h-4 w-4" />,
};

function ConnectorIcon({ type }: { type: string }) {
  return CONNECTOR_ICONS[type] || <Database className="h-4 w-4" />;
}

// =============================================================================
// Create Job Modal/Form
// =============================================================================

interface CreateJobFormProps {
  connectors: ConnectorInfo[];
  onSubmit: (request: CreateETLJobRequest) => void;
  onCancel: () => void;
  isLoading: boolean;
}

function CreateJobForm({ connectors, onSubmit, onCancel, isLoading }: CreateJobFormProps) {
  const [connectorType, setConnectorType] = useState<string>("");
  const [connectionString, setConnectionString] = useState("");
  const [sourceName, setSourceName] = useState("");
  const [batchSize, setBatchSize] = useState(100);
  const [maxRecords, setMaxRecords] = useState<string>("");

  const selectedConnector = connectors.find((c) => c.type === connectorType);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!connectorType) {
      toast.error("Please select a connector type");
      return;
    }

    if (!connectionString) {
      toast.error("Please enter a connection string");
      return;
    }

    const request: CreateETLJobRequest = {
      connector_type: connectorType,
      connection_string: connectionString,
      source_name: sourceName || undefined,
      batch_size: batchSize,
      max_records: maxRecords ? parseInt(maxRecords, 10) : undefined,
    };

    onSubmit(request);
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Create New ETL Job</CardTitle>
            <CardDescription>
              Configure and start a new data extraction job
            </CardDescription>
          </div>
          <Button variant="ghost" size="icon" onClick={onCancel}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Connector Type Selection */}
          <div className="space-y-2">
            <Label>Data Source Type</Label>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-5">
              {connectors.map((connector) => (
                <button
                  key={connector.type}
                  type="button"
                  onClick={() => setConnectorType(connector.type)}
                  className={`flex flex-col items-center gap-2 rounded-lg border p-3 transition-colors hover:bg-muted/50 ${
                    connectorType === connector.type
                      ? "border-primary bg-primary/5"
                      : "border-border"
                  }`}
                >
                  <ConnectorIcon type={connector.type} />
                  <span className="text-xs font-medium">{connector.name}</span>
                </button>
              ))}
            </div>
            {selectedConnector && (
              <p className="text-sm text-muted-foreground">
                {selectedConnector.description}
              </p>
            )}
          </div>

          {/* Connection String */}
          <div className="space-y-2">
            <Label htmlFor="connectionString">Connection String</Label>
            <Input
              id="connectionString"
              placeholder={selectedConnector?.connection_string_hint || "Enter connection string"}
              value={connectionString}
              onChange={(e) => setConnectionString(e.target.value)}
            />
            {selectedConnector && (
              <p className="text-xs text-muted-foreground">
                Example: {selectedConnector.connection_string_hint}
              </p>
            )}
          </div>

          {/* Source Name */}
          <div className="space-y-2">
            <Label htmlFor="sourceName">Source Name (optional)</Label>
            <Input
              id="sourceName"
              placeholder="e.g., Hospital EHR, Lab System"
              value={sourceName}
              onChange={(e) => setSourceName(e.target.value)}
            />
          </div>

          {/* Batch Size and Max Records */}
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="batchSize">Batch Size</Label>
              <Input
                id="batchSize"
                type="number"
                min={1}
                max={10000}
                value={batchSize}
                onChange={(e) => setBatchSize(parseInt(e.target.value, 10) || 100)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="maxRecords">Max Records (optional)</Label>
              <Input
                id="maxRecords"
                type="number"
                min={1}
                placeholder="No limit"
                value={maxRecords}
                onChange={(e) => setMaxRecords(e.target.value)}
              />
            </div>
          </div>

          {/* Submit Buttons */}
          <div className="flex justify-end gap-2 pt-4">
            <Button type="button" variant="outline" onClick={onCancel}>
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading || !connectorType}>
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Creating...
                </>
              ) : (
                <>
                  <Play className="mr-2 h-4 w-4" />
                  Create Job
                </>
              )}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

// =============================================================================
// Job Row Component
// =============================================================================

interface JobRowProps {
  job: ETLJob;
  onCancel: (jobId: string) => void;
  onDelete: (jobId: string) => void;
  isCancelling: boolean;
  isDeleting: boolean;
}

function JobRow({ job, onCancel, onDelete, isCancelling, isDeleting }: JobRowProps) {
  const isActive = job.state === "running" || job.state === "pending";
  const canCancel = isActive;
  const canDelete = !isActive;

  // Format duration
  const formatDuration = (seconds: number | null) => {
    if (seconds === null) return "-";
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds.toFixed(0)}s`;
  };

  // Format date
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <TableRow>
      <TableCell>
        <div className="flex items-center gap-2">
          <ConnectorIcon type={job.config.connector_type} />
          <div>
            <p className="font-medium">
              {job.config.source_name || job.config.connector_type.toUpperCase()}
            </p>
            <p className="text-xs text-muted-foreground">
              {job.job_id.slice(0, 8)}...
            </p>
          </div>
        </div>
      </TableCell>
      <TableCell>
        <StatusBadge state={job.state} />
      </TableCell>
      <TableCell>
        {job.state === "running" ? (
          <div className="w-32 space-y-1">
            <Progress value={job.progress.overall_progress_percent} />
            <p className="text-xs text-muted-foreground">
              {job.progress.overall_progress_percent.toFixed(1)}%
            </p>
          </div>
        ) : job.state === "completed" ? (
          <span className="text-green-600">100%</span>
        ) : job.state === "failed" ? (
          <span className="text-red-600">
            {job.errors.length > 0 ? `${job.errors.length} errors` : "Failed"}
          </span>
        ) : (
          "-"
        )}
      </TableCell>
      <TableCell>
        <div className="text-sm">
          <p>{job.statistics.total_records.toLocaleString()} records</p>
          <p className="text-xs text-muted-foreground">
            {job.statistics.patients_processed} patients
          </p>
        </div>
      </TableCell>
      <TableCell className="text-muted-foreground">
        {formatDate(job.created_at)}
      </TableCell>
      <TableCell className="text-muted-foreground">
        {formatDuration(job.duration_seconds)}
      </TableCell>
      <TableCell>
        <div className="flex gap-1">
          {canCancel && (
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onCancel(job.job_id)}
              disabled={isCancelling}
              title="Cancel job"
            >
              {isCancelling ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Square className="h-4 w-4" />
              )}
            </Button>
          )}
          {canDelete && (
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onDelete(job.job_id)}
              disabled={isDeleting}
              title="Delete job"
            >
              {isDeleting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="h-4 w-4 text-destructive" />
              )}
            </Button>
          )}
        </div>
      </TableCell>
    </TableRow>
  );
}

// =============================================================================
// Job Details Panel
// =============================================================================

interface JobDetailsPanelProps {
  jobId: string;
  onClose: () => void;
}

function JobDetailsPanel({ jobId, onClose }: JobDetailsPanelProps) {
  const { data: job, isLoading } = useETLJobPolling(jobId, {
    pollingInterval: 2000,
  });

  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-8">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  if (!job) {
    return null;
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <ConnectorIcon type={job.config.connector_type} />
              {job.config.source_name || job.config.connector_type.toUpperCase()}
            </CardTitle>
            <CardDescription>Job ID: {job.job_id}</CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge state={job.state} />
            <Button variant="ghost" size="icon" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Progress Section */}
        {(job.state === "running" || job.state === "pending") && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span>Progress</span>
              <span>{job.progress.overall_progress_percent.toFixed(1)}%</span>
            </div>
            <Progress value={job.progress.overall_progress_percent} className="h-3" />
            <p className="text-sm text-muted-foreground">
              Phase: {job.progress.current_phase.replace(/_/g, " ")}
              {job.progress.eta_seconds && (
                <> | ETA: {Math.round(job.progress.eta_seconds)}s</>
              )}
            </p>
          </div>
        )}

        {/* Statistics */}
        <div>
          <h4 className="mb-2 font-medium">Statistics</h4>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div className="rounded-lg bg-muted/50 p-3">
              <p className="text-2xl font-bold">
                {job.statistics.total_records.toLocaleString()}
              </p>
              <p className="text-xs text-muted-foreground">Total Records</p>
            </div>
            <div className="rounded-lg bg-muted/50 p-3">
              <p className="text-2xl font-bold">
                {job.statistics.patients_processed.toLocaleString()}
              </p>
              <p className="text-xs text-muted-foreground">Patients</p>
            </div>
            <div className="rounded-lg bg-muted/50 p-3">
              <p className="text-2xl font-bold">
                {job.statistics.records_created.toLocaleString()}
              </p>
              <p className="text-xs text-muted-foreground">Created</p>
            </div>
            <div className="rounded-lg bg-muted/50 p-3">
              <p className="text-2xl font-bold">
                {job.statistics.unmapped_codes.toLocaleString()}
              </p>
              <p className="text-xs text-muted-foreground">Unmapped</p>
            </div>
          </div>
        </div>

        {/* Errors */}
        {job.errors.length > 0 && (
          <div>
            <h4 className="mb-2 font-medium text-destructive">
              Errors ({job.errors.length})
            </h4>
            <div className="max-h-40 space-y-2 overflow-y-auto">
              {job.errors.slice(0, 5).map((error, index) => (
                <div
                  key={index}
                  className="rounded-lg border border-destructive/20 bg-destructive/5 p-2 text-sm"
                >
                  <p className="font-medium">{error.error_type}</p>
                  <p className="text-muted-foreground">{error.error_message}</p>
                  <p className="text-xs text-muted-foreground">
                    Phase: {error.phase}
                    {error.record_id && <> | Record: {error.record_id}</>}
                  </p>
                </div>
              ))}
              {job.errors.length > 5 && (
                <p className="text-sm text-muted-foreground">
                  ...and {job.errors.length - 5} more errors
                </p>
              )}
            </div>
          </div>
        )}

        {/* Warnings */}
        {job.warnings.length > 0 && (
          <div>
            <h4 className="mb-2 font-medium text-yellow-600">
              Warnings ({job.warnings.length})
            </h4>
            <div className="max-h-32 space-y-1 overflow-y-auto">
              {job.warnings.slice(0, 5).map((warning, index) => (
                <p key={index} className="text-sm text-muted-foreground">
                  {warning}
                </p>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// =============================================================================
// Main ETL Page Component
// =============================================================================

export default function ETLPage() {
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [stateFilter, setStateFilter] = useState<string>("");
  const [cancellingJobId, setCancellingJobId] = useState<string | null>(null);
  const [deletingJobId, setDeletingJobId] = useState<string | null>(null);

  // Queries
  const { data: connectorsData, isLoading: isLoadingConnectors } = useETLConnectors();
  const {
    data: jobsData,
    isLoading: isLoadingJobs,
    refetch: refetchJobs,
  } = useETLJobs(
    { state: stateFilter || undefined, limit: 50 },
    { refetchInterval: 5000 } // Auto-refresh every 5 seconds
  );

  // Mutations
  const createJobMutation = useCreateETLJob({
    onSuccess: (data) => {
      toast.success(`ETL job created: ${data.job_id.slice(0, 8)}...`);
      setShowCreateForm(false);
      setSelectedJobId(data.job_id);
    },
    onError: (error) => {
      toast.error(`Failed to create job: ${error.message}`);
    },
  });

  const cancelJobMutation = useCancelETLJob({
    onSuccess: (data) => {
      if (data.cancelled) {
        toast.success("Job cancellation requested");
      } else {
        toast.info(data.message);
      }
      setCancellingJobId(null);
    },
    onError: (error) => {
      toast.error(`Failed to cancel job: ${error.message}`);
      setCancellingJobId(null);
    },
  });

  const deleteJobMutation = useDeleteETLJob({
    onSuccess: (data) => {
      if (data.deleted) {
        toast.success("Job deleted");
        if (selectedJobId === data.job_id) {
          setSelectedJobId(null);
        }
      } else {
        toast.info(data.message);
      }
      setDeletingJobId(null);
    },
    onError: (error) => {
      toast.error(`Failed to delete job: ${error.message}`);
      setDeletingJobId(null);
    },
  });

  const handleCreateJob = (request: CreateETLJobRequest) => {
    createJobMutation.mutate(request);
  };

  const handleCancelJob = (jobId: string) => {
    setCancellingJobId(jobId);
    cancelJobMutation.mutate(jobId);
  };

  const handleDeleteJob = (jobId: string) => {
    setDeletingJobId(jobId);
    deleteJobMutation.mutate(jobId);
  };

  const connectors = connectorsData?.connectors || [];
  const jobs = jobsData?.jobs || [];

  // Count jobs by state for filter badges
  const jobCounts = jobs.reduce(
    (acc, job) => {
      acc[job.state] = (acc[job.state] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">ETL Jobs</h1>
          <p className="text-muted-foreground">
            Manage data extraction and transformation jobs
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetchJobs()}
            disabled={isLoadingJobs}
          >
            <RefreshCw
              className={`mr-2 h-4 w-4 ${isLoadingJobs ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
          <Button size="sm" onClick={() => setShowCreateForm(true)}>
            <Plus className="mr-2 h-4 w-4" />
            New Job
          </Button>
        </div>
      </div>

      {/* Create Job Form */}
      {showCreateForm && (
        <CreateJobForm
          connectors={connectors}
          onSubmit={handleCreateJob}
          onCancel={() => setShowCreateForm(false)}
          isLoading={createJobMutation.isPending}
        />
      )}

      {/* Filter Tabs */}
      <div className="flex flex-wrap gap-2">
        <Button
          variant={stateFilter === "" ? "default" : "outline"}
          size="sm"
          onClick={() => setStateFilter("")}
        >
          All ({jobs.length})
        </Button>
        {["running", "pending", "completed", "failed", "cancelled"].map((state) => (
          <Button
            key={state}
            variant={stateFilter === state ? "default" : "outline"}
            size="sm"
            onClick={() => setStateFilter(state)}
          >
            {state.charAt(0).toUpperCase() + state.slice(1)} ({jobCounts[state] || 0})
          </Button>
        ))}
      </div>

      {/* Main Content Grid */}
      <div className={`grid gap-6 ${selectedJobId ? "lg:grid-cols-2" : ""}`}>
        {/* Jobs Table */}
        <Card>
          <CardHeader>
            <CardTitle>Jobs</CardTitle>
            <CardDescription>
              {jobs.length} job{jobs.length !== 1 ? "s" : ""} total
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoadingJobs ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : jobs.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <Database className="h-12 w-12 text-muted-foreground/50" />
                <p className="mt-2 text-muted-foreground">No ETL jobs found</p>
                <Button
                  variant="outline"
                  className="mt-4"
                  onClick={() => setShowCreateForm(true)}
                >
                  <Plus className="mr-2 h-4 w-4" />
                  Create your first job
                </Button>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Source</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Progress</TableHead>
                    <TableHead>Records</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead>Duration</TableHead>
                    <TableHead className="w-20">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {jobs.map((job) => (
                    <TableRow
                      key={job.job_id}
                      className={`cursor-pointer ${
                        selectedJobId === job.job_id ? "bg-muted/50" : ""
                      }`}
                      onClick={() => setSelectedJobId(job.job_id)}
                    >
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <ConnectorIcon type={job.config.connector_type} />
                          <div>
                            <p className="font-medium">
                              {job.config.source_name ||
                                job.config.connector_type.toUpperCase()}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {job.job_id.slice(0, 8)}...
                            </p>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <StatusBadge state={job.state} />
                      </TableCell>
                      <TableCell>
                        {job.state === "running" ? (
                          <div className="w-24 space-y-1">
                            <Progress value={job.progress.overall_progress_percent} />
                            <p className="text-xs text-muted-foreground">
                              {job.progress.overall_progress_percent.toFixed(0)}%
                            </p>
                          </div>
                        ) : job.state === "completed" ? (
                          <span className="text-green-600">100%</span>
                        ) : job.state === "failed" ? (
                          <span className="text-red-600">
                            {job.errors.length} errors
                          </span>
                        ) : (
                          "-"
                        )}
                      </TableCell>
                      <TableCell>
                        {job.statistics.total_records.toLocaleString()}
                      </TableCell>
                      <TableCell className="text-muted-foreground text-sm">
                        {new Date(job.created_at).toLocaleDateString()}
                      </TableCell>
                      <TableCell className="text-muted-foreground text-sm">
                        {job.duration_seconds
                          ? `${job.duration_seconds.toFixed(1)}s`
                          : "-"}
                      </TableCell>
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        <div className="flex gap-1">
                          {(job.state === "running" || job.state === "pending") && (
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleCancelJob(job.job_id)}
                              disabled={cancellingJobId === job.job_id}
                              title="Cancel job"
                            >
                              {cancellingJobId === job.job_id ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <Square className="h-4 w-4" />
                              )}
                            </Button>
                          )}
                          {job.state !== "running" && job.state !== "pending" && (
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleDeleteJob(job.job_id)}
                              disabled={deletingJobId === job.job_id}
                              title="Delete job"
                            >
                              {deletingJobId === job.job_id ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <Trash2 className="h-4 w-4 text-destructive" />
                              )}
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* Job Details Panel */}
        {selectedJobId && (
          <JobDetailsPanel
            jobId={selectedJobId}
            onClose={() => setSelectedJobId(null)}
          />
        )}
      </div>
    </div>
  );
}
